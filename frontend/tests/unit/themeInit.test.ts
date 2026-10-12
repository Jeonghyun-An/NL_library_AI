// frontend/tests/unit/themeInit.test.ts
// 화면 테마 고르기 — 이름 검사·저장/복원·기본값·잘못된 값 무시(순수 함수)와 <head> 인라인 스크립트(첫 그림 전에 html[data-theme] 을 붙인다)를 지킨다.
// 스크립트는 문자열이라 가짜 document·localStorage 를 넣어 실제로 실행해 본다.
import { describe, expect, it } from "vitest";
import {
  DEFAULT_THEME,
  THEMES,
  THEME_LABELS,
  THEME_STORAGE_KEY,
  isTheme,
  normalizeTheme,
  readStoredTheme,
  stepTheme,
  storeTheme,
  themeInitScript,
} from "~/utils/theme";

/** 메모리 저장소 — 가끔 던지게도 만든다 */
function fakeStorage(initial: Record<string, string> = {}, opts: { getThrows?: boolean; setThrows?: boolean } = {}) {
  const data = { ...initial };
  const calls: string[] = [];
  return {
    data,
    calls,
    getItem(key: string): string | null {
      if (opts.getThrows) throw new Error("denied");
      return key in data ? data[key]! : null;
    },
    setItem(key: string, value: string): void {
      calls.push(`${key}=${value}`);
      if (opts.setThrows) throw new Error("denied");
      data[key] = value;
    },
  };
}

describe("테마 이름", () => {
  it("기본은 dark-green(다크)이고 목록에 있다", () => {
    expect(DEFAULT_THEME).toBe("dark-green");
    expect(THEMES).toContain(DEFAULT_THEME);
  });

  it("설정 토글에는 [다크] [라이트] 두 칸이다(라이트 = 핑크)", () => {
    expect(THEME_LABELS["dark-green"]).toBe("다크");
    expect(THEME_LABELS.pink).toBe("라이트");
    expect(THEMES.length).toBe(2);
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

describe("테마 저장·복원(순수 함수)", () => {
  it("저장소가 없으면(서버 렌더) 기본 테마", () => {
    expect(readStoredTheme(null)).toBe(DEFAULT_THEME);
    expect(readStoredTheme(undefined)).toBe(DEFAULT_THEME);
  });

  it("아무것도 저장되지 않았으면 기본 테마", () => {
    expect(readStoredTheme(fakeStorage())).toBe(DEFAULT_THEME);
  });

  it("저장된 테마를 복원한다", () => {
    expect(readStoredTheme(fakeStorage({ [THEME_STORAGE_KEY]: "pink" }))).toBe("pink");
    expect(readStoredTheme(fakeStorage({ [THEME_STORAGE_KEY]: "dark-green" }))).toBe("dark-green");
  });

  it("잘못된 저장 값은 무시하고 기본 테마로 간다", () => {
    for (const bad of ["neon", "", "PINK", "<script>", "pink "]) {
      expect(readStoredTheme(fakeStorage({ [THEME_STORAGE_KEY]: bad })), bad).toBe(DEFAULT_THEME);
    }
  });

  it("저장소를 읽다 막혀도(private 창 등) 던지지 않고 기본 테마", () => {
    expect(readStoredTheme(fakeStorage({}, { getThrows: true }))).toBe(DEFAULT_THEME);
  });

  it("저장하면 키 skx_theme 에 이름이 들어가고 복원된다(저장 → 복원 왕복)", () => {
    const storage = fakeStorage();
    expect(storeTheme(storage, "pink")).toBe(true);
    expect(storage.data).toEqual({ skx_theme: "pink" });
    expect(readStoredTheme(storage)).toBe("pink");
    expect(storeTheme(storage, "dark-green")).toBe(true);
    expect(readStoredTheme(storage)).toBe("dark-green");
  });

  it("잘못된 이름은 저장하지 않는다", () => {
    const storage = fakeStorage();
    expect(storeTheme(storage, "neon")).toBe(false);
    expect(storeTheme(storage, null)).toBe(false);
    expect(storage.calls).toEqual([]);
  });

  it("저장소가 없거나 쓰기가 막혀도 던지지 않고 false(이번 방문에서만 바뀐다)", () => {
    expect(storeTheme(null, "pink")).toBe(false);
    expect(storeTheme(fakeStorage({}, { setThrows: true }), "pink")).toBe(false);
  });
});

describe("토글 방향키 이동(stepTheme)", () => {
  it("다음·이전으로 옮기고 끝에서 처음으로 이어진다", () => {
    expect(stepTheme("dark-green", 1)).toBe("pink");
    expect(stepTheme("pink", 1)).toBe("dark-green");
    expect(stepTheme("dark-green", -1)).toBe("pink");
    expect(stepTheme("pink", -1)).toBe("dark-green");
  });

  it("모르는 현재 값은 기본 테마에서 센다", () => {
    expect(stepTheme("neon", 1)).toBe("pink");
  });
});

type Env = { stored?: string | null; getThrows?: boolean; noDocument?: boolean };

function run(env: Env = {}): { attr: string | null; threw: boolean } {
  let attr: string | null = null;
  const document = env.noDocument
    ? undefined
    : {
        documentElement: {
          setAttribute: (name: string, value: string) => {
            if (name === "data-theme") attr = value;
          },
        },
      };
  const localStorage = {
    getItem: (key: string) => {
      if (env.getThrows) throw new Error("denied");
      return key === THEME_STORAGE_KEY ? (env.stored ?? null) : null;
    },
  };
  let threw = false;
  try {
    new Function("document", "localStorage", themeInitScript())(document, localStorage);
  } catch {
    threw = true;
  }
  return { attr, threw };
}

describe("테마 초기 적용 스크립트(<head> 인라인)", () => {
  it("아무것도 없으면 기본 테마를 붙인다", () => {
    expect(run()).toEqual({ attr: DEFAULT_THEME, threw: false });
  });

  it("저장된 테마를 붙인다", () => {
    expect(run({ stored: "pink" }).attr).toBe("pink");
    expect(run({ stored: "dark-green" }).attr).toBe("dark-green");
  });

  it("저장된 값이 이상하면 기본 테마로 간다", () => {
    expect(run({ stored: "<script>" }).attr).toBe(DEFAULT_THEME);
  });

  it("주소의 ?theme= 는 보지 않는다(설정 토글로만 바꾼다)", () => {
    expect(themeInitScript()).not.toMatch(/location|URLSearchParams|search/);
  });

  it("저장소를 읽다 막혀도(private 창 등) 던지지 않고 기본으로 간다", () => {
    expect(run({ getThrows: true })).toEqual({ attr: DEFAULT_THEME, threw: false });
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
