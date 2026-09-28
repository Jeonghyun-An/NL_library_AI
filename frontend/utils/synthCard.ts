// frontend/utils/synthCard.ts
import type { DraftSlot, DraftSlotStatus, SynthEta } from "./researchDraft";
import { formatClock, formatRemaining } from "./researchDraft";

// 쓰는 중인 절이 끝나기 전에 막대가 다 차 보이면 멈춘 것처럼 읽힌다 — 끝날 때까지 이 비율 아래에 둔다
const RUNNING_CAP = 0.9;
// 첫 절은 평균이 없어 예상 소요를 모른다 — 30초마다 남은 거리의 절반씩 다가간다
const FIRST_HALF_LIFE_MS = 30_000;

const FINISHED: readonly DraftSlotStatus[] = ["done", "failed"];

export function synthSummary(eta: SynthEta): string {
  if (eta.total <= 0) return "보고서 작성을 준비하는 중";
  const head = `${Math.min(eta.done, eta.total)}/${eta.total} 절 완료`;
  if (eta.done >= eta.total) return `${head} · 보고서를 마무리하는 중`;
  const remaining = formatRemaining(eta.remainingMs, eta.done);
  return remaining ? `${head} · ${remaining}` : head;
}

export function slotStateLabel(slot: DraftSlot, eta: SynthEta): string {
  switch (slot.status) {
    case "done":
      return slot.durationMs !== null ? `완료 ${formatClock(slot.durationMs)}` : "완료";
    case "running":
      return slot.idx === eta.runningIdx && eta.runningElapsedMs !== null
        ? `작성 중 ${formatClock(eta.runningElapsedMs)}`
        : "작성 중";
    case "failed":
      return "서술 받지 못함";
    case "waiting":
      return "대기";
  }
}

// 막대는 끝난 절 + 쓰는 중인 절의 몫이다. 절 하나가 수십 초라 끝날 때만 늘면 막대가 서 있는 것처럼 보인다.
// 몫 = 경과 ÷ 예상 소요, 예상 소요 = (남은 시간 + 경과) ÷ 남은 절 수. synthEta 의 남은 시간은
// 평균 × 대기 절 + max(0, 평균 − 경과) 라, 경과가 평균보다 짧으면 예상 소요가 정확히 평균이 된다.
export function barFraction(eta: SynthEta): number {
  if (eta.total <= 0) return 0;
  const done = Math.min(Math.max(eta.done, 0), eta.total);
  const left = eta.total - done;
  let part = 0;
  if (left > 0 && eta.runningIdx !== null && eta.runningElapsedMs !== null) {
    const elapsed = Math.max(0, eta.runningElapsedMs);
    if (eta.remainingMs !== null) {
      const expected = (eta.remainingMs + elapsed) / left;
      part = expected > 0 ? Math.min(RUNNING_CAP, elapsed / expected) : RUNNING_CAP;
    } else {
      part = RUNNING_CAP * (1 - 0.5 ** (elapsed / FIRST_HALF_LIFE_MS));
    }
  }
  return Math.min(1, (done + part) / eta.total);
}

// 직전 목록과 비교해 이번에 끝난 절. 처음 그릴 때(prev 가 null)는 없다 — 새로고침한 화면에서
// 이미 끝난 절이 한꺼번에 튀어 오르거나 스크린리더가 몰아 읽지 않게
export function newlyFinished(prev: ReadonlyMap<number, DraftSlotStatus> | null, slots: readonly DraftSlot[]): number[] {
  if (!prev) return [];
  return slots
    .filter((s) => FINISHED.includes(s.status) && !FINISHED.includes(prev.get(s.idx) ?? "waiting"))
    .map((s) => s.idx);
}

export function finishedAnnouncement(slots: readonly DraftSlot[], idxs: readonly number[]): string {
  return idxs
    .map((idx) => slots.find((s) => s.idx === idx))
    .filter((s): s is DraftSlot => s !== undefined)
    .map((s) =>
      s.status === "failed"
        ? `절 ${s.idx + 1} 서술 받지 못함, 논문 목록만 싣습니다: ${s.heading}`
        : `절 ${s.idx + 1} 작성 완료: ${s.heading}`,
    )
    .join(". ");
}
