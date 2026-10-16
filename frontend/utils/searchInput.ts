// frontend/utils/searchInput.ts
// 검색 입력창 보내기 버튼의 상태 판정 — 글자가 있으면 포인트색으로 채워지고, 없으면 옅은 중립색이다(style_skovix.css 의 .skx-send).
// 상태는 aria-disabled 로 알린다(disabled 로 막지 않는다 — 비활성 속성은 대비를 떨어뜨리고, 빈 입력의 클릭은 원래 아무 일도 하지 않는다).

/** 공백(스페이스·탭·줄바꿈·전각 공백)만 있으면 빈 것으로 본다 */
export function hasQuery(text: unknown): boolean {
  return typeof text === "string" && text.trim().length > 0;
}

// 검색어 글자 수 한도 — 서버 SearchRequest.query max_length 와 같다
export const SEARCH_QUERY_MAX = 500;
