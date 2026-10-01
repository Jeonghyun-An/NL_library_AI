// frontend/tests/unit/detailSource.test.ts
import { describe, expect, it } from "vitest";
import type { ReportSection } from "~/types/research";
import {
  anchorSelector,
  anchoredSection,
  backTarget,
  citeAnchor,
  detailUrl,
  excludedAnchor,
  excludedDetailUrl,
  isUuid,
  parseAnchor,
  readDetailSource,
  readReturnSpot,
  relatedDetailUrl,
  resultAnchor,
  shouldGoBack,
} from "~/utils/detailSource";
import { ID1, ID2 } from "./helpers/fakeHistory";

const MIXED = "AbCdEf01-2345-4789-abcd-0123456789ab";
const NO_SPOT = { at: null, y: null };

function section(over: Partial<ReportSection> = {}): ReportSection {
  return { heading: "절", intro: "", papers: [], future: [], evidence_chunks: {}, chunk_scores: {}, ...over };
}

describe("isUuid", () => {
  it("버전을 가리지 않고 UUID 모양만 받는다", () => {
    expect(isUuid(ID1)).toBe(true);
    expect(isUuid(MIXED)).toBe(true);
    expect(isUuid("1727000000000")).toBe(false);
    expect(isUuid("../../admin")).toBe(false);
  });
});

describe("readDetailSource", () => {
  it("검색 출처는 h·q 를 읽고 h 는 소문자로 맞춘다", () => {
    expect(readDetailSource({ from: "search", h: MIXED, q: " 딥러닝 " })).toEqual({
      kind: "search",
      h: MIXED.toLowerCase(),
      q: "딥러닝",
    });
    expect(readDetailSource({ from: "search", q: "딥러닝" })).toEqual({ kind: "search", h: null, q: "딥러닝" });
    expect(readDetailSource({ from: "search", h: ID1 })).toEqual({ kind: "search", h: ID1, q: "" });
  });

  it("딥리서치 출처는 잡 id 가 UUID 일 때만, 근거 번호는 E# 모양만 받는다", () => {
    expect(readDetailSource({ from: "research", job: ID2, e: "E3" })).toEqual({ kind: "research", job: ID2, e: "E3" });
    expect(readDetailSource({ from: "research", job: ID2, e: "<b>" })).toEqual({ kind: "research", job: ID2, e: null });
    expect(readDetailSource({ from: "research", job: "abc", e: "E3" })).toEqual({ kind: "none" });
  });

  it("from 이 없거나 모르는 값, 기록·검색어가 모두 틀린 검색 출처는 출처 없음이다", () => {
    expect(readDetailSource({ q: "딥러닝", h: ID1 })).toEqual({ kind: "none" });
    expect(readDetailSource({ from: "elsewhere", job: ID2 })).toEqual({ kind: "none" });
    expect(readDetailSource({ from: "search", h: "../../admin", q: "  " })).toEqual({ kind: "none" });
  });

  it("배열은 첫 값을 쓴다", () => {
    expect(readDetailSource({ from: ["research", "search"], job: [ID2, ID1] })).toEqual({
      kind: "research",
      job: ID2,
      e: null,
    });
  });
});

describe("readReturnSpot", () => {
  it("앵커 문법에 맞는 at 과 0 이상 정수 y 를 읽는다", () => {
    expect(readReturnSpot({ at: "c-2-E3-1", y: "240" })).toEqual({ at: "c-2-E3-1", y: 240 });
    expect(readReturnSpot({ at: "p-KCI_FI001484593", y: "0" })).toEqual({ at: "p-KCI_FI001484593", y: 0 });
  });

  it("문법 밖의 at 은 버리고, y 만으로는 자리를 정하지 않는다", () => {
    expect(readReturnSpot({ at: 'x-"]<b>', y: "10" })).toEqual(NO_SPOT);
    expect(readReturnSpot({ y: "10" })).toEqual(NO_SPOT);
  });

  it("음수·소수·없는 y 는 버리고 at 은 남긴다", () => {
    expect(readReturnSpot({ at: "x-C1", y: "-4" })).toEqual({ at: "x-C1", y: null });
    expect(readReturnSpot({ at: "x-C1", y: "12.5" })).toEqual({ at: "x-C1", y: null });
    expect(readReturnSpot({ at: "x-C1" })).toEqual({ at: "x-C1", y: null });
  });
});

