// frontend/tests/unit/detailView.test.ts
import { describe, expect, it } from "vitest";
import {
  activeTabKey,
  aiTabAvailable,
  bookDetailRows,
  bookMetaRows,
  detailSearchUrl,
  focusOwningPanel,
  formatAuthors,
  kdcLabel,
  paperMetaRows,
  queryScore,
  relatedMetaLine,
  relativeScore,
  tabKeyTarget,
  visibleTabs,
  withChat,
  type MetaRow,
} from "~/utils/detailView";

/** 행을 '라벨: 값'(화살표는 ' › ') 글로 — 비교를 짧게 */
function flat(rows: MetaRow[]): string[] {
  return rows.map((r) => `${r.label}: ${r.parts.map((p, i) => (i && p.arrow ? ` › ${p.text}` : i ? ` ${p.text}` : p.text)).join("")}`);
}

describe("formatAuthors — 저자 줄", () => {
  it("세로줄·세미콜론으로 적힌 개인 저자를 쉼표로 맞춘다", () => {
    expect(formatAuthors("김수영 | 조성배")).toBe("김수영, 조성배");
    expect(formatAuthors("A;B;C")).toBe("A, B, C");
  });

  it("'성, 이름' 한 사람은 쪼개지 않는다", () => {
    expect(formatAuthors("Smith, John")).toBe("Smith, John");
  });

  it("개인 저자가 없으면 기관 저자, 둘 다 없으면 빈 문자열", () => {
    expect(formatAuthors(null, " 대한민국정부 ")).toBe("대한민국정부");
    expect(formatAuthors("", null)).toBe("");
  });
});

describe("paperMetaRows — 논문 서지 표", () => {
  const paper = {
    personal_author: "김수영 | 조성배",
    corporate_author: "한국인지과학회",
    publisher: null,
    series_title: "인지과학",
    vol_issue: "13(4)",
    pub_date: "2002.12",
    extent: "1~8",
    kci_citations: 10,
    wos_citations: 0,
    grade: "KCI 등재",
  };

  it("저자정보 · 저널정보(발행처 › 분야 › 권호) · 발행년도 · 수록면 · 인용수 · 등재 정보 순", () => {
    expect(flat(paperMetaRows(paper))).toEqual([
      "저자정보: 김수영, 조성배",
      "저널정보: 한국인지과학회 › 인지과학 › 13권 4호",
      "발행년도: 2002년 12월",
      "수록면: 1~8",
      "인용수: 10",
      "등재 정보: KCI 등재",
    ]);
  });

  it("발행처(publisher)가 있으면 기관 저자보다 먼저 쓴다", () => {
    expect(flat(paperMetaRows({ ...paper, publisher: "한국방송학회" }))[1]).toBe("저널정보: 한국방송학회 › 인지과학 › 13권 4호");
  });

  it("개인 저자가 없어 기관이 저자 줄에 오르면 저널정보에서 같은 기관을 빼고 화살표도 앞에 두지 않는다", () => {
    const rows = paperMetaRows({ ...paper, personal_author: null });
    expect(flat(rows).slice(0, 2)).toEqual(["저자정보: 한국인지과학회", "저널정보: 인지과학 › 13권 4호"]);
    expect(rows[1]!.parts[0]!.arrow).toBe(false);
  });

  it("인용수 0 도 보이고, WOS 인용이 있으면 함께 적는다", () => {
    expect(flat(paperMetaRows({ ...paper, kci_citations: 0 }))).toContain("인용수: 0");
    expect(flat(paperMetaRows({ ...paper, wos_citations: 3 }))).toContain("인용수: KCI 10 · WOS 3");
  });

  it("값이 없는 행은 뺀다(등급이 없으면 등재 정보 행도 없다)", () => {
    expect(flat(paperMetaRows({ title: "제목만" }))).toEqual([]);
    expect(flat(paperMetaRows({ ...paper, grade: null, extent: "" })).map((r) => r.split(":")[0])).toEqual([
      "저자정보",
      "저널정보",
      "발행년도",
      "인용수",
    ]);
  });

  it("발행일을 연월로 읽지 못하면 원래 글 그대로", () => {
    expect(flat(paperMetaRows({ pub_date: "미상" }))).toEqual(["발행년도: 미상"]);
  });
});

