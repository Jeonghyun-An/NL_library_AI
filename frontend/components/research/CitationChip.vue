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
      :data-anchor="anchor"
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
        <!-- 누르는 순간의 칩 높이를 주소에 실어야 해서 NuxtLink 대신 직접 옮긴다 -->
        <a
          :href="detailHref(evidence.cnts_id, null)"
          class="rs-btn rs-btn--small rs-btn--ghost"
          @click="goDetail($event, evidence.cnts_id)"
          @auxclick="goDetail($event, evidence.cnts_id)"
          @contextmenu="goDetail($event, evidence.cnts_id)"
        >논문 상세</a>
      </span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { OpenPdfPayload, ReportChunk, ReportEvidence } from "~/types/research";
import { chunkListKey, citeLabel, metaLine, pageLabel, pdfPage } from "~/utils/citations";
import { REPORT_JOB, detailUrl } from "~/utils/detailSource";
import { hideOnPointerLeave, stepChunk } from "~/utils/researchReport";
import { isPlainClick, spotOf } from "~/utils/restorePosition";

// anchor: 돌아왔을 때 이 칩을 다시 찾는 열쇠(같은 절의 같은 근거는 순번으로 가른다)
const props = defineProps<{ eid: string; anchor: string; evidence?: ReportEvidence; chunks: ReportChunk[] }>();
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
const reportJob = inject(REPORT_JOB)!;
const { leave } = useDetailLeave();

const label = computed(() => citeLabel(props.evidence?.meta, props.eid));
const title = computed(() => props.evidence?.meta.title || "근거 정보를 찾을 수 없습니다");
const meta = computed(() => metaLine(props.evidence?.meta));
const current = computed<ReportChunk | undefined>(() => props.chunks[index.value]);
const canPrev = computed(() => stepChunk(index.value, -1, props.chunks.length) !== index.value);
const canNext = computed(() => stepChunk(index.value, 1, props.chunks.length) !== index.value);

// 대목 목록이 실제로 바뀔 때만 첫 대목으로 돌린다 — 다시 그릴 때마다 돌리면 열어 둔 팝오버에서 보던 대목을 잃는다
watch(() => chunkListKey(props.chunks), () => {
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
  const focused = document.activeElement;
  if (hideOnPointerLeave(pinned.value, !!focused && !!wrap.value?.contains(focused))) scheduleHide();
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

function detailHref(cnts: string, y: number | null): string {
  return detailUrl(cnts, { kind: "research", job: reportJob.value, e: props.eid }, { at: props.anchor, y });
}

// 누르는 순간의 칩 높이를 싣는다 — [딥리서치 보고서로]·뒤로 가기로 돌아오면 이 칩을 같은 화면 높이에 맞추고
// 초점을 돌려 팝오버를 다시 연다. 새 창·새 탭으로 여는 클릭과 오른쪽 클릭 메뉴는 브라우저에 맡기되 주소에는 같은
// 자리를 싣는다 — 메뉴는 auxclick 보다 먼저 뜨는 브라우저가 있고, 메뉴 키로 열면 왼쪽 클릭 모양이라 종류로 가린다
function goDetail(e: MouseEvent, cnts: string): void {
  const spot = spotOf(chip.value!, props.anchor);
  const url = detailHref(cnts, spot.y);
  if (e.type === "contextmenu" || !isPlainClick(e)) {
    (e.currentTarget as HTMLAnchorElement).href = url;
    return;
  }
  e.preventDefault();
  void leave(url, spot);
}

onBeforeUnmount(() => {
  cancelHide();
  document.removeEventListener("click", onDocumentClick);
});
</script>
