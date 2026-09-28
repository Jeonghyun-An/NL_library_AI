// frontend/tests/unit/reportDocx.test.ts
// jszip 은 docx 가 끌어오는 의존성이다 — 압축을 풀어 보려고 새 패키지를 들이지 않는다
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import type { ReportDoc } from "~/utils/reportDocument";
import { toDocxBuffer } from "~/utils/reportDocx";

const doc: ReportDoc = {
  fileName: "딥리서치_국내_AI_규제_연구_동향_20260928.docx",
  blocks: [
    { type: "title", text: "국내 AI 규제 연구 동향" },
    { type: "meta", text: "생성 일시 2026년 9월 28일 15:05" },
    { type: "heading", level: 1, text: "1. 규제 논의의 흐름" },
    { type: "para", runs: [{ text: "규제 논의가 늘었다 " }, { cite: 1 }, { text: "." }] },
    { type: "heading", level: 2, text: "향후 과제" },
    { type: "bullets", items: [[{ text: "국제 비교가 필요하다 " }, { cite: 2 }]] },
    { type: "para", runs: [{ text: "자동 점검에서 보고할 한계가 발견되지 않았습니다." }], muted: true },
  ],
  references: [
    { n: 1, eid: "E1", text: "김철수 (2019). AI 윤리 교육." },
    { n: 2, eid: "E2", text: "이영희 (2021). 규제 샌드박스." },
  ],
};

async function unzip(target: ReportDoc): Promise<JSZip> {
  return JSZip.loadAsync(await toDocxBuffer(target));
}

async function read(zip: JSZip, path: string): Promise<string> {
  return (await zip.file(path)?.async("string")) ?? "";
}

describe("toDocxBuffer", () => {
  it("본문에 질문·인용 번호·참고문헌을 싣는다", async () => {
    const xml = await read(await unzip(doc), "word/document.xml");
    expect(xml).toContain("국내 AI 규제 연구 동향");
    expect(xml).toContain("[1]");
    expect(xml).toContain("[2]");
    expect(xml).toContain("참고문헌");
    expect(xml).toContain("[1] 김철수 (2019). AI 윤리 교육.");
  });

  it("A4 용지·맑은 고딕으로 만들고 바닥글에 쪽 번호를 단다", async () => {
    const zip = await unzip(doc);
    expect(await read(zip, "word/document.xml")).toMatch(/<w:pgSz [^>]*w:w="11906"[^>]*w:h="16838"/);
    expect(await read(zip, "word/styles.xml")).toContain('w:eastAsia="맑은 고딕"');
    const footer = Object.keys(zip.files).find((name) => /^word\/footer\d+\.xml$/.test(name));
    expect(footer).toBeDefined();
    expect(await read(zip, footer ?? "")).toContain("PAGE");
  });

  it("인용한 근거가 없으면 참고문헌 제목을 싣지 않는다", async () => {
    const xml = await read(await unzip({ ...doc, references: [] }), "word/document.xml");
    expect(xml).not.toContain("참고문헌");
  });
});
