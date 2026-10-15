// frontend/tests/unit/researchLayout.test.ts
import { describe, expect, it } from "vitest";
import { WIDE_LAYOUT, effectiveLayout } from "~/utils/researchLayout";

describe("effectiveLayout", () => {
  it("넓은 화면은 처음부터 2단이다 — 보고서를 기다리지 않는다", () => {
    expect(WIDE_LAYOUT).toBe("A");
    expect(effectiveLayout(null, true)).toBe("A");
  });

  it("넓은 화면은 손으로 고른 보기를 먼저 따른다", () => {
    expect(effectiveLayout("B", true)).toBe("B");
    expect(effectiveLayout("A", true)).toBe("A");
  });

  it("좁은 화면은 고른 보기와 무관하게 B 다", () => {
    expect(effectiveLayout("A", false)).toBe("B");
    expect(effectiveLayout("B", false)).toBe("B");
    expect(effectiveLayout(null, false)).toBe("B");
  });
});
