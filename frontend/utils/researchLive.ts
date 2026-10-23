// frontend/utils/researchLive.ts
// 탐색 중 본문(보고서 자리)에 띄우는 'AI가 지금 하는 일' 화면(ResearchLive)의 순수 로직 — 지금 하는 일 한 줄과 회차마다의 단계.
// 전에는 이 과정이 옆 칸 진행 패널에만 쌓여 본문에는 하위질문 자리만 보였다. 탐색 중에는 과정을 본문에 크게 띄우고, 보고서를 쓰기
// 시작하면 과정(탐색 경로)은 다시 옆 칸으로 간다(사용자 결정 2026-10-14). 화면 상태(view)만 읽는다
import type { RoundView, SubqView } from "~/types/research";
import { excludedLabel, exploreAttemptStart, fromEarlierAttempt, verdictLabel } from "~/utils/researchEvents";

// 지금 도는 하위질문 — 이번 시도의 행만(탐색부터 다시 도는 재시도에서 이전 시도에 남은 running 행은 아니다 — followTarget 과 같다)
export function liveRunning(subqs: readonly SubqView[]): SubqView | null {
  const since = exploreAttemptStart(subqs);
  return subqs.find((s) => s.status === "running" && !fromEarlierAttempt(s, since)) ?? null;
}

// 화면 맨 위 '지금 AI가 하는 일' 한 줄
export function liveNowLine(subqs: readonly SubqView[]): string {
  const running = liveRunning(subqs);
  if (!running) {
    return subqs.some((s) => s.status === "pending") ? "다음 하위질문을 준비하고 있어요" : "탐색을 마무리하고 있어요";
  }
  const head = `하위질문 ${running.idx + 1}/${subqs.length}`;
  const last = running.rounds[running.rounds.length - 1];
  if (!last) return `${head} — 검색어를 정해 논문을 찾고 있어요`;
  if (last.verdict === null) {
    const found = last.foundChunks !== null ? `찾은 대목 ${last.foundChunks}개를` : "찾은 논문을";
    return `${head} — ${found} 질문에 맞는지 스스로 점검하고 있어요`;
  }
  if (last.nextQuery) return `${head} — 근거가 부족해 ‘${last.nextQuery}’(으)로 다시 찾고 있어요`;
  return `${head} — 근거를 확인했어요`;
}

export type LiveStepKind = "search" | "check" | "recheck";

export interface LiveStep {
  key: string;
  kind: LiveStepKind;
  title: string;
  detail: string | null;
  // 판정의 결 — 충분은 ok, 부족·재검색은 warn
  tone: "ok" | "warn" | null;
  // 지금 하는 중(깜빡임)
  pending: boolean;
}

// 한 회차의 단계 — 검색 → 자기점검 → (부족하면) 다시 찾기. live 는 지금 도는 하위질문의 마지막 회차인가(판정 전이면 점검 중 단계를 단다)
export function roundSteps(r: RoundView, live: boolean): LiveStep[] {
  const stats = [
    r.foundChunks !== null ? `대목 ${r.foundChunks}개` : null,
    r.newPapers !== null ? `새 논문 ${r.newPapers}편` : null,
  ].filter((s): s is string => !!s);
  const steps: LiveStep[] = [
    {
      key: `${r.round}-search`,
      kind: "search",
      title: `‘${r.query}’(으)로 찾음`,
      detail: stats.length ? stats.join(" · ") : null,
      tone: null,
      pending: false,
    },
  ];
  if (r.verdict !== null) {
    const detail = [r.note || null, excludedLabel(r.excluded)].filter((s): s is string => !!s).join(" · ");
    steps.push({
      key: `${r.round}-check`,
      kind: "check",
      title: `자기점검 · ${verdictLabel(r.verdict)}`,
      detail: detail || null,
      tone: r.verdict === "sufficient" ? "ok" : r.verdict === "insufficient" ? "warn" : null,
      pending: false,
    });
  } else if (live) {
    steps.push({ key: `${r.round}-check`, kind: "check", title: "자기점검 중", detail: null, tone: null, pending: true });
  }
  if (r.nextQuery) {
    steps.push({
      key: `${r.round}-recheck`,
      kind: "recheck",
      title: `‘${r.nextQuery}’(으)로 다시 찾기`,
      detail: null,
      tone: "warn",
      pending: live && r.verdict !== null,
    });
  }
  return steps;
}

// 끝난 하위질문의 한 줄 요약 — 접어 둔 줄에 쓴다
export function doneSummary(sq: SubqView): string {
  const parts = [sq.adopted !== null ? `근거 ${sq.adopted}편` : null, sq.rounds.length ? `${sq.rounds.length}회차` : null];
  return parts.filter(Boolean).join(" · ") || "완료";
}
