<!-- frontend/components/SkxConfirm.vue -->
<!-- 확인 칸 — 덮어쓰거나 지우는 일을 하기 전에 누른 버튼 바로 곁(흐름 안)에 펴서 묻는다. 브라우저 확인 창(window.confirm)·모달을 쓰지 않는다
     (오류·확인은 화면 안에서 — 사용자 결정 2026-10-16). 사이드바 기록 지우기 확인(AppSidebar.vue 의 .skx-history__confirm)과 같은 꼴이다.
     디자인은 이 클래스(style_skovix.css 의 '[S] 공통 오류·빈 상태')에만 입히면 전체에 반영된다:
       .skx-confirm · .skx-confirm__msg · .skx-confirm__actions · .skx-confirm__ok · .skx-confirm__cancel
     글은 본문색이고 빨갛게 칠하지 않는다. 묻는 글은 해요체이고 문장 사이를 '\n' 으로 잇는다(.skx-confirm__msg 가 pre-line 으로 줄을 바꾼다).
     쓰는 법: 부모가 v-if 로 펴고 접는다 — 한 화면에 하나만 열리게 부모가 상태 하나로 쥐고, 묻던 일이 더는 맞지 않으면(절을 쓰기 시작함·
     단계가 바뀜 등) 부모가 접는다. @confirm 이면 원래 하던 일을 하고 그 일이 끝날 때까지 busy 로 남겨 두었다가 접는다. @cancel(Esc 포함)이면
     접기만 한다.
     접근성: role="alertdialog" + aria-label(무엇을 확인하는지) + aria-describedby(묻는 글). 펴지면 초점이 칸 안의 버튼으로 오고(initialFocus),
     칸이 접힐 때 초점이 칸 안에 있었으면 연 버튼(returnFocus — 없으면 펼 때 초점이 있던 곳)으로 돌아간다. busy 동안은 두 버튼이
     aria-disabled(누름·Esc 를 무시한다 — disabled 면 누른 버튼이 초점을 잃는다)이고 확인 버튼은 aria-busy 다(SkxInlineError·SkxErrorState 의
     재시도 중과 같은 꼴) -->
<template>
  <div
    ref="root"
    class="skx-confirm"
    role="alertdialog"
    :aria-label="label"
    :aria-describedby="msgId"
    @keydown.esc.stop="dismiss"
  >
    <p :id="msgId" class="skx-confirm__msg">{{ message }}</p>
    <div class="skx-confirm__actions">
      <button
        ref="okBtn"
        type="button"
        class="skx-confirm__ok"
        :aria-disabled="busy ? 'true' : undefined"
        :aria-busy="busy ? 'true' : undefined"
        @click="accept"
      >
        {{ confirmLabel }}
      </button>
      <button
        ref="cancelBtn"
        type="button"
        class="skx-confirm__cancel"
        :aria-disabled="busy ? 'true' : undefined"
        @click="dismiss"
      >
        {{ cancelLabel }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, onUnmounted, ref, useId } from "vue";

const props = withDefaults(
  defineProps<{
    /** 묻는 글 — 해요체, 문장 사이는 '\n' */
    message: string;
    /** 확인 버튼 글 — 하는 일의 동사('다시 쓰기'·'지우기'·'다시 만들기') */
    confirmLabel: string;
    /** 취소 버튼 글 */
    cancelLabel?: string;
    /** 칸의 이름(aria-label) — 무엇을 확인하는지('… 지우기 확인') */
    label: string;
    /** 확인한 일이 도는 중 — 두 버튼이 aria-disabled(누름·Esc 무시), 확인 버튼은 aria-busy */
    busy?: boolean;
    /**
     * 펼 때 초점을 둘 버튼. 기본은 [취소] — 이 칸이 묻는 일은 되돌릴 수 없어(지우기·덮어쓰기) 덜 파괴적인 쪽에 처음 초점을 둔다(WAI-ARIA
     * APG alertdialog 권고). 키보드로 연 버튼을 엔터로 누른 채 있으면 반복 입력이 칸이 열리자마자 확인으로 들어가는 일도 막는다.
     * 사용자가 '다시 쓰기·다시 만들기'를 골라 누른 자리는 'confirm' 을 넘겨 엔터 한 번 더면 진행되게 한다(사이드바 확인과 같다).
     * 'none' 은 초점을 옮기지 않는다(오류 화면 모음이 처음부터 펴 둔 본보기)
     */
    initialFocus?: "confirm" | "cancel" | "none";
    /** 접힌 뒤 초점을 돌려줄 곳 — 접힌 뒤에 부르므로 그 사이 연 버튼이 사라졌으면(절을 쓰기 시작함 등) 다른 자리를 고를 수 있다.
     *  없으면 펼 때 초점이 있던 곳 */
    returnFocus?: () => HTMLElement | null | undefined;
  }>(),
  { cancelLabel: "취소", busy: false, initialFocus: "cancel" },
);
const emit = defineEmits<{ confirm: []; cancel: [] }>();

const msgId = `skx-confirm-msg-${useId()}`;
const root = ref<HTMLElement | null>(null);
const okBtn = ref<HTMLButtonElement | null>(null);
const cancelBtn = ref<HTMLButtonElement | null>(null);
// 펼 때 초점이 있던 곳 — returnFocus 가 없을 때 돌아갈 자리
let opener: HTMLElement | null = null;

onMounted(() => {
  const active = document.activeElement;
  opener = active instanceof HTMLElement && active !== document.body ? active : null;
  if (props.initialFocus === "none") return;
  (props.initialFocus === "confirm" ? okBtn : cancelBtn).value?.focus();
});

// 일하는 중(busy)에는 누름을 무시한다 — disabled 대신이라 버튼은 초점을 잃지 않는다
function accept(): void {
  if (!props.busy) emit("confirm");
}

function dismiss(): void {
  if (!props.busy) emit("cancel");
}

// 칸이 접혀 칸 안의 버튼에 있던 초점이 body 로 떨어지면 연 버튼(returnFocus)으로 돌린다. 그 사이 다른 곳으로 간 초점(단계를 옮겨 새
// 제목으로 간 초점·다른 버튼을 누른 초점)은 빼앗지 않는다. returnFocus 는 마지막으로 받은 것을 접히기 전에 쥔다
let hadFocus = false;
let back: (() => HTMLElement | null | undefined) | undefined;
onBeforeUnmount(() => {
  hadFocus = !!root.value?.contains(document.activeElement);
  back = props.returnFocus;
});
onUnmounted(() => {
  if (!hadFocus) return;
  void nextTick(() => {
    const active = document.activeElement;
    if (active && active !== document.body) return;
    const target = back ? back() : opener?.isConnected ? opener : null;
    target?.focus();
  });
});
</script>
