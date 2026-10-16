// frontend/tests/unit/researchErrors.test.ts
import { describe, expect, it } from "vitest";
import { ERROR_HINTS, httpStatus } from "~/utils/apiErrors";
import {
  BROWSER_ACTIVE_MESSAGE,
  LOST_AFTER_DROPS,
  RESEARCH_NOT_FOUND,
  RESEARCH_STATE_TEXT,
  SUBQ_FAILED_TEXT,
  activeResearchId,
  detailMessage,
  failureReason,
  pdfCheckProblem,
  researchConnectionState,
  researchErrorMessage,
  researchFailedMessage,
  researchRetryLabel,
  subqFailureText,
  versionConflict,
  workErrorMessage,
} from "~/utils/researchErrors";

function fetchError(status: number, detail?: unknown) {
  return Object.assign(new Error(`HTTP ${status}`), { status, statusCode: status, data: detail === undefined ? undefined : { detail } });
}

describe("httpStatus(apiErrors 에 정의 — 연구 화면도 그것을 쓴다)", () => {
  it("$fetch 오류의 status·statusCode·response.status 를 읽는다", () => {
    expect(httpStatus({ status: 409 })).toBe(409);
    expect(httpStatus({ statusCode: 503 })).toBe(503);
    expect(httpStatus({ response: { status: 404 } })).toBe(404);
    expect(httpStatus(new Error("network"))).toBeUndefined();
    expect(httpStatus(null)).toBeUndefined();
  });
});

describe("detailMessage", () => {
  it("깨끗한 한글 문자열 detail 은 그대로, 배열 detail 은 pydantic 의 영문 msg 대신 사람 말(validationMessage)", () => {
    expect(detailMessage("하위질문은 6개까지다")).toBe("하위질문은 6개까지다");
    expect(detailMessage([{ loc: ["body", "question"], msg: "String should have at least 2 characters", type: "string_too_short", ctx: { min_length: 2 } }]))
      .toBe("2자 이상 입력해 주세요");
    expect(detailMessage([{ loc: ["body", "question"], msg: "String should have at most 500 characters", type: "string_too_long", ctx: { max_length: 500 } }]))
      .toBe("500자까지 입력할 수 있어요");
    expect(detailMessage([{ msg: "Field required", type: "missing" }])).toBe("입력값이 올바르지 않아요");
    expect(detailMessage([])).toBe("입력값이 올바르지 않아요");
    expect(detailMessage({ unexpected: true })).toBeNull();
  });

  it("예외 원문·변수 값이 섞인 개발자용 문구는 null(문자열·{message} 둘 다)", () => {
    expect(detailMessage("승인할 수 없는 상태다: running")).toBeNull();
    expect(detailMessage("PDF 없음: NoSuchKey")).toBeNull();
    expect(detailMessage("파라미터 max_rounds 는 int 여야 한다: 'x'")).toBeNull();
    expect(detailMessage({ code: "x", message: "x-session-id 헤더가 필요하다" })).toBeNull();
    expect(detailMessage("Not Found")).toBeNull();
  });
});

