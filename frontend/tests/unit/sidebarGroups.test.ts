// frontend/tests/unit/sidebarGroups.test.ts
import { describe, expect, it } from "vitest";
import type { HistoryEntry } from "~/types/history";
import {
  LIVE_STATUSES,
  SIDEBAR_NOTICE,
  countLiveResearch,
  entryTime,
  formatHistoryTime,
  groupLoadError,
  groupSidebarHistory,
  hasActiveResearch,
  isLiveResearch,
} from "~/utils/sidebarGroups";
import { ID1, ID2, ID3, bookEntry, paperEntry, researchEntry } from "./helpers/fakeHistory";

const T = (hour: number) => `2026-09-26T${String(hour).padStart(2, "0")}:00:00.000Z`;
const status = (s: string) => ({ research: { status: s, stage: "" } });
const ids = (list: Array<{ id: string }>) => list.map((e) => e.id);

describe("groupSidebarHistory", () => {
  it("빈 입력은 두 묶음 모두 비어 있다", () => {
    expect(groupSidebarHistory([])).toEqual({ research: [], researchTotal: 0, recent: [] });
  });

  it("딥리서치는 research 로, 도서·논문은 한 목록(recent)으로 섞여 최신순으로 간다", () => {
    const book = bookEntry(ID1, { createdAt: T(1) });
    const paper = paperEntry(ID2, { createdAt: T(3) });
    const research = researchEntry(ID3, { createdAt: T(2) });
    const { research: r, recent } = groupSidebarHistory([book, paper, research]);
    expect(ids(r)).toEqual([ID3]);
    expect(recent.map((x) => x.entry.id)).toEqual([ID2, ID1]);
  });

  it("recent 항목에는 종류 라벨이 붙는다 — 도서는 소장자료, 논문은 논문", () => {
    const { recent } = groupSidebarHistory([bookEntry(ID1, { createdAt: T(1) }), paperEntry(ID2, { createdAt: T(2) })]);
    expect(recent.map((x) => [x.entry.kind, x.label])).toEqual([
      ["paper", "논문"],
      ["book", "소장자료"],
    ]);
  });

  it("시각은 updatedAt 이 있으면 그것을, 없으면 createdAt 을 본다", () => {
    const old = bookEntry(ID1, { createdAt: T(1), updatedAt: T(9) });
    const fresh = paperEntry(ID2, { createdAt: T(5) });
    expect(groupSidebarHistory([fresh, old]).recent.map((x) => x.entry.id)).toEqual([ID1, ID2]);
  });

  it("진행 중·대기 중인 딥리서치가 더 오래돼도 먼저 오고, 같은 부류 안에서는 최신순이다", () => {
    const doneNew = researchEntry(ID1, { createdAt: T(9), ...status("completed") });
    const runningOld = researchEntry(ID2, { createdAt: T(1), ...status("running") });
    const waitingMid = researchEntry(ID3, { createdAt: T(4), ...status("awaiting_approval") });
    const failedMid = researchEntry("44444444-4444-4444-8444-444444444444", { createdAt: T(6), ...status("failed") });
    const { research } = groupSidebarHistory([doneNew, runningOld, failedMid, waitingMid]);
    // 승인 대기(T4) → 진행 중(T1) → 그 밖에 최신순: 완료(T9) → 실패(T6)
    expect(ids(research)).toEqual([ID3, ID2, ID1, failedMid.id]);
  });

  it("시각이 같으면 원래 순서를 지킨다", () => {
    const a = bookEntry(ID1, { createdAt: T(2) });
    const b = paperEntry(ID2, { createdAt: T(2) });
    const c = bookEntry(ID3, { createdAt: T(2) });
    expect(groupSidebarHistory([a, b, c]).recent.map((x) => x.entry.id)).toEqual([ID1, ID2, ID3]);
    expect(groupSidebarHistory([c, b, a]).recent.map((x) => x.entry.id)).toEqual([ID3, ID2, ID1]);
    const r1 = researchEntry(ID1, { createdAt: T(2), ...status("running") });
    const r2 = researchEntry(ID2, { createdAt: T(2), ...status("running") });
    expect(ids(groupSidebarHistory([r1, r2]).research)).toEqual([ID1, ID2]);
    expect(ids(groupSidebarHistory([r2, r1]).research)).toEqual([ID2, ID1]);
  });

  it("researchLimit 을 주면 research 를 앞에서 그만큼만 돌려주고 researchTotal 은 자르기 전 수다", () => {
    const rows = [1, 2, 3, 4, 5, 6, 7].map((h) =>
      researchEntry(`${h}${h}${h}${h}${h}${h}${h}${h}-0000-4000-8000-000000000000`, {
        createdAt: T(h),
        ...status("completed"),
      }),
    );
    const { research, researchTotal } = groupSidebarHistory(rows, { researchLimit: 5 });
    expect(researchTotal).toBe(7);
    expect(research).toHaveLength(5);
    expect(research.map((e) => e.createdAt)).toEqual([T(7), T(6), T(5), T(4), T(3)]);
  });

  it("자를 때도 진행 중인 것이 오래돼도 먼저 남는다", () => {
    const old = researchEntry(ID1, { createdAt: T(1), ...status("running") });
    const fresh = [2, 3, 4].map((h) => researchEntry(`${h}${h}${h}${h}${h}${h}${h}${h}-0000-4000-8000-000000000000`, { createdAt: T(h), ...status("completed") }));
    const { research } = groupSidebarHistory([...fresh, old], { researchLimit: 2 });
    expect(ids(research)).toEqual([ID1, fresh[2]!.id]);
  });

  it("researchLimit 이 총수 이상이거나 없으면 자르지 않고, 0 이면 비운다", () => {
    const rows = [researchEntry(ID1, { createdAt: T(1) }), researchEntry(ID2, { createdAt: T(2) })];
    expect(groupSidebarHistory(rows, { researchLimit: 5 }).research).toHaveLength(2);
    expect(groupSidebarHistory(rows, { researchLimit: 2 }).research).toHaveLength(2);
    expect(groupSidebarHistory(rows).research).toHaveLength(2);
    const none = groupSidebarHistory(rows, { researchLimit: 0 });
    expect(none.research).toEqual([]);
    expect(none.researchTotal).toBe(2);
  });

  it("researchLimit 은 recent 를 자르지 않는다", () => {
    const rows = [bookEntry(ID1, { createdAt: T(1) }), paperEntry(ID2, { createdAt: T(2) })];
    expect(groupSidebarHistory(rows, { researchLimit: 0 }).recent).toHaveLength(2);
  });

  it("updatedAt 이 빈 문자열이면 createdAt 으로 정렬한다", () => {
    const blank = bookEntry(ID1, { createdAt: T(9), updatedAt: "" });
    const mid = paperEntry(ID2, { createdAt: T(5) });
    expect(groupSidebarHistory([mid, blank]).recent.map((x) => x.entry.id)).toEqual([ID1, ID2]);
  });

  it("모르는 종류는 어느 묶음에도 넣지 않는다", () => {
    const alien = { id: ID3, kind: "video", title: "?", createdAt: T(9), params: {} } as unknown as HistoryEntry;
    const { research, recent } = groupSidebarHistory([alien, bookEntry(ID1)]);
    expect(research).toEqual([]);
    expect(ids(recent.map((x) => x.entry))).toEqual([ID1]);
  });

  it("읽을 수 없는 시각은 가장 오래된 것으로 친다", () => {
    const bad = bookEntry(ID1, { createdAt: "" });
    const ok = paperEntry(ID2, { createdAt: T(1) });
    expect(groupSidebarHistory([bad, ok]).recent.map((x) => x.entry.id)).toEqual([ID2, ID1]);
  });

  it("입력 배열을 바꾸지 않는다", () => {
    const input = [bookEntry(ID1, { createdAt: T(1) }), bookEntry(ID2, { createdAt: T(2) })];
    const copy = input.slice();
    groupSidebarHistory(input);
    expect(input).toEqual(copy);
  });
});

