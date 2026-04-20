<template>
  <div class="page">
    <div class="app-layout">

      <!-- ── 왼쪽: 채팅 기록 ───────────────────────────────── -->
      <aside class="sidebar sidebar-left">
        <ChatHistory
          :history="history"
          :current-id="currentHistoryId"
          @select="restoreHistory"
          @clear="clearHistory"
        />
      </aside>

      <!-- ── 가운데: 메인 콘텐츠 ──────────────────────────── -->
      <main class="main-content">

        <!-- 검색 전: 로고 + 입력창 중앙 배치 -->
        <div v-if="!result && !loading && !error" class="landing">
          <div class="logo-area">
            <img src="/logo.svg" alt="NL-Lib" class="logo" />
            <h1 class="title">국립중앙도서관 의미 기반 검색</h1>
            <p class="subtitle">읽고 싶은 책을 자연어로 검색해보세요</p>
          </div>
          <SearchInput
            placeholder="예: 한강의 채식주의자와 비슷한 책 찾아줘"
            :disabled="loading"
            @submit="handleSearch"
          />
        </div>

        <!-- 검색 후: 상단 입력창 + 결과 -->
        <div v-else class="results-page">
          <!-- 상단 고정 입력창 -->
          <header class="results-header">
            <img src="/logo.svg" alt="NL-Lib" class="header-logo" @click="reset" />
            <div class="header-input-wrap">
              <SearchInput
                v-model="currentQuery"
                :disabled="loading"
                @submit="handleSearch"
              />
            </div>
          </header>

          <!-- 로딩 -->
          <div v-if="loading" class="loading-area">
            <div class="spinner" />
            <p>도서를 찾고 있습니다...</p>
          </div>

          <!-- 에러 -->
          <div v-else-if="error" class="error-area">
            <p>{{ error }}</p>
            <button @click="handleSearch(currentQuery)">다시 검색</button>
          </div>

          <!-- 결과 -->
          <div v-else class="results-content">
            <!-- 검색 정보 -->
            <div class="search-meta">
              <span class="query-display">"{{ result?.query }}"</span>
              <span class="elapsed">{{ result?.elapsed_ms.toFixed(0) }}ms</span>
              <span v-if="result?.rewritten_query" class="rewritten">
                → {{ result?.rewritten_query }}
              </span>
            </div>

            <!-- Book 모드 결과 -->
            <template v-if="bookResult">
              <div v-if="!bookResult.books.length" class="empty">
                검색 결과가 없습니다. 다른 검색어를 시도해보세요.
              </div>

              <template v-else>
                <TopResult v-if="topBook" :book="topBook" :answer="bookAnswer" />

                <div v-if="bookResult.books.length > 1" class="more-section">
                  <h3 class="more-title">함께 추천하는 도서</h3>
                  <div class="book-grid">
                    <BookCard
                      v-for="book in bookResult.books.slice(1)"
                      :key="book.book_id"
                      :book="book"
                    />
                  </div>
                </div>
              </template>
            </template>

            <!-- Chunk 모드 결과 -->
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
                    {{ chunk.book_id }} · p.{{ chunk.page_start }}-{{ chunk.page_end }}
                    <span class="chunk-score">{{ (chunk.score * 100).toFixed(0) }}%</span>
                  </div>
                  <p class="chunk-text">{{ chunk.text }}</p>
                </div>
              </div>
            </template>
          </div>
        </div>
      </main>

      <!-- ── 오른쪽: 카테고리 아코디언 ────────────────────── -->
      <aside class="sidebar sidebar-right">
        <CategoryAccordion :books="bookResult?.books ?? []" />
      </aside>

    </div>
  </div>
</template>

<script setup lang="ts">
import { useSearch } from "~/composables/useSearch";
import { useSearchHistory } from "~/composables/useSearchHistory";
import type { BookSearchResponse, ChunkSearchResponse } from "~/types/search";

const { loading, error, result, search, reset: resetSearch } = useSearch();
const { history, addEntry, clearHistory } = useSearchHistory();

