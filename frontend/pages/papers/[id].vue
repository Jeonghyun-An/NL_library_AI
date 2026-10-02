<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <div class="skx-result-card">
      <main class="skx-pdetail">
        <!-- 돌아가기 — 직전 화면이 출처면 브라우저 뒤로(그 화면 상태 그대로), 새 탭·연관 논문을 거쳐 왔으면 출처 주소로 간다 -->
        <a :href="back.to" class="skx-pdetail__back pd-back" @click="onBack">
          <img src="/img/ico-arrow.svg" alt="" />
          {{ back.label }}
        </a>

        <!-- 인용 맥락 — 보고서의 인용칩에서 왔을 때 이 논문이 그 보고서에서 어떻게 쓰였는지 보인다 -->
        <section v-if="cite" class="pd-cite" aria-label="인용 맥락">
          <div class="pd-cite__row">
            <p class="pd-cite__text">
              딥리서치 보고서 ‘{{ cite.question }}’에서
              <strong>{{ withRo(cite.label) }}</strong> 인용됨
              <span aria-hidden="true">·</span> 인용 대목 {{ cite.chunks.length }}곳
            </p>
            <!-- 첫 인용 쪽에서 원문 뷰어를 열고 인용 대목을 넘겨 본다 -->
            <button
              type="button"
              class="pd-cite__btn"
              :aria-busy="checkingPdf"
              :aria-describedby="bannerPdfProblem ? 'pdetail-cite-problem' : undefined"
              @click="openCitedPassages(cite.chunks)"
            >
              인용 대목 보기
            </button>
          </div>
          <p v-if="bannerPdfProblem" id="pdetail-cite-problem" class="pd-pdf-note" role="alert">
            {{ bannerPdfProblem }}
            <a v-if="paper?.url" :href="paper.url" target="_blank" rel="noopener"
              >KCI에서 원문 페이지 열기<span class="skx-sr-only"> (새 창)</span></a
            >
          </p>
        </section>

        <div v-if="loading" style="padding: 40px; text-align: center">
          <img src="/img/ico-spinner.svg" alt="" style="width: 32px" />
        </div>

        <template v-else-if="paper">
          <!-- 논문 헤더 -->
          <section class="skx-pdetail__hero">
            <div class="skx-pdetail__cover">
              <img
                :src="thumbnailUrl"
                alt="논문 표지"
                @error="thumbnailUrl = '/img/img-paper-thumb.png'"
              />
            </div>
            <div class="skx-pdetail__meta">
              <div class="skx-pdetail__top-row">
                <div class="skx-pdetail__badges">
                  <span v-if="paper.grade" class="skx-ptag skx-ptag--kci">
                    {{ paper.grade }}
                  </span>
                  <span v-if="matchScore" class="skx-ptag skx-ptag--score"
                    >관련도 {{ matchScore }}%</span
                  >
                </div>
                <div class="skx-pdetail__share-group">
                  <button
                    type="button"
                    class="skx-btn-icon-sm"
                    :aria-label="isBookmarked(paperId) ? '북마크 해제' : '북마크'"
                    @click="toggleBookmark(paperId)"
                  >
                    <img :src="bookmarkIcon(paperId)" alt="" />
                  </button>
                </div>
              </div>
              <h1 class="skx-pdetail__title">{{ paper.title }}</h1>
              <p v-if="paper.title_remainder" class="skx-pdetail__title-en">
                {{ paper.title_remainder }}
              </p>
              <div class="skx-pdetail__rows">
                <div
                  v-if="paper.personal_author || paper.corporate_author"
                  class="skx-pdetail__row"
                >
                  <span class="skx-pdetail__row-lbl">저자정보</span>
                  <span class="skx-pdetail__row-val">{{
                    paper.personal_author || paper.corporate_author
                  }}</span>
                </div>
                <div
                  v-if="paper.publisher || paper.series_title"
                  class="skx-pdetail__row"
                >
                  <span class="skx-pdetail__row-lbl">저널정보</span>
                  <span class="skx-pdetail__row-val">
                    <template v-if="paper.publisher">{{
                      paper.publisher
                    }}</template>
                    <template v-if="paper.publisher && paper.series_title">
                      <img
                        class="skx-pdetail__row-arr"
                        src="/img/ico-arrow.svg"
                        alt=""
                      />
                    </template>
                    <template v-if="paper.series_title">{{
                      paper.series_title
                    }}</template>
                    <template v-if="paper.vol_issue">
                      <img
                        class="skx-pdetail__row-arr"
                        src="/img/ico-arrow.svg"
                        alt=""
                      />
                      {{ paper.vol_issue }}
                    </template>
                  </span>
                </div>
                <div v-if="paper.pub_date" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">발행년월</span>
                  <span class="skx-pdetail__row-val">{{ paper.pub_date }}</span>
                </div>
                <div v-if="paper.extent" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">수록면</span>
                  <span class="skx-pdetail__row-val">{{ paper.extent }}</span>
                </div>
                <div v-if="paper.kci_citations" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">KCI 인용수</span>
                  <span class="skx-pdetail__row-val">{{
                    paper.kci_citations
                  }}</span>
                </div>
                <div v-if="paper.wos_citations" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">WOS 인용수</span>
                  <span class="skx-pdetail__row-val">{{
                    paper.wos_citations
                  }}</span>
                </div>
              </div>
              <div class="skx-pdetail__btns">
                <button
                  type="button"
                  :class="[
                    'skx-btn-talk skx-btn-talk--paper',
                    chatOpen && 'is-active',
                  ]"
                  @click="chatOpen = !chatOpen"
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
                <!-- 원문 보기는 늘 이 화면의 원문 뷰어로 연다 — 외부(KCI) 페이지는 보조 링크로 따로 둔다 -->
                <button
                  type="button"
                  class="skx-btn-pview-sm"
                  :aria-busy="checkingPdf"
                  :aria-describedby="pdfProblem ? 'pdetail-pdf-problem' : undefined"
                  @click="openOriginal"
                >
                  원문 보기
                </button>
                <button
                  type="button"
                  class="skx-btn-pbmark-sm"
                  aria-label="출처 인용"
                  @click="citationModal = true"
                >
                  <img src="/img/ico-paper-bookmark.svg" alt="" />
                </button>
                <a
                  v-if="paper.url"
                  :href="paper.url"
                  target="_blank"
                  rel="noopener"
                  class="pd-kci"
                  >KCI에서 보기<span class="skx-sr-only"> (새 창)</span></a
                >
              </div>
              <!-- 원문이 없으면 뷰어 대신 누른 자리 아래에 알리고 KCI 페이지를 건넨다 -->
              <p v-if="pdfProblem" id="pdetail-pdf-problem" class="pd-pdf-note" role="alert">
                {{ pdfProblem }}
                <a v-if="paper.url" :href="paper.url" target="_blank" rel="noopener"
                  >KCI에서 원문 페이지 열기<span class="skx-sr-only"> (새 창)</span></a
                >
              </p>
            </div>
          </section>

          <!-- AI 큐레이션 수직탭 -->
          <section class="skx-curation">
            <h2 class="skx-section-title">AI 큐레이션</h2>
            <div class="skx-curation-panel">
              <div class="skx-vtabs-col">
                <div class="skx-vtabs" role="tablist" ref="vtabsRef">
                  <span
                    class="skx-vtabs__slider"
                    :style="vtabSliderStyle"
                  ></span>
                  <button
                    v-for="tab in curationTabs"
                    :key="tab.key"
                    type="button"
                    :class="[
                      'skx-vtab',
                      curationTab === tab.key && 'is-active',
                    ]"
                    role="tab"
                    :aria-selected="curationTab === tab.key"
                    @click="switchCurationTab(tab.key)"
                  >
                    {{ tab.label }}
                  </button>
                </div>
              </div>
              <div class="skx-curation-content">
                <div class="skx-curation-card">
                  <div v-if="curationTab === 'ai-summary'" role="tabpanel">
                    <p v-if="summaryLoading" class="skx-curation-text">
                      AI가 핵심을 분석 중입니다...
                    </p>
                    <div
                      v-else-if="summaryText"
                      class="skx-curation-text"
                      v-html="renderedSummary"
                    />
                    <p v-else class="skx-curation-text">
                      AI 분석 정보가 없습니다.
                    </p>
                  </div>
                  <p
                    v-else-if="curationTab === 'abstract'"
                    role="tabpanel"
                    class="skx-curation-text"
                  >
                    {{ abstractText || "초록/요약 정보가 없습니다." }}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <!-- 아코디언: 키워드 -->
          <div class="skx-paccordion">
            <div :class="['skx-paccord', keywordOpen && 'is-open']">
              <button
                type="button"
                class="skx-paccord__head"
                :aria-expanded="keywordOpen"
                @click="keywordOpen = !keywordOpen"
              >
                <span class="skx-paccord__title">키워드</span>
                <img
                  class="skx-paccord__arrow"
                  src="/img/ico-arrow-down.svg"
                  alt=""
                  aria-hidden="true"
                />
              </button>
              <!-- 높이만 0 으로 접혀 보이지 않는 키워드 링크에 Tab 초점이 가지 않게 접힌 동안은 inert -->
              <div class="skx-paccord__body-outer" :inert="!keywordOpen">
                <div class="skx-paccord__body">
                  <div class="skx-keyword-list">
                    <!-- 키워드를 누르면 그 키워드로 새 논문 검색을 연다 -->
                    <NuxtLink
                      v-for="kw in keywords"
                      :key="kw"
                      :to="{ path: '/papers', query: { q: kw } }"
                      class="skx-keyword pd-keyword"
                      :aria-label="`${kw} — 이 키워드로 논문 검색`"
                      >{{ kw }}</NuxtLink
                    >
                    <span
                      v-if="!keywords.length"
                      style="color: #bbb; font-size: 12px"
                      >키워드 정보가 없습니다.</span
                    >
                  </div>
                </div>
              </div>
            </div>

            <!-- 아코디언: 참고문헌 -->
            <div :class="['skx-paccord', refsOpen && 'is-open']">
              <button
                type="button"
                class="skx-paccord__head"
                :aria-expanded="refsOpen"
                @click="refsOpen = !refsOpen"
              >
                <span class="skx-paccord__title">참고문헌</span>
                <img
                  class="skx-paccord__arrow"
                  src="/img/ico-arrow-down.svg"
                  alt=""
                  aria-hidden="true"
                />
              </button>
              <div class="skx-paccord__body-outer">
                <div class="skx-paccord__body">
                  <ol v-if="paper.references?.length" class="skx-refs-list">
                    <li
                      v-for="(ref, i) in paper.references"
                      :key="i"
                      class="skx-ref-item"
                    >
                      {{ ref }}
                    </li>
                  </ol>
                  <p
                    v-else
                    style="color: #bbb; font-size: 12px; padding: 8px 0"
                  >
                    참고문헌 정보가 없습니다.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- AI 연관 논문 추천 -->
          <section class="skx-prelate" aria-label="AI 연관 논문 추천">
            <h2 class="skx-prelate__heading">AI 연관 논문 추천</h2>
            <div class="skx-prelate__list">
              <div
                v-if="relatedLoading"
                style="padding: 16px; color: #bbb; font-size: 12px"
              >
                불러오는 중...
              </div>
              <!-- 카드 전체가 제목 링크다(pd-rel__link::after) — 키보드로도 넘어가고, 연관 논문으로 넘어가도 처음 출처를 잇는다 -->
              <article
                v-for="rel in relatedItems"
                :key="rel.book_id"
                class="skx-prelate-card pd-rel"
              >
                <div class="skx-prelate-card__info">
                  <span class="skx-prelate-card__score"
                    >연관도 {{ relatedScore(rel.score) }}%</span
                  >
                  <div class="skx-prelate-card__title-row">
                    <h3 class="skx-prelate-card__title">
                      <NuxtLink
                        :to="relatedDetailUrl(rel.book_id, source, spot)"
                        class="pd-rel__link"
                        >{{ rel.book_info?.title || rel.book_id }}</NuxtLink
                      >
                    </h3>
                    <p class="skx-prelate-card__author">
                      {{
                        rel.book_info?.personal_author ||
                        rel.book_info?.corporate_author ||
                        ""
                      }}
                    </p>
                  </div>
                </div>
                <div class="skx-prelate-card__ai">
                  <div class="skx-prelate-card__ai-inner">
                    <img
                      class="skx-prelate-card__ai-icon"
                      src="/img/ico-ai-related.svg"
                      alt=""
                    />
                    <p class="skx-prelate-card__ai-text">
                      <template
                        v-if="
                          relatedReasonLoading.has(rel.book_id) &&
                          !relatedReasons[rel.book_id]
                        "
                      >
                        AI가 유사성을 분석 중입니다<span
                          class="skx-stream-cursor"
                        />
                      </template>
                      <template v-else>
                        {{ relatedReasons[rel.book_id] || "" }}
                        <span
                          v-if="relatedReasonLoading.has(rel.book_id)"
                          class="skx-stream-cursor"
                        />
                      </template>
                    </p>
                  </div>
                </div>
              </article>
            </div>
          </section>

          <!-- 이 논문으로 딥리서치: 바로 시작하지 않고 초안을 논문 검색 입력창에 채워 고쳐 보내게 한다 -->
          <section
            v-if="researchQuestion"
            class="pd-research"
            aria-labelledby="pdetail-research-title"
          >
            <h2 id="pdetail-research-title" class="skx-prelate__heading">
              이 논문으로 딥리서치
            </h2>
            <p class="pd-research__draft">{{ researchQuestion }}</p>
            <NuxtLink :to="paperResearchUrl(researchQuestion)" class="skx-btn-pview-sm">
              입력창에서 고쳐 쓰고 시작하기
            </NuxtLink>
          </section>
        </template>
      </main>
    </div>

    <!-- 채팅 패널 -->
    <aside :class="['skx-chat-panel', chatOpen && 'is-open']" v-if="paper">
      <div class="skx-chat-panel__inner">
        <div class="skx-chat-header">
          <button
            type="button"
            class="skx-chat-close"
            @click="chatOpen = false"
          >
            <img src="/img/ico-arrow.svg" alt="" class="skx-chat-close__ico" />
          </button>
          <h2 class="skx-chat-title">
            DeepRead<template v-if="paper?.title"
              >: {{ paper.title }}</template
            >
          </h2>
        </div>
        <BookChat
          :cnts-id="paperId"
          :book-title="paper?.title"
          @close="chatOpen = false"
        />
      </div>
    </aside>

    <!-- 출처 인용 모달 -->
    <CitationModal
      :open="citationModal"
      :book-id="paperId"
      :references="paper?.references ?? []"
      @close="citationModal = false"
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
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { usePdfOpener } from "~/composables/usePdfOpener";
import { useResearchApi } from "~/composables/useResearch";
import type { ReportChunk, ResearchJob } from "~/types/research";
import { readAiCache, relatedCacheKey, summaryCacheKey, writeAiCache } from "~/utils/aiCache";
import { safeSessionStorage } from "~/utils/browserId";
import { backTarget, readDetailSource, readReturnSpot, relatedDetailUrl, shouldGoBack } from "~/utils/detailSource";
import { citeContext, summaryQuestion, withRo, type CiteContext } from "~/utils/paperDetail";
import { paperResearchQuestion, paperResearchUrl } from "~/utils/paperResearch";
import { citedPdfTarget } from "~/utils/pdfViewer";
import { isPlainClick } from "~/utils/restorePosition";

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

