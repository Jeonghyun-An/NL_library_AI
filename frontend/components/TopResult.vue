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
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);

  border: 1px solid #e4e4e7; /* zinc-200 */
  border-radius: 20px;

  padding: 28px;
  margin-bottom: 32px;

  box-shadow:
    0 10px 25px rgba(0, 0, 0, 0.04),
    0 2px 6px rgba(0, 0, 0, 0.03);
}

.answer-section {
  background: #fafafa;
  border-radius: 12px;
  padding: 16px;
}
.answer-label {
  font-size: 12px;
  font-weight: 600;

  color: #71717a; /* zinc-500 */
  letter-spacing: 0.08em;
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
  color: #1e293b; /* slate-800 */
}

.meta-row {
  font-size: 14px;
  color: #52525b; /* zinc-600 */
}

.meta-label {
  color: #a1a1aa; /* zinc-400 */
}

.relevance {
  margin-top: 12px;
  padding: 4px 12px;

  background: #f4f4f5; /* zinc-100 */
  color: #18181b; /* zinc-900 */

  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.snippet {
  margin-top: 16px;
  padding: 14px;

  background: #fafafa;
  border-radius: 12px;

  border: 1px solid #e4e4e7;
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
  color: #3f3f46;
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
