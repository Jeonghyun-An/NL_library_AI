export interface ChunkHit {
  chunk_id: string;
  book_id: string;
  chunk_idx: number;
  section_idx: number;
  text: string;
  page_start: number;
  page_end: number;
  score: number;
  rerank_score?: number;
}

export interface BookInfo {
  cnts_id: string;
  title: string;
  title_remainder?: string;
  part_number?: string;
  title_responsibility?: string;
  personal_author?: string;
  corporate_author?: string;
  publisher?: string;
  pub_place?: string;
  pub_date?: string;
  extent?: string;
  kdc?: string;
  ddc?: string;
  isbn?: string;
  uci?: string;
  series_title?: string;
  subject?: string;
  keyword?: string;
  language?: string;
  abstract?: string;
  url?: string;
  media_type?: string;
  material_type?: string;
  genre?: string;
  // 생성 필드 (인덱싱 시 생성)
  summary?: string;
  introduction?: string;
  plot?: string;
  read_effect?: string;
  themes?: string;
  cover_image_key?: string;
  is_embedded: boolean;
  chunk_count?: number;
  full_text_length?: number;
  // KCI 논문 전용
  grade?: string;
  vol_issue?: string;
  kci_citations?: number;
  wos_citations?: number;
}

export interface BookChunkGroup {
  book_id: string;
  book_info?: BookInfo;
  best_score: number;
  chunks: ChunkHit[];
  reason?: string;
}

export interface ChunkSearchResponse {
  mode: "chunk";
  query: string;
  rewritten_query?: string;
  answer?: string;
  chunks: ChunkHit[];
  elapsed_ms: number;
}

export interface BookSearchResponse {
  mode: "book";
  query: string;
  rewritten_query?: string;
  books: BookChunkGroup[];
  elapsed_ms: number;
}

export type SearchResponse = ChunkSearchResponse | BookSearchResponse;

export interface SearchRequest {
  query: string;
  mode: "chunk" | "book";
  top_k: number;
  use_rewrite: boolean;
  use_rerank: boolean;
}
