// frontend/utils/featureFlags.ts
// 동작 없는 목업은 대회 전 숨긴다 — 코드는 남긴다(켤 때 true 한 줄).
export const SHOW_MOCKS = false;

// 사이드바 맨 아래의 화면 테마 견본(components/ThemeSwitcher.vue) — 켜면 다크 그린·핑크를 눌러 바꾼다. 꺼 둬도 주소의 ?theme=pink 로 고를 수 있다.
export const SHOW_THEME_SWITCH = false;
