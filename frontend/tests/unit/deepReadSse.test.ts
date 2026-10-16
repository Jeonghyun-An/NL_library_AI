// frontend/tests/unit/deepReadSse.test.ts
import { describe, expect, it } from "vitest";
import { CODE_MESSAGES, ERROR_HINTS } from "~/utils/apiErrors";
import {
  CHAT_ANSWER_FAILED,
  CHAT_ERROR_TEXT,
  CHAT_MAX_CHARS,
  CHAT_STOPPED_EMPTY,
  CHAT_STOPPED_TEXT,
  CHAT_TIMEOUT_FAILURE,
  LEGACY_NOT_FOUND_TEXT,
  finishedAnswerCode,
  parseSse,
  requestFailure,
  streamFailure,
} from "~/utils/deepReadSse";

describe("parseSse", () => {
  it("조각 경계에 걸린 줄은 남겨 두었다가 다음 조각과 잇는다", () => {
    const first = parseSse("", 'data: {"text": "노인 우울은"}\n\ndata: {"te');
    expect(first.events).toEqual([{ type: "text", text: "노인 우울은" }]);
    expect(first.buffer).toBe('data: {"te');
    const second = parseSse(first.buffer, 'xt": " 사회적 지지와"}\n\n');
    expect(second.events).toEqual([{ type: "text", text: " 사회적 지지와" }]);
    expect(second.buffer).toBe("");
  });

  it("글·출처·[DONE] 을 차례대로 읽고, [DONE] 뒤의 줄은 읽지 않는다", () => {
    const sources = [{ page_start: 5, page_end: 7, text: "가족 지지가 높을수록 우울이 낮았다." }];
    const chunk = [
      'data: {"text": "답"}',
      "",
      `data: ${JSON.stringify({ sources })}`,
      "",
      "data: [DONE]",
      "",
      'data: {"text": "뒤에 온 글"}',
      "",
    ].join("\n");
    expect(parseSse("", chunk)).toEqual({
      buffer: "",
      events: [{ type: "text", text: "답" }, { type: "sources", sources }, { type: "done" }],
    });
    // 서버가 줄 끝에 \r 을 붙여도(\r\n) 같은 값이다
    expect(parseSse("", "data: [DONE]\r\n").events).toEqual([{ type: "done" }]);
  });

  // 서버(app/services/chat/book_chat.py)는 답을 만들지 못하면 [DONE] 바로 앞에 {error, code} 를 보낸다 — LLM 호출 실패는 code 없이 {error} 만
  it("{error, code} 는 code 와 함께 error 로 읽는다 — code 가 없거나 글이 아니면 code 없는 error(서버 문구는 읽지 않는다)", () => {
    const chunk = ['data: {"text": "받다 만"}', "", 'data: {"error": "답을 만들지 못했습니다"}', "", "data: [DONE]", ""].join("\n");
    expect(parseSse("", chunk).events).toEqual([{ type: "text", text: "받다 만" }, { type: "error", code: null }, { type: "done" }]);
    expect(parseSse("", 'data: {"error": "자료를 찾을 수 없어요", "code": "not_found"}\n').events).toEqual([
      { type: "error", code: "not_found" },
    ]);
    expect(parseSse("", 'data: {"error": "", "code": "retrieval_failed"}\n').events).toEqual([
      { type: "error", code: "retrieval_failed" },
    ]);
    expect(parseSse("", 'data: {"error": "x", "code": ""}\n').events).toEqual([{ type: "error", code: null }]);
    expect(parseSse("", 'data: {"error": true, "code": 3}\n').events).toEqual([{ type: "error", code: null }]);
  });

  it("data: 가 아닌 줄·깨진 JSON·빈 글·모르는 모양은 버린다", () => {
    const chunk = [
      ": keep-alive",
      "event: message",
      "data: {깨진",
      'data: {"text": ""}',
      'data: {"other": 1}',
      "data: 3",
      'data: {"text": "남는 글"}',
      "",
    ].join("\n");
    expect(parseSse("", chunk).events).toEqual([{ type: "text", text: "남는 글" }]);
  });
});

