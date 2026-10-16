// frontend/tests/unit/useAutoReport.test.ts
import { describe, expect, it } from "vitest";
import { effectScope, shallowRef } from "vue";
import { useAutoReport } from "~/composables/useAutoReport";
import type { GenKind, Outline, ProposalView, WorkGeneration, WorkView } from "~/types/work";

interface Deferred {
  resolve: () => void;
  reject: (err: unknown) => void;
}

function httpError(status: number, detail?: unknown): Error & { status: number } {
  return Object.assign(new Error(`HTTP ${status}`), { status, statusCode: status }, detail === undefined ? {} : { data: { detail } });
}

const NO_PAPERS = { code: "no_section_papers", message: "이 절에 넣을 논문이 없습니다" };

// 묶음 둘(prior.g1·prior.g2) + 연구 공백 — [보고서 만들기]의 반영이 자동 승인한 목차
function outline(over: Partial<Outline> = {}): Outline {
  return {
    topic: { id: 12, title: "세대 간 지지와 노인 우울", question: "q?" },
    basis: "concept",
    groups: [
      { key: "prior.g1", name: "노인의 우울", hint: "노인 우울", papers: ["KCI_A"] },
      { key: "prior.g2", name: "세대 간 지지", hint: "사회적 지지", papers: ["KCI_B"] },
    ],
    questions: ["a?"],
    question: "a?",
    method: "",
    state: "approved",
    gen_id: 41,
    approved_at: "2026-10-17T01:00:00Z",
    auto: true,
    ...over,
  };
}

function proposal(over: Partial<ProposalView> = {}): ProposalView {
  return {
    version: 3,
    outline: outline(),
    sections: {},
    drafts: {},
    papers: {},
    references: {},
    corpus: null,
    stale: { outline: false, sections: {} },
    disclosure: { steps: [] },
    section_gens: {},
    ...over,
  };
}

function work(over: Partial<WorkView> = {}): WorkView {
  return {
    id: "job",
    phase: "proposal",
    concepts: [],
    memo: null,
    is_example: false,
    progress: {},
    generations: [],
    ...over,
  };
}

function gen(id: number, kind: GenKind, target: string, status: WorkGeneration["status"]): WorkGeneration {
  return { id, kind, target, status, model: null, error: null, position: null };
}

// 절 쓰기 요청(POST)·다시 읽기를 하나씩 손으로 끝낸다 — 기록(log)으로 보낸 차례를 본다
function setup(p: ProposalView | null = proposal(), w: WorkView | null = work()) {
  const log: string[] = [];
  const posts: Deferred[] = [];
  const reloads: Deferred[] = [];
  const proposalRef = shallowRef<ProposalView | null>(p);
  const workRef = shallowRef<WorkView | null>(w);
  const scope = effectScope();
  const auto = scope.run(() =>
    useAutoReport({
      proposal: proposalRef,
      work: workRef,
      generate: (key: string) => {
        log.push(`POST ${key}`);
        return new Promise<void>((resolve, reject) => posts.push({ resolve, reject }));
      },
      reload: () => {
        log.push("GET");
        return new Promise<void>((resolve) => reloads.push({ resolve, reject: () => {} }));
      },
    }),
  )!;
  return { auto, log, posts, reloads, proposalRef, workRef, scope };
}

// 루프의 다음 단계·watch 가 돌 만큼 마이크로태스크를 비운다
async function flush(): Promise<void> {
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
}

