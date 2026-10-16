// frontend/tests/unit/paperErrors.test.ts
// 논문 검색·결과 목록·논문 상세·출처 인용의 오류 처리(2단계 — 영역 paper).
//  - utils/paperErrors: 화면이 쥐는 오류(shownError — 일부러 끊은 요청은 null, 설명 줄은 이유만), [다시 시도] 를 달 kind, 문구(해요체·줄바꿈)
//  - utils/clipboard: http 운영(Clipboard API 없음)에서 글을 선택해 옛 방식으로 복사, 그것도 안 되면 선택을 남긴 채 false
//  - 화면(Nuxt 없이 돌지 않는다)은 소스 글로 고정한다(aiStreamConsumers.test 와 같은 방식)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ERROR_HINTS, VALIDATION_HINTS } from "~/utils/apiErrors";
import { copySelection, copyToClipboard } from "~/utils/clipboard";
import * as paperErrors from "~/utils/paperErrors";
import { PAPER_STATE_TEXT, isRetryableKind, shownError } from "~/utils/paperErrors";
import { SEARCH_QUERY_MAX } from "~/utils/searchInput";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8");

/** ofetch FetchError 모양 — 영문 message 는 화면에 절대 나오면 안 되는 값 */
const ENGLISH = '[POST] "/api/papers/search": 500 Internal Server Error';
function fetchError(status: number | undefined, data?: unknown) {
  return Object.assign(new Error(ENGLISH), { name: "FetchError", status, statusCode: status, data });
}

describe("shownError — 화면이 쥐는 오류(kind·이유)", () => {
  it("새 검색·페이지 떠남으로 일부러 끊은 요청은 null(아무것도 띄우지 않는다)", () => {
    expect(shownError(new DOMException("The operation was aborted.", "AbortError"))).toBeNull();
    expect(shownError(Object.assign(new Error("aborted"), { name: "FetchError", cause: new DOMException("x", "AbortError") }))).toBeNull();
  });

  it("평문 본문의 500(잡지 않은 서버 예외)은 server — 영문 ofetch 메시지 대신 이유(ERROR_HINTS.server)", () => {
    const shown = shownError(fetchError(500, "Internal Server Error"));
    expect(shown).toEqual({ kind: "server", message: ERROR_HINTS.server });
    expect(shown?.message).not.toMatch(/POST|Internal|api/);
  });

  it("게이트웨이 504·연결 끊김·검색 제한(60초) 초과는 시간 초과·네트워크 이유", () => {
    expect(shownError(fetchError(504))).toEqual({ kind: "timeout", message: ERROR_HINTS.timeout });
    expect(shownError(Object.assign(new Error('<no response> Failed to fetch'), { name: "FetchError", cause: new TypeError("Failed to fetch") })))
      .toEqual({ kind: "network", message: ERROR_HINTS.network });
    const timedOut = Object.assign(new Error("signal timed out"), { name: "TimeoutError" });
    expect(shownError(Object.assign(new Error("x"), { name: "FetchError", cause: timedOut }))).toEqual({ kind: "timeout", message: ERROR_HINTS.timeout });
  });

  it("검색어 500자 초과(422 배열)는 배열 원문 대신 글자 수 안내", () => {
    const shown = shownError(fetchError(422, { detail: [{ type: "string_too_long", loc: ["body", "query"], msg: "String should have at most 500 characters", ctx: { max_length: 500 } }] }));
    expect(shown).toEqual({ kind: "invalid", message: VALIDATION_HINTS.tooLong.replace("{n}", "500") });
  });

  it("없는 논문(404 '도서 없음: KCI…')은 notFound — 서버의 개발자용 문구도, '요청을 처리하지 못했어요'도 설명 줄에 두지 않는다", () => {
    expect(shownError(fetchError(404, { detail: "도서 없음: KCI_FI003141592" }))).toEqual({ kind: "notFound", message: "" });
  });

  it("백엔드 code(search_unavailable)가 오면 그 문구가 이유", () => {
    const shown = shownError(fetchError(503, { detail: "검색 서버가 잠시 응답하지 않습니다", code: "search_unavailable" }));
    expect(shown?.kind).toBe("busy");
    expect(shown?.message).toBe("검색 서버가 잠시 응답하지 않아요.\n잠시 뒤 다시 시도해 주세요.");
  });
});

