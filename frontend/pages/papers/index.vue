<template>
  <div :class="['skx-app', chatPaperId && 'is-lnb-collapsed']">
    <AppSidebar
      :collapsed="!!chatPaperId"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <!-- 랜딩 (검색 전) -->
    <main v-if="!hasResults" class="skx-contents">
      <div class="skx-contents__inner">
        <h1 class="skx-hero">논문 의미 기반 검색</h1>
        <div class="skx-search">
          <div class="skx-search__box">
            <ResearchSearchPlusMenu v-model="currentQuery" kind="paper" :disabled="loading" />
            <label class="skx-search__field">
              <span class="skx-sr-only">논문 검색어</span>
              <textarea
                class="skx-search__input"
                v-model="currentQuery"
                placeholder="탐구하고 싶은 논문을 자연어로 검색해보세요"
                :disabled="loading"
                @keydown.enter.exact.prevent="handleSearch(currentQuery)"
              ></textarea>
            </label>
            <div class="skx-search__actions">
              <button
                type="button"
                class="skx-send"
                @click="handleSearch(currentQuery)"
              >
                <img src="/img/ico-send.svg" alt="" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 검색 결과 -->
    <main v-else class="skx-presult">
      <h1 class="skx-sr-only">논문 검색 결과</h1>

      <!-- 검색바 -->
      <div class="skx-rsearch">
        <ResearchSearchPlusMenu v-model="currentQuery" kind="paper" />
        <input
          type="text"
          class="skx-rsearch__input"
          v-model="currentQuery"
          @keydown.enter.prevent="handleSearch(currentQuery)"
        />
        <button
          type="button"
          class="skx-send"
          @click="handleSearch(currentQuery)"
        >
          <img src="/img/ico-send.svg" alt="" />
        </button>
      </div>

      <div class="skx-result-card">
        <!-- 로딩 -->
        <div v-if="loading" style="padding: 40px; text-align: center">
          <img src="/img/ico-spinner.svg" alt="" style="width: 32px" />
          <p style="margin-top: 12px">논문을 탐색하고 있습니다...</p>
        </div>

        <!-- 에러 -->
        <div v-else-if="error" style="padding: 20px; color: #c00">
          {{ error }}
        </div>

        <template v-else>
          <!-- AI 검색 결과 -->
          <section class="skx-pai" aria-label="AI 분석 결과">
            <div class="skx-pai__header">
              <img
                class="skx-pai__logo"
                :src="aiLoading ? '/ic_ing.gif' : '/ic_done.png'"
                alt="SKOVIX AI"
              />
              <span class="skx-pai__hd-text">AI 분석 결과</span>
            </div>
            <div class="skx-pai__grid">
              <!-- 좌측: 요약 텍스트 -->
              <div class="skx-pai-main" :class="aiExpanded && 'is-expanded'">
                <div class="skx-pai-main__scroll">
                  <template v-if="aiLoading && !aiText">
                    <div class="skx-pai-section">
                      <p class="skx-pai-section__text" style="color: #999">
                        AI가 논문을 분석하고 있습니다<span
                          class="skx-stream-cursor"
                        />
                      </p>
                    </div>
                  </template>
                  <div v-else-if="aiText" v-html="renderedAiText" />
                  <div v-else class="skx-pai-section">
                    <p class="skx-pai-section__text">
                      AI 요약 정보가 없습니다.
                    </p>
                  </div>
                </div>
                <div class="skx-pai-main__foot">
                  <button
                    type="button"
                    class="skx-pai-main__expand"
                    :aria-expanded="aiExpanded"
                    @click="aiExpanded = !aiExpanded"
                  >
                    <span>{{ aiExpanded ? "접기" : "전체보기" }}</span>
                    <img
                      src="/img/ico-arrow-down.svg"
                      alt=""
                      aria-hidden="true"
                    />
                  </button>
                </div>
              </div>
              <!-- 우측: 참고 논문 목록 -->
              <div class="skx-pai-refs">
                <div class="skx-pai-refs__scroll">
                  <div v-for="ref in aiRefs" :key="ref.num" class="skx-pai-ref">
                    <div class="skx-pai-ref__num">{{ ref.num }}</div>
                    <div class="skx-pai-ref__body">
                      <p
                        class="skx-pai-ref__title skx-pai-ref__title--link"
                        @click="navigateTo(paperDetailUrl(ref.book_id))"
                      >
                        {{ ref.title }}
                      </p>
                      <p class="skx-pai-ref__author">{{ ref.authors }}</p>
                      <div class="skx-pai-ref__actions">
                        <button
                          type="button"
                          class="skx-pai-ref__btn"
                          aria-label="출처 인용"
                          @click="openRefCitation(ref)"
                        >
                          <img src="/img/ico-paper-bookmark.svg" alt="" />
                        </button>
                        <button
                          type="button"
                          class="skx-pai-ref__btn skx-pai-ref__btn--ai"
                          aria-label="DeepRead"
                          @click="chatPaperId = ref.book_id"
                        >
                          <img src="/img/ico-chat.svg" alt="" />
                        </button>
                        <button
                          type="button"
                          class="skx-pai-ref__btn"
                          aria-label="원문 보기"
                          @click="
                            pdfItem = aiRefPaperMap.get(ref.book_id) ?? null
                          "
                        >
                          <img src="/img/ico-share.svg" alt="" />
                        </button>
                      </div>
                    </div>
                  </div>
                  <template v-if="aiLoading && !aiRefs.length">
                    <div
                      v-for="n in Math.min(pagedPapers.length, 5)"
                      :key="n"
                      class="skx-pai-ref"
                    >
                      <div class="skx-pai-ref__num">{{ n }}</div>
                      <div class="skx-pai-ref__body">
                        <p class="skx-pai-ref__title">
                          {{ pagedPapers[n - 1]?.book_info?.title || "" }}
                        </p>
                        <p class="skx-pai-ref__author">
                          {{
                            pagedPapers[n - 1]?.book_info?.personal_author || ""
                          }}
                        </p>
                      </div>
                    </div>
                  </template>
                </div>
              </div>
            </div>
            <p v-if="aiText && !aiLoading" class="skx-ai-hint">
              <img src="/img/ico-chat.svg" alt="" />
              더 깊이 알고 싶은 논문은 <strong>DeepRead</strong>로 자유롭게
              질문하며 분석해보세요
            </p>
          </section>

          <!-- 논문 목록 -->
          <section class="skx-paper-section" aria-label="논문 검색 결과 목록">
            <!-- 헤더 -->
            <div class="skx-paper-head">
              <div class="skx-paper-count">
                <span class="skx-paper-count__label">그 외 총</span>
                <strong class="skx-paper-count__num">{{
                  filteredPapers.length
                }}</strong>
                <span class="skx-paper-count__label">건</span>
              </div>
              <div class="skx-paper-head__right">
                <!-- 등재 등급 필터 -->
                <div
                  v-if="gradeOptions.length"
                  class="skx-paper-grade-filter"
                  role="group"
                  aria-label="등재 등급 필터"
                >
                  <button
                    type="button"
                    :class="[
                      'skx-ptag skx-ptag--filter',
                      selectedGrade === 'all' && 'is-active',
                    ]"
                    @click="
                      selectedGrade = 'all';
                      currentPage = 1;
                    "
                  >
                    전체
                  </button>
                  <button
                    v-for="g in gradeOptions"
                    :key="g"
                    type="button"
                    :class="[
                      'skx-ptag skx-ptag--filter skx-ptag--kci',
                      selectedGrade === g && 'is-active',
                    ]"
                    @click="
                      selectedGrade = g;
                      currentPage = 1;
                    "
                  >
                    {{ g }}
                  </button>
                </div>
                <div
                  class="skx-paper-sorts"
                  role="group"
                  aria-label="정렬 기준"
                >
                  <button
                    type="button"
                    :class="[
                      'skx-paper-sort',
                      sortBy === 'relevance' && 'is-active',
                    ]"
                    :aria-pressed="sortBy === 'relevance'"
                    @click="setSortBy('relevance')"
                  >
                    <img
                      :src="
                        sortBy === 'relevance'
                          ? '/img/ico-sort-on.svg'
                          : '/img/ico-sort-off.svg'
                      "
                      alt=""
                    />
                    관련도순
                  </button>
                  <button
                    type="button"
                    :class="[
                      'skx-paper-sort',
                      sortBy === 'name' && 'is-active',
                    ]"
                    :aria-pressed="sortBy === 'name'"
                    @click="setSortBy('name')"
                  >
                    <img
                      :src="
                        sortBy === 'name'
                          ? '/img/ico-sort-on.svg'
                          : '/img/ico-sort-off.svg'
                      "
                      alt=""
                    />
                    이름순
                  </button>
                  <button
                    type="button"
                    :class="[
                      'skx-paper-sort',
                      sortBy === 'date_desc' && 'is-active',
                    ]"
                    :aria-pressed="sortBy === 'date_desc'"
                    @click="setSortBy('date_desc')"
                  >
                    <img
                      :src="
                        sortBy === 'date_desc'
                          ? '/img/ico-sort-on.svg'
                          : '/img/ico-sort-off.svg'
                      "
                      alt=""
                    />
                    최신순
                  </button>
                </div>
                <div
                  class="skx-paper-perpage"
                  :class="perpageOpen && 'is-open'"
                  ref="perpageRef"
                >
                  <button
                    type="button"
                    class="skx-paper-perpage__btn"
                    aria-haspopup="listbox"
                    :aria-expanded="perpageOpen"
                    @click.stop="perpageOpen = !perpageOpen"
                  >
                    <span class="skx-paper-perpage__label"
                      >{{ pageSize }}개씩</span
                    >
                    <img
                      src="/img/ico-arrow-down.svg"
                      alt=""
                      aria-hidden="true"
                    />
                  </button>
                  <ul class="skx-paper-perpage__menu" role="listbox">
                    <li v-for="n in [10, 20, 30, 50]" :key="n">
                      <button
                        type="button"
                        :class="[
                          'skx-paper-perpage__opt',
                          pageSize === n && 'is-selected',
                        ]"
                        role="option"
                        :aria-selected="pageSize === n"
                        @click="setPageSize(n)"
                      >
                        {{ n }}개씩
                      </button>
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            <!-- 목록 없음 -->
            <div
              v-if="!filteredPapers.length"
              style="padding: 60px; text-align: center; color: #bbb"
            >
              검색 결과가 없습니다.
            </div>

            <!-- 논문 목록 -->
            <div v-else class="skx-paper-list">
              <h2 class="skx-sr-only">논문 목록</h2>
              <article
                v-for="paper in pagedPapers"
                :key="paper.book_id"
                class="skx-paper-item"
                :data-anchor="resultAnchor(paper.book_id)"
              >
                <div class="skx-paper-item__left">
                  <div class="skx-paper-tags">
                    <span
                      v-if="aiRefNumMap.has(paper.book_id)"
                      class="skx-ptag skx-ptag--ai-cited"
                    >
                      <img src="/img/logo-mark.svg" alt="" />
                      AI 답변 인용 {{ aiRefNumMap.get(paper.book_id) }}
                    </span>
                    <span
                      v-if="paper.book_info?.grade"
                      class="skx-ptag skx-ptag--kci"
                    >
                      {{ paper.book_info.grade }}
                    </span>
                    <span class="skx-ptag skx-ptag--score">
                      관련도 {{ Math.round((paper.best_score || 0) * 100) }}%
                    </span>
                  </div>
                  <h3
                    class="skx-paper-title"
                    style="cursor: pointer"
                    @click="goToDetail(paper, $event)"
                  >
                    {{ paper.book_info?.title || paper.book_id }}
                  </h3>
                  <div
                    v-if="
                      paper.book_info?.personal_author ||
                      paper.book_info?.corporate_author
                    "
                    class="skx-paper-author"
                  >
                    {{
                      paper.book_info?.personal_author ||
                      paper.book_info?.corporate_author
                    }}
                  </div>
                  <div class="skx-paper-meta">
                    <template v-if="paper.book_info?.pub_date">
                      <span class="skx-paper-meta-text">{{
                        formatPubDate(paper.book_info.pub_date)
                      }}</span>
                    </template>
                    <template v-if="paper.book_info?.corporate_author">
                      <span class="skx-dot"></span>
                      <span class="skx-paper-meta-text">{{
                        paper.book_info.corporate_author
                      }}</span>
                    </template>
                    <template v-if="paper.book_info?.series_title">
                      <img
                        class="skx-paper-meta-arr"
                        src="/img/ico-arrow.svg"
                        alt=""
                      />
                      <span class="skx-paper-meta-text">{{
                        paper.book_info.series_title
                      }}</span>
                    </template>
                    <template v-if="paper.book_info?.kci_citations">
                      <span class="skx-dot"></span>
                      <span class="skx-paper-meta-text"
                        >KCI 인용수 {{ paper.book_info.kci_citations }}</span
                      >
                    </template>
                  </div>
                </div>
                <div class="skx-paper-item__right">
                  <div class="skx-paper-item__btn-row">
                    <button
                      type="button"
                      class="skx-btn-pview"
                      @click.stop="pdfItem = paper"
                    >
                      원문 보기
                    </button>
                    <button
                      type="button"
                      class="skx-btn-pbmark"
                      aria-label="인용 모달 팝업 열림"
                      @click.stop="
                        citeBookId = paper.book_id;
                        citeRefs = paper.book_info?.references ?? [];
                        citeModalOpen = true;
                      "
                    >
                      <img src="/img/ico-paper-bookmark.svg" alt="" />
                    </button>
                  </div>
                  <button
                    type="button"
                    class="skx-btn-ptalk"
                    @click.stop="goToDetail(paper, $event, { chat: '1' })"
                  >
                    <img src="/img/ico-chat.svg" alt="" />
                    DeepRead
                  </button>
                </div>
              </article>
            </div>

            <!-- 페이지네이션 -->
            <div v-if="totalPages > 1" class="skx-pagination">
              <nav class="skx-page" aria-label="페이지 탐색">
                <div class="skx-page-nav">
                  <button
                    type="button"
                    class="skx-page-nav-btn"
                    aria-label="처음 페이지"
                    :disabled="currentPage === 1"
                    @click="currentPage = 1"
                  >
                    <img src="/img/ico-page-first.svg" alt="" />
                  </button>
                  <button
                    type="button"
                    class="skx-page-nav-btn"
                    aria-label="이전 페이지"
                    :disabled="currentPage === 1"
                    @click="currentPage--"
                  >
                    <img src="/img/ico-page-prev.svg" alt="" />
                  </button>
                </div>
                <div class="skx-page-nums">
                  <template v-for="p in pageButtons" :key="p">
                    <span v-if="p === '...'" class="skx-page-ellipsis">…</span>
                    <button
                      v-else
                      type="button"
                      :class="[
                        'skx-page-num',
                        p === currentPage && 'is-active',
                      ]"
                      :aria-current="p === currentPage ? 'page' : undefined"
                      @click="currentPage = Number(p)"
                    >
                      {{ p }}
                    </button>
                  </template>
                </div>
                <div class="skx-page-nav">
                  <button
                    type="button"
                    class="skx-page-nav-btn"
                    aria-label="다음 페이지"
                    :disabled="currentPage === totalPages"
                    @click="currentPage++"
                  >
                    <img src="/img/ico-page-next.svg" alt="" />
                  </button>
                  <button
                    type="button"
                    class="skx-page-nav-btn"
                    aria-label="마지막 페이지"
                    :disabled="currentPage === totalPages"
                    @click="currentPage = totalPages"
                  >
                    <img src="/img/ico-page-last.svg" alt="" />
                  </button>
                </div>
              </nav>
            </div>
          </section>
        </template>
      </div>
    </main>

    <!-- 출처 인용 모달 (CitationModal 컴포넌트 재사용) -->
    <CitationModal
      :open="citeModalOpen"
      :book-id="citeBookId"
      :references="citeRefs"
      @close="citeModalOpen = false"
    />

    <!-- PDF 뷰어 -->
    <PdfViewer
      v-if="pdfItem"
      :cnts-id="pdfItem.book_id"
      :title="pdfItem.book_info?.title"
      @close="pdfItem = null"
    />

    <!-- 논문 채팅 패널 -->
    <aside :class="['skx-chat-panel', !!chatPaperId && 'is-open']">
      <div class="skx-chat-panel__inner">
        <div class="skx-chat-header">
          <button
            type="button"
            class="skx-chat-close"
            @click="chatPaperId = null"
          >
            <img src="/img/ico-arrow.svg" alt="" class="skx-chat-close__ico" />
          </button>
          <h2 class="skx-chat-title">
            DeepRead<template v-if="chatPaperTitle"
              >: {{ chatPaperTitle }}</template
            >
          </h2>
        </div>
        <BookChat
          v-if="chatPaperId"
          :cnts-id="chatPaperId"
          :book-title="chatPaperTitle"
          @close="chatPaperId = null"
        />
      </div>
    </aside>

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
import { useDetailLeave, useRestorePosition } from "~/composables/useRestorePosition";
import { safeLocalStorage } from "~/utils/browserId";
import { detailUrl, resultAnchor, type ReturnSpot } from "~/utils/detailSource";
import { slimPaperResult } from "~/utils/historySnapshot";
import { pageOfItem, spotOf } from "~/utils/restorePosition";
import { readV1Map } from "~/utils/historyStore";
import { awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import type { BookSearchResponse, BookChunkGroup } from "~/types/search";
import type { PaperEntry, PaperSnapshot } from "~/types/history";

const api = useApi();
const route = useRoute();
const router = useRouter();

const historyApi = useHistory();
const currentHistoryId = ref<string | null>(null);
// 검색·복원·요약 스트림을 한 묶음으로 끊는다 — 새 검색이나 복원이 시작되면 이전 묶음의
// 응답·스트림·저장이 새 화면과 새 기록을 덮지 못하게 한다
let runCtrl: AbortController | null = null;
function beginRun(): AbortSignal {
  runCtrl?.abort();
  runCtrl = new AbortController();
  return runCtrl.signal;
}

// ── 검색 상태 ────────────────────────────────────────────────
const currentQuery = ref("");
// 화면에 떠 있는 결과의 검색어(앞뒤 공백 제거) — currentQuery 는 검색바 v-model 이라 사용자가 고치는 중일 수 있어,
// 결과에 묶인 이동·주소 비교는 이 값을 쓴다
const resultQuery = ref("");
const loading = ref(false);
const error = ref<string | null>(null);
const paperResult = ref<BookSearchResponse | null>(null);

// ── 상세에서 돌아온 자리 ──────────────────────────────────────
// 결과는 기록에서 비동기로 복원해 브라우저·Nuxt 의 스크롤 복원이 목록보다 먼저 끝난다 — 돌아온 주소(at)면
// Nuxt 는 맞추지 않고, 누른 카드를 목록이 그려진 뒤 직접 맞춘다
definePageMeta({ scrollToTop: (to) => !to.query.at });
// 목록은 복원하는 순간 한 번에 그려져 늦게 붙는 카드가 없다 — 첫 프레임에 그 카드가 없으면(결과가 바뀜) 기다리지 않는다
const restore = useRestorePosition(
  computed(() => paperResult.value !== null && !loading.value),
  { maxWaitMs: 0 },
);
const { leave } = useDetailLeave();

// ── 인라인 채팅 ──────────────────────────────────────────────
const chatPaperId = ref<string | null>(null);
const chatPaperTitle = computed(() =>
  chatPaperId.value
    ? (aiRefPaperMap.value.get(chatPaperId.value)?.book_info?.title ?? "")
    : "",
);

// ── AI 요약 ──────────────────────────────────────────────────
const aiText = ref("");
const aiLoading = ref(false);
const aiExpanded = ref(false);
const aiRefs = ref<
  { num: number; book_id: string; title: string; authors: string }[]
>([]);
const renderedAiText = computed(() =>
  aiText.value ? (marked.parse(aiText.value) as string) : "",
);

// ── 정렬 / 페이지 / 필터 ─────────────────────────────────────
const selectedGrade = ref("all");
const sortBy = ref("relevance");
const pageSize = ref(20);
const currentPage = ref(1);
const perpageOpen = ref(false);
const perpageRef = ref<HTMLElement | null>(null);

// ── PDF 뷰어 ─────────────────────────────────────────────────
const pdfItem = ref<BookChunkGroup | null>(null);

// ── 인용 모달 ─────────────────────────────────────────────────
const citeModalOpen = ref(false);
const citeBookId = ref<string | null>(null);
const citeRefs = ref<string[]>([]);

// ── Toast ─────────────────────────────────────────────────────
const toast = ref("");
function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

// ── 계산 ─────────────────────────────────────────────────────
const hasResults = computed(() => paperResult.value !== null || loading.value);

// AI 답변 인용 논문: book_id → 인용 번호 (우측 참고 카드 번호와 동일)
const aiRefNumMap = computed(() => {
  const m = new Map<string, number>();
  for (const r of aiRefs.value) m.set(r.book_id, r.num);
  return m;
});

const aiRefPaperMap = computed(() => {
  const map = new Map<string, BookChunkGroup>();
  for (const p of paperResult.value?.books ?? []) {
    map.set(p.book_id, p);
  }
  return map;
});

const sortedPapers = computed(() => {
  if (!paperResult.value) return [];
  const books = [...paperResult.value.books];
  if (sortBy.value === "relevance")
    return books.sort((a, b) => b.best_score - a.best_score);
  if (sortBy.value === "name")
    return books.sort((a, b) =>
      (a.book_info?.title ?? "").localeCompare(b.book_info?.title ?? ""),
    );
  if (sortBy.value === "date_desc")
    return books.sort((a, b) =>
      (b.book_info?.pub_date ?? "").localeCompare(a.book_info?.pub_date ?? ""),
    );
  return books;
});

const gradeOptions = computed(() => {
  const grades = new Set<string>();
  (paperResult.value?.books ?? []).forEach((b) => {
    const g = b.book_info?.grade;
    if (g) grades.add(g);
  });
  return Array.from(grades).sort();
});

const filteredPapers = computed(() => {
  const base =
    selectedGrade.value === "all"
      ? sortedPapers.value
      : sortedPapers.value.filter(
          (b) => b.book_info?.grade === selectedGrade.value,
        );
  if (!aiRefNumMap.value.size) return base;
  // AI 답변에 인용된 논문을 인용 번호 순으로 상단 고정, 나머지는 선택 정렬 유지
  const cited = base
    .filter((p) => aiRefNumMap.value.has(p.book_id))
    .sort(
      (a, b) =>
        (aiRefNumMap.value.get(a.book_id) ?? 0) -
        (aiRefNumMap.value.get(b.book_id) ?? 0),
    );
  const rest = base.filter((p) => !aiRefNumMap.value.has(p.book_id));
  return [...cited, ...rest];
});

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredPapers.value.length / pageSize.value)),
);

