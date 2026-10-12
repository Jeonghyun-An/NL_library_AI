// frontend/tests/unit/planSlots.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchJob, ResearchView, RoundView, SubqView, SynthSectionView, SynthView } from "~/types/research";
import {
  newlyCollected,
  planSlotLabel,
  planSlots,
  sectionOfSubq,
  showsPlanSlots,
  slotElementId,
  type PlanSlot,
} from "~/utils/planSlots";
import { initialResearchView } from "~/utils/researchEvents";

const TITLES = ["효과 측정", "교사 인식", "정책 과제"];

function job(over: Partial<ResearchJob> = {}): ResearchJob {
  return {
    job_id: "11111111-1111-4111-8111-111111111111",
    question: "AI 윤리 교육의 효과",
    status: "running",
    stage: "planned",
    plan: TITLES,
    report: null,
    last_error: null,
    steps: [],
    ...over,
  };
}

function round(n: number, over: Partial<RoundView> = {}): RoundView {
  return {
    round: n, query: `질의 ${n}`, foundChunks: 10, newPapers: 3, verdict: "insufficient", note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [], ...over,
  };
}

function subq(idx: number, over: Partial<SubqView> = {}): SubqView {
  return {
    idx, title: TITLES[idx] ?? `하위질문 ${idx + 1}`, seq: idx + 1, status: "done", rounds: [round(1)],
    verdict: "sufficient", note: "", adopted: 3, parseFailed: false, error: null, ...over,
  };
}

function sec(idx: number, status: SynthSectionView["status"], over: Partial<SynthSectionView> = {}): SynthSectionView {
  return { idx, status, subqIdx: idx, heading: null, startedAt: null, durationMs: null, section: null, ...over };
}

function synthOf(over: Partial<SynthView> = {}): SynthView {
  return { seq: null, status: null, total: 0, sections: [], headings: [], evidence: {}, retiredSeq: null, ...over };
}

function viewWith(subqs: SubqView[], synth: Partial<SynthView> = {}): ResearchView {
  return { ...initialResearchView(job()), subqs, synth: synthOf(synth) };
}

function slot(subqIdx: number, state: PlanSlot["state"], over: Partial<PlanSlot> = {}): PlanSlot {
  return { subqIdx, title: TITLES[subqIdx] ?? "", state, adopted: 3, round: null, sectionIdx: null, ...over };
}

describe("sectionOfSubq", () => {
  it("synth 이벤트의 subq_idx 를 먼저 쓴다", () => {
    // 절 0 은 하위질문 0, 절 1 은 하위질문 2(하위질문 1 은 근거가 없어 절이 되지 않았다)
    const map = sectionOfSubq(synthOf({ sections: [sec(0, "done", { subqIdx: 0 }), sec(1, "running", { subqIdx: 2 })] }), TITLES);
    expect([...map]).toEqual([[0, 0], [2, 1]]);
    // 절 제목이 다른 하위질문의 글과 같아도 절 이벤트가 실은 하위질문 번호가 이긴다
    const disagree = sectionOfSubq(
      synthOf({ headings: ["효과 측정"], sections: [sec(0, "running", { subqIdx: 1 })] }),
      TITLES,
    );
    expect([...disagree]).toEqual([[1, 0]]);
  });

  it("subq_idx 를 모르면 headings 를 계획 하위질문 글과 공백 정리 뒤 맞춘다", () => {
    // 절 이벤트에 subq_idx 가 없는(옛 콜백) 절과 아직 쓰기 시작하지 않은 절 — 제목 글로만 맞춘다. 조합형(NFD) 글도 같은 글이다
    const map = sectionOfSubq(
      synthOf({
        headings: ["  효과   측정 ", "정책\n과제".normalize("NFD")],
        sections: [sec(0, "running", { subqIdx: null })],
      }),
      TITLES,
    );
    expect([...map]).toEqual([[0, 0], [2, 1]]);
  });

  it("근거 0 하위질문은 절이 되지 않아 하위질문 번호와 절 번호가 어긋난다", () => {
    const map = sectionOfSubq(synthOf({ headings: ["효과 측정", "정책 과제"] }), TITLES);
    expect(map.get(0)).toBe(0);
    expect(map.has(1)).toBe(false);
    expect(map.get(2)).toBe(1);
  });
});

