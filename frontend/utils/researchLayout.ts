// frontend/utils/researchLayout.ts
export type ResearchLayout = "A" | "B";

// 아래 셋은 화면 기획자가 정할 값이다. 정해지면 값만 바꾼다.
export const DEFAULT_LAYOUT: ResearchLayout = "A";
export const WIDE_MIN_PX = 1200;
export const SHOW_LAYOUT_TOGGLE = true;

export const LAYOUT_KEY = "skx_research_layout";

export function readLayoutPref(storage: Storage | null): ResearchLayout | null {
  try {
    const v = storage?.getItem(LAYOUT_KEY);
    return v === "A" || v === "B" ? v : null;
  } catch {
    return null;
  }
}

export function writeLayoutPref(storage: Storage | null, layout: ResearchLayout): void {
  try {
    storage?.setItem(LAYOUT_KEY, layout);
  } catch {
    // 막힌 저장소(사생활 보호 모드 등)면 이번 방문 동안만 기억한다
  }
}

// 2단은 폭이 모자라면 본문이 좁아져 읽을 수 없다 — 좁은 화면은 선택과 무관하게 B 다
export function effectiveLayout(pref: ResearchLayout | null, wide: boolean): ResearchLayout {
  if (!wide) return "B";
  return (SHOW_LAYOUT_TOGGLE ? pref : null) ?? DEFAULT_LAYOUT;
}
