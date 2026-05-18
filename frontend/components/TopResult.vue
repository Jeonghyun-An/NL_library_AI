<template>
  <div class="top-result">
    <!-- AI 추천 답변 (Gradient Panel) -->
    <div class="answer-section" v-if="answer || isStreaming">
      <div class="answer-inner">
        <header class="answer-header">
          <div class="answer-header-left">
            <img src="/ai_orb.svg" class="ai-orb" alt="" />
            <div>
              <div class="answer-title">
                AI 추천 답변
                <img
                  src="/ic_done.png"
                  class="status-icon"
                  :class="{ spinning: isStreaming }"
                  alt=""
                />
              </div>
              <div class="answer-subtitle">
                <template v-if="isStreaming && !answer">
                  답변 생성 중...
                </template>
                <template v-else-if="book?.book_info?.title">
                  &ldquo;{{ book.book_info.title }}&rdquo; 을(를) 분석했어요
                </template>
              </div>
            </div>
          </div>
        </header>

        <div class="answer-text" v-html="formattedAnswer" />

        <!-- 키워드 칩 -->
        <div v-if="keywords?.length" class="keyword-row">
          <span v-for="kw in keywords" :key="kw" class="keyword-chip"
            >#{{ kw }}</span
          >
        </div>
      </div>
    </div>

    <!-- 도서 커버 + 메타 -->
    <div class="book-detail" v-if="book">
      <!-- 커버 -->
      <div class="cover-col">
        <div class="cover-area" @click="openNLPage">
          <BookCover :book-id="book.book_id" size="large" />
        </div>
        <div class="relevance-bar">
          <div class="relevance-row">
            <span class="relevance-label">관련도</span>
            <span class="relevance-pct"
              >{{ (book.best_score * 100).toFixed(0)
              }}<span class="relevance-unit">%</span></span
            >
          </div>
          <div class="rel-track">
            <div
              class="rel-fill"
              :style="{ width: (book.best_score * 100).toFixed(0) + '%' }"
            />
          </div>
        </div>
      </div>

      <!-- 메타 -->
      <div class="meta-col">
        <div class="book-kdc" v-if="book.book_info?.kdc">
          단행본 · KDC {{ book.book_info.kdc }}
        </div>
        <h2 class="book-title" @click="openNLPage">
          {{ book.book_info?.title || book.book_id }}
        </h2>
        <p class="book-subtitle" v-if="book.book_info?.title_remainder">
          {{ book.book_info.title_remainder }}
          <span v-if="book.book_info?.part_number">
            · {{ book.book_info.part_number }}</span
          >
        </p>

        <div class="meta-grid">
          <template v-if="book.book_info?.personal_author">
            <span class="meta-k">저자</span>
            <span class="meta-v">{{ book.book_info.personal_author }}</span>
          </template>
          <template v-if="book.book_info?.corporate_author">
            <span class="meta-k">{{
              book.book_info?.personal_author ? "기관" : "저자"
            }}</span>
            <span class="meta-v">{{ book.book_info.corporate_author }}</span>
          </template>
          <template
            v-if="
              book.book_info?.publisher ||
              book.book_info?.pub_place ||
              book.book_info?.pub_date
            "
          >
            <span class="meta-k">출판</span>
            <span class="meta-v">
              <span v-if="book.book_info?.publisher">{{
                book.book_info.publisher
              }}</span>
              <span v-if="book.book_info?.pub_place">
                · {{ book.book_info.pub_place }}</span
              >
              <span v-if="book.book_info?.pub_date">
                ({{ book.book_info.pub_date }})</span
              >
            </span>
          </template>
          <template v-if="book.book_info?.series_title">
            <span class="meta-k">시리즈</span>
            <span class="meta-v">{{ book.book_info.series_title }}</span>
          </template>
          <template v-if="book.book_info?.extent">
            <span class="meta-k">분량</span>
            <span class="meta-v">{{ book.book_info.extent }}</span>
          </template>
          <template v-if="book.book_info?.isbn">
            <span class="meta-k">ISBN</span>
            <span class="meta-v">{{ book.book_info.isbn }}</span>
          </template>
          <template v-if="book.book_info?.language">
            <span class="meta-k">언어</span>
            <span class="meta-v">{{ book.book_info.language }}</span>
          </template>
          <template v-if="book.book_info?.subject">
            <span class="meta-k">주제</span>
            <span class="meta-v">{{ book.book_info.subject }}</span>
          </template>
        </div>

        <!-- 도서 요약 / 도서 소개 탭 -->
        <div
          class="summary-block"
          v-if="book?.book_info?.summary || book?.book_info?.introduction"
        >
          <div class="tab-bar">
            <button
              v-if="book?.book_info?.summary"
              class="tab-btn"
              :class="{ active: activeTab === 'summary' }"
              @click="activeTab = 'summary'"
            >
              도서 요약
            </button>
            <button
              v-if="book?.book_info?.introduction"
              class="tab-btn"
              :class="{ active: activeTab === 'introduction' }"
              @click="activeTab = 'introduction'"
            >
              도서 소개
            </button>
          </div>
          <div
            class="summary-body"
            :class="{ clamped: !summaryExpanded }"
            v-html="activeTab === 'summary' ? formattedSummary : formattedIntroduction"
          />
          <button
            class="expand-btn"
            @click="summaryExpanded = !summaryExpanded"
          >
            {{ summaryExpanded ? "접기" : "더보기" }}
          </button>
        </div>

        <!-- 액션 버튼 -->
        <div class="action-row">
          <button class="btn-primary" @click="pdfOpen = true">원문 보기</button>
          <button class="btn-ghost">대출 신청</button>
          <button class="btn-chat" @click="chatOpen = !chatOpen">
            <svg
              width="14"
              height="14"
              viewBox="0 0 16 16"
              fill="none"
              style="flex-shrink: 0"
            >
              <path
                d="M14 1H2a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h2v3l3-3h7a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1z"
                stroke="currentColor"
                stroke-width="1.4"
                stroke-linejoin="round"
              />
            </svg>
            {{ chatOpen ? "대화 닫기" : "이 책과 대화하기" }}
          </button>
        </div>
      </div>
    </div>

    <!-- 도서 심층 대화 (v-show로 마운트 유지 → 기록 보존) -->
    <BookChat
      v-show="chatOpen"
      :cnts-id="book.book_id"
      @close="chatOpen = false"
    />

    <!-- PDF 뷰어 모달 -->
    <PdfViewer
      v-if="pdfOpen"
      :cnts-id="book.book_id"
      :title="book.book_info?.title"
      @close="pdfOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import type { BookChunkGroup } from "~/types/search";
