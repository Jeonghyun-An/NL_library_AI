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
  followKeyDirection,
  followPill,
  followTarget,
  inFollowPhase,
  scrollsInner,
  sectionElementId,
  shouldFollowMove,
  type FollowInput,
  type FollowScroller,
} from "~/utils/researchFollow";

type KeyInput = Extract<FollowInput, { type: "keydown" }>;

function key(k: string, over: Partial<KeyInput> = {}): KeyInput {
  return { type: "keydown", key: k, editable: false, ctrlKey: false, metaKey: false, altKey: false, inner: false, ...over };
}

// 입력 대상에서 위로 올라가며 본 조상 한 칸의 세로 스크롤 모양 — overflow 를 주지 않으면 굴러가지 않는 칸(visible)
function box(over: Partial<FollowScroller> = {}): FollowScroller {
  return { overflowY: "visible", scrollTop: 0, scrollHeight: 100, clientHeight: 100, ...over };
}

// 넓은 화면(A)의 옆 칸(sticky·overflow-y auto) — 회차 타임라인이 길어 넘친다. 가운데·맨 위·맨 끝까지 굴린 모양
const sideMid = box({ overflowY: "auto", scrollTop: 200, scrollHeight: 1400, clientHeight: 700 });
const sideTop = { ...sideMid, scrollTop: 0 };
const sideEnd = { ...sideMid, scrollTop: 700 };
// 옆 칸 안의 근거 장부 목록(max-height 14rem·overflow-y auto)
const ledgerMid = box({ overflowY: "auto", scrollTop: 100, scrollHeight: 600, clientHeight: 224 });
const ledgerEnd = { ...ledgerMid, scrollTop: 376 };
// 인용 팝오버의 인용문(max-height 8rem·overflow-y auto)
const quoteMid = box({ overflowY: "auto", scrollTop: 40, scrollHeight: 300, clientHeight: 128 });
const quoteEnd = { ...quoteMid, scrollTop: 172 };
// 본문 칸·절·팝오버 — 제 칸이 굴러가지 않아 휠은 페이지(창)가 받는다
const page = [box(), box(), box()];

