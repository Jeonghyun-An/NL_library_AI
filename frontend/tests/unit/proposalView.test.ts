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
  WorkView,
} from "~/types/work";
import {
  GAP_NOTE,
  MAX_PARAGRAPH_CHARS,
  SECTION_LABELS,
  acceptParagraph,
  addParagraph,
  autoChainOn,
  autoTargets,
  checkLine,
  docToc,
  editParagraph,
  failedParagraphGens,
  footprint,
  footprintLine,
  isNoSectionPapers,
  nextAutoSection,
  openParagraphGens,
  outlineBackground,
  paragraphParts,
  paragraphProblem,
  paragraphViews,
  removeParagraph,
  reportBar,
  sectionKeysOf,
  sectionLabel,
  sectionStatus,
} from "~/utils/proposalView";
import { FINAL_STEP_NAME } from "~/utils/workPhase";

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

  it("글을 얻지 못하고 끝난 다시 쓰기의 문단만 고른다 — 그 문단을 쓴 생성보다 나중이고, 실패나 빈 결과(model 없음)인 것", () => {
    // 서버는 끝내 검사를 못 넘은 다시 쓰기(입력을 옮긴 답 등)의 문단을 그대로 둔다 — 화면이 알리지 않으면 [다시]가 듣지 않은 듯 보인다
    const pgen = (id: number, status: WorkGeneration["status"], pid: string, model: string | null = null) => ({
      ...gen(id, status, `prior.g1#${pid}`),
      kind: "paragraph" as const,
      model,
    });
    const sec = section([
      para("p1", "proposed"), // 빈 결과로 끝남 → 고른다
      para("p2", "accepted"), // 실패 → 고른다
      para("p3", "proposed"), // 결과가 있다(반영 전) → 빼기
      para("p4", "proposed"), // 그 문단보다 옛 생성 → 빼기
      para("p5", "edited"), // 사용자가 고친 문단 → 빼기
      para("p6", "proposed"), // 실패 뒤 다시 눌러 열린 생성이 가장 새 것 → 빼기
    ]);
    const work = state([
      pgen(60, "done", "p1"),
      pgen(61, "failed", "p2"),
      pgen(62, "done", "p3", "gemma-3-12b"),
      pgen(40, "done", "p4"),
      pgen(63, "done", "p5"),
      pgen(64, "failed", "p6"),
      pgen(65, "queued", "p6"),
    ]).work;
    expect([...failedParagraphGens(work, "prior.g1", sec.paragraphs)]).toEqual(["p1", "p2"]);
    expect(failedParagraphGens(null, "prior.g1", sec.paragraphs).size).toBe(0);
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

// ── 보고서 자동 산출(06e D20) ─────────────────────────────────
// 묶음 둘(prior.g1·prior.g2) + 연구 공백 = 자동으로 쓰는 절 셋. [보고서 만들기]의 반영이 자동 승인한 목차(auto)다
function autoOutline(over: Partial<Outline> = {}): Outline {
  return {
    ...outline(),
    groups: [
      { key: "prior.g1", name: "노인의 우울", hint: "노인 우울", papers: ["KCI_A"] },
      { key: "prior.g2", name: "세대 간 지지", hint: "사회적 지지", papers: ["KCI_B"] },
    ],
    auto: true,
    ...over,
  };
}

function autoProposal(over: Partial<ProposalView> = {}): ProposalView {
  return { ...proposal({}), outline: autoOutline(), section_gens: {}, ...over };
}

// 화면 상태 — 계획서는 p, 생성 목록은 gens(연구의 다른 칸은 over 로 바꾼다)
function autoState(p: ProposalView, gens: WorkGeneration[] = [], over: Partial<WorkView> = {}): WorkState {
  const s = state(gens);
  return { ...s, work: { ...s.work!, ...over }, proposal: p };
}

function outlineGen(id: number, status: WorkGeneration["status"]): WorkGeneration {
  return { ...gen(id, status, "outline"), kind: "outline" };
}

describe("sectionKeysOf — 자동으로 쓰는 절의 차례", () => {
  it("목차 묶음 순서 → 연구 공백, 목차가 없으면 연구 공백만(printedKeys 와 같은 범위)", () => {
    expect(sectionKeysOf(autoProposal())).toEqual(["prior.g1", "prior.g2", "gap"]);
    const reversed = autoOutline({ groups: [...autoOutline().groups].reverse() });
    expect(sectionKeysOf(autoProposal({ outline: reversed }))).toEqual(["prior.g2", "prior.g1", "gap"]);
    expect(sectionKeysOf(autoProposal({ outline: null }))).toEqual(["gap"]);
  });
});

describe("autoChainOn — 자동 산출이 도는 조건", () => {
  it("승인·auto·예시 아님·목차 생성 없음이면 돈다", () => {
    const p = autoProposal();
    expect(autoChainOn(p, autoState(p).work)).toBe(true);
    // 끝난 목차 생성은 막지 않는다
    expect(autoChainOn(p, autoState(p, [outlineGen(40, "done")]).work)).toBe(true);
  });

  it("06b 목차(auto 없음)·auto false 는 돌지 않는다 — [보고서 만들기]를 누르지 않은 연구의 남은 절을 쓰지 않는다", () => {
    const before06e: Outline = { ...autoOutline() };
    delete before06e.auto;
    const old = autoProposal({ outline: before06e });
    expect(autoChainOn(old, autoState(old).work)).toBe(false);
    const off = autoProposal({ outline: autoOutline({ auto: false }) });
    expect(autoChainOn(off, autoState(off).work)).toBe(false);
  });

  it("초안 목차는 돌지 않는다 — 질문이 없어 자동 승인하지 못했거나 [목차 고치기]에서 승인을 푼 목차", () => {
    const p = autoProposal({ outline: autoOutline({ state: "draft", approved_at: null }) });
    expect(autoChainOn(p, autoState(p).work)).toBe(false);
  });

  it("예시 연구는 돌지 않는다(쓰기가 409)", () => {
    const p = autoProposal();
    expect(autoChainOn(p, autoState(p, [], { is_example: true }).work)).toBe(false);
  });

  it("목차를 다시 만드는 중이면 돌지 않는다", () => {
    const p = autoProposal();
    expect(autoChainOn(p, autoState(p, [outlineGen(40, "queued")]).work)).toBe(false);
    expect(autoChainOn(p, autoState(p, [outlineGen(40, "running")]).work)).toBe(false);
  });

  it("끝났지만 계획서에 아직 반영되지 않은 목차 생성이 있으면 돌지 않는다 — done 은 생성 목록에 바로 오고 계획서는 다시 읽어야 바뀐다", () => {
    // 목차 gen_id 41 — [보고서 다시 만들기]의 목차 생성 80 이 끝났는데 계획서는 아직 옛 목차다. 옛 목차의 묶음 키를 넣으면
    // 서버(새 목차)가 404 NO_GROUP·409 승인 전으로 거절해 연쇄가 멈춘다
    const p = autoProposal();
    expect(autoChainOn(p, autoState(p, [outlineGen(80, "done")]).work)).toBe(false);
    // 그 뒤 다시 만들기가 또 실패해도 계획서는 80 의 목차여야 한다 — 다시 읽기 전이다
    expect(autoChainOn(p, autoState(p, [outlineGen(80, "done"), outlineGen(81, "failed")]).work)).toBe(false);
    // 다시 읽어 목차가 그 생성(gen_id 80)이 되면 돈다
    const reread = autoProposal({ outline: autoOutline({ gen_id: 80 }) });
    expect(autoChainOn(reread, autoState(reread, [outlineGen(80, "done")]).work)).toBe(true);
  });

  it("실패·취소로 끝난 다시 만들기와 이 목차를 만든 생성은 막지 않는다 — 목차가 그대로다", () => {
    const p = autoProposal();
    expect(autoChainOn(p, autoState(p, [outlineGen(80, "failed")]).work)).toBe(true);
    expect(autoChainOn(p, autoState(p, [outlineGen(80, "canceled")]).work)).toBe(true);
    expect(autoChainOn(p, autoState(p, [outlineGen(41, "done")]).work)).toBe(true);
  });

  it("조회 전(null)·목차 없음은 돌지 않는다", () => {
    const p = autoProposal();
    expect(autoChainOn(null, autoState(p).work)).toBe(false);
    expect(autoChainOn(p, null)).toBe(false);
    const none = autoProposal({ outline: null });
    expect(autoChainOn(none, autoState(none).work)).toBe(false);
  });
});

describe("autoTargets·nextAutoSection — 남은 절 고르기", () => {
  const four = autoOutline({
    groups: ["prior.g1", "prior.g2", "prior.g3", "prior.g4"].map((key, i) => ({
      key,
      name: `묶음 ${i + 1}`,
      hint: "",
      papers: [`KCI_${i}`],
    })),
  });

  it("문서 순서 prior.g1~g4 → gap", () => {
    expect(autoTargets(autoProposal({ outline: four }))).toEqual(["prior.g1", "prior.g2", "prior.g3", "prior.g4", "gap"]);
  });

  it("쓴 절은 빼고 생성 기록이 있는 키(failed·canceled 포함)도 뺀다 — 실패한 절은 그 절의 [다시 시도]에 맡긴다", () => {
    const p = autoProposal({
      outline: four,
      sections: { "prior.g1": section([para("p1", "proposed")]) },
      section_gens: {
        "prior.g2": { gen_id: 61, status: "failed" },
        "prior.g3": { gen_id: 62, status: "canceled" },
        "prior.g4": { gen_id: 63, status: "running" },
      },
    });
    expect(autoTargets(p)).toEqual(["gap"]);
  });

  it("section_gens 가 없는 옛 응답은 절이 없는 키를 모두 고른다", () => {
    const p = autoProposal({ sections: { "prior.g1": section([para("p1", "proposed")]) } });
    delete p.section_gens;
    expect(autoTargets(p)).toEqual(["prior.g2", "gap"]);
  });

  it("skip 의 키(이 방문에서 넣었거나 근거가 없어 건너뛴 키)는 건너뛴다", () => {
    const p = autoProposal();
    expect(nextAutoSection(p, new Set())).toBe("prior.g1");
    expect(nextAutoSection(p, new Set(["prior.g1"]))).toBe("prior.g2");
    expect(nextAutoSection(p, new Set(["prior.g1", "prior.g2"]))).toBe("gap");
  });

  it("남은 키가 없으면 null", () => {
    expect(nextAutoSection(autoProposal(), new Set(["prior.g1", "prior.g2", "gap"]))).toBeNull();
    const all = autoProposal({
      section_gens: {
        "prior.g1": { gen_id: 1, status: "done" },
        "prior.g2": { gen_id: 2, status: "done" },
        gap: { gen_id: 3, status: "queued" },
      },
    });
    expect(nextAutoSection(all, new Set())).toBeNull();
  });
});

describe("isNoSectionPapers — 근거 없음 409", () => {
  const fetchError = (status: number, detail: unknown) =>
    Object.assign(new Error(`HTTP ${status}`), { status, statusCode: status, data: { detail } });

  it("409 이고 detail code 가 no_section_papers 일 때만 참", () => {
    expect(isNoSectionPapers(fetchError(409, { code: "no_section_papers", message: "이 절에 넣을 논문이 없습니다" }))).toBe(true);
  });

  it("문자열 detail(06e 전 서버)·다른 code·404·네트워크 오류는 거짓", () => {
    expect(isNoSectionPapers(fetchError(409, "이 절에 넣을 논문이 없습니다"))).toBe(false);
    expect(isNoSectionPapers(fetchError(409, "이 절을 쓰는 중입니다"))).toBe(false);
    expect(isNoSectionPapers(fetchError(409, { code: "version_conflict", version: 3, message: "다른 곳에서 바뀌었습니다" }))).toBe(false);
    expect(isNoSectionPapers(fetchError(404, { code: "no_section_papers", message: "이 절에 넣을 논문이 없습니다" }))).toBe(false);
    expect(isNoSectionPapers(new TypeError("Failed to fetch"))).toBe(false);
    expect(isNoSectionPapers(null)).toBe(false);
  });
});

describe("docToc — 머리 목차", () => {
  it("여섯 자리를 문서 순서로 — anchor 는 보고서 화면의 자리 id 와 같은 글자", () => {
    const p = autoProposal({
      outline: autoOutline({ method: "설문 조사" }),
      sections: { "prior.g1": section([para("p1", "proposed")]) },
    });
    const s = autoState(p, [gen(50, "done"), gen(51, "running", "prior.g2")]);
    expect(docToc(p, s, new Set()).map((i) => [i.key, i.no, i.label, i.anchor, i.status])).toEqual([
      ["topic", "1", "주제", "wk-doc-topic", "text"],
      ["background", "2", "연구 배경", "wk-doc-background", "blank"],
      ["prior.g1", "3.1", "노인의 우울", "wk-sec-prior.g1", "done"],
      ["prior.g2", "3.2", "세대 간 지지", "wk-sec-prior.g2", "writing"],
      ["gap", "4", "연구 공백", "wk-sec-gap", "empty"],
      ["question", "5", "연구 질문", "wk-doc-question", "text"],
      ["method", "6", "방법 제안", "wk-doc-method", "text"],
    ]);
  });

  it("배경·질문·방법이 비면 blank — 배경을 적었으면 text", () => {
    const statuses = (p: ProposalView) => docToc(p, autoState(p), new Set()).map((i) => i.status);
    const blank = autoProposal({ outline: autoOutline({ question: null, method: "  " }) });
    expect(statuses(blank)).toEqual(["text", "blank", "empty", "empty", "empty", "blank", "blank"]);
    // 연구 배경은 Outline.background 글이다 — 키가 없는 응답(필드를 열기 전 서버)은 빈 글이다
    const written = autoProposal({ outline: { ...autoOutline(), background: "농촌 노인의 고립이 커졌다." } as Outline });
    expect(statuses(written)[1]).toBe("text");
    expect(outlineBackground(written.outline!)).toBe("농촌 노인의 고립이 커졌다.");
    expect(outlineBackground(autoOutline())).toBe("");
  });

  it("근거가 없어 건너뛴 쓰기 전 절은 skipped — 손으로 다시 쓰기 시작하면 그 절의 상태", () => {
    const p = autoProposal();
    const gapOf = (s: WorkState, skipped: ReadonlySet<string>) => docToc(p, s, skipped).find((i) => i.key === "gap")!.status;
    expect(gapOf(autoState(p), new Set(["gap"]))).toBe("skipped");
    expect(gapOf(autoState(p, [gen(70, "queued", "gap")]), new Set(["gap"]))).toBe("queued");
  });

  it("목차가 없으면 빈 목록", () => {
    const p = autoProposal({ outline: null });
    expect(docToc(p, autoState(p), new Set())).toEqual([]);
  });
});

describe("reportBar — 보고서 작성 중 큰 진행 막대", () => {
  it("쓰는 절이 있으면 '보고서 작성 중 · 1/3절 — 「…」'과 33%", () => {
    const p = autoProposal({
      sections: { "prior.g1": section([para("p1", "proposed")]) },
      section_gens: { "prior.g1": { gen_id: 50, status: "done" }, "prior.g2": { gen_id: 51, status: "running" } },
    });
    expect(reportBar(p, autoState(p, [gen(50, "done"), gen(51, "running", "prior.g2")]), new Set())).toEqual({
      label: "보고서 작성 중 · 1/3절 — 「선행연구 검토 · 세대 간 지지」",
      done: 1,
      total: 3,
      percent: 33,
      running: true,
    });
  });

  it("쓰는 절이 없어도 연쇄가 남은 절을 넣을 참이면 다음 절 이름 — 대기 중인 절이 있으면 그 절", () => {
    const p = autoProposal();
    expect(reportBar(p, autoState(p), new Set())).toEqual({
      label: "보고서 작성 중 · 0/3절 — 「선행연구 검토 · 노인의 우울」",
      done: 0,
      total: 3,
      percent: 0,
      running: false,
    });
    const queued = autoProposal({ section_gens: { gap: { gen_id: 52, status: "queued" } } });
    expect(reportBar(queued, autoState(queued, [gen(52, "queued", "gap")]), new Set())).toMatchObject({
      label: "보고서 작성 중 · 0/3절 — 「연구 공백」",
      running: false,
    });
  });

  it("건너뛴 절·실패한 절·취소로 끝난 쓰기 전 절은 끝난 수에 든다", () => {
    const p = autoProposal({
      section_gens: { "prior.g1": { gen_id: 50, status: "failed" }, "prior.g2": { gen_id: 51, status: "running" } },
    });
    expect(reportBar(p, autoState(p, [gen(50, "failed"), gen(51, "running", "prior.g2")]), new Set(["gap"]))).toEqual({
      label: "보고서 작성 중 · 2/3절 — 「선행연구 검토 · 세대 간 지지」",
      done: 2,
      total: 3,
      percent: 67,
      running: true,
    });
    const canceled = autoProposal({ section_gens: { "prior.g1": { gen_id: 50, status: "canceled" } } });
    expect(reportBar(canceled, autoState(canceled, [gen(50, "canceled")]), new Set())).toMatchObject({
      label: "보고서 작성 중 · 1/3절 — 「선행연구 검토 · 세대 간 지지」",
      done: 1,
      percent: 33,
    });
  });

  it("다 썼거나, auto 없는 목차·멈춘 연쇄에 쓰는 절이 없으면 null", () => {
    const done = autoProposal({
      sections: {
        "prior.g1": section([para("p1", "proposed")]),
        "prior.g2": section([para("p1", "proposed")], { key: "prior.g2", gen_id: 51 }),
        gap: section([para("p1", "proposed")], { key: "gap", gen_id: 52 }),
      },
      section_gens: {
        "prior.g1": { gen_id: 50, status: "done" },
        "prior.g2": { gen_id: 51, status: "done" },
        gap: { gen_id: 52, status: "done" },
      },
    });
    const doneGens = [gen(50, "done"), gen(51, "done", "prior.g2"), gen(52, "done", "gap")];
    expect(reportBar(done, autoState(done, doneGens), new Set())).toBeNull();
    const old = autoProposal({ outline: autoOutline({ auto: false }) });
    expect(reportBar(old, autoState(old), new Set())).toBeNull();
    // 06b 목차라도 손으로 쓰는 절이 있으면 그 절을 보인다
    expect(reportBar(old, autoState(old, [gen(60, "running", "gap")]), new Set())!.label).toBe(
      "보고서 작성 중 · 0/3절 — 「연구 공백」",
    );
    // 연쇄가 오류로 멈추면(넷째 인자) 남은 절로는 막대를 세우지 않는다
    const p = autoProposal();
    expect(reportBar(p, autoState(p), new Set(), true)).toBeNull();
    const none = autoProposal({ outline: null });
    expect(reportBar(none, autoState(none), new Set())).toBeNull();
  });

  it("다시 만든 목차를 계획서에 반영하기 전에는 옛 목차의 남은 절 이름을 보이지 않는다", () => {
    const p = autoProposal();
    expect(reportBar(p, autoState(p, [outlineGen(80, "done")]), new Set())).toBeNull();
    const reread = autoProposal({ outline: autoOutline({ gen_id: 80 }) });
    expect(reportBar(reread, autoState(reread, [outlineGen(80, "done")]), new Set())!.label).toBe(
      "보고서 작성 중 · 0/3절 — 「선행연구 검토 · 노인의 우울」",
    );
  });

  it("조사를 붙이지 않는다 — FINAL_STEP_NAME 뒤가 ' 작성 중'", () => {
    const p = autoProposal();
    const label = reportBar(p, autoState(p), new Set())!.label;
    expect(label.startsWith(`${FINAL_STEP_NAME} 작성 중 · `)).toBe(true);
    expect(label).not.toMatch(new RegExp(`${FINAL_STEP_NAME}[을를이가은는의로]`));
  });
});
