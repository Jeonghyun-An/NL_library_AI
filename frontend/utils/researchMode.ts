// frontend/utils/researchMode.ts
// DeepResearch '탐색 방식'(spec D28 — 06c 판정 뒤 2026-10-12 사용자 결정). 06c 의 두 스위치를 서버 기본값으로 켜지 않고
// (app/services/research/state.py DEFAULT_PARAMS 는 0 그대로) 사용자가 DeepResearch를 시작할 때 고른다. 서버 기본값이 0 이라
// 화면이 고른 방식의 두 칸(broaden·query_context)을 늘 함께 싣는다 — query_context 만 1 이면 범위 용어(broaden 1 의
// 계획 단계가 뽑는다)가 비어 '국내 학술논문에서' 떼기만 한다
import type { ResearchParams } from "~/types/research";
import { menuStep } from "~/utils/menuNav";

export type ResearchMode = "broad" | "precise";

export interface ResearchModeOption {
  id: ResearchMode;
  label: string;
  hint: string;
}

// 잡 params 에 싣는 두 칸 — 서버 merge_params 가 정수 0~1 로 검증한다. interface 가 아니라 type 이어야
// ResearchParams(Record<string, number>)로 그대로 넘어간다(interface 에는 암묵 색인 서명이 없다)
export type ModeParams = { broaden: number; query_context: number };

export const RESEARCH_MODE_LABEL = "탐색 방식";
export const DEFAULT_RESEARCH_MODE: ResearchMode = "precise";
// 고른 방식의 기억 — 같은 브라우저의 편의일 뿐이다(없거나 읽지 못하면 기본 방식)
export const RESEARCH_MODE_KEY = "skx_research_mode";
// 화면의 칸 순서(폭넓게 · 정밀하게)
export const RESEARCH_MODES: readonly ResearchModeOption[] = [
  { id: "broad", label: "폭넓게", hint: "많이 찾지만 엉뚱한 논문이 섞일 수 있습니다" },
  {
    id: "precise",
    label: "정밀하게",
    hint: "질문의 범위를 검색어에 함께 넣어 엉뚱한 논문을 줄입니다. 관련 논문 몇 편을 놓칠 수 있습니다",
  },
];

const MODE_IDS: readonly ResearchMode[] = RESEARCH_MODES.map((m) => m.id);

function isResearchMode(value: unknown): value is ResearchMode {
  return value === "broad" || value === "precise";
}

// 서버가 검증한 값(0·1)만 온다 — 1 이 아니면 꺼짐으로 읽는다(없는 칸은 서버 기본값 0)
function switchOf(value: number | undefined): number {
  return value === 1 ? 1 : 0;
}

// 두 칸이 모두 없으면 06c 전 잡이거나 params 를 싣지 않은 응답이다(ResearchView.params 는 job.params ?? {})
function hasModeKeys(params: ResearchParams | null | undefined): params is ResearchParams {
  return !!params && ("broaden" in params || "query_context" in params);
}

export function modeParams(mode: ResearchMode): ModeParams {
  const on = mode === "precise" ? 1 : 0;
  return { broaden: on, query_context: on };
}

// 잡이 어느 방식으로 돌았나 — 두 칸이 갈리면(판정 도구로 나눠 돌린 잡 같은 경우) 어느 방식도 아니라 null
export function modeOfParams(params: ResearchParams | null | undefined): ResearchMode | null {
  if (!hasModeKeys(params)) return null;
  const broaden = switchOf(params.broaden);
  if (broaden !== switchOf(params.query_context)) return null;
  return broaden === 1 ? "precise" : "broad";
}

export function researchModeLabel(mode: ResearchMode): string {
  return RESEARCH_MODES.find((m) => m.id === mode)?.label ?? "";
}

// 연구 화면 머리의 작은 표시 — 방식을 모르면 null(그리지 않는다)
export function researchModeLine(params: ResearchParams | null | undefined): string | null {
  const mode = modeOfParams(params);
  return mode ? `${RESEARCH_MODE_LABEL} · ${researchModeLabel(mode)}` : null;
}

// 같은 질문으로 다시 시작할 때 실을 두 칸 — 원래 잡의 값을 그대로 이어 쓴다. 두 칸이 모두 없는 잡(06c 전)은 기본 방식
export function restartParams(params: ResearchParams | null | undefined): ModeParams {
  if (!hasModeKeys(params)) return modeParams(DEFAULT_RESEARCH_MODE);
  return { broaden: switchOf(params.broaden), query_context: switchOf(params.query_context) };
}

// radiogroup 의 키보드 관례 — 방향키로 옆 칸을 고르고(끝에서 돈다) Home·End 로 처음·끝. 움직일 키가 아니면 null
export function modeStep(current: ResearchMode, key: string): ResearchMode | null {
  const nav = key === "ArrowRight" ? "ArrowDown" : key === "ArrowLeft" ? "ArrowUp" : key;
  const next = menuStep(MODE_IDS.indexOf(current), nav, MODE_IDS.length);
  return next === null ? null : (MODE_IDS[next] ?? null);
}

export function readResearchMode(storage: Storage | null): ResearchMode {
  try {
    const stored = storage?.getItem(RESEARCH_MODE_KEY);
    return isResearchMode(stored) ? stored : DEFAULT_RESEARCH_MODE;
  } catch {
    return DEFAULT_RESEARCH_MODE;
  }
}

export function saveResearchMode(storage: Storage | null, mode: ResearchMode): void {
  try {
    storage?.setItem(RESEARCH_MODE_KEY, mode);
  } catch {
    // 막힌 저장소·쿼터 초과 — 이 화면에서 고른 값만 쓴다
  }
}
