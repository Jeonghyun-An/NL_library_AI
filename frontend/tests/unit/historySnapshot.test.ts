// frontend/tests/unit/historySnapshot.test.ts
import { describe, expect, it } from "vitest";
import {
  SNAPSHOT_MAX_ITEMS,
  SNAPSHOT_MAX_REFERENCES,
  slimBookResult,
  slimPaperResult,
} from "~/utils/historySnapshot";

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
});
