// frontend/tests/unit/researchEvents.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchEvent, ResearchJob, ResearchReport, ResearchStepRow } from "~/types/research";
import {
  applyApproval,
  applyResearchEvent,
  initialResearchView,
  isTerminalEvent,
  refreshView,
  researchPhase,
  stopPoint,
  subqStatusLabel,
  synthProgress,
  withPlan,
} from "~/utils/researchEvents";

function job(over: Partial<ResearchJob> = {}): ResearchJob {
  return {
    job_id: "11111111-1111-4111-8111-111111111111",
    question: "AI 윤리 교육의 효과",
    status: "running",
    stage: "planned",
    plan: ["효과 측정", "교사 인식"],
    report: null,
    last_error: null,
    steps: [],
    params: { max_subquestions: 6 },
    created_at: "2026-09-26T01:00:00Z",
    started_at: "2026-09-26T01:01:00Z",
    finished_at: null,
    ...over,
  };
}

function step(over: Partial<ResearchStepRow>): ResearchStepRow {
  return { seq: 0, kind: "plan", subq_idx: null, title: "연구 계획 수립", detail: null, status: "done", result: {}, ...over };
}

function run(events: ResearchEvent[], start = initialResearchView(job())) {
  return events.reduce((view, event) => applyResearchEvent(view, event), start);
}

function oldReport(over: Partial<ResearchReport> = {}): ResearchReport {
  return {
    question: "AI 윤리 교육의 효과",
    range: { from: "2002", to: "2026", n_papers: 100 },
    sections: [],
    evidence: {
      E1: { cnts_id: "C1", meta: { title: "t" }, chunks: [] },
    },
    trail: [{
      subquestion: "효과 측정", queries: ["효과 측정", "초등 효과"], evidence_count: 4,
      verdict: "sufficient", note: "충분하다", parse_failed: false, failed: false, capped: 0,
    }],
    limitations: [],
    ...over,
  };
}

const SEARCH_STARTED: ResearchEvent = {
  kind: "step", seq: 1, step_kind: "search", subq_idx: 0, title: "효과 측정", status: "running",
};

// 1회차 점검까지 끝나 저장됐고, 2회차 검색 직후 counters 를 받은 채 점검(LLM)을 기다리는 장면.
// 워커는 자기점검이 끝나야 단계 result 에 저장하므로 이 동안 저장본은 라이브보다 한 회차 뒤처진다.
const ROUND1 = {
  round: 1, query: "효과 측정", found_chunks: 12, new_papers: 5,
  verdict: "insufficient" as const, note: "초등 대상 연구가 없다", next_query: "초등 AI 윤리 교육 효과",
};
const ROUND2 = {
  round: 2, query: "초등 AI 윤리 교육 효과", found_chunks: 9, new_papers: 6,
  verdict: "sufficient" as const, note: "충분", next_query: null,
};
const SAVED = { papers_reviewed: 20, evidence_adopted: 5, rechecks: 0 };
const LIVE = { papers_reviewed: 26, evidence_adopted: 7, rechecks: 1 };
const AWAITING_ROUND2_CRITIQUE: ResearchEvent[] = [
  SEARCH_STARTED,
  { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
  { kind: "counters", ...SAVED },
  {
    kind: "critique", subq_idx: 0, verdict: "insufficient", note: "초등 대상 연구가 없다", adopted: 5,
    parse_failed: false, capped: 0, round: 1, next_query: "초등 AI 윤리 교육 효과", will_recheck: true,
  },
  { ...SEARCH_STARTED, result: { rounds: [ROUND1], counters: SAVED } },
  { kind: "search", subq_idx: 0, query: "초등 AI 윤리 교육 효과", found: 9, round: 2, new_papers: 6 },
  { kind: "counters", ...LIVE },
];
const PLAN_ROW = step({ seq: 0, result: { subquestions: ["효과 측정", "교사 인식"] } });
const SAVED_SEARCH_ROW = step({
  seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "running", result: { rounds: [ROUND1], counters: SAVED },
});
const LIVE_VIEW = { papersReviewed: 26, evidenceAdopted: 7, rechecks: 1 };

describe("initialResearchView", () => {
  it("승인 대기 잡은 계획을 대기 중인 하위질문으로 펼친다", () => {
    const v = initialResearchView(job({ status: "awaiting_approval", steps: [step({ result: { subquestions: ["효과 측정", "교사 인식"] } })] }));
    expect(researchPhase(v)).toBe("awaiting");
    expect(v.subqs.map((s) => [s.idx, s.title, s.status])).toEqual([[0, "효과 측정", "pending"], [1, "교사 인식", "pending"]]);
  });

  it("잡의 plan 이 비어 있으면 계획 단계 결과에서 읽는다", () => {
    const v = initialResearchView(job({ status: "awaiting_approval", plan: null, steps: [step({ result: { subquestions: ["가", "나"] } })] }));
    expect(v.plan).toEqual(["가", "나"]);
  });

  it("보고서 stats 가 있으면 카운터로 쓴다", () => {
    const v = initialResearchView(job({
      status: "completed", stage: "synthesized",
      report: oldReport({ stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 } }),
    }));
    expect(v.counters).toEqual({ papersReviewed: 38, evidenceAdopted: 11, rechecks: 2 });
  });

  it("보고서가 없는 실패 잡은 seq 가 가장 큰 단계 result 의 카운터를 쓴다", () => {
    const v = initialResearchView(job({
      status: "failed", stage: "explored", last_error: "종합 실패",
      steps: [
        step({ seq: 0, result: { subquestions: ["효과 측정", "교사 인식"] } }),
        step({ seq: 2, kind: "search", subq_idx: 1, title: "교사 인식", result: { rounds: [], counters: { papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 } } }),
        step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", result: { rounds: [], counters: { papers_reviewed: 12, evidence_adopted: 4, rechecks: 0 } } }),
        step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "failed", result: { sections_total: 2, sections: [], error: "종합 실패" } }),
      ],
    }));
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 7, rechecks: 1 });
  });

  it("보고서 stats 가 단계 result 의 카운터보다 앞선다", () => {
    const v = initialResearchView(job({
      status: "completed", stage: "synthesized",
      report: oldReport({ stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 } }),
      steps: [step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", result: { rounds: [], counters: { papers_reviewed: 30, evidence_adopted: 9, rechecks: 1 } } })],
    }));
    expect(v.counters).toEqual({ papersReviewed: 38, evidenceAdopted: 11, rechecks: 2 });
  });
});

