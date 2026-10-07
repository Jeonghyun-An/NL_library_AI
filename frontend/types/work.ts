// frontend/types/work.ts
// 연구 어시스턴트(이어간 연구) — 서버 모양의 정본은 app/api/research_work.py·research_topics.py·
// research_reading.py·research_proposal.py 와 services/research_work/*_views.py 다. 서버가 주는 snake_case 를
// 그대로 받는다(types/research.ts 와 같은 관례). 화면 상태(WorkState)만 화면 쪽 이름이다

export type WorkPhase = "topics" | "reading" | "proposal" | "done";
// 주소 ?s= 로 보는 단계 — phase 는 도달한 단계, step 은 지금 보는 단계다(phase done 은 계획서 화면)
export type WorkStep = "topics" | "reading" | "proposal";
export type GenKind = "concepts" | "topic_card" | "refine" | "facet" | "outline" | "section" | "paragraph";
export type GenStatus = "queued" | "running" | "done" | "failed" | "canceled";

// 소장 코퍼스 범위(research_works.corpus_snapshot) — at 은 잡이 끝난 시각
export interface Corpus {
  n_papers: number;
  from: string | null;
  to: string | null;
  at?: string | null;
}

// 사이드바 요약의 재료 — 06a 에 이어간 연구는 빈 객체일 수 있다
export interface WorkProgress {
  topics: number;
  reading: number;
  sections: number;
  sections_total: number;
}

// position 은 queued 일 때만 값이 있다(내 앞의 queued + running 수). eta_sec·others_ahead 는 06b 서버부터
export interface WorkGeneration {
  id: number;
  kind: GenKind;
  target: string | null;
  status: GenStatus;
  model: string | null;
  error: string | null;
  position: number | null;
  eta_sec?: number | null;
  others_ahead?: boolean;
}

export interface WorkView {
  id: string;
  phase: WorkPhase;
  concepts: string[];
  memo: string | null;
  is_example: boolean;
  progress: Partial<WorkProgress>;
  topic_id?: number | null;
  corpus?: Corpus | null;
  generations: WorkGeneration[];
}

export interface PaperMeta {
  title: string;
  personal_author: string | null;
  pub_date: string | null;
  series_title: string | null;
}

// [F#] 수치 — 코드가 센 값이다. 모델은 숫자를 쓰지 않고 이 번호만 쓴다
export interface Figure {
  id: string;
  label: string;
  value: string;
}

export interface TopicSeed {
  key: string;
  kind: "future" | "insufficient";
  section_idx: number | null;
  subq_idx: number | null;
  heading: string;
  text: string;
  papers: string[];
  adopted: number | null;
}

export interface TopicCard {
  title: string;
  question: string;
  evidence: string[];
  figure_sentence: string | null;
  figures: Figure[];
  latest_year: number | null;
  edited: boolean;
  checks: { numbers: string[]; softened: number; recovered: number };
  gen_id: number | null;
}

export type TopicState = "candidate" | "picked" | "insufficient" | "folded";

export interface TopicItem {
  id: number;
  slot: number | null;
  origin: "report_seed" | "grid_seed" | "other" | "refine" | "user";
  state: TopicState;
  parent_id: number | null;
  seed: TopicSeed | null;
  card: TopicCard | null;
  generation: { id: number; status: GenStatus } | null;
  created_at: string;
}

export interface TopicsView {
  picked_id: number | null;
  seeds_left: number;
  corpus: Corpus | null;
  papers: Record<string, PaperMeta>;
  items: TopicItem[];
}

export type ReadingState = "candidate" | "in" | "out";

export interface PathChunk {
  chunk_id: string;
  page_start: number | null;
  page_end: number | null;
  score: number | null;
  text: string;
}

export interface ReadingSubqPath {
  idx: number;
  subquestion: string;
  rank: number | null;
  verdict: string | null;
  first_round: number | null;
  chunks: PathChunk[];
}

export interface ReadingPath {
  subqs: ReadingSubqPath[];
  revived: { subq_idx: number; subquestion: string; round: number | null; note: string } | null;
  user: boolean;
}

export interface ReadingItem {
  cnts_id: string;
  state: ReadingState;
  origin: "evidence" | "revived" | "broaden" | "related" | "user";
  note: string | null;
  group_label: string | null;
  position: number | null;
  meta: PaperMeta;
  path: ReadingPath;
}

export interface ExcludedCandidate {
  cnts_id: string;
  title: string;
  personal_author: string | null;
  pub_date: string | null;
  subq_idx: number;
  subquestion: string;
  round: number | null;
  note: string;
}

export interface ReadingFunnel {
  reviewed: number | null;
  adopted: number | null;
  candidates: number;
  picked: number;
}

