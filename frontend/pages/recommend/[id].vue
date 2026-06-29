<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="skx-result">
      <h1 class="skx-sr-only">추천 도서 큐레이션 상세</h1>
      <div class="skx-result-card">
        <!-- 뒤로가기 -->
        <button type="button" class="skx-detail-back" @click="$router.back()">
          <img class="skx-detail-back__icon" src="/img/ico-arrow.svg" alt="" />
          <span class="skx-detail-back__label">돌아가기</span>
        </button>

        <!-- 히어로 배너 -->
        <div :class="['skx-rcd-hero', `skx-rcd-hero--${meta.heroType}`]">
          <template v-if="meta.heroType === '02'">
            <span class="skx-mt-deco skx-mt-deco--1" aria-hidden="true"><i></i></span>
            <span class="skx-mt-deco skx-mt-deco--2" aria-hidden="true"><i></i></span>
            <span class="skx-mt-deco skx-mt-deco--3" aria-hidden="true"><i></i></span>
          </template>
          <template v-if="meta.heroType === '03'">
            <img class="skx-reco-c03 skx-reco-c03--star-s" src="/img/skx-reco-c03-star.svg" alt="" aria-hidden="true" />
            <img class="skx-reco-c03 skx-reco-c03--star-l" src="/img/skx-reco-c03-star.svg" alt="" aria-hidden="true" />
            <img class="skx-reco-c03 skx-reco-c03--curve" src="/img/skx-reco-c03-curve.svg" alt="" aria-hidden="true" />
          </template>
          <div class="skx-rcd-hero__body">
            <h2 class="skx-rcd-hero__tit">{{ meta.title }}</h2>
            <p class="skx-rcd-hero__sub">{{ meta.sub }}</p>
          </div>
        </div>

        <!-- AI 텍스트 (타이핑 애니메이션) -->
        <div class="skx-rcd-ai">
          <div class="skx-rcd-ai__top">
            <img class="skx-rcd-ai__logo" src="/img/logo-mark.svg" alt="SKOVIX AI" />
            <span class="skx-rcd-ai__label">{{ meta.aiLabel }}</span>
            <span v-if="loading" style="font-size:12px;color:var(--skx-violet)">●</span>
          </div>
          <div :class="['skx-ai-answer-wrap', aiExpanded && 'is-expanded']" ref="aiWrapRef">
            <div class="skx-ai-answer">
              <p class="skx-ai-answer__text">{{ typedText }}</p>
            </div>
            <button v-if="showExpandBtn" type="button" class="skx-ai-expand-bar"
              :aria-expanded="aiExpanded" @click="aiExpanded = !aiExpanded">
              <span class="skx-ai-expand-bar__label">{{ aiExpanded ? '접기' : '펼치기' }}</span>
              <img class="skx-ai-expand-bar__arrow" src="/img/ico-arrow.svg" alt="" aria-hidden="true"
                :style="aiExpanded ? 'transform:rotate(90deg)' : 'transform:rotate(-90deg)'" />
            </button>
          </div>
        </div>

        <!-- 도서 선택 -->
        <div class="skx-rcd-select">
          <h3 class="skx-rcd-select__tit">가장 나에게 도움이되는 책을 선택해주세요.</h3>

          <!-- 로딩 -->
          <div v-if="loading" style="padding:40px;text-align:center">
            <img src="/img/ico-spinner.svg" alt="" style="width:32px">
            <p style="margin-top:12px;font-size:13px;color:#999">AI가 도서를 추천 중입니다...</p>
          </div>

          <div v-else class="skx-rcd-book-grid">
            <button
              v-for="(book, i) in recommendedBooks"
              :key="book.book_id"
              type="button"
              :class="['skx-rcd-book-card', `skx-rcd-book-card--${i + 1}`]"
              @click="openModal(book)"
            >
              <div class="skx-rcd-book-card__head">
                <img class="skx-rcd-book-card__icon" src="/img/ico-book-select.svg" alt="" />
                <p class="skx-rcd-book-card__desc">{{ book.reason }}</p>
              </div>
              <div class="skx-rcd-book-card__cover">
                <BookCover :book-id="book.book_id" />
              </div>
              <p class="skx-rcd-book-card__name">{{ book.book_info?.title || book.book_id }}</p>
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- 맞춤도서 추천 팝업 -->
    <div v-if="modalOpen" class="skx-rcd-modal-overlay"
      role="dialog" aria-modal="true"
      @click.self="modalOpen = false">
      <div class="skx-rcd-modal">
        <button type="button" class="skx-rcd-modal__close" aria-label="닫기" @click="modalOpen = false">
          <img src="/img/ico-close.svg" alt="" />
        </button>
        <h2 class="skx-rcd-modal__title">맞춤도서 추천</h2>
        <div class="skx-rcd-modal__card">
          <div class="skx-rcd-modal__card-top">
            <span class="skx-rcd-modal__badge">Book solution</span>
            <p class="skx-rcd-modal__desc">{{ selectedBook?.reason }}</p>
          </div>
          <div class="skx-rcd-modal__cover" v-if="selectedBook">
            <BookCover :book-id="selectedBook.book_id" />
          </div>
          <div class="skx-rcd-modal__book-info">
            <p class="skx-rcd-modal__book-title">{{ selectedBook?.book_info?.title }}</p>
            <p v-if="selectedBook?.quote" class="skx-rcd-modal__quote">"{{ selectedBook.quote }}"</p>
            <div class="skx-rcd-modal__meta" v-if="selectedBook?.book_info">
              <span v-if="selectedBook.book_info.personal_author || selectedBook.book_info.corporate_author">
                {{ selectedBook.book_info.personal_author || selectedBook.book_info.corporate_author }}
              </span>
            </div>
          </div>
        </div>
        <div class="skx-rcd-modal__btns">
          <button type="button" class="skx-rcd-modal__btn skx-rcd-modal__btn--outline"
            @click="navigateTo(`/books/${selectedBook?.book_id}`)">
            <img src="/img/ico-arrow.svg" alt="" />상세 보기
          </button>
          <button type="button" class="skx-rcd-modal__btn skx-rcd-modal__btn--dark"
            @click="showToast('준비 중입니다.')">
            <img src="/img/ico-download.svg" alt="" />솔루션 저장하기
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const config = useRuntimeConfig()
const apiBase = config.public.apiBase as string
const scenarioId = route.params.id as string

