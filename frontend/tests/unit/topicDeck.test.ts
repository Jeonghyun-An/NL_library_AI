// frontend/tests/unit/topicDeck.test.ts
import { describe, expect, it } from "vitest";
import type {
  KeywordCandidate,
  PaperMeta,
  TopicCard,
  TopicItem,
  TopicSeed,
  TopicsView,
  WorkGeneration,
} from "~/types/work";
import { genQueueLine } from "~/utils/queueLine";
import {
  addConcept,
  aiCardsStale,
  canPick,
  cardArrived,
  cardNumbersLine,
  cardNote,
  cardRemakingNote,
  cardStatus,
  chipFocusAfterToggle,
  cleanConcept,
  conceptsNote,
  conceptsRetryable,
  conceptsStatus,
  deckOrder,
  deckQueueLine,
  evidenceChips,
  keywordChips,
  keywordSpans,
  keywordWarning,
  keywordsChanged,
  liveTopics,
  MIN_PICKED_KEYWORDS,
  moreLine,
  regenerateFocusMoves,
  regenerateProblem,
  seedLine,
  toggleKeyword,
  topicProblem,
} from "~/utils/topicDeck";
import keywordMatch from "../fixtures/keyword_match.json";

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

  it("생성 기록이 없는 빈 씨앗 자리는 키워드 생성이 있으면 waiting, 실패했으면 blocked 다(06e — 카드는 키워드가 정해진 뒤 들어간다)", () => {
    const concepts = (status: WorkGeneration["status"]) => gen({ id: 40, kind: "concepts", target: null, status });
    expect(cardStatus(item({ generation: null }), concepts("queued"))).toBe("waiting");
    expect(cardStatus(item({ generation: null }), concepts("running"))).toBe("waiting");
    // 씨앗 자리 카드 생성은 키워드 반영·취소와 같은 트랜잭션에 들어간다 — done·canceled 이벤트가 온 뒤 topics·work 를
    // 다시 읽기 전까지는 그 생성이 목록에 없다. 그 사이도 기다리는 중이다('카드를 만들지 못했습니다'가 비치지 않게)
    expect(cardStatus(item({ generation: null }), concepts("done"))).toBe("waiting");
    expect(cardStatus(item({ generation: null }), concepts("canceled"))).toBe("waiting");
    expect(cardStatus(item({ generation: null }), concepts("failed"))).toBe("blocked");
    expect(cardNote("blocked")).toBe("키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다");
    // 씨앗 자리가 아닌 빈 카드는 지금처럼 failed, 근거 부족은 그대로, 생성이 있으면 생성 상태가 먼저다
    expect(cardStatus(item({ generation: null, slot: null, origin: "other" }), concepts("done"))).toBe("failed");
    expect(cardStatus(item({ generation: null, slot: null, origin: "other" }), concepts("failed"))).toBe("failed");
    expect(cardStatus(item({ state: "insufficient", generation: null }), concepts("running"))).toBe("insufficient");
    expect(cardStatus(item({ generation: { id: 41, status: "running" } }), concepts("failed"))).toBe("making");
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
  it("카드를 새 키워드로 다시 만드는 중이면(카드 생성이 열려 있으면) 고르지 않고 그 줄을 보인다(06e 정함 16)", () => {
    for (const status of ["queued", "running"] as const) {
      const remaking = item({ card: CARD, generation: { id: 52, status } });
      expect(canPick(remaking)).toBe(false);
      expect(cardRemakingNote(remaking)).toBe("새 키워드로 다시 만드는 중입니다");
    }
    expect(cardRemakingNote(item({ card: CARD, generation: { id: 52, status: "done" } }))).toBeNull();
    expect(cardRemakingNote(item({ card: CARD, generation: null, origin: "user" }))).toBeNull();
    // 카드가 없는 자리의 열린 생성은 대기 뼈대(cardStatus waiting·making)가 알린다
    expect(cardRemakingNote(item({ generation: { id: 52, status: "running" } }))).toBeNull();
  });

  it("카드가 있는 후보만 고를 수 있다", () => {
    expect(canPick(item({ card: CARD, generation: { id: 41, status: "done" } }))).toBe(true);
    expect(canPick(item({ card: CARD, generation: null, origin: "user" }))).toBe(true);
    expect(canPick(item({ card: CARD, state: "picked", generation: { id: 41, status: "done" } }))).toBe(false);
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
    expect(seedLine(SEED)).toBe("딥리서치 보고서의 향후 과제 · 노인 우울과 사회적 지지의 관계");
    expect(seedLine({ ...SEED, kind: "insufficient", key: "insufficient:3" })).toBe(
      "근거가 모자랐던 하위질문 · 노인 우울과 사회적 지지의 관계",
    );
    expect(seedLine({ ...SEED, heading: "  " })).toBe("딥리서치 보고서의 향후 과제");
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
    expect(conceptsNote([], running)).toBe(`키워드를 뽑는 중입니다 · ${genQueueLine(running)}`);
    expect(conceptsNote([], gen({ kind: "concepts", target: null, status: "failed" }))).toBe(
      "키워드를 뽑지 못했습니다 — 직접 넣거나 [다시] 를 누르세요",
    );
    expect(conceptsNote([], gen({ kind: "concepts", target: null, status: "done" }))).toBe(
      "뽑힌 키워드가 없습니다 — 직접 넣거나 [다시] 를 누르세요",
    );
    expect(conceptsNote([], null)).toBe("키워드 넣기 — 원 질문의 키워드를 칩으로 더하세요");
    expect(conceptsNote(["노인 우울"], null)).toBeNull();
  });
});