// 관련도는 검색 결과에서 온 상세에만 뜻이 있다
const matchScore = computed(() => {
  const s = route.query.score;
  return source.kind === "search" && s ? Math.round(Number(s) * 100) : null;
});

// vue-router 는 직전 기록의 경로를 history.state.back 에 둔다. 직전이 출처면 뒤로 가야 그 화면이 브라우저 기록의
// 상태를 그대로 쓰고 기록도 한 칸 더 쌓이지 않는다. 새 탭으로 여는 클릭(보조키·가운데 버튼)은 링크에 맡긴다
function onBack(e: MouseEvent): void {
  if (!isPlainClick(e)) return;
  e.preventDefault();
  const prev = window.history.state?.back;
  if (shouldGoBack(typeof prev === "string" ? prev : null, back.to)) router.back();
  else void router.push(back.to);
}

// Data
const paper = ref<any>(null);
const loading = ref(false);

useHead({ title: () => (paper.value?.title ? `${paper.value.title} — 논문` : "논문") });

// Vertical tabs
const vtabsRef = ref<HTMLElement | null>(null);
const vtabSliderStyle = ref<{ height: string; transform: string }>({
  height: "0px",
  transform: "translateY(0px)",
});
const curationTab = ref("ai-summary");
const curationTabs = [
  { key: "ai-summary", label: "AI 요약" },
  { key: "abstract", label: "초록" },
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

function switchCurationTab(key: string) {
  curationTab.value = key;
  nextTick(() => updateVtabSlider());
}

// Accordion
const keywordOpen = ref(false);
const refsOpen = ref(false);

function parseLegacySummary(raw: unknown): {
  body: string;
  keywords: string[];
} {
  if (typeof raw !== "string" || !raw.trim()) return { body: "", keywords: [] };
  let text = raw.replace(/^##\s*SUMMARY:\s*/i, "").trim();
  const kwMatch = text.match(
    /\*\*관련\s*연구자가\s*검색할\s*학술\s*키워드\s*:\*\*\s*([\s\S]*?)$/i,
  );
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

const keywords = computed<string[]>(() => {
  // 1. keyword / subject 컬럼
  const kwSource = paper.value?.keyword ?? paper.value?.subject ?? "";
  const kw =
    typeof kwSource === "string"
      ? kwSource
      : Array.isArray(kwSource)
        ? (kwSource as string[]).join(",")
        : "";
  if (kw) {
    return kw
      .split(/[,;]/)
      .map((k: string) => k.trim())
      .filter(Boolean);
  }
  // 2. extracted_keywords (BookOut.extra["keywords"] 노출 필드)
  const extraKw = paper.value?.extracted_keywords;
  if (Array.isArray(extraKw) && extraKw.length) {
    return (extraKw as string[]).slice(0, 12);
  }
  // 3. themes 컬럼 (Stage ④ 핵심 개념어)
  const themes =
    typeof paper.value?.themes === "string" ? paper.value.themes : "";
  if (themes) {
    return themes
      .split(/[,;]/)
      .map((k: string) => k.trim())
      .filter(Boolean)
      .slice(0, 12);
  }
  // 4. 레거시 summary 내장 키워드 섹션
  if (typeof paper.value?.summary === "string" && paper.value.summary) {
    return parseLegacySummary(paper.value.summary).keywords;
  }
  return [];
});

// 이 논문으로 딥리서치 — 제목·키워드로 만든 질문 초안(제목이 없으면 빈 글이라 칸을 숨긴다)
const researchQuestion = computed(() =>
  paperResearchQuestion(paper.value?.title ?? "", keywords.value),
);

// AI summary
const summaryText = ref("");
const summaryLoading = ref(false);
const renderedSummary = computed(() =>
  summaryText.value ? (marked.parse(summaryText.value) as string) : "",
);

// Related
const relatedItems = ref<any[]>([]);
const relatedLoading = ref(false);
const relatedReasons = ref<Record<string, string>>({});
const relatedReasonLoading = ref<Set<string>>(new Set());

function relatedScore(score: number): number {
  const maxScore = Math.max(
    ...relatedItems.value.map((r) => r.score || 0),
    1e-9,
  );
  return Math.round((score / maxScore) * 100);
}

// UI
const chatOpen = ref(false);
const citationModal = ref(false);
const toast = ref("");
const thumbnailUrl = ref(`${config.public.apiBase}/books/${paperId}/thumbnail`);

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

// 확인 중에는 어느 쪽 버튼이든 무시한다 — openPdf 가 null 을 돌려줘 안내 문구가 지워지는 일이 없게. 원문이 열리면 두 문구를 함께 지운다
async function openOriginal() {
  if (checkingPdf.value) return;
  const problem = await openPdf({ cntsId: paperId, title: paper.value?.title ?? "" });
  pdfProblem.value = problem ?? "";
  if (!problem) bannerPdfProblem.value = "";
}

// 첫 인용 쪽에서 열고 머리의 "인용 대목 n/N" 으로 대목을 넘겨 본다
async function openCitedPassages(chunks: readonly ReportChunk[]) {
  if (checkingPdf.value) return;
  const problem = await openPdf(citedPdfTarget(paperId, paper.value?.title ?? "", chunks));
  bannerPdfProblem.value = problem ?? "";
  if (!problem) pdfProblem.value = "";
}

async function fetchPaper() {
  loading.value = true;
  try {
    const data = await api<any>(`/books/${paperId}`, { signal: pageAbort.signal });
    paper.value = data;
  } catch {
    paper.value = null;
  } finally {
    loading.value = false;
  }
}

async function fetchRelated() {
  relatedLoading.value = true;
  try {
    const data = await api<any>(`/papers/${paperId}/related`, {
      signal: pageAbort.signal,
    });
    relatedItems.value = data?.results || [];
  } catch {
    /* silent */
  } finally {
    relatedLoading.value = false;
  }
  // 로드 완료 후 모든 연관 논문 유사성 이유 동시 스트리밍
  relatedItems.value.forEach((rel) => streamRelatedReason(rel.book_id));
}

// 기준 질문이 없으면(출처 없음·보고서를 못 읽음) 만들지 않고 소개글을 보인다
async function streamPaperReason(query: string) {
  if (!query) {
    summaryText.value = paper.value?.introduction || "";
    return;
  }
  const key = summaryCacheKey(paperId, query);
  const cached = readAiCache(safeSessionStorage(), key);
  if (cached) {
    summaryText.value = cached;
    return;
  }
  summaryText.value = "";
  summaryLoading.value = true;
  try {
    const resp = await fetch(apiUrl("/papers/reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ paper_id: paperId, query }),
      signal: pageAbort.signal,
    });
    const finished = await readSSE(resp, (json) => {
      if (json.text) summaryText.value += json.text;
    });
    if (finished) writeAiCache(safeSessionStorage(), key, summaryText.value);
  } catch {
    /* silent */
  } finally {
    summaryLoading.value = false;
  }
}

async function streamRelatedReason(relatedId: string) {
  const key = relatedCacheKey(paperId, relatedId);
  const cached = readAiCache(safeSessionStorage(), key);
  if (cached) {
    relatedReasons.value = { ...relatedReasons.value, [relatedId]: cached };
    return;
  }
  relatedReasonLoading.value = new Set([
    ...relatedReasonLoading.value,
    relatedId,
  ]);
  try {
    const resp = await fetch(apiUrl("/papers/related-reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ source_id: paperId, related_id: relatedId }),
      signal: pageAbort.signal,
    });
    const finished = await readSSE(resp, (json) => {
      if (json.text) {
        relatedReasons.value = {
          ...relatedReasons.value,
          [relatedId]: (relatedReasons.value[relatedId] || "") + json.text,
        };
      }
    });
    if (finished) writeAiCache(safeSessionStorage(), key, relatedReasons.value[relatedId] ?? "");
  } catch {
    /* silent */
  } finally {
    const next = new Set(relatedReasonLoading.value);
    next.delete(relatedId);
    relatedReasonLoading.value = next;
  }
}

// [DONE] 까지 받았으면 true — 도중에 끊긴 글은 캐시에 담지 않는다
async function readSSE(resp: Response, onEvent: (json: any) => void): Promise<boolean> {
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
      if (raw === "[DONE]") return true;
      try {
        onEvent(JSON.parse(raw));
      } catch {
        /* skip */
      }
    }
  }
  return false;
}

onMounted(async () => {
  // 보고서는 논문과 함께 읽는다 — 보고서에서 온 상세는 AI 요약의 기준 질문이 보고서 질문이다
  const research = loadResearch();
  await fetchPaper();
  if (route.query.chat === "1") chatOpen.value = true;
  fetchRelated();
  nextTick(() => updateVtabSlider());
  streamPaperReason(summaryQuestion(source, await research));
});
</script>

<style scoped>
/* 돌아가기는 링크지만 기존 버튼 모양을 그대로 쓴다 */
.pd-back {
  text-decoration: none;
}
.pd-back:focus-visible,
.pd-keyword:focus-visible {
  outline: 2px solid var(--skx-primary);
  outline-offset: 2px;
}
.pd-keyword {
  text-decoration: none;
  transition: background 0.15s;
}
.pd-keyword:hover {
  background: rgba(79, 70, 229, 0.18);
}
/* 카드 전체를 제목 링크의 누르는 자리로 덮는다 — 카드에 click 을 걸면 키보드로 갈 수 없다 */
.pd-rel {
  position: relative;
}
.pd-rel__link {
  color: inherit;
  text-decoration: none;
}
.pd-rel__link::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: var(--skx-radius-md);
}
.pd-rel__link:focus-visible {
  outline: none;
}
.pd-rel__link:focus-visible::after {
  outline: 2px solid var(--skx-primary);
  outline-offset: 2px;
}
/* '유사한 점'은 카드에 마우스를 올려야 펼쳐진다(.skx-prelate-card:hover) — 키보드로 카드 링크에 초점이 가도 같이 펼친다 */
.pd-rel:focus-within .skx-prelate-card__ai {
  max-height: 12rem;
  opacity: 1;
}
/* 인용 맥락 배너 — 보고서의 인용칩에서 온 상세에만 뜬다. 글과 [인용 대목 보기] 버튼을 한 줄에 둔다 */
.pd-cite {
  padding: 0.7rem 1rem;
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  background: rgba(79, 70, 229, 0.05);
  font-size: 0.75rem;
  color: var(--skx-ink);
}
.pd-cite__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.8rem;
}
.pd-cite__text {
  flex: 1;
  min-width: 12rem;
  margin: 0;
  line-height: 1.5;
}
/* KCI 보조 링크가 붙어 좁은 화면에서 버튼 줄이 넘치지 않게 줄을 바꾼다 */
.skx-pdetail__btns {
  flex-wrap: wrap;
}
/* 원문 파일을 확인하는 동안 — 눌린 것이 보이게 한다(초점을 잃지 않게 disabled 는 쓰지 않는다) */
.skx-btn-pview-sm[aria-busy="true"],
.pd-cite__btn[aria-busy="true"] {
  cursor: progress;
  opacity: 0.6;
}
.pd-cite__btn {
  padding: 0.3rem 0.7rem;
  border: 1px solid var(--skx-primary);
  border-radius: var(--skx-radius-sm);
  background: var(--skx-white);
  color: var(--skx-primary);
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
}
.pd-cite__btn:hover {
  background: rgba(79, 70, 229, 0.08);
}
/* 원문 보기 옆 보조 링크 — 버튼보다 한 단계 낮춰 글자 링크로 둔다 */
.pd-kci {
  font-size: 0.7rem;
  color: var(--skx-gray-1);
  text-decoration: underline;
  text-underline-offset: 0.15em;
  white-space: nowrap;
}
.pd-kci:hover {
  color: var(--skx-primary);
}
.pd-cite__btn:focus-visible,
.pd-kci:focus-visible {
  outline: 2px solid var(--skx-primary);
  outline-offset: 2px;
}
/* 원문을 열지 못한 까닭 — 누른 자리 아래에 둔다 */
.pd-pdf-note {
  margin: 0.6rem 0 0;
  font-size: 0.7rem;
  color: #c0392b;
}
.pd-pdf-note a {
  margin-left: 0.3rem;
  color: var(--skx-primary);
  text-decoration: underline;
}
.pd-research {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.8rem;
  padding-bottom: 2.4rem;
}
.pd-research__draft {
  margin: 0;
  padding: 0.8rem 1rem;
  border-left: 3px solid var(--skx-border-c2);
  background: rgba(79, 70, 229, 0.05);
  border-radius: var(--skx-radius-sm);
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--skx-ink-2);
}
@media (prefers-reduced-motion: reduce) {
  .pd-keyword {
    transition: none;
  }
}
</style>
