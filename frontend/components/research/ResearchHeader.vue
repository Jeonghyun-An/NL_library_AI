<!-- frontend/components/research/ResearchHeader.vue -->
<template>
  <header class="rs-head">
    <div class="rs-head__main">
      <p class="rs-head__kicker">{{ DEEP_RESEARCH }}</p>
      <h1 class="rs-head__question">{{ question }}</h1>
      <div class="rs-head__meta">
        <span class="rs-status" :class="`rs-status--${phase}`">{{ phaseLabel(phase) }}</span>
        <!-- 그 잡의 탐색 방식(spec D28) — 방식을 모르는 잡(06c 전 잡·params 없음·두 칸이 갈림)은 그리지 않는다 -->
        <span v-if="modeLine" class="rs-head__mode">{{ modeLine }}</span>
      </div>
    </div>
    <div class="rs-head__actions">
      <button v-if="canToggle" type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="$emit('toggle-layout')">
        {{ layout === "A" ? "문서형으로 보기" : "2단으로 보기" }}
      </button>
      <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="$emit('copy-link')">링크 복사</button>
      <button v-if="cancellable" type="button" class="rs-btn rs-btn--ghost rs-btn--small" :disabled="busy" @click="$emit('cancel')">
        취소
      </button>
      <button v-if="phase === 'failed' && canRetry" type="button" class="rs-btn rs-btn--small" :disabled="busy" @click="$emit('retry')">
        다시 시도
      </button>
      <button v-if="restartable" type="button" class="rs-btn rs-btn--small" :disabled="busy" @click="$emit('restart')">
        같은 질문으로 다시 시작
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { DEEP_RESEARCH } from "~/utils/brand";
import { phaseLabel, type ResearchPhase } from "~/utils/researchEvents";
import type { ResearchLayout } from "~/utils/researchLayout";

const props = defineProps<{
  question: string;
  phase: ResearchPhase;
  layout: ResearchLayout;
  canToggle: boolean;
  canRetry: boolean;
  busy: boolean;
  // '탐색 방식 · 정밀하게' 꼴(researchModeLine) — 없거나 null 이면 그리지 않는다
  modeLine?: string | null;
}>();
defineEmits<{ "toggle-layout": []; "copy-link": []; cancel: []; retry: []; restart: [] }>();

const ACTIVE_PHASES: readonly ResearchPhase[] = ["planning", "awaiting", "queued", "exploring", "synthesizing"];

const cancellable = computed(() => ACTIVE_PHASES.includes(props.phase));
// 계획 없이 실패한 잡은 서버가 재시도를 받지 않는다(409) — 새 잡으로 다시 시작한다
const restartable = computed(() => props.phase === "canceled" || (props.phase === "failed" && !props.canRetry));
</script>
