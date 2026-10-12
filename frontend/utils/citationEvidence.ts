// frontend/utils/citationEvidence.ts
// 인용 근거 탭(보고서 단계 오른쪽 패널, D24 A안)의 판단 — 누른 인용 칩의 문장과 그 문장을 쓸 때 모델에 넘긴 원문 대목
// (GET …/sections/{key}/sources 의 excerpt)을 견줘 대목 쪽에서 강조할 문장을 고른다. 리랭커 점수는 쓰지 않는다(대회
// 뒤) — 화면이 글자 n-gram 겹침만 센다(spec §12-4 하이라이트). 본문 쪽 강조는 누른 칩이 든 문장이다(sentenceFlags 의 번호).
// 겹침이 모자라면 아무 문장도 강조하지 않는다 — 뒷받침하지 않는 문장을 근거처럼 보이지 않는다(spec '인용이라는 말을 정확히')
import type { OpenPdfPayload } from "~/types/research";
import type { SectionSource } from "~/types/work";
import { citedPdfTarget } from "~/utils/pdfViewer";

// 글자 2-gram — 한국어는 조사·어미가 붙어 낱말 단위로는 같은 말이 잘 겹치지 않는다
export const NGRAM_N = 2;
// 강조하려면 인용 문장 2-gram(무게를 단)의 이만큼은 그 대목 문장이 덮어야 한다 — 무관한 문장이 어미·흔한 낱말
// ('였다'·'하였'·'연구')만으로 넘는 일이 없게. 맞는 문장(번역·요약하지 않은 것)은 대개 0.3 을 넘는다
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

// 두 글의 글자 n-gram(서로 다른 것) 가운데 겹친 수. [E#]·[F#] 표기·공백·문장부호는 빼고, NFKC·소문자로 맞춘 뒤 센다
export function ngramOverlap(a: string, b: string, n: number = NGRAM_N): number {
  const left = grams(a, n);
  let count = 0;
  for (const g of grams(b, n)) if (left.has(g)) count += 1;
  return count;
}

// 인용한 문장을 가장 많이 덮는 대목 문장의 번호(excerptSentences 순서). 덮는 정도 = 인용 문장 2-gram 가운데 그 문장에도
// 있는 것의 무게 합 ÷ 인용 문장 2-gram 의 무게 합(0~1). 무게는 대목 안 IDF — ln((대목 문장 수 + 1) ÷ 그 2-gram 이 나오는
// 대목 문장 수(대목에 없으면 1)): 여러 문장에 두루 나오는 어미·흔한 낱말은 가볍고 한 문장에만 나오는 말이 무거워, 흔한
// 말을 많이 품은 긴 문장으로 쏠리지 않는다. 대목이 한 문장이면 무게가 모두 같아 그냥 덮는 비율이다. 같으면 앞 문장,
// 가장 큰 값이 EXCERPT_MATCH_MIN 아래면 null(번역·요약해 쓴 문장도 여기로 온다 — 화면은 강조 없이 대목 전체를 보인다)
export function bestExcerptSentence(cited: string, excerpt: string): number | null {
  const sentences = excerptSentences(excerpt).map((s) => grams(s, NGRAM_N));
  const df = new Map<string, number>();
  for (const set of sentences) for (const g of set) df.set(g, (df.get(g) ?? 0) + 1);
  const weight = (g: string) => Math.log((sentences.length + 1) / (df.get(g) ?? 1));
  const target = grams(cited, NGRAM_N);
  let total = 0;
  for (const g of target) total += weight(g);
  if (total <= 0) return null;
  let best: number | null = null;
  let top = 0;
  for (let i = 0; i < sentences.length; i += 1) {
    let covered = 0;
    for (const g of target) if (sentences[i]!.has(g)) covered += weight(g);
    const score = covered / total;
    if (score > top) {
      top = score;
      best = i;
    }
  }
  return top >= EXCERPT_MATCH_MIN ? best : null;
}

// 대목을 그대로 이어 붙인 조각 — 강조할 문장(bestExcerptSentence)만 mark. 조각을 이으면 원문 글자 그대로다
export function excerptParts(excerpt: string, cited: string): { text: string; mark: boolean }[] {
  const best = bestExcerptSentence(cited, excerpt);
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
