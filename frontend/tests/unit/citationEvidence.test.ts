// frontend/tests/unit/citationEvidence.test.ts
import { describe, expect, it } from "vitest";
import type { SectionSource } from "~/types/work";
import {
  EXCERPT_MATCH_MIN,
  NGRAM_N,
  bestExcerptSentence,
  citationPdfTarget,
  citedClaims,
  excerptParts,
  excerptSentences,
  ngramOverlap,
} from "~/utils/citationEvidence";

const EXCERPT =
  "연구 대상은 농촌 노인 300명이다. 가족 지지가 높은 노인일수록 우울 점수가 낮았다.  배우자 유무는 차이가 없었다!";
const CITED = "가족 지지가 높을수록 노인의 우울이 낮다고 보고되었다 [E1].";
// 내용이 무관한데 첫 문장과 어미·흔한 낱말('연구'·'하였'·'였다')만 겹치는 인용 문장과 대목
const UNRELATED = "선행 연구들은 사회적 자본이 지역 공동체의 회복력에 기여한다고 보고하였다 [E2].";
const PANEL_EXCERPT =
  "본 연구는 2019년 전국 패널 자료를 이용하였다. 분석 결과 소득 수준은 주관적 건강에 유의한 영향을 미치지 않았다.";
// 논문 초록 꼴 대목 — '을 대상으로'·'에 미치는 영향을 분석하였다'·'유의하게'·'것으로 나타났다' 가 대목에 한 번씩만 나온다
const ABSTRACT =
  "이 연구는 대학생 500명을 대상으로 학업 스트레스가 수면의 질에 미치는 영향을 분석하였다. " +
  "구조방정식 모형을 적용한 결과 학업 스트레스는 수면의 질을 유의하게 낮추는 것으로 나타났다. " +
  "또한 자기효능감은 이 관계를 부분 매개하였다. 성별에 따른 차이는 확인되지 않았다.";
const ELDERLY =
  "본 연구는 독거노인 412명을 대상으로 사회적 지지와 우울의 관계를 살펴보았다. " +
  "위계적 회귀분석 결과 가족 지지와 친구 지지는 모두 우울을 유의하게 낮추는 것으로 나타났다. " +
  "특히 친구 지지의 효과는 남성 노인에게서 더 컸다. 경제 상태는 우울과 정적 관계가 있었다. " +
  "이러한 결과는 지역사회 차원의 관계망 지원이 필요함을 시사한다. 후속 연구에서는 종단 자료를 활용할 필요가 있다.";
const CSR =
  "이 연구는 국내 소비자 600명을 대상으로 기업의 사회적 책임 활동이 고객 충성도에 미치는 영향을 분석하였다. " +
  "분석 결과 사회적 책임 활동에 대한 인식은 기업 신뢰를 높였고, 기업 신뢰는 고객 충성도를 높였다. " +
  "환경 활동의 효과가 기부 활동보다 컸다. 업종에 따른 차이는 나타나지 않았다.";
const PLAY =
  "본 연구는 만 3~5세 유아 240명의 놀이 시간과 언어 발달의 관계를 살펴보았다. 바깥 놀이 시간은 어휘력과 정적 관계가 있었다. " +
  "그러나 미디어 이용 시간은 표현 언어 발달과 부적 관계를 보였다. 부모의 상호작용 빈도를 통제하면 놀이 시간의 효과는 줄어들었다.";
// 근거가 둘 이상인 문장(절 프롬프트가 '문장마다 그 문장을 받치는 근거를 [E#]'로 붙인다) — 마커가 문장 가운데 있는 꼴과
// 문장 끝에 몰린 꼴. 문장 전체를 인용 문장으로 재면 논문마다 덮는 정도가 갈라져 하한 아래로 떨어졌다
const MID = "가족과 친구의 지지는 독거노인의 우울을 낮추며 [E1], 대학생에게서는 학업 스트레스가 수면의 질을 낮춘다 [E2].";
const MID_CSR =
  "환경 활동이 기부 활동보다 고객 충성도에 더 큰 효과를 보였고 [E1], 유아의 미디어 이용 시간은 표현 언어 발달과 부적 관계를 보였다 [E2].";
const PAIR = "가족 지지는 노인의 우울을 낮추고, 학업 스트레스는 대학생의 수면의 질을 떨어뜨린다 [E1][E2].";
const TRIPLE =
  "가족 지지는 노인의 우울을 낮추고, 학업 스트레스는 수면을 해치며, 스마트폰 과의존은 학업 성취를 떨어뜨린다 [E1][E2][E3].";
