// frontend/tests/unit/themeFrost.test.ts
// 뿌연 유리(frost) — 성능·대체·범위를 지킨다. 테마마다 같은 검사를 돌린다.
//  ① 딥리서치 화면까지 번지지 않게 다크 그린의 기존 --skx-glass 값은 그대로다
//  ② 움직이는 홀로그램 위의 backdrop-filter 는 꼭 필요한 면으로만 건다(테마마다 면 목록·개수를 못 박는다)
//  ③ backdrop-filter 를 못 쓰거나 투명도 줄이기 설정이면 불투명 면으로 돌아간다
//  ④ 핑크는 배경이 비쳐 보이는 유리다 — 면의 흰 바탕 알파가 낮고 불투명 밑칠이 없다
import { describe, expect, it } from "vitest";
import {
  DEFAULT_THEME,
  THEMES,
  css,
  peakStop,
  resolveVars,
  themeTokens,
  type ThemeName,
} from "./helpers/themeCss";

/** backdrop-filter 를 거는 규칙(선택자·값). `none` 으로 끄는 규칙은 뺀다 */
function backdropRules(): { selector: string; value: string }[] {
  const out: { selector: string; value: string }[] = [];
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const decl = (m[2] ?? "").match(/(?<![-\w])backdrop-filter\s*:\s*([^;]+);/);
    if (!decl) continue;
    // 미디어·@supports 블록 안 규칙의 앞쪽 `@…{` 조각은 선택자에서 뗀다
    const selector = (m[1] ?? "").replace(/^[\s\S]*\{/, "").replace(/\s+/g, " ").trim();
    out.push({ selector, value: (decl[1] ?? "").trim() });
  }
  return out;
}

/** 이 테마에서 실제로 흐림이 걸리는 면의 선택자(토큰을 풀어 none 이 아닌 것) */
function blurredSelectors(theme: ThemeName): string[] {
  const t = themeTokens(theme);
  return backdropRules()
    .filter(({ value }) => resolveVars(value, t).trim() !== "none")
    .map(({ selector }) => selector);
}

/** 모든 테마가 흐림을 거는 면 */
const BASE_BLURRED = [
  ".skx-lnb",
  ".skx-seg",
  ".skx-search__box",
  ".skx-rsearch",
  ".skx-chat-panel__inner",
  ".rs-plus__anchor .rs-plus__menu",
  ".skx-search__box .rs-plus__palette, .skx-rsearch .rs-plus__palette",
  ".skx-rel__pop",
  // 논문 AI 요약의 인용 번호를 누르면 뜨는 작은 카드 — 열려 있는 동안만 한 면
  ".skx-citepop",
];
/** 핑크가 더 거는 면 — 비치는 흰 유리라서 예시 질문 칸과 결과 AI 패널에도 흐림을 건다 */
const PINK_EXTRA_BLURRED = [".skx-chip", ".skx-aip"];

const ALLOWED: Record<ThemeName, string[]> = {
  "dark-green": BASE_BLURRED,
  pink: [...BASE_BLURRED, ...PINK_EXTRA_BLURRED],
};

describe("뿌연 유리 — 다크 그린 범위", () => {
  const t = themeTokens(DEFAULT_THEME);

  it("기존 --skx-glass 값은 그대로다(딥리서치 화면이 같은 토큰을 쓴다)", () => {
    expect(t["--skx-glass"]).toBe("rgba(18, 44, 38, 0.62)");
    expect(t["--skx-glass-2"]).toBe("rgba(18, 44, 38, 0.5)");
  });

  it("흰 반투명 바탕은 10% 다(시안)", () => {
    expect(t["--skx-frost-bg"]).toBe("rgba(255, 255, 255, 0.1)");
  });

  it("예시 질문 칸·AI 패널의 흐림과 예시 칸 그림자는 꺼져 있다(핑크 전용 토큰)", () => {
    expect(t["--skx-chip-blur"]).toBe("none");
    expect(t["--skx-aip-blur"]).toBe("none");
    expect(t["--skx-chip-shadow"]).toBe("none");
  });
});

