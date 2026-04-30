<template>
  <div class="book-chat">
    <div class="chat-header">
      <img src="/ai_orb.svg" class="chat-orb" alt="" />
      <span class="chat-title">이 책과 대화하기</span>
      <button class="icon-btn" :title="expanded ? '축소' : '확장'" @click="expanded = !expanded">
        <!-- 확장 아이콘 -->
        <svg v-if="!expanded" width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path d="M10 2h4v4M6 14H2v-4M14 2l-5 5M2 14l5-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <!-- 축소 아이콘 -->
        <svg v-else width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path d="M14 6h-4V2M2 10h4v4M10 6l4-4M6 10l-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      <button class="icon-btn" title="닫기" @click="$emit('close')">✕</button>
    </div>

    <div class="messages-wrap" :class="{ expanded }" ref="messagesEl">
      <div v-if="messages.length === 0" class="empty-hint">
        책의 내용에 대해 무엇이든 질문해보세요.
      </div>

      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="msg-row"
        :class="msg.role"
      >
        <div class="bubble" :class="msg.role">
          <div v-html="formatText(msg.content)" />
          <!-- 출처 칩 -->
          <div v-if="msg.sources?.length" class="source-chips">
            <span
              v-for="(src, si) in msg.sources"
              :key="si"
              class="source-chip"
            >
              p.{{ src.page_start }}–{{ src.page_end }}
            </span>
          </div>
        </div>
      </div>

      <!-- 스트리밍 중 빈 AI 버블 -->
      <div v-if="isStreaming" class="msg-row assistant">
        <div class="bubble assistant">
          <div v-html="formatText(streamingText)" />
          <span class="cursor" />
        </div>
      </div>
    </div>

    <div class="input-area">
      <textarea
        ref="inputEl"
        v-model="inputText"
        class="chat-input"
        placeholder="질문을 입력하세요..."
        rows="2"
        :disabled="isStreaming"
        @keydown.enter.exact.prevent="send"
        @keydown.enter.shift.exact="() => {}"
      />
      <button
        class="send-btn"
        :disabled="!inputText.trim() || isStreaming"
        @click="send"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M14 8L2 2l2.5 6L2 14l12-6z" fill="currentColor" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";

const props = defineProps<{ cntsId: string }>();
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
}

const messages = ref<Message[]>([]);
const inputText = ref("");
const isStreaming = ref(false);
const streamingText = ref("");
const expanded = ref(false);
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
  } catch (err) {
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

<style scoped>
.book-chat {
  display: flex;
  flex-direction: column;
  border: 1px solid oklch(0.88 0.05 277);
  border-radius: var(--radius);
  background: #fff;
  overflow: hidden;
  margin-top: 12px;
}

/* 헤더 */
.chat-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: radial-gradient(
    120% 100% at 0% 0%,
    oklch(0.95 0.05 277) 0%,
    oklch(0.98 0.02 317) 60%,
    #fff 100%
  );
  border-bottom: 1px solid oklch(0.9 0.04 277);
}

.chat-orb {
  width: 24px;
  height: 24px;
  filter: drop-shadow(0 0 5px oklch(0.7 0.18 277 / 0.4));
}

.chat-title {
  font-size: 13px;
  font-weight: 600;
  color: oklch(0.32 0.15 277);
  flex: 1;
  letter-spacing: -0.01em;
}

.icon-btn {
  background: none;
  border: none;
  font-size: 14px;
  color: var(--ink-3);
  cursor: pointer;
  padding: 4px 5px;
  line-height: 1;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}
.icon-btn:hover {
  background: var(--line-2);
  color: var(--ink);
}

/* 메시지 영역 */
.messages-wrap {
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 300px;
  transition: height 0.3s ease;
}

.messages-wrap.expanded {
  height: 620px;
}

.empty-hint {
  text-align: center;
  font-size: 13px;
  color: var(--ink-3);
  margin: auto 0;
  padding: 20px 0;
}

.msg-row {
  display: flex;
}
.msg-row.user {
  justify-content: flex-end;
}
.msg-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 82%;
  padding: 10px 13px;
  border-radius: 12px;
  font-size: 13.5px;
  line-height: 1.65;
  word-break: break-word;
}

.bubble.user {
  background: var(--ink);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble.assistant {
  background: radial-gradient(
    120% 120% at 0% 0%,
    oklch(0.96 0.04 277) 0%,
    oklch(0.98 0.02 317) 60%,
    #fff 100%
  );
  border: 1px solid oklch(0.9 0.04 277);
  color: var(--ink-2);
  border-bottom-left-radius: 4px;
}

.bubble :deep(p) {
  margin: 0 0 6px 0;
}
.bubble :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble :deep(strong) {
  font-weight: 600;
}
.bubble :deep(ul),
.bubble :deep(ol) {
  padding-left: 1.2em;
  margin: 4px 0 6px;
}

/* 깜빡이는 커서 */
.cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: oklch(0.55 0.18 277);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.9s step-end infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* 출처 칩 */
.source-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}

.source-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 99px;
  background: #fff;
  border: 1px solid oklch(0.88 0.05 277);
  color: oklch(0.4 0.12 277);
  font-weight: 500;
}

/* 입력 영역 */
.input-area {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid var(--line);
  background: var(--line-2);
}

.chat-input {
  flex: 1;
  resize: none;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px 11px;
  font-size: 13.5px;
  font-family: inherit;
  line-height: 1.5;
  color: var(--ink);
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
}
.chat-input:focus {
  border-color: oklch(0.72 0.14 277);
}
.chat-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-btn {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 8px;
  background: var(--ink);
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.15s;
}
.send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.send-btn:not(:disabled):hover {
  opacity: 0.82;
}
</style>
