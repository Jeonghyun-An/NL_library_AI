// frontend/tests/unit/landingTabs.test.ts
import { describe, expect, it } from "vitest";
import { LANDING_TABS, landingTabOf, landingTabStep } from "~/utils/landingTabs";

describe("landingTabOf", () => {
  it("도서 모드는 칩이 켜져 있어도 소장자료다", () => {
    expect(landingTabOf("book", false)).toBe("book");
    expect(landingTabOf("book", true)).toBe("book");
  });

  it("논문 모드는 딥리서치 칩이 켜졌는지로 논문·딥리서치를 가른다", () => {
    expect(landingTabOf("paper", false)).toBe("paper");
    expect(landingTabOf("paper", true)).toBe("deep");
  });
});

describe("landingTabStep", () => {
  it("좌우 방향키는 다음·이전 갈래로 가고 끝에서 반대편으로 돈다", () => {
    expect(landingTabStep("book", "ArrowRight")).toBe("paper");
    expect(landingTabStep("paper", "ArrowRight")).toBe("deep");
    expect(landingTabStep("deep", "ArrowRight")).toBe("book");
    expect(landingTabStep("book", "ArrowLeft")).toBe("deep");
    expect(landingTabStep("deep", "ArrowLeft")).toBe("paper");
  });

  it("Home·End 는 첫·마지막 갈래다", () => {
    expect(landingTabStep("paper", "Home")).toBe("book");
    expect(landingTabStep("paper", "End")).toBe("deep");
  });

  it("갈래를 옮기는 키가 아니면 null — 위아래·Tab·엔터는 그대로 둔다", () => {
    for (const key of ["ArrowUp", "ArrowDown", "Tab", "Enter", " "]) {
      expect(landingTabStep("paper", key)).toBeNull();
    }
  });

  it("갈래는 소장자료 · 논문 · 딥리서치 순서다", () => {
    expect(LANDING_TABS.map((t) => t.id)).toEqual(["book", "paper", "deep"]);
  });
});