const pagedPapers = computed(() =>
  filteredPapers.value.slice(
    (currentPage.value - 1) * pageSize.value,
    currentPage.value * pageSize.value,
  ),
);

const pageButtons = computed(() => {
  const total = totalPages.value;
  const cur = currentPage.value;
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | string)[] = [1];
  if (cur > 3) pages.push("...");
  for (let i = Math.max(2, cur - 1); i <= Math.min(total - 1, cur + 1); i++)
    pages.push(i);
  if (cur < total - 2) pages.push("...");
  pages.push(total);
  return pages;
});

// ── 유틸 ─────────────────────────────────────────────────────
function monthStr(pubDate: string): string {
  const m = pubDate?.slice(4, 6);
  return m ? `${parseInt(m)}월` : "";
}

function setSortBy(key: string) {
  sortBy.value = key;
  currentPage.value = 1;
}

function setPageSize(n: number) {
  pageSize.value = n;
  currentPage.value = 1;
  perpageOpen.value = false;
}

function formatPubDate(pubDate: string): string {
  const m = pubDate.match(/(\d{4})[.\-]?(\d{1,2})/);
  if (!m || !m[1] || !m[2]) return pubDate;
  return `${m[1]}년 ${parseInt(m[2])}월`;
}

function openRefCitation(ref: { book_id: string }) {
  const paper = aiRefPaperMap.value.get(ref.book_id);
  citeBookId.value = ref.book_id;
  citeRefs.value = paper?.book_info?.references ?? [];
  citeModalOpen.value = true;
}

