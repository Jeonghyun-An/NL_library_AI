<!-- frontend/components/SkxErrorState.vue -->
<!-- 섹션·화면 단위 상태 블록 — 불러오기 실패·빈 결과·찾을 수 없음을 모든 화면이 이 하나로 보인다.
     디자인은 이 클래스(style_skovix.css 의 '[S] 공통 오류·빈 상태')에만 입히면 전체 오류 화면에 반영된다 — 화면마다 따로 꾸미지 않는다.
     디자인 훅: .skx-state · .skx-state--{kind} · [data-kind] · [data-tone] · .skx-state--compact
               .skx-state__icon(그림 자리 — 기본은 숨김) · .skx-state__title · .skx-state__msg · .skx-state__actions · .skx-state__retry · .skx-state__action(슬롯 버튼·링크)
     kind 별 의미(utils/apiErrors.ts 의 errorKind(err) 결과를 그대로 넘기면 된다):
       error     — 이유를 가리지 않는 일반 실패(기본값)
       network   — 서버에 닿지 못함(오프라인·연결 끊김)
       timeout   — 응답이 늦어 끊음(시간 제한·게이트웨이 504)
       busy      — 요청이 몰림(429·503) — 잠시 뒤 다시
       server    — 서버 오류(5xx)
       notFound  — 찾을 수 없음(404·410) — 지워졌거나 없는 주소
       invalid   — 입력이 올바르지 않음(400·413·422)
       conflict  — 지금 상태와 맞지 않음(409 — 다른 곳에서 바뀜 등)
       forbidden — 권한 없음(401·403)
       unknown   — 그 밖의 상태 코드
       empty     — 실패가 아닌 빈 결과(검색 결과 없음·기록 없음)
     data-tone: 'neutral'(empty·notFound — 사용자가 잘못한 것도 고장도 아니다) / 'error'(그 밖) — 열한 가지 kind 를 두 갈래로 꾸밀 때 쓴다.
     role: empty 는 status(조용히 알림), 나머지는 alert(바로 읽어 줌).
     재시도: 부모가 @retry 를 달면 onRetry prop 으로 들어와 그때만 [다시 시도] 버튼을 그린다. busy 면 aria-disabled·aria-busy 로 알리고 클릭만 무시한다
       (disabled 로 막으면 누른 버튼이 초점을 잃어 키보드·화면 낭독기 사용자가 제자리를 잃는다).
     기본 슬롯은 버튼 줄의 덧붙일 자리([처음 화면으로] 같은 링크) — 같은 모양을 쓰려면 class="skx-state__action" 을 단다 -->
<template>
  <div
    class="skx-state"
    :class="[`skx-state--${kind}`, { 'skx-state--compact': compact }]"
    :data-kind="kind"
    :data-tone="tone"
    :role="kind === 'empty' ? 'status' : 'alert'"
  >
    <span class="skx-state__icon" aria-hidden="true"></span>
    <component :is="titleTag" class="skx-state__title">{{ title }}</component>
    <p v-if="message" class="skx-state__msg">{{ message }}</p>
    <div v-if="onRetry || $slots.default" class="skx-state__actions">
      <button
        v-if="onRetry"
        type="button"
        class="skx-state__retry"
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
import type { ErrorStateKind } from "~/utils/apiErrors";

const props = withDefaults(
  defineProps<{
    /** 상태 종류 — 위 머리 주석. 기본 'error'(일반 실패) */
    kind?: ErrorStateKind;
    /** 한 줄 제목('결과를 불러오지 못했습니다') */
    title: string;
    /** 제목 아래 설명(apiErrorMessage 의 결과 등). 비면 그리지 않는다 */
    message?: string;
    /** 재시도 버튼 글 */
    retryLabel?: string;
    /** 재시도 중 — aria-disabled·aria-busy 로 알리고 클릭을 무시한다(초점은 버튼에 남는다) */
    busy?: boolean;
    /** 카드 상자 없이 좁게(이미 틀 안에 있는 칸·옆 칸용) */
    compact?: boolean;
    /** 제목 요소 — 화면 전체 상태(오류 페이지)면 h1, 절 안이면 기본 p */
    titleTag?: "p" | "h1" | "h2" | "h3";
    /** 부모의 @retry 가 이 prop 으로 들어온다 — 있을 때만 [다시 시도] 를 그린다 */
    onRetry?: () => void;
  }>(),
  { kind: "error", message: "", retryLabel: "다시 시도", busy: false, compact: false, titleTag: "p" },
);

// 사용자가 잘못한 것도 고장도 아닌 상태는 차분한 갈래로 — 나머지는 실패 갈래
const tone = computed(() => (props.kind === "empty" || props.kind === "notFound" ? "neutral" : "error"));

// 재시도 중에는 누름을 무시한다 — disabled 대신이라 버튼은 초점을 잃지 않는다
function retry() {
  if (!props.busy) props.onRetry?.();
}
</script>
