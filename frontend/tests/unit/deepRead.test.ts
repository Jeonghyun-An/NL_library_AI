// frontend/tests/unit/deepRead.test.ts
import { describe, expect, it } from "vitest";
import type { PaperMeta } from "~/types/work";
import {
  PANEL_FULL_MAX_PX,
  PANEL_SIDE_MIN_PX,
  chatCopy,
  panelFocusLost,
  panelHead,
  panelMode,
  panelTabs,
  panelTrapTarget,
  sourceLabel,
  sourcePdfTarget,
} from "~/utils/deepRead";

describe("chatCopy·sourceLabel·sourcePdfTarget", () => {
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

  it("참고문헌 선택하기는 딥리드 탭만, 보고서는 인용 근거·딥리드 두 탭", () => {
    expect(panelTabs("reading")).toEqual(["chat"]);
    expect(panelTabs("proposal")).toEqual(["sources", "chat"]);
  });
});

describe("panelTrapTarget·panelFocusLost — 서랍·전체 폭의 초점 가두기", () => {
  // 패널 안 Tab 순서(숨긴 탭 본문·disabled 는 이미 빠진 목록). 제목 h2(tabindex=-1)와 답을 받는 동안 disabled 가 된
  // 입력 칸은 패널 안에 있지만 목록 밖이다
  const detail = { id: "detail" };
  const close = { id: "close" };
  const chip = { id: "chip" };
  const send = { id: "send" };
  const items = [detail, close, chip, send];
  const title = { id: "title" };
  const disabledInput = { id: "input(disabled)" };

  it("정방향 Tab — 끝에서 처음으로, 가운데는 브라우저 기본(null)", () => {
    expect(panelTrapTarget(items, send, false)).toBe(detail);
    expect(panelTrapTarget(items, detail, false)).toBeNull();
    expect(panelTrapTarget(items, chip, false)).toBeNull();
  });

  it("역방향 Tab — 처음에서 끝으로, 가운데는 브라우저 기본(null)", () => {
    expect(panelTrapTarget(items, detail, true)).toBe(send);
    expect(panelTrapTarget(items, send, true)).toBeNull();
    expect(panelTrapTarget(items, close, true)).toBeNull();
  });

  it("초점이 목록 밖(제목·답을 받는 동안 disabled 가 된 입력 칸)이면 정방향은 처음, 역방향은 끝 — 패널 밖으로 새지 않는다", () => {
    // 보내기 단추도 disabled 라 목록의 끝은 출처 칩이다 — 입력 칸이 끝이 아니어도 밖으로 나가지 않아야 한다
    const streaming = [detail, close, chip];
    expect(panelTrapTarget(streaming, disabledInput, false)).toBe(detail);
    expect(panelTrapTarget(streaming, disabledInput, true)).toBe(chip);
    expect(panelTrapTarget(items, title, false)).toBe(detail);
    expect(panelTrapTarget(items, title, true)).toBe(send);
  });

  it("하나뿐이면 그 하나에 머물고, 비어 있으면 기본(null)", () => {
    expect(panelTrapTarget([close], close, false)).toBe(close);
    expect(panelTrapTarget([close], close, true)).toBe(close);
    expect(panelTrapTarget([], title, false)).toBeNull();
    expect(panelTrapTarget([], title, true)).toBeNull();
  });

  it("서랍·전체 폭에서 초점이 body(또는 없음)로 떨어진 것만 잃은 것으로 본다 — 패널 밖 다른 요소(원문 뷰어 닫기 등)로 간 것은 아니다", () => {
    const body = { id: "body" };
    const viewerClose = { id: "viewer-close" };
    expect(panelFocusLost("drawer", body, body)).toBe(true);
    expect(panelFocusLost("full", body, body)).toBe(true);
    expect(panelFocusLost("drawer", null, body)).toBe(true);
    expect(panelFocusLost("drawer", viewerClose, body)).toBe(false);
    expect(panelFocusLost("full", close, body)).toBe(false);
    // 2단(side)은 화면을 덮지 않아 가두지 않는다 — 초점이 떨어져도 되돌리지 않는다
    expect(panelFocusLost("side", body, body)).toBe(false);
  });
});
