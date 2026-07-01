<template>
  <div class="skx-app">
    <AppSidebar
      :book-history="bookHistory"
      :paper-history="paperHistory"
      :active-id="currentHistoryId ?? undefined"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
      @restore="restoreSession"
    />

    <!-- ===== LANDING VIEW ===== -->
    <main v-if="view === 'landing'" class="skx-contents">
      <div class="skx-contents__inner">
        <h1 class="skx-hero">
          <span v-if="mode === 'book'"
            >몰랐던 책까지 찾고 알려주는<br />든든한 사서 큐레이션 AI
            SKOVIX</span
          >
          <span v-else
            >몰랐던 자료까지 찾고 분석해주는<br />똑똑한 검색 분석가 AI
            SKOVIX</span
          >
        </h1>

        <!-- 검색 탭 슬라이더 -->
        <div
          class="skx-tabs"
          role="tablist"
          aria-label="검색 유형"
          ref="tabsRef"
        >
          <span
            class="skx-tabs__slider"
            :style="tabSliderStyle"
            aria-hidden="true"
          ></span>
          <button
            type="button"
            :class="['skx-tab skx-tab--book', mode === 'book' && 'is-active']"
            role="tab"
            :aria-selected="mode === 'book'"
            @click="setMode('book')"
          >
            <img
              class="skx-tab__icon"
              :src="
                mode === 'book'
                  ? '/img/ico-tab-book-on.svg'
                  : '/img/ico-tab-book-off.svg'
              "
              alt=""
            />
            <span class="skx-tab__label">도서검색</span>
          </button>
          <button
            type="button"
            :class="['skx-tab skx-tab--paper', mode === 'paper' && 'is-active']"
            role="tab"
            :aria-selected="mode === 'paper'"
            @click="setMode('paper')"
          >
            <img
              class="skx-tab__icon"
              :src="
                mode === 'paper'
                  ? '/img/ico-tab-paper-on.svg'
                  : '/img/ico-tab-paper-off.svg'
              "
              alt=""
            />
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
                <button
                  type="button"
                  class="skx-send"
                  aria-label="검색"
                  @click="handleSearch(currentQuery)"
                >
                  <img src="/img/ico-send.svg" alt="" />
                </button>
              </div>
            </div>
            <ul class="skx-chips">
              <li v-for="chip in suggestions.book" :key="chip">
                <button
                  type="button"
                  class="skx-chip"
                  @click="handleSearch(chip)"
                >
                  {{ chip }}
                </button>
              </li>
            </ul>
          </div>
          <button
            type="button"
            class="skx-recommend"
            @click="navigateTo('/recommend')"
          >
            <span class="skx-recommend__glow" aria-hidden="true"></span>
            <span class="skx-recommend__panel" aria-hidden="true"></span>
            <span class="skx-recommend__icon"
              ><img src="/img/ico-search-lg.svg" alt=""
            /></span>
            <span class="skx-recommend__label"
              >내 상황에 맞는 도서 추천받기</span
            >
            <img class="skx-recommend__arrow" src="/img/ico-arrow.svg" alt="" />
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
                <button
                  type="button"
                  class="skx-send"
                  aria-label="검색"
                  @click="handleSearch(currentQuery)"
                >
                  <img src="/img/ico-send.svg" alt="" />
                </button>
              </div>
            </div>
            <ul class="skx-chips">
              <li v-for="chip in suggestions.paper" :key="chip">
                <button
                  type="button"
                  class="skx-chip"
                  @click="handleSearch(chip)"
                >
                  {{ chip }}
                </button>
              </li>
            </ul>
            <!-- 논문 필터 드롭다운 -->
            <div class="skx-filters">
              <div :class="['skx-select', filterOpen && 'is-open']">
                <button
                  type="button"
                  class="skx-select__btn"
                  aria-haspopup="listbox"
                  :aria-expanded="filterOpen"
                  @click.stop="filterOpen = !filterOpen"
                >
                  <span class="skx-select__label">{{
                    selectedFilter || "자료유형"
                  }}</span>
                  <img
                    class="skx-select__arrow"
                    src="/img/ico-arrow-down.svg"
                    alt=""
                  />
                </button>
                <ul class="skx-select__menu" role="listbox">
                  <li v-for="opt in filterOptions" :key="opt">
                    <button
                      type="button"
                      class="skx-select__option"
                      :class="selectedFilter === opt && 'is-selected'"
                      role="option"
                      @click="selectFilter(opt)"
                    >
                      {{ opt }}
                    </button>
                  </li>
                </ul>
              </div>
              <div class="skx-filter-chip__wrap">
                <span
                  v-for="f in activeFilters"
                  :key="f"
                  class="skx-filter-chip"
                >
                  {{ f }}
                  <button
                    type="button"
                    class="skx-filter-chip__x"
                    aria-label="필터 삭제"
                    @click="removeFilter(f)"
                  >
                    <img src="/img/ico-delete.svg" alt="" />
                  </button>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 신작도서 카운트업 -->
        <section class="skx-newbooks">
          <h2 class="skx-newbooks__title">
            지금도 새로운 책이 업데이트 되고 있어요!
          </h2>
          <div class="skx-newbooks__row">
            <div class="skx-newbooks__count">
              <span class="skx-newbooks__label">신작도서</span>
              <span class="skx-newbooks__num">
                <span class="skx-newbooks__value">{{
                  newbooksCount.toLocaleString("ko-KR")
                }}</span>
                <span class="skx-newbooks__unit">권</span>
              </span>
            </div>
            <ul class="skx-newbooks__stack" aria-hidden="true">
              <li
                v-for="i in 6"
                :key="i"
                :class="['skx-book', i === 1 && 'is-loading']"
              >
                <span class="skx-book__spine"
                  ><img
                    class="skx-book__spinner"
                    src="/img/ico-spinner.svg"
                    alt=""
                /></span>
                <span class="skx-book__bar"></span>
              </li>
            </ul>
          </div>
        </section>
      </div>
    </main>

    <!-- ===== RESULTS VIEW ===== -->
    <main v-else-if="view === 'results'" class="skx-result">
      <div class="skx-rsearch">
        <input
          type="text"
          class="skx-rsearch__input"
          v-model="currentQuery"
          aria-label="검색어 입력"
          @keydown.enter.prevent="handleSearch(currentQuery)"
        />
        <button
          type="button"
          class="skx-send"
          aria-label="검색"
          @click="handleSearch(currentQuery)"
        >
          <img src="/img/ico-send.svg" alt="" />
        </button>
      </div>

      <div
        v-if="loading"
        class="skx-result-card"
        style="padding: 40px; text-align: center"
      >
        <img src="/img/ico-spinner.svg" alt="" style="width: 32px" />
        <p style="margin-top: 12px">
          AI가 {{ mode === "book" ? "도서" : "논문" }}를 검색 중입니다...
        </p>
      </div>

      <div
        v-else-if="searchError"
        class="skx-result-card"
        style="padding: 20px; color: #c00"
      >
        {{ searchError }}
      </div>

      <template v-else>
        <div class="skx-result-card">
          <!-- AI 섹션 (도서) -->
          <section
            v-if="mode === 'book' && books.length"
            class="skx-ai-section"
          >
            <header class="skx-ai-header">
              <h2 class="skx-ai-header__title">AI 검색 결과</h2>
              <p v-if="keywordChips.length" class="skx-ai-header__keywords">
                키워드: {{ keywordChips.join(", ") }}
              </p>
            </header>
            <div class="skx-ai-panel">
              <div class="skx-ai-panel__top">
                <div class="skx-ai-panel__logo-row">
                  <img
                    class="skx-ai-panel__logo"
                    src="/img/logo-mark.svg"
                    alt="SKOVIX AI"
                  />
                  <span class="skx-ai-panel__title-text"
                    >AI가 원하시는 도서를 찾았어요!</span
                  >
                  <span v-if="curationLoading" class="skx-ai-panel__loading"
                    >●</span
                  >
                </div>
                <div class="skx-ai-panel__fb">
                  <span class="skx-ai-panel__fb-label"
                    >찾으시는 도서가 맞나요?</span
                  >
                </div>
              </div>
              <div :class="['skx-ai-answer-wrap', aiExpanded && 'is-expanded']">
                <div class="skx-ai-answer">
                  <p class="skx-ai-answer__text">{{ curationIntro }}</p>
                  <ul v-if="curationItems.length" class="skx-ai-answer__list">
                    <li v-for="ci in curationItems" :key="ci.book_id">
                      {{ ci.reason }}
                    </li>
                  </ul>
                </div>
                <button
                  type="button"
                  class="skx-ai-expand-bar"
                  :aria-expanded="aiExpanded"
                  @click="aiExpanded = !aiExpanded"
                >
                  <span class="skx-ai-expand-bar__label">{{
                    aiExpanded ? "접기" : "펼치기"
                  }}</span>
                  <img
                    class="skx-ai-expand-bar__arrow"
                    src="/img/ico-arrow-down.svg"
                    alt=""
                  />
                </button>
              </div>
            </div>
          </section>

          <!-- AI 섹션 (논문) -->
          <section
            v-if="mode === 'paper' && (paperSummaryText || paperSummaryLoading)"
            class="skx-ai-section"
          >
            <header class="skx-ai-header">
              <h2 class="skx-ai-header__title">AI 검색 결과</h2>
            </header>
            <div class="skx-ai-panel">
              <div class="skx-ai-panel__top">
                <div class="skx-ai-panel__logo-row">
                  <img
                    class="skx-ai-panel__logo"
                    src="/img/logo-mark.svg"
                    alt="SKOVIX AI"
                  />
                  <span class="skx-ai-panel__title-text">AI 핵심 요약</span>
                  <span v-if="paperSummaryLoading" class="skx-ai-panel__loading"
                    >●</span
                  >
                </div>
              </div>
              <div :class="['skx-ai-answer-wrap', aiExpanded && 'is-expanded']">
                <div class="skx-ai-answer">
                  <div v-html="renderedPaperSummary" />
                </div>
                <button
                  type="button"
                  class="skx-ai-expand-bar"
                  :aria-expanded="aiExpanded"
                  @click="aiExpanded = !aiExpanded"
                >
                  <span class="skx-ai-expand-bar__label">{{
                    aiExpanded ? "접기" : "펼치기"
                  }}</span>
                  <img
                    class="skx-ai-expand-bar__arrow"
                    src="/img/ico-arrow-down.svg"
                    alt=""
                  />
                </button>
              </div>
            </div>
          </section>

          <!-- 도서/논문 목록 -->
          <div class="skx-book-list">
            <article
              v-for="(item, i) in mode === 'paper' ? papers : books"
              :key="item.book_id"
              :class="[
                'skx-book-card',
                i >= 3 && !bookListExpanded ? 'skx-book-card--hidden' : '',
              ]"
              style="cursor: pointer"
              @click="openDetail(item)"
            >
              <div class="skx-book-card__thumb">
                <BookCover :book-id="item.book_id" />
              </div>
              <div class="skx-book-card__body">
                <div class="skx-book-card__top">
                  <div class="skx-book-card__tags">
                    <span class="skx-tag skx-tag--score"
                      >정합성
                      {{ Math.round((item.best_score || 0) * 100) }}%</span
                    >
                    <span
                      v-for="tag in parseThemes(
                        item.book_info?.themes ||
                          item.book_info?.keyword ||
                          item.book_info?.subject,
                      )"
                      :key="tag"
                      class="skx-tag skx-tag--keyword"
                      >#{{ tag }}</span
                    >
                  </div>
                  <button
                    type="button"
                    class="skx-book-card__bookmark"
                    :aria-label="
                      isBookmarked(item.book_id) ? '북마크 해제' : '북마크'
                    "
                    @click.stop="toggleBookmark(item.book_id)"
                  >
                    <img :src="bookmarkIcon(item.book_id)" alt="" />
                  </button>
                </div>
                <div class="skx-book-card__meta">
                  <h3 class="skx-book-card__title">
                    {{ item.book_info?.title || item.book_id }}
                  </h3>
                  <div class="skx-book-card__info-row">
                    <span
                      v-if="item.book_info?.material_type"
                      class="skx-meta-text"
                      >{{ item.book_info.material_type }}</span
                    >
                    <span
                      v-if="
                        item.book_info?.personal_author ||
                        item.book_info?.corporate_author
                      "
                      class="skx-dot"
                    ></span>
                    <span class="skx-meta-text">{{
                      item.book_info?.personal_author ||
                      item.book_info?.corporate_author
                    }}</span>
                    <span
                      v-if="item.book_info?.pub_date"
                      class="skx-dot"
                    ></span>
                    <span v-if="item.book_info?.pub_date" class="skx-meta-text"
                      >{{ item.book_info.pub_date.slice(0, 4) }}년</span
                    >
                    <span
                      v-if="item.book_info?.publisher"
                      class="skx-dot"
                    ></span>
                    <span
                      v-if="item.book_info?.publisher"
                      class="skx-meta-text"
                      >{{ item.book_info.publisher }}</span
                    >
                  </div>
                </div>
                <div class="skx-book-card__actions" @click.stop>
                  <button
                    type="button"
                    class="skx-btn-chat"
                    @click="openDetailWithChat(item)"
                  >
                    <img src="/img/ico-chat.svg" alt="" />
                    <span class="skx-btn-chat__label"
                      >이
                      {{ mode === "paper" ? "논문과" : "책과" }} 대화하기</span
                    >
                  </button>
                  <!-- <button
                    type="button"
                    class="skx-btn-loan"
                    @click="requestLoan(item)"
                  >
                    대출신청
                  </button> -->
                  <button
                    type="button"
                    class="skx-btn-read"
                    @click="viewPdf(item)"
                  >
                    원문 보기
                  </button>
                  <button
                    v-if="mode === 'paper'"
                    type="button"
                    class="skx-btn-loan"
                    @click.stop="openCitation(item)"
                  >
                    출처 인용
                  </button>
                </div>
              </div>
            </article>
          </div>

          <!-- 펼치기 버튼 (4개 이상일 때만) -->
          <button
            v-if="(mode === 'paper' ? papers.length : books.length) > 3"
            type="button"
            class="skx-book-expand"
            :aria-expanded="bookListExpanded"
            @click="bookListExpanded = !bookListExpanded"
          >
            <span class="skx-book-expand__label">{{
              bookListExpanded ? "접기" : "펼치기"
            }}</span>
            <img
              class="skx-book-expand__arrow"
              src="/img/ico-arrow-down.svg"
              alt=""
            />
          </button>
        </div>
      </template>
    </main>

    <!-- CitationModal, PdfViewer, Toast (preserve existing) -->
    <CitationModal
      :open="citationModal"
      :book-id="citationBook?.book_id ?? null"
      :references="citationBook?.book_info?.references ?? []"
      @close="citationModal = false"
    />

    <PdfViewer
      v-if="pdfOpen && selectedItem"
      :cnts-id="selectedItem.book_id"
      :title="selectedItem.book_info?.title"
      @close="pdfOpen = false"
    />

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import type { BookChunkGroup } from "~/types/search";
import type { HistoryEntry } from "~/types/history";

