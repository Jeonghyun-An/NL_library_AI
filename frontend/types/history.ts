import type { SearchResponse } from "./search";

export interface HistoryEntry {
  id: string;
  query: string;
  timestamp: number | string;
  result: SearchResponse;
}
