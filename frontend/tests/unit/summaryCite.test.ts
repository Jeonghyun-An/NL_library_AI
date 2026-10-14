// frontend/tests/unit/summaryCite.test.ts
import { describe, expect, it } from "vitest";
import { CITE_CLASS, citeLabel, citeYear, linkCitations, parseCiteNumbers } from "~/utils/summaryCite";

const refs = [
  { num: 1, title: "노인 우울과 사회적 지지" },
  { num: 2, title: "다문화 아동의 언어 발달" },
  { num: 3, title: "공공도서관 서비스 품질" },
];

/** 결과 HTML 에서 버튼의 번호와 글자만 뽑는다 */
function buttons(html: string): string[] {
  return [...html.matchAll(/<button[^>]*data-cite="(\d+)"[^>]*>([^<]*)<\/button>/g)].map((m) => `${m[1]}:${m[2]}`);
}

describe("parseCiteNumbers", () => {
  it("묶음 글에서 번호를 차례로 뽑는다", () => {
    expect(parseCiteNumbers("(1)")).toEqual([1]);
    expect(parseCiteNumbers("(1, 3)")).toEqual([1, 3]);
    expect(parseCiteNumbers("( 2 ,4,  5 )")).toEqual([2, 4, 5]);
  });

  it("글이 아닌 것에는 빈 목록", () => {
    expect(parseCiteNumbers("")).toEqual([]);
    expect(parseCiteNumbers("(가)")).toEqual([]);
  });
});

describe("linkCitations — 번호를 버튼으로", () => {
  it("(1) 의 번호가 버튼이 되고 괄호는 글 그대로다", () => {
    const out = linkCitations("<p>공통된 결과입니다 (1).</p>", refs);
    expect(buttons(out)).toEqual(["1:1"]);
    expect(out).toContain("(<button");
    expect(out).toContain("</button>).</p>");
  });

  it("(1, 3) 은 번호마다 따로 버튼이고 쉼표·공백은 글 그대로다", () => {
    const out = linkCitations("<p>근거 (1, 3) 입니다</p>", refs);
    expect(buttons(out)).toEqual(["1:1", "3:3"]);
    expect(out).toMatch(/<\/button>, <button/);
  });

  it("공백 없는 (1,3)·여러 묶음도 같다", () => {
    expect(buttons(linkCitations("<p>(1,3) 그리고 (2)</p>", refs))).toEqual(["1:1", "3:3", "2:2"]);
  });

  it("참고 목록 범위 밖 번호는 글자 그대로다", () => {
    expect(linkCitations("<p>다섯째 (5) 자료</p>", refs)).toBe("<p>다섯째 (5) 자료</p>");
    // 일부만 범위 안이면 그것만 버튼
    const out = linkCitations("<p>(1, 7)</p>", refs);
    expect(buttons(out)).toEqual(["1:1"]);
    expect(out).toMatch(/<\/button>, 7\)/);
  });

  it("연도·세 자리 넘는 수·0 으로 시작하는 수는 인용이 아니다", () => {
    for (const text of ["(2024)", "(1234)", "(01)", "(0)", "(1.5)", "(1 2)"]) {
      expect(linkCitations(`<p>${text}</p>`, refs)).toBe(`<p>${text}</p>`);
    }
  });

  it("참고 목록이 비면 아무것도 바꾸지 않는다", () => {
    expect(linkCitations("<p>(1)</p>", [])).toBe("<p>(1)</p>");
    expect(linkCitations("", refs)).toBe("");
  });

  it("코드·미리 서식·링크·버튼 안의 숫자는 건드리지 않는다", () => {
    const html =
      "<p><code>f(1)</code> 와 <a href=\"/x\">링크 (2)</a> 와 <button>누름 (3)</button> 그리고 (1)</p>" +
      "<pre><code>print(2)\n(3)</code></pre><p>끝 (2)</p>";
    const out = linkCitations(html, refs);
    // 보호된 곳은 그대로, 밖의 (1)·(2) 만 버튼
    expect(out).toContain("<code>f(1)</code>");
    expect(out).toContain('<a href="/x">링크 (2)</a>');
    expect(out).toContain("<button>누름 (3)</button>");
    expect(out).toContain("<pre><code>print(2)\n(3)</code></pre>");
    expect(buttons(out)).toEqual(["1:1", "2:2"]);
  });

  it("보호 태그가 닫힌 뒤에는 다시 바꾼다", () => {
    const out = linkCitations("<p><a href=\"#\">(1)</a> (1)</p>", refs);
    expect(buttons(out)).toEqual(["1:1"]);
    expect(out.startsWith('<p><a href="#">(1)</a> (')).toBe(true);
  });

  it("제목·목록·강조 안의 인용도 버튼이 된다", () => {
    const out = linkCitations("<h2>핵심 (1)</h2><ul><li><strong>결과</strong> (2)</li></ul>", refs);
    expect(buttons(out)).toEqual(["1:1", "2:2"]);
  });

  it("닫히지 않은 태그가 있어도 던지지 않는다(스트리밍 중간 글)", () => {
    expect(() => linkCitations("<p>끝나지 않은 <code>코드 (1)", refs)).not.toThrow();
    expect(linkCitations("<p>끝나지 않은 <code>코드 (1)", refs)).toBe("<p>끝나지 않은 <code>코드 (1)");
    expect(() => linkCitations("<p>열린 꺾쇠 < (1)", refs)).not.toThrow();
  });

  it("버튼에 스크린리더 이름·팝업 속성이 붙고 제목의 특수문자는 이스케이프한다", () => {
    const out = linkCitations("<p>(1)</p>", [{ num: 1, title: '"A" & <B>' }]);
    expect(out).toContain(`class="${CITE_CLASS}"`);
    expect(out).toContain('data-cite="1"');
    expect(out).toContain('aria-haspopup="dialog"');
    expect(out).toContain('aria-expanded="false"');
    expect(out).toContain('aria-label="참고 논문 1: &quot;A&quot; &amp; &lt;B&gt;"');
    // 속성 값이 이스케이프돼 버튼이 하나의 태그로 남는다
    expect(buttons(out)).toEqual(["1:1"]);
  });

  it("같은 번호가 목록에 두 번 있으면 먼저 온 것을 쓴다", () => {
    const out = linkCitations("<p>(1)</p>", [
      { num: 1, title: "처음" },
      { num: 1, title: "나중" },
    ]);
    expect(out).toContain("참고 논문 1: 처음");
    expect(out).not.toContain("나중");
  });

  it("버튼을 만든 결과에 다시 돌려도 중복으로 바꾸지 않는다", () => {
    const once = linkCitations("<p>(1) (2)</p>", refs);
    expect(linkCitations(once, refs)).toBe(once);
  });
});

describe("citeLabel · citeYear", () => {
  it("스크린리더 이름은 '참고 논문 N: 제목'", () => {
    expect(citeLabel({ num: 2, title: "다문화 아동의 언어 발달" })).toBe("참고 논문 2: 다문화 아동의 언어 발달");
  });

  it("발행일에서 연도만 읽는다", () => {
    expect(citeYear("20240115")).toBe("2024년");
    expect(citeYear("2023-07")).toBe("2023년");
    expect(citeYear("1997")).toBe("1997년");
    expect(citeYear(" 2001.03")).toBe("2001년");
  });

  it("읽을 수 없으면 빈 문자열", () => {
    expect(citeYear("")).toBe("");
    expect(citeYear(null)).toBe("");
    expect(citeYear(undefined)).toBe("");
    expect(citeYear("미상")).toBe("");
  });
});
