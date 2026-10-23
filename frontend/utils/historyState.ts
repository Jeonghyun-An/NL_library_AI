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

/** 주소(?h=)로 복원하는 화면이 토스트 이유(없는 기록·연결 문제)를 고르는 읽기 결과 */
export interface HistoryLookup {
  entry: HistoryEntry | null;
  failed: boolean;
}

export interface HistoryState {
  entries: Ref<HistoryEntry[]>;
  /** 전체(종류를 안 준) refresh 가 한 번이라도 끝났는가 — 첫 로드 전의 빈 목록과 진짜 빈 목록을 가른다 */
  loaded: Ref<boolean>;
  /** 마지막으로 읽으려던 종류 중 목록을 못 읽은 것이 있는가(failedKinds 가 비지 않았는가) */
  listFailed: Ref<boolean>;
  /**
   * 마지막으로 읽을 때 목록을 못 읽은 종류(KINDS 순서). 서버가 거절했거나(4xx 등 저장소가 던짐), 서버에 닿지 못했는데 이 브라우저의
   * 사본이 통째로 비어(새 브라우저·메모리 전용) 기록이 없는 것인지 알 수 없는 경우다 — 사이드바가 묶음마다 '기록 없음' 대신 실패를 보인다.
   * 이 수명에 서버에서 한 번 읽은 종류는 사본이 비어도 실패로 보지 않는다(이 탭이 지워 비운 것일 수 있다)
   */
  failedKinds: Ref<HistoryKind[]>;
  byKind(kind: HistoryKind): ComputedRef<HistoryEntry[]>;
  refresh(kind?: HistoryKind): Promise<void>;
  add(input: HistoryEntryInput): Promise<HistoryEntry>;
  patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null>;
  remove(id: string): Promise<void>;
  clear(kind: HistoryKind): Promise<void>;
  /** 읽지 못하면(저장소가 던지면) 없는 기록처럼 null — 못 읽은 것과 없는 것을 갈라야 하면 lookup 을 쓴다 */
  get(id: string): Promise<HistoryEntry | null>;
  /**
   * get 과 같이 읽되 failed 로 못 읽은 것을 알린다 — 서버에 닿지 못했고 사본에도 없음(HistoryUnavailableError)·서버의 거절 등
   * 저장소가 던진 모든 경우다. failed 가 false 인데 entry 가 null 이면 서버가 그 기록이 없다고 답한 것이다
   */
  lookup(id: string): Promise<HistoryLookup>;
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
  /** 연구 화면이 아는 지금 상태를 사이드바 목록의 그 연구 줄에 바로 싣는다(서버에는 보내지 않는다 — 서버가 이미 안다) */
  setResearchStatus(jobId: string, next: { status: string; stage: string }): void;
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
  const loaded = ref(false);
  const listFailed = ref(false);
  const failedKinds = ref<HistoryKind[]>([]);
  const failed = new Set<HistoryKind>();
  // 이 수명 동안 서버 목록을 한 번이라도 받은 종류 — 그 뒤의 빈 사본은 '못 읽음'이 아니라 이 탭·다른 탭이 지운 결과다
  const fromServer = new Set<HistoryKind>();
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
          const { items, fromCache, cacheEmpty } = await store().list(k, { limit: HISTORY_PAGE_SIZE });
          if (!fromCache) fromServer.add(k);
          // 서버에 닿지 못했고 사본도 통째로 비었다 — '아직 기록이 없어요'로 보이면 기록이 사라진 것처럼 읽힌다
          if (fromCache && cacheEmpty && !fromServer.has(k)) failed.add(k);
          else failed.delete(k);
          if ((clearedAt.get(k) ?? 0) > since) return;
          const kept = items.filter((e) => (removedAt.get(e.id) ?? 0) <= since);
          entries.value = [...entries.value.filter((e) => e.kind !== k), ...kept.map(toListItem)];
        } catch (e) {
          failed.add(k);
          warn("목록을 읽지 못했다", e);
        } finally {
          listing -= 1;
          forgetDeletes();
        }
      }),
    );
    failedKinds.value = KINDS.filter((k) => failed.has(k));
    listFailed.value = failedKinds.value.length > 0;
    // 한 종류만 읽는 refresh(폴링·페이지의 부분 갱신)는 첫 로드가 끝났다는 뜻이 아니다. 실패해도 시도는 끝났다
    if (!kind) loaded.value = true;
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

  async function lookup(id: string): Promise<HistoryLookup> {
    try {
      return { entry: await store().get(id), failed: false };
    } catch (e) {
      warn("기록을 읽지 못했다", e);
      return { entry: null, failed: true };
    }
  }

  // upsertResearch 처럼 못 읽었으면 새로 만들면 되는 곳은 둘을 가를 일이 없다
  async function get(id: string): Promise<HistoryEntry | null> {
    return (await lookup(id)).entry;
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

  // 사이드바는 진행 중인 연구가 있을 때만 몇 초마다 다시 읽는다 — 그 사이 연구 화면이 이미 받은 단계(승인·대기열·작성 시작)를 바로
  // 실어 본문과 사이드바가 어긋나지 않게 한다(2026-10-14 운영 확인 — 승인 직후에도 '계획 중', 보고서 작성 중인데 '탐색 중').
  // 목록에 없는 잡(다른 브라우저의 연구 등)이면 아무것도 하지 않는다. 다음 목록 읽기가 서버 값으로 다시 덮는다
  function setResearchStatus(jobId: string, next: { status: string; stage: string }): void {
    const idx = entries.value.findIndex((e) => e.kind === "research" && (e.id === jobId || e.refId === jobId));
    if (idx < 0) return;
    const cur = entries.value[idx] as ResearchEntry;
    if (cur.research?.status === next.status && cur.research?.stage === next.stage) return;
    const updated: ResearchEntry = { ...cur, research: { ...cur.research, status: next.status, stage: next.stage } };
    entries.value = entries.value.map((e, i) => (i === idx ? updated : e));
  }

  return {
    entries,
    loaded,
    listFailed,
    failedKinds,
    byKind,
    refresh,
    add,
    patch,
    remove,
    clear,
    get,
    lookup,
    upsertResearch,
    setResearchStatus,
  };
}
