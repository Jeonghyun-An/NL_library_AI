// frontend/utils/bookErrors.ts
// 랜딩 소장자료 검색·SKOVIX 추천 1권·도서 상세·상황별 추천의 오류·빈 상태 — 화면이 SkxErrorState·SkxInlineError 에 넘길 문구와 판정
// (순수 함수 — Vue 의존 없음). 문구는 해요체(사용자 결정 2026-10-16)이고, 두 문장이면 문장 사이를 '\n' 으로 잇는다.
// 상태 블록의 제목은 '무엇을 못 했는지', 설명 줄은 이유만(논문 화면과 같은 규칙 paperErrors.shownError — 이유가 없으면 빈 글,
// 영문 err.message·서버 영문 detail 은 쓰지 않는다)
// 검색어 글자 수 한도(SEARCH_QUERY_MAX)는 논문 검색과 같은 값이라 utils/searchInput.ts 한 곳에 둔다
import type { ErrorStateKind } from "./apiErrors";
import { shownError } from "./paperErrors";

/** 소장자료 검색(랜딩 → 결과 화면) */
export const BOOK_SEARCH_TEXT = {
  failedTitle: "검색하지 못했어요",
  emptyTitle: "검색 결과가 없어요",
  emptyMessage: "다른 말로 바꿔 다시 찾아봐 주세요.",
} as const;

/**
 * 주소(?h=)의 검색 기록을 복원하지 못했고 다시 찾을 검색어도 없을 때의 토스트(pages/index.vue). 토스트는 한 줄(white-space: nowrap)이라
 * '\n' 이 보이지 않아 한 문장으로 둔다. missing 은 서버가 그 기록이 없다고 답했을 때, unavailable 은 서버에 닿지 못했고 이 브라우저의
 * 사본에도 없어 있는지 없는지 모를 때다(논문 검색의 PAPER_STATE_TEXT.missingHistory·historyUnavailable 과 같은 말)
 */
export const BOOK_HISTORY_TEXT = {
  missing: "없는 기록이라 목록을 새로 고쳤어요.",
  unavailable: "연결이 불안정해 기록을 불러오지 못했어요.",
} as const;

/**
 * 추천 이유 스트림(/books/reason/stream — 결과의 SKOVIX 추천 1권·도서 상세의 [추천 이유] 탭·보존 화면)이 끝까지 오지 않았을 때.
 * 서버가 보낸 {error} 글(합쇼체)은 보이지 않는다 — 말투는 프런트가 가진다. 글 없이 실패(HTTP 오류·네트워크·{error}, 또는 끝까지 왔는데
 * 글이 없음 — 새 서버는 LLM 빈 답을 {error} 로 보내고 옛 서버는 빈 채로 [DONE] 을 보낸다)면 failed, 글 일부를 받은 뒤 실패(연결 끊김·{error})면
 * partial. 둘 다 [다시 시도]가 처음부터 다시 받는다
 */
export const BOOK_REASON_TEXT = {
  failed: "추천 이유를 불러오지 못했어요",
  partial: "추천 이유를 끝까지 받지 못했어요",
} as const;

/** 도서 상세(pages/books/[cnts_id].vue) */
export const BOOK_DETAIL_TEXT = {
  notFoundTitle: "도서를 찾을 수 없어요",
  // 서버 404 는 서지 DB(GET /books/{id} — app/api/book.py get_book)에 그 자료의 행이 없을 때다. 이 화면은 거의 앱 안 링크(검색 결과·
  // 관련 자료·상황별 추천)로 들어오므로 '주소를 확인하라'가 아니라 자료가 없다는 사실을 말한다
  notFoundMessage: "목록에서 빠졌거나 아직 등록되지 않은 자료예요.",
  failedTitle: "도서 정보를 불러오지 못했어요",
  home: "홈으로",
  curationEmpty: "AI 큐레이션 정보가 없어요",
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
  // 목록에 없는 상황 번호(/recommend/99 등) — 예전엔 첫 상황(01)을 대신 그렸다. 추천을 묻지 않고 찾을 수 없음 상태로 알린다([다른 상황 고르기])
  unknownTitle: "없는 상황이에요",
  unknownMessage: "목록에서 다른 상황을 골라 주세요.",
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
 * 설명 줄은 논문 화면(paperErrors.shownError)과 같은 규칙으로 고른 이유만이다 — 연결·시간 초과·몰림·서버 오류·서버 code·422 글자 수·
 * 깨끗한 한글 서버 사유는 그대로, 이유가 없는 kind(찾을 수 없음·권한·충돌·그 밖)는 빈 글이라 제목과 [다시 시도]만 보인다.
 * '요청을 처리하지 못했어요'(DEFAULT_ERROR_MESSAGE)를 제목 아래 되풀이하지 않는다(소장자료 검색·도서 상세·관련 자료·상황별 추천 모두).
 * notFound 를 주면 404·410 은 그 상태(다시 시도 없음 — 같은 주소로 다시 물어도 없다)로 바꾼다. 입력이 틀린 요청(400·413·422 — 검색어
 * 500자 초과 등)도 같은 입력으로 다시 보내면 또 거절되므로 [다시 시도]를 달지 않는다(설명 줄이 고칠 점을 말한다)
 */
export function failureView(
  err: unknown,
  title: string,
  notFound?: { kind: ErrorStateKind; title: string; message: string },
): StateView | null {
  const shown = shownError(err);
  if (!shown) return null;
  if (notFound && shown.kind === "notFound") return { ...notFound, retry: false };
  return { kind: shown.kind, title, message: shown.message, retry: shown.kind !== "invalid" };
}

/** 추천 이유가 끝까지 오지 않았을 때의 한 줄 — 받은 글이 있으면 partial, 없으면 failed(BOOK_REASON_TEXT) */
export function reasonFailureText(received: string): string {
  return received.trim() ? BOOK_REASON_TEXT.partial : BOOK_REASON_TEXT.failed;
}

/**
 * 상황 번호(주소의 /recommend/{id})가 상황 목록(표)에 있는가 — 없으면 화면은 다른 상황을 대신 그리지 않고 SCENARIO_TEXT.unknown* 를 보인다.
 * 'toString'·'__proto__' 같은 상속 이름에 속지 않게 자기 키만 본다(apiErrors codeMessage 와 같은 방식). 문자열이 아니면(배열 등) false
 */
export function isKnownScenario(table: Record<string, unknown>, id: unknown): id is string {
  return typeof id === "string" && Object.prototype.hasOwnProperty.call(table, id);
}

/**
 * 상황별 추천 응답의 ai_failed — 새 서버만 보낸다(LLM 사유 생성 실패면 true, 소개·사유가 빈 값). 옛 서버(필드 없음)·이상한 값은 false 라
 * 화면은 예전처럼 소개(없으면 시나리오 기본 문구)를 보인다
 */
export function scenarioAiFailed(data: unknown): boolean {
  return !!data && typeof data === "object" && (data as { ai_failed?: unknown }).ai_failed === true;
}
