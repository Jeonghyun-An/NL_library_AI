// frontend/tests/unit/resultPaging.test.ts
import { describe, expect, it } from "vitest";
import {
  PAGE_SIZES,
  SORT_OPTIONS,
  clampPage,
  isPageSize,
  isSortKey,
  listViewFromState,
  pageButtons,
  pageCount,
  pageSlice,
  restoredPage,
  sortResults,
  stateWithListView,
  type SortableResult,
} from "~/utils/resultPaging";

interface Row extends SortableResult {
  id: string;
}

function row(id: string, score: number, title: string | null, pubDate: string | null): Row {
  return { id, best_score: score, book_info: { title, pub_date: pubDate } };
}

const rows: Row[] = [
  row("a", 0.9, "다 책", "1992"),
  row("b", 0.7, "가 책", "1997"),
  row("c", 0.7, "나 책", null),
  row("d", 0.5, "라 책", "1983"),
  row("e", 0.3, "마 책", "1997"),
];

const ids = (list: Row[]) => list.map((r) => r.id);

describe("sortResults — 정렬", () => {
  it("관련도순은 종합 점수 높은 순이고, 같은 점수는 받은 순서를 지킨다", () => {
    expect(ids(sortResults(rows, "relevance"))).toEqual(["a", "b", "c", "d", "e"]);
    // 받은 순서를 바꿔도 같은 점수(b, c)는 받은 순서 그대로
    expect(ids(sortResults([rows[2]!, rows[1]!, rows[0]!], "relevance"))).toEqual(["a", "c", "b"]);
  });

  it("이름순은 제목 가나다순이다", () => {
    expect(ids(sortResults(rows, "name"))).toEqual(["b", "c", "a", "d", "e"]);
  });

  it("최신순은 발행일 늦은 순이고, 발행일이 없는 항목은 맨 뒤, 같은 해는 받은 순서를 지킨다", () => {
    expect(ids(sortResults(rows, "date_desc"))).toEqual(["b", "e", "a", "d", "c"]);
  });

  it("제목·발행일·점수가 없어도 던지지 않고 뒤로 보낸다", () => {
    const sparse: Row[] = [{ id: "x" }, row("y", 0.8, "가", "2001"), { id: "z", book_info: null }];
    expect(ids(sortResults(sparse, "relevance"))).toEqual(["y", "x", "z"]);
    expect(ids(sortResults(sparse, "name"))).toEqual(["x", "z", "y"]);
    expect(ids(sortResults(sparse, "date_desc"))).toEqual(["y", "x", "z"]);
  });

  it("받은 목록을 바꾸지 않고 새 목록을 돌려준다", () => {
    const input = [...rows];
    const out = sortResults(input, "name");
    expect(out).not.toBe(input);
    expect(ids(input)).toEqual(ids(rows));
  });

  it("정렬 선택지는 관련도순·이름순·최신순이고 알아보는 키는 이 셋뿐이다", () => {
    expect(SORT_OPTIONS.map((o) => o.label)).toEqual(["관련도순", "이름순", "최신순"]);
    expect(isSortKey("name")).toBe(true);
    expect(isSortKey("date_asc")).toBe(false);
    expect(isSortKey(undefined)).toBe(false);
  });
});

