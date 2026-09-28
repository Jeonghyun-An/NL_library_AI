<!-- frontend/components/research/SynthProgressCard.vue -->
<template>
  <section class="rs-card rs-synth" aria-labelledby="rs-synth-title">
    <header class="rs-synth__head">
      <div class="rs-card__head">
        <h2 id="rs-synth-title" class="rs-card__title">보고서 작성 현황</h2>
        <p class="rs-synth__summary">{{ summary }}</p>
      </div>
      <div class="rs-synth__actions">
        <slot name="actions" />
      </div>
    </header>

    <div
      class="rs-synth__bar"
      role="progressbar"
      aria-label="보고서 작성 진행"
      aria-valuemin="0"
      :aria-valuemax="eta.total || 1"
      :aria-valuenow="Math.min(eta.done, eta.total)"
      :aria-valuetext="summary"
    >
      <span class="rs-synth__fill" :class="{ 'is-running': eta.runningIdx !== null }" :style="{ width: `${percent}%` }" />
    </div>

    <ol v-if="slots.length" class="rs-synth__list">
      <li v-for="slot in slots" :key="slot.idx">
        <!-- 초안이 생기기 전(끝난 절이 없을 때)에는 옮겨 갈 곳이 없어 누를 수 없는 줄로 그린다 -->
        <component
          :is="canJump ? 'button' : 'div'"
          :type="canJump ? 'button' : undefined"
          class="rs-synth__item"
          :class="[`is-${slot.status}`, { 'is-linked': highlightIdx === slot.idx }]"
          :title="canJump ? '초안의 이 절로 이동' : undefined"
          @click="jump(slot.idx)"
          @pointerenter="hover({ kind: 'pointerenter', idx: slot.idx, pointerType: $event.pointerType })"
          @pointerleave="hover({ kind: 'pointerleave', idx: slot.idx })"
          @focus="hover({ kind: 'focus', idx: slot.idx })"
          @blur="hover({ kind: 'blur', idx: slot.idx })"
        >
          <span class="rs-synth__icon" :class="{ 'is-fresh': fresh.includes(slot.idx) }" aria-hidden="true">{{ ICONS[slot.status] }}</span>
          <span class="rs-synth__name">{{ slot.idx + 1 }}. {{ slot.heading }}</span>
          <span class="rs-synth__state">{{ slotStateLabel(slot, eta) }}</span>
        </component>
      </li>
    </ol>

    <!-- 절이 끝날 때 한 번만 읽힌다. 카드는 첫 절 전부터 떠 있어 알림 영역이 내용보다 먼저 생긴다 -->
    <p class="rs-sr-only" role="status" aria-live="polite">{{ announcement }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { DraftSlot, DraftSlotStatus, SynthEta } from "~/utils/researchDraft";
import {
  barFraction,
  finishedAnnouncement,
  newlyFinished,
  slotStateLabel,
  synthSummary,
  type SlotHoverEvent,
} from "~/utils/synthCard";

const props = withDefaults(defineProps<{ slots: DraftSlot[]; eta: SynthEta; highlightIdx?: number | null }>(), {
  highlightIdx: null,
});
const emit = defineEmits<{ jump: [idx: number]; hover: [event: SlotHoverEvent] }>();

const ICONS: Record<DraftSlotStatus, string> = { done: "✓", running: "", waiting: "·", failed: "✕" };
// 체크 표시가 튀어 오르는 시간(research.css 의 rs-pop 과 맞춘다)
const FRESH_MS = 900;

const summary = computed(() => synthSummary(props.eta));
const percent = computed(() => Math.round(barFraction(props.eta) * 1000) / 10);
const canJump = computed(() => props.slots.some((s) => s.sectionIndex !== null));

const fresh = ref<number[]>([]);
const announcement = ref("");
let prev: Map<number, DraftSlotStatus> | null = null;
let freshTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => props.slots,
  (slots) => {
    const idxs = newlyFinished(prev, slots);
    prev = new Map(slots.map((s) => [s.idx, s.status]));
    if (!idxs.length) return;
    fresh.value = idxs;
    announcement.value = finishedAnnouncement(slots, idxs);
    if (freshTimer) clearTimeout(freshTimer);
    freshTimer = setTimeout(() => {
      fresh.value = [];
    }, FRESH_MS);
  },
  { immediate: true },
);

function jump(idx: number): void {
  if (canJump.value) emit("jump", idx);
}

function hover(event: SlotHoverEvent): void {
  if (canJump.value) emit("hover", event);
}

onBeforeUnmount(() => {
  if (freshTimer) clearTimeout(freshTimer);
});
</script>
