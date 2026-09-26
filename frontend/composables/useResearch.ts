// frontend/composables/useResearch.ts
import { getCurrentInstance, onBeforeUnmount, onMounted, ref, shallowRef, toValue, watch, type MaybeRefOrGetter } from "vue";
import type {
  ResearchApproveResponse,
  ResearchCancelResponse,
  ResearchCreateResponse,
  ResearchEvent,
  ResearchJob,
  ResearchParams,
  ResearchRetryResponse,
  ResearchView,
} from "~/types/research";
import { applyResearchEvent, initialResearchView, isTerminalEvent, isTerminalStatus, refreshView, withPlan } from "~/utils/researchEvents";
import { httpStatus, researchErrorMessage } from "~/utils/researchErrors";
import { apiUrl, useApi } from "./useApi";
import { useHistory } from "./useHistory";

const RECONNECT_BASE_MS = 2000;
const RECONNECT_MAX_MS = 30000;

export function useResearchApi() {
  const api = useApi();
  return {
    create: (question: string, params: ResearchParams = {}) =>
      api<ResearchCreateResponse>("/research", { method: "POST", body: { question, params } }),
    get: (jobId: string) => api<ResearchJob>(`/research/${encodeURIComponent(jobId)}`),
    approve: (jobId: string, plan?: string[]) =>
      api<ResearchApproveResponse>(`/research/${encodeURIComponent(jobId)}/approve`, {
        method: "POST",
        body: plan ? { plan } : {},
      }),
    retry: (jobId: string) =>
      api<ResearchRetryResponse>(`/research/${encodeURIComponent(jobId)}/retry`, { method: "POST" }),
    cancel: (jobId: string) =>
      api<ResearchCancelResponse>(`/research/${encodeURIComponent(jobId)}/cancel`, { method: "POST" }),
  };
}

export function useResearchStarter() {
  const research = useResearchApi();
  const history = useHistory();

  async function startResearch(question: string): Promise<string> {
    const { job_id } = await research.create(question);
    try {
      await history.upsertResearch(job_id, question);
    } catch (e) {
      // 잡은 이미 만들어졌다 — 기록 저장 실패로 멈추면 돌고 있는 잡의 주소를 잃는다
      console.warn("[research] 기록 저장 실패", e);
    }
    return job_id;
  }

  return { startResearch };
}

