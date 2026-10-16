<!-- frontend/pages/dev/error-states.vue -->
<!-- 오류 화면 모음(개발용, /dev/error-states) — 후배 디자이너가 오류·빈 상태 표시를 실물로 보며 디자인하는 한 페이지.
     메뉴에 잇지 않고 검색엔진에도 싣지 않는다(robots noindex,nofollow).
     표시는 모두 실제 컴포넌트다(SkxErrorPage·SkxErrorState·SkxInlineError·SkxConnectionBanner·SkxCharCount) — 복제 마크업이 없어
     style_skovix.css 의 '[S] 공통 오류·빈 상태' 구역을 고치면 이 페이지와 실제 화면이 함께 바뀐다.
     문구도 여기 새로 짓지 않는다 — 실제 규칙(errorKind·apiErrorMessage·researchErrorMessage)에 본보기 오류를 넣어 만든 글과
     상수(ERROR_PAGE_TEXT·CONNECTION_HINTS·AI_SUMMARY_FAILED·charLimitMessage·RESEARCH_STATE_TEXT)를 그대로 보여 문구가 바뀌면 같이 바뀐다.
     화면마다 다른 대체 문구('검색하지 못했어요' 등)와 실제 화면에 아직 없는 빈 연구 안내만 본보기로 적는다.
     ③ 딥리서치 상태는 후배 시안의 네 변형(실패·취소·찾을 수 없음·결과 없음)을 실제 동작(pages/research/[id].vue·api/research.py)에 맞춘 것 —
     항목마다 '시안 대비'에 바꾼 점을 적는다.
     [다시 시도] 는 누르면 잠깐 재시도 중 모양으로 바뀌었다 돌아오고, [다시 연결] 은 다시 연결하는 중 → 붙음(띠가 사라짐) → 다시 끊김으로
     돈다(요청은 보내지 않는다).
     이 페이지 자체의 틀(.dev-*)은 아래 scoped 스타일이고 디자인 대상이 아니다 -->
