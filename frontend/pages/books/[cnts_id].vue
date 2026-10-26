<template>
  <div class="skx-app">
    <!-- 상세 화면은 사이드바를 띠로 접은 채 열고, 그 폭을 넓은 DeepRead 창(.skx-chat-panel--wide)에 준다 -->
    <AppSidebar
      fold-on-enter
      @cart="showToast('대출 장바구니 기능은 준비 중이에요.')"
      @save="showToast('저장목록 기능은 준비 중이에요.')"
    />

    <!-- 상세 틀(Figma 2536:16714, 논문 상세와 같은 틀) — 위 알약 검색바 → 큰 틀(돌아가기 · 머리 · AI 큐레이션 · 관련 자료 추천 · 상세 서지 정보).
         모양은 assets/css/detail.css -->
    <main class="skx-result dt-page">
      <DetailSearchBar
        :initial="searchQuery"
        label="소장자료 검색어"
        placeholder="찾고 싶은 자료를 자연어로 검색해보세요"
        @submit="onSearch"
      />

      <!-- tabindex="-1" — 불러오기 실패의 [다시 시도]를 누르면 상태 블록이 버튼째 로딩 표시로 바뀌어, 초점을 이 틀로 옮긴다(retryPage) -->
      <div ref="frameRef" class="dt-frame" tabindex="-1">
        <!-- 뒤로가기 -->
        <button type="button" class="dt-back" @click="$router.back()">
          <img src="/img/ico-arrow.svg" alt="" />
          <span>검색 목록 돌아가기</span>
        </button>

        <!-- 로딩 -->
        <div v-if="pageLoading" class="dt-loading">
          <img :src="SPINNER_SRC" alt="" />
          <p>도서 정보를 불러오는 중...</p>
        </div>
        <!-- 불러오기 실패 — 404 는 '찾을 수 없어요'(다시 시도 없음), 그 밖은 이유 + [다시 시도]. 둘 다 [홈으로] -->
        <SkxErrorState
          v-else-if="pageFailure"
          :kind="pageFailure.kind"
          :title="pageFailure.title"
          :message="pageFailure.message"
          title-tag="h1"
          :on-retry="pageFailure.retry ? retryPage : undefined"
        >
          <button type="button" class="skx-state__action" @click="navigateTo('/')">{{ BOOK_DETAIL_TEXT.home }}</button>
        </SkxErrorState>

        <template v-else-if="book">
          <!-- 머리(서지) — 표지 · 칩 줄(관련도 · #키워드, 키워드가 없으면 분류 칩) · 제목 · 서지 표 · 오른쪽 버튼 열 -->
          <section class="dt-hero" aria-label="서지 정보">
            <div class="dt-hero__cover">
              <div class="dt-cover">
                <BookCover :book-id="cnts_id" />
              </div>
              <!-- AI 가 그린 표지일 때만 — 원문 첫 쪽(PDF 1p)이나 글자 표지(목업)에 붙으면 사실과 다르다(사용자 2026-10-26 확인) -->
              <p v-if="isDrawnCover(book.cover_image_key)" class="dt-cover-note">
                <span class="skx-ai-dot" aria-hidden="true"></span>
                AI가 도서 내용을 분석해 그려낸 표지입니다
              </p>
            </div>
            <div class="dt-hero__head">
              <div v-if="matchScore !== null || keywords.length || kdc" class="dt-chips">
                <RelevanceBadge
                  v-if="matchScore !== null"
                  :score="matchScore"
                  :title-score="titleScore"
                  :content-score="contentScore"
                />
                <span v-for="kw in keywords" :key="kw" class="skx-tag skx-tag--keyword">#{{ kw }}</span>
                <!-- 키워드가 하나도 없을 때만 — 도서관 분류(KDC) 이름 칩(결과 카드와 같은 규칙) -->
                <span v-if="kdc" class="skx-rc__kdc" :title="kdc.title">
                  <span class="skx-sr-only">{{ kdc.title }}: </span>{{ kdc.name }}
                </span>
              </div>
              <h1 class="dt-title">{{ book.title }}</h1>
            </div>
            <div class="dt-hero__meta">
              <DetailMeta :rows="metaRows" />
            </div>
            <div class="dt-hero__actions">
              <div class="dt-hero__row">
                <button
                  type="button"
                  class="dt-btn dt-btn--ghost"
                  :aria-busy="checkingPdf"
                  :aria-describedby="pdfProblem?.id === cnts_id ? 'bdetail-pdf-problem' : undefined"
                  @click="viewPdf(cnts_id, book.title)"
                >
                  원문 보기
                </button>
                <button
                  v-if="SHOW_MOCKS"
                  type="button"
                  class="dt-btn dt-btn--icon"
                  :aria-label="isBookmarked(cnts_id) ? '북마크 해제' : '북마크'"
                  @click="toggleBookmark(cnts_id)"
                >
                  <img :src="bookmarkIcon(cnts_id)" alt="" />
                </button>
              </div>
              <button
                type="button"
                class="dt-btn dt-btn--accent"
                :aria-expanded="chatPanelOpen"
                aria-controls="dt-chat"
                @click="chatPanelOpen = !chatPanelOpen"
              >
                <DetailSparkIcon />DeepRead
              </button>
            </div>
            <!-- 원문 파일이 없으면 뷰어 대신 머리 아래에 알린다 -->
            <SkxInlineError
              v-if="pdfProblem?.id === cnts_id"
              id="bdetail-pdf-problem"
              class="dt-hero__note"
              :message="pdfProblem.message"
            />
          </section>

          <!-- AI 큐레이션 — 가로 밑줄 탭 [추천 이유][줄거리][소개](글이 없는 탭은 뺀다) -->
          <section class="dt-section" aria-labelledby="bdetail-curation-title">
            <h2 id="bdetail-curation-title" class="dt-section__title">AI 큐레이션</h2>
            <DetailTabs
              v-if="curationTabs.length"
              :tabs="curationTabs"
              :model-value="activeCuration"
              label="AI 큐레이션"
              @update:model-value="detailTab = $event"
            >
              <template #default="{ active }">
                <template v-if="active === 'reason'">
                  <!-- 스트리밍 중: raw 텍스트 + 깜빡이는 커서, 완료 후: 마크다운 -->
                  <p v-if="reasonLoading && reasonText" class="dt-prose dt-stream">
                    {{ reasonText }}<span class="skx-stream-cursor" />
                  </p>
                  <p v-else-if="reasonLoading" class="dt-muted">
                    추천 이유를 생성하고 있습니다<span class="skx-stream-cursor" />
                  </p>
                  <div v-else-if="reasonText" class="dt-prose" v-html="renderedReason" />
                  <!-- 추천 이유를 받지 못했다(서버의 {error}·HTTP 오류·끊김, 끝까지 왔는데 글이 없음) — 받은 글이 있으면 그 아래에, 글에 잇지 않고 따로.
                       다 받은 뒤 글이 없으면 늘 이 안내라(streamReason) '추천 이유가 없어요' 같은 빈 상태 갈래는 두지 않는다 -->
                  <SkxInlineError
                    v-if="reasonError && !reasonLoading"
                    ref="reasonFailRef"
                    :message="reasonError"
                    @retry="retryReason"
                  />
                </template>
                <p v-else-if="active === 'plot'" class="dt-prose">{{ plotText }}</p>
                <p v-else-if="active === 'intro'" class="dt-prose">{{ book.introduction }}</p>
              </template>
            </DetailTabs>
            <SkxErrorState v-else kind="empty" compact :title="BOOK_DETAIL_TEXT.curationEmpty" />
          </section>

          <!-- 관련 자료 추천 — 제목으로 찾은 다른 소장자료 최대 4권(연관도 하한 아래는 비운다). 카드를 누르면 그 자료 상세로, [자세히 보기]는 요약 전문과 버튼.
               tabindex="-1" — 실패의 [다시 시도]를 누르면 상태 블록이 버튼째 '불러오는 중'으로 바뀌어, 초점을 이 절로 옮긴다(retryRelated) -->
          <section ref="relatedSectionRef" class="dt-section" aria-labelledby="bdetail-related-title" tabindex="-1">
            <h2 id="bdetail-related-title" class="dt-section__title">관련 자료 추천</h2>
            <p v-if="relatedLoading" class="dt-empty">불러오는 중...</p>
            <!-- 실패와 진짜 0건을 가른다 — 실패를 '없음'으로 보이지 않는다 -->
            <SkxErrorState
              v-else-if="relatedFailure"
              :kind="relatedFailure.kind"
              :title="relatedFailure.title"
              :message="relatedFailure.message"
              compact
              :on-retry="relatedFailure.retry ? retryRelated : undefined"
            />
            <SkxErrorState v-else-if="!relatedItems.length" kind="empty" compact :title="BOOK_DETAIL_TEXT.relatedEmptyTitle" />
            <div v-else class="dt-related__grid">
              <DetailRelatedCard
                v-for="rel in relatedItems"
                :key="rel.book_id"
                :to="relatedBookUrl(rel.book_id)"
                :title="rel.book_info?.title || rel.book_id"
                :author="formatAuthors(rel.book_info?.personal_author, rel.book_info?.corporate_author)"
                :meta="relatedMetaLine(rel.book_info, 'book')"
                :keywords="cardKeywords(rel.book_info)"
                :kdc="cardKeywords(rel.book_info).length ? null : kdcChip(rel.book_info?.kdc)"
                reason-label="AI 요약"
                pop-title="AI 요약"
                :reason="recoDesc(rel)"
                empty-text="요약 정보가 없어요."
                :expanded="openRelated === rel.book_id"
                @update:expanded="(open: boolean) => (openRelated = relatedOpenAfter(openRelated, rel.book_id, open))"
              >
                <template #cover>
                  <BookCover :book-id="rel.book_id" />
                </template>
                <template #badge>
                  <RelevanceBadge
                    :score="rel.best_score ?? rel.score"
                    :title-score="rel.title_score"
                    :content-score="rel.content_score"
                  />
                </template>
                <template #actions>
                  <NuxtLink :to="withChat(relatedBookUrl(rel.book_id))" class="dt-btn dt-btn--accent">
                    <DetailSparkIcon />DeepRead<span class="skx-sr-only">: {{ rel.book_info?.title || rel.book_id }}</span>
                  </NuxtLink>
                  <button
                    type="button"
                    class="dt-btn dt-btn--ghost"
                    :aria-busy="checkingPdf"
                    @click="viewPdf(rel.book_id, rel.book_info?.title ?? '')"
                  >
                    원문 보기
                  </button>
                </template>
                <template #note>
                  <SkxInlineError v-if="pdfProblem && pdfProblem.id === rel.book_id" :message="pdfProblem.message" />
                </template>
              </DetailRelatedCard>
            </div>
          </section>

          <!-- 상세 서지 정보 — 예전 '상세 정보' 표(값이 있는 행만) -->
          <DetailCollapse v-if="detailRows.length" v-model:open="detailOpen" title="상세 서지 정보">
            <DetailMeta :rows="detailRows" wide />
          </DetailCollapse>
        </template>
      </div>
    </main>

    <!-- 채팅 사이드 패널 — 도서를 불러온 뒤에만 연다(못 불러오면 안쪽의 닫기 버튼도 없는 빈 패널이 화면을 덮는다) -->
    <aside id="dt-chat" :class="['skx-chat-panel', 'skx-chat-panel--wide', chatPanelOpen && book && 'is-open']">
      <div class="skx-chat-panel__inner" v-if="book">
        <div class="skx-chat-header">
          <button
            type="button"
            class="skx-chat-close"
            aria-label="채팅 닫기"
            @click="chatPanelOpen = false"
          >
            <img src="/img/ico-arrow.svg" alt="" class="skx-chat-close__ico" />
          </button>
          <h2 class="skx-chat-title">
            <span class="skx-chat-title__brand">DeepRead</span>
            <span v-if="book?.title" class="skx-chat-title__doc">{{ book.title }}</span>
          </h2>
        </div>
        <BookChat
          :cnts-id="cnts_id"
          :book-title="book?.title"
          @close="chatPanelOpen = false"
        />
      </div>
    </aside>

    <!-- 대출 신청 모달 -->
    <div
      v-if="loanModalOpen"
      class="skx-modal-backdrop"
      role="dialog"
      aria-modal="true"
      @click.self="loanModalOpen = false"
    >
      <div class="skx-modal">
        <div class="skx-modal__head">
          <p class="skx-modal__title">대출 신청 완료</p>
          <p class="skx-modal__sub">해당 도서 대출 신청이 완료되었습니다!</p>
        </div>
        <div class="skx-modal__book">
          <p class="skx-modal__book-title">{{ book?.title }}</p>
        </div>
        <div class="skx-modal__actions">
          <button
            type="button"
            class="skx-modal__btn-cancel"
            @click="loanModalOpen = false"
          >
            취소
          </button>
          <button
            type="button"
            class="skx-modal__btn-confirm"
            @click="confirmLoan"
          >
            확인
          </button>
        </div>
      </div>
    </div>

    <!-- 대출 취소 모달 -->
    <div
      v-if="loanCancelModalOpen"
      class="skx-modal-backdrop"
      role="dialog"
      aria-modal="true"
      @click.self="loanCancelModalOpen = false"
    >
      <div class="skx-modal">
        <div class="skx-modal__head">
          <p class="skx-modal__title">대출 신청 취소</p>
          <p class="skx-modal__sub">도서 대출 신청이 취소되었습니다</p>
        </div>
        <div class="skx-modal__actions">
          <button
            type="button"
            class="skx-modal__btn-confirm"
            @click="cancelLoan"
          >
            확인
          </button>
        </div>
      </div>
    </div>

    <!-- PDF 뷰어 — 이 자료·관련 자료가 같이 쓴다 -->
    <PdfViewer
      v-if="pdf"
      :cnts-id="pdf.cntsId"
      :title="pdf.title"
      @close="closePdf"
    />

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast" role="status" aria-live="polite">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import type { ComponentPublicInstance } from "vue";
import { renderMarkdown } from "~/utils/markdown";
import { useBookmark } from "~/composables/useBookmark";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { API_SEARCH_TIMEOUT_MS, apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import type { BookInfo } from "~/types/search";
import { isDrawnCover } from "~/utils/bookCover";
import { firstValue, shouldGoBack } from "~/utils/detailSource";
import {
  activeTabKey,
  aiTabAvailable,
  bookDetailRows,
  bookMetaRows,
  detailSearchUrl,
  focusOwningPanel,
  focusRegion,
  formatAuthors,
  queryScore,
  relatedMetaLine,
  visibleTabs,
  withChat,
} from "~/utils/detailView";
import { kdcChip } from "~/utils/kdc";
import { cardKeywords } from "~/utils/resultCard";
import { relatedOpenAfter } from "~/utils/relatedCard";
import { SPINNER_SRC } from "~/utils/brand";
import { type AiStreamEnd, readAiStream } from "~/utils/aiStream";
import { BOOK_DETAIL_TEXT, failureView, reasonFailureText, type StateView } from "~/utils/bookErrors";
import { usePdfOpener } from "~/composables/usePdfOpener";

// ── 라우트 ─────────────────────────────────────────────────
const route = useRoute();
const router = useRouter();
const cnts_id = route.params.cnts_id as string;
const searchQuery = (route.query.q as string) || "";
const historyId = firstValue(route.query.h) ?? "";

const api = useApi();
// 페이지를 떠나면 추천 이유 스트림을 끊는다 — 안 끊으면 GPU 생성이 끝까지 돈다
const pageAbort = new AbortController();
onBeforeUnmount(() => pageAbort.abort());

// ── 도서 데이터 ────────────────────────────────────────────
const book = ref<BookInfo | null>(null);
const pageLoading = ref(true);
// 불러오기 실패(본문 자리의 상태 블록) — 404 는 '찾을 수 없어요', 그 밖은 이유 + [다시 시도]
const pageFailure = ref<StateView | null>(null);

useHead({ title: () => (book.value?.title ? `${book.value.title} — 소장자료` : "소장자료") });

// 관련도 알약은 결과 카드와 같은 RelevanceBadge — 퍼센트는 같은 relevancePct(내림 + 부동소수 보정) 한 규칙이고,
// 제목·내용 일치율은 알약을 올리거나 누르면 뜨는 팝오버에 링으로 보인다
const matchScore = computed(() => queryScore(route.query.score));
const titleScore = computed(() => queryScore(route.query.title_score));
const contentScore = computed(() => queryScore(route.query.content_score));

// 칩 — 결과 카드와 같은 규칙(키워드 최대 CARD_KEYWORD_LIMIT 개, 하나도 없으면 KDC 분류 칩)
const keywords = computed(() => cardKeywords(book.value));
const kdc = computed(() => (keywords.value.length ? null : kdcChip(book.value?.kdc)));
const metaRows = computed(() => bookMetaRows(book.value));
const detailRows = computed(() => bookDetailRows(book.value));
const detailOpen = ref(true);

// 위 검색바 — 들어온 검색과 같은 검색어면 그 결과로 돌아가고(기록 복원), 다르면 새 소장자료 검색
function onSearch(input: string): void {
  const params = new URLSearchParams({ q: searchQuery });
  if (historyId) params.set("h", historyId);
  const sameTo = `/?${params}`;
  const url = detailSearchUrl("book", input, searchQuery ? { q: searchQuery, to: sameTo } : null);
  if (!url) return;
  const prev = window.history.state?.back;
  if (url === sameTo && shouldGoBack(typeof prev === "string" ? prev : null, sameTo)) router.back();
  else void navigateTo(url);
}

// ── AI 큐레이션 ────────────────────────────────────────────
const reasonText = ref("");
const reasonLoading = ref(false);
// 추천 이유를 다 받았는지 — 받기 전에는 비어 있어도 [추천 이유] 탭을 둔다(곧 채워진다)
const reasonDone = ref(false);
// 추천 이유를 받지 못했을 때 보일 한 줄(reasonFailureText — 서버의 {error} 글(합쇼체)은 쓰지 않는다) — 받은 글에 잇지 않고 따로 보인다
const reasonError = ref("");
// 실패 안내(SkxInlineError) — [다시 시도]를 누르면 안내째 빠지므로 초점을 옮길 탭 본문을 이 요소에서 찾는다
const reasonFailRef = ref<ComponentPublicInstance | null>(null);
const renderedReason = computed(() =>
  renderMarkdown(reasonText.value),
);
const plotText = computed(() => book.value?.plot || book.value?.summary || "");

// 글이 없는 탭은 뺀다 — 추천 이유는 검색어가 있을 때만 만든다. 고른 탭이 빠지면 첫 탭. [추천 이유]는 [다시 시도]로 다시 받는
// 동안에도 남는다
const detailTab = ref<string | null>("reason");
const curationTabs = computed(() =>
  visibleTabs([
    { key: "reason", label: "추천 이유", available: !!searchQuery && aiTabAvailable({ loading: reasonLoading.value, done: reasonDone.value, text: reasonText.value, error: reasonError.value }) },
    { key: "plot", label: "줄거리", available: !!plotText.value },
    { key: "intro", label: "소개", available: !!book.value?.introduction },
  ]),
);
const activeCuration = computed(() => activeTabKey(detailTab.value, curationTabs.value));

// ── 연관 도서 ──────────────────────────────────────────────
// 시안의 4열 카드에 맞춰 4권
const RELATED_LIMIT = 4;
const relatedItems = ref<any[]>([]);
const relatedLoading = ref(false);
// 관련 자료를 불러오지 못함 — 진짜 0건(relatedItems 가 빈 채로 성공)과 가른다
const relatedFailure = ref<StateView | null>(null);
// [자세히 보기]로 연 카드 — 한 번에 하나
const openRelated = ref<string | null>(null);

function relatedBookUrl(id: string): string {
  return `/books/${id}?q=${encodeURIComponent(searchQuery)}`;
}

// ── UI 상태 ────────────────────────────────────────────────
const toast = ref("");

// Chat panel
const chatPanelOpen = ref(false);
// 사이드바 DeepRead 기록을 누르면(같은 자료 화면이면 다시 마운트되지 않는다) ?chat=1 이 다시 와 — 닫힌 딥리드 창을 연다
watch(
  () => route.query.chat,
  (v) => {
    if (v === "1" && book.value) chatPanelOpen.value = true;
  },
);

// Loan modals
const loanModalOpen = ref(false);
const loanCancelModalOpen = ref(false);
const isLoaning = ref(false);

function confirmLoan() {
  loanModalOpen.value = false;
  isLoaning.value = true;
}

function cancelLoan() {
  loanCancelModalOpen.value = false;
  isLoaning.value = false;
}

// Bookmark
const { isBookmarked, toggleBookmark, bookmarkIcon } = useBookmark();

// Toast
function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

// PDF viewer — 이 자료·관련 자료. 파일이 있는지 먼저 묻고 연다(usePdfOpener) — 없는 원문을 그대로 열면 pdf.js 의 영문 오류 화면이 뜬다.
// 열지 못한 까닭은 누른 버튼 쪽(이 자료면 머리 아래, 관련 자료면 그 카드)에 알린다
const { pdf, checking: checkingPdf, openPdf, closePdf } = usePdfOpener();
const pdfProblem = ref<{ id: string; message: string } | null>(null);
async function viewPdf(id: string, title: string) {
  // 확인 중에는 무시한다 — openPdf 가 null 을 돌려줘 안내가 지워지는 일이 없게
  if (checkingPdf.value) return;
  const problem = await openPdf({ cntsId: id, title });
  pdfProblem.value = problem ? { id, message: problem } : null;
}

// ── 초기화 ─────────────────────────────────────────────────
onMounted(() => {
  void loadPage();
});

// 도서를 불러오고, 불러왔으면 추천 이유·관련 자료를 받는다. 처음 열 때와 불러오기 실패의 [다시 시도](retryPage)가 부른다
async function loadPage() {
  await fetchBook();
  if (!book.value) return;
  // ?chat=1(결과의 DeepRead 버튼) → 채팅 패널 자동 오픈. 도서를 불러온 뒤에 연다
  if (route.query.chat === "1") chatPanelOpen.value = true;
  void streamReason();
  void fetchRelatedBooks();
}

// 불러오기 실패의 [다시 시도] — 상태 블록은 다시 불러오는 동안 버튼째 로딩 표시로 바뀌므로 초점을 상세 틀로 먼저 옮긴다(focusRegion)
const frameRef = ref<HTMLElement | null>(null);
function retryPage() {
  if (pageLoading.value) return;
  focusRegion(frameRef.value);
  void loadPage();
}

// ── 도서 fetch ─────────────────────────────────────────────
// 다시 시도하는 동안에는 로딩 표시가 상태 블록 자리를 잇는다(pageLoading 이 먼저 그려진다)
async function fetchBook() {
  pageLoading.value = true;
  try {
    const data = await api<BookInfo>(`/books/${cnts_id}`, { signal: pageAbort.signal });
    book.value = data;
    pageFailure.value = null;
  } catch (e: unknown) {
    // 떠나며 끊은 요청이면 아무것도 띄우지 않는다
    if (pageAbort.signal.aborted) return;
    pageFailure.value = failureView(e, BOOK_DETAIL_TEXT.failedTitle, {
      kind: "notFound",
      title: BOOK_DETAIL_TEXT.notFoundTitle,
      message: BOOK_DETAIL_TEXT.notFoundMessage,
    });
  } finally {
    pageLoading.value = false;
  }
}

// ── 추천 이유 SSE ──────────────────────────────────────────
// 처음 열 때와 [다시 시도](retryReason)가 부른다
async function streamReason() {
  reasonError.value = "";
  if (!searchQuery) {
    reasonDone.value = true;
    return;
  }
  reasonLoading.value = true;
  reasonText.value = "";
  let end: AiStreamEnd = { ok: false, error: null };
  try {
    const resp = await fetch(apiUrl("/books/reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        query: searchQuery,
        book_id: cnts_id,
        chunk_texts: [],
        rewritten_query: "",
      }),
      signal: pageAbort.signal,
    });
    end = await readAiStream(resp, (json) => {
      if (typeof json.text === "string" && json.text) reasonText.value += json.text;
    });
  } catch {
    /* 떠남(pageAbort)·네트워크 오류 — 아래에서 가린다 */
  }
  reasonLoading.value = false;
  reasonDone.value = true;
  if (pageAbort.signal.aborted) return;
  // 이 화면은 추천 이유를 저장하지 않는다 — 실패({error}·HTTP 오류·끊김)면 받은 글에 잇지 않고 안내를 따로 보인다.
  // 끝까지 왔는데 글이 없어도(공백뿐 포함) 실패다 — 새 서버는 LLM 빈 답을 {error} 로, 옛 서버는 빈 채로 [DONE] 을 보낸다. 결과 화면의
  // 추천 1권과 같은 처리이고, 그래야 [추천 이유] 탭이 말없이 빠지지 않고 [다시 시도]와 함께 남는다(aiTabAvailable)
  if (!reasonText.value.trim()) reasonText.value = "";
  if (!end.ok || !reasonText.value) reasonError.value = reasonFailureText(reasonText.value);
}

