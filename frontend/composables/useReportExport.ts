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
    const restore = () => {
      document.title = previousTitle;
      printDoc.value = null;
      exporting.value = false;
    };
    try {
      printDoc.value = doc;
      // 인쇄 전용 문서가 DOM 에 그려진 뒤에 인쇄 창을 연다
      await nextTick();
      // 인쇄 창의 "PDF로 저장"은 문서 제목을 기본 파일 이름으로 쓴다
      document.title = doc.fileName.replace(/\.docx$/i, "");
      window.addEventListener("afterprint", restore, { once: true });
      window.print();
    } catch (e) {
      window.removeEventListener("afterprint", restore);
      restore();
      throw e;
    }
  }

  return { exporting, printDoc, exportDocx, printPdf };
}
