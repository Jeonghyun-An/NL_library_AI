// frontend/utils/researchLayout.ts
export type ResearchLayout = "A" | "B";

// 넓은 화면은 처음부터 2단(A)이다 — 탐색 중에도 본문(하위질문별 절 자리)과 옆 칸(진행 패널·근거 장부)을 함께 보고,
// 보고서가 나와도 배치가 바뀌지 않는다(spec D22 — round04c 의 '보고서 전 문서형(B) → 보고서 뒤 2단' 전환을 앞으로 고침).
// 아래 값은 화면 기획자가 정할 값이다. 바뀌면 값만 바꾼다.
export const WIDE_LAYOUT: ResearchLayout = "A";
export const WIDE_MIN_PX = 1200;
export const SHOW_LAYOUT_TOGGLE = true;

// 2단은 폭이 모자라면 본문이 좁아져 읽을 수 없다 — 좁은 화면은 선택과 무관하게 B 다.
// override 는 이번 방문에서 사용자가 손으로 고른 보기다(저장하지 않는다). 단계가 바뀌어도 그대로 따른다
export function effectiveLayout(override: ResearchLayout | null, wide: boolean): ResearchLayout {
  if (!wide) return "B";
  return (SHOW_LAYOUT_TOGGLE ? override : null) ?? WIDE_LAYOUT;
}
