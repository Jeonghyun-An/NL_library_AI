// frontend/tests/unit/useDeepReadChat.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { useDeepReadChat } from "~/composables/useDeepReadChat";
import { CODE_MESSAGES, ERROR_HINTS } from "~/utils/apiErrors";
import {
  CHAT_ANSWER_FAILED,
  CHAT_ERROR_TEXT,
  CHAT_IDLE_TIMEOUT_MS,
  CHAT_STOPPED_EMPTY,
  CHAT_STOPPED_TEXT,
  type DeepReadMessage,
  LEGACY_NOT_FOUND_TEXT,
} from "~/utils/deepReadSse";

// useApi 는 Nuxt 런타임 설정을 읽는다 — 여기서는 주소 조립만 흉내 낸다(usePdfOpener.test 와 같다)
vi.mock("~/composables/useApi", () => ({
  apiUrl: (path: string) => `/api${path}`,
  apiHeaders: (extra: Record<string, string> = {}) => ({ ...extra, "x-session-id": "sid" }),
}));

// 스트림을 손으로 흘리는 fetch — 부를 때마다 새 본문을 만들고, signal 이 abort 되면 진짜 fetch 처럼 본문을 AbortError 로 끊는다
function streamFetch() {
  const enc = new TextEncoder();
  const calls: { url: string; init: RequestInit }[] = [];
  let ctl: ReadableStreamDefaultController<Uint8Array> | null = null;
  const fetchFn = vi.fn((url: string, init: RequestInit) => {
    calls.push({ url, init });
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        ctl = c;
      },
    });
    const stream = ctl!;
    init.signal?.addEventListener("abort", () => stream.error(new DOMException("aborted", "AbortError")));
    return Promise.resolve(new Response(body, { status: 200 }));
  });
  return {
    fetchFn: fetchFn as unknown as typeof fetch,
    calls,
    push: (text: string) => ctl!.enqueue(enc.encode(text)),
    end: () => ctl!.close(),
  };
}

// 스트림 읽기는 여러 마이크로태스크를 건넌다 — 한 차례 매크로태스크까지 비운다
const flush = () => new Promise<void>((r) => setTimeout(r, 0));

function setup(opts: { id?: string; store?: Map<string, DeepReadMessage[]>; fetchFn?: typeof fetch } = {}) {
  const net = streamFetch();
  const id = ref(opts.id ?? "KCI_1");
  const scope = effectScope();
  const chat = scope.run(() =>
    useDeepReadChat({ cntsId: () => id.value, store: () => opts.store, fetchFn: opts.fetchFn ?? net.fetchFn }),
  )!;
  return { ...net, id, scope, chat };
}

