// frontend/tests/unit/historySnapshot.test.ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  BOOK_INFO_FIELDS,
  BOOK_SNAPSHOT_MAX_BYTES,
  PAPER_INFO_FIELDS,
  PAPER_SNAPSHOT_MAX_BYTES,
  SNAPSHOT_EXCERPT_MAX_CHARS,
  SNAPSHOT_MAX_REFERENCES,
  slimBookResult,
  slimPaperResult,
} from "~/utils/historySnapshot";
import { kdcChip } from "~/utils/kdc";
import { cardKeywords, cardMeta } from "~/utils/resultCard";
import { SHORT_ABSTRACT_CHARS, SUMMARY_PAPER_LIMIT, summaryExcerpt, type ExcerptInfo } from "~/utils/summaryExcerpt";

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
            extracted_keywords: ["k"],
            // 1위 도서만 싣는다 — 복원 때 '이 책에서 얻을 수 있는 것'을 그리려고
            read_effect: "효과",
          },
        },
      ],
    });
  });

  it("read_effect 는 1위 도서에만 싣는다(나머지는 목록 카드가 안 그려 저장량만 는다)", () => {
    const snap = slimBookResult({ query: "q", books: [serverBook(1), serverBook(2), serverBook(3)] })!;
    expect(snap.books[0]!.book_info?.read_effect).toBe("효과");
    expect(snap.books[1]!.book_info).not.toHaveProperty("read_effect");
    expect(snap.books[2]!.book_info).not.toHaveProperty("read_effect");
  });

  it("1위 도서의 read_effect 가 비었거나 없으면 싣지 않는다", () => {
    const b = serverBook(1);
    for (const read_effect of ["  ", null, undefined]) {
      const snap = slimBookResult({ query: "q", books: [{ ...b, book_info: { ...b.book_info, read_effect } }] })!;
      expect(snap.books[0]!.book_info).not.toHaveProperty("read_effect");
    }
  });

  it("서버가 새 필드를 보내도 저장하지 않는다", () => {
    const base = serverBook(1);
    const book = { ...base, new_field: "x", book_info: { ...base.book_info, brand_new: "y".repeat(1000) } };
    const snap = slimBookResult({ query: "q", books: [book] })!;
    expect(snap.books[0]).not.toHaveProperty("new_field");
    expect(snap.books[0]!.book_info).not.toHaveProperty("brand_new");
  });

  it("건수로 자르지 않는다 — 검색이 돌려준 도서는 20권을 넘어도 모두 남긴다(둘째 쪽 이후 카드도 복원한다)", () => {
    const books = Array.from({ length: 60 }, (_, i) => serverBook(i));
    const snap = slimBookResult({ query: "q", books })!;
    expect(snap.books.map((b) => b.book_id)).toEqual(books.map((b) => b.book_id));
    expect(utf8Bytes(snap) + separators(snap)).toBeLessThanOrEqual(200 * 1024);
  });

  // 키워드 문자열이 한 권에 6KB 가까이 되는 극단 — 서버 상한(200KB)에 닿는 만큼
  function fatBook(i: number) {
    const b = serverBook(i);
    return { ...b, book_info: { ...b.book_info, themes: "경제무역".repeat(1000) } };
  }

  it("서버 상한에 닿을 만큼이면 뒤쪽 도서부터 넘는 만큼만 뺀다 — 1위와 앞쪽은 그대로", () => {
    const books = Array.from({ length: 60 }, (_, i) => fatBook(i));
    const snap = slimBookResult({ query: "q", books })!;
    expect(snap.books.length).toBeGreaterThan(1);
    expect(snap.books.length).toBeLessThan(60);
    expect(snap.books.map((b) => b.book_id)).toEqual(books.slice(0, snap.books.length).map((b) => b.book_id));
    expect(utf8Bytes(snap) + separators(snap)).toBeLessThanOrEqual(200 * 1024);
    expect(utf8Bytes(snap)).toBeLessThanOrEqual(BOOK_SNAPSHOT_MAX_BYTES);
    // 한 권을 더 실으면 상한을 넘는다 — 더 빼지 않았다
    const next = slimBookResult({ query: "q", books: [books[snap.books.length]!] })!.books[0]!;
    expect(utf8Bytes({ ...snap, books: [...snap.books, next] })).toBeGreaterThan(BOOK_SNAPSHOT_MAX_BYTES);
  });

  it("상한을 넘어도 1위 도서는 남기고, 그 책의 read_effect 도 그대로 싣는다", () => {
    const top = { ...fatBook(0), book_info: { ...fatBook(0).book_info, read_effect: "얻는 것" } };
    const snap = slimBookResult({ query: "q", books: [top, ...Array.from({ length: 59 }, (_, i) => fatBook(i + 1))] })!;
    expect(snap.books[0]!.book_id).toBe("B0");
    expect(snap.books[0]!.book_info!.read_effect).toBe("얻는 것");
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
      content_score: 0.6,
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
        abstract: "초록".repeat(1000),
        summary: "요약",
        introduction: "소개",
        references: Array.from({ length: 40 }, (_, i) => `참고 ${i}`),
      },
    };
    const snap = slimPaperResult({ query: "딥러닝", books: [paper] })!;
    expect(snap.query).toBe("딥러닝");
    const item = snap.books[0]!;
    // 관련도 알약의 팝오버(제목·내용 일치율)가 그리는 값이라 복원 뒤에도 보이게 싣는다
    expect(item).toMatchObject({ best_score: 0.7, title_score: 0.5, content_score: 0.6 });
    expect(item.chunks).toEqual([]);
    expect(item.book_info).toMatchObject({
      title: "논문",
      grade: "KCI 등재",
      series_title: "학술지",
      kci_citations: 12,
      corporate_author: "학회",
    });
    // 초록은 AI 요약이 읽는 앞쪽 논문에만 잘라 싣는다(아래 '요약 발췌') — 초록이 넉넉하면 색인 요약은, 소개는 늘 싣지 않는다
    expect(item.book_info!.abstract).toHaveLength(SNAPSHOT_EXCERPT_MAX_CHARS);
    expect(item.book_info).not.toHaveProperty("summary");
    expect(item.book_info).not.toHaveProperty("introduction");
    expect(item.book_info!.references).toHaveLength(SNAPSHOT_MAX_REFERENCES);
  });

  // 요약을 끝내기 전에 떠났거나 요약이 실패한 기록은 다시 열 때(applyPaperEntry)·[다시 시도] 때 스냅샷으로 요약을 다시 만든다 —
  // 새 검색 때와 같은 발췌(초록, 없거나 짧으면 색인 요약 본문)를 읽어야 한다
  describe("요약 발췌 — AI 요약이 읽는 앞 5편", () => {
    const withInfo = (i: number, info: ExcerptInfo) => ({ book_id: `P${i}`, best_score: 1 - i / 100, chunks: [], book_info: { title: `논문 ${i}`, ...info } });
    // 짧은 초록 기준보다 긴 초록 — 색인 요약을 덧붙이지 않는다
    const longAbstract = (i: number) => `초록 ${i} ` + "가".repeat(SHORT_ABSTRACT_CHARS);
    // 서버(app/services/search/paper_summary.py)가 발췌를 자르는 길이
    const serverCap = Number(
      /^_MAX_EXCERPT_CHARS = (\d+)/m.exec(readFileSync(resolve(__dirname, "../../../app/services/search/paper_summary.py"), "utf-8"))?.[1],
    );
    // 짝 없는 서로게이트 — 서버가 UTF-8 로 재다 500 을 낸다(app/api/history.py _json_bytes)
    const LONE_SURROGATE = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;

    it("앞 5편만 고른 발췌를 같은 필드 이름으로 싣고, 6번째부터는 싣지 않는다", () => {
      const books = Array.from({ length: 8 }, (_, i) => withInfo(i, { abstract: longAbstract(i), summary: `요약 ${i}` }));
      const snap = slimPaperResult({ query: "q", books })!;
      expect(snap.books.slice(0, SUMMARY_PAPER_LIMIT).map((b) => b.book_info!.abstract)).toEqual([0, 1, 2, 3, 4].map(longAbstract));
      expect(snap.books.every((b) => !("summary" in b.book_info!))).toBe(true);
      expect(snap.books.slice(SUMMARY_PAPER_LIMIT).every((b) => !("abstract" in b.book_info!))).toBe(true);
    });

    it("초록이 짧아 색인 요약 본문을 덧붙인 논문은 둘 다 싣는다 — 복원한 기록도 같은 발췌를 만든다", () => {
      const legacy = "## SUMMARY: 30개 연구 중 28개가 효과적이었다.\n**관련 연구자가 검색할 학술 키워드:** 노인, 우울";
      const books = [withInfo(0, { abstract: "This study examines social support.", summary: legacy })];
      const snap = slimPaperResult({ query: "q", books })!;
      expect(snap.books[0]!.book_info).toMatchObject({ abstract: "This study examines social support.", summary: "30개 연구 중 28개가 효과적이었다." });
      expect(summaryExcerpt(snap.books[0]!)).toBe(summaryExcerpt(books[0]!));
    });

    it("국문 초록 뒤의 영문 초록은 걷어 싣는다", () => {
      const korean = "본 연구는 노인의 사회적 지지와 우울의 관계를 분석하였다. ".repeat(14).trim();
      expect(korean.length).toBeGreaterThanOrEqual(SHORT_ABSTRACT_CHARS);
      const books = [withInfo(0, { abstract: `${korean}\n\n##### ABSTRACT\n\nThis study analyzed social support and depression.` })];
      const snap = slimPaperResult({ query: "q", books })!;
      expect(snap.books[0]!.book_info!.abstract).toBe(korean);
      expect(summaryExcerpt(snap.books[0]!)).toBe(summaryExcerpt(books[0]!));
    });

    it("초록이 없는 논문은 색인 요약의 본문을 summary 로 싣는다 — 복원한 기록도 새 검색과 같은 발췌를 고른다", () => {
      const legacy = "## SUMMARY: 다문화가정 아동의 어휘 발달.\n**관련 연구자가 검색할 학술 키워드:** 다문화, 어휘";
      const books = [withInfo(0, { abstract: "", summary: legacy }), withInfo(1, { abstract: "Original abstract." }), withInfo(2, {})];
      const snap = slimPaperResult({ query: "q", books })!;
      expect(snap.books[0]!.book_info).toMatchObject({ summary: "다문화가정 아동의 어휘 발달." });
      expect(snap.books[0]!.book_info).not.toHaveProperty("abstract");
      expect(snap.books[2]!.book_info).not.toHaveProperty("abstract");
      expect(snap.books[2]!.book_info).not.toHaveProperty("summary");
      expect(snap.books.map(summaryExcerpt)).toEqual(books.map(summaryExcerpt));
    });

    it("긴 초록은 서버가 자르는 길이(_MAX_EXCERPT_CHARS)보다 넉넉히 잘라 담는다 — 복원 뒤 요약도 같은 앞부분을 읽는다", () => {
      const abstract = "가나다라마바 ".repeat(300);
      const snap = slimPaperResult({ query: "q", books: [withInfo(0, { abstract })] })!;
      expect(snap.books[0]!.book_info!.abstract).toHaveLength(SNAPSHOT_EXCERPT_MAX_CHARS);
      const kept = summaryExcerpt(snap.books[0]!);
      // 서버는 앞머리 표지를 걷고 한 글자 더 보아 문장 경계를 찾는다 — 그만큼 넉넉해야 같은 자리에서 자른다
      expect(serverCap).toBeGreaterThan(0);
      expect(SNAPSHOT_EXCERPT_MAX_CHARS).toBeGreaterThanOrEqual(serverCap + 100);
      expect(kept.slice(0, serverCap + 1)).toBe(summaryExcerpt({ book_info: { abstract } }).slice(0, serverCap + 1));
    });

    // PDF 초록의 수학 이탤릭(𝑝·𝛽)·확장 한자·이모지는 서로게이트 쌍이다 — 코드 단위로 자르면 짝 없는 반쪽이 남아 기록 저장이
    // 서버에서 500 으로 끝나고, 편지함이 그 편지에 막혀 기록 동기화가 멈췄다
    it("BMP 밖 글자가 자르는 자리에 걸려도 서로게이트 쌍을 가르지 않는다", () => {
      for (const at of [SNAPSHOT_EXCERPT_MAX_CHARS - 1, SNAPSHOT_EXCERPT_MAX_CHARS]) {
        const abstract = "가".repeat(at) + "\u{1D45D} 값이 유의했다. \u{1D6FD}=.448";
        const snap = slimPaperResult({ query: "q", books: [withInfo(0, { abstract })] })!;
        const kept = snap.books[0]!.book_info!.abstract!;
        expect(Array.from(kept)).toHaveLength(SNAPSHOT_EXCERPT_MAX_CHARS);
        expect(LONE_SURROGATE.test(kept), `${at}`).toBe(false);
        expect(LONE_SURROGATE.test(JSON.stringify(snap)), `${at}`).toBe(false);
      }
      // 색인 요약 본문도 같은 규칙으로 자른다
      const summary = "나".repeat(SNAPSHOT_EXCERPT_MAX_CHARS - 1) + "\u{20000}끝";
      const snap = slimPaperResult({ query: "q", books: [withInfo(0, { summary })] })!;
      expect(snap.books[0]!.book_info!.summary).toBe("나".repeat(SNAPSHOT_EXCERPT_MAX_CHARS - 1) + "\u{20000}");
    });
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

  it(`검색이 돌려준 논문은 20편을 넘어도 모두 남긴다 — 둘째 쪽 이후 카드도 돌아와 찾는다`, () => {
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

// 복원 화면(주소의 h=)은 이 스냅샷으로 결과 카드를 그린다 — 카드가 읽는 book_info 필드가 목록에서 빠지면 그 칩·줄이 복원 때만 사라진다(재발 방지)
describe("스냅샷 필드 목록 — 결과 카드가 읽는 필드를 모두 담는다", () => {
  /** 함수가 info 에서 읽은 속성 이름을 모은다 */
  function readFields(run: (info: Record<string, unknown>) => unknown): Set<string> {
    const seen = new Set<string>();
    const info = new Proxy({} as Record<string, unknown>, {
      get(_target, key) {
        seen.add(String(key));
        return undefined;
      },
    });
    run(info);
    return seen;
  }

  // ResultCard.vue 가 템플릿에서 직접 읽는 필드(제목·표지 id)와 그 밖의 화면(참고 목록·AI 인용)이 읽는 필드
  const TEMPLATE_FIELDS = ["title", "cnts_id"];

  it("소장자료 카드가 읽는 필드(키워드·서지·분류·제목)가 BOOK_INFO_FIELDS 에 모두 있다", () => {
    const read = new Set([
      ...readFields((info) => cardKeywords(info as never)),
      ...readFields((info) => cardMeta(info as never, "book")),
      ...readFields((info) => kdcChip(info.kdc as never)),
      ...TEMPLATE_FIELDS,
    ]);
    const missing = [...read].filter((f) => !(BOOK_INFO_FIELDS as readonly string[]).includes(f));
    expect(missing).toEqual([]);
  });

  it("논문 카드가 읽는 필드(키워드·서지·등급·인용수·제목)가 PAPER_INFO_FIELDS 에 모두 있다", () => {
    const read = new Set([
      ...readFields((info) => cardKeywords(info as never)),
      ...readFields((info) => cardMeta(info as never, "paper")),
      ...TEMPLATE_FIELDS,
    ]);
    // 논문 카드의 서지 줄은 발행처(publisher)를 읽지 않는다 — 소장자료 전용
    read.delete("publisher");
    const missing = [...read].filter((f) => !(PAPER_INFO_FIELDS as readonly string[]).includes(f));
    expect(missing).toEqual([]);
  });

  it("측정이 실제로 필드를 읽고 있다(빈 집합이면 위 두 검사가 아무것도 지키지 못한다)", () => {
    const read = readFields((info) => cardMeta(info as never, "book"));
    expect(read.has("personal_author")).toBe(true);
    expect(read.has("publisher")).toBe(true);
    expect(readFields((info) => cardKeywords(info as never)).has("extracted_keywords")).toBe(true);
  });

  it("논문 키워드 칩이 스냅샷을 거친 뒤에도 같다(저자 키워드 → keyword → themes → subject)", () => {
    const paper = (info: Record<string, unknown>) => ({ book_id: "P1", best_score: 0.5, chunks: [], book_info: info });
    const snapOf = (info: Record<string, unknown>) => slimPaperResult({ query: "q", books: [paper(info)] })!.books[0]!.book_info!;
    const full = { extracted_keywords: ["노인복지", "정서복지", "첨단기술", "감정적 고립"], keyword: "노인복지, 정서복지", themes: "가, 나", subject: "다" };
    expect(cardKeywords(snapOf(full))).toEqual(cardKeywords(full));
    expect(cardKeywords(snapOf({ keyword: "스마트폰 중독, 고립감" }))).toEqual(["스마트폰 중독", "고립감"]);
    expect(cardKeywords(snapOf({ themes: "일, 이, 삼, 사" }))).toEqual(["일", "이", "삼"]);
  });

  it("소장자료의 분류(kdc)·저자 키워드가 스냅샷에 남아 복원 때 분류 칩이 나온다", () => {
    const b = serverBook(1);
    const snap = slimBookResult({
      query: "q",
      books: [{ ...b, book_info: { ...b.book_info, themes: null, extracted_keywords: [], kdc: "329", publisher: "기획예산처" } }],
    })!;
    const info = snap.books[0]!.book_info!;
    expect(info.kdc).toBe("329");
    expect(kdcChip(info.kdc)?.name).toBe("재정");
    expect(cardKeywords(info)).toEqual([]);
    expect(info).not.toHaveProperty("extracted_keywords");
    const withKw = slimBookResult({ query: "q", books: [{ ...b, book_info: { ...b.book_info, extracted_keywords: ["a", "b"] } }] })!;
    expect(withKw.books[0]!.book_info!.extracted_keywords).toEqual(["a", "b"]);
  });

  it("옛 기록(키워드·분류 필드가 없는 스냅샷)은 칩 없이 오류 없이 그려진다", () => {
    const old = { title: "옛 기록", personal_author: "저자", pub_date: "2001" };
    expect(cardKeywords(old)).toEqual([]);
    expect(kdcChip((old as { kdc?: string }).kdc)).toBeNull();
    expect(cardMeta(old, "book").author).toBe("저자");
  });

  it("복원 항목에도 관련도(종합·제목·내용 점수)가 남는다", () => {
    const snap = slimPaperResult({ query: "q", books: [{ book_id: "P1", best_score: 0.7, title_score: 0.5, content_score: 0.6, chunks: [], book_info: { title: "t" } }] })!;
    expect(snap.books[0]).toMatchObject({ best_score: 0.7, title_score: 0.5, content_score: 0.6 });
    const book = slimBookResult({ query: "q", books: [serverBook(1)] })!;
    expect(book.books[0]).toMatchObject({ best_score: 0.9, title_score: 0.8, content_score: 0.7 });
  });

  it("논문 180KB 상한에서 키워드를 더해 넘치면 키워드·서지는 두고 뒤쪽 논문의 참고문헌부터 뺀다", () => {
    const books = Array.from({ length: 60 }, (_, i) => ({
      book_id: `P${i}`,
      best_score: 1 - i / 100,
      chunks: [],
      book_info: {
        cnts_id: `P${i}`,
        title: `논문 ${i}`,
        personal_author: "김",
        corporate_author: "학회",
        pub_date: "2021.03",
        series_title: "학술지",
        grade: "KCI 등재",
        kci_citations: 3,
        extracted_keywords: Array.from({ length: 8 }, (_, k) => `키워드${k}`),
        keyword: Array.from({ length: 8 }, (_, k) => `키워드${k}`).join(", "),
        themes: Array.from({ length: 10 }, (_, k) => `주제어${k}`).join(", "),
        subject: "주제",
        references: Array.from({ length: 40 }, () => "참고문헌".repeat(25)),
      },
    }));
    const snap = slimPaperResult({ query: "q", books })!;
    expect(snap.books).toHaveLength(60);
    expect(utf8Bytes(snap) + separators(snap)).toBeLessThanOrEqual(200 * 1024);
    // 키워드는 모든 논문에 남는다 — 상한 때문에 칩이 사라지지 않는다
    expect(snap.books.every((b) => b.book_info!.extracted_keywords?.length === 8)).toBe(true);
    expect(snap.books.every((b) => b.book_info!.themes && b.book_info!.keyword && b.book_info!.grade)).toBe(true);
    // 참고문헌은 앞쪽 논문은 그대로, 뒤쪽 논문부터 뺀다(기존 순서 그대로)
    const cut = snap.books.findIndex((b) => !b.book_info!.references);
    expect(cut).toBeGreaterThan(0);
    expect(snap.books.slice(0, cut).every((b) => !!b.book_info!.references)).toBe(true);
    expect(snap.books.slice(cut).every((b) => !b.book_info!.references)).toBe(true);
    // 마지막으로 뺀 논문의 참고문헌을 되돌리면 상한을 넘는다 — 필요한 만큼만 뺐다
    snap.books[cut]!.book_info!.references = snap.books[0]!.book_info!.references;
    expect(utf8Bytes(snap)).toBeGreaterThan(PAPER_SNAPSHOT_MAX_BYTES);
  });
});