// ── 상수 ──────────────────────────────────────────────────
const SUGGESTIONS: Record<string, string[]> = {
  book: [
    "한국 경제에 대해 알고싶은데 책 추천해줄래?",
    "북한 경제 관련 리포트 써야하는데 도움되는 책",
    "수출 관련 보고서 참조 가능한 도서 찾아줄래?",
  ],
  paper: [
    "딥러닝 기반 자연어 처리 최신 연구",
    "한국어 감성 분석 논문 추천",
    "의료 AI 임상 적용 사례 연구",
  ],
};

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

// ── 세션 ──────────────────────────────────────────────────
function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getSessionId(): string {
  if (!process.client) return "";
  let sid = localStorage.getItem("sid");
  if (!sid) {
    sid = generateUUID();
    localStorage.setItem("sid", sid);
  }
  return sid;
}

// ── 뷰 상태 ───────────────────────────────────────────────
const view = ref<"landing" | "results" | "detail">("landing");
const mode = ref<"book" | "paper">("book");

// ── 검색 ──────────────────────────────────────────────────
const currentQuery = ref("");
const rewrittenQuery = ref("");
const loading = ref(false);
const searchError = ref("");
const books = ref<BookChunkGroup[]>([]);
const papers = ref<BookChunkGroup[]>([]);
const keywordChips = ref<string[]>([]);

