// frontend/tests/unit/researchReport.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchReport } from "~/types/research";
import type { DraftSlot } from "~/utils/researchDraft";
import {
  draftBadge,
  draftIntro,
  draftStateFor,
  hideOnPointerLeave,
  paperByline,
  rangeLabel,
  reportIntro,
  reportSlot,
  stepChunk,
} from "~/utils/researchReport";

function report(over: Partial<ResearchReport> = {}): ResearchReport {
  return {
    question: "q",
    range: { from: "2002", to: "2026", n_papers: 1234 },
    sections: [],
    evidence: {
      E1: { cnts_id: "C1", meta: {}, chunks: [] },
      E2: { cnts_id: "C2", meta: {}, chunks: [] },
    },
    trail: [
      { subquestion: "가", queries: ["가"], evidence_count: 1, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0 },
      { subquestion: "나", queries: ["나"], evidence_count: 1, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0 },
      { subquestion: "다", queries: ["다"], evidence_count: 0, verdict: "insufficient", note: "", parse_failed: false, failed: false, capped: 0 },
    ],
    limitations: [],
    ...over,
  };
}

describe("rangeLabel", () => {
  it("수록 범위를 연도와 편수로 쓴다", () => {
    expect(rangeLabel({ from: "2002", to: "2026", n_papers: 1234 })).toBe("2002~2026 논문 1,234편 기준");
    expect(rangeLabel({ from: "2019", to: "2019", n_papers: 3 })).toBe("2019년 논문 3편 기준");
    expect(rangeLabel({ from: null, to: null, n_papers: 3 })).toBe("논문 3편 기준");
  });

  it("범위를 모르면 쓰지 않는다", () => {
    expect(rangeLabel(null)).toBeNull();
    expect(rangeLabel({})).toBeNull();
  });
});

describe("reportIntro", () => {
  it("stats 가 있으면 검토·채택 수를 쓴다", () => {
    expect(reportIntro(report({ stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 } })))
      .toBe("하위질문 3개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다.");
  });

  it("보강 전 보고서는 근거 수만 쓴다", () => {
    expect(reportIntro(report())).toBe("하위질문 3개로 나눠 논문 2편을 근거로 삼았다.");
  });

  it("trail 이 아직 없는 초안은 끝난 절 수가 아니라 넘겨받은 하위질문 수로 쓴다", () => {
    const sec = { heading: "가", intro: "", papers: [], future: [], evidence_chunks: {}, chunk_scores: {} };
    expect(reportIntro(report({ trail: [], sections: [sec] }), 3)).toBe("하위질문 3개로 나눠 논문 2편을 근거로 삼았다.");
  });
});

describe("stepChunk", () => {
  it("범위 안에서 한 칸씩 옮긴다", () => {
    expect(stepChunk(0, 1, 3)).toBe(1);
    expect(stepChunk(2, -1, 3)).toBe(1);
  });

  it("끝에서는 제자리에 선다", () => {
    expect(stepChunk(0, -1, 2)).toBe(0);
    expect(stepChunk(1, 1, 2)).toBe(1);
  });

  it("대목이 줄어 범위를 벗어난 위치는 마지막 대목으로 당기고, 대목이 없으면 0 이다", () => {
    expect(stepChunk(5, 1, 2)).toBe(1);
    expect(stepChunk(0, 1, 0)).toBe(0);
  });
});

describe("hideOnPointerLeave", () => {
  it("올려서만 연 팝오버는 포인터가 벗어나면 닫는다", () => {
    expect(hideOnPointerLeave(false, false)).toBe(true);
  });

  it("초점이 팝오버 안에 있으면 포인터가 벗어나도 닫지 않는다(닫기는 focusout 이 맡는다)", () => {
    expect(hideOnPointerLeave(false, true)).toBe(false);
  });

  it("클릭으로 고정한 팝오버는 닫지 않는다", () => {
    expect(hideOnPointerLeave(true, false)).toBe(false);
  });
});

describe("reportSlot", () => {
  it("끝나지 않은 연구는 보고서 칸을 그리지 않는다", () => {
    expect(reportSlot("exploring", false, false)).toBeNull();
    expect(reportSlot("failed", false, true)).toBeNull();
    expect(reportSlot(null, false, false)).toBeNull();
  });

  it("완료 이벤트 뒤 보고서를 받기 전에는 본문을 비우지 않고 불러오는 중으로 둔다", () => {
    expect(reportSlot("completed", false, false)).toBe("loading");
  });

  it("보고서를 받지 못하고 다시 시도하는 동안은 다시 불러오기를 보인다", () => {
    expect(reportSlot("completed", false, true)).toBe("failed");
  });

  it("보고서가 있으면 그 뒤의 재동기화 실패와 상관없이 보고서를 그린다", () => {
    expect(reportSlot("completed", true, false)).toBe("ready");
    expect(reportSlot("completed", true, true)).toBe("ready");
  });
});

