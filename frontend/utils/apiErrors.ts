// frontend/utils/apiErrors.ts
// API 오류를 화면 문구로 바꾸는 공통 규칙(순수 함수 — Vue 의존 없음). 모든 화면이 같은 규칙으로 오류를 말하게 한다.
//  - httpStatus(err)     : $fetch 오류의 HTTP 상태. 정의는 여기 한 곳 — researchErrors 도 여기서 가져간다
//  - errorKind(err)      : 오류의 종류(네트워크·시간 초과·몰림·서버·없음·입력·충돌·권한·그 밖) — 화면 상태(SkxErrorState 의 kind)에 그대로 넘긴다
//  - isAbortError(err)   : 우리가 일부러 끊은 요청(AbortController.abort)인가 — 그렇다면 오류를 보이지 않는다
//  - apiErrorMessage(err, fallback): 화면에 보일 문구 하나. 영문 기술 메시지(err.message)는 어떤 경우에도 쓰지 않는다
//  - toUserError(err, fallback): 위 셋을 한 번에 — 일부러 끊은 요청이면 null(아무것도 띄우지 않는다), 아니면 {kind, message}
//  - charCountState(length, max, near?)·charLimitMessage(max): 글자 수 표시(SkxCharCount)의 상태와 한도 안내
//  - codeMessage(code)   : 백엔드 오류 code 의 문구(CODE_MESSAGES)
// 공통 오류 컴포넌트가 스스로 그리는 고정 문구(ERROR_PAGE_TEXT·CONNECTION_HINTS)도 여기 둔다 — 오류 화면 모음(/dev/error-states)이
// 같은 상수를 읽어 문구 원문을 보이므로, 문구를 고치면 실제 화면과 모음이 함께 바뀐다.
// 문구는 해요체다(사용자 결정 2026-10-16 — 오류·실패·빈 상태는 '~했어요'·'~해 주세요'·'~예요'·'~없어요')

/**
 * 대체 문구(fallback) 뒤에 ' — ' 로 붙이는 이유. 여기 없는 kind(notFound·conflict·invalid·forbidden·unknown)는 대체 문구만 보인다 —
 * 서버가 한글 사유를 주면 그것을 먼저 쓰고, 없으면 '무엇을 못 했는지'가 이미 대체 문구에 있어 덧붙일 이유가 없다.
 * 문구 검토는 이 상수와 아래 CODE_MESSAGES·VALIDATION_HINTS·DEFAULT_ERROR_MESSAGE 만 보면 된다
 */
export const ERROR_HINTS = {
  network: "네트워크 연결을 확인해 주세요",
  timeout: "응답이 늦어 멈췄어요. 잠시 뒤 다시 시도해 주세요",
  busy: "요청이 몰려 있어요. 잠시 뒤 다시 시도해 주세요",
  server: "서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요",
} as const;

/**
 * 백엔드 오류 code 별 문구 — 응답 본문 {detail, code}(HTTP)·DeepRead 스트림 {error, code} 의 code 로 고른다.
 * 서버 detail 은 쓰지 않는다 — 서버가 문구를 바꿔도 화면 말투(해요체)가 섞이지 않게 문구는 프런트가 가진다.
 * apiErrorMessage 는 HTTP 의 code(internal_error·search_unavailable·storage_unavailable)를 ERROR_HINTS 처럼 이유 자리에 쓴다
 * (대체 문구 뒤 ' — '). not_found·empty_answer·retrieval_failed 는 DeepRead 스트림의 code 다
 */
export const CODE_MESSAGES = {
  internal_error: "서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요",
  search_unavailable: "검색 서버가 잠시 응답하지 않아요. 잠시 뒤 다시 시도해 주세요",
  storage_unavailable: "원문 저장소가 잠시 응답하지 않아요. 잠시 뒤 다시 시도해 주세요",
  not_found: "자료를 찾을 수 없어요",
  empty_answer: "답을 만들지 못했어요",
  retrieval_failed: "자료 내용을 읽지 못했어요. 잠시 뒤 다시 시도해 주세요",
} as const;
export type ErrorCode = keyof typeof CODE_MESSAGES;

