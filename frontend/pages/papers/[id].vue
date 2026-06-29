<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <div class="skx-result-card">
      <main class="skx-pdetail">
        <!-- 뒤로가기 -->
        <button type="button" class="skx-pdetail__back" @click="$router.back()">
          <img src="/img/ico-arrow.svg" alt="">
          검색 목록 돌아가기
        </button>

        <div v-if="loading" style="padding:40px;text-align:center">
          <img src="/img/ico-spinner.svg" alt="" style="width:32px">
        </div>

        <template v-else-if="paper">
          <!-- 논문 헤더 -->
          <section class="skx-pdetail__hero">
            <div class="skx-pdetail__cover">
              <img src="/img/img-paper-thumb.png" alt="논문 표지">
            </div>
            <div class="skx-pdetail__meta">
              <div class="skx-pdetail__top-row">
                <div class="skx-pdetail__badges">
                  <span v-if="paper.book_info?.genre" class="skx-ptag skx-ptag--kci">
                    {{ GENRE_LABELS[paper.book_info.genre] || paper.book_info.genre }}
                  </span>
                  <span v-if="matchScore" class="skx-ptag skx-ptag--score">정합성 {{ matchScore }}%</span>
                </div>
                <div class="skx-pdetail__share-group">
                  <button type="button" class="skx-btn-icon-sm" aria-label="출처 인용"
                    @click="citationModal = true">
                    <img src="/img/ico-bookmark.svg" alt="">
                  </button>
                </div>
              </div>
              <h1 class="skx-pdetail__title">{{ paper.book_info?.title }}</h1>
              <p v-if="paper.book_info?.title_remainder" class="skx-pdetail__title-en">
                {{ paper.book_info.title_remainder }}
              </p>
              <div class="skx-pdetail__rows">
                <div v-if="paper.book_info?.personal_author || paper.book_info?.corporate_author" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">저자정보</span>
                  <span class="skx-pdetail__row-val">{{ paper.book_info?.personal_author || paper.book_info?.corporate_author }}</span>
                </div>
                <div v-if="paper.book_info?.publisher" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">저널정보</span>
                  <span class="skx-pdetail__row-val">{{ paper.book_info.publisher }}</span>
                </div>
                <div v-if="paper.book_info?.pub_date" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">발행년도</span>
                  <span class="skx-pdetail__row-val">{{ paper.book_info.pub_date }}</span>
                </div>
              </div>
              <div class="skx-pdetail__btns">
                <button type="button"
                  :class="['skx-btn-talk skx-btn-talk--paper', chatOpen && 'is-active']"
                  @click="chatOpen = !chatOpen">
                  <span class="skx-btn-talk__glow" aria-hidden="true"></span>
                  <span class="skx-btn-talk__panel" aria-hidden="true"></span>
                  <img class="skx-btn-talk__ico" src="/img/ico-chat.svg" alt="">
                  <span class="skx-btn-talk__label">논문과 대화하기</span>
                </button>
                <button type="button" class="skx-btn-pbmark-sm" aria-label="출처 인용"
                  @click="citationModal = true">
                  <img src="/img/ico-paper-bookmark.svg" alt="">
                </button>
              </div>
            </div>
          </section>

          <!-- AI 큐레이션 수직탭 -->
          <section class="skx-curation">
            <h2 class="skx-section-title">AI 큐레이션</h2>
            <div class="skx-curation-panel">
              <div class="skx-vtabs-col">
                <div class="skx-vtabs" role="tablist" ref="vtabsRef">
                  <span class="skx-vtabs__slider" :style="vtabSliderStyle"></span>
                  <button v-for="tab in curationTabs" :key="tab.key"
                    type="button"
                    :class="['skx-vtab', curationTab === tab.key && 'is-active']"
                    role="tab"
                    :aria-selected="curationTab === tab.key"
                    @click="switchCurationTab(tab.key)">{{ tab.label }}</button>
                </div>
              </div>
              <div class="skx-curation-content">
                <div class="skx-curation-card">
                  <div v-if="curationTab === 'ai-summary'" role="tabpanel">
                    <p v-if="summaryLoading" class="skx-curation-text">AI가 핵심을 분석 중입니다...</p>
                    <div v-else-if="summaryText" class="skx-curation-text" v-html="renderedSummary" />
                    <p v-else class="skx-curation-text">AI 분석 정보가 없습니다.</p>
                  </div>
                  <p v-else-if="curationTab === 'abstract'" role="tabpanel" class="skx-curation-text">
                    {{ paper.book_info?.abstract || '초록 정보가 없습니다.' }}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <!-- 아코디언: 키워드 -->
          <div class="skx-paccordion">
            <div class="skx-paccord">
              <button type="button" class="skx-paccord__head"
                :aria-expanded="keywordOpen"
                @click="keywordOpen = !keywordOpen">
                <span class="skx-paccord__title">키워드</span>
                <img class="skx-paccord__arrow" src="/img/ico-arrow-down.svg" alt="" aria-hidden="true"
                  :style="keywordOpen ? 'transform:rotate(180deg)' : ''">
              </button>
              <div v-if="keywordOpen" class="skx-paccord__body-outer">
                <div class="skx-paccord__body">
                  <div class="skx-keyword-list">
                    <span v-for="kw in keywords" :key="kw" class="skx-keyword">{{ kw }}</span>
                    <span v-if="!keywords.length" style="color:#bbb;font-size:12px">키워드 정보가 없습니다.</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 아코디언: 참고문헌 -->
            <div class="skx-paccord">
              <button type="button" class="skx-paccord__head"
                :aria-expanded="refsOpen"
                @click="refsOpen = !refsOpen">
                <span class="skx-paccord__title">참고문헌</span>
                <img class="skx-paccord__arrow" src="/img/ico-arrow-down.svg" alt="" aria-hidden="true"
                  :style="refsOpen ? 'transform:rotate(180deg)' : ''">
              </button>
              <div v-if="refsOpen" class="skx-paccord__body-outer">
                <div class="skx-paccord__body">
                  <ol v-if="paper.book_info?.references?.length" class="skx-refs-list">
                    <li v-for="(ref, i) in paper.book_info.references" :key="i" class="skx-ref-item">{{ ref }}</li>
                  </ol>
                  <p v-else style="color:#bbb;font-size:12px;padding:8px 0">참고문헌 정보가 없습니다.</p>
                </div>
              </div>
            </div>
          </div>

          <!-- AI 연관 논문 추천 -->
          <section class="skx-reco">
            <h2 class="skx-section-title">AI 연관 논문 추천</h2>
            <div class="skx-reco-panel">
              <div class="skx-reco-list">
                <div v-if="relatedLoading" style="padding:16px;color:#bbb;font-size:12px">불러오는 중...</div>
                <button v-for="rel in relatedItems" :key="rel.book_id"
                  type="button"
                  :class="['skx-reco-item', selectedRelated?.book_id === rel.book_id && 'is-active']"
                  @click="selectedRelated = rel">
                  <img class="skx-reco-item__thumb" src="/img/ico-book-thumb.svg" alt="">
                  <div class="skx-reco-item__inner">
                    <span class="skx-reco-item__name">{{ rel.book_info?.title || rel.book_id }}</span>
                    <span class="skx-reco-item__score">정합성 {{ Math.round((rel.score || 0) * 100) }}%</span>
                  </div>
                </button>
              </div>
              <div v-if="!selectedRelated" class="skx-reco-empty">
                <img class="skx-reco-empty__logo" src="/img/logo-mark.svg" alt="SKOVIX">
                <p class="skx-reco-empty__text">추천 논문을 클릭해주세요</p>
              </div>
              <div v-else class="skx-reco-detail">
                <div class="skx-reco-info">
                  <h3 class="skx-reco-title">{{ selectedRelated.book_info?.title }}</h3>
                  <button class="skx-btn-loan" style="margin-top:12px"
                    @click="navigateTo(`/papers/${selectedRelated.book_id}`)">상세 보기</button>
                </div>
              </div>
            </div>
          </section>
        </template>
      </main>
    </div>

    <!-- 채팅 패널 -->
    <aside :class="['skx-chat-panel', chatOpen && 'is-open']" v-if="paper">
      <div class="skx-chat-panel__inner">
        <div class="skx-chat-header">
          <button type="button" class="skx-chat-close" @click="chatOpen = false">
            <img src="/img/ico-arrow.svg" alt="" class="skx-chat-close__ico">
          </button>
          <h2 class="skx-chat-title">논문과 대화하기</h2>
        </div>
        <BookChat :cnts-id="paperId" @close="chatOpen = false" />
      </div>
    </aside>

    <!-- 출처 인용 모달 -->
    <CitationModal
      :open="citationModal"
      :book-id="paperId"
      :references="paper?.book_info?.references ?? []"
      @close="citationModal = false"
    />

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from 'marked'