describe.each(THEMES)("뿌연 유리 — 모양 [%s]", (theme: ThemeName) => {
  const t = themeTokens(theme);

  it("투명감은 흐림·반사광·윗선이 맡는다 — 흐림 20px 대, 반사광은 135도 기울기, 안쪽 윗선이 있다", () => {
    expect(t["--skx-frost-blur"]).toMatch(/^blur\(2\dpx\) saturate\(1\.\d+\)$/);
    expect(t["--skx-frost-reflect"]).toMatch(/^linear-gradient\(135deg,/);
    expect(t["--skx-frost-fill"]).toContain("linear-gradient(135deg");
    expect(t["--skx-frost-hilite"]).toContain("inset 0 1px 0 0");
  });

  it("사이드바·AI 패널·유리 면의 테두리 띠 토큰은 그라데이션이다", () => {
    for (const name of ["--skx-side-edge", "--skx-aip-edge", "--skx-frost-edge"]) {
      expect(t[name], name).toMatch(/^linear-gradient\(/);
    }
  });
});

describe.each(THEMES)("뿌연 유리 — 성능(backdrop-filter 개수 제한) [%s]", (theme: ThemeName) => {
  it("흐림을 거는 면은 정해 둔 목록뿐이다", () => {
    const allowed = new Set(ALLOWED[theme]);
    const found = blurredSelectors(theme);
    expect(found.filter((sel) => !allowed.has(sel))).toEqual([]);
    // 목록의 면은 모두 실제로 흐림이 걸려 있다(빠지면 유리가 사라진 것)
    expect([...allowed].filter((sel) => !found.includes(sel))).toEqual([]);
  });

  it("흐림을 거는 면은 다크 9곳·핑크 11곳이다(늘리면 이 숫자와 목록을 같이 고친다)", () => {
    expect(blurredSelectors(theme).length).toBe(theme === DEFAULT_THEME ? 9 : 11);
  });

  it("결과 카드·큰 틀·읽는 칸·목록에는 흐림을 걸지 않는다", () => {
    const joined = blurredSelectors(theme).join(" | ");
    for (const banned of [".skx-rc", ".skx-result-card", ".skx-rframe", ".skx-pick", ".skx-pai"]) {
      expect(joined, banned).not.toContain(banned);
    }
  });
});

describe("뿌연 유리 — 다크 그린은 예시 칸·AI 패널에 흐림을 걸지 않는다", () => {
  it("예시 질문 칸·결과 AI 패널은 입력창보다 한 단계 낮은 면이다", () => {
    const found = blurredSelectors(DEFAULT_THEME);
    expect(found).not.toContain(".skx-chip");
    expect(found).not.toContain(".skx-aip");
  });
});

describe("뿌연 유리 — 대체", () => {
  it("backdrop-filter 를 못 쓰면(@supports not) 불투명 면으로 돌아간다", () => {
    const block = css.match(
      /@supports not \(\(backdrop-filter: blur\(1px\)\) or \(-webkit-backdrop-filter: blur\(1px\)\)\)\s*\{([\s\S]*?)\n\}/,
    )?.[1];
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

  it.each(["--skx-frost-solid", "--skx-frost-over"])("[핑크] 불투명 대체색 %s 은(는) 흰색 계열이다", (token) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(themeTokens("pink")[token]!.slice(i, i + 2), 16));
    expect(Math.min(r!, g!, b!)).toBeGreaterThanOrEqual(240);
  });
});

describe("뿌연 유리 — 핑크는 배경이 비쳐 보이는 유리다(사용자 결정 2026-10-13)", () => {
  const t = themeTokens("pink");
  /** 층 토큰들을 아래→위로 쌓은 합계 불투명도 */
  const stacked = (tokens: string[]) => 1 - tokens.reduce((rest, tok) => rest * (1 - peakStop(t[tok]!).a), 1);

  it.each([
    { name: "입력창·전환·결과 검색바", layers: ["--skx-frost-tint", "--skx-frost-milk"], max: 0.45 },
    { name: "예시 질문 칸", layers: ["--skx-chip-tint", "--skx-chip-milk"], max: 0.45 },
    { name: "사이드바 바탕", layers: ["--skx-frost-side-bg"], max: 0.4 },
    { name: "결과 큰 틀", layers: ["--skx-frame-bg"], max: 0.4 },
    { name: "결과 AI 패널", layers: ["--skx-frost-panel"], max: 0.4 },
    { name: "DeepRead 패널", layers: ["--skx-chat-bg"], max: 0.4 },
  ])("$name 의 흰 바탕 알파는 $max 이하다(불투명 밑칠 없음 — 분홍·크림이 비친다)", ({ layers, max }) => {
    expect(stacked(layers)).toBeLessThanOrEqual(max);
  });

  it("흐림을 거는 유리 면마다 흐림 토큰이 켜져 있다(예시 칸·AI 패널 포함)", () => {
    for (const name of ["--skx-frost-blur", "--skx-frost-blur-side", "--skx-chip-blur", "--skx-aip-blur"]) {
      expect(t[name], name).toMatch(/^blur\(\d+px\)/);
    }
  });

  it("가장자리 밝은 선(위가 흰색)과 안쪽 하이라이트가 있다", () => {
    for (const name of ["--skx-frost-edge", "--skx-side-edge", "--skx-aip-edge"]) {
      expect(t[name], name).toMatch(/^linear-gradient\(180deg, rgba\(255, 255, 255, 0\.9\d?\)/);
    }
    expect(t["--skx-frost-hilite"]).toMatch(/inset 0 1px 0 0 rgba\(255, 255, 255, 0\.9/);
    expect(t["--skx-chip-shadow"]).toMatch(/inset 0 1px 0 0 rgba\(255, 255, 255, 0\.9/);
    expect(t["--skx-aip-shadow"]).toMatch(/inset 0 1px 0 0 rgba\(255, 255, 255, 0\.9/);
  });
});
