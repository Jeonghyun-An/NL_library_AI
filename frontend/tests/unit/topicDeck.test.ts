// frontend/tests/unit/topicDeck.test.ts
import { describe, expect, it } from "vitest";
import type { PaperMeta, TopicCard, TopicItem, TopicSeed, TopicsView, WorkGeneration } from "~/types/work";
import { genQueueLine } from "~/utils/queueLine";
import {
  addConcept,
  canPick,
  cardArrived,
  cardNumbersLine,
  cardNote,
  cardStatus,
  cleanConcept,
  conceptsNote,
  conceptsRetryable,
  conceptsStatus,
  deckOrder,
  deckQueueLine,
  evidenceChips,
  liveTopics,
  moreLine,
  seedLine,
  topicProblem,
} from "~/utils/topicDeck";

const CARD: TopicCard = {
  title: "노인의 사회적 지지 유형별 우울 완화 효과",
  question: "가족·친구·이웃 지지 가운데 어느 것이 노인 우울을 가장 낮추는가?",
  evidence: ["KCI_A", "KCI_B"],
  figure_sentence: "이 절의 채택 논문은 [F1]편이고 근거 중 최신 연도는 [F2]년이다.",
  figures: [
    { id: "F1", label: "이 절의 채택 논문 수", value: "9" },
    { id: "F2", label: "근거 중 최신 연도", value: "2017" },
  ],
  latest_year: 2017,
  edited: false,
  checks: { numbers: [], softened: 0, recovered: 0 },
  gen_id: 41,
};

const SEED: TopicSeed = {
  key: "future:1:0",
  kind: "future",
  section_idx: 1,
  subq_idx: 1,
  heading: "노인 우울과 사회적 지지의 관계",
  text: "지지 유형별 효과를 비교한 연구가 더 필요하다",
  papers: ["KCI_A", "KCI_B"],
  adopted: 9,
};

function item(over: Partial<TopicItem> = {}): TopicItem {
  return {
    id: 12,
    slot: 1,
    origin: "report_seed",
    state: "candidate",
    parent_id: null,
    seed: SEED,
    card: null,
    generation: { id: 41, status: "queued" },
    created_at: "2026-10-12T01:00:00Z",
    ...over,
  };
}

function gen(over: Partial<WorkGeneration> = {}): WorkGeneration {
  return {
    id: 41,
    kind: "topic_card",
    target: "12",
    status: "queued",
    model: null,
    error: null,
    position: 1,
    eta_sec: 60,
    others_ahead: false,
    ...over,
  };
}

function deck(items: TopicItem[]): TopicsView {
  return { picked_id: null, seeds_left: 2, corpus: null, papers: {}, items };
}

describe("deckOrder", () => {
  it("처음 자리(slot) 카드를 자리 순으로, 그 뒤 다른 방향·직접 쓰기 카드를 만든 순으로 두고 접힌 카드는 뺀다", () => {
    const items = [
      item({ id: 20, slot: null, origin: "user" }),
      item({ id: 13, slot: 2 }),
      item({ id: 18, slot: null, origin: "other" }),
      item({ id: 12, slot: 1 }),
      item({ id: 19, slot: null, state: "folded" }),
    ];
    expect(deckOrder(items).map((i) => i.id)).toEqual([12, 13, 18, 20]);
    // 받은 배열은 그대로 둔다
    expect(items.map((i) => i.id)).toEqual([20, 13, 18, 12, 19]);
  });
});

describe("cardStatus", () => {
  it("카드가 있으면 생성 상태와 무관하게 ready 다", () => {
    expect(cardStatus(item({ card: CARD, generation: { id: 41, status: "done" } }))).toBe("ready");
    expect(cardStatus(item({ card: CARD, generation: null, origin: "user" }))).toBe("ready");
  });

  it("카드가 없으면 생성 상태로 — 대기·쓰는 중·끝났는데 카드 없음(근거 부족)·실패/취소", () => {
    expect(cardStatus(item({ generation: { id: 41, status: "queued" } }))).toBe("waiting");
    expect(cardStatus(item({ generation: { id: 41, status: "running" } }))).toBe("making");
    expect(cardStatus(item({ state: "insufficient", generation: { id: 41, status: "done" } }))).toBe("insufficient");
    expect(cardStatus(item({ generation: { id: 41, status: "failed" } }))).toBe("failed");
    expect(cardStatus(item({ generation: { id: 41, status: "canceled" } }))).toBe("failed");
  });

  it("근거 부족 카드를 다시 부르면 새 생성이 끝날 때까지 대기·쓰는 중이다", () => {
    expect(cardStatus(item({ state: "insufficient", generation: { id: 52, status: "queued" } }))).toBe("waiting");
    expect(cardStatus(item({ state: "insufficient", generation: { id: 52, status: "running" } }))).toBe("making");
  });

  it("생성 기록이 없는 빈 카드·제목이 빈 카드는 카드가 없는 것으로 본다", () => {
    expect(cardStatus(item({ state: "insufficient", generation: null }))).toBe("insufficient");
    expect(cardStatus(item({ generation: null }))).toBe("failed");
    expect(cardStatus(item({ card: { ...CARD, title: " " }, generation: { id: 41, status: "done" } }))).toBe("insufficient");
  });
});

