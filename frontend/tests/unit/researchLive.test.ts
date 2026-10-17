// frontend/tests/unit/researchLive.test.ts
import { describe, expect, it } from "vitest";
import type { RoundView, SubqView } from "~/types/research";
import { doneSummary, liveNowLine, liveRunning, roundSteps } from "~/utils/researchLive";

function round(over: Partial<RoundView> = {}): RoundView {
  return {
    round: 1,
    query: "노인 우울 사회적 지지",
    foundChunks: null,
    newPapers: null,
    verdict: null,
    note: "",
    nextQuery: null,
    excluded: null,
    excludedPapers: [],
    flagged: null,
    adoptedPapers: [],
    ...over,
  };
}

function subq(idx: number, over: Partial<SubqView> = {}): SubqView {
  return {
    idx,
    title: `하위질문 ${idx + 1}`,
    seq: null,
    status: "pending",
    rounds: [],
    verdict: null,
    note: "",
    adopted: null,
    parseFailed: false,
    error: null,
    ...over,
  };
}

describe("liveRunning · liveNowLine — 지금 AI가 하는 일 한 줄", () => {
  it("도는 하위질문이 없으면 다음을 준비하거나 마무리하는 중", () => {
    expect(liveRunning([subq(0, { status: "done" }), subq(1)])).toBeNull();
    expect(liveNowLine([subq(0, { status: "done" }), subq(1)])).toBe("다음 하위질문을 준비하고 있어요");
    expect(liveNowLine([subq(0, { status: "done" }), subq(1, { status: "done" })])).toBe("탐색을 마무리하고 있어요");
  });

  it("도는 하위질문의 마지막 회차로 지금 일을 말한다 — 검색 → 점검 → 다시 찾기 → 확인", () => {
    const at = (rounds: RoundView[]) => liveNowLine([subq(0, { status: "done" }), subq(1, { status: "running", rounds }), subq(2)]);
    expect(at([])).toBe("하위질문 2/3 — 검색어를 정해 논문을 찾고 있어요");
    expect(at([round({ foundChunks: 12 })])).toBe("하위질문 2/3 — 찾은 대목 12개를 질문에 맞는지 스스로 점검하고 있어요");
    expect(at([round()])).toBe("하위질문 2/3 — 찾은 논문을 질문에 맞는지 스스로 점검하고 있어요");
    expect(at([round({ verdict: "insufficient", nextQuery: "농촌 노인 우울" })])).toBe(
      "하위질문 2/3 — 근거가 부족해 ‘농촌 노인 우울’(으)로 다시 찾고 있어요",
    );
    expect(at([round({ verdict: "sufficient" })])).toBe("하위질문 2/3 — 근거를 확인했어요");
  });

  it("이전 시도에 남은 running 행은 지금 도는 하위질문이 아니다(재시도)", () => {
    // 이번 시도는 하위질문 0(seq 10)부터 — seq 5 인 하위질문 1 의 running 행은 앞 시도의 것
    const subqs = [subq(0, { seq: 10, status: "done" }), subq(1, { seq: 5, status: "running" }), subq(2)];
    expect(liveRunning(subqs)).toBeNull();
  });
});

describe("roundSteps — 한 회차의 단계", () => {
  it("검색 단계는 찾은 대목·새 논문 수를 붙인다", () => {
    const [search] = roundSteps(round({ foundChunks: 12, newPapers: 4 }), false);
    expect(search).toMatchObject({ kind: "search", title: "‘노인 우울 사회적 지지’(으)로 찾음", detail: "대목 12개 · 새 논문 4편", pending: false });
  });

  it("판정 전이면 지금 도는 회차에만 '자기점검 중'(깜빡임)을 단다", () => {
    expect(roundSteps(round(), true).map((s) => [s.kind, s.title, s.pending])).toEqual([
      ["search", "‘노인 우울 사회적 지지’(으)로 찾음", false],
      ["check", "자기점검 중", true],
    ]);
    expect(roundSteps(round(), false).map((s) => s.kind)).toEqual(["search"]);
  });

  it("판정은 결(충분 ok · 부족 warn)과 메모·제외 수를 싣고, 다음 검색어가 있으면 다시 찾기 단계를 단다", () => {
    const steps = roundSteps(round({ verdict: "insufficient", note: "국내 연구가 적음", excluded: 2, nextQuery: "농촌 노인 우울" }), true);
    expect(steps.map((s) => [s.kind, s.title, s.detail, s.tone, s.pending])).toEqual([
      ["search", "‘노인 우울 사회적 지지’(으)로 찾음", null, null, false],
      ["check", "자기점검 · 근거 부족", "국내 연구가 적음 · 무관 2편 제외", "warn", false],
      ["recheck", "‘농촌 노인 우울’(으)로 다시 찾기", null, "warn", true],
    ]);
    expect(roundSteps(round({ verdict: "sufficient" }), false)[1]).toMatchObject({ title: "자기점검 · 근거 충분", tone: "ok", detail: null });
  });
});

describe("doneSummary — 접어 둔 끝난 하위질문 한 줄", () => {
  it("근거 편수·회차 수, 둘 다 모르면 '완료'", () => {
    expect(doneSummary(subq(0, { status: "done", adopted: 5, rounds: [round(), round({ round: 2 })] }))).toBe("근거 5편 · 2회차");
    expect(doneSummary(subq(0, { status: "done" }))).toBe("완료");
  });
});
