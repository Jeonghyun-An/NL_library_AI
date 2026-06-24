<template>
  <div class="page">
    <!-- ══ 전체 폭 상단 바 ════════════════════════════════════════ -->
    <header class="top-bar" ref="topBarRef">
      <div class="top-bar-inner">
        <button class="top-brand" @click="resetSearch">
          <img
            src="/skovix-character.png"
            alt="SKOVIX"
            class="top-brand-skovix"
          />
        </button>

        <div class="top-search-area">
          <SearchInput
            v-if="hasResults"
            v-model="currentQuery"
            :disabled="loading"
            @submit="handleSearch"
          />
        </div>

        <div class="top-end" :style="{ flexBasis: '44px' }" />
      </div>
    </header>

    <!-- ══ 3단 그리드 레이아웃 ═══════════════════════════════════ -->
    <div class="app-layout" :style="{ gridTemplateColumns: gridCols }">
      <!-- ══ 왼쪽 사이드바: 필터 ═══════════════════════════════ -->
      <aside class="sidebar sidebar-left">
        <button
          class="sidebar-toggle"
          :class="{ collapsed: !leftOpen }"
          :title="leftOpen ? '필터 패널 닫기' : '필터 패널 열기'"
          @click="leftOpen = !leftOpen"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <polyline
              :points="leftOpen ? '15 18 9 12 15 6' : '9 18 15 12 9 6'"
            />
          </svg>
          <Transition name="fade-text">
            <span v-if="leftOpen">필터</span>
          </Transition>
        </button>

        <div v-show="leftOpen" class="sidebar-body scrollbar-zinc">
          <template v-if="hasResults">
            <div v-if="activeFilterCount > 0" class="facet-clear-row">
              <button class="facets-clear" @click="clearFilters">
                전체 해제
              </button>
            </div>

            <div class="facet-group">
              <h5>자료 유형</h5>
              <label
                v-for="g in genreOptions"
                :key="g.value"
                class="facet-row"
                :class="{ 'is-on': filters.genres.includes(g.value) }"
              >
                <input
                  type="checkbox"
                  :checked="filters.genres.includes(g.value)"
                  @change="toggleGenre(g.value)"
                />
                <span class="facet-name">{{ g.label }}</span>
                <span class="facet-count">{{ g.count }}</span>
              </label>
            </div>

            <div class="facet-group">
              <h5>발행 연도</h5>
              <div class="year-bars">
                <div
                  v-for="(bar, i) in yearBars"
                  :key="i"
                  class="year-bar"
                  :class="{ 'is-out': !bar.inRange }"
                  :style="{ height: bar.h + '%' }"
                />
              </div>
              <div class="year-range">
                <input
                  type="text"
                  v-model="filters.yearFrom"
                  placeholder="2000"
                  maxlength="4"
                />
                <span class="dash">—</span>
                <input
                  type="text"
                  v-model="filters.yearTo"
                  placeholder="2026"
                  maxlength="4"
                />
              </div>
            </div>

            <div class="facet-group" v-if="journalOptions.length">
              <h5>학술지 / 게재지</h5>
              <label
                v-for="j in journalOptions.slice(0, showAllJournals ? 999 : 5)"
                :key="j.value"
                class="facet-row"
                :class="{ 'is-on': filters.journals.includes(j.value) }"
              >
                <input
                  type="checkbox"
                  :checked="filters.journals.includes(j.value)"
                  @change="toggleJournal(j.value)"
                />
                <span class="facet-name">{{ j.value }}</span>
                <span class="facet-count">{{ j.count }}</span>
              </label>
              <button
                v-if="journalOptions.length > 5"
                class="facet-more"
                @click="showAllJournals = !showAllJournals"
              >
                {{
                  showAllJournals
                    ? "접기"
                    : `+${journalOptions.length - 5}개 더 보기`
                }}
              </button>
            </div>

            <div class="facet-group" v-if="languageOptions.length > 1">
              <h5>언어</h5>
              <label
                v-for="l in languageOptions"
                :key="l.value"
                class="facet-row"
                :class="{ 'is-on': filters.languages.includes(l.value) }"
              >
                <input
                  type="checkbox"
                  :checked="filters.languages.includes(l.value)"
                  @change="toggleLanguage(l.value)"
                />
                <span class="facet-name">{{ l.label }}</span>
                <span class="facet-count">{{ l.count }}</span>
              </label>
            </div>
          </template>
        </div>
      </aside>

      <!-- ══ 메인 콘텐츠 ═══════════════════════════════════════ -->
      <main class="main-content scrollbar-zinc">
        <!-- 랜딩 -->
        <div v-if="!hasResults" class="landing">
          <div class="seg" ref="segRef">
            <div class="seg-thumb" :style="thumbStyle" />
            <button data-key="book" class="seg-btn" @click="navigateTo('/')">
              <svg class="ico" viewBox="0 0 20 20" fill="none">
                <path
                  d="M4 4.5C4 3.67 4.67 3 5.5 3H15a1 1 0 0 1 1 1v11.5a.5.5 0 0 1-.5.5H6a2 2 0 0 0-2 2V4.5Z"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linejoin="round"
                />
                <path
                  d="M6 18h9.5"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linecap="round"
                />
                <path
                  d="M7 7h6M7 10h4"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linecap="round"
                />
              </svg>
              도서 검색
            </button>
            <button data-key="paper" class="seg-btn is-active">
              <svg class="ico" viewBox="0 0 20 20" fill="none">
                <path
                  d="M5 2.5h7.5L16 6v11.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Z"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linejoin="round"
                />
                <path
                  d="M12 2.5V6h4"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linejoin="round"
                />
                <path
                  d="M7 10h6M7 13h6M7 16h4"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linecap="round"
                />
              </svg>
              논문 검색
            </button>
          </div>
          <div class="logo-area">
            <h1 class="title">논문 의미 기반 검색</h1>
            <p class="subtitle">탐구하고 싶은 논문을 자연어로 검색해보세요</p>
          </div>
          <SearchInput
            placeholder="RAG 기반 검색 시스템의 최신 동향 알려줘"
            :disabled="loading"
            @submit="handleSearch"
          />
        </div>

        <!-- 결과 -->
        <div v-else class="results-page">
          <div v-if="loading" class="loading-area">
            <div class="spinner" />
            <p>논문을 탐색하고 있습니다...</p>
          </div>

          <div v-else-if="error" class="error-area">
            <p>{{ error }}</p>
            <button @click="handleSearch(currentQuery)">다시 검색</button>
          </div>

          <div v-else class="results-content">
            <div class="search-meta">
              <span class="query-display">"{{ paperResult?.query }}"</span>
              <span class="elapsed"
                >{{ paperResult?.elapsed_ms.toFixed(0) }}ms</span
              >
              <span v-if="paperResult?.rewritten_query" class="rewritten">
                → {{ paperResult?.rewritten_query }}
              </span>
            </div>

            <!-- 적용된 필터 칩 -->
            <div v-if="activeFilterCount > 0" class="applied">
              <span
                v-for="g in filters.genres"
                :key="'g' + g"
                class="applied-chip"
              >
                {{ GENRE_LABELS[g] || g }}
                <span class="x" @click="toggleGenre(g)">✕</span>
              </span>
              <span
                v-if="filters.yearFrom || filters.yearTo"
                class="applied-chip"
              >
                {{ filters.yearFrom || "~" }}–{{ filters.yearTo || "현재" }}
                <span
                  class="x"
                  @click="
                    filters.yearFrom = '';
                    filters.yearTo = '';
                  "
                  >✕</span
                >
              </span>
              <span
                v-for="j in filters.journals"
                :key="'j' + j"
                class="applied-chip"
              >
                {{ j }}<span class="x" @click="toggleJournal(j)">✕</span>
              </span>
              <span
                v-for="l in filters.languages"
                :key="'l' + l"
                class="applied-chip"
              >
                {{ l }}<span class="x" @click="toggleLanguage(l)">✕</span>
              </span>
            </div>

            <!-- 툴바 -->
            <div class="toolbar">
              <div class="toolbar-left">
                <button
                  v-if="!leftOpen"
                  class="facets-reopen"
                  @click="leftOpen = true"
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <path
                      d="M3 4h10M3 8h10M3 12h10"
                      stroke="currentColor"
                      stroke-width="1.5"
                      stroke-linecap="round"
                    />
                  </svg>
                  필터
                  <span v-if="activeFilterCount > 0" class="badge">{{
                    activeFilterCount
                  }}</span>
                </button>
                <div class="count">
                  <strong>{{ filteredPapers.length.toLocaleString() }}</strong>
                  편 검색됨
                </div>
              </div>
              <div class="toolbar-right">
                <div class="sort" ref="sortRef">
                  <button
                    class="sort-btn"
                    @click="sortMenuOpen = !sortMenuOpen"
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                      <path
                        d="M4 4h8M5 8h6M6 12h4"
                        stroke="currentColor"
                        stroke-width="1.5"
                        stroke-linecap="round"
                      />
                    </svg>
                    {{ SORT_LABELS[sortBy] }}
                  </button>
                  <div v-if="sortMenuOpen" class="sort-menu">
                    <button
                      v-for="(label, key) in SORT_LABELS"
                      :key="key"
                      :class="{ 'is-on': sortBy === key }"
                      @click="
                        sortBy = key;
                        sortMenuOpen = false;
                      "
                    >
                      {{ label }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="!filteredPapers.length" class="empty">
              검색 결과가 없습니다. 다른 검색어를 시도해보세요.
            </div>

            <template v-else>
              <!-- 탐구 카드 목록 -->
              <div class="explore-stack">
                <div
                  v-for="paper in pagedPapers"
                  :key="paper.book_id"
                  class="paper-item"
                >
                <article
                  class="ec"
                  :class="{ 'is-chat-open': chatPaper?.book_id === paper.book_id }"
                  @click="openChat(paper)"
                >
                  <div class="ec-main">
                    <div class="ec-pills">
                      <span v-if="paper.book_info?.genre" class="pill kdc">{{
                        GENRE_LABELS[paper.book_info.genre] ||
                        paper.book_info.genre
                      }}</span>
                      <span v-if="paper.book_info?.publisher" class="pill">{{
                        paper.book_info.publisher
                      }}</span>
                      <span
                        v-if="
                          paper.book_info?.language &&
                          paper.book_info.language !== 'ko'
                        "
                        class="pill"
                        >{{ paper.book_info.language?.toUpperCase() }}</span
                      >
                    </div>
                    <h3 class="ec-title">
                      {{ paper.book_info?.title || paper.book_id }}
                    </h3>
                    <p
                      v-if="paper.book_info?.title_remainder"
                      class="ec-title-en"
                    >
                      {{ paper.book_info.title_remainder }}
                    </p>
                    <div class="ec-meta">
                      <span
                        v-if="paper.book_info?.personal_author"
                        class="author"
                        >{{ paper.book_info.personal_author }}</span
                      >
                      <span
                        v-if="
                          paper.book_info?.personal_author &&
                          paper.book_info?.publisher
                        "
                        class="dot"
                        >·</span
                      >
                      <span v-if="paper.book_info?.publisher" class="venue">{{
                        paper.book_info.publisher
                      }}</span>
                      <span v-if="paper.book_info?.pub_date" class="dot"
                        >·</span
                      >
                      <span v-if="paper.book_info?.pub_date">{{
                        paper.book_info.pub_date
                      }}</span>
                      <span v-if="paper.book_info?.corporate_author" class="dot"
                        >·</span
                      >
                      <span v-if="paper.book_info?.corporate_author">{{
                        paper.book_info.corporate_author
                      }}</span>
                    </div>
                    <p v-if="paper.book_info?.abstract" class="ec-abstract">
                      {{ paper.book_info.abstract }}
                    </p>
                    <div class="ec-actions" @click.stop>
                      <button class="ec-btn accent" @click="openChat(paper)">
                        <svg
                          width="13"
                          height="13"
                          viewBox="0 0 16 16"
                          fill="none"
                        >
                          <path
                            d="M2.5 4a1.5 1.5 0 0 1 1.5-1.5h8A1.5 1.5 0 0 1 13.5 4v5A1.5 1.5 0 0 1 12 10.5H6L3 13v-2.5A1.5 1.5 0 0 1 2.5 9V4Z"
                            stroke="currentColor"
                            stroke-width="1.4"
                            stroke-linejoin="round"
                          />
                        </svg>
                        대화하기
                      </button>
                      <a
                        v-if="paper.book_info?.url"
                        :href="paper.book_info.url"
                        target="_blank"
                        class="ec-btn"
                        @click.stop
                      >
                        <svg
                          width="13"
                          height="13"
                          viewBox="0 0 16 16"
                          fill="none"
                        >
                          <path
                            d="M9 3h4v4M13 3 7 9M11 9.5V12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h2.5"
                            stroke="currentColor"
                            stroke-width="1.4"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                        </svg>
                        원문 보기
                      </a>
                    </div>
                  </div>
                  <div class="ec-side">
                    <div class="ec-score">
                      {{ Math.round(paper.best_score * 100)
                      }}<span class="pct-unit">%</span>
                    </div>
                    <div class="ec-score-lbl">적합도</div>
                    <div class="barmini">
                      <i
                        :style="{
                          width: Math.round(paper.best_score * 100) + '%',
                        }"
                      />
                    </div>
                    <div v-if="paper.book_info?.pub_date" class="ec-year">
                      {{ paper.book_info.pub_date.slice(0, 4) }}
                    </div>
                  </div>
                </article>

                <!-- 인라인 대화 패널 (v-show로 마운트 유지 → 기록 보존) -->
                <BookChat
                  v-if="mountedChats.has(paper.book_id)"
                  v-show="chatPaper?.book_id === paper.book_id"
                  :cnts-id="paper.book_id"
                  @close="chatPaper = null"
                />
                </div>
              </div>

              <!-- 페이지네이션 -->
              <div class="pager">
                <div class="pager-info">
                  {{ (currentPage - 1) * PAGE_SIZE + 1 }}–{{
                    Math.min(currentPage * PAGE_SIZE, filteredPapers.length)
                  }}
                  / {{ filteredPapers.length.toLocaleString() }}편
                </div>
                <div class="pager-nav">
                  <button
                    class="page-btn"
                    :disabled="currentPage === 1"
                    @click="currentPage--"
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                      <path
                        d="M10 4L6 8l4 4"
                        stroke="currentColor"
                        stroke-width="1.6"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>
                  <template v-for="p in pageButtons" :key="p">
                    <span v-if="p === '...'" class="page-ellipsis">…</span>
                    <button
                      v-else
                      class="page-btn"
                      :class="{ 'is-on': p === currentPage }"
                      @click="currentPage = p as number"
                    >
                      {{ p }}
                    </button>
                  </template>
                  <button
                    class="page-btn"
                    :disabled="currentPage === totalPages"
                    @click="currentPage++"
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                      <path
                        d="M6 4l4 4-4 4"
                        stroke="currentColor"
                        stroke-width="1.6"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </template>
          </div>
        </div>
      </main>

      <!-- ══ 오른쪽 사이드바 (빈 공간) ════════════════════════ -->
      <aside class="sidebar sidebar-right" />
    </div>

  </div>
