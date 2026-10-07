// frontend/composables/useResearchWork.ts
// 이어간 연구(연구 어시스턴트)의 조회·쓰기 API 와 화면 상태. 상태 판단은 순수 함수(utils/workEvents.ts)가 하고
// 여기서는 요청·스트림·세대 번호만 다룬다 — useResearchJob 과 같은 관례(shallowRef, 늦은 응답 버리기,
// EventSource 는 브라우저에서만, CLOSED 일 때만 백오프 재연결, 떠날 때 끊기)
import {
  computed,
  getCurrentInstance,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type Ref,
  type ShallowRef,
} from "vue";
import type {
  OutlinePut,
  ProposalView,
  ReadingItem,
  ReadingPut,
  ReadingView,
  SectionPut,
  TopicCreate,
  TopicItem,
  TopicPatch,
  TopicsView,
  WorkEvent,
  WorkPatch,
  WorkPhase,
  WorkResource,
  WorkState,
  WorkView,
} from "~/types/work";
import { httpStatus, researchErrorMessage } from "~/utils/researchErrors";
import { applyWorkEvent, initialWorkState, withResource, withWork } from "~/utils/workEvents";
import { apiUrl, useApi } from "./useApi";
import { useHistory } from "./useHistory";

const RECONNECT_BASE_MS = 2000;
const RECONNECT_MAX_MS = 30000;
// 사용자 동작·work 이벤트가 몰려도 사이드바 기록은 한 번만 다시 읽는다(spec §6-4 '짧게 묶어')
const HISTORY_REFRESH_MS = 1000;

