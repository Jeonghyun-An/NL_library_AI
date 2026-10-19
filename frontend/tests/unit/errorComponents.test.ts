// frontend/tests/unit/errorComponents.test.ts
// 공통 오류 기반 — 상태 블록(SkxErrorState)·줄 안내(SkxInlineError)·전역 오류 화면(error.vue)·읽기 요청 시간 제한(useApi)·CSS 구역.
// 컴포넌트는 Nuxt 를 띄우지 않고 소스 글을 검사한다(기존 관례). 시간 제한은 순수 함수(withReadTimeout)를 실제로 돌려 본다
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createFetch } from "ofetch";
import { afterEach, describe, expect, it, vi } from "vitest";
import { API_READ_TIMEOUT_MS, API_SEARCH_TIMEOUT_MS, withReadTimeout } from "~/composables/useApi";
import { ERROR_PAGE_TEXT, errorKind, isAbortError } from "~/utils/apiErrors";
import { rawCss } from "./helpers/themeCss";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8");

const stateVue = read("components/SkxErrorState.vue");
const inlineVue = read("components/SkxInlineError.vue");
const errorVue = read("error.vue");
const useApiTs = read("composables/useApi.ts");

/** <template> 부분만 — 머리 주석의 글에 속지 않게 */
const template = (src: string) => src.match(/<template>([\s\S]*)<\/template>/)?.[1] ?? "";
const script = (src: string) => src.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)?.[1] ?? "";

describe("SkxErrorState — 섹션·화면 단위 상태 블록", () => {
  const tpl = template(stateVue);
  const js = script(stateVue);

  it("머리 주석에 디자인을 입힐 자리와 kind 별 의미를 적는다", () => {
    expect(stateVue).toContain("디자인은 이 클래스");
    expect(stateVue).toContain("전체 오류 화면에 반영된다");
    for (const kind of ["error", "network", "timeout", "busy", "server", "notFound", "invalid", "conflict", "forbidden", "unknown", "empty", "canceled"]) {
      expect(stateVue, kind).toMatch(new RegExp(`\\n\\s+${kind}\\s+—`));
    }
  });

  it("디자인 훅 — kind 클래스·data-kind·data-tone·compact", () => {
    expect(tpl).toContain('class="skx-state"');
    expect(tpl).toContain(":class=\"[`skx-state--${kind}`, { 'skx-state--compact': compact }]\"");
    expect(tpl).toContain(':data-kind="kind"');
    expect(tpl).toContain(':data-tone="tone"');
    for (const cls of ["skx-state__icon", "skx-state__title", "skx-state__msg", "skx-state__actions", "skx-state__retry"]) {
      expect(tpl, cls).toContain(`class="${cls}"`);
    }
  });

  it("빈 결과·취소는 status, 나머지는 alert", () => {
    expect(tpl).toContain(":role=\"kind === 'empty' || kind === 'canceled' ? 'status' : 'alert'\"");
  });

  it("아이콘 — 시안의 32px 선 아이콘을 인라인으로(aria-hidden, 색은 currentColor). 빈 결과·찾을 수 없음·취소만 제 그림, 실패 갈래는 경고 삼각형", () => {
    expect(tpl).toMatch(/<span class="skx-state__icon" aria-hidden="true">\s*<svg[\s\S]*?viewBox="0 0 32 32"[\s\S]*?stroke="currentColor"[\s\S]*?stroke-width="2\.4"/);
    expect(tpl).toContain("<template v-if=\"icon === 'empty'\">");
    expect(tpl).toContain("<template v-else-if=\"icon === 'notFound'\">");
    expect(tpl).toMatch(/<rect v-else-if="icon === 'canceled'" x="8" y="8" width="16" height="16" rx="2\.67" \/>/);
    // 경고 삼각형 — 느낌표(세로 획·점)가 있다
    expect(tpl).toMatch(/<template v-else>[\s\S]*?<path d="M16 12v5\.33" \/>\s*<path d="M16 22\.67h\.01" \/>/);
    expect(js).toContain('props.kind === "empty" || props.kind === "notFound" || props.kind === "canceled" ? props.kind : "warning"');
  });

  it("props — 기본 kind 는 일반 실패('error'), 재시도 글 '다시 시도'", () => {
    expect(js).toMatch(/kind\?: ErrorStateKind;/);
    expect(js).toMatch(/title: string;/);
    expect(js).toMatch(/message\?: string;/);
    expect(js).toMatch(/retryLabel\?: string;/);
    expect(js).toMatch(/busy\?: boolean;/);
    expect(js).toMatch(/compact\?: boolean;/);
    expect(js).toContain('kind: "error"');
    expect(js).toContain('retryLabel: "다시 시도"');
    expect(js).toContain('import type { ErrorStateKind } from "~/utils/apiErrors"');
  });

  it("부모의 @retry 는 onRetry prop 으로 받아, 있을 때만 [다시 시도] 를 그린다 — 재시도 중이면 aria-disabled·aria-busy 로 알리고 클릭만 무시한다", () => {
    expect(js).toMatch(/onRetry\?: \(\) => void;/);
    expect(tpl).toContain('v-if="onRetry || $slots.default"');
    expect(tpl).toMatch(
      /<button\s+v-if="onRetry"\s+type="button"\s+class="skx-state__retry"\s+:aria-disabled="busy \? 'true' : undefined"\s+:aria-busy="busy \? 'true' : undefined"\s+@click="retry"/,
    );
    // disabled 로 막으면 누른 버튼이 초점을 잃는다
    expect(tpl).not.toMatch(/:disabled=/);
    expect(js).toMatch(/function retry\(\) \{\s*if \(!props\.busy\) props\.onRetry\?\.\(\);\s*\}/);
    expect(tpl).toContain("{{ retryLabel }}");
  });

  it("기본 슬롯은 버튼 줄 안 — 덧붙일 버튼·링크 자리", () => {
    expect(tpl).toMatch(/<div v-if="onRetry \|\| \$slots\.default" class="skx-state__actions">[\s\S]*<slot \/>\s*<\/div>/);
  });

  it("빈 결과·찾을 수 없음·취소는 차분한 갈래(neutral), 나머지는 실패 갈래(error)", () => {
    expect(js).toContain('props.kind === "empty" || props.kind === "notFound" || props.kind === "canceled" ? "neutral" : "error"');
  });
});

