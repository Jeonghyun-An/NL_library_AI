// frontend/utils/proposalDocument.ts
import type { PaperMeta, ParaState, ProposalSection, ProposalView, WorkView } from "~/types/work";
import { figureById, splitMarkers } from "~/utils/figureMarkers";
import {
  FOOTPRINT_EMPTY,
  GAP_NOTE,
  SECTION_LABELS,
  footprint,
  footprintLine,
  reviewLine,
  reviewSpots,
  sectionKeysOf,
  sectionLabel,
} from "~/utils/proposalView";
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
import { FINAL_STEP_NAME, scopeLine } from "~/utils/workPhase";

// 보고서(연구계획서형 초안) Word — 딥리서치 보고서와 같은 문서 모델(ReportDoc)로 만들어 useReportExport·reportDocx·ReportPrint
// 를 그대로 탄다. 기본은 네 상태 문단을 모두 싣고 워터마크를 달지 않는다 — 어느 문단을 AI 가 썼는지는 끝의 AI 사용 공개
// 부록이 문단 상태별 개수로 밝힌다(D21). 이 문서 모델은 ReportDoc.watermark 를 만들지 않는다

export interface ProposalDocInput {
  question: string;
  url: string;
  proposal: ProposalView;
  work: WorkView;
  // '수락한 문단만' — 켜면 검토 전 AI 작성 문단(proposed)을 빼고 수락·수정·직접 작성만 싣는다(워터마크 없음)
  acceptedOnly: boolean;
}

const ALL_STATES: readonly ParaState[] = ["proposed", "accepted", "edited", "authored"];
const ACCEPTED_ONLY: readonly ParaState[] = ["accepted", "edited", "authored"];
const RESULTS_LATER = "연구 후 직접 씁니다.";
// 서버가 '다시 맞춤 필요'(stale)를 붙인 절 — 주제·묶음·연구 질문이 바뀐 뒤에도 [보고서 다시 만들기]는 이미 쓴 절을 다시 쓰지
// 않아(06e 정함 4) 옛 주제·묶음으로 쓴 문단이 같은 키로 남는다. 화면 배지·안내(ProposalSection)와 같은 말로 문서에도 밝힌다
const STALE_LABEL = "다시 맞춤 필요";
const STALE_NOTE = `${STALE_LABEL} — 이 절을 쓴 뒤 주제나 목차의 묶음·연구 질문이 바뀌었고, 바뀐 목차로 다시 쓰지 않았습니다.`;
const DISCLOSURE_INTRO =
  "이 초안의 문단은 연구 어시스턴트의 AI(대형 언어 모델)가 소장 KCI 논문을 근거로 작성했고, 사용자가 검토해 수락·수정하거나 " +
  "직접 쓴 문단이 섞여 있습니다. 문단 상태는 AI 작성·검토 전 / 수락 / 수정 / 직접 작성 네 가지로 저장합니다.";
// 부록의 절별 문단 상태 — 화면 띠(ProposalSection 의 STATE_LABELS)와 같은 순서·같은 상태지만 글자는 다르다: 띠는
// 'AI 작성 · 고침'(가운데점 앞뒤 띄움), 부록·footprintLine 은 '수정'(DISCLOSURE_INTRO 의 네 상태 이름). 어느 말로 맞출지는
// spec §12-4 정리(Task Z3)에서 정한다
const MIX_LABELS: { state: ParaState; label: string }[] = [
  { state: "proposed", label: "AI 작성·검토 전" },
  { state: "accepted", label: "수락" },
  { state: "edited", label: "수정" },
  { state: "authored", label: "직접 작성" },
];

export function proposalFileName(topicTitle: string, date: Date, acceptedOnly: boolean): string {
  return `${FINAL_STEP_NAME}_${fileHead(topicTitle) || "초안"}_${kstYmd(date)}${acceptedOnly ? "_수락문단만" : ""}.docx`;
}

