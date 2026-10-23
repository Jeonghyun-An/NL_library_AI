// frontend/tests/unit/markdown.test.ts
// LLM 글의 물결표(~)는 글자로 — marked(GFM)가 '~글~'을 취소선으로 읽어 '2006~2010년 … 2005~2009년' 사이가 그어졌다(2026-10-23 운영 DeepRead)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { renderAnswer } from "~/utils/deepReadCitations";
import { escapeTildes, renderMarkdown } from "~/utils/markdown";

const read = (rel: string) => readFileSync(resolve(__dirname, "../..", rel), "utf-8");
const RANGE_TWICE = "2006~2010년 국가재정운용계획은 과거 계획을 개선했으며, 2005~2009년 계획을 수정한 연동 계획입니다.";

describe("renderMarkdown — 물결표는 취소선이 아니라 글자", () => {
  it("범위를 두 번 쓴 글도 그어지지 않고 물결표가 그대로 보인다", () => {
    const html = renderMarkdown(RANGE_TWICE);
    expect(html).not.toContain("<del>");
    expect(html).toContain("2006~2010년");
    expect(html).toContain("2005~2009년");
  });

  it("물결표 두 개('~~글~~')도 취소선으로 그리지 않는다 — 답 글에 취소선을 쓸 일이 없다", () => {
    expect(renderMarkdown("~~취소~~")).not.toContain("<del>");
  });

  it("코드 칸·코드 블록 안은 건드리지 않는다", () => {
    expect(escapeTildes("범위 `a~b` 와 2006~2010")).toBe("범위 `a~b` 와 2006\\~2010");
    expect(escapeTildes("```\nx~y\n```")).toBe("```\nx~y\n```");
  });

  it("다른 마크다운(굵게·목록)은 그대로 그리고, 빈 글은 빈 HTML", () => {
    expect(renderMarkdown("**굵게** 3~4쪽")).toBe("<p><strong>굵게</strong> 3~4쪽</p>\n");
    expect(renderMarkdown("- 하나\n- 둘")).toContain("<li>하나</li>");
    expect(renderMarkdown("")).toBe("");
  });
});

describe("DeepRead 답(renderAnswer)도 물결표를 글자로 — 쪽 범위 'p.3~4'는 쪽 번호로 먼저 읽는다", () => {
  it("범위를 두 번 쓴 답이 그어지지 않는다", () => {
    const html = renderAnswer(`${RANGE_TWICE} [p.3]`, null);
    expect(html).not.toContain("<del>");
    expect(html).toContain("2005~2009년");
    expect(html).toContain('<span class="skx-chat-cite is-static">p.3</span>');
  });

  it("'p.3~4'는 물결표를 글자로 바꾸기 전에 쪽 번호로 읽는다", () => {
    expect(renderAnswer("[p.3~4]", null)).toContain('<span class="skx-chat-cite is-static">p.3–4</span>');
  });
});

describe("LLM 글을 그리는 화면은 renderMarkdown 을 쓴다(marked.parse 를 바로 부르지 않는다)", () => {
  // 보존 화면(TopResult·BookChat.legacy — /search-classic 의 초안 화면)은 손대지 않는다
  for (const rel of ["components/BookChat.vue", "pages/papers/index.vue", "pages/papers/[id].vue", "pages/books/[cnts_id].vue"]) {
    it(rel, () => {
      const src = read(rel);
      expect(src).toContain('import { renderMarkdown } from "~/utils/markdown";');
      expect(src).not.toContain("marked.parse(");
    });
  }
});
