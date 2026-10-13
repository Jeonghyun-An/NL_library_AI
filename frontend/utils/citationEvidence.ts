// frontend/utils/citationEvidence.ts
// 인용 근거 탭(보고서 단계 오른쪽 패널, D24 A안)의 판단 — 누른 인용 칩의 문장과 그 문장을 쓸 때 모델에 넘긴 원문 대목
// (GET …/sections/{key}/sources 의 excerpt)을 견줘 대목 쪽에서 강조할 문장을 고른다. 리랭커 점수는 쓰지 않는다(대회
// 뒤) — 화면이 글자 n-gram 겹침만 센다(spec §12-4 하이라이트). 본문 쪽 강조는 누른 칩이 든 문장이다(sentenceFlags 의 번호).
// 겹침이 모자라면 아무 문장도 강조하지 않는다 — 뒷받침하지 않는 문장을 근거처럼 보이지 않는다(spec '인용이라는 말을 정확히').
// 한 문장에 근거가 둘 이상이면 누른 칩의 번호가 받치는 말(citedClaims)로 잰다 — 문장 전체로 재면 다른 논문 몫의 말이 분모를 키운다
import type { OpenPdfPayload } from "~/types/research";
import type { SectionSource } from "~/types/work";
import { citedPdfTarget } from "~/utils/pdfViewer";

// 글자 2-gram — 한국어는 조사·어미가 붙어 낱말 단위로는 같은 말이 잘 겹치지 않는다
export const NGRAM_N = 2;
// 강조하려면 인용 문장 2-gram(무게를 단)의 이만큼은 그 대목 문장이 덮어야 한다 — 무관한 문장이 어미·논문 상투구
// ('였다'·'것으로 나타났다'·'을 대상으로')만으로 넘는 일이 없게. 합성 예(초록 꼴 대목 다섯)에서 맞는 문장은 0.24~0.83,
// 내용이 무관한 문장은 0.13 이하였다. 근거가 둘 이상인 문장(받치는 말로 좁힌 뒤)은 맞는 0.30~1.0, 무관은 '의 효과가 … 컸다'
// 결과 문형만 겹친 하나가 0.20 으로 하한에 닿고 나머지는 0.15 이하였다 — 운영 대목으로 잰 값이 아니다(계획 파트 S 메모 12)
export const EXCERPT_MATCH_MIN = 0.2;

// 문장 끝(마침표·물음표·느낌표·고리점) 뒤 공백에서 나눈다 — 대목은 원문 그대로라 [E#] 표기가 없다(본문 쪽 sentenceFlags 와 다른 규칙)
const SENTENCE_SPLIT = /(?<=[.!?。])\s+/;
// 같은 자리에서 나누되 사이 공백을 남긴다(excerptParts 가 원문 글자를 하나도 빼지 않게)
const SENTENCE_SPLIT_KEEP = /((?<=[.!?。])\s+)/;
const MARKERS = /\[[EF]\p{Nd}+\]/gu;
// 공백·문장부호·기호는 겹침으로 세지 않는다
const NOISE = /[\s\p{P}\p{S}]/gu;

export function excerptSentences(text: string): string[] {
  return text
    .split(SENTENCE_SPLIT)
    .map((s) => s.trim())
    .filter(Boolean);
}

function grams(text: string, n: number): Set<string> {
  const chars = Array.from(text.normalize("NFKC").replace(MARKERS, "").toLowerCase().replace(NOISE, ""));
  const out = new Set<string>();
  for (let i = 0; i + n <= chars.length; i += 1) out.add(chars.slice(i, i + n).join(""));
  return out;
}

// 한국어 논문 상투구·어미 — 이 말들의 글자 2-gram(띄어쓰기를 빼고 이어진 것까지)은 고르기에서 무게 0 이다. 대목 안 IDF 는
// 대목에 한 번만 나오는 상투구를 오히려 가장 무겁게 세어, '노인의 신체활동은 … 늦추는 것으로 나타났다' 같은 무관한 짧은
// 인용 문장이 '… 낮추는 것으로 나타났다' 문장에 0.32 로 강조되었다. 내용을 가리키는 말('관계'·'효과'·'매개')은 넣지 않는다
const BOILERPLATE = [
  "는 것으로 나타났다", "것으로 나타난다", "것으로 확인되었다", "것으로 분석되었다", "것으로 보고되었다", "것으로 밝혀졌다",
  "을 대상으로 한", "를 대상으로", "에 미치는 영향을 분석하였다", "영향을 미치지 않았다",
  "유의하게", "유의미한", "유의한", "본 연구는", "선행 연구에서", "연구 결과", "분석 결과",
  "보고하였다", "보고되었다", "확인하였다", "확인되었다", "검증하였다", "제시하였다", "밝혔다",
  "하였다", "되었다", "었다", "았다", "지 않았다", "이다", "있다", "없다", "한다", "하는", "하고", "하여", "으며", "에서",
  "에 따른", "에 대한", "을 통해",
];
const BOILERPLATE_GRAMS = new Set(BOILERPLATE.flatMap((phrase) => Array.from(grams(phrase, NGRAM_N))));

