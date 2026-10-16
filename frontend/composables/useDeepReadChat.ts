// frontend/composables/useDeepReadChat.ts
import { onScopeDispose, type Ref, ref, watch } from "vue";
import {
  CHAT_ERROR_TEXT,
  CHAT_IDLE_TIMEOUT_MS,
  CHAT_STOPPED_EMPTY,
  CHAT_STOPPED_TEXT,
  CHAT_TIMEOUT_FAILURE,
  type ChatFailureCopy,
  type DeepReadMessage,
  type DeepReadSource,
  finishedAnswerCode,
  parseSse,
  requestFailure,
  streamFailure,
} from "~/utils/deepReadSse";
import { apiHeaders, apiUrl } from "./useApi";

export interface DeepReadChatOptions {
  cntsId: () => string;
  // 논문별 대화를 쥐는 곳(연구 화면의 단계 패널 — 06e 정함 20). 있으면 논문을 오갈 때 대화를 이어 쓰고, 없으면 비운다
  store?: () => Map<string, DeepReadMessage[]> | undefined;
  fetchFn?: typeof fetch;
}

// 답을 받지 못한 질문과 보일 문구(ChatFailureCopy — 까닭별 화면 문구와 [다시 시도]를 보일지), 실패 전까지 받던 글(partial — 없으면 "").
// 질문도 오류도 받던 글도 대화(messages·store)에는 남기지 않는다 — 남기면 오류 문구·끊긴 답이 답처럼 굳고 다음 질문의
// history 로 모델에게까지 간다. 받던 글은 실패 안내에만 둔다: 다른 AI 글 화면(논문 검색·상세 요약·추천 이유)처럼 읽던 글이
// 실패 순간 사라지지 않게. 다음 질문·[다시 시도]·논문 바꾸기가 failure 와 함께 걷는다
export interface DeepReadFailure extends ChatFailureCopy {
  question: string;
  partial: string;
}

export interface DeepReadChat {
  messages: Ref<DeepReadMessage[]>;
  streamingText: Ref<string>;
  isStreaming: Ref<boolean>;
  failure: Ref<DeepReadFailure | null>;
  send(text: string): Promise<void>;
  // 실패한 질문을 그대로 다시 보낸다 — 실패가 없거나 다시 보내도 같은 실패인 경우(retryable 아님)면 아무것도 하지 않는다
  retry(): Promise<void>;
  // 받던 답을 끊는다([멈춤]·닫기·논문 바꾸기) — 받은 글은 '멈췄어요' 꼬리와 대화에 남는다
  stop(): void;
}

interface Run {
  ctrl: AbortController;
  list: DeepReadMessage[];
}

// 오류 응답(4xx·5xx)을 $fetch 의 FetchError 처럼 status·data(JSON 본문 — 아니면 undefined)를 단 오류로 — apiErrorMessage 가 읽는다
async function responseError(resp: Response): Promise<Error> {
  const data: unknown = await resp.json().catch(() => undefined);
  return Object.assign(new Error(`DeepRead 응답 ${resp.status}`), { status: resp.status, data });
}