<template>
  <div class="skx-app">
    <main class="dev-gallery">
      <header class="dev-gallery__head">
        <div class="dev-gallery__intro">
          <h1 class="dev-gallery__title">오류 화면 모음</h1>
          <p class="dev-gallery__lead">이 페이지의 표시는 모두 실제 컴포넌트입니다.</p>
          <p class="dev-gallery__lead">
            디자인은 <code>assets/css/style_skovix.css</code> 의 <code>[S] 공통 오류·빈 상태</code> 구역 클래스에 입히면
            실제 화면 전체에 반영됩니다.
          </p>
          <p class="dev-gallery__lead">
            지금 이 컴포넌트를 실제로 쓰는 화면은 전역 오류 화면(①)뿐입니다. 각 항목의 ‘생기는 곳’은 같은 상황이 생기는 실제 화면이고,
            차례로 이 컴포넌트로 옮길 자리입니다.
          </p>
        </div>
        <div class="dev-gallery__theme">
          <p :id="themeLabelId" class="dev-gallery__theme-label">테마</p>
          <div class="skx-set__seg" role="group" :aria-labelledby="themeLabelId">
            <button
              v-for="name in THEMES"
              :key="name"
              type="button"
              :class="['skx-set__opt', theme === name && 'is-active']"
              :aria-pressed="theme === name"
              @click="setTheme(name)"
            >
              {{ THEME_LABELS[name] }}
            </button>
          </div>
        </div>
      </header>

      <!-- ① 전체 화면 오류 페이지 — error.vue 가 그리는 SkxErrorPage 를 16:10 화면 크기로 그려 액자 폭에 맞춰 줄인다 -->
      <section class="dev-gallery__section" aria-labelledby="dev-sec-page">
        <div class="dev-gallery__section-head">
          <h2 id="dev-sec-page" class="dev-gallery__h2">① 전체 화면 오류 페이지</h2>
          <a class="dev-gallery__link" :href="MISSING_PATH" target="_blank" rel="noopener">
            실제 404 화면 열기<span class="skx-sr-only"> (새 탭)</span>
          </a>
        </div>
        <p class="dev-gallery__note">
          SkxErrorPage(preview) — {{ SCREEN_W }}×{{ SCREEN_H }} 화면을 액자 폭에 맞춰 줄였습니다. 액자 안 버튼은 눌러도 이동하지 않습니다.
          액자 속 배경 띠는 실제 창 크기(vmax·vh) 기준이라 줄인 액자에서는 굵게 보입니다 — 실제 404 화면(오른쪽 위 링크)에서 확인해 주세요.
        </p>
        <div class="dev-gallery__grid dev-gallery__grid--wide">
          <article v-for="p in PAGE_SAMPLES" :key="p.status" class="dev-item">
            <h3 class="dev-item__name">{{ p.name }}</h3>
            <div ref="frameEls" class="dev-frame" :style="frameStyle">
              <div class="dev-frame__screen" :style="screenStyle">
                <SkxErrorPage :status="p.status" preview />
              </div>
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ p.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in p.hooks" :key="h">{{ h }}</code></dd>
              <dt>문구</dt>
              <dd><span v-for="t in p.texts" :key="t">‘{{ t }}’</span></dd>
            </dl>
          </article>
        </div>
      </section>

      <!-- ② 섹션 상태 블록 — kind 별 / ③ 딥리서치 상태 — 후배 시안 네 변형을 실제 동작에 맞춰. 같은 틀을 섹션 목록으로 돈다 -->
      <section v-for="g in STATE_SECTIONS" :key="g.id" class="dev-gallery__section" :aria-labelledby="g.id">
        <h2 :id="g.id" class="dev-gallery__h2">{{ g.title }}</h2>
        <p class="dev-gallery__note">{{ g.note }}</p>
        <div class="dev-gallery__grid">
          <article v-for="s in g.samples" :key="s.id" class="dev-item">
            <h3 class="dev-item__name">{{ s.name }}</h3>
            <div class="dev-item__stage">
              <SkxErrorState
                :kind="s.kind"
                :title="s.title"
                :message="s.message"
                :compact="s.compact"
                :retry-label="s.retryLabel"
                :busy="s.busy || !!retrying[s.id]"
                :on-retry="s.retry ? () => simulateRetry(s.id) : undefined"
              >
                <template v-if="s.action" #default>
                  <a class="skx-state__action" :href="s.action.href" @click.prevent>{{ s.action.label }}</a>
                </template>
              </SkxErrorState>
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ s.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in s.hooks" :key="h">{{ h }}</code></dd>
              <dt>문구</dt>
              <dd><span v-for="t in s.texts" :key="t">‘{{ t }}’</span></dd>
              <template v-if="s.diff">
                <dt>시안 대비</dt>
                <dd>{{ s.diff }}</dd>
              </template>
            </dl>
          </article>
        </div>
      </section>

      <!-- ④ 줄 단위 안내 — 쓰이는 자리째로 -->
      <section class="dev-gallery__section" aria-labelledby="dev-sec-inline">
        <h2 id="dev-sec-inline" class="dev-gallery__h2">④ 줄 단위 안내 (SkxInlineError)</h2>
        <div class="dev-gallery__grid dev-gallery__grid--wide">
          <article class="dev-item">
            <h3 class="dev-item__name">{{ INLINE_SAMPLES.basic.name }}</h3>
            <div class="dev-item__stage">
              <div class="skx-search">
                <div class="skx-search__box">
                  <span class="skx-search__glow" aria-hidden="true"></span>
                  <label class="skx-search__field">
                    <span class="skx-sr-only">본보기 검색어</span>
                    <textarea v-model="sampleQuery" class="skx-search__input"></textarea>
                  </label>
                  <div class="skx-search__actions">
                    <button type="button" class="skx-send" aria-label="검색(본보기 — 보내지 않습니다)" :aria-disabled="!sampleQuery.trim()">
                      <img src="/img/ico-send-up.svg" alt="" />
                    </button>
                  </div>
                </div>
                <SkxInlineError :message="INLINE_SAMPLES.basic.texts[0]!" />
              </div>
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ INLINE_SAMPLES.basic.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in INLINE_SAMPLES.basic.hooks" :key="h">{{ h }}</code></dd>
              <dt>문구</dt>
              <dd><span v-for="t in INLINE_SAMPLES.basic.texts" :key="t">‘{{ t }}’</span></dd>
            </dl>
          </article>

          <article class="dev-item">
            <h3 class="dev-item__name">{{ INLINE_SAMPLES.retry.name }}</h3>
            <div class="dev-item__stage">
              <div class="skx-pai-section">
                <p class="skx-pai-section__text">{{ AI_PARTIAL_TEXT }}</p>
              </div>
              <SkxInlineError
                :message="INLINE_SAMPLES.retry.texts[0]!"
                :busy="!!retrying.inlineRetry"
                @retry="simulateRetry('inlineRetry')"
              />
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ INLINE_SAMPLES.retry.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in INLINE_SAMPLES.retry.hooks" :key="h">{{ h }}</code></dd>
              <dt>문구</dt>
              <dd><span v-for="t in INLINE_SAMPLES.retry.texts" :key="t">‘{{ t }}’</span></dd>
            </dl>
          </article>

          <article class="dev-item">
            <h3 class="dev-item__name">{{ INLINE_SAMPLES.busy.name }}</h3>
            <div class="dev-item__stage">
              <SkxInlineError :message="INLINE_SAMPLES.busy.texts[0]!" busy :on-retry="ignoreRetry" />
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ INLINE_SAMPLES.busy.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in INLINE_SAMPLES.busy.hooks" :key="h">{{ h }}</code></dd>
              <dt>문구</dt>
              <dd><span v-for="t in INLINE_SAMPLES.busy.texts" :key="t">‘{{ t }}’</span></dd>
            </dl>
          </article>
        </div>
      </section>

      <!-- ⑤ 연결 끊김 띠 — 화면 위쪽에 붙는 모양을 흐린 본문 자리와 함께 -->
      <section class="dev-gallery__section" aria-labelledby="dev-sec-conn">
        <h2 id="dev-sec-conn" class="dev-gallery__h2">⑤ 연결 끊김 띠 (SkxConnectionBanner)</h2>
        <p class="dev-gallery__note">
          쓰는 화면은 띠를 늘 그려 두고 state 만 바꿉니다(connected 면 보이는 것 없이 빈 알림 영역만) — 끊길 때 새로 생긴 띠는 화면 낭독기가 놓칩니다.
          [다시 연결]을 누르면 버튼이 사라지며 초점이 띠로 옮겨 갑니다.
        </p>
        <div class="dev-gallery__grid dev-gallery__grid--wide">
          <article v-for="c in CONN_SAMPLES" :key="c.id" class="dev-item">
            <h3 class="dev-item__name">{{ c.name }}</h3>
            <div class="dev-item__stage">
              <SkxConnectionBanner
                :state="connState[c.id]"
                :on-retry="c.id === 'lost' ? () => simulateReconnect(c.id) : undefined"
              />
              <div class="dev-ghost" aria-hidden="true"><span></span><span></span><span></span></div>
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ c.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in c.hooks" :key="h">{{ h }}</code></dd>
              <dt>문구</dt>
              <dd><span v-for="t in c.texts" :key="t">‘{{ t }}’</span></dd>
            </dl>
          </article>
        </div>
      </section>

      <!-- ⑥ 글자 수 — 세 상태 + 직접 쳐 보는 입력창 -->
      <section class="dev-gallery__section" aria-labelledby="dev-sec-count">
        <h2 id="dev-sec-count" class="dev-gallery__h2">⑥ 글자 수 (SkxCharCount)</h2>
        <div class="dev-gallery__grid">
          <article v-for="n in COUNT_SAMPLES" :key="n.length" class="dev-item">
            <h3 class="dev-item__name">{{ n.name }}</h3>
            <div class="dev-item__stage">
              <SkxCharCount :length="n.length" :max="CHAR_MAX" />
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ n.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in n.hooks" :key="h">{{ h }}</code></dd>
              <dt>문구</dt>
              <dd><span v-for="t in n.texts" :key="t">‘{{ t }}’</span></dd>
            </dl>
          </article>

          <article class="dev-item dev-item--span">
            <h3 class="dev-item__name">직접 입력해 보기</h3>
            <div class="dev-item__stage">
              <label :for="typeId" class="dev-item__label">본보기 연구 질문 (최대 {{ CHAR_MAX }}자 — maxlength)</label>
              <textarea
                :id="typeId"
                v-model="typed"
                class="wk-edit__input"
                rows="4"
                :maxlength="CHAR_MAX"
                :aria-describedby="countId"
              ></textarea>
              <SkxCharCount :id="countId" :length="typed.length" :max="CHAR_MAX" />
              <div class="dev-item__tools">
                <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="fillTo(COUNT_NEAR_DEMO)">
                  {{ COUNT_NEAR_DEMO }}자로 맞추기
                </button>
                <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="fillTo(CHAR_MAX)">
                  {{ CHAR_MAX }}자로 맞추기
                </button>
                <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="typed = ''">비우기</button>
              </div>
            </div>
            <p class="dev-gallery__note">
              입력창은 aria-describedby 로 글자 수를 가리킵니다. 한도에 닿으면 안내 글이 화면 낭독기에도 읽힙니다(aria-live="polite").
            </p>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useTheme } from "~/composables/useTheme";
