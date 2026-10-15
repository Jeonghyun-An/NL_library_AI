// frontend/utils/resultCard.ts
// 결과 카드(소장자료·논문 공통)가 보이는 글을 만드는 순수 함수 — 키워드 칩·저자·서지 줄.
// 화면 상태 없이 도는 부분만 여기 둔다(components/ResultCard.vue 가 쓴다)
import { parseVolIssue } from "~/utils/citations";

export type ResultKind = "book" | "paper";

export interface CardInfo {
  extracted_keywords?: readonly string[] | null;
  keyword?: string | null;
  themes?: string | null;
  subject?: string | null;
  personal_author?: string | null;
  corporate_author?: string | null;
  publisher?: string | null;
  pub_date?: string | null;
  series_title?: string | null;
  kci_citations?: number | null;
  /** KCI 등재 구분('KCI 등재'·'KCI 후보'·'우수등재'). 논문 전용, 없을 수 있다 */
  grade?: string | null;
}

/**
 * 카드 칩 줄의 규칙(결과 카드·추천 1권·상세가 같이 쓴다): 'AI 답변 인용 N'·관련도 알약은 그대로 두고 #키워드 칩은 최대 이 개수다 —
 * 논문은 저자 키워드가 5~8개, 소장자료 주제어는 10개를 넘기도 해 정신없어 앞에서 자른다. KCI 등재 구분은 칩이 아니라 서지 줄 끝 글자(cardMeta)다
 */
export const CARD_KEYWORD_LIMIT = 3;

// 한 항목에 여러 키워드가 붙어 온 것 — 적재가 원문 키워드 칸을 그대로 읽었다(2026-10-15 운영 논문 검색 300건에서 확인).
// 칩 하나에 세 개가 붙어 보였다:
//  - '키워드(영문) 키워드(영문) …' — 국문(영문 풀이) 짝이 띄어 이어진 것. 짝마다 나누고 영문 풀이는 뗀다(국문 키워드 하나에 영문 풀이 하나)
//  - 'Elderly · Socioeconomic · Depression.' — 띄어 쓴 가운뎃점. 붙여 쓴 '아동·청소년'은 한 낱말이라 그대로
//  - '서울시 Key words : Public Library'·'Radiological Science 중심 단어: 스마트폰' — 원문의 키워드 머리 글자
//  - '이용자 만족도 University Library' — 국문 뒤에 영문 키워드(대문자로 시작하는 낱말)가 이어진 것. 'SNS 이용'·'CHI'처럼
//    약어(대문자만)는 나누지 않는다
const KEYWORD_LABEL = /\s*(?:\bkey\s?words?|중심\s?단어|주제어|핵심어)\s*[:：]\s*/gi;
const SPACED_DOT = /\s+[·•ㆍ]\s+/;
const GLOSSED_PAIRS = /^(?:\s*[^()]*[가-힣][^()]*\([^()]*[A-Za-z][^()]*\)){2,}\s*$/;
const GLOSSED_PAIR = /[^()]*[가-힣][^()]*\([^()]*[A-Za-z][^()]*\)/g;
const HANGUL_THEN_WORD = /(?<=[가-힣])\s+(?=[A-Z][a-z])/;
// 떼는 것은 소문자가 든 영문 풀이만 — '인공지능(AI)'·'크리드(KREAD)' 같은 약어는 이름의 일부라 둔다
const LATIN_GLOSS = /^(.*[가-힣][^()]*?)\s*\(\s*[A-Za-z][^()]*[a-z][^()]*\)$/;

