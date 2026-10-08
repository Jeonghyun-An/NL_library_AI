// frontend/tests/unit/proposalDocument.test.ts
// jszip 은 docx 가 끌어오는 의존성이다 — 압축을 풀어 보려고 새 패키지를 들이지 않는다
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import type { Paragraph, ParaState, ProposalSection, ProposalView, WorkView } from "~/types/work";
import {
  UNREVIEWED_WATERMARK,
  buildProposalDocument,
  disclosureLines,
  printedKeys,
  printedProposedCount,
  proposalFileName,
  type ProposalDocInput,
} from "~/utils/proposalDocument";
import { buildReportDocument, docRunText, kstDateTime, type DocBlock, type ReportDoc } from "~/utils/reportDocument";
import { toDocxBlob } from "~/utils/reportDocx";
import { scopeLine } from "~/utils/workPhase";

// 한국 시각 2026-10-14 15:05
const NOW = new Date("2026-10-14T06:05:00Z");
const NO_CHECKS = { dropped: 0, dropped_f: 0, unmarked: 0, numbers: [], softened: 0 };
const CORPUS = { n_papers: 144748, from: "1980", to: "2017", at: "2026-10-14T05:00:00Z" };

function para(id: string, state: ParaState, text: string): Paragraph {
  return { id, text, state, cites: [], checks: NO_CHECKS, gen_id: 50 };
}

function section(key: string, evidence: Record<string, string>, paragraphs: Paragraph[]): ProposalSection {
  return {
    key,
    gen_id: 50,
    evidence,
    figures: [{ id: "F1", label: "이 절에 준 논문 수", value: "6" }],
    basis: { topic_id: 12, papers: Object.values(evidence) },
    note: key === "gap" ? "소장 코퍼스에서 확인하지 않은 공백 후보" : null,
    paragraphs,
    model: "gemma-3-12b",
    updated_at: "2026-10-14T05:30:00Z",
  };
}

function proposal(over: Partial<ProposalView> = {}): ProposalView {
  return {
    version: 7,
    outline: {
      topic: { id: 12, title: "세대 간 지지와 노인 우울", question: "세대 간 지지는 노인 우울을 낮추는가?" },
      basis: "concept",
      groups: [
        { key: "prior.g1", name: "노인의 우울", hint: "노인 우울", papers: ["KCI_A", "KCI_B"] },
        { key: "prior.g2", name: "사회적 지지", hint: "사회적 지지", papers: ["KCI_C"] },
      ],
      questions: ["세대 간 지지는 노인 우울을 낮추는가?", "지지의 출처에 따라 다른가?"],
      question: "가족 지지는 농촌 노인의 우울을 낮추는가?",
      method: "설문 조사\n위계적 회귀 분석",
      state: "approved",
      gen_id: 41,
      approved_at: "2026-10-14T05:10:00Z",
    },
    sections: {
      "prior.g1": section("prior.g1", { E1: "KCI_A", E2: "KCI_B" }, [
        para("p1", "accepted", "노인 우울 연구는 [F1]편이다 [E1]."),
        para("p2", "proposed", "검토 전 문단이다 [E2]."),
      ]),
      // 이 절의 E1 은 다른 논문이다 — 번호는 절마다 로컬이고 문서 번호는 논문으로 매긴다
      "prior.g2": section("prior.g2", { E1: "KCI_C", E2: "KCI_A" }, [para("p1", "edited", "지지는 우울을 낮춘다 [E2][E1].")]),
      gap: section("gap", { E1: "KCI_B" }, [
        para("p1", "authored", "직접 쓴 공백 문단이다."),
        para("p2", "proposed", "검토 전 공백이다 [E1]."),
      ]),
    },
    drafts: {},
    papers: {
      KCI_A: { title: "노인 우울 연구", personal_author: "김철수", pub_date: "2015", series_title: "노년학" },
      KCI_B: { title: "가족 지지", personal_author: "이영희", pub_date: "2012", series_title: null },
      KCI_C: { title: "사회적 지지 척도", personal_author: null, pub_date: null, series_title: null },
    },
    references: {
      KCI_A: "김철수 (2015). 노인 우울 연구. 노년학. UCI I410-1",
      KCI_B: "이영희 (2012). 가족 지지. UCI I410-2",
    },
    corpus: CORPUS,
    stale: { outline: false, sections: {} },
    disclosure: {
      steps: [
        { kind: "outline", target: "outline", model: "gemma-3-12b", finished_at: "2026-10-14T05:05:00Z", attempts: [{ model: "gemma-3-12b", outcome: "ok" }] },
        {
          kind: "section",
          target: "prior.g1",
          model: "gemma-3-12b",
          finished_at: "2026-10-14T05:20:00Z",
          attempts: [
            { model: "gemma-3-12b", outcome: "broken" },
            { model: "gemma-3-12b", outcome: "ok" },
          ],
        },
        { kind: "paragraph", target: "gap#p2", model: null, finished_at: null, attempts: [] },
      ],
    },
    ...over,
  };
}

