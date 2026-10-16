<template>
  <div class="skx-app" :style="examplesOverflow ? { marginBottom: `${examplesOverflow}px` } : undefined">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <!-- ===== LANDING VIEW ===== -->
    <main v-if="view === 'landing'" ref="contentsRef" class="skx-contents">
      <div ref="contentsInnerRef" class="skx-contents__inner">
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
              <span class="skx-search__glow" aria-hidden="true"></span>
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
                  :aria-disabled="!hasQuery(currentQuery)"
                  @click="handleSearch(currentQuery)"
                >
                  <img src="/img/ico-send-up.svg" alt="" />
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
              <span class="skx-search__glow" aria-hidden="true"></span>
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
                  :aria-disabled="!hasQuery(currentQuery)"
                  @click="handleSearch(currentQuery)"
                >
                  <img src="/img/ico-send-up.svg" alt="" />
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
            <!-- 자료 검색 패널의 '도서 추천받기' 링크 자리 — 두 패널 높이를 같게 해 갈래를 바꿔도 전환·입력창이 움직이지 않게 비워 둔다(보이지 않고 눌리지도 않는다) -->
            <span class="skx-reco-link skx-reco-link--ghost" aria-hidden="true">
              <span>내 상황에 맞는 도서 추천받기</span>
              <img src="/img/ico-arrow.svg" alt="" />
            </span>
          </div>
          <!-- DeepResearch 모드일 때 예시 연구 카드(미리 돌린 실제 연구 — 읽기 전용). 예시가 없으면 그리지 않는다.
               패널 아래에 띄워(.skx-panel__float) 세로 가운데 정렬 계산에서 뺀다 — 모드를 켜고 꺼도 로고·전환·입력창이 제자리다 -->
          <div v-if="deepResearch" ref="examplesRef" class="skx-panel__float">
            <ResearchExampleCards />
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
                    :src="SPINNER_SRC"
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
          :aria-disabled="!hasQuery(currentQuery)"
          :disabled="loading"
          @click="handleSearch(currentQuery)"
        >
          <img src="/img/ico-send-up.svg" alt="" />
        </button>
      </div>

      <div
        v-if="loading"
        class="skx-rframe"
        style="padding: 40px; text-align: center"
      >
        <img :src="SPINNER_SRC" alt="" style="width: 32px" />
        <p style="margin-top: 12px">AI가 도서를 검색 중입니다...</p>
      </div>

      <div
        v-else-if="searchError"
        class="skx-rframe"
        style="padding: 20px; color: #c00"
      >
        {{ searchError }}
      </div>

      <div v-else class="skx-rframe">
        <!-- AI 검색 결과 — SKOVIX 추천 1권 + 왜 이 책인가 + 이 책에서 얻을 수 있는 것. 틀은 논문 결과와 같은 AiResultPanel -->
        <AiResultPanel v-if="topBook && topRecommended" :loading="reasonPending" hint>
            <!-- 왼쪽 글은 일정 높이(16rem)까지만 보이고 넘치면 아래가 흐려지며 [더보기]/[접기] — 스트리밍 중에도 같다 -->
            <ClampedPanel
              v-model:expanded="aiExpanded"
              class="skx-pick__main"
              :collapsed-rem="16"
              scroll-anchor=".skx-aip"
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
            <!-- 아래 목록 카드와 같은 해부도. 키워드 칩은 이 책 자신의 키워드가 먼저이고, 없을 때만 추천 이유 스트림이 준 키워드 -->
            <ResultCard
              :item="topBook"
              kind="book"
              compact
              badge="AI 추천"
              :fallback-keywords="keywordChips"
              @open="openDetail(topBook)"
              @chat="openDetailWithChat(topBook)"
              @pdf="viewPdf(topBook)"
            />
          </aside>
        </AiResultPanel>
        <!-- 1위 도서도 질문과 거리가 멀면 추천하지 않고 목록만 안내한다(추천 이유도 부르지 않는다) -->
        <AiResultPanel v-else-if="topBook">
          <p class="skx-aip__notice" role="status">
            질문과 딱 맞는 자료를 찾지 못했어요 — 아래 목록을 확인해 주세요.
          </p>
        </AiResultPanel>
        <!-- 이 결과에서 이어서 — [DeepResearch로 이어서 조사하기]는 메인 입력창에 이 검색어를 채우고 DeepResearch 모드를 켠다(시작은
             하지 않는다 — 논문 결과의 같은 버튼과 같은 모양) -->
        <div v-if="topBook && resultQuery" class="skx-deeper">
          <button type="button" class="skx-deeper__btn" @click="continueAsDeepResearch">
            <span aria-hidden="true">+</span> {{ DEEP_RESEARCH }}로 이어서 조사하기
          </button>
        </div>

        <!-- 도서 목록 — 추천 1권을 내세웠으면 그 책은 위 패널에 있으니 빼고 '그 외 총 N 건'. 정렬·개수·쪽은 이 나머지 목록에만 적용된다 -->
        <section
          v-if="listBooks.length"
          ref="listRef"
          class="skx-rlist"
          aria-label="소장자료 검색 결과 목록"
        >
          <ResultListHead :count="listBooks.length" :prefix="listExcludesPick ? '그 외 ' : ''">
            <ResultSortControls
              :sort-by="sortBy"
              :page-size="pageSize"
              @sort="setSortBy"
              @size="setPageSize"
            />
          </ResultListHead>
          <div class="skx-book-list">
            <ResultCard
              v-for="item in pagedBooks"
              :key="item.book_id"
              :item="item"
              kind="book"
              @open="openDetail(item)"
              @chat="openDetailWithChat(item)"
              @pdf="viewPdf(item)"
            />
          </div>

          <!-- 쪽 이동 -->
          <ResultPager :page="currentPage" :total="totalPages" @go="goToPage" />
        </section>
      </div>
    </main>

    <!-- PdfViewer, Toast -->
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
import { useBookmark } from "~/composables/useBookmark";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
import ResearchExampleCards from "~/components/research/ResearchExampleCards.vue";
import { useResearchExamples } from "~/composables/useResearchWorks";
import { safeLocalStorage } from "~/utils/browserId";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { slimBookResult } from "~/utils/historySnapshot";
import {
  buildBookAi,
  buildReasonBody,
  isRecommendable,
  listWithoutPick,
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
import { deepResearchStartRoute, queryWithoutStart, readStart, readStartDraft } from "~/utils/landingStart";
import { usePageLeaving } from "~/composables/usePageLeaving";
import { DEEP_RESEARCH } from "~/utils/brand";
import type { SearchModeId } from "~/utils/slashCommand";
import type { BookChunkGroup } from "~/types/search";
import type { BookEntry, BookSnapshot } from "~/types/history";
import { hasQuery } from "~/utils/searchInput";
import { detailScoreParams } from "~/utils/relevance";
import {
  DEFAULT_SORT,
  clampPage,
  pageCount,
  pageSlice,
  sortResults,
  type ListView,
  type PageSize,
  type SortKey,
} from "~/utils/resultPaging";
import { rememberListView, savedListView } from "~/composables/useListView";
import { SPINNER_SRC } from "~/utils/brand";

// ── 상수 ──────────────────────────────────────────────────
// 예시 질의는 운영 검색으로 고른 것이다(2026-10-08 — 후보마다 상위 결과를 판정자 둘 이상이 따로 봤다).
// 도서 소장 자료는 국문학 학위논문(1983~1997)·정부 재정·경제 보고서 쪽에 몰려 있어 교양서를 기대하는 질의
// (경제 일반·기후·진로 등)는 결과가 흩어진다. 논문은 + 메뉴로 딥리서치를 시작할 때도 쓰인다.
// 주제는 그대로 두고 말투만 섞었다(2026-10-16 — 여섯 개가 '~찾아줘'·'~궁금해' 둘뿐이었다). 말투 후보를 화면과 같은
// 인자로 운영 검색에 넣어 상위 10건을 판정자 셋이 블라인드로 매겨, 지금 문장보다 낮지 않은 것만 골랐다 — 논문 검색은
// 재작성하지 않아 질문형이 오히려 잘 찾는다. '중기 재정 운용 계획…'은 도서 재작성이 '중소기업'으로 풀어 뺐다.
// 논문 문장은 딥리서치로도 옛 문장과 같은 날 함께 돌려 문장 감사를 했다 — 공공도서관은 검색 점수가 가장 높던 '…평가 지표'
// (명사구)가 하위질문을 '…지표의 개념/측정…' 틀로 찍어 근거와 맞는 문장이 65% 로 가장 낮아 '…어떻게 평가할까?'(76%)로 했다.
// 근거: research/landing-example-queries
const SUGGESTIONS: Record<string, string[]> = {
  book: [
    "조선시대 고전소설을 연구한 자료 찾아줘",
    "국가 재정 운용 계획은 어떻게 세워지나요?",
    "김소월과 한용운의 시를 연구한 자료",
  ],
  paper: [
    "노인의 사회적 지지가 우울에 미치는 영향은?",
    "다문화가정 아동의 언어 발달은 또래와 어떻게 다를까?",
    "공공도서관 서비스 품질은 어떻게 평가할까?",
  ],
};

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;
const api = useApi();
const route = useRoute();
const router = useRouter();
// 결과를 그린 뒤 기록 저장을 기다리는 사이 상세로 떠나면 늦은 주소 바꾸기가 그 이동을 취소하지 않게
const { leaving } = usePageLeaving();

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

// ── 추천 패널 펼치기/접기 ─────────────────────────────────
const aiExpanded = ref(false);

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
// 알려 deepResearch 가 따라온다. 이 값은 자료 검색으로 옮길 때 켜 둔 모드를 끄는 데 쓴다
const deepResearch = ref(false);
const plusMenu = ref<{
  activateMode: (id: SearchModeId, options?: { focus?: boolean }) => void;
  clearMode: () => void;
} | null>(null);
const tabIndex = computed(() => LANDING_TABS.findIndex((t) => t.id === mode.value));

function onPlusMode(id: SearchModeId | null) {
  deepResearch.value = id === "deep-research";
}

// DeepResearch 예시 연구 카드는 패널 아래에 띄워(.skx-panel__float) 세로 가운데 정렬 계산에서 뺀다 — 갈래 전환의 유령 링크처럼
// 모드를 켜고 꺼도 로고·전환·입력창이 제자리다(사용자 요청 2026-10-16). 띄운 카드는 페이지를 늘리지 않으므로, 본문 아래 여백선을 넘는
// 만큼을 재어 .skx-app 의 아래 바깥 여백으로 둔다 — 페이지가 그만큼 길어져 스크롤로 닿고 푸터와 겹치지 않는다. 바깥 여백은
// .skx-app 높이(가운데 정렬의 기준)를 바꾸지 않아, 다시 재도 같은 값이다(되먹임 없음)
const contentsRef = ref<HTMLElement | null>(null);
const contentsInnerRef = ref<HTMLElement | null>(null);
const examplesRef = ref<HTMLElement | null>(null);
const examplesOverflow = ref(0);
let examplesObserver: ResizeObserver | null = null;

function measureExamplesOverflow() {
  const box = examplesRef.value;
  const main = contentsRef.value;
  if (!box || !main) {
    examplesOverflow.value = 0;
    return;
  }
  const padBottom = parseFloat(getComputedStyle(main).paddingBottom) || 0;
  const over = box.getBoundingClientRect().bottom + padBottom - main.getBoundingClientRect().bottom;
  examplesOverflow.value = Math.max(0, Math.ceil(over));
}

// 카드가 서고 바뀔 때(목록 도착·폭에 따른 줄바꿈), 창 높이가 바뀔 때(본문), 입력창 쪽 높이가 바뀔 때(가운데 자리가 움직여 카드도 따라
// 움직인다) 다시 잰다. 카드가 사라지면(모드 끔·화면 이동) 여백을 걷는다
watch(
  examplesRef,
  (box) => {
    examplesObserver?.disconnect();
    examplesObserver = null;
    if (!box || typeof ResizeObserver === "undefined") {
      examplesOverflow.value = 0;
      return;
    }
    examplesObserver = new ResizeObserver(measureExamplesOverflow);
    for (const el of [box, contentsRef.value, contentsInnerRef.value]) if (el) examplesObserver.observe(el);
  },
  { flush: "post" },
);

// DeepResearch 모드의 예시 연구 카드 재료를 랜딩이 뜰 때 미리 읽어 둔다(앱에서 한 번 — useState). 모드를 켠 뒤에야 읽기 시작하면
// 응답이 온 뒤에 카드가 서서, 세로 가운데 정렬인 랜딩의 입력창이 사용자가 막 쓰기 시작한 때 비동기로 밀린다(P5 리뷰)
const { load: loadResearchExamples } = useResearchExamples();

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
// 결과 화면이었다면 랜딩으로 걷는다. 처리한 뒤 주소에서 start·draft 를 지운다(남기면 새로고침마다 다시 켜진다).
// 이미 '/' 에 있어도 쿼리가 바뀌므로 watch 가 같은 길로 받는다
async function startFromQuery() {
  if (route.path !== "/" || !readStart(route.query)) return;
  // 소장자료 결과의 [DeepResearch로 이어서 조사하기]가 실은 질문 초안 — 주소에서 지우기 전에 읽는다
  const draft = readStartDraft(route.query);
  void router.replace({ query: queryWithoutStart(route.query) });
  if (view.value !== "landing") goLanding();
  mode.value = "paper";
  if (draft) currentQuery.value = draft;
  // 논문 패널이 보인 뒤에 켠다 — 숨은 패널의 입력창에는 초점이 가지 않는다. 초안이 있으면 초점이 글 끝에 간다
  await nextTick();
  plusMenu.value?.activateMode("deep-research");
}

// 소장자료 결과의 [DeepResearch로 이어서 조사하기] — 결과의 검색어를 메인 입력창(논문 패널)에 채우고 DeepResearch 모드를 켠다.
// 연구는 시작하지 않는다(고쳐 보내면 기존 흐름). 사이드바 [+ 연구 시작하기]와 같은 랜딩 주소(?start=)로 옮겨 뒤로 가기로 이 결과에
// 돌아온다. 입력창이 아니라 화면 결과의 검색어(resultQuery)를 싣는다
function continueAsDeepResearch() {
  void router.push(deepResearchStartRoute(resultQuery.value));
}

// tablist 키보드: 좌우·Home·End 로 갈래를 옮기고(자동 선택) 초점도 그 갈래로 따라간다
function onTabsKeydown(e: KeyboardEvent) {
  const next = landingTabStep(mode.value, e.key, e);
  if (!next) return;
  e.preventDefault();
  selectTab(next);
  document.getElementById(`skx-tab-${next}`)?.focus();
}

// ── End publishing additions ──────────────────────────────────

onMounted(async () => {
  if (!process.client) return;
  // 첫 복원을 setup 이 아니라 마운트 뒤에 한다 — 서버가 그린 랜딩과 하이드레이션이 어긋나지 않게
  restoreFromQuery();
  void startFromQuery();
  // 목록 API 는 브라우저 ID 헤더가 있어야 해서 서버 렌더가 아니라 마운트 뒤에 읽는다
  void loadResearchExamples();

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

});

onUnmounted(() => {
  // 떠난 화면에 늦게 온 응답이 상태를 고치지 않게, 진행 중인 검색·추천 이유 스트림을 끊는다
  runCtrl?.abort();
  examplesObserver?.disconnect();
});

// ── 유틸 ──────────────────────────────────────────────────
const suggestions = SUGGESTIONS;

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

  // 논문 모드는 papers 전용 페이지로 이동
  if (mode.value === "paper") {
    navigateTo(`/papers?q=${encodeURIComponent(query.trim())}`);
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
  resetListView();
  aiExpanded.value = false;
  view.value = "results";

  try {
    const data = await api<any>("/books/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        // 서버는 top_k 의 3 배를 후보로 훑어 도서가 모인 만큼을 돌려준다 — 10 이어도 16~30권이라 정렬·쪽 이동에 충분하다.
        // 20(서버 상한)으로 올려도 23~37권뿐이고 응답이 약 1.4s → 2.1s, 본문 2 배라 속도를 우선해 10 으로 둔다(2026-10-13 운영 실측)
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
    // 결과를 그린 뒤 저장을 기다리는 사이 상세로 떠났으면 주소를 건드리지 않는다 — 늦은 replace 가 그 이동을 취소한다(usePageLeaving)
    if (!leaving.value) router.replace({ query: { q: query.trim(), h: entry.id } });
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
  resetListView();
  selectedItem.value = null;
  pdfOpen.value = false;
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
  // 상세에서 뒤로 가기·새로고침으로 같은 기록에 돌아왔으면 그때 보던 정렬·개수·쪽을 다시 연다(그 방문 기록의 state). 새로 연 기록은 기본값
  restoreListView(savedListView());
  aiExpanded.value = false;
  if (!leaving.value && (route.query.h !== entry.id || route.query.q !== entry.title)) {
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
// 'SKOVIX 추천 1권'을 내세울 때는 그 책이 위 AI 패널에 있으므로 목록에서 뺀다(listWithoutPick) — 머리의 건수는 '그 외 총 N 건'.
// 정렬(관련도순·이름순·최신순)·한 쪽 개수·쪽 이동은 이 나머지 목록에만 적용한다 — 추천 1권은 늘 검색이 준 1위다(topBook)

// ── SKOVIX 추천 1권 (도서 AI 영역) ──────────────────────────
const topBook = computed(() => pickTopBook(books.value));
// 1위가 추천할 만큼 맞을 때만 추천 패널을 낸다(MIN_PICK_SCORE) — 아니면 안내만
const topRecommended = computed(() => isRecommendable(topBook.value));
const topReadEffect = computed(() => readEffectOf(topBook.value));
const listExcludesPick = computed(() => !!topBook.value && topRecommended.value);
const listBooks = computed(() => listWithoutPick(books.value, topBook.value, topRecommended.value));

// 기본 한 쪽 개수. 도서 후보는 수십 권이라 10 으로 두면 쪽 이동이 보인다(논문은 후보가 최대 60 편이라 20)
const BOOK_PAGE_SIZE: PageSize = 10;
const sortBy = ref<SortKey>(DEFAULT_SORT);
const pageSize = ref<PageSize>(BOOK_PAGE_SIZE);
const currentPage = ref(1);
const listRef = ref<HTMLElement | null>(null);

const sortedBooks = computed(() => sortResults(listBooks.value, sortBy.value));
const totalPages = computed(() => pageCount(sortedBooks.value.length, pageSize.value));
const pagedBooks = computed(() => pageSlice(sortedBooks.value, currentPage.value, pageSize.value));

function setSortBy(key: SortKey) {
  sortBy.value = key;
  currentPage.value = 1;
}

function setPageSize(n: PageSize) {
  pageSize.value = n;
  currentPage.value = 1;
}

// 쪽 이동 버튼은 목록 아래에 있다 — 새 쪽은 목록 맨 앞부터 읽게 목록 머리로 올린다
function goToPage(p: number) {
  currentPage.value = clampPage(p, sortedBooks.value.length, pageSize.value);
  void nextTick(() => listRef.value?.scrollIntoView({ block: "start", behavior: "smooth" }));
}

// 새 검색·랜딩으로 가면 정렬·쪽을 처음으로 돌린다. 한 쪽 개수는 사용자가 고른 대로 둔다(논문 결과와 같다)
function resetListView() {
  sortBy.value = DEFAULT_SORT;
  currentPage.value = 1;
}

// 저장된 보기가 있으면 그대로, 없으면 기본값. 쪽은 지금 목록 길이 안으로 맞춘다
function restoreListView(saved: ListView | null) {
  if (!saved) {
    resetListView();
    return;
  }
  sortBy.value = saved.sortBy;
  pageSize.value = saved.pageSize;
  currentPage.value = clampPage(saved.page, listBooks.value.length, pageSize.value);
}

// 보던 정렬·개수·쪽을 이 방문 기록(history.state)에 남긴다 — 주소에는 싣지 않는다(논문 결과도 그렇다). 결과가 떠 있을 때만
rememberListView(sortBy, pageSize, currentPage, () => view.value === "results");

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

// ── 상세 열기 ──────────────────────────────────────────────
// 논문 상세의 출처는 결과의 검색어로 싣는다(입력창 글자가 아니다). 이 화면의 기록은 도서 기록이라 h 로 싣지 않는다 —
// [검색 목록 돌아가기]가 논문 검색에서 같은 검색어로 다시 찾는다
function paperDetailUrl(bookId: string, extra: Record<string, string> = {}): string {
  return detailUrl(bookId, { kind: "search", h: null, q: resultQuery.value }, undefined, extra);
}

// 소장자료 상세 주소의 쿼리 — q 는 입력창이 아니라 화면 결과의 검색어다(함께 넘기는 h 와 같은 검색을 가리키게). 상세에서도 사이드바가
// 이 기록을 강조하고 뒤로가기가 재검색 없이 복원되게 h 도 싣는다. 점수(종합·제목·내용)는 논문 쪽과 같은 함수(detailScoreParams)로 싣는다 —
// 종합 점수는 없어도 0 으로 늘 싣는다(관련도 알약이 보이게)
function bookDetailParams(item: BookChunkGroup, extra: Record<string, string> = {}): URLSearchParams {
  const scores = detailScoreParams(item);
  const params = new URLSearchParams({ q: resultQuery.value, score: scores.score ?? "0" });
  if (currentHistoryId.value) params.set("h", currentHistoryId.value);
  if (scores.title_score !== undefined) params.set("title_score", scores.title_score);
  if (scores.content_score !== undefined) params.set("content_score", scores.content_score);
  for (const [key, value] of Object.entries(extra)) params.set(key, value);
  return params;
}

function openDetail(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(paperDetailUrl(item.book_id));
    return;
  }
  navigateTo(`/books/${item.book_id}?${bookDetailParams(item)}`);
}

// 이 책과 대화하기 → detail + chat 자동 오픈
function openDetailWithChat(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(paperDetailUrl(item.book_id, { chat: "1" }));
    return;
  }
  navigateTo(`/books/${item.book_id}?${bookDetailParams(item, { chat: "1" })}`);
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
</script>
