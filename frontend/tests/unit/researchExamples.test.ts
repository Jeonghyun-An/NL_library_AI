// frontend/tests/unit/researchExamples.test.ts
import { describe, expect, it } from "vitest";
import { EXAMPLE_CARD_MAX, exampleMeta, exampleRoute, pickExamples, type WorkListItem } from "~/utils/researchExamples";
import { scopeLine } from "~/utils/workPhase";
import { ID1, ID2, ID3 } from "./helpers/fakeHistory";

const ID4 = "44444444-4444-4444-8444-444444444444";

function item(id: string, over: Partial<WorkListItem> = {}): WorkListItem {
  return { id, question: "공공도서관 서비스 품질 평가 연구가 궁금해", phase: "done", created_at: "2026-10-06T00:30:00Z", ...over };
}

describe("pickExamples", () => {
  it("메인 입력창 아래에는 받은 순서(최근 것부터)로 세 개까지만", () => {
    expect(EXAMPLE_CARD_MAX).toBe(3);
    expect(pickExamples([item(ID1), item(ID2), item(ID3), item(ID4)]).map((x) => x.id)).toEqual([ID1, ID2, ID3]);
    expect(pickExamples([item(ID1)]).map((x) => x.id)).toEqual([ID1]);
    expect(pickExamples([])).toEqual([]);
  });
});

describe("exampleMeta", () => {
  it("실행 시각은 corpus.at 의 KST, 범위는 범위 띠와 같은 scopeLine", () => {
    const corpus = { n_papers: 144748, from: "1980", to: "2017", at: "2026-10-06T00:30:00Z" };
    expect(exampleMeta(corpus)).toEqual({ ranAt: "2026년 10월 6일 09:30 실행", scope: scopeLine(corpus) });
  });

  it("코퍼스가 없거나 at 이 날짜가 아니면 그 칸은 null", () => {
    expect(exampleMeta(null)).toEqual({ ranAt: null, scope: null });
    expect(exampleMeta(undefined)).toEqual({ ranAt: null, scope: null });
    const noAt = { n_papers: 900, from: null, to: "2017", at: null };
    expect(exampleMeta(noAt)).toEqual({ ranAt: null, scope: scopeLine(noAt) });
    expect(exampleMeta({ n_papers: 900, from: null, to: null, at: "어제" }).ranAt).toBeNull();
    // 범위를 모르는(편수 0) 코퍼스도 실행 시각은 보인다
    expect(exampleMeta({ n_papers: 0, from: null, to: null, at: "2026-10-06T00:30:00Z" })).toEqual({
      ranAt: "2026년 10월 6일 09:30 실행",
      scope: null,
    });
  });
});

describe("exampleRoute", () => {
  it("예시 연구는 도달한 단계 화면으로 연다 — 사이드바의 이어간 연구 줄(historyRoute.routeFor)과 같은 규칙", () => {
    expect(exampleRoute({ id: ID1, phase: "reading" })).toEqual({ path: `/research/${ID1}`, query: { s: "reading" } });
    expect(exampleRoute({ id: ID2, phase: "done" })).toEqual({ path: `/research/${ID2}`, query: { s: "proposal" } });
    expect(exampleRoute({ id: ID3, phase: "topics" })).toEqual({ path: `/research/${ID3}`, query: { s: "topics" } });
  });
});
