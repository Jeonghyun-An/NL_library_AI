<!-- frontend/components/research/ReportView.vue -->
<template>
  <article class="rs-card rs-report">
    <header class="rs-report__head">
      <div>
        <h2 class="rs-report__question">{{ report.question }}</h2>
        <p class="rs-report__meta">
          <span v-if="range">{{ range }}</span>
          <span v-if="generated">{{ generated }} 생성</span>
        </p>
      </div>
      <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="$emit('copy-link')">링크 복사</button>
    </header>

    <p class="rs-report__intro">{{ intro }}</p>

    <section v-for="(sec, si) in report.sections" :key="si" class="rs-section">
      <h3 class="rs-section__heading">{{ si + 1 }}. {{ sec.heading }}</h3>
      <p v-if="sec.intro" class="rs-section__intro">
        <template v-for="(part, pi) in splitCitations(sec.intro)" :key="pi">
          <template v-if="part.type === 'text'">{{ part.text }}</template>
          <CitationChip
            v-else
            :eid="part.eid"
            :evidence="report.evidence[part.eid]"
            :chunks="citeChunks(sec, report.evidence[part.eid], part.eid)"
            @open-pdf="$emit('open-pdf', $event)"
          />
        </template>
      </p>
      <p v-else class="rs-muted">이 절은 도입 서술을 받지 못했습니다. 아래 논문 목록만 싣습니다.</p>

      <template v-if="sec.papers.length">
        <h4 class="rs-section__sub">대표 논문</h4>
        <ul class="rs-papers">
          <li v-for="p in sec.papers" :key="p.cnts_id" class="rs-paper">
            <span class="rs-paper__who">{{ paperByline(paperMeta(p)) }}</span>
            <span v-if="paperMeta(p)?.title" class="rs-paper__title">{{ paperMeta(p)?.title }}</span>
            <span class="rs-paper__summary">{{ p.summary || "요약을 받지 못했습니다." }}</span>
            <CitationChip
              v-for="eid in p.evidence"
              :key="eid"
              :eid="eid"
              :evidence="report.evidence[eid]"
              :chunks="citeChunks(sec, report.evidence[eid], eid)"
              @open-pdf="$emit('open-pdf', $event)"
            />
          </li>
        </ul>
      </template>

      <template v-if="sec.future.length">
        <h4 class="rs-section__sub">향후 과제</h4>
        <ul class="rs-future">
          <li v-for="(f, fi) in sec.future" :key="fi">
            <template v-for="(part, pi) in splitCitations(f.text)" :key="pi">
              <template v-if="part.type === 'text'">{{ part.text }}</template>
              <CitationChip
                v-else
                :eid="part.eid"
                :evidence="report.evidence[part.eid]"
                :chunks="citeChunks(sec, report.evidence[part.eid], part.eid)"
                @open-pdf="$emit('open-pdf', $event)"
              />
            </template>
          </li>
        </ul>
      </template>
    </section>

    <section class="rs-limits" aria-labelledby="rs-limits-title">
      <h3 id="rs-limits-title" class="rs-limits__title">이 보고서의 한계</h3>
      <ul v-if="report.limitations.length">
        <li v-for="(line, li) in report.limitations" :key="li">{{ line }}</li>
      </ul>
      <p v-else class="rs-muted">자동 점검에서 보고할 한계가 발견되지 않았습니다.</p>
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { EvidenceMeta, OpenPdfPayload, ReportPaper, ResearchReport } from "~/types/research";
import { citeChunks, splitCitations } from "~/utils/citations";
import { paperByline, rangeLabel, reportIntro } from "~/utils/researchReport";
import CitationChip from "./CitationChip.vue";

const props = defineProps<{ report: ResearchReport; generatedAt: string | null }>();
defineEmits<{ "open-pdf": [payload: OpenPdfPayload]; "copy-link": [] }>();

const range = computed(() => rangeLabel(props.report.range));
const intro = computed(() => reportIntro(props.report));
const generated = computed(() => {
  if (!props.generatedAt) return "";
  const d = new Date(props.generatedAt);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
});

function paperMeta(p: ReportPaper): EvidenceMeta | undefined {
  return props.report.evidence[p.evidence[0] ?? ""]?.meta;
}
</script>
