// frontend/tests/unit/useReportExport.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { useReportExport } from "~/composables/useReportExport";
import type { ReportDoc } from "~/utils/reportDocument";

const doc: ReportDoc = { fileName: "딥리서치_질문_20260928.docx", blocks: [], references: [] };

// Node 에는 인쇄 창이 없다 — print() 는 불린 순간만 흉내 내고 afterprint 는 쏘지 않는다
// (정책으로 인쇄를 막았거나 인앱 브라우저처럼 창 없이 곧바로 돌아오는 곳과 같다)
function stubPage(print: () => void): void {
  vi.stubGlobal("document", { title: "딥리서치" });
  vi.stubGlobal("window", { print });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("printPdf", () => {
  it("인쇄하는 동안만 인쇄 문서와 파일 이름 제목을 두고, afterprint 없이 돌아와도 원래대로 되돌린다", async () => {
    const { exporting, printDoc, printPdf } = useReportExport();
    let during: unknown = null;
    stubPage(() => {
      during = { title: document.title, printDoc: printDoc.value, exporting: exporting.value };
    });
    await printPdf(doc);
    expect(during).toEqual({ title: "딥리서치_질문_20260928", printDoc: doc, exporting: true });
    expect(document.title).toBe("딥리서치");
    expect(printDoc.value).toBeNull();
    expect(exporting.value).toBe(false);
  });

  it("print() 가 던져도 원래대로 되돌리고 오류를 넘긴다", async () => {
    const { exporting, printDoc, printPdf } = useReportExport();
    stubPage(() => {
      throw new Error("인쇄 막힘");
    });
    await expect(printPdf(doc)).rejects.toThrow("인쇄 막힘");
    expect(document.title).toBe("딥리서치");
    expect(printDoc.value).toBeNull();
    expect(exporting.value).toBe(false);
  });
});
