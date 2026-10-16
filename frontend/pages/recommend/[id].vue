<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="skx-result">
      <h1 class="skx-sr-only">추천 도서 큐레이션 상세</h1>
      <div class="skx-result-card">
        <!-- 뒤로가기 -->
        <button type="button" class="skx-detail-back" @click="$router.back()">
          <img class="skx-detail-back__icon" src="/img/ico-arrow.svg" alt="" />
          <span class="skx-detail-back__label">돌아가기</span>
        </button>

        <!-- 히어로 배너 -->
        <div :class="['skx-rcd-hero', `skx-rcd-hero--${meta.heroType}`]">
          <template v-if="meta.heroType === '02'">
            <span class="skx-mt-deco skx-mt-deco--1" aria-hidden="true"
              ><i></i
            ></span>
            <span class="skx-mt-deco skx-mt-deco--2" aria-hidden="true"
              ><i></i
            ></span>
            <span class="skx-mt-deco skx-mt-deco--3" aria-hidden="true"
              ><i></i
            ></span>
          </template>
          <template v-if="meta.heroType === '03'">
            <img
              class="skx-reco-c03 skx-reco-c03--star-s"
              src="/img/skx-reco-c03-star.svg"
              alt=""
              aria-hidden="true"
            />
            <img
              class="skx-reco-c03 skx-reco-c03--star-l"
              src="/img/skx-reco-c03-star.svg"
              alt=""
              aria-hidden="true"
            />
            <img
              class="skx-reco-c03 skx-reco-c03--curve"
              src="/img/skx-reco-c03-curve.svg"
              alt=""
              aria-hidden="true"
            />
          </template>
          <div class="skx-rcd-hero__body">
            <h2 class="skx-rcd-hero__tit">{{ meta.title }}</h2>
            <p class="skx-rcd-hero__sub">{{ meta.sub }}</p>
          </div>
        </div>

        <!-- 불러오지 못함 — 소개·도서 칸 대신 상태 블록. 서버 404(이 고민으로 찾은 도서 없음)·빈 목록은 빈 결과,
             그 밖은 이유 + [다시 시도] -->
        <SkxErrorState
          v-if="loadFailure && !loading"
          :kind="loadFailure.kind"
          :title="loadFailure.title"
          :message="loadFailure.message"
          :on-retry="loadFailure.retry ? fetchRecommend : undefined"
        >
          <NuxtLink v-if="loadFailure.kind === 'empty'" to="/recommend" class="skx-state__action">
            {{ SCENARIO_TEXT.pickAnother }}
          </NuxtLink>
        </SkxErrorState>

        <template v-else>
          <!-- AI 텍스트 (타이핑 애니메이션) -->
          <div class="skx-rcd-ai">
            <div class="skx-rcd-ai__top">
              <span class="skx-ai-dot skx-rcd-ai__logo" aria-hidden="true"></span>
              <span class="skx-rcd-ai__label">{{ meta.aiLabel }}</span>
              <span
                v-if="loading"
                style="font-size: 12px; color: var(--skx-accent-strong)"
                >●</span
              >
            </div>
            <div
              :class="['skx-ai-answer-wrap', aiExpanded && 'is-expanded']"
              ref="aiWrapRef"
            >
              <div class="skx-ai-answer">
                <!-- 새 서버의 ai_failed — 소개·추천 사유를 만들지 못했다(빈 값). [다시 시도]는 추천을 처음부터 다시 받는다 -->
                <SkxInlineError
                  v-if="aiFailed && !loading"
                  :message="SCENARIO_TEXT.aiFailed"
                  @retry="fetchRecommend"
                />
                <p v-else class="skx-ai-answer__text">
                  {{ typedText
                  }}<span v-if="loading && typedText" class="skx-stream-cursor" />
                </p>
              </div>
              <button
                v-if="showExpandBtn"
                type="button"
                class="skx-ai-expand-bar"
                :aria-expanded="aiExpanded"
                @click="aiExpanded = !aiExpanded"
              >
                <span class="skx-ai-expand-bar__label">{{
                  aiExpanded ? "접기" : "펼치기"
                }}</span>
                <img
                  class="skx-ai-expand-bar__arrow"
                  src="/img/ico-arrow.svg"
                  alt=""
                  aria-hidden="true"
                  :style="
                    aiExpanded
                      ? 'transform:rotate(90deg)'
                      : 'transform:rotate(-90deg)'
                  "
                />
              </button>
            </div>
          </div>

          <!-- 도서 선택 -->
          <div class="skx-rcd-select">
            <h3 class="skx-rcd-select__tit">
              가장 나에게 도움이되는 책을 선택해주세요.
            </h3>

            <!-- 로딩 -->
            <div v-if="loading" class="skx-rcd-book-grid">
              <div
                v-for="n in 4"
                :key="n"
                :class="['skx-rcd-book-card', `skx-rcd-book-card--${n}`]"
                style="opacity: 0.4; pointer-events: none"
              >
                <div class="skx-rcd-book-card__head">
                  <img
                    class="skx-rcd-book-card__icon"
                    src="/img/ico-book-select.svg"
                    alt=""
                  />
                  <p
                    class="skx-rcd-book-card__desc"
                    style="
                      background: #eee;
                      border-radius: 4px;
                      height: 2.5rem;
                      width: 80%;
                    "
                  ></p>
                </div>
                <div class="skx-rcd-book-card__cover">
                  <img
                    :src="SPINNER_SRC"
                    alt=""
                    style="width: 32px; opacity: 0.3"
                  />
                </div>
                <p
                  class="skx-rcd-book-card__name"
                  style="
                    background: #eee;
                    border-radius: 4px;
                    height: 1rem;
                    width: 60%;
                  "
                ></p>
              </div>
            </div>

            <!-- 도서 그리드 -->
            <div v-else class="skx-rcd-book-grid">
              <button
                v-for="(book, i) in recommendedBooks"
                :key="book.book_id"
                type="button"
                :class="['skx-rcd-book-card', `skx-rcd-book-card--${i + 1}`]"
                @click="openModal(book)"
              >
                <div class="skx-rcd-book-card__head">
                  <img
                    class="skx-rcd-book-card__icon"
                    src="/img/ico-book-select.svg"
                    alt=""
                  />
                  <p class="skx-rcd-book-card__desc">{{ book.reason }}</p>
                </div>
                <div class="skx-rcd-book-card__cover">
                  <BookCover :book-id="book.book_id" />
                </div>
                <p v-if="book.quote" class="skx-rcd-book-card__quote">
                  {{ book.quote }}
                </p>
                <p class="skx-rcd-book-card__name">
                  {{ book.book_info?.title || book.book_id }}
                </p>
              </button>
            </div>
          </div>
        </template>
      </div>
    </main>

    <!-- 맞춤도서 추천 팝업 -->
    <div
      v-if="modalOpen"
      class="skx-rcd-modal-overlay"
      role="dialog"
      aria-modal="true"
      @click.self="modalOpen = false"
    >
      <div class="skx-rcd-modal">
        <h2 class="skx-rcd-modal__title">맞춤도서 추천</h2>
        <div class="skx-rcd-modal__card">
          <div class="skx-rcd-modal__card-top">
            <span class="skx-rcd-modal__badge">Book solution</span>
            <p class="skx-rcd-modal__desc">{{ selectedBook?.reason }}</p>
            <p v-if="selectedBook?.quote" class="skx-rcd-modal__quote">
              {{ selectedBook.quote }}
            </p>
          </div>
          <div class="skx-rcd-modal__cover" v-if="selectedBook">
            <BookCover :book-id="selectedBook.book_id" />
          </div>
          <div class="skx-rcd-modal__book-info" v-if="selectedBook?.book_info">
            <p class="skx-rcd-modal__book-title">
              {{ selectedBook.book_info.title }}
            </p>
            <div class="skx-rcd-modal__meta">
              <span
                v-if="
                  selectedBook.book_info.personal_author ||
                  selectedBook.book_info.corporate_author
                "
                class="skx-rcd-modal__author-wrap"
              >
                <span class="skx-rcd-modal__author">{{
                  selectedBook.book_info.personal_author ||
                  selectedBook.book_info.corporate_author
                }}</span>
                <span class="skx-rcd-modal__author-role">저자(글)</span>
              </span>
              <span
                v-if="selectedBook.book_info.pub_date"
                class="skx-dot"
              ></span>
              <span
                v-if="selectedBook.book_info.pub_date"
                class="skx-rcd-modal__meta-text"
                >{{ selectedBook.book_info.pub_date.slice(0, 4) }}년</span
              >
              <span
                v-if="selectedBook.book_info.publisher"
                class="skx-dot"
              ></span>
              <span
                v-if="selectedBook.book_info.publisher"
                class="skx-rcd-modal__meta-text"
                >{{ selectedBook.book_info.publisher }}</span
              >
            </div>
          </div>
        </div>
        <div class="skx-rcd-modal__btns">
          <button
            type="button"
            class="skx-rcd-modal__btn skx-rcd-modal__btn--outline"
            @click="navigateTo(`/books/${selectedBook?.book_id}`)"
          >
            <img src="/img/ico-arrow.svg" alt="" />상세 보기
          </button>
          <button
            v-if="SHOW_MOCKS"
            type="button"
            class="skx-rcd-modal__btn skx-rcd-modal__btn--dark"
            @click="showToast('준비 중입니다.')"
          >
            <img src="/img/ico-download.svg" alt="" />솔루션 저장하기
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
import { API_SEARCH_TIMEOUT_MS, useApi } from "~/composables/useApi";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { SPINNER_SRC } from "~/utils/brand";
import { SCENARIO_TEXT, failureView, scenarioAiFailed, type StateView } from "~/utils/bookErrors";

