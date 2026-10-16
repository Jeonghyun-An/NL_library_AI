// frontend/tests/unit/errorCopyLineBreaks.test.ts
// 오류 문구의 줄바꿈 규칙(사용자 요청 2026-10-16) — 두 문장 이상인 문구는 문장마다 줄을 바꾼다('…어요.\n…요.').
// 공통 오류 블록·줄 안내·연결 끊김 띠는 white-space: pre-line 으로 '\n' 을 줄로 그리고, 넘치는 줄은 낱말 사이에서만 바꾼다(keep-all)
import { describe, expect, it } from "vitest";
import { CODE_MESSAGES, CONNECTION_HINTS, ERROR_HINTS, ERROR_PAGE_TEXT, VALIDATION_HINTS } from "~/utils/apiErrors";
import { RESEARCH_STATE_TEXT, pdfCheckProblem } from "~/utils/researchErrors";
import { blockOrThrow } from "./helpers/themeCss";

const copies: [string, string][] = [
  ...Object.entries(ERROR_HINTS),
  ...Object.entries(CODE_MESSAGES),
  ...Object.entries(CONNECTION_HINTS),
  ...Object.entries(VALIDATION_HINTS),
  ...Object.entries(RESEARCH_STATE_TEXT),
  ...Object.entries(ERROR_PAGE_TEXT).flatMap(([k, v]) =>
    typeof v === "string" ? [[k, v] as [string, string]] : Object.entries(v).map(([kk, vv]) => [`${k}.${kk}`, String(vv)] as [string, string]),
  ),
  ["pdf 500", pdfCheckProblem(500) ?? ""],
];

describe("오류 문구 — 문장마다 줄을 바꾼다", () => {
  it.each(copies)("%s: 한 줄 안에 두 문장을 잇지 않는다('. ' 대신 '.\n')", (_name, text) => {
    expect(text).not.toMatch(/[.?!] \S/);
  });

  it.each(copies.filter(([, t]) => t.includes("\n")))("%s: 여러 줄이면 줄마다 마침표로 끝난다", (_name, text) => {
    for (const line of text.split("\n")) expect(line).toMatch(/[.?!…]$/);
  });
});

describe("오류 글자 칸 — '\n' 을 줄로 그리고 낱말 사이에서만 줄을 바꾼다", () => {
  it.each([".skx-state__msg", ".skx-inline-error__msg", ".skx-conn__msg"])("%s", (selector) => {
    const body = blockOrThrow(selector);
    expect(body).toMatch(/white-space:\s*pre-line/);
    expect(body).toMatch(/word-break:\s*keep-all/);
  });

  it("상태 블록 제목도 낱말을 가르지 않고 두 줄이면 길이를 고르게 한다", () => {
    const body = blockOrThrow(".skx-state__title");
    expect(body).toMatch(/word-break:\s*keep-all/);
    expect(body).toMatch(/text-wrap:\s*balance/);
  });
});
