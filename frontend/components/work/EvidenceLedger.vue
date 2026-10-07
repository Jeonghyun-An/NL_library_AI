<!-- frontend/components/work/EvidenceLedger.vue -->
<template>
  <!-- 회차 끝 채택 목록을 기록하기 전 잡(06a 전)은 장부가 없다 — 그리지 않는다 -->
  <section v-if="shown" class="rs-card wk-ledger" aria-labelledby="wk-ledger-title">
    <header class="wk-ledger__head">
      <h2 id="wk-ledger-title" class="rs-card__title">근거 장부</h2>
      <p class="wk-ledger__count">{{ line }}</p>
    </header>

    <ol class="wk-ledger__list" aria-label="채택한 논문">
      <li
        v-for="p in ledger.adopted"
        :key="p.cntsId"
        class="wk-ledger__paper"
        :class="{ 'is-fresh': fresh.adopted.includes(p.cntsId) }"
      >
        <span class="wk-ledger__title">{{ p.title || p.cntsId }}</span>
        <span class="wk-ledger__meta">{{ byline(p) }} · 하위질문 {{ subqLabel(p) }}</span>
      </li>
    </ol>

    <template v-if="ledger.dropped.length">
      <h3 class="wk-ledger__pile-title">뺌 {{ ledger.dropped.length }}</h3>
      <ol class="wk-ledger__list wk-ledger__list--dropped" aria-label="자기점검이 뺀 논문">
        <li
          v-for="p in ledger.dropped"
          :key="p.cntsId"
          class="wk-ledger__paper"
          :class="{ 'is-fresh': fresh.dropped.includes(p.cntsId) }"
        >
          <span class="wk-ledger__title">{{ p.title || p.cntsId }}</span>
          <span class="wk-ledger__meta">{{ byline(p) }} · 하위질문 {{ subqLabel(p) }} · {{ p.round }}회차에 뺌</span>
        </li>
      </ol>
    </template>

    <!-- 점검이 끝날 때만 읽힌다. 다시 연 화면에서 장부 전체를 몰아 읽지 않는다 -->
    <p class="rs-sr-only" role="status" aria-live="polite">{{ announcement }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { SubqView } from "~/types/research";
import { hasLedger, ledgerFrom, ledgerLine, newlyAdded, type LedgerPaper } from "~/utils/evidenceLedger";
import { paperByline } from "~/utils/researchReport";

// live: 탐색 중(점검 이벤트가 오는 화면)일 때만 참 — 끝난 잡·다시 연 화면은 움직이지 않는다
const props = defineProps<{ subqs: SubqView[]; live: boolean }>();

// 떨어지는 효과의 길이(work.css 의 wk-drop·wk-sink 와 맞춘다)
const FRESH_MS = 900;

const shown = computed(() => hasLedger(props.subqs));
const ledger = computed(() => ledgerFrom(props.subqs));
const line = computed(() => ledgerLine(ledger.value));

const fresh = ref<{ adopted: string[]; dropped: string[] }>({ adopted: [], dropped: [] });
const announcement = ref("");
let prevAdopted: Set<string> | null = null;
let prevDropped: Set<string> | null = null;
let freshTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  ledger,
  (l) => {
    // 효과는 실제로 도착한 점검 이벤트가 장부를 바꿨을 때만이다(시연 정직성) — 처음 그릴 때는 prev 가 없다
    const adopted = props.live ? newlyAdded(prevAdopted, l.adopted) : [];
    const dropped = props.live ? newlyAdded(prevDropped, l.dropped) : [];
    prevAdopted = new Set(l.adopted.map((p) => p.cntsId));
    prevDropped = new Set(l.dropped.map((p) => p.cntsId));
    if (!adopted.length && !dropped.length) return;
    fresh.value = { adopted, dropped };
    announcement.value = [
      adopted.length ? `근거 ${adopted.length}편 채택` : "",
      dropped.length ? `${dropped.length}편 뺌` : "",
    ]
      .filter(Boolean)
      .join(", ");
    if (freshTimer) clearTimeout(freshTimer);
    freshTimer = setTimeout(() => {
      fresh.value = { adopted: [], dropped: [] };
    }, FRESH_MS);
  },
  { immediate: true },
);

function byline(p: LedgerPaper): string {
  return paperByline({ personal_author: p.personalAuthor, pub_date: p.pubDate });
}

function subqLabel(p: LedgerPaper): string {
  return p.subqIdx.map((i) => i + 1).join("·");
}

onBeforeUnmount(() => {
  if (freshTimer) clearTimeout(freshTimer);
});
</script>
