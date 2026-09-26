// frontend/utils/researchEvents.ts
import type {
  CountersPayload,
  CountersView,
  CritiqueEvent,
  HighlightView,
  ResearchEvent,
  ResearchJob,
  ResearchReport,
  ResearchStatus,
  ResearchStepRow,
  ResearchView,
  RoundSource,
  RoundView,
  SearchEvent,
  SearchRoundResult,
  SnapshotEvent,
  StepEvent,
  StepKind,
  StepResult,
  StepStatus,
  SubqView,
  SynthSectionStatus,
  SynthSectionView,
  SynthView,
  TrailItem,
  Verdict,
} from "../types/research";

export type ResearchPhase =
  | "planning"
  | "awaiting"
  | "queued"
  | "exploring"
  | "synthesizing"
  | "completed"
  | "failed"
  | "canceled";

export const TERMINAL_STATUSES: readonly ResearchStatus[] = ["completed", "failed", "canceled"];

const EMPTY_COUNTERS: CountersView = { papersReviewed: null, evidenceAdopted: null, rechecks: null };
const EMPTY_SYNTH: SynthView = { seq: null, status: null, total: 0, sections: [] };
// 끊겼다 다시 받은 snapshot 이 라이브로 받은 절 상태를 되돌리지 않게, 더 나아간 쪽을 남긴다
const SECTION_RANK: Record<SynthSectionStatus, number> = { running: 1, done: 2, failed: 2 };
const SOURCE_ORDER: readonly RoundSource[] = ["rounds", "trail", "queries"];

const PHASE_LABEL: Record<ResearchPhase, string> = {
  planning: "계획 수립 중",
  awaiting: "승인 대기",
  queued: "대기열",
  exploring: "탐색 중",
  synthesizing: "보고서 작성 중",
  completed: "완료",
  failed: "실패",
  canceled: "취소됨",
};

const VERDICT_LABEL: Record<Verdict, string> = {
  pending: "점검 중",
  sufficient: "근거 충분",
  insufficient: "근거 부족",
};

