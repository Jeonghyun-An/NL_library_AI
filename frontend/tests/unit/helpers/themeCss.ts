// frontend/tests/unit/helpers/themeCss.ts
// 테마 테스트들이 같이 쓰는 도구 — style_skovix.css 에서 테마별 --skx-* 토큰을 읽고 색 계산(알파 합성·screen·대비)을 한다.
// 기본(dark-green)은 :root 블록이고, 다른 테마는 html[data-theme="이름"] 블록이 같은 토큰을 다시 선언한다(그 안에 없는 토큰은 :root 값을 그대로 쓴다).
// 밝은 읽는 면(.skx-reading)은 자기 블록이 모든 토큰을 다시 선언하고, 테마마다 html[data-theme="이름"] .skx-reading 이 일부를 덮어쓴다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { DEFAULT_THEME, THEMES, type ThemeName } from "~/utils/theme";

export const cssPath = fileURLToPath(new URL("../../../assets/css/style_skovix.css", import.meta.url));
export const rawCss = readFileSync(cssPath, "utf-8");
/** 주석을 지운 CSS — 주석 안의 선택자·중괄호에 블록 찾기가 속지 않게 */
export const css = rawCss.replace(/\/\*[\s\S]*?\*\//g, "");

export { THEMES, DEFAULT_THEME };
export type { ThemeName };

/** 선택자 바로 뒤 `{ ... }` 블록 본문(중첩 괄호 없는 토큰 블록만). 없으면 null */
export function findBlock(selector: string, source: string = css): string | null {
  const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const m = source.match(new RegExp(`(?:^|\\n)${esc}\\s*\\{([^}]*)\\}`));
  return m?.[1] ?? null;
}

export function blockOrThrow(selector: string, source: string = css): string {
  const body = findBlock(selector, source);
  if (body === null) throw new Error(`블록을 찾지 못함: ${selector}`);
  return body;
}

/** 블록 안의 `--skx-*: 값;` 선언 전부(값은 공백을 한 칸으로 줄인다). #hex 는 3·6자리만 받는다 */
export function declarations(body: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/(--skx-[\w-]+)\s*:\s*([^;]+);/g)) {
    const [, name, raw] = m;
    if (!name || !raw) continue;
    const value = raw.trim().replace(/\s+/g, " ");
    if (value.startsWith("#") && !/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)) {
      throw new Error(`${name}: #hex 는 3·6자리만 쓴다 — ${value}`);
    }
    out[name] = value;
  }
  return out;
}

export const themeSelector = (theme: ThemeName) => `html[data-theme="${theme}"]`;
export const themeReadingSelector = (theme: ThemeName) => `${themeSelector(theme)} .skx-reading`;

/** :root 블록의 선언 — 모든 테마의 바탕 */
export const rootDecls = declarations(blockOrThrow(":root"));
/** .skx-reading 블록의 선언 */
export const readingBaseDecls = declarations(blockOrThrow(".skx-reading"));

/** 이 테마 블록이 직접 선언한 토큰(기본 테마는 :root 전체). 블록이 없으면 null */
export function ownDecls(theme: ThemeName): Record<string, string> | null {
  if (theme === DEFAULT_THEME) return rootDecls;
  const body = findBlock(themeSelector(theme));
  return body === null ? null : declarations(body);
}

/** var(--x) 참조를 풀어 준 값(순환·없는 토큰은 던진다) */
export function resolveVars(value: string, tokens: Record<string, string>, depth = 0): string {
  if (depth > 8) throw new Error(`var() 참조가 너무 깊다: ${value}`);
  return value.replace(/var\(\s*(--[\w-]+)\s*\)/g, (_, name: string) => {
    const v = tokens[name];
    if (v === undefined) throw new Error(`${name} 을 찾지 못함`);
    return resolveVars(v, tokens, depth + 1);
  });
}

/** 이 테마에서 실제로 쓰이는 토큰 값(:root + 테마 블록, var() 는 풀어 둔다) */
export function themeTokens(theme: ThemeName): Record<string, string> {
  const own = ownDecls(theme);
  if (!own) throw new Error(`테마 블록이 없음: ${theme}`);
  const merged = { ...rootDecls, ...own };
  return Object.fromEntries(Object.entries(merged).map(([k, v]) => [k, resolveVars(v, merged)]));
}

/** 이 테마의 밝은 읽는 면(.skx-reading) 토큰 */
export function readingTokens(theme: ThemeName): Record<string, string> {
  const extra = theme === DEFAULT_THEME ? null : findBlock(themeReadingSelector(theme));
  const merged = { ...readingBaseDecls, ...(extra ? declarations(extra) : {}) };
  return Object.fromEntries(Object.entries(merged).map(([k, v]) => [k, resolveVars(v, merged)]));
}

/** 테마 정의 블록 전부 — 색 리터럴을 허용하는 자리(가드 테스트가 이 밖만 센다) */
export function themeBlockSelectors(): string[] {
  return [
    ":root",
    ".skx-reading",
    ...THEMES.filter((t) => t !== DEFAULT_THEME).flatMap((t) => [themeSelector(t), themeReadingSelector(t)]),
  ];
}

// ───────── 색 ─────────
export type Rgb = [number, number, number];
export type Rgba = { rgb: Rgb; a: number };

