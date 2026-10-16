// frontend/composables/useResearch.ts
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, ref, shallowRef, toValue, watch, type MaybeRefOrGetter } from "vue";
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
import { errorKind, httpStatus, type UserFacingError } from "~/utils/apiErrors";
import {
  LOST_AFTER_DROPS,
  RESEARCH_STATE_TEXT,
  activeResearchId,
  researchConnectionState,
  researchErrorMessage,
} from "~/utils/researchErrors";
import { researchStartState, startNotice } from "~/utils/researchStart";
import { apiUrl, useApi } from "./useApi";
import { useHistory } from "./useHistory";

const RECONNECT_BASE_MS = 2000;
const RECONNECT_MAX_MS = 30000;
// 취소 뒤 워커가 종합 단계를 닫기를 기다리며 다시 읽는 횟수 상한 — 재연결과 같은 간격(2·4·8·16·30·30초,
// 약 1분 반)이다. 쓰던 절 하나를 마저 쓰는 시간(운영에서 수십 초)을 덮고, 워커가 죽어 단계가 끝내 열려
// 있어도 멈춘다 — 그때는 화면이 '아직 정리되지 않았어요' 한 줄과 [다시 불러오기]를 보인다(closeWaitEnded)
const CLOSE_CHECKS_MAX = 6;
// 스트림이 이만큼 아무것도 받지 못하면 조용히 죽은 연결(절전 복귀·NAT 만료 — onerror 가 오지 않는다)로 보고 닫은 뒤 다시 붙는다.
// 서버는 이벤트가 없어도 15초마다 하트비트(이름 붙은 'ping' 이벤트 — relay.SSE_PING)를 보내고 ping 리스너가 이 시계만 다시 건다 —
// 승인 대기·대기열처럼 이벤트가 없는 동안에도 살아 있는 연결을 끊지 않는다(세 번 연달아 놓쳐야 끊는다). 하트비트가 주석 줄(': ping')인
// 옛 서버에서는 EventSource 가 알리지 않아 이 간격으로 다시 붙고, 서버가 붙자마자 보내는 snapshot 이 화면을 맞추며 시계를 다시 건다.
// 다시 붙는 것만으로는 띠를 띄우지 않는다
const STREAM_QUIET_MS = 45_000;

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

// DeepResearch 를 시작하는 입력창(+ 메뉴 — SearchPlusMenu)이 쓰는 판단은 여기 한 곳이다 — 시작 요청(startResearch — 기록도 남긴다),
// DeepResearch 모드일 때 입력창의 한 줄(notice — 이 브라우저 기록의 끝나지 않은 연구, utils/researchStart)과 그 줄의 [취소]
// (cancelResearch). 사이드바 [+ 연구 시작하기]는 끝나지 않은 연구가 있어도 늘 메인에서 새 연구를 시작한다(사용자 결정 2026-10-13).
// 서버의 승인 429 browser_active 는 그대로 마지막 안전망이다
export function useResearchStarter() {
  const research = useResearchApi();
  const history = useHistory();
  const notice = computed(() => startNotice(researchStartState(history.entries.value)));

  // params 는 잡 파라미터(서버 merge_params 가 검증) — 탐색 방식의 두 칸(broaden·query_context)을 싣는다. 없으면 서버 기본값
  async function startResearch(question: string, params?: ResearchParams): Promise<string> {
    const { job_id } = await research.create(question, params);
    try {
      await history.upsertResearch(job_id, question);
    } catch (e) {
      // 잡은 이미 만들어졌다 — 기록 저장 실패로 멈추면 돌고 있는 잡의 주소를 잃는다
      console.warn("[research] 기록 저장 실패", e);
    }
    return job_id;
  }

  // 입력창 한 줄의 [취소] — 기존 취소 API 로 그 연구를 멈추고 기록을 다시 읽는다(이 줄과 사이드바 배지가 함께 바뀐다). 그새 끝나
  // 취소할 수 없어도(409) 기록을 다시 읽어 낡은 줄을 걷는다. 실패는 그대로 던진다 — 부르는 쪽이 문구를 보인다
  async function cancelResearch(jobId: string): Promise<void> {
    try {
      await research.cancel(jobId);
    } finally {
      await history.refresh("research");
    }
  }

  return { startResearch, notice, cancelResearch };
}

