// frontend/tests/unit/passageText.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { bestExcerptSentence, excerptParts, excerptSentences } from "~/utils/citationEvidence";
import { sentenceFlags } from "~/utils/figureMarkers";
import { passageText } from "~/utils/passageText";
import live from "../fixtures/live_excerpt_br.json";
import tails from "../fixtures/live_passage_tails.json";

const RAW = live.source.excerpt.text;

function read(path: string): string {
  return readFileSync(fileURLToPath(new URL(`../../${path}`, import.meta.url)), "utf8");
}

describe("passageText — 원문 대목의 <br> 태그 글자를 줄바꿈으로", () => {
  it("<br>·<br/>·<br /> 를 대소문자 없이 줄바꿈 하나로 바꾼다", () => {
    expect(passageText("가<br>나<br/>다<br />라<BR>마<Br/>바<bR  />사")).toBe("가\n나\n다\n라\n마\n바\n사");
  });

  it("<br><br> 는 빈 줄 하나(문단 사이)다 — 셋 이상 이어지면 빈 줄 하나로 줄인다", () => {
    expect(passageText("요한다.<br><br>한편")).toBe("요한다.\n\n한편");
    expect(passageText("표<br><br><br><br><br><br>|")).toBe("표\n\n|");
    // 원래 있던 줄바꿈과 섞여도, 사이에 공백이 끼어도 빈 줄 하나다
    expect(passageText("가\n<br> <br>\n나")).toBe("가\n\n나");
  });

  it("태그가 없으면 글을 그대로 둔다 — 앞뒤 공백도 남긴다(excerptParts 의 조각이 대목 글자를 빼지 않는다)", () => {
    expect(passageText("연구 대상은 농촌 노인 300명이다.  배우자 유무는 차이가 없었다!")).toBe(
      "연구 대상은 농촌 노인 300명이다.  배우자 유무는 차이가 없었다!",
    );
    expect(passageText("  [표]\n본문<br>")).toBe("  [표]\n본문\n");
    expect(passageText("")).toBe("");
    expect(passageText(null)).toBe("");
    expect(passageText(undefined)).toBe("");
  });

  it("줄 머리의 마크다운 제목 표시(#~######)는 떼고 제목 글만 둔다 — <br> 뒤 줄도, 줄 가운데 # 는 그대로", () => {
    expect(passageText("#### 5. 결론\n본문이다.")).toBe("5. 결론\n본문이다.");
    expect(passageText("표 끝<br><br>###### Figure 1. 연구 모형")).toBe("표 끝\n\nFigure 1. 연구 모형");
    expect(passageText("  ## 서론")).toBe("서론");
    expect(passageText("####\n본문")).toBe("\n본문");
    expect(passageText("C# 언어와 #해시태그, 1#2")).toBe("C# 언어와 #해시태그, 1#2");
    expect(passageText("####### 일곱 개는 제목이 아니다")).toBe("####### 일곱 개는 제목이 아니다");
  });

  it("저장된 HTML 엔티티를 글자로 푼다 — &amp; 는 한 번만(두 번 풀지 않는다)", () => {
    expect(passageText("&lt;Abstract&gt; 본문 &lt;표 1&gt; A &amp; B")).toBe("<Abstract> 본문 <표 1> A & B");
    expect(passageText("&quot;인용&quot; &#39;작은&#39; &#x27;x&#x27; &apos;y&apos;")).toBe("\"인용\" '작은' 'x' 'y'");
    expect(passageText("&amp;lt;그대로&amp;gt;")).toBe("&lt;그대로&gt;");
    expect(passageText("&LT;대문자&GT;")).toBe("<대문자>");
    // 엔티티로 적힌 <br> 도 줄바꿈이 된다
    expect(passageText("가&lt;br&gt;나")).toBe("가\n나");
  });

  it("마크다운 표는 구분줄을 지우고 칸을 ' · ' 로 이어 편다 — 세로선이 하나뿐인 글은 그대로", () => {
    expect(passageText("|연도|기초연구|응용연구|<br>|---|---|---|<br>|2019|10|20|")).toBe("연도 · 기초연구 · 응용연구\n\n2019 · 10 · 20");
    expect(passageText("| 구분 | 값 |\n| :--- | ---: |\n| A | 1 |")).toBe("구분 · 값\n\nA · 1");
    expect(passageText("앞 문장 |---|---| 뒤 문장")).toBe("앞 문장  뒤 문장");
    expect(passageText("A | B 는 그대로")).toBe("A | B 는 그대로");
  });

  it("줄 가운데에 붙은 제목 표시(##~######)도 뗀다 — 'C#'·'#태그'·'#' 하나는 그대로", () => {
    expect(passageText("결과를 보였다. #### 4. 논의 이어서")).toBe("결과를 보였다. 4. 논의 이어서");
    expect(passageText("C# 과 #태그 와 # 하나")).toBe("C# 과 #태그 와 # 하나");
  });

  it("다른 태그 꼴은 글자 그대로 둔다 — HTML 로 읽지 않는다", () => {
    expect(passageText("<b>굵게</b> <script>x</script> <brx>")).toBe("<b>굵게</b> <script>x</script> <brx>");
  });

  it("두 번 정리해도 같다", () => {
    const once = passageText(RAW);
    expect(passageText(once)).toBe(once);
  });

  it("운영 대목(GET …/sections/prior.g1/sources 의 E1)에서 태그 글자가 모두 줄바꿈이 된다", () => {
    expect(RAW).toContain("<br><br>");
    const text = passageText(RAW);
    expect(text).not.toMatch(/<br/i);
    expect(text).toContain("더욱 주의깊은 관리를 요한다.\n\n한편, 노년기에 있어서");
    expect(text).toContain("관계망의 크기가 축소하여\n\n노인들의 사회적 고립이");
  });
});