/** code 의 문구 — 모르는 code·문자열이 아닌 값이면 null(호출부가 제 규칙으로 고른다) */
export function codeMessage(code: unknown): string | null {
  // Object.hasOwn 은 사파리 15.4 전에 없어 hasOwnProperty 로 — 'toString' 같은 상속 이름에 속지 않게 자기 키만 본다
  return typeof code === "string" && Object.prototype.hasOwnProperty.call(CODE_MESSAGES, code)
    ? CODE_MESSAGES[code as ErrorCode]
    : null;
}

/**
 * FastAPI 422(pydantic 검증 실패) 안내 — {n} 은 서버가 준 글자 수(tooLong 은 ctx.max_length, tooShort 는 ctx.min_length).
 * 1자 이상(=비면 안 됨)은 글자 수보다 '입력하라'가 자연스러워 required 를 쓴다
 */
export const VALIDATION_HINTS = {
  tooLong: "{n}자까지 입력할 수 있어요",
  tooShort: "{n}자 이상 입력해 주세요",
  required: "내용을 입력해 주세요",
  invalid: "입력값이 올바르지 않아요",
} as const;

/** 글자 수 표시(SkxCharCount)의 상태 — 평소 / 한도 가까이 / 한도 */
export type CharCountState = "normal" | "near" | "limit";

/**
 * 글자 수 상태. 한도에 닿으면(length >= max) 'limit', near 이상이면 'near'. near 를 주지 않으면 max 의 90%(소수점 아래 버림) —
 * 0.9 곱셈은 부동소수 오차(510 * 0.9 = 459.00000000000006)가 생겨 정수로만 셈한다
 */
export function charCountState(length: number, max: number, near?: number): CharCountState {
  if (length >= max) return "limit";
  const nearAt = near ?? Math.floor((max * 9) / 10);
  return length >= nearAt ? "near" : "normal";
}

/** 글자 수 한도에 닿았을 때의 안내 — 서버 422(string_too_long) 안내와 같은 말('500자까지 입력할 수 있어요') */
export function charLimitMessage(max: number): string {
  return VALIDATION_HINTS.tooLong.replace("{n}", String(max));
}

/** 대체 문구도 이유도 없을 때 — apiErrorMessage 는 빈 문자열을 돌려주지 않는다(빈 오류 칸이 그려지지 않게) */
export const DEFAULT_ERROR_MESSAGE = "요청을 처리하지 못했어요";

/** 전역 오류 화면(SkxErrorPage — error.vue 가 그린다)의 문구. 404 는 notFound, 그 밖(화면을 그리다 난 치명 오류)은 fatal */
export const ERROR_PAGE_TEXT = {
  notFound: { title: "페이지를 찾을 수 없어요", message: "주소가 바뀌었거나 없는 페이지예요." },
  fatal: { title: "문제가 생겼어요", message: "잠시 뒤 다시 시도해 주세요." },
  home: "처음 화면으로",
} as const;

/**
 * 실시간 연결(딥리서치 진행 화면·연구 작업대의 SSE) 끊김 띠(SkxConnectionBanner)의 문구.
 * reconnecting: 끊겨 다시 붙는 중(백오프 재연결이 도는 동안) / lost: 다시 붙지 못함 — 받은 화면이 낡았을 수 있다
 */
export const CONNECTION_HINTS = {
  reconnecting: "연결이 끊겨 다시 연결하는 중이에요…",
  lost: "연결하지 못했어요. 화면이 최신 상태가 아닐 수 있어요",
} as const;
export type ConnectionState = keyof typeof CONNECTION_HINTS;
/** 연결 끊김 띠(lost)의 버튼 글 */
export const CONNECTION_RETRY_LABEL = "다시 연결";

/** 대체 문구와 이유 사이 — 기존 화면 문구('… — 네트워크 연결을 확인해 주세요')와 같은 줄표 */
const HINT_SEPARATOR = " — ";

export type ErrorKind =
  | "network"
  | "timeout"
  | "busy"
  | "server"
  | "notFound"
  | "invalid"
  | "conflict"
  | "forbidden"
  | "unknown";

/**
 * 상태 블록(SkxErrorState)의 kind — ErrorKind 에 두 가지를 더한다.
 *  'error': 이유를 가리지 않는 일반 실패(컴포넌트 기본값). errorKind(err) 를 넘기면 더 구체적인 모양을 쓸 수 있다
 *  'empty': 실패가 아닌 빈 결과(검색 결과 없음·기록 없음 등)
 */