export function hexToRgb(hex: string): Rgb {
  let h = hex.replace("#", "");
  if (h.length === 3) h = h.replace(/(.)/g, "$1$1");
  const n = parseInt(h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const RGBA_RE = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)/g;

/** 값 안의 rgb()/rgba() 정지점 전부(콤마식) */
export function rgbaStops(text: string): Rgba[] {
  return [...text.matchAll(RGBA_RE)].map((m) => ({
    rgb: [Number(m[1]), Number(m[2]), Number(m[3])] as Rgb,
    a: m[4] === undefined ? 1 : Number(m[4]),
  }));
}

/** 단색 값(#hex 또는 rgb(a)) 하나를 읽는다 — 그라데이션은 읽지 못해 던진다 */
export function parseColor(value: string): Rgba {
  const v = value.trim();
  if (v.startsWith("#")) return { rgb: hexToRgb(v), a: 1 };
  const stops = rgbaStops(v);
  if (stops.length !== 1 || /gradient/.test(v)) throw new Error(`단색을 읽지 못함: ${value}`);
  return stops[0]!;
}

/** 그라데이션 토큰에서 가장 센(알파 큰) 정지점 */
export function peakStop(value: string): Rgba {
  const stops = rgbaStops(value);
  if (stops.length === 0) {
    // #hex 한 개짜리 단색도 받는다
    return parseColor(value);
  }
  return stops.reduce((m, s) => (s.a > m.a ? s : m));
}

/** 보통(normal) 알파 혼합 */
export function over(backdrop: Rgb, src: Rgb, a: number): Rgb {
  return backdrop.map((b, i) => (1 - a) * b + a * src[i]!) as Rgb;
}

/** mix-blend-mode: screen + 알파 */
export function screen(backdrop: Rgb, src: Rgb, a: number): Rgb {
  return backdrop.map((b, i) => {
    const bb = b / 255;
    const ss = src[i]! / 255;
    const sc = 1 - (1 - bb) * (1 - ss);
    return 255 * ((1 - a) * bb + a * sc);
  }) as Rgb;
}

export function luminance([r, g, b]: Rgb): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function contrast(a: Rgb, b: Rgb): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** 토큰 값이 단색이면 그 색, 반투명이면 불투명 면(--skx-white)을 깔고 합성한 색 */
export function solidOf(value: string, tokens: Record<string, string>): Rgb {
  const c = parseColor(value);
  if (c.a >= 1) return c.rgb;
  const base = parseColor(tokens["--skx-white"] ?? "#ffffff").rgb;
  return over(base, c.rgb, c.a);
}

// ───────── 움직이는 홀로그램 배경(.skx-holo) ─────────
export type HoloModel = {
  /** 바탕(페이지 색 + 번짐 층을 모든 부분집합으로 얹은 자리들) */
  bases: Rgb[];
  /** 띠마다의 정지점(알파>0) */
  bands: Rgba[][];
  /** 사이드바 막(없으면 null) */
  veil: Rgba | null;
};

const BAND_TOKENS = ["--skx-holo-band-1", "--skx-holo-band-2", "--skx-holo-band-3"];

export function holoModel(theme: ThemeName): HoloModel {
  const t = themeTokens(theme);
  const page = parseColor(t["--skx-page-bg"]!).rgb;
  // 번짐 층(radial-gradient)마다 가장 센 정지점 — 한 층은 그 자리에 있거나 없거나다
  const washLayers = (t["--skx-holo-wash"]!.match(/radial-gradient\([^]*?\)(?=\s*,\s*radial-gradient|\s*$)/g) ?? []).map(
    (layer) => rgbaStops(layer).filter((s) => s.a > 0).reduce<Rgba | null>((m, s) => (!m || s.a > m.a ? s : m), null),
  );
  const layers = washLayers.filter((l): l is Rgba => l !== null);
  let bases: Rgb[] = [page];
  for (const layer of layers) {
    bases = bases.flatMap((b) => [b, over(b, layer.rgb, layer.a)]);
  }
  const bands = BAND_TOKENS.map((name) => rgbaStops(t[name]!).filter((s) => s.a > 0)).filter((stops) => stops.length > 0);
  const veilValue = t["--skx-holo-veil"]!;
  const veil = veilValue === "none" ? null : (rgbaStops(veilValue)[0] ?? null);
  return { bases, bands, veil };
}

/**
 * 띠마다 정지점 하나(또는 없음)를 골라 만들 수 있는 모든 합성 — 가장 밝은·어두운 자리가 포함된다.
 * maxBands 는 한 자리에 동시에 겹칠 수 있는 띠 수의 상한(기본: 모두)
 */
export function composites(model: HoloModel, maxBands: number = Infinity): Rgb[] {
  const out: Rgb[] = [];
  const walk = (i: number, backdrop: Rgb, used: number) => {
    if (i === model.bands.length) {
      out.push(backdrop);
      return;
    }
    walk(i + 1, backdrop, used); // 이 띠가 그 자리를 지나지 않는 경우
    if (used >= maxBands) return;
    for (const s of model.bands[i]!) walk(i + 1, screen(backdrop, s.rgb, s.a), used + 1);
  };
  for (const base of model.bases) walk(0, base, 0);
  return out;
}
