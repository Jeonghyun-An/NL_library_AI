<!-- frontend/components/work/WorkStepper.vue -->
<template>
  <!-- 이어간 연구에만 그린다(spec §4) — ① 탐색 ② 주제 ③ 읽기 목록 ④ 계획서. 끝난 단계와 지금 단계는 눌러 다시 연다 -->
  <nav class="wk-stepper" aria-label="연구 단계">
    <ol class="wk-stepper__list">
      <li v-for="(item, i) in items" :key="item.key" class="wk-stepper__item" :class="`is-${item.state}`">
        <button v-if="item.clickable" type="button" class="wk-stepper__step" @click="go(item)">
          <span class="wk-stepper__no" aria-hidden="true">{{ i + 1 }}</span>{{ item.label }}<span class="rs-sr-only">
            ({{ STATE_LABEL[item.state] }})</span>
        </button>
        <span v-else class="wk-stepper__step" :aria-current="item.key === viewing ? 'step' : undefined">
          <span class="wk-stepper__no" aria-hidden="true">{{ i + 1 }}</span>{{ item.label }}<span class="rs-sr-only">
            ({{ STATE_LABEL[item.state] }})</span>
        </span>
      </li>
    </ol>
    <p class="wk-stepper__line">{{ line }}</p>
    <button type="button" class="rs-icon-btn wk-stepper__help" aria-label="단계 안내 다시 보기" title="단계 안내" @click="$emit('help')">
      ?
    </button>
  </nav>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { WorkPhase, WorkStep } from "~/types/work";
import { stepLine, stepperItems, type StepperItem } from "~/utils/workPhase";

// phase = 도달한 단계, current = 지금 보는 단계(?s=, null 이면 탐색·보고서)
const props = defineProps<{ phase: WorkPhase; current: WorkStep | null }>();
const emit = defineEmits<{ go: [step: WorkStep | null]; help: [] }>();

const STATE_LABEL: Record<StepperItem["state"], string> = { done: "끝남", current: "지금 단계", todo: "아직" };

const items = computed(() => stepperItems(props.phase, props.current));
const line = computed(() => stepLine(props.phase));
const viewing = computed(() => props.current ?? "explore");

// ① 탐색은 보고서 화면(?s= 없음)이다
function go(item: StepperItem): void {
  emit("go", item.key === "explore" ? null : item.key);
}
</script>
