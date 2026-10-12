<template>
  <div :class="['skx-clamp', clamped && 'is-clamped', expanded && 'is-expanded']" ref="rootRef">
    <!-- 접힌 내용도 DOM 에 그대로 있다 — 시각적으로만 잘려 스크린리더는 전부 읽는다 -->
    <div :id="bodyId" class="skx-clamp__clip" :style="clipStyle">
      <div ref="innerRef" class="skx-clamp__inner"><slot /></div>
    </div>
    <div v-if="overflowing" class="skx-clamp__foot">
      <button
        type="button"
        class="skx-clamp__btn"
        :aria-expanded="expanded"
        :aria-controls="bodyId"
        @click="toggle"
      >
        <span>{{ expanded ? lessLabel : moreLabel }}</span>
        <img src="/img/ico-arrow-down.svg" alt="" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { clampMaxHeightPx, isOverflowing, needsScrollToTop, remToPx } from "~/utils/clampPanel";

// 길어질 수 있는 AI 글 패널 — collapsedRem 높이까지만 보이고, 실제로 넘칠 때만 아래가 흐려지며 [더보기]/[접기]가 생긴다.
// 스트리밍 중에도 ResizeObserver 로 내용 높이를 따라가 넘치는 순간 접힌 채(페이드 + 버튼)가 되고, 넘지 않으면 버튼이 없다.
// 소장자료 'AI 검색 결과'와 논문 'AI 분석 결과'가 같이 쓴다
const props = withDefaults(
  defineProps<{
    /** 접힌 높이(rem) */
    collapsedRem?: number;
    moreLabel?: string;
    lessLabel?: string;
    /** 접을 때 이 선택자로 찾은 가장 가까운 조상(패널 머리)이 화면 위로 지나갔으면 그 머리로 스크롤한다. 없으면 이 패널 */
    scrollAnchor?: string;
  }>(),
  { collapsedRem: 16, moreLabel: "더보기", lessLabel: "접기", scrollAnchor: undefined },
);
const expanded = defineModel<boolean>("expanded", { default: false });

const rootRef = ref<HTMLElement | null>(null);
const innerRef = ref<HTMLElement | null>(null);
const bodyId = `skx-clamp-${useId()}`;

const contentPx = ref(0);
const clampPx = ref(0);

function measure() {
  const inner = innerRef.value;
  if (!inner) return;
  contentPx.value = inner.offsetHeight;
  // rem 은 화면 폭에 따라 달라진다(모바일 html 글자 크기가 줄어든다) — 잴 때마다 현재 값으로 바꾼다
  const rootFont = parseFloat(getComputedStyle(document.documentElement).fontSize) || 20;
  clampPx.value = remToPx(props.collapsedRem, rootFont);
}

const overflowing = computed(() => isOverflowing(contentPx.value, clampPx.value));
const clamped = computed(() => overflowing.value && !expanded.value);
const clipStyle = computed(() => {
  const h = clampMaxHeightPx({
    overflowing: overflowing.value,
    expanded: expanded.value,
    contentPx: contentPx.value,
    clampPx: clampPx.value,
  });
  return h === null ? undefined : { maxHeight: `${h}px` };
});

async function toggle() {
  const next = !expanded.value;
  expanded.value = next;
  if (next) return;
  await nextTick();
  const root = rootRef.value;
  const head = (props.scrollAnchor ? root?.closest<HTMLElement>(props.scrollAnchor) : null) ?? root;
  if (!head || !needsScrollToTop(head.getBoundingClientRect().top)) return;
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  head.scrollIntoView({ block: "start", behavior: calm ? "auto" : "smooth" });
}

let observer: ResizeObserver | null = null;

onMounted(() => {
  measure();
  if (innerRef.value && typeof ResizeObserver !== "undefined") {
    observer = new ResizeObserver(measure);
    observer.observe(innerRef.value);
  }
  window.addEventListener("resize", measure);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  window.removeEventListener("resize", measure);
});

watch(() => props.collapsedRem, measure);
</script>
