<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <!-- ===== LANDING VIEW ===== -->
    <main v-if="view === 'landing'" class="skx-contents">
      <div class="skx-contents__inner">
        <h1 class="skx-brand">
          <span class="skx-brand__line">넓게 찾고 깊게 확인하는, 도서관의 AI 탐색</span>
          <SkovixWordmark class="skx-brand__logo" />
        </h1>

        <!-- 두 갈래 전환: 자료 검색 · 논문 검색. 딥리서치는 갈래가 아니라 논문 패널의 + 메뉴·슬래시 명령 모드다 -->
        <div
          class="skx-seg"
          role="tablist"
          aria-label="검색 유형"
          :style="{ '--seg-i': String(tabIndex), '--seg-n': String(LANDING_TABS.length) }"
          @keydown="onTabsKeydown"
        >
          <span class="skx-seg__thumb" aria-hidden="true"></span>
          <button
            v-for="t in LANDING_TABS"
            :id="`skx-tab-${t.id}`"
            :key="t.id"
            type="button"
            :class="['skx-seg__btn', mode === t.id && 'is-active']"
            role="tab"
            :aria-selected="mode === t.id"
            :aria-controls="t.id === 'book' ? 'skx-panel-book' : 'skx-panel-paper'"
            :tabindex="mode === t.id ? 0 : -1"
            @click="selectTab(t.id)"
          >
            <span class="skx-seg__full">{{ t.label }}</span>
            <span class="skx-seg__short">{{ t.shortLabel }}</span>
          </button>
        </div>

        <!-- 소장자료 패널 -->
        <div
          id="skx-panel-book"
          class="skx-panel"
          role="tabpanel"
          aria-labelledby="skx-tab-book"
          :hidden="mode !== 'book'"
        >
          <div class="skx-search">
            <div class="skx-search__box">
              <label class="skx-search__field">
                <span class="skx-sr-only">자료 검색어</span>
                <textarea
                  ref="bookInputRef"
                  class="skx-search__input"
                  v-model="currentQuery"
                  placeholder="찾고싶은 도서를 문장으로 검색해보세요!"
                  :disabled="loading"
                  @keydown.enter.exact="onSearchEnter"
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
                  <img class="skx-chip__icon" src="/img/ico-bubbles.svg" alt="" />
                  <span>{{ chip }}</span>
                </button>
              </li>
            </ul>
            <NuxtLink class="skx-reco-link" to="/recommend">
              <span>내 상황에 맞는 도서 추천받기</span>
              <img src="/img/ico-arrow.svg" alt="" />
            </NuxtLink>
          </div>
        </div>

        <!-- 논문 패널 — 딥리서치는 이 입력창에서 + 메뉴의 딥리서치 모드를 켠 상태(켜져 있어도 전환은 '논문 검색') -->
        <div
          id="skx-panel-paper"
          class="skx-panel"
          role="tabpanel"
          aria-labelledby="skx-tab-paper"
          :hidden="mode !== 'paper'"
        >
          <div class="skx-search">
            <div class="skx-search__box">
              <ResearchSearchPlusMenu
                ref="plusMenu"
                v-model="currentQuery"
                kind="paper"
                :disabled="loading"
                @update:mode="onPlusMode"
              />
              <label class="skx-search__field">
                <span class="skx-sr-only">논문 검색어</span>
                <textarea
                  ref="paperInputRef"
                  class="skx-search__input"
                  v-model="currentQuery"
                  placeholder="찾고싶은 논문을 문장으로 검색해보세요!"
                  :disabled="loading"
                  @keydown.enter.exact="onSearchEnter"
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
                  <img class="skx-chip__icon" src="/img/ico-bubbles.svg" alt="" />
                  <span>{{ chip }}</span>
                </button>
              </li>
            </ul>
            <!-- 논문 필터 드롭다운 — 딥리서치 모드에서는 쓰지 않아 숨긴다(고른 값은 그대로 두어 논문 검색으로 돌아오면 보인다) -->
            <div v-if="!deepResearch" class="skx-filters">
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
        <section v-if="SHOW_MOCKS" class="skx-newbooks">
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
          @keydown.enter="onSearchEnter"
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
          <!-- AI 섹션 (도서) — SKOVIX 추천 1권 + 왜 이 책인가 + 이 책에서 얻을 수 있는 것 -->
          <section v-if="mode === 'book' && topBook" class="skx-ai-section">
            <header class="skx-ai-header">
              <h2 class="skx-ai-header__title">AI 검색 결과</h2>
              <p v-if="keywordChips.length" class="skx-ai-header__keywords">
                키워드: {{ keywordChips.join(", ") }}
              </p>
            </header>
            <div v-if="topRecommended" class="skx-pick">
              <!-- 왼쪽 글은 일정 높이(16rem)까지만 보이고 넘치면 아래가 흐려지며 [더보기]/[접기] — 스트리밍 중에도 같다 -->
              <ClampedPanel
                v-model:expanded="aiExpanded"
                class="skx-pick__main"
                :collapsed-rem="16"
                scroll-anchor=".skx-ai-section"
              >
                <div class="skx-pick__body">
                  <section
                    class="skx-pick__block"
                    aria-labelledby="skx-pick-why"
                    :aria-busy="reasonPending"
                  >
                    <h3 id="skx-pick-why" class="skx-pick__heading">
                      <span class="skx-ai-dot" aria-hidden="true"></span>
                      왜 이 책인가
                    </h3>
                    <p v-if="reasonText" class="skx-pick__text">
                      {{ reasonText
                      }}<span
                        v-if="reasonPending"
                        class="skx-ai-answer__cursor"
                        aria-hidden="true"
                      ></span>
                    </p>
                    <p
                      v-else-if="reasonPending"
                      class="skx-pick__text skx-pick__text--muted"
                      role="status"
                    >
                      AI 사서가 추천 이유를 정리하고 있어요…
                    </p>
                    <p
                      v-else-if="reasonStatus === 'error'"
                      class="skx-pick__text skx-pick__text--muted"
                      role="status"
                    >
                      추천 이유를 불러오지 못했어요.
                      <button type="button" class="skx-pick__retry" @click="retryTopReason">다시 시도</button>
                    </p>
                    <p
                      v-if="reasonStatus === 'interrupted'"
                      class="skx-pick__text skx-pick__text--muted"
                      role="status"
                    >
                      중간에 끊겼어요 ·
                      <button type="button" class="skx-pick__retry" @click="retryTopReason">다시 시도</button>
                    </p>
                  </section>
                  <section
                    v-if="topReadEffect"
                    class="skx-pick__block"
                    aria-labelledby="skx-pick-effect"
                  >
                    <h3 id="skx-pick-effect" class="skx-pick__heading">
                      이 책에서 얻을 수 있는 것
                    </h3>
                    <p class="skx-pick__text">{{ topReadEffect }}</p>
                  </section>
                </div>
              </ClampedPanel>
              <aside class="skx-pick__book" aria-label="SKOVIX 추천 1권">
                <span class="skx-pick__label">SKOVIX 추천 1권</span>
                <article class="skx-pick__card" @click="openDetail(topBook)">
                  <div class="skx-pick__card-head">
                    <div class="skx-book-card__thumb">
                      <BookCover :book-id="topBook.book_id" />
                    </div>
                    <div class="skx-book-card__body">
                      <div class="skx-book-card__tags">
                        <RelevanceBadge
                          :score="topBook.best_score"
                          :title-score="topBook.title_score"
                          :content-score="topBook.content_score"
                        />
                      </div>
                      <!-- 카드 전체 클릭은 마우스용이다 — 키보드는 제목 버튼으로 상세를 연다 -->
                      <h3 class="skx-book-card__title">
                        <button type="button" class="skx-pick__title-btn" @click.stop="openDetail(topBook)">
                          {{ topBook.book_info?.title || topBook.book_id }}
                        </button>
                      </h3>
                      <div class="skx-book-card__info-row">
                        <template v-for="(part, pi) in topMeta" :key="pi">
                          <span v-if="pi > 0" class="skx-dot"></span>
                          <span class="skx-meta-text">{{ part }}</span>
                        </template>
                      </div>
                    </div>
                  </div>
                  <div class="skx-book-card__actions" @click.stop>
                    <button
                      type="button"
                      class="skx-btn-chat"
                      @click="openDetailWithChat(topBook)"
                    >
                      <img src="/img/ico-chat.svg" alt="" />
                      <span class="skx-btn-chat__label">DeepRead</span>
                    </button>
                    <button
                      type="button"
                      class="skx-btn-read"
                      @click="viewPdf(topBook)"
                    >
                      원문 보기
                    </button>
                  </div>
                </article>
              </aside>
            </div>
            <!-- 1위 도서도 질문과 거리가 멀면 추천하지 않고 목록만 안내한다(추천 이유도 부르지 않는다) -->
            <div v-else class="skx-pick skx-pick--notice">
              <p class="skx-pick__text skx-pick__text--muted" role="status">
                질문과 딱 맞는 자료를 찾지 못했어요 — 아래 목록을 확인해 주세요.
              </p>
            </div>
            <!-- 06d: [딥리서치로 더 깊게]·[담기] 는 이 패널 바로 아래(이 자리)에 들어간다 — 그때까지 DOM 을 만들지 않는다 -->
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
                    <RelevanceBadge
                      :score="item.best_score"
                      :title-score="item.title_score"
                      :content-score="item.content_score"
                    />
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
                    v-if="SHOW_MOCKS"
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

          <!-- 더보기 버튼 (처음 보이는 개수보다 결과가 많을 때만) -->
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
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { slimBookResult } from "~/utils/historySnapshot";
import {
  buildBookAi,
  buildReasonBody,
  isRecommendable,
  pickTopBook,
  readEffectOf,
  readReasonStream,
  readSavedKeywords,
  readSavedReason,
} from "~/utils/bookAiPick";
import { readV1Map } from "~/utils/historyStore";
import { awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import { detailUrl } from "~/utils/detailSource";
import { DEFAULT_LANDING_TAB, LANDING_TABS, landingTabStep, type LandingTab } from "~/utils/landingTabs";
import { queryWithoutStart, readStart } from "~/utils/landingStart";
import type { SearchModeId } from "~/utils/slashCommand";
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
// 처음 열 때의 갈래는 전환의 첫 칸(논문 검색)이다
const mode = ref<"book" | "paper">(DEFAULT_LANDING_TAB);

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

// ── SKOVIX 추천 1권 (도서 AI 영역) ──────────────────────────
// 1위 도서 한 권과, 그 책이 이 검색어에 왜 맞는지(/books/reason/stream 스트리밍)·읽으면 얻는 것(검색 응답의 read_effect).
// 이유 스트림은 검색·복원·랜딩 복귀·페이지 이탈이 공유하는 묶음 signal 로 끊는다.
// 상태: idle(아직 없음) · loading(받는 중) · done(끝까지 받음) · error(글 없이 실패) · interrupted(받다가 끊겨 글이 일부만 있음)
const reasonRaw = ref("");
const reasonStatus = ref<"idle" | "loading" | "done" | "error" | "interrupted">("idle");
let reasonSignal: AbortSignal | null = null;
// 스트림 첫 글자는 줄바꿈이라 앞뒤 공백을 뗀다
const reasonText = computed(() => reasonRaw.value.trim());
const reasonPending = computed(() => reasonStatus.value === "loading");

// ── 결과 펼치기/접기 ──────────────────────────────────────
const bookListExpanded = ref(false);
const aiExpanded = ref(false);

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
// 검색·복원·추천 이유 스트림을 한 묶음으로 끊는다 — 새 검색이나 복원·랜딩 복귀·페이지 이탈이 오면 이전 묶음의
// 응답·스트림·저장이 새 화면과 새 기록을 덮지 못하게 한다(이유 스트림은 연결째 끊겨 서버 생성도 멈춘다)
let runCtrl: AbortController | null = null;
function beginRun(): AbortSignal {
  runCtrl?.abort();
  runCtrl = new AbortController();
  return runCtrl.signal;
}

// ── Publishing additions ──────────────────────────────────────
// 두 갈래 전환 — 갈래는 데이터 모드(mode)와 같다(도서/논문). 딥리서치는 논문 패널에서 + 메뉴·슬래시 명령으로 켜는 모드라
// 켜져 있어도 전환은 '논문 검색'이다. 켜짐 여부의 정본은 + 메뉴(SearchPlusMenu)다 — 어디서 켜고 꺼도 메뉴가 update:mode 로
// 알려 deepResearch 가 따라온다. 이 값은 KCI 등재 필터를 숨기는 데 쓴다
const deepResearch = ref(false);
const plusMenu = ref<{
  activateMode: (id: SearchModeId, options?: { focus?: boolean }) => void;
  clearMode: () => void;
} | null>(null);
const tabIndex = computed(() => LANDING_TABS.findIndex((t) => t.id === mode.value));

function onPlusMode(id: SearchModeId | null) {
  deepResearch.value = id === "deep-research";
}

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

// 갈래를 고른다. 초점은 옮기지 않는다 — 방향키로 갈래를 옮기는 중이거나 모바일에서 갈래만 바꿀 때 입력창·키보드가 끼어들지 않게.
// 자료 검색으로 가면 논문 패널에 켜 둔 딥리서치 모드는 끈다(숨은 패널에 칩이 남지 않게)
function selectTab(next: LandingTab) {
  if (next === mode.value) return;
  mode.value = next;
  if (next === "book" && deepResearch.value) dropDeepResearch();
}

// 딥리서치 모드를 끈다. 화면 상태(deepResearch)도 바로 내린다 — 같은 틱에 랜딩이 걷히면(자료 검색 기록 복원)
// 메뉴가 unmount 돼 update:mode 가 오지 않을 수 있고, 그러면 돌아온 논문 패널에 딥리서치 상태가 남는다
function dropDeepResearch() {
  deepResearch.value = false;
  plusMenu.value?.clearMode();
}

// 기록 복원처럼 코드가 자료 검색 화면으로 돌릴 때 — 딥리서치 모드도 함께 끈다
function showBookMode() {
  mode.value = "book";
  if (deepResearch.value) dropDeepResearch();
}

// 사이드바 [+ 연구 시작하기](?start=deep-research) — 랜딩의 논문 패널에 딥리서치 모드를 켜고 입력창에 초점을 준다.
// 결과 화면이었다면 랜딩으로 걷는다. 처리한 뒤 주소에서 start 만 지운다(남기면 새로고침마다 다시 켜진다).
// 이미 '/' 에 있어도 쿼리가 바뀌므로 watch 가 같은 길로 받는다
async function startFromQuery() {
  if (route.path !== "/" || !readStart(route.query)) return;
  void router.replace({ query: queryWithoutStart(route.query) });
  if (view.value !== "landing") goLanding();
  mode.value = "paper";
  // 논문 패널이 보인 뒤에 켠다 — 숨은 패널의 입력창에는 초점이 가지 않는다
  await nextTick();
  plusMenu.value?.activateMode("deep-research");
}

// tablist 키보드: 좌우·Home·End 로 갈래를 옮기고(자동 선택) 초점도 그 갈래로 따라간다
function onTabsKeydown(e: KeyboardEvent) {
  const next = landingTabStep(mode.value, e.key, e);
  if (!next) return;
  e.preventDefault();
  selectTab(next);
  document.getElementById(`skx-tab-${next}`)?.focus();
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
  // 첫 복원을 setup 이 아니라 마운트 뒤에 한다 — 서버가 그린 랜딩과 하이드레이션이 어긋나지 않게
  restoreFromQuery();
  void startFromQuery();

  // Newbooks countup — 신작도서 블록이 숨겨져 있으면(SHOW_MOCKS=false) 보이지 않는 숫자를 돌리지 않는다
  if (SHOW_MOCKS) {
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
  }

  document.addEventListener("click", onDocClick);
});

