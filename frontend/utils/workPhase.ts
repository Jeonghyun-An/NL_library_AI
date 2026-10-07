// frontend/utils/workPhase.ts
// 연구 어시스턴트의 단계 — 주소 ?s= 는 지금 보는 단계, research_works.phase 는 도달한 단계다(06b 정함 14).
// 진행 막대·요약 띠·범위 띠·온보딩의 문구도 여기서 만든다(.vue 는 그리기만 한다)
import type { ResearchView } from "~/types/research";
import type { Corpus, WorkPhase, WorkStep, WorkView } from "~/types/work";
import { pubYear } from "~/utils/citations";
import type { QueryValue } from "~/utils/restorePosition";

export const WORK_STEPS: readonly WorkStep[] = ["topics", "reading", "proposal"];

// 진행 막대는 ① 탐색(딥리서치 — 이어갈 때 이미 끝나 있다)부터 센다
type StepKey = "explore" | WorkStep;
const STEP_KEYS: readonly StepKey[] = ["explore", ...WORK_STEPS];
const STEP_LABEL: Record<StepKey, string> = {
  explore: "탐색",
  topics: "주제",
  reading: "읽기 목록",
  proposal: "계획서",
};
const PHASE_LINE: Record<WorkPhase, string> = {
  topics: "2/4 단계 · 주제 고르는 중",
  reading: "3/4 단계 · 읽기 목록 만드는 중",
  proposal: "4/4 단계 · 계획서 쓰는 중",
  done: "4/4 단계 · 완료",
};

function isWorkStep(s: string): s is WorkStep {
  return (WORK_STEPS as readonly string[]).includes(s);
}

// 틀린 값·빈 값은 null — 단계 화면이 아니라 탐색·보고서를 연다(기존 링크 호환, spec §4)
export function parseWorkStep(query: Record<string, unknown>): WorkStep | null {
  const raw = Array.isArray(query.s) ? query.s[0] : query.s;
  const s = typeof raw === "string" ? raw.trim() : "";
  return isWorkStep(s) ? s : null;
}

// 도달한 단계에서 열 화면. 완료(done)는 계획서 화면이다. 처음 보는 값(뒤 라운드 서버)은 주제로 연다
export function stepForPhase(phase: WorkPhase): WorkStep {
  if (phase === "done") return "proposal";
  return isWorkStep(phase) ? phase : "topics";
}

export interface StepperItem {
  key: StepKey;
  label: string;
  state: "done" | "current" | "todo";
  clickable: boolean;
}

// state 는 도달한 단계(phase)로 정한다. 누를 수 있는 것은 끝난 단계와 지금 단계(돌아갈 곳) — 아직 오지 않은
// 단계와 지금 보고 있는 단계(current, null 이면 탐색·보고서)는 누를 수 없다
export function stepperItems(phase: WorkPhase, current: WorkStep | null): StepperItem[] {
  const reached = phase === "done" ? STEP_KEYS.length : STEP_KEYS.indexOf(stepForPhase(phase));
  const viewing: StepKey = current ?? "explore";
  return STEP_KEYS.map((key, i) => {
    const state = i < reached ? "done" : i === reached ? "current" : "todo";
    return { key, label: STEP_LABEL[key], state, clickable: state !== "todo" && key !== viewing };
  });
}

export function stepLine(phase: WorkPhase): string {
  return PHASE_LINE[phase] ?? PHASE_LINE.topics;
}

// 단계를 바꾸는 주소 — 돌아갈 자리(at·y)는 그 화면의 것이라 뗀다. null 이면 탐색·보고서(?s= 없음)
export function withStep(query: Readonly<Record<string, QueryValue>>, step: WorkStep | null): Record<string, QueryValue> {
  const out = { ...query };
  delete out.at;
  delete out.y;
  delete out.s;
  if (step) out.s = step;
  return out;
}

// 단계 화면에서 보고서가 접힌 요약 띠(spec §4 S3) — 질문·절 수·채택·제외
export interface SummaryBand {
  question: string;
  sections: number;
  adopted: number | null;
  excluded: number | null;
}

// 최종 보고서의 통계가 정본이고, 없으면(옛 보고서) 탐색 카운터를 쓴다. 제외 수를 모르는 잡(무관 제외 전)은 null
export function summaryBand(view: ResearchView): SummaryBand {
  const stats = view.report?.stats;
  return {
    question: view.question,
    sections: view.report?.sections.length ?? 0,
    adopted: stats ? stats.evidence_adopted : view.counters.evidenceAdopted,
    excluded: stats ? (stats.excluded ?? null) : view.counters.excluded,
  };
}