// [E#] 마커 묶음 — 사이에 공백·쉼표·가운뎃점만 있는 [E#] 들은 한 묶음이다([E1][E2]·[E1] [E2]·[E1], [E2]). [F#] 는 수치
// 표기라 절을 나누지 않는다(grams 가 지운다)
const CITE_GROUP = /\[E\p{Nd}+\](?:[\s,;·]*\[E\p{Nd}+\])*/gu;
const CITE_ID = /\[(E\p{Nd}+)\]/gu;
// 근거가 둘 이상인 묶음 앞 절을 나누는 자리 — 쉼표, 이음 어미('-고'·'-며'·'-면서'·'-지만'·'-으나') 뒤 공백
const CLAUSE_SPLIT = /,|(?<=(?:[고며]|면서|지만|으나))\s+/;
const CLAUSE_EDGE = /^[\s,;·]+|\s+$/g;
// 받치는 말 후보로 쓰려면 상투구 밖 2-gram 이 이만큼은 있어야 한다 — '선행 연구들 [E1]은 …' 의 '선행 연구들'·머리의
// '또한' 같은 조각은 빼고, 남는 것이 없으면 문장 전체로 잰다
const CLAIM_MIN_GRAMS = 3;

function contentGrams(text: string): number {
  let count = 0;
  for (const g of grams(text, NGRAM_N)) if (!BOILERPLATE_GRAMS.has(g)) count += 1;
  return count;
}

// 누른 칩의 근거 번호(eid — CitePick.eid)가 받치는 말 후보. 그 번호가 든 마커 묶음 앞의 절(앞 마커 묶음이나 문장 머리부터)
// 이고, 같은 번호가 여러 번 붙으면 그 절들을 이은 것과 하나씩이다. 묶음에 근거가 둘 이상이면('… 낮추고, … 떨어뜨린다
// [E1][E2]') 어느 말이 어느 논문 몫인지 모르므로 절을 쉼표·이음 어미 뒤에서 나눈 조각도 후보로 더한다. 번호가 없거나
// 문장에 없으면, 또는 후보가 모두 너무 짧으면 문장 그대로 하나다
export function citedClaims(sentence: string, eid?: string): string[] {
  if (!eid) return [sentence];
  const own: string[] = [];
  const pieces: string[] = [];
  let start = 0;
  for (const m of sentence.matchAll(CITE_GROUP)) {
    const at = m.index ?? 0;
    const ids = new Set(Array.from(m[0].matchAll(CITE_ID), (id) => id[1]));
    if (ids.has(eid)) {
      const clause = sentence.slice(start, at).replace(CLAUSE_EDGE, "");
      own.push(clause);
      if (ids.size > 1) pieces.push(...clause.split(CLAUSE_SPLIT).map((p) => p.replace(CLAUSE_EDGE, "")));
    }
    start = at + m[0].length;
  }
  const claims = [own.join(" "), ...(own.length > 1 ? own : []), ...pieces].filter(
    (claim) => contentGrams(claim) >= CLAIM_MIN_GRAMS,
  );
  return claims.length ? Array.from(new Set(claims)) : [sentence];
}

// 두 글의 글자 n-gram(서로 다른 것) 가운데 겹친 수. [E#]·[F#] 표기·공백·문장부호는 빼고, NFKC·소문자로 맞춘 뒤 센다
export function ngramOverlap(a: string, b: string, n: number = NGRAM_N): number {
  const left = grams(a, n);
  let count = 0;
  for (const g of grams(b, n)) if (left.has(g)) count += 1;
  return count;
}

