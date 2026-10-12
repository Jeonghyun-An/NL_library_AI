// frontend/tests/unit/bookAiPick.test.ts
import { describe, expect, it, vi } from "vitest";
import {
  REASON_CHUNK_LIMIT,
  buildBookAi,
  buildReasonBody,
  pickTopBook,
  readEffectOf,
  readReasonStream,
  readSavedReason,
} from "~/utils/bookAiPick";

function book(id: string, over: Record<string, unknown> = {}) {
  return { book_id: id, best_score: 0.5, chunks: [], ...over };
}

describe("pickTopBook — 1위 도서", () => {
  it("검색이 준 순서의 맨 앞을 고른다(재정렬 없음)", () => {
    expect(pickTopBook([book("A", { best_score: 0.1 }), book("B", { best_score: 0.9 })])?.book_id).toBe("A");
  });

  it("book_id 가 없는 앞 항목은 건너뛴다", () => {
    expect(pickTopBook([{ best_score: 1 }, { book_id: "", best_score: 1 }, book("C")])?.book_id).toBe("C");
  });

  it("결과가 없거나 목록이 아니면 null", () => {
    expect(pickTopBook([])).toBeNull();
    expect(pickTopBook(null)).toBeNull();
    expect(pickTopBook(undefined)).toBeNull();
  });
});

describe("readEffectOf — 이 책에서 얻을 수 있는 것", () => {
  it("book_info.read_effect 를 앞뒤 공백 없이 준다", () => {
    expect(readEffectOf({ book_info: { read_effect: "  읽으면 좋다.\n" } })).toBe("읽으면 좋다.");
  });

  it("비었거나 없으면 빈 문자열 — 화면이 블록을 숨긴다", () => {
    expect(readEffectOf({ book_info: { read_effect: "   " } })).toBe("");
    expect(readEffectOf({ book_info: { read_effect: null } })).toBe("");
    expect(readEffectOf({ book_info: {} })).toBe("");
    expect(readEffectOf({})).toBe("");
    expect(readEffectOf(null)).toBe("");
  });
});

describe("buildReasonBody — /books/reason/stream 요청 본문", () => {
  it("검색어(앞뒤 공백 제거)와 도서 id 를 싣는다 — 고쳐 쓴 검색어는 비운다", () => {
    // 고쳐 쓴 검색어는 키워드 나열이라 서버가 이유 글에 그대로 따다 쓴다(운영 확인 2026-10-12). 원문 검색어만 보낸다
    const body = buildReasonBody("  조선 소설  ", book("B1"));
    expect(body).toEqual({
      query: "조선 소설",
      rewritten_query: "",
      book_id: "B1",
      chunk_texts: [],
    });
  });

  it("매칭 구절은 rerank_score(없으면 score) 높은 순으로 상위 REASON_CHUNK_LIMIT 개만", () => {
    const chunks = Array.from({ length: REASON_CHUNK_LIMIT + 5 }, (_, i) => ({
      text: `c${i}`,
      score: i / 100,
    }));
    chunks.push({ text: "rerank-best", score: 0, rerank_score: 5 } as never);
    const body = buildReasonBody("q", book("B1", { chunks }));
    expect(body.chunk_texts).toHaveLength(REASON_CHUNK_LIMIT);
    expect(body.chunk_texts[0]).toBe("rerank-best");
    expect(body.chunk_texts[1]).toBe(`c${REASON_CHUNK_LIMIT + 4}`);
  });

  it("구절이 없는 복원 도서도 만든다(서버가 요약·줄거리로 쓴다)", () => {
    expect(buildReasonBody("q", { book_id: "B1" }).chunk_texts).toEqual([]);
  });

  it("원본 chunks 배열을 바꾸지 않는다", () => {
    const chunks = [
      { text: "a", score: 0.1 },
      { text: "b", score: 0.9 },
    ];
    buildReasonBody("q", book("B1", { chunks }));
    expect(chunks.map((c) => c.text)).toEqual(["a", "b"]);
  });
});

