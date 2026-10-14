// frontend/utils/researchProgress.ts
// 연구 화면 위에 고정되는 큰 진행 막대(spec §12-3 '고정 진행 영역', Q1). 작은 단계 표시·막대 위 큰 글줄·오른쪽
// 퍼센트·채움 폭을 정한다. 막대 하나가 근거 수집(탐색)과 보고서 작성(종합) 두 구간을 실측 시간 비율로 나눠 싣는다 — 구간마다
// 0 부터 다시 세면 작성이 시작될 때 막대가 뒤로 간다. 막대는 실제 이벤트로만 움직이고, 이벤트 사이의 추정 증가는 상한
// RUNNING_CAP(synthCard — 작성 막대와 같은 값)을 넘지 않는다
import type { ResearchParams, StepStatus, SubqView } from "~/types/research";
import type { DraftSlot, SynthEta } from "~/utils/researchDraft";
import { exploreAttemptStart, fromEarlierAttempt, type ResearchPhase } from "~/utils/researchEvents";
import { RUNNING_CAP, barFraction } from "~/utils/synthCard";

export type ProgressStage = "plan" | "collect" | "write" | "done";

export interface ProgressStageItem {
  key: ProgressStage;
  label: string;
  state: "done" | "current" | "todo";
}

export const PROGRESS_STAGES: readonly { key: ProgressStage; label: string }[] = [
  { key: "plan", label: "계획" },
  { key: "collect", label: "근거 수집" },
  { key: "write", label: "보고서 작성" },
  { key: "done", label: "완료" },
];
// 두 구간의 몫 — round06a 실측 한 번(202초) 중 탐색 111초·종합 91초(round06a-완료노트 :95)
export const EXPLORE_WEIGHT = 111;
export const SYNTH_WEIGHT = 91;
// 잡 파라미터에 재검색 상한이 없을 때의 값(app/services/research/state.py DEFAULT_PARAMS["max_recheck"])
export const DEFAULT_MAX_RECHECK = 3;
// 열린 회차(검색·자기점검을 기다리는 중)는 6초마다 남은 거리의 절반씩 다가간다 — 실측 회차 하나가 십수 초다
export const ROUND_HALF_LIFE_MS = 6_000;

export interface ProgressInput {
  phase: ResearchPhase;
  subqs: readonly SubqView[];
  maxRounds: number;
  // 열린 회차를 화면이 처음 본 뒤 지난 시간(모르면 null) — 서버는 회차 시각을 주지 않는다
  roundElapsedMs: number | null;
  eta: SynthEta;
  slots: readonly DraftSlot[];
  // 대기 순번 문구(queueLine) — 대기 중이 아니거나 순번을 모르면 null
  queueNote: string | null;
}

export interface ProgressBarView {
  stages: ProgressStageItem[];
  // 막대 위 큰 글줄
  line: string;
  // 0~100 내림 정수. 계획·승인 대기·대기열은 null(퍼센트를 그리지 않는다)
  percent: number | null;
  // 0~1 채움 폭
  fraction: number;
  // 채움 끝의 빛 흐름 — 도는 하위질문·쓰는 절이 있을 때만
  running: boolean;
  // 화면 읽기 프로그램이 막대에서 읽는 글(aria-valuetext)
  valueText: string;
}

const STAGE_OF: Record<ResearchPhase, ProgressStage | null> = {
  planning: "plan",
  awaiting: "plan",
  queued: "plan",
  exploring: "collect",
  synthesizing: "write",
  completed: "done",
  failed: null,
  canceled: null,
};
const ENDED_PHASES: readonly ResearchPhase[] = ["completed", "failed", "canceled"];

export function progressStage(phase: ResearchPhase): ProgressStage | null {
  return STAGE_OF[phase];
}

export function progressStages(current: ProgressStage): ProgressStageItem[] {
  const at = PROGRESS_STAGES.findIndex((s) => s.key === current);
  return PROGRESS_STAGES.map((s, i): ProgressStageItem => ({ ...s, state: i < at ? "done" : i === at ? "current" : "todo" }));
}