describe("applyResearchEvent — 탐색", () => {
  it("검색·점검 이벤트로 회차를 쌓고 재검색 장면을 강조한다", () => {
    const v = run([
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      {
        kind: "critique", subq_idx: 0, verdict: "insufficient", note: "초등 대상 연구가 없다", adopted: 3,
        parse_failed: false, capped: 0, round: 1, next_query: "초등 AI 윤리 교육 효과", will_recheck: true,
      },
      { kind: "search", subq_idx: 0, query: "초등 AI 윤리 교육 효과", found: 9, round: 2, new_papers: 4 },
    ]);
    const sq = v.subqs[0]!;
    expect(sq.status).toBe("running");
    expect(sq.rounds).toEqual([
      { round: 1, query: "효과 측정", foundChunks: 12, newPapers: 5, verdict: "insufficient", note: "초등 대상 연구가 없다", nextQuery: "초등 AI 윤리 교육 효과" },
      { round: 2, query: "초등 AI 윤리 교육 효과", foundChunks: 9, newPapers: 4, verdict: null, note: "", nextQuery: null },
    ]);
    expect(v.highlight).toEqual({ subqIdx: 0, round: 1, note: "초등 대상 연구가 없다", nextQuery: "초등 AI 윤리 교육 효과" });
    expect(researchPhase(v)).toBe("exploring");
    expect(subqStatusLabel(sq)).toBe("탐색 중 · 2회차");
  });

  it("round 가 없는 이벤트(보강 전 서버)도 순서대로 회차를 매긴다", () => {
    const v = run([
      { kind: "search", subq_idx: 1, query: "교사 인식", found: 3 },
      { kind: "critique", subq_idx: 1, verdict: "insufficient", note: "", adopted: 1, parse_failed: false, capped: 0 },
      { kind: "search", subq_idx: 1, query: "교사 태도", found: 4 },
    ]);
    expect(v.subqs[1]!.rounds.map((r) => [r.round, r.query, r.verdict])).toEqual([[1, "교사 인식", "insufficient"], [2, "교사 태도", null]]);
  });

  it("재검색하지 않는 점검은 강조 카드를 만들지 않는다", () => {
    const v = run([
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      { kind: "critique", subq_idx: 0, verdict: "sufficient", note: "충분", adopted: 6, parse_failed: false, capped: 0, round: 1, next_query: null, will_recheck: false },
    ]);
    expect(v.highlight).toBeNull();
    expect(v.subqs[0]!.adopted).toBe(6);
  });

  it("counters 이벤트는 카운터를 통째로 바꾼다", () => {
    const v = run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 }]);
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 7, rechecks: 1 });
  });

  it("같은 하위질문의 새 시도는 이전 시도의 회차를 버린다", () => {
    const v = run([
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      { kind: "step", seq: 5, step_kind: "search", subq_idx: 0, title: "효과 측정", status: "running" },
    ]);
    expect(v.subqs[0]!.seq).toBe(5);
    expect(v.subqs[0]!.rounds).toEqual([]);
  });

  it("단계 결과의 rounds 가 라이브 회차보다 앞서고, 결과에 없는 뒤 회차는 남긴다", () => {
    const v = run([
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      { kind: "search", subq_idx: 0, query: "초등 효과", found: 9, round: 2, new_papers: 4 },
      {
        kind: "step", seq: 1, step_kind: "search", subq_idx: 0, title: "효과 측정", status: "running",
        result: { rounds: [{ round: 1, query: "효과 측정", found_chunks: 12, new_papers: 5, verdict: "insufficient", note: "저장본", next_query: "초등 효과" }] },
      },
    ]);
    expect(v.subqs[0]!.rounds.map((r) => [r.round, r.note])).toEqual([[1, "저장본"], [2, ""]]);
    expect(v.source).toBe("rounds");
  });
});

