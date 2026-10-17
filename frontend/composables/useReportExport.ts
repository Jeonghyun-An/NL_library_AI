// frontend/composables/useReportExport.ts
import { nextTick, ref, shallowRef } from "vue";
import type { ReportDoc, ReportExportFormat } from "~/utils/reportDocument";
import { downloadBlob, toDocxBlob } from "~/utils/reportDocx";

/**
 * 내보내기 실패 안내(딥리서치 보고서의 토스트·작업대 보고서의 줄 안내가 함께 쓴다). Word 는 배포 뒤 옛 화면에서 누르면 docx 조각
 * 파일이 사라져 동적 import 가 실패한다 — 새로고침이 답이다. 해요체·문장마다 줄바꿈(줄을 그리지 않는 토스트에서는 공백 하나)
 */
export const REPORT_EXPORT_FAILED: Record<ReportExportFormat, string> = {
  docx: "Word 문서를 만들지 못했어요.\n새로고침한 뒤 다시 시도해 주세요.",
  pdf: "인쇄 창을 열지 못했어요.\n다시 시도해 주세요.",
};

/**
 * print() 가 돌아온 뒤 인쇄가 시작됐다는 신호(beforeprint)를 기다리는 시간 — 이 안에 오지 않으면 인쇄 창이 열리지 않은 것
 * (정책으로 인쇄를 막음·인앱 브라우저)으로 보고 바로 되돌린다
 */
export const PRINT_START_GRACE_MS = 1000;
/**
 * 인쇄가 시작된 뒤 끝났다는 신호(afterprint)를 기다리는 가장 긴 시간 — 오지 않아도 이만큼 지나면 되돌린다(버튼이 '만드는 중…'에
 * 영영 멈추지 않게). 인쇄 창을 이보다 오래 열어 두는 드문 경우에는 그 뒤에 찍으면 화면이 찍힐 수 있다
 */
export const PRINT_END_FALLBACK_MS = 120_000;

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

  // 인쇄 전용 문서(ReportPrint)를 붙여 인쇄 창을 열고, 인쇄가 끝나면(afterprint) 떼고 문서 제목을 되돌린다.
  // Chrome·Firefox 데스크톱은 print() 가 인쇄 창이 닫힐 때까지 막혀 있다가 돌아오지만(그 안에서 afterprint 가 온다), 사파리·
  // 모바일처럼 print() 가 곧바로 돌아오고 인쇄 창은 나중에 뜨는 브라우저에서 돌아오자마자 떼면 보고서 대신 앱 화면이 찍혔다.
  // 그래서 afterprint 로 뗀다. 정책으로 인쇄를 막았거나 인앱 브라우저처럼 창 없이 돌아오는 곳은 afterprint 도 오지 않으므로
  // beforeprint(인쇄 시작)가 PRINT_START_GRACE_MS 안에 오지 않으면 바로, 왔는데 afterprint 가 없으면 PRINT_END_FALLBACK_MS 뒤에
  // 되돌린다. 돌려주는 약속은 되돌린 뒤에 풀린다 — 부르는 쪽은 그 뒤에 완료 처리를 한다.
  // 돌려주는 값은 인쇄가 시작됐는가(beforeprint·afterprint 를 받았다). false 면 인쇄 창이 열리지 않은 것이라 부르는 쪽은 조용히 성공으로
  // 두지 않고 실패 안내(REPORT_EXPORT_FAILED.pdf)를 보이며 완료 처리를 하지 않는다(인쇄 창을 열었다가 취소했는지는 브라우저가 알려 주지
  // 않아 시작했으면 true 다). 이미 내보내는 중이면 아무 일 없이 false — 부르는 쪽이 exporting 으로 먼저 막는다
  async function printPdf(doc: ReportDoc): Promise<boolean> {
    if (exporting.value) return false;
    exporting.value = true;
    const previousTitle = document.title;
    let started = false;
    let done = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let finish: () => void = () => {};
    const finished = new Promise<void>((resolve) => {
      finish = resolve;
    });

    function onBefore(): void {
      started = true;
    }

    // beforeprint 를 알리지 않고 afterprint 만 주는 브라우저도 인쇄는 한 것이다
    function onAfter(): void {
      started = true;
      restore();
    }

    function restore(): void {
      if (done) return;
      done = true;
      if (timer) clearTimeout(timer);
      timer = null;
      window.removeEventListener?.("beforeprint", onBefore);
      window.removeEventListener?.("afterprint", onAfter);
      document.title = previousTitle;
      printDoc.value = null;
      exporting.value = false;
      finish();
    }

    try {
      printDoc.value = doc;
      // 인쇄 전용 문서가 DOM 에 그려진 뒤에 인쇄 창을 연다
      await nextTick();
      // 인쇄 창의 "PDF로 저장"은 문서 제목을 기본 파일 이름으로 쓴다
      document.title = doc.fileName.replace(/\.docx$/i, "");
      window.addEventListener?.("beforeprint", onBefore);
      window.addEventListener?.("afterprint", onAfter);
      window.print();
    } catch (e) {
      restore();
      throw e;
    }
    if (!done) {
      // 막혀 있다 돌아오는 브라우저는 이미 afterprint 로 되돌렸다. 곧바로 돌아왔으면 인쇄가 시작됐는지 보고 기다린다
      timer = setTimeout(() => {
        if (!started) {
          restore();
          return;
        }
        timer = setTimeout(restore, PRINT_END_FALLBACK_MS);
      }, PRINT_START_GRACE_MS);
    }
    await finished;
    return started;
  }

  return { exporting, printDoc, exportDocx, printPdf };
}
