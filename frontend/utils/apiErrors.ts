// frontend/utils/apiErrors.ts
// API 오류를 화면 문구로 바꾸는 공통 규칙(순수 함수 — Vue 의존 없음). 모든 화면이 같은 규칙으로 오류를 말하게 한다.
//  - errorKind(err)      : 오류의 종류(네트워크·시간 초과·몰림·서버·없음·입력·충돌·권한·그 밖) — 화면 상태(SkxErrorState 의 kind)에 그대로 넘긴다
//  - isAbortError(err)   : 우리가 일부러 끊은 요청(AbortController.abort)인가 — 그렇다면 오류를 보이지 않는다
//  - apiErrorMessage(err, fallback): 화면에 보일 문구 하나. 영문 기술 메시지(err.message)는 어떤 경우에도 쓰지 않는다
// httpStatus 는 researchErrors 의 것을 그대로 쓴다(중복 정의 금지). researchErrors 가 이 파일을 가져가면 순환이 되니,
// 연구 화면 문구를 이 규칙으로 옮길 때는 researchErrors 의 httpStatus 를 이 파일로 옮기는 쪽이 낫다
import { httpStatus } from "./researchErrors";

/**
 * 대체 문구(fallback) 뒤에 ' — ' 로 붙이는 이유. 여기 없는 kind(notFound·conflict·invalid·forbidden·unknown)는 대체 문구만 보인다 —
 * 서버가 한글 사유를 주면 그것을 먼저 쓰고, 없으면 '무엇을 못 했는지'가 이미 대체 문구에 있어 덧붙일 이유가 없다.
 * 문구 검토는 이 상수와 아래 VALIDATION_HINTS 두 곳만 보면 된다
 */
export const ERROR_HINTS = {
  network: "네트워크 연결을 확인하세요",
  timeout: "응답이 늦어 멈췄습니다. 잠시 뒤 다시 시도하세요",
  busy: "요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요",
  server: "서버에 문제가 생겼습니다. 잠시 뒤 다시 시도하세요",
} as const;

/** FastAPI 422(pydantic 검증 실패) 안내 — tooLong 의 {n} 은 서버가 준 최대 글자 수(ctx.max_length) */
export const VALIDATION_HINTS = {
  tooLong: "{n}자까지 입력할 수 있습니다",
  required: "내용을 입력해 주세요",
  invalid: "입력값이 올바르지 않습니다",
} as const;

/** 대체 문구와 이유 사이 — 기존 화면 문구('… — 네트워크 연결을 확인하세요')와 같은 줄표 */
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

const TIMEOUT_RE = /timeout|timed out/i;

function messageOf(err: unknown): string {
  if (typeof err === "string") return err;
  const message = err && typeof err === "object" ? (err as ErrorLike).message : undefined;
  return typeof message === "string" ? message : "";
}

/**
 * 응답 없이 시간 초과로 끊겼는가. ofetch 1.5.1 은 options.timeout 이 지나면 name 'TimeoutError' 인 Error 로 끊고(FetchError.cause),
 * AbortSignal.timeout 은 DOMException 'TimeoutError' 로 끊는다(native fetch 면 그 자체가, $fetch 면 cause 가 된다).
 * 둘 다 아니어도 메시지에 timeout 이 있으면 시간 초과로 본다 — cause 가 있으면 cause 의 메시지만 본다
 * (FetchError 메시지에는 요청 주소가 들어 있어 주소의 낱말에 속지 않게)
 */
function isTimeoutError(err: unknown): boolean {
  const cause = causeOf(err);
  if (errorName(err) === "TimeoutError" || errorName(cause) === "TimeoutError") return true;
  return TIMEOUT_RE.test(messageOf(cause !== undefined ? cause : err));
}

/**
 * 우리가 일부러 끊은 요청인가(AbortController.abort — 화면을 떠남·새 검색이 이전 검색을 끊음). 시간 초과는 아니다.
 * 호출부는 이것이 true 면 오류 표시를 건너뛴다. native fetch 는 DOMException 'AbortError' 를, $fetch 는 그것을 cause 로 든 FetchError 를 던진다
 */
