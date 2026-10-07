// frontend/utils/researchErrors.ts
interface FetchLikeError {
  status?: number;
  statusCode?: number;
  response?: { status?: number };
  data?: unknown;
}

export function httpStatus(err: unknown): number | undefined {
  if (!err || typeof err !== "object") return undefined;
  const e = err as FetchLikeError;
  return e.status ?? e.statusCode ?? e.response?.status;
}

// FastAPI 는 HTTPException 이면 detail 을 문자열로, pydantic 검증 실패면
// [{loc, msg, type}] 배열로 준다. 한 모양만 읽으면 다른 쪽은 "[object Object]" 가 된다.
// 구조화한 detail({code, message, …} — 429 browser_active·409 version_conflict)은 message 를 읽는다
export function detailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail.trim() || null;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const message = (detail as { message?: unknown }).message;
    return typeof message === "string" ? message.trim() || null : null;
  }
  if (!Array.isArray(detail)) return null;
  const msgs = detail
    .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
    .filter(Boolean);
  return msgs.length ? `입력값이 올바르지 않습니다: ${msgs.join(", ")}` : null;
}

// 원문 보기 전 확인 요청의 결과로 알릴 문구. null 이면 뷰어를 연다. 서버는 파일이 없을 때만
// 404 를 준다(api/book.get_book_pdf) — 5xx 까지 "없음"으로 알리면 있는 원문을 없다고 믿게 된다.
// status 가 null(확인 요청 자체가 실패)이면 판단하지 않고 뷰어가 직접 보여 주게 둔다.
export function pdfCheckProblem(status: number | null): string | null {
  if (status === null || (status >= 200 && status < 300)) return null;
  if (status === 404) return "원문 파일이 없습니다";
  return "원문을 불러오지 못했습니다. 잠시 뒤 다시 시도하세요";
}

// 같은 브라우저의 다른 딥리서치가 진행 중이라 승인·재시도가 막혔다(api/research.py _to_run_queue 의 429
// detail {code: "browser_active", message, job_id}). 서버가 문구를 비워 보내도 같은 안내를 쓴다
const BROWSER_ACTIVE_MESSAGE = "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요";

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
  // 공유 큐 제한(shared_queue)·code 가 없는 429 와 503 은 지금 문구 그대로
  if (status === 429 || status === 503) return "요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요";
  if (status === 404) return "찾을 수 없는 연구입니다";
  const data = (err as FetchLikeError | null)?.data;
  const detail = data && typeof data === "object" && "detail" in data
    ? detailMessage((data as { detail: unknown }).detail)
    : null;
  if (status === 409 || status === 422) return detail ?? fallback;
  if (status === undefined) return `${fallback} — 네트워크 연결을 확인하세요`;
  return fallback;
}

// 이어간 연구 단계 화면(주제·읽기 목록·계획서)의 쓰기 오류 문구. 404 는 서버 문구('주제가 없습니다'·'논문이
// 없습니다'·'문단이 없습니다' 등)를 그대로 보인다 — researchErrorMessage 는 딥리서치 화면 그대로 모든 404 를
// '찾을 수 없는 연구입니다' 로 바꾼다. 문구가 없는 404 와 그 밖의 상태는 researchErrorMessage 와 같다
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