// [다시 시도] — 추천 이유를 처음부터 다시 받는다. 버튼은 안내째 빠지므로 초점을 탭 본문으로 먼저 옮긴다
function retryReason() {
  if (reasonLoading.value) return;
  focusOwningPanel(reasonFailRef.value?.$el ?? null);
  void streamReason();
}

// 관련 자료 실패의 [다시 시도] — 상태 블록은 다시 받는 동안 버튼째 '불러오는 중'으로 바뀌므로 초점을 이 절로 먼저 옮긴다(focusRegion)
const relatedSectionRef = ref<HTMLElement | null>(null);
function retryRelated() {
  if (relatedLoading.value) return;
  focusRegion(relatedSectionRef.value);
  void fetchRelatedBooks();
}

// ── 연관 도서 (관련 자료 전용 GET) ─────────────────────────
// 백엔드가 이 자료의 제목으로 찾되 자기 자신은 검색 조건에서 미리 빼고, 연관도 하한 아래는 채우지 않는다.
// 사용자 검색(POST /books/search)을 쓰면 긴 학위논문은 자기 청크가 후보를 다 채워 1권만 남았다
async function fetchRelatedBooks() {
  if (!book.value || relatedLoading.value) return;
  relatedLoading.value = true;
  relatedFailure.value = null;
  try {
    const data = await api<any>(`/books/${encodeURIComponent(cnts_id)}/related`, {
      query: { top_k: RELATED_LIMIT },
      signal: pageAbort.signal,
      // 검색과 같은 임베딩·재정렬을 돌리는 GET 이라 읽기 기본 제한(30초) 대신 검색 제한을 쓴다 — 붐빌 때 30초를 넘겨 빈 칸이 되지 않게
      timeout: API_SEARCH_TIMEOUT_MS,
    });
    if (data?.books) {
      relatedItems.value = (data.books as any[])
        .filter((b) => b.book_id !== cnts_id)
        .slice(0, RELATED_LIMIT);
    }
  } catch (e: unknown) {
    // 떠나며 끊은 요청이면 아무것도 띄우지 않는다(failureView 도 null)
    if (!pageAbort.signal.aborted) relatedFailure.value = failureView(e, BOOK_DETAIL_TEXT.relatedFailedTitle);
  } finally {
    relatedLoading.value = false;
  }
}

// ── 유틸 ──────────────────────────────────────────────────
function recoDesc(rel: any): string {
  return rel.book_info?.summary || rel.book_info?.introduction || "";
}
</script>
