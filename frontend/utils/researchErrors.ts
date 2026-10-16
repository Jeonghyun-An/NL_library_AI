// frontend/utils/researchErrors.ts
// 연구 화면(DeepResearch·이어간 연구)의 오류 문구. 상태 읽기·서버 사유 고르기·422 문구는 utils/apiErrors 의 규칙을 그대로 쓴다 —
// httpStatus 는 apiErrors 에만 정의한다(여기서 다시 내보내면 Nuxt 자동 import 가 같은 이름을 두 번 만나 경고한다)
import { DEEP_RESEARCH } from "./brand";
import { ERROR_HINTS, codeMessage, errorKind, httpStatus, serverMessage, validationMessage, type ConnectionState } from "./apiErrors";

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
  return "원문을 불러오지 못했어요.\n잠시 뒤 다시 시도해 주세요.";
}

// 같은 브라우저의 다른 딥리서치가 진행 중이라 승인·재시도가 막혔다(api/research.py _to_run_queue 의 429
// detail {code: "browser_active", message, job_id}). 서버 문구(운영 서버는 합쇼체)는 쓰지 않고 늘 이 화면 문구 — 말투를 한 벌로 둔다
export const BROWSER_ACTIVE_MESSAGE = `진행 중인 ${DEEP_RESEARCH}가 있어요 — 끝나거나 취소한 뒤 다시 시작해 주세요`;

// 딥리서치 화면의 404 — 연구 주소가 잘못됐거나 지워졌다(링크만 알면 누구나 열 수 있어 권한 문제는 없다)
export const RESEARCH_NOT_FOUND = "찾을 수 없는 연구예요";

// 딥리서치 화면(pages/research/[id].vue)의 상태 문구 — 멈춘·취소한·찾을 수 없는 연구 카드, 불러오기 실패, 최종 보고서를 받지 못한 안내.
// 오류 화면 모음(/dev/error-states)의 '딥리서치 상태' 묶음이 같은 상수를 읽어 실제 화면과 같은 글을 보인다.
// 멈춘 연구의 설명(failed*)은 researchFailedMessage 가 멈춘 단계로 고른다 — 문장마다 줄을 바꾼다
export const RESEARCH_STATE_TEXT = {
  failedTitle: "연구가 도중에 멈췄어요",
  // 계획이 없는 잡 — 서버가 재시도를 409 로 거절한다(retry_research). 새 잡만 답이다
  failedPlanning: "연구 계획을 세우다 멈췄어요.\n같은 질문으로 새 연구를 시작할 수 있어요.",
  // 계획은 있고 탐색을 마치지 못한 잡(stage planned) — 재시도하면 워커가 승인한 계획으로 탐색부터 다시 돈다(run_deep_research)
  failedExploring: "근거를 찾다 멈췄어요.\n다시 시도하면 승인한 계획으로 탐색부터 다시 해요.",
  // 탐색을 마친 잡(stage explored) — 체크포인트(state_snapshot)가 남아 재시도가 보고서 작성부터 이어 간다
  failedWriting: "보고서를 쓰다 멈췄어요.\n탐색에서 모은 근거는 남아 있어요.",
  canceledTitle: "취소된 연구예요",
  // 재시도는 실패한 잡만 받는다(retry_research) — 취소한 잡은 이어 갈 수 없다
  canceledMessage: "취소한 연구는 이어 갈 수 없어요.\n같은 질문으로 새 연구를 시작할 수 있어요.",
  notFoundMessage: "주소가 맞는지 다시 확인해 주세요.",
  // 원래 질문·탐색 방식으로 새 연구를 만든다 — 취소한 연구·계획 단계에서 멈춘 연구는 이어 갈 수 없어 이 버튼만 있다
  restart: "같은 질문으로 다시 시작",
  backToSearch: "논문 검색으로 돌아가기",
  loadFailedTitle: "연구를 불러오지 못했어요",
  reload: "다시 불러오기",
  // 완료한 연구의 최종 보고서 GET 이 실패했다 — 재동기화가 백오프로 계속 다시 읽는다(useResearchJob.scheduleReconnect)
  reportFailedTitle: "보고서를 불러오지 못했어요",
  reportFailedMessage: "잠시 뒤 자동으로 다시 시도해요.",
  reportFailedOverDraft: "최종 보고서를 불러오지 못했어요.\n잠시 뒤 자동으로 다시 시도해요.\n아래는 작성 중에 받은 초안이에요.",
  // 취소 뒤 워커가 쓰던 절을 마저 쓰고 종합 단계를 닫기를 기다렸지만(약 1분 반) 닫히지 않았다 — 다시 열면 그 절이 채워져 있을 수 있다
  closePending: "취소 전에 쓰던 절이 아직 정리되지 않았어요.\n잠시 뒤 다시 불러오면 그 절까지 보일 수 있어요.",
  // 승인·재시도·취소가 409(그 사이 상태가 바뀜)를 받아 서버 상태로 화면을 맞췄다
  stateChanged: "그 사이 상태가 바뀌어 최신 상태로 맞췄어요",
} as const;

// 멈춘 연구의 [다시 시도] 글 — 보고서 작성 단계(stage explored)에서 멈췄으면 탐색 결과를 체크포인트로 두고 보고서 작성부터
// 이어 간다(api/research.py retry_research). 탐색 중에 멈췄으면 승인한 계획으로 탐색부터 다시 돈다
export function researchRetryLabel(stage: string | null | undefined): string {
  return stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도";
}

