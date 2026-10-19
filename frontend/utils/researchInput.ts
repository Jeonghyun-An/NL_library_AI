// frontend/utils/researchInput.ts
// 서버 검증(api/research.py 의 ResearchCreate·PlanItem)과 같은 경계. 여기서 먼저 막아
// 사용자가 422 의 영문 pydantic 메시지를 보지 않게 한다. 문구는 해요체(사용자 결정 2026-10-16 — 오류 문구는 '~해 주세요'·'~있어요').
export const QUESTION_MIN = 2;
export const QUESTION_MAX = 500;
export const PLAN_ITEM_MIN = 2;
export const PLAN_ITEM_MAX = 300;
// 백엔드 state.DEFAULT_PARAMS 와 같은 값 — GET 응답에 params 가 없는 옛 API 대비
export const DEFAULT_MAX_SUBQUESTIONS = 6;

// 파이썬 len 은 코드포인트를 센다 — JS length(UTF-16)로 세면 이모지에서 어긋난다
function codepoints(text: string): number {
  return [...text].length;
}

export function questionProblem(question: string): string | null {
  const n = codepoints(question.trim());
  if (n < QUESTION_MIN) return `연구 질문을 ${QUESTION_MIN}자 이상 입력해 주세요`;
  if (n > QUESTION_MAX) return `연구 질문은 ${QUESTION_MAX}자까지 입력할 수 있어요`;
  return null;
}

// planner.query_key 와 같은 규칙 — 서버가 중복으로 거절할 항목을 화면이 먼저 알린다
export function planKey(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLowerCase();
}

export function planProblem(items: string[], max: number): string | null {
  if (!items.length) return "하위질문이 하나 이상 있어야 해요";
  if (items.length > max) return `하위질문은 ${max}개까지 둘 수 있어요`;
  const seen = new Set<string>();
  for (const [i, raw] of items.entries()) {
    const text = raw.trim();
    const n = codepoints(text);
    if (n < PLAN_ITEM_MIN) return `${i + 1}번 하위질문을 ${PLAN_ITEM_MIN}자 이상 입력해 주세요`;
    if (n > PLAN_ITEM_MAX) return `${i + 1}번 하위질문은 ${PLAN_ITEM_MAX}자까지 입력할 수 있어요`;
    const key = planKey(text);
    if (seen.has(key)) return `${i + 1}번 하위질문이 앞의 것과 같아요`;
    seen.add(key);
  }
  return null;
}