describe("SkxInlineError — 줄 단위 안내", () => {
  const tpl = template(inlineVue);
  const js = script(inlineVue);

  it("<div role=alert> 안에 경고 아이콘(aria-hidden)과 글 묶음(글·[다시 시도]·슬롯) — 슬롯에 블록 요소를 넣어도 HTML·수화가 깨지지 않게 <p> 를 쓰지 않는다", () => {
    expect(tpl).toMatch(
      /<div class="skx-inline-error" :role="role \?\? 'alert'">\s*<span class="skx-inline-error__icon" aria-hidden="true">\s*<svg[\s\S]*?stroke="currentColor"[\s\S]*?<\/svg>\s*<\/span>\s*<div class="skx-inline-error__body">\s*<span class="skx-inline-error__msg">\{\{ message \}\}<\/span>\s*<button[\s\S]*?class="skx-inline-error__retry"[\s\S]*?<\/button>\s*<slot \/>\s*<\/div>\s*<\/div>/,
    );
    expect(tpl).not.toMatch(/<p[\s>]/);
  });

  it("onRetry prop 이 있을 때만 버튼, 재시도 중이면 aria-disabled·aria-busy 로 알리고 클릭만 무시한다(초점 유지)", () => {
    expect(js).toMatch(/message: string;/);
    expect(js).toMatch(/onRetry\?: \(\) => void;/);
    expect(js).toContain('retryLabel: "다시 시도"');
    expect(tpl).toMatch(/v-if="onRetry"[\s\S]*?:aria-disabled="busy \? 'true' : undefined"[\s\S]*?:aria-busy="busy \? 'true' : undefined"[\s\S]*?@click="retry"/);
    expect(tpl).not.toMatch(/:disabled=/);
    expect(js).toMatch(/function retry\(\) \{\s*if \(!props\.busy\) props\.onRetry\?\.\(\);\s*\}/);
  });
});

