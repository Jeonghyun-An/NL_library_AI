// frontend/utils/summaryExcerpt.ts
// 논문 검색 AI 요약(/papers/summary/stream — pages/papers/index.vue streamAiSummary)에 논문마다 싣는 발췌(best_chunk_text).
// 원문 초록(book_info.abstract)을 먼저 쓰고, 초록이 비었을 때만 색인 때 만든 요약(book_info.summary)의 본문을, 둘 다 없으면 빈 글을 보낸다.
// 초록이 목적 한두 문장뿐일 만큼 짧으면 색인 요약 본문을 뒤에 이어 붙인다 — 결과가 없는 초록만 받은 요약이 결과를 지어냈다.
// 국문 초록 뒤에 같은 내용의 영문 초록이 붙어 있으면 영문 쪽은 걷는다 — 서버가 자르는 길이를 번역이 먹어 국문 결론이 잘렸다.
// 검색 결과의 chunks(질의에 가장 맞은 조각)는 쓰지 않는다 — 참고문헌 목록 조각일 때가 있다.
// 앞머리 표지 걷기와 문장 경계 자르기(_MAX_EXCERPT_CHARS)는 서버가 한다(app/services/search/paper_summary.py _clean_excerpt·_truncate_at_sentence)

/** 요약이 읽는 논문 수 — 서버 _MAX_PAPERS 와 같다. 검색 결과(서버 순서) 앞에서부터 이만큼 보낸다 */
export const SUMMARY_PAPER_LIMIT = 5;
/** 초록이 이보다 짧으면 색인 요약 본문을 덧붙인다. 국문 초록 뒤 영문 초록도 국문이 이만큼은 될 때만 걷는다 */
export const SHORT_ABSTRACT_CHARS = 400;
// 영문 초록을 걷는 국문 초록의 한글 음절 수 하한 — 영문 초록만 있는 논문의 'Abstract' 줄을 국문·영문 경계로 잘못 읽지 않게
const KOREAN_HEAD_MIN_HANGUL = 100;
// 영문 초록인지 보는 머리 줄 뒤 글자 수 — 이 안에 한글이 거의 없어야 영문 초록이다
const TWIN_PROBE_CHARS = 100;

export interface ExcerptInfo {
  abstract?: unknown;
  summary?: unknown;
}

/** 고른 발췌 — 초록·색인 요약 본문 중 쓴 것만. 기록 스냅샷(utils/historySnapshot)이 같은 필드 이름으로 담아, 복원한 기록에서도 같은 글을 고른다 */
export interface ExcerptParts {
  abstract?: string;
  summary?: string;
}

// 색인 요약의 옛 꼴('## SUMMARY: 본문 **관련 연구자가 검색할 학술 키워드:** …')에서 본문만 — 논문 상세의 초록 칸
// (pages/papers/[id].vue parseLegacySummary)과 같은 규칙. 옛 꼴이 아니면 앞뒤 공백만 걷는다
function legacySummaryBody(raw: unknown): string {
  if (typeof raw !== "string") return "";
  const text = raw.replace(/^\s*##\s*SUMMARY:\s*/i, "").trim();
  const kw = text.match(/\*\*관련\s*연구자가\s*검색할\s*학술\s*키워드\s*:\*\*/i);
  return (kw ? text.slice(0, kw.index) : text).trim();
}

// 줄 머리의 영문 초록 표지 — 'ABSTRACT'·'Abstract'·'English Abstract'·'영문 초록'(마크다운 '#'·'*' 장식, 끝의 쌍점 허용).
// 'Abstraction …' 처럼 낱말이 이어지는 줄은 표지가 아니다
const TWIN_HEAD = /\n[ \t]*(?:#{1,6}[ \t]*)?[*_]{0,2}[ \t]*(?:english[ \t]+abstract|abstract|영[ \t]*문[ \t]*초[ \t]*록)(?![a-z])[ \t]*[*_]{0,2}[ \t]*[:：]?/i;
const HANGUL = /[가-힣]/g;

function hangulCount(text: string): number {
  return text.match(HANGUL)?.length ?? 0;
}

// 국문 초록 뒤에 이어 붙은 영문 초록(같은 내용의 번역)을 걷는다. 앞이 넉넉한 국문 초록이고 표지 뒤가 영문일 때만 —
// 국문 쪽이 짧으면 영문 쪽에만 결과가 있을 수 있어 그대로 둔다
function dropEnglishTwin(text: string): string {
  const head = TWIN_HEAD.exec(text);
  if (!head) return text;
  const korean = text.slice(0, head.index).trim();
  if (korean.length < SHORT_ABSTRACT_CHARS || hangulCount(korean) < KOREAN_HEAD_MIN_HANGUL) return text;
  const probe = text.slice(head.index + head[0].length).replace(/\s+/g, "").slice(0, TWIN_PROBE_CHARS);
  if (!probe || hangulCount(probe) * 10 > probe.length) return text;
  return korean;
}

export function pickSummaryExcerpt(info: ExcerptInfo | null | undefined): ExcerptParts | null {
  if (!info) return null;
  const abstract = typeof info.abstract === "string" ? dropEnglishTwin(info.abstract.trim()) : "";
  const summary = abstract.length < SHORT_ABSTRACT_CHARS ? legacySummaryBody(info.summary) : "";
  if (!abstract && !summary) return null;
  return { ...(abstract ? { abstract } : {}), ...(summary ? { summary } : {}) };
}

/** 고른 발췌를 서버에 보낼 한 글로 — 초록 다음에 빈 줄을 두고 색인 요약 본문 */
export function joinExcerpt(parts: ExcerptParts | null): string {
  if (!parts) return "";
  return [parts.abstract, parts.summary].filter(Boolean).join("\n\n");
}

export function summaryExcerpt(book: { book_info?: ExcerptInfo | null }): string {
  return joinExcerpt(pickSummaryExcerpt(book.book_info));
}
