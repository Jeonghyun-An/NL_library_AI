// 서버 모양은 app/api/research.py · services/research/synthesizer.assemble_report 가 정본이다.
// 필드를 바꿀 때는 그쪽과 함께 바꾼다 — 한쪽만 바꾸면 화면 분기가 조용히 빗나간다.

export type ResearchStatus =
  | "created"
  | "planning"
  | "awaiting_approval"
  | "approved"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "canceled";
export type ResearchStage = "created" | "planned" | "explored" | "synthesized";
export type StepKind = "plan" | "search" | "synthesize";
export type StepStatus = "pending" | "running" | "done" | "failed";
export type Verdict = "pending" | "sufficient" | "insufficient";
export type SynthSectionStatus = "running" | "done" | "failed";
export type ResearchParams = Record<string, number>;

// ── research_steps.result ──────────────────────────────────
export interface SearchRoundResult {
  round: number;
  query: string;
  found_chunks?: number | null;
  new_papers?: number | null;
  verdict?: Verdict | null;
  note?: string | null;
  next_query?: string | null;
}

export interface SynthSectionResult {
  idx: number;
  status: SynthSectionStatus;
}

export interface StepResult {
  subquestions?: string[];
  queries?: string[];
  adopted?: number;
  verdict?: Verdict;
  note?: string;
  parse_failed?: boolean;
  capped?: number;
  // 보강 전 잡에는 없다 — 화면은 report.trail 이나 queries 로 대신 그린다
  rounds?: SearchRoundResult[];
  // 보강 전 잡은 절 수(number), 보강 후는 절별 상태 목록이다
  sections?: number | SynthSectionResult[];
  sections_total?: number;
  // search 단계가 회차 끝·종료 때 남기는 잡 전체 카운터 — 보강 전 잡에는 없다
  counters?: CountersPayload;
  error?: string;
}

export interface ResearchStepRow {
  seq: number;
  kind: StepKind;
  subq_idx: number | null;
  title: string;
  detail?: string | null;
  status: StepStatus;
  // 보강 전 서버의 snapshot 행에는 result 가 없다
  result?: StepResult;
}

// ── 보고서 JSON ────────────────────────────────────────────
export interface ReportRange {
  from: string | null;
  to: string | null;
  n_papers: number;
}

export interface EvidenceMeta {
  title?: string | null;
  personal_author?: string | null;
  series_title?: string | null;
  vol_issue?: string | null;
  pub_date?: string | null;
  kci_citations?: number | null;
  grade?: string | null;
}

export interface ReportChunk {
  chunk_id: string;
  text: string;
  page_start: number;
  page_end: number;
  score: number;
}

export interface ReportEvidence {
  cnts_id: string;
  meta: EvidenceMeta;
  chunks: ReportChunk[];
}

export interface ReportPaper {
  cnts_id: string;
  summary: string;
  evidence: string[];
}

export interface ReportFuture {
  text: string;
  evidence: string[];
}

export interface ReportSection {
  heading: string;
  intro: string;
  papers: ReportPaper[];
  future: ReportFuture[];
  evidence_chunks: Record<string, string[]>;
  chunk_scores: Record<string, number>;
}

export interface TrailItem {
  subquestion: string;
  queries: string[];
  evidence_count: number;
  verdict: Verdict;
  note: string;
  parse_failed: boolean;
  failed: boolean;
  capped: number;
}

export interface CountersPayload {
  papers_reviewed: number;
  evidence_adopted: number;
  rechecks: number;
}

export interface ResearchReport {
  question: string;
  range: Partial<ReportRange> | null;
  sections: ReportSection[];
  evidence: Record<string, ReportEvidence>;
  trail: TrailItem[];
  limitations: string[];
  stats?: CountersPayload;
}

