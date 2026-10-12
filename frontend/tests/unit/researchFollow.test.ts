// frontend/tests/unit/researchFollow.test.ts
import { describe, expect, it } from "vitest";
import type { StepStatus, SubqView } from "~/types/research";
import type { PlanSlot } from "~/utils/planSlots";
import type { SynthEta } from "~/utils/researchDraft";
import {
  FOLLOW_KEYS,
  FOLLOW_PILL_EXPLORE,
  FOLLOW_PILL_WRITE,
  breaksFollow,
  followBehavior,
  followBlocked,
  followPill,
  followTarget,
  sectionElementId,
  shouldFollowMove,
  type FollowInput,
} from "~/utils/researchFollow";

type KeyInput = Extract<FollowInput, { type: "keydown" }>;

function key(k: string, over: Partial<KeyInput> = {}): KeyInput {
  return { type: "keydown", key: k, editable: false, ctrlKey: false, metaKey: false, altKey: false, ...over };
}

function eta(over: Partial<SynthEta> = {}): SynthEta {
  return { done: 0, total: 0, runningIdx: null, runningElapsedMs: null, remainingMs: null, ...over };
}

function subq(idx: number, status: StepStatus): SubqView {
  return {
    idx, title: `하위질문 ${idx + 1}`, seq: idx + 1, status, rounds: [],
    verdict: null, note: "", adopted: null, parseFailed: false, error: null,
  };
}

function slot(subqIdx: number, over: Partial<PlanSlot> = {}): PlanSlot {
  return { subqIdx, title: `하위질문 ${subqIdx + 1}`, state: "collected", adopted: 3, round: null, sectionIdx: null, ...over };
}

function target(over: Partial<Parameters<typeof followTarget>[0]> = {}): string | null {
  return followTarget({ phase: "synthesizing", eta: eta(), hasDraft: false, slots: [], subqs: [], ...over });
}

describe("breaksFollow", () => {
  it("세로 휠은 멈추고 가로 휠·Ctrl+휠(확대)은 멈추지 않는다", () => {
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 120, ctrlKey: false })).toBe(true);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: -40, ctrlKey: false })).toBe(true);
    expect(breaksFollow({ type: "wheel", deltaX: 80, deltaY: 10, ctrlKey: false })).toBe(false);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 0, ctrlKey: false })).toBe(false);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 120, ctrlKey: true })).toBe(false);
  });

  it("터치로 끌면 멈춘다", () => {
    expect(breaksFollow({ type: "touchmove" })).toBe(true);
  });

  it("스크롤 키는 멈추되 입력칸 안의 키·수식 키를 함께 누른 키는 멈추지 않는다", () => {
    expect(FOLLOW_KEYS).toEqual(["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "]);
    for (const k of FOLLOW_KEYS) expect(breaksFollow(key(k))).toBe(true);
    expect(breaksFollow(key("Tab"))).toBe(false);
    expect(breaksFollow(key("a"))).toBe(false);
    expect(breaksFollow(key(" ", { editable: true }))).toBe(false);
    expect(breaksFollow(key("ArrowDown", { editable: true }))).toBe(false);
    expect(breaksFollow(key("ArrowLeft", { altKey: true }))).toBe(false);
    expect(breaksFollow(key("End", { ctrlKey: true }))).toBe(false);
    expect(breaksFollow(key("ArrowDown", { metaKey: true }))).toBe(false);
  });

  it("페이지 스크롤바를 누르면 멈추고 본문을 누르면 멈추지 않는다", () => {
    expect(breaksFollow({ type: "pointerdown", clientX: 1425, viewportWidth: 1425 })).toBe(true);
    expect(breaksFollow({ type: "pointerdown", clientX: 1432, viewportWidth: 1425 })).toBe(true);
    expect(breaksFollow({ type: "pointerdown", clientX: 700, viewportWidth: 1425 })).toBe(false);
    expect(breaksFollow({ type: "pointerdown", clientX: 1424, viewportWidth: 1425 })).toBe(false);
  });
});

