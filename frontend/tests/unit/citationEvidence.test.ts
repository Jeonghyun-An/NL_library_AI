// frontend/tests/unit/citationEvidence.test.ts
import { describe, expect, it } from "vitest";
import type { SectionSource } from "~/types/work";
import {
  NGRAM_N,
  bestExcerptSentence,
  citationPdfTarget,
  excerptParts,
  excerptSentences,
  ngramOverlap,
} from "~/utils/citationEvidence";

const EXCERPT =
  "연구 대상은 농촌 노인 300명이다. 가족 지지가 높은 노인일수록 우울 점수가 낮았다.  배우자 유무는 차이가 없었다!";
const CITED = "가족 지지가 높을수록 노인의 우울이 낮다고 보고되었다 [E1].";

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

describe("bestExcerptSentence — 인용 문장과 가장 많이 겹치는 대목 문장", () => {
  it("가장 많이 겹친 문장의 번호", () => {
    expect(bestExcerptSentence(CITED, EXCERPT)).toBe(1);
  });

  it("겹친 수가 같으면 앞 문장", () => {
    expect(bestExcerptSentence("노인 우울", "노인 복지. 우울 증상. 노인 건강.")).toBe(0);
  });

  it("겹침이 없으면 null", () => {
    expect(bestExcerptSentence("도서관 이용", EXCERPT)).toBeNull();
    expect(bestExcerptSentence(CITED, "")).toBeNull();
  });

  it("마커는 세지 않는다 — 대목에 같은 [E1] 이 있어도 고르지 않는다", () => {
    expect(bestExcerptSentence("[E1] [E2].", "다른 말이다 [E1]. 또 다른 말 [E2].")).toBeNull();
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