describe("진행 중 판정", () => {
  it("LIVE_STATUSES 는 폴링 대상이라 승인 대기를 뺀다", () => {
    expect(LIVE_STATUSES.has("running")).toBe(true);
    expect(LIVE_STATUSES.has("awaiting_approval")).toBe(false);
    expect(LIVE_STATUSES.has("completed")).toBe(false);
  });

  it("isLiveResearch: 딥리서치만, 상태가 진행 중일 때만 참이다", () => {
    expect(isLiveResearch(researchEntry(ID1, status("queued")))).toBe(true);
    expect(isLiveResearch(researchEntry(ID1, status("completed")))).toBe(false);
    expect(isLiveResearch(researchEntry(ID1))).toBe(false);
    expect(isLiveResearch(bookEntry(ID1))).toBe(false);
  });

  it("countLiveResearch 는 진행 중인 딥리서치 수를 센다", () => {
    const list: HistoryEntry[] = [
      researchEntry(ID1, status("running")),
      researchEntry(ID2, status("planning")),
      researchEntry(ID3, status("completed")),
      bookEntry("55555555-5555-4555-8555-555555555555"),
    ];
    expect(countLiveResearch(list)).toBe(2);
  });
});

describe("hasActiveResearch — 접힌 사이드바 현미경 점", () => {
  it("진행 중이면 참이다", () => {
    expect(hasActiveResearch([researchEntry(ID1, status("running"))])).toBe(true);
  });

  it("승인 대기도 참이다 — 사용자가 움직여야 하는 상태라 눈에 띄어야 한다", () => {
    expect(hasActiveResearch([researchEntry(ID1, status("awaiting_approval"))])).toBe(true);
  });

  it("끝났거나(완료·실패·취소) 상태를 모르거나 딥리서치가 아니면 거짓이다", () => {
    expect(
      hasActiveResearch([
        researchEntry(ID1, status("completed")),
        researchEntry(ID2, status("failed")),
        researchEntry(ID3, status("canceled")),
        researchEntry("66666666-6666-4666-8666-666666666666"),
        bookEntry("55555555-5555-4555-8555-555555555555"),
      ]),
    ).toBe(false);
    expect(hasActiveResearch([])).toBe(false);
  });
});