describe("paperByline", () => {
  it("첫 저자와 연도, 여럿이면 외를 붙인다", () => {
    expect(paperByline({ personal_author: "김철수; 이영희", pub_date: "2019-03" })).toBe("김철수 외 (2019)");
    expect(paperByline({ personal_author: "김철수" })).toBe("김철수");
    expect(paperByline({ personal_author: "Smith, John", pub_date: "2021" })).toBe("Smith, John (2021)");
    expect(paperByline(undefined)).toBe("저자 미상");
  });
});

describe("draftIntro", () => {
  const slots: DraftSlot[] = [
    { idx: 0, heading: "가", status: "done", durationMs: 30_000, startedAt: null, sectionIndex: 0 },
    { idx: 1, heading: "나", status: "failed", durationMs: 20_000, startedAt: null, sectionIndex: 1 },
    { idx: 2, heading: "다", status: "running", durationMs: null, startedAt: null, sectionIndex: null },
    { idx: 3, heading: "라", status: "waiting", durationMs: null, startedAt: null, sectionIndex: null },
  ];

  const stats = { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 };

  it("전체 절 수는 슬롯으로, 쓴 절은 초안에 실린 절로 센다", () => {
    expect(draftIntro(slots, "writing")).toBe("4개 절 중 2개를 썼습니다. 다 쓴 절부터 먼저 보여 드립니다.");
  });

  it("라이브 카운터가 있으면 검토·채택 수를 덧붙인다", () => {
    expect(draftIntro(slots, "writing", stats))
      .toBe("4개 절 중 2개를 썼습니다. 다 쓴 절부터 먼저 보여 드립니다. 지금까지 논문 38편을 검토하고 11편을 근거로 삼았습니다.");
  });

  it("멈춘 초안은 완성되지 않았음과 한계가 빠졌음을 알린다", () => {
    expect(draftIntro(slots, "interrupted")).toBe("4개 절 중 2개를 쓰고 멈춘 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.");
    expect(draftIntro(slots, "interrupted", stats))
      .toBe("4개 절 중 2개를 쓰고 멈춘 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다. 지금까지 논문 38편을 검토하고 11편을 근거로 삼았습니다.");
  });

  it("작성을 마치고 완성본을 기다리는 초안은 더 쓰는 중이라고 하지 않는다", () => {
    expect(draftIntro(slots, "finishing")).toBe("4개 절을 모두 쓴 초안입니다. 서론과 한계 점검은 완성본에 실립니다.");
    expect(draftIntro(slots, "finishing", stats))
      .toBe("4개 절을 모두 쓴 초안입니다. 서론과 한계 점검은 완성본에 실립니다. 논문 38편을 검토하고 11편을 근거로 삼았습니다.");
  });
});

describe("draftStateFor", () => {
  it("보고서를 쓰는 동안은 작성 중, 실패·취소로 멈추면 멈춘 초안", () => {
    expect(draftStateFor("synthesizing", null)).toBe("writing");
    expect(draftStateFor("failed", null)).toBe("interrupted");
    expect(draftStateFor("canceled", null)).toBe("interrupted");
  });

  it("완료 뒤 최종본을 받는 동안·받기에 실패해 다시 시도하는 동안은 작성을 마친 초안", () => {
    expect(draftStateFor("completed", "loading")).toBe("finishing");
    expect(draftStateFor("completed", "failed")).toBe("finishing");
  });

  it("최종본을 받았거나 보고서를 쓰기 전이면 초안을 그리지 않는다", () => {
    expect(draftStateFor("completed", "ready")).toBeNull();
    for (const phase of ["planning", "awaiting", "queued", "exploring"] as const) {
      expect(draftStateFor(phase, null)).toBeNull();
    }
    expect(draftStateFor(null, null)).toBeNull();
  });
});

describe("draftBadge", () => {
  it("쓰는 동안에만 깜빡이는 점을 단다 — 작성을 마쳤거나 멈춘 초안은 차분하게", () => {
    expect(draftBadge("writing")).toEqual({ label: "작성 중", live: true });
    expect(draftBadge("finishing")).toEqual({ label: "작성을 마친 초안", live: false });
    expect(draftBadge("interrupted")).toEqual({ label: "완성되지 않은 초안", live: false });
  });
});
