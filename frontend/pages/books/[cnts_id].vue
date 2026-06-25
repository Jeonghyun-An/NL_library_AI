<template>
  <div class="page-wrap">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="bd-main">
      <!-- 로딩 -->
      <div v-if="pageLoading" class="bd-page-loading">
        <div class="sk-spinner" />
        <p>도서 정보를 불러오는 중...</p>
      </div>

      <!-- 에러 -->
      <div v-else-if="pageError" class="bd-page-error">
        <p>{{ pageError }}</p>
        <button class="sk-btn-outline" @click="navigateTo('/')">홈으로</button>
      </div>

      <template v-else-if="book">
        <!-- 뒤로가기 -->
        <button class="bd-back" @click="$router.back()">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
          검색 목록 돌아가기
        </button>

        <!-- ── 도서 헤더 ──────────────────────────────────── -->
        <div class="bd-header-card">
          <div class="bd-cover">
            <BookCover :book-id="cnts_id" size="large" />
          </div>
          <div class="bd-meta">
            <div class="bd-chips-row">
              <span v-if="matchScore" class="sk-match-badge"
                >정합성 {{ matchScore }}%</span
              >
              <span v-for="tag in themes" :key="tag" class="sk-hashtag"
                >#{{ tag }}</span
              >
              <span class="bd-bookmark-btn" title="저장">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                </svg>
              </span>
            </div>
            <h1 class="bd-title">{{ book.title }}</h1>
            <p class="bd-sub">
              <span v-if="book.material_type">{{ book.material_type }}</span>
              <template v-if="book.personal_author || book.corporate_author">
                <span class="bd-dot">·</span>
                <span
                  >{{
                    book.personal_author || book.corporate_author
                  }}
                  저자(글)</span
                >
              </template>
              <template v-if="book.pub_date">
                <span class="bd-dot">·</span>
                <span>{{ book.pub_date.slice(0, 4) }}년</span>
              </template>
              <template v-if="book.publisher">
                <span class="bd-dot">·</span>
                <span>{{ book.publisher }}</span>
              </template>
              <template v-if="book.vol_issue">
                <span class="bd-dot">·</span>
                <span>{{ book.vol_issue }}</span>
              </template>
            </p>
            <div class="bd-actions">
              <button
                class="sk-btn-outline"
                @click="showToast('대출 신청 기능은 준비 중입니다.')"
              >
                대출신청
              </button>
              <button class="sk-btn-outline" @click="pdfOpen = true">
                원문 보기
              </button>
              <button class="sk-btn-primary" @click="chatOpen = !chatOpen">
                + 이 책과 대화하기
              </button>
            </div>
          </div>
        </div>

        <!-- BookChat (inline) -->
        <BookChat
          v-show="chatOpen"
          :cnts-id="cnts_id"
          @close="chatOpen = false"
        />

        <!-- ── AI 큐레이션 ─────────────────────────────────── -->
        <section class="bd-section">
          <h2 class="bd-section-title">AI 큐레이션</h2>
          <div class="bd-curation-panel">
            <!-- 탭 -->
            <div class="bd-tab-list">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                :class="['bd-tab', activeTab === tab.key && 'active']"
                @click="activeTab = tab.key"
              >
                {{ tab.label }}
              </button>
            </div>
            <!-- 콘텐츠 -->
            <div class="bd-tab-content">
              <!-- 추천하는 이유 -->
              <div v-if="activeTab === 'reason'" class="bd-tab-pane">
                <div v-if="reasonLoading && !reasonText" class="bd-streaming">
                  <div
                    class="sk-spinner"
                    style="width: 18px; height: 18px; border-width: 2px"
                  />
                  추천 이유 생성 중...
                </div>
                <div
                  v-else-if="reasonText"
                  class="bd-prose"
                  v-html="renderedReason"
                />
                <p v-else class="bd-empty">
                  추천 이유 정보를 불러올 수 없습니다.
                </p>
              </div>
              <!-- 줄거리 -->
              <div v-if="activeTab === 'plot'" class="bd-tab-pane">
                <p v-if="book.plot" class="bd-prose-plain">{{ book.plot }}</p>
                <p v-else-if="book.summary" class="bd-prose-plain">
                  {{ book.summary }}
                </p>
                <p v-else class="bd-empty">줄거리 정보가 없습니다.</p>
              </div>
              <!-- 책 소개 -->
              <div v-if="activeTab === 'intro'" class="bd-tab-pane">
                <p v-if="book.introduction" class="bd-prose-plain">
                  {{ book.introduction }}
                </p>
                <p v-else class="bd-empty">소개 정보가 없습니다.</p>
              </div>
              <!-- 책을 읽고 난 후 -->
              <div v-if="activeTab === 'effect'" class="bd-tab-pane">
                <p v-if="book.read_effect" class="bd-prose-plain">
                  {{ book.read_effect }}
                </p>
                <p v-else class="bd-empty">독후 효과 정보가 없습니다.</p>
              </div>
            </div>
          </div>
        </section>

        <!-- ── 상세 정보 ──────────────────────────────────── -->
        <section class="bd-section">
          <h2 class="bd-section-title">상세 정보</h2>
          <table class="bd-info-table">
            <tbody>
              <tr>
                <th>표제/저자사항</th>
                <td>{{ book.title_responsibility || book.title }}</td>
                <th>발행사항</th>
                <td>
                  {{
                    [book.pub_place, book.publisher, book.pub_date]
                      .filter(Boolean)
                      .join(", ") || "-"
                  }}
                </td>
              </tr>
              <tr>
                <th>형태사항</th>
                <td>{{ book.extent || "-" }}</td>
                <th>총서사항</th>
                <td>{{ book.series_title || "-" }}</td>
              </tr>
              <tr>
                <th>표준번호</th>
                <td>{{ book.isbn || book.uci || "-" }}</td>
                <th>분류기호</th>
                <td>
                  {{ [book.kdc, book.ddc].filter(Boolean).join(" → ") || "-" }}
                </td>
              </tr>
              <tr>
                <th>주제명</th>
                <td>{{ book.subject || book.keyword || "-" }}</td>
                <th>언어</th>
                <td>{{ book.language || "Korean" }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- ── AI 연관 도서 추천 ─────────────────────────── -->
        <section class="bd-section">
          <h2 class="bd-section-title">AI 연관 도서 추천</h2>
          <div class="bd-related-layout">
            <!-- 목록 -->
            <div class="bd-related-list">
              <div v-if="relatedLoading" class="bd-related-loading">
                <div
                  class="sk-spinner"
                  style="width: 18px; height: 18px; border-width: 2px"
                />
              </div>
              <div
                v-else-if="!relatedBooks.length"
                class="bd-empty"
                style="padding: 16px"
              >
                연관 도서 정보가 없습니다.
              </div>
              <div
                v-for="rel in relatedBooks"
                :key="rel.book_id"
                :class="[
                  'bd-related-item',
                  selectedRelated?.book_id === rel.book_id && 'selected',
                ]"
                @click="selectedRelated = rel"
              >
                <BookCover :book-id="rel.book_id" class="bd-related-thumb" />
                <div class="bd-related-item-text">
                  <span class="bd-related-title">{{
                    rel.book_info?.title || rel.book_id
                  }}</span>
                  <span class="bd-related-score"
                    >정합성 {{ Math.round((rel.best_score || 0) * 100) }}%</span
                  >
                </div>
              </div>
            </div>

            <!-- 우측 미리보기 -->
            <div class="bd-related-preview">
              <template v-if="selectedRelated">
                <div class="bd-preview-card">
                  <div class="bd-preview-cover-wrap">
                    <BookCover
                      :book-id="selectedRelated.book_id"
                      size="large"
                    />
                  </div>
                  <div class="bd-preview-info">
                    <div class="bd-chips-row">
                      <span class="sk-match-badge"
                        >정합성
                        {{
                          Math.round((selectedRelated.best_score || 0) * 100)
                        }}%</span
                      >
                      <template
                        v-for="tag in parseThemes(
                          selectedRelated.book_info?.themes,
                        )"
                        :key="tag"
                      >
                        <span class="sk-hashtag">#{{ tag }}</span>
                      </template>
                    </div>
                    <p class="bd-preview-sub">
                      <span v-if="selectedRelated.book_info?.material_type">{{
                        selectedRelated.book_info.material_type
                      }}</span>
                      <span v-if="selectedRelated.book_info?.personal_author">
                        · {{ selectedRelated.book_info.personal_author }}
                      </span>
                      <span v-if="selectedRelated.book_info?.pub_date">
                        · {{ selectedRelated.book_info.pub_date.slice(0, 4) }}년
                      </span>
                      <span v-if="selectedRelated.book_info?.publisher">
                        · {{ selectedRelated.book_info.publisher }}
                      </span>
                    </p>
                    <h3 class="bd-preview-title">
                      {{ selectedRelated.book_info?.title }}
                    </h3>
                    <p
                      v-if="
                        selectedRelated.book_info?.plot ||
                        selectedRelated.book_info?.summary
                      "
                      class="bd-preview-text"
                    >
                      {{
                        (
                          selectedRelated.book_info.plot ||
                          selectedRelated.book_info.summary ||
                          ""
                        ).slice(0, 200)
                      }}{{
                        (
                          selectedRelated.book_info.plot ||
                          selectedRelated.book_info.summary ||
                          ""
                        ).length > 200
                          ? "..."
                          : ""
                      }}
                    </p>
                    <button
                      class="sk-btn-primary bd-preview-btn"
                      @click="
                        navigateTo(
                          `/books/${selectedRelated.book_id}?q=${encodeURIComponent(searchQuery)}`,
                        )
                      "
                    >
                      상세 보기
                    </button>
                  </div>
                </div>
              </template>
              <div v-else class="bd-preview-hint">
                <svg
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#d0c8ff"
                  stroke-width="1.5"
                >
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path
                    d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"
                  />
                </svg>
                <p>추천도서를 클릭해주세요</p>
              </div>
            </div>
          </div>
        </section>
      </template>
    </main>

    <!-- PDF 뷰어 -->
    <PdfViewer
      v-if="pdfOpen"
      :cnts-id="cnts_id"
      :title="book?.title"
      @close="pdfOpen = false"
    />

    <!-- 토스트 -->
    <Teleport to="body">
      <Transition name="sk-toast">
        <div v-if="toast" class="sk-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import type { BookInfo } from "~/types/search";