// ── 큐레이션 (도서) ────────────────────────────────────────
const curation = ref<any>(null);
const curationOpen = ref(true);
const curationLoading = ref(false);

// ── 결과 펼치기/접기 ──────────────────────────────────────
const bookListExpanded = ref(false);
const aiExpanded = ref(false);
// SSE 스트리밍용 분리 ref
const curationIntro = ref("");
const curationItems = ref<Array<{ book_id: string; reason: string }>>([]);

// ── 논문 핵심 요약 SSE ─────────────────────────────────────
const paperSummaryText = ref("");
const paperSummaryLoading = ref(false);
const paperSummarySources = ref<BookChunkGroup[]>([]);

const renderedPaperSummary = computed(() =>
  paperSummaryText.value
    ? (marked.parse(paperSummaryText.value) as string)
    : "",
);

// ── 상세 ──────────────────────────────────────────────────
const selectedItem = ref<BookChunkGroup | null>(null);
const detailTab = ref("reason");
const reasonText = ref("");
const reasonLoading = ref(false);
const showChat = ref(false);
const pdfOpen = ref(false);
const refsOpen = ref(true);

const detailTabs = computed(() =>
  mode.value === "paper"
    ? [
        { key: "abstract", label: "초록" },
        { key: "intro", label: "논문 소개" },
      ]
    : [
        { key: "reason", label: "추천하는 이유" },
        { key: "plot", label: "줄거리" },
        { key: "intro", label: "책 소개" },
        { key: "effect", label: "책을 읽고 난 후" },
      ],
);

