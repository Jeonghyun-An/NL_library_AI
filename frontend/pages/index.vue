<template>
  <div class="page">
    <!-- ══ 전체 폭 상단 바 ════════════════════════════════════════ -->
    <header class="top-bar" ref="topBarRef">
      <div class="top-bar-inner">
        <button class="top-brand" @click="reset">
          <img
            src="/landsoft-ai-gradient.svg"
            alt="NL-Lib"
            class="top-brand-icon"
          />
          <span class="top-brand-name"
            >NL<span class="top-brand-sub">-Lib</span></span
          >
        </button>

        <div class="top-search-area">
          <SearchInput
            v-if="result || loading || error"
            ref="searchInputRef"
            v-model="currentQuery"
            :disabled="loading"
            @submit="handleSearch"
          />
        </div>

        <div
          class="top-end"
          :style="{ flexBasis: rightOpen ? 'clamp(180px,18vw,230px)' : '44px' }"
        />
      </div>
    </header>

    <!-- ══ 3단 그리드 레이아웃 ═══════════════════════════════════ -->
    <div class="app-layout" :style="{ gridTemplateColumns: gridCols }">
      <!-- ══ 왼쪽 사이드바: 검색 기록 ══════════════════════════ -->
      <aside class="sidebar sidebar-left">
        <button
          class="sidebar-toggle"
          :class="{ collapsed: !leftOpen }"
          :title="leftOpen ? '기록 패널 닫기' : '기록 패널 열기'"
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
            <span v-if="leftOpen">검색 기록</span>
          </Transition>
        </button>

        <div v-show="leftOpen" class="sidebar-body">
          <ClientOnly>
            <ChatHistory
              :history="history"
              :current-id="currentHistoryId"
              @select="restoreHistory"
              @clear="clearHistory"
            />
            <template #fallback><div class="ch-placeholder" /></template>
          </ClientOnly>
        </div>
      </aside>

      <!-- ══ 메인 콘텐츠 ═══════════════════════════════════════ -->
      <main class="main-content">
        <!-- 랜딩 -->
        <div v-if="!result && !loading && !error" class="landing">
          <div class="logo-area">
            <h1 class="title">국립중앙도서관 의미 기반 검색</h1>
            <p class="subtitle">읽고 싶은 책을 자연어로 검색해보세요</p>
          </div>
          <SearchInput
            placeholder="예: 국가 안보를 강화하는 데 도움 되는 지침서엔 뭐가 있을까?"
            :disabled="loading"
            @submit="handleSearch"
          />
        </div>

        <!-- 결과 (상단 바에 검색창이 있으므로 별도 헤더 없음) -->
        <div v-else class="results-page">
          <div v-if="loading" class="loading-area">
            <div class="spinner" />
            <p>도서를 찾고 있습니다...</p>
          </div>

          <div v-else-if="error" class="error-area">
            <p>{{ error }}</p>
            <button @click="handleSearch(currentQuery)">다시 검색</button>
          </div>

          <div v-else class="results-content">
            <div class="search-meta">
              <span class="query-display">"{{ result?.query }}"</span>
              <span class="elapsed">{{ result?.elapsed_ms.toFixed(0) }}ms</span>
              <span v-if="result?.rewritten_query" class="rewritten">
                → {{ result?.rewritten_query }}
              </span>
            </div>

            <template v-if="bookResult">
              <div v-if="!bookResult.books.length" class="empty">
                검색 결과가 없습니다. 다른 검색어를 시도해보세요.
              </div>
              <template v-else>
                <TopResult
                  v-if="topBook"
                  :book="topBook"
                  :answer="streamingReason"
                  :keywords="streamingKeywords"
                  :is-streaming="isStreamingReason"
                />
                <div v-if="bookResult.books.length > 1" class="more-section">
                  <h3 class="more-title">함께 추천하는 도서</h3>
                  <div class="slider-wrap">
                    <button class="slider-arrow" @click="slideLeft">
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2.5"
                      >
                        <polyline points="15 18 9 12 15 6" />
                      </svg>
                    </button>
                    <div class="book-slider" ref="sliderRef">
                      <BookCard
                        v-for="book in bookResult.books.slice(1).filter(b => b.best_score >= 0.1)"
                        :key="book.book_id"
                        :book="book"
                        @select="selectSecondaryBook"
                      />
                    </div>
                    <button class="slider-arrow" @click="slideRight">
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2.5"
                      >
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    </button>
                  </div>
                </div>

                <div
                  v-if="selectedBook"
                  class="selected-section"
                  ref="selectedSectionRef"
                >
                  <div class="selected-header">
                    <span class="selected-pill">추천 도서 살펴보기</span>
                    <span class="selected-title">{{
                      selectedBook.book_info?.title || selectedBook.book_id
                    }}</span>
                    <button class="close-btn" @click="selectedBook = null">
                      닫기
                    </button>
                  </div>
                  <TopResult
                    :book="selectedBook"
                    :answer="selectedStreamingReason"
                    :keywords="selectedKeywords"
                    :is-streaming="isSelectedStreaming"
                  />
                </div>
              </template>
            </template>

            <template v-if="chunkResult">
              <div v-if="chunkResult.answer" class="chunk-answer">
                <div class="answer-label">AI 답변</div>
                <div v-html="chunkResult.answer.replace(/\n/g, '<br>')" />
              </div>
              <div v-if="!chunkResult.chunks.length" class="empty">
                검색 결과가 없습니다.
              </div>
              <div v-else class="chunk-list">
                <div
                  v-for="chunk in chunkResult.chunks"
                  :key="chunk.chunk_id"
                  class="chunk-item"
                >
                  <div class="chunk-source">
                    {{ chunk.book_id }} · p.{{ chunk.page_start }}-{{
                      chunk.page_end
                    }}
                    <span class="chunk-score"
                      >{{ (chunk.score * 100).toFixed(0) }}%</span
                    >
                  </div>
                  <p class="chunk-text">{{ chunk.text }}</p>
                </div>
              </div>
            </template>
          </div>
        </div>
      </main>

      <!-- ══ 오른쪽 사이드바: 카테고리 아코디언 ══════════════ -->
      <aside class="sidebar sidebar-right">
        <button
          class="sidebar-toggle right"
          :class="{ collapsed: !rightOpen }"
          :title="rightOpen ? '카테고리 패널 닫기' : '카테고리 패널 열기'"
          @click="rightOpen = !rightOpen"
        >
          <Transition name="fade-text">
            <span v-if="rightOpen">카테고리별 추천</span>
          </Transition>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <polyline
              :points="rightOpen ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"
            />
          </svg>
        </button>

        <div v-show="rightOpen" class="sidebar-body">
          <CategoryAccordion :books="bookResult?.books ?? []" />
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { type Ref } from "vue";
import { useSearch } from "~/composables/useSearch";
import { useSearchHistory } from "~/composables/useSearchHistory";
import type {
  BookChunkGroup,
  BookSearchResponse,
  ChunkSearchResponse,
  SearchResponse,
} from "~/types/search";
import type { HistoryEntry } from "~/types/history";

