// frontend/utils/reportDocument.ts
import type {
  ReportEvidence,
  ReportPaper,
  ReportRange,
  ReportSection,
  ResearchReport,
  ResearchView,
  SubqView,
  TrailItem,
  Verdict,
} from "../types/research";
import { citeChunks, pdfPage, pubYear, splitAuthors, splitCitations } from "./citations";
import type { DraftReport } from "./researchDraft";
import { excludedLabel, verdictLabel } from "./researchEvents";
import { INTROLESS, NO_LIMITS, NO_SUMMARY, paperByline, rangeLabel, reportIntro } from "./researchReport";

// Word·PDF 가 같은 모델에서 그려진다 — 인용 번호·참고문헌·부록이 두 형식에서 어긋나지 않게

export type ReportExportFormat = "docx" | "pdf";

export interface DocTrailItem {
  subquestion: string;
  queries: string[];
  verdict: Verdict | null;
  evidenceCount: number | null;
  // 자기점검이 무관하다고 뺀 근거 수. 무관 제외 전 잡은 0 — 0 이면 적지 않는다
  excluded: number;
}

export interface ReportDocInput {
  question: string;
  range: Partial<ReportRange> | null;
  generatedAt: string | null;
  url: string;
  intro: string;
  sections: ReportSection[];
  evidence: Record<string, ReportEvidence>;
  limitations: string[] | null;
  trail: DocTrailItem[];
  draft: { done: number; total: number } | null;
}

export type DocRun = { text: string } | { cite: number };

export type DocBlock =
  | { type: "title"; text: string }
  | { type: "meta"; text: string }
  | { type: "heading"; level: 1 | 2; text: string }
  | { type: "para"; runs: DocRun[]; muted?: boolean }
  | { type: "bullets"; items: DocRun[][] };

export interface DocReference {
  n: number;
  eid: string;
  text: string;
}

export interface ReportDoc {
  fileName: string;
  blocks: DocBlock[];
  references: DocReference[];
}

const DRAFT_LIMITS = "작성 중에 저장한 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.";
const MISSING_EVIDENCE = "근거 정보를 찾을 수 없습니다";