describe("applyResearchEvent — snapshot·상태", () => {
  it("snapshot 이 결과 없는 행(보강 전 서버)을 보내도 이미 아는 결과를 지우지 않는다", () => {
    const start = initialResearchView(job({
      steps: [step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "running", result: { rounds: [{ round: 1, query: "효과 측정" }] } })],
    }));
    const v = applyResearchEvent(start, {
      kind: "snapshot",
      steps: [{ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", detail: null, status: "running" }],
    });
    expect(v.subqs[0]!.rounds.map((r) => r.query)).toEqual(["효과 측정"]);
  });

  it("snapshot 의 job 으로 상태·계획·카운터를 맞춘다", () => {
    const v = applyResearchEvent(initialResearchView(job({ status: "planning", plan: null })), {
      kind: "snapshot",
      steps: [step({ result: { subquestions: ["가", "나", "다"] } })],
      job: { status: "awaiting_approval", stage: "planned", plan: ["가", "나", "다"], counters: { papers_reviewed: 0, evidence_adopted: 0, rechecks: 0 } },
    });
    expect(researchPhase(v)).toBe("awaiting");
    expect(v.subqs).toHaveLength(3);
    expect(v.counters.papersReviewed).toBe(0);
  });

  it("탐색 중 다시 붙으면 저장된 회차에서 강조 카드를 되살린다", () => {
    const v = applyResearchEvent(initialResearchView(job()), {
      kind: "snapshot",
      steps: [step({
        seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "running",
        result: { rounds: [{ round: 1, query: "효과 측정", verdict: "insufficient", note: "부족", next_query: "초등 효과" }] },
      })],
    });
    expect(v.highlight).toEqual({ subqIdx: 0, round: 1, note: "부족", nextQuery: "초등 효과" });
  });

  it("탐색 중 재접속 — 한 회차 뒤처진 snapshot 카운터가 라이브 카운터를 되돌리지 않는다", () => {
    const v = applyResearchEvent(run(AWAITING_ROUND2_CRITIQUE), {
      kind: "snapshot",
      steps: [PLAN_ROW, SAVED_SEARCH_ROW],
      job: { status: "running", stage: "planned", plan: ["효과 측정", "교사 인식"], counters: SAVED },
    });
    expect(v.counters).toEqual(LIVE_VIEW);
    expect(v.subqs[0]!.rounds.map((r) => r.round)).toEqual([1, 2]);
  });

  it("진행 저장 step 이벤트의 result.counters 로 뒤처진 카운터를 바로잡는다", () => {
    // 저장본으로 연 화면이 counters 이벤트를 놓쳤다 — 점검 직후의 진행 저장이 라이브 값을 싣는다
    const start = initialResearchView(job({ steps: [PLAN_ROW, SAVED_SEARCH_ROW] }));
    expect(start.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 5, rechecks: 0 });
    const v = applyResearchEvent(start, { ...SEARCH_STARTED, result: { rounds: [ROUND1, ROUND2], counters: LIVE } });
    expect(v.counters).toEqual(LIVE_VIEW);
  });

  it("탐색부터 다시 도는 재시도 — 화면이 모르는 뒤 단계의 저장본은 작아도 그대로 쓴다", () => {
    // 재시도는 카운터를 0 부터 새로 센다. 이전 시도의 큰 값을 남기면 안 된다.
    const failed = initialResearchView(job({
      status: "failed", last_error: "x",
      steps: [
        PLAN_ROW,
        step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", result: { rounds: [ROUND1], counters: SAVED } }),
        step({ seq: 2, kind: "search", subq_idx: 1, title: "교사 인식", status: "failed", result: { error: "e", rounds: [], counters: LIVE } }),
      ],
    }));
    const queued = applyResearchEvent(failed, { kind: "status", status: "queued", stage: "planned" });
    const retried = { papers_reviewed: 3, evidence_adopted: 1, rechecks: 0 };
    const v = applyResearchEvent(queued, {
      kind: "snapshot",
      steps: [
        ...failed.steps,
        step({ seq: 3, kind: "search", subq_idx: 0, title: "효과 측정", status: "running", result: { rounds: [ROUND1], counters: retried } }),
      ],
      job: { status: "running", stage: "planned", plan: ["효과 측정", "교사 인식"], counters: retried },
    });
    expect(v.counters).toEqual({ papersReviewed: 3, evidenceAdopted: 1, rechecks: 0 });
  });

  it("status 이벤트는 상태·단계를 바꾸고, 다시 도는 잡이면 실패 사유를 지운다", () => {
    const failed = initialResearchView(job({ status: "failed", last_error: "종합 실패" }));
    const v = applyResearchEvent(failed, { kind: "status", status: "queued", stage: "explored" });
    expect(v.status).toBe("queued");
    expect(v.lastError).toBeNull();
    expect(researchPhase(v)).toBe("queued");
  });

  it("종료 이벤트는 상태를 끝내고 실패 사유를 남긴다", () => {
    const failed: ResearchEvent = { kind: "failed", status: "failed", error: "모든 하위질문 탐색이 오류로 실패했다" };
    const v = run([failed]);
    expect(v.status).toBe("failed");
    expect(v.lastError).toBe("모든 하위질문 탐색이 오류로 실패했다");
    expect(isTerminalEvent(failed)).toBe(true);
    expect(isTerminalEvent({ kind: "search" })).toBe(false);
  });

  it("모르는 이벤트는 그대로 둔다", () => {
    const start = initialResearchView(job());
    expect(applyResearchEvent(start, { kind: "ping" } as unknown as ResearchEvent)).toBe(start);
  });

  it("상태별 화면 단계", () => {
    const phase = (status: ResearchJob["status"], stage: ResearchJob["stage"] = "planned") =>
      researchPhase(initialResearchView(job({ status, stage })));
    expect(phase("created", "created")).toBe("planning");
    expect(phase("approved")).toBe("queued");
    expect(phase("running", "explored")).toBe("synthesizing");
    expect(phase("canceled")).toBe("canceled");
  });
});

