// frontend/tests/unit/searchInput.test.ts
// 검색 입력창 다듬기(2026-10-13 사용자 결정) — 보내기 버튼 상태 판정(순수 함수)·위 화살표 아이콘·테두리(평소 옅은 선·초점 포인트색)·도는 빛·빈 상태 대비를 지킨다.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { hasQuery } from "~/utils/searchInput";
import {
  DEFAULT_THEME,
  THEMES,
  composites,
  contrast,
  css,
  holoModel,
  over,
  parseColor,
  peakStop,
  rgbaStops,
  themeTokens,
  type Rgb,
  type ThemeName,
} from "./helpers/themeCss";

const frontend = (rel: string) => resolve(__dirname, "../..", rel);
const read = (rel: string) => readFileSync(frontend(rel), "utf-8");

describe("hasQuery — 보내기 버튼이 채워질지(공백만 있으면 빈 것)", () => {
  it.each([
    ["강화학습", true],
    ["  강화학습  ", true],
    ["a", true],
    ["", false],
    ["   ", false],
    ["\n\t  ", false],
    ["　", false],
    [null, false],
    [undefined, false],
    [0, false],
    [{}, false],
  ])("hasQuery(%j) = %s", (value, expected) => {
    expect(hasQuery(value)).toBe(expected);
  });
});

describe("보내기 버튼 — 위 화살표 아이콘", () => {
  it("새 아이콘 파일이 있고 선 굵기·크기가 기존 보내기 아이콘과 같다(20×20, 흰 선 2)", () => {
    const up = frontend("public/img/ico-send-up.svg");
    expect(existsSync(up)).toBe(true);
    const svg = readFileSync(up, "utf-8");
    expect(svg).toContain('viewBox="0 0 20 20"');
    expect(svg).toContain('stroke="white"');
    expect(svg.match(/stroke-width="2"/g)?.length).toBeGreaterThanOrEqual(2);
    const old = read("public/img/ico-send.svg");
    expect(old).toContain('viewBox="0 0 20 20"');
    expect(old).toContain('stroke-width="2"');
  });

  it("랜딩·/papers 랜딩·결과·상세 검색바의 보내기 버튼은 모두 위 화살표를 쓴다", () => {
    const counts: [string, number][] = [
      ["pages/index.vue", 3],
      ["pages/papers/index.vue", 2],
      ["components/detail/SearchBar.vue", 1],
    ];
    for (const [file, n] of counts) {
      const src = read(file);
      expect(src.match(/src="\/img\/ico-send-up\.svg"/g)?.length, file).toBe(n);
      expect(src, file).not.toContain("ico-send.svg");
    }
  });

  it("DeepRead 채팅의 보내기는 그대로 종이비행기다", () => {
    expect(read("components/BookChat.vue")).toContain("/img/ico-send.svg");
  });

  it("모든 보내기 버튼이 이름(aria-label)을 갖고 aria-disabled 로 상태를 알리며 disabled 로 막지 않는다(로딩 중 기존 disabled 는 그대로)", () => {
    for (const file of ["pages/index.vue", "pages/papers/index.vue", "components/detail/SearchBar.vue"]) {
      const buttons = [...read(file).matchAll(/<button\b[^>]*class="skx-send"[^>]*>/g)].map((m) => m[0]);
      expect(buttons.length, file).toBeGreaterThan(0);
      for (const tag of buttons) {
        expect(tag, `${file}: ${tag}`).toMatch(/aria-label=/);
        expect(tag, `${file}: ${tag}`).toMatch(/:aria-disabled="!hasQuery\(\w+(?:\.value)?\)"/);
        expect(tag.replace(/:disabled="loading"/, ""), `${file}: ${tag}`).not.toMatch(/\bdisabled\b(?!=)/);
      }
    }
  });
});

