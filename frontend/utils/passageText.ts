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
// 표 행 사이의 <br>('|…|<br>|…|' — 행 끝 세로선과 다음 행 첫 세로선 사이)은 행을 가르는 줄바꿈이다. 칸 속 <br> 과 가르려고
// 먼저 줄바꿈으로 바꾼다
const ROW_BREAK = /\|[ \t]*(?:<br\s*\/?>[ \t]*)+(?=\|)/gi;
// 한 줄이 통째로 표 행('|'로 시작해 '|'로 끝나고 칸이 둘 이상)이면 그 안의 <br> 은 칸 속 줄바꿈이다 — 띄어쓰기로 바꿔 행을 한 줄로
// 편다. 먼저 줄바꿈으로 바꾸면 칸 하나가 여러 줄로 쪼개져 'β|Model 2' 같은 세로선 조각이 남았다(2026-10-15 운영 확인 — 표 행은
// 실제 줄바꿈으로 나뉘고 <br> 은 칸 속에만 있다)
const TABLE_ROW_LINE = /^[ \t]*\|.*\|[ \t]*$/;
const CELL_BREAK = /(?:[ \t]*<br\s*\/?>[ \t]*)+/gi;

// 대목 맨 앞의 학술지 머리말 줄 — 첫 쪽 청크가 '|Journal of Digital Convergence❙ 397'·'https://doi.org/…' 로 시작했다
// (2026-10-15 운영 확인). 맨 앞에 이어진 것만 걷는다(본문 가운데의 같은 꼴은 그대로). 쪽수 머리말의 구분 기호는 ❙·│ 만 —
// 표 칸의 '|' 와 섞이지 않게
const MASTHEAD: readonly RegExp[] = [
  /^\|?[ \t]*(?:\d{1,4}[ \t]*[❙│][^\n]{1,120}|[^\n]{1,120}?[❙│][ \t]*\d{1,4})[ \t]*$/,
  /^[ \t]*(?:https?:\/\/(?:dx\.)?doi\.org\/\S+|DOI[ \t]*:?[ \t]*10\.\d{4,9}\/\S+)[ \t]*$/i,
  /^[ \t]*[pe]?-?ISSN[ \t]*:?[ \t]*\d{4}-\d{3}[\dXx][^\n]{0,60}$/i,
  /^[^\n]{0,100}\bVol\.?[ \t]*\d+[^\n]{0,40}\bNo\.?[ \t]*\d+[^\n]{0,60}$/i,
];

// 쪽이 바뀌는 자리의 머리말 — 대목 가운데에 '…<br><br>| |---|\n\n|(논문 제목)<br><br>Journal of Digital Convergence❙ 399<br><br>…'
// 꼴로 끼어 있었다(2026-10-15 운영 확인, 홀수 쪽은 영문 제목·짝수 쪽은 국문 제목 + '404 ❙Journal of … 397-406'). 쪽수와 ❙ 가
// 붙은 줄을 대목 어디서든 걷고, 그 바로 위(빈 줄 건너)의 '|'로 시작하는 머리 제목 줄과 그 위의 세로선만 남은 줄도 함께 걷는다.
// 구분 기호는 ❙ 만 — 표 그림의 상자 선(│)·표 칸의 '|' 와 섞이지 않게
const RUNNING_HEAD = /^\|?[ \t]*(?:\d{1,4}[ \t]*❙[^\n]{1,120}|[^\n]{1,120}?❙[ \t]*\d{1,4})[ \t]*$/;
const HEAD_TITLE = /^[ \t]*\|[^|]*\S[^|]*$/;
const PIPES_ONLY = /^[ \t]*\|[ \t|]*$/;

// 본문 뒤에 붙은 참고문헌 목록 — '…필요를 느낀다. 참고문헌\n\n고문희(2008), …'(2026-10-15 운영 확인). 도서관학 논문 본문에
// 흔한 '참고문헌 분석(2019)을'·'참고문헌 [1]에서'·'Reference service' 같은 말은 자르지 않는다. 그래서 셋을 다 따진다:
//  - 머리 자리: 대목 맨 앞·줄 머리(절 번호 'Ⅵ.'·'6.'·'5.1' 이 앞서면 번호까지 자른다)·문장 끝(.!?) 뒤 띄어쓰기. 단수 'Reference' 는 아니다
//  - 서지 항목: 이름(연도)·이름, 이름 (연도)·Surname (연도) 은 연도 괄호 뒤에 서지 부호(.,:)가 와야 한다 — 본문의 '분석(2019)을'·
//    '김철수(2010)의' 는 아니다. 'Surname, A.' 은 그대로
//  - 번호 목록 '[1]' 은 머리 뒤에서 줄을 바꾼 때만
// 대소문자를 가리는 것은 영문 성(대문자 시작)을 알아보기 위해서다
const REF_HEAD = "(?:참[ \\t]?고[ \\t]?문[ \\t]?헌|References|REFERENCES|Bibliography|BIBLIOGRAPHY)";
const REF_LEAD =
  "(?:(?:^|\\n)[ \\t]*(?:(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+|[IVX]{1,4}|\\d{1,2}(?:\\.\\d{1,2})*)\\.?[ \\t]+)?|(?<=[.!?。])[ \\t]+)";