describe("error.vue — 전역 오류 화면(본문은 SkxErrorPage)", () => {
  const tpl = template(errorVue);
  const js = script(errorVue);
  const pageVue = read("components/SkxErrorPage.vue");
  const pageTpl = template(pageVue);
  const pageJs = script(pageVue);

  it("error.vue 는 상태 코드만 넘겨 SkxErrorPage 를 그린다", () => {
    expect(tpl.trim()).toBe('<SkxErrorPage :status="status" />');
    expect(js).toContain("props.error?.status ?? props.error?.statusCode ?? 500");
  });

  it("홀로그램 배경·워드마크·상태 블록을 둔다", () => {
    expect(pageTpl).toMatch(/<div class="skx-holo" aria-hidden="true">[\s\S]*skx-holo__band--1[\s\S]*skx-holo__band--2[\s\S]*skx-holo__band--3/);
    expect(pageTpl).toContain('<SkovixWordmark class="skx-error-page__logo" decorative />');
    expect(pageTpl).toContain("<SkxErrorState");
  });

  it("404 — 페이지를 찾을 수 없음 + [처음 화면으로]", () => {
    expect(pageJs).toContain("props.status === 404");
    expect(pageTpl).toContain(':title="ERROR_PAGE_TEXT.notFound.title"');
    expect(pageTpl).toContain(':message="ERROR_PAGE_TEXT.notFound.message"');
    expect(ERROR_PAGE_TEXT.notFound).toEqual({ title: "페이지를 찾을 수 없어요", message: "주소가 바뀌었거나 없는 페이지예요." });
    expect(pageJs).toContain('clearError({ redirect: "/" })');
  });

  it("그 밖 — 문제가 생겼어요 + [다시 시도](새로 불러오기) + [처음 화면으로]", () => {
    expect(pageTpl).toContain(':title="ERROR_PAGE_TEXT.fatal.title"');
    expect(pageTpl).toContain(':message="ERROR_PAGE_TEXT.fatal.message"');
    expect(ERROR_PAGE_TEXT.fatal).toEqual({ title: "문제가 생겼어요", message: "잠시 뒤 다시 시도해 주세요." });
    expect(pageTpl).toContain('@retry="reload"');
    expect(pageJs).toContain("window.location.reload()");
    expect(pageTpl.match(/\{\{ ERROR_PAGE_TEXT\.home \}\}/g)).toHaveLength(2);
    expect(ERROR_PAGE_TEXT.home).toBe("처음 화면으로");
  });

  it("탭 제목은 SKOVIX — 모음의 액자가 탭 제목을 덮지 않게 error.vue 에만", () => {
    expect(js).toContain('useHead({ title: "SKOVIX" })');
    expect(pageJs).not.toContain("useHead");
  });

  it("오류 객체의 영문 message·stack 을 화면에 내보내지 않는다", () => {
    expect(tpl).not.toMatch(/error\.(message|stack|statusMessage|statusText|data)/);
    expect(tpl).not.toMatch(/\{\{\s*error/);
    expect(pageTpl).not.toMatch(/error\.(message|stack|statusMessage|statusText|data)/);
  });
});

/** signal 이 끊기면 그 이유로 실패하고, 아니면 끝없이 기다리는 fetch */
const hangingFetch = ((_: unknown, init?: RequestInit) =>
  new Promise((_resolve, reject) => {
    const signal = init?.signal;
    if (signal?.aborted) return reject(signal.reason);
    signal?.addEventListener("abort", () => reject(signal.reason), { once: true });
  })) as unknown as typeof fetch;

/** AbortSignal.any 가 없는 브라우저를 흉내 낸다 — 끝나면 되돌린다 */
function withoutSignalAny<T>(run: () => T): T {
  const original = AbortSignal.any;
  Object.defineProperty(AbortSignal, "any", { value: undefined, configurable: true, writable: true });
  const restore = () => Object.defineProperty(AbortSignal, "any", { value: original, configurable: true, writable: true });
  try {
    const result = run();
    if (result instanceof Promise) return result.finally(restore) as T;
    restore();
    return result;
  } catch (e) {
    restore();
    throw e;
  }
}

describe("useApi — 읽기 요청의 기본 시간 제한", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("30초, 읽기 성격 POST 는 60초", () => {
    expect(API_READ_TIMEOUT_MS).toBe(30_000);
    expect(API_SEARCH_TIMEOUT_MS).toBe(60_000);
    expect(useApiTs).toMatch(/읽기 성격 POST 호출부가\s*\n?\s*\*?\s*timeout 으로 직접 넘긴다/);
  });

  it("onRequest 에서 건다(ofetch 의 timeout 처리가 onRequest 뒤라서)", () => {
    expect(useApiTs).toMatch(/onRequest\(\{ options \}\) \{\s*withReadTimeout\(options\);/);
  });

  it("signal 이 없는 GET·HEAD 는 options.timeout", () => {
    const get: { method?: string; timeout?: number } = {};
    withReadTimeout(get);
    expect(get.timeout).toBe(API_READ_TIMEOUT_MS);
    const head = { method: "head" } as { method?: string; timeout?: number };
    withReadTimeout(head);
    expect(head.timeout).toBe(API_READ_TIMEOUT_MS);
  });

  it("쓰기 요청(POST·PUT·PATCH·DELETE)에는 걸지 않는다", () => {
    for (const method of ["POST", "PUT", "PATCH", "DELETE", "post"]) {
      const caller = new AbortController();
      const opts: { method?: string; timeout?: number; signal?: AbortSignal } = { method, signal: caller.signal };
      withReadTimeout(opts);
      expect(opts.timeout, method).toBeUndefined();
      expect(opts.signal, method).toBe(caller.signal);
      const bare: { method?: string; timeout?: number } = { method };
      withReadTimeout(bare);
      expect(bare.timeout, method).toBeUndefined();
    }
  });

  it("호출부가 timeout 을 줬으면(0 = 시간 제한 없음 포함) signal 이 있어도 그대로 둔다", () => {
    const opts = { timeout: 5_000 };
    withReadTimeout(opts);
    expect(opts.timeout).toBe(5_000);
    const off: { timeout?: number; signal?: AbortSignal | null } = { timeout: 0, signal: new AbortController().signal };
    const before = off.signal;
    withReadTimeout(off);
    expect(off.timeout).toBe(0);
    expect(off.signal).toBe(before);
  });

  it("실제 ofetch — 연결 실패 뒤 다시 보낸 요청도 첫 요청의 시간 제한 안에서 끝난다", async () => {
    // 첫 요청은 시간 제한(LIMIT_MS) 직전에 연결 실패로 끝나고, ofetch 가 한 번 다시 보낸 요청은 응답 없이 기다린다.
    // 첫 요청의 시간 제한이 이어지면 LIMIT_MS 쯤에 끝나고, 다시 보낸 요청이 새 시간 제한을 받으면 FIRST_FAIL_MS + LIMIT_MS 쯤에야 끝난다 —
    // 그 사이(BOUND_MS)로 가른다. 둘 다 실제 타이머라 느린 기계에서도 양쪽에 여유가 크게(위 250ms·아래 130ms) 남게 잡았다
    const LIMIT_MS = 400;
    const FIRST_FAIL_MS = 380;
    const BOUND_MS = 650;
    let calls = 0;
    const flaky = ((_: unknown, init?: RequestInit) => {
      calls += 1;
      if (calls === 1) {
        return new Promise((_resolve, reject) => setTimeout(() => reject(new TypeError("fetch failed")), FIRST_FAIL_MS));
      }
      return new Promise((_resolve, reject) => {
        const signal = init?.signal;
        if (signal?.aborted) return reject(signal.reason);
        signal?.addEventListener("abort", () => reject(signal.reason), { once: true });
      });
    }) as unknown as typeof fetch;
    const $f = createFetch({ fetch: flaky, defaults: { onRequest: ({ options }) => withReadTimeout(options) } });
    const started = performance.now();
    const err = await $f("/api/x", { timeout: LIMIT_MS }).then(
      () => null,
      (e: unknown) => e,
    );
    const elapsed = performance.now() - started;
    expect(calls).toBe(2);
    expect(errorKind(err)).toBe("timeout");
    // 첫 실패를 기다린 뒤에 끝났고(시나리오대로 돌았다), 다시 보낸 요청이 새 시간 제한을 받지 않았다
    expect(elapsed).toBeGreaterThanOrEqual(FIRST_FAIL_MS - 5);
    expect(elapsed).toBeLessThan(BOUND_MS);
  });

  it("실제 ofetch — signal 없는 GET 은 시간 초과로, 호출부 signal 로 끊은 GET 은 끊김으로 끝난다", async () => {
    const hanging = ((_: unknown, init?: RequestInit) =>
      new Promise((_resolve, reject) => {
        const signal = init?.signal;
        if (signal?.aborted) return reject(signal.reason);
        signal?.addEventListener("abort", () => reject(signal.reason), { once: true });
      })) as unknown as typeof fetch;
    const $f = createFetch({ fetch: hanging, defaults: { onRequest: ({ options }) => withReadTimeout(options) } });
    const timedOut = await $f("/api/x", { timeout: 10 }).then(() => null, (e: unknown) => e);
    expect(errorKind(timedOut)).toBe("timeout");
    expect(isAbortError(timedOut)).toBe(false);
    const caller = new AbortController();
    const pending = $f("/api/x", { signal: caller.signal }).then(() => null, (e: unknown) => e);
    caller.abort();
    expect(isAbortError(await pending)).toBe(true);
  });

  it("signal 이 있으면 시간 제한과 합친다 — 호출부가 끊으면 함께 끊긴다", () => {
    const caller = new AbortController();
    const opts: { timeout?: number; signal?: AbortSignal | null } = { signal: caller.signal };
    withReadTimeout(opts);
    expect(opts.timeout).toBeUndefined();
    expect(opts.signal).not.toBe(caller.signal);
    expect(opts.signal!.aborted).toBe(false);
    caller.abort();
    expect(opts.signal!.aborted).toBe(true);
    expect((opts.signal!.reason as DOMException).name).toBe("AbortError");
  });

  it("읽기 성격 POST — 호출부가 timeout 과 signal 을 함께 주면(ofetch 는 timeout 을 건너뛴다) signal 에 합치고 timeout 은 지운다", () => {
    const caller = new AbortController();
    const opts: { method?: string; timeout?: number; signal?: AbortSignal | null } = {
      method: "POST",
      timeout: API_SEARCH_TIMEOUT_MS,
      signal: caller.signal,
    };
    withReadTimeout(opts);
    expect(opts.signal).not.toBe(caller.signal);
    expect("timeout" in opts).toBe(false);
    caller.abort();
    expect(opts.signal!.aborted).toBe(true);
    expect((opts.signal!.reason as DOMException).name).toBe("AbortError");
    // signal 이 없으면 ofetch 의 timeout 그대로
    const bare: { method?: string; timeout?: number } = { method: "POST", timeout: API_SEARCH_TIMEOUT_MS };
    withReadTimeout(bare);
    expect(bare.timeout).toBe(API_SEARCH_TIMEOUT_MS);
  });

  it("이미 합친 signal(ofetch 가 다시 보낸 요청)은 또 합치지 않는다", () => {
    const opts: { timeout?: number; signal?: AbortSignal | null } = { signal: new AbortController().signal };
    withReadTimeout(opts);
    const combined = opts.signal;
    withReadTimeout(opts);
    expect(opts.signal).toBe(combined);
    expect(opts.timeout).toBeUndefined();
  });

  it("실제 ofetch — 읽기 성격 POST 를 signal 과 함께 보내도 시간 제한에 걸리고, 끊으면 끊김으로 끝난다", async () => {
    const $f = createFetch({ fetch: hangingFetch, defaults: { onRequest: ({ options }) => withReadTimeout(options) } });
    const timedOut = await $f("/api/search", { method: "POST", body: { query: "가" }, signal: new AbortController().signal, timeout: 10 })
      .then(() => null, (e: unknown) => e);
    expect(errorKind(timedOut)).toBe("timeout");
    expect(isAbortError(timedOut)).toBe(false);
    const caller = new AbortController();
    const pending = $f("/api/search", { method: "POST", body: { query: "가" }, signal: caller.signal, timeout: 60_000 })
      .then(() => null, (e: unknown) => e);
    caller.abort();
    expect(isAbortError(await pending)).toBe(true);
  });

  describe("AbortSignal.any 가 없는 브라우저 — 대체 경로로 시간 제한을 지킨다", () => {
    it("호출부 signal 과 합친 새 signal — 호출부가 끊으면 그 이유로 끊기고 타이머를 지운다", () => {
      vi.useFakeTimers();
      withoutSignalAny(() => {
        const caller = new AbortController();
        const opts: { timeout?: number; signal?: AbortSignal | null } = { signal: caller.signal };
        withReadTimeout(opts);
        expect(opts.signal).not.toBe(caller.signal);
        expect(opts.timeout).toBeUndefined();
        expect(vi.getTimerCount()).toBe(1);
        caller.abort();
        expect(opts.signal!.aborted).toBe(true);
        expect((opts.signal!.reason as DOMException).name).toBe("AbortError");
        expect(vi.getTimerCount()).toBe(0);
      });
    });

    it("시간이 지나면 TimeoutError 로 끊긴다 — 그 뒤 호출부가 끊어도 바뀌지 않는다", () => {
      vi.useFakeTimers();
      withoutSignalAny(() => {
        const caller = new AbortController();
        const opts: { timeout?: number; signal?: AbortSignal | null } = { signal: caller.signal };
        withReadTimeout(opts);
        vi.advanceTimersByTime(API_READ_TIMEOUT_MS - 1);
        expect(opts.signal!.aborted).toBe(false);
        vi.advanceTimersByTime(1);
        expect(opts.signal!.aborted).toBe(true);
        expect((opts.signal!.reason as Error).name).toBe("TimeoutError");
        caller.abort();
        expect((opts.signal!.reason as Error).name).toBe("TimeoutError");
      });
    });

    it("이미 끊긴 호출부 signal 이면 바로 끊긴 signal(타이머 없음)", () => {
      vi.useFakeTimers();
      withoutSignalAny(() => {
        const caller = new AbortController();
        caller.abort();
        const opts: { timeout?: number; signal?: AbortSignal | null } = { signal: caller.signal };
        withReadTimeout(opts);
        expect(opts.signal!.aborted).toBe(true);
        expect(vi.getTimerCount()).toBe(0);
      });
    });

    it("실제 ofetch — 시간 초과는 timeout, 호출부가 끊으면 끊김", async () => {
      await withoutSignalAny(async () => {
        const $f = createFetch({ fetch: hangingFetch, defaults: { onRequest: ({ options }) => withReadTimeout(options) } });
        const timedOut = await $f("/api/x", { signal: new AbortController().signal, timeout: 10 }).then(() => null, (e: unknown) => e);
        expect(errorKind(timedOut)).toBe("timeout");
        expect(isAbortError(timedOut)).toBe(false);
        const caller = new AbortController();
        const pending = $f("/api/x", { signal: caller.signal }).then(() => null, (e: unknown) => e);
        caller.abort();
        expect(isAbortError(await pending)).toBe(true);
      });
    });
  });

  it("오래된 엔진(이유와 상관없이 fetch 가 AbortError 로 실패) — 시간 초과를 끊김으로 오인하지 않는다", async () => {
    const oldEngineFetch = ((_: unknown, init?: RequestInit) =>
      new Promise((_resolve, reject) => {
        const fail = () => reject(new DOMException("The operation was aborted.", "AbortError"));
        const signal = init?.signal;
        if (signal?.aborted) return fail();
        signal?.addEventListener("abort", fail, { once: true });
      })) as unknown as typeof fetch;
    const $f = createFetch({ fetch: oldEngineFetch, defaults: { onRequest: ({ options }) => withReadTimeout(options) } });
    const timedOut = await $f("/api/x", { signal: new AbortController().signal, timeout: 10 }).then(() => null, (e: unknown) => e);
    expect(isAbortError(timedOut)).toBe(false);
    expect(errorKind(timedOut)).toBe("timeout");
    const caller = new AbortController();
    const pending = $f("/api/x", { signal: caller.signal }).then(() => null, (e: unknown) => e);
    caller.abort();
    expect(isAbortError(await pending)).toBe(true);
  });
});

describe("CSS — '[S] 공통 오류·빈 상태' 구역", () => {
  const section = rawCss.match(/\/\* \[S\] 공통 오류·빈 상태[\s\S]*?\/\* \[E\] 공통 오류·빈 상태 \*\//)?.[0] ?? "";
  const code = section.replace(/\/\*[\s\S]*?\*\//g, "");

  it("구역이 style_skovix.css 에 있다", () => {
    expect(section.length).toBeGreaterThan(0);
  });

  it("두 컴포넌트·오류 화면의 클래스를 모두 꾸민다", () => {
    for (const cls of [
      ".skx-state ",
      ".skx-state__title",
      ".skx-state__msg",
      ".skx-state__actions",
      ".skx-state__retry",
      ".skx-state__action",
      ".skx-state--empty",
      ".skx-state--compact",
      '.skx-state[data-tone="error"]',
      ".skx-inline-error ",
      ".skx-inline-error__msg",
      ".skx-inline-error__retry",
      ".skx-error-page ",
    ]) {
      expect(code, cls).toContain(cls);
    }
  });

  it("색은 토큰만 — 색 리터럴(#hex·rgb()·hsl()·색 이름·currentColor)이 없다", () => {
    const literals =
      code.match(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|(?<![\w-])(?:white|black|red|green|blue|gray|grey|currentcolor)(?![\w-])/gi) ?? [];
    expect(literals).toEqual([]);
    expect(code).toMatch(/var\(--skx-danger\)/);
  });

  it("글자는 칠하지 않는다 — 제목 --skx-ink-strong·설명 --skx-gray-1·줄 안내 --skx-ink, 위험색은 아이콘에만", () => {
    const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    /** 선택자 하나만으로 된 규칙의 본문 */
    const rule = (selector: string) => code.match(new RegExp(`(?:^|\\n)${escape(selector)} \\{([^}]*)\\}`))?.[1] ?? "";
    expect(rule(".skx-state__title")).toMatch(/color: var\(--skx-ink-strong\);/);
    expect(rule(".skx-state__msg")).toMatch(/color: var\(--skx-gray-1\);/);
    expect(rule(".skx-inline-error")).toMatch(/color: var\(--skx-ink\);/);
    // 위험색은 아이콘 색으로만 — 글자색(color:)에 쓰는 곳은 아이콘 규칙뿐이다
    const dangerRules = [...code.matchAll(/([^{}]+)\{([^}]*)\}/g)]
      .filter((m) => /var\(--skx-danger\)/.test(m[2] ?? ""))
      .map((m) => (m[1] ?? "").trim());
    expect(dangerRules).toEqual(['.skx-state[data-tone="error"]', ".skx-inline-error__icon", ".skx-conn--lost .skx-conn__icon"]);
  });

  it("아이콘 원 — 70px 원·아이콘색 12% 채움·50% 테두리, 색은 갈래·kind 가 --state-ico 로 정한다", () => {
    expect(code).toMatch(/\.skx-state__icon \{[^}]*width: 3\.5rem;[^}]*height: 3\.5rem;[^}]*color: var\(--state-ico\);[^}]*background: color-mix\(in srgb, var\(--state-ico\) 12%, transparent\);[^}]*border: 1px solid color-mix\(in srgb, var\(--state-ico\) 50%, transparent\);[^}]*border-radius: 50%;/);
    expect(code).toMatch(/\.skx-state\[data-tone="error"\] \{\s*--state-ico: var\(--skx-danger\);/);
    expect(code).toMatch(/\.skx-state--empty \{\s*--state-ico: var\(--skx-teal-ink\);/);
    expect(code).toMatch(/\.skx-state--notFound \{\s*--state-ico: var\(--skx-gray-1\);/);
    expect(code).toMatch(/\.skx-state--canceled \{\s*--state-ico: var\(--skx-primary\);/);
    // compact 는 48px 원
    expect(code).toMatch(/\.skx-state--compact \.skx-state__icon \{\s*width: 2\.4rem;\s*height: 2\.4rem;/);
  });

  it("버튼 줄의 첫 버튼([다시 시도], 없으면 슬롯의 첫 버튼)이 포인트색 채움, 나머지는 옅은 면 + 테두리", () => {
    expect(code).toMatch(/\.skx-state__retry,\s*\.skx-state__actions > \.skx-state__action:first-child \{\s*color: var\(--skx-on-accent\);\s*background: var\(--skx-primary\);\s*border: 1px solid var\(--skx-primary\);/);
    expect(code).toMatch(/\.skx-state__action \{\s*color: var\(--skx-ink\);\s*background: var\(--skx-frost-bg-soft\);\s*border: 1px solid var\(--skx-chip-line\);/);
  });

  it("전역 오류 화면도 상태 블록에 면·테두리를 깔지 않는다 — 설명 글만 본문색으로 진하게(후배 의견 2026-10-16, 대비는 themeHolo.test.ts)", () => {
    expect(code).not.toMatch(/\.skx-error-page \.skx-state \{[^}]*(background|border):/);
    expect(code).toMatch(/\.skx-error-page \.skx-state__msg \{\s*color: var\(--skx-ink\);/);
    expect(code).toMatch(/\.skx-error-page__main \{[^}]*max-width: 32rem;/);
  });

  it("버튼은 :focus-visible 테두리가 있고, 손가락 화면에서는 44px·글자 버튼도 24px(좁은 화면은 rem 이 14.4px 라 px 로)", () => {
    expect(code).toMatch(/\.skx-state__retry:focus-visible,\s*\.skx-state__action:focus-visible,\s*\.skx-inline-error__retry:focus-visible\s*\{\s*outline: 2px solid var\(--skx-accent\);/);
    expect(code).toMatch(/@media \(pointer: coarse\) \{\s*\.skx-state__retry,\s*\.skx-state__action \{\s*min-height: 44px;/);
    expect(code).toMatch(/\.skx-inline-error__retry \{[^}]*min-height: 24px;/);
  });

  it("재시도 중 모양은 aria-disabled 로 — 버튼을 disabled 로 막지 않는다", () => {
    // 슬롯 버튼(.skx-state__action)이 일하는 중인 모양도 같은 규칙에
    expect(code).toMatch(/\.skx-state__retry\[aria-disabled="true"\],\s*\.skx-state__action\[aria-disabled="true"\] \{/);
    expect(code).toMatch(/\.skx-inline-error__retry\[aria-disabled="true"\] \{/);
    expect(code).not.toMatch(/__retry:disabled/);
  });
});
