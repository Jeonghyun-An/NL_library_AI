<!-- frontend/components/research/ProgressPanel.vue -->
<template>
  <section class="rs-card rs-progress">
    <h2 class="rs-card__title">{{ title }}</h2>

    <p v-if="phase === 'planning'" class="rs-muted">계획이 확정되면 탐색 과정이 여기에 나타납니다.</p>
    <p v-else-if="phase === 'awaiting'" class="rs-muted">
      계획을 승인하면 하위질문마다 논문을 찾고, 근거가 부족하다고 판단하면 검색어를 바꿔 다시 찾습니다.
    </p>
    <p v-else-if="phase === 'queued'" class="rs-muted">대기열에 들어갔습니다. 앞선 연구가 끝나면 시작합니다.</p>

    <template v-else>
      <dl class="rs-counters">
        <div class="rs-counter">
          <dt>검토한 논문</dt>
          <dd>{{ shown(view.counters.papersReviewed) }}</dd>
        </div>
        <div class="rs-counter">
          <dt>채택한 근거</dt>
          <dd>{{ shown(view.counters.evidenceAdopted) }}</dd>
        </div>
        <div class="rs-counter">
          <dt>재검색</dt>
          <dd>{{ shown(view.counters.rechecks) }}</dd>
        </div>
      </dl>

      <div v-if="phase === 'exploring' && view.highlight" class="rs-highlight" role="status" aria-live="polite">
        <p class="rs-highlight__kicker">자기점검 · 하위질문 {{ view.highlight.subqIdx + 1 }} · {{ view.highlight.round }}회차</p>
        <p class="rs-highlight__main">근거 부족 → ‘{{ view.highlight.nextQuery }}’(으)로 재검색</p>
        <p v-if="view.highlight.note" class="rs-highlight__note">{{ view.highlight.note }}</p>
      </div>

      <p v-if="phase === 'synthesizing'" class="rs-progress__synth">{{ synthLine }}</p>
      <p v-if="view.source === 'trail' || view.source === 'queries'" class="rs-muted rs-progress__note">
        회차별 판정을 기록하기 전에 만든 연구라, 검색어 이력과 마지막 판정만 보여 줍니다.
      </p>

      <ol class="rs-timeline">
        <li
          v-for="sq in view.subqs"
          :key="sq.idx"
          class="rs-subq"
          :class="[`is-${sq.status}`, { 'is-stopped': stoppedIdx === sq.idx }]"
        >
          <div class="rs-subq__head">
            <span class="rs-subq__no">{{ sq.idx + 1 }}</span>
            <span class="rs-subq__title">{{ sq.title }}</span>
            <span class="rs-badge" :class="`rs-badge--${sq.status}`">{{ subqStatusLabel(sq) }}</span>
          </div>
          <p v-if="stoppedIdx === sq.idx" class="rs-subq__stopped">
            {{ sq.status === "pending" ? "이 하위질문을 시작하기 전에 멈췄습니다" : "여기서 멈췄습니다" }}<span v-if="sq.error"> — {{ sq.error }}</span>
          </p>
          <ol v-if="sq.rounds.length" class="rs-rounds">
            <li v-for="r in sq.rounds" :key="r.round" class="rs-round" :class="{ 'is-recheck': !!r.nextQuery }">
              <p class="rs-round__line">
                <span class="rs-round__no">{{ r.round }}회차</span>
                <span class="rs-round__query">‘{{ r.query }}’</span>
                <span v-if="r.foundChunks !== null" class="rs-round__stat">대목 {{ r.foundChunks }}개</span>
                <span v-if="r.newPapers !== null" class="rs-round__stat">새 논문 {{ r.newPapers }}편</span>
              </p>
              <p v-if="r.verdict" class="rs-round__verdict">
                {{ verdictLabel(r.verdict) }}<span v-if="r.note"> — {{ r.note }}</span>
              </p>
              <p v-if="r.nextQuery" class="rs-round__next">→ ‘{{ r.nextQuery }}’(으)로 재검색</p>
            </li>
          </ol>
        </li>
      </ol>
      <p v-if="stop?.kind === 'synth'" class="rs-subq__stopped">보고서 작성 단계에서 멈췄습니다</p>
      <p v-else-if="stop?.kind === 'before'" class="rs-subq__stopped">탐색을 시작하기 전에 멈췄습니다</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ResearchView } from "~/types/research";
import { stopPoint, subqStatusLabel, synthProgress, verdictLabel, type ResearchPhase } from "~/utils/researchEvents";

const props = defineProps<{ view: ResearchView; phase: ResearchPhase }>();

const TITLES: Partial<Record<ResearchPhase, string>> = {
  synthesizing: "탐색 완료 요약",
  completed: "탐색 경로",
  failed: "멈춘 지점",
  canceled: "멈춘 지점",
};

const title = computed(() => TITLES[props.phase] ?? "진행");
const stop = computed(() => stopPoint(props.view));
const stoppedIdx = computed(() => (stop.value?.kind === "subq" ? stop.value.idx : null));
const synthLine = computed(() => {
  const p = synthProgress(props.view);
  return p.total ? `보고서 작성 중 ${p.current}/${p.total}` : "보고서 작성 중";
});

function shown(n: number | null): string {
  return n === null ? "—" : n.toLocaleString("ko-KR");
}
</script>
