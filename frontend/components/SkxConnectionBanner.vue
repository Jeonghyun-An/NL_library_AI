<!-- frontend/components/SkxConnectionBanner.vue -->
<!-- 실시간 연결 끊김 띠 — 딥리서치 진행 화면·연구 작업대의 SSE(EventSource)가 끊겼을 때 화면 위쪽에 얇게 알린다.
       reconnecting — 끊겨 다시 붙는 중(백오프 재연결이 도는 동안). role="status" 로 조용히 알린다
       lost         — 다시 붙지 못함. role="alert" 로 바로 읽고, 부모가 @retry 를 달면(onRetry prop) [다시 연결] 을 그린다
     띠 모양만 맡는다 — 화면 위 어디에 붙일지(sticky 등)는 쓰는 화면이 정한다.
     디자인은 이 클래스(style_skovix.css 의 '[S] 공통 오류·빈 상태')에만 입히면 실제 화면 전체에 반영된다:
       .skx-conn · .skx-conn--{state} · [data-state] · .skx-conn__msg · .skx-conn__retry
     문구는 utils/apiErrors.ts 의 CONNECTION_HINTS·CONNECTION_RETRY_LABEL -->
<template>
  <div
    class="skx-conn"
    :class="`skx-conn--${state}`"
    :data-state="state"
    :role="state === 'lost' ? 'alert' : 'status'"
  >
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
