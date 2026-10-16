<!-- frontend/components/SkxInlineError.vue -->
<!-- 줄 단위 오류 안내 — 입력창 아래·카드 안·스트림이 끊긴 답 뒤처럼 흐름 속에 한 줄로 알린다(섹션 전체가 비면 SkxErrorState).
     디자인은 이 클래스(style_skovix.css 의 '[S] 공통 오류·빈 상태')에만 입히면 전체에 반영된다:
       .skx-inline-error · .skx-inline-error__msg · .skx-inline-error__retry
     부모가 @retry 를 달면 onRetry prop 으로 들어와 그때만 [다시 시도] 를 그린다. 기본 슬롯은 글 뒤에 덧붙일 링크·버튼 자리 -->
<template>
  <p class="skx-inline-error" role="alert">
    <span class="skx-inline-error__msg">{{ message }}</span>
    <button
      v-if="onRetry"
      type="button"
      class="skx-inline-error__retry"
      :disabled="busy"
      :aria-busy="busy ? 'true' : undefined"
      @click="onRetry()"
    >
      {{ retryLabel }}
    </button>
    <slot />
  </p>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    /** 안내 글(apiErrorMessage 의 결과 등) */
    message: string;
    /** 재시도 버튼 글 */
    retryLabel?: string;
    /** 재시도 중 — 버튼을 잠그고 aria-busy */
    busy?: boolean;
    /** 부모의 @retry 가 이 prop 으로 들어온다 — 있을 때만 [다시 시도] 를 그린다 */
    onRetry?: () => void;
  }>(),
  { retryLabel: "다시 시도", busy: false },
);
</script>