describe("운영 대목 넷(노인 연구 c816c7b2, 2026-10-15) — 표 칸 속 <br>·첫 쪽 머리말·참고문헌 꼬리", () => {
  it("자료는 운영 응답 그대로다(글자 수)", () => {
    expect([tails.E2.text.length, tails.E4.text.length, tails.E20.text.length, tails.E21.text.length]).toEqual([1435, 212, 623, 1290]);
  });

  it("E21 — 칸 속에 <br> 이 든 표 행은 칸 속 <br> 을 띄어쓰기로 바꿔 한 줄로 편다('|' 조각이 남지 않는다)", () => {
    const text = passageText(tails.E21.text);
    expect(text).not.toContain("|");
    // 빈 칸은 '–' 로 남긴다 — 버리면 Model 1 칸이 빈 행의 값이 한 칸씩 당겨져 읽혔다(2026-10-15 운영 확인)
    expect(text).toContain("변 수 · – · Model 1 B (S.E) β · Model 2 B (S.E.) β · Model 3 B (S.E.) β · Model 4 B (S.E.) β");
    expect(text).toContain("인구 학적 특성 · 성별 연령 · 5.761 (.767) .199*** .134 (.045) .079** · 3.615 (.815) .125*** .033 (.046) .019 · ");
    expect(text).toContain("사회 경제적 특성 · 교육 소득 · – · -.307 (.069) -.131***");
    expect(text).toContain("사회적 지지망 · 가족 관계 만족도 · – · – · – · -.610 (.056) -.305***");
    // 적재가 표 청크 맨 앞에 붙인 '[표]' 표시는 떼고 표 앞 본문부터, 표 행은 행마다 한 줄
    expect(text.startsWith("적 지지에 대한 만족도가")).toBe(true);
    expect(text.split("\n").filter((l) => l.includes(" · "))).toHaveLength(6);
  });

  it("칸 속 <br> 만 띄어쓰기다 — 행 사이 <br>·표 밖 <br> 은 전처럼 줄바꿈", () => {
    expect(passageText("|구분|값<br>(%)|<br>|---|---|<br>|A|1<br>2|")).toBe("구분 · 값 (%)\n\nA · 1 2");
    expect(passageText("[표]<br>|가|나|<br>본문")).toBe("[표]\n가 · 나\n본문");
  });

  it("표 칸 — 값 사이의 빈 칸은 '–', 앞뒤의 빈 칸은 버리고, 칸이 모두 비면 빈 줄", () => {
    expect(passageText("| |값| |합계| | |")).toBe("값 · – · 합계");
    expect(passageText("|성별| | |.017|")).toBe("성별 · – · – · .017");
    expect(passageText("| | | |")).toBe("");
    // '[표]' 표시는 적재가 맨 앞에 붙인 꼴('[표]\\n')만 뗀다 — 가운데·띄어 쓴 꼴은 그대로
    expect(passageText("[표]\n|가|나|")).toBe("가 · 나");
    expect(passageText("본문\n[표]\n|가|나|")).toBe("본문\n[표]\n가 · 나");
  });

  it("E2 — 대목 맨 앞의 학술지 머리말(❙ 쪽수)·DOI 줄과 첫 쪽의 제목·저자·소속 줄을 걷고 '요 약'부터 보인다", () => {
    const text = passageText(tails.E2.text);
    expect(text.startsWith("요 약 본 연구는 지역사회 노인의 우울과 건강증진행위와의 관계에서")).toBe(true);
    expect(text).not.toContain("❙");
    expect(text).not.toContain("doi.org");
    expect(text).not.toContain("Chodang University");
  });

  it("첫 쪽 앞머리 — 머리말을 걷은 첫 쪽 대목에서만, 짧은 줄 몇 개 뒤에 초록 머리가 올 때만 그 앞을 걷는다", () => {
    const first = "https://doi.org/10.1/x\n\n노인 우울 연구\n\n김철수\n\n○○대학교\n\n초 록 본 연구는 노인을 다룬다.";
    expect(passageText(first)).toBe("초 록 본 연구는 노인을 다룬다.");
    expect(passageText("Journal of X❙ 1\n\nTitle\n\nKim\n\nAbstract This study examines aging.")).toBe("Abstract This study examines aging.");
    // 머리말이 없는(첫 쪽이 아닌) 대목·초록 머리 앞에 긴 본문 줄이 있는 대목은 그대로
    expect(passageText("노인 우울 연구\n\n김철수\n\n요 약 본 연구는")).toBe("노인 우울 연구\n\n김철수\n\n요 약 본 연구는");
    const long = `https://doi.org/10.1/x\n\n${"가".repeat(220)}\n\n요 약 본 연구는`;
    expect(passageText(long)).toBe(`${"가".repeat(220)}\n\n요 약 본 연구는`);
    // '요약하면'·'Abstract concepts' 처럼 낱말이 붙은 것은 머리가 아니다
    expect(passageText("https://doi.org/10.1/x\n\n제목\n\n요약하면 이렇다.")).toBe("제목\n\n요약하면 이렇다.");
  });

  it("머리말 꼴 — 쪽수 ❙ 학술지·DOI·ISSN·Vol. No. 줄이 맨 앞에 이어지면 모두 걷는다. 가운데의 같은 꼴·본문만 남는 경우는 그대로", () => {
    expect(passageText("412 ❙ 한국콘텐츠학회논문지 '17 Vol. 17 No. 9\nhttp://dx.doi.org/10.5392/JKCA.2017.17.09.412\npISSN 1598-4877\n\n본문이다.")).toBe("본문이다.");
    expect(passageText("Journal of the Korea Academia Vol. 18, No. 3 pp. 120-128, 2017\nDOI: 10.5762/KAIS.2017.18.3.120\n본문")).toBe("본문");
    // 머리말이 맨 앞이 아니면 손대지 않는다
    expect(passageText("본문이다.\nhttps://doi.org/10.1/x\n이어서")).toBe("본문이다.\nhttps://doi.org/10.1/x\n이어서");
    // 머리말뿐이면 지우지 않는다(빈 대목을 보이지 않게)
    expect(passageText("https://doi.org/10.14400/JDC.2017.15.9.397")).toBe("https://doi.org/10.14400/JDC.2017.15.9.397");
  });

  it("E4·E20 — 본문 뒤 '참고문헌' 머리에 서지 항목이 이으면 머리부터 잘라 본문만 보인다", () => {
    expect(passageText(tails.E4.text)).toMatch(/실험연구를 수행할 필요를 느낀다\.$/);
    expect(passageText(tails.E20.text)).toMatch(/연구의 필요성을 시사한다\.$/);
  });

  it("참고문헌 머리 꼴 — 이름(연도)·여러 저자 (연도)·영문 References·번호 [1], 머리 뒤 공백·줄바꿈 여럿", () => {
    expect(passageText("결론이다. 참고문헌 김철수 외(2010). 제목.")).toBe("결론이다.");
    expect(passageText("결론이다.\n\nReferences\n\nSmith, J. (2010). Title.")).toBe("결론이다.");
    expect(passageText("결론이다. REFERENCES Kim, H. & Lee, S. (2019).")).toBe("결론이다.");
    expect(passageText("결론이다.\n참 고 문 헌\n[1] 김철수, 「노인 우울」, 2010.")).toBe("결론이다.");
    expect(passageText("결론이다. 참고문헌:\n\n\n  박미진(2007a). 제목.")).toBe("결론이다.");
  });

  it("번호 붙은 머리('Ⅵ. 참고문헌'·'6. References')는 번호까지 자른다 — 끝에 번호만 남지 않게", () => {
    expect(passageText("결론이다.\n\nⅥ. 참고문헌\n\n김철수(2010). 제목.")).toBe("결론이다.");
    expect(passageText("conclusion.\n\n6. References\n\nSmith, J. (2010). Title.")).toBe("conclusion.");
    expect(passageText("결론이다.\n\n#### 5. 참고문헌\n\n김철수(2010). 제목.")).toBe("결론이다.");
  });

  it("본문 속 '참고문헌' 낱말은 자르지 않는다 — 머리 뒤가 서지 항목이 아니거나 대목이 머리로 시작하면 그대로", () => {
    for (const s of [
      "참고문헌 분석에 관한 연구(2010)는 인용 행태를 다뤘다.",
      "본 연구는 학위논문의 참고문헌 인용 정확성을 분석하였다. 참고문헌 오류율은 12%였다.",
      "이용자는 References 목록을 확인했다.",
      "참고문헌\n\n고문희(2008), 「노인우울증」, 석사학위논문.",
      // 검증에서 잘리던 본문(2026-10-15) — 머리는 줄 머리·문장 끝 뒤에만, 연도 괄호 뒤에는 서지 부호(.,:)가, '[1]' 은 줄을 바꾼 뒤에만
      "본 연구는 시스템을 설계하였다. 참고문헌 [1]에서 제안한 방법을 따랐다.",
      "We follow prior work. Reference [1] proposed a hybrid model.",
      "학위논문의 구성 요소를 살펴본다.\n\n3.4 참고문헌\n\n이명희(2010)는 학위논문 참고문헌의 정확성을 분석하였다.",
      "본 연구는 KCI 참고문헌 DB(2020)를 이용하여 분석하였다.",
      "연구자들은 EndNote 와 Reference Manager (2012) 를 썼다.",
      "이 연구는 학위논문의 참고문헌 분석(2019)을 바탕으로 인용 행태를 살폈다. 그 결과 오류가 많았다.",
      "본 연구는 참고문헌 김철수(2010)의 틀을 따른다.",
      "선행연구로는 참고문헌 분석(2010)과 인용 분석이 있다. 이들은 학위논문의 인용 행태를 다루었다.",
      "이 도구는 References Manager (2010) 와 같은 기능을 제공한다.",
    ]) {
      expect(passageText(s)).toBe(s);
    }
  });

  it("쪽이 바뀌는 자리의 머리말(쪽수 ❙ 학술지 줄과 그 위 '|' 머리 제목 줄, 세로선만 남은 줄)은 대목 가운데서도 걷는다", () => {
    expect([tails.E2_0006.text.length, tails.E2_0016.text.length]).toEqual([1314, 1471]);
    const odd = passageText(tails.E2_0006.text);
    expect(odd).not.toMatch(/❙|\||Moderating Effects of Interpersonal/);
    expect(odd).toContain("노인우울과 건강증진행위\n\n간의 관계에 있어 사회적 지지와");
    const even = passageText(tails.E2_0016.text);
    expect(even).not.toMatch(/❙|\||404 /);
    expect(even).toContain("기초자료를 제시\n\n하였다는 데에 그 의의가 있다.");
    // 같은 대목 끝의 'REFERENCES\n\n[1] …' 목록은 꼬리로 잘린다
    expect(even).toMatch(/지지체계가 마 련되고 시행될 필요가 있다\.$/);
  });

  it("쪽 머리말 꼴 — '❙' 와 쪽수가 붙은 줄만, '|' 제목 줄은 그 바로 위일 때만 걷는다. 머리말뿐인 대목은 그대로", () => {
    expect(passageText("앞 문장이다.\n\n|논문 제목\n\nJournal of X❙ 12\n\n뒤 문장이다.")).toBe("앞 문장이다.\n\n뒤 문장이다.");
    // ❙ 없는 '|' 줄·쪽수 없는 ❙ 줄·표 그림의 상자 선(│)은 그대로
    expect(passageText("|논문 제목\n본문이다.")).toBe("|논문 제목\n본문이다.");
    expect(passageText("구분 ❙ 설명이 이어진다\n본문")).toBe("구분 ❙ 설명이 이어진다\n본문");
    expect(passageText("본문\n합계 │ 120\n끝")).toBe("본문\n합계 │ 120\n끝");
    expect(passageText("Journal of X❙ 12")).toBe("Journal of X❙ 12");
  });

  it("넷 모두 두 번 정리해도 같다", () => {
    for (const t of [tails.E2.text, tails.E2_0006.text, tails.E2_0016.text, tails.E4.text, tails.E20.text, tails.E21.text]) {
      const once = passageText(t);
      expect(passageText(once)).toBe(once);
    }
  });
});