import { AI_SUMMARY_FAILED } from "~/utils/aiStream";
import {
  CONNECTION_HINTS,
  CONNECTION_RETRY_LABEL,
  ERROR_PAGE_TEXT,
  apiErrorMessage,
  charCountState,
  charLimitMessage,
  errorKind,
  type ConnectionState,
  type ErrorStateKind,
} from "~/utils/apiErrors";
import { deepResearchStartRoute } from "~/utils/landingStart";
import { RESEARCH_STATE_TEXT, researchErrorMessage, researchRetryLabel } from "~/utils/researchErrors";
import { THEMES, THEME_LABELS } from "~/utils/theme";

useHead({
  title: "오류 화면 모음 — SKOVIX",
  meta: [{ name: "robots", content: "noindex,nofollow" }],
});

const { theme, setTheme } = useTheme();
const uid = useId();
const themeLabelId = `dev-theme-${uid}`;
const typeId = `dev-type-${uid}`;
const countId = `dev-count-${uid}`;

/** 항목 설명 — 생기는 곳(같은 상황이 생기는 실제 화면 — 대부분 아직 이 컴포넌트를 쓰지 않는다)·디자인 훅(클래스·속성)·문구 원문 */
interface SpecInfo {
  name: string;
  uses: string[];
  hooks: string[];
  texts: string[];
}

/** 컴포넌트 기본 버튼 글(SkxErrorState·SkxInlineError 의 retryLabel 기본값) — 설명 줄에만 쓴다 */
const RETRY_TEXT = "다시 시도";
/** 사이드바 [연구 시작하기]가 여는 주소 — 첫 화면의 논문 패널 + DeepResearch 모드(utils/landingStart) */
const START_RESEARCH_HREF = (() => {
  const route = deepResearchStartRoute();
  return `${route.path}?${new URLSearchParams(route.query).toString()}`;
})();

// 실제 규칙(errorKind·apiErrorMessage·researchErrorMessage)에 넣어 볼 본보기 오류 — 문구를 여기 적지 않고 규칙이 만든 글을 보인다.
// network 는 응답 없이 끝난 요청(ofetch FetchError — 상태 없음), 나머지는 상태 코드만 든 응답, tooLong 은 FastAPI 422 검증 실패(검색어 500자 초과)
const SAMPLE = {
  network: { name: "FetchError" },
  timeout: { status: 504 },
  busy: { status: 503 },
  server: { status: 500 },
  notFound: { status: 404 },
  // 백엔드 오류 code — 서버 detail(옛 말투) 대신 CODE_MESSAGES 의 문구를 쓴다
  searchDown: { status: 503, data: { detail: "검색 서버가 잠시 응답하지 않습니다. 잠시 뒤 다시 시도하세요", code: "search_unavailable" } },
  tooLong: { status: 422, data: { detail: [{ type: "string_too_long", ctx: { max_length: 500 } }] } },
} as const;

