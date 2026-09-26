import type {
  BookAi,
  BookSnapshot,
  DistributiveOmit,
  HistoryEntry,
  HistoryImportItem,
  HistoryImportOut,
  HistoryItemDetail,
  HistoryItemIn,
  HistoryItemOut,
  HistoryKind,
  HistoryListOut,
  HistoryPatch,
  PaperAi,
  PaperSnapshot,
} from "~/types/history";

export const HISTORY_CACHE_KEY = "skx_history_v2";
export const HISTORY_OUTBOX_KEY = "skx_history_outbox";
export const HISTORY_PING_KEY = "skx_history_ping";
export const HISTORY_PAGE_SIZE = 30;

const CACHE_LIMIT_PER_KIND = 100;
const OUTBOX_LIMIT = 200;
const REQUEST_TIMEOUT_MS = 10_000;

export interface ListOptions {
  limit?: number;
  before?: string;
}

export interface ListResult {
  items: HistoryEntry[];
  nextCursor: string | null;
}

export interface HistoryStore {
  list(kind?: HistoryKind, opts?: ListOptions): Promise<ListResult>;
  get(id: string): Promise<HistoryEntry | null>;
  put(entry: HistoryEntry): Promise<HistoryEntry>;
  patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null>;
  remove(id: string): Promise<void>;
  clear(kind: HistoryKind): Promise<void>;
}

export interface ServerHistoryStore extends HistoryStore {
  importItems(items: HistoryImportItem[]): Promise<HistoryImportOut>;
}

export type OutboxOp =
  | { opId: string; op: "put"; entry: HistoryEntry }
  | { opId: string; op: "patch"; id: string; partial: HistoryPatch }
  | { opId: string; op: "remove"; id: string }
  | { opId: string; op: "clear"; kind: HistoryKind };

export type OutboxOpInput = DistributiveOmit<OutboxOp, "opId">;

export interface LocalHistoryStore extends HistoryStore {
  replaceKind(kind: HistoryKind | undefined, items: HistoryEntry[]): void;
  readOutbox(): OutboxOp[];
  enqueue(op: OutboxOpInput): void;
  dropOutbox(opId: string): void;
}

export interface HybridHistoryStore extends HistoryStore {
  flush(): Promise<void>;
}

export interface HistoryFetchOptions {
  method?: "GET" | "PUT" | "PATCH" | "DELETE" | "POST";
  query?: Record<string, string | number | undefined>;
  body?: Record<string, unknown>;
  timeout?: number;
}

export type HistoryFetcher = <T>(path: string, opts?: HistoryFetchOptions) => Promise<T>;

export function errorStatus(e: unknown): number | null {
  if (typeof e !== "object" || e === null) return null;
  const err = e as { status?: unknown; statusCode?: unknown; response?: { status?: unknown } };
  const status = err.status ?? err.statusCode ?? err.response?.status;
  return typeof status === "number" ? status : null;
}

/** 네트워크 단절·시간 초과·서버 오류만 다시 보낼 가치가 있다 — 4xx 는 다시 보내도 같은 답이다 */
export function isRetryable(e: unknown): boolean {
  const status = errorStatus(e);
  return status === null || status === 408 || status === 429 || status >= 500;
}

export function isQuotaError(e: unknown): boolean {
  if (typeof DOMException === "undefined" || !(e instanceof DOMException)) return false;
  return e.name === "QuotaExceededError" || e.name === "NS_ERROR_DOM_QUOTA_REACHED" || e.code === 22 || e.code === 1014;
}

export function fromWire(item: HistoryItemOut | HistoryItemDetail): HistoryEntry {
  const base = {
    id: item.id,
    title: item.title,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    params: item.params ?? {},
  };
  if (item.kind === "research") {
    return {
      ...base,
      kind: "research",
      refId: item.ref_id ?? item.id,
      ...(item.research ? { research: item.research } : {}),
    };
  }
  const { snapshot, ai } = item as Partial<HistoryItemDetail>;
  if (item.kind === "book") {
    return {
      ...base,
      kind: "book",
      ...(snapshot ? { snapshot: snapshot as BookSnapshot } : {}),
      ...(ai ? { ai: ai as BookAi } : {}),
    };
  }
  return {
    ...base,
    kind: "paper",
    ...(snapshot ? { snapshot: snapshot as PaperSnapshot } : {}),
    ...(ai ? { ai: ai as PaperAi } : {}),
  };
}

export function toWire(entry: HistoryEntry): HistoryItemIn {
  const research = entry.kind === "research";
  return {
    kind: entry.kind,
    title: entry.title.slice(0, 500),
    params: entry.params ?? {},
    snapshot: research ? null : (entry.snapshot ?? null),
    ai: research ? null : (entry.ai ?? null),
    ref_id: research ? entry.refId : null,
  };
}

