// frontend/utils/researchEvents.ts
import type {
  CountersPayload,
  CountersView,
  CritiqueEvent,
  ExcludedPaper,
  ExcludedPaperView,
  HighlightView,
  ReportEvidence,
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
  SynthEvent,
  SynthSectionResult,
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

// 실패·취소한 잡이 멈춘 곳. before = 탐색을 시작하기 전(계획 단계·승인 대기·대기열),
// subq = 그 하위질문을 돌다가(started) 또는 시작하기 전에(!started) — error 는 이번 시도에서
// 그 하위질문이 남긴 오류다. synth = 탐색을 마친 뒤(보고서 작성 단계)
export type StopPoint =
  | { kind: "before" }
  | { kind: "subq"; idx: number; started: boolean; error: string | null }
  | { kind: "synth" };

type OpenedSubq = SubqView & { seq: number };

export const TERMINAL_STATUSES: readonly ResearchStatus[] = ["completed", "failed", "canceled"];

const EMPTY_COUNTERS: CountersView = { papersReviewed: null, evidenceAdopted: null, rechecks: null, excluded: null };
const EMPTY_SYNTH: SynthView = {
  seq: null, status: null, total: 0, sections: [], headings: [], evidence: {}, retiredSeq: null,
};
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

// 자기점검이 하위질문의 핵심과 무관하다고 보고 뺀 근거 수 — 타임라인 회차 줄과 문서 부록이 같은
// 문구를 쓴다. 뺀 것이 없거나 무관 제외 전 잡(null)이면 적지 않는다
export function excludedLabel(n: number | null): string | null {
  return n ? `무관 ${n}편 제외` : null;
}

// 무관 제외를 끈 잡(exclude_off_topic=0)은 빼지 않고 무관하다고 본 수만 남긴다 — 켠 잡의 "제외"와
// 헷갈리지 않게 빼지 않았음을 문구에 밝힌다. 켠 잡(0)·그 전 잡(null)은 적지 않는다
export function flaggedLabel(n: number | null): string | null {
  return n ? `무관 의심 ${n}편(제외 안 함)` : null;
}

// 카운터에 제외 칸을 그릴지. 제외 수를 모르는 옛 잡은 그리지 않는다. 새 잡은 API 가 잡을 만들 때 기본 파라미터를
// 합쳐 저장해 params 에 exclude_off_topic 이 있으므로 첫 counters 이벤트 전에도 그린다 — 수를 받고서야 그리면
// 첫 검색이 끝날 때 칸이 셋에서 넷으로 늘며 카운터 줄이 흔들린다
export function showsExcludedCounter(view: Pick<ResearchView, "counters" | "params">): boolean {
  return view.counters.excluded !== null || "exclude_off_topic" in view.params;
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

// 취소한 잡의 종합 단계가 아직 열려 있다. 취소는 API 가 곧바로 잡을 끝내고 스트림도 닫지만, 워커는
// LLM 을 부르기 직전에만 멈춤을 보므로 쓰던 절을 마저 쓰고(그 미리보기도 저장하고) 나서야 단계를
// 닫는다. 이 상태로 받은 화면은 단계가 닫힐 때까지 GET 으로 다시 맞춰야 멈춘 초안·[초안 저장]이 다시
// 연 화면과 같아진다. 실패는 워커가 단계를 먼저 닫고 잡을 끝내므로 해당하지 않는다.
export function synthClosePending(view: ResearchView): boolean {
  return view.status === "canceled" && view.synth.status === "running";
}

// 끝났다고 알려졌는데 내용을 받지 못한 절을 저장본(GET)으로 다시 맞출지. 화면을 열거나 다시 붙는 순간
// 스트림은 스냅샷을 읽은 뒤에야 구독을 붙이므로, 그 사이에 나간 synth(done) 이벤트는 다시 오지 않고
// 뒤따르는 step 이벤트는 절 내용을 싣지 않는다(서버는 상태·단계가 바뀔 때만 스냅샷을 다시 보낸다).
// 부족분을 가리키는 열쇠(종합 단계 seq·절 번호)를 돌려주되, 이미 그 열쇠로 다시 읽었으면(recovered)
// null — 같은 부족분으로 GET 을 되풀이하지 않는다. 절 내용을 싣는 워커(절 제목 목록을 보낸다)가 종합
// 단계를 쓰는 동안만 본다 — 옛 워커의 절은 원래 내용이 없고, 닫힌 단계는 종료 뒤 GET 이 맞춘다.
export function sectionGapToRecover(view: ResearchView, recovered: string | null): string | null {
  const { seq, status, headings, sections } = view.synth;
  if (status !== "running" || !headings.length) return null;
  const missing = sections.filter((s) => s.status !== "running" && !s.section).map((s) => s.idx);
  if (!missing.length) return null;
  const key = `${seq}:${missing.join(",")}`;
  return key === recovered ? null : key;
}

// 워커는 하위질문을 idx 순서로 돌고, 하나가 오류로 끝나도 다음 하위질문과 종합으로 넘어간다
// (부분 실패는 전체 실패가 아니다). 그래서 failed 하위질문을 곧 멈춘 곳으로 보면, 종합에서
// 실패·취소한 잡이 앞선 부분 실패를 짚어 본문의 실패 사유와 어긋난다 — 뒤 단계부터 본다.
// 탐색부터 다시 도는 재시도는 idx 0 부터 새 행을 쌓고, 이번 시도가 아직 닿지 않은 하위질문에는
// 이전 시도의 행(done·failed 와 그 오류)이 남는다 — 이번 시도에서 연 행만 보고, 순서도 seq 로 잡는다.
export function stopPoint(view: ResearchView): StopPoint | null {
  if (view.status !== "failed" && view.status !== "canceled") return null;
  if (view.synth.status !== null || view.stage === "explored") return { kind: "synth" };
  const since = attemptStart(view.steps);
  // 행 없이 라이브 search 이벤트로만 도는 하위질문(seq 없음)도 이번 시도의 것이다
  const running = view.subqs.find((s) => s.status === "running" && (s.seq === null || s.seq >= since));
  if (running) return { kind: "subq", idx: running.idx, started: true, error: null };
  const opened = view.subqs.filter((s): s is OpenedSubq => s.seq !== null && s.seq >= since);
  const last = opened.reduce<OpenedSubq | undefined>((a, s) => (a && a.seq > s.seq ? a : s), undefined);
  if (!last) return { kind: "before" };
  // 실패한 잡의 마지막으로 돈 하위질문이 오류면 거기서 멈췄다 — 시간 상한·회수기·예기치 못한
  // 예외는 도는 단계를 failed 로 닫고, 전멸도 마지막 하위질문 뒤에 끝난다. 취소는 워커가
  // 하위질문 경계에서만 확인해(돌던 하위질문은 끝까지 돈다) 그 오류와 무관하다.
  if (view.status === "failed" && last.status === "failed") {
    return { kind: "subq", idx: last.idx, started: true, error: last.error };
  }
  // 뒤 하위질문의 상태는 보지 않는다 — 이전 시도의 행이면 done·failed 로 남아 있다
  const next = view.subqs.find((s) => s.idx > last.idx);
  return next ? { kind: "subq", idx: next.idx, started: false, error: null } : { kind: "synth" };
}

// 탐색은 시도마다 idx 0 부터 다시 돈다 — 하위질문 0 의 search 행 중 가장 늦은 것이 이번 시도의 시작이다
function attemptStart(steps: ResearchStepRow[]): number {
  return latestBySubq(steps, "search").get(0)?.seq ?? Number.NEGATIVE_INFINITY;
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
    // queued 는 재시도로 다시 큐에 든 상태다(models/research.py) — 워커가 집기 전이라 남은 종합
    // 단계는 모두 이전 시도의 것이다
    synth: job.status === "queued" ? retiredSynth(steps) : { ...EMPTY_SYNTH },
    source: "none",
  });
  return view.status === "running" ? { ...view, highlight: latestHighlight(view.subqs) } : view;
}

