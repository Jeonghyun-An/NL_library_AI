import { vi } from "vitest";
import type {
  BookEntry,
  HistoryEntry,
  HistoryKind,
  HistoryPatch,
  PaperEntry,
  ResearchEntry,
} from "~/types/history";
import type { HybridHistoryStore } from "~/utils/historyStore";

export const ID1 = "11111111-1111-4111-8111-111111111111";
export const ID2 = "22222222-2222-4222-8222-222222222222";
export const ID3 = "33333333-3333-4333-8333-333333333333";
export const T0 = "2026-09-26T01:00:00.000Z";

export function bookEntry(id: string, over: Partial<BookEntry> = {}): BookEntry {
  return { id, kind: "book", title: "한국 경제", createdAt: T0, params: {}, ...over };
}

export function paperEntry(id: string, over: Partial<PaperEntry> = {}): PaperEntry {
  return { id, kind: "paper", title: "딥러닝 자연어 처리", createdAt: T0, params: {}, ...over };
}

export function researchEntry(id: string, over: Partial<ResearchEntry> = {}): ResearchEntry {
  return { id, kind: "research", title: "국내 AI 규제 연구 동향", createdAt: T0, params: {}, refId: id, ...over };
}

export function httpError(status: number): Error & { status: number } {
  return Object.assign(new Error(`HTTP ${status}`), { status });
}

export function networkError(): TypeError {
  return new TypeError("fetch failed");
}

/** 서버를 흉내 내는 메모리 저장소. fail() 로 이후 모든 호출을 실패시킨다 */
export function fakeServer() {
  const rows = new Map<string, HistoryEntry>();
  let failure: unknown = null;
  const guard = () => {
    if (failure) throw failure;
  };
  const store = {
    rows,
    fail(e: unknown) {
      failure = e;
    },
    recover() {
      failure = null;
    },
    flush: vi.fn(async () => {}),
    list: vi.fn(async (kind?: HistoryKind) => {
      guard();
      return { items: [...rows.values()].filter((e) => !kind || e.kind === kind), nextCursor: null };
    }),
    get: vi.fn(async (id: string) => {
      guard();
      return rows.get(id) ?? null;
    }),
    put: vi.fn(async (entry: HistoryEntry) => {
      guard();
      rows.set(entry.id, entry);
      return entry;
    }),
    patch: vi.fn(async (id: string, partial: HistoryPatch) => {
      guard();
      const found = rows.get(id);
      if (!found) return null;
      const merged = { ...found, ...partial } as HistoryEntry;
      rows.set(id, merged);
      return merged;
    }),
    remove: vi.fn(async (id: string) => {
      guard();
      rows.delete(id);
    }),
    clear: vi.fn(async (kind: HistoryKind) => {
      guard();
      for (const [id, e] of rows) if (e.kind === kind) rows.delete(id);
    }),
  };
  return store satisfies HybridHistoryStore;
}
