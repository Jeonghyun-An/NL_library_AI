// frontend/tests/unit/reportDocument.test.ts
import { describe, expect, it } from "vitest";
import type {
  ReportChunk,
  ReportEvidence,
  ReportSection,
  ResearchReport,
  ResearchView,
  RoundView,
  SubqView,
} from "~/types/research";
import type { DraftReport } from "~/utils/researchDraft";
import {
  buildReportDocument,
  docInputFromDraft,
  docInputFromReport,
  docRunText,
  reportFileName,
  type DocBlock,
  type ReportDoc,
  type ReportDocInput,
} from "~/utils/reportDocument";
import { reportIntro } from "~/utils/researchReport";
import citationReference from "../fixtures/citation_reference.json";

// 한국 시각 2026-09-28 15:05
const NOW = new Date("2026-09-28T06:05:00Z");

function chunk(id: string, page: number, pageEnd = page): ReportChunk {
  return { chunk_id: id, text: `대목 ${id}`, page_start: page, page_end: pageEnd, score: 0.5 };
}

function ev(cntsId: string, meta: ReportEvidence["meta"] = {}, chunks: ReportChunk[] = []): ReportEvidence {
  return { cnts_id: cntsId, meta, chunks };
}

function section(over: Partial<ReportSection> = {}): ReportSection {
  return { heading: "절", intro: "", papers: [], future: [], evidence_chunks: {}, chunk_scores: {}, ...over };
}

function input(over: Partial<ReportDocInput> = {}): ReportDocInput {
  return {
    question: "국내 AI 규제 연구 동향",
    range: null,
    generatedAt: null,
    url: "",
    intro: "",
    sections: [],
    evidence: {},
    limitations: [],
    trail: [],
    excluded: [],
    draft: null,
    ...over,
  };
}

function lineOf(b: DocBlock): string {
  switch (b.type) {
    case "para":
      return b.runs.map(docRunText).join("");
    case "bullets":
      return b.items.map((runs) => runs.map(docRunText).join("")).join(" / ");
    default:
      return b.text;
  }
}

// 블록을 "종류: 글" 한 줄씩 — 문서의 뼈대를 한눈에 비교한다
function lines(doc: ReportDoc): string[] {
  return doc.blocks.map((b) => `${b.type}${b.type === "heading" ? b.level : ""}: ${lineOf(b)}`);
}

describe("docRunText", () => {
  it("글 조각은 그대로, 인용은 [번호] 로 쓴다", () => {
    expect(docRunText({ text: "효과가 있다" })).toBe("효과가 있다");
    expect(docRunText({ cite: 3 })).toBe("[3]");
  });
});

