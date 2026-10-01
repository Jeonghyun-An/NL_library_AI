# round04b 교본 (6) — 내보내기: 문서 모델·Word·PDF 인쇄

> 이 교본 하나로 round04b 의 핵심을 클론코딩할 수 있어야 한다. 코드는 round04b 브랜치 끝(`d845b8b`)의 파일을 그대로 수록했다.

전체 개요·검증·Q&A 는 [00-개요.md](00-개요.md) 참조.

## 이 챕터의 자리

spec §14 의 두 번째 요청 — "보고서를 문서로 내려받는 기능이 있었으면 좋겠다. 최종본이 완성된 뒤가 깔끔하지만, 중간에도 저장할 수 있으면 그렇게 해 달라."

| 결정 | 근거(spec §14-1) |
|---|---|
| E3 **Word(.docx) + PDF(브라우저 인쇄 → PDF로 저장)** | Word 는 고쳐 쓰기 좋고 한글(HWP)에서도 열린다. PDF 는 인쇄 전용 화면이라 서버·의존성 변경이 없다. Markdown·HWPX 는 범위 밖 |
| E4 **완성 뒤 [다운로드]가 기본, 작성 중·멈춘 초안도 [초안 저장]** | 사용자 요청. 초안도 보고서와 같은 모양이라 같은 코드로 문서를 만든다. 초안 문서는 제목·파일 이름에 초안임을 밝힌다 |
| E5 **Word·PDF 는 문서 모델 하나에서** | 인용 번호·참고문헌·부록이 두 형식에서 어긋나지 않는다. 모델 생성은 순수 함수라 Vitest 로 검증한다 |
| E6 **부록: 탐색 경로** | 자기점검·재검색 과정이 딥리서치의 차별점이다(사용자 결정) |

```text
화면 상태(view)                     문서 모델(순수)                 출력
 ├ 완성본 view.report ─ docInputFromReport ─┐
 └ 초안 draftReport(view) ─ docInputFromDraft ┴▶ buildReportDocument ─▶ ReportDoc{fileName, blocks, references}
                                                                        ├▶ reportDocx.toDocxBlob (docx 동적 import) ─▶ .docx 내려받기
                                                                        └▶ ReportPrint(body 에 Teleport) + @media print ─▶ window.print()
```

## 2. 구현 (클론코딩)

### 2.48 `utils/reportDocument.ts` — 문서 모델

**책임.** 입력(`ReportDocInput` — 질문·수록 범위·생성 시각·연구 주소·서론·절·근거·한계·부록·초안 여부)을 블록 목록(제목·메타·제목줄·문단·글머리표)과 참고문헌으로 바꾼다. 문단은 글 조각과 인용 번호의 배열(`DocRun`)이다. 파일 이름도 여기서 정한다.

**문서의 구성.** ① 제목(질문, 초안이면 "(초안 · 5개 절 중 2개 작성)") ② 메타(생성 일시·수록 범위·연구 주소) ③ 서론 한 줄(화면과 같은 `reportIntro`) ④ 절마다 "1. 소제목" → 도입 → "대표 논문"(`저자 외 (연도) 「제목」 — 요약 [n]`) → "향후 과제" ⑤ 이 보고서의 한계(초안이면 "작성 중에 저장한 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.") ⑥ 부록: 탐색 경로 ⑦ 참고문헌.

**왜 이렇게 짰나.**

