# Publishing Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 퍼블리싱 HTML/CSS(skx-* 클래스 체계)를 기존 Nuxt 프로젝트에 Full 교체 방식으로 적용하고, common.js 미구현 기능(수직탭, 북마크 토글)을 Vue 반응형으로 추가 구현한다.

**Architecture:** style_skovix.css를 전역 CSS로 등록하고, 각 Vue 컴포넌트/페이지의 템플릿을 skx-* 클래스명으로 교체한다. 기존 Vue 반응형 로직(API 호출, SSE, 상태관리)은 유지하고 scoped `<style>` 섹션만 제거한다. common.js의 DOM 조작 로직은 Vue ref + computed로 대체한다.

**Tech Stack:** Nuxt 3, Vue 3 Composition API, TypeScript, style_skovix.css (전역 BEM CSS)

**소스 경로:** `C:\Users\LANDSOFT\Desktop\SKOVIX\수정_260629_skovix\`

---

## 파일 구조

| 파일 | 작업 |
|------|------|
| `frontend/nuxt.config.ts` | css 배열에 style_skovix.css 추가 |
| `frontend/assets/css/style_skovix.css` | 퍼블리싱 CSS 복사 |
| `frontend/public/img/*` | 퍼블리싱 이미지 전체 복사 |
| `frontend/components/AppSidebar.vue` | skx-lnb 구조로 전면 교체 |
| `frontend/composables/useBookmark.ts` | 북마크 on/off 상태 composable 신규 |
| `frontend/pages/index.vue` | landing + results 뷰 skx-* 교체 |
| `frontend/pages/books/[cnts_id].vue` | skx-detail + 수직탭 + 채팅패널 교체 |
| `frontend/pages/papers.vue` | skx-paper-result 구조 교체 |
| `frontend/pages/papers/[id].vue` | 논문 상세 신규 페이지 |
| `frontend/pages/recommend.vue` | 도서 추천 신규 페이지 |
| `frontend/pages/recommend/[id].vue` | 도서 추천 상세 신규 페이지 |

---

## Task 1: 에셋 복사 및 nuxt.config 등록

**Files:**
- Create: `frontend/assets/css/style_skovix.css`
- Create: `frontend/public/img/` (all images)
- Modify: `frontend/nuxt.config.ts`

- [ ] **Step 1: CSS 파일 복사**

```powershell
Copy-Item "C:\Users\LANDSOFT\Desktop\SKOVIX\수정_260629_skovix\files\css\style_skovix.css" `
  "C:\Users\LANDSOFT\mygit\NL_library_AI\frontend\assets\css\style_skovix.css"
```

- [ ] **Step 2: 이미지 파일 전체 복사**

```powershell
# public/img 디렉토리가 없으면 생성
New-Item -ItemType Directory -Force "C:\Users\LANDSOFT\mygit\NL_library_AI\frontend\public\img"

# 퍼블리싱 이미지 전체 복사 (덮어쓰기)
Copy-Item "C:\Users\LANDSOFT\Desktop\SKOVIX\수정_260629_skovix\files\img\*" `
  "C:\Users\LANDSOFT\mygit\NL_library_AI\frontend\public\img\" -Recurse -Force
```

- [ ] **Step 3: nuxt.config.ts에 CSS 등록**

`frontend/nuxt.config.ts`를 다음과 같이 수정:

```typescript
import tailwindcss from "@tailwindcss/vite";
import tsconfigPaths from "vite-tsconfig-paths";
import { resolve } from "path";

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },

  vite: {
    plugins: [tailwindcss(), tsconfigPaths()],
  },

  css: [
    resolve(__dirname, "assets/css/tailwind.css"),
    resolve(__dirname, "assets/css/style_skovix.css"),
  ],

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE ?? "/api",
    },
  },

  nitro: {
    devProxy: {
      "/api": {
        target: "http://localhost:18002",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 4: 커밋**

```bash
git add frontend/assets/css/style_skovix.css frontend/public/img frontend/nuxt.config.ts
git commit -m "feat: add publishing assets and register global CSS"
```

---

## Task 2: useBookmark composable 신규 구현

**Files:**
- Create: `frontend/composables/useBookmark.ts`

북마크 on/off 토글 상태를 로컬에서 관리하는 composable. 아이콘 경로(ico-bookmark.svg ↔ ico-bookmark-on.svg)를 computed로 반환.

- [ ] **Step 1: composable 파일 생성**

`frontend/composables/useBookmark.ts`:

```typescript
const bookmarkedIds = ref(new Set<string>())

export function useBookmark() {
  function isBookmarked(id: string): boolean {
    return bookmarkedIds.value.has(id)
  }

  function toggleBookmark(id: string): void {
    const next = new Set(bookmarkedIds.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    bookmarkedIds.value = next
  }

  function bookmarkIcon(id: string): string {
    return isBookmarked(id) ? '/img/ico-bookmark-on.svg' : '/img/ico-bookmark.svg'
  }

  return { isBookmarked, toggleBookmark, bookmarkIcon }
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/composables/useBookmark.ts
git commit -m "feat: add useBookmark composable for icon toggle state"
```

---

## Task 3: AppSidebar.vue — skx-lnb 구조 교체

**Files:**
- Modify: `frontend/components/AppSidebar.vue`

퍼블리싱 LNB 구조(`skx-lnb`, `skx-logo`, `skx-history` 등) 적용. props/emits는 기존 유지, scoped style 제거.

- [ ] **Step 1: AppSidebar.vue 전면 교체**

`frontend/components/AppSidebar.vue`:

```vue
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
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/components/AppSidebar.vue
git commit -m "feat: replace AppSidebar with skx-lnb publishing structure"
```

---

## Task 4: index.vue — landing + results 뷰 교체

**Files:**
- Modify: `frontend/pages/index.vue`

landing view는 `skx-contents` + `skx-panel`, results view는 `skx-result` + `skx-result-card` 구조로 교체.
기존 Vue 로직(handleSearch, fetchCuration, fetchPaperSummary, SSE 등) 전부 유지. scoped style 제거.

퍼블리싱에서 추가된 기능:
- 검색탭 슬라이더(`skx-tabs__slider`) 위치 계산 — `tabsRef` + `nextTick`
- 논문 필터 드롭다운(`skx-select`) 열기/닫기 — `filterOpen` ref
- 선택된 필터 칩(`skx-filter-chip`) 목록 — `selectedFilters` ref
- 신작도서 카운트업 애니메이션 — `onMounted` + `requestAnimationFrame`
- 신작도서 스켈레톤 컨베이어 — `setInterval`

- [ ] **Step 1: `<template>` 교체 — `skx-app` 래퍼 + 사이드바**

`frontend/pages/index.vue` 템플릿 최상단:

```vue
<template>
  <div class="skx-app">
    <AppSidebar
      :history="history"
      :active-id="currentHistoryId"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
      @restore="restoreHistory"
    />

    <!-- landing view -->
    <main v-if="view === 'landing'" class="skx-contents">
      <div class="skx-contents__inner">
        <h1 class="skx-hero">원하는 자료를 찾고 활용하는<br>가장 쉽고 편안한 검색을 경험해보세요!</h1>

        <!-- 검색 탭 슬라이더 -->
        <div class="skx-tabs" role="tablist" aria-label="검색 유형" ref="tabsRef">
          <span class="skx-tabs__slider" :style="tabSliderStyle" aria-hidden="true"></span>
          <button
            type="button"
            :class="['skx-tab skx-tab--book', mode === 'book' && 'is-active']"
            role="tab"
            :aria-selected="mode === 'book'"
            @click="setMode('book')"
          >
            <img class="skx-tab__icon"
              :src="mode === 'book' ? '/img/ico-tab-book-on.svg' : '/img/ico-tab-book-off.svg'" alt="">
            <span class="skx-tab__label">도서검색</span>
          </button>
          <button
            type="button"
            :class="['skx-tab skx-tab--paper', mode === 'paper' && 'is-active']"
            role="tab"
            :aria-selected="mode === 'paper'"
            @click="setMode('paper')"
          >
            <img class="skx-tab__icon"
              :src="mode === 'paper' ? '/img/ico-tab-paper-on.svg' : '/img/ico-tab-paper-off.svg'" alt="">
            <span class="skx-tab__label">논문검색</span>
          </button>
        </div>

        <!-- 도서 패널 -->
        <div class="skx-panel" :hidden="mode !== 'book'">
          <div class="skx-search">
            <div class="skx-search__box">
              <label class="skx-search__field">
                <span class="skx-sr-only">도서 검색어</span>
                <textarea
                  class="skx-search__input"
                  v-model="currentQuery"
                  placeholder="찾고싶은 도서를 문장으로 검색해보세요!"
                  :disabled="loading"
                  @keydown.enter.exact.prevent="handleSearch(currentQuery)"
                ></textarea>
              </label>
              <div class="skx-search__actions">
                <button type="button" class="skx-send" aria-label="검색" @click="handleSearch(currentQuery)">
                  <img src="/img/ico-send.svg" alt="">
                </button>
              </div>
            </div>
            <ul class="skx-chips">
              <li v-for="chip in suggestions.book" :key="chip">
                <button type="button" class="skx-chip" @click="handleChip(chip)">{{ chip }}</button>
              </li>
            </ul>
          </div>
          <!-- 추천 배너 -->
          <button type="button" class="skx-recommend" @click="navigateTo('/recommend')">
            <span class="skx-recommend__glow" aria-hidden="true"></span>
            <span class="skx-recommend__panel" aria-hidden="true"></span>
            <span class="skx-recommend__icon"><img src="/img/ico-search-lg.svg" alt=""></span>
            <span class="skx-recommend__label">내 상황에 맞는 도서 추천받기</span>
            <img class="skx-recommend__arrow" src="/img/ico-arrow.svg" alt="">
          </button>
        </div>

        <!-- 논문 패널 -->
        <div class="skx-panel" :hidden="mode !== 'paper'">
          <div class="skx-search">
            <div class="skx-search__box">
              <label class="skx-search__field">
                <span class="skx-sr-only">논문 검색어</span>
                <textarea
                  class="skx-search__input"
                  v-model="currentQuery"
                  placeholder="찾고싶은 논문을 문장으로 검색해보세요!"
                  :disabled="loading"
                  @keydown.enter.exact.prevent="handleSearch(currentQuery)"
                ></textarea>
              </label>
              <div class="skx-search__actions">
                <button type="button" class="skx-send" aria-label="검색" @click="handleSearch(currentQuery)">
                  <img src="/img/ico-send.svg" alt="">
                </button>
              </div>
            </div>
            <ul class="skx-chips">
              <li v-for="chip in suggestions.paper" :key="chip">
                <button type="button" class="skx-chip" @click="handleChip(chip)">{{ chip }}</button>
              </li>
            </ul>
            <!-- 논문 필터 드롭다운 -->
            <div class="skx-filters">
              <div :class="['skx-select', filterOpen && 'is-open']">
                <button type="button" class="skx-select__btn"
                  aria-haspopup="listbox" :aria-expanded="filterOpen"
                  @click.stop="filterOpen = !filterOpen">
                  <span class="skx-select__label">{{ selectedFilter || '자료유형' }}</span>
                  <img class="skx-select__arrow" src="/img/ico-arrow-down.svg" alt="">
                </button>
                <ul class="skx-select__menu" role="listbox">
                  <li v-for="opt in filterOptions" :key="opt">
                    <button type="button" class="skx-select__option"
                      :class="selectedFilter === opt && 'is-selected'"
                      role="option" @click="selectFilter(opt)">{{ opt }}</button>
                  </li>
                </ul>
              </div>
              <div class="skx-filter-chip__wrap">
                <span v-for="f in activeFilters" :key="f" class="skx-filter-chip">
                  {{ f }}
                  <button type="button" class="skx-filter-chip__x" aria-label="필터 삭제"
                    @click="removeFilter(f)">
                    <img src="/img/ico-delete.svg" alt="">
                  </button>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 신작도서 -->
        <section class="skx-newbooks">
          <h2 class="skx-newbooks__title">지금도 새로운 책이 업데이트 되고 있어요!</h2>
          <div class="skx-newbooks__row">
            <div class="skx-newbooks__count">
              <span class="skx-newbooks__label">신작도서</span>
              <span class="skx-newbooks__num">
                <span class="skx-newbooks__value">{{ newbooksCount.toLocaleString('ko-KR') }}</span>
                <span class="skx-newbooks__unit">권</span>
              </span>
            </div>
            <ul class="skx-newbooks__stack" aria-hidden="true">
              <li v-for="i in 6" :key="i" :class="['skx-book', i === 1 && 'is-loading']">
                <span class="skx-book__spine"><img class="skx-book__spinner" src="/img/ico-spinner.svg" alt=""></span>
                <span class="skx-book__bar"></span>
              </li>
            </ul>
          </div>
        </section>
      </div>
    </main>

    <!-- results view -->
    <main v-else-if="view === 'results'" class="skx-result">
      <!-- 검색바 -->
      <div class="skx-rsearch">
        <input type="text" class="skx-rsearch__input"
          v-model="currentQuery" aria-label="검색어 입력"
          @keydown.enter.prevent="handleSearch(currentQuery)">
        <button type="button" class="skx-send" aria-label="검색" @click="handleSearch(currentQuery)">
          <img src="/img/ico-send.svg" alt="">
        </button>
      </div>

      <!-- 로딩 -->
      <div v-if="loading" class="skx-result-card" style="padding:40px;text-align:center">
        <img src="/img/ico-spinner.svg" alt="" style="width:32px;animation:skxSpin 1s linear infinite">
        <p style="margin-top:12px">AI가 {{ mode === 'book' ? '도서' : '논문' }}를 검색 중입니다...</p>
      </div>

      <!-- 에러 -->
      <div v-else-if="searchError" class="skx-result-card" style="padding:20px;color:#c00">{{ searchError }}</div>

      <!-- 결과 카드 목록 -->
      <template v-else>
        <!-- AI 큐레이션 박스 (도서) -->
        <div v-if="mode === 'book' && books.length" class="skx-result-card skx-ai-header">
          <div class="skx-ai-header__inner" @click="curationOpen = !curationOpen">
            <img class="skx-ai-header__logo" src="/img/logo-mark.svg" alt="">
            <span class="skx-ai-header__title">AI가 원하시는 도서를 찾았어요!</span>
            <span v-if="curationLoading" style="font-size:12px;color:var(--skx-violet)">분석 중...</span>
            <button type="button" class="skx-ai-header__toggle">{{ curationOpen ? '접기' : '펼치기' }}</button>
          </div>
          <Transition name="skx-expand">
            <div v-if="curationOpen && curation" class="skx-ai-body">
              <p>{{ curation.intro }}</p>
              <ul>
                <li v-for="item in curation.items" :key="item.book_id">• {{ item.reason }}</li>
              </ul>
            </div>
          </Transition>
        </div>

        <!-- 논문 핵심 요약 -->
        <div v-if="mode === 'paper' && (paperSummaryText || paperSummaryLoading)" class="skx-result-card">
          <div class="skx-ai-header__inner">
            <img class="skx-ai-header__logo" src="/img/logo-mark.svg" alt="">
            <span class="skx-ai-header__title">AI 핵심 요약</span>
            <span v-if="paperSummaryLoading" style="color:var(--skx-violet)">●</span>
          </div>
          <div class="skx-ai-body" v-html="renderedPaperSummary" />
        </div>

        <!-- 결과 카드들 -->
        <div v-for="item in books" :key="item.book_id" class="skx-result-card" @click="openDetail(item)" style="cursor:pointer">
          <article class="skx-book-card">
            <div class="skx-book-card__thumb">
              <BookCover :book-id="item.book_id" />
            </div>
            <div class="skx-book-card__body">
              <div class="skx-book-card__top">
                <div class="skx-book-card__tags">
                  <span class="skx-tag skx-tag--score">정합성 {{ Math.round((item.best_score || 0) * 100) }}%</span>
                  <span v-for="tag in parseThemes(item.book_info?.themes)" :key="tag" class="skx-tag skx-tag--keyword">#{{ tag }}</span>
                </div>
                <button type="button" class="skx-book-card__bookmark"
                  :aria-label="bookmarkIcon(item.book_id).includes('on') ? '북마크 해제' : '북마크'"
                  @click.stop="toggleBookmark(item.book_id)">
                  <img :src="bookmarkIcon(item.book_id)" alt="">
                </button>
              </div>
              <div class="skx-book-card__meta">
                <div class="skx-book-card__title-row">
                  <h3 class="skx-book-card__title">{{ item.book_info?.title || item.book_id }}</h3>
                </div>
                <div class="skx-book-card__info-row">
                  <span v-if="item.book_info?.material_type" class="skx-meta-text">{{ item.book_info.material_type }}</span>
                  <span v-if="item.book_info?.personal_author || item.book_info?.corporate_author" class="skx-dot"></span>
                  <span class="skx-meta-text">{{ item.book_info?.personal_author || item.book_info?.corporate_author }}</span>
                  <span v-if="item.book_info?.pub_date" class="skx-dot"></span>
                  <span v-if="item.book_info?.pub_date" class="skx-meta-text">{{ item.book_info.pub_date.slice(0, 4) }}년</span>
                  <span v-if="item.book_info?.publisher" class="skx-dot"></span>
                  <span v-if="item.book_info?.publisher" class="skx-meta-text">{{ item.book_info.publisher }}</span>
                </div>
              </div>
              <div class="skx-book-card__actions" @click.stop>
                <button type="button" class="skx-btn-talk skx-btn-talk--book" @click="openDetail(item)">
                  <span class="skx-btn-talk__glow" aria-hidden="true"></span>
                  <span class="skx-btn-talk__panel" aria-hidden="true"></span>
                  <img class="skx-btn-talk__ico" src="/img/ico-chat.svg" alt="">
                  <span class="skx-btn-talk__label">이 {{ mode === 'paper' ? '논문과' : '책과' }} 대화하기</span>
                </button>
                <button type="button" class="skx-btn-loan" @click="requestLoan(item)">대출신청</button>
                <button type="button" class="skx-btn-read" @click="viewPdf(item)">원문 보기</button>
                <button v-if="mode === 'paper'" type="button" class="skx-btn-loan" @click="openCitation(item)">출처 인용</button>
              </div>
            </div>
          </article>
        </div>
      </template>
    </main>

    <!-- 논문 상세 (in-page, paper mode) -->
    <main v-else-if="view === 'detail' && selectedItem" class="skx-result">
      <!-- 논문 상세는 papers/[id].vue로 이동했으므로 여기서는 redirect -->
    </main>

    <!-- 출처 인용 모달 -->
    <CitationModal
      :open="citationModal"
      :book-id="citationBook?.book_id ?? null"
      :references="citationBook?.book_info?.references ?? []"
      @close="citationModal = false"
    />

    <!-- PDF 뷰어 -->
    <PdfViewer
      v-if="pdfOpen && selectedItem"
      :cnts-id="selectedItem.book_id"
      :title="selectedItem.book_info?.title"
      @close="pdfOpen = false"
    />

    <!-- 토스트 -->
    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>
```

- [ ] **Step 2: `<script setup>` 수정 — 신규 상태 추가**

기존 script 상단에 추가:

```typescript
// 탭 슬라이더
const tabsRef = ref<HTMLElement | null>(null)
const tabSliderStyle = ref({ width: '0px', transform: 'translateX(0px)' })

// 논문 필터 드롭다운
const filterOpen = ref(false)
const selectedFilter = ref('')
const activeFilters = ref<string[]>([])
const filterOptions = ['KCI 등재', 'KCI 미등재', 'KCI 후보']

// 신작도서 카운트업
const newbooksCount = ref(0)
const NEW_BOOKS_TARGET = 1245

// 북마크
const { toggleBookmark, bookmarkIcon } = useBookmark()

function setMode(m: 'book' | 'paper') {
  mode.value = m
  nextTick(() => updateTabSlider())
}

function updateTabSlider() {
  if (!tabsRef.value) return
  const active = tabsRef.value.querySelector('.skx-tab.is-active') as HTMLElement
  if (!active) return
  tabSliderStyle.value = {
    width: active.offsetWidth + 'px',
    transform: `translateX(${active.offsetLeft}px)`,
  }
}

function selectFilter(opt: string) {
  selectedFilter.value = opt
  filterOpen.value = false
  if (!activeFilters.value.includes(opt)) activeFilters.value.push(opt)
}

function removeFilter(f: string) {
  activeFilters.value = activeFilters.value.filter(x => x !== f)
  if (selectedFilter.value === f) selectedFilter.value = ''
}

// 바깥 클릭 시 드롭다운 닫기
function onDocClick() { filterOpen.value = false }
```

기존 `onMounted` 안에 추가:

```typescript
// 탭 슬라이더 초기 배치
nextTick(() => updateTabSlider())
window.addEventListener('resize', updateTabSlider)

// 신작도서 카운트업
const duration = 1600
const start = performance.now()
const tick = (now: number) => {
  const p = Math.min((now - start) / duration, 1)
  const eased = 1 - Math.pow(1 - p, 3)
  newbooksCount.value = Math.round(NEW_BOOKS_TARGET * eased)
  if (p < 1) requestAnimationFrame(tick)
  else newbooksCount.value = NEW_BOOKS_TARGET
}
requestAnimationFrame(tick)

document.addEventListener('click', onDocClick)
```

기존 `onUnmounted` (없으면 추가):

```typescript
onUnmounted(() => {
  window.removeEventListener('resize', updateTabSlider)
  document.removeEventListener('click', onDocClick)
})
```

기존 `openDetail` 함수에서 paper mode도 별도 페이지로 이동하도록 수정:

```typescript
function openDetail(item: BookChunkGroup) {
  // 도서, 논문 모두 별도 상세 페이지로 이동
  if (mode.value === 'book') {
    navigateTo(`/books/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}&score=${item.best_score || 0}`)
  } else {
    navigateTo(`/papers/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}&score=${item.best_score || 0}`)
  }
}
```

- [ ] **Step 3: scoped `<style>` 블록 전체 삭제** (style_skovix.css가 전역으로 처리)

- [ ] **Step 4: 커밋**

```bash
git add frontend/pages/index.vue
git commit -m "feat: apply publishing layout to index.vue (landing + results)"
```

---

## Task 5: books/[cnts_id].vue — skx-detail + 수직탭 + 채팅패널

**Files:**
- Modify: `frontend/pages/books/[cnts_id].vue`

퍼블리싱 `skovix-detail.html` 구조 적용. 추가 구현:
- `skx-vtabs` 수직탭: `detailTab` ref로 `is-active` 클래스 + 슬라이더 위치 관리
- `skx-chat-panel`: 우측에서 슬라이드인하는 채팅 패널 (기존 인라인 BookChat 대신)
- 대출신청 모달(`skx-modal-backdrop`)
- 북마크 토글

- [ ] **Step 1: 수직탭 관련 script 추가**

기존 script에 추가:

```typescript
// 수직 탭
const vtabsRef = ref<HTMLElement | null>(null)
const vtabSliderStyle = ref({ height: '0px', transform: 'translateY(0px)' })

function updateVtabSlider() {
  if (!vtabsRef.value) return
  const active = vtabsRef.value.querySelector('.skx-vtab.is-active') as HTMLElement
  if (!active) return
  vtabSliderStyle.value = {
    height: active.offsetHeight + 'px',
    transform: `translateY(${active.offsetTop}px)`,
  }
}

function switchVtab(key: string) {
  detailTab.value = key
  nextTick(() => updateVtabSlider())
  if (key === 'reason' && !reasonText.value && book.value) {
    // fetchReason 호출 (기존 로직 유지)
  }
}

// 채팅패널
const chatPanelOpen = ref(false)

// 대출 모달
const loanModalOpen = ref(false)
const loanCancelModalOpen = ref(false)
const isLoaning = ref(false)

function confirmLoan() {
  loanModalOpen.value = false
  isLoaning.value = true
}

function cancelLoan() {
  loanCancelModalOpen.value = false
  isLoaning.value = false
}

// 북마크
const { toggleBookmark, bookmarkIcon, isBookmarked } = useBookmark()
```

`onMounted`에 추가:

```typescript
nextTick(() => updateVtabSlider())
```

- [ ] **Step 2: `<template>` 교체**

```vue
<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="skx-result">
      <!-- 로딩 -->
      <div v-if="pageLoading" class="skx-result-card" style="padding:40px;text-align:center">
        <img src="/img/ico-spinner.svg" alt="" style="width:32px">
        <p style="margin-top:12px">도서 정보를 불러오는 중...</p>
      </div>
      <div v-else-if="pageError" class="skx-result-card" style="padding:20px">
        <p style="color:#c00">{{ pageError }}</p>
        <button class="skx-btn-loan" style="margin-top:12px" @click="navigateTo('/')">홈으로</button>
      </div>

      <template v-else-if="book">
        <div class="skx-result-card">
          <!-- 뒤로가기 -->
          <button type="button" class="skx-detail-back" @click="$router.back()">
            <img class="skx-detail-back__icon" src="/img/ico-arrow.svg" alt="">
            <span class="skx-detail-back__label">검색 목록 돌아가기</span>
          </button>

          <!-- 도서 헤더 -->
          <article class="skx-book-card skx-book-card--hd">
            <div class="skx-book-card__thumb">
              <BookCover :book-id="cnts_id" size="large" />
            </div>
            <div class="skx-book-card__body">
              <div class="skx-book-card__top">
                <div class="skx-book-card__tags">
                  <span v-if="matchScore" class="skx-tag skx-tag--score">정합성 {{ matchScore }}%</span>
                  <span v-for="tag in themes" :key="tag" class="skx-tag skx-tag--keyword">#{{ tag }}</span>
                </div>
                <button type="button" class="skx-book-card__bookmark"
                  :aria-label="isBookmarked(cnts_id) ? '북마크 해제' : '북마크'"
                  @click="toggleBookmark(cnts_id)">
                  <img :src="bookmarkIcon(cnts_id)" alt="">
                </button>
              </div>
              <div class="skx-book-card__meta">
                <div class="skx-book-card__title-row">
                  <h2 class="skx-book-card__title">{{ book.title }}</h2>
                  <span class="skx-avail skx-avail--ok">
                    <span class="skx-avail__dot"></span>
                    <span class="skx-avail__label">대출 가능</span>
                  </span>
                </div>
                <div class="skx-book-card__info-row">
                  <span v-if="book.material_type" class="skx-meta-text">{{ book.material_type }}</span>
                  <template v-if="book.personal_author || book.corporate_author">
                    <span class="skx-dot"></span>
                    <span class="skx-meta-text">{{ book.personal_author || book.corporate_author }}</span>
                    <span class="skx-meta-role">&nbsp;저자(글)</span>
                  </template>
                  <template v-if="book.pub_date">
                    <span class="skx-dot"></span>
                    <span class="skx-meta-text">{{ book.pub_date.slice(0, 4) }}년</span>
                  </template>
                  <template v-if="book.publisher">
                    <span class="skx-dot"></span>
                    <span class="skx-meta-text">{{ book.publisher }}</span>
                  </template>
                </div>
              </div>
              <div class="skx-book-card__actions">
                <button type="button" :class="['skx-btn-talk skx-btn-talk--book', chatPanelOpen && 'is-active']"
                  @click="chatPanelOpen = !chatPanelOpen">
                  <span class="skx-btn-talk__glow" aria-hidden="true"></span>
                  <span class="skx-btn-talk__panel" aria-hidden="true"></span>
                  <img class="skx-btn-talk__ico" src="/img/ico-chat.svg" alt="">
                  <span class="skx-btn-talk__label">이 책과 대화하기</span>
                </button>
                <button type="button" :class="['skx-btn-loan', isLoaning && 'is-loaning']"
                  @click="isLoaning ? loanCancelModalOpen = true : loanModalOpen = true">
                  {{ isLoaning ? '대출신청중' : '대출신청' }}
                </button>
                <button type="button" class="skx-btn-read" @click="viewPdf">원문 보기</button>
              </div>
            </div>
          </article>

          <!-- AI 큐레이션 (수직 탭) -->
          <section class="skx-curation" aria-label="AI 큐레이션">
            <h2 class="skx-section-title">AI 큐레이션</h2>
            <div class="skx-curation-panel">
              <div class="skx-vtabs-col">
                <div class="skx-vtabs" role="tablist" ref="vtabsRef">
                  <span class="skx-vtabs__slider" :style="vtabSliderStyle" aria-hidden="true"></span>
                  <button v-for="tab in detailTabs" :key="tab.key"
                    type="button"
                    :class="['skx-vtab', detailTab === tab.key && 'is-active']"
                    role="tab"
                    :aria-selected="detailTab === tab.key"
                    :aria-controls="'vp-' + tab.key"
                    @click="switchVtab(tab.key)">{{ tab.label }}</button>
                </div>
              </div>
              <div class="skx-curation-content">
                <div class="skx-curation-card">
                  <template v-for="tab in detailTabs" :key="tab.key">
                    <div v-if="detailTab === tab.key" :id="'vp-' + tab.key" role="tabpanel">
                      <div v-if="tab.key === 'reason'">
                        <p v-if="reasonLoading" class="skx-curation-text">추천 이유 생성 중...</p>
                        <div v-else-if="reasonText" class="skx-curation-text" v-html="renderedReason" />
                        <p v-else class="skx-curation-text">추천 이유 정보가 없습니다.</p>
                      </div>
                      <p v-else-if="tab.key === 'plot'" class="skx-curation-text">{{ book.plot || '줄거리 정보가 없습니다.' }}</p>
                      <p v-else-if="tab.key === 'intro'" class="skx-curation-text">{{ book.introduction || '소개 정보가 없습니다.' }}</p>
                      <p v-else-if="tab.key === 'effect'" class="skx-curation-text">{{ book.read_effect || '정보가 없습니다.' }}</p>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </section>

          <!-- 상세 정보 -->
          <section class="skx-detail-info" aria-label="상세 정보">
            <h2 class="skx-section-title">상세 정보</h2>
            <div class="skx-detail-info__grid">
              <div class="skx-info-row"><span class="skx-info-label">표제/저자사항</span><span class="skx-info-value">{{ book.title_responsibility || book.title || '-' }}</span></div>
              <div class="skx-info-row"><span class="skx-info-label">발행사항</span><span class="skx-info-value">{{ [book.pub_place, book.publisher, book.pub_date].filter(Boolean).join(', ') || '-' }}</span></div>
              <div class="skx-info-row"><span class="skx-info-label">형태사항</span><span class="skx-info-value">{{ book.extent || '-' }}</span></div>
              <div class="skx-info-row"><span class="skx-info-label">총서사항</span><span class="skx-info-value">{{ book.series_title || '-' }}</span></div>
              <div class="skx-info-row"><span class="skx-info-label">표준번호</span><span class="skx-info-value">{{ book.isbn || book.uci || '-' }}</span></div>
              <div class="skx-info-row"><span class="skx-info-label">분류기호</span><span class="skx-info-value">{{ [book.kdc, book.ddc].filter(Boolean).join(' → ') || '-' }}</span></div>
              <div class="skx-info-row"><span class="skx-info-label">주제명</span><span class="skx-info-value">{{ book.subject || book.keyword || '-' }}</span></div>
              <div class="skx-info-row"><span class="skx-info-label">언어</span><span class="skx-info-value">{{ book.language || 'Korean' }}</span></div>
            </div>
          </section>

          <!-- AI 연관 도서 추천 -->
          <section class="skx-reco" aria-label="AI 연관 도서 추천">
            <h2 class="skx-section-title">AI 연관 도서 추천</h2>
            <div class="skx-reco-panel">
              <div class="skx-reco-list" role="list">
                <div v-if="relatedLoading" style="padding:16px;color:#bbb;font-size:12px">불러오는 중...</div>
                <div v-else-if="!relatedItems.length" style="padding:16px;color:#bbb;font-size:12px">연관 추천 항목이 없습니다.</div>
                <button v-for="rel in relatedItems" :key="rel.book_id"
                  type="button"
                  :class="['skx-reco-item', selectedRelated?.book_id === rel.book_id && 'is-active']"
                  role="listitem"
                  @click="selectedRelated = rel">
                  <img class="skx-reco-item__thumb" src="/img/ico-book-thumb.svg" alt="">
                  <div class="skx-reco-item__inner">
                    <span class="skx-reco-item__name">{{ rel.book_info?.title || rel.book_id }}</span>
                    <span class="skx-reco-item__score">정합성 {{ Math.round((rel.score || 0) * 100) }}%</span>
                  </div>
                </button>
              </div>

              <!-- 선택 전: 빈 상태 -->
              <div v-if="!selectedRelated" class="skx-reco-empty">
                <img class="skx-reco-empty__logo" src="/img/logo-mark.svg" alt="SKOVIX">
                <p class="skx-reco-empty__text">추천도서를 클릭해주세요</p>
              </div>

              <!-- 선택 후: 상세 -->
              <div v-else class="skx-reco-detail">
                <div class="skx-reco-cover">
                  <BookCover :book-id="selectedRelated.book_id" />
                </div>
                <div class="skx-reco-info">
                  <div class="skx-reco-meta">
                    <h3 class="skx-reco-title">{{ selectedRelated.book_info?.title }}</h3>
                    <div class="skx-reco-author">
                      <span class="skx-meta-text">{{ selectedRelated.book_info?.personal_author || selectedRelated.book_info?.corporate_author }}</span>
                    </div>
                  </div>
                  <button class="skx-btn-loan" style="margin-top:12px"
                    @click="navigateTo(`/books/${selectedRelated.book_id}`)">상세 보기</button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </template>
    </main>

    <!-- 채팅 패널 -->
    <aside :class="['skx-chat-panel', chatPanelOpen && 'is-open']">
      <div class="skx-chat-panel__inner" v-if="book">
        <div class="skx-chat-header">
          <button type="button" class="skx-chat-close" aria-label="채팅 닫기" @click="chatPanelOpen = false">
            <img src="/img/ico-arrow.svg" alt="" class="skx-chat-close__ico">
          </button>
          <h2 class="skx-chat-title">이 책과 대화하기</h2>
        </div>
        <BookChat :cnts-id="cnts_id" @close="chatPanelOpen = false" />
      </div>
    </aside>

    <!-- 대출 신청 완료 모달 -->
    <div v-if="loanModalOpen" class="skx-modal-backdrop"
      role="dialog" aria-modal="true"
      @click.self="loanModalOpen = false">
      <div class="skx-modal">
        <div class="skx-modal__head">
          <p class="skx-modal__title">대출 신청 완료</p>
          <p class="skx-modal__sub">해당 도서 대출 신청이 완료되었습니다!</p>
        </div>
        <div class="skx-modal__book">
          <p class="skx-modal__book-title">{{ book?.title }}</p>
        </div>
        <div class="skx-modal__actions">
          <button type="button" class="skx-modal__btn-cancel" @click="loanModalOpen = false">취소</button>
          <button type="button" class="skx-modal__btn-confirm" @click="confirmLoan">확인</button>
        </div>
      </div>
    </div>

    <!-- 대출 신청 취소 모달 -->
    <div v-if="loanCancelModalOpen" class="skx-modal-backdrop"
      role="dialog" aria-modal="true"
      @click.self="loanCancelModalOpen = false">
      <div class="skx-modal">
        <div class="skx-modal__head">
          <p class="skx-modal__title">대출 신청 취소</p>
          <p class="skx-modal__sub">도서 대출 신청이 취소되었습니다</p>
        </div>
        <div class="skx-modal__actions">
          <button type="button" class="skx-modal__btn-confirm" @click="cancelLoan">확인</button>
        </div>
      </div>
    </div>

    <!-- 토스트 -->
    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>
```

- [ ] **Step 3: scoped `<style>` 블록 전체 삭제**

- [ ] **Step 4: 커밋**

```bash
git add frontend/pages/books/[cnts_id].vue
git commit -m "feat: apply publishing layout to book detail page with vtabs and chat panel"
```

---

## Task 6: papers.vue — skx-paper-result 구조 교체

**Files:**
- Modify: `frontend/pages/papers.vue`

퍼블리싱 `skovix-paper-result.html` 구조 적용. 기존 필터/정렬/페이지네이션 Vue 로직 유지.

- [ ] **Step 1: `<template>` 교체**

```vue
<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <!-- landing -->
    <main v-if="!hasResults" class="skx-contents">
      <div class="skx-contents__inner">
        <h1 class="skx-hero">논문 의미 기반 검색</h1>
        <!-- 탭: 도서 / 논문 -->
        <div class="skx-tabs" role="tablist" ref="tabsRef">
          <span class="skx-tabs__slider" :style="tabSliderStyle"></span>
          <button type="button" class="skx-tab skx-tab--book" role="tab" @click="navigateTo('/')">
            <img class="skx-tab__icon" src="/img/ico-tab-book-off.svg" alt="">
            <span class="skx-tab__label">도서검색</span>
          </button>
          <button type="button" class="skx-tab skx-tab--paper is-active" role="tab" aria-selected="true">
            <img class="skx-tab__icon" src="/img/ico-tab-paper-on.svg" alt="">
            <span class="skx-tab__label">논문검색</span>
          </button>
        </div>
        <div class="skx-search">
          <div class="skx-search__box">
            <label class="skx-search__field">
              <span class="skx-sr-only">논문 검색어</span>
              <textarea class="skx-search__input"
                v-model="currentQuery"
                placeholder="탐구하고 싶은 논문을 자연어로 검색해보세요"
                :disabled="loading"
                @keydown.enter.exact.prevent="handleSearch(currentQuery)"></textarea>
            </label>
            <div class="skx-search__actions">
              <button type="button" class="skx-send" @click="handleSearch(currentQuery)">
                <img src="/img/ico-send.svg" alt="">
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- results -->
    <main v-else class="skx-result">
      <!-- 검색바 -->
      <div class="skx-rsearch">
        <input type="text" class="skx-rsearch__input"
          v-model="currentQuery"
          @keydown.enter.prevent="handleSearch(currentQuery)">
        <button type="button" class="skx-send" @click="handleSearch(currentQuery)">
          <img src="/img/ico-send.svg" alt="">
        </button>
      </div>

      <div class="skx-result-card">
        <!-- 로딩 -->
        <div v-if="loading" style="padding:40px;text-align:center">
          <img src="/img/ico-spinner.svg" alt="" style="width:32px">
          <p style="margin-top:12px">논문을 탐색하고 있습니다...</p>
        </div>

        <!-- 에러 -->
        <div v-else-if="error" style="padding:20px;color:#c00">{{ error }}</div>

        <template v-else>
          <!-- 툴바: 건수 + 정렬 -->
          <div class="skx-result-toolbar">
            <span class="skx-result-count">
              <strong>{{ filteredPapers.length.toLocaleString() }}</strong>편 검색됨
            </span>
            <div class="skx-sort" ref="sortRef">
              <button type="button" class="skx-sort__btn" @click="sortMenuOpen = !sortMenuOpen">
                <img src="/img/ico-sort-off.svg" alt="">
                {{ SORT_LABELS[sortBy] }}
              </button>
              <ul v-if="sortMenuOpen" class="skx-sort__menu">
                <li v-for="(label, key) in SORT_LABELS" :key="key">
                  <button type="button" :class="sortBy === key && 'is-on'"
                    @click="sortBy = key; sortMenuOpen = false">{{ label }}</button>
                </li>
              </ul>
            </div>
          </div>

          <!-- 결과 없음 -->
          <div v-if="!filteredPapers.length" style="padding:60px;text-align:center;color:#bbb">
            검색 결과가 없습니다.
          </div>

          <!-- 논문 카드 목록 -->
          <div v-else class="skx-paper-list">
            <div v-for="paper in pagedPapers" :key="paper.book_id" class="skx-paper-item">
              <article class="skx-paper-card"
                @click="navigateTo(`/papers/${paper.book_id}?q=${encodeURIComponent(currentQuery)}`)">
                <div class="skx-paper-card__main">
                  <div class="skx-paper-card__pills">
                    <span v-if="paper.book_info?.genre" class="skx-ptag skx-ptag--kci">
                      {{ GENRE_LABELS[paper.book_info.genre] || paper.book_info.genre }}
                    </span>
                  </div>
                  <h3 class="skx-paper-card__title">{{ paper.book_info?.title || paper.book_id }}</h3>
                  <p v-if="paper.book_info?.title_remainder" class="skx-paper-card__title-en">
                    {{ paper.book_info.title_remainder }}
                  </p>
                  <div class="skx-paper-card__meta">
                    <span v-if="paper.book_info?.personal_author" class="skx-meta-text">
                      {{ paper.book_info.personal_author }}
                    </span>
                    <span v-if="paper.book_info?.publisher" class="skx-dot"></span>
                    <span v-if="paper.book_info?.publisher" class="skx-meta-text">
                      {{ paper.book_info.publisher }}
                    </span>
                    <span v-if="paper.book_info?.pub_date" class="skx-dot"></span>
                    <span v-if="paper.book_info?.pub_date" class="skx-meta-text">
                      {{ paper.book_info.pub_date }}
                    </span>
                  </div>
                  <p v-if="paper.book_info?.abstract" class="skx-paper-card__abstract">
                    {{ paper.book_info.abstract }}
                  </p>
                  <div class="skx-paper-card__actions" @click.stop>
                    <button type="button" class="skx-btn-talk skx-btn-talk--paper"
                      @click="navigateTo(`/papers/${paper.book_id}?q=${encodeURIComponent(currentQuery)}`)">
                      <span class="skx-btn-talk__glow" aria-hidden="true"></span>
                      <span class="skx-btn-talk__panel" aria-hidden="true"></span>
                      <img class="skx-btn-talk__ico" src="/img/ico-chat.svg" alt="">
                      <span class="skx-btn-talk__label">대화하기</span>
                    </button>
                    <a v-if="paper.book_info?.url" :href="paper.book_info.url" target="_blank"
                      class="skx-btn-read" @click.stop>원문 보기</a>
                  </div>
                </div>
                <div class="skx-paper-card__side">
                  <div class="skx-paper-card__score">
                    {{ Math.round(paper.best_score * 100) }}<span>%</span>
                  </div>
                  <div class="skx-paper-card__score-lbl">적합도</div>
                </div>
              </article>
            </div>
          </div>

          <!-- 페이지네이션 -->
          <div class="skx-pager">
            <div class="skx-pager__info">
              {{ (currentPage - 1) * PAGE_SIZE + 1 }}–{{ Math.min(currentPage * PAGE_SIZE, filteredPapers.length) }}
              / {{ filteredPapers.length.toLocaleString() }}편
            </div>
            <div class="skx-pager__nav">
              <button class="skx-page-btn" :disabled="currentPage === 1" @click="currentPage--">
                <img src="/img/ico-page-prev.svg" alt="이전">
              </button>
              <template v-for="p in pageButtons" :key="p">
                <span v-if="p === '...'" class="skx-page-ellipsis">…</span>
                <button v-else class="skx-page-btn" :class="p === currentPage && 'is-on'"
                  @click="currentPage = p as number">{{ p }}</button>
              </template>
              <button class="skx-page-btn" :disabled="currentPage === totalPages" @click="currentPage++">
                <img src="/img/ico-page-next.svg" alt="다음">
              </button>
            </div>
          </div>
        </template>
      </div>
    </main>

    <!-- 토스트 -->
    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>
```

`<script setup>` 상단에 추가:

```typescript
const toast = ref('')
const tabsRef = ref<HTMLElement | null>(null)
const tabSliderStyle = ref({ width: '0px', transform: 'translateX(0px)' })

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}
```

- [ ] **Step 2: scoped `<style>` 블록 전체 삭제**

- [ ] **Step 3: 커밋**

```bash
git add frontend/pages/papers.vue
git commit -m "feat: apply publishing layout to papers.vue"
```

---

## Task 7: papers/[id].vue — 논문 상세 신규 페이지

**Files:**
- Create: `frontend/pages/papers/[id].vue`

퍼블리싱 `skovix-paper-detail.html` 기반. 수직탭(AI분석/초록) + 아코디언(키워드/참고문헌) 구현.

- [ ] **Step 1: 파일 생성**

`frontend/pages/papers/[id].vue`:

```vue
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

        <!-- 로딩 -->
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
                  <button type="button" class="skx-btn-icon-sm" aria-label="공유">
                    <img src="/img/ico-detail-share.svg" alt="">
                  </button>
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
                <div v-if="paper.book_info?.vol_issue" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">수록면</span>
                  <span class="skx-pdetail__row-val">{{ paper.book_info.vol_issue }}</span>
                </div>
                <div v-if="paper.book_info?.kci_citations != null" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">인용수</span>
                  <span class="skx-pdetail__row-val">{{ paper.book_info.kci_citations }}</span>
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
                <button type="button" class="skx-btn-pview-sm">원문 보기</button>
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
                  <div v-if="curationTab === 'ai-summary'" id="vp-ai-summary" role="tabpanel">
                    <p v-if="summaryLoading" class="skx-curation-text">AI가 핵심을 분석 중입니다...</p>
                    <div v-else-if="summaryText" class="skx-curation-text" v-html="renderedSummary" />
                    <p v-else class="skx-curation-text">AI 분석 정보가 없습니다.</p>
                  </div>
                  <p v-else-if="curationTab === 'abstract'" id="vp-abstract" role="tabpanel"
                    class="skx-curation-text">
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

    <!-- 토스트 -->
    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from 'marked'
import type { BookChunkGroup } from '~/types/search'

const route = useRoute()
const config = useRuntimeConfig()
const paperId = route.params.id as string
const matchScore = computed(() => {
  const s = route.query.score
  return s ? Math.round(Number(s) * 100) : null
})

const paper = ref<BookChunkGroup | null>(null)
const loading = ref(false)

const GENRE_LABELS: Record<string, string> = {
  paper: '학술논문', thesis: '학위논문', report: '연구보고서',
  manual: '매뉴얼', book: '단행본', other: '기타',
}

// 수직탭
const vtabsRef = ref<HTMLElement | null>(null)
const vtabSliderStyle = ref({ height: '0px', transform: 'translateY(0px)' })
const curationTab = ref('ai-summary')
const curationTabs = [
  { key: 'ai-summary', label: 'AI가 분석한 연구 핵심' },
  { key: 'abstract', label: '초록' },
]

function updateVtabSlider() {
  if (!vtabsRef.value) return
  const active = vtabsRef.value.querySelector('.skx-vtab.is-active') as HTMLElement
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

// 아코디언
const keywordOpen = ref(false)
const refsOpen = ref(false)

const keywords = computed(() => {
  const kw = paper.value?.book_info?.keyword || ''
  return kw ? kw.split(',').map((k: string) => k.trim()).filter(Boolean) : []
})

// AI 핵심 요약
const summaryText = ref('')
const summaryLoading = ref(false)
const renderedSummary = computed(() =>
  summaryText.value ? (marked.parse(summaryText.value) as string) : ''
)

// 연관 추천
const relatedItems = ref<any[]>([])
const relatedLoading = ref(false)
const selectedRelated = ref<any>(null)

// 채팅 / 모달
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
    const data = await $fetch<any>(`${config.public.apiBase}/papers/${paperId}`)
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
    const data = await $fetch<any>(`${config.public.apiBase}/papers/${paperId}/related`)
    relatedItems.value = data?.results || []
  } catch { /* 연관 없음 */ }
  finally { relatedLoading.value = false }
}