const renderedReason = computed(() =>
  reasonText.value ? (marked.parse(reasonText.value) as string) : "",
);

// ── 연관 추천 ──────────────────────────────────────────────
const relatedItems = ref<any[]>([]);
const relatedLoading = ref(false);
const selectedRelated = ref<any>(null);

// ── 출처 인용 ──────────────────────────────────────────────
const citationModal = ref(false);
const citationBook = ref<BookChunkGroup | null>(null);

// ── 토스트 ────────────────────────────────────────────────
const toast = ref("");

// ── 검색 기록 ─────────────────────────────────────────────
const { bookHistory, paperHistory, addEntry, updateAiSummary, getById } =
  useSearchHistory();
const currentHistoryId = ref<string | null>(null);

// ── Publishing additions ──────────────────────────────────────
// Tab slider
const tabsRef = ref<HTMLElement | null>(null);
const tabSliderStyle = ref<{ width: string; transform: string }>({
  width: "0px",
  transform: "translateX(0px)",
});

// Filter dropdown (paper mode)
const filterOpen = ref(false);
const selectedFilter = ref("");
const activeFilters = ref<string[]>([]);
const filterOptions = ["KCI 등재", "KCI 미등재", "KCI 후보"];

// Newbooks countup
const newbooksCount = ref(0);
const NEW_BOOKS_TARGET = 1245;

