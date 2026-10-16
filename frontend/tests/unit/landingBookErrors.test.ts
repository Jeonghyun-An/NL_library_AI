// frontend/tests/unit/landingBookErrors.test.ts
// 랜딩·소장자료 검색·SKOVIX 추천 1권·도서 상세·상황별 추천·보존 화면(/search-classic)의 오류·빈 상태(에러 처리 2단계, 2026-10-16).
// 문구·판정은 utils/bookErrors.ts 의 순수 함수로 돌려 보고, 화면은 Nuxt 없이 돌지 않아 소스 글로 고정한다(aiStreamConsumers.test 와 같은 방식)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CODE_MESSAGES, DEFAULT_ERROR_MESSAGE, ERROR_HINTS, charLimitMessage } from "~/utils/apiErrors";
import {
  BOOK_DETAIL_TEXT,
  BOOK_REASON_TEXT,
  BOOK_SEARCH_TEXT,
  SCENARIO_TEXT,
  SEARCH_QUERY_MAX,
  failureView,
  reasonFailureText,
  scenarioAiFailed,
} from "~/utils/bookErrors";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8");

/** $fetch 오류 모양 — 영문 message 는 화면에 절대 나오면 안 되는 값으로 둔다 */
const ENGLISH = 'FetchError: [POST] "/api/books/search": 502 Bad Gateway';
function fetchError(status: number | undefined, data?: unknown) {
  return Object.assign(new Error(ENGLISH), { status, statusCode: status, data });
}
/** 응답 없이 끝난 요청(ofetch FetchError — 상태 없음, cause 에 원래 오류) */
const offline = Object.assign(new Error('[POST] "/api/books/search": <no response> Failed to fetch'), {
  name: "FetchError",
  cause: new TypeError("Failed to fetch"),
});
const aborted = Object.assign(new Error("aborted"), { name: "FetchError", cause: new DOMException("aborted", "AbortError") });

describe("검색어 글자 수 한도", () => {
  it("서버 SearchRequest.query 의 max_length 와 같다(app/schemas/book.py)", () => {
    const schema = readFileSync(resolve(root, "../app/schemas/book.py"), "utf-8");
    const m = schema.match(/class SearchRequest\b[\s\S]*?query:\s*str\s*=\s*Field\([^)]*max_length=(\d+)/);
    expect(Number(m?.[1])).toBe(SEARCH_QUERY_MAX);
  });
});

describe("failureView — 요청 실패를 상태 블록으로", () => {
  it("일부러 끊은 요청(새 검색·화면 떠남)이면 null — 아무것도 띄우지 않는다", () => {
    expect(failureView(aborted, BOOK_SEARCH_TEXT.failedTitle)).toBeNull();
    expect(failureView(new DOMException("aborted", "AbortError"), BOOK_SEARCH_TEXT.failedTitle)).toBeNull();
  });

  it("제목은 무엇을 못 했는지, 설명 줄은 이유만(대체 문구를 비워 apiErrorMessage) — 영문 ofetch 메시지는 나오지 않는다", () => {
    const busy = failureView(fetchError(503), BOOK_SEARCH_TEXT.failedTitle);
    expect(busy).toEqual({ kind: "busy", title: "검색하지 못했어요", message: ERROR_HINTS.busy, retry: true });
    const gateway = failureView(fetchError(502, "<html>Bad Gateway</html>"), BOOK_SEARCH_TEXT.failedTitle);
    expect(gateway).toEqual({ kind: "server", title: "검색하지 못했어요", message: ERROR_HINTS.server, retry: true });
    expect(failureView(offline, BOOK_SEARCH_TEXT.failedTitle)).toMatchObject({ kind: "network", message: ERROR_HINTS.network });
    for (const v of [busy, gateway, failureView(offline, "x")]) expect(v!.message).not.toMatch(/Fetch|Gateway|POST|api/);
  });

  it("새 서버의 code(검색 기반 장애 503)는 프런트 문구를 쓴다", () => {
    const down = fetchError(503, { detail: "검색 서버가 잠시 응답하지 않습니다", code: "search_unavailable" });
    expect(failureView(down, BOOK_SEARCH_TEXT.failedTitle)?.message).toBe(CODE_MESSAGES.search_unavailable);
  });

  it("입력이 틀린 요청(422 — 검색어 500자 초과)은 고칠 점을 말하고 [다시 시도]를 달지 않는다(같은 입력은 또 거절된다)", () => {
    const tooLong = fetchError(422, { detail: [{ type: "string_too_long", ctx: { max_length: 500 } }] });
    expect(failureView(tooLong, BOOK_SEARCH_TEXT.failedTitle)).toEqual({
      kind: "invalid",
      title: "검색하지 못했어요",
      message: charLimitMessage(500),
      retry: false,
    });
  });

  it("notFound 를 주면 404·410 은 그 상태(다시 시도 없음) — 서버의 '도서 없음: {id}' 같은 원문은 쓰지 않는다", () => {
    const notFound = { kind: "notFound" as const, title: BOOK_DETAIL_TEXT.notFoundTitle, message: BOOK_DETAIL_TEXT.notFoundMessage };
    for (const status of [404, 410]) {
      expect(failureView(fetchError(status, { detail: "도서 없음: B1" }), BOOK_DETAIL_TEXT.failedTitle, notFound)).toEqual({
        ...notFound,
        retry: false,
      });
    }
    // 404 가 아니면 주어진 제목 + 이유 + [다시 시도]
    expect(failureView(fetchError(500), BOOK_DETAIL_TEXT.failedTitle, notFound)).toEqual({
      kind: "server",
      title: BOOK_DETAIL_TEXT.failedTitle,
      message: ERROR_HINTS.server,
      retry: true,
    });
    // notFound 를 주지 않으면 404 도 일반 실패(대체 문구가 비어 기본 문구)
    expect(failureView(fetchError(404), "x")).toMatchObject({ kind: "notFound", message: DEFAULT_ERROR_MESSAGE, retry: true });
  });

  it("상황별 추천의 404(이 고민으로 찾은 도서 없음)는 빈 결과로 바꿔 쓸 수 있다", () => {
    const empty = { kind: "empty" as const, title: SCENARIO_TEXT.emptyTitle, message: SCENARIO_TEXT.emptyMessage };
    expect(failureView(fetchError(404, { detail: "추천 도서를 찾을 수 없습니다" }), SCENARIO_TEXT.failedTitle, empty)).toEqual({
      ...empty,
      retry: false,
    });
  });
});

