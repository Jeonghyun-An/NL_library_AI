// frontend/tests/unit/proposalSection.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parse } from "vue/compiler-sfc";

// 컴포넌트를 띄우지 않는 단위 테스트 환경이라 템플릿을 읽어 안내 글을 본다(outlineEdit.test.ts 와 같은 방식)
interface TplNode {
  type: number;
  tag?: string;
  content?: string | { content?: string };
  props?: { type: number; name: string; exp?: { content?: string } }[];
  children?: TplNode[];
}
const ELEMENT = 1;
const TEXT = 2;
const INTERPOLATION = 5;
const DIRECTIVE = 7;

function elements(nodes: TplNode[], out: TplNode[] = []): TplNode[] {
  for (const n of nodes) {
    if (n.type === ELEMENT) out.push(n);
    if (n.children) elements(n.children, out);
  }
  return out;
}

// 글자는 그대로, 끼워 넣은 값은 {{식}} 으로 — 줄바꿈·들여쓰기는 빈칸 하나로
function flatText(n: TplNode): string {
  return (n.children ?? [])
    .map((c) => {
      if (c.type === TEXT) return String(c.content ?? "");
      if (c.type === INTERPOLATION) return `{{${typeof c.content === "object" ? c.content?.content : ""}}}`;
      return c.type === ELEMENT ? flatText(c) : "";
    })
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}

const source = readFileSync(fileURLToPath(new URL("../../components/work/ProposalSection.vue", import.meta.url)), "utf8");
const { descriptor } = parse(source);

describe("ProposalSection — 근거가 없어 건너뛴 절(skippedNow)의 안내", () => {
  it("씨앗이 어디서 왔는지를 화면 표기 상수 DEEP_RESEARCH 로 밝힌다", () => {
    const ast = descriptor.template?.ast as unknown as TplNode;
    const notes = elements(ast.children ?? []).filter(
      (n) =>
        n.tag === "p" &&
        (n.props ?? []).some((p) => p.type === DIRECTIVE && p.name === "if" && p.exp?.content === "skippedNow"),
    );

    expect(notes).toHaveLength(1);
    const text = flatText(notes[0]!);
    expect(text).toContain("고른 주제의 씨앗({{DEEP_RESEARCH}} 보고서의 향후 과제·근거가 부족했던 하위질문)에 이은 논문으로 쓰는데");
    expect(text).toContain("[{{REMAKE_REPORT}}]로 맞추세요");
    expect(text).not.toContain("딥리서치");
    // import 줄은 이름만 본다 — 같은 줄에 다른 이름이 더해지거나 줄바꿈·따옴표 꼴이 바뀌어도 깨지지 않게
    expect(descriptor.scriptSetup?.content).toMatch(/import\s*\{[^}]*\bDEEP_RESEARCH\b[^}]*\}\s*from\s*["']~\/utils\/brand["']/);
  });
});