import { marked } from "marked";

const props = defineProps<{
  book: BookChunkGroup;
  answer?: string;
  keywords?: string[];
  isStreaming?: boolean;
}>();

const summaryExpanded = ref(false);
const chatOpen = ref(false);
const pdfOpen  = ref(false);
const activeTab = ref<"summary" | "introduction">(
  props.book?.book_info?.summary ? "summary" : "introduction",
);

function openNLPage() {
  const title = props.book?.book_info?.title || props.book?.book_id;
  if (!title) return;
  const url = `https://www.nl.go.kr/NL/contents/search.do?pageNum=1&pageSize=30&srchTarget=total&kwd=${encodeURIComponent(title)}#`;
  window.open(url, "_blank");
}

const formattedAnswer = computed(() => {
  if (!props.answer) return "";
  return marked.parse(props.answer) as string;
});

const formattedSummary = computed(
  () => marked.parse(props.book?.book_info?.summary ?? "") as string,
);

const formattedIntroduction = computed(
  () => marked.parse(props.book?.book_info?.introduction ?? "") as string,
);
</script>

<style scoped>
.top-result {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 28px;
}

/* ── AI 답변 패널 ── */
.answer-section {
  border-radius: var(--radius);
  background: radial-gradient(
    120% 100% at 0% 0%,
    oklch(0.96 0.05 277) 0%,
    oklch(0.98 0.02 317) 40%,
    #fff 80%
  );
  border: 1px solid oklch(0.9 0.04 277);
  padding: 2px;
}

.answer-inner {
  border-radius: calc(var(--radius) - 2px);
  padding: 22px 24px 20px;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.18),
    rgba(255, 255, 255, 0.6)
  );
}

.answer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.answer-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ai-orb {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  position: relative;
  filter: drop-shadow(0 0 8px oklch(0.7 0.18 277 / 0.5));
}

.answer-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.01em;
  display: flex;
  align-items: center;
  gap: 8px;
}

.answer-subtitle {
  font-size: 11.5px;
  color: var(--ink-3);
  margin-top: 2px;
}

.status-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
  flex-shrink: 0;
}

.status-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.answer-text {
  font-size: 14.5px;
  line-height: 1.75;
  color: var(--ink-2);
  letter-spacing: -0.005em;
}

.answer-text :deep(p) {
  margin: 0 0 8px 0;
}
/* 키워드 칩 */
.keyword-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}

