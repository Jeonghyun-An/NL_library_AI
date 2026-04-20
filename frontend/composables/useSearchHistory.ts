import type { SearchResponse } from "~/types/search";

export interface HistoryEntry {
  id: string;
  query: string;
  timestamp: number;
  result: SearchResponse;
}

const STORAGE_KEY = "nl-search-history";
const MAX_ENTRIES = 30;

export function useSearchHistory() {
  const history = ref<HistoryEntry[]>([]);

  // process.client 대신 onMounted 사용 — SSR hydration 이후 실행 보장
  onMounted(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) history.value = JSON.parse(stored);
    } catch {}
  });

  function _save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history.value));
  }

  function addEntry(query: string, result: SearchResponse): string {
    const id = crypto.randomUUID();
    history.value = [
      { id, query, timestamp: Date.now(), result },
      ...history.value,
    ];
    if (history.value.length > MAX_ENTRIES) {
      history.value = history.value.slice(0, MAX_ENTRIES);
    }
    _save();
    return id;
  }

  function clearHistory() {
    history.value = [];
    localStorage.removeItem(STORAGE_KEY);
  }

  return { history, addEntry, clearHistory };
}