describe("applyResearchEvent — 종합", () => {
  it("절 이벤트로 진행을 센다", () => {
    const v = run([
      { kind: "status", status: "running", stage: "explored" },
      { kind: "step", seq: 3, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running" },
      { kind: "synth", section_idx: 0, total: 3, status: "running" },
      { kind: "synth", section_idx: 0, total: 3, status: "done" },
      { kind: "synth", section_idx: 1, total: 3, status: "running" },
    ]);
    expect(researchPhase(v)).toBe("synthesizing");
    expect(synthProgress(v)).toEqual({ current: 2, total: 3 });
  });

  it("다시 받은 snapshot 이 앞선 절 상태를 되돌리지 않는다", () => {
    const live = run([
      { kind: "step", seq: 3, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running" },
      { kind: "synth", section_idx: 0, total: 2, status: "done" },
    ]);
    const v = applyResearchEvent(live, {
      kind: "snapshot",
      steps: [step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "running", result: { sections_total: 2, sections: [{ idx: 0, status: "running" }] } })],
    });
    expect(v.synth.sections).toEqual([{ idx: 0, status: "done" }]);
  });

  it("보강 전 종합 결과(절 수)도 완료로 센다", () => {
    const v = initialResearchView(job({
      status: "completed", stage: "synthesized",
      steps: [step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "done", result: { sections: 3 } })],
    }));
    expect(synthProgress(v)).toEqual({ current: 3, total: 3 });
  });
});

