// frontend/utils/workEvents.ts
// 연구 어시스턴트 SSE(GET /api/research/{id}/work/stream)의 순수 리듀서. 이벤트는 상태(생성 진행·단계·흐르는 절 글)만
// 싣고 결과(카드·읽기 목록·목차·절)는 싣지 않는다 — 생성이 끝나면 화면이 그 조회를 다시 읽는다(spec §6-4, 06b 정함 10).
// 늘 새 객체를 돌려준다(shallowRef 가 바뀐 것을 안다)
import type {
  GenKind,
  GenStatus,
  LiveSection,
  SectionDeltaEvent,
  WorkEvent,
  WorkGeneration,
  WorkGenerationEvent,
  WorkResource,
  WorkState,
  WorkView,
} from "~/types/work";

interface WorkEventResult {
  state: WorkState;
  reload: WorkResource[];
}

const OPEN_STATUSES: readonly GenStatus[] = ["queued", "running"];

// 생성이 끝나면 다시 읽을 조회. 모든 kind 가 work 도 다시 읽는다 — 진행 요약(progress)과 남은 생성의 순번이 바뀐다
const RELOAD: Record<GenKind, readonly WorkResource[]> = {
  concepts: ["work"],
  topic_card: ["topics", "work"],
  refine: ["topics", "work"],
  facet: ["reading", "work"],
  outline: ["proposal", "work"],
  section: ["proposal", "work"],
  paragraph: ["proposal", "work"],
};

function isOpen(status: GenStatus): boolean {
  return OPEN_STATUSES.includes(status);
}

// queued → running → (done·failed·canceled). 늦게 도착한 앞 상태가 끝난 생성을 되살리지 않게 순서를 본다
function statusRank(status: GenStatus): number {
  return status === "queued" ? 0 : status === "running" ? 1 : 2;
}

// 서버의 offset 은 파이썬 len(코드포인트)이다 — JS 의 length(UTF-16)와 갈리는 글자(이모지 등)가 있다
function charCount(text: string): number {
  return Array.from(text).length;
}

function addAll(into: WorkResource[], kinds: readonly WorkResource[]): void {
  for (const k of kinds) if (!into.includes(k)) into.push(k);
}

function withoutKey(live: Record<string, LiveSection>, key: string): Record<string, LiveSection> {
  const out = { ...live };
  delete out[key];
  return out;
}

export function initialWorkState(): WorkState {
  return { work: null, topics: null, reading: null, proposal: null, live: {} };
}

// 처음 보는 kind(뒤 라운드 서버)는 연구만 다시 읽는다
export function reloadFor(kind: GenKind): WorkResource[] {
  return [...(RELOAD[kind] ?? ["work"])];
}

export function withWork(state: WorkState, work: WorkView): WorkState {
  return { ...state, work };
}

export function withResource<K extends Exclude<WorkResource, "work">>(
  state: WorkState,
  kind: K,
  data: WorkState[K],
): WorkState {
  return { ...state, [kind]: data };
}

function newest(gens: WorkGeneration[]): WorkGeneration | null {
  return gens.reduce<WorkGeneration | null>((best, g) => (!best || g.id > best.id ? g : best), null);
}

// target 을 주지 않으면(undefined) 대상을 가리지 않는다. null 은 대상 없는 생성(핵심 개념)만 고른다
function matching(state: WorkState, kind: GenKind, target: string | null | undefined): WorkGeneration[] {
  return (state.work?.generations ?? []).filter(
    (g) => g.kind === kind && (target === undefined || g.target === target),
  );
}

export function latestGeneration(state: WorkState, kind: GenKind, target?: string | null): WorkGeneration | null {
  return newest(matching(state, kind, target));
}

export function openGeneration(state: WorkState, kind: GenKind, target?: string | null): WorkGeneration | null {
  return newest(matching(state, kind, target).filter((g) => isOpen(g.status)));
}

export function applyWorkEvent(state: WorkState, event: WorkEvent): WorkEventResult {
  switch (event.kind) {
    case "snapshot":
      return applySnapshot(state, event.work);
    case "generation":
      return applyGeneration(state, event);
    case "work":
      if (!state.work) return { state, reload: [] };
      return { state: withWork(state, { ...state.work, phase: event.phase, progress: event.progress }), reload: [] };
    case "section_delta":
      return { state: { ...state, live: applyDelta(state.live, event) }, reload: [] };
    default:
      // 이 화면이 모르는 이벤트(뒤 라운드의 grid·facet 등)는 무시한다
      return { state, reload: [] };
  }
}

