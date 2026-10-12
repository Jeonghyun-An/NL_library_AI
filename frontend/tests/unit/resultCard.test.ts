// frontend/tests/unit/resultCard.test.ts
import { describe, expect, it } from "vitest";
import {
  CARD_KEYWORD_LIMIT,
  cardKeywords,
  cardMeta,
  formatPubLabel,
  formatVolIssue,
  normalizeName,
} from "~/utils/resultCard";

describe("cardKeywords — 카드 키워드 칩", () => {
  it("저자 키워드(extracted_keywords) 배열이 가장 먼저이고, 최대 3개에서 자른다(칩이 많아 정신없다는 의견)", () => {
    const info = { extracted_keywords: ["노인복지", "정서복지", "첨단기술", "감정적 고립", "고령화 사회", "복지 모델", "지속가능성", "커뮤니티"] };
    expect(cardKeywords(info)).toEqual(["노인복지", "정서복지", "첨단기술"]);
    expect(CARD_KEYWORD_LIMIT).toBe(3);
  });

  it("extracted_keywords 가 있으면 keyword·themes 는 보지 않는다(섞지 않는다)", () => {
    expect(cardKeywords({ extracted_keywords: ["A"], keyword: "B, C", themes: "D, E" })).toEqual(["A"]);
  });

  it("extracted_keywords 가 비면 keyword 문자열을 쉼표·세미콜론으로 나눈다", () => {
    expect(cardKeywords({ extracted_keywords: [], keyword: "스마트폰 중독, 사회적 고립감; 자아통제감" })).toEqual([
      "스마트폰 중독",
      "사회적 고립감",
      "자아통제감",
    ]);
  });

  it("그다음은 생성 주제어(themes), 그다음은 subject 이고, 먼저 비지 않은 하나만 쓴다", () => {
    expect(cardKeywords({ keyword: null, themes: "세태, 사회 변화, 신분제", subject: "조선후기 | 세태소설" })).toEqual([
      "세태",
      "사회 변화",
      "신분제",
    ]);
    expect(cardKeywords({ themes: "  ", keyword: null, subject: "조선후기 | 세태소설 | NOVELS" })).toEqual([
      "조선후기",
      "세태소설",
      "NOVELS",
    ]);
  });

  it("기관 보고서처럼 키워드가 모두 없으면 빈 배열이다(칩이 안 나온다)", () => {
    expect(cardKeywords({ keyword: null, extracted_keywords: [], themes: null, subject: null })).toEqual([]);
    expect(cardKeywords(null)).toEqual([]);
    expect(cardKeywords(undefined)).toEqual([]);
  });

  it("자기 키워드가 있으면 스트림이 준 키워드(fallback)는 쓰지 않고, 하나도 없을 때만 쓴다", () => {
    expect(cardKeywords({ themes: "자기" }, ["스트림1", "스트림2"])).toEqual(["자기"]);
    expect(cardKeywords({}, ["스트림1", "스트림2"])).toEqual(["스트림1", "스트림2"]);
    expect(cardKeywords(null, ["스트림1"])).toEqual(["스트림1"]);
  });

  it("앞의 # 와 공백을 떼고 빈 것·대소문자만 다른 중복을 뺀다", () => {
    expect(cardKeywords({ keyword: "#AI, ai, ,  #딥러닝 ,Ai" })).toEqual(["AI", "딥러닝"]);
    expect(cardKeywords({ extracted_keywords: ["Aged", " aged ", "", "Life"] })).toEqual(["Aged", "Life"]);
  });

  it("개수 한도를 바꿀 수 있고, fallback 에도 같은 한도를 건다", () => {
    expect(cardKeywords({ themes: "a,b,c" }, [], 2)).toEqual(["a", "b"]);
    expect(cardKeywords({}, ["a", "b", "c", "d", "e", "f"])).toEqual(["a", "b", "c"]);
  });
});