</template>

<script setup lang="ts">
import type { BookChunkGroup, BookSearchResponse } from "~/types/search";

const config = useRuntimeConfig();

const currentQuery = ref("");
const loading = ref(false);
const error = ref<string | null>(null);
const paperResult = ref<BookSearchResponse | null>(null);
const topBarRef = ref<HTMLElement | null>(null);
const topBarHeight = ref(84);
const segRef = ref<HTMLElement | null>(null);
const thumbStyle = ref({ left: "5px", width: "120px" });
const sortRef = ref<HTMLElement | null>(null);

const leftOpen = ref(true);
const sortMenuOpen = ref(false);
const showAllJournals = ref(false);
const chatPaper = ref<BookChunkGroup | null>(null);
const mountedChats = ref(new Set<string>());
const currentPage = ref(1);

const sessionId = useState<string | null>("sessionId", () => null);

const SORT_LABELS: Record<string, string> = {
  relevance: "적합도순",
  recent: "최신순",
  oldest: "오래된순",
};

const GENRE_LABELS: Record<string, string> = {
  paper: "학술논문",
  thesis: "학위논문",
  report: "연구보고서",
  manual: "매뉴얼",
  book: "단행본",
  other: "기타",
};

const LANG_LABELS: Record<string, string> = {
  ko: "한국어",
  en: "영어",
  ja: "일본어",
  zh: "중국어",
};