export function isAbortError(err: unknown): boolean {
  if (isTimeoutError(err)) return false;
  return errorName(err) === "AbortError" || errorName(causeOf(err)) === "AbortError";
}

/**
 * 오류의 종류. 상태 코드가 없으면(요청이 서버에 닿지 못함) 시간 초과 아니면 네트워크다 — 일부러 끊은 요청도 'network' 로 나오니
 * 호출부는 isAbortError 를 먼저 본다. 상태 0(불투명 응답)도 상태 없음으로 본다
 */
export function errorKind(err: unknown): ErrorKind {
  const status = httpStatus(err);
  if (!status) return isTimeoutError(err) ? "timeout" : "network";
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
  ctx?: { max_length?: unknown } | null;
}

/**
 * FastAPI 422 의 detail 배열([{type, loc, msg, ctx}])을 사람 말로. pydantic 의 영문 msg 는 쓰지 않는다.
 * 여러 항목이면 알아볼 수 있는 첫 항목(길이 초과·비어 있음)을 쓰고, 없으면 일반 문구. 배열이 아니면 null
 */
export function validationMessage(detail: unknown): string | null {
  if (!Array.isArray(detail)) return null;
  for (const item of detail) {
    if (!item || typeof item !== "object") continue;
    const { type, ctx } = item as ValidationItem;
    if (type === "string_too_long") {
      const max = ctx && typeof ctx === "object" ? ctx.max_length : undefined;
      // 서버 문구('3000자를 넘습니다')처럼 쉼표 없이 쓴다
      if (typeof max === "number" && Number.isInteger(max) && max > 0) {
        return VALIDATION_HINTS.tooLong.replace("{n}", String(max));
      }
    }
    if (type === "string_too_short" || type === "missing") return VALIDATION_HINTS.required;
  }
  return VALIDATION_HINTS.invalid;
}

/** 오류 응답 본문의 detail(FastAPI) — 본문이 없거나 JSON 이 아니면 undefined */
function errorDetail(err: unknown): unknown {
  if (!err || typeof err !== "object") return undefined;
  const data = (err as { data?: unknown }).data;
  return data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : undefined;
}

const HANGUL_RE = /[가-힣]/;

/** 서버가 사람에게 보이라고 준 한글 사유 — 문자열 detail 또는 구조화 detail 의 message. 영문(프레임워크 기본 문구)은 null */
function serverReason(detail: unknown): string | null {
  let text: unknown = detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) text = (detail as { message?: unknown }).message;
  if (typeof text !== "string") return null;
  const trimmed = text.trim();
  return trimmed && HANGUL_RE.test(trimmed) ? trimmed : null;
}

/**
 * 화면에 보일 문구 하나를 고른다.
 *  (a) 서버가 한글 사유를 주면 그대로(HTTPException 문구·구조화 detail {message})
 *  (b) 422 검증 실패 배열이면 validationMessage
 *  (c) 그 밖에는 fallback(무엇을 못 했는지) 뒤에 kind 별 이유(ERROR_HINTS)를 붙인다 — 이유가 없는 kind 는 fallback 만
 * err.message(영문 기술 메시지)는 어떤 경우에도 쓰지 않는다. 일부러 끊은 요청은 호출부가 isAbortError 로 먼저 거른다
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const detail = errorDetail(err);
  const reason = serverReason(detail);
  if (reason) return reason;
  if (httpStatus(err) === 422 && Array.isArray(detail)) return validationMessage(detail)!;
  const kind = errorKind(err);
  const hint = kind in ERROR_HINTS ? ERROR_HINTS[kind as keyof typeof ERROR_HINTS] : null;
  const base = fallback.trim();
  if (!hint) return base;
  return base ? `${base}${HINT_SEPARATOR}${hint}` : hint;
}
