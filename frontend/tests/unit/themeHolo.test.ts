// frontend/tests/unit/themeHolo.test.ts
// round08 — 움직이는 홀로그램 배경(.skx-holo)이 글자 가독성을 해치지 않는지 지킨다. 테마마다 같은 검사를 돌린다.
// 띠 색·바탕 번짐·사이드바 막은 테마 토큰(--skx-holo-*)이다. 이 테스트는 그 정지점 알파를 읽어 띠가 모두 가장 밝게 겹친 최악의 합성을 만들고,
//  ① 그 위에 유리 면(입력창·사이드바·큰 틀·읽는 칸 …)을 알파 합성한 자리에서 글자색이 4.5:1 이상,
//  ② 카드 없이 페이지 위에 놓이는 큰 제목이 3:1(다크)·4.5:1(핑크) 이상인지 계산한다.
// 색은 style_skovix.css 에서 읽는다(사본 없음). 읽지 못하는 색 표기가 있으면 조용히 통과하지 않고 실패한다.
import { describe, expect, it } from "vitest";
import {
  DEFAULT_THEME,
  THEMES,
  composites,
  contrast,
  css,
  hexToRgb,
  holoModel,
  over,
  parseColor,
  peakStop,
  rawCss,
  rgbaStops,
  themeTokens,
  type Rgb,
  type ThemeName,
} from "./helpers/themeCss";

const holoSection = (() => {
  const m = rawCss.match(/\[S\] 움직이는 홀로그램 배경 \*\/([\s\S]*?)\/\* \[E\] 움직이는 홀로그램 배경/);
  if (!m?.[1]) throw new Error("홀로그램 구간을 찾지 못함");
  return m[1].replace(/\/\*[\s\S]*?\*\//g, "");
})();

function blockOf(selector: RegExp): string {
  const m = holoSection.match(new RegExp(`${selector.source}\\s*\\{([^}]*)\\}`));
  if (!m?.[1]) throw new Error(`블록을 찾지 못함: ${selector}`);
  return m[1];
}

// 띠 둘이 같이 쓰는 마스크 규칙(.skx-holo__band--2, .skx-holo__band--3)은 배경이 없어 띠로 세지 않는다
const bandBlocks = [...holoSection.matchAll(/\.skx-holo__band--\d+[^{}]*\{([^}]*)\}/g)]
  .map((m) => m[1] ?? "")
  .filter((block) => /(?<![-\w])background:/.test(block));
const veilBlock = holoSection.match(/\.skx-holo__veil\s*\{([^}]*)\}/)?.[1] ?? "";

