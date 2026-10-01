// frontend/composables/useApi.ts
import { useBrowserId } from "./useBrowserId";

function apiBase(): string {
  return ((useRuntimeConfig().public.apiBase as string) || "/api").replace(/\/+$/, "");
}

export function apiUrl(path: string): string {
  return `${apiBase()}${path.startsWith("/") ? path : `/${path}`}`;
}

/** 스트림처럼 native fetch 를 써야 하는 곳용 — $fetch 는 useApi 가 붙인다 */
export function apiHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const sid = useBrowserId();
  return sid ? { ...extra, "x-session-id": sid } : { ...extra };
}

export function useApi() {
  return $fetch.create({
    baseURL: apiBase(),
    onRequest({ options }) {
      const sid = useBrowserId();
      if (!sid) return;
      const headers = new Headers(options.headers);
      headers.set("x-session-id", sid);
      options.headers = headers;
    },
  });
}
