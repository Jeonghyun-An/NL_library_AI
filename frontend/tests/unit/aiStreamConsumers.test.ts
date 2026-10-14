// frontend/tests/unit/aiStreamConsumers.test.ts
// AI 글 스트림을 받는 화면들이 서버의 {error} 이벤트를 안다 — 오류 문구를 답 글에 잇지 않고 오류로 보이며(role="alert"),
// 끝까지 받은 글만 캐시·검색 기록에 저장한다. 서버(app/services/search/paper_summary.py·pipeline.py·chat/book_chat.py)는
// LLM 호출이 실패하면 [DONE] 바로 앞에 {error: 문구} 를 보낸다. 화면은 Nuxt 없이 돌지 않아 소스 글로 고정한다
// (relatedCard.test 와 같은 방식). 스트림 읽기 자체는 aiStream.test·useDeepReadChat.test 가 본다
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8");

// 사용자가 보존하라고 한 첫 화면과 쓰이지 않는 옛 대화 칸 — 손대지 않는다
const UNTOUCHED = new Set(["pages/search-classic.vue", "components/BookChat.legacy.vue"]);

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(resolve(root, dir))) {
    const rel = join(dir, name).replace(/\\/g, "/");
    if (statSync(resolve(root, rel)).isDirectory()) out.push(...sourceFiles(rel));
    else if (/\.(vue|ts)$/.test(name)) out.push(rel);
  }
  return out;
}

const ALL = ["pages", "components", "composables", "utils"].flatMap(sourceFiles).filter((f) => !UNTOUCHED.has(f));

// {{ name }} 를 그리는 요소의 여는 태그에 role="alert" 가 있다
function alertShows(src: string, name: string): boolean {
  return new RegExp(`<(p|div|span)\\b[^>]*role="alert"[^>]*>\\s*\\{\\{\\s*${name.replace(/[.[\]]/g, "\\$&")}\\s*\\}\\}`).test(src);
}

describe("SSE 를 직접 읽는 곳", () => {
  it("세 읽기 도구뿐이다 — 화면마다 따로 읽다가 {error} 를 모르는 곳이 생기지 않게", () => {
    const readers = ALL.filter((f) => read(f).includes("getReader("));
    expect(readers.sort()).toEqual(["composables/useDeepReadChat.ts", "utils/aiStream.ts", "utils/bookAiPick.ts"]);
  });

  it("AI 글 스트림 주소를 부르는 화면은 모두 {error} 를 아는 읽기(readAiStream·readReasonStream)로 읽는다", () => {
    const STREAMS = ["/papers/summary/stream", "/papers/reason/stream", "/papers/related-reason/stream", "/books/reason/stream"];
    const callers = ALL.filter((f) => STREAMS.some((s) => read(f).includes(`"${s}"`)));
    expect(callers.sort()).toEqual(["pages/books/[cnts_id].vue", "pages/index.vue", "pages/papers/[id].vue", "pages/papers/index.vue"]);
    for (const f of callers) expect(read(f), f).toMatch(/\b(readAiStream|readReasonStream)\(/);
  });
});

describe("논문 검색 AI 요약 — pages/papers/index.vue", () => {
  const src = read("pages/papers/index.vue");

  it("끝까지 받은 요약만 검색 기록(ai)에 저장하고, 실패는 오류 문구로 둔다", () => {
    expect(src).toMatch(/if \(end\.ok\) \{\s*if \(text\) void historyApi\.patch\(historyId, \{ ai: \{ text, refs \} \}\)/);
    expect(src).toContain("aiError.value = failureText(end, AI_SUMMARY_FAILED)");
  });

  it("오류는 요약 글과 따로 role=alert 로 보이고 [다시 시도]가 같은 기록으로 다시 만든다", () => {
    expect(alertShows(src, "aiError")).toBe(true);
    expect(src).toMatch(/@click="retryAiSummary"[^>]*>\s*다시 시도/);
    expect(src).toMatch(/function retryAiSummary\(\)[\s\S]*?streamAiSummary\(currentHistoryId\.value, resultQuery\.value/);
  });
});

describe("논문 상세 — pages/papers/[id].vue", () => {
  const src = read("pages/papers/[id].vue");

  it("AI 요약·관련 논문 추천 사유 모두 끝까지 받은 글만 sessionStorage 캐시에 담는다", () => {
    expect(src.match(/if \(end\.ok\) writeAiCache\(/g)).toHaveLength(2);
    expect(src).not.toMatch(/if \(finished\) writeAiCache/);
    expect(src).toContain("summaryError.value = failureText(end, AI_SUMMARY_FAILED)");
    expect(src).toContain("failureText(end, RELATED_REASON_FAILED)");
  });

  it("AI 요약 오류는 role=alert 로 보이고 [다시 시도]가 있으며, 글 없이 실패해도 [AI 요약] 탭이 남는다", () => {
    expect(alertShows(src, "summaryError")).toBe(true);
    expect(src).toMatch(/@click="retrySummary"[^>]*>\s*다시 시도/);
    expect(src).toMatch(/key: "ai-summary", label: "AI 요약", available: [^\n]*summaryError\.value/);
  });

  it("관련 논문 카드에 추천 사유 오류를 넘긴다", () => {
    expect(src).toContain(':reason-error="relatedReasonErrors[rel.book_id]"');
  });
});

describe("관련 자료 카드 — components/detail/RelatedCard.vue", () => {
  const src = read("components/detail/RelatedCard.vue");

  it("추천 사유 오류(reasonError)를 사유 글과 따로 상자·팝업 모두에 보인다", () => {
    expect(src).toMatch(/reasonError\?: string;/);
    expect(src.match(/\{\{\s*reasonError\s*\}\}/g)).toHaveLength(2);
  });
});

describe("소장자료 상세 추천 이유 — pages/books/[cnts_id].vue", () => {
  const src = read("pages/books/[cnts_id].vue");

  it("실패는 role=alert 오류로 보이고 [다시 시도]가 있으며, 글 없이 실패해도 [추천 이유] 탭이 남는다", () => {
    expect(src).toContain("reasonError.value = failureText(end, BOOK_REASON_FAILED)");
    expect(alertShows(src, "reasonError")).toBe(true);
    expect(src).toMatch(/@click="streamReason"[^>]*>\s*다시 시도/);
    expect(src).toMatch(/key: "reason", label: "추천 이유", available: [^\n]*reasonError\.value/);
  });
});

describe("DeepRead 대화 칸 — components/BookChat.vue", () => {
  const src = read("components/BookChat.vue");

  it("답을 만들지 못한 질문은 대화와 따로 role=alert 로 보이고 [다시 시도]가 같은 질문을 다시 보낸다", () => {
    expect(alertShows(src, "failure.message")).toBe(true);
    expect(src).toMatch(/@click="retry"[^>]*>\s*다시 시도/);
  });

  it("실패했을 때는 앞 답을 화면낭독기에 다시 읽히지 않는다", () => {
    expect(src).toMatch(/if \(!failure\.value && last\?\.role === "assistant"\)/);
  });
});