// ── 제목 고르기 — 키워드(06e D23) ──

// 06e 만의 하이라이트 자리 — 일치(참·거짓)의 정본은 06c 의 term_checks.json 이다(사례는 그 contains 칸과 같은 text/word)
interface KeywordMatchCase {
  text: string;
  word: string;
  marked: string[];
  note: string;
}
const MATCH_CASES: KeywordMatchCase[] = keywordMatch;

describe("keywordSpans — keyword_match.json 의 하이라이트 자리", () => {
  it("고정 예제가 맞음·안 맞음·공백 무시·전각·영문 사례를 다 갖고 있다", () => {
    expect(MATCH_CASES.some((c) => c.marked.length === 0)).toBe(true);
    expect(MATCH_CASES.some((c) => c.marked.length > 1)).toBe(true);
    expect(MATCH_CASES.some((c) => c.marked.some((m) => /\s/.test(m)))).toBe(true);
    expect(MATCH_CASES.some((c) => c.text !== c.text.normalize("NFKC"))).toBe(true);
    expect(MATCH_CASES.some((c) => /[A-Za-z]/.test(c.text))).toBe(true);
  });

  it.each(MATCH_CASES)("$note", (c) => {
    const parts = keywordSpans(c.text, [c.word]);
    expect(parts.filter((p) => p.mark).map((p) => p.text)).toEqual(c.marked);
    expect(parts.map((p) => p.text).join("")).toBe(c.text);
  });

  it("여러 키워드는 각자 처음 맞은 자리를, 겹치는 자리는 하나로 감싼다", () => {
    expect(keywordSpans("독거노인의 사회적 지지와 우울", ["사회적 지지", "노인 우울", "지지"])).toEqual([
      { text: "독거", mark: false },
      { text: "노인", mark: true },
      { text: "의 ", mark: false },
      { text: "사회적 지지", mark: true },
      { text: "와 ", mark: false },
      { text: "우울", mark: true },
    ]);
    // 맞닿은 자리도 하나로 합친다
    expect(keywordSpans("노인우울 연구", ["노인", "우울"])).toEqual([
      { text: "노인우울", mark: true },
      { text: " 연구", mark: false },
    ]);
    // 한 키워드가 여러 번 나와도 처음 맞은 자리만 감싼다
    expect(keywordSpans("노인과 노인", ["노인"])).toEqual([
      { text: "노인", mark: true },
      { text: "과 노인", mark: false },
    ]);
    expect(keywordSpans("노인 우울", [])).toEqual([{ text: "노인 우울", mark: false }]);
    expect(keywordSpans("", ["노인"])).toEqual([]);
  });
});

