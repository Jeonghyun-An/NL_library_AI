// frontend/tests/unit/restorePosition.test.ts
import { describe, expect, it } from "vitest";
import {
  hasSpot,
  isPlainClick,
  pageOfItem,
  restoreStep,
  scrollDelta,
  spotOf,
  targetTop,
  withSpot,
  withoutSpot,
} from "~/utils/restorePosition";

function click(over: Partial<Pick<MouseEvent, "button" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">> = {}) {
  return { button: 0, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...over };
}

describe("scrollDelta·targetTop", () => {
  it("요소를 목표 높이에 두려면 그 차이만큼 굴린다", () => {
    expect(scrollDelta(900, 240)).toBe(660);
    expect(scrollDelta(100, 240)).toBe(-140);
    expect(scrollDelta(240.6, 240)).toBe(1);
  });

  it("목표 높이는 떠날 때의 높이, 창이 줄었으면 요소가 보이는 데까지 올리고, 모르면 위쪽 1/3", () => {
    expect(targetTop(240, 800)).toBe(240);
    expect(targetTop(900, 600)).toBe(552);
    expect(targetTop(null, 900)).toBe(300);
  });
});

describe("restoreStep", () => {
  it("요소가 있으면 맞추고, 없으면 기한까지 다시 찾고, 넘기면 포기한다", () => {
    expect(restoreStep(true, 5000, 1000)).toBe("align");
    expect(restoreStep(false, 900, 1000)).toBe("retry");
    expect(restoreStep(false, 1000, 1000)).toBe("give-up");
  });
});

describe("주소의 자리", () => {
  it("자리를 싣거나 떼도 다른 쿼리는 그대로 두고 원본을 고치지 않는다", () => {
    const query = { q: "nlp", h: "id-1", at: "p-C0", y: "3" };
    expect(withSpot(query, { at: "p-C1", y: 120 })).toEqual({ q: "nlp", h: "id-1", at: "p-C1", y: "120" });
    expect(withoutSpot(query)).toEqual({ q: "nlp", h: "id-1" });
    expect(query).toEqual({ q: "nlp", h: "id-1", at: "p-C0", y: "3" });
  });

  it("y 를 모르면 at 만 싣는다", () => {
    expect(withSpot({}, { at: "x-C1", y: null })).toEqual({ at: "x-C1" });
  });

  it("at·y 중 하나라도 있으면 뗄 자리가 있다", () => {
    expect(hasSpot({ q: "nlp" })).toBe(false);
    expect(hasSpot({ at: "p-C1" })).toBe(true);
    expect(hasSpot({ y: "10" })).toBe(true);
  });
});

describe("spotOf", () => {
  it("누른 요소의 지금 화면 높이를 반올림해 싣고, 위로 넘친 요소는 0 으로 둔다", () => {
    expect(spotOf({ getBoundingClientRect: () => ({ top: 240.6 }) as DOMRect }, "c-0-E1")).toEqual({
      at: "c-0-E1",
      y: 241,
    });
    expect(spotOf({ getBoundingClientRect: () => ({ top: -12 }) as DOMRect }, "p-C1")).toEqual({ at: "p-C1", y: 0 });
  });
});

describe("isPlainClick", () => {
  it("수식 키 없는 왼쪽 클릭만 이 탭에서 옮긴다", () => {
    expect(isPlainClick(click())).toBe(true);
    expect(isPlainClick(click({ ctrlKey: true }))).toBe(false);
    expect(isPlainClick(click({ metaKey: true }))).toBe(false);
    expect(isPlainClick(click({ shiftKey: true }))).toBe(false);
    expect(isPlainClick(click({ button: 1 }))).toBe(false);
  });
});

describe("pageOfItem", () => {
  it("목록에서 그 항목이 있는 쪽(1부터)을 찾는다", () => {
    const ids = ["a", "b", "c", "d", "e"];
    expect(pageOfItem(ids, "a", 2)).toBe(1);
    expect(pageOfItem(ids, "d", 2)).toBe(2);
    expect(pageOfItem(ids, "e", 2)).toBe(3);
    expect(pageOfItem(ids, "z", 2)).toBeNull();
  });
});