describe("추천 이유 실패 한 줄 — 서버 {error} 글 대신 프런트 문구", () => {
  it("받은 글이 없으면 failed, 있으면 partial", () => {
    expect(reasonFailureText("")).toBe(BOOK_REASON_TEXT.failed);
    expect(reasonFailureText("  \n")).toBe(BOOK_REASON_TEXT.failed);
    expect(reasonFailureText("이 책은 조선시대")).toBe(BOOK_REASON_TEXT.partial);
  });
});

describe("상황별 추천 ai_failed", () => {
  it("새 서버가 true 를 보낼 때만 true — 옛 서버(필드 없음)·이상한 값은 false 라 예전처럼 소개를 타이핑한다", () => {
    expect(scenarioAiFailed({ ai_failed: true, intro: "", books: [] })).toBe(true);
    for (const data of [{ ai_failed: false }, {}, { ai_failed: "true" }, { ai_failed: 1 }, null, undefined, "x"]) {
      expect(scenarioAiFailed(data)).toBe(false);
    }
  });
});

describe("문구 — 해요체·문장마다 줄바꿈", () => {
  const copies: [string, string][] = [
    ...Object.entries(BOOK_SEARCH_TEXT),
    ...Object.entries(BOOK_REASON_TEXT),
    ...Object.entries(BOOK_DETAIL_TEXT).filter(([k]) => k !== "home"),
    ...Object.entries(SCENARIO_TEXT).filter(([k]) => k !== "pickAnother"),
  ].map(([k, v]) => [k, String(v)]);

  it.each(copies)("%s: 해요체로 끝난다('~요'/'~요.')", (_k, text) => {
    expect(text).toMatch(/요\.?$/);
    expect(text).not.toMatch(/습니다|하세요/);
  });

  it.each(copies)("%s: 한 줄 안에 두 문장을 잇지 않는다", (_k, text) => {
    expect(text).not.toMatch(/[.?!] \S/);
  });
});