// Bookmark
const { isBookmarked, toggleBookmark, bookmarkIcon } = useBookmark();

function setMode(m: "book" | "paper") {
  mode.value = m;
  nextTick(() => updateTabSlider());
}

function updateTabSlider() {
  if (!tabsRef.value) return;
  const active = tabsRef.value.querySelector(
    ".skx-tab.is-active",
  ) as HTMLElement | null;
  if (!active) return;
  tabSliderStyle.value = {
    width: active.offsetWidth + "px",
    transform: `translateX(${active.offsetLeft}px)`,
  };
}

function selectFilter(opt: string) {
  selectedFilter.value = opt;
  filterOpen.value = false;
  if (!activeFilters.value.includes(opt)) activeFilters.value.push(opt);
}

function removeFilter(f: string) {
  activeFilters.value = activeFilters.value.filter((x) => x !== f);
  if (selectedFilter.value === f) selectedFilter.value = "";
}

function onDocClick() {
  filterOpen.value = false;
}
// ── End publishing additions ──────────────────────────────────

onMounted(async () => {
  if (!process.client) return;
  const restoreId = (useRoute().query.restore as string) ?? null;
  if (restoreId) {
    const entry = getById(restoreId);
    if (entry) restoreSession(entry);
  }

  // Tab slider
  nextTick(() => updateTabSlider());
  window.addEventListener("resize", updateTabSlider);

  // Newbooks countup
  const duration = 1600;
  const startTime = performance.now();
  const tick = (now: number) => {
    const p = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    newbooksCount.value = Math.round(NEW_BOOKS_TARGET * eased);
    if (p < 1) requestAnimationFrame(tick);
    else newbooksCount.value = NEW_BOOKS_TARGET;
  };
  requestAnimationFrame(tick);

  document.addEventListener("click", onDocClick);
});

