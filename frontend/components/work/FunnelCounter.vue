<!-- frontend/components/work/FunnelCounter.vue -->
<template>
  <p class="wk-funnel"><span class="rs-sr-only">읽기 목록 깔때기: </span>{{ line }}</p>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ReadingFunnel } from "~/types/work";
import { funnelLine } from "~/utils/readingList";

// "검토 121 → 채택 48 → 후보 31 → 담음 12"(spec §4 S4) — 서버 ReadingView.funnel 그대로
const props = defineProps<{ funnel: ReadingFunnel }>();
const line = computed(() => funnelLine(props.funnel));
</script>
