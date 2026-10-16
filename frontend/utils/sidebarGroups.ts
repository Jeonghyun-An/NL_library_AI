// frontend/utils/sidebarGroups.ts
import type { BookEntry, HistoryEntry, HistoryKind, PaperEntry, ResearchEntry } from "~/types/history";

// 이 상태의 딥리서치가 있으면 배지가 바뀔 수 있다 — 사이드바 폴링 조건. 승인 대기는 사용자가 움직여야 바뀌므로 뺀다
export const LIVE_STATUSES = new Set(["created", "planning", "approved", "queued", "running"]);
// 묶음 맨 위에 둘 상태 — 진행 중에 사용자의 승인을 기다리는 것까지(눈에 띄어야 한다)
const TOP_STATUSES = new Set([...LIVE_STATUSES, "awaiting_approval"]);

export type RecentLabel = "소장자료" | "논문";

export interface RecentItem {
  entry: BookEntry | PaperEntry;
  label: RecentLabel;
}

export interface SidebarGroupOptions {
  /** research 를 앞에서 이만큼만 돌려준다(진행 중·최신순으로 정렬한 뒤 자른다). 없으면 자르지 않는다 */
  researchLimit?: number;
}

export interface SidebarGroups {
  research: ResearchEntry[];
  /** 자르기 전 딥리서치 수 — '더 보기 (N)' 의 N 은 researchTotal - research.length */
  researchTotal: number;
  recent: RecentItem[];
}

const RECENT_LABEL = { book: "소장자료", paper: "논문" } as const satisfies Record<BookEntry["kind"] | PaperEntry["kind"], RecentLabel>;

export function isLiveResearch(entry: HistoryEntry): boolean {
  return entry.kind === "research" && !!entry.research && LIVE_STATUSES.has(entry.research.status);
}

export function countLiveResearch(items: readonly HistoryEntry[]): number {
  return items.filter(isLiveResearch).length;
}

/** 접힌 사이드바의 현미경 점 — 진행 중이거나 사용자의 승인을 기다리는(눈에 띄어야 하는) 딥리서치가 하나라도 있는가 */
export function hasActiveResearch(items: readonly HistoryEntry[]): boolean {
  return items.some((e) => e.kind === "research" && !!e.research && TOP_STATUSES.has(e.research.status));
}

/** 목록에 보일 시각 — updatedAt 이 비어 있으면(빈 문자열 포함) createdAt */
export function entryTime(entry: HistoryEntry): string {
  return entry.updatedAt || entry.createdAt;
}

// 읽을 수 없는 시각은 가장 오래된 것으로 쳐 맨 아래로 보낸다
function timeOf(entry: HistoryEntry): number {
  const ms = Date.parse(entryTime(entry));
  return Number.isNaN(ms) ? Number.NEGATIVE_INFINITY : ms;
}

/** 목록 시각 문구 — 방금 · N분 전 · N시간 전 · 월/일. 읽을 수 없는 시각은 빈 문자열(Invalid Date 를 내보내지 않는다) */
export function formatHistoryTime(ts: string, now: number = Date.now()): string {
  if (!ts) return "";
  const ms = Date.parse(ts);
  if (Number.isNaN(ms)) return "";
  const diff = (now - ms) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return new Date(ms).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
}

// 최신순. 같은 시각이면 들어온 순서를 지킨다(정렬이 안정적이라고 믿지 않고 순번을 함께 비교한다)
function newestFirst<T>(list: T[], entryOf: (item: T) => HistoryEntry, rank: (item: T) => number = () => 0): T[] {
  return list
    .map((item, index) => ({ item, index, time: timeOf(entryOf(item)), rank: rank(item) }))
    .sort((a, b) => a.rank - b.rank || (a.time === b.time ? 0 : b.time > a.time ? 1 : -1) || a.index - b.index)
    .map((x) => x.item);
}

/**
 * 사이드바 기록을 두 묶음으로 가른다.
 * - research: 딥리서치만. 진행 중·승인 대기가 먼저, 그다음 최신순. researchLimit 이 있으면 정렬한 뒤 앞에서 자른다
 * - researchTotal: 자르기 전 딥리서치 수
 * - recent: 도서·논문을 섞어 최신순, 종류 라벨('소장자료'·'논문')을 붙인다
 * 모르는 종류는 어느 쪽에도 넣지 않는다. 입력 배열은 바꾸지 않는다.
 */
export function groupSidebarHistory(items: readonly HistoryEntry[], opts: SidebarGroupOptions = {}): SidebarGroups {
  const research: ResearchEntry[] = [];
  const recent: RecentItem[] = [];
  for (const entry of items) {
    if (entry.kind === "research") research.push(entry);
    else if (entry.kind === "book" || entry.kind === "paper") recent.push({ entry, label: RECENT_LABEL[entry.kind] });
  }
  const sorted = newestFirst(
    research,
    (e) => e,
    (e) => (e.research && TOP_STATUSES.has(e.research.status) ? 0 : 1),
  );
  const limit = opts.researchLimit;
  return {
    research: limit === undefined ? sorted : sorted.slice(0, Math.max(0, limit)),
    researchTotal: sorted.length,
    recent: newestFirst(recent, (r) => r.entry),
  };
}

/** 사이드바의 두 묶음 — DeepResearch(딥리서치)와 최근 검색(소장자료·논문) */
export type SidebarGroupKey = "research" | "recent";

const GROUP_KINDS: Record<SidebarGroupKey, readonly HistoryKind[]> = {
  research: ["research"],
  recent: ["book", "paper"],
};

/**
 * 사이드바 안의 줄 안내 문구(SkxInlineError). 오류 문구 규칙대로 해요체, 문장마다 줄을 바꾼다.
 *  loadFailed : 묶음의 목록을 못 읽었고 보이는 줄도 없음 — '기록 없음'으로 보이지 않게(옛 문구의 '잠시 뒤 다시 열어 주세요'는
 *               [다시 시도] 버튼이 생겨 '다시 시도해 주세요'로)
 *  loadPartial: 못 읽은 종류가 있는데 보이는 줄은 있음 — 앞서 읽은 줄이 낡았거나 같은 묶음의 다른 종류만 읽혔다
 *  storageBlocked: 브라우저 ID 를 저장하지 못함(사이트 데이터 차단) — 새로 고칠 때마다 새 ID 라 서버 기록이 이어지지 않는다
 */
export const SIDEBAR_NOTICE = {
  loadFailed: "기록을 불러오지 못했어요.\n잠시 뒤 다시 시도해 주세요.",
  loadPartial: "기록을 다 불러오지 못했어요.\n잠시 뒤 다시 시도해 주세요.",
  storageBlocked: "이 브라우저는 사이트 데이터 저장이 막혀 있어 새로 고치면 기록이 사라져요.",
} as const;

/** 묶음의 목록 실패 안내 — 그 묶음의 종류 중 못 읽은 것이 없으면 null. rowCount 는 그 묶음에 보이는(자르기 전) 줄 수 */
export function groupLoadError(
  group: SidebarGroupKey,
  failedKinds: readonly HistoryKind[],
  rowCount: number,
): string | null {
  if (!GROUP_KINDS[group].some((k) => failedKinds.includes(k))) return null;
  return rowCount > 0 ? SIDEBAR_NOTICE.loadPartial : SIDEBAR_NOTICE.loadFailed;
}
