// frontend/tests/unit/historySnapshot.test.ts
import { describe, expect, it } from "vitest";
import {
  PAPER_SNAPSHOT_MAX_BYTES,
  SNAPSHOT_MAX_ITEMS,
  SNAPSHOT_MAX_REFERENCES,
  slimBookResult,
  slimPaperResult,
} from "~/utils/historySnapshot";

function utf8Bytes(v: unknown): number {
  return new TextEncoder().encode(JSON.stringify(v)).length;
}

// 서버(app/api/history.py)는 파이썬 json.dumps 기본 구분자(", "·": ")로 잰다 — 구조 쉼표·콜론마다 1바이트씩 더 든다
function separators(v: unknown): number {
  if (typeof v !== "object" || v === null) return 0;
  const children = Object.values(v);
  const own = Array.isArray(v) ? children.length - 1 : children.length * 2 - 1;
  return Math.max(own, 0) + children.reduce((n: number, c) => n + separators(c), 0);
}

function serverBook(i: number) {
  return {
    book_id: `B${i}`,
    best_score: 0.9,
    title_score: 0.8,
    content_score: 0.7,
    reason: "이유",
    chunks: [{ chunk_id: "c1", text: "본문".repeat(200), page_start: 1, page_end: 2, score: 0.5 }],
    book_info: {
      cnts_id: `B${i}`,
      title: `책 ${i}`,
      personal_author: "홍길동",
      publisher: "출판사",
      pub_date: "20200101",
      themes: "경제,무역",
      summary: "요약".repeat(300),
      plot: "줄거리",
      introduction: "소개",
      read_effect: "효과",
      abstract: "초록",
      cover_prompt: "표지 프롬프트",
      references: ["참고1"],
      is_embedded: true,
      extracted_keywords: ["k"],
    },
  };
}

describe("slimBookResult", () => {
  it("목록 카드가 쓰는 필드만 남긴다", () => {
    const snap = slimBookResult({
      mode: "book",
      query: "경제",
      rewritten_query: "한국 경제",
      elapsed_ms: 10,
      books: [serverBook(1)],
    });
    expect(snap).toEqual({
      query: "경제",
      rewritten_query: "한국 경제",
      books: [
        {
          book_id: "B1",
          best_score: 0.9,
          title_score: 0.8,
          content_score: 0.7,
          chunks: [],
          book_info: {
            cnts_id: "B1",
            title: "책 1",
            personal_author: "홍길동",
            publisher: "출판사",
            pub_date: "20200101",
            themes: "경제,무역",
          },
        },
      ],
    });
  });

  it("서버가 새 필드를 보내도 저장하지 않는다", () => {
    const base = serverBook(1);
    const book = { ...base, new_field: "x", book_info: { ...base.book_info, brand_new: "y".repeat(1000) } };
    const snap = slimBookResult({ query: "q", books: [book] })!;
    expect(snap.books[0]).not.toHaveProperty("new_field");
    expect(snap.books[0]!.book_info).not.toHaveProperty("brand_new");
  });

  it(`최대 ${SNAPSHOT_MAX_ITEMS}건만 남긴다`, () => {
    const snap = slimBookResult({ query: "q", books: Array.from({ length: 25 }, (_, i) => serverBook(i)) })!;
    expect(snap.books).toHaveLength(SNAPSHOT_MAX_ITEMS);
    expect(snap.books[0]!.book_id).toBe("B0");
  });

  it("모양이 틀리면 null, book_id 없는 항목은 건너뛴다", () => {
    expect(slimBookResult(null)).toBeNull();
    expect(slimBookResult({ query: "q" })).toBeNull();
    expect(slimBookResult({ query: "q", books: "x" })).toBeNull();
    const snap = slimBookResult({ query: "q", books: [{ best_score: 1 }, serverBook(2)] })!;
    expect(snap.books.map((b) => b.book_id)).toEqual(["B2"]);
  });

  it("빈 값 필드는 싣지 않는다", () => {
    const b = serverBook(1);
    const snap = slimBookResult({
      query: "q",
      books: [{ ...b, book_info: { ...b.book_info, publisher: "", personal_author: null } }],
    })!;
    expect(snap.books[0]!.book_info).not.toHaveProperty("publisher");
    expect(snap.books[0]!.book_info).not.toHaveProperty("personal_author");
  });
});