- **인용 번호는 문서에 처음 나온 순서다.** 블록을 위에서 아래로 만드는 순서(절 순서 → 도입 → 대표 논문 → 향후 과제)가 곧 읽는 순서라 블록을 만들며 번호를 매긴다. 같은 근거는 어디서 나와도 같은 번호이고, 참고문헌에는 인용된 근거만 싣는다. 화면의 `E12` 같은 근거 번호는 탐색 중에 발급된 내부 번호라 문서의 읽는 순서와 다르다 — 문서는 그것을 쓰지 않고 새로 매긴다.
- **참고문헌 한 줄은 `[n] 저자1, 저자2 (연도). 제목. 학술지명, 권(호). 인용 쪽: 12–13, 20`.** 메타가 빠진 칸은 생략한다(`splitAuthors`·`pubYear` 재사용). 인용 쪽은 그 근거를 인용한 절들이 쓴 대목을 칩 팝오버와 같은 규칙(`citeChunks` — 그 절의 대목만)으로 모아, 같은 쪽 규칙(`pdfPage` — 0-based 저장값 + 1, 0 은 쪽 정보 없음)으로 적는다. 겹치거나 맞붙은 쪽은 한 범위로 합친다 — 같은 대목을 두 절이 인용해도 한 번만 적힌다. 남는 쪽이 없으면 "인용 쪽" 칸을 싣지 않는다.
- **초안의 부록은 화면의 탐색 타임라인에서 만든다.** 초안에는 `trail` 이 없다(종합이 끝나야 생긴다). 탐색은 이미 끝났으니 `view.subqs` 가 같은 내용이다. 서론의 하위질문 수도 끝난 절 수가 아니라 탐색한 하위질문 수로 센다(`9f9af0f`). 채택 수를 모르는 하위질문(채택 전에 오류로 멈춤)은 0편으로 채우지 않고 칸을 뺀다 — 0 으로 적으면 모은 근거가 있어도 "0편"이라고 쓴다. 오류로 끝난 하위질문의 판정은 점검을 마친 결과가 아니라 싣지 않는다.
- **부록의 검색어 흐름이 곧 자기점검의 기록이다.** `‘A’ → ‘B’ (재검색 1회)` — 재검색은 근거가 부족하다고 판정했을 때만 일어난다.
- **XML 에 쓸 수 없는 글자를 뺀다(`xmlSafe`)**(`88806cd`, §14 Task 9 품질 검토). 합성 출력의 JSON 을 풀 때 LLM 이 쓴 LaTeX(`\frac`·`\beta`)가 이스케이프 `\f`·`\b` 로 풀려 제어문자(U+000C·U+0008)가 들어온다. `docx` 는 `&<>"'` 만 이스케이프하고 제어문자는 `<w:t>` 에 그대로 써서 **Word 가 그 파일을 열지 못한다.** 화면은 보이지 않는 글자로 넘기지만 문서는 깨진다. 모델이 모든 블록·참고문헌 글에서 한 번에 빼 Word·인쇄가 같은 글을 쓴다. 정규식의 U+FFFE·U+FFFF 는 보이지 않는 글자 그대로 소스에 있으면 diff·에디터로 확인할 수 없고 정규화에 조용히 사라질 수 있어 `￾￿` 이스케이프로 적었다(`edeb5ad`).
- **날짜는 한국 시각으로 적는다.** 사용자는 한국에 있다 — 브라우저·테스트 기계의 시간대와 무관하게 UTC+9 로 계산한다(테스트가 시간대에 따라 흔들리지 않는다).
- **파일 이름 `딥리서치_<질문 앞 20자>_<YYYYMMDD>.docx`(초안은 `…_초안.docx`).** Windows·macOS 파일 이름에 못 쓰는 글자(`\ / : * ? " < > |`·제어문자)는 빼고 공백은 `_` 로. 코드 포인트 단위로 자른다 — 서로게이트 쌍 한가운데서 끊으면 깨진 글자가 남는다. 쓸 글자가 남지 않으면 "보고서".
- **빈자리 문구는 화면과 같은 상수**(`INTROLESS`·`NO_SUMMARY`·`NO_LIMITS`, [04](04-작성중-초안.md) §2.39).

**파일**: `frontend/utils/reportDocument.ts` — 전체 339줄

```ts
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
import { verdictLabel } from "./researchEvents";
import { INTROLESS, NO_LIMITS, NO_SUMMARY, paperByline, rangeLabel, reportIntro } from "./researchReport";

// Word·PDF 가 같은 모델에서 그려진다 — 인용 번호·참고문헌·부록이 두 형식에서 어긋나지 않게

export type ReportExportFormat = "docx" | "pdf";

export interface DocTrailItem {
  subquestion: string;
  queries: string[];
  verdict: Verdict | null;
  evidenceCount: number | null;
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
    if (items.length) out.push({ type: "bullets", items });
  });
  return out;
}

// 재검색은 근거가 부족하다고 판정했을 때만 일어난다 — 검색어가 바뀐 흐름이 곧 자기점검의 기록이다
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
```

**확인.** `reportDocument.test.ts`(21건) — 블록 순서, 번호 매김(첫 등장 순·같은 근거 같은 번호·미인용 제외), 참고문헌 한 줄과 빠진 칸, 인용 쪽(1부터·정렬·중복 제거·쪽 정보 없음 제외), 초안 표시·한계 대체 문구, 도입 없는 절·한계 없음 문구, 부록과 모르는 칸, 제어문자 제거, 파일 이름(금지 문자·20자·초안 접미·한국 날짜·빈 이름).

### 2.49 `utils/menuNav.ts` · `components/research/ReportDownloadMenu.vue` — 내려받기 메뉴

**책임.** [다운로드 ▾](완성 보고서 머리)·[초안 저장 ▾](현황 카드·멈춘 초안) 버튼과 메뉴 "Word 문서(.docx)"·"PDF로 저장". 키보드는 `+` 메뉴([02](02-주소-복원-진입.md) §2.21)와 같은 규칙(`menuStep`).

**왜 이렇게 짰나.**

- **`disabled` 대신 `aria-disabled`.** 고른 직후 만드는 중(`busy`)으로 바뀔 때 초점을 쥔 버튼이 비활성이 되면 초점이 body 로 떨어진다(키보드 사용자가 제자리를 잃는다). 화면은 알리기만 하고 `inactive` 면 열지 않는다.
- **만드는 중에는 흐리지 않는다**(`a0d731c`, §14 다듬기). 처음엔 만드는 중에도 `aria-disabled` 스타일(opacity 0.5)이 걸려 '만드는 중…' 글자와 숨 쉬는 점이 "누를 수 없음"처럼 묻혔다. 흐림과 `not-allowed` 커서는 내려받을 내용이 없을 때(`aria-busy` 가 아닐 때)만 건다.
- **WAI-ARIA 메뉴 버튼 관례.** 열면 첫 항목(위 방향키로 열면 마지막 항목)에 초점, 항목 사이는 방향키·Home·End, Tab 은 메뉴를 닫고 다음 요소로(버튼으로 초점을 돌려 둔 뒤 기본 동작이 앞뒤로 옮긴다), 버튼에 초점이 있어도 Esc 로 닫는다(묶음 전체에서 듣는다).
- **[초안 저장]은 끝난 절이 하나 이상일 때만 누를 수 있다**(페이지가 `disabled` 를 준다).

