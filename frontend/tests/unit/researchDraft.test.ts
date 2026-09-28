// frontend/tests/unit/researchDraft.test.ts
import { describe, expect, it } from "vitest";
import type {
  ReportEvidence,
  ReportSection,
  ResearchEvent,
  ResearchJob,
  ResearchView,
  SynthSectionView,
  SynthView,
} from "~/types/research";
import { draftReport, draftSlots, formatClock, formatRemaining, synthEta } from "~/utils/researchDraft";
import { applyResearchEvent, initialResearchView } from "~/utils/researchEvents";

const NOW = Date.parse("2026-09-28T01:10:00Z");
const HEADINGS3 = ["효과 측정", "교사 인식", "정책 과제"];
const EV: Record<string, ReportEvidence> = {
  E1: {
    cnts_id: "C1", meta: { title: "논문 C1" },
    chunks: [{ chunk_id: "k1", text: "대목", page_start: 3, page_end: 3, score: 0.9 }],
  },
};

function job(over: Partial<ResearchJob> = {}): ResearchJob {
  return {
    job_id: "11111111-1111-4111-8111-111111111111",
    question: "AI 윤리 교육의 효과",
    status: "running",
    stage: "explored",
    plan: HEADINGS3,
    report: null,
    last_error: null,
    steps: [],
    ...over,
  };
}

function section(heading: string): ReportSection {
  return {
    heading,
    intro: `${heading} 도입 [E1]`,
    papers: [{ cnts_id: "C1", summary: "요약", evidence: ["E1"] }],
    future: [],
    evidence_chunks: { E1: ["k1"] },
    chunk_scores: { k1: 0.9 },
  };
}

function sec(idx: number, status: SynthSectionView["status"], over: Partial<SynthSectionView> = {}): SynthSectionView {
  return { idx, status, subqIdx: idx, heading: null, startedAt: null, durationMs: null, section: null, ...over };
}

function viewWith(synth: Partial<SynthView>, over: Partial<ResearchView> = {}): ResearchView {
  return {
    ...initialResearchView(job()),
    ...over,
    synth: { seq: 3, status: "running", total: 0, sections: [], headings: [], evidence: {}, retiredSeq: null, ...synth },
  };
}

// 워커가 보내는 started_at 모양(UTC 오프셋 표기)으로 NOW 보다 ms 만큼 앞선 시각
function ago(ms: number): string {
  return new Date(NOW - ms).toISOString().replace("Z", "+00:00");
}

describe("draftSlots", () => {
  it("절 순서대로 끝남·작성 중·대기를 매기고, 내용을 받은 끝난 절에만 초안 위치를 준다", () => {
    const v = viewWith({
      total: 4,
      headings: [...HEADINGS3, "향후 방향"],
      sections: [
        sec(0, "done", { durationMs: 38000, section: section("효과 측정") }),
        sec(1, "failed", { durationMs: 61000, section: section("교사 인식") }),
        sec(2, "running", { startedAt: ago(12000) }),
      ],
    });
    expect(draftSlots(v)).toEqual([
      { idx: 0, heading: "효과 측정", status: "done", durationMs: 38000, startedAt: null, sectionIndex: 0 },
      { idx: 1, heading: "교사 인식", status: "failed", durationMs: 61000, startedAt: null, sectionIndex: 1 },
      { idx: 2, heading: "정책 과제", status: "running", durationMs: null, startedAt: ago(12000), sectionIndex: null },
      { idx: 3, heading: "향후 방향", status: "waiting", durationMs: null, startedAt: null, sectionIndex: null },
    ]);
  });

  it("제목은 절 제목 목록 → 이벤트의 제목 → 다듬은 절의 제목 → '절 N' 순으로 고르고 빈 제목은 건너뛴다", () => {
    const v = viewWith({
      total: 4,
      headings: ["효과 측정", "  "],
      sections: [
        sec(0, "done", { heading: "이벤트 제목", section: section("절 제목") }),
        sec(1, "done", { heading: "교사 인식", section: section("절 제목") }),
        sec(2, "done", { section: section("정책 과제") }),
      ],
    });
    expect(draftSlots(v).map((s) => s.heading)).toEqual(["효과 측정", "교사 인식", "정책 과제", "절 4"]);
  });

  it("total 을 모르면 제목 목록·받은 절 번호로 센다", () => {
    const v = viewWith({ total: 0, sections: [sec(0, "done"), sec(2, "running")] });
    expect(draftSlots(v).map((s) => [s.idx, s.status])).toEqual([[0, "done"], [1, "waiting"], [2, "running"]]);
    expect(draftSlots(viewWith({ total: 0, headings: HEADINGS3 }))).toHaveLength(3);
  });

  it("끝났어도 절 내용이 없으면(옛 워커) 초안 위치가 없다", () => {
    const v = viewWith({ total: 2, sections: [sec(0, "done"), sec(1, "done", { section: section("교사 인식") })] });
    expect(draftSlots(v).map((s) => s.sectionIndex)).toEqual([null, 0]);
  });

  // 멈춘 초안의 세 조건을 하나씩 — 하나만 빠져도 그 경우의 경과 시계가 멈추지 않는다
  it.each<[string, Partial<SynthView>, Partial<ResearchView>]>([
    ["잡이 끝났다(취소 직후 — 워커가 쓰던 절을 마저 쓰느라 종합 단계는 아직 열려 있다)", { status: "running" }, { status: "canceled" }],
    ["종합 단계가 failed 로 닫혔다(잡은 아직 running — 실패로 닫히는 중)", { status: "failed" }, {}],
    ["종합 단계가 done 으로 닫혔다(잡은 아직 running — 완료로 닫히는 중)", { status: "done" }, {}],
  ])("멈춘 초안에서는 작성 중이던 절을 대기로 본다 — %s", (_, synth, over) => {
    const v = viewWith(
      { ...synth, total: 2, sections: [sec(0, "done", { section: section("효과 측정") }), sec(1, "running", { startedAt: ago(5000) })] },
      over,
    );
    expect(draftSlots(v).map((s) => s.status)).toEqual(["done", "waiting"]);
    expect(synthEta(v, NOW).runningIdx).toBeNull();
  });
});

