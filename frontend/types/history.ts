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
  /** 저자 키워드(논문은 보통 5~8개) — 카드 키워드 칩의 첫 출처 */
  extracted_keywords?: string[];
  subject?: string;
  /** 도서관 분류(KDC) — 키워드가 없는 소장자료 카드의 분류 칩 */
  kdc?: string;
  series_title?: string;
  grade?: string;
  kci_citations?: number;
  references?: string[];
  // 1위 도서만 담는다(slimBookResult) — 복원 때 '이 책에서 얻을 수 있는 것'을 다시 받지 않고 그린다
  read_effect?: string;
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

/** 소장자료 AI 영역 — 1위 도서의 추천 이유(SKOVIX 추천 1권). keywords 는 서버가 이유 스트림 첫 이벤트로 준 도서 키워드 */
export interface BookAiPick {
  book_id: string;
  reason: string;
  keywords?: string[];
}

/** 옛 AI 컬렉션 기록과 v1 가져오기가 남긴 모양 — 화면은 쓰지 않는다(utils/bookAiPick.readSavedReason) */
export interface LegacyBookAi {
  intro: string;
  items: unknown[];
}

export type BookAi = BookAiPick | LegacyBookAi;

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
