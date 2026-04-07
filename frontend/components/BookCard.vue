<template>
  <div
    class="bg-white border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow"
  >
    <div class="flex justify-between items-start gap-4">
      <div class="flex-1 min-w-0">
        <h3 class="text-base font-semibold text-gray-900 truncate">
          {{ book.title }}
        </h3>
        <p class="mt-0.5 text-sm text-gray-500">
          {{
            [book.author, book.publisher, book.pub_year]
              .filter(Boolean)
              .join(" · ")
          }}
        </p>
        <p v-if="book.subject" class="mt-1 text-xs text-gray-400">
          {{ book.subject }}
        </p>
      </div>
      <span
        class="shrink-0 text-xs font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded"
      >
        {{ (score * 100).toFixed(0) }}%
      </span>
    </div>

    <p
      v-if="reason"
      class="mt-3 text-sm text-gray-600 leading-relaxed border-l-2 border-blue-200 pl-3"
    >
      {{ reason }}
    </p>

    <p v-if="book.summary" class="mt-2 text-xs text-gray-400 line-clamp-2">
      {{ book.summary }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { BookOut } from "../types/book";

defineProps<{
  book: BookOut;
  score: number;
  reason: string;
}>();
</script>
