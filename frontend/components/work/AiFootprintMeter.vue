<!-- frontend/components/work/AiFootprintMeter.vue -->
<template>
  <div class="wk-meter">
    <p class="wk-meter__line"><span class="wk-meter__title">AI 기여</span> {{ line }}</p>
    <template v-if="total">
      <div class="wk-meter__bar" aria-hidden="true">
        <span
          v-for="s in segments"
          :key="s.key"
          class="wk-meter__seg"
          :class="`is-${s.key}`"
          :style="{ flexGrow: s.n }"
        />
      </div>
      <ul class="wk-meter__legend">
        <li v-for="s in segments" :key="s.key"><span class="wk-meter__dot" :class="`is-${s.key}`" />{{ s.label }} {{ s.n }}</li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ParaState, ProposalView } from "~/types/work";
import { footprint, footprintLine } from "~/utils/proposalView";

const props = defineProps<{ proposal: ProposalView }>();

const ORDER: { key: ParaState; label: string }[] = [
  { key: "accepted", label: "수락" },
  { key: "edited", label: "수정" },
  { key: "proposed", label: "검토 전" },
  { key: "authored", label: "직접 작성" },
];

const counts = computed(() => footprint(props.proposal));
const line = computed(() => footprintLine(counts.value));
const total = computed(() => ORDER.reduce((n, s) => n + counts.value[s.key], 0));
const segments = computed(() => ORDER.map((s) => ({ ...s, n: counts.value[s.key] })).filter((s) => s.n > 0));
</script>