export function buildProposalDocument(input: ProposalDocInput, now: Date): ReportDoc {
  const p = input.proposal;
  const outline = p.outline;
  const shown = input.acceptedOnly ? ACCEPTED_ONLY : ALL_STATES;
  // 번호는 논문(cnts_id)마다 문서에 처음 나온 순서다 — 절마다 [E#] 가 가리키는 논문이 달라도 한 논문은 한 번호다
  const numbers = new Map<string, number>();

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
      // 문단을 모두 지운 절은 쓰지 않은 절과 같다. '수락한 문단만'에 실을 문단이 없으면 끄는 길을 알린다
      return [
        muted(
          input.acceptedOnly && section.paragraphs.length
            ? "수락한 문단이 없습니다 — '수락한 문단만'을 끄면 AI 작성 문단도 실립니다."
            : "아직 쓰지 않았습니다.",
        ),
      ];
    }
    // 실은 문단이 있을 때만 — 기본(모든 문단)이면 검토 전 AI 문단이 옛 주제·묶음 그대로 새 목차 제목 아래 실린다
    const body = paragraphs.flatMap((x) => lines(x.text).map((line): DocBlock => ({ type: "para", runs: runs(line, section) })));
    return p.stale.sections[key] === true ? [muted(STALE_NOTE), ...body] : body;
  }

  const title = outline?.topic.title || input.question;
  const blocks: DocBlock[] = [
    { type: "title", text: xmlSafe(title) },
    ...metaBlocks(input, now),
    heading(`1. ${SECTION_LABELS.topic}`),
    outline ? plain(outline.topic.title) : muted("주제를 아직 고르지 않았습니다."),
    heading(`2. ${SECTION_LABELS.background}`),
    // 연구 배경은 사용자가 보고서 화면 2절 칸에 적는 글(outline.background, 06e) — AI 가 쓰지 않는다
    ...(outline?.background?.trim() ? lines(outline.background).map(plain) : [muted("연구 배경을 아직 적지 않았습니다.")]),
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
    { type: "bullets", items: disclosureLines(p, input.acceptedOnly, now).map((line) => [{ text: xmlSafe(line) }]) },
  );

  const references: DocReference[] = [...numbers].map(([cnts, n]) => ({
    n,
    eid: cnts,
    text: xmlSafe(p.references[cnts] ?? fallbackReference(cnts, p.papers[cnts])),
  }));
  return { fileName: proposalFileName(title, now, input.acceptedOnly), blocks, references };
}

// 부록 "AI 사용 공개"(D21) — 문단 상태 비율·고른 주제의 출처·미리 담은 참고문헌 수·절별 문단 상태 개수(다시 맞춤 필요한 절은
// 덧붙인다)·실은 문단·검토할 곳(실은 문단에서 센다)·작성 일시·결과·논의 미포함. 모델 이름·생성별 시도 기록은 싣지 않는다('AI 작성·
// 검토' 수준 — 저장(research_generations.model·attempts)은 그대로)
export function disclosureLines(p: ProposalView, acceptedOnly: boolean, now: Date): string[] {
  // 쓴 문단이 없을 때의 말은 문서 말투로(화면 막대는 해요체 — FOOTPRINT_EMPTY)
  const out = [`문단 상태: ${footprintLine(footprint(p), FOOTPRINT_EMPTY.doc)}`];
  if (p.topic_source) out.push(topicSourceLine(p.topic_source));
  const preselected = p.preselected ?? 0;
  if (preselected > 0) out.push(preselectedLine(preselected));
  for (const key of sectionKeys(p)) {
    const section = p.sections[key];
    if (section) {
      out.push(`${sectionLabel(key, p.outline)}: ${stateMix(section)}${p.stale.sections[key] === true ? ` · ${STALE_LABEL}` : ""}`);
    }
  }
  out.push(includedLine(acceptedOnly, printedProposedCount(p)));
  // '수락한 문단만'이면 문서에 실은 문단만 센다 — 빠진 검토 전 문단의 검토 단서는 이 문서의 것이 아니다
  const counted = acceptedOnly
    ? {
        ...p,
        sections: Object.fromEntries(
          Object.entries(p.sections).map(([k, s]): [string, ProposalSection] => [
            k,
            { ...s, paragraphs: s.paragraphs.filter((x) => ACCEPTED_ONLY.includes(x.state)) },
          ]),
        ),
      }
    : p;
  const review = reviewLine(reviewSpots(counted));
  if (review) out.push(review);
  out.push(`작성 일시 ${kstDateTime(now)}`);
  out.push("결과·논의 미포함 — 결과·논의·가설 수치는 AI 가 쓰지 않았고 이 문서에도 없습니다.");
  return out;
}

