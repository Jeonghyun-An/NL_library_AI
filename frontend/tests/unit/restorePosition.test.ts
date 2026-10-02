// frontend/tests/unit/restorePosition.test.ts
import { describe, expect, it } from "vitest";
import { readReturnSpot } from "~/utils/detailSource";
import {
  SPOT_STATE_KEY,
  hasSpot,
  holdDelta,
  holdsReturnSpot,
  isPlainClick,
  isUserMove,
  pageOfItem,
  restoreStep,
  scrollDelta,
  spotFromState,
  spotOf,
  spotState,
  stateWithSpot,
  stateWithoutSpot,
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

describe("holdDelta", () => {
  it("붙잡는 동안은 1px 넘게 밀렸을 때만 그만큼 되돌린다", () => {
    expect(holdDelta(248, 240)).toBe(8);
    expect(holdDelta(231.4, 240)).toBe(-9);
    expect(holdDelta(241, 240)).toBe(1);
    expect(holdDelta(240.9, 240)).toBe(0);
    expect(holdDelta(239.2, 240)).toBe(0);
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

describe("기록의 state 에 남긴 자리", () => {
  it("남긴 자리는 주소의 at·y 와 같은 모양이라 readReturnSpot 이 그대로 읽는다", () => {
    const state = { back: "/papers/x?at=c-0-E1&y=240", position: 3, [SPOT_STATE_KEY]: { at: "c-0-E1", y: "240" } };
    expect(spotFromState(state)).toEqual({ at: "c-0-E1", y: "240" });
    expect(readReturnSpot(spotFromState(state)!)).toEqual({ at: "c-0-E1", y: 240 });
    expect(spotFromState({ [SPOT_STATE_KEY]: { at: "p-C1" } })).toEqual({ at: "p-C1" });
  });

  it("모양이 틀리거나 지운 자리는 없는 것으로 본다", () => {
    expect(spotFromState(null)).toBeNull();
    expect(spotFromState("skxSpot")).toBeNull();
    expect(spotFromState({ back: null })).toBeNull();
    expect(spotFromState({ [SPOT_STATE_KEY]: null })).toBeNull();
    expect(spotFromState({ [SPOT_STATE_KEY]: ["c-0-E1"] })).toBeNull();
    expect(spotFromState({ [SPOT_STATE_KEY]: { at: 3 } })).toBeNull();
    expect(spotFromState({ [SPOT_STATE_KEY]: { at: "c-0-E1", y: 240 } })).toBeNull();
  });

  it("router.replace 에 넘기는 조각은 자리 열쇠 하나뿐이고, y 를 모르면 at 만 싣는다", () => {
    expect(spotState({ at: "c-0-E1", y: 240 })).toEqual({ [SPOT_STATE_KEY]: { at: "c-0-E1", y: "240" } });
    expect(spotState({ at: "x-C1", y: null })).toEqual({ [SPOT_STATE_KEY]: { at: "x-C1" } });
    expect(spotState({ at: null, y: 240 })).toEqual({ [SPOT_STATE_KEY]: null });
    expect(spotState(null)).toEqual({ [SPOT_STATE_KEY]: null });
  });

  it("싣거나 지워도 vue-router 의 열쇠는 그대로 두고 원본을 고치지 않는다 — 지운 자리는 null 로 남긴다", () => {
    const state = { back: "/a", current: "/b", position: 2, scroll: null };
    const withIt = stateWithSpot(state, { at: "p-C1", y: 10 });
    expect(withIt).toEqual({ ...state, [SPOT_STATE_KEY]: { at: "p-C1", y: "10" } });
    expect(stateWithoutSpot(withIt)).toEqual({ ...state, [SPOT_STATE_KEY]: null });
    expect(state).toEqual({ back: "/a", current: "/b", position: 2, scroll: null });
    expect(withIt[SPOT_STATE_KEY]).toEqual({ at: "p-C1", y: "10" });
    expect(stateWithoutSpot(null)).toEqual({ [SPOT_STATE_KEY]: null });
  });

  it("주소나 state 중 한 곳에라도 자리가 있으면 Nuxt 의 스크롤을 끈다", () => {
    expect(holdsReturnSpot({ q: "nlp" }, null)).toBe(false);
    expect(holdsReturnSpot({ q: "nlp" }, { [SPOT_STATE_KEY]: null })).toBe(false);
    expect(holdsReturnSpot({ at: "p-C1" }, null)).toBe(true);
    expect(holdsReturnSpot({ q: "nlp" }, { [SPOT_STATE_KEY]: { at: "p-C1", y: "120" } })).toBe(true);
  });
});

describe("isUserMove", () => {
  it("휠은 세로가 앞설 때만 움직임이다 — 가로 스와이프의 관성 휠은 아니다", () => {
    expect(isUserMove({ type: "wheel", deltaX: 0, deltaY: 40 })).toBe(true);
    expect(isUserMove({ type: "wheel", deltaX: 30, deltaY: -30 })).toBe(true);
    expect(isUserMove({ type: "wheel", deltaX: -60, deltaY: 4 })).toBe(false);
    expect(isUserMove({ type: "wheel", deltaX: 0, deltaY: 0 })).toBe(false);
  });

  it("누르기·터치·키 입력은 움직임이다", () => {
    expect(isUserMove({ type: "touchstart" })).toBe(true);
    expect(isUserMove({ type: "pointerdown", button: 0 })).toBe(true);
    expect(isUserMove({ type: "pointerdown", button: 2 })).toBe(true);
    expect(isUserMove({ type: "keydown", key: "PageDown" })).toBe(true);
    expect(isUserMove({ type: "keydown", key: "Tab" })).toBe(true);
    expect(isUserMove({ type: "keydown", key: "ArrowDown", metaKey: true })).toBe(true);
    expect(isUserMove({ type: "keydown", key: "ArrowLeft" })).toBe(true);
  });

  it("브라우저의 뒤로·앞으로·새로고침 손짓은 움직임이 아니다", () => {
    expect(isUserMove({ type: "pointerdown", button: 3 })).toBe(false);
    expect(isUserMove({ type: "pointerdown", button: 4 })).toBe(false);
    expect(isUserMove({ type: "keydown", key: "Alt", altKey: true })).toBe(false);
    expect(isUserMove({ type: "keydown", key: "ArrowRight", altKey: true })).toBe(false);
    expect(isUserMove({ type: "keydown", key: "[", metaKey: true })).toBe(false);
    expect(isUserMove({ type: "keydown", key: "F5" })).toBe(false);
    expect(isUserMove({ type: "keydown", key: "R", ctrlKey: true })).toBe(false);
  });
});