const route = useRoute()
const config = useRuntimeConfig()
const paperId = route.params.id as string

const matchScore = computed(() => {
  const s = route.query.score
  return s ? Math.round(Number(s) * 100) : null
})

const GENRE_LABELS: Record<string, string> = {
  paper: '학술논문', thesis: '학위논문', report: '연구보고서',
  manual: '매뉴얼', book: '단행본', other: '기타',
}

// Data
const paper = ref<any>(null)
const loading = ref(false)

// Vertical tabs
const vtabsRef = ref<HTMLElement | null>(null)
const vtabSliderStyle = ref<{ height: string; transform: string }>({ height: '0px', transform: 'translateY(0px)' })
const curationTab = ref('ai-summary')
const curationTabs = [
  { key: 'ai-summary', label: 'AI가 분석한 연구 핵심' },
  { key: 'abstract', label: '초록' },
]

function updateVtabSlider() {
  if (!vtabsRef.value) return
  const active = vtabsRef.value.querySelector('.skx-vtab.is-active') as HTMLElement | null
  if (!active) return
  vtabSliderStyle.value = {
    height: active.offsetHeight + 'px',
    transform: `translateY(${active.offsetTop}px)`,
  }
}

function switchCurationTab(key: string) {
  curationTab.value = key
  nextTick(() => updateVtabSlider())
}

