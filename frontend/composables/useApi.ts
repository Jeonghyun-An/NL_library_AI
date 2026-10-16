// frontend/composables/useApi.ts
import { useBrowserId } from "./useBrowserId";

/**
 * 읽기 요청(GET·HEAD)의 기본 시간 제한. 서버·게이트웨이가 응답을 붙들고 있으면 화면이 '불러오는 중'에 끝없이 머문다 —
 * 이만큼 지나면 끊고 시간 초과(utils/apiErrors 의 'timeout')로 알린다. 읽기는 보통 수 초 안에 끝난다.
 * 쓰기 요청(POST·PUT·PATCH·DELETE)에는 걸지 않는다 — 연구 어시스턴트의 일부 동기 요청은 게이트웨이 한도(120초) 가까이 걸리고,
 * 중간에 끊어도 서버에서는 계속 돌아 같은 작업을 두 번 시키게 된다
 */
export const API_READ_TIMEOUT_MS = 30_000;

const READ_METHODS = new Set(["GET", "HEAD"]);

interface TimeoutOptions {
  method?: string;
  timeout?: number;
  signal?: AbortSignal | null;
}

/**
 * 읽기 요청에 기본 시간 제한을 건다(onRequest 에서 부른다). ofetch 1.5.1 은 호출부가 signal 을 주면 timeout 을 건너뛰고,
 * timeout 처리는 onRequest 훅 뒤에 일어난다 — 그래서 여기서 정한다.
 *  - 호출부가 timeout 을 줬으면 그대로 둔다(0 = 시간 제한 없음도 호출부의 뜻)
 *  - signal 이 없으면 options.timeout(ofetch 가 TimeoutError 로 끊는다)
 *  - signal 이 있으면(화면을 떠나면 끊는 요청) 그 signal 과 시간 제한을 AbortSignal.any 로 합친다 — 어느 쪽이든 먼저 오면 끊긴다.
 *    AbortSignal.any 가 없는 브라우저면 합치지 않고 호출부 signal 만 둔다
 * ofetch 는 GET 이 응답 없이 실패하면 한 번 다시 보내고 이 함수도 다시 불린다 — 다시 보낸 요청도 첫 요청의 시간 제한 안에서 끝난다
 * (ofetch 의 타이머는 다시 보낸 요청이 끝날 때까지 살아 있고, 합친 signal 은 앞 signal 을 품고 간다)
 */
export function withReadTimeout(options: TimeoutOptions): void {
  if (!READ_METHODS.has((options.method ?? "GET").toUpperCase())) return;
  if (options.timeout !== undefined) return;
  if (!options.signal) {
    options.timeout = API_READ_TIMEOUT_MS;
    return;
  }
  if (typeof AbortSignal.any === "function" && typeof AbortSignal.timeout === "function") {
    options.signal = AbortSignal.any([options.signal, AbortSignal.timeout(API_READ_TIMEOUT_MS)]);
  }
}

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
      withReadTimeout(options);
      const sid = useBrowserId();
      if (!sid) return;
      const headers = new Headers(options.headers);
      headers.set("x-session-id", sid);
      options.headers = headers;
    },
  });
}
