// frontend/composables/useBrowserId.ts
import { generateUuidV4, readOrCreateBrowserId, safeLocalStorage } from "~/utils/browserId";

let cached: string | null = null;

export function useBrowserId(): string {
  // 서버 렌더에는 브라우저 ID 가 없다 — 빈 값이면 헤더를 붙이지 않는다
  if (import.meta.server) return "";
  if (!cached) cached = readOrCreateBrowserId(safeLocalStorage(), generateUuidV4);
  return cached;
}