// 사용자는 한국에 있다 — 문서의 날짜를 브라우저·테스트 기계의 시간대와 무관하게 한국 시각으로 적는다
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
// Windows·macOS 파일 이름에 못 쓰는 글자와 제어문자
const FILE_FORBIDDEN = /[\\/:*?"<>|\u0000-\u001f\u007f]/g;
const FILE_HEAD_CHARS = 20;
// XML 1.0 에 쓸 수 없는 글자(탭·줄바꿈을 뺀 C0 제어문자, U+FFFE·U+FFFF). 합성 출력의 JSON 을 풀 때
// LLM 이 쓴 LaTeX(\frac·\beta)가 이스케이프 \f·\b 로 풀려 들어온다 — Word 는 이 글자가 든 .docx 를 열지 못한다
const XML_ILLEGAL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/g;

export function xmlSafe(s: string): string {
  return s.replace(XML_ILLEGAL, "");
}

export function docRunText(run: DocRun): string {
  return "text" in run ? run.text : `[${run.cite}]`;
}

export function reportFileName(question: string, date: Date, draft: boolean): string {
  const cleaned = question
    .trim()
    .replace(/\s+/g, "_")
    .replace(FILE_FORBIDDEN, "")
    .replace(/_+/g, "_")
    .replace(/^_+/, "");
  // 코드 포인트 단위로 자른다 — 서로게이트 쌍 한가운데서 끊으면 깨진 글자가 남는다
  const head = Array.from(cleaned).slice(0, FILE_HEAD_CHARS).join("").replace(/[_.]+$/, "");
  return `딥리서치_${head || "보고서"}_${kstYmd(date)}${draft ? "_초안" : ""}.docx`;
}

export function buildReportDocument(input: ReportDocInput, now: Date): ReportDoc {
  const numbers = new Map<string, number>();
  const citedIn = new Map<string, ReportSection[]>();

  // 번호는 문서에 처음 나온 순서다 — 블록을 위에서 아래로 만드는 순서가 곧 읽는 순서라 여기서 매긴다
  function cite(eid: string, sec: ReportSection): DocRun {
    const n = numbers.get(eid) ?? numbers.size + 1;
    numbers.set(eid, n);
    const secs = citedIn.get(eid) ?? [];
    if (!secs.includes(sec)) secs.push(sec);
    citedIn.set(eid, secs);
    return { cite: n };
  }

  function runs(text: string, sec: ReportSection): DocRun[] {
    return splitCitations(text).map((p) => (p.type === "text" ? { text: p.text } : cite(p.eid, sec)));
  }

  const blocks: DocBlock[] = [{ type: "title", text: docTitle(input) }, ...metaBlocks(input, now)];
  if (input.intro) blocks.push({ type: "para", runs: [{ text: input.intro }] });

  input.sections.forEach((sec, si) => {
    blocks.push({ type: "heading", level: 1, text: `${si + 1}. ${sec.heading}` });
    blocks.push(
      sec.intro
        ? { type: "para", runs: runs(sec.intro, sec) }
        : { type: "para", runs: [{ text: INTROLESS }], muted: true },
    );
    if (sec.papers.length) {
      blocks.push({ type: "heading", level: 2, text: "대표 논문" });
      blocks.push({
        type: "bullets",
        items: sec.papers.map((p) => [
          { text: paperLine(p, input.evidence) + (p.evidence.length ? " " : "") },
          ...p.evidence.map((eid) => cite(eid, sec)),
        ]),
      });
    }
    if (sec.future.length) {
      blocks.push({ type: "heading", level: 2, text: "향후 과제" });
      blocks.push({ type: "bullets", items: sec.future.map((f) => runs(f.text, sec)) });
    }
  });

  blocks.push(...limitBlocks(input), ...trailBlocks(input.trail));

  const references = [...numbers].map(([eid, n]) => ({
    n,
    eid,
    text: xmlSafe(referenceText(input.evidence[eid], citedIn.get(eid) ?? [], eid)),
  }));
  // 화면은 보이지 않는 글자로 넘기지만 문서는 깨진다 — Word·인쇄가 같은 글을 쓰도록 모델에서 한 번에 뺀다
  return {
    fileName: reportFileName(input.question, now, input.draft !== null),
    blocks: blocks.map(cleanBlock),
    references,
  };
}

function cleanRun(run: DocRun): DocRun {
  return "text" in run ? { text: xmlSafe(run.text) } : run;
}

function cleanBlock(block: DocBlock): DocBlock {
  switch (block.type) {
    case "para":
      return { ...block, runs: block.runs.map(cleanRun) };
    case "bullets":
      return { ...block, items: block.items.map((runs) => runs.map(cleanRun)) };
    default:
      return { ...block, text: xmlSafe(block.text) };
  }
}

export function docInputFromReport(
  report: ResearchReport,
  opts: { generatedAt: string | null; url: string },
): ReportDocInput {
  return {
    question: report.question,
    range: report.range,
    generatedAt: opts.generatedAt,
    url: opts.url,
    intro: reportIntro(report),
    sections: report.sections,
    evidence: report.evidence,
    limitations: report.limitations,
    trail: report.trail.map(docTrailItem),
    draft: null,
  };
}

export function docInputFromDraft(draft: DraftReport, view: ResearchView, url: string): ReportDocInput {
  // 초안에는 trail 이 없다(종합이 끝나야 생긴다). 탐색은 이미 끝났으니 화면의 탐색 타임라인이 같은 내용이다 —
  // 서론의 하위질문 수도 끝난 절 수가 아니라 탐색한 하위질문 수로 센다
  return {
    question: draft.report.question,
    range: draft.report.range,
    generatedAt: null,
    url,
    intro: reportIntro(draft.report, view.subqs.length),
    sections: draft.report.sections,
    evidence: draft.report.evidence,
    limitations: null,
    trail: view.subqs.map(docTrailFromSubq),
    draft: { done: draft.done, total: draft.total },
  };
}

function docTitle(input: ReportDocInput): string {
  if (!input.draft) return input.question;
  return `${input.question} (초안 · ${input.draft.total}개 절 중 ${input.draft.done}개 작성)`;
}

function metaBlocks(input: ReportDocInput, now: Date): DocBlock[] {
  const parsed = input.generatedAt ? new Date(input.generatedAt) : null;
  const when = parsed && !Number.isNaN(parsed.getTime()) ? parsed : now;
  const range = rangeLabel(input.range);
  return [
    `생성 일시 ${kstDateTime(when)}`,
    range ? `수록 범위 ${range}` : "",
    input.url ? `연구 주소 ${input.url}` : "",
  ]
    .filter(Boolean)
    .map((text): DocBlock => ({ type: "meta", text }));
}

function paperLine(p: ReportPaper, evidence: Record<string, ReportEvidence>): string {
  const meta = evidence[p.evidence[0] ?? ""]?.meta;
  const title = meta?.title?.trim();
  const who = paperByline(meta);
  return `${title ? `${who} 「${title}」` : who} — ${p.summary || NO_SUMMARY}`;
}

function limitBlocks(input: ReportDocInput): DocBlock[] {
  const head: DocBlock = { type: "heading", level: 1, text: "이 보고서의 한계" };
  if (input.draft) return [head, { type: "para", runs: [{ text: DRAFT_LIMITS }], muted: true }];
  const lines = input.limitations ?? [];
  if (!lines.length) return [head, { type: "para", runs: [{ text: NO_LIMITS }], muted: true }];
  return [head, { type: "bullets", items: lines.map((line) => [{ text: line }]) }];
}

function trailBlocks(trail: DocTrailItem[]): DocBlock[] {
  if (!trail.length) return [];
  const out: DocBlock[] = [{ type: "heading", level: 1, text: "부록: 탐색 경로" }];
  trail.forEach((t, i) => {
    out.push({ type: "heading", level: 2, text: `${i + 1}. ${t.subquestion}` });
    const items: DocRun[][] = [];
    if (t.queries.length) items.push([{ text: `검색어: ${queryPath(t.queries)}` }]);
    if (t.verdict) items.push([{ text: `판정: ${verdictLabel(t.verdict)}` }]);
    if (t.evidenceCount !== null) items.push([{ text: `채택한 근거: ${t.evidenceCount}편` }]);
    const excluded = excludedLabel(t.excluded);
    if (excluded) items.push([{ text: excluded }]);
    if (items.length) out.push({ type: "bullets", items });
  });
  return out;
}

// 재검색은 근거가 부족하다고 판정할 때만 일어난다(보인 근거를 모두 무관하다고 빼면 부족으로 읽는다) — 검색어가 바뀐 흐름이 곧 자기점검의 기록이다
function queryPath(queries: string[]): string {
  const path = queries.map((q) => `‘${q}’`).join(" → ");
  return queries.length > 1 ? `${path} (재검색 ${queries.length - 1}회)` : path;
}

function docTrailItem(t: TrailItem): DocTrailItem {
  // 오류로 끝난 하위질문의 판정은 점검을 마친 결과가 아니다
  return {
    subquestion: t.subquestion,
    queries: t.queries,
    verdict: t.failed ? null : t.verdict,
    evidenceCount: t.evidence_count,
    excluded: t.excluded ?? 0,
  };
}

// 초안 부록은 화면의 탐색 타임라인에서 만든다. 채택 수를 모르는 하위질문(채택 전에 오류로 멈춤)은 0편으로
// 채우지 않고 비운다 — 부록은 모르는 칸을 뺀다(0 으로 적으면 모은 근거가 있어도 "0편"이라고 쓴다)
function docTrailFromSubq(sq: SubqView): DocTrailItem {
  return {
    subquestion: sq.title,
    queries: sq.rounds.map((r) => r.query).filter(Boolean),
    verdict: sq.status === "failed" ? null : sq.verdict,
    evidenceCount: sq.adopted,
    // 초안에는 trail 이 없어 회차마다 뺀 수를 더한다 — 최종본 trail 의 총수와 같은 값이다
    excluded: sq.rounds.reduce((n, r) => n + (r.excluded ?? 0), 0),
  };
}

function referenceText(ev: ReportEvidence | undefined, secs: ReportSection[], eid: string): string {
  if (!ev) return MISSING_EVIDENCE;
  const m = ev.meta;
  const authors = splitAuthors(m.personal_author).join(", ");
  const year = pubYear(m.pub_date);
  const title = m.title?.trim() ?? "";
  const journal = [m.series_title, m.vol_issue].map((s) => s?.trim() ?? "").filter(Boolean).join(", ");
  const parts: string[] = [];
  if (authors && year) parts.push(`${authors} (${year}).`);
  else if (authors) parts.push(sentence(authors));
  else if (year) parts.push(`(${year}).`);
  if (title) parts.push(sentence(title));
  if (journal) parts.push(sentence(journal));
  if (!parts.length) parts.push(`서지 정보 없음 (${ev.cnts_id}).`);
  const pages = citedPages(secs, ev, eid);
  if (pages) parts.push(`인용 쪽: ${pages}`);
  return parts.join(" ");
}

function sentence(s: string): string {
  return /[.?!]$/.test(s) ? s : `${s}.`;
}

// 칩 팝오버와 같은 대목(citeChunks)·같은 쪽 규칙(pdfPage — 0-based 저장값 + 1, 0 은 쪽 정보 없음)을 쓴다.
// 겹치거나 맞붙은 쪽은 한 범위로 합친다 — 같은 대목을 두 절이 인용해도 한 번만 적힌다
function citedPages(secs: ReportSection[], ev: ReportEvidence, eid: string): string {
  const ranges: [number, number][] = [];
  for (const sec of secs) {
    for (const c of citeChunks(sec, ev, eid)) {
      const start = pdfPage(c);
      if (start === undefined) continue;
      ranges.push([start, Math.max(start, c.page_end + 1)]);
    }
  }
  ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: [number, number][] = [];
  for (const [s, e] of ranges) {
    const last = merged[merged.length - 1];
    if (last && s <= last[1] + 1) last[1] = Math.max(last[1], e);
    else merged.push([s, e]);
  }
  return merged.map(([s, e]) => (e > s ? `${s}–${e}` : `${s}`)).join(", ");
}

function kstParts(date: Date): { y: number; m: number; d: number; hh: number; mm: number } {
  const k = new Date(date.getTime() + KST_OFFSET_MS);
  return { y: k.getUTCFullYear(), m: k.getUTCMonth() + 1, d: k.getUTCDate(), hh: k.getUTCHours(), mm: k.getUTCMinutes() };
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function kstDateTime(date: Date): string {
  const p = kstParts(date);
  return `${p.y}년 ${p.m}월 ${p.d}일 ${pad2(p.hh)}:${pad2(p.mm)}`;
}

function kstYmd(date: Date): string {
  const p = kstParts(date);
  return `${p.y}${pad2(p.m)}${pad2(p.d)}`;
}
