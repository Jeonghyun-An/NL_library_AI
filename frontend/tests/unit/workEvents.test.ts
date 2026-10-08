// frontend/tests/unit/workEvents.test.ts
import { describe, expect, it } from "vitest";
import type {
  ProposalView,
  SectionDeltaEvent,
  TopicsView,
  WorkGeneration,
  WorkGenerationEvent,
  WorkState,
  WorkView,
} from "~/types/work";
import {
  applyWorkEvent,
  initialWorkState,
  latestGeneration,
  openGeneration,
  reloadFor,
  withResource,
  withWork,
} from "~/utils/workEvents";

function gen(id: number, over: Partial<WorkGeneration> = {}): WorkGeneration {
  return { id, kind: "topic_card", target: "12", status: "queued", model: null, error: null, position: null, ...over };
}

function work(over: Partial<WorkView> = {}): WorkView {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    phase: "topics",
    concepts: ["노인 우울", "사회적 지지"],
    memo: null,
    is_example: false,
    progress: { topics: 0, reading: 0, sections: 0, sections_total: 6 },
    generations: [],
    ...over,
  };
}

function withGens(gens: WorkGeneration[], over: Partial<WorkState> = {}): WorkState {
  return { ...initialWorkState(), work: work({ generations: gens }), ...over };
}

function genEvent(over: Partial<WorkGenerationEvent> = {}): WorkGenerationEvent {
  return { kind: "generation", gen_id: 41, gen_kind: "topic_card", target: "12", status: "done", model: "qwen3-vl-8b", result: null, ...over };
}

function delta(over: Partial<SectionDeltaEvent> = {}): SectionDeltaEvent {
  return { kind: "section_delta", gen_id: 52, target: "prior.g1", seq: 0, offset: 0, text: "", ...over };
}

const TOPICS: TopicsView = { picked_id: null, seeds_left: 2, corpus: null, papers: {}, items: [] };

describe("initialWorkState·withWork·withResource", () => {
  it("빈 상태에서 연구·조회를 새 객체로 끼운다", () => {
    const start = initialWorkState();
    expect(start).toEqual({ work: null, topics: null, reading: null, proposal: null, live: {} });
    const w = work();
    const s1 = withWork(start, w);
    expect(s1.work).toBe(w);
    expect(start.work).toBeNull();
    const s2 = withResource(s1, "topics", TOPICS);
    expect(s2.topics).toBe(TOPICS);
    expect(s2.work).toBe(w);
    expect(s1.topics).toBeNull();
  });
});

describe("reloadFor", () => {
  it("끝난 생성의 종류로 다시 읽을 조회를 정하고, 모든 종류가 연구(work)도 다시 읽는다", () => {
    expect(reloadFor("concepts")).toEqual(["work"]);
    expect(reloadFor("topic_card")).toEqual(["topics", "work"]);
    expect(reloadFor("refine")).toEqual(["topics", "work"]);
    expect(reloadFor("facet")).toEqual(["reading", "work"]);
    expect(reloadFor("outline")).toEqual(["proposal", "work"]);
    expect(reloadFor("section")).toEqual(["proposal", "work"]);
    expect(reloadFor("paragraph")).toEqual(["proposal", "work"]);
  });

  it("돌려준 목록을 고쳐도 다음 호출은 그대로다", () => {
    reloadFor("section").push("topics");
    expect(reloadFor("section")).toEqual(["proposal", "work"]);
  });
});

