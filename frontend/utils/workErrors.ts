// frontend/utils/workErrors.ts
// 연구 작업대(이어간 연구 — 제목 고르기·참고문헌 선택하기·보고서)의 오류 문구와 판정(순수 함수 — Vue 의존 없음).
// 문구를 고르는 규칙은 utils/researchErrors(workErrorMessage·researchErrorMessage)를 그대로 쓰고, 여기서는 그 결과를
// 공통 오류 컴포넌트(SkxErrorState 의 제목·이유, SkxInlineError 의 한 줄)에 맞게 나누고 잇는다.
// 문구는 해요체·문장마다 줄바꿈이다(사용자 결정 2026-10-16)
import type { ConnectionState, ErrorKind } from "./apiErrors";
import { errorKind } from "./apiErrors";
import { researchErrorMessage } from "./researchErrors";
import type { WorkResource, WorkState } from "~/types/work";

/** 이미 읽어 둔 단계의 다시 읽기가 실패했을 때 — 단계 위 한 줄의 머리이자 조회 오류의 대체 문구 */
export const WORK_REFRESH_FAILED = "최신 상태를 불러오지 못했어요";
/** 이어간 연구의 첫 조회(GET work)가 404·422 가 아닌 이유로 실패했을 때 */
export const WORK_LOAD_FAILED = "이어간 연구를 불러오지 못했어요";
/** 보고서의 인용 근거 패널 — 원문 대목 조회(GET …/sources)가 실패했을 때 */
export const WORK_SOURCES_FAILED = "원문 대목을 불러오지 못했어요";

/**
 * 쓰기는 끝났지만 바로 뒤 다시 읽기가 실패했을 때의 머리 — 단계 위 한 줄(SkxInlineError)에 '— 이유'와 함께 보인다.
 * 쓰기 응답 본문은 버리고 다시 읽은 값으로 화면을 그리므로, 이때 화면은 쓰기 전 값이다(성공 문구를 띄우지 않는다)
 */
export const WORK_SAVED_STALE = {
  saved: "저장은 됐지만 화면을 새로 고치지 못했어요",
  started: "요청은 받았지만 화면을 새로 고치지 못했어요",
  approved: "목차를 승인했지만 화면을 새로 고치지 못했어요",
} as const;

/** 보고서 고치기(If-Match)가 409 version_conflict 에 막혔을 때 */
export const WORK_CONFLICT = {
  // 다시 읽어 화면을 서버 값으로 맞췄다
  reloaded: "다른 곳에서 보고서가 바뀌어 다시 불러왔어요 — 바뀐 내용을 확인한 뒤 다시 해 주세요",
  // 이 화면의 앞선 쓰기 뒤 다시 읽기가 실패해 옛 version 으로 보냈다 — '다른 곳에서 바뀌었다'는 사실이 아닐 수 있다
  stale: "화면이 최신 상태가 아니어서 저장하지 못했어요 — 다시 불러온 보고서를 확인한 뒤 다시 해 주세요",
  // 다시 읽기마저 실패했다 — 화면은 여전히 옛 값이다(단계 위 한 줄의 [다시 시도]로 맞춘다)
  unloaded: "보고서가 그 사이 바뀌어 저장하지 못했어요 — 최신 상태를 불러온 뒤 다시 해 주세요",
} as const;

/**
 * 쓰기 요청이 오래 걸릴 때(응답이 오지 않음) — 쓰기는 끊으면 서버에서 두 번 돌 수 있어 시간 제한으로 끊지 않고 이 안내만 띄운다.
 * 버튼 잠금은 그대로 둔다
 */
export const WORK_SLOW_MS = 90_000;
export const WORK_SLOW_MESSAGE = "응답이 늦어지고 있어요.\n잠시 기다리거나 화면을 새로 고쳐 주세요.";

/** 연구 스트림이 끊긴 뒤 이만큼 다시 붙지 못하면 '연결하지 못했어요'(lost)로 바꾼다 — 그 전에는 '다시 연결하는 중' */
export const WORK_STREAM_LOST_MS = 20_000;

/** 조회 하나의 실패 — kind 는 SkxErrorState 의 kind, message 는 대체 문구가 붙은 한 줄, reason 은 이유만(없으면 빈 글) */
export interface WorkFailure {
  kind: ErrorKind;
  message: string;
  reason: string;
}

