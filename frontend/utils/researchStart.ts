// frontend/utils/researchStart.ts
// DeepResearch 를 시작하는 입력창(+ 메뉴 — SearchPlusMenu)이 같이 쓰는 판단(06d 2부 — 사용자 결정 2026-10-12~13).
// 시작은 늘 새 연구다: 사이드바 [+ 연구 시작하기]는 끝나지 않은 연구가 있어도 그 화면으로 가지 않고 메인에서 DeepResearch 모드를 켠다
// (2026-10-13 — 대회 시연에서 이전 연구로 가면 이상하다). 대신 DeepResearch 모드가 켜진 입력창에 이 브라우저의 끝나지 않은 연구를
// 한 줄로 알리고 [보기]·[취소]를 둔다 — 진행 중(사이드바 배지 '진행 중'과 같은 sidebarGroups.LIVE_STATUSES)이 먼저, 없으면 승인 대기.
// 보내기는 막지 않는다 — 서버의 승인 429 browser_active 가 마지막 안전망이다(기록 상태는 사이드바 폴링 간격만큼 늦을 수 있다)
import type { HistoryEntry, ResearchEntry } from "~/types/history";
import { DEEP_RESEARCH } from "~/utils/brand";
import { routeFor, type HistoryRoute } from "~/utils/historyRoute";
import { entryTime, isLiveResearch } from "~/utils/sidebarGroups";

export interface ResearchStartState {
  /** 진행 중이거나 순서를 기다리는 연구 — 가장 최근 것부터 */
  live: ResearchEntry[];
  /** 계획 승인을 기다리는 연구 — 가장 최근 것부터 */
  awaiting: ResearchEntry[];
}

export interface StartNotice {
  /** '진행 중인 DeepResearch 1건' · '승인 대기 중인 DeepResearch 1건' */
  text: string;
  /** [취소]가 멈출 잡(그 묶음의 가장 최근 것) */
  jobId: string;
  /** [보기]가 갈 연구 화면 */
  to: HistoryRoute;
}

// [취소]의 한 번 확인 — idle → (첫 누름) confirm → (두 번째 누름) busy → idle
export type NoticeCancelStep = "idle" | "confirm" | "busy";

// 첫 누름 뒤 이만큼은 두 번째 누름을 받지 않는다 — 더블클릭 한 번에 확인까지 넘어가지 않게
export const NOTICE_CANCEL_ARM_MS = 400;

// 읽을 수 없는 시각은 가장 오래된 것으로 친다(sidebarGroups 와 같은 규칙). 같은 시각이면 먼저 온 것이 앞
function timeOf(entry: ResearchEntry): number {
  const ms = Date.parse(entryTime(entry));
  return Number.isNaN(ms) ? Number.NEGATIVE_INFINITY : ms;
}

function newestFirst(list: readonly ResearchEntry[]): ResearchEntry[] {
  return list
    .map((entry, i) => ({ entry, i, t: timeOf(entry) }))
    .sort((a, b) => (a.t === b.t ? a.i - b.i : b.t > a.t ? 1 : -1))
    .map((x) => x.entry);
}

export function researchStartState(items: readonly HistoryEntry[]): ResearchStartState {
  const research = items.filter((e): e is ResearchEntry => e.kind === "research");
  return {
    live: newestFirst(research.filter(isLiveResearch)),
    awaiting: newestFirst(research.filter((e) => e.research?.status === "awaiting_approval")),
  };
}

// DeepResearch 모드 입력창의 한 줄 — 진행 중이 먼저, 그다음 승인 대기. 둘 다 없으면 null
export function startNotice(state: ResearchStartState): StartNotice | null {
  const live = state.live.length > 0;
  const list = live ? state.live : state.awaiting;
  const target = list[0];
  if (!target) return null;
  return {
    text: `${live ? "진행 중인" : "승인 대기 중인"} ${DEEP_RESEARCH} ${list.length}건`,
    jobId: target.refId || target.id,
    to: routeFor(target),
  };
}

// [취소]를 눌렀을 때 — 처음이면 확인으로 바꾸고(arm), 확인 중이면 잠깐 뒤에만 취소한다(run). 받지 않는 누름은 null
export function noticeCancelPress(step: NoticeCancelStep, armedAt: number, now: number): "arm" | "run" | null {
  if (step === "idle") return "arm";
  if (step === "confirm" && now - armedAt >= NOTICE_CANCEL_ARM_MS) return "run";
  return null;
}

export function noticeCancelLabel(step: NoticeCancelStep): string {
  return step === "idle" ? "취소" : step === "confirm" ? "정말 취소" : "취소하는 중";
}
