// frontend/utils/historyState.ts
import { computed, ref, type ComputedRef, type Ref } from "vue";
import type {
  HistoryEntry,
  HistoryEntryInput,
  HistoryKind,
  HistoryPatch,
  ResearchEntry,
} from "~/types/history";
import { HISTORY_PAGE_SIZE, errorStatus, findRecentDuplicate, type HybridHistoryStore } from "./historyStore";

const KINDS: HistoryKind[] = ["book", "paper", "research"];

export interface HistoryStateOptions {
  genId: () => string;
  now?: () => number;
  onChange?: () => void;
  warn?: (message: string, err: unknown) => void;
}

export interface HistoryState {
  entries: Ref<HistoryEntry[]>;
  byKind(kind: HistoryKind): ComputedRef<HistoryEntry[]>;
  refresh(kind?: HistoryKind): Promise<void>;
  add(input: HistoryEntryInput): Promise<HistoryEntry>;
  patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null>;
  remove(id: string): Promise<void>;
  clear(kind: HistoryKind): Promise<void>;
  get(id: string): Promise<HistoryEntry | null>;
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
}

/** 반응형 목록에는 무거운 필드를 두지 않는다 — 복원은 get(id) 로 상세를 읽는다 */
export function toListItem(entry: HistoryEntry): HistoryEntry {
  if (entry.kind === "research") return entry;
  const item = { ...entry };
  delete item.snapshot;
  delete item.ai;
  return item;
}

export function createHistoryState(store: () => HybridHistoryStore, opts: HistoryStateOptions): HistoryState {
  const now = opts.now ?? Date.now;
  const warn = opts.warn ?? ((message: string, err: unknown) => console.warn(`[history] ${message}`, err));
  const changed = () => opts.onChange?.();
  const entries = ref<HistoryEntry[]>([]);
  const kindViews = new Map<HistoryKind, ComputedRef<HistoryEntry[]>>();

  function place(entry: HistoryEntry, toTop: boolean): void {
    const item = toListItem(entry);
    const idx = entries.value.findIndex((e) => e.id === entry.id);
    if (toTop || idx < 0) {
      entries.value = [item, ...entries.value.filter((e) => e.id !== entry.id)];
      return;
    }
    const next = entries.value.slice();
    next[idx] = item;
    entries.value = next;
  }

  function drop(id: string): void {
    entries.value = entries.value.filter((e) => e.id !== id);
  }

  function byKind(kind: HistoryKind): ComputedRef<HistoryEntry[]> {
    let view = kindViews.get(kind);
    if (!view) {
      view = computed(() => entries.value.filter((e) => e.kind === kind));
      kindViews.set(kind, view);
    }
    return view;
  }

  async function refresh(kind?: HistoryKind): Promise<void> {
    const kinds = kind ? [kind] : KINDS;
    await Promise.all(
      kinds.map(async (k) => {
        try {
          const { items } = await store().list(k, { limit: HISTORY_PAGE_SIZE });
          entries.value = [...entries.value.filter((e) => e.kind !== k), ...items.map(toListItem)];
        } catch (e) {
          warn("목록을 읽지 못했다", e);
        }
      }),
    );
  }

  // 축약 결과가 서버 상한(200KB)을 넘으면 413 이다. 4xx 는 보낼 편지함이 다시 보내지 않아
  // 그대로 두면 기록이 사라진다 — 결과 없이라도 남긴다(복원은 q 재검색으로 물러선다).
  async function putEntry(entry: HistoryEntry): Promise<HistoryEntry> {
    try {
      return await store().put(entry);
    } catch (e) {
      if (errorStatus(e) !== 413 || entry.kind === "research" || !entry.snapshot) throw e;
      const lighter = { ...entry };
      delete lighter.snapshot;
      return store().put(lighter);
    }
  }

  async function add(input: HistoryEntryInput): Promise<HistoryEntry> {
    const nowMs = now();
    const iso = new Date(nowMs).toISOString();
    const dup = findRecentDuplicate(entries.value, input, nowMs);
    const entry = {
      ...input,
      id: dup?.id ?? opts.genId(),
      createdAt: dup?.createdAt ?? iso,
      updatedAt: iso,
    } as HistoryEntry;
    place(entry, true);
    try {
      const saved = await putEntry(entry);
      place(saved, true);
      changed();
      return saved;
    } catch (e) {
      warn("기록을 저장하지 못했다", e);
      if (!dup) drop(entry.id);
      return entry;
    }
  }

  async function patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null> {
    try {
      const saved = await store().patch(id, partial);
      if (!saved) drop(id);
      else if (entries.value.some((e) => e.id === id)) place(saved, false);
      changed();
      return saved;
    } catch (e) {
      warn("기록을 고치지 못했다", e);
      return null;
    }
  }

  async function remove(id: string): Promise<void> {
    drop(id);
    try {
      await store().remove(id);
      changed();
    } catch (e) {
      warn("기록을 지우지 못했다", e);
    }
  }

  async function clear(kind: HistoryKind): Promise<void> {
    entries.value = entries.value.filter((e) => e.kind !== kind);
    try {
      await store().clear(kind);
      changed();
    } catch (e) {
      warn("기록을 지우지 못했다", e);
    }
  }

  async function get(id: string): Promise<HistoryEntry | null> {
    try {
      return await store().get(id);
    } catch (e) {
      warn("기록을 읽지 못했다", e);
      return null;
    }
  }

  async function upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null> {
    const known = entries.value.find((e) => e.id === jobId);
    if (known) return known;
    const found = await get(jobId);
    if (found) {
      place(found, false);
      return found;
    }
    const iso = new Date(now()).toISOString();
    const entry: ResearchEntry = {
      id: jobId,
      kind: "research",
      title: question.trim().slice(0, 500),
      createdAt: iso,
      updatedAt: iso,
      params: {},
      refId: jobId,
    };
    try {
      const saved = await store().put(entry);
      place(saved, true);
      changed();
      return saved;
    } catch (e) {
      // 다른 브라우저가 만든 잡이면 서버가 404 로 막는다 — 보고서는 열리고 사이드바에만 없다
      warn("딥리서치 기록을 만들지 못했다", e);
      return null;
    }
  }

  return { entries, byKind, refresh, add, patch, remove, clear, get, upsertResearch };
}
