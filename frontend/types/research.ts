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
  // 자기점검이 무관하다고 보고 이 회차에 뺀 근거 수 — 무관 제외 전 잡의 회차에는 없다
  excluded?: number | null;
  // 이 회차에 뺀 논문의 서지 — 풀에서 지운 뒤에도 무엇을 뺐는지 남는다. 목록을 기록하기 전 잡에는 없다
  excluded_papers?: ExcludedPaper[] | null;
  // 무관 제외를 끈 잡(exclude_off_topic=0)이 빼지 않고 무관하다고만 본 수. 그 하위질문에서 처음 본 논문만
  // 센다(빼지 않은 논문은 다음 회차 목록에 남아 또 가리켜진다). 켠 잡은 0, 그 전 잡에는 없다
  flagged?: number | null;
  // 회차 끝 이 하위질문의 채택 근거(순위순) — 근거 장부(06b)가 rounds 만으로 다시 그린다. 기록하기 전 잡에는 없다
  adopted_papers?: AdoptedPaper[] | null;
}

// 회차 끝 채택 근거 한 편(runner._adopted_papers). rank 는 1부터. 그 회차에 새로 채택된 논문(new)만
// 서지를 싣는다 — 나머지는 앞 회차의 같은 cnts_id 에 서지가 있다
export interface AdoptedPaper {
  cnts_id: string;
  rank: number;
  title?: string | null;
  personal_author?: string | null;
  pub_date?: string | null;
  new?: boolean;
}

// 자기점검이 무관하다고 보고 뺀 논문의 서지 요약(회차 기록·보고서 trail)
export interface ExcludedPaper {
  cnts_id: string;
  title?: string | null;
  personal_author?: string | null;
  pub_date?: string | null;
}

// idx·status 뒤의 칸은 절 미리보기(spec §14)를 싣는 워커만 남긴다 — 옛 결과에는 없다. 워커는 모르는
// 칸을 null 로 싣는다(subq_idx·heading 포함) — 화면은 toSectionView 의 ?? 로 받는다.
// section 은 진행 저장본(DB)에만 있고, 알리는 step 이벤트·완료로 닫힌 단계에서는 빠진다
export interface SynthSectionResult {
  idx: number;
  status: SynthSectionStatus;
  subq_idx?: number | null;
  heading?: string | null;
  started_at?: string | null;
  duration_ms?: number | null;
  section?: ReportSection;
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
  // 종합 단계의 절 제목(절 순서)과 끝난 절들이 인용한 근거 합집합 — 보강 전 잡에는 없고,
  // evidence 는 알리는 step 이벤트·완료로 닫힌 단계에서도 빠진다
  headings?: string[];
  evidence?: Record<string, ReportEvidence>;
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
  // 하위질문에서 무관하다고 뺀 근거 총수 — 무관 제외 전 보고서에는 없다
  excluded?: number | null;
  // 하위질문에서 뺀 논문 전체(회차 순·중복 없음) — 목록을 기록하기 전 보고서에는 없다
  excluded_papers?: ExcludedPaper[] | null;
}

export interface CountersPayload {
  papers_reviewed: number;
  evidence_adopted: number;
  rechecks: number;
  // 모든 하위질문에서 뺀 논문 수(두 하위질문이 같은 논문을 빼면 두 번 센다) — 무관 제외 전 잡에는 없다
  excluded?: number;
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
// 대기 순번(api/research.py _queue_info) — ahead 는 앞에 있는 잡 수(도는 잡 포함), eta_sec 는 최근 완료 잡의
// 걸린 시간 중앙값으로 어림한 초(완료 잡이 없으면 null). 대기 중(approved·queued)인 잡에만 온다
export interface QueueInfo {
  ahead: number;
  eta_sec: number | null;
}

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
  // 대기 중이 아니면 null, 순번을 싣기 전 서버에는 키가 없다
  queue?: QueueInfo | null;
}

export interface ResearchCreateResponse {
  job_id: string;
  status: "created";
}

export interface ResearchApproveResponse {
  job_id: string;
  status: "approved";
  plan: string[] | null;
  // 승인 직후의 대기 순번 — 첫 하트비트를 기다리지 않게 응답에 싣는다. 싣기 전 서버에는 키가 없다
  queue?: QueueInfo | null;
}