describe("researchErrorMessage", () => {
  it("422 는 두 모양의 detail 을 모두 사람 말로 보여 준다", () => {
    expect(researchErrorMessage(fetchError(422, "중복된 하위질문이다: 가"), "실패")).toBe("중복된 하위질문이다: 가");
    expect(researchErrorMessage(fetchError(422, [{ msg: "too long" }]), "실패")).toBe("입력값이 올바르지 않아요");
    expect(researchErrorMessage(fetchError(422, [{ msg: "String should have at most 500 characters", type: "string_too_long", ctx: { max_length: 500 } }]), "실패"))
      .toBe("500자까지 입력할 수 있어요");
    // 개발자용 문구(필드 이름·repr 값)는 대체 문구로
    expect(researchErrorMessage(fetchError(422, "파라미터 max_rounds 는 int 여야 한다: 'x'"), "실패")).toBe("실패");
  });

  it("429·503 은 잠시 뒤 다시 안내한다", () => {
    expect(researchErrorMessage(fetchError(429, "x"), "실패")).toBe("요청이 몰려 있어요.\n잠시 뒤 다시 시도해 주세요.");
    expect(researchErrorMessage(fetchError(503, "작업 큐"), "실패")).toBe("요청이 몰려 있어요.\n잠시 뒤 다시 시도해 주세요.");
  });

  it("409 는 서버의 깨끗한 사유를, 사유가 없거나 개발자용(상태 값이 섞임)이면 대체 문구를 쓴다", () => {
    expect(researchErrorMessage(fetchError(409, "취소할 수 없는 상태입니다"), "실패")).toBe("취소할 수 없는 상태입니다");
    expect(researchErrorMessage(fetchError(409, "승인할 수 없는 상태다: running"), "실패")).toBe("실패");
    expect(researchErrorMessage(fetchError(409), "실패")).toBe("실패");
  });

  it("응답이 없으면 연결 실패와 시간 초과를 나눠 알리고, 그 밖의 상태는 대체 문구로 둔다", () => {
    // ofetch 가 응답 없이 실패한 요청(FetchError, cause = 연결 실패)
    const refused = Object.assign(new Error("[GET] \"/api/research/x\": <no response> Failed to fetch"), {
      name: "FetchError",
      cause: new TypeError("Failed to fetch"),
    });
    expect(researchErrorMessage(refused, "DeepResearch를 시작하지 못했어요"))
      .toBe(`DeepResearch를 시작하지 못했어요 — ${ERROR_HINTS.network}`);
    expect(researchErrorMessage(new TypeError("Failed to fetch"), "실패")).toBe("실패 — 네트워크 연결을 확인해 주세요");
    // 크롬이 응답 본문을 읽다 끊기면 던지는 TypeError('network error')도 연결 실패
    expect(researchErrorMessage(new TypeError("network error"), "실패")).toBe("실패 — 네트워크 연결을 확인해 주세요");
    // 읽기 요청의 30초 제한에 걸린 폴링 GET — 네트워크 탓이 아니라 시간 초과로 알린다
    const timedOut = Object.assign(new Error("[GET] \"/api/research/x\": <no response> [TimeoutError]: The operation was aborted due to timeout"), {
      name: "FetchError",
      cause: Object.assign(new Error("[TimeoutError]: The operation was aborted due to timeout"), { name: "TimeoutError" }),
    });
    expect(researchErrorMessage(timedOut, "최신 상태를 불러오지 못했어요"))
      .toBe("최신 상태를 불러오지 못했어요 — 응답이 늦어 멈췄어요.\n잠시 뒤 다시 시도해 주세요.");
    // 응답과 상관없는 예외(코드 버그)는 연결 탓으로 돌리지 않는다
    expect(researchErrorMessage(new Error("Failed to fetch"), "실패")).toBe("실패");
    expect(researchErrorMessage(new TypeError("Cannot read properties of undefined (reading 'status')"), "실패")).toBe("실패");
    expect(researchErrorMessage(fetchError(500, "Internal"), "실패")).toBe("실패");
  });
});

// 브라우저당 실행 제한(api/research.py _to_run_queue) — 승인·재시도가 같은 브라우저의 다른 연구에 막히면
// detail 이 {code, message, job_id} 객체로 온다. 공유 큐 제한은 code 가 shared_queue 다
const ACTIVE_JOB = "22222222-2222-4222-8222-222222222222";
const BROWSER_ACTIVE = {
  code: "browser_active",
  message: "진행 중인 DeepResearch가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요",
  job_id: ACTIVE_JOB,
};

