<!-- frontend/components/work/PathPopover.vue -->
<template>
  <div class="wk-path" role="region" :aria-label="`${item.meta.title || item.cnts_id} — 들어온 경로`">
    <ul class="wk-path__list">
      <li v-for="(line, i) in lines" :key="i" class="wk-path__line">
        <span class="wk-path__label">{{ line.label }}</span>
        <span class="wk-path__detail">{{ line.detail }}</span>
        <template v-if="line.chunk">
          <span class="wk-path__quote">{{ line.chunk.text }}</span>
          <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="openChunk(line)">원문 보기</button>
        </template>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { OpenPdfPayload } from "~/types/research";
import type { ReadingItem } from "~/types/work";
import { type PathLine, pathLines, pathPdfTarget } from "~/utils/readingList";

// 행의 [경로] — 저장된 값만으로 그린 들어온 경로(spec §5-4)와, 매칭 대목에서 원문 쪽으로 가는 [원문 보기].
// jobId 는 계약의 props 모양 그대로 받는다 — 06b 의 경로 줄은 서버가 준 값만 그려 쓰지 않는다
const props = defineProps<{ item: ReadingItem; jobId: string }>();
const emit = defineEmits<{ "open-pdf": [payload: OpenPdfPayload] }>();

const lines = computed(() => pathLines(props.item));

function openChunk(line: PathLine): void {
  if (line.chunk) emit("open-pdf", pathPdfTarget(props.item, line.chunk));
}
</script>
