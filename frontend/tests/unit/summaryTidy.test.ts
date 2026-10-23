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

  it("문장이 '…할 수 없'에서 맺어지지 않고 이어지면(현재형·관형형으로 옮긴 결과·한계) 남긴다", () => {
    const kept = [
      "- 횡단 자료라 인과관계를 확인할 수 없다는 한계가 있다 (2).",
      "- 두 집단 간 유의한 차이는 확인할 수 없는 것으로 나타났다 (3).",
      "- 성별 효과는 확인할 수 없음을 보고했다 (3).",
      "- 장기 효과는 파악할 수 없다고 밝혔다 (1).",
      "- 표본이 작아 효과를 확인할 수 없어 후속 연구를 제언했다 (4).",
    ];
    for (const line of kept) expect(tidySummary(`## 연구 방법 및 근거\n${line}`), line).toBe(`## 연구 방법 및 근거\n${line}`);
    // 리뷰가 든 꼴 — 한계 항목은 남고, 결과 항목 하나뿐인 요약도 빈 요약이 되지 않는다
    const limit = "## 연구 방법 및 근거\n- 횡단 자료라 인과관계를 확인할 수 없다는 한계가 있다 (2).\n- 300명을 조사했다 (1).";
    expect(tidySummary(limit)).toBe(limit);
    expect(tidySummary("## 핵심 요약\n- 성별 효과는 확인할 수 없음을 보고했다 (3).")).toBe("## 핵심 요약\n- 성별 효과는 확인할 수 없음을 보고했다 (3).");
  });

  it("'…할 수 없다·없습니다·없음·없어요'로 문장을 맺으면 인용 번호·마침표가 붙거나 줄 끝이어도 뺀다", () => {
    for (const line of [
      "- 표본 크기는 확인할 수 없다",
      "- 표본 크기는 확인할 수 없다(2).",
      "- 표본 크기는 확인할 수 없습니다 (1, 3).",
      "- 표본 크기: 확인할 수 없음 (2)",
      "- 표본 크기는 파악할 수 없어요.",
    ]) {
      expect(tidySummary(`${line}\n- 남는다 (1).`), line).toBe("- 남는다 (1).");
    }
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

  it("항목 문장이 마침표로 끝난 뒤 빈 줄 없이 온 들여 쓰지 않은 줄은 새 문단이다 — 앞 항목과 함께 빠지지 않고, 그 문단도 건드리지 않는다", () => {
    const text = "## 핵심 요약\n- 지지가 컸다 (1).\n전반적으로 효과 크기는 확인할 수 없다.";
    expect(tidySummary(text)).toBe(text);
    // 문단 앞 항목이 빠져도 문단은 남고, 문단이 있으니 섹션 제목도 남는다
    expect(tidySummary("## 핵심 요약\n- 1번 논문은 초록이 없다.\n전반적으로 지지가 컸다 (2).")).toBe("## 핵심 요약\n전반적으로 지지가 컸다 (2).");
    // 인용 번호가 마침표 뒤에 붙은 꼴도 문장이 맺어진 것이다
    expect(tidySummary("- 지지가 컸다. (1)\n효과 크기는 확인할 수 없다.")).toBe("- 지지가 컸다. (1)\n효과 크기는 확인할 수 없다.");
  });

  it("넘친 항목 바로 뒤에 붙은 맺음 문단은 넘친 항목과 함께 빠지지 않는다", () => {
    const four = [1, 2, 3, 4].map(item);
    expect(tidySummary([...four, item(5), "이상의 결과는 지지의 효과를 보여 준다."].join("\n"))).toBe(
      [...four, "이상의 결과는 지지의 효과를 보여 준다."].join("\n"),
    );
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

  it("굵은 글씨만 있는 줄도 섹션 제목으로 본다 — 두 섹션이 한 섹션으로 세어져 둘째 섹션 항목이 잘리지 않는다", () => {
    const text = ["**핵심 요약**", "- a (1).", "- b (2).", "- c (3).", "", "**연구 방법 및 근거**", "- d (4).", "- e (5)."].join("\n");
    expect(tidySummary(text)).toBe(text);
    // '__…__'·끝의 쌍점도 같다. 섹션마다 다시 센다
    const six = [1, 2, 3, 4, 5, 6].map(item);
    for (const head of ["__핵심 요약__", "**핵심 요약:**", "**핵심 요약**:"]) {
      expect(tidySummary([head, ...six, "**연구 방법 및 근거**", ...six].join("\n"))).toBe(
        [head, ...six.slice(0, 4), "**연구 방법 및 근거**", ...six.slice(0, 4)].join("\n"),
      );
    }
    // 항목이 모두 빠진 굵은 글씨 제목 섹션은 제목까지 빠진다
    expect(tidySummary("**핵심 요약**\n- 남는다 (1).\n**연구 방법 및 근거**\n- 1번 논문은 초록이 없다.")).toBe("**핵심 요약**\n- 남는다 (1).");
    // 굵은 글씨로 시작해 글이 이어지는 줄·두 칸 넘게 들여 쓴 줄은 제목이 아니다
    expect(tidySummary(["**주의** 아래는 요약이다.", ...six].join("\n"))).toBe(["**주의** 아래는 요약이다.", ...six.slice(0, 4)].join("\n"));
  });

  it("setext 제목(글 줄 아래 '---'·'===')도 섹션 제목으로 본다", () => {
    const six = [1, 2, 3, 4, 5, 6].map(item);
    for (const bar of ["---", "==="]) {
      const text = ["핵심 요약", bar, ...six, "", "연구 방법 및 근거", bar, ...six].join("\n");
      expect(tidySummary(text), bar).toBe(["핵심 요약", bar, ...six.slice(0, 4), "", "연구 방법 및 근거", bar, ...six.slice(0, 4)].join("\n"));
    }
    // 항목이 모두 빠진 setext 섹션은 글 줄과 밑줄이 함께 빠진다
    expect(tidySummary("핵심 요약\n---\n- 남는다 (1).\n\n연구 방법\n---\n- 1번 논문은 초록이 없다.")).toBe("핵심 요약\n---\n- 남는다 (1).\n");
    // 빈 줄 뒤의 '---'·항목 바로 아래의 '---'는 가로줄이다 — 제목이 아니다
    expect(tidySummary([item(1), item(2), item(3), "---", item(4), item(5)].join("\n"))).toBe(
      [item(1), item(2), item(3), "---", item(4)].join("\n"),
    );
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
  // 받는 글 — 항목 바로 뒤 빈 줄 없이 온 문단(자료가 없다는 말이 든 것·넘친 항목 뒤 맺음 문단)·여러 줄 항목·굵은 글씨 제목·
  // 현재형·관형형으로 옮긴 결과와 한계가 섞였다
  const MIXED = [
    "**핵심 요약**",
    "- 사회적 지지는 우울을 낮췄다 (1).",
    "전반적으로 효과 크기는 확인할 수 없다.",
    "- 2번 논문은 초록이 없어",
    "  주제만 알 수 있다.",
    "- 가족 지지의 효과가 컸다 (2).",
    "- 지지 유형별 효과가",
    "  달랐다 (3).",
    "- 친구 지지도 효과가 있었다 (4).",
    "- 다섯째 항목은 보이지 않는다 (5).",
    "이상은 지역사회 노인 연구다.",
    "",
    "**연구 방법 및 근거**",
    "- 횡단 자료라 인과관계를 확인할 수 없다는 한계가 있다 (2).",
    "- 두 집단 간 차이는 확인할 수 없는 것으로 나타났다 (3).",
    "- 표본 크기는 확인할 수 없다.",
    "- 300명을 조사했다 (1).",
    "",
  ].join("\n");
  const prefixesOf = (full: string) => Array.from({ length: full.length + 1 }, (_, i) => full.slice(0, i));
  /** 다 쓴 줄(뒤에 줄바꿈이 온 줄) 가운데 보이는 것 — 출력의 마지막 줄이 쓰는 중인 줄이면 뺀다(그 줄이 빠졌으면 마지막 줄도 다 쓴 줄이다) */
  const doneLines = (prefix: string, out: string) => {
    const lines = out.split("\n");
    const writing = prefix.split("\n").at(-1)!;
    return writing && lines.at(-1) === writing ? lines.slice(0, -1) : lines;
  };

  it.each([
    ["FULL", FULL],
    ["MIXED", MIXED],
  ])("한 번 보인 다 쓴 줄은 뒤 글이 와도 사라지지 않는다(깜빡이지 않는다) — %s", (_, full) => {
    let before: string[] = [];
    for (const prefix of prefixesOf(full)) {
      const shown = doneLines(prefix, tidySummary(prefix, { streaming: true }));
      for (const line of before.filter((l) => l.trim())) expect(shown, JSON.stringify(prefix)).toContain(line);
      before = shown;
    }
  });

  it.each([
    ["FULL", FULL],
    ["MIXED", MIXED],
  ])("줄 가운데를 자르지 않는다 — 보이는 줄은 모두 받은 글의 한 줄 그대로다 — %s", (_, full) => {
    for (const prefix of prefixesOf(full)) {
      const lines = prefix.split("\n");
      for (const line of tidySummary(prefix, { streaming: true }).split("\n")) expect(lines).toContain(line);
    }
  });

  it("MIXED 를 다 받으면 자료가 없다는 항목과 다섯째 항목만 빠지고, 문단·여러 줄 항목·결과·한계·제목은 남는다", () => {
    const expected = [
      "**핵심 요약**",
      "- 사회적 지지는 우울을 낮췄다 (1).",
      "전반적으로 효과 크기는 확인할 수 없다.",
      "- 가족 지지의 효과가 컸다 (2).",
      "- 지지 유형별 효과가",
      "  달랐다 (3).",
      "- 친구 지지도 효과가 있었다 (4).",
      "이상은 지역사회 노인 연구다.",
      "",
      "**연구 방법 및 근거**",
      "- 횡단 자료라 인과관계를 확인할 수 없다는 한계가 있다 (2).",
      "- 두 집단 간 차이는 확인할 수 없는 것으로 나타났다 (3).",
      "- 300명을 조사했다 (1).",
      "",
    ].join("\n");
    expect(tidySummary(MIXED)).toBe(expected);
    expect(tidySummary(MIXED, { streaming: true })).toBe(expected);
  });

  it("쓰는 중인 '…확인할 수 없다' 는 문장이 맺어지기 전까지 남기고, 문장이 이어지면 계속 남는다", () => {
    const head = "## 핵심 요약\n- 성별 차이는 확인할 수 없";
    for (const tail of ["", "었", "다", "다 (3", "다 (3)", "다는 한계가 있다 (3).", "는 것으로 나타났다 (3)."]) {
      expect(tidySummary(`${head}${tail}`, { streaming: true }), tail).toBe(`${head}${tail}`);
    }
    // 마침표나 줄 끝으로 문장이 맺어지면 자료가 없다는 말이라 그때 빠진다
    expect(tidySummary(`${head}다.`, { streaming: true })).toBe("## 핵심 요약");
    expect(tidySummary(`${head}다 (3).`, { streaming: true })).toBe("## 핵심 요약");
    expect(tidySummary(`${head}다\n`, { streaming: true })).toBe("## 핵심 요약\n");
    // 다 받은 글이면 줄 끝도 문장 끝이다. '없'에서 끊긴 글은 뒤를 알 수 없어 남긴다
    expect(tidySummary(`${head}다`)).toBe("");
    expect(tidySummary(head)).toBe(head);
  });

  it("쓰는 중인 굵은 글씨 줄·setext 밑줄은 줄이 끝나야 제목으로 본다", () => {
    const four = [1, 2, 3, 4].map(item);
    // 쓰는 중인 '**연구' 는 아직 글 줄이다 — 줄이 끝나 제목이 되면 그 아래 항목은 새 섹션에서 센다
    expect(tidySummary([...four, "**연구 방법**"].join("\n"), { streaming: true })).toBe([...four, "**연구 방법**"].join("\n"));
    expect(tidySummary([...four, "**연구 방법**", item(5)].join("\n"), { streaming: true })).toBe([...four, "**연구 방법**", item(5)].join("\n"));
    // 쓰는 중인 '-' 는 아직 항목 머리일 수 있다 — 다섯째 항목처럼 숨었다가 '---' 줄이 끝나면 제목 밑줄로 보인다
    const para = ["## 핵심 요약", ...four, "", "연구 방법"];
    expect(tidySummary([...para, "-"].join("\n"), { streaming: true })).toBe(para.join("\n"));
    expect(tidySummary([...para, "---", ""].join("\n"), { streaming: true })).toBe([...para, "---", ""].join("\n"));
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