export type ErrorStateKind = ErrorKind | "error" | "empty";

/** toUserError 의 결과 — 화면은 kind 를 SkxErrorState 에, message 를 글로 쓴다 */
export interface UserFacingError {
  kind: ErrorKind;
  message: string;
}

interface FetchLikeError {
  status?: number;
  statusCode?: number;
  response?: { status?: number };
}

/** $fetch 오류의 HTTP 상태 — ofetch FetchError 는 status·statusCode, 직접 만든 오류는 response.status 에 둔다. 응답이 없으면 undefined */
export function httpStatus(err: unknown): number | undefined {
  if (!err || typeof err !== "object") return undefined;
  const e = err as FetchLikeError;
  return e.status ?? e.statusCode ?? e.response?.status;
}

interface ErrorLike {
  name?: unknown;
  message?: unknown;
  cause?: unknown;
}

function errorName(err: unknown): string {
  return err && typeof err === "object" && typeof (err as ErrorLike).name === "string" ? ((err as ErrorLike).name as string) : "";
}

function causeOf(err: unknown): unknown {
  return err && typeof err === "object" ? (err as ErrorLike).cause : undefined;
}

function messageOf(err: unknown): string {
  if (typeof err === "string") return err;
  const message = err && typeof err === "object" ? (err as ErrorLike).message : undefined;
  return typeof message === "string" ? message : "";
}

/** ofetch FetchError 가 든 요청 옵션의 signal 이 끊긴 이유(signal.reason) — 없으면 undefined */
function signalReason(err: unknown): unknown {
  if (!err || typeof err !== "object") return undefined;
  const options = (err as { options?: unknown }).options;
  const signal = options && typeof options === "object" ? (options as { signal?: unknown }).signal : undefined;
  return signal && typeof signal === "object" ? (signal as { reason?: unknown }).reason : undefined;
}

const TIMEOUT_RE = /timeout|timed out/i;

/**
 * 응답 없이 시간 초과로 끊겼는가. ofetch 1.5.1 은 options.timeout 이 지나면 name 'TimeoutError' 인 Error 로 끊고(FetchError.cause),
 * AbortSignal.timeout·useApi 의 대체 타이머는 이유를 'TimeoutError' 로 끊는다(native fetch 면 그 자체가, $fetch 면 cause 가 된다).
 * 오래된 엔진은 signal 을 그 이유로 끊어도 fetch 가 AbortError 로 실패한다 — 그래서 FetchError 가 든 options.signal 의 이유도 본다.
 * 셋 다 아니어도 메시지에 timeout 이 있으면 시간 초과로 본다 — cause 가 있으면 cause 의 메시지만 본다
 * (FetchError 메시지에는 요청 주소가 들어 있어 주소의 낱말에 속지 않게)
 */
function isTimeoutError(err: unknown): boolean {
  const cause = causeOf(err);
  if (errorName(err) === "TimeoutError" || errorName(cause) === "TimeoutError") return true;
  if (errorName(signalReason(err)) === "TimeoutError") return true;
  return TIMEOUT_RE.test(messageOf(cause !== undefined ? cause : err));
}

/** native fetch 가 서버에 닿지 못했을 때의 TypeError 문구 — 크롬·파이어폭스·사파리·Node(undici) */
const FETCH_FAILURE_RE = /failed to fetch|fetch failed|networkerror|load failed|network request failed|network connection was lost/i;

/**
 * 응답 없이 끝난 요청의 실패인가 — 이것만 네트워크·시간 초과로 본다. 응답을 가공하다 난 코드 버그(TypeError·SyntaxError 등)를
 * 네트워크 문제로 알리면 사용자는 고장이 아닌 연결만 살피게 된다.
 *  - ofetch 의 FetchError(상태 없음): 연결 실패·시간 초과·끊김을 cause 로 든다
 *  - native fetch: 연결 실패는 TypeError('Failed to fetch' 류), signal 로 끊기면 DOMException(TimeoutError·AbortError)
 */
function isRequestFailure(err: unknown): boolean {
  const name = errorName(err);
  if (name === "FetchError" || name === "TimeoutError" || name === "AbortError") return true;
  return name === "TypeError" && FETCH_FAILURE_RE.test(messageOf(err));
}

