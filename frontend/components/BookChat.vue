<template>
  <div class="skx-chat-body">
    <div class="skx-chat-messages" ref="messagesEl">
      <!-- 빈 상태 -->
      <div v-if="messages.length === 0 && !isStreaming" class="skx-chat-msg skx-chat-msg--ai">
        안녕하세요! <template v-if="bookTitle">《{{ bookTitle }}》에</template> 대해 궁금한 것을 자유롭게 물어보세요!
      </div>

      <!-- 메시지 목록 -->
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['skx-chat-msg', msg.role === 'user' ? 'skx-chat-msg--user' : 'skx-chat-msg--ai']"
      >
        <div v-html="formatText(msg.content)" />
        <!-- 출처 칩 -->
        <div v-if="msg.sources?.length" class="skx-chat-sources">
          <div class="skx-chat-source-chips">
            <span
              v-for="(src, si) in msg.sources"
              :key="si"
              class="skx-chat-source-chip"
              :class="{ 'is-active': msg.pinnedChip === si }"
              @click="msg.pinnedChip = msg.pinnedChip === si ? undefined : si"
            >
              p.{{ src.page_start }}{{ src.page_end !== src.page_start ? `–${src.page_end}` : '' }}
            </span>
          </div>
          <div v-if="msg.pinnedChip !== undefined" class="skx-chat-source-preview">
            {{ msg.sources[msg.pinnedChip]?.text }}
          </div>
        </div>
      </div>

      <!-- 스트리밍 중 -->
      <template v-if="isStreaming">
        <div v-if="streamingText" class="skx-chat-msg skx-chat-msg--ai">
          <div v-html="formatText(streamingText)" />
        </div>
        <div v-else class="skx-chat-typing">
          <span class="skx-chat-typing__dot"></span>
          <span class="skx-chat-typing__dot"></span>
          <span class="skx-chat-typing__dot"></span>
        </div>
      </template>
    </div>

    <div class="skx-chat-input-wrap">
      <textarea
        ref="inputEl"
        v-model="inputText"
        class="skx-chat-input"
        rows="2"
        placeholder="책에 대해서 자유롭게 질문해보세요!"
        aria-label="책에 대한 질문 입력"
        :disabled="isStreaming"
        @keydown.enter.exact.prevent="send"
        @keydown.enter.shift.exact="() => {}"
      />
      <button
        type="button"
        class="skx-chat-send"
        aria-label="검색"
        :disabled="!inputText.trim() || isStreaming"
        @click="send"
      >
        <img src="/img/ico-send.svg" alt="" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";

const props = defineProps<{
  cntsId: string;
  bookTitle?: string;
}>();
defineEmits<{ (e: "close"): void }>();

interface Source {
  page_start: number;
  page_end: number;
  text: string;
}
interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  pinnedChip?: number;
}

const messages = ref<Message[]>([]);
const inputText = ref("");
const isStreaming = ref(false);
const streamingText = ref("");
const messagesEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);

const config = useRuntimeConfig();
const apiBase = (config.public.apiBase as string) || "";

function formatText(text: string) {
  if (!text) return "";
  return marked.parse(text) as string;
}

function scrollBottom() {
  nextTick(() => {
    if (messagesEl.value)
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
  });
}

async function send() {
  const text = inputText.value.trim();
  if (!text || isStreaming.value) return;

  messages.value.push({ role: "user", content: text });
  inputText.value = "";
  isStreaming.value = true;
  streamingText.value = "";
  scrollBottom();

  const history = messages.value
    .slice(0, -1)
    .map((m) => ({ role: m.role, content: m.content }));

  let pendingSources: Source[] | undefined;

  try {
    const resp = await fetch(`${apiBase}/books/chat/${props.cntsId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history }),
    });

    if (!resp.ok || !resp.body) throw new Error("응답 오류");

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      const lines = buf.split("\n");
      buf = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") break;
        try {
          const evt = JSON.parse(payload);
          if (evt.text) {
            streamingText.value += evt.text;
            scrollBottom();
          } else if (evt.sources) {
            pendingSources = evt.sources;
          }
        } catch {}
      }
    }
  } catch {
    streamingText.value = "오류가 발생했습니다. 다시 시도해주세요.";
  }

  messages.value.push({
    role: "assistant",
    content: streamingText.value,
    sources: pendingSources,
  });
  streamingText.value = "";
  isStreaming.value = false;
  scrollBottom();
  nextTick(() => inputEl.value?.focus());
}
</script>
