// frontend/composables/useBrowserId.ts
import { generateUuidV4, resolveBrowserId, safeLocalStorage, type BrowserIdResult } from "~/utils/browserId";

let cached: BrowserIdResult | null = null;

function resolved(): BrowserIdResult {
  if (!cached) cached = resolveBrowserId(safeLocalStorage(), generateUuidV4);
  return cached;
}

export function useBrowserId(): string {
  // 서버 렌더에는 브라우저 ID 가 없다 — 빈 값이면 헤더를 붙이지 않는다
  if (import.meta.server) return "";
  return resolved().id;
}

/**
 * 브라우저 ID 를 저장소에 남겼는가 — false 면 새로 고칠 때마다 새 ID 라 이전 기록이 사이드바에서 사라진다(사이드바가 한 줄로 알린다).
 * 서버 렌더에서는 알 수 없어 true(안내를 띄우지 않는다)
 */
export function useBrowserIdPersisted(): boolean {
  if (import.meta.server) return true;
  return resolved().persisted;
}