// 종료 이벤트 뒤·409 뒤·재연결 때 GET 으로 다시 맞출 때 쓴다. 카운터는 보고서 stats(최종
// 확정값)가 있으면 그것을, 없으면 라이브 값과 저장본을 reconcileCounters 로 합친다 — 취소·
// 실패는 대개 저장본이 뒤처진 구간에 오고, 스트림도 닫혀 뒤에 바로잡히지 않는다.
export function refreshView(prev: ResearchView | null, job: ResearchJob): ResearchView {
  const fresh = initialResearchView(job);
  if (!prev || prev.jobId !== fresh.jobId) return fresh;
  const merged = rebuild({ ...fresh, subqs: prev.subqs, synth: carriedSynth(prev, fresh) });
  const counters = fresh.report?.stats
    ? fresh.counters
    : reconcileCounters(prev.counters, prev.steps, fresh.counters, fresh.steps);
  const highlight = merged.status === "running" ? (prev.highlight ?? latestHighlight(merged.subqs)) : null;
  return { ...merged, counters, highlight };
}

export function withPlan(view: ResearchView, plan: string[]): ResearchView {
  return rebuild({ ...view, plan });
}

// 승인 응답(HTTP)을 화면에 반영한다. 승인 대기는 종료 상태가 아니라 승인하는 동안 스트림이 열려
// 있고, 서버는 approved 를 알린 뒤 큐에 넣고 나서야 응답한다 — 워커가 곧바로 집어 낸 running
// (또는 재접속 snapshot)이 응답보다 먼저 올 수 있다. 그 뒤에 응답의 approved 로 덮으면 화면이
// 대기열로 되돌아가고, step·search 는 status 를 바꾸지 않으니 다음 status(탐색 끝)까지 복구되지
// 않는다. 그래서 status 는 아직 승인 대기일 때만 바꾸고, 계획은 언제나 반영한다.
export function applyApproval(view: ResearchView, status: ResearchStatus, plan: string[] | null | undefined): ResearchView {
  const planned = plan?.length ? withPlan(view, plan) : view;
  if (planned.status !== "awaiting_approval") return planned;
  return applyResearchEvent(planned, { kind: "status", status, stage: planned.stage });
}

