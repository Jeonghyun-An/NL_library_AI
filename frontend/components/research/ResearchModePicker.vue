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
  </div>
  <!-- 고른 방식의 설명은 .rs-mode 밖(+ 메뉴 줄의 자식)이라 랜딩 입력 상자에서 늘 자기 줄에 선다 — 설명 길이가 묶음이 칩 줄에 설지를
       정하지 않는다. 두 방식의 설명을 같은 칸에 겹쳐 두고 고른 것만 보여, 칸을 바꿔도 설명 줄 높이(=상자 높이)가 그대로다.
       radiogroup 의 설명(aria-describedby)은 보이는 것 하나이고 숨긴 것은 읽히지 않는다 -->
  <span class="rs-mode__hint">
    <span
      v-for="m in RESEARCH_MODES"
      :id="m.id === modelValue ? hintId : undefined"
      :key="m.id"
      class="rs-mode__hint-text"
      :class="{ 'is-shown': m.id === modelValue }"
      :aria-hidden="m.id === modelValue ? undefined : 'true'"
    >{{ m.hint }}</span>
  </span>
</template>

<script setup lang="ts">
import { nextTick, ref, useId } from "vue";
import { RESEARCH_MODES, RESEARCH_MODE_LABEL, modeStep, type ResearchMode } from "~/utils/researchMode";

const props = withDefaults(defineProps<{ modelValue: ResearchMode; disabled?: boolean }>(), { disabled: false });
const emit = defineEmits<{ "update:modelValue": [mode: ResearchMode] }>();

const group = ref<HTMLElement | null>(null);
const labelId = useId();
const hintId = useId();

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
