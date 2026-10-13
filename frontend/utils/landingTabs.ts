// frontend/utils/landingTabs.ts
// 메인 랜딩의 두 갈래 전환(논문 검색 · 자료 검색 — 논문이 첫 칸이고 처음 열 때의 기본 갈래다).
// 갈래는 화면의 데이터 모드(도서/논문)와 같다. 딥리서치는 갈래가 아니라 논문 패널에서 + 메뉴·슬래시 명령으로 켜는
// 모드라, 켜져 있어도 전환은 '논문 검색'이 선택된 상태다.
export type LandingMode = "book" | "paper";
export type LandingTab = LandingMode;

export interface LandingTabDef {
  id: LandingTab;
  label: string;
  // 좁은 화면(≤480px)에서 쓰는 짧은 이름
  shortLabel: string;
}

export const LANDING_TABS: readonly LandingTabDef[] = [
  { id: "paper", label: "논문 검색", shortLabel: "논문" },
  { id: "book", label: "자료 검색", shortLabel: "자료" },
];

/** 처음 열 때 선택된 갈래 — 첫 칸 */
export const DEFAULT_LANDING_TAB: LandingTab = LANDING_TABS[0]!.id;

export interface KeyModifiers {
  altKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
}

// 탭 목록의 키보드 관례(WAI-ARIA tablist): 좌우 방향키로 돌고 Home·End 로 끝으로 간다.
// 움직일 키가 아니면 null — 화면은 그 키의 기본 동작을 막지 않는다. 가로 목록이라 위아래 방향키는 쓰지 않는다.
// Alt·Ctrl·Meta·Shift 가 함께 눌렸으면 브라우저·OS 단축키(Alt+← 뒤로 가기 등)이므로 움직이지 않는다.
export function landingTabStep(current: LandingTab, key: string, mods: KeyModifiers = {}): LandingTab | null {
  if (mods.altKey || mods.ctrlKey || mods.metaKey || mods.shiftKey) return null;
  const count = LANDING_TABS.length;
  const at = LANDING_TABS.findIndex((t) => t.id === current);
  let next: number;
  switch (key) {
    case "ArrowRight":
      next = (at + 1) % count;
      break;
    case "ArrowLeft":
      next = (at - 1 + count) % count;
      break;
    case "Home":
      next = 0;
      break;
    case "End":
      next = count - 1;
      break;
    default:
      return null;
  }
  return LANDING_TABS[next]?.id ?? null;
}
