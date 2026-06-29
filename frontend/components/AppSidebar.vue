<template>
  <aside :class="['skx-lnb', !open && 'is-lnb-collapsed']">
    <!-- 접힌 상태에서 펼치기 버튼 -->
    <button type="button" class="skx-lnb__expand" aria-label="사이드바 열기" @click="open = true">
      <img src="/img/ico-arrow.svg" alt="">
    </button>

    <!-- 로고 + 접기 버튼 -->
    <div class="skx-lnb__logo">
      <a class="skx-logo" href="/" aria-label="SKOVIX 메인으로 이동">
        <img class="skx-logo__mark" src="/img/logo-mark.svg" alt="">
        <img class="skx-logo__word" src="/img/logo-word.svg" alt="SKOVIX">
      </a>
      <button type="button" class="skx-icon-btn" aria-label="사이드바 접기" @click="open = false">
        <img src="/img/ico-collapse.svg" alt="">
      </button>
    </div>

    <!-- 새 채팅 -->
    <div class="skx-lnb__new">
      <button type="button" class="skx-newchat" @click="navigateTo('/')">
        <span class="skx-newchat__icon"><img src="/img/ico-newchat.svg" alt=""></span>
        <span class="skx-newchat__label">새 채팅</span>
      </button>
    </div>

    <!-- 메뉴 -->
    <nav class="skx-lnb__menu" aria-label="주요 메뉴">
      <button type="button" class="skx-menu-item" @click="emit('cart')">
        <span class="skx-menu-item__icon"><img src="/img/ico-cart-menu.svg" alt=""></span>
        <span class="skx-menu-item__label">대출 장바구니</span>
      </button>
      <button type="button" class="skx-menu-item" @click="emit('save')">
        <span class="skx-menu-item__icon"><img src="/img/ico-bookmark-menu.svg" alt=""></span>
        <span class="skx-menu-item__label">저장목록</span>
      </button>
    </nav>

    <!-- 검색기록 -->
    <div class="skx-history">
      <p class="skx-history__title">검색기록</p>
      <ul class="skx-history__list">
        <li v-for="h in history" :key="h.id">
          <button
            type="button"
            :class="['skx-history-item', h.id === activeId && 'is-active']"
            @click="emit('restore', h)"
          >
            <span class="skx-history-item__query">{{ h.query }}</span>
            <span class="skx-history-item__time">{{ formatTime(h.timestamp) }}</span>
          </button>
        </li>
      </ul>
    </div>

    <!-- 프로필 -->
    <div class="skx-profile">
      <img class="skx-profile__avatar" src="/img/ico-avatar.svg" alt="">
      <span class="skx-profile__name">김랜드</span>
      <button type="button" class="skx-icon-btn" aria-label="설정">
        <img src="/img/ico-settings.svg" alt="">
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
const open = ref(true)

const props = defineProps<{
  history?: Array<{ id: string; query: string; timestamp: string | number }>
  activeId?: string
}>()

const emit = defineEmits<{
  cart: []
  save: []
  restore: [h: { id: string; query: string; timestamp: string | number }]
}>()

function formatTime(ts: string | number): string {
  if (!ts) return ''
  const d = new Date(ts)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '방금'
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`
  return d.toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' })
}
</script>
