// frontend/tests/unit/proposalView.test.ts
import { describe, expect, it } from "vitest";
import type {
  Outline,
  Paragraph,
  ParaState,
  ProposalSection,
  ProposalView,
  WorkGeneration,
  WorkState,
} from "~/types/work";
import {
  GAP_NOTE,
  MAX_PARAGRAPH_CHARS,
  SECTION_LABELS,
  acceptParagraph,
  addParagraph,
  checkLine,
  editParagraph,
  footprint,
  footprintLine,
  openParagraphGens,
  paragraphParts,
  paragraphProblem,
  paragraphViews,
  removeParagraph,
  sectionLabel,
  sectionStatus,
} from "~/utils/proposalView";

const NO_CHECKS = { dropped: 0, dropped_f: 0, unmarked: 0, numbers: [], softened: 0 };

function para(id: string, state: ParaState, text = `${id} 문단 [E1].`): Paragraph {
  return { id, text, state, cites: ["KCI_A"], checks: NO_CHECKS, gen_id: 50 };
}

function section(paragraphs: Paragraph[], over: Partial<ProposalSection> = {}): ProposalSection {
  return {
    key: "prior.g1",
    gen_id: 50,
    evidence: { E1: "KCI_A", E2: "KCI_B" },
    figures: [{ id: "F1", label: "이 절에 준 논문 수", value: "6" }],
    basis: { topic_id: 12, papers: ["KCI_A", "KCI_B"] },
    note: null,
    paragraphs,
    model: "gemma-3-12b",
    updated_at: "2026-10-14T06:00:00Z",
    ...over,
  };
}

function outline(): Outline {
  return {
    topic: { id: 12, title: "세대 간 지지와 노인 우울", question: "q?" },
    basis: "concept",
    groups: [{ key: "prior.g1", name: "노인의 우울", hint: "노인 우울", papers: ["KCI_A"] }],
    questions: ["a?", "b?"],
    question: "a?",
    method: "",
    state: "approved",
    gen_id: 41,
    approved_at: "2026-10-14T05:00:00Z",
  };
}

function proposal(sections: Record<string, ProposalSection>): ProposalView {
  return {
    version: 3,
    outline: outline(),
    sections,
    drafts: {},
    papers: {},
    references: {},
    corpus: null,
    stale: { outline: false, sections: {} },
    disclosure: { steps: [] },
  };
}

function gen(id: number, status: WorkGeneration["status"], target = "prior.g1"): WorkGeneration {
  return { id, kind: "section", target, status, model: null, error: null, position: null };
}

function state(gens: WorkGeneration[], sections: Record<string, ProposalSection> = {}): WorkState {
  return {
    work: {
      id: "job",
      phase: "proposal",
      concepts: [],
      memo: null,
      is_example: false,
      progress: {},
      generations: gens,
    },
    topics: null,
    reading: null,
    proposal: proposal(sections),
    live: {},
  };
}

describe("SECTION_LABELS · sectionLabel", () => {
  it("고정 6절을 문서 순서대로 둔다", () => {
    expect(Object.keys(SECTION_LABELS)).toEqual(["topic", "background", "prior", "gap", "question", "method"]);
    expect(Object.values(SECTION_LABELS)).toEqual(["주제", "연구 배경", "선행연구 검토", "연구 공백", "연구 질문", "방법 제안"]);
  });

  it("선행연구 묶음은 목차의 묶음 이름으로, 나머지는 절 이름으로 부른다", () => {
    expect(sectionLabel("prior.g1", outline())).toBe("선행연구 검토 · 노인의 우울");
    expect(sectionLabel("prior.g3", outline())).toBe("선행연구 검토");
    expect(sectionLabel("gap", outline())).toBe("연구 공백");
    expect(sectionLabel("gap", null)).toBe("연구 공백");
  });

  it("연구 공백 문구는 서버와 같다", () => {
    expect(GAP_NOTE).toBe("소장 코퍼스에서 확인하지 않은 공백 후보");
  });
});

