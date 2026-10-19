// frontend/tests/unit/summaryTidy.test.ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { marked } from "marked";
import { describe, expect, it } from "vitest";
import { linkCitations } from "~/utils/summaryCite";
import { SUMMARY_ITEMS_MAX, tidySummary } from "~/utils/summaryTidy";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8").replace(/\r\n/g, "\n");

// 문제없는 요약 — 두 섹션, 섹션마다 4항목 이하, 자료가 없다는 말 없음
const CLEAN = [
  "## 핵심 요약",
  "- 사회적 지지는 노인의 우울과 부적 상관을 보였다 (1, 3).",
  "- 가족 지지의 효과가 친구 지지보다 컸다 (2).",
  "",
  "## 연구 방법 및 근거",
  "- 지역사회 노인 300명을 설문조사했다 (1).",
  "- 위계적 회귀분석으로 조절효과를 검증했다 (3).",
].join("\n");

const item = (n: number) => `- 결과 ${n} 이다 (${n}).`;

describe("tidySummary — 자료가 없다는 말만 하는 항목 빼기", () => {
  it("문제없는 요약은 그대로다", () => {
    expect(tidySummary(CLEAN)).toBe(CLEAN);
    expect(tidySummary(CLEAN, { streaming: true })).toBe(CLEAN);
    expect(tidySummary("")).toBe("");
  });

  it("'초록이 없'·'파악할 수 없'·'확인할 수 없'이 든 목록 항목은 줄째 빠지고, 남은 목록은 이어진다", () => {
    const text = [
      "## 핵심 요약",
      "- 사회적 지지는 우울을 낮췄다 (1).",
      "- 4번 논문은 초록이 없어 제목으로만 주제를 알 수 있다 (4).",
      "- 가족 지지의 효과가 컸다 (2).",
      "- 2번 논문의 표본 크기는 주어진 초록에서 파악할 수 없다.",
      "- 효과 크기는 확인할 수 없습니다 (3).",
      "- 우울 척도는 CES-D 였다 (3).",
    ].join("\n");
    expect(tidySummary(text)).toBe(
      ["## 핵심 요약", "- 사회적 지지는 우울을 낮췄다 (1).", "- 가족 지지의 효과가 컸다 (2).", "- 우울 척도는 CES-D 였다 (3)."].join("\n"),
    );
    // 띄어쓰기가 달라도 같은 말이다
    expect(tidySummary("- 방법은 확인 할 수 없다.\n- 남는다 (1).")).toBe("- 남는다 (1).");
    expect(tidySummary("- 1번은 초록이  없다.\n- 남는다 (1).")).toBe("- 남는다 (1).");
  });

  it("'확인할 수 없었다'·'파악할 수 없던'은 연구가 밝힌 결과라 남긴다", () => {
    const text = ["- 성별에 따른 차이는 확인할 수 없었다 (2).", "- 기존 연구로는 파악할 수 없던 경로를 밝혔다 (1)."].join("\n");
    expect(tidySummary(text)).toBe(text);
  });

  it("목록 밖의 문단은 그 말이 있어도 건드리지 않는다", () => {
    const text = "## 핵심 요약\n주어진 초록으로는 확인할 수 없다.\n- 남는다 (1).";
    expect(tidySummary(text)).toBe(text);
  });

  it("빠지는 항목에 딸린 줄(들여 쓴 줄·이어 쓴 줄·하위 목록)도 함께 빠진다", () => {
    const text = [
      "- 남는다 (1).",
      "- 3번 논문은 초록이 없어",
      "  연구 대상을 알 수 없다.",
      "  - 하위 항목",
      "이어 쓴 줄",
      "- 끝 항목 (2).",
    ].join("\n");
    expect(tidySummary(text)).toBe("- 남는다 (1).\n- 끝 항목 (2).");
  });

  it("항목이 모두 빠지고 다른 글도 없는 섹션은 제목까지 뺀다 — 다른 글이 있으면 제목은 남는다", () => {
    const text = [
      "## 핵심 요약",
      "- 남는다 (1).",
      "",
      "## 연구 방법 및 근거",
      "- 1번 논문은 초록이 없다.",
      "- 표본은 확인할 수 없다.",
      "",
      "## 덧붙임",
      "- 남는다 (2).",
    ].join("\n");
    expect(tidySummary(text)).toBe(["## 핵심 요약", "- 남는다 (1).", "", "", "## 덧붙임", "- 남는다 (2)."].join("\n"));

    const withText = "## 연구 방법 및 근거\n방법은 논문마다 다르다.\n- 1번 논문은 초록이 없다.";
    expect(tidySummary(withText)).toBe("## 연구 방법 및 근거\n방법은 논문마다 다르다.");
    // 처음부터 항목이 없던 섹션은 이 규칙이 만든 빈 섹션이 아니다 — 그대로 둔다
    expect(tidySummary("## 핵심 요약\n\n## 연구 방법 및 근거\n- 남는다 (1).")).toBe("## 핵심 요약\n\n## 연구 방법 및 근거\n- 남는다 (1).");
  });

  it("남는 것이 빈 줄뿐이면 빈 글이다", () => {
    expect(tidySummary("- 1번 논문은 초록이 없다.\n- 확인할 수 없다.\n")).toBe("");
    expect(tidySummary("\n\n")).toBe("");
  });
});

