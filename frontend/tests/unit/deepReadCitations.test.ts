// frontend/tests/unit/deepReadCitations.test.ts
// DeepRead 답의 근거 표시(2026-10-23) — 글 속 쪽 표기를 누를 수 있는 쪽 번호로, 출처 대목을 같은 쪽끼리 묶은 '근거 N곳' 목록으로.
// 2026-10-23 운영 화면: 답 글에 '[p.2, p.19]'·'[쪽 정보 없음]'이 글자로 찍히고 아래 칩이 'p.2 p.19 p.19' 였다
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { marked } from "marked";
import { groupForPages, groupSources, renderAnswer, type SourceGroup } from "~/utils/deepReadCitations";
import type { DeepReadSource } from "~/utils/deepReadSse";

// 저장값은 0부터 센다 — 사람이 보는 쪽은 +1(page_start 2 → p.3)
const src = (start: number, end: number, text: string): DeepReadSource => ({ page_start: start, page_end: end, text });

describe("groupSources — 같은 쪽 대목을 한 줄로", () => {
  // 운영 화면의 답과 출처: p.2 한 대목, p.19 두 대목
  const sources = [src(1, 1, "p2 대목"), src(18, 18, "측정도구 대목"), src(18, 18, "신뢰도 대목")];
  const answer = "프로그램 개발의 필요성을 강조합니다 [p.2, p.19]. 측정도구는 … [p.19].";

  it("같은 쪽 표기의 대목은 한 묶음이고 대목 순서는 받은 그대로다", () => {
    const groups = groupSources(sources, answer);
    expect(groups.map((g) => g.label)).toEqual(["p.2", "p.19"]);
    expect(groups[1]!.passages.map((p) => p.text)).toEqual(["측정도구 대목", "신뢰도 대목"]);
    expect(groups[1]).toMatchObject({ start: 19, end: 19 });
  });

  it("답 글에서 먼저 언급한 쪽이 위로 — 언급을 찾지 못한 묶음은 그 뒤에 쪽 순서로", () => {
    const groups = groupSources(
      [src(2, 2, "p3"), src(24, 24, "p25"), src(9, 9, "p10"), src(4, 4, "p5")],
      "28편에서 효과가 있었어요 [p.25]. 30편을 골랐어요 (p.3).",
    );
    expect(groups.map((g) => g.label)).toEqual(["p.25", "p.3", "p.5", "p.10"]);
  });

  it("코드 칸 안의 쪽 표기는 언급 순서에 세지 않는다", () => {
    const groups = groupSources([src(2, 2, "p3"), src(24, 24, "p25")], "예: `p.25` 처럼 써요. 30편을 골랐어요 [p.3].");
    expect(groups.map((g) => g.label)).toEqual(["p.3", "p.25"]);
  });

  it("범위 대목(p.3–4)과 한 쪽 대목(p.3)은 다른 줄이다", () => {
    const groups = groupSources([src(2, 3, "범위"), src(2, 2, "한 쪽")], "[p.3–4] 그리고 [p.3]");
    expect(groups.map((g) => g.label)).toEqual(["p.3–4", "p.3"]);
  });

  it("쪽 정보 없는 대목(저장값 0)은 목록에 넣지 않는다", () => {
    expect(groupSources([src(0, 0, "첫 쪽?"), src(5, 5, "p6")], "").map((g) => g.label)).toEqual(["p.6"]);
  });

  it("sources 가 없으면 빈 목록", () => {
    expect(groupSources(undefined, "[p.3]")).toEqual([]);
  });

  it("줄 머리 글은 대목을 화면 글로 정리해 한 줄로(제목 표시·<br>·겹친 공백 없이), 길면 120자에서 자른다", () => {
    const [g] = groupSources([src(4, 4, "#### 3. 연구 결과<br><br>국내   278편,\n국외 79편")], "");
    expect(g!.snippet).toBe("3. 연구 결과 국내 278편, 국외 79편");
    const [long] = groupSources([src(4, 4, "가".repeat(200))], "");
    expect(long!.snippet).toBe(`${"가".repeat(120)}…`);
  });
});

