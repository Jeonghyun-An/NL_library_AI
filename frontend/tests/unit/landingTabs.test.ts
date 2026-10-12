// frontend/tests/unit/landingTabs.test.ts
import { describe, expect, it } from "vitest";
import { DEFAULT_LANDING_TAB, LANDING_TABS, landingTabStep } from "~/utils/landingTabs";

describe("LANDING_TABS — 두 갈래", () => {
  it("논문 검색 · 자료 검색 순서다(딥리서치는 갈래가 아니라 논문 패널의 + 메뉴 모드)", () => {
    expect(LANDING_TABS.map((t) => t.id)).toEqual(["paper", "book"]);
    expect(LANDING_TABS.map((t) => t.label)).toEqual(["논문 검색", "자료 검색"]);
  });

  it("좁은 화면의 짧은 이름도 순서를 따라 논문 · 자료다", () => {
    expect(LANDING_TABS.map((t) => t.shortLabel)).toEqual(["논문", "자료"]);
  });

  it("처음 열 때의 기본 갈래는 첫 칸(논문 검색)이다", () => {
    expect(DEFAULT_LANDING_TAB).toBe("paper");
    expect(LANDING_TABS[0]?.id).toBe(DEFAULT_LANDING_TAB);
  });
});

describe("landingTabStep", () => {
  it("좌우 방향키는 다음·이전 갈래로 가고 끝에서 반대편으로 돈다", () => {
    expect(landingTabStep("paper", "ArrowRight")).toBe("book");
    expect(landingTabStep("book", "ArrowRight")).toBe("paper");
    expect(landingTabStep("book", "ArrowLeft")).toBe("paper");
    expect(landingTabStep("paper", "ArrowLeft")).toBe("book");
  });

  it("Home·End 는 첫(논문)·마지막(자료) 갈래다", () => {
    expect(landingTabStep("book", "Home")).toBe("paper");
    expect(landingTabStep("paper", "End")).toBe("book");
  });

  it("갈래를 옮기는 키가 아니면 null — 위아래·Tab·엔터는 그대로 둔다", () => {
    for (const key of ["ArrowUp", "ArrowDown", "Tab", "Enter", " "]) {
      expect(landingTabStep("paper", key)).toBeNull();
    }
  });

  it("Alt·Ctrl·Meta·Shift 가 눌린 방향키는 브라우저 단축키라 움직이지 않는다", () => {
    for (const mod of ["altKey", "ctrlKey", "metaKey", "shiftKey"] as const) {
      expect(landingTabStep("paper", "ArrowRight", { [mod]: true })).toBeNull();
      expect(landingTabStep("paper", "Home", { [mod]: true })).toBeNull();
    }
    expect(landingTabStep("paper", "ArrowRight", { altKey: false, shiftKey: false })).toBe("book");
  });
});
