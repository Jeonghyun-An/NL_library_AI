// frontend/tests/unit/themeResearch.test.ts
// round06d 2부 — DeepResearch 화면 스타일(assets/css/research.css)과 사이드바 스타일(AppSidebar.vue 의 scoped)은 round08 테마 토큰만
// 쓴다. ① 색 리터럴(#hex·rgb()·rgba()·hsl()·색 이름)이 없다 ② 쓰는 --skx-* 는 모두 style_skovix.css 의 :root 에 있다(없는 토큰을
// 쓰면 var() 가 비어 바탕·글자가 조용히 사라진다 — 테마 블록은 :root 의 토큰을 다시 선언만 한다) ③ --skx-white 는 이름만 남은 '불투명
// 면' 자리라 글자색으로 쓰지 않고, 산호 바탕(--skx-primary) 위 글자는 --skx-on-accent ④ 진행 막대의 빛 흐름은 밝은 유리 선
// ⑤ 보고서·탐색 중 절 자리는 읽기용 짙은 유리(--skx-read-*)이고 밝은 읽는 면(.skx-reading)은 화면에 쓰지 않는다 — 흰 종이에 찍는
// 인쇄 전용 문서만(사용자 결정 2026-10-13)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { cssRules } from "./helpers/cssRules";
import { THEMES, contrast, over, parseColor, rootDecls, solidOf, themeTokens } from "./helpers/themeCss";

function read(rel: string): string {
  return readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf-8");
}

// 주석과 url(...) 안의 글은 검사하지 않는다(주석의 '흰 8%' 같은 설명·아이콘 경로)
function strip(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "").replace(/url\([^)]*\)/g, "");
}

const LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|(?<![\w-])(?:white|black|red|green|blue|gray|grey|currentcolor)(?![\w-])/gi;
const researchCss = read("../../assets/css/research.css");
const sidebarCss = read("../../components/AppSidebar.vue").match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] ?? "";
const declared = new Set(Object.keys(rootDecls));