// 상세로 갈 때 출처(이 검색 기록)를 넘긴다 — 상세에서도 사이드바가 이 기록을 강조하고, [검색 결과로]가 재검색 없이
// 복원된다. q 는 검색바가 아니라 화면 결과의 검색어다(함께 넘기는 h 와 같은 검색). 관련도는 상세 머리 카드가 보인다
function paperDetailUrl(bookId: string, spot?: ReturnSpot, extra: Record<string, string> = {}): string {
  const score = aiRefPaperMap.value.get(bookId)?.best_score;
  return detailUrl(
    bookId,
    { kind: "search", h: currentHistoryId.value, q: resultQuery.value },
    spot,
    score === undefined ? extra : { score: String(score), ...extra },
  );
}

// 누른 카드의 지금 화면 높이를 싣고 떠난다 — [검색 결과로]·뒤로 가기로 돌아오면 이 카드를 같은 높이에 맞춘다
function goToDetail(paper: BookChunkGroup, e: MouseEvent, extra: Record<string, string> = {}) {
  const card = (e.currentTarget as HTMLElement).closest<HTMLElement>("[data-anchor]")!;
  const spot = spotOf(card, resultAnchor(paper.book_id));
  void leave(paperDetailUrl(paper.book_id, spot, extra), spot);
}

