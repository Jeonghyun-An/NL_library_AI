// frontend/tests/unit/relevance.test.ts
import { describe, expect, it } from "vitest";
import { detailScoreParams, popoverPlacement, queryScorePct, relevancePct, relevanceRings, scoreParam } from "~/utils/relevance";

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

describe("queryScorePct — 상세 화면 주소의 점수(?score= 등)", () => {
  it("목록 카드와 같은 규칙(내림 + 부동소수 보정)으로 퍼센트를 만든다", () => {
    expect(queryScorePct("0.736")).toBe(73); // 상세가 Math.round 로 74 를 보이던 값
    expect(queryScorePct("0.29")).toBe(29); // 보정 없는 Math.floor 로 28 을 보이던 값
    expect(queryScorePct("0.996")).toBe(99);
    expect(queryScorePct("1")).toBe(100);
  });

  it("0 점은 있는 점수다(0) — 없음(null)과 다르다", () => {
    expect(queryScorePct("0")).toBe(0);
    expect(queryScorePct("0.0")).toBe(0);
  });

  it("라우터가 같은 키를 배열로 풀어도 첫 값을 읽는다", () => {
    expect(queryScorePct(["0.5", "0.9"])).toBe(50);
  });

  it("없거나 숫자가 아니면 null", () => {
    expect(queryScorePct(undefined)).toBeNull();
    expect(queryScorePct(null)).toBeNull();
    expect(queryScorePct("")).toBeNull();
    expect(queryScorePct("  ")).toBeNull();
    expect(queryScorePct("abc")).toBeNull();
    expect(queryScorePct("NaN")).toBeNull();
    expect(queryScorePct([])).toBeNull();
  });
});

describe("detailScoreParams — 결과 카드에서 상세 주소로 싣는 점수", () => {
  it("종합·제목·내용 점수를 모두 싣는다(상세의 관련도 알약과 일치율 팝오버가 읽는다)", () => {
    expect(detailScoreParams({ best_score: 0.73, title_score: 0.8, content_score: 0.65 })).toEqual({
      score: "0.73",
      title_score: "0.8",
      content_score: "0.65",
    });
  });

  it("없는 점수는 싣지 않는다 — 옛 기록은 제목·내용 점수가 없을 수 있다", () => {
    expect(detailScoreParams({ best_score: 0.5 })).toEqual({ score: "0.5" });
    expect(detailScoreParams({ best_score: 0.5, title_score: undefined, content_score: null })).toEqual({ score: "0.5" });
    expect(detailScoreParams({})).toEqual({});
    expect(detailScoreParams(null)).toEqual({});
    expect(detailScoreParams(undefined)).toEqual({});
  });

  it("0 점은 싣고, 숫자가 아니거나 유한하지 않은 값은 뗀다", () => {
    expect(detailScoreParams({ best_score: 0, title_score: 0 })).toEqual({ score: "0", title_score: "0" });
    expect(detailScoreParams({ best_score: Number.NaN, title_score: "0.4", content_score: Infinity })).toEqual({});
  });

  it("실린 값은 상세가 읽는 queryScorePct 로 같은 퍼센트가 된다", () => {
    const params = detailScoreParams({ best_score: 0.7351, title_score: 0.29 });
    expect(queryScorePct(params.score)).toBe(relevancePct(0.7351));
    expect(queryScorePct(params.title_score)).toBe(29);
    expect(queryScorePct(params.content_score)).toBeNull();
  });
});