describe("slimPaperResult", () => {
  it("논문 카드·인용 모달이 쓰는 필드만 남기고 참고문헌은 상한까지만", () => {
    const paper = {
      book_id: "P1",
      best_score: 0.7,
      title_score: 0.5,
      chunks: [{ text: "x" }],
      book_info: {
        cnts_id: "P1",
        title: "논문",
        personal_author: "김",
        corporate_author: "학회",
        pub_date: "2021.03",
        series_title: "학술지",
        grade: "KCI 등재",
        kci_citations: 12,
        abstract: "초록".repeat(500),
        summary: "요약",
        introduction: "소개",
        references: Array.from({ length: 40 }, (_, i) => `참고 ${i}`),
      },
    };
    const snap = slimPaperResult({ query: "딥러닝", books: [paper] })!;
    expect(snap.query).toBe("딥러닝");
    const item = snap.books[0]!;
    expect(item).not.toHaveProperty("title_score");
    expect(item.chunks).toEqual([]);
    expect(item.book_info).toMatchObject({
      title: "논문",
      grade: "KCI 등재",
      series_title: "학술지",
      kci_citations: 12,
      corporate_author: "학회",
    });
    expect(item.book_info).not.toHaveProperty("abstract");
    expect(item.book_info!.references).toHaveLength(SNAPSHOT_MAX_REFERENCES);
  });

  it("모양이 틀리면 null", () => {
    expect(slimPaperResult(undefined)).toBeNull();
  });

  // 참고문헌 한 줄이 한글 100자(300바이트)라 서른 줄이면 한 편이 9KB 가까이 된다
  function serverPaper(i: number, refCount: number) {
    return {
      book_id: `P${i}`,
      best_score: 1 - i / 100,
      chunks: [{ text: "본문" }],
      book_info: {
        cnts_id: `P${i}`,
        title: `논문 ${i}`,
        grade: "KCI 등재",
        references: Array.from({ length: refCount }, () => "참고문헌".repeat(25)),
      },
    };
  }

  it(`검색이 돌려준 논문은 ${SNAPSHOT_MAX_ITEMS}편을 넘어도 모두 남긴다 — 둘째 쪽 이후 카드도 돌아와 찾는다`, () => {
    const books = Array.from({ length: 60 }, (_, i) => serverPaper(i, 2));
    const snap = slimPaperResult({ query: "q", books })!;
    expect(snap.books.map((b) => b.book_id)).toEqual(books.map((b) => b.book_id));
    expect(snap.books.every((b) => b.book_info!.references!.length === 2)).toBe(true);
  });

  it("서버 상한에 닿을 만큼이면 뒤쪽 논문부터 넘는 만큼만 참고문헌을 뺀다", () => {
    const books = Array.from({ length: 60 }, (_, i) => serverPaper(i, 40));
    const snap = slimPaperResult({ query: "q", books })!;
    expect(snap.books).toHaveLength(60);
    expect(utf8Bytes(snap) + separators(snap)).toBeLessThanOrEqual(200 * 1024);
    // 앞쪽은 참고문헌을 그대로 두고 뒤쪽만 뺀다
    const cut = snap.books.findIndex((b) => !b.book_info!.references);
    expect(cut).toBeGreaterThan(0);
    expect(snap.books.slice(0, cut).every((b) => b.book_info!.references!.length === SNAPSHOT_MAX_REFERENCES)).toBe(true);
    expect(snap.books.slice(cut).every((b) => !b.book_info!.references)).toBe(true);
    // 마지막으로 뺀 논문의 참고문헌을 되돌리면 상한을 넘는다 — 더 빼지 않았다
    snap.books[cut]!.book_info!.references = snap.books[0]!.book_info!.references;
    expect(utf8Bytes(snap)).toBeGreaterThan(PAPER_SNAPSHOT_MAX_BYTES);
  });
});
