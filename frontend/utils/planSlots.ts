// frontend/utils/planSlots.ts
// 탐색 중 절 자리 — 승인 뒤(대기열·탐색·종합 첫 절 전) 본문에 하위질문마다 세우는 보고서 자리의 상태.
// 하위질문 번호와 절 번호는 다르다: 근거가 없는 하위질문은 절이 되지 않는다(synthesizer.py — 종합 대상은 evidence_ids 가
// 있는 하위질문). 그래서 자리는 하위질문 번호로 세우고, 절 번호는 종합 이벤트(절의 subq_idx, 없으면 절 제목 = 하위질문 글)로
// 맞춘다. 화면 상태(view)만 읽는다 — 초안(draftReport·draftSlots)은 건드리지 않는다
import type { ResearchView, StepStatus, SynthView } from "~/types/research";
import type { ResearchPhase } from "~/utils/researchEvents";

export type PlanSlotState = "waiting" | "collecting" | "collected" | "writing" | "empty" | "failed";

export interface PlanSlot {
  // key·자리 id 의 번호 — 하위질문 번호다(절 번호가 아니다)
  subqIdx: number;
  // 하위질문 글
  title: string;
  state: PlanSlotState;
  // 근거 편수(SubqView.adopted) — 근거 수를 모르는 옛 잡은 null
  adopted: number | null;
  // collecting 일 때 지금 회차(회차가 아직 없으면 null), 아니면 null
  round: number | null;
  // 종합 이벤트로 알게 된 절 번호 — 근거 0 이거나 아직 모르면 null
  sectionIdx: number | null;
}

export function slotElementId(subqIdx: number): string {
  return `rs-slot-${subqIdx}`;
}

// 절 제목(하위질문 글)과 계획 하위질문 글을 견주는 꼴 — 조합형·완성형 차이와 공백 차이를 지운다
function sameText(s: string): string {
  return s.normalize("NFC").trim().replace(/\s+/g, " ");
}

// 하위질문 번호 → 절 번호. ① 절 이벤트가 실은 subq_idx(쓰기 시작한 절) ② 남은 절은 절 제목 목록(headings — 첫 절을
// 쓰기 시작할 때 전부 온다)을 계획 하위질문 글과 같은 글로 맞춘다. titles[i] = 하위질문 i 의 글
export function sectionOfSubq(synth: SynthView, titles: readonly string[]): Map<number, number> {
  const out = new Map<number, number>();
  const taken = new Set<number>();
  for (const s of synth.sections) {
    if (s.subqIdx === null || out.has(s.subqIdx) || taken.has(s.idx)) continue;
    out.set(s.subqIdx, s.idx);
    taken.add(s.idx);
  }
  synth.headings.forEach((heading, idx) => {
    if (taken.has(idx)) return;
    const key = sameText(heading);
    if (!key) return;
    const subqIdx = titles.findIndex((t, i) => !out.has(i) && sameText(t) === key);
    if (subqIdx < 0) return;
    out.set(subqIdx, idx);
    taken.add(idx);
  });
  return out;
}

export function planSlots(view: ResearchView): PlanSlot[] {
  const { synth } = view;
  // 종합 시작 = 종합 단계가 열렸다. 대응을 앎 = 절 제목이나 절 이벤트가 하나라도 왔다 — 워커는 종합 단계를 열 때 결과 없는
  // 단계 이벤트를 먼저 보내고 절 제목은 첫 절 이벤트에서야 오므로, 그 사이는 시작했지만 대응을 모른다
  const started = synth.status !== null || synth.headings.length > 0;
  const mapped = synth.headings.length > 0 || synth.sections.length > 0;
  const size = view.subqs.reduce((n, sq) => Math.max(n, sq.idx + 1), 0);
  const titles = Array.from({ length: size }, (_, i) => view.subqs.find((sq) => sq.idx === i)?.title ?? "");
  const sectionOf = sectionOfSubq(synth, titles);
  return view.subqs.map((sq) => {
    const sectionIdx = sectionOf.get(sq.idx) ?? null;
    const writing = sectionIdx !== null && synth.sections.some((s) => s.idx === sectionIdx && s.status === "running");
    return {
      subqIdx: sq.idx,
      title: sq.title,
      state: slotState(sq.status, sq.adopted, sectionIdx, writing, started, mapped),
      adopted: sq.adopted,
      round: sq.status === "running" && sq.rounds.length ? sq.rounds.length : null,
      sectionIdx,
    };
  });
}

// 근거 0(adopted 0)은 절이 되지 않으므로 종합이 시작되면 접는다. 근거 수를 모르는 옛 잡은 대응을 알게 된 뒤 절이 없을 때만
// 접는다. 근거를 모은 자리(adopted > 0)는 대응을 몰라도(제목 맞춤이 빗나가도) 접지 않는다 — 잠깐 '근거 없음'으로 접혔다가
// 다시 펼쳐지지 않게
function slotState(
  status: StepStatus,
  adopted: number | null,
  sectionIdx: number | null,
  writing: boolean,
  started: boolean,
  mapped: boolean,
): PlanSlotState {
  switch (status) {
    case "failed":
      return "failed";
    case "running":
      return "collecting";
    case "pending":
      return "waiting";
    case "done":
      if (writing) return "writing";
      if (started && adopted === 0) return "empty";
      if (mapped && adopted === null && sectionIdx === null) return "empty";
      return "collected";
  }
}

export function planSlotLabel(slot: PlanSlot): string {
  switch (slot.state) {
    case "waiting":
      return "대기";
    case "collecting":
      return slot.round !== null ? `근거 수집 중 · ${slot.round}회차` : "근거 수집 중";
    case "collected":
      // 근거 0편으로 끝난 자리는 성공 표시(✓)를 달지 않는다 — 종합이 시작되면 '근거 없음'으로 접힌다
      if (slot.adopted === null) return "근거 수집 완료";
      return slot.adopted > 0 ? `근거 ${slot.adopted}편 ✓` : "근거 0편";
    case "writing":
      return "이 절을 쓰는 중";
    case "empty":
      return "근거 없음";
    case "failed":
      return "오류";
  }
}

// 직전 상태와 견줘 이번에 근거 수집을 마친 자리(하위질문 번호). 처음 그릴 때(prev 가 null)는 없다 — 다시 연 화면에서 이미
// 모은 자리가 한꺼번에 튀어 오르지 않게(움직임은 실제 이벤트가 올 때만 — synthCard.newlyFinished 와 같은 규칙).
// 근거 0편으로 끝난 자리는 튀어 오르지 않는다(모은 것이 없다)
export function newlyCollected(prev: ReadonlyMap<number, PlanSlotState> | null, slots: readonly PlanSlot[]): number[] {
  if (!prev) return [];
  return slots
    .filter((s) => s.state === "collected" && s.adopted !== 0 && prev.get(s.subqIdx) !== "collected")
    .map((s) => s.subqIdx);
}

// 절 자리를 그리는 단계 — 승인 뒤 대기열·탐색 중, 종합 중이면 첫 절이 완성되기 전(초안이 생기면 초안이 그 자리에 선다)
export function showsPlanSlots(phase: ResearchPhase | null, hasDraft: boolean): boolean {
  return phase === "queued" || phase === "exploring" || (phase === "synthesizing" && !hasDraft);
}
