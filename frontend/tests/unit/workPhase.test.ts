// frontend/tests/unit/workPhase.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchReport, ResearchView } from "~/types/research";
import {
  ONBOARDING_KEY,
  ONBOARDING_STEPS,
  WORK_STEPS,
  parseWorkStep,
  scopeLine,
  stepForPhase,
  stepLine,
  stepperItems,
  summaryBand,
  summaryLine,
  withStep,
} from "~/utils/workPhase";

function view(over: Partial<ResearchView> = {}): ResearchView {
  return {
    jobId: "11111111-1111-4111-8111-111111111111",
    question: "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
    status: "completed",
    stage: "synthesized",
    plan: [],
    params: {},
    report: null,
    lastError: null,
    createdAt: null,
    startedAt: null,
    finishedAt: null,
    steps: [],
    subqs: [],
    counters: { papersReviewed: 121, evidenceAdopted: 40, rechecks: 2, excluded: 9 },
    highlight: null,
    synth: { seq: null, status: null, total: 0, sections: [], headings: [], evidence: {}, retiredSeq: null },
    source: "rounds",
    queue: null,
    ...over,
  };
}

function report(over: Partial<ResearchReport> = {}): ResearchReport {
  const section = { heading: "절", intro: "", papers: [], future: [], evidence_chunks: {}, chunk_scores: {} };
  return {
    question: "q",
    range: { from: "1980", to: "2017", n_papers: 144748 },
    sections: [section, section, section],
    evidence: {},
    trail: [],
    limitations: [],
    stats: { papers_reviewed: 121, evidence_adopted: 48, rechecks: 2, excluded: 12 },
    ...over,
  };
}

describe("parseWorkStep", () => {
  it("topics·reading·proposal 만 단계로 읽고 앞뒤 공백·배열은 첫 값으로 맞춘다", () => {
    expect(WORK_STEPS).toEqual(["topics", "reading", "proposal"]);
    expect(parseWorkStep({ s: "topics" })).toBe("topics");
    expect(parseWorkStep({ s: " reading " })).toBe("reading");
    expect(parseWorkStep({ s: ["proposal", "topics"] })).toBe("proposal");
  });

  it("없거나 틀린 값은 null — 탐색·보고서 화면을 연다", () => {
    expect(parseWorkStep({})).toBeNull();
    expect(parseWorkStep({ s: "" })).toBeNull();
    expect(parseWorkStep({ s: "done" })).toBeNull();
    expect(parseWorkStep({ s: "grid" })).toBeNull();
    expect(parseWorkStep({ s: 3 })).toBeNull();
    expect(parseWorkStep({ s: null })).toBeNull();
  });
});

describe("stepForPhase·stepLine", () => {
  it("도달한 단계의 화면을 고르고 완료는 계획서 화면이다", () => {
    expect(stepForPhase("topics")).toBe("topics");
    expect(stepForPhase("reading")).toBe("reading");
    expect(stepForPhase("proposal")).toBe("proposal");
    expect(stepForPhase("done")).toBe("proposal");
  });

  it("진행 막대 옆 한 줄", () => {
    expect(stepLine("topics")).toBe("2/4 단계 · 주제 고르는 중");
    expect(stepLine("reading")).toBe("3/4 단계 · 읽기 목록 만드는 중");
    expect(stepLine("proposal")).toBe("4/4 단계 · 계획서 쓰는 중");
    expect(stepLine("done")).toBe("4/4 단계 · 완료");
  });
});

describe("stepperItems", () => {
  it("탐색은 늘 끝난 단계이고, 도달한 단계가 지금 단계, 그 뒤는 아직이다", () => {
    expect(stepperItems("reading", "reading")).toEqual([
      { key: "explore", label: "탐색", state: "done", clickable: true },
      { key: "topics", label: "주제", state: "done", clickable: true },
      { key: "reading", label: "읽기 목록", state: "current", clickable: false },
      { key: "proposal", label: "계획서", state: "todo", clickable: false },
    ]);
  });

  it("보고 있는 단계는 누를 수 없고, 앞 단계를 보는 중이면 지금 단계로 돌아가게 누를 수 있다", () => {
    const viewingTopics = stepperItems("reading", "topics");
    expect(viewingTopics.map((i) => i.clickable)).toEqual([true, false, true, false]);
    const viewingReport = stepperItems("topics", null);
    expect(viewingReport.map((i) => [i.state, i.clickable])).toEqual([
      ["done", false],
      ["current", true],
      ["todo", false],
      ["todo", false],
    ]);
  });

  it("완료면 네 단계가 모두 끝난 단계다", () => {
    expect(stepperItems("done", "proposal").map((i) => [i.state, i.clickable])).toEqual([
      ["done", true],
      ["done", true],
      ["done", true],
      ["done", false],
    ]);
  });
});

