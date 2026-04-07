<template>
  <div class="min-h-screen bg-gray-50">
    <header class="bg-white border-b border-gray-200 px-6 py-4">
      <h1 class="text-lg font-semibold text-gray-800">
        국립중앙도서관 의미 기반 검색
      </h1>
    </header>

    <main class="max-w-2xl mx-auto px-4 py-10">
      <SearchBar v-model="query" :loading="loading" @search="doSearch" />

      <p v-if="response?.rewritten_query" class="mt-3 text-sm text-gray-400">
        해석된 의도:
        <em class="text-gray-600">{{ response.rewritten_query }}</em>
        <span class="ml-2">{{ response.elapsed_ms }}ms</span>
      </p>

      <div class="mt-6 space-y-4">
        <BookCard
          v-for="r in response?.results"
          :key="r.book.nl_id"
          :book="r.book"
          :score="r.score"
          :reason="r.reason"
        />
      </div>

      <p
        v-if="searched && !loading && !response?.results?.length"
        class="mt-16 text-center text-gray-400 text-sm"
      >
        검색 결과가 없습니다.
      </p>

      <p
        v-if="error"
        class="mt-6 p-4 bg-red-50 text-red-500 rounded-lg text-sm"
      >
        {{ error }}
      </p>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import type { SearchResponse } from "../types/book";

const query = ref("");
const loading = ref(false);
const searched = ref(false);
const error = ref<string | null>(null);
const response = ref<SearchResponse | null>(null);

async function doSearch() {
  if (!query.value.trim()) return;
  loading.value = true;
  searched.value = true;
  error.value = null;
  response.value = null;

  try {
    const res = await fetch("/api/books/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query.value, top_k: 5, use_rerank: true }),
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data?.detail ?? "검색 중 오류가 발생했습니다.");
    }
    response.value = (await res.json()) as SearchResponse;
  } catch (e: any) {
    error.value = e?.message ?? "검색 중 오류가 발생했습니다.";
  } finally {
    loading.value = false;
  }
}
</script>
