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
  LegacyHistoryEntry,
  PaperAi,
  PaperSnapshot,
} from "~/types/history";
import { slimBookResult, slimPaperResult } from "./historySnapshot";

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
  // 메모리로 넘어갈 때 저장소에 있던 편지 — 살아 있는 다른 탭도 같은 편지를 보고 보낸다
  const adopted = new Set<string>();

  // 읽지 못하면 undefined — 키가 없거나 깨진 값은 빈 목록이다
  function load<T>(key: string): T[] | undefined {
    if (!storage) return undefined;
    let raw: string | null;
    try {
      raw = storage.getItem(key);
    } catch {
      return undefined;
    }
    if (raw === null) return [];
    try {
      const parsed: unknown = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as T[]) : [];
    } catch {
      return [];
    }
  }

  // 메모리 사본은 이 인스턴스가 마지막으로 쓴 값뿐이라, 새로고침 뒤처럼 편지함을 쓴 적 없는 인스턴스가 그대로 넘어가면
  // 저장소에 남은 편지가 이번 수명 동안 안 보이고 새 변경이 그 편지를 앞질러 서버로 간다 — 넘어가기 전에 두 키를 읽어 둔다
  function goMemory(): void {
    if (memoryOnly) return;
    cacheMem = load<HistoryEntry>(HISTORY_CACHE_KEY) ?? cacheMem;
    outboxMem = load<OutboxOp>(HISTORY_OUTBOX_KEY) ?? outboxMem;
    // 읽지 못해 마지막으로 쓴 값을 그대로 둘 때도 그 편지는 모두 저장소에 쓴 것이다
    for (const o of outboxMem) adopted.add(o.opId);
    memoryOnly = true;
  }

  // 가져온 편지를 다른 탭이 먼저 보내 저장소에서 뺀 뒤 이 탭이 메모리 사본대로 또 보내면, 그 사이 지운 기록을
  // upsert 가 되살린다 — 저장소를 읽을 수 있으면 거기서 사라진 편지는 보내지 않고 뺀다. 메모리 모드에서 줄 세운 편지는
  // 저장소에 없어 대상이 아니고, 새로고침 전의 편지는 보낼 때까지 저장소에 남아 있어 그대로 나간다
  function outboxInMemory(): OutboxOp[] {
    if (!adopted.size) return outboxMem;
    const stored = load<OutboxOp>(HISTORY_OUTBOX_KEY);
    if (!stored) return outboxMem;
    const pending = new Set(stored.map((o) => o.opId));
    const gone = [...adopted].filter((opId) => !pending.has(opId));
    if (!gone.length) return outboxMem;
    for (const opId of gone) adopted.delete(opId);
    outboxMem = outboxMem.filter((o) => !gone.includes(o.opId));
    return outboxMem;
  }

  function read<T>(key: string, mem: () => T[]): T[] {
    if (!memoryOnly && storage) {
      const stored = load<T>(key);
      if (stored) return stored;
      goMemory();
    }
    return mem();
  }

  // 메모리로 넘어가면 호출부가 이번 쓰기 결과(돌려준 목록)로 그 키의 사본을 덮는다
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
          goMemory();
          return attempt;
        }
        attempt = lighter;
      }
    }
  }

  // 메모리 모드에서 보낸 편지는 메모리에서만 빠진다. 저장소 사본에 남으면 다음 새로고침에 한 번 더 나가,
  // 그 사이 지운 기록을 upsert 가 되살리고 고친 값을 옛 값으로 덮는다 — 저장소에서도 그 편지만 뺀다.
  // 줄어드는 쓰기라 쿼터에는 걸리지 않고, 그래도 막히면 저장소 자체가 막힌 것이라 할 수 있는 일이 없다
  function forgetStored(opId: string): void {
    const stored = load<OutboxOp>(HISTORY_OUTBOX_KEY);
    if (!storage || !stored?.some((o) => o.opId === opId)) return;
    try {
      storage.setItem(HISTORY_OUTBOX_KEY, JSON.stringify(stored.filter((o) => o.opId !== opId)));
    } catch {
      // 위 이유로 무시한다
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

  const readCache = () => read(HISTORY_CACHE_KEY, () => cacheMem);
  const writeCache = (list: HistoryEntry[]) => {
    cacheMem = write(HISTORY_CACHE_KEY, capPerKind(list), shedCache);
  };
  const readOutboxList = () => read(HISTORY_OUTBOX_KEY, outboxInMemory);
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
      // 메모리 모드에서 저장소에 남아 있을 수 있는 편지는 넘어갈 때 가져온 것뿐이다
      if (memoryOnly && adopted.delete(opId)) forgetStored(opId);
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

export const LEGACY_HISTORY_KEY = "skx_search_history";
export const LEGACY_BACKUP_KEY = "skx_search_history_backup_v1";
export const LEGACY_MIGRATED_KEY = "skx_history_v1_migrated";
export const V1_MAP_KEY = "skx_history_v1_map";
export const DEDUPE_WINDOW_MS = 10 * 60 * 1000;

const IMPORT_BATCH = 100;

export function normalizeTitle(title: string): string {
  return title.normalize("NFC").trim().replace(/\s+/g, " ").toLowerCase();
}

function paramsKey(params: Record<string, unknown> | undefined): string {
  const entries = Object.entries(params ?? {})
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return JSON.stringify(entries);
}

export function findRecentDuplicate(
  list: readonly HistoryEntry[],
  input: { kind: HistoryKind; title: string; params?: Record<string, unknown> },
  nowMs: number,
  windowMs = DEDUPE_WINDOW_MS,
): HistoryEntry | null {
  if (input.kind === "research") return null;
  const title = normalizeTitle(input.title);
  const key = paramsKey(input.params);
  return (
    list.find((e) => {
      if (e.kind !== input.kind || normalizeTitle(e.title) !== title || paramsKey(e.params) !== key) return false;
      const at = Date.parse(e.updatedAt ?? e.createdAt);
      return !Number.isNaN(at) && nowMs - at <= windowMs;
    }) ?? null
  );
}

export function readV1Map(storage: Storage | null): Record<string, string> {
  if (!storage) return {};
  try {
    const parsed: unknown = JSON.parse(storage.getItem(V1_MAP_KEY) ?? "{}");
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter((kv): kv is [string, string] => typeof kv[1] === "string"),
    );
  } catch {
    return {};
  }
}

function legacyTime(ts: unknown): string | null {
  if (typeof ts !== "number" && typeof ts !== "string") return null;
  const value = typeof ts === "string" && /^\d+$/.test(ts) ? Number(ts) : ts;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function legacyAi(kind: "book" | "paper", raw: unknown): BookAi | PaperAi | null {
  if (typeof raw !== "string" || !raw.trim()) return null;
  let parsed: unknown = null;
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = null;
  }
  const obj =
    typeof parsed === "object" && parsed !== null && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  if (kind === "book") {
    return obj
      ? { intro: typeof obj.intro === "string" ? obj.intro : "", items: Array.isArray(obj.items) ? obj.items : [] }
      : { intro: raw, items: [] };
  }
  return obj
    ? { text: typeof obj.text === "string" ? obj.text : "", refs: Array.isArray(obj.refs) ? obj.refs : [] }
    : { text: raw, refs: [] };
}

export function convertLegacy(v1: LegacyHistoryEntry[]): HistoryImportItem[] {
  const seen = new Set<string>();
  const out: HistoryImportItem[] = [];
  // 브라우저 저장소에서 온 값이라 타입을 믿지 않고 한 칸씩 확인한다
  for (const raw of v1 as unknown[]) {
    if (typeof raw !== "object" || raw === null) continue;
    const { id, type, query, timestamp, result, aiSummary } = raw as Partial<LegacyHistoryEntry>;
    if ((type !== "book" && type !== "paper") || typeof query !== "string" || !query.trim()) continue;
    const legacyId = String(id ?? "");
    if (!legacyId || seen.has(legacyId)) continue;
    seen.add(legacyId);
    out.push({
      legacy_id: legacyId,
      kind: type,
      title: query.trim().slice(0, 500),
      params: {},
      snapshot: type === "book" ? slimBookResult(result) : slimPaperResult(result),
      ai: legacyAi(type, aiSummary),
      ref_id: null,
      created_at: legacyTime(timestamp) ?? legacyTime(legacyId),
    });
  }
  return out;
}

export async function migrateLegacy(
  storage: Storage | null,
  server: Pick<ServerHistoryStore, "importItems">,
): Promise<{ imported: number } | null> {
  if (!storage) return null;
  let raw: string | null;
  try {
    if (storage.getItem(LEGACY_MIGRATED_KEY)) return null;
    raw = storage.getItem(LEGACY_HISTORY_KEY);
  } catch {
    return null;
  }
  if (raw === null) return null;

  let parsed: unknown = null;
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = null;
  }
  const items = Array.isArray(parsed) ? convertLegacy(parsed as LegacyHistoryEntry[]) : [];

  const idMap = readV1Map(storage);
  let imported = 0;
  try {
    for (let i = 0; i < items.length; i += IMPORT_BATCH) {
      const res = await server.importItems(items.slice(i, i + IMPORT_BATCH));
      imported += res.imported;
      Object.assign(idMap, res.id_map);
    }
  } catch {
    // 서버가 받기 전에는 v1 을 건드리지 않는다 — 다음 로드에서 다시 시도한다
    return null;
  }

  try {
    storage.setItem(V1_MAP_KEY, JSON.stringify(idMap));
  } catch {
    // 대응표를 못 남기면 옛 ?restore= 주소만 새 id 를 못 찾는다 — 기록 자체는 이미 서버에 있다
  }
  // 요청이 오가는 사이 구버전 탭이 v1 을 다시 썼으면 서버가 받지 않은 항목이 섞여 있다 — 그때는 v1 을 남겨 다음 로드에 다시 올린다
  const legacyUnchanged = (): boolean => {
    try {
      return storage.getItem(LEGACY_HISTORY_KEY) === raw;
    } catch {
      return false;
    }
  };
  let backup: string | null;
  try {
    // 같은 v1 을 함께 올린 다른 탭이 먼저 백업하고 지웠다 — 사본을 하나 더 두면 쿼터만 잡아먹는다
    if (storage.getItem(LEGACY_HISTORY_KEY) === null) return { imported };
    backup = storage.getItem(LEGACY_BACKUP_KEY);
  } catch {
    return { imported };
  }
  try {
    // 시각 접미 키는 기존 백업과 내용이 다른 v1 을 보존할 때만 쓴다 — 같은 내용이면 사본 없이 v1 만 치운다
    if (backup !== raw) {
      storage.setItem(backup === null ? LEGACY_BACKUP_KEY : `${LEGACY_BACKUP_KEY}_${Date.now()}`, raw);
    }
    if (legacyUnchanged()) storage.removeItem(LEGACY_HISTORY_KEY);
  } catch {
    if (!legacyUnchanged()) return { imported };
    // 사본 둘 자리가 없다 — 원본을 그대로 백업으로 남기고 다시 올리지 않게 표시만 한다
    try {
      storage.setItem(LEGACY_MIGRATED_KEY, "1");
    } catch {
      // 표시도 못 하면 다음 로드에 한 번 더 올린다 — 서버가 같은 id 를 건너뛴다
    }
  }
  return { imported };
}
