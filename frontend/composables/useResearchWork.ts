// frontend/composables/useResearchWork.ts
// 이어간 연구(연구 어시스턴트)의 조회·쓰기 API 와 화면 상태. 상태 판단은 순수 함수(utils/workEvents.ts)가 하고
// 여기서는 요청·스트림·세대 번호만 다룬다 — useResearchJob 과 같은 관례(shallowRef, 늦은 응답 버리기,
// EventSource 는 브라우저에서만, CLOSED 일 때만 백오프 재연결, 떠날 때 끊기)
import {
  computed,
  getCurrentInstance,
  getCurrentScope,
  onBeforeUnmount,
  onMounted,
  onScopeDispose,
  ref,
  shallowRef,
  toValue,
  watch,
  type ComputedRef,
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
  SectionSources,
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
import { httpStatus, type ConnectionState } from "~/utils/apiErrors";
import { applyWorkEvent, initialWorkState, withResource, withWork } from "~/utils/workEvents";
import {
  WORK_LOAD_FAILED,
  WORK_REFRESH_FAILED,
  WORK_SLOW_MS,
  WORK_STREAM_LOST_MS,
  staleWorkKinds,
  withWorkReason,
  workConnectionAfter,
  workFailure,
  type WorkFailure,
  type WorkStreamEvent,
} from "~/utils/workErrors";
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
    // [이 키워드로 다시 만들기] — 저장된 키워드(work.concepts)로 고치지 않은 AI 카드를 다시(06e). skipped = 만드는 중이라 건너뛴 수
    regenerateTopics: (jobId: string) =>
      api<{ topic_ids: number[]; gen_ids: number[]; skipped: number }>(`${job(jobId)}/topics/regenerate`, {
        method: "POST",
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
    // 인용 근거 — 문단의 절 gen_id 로 그 생성이 모델에 넘긴 초록·원문 대목을 읽는다(읽기라 예시 연구도 된다)
    getSectionSources: (jobId: string, key: string, gen: number) =>
      api<SectionSources>(`${job(jobId)}/sections/${encodeURIComponent(key)}/sources`, { query: { gen } }),
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
  // 그 조회가 낸 오류의 종류·이유 — 화면의 오류 블록(SkxErrorState 의 kind·이유)이 읽는다
  failureOf(kind: WorkErrorKind): WorkFailure | null;
  // 연구 스트림(SSE)의 연결 상태 — SkxConnectionBanner 의 state(끊겨 다시 붙는 동안 진행 표시가 멈춰 보이지 않게 알린다)
  connection: Readonly<Ref<ConnectionState>>;
  load(): Promise<void>;
  // 성공하면(또는 더 늦게 보낸 같은 조회가 이 응답을 갈음하면) true, 실패해 오류를 남겼거나 읽을 연구가 없으면 false
  reload(kind: WorkResource): Promise<boolean>;
  ensure(kind: WorkResource): Promise<boolean>;
  setWork(view: WorkView): void;
  // 사용자 동작 직후 — history.refresh('research') 를 1초 묶어 부른다
  afterAction(): void;
  connect(): void;
  // [다시 연결] — 백오프를 기다리지 않고 지금 다시 붙는다
  reconnect(): void;
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
  const errors = shallowRef<Partial<Record<WorkErrorKind, WorkFailure>>>({});
  const error = computed(() => Object.values(errors.value).at(-1)?.message ?? null);
  const connection = ref<ConnectionState>("connected");

  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  // 끊긴 뒤 WORK_STREAM_LOST_MS 가 지나도 다시 붙지 못하면 '연결하지 못했어요'(lost)로 바꾸는 시계
  let lostTimer: ReturnType<typeof setTimeout> | null = null;
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
    return errors.value[kind]?.message ?? null;
  }

  function failureOf(kind: WorkErrorKind): WorkFailure | null {
    return errors.value[kind] ?? null;
  }

  function setError(kind: WorkErrorKind, failure: WorkFailure): void {
    const { [kind]: _old, ...rest } = errors.value;
    errors.value = { ...rest, [kind]: failure };
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
      else setError("load", workFailure(e, WORK_LOAD_FAILED));
    } finally {
      if (gen === generation) loading.value = false;
    }
  }

  // 결과는 화면이 '쓰기는 됐지만 화면을 새로 고치지 못했다'를 가르는 데 쓴다(성공 문구는 true 일 때만). 더 늦게 보낸 같은 조회가
  // 이 응답을 갈음하면 true — 그 조회가 실패하면 그 조회가 오류 칸에 남겨 단계 위 한 줄이 알린다
  async function reload(kind: WorkResource): Promise<boolean> {
    if (exists.value !== true) return false;
    const gen = generation;
    const token = ++tokens[kind];
    loaded.add(kind);
    // 이 조회가 낸 오류는 다시 읽는 동안 비운다 — [다시 불러오기] 뒤 응답을 기다리는 동안 '불러오는 중'이 보이게
    clearErrorOf(kind);
    try {
      const apply = await fetchResource(kind, toValue(jobId));
      if (gen !== generation || token !== tokens[kind]) return true;
      state.value = apply(state.value);
      clearErrorOf(kind);
      return true;
    } catch (e) {
      if (gen !== generation || token !== tokens[kind]) return true;
      setError(kind, workFailure(e, WORK_REFRESH_FAILED));
      return false;
    }
  }

  // 단계 화면이 열릴 때 — 이미 읽은 조회는 다시 읽지 않는다(갱신은 이벤트가 맡는다). 마지막 읽기가 실패한 조회는
  // 다시 읽는다 — 실패한 채 다른 단계로 갔다 돌아왔을 때 요청 없이 멈추지 않게. loaded 에서는 빼지 않는다: 읽어 둔 값이
  // 있는 조회가 한 번 실패했다고 빼면 그 뒤 이벤트가 다시 읽지 않아 화면이 옛 값에 머문다
  function ensure(kind: WorkResource): Promise<boolean> {
    return loaded.has(kind) && errorOf(kind) === null ? Promise.resolve(true) : reload(kind);
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

  // 연결 상태를 옮긴다. 끊기면(drop·retry) lost 시계를 한 번만 건다 — 다시 붙으면(open)·일부러 닫으면(stop) 시계를 걷는다
  function streamEvent(event: WorkStreamEvent): void {
    connection.value = workConnectionAfter(connection.value, event);
    if (connection.value === "reconnecting") {
      if (!lostTimer) {
        lostTimer = setTimeout(() => {
          lostTimer = null;
          connection.value = workConnectionAfter(connection.value, "giveUp");
        }, WORK_STREAM_LOST_MS);
      }
    } else if (lostTimer) {
      clearTimeout(lostTimer);
      lostTimer = null;
    }
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
      if (source === es) streamEvent("open");
    };
    // 서버의 15초 하트비트는 이름 붙은 'ping' 이벤트(relay.SSE_PING)라 onmessage 에 오지 않는다. 이 스트림은 조용함 감시를 두지 않고
    // 끊김을 onerror 로만 보므로(연결 띠는 streamEvent) 하트비트를 받을 리스너가 없다
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
      // CLOSED 는 브라우저가 포기한 경우(오류 응답 등)라 간격을 늘려 가며 직접 다시 붙인다. 어느 쪽이든 다시 붙을 때까지는
      // 진행 표시가 멈춰 보이므로 연결 띠로 알린다. 이미 닫았거나 갈아 끼운 연결의 늦은 오류는 무시한다
      if (source !== es) return;
      streamEvent("drop");
      if (es.readyState !== EventSource.CLOSED) return;
      source = null;
      scheduleReconnect();
    };
  }

  // [다시 연결] — 기다리던 백오프를 걷고 지금 새로 붙는다. 붙으면 서버가 snapshot 부터 보내 놓친 생성을 다시 읽는다
  function reconnect(): void {
    if (disposed || exists.value !== true) return;
    clearReconnect();
    source?.close();
    source = null;
    attempts = 0;
    streamEvent("retry");
    connect();
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
    streamEvent("stop");
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

  return {
    state,
    exists,
    loading,
    error,
    errorOf,
    failureOf,
    connection,
    load,
    reload,
    ensure,
    setWork,
    afterAction,
    connect,
    reconnect,
    disconnect,
  };
}

