// frontend/tests/unit/helpers/cssRules.ts
// research.css 의 규칙 — 선택자(쉼표로 나눔)·감싼 @규칙(@media 등)·선언. 이 파일은 CSS 중첩·중괄호가 든 글자를 쓰지 않는다
export interface CssRule {
  at: string;
  selectors: string[];
  decls: Map<string, string>;
}

export function cssRules(css: string): CssRule[] {
  const src = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const squash = (s: string) => s.replace(/\s+/g, " ").trim();
  const rules: CssRule[] = [];
  const heads: string[] = [];
  let buf = "";
  for (const ch of src) {
    if (ch === "{") {
      heads.push(squash(buf));
      buf = "";
    } else if (ch === "}") {
      const head = heads.pop() ?? "";
      if (!head.startsWith("@") && buf.trim()) {
        const decls = new Map<string, string>();
        for (const d of buf.split(";")) {
          const colon = d.indexOf(":");
          if (colon > 0) decls.set(d.slice(0, colon).trim(), squash(d.slice(colon + 1)));
        }
        rules.push({ at: heads.filter((h) => h.startsWith("@")).join(" "), selectors: head.split(",").map(squash), decls });
      }
      buf = "";
    } else {
      buf += ch;
    }
  }
  return rules;
}