describe("entryTime", () => {
  it("updatedAt 을 먼저, 비었거나 없으면 createdAt 을 쓴다", () => {
    expect(entryTime(bookEntry(ID1, { createdAt: T(1), updatedAt: T(2) }))).toBe(T(2));
    expect(entryTime(bookEntry(ID1, { createdAt: T(1), updatedAt: "" }))).toBe(T(1));
    expect(entryTime(bookEntry(ID1, { createdAt: T(1) }))).toBe(T(1));
  });
});

describe("formatHistoryTime", () => {
  const NOW = Date.parse("2026-09-26T12:00:00.000Z");
  const ago = (sec: number) => new Date(NOW - sec * 1000).toISOString();

  it("1분 미만은 방금, 1시간 미만은 N분 전, 하루 미만은 N시간 전", () => {
    expect(formatHistoryTime(ago(30), NOW)).toBe("방금");
    expect(formatHistoryTime(ago(5 * 60), NOW)).toBe("5분 전");
    expect(formatHistoryTime(ago(3 * 3600), NOW)).toBe("3시간 전");
  });

  it("하루 이상은 월/일 날짜다", () => {
    expect(formatHistoryTime(ago(3 * 86400), NOW)).toMatch(/\d+\.\s*\d+\./);
  });

  it("빈 문자열·읽을 수 없는 시각은 빈 문자열이다 — Invalid Date 를 내보내지 않는다", () => {
    expect(formatHistoryTime("", NOW)).toBe("");
    expect(formatHistoryTime("not-a-date", NOW)).toBe("");
  });

  it("미래 시각(시계 어긋남)은 방금으로 본다", () => {
    expect(formatHistoryTime(ago(-120), NOW)).toBe("방금");
  });
});

describe("groupLoadError — 묶음의 목록 실패 안내", () => {
  it("묶음의 종류 중 못 읽은 것이 없으면 null — 다른 묶음의 실패는 상관없다", () => {
    expect(groupLoadError("research", [], 0)).toBeNull();
    expect(groupLoadError("research", ["book", "paper"], 0)).toBeNull();
    expect(groupLoadError("recent", ["research"], 0)).toBeNull();
  });

  it("보이는 줄이 없으면 '불러오지 못했어요', 있으면 '다 불러오지 못했어요'", () => {
    expect(groupLoadError("research", ["research"], 0)).toBe(SIDEBAR_NOTICE.loadFailed);
    expect(groupLoadError("research", ["research"], 3)).toBe(SIDEBAR_NOTICE.loadPartial);
    // 최근 검색은 소장자료·논문 중 하나만 못 읽어도 그 묶음의 실패다
    expect(groupLoadError("recent", ["book"], 0)).toBe(SIDEBAR_NOTICE.loadFailed);
    expect(groupLoadError("recent", ["paper"], 2)).toBe(SIDEBAR_NOTICE.loadPartial);
  });
});

describe("SIDEBAR_NOTICE — 사이드바 줄 안내 문구", () => {
  it.each(Object.entries(SIDEBAR_NOTICE))("%s: 해요체, 한 줄 안에 두 문장을 잇지 않고 줄마다 마침표로 끝난다", (_name, text) => {
    expect(text).not.toMatch(/[.?!] \S/);
    for (const line of text.split("\n")) expect(line).toMatch(/요\.$/);
  });

  it("옛 문구('잠시 뒤 다시 열어 주세요')는 [다시 시도] 버튼과 맞게 바꿨다", () => {
    expect(SIDEBAR_NOTICE.loadFailed).toBe("기록을 불러오지 못했어요.\n잠시 뒤 다시 시도해 주세요.");
    expect(Object.values(SIDEBAR_NOTICE).join()).not.toContain("열어 주세요");
  });
});