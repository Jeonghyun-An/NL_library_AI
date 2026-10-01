// frontend/tests/unit/reportDocx.test.ts
// jszip 은 docx 가 끌어오는 의존성이다 — 압축을 풀어 보려고 새 패키지를 들이지 않는다
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import type { ReportDoc } from "~/utils/reportDocument";
import { toDocxBlob } from "~/utils/reportDocx";

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
  // 내려받기가 쓰는 Blob 을 그대로 푼다 — Node 에도 Blob 이 있어 브라우저와 같은 경로를 지난다
  return JSZip.loadAsync(await (await toDocxBlob(target)).arrayBuffer());
}

async function read(zip: JSZip, path: string): Promise<string> {
  return (await zip.file(path)?.async("string")) ?? "";
}

// 글이 든 첫 문단(<w:p>…</w:p>)과 그 안의 런 글자를 순서대로 본다
function paragraphWith(xml: string, text: string): string {
  return (xml.match(/<w:p[ >][\s\S]*?<\/w:p>/g) ?? []).find((p) => p.includes(text)) ?? "";
}

function runTexts(paragraph: string): string[] {
  return [...paragraph.matchAll(/<w:t[^>]*>([^<]*)<\/w:t>/g)].map((m) => m[1] ?? "");
}

describe("toDocxBlob", () => {
  it("본문 문단·글머리표의 글 조각 사이에 인용 번호를 잇고 참고문헌을 뒤에 싣는다", async () => {
    const xml = await read(await unzip(doc), "word/document.xml");
    expect(xml).toContain("국내 AI 규제 연구 동향");
    expect(xml).toContain("참고문헌");
    expect(xml).toContain("[1] 김철수 (2019). AI 윤리 교육.");
    // 참고문헌 줄도 [1]·[2] 로 시작한다 — 본문 인용은 참고문헌 앞 구간의 문단 안 런 순서로 본다
    const body = xml.slice(0, xml.indexOf("참고문헌"));
    expect(runTexts(paragraphWith(body, "규제 논의가 늘었다"))).toEqual(["규제 논의가 늘었다 ", "[1]", "."]);
    const bullet = paragraphWith(body, "국제 비교가 필요하다");
    expect(bullet).toContain("<w:numPr>");
    expect(runTexts(bullet)).toEqual(["국제 비교가 필요하다 ", "[2]"]);
  });

  it("A4 용지·맑은 고딕으로 만들고 흐린 문단만 회색으로, 바닥글에 쪽 번호를 단다", async () => {
    const zip = await unzip(doc);
    const xml = await read(zip, "word/document.xml");
    expect(xml).toMatch(/<w:pgSz [^>]*w:w="11906"[^>]*w:h="16838"/);
    expect(paragraphWith(xml, "보고할 한계가 발견되지")).toContain('<w:color w:val="666666"/>');
    expect(paragraphWith(xml, "규제 논의가 늘었다")).not.toContain("<w:color");
    expect(await read(zip, "word/styles.xml")).toContain('w:eastAsia="맑은 고딕"');
    const footer = Object.keys(zip.files).find((name) => /^word\/footer\d+\.xml$/.test(name));
    expect(footer).toBeDefined();
    expect(await read(zip, footer ?? "")).toContain("PAGE");
  });

  it("인용한 근거가 없으면 참고문헌 제목을 싣지 않는다", async () => {
    const xml = await read(await unzip({ ...doc, references: [] }), "word/document.xml");
    expect(xml).not.toContain("참고문헌");
  });

  // 합성 출력의 JSON 을 풀면 LLM 이 쓴 LaTeX(\frac·\beta)가 이스케이프 \f·\b 로 풀려 이런 글자가 된다
  it("XML 에 쓸 수 없는 제어문자는 어느 자리에서도 빼고 쓴다 — Word 가 열지 못하는 파일이 되지 않게", async () => {
    const dirty: ReportDoc = {
      ...doc,
      blocks: [
        { type: "title", text: "국내\u0001 AI 규제" },
        { type: "meta", text: "생성 일시\u000B 2026\uFFFE년\uFFFF" },
        { type: "heading", level: 1, text: "1. 계수\u001F 추정" },
        { type: "para", runs: [{ text: "분수 \u000Crac 와 \u0008eta 계수 " }, { cite: 1 }] },
        { type: "bullets", items: [[{ text: "과제\u0000 하나" }]] },
      ],
      references: [{ n: 1, eid: "E1", text: "김철수 (2019).\u000E 추정." }],
    };
    const xml = await read(await unzip(dirty), "word/document.xml");
    expect(xml).not.toMatch(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/);
    expect(runTexts(paragraphWith(xml, "분수"))).toEqual(["분수 rac 와 eta 계수 ", "[1]"]);
    for (const text of ["국내 AI 규제", "생성 일시 2026년", "1. 계수 추정", "과제 하나", "[1] 김철수 (2019). 추정."]) {
      expect(xml).toContain(text);
    }
  });
});
