// frontend/tests/unit/outlineEdit.test.ts
import { describe, expect, it } from "vitest";
import type { Outline } from "~/types/work";
import { GROUP_LABEL_MAX } from "~/utils/readingList";
import {
  OUTLINE_METHOD_MAX,
  OUTLINE_QUESTION_MAX,
  draftFrom,
  isFallbackOutline,
  movePaper,
  outlineProblems,
  renameGroup,
  toOutlinePut,
  type OutlineDraft,
} from "~/utils/outlineEdit";

function outline(over: Partial<Outline> = {}): Outline {
  return {
    topic: { id: 12, title: "세대 간 지지와 노인 우울", question: "세대 간 지지는 노인 우울을 낮추는가?" },
    basis: "concept",
    groups: [
      { key: "prior.g1", name: "노인의 우울", hint: "노인 우울", papers: ["KCI_A", "KCI_B", "KCI_C"] },
      { key: "prior.g2", name: "사회적 지지", hint: "사회적 지지", papers: ["KCI_D", "KCI_E"] },
    ],
    questions: ["세대 간 지지는 노인 우울을 낮추는가?", "지지의 출처에 따라 효과가 다른가?", "농촌 노인에게도 같은가?"],
    question: null,
    method: "",
    state: "draft",
    gen_id: 41,
    approved_at: null,
    ...over,
  };
}

function draft(over: Partial<OutlineDraft> = {}): OutlineDraft {
  return { ...draftFrom(outline()), question: "세대 간 지지는 노인 우울을 낮추는가?", ...over };
}

describe("draftFrom", () => {
  it("서버가 준 묶음을 순서·배정 그대로 옮기고 힌트는 싣지 않는다", () => {
    expect(draftFrom(outline()).groups).toEqual([
      { key: "prior.g1", name: "노인의 우울", papers: ["KCI_A", "KCI_B", "KCI_C"] },
      { key: "prior.g2", name: "사회적 지지", papers: ["KCI_D", "KCI_E"] },
    ]);
  });

  it("저장된 연구 질문이 없으면 첫 후보에서, 있으면 그 값에서 시작한다", () => {
    expect(draftFrom(outline()).question).toBe("세대 간 지지는 노인 우울을 낮추는가?");
    expect(draftFrom(outline({ question: "다듬은 질문?", method: "설문" }))).toMatchObject({
      question: "다듬은 질문?",
      method: "설문",
    });
    expect(draftFrom(outline({ questions: [] })).question).toBe("");
  });

  it("논문 목록은 사본이다 — 고치는 동안 저장된 목차가 바뀌지 않는다", () => {
    const saved = outline();
    draftFrom(saved).groups[0]!.papers.push("KCI_Z");
    expect(saved.groups[0]!.papers).toEqual(["KCI_A", "KCI_B", "KCI_C"]);
  });
});

describe("movePaper", () => {
  it("논문을 다른 묶음 끝으로 옮기고 원래 묶음에서 뺀다", () => {
    const moved = movePaper(draft(), "KCI_B", "prior.g2");
    expect(moved.groups.map((g) => g.papers)).toEqual([
      ["KCI_A", "KCI_C"],
      ["KCI_D", "KCI_E", "KCI_B"],
    ]);
  });

  it("없는 논문·없는 묶음·이미 그 묶음이면 같은 초안을 그대로 돌려준다", () => {
    const d = draft();
    expect(movePaper(d, "KCI_X", "prior.g2")).toBe(d);
    expect(movePaper(d, "KCI_A", "prior.g9")).toBe(d);
    expect(movePaper(d, "KCI_A", "prior.g1")).toBe(d);
  });

  it("마지막 논문을 옮겨 묶음이 비는 것은 막지 않는다 — 저장 전에 outlineProblems 가 알린다", () => {
    let d = draft();
    d = movePaper(d, "KCI_D", "prior.g1");
    d = movePaper(d, "KCI_E", "prior.g1");
    expect(d.groups[1]!.papers).toEqual([]);
    expect(outlineProblems(d, false)).toEqual(["「사회적 지지」 묶음이 비었습니다 — 논문을 하나 이상 옮겨 두세요"]);
  });
});

