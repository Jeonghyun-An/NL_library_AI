// frontend/tests/unit/researchStart.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parse } from "vue/compiler-sfc";
import { DEEP_RESEARCH } from "~/utils/brand";
import {
  NOTICE_CANCEL_ARM_MS,
  NOTICE_CANCEL_CONFIRM_TEXT,
  NOTICE_CANCEL_DONE_TEXT,
  noticeCancelBack,
  noticeCancelLabel,
  noticeCancelPress,
  noticeFocusTarget,
  researchStartState,
  startNotice,
} from "~/utils/researchStart";
import { ID1, ID2, ID3, bookEntry, researchEntry } from "./helpers/fakeHistory";

const ID4 = "44444444-4444-4444-8444-444444444444";
const ID5 = "55555555-5555-4555-8555-555555555555";
const T = (hour: number) => `2026-10-13T${String(hour).padStart(2, "0")}:00:00.000Z`;
const status = (s: string) => ({ research: { status: s, stage: "planned" } });

describe("researchStartState", () => {
  it("끝나지 않은 연구를 진행 중(순서 대기 포함)과 승인 대기로 가르고 각각 가장 최근 것부터 둔다", () => {
    const older = researchEntry(ID1, { createdAt: T(1), ...status("running") });
    const newer = researchEntry(ID2, { createdAt: T(3), ...status("queued") });
    const waiting = researchEntry(ID3, { createdAt: T(2), ...status("awaiting_approval") });
    const done = researchEntry(ID4, { createdAt: T(9), ...status("completed") });
    expect(researchStartState([older, newer, waiting, done, bookEntry(ID5, { createdAt: T(10) })])).toEqual({
      live: [newer, older],
      awaiting: [waiting],
    });
  });

  it("사이드바 배지의 진행 중 상태(created·planning·approved·queued·running)를 모두 진행 중으로 본다", () => {
    for (const s of ["created", "planning", "approved", "queued", "running"]) {
      expect(researchStartState([researchEntry(ID1, status(s))]).live.map((e) => e.id)).toEqual([ID1]);
    }
    for (const s of ["awaiting_approval", "completed", "failed", "canceled"]) {
      expect(researchStartState([researchEntry(ID1, status(s))]).live).toEqual([]);
    }
    // 상태를 모르는 기록(옛 기록·조회 실패)은 어느 쪽도 아니다
    expect(researchStartState([researchEntry(ID1)])).toEqual({ live: [], awaiting: [] });
  });

  it("시각은 updatedAt 이 있으면 그것을 보고, 읽을 수 없는 시각은 가장 오래된 것으로 친다", () => {
    const a = researchEntry(ID1, { createdAt: T(5), updatedAt: T(6), ...status("running") });
    const b = researchEntry(ID2, { createdAt: T(7), ...status("running") });
    const c = researchEntry(ID3, { createdAt: "어제", ...status("running") });
    const d = researchEntry(ID4, { createdAt: T(4), updatedAt: T(9), ...status("running") });
    expect(researchStartState([c, a, b, d]).live.map((e) => e.id)).toEqual([ID4, ID2, ID1, ID3]);
    expect(researchStartState([])).toEqual({ live: [], awaiting: [] });
  });
});

describe("startNotice — DeepResearch 모드 입력창의 한 줄", () => {
  it("진행 중인 연구가 있으면 그 수와 가장 최근 것 — 승인 대기가 함께 있어도 진행 중이 먼저", () => {
    const live = researchEntry(ID1, { createdAt: T(2), ...status("running") });
    const queued = researchEntry(ID2, { createdAt: T(1), ...status("queued") });
    const awaiting = researchEntry(ID3, { createdAt: T(3), ...status("awaiting_approval") });
    expect(startNotice(researchStartState([queued, awaiting, live]))).toEqual({
      text: `진행 중인 ${DEEP_RESEARCH} 2건`,
      jobId: ID1,
      to: { path: `/research/${ID1}` },
    });
  });

  it("승인 대기만 있으면 승인 대기 줄, 끝나지 않은 연구가 없으면 null — [보기]·[취소]는 기록의 잡 id(refId)", () => {
    const awaiting = researchEntry(ID2, { ...status("awaiting_approval"), refId: ID5 });
    expect(startNotice(researchStartState([awaiting]))).toEqual({
      text: `승인 대기 중인 ${DEEP_RESEARCH} 1건`,
      jobId: ID5,
      to: { path: `/research/${ID5}` },
    });
    expect(startNotice(researchStartState([researchEntry(ID1, status("completed"))]))).toBeNull();
  });
});