const route = useRoute();
const api = useApi();
const scenarioId = route.params.id as string;

const toast = ref("");
function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

// ── 시나리오 메타 ──────────────────────────────────────────
interface ScenarioMeta {
  heroType: string;
  title: string;
  sub: string;
  concern: string;
  aiLabel: string;
}

const SCENARIO_META: Record<string, ScenarioMeta> = {
  "01": {
    heroType: "01",
    title: "위로가 필요할 때",
    sub: "지친 마음에 따뜻한 위로가 필요하다면 이 책들을 펼쳐보세요!",
    concern:
      "마음이 지치고 힘들어서 따뜻한 위로와 공감이 필요합니다. 나를 위로해줄 수 있는 도서를 추천해주세요.",
    aiLabel: "위로가 필요한 당신을 위해 AI가 추천하는 책!",
  },
  "02": {
    heroType: "02",
    title: "심리적 단단함이 필요할 때",
    sub: "마음 근육을 키워 단단해지고 싶다면 이 책들을 읽어보세요!",
    concern:
      "심리적으로 단단해지고 싶습니다. 역경을 이겨내고 내면의 힘을 키울 수 있는 도서를 추천해주세요.",
    aiLabel: "심리적 단단함을 만들 수 있게 AI가 추천하는 책!",
  },
  "03": {
    heroType: "03",
    title: "늦은 밤, 잠이 오지 않을 때",
    sub: "잠 못 드는 밤, 마음을 가라앉혀 줄 책들을 골라봤어요!",
    concern:
      "늦은 밤 잠이 오지 않습니다. 마음을 차분하게 가라앉히고 편안하게 해줄 도서를 추천해주세요.",
    aiLabel: "잠 못 드는 밤을 위해 AI가 추천하는 책!",
  },
  "04": {
    heroType: "04",
    title: "흥미진진한 역사 이야기가 궁금할 때",
    sub: "흥미진진한 역사의 세계로 빠져들 책들을 추천해드려요!",
    concern:
      "흥미진진한 역사 이야기가 궁금합니다. 재미있게 읽을 수 있는 역사 관련 도서를 추천해주세요.",
    aiLabel: "역사가 궁금한 당신을 위해 AI가 추천하는 책!",
  },
};