/** 상태 블록의 설명 줄 — 제목이 이미 '무엇을 못 했는지'라 규칙이 붙이는 이유(ERROR_HINTS)만 둔다(대체 문구를 비워 넘긴다) */
const reasonOf = (err: unknown) => apiErrorMessage(err, "");

// ── ① 전체 화면 오류 페이지 ──

/** 액자 안 화면의 실제 크기(16:10) — 이 크기로 그려 액자 폭에 맞춰 transform: scale 로 줄인다 */
const SCREEN_W = 1024;
const SCREEN_H = 640;
/** 없는 주소 — 새 탭에서 열면 서버가 404 로 error.vue(SkxErrorPage)를 그린다 */
const MISSING_PATH = "/dev/없는-주소";

const PAGE_SAMPLES: (SpecInfo & { status: number })[] = [
  {
    status: 404,
    name: "404 — 없는 주소",
    uses: ["없는 주소로 들어옴(옛 링크·주소 오타)", "지워진 화면의 주소"],
    hooks: [".skx-error-page", "[data-status]", ".skx-error-page__logo", ".skx-error-page .skx-state", ".skx-state--notFound"],
    texts: [ERROR_PAGE_TEXT.notFound.title, ERROR_PAGE_TEXT.notFound.message, ERROR_PAGE_TEXT.home],
  },
  {
    status: 500,
    name: "치명 오류 — 화면을 그리지 못함",
    uses: ["화면을 그리다 난 오류", "서버 렌더 실패(500)"],
    hooks: [".skx-error-page", "[data-status]", ".skx-error-page__main", '.skx-state[data-tone="error"]', ".skx-state__retry"],
    texts: [ERROR_PAGE_TEXT.fatal.title, ERROR_PAGE_TEXT.fatal.message, RETRY_TEXT, ERROR_PAGE_TEXT.home],
  },
];

const frameEls = ref<HTMLElement[]>([]);
const frameScale = ref(0.5);
const frameStyle = { aspectRatio: `${SCREEN_W} / ${SCREEN_H}` };
const screenStyle = computed(() => ({
  width: `${SCREEN_W}px`,
  height: `${SCREEN_H}px`,
  transform: `scale(${frameScale.value})`,
}));
let frameObserver: ResizeObserver | null = null;

// 두 액자는 같은 격자 칸이라 폭이 같다 — 첫 액자만 재어 둘 다 같은 배율로 줄인다
onMounted(() => {
  const first = frameEls.value[0];
  if (!first || typeof ResizeObserver === "undefined") return;
  frameObserver = new ResizeObserver((entries) => {
    const width = entries[0]?.contentRect.width;
    if (width) frameScale.value = width / SCREEN_W;
  });
  frameObserver.observe(first);
});

// ── ② 섹션 상태 블록 · ③ 딥리서치 상태 ──

interface StateSample extends SpecInfo {
  id: string;
  kind: ErrorStateKind;
  title: string;
  message?: string;
  /** [다시 시도] 를 단다 */
  retry?: boolean;
  /** [다시 시도] 글 — 없으면 컴포넌트 기본값('다시 시도') */
  retryLabel?: string;
  /** 늘 재시도 중 */
  busy?: boolean;
  compact?: boolean;
  /** 기본 슬롯에 넣는 버튼 자리 링크(.skx-state__action — 첫 버튼이면 주 버튼 모양) */
  action?: { label: string; href: string };
  /** 후배 시안 대비 바꾼 점(③) */
  diff?: string;
}

function stateSample(s: Omit<StateSample, "texts">): StateSample {
  const retryText = s.retry ? (s.retryLabel ?? RETRY_TEXT) : undefined;
  const texts = [s.title, s.message, retryText, s.action?.label].filter((t): t is string => !!t);
  return { ...s, texts };
}