export function useResearchJob(jobId: MaybeRefOrGetter<string>) {
  const research = useResearchApi();
  const history = useHistory();
  const streamBase = apiUrl("/research");

  const view = shallowRef<ResearchView | null>(null);
  const loading = ref(false);
  const notFound = ref(false);
  const loadError = ref("");
  const actionError = ref("");
  const busy = ref(false);
  const connected = ref(false);

  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  // 주소의 잡이 바뀌거나 페이지를 떠난 뒤 도착한 이전 요청의 응답을 버린다
  let generation = 0;
  // 백그라운드 재동기화(refresh)가 actionError 에 넣은 문구. 재동기화가 성공하면 이것만 지운다 —
  // 사용자는 아무것도 하지 않았으니, 스트림이 복구된 뒤에도 오류가 남아 있으면 안 된다.
  // 사용자 동작의 오류는 그 동작을 다시 하거나 새로 읽을 때까지 남긴다.
  let syncError = "";

  function setActionError(message: string): void {
    actionError.value = message;
    syncError = "";
  }

  async function load(): Promise<void> {
    const gen = ++generation;
    disconnect();
    // 이전 잡의 화면을 남기면 새 잡을 읽는 동안 그 화면의 버튼이 새 잡 id 로 요청을 보낸다
    view.value = null;
    loading.value = true;
    notFound.value = false;
    loadError.value = "";
    setActionError("");
    try {
      const job = await research.get(toValue(jobId));
      if (gen !== generation) return;
      view.value = initialResearchView(job);
      connect();
    } catch (e) {
      if (gen !== generation) return;
      view.value = null;
      const status = httpStatus(e);
      if (status === 404 || status === 422) notFound.value = true;
      else loadError.value = researchErrorMessage(e, "연구를 불러오지 못했습니다");
    } finally {
      if (gen === generation) loading.value = false;
    }
  }

  // 서버 상태로 맞췄으면 true
  async function refresh(): Promise<boolean> {
    const gen = generation;
    try {
      const job = await research.get(toValue(jobId));
      if (gen !== generation) return false;
      view.value = refreshView(view.value, job);
      if (syncError && actionError.value === syncError) actionError.value = "";
      syncError = "";
      if (!isTerminalStatus(view.value.status)) connect();
      return true;
    } catch (e) {
      if (gen !== generation) return false;
      const message = researchErrorMessage(e, "최신 상태를 불러오지 못했습니다");
      actionError.value = message;
      syncError = message;
      scheduleReconnect();
      return false;
    }
  }

  function connect(): void {
    if (!import.meta.client || source || !view.value || isTerminalStatus(view.value.status)) return;
    clearReconnect();
    const gen = generation;
    const es = new EventSource(`${streamBase}/${encodeURIComponent(view.value.jobId)}/stream`);
    source = es;
    es.onopen = () => {
      connected.value = true;
      attempts = 0;
    };
    es.onmessage = (msg: MessageEvent<string>) => {
      if (gen !== generation || !view.value) return;
      let event: ResearchEvent;
      try {
        event = JSON.parse(msg.data) as ResearchEvent;
      } catch {
        return;
      }
      view.value = applyResearchEvent(view.value, event);
      if (isTerminalEvent(event)) {
        // 닫지 않으면 EventSource 가 스스로 다시 붙어 snapshot·종료를 끝없이 되받는다.
        // 종료 이벤트에는 보고서가 없으므로 GET 으로 다시 읽는다.
        disconnect();
        void refresh();
        // 사이드바 배지는 30초마다만 다시 읽는다 — 끝난 순간에 한 번 맞춘다
        void history.refresh("research");
      }
    };
    es.onerror = () => {
      connected.value = false;
      // CONNECTING 이면 브라우저가 다시 붙고 서버가 snapshot 부터 보내 화면이 복원된다.
      // CLOSED 는 브라우저가 포기한 경우(오류 응답 등)라 GET 으로 맞춘 뒤 직접 다시 붙인다.
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
      void refresh();
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
    connected.value = false;
  }

  async function act<T>(run: () => Promise<T>, onOk: (res: T) => void, fallback: string): Promise<boolean> {
    if (busy.value || !view.value) return false;
    // 응답을 기다리는 사이 페이지를 떠났거나 주소의 잡이 바뀌었으면 그 응답으로 화면을 건드리지
    // 않는다 — 떠난 뒤의 onOk·refresh 가 connect() 를 부르면 닫을 주체가 없는 EventSource 가
    // 잡이 끝날 때까지 남고, 잡이 바뀐 뒤면 이전 잡의 계획·상태가 새 잡 화면에 섞인다.
    const gen = generation;
    busy.value = true;
    setActionError("");
    try {
      const res = await run();
      // 서버에서는 이미 바뀌었다 — 사이드바 배지는 이 화면이 남아 있든 말든 맞춘다
      void history.refresh("research");
      if (gen !== generation) return false;
      onOk(res);
      return true;
    } catch (e) {
      if (gen !== generation) return false;
      if (httpStatus(e) === 409) {
        // 이미 진행·종료된 잡 — 사유를 보여 주기보다 화면을 서버 상태로 맞추는 게 답이다.
        // 다시 읽기마저 실패하면 refresh 가 넣은 문구를 둔다(맞추지 못했으니).
        const synced = await refresh();
        if (gen !== generation) return false;
        if (synced) setActionError("그 사이 상태가 바뀌어 최신 상태로 맞췄습니다");
      } else {
        setActionError(researchErrorMessage(e, fallback));
      }
      return false;
    } finally {
      busy.value = false;
    }
  }

  const approve = (plan?: string[]) =>
    act(
      () => research.approve(toValue(jobId), plan),
      (res) => {
        if (!view.value) return;
        const planned = res.plan?.length ? withPlan(view.value, res.plan) : view.value;
        view.value = applyResearchEvent(planned, { kind: "status", status: res.status, stage: planned.stage });
        connect();
      },
      "계획을 승인하지 못했습니다",
    );

  const retry = () =>
    act(
      () => research.retry(toValue(jobId)),
      (res) => {
        if (!view.value) return;
        view.value = applyResearchEvent(view.value, { kind: "status", status: res.status, stage: res.stage });
        connect();
      },
      "다시 시도하지 못했습니다",
    );

  const cancel = () =>
    act(
      () => research.cancel(toValue(jobId)),
      () => {
        if (!view.value) return;
        view.value = applyResearchEvent(view.value, { kind: "canceled", status: "canceled" });
        disconnect();
      },
      "취소하지 못했습니다",
    );

  if (getCurrentInstance()) {
    onMounted(() => {
      void load();
    });
    onBeforeUnmount(() => {
      generation += 1;
      disconnect();
    });
  }

  watch(
    () => toValue(jobId),
    (id, old) => {
      if (import.meta.client && id !== old) void load();
    },
  );

  return { view, loading, notFound, loadError, actionError, busy, connected, load, refresh, connect, disconnect, approve, retry, cancel };
}
