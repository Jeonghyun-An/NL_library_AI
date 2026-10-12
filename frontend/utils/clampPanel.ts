// frontend/utils/clampPanel.ts
// 길어질 수 있는 AI 글 패널(ClampedPanel)의 순수 계산 — 일정 높이까지만 보이고 넘치면 접힘·더보기

const TOLERANCE_PX = 1;

export function remToPx(rem: number, rootFontPx: number): number {
  return rem * rootFontPx;
}

/** 내용(contentPx)이 제한 높이(clampPx)를 실제로 넘는가. 1px 안팎은 반올림 오차라 넘침으로 보지 않는다. 아직 못 잰 값(0·NaN)은 넘치지 않은 것 */
export function isOverflowing(contentPx: number, clampPx: number): boolean {
  if (!Number.isFinite(contentPx) || contentPx <= 0) return false;
  return contentPx > clampPx + TOLERANCE_PX;
}

/** 보이는 영역의 max-height(px). null 이면 제한하지 않는다. 펼칠 때도 숫자(내용 높이)라 max-height 전환이 이어진다 */
export function clampMaxHeightPx(opts: {
  overflowing: boolean;
  expanded: boolean;
  contentPx: number;
  clampPx: number;
}): number | null {
  if (!opts.overflowing) return null;
  return opts.expanded ? opts.contentPx : opts.clampPx;
}

/** 접을 때 패널 머리(화면 기준 위쪽 좌표)가 화면 위로 지나갔으면 머리로 스크롤한다 */
export function needsScrollToTop(headTop: number): boolean {
  return headTop < 0;
}
