// frontend/tests/unit/themeTokens.test.ts
// round08 — 다크 글래스 테마 토큰의 글자 대비를 지킨다.
// style_skovix.css 의 :root 와 .skx-paper 블록에서 --skx-* 값을 읽어 WCAG 대비(상대 휘도)를 계산한다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const cssPath = fileURLToPath(
  new URL("../../assets/css/style_skovix.css", import.meta.url),
);
const css = readFileSync(cssPath, "utf-8");

/** 선택자 바로 뒤 `{ ... }` 블록 본문. 중첩 괄호가 없는 토큰 블록만 대상 */
function blockBody(selectorPattern: RegExp): string {
  const m = css.match(
    new RegExp(`(?:^|\\n)${selectorPattern.source}\\s*\\{([^}]*)\\}`),
  );
  if (!m?.[1]) throw new Error(`블록을 찾지 못함: ${selectorPattern}`);
  return m[1];
}

/** 블록 안의 `--skx-*: #hex;` 선언을 모은다(색이 아닌 값은 건너뛴다) */
function hexTokens(body: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/(--skx-[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,6})\s*;/g)) {
    const [, name, value] = m;
    if (name && value) out[name] = value;
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

const dark = hexTokens(blockBody(/:root/));
const paper = hexTokens(blockBody(/\.skx-paper/));

function need(tokens: Record<string, string>, name: string): string {
  const v = tokens[name];
  if (!v) throw new Error(`${name} 값을 #hex 로 찾지 못함`);
  return v;
}

describe("테마 토큰 대비 — 다크(:root)", () => {
  it("본문 글자(--skx-ink)가 불투명 면(--skx-white) 위에서 4.5:1 이상이다", () => {
    expect(
      contrast(need(dark, "--skx-ink"), need(dark, "--skx-white")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("보조 글자(--skx-gray-1)가 불투명 면(--skx-white) 위에서 4.5:1 이상이다", () => {
    expect(
      contrast(need(dark, "--skx-gray-1"), need(dark, "--skx-white")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("포인트색 위 글자(--skx-on-accent)가 포인트색(--skx-accent) 위에서 4.5:1 이상이다", () => {
    expect(
      contrast(need(dark, "--skx-on-accent"), need(dark, "--skx-accent")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("딥리서치가 포인트색(--skx-primary) 배경 위에 쓰는 --skx-white 글자도 4.5:1 이상이다", () => {
    expect(
      contrast(need(dark, "--skx-white"), need(dark, "--skx-primary")),
    ).toBeGreaterThanOrEqual(4.5);
  });
});

describe("테마 토큰 대비 — 밝은 읽는 면(.skx-paper)", () => {
  it("본문 글자(--skx-ink)가 카드(--skx-white) 위에서 4.5:1 이상이다", () => {
    expect(
      contrast(need(paper, "--skx-ink"), need(paper, "--skx-white")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("보조 글자(--skx-gray-1)가 카드(--skx-white) 위에서 4.5:1 이상이다", () => {
    expect(
      contrast(need(paper, "--skx-gray-1"), need(paper, "--skx-white")),
    ).toBeGreaterThanOrEqual(4.5);
  });
});
