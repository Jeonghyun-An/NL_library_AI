<template>
  <div class="page">
    <!-- 검색 전: 로고 + 입력창 중앙 배치 -->
    <div v-if="!result" class="landing">
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
        <SearchInput
          v-model="currentQuery"
          :disabled="loading"
          @submit="handleSearch"
        />
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
          <span class="query-display">"{{ result.query }}"</span>
          <span class="elapsed">{{ result.elapsed_ms.toFixed(0) }}ms</span>
          <span v-if="result.rewritten_query" class="rewritten">
            → {{ result.rewritten_query }}
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
  </div>
</template>

<script setup lang="ts">
import { useSearch } from "~/composables/useSearch";
import type { BookSearchResponse, ChunkSearchResponse } from "~/types/search";

const { loading, error, result, search, reset: resetSearch } = useSearch();
const currentQuery = ref("");

// book 모드에서 Top 1의 best chunk를 답변으로 사용 (LLM 답변이 없는 경우)
const bookAnswer = computed(() => {
  if (!result.value || result.value.mode !== "book") return undefined;
  const r = result.value as BookSearchResponse;
  const top = r.books?.[0];
  if (!top) return undefined;
  if (top.reason) return top.reason;
  const best = [...top.chunks].sort(
    (a, b) => (b.rerank_score || b.score) - (a.rerank_score || a.score),
  )?.[0];
  return best?.text;
});
// 타입 가드된 book 모드 결과
const bookResult = computed(() => {
  if (!result.value || result.value.mode !== "book") return null;
  return result.value as BookSearchResponse;
});

const chunkResult = computed(() => {
  if (!result.value || result.value.mode !== "chunk") return null;
  return result.value as ChunkSearchResponse;
});

const topBook = computed(() => {
  return bookResult.value?.books?.[0] ?? null;
});
function handleSearch(query: string) {
  currentQuery.value = query;
  search(query, "book", 5);
}

function reset() {
  currentQuery.value = "";
  resetSearch();
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #fff;
}

/* ── 랜딩 (검색 전) ─────────────── */
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
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 15px;
  color: #64748b;
  margin: 0;
}

/* ── 결과 페이지 ─────────────────── */
.results-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 24px 48px;
}

.results-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 0;
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 10;
  border-bottom: 1px solid #f1f5f9;
}

.header-logo {
  width: 32px;
  height: 32px;
  cursor: pointer;
  flex-shrink: 0;
}

/* ── 검색 메타 ───────────────────── */
.search-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 0;
  font-size: 14px;
  color: #64748b;
}

.query-display {
  font-weight: 600;
  color: #0f172a;
}

.elapsed {
  padding: 2px 8px;
  background: #f1f5f9;
  border-radius: 8px;
  font-size: 12px;
}

.rewritten {
  font-size: 13px;
  color: #94a3b8;
}

/* ── 추천 도서 그리드 ────────────── */
.more-section {
  margin-top: 32px;
}

.more-title {
  font-size: 16px;
  font-weight: 600;
  color: #334155;
  margin: 0 0 16px 0;
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}

/* ── Chunk 모드 ──────────────────── */
.chunk-answer {
  background: #f8fafc;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
}

.answer-label {
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
  margin-bottom: 8px;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunk-item {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}

.chunk-source {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.chunk-score {
  padding: 1px 6px;
  background: #f0f9ff;
  color: #0369a1;
  border-radius: 8px;
  font-weight: 600;
  margin-left: 8px;
}

.chunk-text {
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
  margin: 0;
}

/* ── 로딩 / 에러 / 빈 결과 ──────── */
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
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 16px;
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
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}

.empty {
  text-align: center;
  padding: 48px 0;
  color: #94a3b8;
  font-size: 15px;
}

@media (max-width: 640px) {
  .book-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
