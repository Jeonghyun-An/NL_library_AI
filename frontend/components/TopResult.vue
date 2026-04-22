<template>
  <div class="top-result">
    <!-- LLM 추천 이유 -->
    <div class="answer-section" v-if="answer || isStreaming">
      <div class="answer-label">
        <span class="ai-icon"> </span>
        <img
          v-if="isStreaming"
          src="/ic_ing.gif"
          class="status-icon"
          alt="생성 중"
        />
        <img
          v-else-if="answer"
          src="/ic_done.svg"
          class="status-icon"
          alt="완료"
        />
        AI 추천 답변
      </div>
      <div class="answer-text" v-html="formattedAnswer" />
    </div>

    <!-- 도서 커버 + 메타 -->
    <div class="book-detail" v-if="book">
      <div class="cover-area" @click="openNLPage" style="cursor: pointer">
        <BookCover :book-id="book.book_id" size="large" />
      </div>
      <div class="meta-area">
        <h2 class="book-title" @click="openNLPage" style="cursor: pointer">
          {{ book.book_info?.title || book.book_id }}
        </h2>
        <p class="book-subtitle" v-if="book.book_info?.title_remainder">
          {{ book.book_info.title_remainder }}
          <span v-if="book.book_info?.part_number">
            · {{ book.book_info.part_number }}</span
          >
        </p>
        <p class="book-subtitle" v-else-if="book.book_info?.part_number">
          {{ book.book_info.part_number }}
        </p>

        <div class="meta-grid">
          <template v-if="book.book_info?.personal_author">
            <span class="meta-label">저자</span>
            <span class="meta-value">{{ book.book_info.personal_author }}</span>
          </template>
          <template v-if="book.book_info?.corporate_author">
            <span class="meta-label">{{
              book.book_info?.personal_author ? "기관" : "저자"
            }}</span>
            <span class="meta-value">{{
              book.book_info.corporate_author
            }}</span>
          </template>
          <template v-if="book.book_info?.series_title">
            <span class="meta-label">시리즈</span>
            <span class="meta-value">{{ book.book_info.series_title }}</span>
          </template>
          <template
            v-if="
              book.book_info?.publisher ||
              book.book_info?.pub_place ||
              book.book_info?.pub_date
            "
          >
            <span class="meta-label">출판</span>
            <span class="meta-value">
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
          <template v-if="book.book_info?.extent">
            <span class="meta-label">분량</span>
            <span class="meta-value">{{ book.book_info.extent }}</span>
          </template>
          <template v-if="book.book_info?.isbn">
            <span class="meta-label">ISBN</span>
            <span class="meta-value">{{ book.book_info.isbn }}</span>
          </template>
          <template v-if="book.book_info?.kdc">
            <span class="meta-label">KDC</span>
            <span class="meta-value">{{ book.book_info.kdc }}</span>
          </template>
          <template v-if="book.book_info?.language">
            <span class="meta-label">언어</span>
            <span class="meta-value">{{ book.book_info.language }}</span>
          </template>
          <template v-if="book.book_info?.subject">
            <span class="meta-label">주제</span>
            <span class="meta-value">{{ book.book_info.subject }}</span>
          </template>
          <template v-if="book.book_info?.keyword">
            <span class="meta-label">키워드</span>
            <span class="meta-value">{{ book.book_info.keyword }}</span>
          </template>
        </div>

        <div class="relevance">
          관련도 {{ (book.best_score * 100).toFixed(1) }}%
        </div>
      </div>
    </div>

    <!-- 도서 소개 — 카드 전체 너비 / 기본 3줄 -->
    <div class="book-summary" v-if="book?.book_info?.summary">
      <span class="summary-label">도서 소개</span>
      <div
        class="summary-body"
        :class="{ clamped: !summaryExpanded }"
        v-html="formattedSummary"
      />
      <button class="expand-btn" @click="summaryExpanded = !summaryExpanded">
        {{ summaryExpanded ? "접기" : "더보기" }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BookChunkGroup } from "~/types/search";
