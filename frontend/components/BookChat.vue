<template>
  <div class="skx-chat-body">
    <div class="skx-chat-messages" ref="messagesEl">
      <!-- 빈 상태 -->
      <div v-if="messages.length === 0 && !isStreaming" class="skx-chat-msg skx-chat-msg--ai">
        {{ copy.greeting(bookTitle) }}
      </div>

      <!-- 메시지 목록 -->
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['skx-chat-msg', msg.role === 'user' ? 'skx-chat-msg--user' : 'skx-chat-msg--ai']"
      >
        <div v-html="formatText(msg.content)" />
        <!-- 출처 칩 — 누르면 그 대목을 아래에 펼치고 다시 누르면 접는다(키보드로도 누른다). 원문 열기는 펼친 대목 아래
             [원문 보기]이고 pdfLinks 인 곳(연구 화면 오른쪽 패널)에만 둔다 — 기존 네 화면은 지금처럼 미리보기만 -->
        <div v-if="msg.sources?.length" class="skx-chat-sources">
          <div class="skx-chat-source-chips">
            <button
              v-for="(src, si) in msg.sources"
              :key="si"
              type="button"
              class="skx-chat-source-chip"
              :class="{ 'is-active': msg.pinnedChip === si }"
              :aria-pressed="msg.pinnedChip === si"
              @click="msg.pinnedChip = msg.pinnedChip === si ? undefined : si"
            >
              {{ sourceLabel(src) }}<span class="skx-sr-only"> 대목 보기</span>
            </button>
          </div>
          <div v-if="msg.pinnedChip !== undefined" class="skx-chat-source-preview">
            {{ msg.sources[msg.pinnedChip]?.text }}
          </div>
          <button
            v-if="pdfLinks && pinnedSource(msg)"
            type="button"
            class="rs-btn rs-btn--small rs-btn--ghost skx-chat-source-open"
            @click="openSource(msg)"
          >
            원문 보기
          </button>
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
    <!-- 화면낭독기용 — 방금 보낸 질문의 답을 다 받으면 한 번 읽는다. 흐르는 글은 토막마다 읽히지 않게 싣지 않는다 -->
    <div class="skx-sr-only" aria-live="polite" v-html="liveHtml" />

    <div class="skx-chat-input-wrap">
      <textarea
        ref="inputEl"
        v-model="inputText"
        class="skx-chat-input"
        rows="2"
        :placeholder="copy.placeholder"
        :aria-label="copy.inputLabel"
        :disabled="isStreaming"
        @keydown.enter.exact.prevent="send"
        @keydown.enter.shift.exact="() => {}"
      />
      <button
        type="button"
        class="skx-chat-send"
        :aria-label="copy.sendLabel"
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
import { computed, nextTick, ref, watch } from "vue";
import { useDeepReadChat } from "~/composables/useDeepReadChat";
import type { OpenPdfPayload } from "~/types/research";
import { type DocKind, chatCopy, sourceLabel, sourcePdfTarget } from "~/utils/deepRead";
import type { DeepReadMessage, DeepReadSource } from "~/utils/deepReadSse";

// 딥리드 대화 칸 — 논문 상세·논문 검색 결과 채팅·도서 상세·TopResult 와 연구 화면의 오른쪽 패널(06e)이 함께 쓴다.
// 대화 흐름(보내기·스트림 읽기·끊기·논문별 대화)은 useDeepReadChat 이 맡고 여기서는 그리기·입력·스크롤만 한다.
// store 를 넘기면(연구 화면 패널) 논문을 오갈 때 대화가 이어지고, 없으면 논문이 바뀔 때 비운다.
// docKind 는 문구(책/논문), pdfLinks 는 출처 대목의 [원문 보기](open-pdf 로 부르는 쪽의 원문 뷰어를 연다)
const props = withDefaults(
  defineProps<{
    cntsId: string;
    bookTitle?: string;
    store?: Map<string, DeepReadMessage[]>;
    docKind?: DocKind;
    pdfLinks?: boolean;
  }>(),
  { docKind: "book", pdfLinks: false },
);
const emit = defineEmits<{ close: []; "open-pdf": [payload: OpenPdfPayload] }>();

const copy = computed(() => chatCopy(props.docKind));

const { messages, streamingText, isStreaming, send: sendChat } = useDeepReadChat({
  cntsId: () => props.cntsId,
  store: () => props.store,
});
const inputText = ref("");
const messagesEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);
// 화면낭독기가 읽을 끝난 답(HTML) — 방금 보낸 질문의 답만 싣는다(논문을 바꿔 다른 대화를 펼칠 때 옛 답을 다시 읽지 않게)
const liveHtml = ref("");

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

// 질문·답이 쌓이거나 글이 흐르거나 다른 논문의 대화로 바뀌면 맨 아래로
watch([messages, () => messages.value.length, streamingText], scrollBottom);

async function send() {
  const text = inputText.value.trim();
  if (!text || isStreaming.value) return;
  inputText.value = "";
  liveHtml.value = "";
  const sentFor = props.cntsId;
  await sendChat(text);
  // 답을 다 받았을 때만 읽고 입력 칸으로 돌아간다 — 논문을 바꿔 끊긴 경우 초점은 사용자가 누른 곳에 둔다
  if (props.cntsId !== sentFor) return;
  const last = messages.value.at(-1);
  if (last?.role === "assistant") liveHtml.value = formatText(last.content);
  nextTick(() => inputEl.value?.focus());
}

// 펼친 출처 대목 — 없으면 null
function pinnedSource(msg: DeepReadMessage): DeepReadSource | null {
  return msg.pinnedChip === undefined ? null : (msg.sources?.[msg.pinnedChip] ?? null);
}

function openSource(msg: DeepReadMessage): void {
  const src = pinnedSource(msg);
  if (src) emit("open-pdf", sourcePdfTarget(props.cntsId, props.bookTitle || props.cntsId, src));
}
</script>
