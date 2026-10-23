// frontend/tests/unit/detailWideChat.test.ts
// 상세 화면(논문·소장자료)은 사이드바를 띠로 접은 채 열고 그 폭을 넓은 DeepRead 창에 준다(요청 2026-10-23).
// ① AppSidebar 의 foldOnEnter — 이 화면에만 있는 접힘(open 은 건드리지 않는다), 띠의 [사이드바 열기]·현미경이 풀고 [사이드바 접기]가 다시 접는다
// ② .skx-chat-panel--wide — 화면 폭마다 이긴 규칙의 width 를 계산해(선택자 우선순위 + 소스 순서) 넓은 창·덮는 창·휴대폰 폭을 본다
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { cssRules, type CssRule } from "./helpers/cssRules";
import { rawCss } from "./helpers/themeCss";

const read = (rel: string) => readFileSync(resolve(__dirname, "../..", rel), "utf-8");
const sidebar = read("components/AppSidebar.vue");
const paperDetail = read("pages/papers/[id].vue");
const bookDetail = read("pages/books/[cnts_id].vue");
const paperResults = read("pages/papers/index.vue");

describe("AppSidebar foldOnEnter — 상세 화면에서만 띠로 접힌 채 연다", () => {
  it("상세 화면은 이 화면의 값(folded)만 읽는다 — 사용자가 고른 open 은 읽지 않는다", () => {
    expect(sidebar).toContain("defineProps<{ collapsed?: boolean; foldOnEnter?: boolean }>()");
    expect(sidebar).toContain("const folded = ref(!!props.foldOnEnter);");
    expect(sidebar).toContain(
      "const isCollapsed = computed(() => !!props.collapsed || (props.foldOnEnter ? folded.value : !open.value));",
    );
  });

  // 상세에서 펼쳤다 접어도 open 이 바뀌지 않아야 다른 화면은 사용자가 고른 그대로다(리뷰 지적 — 펼침만 open 을 써서 접어 둔 결과 화면이 펼쳐졌다)
  it("상세 화면의 펼치기·접기는 folded 만 쓰고 open 은 쓰지 않는다", () => {
    expect(sidebar).toMatch(
      /function collapse\(\) \{\s*if \(narrow\.value\) closeDrawer\(true\);\s*else if \(props\.foldOnEnter\) folded\.value = true;\s*else open\.value = false;\s*\}/,
    );
    expect(sidebar).toMatch(/function unfold\(\) \{\s*if \(props\.foldOnEnter\) folded\.value = false;\s*else open\.value = true;\s*\}/);
    expect(sidebar).toMatch(/function expandFromRail\(\) \{\s*railTip\.value = null;\s*unfold\(\);\s*\}/);
    expect(sidebar).toMatch(/async function openResearchFromRail\(\) \{\s*railTip\.value = null;\s*unfold\(\);/);
    // open 을 true 로 쓰는 곳은 unfold 의 else(상세가 아닌 화면) 한 곳뿐이다
    expect(sidebar.match(/open\.value = true;/g)).toHaveLength(1);
  });

  it("논문·소장자료 상세는 fold-on-enter 로 열고 DeepRead 창에 --wide 를 단다", () => {
    for (const src of [paperDetail, bookDetail]) {
      expect(src).toMatch(/<AppSidebar\s+fold-on-enter\s/);
      expect(src).toContain("'skx-chat-panel', 'skx-chat-panel--wide',");
    }
  });

  it("검색 결과 화면은 그대로 — 채팅을 여는 동안만 접고(collapsed), 창도 24rem", () => {
    expect(paperResults).not.toContain("fold-on-enter");
    expect(paperResults).not.toContain("skx-chat-panel--wide");
    expect(paperResults).toContain(':collapsed="!!chatPaperId"');
  });
});

// ── 화면 폭별로 이긴 width 를 계산한다 ───────────────────────────
const rules = cssRules(rawCss);

/** @media 머리가 그 폭에서 켜지는지 — (max-width)·(min-width) 만 보고, 움직임 줄이기는 꺼진 브라우저로 본다 */
function mediaOn(at: string, vw: number): boolean {
  if (!at) return true;
  if (/prefers-reduced-motion/.test(at)) return false;
  const conds = [...at.matchAll(/\((max|min)-width:\s*(\d+)px\)/g)];
  if (conds.length === 0) return false;
  return conds.every(([, kind, px]) => (kind === "max" ? vw <= Number(px) : vw >= Number(px)));
}

/** '.a.b' 꼴 한 칸이 그 클래스 목록에 맞는지 */
const compoundMatches = (compound: string, classes: string[]) =>
  /^(\.[\w-]+)+$/.test(compound) && compound.split(".").filter(Boolean).every((c) => classes.includes(c));

/** 선택자가 요소(클래스 목록)에 맞는지 — 클래스로만 된 한 칸, 또는 '조상 자손' 두 칸만 다룬다. 맞으면 우선순위(클래스 수) */
function specificityIfMatch(selector: string, own: string[], ancestor: string[]): number | null {
  const parts = selector.split(" ");
  if (parts.length === 1) return compoundMatches(parts[0]!, own) ? parts[0]!.split(".").length - 1 : null;
  if (parts.length === 2 && compoundMatches(parts[0]!, ancestor) && compoundMatches(parts[1]!, own)) {
    return parts[0]!.split(".").length - 1 + parts[1]!.split(".").length - 1;
  }
  return null;
}

/** 그 폭에서 요소의 prop 값 — 우선순위가 높고, 같으면 나중 규칙이 이긴다 */
function winning(prop: string, vw: number, own: string[], ancestor: string[] = []): string | undefined {
  let best: { spec: number; order: number; value: string } | null = null;
  rules.forEach((r: CssRule, order) => {
    if (!r.decls.has(prop) || !mediaOn(r.at, vw)) return;
    for (const sel of r.selectors) {
      const spec = specificityIfMatch(sel, own, ancestor);
      if (spec === null) continue;
      if (!best || spec > best.spec || (spec === best.spec && order >= best.order)) best = { spec, order, value: r.decls.get(prop)! };
    }
  });
  return (best as { value: string } | null)?.value;
}

const WIDE_OPEN = ["skx-chat-panel", "skx-chat-panel--wide", "is-open"];
const PLAIN_OPEN = ["skx-chat-panel", "is-open"];
const INNER = ["skx-chat-panel__inner"];

describe("넓은 DeepRead 창 — 화면 폭마다 이기는 폭", () => {
  it("넓은 화면(>1100px)에서는 화면 폭의 45%를 24rem~40rem 안에서 쓰고, 안쪽도 같은 폭이다", () => {
    for (const vw of [1101, 1280, 1366, 1920]) {
      expect(winning("width", vw, WIDE_OPEN)).toBe("clamp(24rem, 45vw, 40rem)");
      expect(winning("width", vw, INNER, WIDE_OPEN)).toBe("clamp(24rem, 45vw, 40rem)");
    }
  });

  it("1100px 이하에서는 덮는 창이 30rem 을 넘지 않고, 안쪽은 패널을 그대로 채운다", () => {
    for (const vw of [601, 768, 1024, 1100]) {
      expect(winning("width", vw, WIDE_OPEN)).toBe("min(30rem, 100vw)");
      expect(winning("width", vw, ["skx-chat-panel", "skx-chat-panel--wide"])).toBe("min(30rem, 100vw)");
      expect(winning("width", vw, INNER, WIDE_OPEN)).toBe("100%");
      expect(winning("position", vw, WIDE_OPEN)).toBe("fixed");
    }
  });

  it("휴대폰(≤600px)에서는 넓은 창도 화면 폭을 다 덮는다", () => {
    for (const vw of [375, 600]) {
      expect(winning("width", vw, WIDE_OPEN)).toBe("100vw");
      expect(winning("width", vw, INNER, WIDE_OPEN)).toBe("100%");
    }
  });

  it("--wide 가 없는 창(검색 결과 화면)은 전과 같다 — 넓은 화면 24rem, 덮을 때 min(24rem, 100vw)", () => {
    expect(winning("width", 1920, PLAIN_OPEN)).toBe("24rem");
    expect(winning("width", 1920, INNER, PLAIN_OPEN)).toBe("24rem");
    expect(winning("width", 1024, PLAIN_OPEN)).toBe("min(24rem, 100vw)");
    expect(winning("width", 1024, INNER, PLAIN_OPEN)).toBe("100%");
  });

  it("닫힌 넓은 창은 넓은 화면에서 폭 0 이다(열 때만 넓어진다)", () => {
    expect(winning("width", 1920, ["skx-chat-panel", "skx-chat-panel--wide"])).toBe("0");
  });

  // 위 계산기는 :has 를 읽지 못해 이 규칙은 모양으로 본다 — 사이드바(.skx-lnb)를 펼친 상세 화면은 창이 24rem 으로 돌아간다
  it("상세 화면에서 사이드바를 다시 펼치면 창은 24rem 으로 돌아간다(본문을 미는 넓은 화면에서만)", () => {
    const back = rules.find((r) =>
      r.selectors.includes(".skx-app:has(.skx-lnb:not(.is-lnb-collapsed)) .skx-chat-panel--wide.is-open"),
    );
    expect(back?.at).toBe("@media (min-width: 1101px)");
    expect(back?.selectors).toContain(".skx-app:has(.skx-lnb:not(.is-lnb-collapsed)) .skx-chat-panel--wide .skx-chat-panel__inner");
    expect(back?.decls.get("width")).toBe("24rem");
  });

  // 펴고 접는 동안 안쪽 카드가 창과 같이 움직여야 빈 띠·잘림이 없다(리뷰 지적). 덮는 창(≤1100px)의 안쪽은 100% 라 전환이 없다
  it("넓은 창의 안쪽 카드는 창과 같은 0.42초로 폭을 바꾸고, 덮는 창에서는 전환이 없다", () => {
    const base = rules.find((r) => r.selectors.includes(".skx-chat-panel.is-open") && !r.at);
    expect(winning("transition", 1280, INNER, WIDE_OPEN)).toBe("width 0.42s cubic-bezier(0.4, 0, 0.2, 1)");
    expect(base?.decls.get("transition")).toContain("width 0.42s cubic-bezier(0.4, 0, 0.2, 1)");
    expect(winning("transition", 1024, INNER, WIDE_OPEN)).toBe("none");
  });
});
