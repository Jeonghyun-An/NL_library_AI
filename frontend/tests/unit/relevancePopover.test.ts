// frontend/tests/unit/relevancePopover.test.ts
import { describe, expect, it } from "vitest";
import { INITIAL_POPOVER, popoverReduce, type PopoverEvent, type PopoverState } from "~/utils/relevancePopover";

function run(events: PopoverEvent[], from: PopoverState = INITIAL_POPOVER): PopoverState {
  return events.reduce(popoverReduce, from);
}

describe("popoverReduce — 관련도 팝오버 열기·닫기", () => {
  it("처음에는 닫혀 있다", () => {
    expect(INITIAL_POPOVER).toEqual({ open: false, by: null, pointerDown: false });
  });

  it("호버(지연 뒤)로 열리고 마우스가 떠나면(지연 뒤) 닫힌다", () => {
    const opened = run(["hover-open"]);
    expect(opened).toMatchObject({ open: true, by: "hover" });
    expect(run(["hover-open", "hover-close"]).open).toBe(false);
  });

  it("키보드 초점으로 열리고 초점이 떠나면 닫힌다", () => {
    expect(run(["focus"])).toMatchObject({ open: true, by: "focus" });
    expect(run(["focus", "blur"]).open).toBe(false);
  });

  it("마우스로 누를 때는 초점이 click 보다 먼저 와도 열었다 닫는 깜박임이 없다", () => {
    // pointerdown → focus → click: 초점은 열지 않고, click 이 열어 고정한다
    const afterFocus = run(["pointer-down", "focus"]);
    expect(afterFocus.open).toBe(false);
    expect(run(["pointer-down", "focus", "click"])).toMatchObject({ open: true, by: "click", pointerDown: false });
  });

  it("호버·초점으로 열린 뒤 누르면 그 자리에 고정하고, 고정된 걸 다시 누르면 닫는다", () => {
    expect(run(["hover-open", "pointer-down", "focus", "click"])).toMatchObject({ open: true, by: "click" });
    expect(run(["focus", "click"])).toMatchObject({ open: true, by: "click" });
    expect(run(["focus", "click", "click"]).open).toBe(false);
  });

  it("고정되면 마우스가 떠나도 닫히지 않는다(호버로 연 것만 떠나면 닫힌다)", () => {
    expect(run(["click", "hover-close"]).open).toBe(true);
    expect(run(["hover-open", "click", "hover-close"]).open).toBe(true);
  });

  // 리뷰 지적: 클릭으로 고정한 팝오버 안을 누르면 버튼의 blur 가 닫아 버렸다
  it("클릭으로 고정한 팝오버 안을 눌러도 닫히지 않는다 — 포인터가 눌린 채 오는 blur 는 무시한다", () => {
    const pinned = run(["pointer-down", "focus", "click"]);
    expect(pinned.open).toBe(true);
    // 팝오버 안을 누름 → 버튼이 초점을 잃는다
    const afterInside = run(["pointer-down", "blur"], pinned);
    expect(afterInside.open).toBe(true);
    // 손을 떼면 누름 상태가 풀리고, 그 뒤 초점이 빠지면 닫힌다
    const released = run(["pointer-up"], afterInside);
    expect(released).toMatchObject({ open: true, pointerDown: false });
    expect(run(["blur"], released).open).toBe(false);
  });

  it("키보드로 고정(Enter)한 뒤 Tab 으로 벗어나면 닫힌다", () => {
    expect(run(["focus", "click", "blur"]).open).toBe(false);
  });

  it("이미 클릭으로 고정돼 있으면 초점이 와도 호버·초점으로 내려가지 않는다", () => {
    expect(run(["click", "focus"])).toMatchObject({ open: true, by: "click" });
  });

  it("Esc·바깥 누름은 어떤 방식으로 열렸든 닫는다", () => {
    for (const first of [["hover-open"], ["focus"], ["click"]] as PopoverEvent[][]) {
      expect(run([...first, "escape"]).open).toBe(false);
      expect(run([...first, "outside-pointer-down"]).open).toBe(false);
    }
  });

  it("닫을 때 누름 상태도 풀린다", () => {
    expect(run(["pointer-down", "escape"])).toEqual(INITIAL_POPOVER);
  });

  it("열려 있을 때 호버 열기가 또 와도 방식이 바뀌지 않는다", () => {
    expect(run(["click", "hover-open"])).toMatchObject({ open: true, by: "click" });
  });
});