const sortBy = ref("relevance");
const PAGE_SIZE = 20;

const filters = reactive({
  genres: [] as string[],
  yearFrom: "",
  yearTo: "",
  journals: [] as string[],
  languages: [] as string[],
});

const hasResults = computed(() => paperResult.value !== null || loading.value);

const gridCols = computed(() => {
  const l = leftOpen.value ? "220px" : "44px";
  return `${l} 1fr 44px`;
});

const sortedPapers = computed(() => {
  if (!paperResult.value) return [];
  const books = [...paperResult.value.books];
  if (sortBy.value === "relevance")
    return books.sort((a, b) => b.best_score - a.best_score);
  if (sortBy.value === "recent")
    return books.sort((a, b) =>
      (b.book_info?.pub_date ?? "").localeCompare(a.book_info?.pub_date ?? ""),
    );
  if (sortBy.value === "oldest")
    return books.sort((a, b) =>
      (a.book_info?.pub_date ?? "").localeCompare(b.book_info?.pub_date ?? ""),
    );
  return books;
});

const filteredPapers = computed(() => {
  return sortedPapers.value.filter((p) => {
    const info = p.book_info;
    if (
      filters.genres.length &&
      info?.genre &&
      !filters.genres.includes(info.genre)
    )
      return false;
    if (filters.yearFrom) {
      const y = (info?.pub_date ?? "").slice(0, 4);
      if (y && y < filters.yearFrom) return false;
    }
    if (filters.yearTo) {
      const y = (info?.pub_date ?? "").slice(0, 4);
      if (y && y > filters.yearTo) return false;
    }
    if (
      filters.journals.length &&
      info?.publisher &&
      !filters.journals.includes(info.publisher)
    )
      return false;
    if (
      filters.languages.length &&
      info?.language &&
      !filters.languages.includes(info.language)
    )
      return false;
    return true;
  });
});

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredPapers.value.length / PAGE_SIZE)),
);
const pagedPapers = computed(() =>
  filteredPapers.value.slice(
    (currentPage.value - 1) * PAGE_SIZE,
    currentPage.value * PAGE_SIZE,
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

const activeFilterCount = computed(
  () =>
    filters.genres.length +
    filters.journals.length +
    filters.languages.length +
    (filters.yearFrom || filters.yearTo ? 1 : 0),
);

const genreOptions = computed(() => {
  const map = new Map<string, number>();
  (paperResult.value?.books ?? []).forEach((p) => {
    const g = p.book_info?.genre ?? "other";
    map.set(g, (map.get(g) ?? 0) + 1);
  });
  return [...map.entries()]
    .map(([value, count]) => ({
      value,
      label: GENRE_LABELS[value] || value,
      count,
    }))
    .sort((a, b) => b.count - a.count);
});

const journalOptions = computed(() => {
  const map = new Map<string, number>();
  (paperResult.value?.books ?? []).forEach((p) => {
    const j = p.book_info?.publisher;
    if (j) map.set(j, (map.get(j) ?? 0) + 1);
  });
  return [...map.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count);
});

const languageOptions = computed(() => {
  const map = new Map<string, number>();
  (paperResult.value?.books ?? []).forEach((p) => {
    const l = p.book_info?.language;
    if (l) map.set(l, (map.get(l) ?? 0) + 1);
  });
  return [...map.entries()]
    .map(([value, count]) => ({
      value,
      label: LANG_LABELS[value] || value,
      count,
    }))
    .sort((a, b) => b.count - a.count);
});

const yearBars = computed(() => {
  const years = (paperResult.value?.books ?? [])
    .map((p) => parseInt((p.book_info?.pub_date ?? "0").slice(0, 4)))
    .filter((y) => y > 1900);
  if (!years.length) return [];
  const min = Math.min(...years),
    max = Math.max(...years);
  const buckets = 12;
  const counts = Array(buckets).fill(0);
  years.forEach((y) => {
    counts[
      Math.min(buckets - 1, Math.floor(((y - min) / (max - min + 1)) * buckets))
    ]++;
  });
  const maxCount = Math.max(...counts, 1);
  const fromY = parseInt(filters.yearFrom || "0"),
    toY = parseInt(filters.yearTo || "9999");
  return counts.map((c, i) => {
    const bucketYear = min + Math.floor((i / buckets) * (max - min + 1));
    return {
      h: Math.max(8, Math.round((c / maxCount) * 100)),
      inRange:
        !filters.yearFrom && !filters.yearTo
          ? true
          : bucketYear >= fromY && bucketYear <= toY,
    };
  });
});

async function handleSearch(q?: string) {
  const query = (q ?? currentQuery.value).trim();
  if (!query || loading.value) return;
  currentQuery.value = query;
  loading.value = true;
  error.value = null;
  paperResult.value = null;
  currentPage.value = 1;
  clearFilters();
  try {
    const data = await $fetch<BookSearchResponse>(
      `${config.public.apiBase}/papers/search`,
      {
        method: "POST",
        headers: sessionId.value ? { "x-session-id": sessionId.value } : {},
        body: {
          query,
          mode: "book",
          top_k: 20,
          use_rewrite: true,
          use_rerank: true,
        },
      },
    );
    paperResult.value = data;
  } catch (e: any) {
    error.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
    paperResult.value = { mode: "book", query, books: [], elapsed_ms: 0 };
  } finally {
    loading.value = false;
  }
}

function resetSearch() {
  paperResult.value = null;
  error.value = null;
  currentQuery.value = "";
  clearFilters();
  currentPage.value = 1;
}

function clearFilters() {
  filters.genres = [];
  filters.yearFrom = "";
  filters.yearTo = "";
  filters.journals = [];
  filters.languages = [];
}
function toggleGenre(v: string) {
  const i = filters.genres.indexOf(v);
  if (i === -1) filters.genres.push(v);
  else filters.genres.splice(i, 1);
  currentPage.value = 1;
}
function toggleJournal(v: string) {
  const i = filters.journals.indexOf(v);
  if (i === -1) filters.journals.push(v);
  else filters.journals.splice(i, 1);
  currentPage.value = 1;
}
function toggleLanguage(v: string) {
  const i = filters.languages.indexOf(v);
  if (i === -1) filters.languages.push(v);
  else filters.languages.splice(i, 1);
  currentPage.value = 1;
}
function openChat(paper: BookChunkGroup) {
  if (chatPaper.value?.book_id === paper.book_id) {
    chatPaper.value = null;
  } else {
    mountedChats.value.add(paper.book_id);
    chatPaper.value = paper;
  }
}

onMounted(() => {
  const stored = localStorage.getItem("sid");
  if (stored) sessionId.value = stored;

  if (topBarRef.value) {
    const ro = new ResizeObserver((entries) => {
      topBarHeight.value = Math.round(
        entries[0]?.borderBoxSize?.[0]?.blockSize ??
          entries[0]?.contentRect.height ??
          84,
      );
    });
    ro.observe(topBarRef.value);
    onUnmounted(() => ro.disconnect());
  }

  nextTick(() => {
    if (!segRef.value) return;
    const activeBtn = segRef.value.querySelector(
      '[data-key="paper"]',
    ) as HTMLElement;
    if (!activeBtn) return;
    const wrap = segRef.value.getBoundingClientRect();
    const rect = activeBtn.getBoundingClientRect();
    thumbStyle.value = {
      left: rect.left - wrap.left + "px",
      width: rect.width + "px",
    };
  });

  const onDoc = (e: MouseEvent) => {
    if (sortRef.value && !sortRef.value.contains(e.target as Node))
      sortMenuOpen.value = false;
  };
  document.addEventListener("mousedown", onDoc);
  onUnmounted(() => document.removeEventListener("mousedown", onDoc));
});

watch(currentPage, () => window.scrollTo({ top: 0, behavior: "smooth" }));
</script>

<style scoped>
/* ── 전체 페이지 ─────────────────────────────────── */
.page {
  min-height: 100vh;
  background: var(--bg);
}

/* ── 상단 바 ─────────────────────────────────────── */
.top-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid var(--line);
  background: rgba(246, 246, 244, 0.95);
  backdrop-filter: blur(10px);
}
.top-bar-inner {
  max-width: 1290px;
  margin: 0 auto;
  min-height: 84px;
  display: flex;
  align-items: center;
}
.top-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 14px;
  height: 80%;
  flex: 0 0 220px;
  background: transparent;
  border: none;
  cursor: pointer;
  overflow: hidden;
  white-space: nowrap;
  flex-shrink: 0;
  transition: flex-basis 0.25s ease;
}
.top-brand-skovix {
  height: 36px;
  width: auto;
  flex-shrink: 0;
}
.top-search-area {
  flex: 1;
  min-width: 0;
  padding: 20px;
}
.top-search-area :deep(.search-input-wrap) {
  max-width: none;
  margin: 0;
}
.top-end {
  flex-shrink: 0;
  transition: flex-basis 0.25s ease;
}

