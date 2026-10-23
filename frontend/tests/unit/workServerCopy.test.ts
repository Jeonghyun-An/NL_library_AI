// frontend/tests/unit/workServerCopy.test.ts
// 연구 작업대(이어간 연구 — 제목 고르기·참고문헌 선택하기·보고서) API 가 화면에 보이라고 지은 오류 문구(detail).
// 화면은 깨끗한 한글 문장이면 서버 문구를 그대로 보인다(apiErrors.serverMessage → researchErrors.workErrorMessage·researchErrorMessage).
// 아래 글은 서버 원문을 그대로 옮긴 것이다 — app/api/research_work.py·research_topics.py·research_reading.py·research_proposal.py,
// app/services/research_work/enqueue.py(OPEN_SAME). 서버 문구를 고치면 여기도 함께 고친다.
// 개발자용 문구(필드·헤더 이름·상태 값이 섞임 — 'state 는 비울 수 없습니다'·'If-Match 가 필요합니다'·'같은 문단 id 가 두 번 있습니다'·
// '다시 부를 수 없는 상태입니다: failed')는 화면이 숨기므로 여기 없다
import { describe, expect, it } from "vitest";
import { serverMessage } from "~/utils/apiErrors";
import { researchErrorMessage, workErrorMessage } from "~/utils/researchErrors";

function fetchError(status: number, detail?: unknown) {
  return Object.assign(new Error(`HTTP ${status}`), { status, statusCode: status, data: detail === undefined ? undefined : { detail } });
}

// [HTTP 상태, 서버 문구]
const WORK_DETAILS: [number, string][] = [
  // api/research_work.py
  [404, "이어간 연구를 찾을 수 없어요"],
  [409, "예시 연구는 읽기 전용이에요"],
  [404, "작업을 찾을 수 없어요"],
  [409, "완료된 DeepResearch만 이어갈 수 있어요"],
  [409, "단계를 되돌릴 수 없어요"],
  [422, "키워드를 1개 이상 넣어 주세요"],
  [409, "키워드를 만드는 중이에요 — 끝난 뒤 고쳐 주세요"],
  [409, "진행 중인 작업은 끝날 때까지 기다려야 해요"],
  [409, "취소할 수 없는 상태예요"],
  [409, "같은 작업이 이미 대기 중이거나 진행 중이에요"],
  [409, "더 새로운 작업이 있어요 — 최신 작업에서 다시 불러 주세요"],
  // api/research_topics.py
  [409, "다른 방향으로 더 받을 카드가 없어요"],
  [404, "주제를 찾을 수 없어요"],
  [409, "카드를 만드는 중이에요 — 끝난 뒤 고쳐 주세요"],
  [409, "카드가 아직 없어요"],
  [422, "빈 카드는 제목과 연구 질문을 함께 보내 주세요"],
  [409, "키워드를 고르는 중이에요 — 끝난 뒤 다시 만들어 주세요"],
  [409, "키워드를 2개 이상 골라 주세요"],
  [409, "다시 만들 AI 카드가 없어요"],
  // api/research_reading.py
  [404, "논문을 찾을 수 없어요"],
  // api/research_proposal.py
  [409, "주제를 먼저 골라 주세요"],
  [409, "담은 논문이 5편 이상이어야 보고서를 만들 수 있어요"],
  [409, "목차를 만드는 중이에요"],
  [404, "목차를 찾을 수 없어요"],
  [422, "묶음이 저장된 목차와 달라요"],
  [422, "묶음의 논문이 저장된 목차와 달라요"],
  [422, "한 논문이 두 묶음에 들어 있어요"],
  [422, "빈 묶음이 있어요"],
  [422, "묶음 이름을 써 주세요"],
  [422, "목차를 승인하려면 연구 질문을 2자 이상 써 주세요"],
  [422, "이 절은 아직 쓸 수 없어요"],
  [409, "목차를 먼저 승인해 주세요"],
  [404, "묶음을 찾을 수 없어요"],
  [409, "이 절을 쓰는 중이에요"],
  [404, "절을 찾을 수 없어요"],
  [422, "검사 뒤 문단이 3000자를 넘어요 — 단정 표현을 고치면서 늘었을 수 있으니 조금 줄여 주세요"],
  [404, "문단을 찾을 수 없어요"],
  [409, "다시 쓸 수 없는 문단이에요"],
  [409, "이 절을 쓴 작업 기록이 없어 문단을 다시 쓸 수 없어요"],
  [404, "이 절의 작업 기록이 아니에요"],
];

// 구조화 detail({code, message, …}) — 화면은 message 를 읽는다
const STRUCTURED: [number, Record<string, unknown>][] = [
  [409, { code: "version_conflict", version: 3, message: "다른 곳에서 보고서가 바뀌었어요 — 다시 불러온 뒤 고쳐 주세요" }],
  [409, { code: "no_section_papers", message: "이 절에 넣을 논문이 없어요" }],
];

const ALL_TEXTS = [...WORK_DETAILS.map(([, text]) => text), ...STRUCTURED.map(([, d]) => String(d.message))];

describe("연구 작업대 서버 문구 — 화면이 그대로 보인다", () => {
  it.each(WORK_DETAILS)("%i %s", (status, text) => {
    expect(serverMessage(text)).toBe(text);
    expect(workErrorMessage(fetchError(status, text), "실패")).toBe(text);
  });

  it.each(STRUCTURED)("%i 구조화 detail", (status, detail) => {
    expect(serverMessage(detail)).toBe(detail.message);
    expect(workErrorMessage(fetchError(status, detail), "실패")).toBe(detail.message);
  });

  it("[이 연구 이어가기]의 409 는 딥리서치 화면(researchErrorMessage)에서도 그대로", () => {
    const text = "완료된 DeepResearch만 이어갈 수 있어요";
    expect(researchErrorMessage(fetchError(409, text), "연구를 이어가지 못했어요")).toBe(text);
  });
});

describe("연구 작업대 서버 문구 — 해요체 한 문장", () => {
  it.each(ALL_TEXTS)("%s", (text) => {
    // 해요체로 끝난다('~요') — 합쇼체(습니다·입니다)·명령(하세요 — '~해 주세요'는 된다)·해라체(~다)가 아니다
    expect(text).toMatch(/요$/);
    expect(text).not.toMatch(/(습니다|입니다|합니다|십시오)/);
    if (text.endsWith("세요")) expect(text).toMatch(/ 주세요$/);
    // 한 문장 — 한 줄에 두 문장을 잇지 않고(errorCopyLineBreaks 규칙), 끝에 마침표를 붙이지 않는다(core/errors.py 와 같다)
    expect(text).not.toMatch(/[.?!] \S/);
    expect(text).not.toContain("\n");
    expect(text).not.toMatch(/\.$/);
  });
});
