// frontend/tests/unit/paperDetail.test.ts
import { describe, expect, it } from "vitest";
import type { ReportEvidence, ResearchJob } from "~/types/research";
import { citeContext, summaryQuestion, withRo } from "~/utils/paperDetail";

function chunk(id: string, page: number) {
  return { chunk_id: id, text: `대목 ${id}`, page_start: page, page_end: page, score: 0.5 };
}

const evidence: ReportEvidence = {
  cnts_id: "CNTS-1",
  meta: { title: "AI 윤리 교육", personal_author: "김철수; 이영희", pub_date: "2019-03" },
  // 쪽은 0부터 센다 — 0 은 쪽 정보 없음(citations.pdfPage)
  chunks: [chunk("c1", 7), chunk("c2", 0), chunk("c3", 2)],
};

function job(over: Partial<Pick<ResearchJob, "question" | "report">> = {}): Pick<ResearchJob, "question" | "report"> {
  return {
    question: "AI 윤리 교육의 효과",
    report: {
      question: "AI 윤리 교육의 효과는?",
      range: null,
      sections: [],
      evidence: { E3: evidence },
      trail: [],
      limitations: [],
    },
    ...over,
  };
}

describe("citeContext", () => {
  it("보고서 질문·인용 표기와 쪽 순 인용 대목을 만든다 — 쪽 정보가 없는 대목은 빼지 않고 뒤에 둔다", () => {
    expect(citeContext(job(), "E3", "CNTS-1")).toEqual({
      question: "AI 윤리 교육의 효과는?",
      label: "김 2019",
      chunks: [chunk("c3", 2), chunk("c1", 7), chunk("c2", 0)],
    });
  });

  it("근거 번호가 없거나 다른 논문의 것이거나 보고서가 아직 없으면 배너를 내지 않는다", () => {
    expect(citeContext(job(), null, "CNTS-1")).toBeNull();
    expect(citeContext(job(), "E9", "CNTS-1")).toBeNull();
    expect(citeContext(job(), "E3", "CNTS-2")).toBeNull();
    expect(citeContext(job({ report: null }), "E3", "CNTS-1")).toBeNull();
  });
});

describe("summaryQuestion", () => {
  it("검색에서 왔으면 결과의 검색어, 보고서에서 왔으면 보고서 질문", () => {
    expect(summaryQuestion({ kind: "search", h: null, q: "딥러닝" }, null)).toBe("딥러닝");
    expect(summaryQuestion({ kind: "research", job: "j", e: "E3" }, job())).toBe("AI 윤리 교육의 효과는?");
  });

  it("보고서가 아직 없으면 잡 질문, 잡을 못 읽었거나 출처가 없으면 빈 문자열", () => {
    expect(summaryQuestion({ kind: "research", job: "j", e: null }, job({ report: null }))).toBe("AI 윤리 교육의 효과");
    expect(summaryQuestion({ kind: "research", job: "j", e: null }, null)).toBe("");
    expect(summaryQuestion({ kind: "none" }, job())).toBe("");
  });
});

describe("withRo", () => {
  it("받침(ㄹ 제외)이 있으면 '으로', 없으면 '로' — 숫자는 읽는 소리로 가린다", () => {
    expect(withRo("김 2019")).toBe("김 2019로");
    expect(withRo("김 2020")).toBe("김 2020으로");
    expect(withRo("이 2016")).toBe("이 2016으로");
    expect(withRo("박 2023")).toBe("박 2023으로");
    expect(withRo("E7")).toBe("E7로");
    expect(withRo("김")).toBe("김으로");
    expect(withRo("서울")).toBe("서울로");
    expect(withRo("Smith")).toBe("Smith로");
  });
});
