<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="skx-result">
      <h1 class="skx-sr-only">추천 도서 큐레이션</h1>
      <div class="skx-result-card">
        <!-- 뒤로가기 -->
        <button type="button" class="skx-detail-back" @click="$router.back()">
          <img class="skx-detail-back__icon" src="/img/ico-arrow.svg" alt="">
          <span class="skx-detail-back__label">검색 목록 돌아가기</span>
        </button>

        <!-- 헤더 -->
        <div class="skx-recommend-main__wrap">
          <div class="skx-recommend-main__tit">내 상황에 맞는 도서 추천받기</div>
          <div class="skx-recommend-main__txt">지금 나에게 필요한 책을 AI가 딱 맞게 추천해드려요.</div>
        </div>

        <!-- 상황 카드 목록 -->
        <div class="skx-recommend-list__wrap">
          <div class="skx-ai-header__title skx-recommend-list__tit">현재 나의 상황이 어떠한가요?</div>
          <ul class="skx-recommend-list">
            <li class="skx-recommend-item item-01">
              <NuxtLink to="/recommend/01" class="skx-recommend-item__inn skx-recommend__hover">
                <span class="skx-recommend-item__txt">위로가 <br>필요할 때</span>
              </NuxtLink>
            </li>
            <li class="skx-recommend-item item-02">
              <NuxtLink to="/recommend/02" class="skx-recommend-item__inn skx-recommend__hover">
                <span class="skx-mt-deco skx-mt-deco--1" aria-hidden="true"><i></i></span>
                <span class="skx-mt-deco skx-mt-deco--2" aria-hidden="true"><i></i></span>
                <span class="skx-mt-deco skx-mt-deco--3" aria-hidden="true"><i></i></span>
                <span class="skx-recommend-item__txt">심리적 단단함이 <br>필요할 때</span>
              </NuxtLink>
            </li>
            <li class="skx-recommend-item item-03">
              <NuxtLink to="/recommend/03" class="skx-recommend-item__inn skx-recommend__hover">
                <img class="skx-reco-c03 skx-reco-c03--star-s" src="/img/skx-reco-c03-star.svg" alt="" aria-hidden="true">
                <img class="skx-reco-c03 skx-reco-c03--star-l" src="/img/skx-reco-c03-star.svg" alt="" aria-hidden="true">
                <img class="skx-reco-c03 skx-reco-c03--curve" src="/img/skx-reco-c03-curve.svg" alt="" aria-hidden="true">
                <span class="skx-recommend-item__txt">늦은 밤, <br>잠이 오지 않을 때</span>
              </NuxtLink>
            </li>
            <li class="skx-recommend-item item-04">
              <NuxtLink to="/recommend/04" class="skx-recommend-item__inn skx-recommend__hover">
                <span class="skx-recommend-item__txt">흥미진진한 역사 이야기가 <br>궁금할 때</span>
              </NuxtLink>
            </li>
          </ul>
        </div>
      </div>
    </main>

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
const toast = ref('')
function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}
</script>
