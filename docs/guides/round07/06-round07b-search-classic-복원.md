# round07 교본 (7) — round07b: 초기 SKOVIX 화면 `/search-classic` 되살리기

> round07 과 함께 낸 작은 덩어리다. 적재 코드와는 상관이 없고, 프론트 파일 넷을 지우기 전 모습으로 되살린 뒤 타입 검사에서만 뺐다. 막히면 [00-개요](00-개요.md) 로 돌아간다.

## 1. 설계

### 1-1. 무엇을 왜

round04b 는 기록 기능을 서버로 옮기면서 옛 화면 `pages/search-classic.vue` 와 그 화면만 쓰던 `components/ChatHistory.vue`·`composables/useSearch.ts`·`composables/useSearchHistory.ts` 를 잔재로 지웠다(`abc2426`, round04b 완료노트 C1 줄). 그런데 그 화면은 사용자가 직접 만든 초기 SKOVIX 첫 화면이었다. 링크가 없고 깨져 있어도 기록으로 남겨 두던 것이다. 2026-10-02 사용자 요청으로 되살렸다.

- 브랜치 `fix/round07b-restore-search-classic` — `dev` `9798f46` 에서 땄다(round07 과 같은 분기점). 커밋 2개, `dev` 머지 `5fa1a38`(round07 머지 `18e2c58` 바로 뒤, 충돌 없음).
- 운영에는 같은 날 round05a 의 `nl-lib-nuxt` 배포로 함께 나갔다(`/search-classic` 200).

### 1-2. 결정

| 결정 | 버린 대안 | 이유 |
|---|---|---|
| **지우기 직전 판(`abc2426^`) 그대로** 되살리고 맨 위에 보존 주석 한 줄만 단다 | 지금 화면·타입에 맞게 고쳐 되살린다 | 사용자가 만든 화면의 기록을 남기는 것이 목적이다 — 고치면 원래 모습이 아니다. 이 화면이 쓰는 다른 부품(`SearchInput`·`TopResult`·`CategoryAccordion`·`BookCard`)은 `dev` 에 그대로 있어 더 되살린 것은 없다 |
| 타입이 맞지 않는 세 파일에 **`// @ts-nocheck`** — 타입 검사에서만 뺀다(사용자 결정) | 기록 타입을 v2 에 맞게 고친다 | 세 파일은 기록 타입 v1 기준 코드라 지금 타입(v2)과 맞지 않아 `nuxi typecheck` 오류가 0 → 14 가 됐다. 코드를 고치지 않는다는 첫 결정과 맞추고, 빼는 범위는 파일 단위로 좁힌다. 오류가 없는 `useSearch.ts` 에는 달지 않았다 |
| round04b 완료노트의 삭제 기록 옆에 되살렸다고 적는다 | 기록을 지운다 | 지운 일과 되살린 일이 모두 남아야 다음 정리에서 같은 실수를 하지 않는다 |

## 2. 구현 (클론코딩)

### 2.46 되살린 네 파일

**파일**: `frontend/pages/search-classic.vue`·`frontend/components/ChatHistory.vue`·`frontend/composables/useSearch.ts`·`frontend/composables/useSearchHistory.ts` (새 파일 — `41a8775` 의 전체)

- 셋(`ChatHistory.vue`·`useSearch.ts`·`useSearchHistory.ts`)은 `abc2426^` 의 판과 바이트까지 같다. `search-classic.vue` 만 맨 위에 보존 주석 한 줄이 더 있다(아래 diff).
- 그래서 저장소에서는 이렇게 되살릴 수 있다 — 지우기 직전 판을 꺼낸 뒤 주석 한 줄을 단다.

```bash
git checkout abc2426^ -- frontend/pages/search-classic.vue frontend/components/ChatHistory.vue frontend/composables/useSearch.ts frontend/composables/useSearchHistory.ts
git diff --stat abc2426^ 41a8775 -- frontend/pages/search-classic.vue frontend/components/ChatHistory.vue frontend/composables/useSearch.ts frontend/composables/useSearchHistory.ts   # search-classic.vue 의 1줄만 다르다
```

