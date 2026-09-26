<!-- frontend/components/research/CitationChip.vue -->
<template>
  <span
    ref="wrap"
    class="rs-cite"
    @mouseenter="onEnter"
    @mouseleave="onLeave"
    @focusin="show"
    @focusout="onFocusOut"
    @keydown.escape.stop="close"
  >
    <button
      ref="chip"
      type="button"
      class="rs-cite__chip"
      :aria-expanded="open"
      :aria-controls="popId"
      :aria-label="`근거 ${eid}: ${title}`"
      @click="togglePin"
    >
      {{ label }}
    </button>
    <!-- tabindex=-1: 안쪽 글을 눌러도 초점이 팝오버로 옮겨 와 wrap 안에 머문다 — 그래야 Esc 가 먹는다 -->
    <span
      v-if="open"
      :id="popId"
      ref="pop"
      class="rs-cite__pop"
      role="dialog"
      tabindex="-1"
      :aria-label="`${eid} 근거`"
      :style="shift ? { left: `${shift}px` } : undefined"
    >
      <strong class="rs-cite__title">{{ title }}</strong>
      <span v-if="meta" class="rs-cite__meta">{{ meta }}</span>
      <template v-if="current">
        <span class="rs-cite__quote">{{ current.text }}</span>
        <span class="rs-cite__foot">
          <span>{{ pageLabel(current) }}</span>
          <span v-if="chunks.length > 1" class="rs-cite__pager">
            <button type="button" aria-label="이전 대목" :aria-disabled="!canPrev" @click="step(-1)">‹</button>
            <span>{{ index + 1 }}/{{ chunks.length }}</span>
            <button type="button" aria-label="다음 대목" :aria-disabled="!canNext" @click="step(1)">›</button>
          </span>
        </span>
      </template>
      <span v-else class="rs-cite__quote rs-muted">이 절에서 매칭된 대목이 없습니다</span>
      <span v-if="evidence" class="rs-cite__actions">
        <button type="button" class="rs-btn rs-btn--small" @click="openPdf">원문 보기</button>
        <NuxtLink :to="`/papers/${evidence.cnts_id}`" class="rs-btn rs-btn--small rs-btn--ghost">논문 상세</NuxtLink>
      </span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import type { OpenPdfPayload, ReportChunk, ReportEvidence } from "~/types/research";
import { citeLabel, metaLine, pageLabel, pdfPage } from "~/utils/citations";
import { stepChunk } from "~/utils/researchReport";

const props = defineProps<{ eid: string; evidence?: ReportEvidence; chunks: ReportChunk[] }>();
const emit = defineEmits<{ "open-pdf": [payload: OpenPdfPayload] }>();

// 포인터가 칩에서 팝오버로 옮겨 가는 사이에 닫히지 않게 조금 기다린다
const HIDE_DELAY_MS = 150;
const EDGE_PX = 8;

const popId = useId();
const wrap = ref<HTMLElement | null>(null);
const chip = ref<HTMLButtonElement | null>(null);
const pop = ref<HTMLElement | null>(null);
const shift = ref(0);
const open = ref(false);
const pinned = ref(false);
const index = ref(0);
let hideTimer: ReturnType<typeof setTimeout> | null = null;
// 포인터가 칩·팝오버 위에 있는지 — 초점이 어디로도 옮겨 가지 않고 빠질 때 닫을지 가른다
let hovering = false;

const label = computed(() => citeLabel(props.evidence?.meta, props.eid));
const title = computed(() => props.evidence?.meta.title || "근거 정보를 찾을 수 없습니다");
const meta = computed(() => metaLine(props.evidence?.meta));
const current = computed<ReportChunk | undefined>(() => props.chunks[index.value]);
const canPrev = computed(() => stepChunk(index.value, -1, props.chunks.length) !== index.value);
const canNext = computed(() => stepChunk(index.value, 1, props.chunks.length) !== index.value);

watch(() => props.chunks, () => {
  index.value = 0;
});

// 화면 오른쪽 끝의 칩은 팝오버가 잘리고 가로 스크롤이 생긴다 — 넘친 만큼 왼쪽으로 민다
watch(open, async (isOpen) => {
  shift.value = 0;
  if (!isOpen) return;
  await nextTick();
  const rect = pop.value?.getBoundingClientRect();
  if (!rect) return;
  const overflow = rect.right - (window.innerWidth - EDGE_PX);
  if (overflow > 0) shift.value = -Math.min(overflow, Math.max(0, rect.left - EDGE_PX));
});

function cancelHide(): void {
  if (hideTimer) clearTimeout(hideTimer);
  hideTimer = null;
}

function show(): void {
  cancelHide();
  open.value = true;
}

function scheduleHide(): void {
  if (pinned.value) return;
  cancelHide();
  hideTimer = setTimeout(() => {
    open.value = false;
  }, HIDE_DELAY_MS);
}

function onEnter(): void {
  hovering = true;
  show();
}

function onLeave(): void {
  hovering = false;
  scheduleHide();
}

function step(delta: number): void {
  index.value = stepChunk(index.value, delta, props.chunks.length);
}

// 초점을 먼저 옮긴다 — focus() 가 동기로 쏘는 focusin 이 wrap 의 show 로 올라가 닫힘을 되돌리지 않게
function close(): void {
  cancelHide();
  chip.value?.focus();
  pinned.value = false;
  open.value = false;
  document.removeEventListener("click", onDocumentClick);
}

function togglePin(): void {
  pinned.value = !pinned.value;
  open.value = true;
  if (pinned.value) document.addEventListener("click", onDocumentClick);
  else document.removeEventListener("click", onDocumentClick);
}

function onFocusOut(e: FocusEvent): void {
  const to = e.relatedTarget;
  if (to instanceof Node && wrap.value?.contains(to)) return;
  // 초점이 다른 요소로 옮겨 가지 않고 그냥 빠진 것(창 전환, 초점을 받지 않는 곳 클릭)은 떠난 게 아니다 —
  // 고정은 바깥 클릭·Esc 가 풀고, 포인터가 안에 있으면 닫는 일은 mouseleave 에 맡긴다
  if (!to) {
    if (!hovering) scheduleHide();
    return;
  }
  pinned.value = false;
  document.removeEventListener("click", onDocumentClick);
  scheduleHide();
}

function onDocumentClick(e: MouseEvent): void {
  if (e.target instanceof Node && wrap.value?.contains(e.target)) return;
  // 대목을 끌어 선택하다 팝오버 밖에서 놓으면 click 이 바깥 공통 조상에 떨어진다 — 복사하려던 선택을 지키게 둔다
  const sel = window.getSelection();
  if (sel && !sel.isCollapsed && sel.anchorNode && wrap.value?.contains(sel.anchorNode)) return;
  pinned.value = false;
  open.value = false;
  document.removeEventListener("click", onDocumentClick);
}

function openPdf(): void {
  if (!props.evidence) return;
  emit("open-pdf", {
    cntsId: props.evidence.cnts_id,
    title: title.value,
    page: current.value ? pdfPage(current.value) : undefined,
  });
}

onBeforeUnmount(() => {
  cancelHide();
  document.removeEventListener("click", onDocumentClick);
});
</script>
