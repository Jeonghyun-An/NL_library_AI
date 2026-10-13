<!-- frontend/components/research/ResearchModePicker.vue -->
<!-- DeepResearch '탐색 방식'(spec D28) — 폭넓게 · 정밀하게 두 칸 선택(radiogroup). 고른 값은 v-model 로 주고받고,
     기억(localStorage)과 잡 params 싣기는 부르는 쪽이 한다 -->
<template>
  <div class="rs-mode">
    <span :id="labelId" class="rs-mode__label">{{ RESEARCH_MODE_LABEL }}</span>
    <div
      ref="group"
      class="rs-mode__group"
      role="radiogroup"
      :aria-labelledby="labelId"
      :aria-describedby="hintId"
      @keydown="onKeydown"
    >
      <!-- 고른 칸만 Tab 으로 들어온다(roving tabindex). 칸 사이는 방향키로 옮기며 고른다 -->
      <button
        v-for="m in RESEARCH_MODES"
        :key="m.id"
        type="button"
        role="radio"
        class="rs-mode__opt"
        :data-mode="m.id"
        :aria-checked="m.id === modelValue"
        :tabindex="m.id === modelValue ? 0 : -1"
        :title="m.hint"
        :disabled="disabled"
        @click="pick(m.id)"
      >
        {{ m.label }}
      </button>
    </div>
    <span :id="hintId" class="rs-mode__hint">{{ hint }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useId } from "vue";
import { RESEARCH_MODES, RESEARCH_MODE_LABEL, modeStep, type ResearchMode } from "~/utils/researchMode";

const props = withDefaults(defineProps<{ modelValue: ResearchMode; disabled?: boolean }>(), { disabled: false });
const emit = defineEmits<{ "update:modelValue": [mode: ResearchMode] }>();

const group = ref<HTMLElement | null>(null);
const labelId = useId();
const hintId = useId();
const hint = computed(() => RESEARCH_MODES.find((m) => m.id === props.modelValue)?.hint ?? "");

function pick(mode: ResearchMode): void {
  if (props.disabled || mode === props.modelValue) return;
  emit("update:modelValue", mode);
}

// 선택이 초점을 따른다(radiogroup 관례) — 옮긴 칸을 고르고 그 칸에 초점을 둔다. 방향키가 페이지를 굴리지 않게 막는다
function onKeydown(e: KeyboardEvent): void {
  if (props.disabled) return;
  const next = modeStep(props.modelValue, e.key);
  if (!next) return;
  e.preventDefault();
  pick(next);
  void nextTick(() => group.value?.querySelector<HTMLButtonElement>(`[data-mode="${next}"]`)?.focus());
}
</script>