**파일**: `frontend/utils/menuNav.ts` — 전체 18줄

```ts
// frontend/utils/menuNav.ts
// role="menu" 의 키보드 관례(WAI-ARIA 메뉴 버튼): 방향키로 항목 사이를 돌고 Home·End 로 끝으로 간다.
// 움직일 키가 아니면 null — 화면은 그 키의 기본 동작을 막지 않는다.
export function menuStep(current: number, key: string, count: number): number | null {
  if (count <= 0) return null;
  switch (key) {
    case "ArrowDown":
      return current < 0 ? 0 : (current + 1) % count;
    case "ArrowUp":
      return current < 0 ? count - 1 : (current - 1 + count) % count;
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return null;
  }
}
```

**파일**: `frontend/components/research/ReportDownloadMenu.vue` — 전체 127줄

```vue
<!-- frontend/components/research/ReportDownloadMenu.vue -->
<template>
  <div ref="root" class="rs-dl" @keydown="onRootKeydown">
    <!-- disabled 대신 aria-disabled: 고른 직후 만드는 중(busy)으로 바뀔 때 초점을 쥔 버튼이 비활성이 되면
         초점이 body 로 떨어진다(키보드 사용자가 제자리를 잃는다) -->
    <button
      ref="trigger"
      type="button"
      class="rs-btn rs-btn--ghost rs-btn--small rs-dl__btn"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-controls="open ? menuId : undefined"
      :aria-disabled="inactive"
      :aria-busy="busy"
      :title="disabled ? '아직 내려받을 내용이 없습니다' : undefined"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <span v-if="busy" class="rs-dl__dot" aria-hidden="true" />
      {{ busy ? "만드는 중…" : `${label} ▾` }}
    </button>
    <ul v-if="open" :id="menuId" ref="menu" class="rs-dl__menu" role="menu" :aria-label="label" @keydown="onMenuKeydown">
      <li v-for="f in FORMATS" :key="f.id" role="none">
        <!-- tabindex=-1: 항목 사이는 방향키로 옮긴다. Tab 은 메뉴를 닫고 다음 요소로 간다 -->
        <button type="button" role="menuitem" tabindex="-1" class="rs-dl__item" @click="choose(f.id)">
          <span class="rs-dl__label">{{ f.label }}</span>
          <span class="rs-dl__desc">{{ f.description }}</span>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import { menuStep } from "~/utils/menuNav";
import type { ReportExportFormat } from "~/utils/reportDocument";

const props = withDefaults(defineProps<{ label: string; disabled?: boolean; busy?: boolean }>(), {
  disabled: false,
  busy: false,
});
const emit = defineEmits<{ select: [format: ReportExportFormat] }>();

const FORMATS: readonly { id: ReportExportFormat; label: string; description: string }[] = [
  { id: "docx", label: "Word 문서(.docx)", description: "고쳐 쓰기 좋고 한글에서도 열립니다" },
  { id: "pdf", label: "PDF로 저장", description: "인쇄 창에서 대상을 ‘PDF로 저장’으로 고릅니다" },
];

const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const menuId = useId();
const open = ref(false);
const inactive = computed(() => props.disabled || props.busy);

watch(inactive, (value) => {
  if (value) open.value = false;
});

function items(): HTMLElement[] {
  return Array.from(menu.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
}

function focusItem(key: string): boolean {
  const list = items();
  const at = list.findIndex((el) => el === document.activeElement);
  const next = menuStep(at, key, list.length);
  if (next === null) return false;
  list[next]?.focus();
  return true;
}

// 열면 첫 항목(위 방향키로 열면 마지막 항목)으로 초점을 옮긴다 — 방향키·Esc 가 메뉴 안에서 먹게
async function openMenu(key: "ArrowDown" | "ArrowUp" = "ArrowDown"): Promise<void> {
  if (inactive.value) return;
  open.value = true;
  await nextTick();
  focusItem(key);
}

function closeMenu(returnFocus: boolean): void {
  open.value = false;
  if (returnFocus) trigger.value?.focus();
}

function toggle(): void {
  if (open.value) closeMenu(false);
  else void openMenu();
}

function onTriggerKeydown(e: KeyboardEvent): void {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  e.preventDefault();
  if (open.value) focusItem(e.key === "ArrowUp" ? "End" : "Home");
  else void openMenu(e.key);
}

function onMenuKeydown(e: KeyboardEvent): void {
  // Tab 은 막지 않는다 — 버튼으로 초점을 돌려 둔 뒤 기본 동작이 그 앞뒤 요소로 옮긴다
  if (e.key === "Tab") {
    closeMenu(true);
    return;
  }
  if (focusItem(e.key)) e.preventDefault();
}

// 버튼에 초점이 있어도(마우스로 연 뒤) Esc 로 닫히게 묶음 전체에서 듣는다
function onRootKeydown(e: KeyboardEvent): void {
  if (e.key !== "Escape" || !open.value) return;
  e.preventDefault();
  e.stopPropagation();
  closeMenu(true);
}

function choose(format: ReportExportFormat): void {
  closeMenu(true);
  emit("select", format);
}

function onDocumentClick(e: MouseEvent): void {
  if (open.value && root.value && e.target instanceof Node && !root.value.contains(e.target)) open.value = false;
}

onMounted(() => document.addEventListener("click", onDocumentClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));
</script>
```

