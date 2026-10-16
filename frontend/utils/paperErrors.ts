// frontend/utils/paperErrors.ts
// 논문 검색·결과 목록·논문 상세·출처 인용 화면의 오류·빈 상태 문구와 고르는 규칙(순수 함수 — Vue 의존 없음).
// 상태 블록(SkxErrorState)의 제목은 '무엇을 못 했는지·무엇이 없는지', 설명 줄은 오류 규칙(utils/apiErrors)이 고른 이유만이다 —
// 오류 화면 모음(/dev/error-states)의 본보기('검색하지 못했어요'·'논문 정보를 불러오지 못했어요'·'검색 결과가 없어요')와 같은 말.
// 문구는 해요체(사용자 결정 2026-10-16), 두 문장 이상이면 문장 사이를 '\n' 으로 잇고 줄마다 마침표로 끝낸다
import { DEFAULT_ERROR_MESSAGE, toUserError, type ErrorKind } from "./apiErrors";

/**
 * 검색어 한도 — 서버 SearchRequest.query 의 max_length(app/schemas/book.py)와 같다. 논문 입력창은 DeepResearch 질문도 받는데
 * 그 한도(app/api/research.py ResearchCreate.question)도 500 이다. 입력창의 maxlength 와 글자 수(SkxCharCount)가 함께 쓴다
 */
export const SEARCH_QUERY_MAX = 500;

/** 논문 화면들의 상태 블록·줄 안내 문구 */
export const PAPER_STATE_TEXT = {
  /** 논문 검색 요청 실패 — 결과 자리의 상태 블록 제목 */
  searchFailed: "검색하지 못했어요",
  /** 논문 검색 결과 0건 */
  searchEmpty: "검색 결과가 없어요",
  searchEmptyHint: "다른 검색어로 다시 검색해 주세요.",
  /** 요약 스트림이 글 없이 끝남(옛 서버의 빈 답·글 없는 기록) */
  summaryEmpty: "AI 요약이 없어요",
  /** 논문 상세 읽기 실패(404 밖) */
  detailFailed: "논문 정보를 불러오지 못했어요",
  /** 논문 상세 404 — 서버에 그 논문이 없다(주소 오타·옛 링크) */
  detailNotFound: "논문을 찾을 수 없어요",
  detailNotFoundHint: "주소가 맞는지 다시 확인해 주세요.",
  /** 상세의 AI 큐레이션 탭이 하나도 없음(요약·소개글·초록 모두 없음) */
  curationEmpty: "AI 큐레이션 정보가 없어요",
  /** 상세의 관련 자료(/papers/{id}/related) 읽기 실패 */
  relatedFailed: "관련 자료를 불러오지 못했어요",
  /** 관련 자료 0건 — 실패와 가른다 */
  relatedEmpty: "관련 자료가 없어요",
  /** 관련 논문 카드의 추천 사유가 비어 있음 */
  relatedReasonEmpty: "추천 사유가 없어요",
  /** 참고문헌 목록이 비어 있음(상세·출처 인용 창) */
  referencesEmpty: "참고문헌 정보가 없어요",
  /** 출처 인용 창의 인용문(/papers/{id}/citation) 읽기 실패 */
  citationFailed: "인용 정보를 불러오지 못했어요",
  /** 인용문이 비어 있음(그 언어의 인용문이 없음) */
  citationEmpty: "인용 정보가 없어요",
  /** 클립보드에 쓰지 못함 — 운영 게이트웨이가 http 라 Clipboard API 가 없을 수 있다(utils/clipboard) */
  copyFailed: "복사하지 못했어요.\n글을 직접 복사해 주세요.",
  /** 주소의 검색 기록(h)이 없고 다시 찾을 검색어도 없음 — 토스트 */
  missingHistory: "없는 기록이에요.\n목록을 새로 고쳤어요.",
  /** 원문 파일이 없을 때 건네는 외부(KCI) 원문 페이지 링크 */
  kciOriginal: "KCI에서 원문 페이지 열기",
} as const;

/** 화면이 쥐는 오류 — kind 는 SkxErrorState 의 kind, message 는 설명 줄(이유. 없으면 빈 글) */
export interface ShownError {
  kind: ErrorKind;
  message: string;
}

/**
 * catch 에서 화면에 보일 오류를 고른다 — 일부러 끊은 요청(새 검색·페이지 떠남)이면 null(아무것도 띄우지 않는다).
 * 설명 줄은 이유만이다(toUserError 에 대체 문구를 비워 넘긴다): 연결·시간 초과·몰림·서버 오류는 ERROR_HINTS, 서버 code 는 CODE_MESSAGES,
 * 422 는 글자 수 안내, 깨끗한 한글 서버 사유는 그대로. 이유가 없는 kind(찾을 수 없음 등)는 빈 글 — 제목이 이미 무엇을 못 했는지 말하고,
 * '요청을 처리하지 못했어요'(DEFAULT_ERROR_MESSAGE)를 제목 아래 되풀이하지 않는다. err.message(영문 기술 메시지)는 쓰지 않는다
 */
export function shownError(err: unknown): ShownError | null {
  const shown = toUserError(err, "");
  if (!shown) return null;
  return { kind: shown.kind, message: shown.message === DEFAULT_ERROR_MESSAGE ? "" : shown.message };
}

/** [다시 시도] 를 달 만한 오류인가 — 찾을 수 없음(404)·입력 거절(422 등)은 같은 요청을 다시 보내도 같은 결과라 달지 않는다 */
export function isRetryableKind(kind: ErrorKind): boolean {
  return kind !== "notFound" && kind !== "invalid";
}
