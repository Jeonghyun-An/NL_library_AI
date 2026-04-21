<template>
  <div class="page">
    <div class="app-layout" :style="{ gridTemplateColumns: gridCols }">
      <!-- ══ 왼쪽 사이드바: 로고 + 검색기록 ══════════════════ -->
      <aside class="sidebar sidebar-left">
        <!-- 로고 (항상 표시) -->
        <div class="sidebar-brand" @click="reset">
          <img src="/logo.svg" alt="NL-Lib" class="brand-icon" />
          <Transition name="fade-text">
            <span v-if="leftOpen" class="brand-name">NL-Lib</span>
          </Transition>
        </div>

        <!-- 토글 버튼 -->
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

        <!-- 기록 목록: ClientOnly로 SSR 하이드레이션 불일치 방지 -->
        <div v-show="leftOpen" class="sidebar-body">
          <ClientOnly>
            <ChatHistory
              :history="history"
              :current-id="currentHistoryId"
              @select="restoreHistory"
              @clear="clearHistory"
            />
            <template #fallback>
              <div class="ch-placeholder" />
            </template>
          </ClientOnly>
        </div>
      </aside>

      <!-- ══ 메인 콘텐츠 ═══════════════════════════════════════ -->
      <main class="main-content">
        <!-- 검색 전: 랜딩 -->
        <div v-if="!result && !loading && !error" class="landing">
          <div class="logo-area">
            <h1 class="title">국립중앙도서관 의미 기반 검색</h1>
            <p class="subtitle">읽고 싶은 책을 자연어로 검색해보세요</p>
          </div>
          <SearchInput
            placeholder="예: 한강의 채식주의자와 비슷한 책 찾아줘"
            :disabled="loading"
            @submit="handleSearch"
          />
        </div>

        <!-- 검색 후: 결과 -->
        <div v-else class="results-page">
          <header class="results-header">
            <div class="header-input-wrap">
              <SearchInput
                ref="searchInputRef"
                v-model="currentQuery"
                :disabled="loading"
                @submit="handleSearch"
              />
            </div>
          </header>

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
                  :is-streaming="isStreamingReason"
                />
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
        <!-- 토글 버튼 -->
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

        <!-- 카테고리 목록 -->
        <div v-show="rightOpen" class="sidebar-body">
          <CategoryAccordion :books="bookResult?.books ?? []" />
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
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
const rightOpen = ref(true);
const searchInputRef = ref<{ focus: () => void } | null>(null);
const streamingReason = ref("");
const isStreamingReason = ref(false);

// 그리드 컬럼: 사이드바 열림 상태에 따라 자동 조정
const gridCols = computed(() => {
  const l = leftOpen.value ? "240px" : "44px";
  const r = rightOpen.value ? "clamp(300px, 25vw, 420px)" : "44px";
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

const sessionId = useState("sessionId", () => {
  if (process.client) {
    let sid = localStorage.getItem("sid");
    if (!sid) {
      sid = generateUUID();
      localStorage.setItem("sid", sid);
    }
    return sid;
  }
  return null;
});

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
  if (!sessionId.value) {
    const sid = generateUUID();
    sessionId.value = sid;
    localStorage.setItem("sid", sid);
  }
  loadHistory();
});

async function handleSearch(query: string) {
  currentHistoryId.value = null;
  streamingReason.value = "";
  isStreamingReason.value = false;

  await search(query, "book", 10);
  await loadHistory();

  // 검색 완료 후 상위 도서 추천 이유 스트리밍 시작 (non-blocking)
  if (bookResult.value?.books?.[0]) {
    streamReason(query, bookResult.value.books[0]);
  }

  nextTick(() => searchInputRef.value?.focus());
}

async function streamReason(query: string, book: BookChunkGroup) {
  isStreamingReason.value = true;
  streamingReason.value = "";

  const topChunkTexts = [...book.chunks]
    .sort((a, b) => (b.rerank_score ?? b.score) - (a.rerank_score ?? a.score))
    .slice(0, 3)
    .map((c) => c.text);

  try {
    const response = await fetch(`${config.public.apiBase}/books/reason/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        book_id: book.book_id,
        chunk_texts: topChunkTexts,
      }),
    });

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
          if (parsed.text) streamingReason.value += parsed.text;
        } catch {}
      }
    }
  } catch (e) {
    console.error("추천 이유 스트리밍 실패:", e);
  } finally {
    isStreamingReason.value = false;
  }
}

function restoreHistory(entry: HistoryEntry) {
  currentHistoryId.value = entry.id;
  currentQuery.value = entry.query;
  result.value = entry.result as SearchResponse;
  streamingReason.value = "";
  isStreamingReason.value = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
  nextTick(() => searchInputRef.value?.focus());

  // 도서 검색 결과인 경우 추천 이유 재스트리밍
  // (저장된 결과에 청크 데이터가 포함되어 있어 그대로 활용 가능)
  const restored = entry.result as BookSearchResponse;
  if (restored?.mode === "book" && restored.books?.[0]) {
    streamReason(entry.query, restored.books[0]);
  }
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
  min-height: 100vh;
  transition: grid-template-columns 0.25s ease;
}

/* ── 사이드바 공통 ──────────────────────────────── */
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}

.sidebar-left {
  border-right: 1px solid #ebebed;
}

.sidebar-right {
  border-left: 1px solid #ebebed;
  min-width: 0;
  max-width: 420px;
}

/* ── 로고 (왼쪽 상단 고정) ─────────────────────── */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 14px 14px;
  cursor: pointer;
  min-height: 68px;
  flex-shrink: 0;
}

.brand-icon {
  width: 72px;
  height: 36px;
  flex-shrink: 0;
}

.brand-name {
  font-size: 17px;
  font-weight: 800;
  color: #18181b;
  white-space: nowrap;
  overflow: hidden;
  letter-spacing: -0.02em;
}

/* ── 사이드바 토글 버튼 ─────────────────────────── */
.sidebar-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: calc(100% - 16px);
  margin: 0 8px 4px;
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
  min-height: 100vh;
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

.results-header {
  display: flex;
  align-items: center;
  padding: 16px 0;
  position: sticky;
  top: 0;
  backdrop-filter: blur(10px);
  z-index: 10;
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
  flex-wrap: wrap;
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

/* ── 도서 그리드 ────────────────────────────────── */
.more-section {
  margin-top: 32px;
}

.more-title {
  font-size: 16px;
  font-weight: 600;
  color: #27272a;
  margin-bottom: 16px;
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

.error-area button:hover {
  background: #f4f4f5;
}

.empty {
  text-align: center;
  padding: 48px 0;
  color: #94a3b8;
  font-size: 15px;
}

/* ClientOnly fallback */
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
@media (max-width: 1100px) {
  .landing .title {
    font-size: 22px;
  }
}

@media (max-width: 768px) {
  .app-layout {
    grid-template-columns: 44px 1fr 44px !important;
  }

  .book-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