**확인.** `menuNav.test.ts`(4건).

### 2.50 `utils/reportDocx.ts` — Word 구성

**책임.** 문서 모델을 `docx`(npm, 9.x)로 A4·맑은 고딕·바닥글 쪽 번호의 `.docx` 로 만든다(`toDocxBlob`). 내려받기 링크 헬퍼(`downloadBlob`).

**왜 이렇게 짰나.**

- **`docx` 는 내려받기를 누를 때 동적 import 한다.** 1MB 가 넘는다 — 평소 화면 번들에 넣지 않는다(spec §14-9 의 번들 위험). 의존성 추가는 이것 하나다. 구성 함수는 그때 받은 모듈을 인자로 쓴다 — 값으로 import 하면 정적 번들에 들어간다(`ab43e0a` 가 이 까닭을 주석에 바로 적었다). §14 계획의 검토 드라이런은 `npm run build` 에서 docx 가 별도 청크 1개(436K)이고 딥리서치 페이지 청크만 그것을 부르는 것을 확인했다.
- **단위.** 글자 크기는 반 포인트(`pt(10.5)` → 21), 용지·여백은 twip(1/1440인치) — A4 `11906 × 16838`, 여백 2cm `1134`.
- **제목·절 제목·소제목·본문 크기를 스타일로 나눈다.** 문단마다 크기를 주지 않고 `styles.default` 의 `title`·`heading1`·`heading2`·`document` 로 두고, 제목 문단은 `HeadingLevel` 로 단다 — Word 의 제목 스타일이라 탐색 창에도 절 제목이 잡힌다.
- **인용 번호는 본문과 같은 줄의 `[n]`**(spec §14-4). 참고문헌의 `[n]` 과 그대로 이어 읽힌다.
- **참고문헌은 내어쓰기.** 번호로 찾아 읽는 목록이라 번호가 긴 줄 앞으로 튀어나오게 둔다.
- **`xmlSafe` 를 한 번 더.** 모델이 이미 거르지만 손으로 만든 `ReportDoc` 도 열리는 파일이 되도록 XML 에 쓰는 자리(모든 `TextRun`·문서 제목)에서 한 번 더 막는다.
- **내려받기 링크는 문서에 붙였다 뗀다.** 문서에 붙지 않은 링크의 click 을 무시하는 브라우저가 있다. 객체 URL 은 1초 뒤 해제한다 — 곧바로 해제하면 내려받기가 시작되기 전에 주소가 사라지는 브라우저가 있다.

**파일**: `frontend/utils/reportDocx.ts` — 전체 118줄

```ts
// frontend/utils/reportDocx.ts
import type { Document as DocxDocument, Paragraph } from "docx";
import { docRunText, xmlSafe, type DocBlock, type DocRun, type ReportDoc } from "./reportDocument";

// docx 는 1MB 가 넘는다 — 화면 번들에 넣지 않고 내려받기를 누를 때 받는다(동적 import).
// 구성 함수는 그때 받은 모듈을 인자로 쓴다 — 값으로 import 하면 정적 번들에 들어간다
type DocxModule = typeof import("docx");

const FONT = "맑은 고딕";
const MUTED = "666666";
// A4(210×297mm)와 여백 2cm — 단위는 twip(1/1440인치)
const A4 = { width: 11906, height: 16838 };
const MARGIN = 1134;

// docx 의 글자 크기는 반 포인트 단위다
function pt(n: number): number {
  return Math.round(n * 2);
}

function buildDocxDocument(docx: DocxModule, doc: ReportDoc): DocxDocument {
  const { AlignmentType, Document, Footer, HeadingLevel, PageNumber, Paragraph, TextRun } = docx;

  // docx 는 &<>"' 만 이스케이프하고 제어문자는 <w:t> 에 그대로 쓴다. 모델이 이미 거르지만
  // 손으로 만든 ReportDoc 도 열리는 파일이 되도록 XML 에 쓰는 자리에서 한 번 더 막는다
  const run = (text: string, opts: { size?: number; color?: string } = {}) =>
    new TextRun({ ...opts, text: xmlSafe(text) });

  const runsOf = (runs: DocRun[], muted = false) =>
    runs.map((r) => run(docRunText(r), { color: muted ? MUTED : undefined }));

  function paragraphs(block: DocBlock): Paragraph[] {
    switch (block.type) {
      case "title":
        return [new Paragraph({ heading: HeadingLevel.TITLE, children: [run(block.text)] })];
      case "meta":
        return [new Paragraph({ children: [run(block.text, { size: pt(9), color: MUTED })] })];
      case "heading":
        return [
          new Paragraph({
            heading: block.level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
            children: [run(block.text)],
          }),
        ];
      case "para":
        return [new Paragraph({ children: runsOf(block.runs, block.muted), spacing: { after: 120 } })];
      case "bullets":
        return block.items.map((runs) => new Paragraph({ bullet: { level: 0 }, children: runsOf(runs) }));
    }
  }

  // 참고문헌은 번호가 긴 줄 앞으로 튀어나오게(내어쓰기) 둔다 — 번호로 찾아 읽는 목록이다
  const references = doc.references.length
    ? [
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("참고문헌")] }),
        ...doc.references.map(
          (r) =>
            new Paragraph({
              children: [run(`[${r.n}] ${r.text}`)],
              indent: { left: 440, hanging: 440 },
              spacing: { after: 80 },
            }),
        ),
      ]
    : [];

  return new Document({
    creator: "NL-Lib 딥리서치",
    title: xmlSafe(doc.fileName.replace(/\.docx$/i, "")),
    styles: {
      default: {
        document: { run: { font: FONT, size: pt(10.5) }, paragraph: { spacing: { line: 312 } } },
        title: { run: { font: FONT, size: pt(18), bold: true, color: "000000" }, paragraph: { spacing: { after: 160 } } },
        heading1: {
          run: { font: FONT, size: pt(14), bold: true, color: "000000" },
          paragraph: { spacing: { before: 360, after: 120 } },
        },
        heading2: {
          run: { font: FONT, size: pt(12), bold: true, color: "333333" },
          paragraph: { spacing: { before: 200, after: 80 } },
        },
      },
    },
    sections: [
      {
        properties: { page: { size: A4, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } } },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ children: [PageNumber.CURRENT], size: pt(9), color: MUTED })],
              }),
            ],
          }),
        },
        children: [...doc.blocks.flatMap(paragraphs), ...references],
      },
    ],
  });
}

export async function toDocxBlob(doc: ReportDoc): Promise<Blob> {
  const docx = await import("docx");
  return docx.Packer.toBlob(buildDocxDocument(docx, doc));
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  // 문서에 붙지 않은 링크의 click 을 무시하는 브라우저가 있다
  document.body.appendChild(a);
  a.click();
  a.remove();
  // 곧바로 해제하면 내려받기가 시작되기 전에 주소가 사라지는 브라우저가 있다
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
```