// ── 검색 ─────────────────────────────────────────────────────
async function handleSearch(q?: string, reuse?: PaperEntry) {
  const query = (q ?? currentQuery.value).trim();
  if (!query || loading.value) return;
  const signal = beginRun();
  currentQuery.value = query;
  resultQuery.value = query;
  currentHistoryId.value = null;
  // 등재 필터는 검색을 시작할 때의 값으로 한 번 정한다 — 주소와 기록에 같은 값이 들어가게
  const grade = selectedGrade.value !== "all" ? selectedGrade.value : "";
  // 주소의 이전 h 도 함께 내린다 — 남겨 두면 검색이 도는 동안·실패한 뒤에도 사이드바가 이전 기록을 강조하고,
  // 그 기록을 누르면 지금 주소와 같아 이동이 무시되며, 새로고침하면 이전 기록이 열린다
  router.replace({ query: { q: query, ...(grade ? { grade } : {}) } });
  loading.value = true;
  error.value = null;
  paperResult.value = null;
  aiText.value = "";
  aiRefs.value = [];
  aiLoading.value = false;
  aiExpanded.value = false;
  currentPage.value = 1;
  sortBy.value = "relevance";

  try {
    const data = await api<BookSearchResponse>("/papers/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 20,
        use_rewrite: true,
        use_rerank: true,
      },
      signal,
    });
    if (signal.aborted) return;
    paperResult.value = data;
    loading.value = false;

    // 기록 id 를 먼저 확정해 요약 스트림에 넘긴다 — 끝난 뒤 저장이 그 사이 바뀐 화면의 기록을 덮지 않게
    const snapshot = slimPaperResult(data) ?? undefined;
    const entry = reuse
      ? ((await historyApi.patch(reuse.id, { snapshot })) ?? reuse)
      : await historyApi.add({ kind: "paper", title: query, params: grade ? { grade } : {}, snapshot });
    if (signal.aborted) return;
    currentHistoryId.value = entry.id;
    router.replace({ query: { q: query, h: entry.id, ...(grade ? { grade } : {}) } });
    if (data.books?.length) streamAiSummary(entry.id, query, data.books, signal);
  } catch (e: any) {
    if (signal.aborted) return;
    error.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
    paperResult.value = { mode: "book", query, books: [], elapsed_ms: 0 };
  } finally {
    if (!signal.aborted) loading.value = false;
  }
}

