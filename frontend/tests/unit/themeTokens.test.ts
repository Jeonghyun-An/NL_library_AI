// frontend/tests/unit/themeTokens.test.ts
// round08 — 다크 글래스 테마 토큰을 지킨다.
// style_skovix.css 의 :root 와 .skx-reading 블록에서 --skx-* 선언을 읽어
//  ① 밝은 면이 다크 토큰을 빠짐없이 다시 선언하는지 ② 글자 대비(WCAG 상대 휘도)가 4.5:1 이상인지 검사한다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const cssPath = fileURLToPath(
  new URL("../../assets/css/style_skovix.css", import.meta.url),
);
// 주석을 먼저 지운다 — 주석 안의 선택자·중괄호에 블록 찾기가 속지 않게
const css = readFileSync(cssPath, "utf-8").replace(/\/\*[\s\S]*?\*\//g, "");

/** 선택자 바로 뒤 `{ ... }` 블록 본문. 중첩 괄호가 없는 토큰 블록만 대상 */
function blockBody(selectorPattern: RegExp): string {
  const m = css.match(
    new RegExp(`(?:^|\\n)${selectorPattern.source}\\s*\\{([^}]*)\\}`),
  );
  if (!m?.[1]) throw new Error(`블록을 찾지 못함: ${selectorPattern}`);
  return m[1];
}

/** 블록 안의 `--skx-*: 값;` 선언 전부. #hex 값은 3·6자리만 받고 4·8자리는 명시적으로 실패시킨다 */
function declarations(body: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/(--skx-[\w-]+)\s*:\s*([^;]+);/g)) {
    const [, name, raw] = m;
    if (!name || !raw) continue;
    const value = raw.trim();
    if (value.startsWith("#") && !/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)) {
      throw new Error(`${name}: #hex 는 3·6자리만 쓴다 — ${value}`);
    }
    out[name] = value;
  }
  return out;
}

function toRgb(hex: string): [number, number, number] {
  let h = hex.replace("#", "");
  if (h.length === 3) h = h.replace(/(.)/g, "$1$1");
  const n = parseInt(h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function luminance(hex: string): number {
  const [r, g, b] = toRgb(hex).map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

const dark = declarations(blockBody(/:root/));
const reading = declarations(blockBody(/\.skx-reading/));
const scopes = { 다크: dark, "밝은 읽는 면(.skx-reading)": reading } as const;

/** #hex 로 선언된 토큰의 값 — 없거나 hex 가 아니면 실패 */
function hex(tokens: Record<string, string>, name: string): string {
  const v = tokens[name];
  if (!v?.startsWith("#")) throw new Error(`${name} 값을 #hex 로 찾지 못함: ${v}`);
  return v;
}

describe("테마 토큰 — 밝은 읽는 면이 다크 토큰을 다시 선언한다", () => {
  it(":root 의 --skx-* (반경 제외)가 모두 .skx-reading 에도 있다", () => {
    const missing = Object.keys(dark).filter(
      (name) => !name.startsWith("--skx-radius-") && !(name in reading),
    );
    expect(missing).toEqual([]);
  });
});

describe("테마 토큰 대비 4.5:1 이상", () => {
  // [범위, 글자색 토큰, 바탕색 토큰]
  const pairs: [keyof typeof scopes, string, string][] = [
    ["다크", "--skx-ink", "--skx-white"],
    ["다크", "--skx-gray-1", "--skx-white"],
    ["다크", "--skx-gray-2", "--skx-white"],
    ["다크", "--skx-on-accent", "--skx-accent"],
    // 딥리서치가 포인트색 배경 위에 color: var(--skx-white) 로 얹는 글자
    ["다크", "--skx-white", "--skx-primary"],
    ["밝은 읽는 면(.skx-reading)", "--skx-ink", "--skx-white"],
    ["밝은 읽는 면(.skx-reading)", "--skx-gray-1", "--skx-white"],
    ["밝은 읽는 면(.skx-reading)", "--skx-primary", "--skx-white"],
    ["밝은 읽는 면(.skx-reading)", "--skx-white", "--skx-primary"],
    ["밝은 읽는 면(.skx-reading)", "--skx-accent-strong", "--skx-white"],
    // 상태색(성공) — 초록 점·글자·일치율 링
    ["다크", "--skx-success", "--skx-white"],
    ["밝은 읽는 면(.skx-reading)", "--skx-success", "--skx-white"],
    ["밝은 읽는 면(.skx-reading)", "--skx-success", "--skx-success-bg"],
    // 옅은 청록 틴트(--skx-glass-teal) 위에 얹는 포인트색·청록 글자(키워드 칩·선택된 메뉴 항목·KCI 배지).
    // 다크의 틴트는 rgba 라 여기서 못 읽는다 — 다크는 짙은 면 위 7:1 이상(수동 계산)
    ["밝은 읽는 면(.skx-reading)", "--skx-primary", "--skx-glass-teal"],
    ["밝은 읽는 면(.skx-reading)", "--skx-teal-ink", "--skx-glass-teal"],
  ];

  it.each(pairs)("%s: %s 글자가 %s 바탕 위에서 읽힌다", (scope, fg, bg) => {
    const tokens = scopes[scope];
    expect(contrast(hex(tokens, fg), hex(tokens, bg))).toBeGreaterThanOrEqual(
      4.5,
    );
  });
});

describe("하드코딩 색 회귀 가드", () => {
  // :root·.skx-reading·.skx-holo 블록 밖에 색 리터럴(#hex·rgb()·rgba()·hsl()·색 이름·currentColor)이 다시 늘지 않게 센다.
  // 새 색은 --skx-* 토큰으로 쓰고, 정말 고정이어야 하면 이 숫자를 올리며 이유를 남긴다.
  // 의도적 잔존: 그림자·모달 막(scrim)·광택/글로우 하이라이트·/recommend 파스텔 카드·색조 틴트·건드리지 않은 chat-side 블록(옛 흰색 폴백).
  const MAX_LITERALS_OUTSIDE_TOKEN_BLOCKS = 65;

  const rawCss = readFileSync(cssPath, "utf-8");
  const outside = rawCss
    // 홀로그램 구간은 themeHolo.test.ts 가 따로 지킨다
    .replace(
      /\/\* \[S\] 움직이는 홀로그램 배경 \*\/[\s\S]*?\/\* \[E\] 움직이는 홀로그램 배경 \*\//,
      "",
    )
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/url\([^)]*\)/g, "")
    .replace(/(?:^|\n):root\s*\{[^}]*\}/, "")
    .replace(/(?:^|\n)\.skx-reading\s*\{[^}]*\}/, "");

  it("토큰 블록 밖 색 리터럴 수가 기준 이하다", () => {
    const literals =
      outside.match(
        /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|(?<![\w-])(?:white|black|red|green|blue|gray|grey|currentcolor)(?![\w-])/gi,
      ) ?? [];
    expect(literals.length).toBeLessThanOrEqual(
      MAX_LITERALS_OUTSIDE_TOKEN_BLOCKS,
    );
  });
});
