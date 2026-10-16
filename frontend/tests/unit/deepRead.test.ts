// frontend/tests/unit/deepRead.test.ts
import { describe, expect, it } from "vitest";
import type { PaperMeta } from "~/types/work";
import { DEEP_READ } from "~/utils/brand";
import {
  PANEL_FULL_MAX_PX,
  PANEL_SIDE_MIN_PX,
  PANEL_TAB_LABEL,
  chatCopy,
  keyboardScroller,
  panelEdgeTarget,
  panelFocusLost,
  panelHead,
  panelMode,
  panelTabs,
  sourceLabel,
  sourcePdfTarget,
} from "~/utils/deepRead";

describe("chatCopy·sourceLabel·sourcePdfTarget", () => {
  it("답을 받는 동안의 [멈춤] 단추 이름은 둘 다 '답 받기 멈추기'", () => {
    expect(chatCopy("book").stopLabel).toBe("답 받기 멈추기");
    expect(chatCopy("paper").stopLabel).toBe("답 받기 멈추기");
  });

  it("책은 지금 문구 그대로, 논문은 '논문' 문구 — 보내기 버튼 이름은 둘 다 '질문 보내기'", () => {
    const book = chatCopy("book");
    expect(book.greeting("어린 왕자")).toBe("안녕하세요! 《어린 왕자》에 대해 궁금한 것을 자유롭게 물어보세요!");
    expect(book.greeting()).toBe("안녕하세요! 이 자료에 대해 궁금한 것을 자유롭게 물어보세요!");
    expect(book.placeholder).toBe("책에 대해서 자유롭게 질문해보세요!");
    expect(book.inputLabel).toBe("책에 대한 질문 입력");
    expect(book.sendLabel).toBe("질문 보내기");

    const paper = chatCopy("paper");
    expect(paper.greeting("노인의 우울과 사회적 지지")).toBe(
      "안녕하세요! 《노인의 우울과 사회적 지지》 논문에 대해 궁금한 것을 자유롭게 물어보세요!",
    );
    expect(paper.greeting()).toBe("안녕하세요! 이 논문에 대해 궁금한 것을 자유롭게 물어보세요!");
    expect(paper.placeholder).toBe("논문에 대해서 자유롭게 질문해보세요!");
    expect(paper.inputLabel).toBe("논문에 대한 질문 입력");
    expect(paper.sendLabel).toBe("질문 보내기");
  });

  it("출처 칩 글자는 저장값 그대로 — 서버가 답 글에 쓴 쪽 표기와 같다(BookChat 의 지금 표기)", () => {
    expect(sourceLabel({ page_start: 5, page_end: 5, text: "" })).toBe("p.5");
    expect(sourceLabel({ page_start: 5, page_end: 7, text: "" })).toBe("p.5–7");
  });

  it("p.5 칩은 원문 6쪽을 연다 — 저장값은 0부터 세어 뷰어 쪽은 하나 크다", () => {
    expect(sourcePdfTarget("KCI_1", "제목", { page_start: 5, page_end: 7, text: "대목" })).toEqual({
      cntsId: "KCI_1",
      title: "제목",
      page: 6,
      passages: [{ page: 6, label: "p.6–8" }],
    });
  });

  it("쪽 정보가 없으면(0) 쪽 없이 연다", () => {
    expect(sourcePdfTarget("KCI_1", "제목", { page_start: 0, page_end: 0, text: "대목" })).toEqual({
      cntsId: "KCI_1",
      title: "제목",
      page: undefined,
      passages: [{ page: null, label: "쪽 정보 없음" }],
    });
  });
});