const toast = ref('')
function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

// ── 시나리오 메타 (UI 전용) ────────────────────────────────
interface ScenarioMeta {
  heroType: string
  title: string
  sub: string
  concern: string  // API에 보낼 실제 고민 텍스트
  aiLabel: string
}

const SCENARIO_META: Record<string, ScenarioMeta> = {
  '01': {
    heroType: '01',
    title: '위로가 필요할 때',
    sub: '지친 마음에 따뜻한 위로가 필요하다면 이 책들을 펼쳐보세요!',
    concern: '마음이 지치고 힘들어서 따뜻한 위로와 공감이 필요합니다. 나를 위로해줄 수 있는 도서를 추천해주세요.',
    aiLabel: '위로가 필요한 당신을 위해 AI가 추천하는 책!',
  },
  '02': {
    heroType: '02',
    title: '심리적 단단함이 필요할 때',
    sub: '마음 근육을 키워 단단해지고 싶다면 이 책들을 읽어보세요!',
    concern: '심리적으로 단단해지고 싶습니다. 역경을 이겨내고 내면의 힘을 키울 수 있는 도서를 추천해주세요.',
    aiLabel: '심리적 단단함을 만들 수 있게 AI가 추천하는 책!',
  },
  '03': {
    heroType: '03',
    title: '늦은 밤, 잠이 오지 않을 때',
    sub: '잠 못 드는 밤, 마음을 가라앉혀 줄 책들을 골라봤어요!',
    concern: '늦은 밤 잠이 오지 않습니다. 마음을 차분하게 가라앉히고 편안하게 해줄 도서를 추천해주세요.',
    aiLabel: '잠 못 드는 밤을 위해 AI가 추천하는 책!',
  },
  '04': {
    heroType: '04',
    title: '흥미진진한 역사 이야기가 궁금할 때',
    sub: '흥미진진한 역사의 세계로 빠져들 책들을 추천해드려요!',
    concern: '흥미진진한 역사 이야기가 궁금합니다. 재미있게 읽을 수 있는 역사 관련 도서를 추천해주세요.',
    aiLabel: '역사가 궁금한 당신을 위해 AI가 추천하는 책!',
  },
}

const meta = computed<ScenarioMeta>(() => SCENARIO_META[scenarioId] || SCENARIO_META['02'])

// ── API 데이터 ─────────────────────────────────────────────
interface RecommendedBook {
  book_id: string
  book_info?: any
  reason: string
  quote: string
}

const recommendedBooks = ref<RecommendedBook[]>([])
const loading = ref(false)

// ── AI 타이핑 애니메이션 ────────────────────────────────────
const typedText = ref('')
const aiWrapRef = ref<HTMLElement | null>(null)
const aiExpanded = ref(false)
const showExpandBtn = ref(false)

function typeText(text: string) {
  typedText.value = ''
  let i = 0
  const tick = () => {
    if (i < text.length) {
      typedText.value += text[i++]
      setTimeout(tick, 20)
    } else {
      nextTick(() => {
        if (aiWrapRef.value && aiWrapRef.value.scrollHeight > aiWrapRef.value.clientHeight + 10) {
          showExpandBtn.value = true
        }
      })
    }
  }
  tick()
}

// ── 모달 ───────────────────────────────────────────────────
const modalOpen = ref(false)
const selectedBook = ref<RecommendedBook | null>(null)

function openModal(book: RecommendedBook) {
  selectedBook.value = book
  modalOpen.value = true
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') modalOpen.value = false
}

// ── API 호출 ───────────────────────────────────────────────
async function fetchRecommend() {
  loading.value = true
  typedText.value = ''
  try {
    const data = await $fetch<any>(`${apiBase}/scenario/recommend`, {
      method: 'POST',
      body: {
        concern: meta.value.concern,
        top_k: 4,
      },
    })
    recommendedBooks.value = data?.books || []

    // AI 안내 텍스트: 첫 번째 책의 quote를 타이핑 애니메이션으로
    const firstQuote = data?.books?.[0]?.quote
    if (firstQuote) {
      typeText(`"${firstQuote}"`)
    } else {
      typeText(meta.value.concern)
    }
  } catch (e: any) {
    showToast('추천 도서를 불러오는 중 오류가 발생했습니다.')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  fetchRecommend()
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>
