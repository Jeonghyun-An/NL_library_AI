// frontend/tests/unit/researchProgress.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { ResearchEvent, ResearchStepRow, ResearchView, RoundView, StepStatus, SubqView, Verdict } from "~/types/research";
import type { DraftSlot, DraftSlotStatus, SynthEta } from "~/utils/researchDraft";
import { applyResearchEvent, initialResearchView, researchPhase } from "~/utils/researchEvents";
import {
  DEFAULT_MAX_RECHECK,
  EXPLORE_WEIGHT,
  PROGRESS_STAGES,
  ROUND_HALF_LIFE_MS,
  SYNTH_WEIGHT,
  activeRoundKey,
  exploreFraction,
  maxRoundsOf,
  overallFraction,
  progressBarView,
  progressStage,
  progressStages,
  showsProgressBar,
  type ProgressInput,
} from "~/utils/researchProgress";
import { RUNNING_CAP, barFraction } from "~/utils/synthCard";

function round(n: number, over: Partial<RoundView> = {}): RoundView {
  return {
    round: n, query: `질의 ${n}`, foundChunks: 10, newPapers: 3, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [], ...over,
  };
}

function subq(idx: number, status: StepStatus, rounds: RoundView[] = [], title = `하위질문 ${idx + 1}`): SubqView {
  return {
    idx, title, seq: idx + 1, status, rounds,
    verdict: null, note: "", adopted: null, parseFailed: false, error: null,
  };
}

function eta(over: Partial<SynthEta> = {}): SynthEta {
  return { done: 0, total: 0, runningIdx: null, runningElapsedMs: null, remainingMs: null, ...over };
}

function slot(idx: number, heading: string, status: DraftSlotStatus = "waiting"): DraftSlot {
  return { idx, heading, status, durationMs: null, startedAt: null, sectionIndex: null };
}

function input(over: Partial<ProgressInput> = {}): ProgressInput {
  return {
    phase: "exploring", subqs: [], maxRounds: 4, roundElapsedMs: null, eta: eta(), slots: [], queueNote: null, ...over,
  };
}

// 점검이 끝나고 다음 회차로 재검색하는 회차
const rechecked = (n: number) => round(n, { verdict: "insufficient", nextQuery: `다음 검색어 ${n}` });

describe("progressStage·progressStages", () => {
  it("계획·승인 대기·대기열은 계획, 탐색은 근거 수집, 종합은 보고서 작성, 완료는 완료, 실패·취소는 null", () => {
    expect(progressStage("planning")).toBe("plan");
    expect(progressStage("awaiting")).toBe("plan");
    expect(progressStage("queued")).toBe("plan");
    expect(progressStage("exploring")).toBe("collect");
    expect(progressStage("synthesizing")).toBe("write");
    expect(progressStage("completed")).toBe("done");
    expect(progressStage("failed")).toBeNull();
    expect(progressStage("canceled")).toBeNull();
  });

  it("지금 단계만 current 이고 앞 단계는 done, 뒤 단계는 todo", () => {
    expect(PROGRESS_STAGES.map((s) => s.label)).toEqual(["계획", "근거 수집", "보고서 작성", "완료"]);
    expect(progressStages("collect")).toEqual([
      { key: "plan", label: "계획", state: "done" },
      { key: "collect", label: "근거 수집", state: "current" },
      { key: "write", label: "보고서 작성", state: "todo" },
      { key: "done", label: "완료", state: "todo" },
    ]);
    expect(progressStages("plan").map((s) => s.state)).toEqual(["current", "todo", "todo", "todo"]);
    expect(progressStages("write").map((s) => s.state)).toEqual(["done", "done", "current", "todo"]);
  });
});

describe("maxRoundsOf", () => {
  it("max_recheck + 1 회차, 값이 없거나 범위 밖이면 기본 3 + 1", () => {
    expect(DEFAULT_MAX_RECHECK).toBe(3);
    expect(maxRoundsOf({ max_recheck: 2 })).toBe(3);
    expect(maxRoundsOf({ max_recheck: 0 })).toBe(1);
    expect(maxRoundsOf({ max_recheck: 10 })).toBe(11);
    expect(maxRoundsOf({})).toBe(4);
    expect(maxRoundsOf({ max_recheck: 11 })).toBe(4);
    expect(maxRoundsOf({ max_recheck: -1 })).toBe(4);
    expect(maxRoundsOf({ max_recheck: 1.5 })).toBe(4);
  });
});