describe("보강 전 잡", () => {
  it("단계 결과에 rounds 가 없으면 report.trail 로 회차를 대신 보여 준다", () => {
    const v = initialResearchView(job({
      status: "completed", stage: "synthesized", plan: ["효과 측정"], report: oldReport(),
      steps: [
        step({ seq: 0, result: { subquestions: ["효과 측정"] } }),
        step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", result: { queries: ["효과 측정", "초등 효과"], adopted: 4, verdict: "sufficient", note: "충분하다" } }),
      ],
    }));
    expect(v.source).toBe("trail");
    expect(v.subqs[0]!.rounds).toEqual([
      { round: 1, query: "효과 측정", foundChunks: null, newPapers: null, verdict: "insufficient", note: "", nextQuery: "초등 효과" },
      { round: 2, query: "초등 효과", foundChunks: null, newPapers: null, verdict: "sufficient", note: "충분하다", nextQuery: null },
    ]);
    expect(v.counters).toEqual({ papersReviewed: null, evidenceAdopted: 1, rechecks: 1 });
    expect(v.highlight).toBeNull();
  });

  it("보고서가 없는 옛 실패 잡은 단계 결과의 queries 로 회차를 만든다", () => {
    const v = initialResearchView(job({
      status: "failed", last_error: "x", plan: ["효과 측정"],
      steps: [step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", result: { queries: ["효과 측정"], verdict: "sufficient", note: "" } })],
    }));
    expect(v.source).toBe("queries");
    expect(v.subqs[0]!.rounds.map((r) => r.query)).toEqual(["효과 측정"]);
  });
});

describe("refreshView·withPlan", () => {
  it("GET 재조회는 보고서가 없을 때 라이브 카운터를 잃지 않는다", () => {
    const live = run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 }]);
    const v = refreshView(live, job({ status: "failed", last_error: "종합 실패" }));
    expect(v.status).toBe("failed");
    expect(v.counters.papersReviewed).toBe(20);
  });

  it("회차 도중 취소 — 저장본이 한 회차 뒤처져 있어도 라이브 카운터를 지킨다", () => {
    // 점검을 기다리는 동안 취소하면 GET 에는 앞 회차 카운터만 들어 있다
    const live = run([...AWAITING_ROUND2_CRITIQUE, { kind: "canceled", status: "canceled" }]);
    const v = refreshView(live, job({
      status: "canceled", finished_at: "2026-09-26T01:05:00Z",
      steps: [PLAN_ROW, SAVED_SEARCH_ROW],
    }));
    expect(v.status).toBe("canceled");
    expect(v.subqs[0]!.rounds.map((r) => r.round)).toEqual([1, 2]);
    expect(v.counters).toEqual(LIVE_VIEW);
  });

  it("탐색 중 재접속한 뒤 종합이 실패해도 다시 연 화면과 카운터가 같다", () => {
    const doneSearch = step({
      seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "done",
      result: { queries: ["효과 측정", "초등 AI 윤리 교육 효과"], adopted: 7, rounds: [ROUND1, ROUND2], counters: LIVE },
    });
    const live = run([
      ...AWAITING_ROUND2_CRITIQUE,
      {
        kind: "snapshot", steps: [PLAN_ROW, SAVED_SEARCH_ROW],
        job: { status: "running", stage: "planned", plan: ["효과 측정", "교사 인식"], counters: SAVED },
      },
      { ...SEARCH_STARTED, result: { rounds: [ROUND1, ROUND2], counters: LIVE } },
      { ...SEARCH_STARTED, status: "done", result: doneSearch.result },
      { kind: "status", status: "running", stage: "explored" },
      { kind: "step", seq: 2, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running" },
      { kind: "failed", status: "failed", error: "종합 실패" },
    ]);
    const got = job({
      status: "failed", stage: "explored", last_error: "종합 실패",
      steps: [
        PLAN_ROW, doneSearch,
        step({ seq: 2, kind: "synthesize", title: "보고서 종합", status: "failed", result: { sections_total: 1, sections: [], error: "종합 실패" } }),
      ],
    });
    expect(live.counters).toEqual(LIVE_VIEW);
    expect(refreshView(live, got).counters).toEqual(initialResearchView(got).counters);
    expect(refreshView(live, got).counters).toEqual(LIVE_VIEW);
  });

  it("스트림이 끊긴 사이 앞서 나간 GET 카운터는 라이브보다 커도 받아들인다", () => {
    const live = run([SEARCH_STARTED, { kind: "counters", ...SAVED }]);
    const v = refreshView(live, job({
      steps: [PLAN_ROW, step({ ...SAVED_SEARCH_ROW, result: { rounds: [ROUND1, ROUND2], counters: LIVE } })],
    }));
    expect(v.counters).toEqual(LIVE_VIEW);
  });

  it("라이브 카운터를 받은 적이 없으면 GET 에 저장된 카운터로 채운다", () => {
    const v = refreshView(initialResearchView(job()), job({
      status: "canceled",
      steps: [step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "running", result: { rounds: [], counters: { papers_reviewed: 20, evidence_adopted: 5, rechecks: 0 } } })],
    }));
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 5, rechecks: 0 });
  });

  it("완료 잡은 라이브 카운터보다 보고서 stats(최종값)를 쓴다", () => {
    const live = run([{ kind: "counters", papers_reviewed: 26, evidence_adopted: 7, rechecks: 1 }]);
    const v = refreshView(live, job({
      status: "completed", stage: "synthesized",
      report: oldReport({ stats: { papers_reviewed: 30, evidence_adopted: 9, rechecks: 2 } }),
    }));
    expect(v.counters).toEqual({ papersReviewed: 30, evidenceAdopted: 9, rechecks: 2 });
  });

  it("다른 잡의 응답이면 이전 화면을 섞지 않는다", () => {
    const live = run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 }]);
    const v = refreshView(live, job({ job_id: "22222222-2222-4222-8222-222222222222", status: "failed" }));
    expect(v.counters.papersReviewed).toBeNull();
  });

  it("승인한 계획으로 하위질문 제목을 바꾼다", () => {
    const v = withPlan(initialResearchView(job({ status: "awaiting_approval" })), ["새 질문 하나"]);
    expect(v.subqs.map((s) => s.title)).toEqual(["새 질문 하나"]);
  });
});

