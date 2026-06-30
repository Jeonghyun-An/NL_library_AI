<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <div class="skx-result-card">
      <main class="skx-pdetail">
        <!-- 뒤로가기 -->
        <button type="button" class="skx-pdetail__back" @click="$router.back()">
          <img src="/img/ico-arrow.svg" alt="" />
          검색 목록 돌아가기
        </button>

        <div v-if="loading" style="padding: 40px; text-align: center">
          <img src="/img/ico-spinner.svg" alt="" style="width: 32px" />
        </div>

        <template v-else-if="paper">
          <!-- 논문 헤더 -->
          <section class="skx-pdetail__hero">
            <div class="skx-pdetail__cover">
              <img src="/img/img-paper-thumb.png" alt="논문 표지" />
            </div>
            <div class="skx-pdetail__meta">
              <div class="skx-pdetail__top-row">
                <div class="skx-pdetail__badges">
                  <span v-if="paper.grade" class="skx-ptag skx-ptag--kci">
                    {{ paper.grade }}
                  </span>
                  <span v-if="matchScore" class="skx-ptag skx-ptag--score"
                    >정합성 {{ matchScore }}%</span
                  >
                </div>
                <div class="skx-pdetail__share-group">
                  <button
                    type="button"
                    class="skx-btn-icon-sm"
                    aria-label="출처 인용"
                    @click="citationModal = true"
                  >
                    <img src="/img/ico-bookmark.svg" alt="" />
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
                    <template v-if="paper.publisher">{{ paper.publisher }}</template>
                    <template v-if="paper.publisher && paper.series_title">
                      <img class="skx-pdetail__row-arr" src="/img/ico-arrow.svg" alt="" />
                    </template>
                    <template v-if="paper.series_title">{{ paper.series_title }}</template>
                    <template v-if="paper.vol_issue">
                      <img class="skx-pdetail__row-arr" src="/img/ico-arrow.svg" alt="" />
                      {{ paper.vol_issue }}
                    </template>
                  </span>
                </div>
                <div v-if="paper.pub_date" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">발행년도</span>
                  <span class="skx-pdetail__row-val">{{ paper.pub_date }}</span>
                </div>
                <div v-if="paper.extent" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">수록면</span>
                  <span class="skx-pdetail__row-val">{{ paper.extent }}</span>
                </div>
                <div v-if="paper.kci_citations" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">인용수</span>
                  <span class="skx-pdetail__row-val">{{ paper.kci_citations }}</span>
                </div>
                <div v-if="paper.wos_citations" class="skx-pdetail__row">
                  <span class="skx-pdetail__row-lbl">이용수</span>
                  <span class="skx-pdetail__row-val">{{ paper.wos_citations }}</span>
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
                  <span class="skx-btn-talk__label">논문과 대화하기</span>
                </button>
                <a
                  v-if="paper.url"
                  :href="paper.url"
                  target="_blank"
                  rel="noopener"
                  class="skx-btn-pview-sm"
                >원문 보기</a>
                <button
                  v-else
                  type="button"
                  class="skx-btn-pview-sm"
                  @click="showToast('원문 링크가 없습니다.')"
                >원문 보기</button>
                <button
                  type="button"
                  class="skx-btn-pbmark-sm"
                  aria-label="출처 인용"
                  @click="citationModal = true"
                >
                  <img src="/img/ico-paper-bookmark.svg" alt="" />
                </button>
              </div>
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
            <div class="skx-paccord">
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
                  :style="keywordOpen ? 'transform:rotate(180deg)' : ''"
                />
              </button>
              <div v-if="keywordOpen" class="skx-paccord__body-outer">
                <div class="skx-paccord__body">
                  <div class="skx-keyword-list">
                    <span
                      v-for="kw in keywords"
                      :key="kw"
                      class="skx-keyword"
                      >{{ kw }}</span
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
            <div class="skx-paccord">
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
                  :style="refsOpen ? 'transform:rotate(180deg)' : ''"
                />
              </button>
              <div v-if="refsOpen" class="skx-paccord__body-outer">
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
              <article
                v-for="rel in relatedItems"
                :key="rel.book_id"
                class="skx-prelate-card"
                style="cursor: pointer"
                @click="navigateTo(`/papers/${rel.book_id}`)"
              >
                <div class="skx-prelate-card__info">
                  <span class="skx-prelate-card__score"
                    >정합성 {{ Math.round((rel.score || 0) * 100) }}%</span
                  >
                  <div class="skx-prelate-card__title-row">
                    <h3 class="skx-prelate-card__title">
                      {{ rel.book_info?.title || rel.book_id }}
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
          <h2 class="skx-chat-title">논문과 대화하기</h2>
        </div>
        <BookChat :cnts-id="paperId" @close="chatOpen = false" />
      </div>
    </aside>

    <!-- 출처 인용 모달 -->
    <CitationModal
      :open="citationModal"
      :book-id="paperId"
      :references="paper?.references ?? []"
      @close="citationModal = false"
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

