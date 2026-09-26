import { describe, expect, it } from "vitest";
import type { HistoryItemDetail } from "~/types/history";
import {
  HISTORY_CACHE_KEY,
  HISTORY_OUTBOX_KEY,
  createHybridStore,
  createLocalStore,
  createServerStore,
  errorStatus,
  fromWire,
  isQuotaError,
  isRetryable,
  toWire,
  type HistoryFetchOptions,
  type HistoryFetcher,
} from "~/utils/historyStore";
import { MemoryStorage } from "./helpers/memoryStorage";
import {
  ID1,
  ID2,
  ID3,
  bookEntry,
  fakeServer,
  httpError,
  networkError,
  paperEntry,
  researchEntry,
} from "./helpers/fakeHistory";

const snap = { query: "한국 경제", books: [{ book_id: "B1", best_score: 0.9, chunks: [] as never[] }] };

function wire(over: Partial<HistoryItemDetail> = {}): HistoryItemDetail {
  return {
    id: ID1,
    kind: "book",
    title: "한국 경제",
    params: {},
    ref_id: null,
    created_at: "2026-09-26T01:00:00+00:00",
    updated_at: "2026-09-26T01:00:00+00:00",
    has_snapshot: false,
    has_ai: false,
    research: null,
    snapshot: null,
    ai: null,
    ...over,
  };
}

function fakeFetcher(respond: (path: string, opts?: HistoryFetchOptions) => unknown) {
  const calls: Array<{ path: string; opts?: HistoryFetchOptions }> = [];
  const fetcher: HistoryFetcher = async <T,>(path: string, opts?: HistoryFetchOptions) => {
    calls.push({ path, opts });
    return (await respond(path, opts)) as T;
  };
  return { fetcher, calls };
}

describe("오류 분류", () => {
  it("errorStatus 는 status·statusCode·response.status 를 읽는다", () => {
    expect(errorStatus(httpError(404))).toBe(404);
    expect(errorStatus({ statusCode: 503 })).toBe(503);
    expect(errorStatus({ response: { status: 500 } })).toBe(500);
    expect(errorStatus(networkError())).toBeNull();
  });

  it("네트워크·408·429·5xx 만 다시 보낸다", () => {
    expect(isRetryable(networkError())).toBe(true);
    expect(isRetryable(httpError(503))).toBe(true);
    expect(isRetryable(httpError(429))).toBe(true);
    expect(isRetryable(httpError(404))).toBe(false);
    expect(isRetryable(httpError(413))).toBe(false);
  });

  it("쿼터 초과만 쿼터 오류로 본다", () => {
    expect(isQuotaError(new DOMException("x", "QuotaExceededError"))).toBe(true);
    expect(isQuotaError(new DOMException("x", "SecurityError"))).toBe(false);
    expect(isQuotaError(new Error("QuotaExceededError"))).toBe(false);
  });
});

describe("선 모양 변환", () => {
  it("fromWire 는 종류별 필드를 옮긴다", () => {
    expect(fromWire(wire({ snapshot: snap, ai: { intro: "소개", items: [] } }))).toEqual({
      id: ID1,
      kind: "book",
      title: "한국 경제",
      params: {},
      createdAt: "2026-09-26T01:00:00+00:00",
      updatedAt: "2026-09-26T01:00:00+00:00",
      snapshot: snap,
      ai: { intro: "소개", items: [] },
    });
    expect(
      fromWire(wire({ id: ID2, kind: "research", ref_id: ID2, research: { status: "running", stage: "planned" } })),
    ).toMatchObject({ kind: "research", refId: ID2, research: { status: "running", stage: "planned" } });
  });

  it("toWire 는 딥리서치에 ref_id 를 싣고 snapshot·ai 는 비운다", () => {
    expect(toWire(researchEntry(ID3))).toEqual({
      kind: "research",
      title: "국내 AI 규제 연구 동향",
      params: {},
      snapshot: null,
      ai: null,
      ref_id: ID3,
    });
    expect(toWire(bookEntry(ID1, { snapshot: snap }))).toMatchObject({
      kind: "book",
      snapshot: snap,
      ai: null,
      ref_id: null,
    });
  });
});

