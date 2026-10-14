// frontend/tests/unit/passageText.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { bestExcerptSentence, excerptParts, excerptSentences } from "~/utils/citationEvidence";
import { sentenceFlags } from "~/utils/figureMarkers";
import { passageText } from "~/utils/passageText";
import live from "../fixtures/live_excerpt_br.json";

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
