// frontend/tests/unit/themeFrost.test.ts
// 뿌연 유리(frost) — 성능·대체·범위를 지킨다.
//  ① 딥리서치 화면까지 번지지 않게 기존 --skx-glass 값은 그대로다
//  ② 움직이는 홀로그램 위의 backdrop-filter 는 꼭 필요한 면으로만 건다(개수 제한)
//  ③ backdrop-filter 를 못 쓰거나 투명도 줄이기 설정이면 불투명 면으로 돌아간다
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  fileURLToPath(new URL("../../assets/css/style_skovix.css", import.meta.url)),
  "utf-8",
).replace(/\/\*[\s\S]*?\*\//g, "");

function rootToken(name: string): string {
  const root = css.match(/(?:^|\n):root\s*\{([^}]*)\}/)?.[1] ?? "";
  const m = root.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  if (!m?.[1]) throw new Error(`${name} 을 :root 에서 찾지 못함`);
  return m[1].trim().replace(/\s+/g, " ");
}

/** backdrop-filter 를 none 이 아닌 값으로 거는 규칙의 선택자(정규화) 목록 */
function blurredSelectors(): string[] {
  const out: string[] = [];
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const body = m[2] ?? "";
    const decl = body.match(/(?<![-\w])backdrop-filter\s*:\s*([^;]+);/);
    if (!decl || /^none$/.test((decl[1] ?? "").trim())) continue;
    // 미디어·@supports 블록 안 규칙의 앞쪽 `@…{` 조각은 선택자에서 뗀다
    const selector = (m[1] ?? "").replace(/^[\s\S]*\{/, "").replace(/\s+/g, " ").trim();
    out.push(selector);
  }
  return out;
}

describe("뿌연 유리 — 범위", () => {
  it("기존 --skx-glass 값은 그대로다(딥리서치 화면이 같은 토큰을 쓴다)", () => {
    expect(rootToken("--skx-glass")).toBe("rgba(18, 44, 38, 0.62)");
    expect(rootToken("--skx-glass-2")).toBe("rgba(18, 44, 38, 0.5)");
  });

  it("흰 반투명 바탕은 10% 다(시안)", () => {
    expect(rootToken("--skx-frost-bg")).toBe("rgba(255, 255, 255, 0.1)");
  });

  it("투명감은 불투명도가 아니라 흐림·반사광·윗선이 맡는다 — 흐림 20px 대, 반사광은 135도 기울기, 윗선이 있다", () => {
    expect(rootToken("--skx-frost-blur")).toMatch(/^blur\(2\dpx\) saturate\(1\.\d+\)$/);
    expect(rootToken("--skx-frost-reflect")).toMatch(/^linear-gradient\(135deg,/);
    expect(rootToken("--skx-frost-fill")).toContain("var(--skx-frost-reflect)");
    expect(rootToken("--skx-frost-hilite")).toContain("inset 0 1px 0 0");
  });
});

describe("뿌연 유리 — 성능(backdrop-filter 개수 제한)", () => {
  it("흐림을 거는 면은 입력창·전환·사이드바·결과 검색바·메뉴·목록뿐이다", () => {
    const allowed = new Set([
      ".skx-lnb",
      ".skx-seg",
      ".skx-search__box",
      ".skx-rsearch",
      ".rs-plus__anchor .rs-plus__menu",
      ".skx-search__box .rs-plus__palette, .skx-rsearch .rs-plus__palette",
      ".skx-rel__pop",
    ]);
    const unexpected = blurredSelectors().filter((sel) => !allowed.has(sel));
    expect(unexpected).toEqual([]);
  });

  it("예시 질문 칸은 입력창보다 한 단계 낮은 면이라 흐림을 걸지 않는다", () => {
    expect(blurredSelectors()).not.toContain(".skx-chip");
  });

  it("목록 카드·결과 카드·AI 패널에는 흐림을 걸지 않는다", () => {
    const joined = blurredSelectors().join(" | ");
    for (const banned of [".skx-book-card", ".skx-rc", ".skx-result-card", ".skx-rframe", ".skx-aip", ".skx-pick", ".skx-pai"]) {
      expect(joined, banned).not.toContain(banned);
    }
  });
});

describe("뿌연 유리 — 대체", () => {
  it("backdrop-filter 를 못 쓰면(@supports not) 불투명 면으로 돌아간다", () => {
    const block = css.match(/@supports not \(\(backdrop-filter: blur\(1px\)\) or \(-webkit-backdrop-filter: blur\(1px\)\)\)\s*\{([\s\S]*?)\n\}/)?.[1];
    expect(block).toBeDefined();
    expect(block).toContain(".skx-search__box");
    expect(block).toContain("var(--skx-frost-solid)");
    expect(block).toContain(".skx-lnb");
  });

  it("투명도 줄이기 설정이면 흐림을 끄고 불투명 면을 쓴다", () => {
    const block = css.match(/@media \(prefers-reduced-transparency: reduce\)\s*\{([\s\S]*?)\n\}/)?.[1];
    expect(block).toBeDefined();
    expect(block).toContain(".skx-search__box");
    expect(block).toContain("backdrop-filter: none");
    expect(block).toContain("var(--skx-frost-solid)");
    expect(block).toContain(".rs-plus__menu");
  });
});