function patchBody(partial: HistoryPatch): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(partial)) if (value !== undefined) body[key] = value;
  return body;
}

export function createServerStore(fetcher: HistoryFetcher): ServerHistoryStore {
  const at = (id: string) => `/history/${encodeURIComponent(id)}`;
  const timeout = REQUEST_TIMEOUT_MS;
  return {
    async list(kind, opts) {
      const res = await fetcher<HistoryListOut>("/history", {
        method: "GET",
        query: { kind, limit: opts?.limit ?? HISTORY_PAGE_SIZE, before: opts?.before },
        timeout,
      });
      return { items: res.items.map(fromWire), nextCursor: res.next_cursor };
    },
    async get(id) {
      try {
        return fromWire(await fetcher<HistoryItemDetail>(at(id), { method: "GET", timeout }));
      } catch (e) {
        if (errorStatus(e) === 404) return null;
        throw e;
      }
    },
    async put(entry) {
      return fromWire(
        await fetcher<HistoryItemDetail>(at(entry.id), { method: "PUT", body: { ...toWire(entry) }, timeout }),
      );
    },
    async patch(id, partial) {
      try {
        return fromWire(await fetcher<HistoryItemDetail>(at(id), { method: "PATCH", body: patchBody(partial), timeout }));
      } catch (e) {
        if (errorStatus(e) === 404) return null;
        throw e;
      }
    },
    async remove(id) {
      try {
        await fetcher<void>(at(id), { method: "DELETE", timeout });
      } catch (e) {
        if (errorStatus(e) !== 404) throw e;
      }
    },
    async clear(kind) {
      await fetcher<void>("/history", { method: "DELETE", query: { kind }, timeout });
    },
    async importItems(items) {
      return fetcher<HistoryImportOut>("/history/import", { method: "POST", body: { items }, timeout });
    },
  };
}

function timeOf(e: HistoryEntry): number {
  const t = Date.parse(e.createdAt);
  return Number.isNaN(t) ? 0 : t;
}

function newestFirst(a: HistoryEntry, b: HistoryEntry): number {
  return timeOf(b) - timeOf(a);
}

function cursorOf(e: HistoryEntry): string {
  return `${e.createdAt}|${e.id}`;
}

function withoutField(entry: HistoryEntry, field: "snapshot" | "ai"): HistoryEntry {
  if (entry.kind === "research") return entry;
  const copy = { ...entry };
  delete copy[field];
  return copy;
}

function capPerKind(list: HistoryEntry[]): HistoryEntry[] {
  const count: Partial<Record<HistoryKind, number>> = {};
  return [...list].sort(newestFirst).filter((e) => {
    count[e.kind] = (count[e.kind] ?? 0) + 1;
    return count[e.kind]! <= CACHE_LIMIT_PER_KIND;
  });
}

