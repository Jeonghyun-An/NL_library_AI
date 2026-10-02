// frontend/utils/pdfViewer.ts
import type { OpenPdfPayload, PdfPassage, ReportChunk } from "~/types/research";
import { pageLabel, pdfPage } from "./citations";

// 원문 뷰어(public/pdfjs — pdf.js 4.0.379 고정)의 앱 객체 중 머리의 쪽 표시와 Esc 판단에 쓰는 부분만 적는다
export interface PdfJsApp {
  readonly initializedPromise: Promise<void>;
  page: number;
  readonly pagesCount: number;
  readonly eventBus: { on(name: string, listener: (evt: { pageNumber: number }) => void): void };
  readonly findBar?: { opened: boolean };
  readonly secondaryToolbar?: { isOpen: boolean };
  readonly overlayManager?: { active: unknown };
}

// 뷰어는 같은 출처(/pdfjs/web/viewer.html)라 iframe 창의 앱 객체를 바로 읽는다. 없으면(로드 전·내부 API 변경) null
export function pdfJsApp(win: Window | null): PdfJsApp | null {
  return (win as (Window & { PDFViewerApplication?: PdfJsApp }) | null)?.PDFViewerApplication ?? null;
}

// 찾기 막대·보조 도구 줄·pdf.js 대화상자가 열려 있으면 Esc 는 그것부터 닫는다(pdf.js 동작) —
// 이때 뷰어까지 닫으면 한 번 눌러 둘이 닫힌다
export function viewerOwnsEscape(app: PdfJsApp | null): boolean {
  return !!(app?.findBar?.opened || app?.secondaryToolbar?.isOpen || app?.overlayManager?.active);
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

// 원문 보기 전 확인 요청의 HTTP 상태. 요청 자체가 실패하면 null(pdfCheckProblem 이 판단을 뷰어에 맡긴다)
export async function pdfStatus(
  url: string,
  headers: Record<string, string>,
  fetchFn: typeof fetch = fetch,
): Promise<number | null> {
  const ctrl = new AbortController();
  try {
    const res = await fetchFn(url, { headers, signal: ctrl.signal });
    return res.status;
  } catch {
    return null;
  } finally {
    // 본문은 필요 없다 — 뷰어가 다시 받는다. 끊지 않으면 PDF 전체를 두 번 내려받는다
    ctrl.abort();
  }
}
