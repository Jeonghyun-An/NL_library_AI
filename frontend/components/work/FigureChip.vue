<!-- frontend/components/work/FigureChip.vue -->
<template>
  <!-- [F#] 자리 — 값은 코드가 센 수치다. 무엇을 센 값인지(라벨)는 가리키거나 초점을 줄 때 풀어 보인다 -->
  <span class="wk-fig" tabindex="0">
    {{ figure.value }}<span class="rs-sr-only"> ({{ figure.label }})</span>
    <span class="wk-fig__tip" aria-hidden="true">{{ figure.label }}</span>
  </span>
</template>

<script setup lang="ts">
import type { Figure } from "~/types/work";

defineProps<{ figure: Figure }>();
</script>