const { history, setHistory, clearHistory } = useSearchHistory();
const { loading, error, result, search, reset, generateUUID } = useSearch();
const config = useRuntimeConfig();

const currentQuery = ref("");
const currentHistoryId = ref<string | null>(null);
const leftOpen = ref(true);
const rightOpen = ref(false);
const searchInputRef = ref<{ focus: () => void } | null>(null);
const streamingReason = ref("");
const streamingKeywords = ref<string[]>([]);
const isStreamingReason = ref(false);
const selectedBook = ref<BookChunkGroup | null>(null);
const selectedStreamingReason = ref("");
const selectedKeywords = ref<string[]>([]);
const isSelectedStreaming = ref(false);
const sliderRef = ref<HTMLElement | null>(null);
const selectedSectionRef = ref<HTMLElement | null>(null);
const topBarRef = ref<HTMLElement | null>(null);
const topBarHeight = ref(84);

const gridCols = computed(() => {
  const l = leftOpen.value ? "220px" : "44px";
  const r = rightOpen.value ? "clamp(180px, 18vw, 230px)" : "44px";
  return `${l} 1fr ${r}`;
});

const bookResult = computed(() => {
  if (!result.value || result.value.mode !== "book") return null;
  return result.value as BookSearchResponse;
});

const chunkResult = computed(() => {
  if (!result.value || result.value.mode !== "chunk") return null;
  return result.value as ChunkSearchResponse;
});

const topBook = computed(() => bookResult.value?.books?.[0] ?? null);

const sessionId = useState<string | null>("sessionId", () => null);

