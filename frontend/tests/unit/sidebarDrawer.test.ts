// frontend/tests/unit/sidebarDrawer.test.ts
// 좁은 화면(≤768px)의 사이드바 서랍과 DeepRead 패널 덮기(≤1100px) — 순수 함수와 CSS·마크업 약속을 지킨다.
// 가로 스크롤이 없다는 것(문서 폭 = 화면 폭)은 브라우저에서 375·600·768·1024 로 확인한다(이 테스트는 그것을 가능케 하는 규칙이 있는지만 본다).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { NARROW_MAX_WIDTH, NARROW_QUERY, trapTabTarget } from "~/utils/sidebarDrawer";
import { THEMES, css, readingTokens, themeTokens } from "./helpers/themeCss";

const read = (rel: string) => readFileSync(resolve(__dirname, "../..", rel), "utf-8");
const sidebar = read("components/AppSidebar.vue");

/** 주석 지운 CSS 에서 `@media <query> { … }` 블록 본문 전부(중괄호 짝을 맞춰 자른다) */
function mediaBlocks(query: string): string[] {
  const norm = css.replace(/\r\n/g, "\n");
  const out: string[] = [];
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`@media ${escaped}\\s*\\{`, "g");
  for (const m of norm.matchAll(re)) {
    let depth = 1;
    let i = m.index! + m[0].length;
    const start = i;
    for (; i < norm.length && depth > 0; i++) {
      if (norm[i] === "{") depth++;
      else if (norm[i] === "}") depth--;
    }
    out.push(norm.slice(start, i - 1));
  }
  return out;
}

/** 그 query 의 블록 중 marker 를 담은 것 — 없으면 빈 문자열 */
const atBlock = (query: string, marker: string): string => mediaBlocks(query).find((b) => b.includes(marker)) ?? "";

describe("좁은 화면 기준 폭", () => {
  it("기준은 768px 이고 JS matchMedia 질의가 CSS 와 같은 숫자다", () => {
    expect(NARROW_MAX_WIDTH).toBe(768);
    expect(NARROW_QUERY).toBe("(max-width: 768px)");
    expect(atBlock(NARROW_QUERY, ".skx-lnb-scrim")).not.toBe("");
  });
});

describe("trapTabTarget — 서랍 안 Tab 순환", () => {
  const items = ["a", "b", "c"];

  it("가운데 칸에서는 브라우저 기본 이동에 맡긴다(null)", () => {
    expect(trapTabTarget(items, "b", false)).toBeNull();
    expect(trapTabTarget(items, "b", true)).toBeNull();
  });

  it("마지막 칸에서 Tab 이면 첫 칸으로, 첫 칸에서 Shift+Tab 이면 마지막 칸으로", () => {
    expect(trapTabTarget(items, "c", false)).toBe("a");
    expect(trapTabTarget(items, "a", true)).toBe("c");
  });

  it("첫 칸 Tab·마지막 칸 Shift+Tab 은 기본 이동", () => {
    expect(trapTabTarget(items, "a", false)).toBeNull();
    expect(trapTabTarget(items, "c", true)).toBeNull();
  });

  it("초점이 서랍 밖이거나 없으면 방향에 맞는 끝으로 들인다", () => {
    expect(trapTabTarget(items, "zzz", false)).toBe("a");
    expect(trapTabTarget(items, "zzz", true)).toBe("c");
    expect(trapTabTarget(items, null, false)).toBe("a");
  });

  it("초점 가능한 요소가 없으면 null", () => {
    expect(trapTabTarget([], null, false)).toBeNull();
  });

  it("칸이 하나뿐이면 어느 방향이든 그 칸에 머문다", () => {
    expect(trapTabTarget(["x"], "x", false)).toBe("x");
    expect(trapTabTarget(["x"], "x", true)).toBe("x");
  });
});

