// frontend/utils/menuNav.ts
// role="menu" 의 키보드 관례(WAI-ARIA 메뉴 버튼): 방향키로 항목 사이를 돌고 Home·End 로 끝으로 간다.
// 움직일 키가 아니면 null — 화면은 그 키의 기본 동작을 막지 않는다.
export function menuStep(current: number, key: string, count: number): number | null {
  if (count <= 0) return null;
  switch (key) {
    case "ArrowDown":
      return current < 0 ? 0 : (current + 1) % count;
    case "ArrowUp":
      return current < 0 ? count - 1 : (current - 1 + count) % count;
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}