// 하위질문 하나가 돌 수 있는 회차 수 = 재검색 상한 + 첫 검색. 서버 검증 범위(state.py :42 — 정수 0~10) 밖이면 기본값
export function maxRoundsOf(params: ResearchParams): number {
  const v = params.max_recheck;
  return typeof v === "number" && Number.isInteger(v) && v >= 0 && v <= 10 ? v + 1 : DEFAULT_MAX_RECHECK + 1;
}

// 회차가 열려 있다 — 첫 검색 전(회차 없음)이거나 마지막 회차가 검색만 끝나고 자기점검을 기다린다
function roundOpen(sq: SubqView): boolean {
  const last = sq.rounds[sq.rounds.length - 1];
  return !last || last.verdict === null;
}

function roundApproach(elapsedMs: number | null): number {
  if (elapsedMs === null) return 0;
  return RUNNING_CAP * (1 - 0.5 ** (Math.max(0, elapsedMs) / ROUND_HALF_LIFE_MS));
}

// 이번 시도에서 본 하위질문 상태. 탐색부터 다시 도는 재시도는 idx 0 부터 새 seq 로 행을 쌓고, 이번 시도가 아직 닿지 않은
// 하위질문에는 이전 시도의 행(done·failed)이 남는다 — 그것을 끝남으로 세면 하위질문마다 새 행이 열릴 때 막대가 뒤로 간다.
// 멈춘 지점(stopPoint)과 같은 규칙으로 대기로 본다. 워커가 running 을 알린 뒤 하위질문 0 의 새 행을 열기 전의 짧은 틈은
// 이전 시도의 행뿐이라 1차 시도가 탐색을 막 마친 때와 모양이 같아 하위질문만으로는 가르지 못한다
function attemptStatuses(subqs: readonly SubqView[]): StepStatus[] {
  const since = exploreAttemptStart(subqs);
  return subqs.map((s) => (fromEarlierAttempt(s, since) ? "pending" : s.status));
}

function subqShare(sq: SubqView, status: StepStatus, maxRounds: number, roundElapsedMs: number | null): number {
  switch (status) {
    case "done":
    case "failed":
      return 1;
    case "pending":
      return 0;
    case "running": {
      const closed = sq.rounds.filter((r) => r.verdict !== null).length;
      const open = roundOpen(sq) ? roundApproach(roundElapsedMs) : 0;
      return Math.min(RUNNING_CAP, (closed + open) / Math.max(1, maxRounds));
    }
  }
}

// 탐색 비율 = 하위질문마다의 몫(끝남·실패 1, 대기 0, 도는 하위질문은 회차 몫)의 평균. 상태는 이번 시도의 것(attemptStatuses)
export function exploreFraction(subqs: readonly SubqView[], maxRounds: number, roundElapsedMs: number | null): number {
  if (!subqs.length) return 0;
  const statuses = attemptStatuses(subqs);
  const sum = subqs.reduce((acc, sq, i) => acc + subqShare(sq, statuses[i]!, maxRounds, roundElapsedMs), 0);
  return Math.min(1, sum / subqs.length);
}

// 탐색 중에는 작성 비율을 싣지 않고, 작성이 시작되면 탐색 구간은 다 찬 것으로 본다 — 막대가 뒤로 가지 않는다
export function overallFraction(stage: "collect" | "write", explore: number, synth: number): number {
  const e = stage === "write" ? 1 : clamp01(explore);
  const s = stage === "write" ? clamp01(synth) : 0;
  return Math.min(1, (EXPLORE_WEIGHT * e + SYNTH_WEIGHT * s) / (EXPLORE_WEIGHT + SYNTH_WEIGHT));
}

