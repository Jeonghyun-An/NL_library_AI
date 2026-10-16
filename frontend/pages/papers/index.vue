<template>
  <div :class="['skx-app', chatPaperId && 'is-lnb-collapsed']">
    <AppSidebar
      :collapsed="!!chatPaperId"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <!-- 랜딩 (검색 전) -->
    <main v-if="!hasResults" class="skx-contents">
      <div class="skx-contents__inner">
        <h1 class="skx-hero">논문 의미 기반 검색</h1>
        <div class="skx-search">
          <div class="skx-search__box">
            <span class="skx-search__glow" aria-hidden="true"></span>
            <ResearchSearchPlusMenu ref="plusMenu" v-model="currentQuery" kind="paper" :disabled="loading" />
            <label class="skx-search__field">
              <span class="skx-sr-only">논문 검색어</span>
              <textarea
                class="skx-search__input"
                v-model="currentQuery"
                placeholder="탐구하고 싶은 논문을 자연어로 검색해보세요"
                :maxlength="SEARCH_QUERY_MAX"
                :aria-describedby="landingCountId"
                :disabled="loading"
                @keydown.enter.exact.prevent="handleSearch(currentQuery)"
              ></textarea>
            </label>
            <div class="skx-search__actions">
              <!-- 글자 수 — 서버 한도(500자)를 넘는 검색어는 입력창이 먼저 막는다(넘으면 422 로 거절된다). 한도 가까이부터만 보인다
                   (quiet — 평소엔 화면에서만 숨는다, 사용자 결정 2026-10-16). DeepResearch 모드의 질문 한도도 500 이라 이 하나로 알린다 -->
              <SkxCharCount quiet :id="landingCountId" :length="currentQuery.length" :max="SEARCH_QUERY_MAX" />
              <button
                type="button"
                class="skx-send"
                aria-label="검색"
                :aria-disabled="!hasQuery(currentQuery)"
                @click="handleSearch(currentQuery)"
              >
                <img src="/img/ico-send-up.svg" alt="" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 검색 결과 -->
    <main v-else class="skx-presult">
      <h1 class="skx-sr-only">논문 검색 결과</h1>

      <!-- 검색바 -->
      <div class="skx-rsearch">
        <ResearchSearchPlusMenu ref="plusMenu" v-model="currentQuery" kind="paper" />
        <input
          type="text"
          class="skx-rsearch__input"
          v-model="currentQuery"
          :maxlength="SEARCH_QUERY_MAX"
          aria-label="논문 검색어"
          :aria-describedby="barCountId"
          @keydown.enter.prevent="handleSearch(currentQuery)"
        />
        <SkxCharCount quiet :id="barCountId" :length="currentQuery.length" :max="SEARCH_QUERY_MAX" />
        <button
          type="button"
          class="skx-send"
          aria-label="검색"
          :aria-disabled="!hasQuery(currentQuery)"
          @click="handleSearch(currentQuery)"
        >
          <img src="/img/ico-send-up.svg" alt="" />
        </button>
      </div>

      <!-- 결과 자리 — 검색 실패의 [다시 시도]는 검색이 시작되면 상태 블록째 빠진다. 초점을 이 자리로 먼저 옮겨(tabindex="-1")
           body 로 떨어지지 않게 하고, 스피너·결과가 그 안에 차례로 그려진다 -->
      <div ref="frameRef" class="skx-rframe" tabindex="-1">
        <!-- 로딩 -->
        <div v-if="loading" style="padding: 40px; text-align: center">
          <img :src="SPINNER_SRC" alt="" style="width: 32px" />
          <p style="margin-top: 12px">논문을 탐색하고 있습니다...</p>
        </div>

        <!-- 검색 실패 — 결과 자리에 상태 블록. 같은 검색어로 다시 보내는 [다시 시도](입력 거절·없음처럼 다시 보내도 같은 결과면 달지 않는다) -->
        <SkxErrorState
          v-else-if="searchError"
          :kind="searchError.kind"
          :title="PAPER_STATE_TEXT.searchFailed"
          :message="searchError.message"
          :on-retry="isRetryableKind(searchError.kind) ? retrySearch : undefined"
        />

        <template v-else>
          <!-- AI 검색 결과 — 틀(머리·DeepRead 안내·2:1 두 칸)은 소장자료 결과와 같은 AiResultPanel. 결과가 0건이면 요약할 논문이 없어 그리지 않는다 -->
          <AiResultPanel v-if="paperResult?.books.length" :loading="aiLoading" :hint="!!aiText && !aiLoading">
            <!-- 좌측: 요약 텍스트 -->
            <!-- AI 요약 실패의 [다시 시도](#after 줄 안내)는 다시 받는 동안 빠진다 — 초점을 이 패널로 먼저 옮긴다(tabindex="-1") -->
            <ClampedPanel
              ref="aiMainRef"
              v-model:expanded="aiExpanded"
              class="skx-pai-main"
              tabindex="-1"
              :collapsed-rem="20"
              more-label="전체보기"
              scroll-anchor=".skx-aip"
            >
              <!-- 글 없이 실패하면 칸 안은 비우고 아래(#after) 안내만 보인다 -->
              <div v-if="aiLoading || aiText || !aiError" class="skx-pai-main__scroll">
                <template v-if="aiLoading && !aiText">
                  <div class="skx-pai-section">
                    <p class="skx-pai-section__text" style="color: #999">
                      AI가 논문을 분석하고 있습니다<span
                        class="skx-stream-cursor"
                      />
                    </p>
                  </div>
                </template>
                <!-- 요약이 끝난 뒤(참고 목록이 정해진 뒤)에는 (1)·(1, 3) 인용 번호를 눌러 그 논문 카드를 본다 -->
                <!-- 원문 보기는 팝오버가 파일을 먼저 확인하고(CitePopover — usePdfOpener) 있을 때만 알린다 -->
                <SummaryText
                  v-else-if="aiText"
                  :html="renderedAiText"
                  :refs="summaryRefs"
                  :linked="!aiLoading"
                  @detail="(id) => navigateTo(paperDetailUrl(id))"
                  @pdf="openCheckedPdf"
                  @chat="(id) => (chatPaperId = id)"
                  @reveal="aiExpanded = true"
                />
                <!-- 글 없이 끝난 요약(옛 서버의 빈 답·글 없는 기록) — 실패가 아닌 빈 상태 -->
                <SkxErrorState v-else kind="empty" compact :title="PAPER_STATE_TEXT.summaryEmpty" />
              </div>
              <!-- 요약을 만들지 못했다(서버의 {error}·끊김) — 받은 글이 있으면 그 아래에, 글에 잇지 않고 따로. 접히는 칸 밖이라
                   받은 글이 길어 접혀도 늘 보인다(접힌 채로는 페이드와 '전체보기'만 보여 끊긴 요약을 다 받은 것으로 읽었다).
                   문구는 화면의 해요체 상수(AI_SUMMARY_FAILED — 서버 문구는 쓰지 않는다) -->
              <template #after>
                <SkxInlineError
                  v-if="aiError && !aiLoading"
                  :class="['skx-pai-main__failed', !aiText && 'is-alone']"
                  :message="aiError"
                  @retry="retryAiSummary"
                />
              </template>
            </ClampedPanel>
            <!-- 우측: 참고 논문 목록 — 번호·제목(누르면 상세)·저자만. 원문 보기·DeepRead 는 요약 속 번호의 팝오버와 결과 카드에, 출처 인용은
                 결과 카드에 있어 카드마다 달던 아이콘 버튼 셋은 뺐다(사용자 결정 2026-10-14) -->
            <div class="skx-pai-refs">
              <div class="skx-pai-refs__scroll">
                <div v-for="ref in aiRefs" :key="ref.num" class="skx-pai-ref">
                  <div class="skx-pai-ref__num">{{ ref.num }}</div>
                  <div class="skx-pai-ref__body">
                    <!-- 버튼 셋이 빠져 이 줄에서 키보드로 닿는 것은 제목뿐이라 링크로 둔다(전에는 클릭만 받는 <p>) -->
                    <NuxtLink class="skx-pai-ref__title skx-pai-ref__title--link" :to="paperDetailUrl(ref.book_id)">
                      {{ ref.title }}
                    </NuxtLink>
                    <p class="skx-pai-ref__author">{{ ref.authors }}</p>
                  </div>
                </div>
                <template v-if="aiLoading && !aiRefs.length">
                  <div
                    v-for="n in Math.min(pagedPapers.length, 5)"
                    :key="n"
                    class="skx-pai-ref"
                  >
                    <div class="skx-pai-ref__num">{{ n }}</div>
                    <div class="skx-pai-ref__body">
                      <p class="skx-pai-ref__title">
                        {{ pagedPapers[n - 1]?.book_info?.title || "" }}
                      </p>
                      <p class="skx-pai-ref__author">
                        {{
                          pagedPapers[n - 1]?.book_info?.personal_author || ""
                        }}
                      </p>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </AiResultPanel>

          <!-- 이 결과에서 이어서 DeepResearch 로 — 바로 시작하지 않고 위 검색바에 질문을 채워 고쳐 보내게 한다 -->
          <div v-if="paperResult?.books.length" class="skx-deeper">
            <button type="button" class="skx-deeper__btn" @click="continueAsDeepResearch">
              <span aria-hidden="true">+</span> {{ DEEP_RESEARCH }}로 이어서 조사하기
            </button>
          </div>

          <!-- 논문 목록 -->
          <section class="skx-paper-section" aria-label="논문 검색 결과 목록">
            <!-- 머리: 총 N 건 | 정렬 · 개수 -->
            <ResultListHead :count="filteredPapers.length">
              <ResultSortControls
                :sort-by="sortBy"
                :page-size="pageSize"
                @sort="setSortBy"
                @size="setPageSize"
              />
            </ResultListHead>

            <!-- 결과 0건 — 실패(위 상태 블록)와 가른 빈 상태 -->
            <SkxErrorState
              v-if="!filteredPapers.length"
              kind="empty"
              :title="PAPER_STATE_TEXT.searchEmpty"
              :message="PAPER_STATE_TEXT.searchEmptyHint"
            />

            <!-- 논문 목록 -->
            <div v-else class="skx-paper-list">
              <h2 class="skx-sr-only">논문 목록</h2>
              <!-- 원문 보기는 파일을 먼저 확인하고 연다(usePdfOpener) — 없으면 그 카드 아래에 알린다 -->
              <ResultCard
                v-for="paper in pagedPapers"
                :key="paper.book_id"
                :item="paper"
                kind="paper"
                show-cite
                :anchor="resultAnchor(paper.book_id)"
                :ai-cited-num="aiRefNumMap.get(paper.book_id) ?? null"
                :pdf-problem="resultPdfProblem?.id === paper.book_id ? resultPdfProblem.message : ''"
                :pdf-busy="checkingPdfId === paper.book_id"
                @open="goToDetail(paper, $event)"
                @chat="goToDetail(paper, $event, { chat: '1' })"
                @pdf="openResultPdf(paper)"
                @cite="openPaperCitation(paper)"
              />
            </div>

            <!-- 쪽 이동 -->
            <ResultPager :page="currentPage" :total="totalPages" @go="currentPage = $event" />
          </section>
        </template>
      </div>
    </main>

    <!-- 출처 인용 모달 (CitationModal 컴포넌트 재사용) -->
    <CitationModal
      :open="citeModalOpen"
      :book-id="citeBookId"
      :references="citeRefs"
      @close="citeModalOpen = false"
    />

    <!-- PDF 뷰어 — 파일을 확인한 원문만 연다(결과 카드: openResultPdf, 요약 팝오버: CitePopover 가 확인) -->
    <PdfViewer
      v-if="pdf"
      :cnts-id="pdf.cntsId"
      :title="pdf.title"
      @close="closePdf"
    />

    <!-- 논문 채팅 패널 -->
    <aside :class="['skx-chat-panel', !!chatPaperId && 'is-open']">
      <div class="skx-chat-panel__inner">
        <div class="skx-chat-header">
          <button
            type="button"
            class="skx-chat-close"
            @click="chatPaperId = null"
          >
            <img src="/img/ico-arrow.svg" alt="" class="skx-chat-close__ico" />
          </button>
          <h2 class="skx-chat-title">
            DeepRead<template v-if="chatPaperTitle"
              >: {{ chatPaperTitle }}</template
            >
          </h2>
        </div>
        <BookChat
          v-if="chatPaperId"
          :cnts-id="chatPaperId"
          :book-title="chatPaperTitle"
          doc-kind="paper"
          @close="chatPaperId = null"
        />
      </div>
    </aside>

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast" role="status" aria-live="polite">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import type { ComponentPublicInstance } from "vue";
import { API_SEARCH_TIMEOUT_MS, apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
import { usePdfOpener } from "~/composables/usePdfOpener";
import { useDetailLeave, useRestorePosition } from "~/composables/useRestorePosition";
import { usePageLeaving } from "~/composables/usePageLeaving";
import { rememberListView, savedListView } from "~/composables/useListView";
import { safeLocalStorage } from "~/utils/browserId";
import { DEEP_RESEARCH, SPINNER_SRC } from "~/utils/brand";
import { detailUrl, resultAnchor, type ReturnSpot } from "~/utils/detailSource";
import { detailScoreParams } from "~/utils/relevance";
import { slimPaperResult } from "~/utils/historySnapshot";
import { holdsReturnSpot, pageOfItem, spotOf } from "~/utils/restorePosition";
import {
  DEFAULT_SORT,
  pageCount,
  pageSlice,
  restoredPage,
  sortResults,
  type PageSize,
  type SortKey,
} from "~/utils/resultPaging";
import { readV1Map } from "~/utils/historyStore";
import { awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import { readResearchDraft } from "~/utils/paperResearch";
import { citeYear, type SummaryRef } from "~/utils/summaryCite";
import type { SearchModeId } from "~/utils/slashCommand";
import type { BookSearchResponse, BookChunkGroup } from "~/types/search";
import type { PaperEntry, PaperSnapshot } from "~/types/history";
import { hasQuery, SEARCH_QUERY_MAX } from "~/utils/searchInput";
import { AI_SUMMARY_FAILED, type AiStreamEnd, failureText, readAiStream } from "~/utils/aiStream";
import { isRetryableKind, PAPER_STATE_TEXT, shownError, type ShownError } from "~/utils/paperErrors";

const api = useApi();
const route = useRoute();
const router = useRouter();

const historyApi = useHistory();
const currentHistoryId = ref<string | null>(null);
// 검색·복원·요약 스트림을 한 묶음으로 끊는다 — 새 검색이나 복원이 시작되면 이전 묶음의
// 응답·스트림·저장이 새 화면과 새 기록을 덮지 못하게 한다
let runCtrl: AbortController | null = null;
function beginRun(): AbortSignal {
  runCtrl?.abort();
  runCtrl = new AbortController();
  return runCtrl.signal;
}

// ── 검색 상태 ────────────────────────────────────────────────
const currentQuery = ref("");
// 화면에 떠 있는 결과의 검색어(앞뒤 공백 제거) — currentQuery 는 검색바 v-model 이라 사용자가 고치는 중일 수 있어,
// 결과에 묶인 이동·주소 비교는 이 값을 쓴다
const resultQuery = ref("");
const loading = ref(false);
// 검색 실패 — 결과 자리의 상태 블록(kind·이유). failedSearch 는 [다시 시도]가 같은 검색(기록을 채우던 검색이면 그 기록까지)으로 다시 보내게 쥔다
const searchError = ref<ShownError | null>(null);
let failedSearch: { query: string; reuse?: PaperEntry } | null = null;
const paperResult = ref<BookSearchResponse | null>(null);
// 결과 자리(.skx-rframe) — 검색 실패의 [다시 시도]가 초점을 옮겨 둔다
const frameRef = ref<HTMLElement | null>(null);

// 글자 수(SkxCharCount) — 입력창이 aria-describedby 로 가리킨다. 랜딩 입력 상자와 결과 검색바는 함께 그려지지 않지만 id 는 따로 둔다
const landingCountId = `papers-count-${useId()}`;
const barCountId = `papers-bar-count-${useId()}`;

// ── 상세에서 돌아온 자리 ──────────────────────────────────────
// 결과는 기록에서 비동기로 복원해 브라우저·Nuxt 의 스크롤 복원이 목록보다 먼저 끝난다 — 맞출 자리(주소의 at·y,
// 없으면 그 기록의 state)가 있으면 Nuxt 는 맞추지 않고, 누른 카드를 목록이 그려진 뒤 직접 맞춘다
definePageMeta({ scrollToTop: (to) => !holdsReturnSpot(to.query, import.meta.client ? window.history.state : null) });
// 목록은 복원하는 순간 한 번에 그려져 늦게 붙는 카드가 없다 — 첫 프레임에 그 카드가 없으면(결과가 바뀜) 기다리지 않는다
const restore = useRestorePosition(
  computed(() => paperResult.value !== null && !loading.value),
  { maxWaitMs: 0 },
);
const { leave } = useDetailLeave();
// 결과를 그린 뒤 기록 저장을 기다리는 사이 상세로 떠나면 늦은 주소 바꾸기가 그 이동을 취소하지 않게(usePageLeaving)
const { leaving, markLeaving } = usePageLeaving();

// ── 인라인 채팅 ──────────────────────────────────────────────
const chatPaperId = ref<string | null>(null);
const chatPaperTitle = computed(() =>
  chatPaperId.value
    ? (aiRefPaperMap.value.get(chatPaperId.value)?.book_info?.title ?? "")
    : "",
);

// ── AI 요약 ──────────────────────────────────────────────────
const aiText = ref("");
const aiLoading = ref(false);
// 요약을 만들지 못했을 때 보일 문구(AI_SUMMARY_FAILED — 서버의 {error} 문구는 쓰지 않는다) — 받은 글에 잇지 않고 따로 보인다
const aiError = ref("");
const aiExpanded = ref(false);
// 요약 패널(ClampedPanel 의 뿌리 — tabindex="-1") — AI 요약 실패의 [다시 시도]가 초점을 옮겨 둔다
const aiMainRef = ref<ComponentPublicInstance | null>(null);
const aiRefs = ref<
  { num: number; book_id: string; title: string; authors: string }[]
>([]);
const renderedAiText = computed(() =>
  aiText.value ? (marked.parse(aiText.value) as string) : "",
);

// ── 정렬 / 페이지 ─────────────────────────────────────────────
const sortBy = ref<SortKey>(DEFAULT_SORT);
const pageSize = ref<PageSize>(20);
const currentPage = ref(1);

// ── PDF 뷰어 ─────────────────────────────────────────────────
// 원문 보기는 파일이 있는지 먼저 확인하고 연다(usePdfOpener — 논문 상세·딥리서치와 같다). 없으면 누른 결과 카드 아래에 알린다
const { pdf, checking: checkingPdf, openPdf, closePdf } = usePdfOpener();
const resultPdfProblem = ref<{ id: string; message: string } | null>(null);
// 지금 원문 파일을 확인하는 카드 — 그 카드의 [원문 보기]에만 aria-busy 를 단다(확인은 한 번에 하나라 다른 카드는 누름만 무시된다)
const checkingPdfId = ref<string | null>(null);

// 결과 카드의 [원문 보기] — 확인 중에 다른 카드를 눌러도 무시한다(openPdf 가 null 을 돌려줘 안내가 지워지지 않게).
// 확인하는 사이 결과가 바뀌었으면(랜딩으로·다른 검색) 그 결과에 없는 논문의 뷰어·안내를 남기지 않는다
async function openResultPdf(paper: BookChunkGroup) {
  if (checkingPdf.value) return;
  checkingPdfId.value = paper.book_id;
  let problem: string | null;
  try {
    problem = await openPdf({ cntsId: paper.book_id, title: paper.book_info?.title ?? "" });
  } finally {
    checkingPdfId.value = null;
  }
  if (!aiRefPaperMap.value.has(paper.book_id)) {
    if (!problem) closePdf();
    return;
  }
  resultPdfProblem.value = problem ? { id: paper.book_id, message: problem } : null;
}

// 요약 속 인용 번호 팝오버의 [원문 보기] — 팝오버가 파일을 이미 확인했다(CitePopover)
function openCheckedPdf(bookId: string) {
  resultPdfProblem.value = null;
  pdf.value = { cntsId: bookId, title: aiRefPaperMap.value.get(bookId)?.book_info?.title ?? "" };
}

// ── 인용 모달 ─────────────────────────────────────────────────
const citeModalOpen = ref(false);
const citeBookId = ref<string | null>(null);
const citeRefs = ref<string[]>([]);

// ── Toast ─────────────────────────────────────────────────────
const toast = ref("");
function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

// ── 계산 ─────────────────────────────────────────────────────
const hasResults = computed(() => paperResult.value !== null || loading.value);

// 고른 정렬·개수·쪽을 이 방문 기록(history.state)에 남긴다 — 소장자료 결과와 같다. 상세에서 돌아오면 applyPaperEntry 가 읽는다
rememberListView(sortBy, pageSize, currentPage, () => hasResults.value);

// 인용한 답이 있는가 — 요약을 만들지 못했고(실패) 받은 글도 없으면 없다. 서버가 실패 앞에 보내는 참고 목록(sources — 넘겨준
// 논문이라 맞다)은 오른쪽 참고 칸에만 쓰고, 결과 카드의 칩·고정에는 쓰지 않는다(전에는 요약 없이 'AI 답변 인용 N' 칩이 붙고 카드가 위로 올라갔다)
const aiCited = computed(() => !aiError.value || !!aiText.value.trim());

// AI 답변 인용 논문: book_id → 인용 번호 (우측 참고 카드 번호와 동일) — 결과 카드의 'AI 답변 인용 N' 칩과 위로 고정에 쓴다
const aiRefNumMap = computed(() => {
  const m = new Map<string, number>();
  if (!aiCited.value) return m;
  for (const r of aiRefs.value) m.set(r.book_id, r.num);
  return m;
});

// 요약 속 인용 번호가 가리키는 논문 — 오른쪽 참고 목록(aiRefs)의 번호·제목·저자와 그 논문의 발행 연도
const summaryRefs = computed<SummaryRef[]>(() =>
  aiRefs.value.map((r) => ({
    num: r.num,
    book_id: r.book_id,
    title: r.title,
    authors: r.authors,
    year: citeYear(aiRefPaperMap.value.get(r.book_id)?.book_info?.pub_date),
    grade: (aiRefPaperMap.value.get(r.book_id)?.book_info?.grade ?? "").trim(),
  })),
);

const aiRefPaperMap = computed(() => {
  const map = new Map<string, BookChunkGroup>();
  for (const p of paperResult.value?.books ?? []) {
    map.set(p.book_id, p);
  }
  return map;
});

const sortedPapers = computed(() =>
  paperResult.value ? sortResults(paperResult.value.books, sortBy.value) : [],
);

const filteredPapers = computed(() => {
  const base = sortedPapers.value;
  if (!aiRefNumMap.value.size) return base;
  // AI 답변에 인용된 논문을 인용 번호 순으로 상단 고정, 나머지는 선택 정렬 유지
  const cited = base
    .filter((p) => aiRefNumMap.value.has(p.book_id))
    .sort(
      (a, b) =>
        (aiRefNumMap.value.get(a.book_id) ?? 0) -
        (aiRefNumMap.value.get(b.book_id) ?? 0),
    );
  const rest = base.filter((p) => !aiRefNumMap.value.has(p.book_id));
  return [...cited, ...rest];
});

const totalPages = computed(() => pageCount(filteredPapers.value.length, pageSize.value));

const pagedPapers = computed(() => pageSlice(filteredPapers.value, currentPage.value, pageSize.value));

// ── 유틸 ─────────────────────────────────────────────────────
function monthStr(pubDate: string): string {
  const m = pubDate?.slice(4, 6);
  return m ? `${parseInt(m)}월` : "";
}

function setSortBy(key: SortKey) {
  sortBy.value = key;
  currentPage.value = 1;
}

function setPageSize(n: PageSize) {
  pageSize.value = n;
  currentPage.value = 1;
}

function formatPubDate(pubDate: string): string {
  const m = pubDate.match(/(\d{4})[.\-]?(\d{1,2})/);
  if (!m || !m[1] || !m[2]) return pubDate;
  return `${m[1]}년 ${parseInt(m[2])}월`;
}

function openPaperCitation(paper: BookChunkGroup) {
  citeBookId.value = paper.book_id;
  citeRefs.value = paper.book_info?.references ?? [];
  citeModalOpen.value = true;
}

// 상세로 갈 때 출처(이 검색 기록)를 넘긴다 — 상세에서도 사이드바가 이 기록을 강조하고, [검색 목록 돌아가기]가 재검색 없이
// 복원된다. q 는 검색바가 아니라 화면 결과의 검색어다(함께 넘기는 h 와 같은 검색).
// 관련도(종합·제목·내용 점수)도 함께 싣는다 — 상세 머리의 관련도 알약과 일치율 팝오버가 읽는다. 점수는 이 화면 결과(paperResult)의
// 그 논문에서 찾는다 — 결과 카드·참고 목록·AI 답변 인용이 모두 같은 결과에서 온 논문이라 어느 길로 가도 같은 값이 실린다
function paperDetailUrl(bookId: string, spot?: ReturnSpot, extra: Record<string, string> = {}): string {
  const hit = paperResult.value?.books.find((b) => b.book_id === bookId);
  return detailUrl(
    bookId,
    { kind: "search", h: currentHistoryId.value, q: resultQuery.value },
    spot,
    { ...detailScoreParams(hit), ...extra },
  );
}

// 누른 카드의 지금 화면 높이를 싣고 떠난다 — [검색 목록 돌아가기]·뒤로 가기로 돌아오면 이 카드를 같은 높이에 맞춘다
function goToDetail(paper: BookChunkGroup, e: MouseEvent, extra: Record<string, string> = {}) {
  const card = (e.currentTarget as HTMLElement).closest<HTMLElement>("[data-anchor]")!;
  const spot = spotOf(card, resultAnchor(paper.book_id));
  markLeaving();
  void leave(paperDetailUrl(paper.book_id, spot, extra), spot);
}

// ── 검색 ─────────────────────────────────────────────────────
async function handleSearch(q?: string, reuse?: PaperEntry) {
  const query = (q ?? currentQuery.value).trim();
  if (!query || loading.value) return;
  const signal = beginRun();
  currentQuery.value = query;
  resultQuery.value = query;
  currentHistoryId.value = null;
  // 주소의 이전 h 도 함께 내린다 — 남겨 두면 검색이 도는 동안·실패한 뒤에도 사이드바가 이전 기록을 강조하고,
  // 그 기록을 누르면 지금 주소와 같아 이동이 무시되며, 새로고침하면 이전 기록이 열린다
  router.replace({ query: { q: query } });
  loading.value = true;
  searchError.value = null;
  failedSearch = null;
  resultPdfProblem.value = null;
  paperResult.value = null;
  aiText.value = "";
  aiRefs.value = [];
  aiLoading.value = false;
  aiError.value = "";
  aiExpanded.value = false;
  currentPage.value = 1;
  sortBy.value = DEFAULT_SORT;

  try {
    const data = await api<BookSearchResponse>("/papers/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 20,
        // 논문 검색은 서버가 재작성하지 않는다(app/api/paper.py — 사용자 결정 2026-10-14) — 보내는 값도 그에 맞춘다
        use_rewrite: false,
        use_rerank: true,
      },
      signal,
      // 읽기 성격 POST — 게이트웨이 한도(120초)까지 스피너만 돌지 않게 검색 제한(60초)에서 끊고 시간 초과로 알린다
      timeout: API_SEARCH_TIMEOUT_MS,
    });
    if (signal.aborted) return;
    paperResult.value = data;
    loading.value = false;
    // 요약할 논문이 있으면 기록 저장을 기다리는 동안도 '분석 중'으로 둔다 — 요약 스트림은 저장 뒤에 시작해,
    // 그 사이 'AI 요약이 없어요'(빈 상태)가 먼저 보였다가 바뀌었다
    if (data.books?.length) aiLoading.value = true;

    // 기록 id 를 먼저 확정해 요약 스트림에 넘긴다 — 끝난 뒤 저장이 그 사이 바뀐 화면의 기록을 덮지 않게
    const snapshot = slimPaperResult(data) ?? undefined;
    const entry = reuse
      ? ((await historyApi.patch(reuse.id, { snapshot })) ?? reuse)
      : await historyApi.add({ kind: "paper", title: query, params: {}, snapshot });
    if (signal.aborted) return;
    currentHistoryId.value = entry.id;
    if (!leaving.value) router.replace({ query: { q: query, h: entry.id } });
    if (data.books?.length) streamAiSummary(entry.id, query, data.books, signal);
  } catch (e) {
    if (signal.aborted) return;
    // 서버 detail·ofetch 의 영문 메시지('[POST] "/api/papers/search": 500 …')는 보이지 않는다 — 이유는 오류 규칙(apiErrors)이 고른다.
    // 일부러 끊은 요청이 아닌데 null 이면(우리 signal 은 안 끊겼다) 이유 없는 실패로 둔다
    searchError.value = shownError(e) ?? { kind: "unknown", message: "" };
    failedSearch = { query, reuse };
    paperResult.value = { mode: "book", query, books: [], elapsed_ms: 0 };
    aiLoading.value = false;
  } finally {
    if (!signal.aborted) loading.value = false;
  }
}

// 검색 실패의 [다시 시도] — 같은 검색어로(기록을 채우던 검색이면 그 기록까지) 다시 보낸다.
// 누른 버튼(상태 블록)은 검색이 시작되면 빠진다 — 초점을 결과 자리로 먼저 옮겨 body 로 떨어지지 않게 한다
function retrySearch() {
  if (!failedSearch || loading.value) return;
  const { query, reuse } = failedSearch;
  frameRef.value?.focus();
  void handleSearch(query, reuse);
}

// 랜딩으로 되돌린다 — 진행 중인 검색·복원·요약 묶음을 끊고 결과 화면 상태를 비운다.
// hasResults 가 paperResult·loading 에서 나오므로 둘을 비우면 화면이 랜딩으로 바뀐다
function goLanding() {
  runCtrl?.abort();
  runCtrl = null;
  paperResult.value = null;
  loading.value = false;
  searchError.value = null;
  failedSearch = null;
  resultPdfProblem.value = null;
  currentQuery.value = "";
  resultQuery.value = "";
  currentHistoryId.value = null;
  aiText.value = "";
  aiRefs.value = [];
  aiLoading.value = false;
  aiError.value = "";
  // 결과 화면에서 연 창들도 닫는다 — 랜딩 위에 이전 결과의 논문 창이 남지 않게
  closePdf();
  citeModalOpen.value = false;
  chatPaperId.value = null;
}

// 논문 상세의 [이 논문으로 딥리서치]가 넘긴 질문 초안(?draft=) — 검색하지 않고 랜딩 입력창에 딥리서치 칩을
// 켠 채 채운다. 주소에서는 draft 만 지운다: 남겨 두면 새로고침·뒤로 가기로 올 때마다 고쳐 쓰던 글을 초안이 다시 덮는다
const plusMenu = ref<{ activateMode: (id: SearchModeId) => void } | null>(null);

// 결과 화면의 [딥리서치로 이어서 조사하기] — 지금 결과의 질의를 상단 검색바에 채우고 딥리서치 모드를 켜 초점을 둔다.
// 연구 잡은 만들지 않는다: 사용자가 보내기를 누르면 기존 흐름(계획 카드)으로 간다
function continueAsDeepResearch() {
  if (resultQuery.value) currentQuery.value = resultQuery.value;
  // 입력창 값이 바뀐 뒤에 켜야 초점이 글 끝에 간다
  nextTick(() => plusMenu.value?.activateMode("deep-research"));
}

function fillResearchDraft() {
  const draft = readResearchDraft(route.query);
  if (!draft) return;
  const { draft: _draft, ...rest } = route.query;
  router.replace({ query: rest });
  currentQuery.value = draft;
  // 입력창 값이 바뀐 뒤에 켜야 초점이 글 끝에 간다
  nextTick(() => plusMenu.value?.activateMode("deep-research"));
}

// ── 기록 복원 ─────────────────────────────────────────────────
// 주소(?h=)가 복원의 정본이다 — 사이드바·뒤로가기·새로고침이 모두 이 한 길로 들어온다
async function restoreFromQuery() {
  // 다른 페이지로 넘어가는 중에는 그 주소의 q 로 재검색하지 않는다
  if (route.path !== "/papers") return;
  const query = route.query;
  const v1Map = readV1Map(safeLocalStorage());
  let target = readHistoryQuery(query, v1Map);
  if (awaitsV1Map(query, v1Map)) {
    // 사이드바가 시작한 이전이 대응표를 남길 때까지 기다린다 — 주소가 그대로라 지금 랜딩으로 빠지면 다시 복원할 계기가 없다.
    // 기다리는 사이 다른 복원·검색·이동이 끼면 그쪽이 묶음을 가져가 이 복원은 물러난다
    const signal = beginRun();
    loading.value = false;
    await historyApi.migrated();
    if (signal.aborted) return;
    target = readHistoryQuery(query, readV1Map(safeLocalStorage()));
  }
  const { h, q } = target;
  if (!h) {
    if (!q) {
      // 기록도 검색어도 없는 주소는 랜딩이다 — 같은 경로라 다시 마운트되지 않으므로(랜딩에서 기록을 연 뒤
      // 뒤로가기 등) 결과 화면과 진행 중인 요청을 직접 걷는다. 안 걷으면 주소는 '/papers' 인데 결과가 남는다
      goLanding();
      fillResearchDraft();
      return;
    }
    // 검색바가 아니라 화면 결과의 검색어와 비교한다 — 검색바를 고쳐 둔 채 이 주소로 오면 엉뚱하게 건너뛴다.
    // 둘 다 앞뒤 공백을 뗀 값이라 같은 검색어를 공백 차이로 다시 찾지 않는다
    if (q !== resultQuery.value) {
      await handleSearch(q);
    }
    return;
  }
  if (h === currentHistoryId.value) return;

  const signal = beginRun();
  loading.value = false;
  const entry = await historyApi.get(h);
  if (signal.aborted) return;
  if (entry && entry.kind !== "paper") {
    // 다른 종류의 기록 id 가 이 주소로 왔다(옛 ?restore= 등) — 그 종류의 주소로 보낸다
    router.replace(routeFor(entry));
    return;
  }
  const paper = entry?.kind === "paper" ? entry : null;
  if (paper?.snapshot) {
    applyPaperEntry(paper, signal);
    return;
  }
  // 없거나 남의 기록이면 검색어로 새로 찾는다(D7). 결과만 비어 있던 내 기록은 같은 id 를 채운다
  if (!paper) void historyApi.refresh("paper");
  const retryQuery = q ?? paper?.title;
  if (retryQuery) {
    await handleSearch(retryQuery, paper ?? undefined);
    return;
  }
  // 이 복원이 beginRun 으로 끊은 요약(스트림·기록 저장 대기)이 이어받을 화면 없이 끝나는 길 — '분석 중'으로 굳지 않게 매듭짓는다
  settleAiSummary();
  showToast(PAPER_STATE_TEXT.missingHistory);
}

function applyPaperEntry(entry: PaperEntry, signal: AbortSignal) {
  const snap = entry.snapshot as PaperSnapshot;
  loading.value = false;
  searchError.value = null;
  failedSearch = null;
  resultPdfProblem.value = null;
  currentQuery.value = entry.title;
  resultQuery.value = entry.title;
  currentHistoryId.value = entry.id;
  paperResult.value = {
    mode: "book",
    query: entry.title,
    books: snap.books as unknown as BookChunkGroup[],
    elapsed_ms: 0,
  };
  aiText.value = entry.ai?.text ?? "";
  aiRefs.value = (entry.ai?.refs ?? []) as typeof aiRefs.value;
  aiLoading.value = false;
  aiError.value = "";
  aiExpanded.value = true;
  // 상세에서 뒤로 가기·새로고침으로 같은 기록에 돌아왔으면 그때 고른 정렬·개수를 다시 연다(그 방문 기록의 state — 소장자료 결과와
  // 같다). 새로 연 기록은 기본 정렬이고 개수는 지금 고른 대로 둔다
  const saved = savedListView();
  sortBy.value = saved?.sortBy ?? DEFAULT_SORT;
  if (saved) pageSize.value = saved.pageSize;
  // 정렬·개수를 정한 뒤에 찾아야 화면 목록과 같은 순서·쪽이다. 누른 카드가 있으면 그 카드가 있는 쪽이 먼저이고(카드 자리 복원),
  // 없으면 남긴 쪽, 그것도 없으면 첫 쪽
  const before = currentPage.value;
  currentPage.value = restoredPage(returnPage(), saved, filteredPapers.value.length, pageSize.value);
  if (currentPage.value !== before) skipPageScroll = true;
  if (!leaving.value && (route.query.h !== entry.id || route.query.q !== entry.title)) {
    router.replace({ query: { q: entry.title, h: entry.id } });
  }
  // 요약이 끝나기 전에 떠난 기록은 요약이 비어 있다 — 복원할 때 한 번 더 만든다
  if (!entry.ai && snap.books.length) streamAiSummary(entry.id, entry.title, snap.books, signal);
}

// 상세에서 돌아왔으면 그 카드가 있는 쪽 — 기록은 화면이 쪽으로 나눠 보인 결과를 모두 담아(slimPaperResult) 둘째 쪽 이후의
// 카드도 찾는다. 정렬·쪽 크기는 호출하는 쪽이 먼저 정해 둔 것(남긴 보기 또는 기본값)으로 찾는다. 누른 카드가 없으면 null
function returnPage(): number | null {
  const anchor = restore.pending.value ? restore.anchor : null;
  if (anchor?.kind !== "result") return null;
  return pageOfItem(filteredPapers.value.map((p) => p.book_id), anchor.cnts, pageSize.value);
}

// ── AI 요약 SSE ───────────────────────────────────────────────
type SummarySource = {
  book_id: string;
  book_info?: { title?: string; personal_author?: string; corporate_author?: string };
};

async function streamAiSummary(
  historyId: string | null,
  query: string,
  books: SummarySource[],
  signal: AbortSignal,
) {
  aiLoading.value = true;
  aiError.value = "";
  const papers = books.slice(0, 5).map((b) => ({
    book_id: b.book_id,
    title: b.book_info?.title || "",
    authors:
      b.book_info?.personal_author || b.book_info?.corporate_author || "",
    best_chunk_text: "",
  }));
  let text = "";
  let refs: typeof aiRefs.value = [];
  let end: AiStreamEnd = { ok: false, error: null };
  try {
    const resp = await fetch(apiUrl("/papers/summary/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ query, papers }),
      signal,
    });
    end = await readAiStream(resp, (evt) => {
      if (typeof evt.text === "string" && evt.text) {
        text += evt.text;
        aiText.value = text;
      }
      // 참고 목록(sources)은 끝난 뒤 실패 여부와 함께 한 번에 건다 — 서버는 실패해도 {error} 바로 앞에 보내, 따로 걸면
      // 두 이벤트가 다른 조각으로 오는 사이 결과 카드가 'AI 답변 인용' 칩과 함께 위로 올라갔다 내려왔다(aiRefNumMap)
      if (Array.isArray(evt.sources)) refs = evt.sources;
    });
  } catch {
    /* 중단·네트워크 오류 — 아래에서 가린다 */
  }
  // 끊긴 묶음은 저장하지 않는다 — 화면과 기록은 이미 다음 묶음의 것이다
  if (signal.aborted) return;
  aiLoading.value = false;
  aiRefs.value = refs;
  // 끝까지 받은 요약만 기록에 저장한다. 실패({error}·끊김)면 받은 글은 보이되 오류 문구를 잇지 않고 따로 보이며,
  // 기록에 남기지 않아 다시 열면(applyPaperEntry) 다시 만든다. 기록 id 가 없으면(저장 전에 끊긴 검색의 [다시 시도]) 보이기만 한다
  if (end.ok) {
    if (text && historyId) void historyApi.patch(historyId, { ai: { text, refs } });
  } else {
    aiError.value = failureText(end, AI_SUMMARY_FAILED);
  }
}

// [다시 시도] — 지금 결과(기록·검색어·논문)로 AI 요약을 처음부터 다시 받는다.
// 누른 버튼(줄 안내)은 다시 받는 동안 빠진다 — 초점을 요약 패널로 먼저 옮겨 body 로 떨어지지 않게 한다
function retryAiSummary() {
  const books = paperResult.value?.books;
  if (aiLoading.value || !books?.length) return;
  (aiMainRef.value?.$el as HTMLElement | undefined)?.focus();
  const signal = beginRun();
  aiText.value = "";
  aiRefs.value = [];
  void streamAiSummary(currentHistoryId.value, resultQuery.value, books, signal);
}

// 이 묶음이 끊겼는데 이어받는 새 묶음이 없을 때(없는 기록 토스트) 받는 중 표시가 남지 않게 매듭짓는다(소장자료 랜딩의 settleReason 과
// 같은 자리). 끊긴 요약은 만들지 못한 것으로 두어 [다시 시도]로 다시 받게 한다 — 받던 글이 있으면 그 아래에 안내가 붙는다
function settleAiSummary() {
  if (!aiLoading.value) return;
  aiLoading.value = false;
  aiError.value = AI_SUMMARY_FAILED;
}

// ── 주소 기준 첫 복원 ─────────────────────────────────────────
onMounted(() => {
  // 첫 복원을 setup 이 아니라 마운트 뒤에 한다 — 서버가 그린 랜딩과 하이드레이션이 어긋나지 않게
  restoreFromQuery();
});

// 같은 경로에서 쿼리만 바뀌면(사이드바 클릭·뒤로가기) 페이지가 다시 마운트되지 않는다.
// q 도 본다 — h 가 없는 주소(검색 중·실패 뒤의 ?q=)에서 랜딩 주소로 돌아오면 h 는 그대로 없어 변화를 놓친다
watch(
  [() => route.query.h ?? route.query.restore, () => route.query.q],
  () => {
    restoreFromQuery();
  },
);

// 페이지를 떠나면 요약 스트림도 끊는다 — 안 끊으면 GPU 생성이 끝까지 돈다
onBeforeUnmount(() => runCtrl?.abort());

// 돌아온 카드의 쪽을 여는 동안에는 맨 위로 올리지 않는다 — 그 카드 자리를 맞추는 중이다.
// 기록 복원(applyPaperEntry)이 쪽을 바꾼 것도 올리지 않는다 — 브라우저가 되돌린 스크롤을 덮지 않게
let skipPageScroll = false;
watch(currentPage, () => {
  if (skipPageScroll) {
    skipPageScroll = false;
    return;
  }
  if (!restore.pending.value) window.scrollTo({ top: 0, behavior: "smooth" });
});
</script>

<style scoped>
/* [다시 시도] 뒤 초점을 받는 자리(결과 자리·요약 패널 — tabindex="-1"). 마우스로 누른 뒤에는 테두리를 그리지 않고,
   키보드로 왔을 때만 그린다(연결 띠 .skx-conn 과 같은 규칙) */
.skx-rframe:focus,
.skx-pai-main:focus {
  outline: none;
}
.skx-rframe:focus-visible,
.skx-pai-main:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
</style>
