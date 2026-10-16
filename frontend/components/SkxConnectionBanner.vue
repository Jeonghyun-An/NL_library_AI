<!-- frontend/components/SkxConnectionBanner.vue -->
<!-- 실시간 연결 끊김 띠 — 딥리서치 진행 화면·연구 작업대의 SSE(EventSource)가 끊겼을 때 화면 위쪽에 얇게 알린다.
       reconnecting — 끊겨 다시 붙는 중(백오프 재연결이 도는 동안). role="status" 로 조용히 알린다
       lost         — 다시 붙지 못함. role="alert" 로 바로 읽고, 부모가 @retry 를 달면(onRetry prop) [다시 연결] 을 그린다
     두 상태는 글자색이 같고(빨갛게 칠하지 않는다 — 사용자 지적 2026-10-16) 앞의 아이콘으로만 가른다: 다시 연결하는 중은 깜빡이는 점,
     연결하지 못함은 위험색 경고 삼각형.
     띠 모양만 맡는다 — 화면 위 어디에 붙일지(sticky 등)는 쓰는 화면이 정한다.
     디자인은 이 클래스(style_skovix.css 의 '[S] 공통 오류·빈 상태')에만 입히면 실제 화면 전체에 반영된다:
       .skx-conn · .skx-conn--{state} · [data-state] · .skx-conn__icon · .skx-conn__msg · .skx-conn__retry
     문구는 utils/apiErrors.ts 의 CONNECTION_HINTS·CONNECTION_RETRY_LABEL -->
<template>
  <div
    class="skx-conn"
    :class="`skx-conn--${state}`"
    :data-state="state"
    :role="state === 'lost' ? 'alert' : 'status'"
  >
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
    <span class="skx-conn__msg">{{ CONNECTION_HINTS[state] }}</span>
    <button v-if="state === 'lost' && onRetry" type="button" class="skx-conn__retry" @click="onRetry?.()">
      {{ CONNECTION_RETRY_LABEL }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { CONNECTION_HINTS, CONNECTION_RETRY_LABEL, type ConnectionState } from "~/utils/apiErrors";

defineProps<{
  /** 'reconnecting'(다시 연결하는 중) | 'lost'(연결하지 못함) */
  state: ConnectionState;
  /** 부모의 @retry 가 이 prop 으로 들어온다 — lost 일 때만 [다시 연결] 을 그린다 */
  onRetry?: () => void;
}>();
</script>
