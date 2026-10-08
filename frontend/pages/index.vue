<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
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
                  ref="bookInputRef"
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
                  @click="fillChip(chip, bookInputRef)"
                >
                  {{ chip }}
                </button>
              </li>
            </ul>
            <!-- 컬렉션 크기 드롭다운 (AI 답변에 사용될 도서 개수) -->
            <div class="skx-filters">
              <div :class="['skx-select', collectionOpen && 'is-open']">
                <button
                  type="button"
                  class="skx-select__btn"
                  aria-haspopup="listbox"
                  :aria-expanded="collectionOpen"
                  @click.stop="collectionOpen = !collectionOpen"
                >
                  <span class="skx-select__label"
                    >컬렉션 {{ collectionSize }}권</span
                  >
                  <img
                    class="skx-select__arrow"
                    src="/img/ico-arrow-down.svg"
                    alt=""
                  />
                </button>
                <ul class="skx-select__menu" role="listbox">
                  <li v-for="n in COLLECTION_SIZES" :key="n">
                    <button
                      type="button"
                      class="skx-select__option"
                      :class="collectionSize === n && 'is-selected'"
                      role="option"
                      :aria-selected="collectionSize === n"
                      @click="selectCollectionSize(n)"
                    >
                      {{ n }}권
                    </button>
                  </li>
                </ul>
              </div>
            </div>
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
              <ResearchSearchPlusMenu v-model="currentQuery" kind="paper" :disabled="loading" />
              <label class="skx-search__field">
                <span class="skx-sr-only">논문 검색어</span>
                <textarea
                  ref="paperInputRef"
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
                  @click="fillChip(chip, paperInputRef)"
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
        <!-- 검색 중에는 잠근다 — 검색 중 엔터는 무시되므로 고친 검색어가 조용히 버려지지 않게 -->
        <input
          type="text"
          class="skx-rsearch__input"
          v-model="currentQuery"
          aria-label="검색어 입력"
          :disabled="loading"
          @keydown.enter.prevent="handleSearch(currentQuery)"
        />
        <button
          type="button"
          class="skx-send"
          aria-label="검색"
          :disabled="loading"
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
                    :src="
                      curationLoading || curationTyping
                        ? '/ic_ing.gif'
                        : '/ic_done.png'
                    "
                    alt="SKOVIX AI"
                  />
                  <Transition name="skx-stage-fade" mode="out-in">
                    <span
                      :key="aiPanelTitle"
                      class="skx-ai-panel__title-text"
                      >{{ aiPanelTitle }}</span
                    >
                  </Transition>
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
                  <!-- <div
                    v-if="curationItems.length && !curationLoading"
                    class="skx-deepread-cta"
                  >
                    <span class="skx-deepread-cta__text">컬렉션에서 책과 직접 대화해보세요</span>
                    <button
                      type="button"
                      class="skx-deepread-cta__btn"
                      @click="navigateTo(`/books/${curationItems[0].book_id}?q=${encodeURIComponent(currentQuery)}&chat=1`)"
                    >
                      DeepRead 시작하기
                      <img src="/img/ico-arrow.svg" alt="" />
                    </button>
                  </div> -->
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
              <p
                v-if="curationItems.length && !curationLoading"
                class="skx-ai-hint"
              >
                <img src="/img/ico-chat.svg" alt="" />
                마음에 드는 책을 찾으셨다면
                <strong>DeepRead</strong>로 책과 직접 대화하며 더 깊이
                읽어보세요
              </p>
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
                    :src="paperSummaryLoading ? '/ic_ing.gif' : '/ic_done.png'"
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
              v-for="(item, i) in displayBooks"
              :key="item.book_id"
              :class="[
                'skx-book-card',
                i >= visibleCount && !bookListExpanded
                  ? 'skx-book-card--hidden'
                  : '',
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
                    <span
                      v-if="collectionIds.has(item.book_id)"
                      class="skx-tag skx-tag--collection"
                      >AI 컬렉션</span
                    >
                    <template
                      v-if="
                        item.title_score !== undefined &&
                        item.content_score !== undefined
                      "
                    >
                      <ScoreRing
                        :pct="item.title_score * 100"
                        label="제목 일치율"
                      />
                      <ScoreRing
                        :pct="item.content_score * 100"
                        label="내용 일치율"
                        variant="content"
                      />
                    </template>
                    <span class="skx-tag skx-tag--score"
                      >관련도
                      {{ Math.floor((item.best_score || 0) * 100) }}%</span
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
                    <!-- <span
                      v-if="item.book_info?.material_type"
                      class="skx-meta-text"
                      >{{ item.book_info.material_type }}</span
                    > -->
                    <!-- <span
                      v-if="
                        item.book_info?.personal_author ||
                        item.book_info?.corporate_author
                      "
                      class="skx-dot"
                    ></span> -->
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
                    <span class="skx-btn-chat__label">DeepRead</span>
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

          <!-- 더보기 버튼 (컬렉션 외 도서가 있을 때만) -->
          <button
            v-if="displayBooks.length > visibleCount"
            type="button"
            class="skx-book-expand"
            :aria-expanded="bookListExpanded"
            @click="bookListExpanded = !bookListExpanded"
          >
            <span class="skx-book-expand__label">{{
              bookListExpanded ? "접기" : "더보기"
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
import type { Ref } from "vue";
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
import { useCuration } from "~/composables/useCuration";
import { safeLocalStorage } from "~/utils/browserId";
import { slimBookResult } from "~/utils/historySnapshot";
import { readV1Map } from "~/utils/historyStore";
import { awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import { detailUrl } from "~/utils/detailSource";
import type { BookChunkGroup } from "~/types/search";
import type { BookEntry, BookSnapshot } from "~/types/history";

// ── 상수 ──────────────────────────────────────────────────
// 예시 질의는 운영 검색으로 고른 것이다(2026-10-08 — 후보마다 상위 결과를 판정자 둘 이상이 따로 봤다).
// 도서 소장 자료는 국문학 학위논문(1983~1997)·정부 재정·경제 보고서 쪽에 몰려 있어 교양서를 기대하는 질의
// (경제 일반·기후·진로 등)는 결과가 흩어진다. 논문은 + 메뉴로 딥리서치를 시작할 때도 쓰이므로 06b 재판정에서
// 보고서 정밀도가 높았던 질문(노인 우울 95%·다문화 아동 75~100%·공공도서관 82~86%)을 그 문장 그대로 쓴다
const SUGGESTIONS: Record<string, string[]> = {
  book: [
    "조선시대 고전소설을 연구한 자료 찾아줘",
    "국가 재정 운용 계획에 관한 자료 찾아줘",
    "한국 현대시를 연구한 자료 찾아줘",
  ],
  paper: [
    "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
    "다문화가정 아동의 언어 발달에 관한 연구가 궁금해",
    "공공도서관 서비스 품질 평가 연구가 궁금해",
  ],
};

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;
const api = useApi();
const route = useRoute();
const router = useRouter();

// ── 뷰 상태 ───────────────────────────────────────────────
const view = ref<"landing" | "results" | "detail">("landing");
const mode = ref<"book" | "paper">("book");

// ── 검색 ──────────────────────────────────────────────────
const currentQuery = ref("");
// 화면에 떠 있는 결과의 검색어(앞뒤 공백 제거) — currentQuery 는 입력창 v-model 이라 사용자가 고치는 중일 수 있어,
// 결과에 묶인 이동·주소 비교는 이 값을 쓴다
const resultQuery = ref("");
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
const historyApi = useHistory();
const currentHistoryId = ref<string | null>(null);
// 검색·복원·큐레이션을 한 묶음으로 끊는다 — 새 검색이나 복원이 시작되면 이전 묶음의
// 응답·타이핑·저장이 새 화면과 새 기록을 덮지 못하게 한다. 큐레이션은 화면 갱신만 끊고 요청·저장은 끝까지 간다
let runCtrl: AbortController | null = null;
const curationRequests = useCuration();
function beginRun(): AbortSignal {
  runCtrl?.abort();
  runCtrl = new AbortController();
  return runCtrl.signal;
}

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
  collectionOpen.value = false;
}
// ── End publishing additions ──────────────────────────────────

onMounted(async () => {
  if (!process.client) return;
  // 첫 복원을 setup 이 아니라 마운트 뒤에 한다 — 서버가 그린 랜딩과 하이드레이션이 어긋나지 않게
  restoreFromQuery();

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
  // 떠난 화면에 늦게 온 응답·타이핑 타이머가 상태를 고치지 않게 묶음을 끊는다.
  // 큐레이션 요청은 끊지 않는다 — 끝까지 받아 기록에 저장해야 돌아왔을 때 다시 만들지 않는다(fetchCuration)
  runCtrl?.abort();
  window.removeEventListener("resize", updateTabSlider);
  document.removeEventListener("click", onDocClick);
  if (aiStageTimer) clearTimeout(aiStageTimer);
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
async function handleSearch(query: string, reuse?: BookEntry) {
  if (!query.trim() || loading.value) return;

  // 논문 모드는 papers 전용 페이지로 이동 — 랜딩에서 고른 등재 필터를 유지해서 넘긴다
  if (mode.value === "paper") {
    const grade = activeFilters.value[0];
    const gradeParam = grade ? `&grade=${encodeURIComponent(grade)}` : "";
    navigateTo(`/papers?q=${encodeURIComponent(query.trim())}${gradeParam}`);
    return;
  }

  const signal = beginRun();
  currentQuery.value = query;
  resultQuery.value = query.trim();
  currentHistoryId.value = null;
  // 주소의 이전 h 도 함께 내린다 — 남겨 두면 검색이 도는 동안·실패한 뒤에도 사이드바가 이전 기록을 강조하고,
  // 그 기록을 누르면 지금 주소와 같아 이동이 무시되며, 새로고침하면 이전 기록이 열린다
  router.replace({ query: { q: query.trim() } });
  loading.value = true;
  searchError.value = "";
  books.value = [];
  papers.value = [];
  curation.value = null;
  curationIntro.value = "";
  curationItems.value = [];
  curationLoading.value = false;
  curationTyping.value = false;
  curationOpen.value = true;
  bookListExpanded.value = false;
  aiExpanded.value = false;
  paperSummaryText.value = "";
  keywordChips.value = [];
  view.value = "results";

  try {
    const data = await api<any>("/books/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        // 컬렉션 크기 + 더보기 목록용 여유분 확보 (백엔드 상한 20)
        top_k: Math.min(20, Math.max(collectionSize.value + 5, 10)),
        use_rewrite: true,
        use_rerank: true,
      },
      signal,
    });
    if (signal.aborted) return;
    if (data?.books) {
      books.value = data.books;
      rewrittenQuery.value = data.rewritten_query || query;
    }
    loading.value = false;

    // 기록 id 를 먼저 확정해 큐레이션에 넘긴다 — 끝난 뒤 저장이 그 사이 바뀐 화면의 기록을 덮지 않게
    const snapshot = slimBookResult(data) ?? undefined;
    const entry = reuse
      ? ((await historyApi.patch(reuse.id, { snapshot })) ?? reuse)
      : await historyApi.add({ kind: "book", title: query.trim(), params: {}, snapshot });
    if (signal.aborted) return;
    currentHistoryId.value = entry.id;
    router.replace({ query: { q: query.trim(), h: entry.id } });
    if (books.value.length) fetchCuration(entry.id, query.trim(), rewrittenQuery.value, signal);
  } catch (e: any) {
    if (signal.aborted) return;
    searchError.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
  } finally {
    if (!signal.aborted) loading.value = false;
  }
}

// 예시 질의는 입력창에만 채운다 — 바로 검색하지 않아 고쳐 쓰거나(논문은 + 메뉴로 딥리서치를 골라) 보낼 수 있다.
// 이어 쓰기 좋게 초점을 입력창 끝에 둔다. 두 패널이 입력값(currentQuery)을 같이 쓰므로 초점만 패널별로 옮긴다
const bookInputRef = ref<HTMLTextAreaElement | null>(null);
const paperInputRef = ref<HTMLTextAreaElement | null>(null);

function fillChip(chip: string, input: HTMLTextAreaElement | null) {
  if (loading.value) return;
  currentQuery.value = chip;
  nextTick(() => {
    if (!input) return;
    input.focus();
    input.setSelectionRange(chip.length, chip.length);
  });
}

// 랜딩으로 되돌린다 — 진행 중인 검색·복원·큐레이션 묶음을 끊고 결과 화면 상태를 비운다
function goLanding() {
  runCtrl?.abort();
  runCtrl = null;
  view.value = "landing";
  currentQuery.value = "";
  resultQuery.value = "";
  rewrittenQuery.value = "";
  currentHistoryId.value = null;
  loading.value = false;
  searchError.value = "";
  books.value = [];
  papers.value = [];
  keywordChips.value = [];
  curation.value = null;
  curationIntro.value = "";
  curationItems.value = [];
  curationLoading.value = false;
  curationTyping.value = false;
  selectedItem.value = null;
  pdfOpen.value = false;
  citationModal.value = false;
  // 결과 화면으로 처음 열린 페이지는 탭이 그려진 적이 없어 슬라이더 폭이 0 이다 — 탭이 다시 그려진 뒤 맞춘다
  nextTick(() => updateTabSlider());
}

// ── 기록 복원 ─────────────────────────────────────────────
// 주소(?h=)가 복원의 정본이다 — 사이드바·뒤로가기·새로고침이 모두 이 한 길로 들어온다
async function restoreFromQuery() {
  // 다른 페이지로 넘어가는 중에는 그 주소의 q 로 재검색하지 않는다
  if (route.path !== "/") return;
  const query = route.query;
  const v1Map = readV1Map(safeLocalStorage());
  let target = readHistoryQuery(query, v1Map);
  if (awaitsV1Map(query, v1Map)) {
    // 사이드바가 시작한 이전이 대응표를 남길 때까지 기다린다 — 주소가 그대로라 지금 랜딩으로 빠지면 다시 복원할 계기가 없다.
    // 기다리는 사이 다른 복원·검색·이동이 끼면 그쪽이 묶음을 가져가 이 복원은 물러난다
    const signal = beginRun();
    loading.value = false;
    await historyApi.migrated();
    if (signal.aborted) return;
    target = readHistoryQuery(query, readV1Map(safeLocalStorage()));
  }
  const { h, q } = target;
  if (!h) {
    if (!q) {
      // 기록도 검색어도 없는 주소는 랜딩이다 — 같은 경로라 다시 마운트되지 않으므로(랜딩에서 기록을 연 뒤
      // 뒤로가기 등) 결과 화면과 진행 중인 요청을 직접 걷는다. 안 걷으면 주소는 '/' 인데 결과가 남는다
      goLanding();
      return;
    }
    // 입력창이 아니라 화면 결과의 검색어와 비교한다 — 입력창을 고쳐 둔 채 이 주소로 오면 엉뚱하게 건너뛴다.
    // 둘 다 앞뒤 공백을 뗀 값이라 같은 검색어를 공백 차이로 다시 찾지 않는다
    if (q !== resultQuery.value) {
      mode.value = "book";
      await handleSearch(q);
    }
    return;
  }
  if (h === currentHistoryId.value) return;

  const signal = beginRun();
  loading.value = false;
  const entry = await historyApi.get(h);
  if (signal.aborted) return;
  if (entry && entry.kind !== "book") {
    // 다른 종류의 기록 id 가 이 주소로 왔다(옛 ?restore= 등) — 그 종류의 주소로 보낸다
    router.replace(routeFor(entry));
    return;
  }
  const book = entry?.kind === "book" ? entry : null;
  if (book?.snapshot) {
    applyBookEntry(book, signal);
    return;
  }
  // 없거나 남의 기록이면 검색어로 새로 찾는다(D7). 결과만 비어 있던 내 기록은 같은 id 를 채운다
  if (!book) void historyApi.refresh("book");
  const retryQuery = q ?? book?.title;
  if (retryQuery) {
    mode.value = "book";
    await handleSearch(retryQuery, book ?? undefined);
    return;
  }
  showToast("없는 기록입니다. 목록을 새로 고쳤습니다.");
}

function applyBookEntry(entry: BookEntry, signal: AbortSignal) {
  const snap = entry.snapshot as BookSnapshot;
  mode.value = "book";
  view.value = "results";
  loading.value = false;
  searchError.value = "";
  currentQuery.value = entry.title;
  resultQuery.value = entry.title;
  currentHistoryId.value = entry.id;
  rewrittenQuery.value = snap.rewritten_query || entry.title;
  books.value = snap.books as unknown as BookChunkGroup[];
  papers.value = [];
  keywordChips.value = [];
  curation.value = null;
  curationLoading.value = false;
  curationTyping.value = false;
  curationIntro.value = entry.ai?.intro ?? "";
  curationItems.value = (entry.ai?.items ?? []) as Array<{ book_id: string; reason: string }>;
  curationOpen.value = true;
  bookListExpanded.value = false;
  aiExpanded.value = false;
  if (route.query.h !== entry.id || route.query.q !== entry.title) {
    router.replace({ query: { q: entry.title, h: entry.id } });
  }
  // 요약이 비어 있으면 큐레이션이 아직 도는 중이거나 실패한 기록이다 — 도는 중이면 그 요청을 이어받고, 실패했으면 다시 만든다
  if (!entry.ai && books.value.length) {
    fetchCuration(entry.id, entry.title, rewrittenQuery.value, signal);
  }
}

// 같은 경로에서 쿼리만 바뀌면(사이드바 클릭·뒤로가기) 페이지가 다시 마운트되지 않는다.
// q 도 본다 — h 가 없는 주소(검색 중·실패 뒤의 ?q=)에서 랜딩 주소로 돌아오면 h 는 그대로 없어 변화를 놓친다
watch(
  [() => route.query.h ?? route.query.restore, () => route.query.q],
  () => {
    restoreFromQuery();
  },
);

// ── 컬렉션 개수 조정 (AI 답변에 사용될 도서 수, 랜딩 드롭다운) ──
const COLLECTION_SIZES = [3, 5, 10, 20];
// 컬렉션 포함 최소 연관도 (임계값 미달 도서는 LLM 답변에서 제외)
const COLLECTION_SCORE_THRESHOLD = 0.4;
const collectionSize = ref(3);
const collectionOpen = ref(false);

function selectCollectionSize(n: number) {
  collectionSize.value = n;
  collectionOpen.value = false;
}

// 컬렉션 소속 도서 id — 큐레이션 완료 후엔 실제 답변에 사용된 도서,
// 생성 전엔 동일한 선정 규칙(임계값+크기)으로 미리 계산
const collectionIds = computed(() => {
  if (curationItems.value.length) {
    return new Set(curationItems.value.map((ci) => ci.book_id));
  }
  return new Set(
    books.value
      .filter((b) => (b.best_score || 0) >= COLLECTION_SCORE_THRESHOLD)
      .slice(0, collectionSize.value)
      .map((b) => b.book_id),
  );
});

// 컬렉션 도서를 상위로 정렬한 표시용 목록
const displayBooks = computed(() => {
  if (mode.value === "paper") {
    if (!activeFilters.value.length) return papers.value;
    return papers.value.filter((p) => {
      const grade = p.book_info?.grade;
      return activeFilters.value.some((f) =>
        f === "KCI 미등재" ? !grade : grade === f,
      );
    });
  }
  const ids = collectionIds.value;
  const inCollection = books.value.filter((b) => ids.has(b.book_id));
  const rest = books.value.filter((b) => !ids.has(b.book_id));
  return [...inCollection, ...rest];
});

// 항상 보이는 개수: 컬렉션 전체 (없으면 기본 3권)
const visibleCount = computed(() => {
  if (mode.value === "paper") return 3;
  const n = collectionIds.value.size;
  return n > 0 ? n : 3;
});

// ── AI 패널 단계별 로딩 메시지 ─────────────────────────────
const AI_STAGES = [
  "AI가 질문을 이해했어요",
  "AI 사서가 모든 도서 본문을 탐색하고 있어요",
];
const aiStage = ref(0);
let aiStageTimer: ReturnType<typeof setTimeout> | null = null;

const aiPanelTitle = computed(() =>
  curationLoading.value
    ? AI_STAGES[Math.min(aiStage.value, AI_STAGES.length - 1)]
    : "AI가 가장 적합한 도서를 찾았어요!",
);

function startAiStages() {
  aiStage.value = 0;
  if (aiStageTimer) clearTimeout(aiStageTimer);
  aiStageTimer = setTimeout(() => {
    aiStage.value = 1;
  }, 900);
}

// 타이프라이터 출력 중 여부 (아이콘은 타이핑 종료까지 ing 유지)
const curationTyping = ref(false);

function typeInto(target: Ref<string>, text: string, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    let i = 0;
    const step = () => {
      if (signal.aborted || i >= text.length) {
        resolve();
        return;
      }
      target.value += text.charAt(i++);
      setTimeout(step, 18);
    };
    step();
  });
}

