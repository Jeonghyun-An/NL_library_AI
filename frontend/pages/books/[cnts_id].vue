<template>
  <div class="skx-app">
    <AppSidebar
      :book-history="bookHistory"
      :paper-history="paperHistory"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
      @restore="restoreSession"
    />

    <main class="skx-result">
      <!-- 로딩 -->
      <div
        v-if="pageLoading"
        class="skx-result-card"
        style="padding: 40px; text-align: center"
      >
        <img src="/img/ico-spinner.svg" alt="" style="width: 32px" />
        <p style="margin-top: 12px">도서 정보를 불러오는 중...</p>
      </div>
      <div v-else-if="pageError" class="skx-result-card" style="padding: 20px">
        <p style="color: #c00">{{ pageError }}</p>
        <button
          class="skx-btn-loan"
          style="margin-top: 12px"
          @click="navigateTo('/')"
        >
          홈으로
        </button>
      </div>

      <template v-else-if="book">
        <div class="skx-result-card">
          <!-- 뒤로가기 -->
          <button type="button" class="skx-detail-back" @click="$router.back()">
            <img
              class="skx-detail-back__icon"
              src="/img/ico-arrow.svg"
              alt=""
            />
            <span class="skx-detail-back__label">검색 목록 돌아가기</span>
          </button>

          <!-- 도서 헤더 카드 -->
          <article class="skx-book-card skx-book-card--hd">
            <div class="skx-book-card__thumb">
              <BookCover :book-id="cnts_id" />
              <p class="skx-cover-ai-note">
                <img src="/img/logo-mark.svg" alt="" />
                AI가 도서 내용을 분석해 그려낸 표지입니다
              </p>
            </div>
            <div class="skx-book-card__body">
              <div class="skx-book-card__top">
                <div class="skx-book-card__tags">
                  <template
                    v-if="
                      titleScore !== undefined && contentScore !== undefined
                    "
                  >
                    <ScoreRing :pct="titleScore" label="제목 일치율" />
                    <ScoreRing
                      :pct="contentScore"
                      label="내용 일치율"
                      variant="content"
                    />
                  </template>
                  <span v-if="matchScore" class="skx-tag skx-tag--score"
                    >관련도 {{ matchScore }}%</span
                  >
                  <span
                    v-for="tag in themes"
                    :key="tag"
                    class="skx-tag skx-tag--keyword"
                    >#{{ tag }}</span
                  >
                </div>
                <button
                  type="button"
                  class="skx-book-card__bookmark"
                  :aria-label="isBookmarked(cnts_id) ? '북마크 해제' : '북마크'"
                  @click="toggleBookmark(cnts_id)"
                >
                  <img :src="bookmarkIcon(cnts_id)" alt="" />
                </button>
              </div>
              <div class="skx-book-card__meta">
                <div class="skx-book-card__title-row">
                  <h2 class="skx-book-card__title">{{ book.title }}</h2>
                </div>
                <div class="skx-book-card__info-row">
                  <span v-if="book.material_type" class="skx-meta-text">{{
                    book.material_type
                  }}</span>
                  <template
                    v-if="book.personal_author || book.corporate_author"
                  >
                    <span class="skx-dot"></span>
                    <span class="skx-meta-text">{{
                      book.personal_author || book.corporate_author
                    }}</span>
                  </template>
                  <template v-if="book.pub_date">
                    <span class="skx-dot"></span>
                    <span class="skx-meta-text"
                      >{{ book.pub_date.slice(0, 4) }}년</span
                    >
                  </template>
                  <template v-if="book.publisher">
                    <span class="skx-dot"></span>
                    <span class="skx-meta-text">{{ book.publisher }}</span>
                  </template>
                </div>
              </div>
              <div class="skx-book-card__actions">
                <button
                  type="button"
                  :class="[
                    'skx-btn-talk skx-btn-talk--book',
                    chatPanelOpen && 'is-active',
                  ]"
                  @click="chatPanelOpen = !chatPanelOpen"
                >
                  <span class="skx-btn-talk__glow" aria-hidden="true"></span>
                  <span class="skx-btn-talk__panel" aria-hidden="true"></span>
                  <img
                    class="skx-btn-talk__ico"
                    src="/img/ico-chat.svg"
                    alt=""
                  />
                  <span class="skx-btn-talk__label">DeepRead</span>
                </button>
                <!-- <button
                  type="button"
                  :class="['skx-btn-loan', isLoaning && 'is-loaning']"
                  @click="
                    isLoaning
                      ? (loanCancelModalOpen = true)
                      : (loanModalOpen = true)
                  "
                >
                  {{ isLoaning ? "대출신청중" : "대출신청" }}
                </button> -->
                <button type="button" class="skx-btn-read" @click="viewPdf">
                  원문 보기
                </button>
              </div>
            </div>
          </article>

          <!-- AI 큐레이션 (수직탭) -->
          <section class="skx-curation" aria-label="AI 큐레이션">
            <h2 class="skx-section-title">AI 큐레이션</h2>
            <div class="skx-curation-panel">
              <div class="skx-vtabs-col">
                <div class="skx-vtabs" role="tablist" ref="vtabsRef">
                  <span
                    class="skx-vtabs__slider"
                    :style="vtabSliderStyle"
                    aria-hidden="true"
                  ></span>
                  <button
                    v-for="tab in detailTabs"
                    :key="tab.key"
                    type="button"
                    :class="['skx-vtab', detailTab === tab.key && 'is-active']"
                    role="tab"
                    :aria-selected="detailTab === tab.key"
                    @click="switchVtab(tab.key)"
                  >
                    {{ tab.label }}
                  </button>
                </div>
              </div>
              <div class="skx-curation-content">
                <div class="skx-curation-card">
                  <div v-if="detailTab === 'reason'">
                    <!-- 스트리밍 중: raw 텍스트 + 깜빡이는 커서 -->
                    <p
                      v-if="reasonLoading && reasonText"
                      class="skx-curation-text skx-curation-text--stream"
                    >
                      {{ reasonText }}<span class="skx-stream-cursor" />
                    </p>
                    <p
                      v-else-if="reasonLoading"
                      class="skx-curation-text skx-curation-loading"
                    >
                      추천 이유를 생성하고 있습니다<span
                        class="skx-stream-cursor"
                      />
                    </p>
                    <!-- 완료 후: 마크다운 렌더링 -->
                    <div
                      v-else-if="reasonText"
                      class="skx-curation-text"
                      v-html="renderedReason"
                    />
                    <p v-else class="skx-curation-text">
                      추천 이유 정보가 없습니다.
                    </p>
                  </div>
                  <p v-else-if="detailTab === 'plot'" class="skx-curation-text">
                    {{ book.plot || book.summary || "줄거리 정보가 없습니다." }}
                  </p>
                  <p
                    v-else-if="detailTab === 'intro'"
                    class="skx-curation-text"
                  >
                    {{ book.introduction || "소개 정보가 없습니다." }}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <!-- 상세 정보 -->
          <section class="skx-detail-info" aria-label="상세 정보">
            <h2 class="skx-section-title">상세 정보</h2>
            <div class="skx-detail-info__grid">
              <div class="skx-info-row">
                <span class="skx-info-label">표제/저자사항</span
                ><span class="skx-info-value">{{
                  book.title_responsibility || book.title || "-"
                }}</span>
              </div>
              <div class="skx-info-row">
                <span class="skx-info-label">발행사항</span
                ><span class="skx-info-value">{{
                  [book.pub_place, book.publisher, book.pub_date]
                    .filter(Boolean)
                    .join(", ") || "-"
                }}</span>
              </div>
              <div class="skx-info-row">
                <span class="skx-info-label">형태사항</span
                ><span class="skx-info-value">{{ book.extent || "-" }}</span>
              </div>
              <div class="skx-info-row">
                <span class="skx-info-label">총서사항</span
                ><span class="skx-info-value">{{
                  book.series_title || "-"
                }}</span>
              </div>
              <div class="skx-info-row">
                <span class="skx-info-label">표준번호</span
                ><span class="skx-info-value">{{
                  book.isbn || book.uci || "-"
                }}</span>
              </div>
              <div class="skx-info-row">
                <span class="skx-info-label">분류기호</span
                ><span class="skx-info-value">{{
                  [book.kdc, book.ddc].filter(Boolean).join(" → ") || "-"
                }}</span>
              </div>
              <div class="skx-info-row">
                <span class="skx-info-label">주제명</span
                ><span class="skx-info-value">{{
                  book.subject || book.keyword || "-"
                }}</span>
              </div>
              <div class="skx-info-row">
                <span class="skx-info-label">언어</span
                ><span class="skx-info-value">{{
                  book.language || "Korean"
                }}</span>
              </div>
            </div>
          </section>

          <!-- AI 연관 도서 추천 -->
          <section class="skx-reco" aria-label="AI 연관 도서 추천">
            <h2 class="skx-section-title">AI 연관 도서 추천</h2>
            <div class="skx-reco-panel">
              <div class="skx-reco-list" role="list">
                <div
                  v-if="relatedLoading"
                  style="padding: 16px; color: #bbb; font-size: 12px"
                >
                  불러오는 중...
                </div>
                <div
                  v-else-if="!relatedItems.length"
                  style="padding: 16px; color: #bbb; font-size: 12px"
                >
                  연관 추천 항목이 없습니다.
                </div>
                <button
                  v-for="rel in relatedItems"
                  :key="rel.book_id"
                  type="button"
                  :class="[
                    'skx-reco-item',
                    selectedRelated?.book_id === rel.book_id && 'is-active',
                  ]"
                  @click="selectedRelated = rel"
                >
                  <img
                    class="skx-reco-item__thumb"
                    src="/img/ico-book-thumb.svg"
                    alt=""
                  />
                  <div class="skx-reco-item__inner">
                    <span class="skx-reco-item__name">{{
                      rel.book_info?.title || rel.book_id
                    }}</span>
                    <span class="skx-reco-item__score"
                      >관련도
                      {{
                        Math.round((rel.score || rel.best_score || 0) * 100)
                      }}%</span
                    >
                  </div>
                </button>
              </div>
              <div v-if="!selectedRelated" class="skx-reco-empty">
                <img
                  class="skx-reco-empty__logo"
                  src="/img/logo-mark.svg"
                  alt="SKOVIX"
                />
                <p class="skx-reco-empty__text">추천도서를 클릭해주세요</p>
              </div>
              <div
                v-else
                :key="selectedRelated.book_id"
                class="skx-reco-detail"
                style="cursor: pointer"
                @click="
                  navigateTo(
                    `/books/${selectedRelated.book_id}?q=${encodeURIComponent(searchQuery)}`,
                  )
                "
              >
                <!-- 표지 -->
                <div class="skx-reco-cover skx-anim skx-anim--1">
                  <img
                    :src="`/api/books/${selectedRelated.book_id}/thumbnail`"
                    :alt="selectedRelated.book_info?.title || ''"
                    @error="
                      (e: Event) =>
                        ((e.target as HTMLImageElement).src =
                          '/img/ico-book-thumb.svg')
                    "
                  />
                </div>
                <!-- 정보 -->
                <div class="skx-reco-info">
                  <!-- 키워드 태그 -->
                  <div class="skx-reco-info__top skx-anim skx-anim--2">
                    <div class="skx-reco-info__tags">
                      <span
                        v-for="tag in recoTags(selectedRelated)"
                        :key="tag"
                        class="skx-tag skx-tag--keyword"
                        >#{{ tag }}</span
                      >
                    </div>
                  </div>
                  <!-- 메타 -->
                  <div class="skx-reco-meta skx-anim skx-anim--3">
                    <div class="skx-reco-type-row">
                      <span
                        v-if="selectedRelated.book_info?.material_type"
                        class="skx-reco-type"
                      >
                        {{ selectedRelated.book_info.material_type }}
                      </span>
                    </div>
                    <h3 class="skx-reco-title">
                      {{ selectedRelated.book_info?.title }}
                    </h3>
                    <div class="skx-reco-author">
                      <template
                        v-if="
                          selectedRelated.book_info?.personal_author ||
                          selectedRelated.book_info?.corporate_author
                        "
                      >
                        <span class="skx-meta-text">{{
                          selectedRelated.book_info.personal_author ||
                          selectedRelated.book_info.corporate_author
                        }}</span>
                      </template>
                      <template v-if="selectedRelated.book_info?.pub_date">
                        <span class="skx-dot"></span>
                        <span class="skx-meta-text"
                          >{{
                            selectedRelated.book_info.pub_date.slice(0, 4)
                          }}년</span
                        >
                      </template>
                      <template v-if="selectedRelated.book_info?.publisher">
                        <span class="skx-dot"></span>
                        <span class="skx-meta-text">{{
                          selectedRelated.book_info.publisher
                        }}</span>
                      </template>
                    </div>
                  </div>
                  <!-- 설명 -->
                  <div
                    v-if="recoDesc(selectedRelated)"
                    class="skx-reco-desc skx-anim skx-anim--4"
                  >
                    <p class="skx-reco-desc__text">
                      {{ recoDesc(selectedRelated) }}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </template>
    </main>

    <!-- 채팅 사이드 패널 -->
    <aside :class="['skx-chat-panel', chatPanelOpen && 'is-open']">
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
import { useSearchHistory } from "~/composables/useSearchHistory";
import type { BookInfo } from "~/types/search";
import type { HistoryEntry } from "~/types/history";