describe("buildReportDocument — 구성", () => {
  it("제목 → 메타 → 서론 → 절(도입·대표 논문·향후 과제) → 한계 → 부록 순으로 쌓는다", () => {
    const doc = buildReportDocument(
      input({
        generatedAt: "2026-09-27T23:30:00Z",
        range: { from: "2002", to: "2026", n_papers: 1234 },
        url: "http://nl.example/research/abc",
        intro: "하위질문 1개로 나눠 논문 3편을 검토하고 1편을 근거로 삼았다.",
        sections: [
          section({
            heading: "규제 논의의 흐름",
            intro: "논의가 늘었다 [E1].",
            papers: [
              { cnts_id: "C1", summary: "규제 샌드박스를 분석했다", evidence: ["E1"] },
              { cnts_id: "C2", summary: "", evidence: [] },
            ],
            future: [{ text: "국제 비교가 필요하다 [E1]", evidence: ["E1"] }],
          }),
        ],
        evidence: { E1: ev("C1", { title: "AI 규제", personal_author: "김철수; 이영희", pub_date: "2021" }) },
        limitations: ["근거가 1편뿐인 절이 있다."],
        trail: [
          { subquestion: "규제 논의의 흐름", queries: ["AI 규제", "AI 규제 샌드박스"], verdict: "sufficient", evidenceCount: 1, excluded: 0 },
        ],
      }),
      NOW,
    );
    expect(lines(doc)).toEqual([
      "title: 국내 AI 규제 연구 동향",
      "meta: 생성 일시 2026년 9월 28일 08:30",
      "meta: 수록 범위 2002~2026 논문 1,234편 기준",
      "meta: 연구 주소 http://nl.example/research/abc",
      "para: 하위질문 1개로 나눠 논문 3편을 검토하고 1편을 근거로 삼았다.",
      "heading1: 1. 규제 논의의 흐름",
      "para: 논의가 늘었다 [1].",
      "heading2: 대표 논문",
      "bullets: 김철수 외 (2021) 「AI 규제」 — 규제 샌드박스를 분석했다 [1] / 저자 미상 — 요약을 받지 못했습니다.",
      "heading2: 향후 과제",
      "bullets: 국제 비교가 필요하다 [1]",
      "heading1: 이 보고서의 한계",
      "bullets: 근거가 1편뿐인 절이 있다.",
      "heading1: 부록: 탐색 경로",
      "heading2: 1. 규제 논의의 흐름",
      "bullets: 검색어: ‘AI 규제’ → ‘AI 규제 샌드박스’ (재검색 1회) / 판정: 근거 충분 / 채택한 근거: 1편",
    ]);
    expect(doc.fileName).toBe("딥리서치_국내_AI_규제_연구_동향_20260928.docx");
  });

  it("생성 시각을 모르면 지금 시각을 쓰고, 범위·주소가 없으면 그 줄을 뺀다", () => {
    const doc = buildReportDocument(input({ generatedAt: "잘못된 값" }), NOW);
    expect(doc.blocks.filter((b) => b.type === "meta").map(lineOf)).toEqual(["생성 일시 2026년 9월 28일 15:05"]);
  });

  it("도입이 없는 절은 화면과 같은 안내를, 한계가 없으면 화면과 같은 문구를 흐리게 싣는다", () => {
    const doc = buildReportDocument(input({ sections: [section({ heading: "빈 절" })], limitations: [] }), NOW);
    expect(doc.blocks).toContainEqual({
      type: "para",
      runs: [{ text: "이 절은 도입 서술을 받지 못했습니다. 아래 논문 목록만 싣습니다." }],
      muted: true,
    });
    expect(doc.blocks).toContainEqual({
      type: "para",
      runs: [{ text: "자동 점검에서 보고할 한계가 발견되지 않았습니다." }],
      muted: true,
    });
  });

  it("부록은 하위질문마다 검색어 이력·판정·채택한 근거 수를 싣고, 모르는 칸은 뺀다", () => {
    const doc = buildReportDocument(
      input({
        trail: [
          { subquestion: "가", queries: ["가"], verdict: "insufficient", evidenceCount: 0, excluded: 0 },
          { subquestion: "나", queries: [], verdict: null, evidenceCount: null, excluded: 0 },
        ],
      }),
      NOW,
    );
    const all = lines(doc);
    expect(all.slice(all.indexOf("heading1: 부록: 탐색 경로"))).toEqual([
      "heading1: 부록: 탐색 경로",
      "heading2: 1. 가",
      "bullets: 검색어: ‘가’ / 판정: 근거 부족 / 채택한 근거: 0편",
      "heading2: 2. 나",
    ]);
  });

  it("부록은 자기점검이 무관하다고 뺀 근거 수를 탐색 타임라인과 같은 문구로 싣는다", () => {
    const doc = buildReportDocument(
      input({
        trail: [
          { subquestion: "엣지 컴퓨팅", queries: ["엣지 컴퓨팅", "엣지 컴퓨팅 자원 할당"], verdict: "sufficient", evidenceCount: 6, excluded: 3 },
        ],
      }),
      NOW,
    );
    const all = lines(doc);
    expect(all.slice(all.indexOf("heading1: 부록: 탐색 경로"))).toEqual([
      "heading1: 부록: 탐색 경로",
      "heading2: 1. 엣지 컴퓨팅",
      "bullets: 검색어: ‘엣지 컴퓨팅’ → ‘엣지 컴퓨팅 자원 할당’ (재검색 1회) / 판정: 근거 충분 / 채택한 근거: 6편 / 무관 3편 제외",
    ]);
  });

  it("제외한 논문은 탐색 경로 부록 뒤에 하위질문별로 싣고 참고문헌 번호를 매기지 않는다", () => {
    const doc = buildReportDocument(
      input({
        sections: [section({ heading: "엣지 컴퓨팅", intro: "자원을 나눈다 [E1]." })],
        evidence: { E1: ev("C1", { title: "엣지 자원 할당", personal_author: "김철수", pub_date: "2021" }) },
        trail: [{ subquestion: "엣지 컴퓨팅", queries: ["엣지 컴퓨팅"], verdict: "sufficient", evidenceCount: 1, excluded: 2 }],
        excluded: [{
          subqIdx: 0,
          subquestion: "엣지 컴퓨팅",
          papers: [
            { cntsId: "C8", title: "의료영상 Edge method", personalAuthor: "최지훈", pubDate: "2011" },
            { cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수; 이영희", pubDate: "2008-05" },
          ],
        }],
      }),
      NOW,
    );
    const all = lines(doc);
    expect(all.slice(all.indexOf("heading1: 부록: 탐색 경로"))).toEqual([
      "heading1: 부록: 탐색 경로",
      "heading2: 1. 엣지 컴퓨팅",
      "bullets: 검색어: ‘엣지 컴퓨팅’ / 판정: 근거 충분 / 채택한 근거: 1편 / 무관 2편 제외",
      "heading1: 부록: 관련성이 낮아 제외한 논문",
      "para: 자기점검이 하위질문의 핵심 개념과 무관하다고 판단해 근거에서 제외한 논문입니다. 인용한 근거가 아니어서 참고문헌 번호를 매기지 않습니다.",
      "heading2: 1. 엣지 컴퓨팅",
      "bullets: 최지훈 (2011) 「의료영상 Edge method」 / 박민수 외 (2008) 「CMOS 에지 검출 회로」",
    ]);
    // 참고문헌은 본문이 인용한 근거뿐이다 — 뺀 논문은 글 조각으로만 적힌다
    expect(doc.references.map((r) => r.eid)).toEqual(["E1"]);
  });

  it("제외한 논문이 없으면 그 부록을 싣지 않는다", () => {
    const doc = buildReportDocument(
      input({ trail: [{ subquestion: "가", queries: ["가"], verdict: "sufficient", evidenceCount: 1, excluded: 0 }] }),
      NOW,
    );
    expect(lines(doc)).not.toContain("heading1: 부록: 관련성이 낮아 제외한 논문");
  });

  it("탐색 경로가 없으면 부록을 싣지 않는다", () => {
    const doc = buildReportDocument(input(), NOW);
    expect(lines(doc)).not.toContain("heading1: 부록: 탐색 경로");
  });

  // 합성 출력의 JSON 을 풀면 LLM 이 쓴 LaTeX(\frac·\beta)가 이스케이프 \f·\b 로 풀려 제어문자가 된다
  it("XML 에 쓸 수 없는 제어문자는 모든 블록과 참고문헌에서 뺀다 — Word·인쇄가 같은 글을 쓴다", () => {
    const doc = buildReportDocument(
      input({
        question: "국내\u0001 AI 규제",
        intro: "서론\u000B 문\uFFFE장\uFFFF",
        sections: [
          section({
            heading: "계수\u0008 추정",
            intro: "\u000Crac{1}{2} 로 적는다 [E1].",
            papers: [{ cnts_id: "C1", summary: "\u0008eta 계수를 추정했다", evidence: ["E1"] }],
            future: [{ text: "과제\u001F 하나", evidence: [] }],
          }),
        ],
        evidence: { E1: ev("C1", { title: "회귀\u0007 분석", personal_author: "김철수", pub_date: "2019" }) },
        limitations: ["한계\u000E 문장"],
        trail: [{ subquestion: "하위\u0002질문", queries: ["검색\u0003어"], verdict: null, evidenceCount: null, excluded: 0 }],
      }),
      NOW,
    );
    const all = [...lines(doc), ...doc.references.map((r) => r.text)];
    expect(all.join("\n")).not.toMatch(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/);
    expect(all).toEqual(
      expect.arrayContaining([
        "title: 국내 AI 규제",
        "para: 서론 문장",
        "heading1: 1. 계수 추정",
        "para: rac{1}{2} 로 적는다 [1].",
        "bullets: 김철수 (2019) 「회귀 분석」 — eta 계수를 추정했다 [1]",
        "bullets: 과제 하나",
        "bullets: 한계 문장",
        "heading2: 1. 하위질문",
        "bullets: 검색어: ‘검색어’",
        "김철수 (2019). 회귀 분석.",
      ]),
    );
  });
});

describe("buildReportDocument — 인용 번호", () => {
  const evidence = { E1: ev("C1"), E2: ev("C2"), E3: ev("C3"), E4: ev("C4"), E5: ev("C5"), E9: ev("C9") };
  const secA = section({
    heading: "가",
    intro: "도입 [E3] 그리고 [E1].",
    papers: [{ cnts_id: "C2", summary: "요약", evidence: ["E2"] }],
    future: [{ text: "과제 [E4]", evidence: ["E4"] }],
  });
  const secB = section({ heading: "나", intro: "다시 [E1], 새로 [E5]" });
  const doc = buildReportDocument(input({ sections: [secA, secB], evidence }), NOW);

  it("절 순서 → 도입 → 대표 논문 → 향후 과제 순으로, 처음 나온 근거부터 번호를 매긴다", () => {
    expect(doc.references.map((r) => [r.n, r.eid])).toEqual([
      [1, "E3"],
      [2, "E1"],
      [3, "E2"],
      [4, "E4"],
      [5, "E5"],
    ]);
  });

  it("같은 근거는 어디서 나와도 같은 번호다", () => {
    const paras = doc.blocks.filter((b) => b.type === "para").map(lineOf);
    expect(paras).toContain("도입 [1] 그리고 [2].");
    expect(paras).toContain("다시 [2], 새로 [5]");
  });

  it("인용하지 않은 근거는 참고문헌에 싣지 않는다", () => {
    expect(doc.references.some((r) => r.eid === "E9")).toBe(false);
  });
});

describe("buildReportDocument — 참고문헌", () => {
  it("저자, 연도, 제목, 학술지·권호, 인용 쪽을 한 줄로 쓴다", () => {
    const e1 = ev(
      "C1",
      { title: "AI 윤리 교육", personal_author: "김철수; 이영희", pub_date: "2019-03", series_title: "교육학연구", vol_issue: "57(3)" },
      [chunk("c1", 11, 12), chunk("c2", 19)],
    );
    const doc = buildReportDocument(input({ sections: [section({ intro: "[E1]" })], evidence: { E1: e1 } }), NOW);
    expect(doc.references).toEqual([
      { n: 1, eid: "E1", text: "김철수, 이영희 (2019). AI 윤리 교육. 교육학연구, 57(3). 인용 쪽: 12–13, 20" },
    ]);
  });

  it("메타가 빠진 칸은 생략하고, 근거를 찾을 수 없으면 그렇다고 쓴다", () => {
    const doc = buildReportDocument(
      input({
        sections: [section({ intro: "[E1][E2][E3][E4][E7]" })],
        evidence: {
          E1: ev("C1", { title: "제목만" }),
          E2: ev("C2", { personal_author: "김철수", title: "물음표로 끝나는 제목?" }),
          E3: ev("C3", { pub_date: "2021", series_title: "정책연구" }),
          E4: ev("C4"),
        },
      }),
      NOW,
    );
    expect(doc.references.map((r) => r.text)).toEqual([
      "제목만.",
      "김철수. 물음표로 끝나는 제목?",
      "(2021). 정책연구.",
      "서지 정보 없음 (C4).",
      "근거 정보를 찾을 수 없습니다",
    ]);
  });

  it("인용 쪽은 인용한 절들이 쓴 대목의 쪽을 1부터 세어 정렬·중복 제거하고, 쪽 정보가 없으면 칸을 뺀다", () => {
    const e1 = ev("C1", { title: "가" }, [chunk("a", 19), chunk("b", 11), chunk("c", 12), chunk("z", 30), chunk("zero", 0)]);
    const e2 = ev("C2", { title: "나" }, [chunk("p", 0)]);
    const secA = section({ intro: "[E1]", evidence_chunks: { E1: ["a", "b", "zero"] } });
    const secB = section({
      papers: [{ cnts_id: "C1", summary: "요약", evidence: ["E1"] }],
      evidence_chunks: { E1: ["c", "a"] },
    });
    const secC = section({ future: [{ text: "과제 [E2]", evidence: ["E2"] }] });
    const doc = buildReportDocument(input({ sections: [secA, secB, secC], evidence: { E1: e1, E2: e2 } }), NOW);
    // z(31쪽)는 어느 절도 인용하지 않았고, 0 은 첫 쪽과 쪽 정보 없음이 겹쳐 뺀다
    expect(doc.references.map((r) => r.text)).toEqual(["가. 인용 쪽: 12–13, 20", "나."]);
  });

  it("논문 상세 인용(build_citation)과 같은 서지는 같은 글자로 쓴다 — 백엔드 test_paper_citation.py 가 같은 파일을 읽는다", () => {
    const evidence: Record<string, ReportEvidence> = {};
    citationReference.cases.forEach((c, i) => {
      evidence[`E${i + 1}`] = ev(`C${i + 1}`, c.meta);
    });
    const intro = citationReference.cases.map((_, i) => `[E${i + 1}]`).join("");
    const doc = buildReportDocument(input({ sections: [section({ intro })], evidence }), NOW);
    // 대목이 없어 인용 쪽이 붙지 않는다 — 백엔드 국문 인용의 "저자 (연도). 제목. 학술지, 권호." 와 같은 범위다
    expect(doc.references.map((r) => r.text)).toEqual(citationReference.cases.map((c) => c.reference));
  });
});

describe("buildReportDocument — 초안", () => {
  it("제목·파일 이름에 초안임을 밝히고 한계 대신 안내 문구를 싣는다", () => {
    const doc = buildReportDocument(input({ draft: { done: 2, total: 5 }, limitations: null }), NOW);
    expect(doc.blocks[0]).toEqual({ type: "title", text: "국내 AI 규제 연구 동향 (초안 · 5개 절 중 2개 작성)" });
    const all = lines(doc);
    expect(all[all.indexOf("heading1: 이 보고서의 한계") + 1]).toBe(
      "para: 작성 중에 저장한 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.",
    );
    expect(doc.fileName).toBe("딥리서치_국내_AI_규제_연구_동향_20260928_초안.docx");
  });
});

describe("docInputFromReport", () => {
  it("서론은 화면과 같은 reportIntro 이고, 탐색 경로를 부록 항목으로 옮긴다", () => {
    const report: ResearchReport = {
      question: "q",
      range: { from: "2002", to: "2026", n_papers: 10 },
      sections: [section()],
      evidence: {},
      trail: [
        { subquestion: "가", queries: ["가", "가2"], evidence_count: 2, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0, excluded: 3 },
        // 무관 제외 전 보고서의 trail 에는 excluded 가 없다
        { subquestion: "나", queries: ["나"], evidence_count: 0, verdict: "pending", note: "", parse_failed: false, failed: true, capped: 0 },
      ],
      limitations: ["한계"],
      stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 1 },
    };
    const got = docInputFromReport(report, { generatedAt: "2026-09-28T06:05:00Z", url: "http://x/research/1" });
    expect(got.intro).toBe(reportIntro(report));
    expect(got.intro).toBe("하위질문 2개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다.");
    // 오류로 끝난 하위질문은 판정을 싣지 않는다
    expect(got.trail).toEqual([
      { subquestion: "가", queries: ["가", "가2"], verdict: "sufficient", evidenceCount: 2, excluded: 3 },
      { subquestion: "나", queries: ["나"], verdict: null, evidenceCount: 0, excluded: 0 },
    ]);
    expect(got).toMatchObject({
      question: "q",
      range: { from: "2002", to: "2026", n_papers: 10 },
      generatedAt: "2026-09-28T06:05:00Z",
      url: "http://x/research/1",
      limitations: ["한계"],
      draft: null,
    });
  });

  it("제외한 논문은 보고서 trail 에서 하위질문별로 옮긴다", () => {
    const report: ResearchReport = {
      question: "q",
      range: null,
      sections: [],
      evidence: {},
      trail: [
        { subquestion: "가", queries: ["가"], evidence_count: 2, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0, excluded: 0, excluded_papers: [] },
        {
          subquestion: "엣지 컴퓨팅", queries: ["엣지 컴퓨팅"], evidence_count: 4, verdict: "sufficient", note: "",
          parse_failed: false, failed: false, capped: 0, excluded: 1,
          excluded_papers: [{ cnts_id: "C9", title: "CMOS 에지 검출 회로", personal_author: "박민수", pub_date: "2008" }],
        },
      ],
      limitations: [],
    };
    expect(docInputFromReport(report, { generatedAt: null, url: "" }).excluded).toEqual([
      { subqIdx: 1, subquestion: "엣지 컴퓨팅", papers: [{ cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수", pubDate: "2008" }] },
    ]);
  });
});

function round(n: number, query: string): RoundView {
  return {
    round: n, query, foundChunks: 3, newPapers: 1, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null,
  };
}

function subq(idx: number, over: Partial<SubqView> = {}): SubqView {
  return {
    idx,
    title: `하위질문 ${idx + 1}`,
    seq: idx + 2,
    status: "done",
    rounds: [],
    verdict: "sufficient",
    note: "",
    adopted: 1,
    parseFailed: false,
    error: null,
    ...over,
  };
}

function view(subqs: SubqView[]): ResearchView {
  return {
    jobId: "job-1",
    question: "초안 질문",
    status: "running",
    stage: "explored",
    plan: subqs.map((s) => s.title),
    params: {},
    report: null,
    lastError: null,
    createdAt: null,
    startedAt: null,
    finishedAt: null,
    steps: [],
    subqs,
    counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 1, excluded: null },
    highlight: null,
    synth: { seq: 9, status: "running", total: 3, sections: [], headings: [], evidence: {}, retiredSeq: null },
    source: "rounds",
  };
}

describe("docInputFromDraft", () => {
  const draft: DraftReport = {
    report: {
      question: "초안 질문",
      range: null,
      sections: [section({ heading: "하위질문 1", intro: "초안 도입 [E1]" })],
      evidence: { E1: ev("C1", { title: "가" }) },
      trail: [],
      limitations: [],
      stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 1 },
    },
    slots: [
      { idx: 0, heading: "하위질문 1", status: "done", durationMs: 38000, startedAt: null, sectionIndex: 0 },
      { idx: 1, heading: "하위질문 2", status: "running", durationMs: null, startedAt: "2026-09-28T06:04:50Z", sectionIndex: null },
      { idx: 2, heading: "하위질문 3", status: "waiting", durationMs: null, startedAt: null, sectionIndex: null },
    ],
    done: 1,
    total: 3,
    excluded: [{
      subqIdx: 0,
      subquestion: "하위질문 1",
      papers: [{ cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수", pubDate: "2008" }],
    }],
  };
  const v = view([
    subq(0, { rounds: [{ ...round(1, "가"), excluded: 2 }, { ...round(2, "가 재검색"), excluded: 1 }] }),
    subq(1, { status: "failed", verdict: null, adopted: null }),
    subq(2),
  ]);

  it("부록은 화면의 탐색 타임라인에서, 서론의 하위질문 수는 끝난 절 수가 아니라 탐색한 하위질문 수로 쓴다", () => {
    const got = docInputFromDraft(draft, v, "http://x/research/job-1");
    expect(got.intro).toBe("하위질문 3개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다.");
    // 오류로 멈춘 하위질문은 판정을 싣지 않고, 모르는 채택 수는 0 이 아니라 비워 둔다.
    // 무관하다고 뺀 수는 회차마다 뺀 수의 합이다(최종본 trail 의 총수와 같다)
    expect(got.trail).toEqual([
      { subquestion: "하위질문 1", queries: ["가", "가 재검색"], verdict: "sufficient", evidenceCount: 1, excluded: 3 },
      { subquestion: "하위질문 2", queries: [], verdict: null, evidenceCount: null, excluded: 0 },
      { subquestion: "하위질문 3", queries: [], verdict: "sufficient", evidenceCount: 1, excluded: 0 },
    ]);
    expect(got).toMatchObject({
      question: "초안 질문",
      url: "http://x/research/job-1",
      generatedAt: null,
      limitations: null,
      draft: { done: 1, total: 3 },
    });
  });

  it("제외한 논문은 화면의 초안과 같은 목록(탐색 타임라인에서 만든 draft.excluded)을 쓴다", () => {
    expect(docInputFromDraft(draft, v, "").excluded).toEqual(draft.excluded);
  });

  it("초안 문서는 제목·파일 이름에 초안임을 밝힌다", () => {
    const doc = buildReportDocument(docInputFromDraft(draft, v, ""), NOW);
    expect(doc.blocks[0]).toEqual({ type: "title", text: "초안 질문 (초안 · 3개 절 중 1개 작성)" });
    expect(doc.fileName).toBe("딥리서치_초안_질문_20260928_초안.docx");
  });
});

describe("reportFileName", () => {
  it("파일 이름에 못 쓰는 글자와 제어문자는 빼고 공백은 _ 로 바꾼다", () => {
    expect(reportFileName('AI 규제: "무엇이" 바뀌었나?', NOW, false)).toBe("딥리서치_AI_규제_무엇이_바뀌었나_20260928.docx");
    expect(reportFileName("a\\b/c*d<e>f|g\u0001h", NOW, false)).toBe("딥리서치_abcdefgh_20260928.docx");
  });

  it("질문은 앞 20자만 쓰고, 잘린 끝에 남은 _ 는 뗀다", () => {
    expect(reportFileName("국내 인공지능 규제 연구 동향은 지난 10년간 어떻게 변해 왔는가", NOW, false)).toBe(
      "딥리서치_국내_인공지능_규제_연구_동향은_지난_20260928.docx",
    );
    expect(reportFileName("가나다라마바사아자차카타파하가나다라마 바사", NOW, false)).toBe(
      "딥리서치_가나다라마바사아자차카타파하가나다라마_20260928.docx",
    );
  });

  it("초안은 _초안 을 붙이고, 날짜는 한국 시각으로 적는다", () => {
    expect(reportFileName("질문", new Date("2026-09-28T15:30:00Z"), true)).toBe("딥리서치_질문_20260929_초안.docx");
  });

  it("쓸 글자가 남지 않으면 보고서 로 대신한다", () => {
    expect(reportFileName(' ?*" ', NOW, false)).toBe("딥리서치_보고서_20260928.docx");
  });
});