```diff
diff --git a/frontend/pages/search-classic.vue b/frontend/pages/search-classic.vue
index c4e028a..1959b12 100644
--- a/frontend/pages/search-classic.vue
+++ b/frontend/pages/search-classic.vue
@@ -1,3 +1,4 @@
+<!-- 보존 화면: 사용자가 직접 만든 초기 SKOVIX 첫 화면. 깨져 있어도 지우지 않는다(2026-10-02 사용자 요청으로 되살림). -->
 <template>
   <div class="page">
     <!-- ══ 전체 폭 상단 바 ════════════════════════════════════════ -->
```

```vue
<!-- 보존 화면: 사용자가 직접 만든 초기 SKOVIX 첫 화면. 깨져 있어도 지우지 않는다(2026-10-02 사용자 요청으로 되살림). -->
<template>
  <div class="page">
    <!-- ══ 전체 폭 상단 바 ════════════════════════════════════════ -->
    <header class="top-bar" ref="topBarRef">
      <div class="top-bar-inner">
        <button class="top-brand" @click="reset">
          <!-- <img
            src="/landsoft-ai-gradient.svg"
            alt="landsoft"
            class="top-brand-icon"
          /> -->
          <!-- <span class="top-brand-name"
            >NL<span class="top-brand-sub">-Lib</span></span
          > -->
          <img
            src="/skovix-character.png"
            alt="SKOVIX"
            class="top-brand-skovix"
          />
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

        <div v-show="leftOpen" class="sidebar-body sidebar-body--left">
          <div class="sidebar-history scrollbar-zinc">
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

          <!-- ── 장바구니 (대출 신청한 도서) ── -->
          <ClientOnly>
            <div class="cart-block">
              <div class="cart-head">
                <span>🛒 장바구니</span>
                <span class="cart-count">{{ cart.length }}</span>
              </div>
              <ul class="cart-list scrollbar-zinc">
                <li v-for="item in cart" :key="item.book_id" class="cart-item">
                  <span class="cart-item-title" :title="item.title">{{
                    item.title
                  }}</span>
                  <button
                    class="cart-remove"
                    title="장바구니에서 빼기"
                    @click="removeFromCart(item.book_id)"
                  >
                    ✕
                  </button>
                </li>
                <li v-if="!cart.length" class="cart-empty">
                  대출 신청한 도서가 없습니다
                </li>
              </ul>
            </div>
          </ClientOnly>
        </div>
      </aside>

      <!-- ══ 메인 콘텐츠 ═══════════════════════════════════════ -->
      <main class="main-content scrollbar-zinc">
        <!-- 랜딩 -->
        <div v-if="!result && !loading && !error" class="landing">
          <!-- 세그먼티드 토글 -->
          <div class="seg" ref="segRef">
            <div class="seg-thumb" :style="thumbStyle" />
            <button data-key="book" class="seg-btn is-active">
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
            <button
              data-key="paper"
              class="seg-btn"
              @click="navigateTo('/papers')"
            >
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
            <h1 class="title">도서관 의미 기반 검색</h1>
            <p class="subtitle">읽고 싶은 책을 자연어로 검색해보세요</p>
          </div>
          <SearchInput
            placeholder="요즘 번아웃이 심한 직장인인데, 쉬면서 읽을 수 있는 책 추천해줘"
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
                        v-for="book in bookResult.books
                          .slice(1)
                          .filter((b) => b.best_score >= 0.1)"
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

        <div v-show="rightOpen" class="sidebar-body scrollbar-zinc">
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
import { useCart } from "~/composables/useCart";
import type {
  BookChunkGroup,
  BookSearchResponse,
  ChunkSearchResponse,
  SearchResponse,
} from "~/types/search";
import type { HistoryEntry } from "~/types/history";

const { history, setHistory, clearHistory } = useSearchHistory();
const { cart, removeFromCart } = useCart();
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
const segRef = ref<HTMLElement | null>(null);
const thumbStyle = ref({ left: "5px", width: "120px" });

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

  nextTick(() => {
    if (!segRef.value) return;
    const activeBtn = segRef.value.querySelector(
      '[data-key="book"]',
    ) as HTMLElement;
    if (!activeBtn) return;
    const wrap = segRef.value.getBoundingClientRect();
    const rect = activeBtn.getBoundingClientRect();
    thumbStyle.value = {
      left: rect.left - wrap.left + "px",
      width: rect.width + "px",
    };
  });

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
  height: 100vh;
  overflow: hidden;
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

.top-brand-skovix {
  height: 36px;
  width: auto;
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

/* 왼쪽 패널: 검색기록(내부 스크롤) + 장바구니(하단 고정) → 자체 스크롤 제거(이중 방지) */
.sidebar-body--left {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-history {
  flex: 1;
  min-height: 0;
  overflow: hidden; /* ChatHistory 내부(.ch-list)가 스크롤을 담당 */
}

/* ── 메인 콘텐츠 ────────────────────────────────── */
.main-content {
  min-width: 0;
  /* 사이드바와 동일하게 본문도 독립 스크롤 컨테이너 (.page 가 overflow:hidden 이라
     이 height/overflow 가 없으면 본문이 잘려 스크롤바가 사라진다) */
  height: v-bind("'calc(100vh - ' + topBarHeight + 'px)'");
  overflow-y: auto;
  overflow-x: hidden;
}

/* ── 랜딩 ──────────────────────────────────────── */
.landing {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  /* main-content(동적 높이 calc(100vh - topBarHeight))를 정확히 채움.
     하드코딩 84px 와 실제 상단바 높이가 달라 생기던 상시 스크롤바 제거 */
  min-height: 100%;
  padding: 24px;
  gap: 32px;
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
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  transition:
    transform 280ms cubic-bezier(0.4, 0.2, 0.2, 1),
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
  background: none;
  border: none;
  cursor: pointer;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: color 200ms;
  font-family: inherit;
}
.seg-btn.is-active {
  color: var(--violet-deep, #4a2ed6);
}
.seg-btn .ico {
  width: 16px;
  height: 16px;
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

/* ── 장바구니 ───────────────────────────────────── */
.cart-block {
  flex-shrink: 0; /* 하단 고정 — 검색기록 스크롤 영역과 분리 */
  margin-top: 14px;
  padding: 12px 8px 10px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}
.cart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  color: #374151;
  margin-bottom: 8px;
}
.cart-count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #4f46e5;
  color: #fff;
  font-size: 11px;
  border-radius: 10px;
}
.cart-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 26vh; /* 장바구니가 길면 이 영역만 자체 스크롤 (검색기록과 독립) */
  overflow-y: auto;
}
.cart-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 12px;
}
.cart-item-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #1f2937;
}
.cart-remove {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  padding: 2px;
}
.cart-remove:hover {
  color: #ef4444;
}
.cart-empty {
  font-size: 12px;
  color: #9ca3af;
  padding: 6px 2px;
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
```