function usedTokens(css: string): string[] {
  return [...new Set([...strip(css).matchAll(/var\(\s*(--skx-[\w-]+)/g)].map((m) => m[1]!))];
}

describe("DeepResearch 화면·사이드바 스타일 — 색은 토큰으로만", () => {
  it("research.css·사이드바 스타일·:root 토큰을 읽었다", () => {
    expect(researchCss.length).toBeGreaterThan(0);
    expect(sidebarCss).toMatch(/\.skx-history/);
    expect(declared.has("--skx-white")).toBe(true);
  });

  it("색 리터럴이 없다", () => {
    expect(strip(researchCss).match(LITERAL) ?? []).toEqual([]);
    expect(strip(sidebarCss).match(LITERAL) ?? []).toEqual([]);
  });

  it("쓰는 --skx-* 는 모두 :root 에 선언돼 있다", () => {
    expect(usedTokens(researchCss).filter((name) => !declared.has(name))).toEqual([]);
    expect(usedTokens(sidebarCss).filter((name) => !declared.has(name))).toEqual([]);
  });
});

describe("다크 테마의 글자색·빛(research.css)", () => {
  const rules = cssRules(researchCss);
  const names = (list: typeof rules) => list.map((r) => r.selectors.join(", "));

  it("--skx-white 는 글자색으로 쓰지 않는다 — round08 에서 불투명 면(다크 짙은 청록) 자리다", () => {
    expect(names(rules.filter((r) => r.decls.get("color") === "var(--skx-white)"))).toEqual([]);
  });

  it("산호 바탕(--skx-primary) 위 글자는 --skx-on-accent", () => {
    const onCoral = rules.filter((r) => r.decls.get("background") === "var(--skx-primary)" && r.decls.has("color"));
    expect(onCoral.length).toBeGreaterThan(0);
    expect(names(onCoral.filter((r) => r.decls.get("color") !== "var(--skx-on-accent)"))).toEqual([]);
  });

  it("진행 막대 채움의 빛 흐름은 밝은 유리 선(--skx-frost-line) — 짙은 면 색을 섞으면 산호 막대 위로 어두운 띠가 흐른다", () => {
    const sheen = rules.find((r) => r.selectors.includes(".rs-pbar__fill.is-running::after"))?.decls.get("background") ?? "";
    expect(sheen).toContain("var(--skx-frost-line)");
    expect(sheen).not.toContain("var(--skx-white)");
  });

  it("탐색 방식의 고른 칸은 두 테마 모두에서 3:1 이상의 테두리로 짚는다 — 핑크는 고른 칸 면(흰)과 홈(흰 반투명)·두 글자색이 거의 같다", () => {
    const picked = rules.find((r) => !r.at && r.selectors.includes('.rs-mode__opt[aria-checked="true"]'));
    const ring = picked?.decls.get("box-shadow")?.match(/^inset 0 0 0 1px var\((--skx-[\w-]+)\)$/)?.[1];
    expect(ring).toBeDefined();
    expect(picked?.decls.get("background")).toBe("var(--skx-white)");
    for (const theme of THEMES) {
      const t = themeTokens(theme);
      const ringColor = parseColor(t[ring!]!);
      expect(ringColor.a).toBe(1);
      // 테두리 안쪽은 고른 칸 면, 바깥은 칸 홈(입력 상자 위 --skx-frost-bg — 바탕은 페이지 색으로 어림)
      const face = solidOf(t["--skx-white"]!, t);
      const frost = parseColor(t["--skx-frost-bg"]!);
      const home = over(parseColor(t["--skx-page-bg"]!).rgb, frost.rgb, frost.a);
      expect(contrast(ringColor.rgb, face), `${theme} 면`).toBeGreaterThanOrEqual(3);
      expect(contrast(ringColor.rgb, home), `${theme} 홈`).toBeGreaterThanOrEqual(3);
    }
  });
});

describe("보고서·절 자리 — 읽기용 짙은 유리(밝은 읽는 면은 화면에 쓰지 않는다)", () => {
  const rules = cssRules(researchCss);

  it("보고서(초안·최종본)와 탐색 중 절 자리(뿌리 .rs-card.rs-report)는 결과 화면의 읽는 칸과 같은 토큰 — 줄간격 1.6, 흐림·반사광 없음", () => {
    const face = rules.find((r) => !r.at && r.selectors.includes(".rs-card.rs-report"));
    expect(face?.decls.get("background")).toContain("var(--skx-read-surface)");
    expect(face?.decls.get("background")).not.toMatch(/--skx-frost-(reflect|milk|fill)/);
    expect(face?.decls.has("backdrop-filter")).toBe(false);
    expect(face?.decls.get("--skx-ink")).toBe("var(--skx-read-ink)");
    expect(face?.decls.get("--skx-ink-2")).toBe("var(--skx-read-ink-2)");
    expect(face?.decls.get("--skx-gray-1")).toBe("var(--skx-read-gray-1)");
    expect(face?.decls.get("line-height")).toBe("1.6");
    // 두 부품의 뿌리가 그 클래스다 — 부품 파일을 고치지 않고 면을 준다
    expect(read("../../components/research/ReportView.vue")).toContain('<article class="rs-card rs-report"');
    expect(read("../../components/research/ReportSkeleton.vue")).toContain('<article class="rs-card rs-report rs-report--slots"');
  });

  it("밝은 읽는 면(.skx-reading)은 화면에 그리는 연구 페이지·부품·스타일에 없다", () => {
    for (const rel of [
      "../../pages/research/[id].vue",
      "../../components/research/ReportView.vue",
      "../../components/research/ReportSkeleton.vue",
    ]) {
      expect(read(rel)).not.toContain("skx-reading");
    }
    expect(strip(researchCss)).not.toContain("skx-reading");
  });

  it("흰 종이에 찍는 인쇄 전용 문서(화면에 그리지 않는다)만 밝은 읽는 면이고, 화면 인쇄의 보고서는 짙은 면을 그대로 찍는다", () => {
    expect(read("../../components/research/ReportPrint.vue")).toContain('<article class="rs-print skx-reading">');
    expect(rules.find((r) => !r.at && r.selectors.includes(".rs-print"))?.decls.get("display")).toBe("none");
    const screenPrint = rules.find((r) => r.at.includes("@media print") && r.selectors.includes(".rs-page .rs-report"));
    expect(screenPrint?.decls.get("print-color-adjust")).toBe("exact");
  });
});