describe("exploreFraction", () => {
  it("끝난·실패한 하위질문은 1, 대기는 0 으로 센다", () => {
    expect(exploreFraction([subq(0, "done"), subq(1, "failed"), subq(2, "pending"), subq(3, "pending")], 4, null)).toBe(0.5);
    expect(exploreFraction([subq(0, "done")], 4, null)).toBe(1);
  });

  it("도는 하위질문은 점검이 끝난 회차 ÷ 최대 회차 몫이다", () => {
    // 1회차 점검이 끝나 재검색을 기다린다(다음 회차의 검색 이벤트 전) — 열린 회차가 없어 다가감도 없다
    expect(exploreFraction([subq(0, "running", [rechecked(1)]), subq(1, "pending")], 4, 30_000)).toBe(0.125);
    expect(exploreFraction([subq(0, "running", [rechecked(1), rechecked(2)])], 4, null)).toBe(0.5);
    // 충분 판정으로 끝나기 직전(단계 닫기 전)도 점검이 끝난 회차만큼이다
    expect(exploreFraction([subq(0, "running", [round(1, { verdict: "sufficient" })])], 4, null)).toBe(0.25);
    // 최대 회차가 2 면 같은 1회차가 절반이다
    expect(exploreFraction([subq(0, "running", [rechecked(1)])], 2, null)).toBe(0.5);
  });

  it("검색만 끝난 회차는 경과 시간으로 다가가되 회차 한 칸의 0.9 를 넘지 않는다", () => {
    const open = [subq(0, "running", [round(1)])];
    expect(exploreFraction(open, 4, null)).toBe(0);
    expect(exploreFraction(open, 4, 0)).toBe(0);
    // 반감기 하나가 지나면 한 칸(1/4)의 0.9 × 1/2
    expect(exploreFraction(open, 4, ROUND_HALF_LIFE_MS)).toBeCloseTo((RUNNING_CAP * 0.5) / 4, 10);
    // 회차가 아직 없는(첫 검색 전) 하위질문도 열린 회차로 다가간다
    expect(exploreFraction([subq(0, "running")], 4, ROUND_HALF_LIFE_MS)).toBeCloseTo((RUNNING_CAP * 0.5) / 4, 10);
    // 아무리 오래 기다려도 한 칸의 0.9 를 넘지 않는다
    expect(exploreFraction(open, 4, 600_000)).toBeLessThanOrEqual(RUNNING_CAP / 4);
    // 점검이 끝난 3회차 + 열린 4회차는 하위질문 몫 상한 0.9 에서 멈춘다
    const last = [subq(0, "running", [rechecked(1), rechecked(2), rechecked(3), round(4)])];
    expect(exploreFraction(last, 4, 600_000)).toBe(RUNNING_CAP);
  });

  it("하위질문이 없으면 0", () => {
    expect(exploreFraction([], 4, 5_000)).toBe(0);
  });
});

describe("overallFraction", () => {
  it("탐색 구간은 111, 작성 구간은 91 의 몫이다 — 탐색을 마치면 111/202", () => {
    expect(EXPLORE_WEIGHT).toBe(111);
    expect(SYNTH_WEIGHT).toBe(91);
    expect(overallFraction("collect", 0, 0)).toBe(0);
    expect(overallFraction("collect", 0.5, 0)).toBeCloseTo(55.5 / 202, 10);
    expect(overallFraction("collect", 1, 0)).toBeCloseTo(111 / 202, 10);
    // 탐색 중에는 작성 비율을 싣지 않는다
    expect(overallFraction("collect", 1, 0.8)).toBeCloseTo(111 / 202, 10);
  });

  it("작성 중에는 barFraction 을 작성 구간에 싣고 1 을 넘지 않는다", () => {
    // 작성이 시작되면 탐색 구간은 다 찬 것으로 본다 — 막대가 뒤로 가지 않는다
    expect(overallFraction("write", 0.3, 0)).toBeCloseTo(111 / 202, 10);
    expect(overallFraction("write", 1, 0.5)).toBeCloseTo((111 + 45.5) / 202, 10);
    const e = eta({ done: 2, total: 4, runningIdx: 2, runningElapsedMs: 10_000, remainingMs: 30_000 });
    expect(overallFraction("write", 1, barFraction(e))).toBeCloseTo((111 + 91 * barFraction(e)) / 202, 10);
    expect(overallFraction("write", 1, 1)).toBe(1);
    expect(overallFraction("write", 1, 1.4)).toBe(1);
  });
});