describe("createServerStore", () => {
  it("list 는 kind·limit·before 를 쿼리로 보내고 항목을 바꿔 돌려준다", async () => {
    const { fetcher, calls } = fakeFetcher(() => ({ items: [wire()], next_cursor: "c1" }));
    const res = await createServerStore(fetcher).list("book", { limit: 10, before: "c0" });
    expect(calls[0]).toMatchObject({
      path: "/history",
      opts: { method: "GET", query: { kind: "book", limit: 10, before: "c0" } },
    });
    expect(res.nextCursor).toBe("c1");
    expect(res.items[0]).toMatchObject({ id: ID1, kind: "book" });
  });

  it("get 은 404 면 null, 다른 오류는 그대로 던진다", async () => {
    const notFound = fakeFetcher(() => {
      throw httpError(404);
    });
    expect(await createServerStore(notFound.fetcher).get(ID1)).toBeNull();
    const broken = fakeFetcher(() => {
      throw httpError(500);
    });
    await expect(createServerStore(broken.fetcher).get(ID1)).rejects.toMatchObject({ status: 500 });
  });

  it("put 은 PUT 본문에 선 모양을 싣는다", async () => {
    const { fetcher, calls } = fakeFetcher(() => wire({ snapshot: snap }));
    const saved = await createServerStore(fetcher).put(bookEntry(ID1, { snapshot: snap }));
    expect(calls[0]).toMatchObject({
      path: `/history/${ID1}`,
      opts: { method: "PUT", body: { kind: "book", title: "한국 경제", snapshot: snap } },
    });
    expect(saved).toMatchObject({ id: ID1, snapshot: snap });
  });

  it("patch 는 정의된 필드만 보내고 404 면 null", async () => {
    const { fetcher, calls } = fakeFetcher(() => {
      throw httpError(404);
    });
    const res = await createServerStore(fetcher).patch(ID1, { ai: { text: "요약", refs: [] }, title: undefined });
    expect(res).toBeNull();
    expect(calls[0]!.opts).toMatchObject({ method: "PATCH", body: { ai: { text: "요약", refs: [] } } });
    expect(calls[0]!.opts!.body).not.toHaveProperty("title");
  });

  it("remove 는 404 를 성공으로 본다", async () => {
    const { fetcher } = fakeFetcher(() => {
      throw httpError(404);
    });
    await expect(createServerStore(fetcher).remove(ID1)).resolves.toBeUndefined();
  });

  it("clear 는 kind 를 쿼리로 보낸다", async () => {
    const { fetcher, calls } = fakeFetcher(() => undefined);
    await createServerStore(fetcher).clear("paper");
    expect(calls[0]).toMatchObject({ path: "/history", opts: { method: "DELETE", query: { kind: "paper" } } });
  });

  it("importItems 는 items 를 POST 한다", async () => {
    const { fetcher, calls } = fakeFetcher(() => ({ imported: 1, skipped: 0, id_map: { "1727": ID1 } }));
    const res = await createServerStore(fetcher).importItems([
      { kind: "book", title: "a", params: {}, snapshot: null, ai: null, ref_id: null, legacy_id: "1727" },
    ]);
    expect(calls[0]).toMatchObject({ path: "/history/import", opts: { method: "POST" } });
    expect(res.id_map["1727"]).toBe(ID1);
  });
});

