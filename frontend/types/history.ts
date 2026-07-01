export interface HistoryEntry {
  id: string;
  type: "book" | "paper";
  query: string;
  timestamp: number | string;
  result?: any;       // full search response (books array)
  aiSummary?: string; // AI 요약/큐레이션 텍스트 (스트리밍 완료 후 저장)
}