describe("applyApproval", () => {
  const AWAITING = () => initialResearchView(job({ status: "awaiting_approval", started_at: null }));

  it("아직 승인 대기면 응답의 approved 와 계획을 반영한다", () => {
    const v = applyApproval(AWAITING(), "approved", ["새 질문 하나"]);
    expect(v.status).toBe("approved");
    expect(researchPhase(v)).toBe("queued");
    expect(v.subqs.map((s) => s.title)).toEqual(["새 질문 하나"]);
  });

  it("스트림이 먼저 running 을 알렸으면 응답의 approved 로 되돌리지 않는다", () => {
    // 서버는 큐에 넣기 전에 approved 를 알린다 — 워커가 곧바로 집으면 running·단계 이벤트가
    // HTTP 응답보다 먼저 온다. 되돌리면 다음 status(explored)까지 탐색 화면이 대기열로 가려진다.
    const live = run([
      { kind: "status", status: "approved", stage: "planned" },
      { kind: "status", status: "running", stage: "planned" },
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
    ], AWAITING());
    const v = applyApproval(live, "approved", ["효과 측정", "교사 인식"]);
    expect(v.status).toBe("running");
    expect(researchPhase(v)).toBe("exploring");
    expect(v.subqs[0]!.rounds.map((r) => r.query)).toEqual(["효과 측정"]);
  });

  it("재접속 snapshot 이 먼저 와 running 이 됐어도 되돌리지 않는다", () => {
    const live = run([{
      kind: "snapshot", steps: [PLAN_ROW, SAVED_SEARCH_ROW],
      job: { status: "running", stage: "planned", plan: ["효과 측정", "교사 인식"], counters: SAVED },
    }], AWAITING());
    const v = applyApproval(live, "approved", ["효과 측정", "교사 인식"]);
    expect(v.status).toBe("running");
    expect(researchPhase(v)).toBe("exploring");
  });

  it("응답에 계획이 없으면 화면의 계획을 그대로 둔다", () => {
    const v = applyApproval(AWAITING(), "approved", null);
    expect(v.status).toBe("approved");
    expect(v.plan).toEqual(["효과 측정", "교사 인식"]);
  });
});