const currentQuery = ref("");
const currentHistoryId = ref<string | null>(null);

const bookAnswer = computed(() => {
  if (!result.value || result.value.mode !== "book") return undefined;
  return (result.value as BookSearchResponse).books?.[0]?.reason;
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

async function handleSearch(query: string) {
  currentQuery.value = query;
  await search(query, "book", 5);
  if (result.value) {
    currentHistoryId.value = addEntry(query, result.value);
  }
  nextTick(() => {
    currentQuery.value = "";
  });
}

function restoreHistory(entry: (typeof history.value)[number]) {
  currentHistoryId.value = entry.id;
  result.value = entry.result;
}

function reset() {
  currentQuery.value = "";
  currentHistoryId.value = null;
  resetSearch();
}
</script>

<style scoped>
/* ── 전체 레이아웃 ──────────────────────────────── */
.page {
  min-height: 100vh;
  background:
    radial-gradient(circle at 20% 10%, rgba(0, 0, 0, 0.03), transparent 40%),
    radial-gradient(circle at 80% 0%, rgba(0, 0, 0, 0.02), transparent 40%),
    linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
}

.app-layout {
  display: grid;
  grid-template-columns: 240px 1fr 260px;
  min-height: 100vh;
}

/* ── 사이드바 공통 ──────────────────────────────── */
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  border-right: 1px solid #f0f0f1;
}

.sidebar-left {
  border-right: 1px solid #f0f0f1;
}

.sidebar-right {
  border-left: 1px solid #f0f0f1;
  border-right: none;
}

/* ── 메인 콘텐츠 ────────────────────────────────── */
.main-content {
  min-width: 0;
}

/* ── 랜딩 (검색 전) ────────────────────────────── */
.landing {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  gap: 32px;
}

.logo-area {
  text-align: center;
}

.logo {
  width: 64px;
  height: 64px;
  margin-bottom: 16px;
}

.title {
  font-size: 26px;
  font-weight: 700;
  color: #18181b;
}

.subtitle {
  font-size: 15px;
  color: #71717a;
}

/* ── 결과 페이지 ────────────────────────────────── */
.results-page {
  padding: 0 24px 48px;
}

.results-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 0;
  position: sticky;
  top: 0;
  backdrop-filter: blur(10px);
  z-index: 10;
}

.header-logo {
  width: 32px;
  height: 32px;
  cursor: pointer;
  flex-shrink: 0;
}

.header-input-wrap {
  flex: 1;
  min-width: 0;
}

.header-input-wrap :deep(.search-input-wrap) {
  max-width: none;
  margin: 0;
}

/* ── 검색 메타 ──────────────────────────────────── */
.search-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 0;
  font-size: 14px;
  color: #71717a;
}

.query-display {
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
  color: #94a3b8;
}

/* ── 추천 도서 그리드 ───────────────────────────── */
.more-section {
  margin-top: 32px;
}

.more-title {
  font-size: 16px;
  font-weight: 600;
  color: #27272a;
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
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
  transition: all 0.2s;
}

.chunk-item:hover {
  transform: translateY(-2px);
  box-shadow:
    0 10px 25px rgba(0, 0, 0, 0.05),
    0 2px 6px rgba(0, 0, 0, 0.03);
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
  to { transform: rotate(360deg); }
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

.error-area button:hover {
  background: #f4f4f5;
}

.empty {
  text-align: center;
  padding: 48px 0;
  color: #94a3b8;
  font-size: 15px;
}

/* ── 반응형 ─────────────────────────────────────── */
@media (max-width: 1100px) {
  .app-layout {
    grid-template-columns: 200px 1fr 220px;
  }
}

@media (max-width: 860px) {
  .app-layout {
    grid-template-columns: 1fr;
  }
  .sidebar {
    position: static;
    height: auto;
    border: none;
    border-bottom: 1px solid #f0f0f1;
  }
  .sidebar-right {
    border-top: 1px solid #f0f0f1;
  }
  .book-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
