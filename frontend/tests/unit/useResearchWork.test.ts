// frontend/tests/unit/useResearchWork.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import { useResearchWork, useSlowWrite, useWorkStale } from "~/composables/useResearchWork";
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
const LOAD_FAILED = "이어간 연구를 불러오지 못했어요";
const RELOAD_FAILED = "최신 상태를 불러오지 못했어요";

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
  it("실패한 조회를 다시 읽는 동안에는 오류를 두고 다시 읽는 중(reloading)을 알리며, 성공한 뒤에만 비운다", async () => {
    let respond: (v: TopicsView) => void = () => {};
    route({ topics: [httpError(500), new Promise<TopicsView>((resolve) => (respond = resolve))] });
    const w = setup();
    w.setWork(work());
    await w.reload("topics");
    expect(w.error.value).toBe(RELOAD_FAILED);
    expect(w.reloading("topics")).toBe(false);

    // [다시 시도] — 오류 블록·줄이 버튼째 사라지지 않고 busy 를 보인다
    const again = w.reload("topics");
    expect(w.error.value).toBe(RELOAD_FAILED);
    expect(w.reloading("topics")).toBe(true);
    expect(w.reloading("reading")).toBe(false);
    respond(TOPICS);
    await again;
    expect(w.error.value).toBeNull();
    expect(w.reloading("topics")).toBe(false);
    expect(w.state.value.topics).toEqual(TOPICS);
  });

  it("다시 읽기가 또 실패하면 오류가 그대로 남는다 — 더 늦게 보낸 같은 조회가 돌면 그것이 끝날 때까지 다시 읽는 중", async () => {
    let first: (v: TopicsView) => void = () => {};
    let second: (v: TopicsView) => void = () => {};
    route({
      topics: [
        httpError(500),
        httpError(502),
        new Promise<TopicsView>((resolve) => (first = resolve)),
        new Promise<TopicsView>((resolve) => (second = resolve)),
      ],
    });
    const w = setup();
    w.setWork(work());
    await w.reload("topics");
    await w.reload("topics");
    expect(w.failureOf("topics")?.kind).toBe("server");

    const older = w.reload("topics");
    const newer = w.reload("topics");
    first(TOPICS);
    await older;
    // 앞선 요청은 늦은 요청이 갈음한다 — 오류도 다시 읽는 중도 늦은 요청이 끝날 때까지 그대로
    expect(w.reloading("topics")).toBe(true);
    expect(w.error.value).toBe(RELOAD_FAILED);
    second(TOPICS);
    await newer;
    expect(w.reloading("topics")).toBe(false);
    expect(w.error.value).toBeNull();
  });

  it("연구를 맞추면(setWork) 도는 reload('work') 의 다시 읽는 중도 걷힌다(그 응답은 버려진다)", async () => {
    let respond: (v: WorkView) => void = () => {};
    route({ work: [new Promise<WorkView>((resolve) => (respond = resolve))] });
    const w = setup();
    w.setWork(work());
    const pending = w.reload("work");
    expect(w.reloading("work")).toBe(true);
    w.setWork(work({ phase: "reading" }));
    expect(w.reloading("work")).toBe(false);
    respond(work());
    await pending;
    expect(w.state.value.work?.phase).toBe("reading");
    expect(w.reloading("work")).toBe(false);
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

  it("reload 는 다시 읽었는지를 돌려주고, 오류의 종류·이유를 failureOf 로 내보낸다", async () => {
    route({ topics: [httpError(503), TOPICS] });
    const w = setup();
    w.setWork(work());
    expect(await w.reload("topics")).toBe(false);
    expect(w.failureOf("topics")).toMatchObject({ kind: "busy", reason: expect.stringContaining("요청이 몰려") });
    expect(await w.reload("topics")).toBe(true);
    expect(w.failureOf("topics")).toBeNull();
    // 이어가지 않은(모르는) 연구는 읽지 않는다 — 다시 읽지 못한 것이다
    expect(await setup().reload("topics")).toBe(false);
  });

  it("첫 GET work 의 5xx 는 'load' 칸에 종류와 함께 남는다(단계 화면·이어가기 카드 자리가 읽는다)", async () => {
    route({ work: [httpError(500)] });
    const w = setup();
    await w.load();
    expect(w.failureOf("load")).toEqual({ kind: "server", message: LOAD_FAILED, reason: "" });
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

describe("useWorkStale — 읽어 둔 단계의 다시 읽기 실패를 단계 위 한 줄로", () => {
  it("본문 조회가 값이 없을 때의 실패는 한 줄에 싣지 않는다(본문 자리의 오류 블록 몫)", async () => {
    route({ topics: [httpError(500)] });
    const w = setup();
    w.setWork(work());
    const stale = useWorkStale(w, ["topics", "work"], "topics");
    await w.reload("topics");
    expect(stale.line.value).toBeNull();
  });

  it("읽어 둔 뒤의 실패는 '최신 상태를 불러오지 못했어요 — 이유', [다시 시도] 는 실패한 조회만 다시 읽어 걷는다", async () => {
    route({ topics: [TOPICS, new TypeError("Failed to fetch"), TOPICS] });
    const w = setup();
    w.setWork(work());
    const stale = useWorkStale(w, ["topics", "work"], "topics");
    await w.reload("topics");
    await w.reload("topics");
    expect(stale.line.value).toBe(`${RELOAD_FAILED} — 네트워크 연결을 확인해 주세요`);

    api.mockClear();
    await stale.retry();
    expect(api).toHaveBeenCalledTimes(1);
    expect(api.mock.calls[0]?.[0]).toBe(`/research/${ID}/topics`);
    expect(stale.line.value).toBeNull();
    expect(stale.retrying.value).toBe(false);
  });

  it("쓰기 뒤 다시 읽기가 실패하면 머리를 '저장은 됐지만 화면을 새로 고치지 못했어요'로 — 다시 읽기가 되면 함께 걷힌다", async () => {
    route({ topics: [TOPICS, httpError(500), TOPICS] });
    const w = setup();
    w.setWork(work());
    const stale = useWorkStale(w, ["topics", "work"], "topics");
    await w.reload("topics");
    // 실패가 없을 때의 표시는 무시한다(사실이 아니다)
    stale.markSaved("저장은 됐지만 화면을 새로 고치지 못했어요");
    expect(stale.line.value).toBeNull();

    await w.reload("topics");
    stale.markSaved("저장은 됐지만 화면을 새로 고치지 못했어요");
    expect(stale.line.value).toBe("저장은 됐지만 화면을 새로 고치지 못했어요");

    await stale.retry();
    expect(stale.line.value).toBeNull();
  });

  it("[다시 시도]·배경 다시 읽기 동안 줄과 쓰기 뒤 머리를 그대로 둔다 — 버튼째 사라지거나 깜빡이지 않고, 다시 실패해도 머리가 남는다", async () => {
    let respond: (v: TopicsView) => void = () => {};
    route({
      topics: [TOPICS, httpError(500), httpError(503), new Promise<TopicsView>((resolve) => (respond = resolve))],
    });
    const w = setup();
    w.setWork(work());
    const stale = useWorkStale(w, ["topics", "work"], "topics");
    await w.reload("topics");
    await w.reload("topics");
    stale.markSaved("저장은 됐지만 화면을 새로 고치지 못했어요");
    const head = "저장은 됐지만 화면을 새로 고치지 못했어요";
    expect(stale.line.value).toBe(head);

    // 배경 다시 읽기(생성 완료 이벤트 등)가 또 실패 — 줄은 비지 않고 머리도 남는다(이유만 새 실패로)
    const background = w.reload("topics");
    expect(stale.line.value?.startsWith(head)).toBe(true);
    await background;
    await nextTick();
    expect(stale.line.value).toBe(`${head} — 요청이 몰려 있어요.\n잠시 뒤 다시 시도해 주세요.`);

    // [다시 시도] — 도는 동안 줄이 남아 busy 를 보이고, 성공하면 함께 걷힌다
    const retrying = stale.retry();
    await nextTick();
    expect(stale.retrying.value).toBe(true);
    expect(stale.line.value?.startsWith(head)).toBe(true);
    respond(TOPICS);
    await retrying;
    await nextTick();
    expect(stale.retrying.value).toBe(false);
    expect(stale.line.value).toBeNull();
  });
});

describe("useSlowWrite — 쓰기가 오래 걸리면 안내만(끊지 않는다)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("busy 가 90초 넘게 이어질 때만 참, 풀리면 바로 거짓", async () => {
    vi.useFakeTimers();
    const busy = ref(false);
    const slow = useSlowWrite(busy);
    busy.value = true;
    await nextTick();
    vi.advanceTimersByTime(89_000);
    expect(slow.value).toBe(false);
    vi.advanceTimersByTime(1_000);
    expect(slow.value).toBe(true);
    busy.value = false;
    await nextTick();
    expect(slow.value).toBe(false);
    // 다시 바빠지면 처음부터 다시 잰다
    busy.value = true;
    await nextTick();
    vi.advanceTimersByTime(60_000);
    expect(slow.value).toBe(false);
  });
});