onUnmounted(() => {
  // 떠난 화면에 늦게 온 응답이 상태를 고치지 않게, 진행 중인 검색·추천 이유 스트림을 끊는다
  runCtrl?.abort();
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
  resetReason();
  bookListExpanded.value = false;
  aiExpanded.value = false;
  paperSummaryText.value = "";
  view.value = "results";

  try {
    const data = await api<any>("/books/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 10,
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
    // 기록 저장을 기다리는 동안에도 빈 칸 대신 '정리하는 중'이 보이게 스트림 시작 전에 미리 받는 중으로 둔다
    if (isRecommendable(pickTopBook(books.value))) reasonStatus.value = "loading";

    // 기록 id 를 먼저 확정해 추천 이유 스트림에 넘긴다 — 끝난 뒤 저장이 그 사이 바뀐 화면의 기록을 덮지 않게
    const snapshot = slimBookResult(data) ?? undefined;
    const entry = reuse
      ? ((await historyApi.patch(reuse.id, { snapshot })) ?? reuse)
      : await historyApi.add({ kind: "book", title: query.trim(), params: {}, snapshot });
    if (signal.aborted) return;
    currentHistoryId.value = entry.id;
    router.replace({ query: { q: query.trim(), h: entry.id } });
    void streamTopReason(entry.id, query.trim(), signal);
  } catch (e: any) {
    if (signal.aborted) return;
    searchError.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
  } finally {
    if (!signal.aborted) loading.value = false;
  }
}

// 입력창의 엔터는 검색이다. 한글 조합 중의 엔터는 글자 확정용이라 검색하지 않는다(SearchPlusMenu 와 같은 관례) —
// 안 막으면 마지막 글자가 빠진 채 검색이 나가거나 두 번 나간다
function onSearchEnter(e: KeyboardEvent) {
  e.preventDefault();
  if (e.isComposing) return;
  void handleSearch(currentQuery.value);
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

// 랜딩으로 되돌린다 — 진행 중인 검색·복원·추천 이유 스트림 묶음을 끊고 결과 화면 상태를 비운다
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
  resetReason();
  selectedItem.value = null;
  pdfOpen.value = false;
  citationModal.value = false;
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
      showBookMode();
      await handleSearch(q);
    }
    return;
  }
  if (h === currentHistoryId.value) {
    settleReason();
    return;
  }

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
    showBookMode();
    await handleSearch(retryQuery, book ?? undefined);
    return;
  }
  // 이 복원이 beginRun 으로 끊은 이유 스트림이 이어받을 화면 없이 끝나는 길 — '정리하는 중'으로 굳지 않게 매듭짓는다
  settleReason();
  showToast("없는 기록입니다. 목록을 새로 고쳤습니다.");
}