describe("cardArrived — 카드 뒤집기", () => {
  it("기다리거나 쓰던 슬롯에 카드가 도착했을 때만 뒤집는다", () => {
    expect(cardArrived("waiting", "ready")).toBe(true);
    expect(cardArrived("making", "ready")).toBe(true);
  });

  it("처음 그릴 때·사용자가 빈 슬롯을 채웠을 때·그대로일 때는 뒤집지 않는다", () => {
    expect(cardArrived(undefined, "ready")).toBe(false);
    expect(cardArrived("insufficient", "ready")).toBe(false);
    expect(cardArrived("failed", "ready")).toBe(false);
    expect(cardArrived("ready", "ready")).toBe(false);
    expect(cardArrived("waiting", "making")).toBe(false);
  });
});

describe("cardNote", () => {
  it("빈 슬롯마다 정직한 문구를, 카드가 있으면 null 을 준다", () => {
    expect(cardNote("waiting")).toBe("차례를 기다리는 중입니다");
    expect(cardNote("making")).toBe("카드를 쓰는 중입니다");
    expect(cardNote("insufficient")).toBe("근거 부족 — 이 씨앗을 직접 받치는 논문을 2편 이상 찾지 못했습니다");
    expect(cardNote("failed")).toBe("카드를 만들지 못했습니다");
    expect(cardNote("ready")).toBeNull();
  });
});

describe("canPick", () => {
  it("카드가 있는 후보만 고를 수 있다", () => {
    expect(canPick(item({ card: CARD }))).toBe(true);
    expect(canPick(item({ card: CARD, state: "picked" }))).toBe(false);
    expect(canPick(item({ state: "insufficient", generation: { id: 41, status: "done" } }))).toBe(false);
    expect(canPick(item({ generation: { id: 41, status: "running" } }))).toBe(false);
  });
});

describe("evidenceChips", () => {
  const PAPERS: Record<string, PaperMeta> = {
    KCI_A: { title: "노인의 우울과 사회적 지지", personal_author: "김철수; 이영희", pub_date: "2015-03", series_title: "노인복지연구" },
    KCI_B: { title: "가족 지지가 노인 우울에 미치는 영향 연구", personal_author: null, pub_date: "2013", series_title: null },
    KCI_C: { title: "지지망 분석", personal_author: null, pub_date: null, series_title: null },
  };

  it("보고서 인용칩과 같은 '저자 연도' 라벨과 전체 제목을 준다", () => {
    expect(evidenceChips(CARD, PAPERS)).toEqual([
      { cntsId: "KCI_A", label: "김 2015", title: "노인의 우울과 사회적 지지" },
      { cntsId: "KCI_B", label: "가족 지지가 노인 우울…", title: "가족 지지가 노인 우울에 미치는 영향 연구" },
    ]);
  });

  it("저자를 모르면 제목 앞부분(짧으면 그대로), 서지가 없으면 cnts_id 로 가른다", () => {
    const card = { ...CARD, evidence: ["KCI_C", "KCI_Z"] };
    expect(evidenceChips(card, PAPERS)).toEqual([
      { cntsId: "KCI_C", label: "지지망 분석", title: "지지망 분석" },
      { cntsId: "KCI_Z", label: "KCI_Z", title: "KCI_Z" },
    ]);
  });
});

describe("cardNumbersLine — [F#] 밖 숫자", () => {
  it("서버가 센 숫자가 있으면 계획서 문단과 같은 '확인 필요' 줄, 없으면 null 이다", () => {
    expect(cardNumbersLine({ ...CARD, checks: { numbers: ["2015", "9"], softened: 0, recovered: 0 } })).toBe(
      "확인 필요 2015, 9",
    );
    expect(cardNumbersLine(CARD)).toBeNull();
  });
});

