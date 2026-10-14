// frontend/utils/passageText.ts
// 원문 대목(청크 글)을 화면에 보일 글로 정리한다. 적재(ODL 마크다운)가 표 칸·문단 사이 줄바꿈을 <br> 태그 글자로 남겨
// (services/ingestion/page_routing.py — 표 행이 쪼개지지 않게 일부러 둔다) 그대로 그리면 '<br><br>' 가 글자로 보인다.
// HTML 로 넣지 않고(v-html 금지 — 대목은 원문 그대로라 무엇이 들었는지 모른다) 줄바꿈 글자로 바꾼다 — 보이는 자리는
// white-space: pre-line·pre-wrap 이라 줄이 나뉜다. <br> 말고 다른 태그 꼴은 글자 그대로 둔다
const BR_TAG = /<br\s*\/?>/gi;
// 빈 줄이 이어지면(표 칸 끝의 <br> 연속, 사이에 낀 공백·탭 포함) 빈 줄 하나로 접는다
const BLANK_RUN = /\n(?:[ \t]*\n)+/g;

// 줄 머리의 마크다운 제목 표시('#### 5. 결론'·'###### Figure 1.' — 적재가 절 제목을 ATX 머리표로 남긴다)는 떼고 제목 글만 둔다
// (2026-10-14 운영 확인 — DeepRead 출처 미리보기에 '####' 가 글자로 보였다). 글 없이 '#' 만 있는 줄은 빈 줄이 된다.
// 대목 강조(citationEvidence.excerptSentences·excerptParts)도 이 함수로 나누므로 두 쪽의 문장 순서는 그대로 맞는다
const HEADING_MARK = /^[ \t]{0,3}#{1,6}(?:[ \t]+|$)/gm;
// 줄 가운데에 붙은 제목 표시(줄바꿈이 빠져 '… 결과 #### 4. 논의' 처럼 이어진 것). 두 개 이상(##~######)에 뒤를 띄어 쓴 것만 —
// 'C#'·'#해시태그' 는 건드리지 않는다
const INLINE_HEADING = /([ \t])#{2,6}[ \t]+(?=\S)/g;
// 저장된 대목에 남은 HTML 엔티티('&lt;Abstract&gt;'·'&lt;표 1&gt;'·'&amp;') — 화면은 v-html 을 쓰지 않아 글자 그대로 보였다
// (2026-10-14 운영 확인 — 인용 팝오버 대목 32개 중 9개). 글자로 풀어도 HTML 로 읽지 않으니 안전하다. &amp; 는 마지막에 한 번만
// 푼다 — 먼저 풀면 '&amp;lt;' 가 '<' 까지 두 번 풀린다
const ENTITIES: Readonly<Record<string, string>> = {
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#39;": "'",
  "&#x27;": "'",
  "&apos;": "'",
  "&nbsp;": " ",
};
const ENTITY = /&(?:lt|gt|quot|#39|#x27|apos|nbsp);/gi;
const AMP = /&amp;/gi;
// 마크다운 표의 구분줄('|---|:---:|') — 칸 줄 사이의 선이라 지운다. 줄바꿈이 빠져 한 줄에 이어 붙은 것도 지운다
const TABLE_RULE = /\|(?:[ \t]*:?-{3,}:?[ \t]*\|)+/g;
const PIPE = /\|/g;

function decodeEntities(text: string): string {
  return text.replace(ENTITY, (m) => ENTITIES[m.toLowerCase()] ?? m).replace(AMP, "&");
}

// 표 칸 줄('|연도|기초연구|응용연구|')은 칸을 ' · ' 로 이어 한 줄 글로 편다. 세로선이 둘 이상인 줄만 — 글 속 '|' 하나는 그대로
function flattenTableRow(line: string): string {
  if ((line.match(PIPE) ?? []).length < 2) return line;
  return line
    .replace(/^[ \t]*\|/, "")
    .replace(/\|[ \t]*$/, "")
    .split("|")
    .map((c) => c.trim())
    .filter(Boolean)
    .join(" · ");
}

export function passageText(text: string | null | undefined): string {
  return decodeEntities(text ?? "")
    .replace(BR_TAG, "\n")
    .replace(TABLE_RULE, "")
    .split("\n")
    .map(flattenTableRow)
    .join("\n")
    .replace(HEADING_MARK, "")
    .replace(INLINE_HEADING, "$1")
    .replace(BLANK_RUN, "\n\n");
}