const STATE_SAMPLES: StateSample[] = [
  stateSample({
    id: "error",
    name: "일반 실패 + 다시 시도",
    kind: "error",
    title: "논문 정보를 불러오지 못했어요",
    retry: true,
    uses: ["논문 상세 — 정보 읽기 실패", "딥리서치 — 연구 불러오기 실패", "연구 작업대 — 이어간 연구 불러오기 실패"],
    hooks: [".skx-state", ".skx-state--error", '[data-tone="error"]', ".skx-state__title", ".skx-state__retry"],
  }),
  stateSample({
    id: "network",
    name: "네트워크 끊김",
    kind: errorKind(SAMPLE.network),
    title: "검색하지 못했어요",
    message: reasonOf(SAMPLE.network),
    retry: true,
    uses: ["도서·논문 검색 결과", "논문 상세", "딥리서치 화면 불러오기"],
    hooks: [".skx-state--network", ".skx-state__msg", ".skx-state__icon(아이콘 원 — 실패 갈래는 경고 삼각형)"],
  }),
  stateSample({
    id: "timeout",
    name: "시간 초과",
    kind: errorKind(SAMPLE.timeout),
    title: "검색 기록을 불러오지 못했어요",
    message: reasonOf(SAMPLE.timeout),
    retry: true,
    uses: ["상세·목록 읽기 — GET 30초 제한(useApi)", "게이트웨이 504"],
    hooks: [".skx-state--timeout", '[data-kind="timeout"]'],
  }),
  stateSample({
    id: "busy",
    name: "요청 몰림",
    kind: errorKind(SAMPLE.busy),
    title: "검색하지 못했어요",
    message: reasonOf(SAMPLE.busy),
    retry: true,
    uses: ["딥리서치 시작·승인 — 공유 대기열이 찼을 때(429)", "작업 큐에 연결하지 못함(503)"],
    hooks: [".skx-state--busy", '[data-kind="busy"]'],
  }),
  stateSample({
    id: "server",
    name: "서버 오류",
    kind: errorKind(SAMPLE.server),
    title: "논문 정보를 불러오지 못했어요",
    message: reasonOf(SAMPLE.server),
    retry: true,
    uses: ["논문 상세", "검색 결과", "연구 작업대 저장"],
    hooks: [".skx-state--server", '[data-kind="server"]'],
  }),
  stateSample({
    id: "searchDown",
    name: "서버가 알린 장애(code) — 백엔드 반영 뒤",
    kind: errorKind(SAMPLE.searchDown),
    title: "검색하지 못했어요",
    message: reasonOf(SAMPLE.searchDown),
    retry: true,
    uses: ["검색 서버(Milvus·임베딩) 장애 — 503 search_unavailable", "원문 저장소 장애 — 503 storage_unavailable", "잡지 않은 서버 예외 — 500 internal_error"],
    hooks: [".skx-state--busy", "설명 줄은 apiErrors 의 CODE_MESSAGES(서버 detail 은 쓰지 않는다)"],
  }),
  stateSample({
    id: "notFound",
    name: "찾을 수 없음 + 돌아가기",
    kind: errorKind(SAMPLE.notFound),
    title: researchErrorMessage(SAMPLE.notFound, ""),
    message: RESEARCH_STATE_TEXT.notFoundMessage,
    action: { label: RESEARCH_STATE_TEXT.backToSearch, href: "/papers" },
    uses: ["딥리서치 — 없는 연구 주소", "논문 상세 — 없는 논문 주소"],
    hooks: [".skx-state--notFound", '[data-tone="neutral"]', ".skx-state__action(슬롯 링크 — 버튼 줄의 첫 버튼이라 주 버튼 모양)"],
  }),
  stateSample({
    id: "empty",
    name: "결과 없음",
    kind: "empty",
    title: "검색 결과가 없어요",
    message: "다른 검색어로 다시 검색해 주세요.",
    uses: ["논문 검색 결과 0건", "소장자료 검색 0건", "빈 읽기 목록"],
    hooks: [".skx-state--empty", '[data-tone="neutral"]', 'role="status"'],
  }),
  stateSample({
    id: "canceled",
    name: "취소",
    kind: "canceled",
    title: RESEARCH_STATE_TEXT.canceledTitle,
    uses: ["딥리서치 — 사용자가 취소한 연구(버튼까지 갖춘 모양은 ③)"],
    hooks: [".skx-state--canceled", '[data-tone="neutral"]', 'role="status"'],
  }),
  stateSample({
    id: "retrying",
    name: "재시도 중",
    kind: errorKind(SAMPLE.network),
    title: "검색하지 못했어요",
    message: reasonOf(SAMPLE.network),
    retry: true,
    busy: true,
    uses: ["[다시 시도]를 누르고 응답을 기다리는 동안 — 모든 상태 블록"],
    hooks: ['.skx-state__retry[aria-disabled="true"]', '[aria-busy="true"]'],
  }),
  stateSample({
    id: "compact",
    name: "좁은 칸 (compact)",
    kind: "error",
    title: "원문 대목을 불러오지 못했어요",
    message: reasonOf(SAMPLE.network),
    compact: true,
    retry: true,
    uses: ["연구 작업대 — 인용의 원문 대목", "카드·옆 칸처럼 이미 틀이 있는 자리"],
    hooks: [".skx-state--compact"],
  }),
];