const YEAR_PAREN = "\\([ \\t]*(?:19|20)\\d{2}[a-z]?[ \\t]*\\)[ \\t]*[.,:]";
const REF_ENTRY =
  `(?:[가-힣]{2,5}(?:[ \\t]*[,·ㆍ][ \\t]*[가-힣]{2,5})*(?:[ \\t]*외)?[ \\t]*${YEAR_PAREN}` +
  "|[A-Z][A-Za-z'’-]+,[ \\t]*[A-Z]\\." +
  `|[A-Z][A-Za-z'’-]+[ \\t]*${YEAR_PAREN})`;
const REF_TAIL = new RegExp(
  `${REF_LEAD}${REF_HEAD}[ \\t]*:?[ \\t]*(?:(?:\\n[ \\t]*)+(?=${REF_ENTRY}|\\[[ \\t]*1[ \\t]*\\])|(?=${REF_ENTRY}))`,
);

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

// 통째로 표 행인 줄만 칸 속 <br> 을 띄어쓰기로 바꿔 편다. 표 밖 글·'[표]<br>|가|나|' 처럼 글과 이어진 행은 그대로 두고
// <br> 을 줄바꿈으로 바꾼 뒤에 편다(전과 같다)
function flattenCellBreaks(line: string): string {
  if (!TABLE_ROW_LINE.test(line) || (line.match(PIPE) ?? []).length < 3) return line;
  return flattenTableRow(line.replace(CELL_BREAK, " "));
}

// 쪽 머리말 줄을 대목 어디서든 걷는다(RUNNING_HEAD 와 그 위의 '|' 제목 줄·세로선 줄). 남는 빈 줄은 뒤의 BLANK_RUN 이 접는다.
// 걷고 나니 글이 없으면 그대로, 맨 앞이 비면 첫 글 줄부터
function dropPageHeads(text: string): string {
  const lines = text.split("\n");
  const drop = new Set<number>();
  const above = (from: number): number => {
    let j = from;
    while (j >= 0 && (!lines[j]!.trim() || drop.has(j))) j--;
    return j;
  };
  lines.forEach((line, i) => {
    if (!RUNNING_HEAD.test(line)) return;
    drop.add(i);
    let j = above(i - 1);
    if (j >= 0 && HEAD_TITLE.test(lines[j]!)) {
      drop.add(j);
      j = above(j - 1);
    }
    while (j >= 0 && PIPES_ONLY.test(lines[j]!)) {
      drop.add(j);
      j = above(j - 1);
    }
  });
  if (!drop.size) return text;
  const kept = lines.filter((_, i) => !drop.has(i));
  const first = kept.findIndex((l) => l.trim());
  return first < 0 ? text : kept.slice(first).join("\n");
}

// 맨 앞에 이어진 머리말 줄(사이의 빈 줄 포함)을 걷는다. 걷을 것이 없거나 머리말만 남는 대목은 그대로 — 빈 대목을 보이지 않게
function dropLeadingMasthead(text: string): string {
  const lines = text.split("\n");
  let i = 0;
  let dropped = false;
  while (i < lines.length) {
    const line = lines[i]!;
    if (line.trim() && !MASTHEAD.some((re) => re.test(line))) break;
    if (line.trim()) dropped = true;
    i++;
  }
  return dropped && i < lines.length ? lines.slice(i).join("\n") : text;
}

// 참고문헌 머리부터 끝까지 자른다. 대목이 머리로 시작하면(본문이 없으면) 그대로
function cutReferenceTail(text: string): string {
  const m = REF_TAIL.exec(text);
  if (!m) return text;
  const body = text.slice(0, m.index).trimEnd();
  return body ? body : text;
}

export interface PassageTextOptions {
  /** 참고문헌 꼬리를 자르지 않는다 — '이 문장을 쓸 때 넘긴 원문 대목' 패널(citationEvidence)은 모델이 받은 글을 그대로 보여야
   *  남의 참고문헌 목록에서 인용한 것이 드러난다(서버는 통째로 참고문헌인 대목만 거르고 꼬리 달린 본문 대목은 모델에 넘긴다) */
  keepReferences?: boolean;
}

export function passageText(text: string | null | undefined, options: PassageTextOptions = {}): string {
  const tidy = decodeEntities(text ?? "")
    .replace(ROW_BREAK, "|\n")
    .replace(TABLE_RULE, "")
    .split("\n")
    .map(flattenCellBreaks)
    .join("\n")
    .replace(BR_TAG, "\n")
    .split("\n")
    .map(flattenTableRow)
    .join("\n")
    .replace(HEADING_MARK, "")
    .replace(INLINE_HEADING, "$1");
  const body = dropLeadingMasthead(dropPageHeads(tidy).replace(BLANK_RUN, "\n\n"));
  return options.keepReferences ? body : cutReferenceTail(body);
}
