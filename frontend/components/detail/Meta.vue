<template>
  <!-- 서지 표 — 라벨 열(회녹색) | 값 열(거의 흰색). 값 조각 사이 화살표는 '발행처 › 분야 › 권호' -->
  <dl v-if="rows.length" :class="['dt-meta', wide && 'dt-meta--wide']">
    <template v-for="row in rows" :key="row.label">
      <dt class="dt-meta__label">{{ row.label }}</dt>
      <dd class="dt-meta__value">
        <template v-for="(part, i) in row.parts" :key="i">
          <img v-if="part.arrow" class="dt-meta__arrow" src="/img/ico-arrow.svg" alt="" />
          <span>{{ part.text }}</span>
        </template>
      </dd>
    </template>
  </dl>
</template>

<script setup lang="ts">
import type { MetaRow } from "~/utils/detailView";

defineProps<{
  rows: readonly MetaRow[];
  /** 라벨이 긴 표(표제/저자사항 등) — 라벨 열을 넓힌다 */
  wide?: boolean;
}>();
</script>
