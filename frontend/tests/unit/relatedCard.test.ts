// frontend/tests/unit/relatedCard.test.ts
// 관련 자료 추천 카드 — '자세히 보기' 열림은 사용자가 누른 카드만·한 번에 하나이고, 빛 번짐은 마우스를 올렸을 때와 팝업이 열려 있는 동안만이다.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { relatedOpenAfter } from "~/utils/relatedCard";

const read = (rel: string) => readFileSync(resolve(__dirname, "../..", rel), "utf-8");
const detailCss = read("assets/css/detail.css").replace(/\/\*[\s\S]*?\*\//g, "");
const card = read("components/detail/RelatedCard.vue");

describe("relatedOpenAfter — 한 번에 한 카드, 누른 카드만", () => {
  it("열면 그 카드가 열린 카드다(앞서 열린 카드는 닫힌다)", () => {
    expect(relatedOpenAfter(null, "a", true)).toBe("a");
    expect(relatedOpenAfter("a", "b", true)).toBe("b");
  });

  it("열려 있던 카드의 닫음은 닫는다", () => {
    expect(relatedOpenAfter("a", "a", false)).toBeNull();
  });

  it("이미 닫혔거나 다른 카드가 열린 뒤에 온 닫음은 지금 열린 카드를 닫지 않는다", () => {
    expect(relatedOpenAfter(null, "a", false)).toBeNull();
    expect(relatedOpenAfter("b", "a", false)).toBe("b");
  });

  it("같은 카드를 다시 열어도 그대로 그 카드가 열려 있다", () => {
    expect(relatedOpenAfter("a", "a", true)).toBe("a");
  });
});

describe("빛 번짐 — 마우스 올림·팝업 열림 동안만", () => {
  it(":focus-within 으로는 켜지지 않는다(팝업을 닫으면 초점이 [자세히 보기]로 돌아와 빛이 남았다)", () => {
    expect(detailCss).not.toMatch(/\.dt-rc:focus-within/);
    expect(detailCss).not.toMatch(/focus-within[^{]*\{[^}]*box-shadow/);
  });

  it("마우스 올림은 (hover: hover) 기기에서만 빛을 켠다 — 터치 뒤 눌린 채 남는 :hover 로 빛이 남지 않게", () => {
    expect(detailCss).toMatch(/@media \(hover: hover\)\s*\{\s*\.dt-rc:hover\s*\{[^}]*box-shadow:[^}]*accent/);
  });

  it("팝업이 열려 있는 동안(.is-open)은 빛과 테두리가 있다", () => {
    expect(detailCss).toMatch(/\.dt-rc\.is-open\s*\{[^}]*box-shadow:[^}]*accent[^}]*outline:\s*1\.5px solid var\(--skx-accent\)/);
  });

  it("키보드 초점은 요소마다의 초점 링(:focus-visible)으로 보인다", () => {
    for (const sel of [".dt-rc__link:focus-visible::after", ".dt-rc__more:focus-visible", ".dt-rc__close:focus-visible"]) {
      expect(detailCss, sel).toContain(sel);
    }
  });
});

describe("카드는 늘 닫힌 채 시작한다", () => {
  it("처음부터 열려 있다고 오면 닫는다고 알리고, 뒤로 가기 캐시(pageshow)로 되돌아와도 같다", () => {
    expect(card).toMatch(/onMounted\(\(\) => \{\s*if \(props\.expanded\) setOpen\(false\);/);
    expect(card).toContain('window.addEventListener("pageshow", onPageShow)');
    expect(card).toContain("e.persisted && props.expanded");
    expect(card).toContain('window.removeEventListener("pageshow", onPageShow)');
  });

  it("논문·소장자료 상세 모두 열림을 relatedOpenAfter 로만 바꾼다", () => {
    for (const file of ["pages/papers/[id].vue", "pages/books/[cnts_id].vue"]) {
      const src = read(file);
      expect(src, file).toContain("openRelated = relatedOpenAfter(openRelated, rel.book_id, open)");
      expect(src, file).not.toContain("openRelated = open ? rel.book_id : null");
      expect(src, file).toContain('import { relatedOpenAfter } from "~/utils/relatedCard"');
    }
  });
});
