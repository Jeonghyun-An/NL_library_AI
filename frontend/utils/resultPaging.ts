// frontend/utils/resultPaging.ts
// 결과 목록의 정렬·쪽 나누기 — 논문 결과(pages/papers)와 소장자료 결과(pages/index.vue)가 같은 규칙을 쓴다.
// 화면 상태 없이 순수하게 도는 부분만 여기 둔다

export type SortKey = "relevance" | "name" | "date_desc";

/** 목록 머리의 정렬 버튼 — 화면에 보이는 순서 */
export const SORT_OPTIONS: readonly { key: SortKey; label: string }[] = [
  { key: "relevance", label: "관련도순" },
  { key: "name", label: "이름순" },
  { key: "date_desc", label: "최신순" },
];

/** 한 쪽에 보일 개수 선택지 */
export const PAGE_SIZES = [10, 20, 30, 50] as const;
export type PageSize = (typeof PAGE_SIZES)[number];

export const DEFAULT_SORT: SortKey = "relevance";

export function isSortKey(v: unknown): v is SortKey {
  return SORT_OPTIONS.some((o) => o.key === v);
}

export function isPageSize(v: unknown): v is PageSize {
  return PAGE_SIZES.some((n) => n === v);
}

export interface SortableResult {
  best_score?: number;
  book_info?: { title?: string | null; pub_date?: string | null } | null;
}

/**
 * 결과를 정렬한 새 목록. 같은 값끼리는 받은 순서(= 검색이 준 관련도 순)를 지킨다 — Array.sort 는 안정 정렬이다.
 * relevance 는 종합 점수(best_score) 높은 순, name 은 제목 가나다순, date_desc 는 발행일 최신순(발행일 없는 항목이 맨 뒤)
 */
export function sortResults<T extends SortableResult>(items: readonly T[], key: SortKey): T[] {
  const list = [...items];
  switch (key) {
    case "relevance":
      return list.sort((a, b) => (b.best_score ?? 0) - (a.best_score ?? 0));
    case "name":
      return list.sort((a, b) => (a.book_info?.title ?? "").localeCompare(b.book_info?.title ?? "", "ko"));
    case "date_desc":
      return list.sort((a, b) => (b.book_info?.pub_date ?? "").localeCompare(a.book_info?.pub_date ?? ""));
  }
}

/** 전체 쪽 수. 목록이 비어도 1 쪽이다 */
export function pageCount(total: number, size: number): number {
  return Math.max(1, Math.ceil(total / size));
}

/** 쪽 번호를 1 ~ 마지막 쪽 안으로 맞춘다 — 개수가 줄거나 쪽 크기가 커진 뒤에도 빈 쪽을 가리키지 않게 */
export function clampPage(page: number, total: number, size: number): number {
  if (!Number.isFinite(page)) return 1;
  return Math.min(Math.max(1, Math.floor(page)), pageCount(total, size));
}

/** page(1부터) 쪽에 보일 항목 */
export function pageSlice<T>(items: readonly T[], page: number, size: number): T[] {
  return items.slice((page - 1) * size, page * size);
}

/** 쪽 번호 줄 — 7 쪽까지는 모두, 그 넘으면 처음·끝과 현재 쪽 앞뒤만 두고 사이는 "..." 로 줄인다 */
export function pageButtons(total: number, cur: number): (number | "...")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "...")[] = [1];
  if (cur > 3) pages.push("...");
  for (let i = Math.max(2, cur - 1); i <= Math.min(total - 1, cur + 1); i++) pages.push(i);
  if (cur < total - 2) pages.push("...");
  pages.push(total);
  return pages;
}

// ── 목록 보기 상태(정렬·개수·쪽)를 그 방문 기록(history.state)에 남긴다 ─────────────────────────
// 주소(쿼리)에는 싣지 않는다 — 논문 결과도 정렬·쪽을 주소에 싣지 않는다. 상세에서 뒤로 가기·새로고침으로 같은 기록에 돌아오면
// 그 기록의 state 에서 읽어 같은 정렬·쪽을 다시 연다. 새로 연 기록(사이드바·새 검색)은 state 가 없어 기본값으로 시작한다
export interface ListView {
  sortBy: SortKey;
  pageSize: PageSize;
  page: number;
}

const LIST_VIEW_KEY = "skxListView";

/** state 에 목록 보기를 얹은 새 state — 라우터가 둔 다른 키(back·current·position·scroll 등)는 그대로 둔다 */
export function stateWithListView(state: unknown, view: ListView): Record<string, unknown> {
  const base = typeof state === "object" && state !== null ? (state as Record<string, unknown>) : {};
  return { ...base, [LIST_VIEW_KEY]: { sortBy: view.sortBy, pageSize: view.pageSize, page: view.page } };
}

/** state 에서 목록 보기를 읽는다. 없거나 모양이 틀리면 null(기본값으로 연다) */
export function listViewFromState(state: unknown): ListView | null {
  if (typeof state !== "object" || state === null) return null;
  const raw = (state as Record<string, unknown>)[LIST_VIEW_KEY];
  if (typeof raw !== "object" || raw === null) return null;
  const { sortBy, pageSize, page } = raw as Record<string, unknown>;
  if (!isSortKey(sortBy) || !isPageSize(pageSize)) return null;
  if (typeof page !== "number" || !Number.isInteger(page) || page < 1) return null;
  return { sortBy, pageSize, page };
}