function newOpId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function createLocalStore(storage: Storage | null): LocalHistoryStore {
  // 저장소가 막히면(사생활 모드·쿼터 한계) 이 수명 동안은 메모리만 쓴다
  let memoryOnly = storage === null;
  let cacheMem: HistoryEntry[] = [];
  let outboxMem: OutboxOp[] = [];

  function read<T>(key: string, mem: T[]): T[] {
    if (memoryOnly || !storage) return mem;
    let raw: string | null;
    try {
      raw = storage.getItem(key);
    } catch {
      memoryOnly = true;
      return mem;
    }
    if (raw === null) return [];
    try {
      const parsed: unknown = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as T[]) : [];
    } catch {
      return [];
    }
  }

  function write<T>(key: string, list: T[], shed: (current: T[]) => T[] | null): T[] {
    if (memoryOnly || !storage) return list;
    let attempt = list;
    for (;;) {
      try {
        storage.setItem(key, JSON.stringify(attempt));
        return attempt;
      } catch (e) {
        const lighter = isQuotaError(e) ? shed(attempt) : null;
        if (!lighter) {
          memoryOnly = true;
          return attempt;
        }
        attempt = lighter;
      }
    }
  }

  function shedCache(list: HistoryEntry[]): HistoryEntry[] | null {
    const oldest = [...list].sort((a, b) => timeOf(a) - timeOf(b));
    for (const field of ["snapshot", "ai"] as const) {
      const victim = oldest.find((e) => e.kind !== "research" && e[field] !== undefined);
      if (victim) return list.map((e) => (e === victim ? withoutField(e, field) : e));
    }
    return null;
  }

  function shedOutbox(ops: OutboxOp[]): OutboxOp[] | null {
    const victim = ops.find((o) => o.op === "put" && o.entry.kind !== "research" && o.entry.snapshot !== undefined);
    if (!victim || victim.op !== "put") return null;
    return ops.map((o) => (o === victim ? { ...victim, entry: withoutField(victim.entry, "snapshot") } : o));
  }

  // 저장된 캐시를 한 칸 덜어 고쳐 쓴다. 덜 것이 없거나 쓰지 못하면 false
  function shedStoredCache(): boolean {
    if (!storage) return false;
    let lighter = shedCache(readCache());
    while (lighter) {
      try {
        storage.setItem(HISTORY_CACHE_KEY, JSON.stringify(lighter));
        cacheMem = lighter;
        return true;
      } catch (e) {
        if (!isQuotaError(e)) return false;
        lighter = shedCache(lighter);
      }
    }
    return false;
  }

  // 쿼터 대부분은 캐시가 쓰고, 쿼터에 닿은 캐시는 겨우 들어갈 만큼만 덜어 늘 한계 바로 아래에 있다.
  // 편지는 아직 서버에 없는 사용자 변경이고 캐시는 서버 값·편지의 사본이라, 편지함이 막히면 캐시부터 던다 —
  // 여기서 메모리로 넘어가면 새로고침 한 번에 편지가 사라진다
  function shedForOutbox(ops: OutboxOp[]): OutboxOp[] | null {
    return shedStoredCache() ? ops : shedOutbox(ops);
  }

  const readCache = () => read(HISTORY_CACHE_KEY, cacheMem);
  const writeCache = (list: HistoryEntry[]) => {
    cacheMem = write(HISTORY_CACHE_KEY, capPerKind(list), shedCache);
  };
  const readOutboxList = () => read(HISTORY_OUTBOX_KEY, outboxMem);
  const writeOutbox = (ops: OutboxOp[]) => {
    outboxMem = write(HISTORY_OUTBOX_KEY, ops.slice(-OUTBOX_LIMIT), shedForOutbox);
  };

  return {
    async list(kind, opts) {
      const all = readCache()
        .filter((e) => !kind || e.kind === kind)
        .sort(newestFirst);
      const limit = opts?.limit ?? HISTORY_PAGE_SIZE;
      let start = 0;
      if (opts?.before) {
        const idx = all.findIndex((e) => cursorOf(e) === opts.before);
        start = idx < 0 ? all.length : idx + 1;
      }
      const items = all.slice(start, start + limit);
      const last = items[items.length - 1];
      return { items, nextCursor: last && start + limit < all.length ? cursorOf(last) : null };
    },
    async get(id) {
      return readCache().find((e) => e.id === id) ?? null;
    },
    async put(entry) {
      writeCache([entry, ...readCache().filter((e) => e.id !== entry.id)]);
      return entry;
    },
    async patch(id, partial) {
      const list = readCache();
      const found = list.find((e) => e.id === id);
      if (!found) return null;
      const merged = { ...found, ...patchBody(partial), updatedAt: new Date().toISOString() } as HistoryEntry;
      writeCache(list.map((e) => (e.id === id ? merged : e)));
      return merged;
    },
    async remove(id) {
      writeCache(readCache().filter((e) => e.id !== id));
    },
    async clear(kind) {
      writeCache(readCache().filter((e) => e.kind !== kind));
    },
    replaceKind(kind, items) {
      const current = readCache();
      const cached = new Map(current.map((e) => [e.id, e]));
      const merged = items.map((item) => {
        const prev = cached.get(item.id);
        if (!prev || prev.kind === "research" || item.kind === "research") return item;
        // 서버 목록에는 snapshot·ai 가 없다 — 오프라인 복원용으로 캐시에 있던 것을 붙여 둔다
        return {
          ...item,
          ...(prev.snapshot ? { snapshot: prev.snapshot } : {}),
          ...(prev.ai ? { ai: prev.ai } : {}),
        } as HistoryEntry;
      });
      const keep = kind ? current.filter((e) => e.kind !== kind) : [];
      writeCache([...merged, ...keep]);
    },
    readOutbox() {
      return readOutboxList();
    },
    enqueue(op) {
      writeOutbox([...readOutboxList(), { ...op, opId: newOpId() } as OutboxOp]);
    },
    dropOutbox(opId) {
      writeOutbox(readOutboxList().filter((o) => o.opId !== opId));
    },
  };
}

type Sent<T> = { ok: true; value: T } | { ok: false };

const noop = () => {};

