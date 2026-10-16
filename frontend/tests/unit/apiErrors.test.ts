// frontend/tests/unit/apiErrors.test.ts
// 공통 오류 규칙(utils/apiErrors.ts) — 상태 읽기·오류 종류·일부러 끊은 요청·422 검증 문구·화면 문구 고르기·toUserError.
// 가짜 오류 객체와 함께 실제 ofetch(1.5.1)가 만든 FetchError 로도 확인한다 — 시간 초과·끊김의 모양이 버전마다 달라서다
import { createFetch } from "ofetch";
import { describe, expect, it } from "vitest";
import {
  CODE_MESSAGES,
  DEFAULT_ERROR_MESSAGE,
  ERROR_HINTS,
  VALIDATION_HINTS,
  apiErrorMessage,
  codeMessage,
  errorKind,
  httpStatus,
  isAbortError,
  serverMessage,
  toUserError,
  validationMessage,
  type ErrorKind,
} from "~/utils/apiErrors";

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

  it("statusCode·response.status 만 있어도 읽는다(httpStatus 는 이 파일 한 곳에 정의한다)", () => {
    expect(errorKind({ statusCode: 503 })).toBe("busy");
    expect(errorKind({ response: { status: 404 } })).toBe("notFound");
    expect(httpStatus({ status: 409 })).toBe(409);
    expect(httpStatus({ statusCode: 503 })).toBe(503);
    expect(httpStatus({ response: { status: 404 } })).toBe(404);
    expect(httpStatus(new Error("network"))).toBeUndefined();
    expect(httpStatus(null)).toBeUndefined();
  });
});