describe("createLocalStore", () => {
  it("종류별로 최신순 목록을 돌려준다", async () => {
    const local = createLocalStore(new MemoryStorage());
    await local.put(bookEntry(ID1, { createdAt: "2026-09-26T01:00:00.000Z" }));
    await local.put(bookEntry(ID2, { createdAt: "2026-09-26T02:00:00.000Z" }));
    await local.put(paperEntry(ID3));
    const { items } = await local.list("book");
    expect(items.map((e) => e.id)).toEqual([ID2, ID1]);
  });

  it("before 커서로 다음 쪽을 읽는다", async () => {
    const local = createLocalStore(new MemoryStorage());
    await local.put(bookEntry(ID1, { createdAt: "2026-09-26T01:00:00.000Z" }));
    await local.put(bookEntry(ID2, { createdAt: "2026-09-26T02:00:00.000Z" }));
    const first = await local.list("book", { limit: 1 });
    expect(first.items.map((e) => e.id)).toEqual([ID2]);
    const second = await local.list("book", { limit: 1, before: first.nextCursor! });
    expect(second.items.map((e) => e.id)).toEqual([ID1]);
    expect(second.nextCursor).toBeNull();
  });

  it("patch·remove·clear 가 캐시에 반영된다", async () => {
    const local = createLocalStore(new MemoryStorage());
    await local.put(bookEntry(ID1));
    await local.put(paperEntry(ID2));
    expect(await local.patch(ID1, { title: "새 제목" })).toMatchObject({ id: ID1, title: "새 제목" });
    expect(await local.patch(ID3, { title: "x" })).toBeNull();
    await local.remove(ID1);
    expect(await local.get(ID1)).toBeNull();
    await local.clear("paper");
    expect((await local.list()).items).toEqual([]);
  });

  it("같은 저장소를 여는 다른 인스턴스(다른 탭)가 같은 내용을 본다", async () => {
    const storage = new MemoryStorage();
    await createLocalStore(storage).put(bookEntry(ID1));
    expect(await createLocalStore(storage).get(ID1)).toMatchObject({ id: ID1 });
  });

  it("저장소가 없으면 메모리로 동작한다", async () => {
    const local = createLocalStore(null);
    await local.put(bookEntry(ID1));
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
  });

  it("쿼터에 걸리면 오래된 snapshot 부터 비우고 목록은 남긴다", async () => {
    const heavy = {
      query: "q",
      books: Array.from({ length: 20 }, (_, i) => ({
        book_id: `B${i}`,
        best_score: 0.5,
        chunks: [] as never[],
        book_info: { title: "제목".repeat(40) },
      })),
    };
    const oneSize = JSON.stringify([bookEntry(ID1, { snapshot: heavy })]).length;
    const storage = new MemoryStorage(Math.floor(oneSize * 1.6));
    const local = createLocalStore(storage);
    await local.put(bookEntry(ID1, { createdAt: "2026-09-26T01:00:00.000Z", snapshot: heavy }));
    await local.put(bookEntry(ID2, { createdAt: "2026-09-26T02:00:00.000Z", snapshot: heavy }));
    const cached = JSON.parse(storage.getItem(HISTORY_CACHE_KEY)!) as Array<{ id: string; snapshot?: unknown }>;
    expect(cached.map((e) => e.id).sort()).toEqual([ID1, ID2].sort());
    expect(cached.find((e) => e.id === ID1)!.snapshot).toBeUndefined();
    expect(cached.find((e) => e.id === ID2)!.snapshot).toEqual(heavy);
  });

  it("쿼터가 아닌 쓰기 오류는 던지지 않고 메모리로 넘어간다", async () => {
    const storage = new MemoryStorage();
    storage.failWith = new DOMException("막힘", "SecurityError");
    const local = createLocalStore(storage);
    await expect(local.put(bookEntry(ID1))).resolves.toMatchObject({ id: ID1 });
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
  });

  it("깨진 JSON 은 빈 목록으로 읽는다", async () => {
    const storage = new MemoryStorage();
    storage.setItem(HISTORY_CACHE_KEY, "{깨짐");
    expect((await createLocalStore(storage).list()).items).toEqual([]);
  });

  it("replaceKind 는 서버 목록으로 갈아 끼우되 캐시에 있던 snapshot 은 붙여 둔다", async () => {
    const local = createLocalStore(new MemoryStorage());
    await local.put(bookEntry(ID1, { snapshot: snap }));
    await local.put(bookEntry(ID2));
    await local.put(paperEntry(ID3));
    local.replaceKind("book", [bookEntry(ID1, { title: "서버 제목" })]);
    expect(await local.get(ID1)).toMatchObject({ title: "서버 제목", snapshot: snap });
    expect(await local.get(ID2)).toBeNull();
    expect(await local.get(ID3)).toMatchObject({ kind: "paper" });
  });

  it("outbox 는 넣은 순서대로 쌓이고 opId 로 뺀다", () => {
    const storage = new MemoryStorage();
    const local = createLocalStore(storage);
    local.enqueue({ op: "remove", id: ID1 });
    local.enqueue({ op: "clear", kind: "book" });
    const ops = local.readOutbox();
    expect(ops.map((o) => o.op)).toEqual(["remove", "clear"]);
    expect(storage.getItem(HISTORY_OUTBOX_KEY)).not.toBeNull();
    local.dropOutbox(ops[0]!.opId);
    expect(local.readOutbox().map((o) => o.op)).toEqual(["clear"]);
  });
});