describe("followTarget", () => {
  it("작성 중 초안이 있으면 쓰는 절(rs-sec-i)로 간다", () => {
    expect(sectionElementId(4)).toBe("rs-sec-4");
    expect(target({ eta: eta({ done: 2, total: 5, runningIdx: 2 }), hasDraft: true })).toBe("rs-sec-2");
  });

  it("작성 중 첫 절 전에는 쓰는 절의 하위질문 자리(rs-slot-k)로 간다", () => {
    // 하위질문 1 은 근거가 없어 절이 되지 않았다 — 절 0 은 하위질문 1, 절 1 은 하위질문 3 이다
    const slots = [
      slot(0, { state: "writing", sectionIdx: 0 }),
      slot(1, { state: "empty", adopted: 0 }),
      slot(2, { sectionIdx: 1 }),
    ];
    expect(target({ eta: eta({ total: 2, runningIdx: 0 }), slots })).toBe("rs-slot-0");
    expect(target({ eta: eta({ total: 2, runningIdx: 1 }), slots })).toBe("rs-slot-2");
    // 절 번호와 자리의 대응을 아직 모르면(절 제목이 오기 전) 옮기지 않는다
    expect(target({ eta: eta({ total: 2, runningIdx: 0 }), slots: [slot(0), slot(1)] })).toBeNull();
  });

  it("탐색 중에는 도는 하위질문의 자리로 간다", () => {
    expect(target({ phase: "exploring", subqs: [subq(0, "done"), subq(1, "running"), subq(2, "pending")] })).toBe("rs-slot-1");
  });

  it("도는 것이 없거나 계획·대기·끝난 단계면 null", () => {
    expect(target({ phase: "exploring", subqs: [subq(0, "done"), subq(1, "pending")] })).toBeNull();
    // 절 사이(앞 절이 끝나고 다음 절이 아직 시작되지 않음)
    expect(target({ eta: eta({ done: 1, total: 3 }), hasDraft: true })).toBeNull();
    for (const phase of ["planning", "awaiting", "queued", "completed", "failed", "canceled"] as const) {
      expect(target({ phase, eta: eta({ total: 3, runningIdx: 1 }), hasDraft: true, subqs: [subq(0, "running")] })).toBeNull();
    }
    expect(target({ phase: null })).toBeNull();
  });
});

describe("shouldFollowMove", () => {
  it("따라가는 중이고 막히지 않았고 대상이 바뀌었을 때만 옮긴다", () => {
    const s = { following: true, blocked: false, target: "rs-sec-2", last: "rs-sec-1" };
    expect(shouldFollowMove(s)).toBe(true);
    expect(shouldFollowMove({ ...s, last: null })).toBe(true);
    expect(shouldFollowMove({ ...s, following: false })).toBe(false);
    expect(shouldFollowMove({ ...s, blocked: true })).toBe(false);
    expect(shouldFollowMove({ ...s, target: null })).toBe(false);
    expect(shouldFollowMove({ ...s, last: "rs-sec-2" })).toBe(false);
  });
});

describe("followBlocked", () => {
  it("위치 복원 중·원문 뷰어·열린 인용 팝오버면 막는다", () => {
    const none = { restoring: false, pdfOpen: false, popoverOpen: false };
    expect(followBlocked(none)).toBe(false);
    expect(followBlocked({ ...none, restoring: true })).toBe(true);
    expect(followBlocked({ ...none, pdfOpen: true })).toBe(true);
    expect(followBlocked({ ...none, popoverOpen: true })).toBe(true);
  });
});

describe("followPill", () => {
  it("따라가기를 멈췄고 갈 곳이 있을 때만 띄운다 — 작성 중 '↓ 지금 쓰는 곳으로', 탐색 중 '↓ 지금 찾는 곳으로'", () => {
    expect(FOLLOW_PILL_WRITE).toBe("↓ 지금 쓰는 곳으로");
    expect(FOLLOW_PILL_EXPLORE).toBe("↓ 지금 찾는 곳으로");
    expect(followPill({ phase: "synthesizing", following: false, target: "rs-sec-2" })).toBe(FOLLOW_PILL_WRITE);
    expect(followPill({ phase: "exploring", following: false, target: "rs-slot-1" })).toBe(FOLLOW_PILL_EXPLORE);
    expect(followPill({ phase: "synthesizing", following: true, target: "rs-sec-2" })).toBeNull();
    expect(followPill({ phase: "synthesizing", following: false, target: null })).toBeNull();
    expect(followPill({ phase: "completed", following: false, target: "rs-sec-2" })).toBeNull();
  });
});

describe("followBehavior", () => {
  it("움직임 줄이기면 즉시(auto), 아니면 부드럽게(smooth)", () => {
    expect(followBehavior(true)).toBe("auto");
    expect(followBehavior(false)).toBe("smooth");
  });
});