describe("sectionStatus", () => {
  it("생성이 없고 절도 없으면 empty, 열린 생성은 queued·writing", () => {
    expect(sectionStatus("prior.g1", state([]))).toBe("empty");
    expect(sectionStatus("prior.g1", state([gen(51, "queued")]))).toBe("queued");
    expect(sectionStatus("prior.g1", state([gen(51, "running")]))).toBe("writing");
    // 워커는 running 이벤트를 보내지 않는다(계약 §7) — queued 로 알던 생성이라도 그 생성의 조각이 왔으면 쓰는 중이다
    const writing = { ...state([gen(51, "queued")]), live: { "prior.g1": { genId: 51, text: "", nextSeq: 1, broken: false } } };
    expect(sectionStatus("prior.g1", writing)).toBe("writing");
    // 다른 생성(옛 생성)의 글은 쓰는 중의 근거가 아니다
    const other = { ...state([gen(51, "queued")]), live: { "prior.g1": { genId: 50, text: "x", nextSeq: 3, broken: false } } };
    expect(sectionStatus("prior.g1", other)).toBe("queued");
    // 다른 절의 생성은 보지 않는다
    expect(sectionStatus("prior.g1", state([gen(51, "running", "gap")]))).toBe("empty");
  });

  it("쓴 절이 있으면 done — 그 절보다 나중의 생성이 실패했을 때만 failed", () => {
    const sections = { "prior.g1": section([para("p1", "proposed")]) };
    expect(sectionStatus("prior.g1", state([gen(50, "done")], sections))).toBe("done");
    expect(sectionStatus("prior.g1", state([gen(50, "done"), gen(52, "failed")], sections))).toBe("failed");
    expect(sectionStatus("prior.g1", state([gen(49, "failed"), gen(50, "done")], sections))).toBe("done");
    expect(sectionStatus("prior.g1", state([gen(52, "failed")]))).toBe("failed");
  });

  it("끝났지만 절에 아직 반영되지 않은 생성 — 빈 결과(model 없음)는 실패, 결과가 있으면 다시 읽기 전까지 쓰는 중", () => {
    const done = (id: number, model: string | null): WorkGeneration => ({ ...gen(id, "done"), model });
    // 처음 쓰는 절: 세 번 다 검사를 못 넘어 빈 결과로 끝났다 — 서버는 절을 만들지 않고 retry 를 받는다
    expect(sectionStatus("prior.g1", state([done(51, null)]))).toBe("failed");
    // 결과가 있는 done — 계획서를 다시 읽기 전까지 '쓰기 전' 으로 돌아가지 않는다
    expect(sectionStatus("prior.g1", state([done(51, "gemma-3-12b")]))).toBe("writing");
    // 다시 쓰던 절: 빈 결과는 옛 문단을 남긴 채 실패, 결과가 있으면 옛 문단 대신 쓰는 중
    const sections = { "prior.g1": section([para("p1", "accepted")]) };
    expect(sectionStatus("prior.g1", state([done(50, "gemma-3-12b"), done(52, null)], sections))).toBe("failed");
    expect(sectionStatus("prior.g1", state([done(50, "gemma-3-12b"), done(52, "gemma-3-12b")], sections))).toBe(
      "writing",
    );
    // 다시 읽어 절이 그 생성의 것이 되면 씀
    const reread = { "prior.g1": section([para("p1", "proposed")], { gen_id: 52 }) };
    expect(sectionStatus("prior.g1", state([done(50, "gemma-3-12b"), done(52, "gemma-3-12b")], reread))).toBe("done");
  });

  it("취소는 실패로 보이지 않는다", () => {
    expect(sectionStatus("prior.g1", state([gen(52, "canceled")]))).toBe("empty");
    const sections = { "prior.g1": section([para("p1", "accepted")]) };
    expect(sectionStatus("prior.g1", state([gen(52, "canceled")], sections))).toBe("done");
  });
});

describe("paragraphParts", () => {
  it("근거 지도에 있는 [E#] 는 칩, 없는 번호는 badcite, [F#] 는 수치 칩이다", () => {
    expect(paragraphParts("가 [E1] 나 [E9] 다 [F1].", { E1: "KCI_A" })).toEqual([
      { type: "text", text: "가 " },
      { type: "cite", eid: "E1" },
      { type: "text", text: " 나 " },
      { type: "badcite", eid: "E9" },
      { type: "text", text: " 다 " },
      { type: "figure", fid: "F1" },
      { type: "text", text: "." },
    ]);
  });

  it("스트리밍 끝에 걸린 미완성 표기는 글자로 둔다", () => {
    expect(paragraphParts("가 [E1] 나 [E", { E1: "KCI_A" })).toEqual([
      { type: "text", text: "가 " },
      { type: "cite", eid: "E1" },
      { type: "text", text: " 나 [E" },
    ]);
  });
});

describe("paragraphViews · openParagraphGens", () => {
  it("문단마다 문장·문장의 칩 조각·검사 한 줄을 한 번에 나눈다", () => {
    const checks = { ...NO_CHECKS, numbers: ["9"] };
    const sec = section([{ ...para("p1", "proposed", "가 [E1]. 9편이다 [E9]."), checks }, para("p2", "accepted")]);
    const [first, second] = paragraphViews(sec);
    expect(first!.p.id).toBe("p1");
    expect(first!.sentences.map((s) => [s.text, s.unmarked, s.numbers])).toEqual([
      ["가 [E1]. ", false, []],
      ["9편이다 [E9].", false, ["9"]],
    ]);
    expect(first!.sentences[1]!.parts).toEqual([
      { type: "text", text: "9편이다 " },
      { type: "badcite", eid: "E9" },
      { type: "text", text: "." },
    ]);
    expect(first!.check).toBe("확인 필요한 숫자 1개");
    expect(second!.check).toBeNull();
  });

  it("이 절의 문단마다 열린 다시 쓰기 생성만 고른다 — 끝난 생성·다른 절·목록에 없는 문단은 빼고 같은 문단은 가장 새 것", () => {
    const pgen = (id: number, status: WorkGeneration["status"], target: string): WorkGeneration => ({
      ...gen(id, status, target),
      kind: "paragraph",
    });
    const work = state([
      pgen(60, "queued", "prior.g1#p1"),
      pgen(61, "running", "prior.g1#p1"),
      pgen(62, "done", "prior.g1#p2"),
      pgen(63, "queued", "gap#p2"),
      pgen(64, "queued", "prior.g1#p9"),
      gen(65, "running", "prior.g1"),
    ]).work;
    const open = openParagraphGens(work, "prior.g1", ["p1", "p2"]);
    expect([...open.entries()].map(([pid, g]) => [pid, g.id])).toEqual([["p1", 61]]);
    expect(openParagraphGens(null, "prior.g1", ["p1"]).size).toBe(0);
  });
});

