// frontend/composables/useApi.ts
import { useBrowserId } from "./useBrowserId";

/**
 * 읽기 요청(GET·HEAD)의 기본 시간 제한. 서버·게이트웨이가 응답을 붙들고 있으면 화면이 '불러오는 중'에 끝없이 머문다 —
 * 이만큼 지나면 끊고 시간 초과(utils/apiErrors 의 'timeout')로 알린다. 읽기는 보통 수 초 안에 끝난다.
 * 쓰기 요청(POST·PUT·PATCH·DELETE)에는 기본값을 걸지 않는다 — 연구 어시스턴트의 일부 동기 요청은 게이트웨이 한도(120초) 가까이 걸리고,
 * 중간에 끊어도 서버에서는 계속 돌아 같은 작업을 두 번 시키게 된다
 */
export const API_READ_TIMEOUT_MS = 30_000;

/**
 * 읽기 성격 POST(메인 검색·논문 검색·추천 — 질의를 본문에 실어 보낼 뿐 서버 상태를 바꾸지 않는다)의 시간 제한.
 * LLM 질의 재작성·재정렬로 GET 보다 오래 걸릴 수 있어 60초로 둔다. POST 에는 기본값이 없으니(위 까닭) 읽기 성격 POST 호출부가
 * timeout 으로 직접 넘긴다 — api("/search", { method: "POST", body, signal, timeout: API_SEARCH_TIMEOUT_MS }).
 * signal 과 함께 넘겨도 된다(withReadTimeout 이 둘을 합친다)
 */
export const API_SEARCH_TIMEOUT_MS = 60_000;

const READ_METHODS = new Set(["GET", "HEAD"]);

interface TimeoutOptions {
  method?: string;
  timeout?: number;
  signal?: AbortSignal | null;
}

/**
 * 이 파일이 시간 제한을 합쳐 만든 signal. ofetch 는 GET 이 응답 없이 실패하면 한 번 다시 보내며 onRequest(withReadTimeout)도 다시 부른다 —
 * 이미 합친 signal 이면 또 합치지 않아, 다시 보낸 요청도 첫 요청의 시간 제한 안에서 끝난다
 */
const timedSignals = new WeakSet<AbortSignal>();

/** 시간 초과로 끊을 때의 이유 — AbortSignal.timeout·ofetch 와 같은 이름(utils/apiErrors 가 이 이름으로 시간 초과를 가른다) */
function timeoutReason(): Error {
  const reason = new Error("signal timed out");
  reason.name = "TimeoutError";
  return reason;
}

/**
 * 호출부 signal 과 시간 제한을 하나로 — 어느 쪽이든 먼저 오면 끊긴다(호출부가 끊으면 그 이유, 시간이 지나면 TimeoutError).
 * AbortSignal.any·AbortSignal.timeout 이 있으면 그것을 쓰고, 없는 브라우저(사파리 17.4 전 등)에서는 AbortController 하나에
 * 호출부 signal 의 abort 리스너와 setTimeout 을 묶는다 — 시간 제한이 사라지지 않게. 대체 경로의 타이머는 호출부가 먼저 끊으면 지우고,
 * 타이머가 먼저 울리면 호출부 signal 의 리스너를 뗀다(요청이 먼저 끝나면 타이머는 끝난 요청의 signal 을 끊을 뿐이다 — AbortSignal.timeout 과 같다)
 */
function combineWithTimeout(signal: AbortSignal, ms: number): AbortSignal {
  let combined: AbortSignal;
  if (typeof AbortSignal.any === "function" && typeof AbortSignal.timeout === "function") {
    combined = AbortSignal.any([signal, AbortSignal.timeout(ms)]);
  } else {
    const controller = new AbortController();
    if (signal.aborted) {
      controller.abort(signal.reason);
    } else {
      let timer: ReturnType<typeof setTimeout> | undefined;
      const onAbort = () => {
        clearTimeout(timer);
        controller.abort(signal.reason);
      };
      timer = setTimeout(() => {
        signal.removeEventListener("abort", onAbort);
        controller.abort(timeoutReason());
      }, ms);
      signal.addEventListener("abort", onAbort, { once: true });
    }
    combined = controller.signal;
  }
  timedSignals.add(combined);
  return combined;
}

/**
 * 요청에 시간 제한을 건다(onRequest 에서 부른다). ofetch 1.5.1 은 호출부가 signal 을 주면 timeout 을 건너뛰고,
 * timeout 처리는 onRequest 훅 뒤에 일어난다 — 그래서 여기서 정한다.
 *  - 호출부가 timeout 을 줬으면 그 시간을 쓴다(0 = 시간 제한 없음도 호출부의 뜻). signal 도 함께면 ofetch 가 timeout 을 건너뛰므로
 *    signal 에 합치고 timeout 은 지운다(읽기 성격 POST — API_SEARCH_TIMEOUT_MS — 는 새 검색이 이전 검색을 끊는 signal 과 함께 온다)
 *  - 호출부가 정하지 않은 GET·HEAD 는 API_READ_TIMEOUT_MS — signal 이 없으면 options.timeout(ofetch 가 TimeoutError 로 끊는다),
 *    있으면(화면을 떠나면 끊는 요청) 그 signal 과 합친다
 *  - 쓰기 요청은 호출부가 정하지 않으면 그대로 둔다
 * 다시 보낸 요청: ofetch 의 타이머는 다시 보낸 요청이 끝날 때까지 살아 있고, 합친 signal 은 timedSignals 로 알아봐 다시 합치지 않는다
 */
export function withReadTimeout(options: TimeoutOptions): void {
  if (options.signal && timedSignals.has(options.signal)) return;
  if (options.timeout !== undefined) {
    if (!options.signal || !options.timeout) return;
    options.signal = combineWithTimeout(options.signal, options.timeout);
    delete options.timeout;
    return;
  }
  if (!READ_METHODS.has((options.method ?? "GET").toUpperCase())) return;
  if (!options.signal) {
    options.timeout = API_READ_TIMEOUT_MS;
    return;
  }
  options.signal = combineWithTimeout(options.signal, API_READ_TIMEOUT_MS);
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