describe("errorKind — 응답이 없을 때", () => {
  it("응답 없이 끝난 요청(상태 없는 FetchError·native fetch 의 연결 실패 TypeError)은 네트워크 문제다", () => {
    expect(errorKind(noResponse(new TypeError("Failed to fetch")))).toBe("network");
    expect(errorKind(noResponse(undefined, "[GET] \"/api/x\": <no response>"))).toBe("network");
    // 상태 0(불투명 응답)도 상태 없음으로 본다
    expect(errorKind(Object.assign(noResponse(new TypeError("Failed to fetch")), { status: 0 }))).toBe("network");
    // native fetch 의 연결 실패 문구 — 크롬·Node(undici)·파이어폭스·사파리
    for (const message of ["Failed to fetch", "fetch failed", "NetworkError when attempting to fetch resource.", "Load failed"]) {
      expect(errorKind(new TypeError(message)), message).toBe("network");
    }
  });

  it("응답과 상관없는 예외(응답을 가공하다 난 코드 버그·이상한 값)는 네트워크가 아니라 unknown", () => {
    expect(errorKind(new TypeError("Cannot read properties of undefined (reading 'x')"))).toBe("unknown");
    expect(errorKind(new SyntaxError("Unexpected token < in JSON at position 0"))).toBe("unknown");
    expect(errorKind(new RangeError("Invalid time value"))).toBe("unknown");
    expect(errorKind(new Error("Failed to fetch"))).toBe("unknown");
    expect(errorKind(new Error("request timeout"))).toBe("unknown");
    expect(errorKind({ status: 0 })).toBe("unknown");
    expect(errorKind({ message: "timeout of 30000ms exceeded" })).toBe("unknown");
    expect(errorKind(null)).toBe("unknown");
    expect(errorKind(undefined)).toBe("unknown");
    expect(errorKind("boom")).toBe("unknown");
  });

  it("시간 초과 — ofetch 의 TimeoutError(cause)·DOMException TimeoutError·cause 메시지의 timeout", () => {
    const ofetchTimeout = Object.assign(new Error("[TimeoutError]: The operation was aborted due to timeout"), { name: "TimeoutError" });
    expect(errorKind(noResponse(ofetchTimeout))).toBe("timeout");
    expect(errorKind(domError("TimeoutError", "signal timed out"))).toBe("timeout");
    expect(errorKind(noResponse(domError("TimeoutError")))).toBe("timeout");
    expect(errorKind(noResponse(new Error("request timeout")))).toBe("timeout");
    expect(errorKind(noResponse(new Error("The operation timed out.")))).toBe("timeout");
    // 옛 브라우저의 AbortSignal.timeout — 이름은 AbortError 여도 시간 초과 메시지
    expect(errorKind(domError("AbortError", "signal timed out"))).toBe("timeout");
  });

  it("오래된 엔진 — fetch 는 AbortError 로 실패해도 FetchError 가 든 signal 의 이유가 TimeoutError 면 시간 초과", () => {
    const controller = new AbortController();
    controller.abort(Object.assign(new Error("signal timed out"), { name: "TimeoutError" }));
    const err = Object.assign(noResponse(domError("AbortError")), { options: { signal: controller.signal } });
    expect(errorKind(err)).toBe("timeout");
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

  it("오래된 엔진 — cause 가 AbortError 여도 options.signal 의 이유가 TimeoutError 면 끊김이 아니다", () => {
    const timedOut = new AbortController();
    timedOut.abort(Object.assign(new Error("signal timed out"), { name: "TimeoutError" }));
    expect(isAbortError(Object.assign(noResponse(domError("AbortError")), { options: { signal: timedOut.signal } }))).toBe(false);
    // 호출부가 끊은 signal(이유 AbortError)이면 그대로 끊김
    const cancelled = new AbortController();
    cancelled.abort();
    expect(isAbortError(Object.assign(noResponse(domError("AbortError")), { options: { signal: cancelled.signal } }))).toBe(true);
    // options 가 이상한 값이어도 깨지지 않는다
    expect(isAbortError(Object.assign(noResponse(domError("AbortError")), { options: null }))).toBe(true);
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
      .toBe("500자까지 입력할 수 있어요");
    expect(validationMessage([{ type: "string_too_long", ctx: { max_length: 3000 } }])).toBe("3000자까지 입력할 수 있어요");
  });

  it("string_too_short 는 최소 글자 수가 2 이상이면 그 수로, 1 이하·없으면 내용을 입력하라고 한다", () => {
    expect(validationMessage([{ type: "string_too_short", ctx: { min_length: 2 }, msg: "String should have at least 2 characters" }]))
      .toBe("2자 이상 입력해 주세요");
    expect(validationMessage([{ type: "string_too_short", ctx: { min_length: 10 } }])).toBe("10자 이상 입력해 주세요");
    expect(validationMessage([{ type: "string_too_short", ctx: { min_length: 1 } }])).toBe("내용을 입력해 주세요");
    expect(validationMessage([{ type: "string_too_short" }])).toBe("내용을 입력해 주세요");
    expect(validationMessage([{ type: "string_too_short", ctx: { min_length: "3" } }])).toBe("내용을 입력해 주세요");
  });

  it("missing(필드가 빠짐)은 화면이 요청을 잘못 만든 것이라 일반 문구", () => {
    expect(validationMessage([{ type: "missing", loc: ["body", "query"], msg: "Field required" }])).toBe("입력값이 올바르지 않아요");
  });

  it("그 밖의 항목·최대 글자 수가 없는 길이 초과·빈 배열은 일반 문구", () => {
    expect(validationMessage([{ type: "int_parsing", msg: "Input should be a valid integer" }])).toBe("입력값이 올바르지 않아요");
    expect(validationMessage([{ type: "string_too_long" }])).toBe("입력값이 올바르지 않아요");
    expect(validationMessage([{ type: "string_too_long", ctx: { max_length: "500" } }])).toBe("입력값이 올바르지 않아요");
    expect(validationMessage([])).toBe("입력값이 올바르지 않아요");
    expect(validationMessage([null, "x"])).toBe("입력값이 올바르지 않아요");
  });

  it("여러 항목이면 알아볼 수 있는 첫 항목을 쓴다(missing 은 건너뛴다)", () => {
    expect(validationMessage([{ type: "int_parsing" }, { type: "missing" }, { type: "string_too_short", ctx: { min_length: 1 } }]))
      .toBe("내용을 입력해 주세요");
    expect(validationMessage([{ type: "missing" }, { type: "string_too_long", ctx: { max_length: 500 } }])).toBe("500자까지 입력할 수 있어요");
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

describe("serverMessage — 서버의 깨끗한 한글 사유만", () => {
  it("한글만 있는 문장(숫자·문장 부호·줄표는 괜찮다)은 앞뒤 공백만 걷어 그대로", () => {
    expect(serverMessage(" 목차를 만드는 중입니다 ")).toBe("목차를 만드는 중입니다");
    expect(serverMessage("검사 뒤 글이 3000자를 넘습니다 — 조금 줄여 주세요")).toBe("검사 뒤 글이 3000자를 넘습니다 — 조금 줄여 주세요");
    expect(serverMessage("중복된 하위질문이다: 가")).toBe("중복된 하위질문이다: 가");
    expect(serverMessage({ code: "version_conflict", version: 3, message: "다른 곳에서 계획서가 바뀌었습니다" })).toBe("다른 곳에서 계획서가 바뀌었습니다");
  });

  // 서버(app/api/*.py)에 실제로 있는 개발자용 문구의 모양 — 예외 원문·변수·필드·헤더 이름이 섞여 사용자에게 보이면 안 된다
  it.each([
    "PDF 없음: An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist.",
    "잡 생성 실패: connection refused",
    "파라미터 max_rounds 는 int 여야 한다: 'x'",
    "snapshot 은 200KB 까지다",
    "도서 없음: KCI_FI001234",
    "x-session-id 헤더가 필요하다",
    "승인할 수 없는 상태다: running",
    "설정이 잘못됐다: {1: 2}",
    "값이 \"비어\" 있다",
  ])("한·영 섞인 개발자용 문구는 null — %s", (text) => {
    expect(serverMessage(text)).toBeNull();
    expect(serverMessage({ code: "x", message: text })).toBeNull();
  });

  it("영문·빈 글·한글 없는 글·문자열 아닌 값·배열은 null", () => {
    expect(serverMessage("Not Found")).toBeNull();
    expect(serverMessage("  ")).toBeNull();
    expect(serverMessage("3000")).toBeNull();
    expect(serverMessage({ code: "x", message: 3 })).toBeNull();
    expect(serverMessage({ code: "x" })).toBeNull();
    expect(serverMessage([{ msg: "가나다" }])).toBeNull();
    expect(serverMessage(null)).toBeNull();
    expect(serverMessage(undefined)).toBeNull();
  });
});

describe("apiErrorMessage — (a) 서버의 한글 사유", () => {
  it("4xx 의 깨끗한 한글 문자열 detail 은 그대로(앞뒤 공백만 걷는다)", () => {
    expect(apiErrorMessage(fetchError(404, "주제가 없습니다"), "실패")).toBe("주제가 없습니다");
    expect(apiErrorMessage(fetchError(409, " 목차를 만드는 중입니다 "), "실패")).toBe("목차를 만드는 중입니다");
    expect(apiErrorMessage(fetchError(422, "검사 뒤 글이 3000자를 넘습니다"), "실패")).toBe("검사 뒤 글이 3000자를 넘습니다");
  });

  it("구조화 detail {code, message} 도 message 가 깨끗한 한글이면 그대로", () => {
    expect(apiErrorMessage(fetchError(429, { code: "browser_active", message: "다른 탭의 연구가 돌고 있습니다", job_id: "j" }), "실패"))
      .toBe("다른 탭의 연구가 돌고 있습니다");
    expect(apiErrorMessage(fetchError(409, { code: "version_conflict", version: 3, message: "다른 곳에서 계획서가 바뀌었습니다" }), "실패"))
      .toBe("다른 곳에서 계획서가 바뀌었습니다");
  });

  it("한·영 섞인 개발자용 detail 은 쓰지 않고 kind 규칙으로 간다(문자열·구조화 둘 다)", () => {
    expect(apiErrorMessage(fetchError(404, "PDF 없음: NoSuchKey"), "원문을 불러오지 못했습니다")).toBe("원문을 불러오지 못했습니다");
    expect(apiErrorMessage(fetchError(404, "도서 없음: KCI_FI001234"), "도서를 불러오지 못했습니다")).toBe("도서를 불러오지 못했습니다");
    expect(apiErrorMessage(fetchError(400, "x-session-id 헤더가 필요하다"), "실패")).toBe("실패");
    expect(apiErrorMessage(fetchError(422, "파라미터 max_rounds 는 int 여야 한다: 'x'"), "실패")).toBe("실패");
    expect(apiErrorMessage(fetchError(413, "snapshot 은 200KB 까지다"), "저장하지 못했습니다")).toBe("저장하지 못했습니다");
    expect(apiErrorMessage(fetchError(409, { code: "x", message: "승인할 수 없는 상태다: running" }), "실패")).toBe("실패");
    // 상표 낱말(DeepResearch)이 든 서버 문구도 라틴 문자라 쓰지 않는다 — 연구 화면은 researchErrorMessage 가 browser_active 를 따로 다룬다
    const active = { code: "browser_active", message: "진행 중인 DeepResearch가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요", job_id: "j" };
    expect(apiErrorMessage(fetchError(429, active), "실패")).toBe(`실패 — ${ERROR_HINTS.busy}`);
  });

  it("5xx 는 code 가 있는 구조화 detail 이거나 503 일 때만 서버 사유를 쓴다 — 그 밖은 대체 문구 + 이유", () => {
    expect(apiErrorMessage(fetchError(500, "검색 색인을 열지 못했습니다"), "실패")).toBe(`실패 — ${ERROR_HINTS.server}`);
    expect(apiErrorMessage(fetchError(500, "잡 생성 실패: connection refused"), "실패")).toBe(`실패 — ${ERROR_HINTS.server}`);
    expect(apiErrorMessage(fetchError(502, { message: "서버가 바쁩니다" }), "실패")).toBe(`실패 — ${ERROR_HINTS.server}`);
    expect(apiErrorMessage(fetchError(500, { code: "index_unavailable", message: "검색 색인을 열지 못했습니다" }), "실패"))
      .toBe("검색 색인을 열지 못했습니다");
    expect(apiErrorMessage(fetchError(503, "작업 큐에 연결하지 못했습니다 — 잠시 후 다시 시도하세요"), "실패"))
      .toBe("작업 큐에 연결하지 못했습니다 — 잠시 후 다시 시도하세요");
    // code 가 있어도·503 이어도 개발자용·영문 문구면 쓰지 않는다
    expect(apiErrorMessage(fetchError(500, { code: "x", message: "잡 생성 실패: boom" }), "실패")).toBe(`실패 — ${ERROR_HINTS.server}`);
    expect(apiErrorMessage(fetchError(503, "Service Unavailable"), "실패")).toBe(`실패 — ${ERROR_HINTS.busy}`);
  });

  it("영문 detail(프레임워크 기본 문구)은 쓰지 않고 kind 규칙으로 간다", () => {
    expect(apiErrorMessage(fetchError(404, "Not Found"), "연구를 불러오지 못했습니다")).toBe("연구를 불러오지 못했습니다");
    expect(apiErrorMessage(fetchError(500, "Internal Server Error"), "실패")).toBe(`실패 — ${ERROR_HINTS.server}`);
    expect(apiErrorMessage(fetchError(409, { code: "x", message: "conflict" }), "실패")).toBe("실패");
    expect(apiErrorMessage(fetchError(503, "  "), "실패")).toBe(`실패 — ${ERROR_HINTS.busy}`);
  });
});

describe("apiErrorMessage — (0) 백엔드 오류 code 의 문구(CODE_MESSAGES)", () => {
  /** 서버 응답 본문 {detail, code} — 백엔드 core/errors 의 ApiError 모양 */
  function codedError(status: number, code: unknown, detail: unknown = "서버에서 문제가 생겼습니다. 잠시 뒤 다시 시도하세요") {
    return Object.assign(new Error(ENGLISH), { status, statusCode: status, data: { detail, code } });
  }

  it("문구 표 — 해요체", () => {
    expect(CODE_MESSAGES).toEqual({
      internal_error: "서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요",
      search_unavailable: "검색 서버가 잠시 응답하지 않아요. 잠시 뒤 다시 시도해 주세요",
      storage_unavailable: "원문 저장소가 잠시 응답하지 않아요. 잠시 뒤 다시 시도해 주세요",
      not_found: "자료를 찾을 수 없어요",
      empty_answer: "답을 만들지 못했어요",
      retrieval_failed: "자료 내용을 읽지 못했어요. 잠시 뒤 다시 시도해 주세요",
    });
  });

  it("code 가 표에 있으면 서버 detail 대신 그 문구를 이유로 — 대체 문구 뒤 ' — ', 대체 문구가 비면 문구만", () => {
    const search = codedError(503, "search_unavailable", "검색 서버가 잠시 응답하지 않습니다. 잠시 뒤 다시 시도하세요");
    expect(apiErrorMessage(search, "검색하지 못했어요")).toBe(`검색하지 못했어요 — ${CODE_MESSAGES.search_unavailable}`);
    expect(apiErrorMessage(search, "")).toBe(CODE_MESSAGES.search_unavailable);
    expect(apiErrorMessage(codedError(500, "internal_error"), "실패")).toBe(`실패 — ${CODE_MESSAGES.internal_error}`);
    expect(apiErrorMessage(codedError(503, "storage_unavailable", "원문 저장소가 잠시 응답하지 않아요."), "원문을 불러오지 못했어요"))
      .toBe(`원문을 불러오지 못했어요 — ${CODE_MESSAGES.storage_unavailable}`);
    // 서버의 detail 이 무엇이든(영문·개발자용 포함) code 문구만 보인다
    expect(apiErrorMessage(codedError(500, "internal_error", "Internal Server Error"), "")).toBe(CODE_MESSAGES.internal_error);
  });

  it("모르는 code·문자열이 아닌 code 는 지금 규칙 그대로", () => {
    expect(apiErrorMessage(codedError(500, "ai_failed"), "실패")).toBe(`실패 — ${ERROR_HINTS.server}`);
    expect(apiErrorMessage(codedError(503, 3, "작업 큐에 연결하지 못했어요 — 잠시 뒤 다시 시도해 주세요"), "실패"))
      .toBe("작업 큐에 연결하지 못했어요 — 잠시 뒤 다시 시도해 주세요");
    expect(apiErrorMessage(codedError(409, "toString", "목차를 만드는 중입니다"), "실패")).toBe("목차를 만드는 중입니다");
  });

  it("codeMessage — 자기 키만(상속 이름에 속지 않는다)", () => {
    expect(codeMessage("not_found")).toBe("자료를 찾을 수 없어요");
    expect(codeMessage("toString")).toBeNull();
    expect(codeMessage("__proto__")).toBeNull();
    expect(codeMessage(undefined)).toBeNull();
    expect(codeMessage(404)).toBeNull();
  });
});

describe("apiErrorMessage — (b) 422 검증 실패 배열", () => {
  it("validationMessage 로 바꾼다", () => {
    expect(apiErrorMessage(fetchError(422, [{ type: "string_too_long", ctx: { max_length: 200 }, msg: "too long" }]), "저장하지 못했습니다"))
      .toBe("200자까지 입력할 수 있어요");
    expect(apiErrorMessage(fetchError(422, [{ type: "string_too_short", ctx: { min_length: 2 }, msg: "too short" }]), "실패"))
      .toBe("2자 이상 입력해 주세요");
    expect(apiErrorMessage(fetchError(422, [{ type: "missing", msg: "Field required" }]), "실패")).toBe("입력값이 올바르지 않아요");
    expect(apiErrorMessage(fetchError(422, [{ type: "uuid_parsing", msg: "Input should be a valid UUID" }]), "실패"))
      .toBe("입력값이 올바르지 않아요");
  });
});

describe("apiErrorMessage — (c) kind 별 이유", () => {
  const FALLBACK = "결과를 불러오지 못했습니다";

  it.each<[string, unknown, string]>([
    ["network", new TypeError("Failed to fetch"), `${FALLBACK} — 네트워크 연결을 확인해 주세요`],
    ["timeout", noResponse(domError("TimeoutError")), `${FALLBACK} — 응답이 늦어 멈췄어요. 잠시 뒤 다시 시도해 주세요`],
    ["timeout(504)", fetchError(504), `${FALLBACK} — 응답이 늦어 멈췄어요. 잠시 뒤 다시 시도해 주세요`],
    ["busy(429)", fetchError(429), `${FALLBACK} — 요청이 몰려 있어요. 잠시 뒤 다시 시도해 주세요`],
    ["busy(503)", fetchError(503), `${FALLBACK} — 요청이 몰려 있어요. 잠시 뒤 다시 시도해 주세요`],
    ["server(500)", fetchError(500), `${FALLBACK} — 서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요`],
    ["server(502 HTML 본문)", Object.assign(fetchError(502), { data: "<html>Bad Gateway</html>" }), `${FALLBACK} — 서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요`],
    ["notFound", fetchError(404), FALLBACK],
    ["conflict", fetchError(409), FALLBACK],
    ["invalid(400)", fetchError(400), FALLBACK],
    ["invalid(422 문자열 아닌 detail)", fetchError(422, { foo: 1 }), FALLBACK],
    ["forbidden", fetchError(403), FALLBACK],
    ["unknown", fetchError(418), FALLBACK],
    ["unknown(코드 버그 TypeError)", new TypeError("Cannot read properties of undefined (reading 'x')"), FALLBACK],
    ["unknown(응답 가공 SyntaxError)", new SyntaxError("Unexpected end of JSON input"), FALLBACK],
  ])("%s", (_, err, expected) => {
    expect(apiErrorMessage(err, FALLBACK)).toBe(expected);
  });

  it("이유 문구는 ERROR_HINTS 한 곳에서 온다", () => {
    expect(ERROR_HINTS).toEqual({
      network: "네트워크 연결을 확인해 주세요",
      timeout: "응답이 늦어 멈췄어요. 잠시 뒤 다시 시도해 주세요",
      busy: "요청이 몰려 있어요. 잠시 뒤 다시 시도해 주세요",
      server: "서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요",
    });
    expect(VALIDATION_HINTS).toEqual({
      tooLong: "{n}자까지 입력할 수 있어요",
      tooShort: "{n}자 이상 입력해 주세요",
      required: "내용을 입력해 주세요",
      invalid: "입력값이 올바르지 않아요",
    });
    expect(DEFAULT_ERROR_MESSAGE).toBe("요청을 처리하지 못했어요");
  });

  it("대체 문구가 비면 이유만, 이유도 없으면 일반 문구 — 빈 문자열은 돌려주지 않는다", () => {
    expect(apiErrorMessage(fetchError(500), "")).toBe(ERROR_HINTS.server);
    expect(apiErrorMessage(fetchError(404), " ")).toBe(DEFAULT_ERROR_MESSAGE);
    expect(apiErrorMessage(new Error("boom"), "")).toBe(DEFAULT_ERROR_MESSAGE);
  });
});

describe("toUserError — 화면이 쓰기 편한 한 번에", () => {
  it("일부러 끊은 요청이면 null — 화면은 아무것도 띄우지 않는다", () => {
    expect(toUserError(domError("AbortError"), "실패")).toBeNull();
    expect(toUserError(noResponse(domError("AbortError")), "실패")).toBeNull();
  });

  it("그 밖에는 kind 와 apiErrorMessage 의 문구", () => {
    expect(toUserError(noResponse(domError("TimeoutError")), "결과를 불러오지 못했습니다"))
      .toEqual({ kind: "timeout", message: `결과를 불러오지 못했습니다 — ${ERROR_HINTS.timeout}` });
    expect(toUserError(fetchError(404, "논문이 없습니다"), "실패")).toEqual({ kind: "notFound", message: "논문이 없습니다" });
    expect(toUserError(fetchError(422, [{ type: "string_too_long", ctx: { max_length: 500 } }]), "실패"))
      .toEqual({ kind: "invalid", message: "500자까지 입력할 수 있어요" });
    expect(toUserError(new TypeError("Cannot read properties of null (reading 'books')"), "결과를 보이지 못했습니다"))
      .toEqual({ kind: "unknown", message: "결과를 보이지 못했습니다" });
    expect(toUserError(fetchError(418), "")).toEqual({ kind: "unknown", message: DEFAULT_ERROR_MESSAGE });
  });
});

describe("apiErrorMessage — 영문 기술 메시지는 절대 나오지 않는다", () => {
  const cases: unknown[] = [
    fetchError(500),
    fetchError(500, "Internal Server Error"),
    fetchError(500, "잡 생성 실패: RuntimeError('boom')"),
    fetchError(404, "PDF 없음: NoSuchKey"),
    fetchError(422, "파라미터 max_rounds 는 int 여야 한다: 'x'"),
    fetchError(400, { code: "bad", message: "x-session-id 헤더가 필요하다" }),
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
    for (const fallback of ["불러오지 못했습니다", ""]) {
      const text = apiErrorMessage(err, fallback);
      expectNoEnglish(text);
      expect(text).toMatch(/[가-힣]/);
      expect(text).not.toMatch(/[A-Za-z]/);
    }
  });

  it("코드 버그(응답과 상관없는 예외)는 연결 탓으로 돌리지 않는다 — 대체 문구만", () => {
    expect(apiErrorMessage(new Error("Cannot read properties of undefined (reading 'x')"), "불러오지 못했습니다")).toBe("불러오지 못했습니다");
    expect(apiErrorMessage(new TypeError("x is not a function"), "불러오지 못했습니다")).toBe("불러오지 못했습니다");
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
