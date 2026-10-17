// frontend/tests/unit/landingBookErrors.test.ts
// 랜딩·소장자료 검색·SKOVIX 추천 1권·도서 상세·상황별 추천·보존 화면(/search-classic)의 오류·빈 상태(에러 처리 2단계, 2026-10-16).
// 문구·판정은 utils/bookErrors.ts 의 순수 함수로 돌려 보고, 화면은 Nuxt 없이 돌지 않아 소스 글로 고정한다(aiStreamConsumers.test 와 같은 방식)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CODE_MESSAGES, DEFAULT_ERROR_MESSAGE, ERROR_HINTS, apiErrorMessage, charLimitMessage } from "~/utils/apiErrors";
import * as bookErrors from "~/utils/bookErrors";
import {
  BOOK_DETAIL_TEXT,
  BOOK_REASON_TEXT,
  BOOK_SEARCH_TEXT,
  SCENARIO_TEXT,
  failureView,
  reasonFailureText,
  scenarioAiFailed,
} from "~/utils/bookErrors";
import { SEARCH_QUERY_MAX } from "~/utils/searchInput";

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

  // 소장자료·논문 검색이 같은 값을 따로 export 하던 중복(통합 리뷰 2026-10-16) — 정의는 utils/searchInput.ts 한 곳이고 bookErrors 는 내보내지 않는다
  it("정의는 utils/searchInput.ts 한 곳 — bookErrors 는 SEARCH_QUERY_MAX 를 내보내지 않는다", () => {
    expect(read("utils/searchInput.ts")).toContain("export const SEARCH_QUERY_MAX = 500;");
    expect(Object.keys(bookErrors)).not.toContain("SEARCH_QUERY_MAX");
    expect(read("utils/bookErrors.ts")).not.toMatch(/export const SEARCH_QUERY_MAX/);
    for (const page of ["pages/index.vue", "pages/dev/error-states.vue"]) {
      expect(read(page), page).toMatch(/import \{[^}]*\bSEARCH_QUERY_MAX\b[^}]*\} from "~\/utils\/searchInput";/);
    }
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

  // 404 는 서지 DB 에 그 자료의 행이 없을 때다(app/api/book.py get_book). 이 화면은 앱 안 링크로 들어오므로 '주소를 확인하라'가 아니라 사실을 말한다
  it("도서 404 설명은 주소 탓이 아니라 자료가 없다는 사실이다", () => {
    expect(BOOK_DETAIL_TEXT.notFoundMessage).toBe("목록에서 빠졌거나 아직 등록되지 않은 자료예요.");
    expect(BOOK_DETAIL_TEXT.notFoundMessage).not.toMatch(/주소/);
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
      // 늘 같은 id 를 가리킨다(바인딩이 아니라 고정 속성) — 바인딩을 바꾸면 + 메뉴가 덧붙인 DeepResearch 글자 수 id 를 지운다
      expect(src).toContain(`aria-describedby="${id}"`);
      expect(src).toMatch(new RegExp(`<SkxCharCount (?:v-if="!deepResearch" )?id="${id}" quiet :length="currentQuery\\.length" :max="SEARCH_QUERY_MAX" />`));
    }
  });

  // 사용자 결정(2026-10-16): 검색창 글자 수는 한도 가까이(90%)부터만. v-if 로 90%부터 붙이면 한도에 닿는 순간 새로 생긴 알림 영역을 낭독기가
  // 놓친다(통합 리뷰) — 늘 그려 두고 quiet(평소엔 화면에서만 숨김)로 보인다
  it("글자 수는 v-if 로 붙였다 떼지 않고 늘 그린 채 quiet — 한도 가까이부터만 보인다", () => {
    expect(src).not.toMatch(/showCount|charCountState/);
    expect(src.match(/<SkxCharCount\b[^>]*\bquiet\b[^>]*\/>/g)).toHaveLength(3);
    expect(src).toContain('<SkxCharCount id="skx-count-book" quiet');
    expect(src).toContain('<SkxCharCount id="skx-count-result" quiet');
  });

  it("DeepResearch 모드인 동안 논문 칸의 글자 수는 + 메뉴(SearchPlusMenu)의 것 하나만 — 이 화면의 것은 모드를 바꿀 때만 붙였다 뗀다", () => {
    expect(src).toContain('<SkxCharCount v-if="!deepResearch" id="skx-count-paper" quiet');
    expect(src).not.toMatch(/:aria-describedby=/);
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
    expect(src).toMatch(/function retrySearch\(\) \{[\s\S]*?void handleSearch\(lastSearch\.query, lastSearch\.reuse\);\s*\}/);
  });

  // 통합 리뷰(2026-10-16): [다시 시도]를 누르면 상태 블록이 버튼째 로딩 표시로 바뀌어 초점이 body 로 떨어졌다
  it("검색 실패 [다시 시도]는 누르자마자 초점을 결과 화면(main, tabindex=-1)으로 옮긴 뒤 다시 찾는다", () => {
    expect(src).toMatch(/<main v-else-if="view === 'results'" ref="resultMainRef" class="skx-result" tabindex="-1">/);
    expect(src).toMatch(
      /function retrySearch\(\) \{\s*if \(!lastSearch \|\| loading\.value\) return;\s*focusRegion\(resultMainRef\.value\);\s*void handleSearch\(/,
    );
  });

  it("추천 이유 실패·끊김 [다시 시도]는 초점을 '왜 이 책인가' 칸(tabindex=-1)으로 옮긴 뒤 다시 받는다", () => {
    expect(src).toMatch(/<section\s+ref="pickWhyRef"\s+class="skx-pick__block"\s+aria-labelledby="skx-pick-why"\s+:aria-busy="reasonPending"\s+tabindex="-1"\s*>/);
    expect(src).toMatch(/function retryTopReason\(\) \{\s*focusRegion\(pickWhyRef\.value\);\s*const signal = beginRun\(\);/);
  });

  it("토스트는 낭독기에도 알린다(role=status, aria-live=polite)", () => {
    expect(src).toContain('<div v-if="toast" class="skx-toast" role="status" aria-live="polite">{{ toast }}</div>');
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
    expect(src).toMatch(/<SkxErrorState\s+v-else-if="pageFailure"[\s\S]*?title-tag="h1"\s+:on-retry="pageFailure\.retry \? retryPage : undefined"\s*>/);
    expect(src).toContain(`<button type="button" class="skx-state__action" @click="navigateTo('/')">{{ BOOK_DETAIL_TEXT.home }}</button>`);
    // 서버 detail('도서 없음: {id}')을 그대로 보이지 않는다
    expect(src).not.toMatch(/e\?\.data\?\.detail|class="dt-error"|도서 정보를 불러올 수 없습니다/);
  });

  it("관련 자료는 실패(compact + [다시 시도])와 0건(빈 상태)을 가른다 — 빈 catch 가 없다", () => {
    expect(src).toMatch(
      /<SkxErrorState\s+v-else-if="relatedFailure"[\s\S]*?compact\s+:on-retry="relatedFailure\.retry \? retryRelated : undefined"\s*\/>\s*<SkxErrorState v-else-if="!relatedItems\.length" kind="empty" compact :title="BOOK_DETAIL_TEXT\.relatedEmptyTitle" \/>/,
    );
    expect(src).toContain("relatedFailure.value = failureView(e, BOOK_DETAIL_TEXT.relatedFailedTitle)");
    expect(src).not.toMatch(/\/\* ignore \*\/|연관 추천 항목이 없습니다/);
  });

  // 통합 리뷰(2026-10-16): [다시 시도]를 누르면 상태 블록이 버튼째 로딩 표시로 바뀌어 초점이 body 로 떨어졌다 — 추천 이유의 focusOwningPanel 처럼
  // 누르자마자 다시 받는 동안에도 남는 감싸는 영역(tabindex=-1)으로 초점을 옮긴다
  it("불러오기 실패·관련 자료 실패의 [다시 시도]는 초점을 상세 틀·관련 자료 절로 옮긴 뒤 다시 받는다", () => {
    expect(src).toContain('<div ref="frameRef" class="dt-frame" tabindex="-1">');
    expect(src).toMatch(/function retryPage\(\) \{\s*if \(pageLoading\.value\) return;\s*focusRegion\(frameRef\.value\);\s*void loadPage\(\);\s*\}/);
    expect(src).toContain('<section ref="relatedSectionRef" class="dt-section" aria-labelledby="bdetail-related-title" tabindex="-1">');
    expect(src).toMatch(
      /function retryRelated\(\) \{\s*if \(relatedLoading\.value\) return;\s*focusRegion\(relatedSectionRef\.value\);\s*void fetchRelatedBooks\(\);\s*\}/,
    );
    // 추천 이유는 그대로 탭 본문으로(선례)
    expect(src).toMatch(/function retryReason\(\) \{\s*if \(reasonLoading\.value\) return;\s*focusOwningPanel\(/);
  });

  it("AI 큐레이션의 빈 상태는 공통 상태 블록(empty)이고, 빈 상태 문구는 해요체다", () => {
    expect(src).toContain('<SkxErrorState v-else kind="empty" compact :title="BOOK_DETAIL_TEXT.curationEmpty" />');
    expect(src).toContain('empty-text="요약 정보가 없어요."');
    expect(src).not.toMatch(/없습니다/);
  });

  // 통합 리뷰(2026-10-16): '추천 이유가 없어요' 빈 상태는 탭 조건(aiTabAvailable — 다 받았는데 글도 실패도 없으면 탭을 뺀다)과 맞지 않아 닿지 않는
  // 갈래였다. 다 받았는데 글이 없는 경우를 실패 하나로 모은다 — 새 서버는 LLM 빈 답을 {error} 로 보내고 옛 서버는 빈 [DONE] 이다
  it("[추천 이유] 탭에 닿지 않는 빈 상태 갈래가 없고, 끝까지 왔는데 글이 없으면 실패 안내([다시 시도])로 둔다", () => {
    expect(src).not.toContain("reasonEmpty");
    expect(Object.keys(BOOK_DETAIL_TEXT)).not.toContain("reasonEmpty");
    expect(src).toMatch(
      /if \(pageAbort\.signal\.aborted\) return;[\s\S]*?if \(!reasonText\.value\.trim\(\)\) reasonText\.value = "";\s*if \(!end\.ok \|\| !reasonText\.value\) reasonError\.value = reasonFailureText\(reasonText\.value\);/,
    );
  });

  it("토스트는 낭독기에도 알린다(role=status, aria-live=polite)", () => {
    expect(src).toContain('<div v-if="toast" class="skx-toast" role="status" aria-live="polite">{{ toast }}</div>');
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
    expect(src).toMatch(/<SkxErrorState\s+v-if="loadFailure && !loading"[\s\S]*?:on-retry="loadFailure\.retry \? retryLoad : undefined"\s*>/);
    expect(src).toMatch(/<NuxtLink v-if="loadFailure\.kind === 'empty'" to="\/recommend" class="skx-state__action">/);
  });

  it("새 서버의 ai_failed 면 소개 자리에 '추천 이유를 만들지 못했어요' 한 줄 + [다시 시도](다시 받기), 옛 서버는 예전처럼 타이핑", () => {
    expect(src).toMatch(/if \(scenarioAiFailed\(data\)\) \{\s*aiFailed\.value = true;\s*return;\s*\}\s*\/\/[^\n]*\n\s*typeText\(data\?\.intro \|\| meta\.value\.aiLabel\);/);
    expect(src).toMatch(/<SkxInlineError\s+v-if="aiFailed && !loading"\s+:message="SCENARIO_TEXT\.aiFailed"\s+@retry="retryAi"\s*\/>/);
  });

  // 통합 리뷰(2026-10-16): [다시 시도]를 누르면 상태 블록·줄 안내가 버튼째 빠져 초점이 body 로 떨어졌다
  it("[다시 시도]는 초점을 남는 칸(불러오기 실패면 결과 카드, ai_failed 면 AI 소개 칸 — tabindex=-1)으로 옮긴 뒤 다시 받는다", () => {
    expect(src).toContain('<div ref="cardRef" class="skx-result-card" tabindex="-1">');
    expect(src).toContain('<div ref="aiBoxRef" class="skx-rcd-ai" tabindex="-1">');
    expect(src).toMatch(/function retryLoad\(\) \{\s*if \(loading\.value\) return;\s*focusRegion\(cardRef\.value\);\s*void fetchRecommend\(\);\s*\}/);
    expect(src).toMatch(/function retryAi\(\) \{\s*if \(loading\.value\) return;\s*focusRegion\(aiBoxRef\.value\);\s*void fetchRecommend\(\);\s*\}/);
  });

  it("토스트는 낭독기에도 알린다(role=status, aria-live=polite)", () => {
    expect(src).toContain('<div v-if="toast" class="skx-toast" role="status" aria-live="polite">{{ toast }}</div>');
  });

  it("추천 POST 는 검색 시간 제한·화면 이탈 끊기를 걸고, Esc 리스너는 떠날 때 뗀다", () => {
    expect(src).toMatch(/signal: pageAbort\.signal,[\s\S]*?timeout: API_SEARCH_TIMEOUT_MS,/);
    expect(src).toContain('window.addEventListener("keydown", onKeydown);');
    expect(src).toContain('window.removeEventListener("keydown", onKeydown);');
  });
});

describe("상황 목록 — pages/recommend/index.vue", () => {
  it("토스트는 낭독기에도 알린다(role=status, aria-live=polite)", () => {
    expect(read("pages/recommend/index.vue")).toContain(
      '<div v-if="toast" class="skx-toast" role="status" aria-live="polite">{{ toast }}</div>',
    );
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

// 통합 리뷰(2026-10-16): 검색 실패가 영문 ofetch 메시지·서버 detail 원문을 빨간 글씨(#ef4444)로 보였다. 보존 화면이라 구조·모양은 두고 문구·색만
describe("보존 화면 /search-classic — 검색 실패·빈 상태 문구", () => {
  const page = read("pages/search-classic.vue");
  const search = read("composables/useSearch.ts");

  it("검색 실패 글은 공통 규칙(apiErrorMessage)의 '검색하지 못했어요 — 이유' — 영문·서버 detail 원문을 쓰지 않는다", () => {
    expect(search).toContain("error.value = apiErrorMessage(e, BOOK_SEARCH_TEXT.failedTitle);");
    expect(search).not.toMatch(/e\?\.data\?\.detail|e\?\.message|검색 중 오류가 발생했습니다/);
    const offlineText = apiErrorMessage(offline, BOOK_SEARCH_TEXT.failedTitle);
    expect(offlineText).toBe(`검색하지 못했어요 — ${ERROR_HINTS.network}`);
    expect(apiErrorMessage(fetchError(502), BOOK_SEARCH_TEXT.failedTitle)).not.toMatch(/Fetch|Gateway|POST|api/);
  });

  it("검색 요청은 다른 검색창과 같은 시간 제한(API_SEARCH_TIMEOUT_MS)을 건다 — 서버가 답하지 않아도 '검색 중'에 머물지 않는다", () => {
    expect(search).toContain('import { API_SEARCH_TIMEOUT_MS } from "~/composables/useApi";');
    expect(search).toMatch(/\$fetch<SearchResponse>\([\s\S]*?body,[\s\S]*?timeout: API_SEARCH_TIMEOUT_MS,/);
  });

  it("실패 글은 빨갛게 칠하지 않고 이 화면의 본문색 — 이유가 두 문장이면 줄로 그린다(구조는 그대로)", () => {
    const area = page.match(/\.error-area \{[^}]*\}/)?.[0] ?? "";
    expect(area).toContain("color: var(--ink-2);");
    expect(area).toContain("white-space: pre-line;");
    expect(area).not.toMatch(/#ef4444|--skx-danger/);
    expect(page).toMatch(/<div v-else-if="error" class="error-area">\s*<p>\{\{ error \}\}<\/p>\s*<button @click="handleSearch\(currentQuery\)">다시 검색<\/button>/);
  });

  it("빈 상태 문구는 해요체 — 두 문장은 줄을 나눈다", () => {
    expect(page).not.toMatch(/없습니다|시도해보세요/);
    expect(page).toContain("대출 신청한 도서가 없어요");
    expect(page).toContain("const EMPTY_RESULT_TEXT = `${BOOK_SEARCH_TEXT.emptyTitle}.\\n${BOOK_SEARCH_TEXT.emptyMessage}`;");
    expect(page).toContain('<div v-if="!bookResult.books.length" class="empty">{{ EMPTY_RESULT_TEXT }}</div>');
    expect(page).toContain('<div v-if="!chunkResult.chunks.length" class="empty">{{ BOOK_SEARCH_TEXT.emptyTitle }}.</div>');
    expect(page.match(/\.empty \{[^}]*\}/)?.[0]).toContain("white-space: pre-line;");
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
