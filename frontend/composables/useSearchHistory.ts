import type { HistoryEntry } from "~/types/history";

const STORAGE_KEY = "skx_search_history";
const MAX_ENTRIES = 30;

// Module-level singleton state — shared across all composable calls
const _history = ref<HistoryEntry[]>([]);
let _loaded = false;

export function useSearchHistory() {
  // Lazy-load from localStorage once per app lifetime
  if (process.client && !_loaded) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) _history.value = JSON.parse(raw);
    } catch {
      /* corrupted storage — start fresh */
    }
    _loaded = true;
  }

  function _persist() {
    if (!process.client) return;
    // 쿼터 초과 시 오래된 항목(뒤쪽)을 5개씩 줄여가며 재시도
    let items = _history.value;
    while (true) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
        _history.value = items;
        return;
      } catch {
        if (items.length <= 1) return; // 단일 항목도 저장 불가 — 포기
        items = items.slice(0, Math.max(1, items.length - 5));
      }
    }
  }

  /** Add a new entry to the front of the list. Returns the generated id. */
  function addEntry(entry: Omit<HistoryEntry, "id" | "timestamp">): string {
    const id = Date.now().toString();
    _history.value.unshift({ id, timestamp: new Date().toISOString(), ...entry });
    if (_history.value.length > MAX_ENTRIES) {
      _history.value = _history.value.slice(0, MAX_ENTRIES);
    }
    _persist();
    return id;
  }

  /** Patch the aiSummary field of an existing entry after streaming completes. */
  function updateAiSummary(id: string, summary: string) {
    const entry = _history.value.find((h) => h.id === id);
    if (entry) {
      entry.aiSummary = summary;
      _persist();
    }
  }

  /** Remove all entries of a given type. */
  function clearByType(type: "book" | "paper") {
    _history.value = _history.value.filter((h) => h.type !== type);
    _persist();
  }

  /** Lookup a single entry by id (used on restore navigation). */
  function getById(id: string): HistoryEntry | undefined {
    return _history.value.find((h) => h.id === id);
  }

  const bookHistory = computed(() =>
    _history.value.filter((h) => h.type === "book"),
  );
  const paperHistory = computed(() =>
    _history.value.filter((h) => h.type === "paper"),
  );

  return {
    history: _history,
    bookHistory,
    paperHistory,
    addEntry,
    updateAiSummary,
    clearByType,
    getById,
  };
}
