// frontend/utils/deepRead.ts
// 딥리드(BookChat)의 문서 종류별 문구·출처 칩 표기·원문 열기 입력, 단계 화면 오른쪽 패널(DeepReadPanel)의 배치·머리·탭.
// 연구 화면의 오른쪽 패널(06e)과 기존 네 화면이 함께 쓴다
import type { OpenPdfPayload } from "~/types/research";
import type { PaperMeta } from "~/types/work";
import { DEEP_READ } from "~/utils/brand";
import { pubYear, splitAuthors } from "~/utils/citations";
import type { DeepReadSource } from "~/utils/deepReadSse";
import { citedPdfTarget } from "~/utils/pdfViewer";

// 책(도서 상세·TopResult)인지 논문(논문 상세·논문 검색·연구 화면 패널)인지 — 기본은 책(지금 문구)
export type DocKind = "book" | "paper";

// stopLabel 은 답을 받는 동안 보내기 단추가 바뀌는 [멈춤] 단추의 이름(화면낭독기·마우스 툴팁)
export interface ChatCopy {
  greeting(title?: string): string;
  placeholder: string;
  inputLabel: string;
  sendLabel: string;
  stopLabel: string;
}

const COPY: Record<DocKind, ChatCopy> = {
  book: {
    greeting: (title) => `안녕하세요! ${title ? `《${title}》에 대해` : "이 자료에 대해"} 궁금한 것을 자유롭게 물어보세요!`,
    placeholder: "책에 대해서 자유롭게 질문해보세요!",
    inputLabel: "책에 대한 질문 입력",
    sendLabel: "질문 보내기",
    stopLabel: "답 받기 멈추기",
  },
  paper: {
    greeting: (title) => `안녕하세요! ${title ? `《${title}》 논문에 대해` : "이 논문에 대해"} 궁금한 것을 자유롭게 물어보세요!`,
    placeholder: "논문에 대해서 자유롭게 질문해보세요!",
    inputLabel: "논문에 대한 질문 입력",
    sendLabel: "질문 보내기",
    stopLabel: "답 받기 멈추기",
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

// ── 단계 화면 오른쪽 패널(spec §12-4 D24) ─────────────────────────
// 탭 — 인용 근거(보고서 인용 칩이 연다)·딥리드(BookChat)
export type PanelTab = "sources" | "chat";

// 탭 이름 — 대화 탭은 화면 표기 상수(utils/brand DEEP_READ)
export const PANEL_TAB_LABEL: Readonly<Record<PanelTab, string>> = { sources: "인용 근거", chat: DEEP_READ };

// 배치 경계(px) — 이 폭 이상은 단계 본문 옆 2단(sticky), 그 미만은 오른쪽 서랍, PANEL_FULL_MAX_PX 이하는 전체 폭 서랍.
// work.css 의 @media (max-width: 1199px)·(max-width: 768px) 와 같은 값이다
export const PANEL_SIDE_MIN_PX = 1200;
export const PANEL_FULL_MAX_PX = 768;

export type PanelMode = "side" | "drawer" | "full";

// 서랍·전체 폭이면 패널이 화면을 덮어 Tab 초점을 패널 안에 가둔다(DeepReadPanel — 처음·끝 보초)
export function panelMode(width: number): PanelMode {
  if (width >= PANEL_SIDE_MIN_PX) return "side";
  return width > PANEL_FULL_MAX_PX ? "drawer" : "full";
}

// 서랍·전체 폭의 Tab 가두기는 패널 처음·끝에 둔 보초(tabindex=0, 보이지 않음)로 한다. 패널 안의 Tab 이동은 브라우저 기본에
// 맡겨 셀렉터 목록에 없는 Tab 순서(넘치는 출처 미리보기·메시지 칸·인용 근거 본문처럼 브라우저가 넣는 스크롤 영역)가 그대로 남고,
// 보초가 초점을 받을 때만 돌린다 — Tab 순서를 셀렉터로 다시 만들어 keydown 에서 고르면 목록 밖 요소를 모두 '끝'으로 보아 그 뒤의
// [원문 보기]·입력 칸에 닿지 못했다. 제목(h2 tabindex=-1)·답을 받는 동안 disabled 가 된 입력 칸에서 누른 Tab 도 문서 순서로
// 다음(또는 앞) 요소나 보초로 가서 패널 밖으로 새지 않는다
export type PanelEdge = "start" | "end";

// 보초가 초점을 받았을 때 옮길 곳 — stops 는 보초를 뺀 패널 안 Tab 순서(문서 순서), fromInside 는 초점이 패널 안에서 왔는가
// (focus 의 relatedTarget). 안에서 끝 보초에 닿으면(마지막 요소에서 정방향 Tab) 처음으로, 처음 보초에 닿으면(처음 요소·제목에서
// 역방향 Tab) 끝으로 돌린다. 밖(또는 body)에서 들어오면 처음 보초는 처음, 끝 보초는 끝으로 들인다. 비어 있으면 null(제목으로)
export function panelEdgeTarget<T>(stops: readonly T[], edge: PanelEdge, fromInside: boolean): T | null {
  const toFirst = (edge === "end") === fromInside;
  return (toFirst ? stops[0] : stops[stops.length - 1]) ?? null;
}

// 브라우저가 Tab 순서에 넣는 스크롤 영역인가 — Chrome 130 이후·Firefox 는 넘치는(overflow 가 auto·scroll 이고 내용이 칸보다 큰)
// 영역 가운데 안에 초점 받을 요소가 없는 것을 Tab 순서에 넣는다. tabindex 속성이 없고 IDL tabIndex 도 -1 이라 셀렉터로는 못 찾아,
// 처음 보초가 '끝'을 고를 때 따로 센다(누를 것 없는 인용 근거 탭 본문이 끝이면 그 본문으로 — 건너뛰지 않게)
export interface ScrollBox {
  overflowX: string;
  overflowY: string;
  scrollWidth: number;
  clientWidth: number;
  scrollHeight: number;
  clientHeight: number;
  hasFocusable: boolean;
}

export function keyboardScroller(box: ScrollBox): boolean {
  if (box.hasFocusable) return false;
  const scrolls = (v: string) => v === "auto" || v === "scroll";
  return (
    (scrolls(box.overflowY) && box.scrollHeight > box.clientHeight) ||
    (scrolls(box.overflowX) && box.scrollWidth > box.clientWidth)
  );
}

// 패널 안 초점이 갈 곳 없이 사라졌는가 — related 는 focusout 의 relatedTarget(초점이 옮겨 가는 요소), active 는 그 뒤의
// document.activeElement, body 는 문서의 body. 서랍·전체 폭에서 답을 받는 동안 입력 칸이 disabled 가 되면 초점이
// body 로 떨어져 aside 의 keydown(Esc)이 듣지 못하고 Tab 은 보초를 거치지 않고 배경으로 나간다. 그때만 제목으로 되돌린다.
// relatedTarget 이 있으면 초점이 다른 요소로 옮겨 가는 중이라 잃은 것이 아니다 — 사용자의 클릭·Tab 은 focusout 이 끝난 뒤에야 새
// 요소가 초점을 받아, 그 사이(마이크로태스크)에 읽은 activeElement 는 아직 body 다. active 만 보면 패널 안 이동까지 잃은 것으로 보고
// 제목으로 되돌려 원래 가려던 이동을 막는다(입력 칸 클릭·Tab 순회가 막혔다).
// 패널 밖 다른 요소로 옮겨 간 초점(원문 뷰어의 닫기 단추 등)도 잃은 것이 아니라 그대로 둔다 — 서랍에서는 Tab 가두기와 배경(누르면
// 닫힘) 때문에 사용자가 패널 밖으로 초점을 옮길 길이 없어, 밖으로 간 초점은 다른 부품이 일부러 옮긴 것이다. 2단은 가두지 않는다
export function panelFocusLost(
  mode: PanelMode,
  focus: { related: unknown; active: unknown; body: unknown },
): boolean {
  if (mode === "side" || focus.related) return false;
  return focus.active === null || focus.active === focus.body;
}

// 패널이 여는 논문 — 머리는 행 데이터(서지)만으로 그린다
export interface PanelPaper {
  cntsId: string;
  meta: PaperMeta;
}

// 머리 — 제목(없으면 cnts_id)과 '저자 · 연도 · 학술지' 가운데 있는 것. 저자는 splitAuthors 로 나눠 쉼표로 잇는다
export function panelHead(p: PanelPaper): { title: string; byline: string } {
  const byline = [splitAuthors(p.meta.personal_author).join(", "), pubYear(p.meta.pub_date), p.meta.series_title]
    .map((s) => (s ?? "").trim())
    .filter(Boolean)
    .join(" · ");
  return { title: p.meta.title?.trim() || p.cntsId, byline };
}

// 단계마다 쓰는 탭 — 참고문헌 선택하기는 누른 문장이 없어 딥리드만, 보고서는 인용 근거·딥리드
export function panelTabs(step: "reading" | "proposal"): PanelTab[] {
  return step === "reading" ? ["chat"] : ["sources", "chat"];
}