describe("progressBarView", () => {
  it("끝난 잡(완료·실패·취소)은 그리지 않는다", () => {
    for (const phase of ["completed", "failed", "canceled"] as const) {
      expect(progressBarView(input({ phase }))).toBeNull();
    }
  });

  it("계획 중·승인 대기·대기열은 퍼센트 없이 단계 글줄만 — 대기열은 순번 문구를 잇는다", () => {
    expect(progressBarView(input({ phase: "planning" }))).toEqual({
      stages: progressStages("plan"),
      line: "연구 계획을 세우는 중",
      percent: null,
      fraction: 0,
      running: false,
      valueText: "연구 계획을 세우는 중",
    });
    expect(progressBarView(input({ phase: "awaiting" }))?.line).toBe("계획 확인 대기 · 승인하면 근거 수집을 시작합니다");
    expect(progressBarView(input({ phase: "queued", queueNote: "앞에 2건 · 약 25분" }))?.line).toBe("대기열 · 앞에 2건 · 약 25분");
    const queued = progressBarView(input({ phase: "queued" }));
    expect(queued?.line).toBe("대기열 · 앞선 연구가 끝나면 시작합니다");
    expect(queued?.percent).toBeNull();
  });

  it("탐색 중 글줄은 '근거 수집 중 · 하위질문 k/n — 「하위질문」'", () => {
    const subqs = [
      subq(0, "done", [], "노인 우울과 가족 지지"),
      subq(1, "done", [], "지역사회 지지의 효과"),
      subq(2, "running", [round(1)], "사회적 지지 척도 비교"),
      subq(3, "pending"),
      subq(4, "pending"),
      subq(5, "pending"),
    ];
    const v = progressBarView(input({ subqs }))!;
    expect(v.line).toBe("근거 수집 중 · 하위질문 3/6 — 「사회적 지지 척도 비교」");
    expect(v.stages.find((s) => s.state === "current")?.key).toBe("collect");
    expect(v.valueText).toBe(`${v.line} · ${v.percent}%`);
    expect(progressBarView(input({ subqs: [] }))!.line).toBe("근거 수집을 시작하는 중");
  });

  it("도는 하위질문이 없으면(하위질문 사이) 다음 대기 하위질문 번호를 쓴다", () => {
    const between = [subq(0, "done", [], "가"), subq(1, "pending", [], "나"), subq(2, "pending", [], "다")];
    expect(progressBarView(input({ subqs: between }))!.line).toBe("근거 수집 중 · 하위질문 2/3 — 「나」");
    // 모두 끝났고 종합 단계 행이 아직 없으면 마지막 하위질문
    const ended = [subq(0, "done", [], "가"), subq(1, "failed", [], "나")];
    expect(progressBarView(input({ subqs: ended }))!.line).toBe("근거 수집 중 · 하위질문 2/2 — 「나」");
  });

  it("작성 중 글줄은 '보고서 작성 중 · i/n절 — 「절 제목」'", () => {
    const slots = [
      slot(0, "가족 지지", "done"), slot(1, "지역사회 지지", "done"), slot(2, "척도 비교", "running"),
      slot(3, "정책 함의"), slot(4, "연구 공백"), slot(5, "종합"),
    ];
    const v = progressBarView(input({
      phase: "synthesizing", slots, eta: eta({ done: 2, total: 6, runningIdx: 2, runningElapsedMs: 5_000, remainingMs: 120_000 }),
    }))!;
    expect(v.line).toBe("보고서 작성 중 · 3/6절 — 「척도 비교」");
    expect(v.stages.map((s) => s.state)).toEqual(["done", "done", "current", "todo"]);
    // 앞 절이 끝나고 다음 절이 아직 시작되지 않았으면 다음 절
    const gap = progressBarView(input({ phase: "synthesizing", slots, eta: eta({ done: 3, total: 6 }) }))!;
    expect(gap.line).toBe("보고서 작성 중 · 4/6절 — 「정책 함의」");
  });

  it("절 수를 모르면 준비 중, 모든 절이 끝나면 마무리 중", () => {
    expect(progressBarView(input({ phase: "synthesizing", eta: eta({ total: 0 }) }))!.line).toBe("보고서 작성을 준비하는 중");
    const end = progressBarView(input({ phase: "synthesizing", eta: eta({ done: 6, total: 6, remainingMs: 0 }) }))!;
    expect(end.line).toBe("보고서를 마무리하는 중");
    expect(end.percent).toBe(100);
  });

  it("퍼센트는 내림 정수이고 깜빡임(running)은 도는 것이 있을 때만 켠다", () => {
    // 탐색을 마친 순간 = 111/202 = 54.95…% → 54
    const start = progressBarView(input({ phase: "synthesizing", eta: eta({ total: 6 }) }))!;
    expect(start.fraction).toBeCloseTo(111 / 202, 10);
    expect(start.percent).toBe(54);
    expect(start.running).toBe(false);
    expect(progressBarView(input({ phase: "synthesizing", eta: eta({ total: 6, runningIdx: 0, runningElapsedMs: 1_000 }) }))!.running)
      .toBe(true);
    const exploring = progressBarView(input({ subqs: [subq(0, "running"), subq(1, "pending")] }))!;
    expect(exploring.running).toBe(true);
    expect(exploring.percent).toBe(0);
    // 2개 중 1개 끝 = 탐색 비율 0.5 → 55.5/202 = 27.47…% → 27
    const idle = progressBarView(input({ subqs: [subq(0, "done"), subq(1, "pending")] }))!;
    expect(idle.running).toBe(false);
    expect(idle.percent).toBe(27);
  });
});

