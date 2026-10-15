// frontend/composables/useListView.ts
import { watch, type Ref } from "vue";
import { listViewFromState, stateWithListView, type ListView, type PageSize, type SortKey } from "~/utils/resultPaging";

/**
 * 결과 목록의 보기(정렬·한 쪽 개수·쪽)를 그 방문 기록(history.state)에 남긴다 — 논문·소장자료 결과가 같이 쓴다.
 * 주소에는 싣지 않는다. 상세에서 뒤로 가기·[검색 목록 돌아가기]·새로고침으로 같은 기록에 돌아오면 savedListView() 로 읽어 다시 연다.
 * active 가 거짓이면(랜딩 등 결과가 없을 때) 남기지 않는다 — 결과 없는 방문 기록에 보기가 묻지 않게.
 * 라우터가 둔 다른 state 키(back·current·position·scroll·돌아갈 자리)는 그대로 둔다
 */
export function rememberListView(
  sortBy: Ref<SortKey>,
  pageSize: Ref<PageSize>,
  page: Ref<number>,
  active: () => boolean,
): void {
  watch([sortBy, pageSize, page], () => {
    if (!import.meta.client || !active()) return;
    window.history.replaceState(
      stateWithListView(window.history.state, { sortBy: sortBy.value, pageSize: pageSize.value, page: page.value }),
      "",
    );
  });
}

/** 이 방문 기록에 남은 보기. 없거나 모양이 틀리면 null(기본값으로 연다) */
export function savedListView(): ListView | null {
  return listViewFromState(import.meta.client ? window.history.state : null);
}