describe("withStep", () => {
  it("단계만 바꾸고 돌아갈 자리(at·y)는 떼며 다른 쿼리는 둔다", () => {
    expect(withStep({ at: "c-0-E1", y: "120", s: "topics", h: "x" }, "reading")).toEqual({ h: "x", s: "reading" });
    expect(withStep({}, "topics")).toEqual({ s: "topics" });
  });

  it("null 이면 ?s= 를 지워 탐색·보고서로 간다", () => {
    expect(withStep({ s: "proposal", at: "g-gap-p1" }, null)).toEqual({});
  });

  it("받은 쿼리를 고치지 않는다", () => {
    const query = { s: "topics", at: "r-C1" };
    withStep(query, "reading");
    expect(query).toEqual({ s: "topics", at: "r-C1" });
  });
});

describe("summaryBand·summaryLine", () => {
  it("최종 보고서의 절 수·통계를 쓴다(제외는 하위질문별 판단의 수라 '건')", () => {
    const band = summaryBand(view({ report: report() }));
    expect(band).toEqual({
      question: "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
      sections: 3,
      adopted: 48,
      excluded: 12,
    });
    expect(summaryLine(band)).toBe("절 3개 · 채택 48편 · 제외 12건");
  });

  it("통계가 없는 옛 보고서는 탐색 카운터를, 제외 수를 모르는 보고서는 제외 칸을 뺀다", () => {
    expect(summaryBand(view({ report: report({ stats: undefined }) }))).toMatchObject({ adopted: 40, excluded: 9 });
    const noExcluded = summaryBand(view({ report: report({ stats: { papers_reviewed: 50, evidence_adopted: 20, rechecks: 0 } }) }));
    expect(noExcluded).toMatchObject({ sections: 3, adopted: 20, excluded: null });
    expect(summaryLine(noExcluded)).toBe("절 3개 · 채택 20편");
  });

  it("보고서가 없고 카운터도 모르면 빈 줄이다", () => {
    const band = summaryBand(view({ counters: { papersReviewed: null, evidenceAdopted: null, rechecks: null, excluded: null } }));
    expect(band).toMatchObject({ sections: 0, adopted: null, excluded: null });
    expect(summaryLine(band)).toBe("");
  });
});

describe("scopeLine", () => {
  it("소장 적재분 수와 끝 연도로 고정 띠 문구를 만든다", () => {
    expect(scopeLine({ n_papers: 144748, from: "1980", to: "2017" })).toBe(
      "소장 KCI 적재분 144,748편(~2017) 기준 · 편수 추이는 동향이 아님",
    );
    expect(scopeLine({ n_papers: 900, from: null, to: "2017-12-31", at: "2026-10-06T00:00:00Z" })).toBe(
      "소장 KCI 적재분 900편(~2017) 기준 · 편수 추이는 동향이 아님",
    );
  });

  it("끝 연도를 모르면 괄호를 빼고, 범위가 없으면 null", () => {
    expect(scopeLine({ n_papers: 12, from: null, to: null })).toBe("소장 KCI 적재분 12편 기준 · 편수 추이는 동향이 아님");
    expect(scopeLine(null)).toBeNull();
    expect(scopeLine(undefined)).toBeNull();
    expect(scopeLine({ n_papers: 0, from: null, to: null })).toBeNull();
  });
});

describe("온보딩", () => {
  it("브라우저 저장 열쇠와 세 단계(주제·읽기 목록·계획서)의 설명·결정할 것", () => {
    expect(ONBOARDING_KEY).toBe("skx_work_onboarded");
    expect(ONBOARDING_STEPS.map((s) => s.title)).toEqual(["주제", "읽기 목록", "계획서"]);
    for (const s of ONBOARDING_STEPS) {
      expect(s.body.length).toBeGreaterThan(0);
      expect(s.decide.length).toBeGreaterThan(0);
    }
  });
});
