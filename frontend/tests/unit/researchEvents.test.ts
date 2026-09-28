// frontend/tests/unit/researchEvents.test.ts
import { describe, expect, it } from "vitest";
import type {
  ReportChunk,
  ReportEvidence,
  ReportSection,
  ResearchEvent,
  ResearchJob,
  ResearchReport,
  ResearchStepRow,
  ResearchView,
  StepEvent,
  StepResult,
  SynthEvent,
} from "~/types/research";
import {
  applyApproval,
  applyResearchEvent,
  initialResearchView,
  isTerminalEvent,
  mergeEvidence,
  refreshView,
  researchPhase,
  sectionGapToRecover,
  stopPoint,
  subqStatusLabel,
  synthClosePending,
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
    expect(v.synth.sections.map((s) => [s.idx, s.status])).toEqual([[0, "done"]]);
  });

  it("보강 전 종합 결과(절 수)도 완료로 센다", () => {
    const v = initialResearchView(job({
      status: "completed", stage: "synthesized",
      steps: [step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "done", result: { sections: 3 } })],
    }));
    expect(synthProgress(v)).toEqual({ current: 3, total: 3 });
  });
});

// ── 절 미리보기(spec §14) ─────────────────────────────────
// 절 순번(section_idx)과 하위질문 번호(subq_idx)는 다르다 — 근거 없는 하위질문은 절이 되지 않는다.
// 워커는 절이 끝날 때 synth 이벤트로 다듬은 절·근거를 한 번만 보내고, 진행 저장본(DB)에는 남기되
// 알리는 step 이벤트에는 뺀다(가벼운 step 이벤트).
const T0 = "2026-09-28T01:00:00.123456+00:00";
const T1 = "2026-09-28T01:00:40.654321+00:00";
const HEADINGS = ["효과 측정", "정책 과제"];

function chunk(id: string, score: number): ReportChunk {
  return { chunk_id: id, text: `대목 ${id}`, page_start: 3, page_end: 3, score };
}

function evidence(cntsId: string, chunks: ReportChunk[]): ReportEvidence {
  return { cnts_id: cntsId, meta: { title: `논문 ${cntsId}` }, chunks };
}

const SEC0: ReportSection = {
  heading: "효과 측정",
  intro: "효과가 있었다 [E1]",
  papers: [{ cnts_id: "C1", summary: "요약", evidence: ["E1"] }],
  future: [],
  evidence_chunks: { E1: ["k1"] },
  chunk_scores: { k1: 0.9 },
};
const EV0 = { E1: evidence("C1", [chunk("k1", 0.9)]) };
const SYNTH_STEP: StepEvent = {
  kind: "step", seq: 3, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running",
};
const S0_RUNNING: SynthEvent = {
  kind: "synth", section_idx: 0, total: 2, status: "running",
  subq_idx: 0, heading: "효과 측정", headings: HEADINGS, started_at: T0,
};
const S0_DONE: SynthEvent = {
  kind: "synth", section_idx: 0, total: 2, status: "done",
  subq_idx: 0, heading: "효과 측정", headings: HEADINGS, duration_ms: 38000, section: SEC0, evidence: EV0,
};
const S1_RUNNING: SynthEvent = {
  kind: "synth", section_idx: 1, total: 2, status: "running",
  subq_idx: 2, heading: "정책 과제", headings: HEADINGS, started_at: T1,
};
// 절 1 도 근거 E1 을 쓰지만 자기 절에서 매칭된 대목(k4·k1)만 싣는다
const S1_DONE: SynthEvent = {
  kind: "synth", section_idx: 1, total: 2, status: "done",
  subq_idx: 2, heading: "정책 과제", headings: HEADINGS, duration_ms: 52000,
  section: { ...SEC0, heading: "정책 과제", evidence_chunks: { E1: ["k4", "k1"], E2: ["k9"] } },
  evidence: { E1: evidence("C1", [chunk("k4", 0.95), chunk("k1", 0.9)]), E2: evidence("C2", [chunk("k9", 0.4)]) },
};
// 알리는 step 이벤트·완료로 닫힌 단계의 result — 절 내용(section)·근거(evidence)가 없다
const LIGHT_RESULT: StepResult = {
  sections_total: 2,
  headings: HEADINGS,
  sections: [
    { idx: 0, status: "done", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: 38000 },
    { idx: 1, status: "running", subq_idx: 2, heading: "정책 과제", started_at: T1, duration_ms: null },
  ],
};
// 진행 저장본(snapshot·GET 의 steps[].result) — 끝난 절의 내용과 근거 합집합이 있다
const SAVED_RESULT: StepResult = {
  sections_total: 2,
  headings: HEADINGS,
  sections: [
    { idx: 0, status: "done", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: 38000, section: SEC0 },
    { idx: 1, status: "running", subq_idx: 2, heading: "정책 과제", started_at: T1, duration_ms: null },
  ],
  evidence: EV0,
};
const SYNTH_ROW = step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "running", result: SAVED_RESULT });