describe(`tidySummary — 섹션마다 ${SUMMARY_ITEMS_MAX}항목까지`, () => {
  it("섹션마다 앞에서부터 SUMMARY_ITEMS_MAX 개만 남기고, 섹션이 바뀌면 다시 센다", () => {
    expect(SUMMARY_ITEMS_MAX).toBe(4);
    const six = [1, 2, 3, 4, 5, 6].map(item);
    const text = ["## 핵심 요약", ...six, "", "## 연구 방법 및 근거", ...six].join("\n");
    const four = six.slice(0, 4);
    expect(tidySummary(text)).toBe(["## 핵심 요약", ...four, "", "## 연구 방법 및 근거", ...four].join("\n"));
  });

  it("제목 없는 머리말·번호 목록·'*'·'+' 머리도 항목으로 센다", () => {
    expect(tidySummary([1, 2, 3, 4, 5].map(item).join("\n"))).toBe([1, 2, 3, 4].map(item).join("\n"));
    const numbered = ["1. 가 (1).", "2. 나 (2).", "3) 다 (3).", "* 라 (4).", "+ 마 (5)."];
    expect(tidySummary(numbered.join("\n"))).toBe(numbered.slice(0, 4).join("\n"));
  });

  it("빠진 항목은 세지 않는다 — 다섯 중 하나가 빠지면 나머지 넷이 다 남는다", () => {
    const text = [item(1), "- 2번은 초록이 없다.", item(3), item(4), item(5)].join("\n");
    expect(tidySummary(text)).toBe([item(1), item(3), item(4), item(5)].join("\n"));
  });

  it("하위 목록·이어 쓴 줄은 따로 세지 않고, 넘친 항목에 딸린 줄은 함께 빠진다", () => {
    const text = [item(1), "  - 하위 가", "  - 하위 나", item(2), item(3), item(4), item(5), "  이어 쓴 줄"].join("\n");
    expect(tidySummary(text)).toBe([item(1), "  - 하위 가", "  - 하위 나", item(2), item(3), item(4)].join("\n"));
  });

  it("가로줄(- - -)은 항목이 아니다", () => {
    const text = [item(1), item(2), item(3), item(4), "", "- - -", "", "맺음 문단"].join("\n");
    expect(tidySummary(text)).toBe(text);
  });

  it("CRLF 줄바꿈도 같게 다듬는다", () => {
    expect(tidySummary([1, 2, 3, 4, 5].map(item).join("\r\n"))).toBe([1, 2, 3, 4].map(item).join("\n"));
  });
});