describe("인용 근거 하이라이트는 정리한 글로 잰다", () => {
  const cited = sentenceFlags(live.paragraph)[1]!.text;

  it("문장 나누기 — <br><br> 뒤에서도 문장이 나뉜다(태그 글자가 남은 문장이 없다)", () => {
    const sentences = excerptSentences(RAW);
    expect(sentences.some((s) => /<br/i.test(s))).toBe(false);
    expect(sentences).toContain("한편, 노년기에 있어서 사회적 지지는 우울에 대한 부 정적 생활사건의 효과를 중재하는 요인으로 작용하며 특 히 스트레스로 인한 우울을 완충하는 효과를 나타내는 것으로 보고되고 있다[10].");
  });

  it("운영 문단의 두 번째 문장(사회적 고립 [E1])은 '노년기가 되면 …' 대목 문장을 강조한다", () => {
    expect(cited).toContain("사회적 고립이 심화될 수 있으며");
    const best = bestExcerptSentence(cited, RAW, live.eid);
    expect(best).not.toBeNull();
    expect(excerptSentences(RAW)[best!]).toMatch(/^노년기가 되면 사회적 상호작용이 줄고 관계망의 크기가 축소하여\n\n노인들의/);
  });

  it("'넘긴 원문 대목' 패널(excerptParts)은 참고문헌 꼬리를 자르지 않는다 — 모델이 받은 글 그대로 보여야 남의 참고문헌을 인용한 것이 드러난다", () => {
    const sentence = "고문희(2008)는 노인우울증과 여가활동 및 음주습관의 관계를 분석하였다 [E1].";
    const parts = excerptParts(tails.E4.text, sentence, "E1");
    const joined = parts.map((p) => p.text).join("");
    expect(joined).toBe(passageText(tails.E4.text, { keepReferences: true }));
    expect(joined).toContain("참고문헌\n\n고문희(2008),");
    expect(parts.find((p) => p.mark)?.text).toContain("고문희(2008)");
    // 다른 자리(인용 팝오버 등)는 잘린다
    expect(passageText(tails.E4.text)).not.toContain("고문희");
  });

  it("excerptParts — 조각을 이으면 정리한 글 그대로이고 강조 조각에도 태그 글자가 없다", () => {
    const parts = excerptParts(RAW, cited, live.eid);
    expect(parts.map((p) => p.text).join("")).toBe(passageText(RAW));
    const marked = parts.filter((p) => p.mark);
    expect(marked).toHaveLength(1);
    expect(marked[0]!.text.startsWith("노년기가 되면")).toBe(true);
    expect(marked[0]!.text).not.toMatch(/<br/i);
  });
});

