<template>
  <section class="skx-aip" :aria-label="title">
    <header class="skx-aip__head">
      <img class="skx-aip__logo" :src="loading ? '/ic_ing.gif' : '/ic_done.png'" alt="SKOVIX AI" />
      <h2 class="skx-aip__title">{{ title }}</h2>
      <p v-if="hint" class="skx-aip__hint">
        마음에 드는 자료를 찾으셨다면 <strong>DeepRead</strong>로 자료와 대화해보세요
      </p>
    </header>
    <!-- 본문은 부모가 채운다 — 왼쪽 글(2) : 오른쪽(1) 두 칸이다 -->
    <div class="skx-aip__body"><slot /></div>
  </section>
</template>

<script setup lang="ts">
// 결과 화면의 'AI 검색 결과' 패널 틀 — 소장자료·논문이 같이 쓴다(머리: 로고 + 제목 | 오른쪽 DeepRead 안내, 본문: 2 : 1 두 칸).
// 안쪽 내용(추천 이유 글·추천 1권 카드·참고 논문 목록)은 슬롯으로 받는다
withDefaults(
  defineProps<{
    title?: string;
    /** AI 글을 받는 중이면 움직이는 로고 */
    loading?: boolean;
    /** 머리 오른쪽의 DeepRead 안내를 보인다 */
    hint?: boolean;
  }>(),
  { title: "AI 검색 결과", loading: false, hint: false },
);
</script>
