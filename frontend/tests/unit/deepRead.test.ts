// frontend/tests/unit/deepRead.test.ts
import { describe, expect, it } from "vitest";
import { chatCopy, sourceLabel, sourcePdfTarget } from "~/utils/deepRead";

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