describe("isRetryableKind — [다시 시도] 를 달 만한 오류", () => {
  it("찾을 수 없음·입력 거절은 다시 보내도 같은 결과라 달지 않는다", () => {
    expect(isRetryableKind("notFound")).toBe(false);
    expect(isRetryableKind("invalid")).toBe(false);
  });

  it.each(["network", "timeout", "busy", "server", "conflict", "forbidden", "unknown"] as const)("%s 는 단다", (kind) => {
    expect(isRetryableKind(kind)).toBe(true);
  });
});

describe("문구 — 해요체, 두 문장 이상은 문장마다 줄을 바꾼다", () => {
  const entries = Object.entries(PAPER_STATE_TEXT);

  it.each(entries)("%s: 합쇼체·'~하세요'가 없다", (_key, text) => {
    expect(text).not.toMatch(/습니다|하세요|십시오/);
  });

  it.each(entries)("%s: 한 줄에 두 문장을 잇지 않는다", (_key, text) => {
    expect(text).not.toMatch(/[.?!] \S/);
  });

  it.each(entries.filter(([, t]) => t.includes("\n")))("%s: 여러 줄이면 줄마다 마침표로 끝난다", (_key, text) => {
    for (const line of text.split("\n")) expect(line).toMatch(/[.?!…]$/);
  });

  it("토스트 문구(없는 기록)는 한 문장 — 토스트는 한 줄(nowrap)이라 '\\n' 이 보이지 않는다. 소장자료 랜딩의 같은 토스트와 같은 말", () => {
    expect(PAPER_STATE_TEXT.missingHistory).toBe("없는 기록이라 목록을 새로 고쳤어요.");
    expect(PAPER_STATE_TEXT.missingHistory).not.toContain("\n");
  });

  it("논문 404 설명은 주소 확인을 시키지 않고 사실만 — 앱 안 링크로 왔는데 카탈로그에 그 논문이 없다", () => {
    expect(PAPER_STATE_TEXT.detailNotFoundHint).toBe("목록에서 빠졌거나 아직 등록되지 않은 논문이에요.");
    expect(Object.values(PAPER_STATE_TEXT).join("\n")).not.toMatch(/주소가 맞는지/);
  });

  it("오류 화면 모음의 본보기 제목과 같은 말(검색 실패·상세 실패·결과 없음)", () => {
    const gallery = read("pages/dev/error-states.vue");
    for (const title of [PAPER_STATE_TEXT.searchFailed, PAPER_STATE_TEXT.detailFailed, PAPER_STATE_TEXT.searchEmpty, PAPER_STATE_TEXT.searchEmptyHint]) {
      expect(gallery, title).toContain(`"${title}"`);
    }
  });
});