describe("researchErrorMessage — 429 code", () => {
  it("browser_active 면 서버 문구(운영 서버는 합쇼체)가 아니라 늘 화면의 해요체 문구를 쓴다", () => {
    const front = "진행 중인 DeepResearch가 있어요 — 끝나거나 취소한 뒤 다시 시작해 주세요";
    expect(BROWSER_ACTIVE_MESSAGE).toBe(front);
    expect(researchErrorMessage(fetchError(429, BROWSER_ACTIVE), "계획을 승인하지 못했어요")).toBe(front);
    expect(researchErrorMessage(fetchError(429, { ...BROWSER_ACTIVE, message: " 다른 탭의 연구가 돌고 있습니다 " }), "실패")).toBe(front);
    expect(researchErrorMessage(fetchError(429, { code: "browser_active", message: "", job_id: ACTIVE_JOB }), "실패")).toBe(front);
    // 대체 문구를 비워도(상태 블록의 설명 줄) 같은 문구
    expect(researchErrorMessage(fetchError(429, BROWSER_ACTIVE), "")).toBe(front);
  });

  it("공유 큐(shared_queue)·code 가 없는 429 는 지금 문구 그대로다", () => {
    const crowded = "요청이 몰려 있어요.\n잠시 뒤 다시 시도해 주세요.";
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

// 계획서 고치기(PUT outline·sections)가 다른 곳에서 바뀐 version 에 막히면 detail 이 {code, version, message} 다
const CONFLICT = {
  code: "version_conflict",
  version: 4,
  message: "다른 곳에서 계획서가 바뀌었습니다 — 다시 불러온 뒤 고쳐 주세요",
};

describe("detailMessage·researchErrorMessage — 객체 detail", () => {
  it("{message} 객체 detail 의 문구를 읽고, 문구가 없거나 비었으면 null", () => {
    expect(detailMessage(CONFLICT)).toBe("다른 곳에서 계획서가 바뀌었습니다 — 다시 불러온 뒤 고쳐 주세요");
    expect(detailMessage({ code: "x", message: "  " })).toBeNull();
    expect(detailMessage({ code: "x", message: 3 })).toBeNull();
  });

  it("409·422 의 객체 detail 은 서버 문구를 보인다", () => {
    expect(researchErrorMessage(fetchError(409, CONFLICT), "계획서를 저장하지 못했습니다"))
      .toBe("다른 곳에서 계획서가 바뀌었습니다 — 다시 불러온 뒤 고쳐 주세요");
    expect(researchErrorMessage(fetchError(422, { message: "묶음 키가 다릅니다" }), "실패")).toBe("묶음 키가 다릅니다");
    expect(researchErrorMessage(fetchError(409, { code: "x" }), "실패")).toBe("실패");
    expect(researchErrorMessage(fetchError(409, { code: "x", message: "잡 상태가 running 이다" }), "실패")).toBe("실패");
  });
});

describe("versionConflict", () => {
  it("409 version_conflict 면 서버의 지금 version 을 준다", () => {
    expect(versionConflict(fetchError(409, CONFLICT))).toBe(4);
    expect(versionConflict(fetchError(409, { ...CONFLICT, version: 0 }))).toBe(0);
  });

  it("다른 409·다른 상태·version 이 정수가 아닌 detail·네트워크 오류는 null", () => {
    expect(versionConflict(fetchError(409, "목차를 만드는 중입니다"))).toBeNull();
    expect(versionConflict(fetchError(409, { code: "other", version: 4 }))).toBeNull();
    expect(versionConflict(fetchError(409, { ...CONFLICT, version: "4" }))).toBeNull();
    expect(versionConflict(fetchError(409, { ...CONFLICT, version: 1.5 }))).toBeNull();
    expect(versionConflict(fetchError(428, CONFLICT))).toBeNull();
    expect(versionConflict(new Error("Failed to fetch"))).toBeNull();
    expect(versionConflict(null)).toBeNull();
  });
});

describe("workErrorMessage", () => {
  it("404 는 서버 문구(주제·논문·문단이 없음)를 그대로 보이고, 문구가 없으면 연구 화면과 같은 문구", () => {
    expect(workErrorMessage(fetchError(404, "문단이 없습니다"), "실패")).toBe("문단이 없습니다");
    expect(workErrorMessage(fetchError(404), "실패")).toBe("찾을 수 없는 연구예요");
    // 개발자용 404 문구(예외 원문이 섞임)는 문구가 없는 404 와 같다
    expect(workErrorMessage(fetchError(404, "PDF 없음: NoSuchKey"), "실패")).toBe("찾을 수 없는 연구예요");
  });

  it("404 밖은 researchErrorMessage 와 같다", () => {
    expect(workErrorMessage(fetchError(409, "카드가 아직 없습니다"), "실패")).toBe("카드가 아직 없습니다");
    expect(workErrorMessage(fetchError(500), "실패")).toBe("실패");
  });

  it("절 PUT 의 422(검사 뒤 글이 상한을 넘음)는 서버 문구를 그대로 보인다 — 화면 검사는 보낸 글만 보아 통과시킨다", () => {
    // 서버 api/research_proposal.PARAGRAPH_TOO_LONG — 이유(단정 표현 바꾸기로 늘어남)가 보여야 사용자가 줄일 곳을 안다
    const tooLong = "검사 뒤 글이 3000자를 넘습니다 — 단정 표현을 바꾸면서 글이 늘었을 수 있습니다. 조금 줄여 주세요";
    expect(workErrorMessage(fetchError(422, tooLong), "문단을 저장하지 못했습니다")).toBe(tooLong);
  });
});

describe("pdfCheckProblem", () => {
  it("원문이 있으면 뷰어를 연다", () => {
    expect(pdfCheckProblem(200)).toBeNull();
    expect(pdfCheckProblem(206)).toBeNull();
  });

  it("404 만 원문 파일이 없다고 알린다", () => {
    expect(pdfCheckProblem(404)).toBe("원문 파일이 없어요");
  });

  it("서버 오류 등은 파일이 없다고 하지 않고 다시 시도하라고 알린다", () => {
    expect(pdfCheckProblem(500)).toBe("원문을 불러오지 못했어요.\n잠시 뒤 다시 시도해 주세요.");
    expect(pdfCheckProblem(502)).toBe("원문을 불러오지 못했어요.\n잠시 뒤 다시 시도해 주세요.");
    expect(pdfCheckProblem(403)).toBe("원문을 불러오지 못했어요.\n잠시 뒤 다시 시도해 주세요.");
  });

  it("확인 요청 자체가 실패하면 판단하지 않고 뷰어에 맡긴다", () => {
    expect(pdfCheckProblem(null)).toBeNull();
  });
});

describe("딥리서치 화면의 상태 문구(RESEARCH_STATE_TEXT) — 해요체, 오류 화면 모음과 같은 상수", () => {
  it("멈춘·취소한·찾을 수 없는 연구", () => {
    expect(RESEARCH_NOT_FOUND).toBe("찾을 수 없는 연구예요");
    expect(researchErrorMessage(fetchError(404), "실패")).toBe(RESEARCH_NOT_FOUND);
    expect(RESEARCH_STATE_TEXT).toMatchObject({
      failedTitle: "연구가 도중에 멈췄어요",
      canceledTitle: "취소된 연구예요",
      canceledMessage: "취소한 연구는 이어 갈 수 없어요.\n같은 질문으로 새 연구를 시작할 수 있어요.",
      notFoundMessage: "주소가 맞는지 다시 확인해 주세요.",
      restart: "같은 질문으로 다시 시작",
      backToSearch: "논문 검색으로 돌아가기",
    });
  });

  it("최종 보고서를 받지 못한 안내·409 뒤 맞춘 안내도 해요체(전에는 '…못했습니다. … 다시 시도합니다')", () => {
    expect(RESEARCH_STATE_TEXT.reportFailedOverDraft).toBe(
      "최종 보고서를 불러오지 못했어요.\n잠시 뒤 자동으로 다시 시도해요.\n아래는 작성 중에 받은 초안이에요.",
    );
    expect(RESEARCH_STATE_TEXT.reportFailedTitle).toBe("보고서를 불러오지 못했어요");
    expect(RESEARCH_STATE_TEXT.stateChanged).toBe("그 사이 상태가 바뀌어 최신 상태로 맞췄어요");
    for (const [key, text] of Object.entries(RESEARCH_STATE_TEXT)) {
      expect(text, key).not.toMatch(/습니다|입니다|하세요|합니다/);
    }
  });

  it("[다시 시도] 글 — 보고서 작성 단계(explored)에서 멈췄으면 보고서 작성부터, 그 밖은 다시 시도", () => {
    expect(researchRetryLabel("explored")).toBe("보고서 작성부터 다시 시도");
    expect(researchRetryLabel("exploring")).toBe("다시 시도");
    expect(researchRetryLabel(null)).toBe("다시 시도");
    expect(researchRetryLabel(undefined)).toBe("다시 시도");
  });
});

// 멈춘 연구 카드의 설명 — 서버 last_error 원문을 붙이지 않고 멈춘 단계별 해요체로(api/research.py retry_research·workers/research_tasks.py)
describe("researchFailedMessage — 멈춘 단계별 설명", () => {
  it("계획이 없으면(서버가 재시도를 409 로 거절) 새 연구를 안내한다", () => {
    expect(researchFailedMessage("created", false)).toBe(RESEARCH_STATE_TEXT.failedPlanning);
    expect(RESEARCH_STATE_TEXT.failedPlanning).toBe("연구 계획을 세우다 멈췄어요.\n같은 질문으로 새 연구를 시작할 수 있어요.");
  });

  it("탐색을 마치지 못한 잡은 탐색부터 다시, 탐색을 마친 잡(explored)은 모은 근거가 남아 있다고 알린다", () => {
    expect(researchFailedMessage("planned", true)).toBe("근거를 찾다 멈췄어요.\n다시 시도하면 승인한 계획으로 탐색부터 다시 해요.");
    expect(researchFailedMessage("explored", true)).toBe("보고서를 쓰다 멈췄어요.\n탐색에서 모은 근거는 남아 있어요.");
  });

  it("서버 last_error 원문은 붙이지 않는다 — 깨끗한 한글(해라체)이어도, 예외 원문이어도", () => {
    expect(researchFailedMessage("explored", true, "보고서의 어느 절도 서술을 받지 못했다")).toBe(RESEARCH_STATE_TEXT.failedWriting);
    expect(researchFailedMessage("planned", true, "ConnectionError: [Errno 111] Connection refused")).toBe(RESEARCH_STATE_TEXT.failedExploring);
    expect(researchFailedMessage("created", false, "계획에 하위질문이 없어 탐색하지 않았다 — 새 잡을 만든다")).toBe(RESEARCH_STATE_TEXT.failedPlanning);
  });

  it("알아보는 사유(시간 상한·회수기·전멸)는 해요체로 바꿔 둘째 줄에 넣는다", () => {
    expect(researchFailedMessage("explored", true, "시간 상한 초과 — 워커를 회수했다")).toBe(
      "보고서를 쓰다 멈췄어요.\n정해진 시간 안에 끝나지 않았어요.\n탐색에서 모은 근거는 남아 있어요.",
    );
    expect(researchFailedMessage("planned", true, "모든 하위질문 탐색이 오류로 실패했다")).toBe(
      "근거를 찾다 멈췄어요.\n모든 하위질문의 탐색이 오류로 끝났어요.\n다시 시도하면 승인한 계획으로 탐색부터 다시 해요.",
    );
    expect(researchFailedMessage("created", false, "stale — 워커 응답 없음")).toBe(
      "연구 계획을 세우다 멈췄어요.\n작업이 오래 응답하지 않았어요.\n같은 질문으로 새 연구를 시작할 수 있어요.",
    );
  });

  it("[다시 시도] 글과 같은 갈래다 — 보고서 작성 단계면 '보고서 작성부터 다시 시도'", () => {
    expect(researchRetryLabel("explored")).toBe("보고서 작성부터 다시 시도");
    expect(researchFailedMessage("explored", true)).toContain("보고서를 쓰다");
  });
});

describe("failureReason·subqFailureText — 하위질문 부분 실패의 이유", () => {
  it("알아보는 사유만 해요체로, 그 밖(예외 원문·영문)은 null", () => {
    expect(failureReason("시간 상한 초과 — 워커를 회수했다")).toBe("정해진 시간 안에 끝나지 않았어요.");
    expect(failureReason("stale — 워커 응답 없음")).toBe("작업이 오래 응답하지 않았어요.");
    expect(failureReason("ReadTimeout: timed out")).toBeNull();
    expect(failureReason("임베딩 서버 응답 없음")).toBeNull();
    expect(failureReason(" ")).toBeNull();
    expect(failureReason(null)).toBeNull();
    expect(failureReason(undefined)).toBeNull();
  });

  it("하위질문 오류 줄 — 서버 원문 대신 고정 문구, 알아보는 사유가 있으면 다음 줄에", () => {
    expect(SUBQ_FAILED_TEXT).toBe("오류로 이 하위질문의 탐색을 마치지 못했어요.");
    expect(subqFailureText("httpx.ConnectError: All connection attempts failed")).toBe(SUBQ_FAILED_TEXT);
    expect(subqFailureText(null)).toBe(SUBQ_FAILED_TEXT);
    expect(subqFailureText("시간 상한 초과 — 워커를 회수했다")).toBe(`${SUBQ_FAILED_TEXT}\n정해진 시간 안에 끝나지 않았어요.`);
  });
});

describe("researchConnectionState — 실시간 연결 띠", () => {
  it("스트림이 필요 없는 화면(읽는 중·끝난 잡)은 실패 수와 상관없이 connected", () => {
    expect(researchConnectionState(false, 0)).toBe("connected");
    expect(researchConnectionState(false, 9)).toBe("connected");
  });

  it("끊기면 다시 연결하는 중, 연달아 LOST_AFTER_DROPS 번 실패하면 연결하지 못함", () => {
    expect(LOST_AFTER_DROPS).toBe(3);
    expect(researchConnectionState(true, 0)).toBe("connected");
    expect(researchConnectionState(true, 1)).toBe("reconnecting");
    expect(researchConnectionState(true, LOST_AFTER_DROPS - 1)).toBe("reconnecting");
    expect(researchConnectionState(true, LOST_AFTER_DROPS)).toBe("lost");
    expect(researchConnectionState(true, LOST_AFTER_DROPS + 5)).toBe("lost");
  });
});

describe("researchErrorMessage — 대체 문구를 비우면 이유만(상태 블록의 설명 줄)", () => {
  it("연결 실패·시간 초과는 이유만, 이유가 없으면 빈 글 — ' — ' 로 시작하지 않는다", () => {
    expect(researchErrorMessage(new TypeError("Failed to fetch"), "")).toBe(ERROR_HINTS.network);
    expect(researchErrorMessage(fetchError(500), "")).toBe("");
    expect(researchErrorMessage(new Error("boom"), "")).toBe("");
    expect(researchErrorMessage(fetchError(409), "")).toBe("");
    expect(researchErrorMessage(fetchError(503), "")).toBe(ERROR_HINTS.busy);
  });

  it("백엔드 code(500 internal_error 등)는 서버 detail 대신 화면 문구(CODE_MESSAGES)를 이유로 — code 가 없는 옛 서버는 그대로", () => {
    const internal = Object.assign(new Error("HTTP 500"), {
      status: 500,
      data: { detail: "서버 내부 오류가 발생했어요", code: "internal_error" },
    });
    expect(researchErrorMessage(internal, "연구를 불러오지 못했어요")).toBe(
      "연구를 불러오지 못했어요 — 서버에 문제가 생겼어요.\n잠시 뒤 다시 시도해 주세요.",
    );
    expect(researchErrorMessage(internal, "")).toBe("서버에 문제가 생겼어요.\n잠시 뒤 다시 시도해 주세요.");
    expect(researchErrorMessage(fetchError(500, "Internal"), "실패")).toBe("실패");
  });
});
