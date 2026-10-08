// frontend/utils/proposalDocument.ts
import type {
  DisclosureStep,
  GenKind,
  Outline,
  PaperMeta,
  ParaState,
  ProposalSection,
  ProposalView,
  WorkView,
} from "~/types/work";
import { figureById, splitMarkers } from "~/utils/figureMarkers";
import { GAP_NOTE, SECTION_LABELS, footprint, footprintLine, sectionLabel } from "~/utils/proposalView";
import {
  fileHead,
  kstDateTime,
  kstYmd,
  xmlSafe,
  type DocBlock,
  type DocReference,
  type DocRun,
  type ReportDoc,
} from "~/utils/reportDocument";
import { scopeLine } from "~/utils/workPhase";

// 계획서 Word — 보고서와 같은 문서 모델(ReportDoc)로 만들어 useReportExport·reportDocx·ReportPrint 를 그대로 탄다

export const UNREVIEWED_WATERMARK = "미검토 AI 초안";

export interface ProposalDocInput {
  question: string;
  url: string;
  proposal: ProposalView;
  work: WorkView;
  includeProposed: boolean;
}

// 기본은 사용자가 받아들인 문단만(수락·고침·직접 작성). 검토 전 AI 제안은 사용자가 켤 때만 싣고 워터마크를 단다
const EXPORTED: readonly ParaState[] = ["accepted", "edited", "authored"];
const NOT_YET = "이 초안에는 아직 없습니다 — 다음 단계에서 씁니다.";
const RESULTS_LATER = "연구 후 직접 씁니다.";
const DISCLOSURE_INTRO =
  "이 초안의 문단은 연구 어시스턴트의 AI(대형 언어 모델)가 제안한 글을 사용자가 검토해 받아들이거나 고친 것입니다. " +
  "문단 상태는 AI 제안(검토 전)·AI 작성(수락)·AI 작성(사용자가 고침)·사용자 작성으로 저장하고, 수락만 한 문단도 AI 작성으로 셉니다.";
const KIND_LABELS: Record<GenKind, string> = {
  concepts: "핵심 개념",
  topic_card: "주제 카드",
  refine: "주제 다듬기",
  facet: "논문 특징",
  outline: "목차",
  section: "절 초안",
  paragraph: "문단 다시 쓰기",
};
const OUTCOME_LABELS: Record<string, string> = {
  ok: "완료",
  parse: "해석 실패",
  check: "검사 미달",
  transport: "전송 실패",
  broken: "끊김",
};
const MIX_LABELS: { state: ParaState; label: string }[] = [
  { state: "accepted", label: "수락" },
  { state: "edited", label: "수정" },
  { state: "authored", label: "직접 작성" },
  { state: "proposed", label: "검토 전" },
];

export function proposalFileName(topicTitle: string, date: Date, withProposed: boolean): string {
  return `연구계획서_${fileHead(topicTitle) || "초안"}_${kstYmd(date)}${withProposed ? "_미검토포함" : ""}.docx`;
}