// 랜딩으로 되돌린다 — 진행 중인 검색·복원·요약 묶음을 끊고 결과 화면 상태를 비운다.
// hasResults 가 paperResult·loading 에서 나오므로 둘을 비우면 화면이 랜딩으로 바뀐다
function goLanding() {
  runCtrl?.abort();
  runCtrl = null;
  paperResult.value = null;
  loading.value = false;
  error.value = null;
  currentQuery.value = "";
  resultQuery.value = "";
  currentHistoryId.value = null;
  aiText.value = "";
  aiRefs.value = [];
  aiLoading.value = false;
  selectedGrade.value = "all";
  // 결과 화면에서 연 창들도 닫는다 — 랜딩 위에 이전 결과의 논문 창이 남지 않게
  pdfItem.value = null;
  citeModalOpen.value = false;
  chatPaperId.value = null;
}

// ── 기록 복원 ─────────────────────────────────────────────────
// 주소(?h=)가 복원의 정본이다 — 사이드바·뒤로가기·새로고침이 모두 이 한 길로 들어온다
async function restoreFromQuery() {
  // 다른 페이지로 넘어가는 중에는 그 주소의 q 로 재검색하지 않는다
  if (route.path !== "/papers") return;
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
  const { h, q, grade } = target;
  if (!h) {
    if (!q) {
      // 기록도 검색어도 없는 주소는 랜딩이다 — 같은 경로라 다시 마운트되지 않으므로(랜딩에서 기록을 연 뒤
      // 뒤로가기 등) 결과 화면과 진행 중인 요청을 직접 걷는다. 안 걷으면 주소는 '/papers' 인데 결과가 남는다
      goLanding();
      return;
    }
    // 검색바가 아니라 화면 결과의 검색어와 비교한다 — 검색바를 고쳐 둔 채 이 주소로 오면 엉뚱하게 건너뛴다.
    // 둘 다 앞뒤 공백을 뗀 값이라 같은 검색어를 공백 차이로 다시 찾지 않는다
    if (q !== resultQuery.value) {
      selectedGrade.value = grade ?? "all";
      await handleSearch(q);
    }
    return;
  }
  if (h === currentHistoryId.value) return;

  const signal = beginRun();
  loading.value = false;
  const entry = await historyApi.get(h);
  if (signal.aborted) return;
  if (entry && entry.kind !== "paper") {
    // 다른 종류의 기록 id 가 이 주소로 왔다(옛 ?restore= 등) — 그 종류의 주소로 보낸다
    router.replace(routeFor(entry));
    return;
  }
  const paper = entry?.kind === "paper" ? entry : null;
  if (paper?.snapshot) {
    applyPaperEntry(paper, signal);
    return;
  }
  // 없거나 남의 기록이면 검색어로 새로 찾는다(D7). 결과만 비어 있던 내 기록은 같은 id 를 채운다
  if (!paper) void historyApi.refresh("paper");
  const retryQuery = q ?? paper?.title;
  if (retryQuery) {
    const savedGrade = typeof paper?.params.grade === "string" ? paper.params.grade : "";
    selectedGrade.value = savedGrade || grade || "all";
    await handleSearch(retryQuery, paper ?? undefined);
    return;
  }
  showToast("없는 기록입니다. 목록을 새로 고쳤습니다.");
}

