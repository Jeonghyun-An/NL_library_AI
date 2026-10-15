// frontend/tests/unit/workPhase.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { ResearchReport, ResearchView } from "~/types/research";
import type { WorkView } from "~/types/work";
import { DEEP_READ, DEEP_RESEARCH } from "~/utils/brand";
import {
  BETA_LABEL,
  FINAL_STEP_NAME,
  MAKE_REPORT,
  ONBOARDING_KEY,
  ONBOARDING_LEAD,
  ONBOARDING_STEPS,
  REMAKE_REPORT,
  STEP_NAMES,
  WORK_STEPS,
  continueCard,
  parseWorkStep,
  scopeLine,
  stepForPhase,
  stepLine,
  stepperItems,
  summaryBand,
  summaryLine,
  withStep,
} from "~/utils/workPhase";

function view(over: Partial<ResearchView> = {}): ResearchView {
  return {
    jobId: "11111111-1111-4111-8111-111111111111",
    question: "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
    status: "completed",
    stage: "synthesized",
    plan: [],
    params: {},
    report: null,
    lastError: null,
    createdAt: null,
    startedAt: null,
    finishedAt: null,
    steps: [],
    subqs: [],
    counters: { papersReviewed: 121, evidenceAdopted: 40, rechecks: 2, excluded: 9 },
    highlight: null,
    synth: { seq: null, status: null, total: 0, sections: [], headings: [], evidence: {}, retiredSeq: null },
    source: "rounds",
    queue: null,
    ...over,
  };
}

function report(over: Partial<ResearchReport> = {}): ResearchReport {
  const section = { heading: "절", intro: "", papers: [], future: [], evidence_chunks: {}, chunk_scores: {} };
  return {
    question: "q",
    range: { from: "1980", to: "2017", n_papers: 144748 },
    sections: [section, section, section],
    evidence: {},
    trail: [],
    limitations: [],
    stats: { papers_reviewed: 121, evidence_adopted: 48, rechecks: 2, excluded: 12 },
    ...over,
  };
}

describe("parseWorkStep", () => {
  it("topics·reading·proposal 만 단계로 읽고 앞뒤 공백·배열은 첫 값으로 맞춘다", () => {
    expect(WORK_STEPS).toEqual(["topics", "reading", "proposal"]);
    expect(parseWorkStep({ s: "topics" })).toBe("topics");
    expect(parseWorkStep({ s: " reading " })).toBe("reading");
    expect(parseWorkStep({ s: ["proposal", "topics"] })).toBe("proposal");
  });

  it("없거나 틀린 값은 null — 탐색·보고서 화면을 연다", () => {
    expect(parseWorkStep({})).toBeNull();
    expect(parseWorkStep({ s: "" })).toBeNull();
    expect(parseWorkStep({ s: "done" })).toBeNull();
    expect(parseWorkStep({ s: "grid" })).toBeNull();
    expect(parseWorkStep({ s: 3 })).toBeNull();
    expect(parseWorkStep({ s: null })).toBeNull();
  });
});

describe("stepForPhase·stepLine", () => {
  it("도달한 단계의 화면을 고르고 완료는 계획서 화면이다", () => {
    expect(stepForPhase("topics")).toBe("topics");
    expect(stepForPhase("reading")).toBe("reading");
    expect(stepForPhase("proposal")).toBe("proposal");
    expect(stepForPhase("done")).toBe("proposal");
  });

  it("진행 막대 옆 한 줄", () => {
    expect(stepLine("topics")).toBe("2/4 단계 · 제목 고르는 중");
    expect(stepLine("reading")).toBe("3/4 단계 · 참고문헌 고르는 중");
    expect(stepLine("proposal")).toBe("4/4 단계 · 보고서 쓰는 중");
    expect(stepLine("done")).toBe("4/4 단계 · 완료");
  });

  it("보고서를 다 썼으면(Word 를 받기 전, 서버 단계는 아직 proposal) '보고서 완성' — 다른 단계는 그대로", () => {
    expect(stepLine("proposal", true)).toBe("4/4 단계 · 보고서 완성");
    expect(stepLine("proposal", false)).toBe("4/4 단계 · 보고서 쓰는 중");
    expect(stepLine("reading", true)).toBe("3/4 단계 · 참고문헌 고르는 중");
    expect(stepLine("done", true)).toBe("4/4 단계 · 완료");
  });
});

