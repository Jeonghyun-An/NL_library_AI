// frontend/utils/bookAiPick.ts
// 소장자료 검색 결과의 AI 영역: 1위 도서 한 권 + 왜 이 책인가 + 이 책에서 얻을 수 있는 것.
// 화면 상태 없이 순수하게 도는 부분만 여기 둔다
import type { BookAiPick } from "~/types/history";

/** 1위 도서 점수(best_score)가 이 미만이면 'SKOVIX 추천 1권'으로 내세우지 않는다 — 옛 AI 컬렉션의 포함 기준(0.4)과 같다 */
export const MIN_PICK_SCORE = 0.4;

/** 서버(app/core/config.py REASON_CHUNKS_DISPLAY_LIMIT)가 어차피 15 개에서 자른다 — 보내는 양도 맞춘다 */
export const REASON_CHUNK_LIMIT = 15;

interface ChunkLike {
  text: string;
  score?: number;
  rerank_score?: number;
}

export interface BookLike {
  book_id?: unknown;
  book_info?: { read_effect?: string | null } | null;
  chunks?: readonly ChunkLike[];
}

export interface ReasonBody {
  query: string;
  rewritten_query: string;
  book_id: string;
  chunk_texts: string[];
}

/** 1위 도서 = 검색이 준 순서의 맨 앞. 재정렬하지 않는다(결과 목록과 같은 1위). book_id 없는 항목은 건너뛴다 */
export function pickTopBook<T extends BookLike>(books: readonly T[] | null | undefined): T | null {
  if (!Array.isArray(books)) return null;
  return books.find((b) => typeof b?.book_id === "string" && b.book_id !== "") ?? null;
}

/** 1위 도서를 추천으로 내세울 만큼 질문과 맞는가(점수 MIN_PICK_SCORE 이상). 아니면 화면은 안내만 두고 추천 이유도 부르지 않는다 */
export function isRecommendable(book: { best_score?: unknown } | null | undefined): boolean {
  const score = book?.best_score;
  return typeof score === "number" && score >= MIN_PICK_SCORE;
}

/** '이 책에서 얻을 수 있는 것' — 검색 응답의 book_info.read_effect. 비면 빈 문자열(화면이 블록을 숨긴다) */
export function readEffectOf(book: BookLike | null | undefined): string {
  const v = book?.book_info?.read_effect;
  return typeof v === "string" ? v.trim() : "";
}

/**
 * /books/reason/stream 요청 본문. 매칭 구절은 관련도 높은 순 상위 REASON_CHUNK_LIMIT 개 — 복원한 도서는 구절이 없다(서버가 요약·줄거리로 쓴다).
 * rewritten_query 는 비운다: 고쳐 쓴 검색어는 키워드 나열("조선시대 소설 연구, 고전 소설 비평, …")이라 서버가 이유 글 첫 문장에
 * 그대로 따다 써 어색하다. 원문 검색어만 주면 같은 책에도 자연스러운 문장이 나온다
 */
export function buildReasonBody(query: string, book: BookLike & { book_id: unknown }): ReasonBody {
  const chunks = [...(book.chunks ?? [])]
    .sort((a, b) => (b.rerank_score ?? b.score ?? 0) - (a.rerank_score ?? a.score ?? 0))
    .slice(0, REASON_CHUNK_LIMIT);
  return {
    query: query.trim(),
    rewritten_query: "",
    book_id: String(book.book_id),
    chunk_texts: chunks.map((c) => c.text),
  };
}

/** 문자열 목록에서 앞뒤 공백을 떼고 빈 것·문자열이 아닌 것을 뺀다 */
function cleanKeywords(list: unknown): string[] {
  if (!Array.isArray(list)) return [];
  return list.filter((k): k is string => typeof k === "string").map((k) => k.trim()).filter(Boolean);
}

/** 기록에 저장할 AI 영역 — 끝난 추천 이유와 그 이유가 가리키는 1위 도서 id, 서버가 준 키워드(있을 때만) */
export function buildBookAi(bookId: string, reason: string, keywords: readonly string[] = []): BookAiPick {
  const kw = cleanKeywords(keywords);
  return kw.length ? { book_id: bookId, reason: reason.trim(), keywords: kw } : { book_id: bookId, reason: reason.trim() };
}

/**
 * 기록의 AI 영역에서 저장된 추천 이유를 꺼낸다. 쓸 수 없으면 null — 호출한 화면이 한 번 다시 받아 새 모양으로 덮는다.
 * 옛 AI 컬렉션 기록({intro, items})·모양이 틀린 값·1위 도서가 달라진 기록이 모두 여기로 온다
 */
export function readSavedReason(ai: unknown, topBookId: string | null): string | null {
  if (!topBookId || typeof ai !== "object" || ai === null || Array.isArray(ai)) return null;
  const { book_id, reason } = ai as Record<string, unknown>;
  if (book_id !== topBookId || typeof reason !== "string") return null;
  return reason.trim() || null;
}

/** 기록의 AI 영역에 저장된 키워드. 1위 도서가 다르거나 없거나 모양이 틀리면 빈 목록 */
export function readSavedKeywords(ai: unknown, topBookId: string | null): string[] {
  if (!topBookId || typeof ai !== "object" || ai === null || Array.isArray(ai)) return [];
  const { book_id, keywords } = ai as Record<string, unknown>;
  return book_id === topBookId ? cleanKeywords(keywords) : [];
}

/**
 * 추천 이유 SSE 를 읽어 text 조각마다 onText 를, 첫 이벤트 {keywords}(도서의 MARC 키워드)가 오면 onKeywords 를 부른다. 이벤트: {keywords}·{text}·{effect}·[DONE].
 * 서버는 추천 이유(text) 뒤에 독후 효과(effect)를 이어 만든다 — 화면은 검색 응답의 read_effect 를 쓰므로 effect 가 오면
 * 이유는 끝난 것이고, 읽기를 취소해 연결을 끊는다(서버가 쓰지 않을 글을 더 만들지 않게).
 * 끝까지 받았으면 true, [DONE] 도 effect 도 없이 끊겼으면 false(저장하지 않는다). 읽기 중 abort 는 그대로 던진다
 */
export async function readReasonStream(
  body: ReadableStream<Uint8Array>,
  onText: (delta: string) => void,
  onKeywords?: (keywords: string[]) => void,
): Promise<boolean> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return false;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") return true;
        let event: Record<string, unknown>;
        try {
          event = JSON.parse(raw);
        } catch {
          continue;
        }
        if (typeof event !== "object" || event === null) continue;
        if ("effect" in event) return true;
        if (onKeywords && "keywords" in event) {
          const kw = cleanKeywords(event.keywords);
          if (kw.length) onKeywords(kw);
        }
        if (typeof event.text === "string" && event.text) onText(event.text);
      }
    }
  } finally {
    // 일찍 끝낼 때만 의미가 있다 — 끝까지 읽은 스트림에는 그대로 무해하다. 이미 닫혔거나 취소된 스트림의 취소 실패는 무시한다
    void reader.cancel().catch(() => undefined);
  }
}
