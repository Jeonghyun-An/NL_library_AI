// frontend/tests/unit/aiStream.test.ts
// AI 글 스트림 읽기 — 논문 검색 AI 요약·논문 상세 AI 요약·관련 논문 추천 사유·소장자료 상세 추천 이유가 함께 쓴다.
// 서버는 LLM 호출이 실패하면 [DONE] 바로 앞에 {error: 문구} 를 보낸다(app/services/search/paper_summary.py·pipeline.py)
import { describe, expect, it, vi } from "vitest";
import { failureText, readAiStream } from "~/utils/aiStream";

const enc = new TextEncoder();

// parts 를 한 조각씩 흘리는 응답 — 읽기가 취소되면 cancelled 로 알린다
function responseOf(parts: string[], init: ResponseInit = { status: 200 }) {
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
  return { resp: new Response(body, init), cancelled: () => cancelled };
}

const ev = (o: unknown) => `data: ${JSON.stringify(o)}\n\n`;
const DONE = "data: [DONE]\n\n";

describe("readAiStream", () => {
  it("이벤트를 차례로 넘기고 [DONE] 에서 끝까지 받았다고 알린다", async () => {
    const onEvent = vi.fn();
    const sources = [{ num: 1, book_id: "KCI_1" }];
    const { resp } = responseOf([ev({ keywords: ["k"] }), ev({ text: "요약" }), ev({ sources }), DONE]);
    expect(await readAiStream(resp, onEvent)).toEqual({ ok: true });
    expect(onEvent.mock.calls.map((c) => c[0])).toEqual([{ keywords: ["k"] }, { text: "요약" }, { sources }]);
  });

  it("한 줄이 조각 경계에 걸쳐도 읽고, data: 가 아닌 줄·깨진 JSON·객체가 아닌 값은 버린다", async () => {
    const onEvent = vi.fn();
    const line = ev({ text: "나뉜 줄" });
    const { resp } = responseOf([": keep-alive\n", "data: {broken\n\n", "data: 3\n\n", line.slice(0, 9), line.slice(9), DONE]);
    expect(await readAiStream(resp, onEvent)).toEqual({ ok: true });
    expect(onEvent.mock.calls.map((c) => c[0])).toEqual([{ text: "나뉜 줄" }]);
  });

  it("{error} 가 오면 서버 문구와 함께 실패로 알리고 읽기를 그만둔다 — 뒤의 글·[DONE] 은 넘기지 않는다", async () => {
    const onEvent = vi.fn();
    const { resp, cancelled } = responseOf([
      ev({ text: "받다 만 " }),
      ev({ error: "AI 요약을 만들지 못했습니다" }),
      ev({ text: "뒤" }),
      DONE,
    ]);
    expect(await readAiStream(resp, onEvent)).toEqual({ ok: false, error: "AI 요약을 만들지 못했습니다" });
    expect(onEvent.mock.calls.map((c) => c[0])).toEqual([{ text: "받다 만 " }]);
    expect(cancelled()).toBe(true);
  });

  it("{error} 의 문구가 비었거나 글이 아니면 문구 없는 실패다", async () => {
    for (const error of ["", "  ", true, null, 3]) {
      const { resp } = responseOf([ev({ error }), DONE]);
      expect(await readAiStream(resp, vi.fn())).toEqual({ ok: false, error: null });
    }
  });

  it("[DONE] 없이 끊기면 문구 없는 실패다 — 받은 글은 넘긴 그대로다", async () => {
    const onEvent = vi.fn();
    const { resp } = responseOf([ev({ text: "중간" })]);
    expect(await readAiStream(resp, onEvent)).toEqual({ ok: false, error: null });
    expect(onEvent).toHaveBeenCalledWith({ text: "중간" });
  });

  it("4xx·5xx 응답은 본문을 읽지 않고 문구 없는 실패다", async () => {
    const onEvent = vi.fn();
    const { resp } = responseOf([ev({ text: "오류 본문" }), DONE], { status: 503 });
    expect(await readAiStream(resp, onEvent)).toEqual({ ok: false, error: null });
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("읽는 중 끊김(abort 등)은 그대로 던진다 — 부르는 쪽이 signal 로 가린다", async () => {
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(enc.encode(ev({ text: "앞" })));
        c.error(new DOMException("aborted", "AbortError"));
      },
    });
    await expect(readAiStream(new Response(body), vi.fn())).rejects.toThrow("aborted");
  });
});

describe("failureText", () => {
  it("끝까지 받았으면 빈 글, 실패면 서버 문구 — 없으면 화면이 정한 문구", () => {
    expect(failureText({ ok: true }, "기본")).toBe("");
    expect(failureText({ ok: false, error: "서버 문구" }, "기본")).toBe("서버 문구");
    expect(failureText({ ok: false, error: null }, "기본")).toBe("기본");
  });
});