const meta = computed((): ScenarioMeta => {
  return (SCENARIO_META[scenarioId] ?? SCENARIO_META["01"]) as ScenarioMeta;
});

// ── API 데이터 ─────────────────────────────────────────────
interface RecommendedBook {
  book_id: string;
  book_info?: any;
  reason: string;
  quote: string;
}

const recommendedBooks = ref<RecommendedBook[]>([]);
const loading = ref(false);
// 불러오지 못함(서버 오류·네트워크) 또는 추천할 도서 없음(404·빈 목록) — 토스트로 잠깐 알리고 빈 칸으로 두던 것을 화면 안 상태 블록으로
const loadFailure = ref<StateView | null>(null);
// 새 서버의 ai_failed=true — 도서는 왔지만 소개·추천 사유가 빈 값이다. 옛 서버(필드 없음)는 false 라 예전처럼 기본 문구를 타이핑한다
const aiFailed = ref(false);
// 화면을 떠나면 받던 추천을 끊는다 — 늦은 응답이 떠난 화면의 상태를 고치지 않게
const pageAbort = new AbortController();

// ── AI 타이핑 애니메이션 ───────────────────────────────────
const typedText = ref("");
const aiWrapRef = ref<HTMLElement | null>(null);
const aiExpanded = ref(false);
const showExpandBtn = ref(false);

