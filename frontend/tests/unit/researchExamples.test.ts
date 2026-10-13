// frontend/tests/unit/researchExamples.test.ts
import { describe, expect, it } from "vitest";
import {
  EXAMPLE_CARD_MAX,
  exampleMeta,
  exampleRoute,
  gatherExamples,
  pickExamples,
  type WorkListItem,
} from "~/utils/researchExamples";
import type { Corpus } from "~/types/work";
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

// 손으로 푸는 약속 — 범위 응답이 늦게 오는 예시를 흉내 낸다
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const flush = () => new Promise<void>((r) => setTimeout(r, 0));

describe("gatherExamples", () => {
  const corpusA: Corpus = { n_papers: 144748, from: "1980", to: "2017", at: "2026-10-06T00:30:00Z" };
  const corpusB: Corpus = { n_papers: 900, from: null, to: "2017", at: null };

  it("목록과 예시마다의 범위를 모두 받은 뒤에 한 번에 돌려준다 — 랜딩은 세로 가운데 정렬이라 카드가 선 뒤 메타 줄이 따로 붙으면 입력창이 한 번 더 밀린다", async () => {
    const slow = deferred<Corpus | null>();
    const asked: string[] = [];
    const corpora: Record<string, Promise<Corpus | null>> = {
      [ID1]: Promise.resolve(corpusA),
      [ID2]: slow.promise,
      [ID3]: Promise.resolve(corpusB),
    };
    let done = false;
    const got = gatherExamples(
      async () => ({ items: [item(ID1), item(ID2), item(ID3), item(ID4)] }),
      (id) => {
        asked.push(id);
        return corpora[id] ?? Promise.reject(new Error(`모르는 예시 ${id}`));
      },
    ).then((v) => {
      done = true;
      return v;
    });
    await flush();
    // 범위 셋을 함께 묻고(넷째는 카드가 아니라 묻지 않는다), 하나라도 남아 있으면 아직 돌려주지 않는다
    expect(asked).toEqual([ID1, ID2, ID3]);
    expect(done).toBe(false);
    slow.resolve(null);
    const { examples, metas } = await got;
    expect(examples.map((x) => x.id)).toEqual([ID1, ID2, ID3]);
    expect(metas).toEqual({
      [ID1]: exampleMeta(corpusA),
      [ID2]: exampleMeta(null),
      [ID3]: exampleMeta(corpusB),
    });
  });

  it("범위를 못 읽은 예시는 그 카드의 메타만 빠지고(질문은 선다) 나머지는 그대로 — 실패도 다 끝난 뒤에 함께", async () => {
    const failing = deferred<Corpus | null>();
    let done = false;
    const got = gatherExamples(
      async () => ({ items: [item(ID1), item(ID2)] }),
      (id) => (id === ID1 ? failing.promise : Promise.resolve(corpusA)),
    ).then((v) => {
      done = true;
      return v;
    });
    await flush();
    expect(done).toBe(false);
    failing.reject(new Error("502"));
    const { examples, metas } = await got;
    expect(examples.map((x) => x.id)).toEqual([ID1, ID2]);
    expect(metas).toEqual({ [ID2]: exampleMeta(corpusA) });
  });

  it("목록을 못 읽으면 거절한다(부르는 쪽이 null 로 두어 다음에 다시 읽는다) — 범위는 묻지 않는다. 예시가 없으면 빈 목록·빈 메타", async () => {
    const asked: string[] = [];
    const corpusOf = (id: string) => {
      asked.push(id);
      return Promise.resolve(corpusA);
    };
    await expect(gatherExamples(() => Promise.reject(new Error("503")), corpusOf)).rejects.toThrow("503");
    expect(asked).toEqual([]);
    await expect(gatherExamples(async () => ({ items: [] }), corpusOf)).resolves.toEqual({ examples: [], metas: {} });
    expect(asked).toEqual([]);
  });
});