describe("applyResearchEvent — 절 미리보기", () => {
  it("synth 이벤트로 절 제목·시작 시각·걸린 시간·다듬은 절·근거를 쌓는다", () => {
    const v = run([SYNTH_STEP, S0_RUNNING, S0_DONE, S1_RUNNING]);
    expect(v.synth.headings).toEqual(HEADINGS);
    expect(v.synth.sections).toEqual([
      // done 이벤트에는 started_at 이 없다 — running 때 받은 시작 시각을 지킨다
      { idx: 0, status: "done", subqIdx: 0, heading: "효과 측정", startedAt: T0, durationMs: 38000, section: SEC0 },
      { idx: 1, status: "running", subqIdx: 2, heading: "정책 과제", startedAt: T1, durationMs: null, section: null },
    ]);
    expect(v.synth.evidence).toEqual(EV0);
    expect(synthProgress(v)).toEqual({ current: 2, total: 2 });
  });

  it("진행 저장본(snapshot·GET)으로 다시 연 화면이 라이브로 본 화면과 같은 절을 받는다", () => {
    const live = run([SYNTH_STEP, S0_RUNNING, S0_DONE, S1_RUNNING]);
    const opened = initialResearchView(job({ status: "running", stage: "explored", steps: [PLAN_ROW, SYNTH_ROW] }));
    const snap = applyResearchEvent(initialResearchView(job({ status: "running", stage: "explored" })), {
      kind: "snapshot",
      steps: [PLAN_ROW, SYNTH_ROW],
    });
    for (const v of [opened, snap]) {
      expect(v.synth.sections).toEqual(live.synth.sections);
      expect(v.synth.headings).toEqual(HEADINGS);
      expect(v.synth.evidence).toEqual(EV0);
      expect(v.synth.total).toBe(2);
    }
  });

  it("가벼운 step 이벤트(절 내용·근거 없음)가 받은 절 내용을 지우지 않는다", () => {
    const v = run([SYNTH_STEP, S0_RUNNING, S0_DONE, { ...SYNTH_STEP, result: LIGHT_RESULT }]);
    expect(v.synth.sections.map((s) => [s.idx, s.status, s.section])).toEqual([[0, "done", SEC0], [1, "running", null]]);
    expect(v.synth.evidence).toEqual(EV0);
  });

  it("근거가 없는 step 이벤트는 받은 근거 객체를 그대로 둔다", () => {
    // 근거를 읽는 computed(초안·인용칩)가 절과 무관한 이벤트마다 다시 돌지 않게
    const before = run([SYNTH_STEP, S0_RUNNING, S0_DONE]);
    const after = applyResearchEvent(before, { ...SYNTH_STEP, result: LIGHT_RESULT });
    expect(after.synth.evidence).toBe(before.synth.evidence);
  });

  it("워커가 모르는 칸을 null 로 실은 절(info 없이 부른 옛 콜백)은 빈 칸으로 받는다", () => {
    const v = initialResearchView(job({
      status: "running", stage: "explored",
      steps: [step({
        seq: 3, kind: "synthesize", title: "보고서 종합", status: "running",
        result: {
          sections_total: 1,
          sections: [{ idx: 0, status: "done", subq_idx: null, heading: null, started_at: null, duration_ms: null }],
        },
      })],
    }));
    expect(v.synth.sections).toEqual([
      { idx: 0, status: "done", subqIdx: null, heading: null, startedAt: null, durationMs: null, section: null },
    ]);
  });

  it("끊겼다 다시 받은 snapshot 이 뒤처져 있어도 라이브로 받은 절 상태·내용·걸린 시간을 지킨다", () => {
    const behind: StepResult = {
      sections_total: 2,
      headings: HEADINGS,
      sections: [{ idx: 0, status: "running", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: null }],
    };
    const v = applyResearchEvent(run([SYNTH_STEP, S0_RUNNING, S0_DONE]), {
      kind: "snapshot",
      steps: [PLAN_ROW, step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "running", result: behind })],
    });
    expect(v.synth.sections[0]).toEqual({
      idx: 0, status: "done", subqIdx: 0, heading: "효과 측정", startedAt: T0, durationMs: 38000, section: SEC0,
    });
    expect(v.synth.evidence).toEqual(EV0);
  });

  it("완료로 닫힌 단계(미리보기 없음)를 GET 으로 다시 맞춰도 받은 절 내용은 남는다", () => {
    // 완료 이벤트 뒤 보고서를 받는 동안·받기에 실패해 다시 시도하는 동안 초안을 그대로 보여 줄 원천
    const live = run([SYNTH_STEP, S0_RUNNING, S0_DONE, { kind: "done", status: "completed" }]);
    const got = job({
      status: "completed", stage: "synthesized",
      steps: [PLAN_ROW, step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "done", result: LIGHT_RESULT })],
    });
    const v = refreshView(live, got);
    expect(v.synth.status).toBe("done");
    expect(v.synth.sections[0]!.section).toEqual(SEC0);
    expect(v.synth.evidence).toEqual(EV0);
  });

  it("새 시도(종합 단계 seq 가 바뀜)면 이전 시도의 절·제목·근거를 비운다", () => {
    const v = run([
      SYNTH_STEP, S0_RUNNING, S0_DONE,
      { ...SYNTH_STEP, status: "failed", result: { ...LIGHT_RESULT, error: "취소됨" } },
      { kind: "status", status: "queued", stage: "explored" },
      { ...SYNTH_STEP, seq: 4 },
    ]);
    expect(v.synth.seq).toBe(4);
    expect(v.synth.sections).toEqual([]);
    expect(v.synth.headings).toEqual([]);
    expect(v.synth.evidence).toEqual({});
  });

  it("새 필드가 없는 옛 이벤트·옛 결과는 빈 칸으로 두고 진행만 센다", () => {
    const live = run([
      SYNTH_STEP,
      { kind: "synth", section_idx: 0, total: 3, status: "running" },
      { kind: "synth", section_idx: 0, total: 3, status: "done" },
    ]);
    expect(live.synth.sections).toEqual([
      { idx: 0, status: "done", subqIdx: null, heading: null, startedAt: null, durationMs: null, section: null },
    ]);
    expect(live.synth.headings).toEqual([]);
    expect(live.synth.evidence).toEqual({});
    expect(synthProgress(live)).toEqual({ current: 1, total: 3 });
    const opened = initialResearchView(job({
      status: "running", stage: "explored",
      steps: [step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "running", result: { sections_total: 3, sections: [{ idx: 0, status: "done" }] } })],
    }));
    expect(opened.synth.sections).toEqual(live.synth.sections);
    expect(opened.synth.headings).toEqual([]);
    expect(opened.synth.evidence).toEqual({});
  });

  it("같은 근거가 두 절에 나오면 대목을 chunk_id 로 합쳐 점수순으로 둔다", () => {
    const v = run([SYNTH_STEP, S0_RUNNING, S0_DONE, S1_RUNNING, S1_DONE]);
    expect(Object.keys(v.synth.evidence).sort()).toEqual(["E1", "E2"]);
    expect(v.synth.evidence.E1!.chunks.map((c) => c.chunk_id)).toEqual(["k4", "k1"]);
    expect(synthProgress(v)).toEqual({ current: 2, total: 2 });
  });

  it("mergeEvidence 는 원본을 바꾸지 않고 한쪽에만 있는 근거도 싣는다", () => {
    const a = { E1: evidence("C1", [chunk("k1", 0.9), chunk("k2", 0.5)]) };
    const b = { E1: evidence("C1", [chunk("k2", 0.5), chunk("k3", 0.7)]), E2: evidence("C2", [chunk("k9", 0.4)]) };
    const m = mergeEvidence(a, b);
    expect(m.E1!.chunks.map((c) => c.chunk_id)).toEqual(["k1", "k3", "k2"]);
    expect(m.E2).toEqual(b.E2);
    expect(a.E1.chunks.map((c) => c.chunk_id)).toEqual(["k1", "k2"]);
  });
});

