// frontend/tests/unit/themeCite.test.ts
// 논문 AI 요약 속 인용 번호 버튼(.skx-cite)·팝오버(.skx-citepop)의 색 — 두 테마에서 읽을 수 있어야 한다.
// 번호는 본문 글자색과 달라 보이도록 --skx-teal-ink 를 쓰고(밑줄·굵기가 보조), 요약 패널(--skx-frost-panel) 위에서 본문 글자 기준(4.5:1)을 넘긴다
import { describe, expect, it } from "vitest";
import {
  THEMES,
  contrast,
  findBlock,
  holoModel,
  over,
  parseColor,
  solidOf,
  themeTokens,
  type ThemeName,
} from "./helpers/themeCss";
import { css } from "./helpers/themeCss";

function rule(selector: string): string {
  const body = findBlock(selector);
  if (body === null) throw new Error(`규칙을 찾지 못함: ${selector}`);
  return body;
}

describe("인용 번호 버튼 — 규칙", () => {
  it("번호 글자색은 --skx-teal-ink 이고 초점 링은 --skx-accent 다(색 리터럴 없음)", () => {
    const body = rule(".skx-cite");
    expect(body).toMatch(/color:\s*var\(--skx-teal-ink\)/);
    expect(body).not.toMatch(/#[0-9a-fA-F]{3,6}\b|rgba?\(/);
    expect(rule(".skx-cite:focus-visible")).toMatch(/outline:\s*2px solid var\(--skx-accent\)/);
  });

  it("누를 수 있다는 단서가 색만이 아니다 — 점선 밑줄과 굵은 글씨", () => {
    const body = rule(".skx-cite");
    expect(body).toMatch(/text-decoration:\s*underline dotted/);
    expect(body).toMatch(/font-weight:\s*700/);
  });

  it("팝오버 규칙에도 색 리터럴이 없다", () => {
    for (const sel of [".skx-citepop", ".skx-citepop__title", ".skx-citepop__meta"]) {
      expect(rule(sel), sel).not.toMatch(/#[0-9a-fA-F]{3,6}\b|rgba?\(/);
    }
  });

  it("작은 화면에서 팝오버가 화면 폭을 넘지 않는다", () => {
    expect(rule(".skx-citepop")).toMatch(/width:\s*min\(\d+(?:\.\d+)?rem,\s*calc\(100vw - 16px\)\)/);
    expect(css).toContain(".skx-citepop__actions .skx-btn-pview");
  });
});

describe.each(THEMES)("인용 번호·팝오버 색 대비 [%s]", (theme: ThemeName) => {
  const t = themeTokens(theme);
  const panel = parseColor(t["--skx-frost-panel"]!);
  const bases = holoModel(theme).bases;
  const lowest = (ink: string) => Math.min(...bases.map((b) => contrast(parseColor(ink).rgb, over(b, panel.rgb, panel.a))));

  it("번호 글자(--skx-teal-ink)는 요약 패널 위 어느 배경에서도 4.5:1 이상", () => {
    expect(lowest(t["--skx-teal-ink"]!)).toBeGreaterThanOrEqual(4.5);
  });

  it("팝오버 제목·저자 줄은 팝오버 면(--skx-glass) 위에서 4.5:1 이상", () => {
    const glass = solidOf(t["--skx-glass"]!, t);
    for (const name of ["--skx-ink-strong", "--skx-ink-2"]) {
      expect(contrast(parseColor(t[name]!).rgb, glass), name).toBeGreaterThanOrEqual(4.5);
    }
  });
});