describe("bookMetaRows · bookDetailRows — 소장자료 서지", () => {
  const book = {
    title: "2006~2010년 국가재정운용계획",
    personal_author: null,
    corporate_author: "대한민국정부",
    publisher: "기획예산처",
    pub_place: "서울",
    pub_date: "2006",
    extent: "407 p.",
    kdc: "329",
    language: "한국어",
  };

  it("머리 표는 저자정보 · 발행처 · 발행년도 · 분류(KDC 이름)", () => {
    expect(flat(bookMetaRows(book))).toEqual([
      "저자정보: 대한민국정부",
      "발행처: 기획예산처",
      "발행년도: 2006년",
      "분류: 재정 (KDC 329)",
    ]);
  });

  it("저자와 같은 기관(공백·괄호 차이 무시)인 발행처는 뺀다", () => {
    expect(flat(bookMetaRows({ ...book, publisher: "(대한민국 정부)" })).map((r) => r.split(":")[0])).toEqual([
      "저자정보",
      "발행년도",
      "분류",
    ]);
  });

  it("상세 서지 정보는 예전 상세 정보 표의 행 중 값이 있는 것만", () => {
    expect(flat(bookDetailRows(book))).toEqual([
      "표제/저자사항: 2006~2010년 국가재정운용계획",
      "발행사항: 서울, 기획예산처, 2006",
      "형태사항: 407 p.",
      "분류기호: 329",
      "언어: 한국어",
    ]);
  });

  it("kdcLabel — 이름을 못 찾으면 번호만, 값이 없으면 빈 문자열", () => {
    expect(kdcLabel("813.6")).toBe("한국소설 (KDC 813.6)");
    expect(kdcLabel("x")).toBe("KDC x");
    expect(kdcLabel(null)).toBe("");
  });
});

describe("relatedMetaLine — 관련 자료 카드의 서지 줄", () => {
  it("논문: 연월 · 발행처(없으면 기관 저자)", () => {
    expect(relatedMetaLine({ personal_author: "김경민 | 조성배", corporate_author: "한국인지과학회", pub_date: "2004.09" }, "paper")).toBe(
      "2004년 9월 · 한국인지과학회",
    );
  });

  it("소장자료: 연도 · 출판사, 저자와 같은 기관은 뺀다", () => {
    expect(relatedMetaLine({ corporate_author: "기획예산처", publisher: "기획예산처", pub_date: "2005" }, "book")).toBe("2005년");
    expect(relatedMetaLine({ publisher: "기획예산처" }, "book")).toBe("기획예산처");
    expect(relatedMetaLine(null, "book")).toBe("");
  });
});

describe("점수", () => {
  it("queryScore — 주소의 점수를 0~1 값으로, 없거나 숫자가 아니면 null", () => {
    expect(queryScore("0.8993")).toBe(0.8993);
    expect(queryScore(["0.5", "0.7"])).toBe(0.5);
    expect(queryScore("0")).toBe(0);
    expect(queryScore("")).toBeNull();
    expect(queryScore("abc")).toBeNull();
    expect(queryScore(undefined)).toBeNull();
  });

  it("relativeScore — 목록 1위를 1 로 둔 비율", () => {
    const all = [0.0325, 0.0308, null];
    expect(relativeScore(0.0325, all)).toBe(1);
    expect(relativeScore(0.0308, all)).toBeCloseTo(0.0308 / 0.0325);
    expect(relativeScore(null, all)).toBe(0);
    expect(relativeScore(0, [0, 0])).toBe(0);
  });
});

describe("AI 큐레이션 탭", () => {
  const tabs = [
    { key: "ai-summary", label: "AI 요약", available: true },
    { key: "abstract", label: "초록", available: false },
  ];

  it("글이 없는 탭은 뺀다", () => {
    expect(visibleTabs(tabs).map((t) => t.key)).toEqual(["ai-summary"]);
  });

  it("고른 탭이 빠지면 첫 탭, 탭이 없으면 null", () => {
    expect(activeTabKey("abstract", visibleTabs(tabs))).toBe("ai-summary");
    expect(activeTabKey("ai-summary", tabs)).toBe("ai-summary");
    expect(activeTabKey(null, tabs)).toBe("ai-summary");
    expect(activeTabKey("x", [])).toBeNull();
  });

  it("방향키 — 좌우는 돌고 Home·End 는 처음·끝, 다른 키는 null", () => {
    expect(tabKeyTarget("ArrowRight", 0, 3)).toBe(1);
    expect(tabKeyTarget("ArrowRight", 2, 3)).toBe(0);
    expect(tabKeyTarget("ArrowLeft", 0, 3)).toBe(2);
    expect(tabKeyTarget("Home", 2, 3)).toBe(0);
    expect(tabKeyTarget("End", 0, 3)).toBe(2);
    expect(tabKeyTarget("Enter", 0, 3)).toBeNull();
    expect(tabKeyTarget("ArrowRight", 0, 0)).toBeNull();
  });
});

