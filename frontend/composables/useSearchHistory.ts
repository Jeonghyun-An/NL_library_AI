import type { HistoryEntry } from "~/types/history";

export function useSearchHistory() {
  const history = ref<HistoryEntry[]>([]);

  function setHistory(data: HistoryEntry[]) {
    history.value = data;
  }

  function clearHistory() {
    history.value = [];
  }

  return {
    history,
    setHistory,
    clearHistory,
  };
}
