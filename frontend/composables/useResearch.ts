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

  async function load(): Promise<void> {
    const gen = ++generation;
    disconnect();
    loading.value = true;
    notFound.value = false;
    loadError.value = "";
    actionError.value = "";
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

  async function refresh(): Promise<void> {
    const gen = generation;
    try {
      const job = await research.get(toValue(jobId));
      if (gen !== generation) return;
      view.value = refreshView(view.value, job);
      if (!isTerminalStatus(view.value.status)) connect();
    } catch (e) {
      if (gen !== generation) return;
      actionError.value = researchErrorMessage(e, "최신 상태를 불러오지 못했습니다");
      scheduleReconnect();
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
    busy.value = true;
    actionError.value = "";
    try {
      onOk(await run());
      void history.refresh("research");
      return true;
    } catch (e) {
      if (httpStatus(e) === 409) {
        // 이미 진행·종료된 잡 — 사유를 보여 주기보다 화면을 서버 상태로 맞추는 게 답이다
        await refresh();
        actionError.value = "그 사이 상태가 바뀌어 최신 상태로 맞췄습니다";
      } else {
        actionError.value = researchErrorMessage(e, fallback);
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
