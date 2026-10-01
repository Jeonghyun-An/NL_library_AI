// frontend/tests/unit/historyState.test.ts
import { describe, expect, it, vi } from "vitest";
import type { HistoryEntry, HistoryKind } from "~/types/history";
import { createHistoryState } from "~/utils/historyState";
import { createHybridStore, createLocalStore, type HybridHistoryStore } from "~/utils/historyStore";
import { ID1, ID2, ID3, bookEntry, fakeServer, httpError, paperEntry, researchEntry } from "./helpers/fakeHistory";
import { MemoryStorage } from "./helpers/memoryStorage";

const NOW = Date.parse("2026-09-26T03:00:00.000Z");
const minutesAgo = (m: number) => new Date(NOW - m * 60_000).toISOString();
const snap = { query: "한국 경제", books: [] };

function setup() {
  const store = fakeServer();
  const ids = [ID1, ID2, ID3];
  let changes = 0;
  const state = createHistoryState(() => store, {
    now: () => NOW,
    genId: () => ids.shift()!,
    onChange: () => {
      changes += 1;
    },
    warn: () => {},
  });
  return { store, state, changes: () => changes };
}

/** 다음 목록 요청을 요청 시점의 서버 상태로 답하되, 풀어 줄 때까지 응답을 붙잡아 둔다 — 느린 네트워크 */
function holdNextList(server: ReturnType<typeof fakeServer>): () => void {
  let release!: () => void;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  server.list.mockImplementationOnce(async (kind?: HistoryKind) => {
    const items = [...server.rows.values()].filter((e) => !kind || e.kind === kind);
    await released;
    return { items, nextCursor: null };
  });
  return release;
}

/** 다음 저장 요청을 풀어 줄 때까지 붙잡았다가 서버에 쓴다 — 스냅샷이 커서 오래 걸리는 저장 */
function holdNextPut(server: ReturnType<typeof fakeServer>): () => void {
  let release!: () => void;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  server.put.mockImplementationOnce(async (entry: HistoryEntry) => {
    await released;
    server.rows.set(entry.id, entry);
    return entry;
  });
  return release;
}

/** 앱과 같은 하이브리드 저장소 위의 상태 — 이 탭의 동작이 부른 순서대로 서버에 닿는다 */
function setupHybrid() {
  const server = fakeServer();
  const hybrid: HybridHistoryStore = createHybridStore(server, createLocalStore(new MemoryStorage()));
  const ids = [ID1, ID2, ID3];
  const state = createHistoryState(() => hybrid, { now: () => NOW, genId: () => ids.shift()!, warn: () => {} });
  return { server, state };
}

