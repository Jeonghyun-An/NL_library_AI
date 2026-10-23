// frontend/tests/unit/summaryExcerpt.test.ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { SHORT_ABSTRACT_CHARS, SUMMARY_PAPER_LIMIT, joinExcerpt, pickSummaryExcerpt, summaryExcerpt } from "~/utils/summaryExcerpt";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8").replace(/\r\n/g, "\n");

// 결과까지 담은 국문 초록 — 짧은 초록 기준(SHORT_ABSTRACT_CHARS)보다 길다
const KOREAN_ABSTRACT =
  "본 연구는 노인의 사회적 지지와 우울의 관계를 분석하였다. ".repeat(12) + "분석 결과 사회적 지지는 우울과 유의한 부적 상관을 보였다.";
const LEGACY_SUMMARY = "## SUMMARY: 30개 연구 중 28개가 사회적 지지가 우울 감소에 효과적이라고 보고했다.\n\n**관련 연구자가 검색할 학술 키워드:** 노인, 우울";

describe("summaryExcerpt — 논문 검색 AI 요약에 싣는 발췌", () => {
  it("원문 초록(abstract)이 넉넉하면 그것만 앞뒤 공백을 걷어 보낸다 — 색인 요약이 있어도 초록이 먼저", () => {
    const book = { book_info: { abstract: `  ${KOREAN_ABSTRACT}\n`, summary: LEGACY_SUMMARY } };
    expect(KOREAN_ABSTRACT.length).toBeGreaterThanOrEqual(SHORT_ABSTRACT_CHARS);
    expect(summaryExcerpt(book)).toBe(KOREAN_ABSTRACT);
    expect(pickSummaryExcerpt(book.book_info)).toEqual({ abstract: KOREAN_ABSTRACT });
  });

  // 목적 한 문장뿐인 초록만 받은 요약은 결과를 지어내 출처를 달았다 — 색인 요약에 결과가 있으면 그것까지 읽게 한다
  it("초록이 짧으면(목적 한두 문장) 색인 요약 본문을 빈 줄 뒤에 덧붙인다", () => {
    const abstract = "This study examines the effect of social support on depression among older adults.";
    const book = { book_info: { abstract, summary: LEGACY_SUMMARY } };
    expect(pickSummaryExcerpt(book.book_info)).toEqual({
      abstract,
      summary: "30개 연구 중 28개가 사회적 지지가 우울 감소에 효과적이라고 보고했다.",
    });
    expect(summaryExcerpt(book)).toBe(`${abstract}\n\n30개 연구 중 28개가 사회적 지지가 우울 감소에 효과적이라고 보고했다.`);
    // 색인 요약이 없으면 짧은 초록 그대로
    expect(summaryExcerpt({ book_info: { abstract } })).toBe(abstract);
  });

  it("초록이 비었거나 공백뿐이면 색인 요약(summary)의 본문 — 앞머리 '## SUMMARY:' 와 끝의 학술 키워드 줄은 뺀다", () => {
    const summary = "## SUMMARY: 다문화가정 아동의 어휘 발달을 비교했다.\n\n**관련 연구자가 검색할 학술 키워드:** 다문화, 언어 발달, 어휘";
    expect(summaryExcerpt({ book_info: { abstract: "", summary } })).toBe("다문화가정 아동의 어휘 발달을 비교했다.");
    expect(summaryExcerpt({ book_info: { abstract: "   ", summary } })).toBe("다문화가정 아동의 어휘 발달을 비교했다.");
    expect(pickSummaryExcerpt({ summary })).toEqual({ summary: "다문화가정 아동의 어휘 발달을 비교했다." });
  });

  it("옛 꼴이 아닌 색인 요약은 그대로", () => {
    expect(summaryExcerpt({ book_info: { summary: "공공도서관 서비스 품질을 SERVQUAL 로 측정했다." } })).toBe(
      "공공도서관 서비스 품질을 SERVQUAL 로 측정했다.",
    );
  });

  it("둘 다 없으면 빈 글 — 서버는 '(초록 없음)'으로 두고 제목·저자만으로 요약한다", () => {
    expect(summaryExcerpt({ book_info: {} })).toBe("");
    expect(summaryExcerpt({ book_info: { abstract: "", summary: "" } })).toBe("");
    expect(summaryExcerpt({ book_info: { summary: "## SUMMARY:   " } })).toBe("");
    expect(summaryExcerpt({})).toBe("");
    expect(summaryExcerpt({ book_info: null })).toBe("");
    expect(pickSummaryExcerpt(undefined)).toBeNull();
    expect(joinExcerpt(null)).toBe("");
  });

  it("문자열이 아닌 값은 없는 것으로 본다", () => {
    expect(summaryExcerpt({ book_info: { abstract: 3, summary: ["x"] } })).toBe("");
    expect(summaryExcerpt({ book_info: { abstract: null, summary: "요약" } })).toBe("요약");
  });

  it("검색 결과의 chunks(가장 맞은 조각)는 읽지 않는다 — 참고문헌 목록 조각일 때가 있다", () => {
    const book = { book_info: {}, chunks: [{ text: "참고문헌 김철수(2010). 노인 우울 연구." }] };
    expect(summaryExcerpt(book)).toBe("");
  });

  // 국문 초록 뒤의 영문 초록은 같은 내용의 번역이다 — 서버가 자르는 길이를 먹어 국문 쪽 결론이 잘렸다
  describe("국문 초록 뒤에 붙은 영문 초록", () => {
    const english = "This study analyzed the relationship between social support and depression among older adults in Korea.";

    it.each([
      ["마크다운 머리", "\n\n##### ABSTRACT\n\n"],
      ["줄 머리 쌍점", "\nAbstract: "],
      ["굵은 글씨", "\n**Abstract**\n"],
      ["영문 초록", "\n영문 초록\n"],
    ])("국문이 넉넉하면 걷는다 — %s", (_, head) => {
      expect(summaryExcerpt({ book_info: { abstract: `${KOREAN_ABSTRACT}${head}${english}` } })).toBe(KOREAN_ABSTRACT);
    });

    it("국문 쪽이 짧으면 걷지 않는다 — 결과가 영문 쪽에만 있을 수 있다", () => {
      const abstract = `본 연구는 노인의 사회적 지지와 우울의 관계를 분석하였다.\n\nABSTRACT\n\n${english}`;
      expect(summaryExcerpt({ book_info: { abstract } })).toBe(abstract);
    });

    it("영문 초록만 있는 논문의 'Abstract' 줄은 경계로 읽지 않는다", () => {
      const abstract = `${english} `.repeat(5) + `\nAbstract\n${english}`;
      expect(summaryExcerpt({ book_info: { abstract } })).toBe(abstract.trim());
    });

    it("표지 뒤가 영문이 아니면(한글 본문이 이어지면) 걷지 않는다", () => {
      const abstract = `${KOREAN_ABSTRACT}\n초록\n${KOREAN_ABSTRACT}`;
      expect(summaryExcerpt({ book_info: { abstract } })).toBe(abstract);
      const korean = `${KOREAN_ABSTRACT}\nAbstract\n${KOREAN_ABSTRACT}`;
      expect(summaryExcerpt({ book_info: { abstract: korean } })).toBe(korean);
    });

    it("본문 속 'abstract' 낱말은 표지가 아니다", () => {
      const abstract = `${KOREAN_ABSTRACT} The abstract concept of support was ${english}`;
      expect(summaryExcerpt({ book_info: { abstract } })).toBe(abstract);
      const line = `${KOREAN_ABSTRACT}\nAbstraction of support: ${english}`;
      expect(summaryExcerpt({ book_info: { abstract: line } })).toBe(line);
    });
  });
});

