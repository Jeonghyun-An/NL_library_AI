// frontend/utils/summaryCite.ts
// 논문 검색 AI 요약 속 인용 번호 (1)·(1, 3) 을 누를 수 있는 버튼으로 바꾸는 순수 로직.
// 요약은 marked 로 렌더한 HTML 문자열이라, 태그와 글을 나눠 '코드·링크 밖의 글'에서만 번호를 찾는다.
// 참고 목록(sources)에 있는 번호만 버튼이 되고 범위 밖 번호는 그대로 글자로 둔다

/** 참고 논문 목록의 한 건 — 서버가 요약 끝에 주는 sources 의 번호·제목 */
export interface CiteRef {
  num: number;
  title: string;
}

/** 요약 글 속 번호가 가리키는 참고 논문 — 오른쪽 참고 목록의 한 건(서버 sources) + 연도 */
export interface SummaryRef extends CiteRef {
  book_id: string;
  authors: string;
  year: string;
}

/** 버튼 요소의 클래스 — 화면(SummaryText)이 이 이름으로 눌린 번호를 찾는다 */
export const CITE_CLASS = "skx-cite";

// 괄호 안에 쉼표로 이어진 자연수 — (1)·(1, 3)·(1,3). 앞자리 0 이 없고 세 자리까지(연도 (2024) 는 잡지 않는다)
const GROUP = /\(\s*[1-9]\d{0,2}(?:\s*[,，]\s*[1-9]\d{0,2})*\s*\)/g;
const NUMBER = /[1-9]\d{0,2}/g;
// 안에 든 글은 건드리지 않는 태그 — 코드·미리 서식·링크(이미 눌리는 것)·버튼·스크립트
const SKIP_TAGS = new Set(["code", "pre", "a", "button", "script", "style", "textarea"]);
const TOKEN = /(<!--[\s\S]*?-->|<[^>]+>)/;
const TAG_NAME = /^<\s*(\/?)\s*([a-zA-Z][\w-]*)/;

/** "(1, 3)" 같은 묶음 글에서 번호만 차례로 뽑는다 */
export function parseCiteNumbers(group: string): number[] {
  return (group.match(NUMBER) ?? []).map(Number);
}

function escapeAttr(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** 스크린리더가 읽는 이름 — '참고 논문 2: 제목' */
export function citeLabel(ref: CiteRef): string {
  return `참고 논문 ${ref.num}: ${ref.title}`;
}

function citeButton(ref: CiteRef): string {
  return (
    `<button type="button" class="${CITE_CLASS}" data-cite="${ref.num}" aria-haspopup="dialog" ` +
    `aria-expanded="false" aria-label="${escapeAttr(citeLabel(ref))}">${ref.num}</button>`
  );
}

/**
 * 렌더된 요약 HTML 에서 참고 목록에 있는 인용 번호를 버튼으로 바꾼다. 괄호·쉼표·공백은 글 그대로 두고 번호만 버튼이다 —
 * "(1, 7)" 에서 목록에 1 만 있으면 7 은 글자로 남는다. 목록에 있는 번호가 하나도 없는 묶음은 통째로 그대로 둔다.
 * <code>·<pre>·<a>·<button> 안의 글은 건드리지 않는다. 스트리밍 중간 글처럼 닫히지 않은 태그가 있어도 던지지 않는다
 */
export function linkCitations(html: string, refs: readonly CiteRef[]): string {
  if (!html || !refs.length) return html;
  const byNum = new Map<number, CiteRef>();
  for (const ref of refs) if (!byNum.has(ref.num)) byNum.set(ref.num, ref);

  let skipDepth = 0;
  return html
    .split(TOKEN)
    .map((part, i) => {
      if (i % 2 === 1) {
        // 태그·주석 — 건너뛰는 태그의 열림·닫힘만 센다
        const m = TAG_NAME.exec(part);
        const name = m?.[2]?.toLowerCase();
        if (name && SKIP_TAGS.has(name)) {
          if (m![1]) skipDepth = Math.max(0, skipDepth - 1);
          else if (!part.endsWith("/>")) skipDepth++;
        }
        return part;
      }
      if (skipDepth > 0) return part;
      return part.replace(GROUP, (group) => {
        if (!parseCiteNumbers(group).some((n) => byNum.has(n))) return group;
        return group.replace(NUMBER, (digits) => {
          const ref = byNum.get(Number(digits));
          return ref ? citeButton(ref) : digits;
        });
      });
    })
    .join("");
}

/** 발행일(20240115·2024-01·2024)에서 연도만 — "2024년". 읽을 수 없으면 빈 문자열 */
export function citeYear(pubDate: string | null | undefined): string {
  const m = /^\s*(\d{4})/.exec(pubDate ?? "");
  return m ? `${m[1]}년` : "";
}
