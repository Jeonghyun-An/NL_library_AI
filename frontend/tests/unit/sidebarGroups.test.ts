// frontend/tests/unit/sidebarGroups.test.ts
import { describe, expect, it } from "vitest";
import type { HistoryEntry } from "~/types/history";
import {
  LIVE_STATUSES,
  countLiveResearch,
  groupSidebarHistory,
  isLiveResearch,
} from "~/utils/sidebarGroups";
import { ID1, ID2, ID3, bookEntry, paperEntry, researchEntry } from "./helpers/fakeHistory";

const T = (hour: number) => `2026-09-26T${String(hour).padStart(2, "0")}:00:00.000Z`;
const status = (s: string) => ({ research: { status: s, stage: "" } });
const ids = (list: Array<{ id: string }>) => list.map((e) => e.id);

describe("groupSidebarHistory", () => {
  it("빈 입력은 두 묶음 모두 비어 있다", () => {
    expect(groupSidebarHistory([])).toEqual({ research: [], recent: [] });
  });

  it("딥리서치는 research 로, 도서·논문은 한 목록(recent)으로 섞여 최신순으로 간다", () => {
    const book = bookEntry(ID1, { createdAt: T(1) });
    const paper = paperEntry(ID2, { createdAt: T(3) });
    const research = researchEntry(ID3, { createdAt: T(2) });
    const { research: r, recent } = groupSidebarHistory([book, paper, research]);
    expect(ids(r)).toEqual([ID3]);
    expect(recent.map((x) => x.entry.id)).toEqual([ID2, ID1]);
  });

  it("recent 항목에는 종류 라벨이 붙는다 — 도서는 소장자료, 논문은 논문", () => {
    const { recent } = groupSidebarHistory([bookEntry(ID1, { createdAt: T(1) }), paperEntry(ID2, { createdAt: T(2) })]);
    expect(recent.map((x) => [x.entry.kind, x.label])).toEqual([
      ["paper", "논문"],
      ["book", "소장자료"],
    ]);
  });

  it("시각은 updatedAt 이 있으면 그것을, 없으면 createdAt 을 본다", () => {
    const old = bookEntry(ID1, { createdAt: T(1), updatedAt: T(9) });
    const fresh = paperEntry(ID2, { createdAt: T(5) });
    expect(groupSidebarHistory([fresh, old]).recent.map((x) => x.entry.id)).toEqual([ID1, ID2]);
  });

  it("진행 중·대기 중인 딥리서치가 더 오래돼도 먼저 오고, 같은 부류 안에서는 최신순이다", () => {
    const doneNew = researchEntry(ID1, { createdAt: T(9), ...status("completed") });
    const runningOld = researchEntry(ID2, { createdAt: T(1), ...status("running") });
    const waitingMid = researchEntry(ID3, { createdAt: T(4), ...status("awaiting_approval") });
    const failedMid = researchEntry("44444444-4444-4444-8444-444444444444", { createdAt: T(6), ...status("failed") });
    const { research } = groupSidebarHistory([doneNew, runningOld, failedMid, waitingMid]);
    // 승인 대기(T4) → 진행 중(T1) → 그 밖에 최신순: 완료(T9) → 실패(T6)
    expect(ids(research)).toEqual([ID3, ID2, ID1, failedMid.id]);
  });

  it("시각이 같으면 원래 순서를 지킨다", () => {
    const a = bookEntry(ID1, { createdAt: T(2) });
    const b = paperEntry(ID2, { createdAt: T(2) });
    const c = bookEntry(ID3, { createdAt: T(2) });
    expect(groupSidebarHistory([a, b, c]).recent.map((x) => x.entry.id)).toEqual([ID1, ID2, ID3]);
    expect(groupSidebarHistory([c, b, a]).recent.map((x) => x.entry.id)).toEqual([ID3, ID2, ID1]);
    const r1 = researchEntry(ID1, { createdAt: T(2), ...status("running") });
    const r2 = researchEntry(ID2, { createdAt: T(2), ...status("running") });
    expect(ids(groupSidebarHistory([r1, r2]).research)).toEqual([ID1, ID2]);
    expect(ids(groupSidebarHistory([r2, r1]).research)).toEqual([ID2, ID1]);
  });

  it("모르는 종류는 어느 묶음에도 넣지 않는다", () => {
    const alien = { id: ID3, kind: "video", title: "?", createdAt: T(9), params: {} } as unknown as HistoryEntry;
    const { research, recent } = groupSidebarHistory([alien, bookEntry(ID1)]);
    expect(research).toEqual([]);
    expect(ids(recent.map((x) => x.entry))).toEqual([ID1]);
  });

  it("읽을 수 없는 시각은 가장 오래된 것으로 친다", () => {
    const bad = bookEntry(ID1, { createdAt: "" });
    const ok = paperEntry(ID2, { createdAt: T(1) });
    expect(groupSidebarHistory([bad, ok]).recent.map((x) => x.entry.id)).toEqual([ID2, ID1]);
  });

  it("입력 배열을 바꾸지 않는다", () => {
    const input = [bookEntry(ID1, { createdAt: T(1) }), bookEntry(ID2, { createdAt: T(2) })];
    const copy = input.slice();
    groupSidebarHistory(input);
    expect(input).toEqual(copy);
  });
});

describe("진행 중 판정", () => {
  it("LIVE_STATUSES 는 폴링 대상이라 승인 대기를 뺀다", () => {
    expect(LIVE_STATUSES.has("running")).toBe(true);
    expect(LIVE_STATUSES.has("awaiting_approval")).toBe(false);
    expect(LIVE_STATUSES.has("completed")).toBe(false);
  });

  it("isLiveResearch: 딥리서치만, 상태가 진행 중일 때만 참이다", () => {
    expect(isLiveResearch(researchEntry(ID1, status("queued")))).toBe(true);
    expect(isLiveResearch(researchEntry(ID1, status("completed")))).toBe(false);
    expect(isLiveResearch(researchEntry(ID1))).toBe(false);
    expect(isLiveResearch(bookEntry(ID1))).toBe(false);
  });

  it("countLiveResearch 는 진행 중인 딥리서치 수를 센다", () => {
    const list: HistoryEntry[] = [
      researchEntry(ID1, status("running")),
      researchEntry(ID2, status("planning")),
      researchEntry(ID3, status("completed")),
      bookEntry("55555555-5555-4555-8555-555555555555"),
    ];
    expect(countLiveResearch(list)).toBe(2);
  });
});