describe("사이드바 서랍 — CSS", () => {
  const narrow = atBlock("(max-width: 768px)", ".skx-lnb-scrim");

  it("좁은 화면에서 사이드바는 본문을 밀지 않는 fixed 서랍이다(왼쪽에서 열림, 닫히면 visibility: hidden)", () => {
    expect(narrow).toMatch(/\.skx-lnb,\s*\.skx-lnb\.is-lnb-collapsed,\s*\.skx-app\.is-lnb-collapsed \.skx-lnb\s*\{[^}]*position:\s*fixed;/);
    expect(narrow).toMatch(/transform:\s*translateX\(-100%\);/);
    expect(narrow).toMatch(/visibility:\s*hidden;/);
    expect(narrow).toMatch(/\.skx-lnb\.is-drawer-open\s*\{[^}]*transform:\s*none;[^}]*visibility:\s*visible;/);
  });

  it("앱은 세로로 쌓이고(열기 버튼 줄 + 본문) 본문 폭은 사이드바가 갉아먹지 않는다", () => {
    expect(narrow).toMatch(/\.skx-app\s*\{\s*flex-direction:\s*column;/);
    expect(narrow).toMatch(/\.skx-lnb-opener\s*\{[^}]*display:\s*inline-flex;/);
  });

  it("서랍 뒤 막(scrim)이 있고 색은 테마 토큰이며, 열렸을 때만 보인다", () => {
    expect(narrow).toMatch(/\.skx-lnb-scrim\s*\{[^}]*position:\s*fixed;[^}]*background:\s*var\(--skx-scrim\);[^}]*opacity:\s*0;/);
    expect(narrow).toMatch(/\.skx-lnb-scrim\.is-open\s*\{[^}]*opacity:\s*1;/);
  });

  it("서랍 z-index 가 막보다 위다", () => {
    const z = (sel: string) => Number(narrow.match(new RegExp(`${sel}[^}]*z-index:\\s*(\\d+)`))?.[1]);
    expect(z("\\.skx-app\\.is-lnb-collapsed \\.skx-lnb")).toBeGreaterThan(z("\\.skx-lnb-scrim"));
  });

  it("열기 버튼·막은 넓은 화면에서 숨는다(기본 display: none)", () => {
    expect(css).toMatch(/\.skx-lnb-opener,\s*\.skx-lnb-scrim\s*\{\s*display:\s*none;\s*\}/);
  });

  it("서랍이 열린 동안 본문 스크롤 잠금 규칙이 있다", () => {
    expect(css).toMatch(/html\.skx-scroll-lock\s*\{\s*overflow:\s*hidden;/);
  });

  it("움직임 줄이기 설정이면 서랍·막 전환이 즉시다", () => {
    expect(css).toMatch(/@media \(max-width: 768px\) and \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.skx-lnb-scrim\.is-open[^}]*transition:\s*none;/);
  });

  it("접힌 띠 규칙은 넓은 화면(≥769px)에서만 걸린다 — 좁은 화면에 띠·휴대폰용 화살표 띠가 남지 않는다", () => {
    const wide = atBlock("(min-width: 769px)", ".skx-lnb__rail");
    expect(wide).toContain(".skx-lnb.is-lnb-collapsed > :not(.skx-lnb__rail):not(.skx-profile)");
    expect(wide).toMatch(/width:\s*calc\(40px \+ 1\.2rem\);/);
    expect(css).not.toContain("skx-rail__ico--arrow");
    expect(css).not.toContain("skx-rail__ico--panel");
    expect(css).not.toContain("is-lnb-instant");
  });

  it("좁은 화면 사이드바 규칙에 고정 폭 16rem·sticky 가 남지 않는다(서랍 폭은 화면에 맞춘다)", () => {
    expect(narrow).toMatch(/width:\s*min\(17rem,\s*calc\(100vw - 3rem\)\);/);
    expect(narrow).toMatch(/max-height:\s*none;/);
  });

  it.each(THEMES)("[%s] 막 색(--skx-scrim)이 있고 반투명이다", (theme) => {
    const v = themeTokens(theme)["--skx-scrim"]!;
    expect(v).toMatch(/^rgba\(\d+, \d+, \d+, 0\.\d+\)$/);
    const a = Number(v.match(/, ([\d.]+)\)$/)![1]);
    expect(a).toBeGreaterThanOrEqual(0.3);
    expect(a).toBeLessThanOrEqual(0.8);
  });

  it("밝은 읽는 면도 막 색을 다시 선언한다", () => {
    expect(readingTokens("dark-green")["--skx-scrim"]).toBeDefined();
  });
});