async function loadHistory() {
  if (!sessionId.value) return;
  try {
    const data = await $fetch<HistoryEntry[]>(
      `/api/books/history/${sessionId.value}`,
    );
    setHistory(data);
  } catch (e) {
    console.warn("히스토리 로드 실패:", e);
  }
}

onMounted(() => {
  const stored = localStorage.getItem("sid");
  if (stored) {
    sessionId.value = stored;
  } else {
    const sid = generateUUID();
    sessionId.value = sid;
    localStorage.setItem("sid", sid);
  }
  loadHistory();

  if (topBarRef.value) {
    const ro = new ResizeObserver((entries) => {
      const e = entries[0];
      if (!e) return;
      topBarHeight.value = Math.round(
        e.borderBoxSize?.[0]?.blockSize ?? e.contentRect.height,
      );
    });
    ro.observe(topBarRef.value);
    onUnmounted(() => ro.disconnect());
  }
});

async function handleSearch(query: string) {
  currentQuery.value = query;
  currentHistoryId.value = null;
  streamingReason.value = "";
  streamingKeywords.value = [];
  isStreamingReason.value = false;
  selectedBook.value = null;

  await search(query, "book", 10);
  await loadHistory();

  if (bookResult.value?.books?.[0]) {
    doStreamReason(
      query,
      bookResult.value.rewritten_query ?? query,
      bookResult.value.books[0],
      streamingReason,
      streamingKeywords,
      isStreamingReason,
    );
  }

  nextTick(() => searchInputRef.value?.focus());
}