function applyBookEntry(entry: BookEntry, signal: AbortSignal) {
  const snap = entry.snapshot as BookSnapshot;
  showBookMode();
  view.value = "results";
  loading.value = false;
  searchError.value = "";
  currentQuery.value = entry.title;
  resultQuery.value = entry.title;
  currentHistoryId.value = entry.id;
  rewrittenQuery.value = snap.rewritten_query || entry.title;
  books.value = snap.books as unknown as BookChunkGroup[];
  papers.value = [];
  resetReason();
  bookListExpanded.value = false;
  aiExpanded.value = false;
  if (route.query.h !== entry.id || route.query.q !== entry.title) {
    router.replace({ query: { q: entry.title, h: entry.id } });
  }
  // 저장된 추천 이유가 있으면 그대로 보이고 다시 받지 않는다. 없으면(끝나기 전에 떠났거나 실패한 기록, 옛 AI 컬렉션
  // {intro, items} 기록) 한 번 다시 받고, 끝나면 새 모양으로 덮어 다음부터는 저장분을 쓴다
  const topId = topBook.value?.book_id ?? null;
  const saved = readSavedReason(entry.ai, topId);
  if (saved) {
    reasonRaw.value = saved;
    reasonStatus.value = "done";
    keywordChips.value = readSavedKeywords(entry.ai, topId);
  } else {
    void streamTopReason(entry.id, entry.title, signal);
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
// 사이드바 [+ 연구 시작하기] 는 '/' 에 이미 있어도 ?start= 만 바뀌는 이동이다
watch(
  () => route.query.start,
  () => {
    void startFromQuery();
  },
);

// ── 결과 목록 ─────────────────────────────────────────────
// 도서는 검색이 준 순서 그대로다(AI 영역의 1위 도서도 이 목록의 첫 카드). 처음에는 3건만 보이고 나머지는 더보기로 연다
const visibleCount = 3;

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
  return books.value;
});

