// frontend/tests/unit/slashCommand.test.ts
import { describe, expect, it } from "vitest";
import {
  createEchoGuard,
  modesFor,
  paletteKeyAction,
  parseSlash,
  planSlashSubmit,
  shouldAutoChip,
  slashSuggestions,
  type SearchMode,
} from "~/utils/slashCommand";

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

describe("slashSuggestions", () => {
  const paper = modesFor("paper");
  const deep = paper[0]!;
  // 모드가 여럿일 때 접두로 걸러지는지 보려고 가짜 모드를 하나 더한다
  const summary: SearchMode = { ...deep, label: "요약", slash: "/summary" };
  const two = [deep, summary];
  const slashes = (input: string, modes: readonly SearchMode[] = two) => slashSuggestions(input, modes).map((m) => m.slash);

  it("슬래시 하나만 치면 그 입력창에서 쓸 수 있는 명령 전부", () => {
    expect(slashes("/")).toEqual(["/deep-research", "/summary"]);
    expect(slashSuggestions("/", paper)).toEqual(paper);
  });

  it("명령 이름의 접두로 거르고 대소문자는 가리지 않는다", () => {
    expect(slashes("/dee")).toEqual(["/deep-research"]);
    expect(slashes("/DEEP")).toEqual(["/deep-research"]);
    expect(slashes("/s")).toEqual(["/summary"]);
  });

  it("슬래시 뒤의 글이 라벨의 접두여도 걸린다", () => {
    expect(slashes("/딥")).toEqual(["/deep-research"]);
    expect(slashes("/요")).toEqual(["/summary"]);
  });

  it("앞 공백은 무시하고 명령을 끝까지 쳐도 목록에 남는다", () => {
    expect(slashes("  /de")).toEqual(["/deep-research"]);
    expect(slashes("/deep-research")).toEqual(["/deep-research"]);
  });

  it("토큰 뒤에 공백·글·줄바꿈이 붙으면 목록을 띄우지 않는다", () => {
    expect(slashes("/deep-research ")).toEqual([]);
    expect(slashes("/deep-research 질문")).toEqual([]);
    expect(slashes("/de\n")).toEqual([]);
    expect(slashes("/de\nep")).toEqual([]);
  });

  it("맞는 명령이 없거나 슬래시로 시작하지 않으면 빈 목록", () => {
    expect(slashes("/xyz")).toEqual([]);
    expect(slashes("abc")).toEqual([]);
    expect(slashes("a/deep")).toEqual([]);
    expect(slashes("")).toEqual([]);
    expect(slashes("   ")).toEqual([]);
  });

  it("쓸 수 있는 명령이 없는 입력창(도서)에는 목록이 없다", () => {
    expect(slashSuggestions("/", [])).toEqual([]);
    expect(slashSuggestions("/deep", modesFor("book"))).toEqual([]);
  });
});

describe("paletteKeyAction", () => {
  const plain = { composing: false, shift: false };

  it("방향키는 강조를 옮기고 엔터·Tab 은 고르고 Esc 는 닫는다", () => {
    expect(paletteKeyAction("ArrowDown", plain)).toBe("next");
    expect(paletteKeyAction("ArrowUp", plain)).toBe("prev");
    expect(paletteKeyAction("Enter", plain)).toBe("select");
    expect(paletteKeyAction("Tab", plain)).toBe("select");
    expect(paletteKeyAction("Escape", plain)).toBe("close");
  });

  it("한글 조합 중 엔터는 막기만 하고 방향키·Tab 은 건드리지 않는다", () => {
    const composing = { composing: true, shift: false };
    expect(paletteKeyAction("Enter", composing)).toBe("block");
    expect(paletteKeyAction("ArrowDown", composing)).toBeNull();
    expect(paletteKeyAction("ArrowUp", composing)).toBeNull();
    expect(paletteKeyAction("Tab", composing)).toBeNull();
    expect(paletteKeyAction("Escape", composing)).toBe("close");
  });

  it("Shift 를 쥔 엔터·Tab 은 목록의 키가 아니다", () => {
    const shift = { composing: false, shift: true };
    expect(paletteKeyAction("Enter", shift)).toBeNull();
    expect(paletteKeyAction("Tab", shift)).toBeNull();
    expect(paletteKeyAction("Enter", { composing: true, shift: true })).toBeNull();
  });

  it("그 밖의 키는 입력창에 그대로 둔다", () => {
    expect(paletteKeyAction("a", plain)).toBeNull();
    expect(paletteKeyAction("Home", plain)).toBeNull();
    expect(paletteKeyAction("Backspace", plain)).toBeNull();
  });
});
