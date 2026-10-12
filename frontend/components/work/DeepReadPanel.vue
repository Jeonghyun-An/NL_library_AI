<!-- frontend/components/work/DeepReadPanel.vue -->
<template>
  <template v-if="paper">
    <!-- 1200px 미만(서랍·전체 폭)에서만 보이는 배경 — 누르면 닫는다. 넓은 화면에서는 CSS 가 숨긴다 -->
    <div class="wk-panel-backdrop" aria-hidden="true" @click="emit('close')" />
    <aside
      :id="panelId"
      ref="root"
      class="wk-panel"
      role="complementary"
      :aria-labelledby="`${panelId}-title`"
      @keydown="onKeydown"
    >
      <header class="wk-panel__head">
        <div class="wk-panel__heading">
          <!-- tabindex="-1" — 패널이 열리면 이 제목으로 초점을 옮긴다 -->
          <h2 :id="`${panelId}-title`" ref="titleEl" class="wk-panel__title" tabindex="-1">{{ head.title }}</h2>
          <p v-if="head.byline" class="wk-panel__byline">{{ head.byline }}</p>
        </div>
        <a v-if="detailHref" :href="detailHref" class="wk-panel__detail" @click="emit('detail', $event)">논문 상세 ↗</a>
        <button type="button" class="rs-icon-btn wk-panel__close" aria-label="패널 닫기" title="닫기 (Esc)" @click="emit('close')">
          ✕
        </button>
      </header>
      <div v-if="$slots.extra" class="wk-panel__extra">
        <slot name="extra" />
      </div>
      <div v-if="tabs.length > 1" class="wk-panel__tabs" role="tablist" aria-label="패널 보기">
        <button
          v-for="t in tabs"
          :id="tabId(t)"
          :key="t"
          type="button"
          role="tab"
          class="wk-panel__tab"
          :aria-selected="tab === t"
          :aria-controls="bodyId"
          :tabindex="tab === t ? 0 : -1"
          @click="emit('update:tab', t)"
          @keydown="onTabKey($event, t)"
        >
          {{ TAB_LABEL[t] }}
        </button>
      </div>
      <div
        :id="bodyId"
        class="wk-panel__body"
        :role="tabs.length > 1 ? 'tabpanel' : undefined"
        :aria-labelledby="tabs.length > 1 ? tabId(tab) : undefined"
      >
        <!-- 딥리드는 탭을 옮겨도 내리지 않는다(v-show) — 받던 답이 끊기지 않게. 패널을 닫으면 내려가며 끊는다 -->
        <div v-show="tab === 'chat'" class="wk-panel__chat">
          <BookChat
            :cnts-id="paper.cntsId"
            :book-title="paper.meta.title?.trim() || undefined"
            doc-kind="paper"
            :store="store"
            :pdf-links="true"
            @open-pdf="(payload) => emit('open-pdf', payload)"
          />
        </div>
        <div v-if="tab === 'sources'" class="wk-panel__sources">
          <slot name="sources" />
        </div>
      </div>
    </aside>
  </template>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import BookChat from "~/components/BookChat.vue";
import type { OpenPdfPayload } from "~/types/research";
import { type PanelPaper, type PanelTab, panelHead, panelMode } from "~/utils/deepRead";
import type { DeepReadMessage } from "~/utils/deepReadSse";

// 단계 화면 오른쪽 패널(spec §12-4 D24) — 머리(논문 제목·서지·[논문 상세 ↗]·닫기)와 탭 [인용 근거 | 딥리드].
// 무엇을 열지(paper — null 이면 닫힘)·어느 탭인지(tab)·논문별 대화(store)는 단계 화면이 쥐고, 이 부품은 그리기와 키보드만 맡는다.
// 닫은 뒤 누른 자리(행 제목·인용 칩)로 초점을 돌리는 것도 누른 요소를 아는 여는 쪽이 한다.
// 2단·서랍·전체 폭 모양은 모두 work.css 의 .wk-panel 묶음이 맡는다(전역 style_skovix.css 의 클래스에 기대지 않는다)
const props = defineProps<{
  panelId: string;
  paper: PanelPaper | null;
  tabs: readonly PanelTab[];
  tab: PanelTab;
  detailHref: string | null;
  store: Map<string, DeepReadMessage[]>;
}>();
const emit = defineEmits<{
  close: [];
  "update:tab": [tab: PanelTab];
  "open-pdf": [payload: OpenPdfPayload];
  detail: [e: MouseEvent];
}>();

const TAB_LABEL: Record<PanelTab, string> = { sources: "인용 근거", chat: "딥리드" };
const FOCUSABLE =
  "button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), summary, [tabindex]:not([tabindex='-1'])";

const root = ref<HTMLElement | null>(null);
const titleEl = ref<HTMLElement | null>(null);
const head = computed(() => (props.paper ? panelHead(props.paper) : { title: "", byline: "" }));
const bodyId = computed(() => `${props.panelId}-body`);

function tabId(t: PanelTab): string {
  return `${props.panelId}-tab-${t}`;
}

// 닫혀 있다가 열릴 때만 제목으로 초점을 옮긴다(화면낭독기가 무엇이 열렸는지 읽는다). 열린 채 다른 논문으로 바꿀 때는
// 옮기지 않는다 — 표에서 다음 제목을 이어 누를 수 있게
watch(
  () => props.paper !== null,
  async (open) => {
    if (!open) return;
    await nextTick();
    titleEl.value?.focus({ preventScroll: true });
  },
);

// Esc 는 어느 배치에서나 닫는다 — 초점이 패널 안에 있을 때만(문서가 아니라 패널에서 들어 원문 뷰어 등 위에 뜬 창의 Esc 와
// 겹치지 않는다). 서랍·전체 폭(1200px 미만)은 화면을 덮으므로 Tab 이 패널 밖으로 나가지 않게 처음·끝에서 돌린다
function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape") {
    emit("close");
    return;
  }
  if (e.key !== "Tab" || !root.value || panelMode(window.innerWidth) === "side") return;
  // 숨긴 탭 본문(v-show)의 요소는 뺀다
  const items = [...root.value.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
  const first = items[0];
  const last = items[items.length - 1];
  if (!first || !last) return;
  const active = document.activeElement;
  if (e.shiftKey && (active === first || active === titleEl.value)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && active === last) {
    e.preventDefault();
    first.focus();
  }
}

// 탭 목록의 방향키(WAI-ARIA 탭 관례) — 옆 탭을 고르고 그 탭에 초점
async function onTabKey(e: KeyboardEvent, t: PanelTab): Promise<void> {
  if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
  e.preventDefault();
  const n = props.tabs.length;
  const next = props.tabs[(props.tabs.indexOf(t) + (e.key === "ArrowRight" ? 1 : n - 1)) % n];
  if (!next) return;
  emit("update:tab", next);
  await nextTick();
  document.getElementById(tabId(next))?.focus();
}
</script>
