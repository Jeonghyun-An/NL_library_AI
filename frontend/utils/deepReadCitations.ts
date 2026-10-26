// frontend/utils/deepReadCitations.ts
// DeepRead 답의 근거 표시(요청 2026-10-23) — 답 글 속 쪽 표기([p.3]·[p.2, p.19]·(p.25)·p.3–4)를 누를 수 있는 쪽 번호로 바꾸고,
// 아래 '근거 N곳' 목록을 같은 쪽끼리 묶는다. 전에는 글에 '[p.2, p.19]'·'[쪽 정보 없음]'이 글자로 찍히고, 아래 칩은 'p.2 p.19 p.19'처럼
// 쪽만 있어 같은 쪽 두 대목이 무엇이 다른지 눌러 봐야 알았다.
// 쪽은 사람이 보는 쪽(저장값 +1, citations.pageLabel)이다 — 서버도 LLM 문맥 머리를 같은 쪽으로 싣고(book_chat._context_label)
// 답에서 그 쪽을 언급한 대목만 sources 로 보낸다(_find_cited_hits: 'p.N' 은 N 쪽에서 시작하는 대목과 맞는다)
import { marked } from "marked";
import { pageLabel } from "~/utils/citations";
import type { DeepReadSource } from "~/utils/deepReadSse";
import { MARKDOWN_CODE, escapeTildeText } from "~/utils/markdown";
import { passageText } from "~/utils/passageText";

/** 같은 쪽 표기(label)의 대목 묶음 — 목록 한 줄 */
export interface SourceGroup {
  /** 'p.3'·'p.3–4' */
  label: string;
  /** 사람이 보는 시작·끝 쪽 */
  start: number;
  end: number;
  passages: DeepReadSource[];
  /** 목록 줄에 보이는 첫 대목의 머리 글(한 줄) */
  snippet: string;
}

/** 글 속 쪽 번호를 단추로 만들 때 — 답 번호·그 답의 근거 묶음·펼친 묶음 */
export interface CiteLink {
  msg: number;
  groups: readonly SourceGroup[];
  active?: number;
}

