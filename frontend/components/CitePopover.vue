<template>
  <!-- 요약 글 속 인용 번호를 누르면 뜨는 작은 카드 — 오른쪽 참고 논문 목록의 그 논문(제목·저자·연도·[원문 보기][DeepRead]).
       요약 칸은 넘친 글을 잘라 보이므로(ClampedPanel) body 로 옮겨 그리고 화면 기준(fixed)으로 번호 옆에 놓는다.
       버튼이 든 카드라 말풍선(tooltip)이 아니라 비모달 dialog 다 -->
  <Teleport to="body">
    <Transition name="skx-rel-pop" appear>
      <div
        ref="popRef"
        class="skx-citepop"
        role="dialog"
        aria-modal="false"
        :aria-label="`참고 논문 ${item.num}`"
        tabindex="-1"
        @keydown="onKeydown"
        @focusout="onFocusout"
      >
        <button type="button" class="skx-citepop__title" @click="emit('detail')">{{ item.title }}</button>
        <p v-if="meta" class="skx-citepop__meta">{{ meta }}</p>
        <div class="skx-citepop__actions">
          <button type="button" class="skx-btn-pview" @click="emit('pdf')">원문 보기</button>
          <button type="button" class="skx-btn-ptalk" @click="emit('chat')">
            <img src="/img/ico-chat.svg" alt="" />
            DeepRead
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { CITE_CLASS } from "~/utils/summaryCite";
import { popoverPlacement } from "~/utils/relevance";

// 위치 잡기·초점·닫기를 맡는다 — 열고 닫는 상태는 부모(SummaryText)가 쥐고, 이 컴포넌트는 떠 있는 동안만 산다(v-if).
// 닫기: Esc(번호로 초점을 돌려준다)·카드 밖 누름·카드 밖으로 초점이 나감·스크롤로 번호가 화면 밖으로 나감.
// 카드는 body 끝에 있어 Tab 이 글 흐름으로 이어지지 않는다 — 가장자리에서 Tab 을 더 누르면 닫고 번호로 돌려보낸다
const props = defineProps<{
  /** 눌린 번호 버튼 */
  anchor: HTMLElement;
  item: { num: number; title: string; authors: string; year: string };
}>();
const emit = defineEmits<{
  /** restoreFocus: 번호 버튼으로 초점을 돌려줄지(Esc·Tab 으로 나갈 때) */
  close: [restoreFocus: boolean];
  detail: [];
  pdf: [];
  chat: [];
}>();

const GAP = 6;
const MARGIN = 8;

const popRef = ref<HTMLElement | null>(null);
const meta = computed(() => [props.item.authors, props.item.year].filter(Boolean).join(" · "));

// 번호 아래 왼쪽 맞춤이 기본이고, 좌우로 넘으면 밀고, 아래가 모자라면 번호 위로 올린다(popoverPlacement — 관련도 팝오버와 같은 규칙).
// 마지막으로 화면 안에 가둔다 — fixed 라 화면 밖에 놓이면 스크롤로도 닿지 못한다
function place() {
  const pop = popRef.value;
  if (!pop) return;
  const a = props.anchor.getBoundingClientRect();
  // 번호가 화면 위·아래로 완전히 나갔으면 카드만 남기지 않는다
  if (a.bottom < 0 || a.top > window.innerHeight) {
    emit("close", false);
    return;
  }
  const width = pop.offsetWidth;
  const height = pop.offsetHeight;
  const viewport = { width: document.documentElement.clientWidth, height: window.innerHeight };
  const below = a.bottom + GAP;
  const { shiftX, above } = popoverPlacement(
    { left: a.left, right: a.left + width, top: below, bottom: below + height },
    { top: a.top - GAP },
    viewport,
    MARGIN,
  );
  const top = above ? a.top - GAP - height : below;
  pop.style.left = `${Math.round(a.left + shiftX)}px`;
  pop.style.top = `${Math.round(Math.min(Math.max(top, MARGIN), Math.max(MARGIN, viewport.height - height - MARGIN)))}px`;
}

let frame = 0;
function schedulePlace() {
  if (frame) return;
  frame = requestAnimationFrame(() => {
    frame = 0;
    place();
  });
}

function onDocKeydown(e: KeyboardEvent) {
  if (e.key !== "Escape") return;
  // 다른 창(DeepRead 패널·PDF 뷰어)의 Esc 로 번지지 않게 — 카드만 닫고 초점은 번호로
  e.stopPropagation();
  e.preventDefault();
  emit("close", true);
}

function onDocPointerDown(e: PointerEvent) {
  const target = e.target as Element | null;
  // 카드 안과 인용 번호(다른 번호면 부모가 옮겨 열고, 같은 번호면 닫는다)는 바깥이 아니다
  if (!target || popRef.value?.contains(target) || target.closest(`button.${CITE_CLASS}`)) return;
  emit("close", false);
}

function focusables(): HTMLElement[] {
  return Array.from(popRef.value?.querySelectorAll<HTMLElement>("button") ?? []);
}

function onKeydown(e: KeyboardEvent) {
  if (e.key !== "Tab") return;
  const items = focusables();
  const active = document.activeElement;
  const leavingForward = !e.shiftKey && active === items[items.length - 1];
  const leavingBackward = e.shiftKey && (active === items[0] || active === popRef.value);
  if (leavingForward || leavingBackward) {
    e.preventDefault();
    emit("close", true);
  }
}

function onFocusout(e: FocusEvent) {
  // 초점이 다른 요소로 옮겨 갔을 때만 닫는다. 가는 곳이 없는 경우(빈 곳을 누름·창을 벗어남)는 닫지 않는다 — 빈 곳 누름은
  // 바깥 누름 처리가 맡고, 번호를 다시 눌러 닫는 클릭이 맥 사파리처럼 버튼에 초점을 주지 않는 곳에서 닫았다 다시 열지 않게
  const next = e.relatedTarget as Node | null;
  if (!next || popRef.value?.contains(next) || props.anchor.contains(next)) return;
  emit("close", false);
}

onMounted(() => {
  place();
  // 열린 뒤 곧바로 카드로 초점을 옮긴다 — 키보드로 연 사람이 [원문 보기]·[DeepRead] 로 바로 간다(스크린리더는 dialog 이름을 읽는다)
  popRef.value?.focus({ preventScroll: true });
  document.addEventListener("keydown", onDocKeydown, true);
  document.addEventListener("pointerdown", onDocPointerDown, true);
  // 안쪽 스크롤 칸의 스크롤도 잡도록 capture 로 듣는다
  document.addEventListener("scroll", schedulePlace, true);
  window.addEventListener("resize", schedulePlace);
});

onBeforeUnmount(() => {
  if (frame) cancelAnimationFrame(frame);
  document.removeEventListener("keydown", onDocKeydown, true);
  document.removeEventListener("pointerdown", onDocPointerDown, true);
  document.removeEventListener("scroll", schedulePlace, true);
  window.removeEventListener("resize", schedulePlace);
});
</script>
