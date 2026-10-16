// frontend/tests/unit/errorComponents.test.ts
// 공통 오류 기반 — 상태 블록(SkxErrorState)·줄 안내(SkxInlineError)·전역 오류 화면(error.vue)·읽기 요청 시간 제한(useApi)·CSS 구역.
// 컴포넌트는 Nuxt 를 띄우지 않고 소스 글을 검사한다(기존 관례). 시간 제한은 순수 함수(withReadTimeout)를 실제로 돌려 본다
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createFetch } from "ofetch";
import { describe, expect, it } from "vitest";
import { API_READ_TIMEOUT_MS, withReadTimeout } from "~/composables/useApi";
import { errorKind, isAbortError } from "~/utils/apiErrors";
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
    for (const kind of ["error", "network", "timeout", "busy", "server", "notFound", "invalid", "conflict", "forbidden", "unknown", "empty"]) {
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

  it("빈 결과는 status, 나머지는 alert", () => {
    expect(tpl).toContain(":role=\"kind === 'empty' ? 'status' : 'alert'\"");
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

  it("부모의 @retry 는 onRetry prop 으로 받아, 있을 때만 [다시 시도] 를 그린다 — 재시도 중이면 잠그고 aria-busy", () => {
    expect(js).toMatch(/onRetry\?: \(\) => void;/);
    expect(tpl).toContain('v-if="onRetry || $slots.default"');
    expect(tpl).toMatch(/<button\s+v-if="onRetry"\s+type="button"\s+class="skx-state__retry"\s+:disabled="busy"\s+:aria-busy="busy \? 'true' : undefined"\s+@click="onRetry\(\)"/);
    expect(tpl).toContain("{{ retryLabel }}");
  });

  it("기본 슬롯은 버튼 줄 안 — 덧붙일 버튼·링크 자리", () => {
    expect(tpl).toMatch(/<div v-if="onRetry \|\| \$slots\.default" class="skx-state__actions">[\s\S]*<slot \/>\s*<\/div>/);
  });

  it("빈 결과·찾을 수 없음은 차분한 갈래(neutral), 나머지는 실패 갈래(error)", () => {
    expect(js).toContain('props.kind === "empty" || props.kind === "notFound" ? "neutral" : "error"');
  });
});

describe("SkxInlineError — 줄 단위 안내", () => {
  const tpl = template(inlineVue);
  const js = script(inlineVue);

  it("<p role=alert> 안에 글·[다시 시도]·슬롯", () => {
    expect(tpl).toMatch(
      /<p class="skx-inline-error" role="alert">\s*<span class="skx-inline-error__msg">\{\{ message \}\}<\/span>\s*<button[\s\S]*?class="skx-inline-error__retry"[\s\S]*?<\/button>\s*<slot \/>\s*<\/p>/,
    );
  });

  it("onRetry prop 이 있을 때만 버튼, 재시도 중이면 잠그고 aria-busy", () => {
    expect(js).toMatch(/message: string;/);
    expect(js).toMatch(/onRetry\?: \(\) => void;/);
    expect(js).toContain('retryLabel: "다시 시도"');
    expect(tpl).toMatch(/v-if="onRetry"[\s\S]*?:disabled="busy"[\s\S]*?:aria-busy="busy \? 'true' : undefined"[\s\S]*?@click="onRetry\(\)"/);
  });
});

describe("error.vue — 전역 오류 화면", () => {
  const tpl = template(errorVue);
  const js = script(errorVue);

  it("홀로그램 배경·워드마크·상태 블록을 둔다", () => {
    expect(tpl).toMatch(/<div class="skx-holo" aria-hidden="true">[\s\S]*skx-holo__band--1[\s\S]*skx-holo__band--2[\s\S]*skx-holo__band--3/);
    expect(tpl).toContain('<SkovixWordmark class="skx-error-page__logo" decorative />');
    expect(tpl).toContain("<SkxErrorState");
  });

  it("404 — 페이지를 찾을 수 없음 + [처음 화면으로]", () => {
    expect(js).toContain("(props.error?.status ?? props.error?.statusCode) === 404");
    expect(tpl).toContain('title="페이지를 찾을 수 없습니다"');
    expect(tpl).toContain('message="주소가 바뀌었거나 없는 페이지입니다."');
    expect(js).toContain('clearError({ redirect: "/" })');
  });

  it("그 밖 — 문제가 생겼습니다 + [다시 시도](새로 불러오기) + [처음 화면으로]", () => {
    expect(tpl).toContain('title="문제가 생겼습니다"');
    expect(tpl).toContain('message="잠시 뒤 다시 시도하세요."');
    expect(tpl).toContain('@retry="reload"');
    expect(js).toContain("window.location.reload()");
    expect(tpl.match(/처음 화면으로/g)).toHaveLength(2);
  });

  it("탭 제목은 SKOVIX", () => {
    expect(js).toContain('useHead({ title: "SKOVIX" })');
  });

  it("오류 객체의 영문 message·stack 을 화면에 내보내지 않는다", () => {
    expect(tpl).not.toMatch(/error\.(message|stack|statusMessage|statusText|data)/);
    expect(tpl).not.toMatch(/\{\{\s*error/);
  });
});

describe("useApi — 읽기 요청의 기본 시간 제한", () => {
  it("30초", () => {
    expect(API_READ_TIMEOUT_MS).toBe(30_000);
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
    let calls = 0;
    const flaky = ((_: unknown, init?: RequestInit) => {
      calls += 1;
      if (calls === 1) return Promise.reject(new TypeError("fetch failed"));
      return new Promise((_resolve, reject) => {
        const signal = init?.signal;
        if (signal?.aborted) return reject(signal.reason);
        signal?.addEventListener("abort", () => reject(signal.reason), { once: true });
      });
    }) as unknown as typeof fetch;
    const $f = createFetch({ fetch: flaky, defaults: { onRequest: ({ options }) => withReadTimeout(options) } });
    const err = await $f("/api/x", { timeout: 20 }).then(
      () => null,
      (e: unknown) => e,
    );
    expect(calls).toBe(2);
    expect(errorKind(err)).toBe("timeout");
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

  it("AbortSignal.any 가 없는 브라우저면 호출부 signal 을 그대로 둔다", () => {
    const original = AbortSignal.any;
    try {
      Object.defineProperty(AbortSignal, "any", { value: undefined, configurable: true, writable: true });
      const caller = new AbortController();
      const opts: { timeout?: number; signal?: AbortSignal | null } = { signal: caller.signal };
      withReadTimeout(opts);
      expect(opts.signal).toBe(caller.signal);
      expect(opts.timeout).toBeUndefined();
    } finally {
      Object.defineProperty(AbortSignal, "any", { value: original, configurable: true, writable: true });
    }
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

  it("버튼은 :focus-visible 테두리가 있고, 손가락 화면에서는 44px·글자 버튼도 24px(좁은 화면은 rem 이 14.4px 라 px 로)", () => {
    expect(code).toMatch(/\.skx-state__retry:focus-visible,\s*\.skx-state__action:focus-visible,\s*\.skx-inline-error__retry:focus-visible\s*\{\s*outline: 2px solid var\(--skx-accent\);/);
    expect(code).toMatch(/@media \(pointer: coarse\) \{\s*\.skx-state__retry,\s*\.skx-state__action \{\s*min-height: 44px;/);
    expect(code).toMatch(/\.skx-inline-error__retry \{[^}]*min-height: 24px;/);
  });
});