export function createHybridStore(server: HistoryStore, local: LocalHistoryStore): HybridHistoryStore {
  let flushing: Promise<void> | null = null;

  // 이 탭의 동작을 부른 순서대로 끝낸다. 편지함만 보고 순서를 맞추면 아직 응답을 기다리는 직접 요청을 앞질러,
  // 저장이 끝나기 전에 누른 삭제가 서버에 먼저 닿고(404 → 성공) 늦게 끝난 저장이 기록을 되살린다.
  // 변경은 앞의 모든 동작이 끝난 뒤 혼자 돌고, 읽기는 앞의 변경만 기다리며 읽기끼리는 나란히 돈다
  let writesDone: Promise<void> = Promise.resolve();
  let allDone: Promise<void> = Promise.resolve();

  function exclusive<T>(fn: () => Promise<T>): Promise<T> {
    const run = allDone.then(fn);
    writesDone = allDone = run.then(noop, noop);
    return run;
  }

  function shared<T>(fn: () => Promise<T>): Promise<T> {
    const run = writesDone.then(fn);
    allDone = Promise.all([allDone, run.then(noop, noop)]).then(noop);
    return run;
  }

  // 축약 결과가 서버 상한(200KB)을 넘으면 413 이다. 4xx 라 편지함도 다시 보내지 않으니 그대로 두면
  // 기록이 통째로 사라진다 — 결과 없이라도 남긴다(복원은 q 재검색으로 물러선다). 바로 보낼 때와 편지함이 같이 쓴다
  async function putToServer(entry: HistoryEntry): Promise<HistoryEntry> {
    try {
      return await server.put(entry);
    } catch (e) {
      if (errorStatus(e) !== 413 || entry.kind === "research" || !entry.snapshot) throw e;
      return server.put(withoutField(entry, "snapshot"));
    }
  }

  // 편지를 보낼 때는 캐시를 건드리지 않는다 — 캐시는 줄 세울 때 이미 뒤따른 수정·삭제까지 반영하고 있어서,
  // 서버 응답으로 덮으면 그 뒤 편지가 아직 못 간 동안 사용자의 최근 변경이 사라진다. 정합은 다음 list·get 이 맞춘다
  async function apply(op: OutboxOp): Promise<void> {
    switch (op.op) {
      case "put":
        await putToServer(op.entry);
        return;
      case "patch":
        await server.patch(op.id, op.partial);
        return;
      case "remove":
        await server.remove(op.id);
        return;
      case "clear":
        await server.clear(op.kind);
        return;
    }
  }

  async function drain(): Promise<void> {
    for (const op of local.readOutbox()) {
      try {
        await apply(op);
      } catch (e) {
        if (isRetryable(e)) return;
        // 4xx 는 다시 보내도 같은 거절이다 — 이 편지는 버리고 다음으로 넘어간다
      }
      local.dropOutbox(op.opId);
    }
  }

  function flush(): Promise<void> {
    if (!flushing) {
      flushing = drain().finally(() => {
        flushing = null;
      });
    }
    return flushing;
  }

  // 편지가 남아 있으면 서버로 바로 보내지 않는다 — 순서가 뒤집히면 아직 서버에 없는 기록에 수정이 먼저 닿는다
  async function direct<T>(send: () => Promise<T>): Promise<Sent<T>> {
    await flush();
    if (local.readOutbox().length) return { ok: false };
    try {
      return { ok: true, value: await send() };
    } catch (e) {
      if (!isRetryable(e)) throw e;
      return { ok: false };
    }
  }

  return {
    flush: () => exclusive(flush),
    list: (kind, opts) =>
      shared(async () => {
        const res = await direct(() => server.list(kind, opts));
        if (!res.ok) return local.list(kind, opts);
        if (!opts?.before) local.replaceKind(kind, res.value.items);
        return res.value;
      }),
    get: (id) =>
      shared(async () => {
        const res = await direct(() => server.get(id));
        if (!res.ok) return local.get(id);
        if (res.value) {
          await local.put(res.value);
          return res.value;
        }
        await local.remove(id);
        return null;
      }),
    put: (entry) =>
      exclusive(async () => {
        const res = await direct(() => putToServer(entry));
        if (res.ok) {
          await local.put(res.value);
          return res.value;
        }
        await local.put(entry);
        local.enqueue({ op: "put", entry });
        return entry;
      }),
    patch: (id, partial) =>
      exclusive(async () => {
        const res = await direct(() => server.patch(id, partial));
        if (res.ok) {
          if (res.value) await local.put(res.value);
          else await local.remove(id);
          return res.value;
        }
        const merged = await local.patch(id, partial);
        local.enqueue({ op: "patch", id, partial });
        return merged;
      }),
    remove: (id) =>
      exclusive(async () => {
        await local.remove(id);
        const res = await direct(() => server.remove(id));
        if (!res.ok) local.enqueue({ op: "remove", id });
      }),
    clear: (kind) =>
      exclusive(async () => {
        await local.clear(kind);
        const res = await direct(() => server.clear(kind));
        if (!res.ok) local.enqueue({ op: "clear", kind });
      }),
  };
}