function applyPaperEntry(entry: PaperEntry, signal: AbortSignal) {
  const snap = entry.snapshot as PaperSnapshot;
  const grade = typeof entry.params.grade === "string" ? entry.params.grade : "";
  loading.value = false;
  error.value = null;
  currentQuery.value = entry.title;
  resultQuery.value = entry.title;
  currentHistoryId.value = entry.id;
  paperResult.value = {
    mode: "book",
    query: entry.title,
    books: snap.books as unknown as BookChunkGroup[],
    elapsed_ms: 0,
  };
  aiText.value = entry.ai?.text ?? "";
  aiRefs.value = (entry.ai?.refs ?? []) as typeof aiRefs.value;
  aiLoading.value = false;
  aiExpanded.value = true;
  sortBy.value = "relevance";
  selectedGrade.value = grade || "all";
  // 정렬·필터를 정한 뒤에 찾아야 화면 목록과 같은 순서다
  currentPage.value = returnPage();
  if (route.query.h !== entry.id || route.query.q !== entry.title) {
    router.replace({ query: { q: entry.title, h: entry.id, ...(grade ? { grade } : {}) } });
  }
  // 요약이 끝나기 전에 떠난 기록은 요약이 비어 있다 — 복원할 때 한 번 더 만든다
  if (!entry.ai && snap.books.length) streamAiSummary(entry.id, entry.title, snap.books, signal);
}