// 보고서 작성부터 다시 시도(stage=explored)하면 워커는 running 을 알린 뒤 스냅샷을 되살리고서야
// 새 종합 단계를 연다. 그 사이 화면에 남은 종합 단계는 이전 시도의 닫힌 단계다.
describe("재시도 — 이전 시도의 종합 단계", () => {
  const EMPTY = { seq: null, status: null, total: 0, sections: [], headings: [], evidence: {} };
  // 2개 절 중 1개를 쓰고 실패한 잡 — 종합 단계(seq 3)가 미리보기를 남긴 채 failed 로 닫혔다
  const FAILED_SYNTH_ROW = step({
    seq: 3, kind: "synthesize", title: "보고서 종합", status: "failed", result: { ...SAVED_RESULT, error: "종합 실패" },
  });
  const NEW_SYNTH_ROW = step({
    seq: 5, kind: "synthesize", title: "보고서 종합", status: "running",
    result: { sections_total: 2, headings: HEADINGS, sections: [{ idx: 0, status: "running", subq_idx: 0, heading: "효과 측정", started_at: T1 }] },
  });
  const failedJob = (over: Partial<ResearchJob> = {}) => job({
    status: "failed", stage: "explored", last_error: "종합 실패", steps: [PLAN_ROW, FAILED_SYNTH_ROW], ...over,
  });

  it("재시도를 누르면 새 종합 단계가 열리기 전까지 이전 시도의 초안을 되살리지 않는다", () => {
    const failed = initialResearchView(failedJob());
    expect(failed.synth.sections[0]!.section).toEqual(SEC0);
    const queued = applyResearchEvent(failed, { kind: "status", status: "queued", stage: "explored" });
    // 재접속 snapshot 이 이전 시도의 종합 단계를 다시 실어도 되살리지 않는다
    const snap = applyResearchEvent(queued, {
      kind: "snapshot", steps: [PLAN_ROW, FAILED_SYNTH_ROW], job: { status: "queued", stage: "explored", plan: job().plan },
    });
    const running = applyResearchEvent(snap, { kind: "status", status: "running", stage: "explored" });
    expect(researchPhase(running)).toBe("synthesizing");
    for (const v of [queued, snap, running]) expect(v.synth).toMatchObject(EMPTY);
    expect(synthProgress(running)).toEqual({ current: 0, total: 0 });

    const next = run([{ ...SYNTH_STEP, seq: 5 }, S0_RUNNING], running);
    expect(next.synth.seq).toBe(5);
    expect(next.synth.sections.map((s) => [s.idx, s.status, s.section])).toEqual([[0, "running", null]]);
  });

  it("끝난 화면이 GET 으로 도는 잡을 받으면(409 뒤·다시 불러오기) 그 사이의 재시도로 보고 비운다", () => {
    const failed = initialResearchView(failedJob());
    const gap = refreshView(failed, failedJob({ status: "running", last_error: null }));
    expect(researchPhase(gap)).toBe("synthesizing");
    expect(gap.synth).toMatchObject(EMPTY);
    // 새 종합 단계가 이미 열렸으면 그것을 읽는다
    const opened = refreshView(failed, failedJob({ status: "running", last_error: null, steps: [PLAN_ROW, FAILED_SYNTH_ROW, NEW_SYNTH_ROW] }));
    expect(opened.synth.seq).toBe(5);
    expect(opened.synth.sections.map((s) => [s.idx, s.status, s.section])).toEqual([[0, "running", null]]);
    expect(opened.synth.evidence).toEqual({});
  });

  it("재시도로 큐에 든 잡(queued)을 새로 열어도 워커가 집은 뒤 이전 시도의 초안이 되살아나지 않는다", () => {
    // queued 는 재시도로 다시 큐에 든 상태다 — 워커가 집기 전이라 남은 종합 단계는 모두 이전 시도의 것이다
    const opened = initialResearchView(failedJob({ status: "queued", last_error: null }));
    const running = applyResearchEvent(opened, { kind: "status", status: "running", stage: "explored" });
    for (const v of [opened, running]) expect(v.synth).toMatchObject(EMPTY);
    expect(refreshView(initialResearchView(job()), failedJob({ status: "queued", last_error: null })).synth).toMatchObject(EMPTY);
  });

  it("실패로 닫히는 동안(종합 단계 failed → 잡 failed)은 초안을 비우지 않는다", () => {
    const closing = run([
      SYNTH_STEP, S0_RUNNING, S0_DONE,
      { ...SYNTH_STEP, status: "failed", result: { ...LIGHT_RESULT, error: "종합 실패" } },
    ], initialResearchView(job({ stage: "explored" })));
    const failed = applyResearchEvent(closing, { kind: "failed", status: "failed", error: "종합 실패" });
    for (const v of [closing, failed]) expect(v.synth.sections[0]!.section).toEqual(SEC0);
  });
});

