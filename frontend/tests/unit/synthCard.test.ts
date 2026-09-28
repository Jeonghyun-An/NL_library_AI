// frontend/tests/unit/synthCard.test.ts
import { describe, expect, it } from "vitest";
import type { DraftSlot, DraftSlotStatus, SynthEta } from "~/utils/researchDraft";
import { formatClock, formatRemaining } from "~/utils/researchDraft";
import { barFraction, finishedAnnouncement, newlyFinished, slotStateLabel, synthSummary } from "~/utils/synthCard";

function eta(over: Partial<SynthEta> = {}): SynthEta {
  return { done: 0, total: 5, runningIdx: null, runningElapsedMs: null, remainingMs: null, ...over };
}

function slot(over: Partial<DraftSlot> = {}): DraftSlot {
  return { idx: 0, heading: "가", status: "waiting", durationMs: null, startedAt: null, sectionIndex: null, ...over };
}

describe("synthSummary", () => {
  it("절 수를 모르면 준비 중이라고만 쓴다", () => {
    expect(synthSummary(eta({ total: 0 }))).toBe("보고서 작성을 준비하는 중");
  });

  it("끝난 절 수와 남은 시간을 쓴다", () => {
    expect(synthSummary(eta({ done: 2, remainingMs: 90_000 }))).toBe(`2/5 절 완료 · ${formatRemaining(90_000, 2)}`);
  });

  it("첫 절 전에는 남은 시간 대신 첫 절을 쓰는 중이라고 쓴다", () => {
    expect(synthSummary(eta({ runningIdx: 0, runningElapsedMs: 5_000 }))).toBe(`0/5 절 완료 · ${formatRemaining(null, 0)}`);
  });

  it("절마다 걸린 시간이 없는 옛 워커는 남은 시간을 빼고 쓴다", () => {
    expect(synthSummary(eta({ done: 2, remainingMs: null }))).toBe("2/5 절 완료");
  });

  it("모든 절을 썼으면 마무리 중이라고 쓴다", () => {
    expect(synthSummary(eta({ done: 5, remainingMs: 0 }))).toBe("5/5 절 완료 · 보고서를 마무리하는 중");
  });
});

describe("slotStateLabel", () => {
  it("끝난 절은 걸린 시간을, 모르면 완료만 쓴다", () => {
    expect(slotStateLabel(slot({ status: "done", durationMs: 38_000 }), eta())).toBe(`완료 ${formatClock(38_000)}`);
    expect(slotStateLabel(slot({ status: "done" }), eta())).toBe("완료");
  });

  it("쓰는 중인 절은 경과를 쓴다", () => {
    const e = eta({ runningIdx: 2, runningElapsedMs: 12_000 });
    expect(slotStateLabel(slot({ idx: 2, status: "running" }), e)).toBe(`작성 중 ${formatClock(12_000)}`);
    expect(slotStateLabel(slot({ idx: 3, status: "running" }), e)).toBe("작성 중");
  });

  it("실패·대기 절", () => {
    expect(slotStateLabel(slot({ status: "failed" }), eta())).toBe("서술 받지 못함");
    expect(slotStateLabel(slot({ status: "waiting" }), eta())).toBe("대기");
  });
});

describe("barFraction", () => {
  it("절 수를 모르면 0", () => {
    expect(barFraction(eta({ total: 0 }))).toBe(0);
  });

  it("쓰는 중인 절이 없으면 끝난 절의 비율이다", () => {
    expect(barFraction(eta({ done: 2 }))).toBeCloseTo(0.4);
  });

  it("쓰는 중인 절은 평균 대비 경과만큼 채운다", () => {
    // 평균 40초, 대기 2절, 경과 10초 → 남은 시간 40×2 + 30 = 110초
    expect(barFraction(eta({ done: 2, runningIdx: 2, runningElapsedMs: 10_000, remainingMs: 110_000 }))).toBeCloseTo(2.25 / 5);
  });

  it("평균을 넘겨도 쓰는 중인 절은 다 차지 않는다", () => {
    expect(barFraction(eta({ done: 2, runningIdx: 2, runningElapsedMs: 60_000, remainingMs: 80_000 }))).toBeCloseTo(2.9 / 5);
  });

  it("첫 절은 평균이 없어 30초마다 남은 거리의 절반씩 다가간다", () => {
    expect(barFraction(eta({ runningIdx: 0, runningElapsedMs: 30_000 }))).toBeCloseTo(0.45 / 5);
    expect(barFraction(eta({ runningIdx: 0, runningElapsedMs: 0 }))).toBe(0);
  });

  it("다 쓰면 1 이고 넘치지 않는다", () => {
    expect(barFraction(eta({ done: 5 }))).toBe(1);
    expect(barFraction(eta({ done: 7 }))).toBe(1);
  });
});

describe("newlyFinished", () => {
  const prev = new Map<number, DraftSlotStatus>([
    [0, "done"],
    [1, "running"],
    [2, "waiting"],
  ]);

  it("처음 그릴 때는 없다", () => {
    expect(newlyFinished(null, [slot({ idx: 0, status: "done" })])).toEqual([]);
  });

  it("직전에 끝나지 않았던 절 중 이번에 끝난 절", () => {
    const slots = [
      slot({ idx: 0, status: "done" }),
      slot({ idx: 1, status: "done" }),
      slot({ idx: 2, status: "failed" }),
      slot({ idx: 3, status: "running" }),
    ];
    expect(newlyFinished(prev, slots)).toEqual([1, 2]);
  });

  it("직전 목록에 없던 절이 끝난 채로 오면(재접속 snapshot) 끝난 것으로 본다", () => {
    expect(newlyFinished(new Map(), [slot({ idx: 0, status: "done" })])).toEqual([0]);
  });
});

describe("finishedAnnouncement", () => {
  it("끝난 절을 번호·제목으로 한 번에 알린다", () => {
    const slots = [slot({ idx: 0, heading: "가", status: "done" }), slot({ idx: 1, heading: "나", status: "failed" })];
    expect(finishedAnnouncement(slots, [0, 1])).toBe("절 1 작성 완료: 가. 절 2 서술 받지 못함, 논문 목록만 싣습니다: 나");
    expect(finishedAnnouncement(slots, [])).toBe("");
  });
});