describe("seedLine", () => {
  it("씨앗 종류와 절 소제목을 잇고, 씨앗이 없으면 null 이다", () => {
    expect(seedLine(SEED)).toBe("보고서의 향후 과제 · 노인 우울과 사회적 지지의 관계");
    expect(seedLine({ ...SEED, kind: "insufficient", key: "insufficient:3" })).toBe(
      "근거가 모자랐던 하위질문 · 노인 우울과 사회적 지지의 관계",
    );
    expect(seedLine({ ...SEED, heading: "  " })).toBe("보고서의 향후 과제");
    expect(seedLine(null)).toBeNull();
  });
});

describe("liveTopics — 연구 SSE 의 생성 상태로 덮기", () => {
  it("대기 중이던 카드 생성이 도는 중이 되면 다시 읽지 않아도 쓰는 중이다", () => {
    const topics = deck([item()]);
    const live = liveTopics(topics, [gen({ status: "running" })]);
    expect(live.items[0]!.generation).toEqual({ id: 41, status: "running" });
    expect(cardStatus(live.items[0]!)).toBe("making");
  });

  it("끝난 생성의 카드가 아직 목록에 없으면 쓰는 중으로 두고, 다시 읽은 목록이 같은 생성을 끝났다고 알면 목록 그대로다", () => {
    const before = deck([item({ generation: { id: 41, status: "running" } })]);
    expect(liveTopics(before, [gen({ status: "done" })]).items[0]!.generation).toEqual({ id: 41, status: "running" });
    const reloaded = deck([item({ card: CARD, generation: { id: 41, status: "done" } })]);
    const same = liveTopics(reloaded, [gen({ status: "done" })]);
    expect(same.items[0]).toBe(reloaded.items[0]);
  });

  it("실패는 그대로 싣고, 목록이 더 새 생성을 알면 목록 값을 쓴다", () => {
    const topics = deck([item({ generation: { id: 41, status: "running" } })]);
    expect(cardStatus(liveTopics(topics, [gen({ status: "failed" })]).items[0]!)).toBe("failed");
    const retried = deck([item({ state: "insufficient", generation: { id: 52, status: "queued" } })]);
    expect(liveTopics(retried, [gen({ status: "done" })]).items[0]).toBe(retried.items[0]);
  });

  it("다른 kind·다른 주제의 생성은 보지 않고, 카드 생성이 하나도 없으면 받은 목록을 그대로 돌려준다", () => {
    const topics = deck([item()]);
    const other = liveTopics(topics, [gen({ kind: "concepts", target: null, status: "running" }), gen({ target: "99", status: "running" })]);
    expect(other.items[0]).toBe(topics.items[0]);
    expect(liveTopics(topics, [gen({ kind: "concepts", target: null })])).toBe(topics);
  });
});

describe("deckQueueLine", () => {
  it("열린 카드 생성이 없으면 null 이다", () => {
    expect(deckQueueLine([])).toBeNull();
    expect(deckQueueLine([gen({ status: "done" }), gen({ id: 40, kind: "concepts", target: null, status: "running" })])).toBeNull();
  });

  it("도는 생성이 있으면 그것을, 없으면 가장 앞 순번의 대기 문구를 남은 장수와 함께 쓴다", () => {
    const running = gen({ id: 42, target: "13", status: "running", position: null });
    expect(deckQueueLine([gen({ position: 2 }), running])).toBe("주제 카드 2장 남음 · 쓰는 중");
    const first = gen({ id: 43, target: "14", position: 1, eta_sec: 120 });
    expect(deckQueueLine([gen({ position: 3 }), first])).toBe(`주제 카드 2장 남음 · ${genQueueLine(first)}`);
  });
});

describe("moreLine", () => {
  it("남은 씨앗과 한 번에 받는 장수(최대 2)를, 다 쓰면 직접 쓰기를 안내한다", () => {
    expect(moreLine(5)).toBe("남은 씨앗 5개 · 누르면 2장을 더 받습니다");
    expect(moreLine(1)).toBe("남은 씨앗 1개 · 누르면 1장을 더 받습니다");
    expect(moreLine(0)).toBe("더 쓸 씨앗이 없습니다 — [직접 쓰기] 로 주제를 더할 수 있습니다");
  });
});