onMounted(async () => {
  await fetchPaper()
  await fetchRelated()
  nextTick(() => updateVtabSlider())
})
</script>
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/pages/papers/[id].vue
git commit -m "feat: add paper detail page with vtabs and accordion"
```

---

## Task 8: recommend.vue — 도서 추천 신규 페이지

**Files:**
- Create: `frontend/pages/recommend.vue`

- [ ] **Step 1: 파일 생성**

`frontend/pages/recommend.vue`:

```vue
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
            <li v-for="item in scenarios" :key="item.id" :class="['skx-recommend-item', item.cls]">
              <NuxtLink :to="`/recommend/${item.id}`" class="skx-recommend-item__inn skx-recommend__hover">
                <template v-if="item.deco === 'mt'">
                  <span class="skx-mt-deco skx-mt-deco--1" aria-hidden="true"><i></i></span>
                  <span class="skx-mt-deco skx-mt-deco--2" aria-hidden="true"><i></i></span>
                  <span class="skx-mt-deco skx-mt-deco--3" aria-hidden="true"><i></i></span>
                </template>
                <template v-else-if="item.deco === 'star'">
                  <img class="skx-reco-c03 skx-reco-c03--star-s" src="/img/skx-reco-c03-star.svg" alt="" aria-hidden="true">
                  <img class="skx-reco-c03 skx-reco-c03--star-l" src="/img/skx-reco-c03-star.svg" alt="" aria-hidden="true">
                  <img class="skx-reco-c03 skx-reco-c03--curve" src="/img/skx-reco-c03-curve.svg" alt="" aria-hidden="true">
                </template>
                <span class="skx-recommend-item__txt" v-html="item.label"></span>
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

