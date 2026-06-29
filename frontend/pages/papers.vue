<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <!-- Landing (no results yet) -->
    <main v-if="!hasResults" class="skx-contents">
      <div class="skx-contents__inner">
        <h1 class="skx-hero">논문 의미 기반 검색</h1>
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

    <!-- Results -->
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
        <div v-if="loading" style="padding:40px;text-align:center">
          <img src="/img/ico-spinner.svg" alt="" style="width:32px">
          <p style="margin-top:12px">논문을 탐색하고 있습니다...</p>
        </div>

        <div v-else-if="error" style="padding:20px;color:#c00">{{ error }}</div>

        <template v-else>
          <!-- 툴바 -->
          <div class="skx-result-toolbar">
            <span class="skx-result-count">
              <strong>{{ filteredPapers.length.toLocaleString() }}</strong>편 검색됨
            </span>
            <div class="skx-sort">
              <button type="button" class="skx-sort__btn" @click="sortMenuOpen = !sortMenuOpen">
                <img src="/img/ico-sort-off.svg" alt="">
                {{ SORT_LABELS[sortBy] || sortBy }}
              </button>
              <ul v-if="sortMenuOpen" class="skx-sort__menu">
                <li v-for="(label, key) in SORT_LABELS" :key="key">
                  <button type="button" :class="sortBy === key && 'is-on'"
                    @click="sortBy = key; sortMenuOpen = false">{{ label }}</button>
                </li>
              </ul>
            </div>
          </div>

          <div v-if="!filteredPapers.length" style="padding:60px;text-align:center;color:#bbb">
            검색 결과가 없습니다.
          </div>

          <div v-else class="skx-paper-list">
            <div v-for="paper in pagedPapers" :key="paper.book_id" class="skx-paper-item">
              <article class="skx-paper-card"
                style="cursor:pointer"
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
                    <span v-if="paper.book_info?.personal_author" class="skx-meta-text">{{ paper.book_info.personal_author }}</span>
                    <span v-if="paper.book_info?.publisher" class="skx-dot"></span>
                    <span v-if="paper.book_info?.publisher" class="skx-meta-text">{{ paper.book_info.publisher }}</span>
                    <span v-if="paper.book_info?.pub_date" class="skx-dot"></span>
                    <span v-if="paper.book_info?.pub_date" class="skx-meta-text">{{ paper.book_info.pub_date }}</span>
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
                    {{ Math.round((paper.best_score || 0) * 100) }}<span>%</span>
                  </div>
                  <div class="skx-paper-card__score-lbl">적합도</div>
                </div>
              </article>
            </div>
          </div>

          <!-- 페이지네이션 -->
          <div v-if="totalPages > 1" class="skx-pager">
            <div class="skx-pager__nav">
              <button class="skx-page-btn" :disabled="currentPage === 1" @click="currentPage--">
                <img src="/img/ico-page-prev.svg" alt="이전">
              </button>
              <template v-for="p in pageButtons" :key="p">
                <span v-if="p === '...'" class="skx-page-ellipsis">…</span>
                <button v-else class="skx-page-btn" :class="p === currentPage && 'is-on'"
                  @click="currentPage = Number(p)">{{ p }}</button>
              </template>
              <button class="skx-page-btn" :disabled="currentPage === totalPages" @click="currentPage++">
                <img src="/img/ico-page-next.svg" alt="다음">
              </button>
            </div>
          </div>
        </template>
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
import type { BookChunkGroup, BookSearchResponse } from "~/types/search";

const config = useRuntimeConfig();

const currentQuery = ref("");
const loading = ref(false);
const error = ref<string | null>(null);
const paperResult = ref<BookSearchResponse | null>(null);
const sortRef = ref<HTMLElement | null>(null);

const sortMenuOpen = ref(false);
const showAllJournals = ref(false);
const currentPage = ref(1);

const sessionId = useState<string | null>("sessionId", () => null);

// ── Publishing additions ──────────────────────────────────────
const toast = ref('')
function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

const GENRE_LABELS: Record<string, string> = {
  paper: '학술논문', thesis: '학위논문', report: '연구보고서',
  manual: '매뉴얼', book: '단행본', other: '기타',
}

const SORT_LABELS: Record<string, string> = {
  relevance: '관련도순',
  date_desc: '최신순',
  date_asc: '오래된순',
  citations: '인용수순',
}
// ── End publishing additions ──────────────────────────────────

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

const sortedPapers = computed(() => {
  if (!paperResult.value) return [];
  const books = [...paperResult.value.books];
  if (sortBy.value === "relevance")
    return books.sort((a, b) => b.best_score - a.best_score);
  if (sortBy.value === "date_desc")
    return books.sort((a, b) =>
      (b.book_info?.pub_date ?? "").localeCompare(a.book_info?.pub_date ?? ""),
    );
  if (sortBy.value === "date_asc")
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
  const total = totalPages.value
  const cur = currentPage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | string)[] = [1]
  if (cur > 3) pages.push('...')
  for (let i = Math.max(2, cur - 1); i <= Math.min(total - 1, cur + 1); i++) pages.push(i)
  if (cur < total - 2) pages.push('...')
  pages.push(total)
  return pages
})

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

onMounted(() => {
  const stored = localStorage.getItem("sid");
  if (stored) sessionId.value = stored;

  const onDoc = (e: MouseEvent) => {
    if (sortRef.value && !sortRef.value.contains(e.target as Node))
      sortMenuOpen.value = false;
  };
  document.addEventListener("mousedown", onDoc);
  onUnmounted(() => document.removeEventListener("mousedown", onDoc));
});

watch(currentPage, () => window.scrollTo({ top: 0, behavior: "smooth" }));
</script>
