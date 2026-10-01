// frontend/tests/unit/menuNav.test.ts
import { describe, expect, it } from "vitest";
import { menuStep } from "~/utils/menuNav";

describe("menuStep", () => {
  it("아래·위 방향키는 다음·이전 항목으로 가고 끝에서 반대편으로 돈다", () => {
    expect(menuStep(0, "ArrowDown", 3)).toBe(1);
    expect(menuStep(2, "ArrowDown", 3)).toBe(0);
    expect(menuStep(1, "ArrowUp", 3)).toBe(0);
    expect(menuStep(0, "ArrowUp", 3)).toBe(2);
  });

  it("Home·End 는 첫·마지막 항목이다", () => {
    expect(menuStep(1, "Home", 3)).toBe(0);
    expect(menuStep(1, "End", 3)).toBe(2);
  });

  it("초점이 항목에 없으면 아래는 첫 항목, 위는 마지막 항목부터 잡는다", () => {
    expect(menuStep(-1, "ArrowDown", 3)).toBe(0);
    expect(menuStep(-1, "ArrowUp", 3)).toBe(2);
  });

  it("항목 이동 키가 아니거나 항목이 없으면 움직이지 않는다", () => {
    expect(menuStep(0, "Enter", 3)).toBeNull();
    expect(menuStep(0, "ArrowDown", 0)).toBeNull();
  });
});