export function applyResearchEvent(view: ResearchView, event: ResearchEvent): ResearchView {
  switch (event.kind) {
    case "snapshot":
      return applySnapshot(view, event);
    case "status": {
      const next: ResearchView = {
        ...view,
        status: event.status,
        stage: event.stage ?? view.stage,
        lastError: isTerminalStatus(event.status) ? view.lastError : null,
      };
      return isRetry(view.status, event.status) ? { ...next, synth: retiredSynth(view.steps) } : next;
    }
    case "step":
      return applyStep(view, event);
    case "search":
      return applySearch(view, event);
    case "critique":
      return applyCritique(view, event);
    case "counters":
      return { ...view, counters: countersFromPayload(event) };
    case "synth":
      return { ...view, synth: applySynth(view.synth, event) };
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
    if (event.job.counters) {
      const stored = countersFromPayload(event.job.counters);
      // 완료 잡의 스냅샷 카운터는 보고서 stats(확정값)다
      next.counters = event.job.status === "completed"
        ? stored
        : reconcileCounters(view.counters, view.steps, stored, event.steps ?? []);
    }
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
  // 진행 저장·단계 닫기에 실린 카운터는 저장한 그 순간의 값이다. 이벤트는 순서대로 오고
  // 하위질문은 하나씩 도므로 마지막 counters 이벤트와 같다 — 재접속 스냅샷이 뒤처진 값을
  // 줬어도 여기서 바로잡힌다.
  const counters = event.result?.counters ? countersFromPayload(event.result.counters) : view.counters;
  return rebuild({ ...view, steps, plan, counters });
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
      excluded: event.excluded ?? null,
      // 뒤따르는 진행 저장 step 이벤트의 회차 기록도 같은 값을 싣지만, 저장이 실패하면 오지 않는다 —
      // 점검 이벤트의 값으로 바로 채운다. 목록을 보내지 않는 옛 워커는 빈 목록·null
      excludedPapers: (event.excluded_papers ?? []).map(toExcludedPaperView),
      flagged: event.flagged ?? null,
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

// 다듬은 절·근거는 절이 끝날 때 synth 이벤트로 한 번만 온다 — 알리는 step 이벤트는 그것을 뺀
// 가벼운 result 를 싣는다(spec §14-2). 보강 전 워커의 이벤트는 idx·total·status 뿐이라 나머지
// 칸은 null 로 남고, 화면은 "보고서 작성 중 2/5" 로 되돌아간다.
function applySynth(synth: SynthView, event: SynthEvent): SynthView {
  const entry = toSectionView({
    idx: event.section_idx,
    status: event.status,
    subq_idx: event.subq_idx,
    heading: event.heading,
    started_at: event.started_at,
    duration_ms: event.duration_ms,
    section: event.section,
  });
  return {
    ...synth,
    status: synth.status ?? "running",
    total: Math.max(synth.total, event.total),
    sections: mergeSections(synth.sections, [entry]),
    headings: event.headings?.length ? event.headings : synth.headings,
    evidence: event.evidence ? mergeEvidence(synth.evidence, event.evidence) : synth.evidence,
  };
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

// 단계 result 는 진행 저장본(snapshot·GET — 절 내용·근거 포함)과 알리는 step 이벤트(가볍다 —
// 절 내용·근거 없음) 두 길로 온다. 어느 쪽이든 같은 모양으로 합치고 없는 칸이 받은 칸을 지우지
// 않게 한다. 재시도로 새 종합 단계가 열리면(seq 가 바뀜) 이전 시도의 절은 버린다.
function synthFrom(view: ResearchView): SynthView {
  const step = latestOf(view.steps, "synthesize");
  const retired = view.synth.retiredSeq;
  if (!step || (retired !== null && step.seq <= retired)) return view.synth;
  const r: StepResult = step.result ?? {};
  const listed: SynthSectionView[] = Array.isArray(r.sections) ? r.sections.map(toSectionView) : [];
  const total = r.sections_total ?? (typeof r.sections === "number" ? r.sections : listed.length);
  const sameAttempt = view.synth.seq === null || view.synth.seq === step.seq;
  const prior = sameAttempt ? view.synth : EMPTY_SYNTH;
  return {
    seq: step.seq,
    status: step.status,
    total: Math.max(total, prior.total),
    sections: mergeSections(listed, prior.sections),
    headings: r.headings?.length ? r.headings : prior.headings,
    // 근거가 없는 값(가벼운 step 이벤트)이면 받은 객체를 그대로 둔다 — applySynth 와 같은 규칙
    evidence: r.evidence ? mergeEvidence(r.evidence, prior.evidence) : prior.evidence,
    retiredSeq: retired,
  };
}

// 끝난 잡이 다시 진행으로 바뀌었다 — 재시도다. 스트림은 종료 상태에서 닫히므로 화면이 이것을 보는
// 길은 재시도 응답과 GET 재동기화(409 뒤·다시 불러오기)뿐이다
function isRetry(prev: ResearchStatus, next: ResearchStatus): boolean {
  return isTerminalStatus(prev) && !isTerminalStatus(next);
}

// 재시도로 물러난 시도의 종합. 워커는 running 을 알리고 스냅샷을 되살린 뒤에야 새 종합 단계를 연다 —
// 그 사이 이전 시도의 닫힌 단계를 읽으면 멈춘 초안·남은 시간이 '작성 중'으로 잠깐 되살아난다. 그래서
// 화면을 비우고, 그 단계의 seq 를 기억해 새 종합 단계(더 큰 seq)가 열릴 때까지 읽지 않는다(synthFrom).
// "실패 단계면 숨긴다"로 가르면 실패로 닫히는 길(단계 failed → 잡 failed)의 멈춘 초안까지 깜빡인다.
function retiredSynth(steps: ResearchStepRow[]): SynthView {
  return { ...EMPTY_SYNTH, retiredSeq: latestOf(steps, "synthesize")?.seq ?? null };
}

// GET 으로 다시 맞출 때 이어 갈 종합 화면
function carriedSynth(prev: ResearchView, fresh: ResearchView): SynthView {
  // queued 로 읽은 잡은 initialResearchView 가 새로 읽은 단계까지 모두 물렸다
  if (fresh.status === "queued") return fresh.synth;
  // 끝난 화면이 도는 잡을 받았다 — 새로 읽은 단계에는 새 시도의 종합 단계가 있을 수 있어 화면이 알던 단계만 물린다
  return isRetry(prev.status, fresh.status) ? retiredSynth(prev.steps) : prev.synth;
}

// 회차 기록이 없는 옛 잡에서 재검색은 판정이 부족일 때만 일어났다(무관 제외 전이다) — 마지막 전 회차는 모두 부족이다
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
    excluded: null,
    excludedPapers: [],
    flagged: null,
  }));
}

