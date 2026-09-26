// frontend/tests/unit/slashCommand.test.ts
import { describe, expect, it } from "vitest";
import { createEchoGuard, modesFor, parseSlash, planSlashSubmit, shouldAutoChip } from "~/utils/slashCommand";

describe("parseSlash", () => {
  it("명령 뒤의 글을 질문으로 떼어 낸다", () => {
    expect(parseSlash("/deep-research AI 윤리 교육의 효과")).toEqual({ mode: "deep-research", text: "AI 윤리 교육의 효과" });
  });

  it("앞뒤 공백과 대소문자를 가리지 않는다", () => {
    expect(parseSlash("  /Deep-Research   질문")).toEqual({ mode: "deep-research", text: "질문" });
  });

  it("명령만 있으면 질문은 빈 글이다", () => {
    expect(parseSlash("/deep-research")).toEqual({ mode: "deep-research", text: "" });
  });

  it("명령 이름에 글자가 이어 붙거나 명령이 가운데 있으면 명령이 아니다", () => {
    expect(parseSlash("/deep-researcher x")).toEqual({ mode: null, text: "/deep-researcher x" });
    expect(parseSlash("AI /deep-research")).toEqual({ mode: null, text: "AI /deep-research" });
  });
});

describe("shouldAutoChip", () => {
  it("명령 뒤에 공백이나 글이 붙어야 칩으로 바꾼다", () => {
    expect(shouldAutoChip("/deep-research")).toBe(false);
    expect(shouldAutoChip("/deep-research ")).toBe(true);
    expect(shouldAutoChip("/deep-research 질문")).toBe(true);
    expect(shouldAutoChip("질문")).toBe(false);
  });
});

describe("modesFor", () => {
  it("딥리서치는 논문 입력창에만 있다", () => {
    expect(modesFor("paper").map((m) => m.id)).toEqual(["deep-research"]);
    expect(modesFor("book")).toEqual([]);
  });
});

describe("planSlashSubmit", () => {
  const paper = modesFor("paper");

  it("칩 없이 명령만 치고 보내면 접두를 떼어 비우고 질문 오류를 낸다", () => {
    expect(planSlashSubmit("/deep-research", null, paper)).toEqual({
      mode: "deep-research",
      question: "",
      stripped: "",
      problem: "연구 질문을 2자 이상 입력하세요",
    });
  });

  it("명령 뒤의 글을 질문으로 보내고 입력창에는 접두를 뗀 글을 남긴다", () => {
    expect(planSlashSubmit("  /deep-research  AI 윤리 교육 ", null, paper)).toEqual({
      mode: "deep-research",
      question: "AI 윤리 교육",
      stripped: "AI 윤리 교육 ",
      problem: null,
    });
  });

  it("칩이 켜져 있으면 입력창 글 그대로가 질문이고 입력창은 건드리지 않는다", () => {
    expect(planSlashSubmit(" 질문입니다 ", "deep-research", paper)).toEqual({
      mode: "deep-research",
      question: "질문입니다",
      stripped: null,
      problem: null,
    });
  });

  it("칩도 명령도 없거나 이 입력창에 없는 모드면 딥리서치로 보내지 않는다", () => {
    expect(planSlashSubmit("그냥 검색", null, paper)).toBeNull();
    expect(planSlashSubmit("/deep-research 질문", null, modesFor("book"))).toBeNull();
  });
});

describe("createEchoGuard", () => {
  it("스스로 emit 한 값이 v-model 로 되돌아온 것만 한 번 알아본다", () => {
    const echo = createEchoGuard();
    echo.mark("");
    expect(echo.take("")).toBe(true);
    // 되돌아온 뒤의 같은 값은 사용자가 바꾼 것이다
    expect(echo.take("")).toBe(false);
  });

  it("다른 값이 먼저 오면 사용자의 변화로 보고 표시를 잊는다", () => {
    const echo = createEchoGuard();
    echo.mark("질문");
    expect(echo.take("질문 더")).toBe(false);
    expect(echo.take("질문")).toBe(false);
  });

  it("표시한 적이 없으면 어떤 값도 되돌아온 것이 아니다", () => {
    expect(createEchoGuard().take("")).toBe(false);
  });
});
