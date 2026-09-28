// frontend/tests/unit/citations.test.ts
import { describe, expect, it } from "vitest";
import type { ReportEvidence, ReportSection } from "~/types/research";
import { chunkListKey, citeChunks, citeLabel, metaLine, pageLabel, pdfPage, splitAuthors, splitCitations } from "~/utils/citations";

function chunk(id: string, score = 0.5, page = 3) {
  return { chunk_id: id, text: `본문 ${id}`, page_start: page, page_end: page, score };
}

const evidence: ReportEvidence = {
  cnts_id: "CNTS-1",
  meta: { title: "AI 윤리 교육", personal_author: "김철수; 이영희", pub_date: "2019-03" },
  // 보고서의 evidence.chunks 는 전역 최고점 순이다(synthesizer._serialize_evidence)
  chunks: [chunk("c1", 0.9), chunk("c2", 0.6), chunk("c3", 0.3)],
};

function section(map: Record<string, string[]>): ReportSection {
  return { heading: "h", intro: "", papers: [], future: [], evidence_chunks: map, chunk_scores: {} };
}

describe("splitCitations", () => {
  it("마커를 칩 조각으로, 나머지를 글 조각으로 나눈다", () => {
    expect(splitCitations("효과가 있다 [E1] 반면[E2][E3].")).toEqual([
      { type: "text", text: "효과가 있다 " },
      { type: "cite", eid: "E1" },
      { type: "text", text: " 반면" },
      { type: "cite", eid: "E2" },
      { type: "cite", eid: "E3" },
      { type: "text", text: "." },
    ]);
  });

  it("마커가 없으면 글 한 조각, 빈 글이면 빈 배열이다", () => {
    expect(splitCitations("근거 없음")).toEqual([{ type: "text", text: "근거 없음" }]);
    expect(splitCitations("")).toEqual([]);
  });

  it("표준형이 아닌 괄호는 글자 그대로 둔다", () => {
    expect(splitCitations("[e1] [E 2] [표 1]")).toEqual([{ type: "text", text: "[e1] [E 2] [표 1]" }]);
  });

  it("글 속 HTML 은 해석하지 않고 글 조각으로 남긴다", () => {
    expect(splitCitations("<img src=x onerror=alert(1)>[E1]")).toEqual([
      { type: "text", text: "<img src=x onerror=alert(1)>" },
      { type: "cite", eid: "E1" },
    ]);
  });
});

describe("splitAuthors", () => {
  it("세미콜론, 또는 이름마다 쉼표로 가른 여러 저자를 나눈다", () => {
    expect(splitAuthors("김철수; 이영희")).toEqual(["김철수", "이영희"]);
    expect(splitAuthors("김철수, 이영희")).toEqual(["김철수", "이영희"]);
    expect(splitAuthors("John Smith, Jane Doe")).toEqual(["John Smith", "Jane Doe"]);
  });

  it("성·이름을 쉼표로 가른 한 사람은 나누지 않는다", () => {
    expect(splitAuthors("Smith, John")).toEqual(["Smith, John"]);
    expect(splitAuthors("")).toEqual([]);
    expect(splitAuthors(null)).toEqual([]);
  });
});

describe("citeLabel", () => {
  it("한글 이름은 성과 연도로 줄인다", () => {
    expect(citeLabel(evidence.meta, "E1")).toBe("김 2019");
  });

  it("영문 이름은 성(쉼표 앞 또는 마지막 낱말)을 쓴다", () => {
    expect(citeLabel({ personal_author: "Smith, John", pub_date: "2020" }, "E2")).toBe("Smith 2020");
    expect(citeLabel({ personal_author: "John Smith", pub_date: "2020" }, "E2")).toBe("Smith 2020");
  });

  it("저자가 없으면 근거 번호, 연도가 없으면 성만 쓴다", () => {
    expect(citeLabel({ pub_date: "2020" }, "E3")).toBe("E3");
    expect(citeLabel({ personal_author: "박민수 외 2인" }, "E4")).toBe("박");
    expect(citeLabel(undefined, "E5")).toBe("E5");
  });
});

describe("metaLine", () => {
  it("비어 있는 칸을 빼고 가운뎃점으로 잇는다", () => {
    expect(metaLine({
      personal_author: "김철수", series_title: "교육학연구", vol_issue: "12(3)",
      pub_date: "2019-03", kci_citations: 0, grade: "KCI등재",
    })).toBe("김철수 · 교육학연구 12(3) · 2019 · 피인용 0 · KCI등재");
    expect(metaLine({ title: "제목만" })).toBe("");
  });
});

describe("pageLabel·pdfPage", () => {
  it("0 쪽은 첫 쪽과 구분할 수 없어 쪽 정보 없음으로 둔다", () => {
    expect(pageLabel({ page_start: 0, page_end: 0 })).toBe("쪽 정보 없음");
    expect(pdfPage({ page_start: 0 })).toBeUndefined();
  });

  it("0부터 센 쪽수를 1부터 세어 보여 준다", () => {
    expect(pageLabel({ page_start: 4, page_end: 4 })).toBe("p.5");
    expect(pageLabel({ page_start: 4, page_end: 6 })).toBe("p.5–7");
    expect(pdfPage({ page_start: 4 })).toBe(5);
  });
});

describe("citeChunks", () => {
  it("그 절에서 매칭된 대목만 서버가 준 절별 순서(그 하위질문의 점수 순) 그대로 고른다", () => {
    // 이 절의 검색어로는 c3 가 c1 보다 잘 맞았다 — 전역 최고점 순(c1, c3)으로 되돌리면 안 된다
    expect(citeChunks(section({ E1: ["c3", "c1"] }), evidence, "E1").map((c) => c.chunk_id)).toEqual(["c3", "c1"]);
  });

  it("절 매핑 가운데 근거에 없는 대목은 건너뛴다", () => {
    expect(citeChunks(section({ E1: ["c2", "zz", "c1"] }), evidence, "E1").map((c) => c.chunk_id)).toEqual(["c2", "c1"]);
  });

  it("절 매핑이 없거나 모르는 대목만 가리키면 근거의 대목 전부를 쓴다", () => {
    expect(citeChunks(section({}), evidence, "E1")).toHaveLength(3);
    expect(citeChunks(section({ E1: ["zz"] }), evidence, "E1")).toHaveLength(3);
    expect(citeChunks(undefined, evidence, "E1")).toHaveLength(3);
  });

  it("근거가 없으면 빈 배열이다", () => {
    expect(citeChunks(section({ E9: ["c1"] }), undefined, "E9")).toEqual([]);
  });
});

describe("chunkListKey", () => {
  it("초안이 최종본으로 바뀌어 같은 대목의 새 배열이 와도 열쇠는 같다 — 팝오버에서 보던 대목을 첫 대목으로 돌리지 않게", () => {
    const draftEv: ReportEvidence = { ...evidence, chunks: evidence.chunks.map((c) => ({ ...c })) };
    const map = section({ E1: ["c3", "c1"] });
    const inDraft = citeChunks(map, draftEv, "E1");
    const inFinal = citeChunks(map, evidence, "E1");
    expect(inFinal).not.toBe(inDraft);
    expect(chunkListKey(inFinal)).toBe(chunkListKey(inDraft));
  });

  it("대목이 바뀌면 열쇠도 바뀐다", () => {
    expect(chunkListKey([chunk("c1"), chunk("c2")])).not.toBe(chunkListKey([chunk("c1")]));
    expect(chunkListKey([chunk("c1"), chunk("c2")])).not.toBe(chunkListKey([chunk("c2"), chunk("c1")]));
  });
});
