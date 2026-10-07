<!-- frontend/components/work/CorpusScopeNote.vue -->
<template>
  <!-- 범위 띠(고정, spec §4) — 접거나 닫지 않는다. 범위를 모르면 그리지 않는다 -->
  <p v-if="line" class="wk-scope">{{ line }}</p>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { Corpus } from "~/types/work";
import { scopeLine } from "~/utils/workPhase";

const props = defineProps<{ corpus: Corpus | null }>();

const line = computed(() => scopeLine(props.corpus));
</script>
