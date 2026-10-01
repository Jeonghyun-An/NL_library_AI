// frontend/utils/historySnapshot.ts
import type { BookSnapshot, PaperSnapshot, SnapshotBookInfo, SnapshotItem } from "~/types/history";

export const SNAPSHOT_MAX_ITEMS = 20;
export const SNAPSHOT_MAX_REFERENCES = 30;

// 빼는 필드를 나열하면 서버가 필드를 늘릴 때 저장량도 따라 는다 — 카드가 그리는 필드만 고른다
const BOOK_INFO_FIELDS: readonly (keyof SnapshotBookInfo)[] = [
  "cnts_id",
  "title",
  "personal_author",
  "corporate_author",
  "publisher",
  "pub_date",
  "themes",
  "keyword",
  "subject",
];

const PAPER_INFO_FIELDS: readonly (keyof SnapshotBookInfo)[] = [
  "cnts_id",
  "title",
  "personal_author",
  "corporate_author",
  "pub_date",
  "series_title",
  "grade",
  "kci_citations",
  "references",
];

type Loose = Record<string, unknown>;

function isObject(v: unknown): v is Loose {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function pickInfo(info: unknown, fields: readonly (keyof SnapshotBookInfo)[]): SnapshotBookInfo | undefined {
  if (!isObject(info)) return undefined;
  const out: Loose = {};
  for (const field of fields) {
    const value = info[field];
    if (value === undefined || value === null || value === "") continue;
    out[field] =
      field === "references" && Array.isArray(value)
        ? value.filter((r) => typeof r === "string").slice(0, SNAPSHOT_MAX_REFERENCES)
        : value;
  }
  return out as SnapshotBookInfo;
}

function slimItems(
  result: unknown,
  fields: readonly (keyof SnapshotBookInfo)[],
  withScores: boolean,
): SnapshotItem[] | null {
  if (!isObject(result) || !Array.isArray(result.books)) return null;
  return result.books
    .filter(isObject)
    .filter((b) => typeof b.book_id === "string")
    .slice(0, SNAPSHOT_MAX_ITEMS)
    .map((b) => {
      const item: SnapshotItem = {
        book_id: b.book_id as string,
        best_score: typeof b.best_score === "number" ? b.best_score : 0,
        chunks: [],
      };
      if (withScores && typeof b.title_score === "number") item.title_score = b.title_score;
      if (withScores && typeof b.content_score === "number") item.content_score = b.content_score;
      const info = pickInfo(b.book_info, fields);
      if (info) item.book_info = info;
      return item;
    });
}

export function slimBookResult(result: unknown): BookSnapshot | null {
  const books = slimItems(result, BOOK_INFO_FIELDS, true);
  if (!books) return null;
  const r = result as Loose;
  const snap: BookSnapshot = { query: typeof r.query === "string" ? r.query : "", books };
  if (typeof r.rewritten_query === "string" && r.rewritten_query) snap.rewritten_query = r.rewritten_query;
  return snap;
}

export function slimPaperResult(result: unknown): PaperSnapshot | null {
  const books = slimItems(result, PAPER_INFO_FIELDS, false);
  if (!books) return null;
  const r = result as Loose;
  return { query: typeof r.query === "string" ? r.query : "", books };
}