describe("서버와 맞춘 값", () => {
  const server = read("../app/services/search/paper_summary.py");

  it("요약이 읽는 논문 수는 서버(_MAX_PAPERS)와 같은 5편", () => {
    expect(SUMMARY_PAPER_LIMIT).toBe(5);
    expect(server).toMatch(new RegExp(`^_MAX_PAPERS = ${SUMMARY_PAPER_LIMIT}\\b`, "m"));
  });
});

// e8f9c93(쪽 나누기) 뒤로 이 자리가 빈 글("")을 보내 요약이 제목·저자만 보고 연구 방법·결과를 지어냈다 — 화면은 Nuxt 없이
// 돌지 않아 소스 글로 고정한다(aiStreamConsumers.test 와 같은 방식)
describe("논문 검색 AI 요약의 발췌 배선 — pages/papers/index.vue streamAiSummary", () => {
  const src = read("pages/papers/index.vue");
  const body = src.match(/async function streamAiSummary\([\s\S]*?\n}\n/)?.[0] ?? "";

  it("앞 SUMMARY_PAPER_LIMIT 편마다 summaryExcerpt 로 고른 발췌를 best_chunk_text 에 싣는다", () => {
    expect(body).not.toBe("");
    expect(src).toMatch(/import \{ SUMMARY_PAPER_LIMIT, summaryExcerpt \} from "~\/utils\/summaryExcerpt";/);
    expect(body).toMatch(/const papers = books\.slice\(0, SUMMARY_PAPER_LIMIT\)\.map\(\(b\) => \(\{/);
    expect(body).toMatch(/best_chunk_text: summaryExcerpt\(b\),/);
    expect(body).not.toMatch(/best_chunk_text: ""/);
    expect(body).toMatch(/body: JSON\.stringify\(\{ query, papers \}\)/);
  });

  it("발췌가 읽는 필드(abstract·summary)를 넘겨받는 논문 모양에 둔다", () => {
    expect(src).toMatch(/type SummarySource = \{[\s\S]*?book_info\?: \{[^}]*\babstract\?: string;[^}]*\bsummary\?: string;?[^}]*\}/);
  });
});