// 두 근거가 같은 말을 함께 받치는 꼴(선행 연구 절에 흔하다)
const BOTH = "노인의 우울은 가족 지지와 친구 지지가 높을수록 낮다 [E1][E2].";

function source(excerpt: SectionSource["excerpt"]): SectionSource {
  return { cnts_id: "KCI_A", abstract: "초록", excerpt };
}

describe("excerptSentences·ngramOverlap", () => {
  it("문장 끝(. ! ? 。) 뒤 공백에서 나누고 앞뒤 공백·빈 조각은 버린다", () => {
    expect(excerptSentences(EXCERPT)).toEqual([
      "연구 대상은 농촌 노인 300명이다.",
      "가족 지지가 높은 노인일수록 우울 점수가 낮았다.",
      "배우자 유무는 차이가 없었다!",
    ]);
    expect(excerptSentences("  첫 문장。둘째 문장? 셋째  ")).toEqual(["첫 문장。둘째 문장?", "셋째"]);
    expect(excerptSentences("   ")).toEqual([]);
  });

  it("서로 다른 글자 2-gram 가운데 겹친 수 — 공백·문장부호·대소문자·전각은 보지 않는다", () => {
    expect(NGRAM_N).toBe(2);
    // '가족' '족지' '지지' 셋이 겹친다 — 띄어쓰기가 달라도 같다
    expect(ngramOverlap("가족 지지", "가족지지가")).toBe(3);
    expect(ngramOverlap("ＣＳＲ 성과", "csr, 성과!")).toBe(ngramOverlap("csr성과", "csr성과"));
    expect(ngramOverlap("가", "가")).toBe(0);                 // n 보다 짧으면 n-gram 이 없다
    expect(ngramOverlap("노인 우울", "도서관 이용")).toBe(0);
  });

  it("[E#]·[F#] 표기는 세지 않는다", () => {
    expect(ngramOverlap("[E1] [F2]", "[E1] [F2]")).toBe(0);
    expect(ngramOverlap("우울 [E12].", "우울")).toBe(1);
  });
});

