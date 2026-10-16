import type { SearchRequest, SearchResponse } from "~/types/search";
import { readOrCreateBrowserId, safeLocalStorage } from "~/utils/browserId";

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

  // 저장소가 막힌 브라우저(사생활 보호 창·쿠키 차단)에서는 localStorage 가 던진다 — 여기서 던지면 /search-classic 이 통째로 그려지지 않는다.
  // 읽지 못하면 새 ID 를 만들고, 저장하지 못하면 이 페이지에 있는 동안만 쓴다(utils/browserId)
  const sessionId = useState<string | null>("sessionId", () =>
    process.client ? readOrCreateBrowserId(safeLocalStorage(), generateUUID) : null,
  );

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