export function useResearchJob(jobId: MaybeRefOrGetter<string>) {
  const research = useResearchApi();
  const history = useHistory();
  const streamBase = apiUrl("/research");

  const view = shallowRef<ResearchView | null>(null);
  const loading = ref(false);
  const notFound = ref(false);
  // 첫 로드 실패(404·422 밖) — kind 는 상태 블록(SkxErrorState)의 모양, message 는 제목('연구를 불러오지 못했어요') 아래 이유(없으면 빈 글)
  const loadError = ref<UserFacingError | null>(null);
  const actionError = ref("");
  // 같은 브라우저의 다른 딥리서치에 막힌 승인·재시도(429 browser_active)면 그 연구 id — 화면이 링크를 단다.
  // actionError 와 함께 바뀐다(setActionError 가 비우고, 막힌 동작의 catch 만 채운다)
  const activeJobId = ref<string | null>(null);
  const busy = ref(false);
  const connected = ref(false);
  // 마지막으로 붙거나 받은 뒤 쌓인 연결 실패 수(스트림 onerror·끝나지 않은 잡의 재동기화 GET 실패) — 연결 띠의 상태(connState)가 읽는다
  const drops = ref(0);
  // 마지막 GET 재동기화가 실패했는지(다시 시도 대기 중) — 완료 뒤 보고서를 못 받은 화면이
  // 빈 본문 대신 [다시 불러오기] 를 보이게 한다
  const syncFailed = ref(false);
  const syncing = ref(false);
  // 취소 뒤 종합 단계가 닫히기를 기다리다 상한(CLOSE_CHECKS_MAX)에 닿았다 — 단계가 아직 열려 있는 동안만 화면이 한 줄 알린다
  const closeWaitGaveUp = ref(false);

  let source: EventSource | null = null;
  let syncToken = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let quietTimer: ReturnType<typeof setTimeout> | null = null;
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
  // 마지막 재동기화가 실패한 문구(성공하면 비운다) — 409 뒤 다시 읽기마저 실패한 동작이 그 문구를 띄운다
  let lastSyncMessage = "";

  // 스트림이 있어야 하는 잡인가 — 끝나지 않은 잡. 연결 띠와 재동기화 실패를 어디에 알릴지(띠·오류 줄)가 이것으로 갈린다
  function streaming(): boolean {
    return !!view.value && !isTerminalStatus(view.value.status);
  }

  const connState = computed(() => researchConnectionState(streaming(), drops.value));
  // 취소한 잡의 종합 단계가 기다린 끝에도 아직 열려 있다 — 다시 읽어 닫혔으면 스스로 걷힌다
  const closeWaitEnded = computed(() => closeWaitGaveUp.value && !!view.value && synthClosePending(view.value));

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
    loadError.value = null;
    syncFailed.value = false;
    drops.value = 0;
    closeChecks = null;
    closeWaitGaveUp.value = false;
    recoveredGap = null;
    lastSyncMessage = "";
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
      else loadError.value = { kind: errorKind(e), message: researchErrorMessage(e, "") };
    } finally {
      if (gen === generation) loading.value = false;
    }
  }

  // 보던 연구가 사라졌다(재동기화 GET 404 — 연구를 지우는 API 는 없어 운영자가 DB 에서 지운 경우). 첫 로드처럼 '찾을 수 없는 연구'
  // 화면으로 바꾸고 스트림·예약된 재동기화·종합 단계 기다리기를 모두 멈춘다. 세대를 올려 늦게 오는 응답(동작·GET)도 버린다
  function markGone(): void {
    generation += 1;
    disconnect();
    view.value = null;
    notFound.value = true;
    syncFailed.value = false;
    drops.value = 0;
    closeChecks = null;
    closeWaitGaveUp.value = false;
    lastSyncMessage = "";
    setActionError("");
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
      lastSyncMessage = "";
      if (syncError && actionError.value === syncError) actionError.value = "";
      syncError = "";
      // 끝나지 않은 잡은 다시 붙고, 붙어 열려야(onopen) 연결 띠가 걷힌다. 끝난 잡은 스트림이 필요 없어 실패 수를 지운다 — 남기면
      // 재시도로 다시 돌 때 붙기도 전에 '다시 연결하는 중'이 선다
      if (!isTerminalStatus(view.value.status)) connect();
      else {
        drops.value = 0;
        awaitSynthClose(view.value);
      }
      return true;
    } catch (e) {
      if (gen !== generation || token !== syncToken) return false;
      const status = httpStatus(e);
      if (status === 404 || status === 422) {
        markGone();
        return false;
      }
      const message = researchErrorMessage(e, "최신 상태를 불러오지 못했어요");
      lastSyncMessage = message;
      syncFailed.value = true;
      if (streaming()) {
        // 실시간으로 따라가는 잡이면 연결 띠가 알린다(다시 연결하는 중 → 거듭 실패하면 연결하지 못했어요 + [다시 연결]) —
        // 같은 일을 오류 줄로 한 번 더 말하지 않는다
        drops.value += 1;
      } else {
        actionError.value = message;
        activeJobId.value = null;
        syncError = message;
      }
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

  // 연결 띠의 [다시 연결] — 브라우저가 붙들고 다시 붙던 옛 연결은 버리고, GET 으로 화면을 맞춘 뒤 새로 붙는다(refresh → connect).
  // 띠는 '다시 연결하는 중'으로 돌리고, 한 번 더 실패하면 바로 '연결하지 못했어요'로 돌아온다
  function reconnect(): void {
    closeStream();
    drops.value = Math.min(drops.value, LOST_AFTER_DROPS - 1);
    void resync();
  }

  // 받은 것이 있다 — 연결은 살아 있다. 실패 수를 지우고 조용함 감시를 다시 건다
  function heard(es: EventSource): void {
    connected.value = true;
    drops.value = 0;
    armQuietWatch(es);
  }

  function armQuietWatch(es: EventSource): void {
    clearQuietWatch();
    quietTimer = setTimeout(() => {
      quietTimer = null;
      if (source !== es) return;
      // 조용히 죽었을 수 있는 연결 — 닫고 새로 붙는다. 서버가 붙자마자 snapshot 을 보내 그새 놓친 것도 맞춘다
      closeStream();
      connect();
    }, STREAM_QUIET_MS);
  }

  function clearQuietWatch(): void {
    if (quietTimer) clearTimeout(quietTimer);
    quietTimer = null;
  }

  function connect(): void {
    if (!import.meta.client || source || !view.value || isTerminalStatus(view.value.status)) return;
    clearReconnect();
    const gen = generation;
    const es = new EventSource(`${streamBase}/${encodeURIComponent(view.value.jobId)}/stream`);
    source = es;
    armQuietWatch(es);
    es.onopen = () => {
      if (source !== es) return;
      heard(es);
      attempts = 0;
    };
    // 하트비트 — 연결이 살아 있다는 것만 알린다. 조용함 감시 시계만 다시 걸고 화면 상태(view)는 건드리지 않는다
    // (이름 붙은 이벤트라 onmessage 에는 오지 않는다)
    es.addEventListener("ping", () => {
      if (source !== es) return;
      armQuietWatch(es);
    });
    es.onmessage = (msg: MessageEvent<string>) => {
      if (gen !== generation || !view.value || source !== es) return;
      heard(es);
      let event: ResearchEvent;
      try {
        event = JSON.parse(msg.data) as ResearchEvent;
      } catch {
        // 읽지 못한 이벤트(상태 변화·순번 등)는 다시 오지 않는다 — 버리지 않고 저장본으로 한 번 맞춘다(도는 GET 이 있으면 그것이 맞춘다)
        if (!syncing.value) void refresh();
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
      if (source !== es) return;
      connected.value = false;
      // 끊겼다 — 연결 띠가 '다시 연결하는 중'으로, 거듭되면 '연결하지 못했어요'로 알린다
      drops.value += 1;
      // CONNECTING 이면 브라우저가 다시 붙고 서버가 snapshot 부터 보내 화면이 복원된다.
      // CLOSED 는 브라우저가 포기한 경우(오류 응답 등)라 GET 으로 맞춘 뒤 직접 다시 붙인다.
      if (es.readyState !== EventSource.CLOSED) return;
      clearQuietWatch();
      source = null;
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
    drops.value = 0;
    closeChecks = 0;
    closeWaitGaveUp.value = false;
    void refresh();
  }

  function awaitSynthClose(v: ResearchView): void {
    if (closeChecks === null || closeTimer || !synthClosePending(v)) return;
    if (closeChecks >= CLOSE_CHECKS_MAX) {
      // 기다리기를 그만둔다 — 조용히 끝내지 않고 화면이 한 줄 알린다(closeWaitEnded). [다시 불러오기]가 한 번씩 더 읽는다
      closeChecks = null;
      closeWaitGaveUp.value = true;
      return;
    }
    const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** closeChecks);
    closeChecks += 1;
    closeTimer = setTimeout(() => {
      closeTimer = null;
      void refresh();
    }, delay);
  }

  // 스트림만 닫는다 — 예약된 재동기화·종합 단계 기다리기는 그대로 둔다
  function closeStream(): void {
    clearQuietWatch();
    source?.close();
    source = null;
    connected.value = false;
  }

  function disconnect(): void {
    clearReconnect();
    if (closeTimer) clearTimeout(closeTimer);
    closeTimer = null;
    closeStream();
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
        // 다시 읽기마저 실패하면 그 문구를 둔다(맞추지 못했으니) — 다음 재동기화가 성공하면 걷힌다.
        const synced = await refresh();
        if (gen !== generation) return false;
        if (synced) setActionError(RESEARCH_STATE_TEXT.stateChanged);
        else if (lastSyncMessage) {
          setActionError(lastSyncMessage);
          syncError = lastSyncMessage;
        }
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
      "계획을 승인하지 못했어요",
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
      "다시 시도하지 못했어요",
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
      "취소하지 못했어요",
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
    view, loading, notFound, loadError, actionError, activeJobId, busy, connected, connState, syncFailed, syncing,
    closeWaitEnded, load, refresh, resync, reconnect, connect, disconnect, approve, retry, cancel,
  };
}
