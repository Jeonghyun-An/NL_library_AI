export interface BookOut {
  id: string;
  nl_id: string;
  title: string;
  author: string | null;
  publisher: string | null;
  pub_year: number | null;
  isbn: string | null;
  call_no: string | null;
  subject: string | null;
  summary: string | null;
  is_embedded: boolean;
  created_at: string;
}

export interface SearchResult {
  book: BookOut;
  score: number;
  reason: string;
}

export interface SearchResponse {
  query: string;
  rewritten_query: string;
  results: SearchResult[];
  elapsed_ms: number;
}
