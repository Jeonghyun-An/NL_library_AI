// frontend/tests/unit/themeDetail.test.ts
// round08 — 상세 화면 스타일(assets/css/detail.css)은 색을 테마 토큰으로만 쓴다.
//  ① 색 리터럴(#hex·rgb()·rgba()·hsl()·색 이름)이 없다 ② 쓰는 --skx-* 변수는 모두 style_skovix.css 의 :root 에 선언돼 있다
//  (없는 토큰을 쓰면 var() 가 빈 값이 돼 바탕·글자가 조용히 사라진다)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

function read(rel: string): string {
  return readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf-8");
}

// 주석을 지운다 — 주석 안의 설명(예: '흰 10%')·선택자가 검사에 걸리지 않게. url(...) 안의 경로도 뺀다
const detailCss = read("../../assets/css/detail.css")
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/url\([^)]*\)/g, "");
const rootBlock =
  read("../../assets/css/style_skovix.css")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .match(/(?:^|\n):root\s*\{([^}]*)\}/)?.[1] ?? "";

describe("상세 화면 스타일 — 색은 토큰으로만", () => {
  it("detail.css 를 읽었고 :root 블록을 찾았다", () => {
    expect(detailCss.length).toBeGreaterThan(0);
    expect(rootBlock).toMatch(/--skx-/);
  });

  it("색 리터럴(#hex·rgb()·rgba()·hsl()·색 이름)이 없다", () => {
    const literals =
      detailCss.match(
        /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|(?<![\w-])(?:white|black|red|green|blue|gray|grey|currentcolor)(?![\w-])/gi,
      ) ?? [];
    expect(literals).toEqual([]);
  });

  it("쓰는 --skx-* 변수는 모두 :root 에 선언돼 있다", () => {
    const declared = new Set([...rootBlock.matchAll(/(--skx-[\w-]+)\s*:/g)].map((m) => m[1]));
    const used = new Set([...detailCss.matchAll(/var\(\s*(--skx-[\w-]+)/g)].map((m) => m[1]));
    expect(used.size).toBeGreaterThan(0);
    expect([...used].filter((name) => !declared.has(name))).toEqual([]);
  });

  it("새 색 토큰을 detail.css 안에서 만들지 않는다(다시 정의는 :root 의 토큰을 가리키는 것만)", () => {
    // 틀 안에서 글 톤을 바꾸는 --skx-ink: var(--skx-read-ink) 같은 다시 정의는 되고, 값이 var() 가 아닌 선언은 안 된다
    // 선언은 { 나 ; 바로 뒤에서 시작한다 — 선택자 속 .dt-btn--ghost:hover 를 선언으로 잘못 읽지 않게
    const redefinitions = [...detailCss.matchAll(/(?:^|[{;])\s*(--[\w-]+)\s*:\s*([^;{}]+);/g)].filter(
      ([, , value]) => !/^var\(--skx-[\w-]+\)$/.test(value!.trim()),
    );
    expect(redefinitions.map(([, name, value]) => `${name}: ${value}`)).toEqual([]);
  });
});
