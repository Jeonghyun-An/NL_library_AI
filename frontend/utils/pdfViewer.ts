// frontend/utils/pdfViewer.ts
import type { OpenPdfPayload, PdfPassage, ReportChunk } from "~/types/research";
import { pageLabel, pdfPage } from "./citations";

// 원문 뷰어(public/pdfjs — pdf.js 4.0.379 고정)의 앱 객체 중 머리의 쪽 표시와 Esc 판단에 쓰는 부분만 적는다
export interface PdfJsApp {
  readonly initializedPromise: Promise<void>;
  page: number;
  readonly pagesCount: number;
  readonly eventBus: {
    on(name: "pagechanging", listener: (evt: { pageNumber: number }) => void): void;
    on(name: "pagesinit", listener: () => void): void;
  };
  readonly pdfViewer?: { annotationEditorMode: number };
  readonly findBar?: { opened: boolean };
  readonly secondaryToolbar?: { isOpen: boolean };
  readonly overlayManager?: { active: unknown };
}

// 뷰어는 같은 출처(/pdfjs/web/viewer.html)라 iframe 창의 앱 객체를 바로 읽는다. 없으면(로드 전·내부 API 변경) null
export function pdfJsApp(win: Window | null): PdfJsApp | null {
  return (win as (Window & { PDFViewerApplication?: PdfJsApp }) | null)?.PDFViewerApplication ?? null;
}

// 뷰어의 설정 객체(PDFViewerApplicationOptions = AppOptions) 중 실행 전에 값을 바꾸는 부분만 적는다
export interface PdfJsOptions {
  set(name: string, value: unknown): void;
}

export function pdfJsOptions(win: Window | null): PdfJsOptions | null {
  return (win as (Window & { PDFViewerApplicationOptions?: PdfJsOptions }) | null)?.PDFViewerApplicationOptions ?? null;
}

// pdf.js LinkTarget.BLANK — 링크에 target="_blank"(rel 은 pdf.js 기본 noopener)를 단다
const LINK_TARGET_BLANK = 2;

// 뷰어가 SKOVIX 와 같은 출처라 PDF 가 스크립트를 돌리면 앱의 저장소·세션에 닿는다. pdf.js 4.2.67 전에는 글꼴 글리프를
// eval 로 컴파일해 조작한 글꼴이 임의 스크립트를 돌린다(CVE-2024-4367) — eval 을 끄면 같은 글리프를 해석해 그린다.
// 끼워 넣은 뷰어는 PDF 안의 외부 링크를 _top 으로 열어 SKOVIX 탭을 통째로 떠나므로 새 탭으로 연다.
// 링크 대상은 사용자 설정(preferences) 항목이라 run() 이 설정의 값(기본 0 → 끼워 넣으면 _top)으로 덮어쓴다 — 설정 읽기를 꺼야 남는다.
// 이 판의 뷰어는 설정을 쓰지 않고 설정 기본값도 앱 기본값과 같아, 끄더라도 다른 동작은 바뀌지 않는다
export function hardenPdfViewerOptions(options: PdfJsOptions): void {
  options.set("isEvalSupported", false);
  options.set("externalLinkTarget", LINK_TARGET_BLANK);
  options.set("disablePreferences", true);
}

// 찾기 막대·보조 도구 줄·pdf.js 대화상자가 열려 있으면 Esc 는 그것부터 닫는다(pdf.js 동작) —
// 이때 뷰어까지 닫으면 한 번 눌러 둘이 닫힌다. 주석 도구(글상자·펜 등)를 켠 동안에도 Esc 는 편집을 끝내는 키라
// pdf.js 에 맡긴다 — 그때 뷰어를 닫으려면 ✕ 를 누르거나 도구를 끈다. annotationEditorMode: -1 꺼짐(DISABLE), 0 도구 없음, 0 초과 도구 켜짐
export function viewerOwnsEscape(app: PdfJsApp | null): boolean {
  return !!(
    app?.findBar?.opened ||
    app?.secondaryToolbar?.isOpen ||
    app?.overlayManager?.active ||
    (app?.pdfViewer?.annotationEditorMode ?? 0) > 0
  );
}

// 쪽 정보가 없는 대목(page_start 0)도 빼지 않는다 — 배너의 "인용 대목 N곳"과 뷰어의 "n/N"이 같은 수를 센다
export function citedPassages(chunks: readonly Pick<ReportChunk, "page_start" | "page_end">[]): PdfPassage[] {
  return chunks.map((c) => ({ page: pdfPage(c) ?? null, label: pageLabel(c) }));
}

// 인용 대목으로 원문을 열 때의 뷰어 입력 — 첫 대목의 쪽에서 연다
export function citedPdfTarget(
  cntsId: string,
  title: string,
  chunks: readonly Pick<ReportChunk, "page_start" | "page_end">[],
): OpenPdfPayload {
  const passages = citedPassages(chunks);
  return { cntsId, title, page: passages[0]?.page ?? undefined, passages };
}

const FOCUSABLE =
  "button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex='-1'])";

// 뷰어를 닫을 때 초점을 돌려줄 곳. path 는 연 순간의 초점 요소부터 위로 올라간 조상들이다. 연 버튼이 그사이
// 사라졌으면(딥리서치 인용 팝오버는 초점이 뷰어로 옮겨 가면 닫히며 안의 [원문 보기]도 빠진다) 아직 문서에
// 남은 가장 가까운 조상 안의 첫 초점 요소 — 그 인용칩 — 로 돌려준다
export function focusReturnTarget(path: readonly HTMLElement[]): HTMLElement | null {
  const home = path.find((el) => el.isConnected);
  if (!home) return null;
  return home.matches(FOCUSABLE) ? home : home.querySelector<HTMLElement>(FOCUSABLE);
}

// 확인 요청이 멈추면(예: 백엔드가 객체 저장소를 기다리면) 확인 중에는 클릭을 무시하므로 원문 보기 버튼이 먹지 않는다 —
// 이만큼 지나면 포기하고 판단을 뷰어에 맡긴다
export const PDF_CHECK_TIMEOUT_MS = 10_000;

// 원문 보기 전 확인 요청의 HTTP 상태. 요청 자체가 실패하면 null(pdfCheckProblem 이 판단을 뷰어에 맡긴다)
export async function pdfStatus(
  url: string,
  headers: Record<string, string>,
  fetchFn: typeof fetch = fetch,
): Promise<number | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), PDF_CHECK_TIMEOUT_MS);
  try {
    const res = await fetchFn(url, { headers, signal: ctrl.signal });
    return res.status;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
    // 본문은 필요 없다 — 뷰어가 다시 받는다. 끊지 않으면 PDF 전체를 두 번 내려받는다
    ctrl.abort();
  }
}
