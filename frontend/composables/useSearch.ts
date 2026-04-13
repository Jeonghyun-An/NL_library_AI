import type { SearchRequest, SearchResponse } from "~/types/search";

export function useSearch() {
  const config = useRuntimeConfig();
  const loading = ref(false);
  const error = ref<string | null>(null);
  const result = ref<SearchResponse | null>(null);

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

  return { loading, error, result, search, reset };
}