/**
 * 우리가 일부러 끊은 요청인가(AbortController.abort — 화면을 떠남·새 검색이 이전 검색을 끊음). 시간 초과는 아니다.
 * 호출부는 이것이 true 면 오류 표시를 건너뛴다(toUserError 는 null). native fetch 는 DOMException 'AbortError' 를,
 * $fetch 는 그것을 cause 로 든 FetchError 를 던진다
 */
export function isAbortError(err: unknown): boolean {
  if (isTimeoutError(err)) return false;
  return errorName(err) === "AbortError" || errorName(causeOf(err)) === "AbortError";
}

/**
 * 오류의 종류. 상태 코드가 없으면(상태 0 — 불투명 응답 — 도 같다) 응답 없이 끝난 요청의 실패일 때만 시간 초과·네트워크이고,
 * 그 밖(코드 버그·이상한 값)은 'unknown' 이다. 일부러 끊은 요청도 'network' 로 나오니 호출부는 isAbortError 를 먼저 본다
 */
export function errorKind(err: unknown): ErrorKind {
  const status = httpStatus(err);
  if (!status) {
    if (!isRequestFailure(err)) return "unknown";
    return isTimeoutError(err) ? "timeout" : "network";
  }
  if (status === 408 || status === 504) return "timeout";
  if (status === 429 || status === 503) return "busy";
  if (status >= 500 && status <= 599) return "server";
  if (status === 404 || status === 410) return "notFound";
  if (status === 400 || status === 413 || status === 422) return "invalid";
  if (status === 409) return "conflict";
  if (status === 401 || status === 403) return "forbidden";
  return "unknown";
}

interface ValidationItem {
  type?: unknown;
  ctx?: { max_length?: unknown; min_length?: unknown } | null;
}

function positiveInt(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;
}

/**
 * FastAPI 422 의 detail 배열([{type, loc, msg, ctx}])을 사람 말로. pydantic 의 영문 msg 는 쓰지 않는다.
 * 여러 항목이면 알아볼 수 있는 첫 항목(길이 초과·길이 미달)을 쓰고, 없으면 일반 문구. 배열이 아니면 null.
 * missing(필드가 아예 빠짐)은 사용자가 아니라 화면이 요청을 잘못 만든 것이라 알아볼 항목으로 치지 않는다 — 일반 문구
 */
export function validationMessage(detail: unknown): string | null {
  if (!Array.isArray(detail)) return null;
  for (const item of detail) {
    if (!item || typeof item !== "object") continue;
    const { type, ctx } = item as ValidationItem;
    const limits = ctx && typeof ctx === "object" ? ctx : {};
    // 서버 문구('3000자를 넘습니다')처럼 쉼표 없이 쓴다
    if (type === "string_too_long") {
      const max = positiveInt(limits.max_length);
      if (max) return VALIDATION_HINTS.tooLong.replace("{n}", String(max));
    }
    if (type === "string_too_short") {
      const min = positiveInt(limits.min_length);
      return min && min >= 2 ? VALIDATION_HINTS.tooShort.replace("{n}", String(min)) : VALIDATION_HINTS.required;
    }
  }
  return VALIDATION_HINTS.invalid;
}

/** 오류 응답 본문의 detail(FastAPI) — 본문이 없거나 JSON 이 아니면 undefined */
function errorDetail(err: unknown): unknown {
  if (!err || typeof err !== "object") return undefined;
  const data = (err as { data?: unknown }).data;
  return data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : undefined;
}

/** 오류 응답 본문의 code({detail, code} — 서버가 경우를 갈라 붙인 기계용 이름). 없으면 undefined */
function responseCode(err: unknown): unknown {
  if (!err || typeof err !== "object") return undefined;
  const data = (err as { data?: unknown }).data;
  return data && typeof data === "object" ? (data as { code?: unknown }).code : undefined;
}

const HANGUL_RE = /[가-힣]/;
/**
 * 개발자용 문구의 표시 — 라틴 문자(예외 원문·변수·필드·헤더 이름: 'PDF 없음: NoSuchKey…'·'x-session-id 헤더가 필요하다'),
 * 중괄호(f-string·dict 를 그대로 찍음), 따옴표(repr 로 찍힌 값: "int 여야 한다: 'x'")
 */