const scenarios = [
  { id: '01', cls: 'item-01', deco: '', label: '위로가 <br>필요할 때' },
  { id: '02', cls: 'item-02', deco: 'mt', label: '심리적 단단함이 <br>필요할 때' },
  { id: '03', cls: 'item-03', deco: 'star', label: '늦은 밤, <br>잠이 오지 않을 때' },
  { id: '04', cls: 'item-04', deco: '', label: '흥미진진한 역사 이야기가 <br>궁금할 때' },
]
</script>
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/pages/recommend.vue
git commit -m "feat: add recommend page"
```

---

## Task 9: recommend/[id].vue — 도서 추천 상세 신규 페이지

**Files:**
- Create: `frontend/pages/recommend/[id].vue`

퍼블리싱 `skovix-recommend-detail.html` 기반. 구현:
- AI 타이핑 애니메이션 (글자 단위 append)
- 펼치기/접기 (overflow hidden 영역)
- 도서 선택 → 맞춤도서 추천 팝업 모달

- [ ] **Step 1: 파일 생성**

`frontend/pages/recommend/[id].vue`:

```vue
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
          <img class="skx-detail-back__icon" src="/img/ico-arrow.svg" alt="">
          <span class="skx-detail-back__label">돌아가기</span>
        </button>

        <!-- 히어로 배너 -->
        <div :class="['skx-rcd-hero', `skx-rcd-hero--${scenario.heroType}`]">
          <template v-if="scenario.heroType === '02'">
            <span class="skx-mt-deco skx-mt-deco--1" aria-hidden="true"><i></i></span>
            <span class="skx-mt-deco skx-mt-deco--2" aria-hidden="true"><i></i></span>
            <span class="skx-mt-deco skx-mt-deco--3" aria-hidden="true"><i></i></span>
          </template>
          <template v-if="scenario.heroType === '03'">
            <img class="skx-reco-c03 skx-reco-c03--star-s" src="/img/skx-reco-c03-star.svg" alt="" aria-hidden="true">
            <img class="skx-reco-c03 skx-reco-c03--star-l" src="/img/skx-reco-c03-star.svg" alt="" aria-hidden="true">
            <img class="skx-reco-c03 skx-reco-c03--curve" src="/img/skx-reco-c03-curve.svg" alt="" aria-hidden="true">
          </template>
          <div class="skx-rcd-hero__body">
            <h2 class="skx-rcd-hero__tit" v-html="scenario.title"></h2>
            <p class="skx-rcd-hero__sub">{{ scenario.sub }}</p>
          </div>
        </div>

        <!-- AI 텍스트 -->
        <div class="skx-rcd-ai">
          <div class="skx-rcd-ai__top">
            <img class="skx-rcd-ai__logo" src="/img/logo-mark.svg" alt="SKOVIX AI">
            <span class="skx-rcd-ai__label">{{ scenario.aiLabel }}</span>
          </div>
          <div :class="['skx-ai-answer-wrap', aiExpanded && 'is-expanded']" ref="aiWrapRef">
            <div class="skx-ai-answer">
              <p class="skx-ai-answer__text">{{ typedLine1 }}</p>
              <p class="skx-ai-answer__text">{{ typedLine2 }}</p>
            </div>
            <button v-if="showExpandBtn" type="button" class="skx-ai-expand-bar"
              :aria-expanded="aiExpanded"
              @click="toggleAiExpand">
              <span class="skx-ai-expand-bar__label">{{ aiExpanded ? '접기' : '펼치기' }}</span>
              <img class="skx-ai-expand-bar__arrow" src="/img/ico-arrow.svg" alt="" aria-hidden="true"
                :style="aiExpanded ? 'transform:rotate(180deg)' : ''">
            </button>
          </div>
        </div>

        <!-- 도서 선택 -->
        <div class="skx-rcd-select">
          <h3 class="skx-rcd-select__tit">가장 나에게 도움이되는 책을 선택해주세요.</h3>
          <div class="skx-rcd-book-grid">
            <button v-for="(book, i) in scenario.books" :key="i"
              type="button"
              :class="['skx-rcd-book-card', `skx-rcd-book-card--${i + 1}`]"
              @click="openModal(book)">
              <div class="skx-rcd-book-card__head">
                <img class="skx-rcd-book-card__icon" src="/img/ico-book-select.svg" alt="">
                <p class="skx-rcd-book-card__desc" v-html="book.desc"></p>
              </div>
              <div class="skx-rcd-book-card__cover">
                <img :src="book.cover" :alt="book.name + ' 표지'">
              </div>
              <p class="skx-rcd-book-card__name">{{ book.name }}</p>
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
        <h2 class="skx-rcd-modal__title">맞춤도서 추천</h2>
        <div class="skx-rcd-modal__card">
          <div class="skx-rcd-modal__card-top">
            <span class="skx-rcd-modal__badge">Book solution</span>
            <p class="skx-rcd-modal__desc" v-html="selectedBook?.desc"></p>
          </div>
          <div class="skx-rcd-modal__cover">
            <img :src="selectedBook?.cover" :alt="selectedBook?.name + ' 표지'">
          </div>
          <div class="skx-rcd-modal__book-info">
            <p class="skx-rcd-modal__book-title">{{ selectedBook?.name }}</p>
          </div>
        </div>
        <div class="skx-rcd-modal__btns">
          <button type="button" class="skx-rcd-modal__btn skx-rcd-modal__btn--outline">
            <img src="/img/ico-share.svg" alt="">솔루션 보내기
          </button>
          <button type="button" class="skx-rcd-modal__btn skx-rcd-modal__btn--dark">
            <img src="/img/ico-download.svg" alt="">솔루션 저장하기
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
const scenarioId = route.params.id as string

