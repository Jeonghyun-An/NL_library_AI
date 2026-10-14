// frontend/utils/sidebarResearch.ts
// 사이드바 DeepResearch 묶음(round08 AppSidebar)의 06d 몫 — 진행 중인 연구 줄의 단계 글과 구분선 아래 '이전 연구 [n]' 한 줄.
// 단계 글은 기록 목록(GET history)이 주는 잡의 상태·stage 로만 정하고 숫자를 붙이지 않는다 — 진행 중 잡의 하위질문·절 수는 기록 응답에
// 없고, 그것을 내려고 잡(GET /api/research/{id})을 따로 읽지 않는다. 완료 줄에는 아무것도 붙이지 않는다(사용자 결정 2026-10-13)
import type { HistoryResearchStatus } from "~/types/history";
import { EXPLORE_WEIGHT, SYNTH_WEIGHT } from "~/utils/researchProgress";

// 진행 중(사이드바 배지 '진행 중' — sidebarGroups.LIVE_STATUSES)인 잡의 단계 글. 승인 대기·끝난 잡·상태 모름은 null(배지가 말한다).
// stage explored 는 탐색을 마치고 보고서를 쓰는 중이다(보고서 작성부터 다시 시도한 잡도)
export function statusStageLine(r: HistoryResearchStatus | null | undefined): string | null {
  switch (r?.status) {
    case "created":
    case "planning":
      return "계획 중";
    case "approved":
    case "queued":
      // 연구 화면 머리·단계 칩과 같은 말(researchEvents PHASE_LABEL — 사용자 결정 2026-10-14)
      return "순서 대기 중";
    case "running":
      return r.stage === "explored" || r.stage === "synthesized" ? "보고서 작성 중" : "탐색 중";
    default:
      return null;
  }
}

// 진행 중인 연구 줄 아래 진행 막대(후배 시안, 사용자 결정 2026-10-14) — 지난 단계까지 채움(start)과 지금 단계 구간(span), 모두 0~1.
// 기록 목록에는 하위질문·절 수가 없어 단계 안의 진행은 모른다. 그래서 한 값으로 채우지 않고 연구 화면의 큰 막대(researchProgress)와
// 같은 구간 경계를 쓴다 — 계획은 0, 근거 수집은 0~탐색 몫, 보고서 작성은 탐색 몫~1. 연구 화면 막대의 값은 늘 이 구간 안이라 둘이
// 어긋나 보이지 않는다(전에는 단계 가운데 값을 칠해 사이드바 62.5% · 화면 56% 로 갈렸다 — 2026-10-14 운영 확인).
// 승인 대기·끝난 잡·상태 모름은 null(막대 없이 배지가 말한다). 단계 글(statusStageLine)과 같은 상태 나눔을 쓴다
const COLLECT_END = EXPLORE_WEIGHT / (EXPLORE_WEIGHT + SYNTH_WEIGHT);
export interface StageRange {
  start: number;
  span: number;
}
export function stageProgress(r: HistoryResearchStatus | null | undefined): StageRange | null {
  switch (r?.status) {
    case "created":
    case "planning":
    case "approved":
    case "queued":
      // 계획·순서 대기 — 연구 화면 막대도 아직 0 이다(퍼센트 없음)
      return { start: 0, span: 0 };
    case "running":
      return r.stage === "explored" || r.stage === "synthesized"
        ? { start: COLLECT_END, span: 1 - COLLECT_END }
        : { start: 0, span: COLLECT_END };
    default:
      return null;
  }
}

// 묶음이 처음 보이는 줄 수를 넘는 연구를 펼치는 한 줄(시안 C) — 접혀 있으면 '이전 연구' + 숨은 수 칩, 펼치면 '접기'
export function olderToggle(expanded: boolean, hidden: number): { label: string; count: number | null; ariaLabel: string } {
  return expanded
    ? { label: "접기", count: null, ariaLabel: "이전 연구 접기" }
    : { label: "이전 연구", count: hidden, ariaLabel: `이전 연구 ${hidden}건 더 보기` };
}