// 실은 문단 줄 — 검토 전 AI 작성 문단은 문서가 그리는 절(목차 묶음·연구 공백)에서만 센다(화면 '수락한 문단만' 체크의 수와 같다)
function includedLine(acceptedOnly: boolean, proposed: number): string {
  if (acceptedOnly) {
    return proposed
      ? `이 문서에 실은 문단: 수락·수정·직접 쓴 문단만(검토 전 AI 작성 문단 ${proposed}개는 싣지 않음)`
      : "이 문서에 실은 문단: 수락·수정·직접 쓴 문단만(검토 전 AI 작성 문단 없음)";
  }
  return proposed
    ? `이 문서에 실은 문단: 모든 문단(검토 전 AI 작성 문단 ${proposed}개 포함)`
    : "이 문서에 실은 문단: 모든 문단(검토 전 AI 작성 문단 없음)";
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
    `${FINAL_STEP_NAME} 초안 · 원 질문 ${input.question}`,
    `생성 일시 ${kstDateTime(now)}`,
    scope ? `범위 ${scope}${when}` : "",
    input.url ? `연구 주소 ${input.url}` : "",
    input.work.is_example ? "예시 연구 — 미리 돌린 실제 기록입니다" : "",
  ]
    .filter(Boolean)
    .map((text): DocBlock => ({ type: "meta", text: xmlSafe(text) }));
}

// 문서가 그리는 절 — 목차 순서(선행연구 묶음 → 연구 공백). 계획서 화면의 절 목록(ProposalStep)과 06e 자동 산출의 차례도
// 이 범위다 — 정본은 proposalView.sectionKeysOf(이 파일이 proposalView 를 import 하므로 반대로 두면 순환 import)
export function printedKeys(p: ProposalView): string[] {
  return sectionKeysOf(p);
}

// 문서에 실릴 수 있는 검토 전 AI 작성 문단 수 — 문서가 그리는 절에서만 센다. 목차를 다시 만들며 빠진 옛 절(prior.g3 등)은
// 문서에 실리지 않는다. 공개 부록의 '실은 문단' 줄과 화면의 '수락한 문단만' 체크가 이 수를 쓴다
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

// 이어가기가 채택 근거 상위 편을 참고문헌(읽기 목록)에 담음으로 미리 넣은 사실(사용자 결정 2026-10-14 — 글자 그대로). 수는 서버가
// 센 preselected(뺀 행 포함 — 읽기 목록 머리 안내 readingList.readingIntro 와 같은 수). 0(이 기능 전에 이어간 연구)이면 싣지 않는다.
// 단계 순서(주제 → 참고문헌 선택하기 → 보고서)대로 '주제:' 줄 다음에 둔다
function preselectedLine(n: number): string {
  return `참고문헌: 이어가기 때 채택 근거 상위 ${n}편을 미리 담음 — 사용자가 확인·수정`;
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

function fallbackReference(cnts: string, meta: PaperMeta | undefined): string {
  const title = meta?.title?.trim();
  return title ? `${title}.` : `서지 정보 없음 (${cnts}).`;
}
