// frontend/utils/markdown.ts
// LLM 이 쓴 마크다운을 화면 HTML 로 — 물결표(~)는 글자로 둔다. marked(GFM)는 '~글~'(물결표 하나)도 취소선으로 읽어,
// '2006~2010년 국가재정운용계획은 … 2005~2009년'처럼 범위를 두 번 쓴 답의 그 사이가 통째로 그어졌다(2026-10-23 운영 DeepRead 화면).
// 답 글에 취소선을 쓸 일은 없어 코드 밖의 '~'를 모두 '\~'(마크다운 글자 이스케이프)로 바꾼다. 코드 블록·코드 칸 안은 그대로 둔다
import { marked } from "marked";

// 마크다운 코드(코드 블록·코드 칸) — split 하면 홀수 번째가 코드다
export const MARKDOWN_CODE = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g;

/** 코드가 아닌 글 한 토막의 물결표를 글자로 */
export function escapeTildeText(text: string): string {
  return text.replace(/~/g, "\\~");
}

/** 마크다운 전체의 물결표를 글자로 — 코드 안은 건드리지 않는다 */
export function escapeTildes(markdown: string): string {
  return markdown
    .split(MARKDOWN_CODE)
    .map((part, k) => (k % 2 === 1 ? part : escapeTildeText(part)))
    .join("");
}

/** LLM 글(마크다운) → HTML. 빈 글은 빈 HTML */
export function renderMarkdown(markdown: string): string {
  return markdown ? (marked.parse(escapeTildes(markdown)) as string) : "";
}