/* ── 3단 그리드 ──────────────────────────────────── */
.app-layout {
  display: grid;
  min-height: v-bind("'calc(100vh - ' + topBarHeight + 'px)'");
  max-width: 1290px;
  margin: 0 auto;
  transition: grid-template-columns 0.25s ease;
}

/* ── 사이드바 공통 ──────────────────────────────── */
.sidebar {
  position: sticky;
  top: v-bind("topBarHeight + 'px'");
  height: v-bind("'calc(100vh - ' + topBarHeight + 'px)'");
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.sidebar-left {
  border-right: 1px solid var(--line);
}
.sidebar-right {
  border-left: 1px solid var(--line);
  min-width: 0;
}

/* ── 사이드바 토글 버튼 ─────────────────────────── */
.sidebar-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: calc(100% - 16px);
  margin: 8px 8px 4px;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: #a1a1aa;
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  transition:
    background 0.15s,
    color 0.15s;
  flex-shrink: 0;
}
.sidebar-toggle:hover {
  background: #f0f0f1;
  color: #52525b;
}
.sidebar-toggle.collapsed {
  justify-content: center;
}
.sidebar-toggle svg {
  flex-shrink: 0;
}

/* ── 사이드바 본문 ──────────────────────────────── */
.sidebar-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-width: 0;
}