```vue
<template>
  <div class="chat-history">
    <div class="ch-header">
      <button
        v-if="history.length"
        class="ch-clear"
        @click="$emit('clear')"
        title="기록 삭제"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6l-1 14H6L5 6" />
          <path d="M10 11v6M14 11v6" />
          <path d="M9 6V4h6v2" />
        </svg>
      </button>
    </div>

    <div v-if="!history.length" class="ch-empty">
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
      <p>검색 기록이 없습니다</p>
    </div>

    <ul v-else class="ch-list scrollbar-zinc">
      <li
        v-for="entry in history"
        :key="entry.id"
        class="ch-item"
        :class="{ active: entry.id === currentId }"
        @click="$emit('select', entry)"
      >
        <span class="ch-query">{{ entry.query }}</span>
        <span class="ch-time">{{ formatTime(entry.timestamp) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { HistoryEntry } from "~/types/history";

defineProps<{
  history: HistoryEntry[];
  currentId: string | null;
}>();

defineEmits<{
  select: [entry: HistoryEntry];
  clear: [];
}>();

function formatTime(ts: number | string): string {
  const d = new Date(ts);
  const now = new Date();
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000);
  if (diffMin < 1) return "방금";
  if (diffMin < 60) return `${diffMin}분 전`;
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return d.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
}
</script>

<style scoped>
.chat-history {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 8px 0;
}

.ch-header {
  display: flex;
  justify-content: flex-end;
  padding: 4px 8px;
}

.ch-clear {
  display: flex;
  align-items: center;
  padding: 4px;
  border: none;
  background: transparent;
  color: #a1a1aa;
  cursor: pointer;
  border-radius: 4px;
  transition:
    color 0.15s,
    background 0.15s;
}

.ch-clear:hover {
  color: #ef4444;
  background: #fef2f2;
}

.ch-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 16px;
  color: #d4d4d8;
}

.ch-empty p {
  font-size: 13px;
  color: #a1a1aa;
  text-align: center;
}

.ch-list {
  list-style: none;
  margin: 0;
  padding: 8px 0;
  overflow-y: auto;
  flex: 1;
}

.ch-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 16px;
  cursor: pointer;
  border-radius: 8px;
  margin: 2px 8px;
  transition: background 0.15s;
}

.ch-item:hover {
  background: #fafafa;
}

.ch-item.active {
  background: #fafafa;
  border: #e7e7e2 0.6px solid;
}

.ch-item.active .ch-query {
  color: #18181b;
  font-weight: 600;
}

.ch-query {
  font-size: 13px;
  color: #3f3f46;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ch-time {
  font-size: 11px;
  color: #a1a1aa;
}
</style>
```

