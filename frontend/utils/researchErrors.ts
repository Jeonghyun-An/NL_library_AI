// frontend/utils/researchErrors.ts
// 연구 화면(DeepResearch·이어간 연구)의 오류 문구. 상태 읽기·서버 사유 고르기·422 문구는 utils/apiErrors 의 규칙을 그대로 쓴다 —
// httpStatus 는 apiErrors 에만 정의한다(여기서 다시 내보내면 Nuxt 자동 import 가 같은 이름을 두 번 만나 경고한다)
import { DEEP_RESEARCH } from "./brand";
import { ERROR_HINTS, errorKind, httpStatus, serverMessage, validationMessage } from "./apiErrors";

interface FetchLikeError {
  data?: unknown;
}

// FastAPI 는 HTTPException 이면 detail 을 문자열로, pydantic 검증 실패면 [{loc, msg, type, ctx}] 배열로 준다.
// 한 모양만 읽으면 다른 쪽은 "[object Object]" 가 된다. 구조화한 detail({code, message, …} — 429 browser_active·409 version_conflict)은
// message 를 읽는다. 문자열·message 는 한글만 있는 깨끗한 문장일 때만 쓰고(apiErrors.serverMessage — 'PDF 없음: {e}'·'상태다: running'
// 처럼 예외 원문·변수 값이 섞인 개발자용 문구는 null), 배열은 pydantic 의 영문 msg 대신 validationMessage 의 사람 말로 바꾼다
export function detailMessage(detail: unknown): string | null {
  if (Array.isArray(detail)) return validationMessage(detail);
  return serverMessage(detail);
}

// 원문 보기 전 확인 요청의 결과로 알릴 문구. null 이면 뷰어를 연다. 서버는 파일이 없을 때만
// 404 를 준다(api/book.get_book_pdf) — 5xx 까지 "없음"으로 알리면 있는 원문을 없다고 믿게 된다.
// status 가 null(확인 요청 자체가 실패)이면 판단하지 않고 뷰어가 직접 보여 주게 둔다.
export function pdfCheckProblem(status: number | null): string | null {
  if (status === null || (status >= 200 && status < 300)) return null;
  if (status === 404) return "원문 파일이 없어요";
  return "원문을 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요";
}

// 같은 브라우저의 다른 딥리서치가 진행 중이라 승인·재시도가 막혔다(api/research.py _to_run_queue 의 429
// detail {code: "browser_active", message, job_id}). 서버가 문구를 비워 보내도 같은 안내를 쓴다
const BROWSER_ACTIVE_MESSAGE = `진행 중인 ${DEEP_RESEARCH}가 있어요 — 끝나거나 취소한 뒤 다시 시작해 주세요`;

// 딥리서치 화면의 404 — 연구 주소가 잘못됐거나 지워졌다(링크만 알면 누구나 열 수 있어 권한 문제는 없다)
export const RESEARCH_NOT_FOUND = "찾을 수 없는 연구예요";

interface LimitDetail {
  code?: unknown;
  message?: unknown;
  job_id?: unknown;
}

// 429 detail 이 객체({code, message, job_id?})면 돌려준다. 문자열 detail(06a 전 서버)·배열은 null
function limitDetail(err: unknown): LimitDetail | null {
  if (httpStatus(err) !== 429) return null;
  const data = (err as FetchLikeError | null)?.data;
  const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : null;
  return detail && typeof detail === "object" && !Array.isArray(detail) ? (detail as LimitDetail) : null;
}

// 막은 연구가 있으면 그 id — 화면이 [진행 중인 연구 보기] 링크를 단다
export function activeResearchId(err: unknown): string | null {
  const limit = limitDetail(err);
  return limit?.code === "browser_active" && typeof limit.job_id === "string" && limit.job_id ? limit.job_id : null;
}

// 계획서 고치기(PUT outline·sections, If-Match)가 다른 곳에서 바뀐 version 에 막혔다 — 409 detail
// {code: "version_conflict", version, message}. 서버의 지금 version 을 준다(화면은 다시 불러온 뒤 고친다). 그 밖은 null
export function versionConflict(err: unknown): number | null {
  if (httpStatus(err) !== 409) return null;
  const data = (err as FetchLikeError | null)?.data;
  const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : null;
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return null;
  const { code, version } = detail as { code?: unknown; version?: unknown };
  return code === "version_conflict" && typeof version === "number" && Number.isInteger(version) ? version : null;
}

export function researchErrorMessage(err: unknown, fallback: string): string {
  const status = httpStatus(err);
  const limit = limitDetail(err);
  if (limit?.code === "browser_active") {
    return (typeof limit.message === "string" && limit.message.trim()) || BROWSER_ACTIVE_MESSAGE;
  }
  // 공유 큐 제한(shared_queue)·code 가 없는 429 와 503 은 몰림 안내 하나로(apiErrors 의 busy 이유와 같은 말)
  if (status === 429 || status === 503) return ERROR_HINTS.busy;
  if (status === 404) return RESEARCH_NOT_FOUND;
  const data = (err as FetchLikeError | null)?.data;
  const detail = data && typeof data === "object" && "detail" in data
    ? detailMessage((data as { detail: unknown }).detail)
    : null;
  if (status === 409 || status === 422) return detail ?? fallback;
  // 응답이 없으면 시간 초과(읽기 요청의 30초 제한 — 폴링 GET 이 여기에 걸린다)와 연결 실패를 나눠 알린다.
  // 응답 없이 끝난 요청이 아닌 것(코드 버그 등 — errorKind 'unknown')은 연결 탓으로 돌리지 않고 대체 문구만
  if (!status) {
    const kind = errorKind(err);
    return kind === "timeout" || kind === "network" ? `${fallback} — ${ERROR_HINTS[kind]}` : fallback;
  }
  return fallback;
}

// 이어간 연구 단계 화면(주제·읽기 목록·계획서)의 쓰기 오류 문구. 404 는 서버 문구('주제가 없습니다'·'논문이
// 없습니다'·'문단이 없습니다' 등)를 그대로 보인다 — researchErrorMessage 는 딥리서치 화면 그대로 모든 404 를
// RESEARCH_NOT_FOUND('찾을 수 없는 연구예요')로 바꾼다. 문구가 없는 404 와 그 밖의 상태는 researchErrorMessage 와 같다
export function workErrorMessage(err: unknown, fallback: string): string {
  if (httpStatus(err) === 404) {
    const data = (err as FetchLikeError | null)?.data;
    const detail = data && typeof data === "object" && "detail" in data
      ? detailMessage((data as { detail: unknown }).detail)
      : null;
    if (detail) return detail;
  }
  return researchErrorMessage(err, fallback);
}