describe("keywordsChanged·keywordWarning", () => {
  const made: TopicCard = { ...CARD, keywords: ["노인 우울", "사회적 지지"] };

  it("카드를 만든 키워드와 지금 고른 키워드가 다르면 바뀌었다 — 순서·띄어쓰기는 보지 않고, 06e 전 카드는 알리지 않는다", () => {
    expect(keywordsChanged(made, ["사회적지지", "노인 우울"])).toBe(false);
    expect(keywordsChanged(made, ["노인 우울"])).toBe(true);
    expect(keywordsChanged(made, ["노인 우울", "가족 지지"])).toBe(true);
    expect(keywordsChanged({ ...made, keywords: [] }, ["노인 우울"])).toBe(true);
    expect(keywordsChanged(CARD, ["노인 우울"])).toBe(false);
  });

  it("제목에 고른 키워드가 하나도 없을 때만 경고하고, 사용자가 고친 카드는 알리지 않는다", () => {
    const missed: TopicCard = { ...made, checks: { ...CARD.checks, missing_keywords: ["노인 우울", "사회적 지지"] } };
    expect(keywordWarning(missed)).toBe("제목에 「노인 우울」·「사회적 지지」 없음");
    expect(keywordWarning({ ...missed, checks: { ...CARD.checks, missing_keywords: ["노인 우울"] } })).toBeNull();
    expect(keywordWarning({ ...missed, edited: true })).toBeNull();
    expect(keywordWarning({ ...CARD, keywords: [] })).toBeNull();
    expect(keywordWarning(CARD)).toBeNull();
  });
});

describe("keywordChips·toggleKeyword·regenerateProblem", () => {
  const CANDS: KeywordCandidate[] = [
    { text: "노인 우울", source: "both", n: 4 },
    { text: "사회적 지지", source: "llm", n: 0 },
    { text: "독거노인", source: "paper", n: 3 },
  ];

  it("후보를 낸 순서대로, 고른 것은 눌린 칩·출처와 편수 배지, 후보에 없는 고른 말은 뒤에 '직접'", () => {
    expect(keywordChips(CANDS, ["사회적지지", "가족 돌봄"])).toEqual([
      { text: "노인 우울", pressed: false, badge: "AI · 논문 4편" },
      { text: "사회적 지지", pressed: true, badge: "AI 후보" },
      { text: "독거노인", pressed: false, badge: "논문 3편" },
      { text: "가족 돌봄", pressed: true, badge: "직접" },
    ]);
  });

  it("후보가 없는 연구(06e 전·예시)는 고른 키워드를 눌린 칩으로만 보인다", () => {
    const want = [{ text: "노인 우울", pressed: true, badge: null }];
    expect(keywordChips(null, ["노인 우울"])).toEqual(want);
    expect(keywordChips(undefined, ["노인 우울"])).toEqual(want);
    expect(keywordChips([], ["노인 우울"])).toEqual(want);
  });

  it("toggleKeyword — 고른 것은 빼고 아니면 뒤에 더하되 칩 상한(5)을 넘지 않는다, regenerateProblem — 둘 미만이면 까닭", () => {
    expect(toggleKeyword(["노인 우울", "사회적 지지"], "노인우울")).toEqual(["사회적 지지"]);
    expect(toggleKeyword(["노인 우울"], "독거노인")).toEqual(["노인 우울", "독거노인"]);
    const full = ["가", "나", "다", "라", "마"];
    expect(toggleKeyword(full, "바")).toEqual(full);
    expect(MIN_PICKED_KEYWORDS).toBe(2);
    expect(regenerateProblem(["노인 우울"])).toBe("키워드를 2개 이상 고르면 다시 만들 수 있습니다");
    expect(regenerateProblem(["노인 우울", "독거노인"])).toBeNull();
  });
});

