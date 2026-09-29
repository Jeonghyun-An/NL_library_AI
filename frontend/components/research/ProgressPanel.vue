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
        <!-- 자기점검이 걸러낸 수 — 채택 수만 보이면 무관 제외로 결과가 줄어든 것처럼 읽힌다. 제외 수를 모르는 옛 잡은 칸을 그리지 않는다 -->
        <div v-if="view.counters.excluded !== null" class="rs-counter">
          <dt>제외</dt>
          <dd>{{ shown(view.counters.excluded) }}</dd>
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
          :class="[`is-${sq.status}`, { 'is-stopped': stoppedSubq?.idx === sq.idx }]"
        >
          <div class="rs-subq__head">
            <span class="rs-subq__no">{{ sq.idx + 1 }}</span>
            <span class="rs-subq__title">{{ sq.title }}</span>
            <span class="rs-badge" :class="`rs-badge--${sq.status}`">{{ subqStatusLabel(sq) }}</span>
          </div>
          <p v-if="stoppedSubq && stoppedSubq.idx === sq.idx" class="rs-subq__stopped">
            {{ stoppedSubq.started ? "여기서 멈췄습니다" : "이 하위질문을 시작하기 전에 멈췄습니다" }}<span v-if="stoppedSubq.error"> — {{ stoppedSubq.error }}</span>
          </p>
          <ol v-if="sq.rounds.length" class="rs-rounds">
            <li v-for="r in sq.rounds" :key="r.round" class="rs-round" :class="{ 'is-recheck': !!r.nextQuery }">
              <p class="rs-round__line">
                <span class="rs-round__no">{{ r.round }}회차</span>
                <span class="rs-round__query">‘{{ r.query }}’</span>
                <span v-if="r.foundChunks !== null" class="rs-round__stat">대목 {{ r.foundChunks }}개</span>
                <span v-if="r.newPapers !== null" class="rs-round__stat">새 논문 {{ r.newPapers }}편</span>
                <!-- 뺀 논문 목록이 있으면 눌러 펼친다. 목록 없이 수만 있는 회차(목록을 기록하기 전 잡)는 글자만 둔다 -->
                <button
                  v-if="r.excludedPapers.length"
                  type="button"
                  class="rs-round__toggle"
                  :aria-expanded="isOpen(sq.idx, r.round)"
                  :aria-controls="panelId(sq.idx, r.round)"
                  @click="toggleRound(sq.idx, r.round)"
                >
                  {{ excludedLabel(r.excludedPapers.length) }}<span class="rs-caret" aria-hidden="true">▾</span>
                </button>
                <span v-else-if="excludedLabel(r.excluded)" class="rs-round__stat">{{ excludedLabel(r.excluded) }}</span>
                <span v-if="flaggedLabel(r.flagged)" class="rs-round__stat">{{ flaggedLabel(r.flagged) }}</span>
              </p>
              <div
                v-if="r.excludedPapers.length"
                v-show="isOpen(sq.idx, r.round)"
                :id="panelId(sq.idx, r.round)"
                class="rs-round__excluded"
              >
                <p class="rs-round__why">
                  자기점검이 이 하위질문의 핵심 개념과 무관하다고 판단했습니다<span v-if="r.note"> — {{ r.note }}</span>
                </p>
                <ul class="rs-excluded-list">
                  <li v-for="p in r.excludedPapers" :key="p.cntsId">
                    <a :href="`/papers/${p.cntsId}`" target="_blank" rel="noopener">
                      {{ excludedPaperLine(p) }}<span class="rs-sr-only"> (새 창)</span>
                    </a>
                  </li>
                </ul>
              </div>
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
import { computed, shallowRef, useId } from "vue";
import type { ResearchView } from "~/types/research";
import {
  excludedLabel,
  flaggedLabel,
  stopPoint,
  subqStatusLabel,
  synthProgress,
  verdictLabel,
  type ResearchPhase,
} from "~/utils/researchEvents";
import { excludedPaperLine } from "~/utils/researchReport";

const props = defineProps<{ view: ResearchView; phase: ResearchPhase }>();

const TITLES: Partial<Record<ResearchPhase, string>> = {
  synthesizing: "탐색 완료 요약",
  completed: "탐색 경로",
  failed: "멈춘 지점",
  canceled: "멈춘 지점",
};

const title = computed(() => TITLES[props.phase] ?? "진행");
const stop = computed(() => stopPoint(props.view));
const stoppedSubq = computed(() => (stop.value?.kind === "subq" ? stop.value : null));
const synthLine = computed(() => {
  const p = synthProgress(props.view);
  return p.total ? `보고서 작성 중 ${p.current}/${p.total}` : "보고서 작성 중";
});

function shown(n: number | null): string {
  return n === null ? "—" : n.toLocaleString("ko-KR");
}

// 펼친 회차("하위질문:회차"). 이벤트가 올 때마다 타임라인이 다시 그려져도 사용자가 펼친 회차는 펼친 채로 둔다.
// 집합을 통째로 바꿔 알리므로 깊은 반응성은 필요 없다
const openRounds = shallowRef(new Set<string>());
const uid = useId();

function roundKey(subqIdx: number, round: number): string {
  return `${subqIdx}:${round}`;
}

function isOpen(subqIdx: number, round: number): boolean {
  return openRounds.value.has(roundKey(subqIdx, round));
}

function toggleRound(subqIdx: number, round: number): void {
  const next = new Set(openRounds.value);
  const key = roundKey(subqIdx, round);
  if (!next.delete(key)) next.add(key);
  openRounds.value = next;
}

function panelId(subqIdx: number, round: number): string {
  return `${uid}-excluded-${subqIdx}-${round}`;
}
</script>