// ── 라우트 ─────────────────────────────────────────────────
const route = useRoute();
const cnts_id = route.params.cnts_id as string;
const searchQuery = (route.query.q as string) || "";
const matchScoreParam = Number(route.query.score) || 0;

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

// ── 탭 정의 ────────────────────────────────────────────────
const tabs = [
  { key: "reason", label: "추천하는 이유" },
  { key: "plot", label: "줄거리" },
  { key: "intro", label: "책 소개" },
  { key: "effect", label: "책을 읽고 난 후" },
];
const activeTab = ref("reason");

// ── 도서 데이터 ────────────────────────────────────────────
const book = ref<BookInfo | null>(null);
const pageLoading = ref(true);
const pageError = ref("");

const matchScore = computed(() =>
  matchScoreParam ? Math.round(matchScoreParam * 100) : 0,
);
const themes = computed(() => parseThemes(book.value?.themes));

// ── AI 큐레이션 ────────────────────────────────────────────
const reasonText = ref("");
const reasonLoading = ref(false);
const renderedReason = computed(() =>
  reasonText.value ? (marked.parse(reasonText.value) as string) : "",
);

// ── 연관 도서 ──────────────────────────────────────────────
const relatedBooks = ref<any[]>([]);
const relatedLoading = ref(false);
const selectedRelated = ref<any>(null);

