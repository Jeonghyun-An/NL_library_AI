// frontend/utils/restorePosition.ts
import type { ReturnSpot } from "~/utils/detailSource";

// 내용이 준비된 뒤에도 늦게 붙는 목록(탐색 타임라인의 이벤트 재생 등)을 이만큼 기다린다
export const RESTORE_MAX_WAIT_MS = 2000;
export const RESTORE_RETRY_MS = 100;
// 맞춘 요소를 사용자가 움직이기 전까지 붙잡아 두는 한도. 검색 결과로 돌아와 끝나지 않았던 AI 요약을 다시 받으면 스트림이
// 끝날 때까지 위쪽 요약이 자라고 끝에 인용 논문을 목록 맨 위로 올려, 그 스트림이 걸리는 만큼(길면 이 정도) 카드가 밀린다
export const RESTORE_HOLD_MS = 15000;
// 창이 줄어 떠날 때의 높이가 화면 밖이면 요소가 이만큼은 보이게 올린다
const KEEP_VISIBLE_PX = 48;
// 맞춘 자리를 그 기록의 history.state 에 남기는 열쇠 — 값은 주소의 at·y 와 같은 문자열이라 readReturnSpot 이 그대로 읽는다
export const SPOT_STATE_KEY = "skxSpot";
// 브라우저의 뒤로·앞으로·새로고침 손짓에 쓰이는 키
const MODIFIER_KEYS = new Set(["Alt", "Control", "Meta", "Shift"]);
const HISTORY_KEYS = new Set(["ArrowLeft", "ArrowRight", "[", "]"]);

export type QueryValue = string | null | (string | null)[];
export type RestoreStep = "align" | "retry" | "give-up";
export type SpotQuery = { at: string; y?: string };
export type SpotState = Record<typeof SPOT_STATE_KEY, SpotQuery | null>;
// 사용자 입력 이벤트에서 움직임을 가리는 데 보는 값 — 이벤트 종류마다 있는 것만 온다
export type UserInput = {
  type: string;
  deltaX?: number;
  deltaY?: number;
  button?: number;
  key?: string;
  altKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
};

export function scrollDelta(elementTop: number, targetY: number): number {
  return Math.round(elementTop - targetY);
}

// 붙잡는 동안은 1px 넘게 밀렸을 때만 되돌린다 — 소수점 아래 차이로 매 프레임 굴리지 않게
export function holdDelta(elementTop: number, targetY: number): number {
  const off = elementTop - targetY;
  return Math.abs(off) >= 1 ? Math.round(off) : 0;
}

// 떠날 때 높이를 모르면(새 창 링크를 높이 없이 연 경우) 화면 위쪽 1/3 에 둔다
export function targetTop(y: number | null, viewportHeight: number): number {
  if (y === null) return Math.round(viewportHeight / 3);
  return Math.min(y, Math.max(0, viewportHeight - KEEP_VISIBLE_PX));
}

export function restoreStep(found: boolean, now: number, deadline: number): RestoreStep {
  if (found) return "align";
  return now < deadline ? "retry" : "give-up";
}

export function spotOf(el: Pick<Element, "getBoundingClientRect">, at: string): ReturnSpot {
  return { at, y: Math.max(0, Math.round(el.getBoundingClientRect().top)) };
}

// 새 창·새 탭으로 여는 클릭(수식 키·가운데 버튼)은 브라우저에 맡긴다
export function isPlainClick(e: Pick<MouseEvent, "button" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">): boolean {
  return e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey;
}