describe("groupForPages — 글 속 쪽 표기가 가리키는 묶음", () => {
  const groups = groupSources([src(2, 3, "범위"), src(2, 2, "한 쪽"), src(10, 12, "긴 범위")], "");
  const at = (label: string) => groups.findIndex((g: SourceGroup) => g.label === label);

  it("같은 표기가 먼저 — p.3 은 p.3 줄, p.3–4 는 p.3–4 줄", () => {
    expect(groupForPages(groups, 3, 3)).toBe(at("p.3"));
    expect(groupForPages(groups, 3, 4)).toBe(at("p.3–4"));
  });

  it("같은 표기가 없으면 그 쪽에서 시작하는 줄(서버가 'p.N' 으로 대목을 고르는 규칙), 그다음 그 쪽을 품은 줄", () => {
    expect(at("p.11–13")).not.toBe(-1);
    expect(groupForPages(groups, 11, 11)).toBe(at("p.11–13"));
    expect(groupForPages(groups, 11, 12)).toBe(at("p.11–13"));
    expect(groupForPages(groups, 12, 12)).toBe(at("p.11–13"));
  });

  it("어느 줄에도 없는 쪽은 -1", () => {
    expect(groupForPages(groups, 40, 40)).toBe(-1);
  });
});

describe("renderAnswer — 글 속 쪽 표기를 쪽 번호로", () => {
  const sources = [src(1, 1, "p2"), src(18, 18, "a"), src(18, 18, "b")];
  // 한 문단 답의 <p>…</p> 껍데기를 벗긴 안쪽
  const inline = (text: string, link: Parameters<typeof renderAnswer>[1] = null) =>
    renderAnswer(text, link).replace(/^<p>/, "").replace(/<\/p>\n?$/, "");
  const chip = (label: string) => `<span class="skx-chat-cite is-static">${label}</span>`;

  it("'[쪽 정보 없음]'은 걷는다 — 홀로면 앞 공백과, 겹괄호면 바깥 괄호까지, 목록 속이면 구분자와 함께", () => {
    expect(inline("효과적임을 보여주었습니다 [쪽 정보 없음].")).toBe("효과적임을 보여주었습니다.");
    expect(inline("결과 (쪽 정보 없음)와 같다")).toBe("결과와 같다");
    expect(inline("결과는 다음과 같아요 ([쪽 정보 없음]).")).toBe("결과는 다음과 같아요.");
    expect(inline("결과 ([쪽 정보 없음], [p.3]).")).toBe(`결과 ${chip("p.3")}.`);
    expect(inline("결과 [p.3], [쪽 정보 없음].")).toBe(`결과 ${chip("p.3")}.`);
  });

  it("받는 중(link 없음)에는 모양만 같은 글자 — 괄호 묶음은 칩 여럿을 한 덩이로", () => {
    expect(inline("강조합니다 [p.2, p.19].")).toBe(
      `강조합니다 <span class="skx-chat-cite-group">${chip("p.2")}${chip("p.19")}</span>.`,
    );
  });

  it("받기를 마친 답은 그 쪽 묶음을 펼치는 단추 — 묶음 번호·답 번호를 싣고 펼친 묶음은 is-active", () => {
    const groups = groupSources(sources, "[p.2, p.19]");
    const html = inline("필요성 [p.2, p.19].", { msg: 3, groups, active: 1 });
    expect(html).toContain(
      '<button type="button" class="skx-chat-cite" data-msg="3" data-cite="0" aria-label="p.2 원문 보기">p.2</button>',
    );
    expect(html).toContain(
      '<button type="button" class="skx-chat-cite is-active" data-msg="3" data-cite="1" aria-label="p.19 원문 보기">p.19</button>',
    );
  });

  it("출처에 없는 쪽은 단추가 아니라 모양만 — 눌러도 펼칠 대목이 없다", () => {
    const groups = groupSources(sources, "");
    expect(inline("다른 쪽 [p.7]", { msg: 0, groups })).toBe(`다른 쪽 ${chip("p.7")}`);
  });

  it("둥근 괄호·괄호 없는 쪽·범위·'p.' 없는 둘째 표기도 읽는다", () => {
    expect(inline("(p.25)")).toBe(chip("p.25"));
    expect(inline("p.25에 따르면")).toBe(`${chip("p.25")}에 따르면`);
    expect(inline("[p.3–4]")).toBe(chip("p.3–4"));
    expect(inline("[p.3-4]")).toBe(chip("p.3–4"));
    expect(inline("[p.2, 19]")).toContain(chip("p.19"));
  });

  it("겹괄호 '([p.2])'는 괄호 없이 쪽 번호만 — 운영 답에서 '( p.2 )'로 보였다", () => {
    expect(inline("강조하고 있습니다. ([p.2])")).toBe(`강조하고 있습니다. ${chip("p.2")}`);
  });

  // 리뷰 지적 — 바깥 괄호를 양쪽 짝 없이 먹어 '(무작위 배정, [p.3]).'의 닫는 괄호가 사라졌다
  it("한쪽만 겹친 괄호는 안쪽 표기만 바꾸고 바깥 괄호 짝을 그대로 둔다", () => {
    expect(inline("노인 30명이었어요(무작위 배정, [p.3]).")).toBe(`노인 30명이었어요(무작위 배정, ${chip("p.3")}).`);
    expect(inline("효과가 있었어요(표 2 참조, [p.5]) 그리고")).toBe(`효과가 있었어요(표 2 참조, ${chip("p.5")}) 그리고`);
    expect(inline("결과([p.3] 참조)를 보면")).toBe(`결과(${chip("p.3")} 참조)를 보면`);
  });

  // 리뷰 지적 — 쪽 번호 HTML 을 marked 앞에 넣으면 닫는 '**' 앞이 '>' 가 되어 '**p.3**에'의 강조가 닫히지 않았다
  it("굵게 친 쪽 표기 뒤에 조사가 붙어도 굵게 그린다('**'가 글자로 남지 않는다)", () => {
    const html = inline("**p.3**에 따르면");
    expect(html).toBe(`<strong>${chip("p.3")}</strong>에 따르면`);
    expect(inline("**효과가 컸어요 p.3**이에요")).toBe(`<strong>효과가 컸어요 ${chip("p.3")}</strong>이에요`);
  });

  // 리뷰 지적 — 코드 칸 안은 HTML 이 살지 않아 단추 마크업이 글자로 보였다
  it("코드 칸·코드 블록 안의 쪽 표기는 글자 그대로", () => {
    const html = renderAnswer("코드 `p.3` 과\n\n```\n[p.19]\n```", null);
    expect(html).toContain("<code>p.3</code>");
    expect(html).toContain("[p.19]");
    expect(html).not.toContain("skx-chat-cite");
  });

  it("쪽 표기가 아닌 글은 marked 가 그리는 그대로 — 연도 괄호, 'pp.3', 'ap.3', 마크다운 강조, 목록", () => {
    for (const text of ["이경민(2021)의 연구", "pp.3", "ap.3", "**정서적 지지**", "[참고] 표 2", "1. 첫째\n2. 둘째"]) {
      expect(renderAnswer(text, null)).toBe(marked.parse(text));
    }
  });

  it("목록 항목 끝의 쪽 표기도 쪽 번호로", () => {
    expect(renderAnswer("- 정서적 지지 [p.25]\n- 가족 지지", null)).toContain(`<li>정서적 지지 ${chip("p.25")}</li>`);
  });

  it("빈 글은 빈 HTML", () => {
    expect(renderAnswer("", null)).toBe("");
  });
});

