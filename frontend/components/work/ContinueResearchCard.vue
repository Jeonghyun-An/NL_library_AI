<!-- frontend/components/work/ContinueResearchCard.vue -->
<template>
  <!-- 최종 보고서 끝(ReportView 의 footer 자리) — 이어가기는 완료된 잡만 받는다. 누른 뒤의 일은 연구 화면이 한다 -->
  <section class="rs-card wk-continue" aria-labelledby="wk-continue-title">
    <div class="rs-card__head">
      <h2 id="wk-continue-title" class="rs-card__title">
        {{ view.title }} <span class="wk-beta">{{ BETA_LABEL }}</span>
      </h2>
      <p class="rs-muted">{{ view.body }}</p>
    </div>
    <ol class="wk-continue__steps" aria-label="연구 단계 미리보기">
      <li v-for="(s, i) in view.preview" :key="s.label" class="wk-continue__step" :class="`is-${s.state}`">
        <span class="wk-stepper__no" aria-hidden="true">{{ i + 1 }}</span>{{ s.label }}
      </li>
    </ol>
    <p v-if="view.note" class="rs-muted">{{ view.note }}</p>
    <SkxInlineError v-if="error" :message="error" />
    <div class="rs-card__actions">
      <button type="button" class="rs-btn" :disabled="busy" :aria-busy="busy" @click="act">
        {{ view.label }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { WorkView } from "~/types/work";
import { BETA_LABEL, continueCard } from "~/utils/workPhase";

// written — 보고서 절을 다 썼다(머리 단계 줄과 같은 말을 쓴다)
const props = defineProps<{
  exists: boolean | null;
  work: WorkView | null;
  busy: boolean;
  error: string | null;
  written?: boolean;
}>();
const emit = defineEmits<{ continue: []; open: [] }>();

const view = computed(() => continueCard(props.exists, props.work, props.written));

function act(): void {
  if (props.busy) return;
  if (view.value.action === "continue") emit("continue");
  else emit("open");
}
</script>