// 종합 중에 취소하면 API 는 곧바로 잡을 끝내지만, 워커는 LLM 을 부르기 직전에만 멈춤을 보므로 쓰던
// 절을 마저 쓰고(그 미리보기를 저장하고) 나서야 종합 단계를 failed 로 닫는다.
describe("취소 뒤 워커가 종합 단계를 닫기까지", () => {
  const S1_SECTION = S1_DONE.section!;
  const canceledLive = () => run(
    [SYNTH_STEP, S0_RUNNING, S0_DONE, S1_RUNNING, { kind: "canceled", status: "canceled" }],
    initialResearchView(job({ stage: "explored" })),
  );
  const closedJob = job({
    status: "canceled", stage: "explored",
    steps: [PLAN_ROW, step({
      seq: 3, kind: "synthesize", title: "보고서 종합", status: "failed",
      result: {
        sections_total: 2, headings: HEADINGS, error: "취소됨",
        sections: [
          { idx: 0, status: "done", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: 38000, section: SEC0 },
          { idx: 1, status: "done", subq_idx: 2, heading: "정책 과제", started_at: T1, duration_ms: 52000, section: S1_SECTION },
        ],
        evidence: mergeEvidence(EV0, S1_DONE.evidence!),
      },
    })],
  });

  it("취소한 잡의 종합 단계가 아직 열려 있으면 닫힐 때까지 다시 맞춰야 한다", () => {
    const live = canceledLive();
    expect(synthClosePending(live)).toBe(true);
    // 종료 직후의 GET 도 워커가 절을 쓰는 동안이면 단계가 아직 열려 있다
    const early = refreshView(live, job({ status: "canceled", stage: "explored", steps: [PLAN_ROW, SYNTH_ROW] }));
    expect(synthClosePending(early)).toBe(true);
  });

  it("워커가 닫은 단계를 GET 으로 받으면 마저 쓴 절이 멈춘 초안에 합쳐져 다시 연 화면과 같아진다", () => {
    const v = refreshView(canceledLive(), closedJob);
    expect(v.synth.status).toBe("failed");
    expect(v.synth.sections.map((s) => [s.idx, s.status, s.section])).toEqual([[0, "done", SEC0], [1, "done", S1_SECTION]]);
    expect(v.synth.sections).toEqual(initialResearchView(closedJob).synth.sections);
    expect(v.synth.evidence).toEqual(initialResearchView(closedJob).synth.evidence);
    expect(synthClosePending(v)).toBe(false);
  });

  it("도는 잡은 기다리지 않는다 — 단계를 닫는 이벤트를 스트림이 나른다", () => {
    expect(synthClosePending(run([SYNTH_STEP, S0_RUNNING], initialResearchView(job({ stage: "explored" }))))).toBe(false);
  });
});

