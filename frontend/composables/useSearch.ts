import type { SearchRequest, SearchResponse } from "~/types/search";

export function useSearch() {
  const config = useRuntimeConfig();

  const loading = ref(false);
  const error = ref<string | null>(null);
  const result = ref<SearchResponse | null>(null);

  function generateUUID() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }

    // fallback
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  const sessionId = useState<string | null>("sessionId", () => {
    if (process.client) {
      let sid = localStorage.getItem("sid");
      if (!sid) {
        sid = generateUUID();
        localStorage.setItem("sid", sid);
      }
      return sid;
    }
    return null;
  });

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
          headers: sessionId.value ? { "x-session-id": sessionId.value } : {},
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

  return { loading, error, result, search, reset, generateUUID };
}