describe("applyWorkEvent — snapshot", () => {
  it("처음 받는 snapshot 은 연구를 끼우기만 하고 다시 읽지 않는다", () => {
    const w = work({ generations: [gen(41, { status: "done" })] });
    const out = applyWorkEvent(initialWorkState(), { kind: "snapshot", work: w });
    expect(out.state.work).toBe(w);
    expect(out.reload).toEqual([]);
  });

  it("하트비트 재동기화 — 열려 있다고 알던 생성이 닫혔거나 빠졌으면 그 조회를 다시 읽는다(중복 없이)", () => {
    const before = withGens([
      gen(41, { status: "queued", position: 1 }),
      gen(42, { status: "running" }),
      gen(43, { kind: "concepts", target: null, status: "running" }),
    ]);
    const out = applyWorkEvent(before, {
      kind: "snapshot",
      work: work({ generations: [gen(41, { status: "done" }), gen(42, { status: "failed" })] }),
    });
    expect(out.reload).toEqual(["topics", "work"]);
    expect(out.state.work!.generations.map((g) => g.status)).toEqual(["done", "failed"]);
  });

  it("처음 보는 생성이 이미 끝나 있으면(구독 전에 놓친 done) 그 조회를 다시 읽고, 그대로 열려 있으면 읽지 않는다", () => {
    const before = withGens([gen(41, { status: "queued" })]);
    const missed = applyWorkEvent(before, {
      kind: "snapshot",
      work: work({ generations: [gen(41, { status: "queued" }), gen(44, { kind: "outline", target: "outline", status: "done" })] }),
    });
    expect(missed.reload).toEqual(["proposal", "work"]);
    const same = applyWorkEvent(before, { kind: "snapshot", work: work({ generations: [gen(41, { status: "running" })] }) });
    expect(same.reload).toEqual([]);
  });

  it("이미 끝나 있던 생성은 다시 읽지 않는다", () => {
    const before = withGens([gen(41, { status: "done" })]);
    const out = applyWorkEvent(before, { kind: "snapshot", work: work({ generations: [gen(41, { status: "done" })] }) });
    expect(out.reload).toEqual([]);
  });

  it("열린 절 생성이 아닌 흐르던 글은 비우고, 아직 쓰는 절의 글은 둔다", () => {
    const before = withGens([gen(52, { kind: "section", target: "prior.g1", status: "running" })], {
      live: {
        "prior.g1": { genId: 52, text: "앞 문장", nextSeq: 3, broken: false },
        gap: { genId: 50, text: "옛 글", nextSeq: 9, broken: false },
      },
    });
    const out = applyWorkEvent(before, {
      kind: "snapshot",
      work: work({ generations: [gen(52, { kind: "section", target: "prior.g1", status: "running" })] }),
    });
    expect(Object.keys(out.state.live)).toEqual(["prior.g1"]);
    expect(out.state.live["prior.g1"]!.text).toBe("앞 문장");
  });
});

describe("applyWorkEvent — generation", () => {
  it("처음 보는 queued 생성을 id 순으로 더하고 순번은 아직 모른다", () => {
    const before = withGens([gen(40, { status: "done" }), gen(43, { status: "queued", position: 2 })]);
    const out = applyWorkEvent(before, genEvent({ gen_id: 41, status: "queued", model: null }));
    expect(out.reload).toEqual([]);
    expect(out.state.work!.generations.map((g) => g.id)).toEqual([40, 41, 43]);
    expect(out.state.work!.generations[1]).toEqual({
      id: 41, kind: "topic_card", target: "12", status: "queued", model: null, error: null,
      position: null, eta_sec: null, others_ahead: false,
    });
  });

  it("끝나면 상태·모델을 바꾸고 순번을 지우며 그 종류의 조회를 다시 읽는다", () => {
    const before = withGens([gen(41, { status: "queued", position: 2, eta_sec: 60, others_ahead: true })]);
    const out = applyWorkEvent(before, genEvent({ gen_id: 41, status: "done", model: "qwen3-vl-8b" }));
    expect(out.reload).toEqual(["topics", "work"]);
    expect(out.state.work!.generations[0]).toEqual({
      id: 41, kind: "topic_card", target: "12", status: "done", model: "qwen3-vl-8b", error: null,
      position: null, eta_sec: null, others_ahead: false,
    });
    expect(before.work!.generations[0]!.status).toBe("queued");
  });

  it("대기 중 이벤트는 알던 순번을 둔다", () => {
    const before = withGens([gen(41, { status: "queued", position: 2, eta_sec: 60, others_ahead: true })]);
    const out = applyWorkEvent(before, genEvent({ gen_id: 41, status: "queued", model: null }));
    expect(out.state.work!.generations[0]).toMatchObject({ position: 2, eta_sec: 60, others_ahead: true });
  });

  it("끝난 생성에 늦게 온 queued 는 무시한다", () => {
    const before = withGens([gen(41, { status: "done", model: "gemma-3-12b" })]);
    const out = applyWorkEvent(before, genEvent({ gen_id: 41, status: "queued", model: null }));
    expect(out.state).toBe(before);
    expect(out.reload).toEqual([]);
  });

  it("절 생성이 끝나면 그 생성의 흐르던 글을 지우고, 새 절 생성이 열리면 옛 생성의 글을 지운다", () => {
    const live = { "prior.g1": { genId: 52, text: "쓰던 글", nextSeq: 4, broken: false } };
    const writing = withGens([gen(52, { kind: "section", target: "prior.g1", status: "running" })], { live });
    const done = applyWorkEvent(writing, genEvent({ gen_id: 52, gen_kind: "section", target: "prior.g1", status: "done" }));
    expect(done.state.live).toEqual({});
    expect(done.reload).toEqual(["proposal", "work"]);
    // 다른 생성의 끝(같은 절의 옛 생성)은 지금 흐르는 글을 건드리지 않는다
    const old = applyWorkEvent(writing, genEvent({ gen_id: 50, gen_kind: "section", target: "prior.g1", status: "failed" }));
    expect(old.state.live).toEqual(live);
    const again = applyWorkEvent(writing, genEvent({ gen_id: 53, gen_kind: "section", target: "prior.g1", status: "queued" }));
    expect(again.state.live).toEqual({});
  });

  it("연구를 아직 받지 않았으면 생성 목록은 두고 다시 읽을 조회만 알린다", () => {
    const out = applyWorkEvent(initialWorkState(), genEvent({ gen_kind: "concepts", target: null, status: "done" }));
    expect(out.state.work).toBeNull();
    expect(out.reload).toEqual(["work"]);
  });
});

