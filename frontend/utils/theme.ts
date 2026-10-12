// frontend/utils/theme.ts
// 화면 테마 — 루트(html)의 data-theme 속성 하나로 --skx-* 토큰 묶음을 갈아 끼운다(style_skovix.css).
// 기본(dark-green)은 :root 의 토큰 그대로이고, 다른 테마는 html[data-theme="이름"] 블록이 같은 토큰을 다시 선언한다.
// 새 테마를 더할 때: ① 아래 THEMES 에 이름 ② style_skovix.css 에 html[data-theme="이름"] 토큰 블록(+ .skx-reading 짝) ③ themeContrast.test.ts 가 자동으로 대비를 검사한다.

export const THEMES = ["dark-green", "pink"] as const;
export type ThemeName = (typeof THEMES)[number];

export const DEFAULT_THEME: ThemeName = "dark-green";
/** 고른 테마를 기억하는 localStorage 키 */
export const THEME_STORAGE_KEY = "skx_theme";
/** 주소의 ?theme=pink 로도 고른다(고르면 기억한다) */
export const THEME_QUERY_KEY = "theme";

/** 사이드바 스위처에 보이는 이름 */
export const THEME_LABELS: Record<ThemeName, string> = {
  "dark-green": "다크 그린",
  pink: "핑크",
};

export function isTheme(value: unknown): value is ThemeName {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

/** 모르는 값은 기본 테마로 */
export function normalizeTheme(value: unknown): ThemeName {
  return isTheme(value) ? value : DEFAULT_THEME;
}

/**
 * <head> 맨 앞에 넣는 작은 인라인 스크립트 — 화면이 그려지기 전에 html 에 data-theme 을 붙여 첫 화면이 깜빡이지 않게 한다.
 * 순서: 주소의 ?theme= (맞는 값이면 기억까지) → localStorage → 기본. 저장소가 막혀 있어도(private 창 등) 던지지 않고 기본으로 간다.
 * 서버 렌더 결과에는 속성이 없고(기본 :root 토큰), 클라이언트가 이 스크립트로 바로 바꾼다.
 */
export function themeInitScript(): string {
  const names = JSON.stringify(THEMES);
  return (
    `(function(){try{var d=document.documentElement,n=${names},t=null;` +
    `var q=new URLSearchParams(location.search).get(${JSON.stringify(THEME_QUERY_KEY)});` +
    `if(q&&n.indexOf(q)>=0){t=q;try{localStorage.setItem(${JSON.stringify(THEME_STORAGE_KEY)},q)}catch(e){}}` +
    `else{try{t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)})}catch(e){}}` +
    `d.setAttribute("data-theme",t&&n.indexOf(t)>=0?t:${JSON.stringify(DEFAULT_THEME)})}catch(e){}})();`
  );
}