describe("bestExcerptSentence — 인용 문장을 가장 많이 덮는 대목 문장", () => {
  it("가장 많이 덮는 문장의 번호", () => {
    expect(bestExcerptSentence(CITED, EXCERPT)).toBe(1);
  });

  it("덮는 정도가 같으면 앞 문장", () => {
    expect(bestExcerptSentence("노인 우울", "노인 복지. 우울 증상.")).toBe(0);
  });

  it("대목의 여러 문장에 두루 나오는 말보다 한 문장에만 나오는 말을 무겁게 센다", () => {
    // '노인' 은 두 문장, '우울' 은 한 문장에 나온다 — 같은 한 개 겹침이어도 '우울 증상' 이 더 가리키는 문장이다
    expect(bestExcerptSentence("노인 우울", "노인 복지. 우울 증상. 노인 건강.")).toBe(1);
  });

  it("인용 문장 2-gram 을 EXCERPT_MATCH_MIN 이상 덮는 문장만 고른다", () => {
    expect(EXCERPT_MATCH_MIN).toBe(0.2);
    // 문장이 하나면 무게가 모두 같아 그냥 덮는 비율이다 — '가족' 하나가 3개 가운데 1개(0.33)·8개 가운데 1개(0.125)
    expect(bestExcerptSentence("가족 지지", "가족 갈등이 컸다.")).toBe(0);
    expect(bestExcerptSentence("가족 지지와 우울 증상", "가족 갈등이 컸다.")).toBeNull();
  });

  it("어미·흔한 낱말만 겹치는 무관 문장은 고르지 않는다", () => {
    expect(ngramOverlap(UNRELATED, excerptSentences(PANEL_EXCERPT)[0]!)).toBe(3);
    expect(bestExcerptSentence(UNRELATED, PANEL_EXCERPT)).toBeNull();
  });

  it("대목에 한 번만 나오는 논문 상투구만 겹치는 짧은 무관 문장은 고르지 않는다", () => {
    // 대목 안 IDF 만으로는 한 번 나오는 상투구가 가장 무거워 이 문장들이 0.32·0.32·0.44·0.32·0.38 로 강조되었다
    for (const cited of [
      "노인의 신체활동은 인지 기능 저하를 늦추는 것으로 나타났다 [E1].",
      "기업의 사회적 책임 활동은 고객 충성도를 유의하게 높이는 것으로 나타났다 [E1].",
      "중학생을 대상으로 한 연구에서 부모의 양육 태도가 자아존중감에 미치는 영향을 분석하였다 [E1].",
    ]) {
      expect(bestExcerptSentence(cited, ABSTRACT), cited).toBeNull();
    }
    expect(bestExcerptSentence("청소년의 스마트폰 과의존은 학업 성취도를 낮추는 것으로 나타났다 [E2].", ELDERLY)).toBeNull();
    expect(bestExcerptSentence("유아의 놀이 시간은 언어 발달에 영향을 미치지 않았다 [E2].", PANEL_EXCERPT)).toBeNull();
  });

  it("상투구로만 된 인용 문장은 대목에 같은 말이 있어도 고르지 않는다", () => {
    expect(bestExcerptSentence("것으로 나타났다 [E1].", ABSTRACT)).toBeNull();
    expect(bestExcerptSentence("을 대상으로 한 연구에서 유의하게 확인되었다.", ABSTRACT)).toBeNull();
  });

  it("상투구가 섞인 맞는 인용 문장은 그대로 고른다", () => {
    expect(bestExcerptSentence("학업 스트레스가 수면의 질을 유의하게 낮추는 것으로 나타났다 [E1].", ABSTRACT)).toBe(1);
    expect(bestExcerptSentence("자기효능감이 학업 스트레스와 수면의 관계를 매개한다 [E1].", ABSTRACT)).toBe(2);
    expect(bestExcerptSentence("성별 차이는 없었다 [E1].", ABSTRACT)).toBe(3);
    expect(bestExcerptSentence("친구 지지의 효과는 남성 노인에서 더 크게 나타났다 [E1].", ELDERLY)).toBe(2);
    expect(bestExcerptSentence("독거노인의 우울을 줄이려면 지역사회 관계망 지원이 필요하다 [E1].", ELDERLY)).toBe(4);
  });

  it("흔한 말을 더 많이 나누는 긴 문장보다 내용이 겹치는 짧은 문장을 고른다", () => {
    const cited = "선행 연구는 가족 지지가 노인의 우울을 낮춘다고 보고하였다 [E1].";
    const excerpt =
      "본 연구는 노인을 대상으로 사회적 지지가 정신건강에 미치는 영향을 분석하였으며, 연구 결과를 바탕으로 노인 복지 정책에 주는 함의를 논의하였다. " +
      "가족 지지는 우울을 낮췄다. 본 연구는 노인 복지 현장에서 활용할 수 있는 기초 자료를 제공하였다.";
    const [long, short] = excerptSentences(excerpt);
    expect(ngramOverlap(cited, long!)).toBeGreaterThan(ngramOverlap(cited, short!));
    expect(bestExcerptSentence(cited, excerpt)).toBe(1);
  });

  it("겹침이 없으면 null", () => {
    expect(bestExcerptSentence("도서관 이용", EXCERPT)).toBeNull();
    expect(bestExcerptSentence(CITED, "")).toBeNull();
  });

  it("마커는 세지 않는다 — 대목에 같은 [E1] 이 있어도 고르지 않는다", () => {
    expect(bestExcerptSentence("[E1] [E2].", "다른 말이다 [E1]. 또 다른 말 [E2].")).toBeNull();
  });
});

