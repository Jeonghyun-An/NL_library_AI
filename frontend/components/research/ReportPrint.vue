<!-- frontend/components/research/ReportPrint.vue -->
<template>
  <!-- body 바로 아래에 붙인다 — 인쇄 CSS 가 body 의 다른 자식(앱 전체)을 한 번에 숨기고 이것만 찍는다 -->
  <Teleport to="body">
    <!-- 흰 종이에 찍는 문서라 밝은 읽는 면 — 다크 테마의 밝은 글 톤이 흰 종이에 찍히지 않게 토큰을 밝은 면 값으로 바꾼다.
         화면에는 그리지 않는다(research.css 의 .rs-print — [PDF로 저장]을 누른 동안에만 body 에 붙는다) -->
    <article class="rs-print skx-reading">
      <!-- 인쇄에서 position: fixed 는 쪽마다 되풀이된다 — 검토 전 AI 문단을 실은 계획서의 경고 글(work.css) -->
      <p v-if="doc.watermark" class="wk-print-watermark">{{ doc.watermark }}</p>
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
