// frontend/tests/unit/researchReport.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchReport } from "~/types/research";
import { paperByline, rangeLabel, reportIntro } from "~/utils/researchReport";

function report(over: Partial<ResearchReport> = {}): ResearchReport {
  return {
    question: "q",
    range: { from: "2002", to: "2026", n_papers: 1234 },
    sections: [],
    evidence: {
      E1: { cnts_id: "C1", meta: {}, chunks: [] },
      E2: { cnts_id: "C2", meta: {}, chunks: [] },
    },
    trail: [
      { subquestion: "가", queries: ["가"], evidence_count: 1, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0 },
      { subquestion: "나", queries: ["나"], evidence_count: 1, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0 },
      { subquestion: "다", queries: ["다"], evidence_count: 0, verdict: "insufficient", note: "", parse_failed: false, failed: false, capped: 0 },
    ],
    limitations: [],
    ...over,
  };
}

describe("rangeLabel", () => {
  it("수록 범위를 연도와 편수로 쓴다", () => {
    expect(rangeLabel({ from: "2002", to: "2026", n_papers: 1234 })).toBe("2002~2026 논문 1,234편 기준");
    expect(rangeLabel({ from: "2019", to: "2019", n_papers: 3 })).toBe("2019년 논문 3편 기준");
    expect(rangeLabel({ from: null, to: null, n_papers: 3 })).toBe("논문 3편 기준");
  });

  it("범위를 모르면 쓰지 않는다", () => {
    expect(rangeLabel(null)).toBeNull();
    expect(rangeLabel({})).toBeNull();
  });
});

describe("reportIntro", () => {
  it("stats 가 있으면 검토·채택 수를 쓴다", () => {
    expect(reportIntro(report({ stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 } })))
      .toBe("하위질문 3개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다.");
  });

  it("보강 전 보고서는 근거 수만 쓴다", () => {
    expect(reportIntro(report())).toBe("하위질문 3개로 나눠 논문 2편을 근거로 삼았다.");
  });
});

describe("paperByline", () => {
  it("첫 저자와 연도, 여럿이면 외를 붙인다", () => {
    expect(paperByline({ personal_author: "김철수; 이영희", pub_date: "2019-03" })).toBe("김철수 외 (2019)");
    expect(paperByline({ personal_author: "김철수" })).toBe("김철수");
    expect(paperByline({ personal_author: "Smith, John", pub_date: "2021" })).toBe("Smith, John (2021)");
    expect(paperByline(undefined)).toBe("저자 미상");
  });
});