describe("단계 이름", () => {
  it("STEP_NAMES 는 사이드바가 읽는 단계 이름이다", () => {
    expect(STEP_NAMES).toEqual({ explore: "탐색", topics: "제목 고르기", reading: "참고문헌 선택하기", proposal: "보고서" });
    // 진행 막대·이어가기 카드·온보딩이 같은 이름을 쓴다 — 화면마다 이름을 다시 쓰지 않는다
    expect(stepperItems("topics", null).map((i) => i.label)).toEqual(Object.values(STEP_NAMES));
    expect(ONBOARDING_STEPS.map((s) => s.title)).toEqual([STEP_NAMES.topics, STEP_NAMES.reading, STEP_NAMES.proposal]);
    // 마지막 단계 이름은 조사가 붙지 않는 꼴에만 쓴다(06e 정함 1) — '보고서를'·'보고서로' 를 상수로 만들지 않는다
    expect(stepLine("proposal")).toBe(`4/4 단계 · ${STEP_NAMES.proposal} 쓰는 중`);
  });
});

describe("stepperItems", () => {
  it("탐색은 늘 끝난 단계이고, 도달한 단계가 지금 단계, 그 뒤는 아직이다", () => {
    expect(stepperItems("reading", "reading")).toEqual([
      { key: "explore", label: "탐색", state: "done", clickable: true },
      { key: "topics", label: "제목 고르기", state: "done", clickable: true },
      { key: "reading", label: "참고문헌 선택하기", state: "current", clickable: false },
      { key: "proposal", label: "보고서", state: "todo", clickable: false },
    ]);
  });

  it("보고 있는 단계는 누를 수 없고, 앞 단계를 보는 중이면 지금 단계로 돌아가게 누를 수 있다", () => {
    const viewingTopics = stepperItems("reading", "topics");
    expect(viewingTopics.map((i) => i.clickable)).toEqual([true, false, true, false]);
    const viewingReport = stepperItems("topics", null);
    expect(viewingReport.map((i) => [i.state, i.clickable])).toEqual([
      ["done", false],
      ["current", true],
      ["todo", false],
      ["todo", false],
    ]);
  });

  it("완료면 네 단계가 모두 끝난 단계다", () => {
    expect(stepperItems("done", "proposal").map((i) => [i.state, i.clickable])).toEqual([
      ["done", true],
      ["done", true],
      ["done", true],
      ["done", false],
    ]);
  });
});

describe("withStep", () => {
  it("단계만 바꾸고 돌아갈 자리(at·y)는 떼며 다른 쿼리는 둔다", () => {
    expect(withStep({ at: "c-0-E1", y: "120", s: "topics", h: "x" }, "reading")).toEqual({ h: "x", s: "reading" });
    expect(withStep({}, "topics")).toEqual({ s: "topics" });
  });

  it("null 이면 ?s= 를 지워 탐색·보고서로 간다", () => {
    expect(withStep({ s: "proposal", at: "g-gap-p1" }, null)).toEqual({});
  });

  it("받은 쿼리를 고치지 않는다", () => {
    const query = { s: "topics", at: "r-C1" };
    withStep(query, "reading");
    expect(query).toEqual({ s: "topics", at: "r-C1" });
  });
});

describe("summaryBand·summaryLine", () => {
  it("최종 보고서의 절 수·통계를 쓴다(제외는 하위질문별 판단의 수라 '건')", () => {
    const band = summaryBand(view({ report: report() }));
    expect(band).toEqual({
      question: "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
      sections: 3,
      adopted: 48,
      excluded: 12,
    });
    expect(summaryLine(band)).toBe("절 3개 · 채택 48편 · 제외 12건");
  });

  it("통계가 없는 옛 보고서는 탐색 카운터를, 제외 수를 모르는 보고서는 제외 칸을 뺀다", () => {
    expect(summaryBand(view({ report: report({ stats: undefined }) }))).toMatchObject({ adopted: 40, excluded: 9 });
    const noExcluded = summaryBand(view({ report: report({ stats: { papers_reviewed: 50, evidence_adopted: 20, rechecks: 0 } }) }));
    expect(noExcluded).toMatchObject({ sections: 3, adopted: 20, excluded: null });
    expect(summaryLine(noExcluded)).toBe("절 3개 · 채택 20편");
  });

  it("보고서가 없고 카운터도 모르면 빈 줄이다", () => {
    const band = summaryBand(view({ counters: { papersReviewed: null, evidenceAdopted: null, rechecks: null, excluded: null } }));
    expect(band).toMatchObject({ sections: 0, adopted: null, excluded: null });
    expect(summaryLine(band)).toBe("");
  });
});

