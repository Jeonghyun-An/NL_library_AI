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
// 파일 글은 모을 때 한 번만 읽는다 — 테스트 안에서 파일마다(스트림 주소마다) 다시 읽으면 전체 실행(파일 병렬)에서 5초 제한을 넘곤 했다
const SOURCES = new Map(ALL.map((f) => [f, read(f)] as const));
const source = (f: string) => SOURCES.get(f) ?? read(f);

// {{ name }} 를 그리는 요소의 여는 태그에 role="alert" 가 있다
function alertShows(src: string, name: string): boolean {
  return new RegExp(`<(p|div|span)\\b[^>]*role="alert"[^>]*>\\s*\\{\\{\\s*${name.replace(/[.[\]]/g, "\\$&")}\\s*\\}\\}`).test(src);
}

describe("SSE 를 직접 읽는 곳", () => {
  it("세 읽기 도구뿐이다 — 화면마다 따로 읽다가 {error} 를 모르는 곳이 생기지 않게", () => {
    const readers = ALL.filter((f) => source(f).includes("getReader("));
    expect(readers.sort()).toEqual(["composables/useDeepReadChat.ts", "utils/aiStream.ts", "utils/bookAiPick.ts"]);
  });

  it("AI 글 스트림 주소를 부르는 화면은 모두 {error} 를 아는 읽기(readAiStream·readReasonStream)로 읽는다", () => {
    const STREAMS = ["/papers/summary/stream", "/papers/reason/stream", "/papers/related-reason/stream", "/books/reason/stream"];
    const callers = ALL.filter((f) => STREAMS.some((s) => source(f).includes(`"${s}"`)));
    expect(callers.sort()).toEqual(["pages/books/[cnts_id].vue", "pages/index.vue", "pages/papers/[id].vue", "pages/papers/index.vue"]);
    for (const f of callers) expect(source(f), f).toMatch(/\b(readAiStream|readReasonStream)\(/);
  });
});

describe("논문 검색 AI 요약 — pages/papers/index.vue", () => {
  const src = read("pages/papers/index.vue");

  it("끝까지 받은 요약만 검색 기록(ai)에 저장하고, 실패는 오류 문구로 둔다", () => {
    // 기록 id 가 없으면(저장 전에 끊긴 검색을 [다시 시도]로 다시 받음) 보이기만 하고 저장하지 않는다
    expect(src).toMatch(/if \(end\.ok\) \{\s*if \(text && historyId\) void historyApi\.patch\(historyId, \{ ai: \{ text, refs \} \}\)/);
    expect(src).toContain("aiError.value = failureText(end, AI_SUMMARY_FAILED)");
  });

  // 줄 안내(SkxInlineError — role=alert)가 요약 글과 따로 보이고, 그 [다시 시도]가 같은 기록으로 다시 만든다
  it("오류는 요약 글과 따로 공통 줄 안내로 보이고 [다시 시도]가 같은 기록으로 다시 만든다", () => {
    expect(src).toMatch(/<SkxInlineError\b[^>]*:message="aiError"[^>]*@retry="retryAiSummary"/);
    expect(src).not.toContain('class="skx-retry"');
    expect(src).toMatch(/function retryAiSummary\(\)[\s\S]*?streamAiSummary\(currentHistoryId\.value, resultQuery\.value/);
  });

  // 요약 칸은 ClampedPanel(:collapsed-rem 20) 안이다 — 받은 글이 20rem 을 넘은 뒤 실패하면 접힌 기본 상태에서 안내가 잘려,
  // 페이드와 '전체보기'만 보고 끊긴 요약을 끝까지 받은 것으로 읽었다
  it("실패 안내는 접히는 칸 밖(#after)에 하나만 있어 글이 길어 접혀도 늘 보인다", () => {
    expect(src).toMatch(/<template #after>\s*<SkxInlineError\b[^>]*:message="aiError"/);
    expect(src.match(/:message="aiError"/g)).toHaveLength(1);
    const panel = read("components/ClampedPanel.vue");
    // 접히는 영역(.skx-clamp__clip) 이 닫힌 뒤, [더보기] 띠 앞
    expect(panel).toMatch(
      /class="skx-clamp__clip"[\s\S]*?<slot \/><\/div>\s*<\/div>\s*(?:<!--[\s\S]*?-->\s*)?<slot name="after" \/>\s*<div v-if="overflowing" class="skx-clamp__foot">/,
    );
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

  it("AI 요약 오류는 공통 줄 안내로 보이고 [다시 시도]가 있으며, 글 없이 실패해도 [AI 요약] 탭이 남는다", () => {
    expect(src).toMatch(/<SkxInlineError\b[^>]*:message="summaryError"[^>]*@retry="retrySummary"/);
    expect(src).not.toContain('class="skx-retry"');
    expect(src).toMatch(/key: "ai-summary", label: "AI 요약", available: [^\n]*summaryError\.value/);
  });

  // 실패로 summaryDone 이 된 뒤 [다시 시도]가 글·안내를 비우면, 받는 중을 보지 않는 조건은 첫 글자까지 탭을 뺐다(초록 탭으로 넘어감)
  it("[다시 시도]로 다시 받는 동안에도 [AI 요약] 탭이 남고, 사라지는 버튼의 초점은 탭 본문으로 간다", () => {
    expect(src).toContain(
      "available: aiTabAvailable({ loading: summaryLoading.value, done: summaryDone.value, text: summaryText.value, error: summaryError.value })",
    );
    // 줄 안내의 @retry 는 이벤트를 넘기지 않는다 — 그 안내(ref)의 뿌리 요소에서 탭 본문을 찾는다
    expect(src).toMatch(/<SkxInlineError\b[^>]*ref="summaryFailedRef"/);
    expect(src).toMatch(/function retrySummary\(\)[\s\S]*?focusOwningPanel\(summaryFailedRef\.value\?\.\$el \?\? null\)/);
  });

  it("관련 논문 카드에 추천 사유 오류와 [다시 시도]를 넘긴다", () => {
    expect(src).toContain(':reason-error="relatedReasonErrors[rel.book_id]"');
    expect(src).toContain('@retry-reason="retryRelatedReason(rel.book_id)"');
    // 다시 받을 때 그 카드의 실패 안내와 받다 만 글을 걷는다
    expect(src).toMatch(/function retryRelatedReason\(relatedId: string\)[\s\S]*?relatedReasonErrors\.value = errors;[\s\S]*?relatedReasons\.value = reasons;[\s\S]*?streamRelatedReason\(relatedId\)/);
  });
});

describe("관련 자료 카드 — components/detail/RelatedCard.vue", () => {
  const src = read("components/detail/RelatedCard.vue");

  it("추천 사유 오류(reasonError)를 사유 글과 따로 상자·팝업 모두에 공통 줄 안내로 보인다", () => {
    expect(src).toMatch(/reasonError\?: string;/);
    expect(src.match(/<SkxInlineError\b[^>]*:message="reasonError"/g)).toHaveLength(2);
    expect(src).not.toMatch(/\{\{\s*reasonError\s*\}\}/);
  });

  // 카드 네 장이 한꺼번에 실패할 수 있어 alert(끼어들어 읽음) 대신 status(차례가 오면 읽음) — 공통 줄 안내의 role 을 덮어쓴다
  it("실패 안내는 화면낭독기에 role=status 로 알린다", () => {
    for (const tag of src.match(/<SkxInlineError\b[^>]*\/>/g) ?? []) expect(tag).toContain('role="status"');
    expect(src).not.toContain('role="alert"');
  });

  it("[다시 시도]는 부모가 @retry-reason 을 달았을 때만(소장자료 상세는 달지 않는다)", () => {
    expect(src).toMatch(/onRetryReason\?: \(\) => void;/);
    expect(src.match(/:on-retry="onRetryReason \? retryReason : undefined"/g)).toHaveLength(2);
  });
});

describe("소장자료 상세 추천 이유 — pages/books/[cnts_id].vue", () => {
  const src = read("pages/books/[cnts_id].vue");

  // 서버의 {error} 글(합쇼체)은 쓰지 않고 프런트 문구(해요체 — utils/bookErrors reasonFailureText)를 쓴다. 안내는 공통 줄 안내
  // (SkxInlineError — role=alert, [다시 시도])로 보인다
  it("실패는 공통 줄 안내(SkxInlineError)로 보이고 [다시 시도]가 있으며, 글 없이 실패해도 [추천 이유] 탭이 남는다", () => {
    expect(src).toContain("reasonError.value = reasonFailureText(reasonText.value)");
    expect(src).not.toContain("failureText(end, BOOK_REASON_FAILED)");
    expect(src).toMatch(/<SkxInlineError\s+v-if="reasonError && !reasonLoading"\s+ref="reasonFailRef"\s+:message="reasonError"\s+@retry="retryReason"\s*\/>/);
    expect(src).toMatch(/key: "reason", label: "추천 이유", available: [^\n]*reasonError\.value/);
  });

  it("[다시 시도]로 다시 받는 동안에도 [추천 이유] 탭이 남고, 사라지는 버튼의 초점은 탭 본문으로 간다", () => {
    expect(src).toContain(
      "available: !!searchQuery && aiTabAvailable({ loading: reasonLoading.value, done: reasonDone.value, text: reasonText.value, error: reasonError.value })",
    );
    expect(src).toMatch(/function retryReason\(\)[\s\S]*?focusOwningPanel\(reasonFailRef\.value\?\.\$el \?\? null\)[\s\S]*?streamReason\(\)/);
  });
});

describe("DeepRead 대화 칸 — components/BookChat.vue", () => {
  const src = read("components/BookChat.vue");

  // SkxInlineError 는 role=alert 줄 안내 — 부모가 onRetry 를 넘길 때만 [다시 시도]를 그린다. AI 말풍선(.skx-chat-msg--ai) 안에서는
  // 공통 CSS 가 아이콘·버튼을 말풍선 글자색으로 바꾼다
  it("답을 만들지 못한 질문은 대화와 따로 AI 말풍선 안의 SkxInlineError 로 보이고, 다시 보낼 만할 때만 [다시 시도]가 같은 질문을 다시 보낸다", () => {
    expect(src).toMatch(
      /<div class="skx-chat-msg skx-chat-msg--ai">\s*<div v-if="failure\.partial"[^>]*\/>\s*<SkxInlineError\s+class="skx-chat-msg__failed"\s+:message="failure\.message"\s+:on-retry="failure\.retryable \? retry : undefined"\s*\/>/,
    );
    // 옛 표시(빨간 글로 칠할 수 있던 자체 <p role=alert>·.skx-retry 글자 버튼)는 남지 않는다
    expect(src).not.toContain("skx-retry");
    expect(src).not.toContain('role="alert"');
  });

  // 다른 AI 글 화면(논문 검색·상세 요약·추천 이유·관련 카드 팝업)처럼 받던 글을 남기고 그 아래에 안내를 둔다 — 대화(messages·store)
  // 에는 넣지 않는다. 받던 글은 안내(role=alert) 밖이라 알림이 긴 글을 다시 읽지 않는다
  it("글 일부를 받은 뒤 실패하면 받던 글을 흐리게 실패 말풍선에 남기고, 안내만 role=alert 다", () => {
    expect(src).toMatch(/<div v-if="failure\.partial" class="skx-chat-msg__partial" v-html="formatText\(failure\.partial\)" \/>/);
    expect(src).not.toMatch(/role="alert"[^>]*>\s*<div v-if="failure\.partial"/);
  });

  it("실패했을 때는 앞 답을 화면낭독기에 다시 읽히지 않는다", () => {
    expect(src).toMatch(/if \(!failure\.value && last\?\.role === "assistant"\)/);
  });

  // 서버 BookChatRequest.message 는 max_length=2000(422) — 입력 칸이 미리 막고 얼마나 썼는지 보인다
  // 질문 칸의 글자 수는 검색창처럼 한도 가까이(90%)부터만 보인다(사용자 결정 2026-10-16) — quiet 는 평소 화면에서만 숨기고 낭독기
  // 알림 영역·aria-describedby 는 남긴다(v-if 로 붙였다 떼지 않는다)
  it("입력 칸은 서버 한도(CHAT_MAX_CHARS)까지 — maxlength 와 글자 수(SkxCharCount quiet)를 aria-describedby 로 잇는다", () => {
    expect(src).toMatch(
      /<textarea[\s\S]*?:maxlength="CHAT_MAX_CHARS"[\s\S]*?:aria-describedby="countId"[\s\S]*?\/>\s*<SkxCharCount :id="countId" class="skx-chat-count" quiet :length="inputText\.length" :max="CHAT_MAX_CHARS" \/>/,
    );
    expect(src).not.toMatch(/<SkxCharCount[^>]*v-if/);
  });

  it("답을 받지 못하면 보낸 질문을 입력 칸에 되살리고(보낼 때 비운 칸), [다시 시도]는 되살린 그 질문을 칸에서 비운다", () => {
    expect(src).toMatch(
      /if \(failure\.value && !inputText\.value\.trim\(\)\) \{\s*inputText\.value = failure\.value\.question;\s*restoredQuestion = failure\.value\.question;\s*\}/,
    );
    expect(src).toMatch(/async function retry\(\)[\s\S]*?if \(inputText\.value\.trim\(\) === failure\.value\?\.question\) inputText\.value = "";/);
  });

  it("되살린 질문은 논문을 바꾸면 칸에서 비운다 — 고쳐 쓴 글은 둔다, 새로 보내면 되살린 표시를 지운다", () => {
    expect(src).toMatch(
      /watch\(\s*\(\) => props\.cntsId,\s*\(\) => \{\s*if \(restoredQuestion !== null && inputText\.value\.trim\(\) === restoredQuestion\) inputText\.value = "";\s*restoredQuestion = null;\s*\},?\s*\);/,
    );
    expect(src).toMatch(/async function ask\(request: \(\) => Promise<void>\) \{\s*liveHtml\.value = "";\s*restoredQuestion = null;/);
  });

  // Enter 를 누른 채 보내면 초점이 [멈춤]으로 옮겨 오고 자동 반복 keydown 이 키보드 click(detail 0)이 되어 바로 멈췄다
  it("누른 채 있는 Enter 의 자동 반복은 누름이 아니다 — 질문 칸은 다시 보내지 않고, [멈춤]은 click 을 막는다", () => {
    expect(src).toContain('@keydown.enter.exact.prevent="onInputEnter"');
    expect(src).toMatch(/function onInputEnter\(e: KeyboardEvent\) \{\s*if \(!e\.repeat\) void send\(\);\s*\}/);
    expect(src).toMatch(/@click="onSendButton"\s+@keydown\.enter="onSendKeydown"/);
    expect(src).toMatch(/function onSendKeydown\(e: KeyboardEvent\) \{\s*if \(e\.repeat\) e\.preventDefault\(\);\s*\}/);
  });

  it("답을 받는 동안 보내기 단추가 [멈춤](stop)이 된다 — 더블클릭의 둘째 누름은 무시하고, Enter 로 보내 떨어진 초점은 그 단추로", () => {
    expect(src).toMatch(/stop: stopChat,?\s*\}\s*=\s*useDeepReadChat\(/);
    expect(src).toContain(':aria-label="isStreaming ? copy.stopLabel : copy.sendLabel"');
    expect(src).toContain(':disabled="!isStreaming && !inputText.trim()"');
    expect(src).toMatch(/function onSendButton\(e: MouseEvent\) \{\s*if \(!isStreaming\.value\) void send\(\);\s*else if \(e\.detail < 2\) stopChat\(\);/);
    expect(src).toContain("if (isStreaming.value && (!active || active === document.body || active === inputEl.value)) sendEl.value?.focus();");
  });
});
