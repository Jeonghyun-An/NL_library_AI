// frontend/tests/unit/apiErrors.test.ts
// 공통 오류 규칙(utils/apiErrors.ts) — 오류 종류·일부러 끊은 요청·422 검증 문구·화면 문구 고르기.
// 가짜 오류 객체와 함께 실제 ofetch(1.5.1)가 만든 FetchError 로도 확인한다 — 시간 초과·끊김의 모양이 버전마다 달라서다
import { createFetch } from "ofetch";
import { describe, expect, it } from "vitest";
import {
  ERROR_HINTS,
  VALIDATION_HINTS,
  apiErrorMessage,
  errorKind,
  isAbortError,
  validationMessage,
  type ErrorKind,
} from "~/utils/apiErrors";
import { httpStatus } from "~/utils/researchErrors";

/** $fetch 오류 모양 — 영문 message 는 화면에 절대 나오면 안 되는 값으로 둔다 */
const ENGLISH = "FetchError: [GET] \"/api/x\": 500 Internal Server Error";
function fetchError(status: number | undefined, detail?: unknown) {
  return Object.assign(new Error(ENGLISH), {
    status,
    statusCode: status,
    data: detail === undefined ? undefined : { detail },
  });
}

/** 응답 없이 끝난 요청 — cause 에 원래 오류를 든다(ofetch FetchError 모양) */
function noResponse(cause: unknown, message = "[GET] \"/api/x\": <no response> Failed to fetch") {
  return Object.assign(new Error(message), { name: "FetchError", cause });
}

function domError(name: string, message = "The operation was aborted.") {
  return new DOMException(message, name);
}

/** 화면 문구에 영문 기술 메시지가 섞이지 않았는가 — 한글 문구만 나온다 */
function expectNoEnglish(text: string) {
  expect(text).not.toMatch(/FetchError|Internal Server Error|Failed to fetch|aborted|timeout|\[object Object\]|undefined|null/i);
}

describe("errorKind — 상태 코드", () => {
  it.each<[number, ErrorKind]>([
    [408, "timeout"],
    [504, "timeout"],
    [429, "busy"],
    [503, "busy"],
    [500, "server"],
    [502, "server"],
    [501, "server"],
    [599, "server"],
    [404, "notFound"],
    [410, "notFound"],
    [400, "invalid"],
    [413, "invalid"],
    [422, "invalid"],
    [409, "conflict"],
    [401, "forbidden"],
    [403, "forbidden"],
    [418, "unknown"],
    [428, "unknown"],
  ])("%i → %s", (status, kind) => {
    expect(errorKind(fetchError(status))).toBe(kind);
  });

  it("statusCode·response.status 만 있어도 읽는다(researchErrors 의 httpStatus 를 그대로 쓴다)", () => {
    expect(errorKind({ statusCode: 503 })).toBe("busy");
    expect(errorKind({ response: { status: 404 } })).toBe("notFound");
    expect(httpStatus({ statusCode: 503 })).toBe(503);
  });
});

describe("errorKind — 응답이 없을 때", () => {
  it("상태가 없으면 네트워크 문제다(상태 0 도 같다)", () => {
    expect(errorKind(new TypeError("Failed to fetch"))).toBe("network");
    expect(errorKind(noResponse(new TypeError("Failed to fetch")))).toBe("network");
    expect(errorKind({ status: 0 })).toBe("network");
    expect(errorKind(null)).toBe("network");
    expect(errorKind(undefined)).toBe("network");
    expect(errorKind("boom")).toBe("network");
  });

  it("시간 초과 — ofetch 의 TimeoutError(cause)·DOMException TimeoutError·메시지의 timeout", () => {
    const ofetchTimeout = Object.assign(new Error("[TimeoutError]: The operation was aborted due to timeout"), { name: "TimeoutError" });
    expect(errorKind(noResponse(ofetchTimeout))).toBe("timeout");
    expect(errorKind(domError("TimeoutError", "signal timed out"))).toBe("timeout");
    expect(errorKind(noResponse(domError("TimeoutError")))).toBe("timeout");
    expect(errorKind(new Error("request timeout"))).toBe("timeout");
    expect(errorKind(new Error("The operation timed out."))).toBe("timeout");
  });

  it("상태가 있으면 메시지의 timeout 보다 상태를 따른다", () => {
    expect(errorKind(Object.assign(new Error("upstream timeout"), { status: 500 }))).toBe("server");
  });
});

