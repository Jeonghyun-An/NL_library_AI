// frontend/tests/unit/relevance.test.ts
import { describe, expect, it } from "vitest";
import { popoverPlacement, relevancePct, relevanceRings } from "~/utils/relevance";

describe("relevancePct — 점수(0~1)를 정수 퍼센트로", () => {
  it("내림한다 — 99.6% 가 100% 로 올림 표기되지 않게(결과 카드·상세와 같은 규칙)", () => {
    expect(relevancePct(0.996)).toBe(99);
    expect(relevancePct(0.735)).toBe(73);
    expect(relevancePct(0.8685)).toBe(86);
  });

  it("부동소수 오차로 한 칸 덜 나오지 않는다(0.29×100 = 28.999…)", () => {
    expect(relevancePct(0.29)).toBe(29);
    expect(relevancePct(0.57)).toBe(57);
    expect(relevancePct(0.58)).toBe(58);
  });

  it("0~100 으로 자르고 숫자가 아니면 0", () => {
    expect(relevancePct(1)).toBe(100);
    expect(relevancePct(1.4)).toBe(100);
    expect(relevancePct(-0.2)).toBe(0);
    expect(relevancePct(undefined)).toBe(0);
    expect(relevancePct(null)).toBe(0);
    expect(relevancePct(Number.NaN)).toBe(0);
    expect(relevancePct("0.5")).toBe(0);
  });
});

describe("relevanceRings — 팝오버의 링(제목·내용 일치율)", () => {
  it("제목 → 내용 순으로 라벨·퍼센트·색 변형을 준다", () => {
    expect(relevanceRings(0.24, 0.7)).toEqual([
      { key: "title", label: "제목 일치율", pct: 24, variant: "title" },
      { key: "content", label: "내용 일치율", pct: 70, variant: "content" },
    ]);
  });

  it("있는 점수만 — 한쪽이 없으면 그 링은 뺀다", () => {
    expect(relevanceRings(undefined, 0.5).map((r) => r.key)).toEqual(["content"]);
    expect(relevanceRings(0.5, null).map((r) => r.key)).toEqual(["title"]);
  });

  it("둘 다 없으면(옛 기록 복원 등) 빈 목록 — 알약만 보인다", () => {
    expect(relevanceRings(undefined, undefined)).toEqual([]);
    expect(relevanceRings(Number.NaN, "x")).toEqual([]);
  });

  it("0 점은 있는 점수다(0% 링)", () => {
    expect(relevanceRings(0, 0.69).map((r) => r.pct)).toEqual([0, 69]);
  });
});

describe("popoverPlacement — 팝오버가 화면 밖으로 나가지 않게", () => {
  const vp = { width: 400, height: 800 };

  it("들어맞으면 그대로 아래에 둔다", () => {
    expect(popoverPlacement({ left: 50, right: 200, top: 100, bottom: 160 }, { top: 90 }, vp)).toEqual({ shiftX: 0, above: false });
  });

  it("오른쪽으로 넘으면 넘는 만큼 왼쪽으로 민다(여백 8)", () => {
    expect(popoverPlacement({ left: 300, right: 460, top: 100, bottom: 160 }, { top: 90 }, vp).shiftX).toBe(-68);
  });

  it("왼쪽으로 넘으면 오른쪽으로 민다", () => {
    expect(popoverPlacement({ left: -20, right: 140, top: 100, bottom: 160 }, { top: 90 }, vp).shiftX).toBe(28);
  });

  it("너무 넓어 양쪽에 다 못 들어가면 왼쪽 여백에 맞춘다", () => {
    expect(popoverPlacement({ left: 10, right: 420, top: 100, bottom: 160 }, { top: 90 }, vp).shiftX).toBe(-2);
  });

  it("아래로 넘고 위에 자리가 있으면 위로 올린다", () => {
    expect(popoverPlacement({ left: 50, right: 200, top: 780, bottom: 840 }, { top: 755 }, vp).above).toBe(true);
  });

  it("아래로 넘어도 위에도 자리가 없으면 아래에 둔다", () => {
    expect(popoverPlacement({ left: 50, right: 200, top: 30, bottom: 90 }, { top: 5 }, { width: 400, height: 80 }).above).toBe(false);
  });
});