describe("panelMode·panelHead·panelTabs", () => {
  it("1200px 이상은 본문 옆 2단, 769~1199px 는 오른쪽 서랍, 768px 이하는 전체 폭", () => {
    expect([PANEL_SIDE_MIN_PX, PANEL_FULL_MAX_PX]).toEqual([1200, 768]);
    expect(panelMode(1440)).toBe("side");
    expect(panelMode(1200)).toBe("side");
    expect(panelMode(1199)).toBe("drawer");
    expect(panelMode(769)).toBe("drawer");
    expect(panelMode(768)).toBe("full");
    expect(panelMode(375)).toBe("full");
  });

  it("머리는 행의 서지만으로 — 저자·연도·학술지 가운데 있는 것만 잇고, 제목이 없으면 cnts_id", () => {
    const meta: PaperMeta = {
      title: " 노인의 우울과 사회적 지지 ",
      personal_author: "김철수; 이영희",
      pub_date: "2015-03",
      series_title: "노인복지연구",
    };
    expect(panelHead({ cntsId: "KCI_A", meta })).toEqual({
      title: "노인의 우울과 사회적 지지",
      byline: "김철수, 이영희 · 2015 · 노인복지연구",
    });
    expect(panelHead({ cntsId: "KCI_B", meta: { ...meta, personal_author: null, series_title: " " } })).toEqual({
      title: "노인의 우울과 사회적 지지",
      byline: "2015",
    });
    expect(
      panelHead({ cntsId: "KCI_C", meta: { title: "", personal_author: null, pub_date: null, series_title: null } }),
    ).toEqual({ title: "KCI_C", byline: "" });
  });

  it("참고문헌 선택하기는 DeepRead 탭만, 보고서는 인용 근거·DeepRead 두 탭", () => {
    expect(panelTabs("reading")).toEqual(["chat"]);
    expect(panelTabs("proposal")).toEqual(["sources", "chat"]);
  });

  it("탭 이름 — 대화 탭은 화면 표기 상수 DEEP_READ(utils/brand)다", () => {
    expect(PANEL_TAB_LABEL).toEqual({ sources: "인용 근거", chat: DEEP_READ });
    expect(PANEL_TAB_LABEL.chat).toBe("DeepRead");
  });
});

