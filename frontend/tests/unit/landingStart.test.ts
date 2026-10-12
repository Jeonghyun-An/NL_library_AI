// frontend/tests/unit/landingStart.test.ts
import { describe, expect, it } from "vitest";
import { parseQuery } from "vue-router";
import { START_DEEP_RESEARCH, deepResearchStartRoute, queryWithoutStart, readStart } from "~/utils/landingStart";

describe("deepResearchStartRoute — 사이드바 [+ 연구 시작하기]", () => {
  it("랜딩('/')에 ?start=deep-research 를 싣는다", () => {
    expect(deepResearchStartRoute()).toEqual({ path: "/", query: { start: START_DEEP_RESEARCH } });
    expect(START_DEEP_RESEARCH).toBe("deep-research");
  });
});

describe("readStart", () => {
  it("deep-research 만 시작 요청으로 읽는다", () => {
    expect(readStart({ start: "deep-research" })).toBe("deep-research");
    expect(readStart({ start: " deep-research " })).toBe("deep-research");
  });

  it("라우터가 같은 키를 배열로 풀어도 첫 값을 읽는다", () => {
    expect(readStart(parseQuery("start=deep-research&start=x"))).toBe("deep-research");
  });

  it("없거나 모르는 값이면 null", () => {
    expect(readStart({})).toBeNull();
    expect(readStart({ start: "" })).toBeNull();
    expect(readStart({ start: "something" })).toBeNull();
    expect(readStart({ start: null })).toBeNull();
  });
});

describe("queryWithoutStart — 처리한 뒤 주소에서 start 만 지운다", () => {
  it("다른 쿼리는 그대로 둔다", () => {
    expect(queryWithoutStart({ start: "deep-research", q: "논문", h: "abc" })).toEqual({ q: "논문", h: "abc" });
  });

  it("start 가 없으면 같은 내용을 준다", () => {
    expect(queryWithoutStart({ q: "논문" })).toEqual({ q: "논문" });
    expect(queryWithoutStart({})).toEqual({});
  });
});
