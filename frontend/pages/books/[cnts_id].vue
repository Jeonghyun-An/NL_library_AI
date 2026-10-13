<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
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

      <div class="dt-frame">
        <!-- 뒤로가기 -->
        <button type="button" class="dt-back" @click="$router.back()">
          <img src="/img/ico-arrow.svg" alt="" />
          <span>검색 목록 돌아가기</span>
        </button>

        <!-- 로딩 -->
        <div v-if="pageLoading" class="dt-loading">
          <img src="/img/ico-spinner.svg" alt="" />
          <p>도서 정보를 불러오는 중...</p>
        </div>
        <div v-else-if="pageError" class="dt-error">
          <p>{{ pageError }}</p>
          <button type="button" class="dt-btn dt-btn--ghost" @click="navigateTo('/')">홈으로</button>
        </div>

        <template v-else-if="book">
          <!-- 머리(서지) — 표지 · 칩 줄(관련도 · #키워드, 키워드가 없으면 분류 칩) · 제목 · 서지 표 · 오른쪽 버튼 열 -->
          <section class="dt-hero" aria-label="서지 정보">
            <div class="dt-hero__cover">
              <div class="dt-cover">
                <BookCover :book-id="cnts_id" />
              </div>
              <p class="dt-cover-note">
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
                <button type="button" class="dt-btn dt-btn--ghost" @click="viewPdf(cnts_id, book.title)">
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
                  <p v-else class="dt-muted">추천 이유 정보가 없습니다.</p>
                </template>
                <p v-else-if="active === 'plot'" class="dt-prose">{{ plotText }}</p>
                <p v-else-if="active === 'intro'" class="dt-prose">{{ book.introduction }}</p>
              </template>
            </DetailTabs>
            <p v-else class="dt-empty">AI 큐레이션 정보가 없습니다.</p>
          </section>

          <!-- 관련 자료 추천 — 제목으로 찾은 소장자료 4권. 카드를 누르면 그 자료 상세로, [자세히 보기]는 요약 전문과 버튼 -->
          <section class="dt-section" aria-labelledby="bdetail-related-title">
            <h2 id="bdetail-related-title" class="dt-section__title">관련 자료 추천</h2>
            <p v-if="relatedLoading" class="dt-empty">불러오는 중...</p>
            <p v-else-if="!relatedItems.length" class="dt-empty">연관 추천 항목이 없습니다.</p>
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
                empty-text="요약 정보가 없습니다."
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
                    @click="viewPdf(rel.book_id, rel.book_info?.title ?? '')"
                  >
                    원문 보기
                  </button>
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

    <!-- 채팅 사이드 패널 -->
    <aside id="dt-chat" :class="['skx-chat-panel', chatPanelOpen && 'is-open']">
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
            DeepRead<template v-if="book?.title">: {{ book.title }}</template>
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
      v-if="pdfTarget"
      :cnts-id="pdfTarget.id"
      :title="pdfTarget.title"
      @close="pdfTarget = null"
    />

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import type { BookInfo } from "~/types/search";
import { firstValue, shouldGoBack } from "~/utils/detailSource";
import {
  activeTabKey,
  bookDetailRows,
  bookMetaRows,
  detailSearchUrl,
  formatAuthors,
  queryScore,
  relatedMetaLine,
  visibleTabs,
  withChat,
} from "~/utils/detailView";
import { kdcChip } from "~/utils/kdc";
import { cardKeywords } from "~/utils/resultCard";
import { relatedOpenAfter } from "~/utils/relatedCard";

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
const pageError = ref("");

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
const renderedReason = computed(() =>
  reasonText.value ? (marked.parse(reasonText.value) as string) : "",
);
const plotText = computed(() => book.value?.plot || book.value?.summary || "");

// 글이 없는 탭은 뺀다 — 추천 이유는 검색어가 있을 때만 만든다. 고른 탭이 빠지면 첫 탭
const detailTab = ref<string | null>("reason");
const curationTabs = computed(() =>
  visibleTabs([
    { key: "reason", label: "추천 이유", available: !!searchQuery && (!reasonDone.value || !!reasonText.value) },
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
// [자세히 보기]로 연 카드 — 한 번에 하나
const openRelated = ref<string | null>(null);

function relatedBookUrl(id: string): string {
  return `/books/${id}?q=${encodeURIComponent(searchQuery)}`;
}

// ── UI 상태 ────────────────────────────────────────────────
const toast = ref("");

// Chat panel
const chatPanelOpen = ref(false);

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

// PDF viewer — 이 자료·관련 자료
const pdfTarget = ref<{ id: string; title: string } | null>(null);
function viewPdf(id: string, title: string) {
  pdfTarget.value = { id, title };
}

// ── 초기화 ─────────────────────────────────────────────────
onMounted(async () => {
  // ?chat=1 → 채팅 패널 자동 오픈
  if (route.query.chat === "1") {
    chatPanelOpen.value = true;
  }
  await fetchBook();
  if (book.value) {
    streamReason();
    fetchRelatedBooks();
  }
});

// ── 도서 fetch ─────────────────────────────────────────────
async function fetchBook() {
  pageLoading.value = true;
  pageError.value = "";
  try {
    const data = await api<BookInfo>(`/books/${cnts_id}`, { signal: pageAbort.signal });
    book.value = data;
  } catch (e: any) {
    pageError.value = e?.data?.detail || "도서 정보를 불러올 수 없습니다.";
  } finally {
    pageLoading.value = false;
  }
}

// ── 추천 이유 SSE ──────────────────────────────────────────
async function streamReason() {
  if (!searchQuery) {
    reasonDone.value = true;
    return;
  }
  reasonLoading.value = true;
  reasonText.value = "";
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
    await readSSE(resp, (json) => {
      if (json.text) reasonText.value += json.text;
    });
  } catch {
    /* ignore */
  } finally {
    reasonLoading.value = false;
    reasonDone.value = true;
  }
}

// ── 연관 도서 (제목 기반 검색) ─────────────────────────────
async function fetchRelatedBooks() {
  if (!book.value) return;
  relatedLoading.value = true;
  const query = book.value.title || "";
  try {
    const data = await api<any>("/books/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 6,
        use_rewrite: false,
        use_rerank: true,
      },
      signal: pageAbort.signal,
    });
    if (data?.books) {
      relatedItems.value = (data.books as any[])
        .filter((b) => b.book_id !== cnts_id)
        .slice(0, RELATED_LIMIT);
    }
  } catch {
    /* ignore */
  } finally {
    relatedLoading.value = false;
  }
}

// ── 유틸 ──────────────────────────────────────────────────
function recoDesc(rel: any): string {
  return rel.book_info?.summary || rel.book_info?.introduction || "";
}

async function readSSE(resp: Response, onEvent: (json: any) => void) {
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop()!;
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (raw === "[DONE]") return;
      try {
        onEvent(JSON.parse(raw));
      } catch {
        /* skip */
      }
    }
  }
}
</script>
