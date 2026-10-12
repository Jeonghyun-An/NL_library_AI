// frontend/tests/unit/clampPanel.test.ts
import { describe, expect, it } from "vitest";
import { clampMaxHeightPx, isOverflowing, needsScrollToTop, remToPx } from "~/utils/clampPanel";

describe("remToPx", () => {
  it("루트 글자 크기를 곱한다(1rem = 20px 기준 화면, 모바일은 더 작다)", () => {
    expect(remToPx(16, 20)).toBe(320);
    expect(remToPx(22.6, 20)).toBeCloseTo(452);
    expect(remToPx(16, 14.4)).toBeCloseTo(230.4);
  });
});

describe("isOverflowing — 실제로 높이를 넘는가", () => {
  it("내용이 제한 높이보다 클 때만 넘친다", () => {
    expect(isOverflowing(321, 320)).toBe(false); // 1px 오차는 넘침이 아니다(소수 높이·반올림)
    expect(isOverflowing(322, 320)).toBe(true);
    expect(isOverflowing(100, 320)).toBe(false);
    expect(isOverflowing(320, 320)).toBe(false);
  });

  it("아직 잴 수 없는 값(0·NaN)은 넘치지 않은 것으로 본다", () => {
    expect(isOverflowing(0, 320)).toBe(false);
    expect(isOverflowing(Number.NaN, 320)).toBe(false);
  });

  it("스트리밍으로 내용이 자라 한계를 넘는 순간 넘침으로 바뀐다", () => {
    const heights = [80, 160, 240, 320, 400, 520];
    expect(heights.map((h) => isOverflowing(h, 320))).toEqual([false, false, false, false, true, true]);
  });
});

describe("clampMaxHeightPx — 보이는 영역의 최대 높이", () => {
  it("넘치지 않으면 제한하지 않는다(null)", () => {
    expect(clampMaxHeightPx({ overflowing: false, expanded: false, contentPx: 200, clampPx: 320 })).toBeNull();
    expect(clampMaxHeightPx({ overflowing: false, expanded: true, contentPx: 200, clampPx: 320 })).toBeNull();
  });

  it("넘치면 접힌 동안 제한 높이, 펼치면 내용 높이(전환이 이어지게 숫자로)", () => {
    expect(clampMaxHeightPx({ overflowing: true, expanded: false, contentPx: 600, clampPx: 320 })).toBe(320);
    expect(clampMaxHeightPx({ overflowing: true, expanded: true, contentPx: 600, clampPx: 320 })).toBe(600);
  });
});

describe("needsScrollToTop — 접을 때 패널 머리로 스크롤할지", () => {
  it("머리가 화면 위로 지나갔을 때만 스크롤한다", () => {
    expect(needsScrollToTop(-120)).toBe(true);
    expect(needsScrollToTop(-1)).toBe(true);
    expect(needsScrollToTop(0)).toBe(false);
    expect(needsScrollToTop(240)).toBe(false);
  });
});