// 한 쪽 표기 — 'p.3'·'p.3–4'·'p. 3 - 4'. 괄호 안 두 번째부터는 'p.' 없이 '19' 로도 쓴다('[p.2, 19]')
const ITEM = String.raw`(?:p\.\s?)?\d+(?:\s?[–\-~]\s?\d+)?`;
// 괄호 안 표기 목록 — 첫 표기는 'p.' 로 시작해야 한다('(2021)' 같은 연도·숫자 괄호는 건드리지 않는다)
const LIST = String.raw`p\.\s?\d+(?:\s?[–\-~]\s?\d+)?(?:\s*[,，;·]\s*${ITEM})*`;
// 겹괄호 '([p.2])'(2026-10-23 운영 답) — 양쪽이 짝을 이룰 때만 바깥 괄호까지 먹는다. 한쪽만 겹치면('(무작위 배정, [p.3]).'·
// '결과([p.3] 참조)') 안쪽 '[p.3]'만 바꿔 바깥 괄호 짝이 그대로 남는다
const DOUBLE = String.raw`\(\s*\[\s*(${LIST})\s*\]\s*\)`;
const SINGLE = String.raw`[\[(]\s*(${LIST})\s*[\])]`;
// 괄호 없이 글 속에 쓴 'p.25' — 앞이 글자·숫자·점이 아닐 때만('pp.3'·'ap.3' 은 아니다)
const BARE = String.raw`(?<![\w.])p\.\s?(\d+)(?:\s?[–\-~]\s?(\d+))?`;
const CITE = new RegExp(`${DOUBLE}|${SINGLE}|${BARE}`, "g");
const ITEM_RE = /(\d+)(?:\s?[–\-~]\s?(\d+))?/;
const SEP = /[,，;·]/;
// LLM 문맥에서 쪽이 없는 대목의 머리(book_chat._context_label). 프롬프트가 옮기지 말라 해도 답 글에 그대로 옮길 때가 있어(2026-10-23
// 운영 화면) 사람에게 보이지 않게 걷는다 — 목록 속 한 항목이면 구분자와 함께, 겹괄호면 바깥 괄호까지, 홀로면 앞 공백과 함께
const NO_PAGE_HEAD = String.raw`[\[(]\s*쪽\s?정보\s?없음\s*[\])]`;
const NO_PAGE_RULES: readonly [RegExp, string][] = [
  // 문맥의 요약 머리('[논문 요약]'·'[자료 요약]')를 모델이 '[요약]'·'[요약, p.20]'으로 옮겨 적는다(2026-10-26 운영 답 42개 중 5개) —
  // 쪽과 함께면 쪽만 남기고, 홀로면 앞 공백과 함께 걷는다
  [/\[\s*(?:논문\s|자료\s)?요약\s*[,，]\s*/g, "["],
  [/[ \t]*[\[(]\s*(?:논문\s|자료\s)?요약\s*[\])]/g, ""],
  // 앞에 다른 표기가 붙은 괄호째('[표 4-2, 쪽 정보 없음]') — 2026-10-26 운영 답에서 걷히지 않고 글자로 남았다
  [new RegExp(String.raw`[ \t]*[\[(][^\[\]()
]{1,40}?[,，]\s*쪽\s?정보\s?없음\s*[\])]`, "g"), ""],
  [new RegExp(String.raw`\s*[,，;·]\s*${NO_PAGE_HEAD}`, "g"), ""],
  [new RegExp(String.raw`${NO_PAGE_HEAD}\s*[,，;·]\s*`, "g"), ""],
  [new RegExp(String.raw`[ \t]*\(\s*\[\s*쪽\s?정보\s?없음\s*\]\s*\)`, "g"), ""],
  [new RegExp(String.raw`[ \t]*${NO_PAGE_HEAD}`, "g"), ""],
];
// 마크다운 코드(코드 블록·코드 칸 — utils/markdown) 안은 HTML 이 살지 않아 쪽 번호로 바꾸지 않고 글자 그대로 둔다
const CODE = MARKDOWN_CODE;
// 쪽 번호 자리표시 — 사설 영역 글자로 감싼다. marked 가 강조(**…**)를 판단할 때 문장부호로 보지 않아 '**p.3**에'도 굵게 그려진다
// (HTML 태그를 먼저 넣으면 닫는 '**' 앞이 '>' 가 되어 강조가 닫히지 않았다). marked 를 거친 뒤 단추 HTML 로 바꾼다
const MARK_OPEN = "";
const MARK_CLOSE = "";
const MARK = /(\d+)/g;
const SNIPPET_MAX = 120;

/** 사람이 보는 쪽 범위 — 쪽 정보가 없으면 null */
function shownRange(src: DeepReadSource): { start: number; end: number } | null {
  if (!src.page_start || src.page_start <= 0) return null;
  const start = src.page_start + 1;
  return { start, end: Math.max(src.page_end + 1, start) };
}

function rangeLabel(start: number, end: number): string {
  return end > start ? `p.${start}–${end}` : `p.${start}`;
}

/** 글 속 쪽 표기가 가리키는 묶음 — 같은 표기가 먼저, 없으면 그 쪽에서 시작하는 묶음(서버가 대목을 고르는 규칙), 그다음 그 쪽을 품은 묶음 */
export function groupForPages(groups: readonly SourceGroup[], start: number, end: number): number {
  const label = rangeLabel(start, Math.max(end, start));
  const exact = groups.findIndex((g) => g.label === label);
  if (exact !== -1) return exact;
  const starts = groups.findIndex((g) => g.start === start);
  if (starts !== -1) return starts;
  return groups.findIndex((g) => g.start <= start && start <= g.end);
}

/** 쪽 표기 매치 하나의 표기들 — 괄호 목록이면 여럿, 괄호 없는 표기면 하나 */
function matchPages(m: RegExpMatchArray | string[]): { start: number; end: number }[] {
  const list = m[1] ?? m[2];
  if (list !== undefined) {
    return list
      .split(SEP)
      .map((item) => ITEM_RE.exec(item))
      .filter((im): im is RegExpExecArray => im !== null)
      .map((im) => ({ start: Number(im[1]), end: Number(im[2] ?? im[1]) }));
  }
  return [{ start: Number(m[3]), end: Number(m[4] ?? m[3]) }];
}

/** 글에서 쪽 표기를 차례로 — 사람이 보는 시작·끝 쪽과 글 속 자리. 코드 안은 세지 않는다(자리가 어긋나지 않게 같은 길이로 비운다) */
function citedPages(answer: string): { start: number; end: number; at: number }[] {
  const prose = answer.replace(CODE, (code) => " ".repeat(code.length));
  const out: { start: number; end: number; at: number }[] = [];
  for (const m of prose.matchAll(CITE)) {
    for (const p of matchPages(m)) out.push({ ...p, at: m.index! });
  }
  return out;
}

/** 출처 대목을 쪽 표기로 묶는다 — 답 글에서 먼저 언급한 쪽이 위로, 언급을 찾지 못한 묶음은 그 뒤에 쪽 순서로. 쪽 정보 없는 대목은 뺀다 */
export function groupSources(sources: readonly DeepReadSource[] | undefined, answer: string): SourceGroup[] {
  const groups: SourceGroup[] = [];
  for (const src of sources ?? []) {
    const range = shownRange(src);
    if (!range) continue;
    const label = pageLabel(src);
    const found = groups.find((g) => g.label === label);
    if (found) found.passages.push(src);
    else groups.push({ label, ...range, passages: [src], snippet: snippetOf(src.text) });
  }
  const firstMention = new Map<SourceGroup, number>();
  for (const c of citedPages(answer)) {
    const gi = groupForPages(groups, c.start, c.end);
    if (gi !== -1 && !firstMention.has(groups[gi]!)) firstMention.set(groups[gi]!, c.at);
  }
  return groups
    .map((g, i) => ({ g, i }))
    .sort((a, b) => {
      const ma = firstMention.get(a.g) ?? Infinity;
      const mb = firstMention.get(b.g) ?? Infinity;
      if (ma !== mb) return ma - mb;
      return a.g.start - b.g.start || a.i - b.i;
    })
    .map(({ g }) => g);
}

/** 목록 줄의 머리 글 — 대목을 화면 글로 정리해(passageText) 줄바꿈·겹친 공백을 한 칸으로 */
function snippetOf(text: string): string {
  const flat = passageText(text).replace(/\s+/g, " ").trim();
  return flat.length > SNIPPET_MAX ? `${flat.slice(0, SNIPPET_MAX)}…` : flat;
}

/** 쪽 표기 하나의 HTML — 가리키는 묶음이 있으면 누르는 단추, 없거나(아직 받는 중·쪽이 출처에 없음) 그리는 글이면 모양만 */
function citeChip(start: number, end: number, link: CiteLink | null): string {
  const label = rangeLabel(start, Math.max(end, start));
  const gi = link ? groupForPages(link.groups, start, end) : -1;
  if (!link || gi === -1) return `<span class="skx-chat-cite is-static">${label}</span>`;
  const active = link.active === gi ? " is-active" : "";
  return (
    `<button type="button" class="skx-chat-cite${active}" data-msg="${link.msg}" data-cite="${gi}" ` +
    `aria-label="${label} 원문 보기">${label}</button>`
  );
}

/** 쪽 정보 없음 머리를 걷는다(코드 밖 글에만) */
function stripNoPage(text: string): string {
  return NO_PAGE_RULES.reduce((acc, [re, to]) => acc.replace(re, to), text);
}

/**
 * 답 글(마크다운)을 HTML 로 — 쪽 표기는 쪽 번호로, '[쪽 정보 없음]'은 걷는다. 코드 블록·코드 칸 안은 글자 그대로 둔다.
 * link 가 있으면(받기를 마친 답) 출처 묶음을 가리키는 단추, 없으면(받는 중·실패한 글·낭독용) 모양만 같은 글자다.
 * 쪽 번호는 자리표시로 marked 를 거친 뒤 HTML 로 바꾼다(강조 판단이 쪽 표기 글자를 그대로 보게). 물결표는 쪽 표기를 읽은 뒤
 * 글자로 바꾼다('p.3~4' 는 쪽 번호로, '2006~2010년 … 2005~2009년' 은 취소선이 아닌 글자로 — utils/markdown)
 */
export function renderAnswer(answer: string, link: CiteLink | null): string {
  if (!answer) return "";
  const chips: string[] = [];
  const markdown = answer
    .split(CODE)
    .map((part, k) =>
      k % 2 === 1
        ? part
        : escapeTildeText(
            stripNoPage(part).replace(CITE, (...args: string[]) => {
              const pages = matchPages(args);
              if (pages.length === 0) return args[0]!;
              const html = pages.map((p) => citeChip(p.start, p.end, link));
              // 여럿이면 줄바꿈에 갈리지 않게 한 덩이로
              chips.push(html.length > 1 ? `<span class="skx-chat-cite-group">${html.join("")}</span>` : html[0]!);
              return `${MARK_OPEN}${chips.length - 1}${MARK_CLOSE}`;
            }),
          ),
    )
    .join("");
  const html = marked.parse(markdown) as string;
  return html.replace(MARK, (_, n: string) => chips[Number(n)] ?? "");
}