describe("사이드바 서랍 — 마크업·동작", () => {
  it("[사이드바 열기] 버튼이 있고 서랍 상태를 aria 로 알린다", () => {
    expect(sidebar).toMatch(/class="skx-lnb-opener"[\s\S]*?aria-label="사이드바 열기"[\s\S]*?:aria-expanded="drawerOpen"[\s\S]*?aria-controls="skx-lnb"/);
    expect(sidebar).toContain('id="skx-lnb"');
  });

  it("막을 누르면 닫히고(초점 복귀), Esc 로 닫히며, 열린 동안 스크롤을 잠근다", () => {
    expect(sidebar).toMatch(/class="\['skx-lnb-scrim', drawerOpen && 'is-open'\]"[^>]*@click="closeDrawer\(true\)"/);
    expect(sidebar).toContain('e.key === "Escape" && drawerOpen.value');
    expect(sidebar).toContain('SCROLL_LOCK_CLASS = "skx-scroll-lock"');
    expect(sidebar).toContain("document.documentElement.classList.toggle(SCROLL_LOCK_CLASS, isOpen)");
  });

  it("닫히면 열기 버튼으로 초점이 돌아가고, 열리면 서랍 안(접기 버튼)으로 초점이 간다", () => {
    expect(sidebar).toMatch(/function closeDrawer\(restoreFocus: boolean\)[\s\S]*?openerBtn\.value\?\.focus/);
    expect(sidebar).toMatch(/async function openDrawer\(\)[\s\S]*?collapseBtn\.value\?\.focus/);
  });

  it("좁은 화면에서는 데스크톱에서 펼쳐 둔 값(open)과 상관없이 닫힌 채 시작한다(서랍 상태는 따로, 처음 false)", () => {
    expect(sidebar).toContain("const drawerOpen = ref(false);");
    expect(sidebar).not.toContain("lnbAutoFolded");
    expect(sidebar).toContain("window.matchMedia(NARROW_QUERY)");
  });

  it("폭이 바뀌어 좁아지거나 넓어지면 서랍을 닫고, 주소가 바뀌어도 닫는다", () => {
    expect(sidebar).toMatch(/function onNarrowChange[\s\S]*?drawerOpen\.value = false;/);
    expect(sidebar).toMatch(/watch\(\s*\(\) => route\.fullPath,\s*\(\) => closeDrawer\(false\)/);
  });

  it("서랍 안에서 Tab 이 본문으로 새지 않는다(trapTabTarget)", () => {
    expect(sidebar).toContain("trapTabTarget(items, document.activeElement");
    expect(sidebar).toContain('@keydown="onAsideKeydown"');
  });
});

describe("DeepRead 패널 — 1100px 이하에서는 본문을 밀지 않고 덮는다", () => {
  const overlay = atBlock("(max-width: 1100px)", ".skx-chat-panel.is-open");

  it("fixed 로 오른쪽에서 열리고 닫히면 visibility: hidden 이다", () => {
    expect(overlay).toMatch(/\.skx-chat-panel,\s*\.skx-chat-panel\.is-open\s*\{[^}]*position:\s*fixed;/);
    expect(overlay).toMatch(/transform:\s*translateX\(100%\);/);
    expect(overlay).toMatch(/visibility:\s*hidden;/);
    expect(overlay).toMatch(/\.skx-chat-panel\.is-open\s*\{[^}]*transform:\s*none;/);
  });

  it("폭은 24rem 을 넘지 않고, 안쪽은 패널 폭·높이를 그대로 채운다", () => {
    expect(overlay).toMatch(/width:\s*min\(24rem,\s*100vw\);/);
    expect(overlay).toMatch(/\.skx-chat-panel__inner\s*\{[^}]*width:\s*100%;[^}]*height:\s*100%;/);
  });

  it("휴대폰(≤600px)에서는 화면 폭을 다 덮는다", () => {
    expect(atBlock("(max-width: 600px)", ".skx-chat-panel")).toMatch(/width:\s*100vw;/);
  });

  it("넓은 화면(>1100px)의 기본 규칙은 그대로 본문을 민다(폭 0 → 24rem 전환)", () => {
    expect(css).toMatch(/\.skx-chat-panel\.is-open\s*\{\s*width:\s*24rem;\s*margin-left:\s*1\.2rem;/);
  });
});

describe("키워드 칩 — 좁은 칸에서 말줄임으로 자른다", () => {
  it(".skx-tag 가 max-width: 100% + 말줄임이라 긴 칩이 문서 가로 폭을 늘리지 않는다", () => {
    const rule = css.match(/\n\.skx-tag\s*\{[^}]*\}/)?.[0] ?? "";
    expect(rule).toMatch(/max-width:\s*100%;/);
    expect(rule).toMatch(/overflow:\s*hidden;/);
    expect(rule).toMatch(/text-overflow:\s*ellipsis;/);
    expect(rule).toMatch(/white-space:\s*nowrap;/);
  });
});