// 브라우저의 뒤로·앞으로·새로고침(마우스 옆 버튼, Alt·Cmd+방향키·대괄호, F5·Ctrl+R, 수식 키만 누름) — 화면 안에서
// 자리를 옮기는 손짓이 아니다. 움직임으로 치면 맞춘 자리를 지워 앞으로 갔다 다시 돌아올 때 그 자리를 잃는다
function isHistoryGesture(e: UserInput): boolean {
  if (e.type === "pointerdown") return e.button === 3 || e.button === 4;
  if (e.type !== "keydown" || e.key === undefined) return false;
  if (MODIFIER_KEYS.has(e.key) || e.key === "F5") return true;
  if ((e.altKey || e.metaKey) && HISTORY_KEYS.has(e.key)) return true;
  return !!(e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "r";
}

// 사용자가 화면을 움직이려는 입력인지. 휠은 세로가 앞설 때만 — 맥 트랙패드의 두 손가락 뒤로 가기가 남긴 가로 관성 휠이
// 돌아온 화면에 떨어져도 맞추기를 취소하지 않게
export function isUserMove(e: UserInput): boolean {
  if (e.type === "wheel") {
    const dy = Math.abs(e.deltaY ?? 0);
    return dy > 0 && dy >= Math.abs(e.deltaX ?? 0);
  }
  return !isHistoryGesture(e);
}

export function hasSpot(query: Readonly<Record<string, unknown>>): boolean {
  return "at" in query || "y" in query;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// 모양만 본다 — 앵커·높이의 값은 readReturnSpot 이 주소의 at·y 와 똑같이 가린다
export function spotFromState(state: unknown): SpotQuery | null {
  const v = isRecord(state) ? state[SPOT_STATE_KEY] : null;
  if (!isRecord(v) || typeof v.at !== "string") return null;
  if (v.y === undefined) return { at: v.at };
  return typeof v.y === "string" ? { at: v.at, y: v.y } : null;
}

// router.replace 의 state 로 넘기는 조각 — vue-router 는 이것을 지금 기록의 state 위에 덮어 자기 열쇠(back·current·
// position 등)를 지킨다. 지금 state 를 통째로 넘기면 옛 current(at·y 를 실은 주소)가 새 주소를 덮는다
export function spotState(spot: ReturnSpot | null): SpotState {
  if (!spot?.at) return { [SPOT_STATE_KEY]: null };
  return { [SPOT_STATE_KEY]: spot.y === null ? { at: spot.at } : { at: spot.at, y: String(spot.y) } };
}

export function stateWithSpot(state: unknown, spot: ReturnSpot | null): Record<string, unknown> {
  return { ...(isRecord(state) ? state : {}), ...spotState(spot) };
}

// 열쇠를 빼지 않고 null 로 둔다 — vue-router 의 push 는 떠나는 기록에 자기가 쥔 state 사본 위에 history.state 를 덮어
// 다시 적어, 열쇠를 빼면 사본에 남은 옛 자리가 되살아난다
export function stateWithoutSpot(state: unknown): Record<string, unknown> {
  return stateWithSpot(state, null);
}

// 돌아왔을 때 맞출 자리가 주소나 그 기록의 state 에 있는지 — 있으면 Nuxt 는 굴리지 않고 화면이 직접 맞춘다.
// Nuxt 의 scrollToTop 이 불리는 때의 history.state 는 들어갈 기록의 것이다(뒤로·앞으로는 브라우저가 이미 바꿨고,
// push 는 pushState 뒤에 스크롤을 정한다)
export function holdsReturnSpot(query: Readonly<Record<string, unknown>>, state: unknown): boolean {
  return hasSpot(query) || spotFromState(state) !== null;
}

export function withoutSpot(query: Readonly<Record<string, QueryValue>>): Record<string, QueryValue> {
  const out = { ...query };
  delete out.at;
  delete out.y;
  return out;
}

export function withSpot(query: Readonly<Record<string, QueryValue>>, spot: ReturnSpot): Record<string, QueryValue> {
  const out = withoutSpot(query);
  if (spot.at) {
    out.at = spot.at;
    if (spot.y !== null) out.y = String(spot.y);
  }
  return out;
}

export function pageOfItem(ids: readonly string[], id: string, pageSize: number): number | null {
  const i = ids.indexOf(id);
  return i < 0 ? null : Math.floor(i / pageSize) + 1;
}