describe("panelEdgeTarget·keyboardScroller·panelFocusLost — 서랍·전체 폭의 초점 가두기", () => {
  // 패널 안 Tab 순서(보초를 뺀 문서 순서). 패널 안의 Tab 이동은 브라우저 기본에 맡기고, 처음·끝 보초가 초점을 받을 때만 돌린다 —
  // 그래서 목록 가운데의 목록 밖 요소(넘치는 출처 미리보기·메시지 칸처럼 브라우저가 Tab 순서에 넣는 스크롤 영역)에서 누른 Tab 은
  // 아무도 가로채지 않고 다음 요소(원문 보기·입력 칸)로 간다
  const detail = { id: "detail" };
  const close = { id: "close" };
  const chip = { id: "chip" };
  const preview = { id: "preview(scroller)" };
  const send = { id: "send" };
  const stops = [detail, close, chip, preview, send];

  it("끝 보초에 패널 안에서 닿으면(마지막 요소에서 정방향 Tab) 처음으로", () => {
    expect(panelEdgeTarget(stops, "end", true)).toBe(detail);
  });

  it("처음 보초에 패널 안에서 닿으면(처음 요소·제목에서 역방향 Tab) 끝으로 — 끝이 스크롤 영역이면 그 영역", () => {
    expect(panelEdgeTarget(stops, "start", true)).toBe(send);
    // 누를 것이 없는 인용 근거 탭 본문 — 목록의 끝이 탭 단추가 아니라 본문 스크롤 영역이다
    const tabBtn = { id: "tab(sources)" };
    const sourcesBody = { id: "sources(scroller)" };
    expect(panelEdgeTarget([detail, close, tabBtn, sourcesBody], "start", true)).toBe(sourcesBody);
  });

  it("패널 밖(또는 body)에서 보초로 들어오면 처음 보초는 처음, 끝 보초는 끝으로 들인다", () => {
    expect(panelEdgeTarget(stops, "start", false)).toBe(detail);
    expect(panelEdgeTarget(stops, "end", false)).toBe(send);
  });

  it("하나뿐이면 그 하나에 머물고, 비어 있으면 null(부르는 쪽이 제목으로)", () => {
    expect(panelEdgeTarget([close], "end", true)).toBe(close);
    expect(panelEdgeTarget([close], "start", true)).toBe(close);
    expect(panelEdgeTarget([], "end", true)).toBeNull();
    expect(panelEdgeTarget([], "start", true)).toBeNull();
  });

  it("넘치고 안에 누를 것이 없는 스크롤 영역은 Tab 순서에 든다 — tabindex 가 없어 셀렉터로는 못 찾는 요소다", () => {
    const box = {
      overflowX: "visible",
      overflowY: "auto",
      scrollWidth: 300,
      clientWidth: 300,
      scrollHeight: 400,
      clientHeight: 120,
      hasFocusable: false,
    };
    // 출처 칩을 펼친 미리보기(max-height 120px, 글만)
    expect(keyboardScroller(box)).toBe(true);
    expect(keyboardScroller({ ...box, overflowY: "scroll" })).toBe(true);
    expect(keyboardScroller({ ...box, overflowY: "visible", overflowX: "auto", scrollWidth: 500 })).toBe(true);
    // 넘치지 않으면·overflow 가 hidden·visible 이면·안에 누를 것(칩·링크)이 있으면 들지 않는다
    expect(keyboardScroller({ ...box, scrollHeight: 120 })).toBe(false);
    expect(keyboardScroller({ ...box, overflowY: "hidden" })).toBe(false);
    expect(keyboardScroller({ ...box, overflowY: "visible" })).toBe(false);
    expect(keyboardScroller({ ...box, hasFocusable: true })).toBe(false);
  });

  it("서랍·전체 폭에서 초점이 body(또는 없음)로 떨어진 것만 잃은 것으로 본다 — 패널 밖 다른 요소(원문 뷰어 닫기 등)로 간 것은 아니다", () => {
    const body = { id: "body" };
    const viewerClose = { id: "viewer-close" };
    // 옮겨 갈 요소 없이(relatedTarget null — disabled 가 되어 잃음·초점을 받지 않는 곳 클릭) 빠진 초점
    expect(panelFocusLost("drawer", { related: null, active: body, body })).toBe(true);
    expect(panelFocusLost("full", { related: null, active: body, body })).toBe(true);
    expect(panelFocusLost("drawer", { related: null, active: null, body })).toBe(true);
    // 창 전환처럼 activeElement 가 그대로 남은 것, 다른 부품이 일부러 옮긴 초점은 잃은 것이 아니다
    expect(panelFocusLost("drawer", { related: null, active: viewerClose, body })).toBe(false);
    expect(panelFocusLost("full", { related: null, active: close, body })).toBe(false);
    // 2단(side)은 화면을 덮지 않아 가두지 않는다 — 초점이 떨어져도 되돌리지 않는다
    expect(panelFocusLost("side", { related: null, active: body, body })).toBe(false);
  });

  it("다른 요소로 옮겨 가는 초점(relatedTarget 있음)은 잃은 것이 아니다 — 사용자의 클릭·Tab 은 focusout 바로 뒤에 activeElement 가 아직 body 다", () => {
    // 제목에서 입력 칸을 클릭하거나, 상세 링크에서 Tab 으로 닫기 단추로 갈 때 — 새 요소가 초점을 받기 전이라 active 는 body 다.
    // 이것을 잃은 것으로 보면 제목으로 되돌려 원래 가려던 이동을 막는다(서랍·모바일에서 질문을 입력할 수 없었다)
    const body = { id: "body" };
    const input = { id: "input" };
    expect(panelFocusLost("drawer", { related: input, active: body, body })).toBe(false);
    expect(panelFocusLost("full", { related: close, active: body, body })).toBe(false);
    expect(panelFocusLost("drawer", { related: chip, active: null, body })).toBe(false);
  });
});
