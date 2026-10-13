// frontend/tests/unit/deepReadSse.test.ts
import { describe, expect, it } from "vitest";
import { parseSse } from "~/utils/deepReadSse";

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