describe("noticeCancelPress · noticeCancelLabel — [취소]는 한 번 더 눌러 확인한다", () => {
  it("첫 누름은 '정말 취소'로 바꾸기만 하고, 확인은 잠깐 뒤의 두 번째 누름에서만 — 더블클릭 한 번에 넘어가지 않는다", () => {
    expect(noticeCancelPress("idle", 0, 1000)).toBe("arm");
    expect(noticeCancelPress("confirm", 1000, 1000 + NOTICE_CANCEL_ARM_MS - 1)).toBeNull();
    expect(noticeCancelPress("confirm", 1000, 1000 + NOTICE_CANCEL_ARM_MS)).toBe("run");
    // 취소하는 중에는 다시 받지 않는다
    expect(noticeCancelPress("busy", 1000, 99999)).toBeNull();
  });

  it("버튼 글은 취소 → 정말 취소 → 취소하는 중", () => {
    expect((["idle", "confirm", "busy"] as const).map(noticeCancelLabel)).toEqual(["취소", "정말 취소", "취소하는 중"]);
  });
});

describe("noticeCancelBack — 확인에서 물러나기([그대로 두기]·Esc)", () => {
  it("확인 중일 때만 처음으로 돌린다 — 그 밖의 Esc 는 받지 않아 페이지(+ 메뉴 닫기 등)로 흘려보낸다", () => {
    expect(noticeCancelBack("confirm")).toBe("idle");
    expect(noticeCancelBack("idle")).toBeNull();
    expect(noticeCancelBack("busy")).toBeNull();
  });
});

describe("noticeFocusTarget — 확인을 풀거나 취소가 끝난 뒤 초점(사이드바 clearGroup 의 대체 경로와 같은 방식)", () => {
  const el = (isConnected = true) => ({ isConnected });
  const body = el();

  it("쥔 버튼이 사라져 초점이 body 로 떨어졌으면 — 취소 버튼이 남아 있으면 그것, 줄째 사라졌으면 입력창", () => {
    const cancelBtn = el();
    const field = el();
    expect(noticeFocusTarget({ active: body, body }, cancelBtn, field)).toBe(cancelBtn);
    expect(noticeFocusTarget({ active: body, body }, el(false), field)).toBe(field);
    expect(noticeFocusTarget({ active: body, body }, null, field)).toBe(field);
    expect(noticeFocusTarget({ active: null, body }, null, field)).toBe(field);
    // 입력창마저 없으면 옮길 곳이 없다
    expect(noticeFocusTarget({ active: body, body }, null, el(false))).toBeNull();
  });

  it("초점이 취소 버튼에 묶여 있거나(취소하는 동안 잠김) DOM 에서 빠진 요소에 남아 있어도 잃은 것으로 본다", () => {
    const cancelBtn = el();
    const field = el();
    expect(noticeFocusTarget({ active: cancelBtn, body }, cancelBtn, field)).toBe(cancelBtn);
    expect(noticeFocusTarget({ active: el(false), body }, cancelBtn, field)).toBe(cancelBtn);
  });

  it("기다리는 동안 사용자가 다른 곳(입력창·다른 버튼)으로 옮겼으면 null — 초점을 빼앗지 않는다", () => {
    const cancelBtn = el();
    const field = el();
    expect(noticeFocusTarget({ active: field, body }, cancelBtn, field)).toBeNull();
    expect(noticeFocusTarget({ active: el(), body }, cancelBtn, field)).toBeNull();
  });
});

describe("확인·취소를 스크린리더에 알리는 문구", () => {
  it("확인 문구는 '정말 취소할까요?'로 시작하고 물러나는 길([그대로 두기]·Esc)을 함께 알린다 — 성공은 DeepResearch 를 취소했다는 말", () => {
    expect(NOTICE_CANCEL_CONFIRM_TEXT.startsWith("정말 취소할까요?")).toBe(true);
    expect(NOTICE_CANCEL_CONFIRM_TEXT).toContain("그대로 두기");
    expect(NOTICE_CANCEL_CONFIRM_TEXT).toContain("Esc");
    expect(NOTICE_CANCEL_DONE_TEXT).toBe(`${DEEP_RESEARCH}를 취소했습니다`);
  });
});

// 컴포넌트를 띄우지 않는 단위 테스트 환경(DOM 없음)이라 SearchPlusMenu 의 템플릿을 읽어 알림 줄의 키보드·스크린리더 계약을 본다
interface TplProp {
  type: number;
  name: string;
  value?: { content: string };
  arg?: { content?: string };
  exp?: { content?: string };
  modifiers?: (string | { content: string })[];
}
interface TplNode {
  type: number;
  tag?: string;
  content?: string | { content?: string };
  props?: TplProp[];
  children?: TplNode[];
}
const ELEMENT = 1;
const ATTRIBUTE = 6;
const DIRECTIVE = 7;
const INTERPOLATION = 5;