export function buildProposalDocument(input: ProposalDocInput, now: Date): ReportDoc {
  const p = input.proposal;
  const outline = p.outline;
  const shown: readonly ParaState[] = input.includeProposed ? [...EXPORTED, "proposed"] : EXPORTED;
  // 번호는 논문(cnts_id)마다 문서에 처음 나온 순서다 — 절마다 [E#] 가 가리키는 논문이 달라도 한 논문은 한 번호다
  const numbers = new Map<string, number>();
  let shownProposed = 0;

  function cite(cnts: string): DocRun {
    const n = numbers.get(cnts) ?? numbers.size + 1;
    numbers.set(cnts, n);
    return { cite: n };
  }

  // [E#] 는 그 절의 근거 지도로 논문을 찾아 문서 번호로, [F#] 는 코드가 센 값 글자로 바꾼다
  function runs(text: string, section: ProposalSection): DocRun[] {
    const out: DocRun[] = [];
    for (const part of splitMarkers(text)) {
      if (part.type === "text") {
        out.push({ text: xmlSafe(part.text) });
      } else if (part.type === "cite") {
        const cnts = section.evidence[part.eid];
        if (cnts) out.push(cite(cnts));
      } else {
        const figure = figureById(section.figures, part.fid);
        if (figure) out.push({ text: xmlSafe(figure.value) });
      }
    }
    return out;
  }

  function sectionBlocks(key: string): DocBlock[] {
    const section = p.sections[key];
    if (!section) return [muted("아직 쓰지 않았습니다.")];
    const paragraphs = section.paragraphs.filter((x) => shown.includes(x.state));
    if (!paragraphs.length) {
      return [muted("받아들인 문단이 없습니다 — 화면에서 [수락]하거나 '미수락 문단도 넣기'를 켜면 실립니다.")];
    }
    shownProposed += paragraphs.filter((x) => x.state === "proposed").length;
    return paragraphs.flatMap((x) => lines(x.text).map((line): DocBlock => ({ type: "para", runs: runs(line, section) })));
  }

  const title = outline?.topic.title || input.question;
  const blocks: DocBlock[] = [
    { type: "title", text: xmlSafe(title) },
    ...metaBlocks(input, now),
    heading(`1. ${SECTION_LABELS.topic}`),
    outline ? plain(outline.topic.title) : muted("주제를 아직 고르지 않았습니다."),
    heading(`2. ${SECTION_LABELS.background}`),
    muted(NOT_YET),
    heading(`3. ${SECTION_LABELS.prior}`),
  ];
  const groups = outline?.groups ?? [];
  if (!groups.length) blocks.push(muted("목차를 아직 만들지 않았습니다."));
  groups.forEach((g, i) => {
    blocks.push({ type: "heading", level: 2, text: xmlSafe(`3.${i + 1} ${g.name}`) }, ...sectionBlocks(g.key));
  });
  blocks.push(
    heading(`4. ${SECTION_LABELS.gap}`),
    muted(`${p.sections.gap?.note ?? GAP_NOTE}로만 적은 절입니다.`),
    ...sectionBlocks("gap"),
    heading(`5. ${SECTION_LABELS.question}`),
    outline?.question ? plain(outline.question) : muted("목차에서 연구 질문을 아직 정하지 않았습니다."),
    heading(`6. ${SECTION_LABELS.method}`),
    ...(outline?.method.trim() ? lines(outline.method).map(plain) : [muted("방법을 아직 적지 않았습니다.")]),
    heading("결과·논의"),
    muted(RESULTS_LATER),
    heading("부록: AI 사용 공개"),
    muted(DISCLOSURE_INTRO),
    { type: "bullets", items: disclosureLines(p, input.includeProposed).map((line) => [{ text: xmlSafe(line) }]) },
  );

  const references: DocReference[] = [...numbers].map(([cnts, n]) => ({
    n,
    eid: cnts,
    text: xmlSafe(p.references[cnts] ?? fallbackReference(cnts, p.papers[cnts])),
  }));
  return {
    fileName: proposalFileName(title, now, shownProposed > 0),
    blocks,
    references,
    ...(shownProposed > 0 ? { watermark: UNREVIEWED_WATERMARK } : {}),
  };
}

// 부록 "AI 사용 공개" — 문단 상태 비율·고른 주제의 출처·절별 상태·실은 문단·생성 단계(모델·완료 시각·시도)·결과·논의 미포함.
// 시도는 모델·결과만 싣는다 — 실패 사유(error)에는 내부 주소가 들어 있어 문서에 내보내지 않는다
export function disclosureLines(p: ProposalView, includeProposed: boolean): string[] {
  const f = footprint(p);
  // 실은 검토 전 문단은 문서가 그리는 절(목차 묶음·연구 공백)에서만 센다 — 워터마크·파일 이름 꼬리(shownProposed)와 같은 범위다
  const included = printedProposedCount(p);
  const out = [`문단 상태: ${footprintLine(f)}`];
  if (p.topic_source) out.push(topicSourceLine(p.topic_source));
  for (const key of sectionKeys(p)) {
    const section = p.sections[key];
    if (section) out.push(`${sectionLabel(key, p.outline)}: ${stateMix(section)}`);
  }
  out.push(
    includeProposed && included
      ? `이 문서에 실은 문단: 수락·수정·직접 쓴 문단과 검토 전 AI 제안 ${included}문단(쪽마다 '${UNREVIEWED_WATERMARK}' 표시)`
      : "이 문서에 실은 문단: 수락·수정·직접 쓴 문단(검토 전 AI 제안은 싣지 않음)",
  );
  for (const step of p.disclosure.steps) out.push(stepLine(step, p.outline));
  out.push("결과·논의 미포함 — 결과·논의·가설 수치는 AI 가 쓰지 않았고 이 문서에도 없습니다.");
  return out;
}

function heading(text: string): DocBlock {
  return { type: "heading", level: 1, text: xmlSafe(text) };
}

function plain(text: string): DocBlock {
  return { type: "para", runs: [{ text: xmlSafe(text) }] };
}

function muted(text: string): DocBlock {
  return { type: "para", runs: [{ text: xmlSafe(text) }], muted: true };
}

