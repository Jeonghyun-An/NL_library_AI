// frontend/utils/relevancePopover.ts
// 관련도 팝오버(RelevanceBadge)의 열기·닫기 전환 — 호버·초점·누름(탭)·Esc·바깥 누름이 서로 얽히는 규칙을 한 곳에 둔다.
// 지연 타이머(호버 열기·닫기)와 DOM 은 화면이 맡고, 여기서는 "이 일이 일어나면 상태가 어떻게 되는가"만 정한다.

export type PopoverBy = "hover" | "focus" | "click";

export interface PopoverState {
  open: boolean;
  /** 어떻게 열렸나 — 호버로 열린 건 마우스가 떠나면, 초점으로 열린 건 초점이 떠나면 닫고, 누른 건(고정) 다시 누를 때까지 둔다 */
  by: PopoverBy | null;
  /** 알약·팝오버 안에서 포인터가 눌려 있다 — 이때 오는 blur 는 안을 누르느라 초점이 빠진 것이라 닫지 않는다 */
  pointerDown: boolean;
}

export type PopoverEvent =
  | "hover-open" // 마우스를 올리고 지연이 지났다
  | "hover-close" // 마우스가 떠나고 지연이 지났다
  | "focus"
  | "blur"
  | "pointer-down" // 알약·팝오버 안에서 눌렀다
  | "pointer-up"
  | "click" // 알약을 눌렀다(터치는 탭)
  | "escape"
  | "outside-pointer-down";

export const INITIAL_POPOVER: PopoverState = { open: false, by: null, pointerDown: false };

const CLOSED = INITIAL_POPOVER;

export function popoverReduce(state: PopoverState, event: PopoverEvent): PopoverState {
  switch (event) {
    case "hover-open":
      return state.open ? state : { ...state, open: true, by: "hover" };
    case "hover-close":
      return state.open && state.by === "hover" ? CLOSED : state;
    case "pointer-down":
      return { ...state, pointerDown: true };
    case "pointer-up":
      return { ...state, pointerDown: false };
    case "focus":
      // 마우스로 누르는 중의 초점은 열지 않는다(곧 오는 click 이 열어 고정한다). 고정된 것을 내리지도 않는다
      if (state.pointerDown || (state.open && state.by === "click")) return state;
      return { ...state, open: true, by: "focus" };
    case "blur":
      return state.pointerDown ? state : CLOSED;
    case "click":
      // 호버·초점으로 이미 열려 있으면 그 자리에 고정한다. 고정된 걸 다시 누르면 닫는다
      if (state.open && state.by === "click") return CLOSED;
      return { open: true, by: "click", pointerDown: false };
    case "escape":
    case "outside-pointer-down":
      return CLOSED;
  }
}
