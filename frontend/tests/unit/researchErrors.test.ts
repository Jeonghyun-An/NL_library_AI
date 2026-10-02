// frontend/tests/unit/researchErrors.test.ts
import { describe, expect, it } from "vitest";
import { activeResearchId, detailMessage, httpStatus, pdfCheckProblem, researchErrorMessage } from "~/utils/researchErrors";

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

// 브라우저당 실행 제한(api/research.py _to_run_queue) — 승인·재시도가 같은 브라우저의 다른 연구에 막히면
// detail 이 {code, message, job_id} 객체로 온다. 공유 큐 제한은 code 가 shared_queue 다
const ACTIVE_JOB = "22222222-2222-4222-8222-222222222222";
const BROWSER_ACTIVE = {
  code: "browser_active",
  message: "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요",
  job_id: ACTIVE_JOB,
};

describe("researchErrorMessage — 429 code", () => {
  it("browser_active 면 서버 문구를, 문구가 비었으면 같은 기본 문구를 쓴다", () => {
    expect(researchErrorMessage(fetchError(429, BROWSER_ACTIVE), "계획을 승인하지 못했습니다"))
      .toBe("진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요");
    expect(researchErrorMessage(fetchError(429, { ...BROWSER_ACTIVE, message: " 다른 탭의 연구가 돌고 있습니다 " }), "실패"))
      .toBe("다른 탭의 연구가 돌고 있습니다");
    expect(researchErrorMessage(fetchError(429, { code: "browser_active", message: "", job_id: ACTIVE_JOB }), "실패"))
      .toBe("진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요");
  });

  it("공유 큐(shared_queue)·code 가 없는 429 는 지금 문구 그대로다", () => {
    const crowded = "요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요";
    expect(researchErrorMessage(fetchError(429, { code: "shared_queue", message: "다른 딥리서치가 실행 중이다" }), "실패")).toBe(crowded);
    expect(researchErrorMessage(fetchError(429, "다른 딥리서치가 실행 중이다"), "실패")).toBe(crowded);
    expect(researchErrorMessage(fetchError(429), "실패")).toBe(crowded);
  });
});

describe("activeResearchId", () => {
  it("429 browser_active 면 진행 중인 연구 id 를 준다", () => {
    expect(activeResearchId(fetchError(429, BROWSER_ACTIVE))).toBe(ACTIVE_JOB);
  });

  it("다른 429·다른 상태·id 가 없는 detail·네트워크 오류는 null", () => {
    expect(activeResearchId(fetchError(429, { code: "shared_queue", message: "x" }))).toBeNull();
    expect(activeResearchId(fetchError(429, "x"))).toBeNull();
    expect(activeResearchId(fetchError(429, { code: "browser_active", message: "m" }))).toBeNull();
    expect(activeResearchId(fetchError(409, BROWSER_ACTIVE))).toBeNull();
    expect(activeResearchId(new Error("Failed to fetch"))).toBeNull();
    expect(activeResearchId(null)).toBeNull();
  });
});

describe("pdfCheckProblem", () => {
  it("원문이 있으면 뷰어를 연다", () => {
    expect(pdfCheckProblem(200)).toBeNull();
    expect(pdfCheckProblem(206)).toBeNull();
  });

  it("404 만 원문 파일이 없다고 알린다", () => {
    expect(pdfCheckProblem(404)).toBe("원문 파일이 없습니다");
  });

  it("서버 오류 등은 파일이 없다고 하지 않고 다시 시도하라고 알린다", () => {
    expect(pdfCheckProblem(500)).toBe("원문을 불러오지 못했습니다. 잠시 뒤 다시 시도하세요");
    expect(pdfCheckProblem(502)).toBe("원문을 불러오지 못했습니다. 잠시 뒤 다시 시도하세요");
    expect(pdfCheckProblem(403)).toBe("원문을 불러오지 못했습니다. 잠시 뒤 다시 시도하세요");
  });

  it("확인 요청 자체가 실패하면 판단하지 않고 뷰어에 맡긴다", () => {
    expect(pdfCheckProblem(null)).toBeNull();
  });
});