export interface ReadingView {
  topic_id: number | null;
  subquestions: string[];
  funnel: ReadingFunnel;
  items: ReadingItem[];
  excluded: ExcludedCandidate[];
  // 목차를 만든 뒤 고른 주제가 바뀌었다 — 목차가 없으면 false
  stale?: boolean;
}

export interface OutlineGroup {
  key: string;
  name: string;
  hint: string;
  papers: string[];
}

export interface Outline {
  topic: { id: number; title: string; question: string };
  basis: "concept" | "subq";
  groups: OutlineGroup[];
  questions: string[];
  question: string | null;
  method: string;
  state: "draft" | "approved";
  gen_id: number | null;
  approved_at: string | null;
  // 목차를 만들 때의 핵심 개념
  concepts?: string[];
}

export type ParaState = "proposed" | "accepted" | "edited" | "authored";

export interface ParagraphChecks {
  dropped: number;
  dropped_f: number;
  unmarked: number;
  numbers: string[];
  softened: number;
}

export interface Paragraph {
  id: string;
  text: string;
  state: ParaState;
  cites: string[];
  checks: ParagraphChecks;
  gen_id: number | null;
}

export interface ProposalSection {
  key: string;
  gen_id: number;
  evidence: Record<string, string>;
  figures: Figure[];
  basis: { topic_id: number | null; papers: string[] };
  note: string | null;
  paragraphs: Paragraph[];
  model: string | null;
  updated_at: string;
}

// 쓰는 중인 절의 입력 — 스트리밍 글의 [E#]·[F#] 를 칩으로 그리는 재료
export interface SectionDraft {
  gen_id: number;
  evidence: Record<string, string>;
  figures: Figure[];
}

export interface DisclosureStep {
  kind: GenKind;
  target: string | null;
  model: string | null;
  finished_at: string | null;
  attempts: { model: string; outcome: string }[];
}

export interface ProposalView {
  version: number;
  outline: Outline | null;
  sections: Record<string, ProposalSection>;
  drafts: Record<string, SectionDraft>;
  papers: Record<string, PaperMeta>;
  references: Record<string, string>;
  corpus: Corpus | null;
  stale: { outline: boolean; sections: Record<string, boolean> };
  disclosure: { steps: DisclosureStep[] };
  // 고른 주제의 출처(공개 부록용) — 주제가 없으면 null
  topic_source?: { origin: TopicItem["origin"]; edited: boolean } | null;
}

// ── 요청 본문 ──────────────────────────────────────────────
export interface WorkPatch {
  concepts?: string[];
  memo?: string | null;
  phase?: WorkPhase;
}

export interface TopicCreate {
  title: string;
  question: string;
}

export interface TopicPatch {
  title?: string;
  question?: string;
}

export interface ReadingPut {
  state?: ReadingState;
  note?: string | null;
  group_label?: string | null;
  position?: number | null;
}

export interface OutlinePut {
  groups: { key: string; name: string; papers: string[] }[];
  question: string;
  method: string;
  approve: boolean;
}

export interface SectionPut {
  paragraphs: { id: string | null; text: string; state: ParaState }[];
}

// ── SSE 이벤트 (GET /api/research/{id}/work/stream, data: 한 줄 JSON, kind 로 분기) ──
export interface WorkSnapshotEvent {
  kind: "snapshot";
  work: WorkView;
}

// 생성 종류는 gen_kind 다 — 이벤트 종류(kind)와 겹치지 않게 서버가 이름을 갈랐다
export interface WorkGenerationEvent {
  kind: "generation";
  gen_id: number;
  gen_kind: GenKind;
  target: string | null;
  status: GenStatus;
  model: string | null;
  result: Record<string, unknown> | null;
}

export interface WorkPhaseEvent {
  kind: "work";
  phase: WorkPhase;
  progress: Partial<WorkProgress>;
}

// offset 은 이 조각 앞까지의 글자 수(서버 len — 코드포인트). reset 은 다시 부르기 전에 쓰던 글을 비운다
export interface SectionDeltaEvent {
  kind: "section_delta";
  gen_id: number;
  target: string;
  seq: number;
  offset: number;
  text: string;
  reset?: boolean;
}

export type WorkEvent = WorkSnapshotEvent | WorkGenerationEvent | WorkPhaseEvent | SectionDeltaEvent;

// ── 화면 상태 ─────────────────────────────────────────────
export type WorkResource = "work" | "topics" | "reading" | "proposal";

// 절 키별로 흘러 들어오는 글. broken 이면 조각을 놓쳤다 — 끝난 뒤 계획서를 다시 읽어 맞춘다
export interface LiveSection {
  genId: number;
  text: string;
  nextSeq: number;
  broken: boolean;
}

export interface WorkState {
  work: WorkView | null;
  topics: TopicsView | null;
  reading: ReadingView | null;
  proposal: ProposalView | null;
  live: Record<string, LiveSection>;
}
