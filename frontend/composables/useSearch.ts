import type { SearchRequest, SearchResponse } from "~/types/search";
import { apiErrorMessage } from "~/utils/apiErrors";
import { BOOK_SEARCH_TEXT } from "~/utils/bookErrors";
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
    } catch (e: unknown) {
      // 화면(보존 화면 /search-classic)에 보일 한 줄 — 영문 ofetch 메시지·서버 detail 원문 대신 공통 규칙(apiErrorMessage)으로
      // '검색하지 못했어요 — 이유'. 이유가 두 문장이면 '\n' 으로 이어 오고 화면은 줄로 그린다(.error-area white-space: pre-line)
      error.value = apiErrorMessage(e, BOOK_SEARCH_TEXT.failedTitle);
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