// 뺀 논문의 서지 — 회차 기록(타임라인)과 보고서 trail(제외한 논문 섹션·문서 부록)이 같은 모양으로 받는다
export function toExcludedPaperView(p: ExcludedPaper): ExcludedPaperView {
  return {
    cntsId: p.cnts_id,
    title: p.title?.trim() ?? "",
    personalAuthor: p.personal_author ?? null,
    pubDate: p.pub_date ?? null,
  };
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
    excluded: r.excluded ?? null,
    excludedPapers: (r.excluded_papers ?? []).map(toExcludedPaperView),
    flagged: r.flagged ?? null,
  };
}

function blankRound(round: number): RoundView {
  return {
    round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null,
  };
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
    out.set(s.idx, cur ? mergeSection(cur, s) : s);
  }
  return [...out.values()].sort((a, b) => a.idx - b.idx);
}

// 상태는 더 나아간 쪽, 나머지 칸은 들어온 값이 있을 때만 바꾼다 — 가벼운 step 이벤트·뒤처진
// snapshot 이 이미 받은 절 내용·걸린 시간을 지우지 않게
function mergeSection(cur: SynthSectionView, s: SynthSectionView): SynthSectionView {
  return {
    idx: cur.idx,
    status: SECTION_RANK[s.status] >= SECTION_RANK[cur.status] ? s.status : cur.status,
    subqIdx: s.subqIdx ?? cur.subqIdx,
    heading: s.heading ?? cur.heading,
    startedAt: s.startedAt ?? cur.startedAt,
    durationMs: s.durationMs ?? cur.durationMs,
    section: s.section ?? cur.section,
  };
}

