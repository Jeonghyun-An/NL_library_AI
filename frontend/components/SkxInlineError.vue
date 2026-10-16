<!-- frontend/components/SkxInlineError.vue -->
<!-- 줄 단위 오류 안내 — 입력창 아래·카드 안·스트림이 끊긴 답 뒤처럼 흐름 속에 한 줄로 알린다(섹션 전체가 비면 SkxErrorState).
     디자인은 이 클래스(style_skovix.css 의 '[S] 공통 오류·빈 상태')에만 입히면 전체에 반영된다:
       .skx-inline-error · .skx-inline-error__icon · .skx-inline-error__body · .skx-inline-error__msg · .skx-inline-error__retry
     글자는 본문색이고(빨갛게 칠하지 않는다 — 사용자 지적 2026-10-16), 앞의 작은 경고 삼각형(16px)만 위험색이다.
     부모가 @retry 를 달면 onRetry prop 으로 들어와 그때만 [다시 시도](포인트색 글자 버튼)를 그린다. 재시도 중(busy)이면 aria-disabled·aria-busy 로
     알리고 클릭만 무시한다(disabled 면 버튼이 초점을 잃는다). 기본 슬롯은 글 뒤에 덧붙일 링크·버튼 자리 — 뿌리와 글 묶음을 <div> 로 두어
     슬롯에 블록 요소(<p>·<div>)를 넣어도 HTML 이 깨지거나 SSR 수화가 어긋나지 않는다 -->
<template>
  <div class="skx-inline-error" role="alert">
    <span class="skx-inline-error__icon" aria-hidden="true">
      <svg
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
    <div class="skx-inline-error__body">
      <span class="skx-inline-error__msg">{{ message }}</span>
      <button
        v-if="onRetry"
        type="button"
        class="skx-inline-error__retry"
        :aria-disabled="busy ? 'true' : undefined"
        :aria-busy="busy ? 'true' : undefined"
        @click="retry"
      >
        {{ retryLabel }}
      </button>
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    /** 안내 글(apiErrorMessage 의 결과 등) */
    message: string;
    /** 재시도 버튼 글 */
    retryLabel?: string;
    /** 재시도 중 — aria-disabled·aria-busy 로 알리고 클릭을 무시한다(초점은 버튼에 남는다) */
    busy?: boolean;
    /** 부모의 @retry 가 이 prop 으로 들어온다 — 있을 때만 [다시 시도] 를 그린다 */
    onRetry?: () => void;
  }>(),
  { retryLabel: "다시 시도", busy: false },
);

// 재시도 중에는 누름을 무시한다 — disabled 대신이라 버튼은 초점을 잃지 않는다
function retry() {
  if (!props.busy) props.onRetry?.();
}
</script>
