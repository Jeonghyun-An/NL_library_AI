// frontend/utils/searchInput.ts
// 검색 입력창 공통 — 검색어 글자 수 한도와 보내기 버튼의 상태 판정.
// 보내기 버튼은 글자가 있으면 포인트색으로 채워지고, 없으면 옅은 중립색이다(style_skovix.css 의 .skx-send).
// 상태는 aria-disabled 로 알린다(disabled 로 막지 않는다 — 비활성 속성은 대비를 떨어뜨리고, 빈 입력의 클릭은 원래 아무 일도 하지 않는다).

/**
 * 검색어 글자 수 한도 — 소장자료·논문 검색창 모두(랜딩 두 입력창·결과 검색바·상세 검색바·/papers). 서버 SearchRequest.query 의
 * max_length(app/schemas/book.py — 소장자료·논문 검색이 같은 요청 모양)와 같고, 논문 입력창이 함께 받는 DeepResearch 질문의 한도
 * (app/api/research.py ResearchCreate.question)도 500 이다. 입력창의 maxlength 와 글자 수(SkxCharCount)가 함께 쓴다 — 정의는 여기 한 곳
 */
export const SEARCH_QUERY_MAX = 500;

/** 공백(스페이스·탭·줄바꿈·전각 공백)만 있으면 빈 것으로 본다 */
export function hasQuery(text: unknown): boolean {
  return typeof text === "string" && text.trim().length > 0;
}
