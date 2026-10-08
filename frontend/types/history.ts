import type { WorkPhase, WorkProgress } from "~/types/work";

export type HistoryKind = "book" | "paper" | "research";

// 유니온에 그냥 Omit 을 쓰면 공통 키만 남아 snapshot·refId 같은 종류별 필드가 사라진다
export type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;

export interface SnapshotBookInfo {
  cnts_id?: string;
  title?: string;
  personal_author?: string;
  corporate_author?: string;
  publisher?: string;
  pub_date?: string;
  themes?: string;
  keyword?: string;
  subject?: string;
  series_title?: string;
  grade?: string;
  kci_citations?: number;
  references?: string[];
}

export interface SnapshotItem {
  book_id: string;
  best_score: number;
  title_score?: number;
  content_score?: number;
  book_info?: SnapshotBookInfo;
  chunks: never[];
}

export interface BookSnapshot {
  query: string;
  rewritten_query?: string;
  books: SnapshotItem[];
}

export interface PaperSnapshot {
  query: string;
  books: SnapshotItem[];
}

export interface BookAi {
  intro: string;
  items: unknown[];
}

export interface PaperAi {
  text: string;
  refs: unknown[];
}

export interface HistoryResearchStatus {
  status: string;
  stage: string;
  // 아래 셋은 [이 연구 이어가기] 로 연구 행이 생긴 잡에만 값이 있다(app/schemas/history.py ResearchStatus).
  // 06a 전 서버에는 키가 없다
  phase?: WorkPhase | null;
  progress?: Partial<WorkProgress> | null;
  // 진행 중 생성(queued·running)이 있는가 — 사이드바 폴링 조건(06d)
  generating?: boolean;
}

export interface HistoryBase {
  id: string;
  kind: HistoryKind;
  title: string;
  createdAt: string;
  updatedAt?: string;
  params: Record<string, unknown>;
}

export interface BookEntry extends HistoryBase {
  kind: "book";
  snapshot?: BookSnapshot;
  ai?: BookAi;
}

export interface PaperEntry extends HistoryBase {
  kind: "paper";
  snapshot?: PaperSnapshot;
  ai?: PaperAi;
}

export interface ResearchEntry extends HistoryBase {
  kind: "research";
  refId: string;
  research?: HistoryResearchStatus;
}

export type HistoryEntry = BookEntry | PaperEntry | ResearchEntry;

export type HistoryEntryInput = DistributiveOmit<HistoryEntry, "id" | "createdAt">;

export interface HistoryPatch {
  title?: string;
  params?: Record<string, unknown>;
  snapshot?: BookSnapshot | PaperSnapshot;
  ai?: BookAi | PaperAi;
}

/** v1(`skx_search_history`) 항목 — 서버로 옮길 때만 읽는다 */
export interface LegacyHistoryEntry {
  id: string;
  type: "book" | "paper";
  query: string;
  timestamp: number | string;
  result?: unknown;
  aiSummary?: string;
}

// 아래는 app/schemas/history.py 의 선 모양 — 서버가 주는 snake_case 를 그대로 받는다
export interface HistoryItemOut {
  id: string;
  kind: HistoryKind;
  title: string;
  params: Record<string, unknown>;
  ref_id: string | null;
  created_at: string;
  updated_at: string;
  has_snapshot: boolean;
  has_ai: boolean;
  research: HistoryResearchStatus | null;
}

export interface HistoryItemDetail extends HistoryItemOut {
  snapshot: BookSnapshot | PaperSnapshot | null;
  ai: BookAi | PaperAi | null;
}

export interface HistoryListOut {
  items: HistoryItemOut[];
  next_cursor: string | null;
}

export interface HistoryItemIn {
  kind: HistoryKind;
  title: string;
  params: Record<string, unknown>;
  snapshot: BookSnapshot | PaperSnapshot | null;
  ai: BookAi | PaperAi | null;
  ref_id: string | null;
}

export interface HistoryImportItem extends HistoryItemIn {
  id?: string | null;
  legacy_id?: string | null;
  created_at?: string | null;
}

export interface HistoryImportOut {
  imported: number;
  skipped: number;
  id_map: Record<string, string>;
}