describe("DeepRead 실패 문구", () => {
  it("스트림 {error, code} — code 별 화면 문구, 자료가 없으면(not_found) [다시 시도]를 숨긴다", () => {
    expect(streamFailure("not_found")).toEqual({ message: CODE_MESSAGES.not_found, retryable: false });
    expect(streamFailure("empty_answer")).toEqual({ message: CODE_MESSAGES.empty_answer, retryable: true });
    expect(streamFailure("retrieval_failed")).toEqual({ message: CODE_MESSAGES.retrieval_failed, retryable: true });
  });

  it("code 없는 {error}(LLM 호출 실패)·모르는 code 는 화면 문구 '답을 만들지 못했어요' — 다시 시도할 수 있다", () => {
    expect(CHAT_ANSWER_FAILED).toBe("답을 만들지 못했어요");
    expect(streamFailure(null)).toEqual({ message: CHAT_ANSWER_FAILED, retryable: true });
    expect(streamFailure("toString")).toEqual({ message: CHAT_ANSWER_FAILED, retryable: true });
  });

  it("422(질문이 너무 김)는 서버 한도를 이유로 보이고 같은 질문을 다시 보내지 않는다", () => {
    const tooLong = Object.assign(new Error("422"), {
      status: 422,
      data: { detail: [{ type: "string_too_long", loc: ["body", "message"], msg: "String should have at most 2000 characters", ctx: { max_length: 2000 } }] },
    });
    expect(requestFailure(tooLong)).toEqual({ message: "2000자까지 입력할 수 있어요", retryable: false });
    expect(CHAT_MAX_CHARS).toBe(2000);
  });

  it("그 밖의 HTTP 오류·네트워크 오류는 '답을 받지 못했어요' 뒤에 이유 — 다시 시도할 수 있다(영문 오류 글은 보이지 않는다)", () => {
    expect(requestFailure(Object.assign(new Error("DeepRead 응답 502"), { status: 502, data: undefined }))).toEqual({
      message: `${CHAT_ERROR_TEXT} — ${ERROR_HINTS.server}`,
      retryable: true,
    });
    expect(requestFailure(new TypeError("Failed to fetch"))).toEqual({
      message: `${CHAT_ERROR_TEXT} — ${ERROR_HINTS.network}`,
      retryable: true,
    });
    expect(requestFailure(new TypeError("Cannot read properties of undefined"))).toEqual({ message: CHAT_ERROR_TEXT, retryable: true });
  });

  it("오래 무응답으로 끊은 답은 '응답이 늦어 멈췄어요.\\n잠시 뒤 다시 시도해 주세요.' — 다시 시도할 수 있다", () => {
    expect(CHAT_TIMEOUT_FAILURE).toEqual({ message: "응답이 늦어 멈췄어요.\n잠시 뒤 다시 시도해 주세요.", retryable: true });
  });

  it("옛 서버의 [DONE] 답 — 빈 답(공백뿐 포함)·'도서를 찾을 수 없습니다.' 는 실패 code, 그 밖은 정상 답", () => {
    expect(finishedAnswerCode("")).toBe("empty_answer");
    expect(finishedAnswerCode(" \n\n ")).toBe("empty_answer");
    expect(finishedAnswerCode(LEGACY_NOT_FOUND_TEXT)).toBe("not_found");
    expect(finishedAnswerCode(` ${LEGACY_NOT_FOUND_TEXT}\n`)).toBe("not_found");
    expect(finishedAnswerCode("이 논문에서 도서를 찾을 수 없습니다. 대신 …")).toBeNull();
    expect(finishedAnswerCode("노인 300명입니다.")).toBeNull();
  });

  it("끊은 답의 꼬리·실패 문구는 해요체다", () => {
    expect(CHAT_STOPPED_TEXT).toBe("(답을 받다가 멈췄어요)");
    expect(CHAT_STOPPED_EMPTY).toBe("(답을 받기 전에 멈췄어요)");
    for (const text of [CHAT_ERROR_TEXT, CHAT_ANSWER_FAILED, CHAT_STOPPED_TEXT, CHAT_STOPPED_EMPTY]) {
      expect(text).not.toMatch(/습니다|하세요/);
    }
  });
});