/* ── 메인 콘텐츠 ────────────────────────────────── */
.main-content {
  min-width: 0;
  /* 본문 독립 스크롤 컨테이너 (.page 가 overflow:hidden 이라 없으면 본문이 잘려 스크롤바 사라짐) */
  height: v-bind("'calc(100vh - ' + topBarHeight + 'px)'");
  overflow-y: auto;
  overflow-x: hidden;
}

/* ── 페이드 텍스트 전환 ──────────────────────────── */
.fade-text-enter-active,
.fade-text-leave-active {
  transition:
    opacity 0.15s,
    transform 0.15s;
}
.fade-text-enter-from,
.fade-text-leave-to {
  opacity: 0;
  transform: translateX(-4px);
}

/* ── 랜딩 ──────────────────────────────────────── */
.landing {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  /* main-content 높이를 정확히 채움 (하드코딩 84px ↔ 실제 상단바 불일치 스크롤바 제거) */
  min-height: 100%;
  padding: 24px;
  gap: 32px;
}
.logo-area {
  text-align: center;
}
.title {
  font-size: 26px;
  font-weight: 700;
  color: #18181b;
}
.subtitle {
  font-size: 15px;
  color: #71717a;
  margin-top: 6px;
}

/* ── 세그먼티드 토글 ─────────────────────────────── */
.seg {
  display: inline-flex;
  padding: 5px;
  background: #eeeaf6;
  border-radius: 999px;
  position: relative;
  box-shadow: inset 0 0 0 1px rgba(124, 77, 255, 0.06);
}
.seg-thumb {
  position: absolute;
  top: 5px;
  bottom: 5px;
  border-radius: 999px;
  background: #fff;
  box-shadow:
    0 2px 6px rgba(124, 77, 255, 0.18),
    0 0 0 1px rgba(124, 77, 255, 0.08);
  transition:
    left 280ms cubic-bezier(0.4, 0.2, 0.2, 1),
    width 280ms;
  z-index: 0;
}
.seg-btn {
  position: relative;
  z-index: 1;
  padding: 9px 22px;
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  border-radius: 999px;
  border: none;
  background: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: color 200ms;
  font-family: inherit;
}
.seg-btn.is-active {
  color: var(--violet-deep);
}
.seg-btn .ico {
  width: 16px;
  height: 16px;
}