// ── API 응답 ───────────────────────────────────────────────
export interface ResearchJob {
  job_id: string;
  question: string;
  status: ResearchStatus;
  stage: ResearchStage;
  plan: string[] | null;
  report: ResearchReport | null;
  last_error: string | null;
  steps: ResearchStepRow[];
  params?: ResearchParams;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ResearchCreateResponse {
  job_id: string;
  status: "created";
}

export interface ResearchApproveResponse {
  job_id: string;
  status: "approved";
  plan: string[] | null;
}

export interface ResearchRetryResponse {
  job_id: string;
  status: "queued";
  stage: ResearchStage;
}

export interface ResearchCancelResponse {
  job_id: string;
  status: "canceled";
}

// ── SSE 이벤트 (data: 한 줄 JSON, kind 로 분기) ────────────
export interface SnapshotEvent {
  kind: "snapshot";
  steps: ResearchStepRow[];
  job?: {
    status: ResearchStatus;
    stage: ResearchStage;
    plan: string[] | null;
    counters?: CountersPayload;
  };
}

export interface StatusEvent {
  kind: "status";
  status: ResearchStatus;
  stage: ResearchStage;
}

export interface StepEvent {
  kind: "step";
  seq: number;
  step_kind: StepKind;
  subq_idx: number | null;
  title: string;
  detail?: string | null;
  status: StepStatus;
  result?: StepResult;
}

export interface SearchEvent {
  kind: "search";
  subq_idx: number;
  query: string;
  found: number;
  round?: number;
  new_papers?: number;
}

export interface CritiqueEvent {
  kind: "critique";
  subq_idx: number;
  verdict: Verdict;
  note: string;
  adopted: number;
  parse_failed: boolean;
  capped: number;
  round?: number;
  next_query?: string | null;
  will_recheck?: boolean;
}

export interface CountersEvent extends CountersPayload {
  kind: "counters";
}

export interface SynthEvent {
  kind: "synth";
  section_idx: number;
  total: number;
  status: SynthSectionStatus;
}

export interface DoneEvent {
  kind: "done";
  status: "completed";
}

export interface FailedEvent {
  kind: "failed";
  status: "failed";
  error?: string;
}

export interface CanceledEvent {
  kind: "canceled";
  status: "canceled";
}

export type ResearchEvent =
  | SnapshotEvent
  | StatusEvent
  | StepEvent
  | SearchEvent
  | CritiqueEvent
  | CountersEvent
  | SynthEvent
  | DoneEvent
  | FailedEvent
  | CanceledEvent;

// ── 화면 상태 ─────────────────────────────────────────────
export type RoundSource = "rounds" | "trail" | "queries" | "none";

export interface RoundView {
  round: number;
  query: string;
  foundChunks: number | null;
  newPapers: number | null;
  verdict: Verdict | null;
  note: string;
  nextQuery: string | null;
}

export interface SubqView {
  idx: number;
  title: string;
  seq: number | null;
  status: StepStatus;
  rounds: RoundView[];
  verdict: Verdict | null;
  note: string;
  adopted: number | null;
  parseFailed: boolean;
  error: string | null;
}

export interface CountersView {
  papersReviewed: number | null;
  evidenceAdopted: number | null;
  rechecks: number | null;
}

export interface HighlightView {
  subqIdx: number;
  round: number;
  note: string;
  nextQuery: string;
}

export interface SynthSectionView {
  idx: number;
  status: SynthSectionStatus;
}

export interface SynthView {
  seq: number | null;
  status: StepStatus | null;
  total: number;
  sections: SynthSectionView[];
}

export interface ResearchView {
  jobId: string;
  question: string;
  status: ResearchStatus;
  stage: ResearchStage;
  plan: string[];
  params: ResearchParams;
  report: ResearchReport | null;
  lastError: string | null;
  createdAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  steps: ResearchStepRow[];
  subqs: SubqView[];
  counters: CountersView;
  highlight: HighlightView | null;
  synth: SynthView;
  source: RoundSource;
}

export interface OpenPdfPayload {
  cntsId: string;
  title: string;
  page?: number;
}
