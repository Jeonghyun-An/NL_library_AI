// frontend/utils/paperResearch.ts
// 논문 상세의 [이 논문으로 딥리서치] — 제목·키워드로 질문 초안을 만들어 논문 검색 입력창으로 넘긴다

// 부제까지 붙은 긴 제목이나 문장형 키워드가 질문을 다 차지하지 않게 자른다(서버 한도 QUESTION_MAX 500자 안쪽)
const TITLE_MAX = 120;
const KEYWORD_MAX = 30;
const KEYWORDS = 3;

// 파이썬 len 과 같게 코드포인트로 센다(researchInput 과 같은 이유)
function clip(text: string, max: number): string {
  const chars = [...text];
  return chars.length > max ? `${chars.slice(0, max).join("")}…` : text;
}

// 조사(을/를·와/과)는 앞 글자의 받침에 따라 바뀐다 — 제목·키워드 바로 뒤에는 받침과 무관한 말만 붙인다
export function paperResearchQuestion(title: string, keywords: readonly string[]): string {
  const name = title.trim().replace(/\s+/g, " ");
  if (!name) return "";
  const picked = keywords
    .map((k) => k.trim())
    .filter(Boolean)
    .slice(0, KEYWORDS)
    .map((k) => clip(k, KEYWORD_MAX));
  const topic = picked.length ? `${picked.join("·")} 관련` : "이 주제의";
  return `「${clip(name, TITLE_MAX)}」에서 출발해, ${topic} 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?`;
}

export function paperResearchUrl(question: string): string {
  return `/papers?${new URLSearchParams({ draft: question })}`;
}

// /papers 가 받는 질문 초안(?draft=). 없거나 빈 값이면 null
export function readResearchDraft(query: Record<string, unknown>): string | null {
  const raw = Array.isArray(query.draft) ? query.draft[0] : query.draft;
  return typeof raw === "string" && raw.trim() ? raw.trim() : null;
}