describe("useDeepReadChat", () => {
  it("보낸 질문과 그 앞 대화를 history 로 싣는다", async () => {
    const { chat, calls, push, end } = setup();
    const first = chat.send("  이 논문의 대상은?  ");
    await flush();
    push('data: {"text": "노인 300명입니다."}\n\ndata: [DONE]\n\n');
    end();
    await first;

    const second = chat.send("방법은?");
    await flush();
    expect(calls).toHaveLength(2);
    const { url, init } = calls[1]!;
    expect(url).toBe("/api/books/chat/KCI_1");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json", "x-session-id": "sid" });
    expect(init.signal).toBeInstanceOf(AbortSignal);
    expect(JSON.parse(String(init.body))).toEqual({
      message: "방법은?",
      history: [
        { role: "user", content: "이 논문의 대상은?" },
        { role: "assistant", content: "노인 300명입니다." },
      ],
    });
    // 답을 받는 동안 또 보내면 무시한다
    await chat.send("셋째 질문");
    expect(calls).toHaveLength(2);
    chat.stop();
    await second;
  });

  it("흐른 글을 모아 두었다가 끝나면 출처와 함께 답 메시지가 된다", async () => {
    const { chat, push, end } = setup();
    const sent = chat.send("결론은?");
    await flush();
    expect(chat.isStreaming.value).toBe(true);
    expect(chat.messages.value).toEqual([{ role: "user", content: "결론은?" }]);

    push('data: {"text": "가족 지지가"}\n\n');
    await flush();
    expect(chat.streamingText.value).toBe("가족 지지가");

    const sources = [{ page_start: 5, page_end: 5, text: "가족 지지가 높을수록 우울이 낮았다." }];
    push(`data: {"text": " 우울을 낮춘다(p.5)."}\n\ndata: ${JSON.stringify({ sources })}\n\ndata: [DONE]\n\n`);
    end();
    await sent;
    expect(chat.messages.value).toEqual([
      { role: "user", content: "결론은?" },
      { role: "assistant", content: "가족 지지가 우울을 낮춘다(p.5).", sources },
    ]);
    expect(chat.streamingText.value).toBe("");
    expect(chat.isStreaming.value).toBe(false);
  });

  it("응답 오류(5xx)·네트워크 오류면 질문을 대화에서 빼고 '답을 받지 못했어요 — 이유'로 알린다 — 오류 문구를 답으로 남기지 않는다", async () => {
    const failing = vi.fn().mockResolvedValue(new Response("<html>502 Bad Gateway</html>", { status: 502 }));
    const { chat } = setup({ fetchFn: failing as unknown as typeof fetch });
    await chat.send("질문");
    expect(chat.messages.value).toEqual([]);
    expect(chat.failure.value).toEqual({
      question: "질문",
      message: `${CHAT_ERROR_TEXT} — ${ERROR_HINTS.server}`,
      retryable: true,
      partial: "",
    });
    expect(chat.isStreaming.value).toBe(false);

    const offline = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const other = setup({ fetchFn: offline as unknown as typeof fetch });
    await other.chat.send("질문");
    expect(other.chat.messages.value).toEqual([]);
    expect(other.chat.failure.value).toEqual({
      question: "질문",
      message: `${CHAT_ERROR_TEXT} — ${ERROR_HINTS.network}`,
      retryable: true,
      partial: "",
    });
  });

  // 서버 BookChatRequest.message 는 max_length=2000 — 넘으면 FastAPI 가 422(string_too_long) 를 돌려준다
  it("422(질문이 너무 김)는 한도를 이유로 알리고, 같은 질문을 다시 보내도 같은 실패라 retry 가 다시 보내지 않는다", async () => {
    const detail = [{ type: "string_too_long", loc: ["body", "message"], msg: "String should have at most 2000 characters", ctx: { max_length: 2000 } }];
    const invalid = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status: 422 }));
    const { chat } = setup({ fetchFn: invalid as unknown as typeof fetch });
    await chat.send("아주 긴 질문");
    expect(chat.messages.value).toEqual([]);
    expect(chat.failure.value).toEqual({
      question: "아주 긴 질문",
      message: "2000자까지 입력할 수 있어요",
      retryable: false,
      partial: "",
    });
    await chat.retry();
    expect(invalid).toHaveBeenCalledTimes(1);
    expect(chat.failure.value).not.toBeNull();
  });

  // 서버(app/services/chat/book_chat.py)는 LLM 호출이 실패하면 [DONE] 바로 앞에 {error} 를 보낸다(code 없음).
  // 받던 글은 실패 안내(failure.partial)에만 둔다 — 다른 AI 글 화면처럼 읽던 글이 실패 순간 사라지지 않되 대화에는 남지 않는다
  it("{error} 가 오면 받던 글도 질문도 대화에 남기지 않고(받던 글은 failure.partial) 화면 문구로 실패를 알린다 — 다음 질문의 history 에 실리지 않는다", async () => {
    const store = new Map<string, DeepReadMessage[]>();
    const { chat, calls, push } = setup({ store });
    const first = chat.send("대상은?");
    await flush();
    push('data: {"text": "노인 300명입니다."}\n\ndata: [DONE]\n\n');
    await first;

    const second = chat.send("방법은?");
    await flush();
    push('data: {"text": "받다 만 "}\n\n');
    await flush();
    expect(chat.streamingText.value).toBe("받다 만 ");
    push('data: {"error": "답을 만들지 못했습니다"}\n\ndata: [DONE]\n\n');
    await second;
    const answered = [
      { role: "user", content: "대상은?" },
      { role: "assistant", content: "노인 300명입니다." },
    ];
    expect(store.get("KCI_1")).toEqual(answered);
    // 서버 문구('…습니다')가 아니라 화면의 해요체 문구
    expect(chat.failure.value).toEqual({ question: "방법은?", message: CHAT_ANSWER_FAILED, retryable: true, partial: "받다 만 " });
    expect(chat.streamingText.value).toBe("");
    expect(chat.isStreaming.value).toBe(false);

    // 새 질문을 보내면 실패 안내는 걷히고, history 에는 실패한 질문·오류가 없다
    const third = chat.send("결론은?");
    await flush();
    expect(chat.failure.value).toBeNull();
    expect(JSON.parse(String(calls[2]!.init.body))).toEqual({ message: "결론은?", history: answered });
    chat.stop();
    await third;
  });

  it("{error} 의 문구가 비어도 화면 문구로, [DONE] 없이 끊겨도 실패로 알린다 — 받던 글을 답으로 남기지 않는다(failure.partial 에만)", async () => {
    const { chat, push } = setup();
    const sent = chat.send("질문");
    await flush();
    push('data: {"error": ""}\n\ndata: [DONE]\n\n');
    await sent;
    expect(chat.failure.value).toEqual({ question: "질문", message: CHAT_ANSWER_FAILED, retryable: true, partial: "" });

    const cut = setup();
    const again = cut.chat.send("질문");
    await flush();
    cut.push('data: {"text": "반쯤"}\n\n');
    await flush();
    cut.end();
    await again;
    expect(cut.chat.messages.value).toEqual([]);
    expect(cut.chat.failure.value).toEqual({ question: "질문", message: CHAT_ERROR_TEXT, retryable: true, partial: "반쯤" });
  });

  // 새 서버(eh/backend)는 실패의 갈래를 {error, code} 의 code 로 붙인다
  it("{error, code} 는 code 별 문구로 — 자료가 없으면(not_found) retryable 이 아니고 retry 가 다시 보내지 않는다", async () => {
    const { chat, calls, push } = setup();
    const sent = chat.send("질문");
    await flush();
    push('data: {"error": "자료 내용을 읽지 못했어요. 잠시 뒤 다시 시도해 주세요", "code": "retrieval_failed"}\n\ndata: [DONE]\n\n');
    await sent;
    expect(chat.failure.value).toEqual({ question: "질문", message: CODE_MESSAGES.retrieval_failed, retryable: true, partial: "" });

    const again = chat.retry();
    await flush();
    expect(calls).toHaveLength(2);
    push('data: {"error": "자료를 찾을 수 없어요", "code": "not_found"}\n\ndata: [DONE]\n\n');
    await again;
    expect(chat.failure.value).toEqual({ question: "질문", message: CODE_MESSAGES.not_found, retryable: false, partial: "" });
    await chat.retry();
    expect(calls).toHaveLength(2);
    expect(chat.messages.value).toEqual([]);
  });

  // 옛 서버(오류 code 배포 전)는 빈 답을 정상 [DONE] 으로 끝내고, 자료를 못 찾으면 '도서를 찾을 수 없습니다.' 를 보통 글로 보냈다
  it("옛 서버의 빈 답·'도서를 찾을 수 없습니다.' 는 [DONE] 으로 끝나도 실패다 — 대화·다음 질문의 history 에 남지 않는다", async () => {
    const { chat, calls, push } = setup();
    const empty = chat.send("질문");
    await flush();
    push('data: {"text": "  "}\n\ndata: [DONE]\n\n');
    await empty;
    expect(chat.messages.value).toEqual([]);
    expect(chat.failure.value).toEqual({ question: "질문", message: CODE_MESSAGES.empty_answer, retryable: true, partial: "" });

    const gone = chat.send("다시");
    await flush();
    push(`data: ${JSON.stringify({ text: LEGACY_NOT_FOUND_TEXT })}\n\ndata: [DONE]\n\n`);
    await gone;
    expect(chat.messages.value).toEqual([]);
    expect(chat.failure.value).toEqual({ question: "다시", message: CODE_MESSAGES.not_found, retryable: false, partial: "" });

    const next = chat.send("셋째");
    await flush();
    expect(JSON.parse(String(calls[2]!.init.body))).toEqual({ message: "셋째", history: [] });
    chat.stop();
    await next;
  });

  it("retry 는 실패한 질문을 그대로 다시 보낸다 — 실패가 없으면 아무것도 하지 않는다", async () => {
    const { chat, calls, push } = setup();
    const sent = chat.send("방법은?");
    await flush();
    push('data: {"error": "답을 만들지 못했습니다"}\n\ndata: [DONE]\n\n');
    await sent;
    expect(chat.failure.value?.retryable).toBe(true);

    const again = chat.retry();
    await flush();
    expect(calls).toHaveLength(2);
    expect(JSON.parse(String(calls[1]!.init.body))).toEqual({ message: "방법은?", history: [] });
    expect(chat.failure.value).toBeNull();
    expect(chat.messages.value).toEqual([{ role: "user", content: "방법은?" }]);
    push('data: {"text": "설문 조사입니다."}\n\ndata: [DONE]\n\n');
    await again;
    expect(chat.messages.value).toEqual([
      { role: "user", content: "방법은?" },
      { role: "assistant", content: "설문 조사입니다." },
    ]);

    await chat.retry();
    expect(calls).toHaveLength(2);
  });

  it("논문을 바꾸면 실패 안내를 걷는다 — 다른 논문의 대화 아래에 남지 않게", async () => {
    const { chat, id, push } = setup();
    const sent = chat.send("질문");
    await flush();
    push('data: {"error": "답을 만들지 못했습니다"}\n\ndata: [DONE]\n\n');
    await sent;
    expect(chat.failure.value).not.toBeNull();

    id.value = "KCI_2";
    await nextTick();
    expect(chat.failure.value).toBeNull();
  });

  it("cntsId 가 바뀌면 스트림을 끊고 받던 글을 그 논문 대화에 남긴 뒤 store 의 새 논문 대화로 바꾼다", async () => {
    const earlier: DeepReadMessage[] = [
      { role: "user", content: "이 논문은?" },
      { role: "assistant", content: "척도 타당화 연구입니다." },
    ];
    const store = new Map<string, DeepReadMessage[]>([["KCI_2", earlier]]);
    const { chat, id, calls, push } = setup({ store });
    const sent = chat.send("대상은?");
    await flush();
    push('data: {"text": "노인"}\n\n');
    await flush();

    id.value = "KCI_2";
    await nextTick();
    expect(calls[0]!.init.signal!.aborted).toBe(true);
    expect(chat.messages.value).toEqual(earlier);
    expect(chat.isStreaming.value).toBe(false);
    expect(chat.streamingText.value).toBe("");
    await sent;
    // 끊긴 답도 user/assistant 짝을 지켜 남는다(다음 질문의 history 가 어긋나지 않게)
    expect(store.get("KCI_1")).toEqual([
      { role: "user", content: "대상은?" },
      { role: "assistant", content: `노인\n\n${CHAT_STOPPED_TEXT}` },
    ]);

    // 앞 논문으로 돌아오면 store 의 그 논문 대화가 이어진다
    id.value = "KCI_1";
    await nextTick();
    expect(chat.messages.value).toEqual(store.get("KCI_1"));
  });

  it("store 가 없으면 논문을 바꿀 때 대화를 비운다", async () => {
    const { chat, id, push, end } = setup();
    const sent = chat.send("질문");
    await flush();
    push('data: {"text": "답"}\n\ndata: [DONE]\n\n');
    end();
    await sent;
    expect(chat.messages.value).toHaveLength(2);

    id.value = "KCI_9";
    await nextTick();
    expect(chat.messages.value).toEqual([]);
  });

  it("stop 은 fetch 의 signal 을 abort 하고 받은 글을 '멈췄습니다'와 남긴다 — 받은 글이 없으면 그 문구만", async () => {
    const { chat, calls, push } = setup();
    const first = chat.send("첫 질문");
    await flush();
    chat.stop();
    await first;
    expect(calls[0]!.init.signal!.aborted).toBe(true);
    expect(chat.messages.value.at(-1)).toEqual({ role: "assistant", content: CHAT_STOPPED_EMPTY });

    const second = chat.send("둘째 질문");
    await flush();
    push('data: {"text": "반쯤 받은 답"}\n\n');
    await flush();
    chat.stop();
    await second;
    expect(chat.messages.value.at(-1)).toEqual({ role: "assistant", content: `반쯤 받은 답\n\n${CHAT_STOPPED_TEXT}` });
    expect(chat.isStreaming.value).toBe(false);
    // 멈춘 뒤에 부른 stop 은 아무것도 하지 않는다
    chat.stop();
    expect(chat.messages.value).toHaveLength(4);
  });

  it("scope 가 끝나면(패널을 닫아 BookChat 이 내려가면) 스트림을 끊는다", async () => {
    const store = new Map<string, DeepReadMessage[]>();
    const { chat, scope, calls, push } = setup({ store });
    const sent = chat.send("질문");
    await flush();
    push('data: {"text": "받던 글"}\n\n');
    await flush();

    scope.stop();
    await sent;
    expect(calls[0]!.init.signal!.aborted).toBe(true);
    expect(store.get("KCI_1")).toEqual([
      { role: "user", content: "질문" },
      { role: "assistant", content: `받던 글\n\n${CHAT_STOPPED_TEXT}` },
    ]);
  });
});