onUnmounted(() => {
  window.removeEventListener("resize", updateTabSlider);
  document.removeEventListener("click", onDocClick);
});

// ── 유틸 ──────────────────────────────────────────────────
const suggestions = SUGGESTIONS;

function parseThemes(themes?: string | null): string[] {
  if (!themes) return [];
  return themes
    .split(/[,;]/)
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 4);
}

function isAvailable(_item: BookChunkGroup): boolean {
  return false; // 소장 정보 없음 — 더미
}

function formatTime(ts: string | number): string {
  if (!ts) return "";
  const d = new Date(ts);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return d.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
}

function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

// ── 검색 ──────────────────────────────────────────────────
async function handleSearch(query: string) {
  if (!query.trim()) return;

  // 논문 모드는 papers 전용 페이지로 이동
  if (mode.value === "paper") {
    navigateTo(`/papers?q=${encodeURIComponent(query.trim())}`);
    return;
  }

  currentQuery.value = query;
  loading.value = true;
  searchError.value = "";
  books.value = [];
  papers.value = [];
  curation.value = null;
  curationIntro.value = "";
  curationItems.value = [];
  curationOpen.value = true;
  bookListExpanded.value = false;
  aiExpanded.value = false;
  paperSummaryText.value = "";
  keywordChips.value = [];
  view.value = "results";

  try {
    {
      const data = await $fetch<any>(`${apiBase}/books/search`, {
        method: "POST",
        headers: { "x-session-id": getSessionId() },
        body: {
          query,
          mode: "book",
          top_k: 5,
          use_rewrite: true,
          use_rerank: true,
        },
      });
      if (data?.books) {
        books.value = data.books;
        rewrittenQuery.value = data.rewritten_query || query;
      }
      if (books.value.length) fetchCuration();
      currentHistoryId.value = addEntry({
        type: "book",
        query,
        result: data,
      });
    }
  } catch (e: any) {
    searchError.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
  } finally {
    loading.value = false;
  }
}

function handleChip(chip: string) {
  currentQuery.value = chip;
  handleSearch(chip);
}

function goLanding() {
  view.value = "landing";
  currentQuery.value = "";
  books.value = [];
  curation.value = null;
  selectedItem.value = null;
}

function restoreSession(entry: HistoryEntry) {
  if (entry.type === "paper") {
    navigateTo(`/papers?restore=${entry.id}`);
    return;
  }
  currentQuery.value = entry.query;
  currentHistoryId.value = entry.id;
  view.value = "results";
  books.value = entry.result?.books ?? [];
  curationIntro.value = entry.aiSummary ?? "";
  curationItems.value = [];
  curationOpen.value = true;
  bookListExpanded.value = false;
  aiExpanded.value = false;
}

// ── 큐레이션 (도서) ── SSE 타이프라이터 스트리밍 ──────────────
async function fetchCuration() {
  const topBooks = books.value.slice(0, 3);
  if (!topBooks.length) return;
  curationLoading.value = true;
  curationIntro.value = "";
  curationItems.value = [];
  try {
    const data = await $fetch<any>(`${apiBase}/books/curate`, {
      method: "POST",
      body: {
        query: currentQuery.value,
        book_ids: topBooks.map((b) => b.book_id),
        scores: topBooks.map((b) => b.best_score || 0),
        rewritten_query: rewrittenQuery.value,
      },
    });
    curation.value = data;
    // intro 타이프라이터 효과
    const intro: string = data?.intro || "";
    const items: Array<{ book_id: string; reason: string }> = data?.items || [];
    let i = 0;
    const typeIntro = () => {
      if (i < intro.length) {
        curationIntro.value += intro[i++];
        setTimeout(typeIntro, 18);
      } else {
        for (const ci of items) {
          curationItems.value.push({ book_id: ci.book_id, reason: ci.reason });
        }
        if (currentHistoryId.value && curationIntro.value) {
          updateAiSummary(currentHistoryId.value, curationIntro.value);
        }
      }
    };
    if (intro) {
      curationOpen.value = true;
      typeIntro();
    } else {
      curationIntro.value = intro;
      curationItems.value = items;
    }
  } catch {
    /* 큐레이션 실패 시 조용히 무시 */
  } finally {
    curationLoading.value = false;
  }
}

