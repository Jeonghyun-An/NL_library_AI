// frontend/utils/sidebarGroups.ts
import type { BookEntry, HistoryEntry, PaperEntry, ResearchEntry } from "~/types/history";

// 이 상태의 딥리서치가 있으면 배지가 바뀔 수 있다 — 사이드바 폴링 조건. 승인 대기는 사용자가 움직여야 바뀌므로 뺀다
export const LIVE_STATUSES = new Set(["created", "planning", "approved", "queued", "running"]);
// 묶음 맨 위에 둘 상태 — 진행 중에 사용자의 승인을 기다리는 것까지(눈에 띄어야 한다)
const TOP_STATUSES = new Set([...LIVE_STATUSES, "awaiting_approval"]);

export type RecentLabel = "소장자료" | "논문";

export interface RecentItem {
  entry: BookEntry | PaperEntry;
  label: RecentLabel;
}

export interface SidebarGroups {
  research: ResearchEntry[];
  recent: RecentItem[];
}

const RECENT_LABEL = { book: "소장자료", paper: "논문" } as const satisfies Record<BookEntry["kind"] | PaperEntry["kind"], RecentLabel>;

export function isLiveResearch(entry: HistoryEntry): boolean {
  return entry.kind === "research" && !!entry.research && LIVE_STATUSES.has(entry.research.status);
}

export function countLiveResearch(items: readonly HistoryEntry[]): number {
  return items.filter(isLiveResearch).length;
}

// 읽을 수 없는 시각은 가장 오래된 것으로 쳐 맨 아래로 보낸다
function timeOf(entry: HistoryEntry): number {
  const ms = Date.parse(entry.updatedAt ?? entry.createdAt);
  return Number.isNaN(ms) ? Number.NEGATIVE_INFINITY : ms;
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
 * - research: 딥리서치만. 진행 중·승인 대기가 먼저, 그다음 최신순
 * - recent: 도서·논문을 섞어 최신순, 종류 라벨('소장자료'·'논문')을 붙인다
 * 모르는 종류는 어느 쪽에도 넣지 않는다. 입력 배열은 바꾸지 않는다.
 */
export function groupSidebarHistory(items: readonly HistoryEntry[]): SidebarGroups {
  const research: ResearchEntry[] = [];
  const recent: RecentItem[] = [];
  for (const entry of items) {
    if (entry.kind === "research") research.push(entry);
    else if (entry.kind === "book" || entry.kind === "paper") recent.push({ entry, label: RECENT_LABEL[entry.kind] });
  }
  return {
    research: newestFirst(
      research,
      (e) => e,
      (e) => (e.research && TOP_STATUSES.has(e.research.status) ? 0 : 1),
    ),
    recent: newestFirst(recent, (r) => r.entry),
  };
}
