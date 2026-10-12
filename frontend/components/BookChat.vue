<template>
  <div class="skx-chat-body">
    <div class="skx-chat-messages" ref="messagesEl">
      <!-- 빈 상태 -->
      <div v-if="messages.length === 0 && !isStreaming" class="skx-chat-msg skx-chat-msg--ai">
        안녕하세요! <template v-if="bookTitle">《{{ bookTitle }}》에 대해</template><template v-else>이 자료에 대해</template> 궁금한 것을 자유롭게 물어보세요!
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
import { nextTick, ref, watch } from "vue";
import { useDeepReadChat } from "~/composables/useDeepReadChat";
import type { DeepReadMessage } from "~/utils/deepReadSse";

// 딥리드 대화 칸 — 논문 상세·논문 검색 결과 채팅·도서 상세·TopResult 와 연구 화면의 오른쪽 패널(06e)이 함께 쓴다.
// 대화 흐름(보내기·스트림 읽기·끊기·논문별 대화)은 useDeepReadChat 이 맡고 여기서는 그리기·입력·스크롤만 한다.
// store 를 넘기면(연구 화면 패널) 논문을 오갈 때 대화가 이어지고, 없으면 논문이 바뀔 때 비운다
const props = defineProps<{
  cntsId: string;
  bookTitle?: string;
  store?: Map<string, DeepReadMessage[]>;
}>();
defineEmits<{ (e: "close"): void }>();

const { messages, streamingText, isStreaming, send: sendChat } = useDeepReadChat({
  cntsId: () => props.cntsId,
  store: () => props.store,
});
const inputText = ref("");
const messagesEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);

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
  const sentFor = props.cntsId;
  await sendChat(text);
  // 답을 다 받았을 때만 입력 칸으로 돌아간다 — 논문을 바꿔 끊긴 경우 초점은 사용자가 누른 곳에 둔다
  if (props.cntsId === sentFor) nextTick(() => inputEl.value?.focus());
}
</script>