// 인용한 문장을 가장 많이 덮는 대목 문장의 번호(excerptSentences 순서). 덮는 정도 = 인용 문장 2-gram 가운데 그 문장에도
// 있는 것의 무게 합 ÷ 인용 문장 2-gram 의 무게 합(0~1). 무게는 상투구(BOILERPLATE) 2-gram 이면 0, 아니면 대목 안 IDF —
// ln((대목 문장 수 + 1) ÷ 그 2-gram 이 나오는 대목 문장 수(대목에 없으면 1)): 여러 문장에 두루 나오는 흔한 낱말은 가볍고
// 한 문장에만 나오는 말이 무거워, 흔한 말을 많이 품은 긴 문장으로 쏠리지 않는다. 대목이 한 문장이면 상투구 밖 말을 덮는
// 비율이다. 같으면 앞 문장, 인용 문장이 상투구뿐이거나 가장 큰 값이 EXCERPT_MATCH_MIN 아래면 null(번역·요약해 쓴 문장도
// 여기로 온다 — 화면은 강조 없이 대목 전체를 보인다). 누른 칩의 근거 번호(eid)를 넘기면 인용 문장 대신 그 번호가 받치는
// 말 후보(citedClaims)마다 덮는 정도를 재어 가장 큰 값을 그 문장의 값으로 쓴다 — 근거가 하나인 문장은 후보가 문장 하나라 같다
export function bestExcerptSentence(cited: string, excerpt: string, eid?: string): number | null {
  const sentences = excerptSentences(excerpt).map((s) => grams(s, NGRAM_N));
  const df = new Map<string, number>();
  for (const set of sentences) for (const g of set) df.set(g, (df.get(g) ?? 0) + 1);
  const weight = (g: string) =>
    BOILERPLATE_GRAMS.has(g) ? 0 : Math.log((sentences.length + 1) / (df.get(g) ?? 1));
  const scores = sentences.map(() => 0);
  for (const claim of citedClaims(cited, eid)) {
    const target = grams(claim, NGRAM_N);
    let total = 0;
    for (const g of target) total += weight(g);
    if (total <= 0) continue;
    for (let i = 0; i < sentences.length; i += 1) {
      let covered = 0;
      for (const g of target) if (sentences[i]!.has(g)) covered += weight(g);
      scores[i] = Math.max(scores[i]!, covered / total);
    }
  }
  let best: number | null = null;
  let top = 0;
  for (let i = 0; i < scores.length; i += 1) {
    if (scores[i]! > top) {
      top = scores[i]!;
      best = i;
    }
  }
  return top >= EXCERPT_MATCH_MIN ? best : null;
}

// 대목을 그대로 이어 붙인 조각 — 강조할 문장(bestExcerptSentence)만 mark. 조각을 이으면 원문 글자 그대로다.
// eid 는 누른 칩의 근거 번호(CitePick.eid — bestExcerptSentence 에 그대로 넘긴다)
export function excerptParts(excerpt: string, cited: string, eid?: string): { text: string; mark: boolean }[] {
  const best = bestExcerptSentence(cited, excerpt, eid);
  const parts: { text: string; mark: boolean }[] = [];
  const push = (text: string, mark: boolean) => {
    if (!text) return;
    const last = parts[parts.length - 1];
    if (last && last.mark === mark) last.text += text;
    else parts.push({ text, mark });
  };
  let index = 0;
  for (const piece of excerpt.split(SENTENCE_SPLIT_KEEP)) {
    if (!piece.trim()) {
      push(piece, false);
      continue;
    }
    // 문장 앞뒤 공백은 강조 밖에 둔다
    const lead = piece.length - piece.trimStart().length;
    const core = piece.trim();
    push(piece.slice(0, lead), false);
    push(core, index === best);
    push(piece.slice(lead + core.length), false);
    index += 1;
  }
  return parts;
}

// [원문 보기] — 대목이 있으면 그 쪽에서 연다(저장값은 0부터 센다 — citedPdfTarget 이 뷰어 쪽으로 +1, 0 은 쪽 없이).
// 대목이 없으면(초록만) 논문을 처음부터 연다
export function citationPdfTarget(source: SectionSource, title: string): OpenPdfPayload {
  const excerpt = source.excerpt;
  if (!excerpt) return { cntsId: source.cnts_id, title };
  const start = excerpt.page_start ?? 0;
  return citedPdfTarget(source.cnts_id, title, [{ page_start: start, page_end: excerpt.page_end ?? start }]);
}