describe("citedClaims — 누른 칩의 [E#] 가 받치는 말", () => {
  it("근거 번호가 없으면 문장 그대로", () => {
    expect(citedClaims(MID)).toEqual([MID]);
  });

  it("앞 마커 묶음(없으면 문장 머리)부터 누른 마커까지의 절 — 앞뒤 공백·쉼표는 뗀다", () => {
    expect(citedClaims(MID, "E1")).toEqual(["가족과 친구의 지지는 독거노인의 우울을 낮추며"]);
    expect(citedClaims(MID, "E2")).toEqual(["대학생에게서는 학업 스트레스가 수면의 질을 낮춘다"]);
    // 문장 끝 마커 하나면 마커 앞 문장 전체 — 마침표 뒤에 붙은 묶음(sentenceFlags 가 앞 문장으로 센다)도 같다
    expect(citedClaims(CITED, "E1")).toEqual(["가족 지지가 높을수록 노인의 우울이 낮다고 보고되었다"]);
    expect(citedClaims("가족 지지는 우울을 낮춘다. [E1] ", "E1")).toEqual(["가족 지지는 우울을 낮춘다."]);
  });

  it("한 묶음에 근거가 둘 이상이면 그 절과, 쉼표·이음 어미 뒤에서 나눈 조각도 받치는 말 후보다", () => {
    const halves = ["가족 지지는 노인의 우울을 낮추고", "학업 스트레스는 대학생의 수면의 질을 떨어뜨린다"];
    const clause = "가족 지지는 노인의 우울을 낮추고, 학업 스트레스는 대학생의 수면의 질을 떨어뜨린다";
    expect(citedClaims(PAIR, "E1")).toEqual([clause, ...halves]);
    expect(citedClaims(PAIR, "E2")).toEqual([clause, ...halves]);
    // 묶음 사이의 공백·쉼표는 한 묶음이다
    expect(citedClaims(PAIR.replace("[E1][E2]", "[E1], [E2]"), "E2")).toEqual([clause, ...halves]);
    // 쉼표 없이 '-며' 로 이은 절
    expect(citedClaims("스마트폰 과의존은 학업 성취를 낮추며 대학생의 학업 스트레스는 수면의 질을 해친다 [E1] [E2].", "E1")).toEqual([
      "스마트폰 과의존은 학업 성취를 낮추며 대학생의 학업 스트레스는 수면의 질을 해친다",
      "스마트폰 과의존은 학업 성취를 낮추며",
      "대학생의 학업 스트레스는 수면의 질을 해친다",
    ]);
    // 나눌 자리가 없으면 그 절 하나
    expect(citedClaims(BOTH, "E2")).toEqual(["노인의 우울은 가족 지지와 친구 지지가 높을수록 낮다"]);
  });

  it("같은 근거가 여러 번 붙으면 그 절들을 함께와 하나씩", () => {
    expect(citedClaims("과의존은 학업 성취를 낮추고 [E1], 부모의 감독이 그 관계를 바꾼다 [E1].", "E1")).toEqual([
      "과의존은 학업 성취를 낮추고 부모의 감독이 그 관계를 바꾼다",
      "과의존은 학업 성취를 낮추고",
      "부모의 감독이 그 관계를 바꾼다",
    ]);
  });

  it("상투구 밖 2-gram 이 셋 미만인 조각은 버리고, 남는 것이 없으면 문장 그대로", () => {
    // '선행 연구들' 은 '구들' 하나뿐이다 — 마커가 주어 뒤에 붙은 꼴은 문장 전체로 잰다
    const subject = "선행 연구들 [E1][E2]은 가족 지지가 노인의 우울을 낮춘다고 보았다.";
    expect(citedClaims(subject, "E1")).toEqual([subject]);
    // '또한' 같은 머리 조각은 후보에서 빠진다
    expect(citedClaims("또한, 가족 지지는 우울을 낮춘다 [E1][E2].", "E1")).toEqual([
      "또한, 가족 지지는 우울을 낮춘다",
      "가족 지지는 우울을 낮춘다",
    ]);
    // 문장에 없는 번호
    expect(citedClaims(MID, "E9")).toEqual([MID]);
  });
});

describe("bestExcerptSentence — 근거가 둘 이상인 문장(누른 칩의 번호를 넘길 때)", () => {
  it("마커가 문장 가운데 있으면 누른 마커로 끝나는 절만 잰다", () => {
    // 문장 전체로 재면 다른 논문 몫의 말이 분모를 키워 0.145·0.172 로 하한 아래였다
    expect(bestExcerptSentence(MID, ELDERLY)).toBeNull();
    expect(bestExcerptSentence(MID, ELDERLY, "E1")).toBe(1);
    expect(bestExcerptSentence(MID_CSR, CSR)).toBeNull();
    expect(bestExcerptSentence(MID_CSR, CSR, "E1")).toBe(2);
    expect(bestExcerptSentence(MID_CSR, PLAY, "E2")).toBe(2);
  });

  it("문장 끝에 몰린 마커는 나눈 조각 가운데 가장 잘 덮이는 것으로 잰다", () => {
    // 검토 반례 — 문장 전체로는 독거노인 대목의 맞는 문장이 0.181 로 null 이었다
    expect(bestExcerptSentence(PAIR, ELDERLY)).toBeNull();
    expect(bestExcerptSentence(PAIR, ELDERLY, "E1")).toBe(1);
    expect(bestExcerptSentence(TRIPLE, ELDERLY)).toBeNull();
    expect(bestExcerptSentence(TRIPLE, ELDERLY, "E1")).toBe(1);
    expect(bestExcerptSentence(TRIPLE, ABSTRACT, "E2")).toBe(1);
  });

  it("두 근거가 같은 말을 함께 받치는 문장은 그대로 고른다", () => {
    expect(bestExcerptSentence(BOTH, ELDERLY, "E1")).toBe(1);
    expect(bestExcerptSentence(BOTH, EXCERPT, "E2")).toBe(1);
  });

  it("내용이 무관한 대목은 좁히거나 나눈 뒤에도 고르지 않는다", () => {
    for (const [cited, eid] of [[MID, "E1"], [MID, "E2"], [PAIR, "E1"], [PAIR, "E2"], [TRIPLE, "E3"], [BOTH, "E1"]] as const) {
      for (const excerpt of [CSR, PLAY, PANEL_EXCERPT]) expect(bestExcerptSentence(cited, excerpt, eid), `${eid} ${cited}`).toBeNull();
    }
    expect(bestExcerptSentence(MID_CSR, ELDERLY, "E1")).toBeNull();
    expect(bestExcerptSentence(MID_CSR, ABSTRACT, "E2")).toBeNull();
  });

  it("근거가 하나인 문장은 번호를 넘겨도 문장 전체로 잴 때와 같다", () => {
    expect(bestExcerptSentence(CITED, EXCERPT, "E1")).toBe(1);
    expect(bestExcerptSentence("노인의 신체활동은 인지 기능 저하를 늦추는 것으로 나타났다 [E1].", ABSTRACT, "E1")).toBeNull();
    expect(bestExcerptSentence(UNRELATED, PANEL_EXCERPT, "E2")).toBeNull();
    expect(bestExcerptSentence("친구 지지의 효과는 남성 노인에서 더 크게 나타났다 [E1].", ELDERLY, "E1")).toBe(2);
  });
});

