<!-- frontend/components/research/ResearchExampleCards.vue -->
<!-- 메인에서 DeepResearch 모드를 켰을 때 입력창 아래에 서는 예시 연구 카드(06d 2부 — 사용자 결정 2026-10-13). 미리 돌린 실제 연구라
     읽기 전용이고(쓰기 API 409), 질문·실행 시각·코퍼스 범위를 보인다(시연 정직성 규칙). 누르면 그 연구 화면으로 간다.
     예시가 없거나(리허설에서 mark_example.py 로 지정하기 전) 목록을 못 읽으면 아무것도 그리지 않는다 -->
<template>
  <section v-if="examples?.length" class="rs-examples" aria-labelledby="rs-examples-title">
    <h2 id="rs-examples-title" class="rs-examples__title">예시 연구</h2>
    <p class="rs-examples__note">미리 돌려 둔 실제 연구예요.<br />둘러볼 수 있고 바꿀 수는 없어요.</p>
    <ul class="rs-examples__list">
      <li v-for="ex in examples" :key="ex.id">
        <NuxtLink :to="exampleRoute(ex)" class="rs-examples__card">
          <span class="rs-examples__kicker">읽기 전용</span>
          <span class="rs-examples__q">{{ ex.question }}</span>
          <span v-if="metas[ex.id]?.ranAt" class="rs-examples__meta">{{ metas[ex.id]?.ranAt }}</span>
          <span v-if="metas[ex.id]?.scope" class="rs-examples__meta">{{ metas[ex.id]?.scope }}</span>
        </NuxtLink>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useResearchExamples } from "~/composables/useResearchWorks";
import { exampleRoute } from "~/utils/researchExamples";

const { examples, metas, load } = useResearchExamples();

// 예시 목록 API 는 브라우저 ID 헤더가 있어야 한다 — 서버 렌더가 아니라 마운트 뒤에 읽는다(사이드바·논문 화면과 같은 관례)
onMounted(() => {
  void load();
});
</script>