export function useWorkApi() {
  const api = useApi();
  const job = (jobId: string) => `/research/${encodeURIComponent(jobId)}`;
  const ifMatch = (version: number) => ({ "If-Match": String(version) });
  return {
    continueWork: (jobId: string) => api<WorkView>(`${job(jobId)}/work/continue`, { method: "POST" }),
    getWork: (jobId: string) => api<WorkView>(`${job(jobId)}/work`),
    patchWork: (jobId: string, body: WorkPatch) => api<WorkView>(`${job(jobId)}/work`, { method: "PATCH", body }),
    getTopics: (jobId: string) => api<TopicsView>(`${job(jobId)}/topics`),
    generateTopics: (jobId: string) =>
      api<{ topic_ids: number[]; gen_ids: number[] }>(`${job(jobId)}/topics/generate`, {
        method: "POST",
        body: { mode: "other" },
      }),
    createTopic: (jobId: string, body: TopicCreate) =>
      api<TopicItem>(`${job(jobId)}/topics`, { method: "POST", body }),
    editTopic: (jobId: string, tid: number, body: TopicPatch) =>
      api<TopicItem>(`${job(jobId)}/topics/${tid}`, { method: "PATCH", body }),
    pickTopic: (jobId: string, tid: number) =>
      api<{ topic_id: number; phase: WorkPhase }>(`${job(jobId)}/topics/${tid}/pick`, { method: "POST" }),
    getReading: (jobId: string) => api<ReadingView>(`${job(jobId)}/reading`),
    putReading: (jobId: string, cnts: string, body: ReadingPut) =>
      api<ReadingItem>(`${job(jobId)}/reading/${encodeURIComponent(cnts)}`, { method: "PUT", body }),
    getProposal: (jobId: string) => api<ProposalView>(`${job(jobId)}/proposal`),
    createOutline: (jobId: string) => api<{ gen_id: number }>(`${job(jobId)}/outline`, { method: "POST" }),
    putOutline: (jobId: string, version: number, body: OutlinePut) =>
      api<ProposalView>(`${job(jobId)}/outline`, { method: "PUT", headers: ifMatch(version), body }),
    generateSection: (jobId: string, key: string) =>
      api<{ gen_id: number }>(`${job(jobId)}/sections/${encodeURIComponent(key)}/generate`, { method: "POST" }),
    putSection: (jobId: string, key: string, version: number, body: SectionPut) =>
      api<ProposalView>(`${job(jobId)}/sections/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers: ifMatch(version),
        body,
      }),
    regenerateParagraph: (jobId: string, key: string, pid: string) =>
      api<{ gen_id: number }>(
        `${job(jobId)}/sections/${encodeURIComponent(key)}/paragraphs/${encodeURIComponent(pid)}/regenerate`,
        { method: "POST" },
      ),
    cancelGeneration: (jobId: string, gid: number) =>
      api<unknown>(`${job(jobId)}/generations/${gid}/cancel`, { method: "POST" }),
    retryGeneration: (jobId: string, gid: number) =>
      api<{ gen_id: number }>(`${job(jobId)}/generations/${gid}/retry`, { method: "POST" }),
  };
}

// 오류를 낸 조회 — 'load' 는 첫 GET work
export type WorkErrorKind = WorkResource | "load";

export interface ResearchWorkHandle {
  state: Readonly<ShallowRef<WorkState>>;
  // null = 아직 모름(읽는 중·완료 전 딥리서치), false = 이어가지 않음(GET work 404), true = 이어간 연구
  exists: Readonly<Ref<boolean | null>>;
  loading: Readonly<Ref<boolean>>;
  // 남아 있는 오류 가운데 가장 늦게 난 것(호환용). 단계 화면은 errorOf 로 자기 조회의 오류만 읽는다
  error: Readonly<Ref<string | null>>;
  // 그 조회가 낸 오류 — 다른 조회의 실패·성공과 섞이지 않는다
  errorOf(kind: WorkErrorKind): string | null;
  load(): Promise<void>;
  reload(kind: WorkResource): Promise<void>;
  ensure(kind: WorkResource): Promise<void>;
  setWork(view: WorkView): void;
  // 사용자 동작 직후 — history.refresh('research') 를 1초 묶어 부른다
  afterAction(): void;
  connect(): void;
  disconnect(): void;
}

// enabled 는 딥리서치가 끝났을 때(completed)만 참이다 — 그 전에는 이어간 연구가 있을 수 없어 읽지 않는다
export function useResearchWork(jobId: MaybeRefOrGetter<string>, opts: { enabled: Ref<boolean> }): ResearchWorkHandle {
  const workApi = useWorkApi();
  const history = useHistory();
  const streamBase = apiUrl("/research");

  const state = shallowRef<WorkState>(initialWorkState());
  const exists = ref<boolean | null>(null);
  const loading = ref(false);
  // 조회마다 따로 둔 오류 칸. 같은 조회를 다시 읽기 시작하거나 성공할 때만 그 칸을 비운다 — 칸이 하나면 다른 조회의
  // 오류가 처음 여는 단계에 '불러오는 중' 대신 보이고, 다른 조회의 성공이 지우면 실패해 비어 있는 단계가 요청 없이
  // '불러오는 중'에 멈춘다. 새로 쓸 때 맨 뒤로 옮겨 error 가 가장 늦게 난 오류를 보이게 한다
  const errors = shallowRef<Partial<Record<WorkErrorKind, string>>>({});
  const error = computed(() => Object.values(errors.value).at(-1) ?? null);

  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let historyTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  // 주소의 잡이 바뀌거나 페이지를 떠난 뒤 도착한 이전 요청의 응답을 버린다
  let generation = 0;
  // 화면을 떠났다(unmount) — 그 뒤 도착한 쓰기 응답(setWork)이나 connect() 가 닫을 주체가 없는
  // EventSource 를 열지 않게 한다(연구 스트림은 끝이 없어 출처당 연결 한 칸을 영구히 차지한다)
  let disposed = false;
  // 조회마다 마지막으로 보낸 요청 — 앞서 보낸 요청이 늦게 와 새 값을 덮지 않게
  const tokens: Record<WorkResource, number> = { work: 0, topics: 0, reading: 0, proposal: 0 };
  // 이 화면이 한 번이라도 읽으려 한 조회 — 생성이 끝났을 때 이것만 다시 읽는다(보지 않는 단계는 열 때 읽는다)
  const loaded = new Set<WorkResource>();

  function errorOf(kind: WorkErrorKind): string | null {
    return errors.value[kind] ?? null;
  }

  function setError(kind: WorkErrorKind, message: string): void {
    const { [kind]: _old, ...rest } = errors.value;
    errors.value = { ...rest, [kind]: message };
  }

  function clearErrorOf(...kinds: WorkErrorKind[]): void {
    if (!kinds.some((kind) => kind in errors.value)) return;
    const next = { ...errors.value };
    for (const kind of kinds) delete next[kind];
    errors.value = next;
  }

  async function fetchResource(kind: WorkResource, id: string): Promise<(s: WorkState) => WorkState> {
    switch (kind) {
      case "work": {
        const view = await workApi.getWork(id);
        return (s) => withWork(s, view);
      }
      case "topics": {
        const view = await workApi.getTopics(id);
        return (s) => withResource(s, "topics", view);
      }
      case "reading": {
        const view = await workApi.getReading(id);
        return (s) => withResource(s, "reading", view);
      }
      case "proposal": {
        const view = await workApi.getProposal(id);
        return (s) => withResource(s, "proposal", view);
      }
    }
  }

  async function load(): Promise<void> {
    const gen = ++generation;
    disconnect();
    state.value = initialWorkState();
    exists.value = null;
    errors.value = {};
    loaded.clear();
    if (!opts.enabled.value) {
      loading.value = false;
      return;
    }
    loading.value = true;
    // 읽는 사이 [이 연구 이어가기] 응답(setWork)이 먼저 맞췄으면 이 응답(그 전의 404 등)은 버린다
    const token = ++tokens.work;
    try {
      const view = await workApi.getWork(toValue(jobId));
      if (gen !== generation || token !== tokens.work) return;
      state.value = withWork(state.value, view);
      exists.value = true;
      loaded.add("work");
      connect();
    } catch (e) {
      if (gen !== generation || token !== tokens.work) return;
      const status = httpStatus(e);
      // 404 = 이어가지 않은 딥리서치(D15 — 화면은 지금 그대로). 스트림을 열지 않는다
      if (status === 404 || status === 422) exists.value = false;
      else setError("load", researchErrorMessage(e, "이어간 연구를 불러오지 못했습니다"));
    } finally {
      if (gen === generation) loading.value = false;
    }
  }

  async function reload(kind: WorkResource): Promise<void> {
    if (exists.value !== true) return;
    const gen = generation;
    const token = ++tokens[kind];
    loaded.add(kind);
    // 이 조회가 낸 오류는 다시 읽는 동안 비운다 — [다시 불러오기] 뒤 응답을 기다리는 동안 '불러오는 중'이 보이게
    clearErrorOf(kind);
    try {
      const apply = await fetchResource(kind, toValue(jobId));
      if (gen !== generation || token !== tokens[kind]) return;
      state.value = apply(state.value);
      clearErrorOf(kind);
    } catch (e) {
      if (gen !== generation || token !== tokens[kind]) return;
      setError(kind, researchErrorMessage(e, "최신 상태를 불러오지 못했습니다"));
    }
  }

  // 단계 화면이 열릴 때 — 이미 읽은 조회는 다시 읽지 않는다(갱신은 이벤트가 맡는다). 마지막 읽기가 실패한 조회는
  // 다시 읽는다 — 실패한 채 다른 단계로 갔다 돌아왔을 때 요청 없이 멈추지 않게. loaded 에서는 빼지 않는다: 읽어 둔 값이
  // 있는 조회가 한 번 실패했다고 빼면 그 뒤 이벤트가 다시 읽지 않아 화면이 옛 값에 머문다
  function ensure(kind: WorkResource): Promise<void> {
    return loaded.has(kind) && errorOf(kind) === null ? Promise.resolve() : reload(kind);
  }

  // [이 연구 이어가기]·PATCH 응답처럼 쓰기 응답이 준 연구로 맞춘다. 처음 이어간 화면은 여기서 스트림을 연다.
  // 호출처는 응답을 기다린 뒤 세대 확인 없이 부르므로 여기서 거른다 — 화면을 떠났거나 주소의 잡이 바뀐 뒤의
  // 응답은 버린다(다른 잡의 연구가 이 상태에 들어가거나 떠난 화면이 스트림을 열지 않게). 서버 id 는 소문자
  // uuid 이고 주소의 id 는 대문자일 수 있어 대소문자를 무시하고 견준다
  function setWork(view: WorkView): void {
    if (disposed || view.id.toLowerCase() !== toValue(jobId).toLowerCase()) return;
    tokens.work += 1;
    state.value = withWork(state.value, view);
    exists.value = true;
    loaded.add("work");
    // 연구를 맞췄으니 첫 GET work·reload('work') 의 오류는 풀렸다(다른 조회의 오류는 그 조회가 비운다)
    clearErrorOf("load", "work");
    connect();
  }

  function afterAction(): void {
    if (!import.meta.client) return;
    if (historyTimer) clearTimeout(historyTimer);
    // 화면을 떠나도 지우지 않는다 — 서버는 이미 바뀌었고 사이드바는 앱 전체가 함께 쓴다
    historyTimer = setTimeout(() => {
      historyTimer = null;
      void history.refresh("research");
    }, HISTORY_REFRESH_MS);
  }

  function connect(): void {
    if (disposed) return;
    if (!import.meta.client || source || exists.value !== true) return;
    clearReconnect();
    const gen = generation;
    const es = new EventSource(`${streamBase}/${encodeURIComponent(toValue(jobId))}/work/stream`);
    source = es;
    es.onopen = () => {
      attempts = 0;
    };
    es.onmessage = (msg: MessageEvent<string>) => {
      if (gen !== generation) return;
      let event: WorkEvent;
      try {
        event = JSON.parse(msg.data) as WorkEvent;
      } catch {
        return;
      }
      const out = applyWorkEvent(state.value, event);
      state.value = out.state;
      for (const kind of out.reload) if (loaded.has(kind)) void reload(kind);
      if (event.kind === "work") afterAction();
    };
    es.onerror = () => {
      // CONNECTING 이면 브라우저가 다시 붙고 서버가 snapshot 부터 보내 상태가 맞춰진다(놓친 생성은 리듀서가 다시 읽게 한다).
      // CLOSED 는 브라우저가 포기한 경우(오류 응답 등)라 간격을 늘려 가며 직접 다시 붙인다
      if (es.readyState !== EventSource.CLOSED) return;
      if (source === es) source = null;
      scheduleReconnect();
    };
  }

  function scheduleReconnect(): void {
    if (reconnectTimer || !import.meta.client) return;
    const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** attempts);
    attempts += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  function clearReconnect(): void {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  function disconnect(): void {
    clearReconnect();
    source?.close();
    source = null;
  }

  if (getCurrentInstance()) {
    onMounted(() => {
      if (opts.enabled.value) void load();
    });
    onBeforeUnmount(() => {
      disposed = true;
      generation += 1;
      disconnect();
    });
  }

  // 딥리서치가 이 화면에서 끝났거나(enabled 가 참이 됨) 주소의 잡이 바뀌면 처음부터 다시 읽는다
  watch(
    () => [toValue(jobId), opts.enabled.value] as const,
    ([id, on], [oldId, oldOn]) => {
      if (import.meta.client && (id !== oldId || on !== oldOn)) void load();
    },
  );

  return { state, exists, loading, error, errorOf, load, reload, ensure, setWork, afterAction, connect, disconnect };
}
