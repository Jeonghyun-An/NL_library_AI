// frontend/utils/historyState.ts
import { computed, ref, type ComputedRef, type Ref } from "vue";
import type {
  HistoryEntry,
  HistoryEntryInput,
  HistoryKind,
  HistoryPatch,
  ResearchEntry,
} from "~/types/history";
import { HISTORY_PAGE_SIZE, findRecentDuplicate, type HybridHistoryStore } from "./historyStore";

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

  // 목록·저장 응답은 요청이 출발한 때의 서버 상태다. 그 사이 이 탭에서 지운 기록을 늦게 도착한 응답이 되살리지 않도록
  // 지운 순번을 남기고, 그보다 먼저 출발한 응답에서는 그 기록을(비운 종류면 응답 전체를) 버린다
  let deleteSeq = 0;
  const removedAt = new Map<string, number>();
  const clearedAt = new Map<HistoryKind, number>();
  let listing = 0;
  let saving = 0;

  /** 순번 since 뒤에(=요청이 출발한 뒤에) 이 탭에서 그 기록을 지웠거나 그 종류를 비웠는가 */
  function deletedSince(entry: Pick<HistoryEntry, "id" | "kind">, since: number): boolean {
    return (removedAt.get(entry.id) ?? 0) > since || (clearedAt.get(entry.kind) ?? 0) > since;
  }

  // 기다리는 목록·저장 응답이 없으면 이후의 응답은 모두 지금 뒤에 출발한다 — 남긴 순번은 더 쓸 일이 없다
  function forgetDeletes(): void {
    if (listing || saving) return;
    removedAt.clear();
    clearedAt.clear();
  }

  async function refresh(kind?: HistoryKind): Promise<void> {
    const kinds = kind ? [kind] : KINDS;
    await Promise.all(
      kinds.map(async (k) => {
        const since = deleteSeq;
        listing += 1;
        try {
          const { items } = await store().list(k, { limit: HISTORY_PAGE_SIZE });
          if ((clearedAt.get(k) ?? 0) > since) return;
          const kept = items.filter((e) => (removedAt.get(e.id) ?? 0) <= since);
          entries.value = [...entries.value.filter((e) => e.kind !== k), ...kept.map(toListItem)];
        } catch (e) {
          warn("목록을 읽지 못했다", e);
        } finally {
          listing -= 1;
          forgetDeletes();
        }
      }),
    );
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
    const since = deleteSeq;
    saving += 1;
    try {
      // 축약 결과가 너무 커서 난 413 은 저장소가 결과 없이 다시 보내 처리한다 — 여기로 오는 거절은 기록 자체를 받지 않은 것이다
      const saved = await store().put(entry);
      // 저장하는 사이 낙관적으로 올린 기록을 지웠거나 그 종류를 비웠다 — 뒤따른 삭제가 서버에서도 지우니 다시 올리지 않는다
      if (!deletedSince(entry, since)) place(saved, true);
      changed();
      return saved;
    } catch (e) {
      warn("기록을 저장하지 못했다", e);
      if (!dup) drop(entry.id);
      return entry;
    } finally {
      saving -= 1;
      forgetDeletes();
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
    removedAt.set(id, ++deleteSeq);
    drop(id);
    try {
      await store().remove(id);
      changed();
    } catch (e) {
      warn("기록을 지우지 못했다", e);
    }
  }

  async function clear(kind: HistoryKind): Promise<void> {
    clearedAt.set(kind, ++deleteSeq);
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
    // 조회·저장 응답 모두 요청이 출발한 때의 상태다 — 그 사이 지웠거나 비웠으면 목록에 올리지 않는다(add 와 같다)
    const since = deleteSeq;
    saving += 1;
    try {
      const found = await get(jobId);
      if (found) {
        if (!deletedSince(found, since)) place(found, false);
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
        if (!deletedSince(entry, since)) place(saved, true);
        changed();
        return saved;
      } catch (e) {
        // 다른 브라우저가 만든 잡이면 서버가 404 로 막는다 — 보고서는 열리고 사이드바에만 없다
        warn("딥리서치 기록을 만들지 못했다", e);
        return null;
      }
    } finally {
      saving -= 1;
      forgetDeletes();
    }
  }

  return { entries, byKind, refresh, add, patch, remove, clear, get, upsertResearch };
}