import { marked } from "marked";

const props = defineProps<{
  book: BookChunkGroup;
  answer?: string;
  isStreaming?: boolean;
}>();

const summaryExpanded = ref(false);

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
</script>

<style scoped>
.top-result {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid #e4e4e7;
  border-radius: 20px;
  padding: 28px;
  margin-bottom: 32px;
  box-shadow:
    0 10px 25px rgba(0, 0, 0, 0.04),
    0 2px 6px rgba(0, 0, 0, 0.03);
}

.answer-section {
  position: relative;
  background: linear-gradient(
    135deg,
    rgba(109, 40, 217, 0.04) 0%,
    rgba(99, 102, 241, 0.05) 100%
  );
  border: 1px solid rgba(109, 40, 217, 0.18);
  border-radius: 14px;
  padding: 16px 16px 16px 18px;
  margin-bottom: 20px;
  overflow: hidden;
}

.answer-section::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #a78bfa 0%, #6366f1 50%, #818cf8 100%);
  border-radius: 14px 14px 0 0;
}

.answer-section::after {
  content: "";
  position: absolute;
  bottom: -30px;
  right: -30px;
  width: 120px;
  height: 120px;
  background: radial-gradient(
    circle,
    rgba(139, 92, 246, 0.08) 0%,
    transparent 70%
  );
  pointer-events: none;
}

.answer-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #7c3aed;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.ai-icon {
  display: flex;
  align-items: center;
  color: #8b5cf6;
}

.done-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  background: rgba(139, 92, 246, 0.1);
  color: #7c3aed;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.status-icon {
  width: 36px;
  height: 36px;
  object-fit: contain;
  flex-shrink: 0;
}

.answer-text {
  font-size: 15px;
  line-height: 1.7;
  color: #1e293b;
}

.book-detail {
  display: flex;
  gap: 24px;
}

.cover-area {
  flex-shrink: 0;
  width: 180px;
}

.meta-area {
  flex: 1;
  min-width: 0;
}

.book-title {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 4px 0;
  cursor: pointer;
}

.book-title:hover {
  color: #3b82f6;
}

.book-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0 0 12px 0;
  line-height: 1.4;
}

.meta-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 10px;
  margin-bottom: 12px;
}

.meta-label {
  font-size: 12px;
  color: #a1a1aa;
  font-weight: 500;
  white-space: nowrap;
  padding-top: 1px;
}

.meta-value {
  font-size: 13px;
  color: #52525b;
  line-height: 1.5;
  word-break: break-word;
}

.relevance {
  display: inline-block;
  margin-top: 10px;
  padding: 4px 12px;
  background: #f4f4f5;
  color: #18181b;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

/* 도서 소개 — 카드 하단 전체 너비 */
.book-summary {
  margin-top: 20px;
  padding: 14px;
  background: #fafafa;
  border-radius: 12px;
  border: 1px solid #e4e4e7;
}

.summary-label {
  font-size: 12px;
  font-weight: 600;
  color: #a1a1aa;
  display: block;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
}

.summary-body {
  font-size: 14px;
  line-height: 1.7;
  color: #3f3f46;
  margin: 0 0 8px 0;
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
  color: #1e293b;
}

.expand-btn {
  font-size: 13px;
  color: #71717a;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.expand-btn:hover {
  color: #27272a;
}

.answer-text :deep(p) {
  margin: 0 0 8px 0;
}

.answer-text :deep(strong) {
  font-weight: 600;
  color: #1e293b;
}

.answer-text :deep(ul),
.answer-text :deep(ol) {
  padding-left: 1.2em;
  margin: 4px 0 8px;
}

.answer-text :deep(code) {
  background: #f0f0f3;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
}

@media (max-width: 640px) {
  .book-detail {
    flex-direction: column;
  }
  .cover-area {
    width: 120px;
  }
}
</style>
