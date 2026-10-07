<!-- frontend/components/work/OnboardingModal.vue -->
<template>
  <Teleport to="body">
    <div v-if="open" class="wk-modal" @click.self="$emit('close')">
      <div class="wk-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="wk-onboarding-title">
        <header class="wk-modal__head">
          <h2 id="wk-onboarding-title" class="wk-modal__title">탐색은 끝났습니다</h2>
          <button ref="closeBtn" type="button" class="rs-icon-btn" aria-label="안내 닫기" title="닫기 (Esc)" @click="$emit('close')">
            ✕
          </button>
        </header>
        <p class="wk-modal__lead">주제 → 읽기 목록 → 계획서 3단계를 거쳐 연구계획서 초안까지 갑니다.</p>
        <ol class="wk-modal__steps">
          <li v-for="(s, i) in ONBOARDING_STEPS" :key="s.title" class="wk-modal__step">
            <p class="wk-modal__step-title"><span class="wk-stepper__no" aria-hidden="true">{{ i + 2 }}</span>{{ s.title }}</p>
            <p class="rs-muted">{{ s.body }}</p>
            <p class="wk-modal__decide">결정할 것 — {{ s.decide }}</p>
          </li>
        </ol>
        <div class="wk-modal__actions">
          <button type="button" class="rs-btn" @click="$emit('close')">알겠습니다</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { focusReturnTarget } from "~/utils/pdfViewer";
import { ONBOARDING_STEPS } from "~/utils/workPhase";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const closeBtn = ref<HTMLButtonElement | null>(null);
// 연 순간의 초점 요소부터 위로 올라간 조상들 — 닫을 때 초점을 돌려줄 곳을 찾는다(PdfViewer 와 같은 방식)
let returnPath: HTMLElement[] = [];
let locked = false;

function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape") emit("close");
}

// 열려 있는 동안 배경(#__nuxt — 모달은 body 로 옮겨 그려진다)은 초점·클릭을 받지 않는다(inert). Tab 이 모달 밖
// 화면으로 새지 않고, 겹친 화면을 굴려도 읽던 자리가 그대로다
function lock(on: boolean): void {
  if (locked === on) return;
  locked = on;
  document.getElementById("__nuxt")?.toggleAttribute("inert", on);
  document.documentElement.style.overflow = on ? "hidden" : "";
  if (on) document.addEventListener("keydown", onKeydown);
  else document.removeEventListener("keydown", onKeydown);
}

watch(
  () => props.open,
  async (open) => {
    if (!import.meta.client) return;
    if (open) {
      returnPath = [];
      for (let el = document.activeElement; el instanceof HTMLElement && el !== document.body; el = el.parentElement) {
        returnPath.push(el);
      }
      lock(true);
      await nextTick();
      closeBtn.value?.focus();
    } else if (locked) {
      lock(false);
      focusReturnTarget(returnPath)?.focus({ preventScroll: true });
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (locked) lock(false);
});
</script>