describe("excerptParts", () => {
  it("가장 많이 겹친 문장만 표시하고, 조각을 이으면 원문 글자 그대로다", () => {
    const parts = excerptParts(EXCERPT, CITED);
    expect(parts).toEqual([
      { text: "연구 대상은 농촌 노인 300명이다. ", mark: false },
      { text: "가족 지지가 높은 노인일수록 우울 점수가 낮았다.", mark: true },
      { text: "  배우자 유무는 차이가 없었다!", mark: false },
    ]);
    expect(parts.map((p) => p.text).join("")).toBe(EXCERPT);
  });

  it("겹치는 문장이 없으면 표시 없이 한 조각, 앞뒤 공백도 남긴다", () => {
    expect(excerptParts(" 다른 이야기. 또 다른 이야기 ", "노인 우울")).toEqual([
      { text: " 다른 이야기. 또 다른 이야기 ", mark: false },
    ]);
    expect(excerptParts("", CITED)).toEqual([]);
    // 어미·흔한 낱말만 겹치면 근거처럼 강조하지 않는다
    expect(excerptParts(PANEL_EXCERPT, UNRELATED)).toEqual([{ text: PANEL_EXCERPT, mark: false }]);
    // 논문 상투구만 겹쳐도 그렇다
    expect(excerptParts(ABSTRACT, "노인의 신체활동은 인지 기능 저하를 늦추는 것으로 나타났다 [E1].")).toEqual([
      { text: ABSTRACT, mark: false },
    ]);
  });

  it("누른 칩의 번호를 넘기면 그 칩이 받치는 말로 고른다", () => {
    expect(excerptParts(ELDERLY, PAIR)).toEqual([{ text: ELDERLY, mark: false }]);
    const parts = excerptParts(ELDERLY, PAIR, "E1");
    expect(parts.filter((p) => p.mark).map((p) => p.text)).toEqual([excerptSentences(ELDERLY)[1]]);
    expect(parts.map((p) => p.text).join("")).toBe(ELDERLY);
  });
});

describe("citationPdfTarget", () => {
  it("대목의 쪽(0부터 센 저장값)을 뷰어 쪽으로 열고 대목 이름을 붙인다", () => {
    const target = citationPdfTarget(source({ chunk_id: "KCI_A__0004", page_start: 5, page_end: 7, text: "대목" }), "논문");
    expect(target).toEqual({ cntsId: "KCI_A", title: "논문", page: 6, passages: [{ page: 6, label: "p.6–8" }] });
    const single = citationPdfTarget(source({ chunk_id: "c", page_start: 5, page_end: null, text: "대목" }), "논문");
    expect(single.passages).toEqual([{ page: 6, label: "p.6" }]);
  });

  it("쪽 정보가 0·없음이면 쪽 없이 연다", () => {
    const target = citationPdfTarget(source({ chunk_id: "c", page_start: null, page_end: null, text: "대목" }), "논문");
    expect(target.page).toBeUndefined();
    expect(target.passages).toEqual([{ page: null, label: "쪽 정보 없음" }]);
  });

  it("대목이 없으면(초록만) 논문을 처음부터 연다", () => {
    expect(citationPdfTarget(source(null), "논문")).toEqual({ cntsId: "KCI_A", title: "논문" });
  });
});