describe("applyWorkEvent — work", () => {
  it("단계·진행 요약을 바꾸고 다른 값은 둔다", () => {
    const before = withGens([gen(41)]);
    const out = applyWorkEvent(before, { kind: "work", phase: "reading", progress: { topics: 4, reading: 12, sections: 0, sections_total: 6 } });
    expect(out.reload).toEqual([]);
    expect(out.state.work!.phase).toBe("reading");
    expect(out.state.work!.progress).toEqual({ topics: 4, reading: 12, sections: 0, sections_total: 6 });
    expect(out.state.work!.generations).toBe(before.work!.generations);
    expect(before.work!.phase).toBe("topics");
  });

  it("연구를 아직 받지 않았으면 그대로다", () => {
    const start = initialWorkState();
    expect(applyWorkEvent(start, { kind: "work", phase: "reading", progress: {} }).state).toBe(start);
  });
});

describe("applyWorkEvent — section_delta", () => {
  it("offset 이 받은 글자 수와 맞으면 이어 붙인다", () => {
    let s = initialWorkState();
    s = applyWorkEvent(s, delta({ seq: 0, offset: 0, text: "노인의 우울은 " })).state;
    s = applyWorkEvent(s, delta({ seq: 1, offset: 8, text: "사회적 지지와 함께 다뤄졌다 [E1]." })).state;
    expect(s.live["prior.g1"]).toEqual({ genId: 52, text: "노인의 우울은 사회적 지지와 함께 다뤄졌다 [E1].", nextSeq: 2, broken: false });
  });

  it("offset 이 어긋나면 broken 으로 두고 받은 글은 남기며, 그 뒤 조각은 잇지 않는다", () => {
    let s = applyWorkEvent(initialWorkState(), delta({ seq: 0, offset: 0, text: "앞 글" })).state;
    s = applyWorkEvent(s, delta({ seq: 2, offset: 10, text: "건너뛴 뒤" })).state;
    expect(s.live["prior.g1"]).toEqual({ genId: 52, text: "앞 글", nextSeq: 3, broken: true });
    const after = applyWorkEvent(s, delta({ seq: 3, offset: 3, text: "더" })).state;
    expect(after.live).toBe(s.live);
  });

  it("reset 이면 비우고 broken 을 푼다", () => {
    let s = applyWorkEvent(initialWorkState(), delta({ seq: 0, offset: 0, text: "첫 시도" })).state;
    s = applyWorkEvent(s, delta({ seq: 1, offset: 9, text: "x" })).state;
    s = applyWorkEvent(s, delta({ seq: 2, offset: 0, text: "", reset: true })).state;
    expect(s.live["prior.g1"]).toEqual({ genId: 52, text: "", nextSeq: 3, broken: false });
    s = applyWorkEvent(s, delta({ seq: 3, offset: 0, text: "다시" })).state;
    expect(s.live["prior.g1"]!.text).toBe("다시");
  });

  it("처음 받는 조각이 처음부터가 아니면(재접속) 글 없이 broken 이다", () => {
    const s = applyWorkEvent(initialWorkState(), delta({ seq: 5, offset: 120, text: "중간" })).state;
    expect(s.live["prior.g1"]).toEqual({ genId: 52, text: "", nextSeq: 6, broken: true });
  });

  it("같은 절의 다른 생성 조각은 새로 시작한다", () => {
    let s = applyWorkEvent(initialWorkState(), delta({ gen_id: 50, seq: 0, offset: 0, text: "옛 글" })).state;
    s = applyWorkEvent(s, delta({ gen_id: 52, seq: 0, offset: 0, text: "새 글" })).state;
    expect(s.live["prior.g1"]).toEqual({ genId: 52, text: "새 글", nextSeq: 1, broken: false });
  });

  it("글자 수는 서버(파이썬 len)처럼 코드포인트로 센다", () => {
    let s = applyWorkEvent(initialWorkState(), delta({ seq: 0, offset: 0, text: "𝑥 값" })).state;
    s = applyWorkEvent(s, delta({ seq: 1, offset: 3, text: "이다" })).state;
    expect(s.live["prior.g1"]).toEqual({ genId: 52, text: "𝑥 값이다", nextSeq: 2, broken: false });
  });

  it("다른 절의 흐르는 글은 건드리지 않는다", () => {
    let s = applyWorkEvent(initialWorkState(), delta({ gen_id: 50, target: "gap", seq: 0, offset: 0, text: "공백" })).state;
    s = applyWorkEvent(s, delta({ seq: 0, offset: 0, text: "선행" })).state;
    expect(Object.keys(s.live).sort()).toEqual(["gap", "prior.g1"]);
    expect(s.live.gap!.text).toBe("공백");
  });
});

