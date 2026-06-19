<template>
  <div class="category-accordion">
    <!-- <div class="ca-header">
      <span class="ca-title">카테고리별 추천</span>
    </div> -->

    <div v-if="!grouped.length" class="ca-empty">
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path
          d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"
        />
      </svg>
      <p>검색 결과가 표시됩니다</p>
    </div>

    <div v-else class="ca-list scrollbar-zinc">
      <div v-for="group in grouped" :key="group.category" class="ca-item">
        <!-- 아코디언 헤더 -->
        <button
          class="ca-toggle"
          :class="{ open: openCategories.has(group.category) }"
          @click="toggle(group.category)"
        >
          <span class="ca-category-name">
            <span class="ca-kdc-badge">{{ group.kdc }}</span>
            {{ group.label }}
          </span>
          <span class="ca-count">{{ group.books.length }}</span>
          <svg
            class="ca-chevron"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        <!-- 아코디언 본문 -->
        <transition name="accordion">
          <ul v-if="openCategories.has(group.category)" class="ca-books">
            <li
              v-for="book in group.books"
              :key="book.book_id"
              class="ca-book"
              @click="openBook(book)"
            >
              <span class="ca-book-title">{{
                book.book_info?.title ?? book.book_id
              }}</span>
              <span class="ca-book-author">
                {{
                  book.book_info?.personal_author ||
                  book.book_info?.corporate_author ||
                  ""
                }}
              </span>
            </li>
          </ul>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BookChunkGroup } from "~/types/search";

const props = defineProps<{
  books: BookChunkGroup[];
}>();

const KDC_LABELS: Record<string, string> = {
  "0": "총류",
  "1": "철학·심리·윤리",
  "2": "종교",
  "3": "사회과학",
  "4": "자연과학",
  "5": "기술과학",
  "6": "예술",
  "7": "언어",
  "8": "문학",
  "9": "역사·지리",
};

interface CategoryGroup {
  category: string; // first digit of KDC
  kdc: string; // display KDC key
  label: string;
  books: BookChunkGroup[];
}

const grouped = computed<CategoryGroup[]>(() => {
  const map = new Map<string, BookChunkGroup[]>();

  for (const book of props.books) {
    const kdc = book.book_info?.kdc ?? "";
    const key = kdc ? kdc.charAt(0) : "?";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(book);
  }

  return [...map.entries()]
    .map(([key, books]) => ({
      category: key,
      kdc: key === "?" ? "-" : `${key}xx`,
      label: KDC_LABELS[key] ?? "기타",
      books,
    }))
    .sort((a, b) => a.category.localeCompare(b.category));
});

// 기본으로 첫 번째 카테고리 열어두기
const openCategories = ref<Set<string>>(new Set());

watch(
  grouped,
  (val) => {
    if (val.length && openCategories.value.size === 0) {
      const firstCategory = val[0]?.category;
      if (firstCategory) {
        openCategories.value = new Set([firstCategory]);
      }
    }
  },
  { immediate: true },
);

function toggle(category: string) {
  const next = new Set(openCategories.value);
  if (next.has(category)) next.delete(category);
  else next.add(category);
  openCategories.value = next;
}

function openBook(book: BookChunkGroup) {
  const title = book.book_info?.title ?? book.book_id;

  const url = `https://www.nl.go.kr/NL/contents/search.do?pageNum=1&pageSize=30&srchTarget=total&kwd=${encodeURIComponent(title)}#`;
  window.open(url, "_blank", "noopener,noreferrer");
}
</script>

<style scoped>
.category-accordion {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px 0;
}

.ca-header {
  padding: 0 16px 12px;
  border-bottom: 1px solid #f0f0f1;
}

.ca-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #a1a1aa;
  text-transform: uppercase;
}

.ca-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 16px;
  color: #d4d4d8;
}

.ca-empty p {
  font-size: 13px;
  color: #a1a1aa;
  text-align: center;
}

.ca-item {
  min-width: 0;
}

.ca-list {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex: 1;
  padding: 8px 0;
  min-width: 0;
}

/* 아코디언 토글 버튼 */
.ca-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: calc(100% - 8px);
  min-width: 0;
  padding: 10px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  border-radius: 8px;
  margin: 1px 0;
  transition: background 0.15s;
}

.ca-toggle:hover {
  background: #f4f4f5;
}

.ca-category-name {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: #27272a;
  min-width: 0;
}

.ca-kdc-badge {
  font-size: 10px;
  font-weight: 700;
  color: #71717a;
  background: #f4f4f5;
  border-radius: 4px;
  padding: 1px 5px;
  flex-shrink: 0;
}

.ca-count {
  font-size: 11px;
  font-weight: 600;
  color: #a1a1aa;
  background: #f4f4f5;
  border-radius: 999px;
  padding: 1px 7px;
  flex-shrink: 0;
}

.ca-chevron {
  color: #a1a1aa;
  flex-shrink: 0;
  transition: transform 0.2s;
}

.ca-toggle.open .ca-chevron {
  transform: rotate(180deg);
}

/* 아코디언 본문 */
.ca-books {
  list-style: none;
  margin: 0;
  padding: 0 4px 4px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.ca-book {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px 8px 28px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  overflow-x: hidden;
}

.ca-book:hover {
  background: #fafafa;
}

.ca-book-title {
  font-size: 12px;
  color: #3f3f46;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.ca-book-author {
  font-size: 11px;
  color: #a1a1aa;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 아코디언 트랜지션 */
.accordion-enter-active,
.accordion-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.accordion-enter-from,
.accordion-leave-to {
  opacity: 0;
  max-height: 0;
}

.accordion-enter-to,
.accordion-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
