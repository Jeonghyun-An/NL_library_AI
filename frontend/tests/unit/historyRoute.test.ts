// frontend/tests/unit/historyRoute.test.ts
import { describe, expect, it } from "vitest";
import { activeIdFor, activeKindForPath, awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import { ID1, ID2, bookEntry, paperEntry, researchEntry } from "./helpers/fakeHistory";

const MIXED = "AbCdEf01-2345-4789-abcd-0123456789ab";

describe("routeFor", () => {
  it("도서는 / 에 h·q 를 싣는다", () => {
    expect(routeFor(bookEntry(ID1))).toEqual({ path: "/", query: { h: ID1, q: "한국 경제" } });
  });

  it("논문은 /papers 에 등재구분이 있으면 grade 까지 싣는다", () => {
    expect(routeFor(paperEntry(ID1, { params: { grade: "KCI 등재" } }))).toEqual({
      path: "/papers",
      query: { h: ID1, q: "딥러닝 자연어 처리", grade: "KCI 등재" },
    });
    expect(routeFor(paperEntry(ID1))).toEqual({ path: "/papers", query: { h: ID1, q: "딥러닝 자연어 처리" } });
  });

  it("딥리서치는 잡 주소로 간다", () => {
    expect(routeFor(researchEntry(ID2))).toEqual({ path: `/research/${ID2}` });
  });
});

describe("readHistoryQuery", () => {
  it("h 와 q·grade 를 읽는다", () => {
    expect(readHistoryQuery({ h: ID1, q: " 경제 ", grade: "KCI 등재" })).toEqual({
      h: ID1,
      q: "경제",
      grade: "KCI 등재",
    });
  });

  it("옛 restore 를 h 의 별칭으로 받되 h 가 우선이다", () => {
    expect(readHistoryQuery({ restore: ID1 })).toEqual({ h: ID1 });
    expect(readHistoryQuery({ h: ID2, restore: ID1 })).toEqual({ h: ID2 });
  });

  it("v1 숫자 id 는 대응표로 새 id 를 찾고 못 찾으면 버린다", () => {
    expect(readHistoryQuery({ restore: "1727000000000" }, { "1727000000000": ID1 })).toEqual({ h: ID1 });
    expect(readHistoryQuery({ restore: "1727000000000", q: "경제" }, {})).toEqual({ q: "경제" });
  });

  it("형식이 틀린 id·빈 값은 버리고 배열은 첫 값을 쓴다", () => {
    expect(readHistoryQuery({ h: "../../admin", q: "   " })).toEqual({});
    expect(readHistoryQuery({ h: [ID1, ID2], q: ["a", "b"] })).toEqual({ h: ID1, q: "a" });
  });

  it("대문자 id 는 소문자로 맞춘다", () => {
    expect(readHistoryQuery({ h: MIXED })).toEqual({ h: MIXED.toLowerCase() });
  });
});

describe("awaitsV1Map", () => {
  it("h·restore 의 옛 숫자 id 가 대응표에 없을 때만 대응표를 기다린다", () => {
    expect(awaitsV1Map({ restore: "1727000000000" })).toBe(true);
    expect(awaitsV1Map({ h: "1727000000000", q: "경제" }, {})).toBe(true);
    expect(awaitsV1Map({ restore: "1727000000000" }, { "1727000000000": ID1 })).toBe(false);
  });

  it("새 id·형식이 틀린 값·빈 주소는 기다리지 않고, h 가 새 id 면 restore 는 보지 않는다", () => {
    expect(awaitsV1Map({ restore: ID1 })).toBe(false);
    expect(awaitsV1Map({ h: ID2, restore: "1727000000000" })).toBe(false);
    expect(awaitsV1Map({ restore: "12ab" })).toBe(false);
    expect(awaitsV1Map({ q: "경제" })).toBe(false);
    expect(awaitsV1Map({})).toBe(false);
  });
});

describe("activeKindForPath", () => {
  it("경로로 사이드바 탭을 정한다", () => {
    expect(activeKindForPath("/")).toBe("book");
    expect(activeKindForPath("/books/CNTS-1")).toBe("book");
    expect(activeKindForPath("/recommend/3")).toBe("book");
    expect(activeKindForPath("/papers")).toBe("paper");
    expect(activeKindForPath("/papers/CNTS-2")).toBe("paper");
    expect(activeKindForPath(`/research/${ID1}`)).toBe("research");
    expect(activeKindForPath("/papersX")).toBe("book");
  });

  it("보고서에서 온 상세는 딥리서치 탭, 검색에서 온 상세는 논문 탭이다 — 잡 id 모양이 틀리면 논문 탭", () => {
    expect(activeKindForPath("/papers/CNTS-2", { from: "research", job: ID1, e: "E3" })).toBe("research");
    expect(activeKindForPath("/papers/CNTS-2", { from: "search", h: ID2, q: "nlp" })).toBe("paper");
    expect(activeKindForPath("/papers/CNTS-2", { from: "research", job: "../admin" })).toBe("paper");
    expect(activeKindForPath("/papers", { from: "research", job: ID1 })).toBe("paper");
  });
});

describe("activeIdFor", () => {
  it("딥리서치는 경로의 잡 id, 나머지는 쿼리의 h", () => {
    expect(activeIdFor(`/research/${ID1}`, {})).toBe(ID1);
    expect(activeIdFor("/papers/CNTS-2", { h: ID2 })).toBe(ID2);
    expect(activeIdFor("/", {})).toBeNull();
  });

  it("상세는 출처의 잡·기록을 강조한다 — 잡 id 는 소문자로 맞추고 모양이 틀리면 버린다", () => {
    expect(activeIdFor("/papers/CNTS-2", { from: "research", job: ID1, e: "E3" })).toBe(ID1);
    expect(activeIdFor("/papers/CNTS-2", { from: "research", job: MIXED })).toBe(MIXED.toLowerCase());
    expect(activeIdFor("/papers/CNTS-2", { from: "search", h: ID2, q: "nlp" })).toBe(ID2);
    expect(activeIdFor("/papers/CNTS-2", { from: "search", q: "nlp" })).toBeNull();
    expect(activeIdFor("/papers/CNTS-2", { from: "research", job: "nope" })).toBeNull();
  });
});
