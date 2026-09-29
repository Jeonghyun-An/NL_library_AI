<!-- frontend/components/research/ReportView.vue -->
<template>
  <article class="rs-card rs-report" :class="{ 'rs-report--draft': !!draft }">
    <header class="rs-report__head">
      <div>
        <p v-if="badge" class="rs-report__kicker">
          <span class="rs-badge rs-badge--draft" :class="{ 'rs-badge--live': badge.live }">{{ badge.label }}</span>
        </p>
        <h2 class="rs-report__question">{{ report.question }}</h2>
        <p v-if="range || generated" class="rs-report__meta">
          <span v-if="range">{{ range }}</span>
          <span v-if="generated">{{ generated }} 생성</span>
        </p>
      </div>
      <div class="rs-report__actions">
        <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="$emit('copy-link')">링크 복사</button>
        <slot name="actions" />
      </div>
    </header>

    <p class="rs-report__intro">{{ intro }}</p>

    <!-- 절 id 는 작성 현황 카드가 눌러 옮겨 오는 자리다. 초점도 받아 키보드로 옮긴 사람이 이어 읽는다 —
         초안이 같은 자리에서 최종본으로 바뀔 때 tabindex 가 빠지면 그 절에 있던 초점이 body 로 떨어지므로 최종본에도 둔다 -->
    <section
      v-for="row in rows"
      :id="`rs-sec-${row.idx}`"
      :key="row.idx"
      class="rs-section"
      :class="[`is-${row.state}`, { 'is-linked': highlightIdx === row.idx }]"
      tabindex="-1"
    >
      <h3 class="rs-section__heading">{{ row.idx + 1 }}. {{ row.heading }}</h3>
      <ReportSectionBody v-if="row.sec" :sec="row.sec" :evidence="report.evidence" @open-pdf="$emit('open-pdf', $event)" />
      <p v-else-if="draft?.state === 'interrupted'" class="rs-muted">작성을 마치지 못한 절입니다.</p>
      <p v-else-if="draft?.state === 'finishing'" class="rs-muted">이 절은 완성본에 실립니다.</p>
      <template v-else-if="row.state === 'running'">
        <p class="rs-muted">이 절을 쓰는 중입니다</p>
        <div class="rs-skeleton" aria-hidden="true">
          <span class="rs-skeleton__line" />
          <span class="rs-skeleton__line" />
          <span class="rs-skeleton__line" />
        </div>
      </template>
      <p v-else-if="row.state === 'failed'" class="rs-muted">이 절은 서술을 받지 못했습니다.</p>
      <p v-else class="rs-muted">작성 대기</p>
    </section>

    <section v-if="!draft" class="rs-limits" aria-labelledby="rs-limits-title">
      <h3 id="rs-limits-title" class="rs-limits__title">이 보고서의 한계</h3>
      <ul v-if="report.limitations.length">
        <li v-for="(line, li) in report.limitations" :key="li">{{ line }}</li>
      </ul>
      <p v-else class="rs-muted">{{ NO_LIMITS }}</p>
    </section>

    <!-- 자기점검이 걸러낸 논문을 버리지 않고 보인다 — 무엇을 왜 뺐는지 보여야 결과가 줄어든 것으로 읽히지 않는다.
         본문이 인용한 논문이 아니라 접어 둔다. 초안은 탐색 타임라인에서 같은 목록을 만든다 -->
    <section v-if="excluded.length" class="rs-excluded" aria-labelledby="rs-excluded-title">
      <h3 id="rs-excluded-title" class="rs-excluded__title">
        <button
          type="button"
          class="rs-excluded__toggle"
          :aria-expanded="excludedOpen"
          aria-controls="rs-excluded-body"
          @click="excludedOpen = !excludedOpen"
        >
          {{ EXCLUDED_TITLE }} ({{ excludedCount }})<span class="rs-caret" aria-hidden="true">▾</span>
        </button>
      </h3>
      <div v-show="excludedOpen" id="rs-excluded-body" class="rs-excluded__body">
        <p class="rs-muted">{{ EXCLUDED_WHY }}</p>
        <div v-for="g in excluded" :key="g.subqIdx" class="rs-excluded__group">
          <h4 class="rs-section__sub">{{ g.subqIdx + 1 }}. {{ g.subquestion }}</h4>
          <ul class="rs-excluded-list">
            <li v-for="p in g.papers" :key="p.cntsId">
              <a :href="`/papers/${p.cntsId}`" target="_blank" rel="noopener">
                {{ excludedPaperLine(p) }}<span class="rs-sr-only"> (새 창)</span>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { OpenPdfPayload, ReportSection, ResearchReport } from "~/types/research";
import type { DraftSlot, DraftSlotStatus } from "~/utils/researchDraft";
import {
  EXCLUDED_TITLE,
  EXCLUDED_WHY,
  NO_LIMITS,
  draftBadge,
  draftIntro,
  excludedFromTrail,
  excludedPaperLine,
  rangeLabel,
  reportIntro,
  type DraftState,
  type ExcludedGroup,
} from "~/utils/researchReport";
import ReportSectionBody from "./ReportSectionBody.vue";

interface SectionRow {
  idx: number;
  heading: string;
  state: DraftSlotStatus;
  sec: ReportSection | null;
}

const props = withDefaults(
  defineProps<{
    report: ResearchReport;
    generatedAt: string | null;
    draft?: { slots: DraftSlot[]; state: DraftState; excluded: ExcludedGroup[] } | null;
    highlightIdx?: number | null;
  }>(),
  { draft: null, highlightIdx: null },
);
defineEmits<{ "open-pdf": [payload: OpenPdfPayload]; "copy-link": [] }>();

const range = computed(() => rangeLabel(props.report.range));
const badge = computed(() => (props.draft ? draftBadge(props.draft.state) : null));
const intro = computed(() =>
  props.draft ? draftIntro(props.draft.slots, props.draft.state, props.report.stats) : reportIntro(props.report),
);
const generated = computed(() => {
  if (!props.generatedAt) return "";
  const d = new Date(props.generatedAt);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
});

// 최종본은 절 순서 그대로, 초안은 아직 쓰지 않은 절까지 자리를 잡아 둔다 — 절이 끝나도 뒤 절이 밀리지 않는다
const rows = computed<SectionRow[]>(() => {
  const sections = props.report.sections;
  if (!props.draft) return sections.map((sec, si) => ({ idx: si, heading: sec.heading, state: "done", sec }));
  return props.draft.slots.map((slot) => ({
    idx: slot.idx,
    heading: slot.heading,
    state: slot.status,
    sec: slot.sectionIndex !== null ? (sections[slot.sectionIndex] ?? null) : null,
  }));
});

// 최종본은 보고서 trail 에서, 초안은 탐색 타임라인에서 만든 목록이다(초안에는 trail 이 없다)
const excluded = computed<ExcludedGroup[]>(() =>
  props.draft ? props.draft.excluded : excludedFromTrail(props.report.trail),
);
const excludedCount = computed(() => excluded.value.reduce((n, g) => n + g.papers.length, 0));
// 초안이 같은 자리에서 최종본으로 바뀌어도 이 부품은 그대로라 펼친 상태가 이어진다
const excludedOpen = ref(false);
</script>