function toSectionView(s: SynthSectionResult): SynthSectionView {
  return {
    idx: s.idx,
    status: s.status,
    subqIdx: s.subq_idx ?? null,
    heading: s.heading ?? null,
    startedAt: s.started_at ?? null,
    durationMs: s.duration_ms ?? null,
    section: s.section ?? null,
  };
}

// 같은 근거가 여러 절에 나오면 절마다 자기 절이 쓴 대목만 온다(section_evidence) — 대목을
// chunk_id 로 합집합하고, 보고서의 evidence(_serialize_evidence)처럼 점수순으로 둔다
export function mergeEvidence(
  a: Record<string, ReportEvidence>,
  b: Record<string, ReportEvidence>,
): Record<string, ReportEvidence> {
  const out: Record<string, ReportEvidence> = { ...a };
  for (const [eid, ev] of Object.entries(b)) {
    const cur = out[eid];
    if (!cur) {
      out[eid] = ev;
      continue;
    }
    const known = new Set(cur.chunks.map((c) => c.chunk_id));
    const chunks = [...cur.chunks, ...ev.chunks.filter((c) => !known.has(c.chunk_id))]
      .sort((x, y) => y.score - x.score);
    out[eid] = { ...cur, chunks };
  }
  return out;
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
  return {
    papersReviewed: p.papers_reviewed,
    evidenceAdopted: p.evidence_adopted,
    rechecks: p.rechecks,
    excluded: p.excluded ?? null,
  };
}

