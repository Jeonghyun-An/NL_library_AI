<!-- frontend/components/research/ReportPrint.vue -->
<template>
  <!-- body 바로 아래에 붙인다 — 인쇄 CSS 가 body 의 다른 자식(앱 전체)을 한 번에 숨기고 이것만 찍는다 -->
  <Teleport to="body">
    <article class="rs-print">
      <template v-for="(block, bi) in doc.blocks" :key="bi">
        <h1 v-if="block.type === 'title'" class="rs-print__title">{{ block.text }}</h1>
        <p v-else-if="block.type === 'meta'" class="rs-print__meta">{{ block.text }}</p>
        <h2 v-else-if="block.type === 'heading' && block.level === 1" class="rs-print__h1">{{ block.text }}</h2>
        <h3 v-else-if="block.type === 'heading'" class="rs-print__h2">{{ block.text }}</h3>
        <p v-else-if="block.type === 'para'" class="rs-print__para" :class="{ 'is-muted': block.muted }">
          {{ runsText(block.runs) }}
        </p>
        <ul v-else-if="block.type === 'bullets'" class="rs-print__list">
          <li v-for="(runs, ii) in block.items" :key="ii">{{ runsText(runs) }}</li>
        </ul>
      </template>
      <template v-if="doc.references.length">
        <h2 class="rs-print__h1">참고문헌</h2>
        <ol class="rs-print__refs">
          <li v-for="r in doc.references" :key="r.n">[{{ r.n }}] {{ r.text }}</li>
        </ol>
      </template>
    </article>
  </Teleport>
</template>

<script setup lang="ts">
import { docRunText, type DocRun, type ReportDoc } from "~/utils/reportDocument";

defineProps<{ doc: ReportDoc }>();

function runsText(runs: DocRun[]): string {
  return runs.map(docRunText).join("");
}
</script>