// 화면을 열거나 다시 붙는 순간, 스트림은 스냅샷(DB)을 읽은 뒤에야 구독을 붙인다. 워커가 그 사이에 절을
// 끝내면 synth(done) 이벤트는 놓치고 스냅샷에도 아직 없으며, 뒤따르는 step 이벤트는 절 내용을 싣지 않는다.
describe("sectionGapToRecover — 놓친 절 내용을 저장본으로 한 번 다시 맞춘다", () => {
  const S0_RUNNING_ROW = step({
    seq: 3, kind: "synthesize", title: "보고서 종합", status: "running",
    result: {
      sections_total: 2, headings: HEADINGS,
      sections: [{ idx: 0, status: "running", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: null }],
    },
  });
  const LIGHT_BOTH_FINISHED: StepResult = {
    ...LIGHT_RESULT,
    sections: [
      { idx: 0, status: "done", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: 38000 },
      { idx: 1, status: "failed", subq_idx: 2, heading: "정책 과제", started_at: T1, duration_ms: 52000 },
    ],
  };
  const opened = () => applyResearchEvent(
    initialResearchView(job({ stage: "explored" })),
    { kind: "snapshot", steps: [PLAN_ROW, S0_RUNNING_ROW] },
  );
  // 절 0 의 synth(done) 는 구독이 붙기 전에 나갔다 — 뒤따른 가벼운 step 이벤트만 받는다
  const missed = () => applyResearchEvent(opened(), { ...SYNTH_STEP, result: LIGHT_RESULT });

  it("끝났다고 알려진 절에 내용이 없으면 열쇠를 주고, 같은 부족분이면 다시 주지 않는다", () => {
    expect(sectionGapToRecover(opened(), null)).toBeNull();
    const key = sectionGapToRecover(missed(), null);
    expect(key).not.toBeNull();
    expect(sectionGapToRecover(missed(), key)).toBeNull();
  });

  it("저장본(GET)을 받으면 놓친 절 내용이 채워지고 부족분이 사라진다", () => {
    const v = refreshView(missed(), job({ stage: "explored", steps: [PLAN_ROW, SYNTH_ROW] }));
    expect(v.synth.sections[0]!.section).toEqual(SEC0);
    expect(v.synth.evidence).toEqual(EV0);
    expect(sectionGapToRecover(v, null)).toBeNull();
  });

  it("부족한 절이 늘거나(내용 없는 failed 절 포함) 새 시도면 새 열쇠를 준다", () => {
    const key = sectionGapToRecover(missed(), null);
    const more = applyResearchEvent(missed(), { ...SYNTH_STEP, result: LIGHT_BOTH_FINISHED });
    const moreKey = sectionGapToRecover(more, key);
    expect(moreKey).not.toBeNull();
    expect(moreKey).not.toBe(key);
    const nextAttempt: ResearchView = { ...missed(), synth: { ...missed().synth, seq: 5 } };
    expect(sectionGapToRecover(nextAttempt, key)).not.toBeNull();
  });

  it("받은 절·옛 워커(절 내용 없음)·닫힌 종합 단계는 다시 읽지 않는다", () => {
    expect(sectionGapToRecover(run([SYNTH_STEP, S0_RUNNING, S0_DONE, { ...SYNTH_STEP, result: LIGHT_RESULT }]), null)).toBeNull();
    const oldWorker = run([
      SYNTH_STEP,
      { kind: "synth", section_idx: 0, total: 2, status: "done" },
      { ...SYNTH_STEP, result: { sections_total: 2, sections: [{ idx: 0, status: "done" }] } },
    ]);
    expect(sectionGapToRecover(oldWorker, null)).toBeNull();
    // 완료로 닫는 단계는 미리보기를 지우고 온다 — 종료 뒤 GET 이 보고서로 맞춘다
    const closing = applyResearchEvent(missed(), { ...SYNTH_STEP, status: "done", result: LIGHT_BOTH_FINISHED });
    expect(sectionGapToRecover(closing, null)).toBeNull();
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
