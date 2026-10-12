// frontend/tests/unit/themeHolo.test.ts
// round08 — 움직이는 홀로그램 배경(.skx-holo)이 글자 가독성을 해치지 않는지 지킨다.
// style_skovix.css 의 띠(.skx-holo__band--N) 정지점 알파를 읽어 띠가 모두 가장 밝게 겹친 최악의 합성을 만들고,
//  ① 그 위에 유리 색(--skx-glass·--skx-glass-2)을 알파 합성한 카드 위에서 본문색(--skx-ink)이 4.5:1 이상,
//  ② 카드 없이 페이지 위에 놓이는 큰 흰 제목(#fff)이 3:1 이상인지 계산한다.
// 유리·본문색은 :root 토큰에서 읽는다(사본 없음). 읽지 못하는 색 표기가 있으면 조용히 통과하지 않고 실패한다.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const rawCss = readFileSync(
  fileURLToPath(new URL("../../assets/css/style_skovix.css", import.meta.url)),
  "utf-8",
);
const css = rawCss.replace(/\/\*[\s\S]*?\*\//g, "");
const holoSection = (() => {
  const m = rawCss.match(
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

/** 이 테스트가 읽을 수 없는 색 표기 — transparent·마스크용 #000·rgba 콤마식만 허용한다 */
function unreadableColors(block: string): string[] {
  const found: string[] = [];
  const anyRgb = block.match(/\brgba?\(/g)?.length ?? 0;
  const comma = [...block.matchAll(RGBA)].length;
  if (anyRgb !== comma) found.push("콤마식이 아닌 rgb()/rgba()");
  for (const h of block.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []) {
    if (h !== "#000") found.push(`hex ${h}`);
  }
  for (const f of block.match(
    /\b(?:hsla?|hwb|lab|lch|oklab|oklch|color-mix|color)\(/g,
  ) ?? []) {
    found.push(f);
  }
  for (const n of block.match(
    /\b(?:white|black|red|green|blue|gray|grey|silver|purple|pink|orange|yellow|teal|aqua|cyan|magenta|coral|violet|currentcolor)\b/gi,
  ) ?? []) {
    found.push(`색 이름 ${n}`);
  }
  return found;
}

function rootToken(name: string): string {
  const root = css.match(/(?:^|\n):root\s*\{([^}]*)\}/)?.[1] ?? "";
  const m = root.match(new RegExp(`${name}\\s*:\\s*([^;]+);`));
  if (!m?.[1]) throw new Error(`${name} 을 :root 에서 찾지 못함`);
  return m[1].trim();
}

function rootStop(name: string): Stop {
  const stop = rgbaStops(rootToken(name))[0];
  if (!stop) throw new Error(`${name} 을 rgba(r, g, b, a) 로 읽지 못함`);
  return stop;
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

function blockOf(selector: RegExp): string {
  const m = holoSection.match(
    new RegExp(`${selector.source}\\s*\\{([^}]*)\\}`),
  );
  if (!m?.[1]) throw new Error(`블록을 찾지 못함: ${selector}`);
  return m[1];
}

/** `.skx-holo` 바탕: 단색 위에 옅은 방사 그라데이션 — 두 겹이 가장 짙게 겹친 자리 */
function worstBase(): Rgb {
  let base = hexToRgb(rootToken("--skx-page-bg"));
  for (const s of rgbaStops(blockOf(/\.skx-holo(?![\w-])/))) {
    base = over(base, s.rgb, s.a);
  }
  return base;
}

const bandBlocks = [
  ...holoSection.matchAll(/\.skx-holo__band--\d+[^{}]*\{([^}]*)\}/g),
].map((m) => m[1] ?? "");

function bands(): Stop[][] {
  return bandBlocks.map(rgbaStops).filter((stops) => stops.length > 0);
}

/** 띠마다 정지점 하나(또는 비어 있음)를 골라 만들 수 있는 모든 합성 — 가장 밝은 자리들이 포함된다 */
function composites(): Rgb[] {
  const all = bands();
  const out: Rgb[] = [];
  const walk = (i: number, backdrop: Rgb) => {
    if (i === all.length) {
      out.push(backdrop);
      return;
    }
    walk(i + 1, backdrop); // 이 띠가 그 자리를 지나지 않는 경우
    for (const s of all[i]!) walk(i + 1, screen(backdrop, s.rgb, s.a));
  };
  walk(0, worstBase());
  return out;
}

describe("홀로그램 배경 — 가독성", () => {
  it("띠가 2~3개이고 정지점이 읽힌다", () => {
    const all = bands();
    expect(all.length).toBeGreaterThanOrEqual(2);
    expect(all.length).toBeLessThanOrEqual(3);
    for (const stops of all) expect(stops.length).toBeGreaterThanOrEqual(1);
  });

  it("띠·바탕 블록에 읽을 수 없는 색 표기(hex·rgb 슬래시·hsl·색 이름 등)가 없다", () => {
    const blocks = [blockOf(/\.skx-holo(?![\w-])/), ...bandBlocks];
    expect(blocks.flatMap(unreadableColors)).toEqual([]);
  });

  it("띠 정지점 알파가 .35 를 넘지 않는다", () => {
    for (const band of bands()) {
      for (const s of band) expect(s.a).toBeLessThanOrEqual(0.35);
    }
  });

  it.each(["--skx-glass", "--skx-glass-2"])(
    "띠가 모두 가장 밝게 겹쳐도 %s 카드 위에서 본문색(--skx-ink)이 4.5:1 이상이다",
    (token) => {
      const ink = hexToRgb(rootToken("--skx-ink"));
      const glass = rootStop(token);
      const worst = Math.min(
        ...composites().map((c) => contrast(ink, over(c, glass.rgb, glass.a))),
      );
      expect(worst).toBeGreaterThanOrEqual(4.5);
    },
  );

  // 뿌연 유리(frost) 면 — 밑에서부터 겹치는 층(짙은 밑칠 → 흰 반투명 …)을 최악의 합성 위에 얹은 면에서 글자가 읽혀야 한다.
  // 흐림은 최악을 덜어 주지만 믿지 않는다. 흰 10% 만으로는 이 최악에서 본문색이 2:1 이라 밑칠이 필요하다(토큰 주석).
  // 그라데이션 토큰(반사광)은 가장 센 정지점의 알파로 면 전체에 깔아 본다 — 글자가 어디에 놓여도 지켜지게
  const peakStop = (token: string): Stop =>
    rgbaStops(rootToken(token)).reduce((m, s) => (s.a > m.a ? s : m));
  const faceWorst = (layers: string[], text: string, tintDelta = 0): number => {
    const fg = hexToRgb(rootToken(text));
    return Math.min(
      ...composites().map((c) =>
        contrast(
          fg,
          layers.reduce<Rgb>((acc, token, i) => {
            const l = peakStop(token);
            return over(acc, l.rgb, i === 0 ? l.a + tintDelta : l.a);
          }, c),
        ),
      ),
    );
  };
  const INPUT_FACE = ["--skx-frost-tint", "--skx-frost-milk", "--skx-frost-reflect"];
  const SIDE_FACE = ["--skx-frost-side-bg"];
  const CHIP_FACE = ["--skx-chip-tint", "--skx-chip-milk"];
  const faces: [string, string[], string[]][] = [
    // [이름, 층 토큰(아래→위), 이 면에 놓이는 글자색 토큰] — 입력창의 안내 글(placeholder)은 --skx-ink-2
    ["입력창·전환·결과 검색바(--skx-frost-fill)", INPUT_FACE, ["--skx-ink", "--skx-ink-2"]],
    ["예시 질문 칸(--skx-chip-fill)", CHIP_FACE, ["--skx-ink"]],
    ["예시 질문 칸 올림(--skx-chip-fill-hover)", ["--skx-chip-tint", "--skx-chip-milk-hover"], ["--skx-ink"]],
    ["사이드바(--skx-frost-side-bg)", SIDE_FACE, ["--skx-ink", "--skx-gray-1"]],
    ["사이드바 [새 검색]", ["--skx-frost-side-bg", "--skx-frost-side-under", "--skx-frost-bg"], ["--skx-ink"]],
    ["사이드바 DeepResearch 묶음 카드", ["--skx-frost-side-bg", "--skx-frost-side-under", "--skx-frost-bg-soft"], ["--skx-ink", "--skx-gray-1"]],
    ["+ 메뉴(--skx-frost-menu-bg)", ["--skx-frost-menu-bg"], ["--skx-ink", "--skx-gray-1"]],
  ];
  const faceCases = faces.flatMap(([name, layers, texts]) =>
    texts.map((text) => [name, layers, text] as const),
  );

  it.each(faceCases.map(([name, layers, text]) => ({ name, layers, text })))(
    "띠가 모두 가장 밝게 겹쳐도 $name 위에서 $text 글자가 4.5:1 이상이다",
    ({ layers, text }) => {
      expect(faceWorst([...layers], text)).toBeGreaterThanOrEqual(4.5);
    },
  );

  // 불투명도로 글자를 지키되 필요 이상으로 짙게 두지 않는다 — 밑칠 알파를 0.06 만 낮춰도 4.5:1 을 못 넘는 값이어야 한다
  // (사용자 피드백 10-12: 밑칠 80%+흰 10% 는 유리 같은 투명감이 사라진다). 더 짙게 고쳐 쓰려면 이 테스트가 막는다
  it.each([
    { name: "입력창·전환·결과 검색바", layers: INPUT_FACE, text: "--skx-ink-2" },
    { name: "사이드바", layers: SIDE_FACE, text: "--skx-gray-1" },
    { name: "예시 질문 칸", layers: CHIP_FACE, text: "--skx-ink" },
  ])("$name 의 밑칠은 가장 낮은 쪽이다(알파를 0.06 낮추면 4.5:1 미만)", ({ layers, text }) => {
    expect(faceWorst(layers, text, -0.06)).toBeLessThan(4.5);
  });

  it("입력창·전환·결과 검색바와 사이드바의 합계 불투명도(밑칠+흰 막)는 0.62 이하다", () => {
    const alpha = (tokens: string[]) =>
      1 - tokens.reduce((rest, t) => rest * (1 - peakStop(t).a), 1);
    expect(alpha(["--skx-frost-tint", "--skx-frost-milk"])).toBeLessThanOrEqual(0.62);
    expect(alpha(SIDE_FACE)).toBeLessThanOrEqual(0.62);
  });

  it("카드 없이 페이지 위에 놓이는 큰 흰 제목(#fff)이 가장 밝은 합성 위에서 3:1 이상이다", () => {
    const worst = Math.min(
      ...composites().map((c) => contrast([255, 255, 255], c)),
    );
    expect(worst).toBeGreaterThanOrEqual(3);
  });

  it("화면 아래 15% 는 마스크로 띠를 걷는다(푸터 글자가 띠 위에 놓이지 않게)", () => {
    const m = blockOf(/\.skx-holo(?![\w-])/).match(
      /(?<![-\w])mask-image:\s*linear-gradient\(\s*180deg[^)]*transparent\s+(\d+)%/,
    );
    expect(m).not.toBeNull();
    expect(Number(m![1])).toBeLessThanOrEqual(85);
  });

  it("푸터 글자색은 --skx-gray-1 이다", () => {
    for (const sel of [".skx-footer__copy", ".skx-footer__credit"]) {
      const block = css.match(new RegExp(`\\n${sel}\\s*\\{([^}]*)\\}`))?.[1];
      expect(block, sel).toMatch(/color:\s*var\(--skx-gray-1\)/);
    }
  });
});

describe("홀로그램 배경 — 유리·성능", () => {
  it("--skx-blur 는 순수 흐림이고 backdrop brightness 계수는 없다", () => {
    expect(rootToken("--skx-blur")).toMatch(/^blur\(\d+px\)$/);
    expect(css).not.toContain("--skx-glass-dim");
  });
});

describe("홀로그램 배경 — 움직임", () => {
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

  it("움직임 줄이기 규칙이 띠 규칙보다 뒤에 있다(같은 특이도라 순서가 이긴다)", () => {
    const reduced = holoSection.indexOf("prefers-reduced-motion");
    const lastBandRule = Math.max(
      ...[...holoSection.matchAll(/\.skx-holo__band--\d+[^{}]*\{/g)].map(
        (m) => m.index!,
      ),
    );
    expect(reduced).toBeGreaterThan(lastBandRule);
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
