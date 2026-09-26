// frontend/tests/unit/researchErrors.test.ts
import { describe, expect, it } from "vitest";
import { detailMessage, httpStatus, researchErrorMessage } from "~/utils/researchErrors";

function fetchError(status: number, detail?: unknown) {
  return Object.assign(new Error(`HTTP ${status}`), { status, statusCode: status, data: detail === undefined ? undefined : { detail } });
}

describe("httpStatus", () => {
  it("$fetch 오류의 status·statusCode·response.status 를 읽는다", () => {
    expect(httpStatus({ status: 409 })).toBe(409);
    expect(httpStatus({ statusCode: 503 })).toBe(503);
    expect(httpStatus({ response: { status: 404 } })).toBe(404);
    expect(httpStatus(new Error("network"))).toBeUndefined();
    expect(httpStatus(null)).toBeUndefined();
  });
});

describe("detailMessage", () => {
  it("문자열 detail 은 그대로, 배열 detail 은 msg 를 모아 쓴다", () => {
    expect(detailMessage("하위질문은 6개까지다")).toBe("하위질문은 6개까지다");
    expect(detailMessage([{ loc: ["body", "question"], msg: "String should have at least 2 characters", type: "string_too_short" }]))
      .toBe("입력값이 올바르지 않습니다: String should have at least 2 characters");
    expect(detailMessage({ unexpected: true })).toBeNull();
    expect(detailMessage([])).toBeNull();
  });
});

describe("researchErrorMessage", () => {
  it("422 는 두 모양의 detail 을 모두 보여 준다", () => {
    expect(researchErrorMessage(fetchError(422, "중복된 하위질문이다: 가"), "실패")).toBe("중복된 하위질문이다: 가");
    expect(researchErrorMessage(fetchError(422, [{ msg: "too long" }]), "실패")).toBe("입력값이 올바르지 않습니다: too long");
  });

  it("429·503 은 잠시 뒤 다시 안내한다", () => {
    expect(researchErrorMessage(fetchError(429, "x"), "실패")).toBe("요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요");
    expect(researchErrorMessage(fetchError(503, "작업 큐"), "실패")).toBe("요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요");
  });

  it("409 는 서버 사유를, 사유가 없으면 대체 문구를 쓴다", () => {
    expect(researchErrorMessage(fetchError(409, "승인할 수 없는 상태다: running"), "실패")).toBe("승인할 수 없는 상태다: running");
    expect(researchErrorMessage(fetchError(409), "실패")).toBe("실패");
  });

  it("상태가 없으면 네트워크 문제로, 그 밖의 상태는 대체 문구로 둔다", () => {
    expect(researchErrorMessage(new Error("Failed to fetch"), "딥리서치를 시작하지 못했습니다"))
      .toBe("딥리서치를 시작하지 못했습니다 — 네트워크 연결을 확인하세요");
    expect(researchErrorMessage(fetchError(500, "Internal"), "실패")).toBe("실패");
  });
});