// D7 이 창의 휠을 옮기는 모양 — inner 는 대상의 조상 사슬로 잰다
function wheelOver(chain: readonly FollowScroller[], deltaY: number): FollowInput {
  return { type: "wheel", deltaX: 0, deltaY, ctrlKey: false, inner: scrollsInner(chain, Math.sign(deltaY)) };
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
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 120, ctrlKey: false, inner: false })).toBe(true);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: -40, ctrlKey: false, inner: false })).toBe(true);
    expect(breaksFollow({ type: "wheel", deltaX: 80, deltaY: 10, ctrlKey: false, inner: false })).toBe(false);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 0, ctrlKey: false, inner: false })).toBe(false);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 120, ctrlKey: true, inner: false })).toBe(false);
  });

  it("터치로 끌면 멈춘다", () => {
    expect(breaksFollow({ type: "touchmove", inner: false })).toBe(true);
  });

  it("옆 칸·근거 장부 목록·인용문처럼 안쪽 스크롤 칸만 굴리는 휠·터치 이동·스크롤 키는 멈추지 않는다", () => {
    // 넓은 화면은 탐색 중에도 2단(A)이라 옆 칸은 sticky — 제 칸을 굴려 읽어도 본문 따라가기가 그 읽기를 방해하지 않는다
    expect(breaksFollow(wheelOver([box(), box(), sideMid], 120))).toBe(false);
    expect(breaksFollow(wheelOver([box(), box(), sideMid], -120))).toBe(false);
    expect(breaksFollow(wheelOver([box(), ledgerMid, box(), sideMid], 120))).toBe(false);
    // 장부 목록이 끝에 닿아도 옆 칸이 더 내려가면 옆 칸이 받는다 — 페이지는 그대로다
    expect(breaksFollow(wheelOver([box(), ledgerEnd, box(), sideMid], 120))).toBe(false);
    // 인용 팝오버는 aria-modal 이 없어 모달로 걸러지지 않는다 — 긴 인용문을 휠로 읽어도 따라가기는 켜진 채 막힘으로만 지나간다
    expect(breaksFollow(wheelOver([quoteMid, ...page], 120))).toBe(false);
    expect(breaksFollow({ type: "touchmove", inner: true })).toBe(false);
    expect(breaksFollow(key("ArrowDown", { inner: true }))).toBe(false);
    expect(breaksFollow(key("End", { ctrlKey: true, inner: true }))).toBe(false);
  });

  it("칸 끝에 닿아 창으로 넘어가는 휠은 페이지를 굴린다 — 멈춘다", () => {
    expect(breaksFollow(wheelOver([box(), ledgerEnd, box(), sideEnd], 120))).toBe(true);
    expect(breaksFollow(wheelOver([box(), box(), sideTop], -120))).toBe(true);
    expect(breaksFollow(wheelOver([quoteEnd, ...page], 120))).toBe(true);
    // 끝에 닿은 칸도 반대 방향으로는 제 칸이 받는다
    expect(breaksFollow(wheelOver([box(), ledgerEnd, box(), sideEnd], -120))).toBe(false);
    // 본문 위의 휠은 페이지를 굴린다
    expect(breaksFollow(wheelOver(page, 120))).toBe(true);
  });

  it("스크롤 키는 멈추되 입력칸 안의 키는 멈추지 않는다", () => {
    expect(FOLLOW_KEYS).toEqual(["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "]);
    for (const k of FOLLOW_KEYS) expect(breaksFollow(key(k))).toBe(true);
    expect(breaksFollow(key("a"))).toBe(false);
    expect(breaksFollow(key("Enter"))).toBe(false);
    expect(breaksFollow(key(" ", { editable: true }))).toBe(false);
    expect(breaksFollow(key("ArrowDown", { editable: true }))).toBe(false);
  });

  it("수식 키와 함께 눌러도 페이지를 굴리는 조합은 멈춘다 — Ctrl+Home/End·Cmd+↑/↓·Option+↑/↓", () => {
    // Windows·Linux 의 Ctrl+Home/End 는 문서 처음·끝, macOS 의 Cmd+↑/↓ 는 문서 처음·끝, Option+↑/↓ 는 PageUp/PageDown 이다
    for (const k of ["Home", "End"]) expect(breaksFollow(key(k, { ctrlKey: true }))).toBe(true);
    for (const k of ["ArrowUp", "ArrowDown"]) {
      expect(breaksFollow(key(k, { metaKey: true }))).toBe(true);
      expect(breaksFollow(key(k, { altKey: true }))).toBe(true);
    }
    // 입력칸 안에서는 수식 키 조합도 글자 사이 이동이다
    expect(breaksFollow(key("End", { ctrlKey: true, editable: true }))).toBe(false);
    expect(breaksFollow(key("ArrowDown", { metaKey: true, editable: true }))).toBe(false);
  });

  it("페이지를 굴리지 않는 수식 키 조합은 멈추지 않는다 — 탭 전환·브라우저 홈·입력기 전환·Ctrl+방향키", () => {
    expect(breaksFollow(key("PageDown", { ctrlKey: true }))).toBe(false);
    expect(breaksFollow(key("PageUp", { ctrlKey: true }))).toBe(false);
    expect(breaksFollow(key("Home", { altKey: true }))).toBe(false);
    expect(breaksFollow(key(" ", { ctrlKey: true }))).toBe(false);
    expect(breaksFollow(key(" ", { metaKey: true }))).toBe(false);
    expect(breaksFollow(key("ArrowDown", { ctrlKey: true }))).toBe(false);
    // 수식 키를 둘 이상 함께 누른 조합(Ctrl+Alt+↓·Ctrl+Cmd+End)도 굴리지 않는다
    expect(breaksFollow(key("ArrowDown", { ctrlKey: true, altKey: true }))).toBe(false);
    expect(breaksFollow(key("End", { ctrlKey: true, metaKey: true }))).toBe(false);
  });

  it("Tab·Shift+Tab 으로 초점을 옮기면 멈춘다 — 브라우저가 초점 받은 요소로 창을 굴리고, 따라가면 그 초점이 화면 밖에 남는다", () => {
    // Shift+Tab 도 key 는 "Tab" 이다(Shift 는 FollowInput 에 싣지 않는다)
    expect(breaksFollow(key("Tab"))).toBe(true);
    // 입력칸·인용 팝오버(role=dialog)·메뉴를 떠나는 Tab 도 초점을 페이지의 다른 요소로 옮긴다 — 키를 스스로 쓰는 자리여도 Tab 은 넘긴다
    expect(breaksFollow(key("Tab", { editable: true }))).toBe(true);
    // Ctrl+Tab(탭 전환)·Cmd+Tab·Alt+Tab(앱·창 전환)은 페이지의 초점을 옮기지 않는다
    expect(breaksFollow(key("Tab", { ctrlKey: true }))).toBe(false);
    expect(breaksFollow(key("Tab", { metaKey: true }))).toBe(false);
    expect(breaksFollow(key("Tab", { altKey: true }))).toBe(false);
  });

  it("페이지 스크롤바를 누르면 멈추고 본문을 누르면 멈추지 않는다", () => {
    expect(breaksFollow({ type: "pointerdown", clientX: 1425, viewportWidth: 1425 })).toBe(true);
    expect(breaksFollow({ type: "pointerdown", clientX: 1432, viewportWidth: 1425 })).toBe(true);
    expect(breaksFollow({ type: "pointerdown", clientX: 700, viewportWidth: 1425 })).toBe(false);
    expect(breaksFollow({ type: "pointerdown", clientX: 1424, viewportWidth: 1425 })).toBe(false);
  });
});