describe("topicProblem", () => {
  it("앞뒤 공백을 뺀 제목 2~120자·연구 질문 2~300자만 받는다", () => {
    expect(topicProblem({ title: "노인 우울", question: "무엇이 우울을 낮추는가?" })).toBeNull();
    expect(topicProblem({ title: " 가 ", question: "무엇이 우울을 낮추는가?" })).toBe("제목을 2자 이상 쓰세요");
    expect(topicProblem({ title: "가".repeat(121), question: "질문" })).toBe("제목은 120자까지입니다");
    expect(topicProblem({ title: "노인 우울", question: "?" })).toBe("연구 질문을 2자 이상 쓰세요");
    expect(topicProblem({ title: "노인 우울", question: "가".repeat(301) })).toBe("연구 질문은 300자까지입니다");
  });
});

describe("핵심 개념 칩", () => {
  it("cleanConcept — NFKC 뒤 공백을 하나로 접는다(서버 clean_concepts 와 같다)", () => {
    expect(cleanConcept("  ＡＩ   윤리 ")).toBe("AI 윤리");
  });

  it("addConcept — 새 개념만 뒤에 붙이고, 빈 글·40자 초과·같은 개념·5개가 찬 목록이면 받은 배열 그대로다", () => {
    const base = ["노인 우울", "사회적 지지"];
    expect(addConcept(base, " 가족  지지 ")).toEqual(["노인 우울", "사회적 지지", "가족 지지"]);
    expect(base).toEqual(["노인 우울", "사회적 지지"]);
    expect(addConcept(base, "   ")).toBe(base);
    expect(addConcept(base, "가".repeat(41))).toBe(base);
    expect(addConcept(base, "노인우울")).toBe(base);
    expect(addConcept(["ai", "b"], "AI")).toEqual(["ai", "b"]);
    const full = ["a", "b", "c", "d", "e"];
    expect(addConcept(full, "f")).toBe(full);
  });

  it("conceptsStatus — 생성이 열려 있으면 making, 칩이 있으면 ready, 실패·취소면 failed, 그 밖은 empty", () => {
    expect(conceptsStatus([], gen({ kind: "concepts", target: null, status: "queued" }))).toBe("making");
    expect(conceptsStatus(["a"], gen({ kind: "concepts", target: null, status: "running" }))).toBe("making");
    expect(conceptsStatus(["a", "b"], gen({ kind: "concepts", target: null, status: "done" }))).toBe("ready");
    expect(conceptsStatus([], gen({ kind: "concepts", target: null, status: "failed" }))).toBe("failed");
    expect(conceptsStatus([], gen({ kind: "concepts", target: null, status: "canceled" }))).toBe("failed");
    expect(conceptsStatus([], gen({ kind: "concepts", target: null, status: "done" }))).toBe("empty");
    expect(conceptsStatus([], null)).toBe("empty");
  });

  it("conceptsRetryable — 칩이 빈 채 실패·취소·끝난 생성만 다시 부른다", () => {
    const g = (status: WorkGeneration["status"]) => gen({ kind: "concepts", target: null, status });
    expect(conceptsRetryable([], g("failed"))).toBe(true);
    expect(conceptsRetryable([], g("canceled"))).toBe(true);
    expect(conceptsRetryable([], g("done"))).toBe(true);
    expect(conceptsRetryable(["사용자 칩"], g("done"))).toBe(false);
    expect(conceptsRetryable([], g("queued"))).toBe(false);
    expect(conceptsRetryable([], null)).toBe(false);
  });

  it("conceptsNote — 뽑는 중이면 대기 문구를 잇고, 비었으면 넣기·다시를 안내한다", () => {
    const running = gen({ kind: "concepts", target: null, status: "running" });
    expect(conceptsNote([], running)).toBe(`핵심 개념을 뽑는 중입니다 · ${genQueueLine(running)}`);
    expect(conceptsNote([], gen({ kind: "concepts", target: null, status: "failed" }))).toBe(
      "핵심 개념을 뽑지 못했습니다 — 직접 넣거나 [다시] 를 누르세요",
    );
    expect(conceptsNote([], gen({ kind: "concepts", target: null, status: "done" }))).toBe(
      "뽑힌 핵심 개념이 없습니다 — 직접 넣거나 [다시] 를 누르세요",
    );
    expect(conceptsNote([], null)).toBe("핵심 개념 넣기 — 원 질문의 핵심 개념을 칩으로 더하세요");
    expect(conceptsNote(["노인 우울"], null)).toBeNull();
  });
});
