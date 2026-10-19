// frontend/tests/unit/errorComponentOptions.test.ts
// 공통 오류 컴포넌트의 선택지 — 글자 수의 quiet(평소엔 화면에서만 숨김, 낭독기 알림 영역은 늘 남김)·줄 안내의 role(alert|status)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { blockOrThrow } from "./helpers/themeCss";

const read = (rel: string) => readFileSync(resolve(__dirname, "../..", rel), "utf-8");

describe("SkxCharCount quiet", () => {
  const src = read("components/SkxCharCount.vue");

  it("quiet 이면 뿌리에 --quiet 를 달고, 알림 칸(aria-live)은 v-if 없이 늘 그린다", () => {
    expect(src).toContain("'skx-charcount--quiet': quiet");
    expect(src).toMatch(/quiet\?: boolean;/);
    expect(src).toMatch(/<span class="skx-charcount__msg" aria-live="polite">/);
    expect(src).not.toMatch(/<span[^>]*v-if[^>]*skx-charcount__msg/);
  });

  it("평소(normal)에만 화면 밖으로 접고 display: none 은 쓰지 않는다 — 가까움·한도에서는 보인다", () => {
    const body = blockOrThrow('.skx-charcount--quiet[data-state="normal"]');
    expect(body).toMatch(/position:\s*absolute/);
    expect(body).toMatch(/clip:\s*rect\(0 0 0 0\)/);
    expect(body).not.toMatch(/display:\s*none/);
  });
});

describe("SkxInlineError role", () => {
  const src = read("components/SkxInlineError.vue");

  it("기본은 alert, status 를 넘기면 status — 지난 실패·계속 남는 안내를 거듭 끊고 읽지 않게", () => {
    expect(src).toContain(`:role="role ?? 'alert'"`);
    expect(src).toMatch(/role\?: "alert" \| "status";/);
  });
});
