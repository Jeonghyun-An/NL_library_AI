// frontend/composables/useDeepReadChat.ts
import { onScopeDispose, type Ref, ref, watch } from "vue";
import {
  CHAT_ERROR_TEXT,
  CHAT_STOPPED_EMPTY,
  CHAT_STOPPED_TEXT,
  type DeepReadMessage,
  type DeepReadSource,
  parseSse,
} from "~/utils/deepReadSse";
import { apiHeaders, apiUrl } from "./useApi";

export interface DeepReadChatOptions {
  cntsId: () => string;
  // 논문별 대화를 쥐는 곳(연구 화면의 단계 패널 — 06e 정함 20). 있으면 논문을 오갈 때 대화를 이어 쓰고, 없으면 비운다
  store?: () => Map<string, DeepReadMessage[]> | undefined;
  fetchFn?: typeof fetch;
}

export interface DeepReadChat {
  messages: Ref<DeepReadMessage[]>;
  streamingText: Ref<string>;
  isStreaming: Ref<boolean>;
  send(text: string): Promise<void>;
  stop(): void;
}

interface Run {
  ctrl: AbortController;
  list: DeepReadMessage[];
}

// 딥리드 대화의 흐름(BookChat 에서 뺐다 — spec §12-4). 논문(cntsId)이 바뀌면 받던 답을 끊고 그 논문의 대화로 바꾸며,
// 닫히면(scope 끝) 끊는다. 끊은 답은 받은 글 + '멈췄습니다'로 그 논문의 대화에 남는다(06e 정함 21)
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
    const list = messages.value;
    list.push({ role: "user", content: text });
    const history = list.slice(0, -1).map((m) => ({ role: m.role, content: m.content }));
    const run: Run = { ctrl: new AbortController(), list };
    current = run;
    isStreaming.value = true;
    streamingText.value = "";
    let sources: DeepReadSource[] | undefined;
    let failed = false;
    try {
      const fetchFn = opts.fetchFn ?? fetch;
      const resp = await fetchFn(apiUrl(`/books/chat/${opts.cntsId()}`), {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ message: text, history }),
        signal: run.ctrl.signal,
      });
      if (!resp.ok || !resp.body) throw new Error("응답 오류");
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      reading: while (current === run) {
        const { done, value } = await reader.read();
        if (done || current !== run) break;
        const parsed = parseSse(buffer, decoder.decode(value, { stream: true }));
        buffer = parsed.buffer;
        for (const evt of parsed.events) {
          if (evt.type === "done") break reading;
          if (evt.type === "text") streamingText.value += evt.text;
          else sources = evt.sources;
        }
      }
    } catch {
      failed = true;
    }
    // stop() 이 이미 끊고 남겼다(닫기·논문 바꾸기)
    if (current !== run) return;
    current = null;
    run.list.push(
      failed
        ? { role: "assistant", content: CHAT_ERROR_TEXT }
        : { role: "assistant", content: streamingText.value, ...(sources ? { sources } : {}) },
    );
    streamingText.value = "";
    isStreaming.value = false;
  }

  watch(opts.cntsId, (id) => {
    stop();
    messages.value = thread(id);
  });
  onScopeDispose(stop);

  return { messages, streamingText, isStreaming, send, stop };
}
