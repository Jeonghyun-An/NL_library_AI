// frontend/utils/sidebarDrawer.ts
// 좁은 화면(≤768px)의 사이드바는 본문을 밀지 않고 위를 덮는 서랍이다(components/AppSidebar.vue, style_skovix.css 의 '좁은 화면' 구간).
// 기준 폭 768px: 앱의 다른 휴대폰 배치(html 글자 크기 0.9rem·카드 한 줄·결과 틀 여백)도 이 폭에서 바뀐다 — 펼친 사이드바(16rem = 14.4px 기준 230px)를
// 밀어내는 배치는 이 폭 이하에서 본문이 500px 아래로 줄어 결과 카드·상세 화면이 무너진다(375px 에서는 본문 87px).
// CSS 의 @media 와 JS 의 matchMedia 가 같은 숫자를 쓰도록 여기 한 곳에 둔다(테스트가 CSS 와 맞는지 본다).

export const NARROW_MAX_WIDTH = 768;
export const NARROW_QUERY = `(max-width: ${NARROW_MAX_WIDTH}px)`;

/**
 * 서랍 안 Tab 순환 — 첫 칸에서 Shift+Tab, 마지막 칸에서 Tab 이면 반대편 끝으로 돌려 보낸다(그 외에는 null: 브라우저 기본 이동).
 * 초점이 서랍 밖(또는 없음)이면 방향에 맞는 끝으로 들인다. items 는 화면에 보이는 초점 가능 요소를 DOM 순서대로.
 */
export function trapTabTarget<T>(items: readonly T[], active: T | null, shift: boolean): T | null {
  if (items.length === 0) return null;
  const first = items[0]!;
  const last = items[items.length - 1]!;
  const i = active === null ? -1 : items.indexOf(active);
  if (i === -1) return shift ? last : first;
  if (shift && i === 0) return last;
  if (!shift && i === items.length - 1) return first;
  return null;
}
