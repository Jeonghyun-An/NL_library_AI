// frontend/tests/unit/researchEvents.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchEvent, ResearchJob, ResearchReport, ResearchStepRow } from "~/types/research";
import {
  applyResearchEvent,
  initialResearchView,
  isTerminalEvent,
  refreshView,
  researchPhase,
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

  it("GET 에 저장된 카운터가 있으면 그 값으로 맞춘다", () => {
    const live = run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 }]);
    const v = refreshView(live, job({
      status: "failed", last_error: "종합 실패",
      steps: [step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "done", result: { rounds: [], counters: { papers_reviewed: 20, evidence_adopted: 7, rechecks: 2 } } })],
    }));
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 7, rechecks: 2 });
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
