// frontend/utils/historySnapshot.ts
import type { BookSnapshot, PaperSnapshot, SnapshotBookInfo, SnapshotItem } from "~/types/history";

export const SNAPSHOT_MAX_ITEMS = 20;
export const SNAPSHOT_MAX_REFERENCES = 30;
// 논문은 건수로 자르지 않고 바이트로 맞춘다 — 검색이 top_k 의 몇 배(지금 최대 60편)를 돌려주고 화면은 그 전부를 쪽으로
// 나눠 보이므로, 상세에서 돌아와 둘째 쪽 이후의 카드 자리를 찾으려면 복원 목록에 모두 있어야 한다.
// 서버 상한(app/api/history.py 의 200KB)은 파이썬 구분자(", "·": ")까지 세어 여유를 둔다
export const PAPER_SNAPSHOT_MAX_BYTES = 180 * 1024;

// 빼는 필드를 나열하면 서버가 필드를 늘릴 때 저장량도 따라 는다 — 카드(ResultCard)가 그리는 필드만 고른다.
// 카드가 새 필드를 읽게 되면 여기에도 넣어야 한다 — 복원 화면(주소의 h=)은 이 스냅샷으로 카드를 그려 빠진 필드의 칩·줄이 사라진다.
// tests/unit/historySnapshot.test.ts 가 cardKeywords·cardMeta·kdcChip 이 읽는 필드가 이 목록에 모두 있는지 검사한다
export const BOOK_INFO_FIELDS: readonly (keyof SnapshotBookInfo)[] = [
  "cnts_id",
  "title",
  "personal_author",
  "corporate_author",
  "publisher",
  "pub_date",
  // 키워드 칩(저자 키워드 → keyword → themes → subject)과 키워드가 없을 때의 분류 칩(kdc)
  "extracted_keywords",
  "keyword",
  "themes",
  "subject",
  "kdc",
];

export const PAPER_INFO_FIELDS: readonly (keyof SnapshotBookInfo)[] = [
  "cnts_id",
  "title",
  "personal_author",
  "corporate_author",
  "pub_date",
  "series_title",
  "grade",
  "kci_citations",
  "extracted_keywords",
  "keyword",
  "themes",
  "subject",
  // 상한(PAPER_SNAPSHOT_MAX_BYTES)에 닿으면 가장 먼저 뒤쪽 논문부터 빠진다 — 키워드·서지는 남는다
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
    if (Array.isArray(value)) {
      // 문자열 목록만, 비면 싣지 않는다(저자 키워드가 없는 논문은 빈 배열로 온다)
      const list = value.filter((r) => typeof r === "string");
      if (!list.length) continue;
      out[field] = field === "references" ? list.slice(0, SNAPSHOT_MAX_REFERENCES) : list;
      continue;
    }
    out[field] = value;
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
  // 1위 도서의 '이 책에서 얻을 수 있는 것'(read_effect)만 싣는다 — 소장자료 AI 영역이 복원 때 다시 받지 않고 그린다.
  // 목록 카드는 그리지 않는 필드라 나머지 도서에는 싣지 않는다(수백 자씩 곱해 저장량만 는다)
  const top = (r.books as unknown[]).filter(isObject).find((b) => typeof b.book_id === "string");
  const effect = isObject(top?.book_info) ? top.book_info.read_effect : undefined;
  if (books[0] && typeof effect === "string" && effect.trim()) {
    books[0].book_info = { ...books[0].book_info, read_effect: effect };
  }
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
  const books = slimItems(result, PAPER_INFO_FIELDS, true);
  if (!books) return null;
  const r = result as Loose;
  const snap: PaperSnapshot = { query: typeof r.query === "string" ? r.query : "", books };
  shedReferences(snap);
  return snap;
}