// 누른 버튼이 v-if 로 사라지면 초점이 body 로 떨어진다(TopicCard [직접 고치기] 와 같은 문제 — 운영 확인 2026-10-08).
// ConceptChips 는 이 판정으로 초점을 옮긴다(06e K8 quality 검토 반영)
describe("chipFocusAfterToggle·regenerateFocusMoves — 사라지는 버튼의 초점", () => {
  const CANDS: KeywordCandidate[] = [
    { text: "노인 우울", source: "both", n: 4 },
    { text: "사회적 지지", source: "llm", n: 0 },
    { text: "독거노인", source: "paper", n: 3 },
  ];
  // 칩 하나를 누르기 전·뒤의 칩 목록 — 부품과 같은 길(keywordChips·toggleKeyword)로 만든다
  const press = (cands: KeywordCandidate[] | null, picked: string[], text: string) =>
    chipFocusAfterToggle(keywordChips(cands, picked), keywordChips(cands, toggleKeyword(picked, text)), text);

  it("누른 칩이 남으면 그 칩이다 — 후보 칩은 빼도 눌리지 않은 칩으로, 더해도 눌린 칩으로 남는다", () => {
    expect(press(CANDS, ["노인 우울", "사회적 지지"], "노인 우울")).toBe("노인 우울");
    expect(press(CANDS, ["노인 우울"], "독거노인")).toBe("독거노인");
  });

  it("후보가 없는 연구의 칩을 빼면 사라진 칩 다음 칩, 마지막 칩이었으면 null(직접 더하기 칸으로)", () => {
    const picked = ["노인 우울", "사회적 지지", "독거노인"];
    expect(press(null, picked, "노인 우울")).toBe("사회적 지지");
    expect(press(null, picked, "사회적 지지")).toBe("독거노인");
    expect(press(null, picked, "독거노인")).toBeNull();
    expect(press([], ["노인 우울"], "노인 우울")).toBeNull();
  });

  it("'직접' 칩을 빼면 그 뒤의 칩, 뒤에 칩이 없으면 null — 앞의 후보 칩으로 돌아가지 않는다", () => {
    const picked = ["노인 우울", "가족 돌봄", "돌봄 부담"];
    expect(press(CANDS, picked, "가족 돌봄")).toBe("돌봄 부담");
    expect(press(CANDS, picked, "돌봄 부담")).toBeNull();
  });

  it("regenerateFocusMoves — 보이던 다시 만들기 줄이 사라질 때, 줄 안에 초점이 있었거나 그 버튼으로 부른 뒤에만 옮긴다", () => {
    const gone = { wasShown: true, shown: false };
    // 부르는 동안 버튼이 막혀 브라우저가 초점을 이미 놓았어도(줄 안에 초점 없음) 누른 것을 기억해 옮긴다
    expect(regenerateFocusMoves({ ...gone, asked: true, focusInside: false })).toBe(true);
    expect(regenerateFocusMoves({ ...gone, asked: false, focusInside: true })).toBe(true);
    // 다른 곳(칩·[되돌리기])에서 줄이 사라지게 한 것 — 초점은 그 자리의 몫이다
    expect(regenerateFocusMoves({ ...gone, asked: false, focusInside: false })).toBe(false);
    // 줄이 그대로 남았거나(409 등으로 끝남) 처음부터 없던 때
    expect(regenerateFocusMoves({ wasShown: true, shown: true, asked: true, focusInside: true })).toBe(false);
    expect(regenerateFocusMoves({ wasShown: false, shown: false, asked: true, focusInside: true })).toBe(false);
  });
});

describe("aiCardsStale — 다시 만들 AI 자리가 있다", () => {
  const made: TopicCard = { ...CARD, keywords: ["노인 우울", "사회적 지지"] };
  const now = ["노인 우울", "독거노인"];
  const concepts = (status: WorkGeneration["status"]) => gen({ id: 40, kind: "concepts", target: null, status });

  it("지금 키워드와 다른 키워드로 만든 AI 후보 카드가 있을 때 — 고른·고친·직접 쓴 카드와 다시 만드는 중인 카드는 세지 않는다", () => {
    const done = { id: 41, status: "done" as const };
    expect(aiCardsStale(deck([item({ card: made, generation: done })]), now)).toBe(true);
    expect(aiCardsStale(deck([item({ card: made, generation: done })]), ["사회적 지지", "노인 우울"])).toBe(false);
    // 픽스처 기본 생성(queued)이면 '다시 만드는 중'만으로 거짓이 된다 — 끝난 생성(사용자 카드는 생성 기록 없음)을 준다
    expect(aiCardsStale(deck([item({ card: made, state: "picked", generation: done })]), now)).toBe(false);
    expect(aiCardsStale(deck([item({ card: { ...made, edited: true }, generation: done })]), now)).toBe(false);
    expect(aiCardsStale(deck([item({ card: made, origin: "user", seed: null, generation: null })]), now)).toBe(false);
    expect(aiCardsStale(deck([item({ card: null, state: "insufficient" })]), now)).toBe(false);
    expect(aiCardsStale(deck([item({ card: made, generation: { id: 52, status: "running" } })]), now)).toBe(false);
  });

  it("키워드 생성이 실패해 카드가 들어가지 않은 빈 씨앗 자리(blocked)도 다시 만들 자리다 — 키워드를 직접 넣고 저장한 뒤의 길", () => {
    const blocked = deck([item({ card: null, generation: null })]);
    expect(aiCardsStale(blocked, now, concepts("failed"))).toBe(true);
    // 키워드 생성이 끝난 직후(카드 생성을 다시 읽기 전)는 기다리는 중이라 세지 않는다
    expect(aiCardsStale(blocked, now, concepts("done"))).toBe(false);
    expect(aiCardsStale(blocked, now)).toBe(false);
  });
});
