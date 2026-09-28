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
    let restored = false;
    const restore = () => {
      if (restored) return;
      restored = true;
      window.removeEventListener("afterprint", restore);
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
    } finally {
      // print() 는 인쇄 창이 닫힐 때까지 막혀 있다가 돌아온다(afterprint 도 그 전에 온다).
      // 정책으로 인쇄를 막았거나 인앱 브라우저처럼 창 없이 곧바로 돌아오는 곳은 afterprint 를
      // 쏘지 않으니, 돌아온 뒤에도 되돌려 버튼이 '만드는 중…'에 멈추지 않게 한다
      restore();
    }
  }

  return { exporting, printDoc, exportDocx, printPdf };
}