// 사용자가 고친 문단·방법에는 줄바꿈이 들어 있을 수 있다 — Word 런은 줄바꿈을 그리지 않으므로 줄마다 문단으로 나눈다
function lines(text: string): string[] {
  return text
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function metaBlocks(input: ProposalDocInput, now: Date): DocBlock[] {
  const corpus = input.proposal.corpus ?? input.work.corpus ?? null;
  const scope = scopeLine(corpus);
  const at = corpus?.at ? new Date(corpus.at) : null;
  const when = at && !Number.isNaN(at.getTime()) ? ` — ${kstDateTime(at)} 시점` : "";
  return [
    `연구계획서 초안 · 원 질문 ${input.question}`,
    `생성 일시 ${kstDateTime(now)}`,
    scope ? `범위 ${scope}${when}` : "",
    input.url ? `연구 주소 ${input.url}` : "",
    input.work.is_example ? "예시 연구 — 미리 돌린 실제 기록입니다" : "",
  ]
    .filter(Boolean)
    .map((text): DocBlock => ({ type: "meta", text: xmlSafe(text) }));
}

// 문서가 그리는 절 — 목차 순서(선행연구 묶음 → 연구 공백). 계획서 화면의 절 목록(ProposalStep)도 이 범위를 쓴다 —
// 절을 더하면(06c 연구 배경 등) 화면과 문서가 함께 바뀐다
export function printedKeys(p: ProposalView): string[] {
  return [...(p.outline?.groups.map((g) => g.key) ?? []), "gap"];
}

// 문서에 실릴 수 있는 검토 전 AI 제안 수 — 문서가 그리는 절에서만 센다. 목차를 다시 만들며 빠진 옛 절(prior.g3 등)은
// 문서에 실리지 않는다. 공개 부록의 '실은 문단' 줄과 화면의 '미수락 문단도 넣기(워터마크)' 토글이 이 수를 쓴다
export function printedProposedCount(p: ProposalView): number {
  return printedKeys(p).reduce(
    (n, k) => n + (p.sections[k]?.paragraphs.filter((x) => x.state === "proposed").length ?? 0),
    0,
  );
}

// 목차 순서(선행연구 묶음 → 연구 공백) 뒤에, 목차에서 빠진 옛 절이 남아 있으면 그것도 센다
function sectionKeys(p: ProposalView): string[] {
  const ordered = printedKeys(p);
  return [...ordered, ...Object.keys(p.sections).filter((k) => !ordered.includes(k)).sort()];
}

// 고른 주제의 출처(spec §5-2 — card.edited 는 공개 부록용). 사용자가 직접 쓴 주제는 고쳐도 사용자 작성이다
function topicSourceLine(source: NonNullable<ProposalView["topic_source"]>): string {
  if (source.origin === "user") return "주제: 사용자가 직접 쓴 주제";
  return source.edited ? "주제: AI 주제 카드(사용자가 고침)" : "주제: AI 주제 카드";
}

function stateMix(section: ProposalSection): string {
  const n = section.paragraphs.length;
  if (!n) return "문단 없음";
  const parts = MIX_LABELS.map(({ state, label }) => {
    const count = section.paragraphs.filter((x) => x.state === state).length;
    return count ? `${label} ${count}` : "";
  }).filter(Boolean);
  return `문단 ${n}개 — ${parts.join("·")}`;
}

function stepName(step: DisclosureStep, outline: Outline | null): string {
  const label = KIND_LABELS[step.kind] ?? step.kind;
  if (!step.target) return label;
  if (step.kind === "section") return `${label}(${sectionLabel(step.target, outline)})`;
  if (step.kind === "paragraph") {
    const [key = "", pid = ""] = step.target.split("#");
    return `${label}(${sectionLabel(key, outline)} ${pid})`;
  }
  if (step.kind === "topic_card") return `${label}(#${step.target})`;
  return label;
}

function stepLine(step: DisclosureStep, outline: Outline | null): string {
  const model = step.model ?? "모델 출력 없음(기본값으로 채움)";
  const done = step.finished_at ? new Date(step.finished_at) : null;
  const when = done && !Number.isNaN(done.getTime()) ? kstDateTime(done) : "완료 시각 기록 없음";
  const tries =
    step.attempts.length > 1
      ? ` — 시도 ${step.attempts.length}회: ${step.attempts
          .map((a) => `${a.model} ${OUTCOME_LABELS[a.outcome] ?? a.outcome}`)
          .join(" → ")}`
      : "";
  return `${stepName(step, outline)}: ${model} · ${when}${tries}`;
}

function fallbackReference(cnts: string, meta: PaperMeta | undefined): string {
  const title = meta?.title?.trim();
  return title ? `${title}.` : `서지 정보 없음 (${cnts}).`;
}