describe("BookChat — 근거 목록과 글 속 쪽 번호를 그린다", () => {
  const chat = readFileSync(resolve(__dirname, "../../components/BookChat.vue"), "utf-8");

  it("받기를 마친 답은 쪽 번호 단추로, 받는 중·실패한 글·낭독용은 모양만", () => {
    expect(chat).toContain('v-html="formatAnswer(msg, i)" @click="onCiteClick"');
    expect(chat).toContain("return renderAnswer(msg.content, { msg: i, groups: groupsByMsg.value[i] ?? [], active: msg.pinnedChip });");
    expect(chat).toContain("return renderAnswer(text, null);");
    expect(chat).toContain('v-html="formatStatic(streamingText)"');
    expect(chat).toContain('v-html="formatStatic(failure.partial)"');
    expect(chat).toContain("liveHtml.value = formatStatic(last.content);");
  });

  it("근거 줄은 펼침 상태(aria-expanded)를 알리고 펼친 대목을 가리킨다(aria-controls)", () => {
    expect(chat).toContain(':aria-expanded="msg.pinnedChip === gi"');
    expect(chat).toContain(':aria-controls="msg.pinnedChip === gi ? previewId(i, gi) : undefined"');
  });

  it("글 속 쪽 번호를 누르면 그 줄을 펼치고 줄로 초점을 옮긴다(이미 펼쳤으면 접지 않는다)", () => {
    expect(chat).toMatch(/function onCiteClick[\s\S]*?if \(msg\.pinnedChip !== gi\) \{[\s\S]*?row\?\.focus\(\{ preventScroll: true \}\);/);
  });

  // 리뷰 지적 — 끝에서 disabled 가 되면 누른 단추에 있던 키보드 초점이 사라졌다. 반복 Enter 는 펼친 줄을 도로 접었다
  it("넘기기 단추는 끝에서도 초점을 잃지 않고(aria-disabled), 근거 줄은 누른 채 있는 Enter 를 다시 누르지 않는다", () => {
    expect(chat).toContain(':aria-disabled="passageIndex(msg, g) === 0"');
    expect(chat).toContain(':aria-disabled="passageIndex(msg, g) === g.passages.length - 1"');
    expect(chat).not.toMatch(/skx-chat-source-pager__btn"[^>]*:disabled=/);
    expect(chat).toContain('@keydown.enter="onRepeatEnter"');
    expect(chat).toMatch(/function onRepeatEnter\(e: KeyboardEvent\) \{\s*if \(e\.repeat\) e\.preventDefault\(\);\s*\}/);
  });

  // 화면 말은 사서가 쓰는 말로 — '대목'·'근거'·'✦' 는 AI 말투로 읽혀 걷었다(사용자 2026-10-23)
  it("출처 목록은 '출처 N건', 같은 쪽 여럿은 '외 n건' — 템플릿에 '대목'·'근거'·'✦' 가 보이지 않는다", () => {
    expect(chat).toContain("출처 {{ groupsByMsg[i]!.length }}건");
    expect(chat).toContain("외 {{ g.passages.length - 1 }}건");
    const template = chat.slice(0, chat.indexOf("<script")).replace(/<!--[\s\S]*?-->/g, "");
    expect(template).not.toMatch(/대목|근거|✦/);
    expect(chat).toContain('const CITE_HINT = "답과 함께 출처를 보여 드려요. 출처를 누르면 원문을 바로 확인할 수 있어요.";');
  });

  it("첫 글을 기다리는 동안 지금 하는 일을 보이고, 화면을 떠나면 타이머를 멈춘다", () => {
    expect(chat).toContain('const WAIT_STEPS = ["원문에서 찾고 있어요", "답변을 작성하고 있어요"] as const;');
    expect(chat).toContain("onBeforeUnmount(clearWait);");
  });
});

// 대화 첫 차례 — 설명 문장 두 줄(머리말과 같은 말)을 걷고, 바로 눌러 묻는 추천 질문과 출처 안내 한 줄로(사용자 2026-10-23)
describe("BookChat — 첫 차례는 머리말 · 추천 질문 · 출처 안내", () => {
  const chat = readFileSync(resolve(__dirname, "../../components/BookChat.vue"), "utf-8").replace(/\r\n/g, "\n");
  const template = chat.slice(0, chat.indexOf("<script")).replace(/<!--[\s\S]*?-->/g, "");

  it("첫 차례는 대화가 시작돼도 남고, 추천 질문은 물어보면 체크와 [답 보기]가 된다", () => {
    expect(template).toContain('class="skx-chat-msg skx-chat-msg--ai skx-chat-opening"');
    expect(template).not.toContain("messages.length === 0 && !isStreaming");
    expect(template).toContain('v-for="s in starters"');
    expect(template).toContain("답 보기");
    expect(template).not.toMatch(/introBody|skx-chat-intro__hint/);
  });

  it("출처 안내는 견본 칩(누르지 않는 span) 뒤에 CITE_HINT 그대로", () => {
    expect(template).toContain('<span class="skx-chat-cite is-static" aria-hidden="true">p.3</span>');
    expect(template).toContain("{{ CITE_HINT }}");
  });

  it("끝난 답 아래에 아직 묻지 않은 추천 질문 하나를 '다음 질문'으로 권하고, 받는 중·실패 때는 숨긴다", () => {
    expect(template).toContain('v-if="nextStarter"');
    expect(template).toContain("다음 질문");
    expect(chat).toContain("!messages.value.length || isStreaming.value || failure.value ? null");
  });

  it("추천 질문으로 보낼 때 입력 칸에 되살린 같은 질문은 비운다([다시 시도]와 같은 규칙)", () => {
    expect(chat).toContain("if (inputText.value.trim() === s.q) inputText.value = \"\";");
    expect(chat).toContain("await ask(() => sendChat(s.q));");
  });
});
