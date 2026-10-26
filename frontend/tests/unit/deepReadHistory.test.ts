// 딥리드 대화 기록(utils/deepReadHistory) — 이 브라우저에 자료별 대화를 남겨 사이드바 'DeepRead' 묶음과 대화 복원에 쓴다(2026-10-26)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEEP_READ_HISTORY_KEY,
  DEEP_READ_HISTORY_MAX,
  DEEP_READ_MESSAGES_MAX,
  cleanMessages,
  deepReadRoute,
  firstQuestion,
  questionCount,
  removeConversation,
  resetDeepReadHistoryForTest,
  saveConversation,
  savedSession,
  useDeepReadHistory,
} from "~/utils/deepReadHistory";
import type { DeepReadMessage } from "~/utils/deepReadSse";
import { MemoryStorage } from "./helpers/memoryStorage";

let storage: MemoryStorage;

beforeEach(() => {
  storage = new MemoryStorage();
  vi.stubGlobal("window", { localStorage: storage, addEventListener: () => {} });
  resetDeepReadHistoryForTest();
});
afterEach(() => {
  vi.unstubAllGlobals();
  resetDeepReadHistoryForTest();
});

const turn = (q: string, a: string, page = 2): DeepReadMessage[] => [
  { role: "user", content: q },
  { role: "assistant", content: `${a} [p.${page + 1}]`, sources: [{ page_start: page, page_end: page, text: "원문".repeat(2000) }], pinnedChip: 0 },
];