// ── 논문 핵심 요약 SSE ─────────────────────────────────────
async function fetchPaperSummary(query: string) {
  paperSummaryLoading.value = true;
  paperSummaryText.value = "";
  paperSummarySources.value = papers.value.slice(0, 5);
  const paperList = papers.value.slice(0, 5).map((b) => ({
    book_id: b.book_id,
    title: b.book_info?.title || "",
    authors:
      b.book_info?.personal_author || b.book_info?.corporate_author || "",
    best_chunk_text: b.chunks?.[0]?.text || "",
  }));
  try {
    const resp = await fetch(`${apiBase}/papers/summary/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, papers: paperList }),
    });
    await readSSE(resp, (json) => {
      if (json.text) paperSummaryText.value += json.text;
    });
  } catch {
    /* SSE 실패 — 조용히 */
  } finally {
    paperSummaryLoading.value = false;
  }
}

// ── 상세 열기 ──────────────────────────────────────────────
function openDetail(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(
      `/papers/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}`,
    );
    return;
  }
  navigateTo(
    `/books/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}&score=${item.best_score || 0}`,
  );
}

// 이 책과 대화하기 → detail + chat 자동 오픈
function openDetailWithChat(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(
      `/papers/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}&chat=1`,
    );
    return;
  }
  navigateTo(
    `/books/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}&score=${item.best_score || 0}&chat=1`,
  );
}

function openRelatedDetail(rel: any) {
  const fakeGroup: BookChunkGroup = {
    book_id: rel.book_id,
    book_info: rel.book_info,
    best_score: rel.score || 0,
    chunks: [],
  };
  openDetail(fakeGroup);
}

function switchDetailTab(key: string) {
  detailTab.value = key;
  if (key === "reason" && !reasonText.value && selectedItem.value) {
    fetchReason(selectedItem.value);
  }
}

// ── 추천 이유 SSE ──────────────────────────────────────────
async function fetchReason(item: BookChunkGroup) {
  reasonLoading.value = true;
  reasonText.value = "";
  try {
    const resp = await fetch(`${apiBase}/books/reason/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: currentQuery.value,
        book_id: item.book_id,
        chunk_texts: item.chunks?.map((c) => c.text) ?? [],
        rewritten_query: rewrittenQuery.value,
      }),
    });
    await readSSE(resp, (json) => {
      if (json.text) reasonText.value += json.text;
      if (json.keywords?.length && !keywordChips.value.length)
        keywordChips.value = json.keywords;
    });
  } catch {
    /* 추천 이유 실패 */
  } finally {
    reasonLoading.value = false;
  }
}

// ── 연관 추천 ──────────────────────────────────────────────
async function fetchRelated(cntsId: string) {
  relatedLoading.value = true;
  relatedItems.value = [];
  try {
    const endpoint =
      mode.value === "paper" ? `${apiBase}/papers/${cntsId}/related` : null;
    if (!endpoint) return;
    const data = await $fetch<any>(endpoint);
    relatedItems.value = data?.results || [];
  } catch {
    /* 연관 추천 실패 */
  } finally {
    relatedLoading.value = false;
  }
}

// ── 출처 인용 ──────────────────────────────────────────────
function openCitation(item: BookChunkGroup) {
  citationBook.value = item;
  citationModal.value = true;
}

// ── 대출 신청 / PDF ────────────────────────────────────────
function requestLoan(item: BookChunkGroup) {
  showToast(
    `"${item.book_info?.title || item.book_id}" 대출 신청 기능은 준비 중입니다.`,
  );
}

function viewPdf(item: BookChunkGroup) {
  selectedItem.value = item;
  pdfOpen.value = true;
}

// ── SSE 헬퍼 ──────────────────────────────────────────────
async function readSSE(resp: Response, onEvent: (json: any) => void) {
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop()!;
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (raw === "[DONE]") return;
      try {
        onEvent(JSON.parse(raw));
      } catch {
        /* skip */
      }
    }
  }
}
</script>