// ── UI 상태 ────────────────────────────────────────────────
const chatOpen = ref(false);
const pdfOpen = ref(false);
const toast = ref("");

// ── 초기화 ─────────────────────────────────────────────────
onMounted(async () => {
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
      relatedBooks.value = (data.books as any[])
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
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 3);
}

function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
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

<style scoped>
/* ── 레이아웃 ─────────────────────────────────────────────── */
.page-wrap {
  display: flex;
  height: 100vh;
  background: var(--bg);
  overflow: hidden;
}
.bd-main {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px 32px;
  max-width: 900px;
}

/* ── 로딩 / 에러 ─────────────────────────────────────────── */
.bd-page-loading,
.bd-page-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px;
  color: #888;
}
.sk-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ── 뒤로가기 ────────────────────────────────────────────── */
.bd-back {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  color: #888;
  padding: 0;
}
.bd-back:hover {
  color: var(--ink);
}

/* ── 도서 헤더 ───────────────────────────────────────────── */
.bd-header-card {
  display: flex;
  gap: 20px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px;
}
.bd-cover {
  width: 100px;
  min-width: 100px;
  height: 140px;
  border-radius: 8px;
  overflow: hidden;
}
.bd-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bd-chips-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.bd-bookmark-btn {
  margin-left: auto;
  color: #ccc;
  cursor: pointer;
}
.bd-bookmark-btn:hover {
  color: var(--accent);
}
.bd-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
}
.bd-sub {
  font-size: 12px;
  color: #888;
  margin: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}
.bd-dot {
  margin: 0 2px;
}
.bd-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

/* ── 섹션 공통 ───────────────────────────────────────────── */
.bd-section {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.bd-section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
  margin: 0;
}

