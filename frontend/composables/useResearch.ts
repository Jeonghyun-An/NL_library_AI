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
import {
  applyApproval,
  applyQueue,
  applyResearchEvent,
  initialResearchView,
  isTerminalEvent,
  isTerminalStatus,
  refreshView,
  sectionGapToRecover,
  synthClosePending,
} from "~/utils/researchEvents";
import { activeResearchId, httpStatus, researchErrorMessage } from "~/utils/researchErrors";
import { apiUrl, useApi } from "./useApi";
import { useHistory } from "./useHistory";

const RECONNECT_BASE_MS = 2000;
const RECONNECT_MAX_MS = 30000;
// 취소 뒤 워커가 종합 단계를 닫기를 기다리며 다시 읽는 횟수 상한 — 재연결과 같은 간격(2·4·8·16·30·30초,
// 약 1분 반)이다. 쓰던 절 하나를 마저 쓰는 시간(운영에서 수십 초)을 덮고, 워커가 죽어 단계가 끝내 열려
// 있어도 멈춘다 — 그때는 다시 열면 맞는다
const CLOSE_CHECKS_MAX = 6;

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
  // 같은 브라우저의 다른 딥리서치에 막힌 승인·재시도(429 browser_active)면 그 연구 id — 화면이 링크를 단다.
  // actionError 와 함께 바뀐다(setActionError 가 비우고, 막힌 동작의 catch 만 채운다)
  const activeJobId = ref<string | null>(null);
  const busy = ref(false);
  const connected = ref(false);
  // 마지막 GET 재동기화가 실패했는지(다시 시도 대기 중) — 완료 뒤 보고서를 못 받은 화면이
  // 빈 본문 대신 [다시 불러오기] 를 보이게 한다
  const syncFailed = ref(false);
  const syncing = ref(false);

  let source: EventSource | null = null;
  let syncToken = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  // 이 화면에서 잡이 끝난 것을 본 뒤 종합 단계가 닫히기를 기다리며 다시 읽은 횟수 — null 이면 기다리지 않는다
  let closeChecks: number | null = null;
  let closeTimer: ReturnType<typeof setTimeout> | null = null;
  // 저장본으로 다시 맞춘 절 부족분(sectionGapToRecover 의 열쇠) — 같은 부족분으로 GET 을 되풀이하지 않는다
  let recoveredGap: string | null = null;
  // 주소의 잡이 바뀌거나 페이지를 떠난 뒤 도착한 이전 요청의 응답을 버린다
  let generation = 0;
  // 백그라운드 재동기화(refresh)가 actionError 에 넣은 문구. 재동기화가 성공하면 이것만 지운다 —
  // 사용자는 아무것도 하지 않았으니, 스트림이 복구된 뒤에도 오류가 남아 있으면 안 된다.
  // 사용자 동작의 오류는 그 동작을 다시 하거나 새로 읽을 때까지 남긴다.
  let syncError = "";

  function setActionError(message: string): void {
    actionError.value = message;
    activeJobId.value = null;
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
    syncFailed.value = false;
    closeChecks = null;
    recoveredGap = null;
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
    const token = ++syncToken;
    syncing.value = true;
    try {
      const job = await research.get(toValue(jobId));
      // 뒤에 보낸 GET 이 있으면 이 응답은 버린다 — 도는 동안 보낸 GET 이 종료 뒤에 도착해 끝난 화면을
      // 도는 잡으로 되돌리면 재시도로 읽혀(refreshView) 멈춘 초안까지 비운다. 뒤의 GET 이 맞춘다.
      if (gen !== generation || token !== syncToken) return false;
      view.value = refreshView(view.value, job);
      syncFailed.value = false;
      if (syncError && actionError.value === syncError) actionError.value = "";
      syncError = "";
      if (!isTerminalStatus(view.value.status)) connect();
      else awaitSynthClose(view.value);
      return true;
    } catch (e) {
      if (gen !== generation || token !== syncToken) return false;
      const message = researchErrorMessage(e, "최신 상태를 불러오지 못했습니다");
      actionError.value = message;
      activeJobId.value = null;
      syncError = message;
      syncFailed.value = true;
      scheduleReconnect();
      return false;
    } finally {
      if (token === syncToken) syncing.value = false;
    }
  }

  // 사용자가 누른 [다시 불러오기] — 백오프로 잡힌 다음 시도를 기다리지 않고 지금 읽는다
  function resync(): Promise<boolean> {
    clearReconnect();
    attempts = 0;
    return refresh();
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
        settle();
        // 사이드바 배지는 30초마다만 다시 읽는다 — 끝난 순간에 한 번 맞춘다
        void history.refresh("research");
        return;
      }
      // 스냅샷과 구독 사이에 놓친 절 내용은 스트림으로 다시 오지 않는다 — 저장본으로 한 번 맞춘다
      const gap = sectionGapToRecover(view.value, recoveredGap);
      if (gap) {
        recoveredGap = gap;
        void refresh();
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

  // 잡이 끝난 것을 이 화면에서 봤다(종료 이벤트·취소 응답). 스트림을 닫고 — 닫지 않으면 EventSource 가
  // 스스로 다시 붙어 snapshot·종료를 끝없이 되받는다 — 보고서·마지막 저장본을 GET 으로 다시 읽는다.
  // 취소였으면 워커가 종합 단계를 닫을 때까지 이어서 다시 읽는다(awaitSynthClose)
  function settle(): void {
    disconnect();
    closeChecks = 0;
    void refresh();
  }

  function awaitSynthClose(v: ResearchView): void {
    if (closeChecks === null || closeTimer || !synthClosePending(v)) return;
    if (closeChecks >= CLOSE_CHECKS_MAX) {
      closeChecks = null;
      return;
    }
    const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** closeChecks);
    closeChecks += 1;
    closeTimer = setTimeout(() => {
      closeTimer = null;
      void refresh();
    }, delay);
  }

  function disconnect(): void {
    clearReconnect();
    if (closeTimer) clearTimeout(closeTimer);
    closeTimer = null;
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
        activeJobId.value = activeResearchId(e);
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
        // 스트림이 응답보다 먼저 running 을 알렸으면 status 는 그대로 둔다(applyApproval) — 그때는 응답의
        // 순번도 싣지 않는다(applyQueue). 대기 중이면 첫 하트비트(15초)를 기다리지 않고 순번을 보인다
        view.value = applyQueue(applyApproval(view.value, res.status, res.plan), res.queue);
        connect();
      },
      "계획을 승인하지 못했습니다",
    );

  const retry = () =>
    act(
      () => research.retry(toValue(jobId)),
      (res) => {
        if (!view.value) return;
        view.value = applyQueue(
          applyResearchEvent(view.value, { kind: "status", status: res.status, stage: res.stage }),
          res.queue,
        );
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
        // 스트림보다 응답이 먼저 오면 종료 이벤트를 받지 못한다 — 여기서도 종료를 마무리한다
        settle();
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

  return {
    view, loading, notFound, loadError, actionError, activeJobId, busy, connected, syncFailed, syncing,
    load, refresh, resync, connect, disconnect, approve, retry, cancel,
  };
}
