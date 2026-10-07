// frontend/tests/unit/evidenceLedger.test.ts
import { describe, expect, it } from "vitest";
import type { AdoptedPaperView, ExcludedPaperView, RoundView, SubqView } from "~/types/research";
import { hasLedger, ledgerFrom, ledgerLine, newlyAdded } from "~/utils/evidenceLedger";

function adopted(cntsId: string, rank: number, bib?: { title: string; author?: string; date?: string }): AdoptedPaperView {
  return bib
    ? { cntsId, rank, title: bib.title, personalAuthor: bib.author ?? null, pubDate: bib.date ?? null, isNew: true }
    : { cntsId, rank, title: null, personalAuthor: null, pubDate: null, isNew: false };
}

function excluded(cntsId: string, title = ""): ExcludedPaperView {
  return { cntsId, title, personalAuthor: title ? "김철수" : null, pubDate: title ? "2015" : null };
}

function round(n: number, over: Partial<RoundView> = {}): RoundView {
  return {
    round: n, query: `질의 ${n}`, foundChunks: 10, newPapers: 3, verdict: "sufficient", note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [], ...over,
  };
}

function subq(idx: number, rounds: RoundView[]): SubqView {
  return {
    idx, title: `하위질문 ${idx + 1}`, seq: idx + 1, status: "done", rounds,
    verdict: "sufficient", note: "", adopted: null, parseFailed: false, error: null,
  };
}

const C1 = { title: "노인 우울과 가족 지지", author: "김철수; 이영희", date: "2013" };
const C2 = { title: "지역사회 지지의 효과", author: "박민수", date: "2016-05" };
const C3 = { title: "사회적 지지 척도 비교", author: "최지은", date: "2019" };

describe("hasLedger", () => {
  it("어느 회차에든 채택 목록이 있으면 그린다", () => {
    expect(hasLedger([subq(0, [round(1, { adoptedPapers: [adopted("C1", 1, C1)] })])])).toBe(true);
  });

  it("채택 목록을 기록하기 전 잡(06a 전)·회차가 없는 화면은 그리지 않는다", () => {
    expect(hasLedger([subq(0, [round(1), round(2)]), subq(1, [])])).toBe(false);
    expect(hasLedger([])).toBe(false);
  });
});

describe("ledgerFrom — 채택", () => {
  it("하위질문마다 마지막 회차의 채택을 하위질문 순 → 순위 순으로 합치고, 서지는 앞 회차의 새 채택에서 찾는다", () => {
    const subqs = [
      subq(0, [
        round(1, { verdict: "insufficient", adoptedPapers: [adopted("C1", 1, C1)] }),
        round(2, { adoptedPapers: [adopted("C2", 1, C2), adopted("C1", 2)] }),
      ]),
      subq(1, [round(1, { adoptedPapers: [adopted("C3", 1, C3), adopted("C1", 2, C1)] })]),
    ];
    const l = ledgerFrom(subqs);
    expect(l.adopted).toEqual([
      { cntsId: "C2", title: C2.title, personalAuthor: C2.author, pubDate: C2.date, subqIdx: [0], round: 2, isNew: true },
      { cntsId: "C1", title: C1.title, personalAuthor: C1.author, pubDate: C1.date, subqIdx: [0, 1], round: 1, isNew: true },
      { cntsId: "C3", title: C3.title, personalAuthor: C3.author, pubDate: C3.date, subqIdx: [1], round: 1, isNew: true },
    ]);
  });

  it("마지막 회차가 앞 회차의 채택을 뺐으면 장부에서도 빠진다", () => {
    const l = ledgerFrom([
      subq(0, [
        round(1, { verdict: "insufficient", adoptedPapers: [adopted("C1", 1, C1), adopted("C2", 2, C2)] }),
        round(2, { adoptedPapers: [adopted("C2", 1)], excludedPapers: [excluded("C1", C1.title)] }),
      ]),
    ]);
    expect(l.adopted.map((p) => [p.cntsId, p.isNew, p.title])).toEqual([["C2", false, C2.title]]);
    expect(l.dropped.map((p) => [p.cntsId, p.round, p.isNew])).toEqual([["C1", 2, true]]);
  });

  it("검색만 끝나고 점검을 기다리는 회차는 건너뛰고 점검이 끝난 마지막 회차를 쓴다", () => {
    const l = ledgerFrom([
      subq(0, [
        round(1, { verdict: "insufficient", adoptedPapers: [adopted("C1", 1, C1)] }),
        round(2, { verdict: null, adoptedPapers: [] }),
      ]),
    ]);
    expect(l.adopted.map((p) => p.cntsId)).toEqual(["C1"]);
    expect(ledgerFrom([subq(0, [round(1, { verdict: null })])])).toEqual({ adopted: [], dropped: [] });
  });

  it("서지를 어디서도 찾지 못하면 null 로 둔다(화면은 cnts_id 를 보인다)", () => {
    const l = ledgerFrom([subq(0, [round(3, { adoptedPapers: [adopted("C9", 1)] })])]);
    expect(l.adopted[0]).toEqual({
      cntsId: "C9", title: null, personalAuthor: null, pubDate: null, subqIdx: [0], round: 3, isNew: false,
    });
  });
});