// 상세에서 돌아왔으면 그 카드가 있는 쪽을 연다 — 기록은 화면이 쪽으로 나눠 보인 결과를 모두 담아(slimPaperResult)
// 둘째 쪽 이후의 카드도 찾는다. 쪽 크기·정렬은 기록에 없어 기본값으로 찾는다
function returnPage(): number {
  const anchor = restore.pending.value ? restore.anchor : null;
  if (anchor?.kind !== "result") return 1;
  return pageOfItem(filteredPapers.value.map((p) => p.book_id), anchor.cnts, pageSize.value) ?? 1;
}

// ── AI 요약 SSE ───────────────────────────────────────────────
type SummarySource = {
  book_id: string;
  book_info?: { title?: string; personal_author?: string; corporate_author?: string };
};

async function streamAiSummary(
  historyId: string,
  query: string,
  books: SummarySource[],
  signal: AbortSignal,
) {
  aiLoading.value = true;
  const papers = books.slice(0, 5).map((b) => ({
    book_id: b.book_id,
    title: b.book_info?.title || "",
    authors:
      b.book_info?.personal_author || b.book_info?.corporate_author || "",
    best_chunk_text: "",
  }));
  let text = "";
  let refs: typeof aiRefs.value = [];
  try {
    const resp = await fetch(apiUrl("/papers/summary/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ query, papers }),
      signal,
    });
    if (!resp.ok || !resp.body) return;
    const reader = resp.body.getReader();
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
          const evt = JSON.parse(raw);
          if (evt.text) {
            text += evt.text;
            aiText.value = text;
          }
          if (evt.sources) {
            refs = evt.sources;
            aiRefs.value = refs;
          }
        } catch {}
      }
    }
  } catch {
    /* 중단·네트워크 오류 — 받은 데까지만 남긴다 */
  } finally {
    // 끊긴 묶음은 저장하지 않는다 — 화면과 기록은 이미 다음 묶음의 것이다
    if (!signal.aborted) {
      aiLoading.value = false;
      if (text) historyApi.patch(historyId, { ai: { text, refs } });
    }
  }
}