describe("useAutoReport — 남은 절을 하나씩 넣는다", () => {
  it("앞 요청의 응답을 받은 뒤 다음 키를 문서 순서로 넣는다 — 생성이 끝나기는 기다리지 않는다", async () => {
    const { auto, log, posts } = setup();
    await flush();
    expect(log).toEqual(["POST prior.g1"]);
    expect(auto.running.value).toBe(true);
    posts[0]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2"]);
    posts[1]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap"]);
  });

  it("근거 없음(409 code)은 skipped 에 넣고 다음 키로 간다", async () => {
    const { auto, log, posts } = setup();
    posts[0]!.resolve();
    await flush();
    posts[1]!.reject(httpError(409, NO_PAPERS));
    await flush();
    expect([...auto.skipped.value]).toEqual(["prior.g2"]);
    expect(auto.stopped.value).toBeNull();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap"]);
  });

  it("409 절 쓰는 중·500·네트워크 오류면 다음 키를 넣지 않고 멈춘 까닭을 남긴다", async () => {
    const cases: [unknown, string][] = [
      [httpError(409, "이 절을 쓰는 중입니다"), "이 절을 쓰는 중입니다"],
      [httpError(500), "보고서를 이어 쓰지 못했어요"],
      [new TypeError("Failed to fetch"), "보고서를 이어 쓰지 못했어요 — 네트워크 연결을 확인해 주세요"],
    ];
    for (const [err, message] of cases) {
      const { auto, log, posts, reloads } = setup();
      posts[0]!.reject(err);
      await flush();
      expect(auto.stopped.value).toBe(message);
      // 멈춰도 다시 읽기는 한 번 — 그사이 바뀐 서버 상태로 화면을 맞춘다
      expect(log).toEqual(["POST prior.g1", "GET"]);
      reloads[0]!.resolve();
      await flush();
      expect(auto.running.value).toBe(false);
      expect(log).toEqual(["POST prior.g1", "GET"]);
    }
  });

  it("resume 은 멈춤을 풀고 같은 조건으로 다시 돈다 — 멈춘 키부터", async () => {
    const { auto, log, posts, reloads } = setup();
    posts[0]!.reject(httpError(500));
    await flush();
    reloads[0]!.resolve();
    await flush();
    auto.resume();
    expect(auto.stopped.value).toBeNull();
    await flush();
    expect(log).toEqual(["POST prior.g1", "GET", "POST prior.g1"]);
    expect(auto.running.value).toBe(true);
  });

  it("auto 없음·예시·초안·목차를 다시 만드는 중·조회 전이면 부르지 않고, 조건이 서면 그때 돈다", async () => {
    const before06e: Outline = outline();
    delete before06e.auto;
    const cases: [ProposalView | null, WorkView | null][] = [
      [proposal({ outline: before06e }), work()],
      [proposal(), work({ is_example: true })],
      [proposal({ outline: outline({ state: "draft", approved_at: null }) }), work()],
      [proposal(), work({ generations: [gen(40, "outline", "outline", "queued")] })],
      [null, work()],
    ];
    for (const [p, w] of cases) {
      const { auto, log } = setup(p, w);
      await flush();
      expect(log).toEqual([]);
      expect(auto.running.value).toBe(false);
    }
    // 목차 생성이 끝나 계획서를 다시 읽으면(자동 승인 목차가 들어오면) 그때 돈다 — 탭을 닫았다 와도 같은 조건
    const { log, proposalRef } = setup(null, work());
    proposalRef.value = proposal();
    await flush();
    expect(log).toEqual(["POST prior.g1"]);
  });

  it("넣을 키가 다 끝나면 다시 읽기를 한 번 — 다시 읽은 뒤 남은 절이 없으면 더 넣지 않는다", async () => {
    const { auto, log, posts, reloads, proposalRef } = setup();
    for (let i = 0; i < 3; i += 1) {
      posts[i]!.resolve();
      await flush();
    }
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap", "GET"]);
    expect(auto.running.value).toBe(true);
    // 다시 읽은 계획서에는 세 키의 생성 기록이 있다
    proposalRef.value = proposal({
      section_gens: {
        "prior.g1": { gen_id: 51, status: "queued" },
        "prior.g2": { gen_id: 52, status: "queued" },
        gap: { gen_id: 53, status: "queued" },
      },
    });
    reloads[0]!.resolve();
    await flush();
    expect(auto.running.value).toBe(false);
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap", "GET"]);
  });

  it("다시 읽기 전에도 넣은 키를 또 넣지 않는다", async () => {
    const { log, posts, reloads, workRef } = setup();
    for (let i = 0; i < 3; i += 1) {
      posts[i]!.resolve();
      await flush();
    }
    // 다시 읽기를 기다리는 동안 이벤트로 연구가 바뀌어 watch 가 불려도 새 루프를 열지 않는다
    workRef.value = work({ progress: { sections: 0 } });
    await flush();
    // 다시 읽은 계획서가 아직 생성 기록을 싣지 못했어도(옛 값 그대로) 이 방문에서 넣은 키는 다시 넣지 않는다
    reloads[0]!.resolve();
    await flush();
    workRef.value = work({ progress: { sections: 1 } });
    await flush();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap", "GET"]);
  });

  it("생성 목록에 그 키의 절 생성이 있으면(손으로 [이 절 쓰기]) 계획서를 다시 읽기 전이라도 넣지 않는다", async () => {
    const { log, posts, workRef } = setup();
    // 사용자가 연구 공백을 손으로 쓰기 시작했다 — 이벤트로 생성 목록에 먼저 들어온다
    workRef.value = work({ generations: [gen(60, "section", "gap", "queued")] });
    posts[0]!.resolve();
    await flush();
    posts[1]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "GET"]);
  });

  it("scope 가 끝나면(화면을 떠나면) 다음 키도 다시 읽기도 하지 않는다", async () => {
    const { log, posts, scope } = setup();
    scope.stop();
    posts[0]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1"]);
  });

  it("목차를 새로 만들면(gen_id 가 바뀌면) 건너뜀·멈춤을 비우고 새 목차로 처음부터 같은 조건으로 돈다", async () => {
    const { auto, log, posts, reloads, proposalRef } = setup();
    posts[0]!.reject(httpError(409, NO_PAPERS));
    await flush();
    posts[1]!.reject(httpError(500));
    await flush();
    reloads[0]!.resolve();
    await flush();
    expect([...auto.skipped.value]).toEqual(["prior.g1"]);
    expect(auto.stopped.value).toBe("보고서를 이어 쓰지 못했어요");
    // [보고서 다시 만들기] — 새 반영이 묶음을 다시 나눈 목차(gen_id 42)를 다시 읽었다
    proposalRef.value = proposal({ outline: outline({ gen_id: 42 }) });
    await flush();
    expect(auto.skipped.value.size).toBe(0);
    expect(auto.stopped.value).toBeNull();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "GET", "POST prior.g1"]);
  });

  it("도는 동안 들어온 변화(새 목차)는 루프가 끝난 뒤 다시 본다", async () => {
    const { log, posts, reloads, proposalRef, workRef } = setup();
    // 첫 절을 넣는 사이 [보고서 다시 만들기]를 눌렀다 — 목차 생성이 열리면 연쇄는 다음 키를 넣지 않는다
    workRef.value = work({ generations: [gen(43, "outline", "outline", "queued")] });
    posts[0]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "GET"]);
    // 다시 읽기를 기다리는 사이 새 목차가 반영됐다 — 그때의 watch 는 도는 중이라 막힌다
    workRef.value = work({ generations: [gen(43, "outline", "outline", "done")] });
    proposalRef.value = proposal({
      outline: outline({ gen_id: 43 }),
      section_gens: { "prior.g1": { gen_id: 51, status: "queued" } },
    });
    await flush();
    expect(log).toEqual(["POST prior.g1", "GET"]);
    reloads[0]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "GET", "POST prior.g2"]);
  });
});
