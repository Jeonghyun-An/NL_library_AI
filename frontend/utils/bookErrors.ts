// frontend/utils/bookErrors.ts
// 랜딩 소장자료 검색·SKOVIX 추천 1권·도서 상세·상황별 추천의 오류·빈 상태 — 화면이 SkxErrorState·SkxInlineError 에 넘길 문구와 판정
// (순수 함수 — Vue 의존 없음). 문구는 해요체(사용자 결정 2026-10-16)이고, 두 문장이면 문장 사이를 '\n' 으로 잇는다.
// 상태 블록의 제목은 '무엇을 못 했는지', 설명 줄은 이유(apiErrorMessage(err, '') — 영문 err.message·서버 영문 detail 은 쓰지 않는다)
import { apiErrorMessage, errorKind, isAbortError, type ErrorStateKind } from "./apiErrors";

/** 검색어 글자 수 한도 — 서버 SearchRequest.query(max_length=500, app/schemas/book.py)와 같다. 랜딩 두 입력창·결과 검색바의 maxlength */
export const SEARCH_QUERY_MAX = 500;

/** 소장자료 검색(랜딩 → 결과 화면) */
export const BOOK_SEARCH_TEXT = {
  failedTitle: "검색하지 못했어요",
  emptyTitle: "검색 결과가 없어요",
  emptyMessage: "다른 말로 바꿔 다시 찾아봐 주세요.",
} as const;

/**
 * 추천 이유 스트림(/books/reason/stream — 결과의 SKOVIX 추천 1권·도서 상세의 [추천 이유] 탭)이 끝까지 오지 않았을 때.
 * 서버가 보낸 {error} 글(합쇼체)은 보이지 않는다 — 말투는 프런트가 가진다. 글 없이 실패(HTTP 오류·네트워크·{error})면 failed,
 * 글 일부를 받은 뒤 실패(연결 끊김·{error})면 partial. 둘 다 [다시 시도]가 처음부터 다시 받는다
 */
export const BOOK_REASON_TEXT = {
  failed: "추천 이유를 불러오지 못했어요",
  partial: "추천 이유를 끝까지 받지 못했어요",
} as const;

/** 도서 상세(pages/books/[cnts_id].vue) */
export const BOOK_DETAIL_TEXT = {
  notFoundTitle: "도서를 찾을 수 없어요",
  notFoundMessage: "주소가 맞는지 다시 확인해 주세요.",
  failedTitle: "도서 정보를 불러오지 못했어요",
  home: "홈으로",
  curationEmpty: "AI 큐레이션 정보가 없어요",
  reasonEmpty: "추천 이유가 없어요",
  relatedFailedTitle: "관련 자료를 불러오지 못했어요",
  relatedEmptyTitle: "관련 자료가 없어요",
} as const;

/** 상황별 추천(pages/recommend/[id].vue — POST /scenario/recommend) */
export const SCENARIO_TEXT = {
  failedTitle: "추천 도서를 불러오지 못했어요",
  // 서버는 이 고민으로 찾은 도서가 없으면 404 를 준다(app/api/scenario.py) — 고장이 아니라 빈 결과다
  emptyTitle: "추천할 도서를 찾지 못했어요",
  emptyMessage: "다른 상황을 골라 주세요.",
  pickAnother: "다른 상황 고르기",
  // 새 서버의 ai_failed=true — LLM 이 소개·추천 사유를 만들지 못해 빈 값으로 왔다(도서는 그대로 왔다)
  aiFailed: "추천 이유를 만들지 못했어요",
} as const;

/** 상태 블록(SkxErrorState) 하나에 넘길 것 — retry 가 false 면 [다시 시도]를 달지 않는다 */
export interface StateView {
  kind: ErrorStateKind;
  title: string;
  message: string;
  retry: boolean;
}

/**
 * 요청 실패를 상태 블록으로. 일부러 끊은 요청(화면을 떠남·새 검색이 이전 검색을 끊음)이면 null — 아무것도 띄우지 않는다.
 * notFound 를 주면 404·410 은 그 상태(다시 시도 없음 — 같은 주소로 다시 물어도 없다)로 바꾼다. 입력이 틀린 요청(400·413·422 — 검색어
 * 500자 초과 등)도 같은 입력으로 다시 보내면 또 거절되므로 [다시 시도]를 달지 않는다(설명 줄이 고칠 점을 말한다)
 */
export function failureView(
  err: unknown,
  title: string,
  notFound?: { kind: ErrorStateKind; title: string; message: string },
): StateView | null {
  if (isAbortError(err)) return null;
  const kind = errorKind(err);
  if (notFound && kind === "notFound") return { ...notFound, retry: false };
  return { kind, title, message: apiErrorMessage(err, ""), retry: kind !== "invalid" };
}

/** 추천 이유가 끝까지 오지 않았을 때의 한 줄 — 받은 글이 있으면 partial, 없으면 failed(BOOK_REASON_TEXT) */
export function reasonFailureText(received: string): string {
  return received.trim() ? BOOK_REASON_TEXT.partial : BOOK_REASON_TEXT.failed;
}

/**
 * 상황별 추천 응답의 ai_failed — 새 서버만 보낸다(LLM 사유 생성 실패면 true, 소개·사유가 빈 값). 옛 서버(필드 없음)·이상한 값은 false 라
 * 화면은 예전처럼 소개(없으면 시나리오 기본 문구)를 보인다
 */
export function scenarioAiFailed(data: unknown): boolean {
  return !!data && typeof data === "object" && (data as { ai_failed?: unknown }).ai_failed === true;
}