describe("tidySummary — 스트리밍 중간 글", () => {
  // 받는 글 — 자료가 없다는 항목·넘친 항목·연구 결과의 '확인할 수 없었다'·인용 번호가 섞였다. 마지막 섹션이 통째로 빠진다
  const FULL = [
    "## 핵심 요약",
    "- 사회적 지지는 우울과 부적 상관을 보였다 (1, 3).",
    "- 2번 논문은 초록이 없어 결과를 파악할 수 없다.",
    "- 가족 지지의 효과가 컸다 (2).",
    "- 성별 차이는 확인할 수 없었다 (4).",
    "- 지지 유형별 효과가 달랐다 (5).",
    "- 다섯째 항목은 보이지 않는다 (1).",
    "",
    "## 연구 방법 및 근거",
    "- 지역사회 노인 300명을 조사했다 (1).",
    "- 효과 크기는 확인할 수 없다.",
    "",
    "## 덧붙임",
    "- 4번 논문은 초록이 없다.",
    "",
  ].join("\n");
  const prefixes = Array.from({ length: FULL.length + 1 }, (_, i) => FULL.slice(0, i));
  /** 다 쓴 줄(뒤에 줄바꿈이 온 줄) 가운데 보이는 것 — 출력의 마지막 줄이 쓰는 중인 줄이면 뺀다(그 줄이 빠졌으면 마지막 줄도 다 쓴 줄이다) */
  const doneLines = (prefix: string, out: string) => {
    const lines = out.split("\n");
    const writing = prefix.split("\n").at(-1)!;
    return writing && lines.at(-1) === writing ? lines.slice(0, -1) : lines;
  };

  it("한 번 보인 다 쓴 줄은 뒤 글이 와도 사라지지 않는다(깜빡이지 않는다)", () => {
    let before: string[] = [];
    for (const prefix of prefixes) {
      const shown = doneLines(prefix, tidySummary(prefix, { streaming: true }));
      for (const line of before.filter((l) => l.trim())) expect(shown, JSON.stringify(prefix)).toContain(line);
      before = shown;
    }
  });

  it("줄 가운데를 자르지 않는다 — 보이는 줄은 모두 받은 글의 한 줄 그대로다", () => {
    for (const prefix of prefixes) {
      const lines = prefix.split("\n");
      for (const line of tidySummary(prefix, { streaming: true }).split("\n")) expect(lines).toContain(line);
    }
  });

  it("쓰는 중인 '…확인할 수 없' 은 뒤 글자가 오기 전까지 남기고, '었'이 오면 계속 남는다", () => {
    const head = "## 핵심 요약\n- 성별 차이는 확인할 수 없";
    expect(tidySummary(head, { streaming: true })).toBe(head);
    expect(tidySummary(`${head}었`, { streaming: true })).toBe(`${head}었`);
    // '다'가 오면 자료가 없다는 말이라 그때 빠진다
    expect(tidySummary(`${head}다`, { streaming: true })).toBe("## 핵심 요약");
    // 다 받은 글이면 줄 끝의 '없'도 판단한다(줄 끝을 뒤 글자로 본다)
    expect(tidySummary(head)).toBe("");
  });

  it("다섯째 항목은 머리('-')가 오는 순간부터 보이지 않는다", () => {
    const four = ["## 핵심 요약", ...[1, 2, 3, 4].map(item)].join("\n");
    for (const tail of ["\n-", "\n- ", "\n- 다섯", `\n${item(5)}`]) {
      expect(tidySummary(four + tail, { streaming: true })).toBe(four);
    }
  });

  it("빈 섹션의 제목은 다음 제목이 오거나 다 받은 뒤에만 뺀다 — 받는 중인 마지막 섹션은 제목을 둔다", () => {
    const open = "## 핵심 요약\n- 남는다 (1).\n\n## 연구 방법 및 근거\n- 1번 논문은 초록이 없다.\n";
    expect(tidySummary(open, { streaming: true })).toContain("## 연구 방법 및 근거");
    expect(tidySummary(`${open}\n##`, { streaming: true })).not.toContain("## 연구 방법 및 근거");
    expect(tidySummary(open)).not.toContain("## 연구 방법 및 근거");
  });

  it("다 받은 글은 넘친 항목·자료 없음 항목·빈 마지막 섹션을 모두 정리하고 인용 번호는 그대로 둔다", () => {
    const expected = [
      "## 핵심 요약",
      "- 사회적 지지는 우울과 부적 상관을 보였다 (1, 3).",
      "- 가족 지지의 효과가 컸다 (2).",
      "- 성별 차이는 확인할 수 없었다 (4).",
      "- 지지 유형별 효과가 달랐다 (5).",
      "",
      "## 연구 방법 및 근거",
      "- 지역사회 노인 300명을 조사했다 (1).",
      "",
      "",
    ].join("\n");
    expect(tidySummary(FULL)).toBe(expected);
    // 받는 중에도 마지막 섹션 제목만 빼고 같다
    expect(tidySummary(FULL, { streaming: true })).toBe(expected.replace(/\n\n$/, "\n\n## 덧붙임\n"));
  });

  it("다듬은 글을 그리면 남은 인용 번호가 그대로 버튼이 된다(SummaryText 의 linkCitations)", () => {
    const refs = [1, 2, 3, 4, 5].map((num) => ({ num, title: `논문 ${num}` }));
    const html = linkCitations(marked.parse(tidySummary(FULL)) as string, refs);
    const cited = [...html.matchAll(/data-cite="(\d+)"/g)].map((m) => Number(m[1]));
    expect(cited).toEqual([1, 3, 2, 4, 5, 1]);
    expect(html).not.toContain("초록이 없");
  });
});

