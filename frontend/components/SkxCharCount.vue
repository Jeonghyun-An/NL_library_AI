<!-- frontend/components/SkxCharCount.vue -->
<!-- 글자 수 표시 — 입력창의 maxlength 와 함께 쓴다(한도는 maxlength 가 막고, 이것은 얼마나 썼는지 보인다).
     '{length}/{max}' 를 늘 보이고, 한도 가까이(near — 기본 max 의 90%)면 --near, 한도에 닿으면(length >= max) --limit 와 함께
     '{max}자까지 입력할 수 있습니다'(charLimitMessage — 서버 422 안내와 같은 말)를 보이며 화면 낭독기에도 알린다(aria-live="polite").
     상태 셈은 utils/apiErrors.ts 의 charCountState(순수 함수 — 테스트가 직접 돌린다).
     알림 칸(__msg)은 비어 있어도 늘 그려 둔다 — 이미 있던 live 영역에 글이 들어가야 낭독기가 읽는다(한도에 닿는 순간 새로 생긴 요소는 놓친다).
     글자 수(__num)는 live 로 두지 않는다 — 한 글자마다 읽히면 입력을 방해한다. 입력창이 aria-describedby 로 이 요소의 id 를 가리키면
     초점을 줄 때 지금 글자 수가 읽힌다(id 는 뿌리 요소로 내려간다).
     디자인은 이 클래스(style_skovix.css 의 '[S] 공통 오류·빈 상태')에만 입히면 실제 화면 전체에 반영된다:
       .skx-charcount · .skx-charcount--near · .skx-charcount--limit · [data-state="normal|near|limit"] · .skx-charcount__num · .skx-charcount__msg -->
<template>
  <span
    class="skx-charcount"
    :class="{ 'skx-charcount--near': state === 'near', 'skx-charcount--limit': state === 'limit' }"
    :data-state="state"
  >
    <span class="skx-charcount__msg" aria-live="polite">{{ state === "limit" ? limitMessage : "" }}</span>
    <span class="skx-charcount__num">{{ length }}/{{ max }}</span>
  </span>
</template>

<script setup lang="ts">
import { charCountState, charLimitMessage } from "~/utils/apiErrors";

const props = defineProps<{
  /** 지금 글자 수(보통 v-model 값의 length — maxlength 와 같은 셈) */
  length: number;
  /** 한도 — 입력창의 maxlength 와 같은 값 */
  max: number;
  /** 이 글자 수부터 '가까움' 모양. 없으면 max 의 90%(소수점 아래 버림) */
  near?: number;
}>();

const state = computed(() => charCountState(props.length, props.max, props.near));
const limitMessage = computed(() => charLimitMessage(props.max));
</script>
