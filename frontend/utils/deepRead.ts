// frontend/utils/deepRead.ts
// 딥리드(BookChat)의 문서 종류별 문구·출처 칩 표기·원문 열기 입력. 연구 화면의 오른쪽 패널(06e)과 기존 네 화면이 함께 쓴다
import type { OpenPdfPayload } from "~/types/research";
import type { DeepReadSource } from "~/utils/deepReadSse";
import { citedPdfTarget } from "~/utils/pdfViewer";

// 책(도서 상세·TopResult)인지 논문(논문 상세·논문 검색·연구 화면 패널)인지 — 기본은 책(지금 문구)
export type DocKind = "book" | "paper";

export interface ChatCopy {
  greeting(title?: string): string;
  placeholder: string;
  inputLabel: string;
  sendLabel: string;
}

const COPY: Record<DocKind, ChatCopy> = {
  book: {
    greeting: (title) => `안녕하세요! ${title ? `《${title}》에 대해` : "이 자료에 대해"} 궁금한 것을 자유롭게 물어보세요!`,
    placeholder: "책에 대해서 자유롭게 질문해보세요!",
    inputLabel: "책에 대한 질문 입력",
    sendLabel: "질문 보내기",
  },
  paper: {
    greeting: (title) => `안녕하세요! ${title ? `《${title}》 논문에 대해` : "이 논문에 대해"} 궁금한 것을 자유롭게 물어보세요!`,
    placeholder: "논문에 대해서 자유롭게 질문해보세요!",
    inputLabel: "논문에 대한 질문 입력",
    sendLabel: "질문 보내기",
  },
};

export function chatCopy(kind: DocKind): ChatCopy {
  return COPY[kind];
}

// 출처 칩 글자 — 저장값 그대로(0부터 센 쪽). 서버가 같은 값으로 LLM 문맥 [p.X–Y] 를 만들어 답 글에도 그 숫자가 나온다
// (book_chat.py:155). citations.pageLabel(+1)로 바꾸면 칩이 답 글과 한 쪽씩 어긋난다(06e 정함 22)
export function sourceLabel(src: DeepReadSource): string {
  return `p.${src.page_start}${src.page_end !== src.page_start ? `–${src.page_end}` : ""}`;
}

// 출처 대목으로 원문을 연다 — 0부터 센 저장값을 뷰어 쪽(+1)으로(pdfViewer.citedPdfTarget). 쪽 정보가 0 이면 쪽 없이 연다
export function sourcePdfTarget(cntsId: string, title: string, src: DeepReadSource): OpenPdfPayload {
  return citedPdfTarget(cntsId, title, [src]);
}
