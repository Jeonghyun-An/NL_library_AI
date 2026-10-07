<!-- frontend/components/work/CandidateDrawer.vue -->
<template>
  <details class="wk-drawer">
    <summary class="wk-drawer__summary">critic 이 뺀 논문 {{ excluded.length }}편</summary>
    <p class="rs-muted">
      탐색 중 자기점검(critic)이 하위질문과 무관하다고 보고 뺀 논문입니다. 논문별 사유는 남지 않아 뺀 회차와 그 회차의
      critic 메모를 함께 보입니다. [되살리기] 를 누르면 읽기 후보로 들어옵니다 — 보고서는 바뀌지 않습니다.
    </p>
    <section v-for="group in groups" :key="group.subqIdx" class="wk-drawer__group">
      <h4 class="wk-drawer__subq">하위질문 {{ group.subqIdx + 1 }} · {{ group.subquestion }}</h4>
      <ul class="wk-drawer__list">
        <li v-for="c in group.items" :key="c.cnts_id" class="wk-drawer__item">
          <span class="wk-drawer__line">{{ candidateLine(c) }}</span>
          <span v-if="candidateNote(c)" class="rs-muted">{{ candidateNote(c) }}</span>
          <button
            type="button"
            class="rs-btn rs-btn--small rs-btn--ghost"
            :disabled="readOnly || busy || reviving.has(c.cnts_id)"
            @click="revive(c.cnts_id)"
          >
            되살리기
          </button>
        </li>
      </ul>
    </section>
  </details>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ExcludedCandidate } from "~/types/work";
import { candidateGroups, candidateLine, candidateNote } from "~/utils/readingList";

// 후보 서랍의 'critic 이 뺀 논문' 묶음(spec §5-4 ②). [되살리기] 는 의도만 emit 하고 PUT(새 행, origin revived)은 ReadingStep 이 한다
const props = defineProps<{ excluded: ExcludedCandidate[]; readOnly: boolean; busy: boolean }>();
const emit = defineEmits<{ revive: [cnts: string] }>();

const groups = computed(() => candidateGroups(props.excluded));
// 누른 논문 — 다시 읽은 목록이 오면 풀린다(되살린 논문은 서랍에서 빠지고, 실패면 그대로 남아 다시 누를 수 있다)
const reviving = ref(new Set<string>());
watch(
  () => props.excluded,
  () => {
    reviving.value = new Set();
  },
);

function revive(cnts: string): void {
  if (props.readOnly || reviving.value.has(cnts)) return;
  reviving.value.add(cnts);
  emit("revive", cnts);
}
</script>
