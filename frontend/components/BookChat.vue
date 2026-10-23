<template>
  <div ref="rootEl" class="skx-chat-body">
    <div class="skx-chat-messages" ref="messagesEl">
      <!-- 빈 상태 — 인사와 쪽 번호 쓰는 법 한 줄 -->
      <div v-if="messages.length === 0 && !isStreaming" class="skx-chat-msg skx-chat-msg--ai skx-chat-msg--intro">
        <p class="skx-chat-answer__head" aria-hidden="true"><span class="skx-chat-answer__mark">✦</span>{{ DEEP_READ }}</p>
        <p class="skx-chat-intro__text">{{ copy.greeting(bookTitle) }}</p>
        <p class="skx-chat-intro__hint">{{ CITE_HINT }}</p>
      </div>

      <!-- 메시지 목록 — 질문은 오른쪽 말풍선, 답은 너비를 다 쓰는 답 카드(머리 · 글 · 근거 목록) -->
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['skx-chat-msg', msg.role === 'user' ? 'skx-chat-msg--user' : 'skx-chat-msg--ai']"
      >
        <div v-if="msg.role === 'user'" v-html="formatText(msg.content)" />
        <template v-else>
          <p class="skx-chat-answer__head" aria-hidden="true"><span class="skx-chat-answer__mark">✦</span>{{ DEEP_READ }}</p>
          <!-- 글 속 쪽 번호(.skx-chat-cite 단추)는 v-html 이라 누름을 여기서 받는다(onCiteClick) — 그 쪽의 근거 대목을 아래 목록에서 펼친다 -->
          <div class="skx-chat-answer__text" v-html="formatAnswer(msg, i)" @click="onCiteClick" />
          <!-- 근거 목록 — 같은 쪽 대목은 한 줄로 묶고 첫 대목의 머리 글을 보인다. 줄을 누르면 그 아래 대목이 펼쳐지고 다시 누르면 접는다.
               같은 쪽 대목이 여럿이면 ‹ › 로 넘긴다(끝에서도 disabled 로 막지 않는다 — 누른 단추가 막히면 키보드 초점이 사라진다). 원문 열기는 펼친 대목 아래 [원문 보기]이고 pdfLinks 인 곳(연구 화면 오른쪽 패널)에만 둔다 -->
          <div v-if="groupsByMsg[i]?.length" class="skx-chat-sources">
            <p class="skx-chat-sources__head">근거 {{ groupsByMsg[i]!.length }}곳</p>
            <ul class="skx-chat-source-list">
              <li v-for="(g, gi) in groupsByMsg[i]" :key="g.label" class="skx-chat-source">
                <button
                  :id="rowId(i, gi)"
                  type="button"
                  class="skx-chat-source-row"
                  :class="{ 'is-active': msg.pinnedChip === gi }"
                  :aria-expanded="msg.pinnedChip === gi"
                  :aria-controls="msg.pinnedChip === gi ? previewId(i, gi) : undefined"
                  @click="toggleGroup(msg, gi)"
                  @keydown.enter="onRepeatEnter"
                >
                  <span class="skx-chat-source-row__page">{{ g.label }}</span>
                  <span class="skx-chat-source-row__snippet">{{ g.snippet }}</span>
                  <span v-if="g.passages.length > 1" class="skx-chat-source-row__count">대목 {{ g.passages.length }}개</span>
                </button>
                <div v-if="msg.pinnedChip === gi" :id="previewId(i, gi)" class="skx-chat-source-preview">
                  <div v-if="g.passages.length > 1" class="skx-chat-source-pager">
                    <button
                      type="button"
                      class="skx-chat-source-pager__btn"
                      aria-label="이전 대목"
                      :aria-disabled="passageIndex(msg, g) === 0"
                      @click="movePassage(msg, g, -1)"
                    >
                      ‹
                    </button>
                    <span>{{ passageIndex(msg, g) + 1 }} / {{ g.passages.length }}</span>
                    <button
                      type="button"
                      class="skx-chat-source-pager__btn"
                      aria-label="다음 대목"
                      :aria-disabled="passageIndex(msg, g) === g.passages.length - 1"
                      @click="movePassage(msg, g, 1)"
                    >
                      ›
                    </button>
                  </div>
                  <p class="skx-chat-source-preview__text">{{ passageText(g.passages[passageIndex(msg, g)]?.text) }}</p>
                  <button
                    v-if="pdfLinks"
                    type="button"
                    class="rs-btn rs-btn--small rs-btn--ghost skx-chat-source-open"
                    @click="openSource(msg)"
                  >
                    원문 보기
                  </button>
                </div>
              </li>
            </ul>
          </div>
        </template>
      </div>

      <!-- 답을 받지 못한 질문 — 대화에는 남기지 않고(오류가 답처럼 굳거나 다음 질문의 history 로 가지 않게) 여기에만 보인다.
           실패 전까지 받던 글은 흐리게 남기고(다른 AI 글 화면처럼 읽던 글이 사라지지 않게) 그 아래 줄 안내(SkxInlineError — role=alert,
           받던 글까지 다시 읽지 않게)만 알린다. [다시 시도]는 같은 질문을 다시 보낸다 — 다시 보내도 같은 실패인 경우(자료 없음·질문이
           너무 김)는 숨긴다. 질문은 입력 칸에도 되살려 고쳐 보낼 수 있다(ask) -->
      <template v-if="failure">
        <div class="skx-chat-msg skx-chat-msg--user">
          <div v-html="formatText(failure.question)" />
        </div>
        <div class="skx-chat-msg skx-chat-msg--ai">
          <div v-if="failure.partial" class="skx-chat-msg__partial" v-html="formatStatic(failure.partial)" />
          <SkxInlineError
            class="skx-chat-msg__failed"
            :message="failure.message"
            :on-retry="failure.retryable ? retry : undefined"
          />
        </div>
      </template>

      <!-- 스트리밍 중 — 첫 글이 오기 전에는 지금 하는 일(대목 찾기 → 답 쓰기)을 보이고, 글이 흐르는 동안은 끝에 커서가 깜박인다.
           쪽 번호는 근거(sources)가 답 끝에 오므로 받는 동안은 모양만 같은 글자다 -->
      <template v-if="isStreaming">
        <div v-if="streamingText" class="skx-chat-msg skx-chat-msg--ai is-streaming">
          <p class="skx-chat-answer__head" aria-hidden="true"><span class="skx-chat-answer__mark">✦</span>{{ DEEP_READ }}</p>
          <div class="skx-chat-answer__text" v-html="formatStatic(streamingText)" />
        </div>
        <div v-else class="skx-chat-typing">
          <span class="skx-chat-typing__dots" aria-hidden="true">
            <span class="skx-chat-typing__dot"></span>
            <span class="skx-chat-typing__dot"></span>
            <span class="skx-chat-typing__dot"></span>
          </span>
          <span class="skx-chat-typing__text">{{ WAIT_STEPS[waitStep] }}</span>
        </div>
      </template>
    </div>
    <!-- 화면낭독기용 — 방금 보낸 질문의 답을 다 받으면 한 번 읽는다. 흐르는 글은 토막마다 읽히지 않게 싣지 않는다 -->
    <div class="skx-sr-only" aria-live="polite" v-html="liveHtml" />

    <div class="skx-chat-input-wrap">
      <!-- 질문은 서버 한도(CHAT_MAX_CHARS)까지 — maxlength 가 막고 글자 수(SkxCharCount)가 얼마나 썼는지 보인다. 질문 칸이라
           quiet — 한도 가까이(90%)부터만 보인다(검색창과 같다, 사용자 결정 2026-10-16). 낭독기 알림 영역은 늘 남는다 -->
      <textarea
        ref="inputEl"
        v-model="inputText"
        class="skx-chat-input"
        rows="2"
        :maxlength="CHAT_MAX_CHARS"
        :placeholder="copy.placeholder"
        :aria-label="copy.inputLabel"
        :aria-describedby="countId"
        :disabled="isStreaming"
        @keydown.enter.exact.prevent="onInputEnter"
        @keydown.enter.shift.exact="() => {}"
      />
      <SkxCharCount :id="countId" class="skx-chat-count" quiet :length="inputText.length" :max="CHAT_MAX_CHARS" />
      <!-- 보내기 — 답을 받는 동안은 같은 단추가 [멈춤]이다(한 요소라 누른 초점이 그대로 남는다) -->
      <button
        ref="sendEl"
        type="button"
        class="skx-chat-send"
        :class="{ 'skx-chat-send--stop': isStreaming }"
        :aria-label="isStreaming ? copy.stopLabel : copy.sendLabel"
        :title="isStreaming ? copy.stopLabel : undefined"
        :disabled="!isStreaming && !inputText.trim()"
        @click="onSendButton"
        @keydown.enter="onSendKeydown"
      >
        <svg v-if="isStreaming" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <rect x="3" y="3" width="10" height="10" rx="2" fill="currentColor" />
        </svg>
        <img v-else src="/img/ico-send.svg" alt="" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import { useDeepReadChat } from "~/composables/useDeepReadChat";