async function doStreamReason(
  query: string,
  rewrittenQuery: string,
  book: BookChunkGroup,
  reasonRef: Ref<string>,
  keywordsRef: Ref<string[]>,
  streamingRef: Ref<boolean>,
) {
  streamingRef.value = true;
  reasonRef.value = "";
  keywordsRef.value = [];

  const topChunkTexts = [...book.chunks]
    .sort((a, b) => (b.rerank_score ?? b.score) - (a.rerank_score ?? a.score))
    .slice(0, 15)
    .map((c) => c.text);

  try {
    const response = await fetch(
      `${config.public.apiBase}/books/reason/stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          rewritten_query: rewrittenQuery,
          book_id: book.book_id,
          chunk_texts: topChunkTexts,
        }),
      },
    );

    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      for (const line of text.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") return;
        try {
          const parsed = JSON.parse(data);
          if (parsed.keywords) {
            keywordsRef.value = parsed.keywords;
          } else if (parsed.text) {
            reasonRef.value += parsed.text;
          }
        } catch {}
      }
    }
  } catch (e) {
    console.error("추천 이유 스트리밍 실패:", e);
  } finally {
    streamingRef.value = false;
  }
}

function selectSecondaryBook(book: BookChunkGroup) {
  selectedBook.value = book;
  selectedStreamingReason.value = "";
  selectedKeywords.value = [];
  doStreamReason(
    currentQuery.value,
    bookResult.value?.rewritten_query ?? currentQuery.value,
    book,
    selectedStreamingReason,
    selectedKeywords,
    isSelectedStreaming,
  );
  nextTick(() => {
    selectedSectionRef.value?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  });
}

function slideLeft() {
  const el = sliderRef.value;
  if (!el) return;
  el.scrollBy({ left: -(el.clientWidth * 0.75), behavior: "smooth" });
}

function slideRight() {
  const el = sliderRef.value;
  if (!el) return;
  el.scrollBy({ left: el.clientWidth * 0.75, behavior: "smooth" });
}

function restoreHistory(entry: HistoryEntry) {
  currentHistoryId.value = entry.id;
  currentQuery.value = entry.query;
  result.value = entry.result as SearchResponse;
  streamingReason.value = "";
  streamingKeywords.value = [];
  isStreamingReason.value = false;
  selectedBook.value = null;
  window.scrollTo({ top: 0, behavior: "smooth" });
  nextTick(() => searchInputRef.value?.focus());

  const restored = entry.result as BookSearchResponse;
  if (restored?.mode === "book" && restored.books?.[0]) {
    doStreamReason(
      entry.query,
      restored.rewritten_query ?? entry.query,
      restored.books[0],
      streamingReason,
      streamingKeywords,
      isStreamingReason,
    );
  }
}
</script>

<style scoped>
/* ── 전체 페이지 ─────────────────────────────────── */
.page {
  min-height: 100vh;
  background: var(--bg);
}

/* ── 전체 폭 상단 바 ─────────────────────────────── */
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

.top-brand-icon {
  height: 24px;
  width: 120px;
  flex-shrink: 0;
}

.top-brand-name {
  font-size: 16px;
  font-weight: 800;
  color: var(--ink);
  letter-spacing: -0.02em;
}

.top-brand-sub {
  font-weight: 500;
  color: var(--ink-3);
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
  max-width: 230px;
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

.sidebar-toggle.right {
  justify-content: flex-end;
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
}

/* ── 랜딩 ──────────────────────────────────────── */
.landing {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 84px);
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
  padding: 2px 8px;
  background: #f4f4f5;
  border-radius: 999px;
  font-size: 12px;
}

.rewritten {
  font-size: 13px;
  color: #a1a1aa;
}

/* ── 슬라이더 ───────────────────────────────────── */
.more-section {
  margin-top: 32px;
}

.more-title {
  font-size: 16px;
  font-weight: 600;
  color: #27272a;
  margin-bottom: 16px;
}

.slider-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.book-slider {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  padding: 4px 2px 10px;
  flex: 1;
  min-width: 0;
}

.book-slider::-webkit-scrollbar {
  display: none;
}

.book-slider > * {
  flex: 0 0 180px;
}

.slider-arrow {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid #e4e4e7;
  background: #ffffff;
  color: #52525b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  padding: 0;
}

.slider-arrow:hover {
  background: #f4f4f5;
  border-color: #d4d4d8;
}

/* ── 선택된 도서 ────────────────────────────────── */
.selected-section {
  margin-top: 8px;
  padding-top: 20px;
  border-top: 2px solid oklch(0.55 0.22 277);
  display: flex;
  flex-direction: column;
  gap: 14px;
  animation: selRecIn 0.25s ease;
}

@keyframes selRecIn {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.selected-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.selected-pill {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
  color: #fff;
  background: oklch(0.55 0.22 277);
  padding: 4px 10px;
  border-radius: 99px;
  white-space: nowrap;
  flex-shrink: 0;
}

.selected-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
  flex: 1;
  min-width: 0;
}

.close-btn {
  font-size: 12px;
  color: var(--ink-3);
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 99px;
  padding: 5px 12px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}

.close-btn:hover {
  background: #f4f4f5;
  color: #27272a;
}

/* ── Chunk 모드 ─────────────────────────────────── */
.chunk-answer {
  background: #fafafa;
  border: 1px solid #e4e4e7;
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 24px;
}

.answer-label {
  font-size: 12px;
  font-weight: 600;
  color: #a1a1aa;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunk-item {
  padding: 16px;
  border-radius: 14px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
}

.chunk-source {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.chunk-score {
  padding: 2px 8px;
  background: #f4f4f5;
  color: #27272a;
  border-radius: 999px;
  font-weight: 600;
  margin-left: 8px;
}

.chunk-text {
  font-size: 14px;
  line-height: 1.6;
  color: #3f3f46;
}

/* ── 로딩 / 에러 / 빈 결과 ─────────────────────── */
.loading-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 0;
  color: #64748b;
  gap: 12px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e4e4e7;
  border-top-color: #52525b;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-area {
  text-align: center;
  padding: 48px 0;
  color: #ef4444;
}

.error-area button {
  margin-top: 12px;
  padding: 8px 20px;
  border: 1px solid #d4d4d8;
  border-radius: 8px;
  background: #fafafa;
  cursor: pointer;
}

.empty {
  text-align: center;
  padding: 48px 0;
  color: #94a3b8;
  font-size: 15px;
}

.ch-placeholder {
  height: 100%;
}

/* ── 트랜지션 ───────────────────────────────────── */
.fade-text-enter-active,
.fade-text-leave-active {
  transition: opacity 0.15s ease;
}
.fade-text-enter-from,
.fade-text-leave-to {
  opacity: 0;
}

/* ── 반응형 ─────────────────────────────────────── */
@media (max-width: 768px) {
  .app-layout {
    grid-template-columns: 44px 1fr 44px !important;
  }
  .top-brand {
    flex: 0 0 44px;
    gap: 0;
  }
  .top-brand-name {
    display: none;
  }
  .book-slider > * {
    flex: 0 0 140px;
  }
}
</style>