/* ── AI 큐레이션 ─────────────────────────────────────────── */
.bd-curation-panel {
  display: flex;
}
.bd-tab-list {
  display: flex;
  flex-direction: column;
  min-width: 130px;
  border-right: 1px solid var(--line);
  padding: 12px 8px;
  gap: 4px;
}
.bd-tab {
  padding: 9px 14px;
  border-radius: var(--radius-sm);
  border: none;
  background: none;
  color: #777;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.bd-tab:hover {
  background: var(--bg);
}
.bd-tab.active {
  background: var(--accent);
  color: white;
  font-weight: 600;
}
.bd-tab-content {
  flex: 1;
  overflow: hidden;
}
.bd-tab-pane {
  padding: 20px;
  min-height: 140px;
  max-height: 320px;
  overflow-y: auto;
}
.bd-streaming {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--accent);
  font-size: 13px;
}
.bd-prose {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.85;
}
.bd-prose :deep(h2) {
  font-size: 14px;
  font-weight: 700;
  margin: 14px 0 6px;
}
.bd-prose :deep(p) {
  margin: 0 0 10px;
}
.bd-prose :deep(ul) {
  padding-left: 16px;
  margin: 0 0 10px;
}
.bd-prose-plain {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.85;
  margin: 0;
  white-space: pre-wrap;
}
.bd-empty {
  font-size: 13px;
  color: #bbb;
  margin: 0;
}

/* ── 상세 정보 테이블 ────────────────────────────────────── */
.bd-info-table {
  width: 100%;
  border-collapse: collapse;
}
.bd-info-table th,
.bd-info-table td {
  padding: 10px 16px;
  font-size: 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
.bd-info-table th {
  color: #888;
  font-weight: 500;
  white-space: nowrap;
  width: 110px;
  background: var(--bg);
}
.bd-info-table td {
  color: var(--ink);
}
.bd-info-table tr:last-child th,
.bd-info-table tr:last-child td {
  border-bottom: none;
}

/* ── AI 연관 도서 추천 ───────────────────────────────────── */
.bd-related-layout {
  display: flex;
}
.bd-related-list {
  width: 240px;
  min-width: 240px;
  border-right: 1px solid var(--line);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bd-related-loading {
  display: flex;
  justify-content: center;
  padding: 20px;
}
.bd-related-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.1s;
}
.bd-related-item:hover {
  background: var(--bg);
}
.bd-related-item.selected {
  background: var(--lilac);
  border-color: var(--accent);
}
.bd-related-thumb {
  width: 36px;
  min-width: 36px;
  height: 50px;
  border-radius: 4px;
  overflow: hidden;
}
.bd-related-item-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow: hidden;
}
.bd-related-title {
  font-size: 12px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}
.bd-related-score {
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
}

.bd-related-preview {
  flex: 1;
  padding: 20px;
  display: flex;
  align-items: flex-start;
}
.bd-preview-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 20px;
}
.bd-preview-hint p {
  font-size: 13px;
  color: #aaa;
}
.bd-preview-card {
  display: flex;
  gap: 16px;
  width: 100%;
}
.bd-preview-cover-wrap {
  width: 90px;
  min-width: 90px;
  height: 126px;
  border-radius: 8px;
  overflow: hidden;
}
.bd-preview-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.bd-preview-sub {
  font-size: 12px;
  color: #888;
  margin: 0;
}
.bd-preview-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
}
.bd-preview-text {
  font-size: 12px;
  color: #666;
  line-height: 1.7;
  margin: 0;
}
.bd-preview-btn {
  margin-top: auto;
  align-self: flex-start;
}

/* ── 공용 버튼 ───────────────────────────────────────────── */
.sk-btn-outline {
  padding: 7px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink);
  font-size: 12px;
  cursor: pointer;
}
.sk-btn-outline:hover {
  background: var(--bg);
}
.sk-btn-primary {
  padding: 7px 14px;
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: white;
  font-size: 12px;
  cursor: pointer;
}
.sk-btn-primary:hover {
  background: var(--accent-deep);
}
.sk-match-badge {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  background: var(--lilac);
  padding: 2px 8px;
  border-radius: 20px;
}
.sk-hashtag {
  font-size: 11px;
  color: var(--accent);
  background: var(--lilac);
  padding: 2px 8px;
  border-radius: 20px;
}

/* ── 토스트 ──────────────────────────────────────────────── */
.sk-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(18, 19, 26, 0.9);
  color: white;
  padding: 10px 20px;
  border-radius: 100px;
  font-size: 13px;
  pointer-events: none;
  z-index: 2000;
}
.sk-toast-enter-active,
.sk-toast-leave-active {
  transition:
    opacity 0.3s,
    transform 0.3s;
}
.sk-toast-enter-from,
.sk-toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}
</style>