describe("입력창 테두리 — 평소 옅은 선, 초점일 때만 포인트색", () => {
  it("규칙: 랜딩 입력 상자·결과/상세 검색바 모두 평소는 --skx-input-ring, 초점(:focus-within)은 --skx-input-ring-focus", () => {
    expect(css).toMatch(/\.skx-search__box::before,\s*\.skx-rsearch::before\s*\{\s*background:\s*var\(--skx-input-ring\);/);
    expect(css).toMatch(
      /\.skx-search__box:focus-within::before,\s*\.skx-rsearch:focus-within::before\s*\{\s*background:\s*var\(--skx-input-ring-focus\);/,
    );
  });

  it("다크: 평소 테두리는 흰색 계열의 옅은 선이고(흰 4할 이하), 초점은 포인트색(산호)이다", () => {
    const t = themeTokens(DEFAULT_THEME);
    const ring = parseColor(t["--skx-input-ring"]!);
    expect(ring.rgb).toEqual([255, 255, 255]);
    expect(ring.a).toBeGreaterThan(0.1);
    expect(ring.a).toBeLessThanOrEqual(0.4);
    expect(t["--skx-input-ring-focus"]).toBe(t["--skx-accent"]);
    expect(t["--skx-input-ring"]).not.toBe(t["--skx-accent"]);
  });

  it("핑크: 평소는 그 테마의 중립 선(--skx-line), 초점은 검정 포인트다", () => {
    const t = themeTokens("pink");
    expect(t["--skx-input-ring"]).toBe(t["--skx-line"]);
    expect(t["--skx-input-ring-focus"]).toBe(t["--skx-accent"]);
    expect(t["--skx-input-ring-focus"]).toBe("#1a1115");
  });

  it.each(THEMES)("[%s] 평소 선과 초점 선이 다르다(초점이 눈에 띈다)", (theme) => {
    const t = themeTokens(theme);
    expect(t["--skx-input-ring"]).not.toBe(t["--skx-input-ring-focus"]);
  });
});

describe("랜딩 입력창 — 테두리를 따라 도는 빛", () => {
  it.each(THEMES)("[%s] 빛 토큰이 방사 그라데이션이고 가장자리는 투명하다", (theme) => {
    const glow = themeTokens(theme)["--skx-input-glow"]!;
    expect(glow).toMatch(/^radial-gradient\(circle closest-side,/);
    const stops = rgbaStops(glow);
    expect(stops.length).toBeGreaterThanOrEqual(3);
    expect(stops[stops.length - 1]!.a).toBe(0);
    expect(Math.max(...stops.map((s) => s.a))).toBeLessThanOrEqual(0.9);
  });

  it("다크 빛은 흰색 하나다(색을 늘리지 않는다)", () => {
    for (const s of rgbaStops(themeTokens(DEFAULT_THEME)["--skx-input-glow"]!)) expect(s.rgb).toEqual([255, 255, 255]);
  });

  it("핑크 빛은 분홍 계열이다(빨강 채널이 가장 크다)", () => {
    for (const s of rgbaStops(themeTokens("pink")["--skx-input-glow"]!)) {
      expect(s.rgb[0]).toBeGreaterThanOrEqual(s.rgb[1]);
      expect(s.rgb[0]).toBeGreaterThanOrEqual(s.rgb[2]);
    }
  });

  /** 빛 규칙 전체 — `.skx-search__glow { display: none }` 부터 그 뒤 @supports 블록의 짝 맞는 닫는 괄호까지 */
  const glowRules = (() => {
    const start = css.indexOf(".skx-search__glow {");
    const open = start < 0 ? -1 : css.indexOf("@supports (offset-path: border-box)", start);
    if (open < 0) return "";
    let depth = 0;
    for (let i = css.indexOf("{", open); i < css.length; i++) {
      if (css[i] === "{") depth++;
      else if (css[i] === "}" && --depth === 0) return css.slice(start, i + 1);
    }
    return "";
  })();

  it("빛 틀은 기본이 숨김이고, offset-path 를 아는 브라우저 + 움직임 줄이기가 아닐 때만 그린다", () => {
    expect(glowRules).not.toBe("");
    expect(glowRules).toMatch(/@supports \(offset-path: border-box\)\s*\{\s*@media \(prefers-reduced-motion: no-preference\)/);
  });

  it("빛은 테두리 띠(2px)만 남기는 마스크 안에서만 보이고 안쪽 글·버튼을 덮지 않는다", () => {
    expect(glowRules).toMatch(/padding:\s*2px;/);
    expect(glowRules).toMatch(/mask-composite:\s*exclude;/);
    expect(glowRules).toMatch(/pointer-events:\s*none;/);
  });

  it("빛 덩어리는 offset-path: border-box 로 틀의 테두리를 따라 5초에 한 바퀴 돈다", () => {
    expect(glowRules).toMatch(/offset-path:\s*border-box;/);
    expect(glowRules).toMatch(/animation:\s*skx-glow-travel 5s linear infinite;/);
    expect(glowRules).toMatch(/@keyframes skx-glow-travel\s*\{\s*to\s*\{\s*offset-distance:\s*100%;/);
    expect(glowRules).toMatch(/background:\s*var\(--skx-input-glow\);/);
  });

  it("빛 틀은 랜딩 입력 상자 안에만 있다(자료·논문 두 칸 + /papers 랜딩), 결과·상세 검색바에는 없다", () => {
    expect(read("pages/index.vue").match(/class="skx-search__glow"/g)?.length).toBe(2);
    expect(read("pages/papers/index.vue").match(/class="skx-search__glow"/g)?.length).toBe(1);
    expect(read("components/detail/SearchBar.vue")).not.toContain("skx-search__glow");
    // 결과 검색바(.skx-rsearch) 안에는 빛 틀이 없다
    for (const file of ["pages/index.vue", "pages/papers/index.vue"]) {
      for (const m of read(file).matchAll(/<div class="skx-rsearch">([\s\S]*?)<\/div>\s*\n/g)) {
        expect(m[1], file).not.toContain("skx-search__glow");
      }
    }
    expect(css).not.toMatch(/\.skx-rsearch[^{]*glow/);
  });
});

describe("보내기 버튼 — 빈 입력은 옅은 중립색, 글자가 있으면 포인트색", () => {
  it("빈 상태는 aria-disabled=true 일 때의 규칙이고 채움·테두리·화살표를 토큰으로 정한다", () => {
    expect(css).toMatch(
      /\.skx-send\[aria-disabled="true"\]\s*\{\s*background:\s*var\(--skx-send-empty-bg\);\s*box-shadow:\s*inset 0 0 0 1px var\(--skx-send-empty-line\);/,
    );
    expect(css).toMatch(/\.skx-send\[aria-disabled="true"\] img\s*\{\s*filter:\s*var\(--skx-send-empty-ico-filter\);/);
    // 글자가 있을 때의 채움은 포인트색(규칙 그대로)
    expect(css).toMatch(/\.skx-send\s*\{[^}]*background:\s*var\(--skx-primary\);/);
  });

  it("빈 상태에서 올려도 밝아지지 않는다(눌러도 되는 것처럼 보이지 않게)", () => {
    expect(css).toMatch(/\.skx-send\[aria-disabled="true"\]:hover\s*\{\s*filter:\s*none;/);
  });

  it("상태 전환은 150ms 색 전환이고, 움직임 줄이기 설정이면 즉시다", () => {
    const rule = css.match(/\n\.skx-send\s*\{[^}]*\}/)?.[0] ?? "";
    expect(rule).toMatch(/transition:[^;]*background-color 0\.15s/);
    expect(rule).toMatch(/box-shadow 0\.15s/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.skx-send\s*\{\s*transition:\s*none;/);
  });

  /** filter 의 brightness(0) invert(v) 에서 화살표의 회색(0~255) */
  const arrowGray = (filter: string): number => {
    const m = filter.match(/^brightness\(0\) invert\(([\d.]+)\)$/);
    if (!m) throw new Error(`화살표 필터를 읽지 못함: ${filter}`);
    return Math.round(255 * Number(m[1]));
  };

  // 입력창 면(밑칠 → 막 → 반사광)을 띠가 겹친 모든 합성 위에 얹은 자리에 버튼이 놓인다
  const INPUT_FACE = ["--skx-frost-tint", "--skx-frost-milk", "--skx-frost-reflect"];
  const faces = (theme: ThemeName): Rgb[] => {
    const t = themeTokens(theme);
    return composites(holoModel(theme)).map((c) =>
      INPUT_FACE.reduce<Rgb>((acc, token) => {
        const l = peakStop(t[token]!);
        return over(acc, l.rgb, l.a);
      }, c),
    );
  };

  describe.each(THEMES)("그래픽 요소 대비 3:1 이상 [%s]", (theme: ThemeName) => {
    const t = themeTokens(theme);
    const bg = parseColor(t["--skx-send-empty-bg"]!);
    const line = parseColor(t["--skx-send-empty-line"]!);
    const gray = arrowGray(t["--skx-send-empty-ico-filter"]!);

    it("빈 상태: 버튼 테두리가 입력창 면(최악의 합성) 위에서 3:1 이상 구분된다", () => {
      const worst = Math.min(
        ...faces(theme).map((f) => {
          const fill = over(f, bg.rgb, bg.a);
          const edge = over(fill, line.rgb, line.a);
          return contrast(edge, f);
        }),
      );
      expect(worst).toBeGreaterThanOrEqual(3);
    });

    it("빈 상태: 옅은 화살표가 중립 채움 위에서 3:1 이상 읽힌다", () => {
      const worst = Math.min(
        ...faces(theme).map((f) => contrast([gray, gray, gray], over(f, bg.rgb, bg.a))),
      );
      expect(worst).toBeGreaterThanOrEqual(3);
    });

    it("글자가 있을 때: 포인트색 채움이 입력창 면 위에서 3:1 이상 구분된다", () => {
      const primary = parseColor(t["--skx-primary"]!).rgb;
      expect(Math.min(...faces(theme).map((f) => contrast(primary, f)))).toBeGreaterThanOrEqual(3);
    });

    it("빈 상태 채움이 포인트색과 확실히 다르다(상태가 눈에 보인다)", () => {
      const primary = parseColor(t["--skx-primary"]!).rgb;
      const empty = over(faces(theme)[0]!, bg.rgb, bg.a);
      const dist = Math.hypot(...primary.map((v, i) => v - empty[i]!));
      expect(dist).toBeGreaterThan(60);
    });
  });
});
