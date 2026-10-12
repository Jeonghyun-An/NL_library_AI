<template>
  <!-- 상세 위 알약 검색바 — 결과 화면의 검색바(.skx-rsearch)와 같은 모양. 들어온 검색어가 채워져 있고,
       보내면 부모가 정한 곳(같은 검색어면 그 결과로 돌아가기, 다르면 새 검색)으로 간다 -->
  <form class="skx-rsearch dt-search" role="search" @submit.prevent="submit">
    <label class="skx-sr-only" :for="inputId">{{ label }}</label>
    <input
      :id="inputId"
      v-model="text"
      type="text"
      class="skx-rsearch__input"
      :placeholder="placeholder"
      enterkeyhint="search"
    />
    <button type="submit" class="skx-send" :aria-label="`${label} 보내기`">
      <img src="/img/ico-send.svg" alt="" />
    </button>
  </form>
</template>

<script setup lang="ts">
const props = defineProps<{
  /** 처음 채울 검색어 */
  initial: string;
  /** 입력칸 이름(스크린리더) — '논문 검색어' 등 */
  label: string;
  placeholder: string;
}>();
const emit = defineEmits<{ submit: [query: string] }>();

const inputId = `dt-search-${useId()}`;
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
