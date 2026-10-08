// frontend/utils/reportDocx.ts
import type { Document as DocxDocument, Paragraph } from "docx";
import { docRunText, xmlSafe, type DocBlock, type DocRun, type ReportDoc } from "./reportDocument";

// docx 는 1MB 가 넘는다 — 화면 번들에 넣지 않고 내려받기를 누를 때 받는다(동적 import).
// 구성 함수는 그때 받은 모듈을 인자로 쓴다 — 값으로 import 하면 정적 번들에 들어간다
type DocxModule = typeof import("docx");

const FONT = "맑은 고딕";
const MUTED = "666666";
const WATERMARK = "999999";
// A4(210×297mm)와 여백 2cm — 단위는 twip(1/1440인치)
const A4 = { width: 11906, height: 16838 };
const MARGIN = 1134;

// docx 의 글자 크기는 반 포인트 단위다
function pt(n: number): number {
  return Math.round(n * 2);
}

function buildDocxDocument(docx: DocxModule, doc: ReportDoc): DocxDocument {
  const { AlignmentType, Document, Footer, Header, HeadingLevel, PageNumber, Paragraph, TextRun } = docx;

  // docx 는 &<>"' 만 이스케이프하고 제어문자는 <w:t> 에 그대로 쓴다. 모델이 이미 거르지만
  // 손으로 만든 ReportDoc 도 열리는 파일이 되도록 XML 에 쓰는 자리에서 한 번 더 막는다
  const run = (text: string, opts: { size?: number; color?: string; bold?: boolean } = {}) =>
    new TextRun({ ...opts, text: xmlSafe(text) });

  const runsOf = (runs: DocRun[], muted = false) =>
    runs.map((r) => run(docRunText(r), { color: muted ? MUTED : undefined }));

  function paragraphs(block: DocBlock): Paragraph[] {
    switch (block.type) {
      case "title":
        return [new Paragraph({ heading: HeadingLevel.TITLE, children: [run(block.text)] })];
      case "meta":
        return [new Paragraph({ children: [run(block.text, { size: pt(9), color: MUTED })] })];
      case "heading":
        return [
          new Paragraph({
            heading: block.level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
            children: [run(block.text)],
          }),
        ];
      case "para":
        return [new Paragraph({ children: runsOf(block.runs, block.muted), spacing: { after: 120 } })];
      case "bullets":
        return block.items.map((runs) => new Paragraph({ bullet: { level: 0 }, children: runsOf(runs) }));
    }
  }

  // 참고문헌은 번호가 긴 줄 앞으로 튀어나오게(내어쓰기) 둔다 — 번호로 찾아 읽는 목록이다
  const references = doc.references.length
    ? [
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("참고문헌")] }),
        ...doc.references.map(
          (r) =>
            new Paragraph({
              children: [run(`[${r.n}] ${r.text}`)],
              indent: { left: 440, hanging: 440 },
              spacing: { after: 80 },
            }),
        ),
      ]
    : [];

  // 워터마크는 쪽마다 머리글에 싣는다. 없으면 머리글 자체를 만들지 않는다 — 보고서 문서는 지금과 같은 구성이다
  const headers = doc.watermark
    ? {
        headers: {
          default: new Header({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [run(doc.watermark, { size: pt(11), color: WATERMARK, bold: true })],
              }),
            ],
          }),
        },
      }
    : {};

  return new Document({
    creator: "NL-Lib 딥리서치",
    title: xmlSafe(doc.fileName.replace(/\.docx$/i, "")),
    styles: {
      default: {
        document: { run: { font: FONT, size: pt(10.5) }, paragraph: { spacing: { line: 312 } } },
        title: { run: { font: FONT, size: pt(18), bold: true, color: "000000" }, paragraph: { spacing: { after: 160 } } },
        heading1: {
          run: { font: FONT, size: pt(14), bold: true, color: "000000" },
          paragraph: { spacing: { before: 360, after: 120 } },
        },
        heading2: {
          run: { font: FONT, size: pt(12), bold: true, color: "333333" },
          paragraph: { spacing: { before: 200, after: 80 } },
        },
      },
    },
    sections: [
      {
        properties: { page: { size: A4, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } } },
        ...headers,
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ children: [PageNumber.CURRENT], size: pt(9), color: MUTED })],
              }),
            ],
          }),
        },
        children: [...doc.blocks.flatMap(paragraphs), ...references],
      },
    ],
  });
}

export async function toDocxBlob(doc: ReportDoc): Promise<Blob> {
  const docx = await import("docx");
  return docx.Packer.toBlob(buildDocxDocument(docx, doc));
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  // 문서에 붙지 않은 링크의 click 을 무시하는 브라우저가 있다
  document.body.appendChild(a);
  a.click();
  a.remove();
  // 곧바로 해제하면 내려받기가 시작되기 전에 주소가 사라지는 브라우저가 있다
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