// ── 라우트 ─────────────────────────────────────────────────
const route = useRoute();
const cnts_id = route.params.cnts_id as string;
const searchQuery = (route.query.q as string) || "";

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

const { bookHistory, paperHistory } = useSearchHistory();

function restoreSession(entry: HistoryEntry) {
  if (entry.type === "book") {
    navigateTo(`/?restore=${entry.id}`);
  } else {
    navigateTo(`/papers?restore=${entry.id}`);
  }
}

// ── 도서 데이터 ────────────────────────────────────────────
const book = ref<BookInfo | null>(null);
const pageLoading = ref(true);
const pageError = ref("");

// 점수 표시는 내림 처리: 99.6%가 100%로 올림 표기되는 것 방지
const matchScore = computed(() => {
  const s = route.query.score;
  return s ? Math.floor(Number(s) * 100) : null;
});

const titleScore = computed(() => {
  const s = route.query.title_score;
  return s !== undefined && s !== "" ? Math.floor(Number(s) * 100) : undefined;
});

const contentScore = computed(() => {
  const s = route.query.content_score;
  return s !== undefined && s !== "" ? Math.floor(Number(s) * 100) : undefined;
});

const themes = computed(() =>
  parseThemes(book.value?.themes || book.value?.keyword || book.value?.subject),
);