describe("SEARCH_QUERY_MAX — 서버 검색어 한도와 같다", () => {
  it("한 곳(utils/searchInput)에만 둔다 — paperErrors 는 내보내지 않고, 논문 화면은 searchInput 에서 가져다 쓴다", () => {
    expect("SEARCH_QUERY_MAX" in paperErrors).toBe(false);
    expect(read("utils/searchInput.ts")).toMatch(
      /\/\/ 검색어 글자 수 한도 — 서버 SearchRequest\.query max_length 와 같다\r?\nexport const SEARCH_QUERY_MAX = 500;/,
    );
    for (const file of ["pages/papers/index.vue", "components/detail/SearchBar.vue"]) {
      expect(read(file), file).toMatch(/import \{ hasQuery, SEARCH_QUERY_MAX \} from "~\/utils\/searchInput";/);
    }
  });

  it("app/schemas/book.py SearchRequest.query 의 max_length·연구 질문 한도와 같은 500", () => {
    expect(SEARCH_QUERY_MAX).toBe(500);
    const schema = readFileSync(resolve(root, "../app/schemas/book.py"), "utf-8");
    expect(schema).toMatch(/query:\s*str\s*=\s*Field\(\.\.\., min_length=1, max_length=500/);
    const research = readFileSync(resolve(root, "../app/api/research.py"), "utf-8");
    expect(research).toMatch(/question: str = Field\(min_length=2, max_length=500\)/);
  });
});

// ── 클립보드 ──

/** 선택·execCommand 를 흉내 내는 최소 DOM */
function fakeDom(execResult: boolean | "throw") {
  const ranges: unknown[] = [];
  const selection = {
    removeAllRanges: vi.fn(() => ranges.splice(0)),
    addRange: vi.fn((r: unknown) => ranges.push(r)),
  };
  const range = { selectNodeContents: vi.fn() };
  const execCommand = vi.fn(() => {
    if (execResult === "throw") throw new Error("not allowed");
    return execResult;
  });
  vi.stubGlobal("window", { getSelection: () => selection });
  vi.stubGlobal("document", { createRange: () => range, execCommand });
  return { selection, range, execCommand, ranges };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("copyToClipboard — Clipboard API, 없으면 글을 선택해 옛 방식으로", () => {
  const source = {} as Element;

  it("Clipboard API 가 있으면 그것으로 쓴다(옛 방식은 쓰지 않는다)", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const dom = fakeDom(true);
    await expect(copyToClipboard("인용문", source)).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith("인용문");
    expect(dom.execCommand).not.toHaveBeenCalled();
  });

  it("http 운영(보안 컨텍스트가 아님 — navigator.clipboard 없음)이면 그 글을 선택해 execCommand('copy') 로 복사하고 선택을 푼다", async () => {
    vi.stubGlobal("navigator", {});
    const dom = fakeDom(true);
    await expect(copyToClipboard("인용문", source)).resolves.toBe(true);
    expect(dom.range.selectNodeContents).toHaveBeenCalledWith(source);
    expect(dom.execCommand).toHaveBeenCalledWith("copy");
    expect(dom.ranges).toHaveLength(0);
  });

  it("옛 방식으로 복사했으면 사용자가 그 전에 잡아 둔 선택을 되살린다(복제한 범위로)", async () => {
    vi.stubGlobal("navigator", {});
    const dom = fakeDom(true);
    const userRange = { cloneRange: vi.fn(() => "사용자 선택(복제)") };
    Object.assign(dom.selection, { rangeCount: 1, getRangeAt: vi.fn(() => userRange) });
    await expect(copyToClipboard("인용문", source)).resolves.toBe(true);
    expect(dom.execCommand).toHaveBeenCalledWith("copy");
    expect(dom.ranges).toEqual(["사용자 선택(복제)"]);
  });

  it("옛 방식도 안 되면 원래 선택 대신 그 글을 선택해 둔다(직접 복사하게)", () => {
    const dom = fakeDom(false);
    const userRange = { cloneRange: vi.fn(() => "사용자 선택(복제)") };
    Object.assign(dom.selection, { rangeCount: 1, getRangeAt: vi.fn(() => userRange) });
    expect(copySelection(source)).toBe(false);
    expect(dom.ranges).toEqual([dom.range]);
  });

  it("Clipboard API 가 거절하면(권한) 옛 방식으로 한 번 더", async () => {
    vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("NotAllowedError")) } });
    const dom = fakeDom(true);
    await expect(copyToClipboard("인용문", source)).resolves.toBe(true);
    expect(dom.execCommand).toHaveBeenCalledWith("copy");
  });

  it("둘 다 안 되면 false — 글은 선택된 채 남아 사용자가 직접 복사할 수 있다", async () => {
    vi.stubGlobal("navigator", {});
    const dom = fakeDom(false);
    await expect(copyToClipboard("인용문", source)).resolves.toBe(false);
    expect(dom.ranges).toHaveLength(1);
  });

  it("execCommand 가 던져도 false(선택은 남는다)", () => {
    const dom = fakeDom("throw");
    expect(copySelection(source)).toBe(false);
    expect(dom.ranges).toHaveLength(1);
  });

  it("선택할 글이 없으면 false", () => {
    fakeDom(true);
    expect(copySelection(null)).toBe(false);
  });
});

// ── 화면 소스 ──

