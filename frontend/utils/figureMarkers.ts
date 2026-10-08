// frontend/utils/figureMarkers.ts
// 계획서 글의 [E#](근거)·[F#](코드가 센 수치) 마커와 문장 표시. 서버(services/research_work/markers.py ·
// services/research/citations.bind_markers)가 검사해 표준형([E3]·[F1])으로 저장한 글을 그린다 — 숫자 검사와
// '근거 표시 없는 문장' 셈은 서버와 같은 규칙이어야 한다(frontend/tests/fixtures/marker_checks.json 이 둘을 묶는다)
import type { Figure } from "~/types/work";

export type MarkerPart = { type: "text"; text: string } | { type: "cite"; eid: string } | { type: "figure"; fid: string };

export interface SentenceFlag {
  text: string;
  // 근거 [E#] 가 없는 문장 — 점선 밑줄(spec §5-5)
  unmarked: boolean;
  // [E#]·[F#] 밖에 쓴 숫자 — '확인 필요'
  numbers: string[];
}

const MARKER = /\[(E\d+)\]|\[(F\d+)\]/g;
// 파이썬 re 의 \d 는 유니코드 숫자(Nd)다 — 전각 숫자도 같게 세려고 \p{Nd} 를 쓴다
const ANY_MARKER = /\[[EF]\p{Nd}+\]/gu;
const NUMBER = /(?<![A-Za-z0-9.\-])\p{Nd}+(?:[.,]\p{Nd}+)*(?![A-Za-z0-9])/gu;
const CITE = /\[E\d+\]/;
// 문장 끝(마침표·물음표·느낌표·고리점) 뒤 공백까지가 한 문장이다. 그 뒤에 붙은 [E#] 묶음은 앞 문장의 근거로 센다 —
// 서버의 _TRAILING_MARKER 가 마커를 마침표 앞으로 당겨 센 것과 같다. 원문 글자는 하나도 빼지 않는다
const SENTENCE_END = /[.!?。]\s+(?:\[E\d+\][ \t]*)*\s*/g;

// 다 받지 못한 끝 표기(스트리밍 중의 "[E"·"[F1")는 글자로 둔다 — 닫는 괄호가 오면 칩이 된다
export function splitMarkers(text: string): MarkerPart[] {
  const parts: MarkerPart[] = [];
  let last = 0;
  for (const m of text.matchAll(MARKER)) {
    const at = m.index ?? 0;
    if (at > last) parts.push({ type: "text", text: text.slice(last, at) });
    parts.push(m[1] ? { type: "cite", eid: m[1] } : { type: "figure", fid: m[2] ?? "" });
    last = at + m[0].length;
  }
  if (last < text.length) parts.push({ type: "text", text: text.slice(last) });
  return parts;
}

// 서버 markers.numbers_outside 와 같다 — 마커를 빈 글자로 지운 뒤, 영문자·숫자·점·하이픈에 붙지 않은 숫자(소수점·
// 천 단위 쉼표는 한 숫자)를 등장 순으로. "COVID-19"·"B2B"·"5G" 의 숫자는 이름의 일부라 세지 않는다
export function numbersOutside(text: string): string[] {
  return Array.from(text.replace(ANY_MARKER, "").matchAll(NUMBER), (m) => m[0]);
}

// 원문을 문장으로 나눈다 — 이어 붙이면 원문과 같고, unmarked 인 문장 수는 서버의 unmarked 와 같다
export function sentenceFlags(text: string): SentenceFlag[] {
  const out: SentenceFlag[] = [];
  const push = (piece: string) => {
    const blank = !piece.trim();
    out.push({ text: piece, unmarked: !blank && !CITE.test(piece), numbers: numbersOutside(piece) });
  };
  let start = 0;
  for (const m of text.matchAll(SENTENCE_END)) {
    const end = (m.index ?? 0) + m[0].length;
    push(text.slice(start, end));
    start = end;
  }
  if (start < text.length) push(text.slice(start));
  return out;
}

export function figureById(figures: readonly Figure[], fid: string): Figure | null {
  return figures.find((f) => f.id === fid) ?? null;
}
