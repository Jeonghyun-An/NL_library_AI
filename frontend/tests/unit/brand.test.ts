// frontend/tests/unit/brand.test.ts
import { describe, expect, it } from "vitest";
import { DEEP_RESEARCH } from "~/utils/brand";
import { SEARCH_MODES } from "~/utils/slashCommand";

describe("DEEP_RESEARCH — 화면 표기(사용자 결정 2026-10-12)", () => {
  it("영문 DeepResearch 를 붙여 쓴다(DeepRead 와 짝)", () => {
    expect(DEEP_RESEARCH).toBe("DeepResearch");
  });

  it("+ 메뉴·칩의 이름은 이 상수이고 슬래시 명령은 그대로 /deep-research 다", () => {
    const deep = SEARCH_MODES.find((m) => m.id === "deep-research");
    expect(deep?.label).toBe(DEEP_RESEARCH);
    expect(deep?.slash).toBe("/deep-research");
  });
});