const route = useRoute();
const config = useRuntimeConfig();
const paperId = route.params.id as string;

const matchScore = computed(() => {
  const s = route.query.score;
  return s ? Math.round(Number(s) * 100) : null;
});

// Data
const paper = ref<any>(null);
const loading = ref(false);

// Vertical tabs
const vtabsRef = ref<HTMLElement | null>(null);
const vtabSliderStyle = ref<{ height: string; transform: string }>({
  height: "0px",
  transform: "translateY(0px)",
});
const curationTab = ref("ai-summary");
const curationTabs = [
  { key: "ai-summary", label: "AI가 분석한 연구 핵심" },
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

// UI
const chatOpen = ref(false);
const citationModal = ref(false);
const toast = ref("");

function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

async function fetchPaper() {
  loading.value = true;
  try {
    const data = await $fetch<any>(`${config.public.apiBase}/books/${paperId}`);
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
    const data = await $fetch<any>(
      `${config.public.apiBase}/papers/${paperId}/related`,
    );
    relatedItems.value = data?.results || [];
  } catch {
    /* silent */
  } finally {
    relatedLoading.value = false;
  }
  // 로드 완료 후 모든 연관 논문 유사성 이유 동시 스트리밍
  relatedItems.value.forEach((rel) => streamRelatedReason(rel.book_id));
}

async function streamPaperReason() {
  const query = (route.query.q as string) || "";
  if (!query) {
    summaryText.value = paper.value?.introduction || "";
    return;
  }
  summaryText.value = "";
  summaryLoading.value = true;
  try {
    const resp = await fetch(`${config.public.apiBase}/papers/reason/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paper_id: paperId, query }),
    });
    await readSSE(resp, (json) => {
      if (json.text) summaryText.value += json.text;
    });
  } catch {
    /* silent */
  } finally {
    summaryLoading.value = false;
  }
}

async function streamRelatedReason(relatedId: string) {
  relatedReasonLoading.value = new Set([
    ...relatedReasonLoading.value,
    relatedId,
  ]);
  try {
    const resp = await fetch(
      `${config.public.apiBase}/papers/related-reason/stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_id: paperId, related_id: relatedId }),
      },
    );
    await readSSE(resp, (json) => {
      if (json.text) {
        relatedReasons.value = {
          ...relatedReasons.value,
          [relatedId]: (relatedReasons.value[relatedId] || "") + json.text,
        };
      }
    });
  } catch {
    /* silent */
  } finally {
    const next = new Set(relatedReasonLoading.value);
    next.delete(relatedId);
    relatedReasonLoading.value = next;
  }
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

onMounted(async () => {
  await fetchPaper();
  streamPaperReason();
  fetchRelated();
  nextTick(() => updateVtabSlider());
});
</script>