describe("draftReport", () => {
  it("끝난 절(내용 있음)이 없으면 null", () => {
    expect(draftReport(viewWith({ total: 2, sections: [sec(0, "running", { startedAt: ago(1000) })] }))).toBeNull();
    expect(draftReport(viewWith({ total: 2, sections: [sec(0, "done")] }))).toBeNull();
  });

  it("끝난 절을 절 순서대로 모아 보고서 모양으로 만든다 — 한계 없음, 근거는 합집합, stats 는 라이브 카운터", () => {
    const s0 = section("효과 측정");
    const s2 = section("정책 과제");
    const v = viewWith(
      {
        total: 3, headings: HEADINGS3, evidence: EV,
        sections: [sec(0, "done", { section: s0 }), sec(1, "running"), sec(2, "done", { section: s2 })],
      },
      { counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 2 } },
    );
    const d = draftReport(v)!;
    expect(d.report).toEqual({
      question: "AI 윤리 교육의 효과",
      range: null,
      sections: [s0, s2],
      evidence: EV,
      trail: [],
      limitations: [],
      stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 },
    });
    expect([d.done, d.total]).toEqual([2, 3]);
    expect(d.slots.map((s) => s.sectionIndex)).toEqual([0, null, 1]);
  });

  it("라이브 카운터가 하나라도 비면 stats 를 싣지 않는다", () => {
    const v = viewWith(
      { total: 1, sections: [sec(0, "done", { section: section("효과 측정") })] },
      { counters: { papersReviewed: null, evidenceAdopted: 3, rechecks: 0 } },
    );
    expect("stats" in draftReport(v)!.report).toBe(false);
  });

  it("synth 이벤트로 쌓은 화면에서 초안과 남은 시간을 만든다", () => {
    const s0 = section("효과 측정");
    const headings = ["효과 측정", "정책 과제"];
    const events: ResearchEvent[] = [
      { kind: "step", seq: 3, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running" },
      { kind: "synth", section_idx: 0, total: 2, status: "running", subq_idx: 0, heading: "효과 측정", headings, started_at: ago(40000) },
      {
        kind: "synth", section_idx: 0, total: 2, status: "done", subq_idx: 0, heading: "효과 측정", headings,
        duration_ms: 38000, section: s0, evidence: EV,
      },
    ];
    const v = events.reduce((view, e) => applyResearchEvent(view, e), initialResearchView(job()));
    const d = draftReport(v)!;
    expect(d.report.sections).toEqual([s0]);
    expect(d.report.evidence).toEqual(EV);
    expect(d.slots.map((s) => [s.heading, s.status])).toEqual([["효과 측정", "done"], ["정책 과제", "waiting"]]);
    expect(synthEta(v, NOW)).toEqual({ done: 1, total: 2, runningIdx: null, runningElapsedMs: null, remainingMs: 38000 });
  });

  it("보고서 작성부터 다시 시도하면 새 종합 단계가 열리기 전에도 이전 시도의 초안·남은 시간을 보이지 않는다", () => {
    const failed = initialResearchView(job({
      status: "failed", stage: "explored", last_error: "종합 실패",
      steps: [{
        seq: 4, kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "failed",
        result: {
          sections_total: 3, headings: HEADINGS3, evidence: EV, error: "종합 실패",
          sections: [
            { idx: 0, status: "done", duration_ms: 30000, section: section("효과 측정") },
            { idx: 1, status: "running", started_at: ago(5000) },
          ],
        },
      }],
    }));
    expect(draftReport(failed)?.done).toBe(1);
    const events: ResearchEvent[] = [
      { kind: "status", status: "queued", stage: "explored" },
      { kind: "status", status: "running", stage: "explored" },
    ];
    const running = events.reduce((view, e) => applyResearchEvent(view, e), failed);
    expect(draftReport(running)).toBeNull();
    expect(draftSlots(running)).toEqual([]);
    expect(synthEta(running, NOW)).toEqual({ done: 0, total: 0, runningIdx: null, runningElapsedMs: null, remainingMs: null });
  });
});

