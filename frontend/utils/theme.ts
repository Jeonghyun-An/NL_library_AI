// frontend/utils/theme.ts
// 화면 테마 — 루트(html)의 data-theme 속성 하나로 --skx-* 토큰 묶음을 갈아 끼운다(style_skovix.css).
// 기본(dark-green)은 :root 의 토큰 그대로이고, 다른 테마는 html[data-theme="이름"] 블록이 같은 토큰을 다시 선언한다.
// 화면에서는 사이드바 하단 설정(톱니)의 [다크] [라이트] 토글로 고른다(components/SettingsMenu.vue). 라이트 = pink(Figma main_시안D).
// 새 테마를 더할 때: ① 아래 THEMES·THEME_LABELS 에 이름 ② style_skovix.css 에 html[data-theme="이름"] 토큰 블록(+ .skx-reading 짝) ③ 테마 테스트(themeTokens·themeHolo·themeFrost)가 자동으로 같은 검사를 돈다.

export const THEMES = ["dark-green", "pink"] as const;
export type ThemeName = (typeof THEMES)[number];

export const DEFAULT_THEME: ThemeName = "dark-green";
/** 고른 테마를 기억하는 localStorage 키 */
export const THEME_STORAGE_KEY = "skx_theme";

/** 설정 토글에 보이는 이름 — 다크 = 다크 그린(기본), 라이트 = 핑크 */
export const THEME_LABELS: Record<ThemeName, string> = {
  "dark-green": "다크",
  pink: "라이트",
};

export function isTheme(value: unknown): value is ThemeName {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

/** 모르는 값은 기본 테마로 */
export function normalizeTheme(value: unknown): ThemeName {
  return isTheme(value) ? value : DEFAULT_THEME;
}

/** 저장된 테마 복원 — 저장소가 없거나(서버 렌더) 막혔거나(private 창 등) 값이 이상하면 기본 테마. 던지지 않는다 */
export function readStoredTheme(storage: Pick<Storage, "getItem"> | null | undefined): ThemeName {
  if (!storage) return DEFAULT_THEME;
  try {
    return normalizeTheme(storage.getItem(THEME_STORAGE_KEY));
  } catch {
    return DEFAULT_THEME;
  }
}

/** 고른 테마 저장 — 잘못된 이름은 저장하지 않고, 저장소가 막혀 있으면 false(이번 방문에서만 바뀐다) */
export function storeTheme(storage: Pick<Storage, "setItem"> | null | undefined, theme: unknown): boolean {
  if (!storage || !isTheme(theme)) return false;
  try {
    storage.setItem(THEME_STORAGE_KEY, theme);
    return true;
  } catch {
    return false;
  }
}

/** 방향키로 옮길 다음 테마(토글의 ←→) — 끝에서 처음으로 이어진다. 모르는 현재 값은 기본 테마에서 센다 */
export function stepTheme(current: unknown, delta: 1 | -1): ThemeName {
  const i = THEMES.indexOf(normalizeTheme(current));
  return THEMES[(i + delta + THEMES.length) % THEMES.length]!;
}

/**
 * <head> 맨 앞에 넣는 작은 인라인 스크립트 — 화면이 그려지기 전에 html 에 data-theme 을 붙여 첫 화면이 깜빡이지 않게 한다.
 * localStorage 에 저장된 테마(맞는 값일 때) → 기본 순이다. 저장소가 막혀 있어도(private 창 등) 던지지 않고 기본으로 간다.
 * 서버 렌더 결과에는 속성이 없고(기본 :root 토큰), 클라이언트가 이 스크립트로 바로 바꾼다.
 */
export function themeInitScript(): string {
  const names = JSON.stringify(THEMES);
  return (
    `(function(){try{var d=document.documentElement,n=${names},t=null;` +
    `try{t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)})}catch(e){}` +
    `d.setAttribute("data-theme",t&&n.indexOf(t)>=0?t:${JSON.stringify(DEFAULT_THEME)})}catch(e){}})();`
  );
}
