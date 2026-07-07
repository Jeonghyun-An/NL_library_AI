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
          <img class="skx-detail-back__icon" src="/img/ico-arrow.svg" alt="" />
          <span class="skx-detail-back__label">검색 목록 돌아가기</span>
        </button>

        <!-- 헤더 -->
        <div class="skx-recommend-main__wrap">
          <div class="skx-recommend-main__tit">
            내 상황에 맞는 도서 추천받기
          </div>
          <div class="skx-recommend-main__txt">
            지금 나에게 필요한 책을 AI가 딱 맞게 추천해드려요.
          </div>
        </div>

        <!-- 상황 카드 목록 -->
        <div class="skx-recommend-list__wrap">
          <div class="skx-ai-header__title skx-recommend-list__tit">
            현재 나의 상황이 어떠한가요?
          </div>
          <ul class="skx-recommend-list">
            <li class="skx-recommend-item">
              <NuxtLink
                to="/recommend/01"
                class="skx-recommend-item__inn skx-recommend-item__inn--img skx-recommend__hover"
              >
                <img
                  class="skx-recommend-item__img"
                  src="/img/skx-reco-card-01.png"
                  alt="위로가 필요할 때"
                />
              </NuxtLink>
            </li>
            <li class="skx-recommend-item">
              <NuxtLink
                to="/recommend/02"
                class="skx-recommend-item__inn skx-recommend-item__inn--img skx-recommend__hover"
              >
                <img
                  class="skx-recommend-item__img"
                  src="/img/skx-reco-card-02.png"
                  alt="심리적 단단함이 필요할 때"
                />
              </NuxtLink>
            </li>
            <li class="skx-recommend-item">
              <NuxtLink
                to="/recommend/03"
                class="skx-recommend-item__inn skx-recommend-item__inn--img skx-recommend__hover"
              >
                <img
                  class="skx-recommend-item__img"
                  src="/img/skx-reco-card-03.png"
                  alt="늦은 밤, 잠이 오지 않을 때"
                />
              </NuxtLink>
            </li>
            <li class="skx-recommend-item">
              <NuxtLink
                to="/recommend/04"
                class="skx-recommend-item__inn skx-recommend-item__inn--img skx-recommend__hover"
              >
                <img
                  class="skx-recommend-item__img"
                  src="/img/skx-reco-card-04.png"
                  alt="흥미진진한 역사 이야기가 궁금할 때"
                />
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
const toast = ref("");
function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}
</script>
