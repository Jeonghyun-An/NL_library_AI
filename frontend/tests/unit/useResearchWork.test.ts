// frontend/tests/unit/useResearchWork.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useResearchWork } from "~/composables/useResearchWork";
import type { ReadingView, TopicsView, WorkView } from "~/types/work";

// useApi 는 Nuxt 런타임($fetch·설정)을 읽는다 — 주소마다 정해 둔 응답만 흉내 낸다. 연구 스트림(EventSource)은
// import.meta.client 가 없는 여기서는 열리지 않고, 컴포넌트 밖이라 onMounted 의 첫 load 도 돌지 않는다
const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("~/composables/useApi", () => ({ apiUrl: (path: string) => `/api${path}`, useApi: () => api }));
vi.mock("~/composables/useHistory", () => ({ useHistory: () => ({ refresh: vi.fn() }) }));

const ID = "11111111-1111-4111-8111-111111111111";
const TOPICS: TopicsView = { picked_id: null, seeds_left: 2, corpus: null, papers: {}, items: [] };
const READING: ReadingView = {
  topic_id: 7,
  subquestions: [],
  funnel: { reviewed: null, adopted: null, candidates: 0, picked: 0 },
  items: [],
  excluded: [],
};
const LOAD_FAILED = "이어간 연구를 불러오지 못했습니다";
const RELOAD_FAILED = "최신 상태를 불러오지 못했습니다";

function work(over: Partial<WorkView> = {}): WorkView {
  return {
    id: ID,
    phase: "topics",
    concepts: [],
    memo: null,
    is_example: false,
    progress: {},
    generations: [],
    ...over,
  };
}

function httpError(status: number): Error & { status: number } {
  return Object.assign(new Error(`HTTP ${status}`), { status });
}

// 주소 끝(work·topics·reading)마다 응답을 차례로 꺼낸다 — Error 면 거절, Promise 면 그대로(응답을 기다리게 할 때)
function route(replies: Record<string, unknown[]>): void {
  api.mockImplementation((url: string) => {
    const kind = url.slice(url.lastIndexOf("/") + 1);
    const next = replies[kind]?.shift();
    if (next === undefined) return Promise.reject(new Error(`예상하지 않은 요청 ${url}`));
    if (next instanceof Error) return Promise.reject(next);
    return next instanceof Promise ? next : Promise.resolve(next);
  });
}

function setup() {
  return useResearchWork(ID, { enabled: ref(true) });
}

afterEach(() => {
  api.mockReset();
});

describe("useResearchWork — 오류는 그것을 낸 조회만 비운다", () => {
  it("실패한 조회를 다시 읽기 시작하면 바로 비우고(기다리는 동안 '불러오는 중'), 성공한 뒤에도 비어 있다", async () => {
    let respond: (v: TopicsView) => void = () => {};
    route({ topics: [httpError(500), new Promise<TopicsView>((resolve) => (respond = resolve))] });
    const w = setup();
    w.setWork(work());
    await w.reload("topics");
    expect(w.error.value).toBe(RELOAD_FAILED);

    const again = w.reload("topics");
    expect(w.error.value).toBeNull();
    respond(TOPICS);
    await again;
    expect(w.error.value).toBeNull();
    expect(w.state.value.topics).toEqual(TOPICS);
  });

  it("다른 조회의 성공·연구 맞추기(setWork)는 그 오류를 지우지 않는다 — 실패해 빈 단계가 요청 없이 '불러오는 중'에 멈추지 않게", async () => {
    route({ topics: [httpError(500)], reading: [READING] });
    const w = setup();
    w.setWork(work());
    await w.reload("topics");
    await w.reload("reading");
    expect(w.state.value.reading).toEqual(READING);
    expect(w.error.value).toBe(RELOAD_FAILED);

    w.setWork(work({ phase: "reading" }));
    expect(w.error.value).toBe(RELOAD_FAILED);
  });

  it("첫 GET work 가 5xx 로 실패한 뒤 [이 연구 이어가기] 응답으로 연구를 맞추면 오류가 풀린다", async () => {
    route({ work: [httpError(500)] });
    const w = setup();
    await w.load();
    expect(w.exists.value).toBeNull();
    expect(w.error.value).toBe(LOAD_FAILED);

    w.setWork(work());
    expect(w.exists.value).toBe(true);
    expect(w.error.value).toBeNull();
  });

  it("연구를 다시 읽다(reload('work')) 실패한 오류도 연구를 맞추면 풀린다", async () => {
    route({ work: [httpError(500)] });
    const w = setup();
    w.setWork(work());
    await w.reload("work");
    expect(w.error.value).toBe(RELOAD_FAILED);

    w.setWork(work({ phase: "reading" }));
    expect(w.error.value).toBeNull();
    expect(w.state.value.work?.phase).toBe("reading");
  });

  it("다른 조회의 오류는 그 조회 칸에만 있다 — 처음 여는 단계는 응답을 기다리는 동안 '불러오는 중'이다", async () => {
    let respond: (v: ReadingView) => void = () => {};
    route({ topics: [httpError(500)], reading: [new Promise<ReadingView>((resolve) => (respond = resolve))] });
    const w = setup();
    w.setWork(work());
    await w.reload("topics");
    expect(w.errorOf("topics")).toBe(RELOAD_FAILED);

    const opening = w.reload("reading");
    expect(w.errorOf("reading")).toBeNull();
    respond(READING);
    await opening;
    expect(w.errorOf("reading")).toBeNull();
    expect(w.errorOf("topics")).toBe(RELOAD_FAILED);
  });

  it("실패한 조회는 다른 조회가 실패했다 성공해도 남고, 다음 ensure 가 다시 요청한다", async () => {
    route({ topics: [httpError(500), TOPICS], work: [httpError(503), work({ phase: "reading" })] });
    const w = setup();
    w.setWork(work());
    await w.ensure("topics");
    await w.reload("work");
    await w.reload("work");
    expect(w.state.value.topics).toBeNull();
    expect(w.errorOf("topics")).toBe(RELOAD_FAILED);
    expect(w.errorOf("work")).toBeNull();

    api.mockClear();
    await w.ensure("topics");
    expect(api).toHaveBeenCalledTimes(1);
    expect(api.mock.calls[0]?.[0]).toBe(`/research/${ID}/topics`);
    expect(w.state.value.topics).toEqual(TOPICS);
    expect(w.errorOf("topics")).toBeNull();

    // 읽어 둔 조회는 다시 들어와도 요청하지 않는다(갱신은 이벤트가 맡는다)
    api.mockClear();
    await w.ensure("topics");
    expect(api).not.toHaveBeenCalled();
  });

  it("처음부터 다시 읽으면(load) 어느 조회가 낸 오류든 비운다", async () => {
    route({ work: [work()], topics: [httpError(500)] });
    const w = setup();
    w.setWork(work());
    await w.reload("topics");
    expect(w.error.value).toBe(RELOAD_FAILED);

    await w.load();
    expect(w.exists.value).toBe(true);
    expect(w.error.value).toBeNull();
  });
});
