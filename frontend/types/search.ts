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
  personal_author?: string;
  corporate_author?: string;
  publisher?: string;
  pub_place?: string;
  pub_date?: string;
  extent?: string;
  kdc?: string;
  ddc?: string;
  isbn?: string;
  series_title?: string;
  subject?: string;
  keyword?: string;
  language?: string;
  summary?: string;
  introduction?: string;
  abstract?: string;
  genre?: string;
  url?: string;
  is_embedded: boolean;
  chunk_count?: number;
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