const toast = ref('')
function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

// 시나리오 데이터 (퍼블리싱 기준, 추후 API 연동)
const SCENARIOS: Record<string, any> = {
  '01': {
    heroType: '01', title: '위로가 필요할 때',
    sub: '지친 마음에 따뜻한 위로가 필요하다면 이 책들을 펼쳐보세요!',
    aiLabel: '위로가 필요한 당신을 위해 AI가 추천하는 책!',
    aiLines: ['위로가 필요한 당신을 위한 책들입니다.', '마음의 상처를 치유해 줄 따뜻한 이야기들을 골랐습니다.'],
    books: [
      { name: '강아지똥', desc: '보잘것없는 존재도<br>소중한 가치가 있음을', cover: '/img/img-book-01.jpg' },
      { name: '알사탕', desc: '자신의 마음을<br>경청하는 법', cover: '/img/img-book-alsatang.jpg' },
      { name: '구름빵', desc: '상상력과 따뜻함이<br>가득한 이야기', cover: '/img/img-book-02.jpg' },
      { name: '솔이의 추석 이야기', desc: '가족과 함께하는<br>따뜻한 명절', cover: '/img/img-book-01.jpg' },
    ],
  },
  '02': {
    heroType: '02', title: '심리적 단단함이 필요할 때',
    sub: '마음 근육을 키워 단단해지고 싶다면 이 책들을 읽어보세요!',
    aiLabel: '심리적 단단함을 만들 수 있게 AI가 추천하는 책!',
    aiLines: [
      '심리적 단단함을 만들 수 있게 AI가 추천하는 책!',
      '추천 도서들은 고난과 역경 속에서도 흔들리지 않는 내면의 중심을 잡았던 이들의 지혜가 담겨 있어, 무너진 기강을 세우고 삶의 맷집을 키워주는 도서들입니다.',
    ],
    books: [
      { name: '다산 정약용 산문집', desc: '유배지의 절망 속에서 피려낸<br>명철한 통찰로, 내면의 기강 바로잡기', cover: '/img/rcd-book-01.png' },
      { name: '너는 가능성이다', desc: '인간 본연의 숭고한 가치와 가능성을<br>깨워 주어, 무기력증 깨부수기', cover: '/img/rcd-book-02.png' },
      { name: '혼자 일어설 때 햇살은 더욱 눈부시다', desc: '홀로서기의 당당함과 회복탄력성을<br>전해주며 용기를 주는 책', cover: '/img/rcd-book-03.png' },
      { name: '방황하는 내국인', desc: '유배지의 절망 속에서 피려낸<br>명철한 통찰로, 내면의 기강 바로잡기', cover: '/img/rcd-book-04.png' },
    ],
  },
  '03': {
    heroType: '03', title: '늦은 밤, 잠이 오지 않을 때',
    sub: '잠 못 드는 밤, 마음을 가라앉혀 줄 책들을 골라봤어요!',
    aiLabel: '잠 못 드는 밤을 위해 AI가 추천하는 책!',
    aiLines: ['잠 못 드는 밤을 위한 책들입니다.', '마음을 차분히 가라앉혀 줄 이야기들을 골랐습니다.'],
    books: [
      { name: '강아지똥', desc: '보잘것없는 존재도<br>소중한 가치가 있음을', cover: '/img/img-book-01.jpg' },
      { name: '알사탕', desc: '자신의 마음을<br>경청하는 법', cover: '/img/img-book-alsatang.jpg' },
      { name: '구름빵', desc: '상상력과 따뜻함이<br>가득한 이야기', cover: '/img/img-book-02.jpg' },
      { name: '솔이의 추석 이야기', desc: '가족과 함께하는<br>따뜻한 명절', cover: '/img/img-book-01.jpg' },
    ],
  },
  '04': {
    heroType: '04', title: '흥미진진한 역사 이야기가 궁금할 때',
    sub: '흥미진진한 역사의 세계로 빠져들 책들을 추천해드려요!',
    aiLabel: '역사가 궁금한 당신을 위해 AI가 추천하는 책!',
    aiLines: ['역사에 대한 흥미를 키워줄 책들입니다.', '생생한 역사 이야기를 담은 도서들을 선별했습니다.'],
    books: [
      { name: '강아지똥', desc: '보잘것없는 존재도<br>소중한 가치가 있음을', cover: '/img/img-book-01.jpg' },
      { name: '알사탕', desc: '자신의 마음을<br>경청하는 법', cover: '/img/img-book-alsatang.jpg' },
      { name: '구름빵', desc: '상상력과 따뜻함이<br>가득한 이야기', cover: '/img/img-book-02.jpg' },
      { name: '방황하는 내국인', desc: '유배지의 절망 속에서<br>명철한 통찰', cover: '/img/rcd-book-04.png' },
    ],
  },
}