import type { OpenPdfPayload } from "~/types/research";
import { DEEP_READ } from "~/utils/brand";
import { type DocKind, chatCopy, sourcePdfTarget } from "~/utils/deepRead";
import { type SourceGroup, groupSources, renderAnswer } from "~/utils/deepReadCitations";
import { CHAT_MAX_CHARS, type DeepReadMessage, type DeepReadSource } from "~/utils/deepReadSse";
import { passageText } from "~/utils/passageText";

// 빈 대화의 쓰는 법 한 줄 — 답의 쪽 번호가 이 화면의 핵심이라 처음부터 알린다
const CITE_HINT = "답에 붙은 쪽 번호를 누르면 근거가 된 원문 대목이 펼쳐져요.";
// 첫 글이 오기 전의 안내 — 서버는 먼저 이 자료에서 대목을 찾고(1초 안팎) 그 대목으로 답을 쓴다. 단계 신호는 없어 시간으로 넘긴다
const WAIT_STEPS = ["원문에서 관련 대목을 찾는 중…", "찾은 대목을 읽고 답을 쓰는 중…"] as const;
const WAIT_STEP_MS = 1800;

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

const {
  messages,
  streamingText,
  isStreaming,
  failure,
  send: sendChat,
  retry: retryChat,
  stop: stopChat,
} = useDeepReadChat({
  cntsId: () => props.cntsId,
  store: () => props.store,
});
const inputText = ref("");
const rootEl = ref<HTMLElement | null>(null);
const messagesEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);
const sendEl = ref<HTMLButtonElement | null>(null);
// 입력 칸이 aria-describedby 로 가리키는 글자 수 — 한 화면에 대화 칸이 여럿이어도 겹치지 않게
const countId = `skx-chat-count-${useId()}`;
// 화면낭독기가 읽을 끝난 답(HTML) — 방금 보낸 질문의 답만 싣는다(논문을 바꿔 다른 대화를 펼칠 때 옛 답을 다시 읽지 않게)
const liveHtml = ref("");