describe("대목 글을 보여 주는 화면이 같은 정리 함수를 쓴다", () => {
  const IMPORT = /import \{ [^}]*\bpassageText\b[^}]*\} from "~\/utils\/passageText";/;
  const uses: [string, string][] = [
    ["components/work/CitationSource.vue", "passageText(source.abstract)"],
    ["components/research/CitationChip.vue", "{{ passageText(current.text) }}"],
    ["components/work/PathPopover.vue", "{{ passageText(line.chunk.text) }}"],
    ["components/work/ReadingStep.vue", "{{ passageText(panelPath.chunk.text) }}"],
    ["components/BookChat.vue", "passageText(msg.sources[msg.pinnedChip]?.text)"],
  ];

  it.each(uses)("%s", (path, call) => {
    const source = read(path);
    expect(source).toMatch(IMPORT);
    expect(source).toContain(call);
  });

  it("대목 글은 HTML 로 넣지 않는다(v-html 금지 — 답변 마크다운의 v-html 은 대목이 아니다)", () => {
    for (const [path] of uses) expect(read(path)).not.toMatch(/v-html="[^"]*\.(?:text|abstract)\b[^"]*"/);
  });

  it("줄바꿈이 보이게 — 칩 팝오버·경로 대목은 white-space: pre-line", () => {
    const research = read("assets/css/research.css");
    const work = read("assets/css/work.css");
    expect(research).toMatch(/\.rs-cite__quote \{[^}]*white-space: pre-line;/);
    expect(work).toMatch(/\.wk-path__quote \{[^}]*white-space: pre-line;/);
  });
});