/* ── 결과 페이지 ────────────────────────────────── */
.results-page {
  padding: 0 24px 48px;
}

/* ── 검색 메타 ──────────────────────────────────── */
.search-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 0 16px;
  font-size: 11px;
  color: #8a8a91;
  flex-wrap: wrap;
}
.query-display {
  font-size: 18px;
  font-weight: 600;
  color: #18181b;
}
.elapsed {
  font-size: 12px;
}
.rewritten {
  font-size: 13px;
  color: var(--violet-deep, #4a2ed6);
}

/* ── 패싯 그룹 ───────────────────────────────────── */
.facet-clear-row {
  display: flex;
  justify-content: flex-end;
  padding: 8px 12px 4px;
}
.facets-clear {
  font-size: 12px;
  color: var(--violet-deep, #4a2ed6);
  font-weight: 600;
  background: none;
  border: none;
  cursor: pointer;
}
.facets-clear:hover {
  text-decoration: underline;
}
.facet-group {
  border-top: 1px solid var(--line);
  padding: 14px 12px 12px;
}
.facet-group:first-of-type {
  border-top: none;
}
.facet-group h5 {
  margin: 0 0 10px;
  font-size: 11px;
  color: var(--ink-4);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.facet-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  cursor: pointer;
  color: var(--ink-2);
  font-size: 13px;
}
.facet-row input[type="checkbox"] {
  accent-color: var(--violet, #7c4dff);
  margin: 0;
}
.facet-row:hover .facet-name {
  color: var(--violet-deep, #4a2ed6);
}
.facet-row.is-on .facet-name {
  color: var(--violet-deep, #4a2ed6);
  font-weight: 600;
}
.facet-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.facet-count {
  font-size: 11px;
  color: var(--ink-4);
  font-variant-numeric: tabular-nums;
}
.facet-more {
  font-size: 12px;
  color: var(--violet-deep, #4a2ed6);
  cursor: pointer;
  margin-top: 6px;
  background: none;
  border: none;
  padding: 0;
  font-family: inherit;
}
.facet-more:hover {
  text-decoration: underline;
}
.year-bars {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 36px;
  margin: 10px 0 4px;
}
.year-bar {
  flex: 1;
  background: var(--violet-soft, #b9a7ff);
  border-radius: 2px;
  opacity: 0.7;
  transition: background 160ms;
}
.year-bar.is-out {
  background: #ececec;
}
.year-range {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 4px;
}
.year-range input {
  flex: 1;
  height: 28px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0 6px;
  font-size: 12px;
  text-align: center;
  outline: none;
  font-family: monospace;
  width: 0;
}
.year-range input:focus {
  border-color: var(--violet-soft, #b9a7ff);
}
.year-range .dash {
  color: var(--ink-4);
}

/* ── 적용된 필터 칩 ─────────────────────────────── */
.applied {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 10px;
}
.applied-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--violet-deep, #4a2ed6);
  background: var(--lilac, #f1edff);
  border: 1px solid #e1d5ff;
  padding: 3px 6px 3px 9px;
  border-radius: 999px;
}
.applied-chip .x {
  cursor: pointer;
  opacity: 0.6;
}
.applied-chip .x:hover {
  opacity: 1;
}

/* ── 툴바 ───────────────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 8px 0 16px;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 10px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.count {
  font-size: 13px;
  color: var(--ink-3);
}
.count strong {
  color: var(--ink);
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-right: 2px;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.facets-reopen {
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 7px;
  font-size: 13px;
  background: #fff;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-2);
  cursor: pointer;
  font-family: inherit;
}
.facets-reopen .badge {
  background: var(--violet, #7c4dff);
  color: #fff;
  font-size: 10px;
  padding: 2px 5px;
  border-radius: 999px;
  font-weight: 600;
}
.sort {
  position: relative;
}
.sort-btn {
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 7px;
  font-size: 13px;
  background: #fff;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-2);
  cursor: pointer;
  font-family: inherit;
}
.sort-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  width: 160px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 8px 20px rgba(14, 14, 20, 0.1);
  padding: 4px;
  z-index: 20;
}
.sort-menu button {
  width: 100%;
  text-align: left;
  padding: 7px 10px;
  border-radius: 5px;
  font-size: 13px;
  color: var(--ink-2);
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
}
.sort-menu button:hover {
  background: var(--bg, #f6f6f4);
}
.sort-menu button.is-on {
  color: var(--violet-deep, #4a2ed6);
  font-weight: 600;
}

/* ── 탐구 카드 ──────────────────────────────────── */
.explore-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ec {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 16px 18px;
  display: grid;
  grid-template-columns: 1fr 80px;
  column-gap: 18px;
  cursor: pointer;
  transition:
    border-color 160ms,
    box-shadow 160ms;
}
.ec:hover {
  border-color: var(--violet-soft, #b9a7ff);
  box-shadow: 0 4px 14px rgba(124, 77, 255, 0.07);
}
.ec:hover .ec-title {
  color: var(--violet-deep, #4a2ed6);
}
.ec-main {
  min-width: 0;
}
.ec-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 7px;
}
.pill {
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--ink-3);
  padding: 2px 6px;
  background: var(--bg, #f6f6f4);
  border: 1px solid var(--line);
  border-radius: 4px;
}
.pill.kdc {
  color: var(--violet-deep, #4a2ed6);
  background: var(--lilac, #f1edff);
  border-color: #ebe4ff;
}
.ec-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--ink);
  margin: 0 0 3px;
  transition: color 160ms;
}
.ec-title-en {
  font-size: 12px;
  color: var(--ink-3);
  margin-bottom: 8px;
  font-style: italic;
}
.ec-meta {
  font-size: 12px;
  color: var(--ink-3);
  display: flex;
  flex-wrap: wrap;
  gap: 3px 6px;
  margin-bottom: 8px;
}
.ec-meta .author {
  color: var(--ink-2);
  font-weight: 500;
}
.ec-meta .venue {
  color: var(--violet-deep, #4a2ed6);
  font-weight: 600;
}
.ec-meta .dot {
  color: var(--line);
}
.ec-abstract {
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink-2);
  margin: 0 0 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ec-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.ec-btn {
  height: 28px;
  padding: 0 9px;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  cursor: pointer;
  font-family: inherit;
  text-decoration: none;
  transition: all 140ms;
}
.ec-btn:hover {
  background: var(--bg, #f6f6f4);
}
.ec-btn.accent {
  background: var(--lilac, #f1edff);
  color: var(--violet-deep, #4a2ed6);
  border-color: #e1d5ff;
}
.ec-btn.accent:hover {
  background: #e8e1ff;
}
.ec-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  padding-left: 14px;
  border-left: 1px dashed var(--line);
}
.ec-score {
  font-size: 20px;
  font-weight: 800;
  color: var(--violet-deep, #4a2ed6);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.pct-unit {
  font-size: 12px;
  font-weight: 400;
}
.ec-score-lbl {
  font-size: 10px;
  color: var(--ink-3);
  letter-spacing: 0.04em;
}
.barmini {
  height: 3px;
  width: 100%;
  background: #f0eef5;
  border-radius: 999px;
  overflow: hidden;
}
.barmini i {
  display: block;
  height: 100%;
  background: linear-gradient(
    90deg,
    var(--violet, #7c4dff),
    var(--rose, #ff5cad)
  );
}
.ec-year {
  font-size: 12px;
  color: var(--ink-3);
  margin-top: 4px;
}

/* ── 페이지네이션 ────────────────────────────────── */
.pager {
  margin-top: 22px;
  padding-bottom: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.pager-info {
  font-size: 12px;
  color: var(--ink-3);
}
.pager-nav {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}
.page-btn {
  min-width: 30px;
  height: 30px;
  border-radius: 7px;
  font-size: 13px;
  color: var(--ink-2);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 7px;
  border: 1px solid transparent;
  background: none;
  cursor: pointer;
  font-family: monospace;
}
.page-btn:hover:not(:disabled) {
  background: var(--lilac, #f1edff);
  color: var(--violet-deep, #4a2ed6);
}
.page-btn.is-on {
  background: var(--ink);
  color: #fff;
}
.page-btn:disabled {
  color: var(--ink-4);
  cursor: default;
}
.page-ellipsis {
  color: var(--ink-4);
  padding: 0 3px;
  font-family: monospace;
}

/* ── 로딩 / 에러 / 빈 결과 ───────────────────────── */
.loading-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 0;
  gap: 12px;
  color: var(--ink-3);
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--line);
  border-top-color: var(--violet, #7c4dff);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.error-area {
  padding: 40px 0;
  text-align: center;
  color: var(--ink-3);
}
.empty {
  text-align: center;
  padding: 60px 0;
  color: var(--ink-3);
  font-size: 15px;
}

/* ── 카드 + 인라인 채팅 래퍼 ────────────────────── */
.paper-item {
  display: flex;
  flex-direction: column;
}
.ec.is-chat-open {
  border-color: var(--violet-soft, #b9a7ff);
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  border-bottom-color: transparent;
}
.paper-item :deep(.book-chat) {
  border-top: none;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
  border-color: var(--violet-soft, #b9a7ff);
}
</style>
