// frontend/composables/useResearchWork.ts
// 이어간 연구(연구 어시스턴트)의 조회·쓰기 API 와 화면 상태. 상태 판단은 순수 함수(utils/workEvents.ts)가 하고
// 여기서는 요청·스트림·세대 번호만 다룬다 — useResearchJob 과 같은 관례(shallowRef, 늦은 응답 버리기,
// EventSource 는 브라우저에서만, CLOSED 일 때만 백오프 재연결, 떠날 때 끊기)
import {
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

export interface ResearchWorkHandle {
  state: Readonly<ShallowRef<WorkState>>;
  // null = 아직 모름(읽는 중·완료 전 딥리서치), false = 이어가지 않음(GET work 404), true = 이어간 연구
  exists: Readonly<Ref<boolean | null>>;
  loading: Readonly<Ref<boolean>>;
  error: Ref<string | null>;
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
  const error = ref<string | null>(null);

  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let historyTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  // 주소의 잡이 바뀌거나 페이지를 떠난 뒤 도착한 이전 요청의 응답을 버린다
  let generation = 0;
  // 조회마다 마지막으로 보낸 요청 — 앞서 보낸 요청이 늦게 와 새 값을 덮지 않게
  const tokens: Record<WorkResource, number> = { work: 0, topics: 0, reading: 0, proposal: 0 };
  // 이 화면이 한 번이라도 읽은 조회 — 생성이 끝났을 때 이것만 다시 읽는다(보지 않는 단계는 열 때 읽는다)
  const loaded = new Set<WorkResource>();

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
    error.value = null;
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
      else error.value = researchErrorMessage(e, "이어간 연구를 불러오지 못했습니다");
    } finally {
      if (gen === generation) loading.value = false;
    }
  }

  async function reload(kind: WorkResource): Promise<void> {
    if (exists.value !== true) return;
    const gen = generation;
    const token = ++tokens[kind];
    loaded.add(kind);
    try {
      const apply = await fetchResource(kind, toValue(jobId));
      if (gen !== generation || token !== tokens[kind]) return;
      state.value = apply(state.value);
    } catch (e) {
      if (gen !== generation || token !== tokens[kind]) return;
      error.value = researchErrorMessage(e, "최신 상태를 불러오지 못했습니다");
    }
  }

  // 단계 화면이 열릴 때 — 이미 읽은 조회는 다시 읽지 않는다(갱신은 이벤트가 맡는다)
  function ensure(kind: WorkResource): Promise<void> {
    return loaded.has(kind) ? Promise.resolve() : reload(kind);
  }

  // [이 연구 이어가기]·PATCH 응답처럼 쓰기 응답이 준 연구로 맞춘다. 처음 이어간 화면은 여기서 스트림을 연다
  function setWork(view: WorkView): void {
    tokens.work += 1;
    state.value = withWork(state.value, view);
    exists.value = true;
    loaded.add("work");
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

  return { state, exists, loading, error, load, reload, ensure, setWork, afterAction, connect, disconnect };
}
