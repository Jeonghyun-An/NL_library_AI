// frontend/tests/unit/themeTokens.test.ts
// round08 — 화면 테마 토큰을 지킨다(다크 그린 기본 + 핑크 …). 테마마다 같은 검사를 돌린다.
// style_skovix.css 의 :root(다크 그린)·html[data-theme="이름"](그 밖의 테마)·.skx-reading 블록에서 --skx-* 선언을 읽어
//  ① 테마 블록과 밝은 읽는 면이 토큰을 빠짐없이 다시 선언하는지 ② 글자 대비(WCAG 상대 휘도)가 4.5:1 이상인지 ③ 색 리터럴이 테마 블록 밖에 늘지 않는지 검사한다.
import { describe, expect, it } from "vitest";
import {
  DEFAULT_THEME,
  THEMES,
  contrast,
  css,
  declarations,
  findBlock,
  rawCss,
  readingBaseDecls,
  readingTokens,
  rootDecls,
  solidOf,
  themeBlockSelectors,
  themeSelector,
  themeTokens,
  type ThemeName,
} from "./helpers/themeCss";

const otherThemes = THEMES.filter((t) => t !== DEFAULT_THEME);

/** 홀로그램 배경 토큰은 화면 전체에 하나뿐이라 밝은 읽는 면이 다시 선언하지 않는다 */
const isHoloToken = (name: string) => name.startsWith("--skx-holo-");
/** 테마 견본 색은 현재 테마와 상관없이 늘 그 테마의 색이라 테마 블록이 다시 선언하지 않는다 */
const isSwatchToken = (name: string) => name.startsWith("--skx-swatch-");

describe("테마 구조 — 토큰 묶음", () => {
  it("테마는 dark-green(기본)과 pink 를 포함하고 기본은 dark-green 이다", () => {
    expect(DEFAULT_THEME).toBe("dark-green");
    expect([...THEMES]).toEqual(expect.arrayContaining(["dark-green", "pink"]));
  });

  it("밝은 읽는 면이 :root 의 --skx-* (반경·홀로그램 제외)를 빠짐없이 다시 선언한다", () => {
    const missing = Object.keys(rootDecls).filter(
      (name) => !name.startsWith("--skx-radius-") && !isHoloToken(name) && !isSwatchToken(name) && !(name in readingBaseDecls),
    );
    expect(missing).toEqual([]);
  });

  it.each(otherThemes)("[%s] 테마 블록이 :root 의 --skx-* (반경 제외)를 빠짐없이 다시 선언한다", (theme) => {
    const body = findBlock(themeSelector(theme));
    expect(body, `${themeSelector(theme)} 블록이 있어야 한다`).not.toBeNull();
    const own = declarations(body!);
    const missing = Object.keys(rootDecls).filter(
      (name) => !name.startsWith("--skx-radius-") && !isSwatchToken(name) && !(name in own),
    );
    expect(missing).toEqual([]);
  });

  it.each(otherThemes)("[%s] 테마 블록이 :root 에 없는 토큰을 새로 만들지 않는다(이름 오타 방지)", (theme) => {
    const own = declarations(findBlock(themeSelector(theme))!);
    expect(Object.keys(own).filter((name) => !(name in rootDecls))).toEqual([]);
  });

  it.each(otherThemes)("[%s] 테마 블록의 color-scheme 은 선언돼 있다", (theme) => {
    expect(findBlock(themeSelector(theme))).toMatch(/color-scheme:\s*(light|dark)\s*;/);
  });
});

type Scope = "root" | "reading";