describe("aiTabAvailable — AI 글 탭(논문 AI 요약·소장자료 추천 이유)을 둘지", () => {
  const idle = { loading: false, done: false, text: "", error: "" };

  it("정하기 전·받는 중·받은 글·실패 안내가 있으면 둔다", () => {
    expect(aiTabAvailable(idle)).toBe(true);
    expect(aiTabAvailable({ ...idle, loading: true })).toBe(true);
    expect(aiTabAvailable({ ...idle, done: true, text: "요약" })).toBe(true);
    expect(aiTabAvailable({ ...idle, done: true, error: "AI 요약을 만들지 못했습니다" })).toBe(true);
  });

  it("다 정했는데 글도 실패도 없으면 뺀다", () => {
    expect(aiTabAvailable({ ...idle, done: true })).toBe(false);
  });

  it("[다시 시도] — 실패로 정한 뒤 글·안내를 비우고 다시 받는 동안에도 탭이 남는다(첫 글자가 오기 전)", () => {
    // 첫 실패: done=true · error 있음 → 다시 받기 시작: error·text 를 비우고 loading=true(done 은 앞 실패에서 true)
    expect(aiTabAvailable({ loading: true, done: true, text: "", error: "" })).toBe(true);
  });
});

describe("focusOwningPanel — 누르면 사라지는 버튼의 초점을 그 탭 본문으로", () => {
  it("버튼에서 가장 가까운 tabpanel 에 초점을 준다", () => {
    const focused: string[] = [];
    const panel = { focus: () => focused.push("panel") };
    const button = { closest: (sel: string) => (sel === '[role="tabpanel"]' ? panel : null) };
    focusOwningPanel(button as unknown as EventTarget);
    expect(focused).toEqual(["panel"]);
  });

  it("탭 본문 밖이거나 대상이 없으면 아무것도 하지 않는다", () => {
    expect(() => focusOwningPanel({ closest: () => null } as unknown as EventTarget)).not.toThrow();
    expect(() => focusOwningPanel(null)).not.toThrow();
    expect(() => focusOwningPanel({} as EventTarget)).not.toThrow();
  });
});

describe("withChat — DeepRead 를 연 채 들어가는 주소", () => {
  it("쿼리가 있으면 &, 없으면 ? 로 붙이고 해시는 뒤에 둔다", () => {
    expect(withChat("/papers/A?from=search&q=x")).toBe("/papers/A?from=search&q=x&chat=1");
    expect(withChat("/books/B")).toBe("/books/B?chat=1");
    expect(withChat("/books/B?q=a#top")).toBe("/books/B?q=a&chat=1#top");
  });
});

describe("detailSearchUrl — 상세 위 검색바", () => {
  it("빈 글이면 보내지 않는다", () => {
    expect(detailSearchUrl("paper", "   ")).toBeNull();
  });

  it("들어온 검색과 같은 검색어면 그 결과 화면으로 돌아간다", () => {
    expect(detailSearchUrl("paper", " RAG 검색 ", { q: "RAG 검색", to: "/papers?h=1&q=RAG" })).toBe("/papers?h=1&q=RAG");
  });

  it("다른 검색어면 새 검색 — 논문은 /papers, 소장자료는 /", () => {
    expect(detailSearchUrl("paper", "대화형 에이전트", { q: "RAG", to: "/papers?q=RAG" })).toBe(
      "/papers?q=%EB%8C%80%ED%99%94%ED%98%95+%EC%97%90%EC%9D%B4%EC%A0%84%ED%8A%B8",
    );
    expect(detailSearchUrl("book", "재정")).toBe("/?q=%EC%9E%AC%EC%A0%95");
  });
});
