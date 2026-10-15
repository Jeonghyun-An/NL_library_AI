<template>
  <div class="skx-sumtext">
    <!-- 요약 글(marked 가 만든 HTML). 인용 번호 버튼은 이 안에 있어 클릭을 위임해 받는다 -->
    <div ref="bodyRef" v-html="shown" @click="onClick" @focusin="onFocusin" />
    <CitePopover
      v-if="anchor && active"
      :key="seq"
      :anchor="anchor"
      :item="{ num: active.num, title: active.title, authors: active.authors, year: active.year, grade: active.grade }"
      @close="onClose"
      @detail="act('detail')"
      @pdf="act('pdf')"
      @chat="act('chat')"
    />
  </div>
</template>

<script setup lang="ts">
import { INITIAL_POPOVER, popoverReduce } from "~/utils/relevancePopover";
import { CITE_CLASS, linkCitations, type SummaryRef } from "~/utils/summaryCite";

// 논문 검색 AI 요약 본문. 인용 번호 (1)·(1, 3) 을 누를 수 있는 버튼으로 바꾸고, 누르면 그 논문 카드를 작은 팝오버로 보인다.
// linked 가 켜진 뒤에만 바꾼다 — 참고 목록(sources)은 요약이 끝나야 오고, 스트리밍 중에는 글이 토큰마다 통째로 다시 그려져
// 버튼·열린 팝오버·초점이 매번 사라진다. 끝난 뒤(또는 저장된 요약을 복원한 때)에는 글이 바뀌지 않아 안정적이다.
// 열고 닫는 전환은 관련도 팝오버와 같은 리듀서(utils/relevancePopover.ts)를 쓴다 — 여기서 쓰는 이벤트는 click·escape·outside-pointer-down
const props = defineProps<{
  /** marked 로 렌더한 요약 HTML */
  html: string;
  refs: readonly SummaryRef[];
  /** 요약이 끝나 참고 목록이 정해졌는가 */
  linked: boolean;
}>();
const emit = defineEmits<{
  detail: [bookId: string];
  pdf: [bookId: string];
  chat: [bookId: string];
  /** 접혀 잘린 칸 안의 번호에 초점이 갔다 — 부모가 칸을 펼친다 */
  reveal: [];
}>();

const shown = computed(() => (props.linked ? linkCitations(props.html, props.refs) : props.html));

const bodyRef = ref<HTMLElement | null>(null);
const state = ref(INITIAL_POPOVER);
const anchor = shallowRef<HTMLElement | null>(null);
// 번호를 옮겨 눌러도 카드를 새로 그려 위치·초점을 다시 잡는다
const seq = ref(0);

const active = computed(() => {
  const el = anchor.value;
  return el ? (props.refs.find((r) => r.num === Number(el.dataset.cite)) ?? null) : null;
});

function citeButton(e: Event): HTMLElement | null {
  const el = (e.target as Element | null)?.closest<HTMLElement>(`button.${CITE_CLASS}`) ?? null;
  return el && bodyRef.value?.contains(el) ? el : null;
}

function release() {
  anchor.value?.setAttribute("aria-expanded", "false");
  anchor.value = null;
}

function onClick(e: MouseEvent) {
  const btn = citeButton(e);
  if (!btn || !props.refs.some((r) => r.num === Number(btn.dataset.cite))) return;
  // 열린 채 다른 번호를 누르면 그 번호로 옮겨 연다. 같은 번호를 다시 누르면 닫는다
  if (anchor.value && anchor.value !== btn) {
    release();
    state.value = INITIAL_POPOVER;
  }
  state.value = popoverReduce(state.value, "click");
  if (!state.value.open) {
    release();
    return;
  }
  anchor.value = btn;
  btn.setAttribute("aria-expanded", "true");
  seq.value++;
}

function onClose(restoreFocus: boolean) {
  const el = anchor.value;
  state.value = popoverReduce(state.value, restoreFocus ? "escape" : "outside-pointer-down");
  release();
  if (restoreFocus) el?.focus({ preventScroll: true });
}

function act(kind: "detail" | "pdf" | "chat") {
  const ref = active.value;
  if (!ref) return;
  state.value = popoverReduce(state.value, "outside-pointer-down");
  release();
  if (kind === "detail") emit("detail", ref.book_id);
  else if (kind === "pdf") emit("pdf", ref.book_id);
  else emit("chat", ref.book_id);
}

// 접힌 칸의 잘린 부분은 보이지 않는데 초점은 갈 수 있다 — 거기 있는 번호에 초점이 오면 칸을 펼쳐 보이게 한다
function onFocusin(e: FocusEvent) {
  const btn = citeButton(e);
  const clip = btn?.closest<HTMLElement>(".skx-clamp__clip");
  if (!btn || !clip) return;
  if (btn.getBoundingClientRect().bottom > clip.getBoundingClientRect().bottom + 1) emit("reveal");
}

// 글이 다시 그려져(요약을 다시 받음 등) 눌렀던 번호가 사라지면 카드도 거둔다
watch(shown, async () => {
  await nextTick();
  if (anchor.value && !anchor.value.isConnected) {
    state.value = INITIAL_POPOVER;
    anchor.value = null;
  }
});
</script>