describe.each(THEMES)("테마 토큰 대비 4.5:1 이상 [%s]", (theme: ThemeName) => {
  const dark = theme === DEFAULT_THEME;
  const tokens = { root: themeTokens(theme), reading: readingTokens(theme) } as const;

  // [범위, 글자색 토큰, 바탕색 토큰] — 바탕이 반투명이면 불투명 면(--skx-white)을 깔고 합성해 잰다(다크의 유리 틴트는 그 아래 짙은 면 위에서 잰다)
  const pairs: [Scope, string, string][] = [
    ["root", "--skx-ink", "--skx-white"],
    ["root", "--skx-ink-strong", "--skx-white"],
    ["root", "--skx-ink-2", "--skx-white"],
    ["root", "--skx-gray-1", "--skx-white"],
    ["root", "--skx-gray-2", "--skx-white"],
    ["root", "--skx-teal-ink", "--skx-white"],
    ["root", "--skx-on-accent", "--skx-accent"],
    // 딥리서치가 포인트색 배경 위에 color: var(--skx-white) 로 얹는 글자
    ["root", "--skx-white", "--skx-primary"],
    // 포인트색 바탕이 아닌 밝은 면 위의 짙은 글(AI 말풍선·답변 안 출처 칩)
    ["root", "--skx-ink-on-light", "--skx-chat-ai-bg"],
    // 상태색(성공) — 초록 점·글자·일치율 링
    ["root", "--skx-success", "--skx-white"],
    // 상태색(위험) — 실패 배지 글자·지우기 확인 버튼(위험색 바탕 위 --skx-on-accent 글자)
    ["root", "--skx-danger", "--skx-white"],
    ["root", "--skx-on-accent", "--skx-danger"],
    // 사이드바·읽는 칸·묶음 카드 글 톤
    ["root", "--skx-side-ink", "--skx-white"],
    ["root", "--skx-side-gray-2", "--skx-white"],
    ["root", "--skx-read-ink-2", "--skx-white"],
    ["root", "--skx-research-gray-2", "--skx-white"],
    // 밝은 읽는 면(.skx-reading)
    ["reading", "--skx-ink", "--skx-white"],
    ["reading", "--skx-gray-1", "--skx-white"],
    ["reading", "--skx-primary", "--skx-white"],
    ["reading", "--skx-white", "--skx-primary"],
    ["reading", "--skx-accent-strong", "--skx-white"],
    ["reading", "--skx-success", "--skx-white"],
    ["reading", "--skx-success", "--skx-success-bg"],
    ["reading", "--skx-danger", "--skx-white"],
    ["reading", "--skx-danger", "--skx-danger-bg"],
    ["reading", "--skx-on-accent", "--skx-danger"],
    // 옅은 틴트(--skx-glass-teal) 위에 얹는 포인트색·보조 글자(키워드 칩·선택된 메뉴 항목·KCI 배지)
    ["reading", "--skx-primary", "--skx-glass-teal"],
    ["reading", "--skx-teal-ink", "--skx-glass-teal"],
    // 다크 전용: 짙은 면 위에서만 성립하는 쌍(핑크는 위 쌍이 같은 일을 한다)
    ...(dark ? ([["root", "--skx-ink-strong", "--skx-seg-thumb"]] as [Scope, string, string][]) : []),
    // 핑크 전용: 반투명 틴트 위의 보조 글자·상태 배경 위 상태 글자
    ...(!dark
      ? ([
          ["root", "--skx-teal-ink", "--skx-glass-teal"],
          ["root", "--skx-success", "--skx-success-bg"],
          ["root", "--skx-danger", "--skx-danger-bg"],
          ["root", "--skx-ink", "--skx-glass"],
          ["root", "--skx-gray-1", "--skx-glass"],
        ] as [Scope, string, string][])
      : []),
  ];

  it.each(pairs)("%s: %s 글자가 %s 바탕 위에서 읽힌다", (scope, fg, bg) => {
    const t = tokens[scope];
    const front = solidOf(t[fg]!, t);
    const back = solidOf(t[bg]!, t);
    expect(contrast(front, back)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("하드코딩 색 회귀 가드", () => {
  // 테마 정의 블록(:root·.skx-reading·html[data-theme=…]·그 읽는 면)과 .skx-holo 구간 밖에 색 리터럴(#hex·rgb()·rgba()·hsl()·색 이름·currentColor)이 다시 늘지 않게 센다.
  // 새 색은 --skx-* 토큰으로 쓰고(테마마다 값은 테마 블록 안에서), 정말 고정이어야 하면 이 숫자를 올리며 이유를 남긴다.
  // 의도적 잔존: 그림자·모달 막(scrim)·광택/글로우 하이라이트·/recommend 파스텔 카드·색조 틴트.
  // 상세·옛 추천 화면만 쓰던 죽은 클래스를 지워 56 → 50 으로 줄었다(round08) — 줄어든 값으로 고정한다. 핑크 테마를 더해도 늘지 않는다(테마 블록 안만 허용).
  const MAX_LITERALS_OUTSIDE_TOKEN_BLOCKS = 50;

  const outside = (() => {
    let text = rawCss
      // 홀로그램 구간은 themeHolo.test.ts 가 따로 지킨다
      .replace(/\/\* \[S\] 움직이는 홀로그램 배경 \*\/[\s\S]*?\/\* \[E\] 움직이는 홀로그램 배경 \*\//, "")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/url\([^)]*\)/g, "");
    for (const selector of themeBlockSelectors()) {
      const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      text = text.replace(new RegExp(`(?:^|\\n)${esc}\\s*\\{[^}]*\\}`), "");
    }
    return text;
  })();

  it("토큰 블록 밖 색 리터럴 수가 기준 이하다", () => {
    const literals =
      outside.match(
        /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|(?<![\w-])(?:white|black|red|green|blue|gray|grey|currentcolor)(?![\w-])/gi,
      ) ?? [];
    expect(literals.length).toBeLessThanOrEqual(MAX_LITERALS_OUTSIDE_TOKEN_BLOCKS);
  });

  it("테마 블록 선택자가 실제로 파일에 있다(가드가 빈 값을 지우고 통과하지 않게)", () => {
    for (const selector of themeBlockSelectors()) {
      expect(findBlock(selector), selector).not.toBeNull();
    }
  });
});

describe("아이콘 필터 규칙 특이도", () => {
  // 색 파일(<img src="/img/ico-*.svg">)에 거는 일반 규칙은 :where() 로 감싸 특이도 0 이어야 한다.
  // 그냥 img[src...] 로 쓰면 (0,1,1) 이라 단일 클래스 규칙(.skx-btn-talk__ico 등)의 filter 를 이겨
  // 산호 버튼 위 아이콘이 일반 색(#ccc)으로 덮인다.
  /** 괄호 밖의 쉼표로만 선택자 목록을 나눈다(:where(a, b) 안의 쉼표는 그대로) */
  function splitSelectors(list: string): string[] {
    const out: string[] = [];
    let depth = 0;
    let cur = "";
    for (const ch of list) {
      if (ch === "(" || ch === "[") depth++;
      if (ch === ")" || ch === "]") depth--;
      if (ch === "," && depth === 0) {
        out.push(cur.trim());
        cur = "";
      } else {
        cur += ch;
      }
    }
    out.push(cur.trim());
    return out.filter(Boolean);
  }
  const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({
    selectors: splitSelectors(m[1] ?? ""),
    body: m[2] ?? "",
  }));

  it("filter 를 거는 img[...] 규칙은 :where() 로 감싼다", () => {
    const bare = rules
      .filter((r) => /(?:^|[;\s])filter\s*:/.test(r.body))
      .flatMap((r) => r.selectors)
      .filter((s) => /^img\[/.test(s));
    expect(bare).toEqual([]);
  });

  it("일반 아이콘 규칙(:where)이 있다", () => {
    expect(css).toMatch(/:where\(img\[src\*="\/img\/ico-"\]/);
  });
});