describe("planSlots", () => {
  it("하위질문마다 자리를 만들고 key 는 하위질문 번호다 — 대기·근거 수집 중(회차)·근거 N편", () => {
    const v = viewWith([
      subq(0, { adopted: 4 }),
      subq(1, { status: "running", rounds: [round(1), round(2, { verdict: null })], verdict: "insufficient", adopted: 2 }),
      subq(2, { status: "pending", seq: null, rounds: [], verdict: null, adopted: null }),
    ]);
    expect(planSlots(v)).toEqual([
      { subqIdx: 0, title: "효과 측정", state: "collected", adopted: 4, round: null, sectionIdx: null },
      { subqIdx: 1, title: "교사 인식", state: "collecting", adopted: 2, round: 2, sectionIdx: null },
      { subqIdx: 2, title: "정책 과제", state: "waiting", adopted: null, round: null, sectionIdx: null },
    ]);
    // 하위질문 단계가 막 열려 회차가 아직 없으면 회차를 적지 않는다
    expect(planSlots(viewWith([subq(0, { status: "running", rounds: [], adopted: null })]))[0]!.round).toBeNull();
  });

  it("종합이 시작되면 근거 0 자리는 '근거 없음'으로 접는다", () => {
    const v = viewWith(
      [subq(0, { adopted: 4 }), subq(1, { adopted: 0 }), subq(2, { adopted: 3 })],
      { seq: 9, status: "running", total: 2, headings: ["효과 측정", "정책 과제"], sections: [sec(0, "running", { subqIdx: 0 })] },
    );
    expect(planSlots(v).map((s) => [s.subqIdx, s.state, s.sectionIdx])).toEqual([
      [0, "writing", 0],
      [1, "empty", null],
      [2, "collected", 1],
    ]);
    // 근거 수를 모르는 옛 잡(adopted null)은 대응을 알게 된 뒤에도 절이 없으면 접는다
    const legacy = viewWith(
      [subq(0, { adopted: null }), subq(1, { adopted: null })],
      { seq: 9, status: "running", total: 1, headings: ["효과 측정"], sections: [sec(0, "running", { subqIdx: 0 })] },
    );
    expect(planSlots(legacy).map((s) => s.state)).toEqual(["writing", "empty"]);
  });

  it("종합 단계가 열렸지만 절 제목이 아직 없으면 근거를 모은 자리는 접지 않는다 — 근거 0 자리만 접는다", () => {
    // 워커가 종합 단계를 열고(결과 없는 running 단계 이벤트) 첫 절 이벤트를 보내기 전 — 대응을 아직 모른다
    const v = viewWith(
      [subq(0, { adopted: 4 }), subq(1, { adopted: 0 }), subq(2, { adopted: null })],
      { seq: 9, status: "running", headings: [], sections: [] },
    );
    expect(planSlots(v).map((s) => s.state)).toEqual(["collected", "empty", "collected"]);
  });

  it("종합 중 첫 절 전에는 쓰는 절의 자리를 '작성 중'으로 둔다", () => {
    // 하위질문 0 은 근거가 없어 절 0 이 하위질문 1 이다. 절 이벤트가 subq_idx 를 싣지 않아도 절 제목으로 맞춘다
    const v = viewWith(
      [subq(0, { adopted: 0 }), subq(1, { adopted: 2 }), subq(2, { adopted: 5 })],
      { seq: 9, status: "running", total: 2, headings: ["교사 인식", "정책 과제"], sections: [sec(0, "running", { subqIdx: null })] },
    );
    expect(planSlots(v).map((s) => [s.state, s.sectionIdx])).toEqual([
      ["empty", null],
      ["writing", 0],
      ["collected", 1],
    ]);
  });

  it("실패한 하위질문은 오류, 하위질문이 없으면 빈 목록", () => {
    const v = viewWith([subq(0), subq(1, { status: "failed", adopted: null, error: "시간 상한" })]);
    expect(planSlots(v).map((s) => s.state)).toEqual(["collected", "failed"]);
    expect(planSlots(viewWith([]))).toEqual([]);
  });

  it("탐색부터 다시 도는 재시도에서 이번 시도가 아직 닿지 않은 자리는 이전 시도의 행이 남아도 대기다", () => {
    // 재시도는 idx 0 부터 새 seq 로 행을 쌓는다 — 1차 시도(seq 1~3)는 [근거 4편·근거 2편·실패]로 끝났고, 이번 시도는
    // 하위질문 0 을 seq 4 로 다시 열었다. 하위질문 1·2 에 남은 1차 시도의 행을 이번 시도의 것으로 읽지 않는다
    // (stopPoint·researchProgress 와 같은 규칙 — 진행 막대가 대기로 보는 자리를 절 자리도 대기로 본다)
    const first = [subq(1, { adopted: 2 }), subq(2, { status: "failed", adopted: null, error: "시간 상한" })];
    const opened = viewWith([
      subq(0, { seq: 4, status: "running", rounds: [round(1, { verdict: null })], verdict: null, adopted: null }),
      ...first,
    ]);
    const slots = planSlots(opened);
    expect(slots.map((s) => [s.state, s.adopted, s.round])).toEqual([
      ["collecting", null, 1],
      ["waiting", null, null],
      ["waiting", null, null],
    ]);
    expect(slots.map(planSlotLabel)).toEqual(["근거 수집 중 · 1회차", "대기", "대기"]);
    // 이번 시도가 연 행은 그대로 읽는다 — 하위질문 0 을 마치고 1 을 seq 5 로 열었다
    const next = viewWith([
      subq(0, { seq: 4, adopted: 5 }),
      subq(1, { seq: 5, status: "running", rounds: [round(1, { verdict: null })], verdict: null, adopted: null }),
      first[1]!,
    ]);
    expect(planSlots(next).map((s) => [s.state, s.adopted])).toEqual([
      ["collected", 5],
      ["collecting", null],
      ["waiting", null],
    ]);
  });

  it("받은 화면 상태(view)를 고치지 않는다", () => {
    const v = viewWith(
      [subq(0), subq(1, { status: "running", rounds: [round(1)] }), subq(2, { adopted: 0 })],
      { seq: 9, status: "running", headings: ["효과 측정"], sections: [sec(0, "running")] },
    );
    const before = JSON.stringify(v);
    planSlots(v);
    expect(JSON.stringify(v)).toBe(before);
  });
});