describe("synthEta", () => {
  const twoFinished = (running: Partial<SynthSectionView>) => viewWith({
    total: 4,
    sections: [
      sec(0, "done", { durationMs: 30000, section: section("가") }),
      sec(1, "failed", { durationMs: 50000, section: section("나") }),
      sec(2, "running", running),
    ],
  });

  it("끝난 절이 없으면 남은 시간을 모른다 — '첫 절을 쓰는 중'", () => {
    const eta = synthEta(viewWith({ total: 3, headings: HEADINGS3, sections: [sec(0, "running", { startedAt: ago(12000) })] }), NOW);
    expect(eta).toEqual({ done: 0, total: 3, runningIdx: 0, runningElapsedMs: 12000, remainingMs: null });
    expect(formatRemaining(eta.remainingMs, eta.done)).toBe("첫 절을 쓰는 중");
  });

  it("끝난 절(실패 포함)의 평균 × 대기 절 수 + 쓰는 중인 절의 (평균 − 경과)", () => {
    // 평균 40초 · 대기 1절 40초 + 쓰는 중 40−10=30초
    expect(synthEta(twoFinished({ startedAt: ago(10000) }), NOW))
      .toEqual({ done: 2, total: 4, runningIdx: 2, runningElapsedMs: 10000, remainingMs: 70000 });
  });

  it("쓰는 중인 절이 평균보다 오래 걸리면 그 절 몫은 0 으로 자른다", () => {
    const eta = synthEta(twoFinished({ startedAt: ago(55000) }), NOW);
    expect(eta.runningElapsedMs).toBe(55000);
    expect(eta.remainingMs).toBe(40000);
  });

  it("started_at 이 화면 시계보다 미래여도(시계 차) 경과는 0 이다", () => {
    const eta = synthEta(twoFinished({ startedAt: new Date(NOW + 5000).toISOString() }), NOW);
    expect(eta.runningElapsedMs).toBe(0);
    expect(eta.remainingMs).toBe(80000);
  });

  it("워커가 보내는 마이크로초 ISO 시각도 읽는다", () => {
    const eta = synthEta(twoFinished({ startedAt: "2026-09-28T01:09:48.123456+00:00" }), NOW);
    expect(eta.runningElapsedMs).toBe(11877);
  });

  it("모든 절이 끝났으면 남은 시간은 0 — '곧 끝납니다'", () => {
    const eta = synthEta(viewWith({
      total: 2,
      sections: [sec(0, "done", { durationMs: 30000, section: section("가") }), sec(1, "done", { durationMs: 20000, section: section("나") })],
    }), NOW);
    expect(eta).toEqual({ done: 2, total: 2, runningIdx: null, runningElapsedMs: null, remainingMs: 0 });
    expect(formatRemaining(eta.remainingMs, eta.done)).toBe("곧 끝납니다");
  });

  it("걸린 시간이 없는 끝난 절(옛 워커)만 있으면 남은 시간을 모른다 — 남은 시간 칸을 쓰지 않는다", () => {
    const eta = synthEta(viewWith({
      total: 2,
      sections: [sec(0, "done", { section: section("가") }), sec(1, "running", { startedAt: ago(3000) })],
    }), NOW);
    expect(eta.remainingMs).toBeNull();
    expect(formatRemaining(eta.remainingMs, eta.done)).toBeNull();
  });
});

describe("formatClock", () => {
  it("분:초 로 쓰고 초는 버림, 음수·NaN 은 0:00", () => {
    expect(formatClock(38_000)).toBe("0:38");
    expect(formatClock(38_900)).toBe("0:38");
    expect(formatClock(65_000)).toBe("1:05");
    expect(formatClock(723_000)).toBe("12:03");
    expect(formatClock(-500)).toBe("0:00");
    expect(formatClock(Number.NaN)).toBe("0:00");
  });
});

describe("formatRemaining", () => {
  it("첫 절 전·10초 미만·1분 미만·1분 이상(10초 단위 반올림)을 나눠 쓴다", () => {
    expect(formatRemaining(null, 0)).toBe("첫 절을 쓰는 중");
    expect(formatRemaining(40_000, 0)).toBe("첫 절을 쓰는 중");
    expect(formatRemaining(9_400, 2)).toBe("곧 끝납니다");
    expect(formatRemaining(40_000, 2)).toBe("약 40초 남음");
    expect(formatRemaining(59_700, 1)).toBe("약 1분 남음");
    expect(formatRemaining(90_000, 2)).toBe("약 1분 30초 남음");
    expect(formatRemaining(124_000, 2)).toBe("약 2분 남음");
  });

  it("끝난 절은 있는데 남은 시간을 모르면(옛 워커) 칸을 비운다", () => {
    expect(formatRemaining(null, 2)).toBeNull();
  });
});