describe("formatPubLabel — 발행일 표기", () => {
  it("논문은 연월, 소장자료는 연도만", () => {
    expect(formatPubLabel("2024.03", "paper")).toBe("2024년 3월");
    expect(formatPubLabel("2024-11-05", "paper")).toBe("2024년 11월");
    expect(formatPubLabel("20240315", "paper")).toBe("2024년 3월");
    expect(formatPubLabel("19970301", "book")).toBe("1997년");
    expect(formatPubLabel("1997", "book")).toBe("1997년");
  });

  it("월을 못 읽으면 연도만 — 논문도 그렇다", () => {
    expect(formatPubLabel("2024", "paper")).toBe("2024년");
    expect(formatPubLabel("2024.13", "paper")).toBe("2024년");
    expect(formatPubLabel("2024.00", "paper")).toBe("2024년");
  });

  it("연도를 못 읽으면 빈 문자열", () => {
    expect(formatPubLabel("", "paper")).toBe("");
    expect(formatPubLabel(null, "book")).toBe("");
    expect(formatPubLabel(undefined, "book")).toBe("");
    expect(formatPubLabel("미상", "paper")).toBe("");
    expect(formatPubLabel("12", "paper")).toBe("");
  });
});

describe("formatVolIssue — 권호", () => {
  it("'V(N)' 은 'V권 N호'", () => {
    expect(formatVolIssue("11(3)")).toBe("11권 3호");
    expect(formatVolIssue("4(2)")).toBe("4권 2호");
    expect(formatVolIssue("24(10)")).toBe("24권 10호");
    expect(formatVolIssue(" 13 ( 4 ) ")).toBe("13권 4호");
  });

  it("권 없이 호만('-N')이면 'N호', 권만('V')이면 'V권'", () => {
    expect(formatVolIssue("-33")).toBe("33호");
    expect(formatVolIssue("-42")).toBe("42호");
    expect(formatVolIssue("- 5")).toBe("5호");
    expect(formatVolIssue("7")).toBe("7권");
  });

  it("비었거나 기호뿐이면 빈 문자열(생략)", () => {
    expect(formatVolIssue("")).toBe("");
    expect(formatVolIssue("  ")).toBe("");
    expect(formatVolIssue("-")).toBe("");
    expect(formatVolIssue(" - ")).toBe("");
    expect(formatVolIssue("—")).toBe("");
    expect(formatVolIssue(null)).toBe("");
    expect(formatVolIssue(undefined)).toBe("");
  });

  it("그 밖의 모양은 원문 그대로", () => {
    expect(formatVolIssue("특별호")).toBe("특별호");
    expect(formatVolIssue("11-3")).toBe("11-3");
    expect(formatVolIssue("제3권 2호")).toBe("제3권 2호");
    expect(formatVolIssue("11(특집)")).toBe("11(특집)");
  });
});

describe("normalizeName — 이름 비교용 정리", () => {
  it("공백·괄호·가운뎃점·대소문자 차이를 지운다", () => {
    expect(normalizeName("한국 도서관 협회")).toBe(normalizeName("한국도서관협회"));
    expect(normalizeName("(한국도서관협회)")).toBe(normalizeName("한국도서관협회"));
    expect(normalizeName("「한국도서관협회」")).toBe(normalizeName("한국도서관협회"));
    expect(normalizeName("KISTI ")).toBe(normalizeName("kisti"));
    expect(normalizeName("한국·도서관협회")).toBe(normalizeName("한국도서관협회"));
  });

  it("다른 이름은 다르고, 비면 빈 문자열이다", () => {
    expect(normalizeName("기획예산처")).not.toBe(normalizeName("재정경제부"));
    expect(normalizeName(null)).toBe("");
    expect(normalizeName("  ")).toBe("");
  });
});

