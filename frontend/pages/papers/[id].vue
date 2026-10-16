<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <!-- 상세 틀(Figma 2536:16714) — 위 알약 검색바 → 큰 틀(돌아가기 · 머리 · AI 큐레이션 · 관련 자료 추천 · 참고문헌). 모양은 assets/css/detail.css -->
    <main class="skx-result dt-page">
      <DetailSearchBar
        :initial="searchInitial"
        label="논문 검색어"
        placeholder="탐구하고 싶은 논문을 자연어로 검색해보세요"
        @submit="onSearch"
      />

      <div class="dt-frame">
        <!-- 돌아가기 — 직전 화면이 출처면 브라우저 뒤로(그 화면 상태 그대로), 새 탭·연관 논문을 거쳐 왔으면 출처 주소로 간다 -->
        <a :href="back.to" class="dt-back" @click="onBack">
          <img src="/img/ico-arrow.svg" alt="" />
          <span>{{ back.label }}</span>
        </a>

        <!-- 인용 맥락 — 보고서의 인용칩에서 왔을 때 이 논문이 그 보고서에서 어떻게 쓰였는지 보인다.
             논문을 읽지 못했으면 그리지 않는다 — 빈 화면에 배너만 남아 제목 없는 원문 뷰어를 연다 -->
        <section v-if="cite && paper" class="dt-cite" aria-label="인용 맥락">
          <div class="dt-cite__row">
            <p class="dt-cite__text">
              {{ DEEP_RESEARCH }} 보고서 ‘{{ cite.question }}’에서
              <strong>{{ withRo(cite.label) }}</strong> 인용됨
              <span aria-hidden="true">·</span> 인용 대목 {{ cite.chunks.length }}곳
            </p>
            <!-- 첫 인용 쪽에서 원문 뷰어를 열고 인용 대목을 넘겨 본다 -->
            <button
              type="button"
              class="dt-cite__btn"
              :aria-busy="pdfCheckingAt === 'banner' ? 'true' : undefined"
              :aria-describedby="bannerPdfProblem ? 'pdetail-cite-problem' : undefined"
              @click="openCitedPassages(cite.chunks)"
            >
              인용 대목 보기
            </button>
          </div>
          <SkxInlineError v-if="bannerPdfProblem" id="pdetail-cite-problem" class="dt-cite__note" :message="bannerPdfProblem">
            <a v-if="paper?.url" class="dt-pdf-link" :href="paper.url" target="_blank" rel="noopener"
              >{{ PAPER_STATE_TEXT.kciOriginal }}<span class="skx-sr-only"> (새 창)</span></a
            >
          </SkxInlineError>
        </section>

        <!-- 처음 읽는 중 — [다시 시도]로 다시 읽는 동안은 아래 상태 블록이 재시도 중(busy)으로 남는다(누른 버튼이 초점을 잃지 않게) -->
        <div v-if="loading && !paperError" class="dt-loading">
          <img :src="SPINNER_SRC" alt="" />
        </div>

        <template v-else-if="paper">
          <!-- 머리(서지) — 표지 · 칩 줄(관련도 · #키워드) · 제목 · 서지 표 · 오른쪽 버튼 열 -->
          <section class="dt-hero" aria-label="서지 정보">
            <div class="dt-hero__cover">
              <div class="dt-cover">
                <img :src="thumbnailUrl" alt="논문 표지" @error="thumbnailUrl = '/img/img-paper-thumb.png'" />
              </div>
            </div>
            <div class="dt-hero__head">
              <div v-if="matchScore !== null || keywords.length" class="dt-chips">
                <RelevanceBadge
                  v-if="matchScore !== null"
                  :score="matchScore"
                  :title-score="titleScore"
                  :content-score="contentScore"
                />
                <!-- 키워드를 누르면 그 키워드로 새 논문 검색을 연다 -->
                <NuxtLink
                  v-for="kw in keywords"
                  :key="kw"
                  :to="{ path: '/papers', query: { q: kw } }"
                  class="skx-tag skx-tag--keyword dt-kw-link"
                  :aria-label="`${kw} — 이 키워드로 논문 검색`"
                  >#{{ kw }}</NuxtLink
                >
              </div>
              <h1 class="dt-title">{{ paper.title }}</h1>
              <p v-if="paper.title_remainder" class="dt-subtitle">{{ paper.title_remainder }}</p>
            </div>
            <div class="dt-hero__meta">
              <DetailMeta :rows="metaRows" />
            </div>
            <div class="dt-hero__actions">
              <div class="dt-hero__row">
                <!-- 원문 보기는 늘 이 화면의 원문 뷰어로 연다 — 외부(KCI) 페이지는 아래 보조 링크로 따로 둔다 -->
                <button
                  type="button"
                  class="dt-btn dt-btn--ghost"
                  :aria-busy="pdfCheckingAt === 'original' ? 'true' : undefined"
                  :aria-describedby="pdfProblem ? 'pdetail-pdf-problem' : undefined"
                  @click="openOriginal"
                >
                  원문 보기
                </button>
                <button
                  type="button"
                  class="dt-btn dt-btn--icon"
                  aria-label="출처 인용"
                  @click="openCitation(paperId, paper.references)"
                >
                  <img src="/img/ico-paper-bookmark.svg" alt="" />
                </button>
                <button
                  v-if="SHOW_MOCKS"
                  type="button"
                  class="dt-btn dt-btn--icon"
                  :aria-label="isBookmarked(paperId) ? '북마크 해제' : '북마크'"
                  @click="toggleBookmark(paperId)"
                >
                  <img :src="bookmarkIcon(paperId)" alt="" />
                </button>
              </div>
              <button
                type="button"
                class="dt-btn dt-btn--accent"
                :aria-expanded="chatOpen"
                aria-controls="dt-chat"
                @click="chatOpen = !chatOpen"
              >
                <DetailSparkIcon />DeepRead
              </button>
              <a v-if="paper.url" :href="paper.url" target="_blank" rel="noopener" class="dt-ext"
                >KCI에서 보기<span class="skx-sr-only"> (새 창)</span></a
              >
            </div>
            <!-- 원문이 없으면 뷰어 대신 머리 아래에 알리고 KCI 페이지를 건넨다 -->
            <SkxInlineError v-if="pdfProblem" id="pdetail-pdf-problem" class="dt-hero__note" :message="pdfProblem">
              <a v-if="paper.url" class="dt-pdf-link" :href="paper.url" target="_blank" rel="noopener"
                >{{ PAPER_STATE_TEXT.kciOriginal }}<span class="skx-sr-only"> (새 창)</span></a
              >
            </SkxInlineError>
          </section>

          <!-- AI 큐레이션 — 가로 밑줄 탭 [AI 요약][초록](글이 없는 탭은 뺀다) + 이 논문으로 DeepResearch -->
          <section class="dt-section" aria-labelledby="pdetail-curation-title">
            <h2 id="pdetail-curation-title" class="dt-section__title">AI 큐레이션</h2>
            <DetailTabs
              v-if="curationTabs.length"
              :tabs="curationTabs"
              :model-value="activeCuration"
              label="AI 큐레이션"
              @update:model-value="curationTab = $event"
            >
              <template #default="{ active }">
                <template v-if="active === 'ai-summary'">
                  <!-- 받는 중에는 글 그대로 + 깜빡이는 커서, 다 받으면 마크다운으로 -->
                  <p v-if="summaryLoading && !summaryText" class="dt-muted">
                    AI가 핵심을 분석 중입니다<span class="skx-stream-cursor" />
                  </p>
                  <p v-else-if="summaryLoading" class="dt-prose dt-stream">
                    {{ summaryText }}<span class="skx-stream-cursor" />
                  </p>
                  <div v-else-if="summaryText" class="dt-prose" v-html="renderedSummary" />
                  <!-- 글 없이 끝난 요약(옛 서버의 빈 답) — 실패가 아닌 빈 상태 -->
                  <SkxErrorState v-else-if="!summaryError" kind="empty" compact :title="PAPER_STATE_TEXT.summaryEmpty" />
                  <!-- 요약을 만들지 못했다(서버의 {error}·끊김) — 받은 글이 있으면 그 아래에, 글에 잇지 않고 따로.
                       문구는 화면의 해요체 상수(AI_SUMMARY_FAILED — 서버 문구는 쓰지 않는다) -->
                  <SkxInlineError
                    v-if="summaryError && !summaryLoading"
                    ref="summaryFailedRef"
                    :message="summaryError"
                    @retry="retrySummary"
                  />
                </template>
                <p v-else-if="active === 'abstract'" class="dt-prose">{{ abstractText }}</p>
              </template>
            </DetailTabs>
            <SkxErrorState v-else kind="empty" compact :title="PAPER_STATE_TEXT.curationEmpty" />

            <!-- 이 논문으로 DeepResearch: 바로 시작하지 않고 초안을 논문 검색 입력창에 채워 고쳐 보내게 한다 -->
            <section v-if="researchQuestion" class="dt-research" aria-labelledby="pdetail-research-title">
              <span class="dt-research__icon" aria-hidden="true"><DetailSparkIcon /></span>
              <div class="dt-research__text">
                <h3 id="pdetail-research-title" class="dt-research__title">이 논문으로 {{ DEEP_RESEARCH }} 시작하기</h3>
                <p class="dt-research__desc">
                  논문 입력창에 {{ DEEP_RESEARCH }} 모드가 켜지고, 이 논문의 주제로 질문 초안이 채워집니다
                </p>
              </div>
              <NuxtLink :to="paperResearchUrl(researchQuestion)" class="dt-btn dt-btn--accent">
                <span class="skx-sr-only">{{ DEEP_RESEARCH }} </span>질문 초안 만들기
              </NuxtLink>
            </section>
          </section>

          <!-- 관련 자료 추천 — 연관 논문 4편. 카드를 누르면 그 논문 상세로(처음 출처를 잇는다), [자세히 보기]는 사유 전문과 버튼 -->
          <section class="dt-section" aria-labelledby="pdetail-related-title">
            <h2 id="pdetail-related-title" class="dt-section__title">관련 자료 추천</h2>
            <!-- 읽기 실패와 0건을 가른다 — 실패를 '없음'으로 보이지 않는다. [다시 시도]로 다시 읽는 동안은 상태 블록이 재시도 중(busy)으로 남는다 -->
            <p v-if="relatedLoading && !relatedError" class="dt-empty">불러오는 중...</p>
            <SkxErrorState
              v-else-if="relatedError"
              compact
              :kind="relatedError.kind"
              :title="PAPER_STATE_TEXT.relatedFailed"
              :message="relatedError.message"
              :busy="relatedLoading"
              :on-retry="isRetryableKind(relatedError.kind) ? retryRelated : undefined"
            />
            <SkxErrorState v-else-if="!relatedItems.length" kind="empty" compact :title="PAPER_STATE_TEXT.relatedEmpty" />
            <div v-else class="dt-related__grid">
              <DetailRelatedCard
                v-for="rel in relatedItems"
                :key="rel.book_id"
                :to="relatedDetailUrl(rel.book_id, source, spot)"
                :title="rel.book_info?.title || rel.book_id"
                :author="formatAuthors(rel.book_info?.personal_author, rel.book_info?.corporate_author)"
                :meta="relatedMetaLine(rel.book_info, 'paper')"
                :keywords="cardKeywords(rel.book_info)"
                reason-label="AI 추천 사유"
                pop-title="AI 추천 사유 & 유사점 분석"
                :reason="relatedReasons[rel.book_id]"
                :reason-loading="relatedReasonLoading.has(rel.book_id)"
                :reason-error="relatedReasonErrors[rel.book_id]"
                :empty-text="PAPER_STATE_TEXT.relatedReasonEmpty"
                :expanded="openRelated === rel.book_id"
                @update:expanded="(open: boolean) => (openRelated = relatedOpenAfter(openRelated, rel.book_id, open))"
                @retry-reason="retryRelatedReason(rel.book_id)"
              >
                <template #cover>
                  <img
                    :src="`${config.public.apiBase}/books/${rel.book_id}/thumbnail`"
                    alt=""
                    loading="lazy"
                    @error="onRelatedThumbError"
                  />
                </template>
                <template #badge>
                  <RelevanceBadge :score="relativeScore(rel.score, relatedScores)" />
                </template>
                <template #actions>
                  <NuxtLink :to="withChat(relatedDetailUrl(rel.book_id, source, spot))" class="dt-btn dt-btn--accent">
                    <DetailSparkIcon />DeepRead<span class="skx-sr-only">: {{ rel.book_info?.title || rel.book_id }}</span>
                  </NuxtLink>
                  <button
                    type="button"
                    class="dt-btn dt-btn--ghost"
                    :aria-busy="pdfCheckingAt === `related:${rel.book_id}` ? 'true' : undefined"
                    :aria-describedby="relatedPdfProblem?.id === rel.book_id ? relatedProblemId(rel.book_id) : undefined"
                    @click="openRelatedPdf(rel)"
                  >
                    원문 보기
                  </button>
                  <button
                    type="button"
                    class="dt-btn dt-btn--icon"
                    aria-label="출처 인용"
                    @click="openCitation(rel.book_id, rel.book_info?.references)"
                  >
                    <img src="/img/ico-paper-bookmark.svg" alt="" />
                  </button>
                </template>
                <template #note>
                  <SkxInlineError
                    v-if="relatedPdfProblem?.id === rel.book_id"
                    :id="relatedProblemId(rel.book_id)"
                    :message="relatedPdfProblem?.message ?? ''"
                  />
                </template>
              </DetailRelatedCard>
            </div>
          </section>

          <!-- 참고문헌 — 제목 줄의 ˄/˅ 로 접고 편다 -->
          <DetailCollapse v-model:open="refsOpen" title="참고문헌">
            <ol v-if="references.length" class="dt-refs">
              <li v-for="(ref, i) in references" :key="i">{{ ref }}</li>
            </ol>
            <SkxErrorState v-else kind="empty" compact :title="PAPER_STATE_TEXT.referencesEmpty" />
          </DetailCollapse>
        </template>

        <!-- 논문을 읽지 못했다 — 없는 논문(404)은 차분한 '찾을 수 없음' + 돌아가기, 그 밖(연결·서버)은 [다시 시도] + 돌아가기.
             이 화면의 제목(h1)이 없어지는 자리라 상태 제목을 h1 으로 -->
        <SkxErrorState
          v-else-if="paperError"
          title-tag="h1"
          :kind="paperError.kind"
          :title="paperError.kind === 'notFound' ? PAPER_STATE_TEXT.detailNotFound : PAPER_STATE_TEXT.detailFailed"
          :message="paperError.kind === 'notFound' ? PAPER_STATE_TEXT.detailNotFoundHint : paperError.message"
          :busy="loading"
          :on-retry="isRetryableKind(paperError.kind) ? retryPaper : undefined"
        >
          <a :href="back.to" class="skx-state__action" @click="onBack">{{ back.label }}</a>
        </SkxErrorState>
      </div>
    </main>

    <!-- 채팅 패널 -->
    <aside v-if="paper" id="dt-chat" :class="['skx-chat-panel', chatOpen && 'is-open']">
      <div class="skx-chat-panel__inner">
        <div class="skx-chat-header">
          <button type="button" class="skx-chat-close" aria-label="DeepRead 닫기" @click="chatOpen = false">
            <img src="/img/ico-arrow.svg" alt="" class="skx-chat-close__ico" />
          </button>
          <h2 class="skx-chat-title">
            DeepRead<template v-if="paper?.title">: {{ paper.title }}</template>
          </h2>
        </div>
        <BookChat :cnts-id="paperId" :book-title="paper?.title" doc-kind="paper" @close="chatOpen = false" />
      </div>
    </aside>

    <!-- 출처 인용 모달 — 이 논문·연관 논문이 같이 쓴다 -->
    <CitationModal
      :open="!!citeTarget"
      :book-id="citeTarget?.id ?? null"
      :references="citeTarget?.refs ?? []"
      @close="citeTarget = null"
    />

    <!-- PDF 뷰어 모달 -->
    <PdfViewer
      v-if="pdf"
      :cnts-id="pdf.cntsId"
      :title="pdf.title"
      :page="pdf.page"
      :passages="pdf.passages"
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
import { marked } from "marked";
import type { ComponentPublicInstance } from "vue";
import { useBookmark } from "~/composables/useBookmark";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { API_SEARCH_TIMEOUT_MS, apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { usePdfOpener } from "~/composables/usePdfOpener";
import { useResearchApi } from "~/composables/useResearch";
import type { OpenPdfPayload, ReportChunk, ResearchJob } from "~/types/research";
import { readAiCache, relatedCacheKey, summaryCacheKey, writeAiCache } from "~/utils/aiCache";
import {
  AI_SUMMARY_FAILED,
  type AiStreamEnd,
  failureText,
  readAiStream,
  RELATED_REASON_FAILED,
} from "~/utils/aiStream";
import { safeSessionStorage } from "~/utils/browserId";
import { DEEP_RESEARCH, SPINNER_SRC } from "~/utils/brand";
import { backTarget, readDetailSource, readReturnSpot, relatedDetailUrl, shouldGoBack } from "~/utils/detailSource";
import {
  activeTabKey,
  aiTabAvailable,
  detailSearchUrl,
  focusOwningPanel,
  formatAuthors,
  paperMetaRows,
  queryScore,
  relatedMetaLine,
  relativeScore,
  visibleTabs,
  withChat,
} from "~/utils/detailView";
import { citeContext, summaryQuestion, withRo, type CiteContext } from "~/utils/paperDetail";
import { isRetryableKind, PAPER_STATE_TEXT, shownError, type ShownError } from "~/utils/paperErrors";
import { paperResearchQuestion, paperResearchUrl } from "~/utils/paperResearch";
import { citedPdfTarget } from "~/utils/pdfViewer";
import { isPlainClick } from "~/utils/restorePosition";
import { cardKeywords } from "~/utils/resultCard";
import { relatedOpenAfter } from "~/utils/relatedCard";

const route = useRoute();
const router = useRouter();
const config = useRuntimeConfig();
const api = useApi();
// 페이지를 떠나면 추천 이유·연관 이유 스트림을 끊는다 — 연관 논문마다 동시에 도는 생성이 끝까지 돈다
const pageAbort = new AbortController();
onBeforeUnmount(() => pageAbort.abort());

const { isBookmarked, toggleBookmark, bookmarkIcon } = useBookmark();

const paperId = route.params.id as string;
// 주소에 실린 출처 — 돌아갈 곳·관련도·AI 요약 기준·인용 배너가 모두 여기서 정해진다(새 탭·새로고침에도).
// 다른 논문으로 넘어가면 페이지가 새로 마운트되므로 한 번만 읽는다
const source = readDetailSource(route.query);
const spot = readReturnSpot(route.query);
const back = backTarget(source, spot);

// 관련도는 검색 결과에서 온 상세에만 뜻이 있다. 알약은 결과 카드와 같은 RelevanceBadge(제목·내용 일치율이 실려 오면 팝오버)
const matchScore = computed(() => (source.kind === "search" ? queryScore(route.query.score) : null));
const titleScore = computed(() => queryScore(route.query.title_score));
const contentScore = computed(() => queryScore(route.query.content_score));

// vue-router 는 직전 기록의 경로를 history.state.back 에 둔다. 직전이 출처면 뒤로 가야 그 화면이 브라우저 기록의
// 상태를 그대로 쓰고 기록도 한 칸 더 쌓이지 않는다. 새 탭으로 여는 클릭(보조키·가운데 버튼)은 링크에 맡긴다
function onBack(e: MouseEvent): void {
  if (!isPlainClick(e)) return;
  e.preventDefault();
  goBack();
}

function goBack(): void {
  const prev = window.history.state?.back;
  if (shouldGoBack(typeof prev === "string" ? prev : null, back.to)) router.back();
  else void router.push(back.to);
}

// 위 검색바 — 들어온 검색과 같은 검색어면 그 결과로 돌아가고(재검색 없이), 다르면 새 논문 검색
const searchInitial = computed(() => (source.kind === "search" ? source.q : (cite.value?.question ?? "")));
function onSearch(input: string): void {
  const url = detailSearchUrl("paper", input, source.kind === "search" ? { q: source.q, to: back.to } : null);
  if (!url) return;
  if (url === back.to) goBack();
  else void navigateTo(url);
}

// Data
const paper = ref<any>(null);
// 처음부터 읽는 중 — 마운트 전 첫 그림에 오류 상태가 번쩍이지 않게
const loading = ref(true);
// 논문을 읽지 못했다(404 찾을 수 없음·연결·서버) — 본문 자리의 상태 블록. [다시 시도]로 다시 읽는 동안에도 남아 재시도 중으로 보인다
const paperError = ref<ShownError | null>(null);

useHead({ title: () => (paper.value?.title ? `${paper.value.title} — 논문` : "논문") });

const metaRows = computed(() => paperMetaRows(paper.value));
const references = computed<string[]>(() => (Array.isArray(paper.value?.references) ? paper.value.references : []));
// 참고문헌은 시안대로 펼친 채 시작한다
const refsOpen = ref(true);

function parseLegacySummary(raw: unknown): {
  body: string;
  keywords: string[];
} {
  if (typeof raw !== "string" || !raw.trim()) return { body: "", keywords: [] };
  let text = raw.replace(/^##\s*SUMMARY:\s*/i, "").trim();
  const kwMatch = text.match(/\*\*관련\s*연구자가\s*검색할\s*학술\s*키워드\s*:\*\*\s*([\s\S]*?)$/i);
  let keywords: string[] = [];
  if (kwMatch && kwMatch[1]) {
    keywords = kwMatch[1]
      .split(/[,;]/)
      .map((k) => k.trim())
      .filter(Boolean)
      .slice(0, 12);
    text = text.slice(0, kwMatch.index).trim();
  }
  return { body: text, keywords };
}

const abstractText = computed<string>(() => {
  if (paper.value?.abstract) return paper.value.abstract;
  if (typeof paper.value?.summary === "string" && paper.value.summary)
    return parseLegacySummary(paper.value.summary).body;
  return "";
});

// 키워드 칩 — 결과 카드와 같은 규칙(저자 키워드 → keyword → 생성 주제어 → subject 중 먼저 비지 않은 하나, 최대 CARD_KEYWORD_LIMIT 개).
// 하나도 없으면 레거시 요약에 박힌 키워드 섹션
const keywords = computed<string[]>(() =>
  cardKeywords(paper.value, parseLegacySummary(paper.value?.summary).keywords),
);

// 이 논문으로 딥리서치 — 제목·키워드로 만든 질문 초안(제목이 없으면 빈 글이라 칸을 숨긴다)
const researchQuestion = computed(() => paperResearchQuestion(paper.value?.title ?? "", keywords.value));

// AI summary
const summaryText = ref("");
const summaryLoading = ref(false);
// 요약을 다 정했는지(받기 끝·캐시·소개글) — 정하기 전에는 비어 있어도 [AI 요약] 탭을 둔다(곧 채워진다)
const summaryDone = ref(false);
// 요약을 만들지 못했을 때 보일 문구(AI_SUMMARY_FAILED — 서버의 {error} 문구는 쓰지 않는다) — 받은 글에 잇지 않고 따로 보인다.
// summaryQuestionText 는 [다시 시도]가 같은 기준 질문으로 다시 받게 쥔다. summaryFailedRef 는 그 줄 안내(초점을 옮길 탭 본문을 찾는다)
const summaryError = ref("");
const summaryQuestionText = ref("");
const summaryFailedRef = ref<ComponentPublicInstance | null>(null);
const renderedSummary = computed(() => (summaryText.value ? (marked.parse(summaryText.value) as string) : ""));

// AI 큐레이션 탭 — 글이 없는 탭은 뺀다. 고른 탭이 빠지면 첫 탭. [AI 요약]은 [다시 시도]로 다시 받는 동안에도 남는다
const curationTab = ref<string | null>("ai-summary");
const curationTabs = computed(() =>
  visibleTabs([
    { key: "ai-summary", label: "AI 요약", available: aiTabAvailable({ loading: summaryLoading.value, done: summaryDone.value, text: summaryText.value, error: summaryError.value }) },
    { key: "abstract", label: "초록", available: !!abstractText.value },
  ]),
);
const activeCuration = computed(() => activeTabKey(curationTab.value, curationTabs.value));

// Related
const relatedItems = ref<any[]>([]);
const relatedLoading = ref(false);
// 관련 자료를 읽지 못했다 — 0건(빈 상태)과 가른다. [다시 시도]로 다시 읽는 동안에도 남아 재시도 중으로 보인다
const relatedError = ref<ShownError | null>(null);
const relatedReasons = ref<Record<string, string>>({});
const relatedReasonLoading = ref<Set<string>>(new Set());
// 추천 사유를 만들지 못한 연관 논문 → 보일 문구. 캐시에 담지 않으므로 상세를 다시 열면 다시 만든다
const relatedReasonErrors = ref<Record<string, string>>({});
// [자세히 보기]로 연 카드 — 한 번에 하나
const openRelated = ref<string | null>(null);
// 연관 논문 점수는 절대값이 아주 작아 목록 1위를 100% 로 둔 비율로 보인다
const relatedScores = computed(() => relatedItems.value.map((r) => r.score));

function onRelatedThumbError(e: Event) {
  const img = e.target as HTMLImageElement;
  if (!img.src.endsWith("/img/img-paper-thumb.png")) img.src = "/img/img-paper-thumb.png";
}

// UI
const chatOpen = ref(false);
const toast = ref("");
const thumbnailUrl = ref(`${config.public.apiBase}/books/${paperId}/thumbnail`);

// 출처 인용 — 이 논문·연관 논문 어느 쪽이든 같은 모달
const citeTarget = ref<{ id: string; refs: string[] } | null>(null);
function openCitation(id: string, refs: unknown) {
  citeTarget.value = { id, refs: Array.isArray(refs) ? (refs as string[]) : [] };
}

// ── 인용 맥락(보고서에서 온 상세) ──────────────────────────
const researchApi = useResearchApi();
const cite = ref<CiteContext | null>(null);

// 배너와 AI 요약 기준 질문을 그 보고서에서 읽는다. 못 읽으면 배너 없이 두고 요약은 소개글로 대신한다
async function loadResearch(): Promise<Pick<ResearchJob, "question" | "report"> | null> {
  if (source.kind !== "research") return null;
  try {
    const job = await researchApi.get(source.job);
    cite.value = citeContext(job, source.e, paperId);
    return job;
  } catch {
    return null;
  }
}

function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

// 원문 보기 — 파일이 있는지 먼저 확인하고 연다. 없으면 누른 버튼 아래에 알리고 KCI 페이지 링크를 건넨다
const { pdf, checking: checkingPdf, openPdf, closePdf } = usePdfOpener();
const pdfProblem = ref("");
// 배너의 [인용 대목 보기]가 열지 못한 까닭 — 배너 안에 알린다
const bannerPdfProblem = ref("");
// 연관 논문 카드 팝업의 [원문 보기]가 열지 못한 까닭 — 그 카드 팝업 안에 알린다
const relatedPdfProblem = ref<{ id: string; message: string } | null>(null);

// 지금 원문 파일을 확인하는 버튼('original' 머리 · 'banner' 인용 배너 · 'related:{id}' 관련 카드) — 그 버튼에만 aria-busy 를 단다
// (확인은 한 번에 하나라 다른 버튼은 누름만 무시된다)
const pdfCheckingAt = ref<string | null>(null);
async function checkPdfAt(at: string, target: OpenPdfPayload): Promise<string | null> {
  pdfCheckingAt.value = at;
  try {
    return await openPdf(target);
  } finally {
    pdfCheckingAt.value = null;
  }
}

// 관련 카드의 원문을 열지 못한 까닭 줄 — 그 카드의 [원문 보기]가 aria-describedby 로 가리킨다
function relatedProblemId(bookId: string): string {
  return `pdetail-related-problem-${bookId}`;
}

// 확인 중에는 어느 쪽 버튼이든 무시한다 — openPdf 가 null 을 돌려줘 안내 문구가 지워지는 일이 없게. 원문이 열리면 두 문구를 함께 지운다
async function openOriginal() {
  if (checkingPdf.value) return;
  const problem = await checkPdfAt("original", { cntsId: paperId, title: paper.value?.title ?? "" });
  pdfProblem.value = problem ?? "";
  if (!problem) bannerPdfProblem.value = "";
}

// 첫 인용 쪽에서 열고 머리의 "인용 대목 n/N" 으로 대목을 넘겨 본다
async function openCitedPassages(chunks: readonly ReportChunk[]) {
  if (checkingPdf.value) return;
  const problem = await checkPdfAt("banner", citedPdfTarget(paperId, paper.value?.title ?? "", chunks));
  bannerPdfProblem.value = problem ?? "";
  if (!problem) pdfProblem.value = "";
}

async function openRelatedPdf(rel: any) {
  if (checkingPdf.value) return;
  const problem = await checkPdfAt(`related:${rel.book_id}`, { cntsId: rel.book_id, title: rel.book_info?.title ?? "" });
  relatedPdfProblem.value = problem ? { id: rel.book_id, message: problem } : null;
}

// 논문을 읽는다. 실패하면 paperError(404 는 찾을 수 없음) — 페이지를 떠나 끊긴 요청(pageAbort)은 알리지 않는다.
// 오류 문구는 오류 규칙(apiErrors)이 고른 이유만 — 서버 detail('도서 없음: …')·ofetch 의 영문 메시지는 보이지 않는다
async function fetchPaper() {
  loading.value = true;
  try {
    const data = await api<any>(`/books/${paperId}`, { signal: pageAbort.signal });
    paper.value = data;
    paperError.value = null;
  } catch (e) {
    paper.value = null;
    const shown = shownError(e);
    if (shown) paperError.value = shown;
  } finally {
    loading.value = false;
  }
}

// 관련 자료를 읽는다. 실패하면 relatedError — '관련 자료가 없어요'(0건)와 가른다. 받은 연관 논문마다 추천 사유를 동시에 받는다
async function fetchRelated() {
  relatedLoading.value = true;
  try {
    const data = await api<any>(`/papers/${paperId}/related`, {
      signal: pageAbort.signal,
      // 임베딩 검색을 돌리는 GET 이라 읽기 기본 제한(30초) 대신 검색 제한을 쓴다
      timeout: API_SEARCH_TIMEOUT_MS,
    });
    relatedItems.value = data?.results || [];
    relatedError.value = null;
  } catch (e) {
    const shown = shownError(e);
    if (shown) relatedError.value = shown;
  } finally {
    relatedLoading.value = false;
  }
  // 로드 완료 후 모든 연관 논문 유사성 이유 동시 스트리밍
  relatedItems.value.forEach((rel) => streamRelatedReason(rel.book_id));
}

// 관련 자료 읽기 실패의 [다시 시도] — 받는 동안 상태 블록이 재시도 중으로 남는다
function retryRelated() {
  if (relatedLoading.value) return;
  void fetchRelated();
}

// 기준 질문이 없으면(출처 없음·보고서를 못 읽음) 만들지 않고 소개글을 보인다
async function streamPaperReason(query: string) {
  summaryQuestionText.value = query;
  summaryError.value = "";
  if (!query) {
    summaryText.value = paper.value?.introduction || "";
    summaryDone.value = true;
    return;
  }
  const key = summaryCacheKey(paperId, query);
  const cached = readAiCache(safeSessionStorage(), key);
  if (cached) {
    summaryText.value = cached;
    summaryDone.value = true;
    return;
  }
  summaryText.value = "";
  summaryLoading.value = true;
  let end: AiStreamEnd = { ok: false, error: null };
  try {
    const resp = await fetch(apiUrl("/papers/reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ paper_id: paperId, query }),
      signal: pageAbort.signal,
    });
    end = await readAiStream(resp, (json) => {
      if (typeof json.text === "string" && json.text) summaryText.value += json.text;
    });
  } catch {
    /* 떠남(pageAbort)·네트워크 오류 — 아래에서 가린다 */
  }
  summaryLoading.value = false;
  summaryDone.value = true;
  // 끝까지 받은 글만 캐시에 담는다 — 실패({error}·끊김)한 글은 담지 않아 상세를 다시 열면 다시 만든다
  if (end.ok) writeAiCache(safeSessionStorage(), key, summaryText.value);
  else if (!pageAbort.signal.aborted) summaryError.value = failureText(end, AI_SUMMARY_FAILED);
}

// [다시 시도] — 같은 기준 질문으로 AI 요약을 처음부터 다시 받는다. 버튼(줄 안내)은 받는 동안 빠지므로 초점을 탭 본문으로 먼저 옮긴다
function retrySummary() {
  if (summaryLoading.value) return;
  focusOwningPanel(summaryFailedRef.value?.$el ?? null);
  void streamPaperReason(summaryQuestionText.value);
}

async function streamRelatedReason(relatedId: string) {
  const key = relatedCacheKey(paperId, relatedId);
  const cached = readAiCache(safeSessionStorage(), key);
  if (cached) {
    relatedReasons.value = { ...relatedReasons.value, [relatedId]: cached };
    return;
  }
  relatedReasonLoading.value = new Set([...relatedReasonLoading.value, relatedId]);
  let end: AiStreamEnd = { ok: false, error: null };
  try {
    const resp = await fetch(apiUrl("/papers/related-reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ source_id: paperId, related_id: relatedId }),
      signal: pageAbort.signal,
    });
    end = await readAiStream(resp, (json) => {
      if (typeof json.text === "string" && json.text) {
        relatedReasons.value = {
          ...relatedReasons.value,
          [relatedId]: (relatedReasons.value[relatedId] || "") + json.text,
        };
      }
    });
  } catch {
    /* 떠남(pageAbort)·네트워크 오류 — 아래에서 가린다 */
  }
  const next = new Set(relatedReasonLoading.value);
  next.delete(relatedId);
  relatedReasonLoading.value = next;
  // 끝까지 받은 사유만 캐시에 담는다 — 실패({error}·끊김)는 카드에 오류로 보이고 담지 않는다
  if (end.ok) writeAiCache(safeSessionStorage(), key, relatedReasons.value[relatedId] ?? "");
  else if (!pageAbort.signal.aborted) {
    relatedReasonErrors.value = { ...relatedReasonErrors.value, [relatedId]: failureText(end, RELATED_REASON_FAILED) };
  }
}

// 관련 논문 카드의 추천 사유 [다시 시도] — 그 카드의 실패 안내와 받다 만 글을 걷고 처음부터 다시 받는다
function retryRelatedReason(relatedId: string) {
  if (relatedReasonLoading.value.has(relatedId)) return;
  const { [relatedId]: _failed, ...errors } = relatedReasonErrors.value;
  relatedReasonErrors.value = errors;
  const { [relatedId]: _partial, ...reasons } = relatedReasons.value;
  relatedReasons.value = reasons;
  void streamRelatedReason(relatedId);
}

// 논문 → (읽었으면) 관련 자료·AI 요약. 보고서는 논문과 함께 읽는다 — 보고서에서 온 상세는 AI 요약의 기준 질문이 보고서 질문이다.
// 보고서를 받는 동안도 분석 중으로 둔다 — 큰 보고서를 기다리는 사이 빈 요약 상태가 먼저 뜨지 않게.
// 논문을 읽지 못하면 관련 자료·요약은 받지 않는다(보일 자리가 없다) — [다시 시도]가 이 흐름을 처음부터 다시 돈다
async function loadPage() {
  const research = loadResearch();
  summaryLoading.value = source.kind === "research";
  await fetchPaper();
  if (!paper.value) {
    summaryLoading.value = false;
    return;
  }
  if (route.query.chat === "1") chatOpen.value = true;
  fetchRelated();
  // loadResearch 는 보고서를 못 읽어도 null 로 끝난다 — 그때는 소개글로 넘어간다. 질문이 정해지면 캐시·스트림·소개글이 바로 이어 받는다
  const question = summaryQuestion(source, await research);
  summaryLoading.value = false;
  streamPaperReason(question);
}

// 논문 읽기 실패의 [다시 시도] — 받는 동안 상태 블록이 재시도 중으로 남는다
function retryPaper() {
  if (loading.value) return;
  void loadPage();
}

onMounted(() => {
  void loadPage();
});
</script>