describe("createHybridStore", () => {
  function setup() {
    const server = fakeServer();
    const local = createLocalStore(new MemoryStorage());
    return { server, local, store: createHybridStore(server, local) };
  }

  it("서버 저장이 되면 캐시에도 남긴다", async () => {
    const { server, local, store } = setup();
    await store.put(bookEntry(ID1, { snapshot: snap }));
    expect(server.rows.has(ID1)).toBe(true);
    expect(await local.get(ID1)).toMatchObject({ snapshot: snap });
    expect(local.readOutbox()).toEqual([]);
  });

  it("서버가 안 되면 브라우저에 먼저 저장하고 보낼 편지함에 넣는다", async () => {
    const { server, local, store } = setup();
    server.fail(networkError());
    const saved = await store.put(bookEntry(ID1));
    expect(saved.id).toBe(ID1);
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
    expect(local.readOutbox()).toMatchObject([{ op: "put", entry: { id: ID1 } }]);
  });

  it("다음 목록 읽기에서 편지함을 먼저 보내고 서버 목록을 쓴다", async () => {
    const { server, local, store } = setup();
    server.fail(httpError(503));
    await store.put(bookEntry(ID1));
    server.recover();
    const { items } = await store.list("book");
    expect(server.rows.has(ID1)).toBe(true);
    expect(items.map((e) => e.id)).toEqual([ID1]);
    expect(local.readOutbox()).toEqual([]);
  });

  it("편지함이 남아 있으면 목록은 캐시로 답한다", async () => {
    const { server, store } = setup();
    server.fail(networkError());
    await store.put(bookEntry(ID1));
    const { items } = await store.list("book");
    expect(items.map((e) => e.id)).toEqual([ID1]);
    expect(server.list).not.toHaveBeenCalled();
  });

  it("4xx 거절은 편지함에 넣지 않고 그대로 던진다", async () => {
    const { server, local, store } = setup();
    server.fail(httpError(422));
    await expect(store.put(bookEntry(ID1))).rejects.toMatchObject({ status: 422 });
    expect(local.readOutbox()).toEqual([]);
  });

  it("보낼 때 4xx 로 거절된 편지는 버리고 다음 편지를 보낸다", async () => {
    const { server, local, store } = setup();
    local.enqueue({ op: "patch", id: ID1, partial: { title: "x" } });
    local.enqueue({ op: "put", entry: bookEntry(ID2) });
    server.patch.mockRejectedValueOnce(httpError(422));
    await store.flush();
    expect(server.rows.has(ID2)).toBe(true);
    expect(local.readOutbox()).toEqual([]);
  });

  it("다시 보낼 만한 실패에서는 멈추고 순서를 지킨다", async () => {
    const { server, local, store } = setup();
    local.enqueue({ op: "put", entry: bookEntry(ID1) });
    local.enqueue({ op: "remove", id: ID1 });
    server.put.mockRejectedValueOnce(networkError());
    await store.flush();
    expect(server.remove).not.toHaveBeenCalled();
    expect(local.readOutbox().map((o) => o.op)).toEqual(["put", "remove"]);
  });

  it("편지함이 남아 있을 때의 수정은 서버로 바로 가지 않고 뒤에 줄 선다", async () => {
    const { server, local, store } = setup();
    server.fail(networkError());
    await store.put(bookEntry(ID1));
    server.recover();
    server.put.mockRejectedValueOnce(networkError());
    await store.patch(ID1, { ai: { intro: "소개", items: [] } });
    expect(server.patch).not.toHaveBeenCalled();
    expect(local.readOutbox().map((o) => o.op)).toEqual(["put", "patch"]);
    expect(await local.get(ID1)).toMatchObject({ ai: { intro: "소개", items: [] } });
  });

  it("서버에 없는 기록은 캐시에서도 지운다", async () => {
    const { local, store } = setup();
    await local.put(bookEntry(ID1));
    expect(await store.get(ID1)).toBeNull();
    expect(await local.get(ID1)).toBeNull();
  });

  it("서버가 안 되면 get 은 캐시로 답한다", async () => {
    const { server, local, store } = setup();
    await local.put(bookEntry(ID1, { snapshot: snap }));
    server.fail(networkError());
    expect(await store.get(ID1)).toMatchObject({ snapshot: snap });
  });

  it("put·patch 가 줄 선 뒤 patch 만 다시 보낼 오류로 실패해도 get 은 최근 수정을 돌려준다", async () => {
    const { server, local, store } = setup();
    const ai = { intro: "소개", items: [] };
    server.fail(networkError());
    await store.put(bookEntry(ID1));
    await store.patch(ID1, { ai });
    expect(local.readOutbox().map((o) => o.op)).toEqual(["put", "patch"]);
    server.recover();
    server.patch.mockRejectedValueOnce(httpError(503));
    expect(await store.get(ID1)).toMatchObject({ ai });
    expect(server.rows.has(ID1)).toBe(true);
    expect(local.readOutbox().map((o) => o.op)).toEqual(["patch"]);
    // 남은 편지까지 다 보낸 뒤에도 오프라인 복원용 캐시에 수정이 남아 있어야 한다
    await store.flush();
    expect(local.readOutbox()).toEqual([]);
    expect(server.rows.get(ID1)).toMatchObject({ ai });
    expect(await local.get(ID1)).toMatchObject({ ai });
  });

  it("put·remove 가 줄 선 뒤 remove 만 다시 보낼 오류로 실패해도 지운 기록이 목록에 되살아나지 않는다", async () => {
    const { server, local, store } = setup();
    server.fail(networkError());
    await store.put(bookEntry(ID1));
    await store.remove(ID1);
    expect(local.readOutbox().map((o) => o.op)).toEqual(["put", "remove"]);
    server.recover();
    server.remove.mockRejectedValueOnce(httpError(429));
    expect((await store.list("book")).items).toEqual([]);
    expect(server.list).not.toHaveBeenCalled();
    expect(local.readOutbox().map((o) => o.op)).toEqual(["remove"]);
    expect(await local.get(ID1)).toBeNull();
  });

  it("바로 보낸 put 이 413 이면 결과 없이 다시 보내 서버·캐시에 남긴다", async () => {
    const { server, local, store } = setup();
    server.put.mockRejectedValueOnce(httpError(413));
    const saved = await store.put(bookEntry(ID1, { snapshot: snap }));
    expect(saved).toMatchObject({ id: ID1 });
    expect(saved).not.toHaveProperty("snapshot");
    expect(server.rows.get(ID1)).not.toHaveProperty("snapshot");
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
    expect(local.readOutbox()).toEqual([]);
  });

  it("줄 선 put 이 보낼 때 413 이면 결과 없이라도 서버·캐시에 남는다", async () => {
    const { server, local, store } = setup();
    server.fail(networkError());
    await store.put(bookEntry(ID1, { snapshot: snap }));
    server.recover();
    server.put.mockRejectedValueOnce(httpError(413));
    const { items } = await store.list("book");
    expect(items.map((e) => e.id)).toEqual([ID1]);
    expect(server.rows.get(ID1)).not.toHaveProperty("snapshot");
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
    expect(local.readOutbox()).toEqual([]);
  });

  it("결과가 없는 기록의 413 은 다시 보내지 않고 그대로 던진다", async () => {
    const { server, store } = setup();
    server.put.mockRejectedValueOnce(httpError(413));
    await expect(store.put(bookEntry(ID1))).rejects.toMatchObject({ status: 413 });
    expect(server.put).toHaveBeenCalledTimes(1);
  });

  /** 열어 줄 때까지 요청을 붙잡아 두는 문 — 느린 네트워크를 흉내 낸다 */
  function gate() {
    let open!: () => void;
    const opened = new Promise<void>((resolve) => {
      open = resolve;
    });
    return { opened, open };
  }

  // 붙잡히지 않은 비동기 작업을 끝까지 흘려보낸다
  const idle = () => new Promise((resolve) => setTimeout(resolve, 0));

  function slowPut(server: ReturnType<typeof fakeServer>) {
    const slow = gate();
    server.put.mockImplementationOnce(async (entry) => {
      await slow.opened;
      server.rows.set(entry.id, entry);
      return entry;
    });
    return slow;
  }

  it("put 이 응답을 기다리는 동안 누른 remove 는 put 뒤에 가서 기록이 되살아나지 않는다", async () => {
    const { server, local, store } = setup();
    const slow = slowPut(server);
    const putting = store.put(bookEntry(ID1));
    const removing = store.remove(ID1);
    await idle();
    expect(server.remove).not.toHaveBeenCalled();
    slow.open();
    await Promise.all([putting, removing]);
    expect(server.rows.has(ID1)).toBe(false);
    expect(await local.get(ID1)).toBeNull();
    expect(local.readOutbox()).toEqual([]);
  });

  it("기다리던 put 이 네트워크 오류로 줄 서면 뒤따른 remove 도 그 뒤에 줄 선다", async () => {
    const { server, local, store } = setup();
    const slow = gate();
    server.put.mockImplementationOnce(async () => {
      await slow.opened;
      throw networkError();
    });
    const putting = store.put(bookEntry(ID1));
    const removing = store.remove(ID1);
    await idle();
    server.fail(networkError());
    slow.open();
    await Promise.all([putting, removing]);
    expect(local.readOutbox().map((o) => o.op)).toEqual(["put", "remove"]);
    expect(await local.get(ID1)).toBeNull();
    server.recover();
    await store.flush();
    expect(server.rows.has(ID1)).toBe(false);
    expect(local.readOutbox()).toEqual([]);
  });

  it("put 이 응답을 기다리는 동안 누른 patch 는 put 뒤에 가서 수정이 사라지지 않는다", async () => {
    const { server, local, store } = setup();
    const slow = slowPut(server);
    const putting = store.put(bookEntry(ID1));
    const patching = store.patch(ID1, { title: "새 제목" });
    await idle();
    expect(server.patch).not.toHaveBeenCalled();
    slow.open();
    await putting;
    expect(await patching).toMatchObject({ id: ID1, title: "새 제목" });
    expect(server.rows.get(ID1)).toMatchObject({ title: "새 제목" });
    expect(await local.get(ID1)).toMatchObject({ title: "새 제목" });
  });

  it("put 이 응답을 기다리는 동안 부른 get 은 저장이 끝난 뒤 답한다", async () => {
    const { server, local, store } = setup();
    const slow = slowPut(server);
    const putting = store.put(bookEntry(ID1));
    const getting = store.get(ID1);
    await idle();
    expect(server.get).not.toHaveBeenCalled();
    slow.open();
    await putting;
    expect(await getting).toMatchObject({ id: ID1 });
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
  });

  it("읽기끼리는 서로 기다리지 않는다", async () => {
    const { server, store } = setup();
    const slow = gate();
    server.list.mockImplementationOnce(async () => {
      await slow.opened;
      return { items: [], nextCursor: null };
    });
    const books = store.list("book");
    const papers = store.list("paper");
    await idle();
    expect(server.list).toHaveBeenCalledTimes(2);
    slow.open();
    await Promise.all([books, papers]);
  });
});