describe("논문 검색 — pages/papers/index.vue", () => {
  const src = read("pages/papers/index.vue");

  it("검색 POST 는 검색 제한(60초)에서 끊는다", () => {
    expect(src).toMatch(/api<BookSearchResponse>\("\/papers\/search", \{[\s\S]*?signal,[\s\S]*?timeout: API_SEARCH_TIMEOUT_MS,[\s\S]*?\}\);/);
  });

  it("실패는 서버 detail·ofetch 영문 메시지 대신 shownError, 결과 자리에 상태 블록 + 같은 검색의 [다시 시도]", () => {
    expect(src).toContain("searchError.value = shownError(e)");
    expect(src).not.toMatch(/e\?\.message|e\?\.data\?\.detail/);
    expect(src).not.toContain("color: #c00");
    expect(src).toMatch(/<SkxErrorState\s+v-else-if="searchError"[\s\S]*?:title="PAPER_STATE_TEXT\.searchFailed"[\s\S]*?:on-retry="isRetryableKind\(searchError\.kind\) \? retrySearch : undefined"/);
    expect(src).toMatch(/function retrySearch\(\)[\s\S]*?handleSearch\(query, reuse\)/);
  });

  it("0건은 실패와 가른 빈 상태(kind=empty), 요약할 논문이 없으니 AI 요약 칸은 그리지 않는다", () => {
    expect(src).toMatch(/<SkxErrorState\s+v-if="!filteredPapers\.length"\s+kind="empty"/);
    expect(src).not.toContain("검색 결과가 없습니다");
    expect(src).toContain('<AiResultPanel v-if="paperResult?.books.length"');
  });

  it("랜딩 입력 상자·결과 검색바는 500자까지 받고 글자 수를 aria-describedby 로 잇는다 — 글자 수는 한도 가까이부터만(quiet)", () => {
    expect(src.match(/:maxlength="SEARCH_QUERY_MAX"/g)).toHaveLength(2);
    expect(src).toMatch(/<textarea[\s\S]*?:aria-describedby="landingCountId"[\s\S]*?<SkxCharCount quiet :id="landingCountId" :length="currentQuery\.length" :max="SEARCH_QUERY_MAX" \/>/);
    expect(src).toMatch(/<input[\s\S]*?:aria-describedby="barCountId"[\s\S]*?\/>\s*<SkxCharCount quiet :id="barCountId" :length="currentQuery\.length" :max="SEARCH_QUERY_MAX" \/>/);
    // 한 입력에 글자 수 하나 — 늘 보이는 글자 수가 남지 않았다
    expect(src.match(/<SkxCharCount\b/g)).toHaveLength(2);
    expect(src).not.toMatch(/<SkxCharCount (?!quiet)/);
  });

  it("공통 규칙(.skx-search__actions — 가운데 맞춤·gap)과 겹치던 scoped 규칙은 없다", () => {
    const style = src.slice(src.indexOf("<style scoped>"));
    expect(style).not.toContain(".skx-search__actions");
  });

  it("검색이 끝나 결과가 있으면 기록 저장을 기다리기 전에 '분석 중'으로 둔다('AI 요약이 없어요'가 먼저 보이지 않게)", () => {
    expect(src).toMatch(
      /paperResult\.value = data;\s*loading\.value = false;[\s\S]*?if \(data\.books\?\.length\) aiLoading\.value = true;[\s\S]*?await historyApi\.add\(/,
    );
    // 실패하면 그 표시를 걷는다
    expect(src).toMatch(/paperResult\.value = \{ mode: "book", query, books: \[\], elapsed_ms: 0 \};\s*aiLoading\.value = false;/);
  });

  it("[다시 시도](검색 실패·AI 요약 실패)는 버튼이 빠지기 전에 감싸는 자리로 초점을 옮긴다 — 키보드로 왔을 때만 테두리", () => {
    expect(src).toContain('<div ref="frameRef" class="skx-rframe" tabindex="-1">');
    expect(src).toMatch(/function retrySearch\(\) \{[\s\S]*?frameRef\.value\?\.focus\(\);\s*void handleSearch\(query, reuse\);/);
    expect(src).toMatch(/<ClampedPanel\s+ref="aiMainRef"[^>]*class="skx-pai-main"\s+tabindex="-1"/);
    expect(src).toMatch(/function retryAiSummary\(\) \{[\s\S]*?\(aiMainRef\.value\?\.\$el as HTMLElement \| undefined\)\?\.focus\(\);\s*const signal = beginRun\(\);/);
    const style = src.slice(src.indexOf("<style scoped>"));
    expect(style).toMatch(/\.skx-rframe:focus,\s*\.skx-pai-main:focus \{\s*outline: none;/);
    expect(style).toMatch(/\.skx-rframe:focus-visible,\s*\.skx-pai-main:focus-visible \{\s*outline: 2px solid var\(--skx-accent\);/);
  });

  it("AI 요약이 글 없이 실패하면 참고 목록을 결과 카드의 'AI 답변 인용' 칩·위로 고정에 쓰지 않는다(오른쪽 참고 칸에는 그대로)", () => {
    expect(src).toContain("const aiCited = computed(() => !aiError.value || !!aiText.value.trim());");
    expect(src).toMatch(/const aiRefNumMap = computed\(\(\) => \{\s*const m = new Map<string, number>\(\);\s*if \(!aiCited\.value\) return m;/);
    // 칩(aiCitedNum)·고정(filteredPapers) 모두 aiRefNumMap 하나로 정한다
    expect(src).toContain(':ai-cited-num="aiRefNumMap.get(paper.book_id) ?? null"');
    expect(src).toMatch(/const filteredPapers = computed\(\(\) => \{[\s\S]*?if \(!aiRefNumMap\.value\.size\) return base;/);
    // 참고 목록은 끝난 뒤 실패 여부와 함께 한 번에 건다 — 두 이벤트 사이에 카드가 올라갔다 내려오지 않게
    expect(src).toContain("if (Array.isArray(evt.sources)) refs = evt.sources;");
    expect(src).toMatch(/if \(signal\.aborted\) return;\s*aiLoading\.value = false;\s*aiRefs\.value = refs;/);
  });

  it("없는 기록 토스트로 끝나는 복원은 끊긴 요약을 '분석 중'으로 남기지 않는다", () => {
    expect(src).toMatch(/settleAiSummary\(\);\s*showToast\(PAPER_STATE_TEXT\.missingHistory\);/);
    expect(src).toMatch(/function settleAiSummary\(\) \{\s*if \(!aiLoading\.value\) return;\s*aiLoading\.value = false;\s*aiError\.value = AI_SUMMARY_FAILED;/);
  });

  it("결과 카드의 [원문 보기]는 누른 카드에만 aria-busy", () => {
    expect(src).toContain(':pdf-busy="checkingPdfId === paper.book_id"');
    expect(src).not.toContain(':pdf-busy="checkingPdf"');
    expect(src).toMatch(/checkingPdfId\.value = paper\.book_id;[\s\S]*?finally \{\s*checkingPdfId\.value = null;/);
  });

  it("결과 카드의 [원문 보기]는 파일을 확인한 뒤 열고, 없으면 그 카드에 알린다", () => {
    expect(src).toContain('@pdf="openResultPdf(paper)"');
    expect(src).toMatch(/async function openResultPdf\(paper: BookChunkGroup\)[\s\S]*?await openPdf\(\{ cntsId: paper\.book_id/);
    expect(src).toContain(":pdf-problem=\"resultPdfProblem?.id === paper.book_id ? resultPdfProblem.message : ''\"");
    expect(src).toMatch(/<PdfViewer\s+v-if="pdf"/);
    expect(src).not.toContain("pdfItem");
  });

  it("요약 인용 팝오버의 [원문 보기]는 팝오버가 확인한 뒤에만 뷰어를 연다", () => {
    expect(src).toContain('@pdf="openCheckedPdf"');
  });

  it("옛 합쇼체 오류·빈 문구가 남지 않았다", () => {
    for (const old of ["검색 중 오류가 발생했습니다", "AI 요약 정보가 없습니다", "없는 기록입니다"]) expect(src, old).not.toContain(old);
  });
});

describe("상세 검색바 — components/detail/SearchBar.vue", () => {
  const src = read("components/detail/SearchBar.vue");

  it("500자까지 받고 글자 수를 보내기 왼쪽에(한도 가까이부터만 — quiet), 입력창이 aria-describedby 로 가리킨다", () => {
    expect(src).toContain(':maxlength="SEARCH_QUERY_MAX"');
    expect(src).toContain(':aria-describedby="countId"');
    expect(src).toMatch(/<SkxCharCount quiet :id="countId" :length="text\.length" :max="SEARCH_QUERY_MAX" \/>\s*<button type="submit" class="skx-send"/);
  });
});

describe("논문 상세 — pages/papers/[id].vue", () => {
  const src = read("pages/papers/[id].vue");

  it("논문 읽기 실패는 상태 블록 — 404 는 '찾을 수 없음'(다시 시도 없음), 그 밖은 [다시 시도], 둘 다 돌아가기", () => {
    expect(src).toMatch(/const shown = shownError\(e\);\s*if \(shown\) paperError\.value = shown;/);
    expect(src).toMatch(/<SkxErrorState\s+v-else-if="paperError"[\s\S]*?:title="paperError\.kind === 'notFound' \? PAPER_STATE_TEXT\.detailNotFound : PAPER_STATE_TEXT\.detailFailed"[\s\S]*?:on-retry="isRetryableKind\(paperError\.kind\) \? retryPaper : undefined"[\s\S]*?<a :href="back\.to" class="skx-state__action" @click="onBack">\{\{ back\.label \}\}<\/a>/);
    expect(src).not.toContain("논문 정보를 불러오지 못했습니다");
  });

  it("논문을 읽지 못하면 관련 자료·요약은 받지 않고, [다시 시도]가 처음부터 다시 돈다", () => {
    expect(src).toMatch(/async function loadPage\(\)[\s\S]*?await fetchPaper\(\);\s*if \(!paper\.value\) \{/);
    expect(src).toMatch(/function retryPaper\(\)[\s\S]*?loadPage\(\)/);
  });

  it("관련 자료 실패를 빈 catch 로 삼키지 않고, 실패(compact + [다시 시도])와 0건(empty)을 가른다", () => {
    expect(src).not.toContain("/* silent */");
    expect(src).toMatch(/<SkxErrorState\s+v-else-if="relatedError"\s+compact[\s\S]*?:title="PAPER_STATE_TEXT\.relatedFailed"[\s\S]*?:on-retry="isRetryableKind\(relatedError\.kind\) \? retryRelated : undefined"/);
    expect(src).toMatch(/<SkxErrorState v-else-if="!relatedItems\.length" kind="empty" compact :title="PAPER_STATE_TEXT\.relatedEmpty" \/>/);
  });

  it("원문을 열지 못한 까닭은 세 곳(머리·인용 배너·관련 카드 팝업) 모두 공통 줄 안내 — 빨간 .dt-note 는 없다", () => {
    expect(src.match(/<SkxInlineError\s+v-if="(pdfProblem|bannerPdfProblem|relatedPdfProblem\?\.id === rel\.book_id)"/g)).toHaveLength(3);
    expect(src).not.toMatch(/dt-note|dt-error/);
    expect(src.match(/\{\{ PAPER_STATE_TEXT\.kciOriginal \}\}/g)).toHaveLength(2);
  });

  it("원문 파일을 확인하는 동안 누른 버튼에만 aria-busy(머리·인용 배너·관련 카드), 관련 카드의 [원문 보기]는 열지 못한 까닭을 가리킨다", () => {
    expect(src).not.toContain(':aria-busy="checkingPdf"');
    expect(src).toContain(":aria-busy=\"pdfCheckingAt === 'banner' ? 'true' : undefined\"");
    expect(src).toContain(":aria-busy=\"pdfCheckingAt === 'original' ? 'true' : undefined\"");
    expect(src).toContain(":aria-busy=\"pdfCheckingAt === `related:${rel.book_id}` ? 'true' : undefined\"");
    expect(src).toMatch(/async function checkPdfAt\(at: string, target: OpenPdfPayload\)[\s\S]*?pdfCheckingAt\.value = at;[\s\S]*?finally \{\s*pdfCheckingAt\.value = null;/);
    expect(src).toContain('await checkPdfAt("original", ');
    expect(src).toContain('await checkPdfAt("banner", ');
    expect(src).toContain("await checkPdfAt(`related:${rel.book_id}`, ");
    expect(src).toContain(':aria-describedby="relatedPdfProblem?.id === rel.book_id ? relatedProblemId(rel.book_id) : undefined"');
    expect(src).toMatch(/<SkxInlineError\s+v-if="relatedPdfProblem\?\.id === rel\.book_id"\s+:id="relatedProblemId\(rel\.book_id\)"/);
  });

  it("빈 상태(요약·큐레이션·참고문헌)도 공통 상태 블록이고 옛 합쇼체 문구가 남지 않았다", () => {
    for (const key of ["summaryEmpty", "curationEmpty", "referencesEmpty"]) {
      expect(src, key).toMatch(new RegExp(`<SkxErrorState\\b[^>]*kind="empty"[^>]*:title="PAPER_STATE_TEXT\\.${key}"`));
    }
    for (const old of ["AI 분석 정보가 없습니다", "AI 큐레이션 정보가 없습니다", "참고문헌 정보가 없습니다", "관련 자료가 없습니다", "추천 사유 정보가 없습니다"]) {
      expect(src, old).not.toContain(old);
    }
  });
});

describe("토스트 — 논문 검색·논문 상세", () => {
  it.each(["pages/papers/index.vue", "pages/papers/[id].vue"])("%s: 화면 낭독기가 읽는다(role=status, aria-live=polite)", (file) => {
    const toasts = [...read(file).matchAll(/<div v-if="toast" class="skx-toast"[^>]*>/g)].map((m) => m[0]);
    expect(toasts).toEqual(['<div v-if="toast" class="skx-toast" role="status" aria-live="polite">']);
  });
});

describe("결과 카드 — components/ResultCard.vue", () => {
  const src = read("components/ResultCard.vue");

  it("원문을 열지 못한 까닭(pdfProblem)을 카드 아래 공통 줄 안내로, 누름이 카드(상세 이동)로 번지지 않게", () => {
    expect(src).toMatch(/pdfProblem\?: string;/);
    expect(src).toMatch(/<div v-if="pdfProblem" :id="noteId" class="skx-rc__note" @click\.stop>\s*<SkxInlineError :message="pdfProblem">/);
    expect(src).toContain(':aria-busy="pdfBusy ? \'true\' : undefined"');
  });
});

describe("요약 인용 팝오버 — components/CitePopover.vue", () => {
  const src = read("components/CitePopover.vue");

  it("[원문 보기]는 usePdfOpener 로 파일을 확인한 뒤에만 pdf 를 알리고, 없으면 카드 안에 줄 안내", () => {
    expect(src).toContain('import { usePdfOpener } from "~/composables/usePdfOpener"');
    expect(src).toMatch(/async function openPdf\(\)[\s\S]*?await checkPdf\(\{ cntsId: props\.item\.id[\s\S]*?if \(!alive\) return;[\s\S]*?emit\("pdf"\);/);
    expect(src).toMatch(/<SkxInlineError v-if="pdfProblem"/);
    expect(src).not.toContain("@click=\"emit('pdf')\"");
  });

  it("SummaryText 가 그 논문의 id 를 넘긴다", () => {
    expect(read("components/SummaryText.vue")).toContain("id: active.book_id");
  });
});

describe("출처 인용 창 — components/CitationModal.vue", () => {
  const src = read("components/CitationModal.vue");

  it("조회 실패를 인용문 자리(korean)에 넣지 않고 따로 — 상태 블록 + [다시 시도], 복사 버튼은 숨긴다", () => {
    expect(src).not.toContain("인용 정보를 불러오지 못했습니다");
    expect(src).not.toMatch(/korean:\s*"/);
    expect(src).toContain("loadError.value = shownError(e)");
    expect(src).toMatch(/<SkxErrorState\s+v-if="loadError"\s+compact[\s\S]*?:title="PAPER_STATE_TEXT\.citationFailed"[\s\S]*?:on-retry="isRetryableKind\(loadError\.kind\) \? retryCitation : undefined"/);
    expect(src).toContain('<button v-if="citeText && !loadError"');
  });

  it("클립보드는 copyToClipboard(옛 방식 대체 포함)로 쓰고, 못 쓰면 그 칸 아래에 '직접 복사해 주세요'", () => {
    expect(src).not.toContain("navigator.clipboard");
    expect(src).toContain("await copyToClipboard(text, source)");
    expect(src.match(/<SkxInlineError v-if="copyFailed === '(refs|cite)'" :message="PAPER_STATE_TEXT\.copyFailed" \/>/g)).toHaveLength(2);
  });

  it("[다시 시도] 뒤 초점을 받는 인용 칸은 키보드로 왔을 때 초점 테두리가 보인다(늘 지우지 않는다)", () => {
    expect(src).toContain('<div ref="citeBlockEl" class="cm-block" tabindex="-1">');
    expect(src).toMatch(/\.cm-block:focus-visible \{\s*outline: 2px solid var\(--skx-accent\);/);
  });

  it("늦게 온 응답이 다시 연 창을 덮지 않는다(마지막 요청만)", () => {
    expect(src).toMatch(/const seq = \+\+loadSeq;[\s\S]*?if \(seq !== loadSeq\) return;/);
  });
});

describe("상세 틀 CSS — assets/css/detail.css", () => {
  const css = read("assets/css/detail.css").replace(/\/\*[\s\S]*?\*\//g, "");

  it("빨간 오류 글이 없다(.dt-note 는 지웠고 .dt-error 도 위험색을 쓰지 않는다)", () => {
    expect(css).not.toContain("--skx-danger");
    expect(css).not.toMatch(/\.dt-note\b/);
  });
});
