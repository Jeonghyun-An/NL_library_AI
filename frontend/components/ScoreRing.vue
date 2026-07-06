<template>
  <span
    :class="[
      'skx-score-ring',
      variant === 'content' && 'skx-score-ring--content',
    ]"
    tabindex="0"
  >
    <svg class="skx-score-ring__svg" viewBox="0 0 36 36" aria-hidden="true">
      <circle class="skx-score-ring__bg" cx="18" cy="18" r="15.5" />
      <circle
        class="skx-score-ring__fg"
        cx="18"
        cy="18"
        r="15.5"
        :style="{
          strokeDasharray: CIRC + 'px',
          strokeDashoffset: offset + 'px',
        }"
      />
    </svg>
    <span class="skx-score-ring__pct">{{ clamped }}</span>
    <span class="skx-score-ring__tip" role="tooltip"
      >{{ label }} {{ clamped }}%</span
    >
  </span>
</template>

<script setup lang="ts">
const props = defineProps<{
  pct: number;
  label: string;
  variant?: "title" | "content";
}>();

const CIRC = 2 * Math.PI * 15.5;
const clamped = computed(() =>
  Math.max(0, Math.min(100, Math.round(props.pct))),
);
const offset = computed(() => CIRC * (1 - clamped.value / 100));
</script>