describe("scopeLine", () => {
  it("소장 적재분 수와 끝 연도로 고정 띠 문구를 만든다", () => {
    expect(scopeLine({ n_papers: 144748, from: "1980", to: "2017" })).toBe(
      "소장 KCI 적재분 144,748편(~2017) 기준 · 편수 추이는 동향이 아님",
    );
    expect(scopeLine({ n_papers: 900, from: null, to: "2017-12-31", at: "2026-10-06T00:00:00Z" })).toBe(
      "소장 KCI 적재분 900편(~2017) 기준 · 편수 추이는 동향이 아님",
    );
  });

  it("끝 연도를 모르면 괄호를 빼고, 범위가 없으면 null", () => {
    expect(scopeLine({ n_papers: 12, from: null, to: null })).toBe("소장 KCI 적재분 12편 기준 · 편수 추이는 동향이 아님");
    expect(scopeLine(null)).toBeNull();
    expect(scopeLine(undefined)).toBeNull();
    expect(scopeLine({ n_papers: 0, from: null, to: null })).toBeNull();
  });
});

describe("continueCard", () => {
  const work = (over: Partial<WorkView> = {}): WorkView => ({
    id: "11111111-1111-4111-8111-111111111111",
    phase: "reading",
    concepts: [],
    memo: null,
    is_example: false,
    progress: {},
    generations: [],
    ...over,
  });

  it("이어가지 않았으면 4단계 미리보기(탐색 끝 · 제목 고르기 · 참고문헌 선택하기 · 보고서)와 [이 연구 이어가기]", () => {
    const card = continueCard(false, null);
    expect(card).toMatchObject({
      title: "이 연구 이어가기",
      body: "탐색이 끝났습니다. 제목 고르기 → 참고문헌 선택하기 → 보고서 3단계를 거쳐 보고서 초안까지 이어 갈 수 있습니다.",
      label: "이 연구 이어가기",
      action: "continue",
      note: null,
    });
    expect(card.preview).toEqual([
      { label: "탐색 끝", state: "done" },
      { label: "제목 고르기", state: "todo" },
      { label: "참고문헌 선택하기", state: "todo" },
      { label: "보고서", state: "todo" },
    ]);
  });

  it("이어갔는지 아직 모르면(확인 중·조회 실패)도 이어가기다 — POST continue 는 멱등이라 이어간 연구면 그것을 연다", () => {
    expect(continueCard(null, null)).toMatchObject({ label: "이 연구 이어가기", action: "continue" });
  });

  it("이어간 연구면 지금 단계와 [이어간 연구 열기]", () => {
    const card = continueCard(true, work());
    expect(card).toMatchObject({
      title: "이어간 연구",
      body: "3/4 단계 · 참고문헌 고르는 중",
      label: "이어간 연구 열기",
      action: "open",
      note: null,
    });
    expect(card.preview.map((s) => s.state)).toEqual(["done", "done", "current", "todo"]);
  });

  it("예시 연구는 읽기 전용이라고 알린다", () => {
    expect(continueCard(true, work({ is_example: true })).note).toBe(
      "예시 연구는 읽기 전용입니다 — 둘러볼 수 있고 바꿀 수는 없습니다.",
    );
  });

  it("보고서를 다 썼으면 머리 단계 줄(WorkStepper)과 같은 '보고서 완성' — 한 화면에서 위아래가 갈리지 않게", () => {
    expect(continueCard(true, work({ phase: "proposal" }), true).body).toBe("4/4 단계 · 보고서 완성");
    expect(continueCard(true, work({ phase: "proposal" })).body).toBe("4/4 단계 · 보고서 쓰는 중");
  });
});

describe("연구 이어가기는 베타 기능이다(사용자 결정 2026-10-15)", () => {
  const read = (rel: string) => readFileSync(fileURLToPath(new URL(`../../${rel}`, import.meta.url)), "utf8");

  it("이어가기 카드 제목·단계 막대 옆에 같은 'Beta' 표시를 단다", () => {
    expect(BETA_LABEL).toBe("Beta");
    for (const path of ["components/work/ContinueResearchCard.vue", "components/work/WorkStepper.vue"]) {
      const src = read(path);
      expect(src).toContain('class="wk-beta"');
      expect(src).toContain("{{ BETA_LABEL }}");
    }
  });
});