/**
 * 오류 문구에서 대체 문구 머리('… — ')를 떼고 이유만 남긴다. 대체 문구 그대로면(이유가 없음) 빈 글,
 * 대체 문구로 시작하지 않으면(서버 사유·몰림 안내·찾을 수 없음 등 이유만 온 문구) 그대로
 */
export function workReason(message: string, fallback: string): string {
  if (message === fallback) return "";
  const head = `${fallback} — `;
  return message.startsWith(head) ? message.slice(head.length) : message;
}

/** 오류 하나를 화면 몫으로 — 문구 규칙은 read(기본 researchErrorMessage, 쓰기는 workErrorMessage) */
export function workFailure(
  err: unknown,
  fallback: string,
  read: (err: unknown, fallback: string) => string = researchErrorMessage,
): WorkFailure {
  const message = read(err, fallback);
  return { kind: errorKind(err), message, reason: workReason(message, fallback) };
}

/** 머리 뒤에 이유를 ' — ' 로 잇는다 — 이유가 없으면 머리만 */
export function withWorkReason(head: string, reason: string): string {
  return reason ? `${head} — ${reason}` : head;
}

/** 줄 끝에 마침표가 없으면 붙인다 — 여러 줄 문구는 줄마다 마침표로 끝낸다(문장마다 줄바꿈 규칙) */
export function withPeriod(line: string): string {
  const text = line.trimEnd();
  return /[.?!…]$/.test(text) ? text : `${text}.`;
}

/** 보고서 자동 작성(절 연쇄)이 멈춘 줄 — 까닭 뒤에 [이어서 쓰기] 안내를 다음 줄로(까닭이 여러 줄이어도 줄마다 마침표) */
export function autoResumeLine(stopped: string): string {
  return `${withPeriod(stopped)}\n[이어서 쓰기]를 누르면 남은 절부터 다시 써요.`;
}

/** 조회에 읽어 둔 값이 있는가 */
export function hasWorkData(state: WorkState, kind: WorkResource): boolean {
  return state[kind] !== null;
}

/**
 * 단계 위 한 줄(SkxInlineError)로 알릴 조회 — 이 단계가 쓰는 조회(kinds) 가운데 마지막 읽기가 실패한 것.
 * 단계의 본문 조회(main)가 아직 값이 없으면 본문 자리의 오류 블록(SkxErrorState)이 알리므로 뺀다 — 같은 실패를 두 번 말하지 않게.
 * 본문 조회가 아닌 조회(연구 요약·고른 주제 등)는 값이 없어도 알린다 — 그 실패를 보일 자리가 따로 없다
 */
export function staleWorkKinds(
  kinds: readonly WorkResource[],
  main: WorkResource,
  state: WorkState,
  failed: (kind: WorkResource) => boolean,
): WorkResource[] {
  return kinds.filter((kind) => failed(kind) && (kind !== main || hasWorkData(state, kind)));
}

/**
 * 연구 스트림(SSE) 연결 상태의 다음 값 — SkxConnectionBanner 의 state.
 *  open    : 열렸다(처음·다시 붙음) → connected
 *  drop    : 끊겼다(브라우저가 다시 붙는 중이거나 직접 다시 붙일 참) → reconnecting. 이미 lost 면 그대로(다시 붙어야 풀린다)
 *  giveUp  : 끊긴 뒤 WORK_STREAM_LOST_MS 가 지나도 다시 붙지 못했다 → lost
 *  retry   : [다시 연결] 을 눌렀다 → reconnecting
 *  stop    : 일부러 닫았다(화면을 떠남·연구를 처음부터 다시 읽음) → connected(띠를 비운다)
 */
export type WorkStreamEvent = "open" | "drop" | "giveUp" | "retry" | "stop";

export function workConnectionAfter(prev: ConnectionState, event: WorkStreamEvent): ConnectionState {
  switch (event) {
    case "open":
    case "stop":
      return "connected";
    case "drop":
      return prev === "lost" ? "lost" : "reconnecting";
    case "giveUp":
      return prev === "reconnecting" ? "lost" : prev;
    case "retry":
      return "reconnecting";
  }
}