describe("buildBookAi · readSavedReason — 기록의 AI 영역", () => {
  it("끝난 추천 이유를 1위 도서 id 와 함께 담는다(앞뒤 공백 제거)", () => {
    expect(buildBookAi("B1", "\n이유입니다.\n\n")).toEqual({ book_id: "B1", reason: "이유입니다." });
  });

  it("새 모양은 1위 도서가 같을 때 저장된 이유를 그대로 준다", () => {
    expect(readSavedReason({ book_id: "B1", reason: "이유" }, "B1")).toBe("이유");
  });

  it("1위 도서가 달라졌으면(옛 결과와 어긋남) 쓰지 않는다", () => {
    expect(readSavedReason({ book_id: "B1", reason: "이유" }, "B2")).toBeNull();
    expect(readSavedReason({ book_id: "B1", reason: "이유" }, null)).toBeNull();
  });

  it("옛 AI 컬렉션 기록({intro, items})은 이유가 없는 것으로 본다 — 깨지지 않는다", () => {
    const legacy = { intro: "소개", items: [{ book_id: "B1", reason: "이유" }] };
    expect(readSavedReason(legacy, "B1")).toBeNull();
  });

  it("없거나 모양이 틀린 값도 null", () => {
    expect(readSavedReason(undefined, "B1")).toBeNull();
    expect(readSavedReason(null, "B1")).toBeNull();
    expect(readSavedReason("text", "B1")).toBeNull();
    expect(readSavedReason([], "B1")).toBeNull();
    expect(readSavedReason({ book_id: "B1" }, "B1")).toBeNull();
    expect(readSavedReason({ book_id: "B1", reason: 3 }, "B1")).toBeNull();
    expect(readSavedReason({ book_id: "B1", reason: "  " }, "B1")).toBeNull();
  });
});

function streamOf(parts: string[]): { body: ReadableStream<Uint8Array>; cancelled: () => boolean } {
  const enc = new TextEncoder();
  let i = 0;
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < parts.length) controller.enqueue(enc.encode(parts[i++]));
      else controller.close();
    },
    cancel() {
      cancelled = true;
    },
  });
  return { body, cancelled: () => cancelled };
}

const ev = (o: unknown) => `data: ${JSON.stringify(o)}\n\n`;

describe("readReasonStream — 추천 이유 SSE 읽기", () => {
  it("text 이벤트를 이어 붙이고 [DONE] 에서 끝났다고 알린다", async () => {
    const onText = vi.fn();
    const { body } = streamOf([ev({ keywords: ["k"] }), ev({ text: "이 책은" }), ev({ text: " 좋다." }), "data: [DONE]\n\n"]);
    const complete = await readReasonStream(body, onText);
    expect(complete).toBe(true);
    expect(onText.mock.calls.map((c) => c[0])).toEqual(["이 책은", " 좋다."]);
  });

  it("한 줄이 청크 경계에 걸쳐도 읽는다", async () => {
    const onText = vi.fn();
    const line = ev({ text: "나뉜 줄" });
    const { body } = streamOf([line.slice(0, 9), line.slice(9), "data: [DONE]\n\n"]);
    await readReasonStream(body, onText);
    expect(onText.mock.calls.map((c) => c[0])).toEqual(["나뉜 줄"]);
  });

  it("effect 이벤트가 오면 이유는 끝난 것이다 — 연결을 끊고(읽기 취소) 끝났다고 알린다", async () => {
    const onText = vi.fn();
    const { body, cancelled } = streamOf([ev({ text: "이유" }), ev({ effect: "독후 효과" }), ev({ effect: "더" }), "data: [DONE]\n\n"]);
    const complete = await readReasonStream(body, onText);
    expect(complete).toBe(true);
    expect(onText.mock.calls.map((c) => c[0])).toEqual(["이유"]);
    expect(cancelled()).toBe(true);
  });

  it("[DONE] 없이 끊기면 끝나지 않았다고 알린다", async () => {
    const onText = vi.fn();
    const { body } = streamOf([ev({ text: "중간" })]);
    expect(await readReasonStream(body, onText)).toBe(false);
    expect(onText).toHaveBeenCalledWith("중간");
  });

  it("깨진 줄·text 가 아닌 값은 건너뛴다", async () => {
    const onText = vi.fn();
    const { body } = streamOf(["data: {broken\n\n", ev({ text: 3 }), ev({ text: "" }), ev({ text: "정상" }), "data: [DONE]\n\n"]);
    expect(await readReasonStream(body, onText)).toBe(true);
    expect(onText.mock.calls.map((c) => c[0])).toEqual(["정상"]);
  });
});