// ── AI 큐레이션 ────────────────────────────────────────────
const reasonText = ref("");
const reasonLoading = ref(false);
const renderedReason = computed(() =>
  reasonText.value ? (marked.parse(reasonText.value) as string) : "",
);

// ── 연관 도서 ──────────────────────────────────────────────
const relatedItems = ref<any[]>([]);
const relatedLoading = ref(false);
const selectedRelated = ref<any>(null);

// ── UI 상태 ────────────────────────────────────────────────
const toast = ref("");

// ── Publishing additions ──────────────────────────────────────
// Vertical tabs
const vtabsRef = ref<HTMLElement | null>(null);
const vtabSliderStyle = ref<{ height: string; transform: string }>({
  height: "0px",
  transform: "translateY(0px)",
});
const detailTab = ref("reason");
const detailTabs = [
  { key: "reason", label: "추천 이유" },
  { key: "plot", label: "줄거리" },
  { key: "intro", label: "소개" },
];

function updateVtabSlider() {
  if (!vtabsRef.value) return;
  const active = vtabsRef.value.querySelector(
    ".skx-vtab.is-active",
  ) as HTMLElement | null;
  if (!active) return;
  vtabSliderStyle.value = {
    height: active.offsetHeight + "px",
    transform: `translateY(${active.offsetTop}px)`,
  };
}

