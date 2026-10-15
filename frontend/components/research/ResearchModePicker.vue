<!-- frontend/components/research/ResearchModePicker.vue -->
<!-- DeepResearch '탐색 방식'(spec D28) — DeepResearch 칩 옆의 작은 칩 하나('정밀하게 탐색 ▾')와, 누르면 펼쳐지는 고르기 카드 두 장.
     카드(라디오 · 영문 이름 · 우리말 이름 · 기본 배지 · 설명 두 줄)는 후배 시안 '탐색 방식 선택'(피그마 DeepResearch_hover 2701:10988)을
     따른다. 전에는 칩 옆 두 칸 + 입력창 아래 설명 줄이라 입력 상자가 어수선했다(사용자 의견 2026-10-14). 고른 값은 v-model 로
     주고받고, 기억(localStorage)과 잡 params 싣기는 부르는 쪽이 한다 -->
<template>
  <span ref="root" class="rs-mode" @keydown.esc="onEsc">
    <button
      ref="chip"
      type="button"
      class="rs-mode__chip"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :aria-controls="open ? panelId : undefined"
      :aria-label="`${RESEARCH_MODE_LABEL}: ${current.label} — 바꾸기`"
      :disabled="disabled"
      @click="toggle"
    >
      {{ current.label }}
      <span class="rs-mode__caret" aria-hidden="true">▾</span>
    </button>
    <div v-if="open" :id="panelId" class="rs-mode__panel" role="dialog" :aria-labelledby="titleId">
      <p :id="titleId" class="rs-mode__title">{{ RESEARCH_MODE_LABEL }} 선택</p>
      <!-- 고른 카드만 Tab 으로 들어온다(roving tabindex). 위·아래 방향키로 옮기며 고르고, 엔터·누름은 고르고 닫는다 -->
      <div ref="group" class="rs-mode__cards" role="radiogroup" :aria-labelledby="titleId" @keydown="onKeydown">
        <button
          v-for="m in RESEARCH_MODES"
          :key="m.id"
          type="button"
          role="radio"
          class="rs-mode__card"
          :data-mode="m.id"
          :aria-checked="m.id === modelValue"
          :aria-describedby="`${panelId}-${m.id}`"
          :tabindex="m.id === modelValue ? 0 : -1"
          @click="choose(m.id)"
        >
          <span class="rs-mode__radio" aria-hidden="true" />
          <span class="rs-mode__body">
            <span class="rs-mode__head">
              <span class="rs-mode__en">{{ m.en }}</span>
              <span class="rs-mode__ko">{{ m.label }}</span>
              <span v-if="m.id === DEFAULT_RESEARCH_MODE" class="rs-mode__default">기본</span>
            </span>
            <span :id="`${panelId}-${m.id}`" class="rs-mode__desc">{{ m.hint }}</span>
          </span>
        </button>
      </div>
    </div>
  </span>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import {
  DEFAULT_RESEARCH_MODE,
  RESEARCH_MODES,
  RESEARCH_MODE_LABEL,
  modeStep,
  type ResearchMode,
} from "~/utils/researchMode";

const props = withDefaults(defineProps<{ modelValue: ResearchMode; disabled?: boolean }>(), { disabled: false });
const emit = defineEmits<{ "update:modelValue": [mode: ResearchMode] }>();

const root = ref<HTMLElement | null>(null);
const chip = ref<HTMLButtonElement | null>(null);
const group = ref<HTMLElement | null>(null);
const panelId = useId();
const titleId = useId();
const open = ref(false);

const current = computed(() => RESEARCH_MODES.find((m) => m.id === props.modelValue) ?? RESEARCH_MODES[0]!);

function focusCard(mode: ResearchMode): void {
  void nextTick(() => group.value?.querySelector<HTMLButtonElement>(`[data-mode="${mode}"]`)?.focus({ preventScroll: true }));
}

// 열면 고른 카드에 초점을 둔다 — 방향키·엔터가 바로 먹게
function toggle(): void {
  if (props.disabled) return;
  open.value = !open.value;
  if (open.value) focusCard(props.modelValue);
}

function close(refocus: boolean): void {
  if (!open.value) return;
  open.value = false;
  if (refocus) void nextTick(() => chip.value?.focus({ preventScroll: true }));
}

function pick(mode: ResearchMode): void {
  if (props.disabled || mode === props.modelValue) return;
  emit("update:modelValue", mode);
}

// 누르거나 엔터 — 고르고 닫는다
function choose(mode: ResearchMode): void {
  pick(mode);
  close(true);
}

// 선택이 초점을 따른다(radiogroup 관례) — 옮긴 카드를 고르고 그 카드에 초점을 둔다. 방향키가 페이지를 굴리지 않게 막는다.
// Tab 은 막지 않는다 — 닫고 칩 다음으로 간다
function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Tab") {
    close(false);
    return;
  }
  const next = modeStep(props.modelValue, e.key);
  if (!next) return;
  e.preventDefault();
  pick(next);
  focusCard(next);
}

// Esc 는 열려 있을 때만 받는다 — 닫고 칩으로 돌아간다. 그 밖에는 흘려보낸다(+ 메뉴 닫기 등)
function onEsc(e: KeyboardEvent): void {
  if (!open.value) return;
  e.preventDefault();
  e.stopPropagation();
  close(true);
}

function onDocumentPointer(e: PointerEvent): void {
  if (root.value && e.target instanceof Node && !root.value.contains(e.target)) close(false);
}

watch(open, (now) => {
  if (now) document.addEventListener("pointerdown", onDocumentPointer);
  else document.removeEventListener("pointerdown", onDocumentPointer);
});
// 잠기면(시작 요청 중) 펼친 카드를 거둔다
watch(
  () => props.disabled,
  (now) => {
    if (now) close(false);
  },
);
onBeforeUnmount(() => document.removeEventListener("pointerdown", onDocumentPointer));
</script>