// ── 단계 화면이 함께 쓰는 오류 처리 ──────────────────────────

export interface WorkStaleHandle {
  // 단계 위 한 줄(SkxInlineError) — '최신 상태를 불러오지 못했어요 — 이유'. 알릴 실패가 없으면 null
  line: ComputedRef<string | null>;
  // [다시 시도] 로 다시 읽는 중 — SkxInlineError 의 busy
  retrying: Readonly<Ref<boolean>>;
  // 쓰기는 됐지만 바로 뒤 다시 읽기가 실패했다 — 한 줄의 머리를 그 사실(WORK_SAVED_STALE)로 바꾼다. 실패가 걷히면 함께 걷힌다
  markSaved(head: string): void;
  retry(): Promise<void>;
}

// 이미 읽어 둔 단계의 다시 읽기(단계 진입·생성 완료 이벤트 뒤·쓰기 뒤)가 실패하면 옛 목록·옛 보고서가 아무 안내 없이 남았다 —
// 단계가 쓰는 조회(kinds) 가운데 실패한 것을 단계 위 한 줄로 알리고 [다시 시도] 로 그 조회만 다시 읽는다. 본문 조회(main)가 아직
// 값이 없으면 본문 자리의 오류 블록이 알리므로 한 줄에서는 뺀다(staleWorkKinds)
export function useWorkStale(work: ResearchWorkHandle, kinds: readonly WorkResource[], main: WorkResource): WorkStaleHandle {
  const savedHead = ref<string | null>(null);
  const retrying = ref(false);
  const failed = computed(() => staleWorkKinds(kinds, main, work.state.value, (kind) => work.errorOf(kind) !== null));
  const line = computed(() => {
    const first = failed.value[0];
    if (!first) return null;
    return withWorkReason(savedHead.value ?? WORK_REFRESH_FAILED, work.failureOf(first)?.reason ?? "");
  });
  // 실패가 모두 걷히면(다시 읽기 성공) 쓰기 뒤 머리도 걷는다 — [다시 시도] 로 다시 읽는 동안(오류 칸이 잠시 빈다)은 기다린다
  watch(
    () => failed.value.length === 0,
    (none) => {
      if (none && !retrying.value) savedHead.value = null;
    },
  );

  function markSaved(head: string): void {
    if (failed.value.length) savedHead.value = head;
  }

  async function retry(): Promise<void> {
    if (retrying.value) return;
    const targets = [...failed.value];
    retrying.value = true;
    try {
      const results = await Promise.all(targets.map((kind) => work.reload(kind)));
      if (results.every(Boolean)) savedHead.value = null;
    } finally {
      retrying.value = false;
    }
  }

  return { line, retrying, markSaved, retry };
}

// 쓰기 요청이 오래 걸리는가 — busy 가 ms(기본 90초) 넘게 이어지면 참. 쓰기는 끊으면 서버에서 두 번 돌 수 있어 시간 제한으로
// 끊지 않는다(useApi 도 쓰기에는 제한을 두지 않는다) — 화면은 이 값으로 '응답이 늦어지고 있어요' 안내만 띄우고 잠금은 둔다
export function useSlowWrite(busy: MaybeRefOrGetter<boolean>, ms = WORK_SLOW_MS): Readonly<Ref<boolean>> {
  const slow = ref(false);
  let timer: ReturnType<typeof setTimeout> | null = null;
  function clear(): void {
    if (timer) clearTimeout(timer);
    timer = null;
  }
  watch(
    () => toValue(busy),
    (on) => {
      clear();
      slow.value = false;
      if (on) {
        timer = setTimeout(() => {
          timer = null;
          slow.value = true;
        }, ms);
      }
    },
    { immediate: true },
  );
  if (getCurrentScope()) onScopeDispose(clear);
  return slow;
}