// 서버 스냅샷(api/research.py _live_counters)과 같은 순서로 고른다 — 갈리면 끝난 뒤 다시 연
// 실패·취소 잡의 카운터가 라이브로 볼 때와 다르게(빈칸으로) 나온다.
function countersFromJob(report: ResearchReport | null, steps: ResearchStepRow[]): CountersView {
  if (report?.stats) return countersFromPayload(report.stats);
  const counters = countersStep(steps)?.result?.counters;
  return counters ? countersFromPayload(counters) : countersFromLegacyReport(report);
}

// 서버가 저장본 카운터를 꺼내는 단계 — 카운터를 실은 단계 중 seq 가 가장 큰 행
function countersStep(steps: ResearchStepRow[]): ResearchStepRow | undefined {
  let best: ResearchStepRow | undefined;
  for (const s of steps) if (s.result?.counters && (!best || s.seq > best.seq)) best = s;
  return best;
}

// 라이브 카운터와 저장본(스냅샷·GET) 카운터를 합친다. 한 시도 안에서 검토한 논문·재검색·제외 수는
// 줄지 않는다(research_stats 의 seen_cnts·queries·회차 기록은 늘기만 한다). 저장본은 자기점검(LLM)이
// 끝나야 쓰여 점검을 기다리는 동안 검색 직후 받은 counters 이벤트보다 한 회차 뒤처지고,
// 반대로 스트림이 끊긴 사이에는 저장본이 앞선다 — 그래서 필드별로 큰 값을 남긴다.
// 다만 화면이 모르는 뒤 단계에서 나온 저장본은 그대로 쓴다. 탐색부터 다시 도는 재시도는
// 카운터를 0 부터 새로 세므로, 큰 값을 남기면 이전 시도의 숫자가 버티고 선다.
// 저장본을 쓴 단계가 닫혔고 그 뒤로 열린 탐색 단계가 없어도 저장본을 그대로 쓴다 — 단계를 닫을 때 쓴
// 값이라 그 단계의 어떤 counters 이벤트보다 새롭다. 채택한 근거는 자기점검이 무관 근거를 풀에서 지우면
// 주는데, 탐색이 끝난 뒤의 종합 단계 이벤트는 카운터를 싣지 않아 큰 값을 남기면 바로잡히지 않는다.
// 도는 단계 안에서는 여전히 필드별 큰 값이다 — 그 동안 지운 뒤의 저장본이 오면 지우기 전의 수가
// 다음 counters·step 이벤트까지 남는다.
function reconcileCounters(
  live: CountersView,
  liveSteps: ResearchStepRow[],
  stored: CountersView,
  storedSteps: ResearchStepRow[],
): CountersView {
  const source = countersStep(storedSteps);
  if (source && liveSteps.every((s) => s.seq < source.seq)) return stored;
  if (source && source.status !== "running"
    && ![...liveSteps, ...storedSteps].some((s) => s.kind === "search" && s.seq > source.seq)) return stored;
  return {
    papersReviewed: larger(live.papersReviewed, stored.papersReviewed),
    evidenceAdopted: larger(live.evidenceAdopted, stored.evidenceAdopted),
    rechecks: larger(live.rechecks, stored.rechecks),
    excluded: larger(live.excluded, stored.excluded),
  };
}

function larger(a: number | null, b: number | null): number | null {
  if (a === null) return b;
  if (b === null) return a;
  return Math.max(a, b);
}

// 보강 전 보고서(stats 없음) — 검토한 논문 수는 어디에도 남아 있지 않다
function countersFromLegacyReport(report: ResearchReport | null): CountersView {
  if (!report) return { ...EMPTY_COUNTERS };
  return {
    papersReviewed: null,
    evidenceAdopted: Object.keys(report.evidence ?? {}).length,
    rechecks: report.trail.reduce((n, t) => n + Math.max(0, t.queries.length - 1), 0),
    excluded: null,
  };
}

function bySeq(a: ResearchStepRow, b: ResearchStepRow): number {
  return a.seq - b.seq;
}
