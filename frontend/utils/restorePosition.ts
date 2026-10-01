// frontend/utils/restorePosition.ts
import type { ReturnSpot } from "~/utils/detailSource";

// 내용이 준비된 뒤에도 늦게 붙는 목록(탐색 타임라인의 이벤트 재생 등)을 이만큼 기다린다
export const RESTORE_MAX_WAIT_MS = 2000;
export const RESTORE_RETRY_MS = 100;
// 창이 줄어 떠날 때의 높이가 화면 밖이면 요소가 이만큼은 보이게 올린다
const KEEP_VISIBLE_PX = 48;

export type QueryValue = string | null | (string | null)[];
export type RestoreStep = "align" | "retry" | "give-up";

export function scrollDelta(elementTop: number, targetY: number): number {
  return Math.round(elementTop - targetY);
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

export function hasSpot(query: Readonly<Record<string, unknown>>): boolean {
  return "at" in query || "y" in query;
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