// 도는 하위질문의 회차 열쇠 — 회차가 늘거나 판정이 날 때만 바뀐다(화면이 이 열쇠가 바뀐 시각을 열린 회차의 시작으로 잰다).
// 회차가 아직 없을 때도 1회차로 센다: 첫 검색 이벤트가 와도 같은 열린 회차라 다가감이 0 으로 돌아가지 않는다
export function activeRoundKey(subqs: readonly SubqView[]): string | null {
  const statuses = attemptStatuses(subqs);
  const sq = subqs.find((_, i) => statuses[i] === "running");
  if (!sq) return null;
  const last = sq.rounds[sq.rounds.length - 1];
  return `${sq.idx}:${Math.max(1, sq.rounds.length)}:${last?.verdict ?? "open"}`;
}

// 지금 단계 칩에 붙는 작은 꼬리표 — 계획 단계라도 승인을 기다리는 중이면 '승인 대기', 순서를 기다리면 '순서 대기'(일은 멈춰 있다).
// 그 밖에는 '진행 중'(사용자 결정 2026-10-14 — 후배 시안의 박스 단계에서 지금 단계 표시만 작은 칩으로 옮겼다). 말은 사이드바·머리
// 상태(researchEvents PHASE_LABEL)와 같다
export function currentStageTag(phase: ResearchPhase | null): string {
  if (phase === "awaiting") return "승인 대기";
  if (phase === "queued") return "순서 대기";
  return "진행 중";
}

// 끝나지 않은 잡에만 그린다. 단계 화면(stepMode — 끝난 잡의 이어간 연구)에는 WorkStepper 가 서므로 그리지 않는다
export function showsProgressBar(phase: ResearchPhase | null, stepMode: boolean): boolean {
  return phase !== null && !ENDED_PHASES.includes(phase) && !stepMode;
}

export function progressBarView(input: ProgressInput): ProgressBarView | null {
  const stage = progressStage(input.phase);
  if (stage === null || stage === "done") return null;
  const stages = progressStages(stage);
  if (stage === "plan") {
    const line = planLine(input.phase, input.queueNote);
    return { stages, line, percent: null, fraction: 0, running: false, valueText: line };
  }
  const collecting = stage === "collect";
  const line = collecting ? collectLine(input.subqs) : writeLine(input.eta, input.slots);
  const fraction = collecting
    ? overallFraction("collect", exploreFraction(input.subqs, input.maxRounds, input.roundElapsedMs), 0)
    : overallFraction("write", 1, barFraction(input.eta));
  const running = collecting ? attemptStatuses(input.subqs).includes("running") : input.eta.runningIdx !== null;
  const percent = Math.floor(fraction * 100);
  return { stages, line, percent, fraction, running, valueText: `${line} · ${percent}%` };
}

function planLine(phase: ResearchPhase, queueNote: string | null): string {
  if (phase === "awaiting") return "승인 대기 · 계획을 확인하고 승인하면 근거 수집을 시작합니다";
  if (phase === "queued") return `순서 대기 · ${queueNote ?? "앞선 연구가 끝나면 시작합니다"}`;
  return "계획 중 · 연구 계획을 세우고 있습니다";
}

// 도는 하위질문, 없으면(하위질문 사이) 다음 대기 하위질문, 그것도 없으면(종합 단계 행 전) 마지막 하위질문. 상태는 이번 시도의 것
function collectLine(subqs: readonly SubqView[]): string {
  if (!subqs.length) return "근거 수집을 시작하는 중";
  const statuses = attemptStatuses(subqs);
  const running = statuses.indexOf("running");
  const waiting = statuses.indexOf("pending");
  const at = running >= 0 ? running : waiting >= 0 ? waiting : subqs.length - 1;
  return `근거 수집 중 · 하위질문 ${at + 1}/${subqs.length} — 「${subqs[at]!.title}」`;
}

function writeLine(eta: SynthEta, slots: readonly DraftSlot[]): string {
  if (eta.total <= 0) return "보고서 작성을 준비하는 중";
  if (eta.done >= eta.total) return "보고서를 마무리하는 중";
  const i = (eta.runningIdx ?? eta.done) + 1;
  return `보고서 작성 중 · ${i}/${eta.total}절 — 「${slots[i - 1]?.heading ?? `절 ${i}`}」`;
}

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}