describe("랜딩·결과 — pages/index.vue", () => {
  const src = read("pages/index.vue");

  it("랜딩 두 입력창과 결과 검색바 모두 maxlength=500 이고, 글자 수(SkxCharCount)를 aria-describedby 로 가리킨다", () => {
    expect(src.match(/:maxlength="SEARCH_QUERY_MAX"/g)).toHaveLength(3);
    for (const id of ["skx-count-book", "skx-count-paper", "skx-count-result"]) {
      expect(src).toContain(`:aria-describedby="showCount ? '${id}' : undefined"`);
      expect(src).toContain(`<SkxCharCount v-if="showCount" id="${id}" :length="currentQuery.length" :max="SEARCH_QUERY_MAX" />`);
    }
    // 랜딩 모양을 지키려 글자 수는 한도 가까이(90%)부터만 보인다
    expect(src).toContain('const showCount = computed(() => charCountState(currentQuery.value.length, SEARCH_QUERY_MAX) !== "normal");');
  });

  it("랜딩 입력 상자의 보내기 줄은 글자 수와 보내기를 세로 가운데로 맞추고 띄운다(보내기만 있을 때 모양은 그대로)", () => {
    const css = read("assets/css/style_skovix.css");
    expect(css).toMatch(/\.skx-search__actions \{\s*grid-area: send;\s*display: flex;\s*justify-content: flex-end;[\s\S]*?align-items: center;\s*gap: 0\.5rem;\s*\}/);
  });

  it("검색 POST 는 검색 시간 제한을 걸고, 실패는 영문 메시지 대신 failureView 로 결과 자리의 상태 블록에 보인다", () => {
    expect(src).toMatch(/api<any>\("\/books\/search", \{[\s\S]*?signal,[\s\S]*?timeout: API_SEARCH_TIMEOUT_MS,/);
    expect(src).toContain("searchFailure.value = failureView(e, BOOK_SEARCH_TEXT.failedTitle);");
    expect(src).not.toMatch(/\be\??\.message\b|color: #c00|검색 중 오류가 발생했습니다/);
    expect(src).toMatch(
      /<div v-else-if="searchFailure" class="skx-rframe">\s*<SkxErrorState\s+:kind="searchFailure\.kind"\s+:title="searchFailure\.title"\s+:message="searchFailure\.message"\s+:on-retry="searchFailure\.retry \? retrySearch : undefined"\s*\/>/,
    );
  });

  it("[다시 시도]는 실패한 그 검색어(와 같은 기록)로 다시 찾는다", () => {
    expect(src).toContain("lastSearch = { query, reuse };");
    expect(src).toMatch(/function retrySearch\(\) \{\s*if \(lastSearch\) void handleSearch\(lastSearch\.query, lastSearch\.reuse\);/);
  });

  it("0건(books 없음·0건 기록 복원)은 결과가 정해진 뒤에만 '검색 결과가 없어요' 빈 상태", () => {
    expect(src).toMatch(
      /<div v-else-if="resultSettled && !books\.length" class="skx-rframe">\s*<SkxErrorState kind="empty" :title="BOOK_SEARCH_TEXT\.emptyTitle" :message="BOOK_SEARCH_TEXT\.emptyMessage" \/>/,
    );
    // 검색 응답이 오면·기록을 펼치면 정해지고, 새 검색·랜딩 복귀에서 다시 내린다
    expect(src).toMatch(/loading\.value = false;\s*resultSettled\.value = true;/);
    expect(src).toMatch(/searchFailure\.value = null;\s*resultSettled\.value = true;\s*pdfProblem\.value = null;/);
    expect(src.match(/resultSettled\.value = false;/g)).toHaveLength(2);
  });

  it("추천 이유 실패·끊김은 해요체 프런트 문구의 공통 줄 안내 — 끊김은 접히는 칸 밖(#after)에 있어 늘 보인다", () => {
    expect(src).toMatch(
      /<SkxInlineError\s+v-else-if="reasonStatus === 'error'"\s+:message="BOOK_REASON_TEXT\.failed"\s+@retry="retryTopReason"\s*\/>/,
    );
    expect(src).toMatch(
      /<template #after>\s*<SkxInlineError\s+v-if="reasonStatus === 'interrupted'"\s+:message="BOOK_REASON_TEXT\.partial"\s+@retry="retryTopReason"\s*\/>\s*<\/template>/,
    );
    expect(src).not.toMatch(/skx-pick__retry|중간에 끊겼어요|추천 이유를 불러오지 못했어요\./);
  });

  it("[원문 보기]는 파일을 확인한 뒤 열고, 없으면 누른 카드 바로 아래에 알린다", () => {
    expect(src).toContain("const { pdf, checking: checkingPdf, openPdf, closePdf } = usePdfOpener();");
    expect(src).toMatch(/async function viewPdf\(item: BookChunkGroup\) \{\s*if \(checkingPdf\.value\) return;\s*const problem = await openPdf\(/);
    expect(src).toMatch(/<PdfViewer\s+v-if="pdf"\s+:cnts-id="pdf\.cntsId"/);
    expect(src).toContain('<SkxInlineError v-if="pdfProblem?.id === topBook.book_id" :message="pdfProblem.message" />');
    expect(src).toContain('<SkxInlineError v-if="pdfProblem?.id === item.book_id" :message="pdfProblem.message" />');
    expect(src).not.toContain("pdfOpen");
  });
});

describe("도서 상세 — pages/books/[cnts_id].vue", () => {
  const src = read("pages/books/[cnts_id].vue");

  it("불러오기 실패는 상태 블록 — 404 는 '도서를 찾을 수 없어요'(다시 시도 없음), 그 밖은 [다시 시도], 둘 다 [홈으로]", () => {
    expect(src).toMatch(
      /pageFailure\.value = failureView\(e, BOOK_DETAIL_TEXT\.failedTitle, \{\s*kind: "notFound",\s*title: BOOK_DETAIL_TEXT\.notFoundTitle,\s*message: BOOK_DETAIL_TEXT\.notFoundMessage,\s*\}\);/,
    );
    expect(src).toMatch(/<SkxErrorState\s+v-else-if="pageFailure"[\s\S]*?title-tag="h1"\s+:on-retry="pageFailure\.retry \? loadPage : undefined"\s*>/);
    expect(src).toContain(`<button type="button" class="skx-state__action" @click="navigateTo('/')">{{ BOOK_DETAIL_TEXT.home }}</button>`);
    // 서버 detail('도서 없음: {id}')을 그대로 보이지 않는다
    expect(src).not.toMatch(/e\?\.data\?\.detail|class="dt-error"|도서 정보를 불러올 수 없습니다/);
  });

  it("관련 자료는 실패(compact + [다시 시도])와 0건(빈 상태)을 가른다 — 빈 catch 가 없다", () => {
    expect(src).toMatch(
      /<SkxErrorState\s+v-else-if="relatedFailure"[\s\S]*?compact\s+:on-retry="relatedFailure\.retry \? fetchRelatedBooks : undefined"\s*\/>\s*<SkxErrorState v-else-if="!relatedItems\.length" kind="empty" compact :title="BOOK_DETAIL_TEXT\.relatedEmptyTitle" \/>/,
    );
    expect(src).toContain("relatedFailure.value = failureView(e, BOOK_DETAIL_TEXT.relatedFailedTitle)");
    expect(src).not.toMatch(/\/\* ignore \*\/|연관 추천 항목이 없습니다/);
  });

  it("AI 큐레이션·추천 이유의 빈 상태도 공통 상태 블록(empty)이고, 빈 상태 문구는 해요체다", () => {
    expect(src).toContain('<SkxErrorState v-else kind="empty" compact :title="BOOK_DETAIL_TEXT.curationEmpty" />');
    expect(src).toContain('<SkxErrorState v-else-if="!reasonError" kind="empty" compact :title="BOOK_DETAIL_TEXT.reasonEmpty" />');
    expect(src).toContain('empty-text="요약 정보가 없어요."');
    expect(src).not.toMatch(/없습니다/);
  });

  it("?chat=1 로 왔어도 도서를 불러온 뒤에만 DeepRead 패널을 연다 — 못 불러오면 닫을 수 없는 빈 패널이 화면을 덮지 않는다", () => {
    expect(src).toContain(":class=\"['skx-chat-panel', chatPanelOpen && book && 'is-open']\"");
    expect(src).toMatch(
      /async function loadPage\(\) \{\s*await fetchBook\(\);\s*if \(!book\.value\) return;[\s\S]*?if \(route\.query\.chat === "1"\) chatPanelOpen\.value = true;/,
    );
    expect(src).not.toMatch(/onMounted\(async \(\) => \{\s*\/\/ \?chat=1/);
  });

  it("[원문 보기](이 자료·관련 자료)는 파일을 확인한 뒤 열고, 없으면 누른 쪽에 알린다", () => {
    expect(src).toContain("const { pdf, checking: checkingPdf, openPdf, closePdf } = usePdfOpener();");
    expect(src).toMatch(/<PdfViewer\s+v-if="pdf"\s+:cnts-id="pdf\.cntsId"/);
    expect(src).toMatch(/<SkxInlineError\s+v-if="pdfProblem\?\.id === cnts_id"\s+id="bdetail-pdf-problem"\s+class="dt-hero__note"/);
    expect(src).toMatch(/<template #note>\s*<SkxInlineError v-if="pdfProblem && pdfProblem\.id === rel\.book_id"/);
    expect(src).not.toContain("pdfTarget");
  });
});

describe("상황별 추천 — pages/recommend/[id].vue", () => {
  const src = read("pages/recommend/[id].vue");

  it("실패는 2.5초 토스트 대신 화면 안 상태 블록 — 404·빈 목록은 빈 결과(+[다른 상황 고르기]), 그 밖은 [다시 시도]", () => {
    expect(src).not.toContain("추천 도서를 불러오는 중 오류가 발생했습니다");
    expect(src).toContain("loadFailure.value = failureView(e, SCENARIO_TEXT.failedTitle, scenarioEmpty());");
    expect(src).toMatch(/if \(!recommendedBooks\.value\.length\) \{\s*loadFailure\.value = scenarioEmpty\(\);/);
    expect(src).toMatch(/<SkxErrorState\s+v-if="loadFailure && !loading"[\s\S]*?:on-retry="loadFailure\.retry \? fetchRecommend : undefined"\s*>/);
    expect(src).toMatch(/<NuxtLink v-if="loadFailure\.kind === 'empty'" to="\/recommend" class="skx-state__action">/);
  });

  it("새 서버의 ai_failed 면 소개 자리에 '추천 이유를 만들지 못했어요' 한 줄 + [다시 시도](다시 받기), 옛 서버는 예전처럼 타이핑", () => {
    expect(src).toMatch(/if \(scenarioAiFailed\(data\)\) \{\s*aiFailed\.value = true;\s*return;\s*\}\s*\/\/[^\n]*\n\s*typeText\(data\?\.intro \|\| meta\.value\.aiLabel\);/);
    expect(src).toMatch(/<SkxInlineError\s+v-if="aiFailed && !loading"\s+:message="SCENARIO_TEXT\.aiFailed"\s+@retry="fetchRecommend"\s*\/>/);
  });

  it("추천 POST 는 검색 시간 제한·화면 이탈 끊기를 걸고, Esc 리스너는 떠날 때 뗀다", () => {
    expect(src).toMatch(/signal: pageAbort\.signal,[\s\S]*?timeout: API_SEARCH_TIMEOUT_MS,/);
    expect(src).toContain('window.addEventListener("keydown", onKeydown);');
    expect(src).toContain('window.removeEventListener("keydown", onKeydown);');
  });
});

describe("장바구니·보존 화면 — 저장소가 막힌 브라우저", () => {
  it("useCart 의 저장은 try/catch — 던져도 담기(대출 신청)가 멈추지 않는다", () => {
    const src = read("composables/useCart.ts");
    expect(src).toMatch(/function _persist\(\) \{\s*if \(!process\.client\) return;\s*try \{\s*localStorage\.setItem\(STORAGE_KEY, JSON\.stringify\(cart\.value\)\);\s*\} catch \{/);
  });

  it("/search-classic 과 그 검색 도구는 브라우저 ID 를 막힌 저장소에서도 던지지 않는 readOrCreateBrowserId 로 읽는다", () => {
    const page = read("pages/search-classic.vue");
    const search = read("composables/useSearch.ts");
    expect(page).toContain("sessionId.value = readOrCreateBrowserId(safeLocalStorage(), generateUUID);");
    expect(search).toContain("readOrCreateBrowserId(safeLocalStorage(), generateUUID)");
    for (const src of [page, search]) expect(src).not.toMatch(/localStorage\.(getItem|setItem)\("sid"/);
  });
});

describe("보존 화면 /search-classic — 추천 이유 스트림 실패", () => {
  const page = read("pages/search-classic.vue");
  const top = read("components/TopResult.vue");

  it("4xx·5xx 는 본문을 읽지 않고, {error}·끊김은 메인과 같은 읽기(readReasonStream)로 가려 안내 한 줄(reasonFailureText)을 둔다", () => {
    expect(page).toMatch(/if \(response\.ok && response\.body\) \{\s*complete = await readReasonStream\(/);
    expect(page).toContain("if (!complete) errorRef.value = reasonFailureText(reasonRef.value);");
    expect(page).not.toContain("getReader(");
  });

  it("1위·살펴보기 두 칸 모두 TopResult 에 안내와 [다시 시도]를 넘긴다", () => {
    expect(page).toMatch(/:reason-error="reasonError"\s+@retry-reason="retryTopReason"/);
    expect(page).toMatch(/:reason-error="selectedReasonError"\s+@retry-reason="retrySelectedReason"/);
    expect(top.match(/<SkxInlineError :message="reasonError" @retry="emit\('retryReason'\)" \/>/g)).toHaveLength(2);
    expect(top).toContain("const emit = defineEmits<{ retryReason: [] }>();");
  });

  it("보존 화면은 늘 밝은 바탕이라 안내 칸에서만 테마 글자색을 이 화면의 글자색으로 바꾼다", () => {
    expect(top).toMatch(/\.reason-error \{[^}]*--skx-ink: var\(--ink-2\);[^}]*--skx-primary: var\(--violet-deep\);[^}]*\}/);
  });
});