.keyword-chip {
  font-size: 12px;
  padding: 5px 11px;
  background: #fff;
  border: 1px solid oklch(0.88 0.05 277);
  color: oklch(0.32 0.15 277);
  border-radius: 99px;
  font-weight: 500;
  letter-spacing: -0.01em;
}

.answer-text :deep(p:last-child) {
  margin-bottom: 0;
}
.answer-text :deep(strong) {
  font-weight: 600;
  color: var(--ink);
}
.answer-text :deep(ul),
.answer-text :deep(ol) {
  padding-left: 1.2em;
  margin: 4px 0 8px;
}

/* ── 도서 카드 ── */
.book-detail {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px 26px;
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 28px;
}

.cover-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.cover-area {
  cursor: pointer;
  border-radius: 8px;
  overflow: hidden;
}

.relevance-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 6px;
}

.relevance-label {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-3);
  font-weight: 500;
}

.relevance-pct {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.relevance-unit {
  color: var(--ink-4);
  font-size: 12px;
}

.rel-track {
  height: 5px;
  background: var(--line);
  border-radius: 99px;
  overflow: hidden;
}

.rel-fill {
  height: 100%;
  background: linear-gradient(
    90deg,
    oklch(0.72 0.14 277) 0%,
    oklch(0.55 0.22 277) 50%,
    oklch(0.5 0.22 317) 100%
  );
  border-radius: 99px;
  transition: width 0.8s ease;
}

/* 메타 */
.meta-col {
  min-width: 0;
}

.book-kdc {
  font-size: 10px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--ink-3);
  font-weight: 600;
  margin-bottom: 8px;
}

.book-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.25;
  margin: 0 0 4px;
  cursor: pointer;
}

.book-title:hover {
  color: oklch(0.45 0.2 277);
}

.book-subtitle {
  font-size: 13px;
  color: var(--ink-3);
  margin: 0 0 12px;
  line-height: 1.4;
}

.meta-grid {
  display: grid;
  grid-template-columns: 52px 1fr;
  row-gap: 5px;
  column-gap: 14px;
  margin-bottom: 16px;
  font-size: 13px;
  align-items: start;
}

.meta-k {
  color: var(--ink-3);
  font-size: 12px;
  padding-top: 1px;
  align-self: start;
}

.meta-v {
  color: var(--ink-2);
  word-break: break-word;
  line-height: 1.5;
}

/* 도서 요약/소개 탭 */
.summary-block {
  background: var(--line-2);
  border-radius: var(--radius-sm);
  margin-bottom: 16px;
  overflow: hidden;
}

.tab-bar {
  display: flex;
  border-bottom: 1px solid var(--line);
}

.tab-btn {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink-3);
  background: none;
  border: none;
  padding: 9px 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn.active {
  color: oklch(0.4 0.18 277);
  border-bottom-color: oklch(0.55 0.22 277);
}

.tab-btn:not(.active):hover {
  color: var(--ink-2);
}

.summary-body {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--ink-2);
  margin: 0;
  padding: 12px 16px 8px;
}

.summary-body.clamped {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.summary-body :deep(p) {
  margin: 0 0 6px 0;
}
.summary-body :deep(strong) {
  font-weight: 600;
  color: var(--ink);
}

.expand-btn {
  font-size: 12px;
  color: var(--ink);
  background: none;
  border: none;
  padding: 0 16px 10px;
  display: block;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
  font-weight: 500;
}

/* 액션 버튼 */
.action-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-primary {
  font-size: 13px;
  padding: 8px 16px;
  border-radius: 8px;
  background: var(--ink);
  color: #fff;
  border: 1px solid var(--ink);
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-primary:hover {
  opacity: 0.85;
}

.btn-ghost {
  font-size: 13px;
  padding: 8px 14px;
  border-radius: 8px;
  background: #fff;
  color: var(--ink-2);
  border: 1px solid var(--line);
  cursor: pointer;
  transition: background 0.15s;
}

.btn-ghost:hover {
  background: var(--line-2);
}

.btn-chat {
  font-size: 13px;
  padding: 8px 14px;
  border-radius: 8px;
  background: linear-gradient(
    110deg,
    oklch(0.93 0.06 277) 0%,
    oklch(0.95 0.04 317) 100%
  );
  color: oklch(0.28 0.18 277);
  border: 1px solid oklch(0.86 0.06 277);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  transition: filter 0.15s;
}
.btn-chat:hover {
  filter: brightness(0.95);
}

@media (max-width: 640px) {
  .book-detail {
    grid-template-columns: 1fr;
  }
  .cover-col {
    flex-direction: row;
    align-items: flex-start;
  }
  .cover-area {
    width: 120px;
    flex-shrink: 0;
  }
}
</style>