describe("saveConversation · savedSession", () => {
  it("답을 받은 대화를 남기고 다시 읽는다 — 화면 상태(펼친 출처)는 빼고 출처 원문은 줄여서", () => {
    saveConversation("S1", "KCI_1", "노인의 사회적 지지", "paper", turn("누가 효과적?", "가족"));
    const saved = savedSession("KCI_1")!.messages;
    expect(saved.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(saved[1]!.pinnedChip).toBeUndefined();
    expect(saved[1]!.sources![0]!.text.length).toBe(4000);
    expect(JSON.parse(storage.getItem(DEEP_READ_HISTORY_KEY)!)[0].title).toBe("노인의 사회적 지지");
  });

  it("답이 없는 대화(질문만)는 남기지 않는다", () => {
    saveConversation("S1", "KCI_1", "t", "paper", [{ role: "user", content: "질문" }]);
    expect(savedSession("KCI_1")).toBeNull();
  });

  it("같은 자료는 하나로 묶여 맨 앞으로 오고, 자료 수는 상한에서 오래된 것부터 빠진다", () => {
    for (let n = 0; n < DEEP_READ_HISTORY_MAX + 3; n++) saveConversation(`D${n}`, `doc${n}`, `t${n}`, "book", turn("q", "a"));
    saveConversation("D5", "doc5", "t5", "book", turn("q2", "a2"));
    const { items } = useDeepReadHistory();
    expect(items.value).toHaveLength(DEEP_READ_HISTORY_MAX);
    expect(items.value.filter((i) => i.id === "D5")).toHaveLength(1);
    expect(items.value.some((i) => i.id === "D0")).toBe(false);
  });

  it("말이 많으면 끝의 상한만, 질문에서 시작하게 남긴다", () => {
    const long: DeepReadMessage[] = [];
    for (let n = 0; n < DEEP_READ_MESSAGES_MAX; n++) long.push(...turn(`q${n}`, `a${n}`));
    const kept = cleanMessages(long);
    expect(kept.length).toBeLessThanOrEqual(DEEP_READ_MESSAGES_MAX);
    expect(kept[0]!.role).toBe("user");
    expect(kept.at(-1)!.content).toContain(`a${DEEP_READ_MESSAGES_MAX - 1}`);
  });

  it("저장소가 가득 차면 오래된 자료부터 빼며 다시 쓰고, 막혀도 던지지 않는다", () => {
    storage = new MemoryStorage(22000);
    vi.stubGlobal("window", { localStorage: storage, addEventListener: () => {} });
    resetDeepReadHistoryForTest();
    for (let n = 0; n < 6; n++) saveConversation(`D${n}`, `doc${n}`, `t${n}`, "paper", turn("q", "a"));
    const stored = JSON.parse(storage.getItem(DEEP_READ_HISTORY_KEY)!);
    expect(stored[0].id).toBe("D5");
    expect(stored.length).toBeLessThan(6);
    storage.failWith = new Error("blocked");
    expect(() => saveConversation("X", "docX", "x", "paper", turn("q", "a"))).not.toThrow();
  });

  it("깨진 저장 값은 무시한다", () => {
    storage.setItem(DEEP_READ_HISTORY_KEY, "{not json");
    resetDeepReadHistoryForTest();
    expect(useDeepReadHistory().items.value).toEqual([]);
    storage.setItem(DEEP_READ_HISTORY_KEY, JSON.stringify([{ id: "A" }, { id: "B", docId: "D", title: "t", kind: "paper", updatedAt: "2026-10-26T00:00:00Z", messages: [] }]));
    resetDeepReadHistoryForTest();
    expect(useDeepReadHistory().items.value.map((i) => i.id)).toEqual(["B"]);
  });

  it("지우면 목록과 저장소에서 빠진다", () => {
    saveConversation("A", "docA", "a", "paper", turn("q", "a"));
    removeConversation("A");
    expect(useDeepReadHistory().items.value).toEqual([]);
    expect(storage.getItem(DEEP_READ_HISTORY_KEY)).toBeNull();   // 마지막 하나를 지우면 키째 지운다
  });
});

// 한 자료에 대화가 여럿 — [새 대화](사용자 2026-10-26). 고른 대화(?dr=)가 그 자료의 것이면 그것, 아니면 그 자료의 가장 최근 대화
describe("한 자료의 여러 대화", () => {
  it("대화마다 따로 남고, 고른 대화나 가장 최근 대화를 되살린다 — 멀티턴 말과 출처를 모두", async () => {
    saveConversation("S1", "KCI_1", "t", "paper", turn("첫 대화 질문", "답1"));
    await new Promise((r) => setTimeout(r, 5));
    saveConversation("S2", "KCI_1", "t", "paper", [...turn("둘째 대화 질문", "답2"), ...turn("이어 묻기", "답3", 5)]);
    expect(useDeepReadHistory().items.value.map((i) => i.id)).toEqual(["S2", "S1"]);
    expect(savedSession("KCI_1")!.id).toBe("S2");
    const s2 = savedSession("KCI_1", "S2")!.messages;
    expect(s2.map((m) => m.role)).toEqual(["user", "assistant", "user", "assistant"]);
    expect(s2[3]!.sources![0]!.page_start).toBe(5);
    expect(savedSession("KCI_1", "S1")!.messages[0]!.content).toBe("첫 대화 질문");
    expect(savedSession("OTHER", "S1")).toBeNull();               // 다른 자료의 대화 id 는 쓰지 않는다
    expect(firstQuestion(useDeepReadHistory().items.value[0]!)).toBe("둘째 대화 질문");
  });
});

describe("deepReadRoute · questionCount", () => {
  it("논문은 /papers, 소장자료는 /books 상세로 — 딥리드 창을 연 채로(?chat=1), 그 대화로(?dr=)", () => {
    expect(deepReadRoute({ id: "S1", docId: "KCI_FI002782062", kind: "paper" })).toEqual({
      path: "/papers/KCI_FI002782062",
      query: { chat: "1", dr: "S1" },
    });
    expect(deepReadRoute({ id: "S2", docId: "PSN-SONAGI", kind: "book" })).toEqual({
      path: "/books/PSN-SONAGI",
      query: { chat: "1", dr: "S2" },
    });
  });
  it("질문 수는 사용자 말만 센다", () => {
    expect(questionCount({ messages: [...turn("q1", "a1"), ...turn("q2", "a2")] })).toBe(2);
  });
});

describe("BookChat · AppSidebar 연결", () => {
  const chat = readFileSync(resolve(__dirname, "../../components/BookChat.vue"), "utf-8").replace(/\r\n/g, "\n");
  const sidebar = readFileSync(resolve(__dirname, "../../components/AppSidebar.vue"), "utf-8").replace(/\r\n/g, "\n");

  it("답을 다 받거나 멈추면 남기고, 화면에 붙은 뒤·자료가 바뀐 뒤 남긴 대화를 되살린다(store 를 넘긴 곳은 되살리지 않는다)", () => {
    expect(chat).toContain("saveConversation(sessionId.value, props.cntsId, props.bookTitle || props.cntsId, props.docKind, messages.value)");
    expect(chat).toContain('<button type="button" class="skx-chat-new" @click="startNewConversation">새 대화</button>');
    expect(chat).toContain("onMounted(restoreSaved);");
    expect(chat).toContain("if (props.store || messages.value.length || isStreaming.value) return;");
  });

  it("사이드바는 대화가 있을 때만 'DeepRead' 묶음을 그리고, 누르면 그 자료 상세로 간다", () => {
    expect(sidebar).toContain('v-if="deepReadRows.length"');
    expect(sidebar).toContain('@click="goDeepRead(d)"');
    expect(sidebar).toContain("void router.push(deepReadRoute(d));");
  });
});
