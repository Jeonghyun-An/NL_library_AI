// frontend/tests/unit/themeHolo.test.ts
// round08 — 움직이는 홀로그램 배경(.skx-holo)이 글자 가독성을 해치지 않는지 지킨다.
// style_skovix.css 의 띠(.skx-holo__band--N) 정지점 알파를 읽어 띠가 모두 가장 밝게 겹친 최악의 자리를 만들고,
// 유리 카드가 뒤를 --skx-glass-dim 배로 어둡게 누른 뒤(--skx-blur 의 brightness) 유리색(--skx-glass)을 얹었을 때
// 본문색(--skx-ink)이 4.5:1 이상인지 계산한다. 밝기 계수·유리·본문색은 모두 :root 토큰에서 읽는다(사본 없음).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(
  fileURLToPath(new URL("../../assets/css/style_skovix.css", import.meta.url)),
  "utf-8",
);
const holoSection = (() => {
  const m = css.match(
    /\[S\] 움직이는 홀로그램 배경 \*\/([\s\S]*?)\/\* \[E\] 움직이는 홀로그램 배경/,
  );
  if (!m?.[1]) throw new Error("홀로그램 구간을 찾지 못함");
  return m[1].replace(/\/\*[\s\S]*?\*\//g, "");
})();

type Rgb = [number, number, number];
type Stop = { rgb: Rgb; a: number };

const RGBA = /rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)/g;

function rgbaStops(text: string): Stop[] {
  return [...text.matchAll(RGBA)]
    .map((m) => ({
      rgb: [Number(m[1]), Number(m[2]), Number(m[3])] as Rgb,
      a: Number(m[4]),
    }))
    .filter((s) => s.a > 0);
}

function rootToken(name: string): string {
  const root = css.match(/(?:^|\n):root\s*\{([^}]*)\}/)?.[1] ?? "";
  const m = root.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  if (!m?.[1]) throw new Error(`${name} 을 :root 에서 찾지 못함`);
  return m[1].trim();
}

function hexToRgb(hex: string): Rgb {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** 보통(normal) 알파 혼합 */
function over(backdrop: Rgb, src: Rgb, a: number): Rgb {
  return backdrop.map((b, i) => (1 - a) * b + a * src[i]!) as Rgb;
}

/** mix-blend-mode: screen + 알파 */
function screen(backdrop: Rgb, src: Rgb, a: number): Rgb {
  return backdrop.map((b, i) => {
    const bb = b / 255;
    const ss = src[i]! / 255;
    const sc = 1 - (1 - bb) * (1 - ss);
    return 255 * ((1 - a) * bb + a * sc);
  }) as Rgb;
}

function luminance([r, g, b]: Rgb): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: Rgb, b: Rgb): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** `.skx-holo` 바탕: 단색 위에 옅은 방사 그라데이션 — 두 겹이 가장 짙게 겹친 자리 */
function worstBase(): Rgb {
  const block = holoSection.match(/\.skx-holo\s*\{([^}]*)\}/)?.[1];
  if (!block) throw new Error(".skx-holo 블록을 찾지 못함");
  let base = hexToRgb(rootToken("--skx-page-bg"));
  for (const s of rgbaStops(block)) base = over(base, s.rgb, s.a);
  return base;
}

function bands(): Stop[][] {
  const out: Stop[][] = [];
  for (const m of holoSection.matchAll(
    /\.skx-holo__band--\d+\s*\{([^}]*)\}/g,
  )) {
    const stops = rgbaStops(m[1] ?? "");
    if (stops.length) out.push(stops); // 색 없는 공통 규칙(mask 등)은 띠가 아니다
  }
  return out;
}

/** 띠마다 정지점 하나(또는 비어 있음)를 골라 모든 조합을 겹친 뒤, 카드가 어둡게 누르고(brightness) 유리를 얹은 가장 낮은 대비 */
function worstContrast(): number {
  const ink = hexToRgb(rootToken("--skx-ink"));
  const dim = Number(rootToken("--skx-glass-dim"));
  if (!(dim > 0 && dim <= 1)) throw new Error(`--skx-glass-dim 은 0 초과 1 이하: ${dim}`);
  const glass = rgbaStops(rootToken("--skx-glass"))[0];
  if (!glass) throw new Error("--skx-glass 를 rgba 로 읽지 못함");
  const all = bands();
  let worst = Infinity;
  const walk = (i: number, backdrop: Rgb) => {
    if (i === all.length) {
      // filter: brightness() 는 sRGB 값에 계수를 곱한다
      const dimmed = backdrop.map((c) => c * dim) as Rgb;
      worst = Math.min(worst, contrast(ink, over(dimmed, glass.rgb, glass.a)));
      return;
    }
    walk(i + 1, backdrop); // 이 띠가 그 자리를 지나지 않는 경우
    for (const s of all[i]!) walk(i + 1, screen(backdrop, s.rgb, s.a));
  };
  walk(0, worstBase());
  return worst;
}

describe("홀로그램 배경 — 가독성", () => {
  it("띠가 2~3개다", () => {
    expect(bands().length).toBeGreaterThanOrEqual(2);
    expect(bands().length).toBeLessThanOrEqual(3);
  });

  it("--skx-blur 가 --skx-glass-dim 밝기 계수를 쓴다(뒤를 어둡게 누르는 유리)", () => {
    expect(rootToken("--skx-blur")).toMatch(
      /^blur\([^)]+\)\s+brightness\(var\(--skx-glass-dim\)\)$/,
    );
  });

  it("띠가 모두 가장 밝게 겹쳐도 어둡게 누른 유리 카드 위에서 본문색이 4.5:1 이상이다", () => {
    expect(worstContrast()).toBeGreaterThanOrEqual(4.5);
  });

  it("띠 정지점 알파가 .35 를 넘지 않는다", () => {
    for (const band of bands()) {
      for (const s of band) expect(s.a).toBeLessThanOrEqual(0.35);
    }
  });
});

describe("홀로그램 배경 — 움직임·성능", () => {
  it("흐림·배경 위치 애니메이션 없이 transform 만 움직인다", () => {
    expect(holoSection).not.toMatch(/blur\(|filter\s*:|background-position/);
    const frames = [...holoSection.matchAll(/@keyframes skx-holo-\w+\s*\{/g)];
    expect(frames.length).toBeGreaterThanOrEqual(2);
    // 키프레임 안의 선언은 transform 하나뿐이다
    const decls = holoSection
      .split(/@keyframes/)
      .slice(1)
      .flatMap((k) => [...k.split("@media")[0]!.matchAll(/([\w-]+)\s*:/g)])
      .map((m) => m[1]);
    expect(new Set(decls)).toEqual(new Set(["transform"]));
  });

  it("움직임 줄이기 설정에서는 띠 애니메이션이 멈춘다", () => {
    expect(holoSection).toMatch(
      /@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.skx-holo__band\s*\{\s*animation:\s*none;/,
    );
  });

  it("띠 애니메이션 주기가 18~40초이고 서로 다르다", () => {
    const secs = [...holoSection.matchAll(/animation:\s*skx-holo-\w+\s+(\d+)s/g)].map(
      (m) => Number(m[1]),
    );
    expect(secs.length).toBeGreaterThanOrEqual(2);
    for (const s of secs) {
      expect(s).toBeGreaterThanOrEqual(18);
      expect(s).toBeLessThanOrEqual(40);
    }
    expect(new Set(secs).size).toBe(secs.length);
  });
});