// 후배 시안 'DR/상태 안내'의 네 변형을 실제 동작에 맞춘 것 — 제목·버튼은 실제 화면(pages/research/[id].vue)과 같은 상수,
// 실패의 다시 시도 갈래는 api/research.py retry_research(보고서 작성 단계에서 멈춘 연구만 체크포인트로 이어 가고, 계획 단계 실패는 새 연구)
const RESEARCH_SAMPLES: StateSample[] = [
  stateSample({
    id: "researchFailed",
    name: "실패 — 보고서 작성 중 멈춤",
    kind: "error",
    title: RESEARCH_STATE_TEXT.failedTitle,
    message: "탐색에서 모은 근거는 남아 있어요.\n보고서 작성부터 다시 시작할 수 있어요.",
    retry: true,
    retryLabel: researchRetryLabel("explored"),
    uses: ["딥리서치 — 보고서를 쓰다 멈춘 연구(stage explored)"],
    hooks: [".skx-state--error", '[data-tone="error"]', ".skx-state__retry(retryLabel)"],
    diff:
      "제목은 실제 화면 문구. [문의하기]는 뺐다 — 앱에 문의 창구가 없다. [다시 시도] 글은 멈춘 단계를 따른다: 보고서 작성 중이면 '보고서 작성부터 다시 시도'(탐색 결과로 이어 감), " +
      "탐색 중이면 '다시 시도'(승인한 계획으로 탐색부터 다시), 계획 단계에서 멈췄으면 다시 시도할 수 없어 '같은 질문으로 다시 시작'(새 연구)만 둔다. " +
      "실제 화면은 설명 줄에 서버가 남긴 멈춘 까닭(last_error — 예외 원문일 수 있다)을 그대로 붙인다 — 이 컴포넌트로 옮길 때 이 설명으로 바꾼다.",
  }),
  stateSample({
    id: "researchCanceled",
    name: "취소",
    kind: "canceled",
    title: RESEARCH_STATE_TEXT.canceledTitle,
    message: "취소한 연구는 이어 갈 수 없어요.\n같은 질문으로 새 연구를 시작할 수 있어요.",
    action: { label: RESEARCH_STATE_TEXT.restart, href: "#" },
    uses: ["딥리서치 — 사용자가 취소한 연구(계획을 세우는 중·승인 대기·대기열·진행 중 어디서든)"],
    hooks: [".skx-state--canceled", '[data-tone="neutral"]', 'role="status"'],
    diff:
      "시안 제목 '연구가 중단되었어요' 대신 실제 화면 문구. [이어서 연구하기]·'중단된 지점부터 이어서 진행'은 뺐다 — 취소한 연구는 이어 갈 수 없다" +
      "(다시 시도는 실패한 연구만 받는다). [새 연구 시작]은 실제 버튼 '같은 질문으로 다시 시작'(원래 질문·탐색 방식으로 새 연구를 만든다).",
  }),
  stateSample({
    id: "researchNotFound",
    name: "찾을 수 없음",
    kind: errorKind(SAMPLE.notFound),
    title: researchErrorMessage(SAMPLE.notFound, ""),
    message: RESEARCH_STATE_TEXT.notFoundMessage,
    action: { label: RESEARCH_STATE_TEXT.backToSearch, href: "/papers" },
    uses: ["딥리서치 — 없는 연구 주소(주소 오타)"],
    hooks: [".skx-state--notFound", '[data-tone="neutral"]'],
    diff:
      "시안 제목 '연구를 불러오지 못했어요'는 불러오기 실패(네트워크·서버)와 헷갈려 실제 404 문구를 쓴다. '접근 권한이 없는 연구일 수 있어요'는 뺐다 — " +
      "연구는 주소만 알면 누구나 연다(권한 검사가 없다). 원인은 주소가 잘못된 경우다(연구를 지우는 기능은 없다 — 사이드바 전체 삭제도 기록만 지운다).",
  }),
  stateSample({
    id: "researchEmpty",
    name: "결과 없음 — 아직 연구가 없음",
    kind: "empty",
    title: "아직 진행한 연구가 없어요",
    message: "연구 시작하기를 누르면 첫 화면에서 DeepResearch로 질문할 수 있어요.",
    action: { label: "연구 시작하기", href: START_RESEARCH_HREF },
    uses: ["사이드바 DeepResearch 묶음 — 연구 기록이 하나도 없을 때(지금은 [연구 시작하기] 버튼만 있다)"],
    hooks: [".skx-state--empty", '[data-tone="neutral"]', 'role="status"'],
    diff:
      "제목은 시안 그대로. 실제로는 이 큰 빈 화면이 없다 — 사이드바 묶음이 [연구 시작하기]만 두고, 누르면 첫 화면이 논문 패널 + DeepResearch 모드로 열린다" +
      "(?start=deep-research). 연구 시작 전용 화면은 두지 않는다.",
  }),
];

const STATE_SECTIONS = [
  {
    id: "dev-sec-state",
    title: "② 섹션 상태 블록 (SkxErrorState)",
    note:
      "제목은 화면마다 다른 '무엇을 못 했는지', 설명 줄은 오류 규칙(apiErrorMessage)이 붙이는 이유입니다. 색은 아이콘 원에만 씁니다 — 실패 갈래는 경고 삼각형(위험색), " +
      "빈 결과는 문서+돋보기(청록), 찾을 수 없음은 돋보기+X(회색), 취소는 둥근 네모(포인트색). 여기 없는 kind(invalid·conflict·forbidden·unknown)는 " +
      '실패 갈래([data-tone="error"])로 같은 모양이고, .skx-state--{kind} 로 따로 꾸밀 수 있습니다. 버튼 줄의 첫 버튼이 주 버튼(포인트색 채움)입니다.',
    samples: STATE_SAMPLES,
  },
  {
    id: "dev-sec-research",
    title: "③ 딥리서치 상태 (후배 시안 네 변형)",
    note:
      "시안의 실패·취소·찾을 수 없음·결과 없음을 실제 동작에 맞춘 문구로 그렸습니다. 제목·버튼은 딥리서치 화면(pages/research/[id].vue)과 같은 상수입니다 — " +
      "실제 화면은 아직 이 컴포넌트가 아니라 rs-card 로 그립니다. 항목마다 '시안 대비'에 바꾼 점을 적었습니다.",
    samples: RESEARCH_SAMPLES,
  },
];

// ── ④ 줄 단위 안내 ──

/** 받다가 끊긴 AI 요약 — 문장 중간에서 끊긴 본보기 글 */
const AI_PARTIAL_TEXT =
  "검색된 논문들은 공공도서관 이용의 변화를 대출 기록과 이용자 설문으로 살핍니다. 대부분은 비대면 서비스가 늘면서 방문 이용이 줄었다고 보고하고, 일부 연구는 청소년 이용자의 열람실 이용이";

const sampleQuery = ref("공공도서관 서비스 품질을 평가한 연구를 찾고 있어요. 이용자 만족도와 시설, 장서, 프로그램을 함께 본 연구면 좋겠어요… (500자를 넘는 긴 질문)");