describe("applyWorkEvent — 모르는 이벤트", () => {
  it("뒤 라운드의 이벤트(grid 등)는 같은 상태를 돌려준다", () => {
    const before = withGens([gen(41)]);
    const unknown = { kind: "grid", cells: [] } as unknown as Parameters<typeof applyWorkEvent>[1];
    const out = applyWorkEvent(before, unknown);
    expect(out.state).toBe(before);
    expect(out.reload).toEqual([]);
  });
});

describe("openGeneration·latestGeneration", () => {
  const state = withGens([
    gen(40, { kind: "concepts", target: null, status: "done" }),
    gen(41, { target: "12", status: "failed" }),
    gen(45, { target: "12", status: "queued" }),
    gen(46, { target: "13", status: "running" }),
    gen(47, { target: "12", status: "done" }),
  ]);

  it("가장 최근(id 가 큰) 생성을 고르고, target 을 주면 그 대상만 본다", () => {
    expect(latestGeneration(state, "topic_card")?.id).toBe(47);
    expect(latestGeneration(state, "topic_card", "13")?.id).toBe(46);
    expect(latestGeneration(state, "concepts", null)?.id).toBe(40);
    expect(latestGeneration(state, "outline")).toBeNull();
  });

  it("열린(queued·running) 생성만 고른다", () => {
    expect(openGeneration(state, "topic_card")?.id).toBe(46);
    expect(openGeneration(state, "topic_card", "12")?.id).toBe(45);
    expect(openGeneration(state, "concepts")).toBeNull();
    expect(openGeneration(initialWorkState(), "topic_card")).toBeNull();
  });
});

describe("withResource — 계획서", () => {
  it("계획서 조회를 끼우고 흐르는 글은 그대로 둔다", () => {
    const proposal = { version: 3 } as ProposalView;
    const live = { gap: { genId: 60, text: "x", nextSeq: 1, broken: false } };
    const out = withResource({ ...initialWorkState(), live }, "proposal", proposal);
    expect(out.proposal).toBe(proposal);
    expect(out.live).toBe(live);
  });
});
