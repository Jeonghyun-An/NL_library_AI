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

  // 운영 논문 검색 결과 300건에서 모은 실제 항목(2026-10-15) — 원문 키워드 칸을 그대로 읽어 한 항목에 여러 키워드가 붙어 왔다
  it("한 항목에 붙어 온 키워드를 나눈다 — 국문(영문) 짝이 띄어 이어진 것은 영문 풀이를 떼고 나눈다", () => {
    expect(
      cardKeywords(
        {
          extracted_keywords: [
            "다문화가정유아(Children of Multicultural Families) 언어발달(Language Development) 언어환경(Language Environment)",
          ],
        },
        [],
        10,
      ),
    ).toEqual(["다문화가정유아", "언어발달", "언어환경"]);
    expect(
      cardKeywords(
        {
          extracted_keywords: [
            "어휘력(vocabularies) 언어이해력(understanding of oral language) 언어표현력( language expression) 사회 인구학적 변인(demographic variables)",
          ],
        },
        [],
        10,
      ),
    ).toEqual(["어휘력", "언어이해력", "언어표현력", "사회 인구학적 변인"]);
    // 짝이 하나뿐이어도 영문 풀이는 뗀다
    expect(cardKeywords({ extracted_keywords: ["다문화가정유아(young children from multi-cultural families)"] })).toEqual(["다문화가정유아"]);
  });

  it("띄어 쓴 가운뎃점으로 이은 항목은 나누고 끝 마침표를 뗀다 — 붙여 쓴 '아동·청소년'은 한 낱말", () => {
    expect(cardKeywords({ extracted_keywords: ["Elderly · Socioeconomic · Depression · Suicide Ideation."] }, [], 10)).toEqual([
      "Elderly",
      "Socioeconomic",
      "Depression",
      "Suicide Ideation",
    ]);
    expect(cardKeywords({ extracted_keywords: ["아동·청소년", "부모의 긍정적·부정적 양육태도", "한국아동ㆍ청소년패널조사 2010"] })).toEqual([
      "아동·청소년",
      "부모의 긍정적·부정적 양육태도",
      "한국아동ㆍ청소년패널조사 2010",
    ]);
  });

  it("'Key words :'·'Keyword :'·'중심 단어:' 머리에서 나누고, 국문 뒤에 붙은 영문 키워드도 나눈다", () => {
    const one = (item: string) => cardKeywords({ extracted_keywords: [item] }, [], 10);
    expect(one("서울시 Key words : Public Library")).toEqual(["서울시", "Public Library"]);
    expect(one("적정성 Keywords : Library")).toEqual(["적정성", "Library"]);
    expect(one("과의존. Keyword : family problem")).toEqual(["과의존", "family problem"]);
    expect(one("Radiological Science 중심 단어: 스마트폰")).toEqual(["Radiological Science", "스마트폰"]);
    expect(one("이용자 만족도 University Library")).toEqual(["이용자 만족도", "University Library"]);
    expect(one("연구사서 Subject Specialized Manpower")).toEqual(["연구사서", "Subject Specialized Manpower"]);
    expect(one("감축목표 Key Words : Energy Policy")).toEqual(["감축목표", "Energy Policy"]);
    expect(one("다중사례분석 Keywords: Green New Deal")).toEqual(["다중사례분석", "Green New Deal"]);
  });

  it("약어 괄호('인공지능(AI)'·'크리드(KREAD)')는 이름의 일부라 떼지 않는다 — 소문자가 든 영문 풀이만 뗀다", () => {
    expect(cardKeywords({ extracted_keywords: ["인공지능(AI)", "크리드(KREAD)", "불륜(extramarital relationship)"] })).toEqual([
      "인공지능(AI)",
      "크리드(KREAD)",
      "불륜",
    ]);
  });

  it("한 키워드인 것은 그대로 — 약어 뒤 국문·국문 괄호·영문 구·띄어 쓴 국문 낱말", () => {
    for (const kw of ["SNS 이용", "CHI 서비스 개발방향 CHI", "SERVQUAL(서비스 품질) 모형", "The Mediated Moderation Effect", "사회적 지지", "COVID-19 대응"]) {
      expect(cardKeywords({ extracted_keywords: [kw] })).toEqual([kw]);
    }
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
