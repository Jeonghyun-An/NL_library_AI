<!-- frontend/components/research/ReportSectionBody.vue -->
<!-- 절 본문(도입·대표 논문·향후 과제). 최종본과 작성 중 초안이 같은 부품으로 그려야 두 화면의 글이 갈리지 않는다 -->
<template>
  <div class="rs-section__body">
    <p v-if="sec.intro" class="rs-section__intro">
      <template v-for="(part, pi) in cites.intro" :key="pi">
        <template v-if="part.type === 'text'">{{ part.text }}</template>
        <CitationChip
          v-else
          :eid="part.eid"
          :anchor="part.anchor"
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
        <li v-for="row in cites.papers" :key="row.paper.cnts_id" class="rs-paper">
          <span class="rs-paper__who">{{ paperByline(paperMeta(row.paper)) }}</span>
          <span v-if="paperMeta(row.paper)?.title" class="rs-paper__title">{{ paperMeta(row.paper)?.title }}</span>
          <span class="rs-paper__summary">{{ row.paper.summary || NO_SUMMARY }}</span>
          <CitationChip
            v-for="c in row.chips"
            :key="c.anchor"
            :eid="c.eid"
            :anchor="c.anchor"
            :evidence="evidence[c.eid]"
            :chunks="citeChunks(sec, evidence[c.eid], c.eid)"
            @open-pdf="$emit('open-pdf', $event)"
          />
        </li>
      </ul>
    </template>

    <template v-if="sec.future.length">
      <h4 class="rs-section__sub">향후 과제</h4>
      <ul class="rs-future">
        <li v-for="(parts, fi) in cites.future" :key="fi">
          <template v-for="(part, pi) in parts" :key="pi">
            <template v-if="part.type === 'text'">{{ part.text }}</template>
            <CitationChip
              v-else
              :eid="part.eid"
              :anchor="part.anchor"
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
import { computed } from "vue";
import type { EvidenceMeta, OpenPdfPayload, ReportEvidence, ReportPaper, ReportSection } from "~/types/research";
import { citeChunks } from "~/utils/citations";
import { anchoredSection } from "~/utils/detailSource";
import { INTROLESS, NO_SUMMARY, paperByline } from "~/utils/researchReport";
import CitationChip from "./CitationChip.vue";

// sectionIdx: 보고서에 보이는 절 번호(0부터) — 칩 앵커는 이 번호로 돌아올 자리를 찾는다
const props = defineProps<{ sec: ReportSection; sectionIdx: number; evidence: Record<string, ReportEvidence> }>();
defineEmits<{ "open-pdf": [payload: OpenPdfPayload] }>();

// 칩마다 돌아올 자리의 앵커를 붙인 본문 조각 — 같은 절의 같은 근거는 그리는 순서로 가른다
const cites = computed(() => anchoredSection(props.sec, props.sectionIdx));

function paperMeta(p: ReportPaper): EvidenceMeta | undefined {
  return props.evidence[p.evidence[0] ?? ""]?.meta;
}
</script>