```ts
import type { SearchRequest, SearchResponse } from "~/types/search";

export function useSearch() {
  const config = useRuntimeConfig();

  const loading = ref(false);
  const error = ref<string | null>(null);
  const result = ref<SearchResponse | null>(null);

  function generateUUID() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }

    // fallback
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  const sessionId = useState<string | null>("sessionId", () => {
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

  async function search(
    query: string,
    mode: "chunk" | "book" = "book",
    topK = 5,
  ) {
    loading.value = true;
    error.value = null;
    result.value = null;

    try {
      const body: SearchRequest = {
        query,
        mode,
        top_k: topK,
        use_rewrite: true,
        use_rerank: true,
      };

      const data = await $fetch<SearchResponse>(
        `${config.public.apiBase}/books/search`,
        {
          method: "POST",
          headers: sessionId.value ? { "x-session-id": sessionId.value } : {},
          body,
        },
      );

      result.value = data;
    } catch (e: any) {
      error.value =
        e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
    } finally {
      loading.value = false;
    }
  }

  function reset() {
    result.value = null;
    error.value = null;
  }

  return { loading, error, result, search, reset, generateUUID };
}
```

```ts
import type { HistoryEntry } from "~/types/history";

const STORAGE_KEY = "skx_search_history";
const MAX_ENTRIES = 30;

// Module-level singleton state — shared across all composable calls
const _history = ref<HistoryEntry[]>([]);
let _loaded = false;

export function useSearchHistory() {
  // Lazy-load from localStorage once per app lifetime
  if (process.client && !_loaded) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) _history.value = JSON.parse(raw);
    } catch {
      /* corrupted storage — start fresh */
    }
    _loaded = true;
  }

  function _persist() {
    if (!process.client) return;
    // 쿼터 초과 시 오래된 항목(뒤쪽)을 5개씩 줄여가며 재시도
    let items = _history.value;
    while (true) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
        _history.value = items;
        return;
      } catch {
        if (items.length <= 1) return; // 단일 항목도 저장 불가 — 포기
        items = items.slice(0, Math.max(1, items.length - 5));
      }
    }
  }

  /** Add a new entry to the front of the list. Returns the generated id. */
  function addEntry(entry: Omit<HistoryEntry, "id" | "timestamp">): string {
    const id = Date.now().toString();
    _history.value.unshift({ id, timestamp: new Date().toISOString(), ...entry });
    if (_history.value.length > MAX_ENTRIES) {
      _history.value = _history.value.slice(0, MAX_ENTRIES);
    }
    _persist();
    return id;
  }

  /** Patch the aiSummary field of an existing entry after streaming completes. */
  function updateAiSummary(id: string, summary: string) {
    const entry = _history.value.find((h) => h.id === id);
    if (entry) {
      entry.aiSummary = summary;
      _persist();
    }
  }

  /** Remove all entries of a given type. */
  function clearByType(type: "book" | "paper") {
    _history.value = _history.value.filter((h) => h.type !== type);
    _persist();
  }

  /** Lookup a single entry by id (used on restore navigation). */
  function getById(id: string): HistoryEntry | undefined {
    return _history.value.find((h) => h.id === id);
  }

  const bookHistory = computed(() =>
    _history.value.filter((h) => h.type === "book"),
  );
  const paperHistory = computed(() =>
    _history.value.filter((h) => h.type === "paper"),
  );

  return {
    history: _history,
    bookHistory,
    paperHistory,
    addEntry,
    updateAiSummary,
    clearByType,
    getById,
  };
}
```

### 2.47 타입 검사에서만 빼기 — `// @ts-nocheck`

**파일**: `frontend/pages/search-classic.vue`·`frontend/components/ChatHistory.vue`·`frontend/composables/useSearchHistory.ts` (`41a8775` 대비 diff — `b468e4c`)