describe("온보딩", () => {
  it("브라우저 저장 열쇠와 세 단계(제목 고르기·참고문헌 선택하기·보고서)의 설명·결정할 것", () => {
    expect(ONBOARDING_KEY).toBe("skx_work_onboarded");
    expect(ONBOARDING_LEAD).toBe("제목 고르기 → 참고문헌 선택하기 → 보고서 3단계를 거쳐 보고서 초안까지 갑니다.");
    expect(ONBOARDING_STEPS.map((s) => s.title)).toEqual(["제목 고르기", "참고문헌 선택하기", "보고서"]);
    // 마지막 단계는 [보고서 만들기] 한 번으로 목차·절이 서는 흐름을 알린다(D20)
    expect(ONBOARDING_STEPS[1]!.decide).toContain("[보고서 만들기]");
    expect(ONBOARDING_STEPS[2]!.body).toContain("[보고서 만들기]");
    // 제품 기능 이름은 화면 표기 상수(utils/brand — 사용자 결정 2026-10-12)로 — '딥리서치' 글자를 두지 않는다
    expect(ONBOARDING_STEPS[0]!.body.startsWith(`${DEEP_RESEARCH} 보고서의 향후 과제`)).toBe(true);
    expect(ONBOARDING_STEPS[1]!.body).toContain(`그 논문과 대화(${DEEP_READ})할 수 있고`);
    expect(ONBOARDING_STEPS[1]!.body.endsWith("자기점검이 뺀 논문을 되살릴 수 있습니다.")).toBe(true);
    for (const s of ONBOARDING_STEPS) {
      expect(s.body).not.toContain("딥리서치");
      expect(s.body).not.toContain("딥리드");
      expect(s.body.length).toBeGreaterThan(0);
      expect(s.decide.length).toBeGreaterThan(0);
    }
  });
});

describe("온보딩 — 참고문헌 선택하기는 미리 담아 둔 채로 시작한다(승인 문구 2026-10-13)", () => {
  // 사용자가 승인한 문구 — 글자 그대로(띄어쓰기·문장부호 포함). 숫자 없는 기능 설명이다 — 이 안내는 [단계 안내 다시 보기]로
  // 이어간 모든 연구(미리 담기 전에 이어간 연구·후보가 적은 연구·예시 연구 포함)에서 열리니, 경우별 실제 수는 머리 소개가 맡는다
  const APPROVED = "이어가기를 시작하면 근거로 쓰인 논문을 미리 담아 둡니다. 빼거나 더 담아서 참고문헌을 정해 보세요.";
  const body = ONBOARDING_STEPS[1]!.body;

  it("설명은 승인 문구로 시작하고 편수를 적지 않는다(사용자 결정 2026-10-13)", () => {
    expect(body.startsWith(APPROVED)).toBe(true);
    expect(body).not.toMatch(/\d+\s*편/);
    // 미리 담기 전의 '후보로 들어와 있습니다'(0 에서 담아 올라가는 말)는 이제 틀린 말이다
    expect(body).not.toContain("후보로 들어와 있습니다");
  });

  it("결정할 것 — 여덟 편이 담긴 채 시작하니 '5편 이상 담으면'이 아니라 '담은 논문이 5편 이상이면'", () => {
    expect(ONBOARDING_STEPS[1]!.decide).toBe(
      "보고서에 쓸 논문을 담습니다. 담은 논문이 5편 이상이면 [보고서 만들기]를 누를 수 있습니다.",
    );
  });

  it("말투는 다른 단계와 같은 합니다체 — 해요체 서술('…어요.')을 두지 않는다(사용자 결정 2026-10-13)", () => {
    for (const s of ONBOARDING_STEPS) {
      expect(s.body).not.toMatch(/[어아]요\./);
      expect(s.decide).not.toMatch(/[어아]요\./);
    }
  });
});

describe("FINAL_STEP_NAME·버튼 이름", () => {
  it("마지막 단계 이름은 '보고서'(Q2 기본) — 버튼은 조사 없는 꼴로 이름에서 만든다", () => {
    expect(FINAL_STEP_NAME).toBe("보고서");
    expect(MAKE_REPORT).toBe(`${FINAL_STEP_NAME} 만들기`);
    expect(REMAKE_REPORT).toBe(`${FINAL_STEP_NAME} 다시 만들기`);
    expect([MAKE_REPORT, REMAKE_REPORT]).toEqual(["보고서 만들기", "보고서 다시 만들기"]);
  });
});