describe("scrollsInner", () => {
  it("넘치지 않는 칸·사용자가 굴리지 못하는 칸은 건너뛰고, 방향을 모르면 안쪽으로 보지 않는다", () => {
    // 옆 칸이 짧아 넘치지 않거나, 가로로만 굴러가는 감싸개(세로 overflow 도 auto 로 계산된다)면 휠은 창이 받는다
    expect(scrollsInner([box(), box({ overflowY: "auto", scrollHeight: 500, clientHeight: 500 })], 1)).toBe(false);
    expect(scrollsInner([box({ overflowY: "hidden", scrollHeight: 600, clientHeight: 200 })], 1)).toBe(false);
    expect(scrollsInner([box({ overflowY: "clip", scrollHeight: 600, clientHeight: 200 })], 1)).toBe(false);
    expect(scrollsInner([box({ overflowY: "scroll", scrollHeight: 600, clientHeight: 200 })], 1)).toBe(true);
    expect(scrollsInner([box({ overflowY: "overlay", scrollHeight: 600, clientHeight: 200 })], 1)).toBe(true);
    expect(scrollsInner([box(), box(), sideMid], 0)).toBe(false);
    expect(scrollsInner([], 1)).toBe(false);
  });

  it("끝까지 1px 이 안 남은 칸은 끝으로 본다 — 확대한 화면은 scrollTop 이 소수다", () => {
    expect(scrollsInner([{ ...sideMid, scrollTop: 0.5 }], -1)).toBe(false);
    expect(scrollsInner([{ ...sideMid, scrollTop: 699.4 }], 1)).toBe(false);
    expect(scrollsInner([{ ...sideMid, scrollTop: 698 }], 1)).toBe(true);
    expect(scrollsInner([{ ...sideMid, scrollTop: 1 }], -1)).toBe(true);
  });
});

describe("followKeyDirection", () => {
  it("스크롤 키가 굴리는 방향 — 위 -1·아래 1, Shift+Space 는 위, 그 밖의 키는 0", () => {
    for (const k of ["ArrowUp", "PageUp", "Home"]) expect(followKeyDirection(k, false)).toBe(-1);
    for (const k of ["ArrowDown", "PageDown", "End", " "]) expect(followKeyDirection(k, false)).toBe(1);
    expect(followKeyDirection(" ", true)).toBe(-1);
    // 수식 키는 방향을 바꾸지 않는다 — Shift 는 Space 만
    expect(followKeyDirection("ArrowDown", true)).toBe(1);
    expect(followKeyDirection("Tab", false)).toBe(0);
    expect(followKeyDirection("a", false)).toBe(0);
    for (const k of FOLLOW_KEYS) expect(followKeyDirection(k, false)).not.toBe(0);
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

  it("탐색부터 다시 도는 재시도에서 이전 시도에 running 으로 남은 행은 도는 하위질문이 아니다", () => {
    // 1차 시도의 행은 seq 1~3, 이번 시도는 하위질문 0 을 seq 4 로 다시 열었다(stopPoint·researchProgress 와 같은 규칙)
    const again = (sq: SubqView, seq: number): SubqView => ({ ...sq, seq });
    expect(target({ phase: "exploring", subqs: [again(subq(0, "done"), 4), subq(1, "running"), subq(2, "pending")] })).toBeNull();
    expect(target({ phase: "exploring", subqs: [again(subq(0, "done"), 4), again(subq(1, "running"), 5), subq(2, "done")] }))
      .toBe("rs-slot-1");
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

describe("inFollowPhase", () => {
  it("따라갈 것이 생기는 단계(탐색·작성)에서만 참 — 그 앞(계획·승인 대기·대기열)과 끝난 잡의 입력은 따라가기를 멈추지 않는다", () => {
    // 승인 대기에 계획을 굴려 읽거나 Tab 으로 [승인] 까지 가도 탐색이 시작되면 따라간다(기본 켬)
    for (const phase of ["exploring", "synthesizing"] as const) expect(inFollowPhase(phase)).toBe(true);
    for (const phase of ["planning", "awaiting", "queued", "completed", "failed", "canceled", null] as const) {
      expect(inFollowPhase(phase)).toBe(false);
    }
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