// ── SKOVIX 추천 1권 (도서 AI 영역) ──────────────────────────
const topBook = computed(() => pickTopBook(books.value));
// 1위가 추천할 만큼 맞을 때만 추천 패널을 낸다(MIN_PICK_SCORE) — 아니면 안내만
const topRecommended = computed(() => isRecommendable(topBook.value));
const topReadEffect = computed(() => readEffectOf(topBook.value));
// 저자 · 출판사 · 발행년 — 있는 것만
const topMeta = computed(() => {
  const info = topBook.value?.book_info;
  if (!info) return [];
  const year = info.pub_date ? `${info.pub_date.slice(0, 4)}년` : "";
  return [info.personal_author || info.corporate_author, info.publisher, year].filter(
    (v): v is string => !!v,
  );
});

function resetReason() {
  reasonRaw.value = "";
  reasonStatus.value = "idle";
  keywordChips.value = [];
}

// 이 묶음이 끊겼는데 이어받는 새 묶음이 없을 때(없는 기록 토스트 등) 받는 중 표시가 남지 않게 매듭짓는다 —
// 받은 글이 있으면 끊긴 글, 없으면 실패. 끊기지 않은 스트림은 건드리지 않는다
function settleReason() {
  if (reasonStatus.value !== "loading" || !reasonSignal?.aborted) return;
  reasonStatus.value = reasonText.value ? "interrupted" : "error";
}

