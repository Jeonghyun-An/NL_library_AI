<template>
  <div class="top-result">
    <!-- LLM 답변 -->
    <div class="answer-section" v-if="answer">
      <div class="answer-label">AI 추천 답변</div>
      <div class="answer-text" v-html="formattedAnswer" />
    </div>

    <!-- Top 1 도서 정보 -->
    <div class="book-detail" v-if="book">
      <div class="cover-area">
        <BookCover :book-id="book.book_id" />
      </div>
      <div class="meta-area">
        <h2 class="book-title">{{ book.book_info?.title || book.book_id }}</h2>
        <div class="meta-row" v-if="book.book_info?.personal_author">
          <span class="meta-label">저자</span>
          <span>{{ book.book_info.personal_author }}</span>
        </div>
        <div class="meta-row" v-if="book.book_info?.publisher">
          <span class="meta-label">출판사</span>
          <span>{{ book.book_info.publisher }}</span>
        </div>
        <div class="meta-row" v-if="book.book_info?.pub_date">
          <span class="meta-label">발행년</span>
          <span>{{ book.book_info.pub_date }}</span>
        </div>
        <div class="meta-row" v-if="book.book_info?.kdc">
          <span class="meta-label">KDC</span>
          <span>{{ book.book_info.kdc }}</span>
        </div>
        <div class="meta-row" v-if="book.book_info?.subject">
          <span class="meta-label">주제</span>
          <span>{{ book.book_info.subject }}</span>
        </div>
        <div class="relevance">
          관련도 {{ (book.best_score * 100).toFixed(1) }}%
        </div>
        <div class="snippet" v-if="topChunkText">
          <span class="snippet-label">관련 구절</span>
          <p>{{ topChunkText }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BookChunkGroup } from "~/types/search";

const props = defineProps<{
  book: BookChunkGroup;
  answer?: string;
}>();

const formattedAnswer = computed(() => {
  if (!props.answer) return "";
  return props.answer.replace(/\n/g, "<br>");
});

const topChunkText = computed(() => {
  const chunks = props.book.chunks;
  if (!chunks?.length) return "";
  const best = [...chunks].sort(
    (a, b) => (b.rerank_score || b.score) - (a.rerank_score || a.score),
  )?.[0];
  if (!best) return "";
  return best.text.length > 300 ? best.text.slice(0, 300) + "..." : best.text;
});
</script>

<style scoped>
.top-result {
  background: #f8fafc;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 32px;
}

.answer-section {
  margin-bottom: 24px;
}

.answer-label {
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
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
  color: #0f172a;
  margin: 0 0 12px 0;
}

.meta-row {
  font-size: 14px;
  color: #475569;
  margin-bottom: 4px;
}

.meta-label {
  display: inline-block;
  width: 56px;
  font-weight: 600;
  color: #64748b;
}

.relevance {
  display: inline-block;
  margin-top: 12px;
  padding: 4px 12px;
  background: #dbeafe;
  color: #1d4ed8;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.snippet {
  margin-top: 16px;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.snippet-label {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  display: block;
  margin-bottom: 6px;
}

.snippet p {
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
  margin: 0;
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