function elements(nodes: TplNode[], out: TplNode[] = []): TplNode[] {
  for (const n of nodes) {
    if (n.type === ELEMENT) out.push(n);
    if (n.children) elements(n.children, out);
  }
  return out;
}

const attr = (n: TplNode, name: string) => n.props?.find((p) => p.type === ATTRIBUTE && p.name === name)?.value?.content;
const bind = (n: TplNode, name: string) =>
  n.props?.find((p) => p.type === DIRECTIVE && p.name === "bind" && p.arg?.content === name)?.exp?.content;
const on = (n: TplNode, event: string) => n.props?.filter((p) => p.type === DIRECTIVE && p.name === "on" && p.arg?.content === event) ?? [];
const modifiers = (p: TplProp) => (p.modifiers ?? []).map((m) => (typeof m === "string" ? m : m.content));
const conditional = (n: TplNode) => (n.props ?? []).some((p) => p.type === DIRECTIVE && ["if", "else-if", "else", "show"].includes(p.name));
const hasClass = (n: TplNode, cls: string) => (attr(n, "class") ?? "").split(/\s+/).includes(cls);
const interpolations = (n: TplNode) =>
  (n.children ?? [])
    .filter((c) => c.type === INTERPOLATION)
    .map((c) => (typeof c.content === "object" ? c.content?.content ?? "" : ""))
    .map((s) => s.trim());
const textOf = (n: TplNode): string =>
  (n.children ?? []).map((c) => (typeof c.content === "string" ? c.content : c.children ? textOf(c) : "")).join("").trim();

describe("SearchPlusMenu 알림 줄 — 한 번 확인하는 과정의 초점·키보드·알림", () => {
  const source = readFileSync(fileURLToPath(new URL("../../components/research/SearchPlusMenu.vue", import.meta.url)), "utf8");
  const { descriptor } = parse(source);
  const tpl = descriptor.template?.ast as unknown as TplNode;
  const script = descriptor.scriptSetup?.content ?? "";
  const root = elements(tpl.children ?? []).find((n) => hasClass(n, "rs-plus"))!;
  const all = elements(root.children ?? []);
  const note = all.find((n) => hasClass(n, "rs-start-note"))!;
  const noteEls = elements(note.children ?? []);
  const cancelBtn = noteEls.find((n) => n.tag === "button" && interpolations(n).some((s) => s.startsWith("noticeCancelLabel(")))!;
  const keepBtn = noteEls.find((n) => n.tag === "button" && textOf(n) === "그대로 두기")!;

  it("+ 메뉴 뿌리에 늘 DOM 에 있는(조건 없는) 숨김 live 영역이 있다 — 줄째 사라져도 '취소했습니다'가 들린다", () => {
    const live = (root.children ?? []).filter(
      (n) => n.type === ELEMENT && attr(n, "role") === "status" && hasClass(n, "rs-sr-only") && !conditional(n),
    );
    expect(live).toHaveLength(1);
    expect(interpolations(live[0]!)).toHaveLength(1);
    expect(script).toContain("NOTICE_CANCEL_DONE_TEXT");
  });

  it("취소 버튼은 ref 로 쥐고(물러난 뒤·취소가 끝난 뒤 초점을 돌릴 곳), 확인 중이면 숨김 확인 문구를 aria-describedby 로 단다", () => {
    expect(cancelBtn).toBeTruthy();
    expect(attr(cancelBtn, "ref")).toBe("cancelBtn");
    const described = bind(cancelBtn, "aria-describedby");
    expect(described).toBeTruthy();
    const desc = noteEls.find((n) => hasClass(n, "rs-sr-only") && interpolations(n).includes("NOTICE_CANCEL_CONFIRM_TEXT"));
    expect(desc).toBeTruthy();
    // 버튼의 aria-describedby 가 그 문구의 id 를 가리킨다(확인 중이 아니면 undefined)
    expect(described).toContain(bind(desc!, "id"));
    expect(script).toContain("noticeFocusTarget");
  });

  it("줄에서 Esc 를 들어 확인에서 물러난다", () => {
    const esc = on(note, "keydown").filter((p) => modifiers(p).includes("esc"));
    expect(esc).toHaveLength(1);
  });

  it("[그대로 두기]는 상태만 바꾸는 인라인 대입이 아니라 초점을 취소 버튼으로 돌리는 함수를 부른다 — 사라지는 버튼의 초점이 body 로 떨어지지 않게", () => {
    expect(keepBtn).toBeTruthy();
    const click = on(keepBtn, "click")[0]?.exp?.content ?? "";
    expect(click).toMatch(/^[A-Za-z_$][\w$]*$/);
    expect(click).not.toContain("=");
  });
});