const INLINE_SAMPLES: Record<"basic" | "retry" | "busy", SpecInfo> = {
  basic: {
    name: "기본 — 검색 입력 상자 바로 아래",
    uses: [
      "입력 상자 바로 아래 — 서버가 글자 수로 거절한 입력(422, 검색어 500자 초과)",
      "입력창에 글자 수 제한(maxlength)이 들어가면 화면이 먼저 막아 거의 생기지 않는다",
    ],
    hooks: [".skx-inline-error", ".skx-inline-error__msg", 'role="alert"'],
    texts: [apiErrorMessage(SAMPLE.tooLong, "검색하지 못했어요")],
  },
  retry: {
    name: "다시 시도 있음 — AI 글 뒤에서 끊김",
    uses: ["논문 검색 AI 요약", "논문 상세 AI 요약", "도서 추천 이유"],
    hooks: [".skx-inline-error__retry", ".skx-chat-msg--ai .skx-inline-error(AI 말풍선 안)"],
    texts: [AI_SUMMARY_FAILED, RETRY_TEXT],
  },
  busy: {
    name: "재시도 중",
    uses: ["[다시 시도]를 누르고 응답을 기다리는 동안 — 모든 줄 안내"],
    hooks: ['.skx-inline-error__retry[aria-disabled="true"]', '[aria-busy="true"]'],
    texts: [apiErrorMessage(SAMPLE.network, "목록을 불러오지 못했어요"), RETRY_TEXT],
  },
};

/** '재시도 중' 본보기는 버튼만 그리면 된다 — 눌러도(컴포넌트가 무시한다) 아무 일도 하지 않는다 */
function ignoreRetry(): void {}

// ── ⑤ 연결 끊김 띠 ──

type ConnSampleId = "reconnecting" | "lost";

const CONN_SAMPLES: (SpecInfo & { id: ConnSampleId })[] = [
  {
    id: "reconnecting",
    name: "다시 연결하는 중",
    uses: ["딥리서치 진행 화면 — 실시간 진행이 끊겨 다시 붙는 동안", "연구 작업대 — 작업 스트림 재연결"],
    hooks: [".skx-conn", ".skx-conn--reconnecting", '[data-state="reconnecting"]', ".skx-conn__icon(깜빡이는 점)", ".skx-conn__msg", 'role="status"'],
    texts: [CONNECTION_HINTS.reconnecting],
  },
  {
    id: "lost",
    name: "연결하지 못함 + 다시 연결",
    uses: [
      "딥리서치 진행 화면 — 다시 붙으려고 상태를 다시 읽었는데 그것도 실패해 다음 시도를 기다리는 동안(백오프로 계속 다시 시도한다)",
      "[다시 연결] = 기다리지 않고 지금 다시 읽기(useResearch 의 resync)",
    ],
    hooks: [".skx-conn--lost", '[data-state="lost"]', ".skx-conn__icon(경고 삼각형)", ".skx-conn__retry", ".skx-conn--connected(붙음 — 보이지 않음)"],
    texts: [CONNECTION_HINTS.lost, CONNECTION_RETRY_LABEL],
  },
];

const connState = reactive<Record<ConnSampleId, ConnectionState>>({ reconnecting: "reconnecting", lost: "lost" });

// ── ⑥ 글자 수 ──

/** 본보기 한도 — 딥리서치 질문·검색어의 서버 한도(max_length 500)와 같다(실제 그 입력창에는 maxlength 가 없다) */
const CHAR_MAX = 500;
/** [N자로 맞추기] — 한도 가까이(기본 90%) 모양을 바로 볼 수 있는 길이 */
const COUNT_NEAR_DEMO = 460;
const COUNT_USES = ["연구 계획 하위질문 고치기(300자)", "작업대 주제 카드 제목·연구 질문 고치기", "읽기 목록 메모(1000자)"];

const COUNT_SAMPLES = [
  { length: 120, name: "평소" },
  { length: COUNT_NEAR_DEMO, name: "한도 가까이 (90%부터)" },
  { length: CHAR_MAX, name: "한도" },
].map(({ length, name }): SpecInfo & { length: number } => {
  const state = charCountState(length, CHAR_MAX);
  const hooks =
    state === "limit"
      ? [".skx-charcount--limit", '[data-state="limit"]', ".skx-charcount__msg", 'aria-live="polite"']
      : state === "near"
        ? [".skx-charcount--near", '[data-state="near"]']
        : [".skx-charcount", '[data-state="normal"]', ".skx-charcount__num"];
  const texts = [`${length}/${CHAR_MAX}`, ...(state === "limit" ? [charLimitMessage(CHAR_MAX)] : [])];
  return { length, name, uses: COUNT_USES, hooks, texts };
});

const typed = ref("공공도서관의 비대면 서비스가 청소년 이용자의 독서 습관에 준 영향은 무엇인가?");
const FILLER = " 도서관 이용 연구";

/** 입력창 글을 n 자로 맞춘다(모자라면 채우고 넘치면 자른다) — 가까움·한도 모양을 바로 보게 */
function fillTo(n: number): void {
  let text = typed.value;
  while (text.length < n) text += FILLER;
  typed.value = text.slice(0, Math.min(n, CHAR_MAX));
}

// ── 다시 시도 흉내 ──