// Accordion
const keywordOpen = ref(false)
const refsOpen = ref(false)

const keywords = computed<string[]>(() => {
  const kw = paper.value?.book_info?.keyword || ''
  return kw ? kw.split(',').map((k: string) => k.trim()).filter(Boolean) : []
})

// AI summary
const summaryText = ref('')
const summaryLoading = ref(false)
const renderedSummary = computed(() =>
  summaryText.value ? (marked.parse(summaryText.value) as string) : ''
)

// Related
const relatedItems = ref<any[]>([])
const relatedLoading = ref(false)
const selectedRelated = ref<any>(null)

// UI
const chatOpen = ref(false)
const citationModal = ref(false)
const toast = ref('')

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

async function fetchPaper() {
  loading.value = true
  try {
    const data = await $fetch<any>(`${config.public.apiBase}/books/${paperId}`)
    paper.value = data
  } catch {
    paper.value = null
  } finally {
    loading.value = false
  }
}

async function fetchRelated() {
  relatedLoading.value = true
  try {
    const data = await $fetch<any>(`${config.public.apiBase}/books/${paperId}/related`)
    relatedItems.value = data?.results || []
  } catch { /* silent */ }
  finally { relatedLoading.value = false }
}

onMounted(async () => {
  await fetchPaper()
  fetchRelated()
  nextTick(() => updateVtabSlider())
})
</script>
