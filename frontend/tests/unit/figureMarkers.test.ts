// frontend/tests/unit/figureMarkers.test.ts
import { describe, expect, it } from "vitest";
import type { Figure } from "~/types/work";
import { figureById, numbersOutside, sentenceFlags, splitMarkers } from "~/utils/figureMarkers";
import markerChecks from "../fixtures/marker_checks.json";

// 백엔드 test_research_work_markers.py 와 함께 읽는 고정 예제(Task 6) — 한쪽 규칙을 바꾸면 다른 쪽 테스트가 깨진다
interface MarkerCase {
  text: string;
  numbers: string[];
  unmarked: number;
  // 서버 검사(check_paragraph) 뒤에도 남는 괄호 글 — 화면도 칩이 아닌 글자로 그려야 한다
  kept?: string[];
  note: string;
}
const CASES: MarkerCase[] = markerChecks;

describe("marker_checks.json — 백엔드와 같은 결과", () => {
  it("고정 예제가 있다", () => {
    expect(CASES.length).toBeGreaterThan(0);
  });

  it.each(CASES)("$note", (c) => {
    expect(numbersOutside(c.text)).toEqual(c.numbers);
    const flags = sentenceFlags(c.text);
    expect(flags.map((f) => f.text).join("")).toBe(c.text);
    expect(flags.filter((f) => f.unmarked).length).toBe(c.unmarked);
    expect(flags.flatMap((f) => f.numbers)).toEqual(c.numbers);
    for (const kept of c.kept ?? []) {
      expect(c.text).toContain(kept);
      expect(splitMarkers(kept)).toEqual([{ type: "text", text: kept }]);
    }
  });

  it("마커가 아닌 '[F1-score]' 가 남는 예제가 있다", () => {
    expect(CASES.some((c) => c.kept?.includes("[F1-score]"))).toBe(true);
  });
});

describe("splitMarkers", () => {
  it("[E#] 은 근거 칩, [F#] 은 수치 칩, 나머지는 글자 그대로다", () => {
    expect(splitMarkers("이 절의 논문 [F1] 가운데 종단 자료가 많다 [E2].")).toEqual([
      { type: "text", text: "이 절의 논문 " },
      { type: "figure", fid: "F1" },
      { type: "text", text: " 가운데 종단 자료가 많다 " },
      { type: "cite", eid: "E2" },
      { type: "text", text: "." },
    ]);
    expect(splitMarkers("[E1][F2]")).toEqual([
      { type: "cite", eid: "E1" },
      { type: "figure", fid: "F2" },
    ]);
    expect(splitMarkers("")).toEqual([]);
  });

  it("스트리밍 중 끝에 걸린 미완성 표기는 글자로 둔다", () => {
    expect(splitMarkers("근거가 있다 [E")).toEqual([{ type: "text", text: "근거가 있다 [E" }]);
    expect(splitMarkers("수치는 [F1")).toEqual([{ type: "text", text: "수치는 [F1" }]);
    expect(splitMarkers("앞 [E1] 뒤 [F")).toEqual([
      { type: "text", text: "앞 " },
      { type: "cite", eid: "E1" },
      { type: "text", text: " 뒤 [F" },
    ]);
  });

  it("표준형이 아닌 괄호는 칩으로 바꾸지 않는다", () => {
    expect(splitMarkers("[e1] [F 2] [표 1] [G3]")).toEqual([{ type: "text", text: "[e1] [F 2] [표 1] [G3]" }]);
  });
});

describe("numbersOutside", () => {
  it("마커 밖 숫자만 등장 순으로 센다", () => {
    expect(numbersOutside("2017년 이후 [F1]편 가운데 3편이 [E2] 종단 연구다.")).toEqual(["2017", "3"]);
    expect(numbersOutside("근거 [E12] 와 수치 [F3] 만 있다.")).toEqual([]);
  });

  it("이름에 붙은 숫자·통계 표기의 소수점 뒤 숫자는 세지 않는다", () => {
    expect(numbersOutside("COVID-19 와 B2B, 5G, p<.05 를 다룬다.")).toEqual([]);
  });

  it("마커는 빈 글자로 지운다 — 서버 numbers_outside 와 같이 마커 양옆 숫자는 한 숫자가 된다", () => {
    expect(numbersOutside("3[F1]4")).toEqual(["34"]);
  });

  it("전각 숫자도 서버(파이썬 \\d)처럼 숫자로 센다", () => {
    expect(numbersOutside("２０１９년 연구")).toEqual(["２０１９"]);
  });
});

describe("sentenceFlags", () => {
  it("문장마다 근거 표시와 숫자를 붙이고, 이어 붙이면 원문이다", () => {
    const text = "선행연구는 두 갈래다. 첫째는 가족 지지다 [E1]. 둘째는 2019년 뒤 늘었다.";
    expect(sentenceFlags(text)).toEqual([
      { text: "선행연구는 두 갈래다. ", unmarked: true, numbers: [] },
      { text: "첫째는 가족 지지다 [E1]. ", unmarked: false, numbers: [] },
      { text: "둘째는 2019년 뒤 늘었다.", unmarked: true, numbers: ["2019"] },
    ]);
  });

  it("마침표 뒤에 붙은 [E#] 묶음은 앞 문장의 근거다", () => {
    expect(sentenceFlags("지지는 우울을 낮춘다. [E1] [E2] 효과는 작다.")).toEqual([
      { text: "지지는 우울을 낮춘다. [E1] [E2] ", unmarked: false, numbers: [] },
      { text: "효과는 작다.", unmarked: true, numbers: [] },
    ]);
  });

  it("소수점과 마침표에 바로 붙은 마커는 문장을 가르지 않는다(서버도 공백 없는 끝은 나누지 않는다)", () => {
    expect(sentenceFlags("효과 크기는 0.35였다.[E1] 이어서 본다.")).toEqual([
      { text: "효과 크기는 0.35였다.[E1] 이어서 본다.", unmarked: false, numbers: ["0.35"] },
    ]);
  });

  it("빈 글은 빈 목록, 공백만 있으면 근거 표시 없음으로 세지 않는다", () => {
    expect(sentenceFlags("")).toEqual([]);
    expect(sentenceFlags("  ")).toEqual([{ text: "  ", unmarked: false, numbers: [] }]);
  });
});

describe("figureById", () => {
  const FIGURES: Figure[] = [
    { id: "F1", label: "이 절에 준 논문 수", value: "6" },
    { id: "F2", label: "발행 연도 범위", value: "2008~2015" },
  ];

  it("번호로 수치를 찾고 없으면 null", () => {
    expect(figureById(FIGURES, "F2")).toEqual({ id: "F2", label: "발행 연도 범위", value: "2008~2015" });
    expect(figureById(FIGURES, "F9")).toBeNull();
    expect(figureById([], "F1")).toBeNull();
  });
});
