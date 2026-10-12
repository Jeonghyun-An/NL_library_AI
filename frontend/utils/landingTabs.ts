// frontend/utils/landingTabs.ts
// 메인 랜딩의 세 갈래 전환(소장자료 검색 · 논문 검색 · 딥리서치).
// 화면의 데이터 모드는 도서/논문 둘뿐이고, 딥리서치는 논문 패널에서 + 메뉴의 딥리서치 칩을 켠 상태다 —
// 그래서 세 갈래는 (모드, 칩 켜짐) 두 값에서 정해진다.
export type LandingMode = "book" | "paper";
export type LandingTab = "book" | "paper" | "deep";

export interface LandingTabDef {
  id: LandingTab;
  label: string;
  // 좁은 화면(≤480px)에서 쓰는 짧은 이름
  shortLabel: string;
}

export const LANDING_TABS: readonly LandingTabDef[] = [
  { id: "book", label: "소장자료 검색", shortLabel: "소장자료" },
  { id: "paper", label: "논문 검색", shortLabel: "논문" },
  { id: "deep", label: "딥리서치", shortLabel: "딥리서치" },
];

// 도서 모드에서는 칩이 켜져 있어도(숨은 논문 패널에 남은 상태) 소장자료다
export function landingTabOf(mode: LandingMode, deepResearch: boolean): LandingTab {
  if (mode === "book") return "book";
  return deepResearch ? "deep" : "paper";
}

export interface LandingSelectPlan {
  mode: LandingMode;
  // 켜져 있는 딥리서치 모드를 끈다 — 메뉴(clearMode)와 화면 상태(deepResearch) 둘 다.
  // 메뉴가 같은 틱에 unmount 되면(소장자료 기록 복원) update:mode 가 오지 않을 수 있어 화면 상태는 호출하는 쪽이 직접 내린다
  clearDeep: boolean;
  // 논문 패널이 보인 뒤에 딥리서치 모드를 켠다
  activateDeep: boolean;
}

// 갈래를 고를 때 할 일. 소장자료·논문으로 갈 때 딥리서치가 켜져 있었다면 반드시 끈다
export function planLandingSelect(next: LandingTab, deepResearch: boolean): LandingSelectPlan {
  if (next === "deep") return { mode: "paper", clearDeep: false, activateDeep: true };
  return { mode: next === "book" ? "book" : "paper", clearDeep: deepResearch, activateDeep: false };
}

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
