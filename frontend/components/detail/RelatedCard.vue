<template>
  <!-- 관련 자료 카드 — 표지 칸(흰 종이) → 칩 줄 → 제목(2줄) → 저자 → 서지 줄 → 'AI 추천 사유' 상자(2줄 + 자세히 보기).
       카드 전체가 제목 링크다(.dt-rc__link::after). 칩·사유 상자는 링크 위에 떠서 따로 눌린다.
       [자세히 보기]는 카드 아래쪽을 덮는 팝업(사유 전문 + 키워드 + DeepRead·원문 보기·인용)을 연다 — 열리면 초점이 [접기]로 가고,
       Esc·[접기]로 닫으면 초점이 [자세히 보기]로 돌아온다. 바깥을 누르면 닫힌다 -->
  <article ref="rootRef" :class="['dt-rc', expanded && 'is-open']">
    <div class="dt-rc__cover">
      <slot name="cover" />
    </div>
    <div class="dt-rc__body">
      <div class="dt-rc__info">
        <div class="dt-rc__chips">
          <slot name="badge" />
          <span v-if="keywords.length || kdc" class="dt-rc__kws">
            <span
              v-for="kw in keywords"
              :key="kw"
              class="skx-tag skx-tag--keyword"
              >#{{ kw }}</span
            >
            <span v-if="kdc" class="skx-rc__kdc" :title="kdc.title">
              <span class="skx-sr-only">{{ kdc.title }}: </span>{{ kdc.name }}
            </span>
          </span>
        </div>
        <h3 class="dt-rc__title">
          <NuxtLink :to="to" class="dt-rc__link">{{ title }}</NuxtLink>
        </h3>
        <p v-if="author" class="dt-rc__author">{{ author }}</p>
        <p v-if="meta" class="dt-rc__meta">{{ meta }}</p>
      </div>
      <div class="dt-rc__why">
        <p class="dt-rc__why-label"><DetailSparkIcon />{{ reasonLabel }}</p>
        <p class="dt-rc__why-text">
          <template v-if="reasonLoading && !reason">
            AI가 유사성을 분석 중입니다<span class="skx-stream-cursor" />
          </template>
          <template v-else>{{ reason || emptyText }}</template>
        </p>
        <button
          ref="moreRef"
          type="button"
          class="dt-rc__more"
          :aria-expanded="expanded"
          :aria-controls="expanded ? popId : undefined"
          @click="setOpen(!expanded)"
        >
          자세히 보기<span class="skx-sr-only">: {{ title }}</span>
          <svg
            class="dt-rc__more-chev"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
          >
            <path
              d="M6 9l6 6 6-6"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>

    <div
      v-if="expanded"
      :id="popId"
      class="dt-rc__pop"
      role="region"
      :aria-label="`${popTitle} — ${title}`"
      @keydown.esc.stop.prevent="closeAndReturn"
    >
      <div class="dt-rc__pop-head">
        <p class="dt-rc__pop-title"><DetailSparkIcon />{{ popTitle }}</p>
        <button
          ref="closeRef"
          type="button"
          class="dt-rc__close"
          aria-label="접기"
          @click="closeAndReturn"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path
              d="M6 15l6-6 6 6"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
      <div v-if="keywords.length" class="dt-rc__pop-kws">
        <span v-for="kw in keywords" :key="kw" class="skx-tag skx-tag--keyword"
          >#{{ kw }}</span
        >
      </div>
      <p class="dt-rc__pop-text" tabindex="0">
        <template v-if="reasonLoading && !reason">
          AI가 유사성을 분석 중입니다<span class="skx-stream-cursor" />
        </template>
        <template v-else>
          {{ reason || emptyText
          }}<span v-if="reasonLoading" class="skx-stream-cursor" />
        </template>
      </p>
      <div class="dt-rc__pop-actions">
        <slot name="actions" />
      </div>
      <slot name="note" />
    </div>
  </article>
</template>

<script setup lang="ts">
import type { KdcChip } from "~/utils/kdc";

const props = withDefaults(
  defineProps<{
    /** 카드가 가는 상세 주소 */
    to: string;
    title: string;
    author?: string;
    /** '2004년 9월 · 한국인지과학회' */
    meta?: string;
    keywords?: readonly string[];
    /** 키워드가 없는 소장자료의 분류 칩 */
    kdc?: KdcChip | null;
    /** 상자 머리 — '✦ AI 추천 사유' */
    reasonLabel: string;
    /** 팝업 머리 — '✦ AI 추천 사유 & 유사점 분석' */
    popTitle: string;
    reason?: string;
    reasonLoading?: boolean;
    emptyText?: string;
    /** 팝업이 열렸는지 — 한 번에 한 카드만 열리도록 부모가 쥔다 */
    expanded: boolean;
  }>(),
  {
    author: "",
    meta: "",
    keywords: () => [],
    kdc: null,
    reason: "",
    reasonLoading: false,
    emptyText: "정보가 없습니다.",
  },
);
const emit = defineEmits<{ "update:expanded": [open: boolean] }>();

const popId = `dt-rc-${useId()}`;
const rootRef = ref<HTMLElement | null>(null);
const moreRef = ref<HTMLButtonElement | null>(null);
const closeRef = ref<HTMLButtonElement | null>(null);

function setOpen(open: boolean) {
  emit("update:expanded", open);
}

function closeAndReturn() {
  setOpen(false);
  // 팝업이 사라진 뒤 [자세히 보기]로 — 팝업이 덮던 자리라 지금 바로 옮기면 사라지는 요소 위에 머문다
  void nextTick(() => moreRef.value?.focus());
}

function onOutsidePointerDown(e: PointerEvent) {
  if (rootRef.value && !rootRef.value.contains(e.target as Node))
    setOpen(false);
}

// 열릴 때 초점을 팝업의 [접기]로 옮겨 키보드로 안의 버튼에 바로 닿게 한다. 열린 동안만 바깥 누름을 듣는다
watch(
  () => props.expanded,
  async (open) => {
    if (open) {
      document.addEventListener("pointerdown", onOutsidePointerDown, true);
      await nextTick();
      closeRef.value?.focus();
    } else {
      document.removeEventListener("pointerdown", onOutsidePointerDown, true);
    }
  },
);

// 카드는 늘 닫힌 채 시작한다 — 부모가 쥔 열림이 목록을 다시 그릴 때·되돌아올 때(뒤로 가기 캐시 pageshow)에 남아 있어도
// 사용자가 누르지 않은 팝업이 저절로 열려 보이지 않게, 처음부터 열려 있다고 오면 닫는다고 알린다
function onPageShow(e: PageTransitionEvent) {
  if (e.persisted && props.expanded) setOpen(false);
}
onMounted(() => {
  if (props.expanded) setOpen(false);
  window.addEventListener("pageshow", onPageShow);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onOutsidePointerDown, true);
  window.removeEventListener("pageshow", onPageShow);
});
</script>
