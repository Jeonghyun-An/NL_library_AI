// frontend/tests/unit/curationRequest.test.ts
import { describe, expect, it, vi } from "vitest";
import type { BookAi } from "~/types/history";
import { createCurationRequests, type CurationBody } from "~/utils/curationRequest";
import { ID1, ID2 } from "./helpers/fakeHistory";

const body: CurationBody = {
  query: "한국 경제",
  book_ids: ["b1", "b2"],
  scores: [0.9, 0.8],
  rewritten_query: "한국 경제 성장",
};

const reply = {
  intro: "두 권을 골랐어요",
  items: [
    { book_id: "b1", reason: "성장 이론", extra: "버린다" },
    { book_id: "b2", reason: "통계" },
  ],
};

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

describe("createCurationRequests", () => {
  it("요청에 화면의 중단 신호를 싣지 않고, 응답이 오면 시작 때의 기록 id 로 저장한다 — 화면이 떠나도 결과가 버려지지 않게", async () => {
    const request = vi.fn(async (_b: CurationBody) => reply);
    const save = vi.fn(async (_id: string, _ai: BookAi) => null);
    const requests = createCurationRequests({ request, save });

    const result = await requests.run(ID1, body);

    expect(request).toHaveBeenCalledTimes(1);
    expect(request.mock.calls[0]).toEqual([body]);
    expect(result).toEqual({
      data: reply,
      intro: "두 권을 골랐어요",
      items: [
        { book_id: "b1", reason: "성장 이론" },
        { book_id: "b2", reason: "통계" },
      ],
    });
    await flush();
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith(ID1, {
      intro: "두 권을 골랐어요",
      items: [
        { book_id: "b1", reason: "성장 이론" },
        { book_id: "b2", reason: "통계" },
      ],
    });
  });

  it("같은 기록의 요청이 진행 중이면 새로 부르지 않고 그 요청을 이어받는다 — 떠났다 돌아올 때마다 생성이 쌓이지 않게", async () => {
    const pending = deferred<unknown>();
    const request = vi.fn((_b: CurationBody) => pending.promise);
    const save = vi.fn(async (_id: string, _ai: BookAi) => null);
    const requests = createCurationRequests({ request, save });

    const first = requests.run(ID1, body);
    const second = requests.run(ID1, body);
    const third = requests.run(ID1, body);
    expect(request).toHaveBeenCalledTimes(1);

    pending.resolve(reply);
    const results = await Promise.all([first, second, third]);
    expect(results[0]).not.toBeNull();
    expect(results[1]).toBe(results[0]);
    expect(results[2]).toBe(results[0]);
    await flush();
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("다른 기록의 요청은 따로 부른다", async () => {
    const request = vi.fn(async (_b: CurationBody) => reply);
    const save = vi.fn(async (_id: string, _ai: BookAi) => null);
    const requests = createCurationRequests({ request, save });

    await Promise.all([requests.run(ID1, body), requests.run(ID2, body)]);
    await flush();

    expect(request).toHaveBeenCalledTimes(2);
    expect(save.mock.calls.map((c) => c[0]).sort()).toEqual([ID1, ID2].sort());
  });

  it("저장이 끝날 때까지는 끝난 요청을 이어받는다 — 저장 전에 복원이 기록을 읽어 요약이 비어 보여도 다시 만들지 않게", async () => {
    const saving = deferred<null>();
    const request = vi.fn(async (_b: CurationBody) => reply);
    const save = vi.fn((_id: string, _ai: BookAi) => saving.promise);
    const requests = createCurationRequests({ request, save });

    const first = await requests.run(ID1, body);
    await flush();
    expect(save).toHaveBeenCalledTimes(1);

    const again = await requests.run(ID1, body);
    expect(request).toHaveBeenCalledTimes(1);
    expect(again).toBe(first);

    saving.resolve(null);
    await flush();
    await requests.run(ID1, body);
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("요청이 실패하면 null 을 주고 저장하지 않으며, 다음 호출은 다시 부른다", async () => {
    const request = vi
      .fn<(b: CurationBody) => Promise<unknown>>()
      .mockRejectedValueOnce(new Error("HTTP 502"))
      .mockResolvedValueOnce(reply);
    const save = vi.fn(async (_id: string, _ai: BookAi) => null);
    const requests = createCurationRequests({ request, save });

    expect(await requests.run(ID1, body)).toBeNull();
    await flush();
    expect(save).not.toHaveBeenCalled();

    expect(await requests.run(ID1, body)).not.toBeNull();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("저장이 실패해도 결과는 주고, 다음 호출은 다시 부른다", async () => {
    const request = vi.fn(async (_b: CurationBody) => reply);
    const save = vi.fn(async (_id: string, _ai: BookAi) => {
      throw new Error("저장 실패");
    });
    const requests = createCurationRequests({ request, save });

    expect(await requests.run(ID1, body)).not.toBeNull();
    await flush();
    await requests.run(ID1, body);
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("모양이 어긋난 응답은 빈 요약으로 다룬다", async () => {
    const request = vi.fn(async (_b: CurationBody) => ({ intro: 3, items: "x" }));
    const save = vi.fn(async (_id: string, _ai: BookAi) => null);
    const requests = createCurationRequests({ request, save });

    const result = await requests.run(ID1, body);

    expect(result).toMatchObject({ intro: "", items: [] });
  });
});