### 2.51 `composables/useReportExport.ts` — 내보내기 상태와 인쇄 수명

**책임.** `exportDocx(doc)` — Blob 을 만들어 내려받는다. `printPdf(doc)` — 인쇄 전용 문서를 그리고 `window.print()` 를 부른 뒤 되돌린다. 둘 다 `exporting` 으로 겹쳐 누르기를 막는다.

**왜 이렇게 짰나.**

- **인쇄하는 동안 `document.title` 을 파일 이름으로 바꾼다.** 인쇄 창의 "PDF로 저장"은 문서 제목을 기본 파일 이름으로 쓴다.
- **되돌리기는 `print()` 가 돌아온 뒤 `finally` 에서 한다**(`f5e484c` → `de8efe3`). 데스크톱 Chrome·Edge·Firefox 는 인쇄 창이 닫힐 때까지 `print()` 가 막혀 있다가 돌아온다는 전제다(코드 주석·spec §14-4). 처음엔 `afterprint` 이벤트로 되돌렸는데, 인쇄를 정책으로 막았거나 인앱 브라우저(카카오톡 등)처럼 `print()` 가 창 없이 곧바로 돌아오고 `afterprint` 를 쏘지 않는 곳에서는 `exporting` 이 참으로 남아 **모든 내려받기 메뉴가 '만드는 중…'에 멈추고** 탭 제목·숨은 인쇄 문서도 남았다. `finally` 로 옮긴 뒤에는 `afterprint` 리스너·가드가 결과를 바꾸지 못하는 코드가 돼 걷었다. 막히지 않고 인쇄 모양을 나중에 뜨는 브라우저(iOS Safari 등)에서는 화면이 찍힐 수 있다 — 대상 밖(spec §14-4, 대상은 Chrome·Edge).
- **문서 모델은 `shallowRef`.** 한 번 만들고 바꾸지 않는다 — 깊은 반응형으로 감쌀 까닭이 없다.

**파일**: `frontend/composables/useReportExport.ts` — 전체 43줄

```ts
// frontend/composables/useReportExport.ts
import { nextTick, ref, shallowRef } from "vue";
import type { ReportDoc } from "~/utils/reportDocument";
import { downloadBlob, toDocxBlob } from "~/utils/reportDocx";

export function useReportExport() {
  const exporting = ref(false);
  // 문서 모델은 한 번 만들고 바꾸지 않는다 — 깊은 반응형으로 감쌀 까닭이 없다
  const printDoc = shallowRef<ReportDoc | null>(null);

  async function exportDocx(doc: ReportDoc): Promise<void> {
    if (exporting.value) return;
    exporting.value = true;
    try {
      downloadBlob(await toDocxBlob(doc), doc.fileName);
    } finally {
      exporting.value = false;
    }
  }

  async function printPdf(doc: ReportDoc): Promise<void> {
    if (exporting.value) return;
    exporting.value = true;
    const previousTitle = document.title;
    try {
      printDoc.value = doc;
      // 인쇄 전용 문서가 DOM 에 그려진 뒤에 인쇄 창을 연다
      await nextTick();
      // 인쇄 창의 "PDF로 저장"은 문서 제목을 기본 파일 이름으로 쓴다
      document.title = doc.fileName.replace(/\.docx$/i, "");
      window.print();
    } finally {
      // Chrome·Firefox 데스크톱은 print() 가 인쇄 창이 닫힐 때까지 막혀 있다가 돌아온다는 전제로, 돌아오면 되돌린다.
      // afterprint 는 기다리지 않는다 — 정책으로 인쇄를 막았거나 인앱 브라우저처럼 창 없이 곧바로 돌아오는 곳은 이 이벤트를
      // 쏘지 않아 버튼이 '만드는 중…'에 멈춘다. 막히지 않고 인쇄할 모양을 나중에 뜨는 브라우저라면 화면이 찍힌다
      document.title = previousTitle;
      printDoc.value = null;
      exporting.value = false;
    }
  }

  return { exporting, printDoc, exportDocx, printPdf };
}
```