export function isTerminalStatus(status: ResearchStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function isTerminalEvent(event: { kind: string }): boolean {
  return event.kind === "done" || event.kind === "failed" || event.kind === "canceled";
}

export function researchPhase(view: ResearchView): ResearchPhase {
  switch (view.status) {
    case "created":
    case "planning":
      return "planning";
    case "awaiting_approval":
      return "awaiting";
    case "approved":
    case "queued":
      return "queued";
    case "running":
      // stage=explored 로 재시도한 잡은 종합 단계 행이 생기기 전부터 종합 중이다
      return view.stage === "explored" || view.synth.status === "running" ? "synthesizing" : "exploring";
    default:
      return view.status;
  }
}

export function phaseLabel(phase: ResearchPhase): string {
  return PHASE_LABEL[phase];
}

export function verdictLabel(verdict: Verdict): string {
  return VERDICT_LABEL[verdict];
}

export function subqStatusLabel(sq: SubqView): string {
  switch (sq.status) {
    case "pending":
      return "대기";
    case "running":
      return sq.rounds.length ? `탐색 중 · ${sq.rounds.length}회차` : "탐색 중";
    case "done":
      return sq.adopted !== null ? `완료 · 근거 ${sq.adopted}편` : "완료";
    case "failed":
      return "오류";
  }
}

export function synthProgress(view: ResearchView): { current: number; total: number } {
  const { total, sections, status } = view.synth;
  if (!total) return { current: 0, total: 0 };
  const finished = status === "done" && !sections.length
    ? total
    : sections.filter((s) => s.status !== "running").length;
  const running = sections.some((s) => s.status === "running") ? 1 : 0;
  return { current: Math.min(total, Math.max(1, finished + running)), total };
}

export function initialResearchView(job: ResearchJob): ResearchView {
  const steps = [...(job.steps ?? [])].sort(bySeq);
  const view = rebuild({
    jobId: job.job_id,
    question: job.question,
    status: job.status,
    stage: job.stage,
    plan: job.plan?.length ? job.plan : planFromSteps(steps),
    params: job.params ?? {},
    report: job.report ?? null,
    lastError: job.last_error ?? null,
    createdAt: job.created_at ?? null,
    startedAt: job.started_at ?? null,
    finishedAt: job.finished_at ?? null,
    steps,
    subqs: [],
    counters: countersFromJob(job.report ?? null, steps),
    highlight: null,
    synth: { ...EMPTY_SYNTH },
    source: "none",
  });
  return view.status === "running" ? { ...view, highlight: latestHighlight(view.subqs) } : view;
}

// 종료 이벤트 뒤·409 뒤 GET 으로 다시 맞출 때 쓴다. GET 에 저장된 카운터가 아직 없으면
// (첫 회차가 저장되기 전·보강 전 잡) 스트림으로 먼저 받은 값을 잃지 않게 라이브 값을 지킨다.
export function refreshView(prev: ResearchView | null, job: ResearchJob): ResearchView {
  const fresh = initialResearchView(job);
  if (!prev || prev.jobId !== fresh.jobId) return fresh;
  const merged = rebuild({ ...fresh, subqs: prev.subqs, synth: prev.synth });
  const counters = fresh.counters.papersReviewed === null && prev.counters.papersReviewed !== null
    ? prev.counters
    : fresh.counters;
  const highlight = merged.status === "running" ? (prev.highlight ?? latestHighlight(merged.subqs)) : null;
  return { ...merged, counters, highlight };
}

export function withPlan(view: ResearchView, plan: string[]): ResearchView {
  return rebuild({ ...view, plan });
}

export function applyResearchEvent(view: ResearchView, event: ResearchEvent): ResearchView {
  switch (event.kind) {
    case "snapshot":
      return applySnapshot(view, event);
    case "status":
      return {
        ...view,
        status: event.status,
        stage: event.stage ?? view.stage,
        lastError: isTerminalStatus(event.status) ? view.lastError : null,
      };
    case "step":
      return applyStep(view, event);
    case "search":
      return applySearch(view, event);
    case "critique":
      return applyCritique(view, event);
    case "counters":
      return { ...view, counters: countersFromPayload(event) };
    case "synth":
      return {
        ...view,
        synth: {
          ...view.synth,
          status: view.synth.status ?? "running",
          total: Math.max(view.synth.total, event.total),
          sections: mergeSections(view.synth.sections, [{ idx: event.section_idx, status: event.status }]),
        },
      };
    case "done":
      return { ...view, status: "completed", highlight: null };
    case "failed":
      return { ...view, status: "failed", lastError: event.error ?? view.lastError, highlight: null };
    case "canceled":
      return { ...view, status: "canceled", highlight: null };
    default:
      return view;
  }
}

function applySnapshot(view: ResearchView, event: SnapshotEvent): ResearchView {
  const next: ResearchView = { ...view, steps: withKnownResults(view.steps, event.steps ?? []) };
  if (event.job) {
    next.status = event.job.status;
    next.stage = event.job.stage;
    if (event.job.plan?.length) next.plan = event.job.plan;
    if (event.job.counters) next.counters = countersFromPayload(event.job.counters);
  }
  if (!next.plan.length) next.plan = planFromSteps(next.steps);
  const rebuilt = rebuild(next);
  if (rebuilt.highlight || rebuilt.status !== "running") return rebuilt;
  return { ...rebuilt, highlight: latestHighlight(rebuilt.subqs) };
}

function applyStep(view: ResearchView, event: StepEvent): ResearchView {
  const prev = view.steps.find((s) => s.seq === event.seq);
  const row: ResearchStepRow = {
    seq: event.seq,
    kind: event.step_kind,
    subq_idx: event.subq_idx ?? null,
    title: event.title,
    detail: event.detail ?? prev?.detail ?? null,
    status: event.status,
    result: event.result ?? prev?.result ?? {},
  };
  const steps = [...view.steps.filter((s) => s.seq !== event.seq), row].sort(bySeq);
  const plan = view.plan.length ? view.plan : planFromSteps(steps);
  return rebuild({ ...view, steps, plan });
}

function applySearch(view: ResearchView, event: SearchEvent): ResearchView {
  return updateSubq(view, event.subq_idx, (sq) => {
    const round = event.round ?? (lastRound(sq.rounds) ?? 0) + 1;
    const existing = sq.rounds.find((r) => r.round === round);
    const entry: RoundView = {
      ...(existing ?? blankRound(round)),
      query: event.query,
      foundChunks: event.found,
      newPapers: event.new_papers ?? existing?.newPapers ?? null,
    };
    return { ...sq, status: "running", rounds: upsertRound(sq.rounds, entry) };
  });
}

function applyCritique(view: ResearchView, event: CritiqueEvent): ResearchView {
  const current = view.subqs.find((s) => s.idx === event.subq_idx);
  const round = event.round ?? lastRound(current?.rounds ?? []) ?? 1;
  const next = updateSubq(view, event.subq_idx, (sq) => {
    const existing = sq.rounds.find((r) => r.round === round);
    const entry: RoundView = {
      ...(existing ?? blankRound(round)),
      verdict: event.verdict,
      note: event.note,
      nextQuery: event.next_query ?? null,
    };
    return {
      ...sq,
      rounds: upsertRound(sq.rounds, entry),
      verdict: event.verdict,
      note: event.note,
      adopted: event.adopted,
      parseFailed: event.parse_failed,
    };
  });
  const highlight: HighlightView | null = event.will_recheck && event.next_query
    ? { subqIdx: event.subq_idx, round, note: event.note, nextQuery: event.next_query }
    : next.highlight;
  return { ...next, highlight };
}

function rebuild(view: ResearchView): ResearchView {
  const searchSteps = latestBySubq(view.steps, "search");
  const prior = new Map(view.subqs.map((s) => [s.idx, s]));
  const trail = view.report?.trail ?? [];
  const titles = view.plan.length ? view.plan : trail.map((t) => t.subquestion);
  const idxs = new Set<number>(titles.map((_, i) => i));
  for (const idx of searchSteps.keys()) idxs.add(idx);
  // 계획을 모를 때만 라이브로 받은 하위질문을 남긴다 — 알면 계획에서 지운 항목이 되살아난다
  if (!titles.length) for (const idx of prior.keys()) idxs.add(idx);

  const sources = new Set<RoundSource>();
  const subqs = [...idxs]
    .sort((a, b) => a - b)
    .map((idx) => {
      const built = buildSubq(idx, titles[idx], searchSteps.get(idx), prior.get(idx), trail[idx]);
      sources.add(built.source);
      return built.subq;
    });
  return {
    ...view,
    subqs,
    source: SOURCE_ORDER.find((s) => sources.has(s)) ?? "none",
    synth: synthFrom(view),
  };
}

function buildSubq(
  idx: number,
  title: string | undefined,
  step: ResearchStepRow | undefined,
  old: SubqView | undefined,
  trail: TrailItem | undefined,
): { subq: SubqView; source: RoundSource } {
  // 같은 하위질문의 새 시도(재시도)는 seq 가 커진다 — 이전 시도의 라이브 회차를 섞지 않는다
  const carry = old && (!step || old.seq === null || old.seq === step.seq) ? old : undefined;
  const r: StepResult = step?.result ?? {};
  let rounds: RoundView[] = [];
  let source: RoundSource = "none";
  if (Array.isArray(r.rounds)) {
    rounds = r.rounds.map(toRoundView);
    source = "rounds";
  } else if (trail?.queries.length) {
    rounds = roundsFromQueries(trail.queries, trail.verdict, trail.note);
    source = "trail";
  } else if (r.queries?.length) {
    rounds = roundsFromQueries(r.queries, r.verdict ?? null, r.note ?? "");
    source = "queries";
  }
  rounds = mergeRounds(rounds, carry?.rounds ?? []);
  if (source === "none" && rounds.length) source = "rounds";

  const fallbackStatus: StepStatus = trail ? (trail.failed ? "failed" : "done") : "pending";
  return {
    source,
    subq: {
      idx,
      title: title ?? step?.title ?? carry?.title ?? "",
      seq: step?.seq ?? carry?.seq ?? null,
      status: step?.status ?? carry?.status ?? fallbackStatus,
      rounds,
      verdict: r.verdict ?? carry?.verdict ?? trail?.verdict ?? null,
      note: r.note ?? carry?.note ?? trail?.note ?? "",
      adopted: r.adopted ?? carry?.adopted ?? trail?.evidence_count ?? null,
      parseFailed: r.parse_failed ?? carry?.parseFailed ?? trail?.parse_failed ?? false,
      error: r.error ?? null,
    },
  };
}

function synthFrom(view: ResearchView): SynthView {
  const step = latestOf(view.steps, "synthesize");
  if (!step) return view.synth;
  const r: StepResult = step.result ?? {};
  const listed: SynthSectionView[] = Array.isArray(r.sections)
    ? r.sections.map((s) => ({ idx: s.idx, status: s.status }))
    : [];
  const total = r.sections_total ?? (typeof r.sections === "number" ? r.sections : listed.length);
  const sameAttempt = view.synth.seq === null || view.synth.seq === step.seq;
  return {
    seq: step.seq,
    status: step.status,
    total: Math.max(total, sameAttempt ? view.synth.total : 0),
    sections: mergeSections(listed, sameAttempt ? view.synth.sections : []),
  };
}

// 재검색은 판정이 부족일 때만 일어난다(critic.should_recheck) — 마지막 전 회차는 모두 부족이다
function roundsFromQueries(queries: string[], verdict: Verdict | null, note: string): RoundView[] {
  const last = queries.length - 1;
  return queries.map((query, i) => ({
    round: i + 1,
    query,
    foundChunks: null,
    newPapers: null,
    verdict: i < last ? "insufficient" : verdict,
    note: i < last ? "" : note,
    nextQuery: i < last ? (queries[i + 1] ?? null) : null,
  }));
}

function toRoundView(r: SearchRoundResult): RoundView {
  return {
    round: r.round,
    query: r.query,
    foundChunks: r.found_chunks ?? null,
    newPapers: r.new_papers ?? null,
    verdict: r.verdict ?? null,
    note: r.note ?? "",
    nextQuery: r.next_query ?? null,
  };
}

function blankRound(round: number): RoundView {
  return { round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null };
}

function mergeRounds(base: RoundView[], live: RoundView[]): RoundView[] {
  const known = new Set(base.map((r) => r.round));
  return [...base, ...live.filter((r) => !known.has(r.round))].sort((a, b) => a.round - b.round);
}

function upsertRound(rounds: RoundView[], entry: RoundView): RoundView[] {
  return [...rounds.filter((r) => r.round !== entry.round), entry].sort((a, b) => a.round - b.round);
}

function lastRound(rounds: RoundView[]): number | null {
  return rounds.length ? Math.max(...rounds.map((r) => r.round)) : null;
}

function mergeSections(base: SynthSectionView[], extra: SynthSectionView[]): SynthSectionView[] {
  const out = new Map(base.map((s) => [s.idx, s]));
  for (const s of extra) {
    const cur = out.get(s.idx);
    if (!cur || SECTION_RANK[s.status] >= SECTION_RANK[cur.status]) out.set(s.idx, s);
  }
  return [...out.values()].sort((a, b) => a.idx - b.idx);
}

function updateSubq(view: ResearchView, idx: number, fn: (sq: SubqView) => SubqView): ResearchView {
  const list = view.subqs.some((s) => s.idx === idx)
    ? view.subqs
    : [...view.subqs, emptySubq(idx, view.plan[idx] ?? "")].sort((a, b) => a.idx - b.idx);
  return { ...view, subqs: list.map((s) => (s.idx === idx ? fn(s) : s)) };
}

function emptySubq(idx: number, title: string): SubqView {
  return {
    idx, title, seq: null, status: "pending", rounds: [],
    verdict: null, note: "", adopted: null, parseFailed: false, error: null,
  };
}

function latestHighlight(subqs: SubqView[]): HighlightView | null {
  for (const sq of [...subqs].reverse()) {
    if (sq.status !== "running") continue;
    const r = [...sq.rounds].reverse().find((x) => x.nextQuery);
    if (r?.nextQuery) return { subqIdx: sq.idx, round: r.round, note: r.note, nextQuery: r.nextQuery };
  }
  return null;
}

function withKnownResults(prev: ResearchStepRow[], incoming: ResearchStepRow[]): ResearchStepRow[] {
  const bySeqMap = new Map(prev.map((s) => [s.seq, s]));
  return incoming
    .map((s) => (s.result === undefined ? { ...s, result: bySeqMap.get(s.seq)?.result ?? {} } : s))
    .sort(bySeq);
}

function planFromSteps(steps: ResearchStepRow[]): string[] {
  return latestOf(steps, "plan")?.result?.subquestions ?? [];
}

function latestOf(steps: ResearchStepRow[], kind: StepKind): ResearchStepRow | undefined {
  let best: ResearchStepRow | undefined;
  for (const s of steps) if (s.kind === kind && (!best || s.seq > best.seq)) best = s;
  return best;
}

// 재시도가 끼면 같은 (kind, subq_idx) 행이 여럿 남는다 — seq 가 가장 큰 행이 현재 시도다
function latestBySubq(steps: ResearchStepRow[], kind: StepKind): Map<number, ResearchStepRow> {
  const out = new Map<number, ResearchStepRow>();
  for (const s of steps) {
    if (s.kind !== kind || s.subq_idx === null) continue;
    const cur = out.get(s.subq_idx);
    if (!cur || s.seq > cur.seq) out.set(s.subq_idx, s);
  }
  return out;
}

function countersFromPayload(p: CountersPayload): CountersView {
  return { papersReviewed: p.papers_reviewed, evidenceAdopted: p.evidence_adopted, rechecks: p.rechecks };
}

// 서버 스냅샷(api/research.py _live_counters)과 같은 순서로 고른다 — 갈리면 끝난 뒤 다시 연
// 실패·취소 잡의 카운터가 라이브로 볼 때와 다르게(빈칸으로) 나온다. steps 는 seq 오름차순이다.
function countersFromJob(report: ResearchReport | null, steps: ResearchStepRow[]): CountersView {
  if (report?.stats) return countersFromPayload(report.stats);
  for (let i = steps.length - 1; i >= 0; i--) {
    const counters = steps[i]?.result?.counters;
    if (counters) return countersFromPayload(counters);
  }
  return countersFromLegacyReport(report);
}

// 보강 전 보고서(stats 없음) — 검토한 논문 수는 어디에도 남아 있지 않다
function countersFromLegacyReport(report: ResearchReport | null): CountersView {
  if (!report) return { ...EMPTY_COUNTERS };
  return {
    papersReviewed: null,
    evidenceAdopted: Object.keys(report.evidence ?? {}).length,
    rechecks: report.trail.reduce((n, t) => n + Math.max(0, t.queries.length - 1), 0),
  };
}

function bySeq(a: ResearchStepRow, b: ResearchStepRow): number {
  return a.seq - b.seq;
}