// 제외는 하위질문별 판단의 수라 "건"으로 적는다(researchReport.reportIntro 와 같은 까닭). 모르는 값은 칸째 뺀다
export function summaryLine(b: SummaryBand): string {
  const parts: string[] = [];
  if (b.sections > 0) parts.push(`절 ${b.sections}개`);
  if (b.adopted !== null) parts.push(`채택 ${b.adopted}편`);
  if (b.excluded !== null) parts.push(`제외 ${b.excluded}건`);
  return parts.join(" · ");
}

// 범위 띠(고정, spec §4) — 편수는 소장 적재분의 수이고 연도별 편수는 수집 상한 때문에 동향이 아니다
export function scopeLine(corpus: Corpus | null | undefined): string | null {
  if (!corpus?.n_papers) return null;
  const to = pubYear(corpus.to);
  const until = to ? `(~${to})` : "";
  return `소장 KCI 적재분 ${corpus.n_papers.toLocaleString("ko-KR")}편${until} 기준 · 편수 추이는 동향이 아님`;
}

// [이 연구 이어가기] 를 이 브라우저에서 처음 누를 때 한 번 띄우는 안내(spec §4). 진행 막대의 [?] 로 다시 본다
export const ONBOARDING_KEY = "skx_work_onboarded";

export const ONBOARDING_STEPS: readonly { title: string; body: string; decide: string }[] = [
  {
    title: "주제",
    body: "보고서의 향후 과제와 근거가 부족했던 하위질문에서 주제 카드를 만듭니다. 카드마다 연구 질문과 근거 논문이 붙습니다.",
    decide: "카드 하나를 고릅니다. 카드를 고치거나 직접 쓸 수도 있습니다.",
  },
  {
    title: "읽기 목록",
    body: "탐색에서 채택한 논문이 후보로 들어와 있습니다. 논문마다 들어온 경로를 볼 수 있고, 자기점검이 뺀 논문도 되살릴 수 있습니다.",
    decide: "읽을 논문을 담습니다. 5편 이상 담으면 목차를 만들 수 있습니다.",
  },
  {
    title: "계획서",
    body: "담은 논문으로 목차를 만들고 선행연구와 연구 공백 절을 근거 인용과 함께 씁니다. 결과·논의는 쓰지 않습니다.",
    decide: "목차를 승인하고 문단을 수락하거나 고친 뒤 Word 로 내려받습니다.",
  },
];

// 보고서 끝 [이 연구 이어가기] 카드(spec §4 S2) — 4단계 미리보기와 버튼. exists 는 useResearchWork 의 값이다
// (null = 아직 모름, false = 이어가지 않음, true = 이어간 연구). 모르는 동안(확인 중·조회 실패)에도 이어가기를
// 누를 수 있다 — POST continue 는 멱등이라 이미 이어간 연구면 그 연구를 돌려준다
export interface ContinueCardView {
  title: string;
  body: string;
  preview: { label: string; state: StepperItem["state"] }[];
  label: string;
  action: "continue" | "open";
  note: string | null;
}

function continuePreview(phase: WorkPhase | null): ContinueCardView["preview"] {
  return stepperItems(phase ?? "topics", null).map((item) => ({
    label: item.key === "explore" ? "탐색 끝" : item.label,
    state: phase === null && item.key !== "explore" ? "todo" : item.state,
  }));
}

export function continueCard(exists: boolean | null, work: WorkView | null): ContinueCardView {
  if (exists === true) {
    return {
      title: "이어간 연구",
      body: work ? stepLine(work.phase) : "이어간 연구가 있습니다.",
      preview: continuePreview(work?.phase ?? null),
      label: "이어간 연구 열기",
      action: "open",
      // 예시 연구(is_example)는 쓰기 API 가 409 다 — 둘러보기만 한다는 것을 누르기 전에 알린다
      note: work?.is_example ? "예시 연구는 읽기 전용입니다 — 둘러볼 수 있고 바꿀 수는 없습니다." : null,
    };
  }
  return {
    title: "이 연구 이어가기",
    body: "탐색이 끝났습니다. 주제 → 읽기 목록 → 계획서를 거쳐 연구계획서 초안까지 이어 갈 수 있습니다.",
    preview: continuePreview(null),
    label: "이 연구 이어가기",
    action: "continue",
    note: null,
  };
}