function switchVtab(key: string) {
  detailTab.value = key;
  nextTick(() => updateVtabSlider());
}

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

// PDF viewer
function viewPdf() {
  showToast("원문 보기 기능은 준비 중입니다.");
}
// ── End publishing additions ──────────────────────────────────

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
  nextTick(() => updateVtabSlider());
});

// ── 도서 fetch ─────────────────────────────────────────────
async function fetchBook() {
  pageLoading.value = true;
  pageError.value = "";
  try {
    const data = await $fetch<BookInfo>(`${apiBase}/books/${cnts_id}`);
    book.value = data;
  } catch (e: any) {
    pageError.value = e?.data?.detail || "도서 정보를 불러올 수 없습니다.";
  } finally {
    pageLoading.value = false;
  }
}

// ── 추천 이유 SSE ──────────────────────────────────────────
async function streamReason() {
  if (!searchQuery) return;
  reasonLoading.value = true;
  reasonText.value = "";
  try {
    const resp = await fetch(`${apiBase}/books/reason/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: searchQuery,
        book_id: cnts_id,
        chunk_texts: [],
        rewritten_query: "",
      }),
    });
    await readSSE(resp, (json) => {
      if (json.text) reasonText.value += json.text;
    });
  } catch {
    /* ignore */
  } finally {
    reasonLoading.value = false;
  }
}

// ── 연관 도서 (제목 기반 검색) ─────────────────────────────
async function fetchRelatedBooks() {
  if (!book.value) return;
  relatedLoading.value = true;
  const query = book.value.title || "";
  try {
    const data = await $fetch<any>(`${apiBase}/books/search`, {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 6,
        use_rewrite: false,
        use_rerank: true,
      },
    });
    if (data?.books) {
      relatedItems.value = (data.books as any[])
        .filter((b) => b.book_id !== cnts_id)
        .slice(0, 5);
    }
  } catch {
    /* ignore */
  } finally {
    relatedLoading.value = false;
  }
}

// ── 유틸 ──────────────────────────────────────────────────
function parseThemes(themes?: string | null): string[] {
  if (!themes) return [];
  return themes
    .split(/[,;]/)
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 4);
}

function recoTags(rel: any): string[] {
  const raw =
    rel.book_info?.themes ||
    rel.book_info?.keyword ||
    rel.book_info?.subject ||
    "";
  return parseThemes(raw).slice(0, 3);
}

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
