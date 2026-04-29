<template>
  <div class="book-card" @click="$emit('select', book)" style="cursor: pointer">
    <div class="card-cover">
      <BookCover :book-id="book.book_id" size="small" />
    </div>
    <div class="card-info">
      <h3 class="card-title">{{ book.book_info?.title || book.book_id }}</h3>
      <p
        class="card-author"
        v-if="
          book.book_info?.personal_author || book.book_info?.corporate_author
        "
      >
        {{
          book.book_info?.personal_author ||
          book.book_info?.corporate_author ||
          ""
        }}
      </p>
      <p class="card-publisher" v-if="book.book_info?.publisher">
        {{ book.book_info.publisher }}
        <span v-if="book.book_info?.pub_date"
          >({{ book.book_info.pub_date }})</span
        >
      </p>
      <div class="card-footer">
        <div class="card-score">{{ (book.best_score * 100).toFixed(0) }}%</div>
        <button
          class="nl-link-btn"
          @click.stop="openNLPage"
          title="도서관에서 검색"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <path
              d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"
            />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BookChunkGroup } from "~/types/search";

const props = defineProps<{
  book: BookChunkGroup;
}>();

const emit = defineEmits<{
  select: [book: BookChunkGroup];
}>();

function openNLPage() {
  const title = props.book.book_info?.title || props.book.book_id;
  const url = `https://www.nl.go.kr/NL/contents/search.do?pageNum=1&pageSize=30&srchTarget=total&kwd=${encodeURIComponent(title)}#`;
  window.open(url, "_blank");
}
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
  border-radius: 14px 14px 0 0;
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
  font-size: 12px;
  color: #8a8a91;
  margin: 0 0 2px 0;
}

.card-publisher {
  font-size: 11px;
  color: #a1a1aa;
  margin: 0 0 8px 0;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-score {
  padding: 2px 8px;
  background: #f4f4f5;
  color: #27272a;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.nl-link-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #a1a1aa;
  cursor: pointer;
  transition: all 0.15s;
  padding: 0;
}

.nl-link-btn:hover {
  background: #f4f4f5;
  color: #52525b;
}
</style>
