// frontend/tests/unit/summaryExcerpt.test.ts
import { describe, expect, it } from "vitest";
import { SUMMARY_PAPER_LIMIT, pickSummaryExcerpt, summaryExcerpt } from "~/utils/summaryExcerpt";

describe("summaryExcerpt — 논문 검색 AI 요약에 싣는 발췌", () => {
  it("원문 초록(abstract)이 있으면 그것을 앞뒤 공백만 걷어 보낸다 — 색인 요약이 있어도 초록이 먼저", () => {
    const book = { book_info: { abstract: "  본 연구는 노인의 사회적 지지와 우울의 관계를 분석하였다.\n", summary: "## SUMMARY: 색인 요약" } };
    expect(summaryExcerpt(book)).toBe("본 연구는 노인의 사회적 지지와 우울의 관계를 분석하였다.");
    expect(pickSummaryExcerpt(book.book_info)?.field).toBe("abstract");
  });

  it("영문 초록도 그대로 보낸다(요약은 한국어로 쓰라고 프롬프트가 정한다)", () => {
    expect(summaryExcerpt({ book_info: { abstract: "This study examines social support." } })).toBe("This study examines social support.");
  });

  it("초록이 비었거나 공백뿐이면 색인 요약(summary)의 본문 — 앞머리 '## SUMMARY:' 와 끝의 학술 키워드 줄은 뺀다", () => {
    const summary = "## SUMMARY: 다문화가정 아동의 어휘 발달을 비교했다.\n\n**관련 연구자가 검색할 학술 키워드:** 다문화, 언어 발달, 어휘";
    expect(summaryExcerpt({ book_info: { abstract: "", summary } })).toBe("다문화가정 아동의 어휘 발달을 비교했다.");
    expect(summaryExcerpt({ book_info: { abstract: "   ", summary } })).toBe("다문화가정 아동의 어휘 발달을 비교했다.");
    expect(pickSummaryExcerpt({ summary })?.field).toBe("summary");
  });

  it("옛 꼴이 아닌 색인 요약은 그대로", () => {
    expect(summaryExcerpt({ book_info: { summary: "공공도서관 서비스 품질을 SERVQUAL 로 측정했다." } })).toBe(
      "공공도서관 서비스 품질을 SERVQUAL 로 측정했다.",
    );
  });

  it("둘 다 없으면 빈 글 — 서버는 제목·저자만으로 요약한다", () => {
    expect(summaryExcerpt({ book_info: {} })).toBe("");
    expect(summaryExcerpt({ book_info: { abstract: "", summary: "" } })).toBe("");
    expect(summaryExcerpt({ book_info: { summary: "## SUMMARY:   " } })).toBe("");
    expect(summaryExcerpt({})).toBe("");
    expect(summaryExcerpt({ book_info: null })).toBe("");
    expect(pickSummaryExcerpt(undefined)).toBeNull();
  });

  it("문자열이 아닌 값은 없는 것으로 본다", () => {
    expect(summaryExcerpt({ book_info: { abstract: 3, summary: ["x"] } })).toBe("");
    expect(summaryExcerpt({ book_info: { abstract: null, summary: "요약" } })).toBe("요약");
  });

  it("검색 결과의 chunks(가장 맞은 조각)는 읽지 않는다 — 참고문헌 목록 조각일 때가 있다", () => {
    const book = { book_info: {}, chunks: [{ text: "참고문헌 김철수(2010). 노인 우울 연구." }] };
    expect(summaryExcerpt(book)).toBe("");
  });

  it("요약이 읽는 논문 수는 서버(_MAX_PAPERS)와 같은 5편", () => {
    expect(SUMMARY_PAPER_LIMIT).toBe(5);
  });
});