// 시계만 가짜로 — 스트림 읽기는 마이크로태스크라 그대로 돈다. advanceTimersByTimeAsync 는 진짜 매크로태스크로 한 번씩 비켜 주어
// 읽기 사슬이 끝까지 흐른다(그래서 여기서는 setTimeout 을 쓰는 flush 대신 advance(0))
describe("useDeepReadChat — 오래 무응답이면 스스로 끊는다", () => {
  afterEach(() => vi.useRealTimers());
  const advance = (ms: number) => vi.advanceTimersByTimeAsync(ms);

  it(`응답 머리도 글도 ${CHAT_IDLE_TIMEOUT_MS / 1000}초 동안 오지 않으면 끊고 '응답이 늦어 멈췄어요' 실패 — [다시 시도]할 수 있다`, async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    // 응답 머리가 오지 않는 서버 — abort 되면 진짜 fetch 처럼 AbortError 로 끝난다
    const signals: AbortSignal[] = [];
    const hanging = vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          signals.push(init.signal!);
          init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        }),
    );
    const { chat } = setup({ fetchFn: hanging as unknown as typeof fetch });
    const sent = chat.send("질문");
    await advance(CHAT_IDLE_TIMEOUT_MS - 1);
    expect(chat.isStreaming.value).toBe(true);
    expect(signals[0]!.aborted).toBe(false);

    await advance(1);
    await sent;
    expect(signals[0]!.aborted).toBe(true);
    expect(chat.messages.value).toEqual([]);
    expect(chat.failure.value).toEqual({ question: "질문", message: ERROR_HINTS.timeout, retryable: true, partial: "" });
    expect(chat.isStreaming.value).toBe(false);
  });

  it("글 조각이 올 때마다 다시 센다 — 조각 사이가 한도를 넘으면 받던 글을 failure.partial 에 남기고 끊는다", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const { chat, calls, push } = setup();
    const first = chat.send("질문");
    await advance(0);
    await advance(CHAT_IDLE_TIMEOUT_MS - 10_000);
    push('data: {"text": "천천히 "}\n\n');
    await advance(CHAT_IDLE_TIMEOUT_MS - 10_000);
    push('data: {"text": "오는 답"}\n\ndata: [DONE]\n\n');
    await first;
    expect(chat.failure.value).toBeNull();
    expect(chat.messages.value.at(-1)).toEqual({ role: "assistant", content: "천천히 오는 답" });

    const second = chat.send("둘째");
    await advance(0);
    push('data: {"text": "받다가 멈춘 "}\n\n');
    await advance(CHAT_IDLE_TIMEOUT_MS);
    await second;
    expect(calls[1]!.init.signal!.aborted).toBe(true);
    expect(chat.failure.value).toEqual({ question: "둘째", message: ERROR_HINTS.timeout, retryable: true, partial: "받다가 멈춘 " });
    expect(chat.messages.value).toHaveLength(2);
  });

  it("끝난 답·[멈춤]으로 끊은 답은 시계가 남지 않는다 — 나중에 실패로 바뀌지 않는다", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const { chat, push } = setup();
    const sent = chat.send("질문");
    await advance(0);
    chat.stop();
    await sent;
    await advance(CHAT_IDLE_TIMEOUT_MS * 2);
    expect(chat.failure.value).toBeNull();
    expect(chat.messages.value.at(-1)).toEqual({ role: "assistant", content: CHAT_STOPPED_EMPTY });

    const next = chat.send("둘째");
    await advance(0);
    push('data: {"text": "답"}\n\ndata: [DONE]\n\n');
    await next;
    await advance(CHAT_IDLE_TIMEOUT_MS * 2);
    expect(chat.failure.value).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });
});