const scenario = computed(() => SCENARIOS[scenarioId] || SCENARIOS['02'])

// AI 타이핑 애니메이션
const typedLine1 = ref('')
const typedLine2 = ref('')
const aiWrapRef = ref<HTMLElement | null>(null)
const aiExpanded = ref(false)
const showExpandBtn = ref(false)
const typingDone = ref(false)

function toggleAiExpand() {
  if (!typingDone.value) {
    // 타이핑 중 펼치기 클릭 → 즉시 완성
    typedLine1.value = scenario.value.aiLines[0]
    typedLine2.value = scenario.value.aiLines[1]
    typingDone.value = true
  }
  aiExpanded.value = !aiExpanded.value
}

function typeLine(lineRef: Ref<string>, text: string, onDone?: () => void) {
  let i = 0
  const tick = () => {
    if (i < text.length) {
      lineRef.value += text[i++]
      setTimeout(tick, 28)
    } else {
      onDone?.()
    }
  }
  tick()
}

// 모달
const modalOpen = ref(false)
const selectedBook = ref<any>(null)

function openModal(book: any) {
  selectedBook.value = book
  modalOpen.value = true
}

onKeydown('Escape', () => { modalOpen.value = false })

onMounted(() => {
  setTimeout(() => {
    typeLine(typedLine1, scenario.value.aiLines[0], () => {
      setTimeout(() => {
        typeLine(typedLine2, scenario.value.aiLines[1], () => {
          typingDone.value = true
          nextTick(() => {
            if (aiWrapRef.value && aiWrapRef.value.scrollHeight > aiWrapRef.value.clientHeight) {
              showExpandBtn.value = true
            }
          })
        })
      }, 120)
    })
  }, 500)
})