describe("isAbortError", () => {
  it("일부러 끊은 요청(AbortError — 그 자체 또는 cause)은 true", () => {
    expect(isAbortError(domError("AbortError"))).toBe(true);
    expect(isAbortError(noResponse(domError("AbortError"), "[GET] \"/api/x\": <no response> This operation was aborted"))).toBe(true);
  });

  it("시간 초과는 끊김이 아니다 — 오류로 보여야 한다", () => {
    expect(isAbortError(domError("TimeoutError"))).toBe(false);
    expect(isAbortError(noResponse(domError("TimeoutError")))).toBe(false);
    // AbortError 이름이어도 시간 초과 메시지면(옛 브라우저의 AbortSignal.timeout) 끊김으로 보지 않는다
    expect(isAbortError(domError("AbortError", "signal timed out"))).toBe(false);
  });

  it("네트워크·HTTP 오류·이상한 값은 false", () => {
    expect(isAbortError(new TypeError("Failed to fetch"))).toBe(false);
    expect(isAbortError(fetchError(500))).toBe(false);
    expect(isAbortError(null)).toBe(false);
    expect(isAbortError("AbortError")).toBe(false);
  });
});

describe("validationMessage — FastAPI 422 배열", () => {
  it("string_too_long 은 서버가 준 최대 글자 수로 안내한다", () => {
    expect(validationMessage([{ type: "string_too_long", loc: ["body", "question"], msg: "String should have at most 500 characters", ctx: { max_length: 500 } }]))
      .toBe("500자까지 입력할 수 있습니다");
    expect(validationMessage([{ type: "string_too_long", ctx: { max_length: 3000 } }])).toBe("3000자까지 입력할 수 있습니다");
  });

  it("string_too_short·missing 은 내용을 입력하라고 한다", () => {
    expect(validationMessage([{ type: "string_too_short", ctx: { min_length: 2 } }])).toBe("내용을 입력해 주세요");
    expect(validationMessage([{ type: "missing", loc: ["body", "query"], msg: "Field required" }])).toBe("내용을 입력해 주세요");
  });

  it("그 밖의 항목·최대 글자 수가 없는 길이 초과·빈 배열은 일반 문구", () => {
    expect(validationMessage([{ type: "int_parsing", msg: "Input should be a valid integer" }])).toBe("입력값이 올바르지 않습니다");
    expect(validationMessage([{ type: "string_too_long" }])).toBe("입력값이 올바르지 않습니다");
    expect(validationMessage([{ type: "string_too_long", ctx: { max_length: "500" } }])).toBe("입력값이 올바르지 않습니다");
    expect(validationMessage([])).toBe("입력값이 올바르지 않습니다");
    expect(validationMessage([null, "x"])).toBe("입력값이 올바르지 않습니다");
  });

  it("여러 항목이면 알아볼 수 있는 첫 항목을 쓴다", () => {
    expect(validationMessage([{ type: "int_parsing" }, { type: "missing" }])).toBe("내용을 입력해 주세요");
  });

  it("배열이 아니면 null", () => {
    expect(validationMessage("질문이 비었습니다")).toBeNull();
    expect(validationMessage({ message: "x" })).toBeNull();
    expect(validationMessage(undefined)).toBeNull();
  });

  it("pydantic 의 영문 msg 는 쓰지 않는다", () => {
    const text = validationMessage([{ type: "value_error", msg: "Value error, bad input" }])!;
    expect(text).not.toContain("Value error");
  });
});

describe("apiErrorMessage — (a) 서버의 한글 사유", () => {
  it("한글 문자열 detail 은 상태와 상관없이 그대로(앞뒤 공백만 걷는다)", () => {
    expect(apiErrorMessage(fetchError(404, "주제가 없습니다"), "실패")).toBe("주제가 없습니다");
    expect(apiErrorMessage(fetchError(409, " 목차를 만드는 중입니다 "), "실패")).toBe("목차를 만드는 중입니다");
    expect(apiErrorMessage(fetchError(500, "검색 색인을 열지 못했습니다"), "실패")).toBe("검색 색인을 열지 못했습니다");
    expect(apiErrorMessage(fetchError(422, "검사 뒤 글이 3000자를 넘습니다"), "실패")).toBe("검사 뒤 글이 3000자를 넘습니다");
  });

  it("구조화 detail {code, message} 도 message 가 한글이면 그대로", () => {
    const active = { code: "browser_active", message: "진행 중인 DeepResearch가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요", job_id: "j" };
    expect(apiErrorMessage(fetchError(429, active), "실패")).toBe(active.message);
    expect(apiErrorMessage(fetchError(409, { code: "version_conflict", version: 3, message: "다른 곳에서 계획서가 바뀌었습니다" }), "실패"))
      .toBe("다른 곳에서 계획서가 바뀌었습니다");
  });

  it("영문 detail(프레임워크 기본 문구)은 쓰지 않고 kind 규칙으로 간다", () => {
    expect(apiErrorMessage(fetchError(404, "Not Found"), "연구를 불러오지 못했습니다")).toBe("연구를 불러오지 못했습니다");
    expect(apiErrorMessage(fetchError(500, "Internal Server Error"), "실패")).toBe(`실패 — ${ERROR_HINTS.server}`);
    expect(apiErrorMessage(fetchError(409, { code: "x", message: "conflict" }), "실패")).toBe("실패");
    expect(apiErrorMessage(fetchError(503, "  "), "실패")).toBe(`실패 — ${ERROR_HINTS.busy}`);
  });
});

