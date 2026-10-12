// frontend/utils/landingStart.ts
// 사이드바 딥리서치 묶음의 [+ 연구 시작하기] — 랜딩('/')을 ?start=deep-research 로 열면 논문 패널에 딥리서치 모드를 켜고
// 입력창에 초점을 준다. 이미 '/' 에 있어도 쿼리가 바뀌므로 같은 경로로 동작하고, 처리한 뒤 쿼리는 지운다
import { firstValue } from "~/utils/detailSource";

export const START_DEEP_RESEARCH = "deep-research";

export function deepResearchStartRoute(): { path: string; query: { start: string } } {
  return { path: "/", query: { start: START_DEEP_RESEARCH } };
}

/** 주소의 ?start= — 딥리서치 시작 요청이면 값을, 아니면 null */
export function readStart(query: Record<string, unknown>): typeof START_DEEP_RESEARCH | null {
  return firstValue(query.start) === START_DEEP_RESEARCH ? START_DEEP_RESEARCH : null;
}

/** 처리한 뒤 주소에 남길 쿼리 — start 만 뺀다(남기면 새로고침·뒤로 가기마다 다시 켜진다) */
export function queryWithoutStart<T extends Record<string, unknown>>(query: T): Omit<T, "start"> {
  const { start: _start, ...rest } = query;
  return rest;
}