describe("탐색부터 다시 도는 재시도(stage=planned)", () => {
  // 재시도는 idx 0 부터 새 seq 로 행을 쌓고, 이번 시도가 아직 닿지 않은 하위질문에는 이전 시도의 행(done·failed)이
  // 그대로 남는다(researchEvents stopPoint 와 같은 규칙). 1차 시도(seq 1~3): 하위질문 0·1 을 마치고 2 에서 시간 상한에 걸려 실패했다
  const FIRST_TRY = [subq(0, "done"), subq(1, "done"), subq(2, "failed")];
  // 이번 시도가 연 행 — 이전 시도의 행보다 seq 가 크다
  const again = (sq: SubqView, seq: number): SubqView => ({ ...sq, seq });

  it("이번 시도가 아직 닿지 않은 하위질문은 이전 시도에서 끝났어도 대기(0)로 센다", () => {
    const opened = [again(subq(0, "running"), 4), ...FIRST_TRY.slice(1)];
    expect(exploreFraction(opened, 4, null)).toBe(0);
    expect(exploreFraction(opened, 4, ROUND_HALF_LIFE_MS)).toBeCloseTo((RUNNING_CAP * 0.5) / 4 / 3, 10);
    expect(exploreFraction([again(subq(0, "done"), 4), ...FIRST_TRY.slice(1)], 4, null)).toBeCloseTo(1 / 3, 10);
    // 이번 시도가 연 행끼리는 끝남·실패를 그대로 1 로 센다
    expect(exploreFraction([again(subq(0, "done"), 4), again(subq(1, "failed"), 5), FIRST_TRY[2]!], 4, null))
      .toBeCloseTo(2 / 3, 10);
  });

  it("글줄·빛 흐름·회차 열쇠도 이전 시도의 행을 대기로 본다", () => {
    // 하위질문 사이 — 이번 시도는 하위질문 0 만 마쳤다. 다음에 돌 것은 2/6 이다(4/6 이 아니다)
    const between = [
      again(subq(0, "done", [], "가"), 7), subq(1, "done", [], "나"), subq(2, "failed", [], "다"),
      subq(3, "pending"), subq(4, "pending"), subq(5, "pending"),
    ];
    const v = progressBarView(input({ subqs: between }))!;
    expect(v.line).toBe("근거 수집 중 · 하위질문 2/6 — 「나」");
    // 탐색 비율 1/6 → 111/6/202 = 9.15…% → 9
    expect(v.percent).toBe(9);
    // 이전 시도에 running 으로 남은 행은 도는 하위질문이 아니다
    const stale = [again(subq(0, "done", [], "가"), 4), subq(1, "running", [round(1)], "나"), subq(2, "pending", [], "다")];
    const s = progressBarView(input({ subqs: stale }))!;
    expect(s.line).toBe("근거 수집 중 · 하위질문 2/3 — 「나」");
    expect(s.running).toBe(false);
    expect(s.fraction).toBeCloseTo((111 / 3) / 202, 10);
    expect(activeRoundKey(stale)).toBeNull();
  });

  it("실패한 잡을 다시 시도해 라이브로 볼 때 하위질문 0 의 새 행이 열린 뒤로 막대가 뒤로 가지 않는다", () => {
    const PLAN3 = ["효과 측정", "교사 인식", "정책 과제"];
    const row = (seq: number, idx: number, status: StepStatus, result: ResearchStepRow["result"] = {}): ResearchStepRow => ({
      seq, kind: "search", subq_idx: idx, title: PLAN3[idx]!, detail: null, status, result,
    });
    const failed = initialResearchView({
      job_id: "11111111-1111-4111-8111-111111111111",
      question: "AI 윤리 교육의 효과",
      status: "failed",
      stage: "planned",
      plan: PLAN3,
      report: null,
      last_error: "시간 상한 초과",
      steps: [
        { seq: 0, kind: "plan", subq_idx: null, title: "연구 계획 수립", detail: null, status: "done", result: { subquestions: PLAN3 } },
        row(1, 0, "done"), row(2, 1, "done"), row(3, 2, "failed", { error: "시간 상한 초과" }),
      ],
      params: {},
      created_at: "2026-09-26T01:00:00Z",
      started_at: "2026-09-26T01:01:00Z",
      finished_at: "2026-09-26T01:20:00Z",
    });
    const opened = (seq: number, idx: number): ResearchEvent =>
      ({ kind: "step", seq, step_kind: "search", subq_idx: idx, title: PLAN3[idx]!, status: "running" });
    const closed = (seq: number, idx: number): ResearchEvent =>
      ({ kind: "step", seq, step_kind: "search", subq_idx: idx, title: PLAN3[idx]!, status: "done", result: {} });
    const searched = (idx: number, n: number): ResearchEvent => ({ kind: "search", subq_idx: idx, query: `질의 ${n}`, found: 10, round: n });
    const judged = (idx: number, n: number, verdict: Verdict): ResearchEvent => ({
      kind: "critique", subq_idx: idx, verdict, note: "", adopted: 2, parse_failed: false, capped: 0, round: n,
      next_query: verdict === "insufficient" ? `다음 질의 ${n}` : null, will_recheck: verdict === "insufficient",
    });
    const events: ResearchEvent[] = [
      { kind: "status", status: "queued", stage: "planned" },
      { kind: "status", status: "running", stage: "planned" },
      opened(4, 0), searched(0, 1), judged(0, 1, "sufficient"), closed(4, 0),
      opened(5, 1), searched(1, 1), judged(1, 1, "insufficient"), searched(1, 2), judged(1, 2, "sufficient"), closed(5, 1),
      opened(6, 2), searched(2, 1), judged(2, 1, "sufficient"), closed(6, 2),
    ];
    const views = events.reduce<ResearchView[]>((acc, e) => [...acc, applyResearchEvent(acc[acc.length - 1] ?? failed, e)], []);
    // 워커가 running 을 알린 뒤 하위질문 0 의 새 행을 열기 전(수록 범위 조회 한 번 사이)에는 이전 시도의 행뿐이라
    // 1차 시도가 탐색을 막 마친 때와 모양이 같다 — 그 틈은 하위질문만으로 가를 수 없어 새 행이 열린 뒤부터 본다
    const from = views.findIndex((v) => v.subqs[0]!.seq === 4);
    expect(from).toBe(2);
    const fractions = views.slice(from).map((v) =>
      progressBarView(input({ phase: researchPhase(v), subqs: v.subqs, roundElapsedMs: ROUND_HALF_LIFE_MS }))!.fraction);
    // 새 행이 막 열린 때는 이번 시도의 하위질문 0 이 다가간 만큼뿐이다(이전 시도의 끝남·실패를 세지 않는다)
    expect(fractions[0]).toBeCloseTo((((RUNNING_CAP * 0.5) / 4 / 3) * 111) / 202, 10);
    fractions.slice(1).forEach((f, i) => expect(f).toBeGreaterThanOrEqual(fractions[i]!));
    expect(fractions[fractions.length - 1]).toBeCloseTo(111 / 202, 10);
  });
});

