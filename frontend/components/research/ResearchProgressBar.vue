<!-- frontend/components/research/ResearchProgressBar.vue -->
<template>
  <!-- 연구 화면 위에 고정되는 큰 진행 막대(spec §12-3 고정 진행 영역·Q1). 보기는 utils/researchProgress.ts 의
       progressBarView 가 만들고 여기서는 그리기만 한다. aria-live 는 두지 않는다 — 1초마다 바뀌는 퍼센트를 읽어 대지 않게
       (절이 끝날 때의 알림은 현황 카드·근거 장부가 한다) -->
  <div class="rs-pbar" role="group" aria-label="연구 진행">
    <!-- 단계 칩 — 번호(01~04)·끝난 단계는 ✓·지금 단계는 산호 테두리에 작은 꼬리표('진행 중'·'승인 대기'·'순서 대기'). 후배 시안의
         박스 단계의 좋은 점만 한 줄 높이 그대로 옮겼다(사용자 결정 2026-10-14 — 박스는 막대와 같은 말을 두 번 하고 고정 영역을 키운다) -->
    <ol class="rs-pbar__stages">
      <li
        v-for="(s, i) in view.stages"
        :key="s.key"
        class="rs-pbar__stage"
        :class="`is-${s.state}`"
        :aria-current="s.state === 'current' ? 'step' : undefined"
      >
        <span class="rs-pbar__num" aria-hidden="true">{{ s.state === "done" ? "✓" : String(i + 1).padStart(2, "0") }}</span>
        {{ s.label }}<span v-if="s.state === 'done'" class="rs-sr-only"> (끝남)</span>
        <span v-if="s.state === 'current'" class="rs-pbar__tag">{{ tag }}</span>
      </li>
    </ol>
    <div class="rs-pbar__line">
      <p class="rs-pbar__text" :title="view.line">{{ view.line }}</p>
      <p v-if="view.percent !== null" class="rs-pbar__pct">{{ view.percent }}%</p>
    </div>
    <div
      class="rs-pbar__track"
      role="progressbar"
      aria-label="연구 진행"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="view.percent ?? undefined"
      :aria-valuetext="view.valueText"
    >
      <span class="rs-pbar__fill" :class="{ 'is-running': view.running }" :style="{ width: `${width}%` }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ProgressBarView } from "~/utils/researchProgress";

const props = withDefaults(defineProps<{ view: ProgressBarView; tag?: string }>(), { tag: "진행 중" });

// 채움 폭은 0.1% 단위 — 1초마다 다시 재는 폭을 같은 1초 transition 으로 이어 붙인다(research.css .rs-pbar__fill)
const width = computed(() => Math.round(props.view.fraction * 1000) / 10);
</script>