describe("planSlotLabel", () => {
  it("상태마다 짧은 글 — 대기·근거 수집 중 · n회차·근거 N편 ✓·이 절을 쓰는 중·근거 없음·오류", () => {
    expect(planSlotLabel(slot(0, "waiting", { adopted: null }))).toBe("대기");
    expect(planSlotLabel(slot(0, "collecting", { round: 2 }))).toBe("근거 수집 중 · 2회차");
    expect(planSlotLabel(slot(0, "collecting", { round: null }))).toBe("근거 수집 중");
    expect(planSlotLabel(slot(0, "collected", { adopted: 4 }))).toBe("근거 4편 ✓");
    expect(planSlotLabel(slot(0, "collected", { adopted: null }))).toBe("근거 수집 완료");
    // 근거 0편으로 끝난 자리(종합 시작 전)는 성공 표시(✓)를 달지 않는다
    expect(planSlotLabel(slot(0, "collected", { adopted: 0 }))).toBe("근거 0편");
    expect(planSlotLabel(slot(0, "writing", { sectionIdx: 0 }))).toBe("이 절을 쓰는 중");
    expect(planSlotLabel(slot(0, "empty", { adopted: 0 }))).toBe("근거 없음");
    expect(planSlotLabel(slot(0, "failed", { adopted: null }))).toBe("오류");
  });
});

describe("newlyCollected", () => {
  it("직전 상태와 견줘 이번에 근거 수집을 마친 자리만 — 처음 그릴 때는 없다", () => {
    const slots = [slot(0, "collected"), slot(1, "collected"), slot(2, "collecting", { round: 1 })];
    expect(newlyCollected(null, slots)).toEqual([]);
    const prev = new Map<number, PlanSlot["state"]>([[0, "collecting"], [1, "collected"], [2, "waiting"]]);
    expect(newlyCollected(prev, slots)).toEqual([0]);
    expect(newlyCollected(new Map([[0, "collected"], [1, "collected"], [2, "collecting"]]), slots)).toEqual([]);
    // 근거 0편으로 끝난 자리는 튀어 오르지 않는다
    expect(newlyCollected(new Map([[0, "collecting"]]), [slot(0, "collected", { adopted: 0 })])).toEqual([]);
  });
});

describe("showsPlanSlots", () => {
  it("대기열·탐색 중·종합 첫 절 전에만 그린다", () => {
    expect(showsPlanSlots("queued", false)).toBe(true);
    expect(showsPlanSlots("exploring", false)).toBe(true);
    expect(showsPlanSlots("synthesizing", false)).toBe(true);
    expect(showsPlanSlots("synthesizing", true)).toBe(false);
    for (const p of ["planning", "awaiting", "completed", "failed", "canceled"] as const) {
      expect(showsPlanSlots(p, false)).toBe(false);
    }
    expect(showsPlanSlots(null, false)).toBe(false);
  });
});

describe("slotElementId", () => {
  it("자리 id 는 rs-slot-{하위질문 번호}", () => {
    expect(slotElementId(0)).toBe("rs-slot-0");
    expect(slotElementId(5)).toBe("rs-slot-5");
  });
});
