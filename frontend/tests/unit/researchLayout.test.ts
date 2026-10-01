// frontend/tests/unit/researchLayout.test.ts
import { describe, expect, it } from "vitest";
import { LAYOUT_BEFORE_REPORT, LAYOUT_WITH_REPORT, effectiveLayout } from "~/utils/researchLayout";

describe("effectiveLayout", () => {
  it("보고서가 나오기 전에는 문서형, 나오면 2단이다", () => {
    expect(LAYOUT_BEFORE_REPORT).toBe("B");
    expect(LAYOUT_WITH_REPORT).toBe("A");
    expect(effectiveLayout(null, true, false)).toBe("B");
    expect(effectiveLayout(null, true, true)).toBe("A");
  });

  it("넓은 화면은 손으로 고른 보기를 자동 보기보다 먼저 따른다", () => {
    expect(effectiveLayout("A", true, false)).toBe("A");
    expect(effectiveLayout("B", true, true)).toBe("B");
  });

  it("좁은 화면은 고른 보기·보고서와 무관하게 B 다", () => {
    expect(effectiveLayout("A", false, true)).toBe("B");
    expect(effectiveLayout(null, false, true)).toBe("B");
  });
});
