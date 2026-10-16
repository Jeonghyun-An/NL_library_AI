<!-- frontend/components/SkxConnectionBanner.vue -->
<!-- 실시간 연결 끊김 띠 — 딥리서치 진행 화면·연구 작업대의 SSE(EventSource)가 끊겼을 때 화면 위쪽에 얇게 알린다.
       connected    — 붙어 있음. 보이는 것 없이 빈 알림 영역만 그려 둔다
       reconnecting — 끊겨 다시 붙는 중(백오프 재연결이 도는 동안)
       lost         — 다시 붙지 못함. 부모가 @retry 를 달면(onRetry prop) [다시 연결] 을 그린다
     사용법: 쓰는 화면은 띠를 늘 그려 두고 state 만 바꾼다 — <SkxConnectionBanner :state="connState" @retry="resync" />
       (v-if 로 끊길 때만 그리지 않는다). 알림 영역(role="status")은 처음부터 있어야 낭독기가 새로 들어온 글을 읽는다 —
       끊길 때 새로 생긴 요소는 놓친다(SkxCharCount 의 늘 그려 둔 안내 칸과 같은 까닭). 그래서 role 도 상태마다 바꾸지 않는다.
     [다시 연결] 을 누르면 부모가 state 를 reconnecting 으로 바꿔 버튼이 사라진다 — 버튼에 있던 초점은 띠(tabindex="-1")로 옮겨
       body 로 빠지지 않게 한다(키보드·낭독기 사용자가 제자리를 잃지 않고, 띠의 새 글이 바로 읽힌다).
     두 상태는 글자색이 같고(빨갛게 칠하지 않는다 — 사용자 지적 2026-10-16) 앞의 아이콘으로만 가른다: 다시 연결하는 중은 깜빡이는 점,
     연결하지 못함은 위험색 경고 삼각형.
     띠 모양만 맡는다 — 화면 위 어디에 붙일지(sticky 등)는 쓰는 화면이 정한다.
     디자인은 이 클래스(style_skovix.css 의 '[S] 공통 오류·빈 상태')에만 입히면 실제 화면 전체에 반영된다:
       .skx-conn · .skx-conn--{state} · [data-state] · .skx-conn__icon · .skx-conn__msg · .skx-conn__retry
     문구는 utils/apiErrors.ts 의 CONNECTION_HINTS·CONNECTION_RETRY_LABEL -->
<template>
  <div
    ref="root"
    class="skx-conn"
    :class="`skx-conn--${state}`"
    :data-state="state"
    role="status"
    tabindex="-1"
  >
    <template v-if="message">
      <span class="skx-conn__icon" aria-hidden="true">
        <svg
          v-if="state === 'lost'"
          viewBox="0 0 32 32"
          fill="none"
          stroke="currentColor"
          stroke-width="2.6"
          stroke-linecap="round"
          stroke-linejoin="round"
          focusable="false"
        >
          <path d="M13.73 5.2 2.4 24a2.67 2.67 0 0 0 2.27 4h22.66a2.67 2.67 0 0 0 2.27-4L18.27 5.2a2.67 2.67 0 0 0-4.54 0" />
          <path d="M16 12v5.33" />
          <path d="M16 22.67h.01" />
        </svg>
      </span>
      <span class="skx-conn__msg">{{ message }}</span>
      <button v-if="state === 'lost' && onRetry" ref="retryButton" type="button" class="skx-conn__retry" @click="onRetry?.()">
        {{ CONNECTION_RETRY_LABEL }}
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { CONNECTION_HINTS, CONNECTION_RETRY_LABEL, type ConnectionState } from "~/utils/apiErrors";

const props = defineProps<{
  /** 'connected'(보이는 것 없음) | 'reconnecting'(다시 연결하는 중) | 'lost'(연결하지 못함) */
  state: ConnectionState;
  /** 부모의 @retry 가 이 prop 으로 들어온다 — lost 일 때만 [다시 연결] 을 그린다 */
  onRetry?: () => void;
}>();

const root = ref<HTMLElement | null>(null);
const retryButton = ref<HTMLButtonElement | null>(null);

/** 띠의 글 — 붙어 있으면 빈 글(알림 영역만 남는다) */
const message = computed(() => (props.state === "connected" ? "" : CONNECTION_HINTS[props.state]));

// [다시 연결] 이 사라질 때 그 버튼에 있던 초점을 띠로 옮긴다. watch 는 DOM 을 바꾸기 전(flush 'pre')에 불려 버튼이 아직 있어
// 초점을 잴 수 있고, 바꾼 뒤(nextTick) 띠에 준다
watch(
  () => props.state,
  async (next) => {
    if (next === "lost" || typeof document === "undefined") return;
    const button = retryButton.value;
    if (!button || document.activeElement !== button) return;
    await nextTick();
    root.value?.focus();
  },
);
</script>
