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

export function passageText(text: string | null | undefined): string {
  return (text ?? "").replace(BR_TAG, "\n").replace(HEADING_MARK, "").replace(BLANK_RUN, "\n\n");
}