// ───────── 구조(테마와 무관) ─────────
describe("홀로그램 배경 — 구조", () => {
  it("띠가 2~3개이고 색은 모두 테마 토큰이다", () => {
    expect(bandBlocks.length).toBeGreaterThanOrEqual(2);
    expect(bandBlocks.length).toBeLessThanOrEqual(3);
    for (const block of bandBlocks) expect(block).toMatch(/background:\s*var\(--skx-holo-band-\d\);/);
    expect(blockOf(/\.skx-holo(?![\w-])/)).toMatch(/background:\s*var\(--skx-holo-wash\),\s*var\(--skx-page-bg\);/);
    expect(veilBlock).toMatch(/background:\s*var\(--skx-holo-veil\);/);
  });

  it("홀로그램 구간에 색 리터럴이 없다(마스크용 #000 만) — 색은 테마 블록에서만 정한다", () => {
    const found = [
      ...(holoSection.match(/\brgba?\(|\bhsla?\(/g) ?? []),
      ...(holoSection.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).filter((h) => h !== "#000"),
      ...(holoSection.match(/(?<![\w-])(?:white|black|red|green|blue|gray|grey|pink|currentcolor)(?![\w-])/gi) ?? []),
    ];
    expect(found).toEqual([]);
  });

  it("마스크는 테마 토큰(--skx-holo-mask)이다", () => {
    expect(blockOf(/\.skx-holo(?![\w-])/)).toMatch(/(?<![-\w])mask-image:\s*var\(--skx-holo-mask\);/);
  });

  it("푸터 글자색은 --skx-gray-1 이다", () => {
    for (const sel of [".skx-footer__copy", ".skx-footer__credit"]) {
      const block = css.match(new RegExp(`\\n${sel}\\s*\\{([^}]*)\\}`))?.[1];
      expect(block, sel).toMatch(/color:\s*var\(--skx-gray-1\)/);
    }
  });

  it("사이드바 막(.skx-holo__veil)의 짙은 구간이 사이드바 오른쪽 끝(앱 여백 + 사이드바 폭)까지 덮는다(다크 토큰 기준)", () => {
    const veilToken = themeTokens(DEFAULT_THEME)["--skx-holo-veil"]!;
    const solidEnd = Number(veilToken.match(/rgba\([^)]*\)\s+(\d+(?:\.\d+)?)rem\s*,\s*rgba\([^)]*,\s*0\)/)?.[1]);
    const lnbWidth = Number(css.match(/\n\.skx-lnb\s*\{[^}]*?\bwidth:\s*(\d+(?:\.\d+)?)rem/)?.[1]);
    const appPad = Number(css.match(/\n\.skx-app\s*\{[^}]*?\bpadding:\s*(\d+(?:\.\d+)?)rem/)?.[1]);
    expect(solidEnd).toBeGreaterThanOrEqual(appPad + lnbWidth);
  });
});