describe("createHistoryState", () => {
  it("refresh 는 종류별 목록을 채우고 무거운 필드는 목록에 두지 않는다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, bookEntry(ID1, { snapshot: snap }));
    store.rows.set(ID2, researchEntry(ID2, { research: { status: "running", stage: "planned" } }));
    await state.refresh();
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID1]);
    expect(state.byKind("book").value[0]).not.toHaveProperty("snapshot");
    expect(state.byKind("research").value[0]).toMatchObject({ research: { status: "running" } });
  });

  it("add 는 새 id 로 맨 위에 넣고 서버에 저장한다", async () => {
    const { store, state, changes } = setup();
    store.rows.set(ID3, bookEntry(ID3, { title: "다른 검색", createdAt: minutesAgo(1) }));
    await state.refresh();
    const saved = await state.add({ kind: "book", title: "한국 경제", params: {}, snapshot: snap });
    expect(saved.id).toBe(ID1);
    expect(store.rows.get(ID1)).toMatchObject({
      title: "한국 경제",
      snapshot: snap,
      createdAt: new Date(NOW).toISOString(),
    });
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID1, ID3]);
    expect(changes()).toBe(1);
  });

  it("10분 안의 같은 검색은 새로 만들지 않고 기존 기록을 갱신해 맨 위로 올린다", async () => {
    const { store, state } = setup();
    store.rows.set(ID2, paperEntry(ID2, { title: "다른 것", createdAt: minutesAgo(1) }));
    store.rows.set(ID3, paperEntry(ID3, { title: "딥러닝", createdAt: minutesAgo(5) }));
    await state.refresh();
    expect(state.byKind("paper").value.map((e) => e.id)).toEqual([ID2, ID3]);
    const saved = await state.add({ kind: "paper", title: " 딥러닝 ", params: {}, snapshot: { query: "딥러닝", books: [] } });
    expect(saved.id).toBe(ID3);
    expect(store.put).toHaveBeenCalledWith(
      expect.objectContaining({ id: ID3, createdAt: minutesAgo(5), updatedAt: new Date(NOW).toISOString() }),
    );
    expect(state.byKind("paper").value.map((e) => e.id)).toEqual([ID3, ID2]);
  });

  it("10분이 지난 같은 검색은 새 기록이다", async () => {
    const { store, state } = setup();
    store.rows.set(ID3, bookEntry(ID3, { createdAt: minutesAgo(11) }));
    await state.refresh();
    expect((await state.add({ kind: "book", title: "한국 경제", params: {} })).id).toBe(ID1);
  });

  it("서버가 거절하면 목록에서 빼되 던지지 않고 항목을 돌려준다", async () => {
    const { store, state } = setup();
    store.put.mockRejectedValueOnce(httpError(422));
    const entry = await state.add({ kind: "book", title: "한국 경제", params: {} });
    expect(entry.id).toBe(ID1);
    expect(state.entries.value).toEqual([]);
  });

  it("저장소가 결과를 덜고 저장하면 저장된 항목을 돌려주고 목록에 올린다", async () => {
    const { store, state } = setup();
    // 축약 결과가 커서 413 이면 하이브리드 저장소가 결과 없이 다시 보내 이렇게 돌려준다
    store.put.mockImplementationOnce(async (entry) => {
      const lighter = bookEntry(entry.id, { title: entry.title, createdAt: entry.createdAt, updatedAt: entry.updatedAt });
      store.rows.set(lighter.id, lighter);
      return lighter;
    });
    const saved = await state.add({ kind: "book", title: "한국 경제", params: {}, snapshot: snap });
    expect(saved).toMatchObject({ id: ID1, title: "한국 경제" });
    expect(saved).not.toHaveProperty("snapshot");
    expect(store.put).toHaveBeenCalledTimes(1);
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID1]);
  });

  it("patch 대상이 사라졌으면 목록에서 정리한다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, bookEntry(ID1));
    await state.refresh();
    store.rows.delete(ID1);
    expect(await state.patch(ID1, { ai: { intro: "", items: [] } })).toBeNull();
    expect(state.entries.value).toEqual([]);
  });

  it("remove·clear 는 목록에서 먼저 빼고 서버에 알린다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, bookEntry(ID1));
    store.rows.set(ID2, paperEntry(ID2));
    store.rows.set(ID3, paperEntry(ID3, { title: "다른 논문" }));
    await state.refresh();
    await state.remove(ID1);
    expect(store.remove).toHaveBeenCalledWith(ID1);
    await state.clear("paper");
    expect(store.clear).toHaveBeenCalledWith("paper");
    expect(state.entries.value).toEqual([]);
  });

  it("목록을 읽는 사이 지운 기록은 늦게 도착한 목록이 되살리지 않는다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, bookEntry(ID1));
    store.rows.set(ID2, bookEntry(ID2, { title: "다른 검색" }));
    await state.refresh();
    const release = holdNextList(store);
    const refreshing = state.refresh("book");
    await state.remove(ID1);
    release();
    await refreshing;
    expect(store.rows.has(ID1)).toBe(false);
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID2]);
  });

  it("목록을 읽는 사이 비운 종류는 늦게 도착한 목록이 다시 채우지 않는다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, paperEntry(ID1));
    store.rows.set(ID2, paperEntry(ID2, { title: "다른 논문" }));
    store.rows.set(ID3, bookEntry(ID3));
    await state.refresh();
    const release = holdNextList(store);
    const refreshing = state.refresh("paper");
    await state.clear("paper");
    release();
    await refreshing;
    expect(state.byKind("paper").value).toEqual([]);
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID3]);
  });

  it("하이브리드 저장소에서 목록을 읽는 사이 지워도 기록이 되살아나지 않는다", async () => {
    const server = fakeServer();
    const hybrid: HybridHistoryStore = createHybridStore(server, createLocalStore(new MemoryStorage()));
    const state = createHistoryState(() => hybrid, { now: () => NOW, genId: () => ID3, warn: () => {} });
    server.rows.set(ID1, bookEntry(ID1));
    await state.refresh();
    const release = holdNextList(server);
    const refreshing = state.refresh("book");
    // 하이브리드의 삭제는 먼저 출발한 목록 요청이 끝나기를 기다린다
    const removing = state.remove(ID1);
    release();
    await Promise.all([refreshing, removing]);
    expect(server.rows.has(ID1)).toBe(false);
    expect(state.entries.value).toEqual([]);
  });

  it("지운 뒤에 출발한 목록은 그대로 반영한다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, bookEntry(ID1));
    await state.refresh();
    await state.remove(ID1);
    // 다른 탭이 같은 기록을 다시 저장했다
    store.rows.set(ID1, bookEntry(ID1));
    await state.refresh("book");
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID1]);
  });

  it("저장하는 사이 지운 기록은 늦게 도착한 저장 응답이 되살리지 않는다", async () => {
    const { server, state } = setupHybrid();
    const release = holdNextPut(server);
    const adding = state.add({ kind: "book", title: "한국 경제", params: {}, snapshot: snap });
    // 사이드바는 낙관적으로 올라간 기록을 저장이 끝나기 전에 지울 수 있다
    const removing = state.remove(ID1);
    release();
    await Promise.all([adding, removing]);
    expect(server.rows.has(ID1)).toBe(false);
    expect(state.entries.value).toEqual([]);
  });

  it("저장하는 사이 비운 종류는 늦게 도착한 저장 응답이 다시 채우지 않는다", async () => {
    const { server, state } = setupHybrid();
    server.rows.set(ID3, paperEntry(ID3));
    await state.refresh();
    const release = holdNextPut(server);
    const adding = state.add({ kind: "book", title: "한국 경제", params: {}, snapshot: snap });
    const clearing = state.clear("book");
    release();
    await Promise.all([adding, clearing]);
    expect([...server.rows.values()].filter((e) => e.kind === "book")).toEqual([]);
    expect(state.byKind("book").value).toEqual([]);
    expect(state.byKind("paper").value.map((e) => e.id)).toEqual([ID3]);
  });

  it("목록 읽기가 저장보다 먼저 끝나도 저장하는 사이 지운 기록은 되살아나지 않는다", async () => {
    const { server, state } = setupHybrid();
    const releaseList = holdNextList(server);
    const releasePut = holdNextPut(server);
    const refreshing = state.refresh("book");
    const adding = state.add({ kind: "book", title: "한국 경제", params: {} });
    const removing = state.remove(ID1);
    // 읽는 중인 목록은 없어졌지만 저장 응답은 아직 오지 않았다 — 지운 순번을 이때 버리면 안 된다
    releaseList();
    await refreshing;
    releasePut();
    await Promise.all([adding, removing]);
    expect(server.rows.has(ID1)).toBe(false);
    expect(state.entries.value).toEqual([]);
  });

  it("저장하는 사이 지운 것은 그 기록뿐이면 다른 기록의 저장 응답은 그대로 올린다", async () => {
    const { server, state } = setupHybrid();
    server.rows.set(ID3, bookEntry(ID3, { title: "다른 검색" }));
    await state.refresh();
    const release = holdNextPut(server);
    const adding = state.add({ kind: "book", title: "한국 경제", params: {} });
    const removing = state.remove(ID3);
    release();
    await Promise.all([adding, removing]);
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID1]);
  });

  it("upsertResearch 는 이미 목록에 있으면 서버에 묻지 않는다", async () => {
    const { store, state } = setup();
    store.rows.set(ID2, researchEntry(ID2));
    await state.refresh();
    store.get.mockClear();
    store.put.mockClear();
    expect(await state.upsertResearch(ID2, "질문")).toMatchObject({ id: ID2 });
    expect(store.get).not.toHaveBeenCalled();
    expect(store.put).not.toHaveBeenCalled();
  });

  it("upsertResearch 는 없으면 잡 id 로 딥리서치 기록을 만든다", async () => {
    const { state } = setup();
    const saved = await state.upsertResearch(ID2, "  국내 AI 규제 연구 동향  ");
    expect(saved).toMatchObject({ id: ID2, kind: "research", refId: ID2, title: "국내 AI 규제 연구 동향" });
    expect(state.byKind("research").value.map((e) => e.id)).toEqual([ID2]);
  });

  it("upsertResearch 는 남의 잡이라 거절되면 null 을 돌려준다", async () => {
    const { store, state } = setup();
    store.put.mockRejectedValueOnce(httpError(404));
    expect(await state.upsertResearch(ID2, "질문")).toBeNull();
    expect(state.entries.value).toEqual([]);
  });

  it("upsertResearch 가 만드는 사이 딥리서치 기록을 비우면 늦게 도착한 저장 응답이 다시 채우지 않는다", async () => {
    const { server, state } = setupHybrid();
    const release = holdNextPut(server);
    const upserting = state.upsertResearch(ID2, "국내 AI 규제 연구 동향");
    // 조회가 끝나 저장 요청이 나간 뒤에 비운다
    await vi.waitFor(() => expect(server.put).toHaveBeenCalled());
    const clearing = state.clear("research");
    release();
    await Promise.all([upserting, clearing]);
    expect(server.rows.has(ID2)).toBe(false);
    expect(state.byKind("research").value).toEqual([]);
  });

  it("upsertResearch 가 서버의 기록을 읽는 사이 딥리서치 기록을 비우면 읽은 기록을 목록에 올리지 않는다", async () => {
    const { server, state } = setupHybrid();
    // 다른 탭이 만든 기록 — 이 탭의 목록에는 아직 없다
    server.rows.set(ID2, researchEntry(ID2));
    let release!: () => void;
    const released = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.get.mockImplementationOnce(async (id: string) => {
      const found = server.rows.get(id) ?? null;
      await released;
      return found;
    });
    const upserting = state.upsertResearch(ID2, "질문");
    const clearing = state.clear("research");
    release();
    await Promise.all([upserting, clearing]);
    expect(server.rows.has(ID2)).toBe(false);
    expect(state.byKind("research").value).toEqual([]);
  });
});
