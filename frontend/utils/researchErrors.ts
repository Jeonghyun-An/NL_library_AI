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
export function detailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail.trim() || null;
  if (!Array.isArray(detail)) return null;
  const msgs = detail
    .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
    .filter(Boolean);
  return msgs.length ? `입력값이 올바르지 않습니다: ${msgs.join(", ")}` : null;
}

export function researchErrorMessage(err: unknown, fallback: string): string {
  const status = httpStatus(err);
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