describe("쪽 나누기", () => {
  const items = Array.from({ length: 23 }, (_, i) => i + 1);

  it("전체 쪽 수는 올림이고 빈 목록도 1 쪽이다", () => {
    expect(pageCount(23, 10)).toBe(3);
    expect(pageCount(20, 10)).toBe(2);
    expect(pageCount(1, 10)).toBe(1);
    expect(pageCount(0, 10)).toBe(1);
  });

  it("page 쪽의 항목만 자르고 마지막 쪽은 남은 만큼이다", () => {
    expect(pageSlice(items, 1, 10)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(pageSlice(items, 3, 10)).toEqual([21, 22, 23]);
    expect(pageSlice(items, 2, 20)).toEqual([21, 22, 23]);
    expect(pageSlice(items, 1, 50)).toHaveLength(23);
  });

  it("쪽 번호는 1 ~ 마지막 쪽 안으로 맞춘다", () => {
    expect(clampPage(0, 23, 10)).toBe(1);
    expect(clampPage(-4, 23, 10)).toBe(1);
    expect(clampPage(9, 23, 10)).toBe(3);
    expect(clampPage(2, 23, 10)).toBe(2);
    expect(clampPage(2.7, 23, 10)).toBe(2);
    expect(clampPage(Number.NaN, 23, 10)).toBe(1);
  });

  it("개수 선택지는 10·20·30·50 이다", () => {
    expect([...PAGE_SIZES]).toEqual([10, 20, 30, 50]);
    expect(isPageSize(20)).toBe(true);
    expect(isPageSize(15)).toBe(false);
    expect(isPageSize("20")).toBe(false);
  });
});

describe("pageButtons — 쪽 번호 줄", () => {
  it("7 쪽까지는 모두 보인다", () => {
    expect(pageButtons(1, 1)).toEqual([1]);
    expect(pageButtons(4, 2)).toEqual([1, 2, 3, 4]);
    expect(pageButtons(7, 4)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("8 쪽부터는 처음·끝과 현재 쪽 앞뒤만 두고 사이를 줄인다", () => {
    expect(pageButtons(10, 1)).toEqual([1, 2, "...", 10]);
    expect(pageButtons(10, 3)).toEqual([1, 2, 3, 4, "...", 10]);
    expect(pageButtons(10, 5)).toEqual([1, "...", 4, 5, 6, "...", 10]);
    expect(pageButtons(10, 8)).toEqual([1, "...", 7, 8, 9, 10]);
    expect(pageButtons(10, 10)).toEqual([1, "...", 9, 10]);
  });
});

describe("restoredPage — 기록을 다시 열 때의 쪽", () => {
  const saved = { sortBy: "name", pageSize: 10, page: 3 } as const;

  it("누른 카드가 있는 쪽이 남긴 쪽보다 먼저다", () => {
    expect(restoredPage(2, saved, 60, 10)).toBe(2);
    expect(restoredPage(1, saved, 60, 10)).toBe(1);
  });

  it("누른 카드가 없으면 남긴 쪽, 둘 다 없으면 첫 쪽", () => {
    expect(restoredPage(null, saved, 60, 10)).toBe(3);
    expect(restoredPage(null, null, 60, 10)).toBe(1);
  });

  it("어느 쪽이든 지금 목록 길이 안으로 맞춘다", () => {
    expect(restoredPage(null, saved, 15, 10)).toBe(2);
    expect(restoredPage(9, null, 15, 10)).toBe(2);
    expect(restoredPage(null, { ...saved, page: 4 }, 0, 10)).toBe(1);
  });
});

describe("목록 보기 상태(history.state)", () => {
  const view = { sortBy: "name", pageSize: 20, page: 2 } as const;

  it("실어 두면 그대로 읽힌다", () => {
    expect(listViewFromState(stateWithListView({}, view))).toEqual(view);
  });

  it("라우터가 둔 다른 키는 그대로 둔다", () => {
    const state = { back: "/x", current: "/y", position: 3, scroll: { left: 0, top: 10 } };
    const next = stateWithListView(state, view);
    expect(next).toMatchObject(state);
    expect(next).not.toBe(state);
    expect(state).not.toHaveProperty("skxListView");
  });

  it("state 가 없거나 객체가 아니어도 새 객체로 만든다", () => {
    expect(listViewFromState(stateWithListView(null, view))).toEqual(view);
    expect(listViewFromState(stateWithListView("x", view))).toEqual(view);
  });

  it("없거나 모양이 틀리면 null 이다 — 기본값으로 연다", () => {
    expect(listViewFromState(null)).toBeNull();
    expect(listViewFromState({})).toBeNull();
    expect(listViewFromState({ skxListView: null })).toBeNull();
    expect(listViewFromState({ skxListView: { sortBy: "name", pageSize: 15, page: 1 } })).toBeNull();
    expect(listViewFromState({ skxListView: { sortBy: "oldest", pageSize: 10, page: 1 } })).toBeNull();
    expect(listViewFromState({ skxListView: { sortBy: "name", pageSize: 10, page: 0 } })).toBeNull();
    expect(listViewFromState({ skxListView: { sortBy: "name", pageSize: 10, page: 1.5 } })).toBeNull();
    expect(listViewFromState({ skxListView: { sortBy: "name", pageSize: 10, page: "2" } })).toBeNull();
  });
});
