// frontend/utils/relatedCard.ts
// 관련 자료 추천 카드(components/detail/RelatedCard.vue)의 '자세히 보기' 열림 — 한 번에 한 카드만, 사용자가 누른 카드만 연다.

/**
 * 카드가 열림·닫힘을 알려 올 때 다음에 열려 있는 카드 id.
 * 열면 그 카드가 열린 카드가 되고(앞서 열린 카드는 닫힌다), 닫음은 **그 카드가 열려 있을 때만** 닫는다 —
 * 이미 닫혔거나 다른 카드가 열린 뒤에 늦게 온 닫음이 지금 열린 카드를 닫지 않게 한다.
 */
export function relatedOpenAfter(current: string | null, id: string, open: boolean): string | null {
  if (open) return id;
  return current === id ? null : current;
}
