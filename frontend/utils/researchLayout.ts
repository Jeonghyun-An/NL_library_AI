// frontend/utils/researchLayout.ts
export type ResearchLayout = "A" | "B";

// 보고서가 나오기 전에는 계획·탐색 과정이 한 줄로 쌓이는 문서형(B)으로 과정을 크게 보이고, 보고서(작성 중
// 초안의 첫 절 포함)가 나오면 본문 + 진행 패널 2단(A)으로 바꿔 보고서를 읽으며 옆에서 과정을 본다 —
// 화면 기획 결정(2026-09-30). 아래 값은 화면 기획자가 정할 값이다. 바뀌면 값만 바꾼다.
export const LAYOUT_BEFORE_REPORT: ResearchLayout = "B";
export const LAYOUT_WITH_REPORT: ResearchLayout = "A";
export const WIDE_MIN_PX = 1200;
export const SHOW_LAYOUT_TOGGLE = true;

// 2단은 폭이 모자라면 본문이 좁아져 읽을 수 없다 — 좁은 화면은 선택과 무관하게 B 다.
// override 는 사용자가 손으로 고른 보기다. 보고서가 나와 자동 보기가 바뀔 때 호출하는 쪽이 비운다 —
// 과정을 보며 고른 보기가 보고서가 나오는 순간의 전환까지 막지 않게
export function effectiveLayout(override: ResearchLayout | null, wide: boolean, hasReport: boolean): ResearchLayout {
  if (!wide) return "B";
  return (SHOW_LAYOUT_TOGGLE ? override : null) ?? (hasReport ? LAYOUT_WITH_REPORT : LAYOUT_BEFORE_REPORT);
}
