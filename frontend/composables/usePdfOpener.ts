// frontend/composables/usePdfOpener.ts
import { ref } from "vue";
import type { OpenPdfPayload } from "~/types/research";
import { pdfStatus } from "~/utils/pdfViewer";
import { pdfCheckProblem } from "~/utils/researchErrors";
import { apiHeaders, apiUrl } from "./useApi";

// 원문 뷰어를 열기 전에 파일이 있는지 먼저 묻는다 — 없는 원문을 그대로 열면 pdf.js 의 영문 오류 화면이 뜬다.
// 알릴 문구(utils/researchErrors 의 pdfCheckProblem — 해요체)는 돌려주기만 하고 어디에 보일지는 화면이 정한다
// (딥리서치는 토스트, 논문 상세·논문 검색 결과 카드·요약 인용 팝오버는 누른 버튼 옆의 줄 안내 SkxInlineError)
export function usePdfOpener() {
  const pdf = ref<OpenPdfPayload | null>(null);
  const checking = ref(false);

  async function openPdf(target: OpenPdfPayload): Promise<string | null> {
    // 확인이 끝나기 전에 또 누르면 무시한다 — 뷰어가 두 번 열리거나 문구가 뒤섞이지 않게
    if (checking.value) return null;
    checking.value = true;
    try {
      const problem = pdfCheckProblem(await pdfStatus(apiUrl(`/books/${encodeURIComponent(target.cntsId)}/pdf`), apiHeaders()));
      if (!problem) pdf.value = target;
      return problem;
    } finally {
      checking.value = false;
    }
  }

  function closePdf(): void {
    pdf.value = null;
  }

  return { pdf, checking, openPdf, closePdf };
}
