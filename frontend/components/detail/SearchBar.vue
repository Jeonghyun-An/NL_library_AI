<template>
  <!-- 상세 위 알약 검색바 — 결과 화면의 검색바(.skx-rsearch)와 같은 모양. 들어온 검색어가 채워져 있고,
       보내면 부모가 정한 곳(같은 검색어면 그 결과로 돌아가기, 다르면 새 검색)으로 간다.
       검색어는 서버 한도(SEARCH_QUERY_MAX — 500자)까지만 받고, 글자 수(SkxCharCount quiet)는 한도 가까이부터 보내기 왼쪽에 보인다
       (평소엔 화면에서만 숨는다 — 검색창마다 숫자가 늘 붙어 어수선하지 않게, 사용자 결정 2026-10-16) -->
  <form class="skx-rsearch dt-search" role="search" @submit.prevent="submit">
    <label class="skx-sr-only" :for="inputId">{{ label }}</label>
    <input
      :id="inputId"
      v-model="text"
      type="text"
      class="skx-rsearch__input"
      :placeholder="placeholder"
      :maxlength="SEARCH_QUERY_MAX"
      :aria-describedby="countId"
      enterkeyhint="search"
    />
    <SkxCharCount quiet :id="countId" :length="text.length" :max="SEARCH_QUERY_MAX" />
    <button type="submit" class="skx-send" :aria-label="`${label} 보내기`" :aria-disabled="!hasQuery(text)">
      <img src="/img/ico-send-up.svg" alt="" />
    </button>
  </form>
</template>

<script setup lang="ts">
import { hasQuery, SEARCH_QUERY_MAX } from "~/utils/searchInput";

const props = defineProps<{
  /** 처음 채울 검색어 */
  initial: string;
  /** 입력칸 이름(스크린리더) — '논문 검색어' 등 */
  label: string;
  placeholder: string;
}>();
const emit = defineEmits<{ submit: [query: string] }>();

const uid = useId();
const inputId = `dt-search-${uid}`;
const countId = `dt-search-count-${uid}`;
const text = ref(props.initial);
// 검색어가 늦게 정해지는 출처(보고서 질문을 읽어 온 뒤)도 있다 — 아직 아무것도 쓰지 않았을 때만 채운다
watch(
  () => props.initial,
  (next) => {
    if (!text.value.trim()) text.value = next;
  },
);

function submit() {
  if (text.value.trim()) emit("submit", text.value);
}
</script>