function formatText(text: string) {
  if (!text) return "";
  return marked.parse(text) as string;
}

// 답마다 근거 묶음(같은 쪽 대목 한 줄) — 글과 sources 로만 정해져 펼침이 바뀌어도 다시 묶지 않는다
const groupsByMsg = computed<SourceGroup[][]>(() =>
  messages.value.map((m) => (m.role === "assistant" ? groupSources(m.sources, m.content) : [])),
);

/** 받기를 마친 답 — 글 속 쪽 표기를 그 근거 묶음을 펼치는 단추로 */
function formatAnswer(msg: DeepReadMessage, i: number): string {
  return renderAnswer(msg.content, { msg: i, groups: groupsByMsg.value[i] ?? [], active: msg.pinnedChip });
}

/** 받는 중·받지 못한 글·낭독용 — 쪽 표기는 모양만 같은 글자('[쪽 정보 없음]'은 걷는다) */
function formatStatic(text: string): string {
  return renderAnswer(text, null);
}

const domId = useId();
const rowId = (i: number, gi: number) => `skx-chat-src-${domId}-${i}-${gi}`;
const previewId = (i: number, gi: number) => `skx-chat-src-${domId}-${i}-${gi}-text`;

/** 근거 줄 누름 — 펼치고(첫 대목부터) 다시 누르면 접는다 */
function toggleGroup(msg: DeepReadMessage, gi: number): void {
  const opening = msg.pinnedChip !== gi;
  msg.pinnedChip = opening ? gi : undefined;
  msg.pinnedPassage = 0;
}

