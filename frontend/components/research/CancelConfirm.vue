<!-- frontend/components/research/CancelConfirm.vue -->
<!-- 연구 취소의 한 번 확인 — 메인 입력창의 끝나지 않은 연구 줄(SearchPlusMenu)과 같은 화면 안 2단계(사용자 결정 2026-10-14: 연구 화면만
     브라우저 확인창이라 둘이 달랐다). 첫 누름은 '정말 취소' + [그대로 두기]로 바꾸기만 하고, 잠깐(NOTICE_CANCEL_ARM_MS) 뒤의 두 번째
     누름에 confirm 을 알린다 — 더블클릭 한 번에 넘어가지 않게. [그대로 두기]·Esc 는 물러나며 초점을 취소 버튼으로 돌린다.
     취소 요청과 그동안의 잠금(disabled)은 부르는 쪽이 한다 -->
<template>
  <span class="rs-cancel" @keydown.esc="onEsc">
    <button
      ref="btn"
      type="button"
      :class="['rs-btn', 'rs-btn--ghost', small && 'rs-btn--small', step === 'confirm' && 'rs-cancel__btn--danger']"
      :disabled="disabled"
      :aria-describedby="step === 'confirm' ? hintId : undefined"
      @click="press"
    >
      {{ step === "confirm" ? noticeCancelLabel("confirm") : label }}
    </button>
    <button
      v-if="step === 'confirm'"
      type="button"
      :class="['rs-btn', 'rs-btn--ghost', small && 'rs-btn--small']"
      @click="back"
    >
      그대로 두기
    </button>
    <span v-if="step === 'confirm'" :id="hintId" class="rs-sr-only">{{ NOTICE_CANCEL_CONFIRM_TEXT }}</span>
    <span class="rs-sr-only" role="status">{{ live }}</span>
  </span>
</template>

<script setup lang="ts">
import { nextTick, ref, useId, watch } from "vue";
import {
  NOTICE_CANCEL_CONFIRM_TEXT,
  noticeCancelBack,
  noticeCancelLabel,
  noticeCancelPress,
  type NoticeCancelStep,
} from "~/utils/researchStart";

const props = withDefaults(defineProps<{ label?: string; disabled?: boolean; small?: boolean }>(), {
  label: "취소",
  disabled: false,
  small: false,
});
const emit = defineEmits<{ confirm: [] }>();

const btn = ref<HTMLButtonElement | null>(null);
const hintId = useId();
const step = ref<NoticeCancelStep>("idle");
// 확인에 들어갈 때만 채운다 — 바뀐 버튼 이름은 초점을 쥔 채로는 잘 읽히지 않는다
const live = ref("");
let armedAt = 0;

function press(): void {
  const now = Date.now();
  const action = noticeCancelPress(step.value, armedAt, now);
  if (action === "arm") {
    step.value = "confirm";
    armedAt = now;
    live.value = NOTICE_CANCEL_CONFIRM_TEXT;
    return;
  }
  if (action !== "run") return;
  step.value = "idle";
  live.value = "";
  emit("confirm");
}

// [그대로 두기]를 누르면 그 버튼이 사라지므로 초점을 취소 버튼으로 돌린다
function back(): void {
  const next = noticeCancelBack(step.value);
  if (!next) return;
  step.value = next;
  live.value = "";
  void nextTick(() => btn.value?.focus());
}

// Esc 는 확인 중일 때만 받는다 — 그 밖에는 페이지로 흘려보낸다
function onEsc(e: KeyboardEvent): void {
  if (step.value !== "confirm") return;
  e.preventDefault();
  e.stopPropagation();
  back();
}

// 잠기면(취소 요청 중·다른 동작) 확인을 푼다 — 풀린 뒤 '정말 취소'가 남아 있지 않게
watch(
  () => props.disabled,
  (now) => {
    if (now && step.value === "confirm") {
      step.value = "idle";
      live.value = "";
    }
  },
);
</script>