describe("detailUrl·relatedDetailUrl·excludedDetailUrl", () => {
  const search = { kind: "search", h: ID1, q: "nlp" } as const;
  const research = { kind: "research", job: ID2, e: "E3" } as const;

  it("출처·돌아갈 자리·덧붙일 값을 순서대로 싣는다", () => {
    expect(detailUrl("CNTS-1", search, { at: "p-CNTS-1", y: 320 }, { score: "0.83" })).toBe(
      `/papers/CNTS-1?from=search&h=${ID1}&q=nlp&at=p-CNTS-1&y=320&score=0.83`,
    );
    expect(detailUrl("CNTS-1", research, { at: "c-0-E3", y: 120 })).toBe(
      `/papers/CNTS-1?from=research&job=${ID2}&e=E3&at=c-0-E3&y=120`,
    );
  });

  it("출처가 없으면 덧붙일 값만 싣는다", () => {
    expect(detailUrl("CNTS-1", { kind: "none" })).toBe("/papers/CNTS-1");
    expect(detailUrl("CNTS-1", { kind: "none" }, undefined, { chat: "1" })).toBe("/papers/CNTS-1?chat=1");
  });

  it("y 는 at 이 있을 때만 싣는다", () => {
    expect(detailUrl("CNTS-1", research, { at: null, y: 40 })).toBe(`/papers/CNTS-1?from=research&job=${ID2}&e=E3`);
    expect(detailUrl("CNTS-1", research, { at: "x-CNTS-1", y: null })).toBe(
      `/papers/CNTS-1?from=research&job=${ID2}&e=E3&at=x-CNTS-1`,
    );
  });

  it("만든 주소를 다시 읽으면 같은 출처·자리가 나온다", () => {
    const src = { kind: "search", h: ID1, q: "딥러닝 자연어 처리" } as const;
    const url = new URL(detailUrl("CNTS-1", src, { at: "p-CNTS-1", y: 15 }), "http://local");
    const query = Object.fromEntries(url.searchParams);
    expect(readDetailSource(query)).toEqual(src);
    expect(readReturnSpot(query)).toEqual({ at: "p-CNTS-1", y: 15 });
  });

  it("연관 논문은 처음 출처와 돌아갈 자리를 잇고 e·score 는 뗀다", () => {
    expect(relatedDetailUrl("CNTS-9", research, { at: "c-1-E3", y: 200 })).toBe(
      `/papers/CNTS-9?from=research&job=${ID2}&at=c-1-E3&y=200`,
    );
    expect(relatedDetailUrl("CNTS-9", search, { at: "p-CNTS-1", y: 80 })).toBe(
      `/papers/CNTS-9?from=search&h=${ID1}&q=nlp&at=p-CNTS-1&y=80`,
    );
    expect(relatedDetailUrl("CNTS-9", { kind: "none" }, NO_SPOT)).toBe("/papers/CNTS-9");
  });

  it("제외한 논문 링크는 근거 번호 없이 그 항목 앵커를 싣는다", () => {
    expect(excludedDetailUrl(ID2, "C1")).toBe(`/papers/C1?from=research&job=${ID2}&at=x-C1`);
    expect(excludedDetailUrl(ID2, "C1", 88)).toBe(`/papers/C1?from=research&job=${ID2}&at=x-C1&y=88`);
  });
});

describe("backTarget", () => {
  it("검색 출처는 검색 결과 주소로, 자리를 함께 넘긴다", () => {
    expect(backTarget({ kind: "search", h: ID1, q: "nlp" }, { at: "p-CNTS-1", y: 300 })).toEqual({
      label: "검색 결과로",
      to: `/papers?h=${ID1}&q=nlp&at=p-CNTS-1&y=300`,
    });
    expect(backTarget({ kind: "search", h: null, q: "nlp" }, NO_SPOT)).toEqual({
      label: "검색 결과로",
      to: "/papers?q=nlp",
    });
  });

  it("딥리서치 출처는 보고서 주소로 간다", () => {
    expect(backTarget({ kind: "research", job: ID2, e: "E3" }, { at: "c-0-E3", y: 120 })).toEqual({
      label: "딥리서치 보고서로",
      to: `/research/${ID2}?at=c-0-E3&y=120`,
    });
    expect(backTarget({ kind: "research", job: ID2, e: null }, NO_SPOT)).toEqual({
      label: "딥리서치 보고서로",
      to: `/research/${ID2}`,
    });
  });

  it("출처가 없으면 홈 검색으로 간다", () => {
    expect(backTarget({ kind: "none" }, { at: "p-CNTS-1", y: 10 })).toEqual({ label: "검색으로", to: "/" });
  });
});

