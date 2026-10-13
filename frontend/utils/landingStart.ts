// frontend/utils/landingStart.ts
// 사이드바 DeepResearch 묶음의 [+ 연구 시작하기]·소장자료 결과의 [DeepResearch로 이어서 조사하기] — 랜딩('/')을
// ?start=deep-research 로 열면 논문 패널에 DeepResearch 모드를 켜고 입력창에 초점을 준다. ?draft= 가 함께 오면 그 질문을 입력창에
// 채운다(연구는 시작하지 않는다). 이미 '/' 에 있어도 쿼리가 바뀌므로 같은 경로로 동작하고, 처리한 뒤 두 쿼리는 지운다
import { firstValue } from "~/utils/detailSource";
import { questionProblem } from "~/utils/researchInput";

export const START_DEEP_RESEARCH = "deep-research";

// 질문 초안 — 줄바꿈·겹친 공백은 한 칸으로. 질문으로 쓸 수 없는 길이(서버 QUESTION_MIN·MAX 와 같은 경계)면 싣지 않는다
function draftQuestion(text: string | undefined): string | null {
  const q = (text ?? "").replace(/\s+/g, " ").trim();
  return q && !questionProblem(q) ? q : null;
}

export function deepResearchStartRoute(draft?: string): { path: string; query: Record<string, string> } {
  const question = draftQuestion(draft);
  return { path: "/", query: question ? { start: START_DEEP_RESEARCH, draft: question } : { start: START_DEEP_RESEARCH } };
}

/** 주소의 ?start= — 딥리서치 시작 요청이면 값을, 아니면 null */
export function readStart(query: Record<string, unknown>): typeof START_DEEP_RESEARCH | null {
  return firstValue(query.start) === START_DEEP_RESEARCH ? START_DEEP_RESEARCH : null;
}

/** 함께 온 질문 초안(?draft=) — 없거나 질문으로 쓸 수 없으면 null */
export function readStartDraft(query: Record<string, unknown>): string | null {
  return draftQuestion(firstValue(query.draft));
}

/** 처리한 뒤 주소에 남길 쿼리 — start·draft 만 뺀다(남기면 새로고침·뒤로 가기마다 다시 켜지고 고쳐 쓰던 글을 초안이 덮는다) */
export function queryWithoutStart<T extends Record<string, unknown>>(query: T): Omit<T, "start" | "draft"> {
  const { start: _start, draft: _draft, ...rest } = query;
  return rest;
}
