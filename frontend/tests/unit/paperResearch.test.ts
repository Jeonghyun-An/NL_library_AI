// frontend/tests/unit/paperResearch.test.ts
import { describe, expect, it } from "vitest";
import { paperResearchQuestion, paperResearchUrl, readResearchDraft } from "~/utils/paperResearch";
import { questionProblem } from "~/utils/researchInput";

describe("paperResearchQuestion", () => {
  it("제목과 앞 키워드 세 개로 질문 초안을 만든다", () => {
    expect(paperResearchQuestion(" 청소년  SNS 이용과 우울 ", ["SNS", " 우울 ", "", "청소년", "패널"])).toBe(
      "「청소년 SNS 이용과 우울」에서 출발해, SNS·우울·청소년 관련 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?",
    );
  });

  it("키워드가 없으면 제목만으로 묻는다", () => {
    expect(paperResearchQuestion("공공도서관 이용 행태", [])).toBe(
      "「공공도서관 이용 행태」에서 출발해, 이 주제의 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?",
    );
  });

  it("제목이 없으면 초안을 만들지 않는다", () => {
    expect(paperResearchQuestion("  ", ["키워드"])).toBe("");
  });

  it("긴 제목·키워드는 잘라 서버 질문 한도 안에 둔다", () => {
    const q = paperResearchQuestion("가".repeat(400), ["나".repeat(100), "다".repeat(100), "라".repeat(100)]);
    expect(q).toContain(`「${"가".repeat(120)}…」`);
    expect(q).toContain(`${"나".repeat(30)}…·`);
    expect(questionProblem(q)).toBeNull();
  });
});

describe("paperResearchUrl · readResearchDraft", () => {
  it("주소에 실은 초안을 그대로 읽는다", () => {
    const q = "「제목 & 부제」에서 출발해, 이 주제의 선행 연구는?";
    const url = new URL(paperResearchUrl(q), "http://x");
    expect(url.pathname).toBe("/papers");
    expect(readResearchDraft(Object.fromEntries(url.searchParams))).toBe(q);
  });

  it("없거나 빈 값이면 null, 배열이면 첫 값", () => {
    expect(readResearchDraft({})).toBeNull();
    expect(readResearchDraft({ draft: "  " })).toBeNull();
    expect(readResearchDraft({ draft: [" 질문 ", "다른"] })).toBe("질문");
  });
});