// 타이핑 차례 — 다시 받기로 새 글을 타이핑하기 시작하면 이전 타이핑은 멈춘다(두 글이 섞이지 않게)
let typingRun = 0;

function typeText(text: string) {
  typedText.value = "";
  const run = ++typingRun;
  let i = 0;
  const tick = () => {
    if (run !== typingRun) return;
    if (i < text.length) {
      typedText.value += text[i++];
      setTimeout(tick, 20);
    } else {
      nextTick(() => {
        if (
          aiWrapRef.value &&
          aiWrapRef.value.scrollHeight > aiWrapRef.value.clientHeight + 10
        ) {
          showExpandBtn.value = true;
        }
      });
    }
  };
  tick();
}

// ── 모달 ──────────────────────────────────────────────────
const modalOpen = ref(false);
const selectedBook = ref<RecommendedBook | null>(null);

function openModal(book: RecommendedBook) {
  selectedBook.value = book;
  modalOpen.value = true;
}

// ── API 호출 ──────────────────────────────────────────────
// 처음 열 때와 [다시 시도](불러오기 실패·ai_failed)가 부른다
async function fetchRecommend() {
  if (loading.value) return;
  loading.value = true;
  loadFailure.value = null;
  aiFailed.value = false;
  showExpandBtn.value = false;
  typingRun += 1;
  typedText.value = "";
  try {
    const data = await api<any>("/scenario/recommend", {
      method: "POST",
      body: { concern: meta.value.concern, top_k: 4 },
      signal: pageAbort.signal,
      // 검색 + LLM 사유 생성이라 오래 걸릴 수 있는 읽기 성격 POST — 검색과 같은 시간 제한
      timeout: API_SEARCH_TIMEOUT_MS,
    });
    if (pageAbort.signal.aborted) return;
    recommendedBooks.value = data?.books || [];
    if (!recommendedBooks.value.length) {
      loadFailure.value = scenarioEmpty();
      return;
    }
    if (scenarioAiFailed(data)) {
      aiFailed.value = true;
      return;
    }
    // AI 요약 영역: LLM이 생성한 고민 공감 + 추천 소개(intro)
    typeText(data?.intro || meta.value.aiLabel);
  } catch (e: unknown) {
    if (pageAbort.signal.aborted) return;
    recommendedBooks.value = [];
    loadFailure.value = failureView(e, SCENARIO_TEXT.failedTitle, scenarioEmpty());
  } finally {
    loading.value = false;
  }
}

// 추천할 도서가 없다 — 서버 404(검색 0건)·빈 목록. 고장이 아니라 빈 결과라 [다시 시도] 대신 [다른 상황 고르기]
function scenarioEmpty(): StateView {
  return { kind: "empty", title: SCENARIO_TEXT.emptyTitle, message: SCENARIO_TEXT.emptyMessage, retry: false };
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") modalOpen.value = false;
}

onMounted(() => {
  window.addEventListener("keydown", onKeydown);
  void fetchRecommend();
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
  pageAbort.abort();
  typingRun += 1;
});
</script>
