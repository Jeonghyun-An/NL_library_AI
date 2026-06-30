<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <!-- 랜딩 (검색 전) -->
    <main v-if="!hasResults" class="skx-contents">
      <div class="skx-contents__inner">
        <h1 class="skx-hero">논문 의미 기반 검색</h1>
        <div class="skx-search">
          <div class="skx-search__box">
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
          <section class="skx-pai" aria-label="AI 검색 결과">
            <div class="skx-pai__header">
              <img
                class="skx-pai__logo"
                src="/img/logo-mark.svg"
                alt="SKOVIX AI"
              />
              <span class="skx-pai__hd-text">AI 검색 결과</span>
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
                      <p class="skx-pai-ref__title">{{ ref.title }}</p>
                      <p class="skx-pai-ref__author">{{ ref.authors }}</p>
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
          </section>

          <!-- 논문 목록 -->
          <section class="skx-paper-section" aria-label="논문 검색 결과 목록">
            <!-- 헤더 -->
            <div class="skx-paper-head">
              <div class="skx-paper-count">
                <span class="skx-paper-count__label">총</span>
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
                    정합성순
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
              >
                <div class="skx-paper-item__left">
                  <div class="skx-paper-tags">
                    <span
                      v-if="paper.book_info?.grade"
                      class="skx-ptag skx-ptag--kci"
                    >
                      {{ paper.book_info.grade }}
                    </span>
                    <span class="skx-ptag skx-ptag--score">
                      정합성 {{ Math.round((paper.best_score || 0) * 100) }}%
                    </span>
                  </div>
                  <h3
                    class="skx-paper-title"
                    style="cursor: pointer"
                    @click="goToDetail(paper)"
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
                        paper.book_info.pub_date
                      }}</span>
                    </template>
                    <template v-if="paper.book_info?.publisher">
                      <span class="skx-dot"></span>
                      <span class="skx-paper-meta-text">{{
                        paper.book_info.publisher
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
                  </div>
                </div>
                <div class="skx-paper-item__right">
                  <div class="skx-paper-item__btn-row">
                    <a
                      v-if="paper.book_info?.url"
                      :href="paper.book_info.url"
                      target="_blank"
                      rel="noopener"
                      class="skx-btn-pview"
                      @click.stop
                      >원문 보기</a
                    >
                    <button
                      v-else
                      type="button"
                      class="skx-btn-pview"
                      @click.stop="showToast('원문 링크가 없습니다.')"
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
                    @click.stop="goToDetail(paper)"
                  >
                    <img src="/img/ico-chat.svg" alt="" />
                    논문과 대화하기
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

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import type { BookSearchResponse } from "~/types/search";

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

// ── 검색 상태 ────────────────────────────────────────────────
const currentQuery = ref("");
const loading = ref(false);
const error = ref<string | null>(null);
const paperResult = ref<BookSearchResponse | null>(null);

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
  if (selectedGrade.value === "all") return sortedPapers.value;
  return sortedPapers.value.filter(
    (b) => b.book_info?.grade === selectedGrade.value,
  );
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

function goToDetail(paper: any) {
  navigateTo(
    `/papers/${paper.book_id}?q=${encodeURIComponent(currentQuery.value)}`,
  );
}

// ── 검색 ─────────────────────────────────────────────────────
async function handleSearch(q?: string) {
  const query = (q ?? currentQuery.value).trim();
  if (!query || loading.value) return;
  currentQuery.value = query;
  loading.value = true;
  error.value = null;
  paperResult.value = null;
  aiText.value = "";
  aiRefs.value = [];
  aiExpanded.value = false;
  currentPage.value = 1;
  sortBy.value = "relevance";

  try {
    const data = await $fetch<BookSearchResponse>(`${apiBase}/papers/search`, {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 20,
        use_rewrite: true,
        use_rerank: true,
      },
    });
    paperResult.value = data;
    // AI 요약 SSE 병렬 시작
    if (data.books?.length) {
      streamAiSummary(query, data.books);
    }
  } catch (e: any) {
    error.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
    paperResult.value = { mode: "book", query, books: [], elapsed_ms: 0 };
  } finally {
    loading.value = false;
  }
}

// ── AI 요약 SSE ───────────────────────────────────────────────
async function streamAiSummary(query: string, books: any[]) {
  aiLoading.value = true;
  const papers = books.slice(0, 5).map((b) => ({
    book_id: b.book_id,
    title: b.book_info?.title || "",
    authors:
      b.book_info?.personal_author || b.book_info?.corporate_author || "",
    best_chunk_text: "",
  }));
  try {
    const resp = await fetch(`${apiBase}/papers/summary/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, papers }),
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
          if (evt.text) aiText.value += evt.text;
          if (evt.sources) aiRefs.value = evt.sources;
        } catch {}
      }
    }
  } catch {
    /* ignore */
  } finally {
    aiLoading.value = false;
  }
}

// ── 페이지당 개수 드롭다운 닫기 + URL 초기 검색 ───────────────
onMounted(() => {
  document.addEventListener("click", () => {
    perpageOpen.value = false;
  });
  const route = useRoute();
  const q = route.query.q as string | undefined;
  if (q?.trim()) handleSearch(q.trim());
});

watch(currentPage, () => window.scrollTo({ top: 0, behavior: "smooth" }));
</script>
