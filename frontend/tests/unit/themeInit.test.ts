// frontend/tests/unit/themeInit.test.ts
// 화면 테마 고르기 — 이름 검사와 <head> 인라인 스크립트(첫 그림 전에 html[data-theme] 을 붙인다)를 지킨다.
// 스크립트는 문자열이라 가짜 document·location·localStorage 를 넣어 실제로 실행해 본다.
import { describe, expect, it } from "vitest";
import {
  DEFAULT_THEME,
  THEMES,
  THEME_LABELS,
  THEME_QUERY_KEY,
  THEME_STORAGE_KEY,
  isTheme,
  normalizeTheme,
  themeInitScript,
} from "~/utils/theme";

type Env = {
  search?: string;
  stored?: string | null;
  getThrows?: boolean;
  setThrows?: boolean;
  noDocument?: boolean;
};

function run(env: Env = {}): { attr: string | null; saved: string | null; threw: boolean } {
  let attr: string | null = null;
  let saved: string | null = env.stored ?? null;
  const document = env.noDocument
    ? undefined
    : {
        documentElement: {
          setAttribute: (name: string, value: string) => {
            if (name === "data-theme") attr = value;
          },
        },
      };
  const location = { search: env.search ?? "" };
  const localStorage = {
    getItem: (key: string) => {
      if (env.getThrows) throw new Error("denied");
      return key === THEME_STORAGE_KEY ? saved : null;
    },
    setItem: (key: string, value: string) => {
      if (env.setThrows) throw new Error("denied");
      if (key === THEME_STORAGE_KEY) saved = value;
    },
  };
  let threw = false;
  try {
    new Function("document", "location", "localStorage", "URLSearchParams", themeInitScript())(
      document,
      location,
      localStorage,
      URLSearchParams,
    );
  } catch {
    threw = true;
  }
  return { attr, saved, threw };
}

describe("테마 이름", () => {
  it("기본은 dark-green 이고 목록에 있다", () => {
    expect(DEFAULT_THEME).toBe("dark-green");
    expect(THEMES).toContain(DEFAULT_THEME);
  });

  it("모든 테마에 화면 이름이 있다", () => {
    for (const theme of THEMES) expect(THEME_LABELS[theme].length).toBeGreaterThan(0);
  });

  it.each([
    ["dark-green", true],
    ["pink", true],
    ["blackpink", false],
    ["", false],
    [null, false],
    [undefined, false],
    [1, false],
  ])("isTheme(%j) = %s", (value, expected) => {
    expect(isTheme(value)).toBe(expected);
  });

  it("모르는 값은 기본 테마로 바꾼다", () => {
    expect(normalizeTheme("pink")).toBe("pink");
    expect(normalizeTheme("nope")).toBe(DEFAULT_THEME);
    expect(normalizeTheme(null)).toBe(DEFAULT_THEME);
  });
});

describe("테마 초기 적용 스크립트(<head> 인라인)", () => {
  it("아무것도 없으면 기본 테마를 붙인다", () => {
    expect(run()).toEqual({ attr: DEFAULT_THEME, saved: null, threw: false });
  });

  it("저장된 테마를 붙인다", () => {
    expect(run({ stored: "pink" }).attr).toBe("pink");
  });

  it("주소의 ?theme=pink 를 붙이고 기억한다", () => {
    const r = run({ search: `?${THEME_QUERY_KEY}=pink` });
    expect(r.attr).toBe("pink");
    expect(r.saved).toBe("pink");
  });

  it("주소의 값이 저장된 값보다 먼저다", () => {
    expect(run({ search: "?theme=dark-green", stored: "pink" })).toMatchObject({ attr: "dark-green", saved: "dark-green" });
  });

  it("다른 쿼리와 섞여도 읽는다", () => {
    expect(run({ search: "?q=%EA%B0%95&theme=pink&h=1" }).attr).toBe("pink");
  });

  it("모르는 ?theme= 값은 무시하고 저장된 값을 쓴다", () => {
    expect(run({ search: "?theme=neon", stored: "pink" })).toMatchObject({ attr: "pink", saved: "pink" });
  });

  it("저장된 값이 이상하면 기본 테마로 간다", () => {
    expect(run({ stored: "<script>" }).attr).toBe(DEFAULT_THEME);
  });

  it("저장소를 읽다 막혀도(private 창 등) 던지지 않고 기본으로 간다", () => {
    expect(run({ getThrows: true })).toMatchObject({ attr: DEFAULT_THEME, threw: false });
  });

  it("저장소에 쓰다 막혀도 이번 방문에는 주소의 테마가 붙는다", () => {
    expect(run({ search: "?theme=pink", setThrows: true })).toMatchObject({ attr: "pink", threw: false });
  });

  it("document 가 없어도 던지지 않는다", () => {
    expect(run({ noDocument: true }).threw).toBe(false);
  });

  it("스크립트 문자열에 </script 가 없고 한 줄이다(인라인 삽입 안전)", () => {
    const script = themeInitScript();
    expect(script).not.toMatch(/<\/script/i);
    expect(script).not.toContain("\n");
  });
});
