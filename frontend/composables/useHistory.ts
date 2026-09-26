// frontend/composables/useHistory.ts
import type { ComputedRef, Ref } from "vue";
import type { HistoryEntry, HistoryEntryInput, HistoryKind, HistoryPatch } from "~/types/history";
import { generateUuidV4, safeLocalStorage } from "~/utils/browserId";
import { createHistoryState, type HistoryState } from "~/utils/historyState";
import {
  HISTORY_PING_KEY,
  createHybridStore,
  createLocalStore,
  createServerStore,
  migrateLegacy,
  type HistoryFetcher,
  type HybridHistoryStore,
  type ServerHistoryStore,
} from "~/utils/historyStore";
import { useApi } from "./useApi";

// 앱 전체가 한 벌을 나눠 쓴다 — 사이드바와 페이지가 같은 목록을 보고, 창 이벤트도 한 번만 건다
let server: ServerHistoryStore | null = null;
let hybrid: HybridHistoryStore | null = null;
let state: HistoryState | null = null;
let loading: Promise<void> | null = null;
let migrating: Promise<void> | null = null;
let refreshTimer: ReturnType<typeof setTimeout> | null = null;

const noop = () => {};

function stores(): { server: ServerHistoryStore; hybrid: HybridHistoryStore } {
  if (!server || !hybrid) {
    // Nitro 의 경로별 응답 타입 추론이 저장소의 제네릭 응답 타입과 맞물리면 타입검사가 깊이 한도를 넘는다 — 응답 모양은 저장소가 안다
    const fetcher = useApi() as unknown as HistoryFetcher;
    server = createServerStore(fetcher);
    hybrid = createHybridStore(server, createLocalStore(safeLocalStorage()));
  }
  return { server, hybrid };
}

function ping(): void {
  try {
    window.localStorage.setItem(HISTORY_PING_KEY, `${Date.now()}:${Math.random().toString(36).slice(2)}`);
  } catch {
    // 막힌 저장소 — 다른 탭 동기화만 포기한다
  }
}

function historyState(): HistoryState {
  if (!state) {
    state = createHistoryState(() => stores().hybrid, { genId: generateUuidV4, onChange: ping });
  }
  return state;
}

function scheduleRefresh(): void {
  if (refreshTimer) clearTimeout(refreshTimer);
  // 다른 탭이 연달아 고칠 때 목록을 한 번만 다시 읽는다
  refreshTimer = setTimeout(() => {
    refreshTimer = null;
    void historyState().refresh();
  }, 300);
}

// 사이드바의 load() 와 옛 ?restore= 를 복원하는 페이지가 같은 이전을 기다린다. 실패해도 이룬다 — 목록은 읽어야 하고,
// 다음 로드가 다시 올린다
function migrated(): Promise<void> {
  if (!import.meta.client) return Promise.resolve();
  if (!migrating) migrating = migrateLegacy(safeLocalStorage(), stores().server).then(noop, noop);
  return migrating;
}

function load(): Promise<void> {
  if (!import.meta.client) return Promise.resolve();
  if (!loading) {
    loading = (async () => {
      window.addEventListener("storage", (e) => {
        if (e.key === HISTORY_PING_KEY) scheduleRefresh();
      });
      window.addEventListener("online", scheduleRefresh);
      await migrated();
      await historyState().refresh();
    })();
  }
  return loading;
}

export interface UseHistory {
  entries: Ref<HistoryEntry[]>;
  byKind(kind: HistoryKind): ComputedRef<HistoryEntry[]>;
  load(): Promise<void>;
  migrated(): Promise<void>;
  refresh(kind?: HistoryKind): Promise<void>;
  add(input: HistoryEntryInput): Promise<HistoryEntry>;
  patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null>;
  remove(id: string): Promise<void>;
  clear(kind: HistoryKind): Promise<void>;
  get(id: string): Promise<HistoryEntry | null>;
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
}

export function useHistory(): UseHistory {
  const s = historyState();
  return {
    entries: s.entries,
    byKind: s.byKind,
    load,
    migrated,
    refresh: (kind) => (import.meta.client ? s.refresh(kind) : Promise.resolve()),
    add: s.add,
    patch: s.patch,
    remove: s.remove,
    clear: s.clear,
    get: s.get,
    upsertResearch: s.upsertResearch,
  };
}