describe("showsProgressBar", () => {
  it("끝나지 않은 잡에만 그리고 단계 화면(stepMode)에는 그리지 않는다", () => {
    for (const phase of ["planning", "awaiting", "queued", "exploring", "synthesizing"] as const) {
      expect(showsProgressBar(phase, false)).toBe(true);
    }
    for (const phase of ["completed", "failed", "canceled"] as const) {
      expect(showsProgressBar(phase, false)).toBe(false);
    }
    expect(showsProgressBar(null, false)).toBe(false);
    // 단계 화면은 끝난 잡의 이어간 연구에만 선다 — WorkStepper·06e 자동 보고서의 큰 막대와 한 화면에 서지 않는다
    expect(showsProgressBar("completed", true)).toBe(false);
    expect(showsProgressBar("synthesizing", true)).toBe(false);
  });
});

describe("activeRoundKey", () => {
  it("도는 하위질문의 회차가 늘거나 판정이 날 때만 바뀌고, 도는 하위질문이 없으면 null", () => {
    expect(activeRoundKey([subq(0, "done"), subq(1, "pending")])).toBeNull();
    const started = activeRoundKey([subq(0, "done"), subq(1, "running")]);
    const searched = activeRoundKey([subq(0, "done"), subq(1, "running", [round(1)])]);
    // 첫 검색이 와도 같은 열린 회차다 — 다가감이 0 으로 돌아가지 않는다
    expect(searched).toBe(started);
    // 같은 회차에 값만 바뀌어도 그대로다
    expect(activeRoundKey([subq(0, "done"), subq(1, "running", [round(1, { foundChunks: 25 })])])).toBe(searched);
    const judged = activeRoundKey([subq(0, "done"), subq(1, "running", [rechecked(1)])]);
    expect(judged).not.toBe(searched);
    const next = activeRoundKey([subq(0, "done"), subq(1, "running", [rechecked(1), round(2)])]);
    expect(next).not.toBe(judged);
    expect(next).not.toBe(searched);
  });
});