// ───────── 테마마다: 띠·바탕 토큰이 읽히고, 글자가 최악의 합성 위에서 읽힌다 ─────────
describe.each(THEMES)("홀로그램 배경 — 가독성 [%s]", (theme: ThemeName) => {
  const t = themeTokens(theme);
  const model = holoModel(theme);
  const dark = theme === DEFAULT_THEME;

  it("띠가 2~3개이고 정지점이 읽힌다", () => {
    expect(model.bands.length).toBeGreaterThanOrEqual(2);
    expect(model.bands.length).toBeLessThanOrEqual(3);
    for (const stops of model.bands) expect(stops.length).toBeGreaterThanOrEqual(1);
  });

  it("바탕 번짐·띠·막의 색 표기가 모두 읽힌다(콤마식 rgb/rgba·#hex·none)", () => {
    for (const name of ["--skx-holo-wash", "--skx-holo-band-1", "--skx-holo-band-2", "--skx-holo-band-3", "--skx-holo-veil"]) {
      const value = t[name]!;
      const anyRgb = value.match(/\brgba?\(/g)?.length ?? 0;
      expect(rgbaStops(value).length, `${name} 의 rgb()/rgba() 를 모두 읽어야 한다`).toBe(anyRgb);
      expect(value, name).not.toMatch(/hsla?\(|hwb\(|lab\(|lch\(|oklab\(|oklch\(|color-mix\(|color\(/);
    }
    expect(parseColor(t["--skx-page-bg"]!).a).toBe(1);
  });

  it("띠 정지점 알파가 .35 를 넘지 않는다", () => {
    for (const band of model.bands) {
      for (const s of band) expect(s.a).toBeLessThanOrEqual(0.35);
    }
  });

  it.each(["--skx-glass", "--skx-glass-2"])(
    "띠가 모두 가장 밝게 겹쳐도 %s 카드 위에서 본문색(--skx-ink)이 4.5:1 이상이다",
    (token) => {
      const ink = parseColor(t["--skx-ink"]!).rgb;
      const glass = parseColor(t[token]!);
      const worst = Math.min(...composites(model).map((c) => contrast(ink, over(c, glass.rgb, glass.a))));
      expect(worst).toBeGreaterThanOrEqual(4.5);
    },
  );

  // 뿌연 유리(frost) 면 — 밑에서부터 겹치는 층(밑칠 → 막 → 반사광 …)을 최악의 합성 위에 얹은 면에서 글자가 읽혀야 한다.
  // 흐림은 최악을 덜어 주지만 믿지 않는다. 그라데이션 토큰(반사광)은 가장 센 정지점의 알파로 면 전체에 깔아 본다 — 글자가 어디에 놓여도 지켜지게
  const faceWorst = (layers: string[], text: string, tintDelta = 0, behindVeil = false): number => {
    const fg = parseColor(t[text]!).rgb;
    return Math.min(
      ...composites(model).map((c) =>
        contrast(
          fg,
          layers.reduce<Rgb>(
            (acc, token, i) => {
              const l = peakStop(t[token]!);
              return over(acc, l.rgb, i === 0 ? l.a + tintDelta : l.a);
            },
            behindVeil && model.veil ? over(c, model.veil.rgb, model.veil.a) : c,
          ),
        ),
      ),
    );
  };
  const INPUT_FACE = ["--skx-frost-tint", "--skx-frost-milk", "--skx-frost-reflect"];
  const SIDE_FACE = ["--skx-frost-side-bg"];
  const CHIP_FACE = ["--skx-chip-tint", "--skx-chip-milk"];
  const SEG_FACE = ["--skx-frost-tint", "--skx-frost-bg", "--skx-frost-reflect"];
  // 결과 화면: 큰 틀(--skx-frame-bg) → AI 패널(--skx-frost-panel) → 읽는 칸(--skx-read-surface). 틀 위의 목록 글은 틀만, 읽는 칸의 글은 세 겹 위에 얹힌다.
  const FRAME_FACE = ["--skx-frame-bg"];
  const READ_FACE = ["--skx-frame-bg", "--skx-frost-panel", "--skx-read-surface"];
  const READ_TEXTS = ["--skx-read-ink", "--skx-read-ink-2", "--skx-read-gray-1"];
  // 사이드바 글 톤은 .skx-lnb 안에서 --skx-ink 등을 --skx-side-* 로 다시 정의한 값이다
  const SIDE_TEXTS = ["--skx-side-ink", "--skx-side-gray-1", "--skx-side-teal-ink", "--skx-side-gray-2"];
  const faces: [string, string[], string[], boolean][] = [
    // [이름, 층 토큰(아래→위), 이 면에 놓이는 글자색 토큰, 사이드바 막(veil) 뒤인가] — 입력창의 안내 글(placeholder)은 --skx-ink-2
    ["입력창·전환·결과 검색바(--skx-frost-fill)", INPUT_FACE, ["--skx-ink", "--skx-ink-2"], false],
    ["예시 질문 칸(--skx-chip-fill)", CHIP_FACE, ["--skx-ink"], false],
    ["예시 질문 칸 올림(--skx-chip-fill-hover)", ["--skx-chip-tint", "--skx-chip-milk-hover"], ["--skx-ink"], false],
    ["사이드바(--skx-frost-side-bg)", SIDE_FACE, SIDE_TEXTS, true],
    ["사이드바 [새 검색]", ["--skx-frost-side-bg", "--skx-frost-side-under", "--skx-frost-bg"], ["--skx-side-ink"], true],
    // 묶음 카드 안의 글 톤은 사이드바 글 톤을 올리기 전 값(--skx-research-*)이다
    [
      "사이드바 DeepResearch 묶음 카드",
      ["--skx-frost-side-bg", "--skx-frost-side-under", "--skx-frost-bg-soft"],
      ["--skx-research-ink", "--skx-research-gray-1"],
      true,
    ],
    ["결과 큰 틀(--skx-frame-bg)", FRAME_FACE, ["--skx-ink", "--skx-gray-1"], false],
    // 전역 오류 화면(SkxErrorPage) — 홀로그램 위 상태 블록 뒤의 유리 면(.skx-error-page .skx-state). 제목·설명·보조 버튼 글
    ["전역 오류 화면 상태 카드(--skx-frame-bg)", FRAME_FACE, ["--skx-ink-strong", "--skx-gray-1"], false],
    ["전역 오류 화면 보조 버튼(--skx-frost-bg-soft)", [...FRAME_FACE, "--skx-frost-bg-soft"], ["--skx-ink"], false],
    // DeepRead 채팅 패널: 머리 글은 패널 위에 바로, AI 말풍선은 옅은 면 + 짙은 글, 사용자 말풍선·입력창은 밑칠 + 막 + 글
    ["DeepRead 패널(--skx-chat-bg)", ["--skx-chat-bg"], ["--skx-ink-strong"], false],
    ["DeepRead AI 말풍선(--skx-chat-ai-bg)", ["--skx-chat-bg", "--skx-chat-ai-bg"], ["--skx-ink-on-light"], false],
    ["DeepRead 사용자 말풍선", ["--skx-chat-bg", "--skx-chat-user-tint", "--skx-chat-user-milk"], ["--skx-ink-strong"], false],
    [
      "DeepRead 입력창(--skx-chat-input-bg)",
      ["--skx-chat-bg", "--skx-chat-input-tint", "--skx-chat-input-milk"],
      ["--skx-ink-strong", "--skx-ink-2"],
      false,
    ],
    ["결과 읽는 칸(--skx-read-surface)", READ_FACE, READ_TEXTS, false],
    ["+ 메뉴(--skx-frost-menu-bg)", ["--skx-frost-menu-bg"], ["--skx-ink", "--skx-gray-1"], false],
    // 설정 팝오버(사이드바 하단 톱니) — 메뉴 바탕 위, 제목·항목 이름은 사이드바 글 톤(.skx-lnb 안에서 --skx-ink·--skx-gray-1 이 --skx-side-* 로 바뀐다)
    ["설정 팝오버(--skx-frost-menu-bg)", ["--skx-frost-menu-bg"], ["--skx-side-ink", "--skx-side-gray-1"], true],
  ];
  const faceCases = faces.flatMap(([name, layers, texts, veil]) =>
    texts.map((text) => ({ name, layers, text, veil })),
  );

  it.each(faceCases)(
    "띠가 모두 가장 밝게 겹쳐도 $name 위에서 $text 글자가 4.5:1 이상이다",
    ({ layers, text, veil }) => {
      expect(faceWorst([...layers], text, 0, veil)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it("카드 없이 페이지 위에 놓이는 큰 제목(--skx-ink-strong)이 가장 밝은·어두운 합성 위에서 기준 이상이다(다크 3:1, 핑크 4.5:1)", () => {
    const fg = parseColor(t["--skx-ink-strong"]!).rgb;
    const worst = Math.min(...composites(model).map((c) => contrast(fg, c)));
    expect(worst).toBeGreaterThanOrEqual(dark ? 3 : 4.5);
  });

  it("화면 아래 15% 는 마스크로 띠를 걷거나(다크), 띠가 겹쳐도 푸터 글자가 읽힌다(핑크)", () => {
    const mask = t["--skx-holo-mask"]!;
    const fg = parseColor(t["--skx-gray-1"]!).rgb;
    if (mask === "none") {
      // 띠를 걷지 않는 테마 — 푸터 글자(--skx-gray-1)가 띠가 모두 겹친 최악의 합성 위에서도 4.5:1 이상이어야 한다
      expect(Math.min(...composites(model).map((c) => contrast(fg, c)))).toBeGreaterThanOrEqual(4.5);
    } else {
      const m = mask.match(/^linear-gradient\(180deg[^)]*transparent (\d+)%\)$/);
      expect(m, `마스크를 읽지 못함: ${mask}`).not.toBeNull();
      expect(Number(m![1])).toBeLessThanOrEqual(85);
      // 걷은 자리는 띠 없이 바탕만 — 그 위에서 푸터 글자가 4.5:1 이상
      expect(Math.min(...model.bases.map((b) => contrast(fg, b)))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("전환 알약: 켜진 칸의 글(--skx-seg-thumb-ink)이 채움(--skx-seg-thumb) 위에서 4.5:1 이상이다", () => {
    expect(
      contrast(parseColor(t["--skx-seg-thumb-ink"]!).rgb, parseColor(t["--skx-seg-thumb"]!).rgb),
    ).toBeGreaterThanOrEqual(4.5);
  });
});

// ───────── 다크 그린 전용: 시안 값을 지키는 상한·하한 ─────────
describe("홀로그램 배경 — 다크 그린 시안 값", () => {
  const theme = DEFAULT_THEME;
  const t = themeTokens(theme);
  const model = holoModel(theme);
  const faceWorst = (layers: string[], text: string, tintDelta = 0): number => {
    const fg = parseColor(t[text]!).rgb;
    return Math.min(
      ...composites(model).map((c) =>
        contrast(
          fg,
          layers.reduce<Rgb>((acc, token, i) => {
            const l = peakStop(t[token]!);
            return over(acc, l.rgb, i === 0 ? l.a + tintDelta : l.a);
          }, c),
        ),
      ),
    );
  };
  const INPUT_FACE = ["--skx-frost-tint", "--skx-frost-milk", "--skx-frost-reflect"];
  const CHIP_FACE = ["--skx-chip-tint", "--skx-chip-milk"];
  const SIDE_FACE = ["--skx-frost-side-bg"];
  const SEG_FACE = ["--skx-frost-tint", "--skx-frost-bg", "--skx-frost-reflect"];

  // 불투명도로 글자를 지키되 필요 이상으로 짙게 두지 않는다 — 밑칠 알파를 0.06 만 낮춰도 4.5:1 을 못 넘는 값이어야 한다
  // (사용자 피드백 10-12: 밑칠 80%+흰 10% 는 유리 같은 투명감이 사라진다). 더 짙게 고쳐 쓰려면 이 테스트가 막는다.
  // 사이드바는 해당 없음 — 바탕 알파(30%)는 시안 값이고, 글자는 막(veil)·밝은 글색이 지킨다
  it.each([
    { name: "입력창·전환·결과 검색바", layers: INPUT_FACE, text: "--skx-ink-2" },
    { name: "예시 질문 칸", layers: CHIP_FACE, text: "--skx-ink" },
  ])("$name 의 밑칠은 가장 낮은 쪽이다(알파를 0.06 낮추면 4.5:1 미만)", ({ layers, text }) => {
    expect(faceWorst(layers, text, -0.06)).toBeLessThan(4.5);
  });

  it("입력창·전환·결과 검색바의 합계 불투명도(밑칠+흰 막)는 0.62 이하이고, 사이드바 바탕 알파는 시안대로 0.30~0.40 이다", () => {
    const alpha = (tokens: string[]) => 1 - tokens.reduce((rest, tok) => rest * (1 - peakStop(t[tok]!).a), 1);
    expect(alpha(["--skx-frost-tint", "--skx-frost-milk"])).toBeLessThanOrEqual(0.62);
    expect(alpha(SIDE_FACE)).toBeGreaterThanOrEqual(0.3);
    expect(alpha(SIDE_FACE)).toBeLessThanOrEqual(0.4);
  });

  // 전환 알약(시안 색, 사용자 결정): 켜진 칸은 짙은 초록 채움 위 흰 글, 꺼진 칸은 회녹색(--skx-gray-2).
  // 꺼진 칸 글은 시안 색이고 바깥 면도 시안의 흰 10%(SEG_FACE)라 모든 띠가 가장 밝게 겹친 최악에는 4.5:1 이 안 된다 —
  // 평온한 자리(띠 없음)에서 3:1, 띠 하나가 지나는 자리에서 2.5:1 이상으로 지킨다(AA 4.5:1 미달은 시안 색 그대로 둔 값이다)
  it.each([
    { bands: 0, min: 3 },
    { bands: 1, min: 2.5 },
  ])("전환 알약: 꺼진 칸의 회녹색 글(--skx-gray-2)이 띠 $bands 개가 겹치는 자리까지 $min:1 이상이다", ({ bands: n, min }) => {
    const fg = parseColor(t["--skx-gray-2"]!).rgb;
    const worst = Math.min(
      ...composites(model, n).map((c) =>
        contrast(
          fg,
          SEG_FACE.reduce<Rgb>((acc, token) => {
            const l = peakStop(t[token]!);
            return over(acc, l.rgb, l.a);
          }, c),
        ),
      ),
    );
    expect(worst).toBeGreaterThanOrEqual(min);
  });
});

// ───────── 핑크 전용: 시안 값 ─────────
describe("홀로그램 배경 — 핑크 시안 값", () => {
  const t = themeTokens("pink");
  const model = holoModel("pink");

  it("전환 알약: 꺼진 칸의 글(--skx-gray-2)은 흰 유리 위에서 띠가 모두 겹쳐도 4.5:1 이상이다(시안 #879491 보다 짙게 잡았다)", () => {
    const fg = parseColor(t["--skx-gray-2"]!).rgb;
    const worst = Math.min(
      ...composites(model).map((c) =>
        contrast(
          fg,
          ["--skx-frost-tint", "--skx-frost-bg", "--skx-frost-reflect"].reduce<Rgb>((acc, token) => {
            const l = peakStop(t[token]!);
            return over(acc, l.rgb, l.a);
          }, c),
        ),
      ),
    );
    expect(worst).toBeGreaterThanOrEqual(4.5);
  });

  it("띠는 흰색 계열이다(밝기를 올려 시안의 진주빛을 낸다) — 띠 색의 세 채널이 모두 230 이상", () => {
    for (const band of model.bands) {
      for (const s of band) expect(Math.min(...s.rgb)).toBeGreaterThanOrEqual(230);
    }
  });

  it("검정 포인트(#1a1115)·시안 글색을 그대로 쓴다", () => {
    expect(hexToRgb(t["--skx-primary"]!)).toEqual(hexToRgb("#1a1115"));
    expect(hexToRgb(t["--skx-ink-strong"]!)).toEqual(hexToRgb("#1a1115"));
  });
});

// ───────── 성능·움직임(테마와 무관) ─────────
describe("홀로그램 배경 — 유리·성능", () => {
  it("--skx-blur 는 순수 흐림이고 backdrop brightness 계수는 없다", () => {
    for (const theme of THEMES) expect(themeTokens(theme)["--skx-blur"]).toMatch(/^blur\(\d+px\)$/);
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
    expect(holoSection).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.skx-holo__band\s*\{\s*animation:\s*none;/);
  });

  it("움직임 줄이기 규칙이 띠 규칙보다 뒤에 있다(같은 특이도라 순서가 이긴다)", () => {
    const reduced = holoSection.indexOf("prefers-reduced-motion");
    const lastBandRule = Math.max(...[...holoSection.matchAll(/\.skx-holo__band--\d+[^{}]*\{/g)].map((m) => m.index!));
    expect(reduced).toBeGreaterThan(lastBandRule);
  });

  it("띠 애니메이션 주기가 18~40초이고 서로 다르다", () => {
    const secs = [...holoSection.matchAll(/animation:\s*skx-holo-\w+\s+(\d+)s/g)].map((m) => Number(m[1]));
    expect(secs.length).toBeGreaterThanOrEqual(2);
    for (const s of secs) {
      expect(s).toBeGreaterThanOrEqual(18);
      expect(s).toBeLessThanOrEqual(40);
    }
    expect(new Set(secs).size).toBe(secs.length);
  });
});
