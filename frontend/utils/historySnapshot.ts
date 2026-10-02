// frontend/utils/historySnapshot.ts
import type { BookSnapshot, PaperSnapshot, SnapshotBookInfo, SnapshotItem } from "~/types/history";

export const SNAPSHOT_MAX_ITEMS = 20;
export const SNAPSHOT_MAX_REFERENCES = 30;
// 논문은 건수로 자르지 않고 바이트로 맞춘다 — 검색이 top_k 의 몇 배(지금 최대 60편)를 돌려주고 화면은 그 전부를 쪽으로
// 나눠 보이므로, 상세에서 돌아와 둘째 쪽 이후의 카드 자리를 찾으려면 복원 목록에 모두 있어야 한다.
// 서버 상한(app/api/history.py 의 200KB)은 파이썬 구분자(", "·": ")까지 세어 여유를 둔다
export const PAPER_SNAPSHOT_MAX_BYTES = 180 * 1024;

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
  maxItems?: number,
): SnapshotItem[] | null {
  if (!isObject(result) || !Array.isArray(result.books)) return null;
  return result.books
    .filter(isObject)
    .filter((b) => typeof b.book_id === "string")
    .slice(0, maxItems)
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
  const books = slimItems(result, BOOK_INFO_FIELDS, true, SNAPSHOT_MAX_ITEMS);
  if (!books) return null;
  const r = result as Loose;
  const snap: BookSnapshot = { query: typeof r.query === "string" ? r.query : "", books };
  if (typeof r.rewritten_query === "string" && r.rewritten_query) snap.rewritten_query = r.rewritten_query;
  return snap;
}

const utf8 = new TextEncoder();

function utf8Bytes(value: unknown): number {
  return utf8.encode(JSON.stringify(value)).length;
}

// 상한을 넘으면 관련도가 낮은 뒤쪽 논문부터 참고문헌을 뺀다 — 요약이 인용하는 앞쪽 논문의 인용 모달은 그대로 둔다.
// 넘긴 채 보내면 413 이라 기록이 결과 없이 남고, 돌아올 때 재검색으로 물러선다
function shedReferences(snap: PaperSnapshot): void {
  let excess = utf8Bytes(snap) - PAPER_SNAPSHOT_MAX_BYTES;
  for (let i = snap.books.length - 1; excess > 0 && i >= 0; i--) {
    const item = snap.books[i]!;
    if (!item.book_info?.references) continue;
    const before = utf8Bytes(item);
    delete item.book_info.references;
    excess -= before - utf8Bytes(item);
  }
}

export function slimPaperResult(result: unknown): PaperSnapshot | null {
  const books = slimItems(result, PAPER_INFO_FIELDS, false);
  if (!books) return null;
  const r = result as Loose;
  const snap: PaperSnapshot = { query: typeof r.query === "string" ? r.query : "", books };
  shedReferences(snap);
  return snap;
}