function work(over: Partial<WorkView> = {}): WorkView {
  return {
    id: "job",
    phase: "proposal",
    concepts: ["노인 우울", "사회적 지지"],
    memo: null,
    is_example: false,
    progress: {},
    corpus: null,
    generations: [],
    ...over,
  };
}

function input(over: Partial<ProposalDocInput> = {}): ProposalDocInput {
  return {
    question: "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
    url: "http://local/research/job?s=proposal",
    proposal: proposal(),
    work: work(),
    includeProposed: false,
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

function lines(doc: ReportDoc): string[] {
  return doc.blocks.map((b) => `${b.type}${b.type === "heading" ? b.level : ""}${"muted" in b && b.muted ? "~" : ""}: ${lineOf(b)}`);
}

describe("buildProposalDocument", () => {
  it("6절을 목차 순서로 싣고 기본은 받아들인 문단만 — 검토 전 문단·워터마크는 없다", () => {
    const doc = buildProposalDocument(input(), NOW);
    expect(lines(doc).filter((l) => !l.startsWith("meta") && !l.startsWith("bullets"))).toEqual([
      "title: 세대 간 지지와 노인 우울",
      "heading1: 1. 주제",
      "para: 세대 간 지지와 노인 우울",
      "heading1: 2. 연구 배경",
      "para~: 이 초안에는 아직 없습니다 — 다음 단계에서 씁니다.",
      "heading1: 3. 선행연구 검토",
      "heading2: 3.1 노인의 우울",
      "para: 노인 우울 연구는 6편이다 [1].",
      "heading2: 3.2 사회적 지지",
      "para: 지지는 우울을 낮춘다 [1][2].",
      "heading1: 4. 연구 공백",
      "para~: 소장 코퍼스에서 확인하지 않은 공백 후보로만 적은 절입니다.",
      "para: 직접 쓴 공백 문단이다.",
      "heading1: 5. 연구 질문",
      "para: 가족 지지는 농촌 노인의 우울을 낮추는가?",
      "heading1: 6. 방법 제안",
      "para: 설문 조사",
      "para: 위계적 회귀 분석",
      "heading1: 결과·논의",
      "para~: 연구 후 직접 씁니다.",
      "heading1: 부록: AI 사용 공개",
      expect.stringMatching(/^para~: 이 초안의 문단은 연구 어시스턴트의 AI/),
    ]);
    expect("watermark" in doc).toBe(false);
    expect(doc.fileName).toBe("연구계획서_세대_간_지지와_노인_우울_20261014.docx");
  });

  it("인용 번호는 논문마다 문서에 처음 나온 순서이고 참고문헌 글은 서버가 만든 것을 쓴다", () => {
    const doc = buildProposalDocument(input(), NOW);
    expect(doc.references).toEqual([
      { n: 1, eid: "KCI_A", text: "김철수 (2015). 노인 우울 연구. 노년학. UCI I410-1" },
      { n: 2, eid: "KCI_C", text: "사회적 지지 척도." },
    ]);
  });

  it("meta 에 원 질문·생성 일시·범위(코퍼스 스냅숏)·연구 주소를 싣는다", () => {
    const meta = buildProposalDocument(input(), NOW).blocks.filter((b) => b.type === "meta").map(lineOf);
    expect(meta).toEqual([
      "연구계획서 초안 · 원 질문 노인의 우울과 사회적 지지에 관한 연구가 궁금해",
      `생성 일시 ${kstDateTime(NOW)}`,
      `범위 ${scopeLine(CORPUS)} — ${kstDateTime(new Date(CORPUS.at))} 시점`,
      "연구 주소 http://local/research/job?s=proposal",
    ]);
    const example = buildProposalDocument(input({ work: work({ is_example: true }) }), NOW);
    expect(example.blocks.filter((b) => b.type === "meta").map(lineOf)).toContain("예시 연구 — 미리 돌린 실제 기록입니다");
  });

  it("미수락 문단도 넣으면 검토 전 문단이 실리고 워터마크·파일 이름 꼬리가 붙는다", () => {
    const doc = buildProposalDocument(input({ includeProposed: true }), NOW);
    expect(lines(doc)).toContain("para: 검토 전 문단이다 [2].");
    expect(lines(doc)).toContain("para: 검토 전 공백이다 [2].");
    expect(doc.watermark).toBe(UNREVIEWED_WATERMARK);
    expect(doc.fileName).toBe("연구계획서_세대_간_지지와_노인_우울_20261014_미검토포함.docx");
    expect(doc.references.map((r) => r.eid)).toEqual(["KCI_A", "KCI_B", "KCI_C"]);
  });

  it("켜도 검토 전 문단이 하나도 없으면 워터마크를 달지 않는다", () => {
    const p = proposal();
    const sections = Object.fromEntries(
      Object.entries(p.sections).map(([k, s]) => [k, { ...s, paragraphs: s.paragraphs.filter((x) => x.state !== "proposed") }]),
    );
    const doc = buildProposalDocument(input({ includeProposed: true, proposal: { ...p, sections } }), NOW);
    expect("watermark" in doc).toBe(false);
    expect(doc.fileName.endsWith("_20261014.docx")).toBe(true);
  });

  it("쓰지 않은 절·받아들인 문단이 없는 절·목차가 없는 계획서는 흐린 안내로 둔다", () => {
    const p = proposal();
    const onlyProposed = { ...p, sections: { "prior.g1": p.sections["prior.g1"]!, gap: { ...p.sections.gap!, paragraphs: [para("p2", "proposed", "x [E1].")] } } };
    const out = lines(buildProposalDocument(input({ proposal: onlyProposed }), NOW));
    expect(out).toContain("para~: 아직 쓰지 않았습니다.");
    expect(out).toContain("para~: 받아들인 문단이 없습니다 — 화면에서 [수락]하거나 '미수락 문단도 넣기'를 켜면 실립니다.");

    const empty = lines(buildProposalDocument(input({ proposal: proposal({ outline: null, sections: {} }) }), NOW));
    expect(empty[0]).toBe("title: 노인의 우울과 사회적 지지에 관한 연구가 궁금해");
    expect(empty).toContain("para~: 주제를 아직 고르지 않았습니다.");
    expect(empty).toContain("para~: 목차를 아직 만들지 않았습니다.");
    expect(empty).toContain("para~: 목차에서 연구 질문을 아직 정하지 않았습니다.");
    expect(empty).toContain("para~: 방법을 아직 적지 않았습니다.");
  });

  it("XML 에 쓸 수 없는 제어문자는 문단·제목에서 뺀다", () => {
    const p = proposal();
    const dirty = {
      ...p,
      sections: { ...p.sections, "prior.g1": { ...p.sections["prior.g1"]!, paragraphs: [para("p1", "accepted", "분수 \u000Crac 계수 [E1].")] } },
    };
    expect(lines(buildProposalDocument(input({ proposal: dirty }), NOW))).toContain("para: 분수 rac 계수 [1].");
  });
});

describe("disclosureLines", () => {
  it("문단 상태 비율·절별 상태·실은 문단·생성 단계·결과·논의 미포함을 싣는다", () => {
    expect(disclosureLines(proposal(), false)).toEqual([
      "문단 상태: AI 제안 4문단 중 수락 1·수정 1·검토 전 2 · 직접 쓴 문단 1",
      "선행연구 검토 · 노인의 우울: 문단 2개 — 수락 1·검토 전 1",
      "선행연구 검토 · 사회적 지지: 문단 1개 — 수정 1",
      "연구 공백: 문단 2개 — 직접 작성 1·검토 전 1",
      "이 문서에 실은 문단: 수락·수정·직접 쓴 문단(검토 전 AI 제안은 싣지 않음)",
      `목차: gemma-3-12b · ${kstDateTime(new Date("2026-10-14T05:05:00Z"))}`,
      `절 초안(선행연구 검토 · 노인의 우울): gemma-3-12b · ${kstDateTime(new Date("2026-10-14T05:20:00Z"))} — 시도 2회: gemma-3-12b 끊김 → gemma-3-12b 완료`,
      "문단 다시 쓰기(연구 공백 p2): 모델 출력 없음(기본값으로 채움) · 완료 시각 기록 없음",
      "결과·논의 미포함 — 결과·논의·가설 수치는 AI 가 쓰지 않았고 이 문서에도 없습니다.",
    ]);
  });

  it("미수락 문단을 넣으면 그 수와 워터마크를 적는다", () => {
    expect(disclosureLines(proposal(), true)).toContain(
      "이 문서에 실은 문단: 수락·수정·직접 쓴 문단과 검토 전 AI 제안 2문단(쪽마다 '미검토 AI 초안' 표시)",
    );
  });

  it("실은 문단 수는 문서가 그리는 절에서만 센다 — 목차에서 빠진 옛 절의 검토 전 문단은 워터마크처럼 세지 않는다", () => {
    // (a) 옛 절(prior.g3)에 검토 전 문단이 남아 있어도 실은 수는 목차 묶음·연구 공백의 2문단이다
    const p = proposal();
    const withOrphan = {
      ...p,
      sections: { ...p.sections, "prior.g3": section("prior.g3", { E1: "KCI_C" }, [para("p1", "proposed", "옛 절 [E1].")]) },
    };
    expect(disclosureLines(withOrphan, true)).toContain(
      "이 문서에 실은 문단: 수락·수정·직접 쓴 문단과 검토 전 AI 제안 2문단(쪽마다 '미검토 AI 초안' 표시)",
    );

    // (b) 검토 전 문단이 옛 절에만 있으면 문서에 싣지 않으므로 워터마크도, 실었다는 줄도 없다
    const printed = Object.fromEntries(
      Object.entries(withOrphan.sections).map(([k, s]) => [
        k,
        k === "prior.g3" ? s : { ...s, paragraphs: s.paragraphs.filter((x) => x.state !== "proposed") },
      ]),
    );
    const orphanOnly = { ...withOrphan, sections: printed };
    expect(disclosureLines(orphanOnly, true)).toContain("이 문서에 실은 문단: 수락·수정·직접 쓴 문단(검토 전 AI 제안은 싣지 않음)");
    expect("watermark" in buildProposalDocument(input({ includeProposed: true, proposal: orphanOnly }), NOW)).toBe(false);
  });

  it("고른 주제의 출처를 문단 상태 다음 줄에 적는다 — 출처를 모르면 적지 않는다", () => {
    const second = (source: ProposalView["topic_source"]) => disclosureLines(proposal({ topic_source: source }), false)[1];
    expect(second({ origin: "user", edited: false })).toBe("주제: 사용자가 직접 쓴 주제");
    expect(second({ origin: "report_seed", edited: true })).toBe("주제: AI 주제 카드(사용자가 고침)");
    expect(second({ origin: "other", edited: false })).toBe("주제: AI 주제 카드");
    expect(second(null)).toBe("선행연구 검토 · 노인의 우울: 문단 2개 — 수락 1·검토 전 1");
  });
});

describe("printedKeys·printedProposedCount — 계획서 화면의 절 목록·토글 수와 문서가 같은 범위", () => {
  // 목차를 다시 만들며 빠진 옛 절(prior.g3) — 문서에 실리지 않고 화면에서 수락할 수도 없다
  function withOrphan(p: ProposalView): ProposalView {
    const orphan = section("prior.g3", { E1: "KCI_C" }, [para("p1", "proposed", "옛 절 [E1]."), para("p2", "proposed", "옛 절 둘.")]);
    return { ...p, sections: { ...p.sections, "prior.g3": orphan } };
  }

  function withoutPrintedProposed(p: ProposalView): ProposalView {
    const keys = printedKeys(p);
    const sections = Object.fromEntries(
      Object.entries(p.sections).map(([k, s]) => [
        k,
        keys.includes(k) ? { ...s, paragraphs: s.paragraphs.filter((x) => x.state !== "proposed") } : s,
      ]),
    );
    return { ...p, sections };
  }

  it("문서가 그리는 절은 목차 묶음 순서 → 연구 공백이다 — 목차에서 빠진 옛 절은 넣지 않고, 목차가 없으면 연구 공백만", () => {
    expect(printedKeys(proposal())).toEqual(["prior.g1", "prior.g2", "gap"]);
    expect(printedKeys(withOrphan(proposal()))).toEqual(["prior.g1", "prior.g2", "gap"]);
    expect(printedKeys(proposal({ outline: null }))).toEqual(["gap"]);
  });

  it("검토 전 문단은 문서가 그리는 절에서만 센다 — 옛 절에만 남은 검토 전 문단은 0 이고 워터마크도 없다", () => {
    expect(printedProposedCount(proposal())).toBe(2);
    expect(printedProposedCount(withOrphan(proposal()))).toBe(2);

    const orphanOnly = withoutPrintedProposed(withOrphan(proposal()));
    expect(printedProposedCount(orphanOnly)).toBe(0);
    expect("watermark" in buildProposalDocument(input({ includeProposed: true, proposal: orphanOnly }), NOW)).toBe(false);
    expect(printedProposedCount(proposal({ outline: null, sections: {} }))).toBe(0);
  });

  it("미수락 문단을 켰을 때 워터마크·파일 이름 꼬리·공개 부록의 실은 수가 이 수와 맞는다", () => {
    for (const p of [proposal(), withOrphan(proposal()), withoutPrintedProposed(withOrphan(proposal()))]) {
      const n = printedProposedCount(p);
      const doc = buildProposalDocument(input({ includeProposed: true, proposal: p }), NOW);
      expect("watermark" in doc).toBe(n > 0);
      expect(doc.fileName.endsWith("_미검토포함.docx")).toBe(n > 0);
      expect(disclosureLines(p, true).some((l) => l.includes(`검토 전 AI 제안 ${n}문단(`))).toBe(n > 0);
    }
  });
});

describe("proposalFileName", () => {
  it("주제 앞 20자·한국 날짜·미검토 꼬리 — 파일 이름에 못 쓰는 글자는 뺀다", () => {
    expect(proposalFileName("노인 우울/사회적 지지: 연구?", NOW, false)).toBe("연구계획서_노인_우울사회적_지지_연구_20261014.docx");
    expect(proposalFileName("가".repeat(30), NOW, true)).toBe(`연구계획서_${"가".repeat(20)}_20261014_미검토포함.docx`);
    expect(proposalFileName("  ", NOW, false)).toBe("연구계획서_초안_20261014.docx");
  });
});

describe("계획서 Word 의 워터마크", () => {
  async function unzip(target: ReportDoc): Promise<JSZip> {
    return JSZip.loadAsync(await (await toDocxBlob(target)).arrayBuffer());
  }

  it("워터마크가 있으면 쪽마다 쓰는 머리글에 회색 굵은 글로 싣는다", async () => {
    const zip = await unzip(buildProposalDocument(input({ includeProposed: true }), NOW));
    const headers = Object.keys(zip.files).filter((name) => /^word\/header\d+\.xml$/.test(name));
    expect(headers.length).toBeGreaterThan(0);
    const xml = (await zip.file(headers[0]!)?.async("string")) ?? "";
    expect(xml).toContain(UNREVIEWED_WATERMARK);
    expect(xml).toContain("<w:b/>");
    expect(xml).toContain('<w:color w:val="999999"/>');
  });

  it("워터마크가 없으면 머리글을 만들지 않는다 — 보고서 문서와 같은 구성", async () => {
    const zip = await unzip(buildProposalDocument(input(), NOW));
    expect(Object.keys(zip.files).filter((name) => /^word\/header\d+\.xml$/.test(name))).toEqual([]);
  });

  it("보고서 문서 모델은 watermark 키를 만들지 않는다 — 보고서 내보내기 출력은 그대로다", async () => {
    const report = buildReportDocument(
      {
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
      },
      NOW,
    );
    expect("watermark" in report).toBe(false);
    const zip = await unzip(report);
    expect(Object.keys(zip.files).filter((name) => /^word\/header\d+\.xml$/.test(name))).toEqual([]);
  });
});
