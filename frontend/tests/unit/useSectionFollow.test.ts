// frontend/tests/unit/useSectionFollow.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, effectScope, nextTick, ref, type EffectScope } from "vue";
import { useSectionFollow } from "~/composables/useSectionFollow";
import type { ResearchPhase } from "~/utils/researchEvents";
import { FOLLOW_PILL_EXPLORE, FOLLOW_PILL_WRITE } from "~/utils/researchFollow";

// 컴포넌트 밖에서 부른다 — 창 입력 리스너(onMounted)는 걸리지 않고, 옮기기(nextTick → 다음 프레임 → scrollIntoView)와 알약만 본다.
// 자리 요소(rs-sec-N·rs-slot-N — 둘 다 tabindex=-1)는 scrollIntoView·focus 만 흉내 낸다
type FakeSpot = { scrollIntoView: ReturnType<typeof vi.fn>; focus: ReturnType<typeof vi.fn> };
type SpotId = "rs-sec-1" | "rs-sec-2" | "rs-slot-0" | "rs-slot-1";

let spots: Record<SpotId, FakeSpot>;
let frames: Map<number, FrameRequestCallback>;
let lastFrame: number;
let scope: EffectScope;

function spot(): FakeSpot {
  return { scrollIntoView: vi.fn(), focus: vi.fn() };
}

beforeEach(() => {
  spots = { "rs-sec-1": spot(), "rs-sec-2": spot(), "rs-slot-0": spot(), "rs-slot-1": spot() };
  frames = new Map();
  lastFrame = 0;
  // 그려지지 않은 자리(rs-sec-9 등)는 null
  vi.stubGlobal("document", { getElementById: (id: string) => (id in spots ? spots[id as SpotId] : null) });
  vi.stubGlobal("window", { matchMedia: () => ({ matches: false }) });
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    lastFrame += 1;
    frames.set(lastFrame, cb);
    return lastFrame;
  });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => {
    frames.delete(id);
  });
  scope = effectScope();
});

afterEach(() => {
  scope.stop();
  vi.unstubAllGlobals();
});

// 감시(pre)·nextTick 을 다 흘려보낸 뒤 걸린 프레임을 돌린다
async function settle(): Promise<void> {
  await nextTick();
  await new Promise((resolve) => setTimeout(resolve, 0));
  const due = [...frames.values()];
  frames.clear();
  for (const cb of due) cb(0);
}

function setup(o: { phase?: ResearchPhase; target?: string | null; startPaused?: boolean } = {}) {
  const phase = ref<ResearchPhase | null>(o.phase ?? "synthesizing");
  const target = ref<string | null>(o.target === undefined ? null : o.target);
  const follow = scope.run(() =>
    useSectionFollow({
      phase: computed(() => phase.value),
      target: computed(() => target.value),
      isBlocked: () => false,
      startPaused: o.startPaused ?? false,
    }),
  )!;
  return { phase, target, follow };
}