// [다시 시도] — 지금 결과의 1위 도서로 추천 이유를 처음부터 다시 받는다
function retryTopReason() {
  const signal = beginRun();
  void streamTopReason(currentHistoryId.value, resultQuery.value, signal);
}

// 1위 도서의 추천 이유를 받는다. 기록 id 와 검색어도 호출하는 쪽이 붙잡아 넘긴다 — 입력창(currentQuery)은 사용자가
// 고치는 중일 수 있어, 지금 값을 읽으면 다른 검색어로 만든 이유가 이 기록에 저장된다.
// signal 이 끊기면(새 검색·복원·랜딩·이탈) 연결째 끊고 화면·기록 어디도 건드리지 않는다.
// 끝까지 받은 이유만 저장한다 — 받다가 끊기면(interrupted) 받은 글은 보이되 저장하지 않는다
async function streamTopReason(
  historyId: string | null,
  query: string,
  signal: AbortSignal,
) {
  const book = pickTopBook(books.value);
  if (!book || !isRecommendable(book)) return;
  reasonSignal = signal;
  reasonRaw.value = "";
  keywordChips.value = [];
  reasonStatus.value = "loading";
  let complete = false;
  let keywords: string[] = [];
  try {
    const resp = await fetch(apiUrl("/books/reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(buildReasonBody(query, book)),
      signal,
    });
    if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);
    complete = await readReasonStream(
      resp.body,
      (delta) => {
        if (!signal.aborted) reasonRaw.value += delta;
      },
      (kw) => {
        if (signal.aborted) return;
        keywords = kw;
        keywordChips.value = kw;
      },
    );
  } catch {
    /* 실패·중단 — 아래에서 가린다 */
  }
  if (signal.aborted) return;
  const reason = reasonRaw.value.trim();
  if (!reason) {
    reasonStatus.value = "error";
    return;
  }
  if (!complete) {
    reasonStatus.value = "interrupted";
    return;
  }
  reasonStatus.value = "done";
  if (historyId) {
    void historyApi
      .patch(historyId, { ai: buildBookAi(book.book_id, reason, keywords) })
      .catch(() => undefined);
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
