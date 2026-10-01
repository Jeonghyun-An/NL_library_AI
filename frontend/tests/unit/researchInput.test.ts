// frontend/tests/unit/researchInput.test.ts
import { describe, expect, it } from "vitest";
import { planKey, planProblem, questionProblem } from "~/utils/researchInput";

describe("questionProblem", () => {
  it("앞뒤 공백을 빼고 2~500자만 받는다", () => {
    expect(questionProblem(" 가 ")).toBe("연구 질문을 2자 이상 입력하세요");
    expect(questionProblem("가나")).toBeNull();
    expect(questionProblem("가".repeat(500))).toBeNull();
    expect(questionProblem("가".repeat(501))).toBe("연구 질문은 500자까지 입력할 수 있습니다");
  });

  it("글자 수는 코드포인트로 센다", () => {
    expect(questionProblem("😀")).toBe("연구 질문을 2자 이상 입력하세요");
  });
});

describe("planProblem", () => {
  it("정상 계획은 문제가 없다", () => {
    expect(planProblem(["효과 측정", "교사 인식"], 6)).toBeNull();
  });

  it("비었거나 상한을 넘으면 알린다", () => {
    expect(planProblem([], 6)).toBe("하위질문이 하나 이상 있어야 합니다");
    expect(planProblem(["가나", "다라", "마바"], 2)).toBe("하위질문은 2개까지입니다");
  });

  it("짧거나 긴 항목의 번호를 알린다", () => {
    expect(planProblem(["효과 측정", " 가 "], 6)).toBe("2번 하위질문을 2자 이상 입력하세요");
    expect(planProblem(["가".repeat(301)], 6)).toBe("1번 하위질문은 300자까지입니다");
  });

  it("공백·대소문자만 다른 항목은 중복이다", () => {
    expect(planKey("  AI   윤리 ")).toBe("ai 윤리");
    expect(planProblem(["AI 윤리", "ai  윤리"], 6)).toBe("2번 하위질문이 앞의 것과 같습니다");
  });
});
