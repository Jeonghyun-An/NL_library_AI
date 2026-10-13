// frontend/tests/unit/researchStart.test.ts
import { describe, expect, it } from "vitest";
import { DEEP_RESEARCH } from "~/utils/brand";
import {
  NOTICE_CANCEL_ARM_MS,
  noticeCancelLabel,
  noticeCancelPress,
  researchStartState,
  startNotice,
} from "~/utils/researchStart";
import { ID1, ID2, ID3, bookEntry, researchEntry } from "./helpers/fakeHistory";

const ID4 = "44444444-4444-4444-8444-444444444444";
const ID5 = "55555555-5555-4555-8555-555555555555";
const T = (hour: number) => `2026-10-13T${String(hour).padStart(2, "0")}:00:00.000Z`;
const status = (s: string) => ({ research: { status: s, stage: "planned" } });

describe("researchStartState", () => {
  it("끝나지 않은 연구를 진행 중(순서 대기 포함)과 승인 대기로 가르고 각각 가장 최근 것부터 둔다", () => {
    const older = researchEntry(ID1, { createdAt: T(1), ...status("running") });
    const newer = researchEntry(ID2, { createdAt: T(3), ...status("queued") });
    const waiting = researchEntry(ID3, { createdAt: T(2), ...status("awaiting_approval") });
    const done = researchEntry(ID4, { createdAt: T(9), ...status("completed") });
    expect(researchStartState([older, newer, waiting, done, bookEntry(ID5, { createdAt: T(10) })])).toEqual({
      live: [newer, older],
      awaiting: [waiting],
    });
  });

  it("사이드바 배지의 진행 중 상태(created·planning·approved·queued·running)를 모두 진행 중으로 본다", () => {
    for (const s of ["created", "planning", "approved", "queued", "running"]) {
      expect(researchStartState([researchEntry(ID1, status(s))]).live.map((e) => e.id)).toEqual([ID1]);
    }
    for (const s of ["awaiting_approval", "completed", "failed", "canceled"]) {
      expect(researchStartState([researchEntry(ID1, status(s))]).live).toEqual([]);
    }
    // 상태를 모르는 기록(옛 기록·조회 실패)은 어느 쪽도 아니다
    expect(researchStartState([researchEntry(ID1)])).toEqual({ live: [], awaiting: [] });
  });

  it("시각은 updatedAt 이 있으면 그것을 보고, 읽을 수 없는 시각은 가장 오래된 것으로 친다", () => {
    const a = researchEntry(ID1, { createdAt: T(5), updatedAt: T(6), ...status("running") });
    const b = researchEntry(ID2, { createdAt: T(7), ...status("running") });
    const c = researchEntry(ID3, { createdAt: "어제", ...status("running") });
    const d = researchEntry(ID4, { createdAt: T(4), updatedAt: T(9), ...status("running") });
    expect(researchStartState([c, a, b, d]).live.map((e) => e.id)).toEqual([ID4, ID2, ID1, ID3]);
    expect(researchStartState([])).toEqual({ live: [], awaiting: [] });
  });
});

describe("startNotice — DeepResearch 모드 입력창의 한 줄", () => {
  it("진행 중인 연구가 있으면 그 수와 가장 최근 것 — 승인 대기가 함께 있어도 진행 중이 먼저", () => {
    const live = researchEntry(ID1, { createdAt: T(2), ...status("running") });
    const queued = researchEntry(ID2, { createdAt: T(1), ...status("queued") });
    const awaiting = researchEntry(ID3, { createdAt: T(3), ...status("awaiting_approval") });
    expect(startNotice(researchStartState([queued, awaiting, live]))).toEqual({
      text: `진행 중인 ${DEEP_RESEARCH} 2건`,
      jobId: ID1,
      to: { path: `/research/${ID1}` },
    });
  });

  it("승인 대기만 있으면 승인 대기 줄, 끝나지 않은 연구가 없으면 null — [보기]·[취소]는 기록의 잡 id(refId)", () => {
    const awaiting = researchEntry(ID2, { ...status("awaiting_approval"), refId: ID5 });
    expect(startNotice(researchStartState([awaiting]))).toEqual({
      text: `승인 대기 중인 ${DEEP_RESEARCH} 1건`,
      jobId: ID5,
      to: { path: `/research/${ID5}` },
    });
    expect(startNotice(researchStartState([researchEntry(ID1, status("completed"))]))).toBeNull();
  });
});

describe("noticeCancelPress · noticeCancelLabel — [취소]는 한 번 더 눌러 확인한다", () => {
  it("첫 누름은 '정말 취소'로 바꾸기만 하고, 확인은 잠깐 뒤의 두 번째 누름에서만 — 더블클릭 한 번에 넘어가지 않는다", () => {
    expect(noticeCancelPress("idle", 0, 1000)).toBe("arm");
    expect(noticeCancelPress("confirm", 1000, 1000 + NOTICE_CANCEL_ARM_MS - 1)).toBeNull();
    expect(noticeCancelPress("confirm", 1000, 1000 + NOTICE_CANCEL_ARM_MS)).toBe("run");
    // 취소하는 중에는 다시 받지 않는다
    expect(noticeCancelPress("busy", 1000, 99999)).toBeNull();
  });

  it("버튼 글은 취소 → 정말 취소 → 취소하는 중", () => {
    expect((["idle", "confirm", "busy"] as const).map(noticeCancelLabel)).toEqual(["취소", "정말 취소", "취소하는 중"]);
  });
});
