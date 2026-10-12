// frontend/composables/useTheme.ts
// 화면 테마 고르기 — html[data-theme] 를 바꾸고 고른 값을 localStorage 에 기억한다(utils/theme.ts).
// 첫 화면의 속성은 <head> 인라인 스크립트(themeInitScript)가 이미 붙였다. 여기서는 그 값을 읽어 상태로 삼고, 바꿀 때만 속성·저장소를 만진다.
import { DEFAULT_THEME, THEME_STORAGE_KEY, isTheme, normalizeTheme, type ThemeName } from "~/utils/theme";
import { safeLocalStorage } from "~/utils/browserId";

export function useTheme() {
  // 서버 렌더에서는 기본값 — 클라이언트가 마운트되며 실제 속성에서 읽어 맞춘다(하이드레이션이 어긋나지 않게)
  const theme = useState<ThemeName>("skx-theme", () => DEFAULT_THEME);

  function applied(): ThemeName {
    if (typeof document === "undefined") return DEFAULT_THEME;
    return normalizeTheme(document.documentElement.getAttribute("data-theme"));
  }

  onMounted(() => {
    theme.value = applied();
  });

  function setTheme(next: ThemeName): void {
    if (!isTheme(next)) return;
    theme.value = next;
    if (typeof document !== "undefined") document.documentElement.setAttribute("data-theme", next);
    try {
      safeLocalStorage()?.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* 저장소가 막혀 있어도 이번 방문에서는 바뀐다 */
    }
  }

  return { theme, setTheme };
}