describe("footprint · footprintLine", () => {
  it("모든 절의 문단 상태를 센다", () => {
    const p = proposal({
      "prior.g1": section([para("p1", "accepted"), para("p2", "edited"), para("p3", "proposed")]),
      gap: section([para("p1", "accepted"), para("p2", "authored")], { key: "gap" }),
    });
    expect(footprint(p)).toEqual({ proposed: 1, accepted: 2, edited: 1, authored: 1 });
  });

  it("AI 제안 = 검토 전 + 수락 + 수정, 사용자 작성은 따로 적는다", () => {
    expect(footprintLine({ proposed: 0, accepted: 7, edited: 2, authored: 0 })).toBe("AI 제안 9문단 중 수락 7·수정 2");
    expect(footprintLine({ proposed: 2, accepted: 5, edited: 2, authored: 1 })).toBe(
      "AI 제안 9문단 중 수락 5·수정 2·검토 전 2 · 직접 쓴 문단 1",
    );
    expect(footprintLine({ proposed: 0, accepted: 0, edited: 0, authored: 3 })).toBe("직접 쓴 문단 3");
    expect(footprintLine({ proposed: 0, accepted: 0, edited: 0, authored: 0 })).toBe("아직 쓴 문단이 없습니다");
  });
});

describe("checkLine · paragraphProblem", () => {
  it("서버 검사 결과를 한 줄로 — 아무것도 없으면 null", () => {
    expect(checkLine(NO_CHECKS)).toBeNull();
    expect(checkLine({ dropped: 1, dropped_f: 2, unmarked: 1, numbers: ["9", "2017"], softened: 1 })).toBe(
      "인용 1개 버림 · 수치 표기 2개 버림 · 단정 표현 1곳 고침 · 근거 표시 없는 문장 1 · 확인 필요한 숫자 2개",
    );
  });

  it("빈 문단·상한을 넘는 문단은 저장 전에 막는다", () => {
    expect(paragraphProblem("  ")).toBe("빈 문단은 저장할 수 없습니다 — 지우려면 [지우기]를 누르세요");
    expect(paragraphProblem("가".repeat(MAX_PARAGRAPH_CHARS))).toBeNull();
    expect(paragraphProblem("가".repeat(MAX_PARAGRAPH_CHARS + 1))).toBe(`문단은 ${MAX_PARAGRAPH_CHARS}자까지입니다`);
  });
});

describe("절 PUT 본문", () => {
  const sec = section([para("p1", "proposed"), para("p2", "accepted"), para("p3", "authored", "직접 쓴 글.")]);

  it("고친 문단만 글과 상태(edited)가 바뀌고 나머지는 그대로 실린다", () => {
    expect(editParagraph(sec, "p1", "새 글 [E2].")).toEqual({
      paragraphs: [
        { id: "p1", text: "새 글 [E2].", state: "edited" },
        { id: "p2", text: "p2 문단 [E1].", state: "accepted" },
        { id: "p3", text: "직접 쓴 글.", state: "authored" },
      ],
    });
  });

  it("사용자가 쓴 문단을 고쳐도 사용자 작성이고, 글이 같으면 상태를 바꾸지 않는다", () => {
    expect(editParagraph(sec, "p3", "고친 글.").paragraphs[2]).toEqual({ id: "p3", text: "고친 글.", state: "authored" });
    expect(editParagraph(sec, "p1", "p1 문단 [E1].").paragraphs[0]).toEqual({
      id: "p1",
      text: "p1 문단 [E1].",
      state: "proposed",
    });
  });

  it("수락은 AI 제안만 accepted 로 바꾼다", () => {
    expect(acceptParagraph(sec, "p1").paragraphs.map((p) => p.state)).toEqual(["accepted", "accepted", "authored"]);
    expect(acceptParagraph(sec, "p3").paragraphs.map((p) => p.state)).toEqual(["proposed", "accepted", "authored"]);
  });

  it("지우기는 그 문단을 빼고, 더하기는 id 없는 사용자 작성 문단을 끝에 붙인다", () => {
    expect(removeParagraph(sec, "p2").paragraphs.map((p) => p.id)).toEqual(["p1", "p3"]);
    expect(addParagraph(sec, "더한 글.").paragraphs.at(-1)).toEqual({ id: null, text: "더한 글.", state: "authored" });
    expect(addParagraph(sec, "더한 글.").paragraphs).toHaveLength(4);
  });
});