describe("논문 검색 AI 요약 그리기 배선 — pages/papers/index.vue", () => {
  const src = read("pages/papers/index.vue");

  it("받은 글(aiText)을 tidySummary 로 다듬은 글(shownAiText)을 marked 로 그린다 — 받는 중이면 streaming", () => {
    expect(src).toContain('import { tidySummary } from "~/utils/summaryTidy";');
    expect(src).toContain("const shownAiText = computed(() => tidySummary(aiText.value, { streaming: aiLoading.value }));");
    expect(src).toMatch(/const renderedAiText = computed\(\(\) =>\s*shownAiText\.value \? \(marked\.parse\(shownAiText\.value\) as string\) : "",\s*\);/);
    // marked 로 그리는 곳은 이 한 곳뿐이다 — 받은 글을 그대로 그리는 길이 없다
    expect(src.match(/marked\.parse\(/g)).toHaveLength(1);
  });

  it("요약 칸의 보이기 조건도 다듬은 글로 정한다 — 다 빠지면 빈 요약", () => {
    expect(src).toContain(':hint="!!shownAiText && !aiLoading"');
    expect(src).toContain('<div v-if="aiLoading || shownAiText || !aiError" class="skx-pai-main__scroll">');
    expect(src).toContain('<template v-if="aiLoading && !shownAiText">');
    expect(src).toMatch(/<SummaryText\s+v-else-if="shownAiText"\s+:html="renderedAiText"/);
    expect(src).toContain(":class=\"['skx-pai-main__failed', !shownAiText && 'is-alone']\"");
  });

  it("기록에는 받은 글 원문을 저장하고, 복원은 그 원문을 aiText 에 넣어 같은 자리에서 다듬는다", () => {
    expect(src).toMatch(/void historyApi\.patch\(historyId, \{ ai: \{ text, refs \} \}\)/);
    expect(src).toContain('aiText.value = entry.ai?.text ?? "";');
  });
});