// ── 페이지당 개수 드롭다운 닫기 + 주소 기준 첫 복원 ─────────────
onMounted(() => {
  document.addEventListener("click", () => {
    perpageOpen.value = false;
  });
  // 첫 복원을 setup 이 아니라 마운트 뒤에 한다 — 서버가 그린 랜딩과 하이드레이션이 어긋나지 않게
  restoreFromQuery();
});

// 같은 경로에서 쿼리만 바뀌면(사이드바 클릭·뒤로가기) 페이지가 다시 마운트되지 않는다.
// q 도 본다 — h 가 없는 주소(검색 중·실패 뒤의 ?q=)에서 랜딩 주소로 돌아오면 h 는 그대로 없어 변화를 놓친다
watch(
  [() => route.query.h ?? route.query.restore, () => route.query.q],
  () => {
    restoreFromQuery();
  },
);

// 페이지를 떠나면 요약 스트림도 끊는다 — 안 끊으면 GPU 생성이 끝까지 돈다
onBeforeUnmount(() => runCtrl?.abort());

// 돌아온 카드의 쪽을 여는 동안에는 맨 위로 올리지 않는다 — 그 카드 자리를 맞추는 중이다
watch(currentPage, () => {
  if (!restore.pending.value) window.scrollTo({ top: 0, behavior: "smooth" });
});
</script>