const DEV_TEXT_RE = /[A-Za-z{}'"`]/;

/**
 * 서버가 사람에게 보이라고 지은 사유 — 문자열 detail 또는 구조화 detail({code, message, …})의 message.
 * 한글이 있고 개발자용 표시가 없는 깨끗한 문장일 때만 돌려준다(앞뒤 공백은 걷는다). 영문(프레임워크 기본 문구)·한영이 섞인
 * 개발자용 문구·배열(422 검증 실패 — validationMessage 몫)은 null
 */
export function serverMessage(detail: unknown): string | null {
  let text: unknown = detail;
  if (detail && typeof detail === "object") {
    if (Array.isArray(detail)) return null;
    text = (detail as { message?: unknown }).message;
  }
  if (typeof text !== "string") return null;
  const trimmed = text.trim();
  return trimmed && HANGUL_RE.test(trimmed) && !DEV_TEXT_RE.test(trimmed) ? trimmed : null;
}

/** 구조화 detail 에 code 가 있는가 — 서버가 경우를 갈라 일부러 지은 응답이라는 표시 */
function hasDetailCode(detail: unknown): boolean {
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return false;
  const code = (detail as { code?: unknown }).code;
  return typeof code === "string" && code.trim() !== "";
}

/**
 * 화면에 보일 문구 하나를 고른다.
 *  (0) 응답 본문의 code 가 CODE_MESSAGES 에 있으면 서버 detail 대신 그 문구를 이유로 — fallback 뒤 ' — '(fallback 이 비면 그 문구만).
 *      서버 문구의 말투가 화면과 섞이지 않게 프런트의 문구를 쓴다
 *  (a) 서버의 깨끗한 한글 사유(serverMessage)면 그대로. 단 5xx 는 code 가 있는 구조화 detail 이거나 503(서버가 지은 '잠시 뒤' 안내)일 때만 —
 *      그 밖의 5xx 문구는 예외를 감싼 개발자용('잡 생성 실패: …')일 수 있어 (c) 로 간다
 *  (b) 422 검증 실패 배열이면 validationMessage
 *  (c) 그 밖에는 fallback(무엇을 못 했는지) 뒤에 kind 별 이유(ERROR_HINTS)를 붙인다 — 이유가 없는 kind 는 fallback 만,
 *      fallback 도 비면 DEFAULT_ERROR_MESSAGE(빈 문자열은 돌려주지 않는다)
 * err.message(영문 기술 메시지)는 어떤 경우에도 쓰지 않는다. 일부러 끊은 요청은 호출부가 isAbortError 로 먼저 거른다(toUserError)
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const base = typeof fallback === "string" ? fallback.trim() : "";
  const byCode = codeMessage(responseCode(err));
  if (byCode) return withHint(base, byCode);
  const status = httpStatus(err);
  const detail = errorDetail(err);
  const reason = serverMessage(detail);
  const isServerError = !!status && status >= 500 && status <= 599;
  if (reason && (!isServerError || status === 503 || hasDetailCode(detail))) return reason;
  if (status === 422 && Array.isArray(detail)) return validationMessage(detail)!;
  const kind = errorKind(err);
  const hint = kind in ERROR_HINTS ? ERROR_HINTS[kind as keyof typeof ERROR_HINTS] : null;
  if (!hint) return base || DEFAULT_ERROR_MESSAGE;
  return withHint(base, hint);
}

/** 무엇을 못 했는지(base) 뒤에 이유 — base 가 비면 이유만 */
function withHint(base: string, hint: string): string {
  return base ? `${base}${HINT_SEPARATOR}${hint}` : hint;
}

/**
 * 화면이 쓰기 편한 한 번에 — catch 에서 `const shown = toUserError(e, '결과를 불러오지 못했어요'); if (shown) …`.
 * 일부러 끊은 요청(isAbortError)이면 null(화면은 아무것도 띄우지 않는다), 아니면 kind(SkxErrorState 의 kind)와 apiErrorMessage 의 문구
 */
export function toUserError(err: unknown, fallback: string): UserFacingError | null {
  if (isAbortError(err)) return null;
  return { kind: errorKind(err), message: apiErrorMessage(err, fallback) };
}