**확인.** `useReportExport.test.ts`(2건) — `window`·`document` 를 흉내 내 `print()` 가 `afterprint` 없이 돌아오거나 던져도 제목·인쇄 문서·만드는 중 표시가 되돌아가는지.

### 2.52 `components/research/ReportPrint.vue` — 인쇄 전용 화면

**책임.** 같은 문서 모델을 인쇄용 HTML 로 그린다. 화면에서는 숨기고 [PDF로 저장]을 누른 동안에만 붙는다.

**왜 이렇게 짰나.** `Teleport to="body"` 로 body 바로 아래에 붙인다 — 인쇄 CSS 가 body 의 다른 자식(앱 전체·토스트·원문 뷰어)을 한 번에 숨기고 이것만 찍는다(§2.53). 글은 텍스트 보간만 쓴다(`v-html` 없음, D9).

**파일**: `frontend/components/research/ReportPrint.vue` — 전체 36줄

```vue
<!-- frontend/components/research/ReportPrint.vue -->
<template>
  <!-- body 바로 아래에 붙인다 — 인쇄 CSS 가 body 의 다른 자식(앱 전체)을 한 번에 숨기고 이것만 찍는다 -->
  <Teleport to="body">
    <article class="rs-print">
      <template v-for="(block, bi) in doc.blocks" :key="bi">
        <h1 v-if="block.type === 'title'" class="rs-print__title">{{ block.text }}</h1>
        <p v-else-if="block.type === 'meta'" class="rs-print__meta">{{ block.text }}</p>
        <h2 v-else-if="block.type === 'heading' && block.level === 1" class="rs-print__h1">{{ block.text }}</h2>
        <h3 v-else-if="block.type === 'heading'" class="rs-print__h2">{{ block.text }}</h3>
        <p v-else-if="block.type === 'para'" class="rs-print__para" :class="{ 'is-muted': block.muted }">
          {{ runsText(block.runs) }}
        </p>
        <ul v-else-if="block.type === 'bullets'" class="rs-print__list">
          <li v-for="(runs, ii) in block.items" :key="ii">{{ runsText(runs) }}</li>
        </ul>
      </template>
      <template v-if="doc.references.length">
        <h2 class="rs-print__h1">참고문헌</h2>
        <ol class="rs-print__refs">
          <li v-for="r in doc.references" :key="r.n">[{{ r.n }}] {{ r.text }}</li>
        </ol>
      </template>
    </article>
  </Teleport>
</template>

<script setup lang="ts">
import { docRunText, type DocRun, type ReportDoc } from "~/utils/reportDocument";

defineProps<{ doc: ReportDoc }>();

function runsText(runs: DocRun[]): string {
  return runs.map(docRunText).join("");
}
</script>
```

### 2.53 `assets/css/research.css` 인쇄 절 — A4 와 숨기기

**책임.** `@media print` 에서 인쇄 전용 문서만, 또는 딥리서치 화면을 그대로 인쇄(Ctrl+P)할 때 사이드바·머리·버튼·진행 패널을 뺀 본문만 찍는다.

**왜 이렇게 짰나.**

- **이름 붙은 `@page rs-report`**(`1243044`, §14 Task 10 품질 검토). 처음엔 A4·18/16mm 여백을 이름 없는 `@page` 로 두었다. 이 파일은 모든 페이지에 실리므로(`nuxt.config.ts` 의 전역 CSS) 논문 검색 등 **모든 페이지의 인쇄에 걸리고** Chrome 인쇄 창의 가로/세로 선택까지 숨겼다. 이름 없는 `@page` 는 선택자로 좁힐 수 없어, 이름 붙은 페이지로 두고 인쇄 전용 문서(`.rs-print`)와 딥리서치 화면(`.skx-app:has(.rs-page)`)에만 `page: rs-report` 를 준다. `page` 속성을 모르는 브라우저는 기본 여백으로 찍힌다.
- **`body:has(> .rs-print) > :not(.rs-print)` 로 나머지를 숨긴다.** [PDF로 저장] 중에만 맞는 선택자다.
- **딥리서치 화면 인쇄는 2단 격자를 푼다.** 진행 패널을 뺀 자리에 빈 칸이 남지 않게 본문이 용지 폭을 다 쓴다.
- **제목 뒤에서 끊지 않고(`break-after: avoid`), 목록 항목 안에서 끊지 않는다(`break-inside: avoid`).** 참고문헌은 Word 와 같이 내어쓰기.