/** [다시 시도]·[다시 연결] 을 누르면 이만큼 재시도 중 모양을 보였다 돌아온다 */
const RETRY_DEMO_MS = 1600;
const retrying = reactive<Record<string, boolean>>({});
const timers = new Set<ReturnType<typeof setTimeout>>();

function later(run: () => void): void {
  const timer = setTimeout(() => {
    timers.delete(timer);
    run();
  }, RETRY_DEMO_MS);
  timers.add(timer);
}

function simulateRetry(id: string): void {
  if (retrying[id]) return;
  retrying[id] = true;
  later(() => {
    retrying[id] = false;
  });
}

/** [다시 연결] — 다시 연결하는 중 → 붙음(띠가 사라지고 빈 알림 영역만) → 다시 끊김으로 돈다 */
function simulateReconnect(id: ConnSampleId): void {
  if (connState[id] !== "lost") return;
  connState[id] = "reconnecting";
  later(() => {
    connState[id] = "connected";
    later(() => {
      connState[id] = "lost";
    });
  });
}

onBeforeUnmount(() => {
  frameObserver?.disconnect();
  for (const timer of timers) clearTimeout(timer);
  timers.clear();
});
</script>

<style scoped>
/* 모음 페이지 자체의 틀 — 디자인 대상이 아니다(오류 표시는 컴포넌트가 style_skovix.css 의 공통 구역으로 그린다). 색은 --skx-* 토큰만 */
.dev-gallery {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2rem;
  width: 100%;
  min-width: 0;
  max-width: 64rem;
  margin: 0 auto;
  padding: 0.6rem 0 2.4rem;
  color: var(--skx-ink);
}
.dev-gallery code {
  padding: 0 0.25em;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.92em;
  background: var(--skx-frost-bg-soft);
  border-radius: 0.2rem;
  overflow-wrap: anywhere;
}
.dev-gallery__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem 2rem;
}
.dev-gallery__intro {
  flex: 1 1 24rem;
  min-width: 0;
}
.dev-gallery__title {
  margin: 0 0 0.4rem;
  font-size: 1.3rem;
  font-weight: 700;
  line-height: 1.3;
  color: var(--skx-ink-strong);
}
.dev-gallery__lead {
  margin: 0;
  font-size: 0.7rem;
  line-height: 1.7;
  color: var(--skx-ink-2);
}
.dev-gallery__theme {
  flex: 0 0 auto;
  width: 10rem;
}
.dev-gallery__theme-label {
  margin: 0 0 0.3rem;
  font-size: 0.65rem;
  font-weight: 500;
  color: var(--skx-gray-1);
}
.dev-gallery__section {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.dev-gallery__section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.3rem 1rem;
}
.dev-gallery__h2 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-ink-strong);
}
.dev-gallery__note {
  margin: 0;
  font-size: 0.65rem;
  line-height: 1.6;
  color: var(--skx-gray-1);
}
/* 공통 리셋(a:hover 등 — color: inherit)보다 특이도가 높아(scoped 속성) 링크 색이 유지된다 */
.dev-gallery__link {
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--skx-primary);
  text-decoration: underline;
}
.dev-gallery__link:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
.dev-gallery__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 17rem), 1fr));
  gap: 0.8rem;
}
.dev-gallery__grid--wide {
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 26rem), 1fr));
}
.dev-item {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-width: 0;
  padding: 0.8rem;
  background: var(--skx-frame-bg);
  border: 1px solid var(--skx-frame-line);
  border-radius: var(--skx-radius-lg);
}
.dev-item--span {
  grid-column: 1 / -1;
}
.dev-item__name {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-ink-strong);
}
/* 본보기 자리 — 점선 테두리로 '여기부터 실제 컴포넌트'를 표시한다 */
.dev-item__stage {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-width: 0;
  padding: 0.8rem;
  border: 1px dashed var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
}
.dev-item__label {
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--skx-ink-2);
}
.dev-item__tools {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.dev-item__meta {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.2rem 0.6rem;
  margin: 0;
  font-size: 0.6rem;
  line-height: 1.6;
  color: var(--skx-gray-1);
}
.dev-item__meta dt {
  font-weight: 600;
  color: var(--skx-ink-2);
  white-space: nowrap;
}
.dev-item__meta dd {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem 0.4rem;
  min-width: 0;
  margin: 0;
}
/* 오류 페이지 액자 — SkxErrorPage 의 홀로그램(position: fixed)을 가두려고 transform 으로 고정 위치의 기준을 액자로 바꾸고 overflow 로 자른다.
   바탕은 실제 오류 화면의 body 와 같은 페이지 바탕(홀로그램 아래 15% 는 mask 로 비친다). 테두리는 그림자 선 — border 는 16:10 칸을 1px 씩 줄인다 */
.dev-frame {
  position: relative;
  overflow: hidden;
  transform: translateZ(0);
  background: var(--skx-page-bg);
  border-radius: var(--skx-radius-md);
  box-shadow: 0 0 0 1px var(--skx-frame-line);
}
.dev-frame__screen {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
}
/* 연결 끊김 띠 아래의 흐린 본문 자리(장식) */
.dev-ghost {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.dev-ghost span {
  display: block;
  height: 0.45rem;
  background: var(--skx-line);
  border-radius: var(--skx-radius-pill);
}
.dev-ghost span:nth-child(1) {
  width: 92%;
}
.dev-ghost span:nth-child(2) {
  width: 74%;
}
.dev-ghost span:nth-child(3) {
  width: 84%;
}
</style>