describe("shouldGoBack", () => {
  it("직전 기록이 같은 보고서면 at·y 가 달라도 뒤로 간다", () => {
    expect(shouldGoBack(`/research/${ID2}?at=c-0-E3&y=120`, `/research/${ID2}?at=c-0-E3&y=99`)).toBe(true);
    expect(shouldGoBack(`/research/${ID2}`, `/research/${ID2}?at=c-0-E3&y=120`)).toBe(true);
  });

  it("검색 결과는 같은 기록 id 면, 기록 id 가 없으면 같은 검색어면 뒤로 간다", () => {
    expect(shouldGoBack(`/papers?q=nlp&h=${ID1}&at=p-C1&y=5`, `/papers?h=${ID1}&q=nlp&at=p-C1&y=5`)).toBe(true);
    expect(shouldGoBack(`/papers?q=nlp&h=${ID2}`, `/papers?h=${ID1}&q=nlp`)).toBe(false);
    expect(shouldGoBack("/papers?q=nlp", "/papers?q=nlp&at=p-C1&y=5")).toBe(true);
    expect(shouldGoBack("/papers?q=other", "/papers?q=nlp")).toBe(false);
  });

  it("직전 기록이 없거나 다른 화면(연관 논문 등)이면 뒤로 가지 않는다", () => {
    expect(shouldGoBack(null, `/research/${ID2}`)).toBe(false);
    expect(shouldGoBack(`/papers/CNTS-1?from=research&job=${ID2}`, `/research/${ID2}`)).toBe(false);
    expect(shouldGoBack(`/research/${ID1}`, `/research/${ID2}`)).toBe(false);
    expect(shouldGoBack(`/?h=${ID1}&q=경제`, "/")).toBe(false);
    expect(shouldGoBack("/", "/")).toBe(true);
  });
});

describe("앵커", () => {
  it("인용칩·제외 목록·검색 결과 앵커를 만들고 다시 읽는다", () => {
    expect(citeAnchor(2, "E3")).toBe("c-2-E3");
    expect(citeAnchor(2, "E3", 1)).toBe("c-2-E3-1");
    expect(excludedAnchor("KCI_FI001484593")).toBe("x-KCI_FI001484593");
    expect(resultAnchor("CNTS-00049204004")).toBe("p-CNTS-00049204004");
    expect(parseAnchor(citeAnchor(0, "E12", 2))).toEqual({ kind: "cite", section: 0, eid: "E12", n: 2 });
    expect(parseAnchor(citeAnchor(3, "E1"))).toEqual({ kind: "cite", section: 3, eid: "E1", n: 0 });
    expect(parseAnchor(excludedAnchor("C1"))).toEqual({ kind: "excluded", cnts: "C1" });
    expect(parseAnchor(resultAnchor("CNTS-1"))).toEqual({ kind: "result", cnts: "CNTS-1" });
  });

  it("문법 밖의 값은 null — 선택자에 따옴표·괄호·공백이 끼지 않는다", () => {
    for (const bad of ["", "c-01-E3", "c-1-X3", "c-1-E3-0", "q-C1", 'p-C1"]', "x-", "p-a b"]) {
      expect(parseAnchor(bad)).toBeNull();
      expect(anchorSelector(bad)).toBeNull();
    }
    expect(anchorSelector("c-1-E3-2")).toBe('[data-anchor="c-1-E3-2"]');
  });
});

describe("anchoredSection", () => {
  it("그리는 순서(도입 → 대표 논문 → 향후 과제)대로 같은 근거 칩에 순번을 붙인다", () => {
    const sec = section({
      intro: "앞 [E1] 가운데 [E2] 뒤 [E1]",
      papers: [{ cnts_id: "C1", summary: "요약", evidence: ["E1", "E3"] }],
      future: [{ text: "과제 [E3]", evidence: ["E3"] }],
    });
    const out = anchoredSection(sec, 4);
    expect(out.intro).toEqual([
      { type: "text", text: "앞 " },
      { type: "cite", eid: "E1", anchor: "c-4-E1" },
      { type: "text", text: " 가운데 " },
      { type: "cite", eid: "E2", anchor: "c-4-E2" },
      { type: "text", text: " 뒤 " },
      { type: "cite", eid: "E1", anchor: "c-4-E1-1" },
    ]);
    expect(out.papers).toEqual([
      {
        paper: sec.papers[0],
        chips: [
          { eid: "E1", anchor: "c-4-E1-2" },
          { eid: "E3", anchor: "c-4-E3" },
        ],
      },
    ]);
    expect(out.future).toEqual([
      [
        { type: "text", text: "과제 " },
        { type: "cite", eid: "E3", anchor: "c-4-E3-1" },
      ],
    ]);
  });

  it("도입이 비면 도입 조각이 없다", () => {
    expect(anchoredSection(section(), 0)).toEqual({ intro: [], papers: [], future: [] });
  });
});
