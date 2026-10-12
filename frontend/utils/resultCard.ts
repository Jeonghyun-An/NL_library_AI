// frontend/utils/resultCard.ts
// 결과 카드(소장자료·논문 공통)가 보이는 글을 만드는 순수 함수 — 키워드 칩·저자·서지 줄.
// 화면 상태 없이 도는 부분만 여기 둔다(components/ResultCard.vue 가 쓴다)

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
}

/** 카드 키워드 칩의 최대 개수 — 논문은 저자 키워드가 5~8개, 소장자료 주제어는 10개를 넘기도 해 앞에서 자른다 */
export const CARD_KEYWORD_LIMIT = 5;

/** `a, b; c | d` → ["a","b","c","d"] — 앞의 # 와 공백을 떼고 빈 것·중복(대소문자 무시)을 뺀다. 배열이면 항목마다 같은 정리만 한다 */
function splitKeywords(raw: string | readonly string[] | null | undefined): string[] {
  const parts = Array.isArray(raw) ? raw : typeof raw === "string" ? raw.split(/[,;|\n]/) : [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const p of parts) {
    if (typeof p !== "string") continue;
    const kw = p.trim().replace(/^#+\s*/, "");
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
 *  - 논문: 연월 · 발행처 > 분야 · 인용수 N
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
  } else {
    addName((info?.publisher ?? "").trim());
  }
  return { author, parts };
}