// ── 큐레이션 (도서) ── 타이프라이터 출력 ──────────────────────
// 기록 id 와 함께 검색어도 호출하는 쪽이 붙잡아 넘긴다 — 입력창(currentQuery)은 사용자가 고치는 중일 수 있어,
// 지금 값을 읽으면 다른 검색어로 만든 요약이 이 기록에 저장된다
async function fetchCuration(
  historyId: string,
  query: string,
  rewritten: string,
  signal: AbortSignal,
) {
  // 임계값을 넘는 도서만, 선택한 컬렉션 크기만큼 LLM 답변에 포함
  const topBooks = books.value
    .filter((b) => (b.best_score || 0) >= COLLECTION_SCORE_THRESHOLD)
    .slice(0, collectionSize.value);
  if (!topBooks.length) return;
  startAiStages();
  curationLoading.value = true;
  curationTyping.value = true;
  curationIntro.value = "";
  curationItems.value = [];
  try {
    // 요청은 묶음의 signal 로 끊지 않는다 — 단발 POST 라 끊어도 서버 생성은 끝까지 돌고 결과만 버려져, 돌아오면 다시 만든다.
    // 응답이 오면 시작 때 붙잡은 id 로 저장되고(떠난 뒤에 와도), 같은 기록의 요청이 도는 중이면 새로 부르지 않고 이어받는다.
    // 타이핑은 화면 연출로만 둔다 — 떠났거나 다른 묶음이 시작됐으면 화면만 건너뛴다
    const result = await curationRequests.run(historyId, {
      query,
      book_ids: topBooks.map((b) => b.book_id),
      scores: topBooks.map((b) => b.best_score || 0),
      rewritten_query: rewritten,
    });
    if (signal.aborted || !result) return;
    curation.value = result.data;
    curationLoading.value = false;
    const { intro, items } = result;
    if (intro) {
      curationOpen.value = true;
      await typeInto(curationIntro, intro, signal);
      if (signal.aborted) return;
    }
    curationItems.value = items;
    curationTyping.value = false;
  } catch {
    /* 큐레이션 실패 시 조용히 무시 */
  } finally {
    if (!signal.aborted) {
      curationLoading.value = false;
      curationTyping.value = false;
    }
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
// 논문 상세의 출처는 결과의 검색어로 싣는다(입력창 글자가 아니다). 이 화면의 기록은 도서 기록이라 h 로 싣지 않는다 —
// [검색 결과로]가 논문 검색에서 같은 검색어로 다시 찾는다
function paperDetailUrl(bookId: string, extra: Record<string, string> = {}): string {
  return detailUrl(bookId, { kind: "search", h: null, q: resultQuery.value }, undefined, extra);
}

function openDetail(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(paperDetailUrl(item.book_id));
    return;
  }
  // q 는 입력창이 아니라 화면 결과의 검색어다 — 함께 넘기는 h 와 같은 검색을 가리키게
  const params = new URLSearchParams({
    q: resultQuery.value,
    score: String(item.best_score || 0),
  });
  // 상세에서도 사이드바가 이 기록을 강조하고, 뒤로가기가 재검색 없이 복원되게
  if (currentHistoryId.value) params.set("h", currentHistoryId.value);
  if (item.title_score !== undefined)
    params.set("title_score", String(item.title_score));
  if (item.content_score !== undefined)
    params.set("content_score", String(item.content_score));
  navigateTo(`/books/${item.book_id}?${params}`);
}

// 이 책과 대화하기 → detail + chat 자동 오픈
function openDetailWithChat(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(paperDetailUrl(item.book_id, { chat: "1" }));
    return;
  }
  const params = new URLSearchParams({
    q: resultQuery.value,
    score: String(item.best_score || 0),
    chat: "1",
  });
  if (currentHistoryId.value) params.set("h", currentHistoryId.value);
  if (item.title_score !== undefined)
    params.set("title_score", String(item.title_score));
  if (item.content_score !== undefined)
    params.set("content_score", String(item.content_score));
  navigateTo(`/books/${item.book_id}?${params}`);
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
