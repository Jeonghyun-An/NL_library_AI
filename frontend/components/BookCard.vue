<template>
  <div class="book-card">
    <div class="card-cover">
      <BookCover :book-id="book.book_id" size="small" />
    </div>
    <div class="card-info">
      <h3 class="card-title">{{ book.book_info?.title || book.book_id }}</h3>
      <p class="card-author" v-if="book.book_info?.personal_author">
        {{ book.book_info.personal_author }}
      </p>
      <p class="card-publisher" v-if="book.book_info?.publisher">
        {{ book.book_info.publisher }}
        <span v-if="book.book_info?.pub_date"
          >({{ book.book_info.pub_date }})</span
        >
      </p>
      <div class="card-score">{{ (book.best_score * 100).toFixed(0) }}%</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BookChunkGroup } from "~/types/search";

defineProps<{
  book: BookChunkGroup;
}>();
</script>

<style scoped>
.book-card {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 14px;

  transition: all 0.2s ease;
}

.book-card:hover {
  transform: translateY(-4px);

  box-shadow:
    0 12px 30px rgba(0, 0, 0, 0.08),
    0 4px 10px rgba(0, 0, 0, 0.04);

  border-color: #d4d4d8;
}

.card-cover {
  aspect-ratio: 3 / 4;
  overflow: hidden;
  background: #f1f5f9;
}

.card-info {
  padding: 12px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 4px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-author {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 2px 0;
}

.card-publisher {
  font-size: 12px;
  color: #94a3b8;
  margin: 0 0 8px 0;
}

.card-score {
  padding: 2px 8px;

  background: #f4f4f5;
  color: #27272a;

  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
</style>
