// frontend/tests/unit/pdfViewer.test.ts
import { describe, expect, it } from "vitest";
import {
  citedPassages,
  citedPdfTarget,
  focusReturnTarget,
  pdfJsApp,
  pdfStatus,
  viewerOwnsEscape,
  type PdfJsApp,
} from "~/utils/pdfViewer";

function app(over: Partial<PdfJsApp> = {}): PdfJsApp {
  return {
    initializedPromise: Promise.resolve(),
    page: 1,
    pagesCount: 10,
    eventBus: { on: () => {} },
    findBar: { opened: false },
    secondaryToolbar: { isOpen: false },
    overlayManager: { active: null },
    ...over,
  };
}

// Node 에는 DOM 이 없다 — 초점 되돌리기가 읽는 isConnected·matches·querySelector 만 흉내 낸다
function node(name: string, opts: { connected?: boolean; focusable?: boolean; inner?: HTMLElement } = {}): HTMLElement {
  return {
    name,
    isConnected: opts.connected ?? true,
    matches: () => opts.focusable ?? false,
    querySelector: () => opts.inner ?? null,
  } as unknown as HTMLElement;
}

describe("pdfJsApp", () => {
  it("iframe 창의 PDFViewerApplication 을 읽고, 없으면 null", () => {
    const a = app();
    expect(pdfJsApp({ PDFViewerApplication: a } as unknown as Window)).toBe(a);
    expect(pdfJsApp({} as Window)).toBeNull();
    expect(pdfJsApp(null)).toBeNull();
  });
});

describe("viewerOwnsEscape", () => {
  it("찾기 막대·보조 도구 줄·대화상자가 열려 있으면 Esc 를 pdf.js 에 맡긴다", () => {
    expect(viewerOwnsEscape(app({ findBar: { opened: true } }))).toBe(true);
    expect(viewerOwnsEscape(app({ secondaryToolbar: { isOpen: true } }))).toBe(true);
    expect(viewerOwnsEscape(app({ overlayManager: { active: {} } }))).toBe(true);
  });

  it("아무것도 열려 있지 않거나 앱을 못 읽으면 뷰어를 닫는다", () => {
    expect(viewerOwnsEscape(app())).toBe(false);
    expect(viewerOwnsEscape(null)).toBe(false);
  });
});

describe("citedPassages", () => {
  it("대목마다 pdf.js 쪽(1부터)과 쪽 표시를 만들고, 쪽 정보가 없는 대목도 센다", () => {
    expect(
      citedPassages([
        { page_start: 2, page_end: 3 },
        { page_start: 0, page_end: 0 },
        { page_start: 6, page_end: 6 },
      ]),
    ).toEqual([
      { page: 3, label: "p.3–4" },
      { page: null, label: "쪽 정보 없음" },
      { page: 7, label: "p.7" },
    ]);
  });
});

describe("citedPdfTarget", () => {
  it("첫 대목의 쪽에서 열고 대목 목록을 함께 넘긴다", () => {
    expect(citedPdfTarget("C1", "논문", [{ page_start: 4, page_end: 4 }, { page_start: 9, page_end: 9 }])).toEqual({
      cntsId: "C1",
      title: "논문",
      page: 5,
      passages: [
        { page: 5, label: "p.5" },
        { page: 10, label: "p.10" },
      ],
    });
  });

  it("첫 대목에 쪽 정보가 없으면 첫 쪽에서 연다", () => {
    expect(citedPdfTarget("C1", "논문", [{ page_start: 0, page_end: 0 }]).page).toBeUndefined();
  });
});

describe("focusReturnTarget", () => {
  it("연 버튼이 남아 있으면 그 버튼으로 돌려준다", () => {
    const opener = node("원문 보기", { focusable: true });
    expect(focusReturnTarget([opener, node("버튼 묶음")])).toBe(opener);
  });

  it("연 버튼이 사라졌으면 남은 가장 가까운 조상 안의 첫 초점 요소로 돌려준다", () => {
    const chip = node("인용칩", { focusable: true });
    const opener = node("팝오버의 원문 보기", { connected: false, focusable: true });
    const pop = node("팝오버", { connected: false });
    const wrap = node("칩 묶음", { inner: chip });
    expect(focusReturnTarget([opener, pop, wrap])).toBe(chip);
  });

  it("돌려줄 곳이 없으면 null", () => {
    expect(focusReturnTarget([])).toBeNull();
    expect(focusReturnTarget([node("사라진 버튼", { connected: false, focusable: true })])).toBeNull();
  });
});

describe("pdfStatus", () => {
  it("확인 요청의 상태를 돌려주고, 본문은 받지 않게 요청을 끊는다", async () => {
    let seen: RequestInit | undefined;
    const fake = (async (_url: string | URL | Request, init?: RequestInit) => {
      seen = init;
      return new Response(null, { status: 404 });
    }) as typeof fetch;
    expect(await pdfStatus("/api/books/C1/pdf", { "x-session-id": "s1" }, fake)).toBe(404);
    expect(seen?.headers).toEqual({ "x-session-id": "s1" });
    expect(seen?.signal?.aborted).toBe(true);
  });

  it("요청 자체가 실패하면 null", async () => {
    const fake = (async () => {
      throw new TypeError("Failed to fetch");
    }) as typeof fetch;
    expect(await pdfStatus("/api/books/C1/pdf", {}, fake)).toBeNull();
  });
});