// 딥리드 대화의 흐름(BookChat 에서 뺐다 — spec §12-4). 논문(cntsId)이 바뀌면 받던 답을 끊고 그 논문의 대화로 바꾸며,
// 닫히면(scope 끝) 끊는다. 끊은 답은 받은 글 + '멈췄어요'로 그 논문의 대화에 남는다(06e 정함 21).
// 답을 받지 못하면({error}·4xx·5xx·네트워크 오류·[DONE] 없이 끊김·오래 무응답·옛 서버의 빈 답과 '도서를 찾을 수 없습니다.') 받던 글과
// 질문을 대화에서 빼 failure 로 알린다(받던 글은 failure.partial) — user/assistant 짝은 그대로이고, 화면이 [다시 시도](retry)로 같은
// 질문을 다시 보낸다
export function useDeepReadChat(opts: DeepReadChatOptions): DeepReadChat {
  // store 가 있으면 그 논문의 배열을 그대로 쥔다 — messages 에 쓰는 것이 곧 store 에 남는다
  function thread(id: string): DeepReadMessage[] {
    const store = opts.store?.();
    if (!store) return [];
    let list = store.get(id);
    if (!list) {
      list = [];
      store.set(id, list);
    }
    return list;
  }

  const messages = ref<DeepReadMessage[]>(thread(opts.cntsId()));
  const streamingText = ref("");
  const isStreaming = ref(false);
  const failure = ref<DeepReadFailure | null>(null);
  // 지금 받는 답 — 끊긴 뒤 늦게 끝난 읽기가 다음 답의 상태를 건드리지 않게 이것과 견준다
  let current: Run | null = null;

  function stop(): void {
    const run = current;
    if (!run) return;
    current = null;
    run.ctrl.abort();
    const got = streamingText.value;
    run.list.push({ role: "assistant", content: got ? `${got}\n\n${CHAT_STOPPED_TEXT}` : CHAT_STOPPED_EMPTY });
    streamingText.value = "";
    isStreaming.value = false;
  }

  async function send(raw: string): Promise<void> {
    const text = raw.trim();
    if (!text || current) return;
    failure.value = null;
    const list = messages.value;
    const asked: DeepReadMessage = { role: "user", content: text };
    list.push(asked);
    const history = list.slice(0, -1).map((m) => ({ role: m.role, content: m.content }));
    const run: Run = { ctrl: new AbortController(), list };
    current = run;
    isStreaming.value = true;
    streamingText.value = "";
    let sources: DeepReadSource[] | undefined;
    // [DONE] 까지 정상 답을 받았는지 — 못 받았으면 실패다. 실패의 문구는 까닭을 안 곳에서 정하고, 모르면(끊김) CHAT_ERROR_TEXT
    let finished = false;
    let failed: ChatFailureCopy | null = null;
    // 아무 데이터 없이 CHAT_IDLE_TIMEOUT_MS 가 지나면 스스로 끊는다 — 응답 머리를 기다리는 동안도, 글 조각 사이도. 조각이 올 때마다
    // 다시 센다. 끊으면 기다리던 fetch·읽기가 AbortError 로 catch 에 간다(timedOut 으로 [멈춤]·닫기와 가른다)
    let timedOut = false;
    let idleTimer: ReturnType<typeof setTimeout> | undefined;
    const armIdle = () => {
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => {
        timedOut = true;
        run.ctrl.abort();
      }, CHAT_IDLE_TIMEOUT_MS);
    };
    try {
      armIdle();
      const fetchFn = opts.fetchFn ?? fetch;
      const resp = await fetchFn(apiUrl(`/books/chat/${opts.cntsId()}`), {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ message: text, history }),
        signal: run.ctrl.signal,
      });
      if (!resp.ok || !resp.body) throw await responseError(resp);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      reading: while (current === run) {
        const { done, value } = await reader.read();
        if (done || current !== run) break;
        armIdle();
        const parsed = parseSse(buffer, decoder.decode(value, { stream: true }));
        buffer = parsed.buffer;
        for (const evt of parsed.events) {
          if (evt.type === "error") {
            failed = streamFailure(evt.code);
            break reading;
          }
          if (evt.type === "done") {
            // 옛 서버의 빈 답·'도서를 찾을 수 없습니다.' 는 [DONE] 으로 끝나도 실패다 — 그 글은 받던 글(partial)로도 보이지 않는다
            const code = finishedAnswerCode(streamingText.value);
            if (code) {
              failed = streamFailure(code);
              streamingText.value = "";
            } else finished = true;
            break reading;
          }
          if (evt.type === "text") streamingText.value += evt.text;
          else sources = evt.sources;
        }
      }
      // 일찍 끝낸 읽기({error})는 연결을 끊는다 — 이미 닫힌 스트림의 취소 실패는 무시한다
      void reader.cancel().catch(() => undefined);
    } catch (err) {
      // 4xx·5xx·네트워크 오류·스스로 끊음(무응답). [멈춤]·닫기로 끊긴 것(current 가 바뀜)은 아래에서 조용히 끝난다
      failed = timedOut ? CHAT_TIMEOUT_FAILURE : requestFailure(err);
    } finally {
      clearTimeout(idleTimer);
    }
    // stop() 이 이미 끊고 남겼다(닫기·논문 바꾸기·[멈춤])
    if (current !== run) return;
    current = null;
    if (finished) {
      run.list.push({ role: "assistant", content: streamingText.value, ...(sources ? { sources } : {}) });
    } else {
      // 받던 글은 대화에 넣지 않고 질문도 대화에서 뺀다 — 오류가 답처럼 굳거나 다음 질문의 history 에 실리지 않게.
      // 받던 글은 실패 안내에만 남긴다
      const at = run.list.lastIndexOf(asked);
      if (at >= 0) run.list.splice(at, 1);
      const copy = failed ?? { message: CHAT_ERROR_TEXT, retryable: true };
      failure.value = { question: text, message: copy.message, retryable: copy.retryable, partial: streamingText.value };
    }
    streamingText.value = "";
    isStreaming.value = false;
  }

  async function retry(): Promise<void> {
    if (!failure.value?.retryable || current) return;
    await send(failure.value.question);
  }

  watch(opts.cntsId, (id) => {
    stop();
    failure.value = null;
    messages.value = thread(id);
  });
  onScopeDispose(stop);

  return { messages, streamingText, isStreaming, failure, send, retry, stop };
}
