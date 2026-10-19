// frontend/utils/summaryExcerpt.ts
// 논문 검색 AI 요약(/papers/summary/stream — pages/papers/index.vue streamAiSummary)에 논문마다 싣는 발췌(best_chunk_text).
// 원문 초록(book_info.abstract)을 먼저 쓰고, 초록이 비었을 때만 색인 때 만든 요약(book_info.summary)의 본문을, 둘 다 없으면 빈 글을 보낸다.
// 검색 결과의 chunks(질의에 가장 맞은 조각)는 쓰지 않는다 — 참고문헌 목록 조각일 때가 있다.
// 앞머리 표지 걷기와 500자 자르기는 서버가 한다(app/services/search/paper_summary.py _clean_excerpt·_MAX_EXCERPT_CHARS)

/** 요약이 읽는 논문 수 — 서버 _MAX_PAPERS 와 같다. 검색 결과(서버 순서) 앞에서부터 이만큼 보낸다 */
export const SUMMARY_PAPER_LIMIT = 5;

export interface ExcerptInfo {
  abstract?: unknown;
  summary?: unknown;
}

export interface ExcerptPick {
  /** 고른 필드 — 기록 스냅샷(utils/historySnapshot)이 같은 이름으로 담아, 복원한 기록에서도 같은 쪽을 고른다 */
  field: "abstract" | "summary";
  text: string;
}

// 색인 요약의 옛 꼴('## SUMMARY: 본문 **관련 연구자가 검색할 학술 키워드:** …')에서 본문만 — 논문 상세의 초록 칸
// (pages/papers/[id].vue parseLegacySummary)과 같은 규칙. 옛 꼴이 아니면 앞뒤 공백만 걷는다
function legacySummaryBody(raw: unknown): string {
  if (typeof raw !== "string") return "";
  const text = raw.replace(/^\s*##\s*SUMMARY:\s*/i, "").trim();
  const kw = text.match(/\*\*관련\s*연구자가\s*검색할\s*학술\s*키워드\s*:\*\*/i);
  return (kw ? text.slice(0, kw.index) : text).trim();
}

export function pickSummaryExcerpt(info: ExcerptInfo | null | undefined): ExcerptPick | null {
  if (!info) return null;
  const abstract = typeof info.abstract === "string" ? info.abstract.trim() : "";
  if (abstract) return { field: "abstract", text: abstract };
  const summary = legacySummaryBody(info.summary);
  return summary ? { field: "summary", text: summary } : null;
}

export function summaryExcerpt(book: { book_info?: ExcerptInfo | null }): string {
  return pickSummaryExcerpt(book.book_info)?.text ?? "";
}
