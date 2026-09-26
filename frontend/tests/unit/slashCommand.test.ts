// frontend/tests/unit/slashCommand.test.ts
import { describe, expect, it } from "vitest";
import { modesFor, parseSlash, shouldAutoChip } from "~/utils/slashCommand";

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