// 워커가 실패로 남긴 사유(잡 last_error·단계 result.error) 가운데 화면이 알아보는 것. 서버 문구는 개발자용 해라체('시간 상한 초과 —
// 워커를 회수했다')이거나 예외 원문이라 그대로 보이지 않고 해요체 한 줄로 바꾼다. 모르는 사유는 null — 원문은 보이지 않는다
const FAILURE_REASONS: readonly (readonly [RegExp, string])[] = [
  // workers/research_tasks.py TIMEOUT_ERROR — 태스크 시간 상한에 걸려 도는 단계를 닫았다
  [/^시간 상한 초과/, "정해진 시간 안에 끝나지 않았어요."],
  // reap_stale_research — 워커가 응답하지 않아 회수기가 잡·단계를 닫았다
  [/^stale\b/, "작업이 오래 응답하지 않았어요."],
  // 전멸 — 하위질문마다 탐색이 오류로 끝났다(_wiped_out)
  [/^모든 하위질문 탐색이 오류로 실패/, "모든 하위질문의 탐색이 오류로 끝났어요."],
];

export function failureReason(error: string | null | undefined): string | null {
  const text = typeof error === "string" ? error.trim() : "";
  if (!text) return null;
  return FAILURE_REASONS.find(([re]) => re.test(text))?.[1] ?? null;
}

// 멈춘 연구 카드의 설명 — 어디서 멈췄는지, 알아보는 사유, 다시 시도하면 어떻게 되는지를 줄마다. 서버의 last_error 원문은 붙이지 않는다.
// hasPlan 은 화면이 [다시 시도]를 보이는 기준(canRetry — 계획이 없으면 서버가 재시도를 409 로 거절한다)과 같다
export function researchFailedMessage(stage: string | null | undefined, hasPlan: boolean, lastError?: string | null): string {
  const text = !hasPlan
    ? RESEARCH_STATE_TEXT.failedPlanning
    : stage === "explored"
      ? RESEARCH_STATE_TEXT.failedWriting
      : RESEARCH_STATE_TEXT.failedExploring;
  const reason = failureReason(lastError);
  if (!reason) return text;
  const [where, ...rest] = text.split("\n");
  return [where, reason, ...rest].join("\n");
}

// 연결 실패(스트림 onerror·재동기화 GET 실패)가 연달아 이만큼 쌓이면 '다시 연결하는 중'을 '연결하지 못했어요' + [다시 연결]로 바꾼다.
// 그 뒤에도 브라우저 재연결·백오프 재동기화는 계속 돌아, 붙으면 띠가 스스로 걷힌다
export const LOST_AFTER_DROPS = 3;

// 딥리서치 화면의 실시간 연결 띠(SkxConnectionBanner) 상태. streaming 은 스트림이 있어야 하는 잡인가(끝나지 않은 잡) — 읽는 중·끝난 잡은
// 늘 connected(보이는 것 없음). drops 는 마지막으로 붙거나 받은 뒤 쌓인 연결 실패 수(useResearchJob)
export function researchConnectionState(streaming: boolean, drops: number): ConnectionState {
  if (!streaming || drops <= 0) return "connected";
  return drops >= LOST_AFTER_DROPS ? "lost" : "reconnecting";
}

// 하위질문 하나가 오류로 끝났다(부분 실패 — 잡은 다음 하위질문으로 넘어간다). 단계 result.error 는 예외 원문이라 알아보는 사유만 붙인다
export const SUBQ_FAILED_TEXT = "오류로 이 하위질문의 탐색을 마치지 못했어요.";

export function subqFailureText(error: string | null | undefined): string {
  const reason = failureReason(error);
  return reason ? `${SUBQ_FAILED_TEXT}\n${reason}` : SUBQ_FAILED_TEXT;
}

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

// 무엇을 못 했는지(base) 뒤에 이유 — base 가 비면 이유만(상태 블록의 설명 줄처럼 제목이 따로 있는 자리는 fallback 을 비워 이유만 받는다)
function withReason(base: string, reason: string): string {
  return base ? `${base} — ${reason}` : reason;
}

// fallback 을 비우면(상태 블록의 설명 줄) 이유만 돌려준다 — 이유가 없으면 빈 문자열
export function researchErrorMessage(err: unknown, fallback: string): string {
  const base = typeof fallback === "string" ? fallback.trim() : "";
  const status = httpStatus(err);
  if (limitDetail(err)?.code === "browser_active") return BROWSER_ACTIVE_MESSAGE;
  if (status === 404) return RESEARCH_NOT_FOUND;
  const data = (err as FetchLikeError | null)?.data;
  // 백엔드가 경우를 갈라 붙인 code(500 internal_error 등 — 응답 본문 {detail, code})는 서버 detail 대신 화면 문구(CODE_MESSAGES)를 이유로.
  // code 가 없는 옛 서버는 아래 규칙 그대로다
  const byCode = codeMessage(data && typeof data === "object" ? (data as { code?: unknown }).code : undefined);
  if (byCode) return withReason(base, byCode);
  // 공유 큐 제한(shared_queue)·code 가 없는 429 와 503 은 몰림 안내 하나로(apiErrors 의 busy 이유와 같은 말)
  if (status === 429 || status === 503) return ERROR_HINTS.busy;
  const detail = data && typeof data === "object" && "detail" in data
    ? detailMessage((data as { detail: unknown }).detail)
    : null;
  if (status === 409 || status === 422) return detail ?? base;
  // 응답이 없으면 시간 초과(읽기 요청의 30초 제한 — 폴링 GET 이 여기에 걸린다)와 연결 실패를 나눠 알린다.
  // 응답 없이 끝난 요청이 아닌 것(코드 버그 등 — errorKind 'unknown')은 연결 탓으로 돌리지 않고 대체 문구만
  if (!status) {
    const kind = errorKind(err);
    return kind === "timeout" || kind === "network" ? withReason(base, ERROR_HINTS[kind]) : base;
  }
  return base;
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