describe("renameGroup", () => {
  it("그 묶음의 이름만 바꾸고 없는 묶음이면 그대로 돌려준다", () => {
    const d = draft();
    const renamed = renameGroup(d, "prior.g2", "가족 지지");
    expect(renamed.groups.map((g) => g.name)).toEqual(["노인의 우울", "가족 지지"]);
    expect(renamed.groups[0]).toBe(d.groups[0]);
    expect(renameGroup(d, "prior.g9", "x")).toBe(d);
  });
});

describe("outlineProblems", () => {
  it("묶음마다 이름·논문이 있고 질문을 골랐으면 문제가 없다", () => {
    expect(outlineProblems(draft(), false)).toEqual([]);
    expect(outlineProblems(draft(), true)).toEqual([]);
  });

  it("묶음 이름이 비거나 너무 길면 알린다(서버 422 와 같은 기준)", () => {
    let d = renameGroup(draft(), "prior.g1", "  ");
    d = renameGroup(d, "prior.g2", "가".repeat(GROUP_LABEL_MAX + 1));
    expect(outlineProblems(d, false)).toEqual([
      "1번째 묶음의 이름을 적어 주세요",
      `2번째 묶음 이름은 ${GROUP_LABEL_MAX}자까지입니다`,
    ]);
    expect(outlineProblems(renameGroup(draft(), "prior.g2", "가".repeat(GROUP_LABEL_MAX)), false)).toEqual([]);
  });

  it("연구 질문은 승인할 때만 2자 이상이어야 한다 — 저장은 질문 없이도 된다", () => {
    const d = draft({ question: " 가 " });
    expect(outlineProblems(d, false)).toEqual([]);
    expect(outlineProblems(d, true)).toEqual(["승인하려면 연구 질문을 고르거나 적어 주세요"]);
  });

  it("질문·방법의 글자 수는 코드 포인트로 센다(서버의 파이썬 len 과 같다)", () => {
    expect(outlineProblems(draft({ question: "😀".repeat(OUTLINE_QUESTION_MAX) }), true)).toEqual([]);
    expect(outlineProblems(draft({ question: "가".repeat(OUTLINE_QUESTION_MAX + 1) }), false)).toEqual([
      `연구 질문은 ${OUTLINE_QUESTION_MAX}자까지입니다`,
    ]);
    expect(outlineProblems(draft({ method: "가".repeat(OUTLINE_METHOD_MAX + 1) }), false)).toEqual([
      `방법은 ${OUTLINE_METHOD_MAX}자까지입니다`,
    ]);
  });
});

describe("toOutlinePut", () => {
  it("묶음 키·논문 순서를 그대로 싣고 이름·질문·방법의 앞뒤 공백을 지운다", () => {
    const d = renameGroup(draft({ question: "  다듬은 질문?  ", method: " 설문 조사 \n" }), "prior.g1", " 노인 우울 ");
    expect(toOutlinePut(d, true)).toEqual({
      groups: [
        { key: "prior.g1", name: "노인 우울", papers: ["KCI_A", "KCI_B", "KCI_C"] },
        { key: "prior.g2", name: "사회적 지지", papers: ["KCI_D", "KCI_E"] },
      ],
      question: "다듬은 질문?",
      method: "설문 조사",
      approve: true,
    });
    expect(toOutlinePut(d, false).approve).toBe(false);
  });
});

describe("isFallbackOutline", () => {
  it("연구 질문 후보가 둘 미만이면 기본값으로 끝난 목차다", () => {
    expect(isFallbackOutline(outline({ questions: ["세대 간 지지는 노인 우울을 낮추는가?"] }))).toBe(true);
    expect(isFallbackOutline(outline())).toBe(false);
  });
});