// 접속 직후, 그리고 하트비트가 열린 생성 집합의 변화를 보면 서버가 snapshot 을 다시 보낸다(06b 정함 13).
// 열려 있다고 알던 생성이 닫혔거나 처음 보는 생성이 이미 닫혀 있으면 놓친 generation 이벤트 대신 그 조회를
// 다시 읽는다. work 가 없던 화면(처음 받는 snapshot)은 다시 읽지 않는다 — 조회는 화면이 처음 열 때 읽는다
function applySnapshot(state: WorkState, work: WorkView): WorkEventResult {
  const reload: WorkResource[] = [];
  if (state.work) {
    const before = new Map(state.work.generations.map((g) => [g.id, g]));
    for (const g of work.generations) {
      if (isOpen(g.status)) continue;
      const known = before.get(g.id);
      if (!known || isOpen(known.status)) addAll(reload, reloadFor(g.kind));
    }
    // 목록에서 빠진 열린 생성(회수됨) — 무엇이 바뀌었는지 모르니 그 조회를 다시 읽는다
    const now = new Set(work.generations.map((g) => g.id));
    for (const g of state.work.generations) {
      if (isOpen(g.status) && !now.has(g.id)) addAll(reload, reloadFor(g.kind));
    }
  }
  const writing = new Set(work.generations.filter((g) => g.kind === "section" && isOpen(g.status)).map((g) => g.id));
  let live = state.live;
  for (const [key, section] of Object.entries(state.live)) {
    if (!writing.has(section.genId)) live = withoutKey(live, key);
  }
  return { state: { ...state, work, live }, reload };
}

function applyGeneration(state: WorkState, ev: WorkGenerationEvent): WorkEventResult {
  const prev = state.work?.generations.find((g) => g.id === ev.gen_id);
  // 끝난 생성에 늦게 온 queued — 이미 아는 것보다 앞선 상태로 되돌리지 않는다
  if (prev && statusRank(prev.status) > statusRank(ev.status)) return { state, reload: [] };
  const reload = isOpen(ev.status) ? [] : reloadFor(ev.gen_kind);
  const live = ev.gen_kind === "section" && ev.target !== null ? sectionLive(state.live, ev, ev.target) : state.live;
  if (!state.work) return { state: { ...state, live }, reload };
  const waiting = ev.status === "queued";
  const next: WorkGeneration = {
    id: ev.gen_id,
    kind: ev.gen_kind,
    target: ev.target,
    status: ev.status,
    model: ev.model ?? prev?.model ?? null,
    error: prev?.error ?? null,
    // 순번은 이벤트에 없다 — 대기 중이면 알던 값을 두고(다음 snapshot·조회가 맞춘다), 대기를 벗어나면 지운다
    position: waiting ? (prev?.position ?? null) : null,
    eta_sec: waiting ? (prev?.eta_sec ?? null) : null,
    others_ahead: waiting ? (prev?.others_ahead ?? false) : false,
  };
  const gens = state.work.generations;
  const generations = prev
    ? gens.map((g) => (g.id === ev.gen_id ? next : g))
    : [...gens, next].sort((a, b) => a.id - b.id);
  return { state: { ...state, work: { ...state.work, generations }, live }, reload };
}

// 절 생성이 끝나면 흐르던 글을 지운다(정본은 다시 읽은 계획서다). 같은 절에 새 생성이 열리면 옛 생성의 글을 지운다
function sectionLive(
  live: Record<string, LiveSection>,
  ev: WorkGenerationEvent,
  key: string,
): Record<string, LiveSection> {
  const cur = live[key];
  if (!cur) return live;
  const stale = isOpen(ev.status) ? cur.genId !== ev.gen_id : cur.genId === ev.gen_id;
  return stale ? withoutKey(live, key) : live;
}

// 조각은 offset 이 지금까지 받은 글자 수와 맞을 때만 잇는다. 어긋나면(놓친 조각·재접속) broken 으로 두고 더 잇지
// 않는다 — 빠진 글을 이어 붙여 보이지 않는다. 생성이 끝나면 계획서를 다시 읽어 맞춘다. reset 은 다시 부르기 전
// 서버가 보내는 비움이다
function applyDelta(live: Record<string, LiveSection>, ev: SectionDeltaEvent): Record<string, LiveSection> {
  const nextSeq = ev.seq + 1;
  if (ev.reset) return { ...live, [ev.target]: { genId: ev.gen_id, text: "", nextSeq, broken: false } };
  const cur = live[ev.target];
  if (!cur || cur.genId !== ev.gen_id) {
    // 처음 받는 조각이 처음부터(offset 0)가 아니면 앞 조각을 놓친 채 붙은 것이다(새로고침·재접속)
    const joined = ev.offset === 0;
    return { ...live, [ev.target]: { genId: ev.gen_id, text: joined ? ev.text : "", nextSeq, broken: !joined } };
  }
  if (cur.broken) return live;
  if (ev.offset !== charCount(cur.text)) return { ...live, [ev.target]: { ...cur, nextSeq, broken: true } };
  return { ...live, [ev.target]: { ...cur, text: cur.text + ev.text, nextSeq } };
}
