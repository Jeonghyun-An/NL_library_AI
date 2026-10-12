<template>
  <!-- 결과 카드 전체가 누르면 상세로 가는 영역이라, 알약·팝오버의 클릭은 카드로 번지지 않게 막는다 -->
  <span ref="rootRef" class="skx-rel">
    <!-- 제목·내용 일치율이 있으면 누르거나 올리거나 초점을 주면 팝오버가 열리는 버튼, 없으면(옛 기록 복원 등) 알약만 -->
    <button
      v-if="rings.length"
      type="button"
      class="skx-rel__pill skx-rel__pill--btn"
      :aria-expanded="open"
      :aria-describedby="popId"
      @pointerenter="onPointerEnter"
      @pointerleave="onPointerLeave"
      @pointerdown="pointerDown = true"
      @focus="onFocus"
      @blur="close"
      @click.stop="onClick"
    >
      관련도 {{ pct }}%
    </button>
    <span v-else class="skx-rel__pill">관련도 {{ pct }}%</span>

    <Transition name="skx-rel-pop">
      <span
        v-if="rings.length"
        v-show="open"
        :id="popId"
        ref="popRef"
        :class="['skx-rel__pop', above && 'is-above']"
        :style="{ transform: shiftX ? `translateX(${shiftX}px)` : undefined }"
        role="tooltip"
        @pointerenter="onPointerEnter"
        @pointerleave="onPointerLeave"
        @click.stop
      >
        <span v-for="ring in rings" :key="ring.key" class="skx-rel__item">
          <span class="skx-sr-only">{{ ring.label }} {{ ring.pct }}%</span>
          <span class="skx-rel__ring" aria-hidden="true">
            <ScoreRing :pct="ring.pct" :label="ring.label" :variant="ring.variant" :tip="false" />
          </span>
          <span class="skx-rel__label" aria-hidden="true">{{ ring.label }}</span>
        </span>
      </span>
    </Transition>
  </span>
</template>

<script setup lang="ts">
import { popoverPlacement, relevancePct, relevanceRings } from "~/utils/relevance";

// 결과 카드의 '관련도 N%' 알약 하나. 제목·내용 일치율은 알약을 올리거나(마우스) 초점을 주거나(키보드) 누르면(탭)
// 뜨는 작은 유리 팝오버에 링 두 개로 보인다. 소장자료·'SKOVIX 추천 1권'·논문 카드가 같이 쓴다
const props = defineProps<{
  /** 종합 점수(best_score, 0~1) */
  score: number | null | undefined;
  titleScore?: number | null;
  contentScore?: number | null;
}>();

// 마우스를 올릴 때만 짧게 늦춘다 — 지나가는 마우스에 번쩍이지 않고, 알약에서 팝오버로 옮기는 사이엔 닫히지 않게
const HOVER_OPEN_MS = 100;
const HOVER_CLOSE_MS = 150;

const pct = computed(() => relevancePct(props.score));
const rings = computed(() => relevanceRings(props.titleScore, props.contentScore));

const popId = `skx-rel-${useId()}`;
const rootRef = ref<HTMLElement | null>(null);
const popRef = ref<HTMLElement | null>(null);

const open = ref(false);
// 어떻게 열렸나 — 호버로 열린 건 마우스가 떠나면, 초점으로 열린 건 초점이 떠나면 닫고, 누른 건(고정) 다시 누를 때까지 둔다
let openedBy: "hover" | "focus" | "click" | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;
// 마우스로 누를 때는 초점(focus)이 click 보다 먼저 와서 열었다 닫는 깜박임이 생긴다 — 누르는 중의 초점은 열지 않는다
const pointerDown = ref(false);

const shiftX = ref(0);
const above = ref(false);

function clearTimer() {
  if (timer) clearTimeout(timer);
  timer = null;
}

function openNow(by: "hover" | "focus" | "click") {
  clearTimer();
  openedBy = by;
  if (open.value) return;
  open.value = true;
}

function close() {
  clearTimer();
  openedBy = null;
  open.value = false;
  pointerDown.value = false;
}

function onPointerEnter(e: PointerEvent) {
  // 터치의 pointerenter 는 탭마다 오므로 무시한다 — 터치는 click(탭)으로만 연다
  if (e.pointerType === "touch") return;
  clearTimer();
  if (open.value) return;
  timer = setTimeout(() => openNow("hover"), HOVER_OPEN_MS);
}

function onPointerLeave(e: PointerEvent) {
  if (e.pointerType === "touch") return;
  clearTimer();
  if (!open.value) return;
  if (openedBy === "hover") timer = setTimeout(close, HOVER_CLOSE_MS);
}

function onFocus() {
  if (pointerDown.value) return;
  openNow("focus");
}

function onClick() {
  pointerDown.value = false;
  // 호버·초점으로 이미 열려 있으면 그 자리에 고정한다. 고정된 걸 다시 누르면 닫는다
  if (open.value && openedBy === "click") close();
  else openNow("click");
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape" && open.value) {
    // 초점은 알약에 그대로 둔다 — 다음 Tab 이 자연스럽게 이어지게
    close();
    e.stopPropagation();
  }
}

function onOutsidePointerDown(e: PointerEvent) {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) close();
}

// 열린 동안만 문서 수준 키·바깥 클릭을 듣는다. 열릴 때 화면 밖으로 안 잘리게 위치를 잰다
watch(open, async (isOpen) => {
  if (isOpen) {
    document.addEventListener("keydown", onKeydown, true);
    document.addEventListener("pointerdown", onOutsidePointerDown, true);
    shiftX.value = 0;
    above.value = false;
    await nextTick();
    placePopover();
  } else {
    document.removeEventListener("keydown", onKeydown, true);
    document.removeEventListener("pointerdown", onOutsidePointerDown, true);
  }
});

function placePopover() {
  const pop = popRef.value;
  const root = rootRef.value;
  if (!pop || !root || !open.value) return;
  const rect = pop.getBoundingClientRect();
  const anchor = root.getBoundingClientRect();
  const next = popoverPlacement(rect, { top: anchor.top }, { width: window.innerWidth, height: window.innerHeight });
  shiftX.value = next.shiftX;
  above.value = next.above;
}

onBeforeUnmount(() => {
  clearTimer();
  document.removeEventListener("keydown", onKeydown, true);
  document.removeEventListener("pointerdown", onOutsidePointerDown, true);
});
</script>