describe("useSectionFollow — 알약", () => {
  it("알약을 누르면 지금 대상으로 옮기며 초점도 그 자리로 옮긴다 — 누른 알약이 사라져도 초점이 body 로 떨어지지 않는다", async () => {
    const { follow } = setup({ target: "rs-sec-1", startPaused: true });
    expect(follow.pill.value).toBe(FOLLOW_PILL_WRITE);

    follow.resume();
    expect(follow.pill.value).toBeNull();
    await settle();
    expect(spots["rs-sec-1"].scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    expect(spots["rs-sec-1"].focus).toHaveBeenCalledWith({ preventScroll: true });
  });

  it("따라가며 대상이 바뀌어 옮길 때는 초점을 옮기지 않는다 — 읽거나 고르던 초점을 빼앗지 않는다", async () => {
    const { target } = setup({ target: "rs-sec-1" });
    await settle();
    // 처음 본 대상은 기준으로만 삼는다
    expect(spots["rs-sec-1"].scrollIntoView).not.toHaveBeenCalled();

    target.value = "rs-sec-2";
    await settle();
    expect(spots["rs-sec-2"].scrollIntoView).toHaveBeenCalledTimes(1);
    expect(spots["rs-sec-2"].focus).not.toHaveBeenCalled();
  });

  it("따라가며 옮길 때는 가장 가까운 끝에 맞춘다(nearest) — 방금 끝난 절·하위질문이 화면 위로 밀려나지 않는다. 알약을 누른 이동만 머리를 위에 맞춘다(start)", async () => {
    // 종합기는 절 i 의 done 을 보내자마자 i+1 의 running 을 보낸다 — 사이(null)를 거쳐 다음 절로 바뀐다
    const write = setup({ target: "rs-sec-1" });
    await settle();
    write.target.value = null;
    write.target.value = "rs-sec-2";
    await settle();
    expect(spots["rs-sec-2"].scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "nearest" });

    // 탐색 중 하위질문 자리도 같다 — '근거 N편 ✓' 가 튀어 오르는 자리가 다음 자리에 가려지지 않는다
    const explore = setup({ phase: "exploring", target: "rs-slot-0" });
    await settle();
    explore.target.value = "rs-slot-1";
    await settle();
    expect(spots["rs-slot-1"].scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "nearest" });

    // 알약은 사용자가 고른 이동이라 그 자리 머리를 막대 바로 아래에 둔다
    explore.follow.pause();
    explore.follow.resume();
    await settle();
    expect(spots["rs-slot-1"].scrollIntoView).toHaveBeenLastCalledWith({ behavior: "smooth", block: "start" });
  });

  it("멈춘 동안 절과 절 사이(쓰는·도는 것이 잠깐 없음)에도 알약이 남는다 — 사라졌다 다시 서면 알약에 가 있던 초점이 body 로 떨어진다", async () => {
    const write = setup({ target: "rs-sec-1", startPaused: true });
    write.target.value = null;
    await settle();
    expect(write.follow.pill.value).toBe(FOLLOW_PILL_WRITE);
    write.target.value = "rs-sec-2";
    await settle();
    expect(write.follow.pill.value).toBe(FOLLOW_PILL_WRITE);
    // 멈춘 동안은 옮기지 않는다
    expect(spots["rs-sec-2"].scrollIntoView).not.toHaveBeenCalled();

    const explore = setup({ phase: "exploring", target: "rs-slot-0", startPaused: true });
    explore.target.value = null;
    await settle();
    expect(explore.follow.pill.value).toBe(FOLLOW_PILL_EXPLORE);
  });

  it("사이에 알약을 누르면 마지막으로 진행한 자리로 옮기며 초점을 주고, 다음 절이 시작되면 그리로 따라간다", async () => {
    const { target, follow } = setup({ target: "rs-sec-1", startPaused: true });
    target.value = null;
    await settle();

    follow.resume();
    await settle();
    expect(spots["rs-sec-1"].scrollIntoView).toHaveBeenCalledTimes(1);
    expect(spots["rs-sec-1"].focus).toHaveBeenCalledWith({ preventScroll: true });

    target.value = "rs-sec-2";
    await settle();
    expect(spots["rs-sec-2"].scrollIntoView).toHaveBeenCalledTimes(1);
    expect(spots["rs-sec-2"].focus).not.toHaveBeenCalled();
  });

  it("진행한 자리가 한 번도 없었거나 진행 단계가 끝나면(최종본 뒤) 알약은 없다", async () => {
    const never = setup({ phase: "exploring", target: null, startPaused: true });
    expect(never.follow.pill.value).toBeNull();

    const done = setup({ target: "rs-sec-2", startPaused: true });
    done.target.value = null;
    done.phase.value = "completed";
    await settle();
    expect(done.follow.pill.value).toBeNull();
  });

  it("갈 자리가 아직 그려지지 않았으면 옮기지 않고 따라가기만 켠다", async () => {
    const { follow } = setup({ target: "rs-sec-9", startPaused: true });
    follow.resume();
    await settle();
    expect(follow.following.value).toBe(true);
    expect(follow.pill.value).toBeNull();
  });
});