describe("stopPoint — 멈춘 지점", () => {
  // 워커는 하위질문을 idx 순서로 하나씩 돌고, 하위질문 하나가 오류로 끝나도 잡을 멈추지 않는다
  // (부분 실패는 전체 실패가 아니다). 그래서 failed 하위질문이 곧 멈춘 지점은 아니다.
  const PLAN3 = ["효과 측정", "교사 인식", "정책 과제"];
  const planRow = step({ seq: 0, result: { subquestions: PLAN3 } });
  const searchRow = (idx: number, status: ResearchStepRow["status"], result: ResearchStepRow["result"] = {}) =>
    step({ seq: idx + 1, kind: "search", subq_idx: idx, title: PLAN3[idx]!, status, result });
  const synthRow = (error: string) => step({
    seq: 4, kind: "synthesize", title: "보고서 종합", status: "failed",
    result: { sections_total: 2, sections: [{ idx: 0, status: "done" }], error },
  });
  const PARTIAL = searchRow(0, "failed", { error: "검색 오류" });
  const at = (over: Partial<ResearchJob>) => stopPoint(initialResearchView(job({ plan: PLAN3, ...over })));
  // 그 하위질문을 돌다 멈춤 / 그 하위질문을 시작하기 전에 멈춤
  const inSubq = (idx: number, error: string | null = null) => ({ kind: "subq", idx, started: true, error });
  const beforeSubq = (idx: number) => ({ kind: "subq", idx, started: false, error: null });

  it("앞 하위질문이 부분 실패하고 종합에서 실패한 잡은 보고서 작성 단계에서 멈췄다", () => {
    expect(at({
      status: "failed", stage: "explored", last_error: "종합 실패",
      steps: [planRow, PARTIAL, searchRow(1, "done"), searchRow(2, "done"), synthRow("종합 실패")],
    })).toEqual({ kind: "synth" });
  });

  it("종합 중 취소도 앞선 부분 실패가 아니라 보고서 작성 단계를 짚는다", () => {
    expect(at({
      status: "canceled", stage: "explored",
      steps: [planRow, PARTIAL, searchRow(1, "done"), searchRow(2, "done"), synthRow("취소됨")],
    })).toEqual({ kind: "synth" });
  });

  it("종합 단계 행이 생기기 전에 멈춘 stage=explored 잡도 보고서 작성 단계다", () => {
    expect(at({
      status: "canceled", stage: "explored",
      steps: [planRow, PARTIAL, searchRow(1, "done"), searchRow(2, "done")],
    })).toEqual({ kind: "synth" });
  });

  it("탐색 중 취소 — 앞에 부분 실패가 있어도 돌던 하위질문을 짚는다", () => {
    expect(at({
      status: "canceled", stage: "planned",
      steps: [planRow, PARTIAL, searchRow(1, "running")],
    })).toEqual(inSubq(1));
  });

  it("탐색 중 취소 이벤트를 받은 직후에도 돌던 하위질문을 짚는다", () => {
    expect(stopPoint(run([SEARCH_STARTED, { kind: "canceled", status: "canceled" }]))).toEqual(inSubq(0));
  });

  it("하위질문 경계에서 취소된 뒤 다시 연 잡은 시작하지 못한 첫 하위질문을 짚는다", () => {
    // 취소는 워커가 하위질문 경계에서 확인한다 — 돌던 하위질문은 끝까지 돌아 done 으로 닫힌다
    expect(at({
      status: "canceled", stage: "planned",
      steps: [planRow, PARTIAL, searchRow(1, "done")],
    })).toEqual(beforeSubq(2));
  });

  it("취소 뒤 끝까지 돌고 오류로 닫힌 하위질문이 있어도 취소는 그 다음 경계에서 멈춘 것이다", () => {
    expect(at({
      status: "canceled", stage: "planned",
      steps: [planRow, searchRow(0, "done"), searchRow(1, "failed", { error: "검색 오류" })],
    })).toEqual(beforeSubq(2));
  });

  it("시간 상한·회수기가 닫은 하위질문은 거기서 멈춘 것이다", () => {
    expect(at({
      status: "failed", stage: "planned", last_error: "시간 상한 초과 — 워커를 회수했다",
      steps: [planRow, searchRow(0, "done"), searchRow(1, "failed", { error: "시간 상한 초과 — 워커를 회수했다" })],
    })).toEqual(inSubq(1, "시간 상한 초과 — 워커를 회수했다"));
  });

  it("다음 하위질문을 열다 실패한 잡은 시작하지 못한 하위질문을 짚는다", () => {
    expect(at({
      status: "failed", stage: "planned", last_error: "DB 오류",
      steps: [planRow, searchRow(0, "done")],
    })).toEqual(beforeSubq(1));
  });

  it("전멸 실패는 마지막 하위질문에서 멈췄다", () => {
    expect(at({
      status: "failed", stage: "planned", last_error: "모든 하위질문 탐색이 오류로 실패했다",
      steps: [
        planRow,
        searchRow(0, "failed", { error: "검색 오류" }),
        searchRow(1, "failed", { error: "검색 오류" }),
        searchRow(2, "failed", { error: "검색 오류" }),
      ],
    })).toEqual(inSubq(2, "검색 오류"));
  });

  it("탐색을 다 마치고 종합 전에 취소된 잡은 보고서 작성 단계다 — 마지막 하위질문이 부분 실패여도", () => {
    const explored = [planRow, searchRow(0, "done"), searchRow(1, "done")];
    expect(at({ status: "canceled", stage: "planned", steps: [...explored, searchRow(2, "done")] }))
      .toEqual({ kind: "synth" });
    expect(at({ status: "canceled", stage: "planned", steps: [...explored, searchRow(2, "failed", { error: "검색 오류" })] }))
      .toEqual({ kind: "synth" });
  });

  it("계획 단계 실패는 탐색을 시작하기 전이다", () => {
    expect(at({
      status: "failed", stage: "created", plan: null, last_error: "LLM 오류", started_at: null,
      steps: [step({ seq: 0, status: "failed", result: { error: "LLM 오류" } })],
    })).toEqual({ kind: "before" });
  });

  it("승인 대기·대기열에서 취소된 잡도 탐색을 시작하기 전이다", () => {
    expect(at({ status: "canceled", stage: "planned", started_at: null, steps: [planRow] })).toEqual({ kind: "before" });
  });

  describe("탐색부터 다시 도는 재시도(stage=planned)", () => {
    // 재시도는 idx 0 부터 새 seq 로 행을 쌓는다. 이번 시도가 아직 닿지 않은 하위질문에는 이전
    // 시도의 행(done·failed·그 오류)이 그대로 남는다.
    const TIMEOUT = "시간 상한 초과 — 워커를 회수했다";
    const REAPED = "stale — 워커 응답 없음";
    const rowAt = (seq: number, idx: number, status: ResearchStepRow["status"], result: ResearchStepRow["result"] = {}) =>
      step({ seq, kind: "search", subq_idx: idx, title: PLAN3[idx]!, status, result });
    // 1차 시도: 하위질문 0·1 을 마치고 2 에서 시간 상한에 걸려 실패했다
    const FIRST_TRY = [planRow, searchRow(0, "done"), searchRow(1, "done"), searchRow(2, "failed", { error: TIMEOUT })];

    it("재시도가 하위질문 0 을 마치고 취소되면 하위질문 1 을 시작하기 전이다 — 이전 시도의 done 행에 속지 않는다", () => {
      expect(at({ status: "canceled", stage: "planned", steps: [...FIRST_TRY, rowAt(4, 0, "done")] }))
        .toEqual(beforeSubq(1));
    });

    it("재시도가 하위질문 1 에서 실패하면 거기서 멈췄고, 이전 시도가 아니라 이번 시도의 오류를 붙인다", () => {
      expect(at({
        status: "failed", stage: "planned", last_error: REAPED,
        steps: [...FIRST_TRY, rowAt(4, 0, "done"), rowAt(5, 1, "failed", { error: REAPED })],
      })).toEqual(inSubq(1, REAPED));
    });

    it("재시도 후 대기열에서 취소 — 앞 시도의 행으로 판정하고, 닿지 않은 하위질문의 옛 오류는 붙이지 않는다", () => {
      // 2차 시도가 하위질문 1 에서 실패한 뒤 다시 재시도하고 대기열에서 취소했다. 단계 행에 시각이
      // 없어 "2차 시도가 하위질문 1 을 돌다 취소됨"과 모양이 같다 — 둘 다 하위질문 2 는 시작하지 않았다.
      expect(at({
        status: "canceled", stage: "planned",
        steps: [...FIRST_TRY, rowAt(4, 0, "done"), rowAt(5, 1, "failed", { error: REAPED })],
      })).toEqual(beforeSubq(2));
    });

    it("재시도를 라이브로 보다 취소 이벤트를 받아도 다시 열었을 때와 같은 곳을 짚는다", () => {
      const failed = initialResearchView(job({
        plan: PLAN3, status: "failed", stage: "planned", last_error: TIMEOUT, steps: FIRST_TRY,
      }));
      const opened = { kind: "step", seq: 4, step_kind: "search", subq_idx: 0, title: PLAN3[0]!, status: "running" } as const;
      const live = run([
        { kind: "status", status: "queued", stage: "planned" },
        { kind: "status", status: "running", stage: "planned" },
        opened,
        { ...opened, status: "done", result: {} },
        { kind: "canceled", status: "canceled" },
      ], failed);
      expect(stopPoint(live)).toEqual(beforeSubq(1));
    });
  });

  it("멈추지 않은 잡은 멈춘 지점이 없다", () => {
    const steps = [planRow, PARTIAL, searchRow(1, "running")];
    expect(at({ status: "running", stage: "planned", steps })).toBeNull();
    expect(at({ status: "awaiting_approval", stage: "planned", steps: [planRow] })).toBeNull();
    expect(at({
      status: "completed", stage: "synthesized",
      steps: [planRow, PARTIAL, searchRow(1, "done"), searchRow(2, "done")],
    })).toBeNull();
  });
});