export interface ResearchRetryResponse {
  job_id: string;
  status: "queued";
  stage: ResearchStage;
  queue?: QueueInfo | null;
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
    // 대기 중일 때만 싣는다
    queue?: QueueInfo | null;
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
  // 이번 회차에 무관하다고 뺀 근거 수 — 무관 제외 전 워커는 보내지 않는다
  excluded?: number | null;
  // 이번 회차에 뺀 논문의 서지와 무관 제외를 끈 잡이 무관하다고만 본 수 — 회차 기록(SearchRoundResult)과
  // 같은 값이다. 점검 직후 진행 저장이 실패해도 타임라인이 목록을 펼칠 수 있게 이벤트에도 싣는다
  excluded_papers?: ExcludedPaper[] | null;
  flagged?: number | null;
  // 회차 끝 채택 근거 — 회차 기록의 adopted_papers 와 같은 값이다. 보내지 않는 옛 워커는 빈 목록으로 받는다
  adopted_papers?: AdoptedPaper[] | null;
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
  // 보강 전 워커는 위 셋만 보낸다. started_at 은 running 에, duration_ms·section·evidence 는
  // done·failed 에만 온다 — evidence 는 그 절이 인용한 근거·대목만이다
  subq_idx?: number;
  heading?: string;
  headings?: string[];
  started_at?: string;
  duration_ms?: number;
  section?: ReportSection;
  evidence?: Record<string, ReportEvidence>;
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

// 스트림 하트비트가 대기 중인 잡의 순번을 다시 세어 바뀌었을 때만 보낸다
export interface QueueEvent {
  kind: "queue";
  ahead: number;
  eta_sec: number | null;
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
  | CanceledEvent
  | QueueEvent;

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
  excluded: number | null;
  // 뺀 논문 목록이 있는 회차만 타임라인에서 펼칠 수 있다 — 목록을 기록하기 전 회차는 빈 목록
  excludedPapers: ExcludedPaperView[];
  flagged: number | null;
  // 회차 끝 채택 근거(순위순) — 점검 전 회차·기록하기 전 잡은 빈 목록
  adoptedPapers: AdoptedPaperView[];
}

export interface AdoptedPaperView {
  cntsId: string;
  rank: number;
  // 그 회차에 새로 채택된 논문(isNew)만 서지가 있고, 나머지는 null — 앞 회차의 같은 논문에서 찾는다
  title: string | null;
  personalAuthor: string | null;
  pubDate: string | null;
  isNew: boolean;
}

export interface ExcludedPaperView {
  cntsId: string;
  // 제목이 없으면 빈 문자열
  title: string;
  personalAuthor: string | null;
  pubDate: string | null;
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
  // 제외 수를 모르는 잡(무관 제외 전)은 null — 화면은 제외 칸을 그리지 않는다
  excluded: number | null;
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
  subqIdx: number | null;
  heading: string | null;
  startedAt: string | null;
  durationMs: number | null;
  // 최종본과 같은 코드(finalize_section)로 다듬은 절 — 끝난 절에만 있다
  section: ReportSection | null;
}

export interface SynthView {
  seq: number | null;
  status: StepStatus | null;
  total: number;
  sections: SynthSectionView[];
  // 절 순서의 제목 — 아직 쓰기 시작하지 않은 절도 이름을 보여 줄 수 있다
  headings: string[];
  // 끝난 절들이 인용한 근거 합집합 — 초안의 인용칩·내보내기가 읽는다
  evidence: Record<string, ReportEvidence>;
  // 재시도로 물러난 이전 시도의 마지막 종합 단계 seq — 새 종합 단계가 열릴 때까지 그 이하의 단계는 읽지 않는다
  retiredSeq: number | null;
}

export interface QueueView {
  ahead: number;
  etaSec: number | null;
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
  // 대기 순번 — 대기 중(approved·queued)이고 서버가 순번을 실었을 때만 있다
  queue: QueueView | null;
}

// 원문 뷰어 머리의 "인용 대목 n/N" 한 칸. page 는 pdf.js 쪽 번호(1부터), 쪽 정보가 없으면 null
export interface PdfPassage {
  page: number | null;
  label: string;
}

export interface OpenPdfPayload {
  cntsId: string;
  title: string;
  page?: number;
  passages?: PdfPassage[];
}