describe("scoreParam — 상세 주소에 싣는 점수는 소수 넷째 자리까지 버림", () => {
  it("긴 소수는 넷째 자리까지 버린다(서버 실측 0.9243096611209584 → 0.9243)", () => {
    expect(scoreParam(0.9243096611209584)).toBe("0.9243");
    expect(scoreParam(0.9388)).toBe("0.9388");
    expect(scoreParam(0.123456789)).toBe("0.1234");
  });

  it("끝의 0 은 빼서 싣는다(0.48 · 0.9 · 1 · 0)", () => {
    expect(scoreParam(0.48)).toBe("0.48");
    expect(scoreParam(0.9)).toBe("0.9");
    expect(scoreParam(0.5)).toBe("0.5");
    expect(scoreParam(1)).toBe("1");
    expect(scoreParam(0)).toBe("0");
  });

  it("올리지 않고 버린다 — 0.92999 → 0.9299(92%) 이지 0.93(93%) 이 아니다", () => {
    expect(scoreParam(0.92999)).toBe("0.9299");
    expect(scoreParam(0.99999)).toBe("0.9999");
    expect(scoreParam(0.00009)).toBe("0");
  });

  it("부동소수 오차로 한 칸 덜 나오지 않는다(0.29×10000 = 2899.9999…)", () => {
    expect(scoreParam(0.29)).toBe("0.29");
    expect(scoreParam(0.57)).toBe("0.57");
    expect(scoreParam(0.58)).toBe("0.58");
    expect(scoreParam(0.1 + 0.2)).toBe("0.3");
  });

  it("정수·0~1 밖은 자른다(음수 0, 1 초과 1)", () => {
    expect(scoreParam(-0.2)).toBe("0");
    expect(scoreParam(1.4)).toBe("1");
    expect(scoreParam(7)).toBe("1");
  });

  it("숫자가 아니거나 유한하지 않으면 null — null·undefined·문자열·NaN·Infinity", () => {
    for (const bad of [null, undefined, "0.5", "", "abc", Number.NaN, Infinity, -Infinity, {}, [], true]) {
      expect(scoreParam(bad), String(bad)).toBeNull();
    }
  });

  it("싣는 값은 항상 소수 넷째 자리 이하이고 다시 읽어도 같은 숫자다", () => {
    for (const x of [0.1, 0.12, 0.123, 0.1234, 0.12345678, 0.9388, 0.48, 0.9243096611209584, 1e-9, 0.99999999]) {
      const p = scoreParam(x)!;
      expect(p, String(x)).toMatch(/^(?:0|1|0\.\d{1,4})$/);
      expect(String(Number(p))).toBe(p);
    }
  });

  it("퍼센트가 바뀌지 않는다 — 싣기 전 점수와 싣고 난 뒤(상세가 읽는 값)의 relevancePct 가 같다(무작위 + 경계 값)", () => {
    // 결정적인 난수(같은 값열) — 실패하면 어느 값인지 보이게 한다
    let seed = 20261013;
    const rand = () => {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      return seed / 2 ** 32;
    };
    const samples: number[] = [];
    for (let i = 0; i < 20000; i++) samples.push(rand());
    // 퍼센트 경계 바로 아래·위(0.93 의 앞뒤 1e-12~1e-3)와 넷째 자리 경계
    for (let pct = 0; pct <= 100; pct++) {
      const b = pct / 100;
      for (const d of [1e-12, 1e-10, 1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3]) samples.push(b - d, b + d);
      samples.push(b);
    }
    for (let k = 0; k <= 10000; k += 7) samples.push(k / 10000, k / 10000 - 1e-12, k / 10000 + 1e-12);
    for (const x of samples) {
      const p = scoreParam(x);
      expect(p, String(x)).not.toBeNull();
      expect(relevancePct(Number(p)), `x=${x} → ${p}`).toBe(relevancePct(x));
    }
  });
});

describe("detailScoreParams — 세 점수가 같은 규칙(넷째 자리 버림)으로 실린다", () => {
  it("실측 값: 종합 0.9388 · 제목 0.48 · 내용 0.9243096611209584 → 0.9388 · 0.48 · 0.9243", () => {
    expect(detailScoreParams({ best_score: 0.9388, title_score: 0.48, content_score: 0.9243096611209584 })).toEqual({
      score: "0.9388",
      title_score: "0.48",
      content_score: "0.9243",
    });
  });

  it("긴 소수 세 점수 모두 넷째 자리까지만 싣는다", () => {
    const p = detailScoreParams({ best_score: 0.73456789, title_score: 0.80123456, content_score: 0.65987654 });
    expect(p).toEqual({ score: "0.7345", title_score: "0.8012", content_score: "0.6598" });
  });

  it("없는 점수·null·문자열은 싣지 않고 정수 1 과 0 은 싣는다", () => {
    expect(detailScoreParams({ best_score: 1, title_score: 0, content_score: null })).toEqual({ score: "1", title_score: "0" });
    expect(detailScoreParams({ best_score: "0.9", title_score: undefined })).toEqual({});
  });

  it("상세가 읽는 퍼센트가 싣기 전 점수의 퍼센트와 같다", () => {
    const item = { best_score: 0.92999, title_score: 0.4999999, content_score: 0.9243096611209584 };
    const p = detailScoreParams(item);
    expect(queryScorePct(p.score)).toBe(relevancePct(item.best_score));
    expect(queryScorePct(p.title_score)).toBe(relevancePct(item.title_score));
    expect(queryScorePct(p.content_score)).toBe(relevancePct(item.content_score));
    expect(queryScorePct(p.score)).toBe(92);
  });
});
