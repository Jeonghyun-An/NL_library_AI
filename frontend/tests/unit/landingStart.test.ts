// frontend/tests/unit/landingStart.test.ts
import { describe, expect, it } from "vitest";
import { parseQuery } from "vue-router";
import { START_DEEP_RESEARCH, deepResearchStartRoute, queryWithoutStart, readStart, readStartDraft } from "~/utils/landingStart";

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

describe("queryWithoutStart — 처리한 뒤 주소에서 start·draft 를 지운다", () => {
  it("다른 쿼리는 그대로 둔다", () => {
    expect(queryWithoutStart({ start: "deep-research", q: "논문", h: "abc" })).toEqual({ q: "논문", h: "abc" });
  });

  it("start 가 없으면 같은 내용을 준다", () => {
    expect(queryWithoutStart({ q: "논문" })).toEqual({ q: "논문" });
    expect(queryWithoutStart({})).toEqual({});
  });

  it("함께 온 질문 초안(draft)도 지운다 — 남기면 새로고침마다 고쳐 쓰던 글을 덮는다", () => {
    expect(queryWithoutStart({ start: "deep-research", draft: "국가 재정 운용", q: "논문" })).toEqual({ q: "논문" });
  });
});

describe("질문 초안(?draft=) — 소장자료 결과의 [DeepResearch로 이어서 조사하기]", () => {
  it("초안을 함께 싣는다 — 줄바꿈·겹친 공백은 한 칸으로", () => {
    expect(deepResearchStartRoute("  조선시대 고전소설을\n 연구한  자료 찾아줘 ")).toEqual({
      path: "/",
      query: { start: START_DEEP_RESEARCH, draft: "조선시대 고전소설을 연구한 자료 찾아줘" },
    });
  });

  it("질문으로 쓸 수 없는 초안(2자 미만·500자 초과·빈 글)은 싣지 않는다", () => {
    expect(deepResearchStartRoute("가")).toEqual(deepResearchStartRoute());
    expect(deepResearchStartRoute("가".repeat(501))).toEqual(deepResearchStartRoute());
    expect(deepResearchStartRoute("   ")).toEqual(deepResearchStartRoute());
  });

  it("readStartDraft 는 같은 규칙으로 읽고, 같은 키가 여럿이면 첫 값", () => {
    expect(readStartDraft({ start: "deep-research", draft: " 국가 재정  운용 " })).toBe("국가 재정 운용");
    expect(readStartDraft(parseQuery("start=deep-research&draft=%EB%85%B8%EC%9D%B8%20%EC%9A%B0%EC%9A%B8&draft=x"))).toBe("노인 우울");
    expect(readStartDraft({ draft: "가" })).toBeNull();
    expect(readStartDraft({})).toBeNull();
  });
});