describe("ledgerFrom — 뺌", () => {
  it("탐색이 지나간 순서로 중복 없이 모으고, 다른 하위질문에 채택된 논문은 뺌에 두지 않는다", () => {
    const l = ledgerFrom([
      subq(0, [
        round(1, { verdict: "insufficient", excludedPapers: [excluded("X1", "무관한 논문 1"), excluded("C3", C3.title)] }),
        round(2, { adoptedPapers: [adopted("C1", 1, C1)], excludedPapers: [excluded("X2")] }),
      ]),
      subq(1, [round(1, { adoptedPapers: [adopted("C3", 1, C3)], excludedPapers: [excluded("X1", "무관한 논문 1")] })]),
    ]);
    expect(l.dropped).toEqual([
      { cntsId: "X1", title: "무관한 논문 1", personalAuthor: "김철수", pubDate: "2015", subqIdx: [0, 1], round: 1, isNew: true },
      { cntsId: "X2", title: null, personalAuthor: null, pubDate: null, subqIdx: [0], round: 2, isNew: true },
    ]);
    expect(l.adopted.map((p) => p.cntsId)).toEqual(["C1", "C3"]);
  });

  it("뺀 논문의 isNew 는 그 하위질문의 마지막 점검 회차에 뺐는가다", () => {
    const l = ledgerFrom([
      subq(0, [
        round(1, { verdict: "insufficient", excludedPapers: [excluded("X1", "앞 회차에 뺌")] }),
        round(2, { adoptedPapers: [adopted("C1", 1, C1)] }),
      ]),
    ]);
    expect(l.dropped.map((p) => [p.cntsId, p.isNew])).toEqual([["X1", false]]);
  });

  it("받은 하위질문을 고치지 않는다", () => {
    const subqs = [subq(0, [round(1, { adoptedPapers: [adopted("C1", 1, C1)], excludedPapers: [excluded("X1", "x")] })])];
    const before = JSON.stringify(subqs);
    ledgerFrom(subqs);
    expect(JSON.stringify(subqs)).toBe(before);
  });
});

describe("ledgerLine·newlyAdded", () => {
  const l = ledgerFrom([
    subq(0, [round(1, { adoptedPapers: [adopted("C1", 1, C1), adopted("C2", 2, C2)], excludedPapers: [excluded("X1", "x")] })]),
  ]);

  it("채택·뺌 수 한 줄", () => {
    expect(ledgerLine(l)).toBe("채택 2 · 뺌 1");
    expect(ledgerLine({ adopted: [], dropped: [] })).toBe("채택 0 · 뺌 0");
  });

  it("직전 장부에 없던 논문만 새로 들어온 것으로 보고, 처음 그릴 때는 없다", () => {
    expect(newlyAdded(null, l.adopted)).toEqual([]);
    expect(newlyAdded(new Set(["C1"]), l.adopted)).toEqual(["C2"]);
    expect(newlyAdded(new Set(["C1", "C2"]), l.adopted)).toEqual([]);
  });
});