function onKeydown(key: string, fn: () => void) {
  const handler = (e: KeyboardEvent) => { if (e.key === key) fn() }
  onMounted(() => document.addEventListener('keydown', handler))
  onUnmounted(() => document.removeEventListener('keydown', handler))
}
</script>
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/pages/recommend/[id].vue
git commit -m "feat: add recommend detail page with AI typing animation and modal"
```

---

## Self-Review

### Spec Coverage
- ✅ 에셋 복사 (Task 1)
- ✅ useBookmark composable (Task 2)
- ✅ AppSidebar skx-lnb (Task 3)
- ✅ index.vue landing+results (Task 4)
- ✅ books/[cnts_id].vue + vtabs + chat panel (Task 5)
- ✅ papers.vue (Task 6)
- ✅ papers/[id].vue 논문 상세 신규 (Task 7)
- ✅ recommend.vue 신규 (Task 8)
- ✅ recommend/[id].vue + AI 타이핑 + 모달 (Task 9)
- ✅ common.js 수직탭 → Vue vtabsRef + updateVtabSlider (Tasks 5, 7)
- ✅ common.js 북마크 → useBookmark composable (Tasks 2, 4, 5)
- ✅ 신작도서 카운트업 + 탭슬라이더 → Vue onMounted (Task 4)

### Type Consistency
- `BookChunkGroup` 타입 — tasks 4, 5, 6, 7에서 일관 사용
- `updateVtabSlider` — tasks 5, 7 동일 패턴
- `useBookmark` — task 2 정의, tasks 4, 5에서 import