/** 펼친 묶음에서 보이는 대목 번호 — 범위를 벗어나면 첫 대목 */
function passageIndex(msg: DeepReadMessage, g: SourceGroup): number {
  const pi = msg.pinnedPassage ?? 0;
  return pi >= 0 && pi < g.passages.length ? pi : 0;
}

function movePassage(msg: DeepReadMessage, g: SourceGroup, step: number): void {
  msg.pinnedPassage = Math.min(g.passages.length - 1, Math.max(0, passageIndex(msg, g) + step));
}

// 글 속 쪽 번호 누름 — 그 근거 묶음을 펼치고(이미 펼쳤으면 그대로) 목록 줄로 초점을 옮겨 보이게 한다(낭독기는 펼침 상태를 읽는다)
function onCiteClick(e: MouseEvent): void {
  const btn = (e.target as HTMLElement | null)?.closest<HTMLButtonElement>("button.skx-chat-cite[data-cite]");
  if (!btn) return;
  const i = Number(btn.dataset.msg);
  const gi = Number(btn.dataset.cite);
  const msg = messages.value[i];
  if (!msg || !groupsByMsg.value[i]?.[gi]) return;
  if (msg.pinnedChip !== gi) {
    msg.pinnedChip = gi;
    msg.pinnedPassage = 0;
  }
  nextTick(() => {
    const row = document.getElementById(rowId(i, gi));
    row?.focus({ preventScroll: true });
    const preview = document.getElementById(previewId(i, gi));
    (preview ?? row)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
}

// 첫 글을 기다리는 동안의 안내 단계 — 보낼 때 0, WAIT_STEP_MS 뒤 1. 글이 오거나 끝나면 멈춘다
const waitStep = ref(0);
let waitTimer: ReturnType<typeof setTimeout> | null = null;
function clearWait() {
  if (waitTimer) clearTimeout(waitTimer);
  waitTimer = null;
}
watch(
  () => isStreaming.value && !streamingText.value,
  (waiting) => {
    clearWait();
    if (!waiting) return;
    waitStep.value = 0;
    waitTimer = setTimeout(() => {
      waitStep.value = 1;
      waitTimer = null;
    }, WAIT_STEP_MS);
  },
  { immediate: true },
);
onBeforeUnmount(clearWait);

function scrollBottom() {
  nextTick(() => {
    if (messagesEl.value)
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
  });
}

// 질문·답이 쌓이거나 글이 흐르거나 답을 받지 못했거나 다른 논문의 대화로 바뀌면 맨 아래로
watch([messages, () => messages.value.length, streamingText, failure], scrollBottom);

async function send() {
  const text = inputText.value.trim();
  if (!text || isStreaming.value) return;
  inputText.value = "";
  await ask(() => sendChat(text));
}

// 보내기 단추 — 답을 받는 동안은 [멈춤]. 보내기를 두 번 눌러(더블클릭) 둘째 누름이 방금 보낸 질문을 끊지 않게 연속 누름
// (detail 2 이상)은 무시한다. 키보드로 누르면 detail 이 0 이다
function onSendButton(e: MouseEvent) {
  if (!isStreaming.value) void send();
  else if (e.detail < 2) stopChat();
}

// 근거 줄의 Enter — 글 속 쪽 번호를 Enter 로 누르면 초점이 이 줄로 옮겨 오는데, 누른 채 있으면 반복 keydown 이 줄의 click 이 되어
// 방금 펼친 대목을 도로 접었다. 반복이면 기본 동작(click)을 막는다
function onRepeatEnter(e: KeyboardEvent) {
  if (e.repeat) e.preventDefault();
}

// Enter 를 누른 채 있으면 자동 반복 keydown(e.repeat)이 이어진다 — 한 번 누른 것의 꼬리라 어디서든 누름으로 치지 않는다.
// 질문 칸: Enter 로 보낸다(Shift+Enter 는 줄바꿈). 반복은 다시 보내지 않는다 — 답을 받지 못해 질문이 칸에 되살아난 뒤 같은
// 질문이 또 나가지 않게
function onInputEnter(e: KeyboardEvent) {
  if (!e.repeat) void send();
}

// [멈춤] 단추: 보낸 뒤 초점이 이 단추로 옮겨 오면(ask) 이어지는 반복 keydown 이 단추의 키보드 click(detail 0)이 되어 방금 보낸
// 질문을 바로 멈췄다 — 반복이면 기본 동작(click)을 막는다. 손을 뗐다 다시 누른 Enter 는 그대로 [멈춤]이다
function onSendKeydown(e: KeyboardEvent) {
  if (e.repeat) e.preventDefault();
}

// 답을 받지 못해 입력 칸에 되살린 질문(ask) — 그 논문에 묻던 질문이라 논문을 바꾸면 칸에서 비운다(실패 안내도 함께 걷힌다 —
// useDeepReadChat). 고쳐 쓴 글은 사용자 글이라 둔다
let restoredQuestion: string | null = null;
watch(
  () => props.cntsId,
  () => {
    if (restoredQuestion !== null && inputText.value.trim() === restoredQuestion) inputText.value = "";
    restoredQuestion = null;
  },
);

// [다시 시도] — 답을 받지 못한 질문을 그대로 다시 보낸다. 입력 칸에 되살려 둔 그 질문은 비운다(답을 받은 뒤 칸에 남지 않게) —
// 고쳐 쓴 글은 둔다
async function retry() {
  if (isStreaming.value) return;
  if (inputText.value.trim() === failure.value?.question) inputText.value = "";
  await ask(retryChat);
}

async function ask(request: () => Promise<void>) {
  liveHtml.value = "";
  restoredQuestion = null;
  const sentFor = props.cntsId;
  const answered = request();
  // 보내는 동안 입력 칸이 막혀 초점이 떨어지면(Enter 로 보냄) 같은 자리의 [멈춤] 단추로 옮긴다 — 키보드로도 바로 멈출 수 있고
  // 서랍 패널의 초점이 body 로 새지 않는다. 사용자가 그새 다른 곳을 눌렀으면 두지 않는다
  nextTick(() => {
    const active = document.activeElement;
    if (isStreaming.value && (!active || active === document.body || active === inputEl.value)) sendEl.value?.focus();
  });
  await answered;
  // 답을 다 받았을 때만 읽고 입력 칸으로 돌아간다 — 논문을 바꿔 끊긴 경우 초점은 사용자가 누른 곳에 둔다
  if (props.cntsId !== sentFor) return;
  // 답을 받지 못했으면 보낸 질문을 입력 칸에 되살린다 — 보낼 때 비운 칸이라 고쳐 다시 보낼 수 있게(그새 쓴 글이 있으면 두지 않는다)
  if (failure.value && !inputText.value.trim()) {
    inputText.value = failure.value.question;
    restoredQuestion = failure.value.question;
  }
  const last = messages.value.at(-1);
  // 답을 받지 못했으면 앞 답을 다시 읽히지 않는다 — 실패 안내는 role=alert 가 읽는다
  if (!failure.value && last?.role === "assistant") liveHtml.value = formatStatic(last.content);
  // 초점이 갈 곳 없이 떨어졌거나(보내는 동안 막힌 버튼 — body) 대화 안에 있을 때만 질문 칸으로 — 연구 화면 2단에서는 답을
  // 기다리는 사이 본문 칸(메모·연구 배경·문단 고치기)에 쓸 수 있어, 그 글을 끊지 않는다
  nextTick(() => {
    const active = document.activeElement;
    if (!active || active === document.body || rootEl.value?.contains(active)) inputEl.value?.focus();
  });
}

// 펼친 근거 대목(펼친 묶음의 보이는 대목) — 없으면 null
function pinnedSource(msg: DeepReadMessage): DeepReadSource | null {
  if (msg.pinnedChip === undefined) return null;
  const g = groupsByMsg.value[messages.value.indexOf(msg)]?.[msg.pinnedChip];
  return g ? (g.passages[passageIndex(msg, g)] ?? null) : null;
}

function openSource(msg: DeepReadMessage): void {
  const src = pinnedSource(msg);
  if (src) emit("open-pdf", sourcePdfTarget(props.cntsId, props.bookTitle || props.cntsId, src));
}
</script>