function splitKeywordItem(item: string): string[] {
  return item
    .split(KEYWORD_LABEL)
    .flatMap((s) => s.split(SPACED_DOT))
    .flatMap((s) => (GLOSSED_PAIRS.test(s) ? (s.match(GLOSSED_PAIR) ?? [s]) : [s]))
    .flatMap((s) => s.split(HANGUL_THEN_WORD))
    .map((s) =>
      s
        .trim()
        .replace(/^#+\s*/, "")
        .replace(/[.,;:]+$/, "")
        .replace(LATIN_GLOSS, "$1")
        .trim(),
    );
}

/** `a, b; c | d` → ["a","b","c","d"] — 앞의 # 와 공백을 떼고 빈 것·중복(대소문자 무시)을 뺀다. 배열이면 항목마다 같은 정리만 한다.
 *  어느 쪽이든 한 항목 안에 붙어 온 키워드는 splitKeywordItem 으로 나눈다 */
function splitKeywords(raw: string | readonly string[] | null | undefined): string[] {
  const items = Array.isArray(raw) ? raw : typeof raw === "string" ? raw.split(/[,;|\n]/) : [];
  const parts = items.flatMap((p) => (typeof p === "string" ? splitKeywordItem(p) : []));
  const seen = new Set<string>();
  const out: string[] = [];
  for (const kw of parts) {
    const key = kw.toLowerCase();
    if (!kw || seen.has(key)) continue;
    seen.add(key);
    out.push(kw);
  }
  return out;
}

/**
 * 카드에 칩으로 달 키워드. 자료 자신의 키워드가 먼저이고 — 저자 키워드(extracted_keywords) → keyword 문자열 → 생성 주제어(themes) → subject,
 * 먼저 비지 않은 하나(섞지 않는다) — 하나도 없을 때만 fallback(추천 이유 스트림이 준 키워드)을 쓴다. 최대 limit 개
 */
export function cardKeywords(
  info: CardInfo | null | undefined,
  fallback: readonly string[] = [],
  limit: number = CARD_KEYWORD_LIMIT,
): string[] {
  for (const raw of [info?.extracted_keywords, info?.keyword, info?.themes, info?.subject]) {
    const own = splitKeywords(raw);
    if (own.length) return own.slice(0, limit);
  }
  return splitKeywords(fallback).slice(0, limit);
}

/**
 * 발행일 표기. 숫자만 읽어 앞 4자리를 연도, 다음 두 자리를 월(1~12)로 본다.
 * 논문은 '2024년 3월'(월이 없으면 '2024년'), 소장자료는 '1997년'. 연도를 못 읽으면 빈 문자열
 */
export function formatPubLabel(pubDate: string | null | undefined, kind: ResultKind): string {
  const digits = (pubDate ?? "").replace(/\D/g, "");
  if (digits.length < 4) return "";
  const year = digits.slice(0, 4);
  const month = Number(digits.slice(4, 6));
  if (kind === "paper" && digits.length >= 6 && month >= 1 && month <= 12) return `${year}년 ${month}월`;
  return `${year}년`;
}

/**
 * 논문 권호(vol_issue)를 읽기 좋게. 운영 값: '11(3)'·'4(2)'·'24(10)'(권(호)), '-33'·'-42'(권 없이 호만), 숫자 하나(권만).
 *  - 'V(N)' → 'V권 N호', '-N' → 'N호', 'V' → 'V권'
 *  - 비었거나 '-' 같은 기호뿐이면 빈 문자열(생략), 그 밖의 모양은 원문 그대로(예: '특별호', '11-3')
 * 읽기는 참고문헌과 같은 parseVolIssue(utils/citations)
 */
export function formatVolIssue(value: string | null | undefined): string {
  const v = parseVolIssue(value);
  if (!v) return "";
  if (v.raw !== null) return v.raw;
  return [v.vol ? `${v.vol}권` : "", v.issue ? `${v.issue}호` : ""].filter(Boolean).join(" ");
}

/** 이름 비교용 정리 — 공백·괄호·가운뎃점 같은 겉모양 차이와 대소문자를 지운다('한국 도서관 협회' = '한국도서관협회' = '(한국도서관협회)') */
export function normalizeName(name: string | null | undefined): string {
  return (name ?? "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\s()[\]{}<>「」『』〈〉《》“”"'·ㆍ.,]/g, "");
}

export interface MetaPart {
  text: string;
  /** 이 조각 앞에 '>' 화살표를 둔다(발행처 > 분야) */
  arrow?: boolean;
}

export interface CardMeta {
  /** 저자 줄. 없으면 빈 문자열 */
  author: string;
  /** 서지 줄 조각 — 있는 것만, 조각 사이는 점으로 이어진다 */
  parts: MetaPart[];
}

/**
 * 저자 줄과 서지 줄.
 *  - 논문: 연월 · 발행처 > 분야 · 인용수 N · KCI 등재(등급이 없으면 생략)
 *  - 소장자료: 발행연도 · 출판사
 * 저자 줄과 같은 이름(정규화 비교)이 서지 줄에 또 나오면 서지 줄에서 뺀다 — 기관 보고서는 저자·발행처가 같은 기관이라 같은 말이 두 번 나왔다
 */
export function cardMeta(info: CardInfo | null | undefined, kind: ResultKind): CardMeta {
  const personal = (info?.personal_author ?? "").trim();
  const corporate = (info?.corporate_author ?? "").trim();
  // MARC 다중 저자는 ' | ' 로 이어져 온다 — 보이는 글은 쉼표로 잇는다
  const author = (personal || corporate).split(/\s*\|\s*/).filter(Boolean).join(", ");
  const authorKey = normalizeName(author);
  const parts: MetaPart[] = [];
  const date = formatPubLabel(info?.pub_date, kind);
  if (date) parts.push({ text: date });
  // 이름 조각(발행처)은 저자 줄·앞 조각과 같으면 건너뛴다. 건너뛰었는지는 화살표를 정할 때 쓴다
  const addName = (name: string): boolean => {
    const key = normalizeName(name);
    if (!key || key === authorKey) return false;
    if (parts.some((p) => normalizeName(p.text) === key)) return false;
    parts.push({ text: name });
    return true;
  };
  if (kind === "paper") {
    const shown = addName(corporate);
    const field = (info?.series_title ?? "").trim();
    if (field) parts.push({ text: field, arrow: shown });
    const cites = info?.kci_citations;
    if (typeof cites === "number" && Number.isFinite(cites)) parts.push({ text: `인용수 ${cites}` });
    const grade = (info?.grade ?? "").trim();
    if (grade) parts.push({ text: grade });
  } else {
    addName((info?.publisher ?? "").trim());
  }
  return { author, parts };
}
