<!-- frontend/components/research/ReportSkeleton.vue -->
<template>
  <!-- 승인 뒤(대기열·탐색·종합 첫 절 전) 본문에 세우는 보고서의 자리. 하위질문마다 한 자리이고 근거가 모이면
       '근거 N편 ✓'을 찍는다. 자리 번호는 하위질문 번호다 — 근거가 없는 하위질문은 절이 되지 않아 절 번호와 다르므로
       'N.' 대신 작은 '하위질문 N'을 단다. 첫 절이 완성되면 이 자리 대신 초안(ReportView)이 선다.
       자리 id(rs-slot-N)는 지금 진행하는 곳 따라가기가 옮겨 오는 자리다 — rs-section 이라 고정 막대 밑 여백도 함께 받는다 -->
  <article class="rs-card rs-report rs-report--slots" aria-labelledby="rs-slots-title">
    <header class="rs-report__head">
      <div>
        <h2 id="rs-slots-title" class="rs-report__question">보고서 자리</h2>
        <p class="rs-muted">하위질문마다 근거를 모으면 그 자리에 절이 쓰입니다.</p>
      </div>
    </header>

    <section
      v-for="s in slots"
      :id="slotElementId(s.subqIdx)"
      :key="s.subqIdx"
      class="rs-section rs-slot"
      :class="`is-${s.state}`"
      tabindex="-1"
    >
      <p class="rs-slot__kicker">하위질문 {{ s.subqIdx + 1 }}</p>
      <h3 class="rs-section__heading">{{ s.title }}</h3>
      <span class="rs-slot__state" :class="{ 'is-fresh': fresh.includes(s.subqIdx) }">{{ planSlotLabel(s) }}</span>
      <!-- 아직 쓰이지 않은 자리만 줄 모양을 둔다. 근거 없음은 한 줄로 접고, 근거를 모은 자리는 상태 글이 대신한다 -->
      <div v-if="SKELETON_STATES.includes(s.state)" class="rs-skeleton" aria-hidden="true">
        <span class="rs-skeleton__line" />
        <span class="rs-skeleton__line" />
        <span class="rs-skeleton__line" />
      </div>
    </section>
  </article>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { newlyCollected, planSlotLabel, slotElementId, type PlanSlot, type PlanSlotState } from "~/utils/planSlots";

const props = defineProps<{ slots: PlanSlot[] }>();

const SKELETON_STATES: readonly PlanSlotState[] = ["waiting", "collecting", "writing"];
// '근거 N편 ✓'이 튀어 오르는 시간(research.css 의 rs-pop 과 맞춘다 — SynthProgressCard 와 같다)
const FRESH_MS = 900;

const fresh = ref<number[]>([]);
let prev: Map<number, PlanSlotState> | null = null;
let freshTimer: ReturnType<typeof setTimeout> | null = null;

// 효과는 실제 이벤트가 자리를 바꿨을 때만이다 — 처음 그릴 때(다시 연 화면)는 prev 가 없어 튀어 오르지 않는다
watch(
  () => props.slots,
  (slots) => {
    const idxs = newlyCollected(prev, slots);
    prev = new Map(slots.map((s) => [s.subqIdx, s.state]));
    if (!idxs.length) return;
    fresh.value = idxs;
    if (freshTimer) clearTimeout(freshTimer);
    freshTimer = setTimeout(() => {
      fresh.value = [];
    }, FRESH_MS);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (freshTimer) clearTimeout(freshTimer);
});
</script>