describe("cardMeta — 저자 줄과 서지 줄", () => {
  it("논문: 연월 · 발행처 > 분야 · 인용수 N", () => {
    const meta = cardMeta(
      {
        personal_author: "강상순",
        corporate_author: "한국고소설학회",
        pub_date: "2021.06",
        series_title: "고전문학",
        kci_citations: 12,
      },
      "paper",
    );
    expect(meta.author).toBe("강상순");
    expect(meta.parts).toEqual([
      { text: "2021년 6월" },
      { text: "한국고소설학회" },
      { text: "고전문학", arrow: true },
      { text: "인용수 12" },
    ]);
  });

  it("논문: KCI 등재 구분은 칩이 아니라 서지 줄의 맨 끝 글자이고, 없으면 생략한다", () => {
    expect(cardMeta({ pub_date: "2021.06", kci_citations: 5, grade: "KCI 등재" }, "paper").parts).toEqual([
      { text: "2021년 6월" },
      { text: "인용수 5" },
      { text: "KCI 등재" },
    ]);
    expect(cardMeta({ kci_citations: 5, grade: "KCI 후보" }, "paper").parts.at(-1)).toEqual({ text: "KCI 후보" });
    expect(cardMeta({ kci_citations: 5, grade: "우수등재" }, "paper").parts.at(-1)).toEqual({ text: "우수등재" });
    expect(cardMeta({ kci_citations: 5, grade: " " }, "paper").parts).toEqual([{ text: "인용수 5" }]);
    expect(cardMeta({ kci_citations: 5 }, "paper").parts).toEqual([{ text: "인용수 5" }]);
  });

  it("소장자료는 등급을 서지 줄에 싣지 않는다", () => {
    expect(cardMeta({ publisher: "출판사", grade: "KCI 등재" }, "book").parts).toEqual([{ text: "출판사" }]);
  });

  it("논문: 인용수 0 도 보이고, 없는 조각은 건너뛴다", () => {
    const meta = cardMeta({ personal_author: "류준경", kci_citations: 0 }, "paper");
    expect(meta.parts).toEqual([{ text: "인용수 0" }]);
  });

  it("논문: 저자가 발행처(기관) 하나뿐이면 서지 줄에서 같은 말을 되풀이하지 않고 화살표도 달지 않는다", () => {
    const meta = cardMeta(
      { corporate_author: "한국도서관협회", pub_date: "2020", series_title: "도서관학" },
      "paper",
    );
    expect(meta.author).toBe("한국도서관협회");
    expect(meta.parts).toEqual([{ text: "2020년" }, { text: "도서관학", arrow: false }]);
  });

  it("소장자료: 저자 줄(개인 저자 우선, 없으면 단체)과 발행연도 · 출판사", () => {
    expect(
      cardMeta({ personal_author: "우창호", publisher: "慶北大學校", pub_date: "1997" }, "book"),
    ).toEqual({ author: "우창호", parts: [{ text: "1997년" }, { text: "慶北大學校" }] });
    expect(cardMeta({ corporate_author: "국회도서관" }, "book").author).toBe("국회도서관");
  });

  it("소장자료: 저자와 출판사가 같으면(기관 보고서) 서지 줄에서 출판사를 뺀다", () => {
    expect(cardMeta({ corporate_author: "기획예산처", publisher: "기획예산처", pub_date: "2004" }, "book")).toEqual({
      author: "기획예산처",
      parts: [{ text: "2004년" }],
    });
  });

  it("소장자료: 공백·괄호만 다른 같은 이름도 뺀다(정규화 비교)", () => {
    expect(cardMeta({ personal_author: "한국 도서관 협회", publisher: "(한국도서관협회)" }, "book").parts).toEqual([]);
  });

  it("소장자료: 저자가 개인이고 출판사가 기관이면 둘 다 보인다", () => {
    expect(cardMeta({ personal_author: "옥동석", publisher: "기획예산처" }, "book")).toEqual({
      author: "옥동석",
      parts: [{ text: "기획예산처" }],
    });
  });

  it("소장자료는 논문 전용 칸(분야·인용수)을 쓰지 않는다", () => {
    const meta = cardMeta({ series_title: "총서", kci_citations: 3, publisher: "출판사" }, "book");
    expect(meta.parts).toEqual([{ text: "출판사" }]);
  });

  it("다중 저자(' | ')는 쉼표로 이어 보인다", () => {
    expect(cardMeta({ personal_author: "최정현 | 최소연" }, "paper").author).toBe("최정현, 최소연");
    expect(cardMeta({ personal_author: "홍길동" }, "book").author).toBe("홍길동");
  });

  it("정보가 없으면 빈 저자·빈 조각", () => {
    expect(cardMeta(null, "book")).toEqual({ author: "", parts: [] });
    expect(cardMeta(undefined, "paper")).toEqual({ author: "", parts: [] });
  });
});
