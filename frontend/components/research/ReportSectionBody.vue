<!-- frontend/components/research/ReportSectionBody.vue -->
<!-- 절 본문(도입·대표 논문·향후 과제). 최종본과 작성 중 초안이 같은 부품으로 그려야 두 화면의 글이 갈리지 않는다 -->
<template>
  <div class="rs-section__body">
    <p v-if="sec.intro" class="rs-section__intro">
      <template v-for="(part, pi) in splitCitations(sec.intro)" :key="pi">
        <template v-if="part.type === 'text'">{{ part.text }}</template>
        <CitationChip
          v-else
          :eid="part.eid"
          :evidence="evidence[part.eid]"
          :chunks="citeChunks(sec, evidence[part.eid], part.eid)"
          @open-pdf="$emit('open-pdf', $event)"
        />
      </template>
    </p>
    <p v-else class="rs-muted">{{ INTROLESS }}</p>

    <template v-if="sec.papers.length">
      <h4 class="rs-section__sub">대표 논문</h4>
      <ul class="rs-papers">
        <li v-for="p in sec.papers" :key="p.cnts_id" class="rs-paper">
          <span class="rs-paper__who">{{ paperByline(paperMeta(p)) }}</span>
          <span v-if="paperMeta(p)?.title" class="rs-paper__title">{{ paperMeta(p)?.title }}</span>
          <span class="rs-paper__summary">{{ p.summary || NO_SUMMARY }}</span>
          <CitationChip
            v-for="eid in p.evidence"
            :key="eid"
            :eid="eid"
            :evidence="evidence[eid]"
            :chunks="citeChunks(sec, evidence[eid], eid)"
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
              :evidence="evidence[part.eid]"
              :chunks="citeChunks(sec, evidence[part.eid], part.eid)"
              @open-pdf="$emit('open-pdf', $event)"
            />
          </template>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EvidenceMeta, OpenPdfPayload, ReportEvidence, ReportPaper, ReportSection } from "~/types/research";
import { citeChunks, splitCitations } from "~/utils/citations";
import { INTROLESS, NO_SUMMARY, paperByline } from "~/utils/researchReport";
import CitationChip from "./CitationChip.vue";

const props = defineProps<{ sec: ReportSection; evidence: Record<string, ReportEvidence> }>();
defineEmits<{ "open-pdf": [payload: OpenPdfPayload] }>();

function paperMeta(p: ReportPaper): EvidenceMeta | undefined {
  return props.evidence[p.evidence[0] ?? ""]?.meta;
}
</script>