describe("apiErrorMessage — (b) 422 검증 실패 배열", () => {
  it("validationMessage 로 바꾼다", () => {
    expect(apiErrorMessage(fetchError(422, [{ type: "string_too_long", ctx: { max_length: 200 }, msg: "too long" }]), "저장하지 못했습니다"))
      .toBe("200자까지 입력할 수 있습니다");
    expect(apiErrorMessage(fetchError(422, [{ type: "missing", msg: "Field required" }]), "실패")).toBe("내용을 입력해 주세요");
    expect(apiErrorMessage(fetchError(422, [{ type: "uuid_parsing", msg: "Input should be a valid UUID" }]), "실패"))
      .toBe("입력값이 올바르지 않습니다");
  });
});

describe("apiErrorMessage — (c) kind 별 이유", () => {
  const FALLBACK = "결과를 불러오지 못했습니다";

  it.each<[string, unknown, string]>([
    ["network", new TypeError("Failed to fetch"), `${FALLBACK} — 네트워크 연결을 확인하세요`],
    ["timeout", noResponse(domError("TimeoutError")), `${FALLBACK} — 응답이 늦어 멈췄습니다. 잠시 뒤 다시 시도하세요`],
    ["timeout(504)", fetchError(504), `${FALLBACK} — 응답이 늦어 멈췄습니다. 잠시 뒤 다시 시도하세요`],
    ["busy(429)", fetchError(429), `${FALLBACK} — 요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요`],
    ["busy(503)", fetchError(503), `${FALLBACK} — 요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요`],
    ["server(500)", fetchError(500), `${FALLBACK} — 서버에 문제가 생겼습니다. 잠시 뒤 다시 시도하세요`],
    ["server(502 HTML 본문)", Object.assign(fetchError(502), { data: "<html>Bad Gateway</html>" }), `${FALLBACK} — 서버에 문제가 생겼습니다. 잠시 뒤 다시 시도하세요`],
    ["notFound", fetchError(404), FALLBACK],
    ["conflict", fetchError(409), FALLBACK],
    ["invalid(400)", fetchError(400), FALLBACK],
    ["invalid(422 문자열 아닌 detail)", fetchError(422, { foo: 1 }), FALLBACK],
    ["forbidden", fetchError(403), FALLBACK],
    ["unknown", fetchError(418), FALLBACK],
  ])("%s", (_, err, expected) => {
    expect(apiErrorMessage(err, FALLBACK)).toBe(expected);
  });

  it("이유 문구는 ERROR_HINTS 한 곳에서 온다", () => {
    expect(ERROR_HINTS).toEqual({
      network: "네트워크 연결을 확인하세요",
      timeout: "응답이 늦어 멈췄습니다. 잠시 뒤 다시 시도하세요",
      busy: "요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요",
      server: "서버에 문제가 생겼습니다. 잠시 뒤 다시 시도하세요",
    });
    expect(VALIDATION_HINTS).toEqual({
      tooLong: "{n}자까지 입력할 수 있습니다",
      required: "내용을 입력해 주세요",
      invalid: "입력값이 올바르지 않습니다",
    });
  });

  it("대체 문구가 비면 이유만 보인다", () => {
    expect(apiErrorMessage(fetchError(500), "")).toBe(ERROR_HINTS.server);
    expect(apiErrorMessage(fetchError(404), " ")).toBe("");
  });
});