// research.css 의 규칙 — 선택자(쉼표로 나눔)·감싼 @규칙(@media 등)·선언. 이 파일은 CSS 중첩·중괄호가 든 글자를 쓰지 않는다
interface CssRule {
  at: string;
  selectors: string[];
  decls: Map<string, string>;
}

function cssRules(css: string): CssRule[] {
  const src = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const squash = (s: string) => s.replace(/\s+/g, " ").trim();
  const rules: CssRule[] = [];
  const heads: string[] = [];
  let buf = "";
  for (const ch of src) {
    if (ch === "{") {
      heads.push(squash(buf));
      buf = "";
    } else if (ch === "}") {
      const head = heads.pop() ?? "";
      if (!head.startsWith("@") && buf.trim()) {
        const decls = new Map<string, string>();
        for (const d of buf.split(";")) {
          const colon = d.indexOf(":");
          if (colon > 0) decls.set(d.slice(0, colon).trim(), squash(d.slice(colon + 1)));
        }
        rules.push({ at: heads.filter((h) => h.startsWith("@")).join(" "), selectors: head.split(",").map(squash), decls });
      }
      buf = "";
    } else {
      buf += ch;
    }
  }
  return rules;
}

// 고정 진행 막대는 문서(창) 스크롤 위에 sticky 로 붙는다 — 브라우저는 초점 이동·scrollIntoView·#조각 이동에서 sticky 막대를 모르므로
// 막대 높이를 문서 스크롤 칸(html)의 scroll-padding-top 으로 알려야 막대 밑에 가린 채 초점을 받는 요소가 없다(WCAG 2.2 2.4.11)
describe("고정 진행 영역의 문서 스크롤 여백(research.css)", () => {
  const rules = cssRules(readFileSync(fileURLToPath(new URL("../../assets/css/research.css", import.meta.url)), "utf8"));
  const declsOf = (selector: string, prop: string) =>
    rules.filter((r) => r.selectors.includes(selector) && r.decls.has(prop)).map((r) => ({ at: r.at, value: r.decls.get(prop) }));

  it("막대가 서 있으면 html 이 막대 영역 높이만큼 scroll-padding-top 을 둔다 — 화면 폭 조건마다 막대 높이와 같은 값", () => {
    const bar = declsOf(".rs-page.has-progressbar", "--rs-bar-h");
    expect(bar.length).toBeGreaterThan(0);
    expect(declsOf("html:has(.rs-page.has-progressbar)", "scroll-padding-top")).toEqual(bar);
  });

  it("막대 높이는 그 한 곳에만 — 절의 scroll-margin-top 에 다시 더하지 않는다(두 번 더하면 절 이동 오프셋이 두 배가 된다)", () => {
    const margins = rules.flatMap((r) => r.decls.get("scroll-margin-top") ?? []);
    expect(margins.length).toBeGreaterThan(0);
    for (const m of margins) expect(m).not.toMatch(/--rs-bar/);
  });
});