`<script setup>` 첫 줄(합성 함수는 파일 첫 줄)에 `// @ts-nocheck` 와 까닭 한 줄을 단다. 지시는 그 파일 하나에만 걸리므로 다른 파일의 타입 검사는 그대로다.

```diff
diff --git a/frontend/components/ChatHistory.vue b/frontend/components/ChatHistory.vue
index cf9f153..8756e3b 100644
--- a/frontend/components/ChatHistory.vue
+++ b/frontend/components/ChatHistory.vue
@@ -54,6 +54,8 @@
 </template>
 
 <script setup lang="ts">
+// @ts-nocheck
+// 보존 화면(/search-classic) 전용 — 기록 타입 v1 기준 코드라 지금 타입(v2)과 맞지 않는다. typecheck 에서만 뺀다.
 import type { HistoryEntry } from "~/types/history";
 
 defineProps<{
diff --git a/frontend/composables/useSearchHistory.ts b/frontend/composables/useSearchHistory.ts
index c1ff138..1830124 100644
--- a/frontend/composables/useSearchHistory.ts
+++ b/frontend/composables/useSearchHistory.ts
@@ -1,3 +1,5 @@
+// @ts-nocheck
+// 보존 화면(/search-classic) 전용 — 기록 타입 v1 기준 코드라 지금 타입(v2)과 맞지 않는다. typecheck 에서만 뺀다.
 import type { HistoryEntry } from "~/types/history";
 
 const STORAGE_KEY = "skx_search_history";
diff --git a/frontend/pages/search-classic.vue b/frontend/pages/search-classic.vue
index 1959b12..2b5498e 100644
--- a/frontend/pages/search-classic.vue
+++ b/frontend/pages/search-classic.vue
@@ -336,6 +336,8 @@
 </template>
 
 <script setup lang="ts">
+// @ts-nocheck
+// 보존 화면 — 기록 타입 v1 기준 코드라 지금 타입(v2)과 맞지 않는다. 고치지 않고 typecheck 에서만 뺀다.
 import { type Ref } from "vue";
 import { useSearch } from "~/composables/useSearch";
 import { useSearchHistory } from "~/composables/useSearchHistory";
```

## 3. 검증

```bash
# frontend/ 에서 (npm ci 뒤) — 2026-10-02, b468e4c
npx vitest run                                   # Test Files 21 passed · Tests 406 passed
npx nuxi typecheck 2>&1 | grep -c "error TS"     # 0 (주석을 달기 전에는 14)
```

- 주석을 하나 빼면 그 파일의 오류가 다시 나오는 것도 확인했다 — 지시가 실제로 그 파일을 빼고 있다.
- 운영: round05a 의 `nl-lib-nuxt` 배포(2026-10-02) 뒤 `/search-classic` 이 200 이다.

## 4. 면접식 Q&A

**Q1. 링크도 없고 깨진 화면을 왜 다시 저장소에 들였나? 잔재 정리와 어긋나지 않나?**
A. 잔재 정리는 "아무도 쓰지 않고 기록할 가치도 없는 코드"를 지우는 일이다. 이 화면은 쓰이지는 않지만 사용자가 직접 만든 첫 화면이라는 기록의 가치가 있었다 — 정리하는 쪽이 그 사정을 몰랐을 뿐이다. 그래서 지우기 직전 판 그대로 되살리고, 맨 위 주석과 round04b 완료노트에 보존 화면이라고 적어 다음 정리에서 다시 지우지 않게 했다. 교훈은 "링크 없는 화면을 지우기 전에 만든 사람에게 먼저 묻는다"다.

**Q2. `@ts-nocheck` 는 타입 오류를 숨기는 것 아닌가?**
A. 숨기는 범위를 정확히 정한 것이다. 고치지 않기로 한 보존 파일 셋만 파일 단위로 빼고, 나머지 코드는 전과 같이 오류 0 을 지킨다. 반대로 그냥 두면 타입 검사가 늘 14개 오류로 끝나, 새 코드의 진짜 오류가 그 속에 묻힌다. 주석을 하나 빼면 오류가 다시 나오는 것을 확인해, 지시가 의도한 파일에만 걸린다는 것도 봤다. 그 화면을 다시 쓰게 되면 그때 타입을 v2 로 고치고 주석을 지운다.
