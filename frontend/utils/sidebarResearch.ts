// frontend/utils/sidebarResearch.ts
// 사이드바 DeepResearch 묶음(round08 AppSidebar)의 06d 몫 — 진행 중인 연구 줄의 단계 글과 구분선 아래 '이전 연구 [n]' 한 줄.
// 단계 글은 기록 목록(GET history)이 주는 잡의 상태·stage 로만 정하고 숫자를 붙이지 않는다 — 진행 중 잡의 하위질문·절 수는 기록 응답에
// 없고, 그것을 내려고 잡(GET /api/research/{id})을 따로 읽지 않는다. 완료 줄에는 아무것도 붙이지 않는다(사용자 결정 2026-10-13)
import type { HistoryResearchStatus } from "~/types/history";

// 진행 중(사이드바 배지 '진행 중' — sidebarGroups.LIVE_STATUSES)인 잡의 단계 글. 승인 대기·끝난 잡·상태 모름은 null(배지가 말한다).
// stage explored 는 탐색을 마치고 보고서를 쓰는 중이다(보고서 작성부터 다시 시도한 잡도)
export function statusStageLine(r: HistoryResearchStatus | null | undefined): string | null {
  switch (r?.status) {
    case "created":
    case "planning":
      return "계획 중";
    case "approved":
    case "queued":
      return "대기 중";
    case "running":
      return r.stage === "explored" || r.stage === "synthesized" ? "보고서 작성 중" : "근거 수집 중";
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