describe("apiErrorMessage — 영문 기술 메시지는 절대 나오지 않는다", () => {
  const cases: unknown[] = [
    fetchError(500),
    fetchError(500, "Internal Server Error"),
    fetchError(502, { message: "Bad Gateway" }),
    fetchError(422, [{ type: "x", msg: "Input should be a valid integer" }]),
    fetchError(404),
    fetchError(418, "I'm a teapot"),
    fetchError(undefined),
    new TypeError("Failed to fetch"),
    new Error("Cannot read properties of undefined (reading 'x')"),
    noResponse(domError("TimeoutError", "signal timed out")),
    noResponse(domError("AbortError")),
    { message: "timeout of 30000ms exceeded" },
    null,
    undefined,
    "string error",
  ];

  it.each(cases.map((c, i) => [i, c] as const))("경우 %i", (_, err) => {
    const text = apiErrorMessage(err, "불러오지 못했습니다");
    expectNoEnglish(text);
    expect(text).toMatch(/[가-힣]/);
  });

  it("요청 주소의 낱말(timeout)에 속지 않는다 — FetchError 메시지가 아니라 cause 를 본다", () => {
    const err = noResponse(new TypeError("Failed to fetch"), "[GET] \"/api/timeout-check\": <no response> Failed to fetch");
    expect(errorKind(err)).toBe("network");
    const aborted = noResponse(domError("AbortError"), "[GET] \"/api/timeout-check\": <no response> This operation was aborted");
    expect(isAbortError(aborted)).toBe(true);
  });
});

// 실제 ofetch 1.5.1 이 만든 오류 — 가짜 fetch 로 응답·끊김·시간 초과를 흉내 낸다
describe("실제 ofetch 오류 모양", () => {
  /** signal 이 끊기면 그 이유로 실패하고, 아니면 끝없이 기다리는 fetch */
  const hangingFetch = ((_: unknown, init?: RequestInit) =>
    new Promise((_resolve, reject) => {
      const signal = init?.signal;
      if (signal?.aborted) return reject(signal.reason);
      signal?.addEventListener("abort", () => reject(signal.reason), { once: true });
    })) as unknown as typeof fetch;

  async function caught(p: Promise<unknown>): Promise<unknown> {
    try {
      await p;
    } catch (e) {
      return e;
    }
    throw new Error("실패해야 하는 요청이 성공했다");
  }

  it("options.timeout 시간 초과 → timeout, 끊김 아님, 한글 문구", async () => {
    const $f = createFetch({ fetch: hangingFetch });
    const err = await caught($f("/api/x", { timeout: 5 }));
    expect(errorKind(err)).toBe("timeout");
    expect(isAbortError(err)).toBe(false);
    expect(apiErrorMessage(err, "불러오지 못했습니다")).toBe(`불러오지 못했습니다 — ${ERROR_HINTS.timeout}`);
  });

  it("AbortSignal.timeout 을 합친 signal 의 시간 초과 → timeout", async () => {
    const $f = createFetch({ fetch: hangingFetch });
    const caller = new AbortController();
    const err = await caught($f("/api/x", { signal: AbortSignal.any([caller.signal, AbortSignal.timeout(5)]) }));
    expect(errorKind(err)).toBe("timeout");
    expect(isAbortError(err)).toBe(false);
  });

  it("호출부가 끊은 요청 → isAbortError", async () => {
    const $f = createFetch({ fetch: hangingFetch });
    const caller = new AbortController();
    const p = caught($f("/api/x", { signal: AbortSignal.any([caller.signal, AbortSignal.timeout(60_000)]) }));
    caller.abort();
    expect(isAbortError(await p)).toBe(true);
  });

  it("응답 오류 — status·detail 을 읽는다", async () => {
    const respond = (status: number, body: unknown) =>
      (async () =>
        new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })) as unknown as typeof fetch;
    const notFound = await caught(createFetch({ fetch: respond(404, { detail: "논문이 없습니다" }) })("/api/x"));
    expect(errorKind(notFound)).toBe("notFound");
    expect(apiErrorMessage(notFound, "실패")).toBe("논문이 없습니다");
    const server = await caught(createFetch({ fetch: respond(500, { detail: "Internal Server Error" }) })("/api/x", { retry: 0 }));
    expect(errorKind(server)).toBe("server");
    expect(apiErrorMessage(server, "실패")).toBe(`실패 — ${ERROR_HINTS.server}`);
  });

  it("연결 실패 → network", async () => {
    const refused = (async () => {
      throw new TypeError("fetch failed");
    }) as unknown as typeof fetch;
    const err = await caught(createFetch({ fetch: refused })("/api/x", { retry: 0 }));
    expect(errorKind(err)).toBe("network");
    expect(apiErrorMessage(err, "실패")).toBe(`실패 — ${ERROR_HINTS.network}`);
  });
});