**파일**: `frontend/assets/css/research.css` — 1153~1244행 발췌(전체 1244줄)

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
/* 인쇄 전용 문서는 화면에 그리지 않는다 — [PDF로 저장]을 누른 동안에만 body 에 붙는다 */
.rs-print {
  display: none;
}
@media print {
  /* 이름 없는 @page 는 선택자로 좁힐 수 없어 모든 페이지의 인쇄에 걸린다(이 파일은 모든 페이지에 실린다).
     그래서 이름 붙은 페이지로 두고 인쇄 전용 문서와 딥리서치 화면에만 준다 — 다른 페이지는 브라우저 기본값
     (용지·여백·가로/세로 선택)을 그대로 쓰고, page 속성을 모르는 브라우저는 기본 여백으로 찍힌다 */
  @page rs-report {
    size: A4;
    margin: 18mm 16mm;
  }
  .rs-print,
  .skx-app:has(.rs-page) {
    page: rs-report;
  }
  /* [PDF로 저장] 중에는 인쇄 전용 문서만 찍는다 — body 의 다른 자식(앱·토스트·원문 뷰어)은 숨긴다 */
  body:has(> .rs-print) > :not(.rs-print) {
    display: none !important;
  }
  /* 딥리서치 화면을 그대로 인쇄(Ctrl+P)해도 사이드바·머리·버튼·진행 패널은 뺀다.
     이 파일은 모든 페이지에 실리므로 다른 화면의 인쇄에는 걸리지 않게 딥리서치 화면으로 좁힌다 */
  .skx-app:has(.rs-page) .skx-lnb,
  body:has(.rs-page) .skx-footer,
  .rs-page .rs-head,
  .rs-page .rs-col-side,
  .rs-page .rs-dl,
  .rs-page .rs-btn {
    display: none !important;
  }
  /* 진행 패널을 뺀 자리에 빈 칸이 남지 않게 배치 A 의 2단 격자를 푼다 — 본문이 용지 폭을 다 쓴다 */
  .rs-page .rs-body {
    display: block;
  }
  .rs-print {
    display: block;
    font-family: "맑은 고딕", "Malgun Gothic", "Pretendard", sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: var(--skx-ink);
  }
  .rs-print__title {
    margin: 0 0 6pt;
    font-size: 18pt;
    font-weight: 700;
    line-height: 1.35;
  }
  .rs-print__meta {
    margin: 0;
    font-size: 9pt;
    color: var(--skx-gray-1);
    word-break: break-all;
  }
  .rs-print__h1 {
    margin: 18pt 0 6pt;
    font-size: 14pt;
    font-weight: 700;
    break-after: avoid;
  }
  .rs-print__h2 {
    margin: 10pt 0 4pt;
    font-size: 12pt;
    font-weight: 700;
    break-after: avoid;
  }
  .rs-print__para {
    margin: 0 0 6pt;
  }
  .rs-print__para.is-muted {
    color: var(--skx-gray-1);
  }
  .rs-print__list {
    margin: 0 0 6pt;
    padding-left: 16pt;
  }
  .rs-print__refs {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .rs-print__list li,
  .rs-print__refs li {
    margin-bottom: 3pt;
    break-inside: avoid;
  }
  /* 번호로 찾아 읽는 목록이라 둘째 줄부터 들여 번호가 튀어나오게 한다 */
  .rs-print__refs li {
    padding-left: 22pt;
    text-indent: -22pt;
  }
}
```

### 2.54 `tests/unit/reportDocx.test.ts` — 실제 파일을 풀어 보는 Word 테스트

**책임.** Node 에서 실제로 `.docx` 를 만들고 압축을 풀어 `word/document.xml`·`styles.xml`·바닥글을 본다(spec §14-6).

**왜 이렇게 짰나.**

- **`jszip` 은 `docx` 가 끌어오는 의존성이다** — 압축을 풀어 보려고 새 패키지를 들이지 않는다.
- **내려받기가 쓰는 Blob 을 그대로 푼다**(`ab43e0a`). 처음엔 테스트만 쓰는 `toDocxBuffer`(`Packer.toArrayBuffer`)를 지나 실제 내려받기의 `toDocxBlob` 은 시험되지 않았다. Node 에도 `Blob` 이 있어 브라우저와 같은 경로를 지난다.
- **본문 인용 번호는 참고문헌 앞 구간의 문단 런 순서로 본다**(`c4ebc34`, §14 Task 9 품질 검토). 참고문헌 줄도 `[1]`·`[2]` 로 시작해서, "XML 에 `[1]` 이 있다"만 보면 본문 인용이 빠져도 통과한다.
- **제어문자 테스트의 입력에 U+FFFE·U+FFFF 를 넣는다**(`edeb5ad`) — 정규식에서 빠지면 테스트가 잡는다.

**파일**: `frontend/tests/unit/reportDocx.test.ts` — 전체 94줄

```ts
// frontend/tests/unit/reportDocx.test.ts
// jszip 은 docx 가 끌어오는 의존성이다 — 압축을 풀어 보려고 새 패키지를 들이지 않는다
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import type { ReportDoc } from "~/utils/reportDocument";
import { toDocxBlob } from "~/utils/reportDocx";

const doc: ReportDoc = {
  fileName: "딥리서치_국내_AI_규제_연구_동향_20260928.docx",
  blocks: [
    { type: "title", text: "국내 AI 규제 연구 동향" },
    { type: "meta", text: "생성 일시 2026년 9월 28일 15:05" },
    { type: "heading", level: 1, text: "1. 규제 논의의 흐름" },
    { type: "para", runs: [{ text: "규제 논의가 늘었다 " }, { cite: 1 }, { text: "." }] },
    { type: "heading", level: 2, text: "향후 과제" },
    { type: "bullets", items: [[{ text: "국제 비교가 필요하다 " }, { cite: 2 }]] },
    { type: "para", runs: [{ text: "자동 점검에서 보고할 한계가 발견되지 않았습니다." }], muted: true },
  ],
  references: [
    { n: 1, eid: "E1", text: "김철수 (2019). AI 윤리 교육." },
    { n: 2, eid: "E2", text: "이영희 (2021). 규제 샌드박스." },
  ],
};

async function unzip(target: ReportDoc): Promise<JSZip> {
  // 내려받기가 쓰는 Blob 을 그대로 푼다 — Node 에도 Blob 이 있어 브라우저와 같은 경로를 지난다
  return JSZip.loadAsync(await (await toDocxBlob(target)).arrayBuffer());
}

async function read(zip: JSZip, path: string): Promise<string> {
  return (await zip.file(path)?.async("string")) ?? "";
}

// 글이 든 첫 문단(<w:p>…</w:p>)과 그 안의 런 글자를 순서대로 본다
function paragraphWith(xml: string, text: string): string {
  return (xml.match(/<w:p[ >][\s\S]*?<\/w:p>/g) ?? []).find((p) => p.includes(text)) ?? "";
}

function runTexts(paragraph: string): string[] {
  return [...paragraph.matchAll(/<w:t[^>]*>([^<]*)<\/w:t>/g)].map((m) => m[1] ?? "");
}

describe("toDocxBlob", () => {
  it("본문 문단·글머리표의 글 조각 사이에 인용 번호를 잇고 참고문헌을 뒤에 싣는다", async () => {
    const xml = await read(await unzip(doc), "word/document.xml");
    expect(xml).toContain("국내 AI 규제 연구 동향");
    expect(xml).toContain("참고문헌");
    expect(xml).toContain("[1] 김철수 (2019). AI 윤리 교육.");
    // 참고문헌 줄도 [1]·[2] 로 시작한다 — 본문 인용은 참고문헌 앞 구간의 문단 안 런 순서로 본다
    const body = xml.slice(0, xml.indexOf("참고문헌"));
    expect(runTexts(paragraphWith(body, "규제 논의가 늘었다"))).toEqual(["규제 논의가 늘었다 ", "[1]", "."]);
    const bullet = paragraphWith(body, "국제 비교가 필요하다");
    expect(bullet).toContain("<w:numPr>");
    expect(runTexts(bullet)).toEqual(["국제 비교가 필요하다 ", "[2]"]);
  });

  it("A4 용지·맑은 고딕으로 만들고 흐린 문단만 회색으로, 바닥글에 쪽 번호를 단다", async () => {
    const zip = await unzip(doc);
    const xml = await read(zip, "word/document.xml");
    expect(xml).toMatch(/<w:pgSz [^>]*w:w="11906"[^>]*w:h="16838"/);
    expect(paragraphWith(xml, "보고할 한계가 발견되지")).toContain('<w:color w:val="666666"/>');
    expect(paragraphWith(xml, "규제 논의가 늘었다")).not.toContain("<w:color");
    expect(await read(zip, "word/styles.xml")).toContain('w:eastAsia="맑은 고딕"');
    const footer = Object.keys(zip.files).find((name) => /^word\/footer\d+\.xml$/.test(name));
    expect(footer).toBeDefined();
    expect(await read(zip, footer ?? "")).toContain("PAGE");
  });

  it("인용한 근거가 없으면 참고문헌 제목을 싣지 않는다", async () => {
    const xml = await read(await unzip({ ...doc, references: [] }), "word/document.xml");
    expect(xml).not.toContain("참고문헌");
  });

  // 합성 출력의 JSON 을 풀면 LLM 이 쓴 LaTeX(\frac·\beta)가 이스케이프 \f·\b 로 풀려 이런 글자가 된다
  it("XML 에 쓸 수 없는 제어문자는 어느 자리에서도 빼고 쓴다 — Word 가 열지 못하는 파일이 되지 않게", async () => {
    const dirty: ReportDoc = {
      ...doc,
      blocks: [
        { type: "title", text: "국내\u0001 AI 규제" },
        { type: "meta", text: "생성 일시\u000B 2026\uFFFE년\uFFFF" },
        { type: "heading", level: 1, text: "1. 계수\u001F 추정" },
        { type: "para", runs: [{ text: "분수 \u000Crac 와 \u0008eta 계수 " }, { cite: 1 }] },
        { type: "bullets", items: [[{ text: "과제\u0000 하나" }]] },
      ],
      references: [{ n: 1, eid: "E1", text: "김철수 (2019).\u000E 추정." }],
    };
    const xml = await read(await unzip(dirty), "word/document.xml");
    expect(xml).not.toMatch(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/);
    expect(runTexts(paragraphWith(xml, "분수"))).toEqual(["분수 rac 와 eta 계수 ", "[1]"]);
    for (const text of ["국내 AI 규제", "생성 일시 2026년", "1. 계수 추정", "과제 하나", "[1] 김철수 (2019). 추정."]) {
      expect(xml).toContain(text);
    }
  });
});
```

**확인.** `reportDocx.test.ts`(4건).

```bash
$ cd frontend && npx vitest run tests/unit/reportDocument.test.ts tests/unit/reportDocx.test.ts tests/unit/useReportExport.test.ts tests/unit/menuNav.test.ts
# 2026-10-01, d845b8b 사본: 4파일 31 tests passed (21+4+2+4)
```

운영 확인(2026-09-29, 사용자): 완성 보고서의 Word·PDF 둘 다 정상으로 내려받아졌다. Word 파일을 한글(HWP)에서 연 결과는 기록이 없다.
