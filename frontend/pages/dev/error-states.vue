<!-- frontend/pages/dev/error-states.vue -->
<!-- 오류 화면 모음(개발용, /dev/error-states) — 후배 디자이너가 오류·빈 상태 표시를 실물로 보며 디자인하는 한 페이지.
     메뉴에 잇지 않고 검색엔진에도 싣지 않는다(robots noindex,nofollow).
     표시는 모두 실제 컴포넌트다(SkxErrorPage·SkxErrorState·SkxInlineError·SkxConnectionBanner·SkxCharCount·SkxConfirm) — 복제 마크업이 없어
     style_skovix.css 의 '[S] 공통 오류·빈 상태' 구역을 고치면 이 페이지와 실제 화면이 함께 바뀐다.
     문구도 여기 새로 짓지 않는다 — 실제 규칙(errorKind·apiErrorMessage·researchErrorMessage·researchFailedMessage)에 본보기 오류를 넣어
     만든 글과 상수(ERROR_PAGE_TEXT·CONNECTION_HINTS·AI_SUMMARY_FAILED·charLimitMessage·RESEARCH_STATE_TEXT·PAPER_STATE_TEXT·
     WORK_SOURCES_FAILED·SIDEBAR_NOTICE·REMAKE_CONFIRM·REWRITE_CONFIRM·REMOVE_CONFIRM)를 그대로 보여 문구가 바뀌면 같이 바뀐다. 상태 블록의 제목('검색하지 못했어요' 등)도 실제 화면의
     상수를 읽는다 — 이 페이지가 새로 짓는 화면 문구는 없다(연구 질문·절 제목 같은 본보기 내용만 적는다).
     항목마다 '생기는 곳'은 그 모양이 실제로 나오는 대표 화면이다(공통 컴포넌트를 쓰는 곳 — 2~5곳).
     ③ 딥리서치 상태는 후배 시안의 변형(실패·취소·찾을 수 없음)을 실제 동작(pages/research/[id].vue·api/research.py)에 맞춘 것 —
     딥리서치 화면과 같은 상수·함수를 읽고, 항목마다 '시안 대비'에 바꾼 점을 적는다. 시안의 '결과 없음(아직 연구가 없음)'은 실제 앱에
     없어(사이드바가 [연구 시작하기]만 둔다) 그리지 않는다.
     ⑦ 확인 칸은 브라우저 확인 창 대신 누른 버튼 곁에 펴는 확인이다 — 실제 화면처럼 보고서 카드(.rs-card) 위에 처음부터 펴 두고(초점을
     옮기지 않는다), 닫은 뒤 [다시 펴기]로 열면 실제처럼 초점이 칸으로 간다. 확인 버튼은 잠깐 일하는 중 모양이 됐다 접힌다.
     ⑧~⑩ 는 공통 구역 밖에서 따로 꾸미는 표시(토스트·상태 배지·흐린 안내 글 등)다 — 실제 부품(SynthProgressCard·ReportSkeleton·
     ReportView·TopicCard·ReadingNextActions·BookCover)은 본보기 내용을 넣어 그대로 그리고, 부품 없이 화면이 직접 그리는 것은 같은 클래스·
     같은 상수·함수(phaseLabel·subqStatusLabel·moreLine·NO_LIMITS·outlineProblems·SIDEBAR_EMPTY·BOOK_HISTORY_TEXT 등)로 같은 마크업을
     그린다. 항목마다 '스타일 위치'에 고칠 파일·클래스를 적는다. 사이드바 빈 기록(.skx-history__empty)의 모양은 AppSidebar.vue 의 scoped
     스타일이라, 그 컴포넌트의 scope 속성(__scopeId)을 같은 줄에 붙여 실제 규칙을 입힌다(사이드바를 고치면 여기도 바뀐다).
     ⑪ 은 글이 컴포넌트 안에만 있어 그리지 못한 자리·표시가 없는 상태·디자인 시스템 밖 화면을 적은 목록이다.
     [다시 시도] 는 누르면 잠깐 재시도 중 모양으로 바뀌었다 돌아오고, [다시 연결] 은 다시 연결하는 중 → 붙음(띠가 사라짐) → 다시 끊김으로
     돈다(요청은 보내지 않는다). 표지 대체 그림(BookCover)만 없는 자료 번호로 표지를 한 번 불러 실패시킨다.
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
          <p class="dev-gallery__lead">각 항목의 ‘생기는 곳’은 그 모양이 실제로 나오는 대표 화면입니다.</p>
          <p class="dev-gallery__lead">{{ OUTSIDE_LEAD }}</p>
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

      <!-- ② 섹션 상태 블록 — kind 별 / ③ 딥리서치 상태 — 후배 시안 변형을 실제 동작에 맞춰. 같은 틀을 섹션 목록으로 돈다 -->
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

      <!-- ⑥ 글자 수 — 세 상태 + quiet(평소엔 숨김) + 직접 쳐 보는 입력창(quiet 켜고 끄기) -->
      <section class="dev-gallery__section" aria-labelledby="dev-sec-count">
        <h2 id="dev-sec-count" class="dev-gallery__h2">⑥ 글자 수 (SkxCharCount)</h2>
        <p class="dev-gallery__note">{{ COUNT_QUIET_NOTE }}</p>
        <div class="dev-gallery__grid">
          <article v-for="n in COUNT_SAMPLES" :key="n.name" class="dev-item">
            <h3 class="dev-item__name">{{ n.name }}</h3>
            <div class="dev-item__stage">
              <SkxCharCount :length="n.length" :max="CHAR_MAX" :quiet="n.quiet" />
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
              <SkxCharCount :id="countId" :length="typed.length" :max="CHAR_MAX" :quiet="typedQuiet" />
              <label class="dev-item__check">
                <input v-model="typedQuiet" type="checkbox" />
                quiet — 검색창·질문 칸처럼 한도 가까이부터만 보이기
              </label>
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
              quiet 를 켜면 {{ COUNT_NEAR_DEMO }}자로 맞출 때 처음 나타납니다.
            </p>
          </article>
        </div>
      </section>

      <!-- ⑦ 확인 칸 — 브라우저 확인 창 대신 누른 버튼 곁에 펴는 확인. 실제 화면처럼 보고서 카드(.rs-card) 위에 그린다.
           처음에는 펴 둔 채(초점을 옮기지 않는다) 보이고, 닫은 뒤 [다시 펴기]로 열면 실제처럼 초점이 칸으로 간다 -->
      <section class="dev-gallery__section" aria-labelledby="dev-sec-confirm">
        <h2 id="dev-sec-confirm" class="dev-gallery__h2">⑦ 확인 칸 (SkxConfirm)</h2>
        <p class="dev-gallery__note">{{ CONFIRM_NOTE }}</p>
        <div class="dev-gallery__grid dev-gallery__grid--wide">
          <article v-for="c in CONFIRM_SAMPLES" :key="c.id" class="dev-item">
            <h3 class="dev-item__name">{{ c.name }}</h3>
            <div class="dev-item__stage">
              <div class="rs-card">
                <SkxConfirm
                  v-if="confirmShown[c.id]"
                  :message="c.message"
                  :confirm-label="c.confirmLabel"
                  :label="c.label"
                  :busy="c.busy || !!retrying[c.id]"
                  :initial-focus="confirmReopened[c.id] ? c.focus : 'none'"
                  :return-focus="() => reopenButton(c.id)"
                  @confirm="simulateConfirm(c.id)"
                  @cancel="confirmShown[c.id] = false"
                />
                <div v-else class="dev-item__tools">
                  <button :id="`dev-reopen-${c.id}`" type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="reopenConfirm(c.id)">
                    다시 펴기
                  </button>
                </div>
              </div>
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ c.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in c.hooks" :key="h">{{ h }}</code></dd>
              <dt>처음 초점</dt>
              <dd>{{ c.focusNote }}</dd>
              <dt>문구</dt>
              <dd><span v-for="t in c.texts" :key="t">‘{{ t }}’</span></dd>
            </dl>
          </article>
        </div>
      </section>

      <!-- ⑧ 토스트 · ⑨ 상태 배지·줄 상태 · ⑩ 흐린 안내 글·카드 안 안내 — 공통 구역 밖에서 따로 꾸미는 표시. 같은 틀을 섹션 목록으로 돈다.
           실제 부품은 본보기 내용을 넣어 그대로 그리고, 화면이 직접 그리는 것은 같은 클래스·같은 상수로 같은 마크업을 그린다 -->
      <section v-for="g in OUTSIDE_SECTIONS" :key="g.id" class="dev-gallery__section" :aria-labelledby="g.id">
        <h2 :id="g.id" class="dev-gallery__h2">{{ g.title }}</h2>
        <p class="dev-gallery__note">{{ g.note }}</p>
        <div class="dev-gallery__grid dev-gallery__grid--wide">
          <article v-for="s in g.samples" :key="s.id" class="dev-item">
            <h3 class="dev-item__name">{{ s.name }}</h3>
            <div class="dev-item__stage">
              <!-- 토스트는 position: fixed(화면 아래 가운데) — transform 을 준 칸이 고정 위치의 기준이 되어 칸 아래 가운데에 늘 떠 있다.
                   마크업은 화면들(pages/*.vue 의 Teleport)과 같고, 2.5초 타이머·나타남 전환만 없다 -->
              <div v-if="s.id === 'toast'" class="dev-toast-stage">
                <div class="dev-ghost" aria-hidden="true"><span></span><span></span><span></span></div>
                <div class="skx-toast" role="status" aria-live="polite">{{ BOOK_HISTORY_TEXT.missing }}</div>
              </div>
              <div v-else-if="s.id === 'statusChip'" class="rs-head">
                <div class="rs-head__meta">
                  <span v-for="p in STOPPED_PHASES" :key="p" class="rs-status" :class="`rs-status--${p}`">{{ phaseLabel(p) }}</span>
                </div>
              </div>
              <div v-else-if="s.id === 'failedBadge'" class="rs-card">
                <div class="rs-subq__head">
                  <span class="rs-subq__no">{{ FAILED_SUBQ.idx + 1 }}</span>
                  <span class="rs-subq__title">{{ FAILED_SUBQ.title }}</span>
                  <span class="rs-badge rs-badge--failed">{{ subqStatusLabel(FAILED_SUBQ) }}</span>
                </div>
              </div>
              <SynthProgressCard v-else-if="s.id === 'synthFailed'" :slots="DRAFT_SLOTS" :eta="DRAFT_ETA" />
              <ReportSkeleton v-else-if="s.id === 'slotStates'" :slots="PLAN_SLOTS" />
              <div v-else-if="s.id === 'muted'" class="rs-card">
                <p v-for="t in s.texts" :key="t" class="rs-muted">{{ t }}</p>
              </div>
              <div v-else-if="s.id === 'disabledReason'" class="rs-card">
                <ReadingNextActions
                  class="wk-screen__next"
                  where="bottom"
                  :no-topic="false"
                  :outline-made="false"
                  make-disabled
                  :hint="READING_HINT"
                  :disabled-why-id="null"
                />
              </div>
              <ReportView
                v-else-if="s.id === 'reportDraft'"
                :report="DRAFT_REPORT"
                job-id="dev-gallery"
                :generated-at="null"
                :draft="DRAFT_STOPPED"
              />
              <TopicCard
                v-else-if="s.id === 'topicFailed' || s.id === 'topicChecks'"
                :item="s.id === 'topicFailed' ? TOPIC_FAILED : TOPIC_CHECKED"
                :papers="{}"
                :picked="false"
                :read-only="false"
                :busy="false"
                :concepts="TOPIC_KEYWORDS"
                :concepts-gen="null"
              />
              <div v-else-if="s.id === 'outlineProblems'" class="rs-card">
                <ul class="wk-outline__problems">
                  <li v-for="p in OUTLINE_PROBLEMS" :key="p">{{ p }}</li>
                </ul>
              </div>
              <!-- 사이드바 바탕·글자 토큰(.dev-side) 위에 사이드바의 scope 속성을 붙인 같은 줄 — AppSidebar.vue 의 scoped 규칙이 그대로 입는다 -->
              <div v-else-if="s.id === 'sidebarEmpty'" class="dev-side">
                <p class="skx-history__empty" role="status" v-bind="SIDEBAR_SCOPE">{{ SIDEBAR_EMPTY }}</p>
              </div>
              <!-- 표지는 브라우저에서만 불러야 실패(@error)를 놓치지 않는다 — 서버 렌더 중 실패하면 붙기 전이라 깨진 그림이 남는다 -->
              <div v-else-if="s.id === 'bookCover'" class="dev-cover">
                <ClientOnly>
                  <BookCover :book-id="MISSING_BOOK_ID" size="small" />
                </ClientOnly>
              </div>
            </div>
            <dl class="dev-item__meta">
              <dt>생기는 곳</dt>
              <dd>{{ s.uses.join(" · ") }}</dd>
              <dt>디자인 훅</dt>
              <dd><code v-for="h in s.hooks" :key="h">{{ h }}</code></dd>
              <dt>스타일 위치</dt>
              <dd>{{ styleLine(s.styleAt) }}</dd>
              <dt>문구</dt>
              <dd>
                <span v-for="t in s.texts" :key="t">‘{{ t }}’</span>
                <span v-if="!s.texts.length">부품 안의 글이라 상수로 읽지 못해요(실제 모양은 위 본보기).</span>
              </dd>
            </dl>
          </article>
        </div>
      </section>

      <!-- ⑪ 이 모음에 그리지 않은 것 — 디자이너가 따로 찾아봐야 하는 자리 -->
      <section class="dev-gallery__section" aria-labelledby="dev-sec-skip">
        <h2 id="dev-sec-skip" class="dev-gallery__h2">⑪ 이 모음에 그리지 않은 것</h2>
        <p class="dev-gallery__note">{{ SKIPPED_NOTE }}</p>
        <div class="dev-gallery__grid dev-gallery__grid--wide">
          <article v-for="k in SKIPPED" :key="k.name" class="dev-item">
            <h3 class="dev-item__name">{{ k.name }}</h3>
            <ul class="dev-item__list">
              <li v-for="line in k.lines" :key="line">{{ line }}</li>
            </ul>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import AppSidebar from "~/components/AppSidebar.vue";
import ReportSkeleton from "~/components/research/ReportSkeleton.vue";
import ReportView from "~/components/research/ReportView.vue";
import SynthProgressCard from "~/components/research/SynthProgressCard.vue";
import ReadingNextActions from "~/components/work/ReadingNextActions.vue";
import TopicCard from "~/components/work/TopicCard.vue";
import { REPORT_EXPORT_FAILED_TOAST } from "~/composables/useReportExport";
import { useTheme } from "~/composables/useTheme";
import type { ResearchReport, SubqView } from "~/types/research";
import type { ReadingItem, ReadingView, TopicItem } from "~/types/work";
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
import { SEARCH_QUERY_MAX } from "~/utils/searchInput";
import { BOOK_HISTORY_TEXT } from "~/utils/bookErrors";
import { DEEP_RESEARCH } from "~/utils/brand";
import { CHAT_MAX_CHARS } from "~/utils/deepReadSse";
import { outlineProblems } from "~/utils/outlineEdit";
import { planSlotLabel, type PlanSlot } from "~/utils/planSlots";
import {
  REMOVE_CONFIRM,
  REMOVE_CONFIRM_OK,
  REWRITE_CONFIRM,
  REWRITE_CONFIRM_OK,
  SECTION_LABELS,
  paragraphProblem,
  reviewLine,
} from "~/utils/proposalView";
import { outlineHint } from "~/utils/readingList";
import type { DraftSlot, SynthEta } from "~/utils/researchDraft";
import {
  LOST_AFTER_DROPS,
  RESEARCH_STATE_TEXT,
  RESEARCH_TOAST_TEXT,
  pdfCheckProblem,
  researchErrorMessage,
  researchFailedMessage,
  researchRetryLabel,
  toastLine,
} from "~/utils/researchErrors";
import { phaseLabel, subqStatusLabel, type ResearchPhase } from "~/utils/researchEvents";
import { INTROLESS, NO_LIMITS, draftBadge, draftIntro, type DraftState } from "~/utils/researchReport";
import { PAPER_STATE_TEXT } from "~/utils/paperErrors";
import { QUESTION_MAX } from "~/utils/researchInput";
import { SIDEBAR_EMPTY, SIDEBAR_NOTICE } from "~/utils/sidebarGroups";
import { slotStateLabel } from "~/utils/synthCard";
import { THEMES, THEME_LABELS } from "~/utils/theme";
import { cardNote, cardNumbersLine, keywordWarning, moreLine, regenerateProblem } from "~/utils/topicDeck";
import { WORK_SLOW_MS, WORK_SOURCES_FAILED, WORK_STREAM_LOST_MS } from "~/utils/workErrors";
import { REMAKE_CONFIRM, REMAKE_CONFIRM_OK, REMAKE_REPORT } from "~/utils/workPhase";

useHead({
  title: "오류 화면 모음 — SKOVIX",
  meta: [{ name: "robots", content: "noindex,nofollow" }],
});

const { theme, setTheme } = useTheme();
const uid = useId();
const themeLabelId = `dev-theme-${uid}`;
const typeId = `dev-type-${uid}`;
const countId = `dev-count-${uid}`;

/** 항목 설명 — 생기는 곳(그 모양이 실제로 나오는 대표 화면 2~4곳)·디자인 훅(클래스·속성)·문구 원문 */
interface SpecInfo {
  name: string;
  uses: string[];
  hooks: string[];
  texts: string[];
}

/** 컴포넌트 기본 버튼 글(SkxErrorState·SkxInlineError 의 retryLabel 기본값) — 설명 줄에만 쓴다 */
const RETRY_TEXT = "다시 시도";

// 실제 규칙(errorKind·apiErrorMessage·researchErrorMessage)에 넣어 볼 본보기 오류 — 문구를 여기 적지 않고 규칙이 만든 글을 보인다.
// network 는 응답 없이 끝난 요청(ofetch FetchError — 상태 없음), 나머지는 상태 코드만 든 응답
const SAMPLE = {
  network: { name: "FetchError" },
  timeout: { status: 504 },
  busy: { status: 503 },
  server: { status: 500 },
  notFound: { status: 404 },
  // 백엔드 오류 code — 서버 detail(옛 말투) 대신 CODE_MESSAGES 의 문구를 쓴다
  searchDown: { status: 503, data: { detail: "검색 서버가 잠시 응답하지 않습니다. 잠시 뒤 다시 시도하세요", code: "search_unavailable" } },
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
    title: PAPER_STATE_TEXT.detailFailed,
    retry: true,
    uses: [
      "딥리서치 — 멈춘 연구 카드(③ 실패 — kind 를 주지 않아 기본값)",
      "전역 오류 화면 — 화면을 그리지 못함(① 치명 오류)",
      "kind 를 errorKind 로 넘기는 화면(검색·상세·작업대)은 이 갈래가 아니라 아래 network·timeout·busy·server 로 나온다",
    ],
    hooks: [".skx-state", ".skx-state--error", '[data-tone="error"]', ".skx-state__title", ".skx-state__retry"],
  }),
  stateSample({
    id: "network",
    name: "네트워크 끊김",
    kind: errorKind(SAMPLE.network),
    title: PAPER_STATE_TEXT.searchFailed,
    message: reasonOf(SAMPLE.network),
    retry: true,
    uses: [
      "소장자료·논문 검색 결과",
      "논문·도서 상세 — 정보·관련 자료 읽기",
      "딥리서치 — 연구 불러오기",
      "연구 작업대 — 주제 카드·참고문헌 후보·보고서 불러오기",
    ],
    hooks: [".skx-state--network", ".skx-state__msg", ".skx-state__icon(아이콘 원 — 실패 갈래는 경고 삼각형)"],
  }),
  stateSample({
    id: "timeout",
    name: "시간 초과",
    kind: errorKind(SAMPLE.timeout),
    title: PAPER_STATE_TEXT.relatedFailed,
    message: reasonOf(SAMPLE.timeout),
    retry: true,
    uses: [
      "논문·도서 상세·딥리서치 — 정보 읽기(GET 30초 제한 — useApi)",
      "소장자료·논문 검색 결과·상세의 관련 자료(60초 제한 — API_SEARCH_TIMEOUT_MS)",
      "게이트웨이 504",
    ],
    hooks: [".skx-state--timeout", '[data-kind="timeout"]'],
  }),
  stateSample({
    id: "busy",
    name: "요청 몰림",
    kind: errorKind(SAMPLE.busy),
    title: PAPER_STATE_TEXT.searchFailed,
    message: reasonOf(SAMPLE.busy),
    retry: true,
    uses: ["소장자료·논문 검색 결과 — 요청 몰림(429·503)", "논문·도서 상세·관련 자료 — 503", "딥리서치·연구 작업대 불러오기 — 503"],
    hooks: [".skx-state--busy", '[data-kind="busy"]'],
  }),
  stateSample({
    id: "server",
    name: "서버 오류",
    kind: errorKind(SAMPLE.server),
    title: PAPER_STATE_TEXT.detailFailed,
    message: reasonOf(SAMPLE.server),
    retry: true,
    uses: ["논문·도서 상세 — 정보 읽기(5xx)", "소장자료·논문 검색 결과", "연구 작업대 — 주제 카드·참고문헌 후보·보고서 불러오기"],
    hooks: [".skx-state--server", '[data-kind="server"]'],
  }),
  stateSample({
    id: "searchDown",
    name: "서버가 알린 장애(code)",
    kind: errorKind(SAMPLE.searchDown),
    title: PAPER_STATE_TEXT.searchFailed,
    message: reasonOf(SAMPLE.searchDown),
    retry: true,
    uses: [
      "소장자료·논문 검색 결과 — 검색 서버(Milvus·임베딩) 장애(503 search_unavailable)",
      "상황별 추천 — 같은 장애(503 search_unavailable)",
      "어느 화면이든 잡지 않은 서버 예외(500 internal_error — kind 는 server, 설명 줄은 같은 규칙)",
    ],
    hooks: [".skx-state--busy", "설명 줄은 apiErrors 의 CODE_MESSAGES(서버 detail 은 쓰지 않는다)"],
  }),
  stateSample({
    id: "notFound",
    name: "찾을 수 없음 + 돌아가기",
    kind: errorKind(SAMPLE.notFound),
    title: researchErrorMessage(SAMPLE.notFound, ""),
    message: RESEARCH_STATE_TEXT.notFoundMessage,
    action: { label: RESEARCH_STATE_TEXT.backToSearch, href: "/papers" },
    uses: ["딥리서치 — 없는 연구 주소", "논문·도서 상세 — 없는 주소", "연구 작업대 — 인용의 근거 기록을 찾지 못함(compact)"],
    hooks: [".skx-state--notFound", '[data-tone="neutral"]', ".skx-state__action(슬롯 링크 — 버튼 줄의 첫 버튼이라 주 버튼 모양)"],
  }),
  stateSample({
    id: "empty",
    name: "결과 없음",
    kind: "empty",
    // 논문 검색 결과 0건의 실제 문구(소장자료 검색은 같은 모양에 설명 줄만 다르다 — BOOK_SEARCH_TEXT)
    title: PAPER_STATE_TEXT.searchEmpty,
    message: PAPER_STATE_TEXT.searchEmptyHint,
    uses: [
      "논문·소장자료 검색 결과 0건",
      "논문·도서 상세 — 관련 자료·AI 큐레이션 없음(compact)",
      "연구 작업대 — 후보 논문·주제 카드·목차 없음",
    ],
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
    title: PAPER_STATE_TEXT.searchFailed,
    message: reasonOf(SAMPLE.network),
    retry: true,
    busy: true,
    uses: [
      "[다시 시도]를 누르고 응답을 기다리는 동안 — 논문 상세·관련 자료",
      "출처 인용 창 — 인용 정보",
      "딥리서치 — 연구 불러오기 실패·멈춘 연구 카드",
    ],
    hooks: ['.skx-state__retry[aria-disabled="true"]', '[aria-busy="true"]'],
  }),
  stateSample({
    id: "compact",
    name: "좁은 칸 (compact)",
    kind: "error",
    title: WORK_SOURCES_FAILED,
    message: reasonOf(SAMPLE.network),
    compact: true,
    retry: true,
    uses: [
      "연구 작업대 — 인용의 원문 대목",
      "논문·도서 상세 — 관련 자료",
      "출처 인용 창 — 인용 정보",
      "딥리서치 — 멈춘·취소한 연구 카드(③)",
    ],
    hooks: [".skx-state--compact"],
  }),
];

// 후배 시안 'DR/상태 안내'의 변형을 실제 동작에 맞춘 것 — 제목·설명·버튼은 실제 화면(pages/research/[id].vue)과 같은 상수·함수
// (RESEARCH_STATE_TEXT·researchFailedMessage·researchRetryLabel). 멈춘·취소한 연구는 실제 화면처럼 카드 안의 compact 블록이다.
// 실패의 다시 시도 갈래는 api/research.py retry_research(보고서 작성 단계에서 멈춘 연구만 체크포인트로 이어 가고, 계획 단계 실패는 새 연구)
const RESEARCH_SAMPLES: StateSample[] = [
  stateSample({
    id: "researchFailed",
    name: "실패 — 보고서 작성 중 멈춤",
    kind: "error",
    title: RESEARCH_STATE_TEXT.failedTitle,
    // 보고서 작성 단계(stage explored)에서 멈춘, 계획이 있는 연구 — 실제 화면은 서버 last_error 중 알아보는 사유만 둘째 줄에 넣는다
    message: researchFailedMessage("explored", true),
    retry: true,
    retryLabel: researchRetryLabel("explored"),
    compact: true,
    uses: ["딥리서치 — 보고서를 쓰다 멈춘 연구(stage explored) — 머리 아래(진행 막대 자리) 카드"],
    hooks: [".skx-state--error", '[data-tone="error"]', ".skx-state--compact", ".skx-state__retry(retryLabel)"],
    diff:
      "제목은 실제 화면 문구. [문의하기]는 뺐다 — 앱에 문의 창구가 없다. 설명과 [다시 시도] 글은 멈춘 단계를 따른다: 보고서 작성 중이면 " +
      "'보고서 작성부터 다시 시도'(탐색 결과로 이어 감), 탐색 중이면 '다시 시도'(승인한 계획으로 탐색부터 다시), 계획 단계에서 멈췄으면 " +
      "다시 시도할 수 없어 '같은 질문으로 다시 시작'(새 연구)만 둔다. 서버가 남긴 멈춘 까닭(last_error — 예외 원문일 수 있다)은 붙이지 않고, " +
      "알아보는 사유(시간 상한·응답 없는 작업 회수·모든 하위질문 실패)만 해요체 한 줄로 바꿔 둘째 줄에 넣는다.",
  }),
  stateSample({
    id: "researchCanceled",
    name: "취소",
    kind: "canceled",
    title: RESEARCH_STATE_TEXT.canceledTitle,
    message: RESEARCH_STATE_TEXT.canceledMessage,
    action: { label: RESEARCH_STATE_TEXT.restart, href: "#" },
    compact: true,
    uses: ["딥리서치 — 사용자가 취소한 연구(계획을 세우는 중·승인 대기·대기열·진행 중 어디서든) — 머리 아래 카드"],
    hooks: [
      ".skx-state--canceled",
      '[data-tone="neutral"]',
      'role="status"',
      '.skx-state__action[aria-disabled="true"](새 연구를 만드는 동안 — aria-busy 와 함께)',
    ],
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
      "시안 제목 '연구를 불러오지 못했어요'는 실제 화면의 불러오기 실패(네트워크·서버) 제목이라 헷갈려 실제 404 문구를 쓴다. '접근 권한이 없는 연구일 수 있어요'는 뺐다 — " +
      "연구는 주소만 알면 누구나 연다(권한 검사가 없다). 원인은 주소가 잘못된 경우다(연구를 지우는 기능은 없다 — 사이드바 전체 삭제도 기록만 지운다).",
  }),
];

const STATE_SECTIONS = [
  {
    id: "dev-sec-state",
    title: "② 섹션 상태 블록 (SkxErrorState)",
    note:
      "제목은 화면마다 다른 '무엇을 못 했는지', 설명 줄은 오류 규칙(apiErrorMessage)이 붙이는 이유입니다. 색은 아이콘 원에만 씁니다 — 실패 갈래는 경고 삼각형(위험색), " +
      "빈 결과는 문서+돋보기(청록), 찾을 수 없음은 돋보기+X(회색), 취소는 둥근 네모(포인트색). 여기 없는 kind(invalid·conflict·forbidden·unknown)는 " +
      '실패 갈래([data-tone="error"])로 같은 모양이고, .skx-state--{kind} 로 따로 꾸밀 수 있습니다. 버튼 줄의 첫 버튼이 주 버튼(포인트색 채움)입니다. ' +
      "사이드바의 빈 기록 안내(.skx-history__empty)는 사이드바 모양을 지키려 이 블록을 쓰지 않아요 — ⑩ 에 따로 그렸어요.",
    samples: STATE_SAMPLES,
  },
  {
    id: "dev-sec-research",
    title: "③ 딥리서치 상태 (후배 시안 변형)",
    note:
      "시안의 실패·취소·찾을 수 없음을 실제 동작에 맞춘 문구로 그렸습니다. 딥리서치 화면(pages/research/[id].vue)도 같은 컴포넌트에 " +
      "같은 상수·함수(RESEARCH_STATE_TEXT·researchFailedMessage·researchRetryLabel)를 넘깁니다 — 멈춘·취소한 연구는 머리 아래(진행 막대 자리) 카드 안의 " +
      "compact 블록, 없는 연구는 본문 전체 자리입니다. 항목마다 '시안 대비'에 바꾼 점을 적었습니다.\n" +
      "시안의 넷째 변형(결과 없음 — 아직 연구가 없음)은 실제 앱에 없어 그리지 않았어요.\n" +
      "연구 기록이 하나도 없으면 사이드바 DeepResearch 묶음이 빈 화면 없이 [연구 시작하기] 버튼만 둬요(누르면 첫 화면이 논문 패널 + DeepResearch 모드로 열려요).",
    samples: RESEARCH_SAMPLES,
  },
];

// ── ④ 줄 단위 안내 ──

/** 받다가 끊긴 AI 요약 — 문장 중간에서 끊긴 본보기 글 */
const AI_PARTIAL_TEXT =
  "검색된 논문들은 공공도서관 이용의 변화를 대출 기록과 이용자 설문으로 살핍니다. 대부분은 비대면 서비스가 늘면서 방문 이용이 줄었다고 보고하고, 일부 연구는 청소년 이용자의 열람실 이용이";

const sampleQuery = ref("공공도서관 서비스 품질을 평가한 연구를 찾고 있어요. 이용자 만족도와 시설, 장서, 프로그램을 함께 본 연구면 좋겠어요.");

const INLINE_SAMPLES: Record<"basic" | "retry" | "busy", SpecInfo> = {
  basic: {
    name: "기본 — 검색 입력 상자 바로 아래",
    uses: [
      `${DEEP_RESEARCH} 모드의 입력 상자 아래 — 질문 길이·연구 시작 실패(네트워크가 끊겼을 때의 문구)`,
      "연구 계획·주제 카드 고치기 — 입력이 규칙에 맞지 않음(하위질문 개수·글자 수 등)",
      "출처 인용 창 — 복사하지 못함",
      `연구 작업대 — 쓰기 응답이 ${WORK_SLOW_MS / 1000}초 넘게 늦어짐(끊지 않고 안내만 — WORK_SLOW_MESSAGE)`,
      '사이드바 — 사이트 데이터 저장이 막힌 브라우저(SIDEBAR_NOTICE.storageBlocked — role="status")',
    ],
    hooks: [".skx-inline-error", ".skx-inline-error__msg", 'role="alert"'],
    // 연구 시작 요청이 서버에 닿지 못했을 때 — SearchPlusMenu 와 같은 규칙·대체 문구
    texts: [researchErrorMessage(SAMPLE.network, `${DEEP_RESEARCH}를 시작하지 못했어요`)],
  },
  retry: {
    name: "다시 시도 있음 — AI 글 뒤에서 끊김",
    uses: ["논문 검색·논문 상세 AI 요약", "도서 추천 이유", "사이드바 — 기록을 불러오지 못함", "DeepRead 대화 — 답을 받지 못한 말풍선"],
    hooks: [".skx-inline-error__retry", ".skx-chat-msg--ai .skx-inline-error(DeepRead AI 말풍선 안 — 말풍선 글자색)"],
    texts: [AI_SUMMARY_FAILED, RETRY_TEXT],
  },
  busy: {
    name: "재시도 중",
    uses: [
      "[다시 시도]를 누르고 응답을 기다리는 동안 — 사이드바 기록",
      "연구 작업대 — 저장 뒤 화면을 새로 고치지 못한 단계",
      "딥리서치 — 취소 뒤 정리 안내의 [다시 불러오기]",
    ],
    hooks: ['.skx-inline-error__retry[aria-disabled="true"]', '[aria-busy="true"]'],
    // 사이드바가 실제로 보이는 목록 실패 안내(utils/sidebarGroups — 묶음의 목록을 못 읽었고 보이는 줄도 없을 때)
    texts: [SIDEBAR_NOTICE.loadFailed, RETRY_TEXT],
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
      `딥리서치 진행 화면 — 연결 실패(스트림 끊김·상태 다시 읽기 실패)가 연달아 ${LOST_AFTER_DROPS}번 쌓였을 때(그 뒤에도 백오프로 계속 다시 시도해, 붙으면 띠가 걷힌다)`,
      `연구 작업대 — 끊긴 뒤 ${WORK_STREAM_LOST_MS / 1000}초 안에 다시 붙지 못했을 때`,
      "[다시 연결] = 기다리지 않고 지금 다시 붙기(딥리서치는 상태를 다시 읽은 뒤 — useResearch 의 reconnect)",
    ],
    hooks: [".skx-conn--lost", '[data-state="lost"]', ".skx-conn__icon(경고 삼각형)", ".skx-conn__retry", ".skx-conn--connected(붙음 — 보이지 않음)"],
    texts: [CONNECTION_HINTS.lost, CONNECTION_RETRY_LABEL],
  },
];

const connState = reactive<Record<ConnSampleId, ConnectionState>>({ reconnecting: "reconnecting", lost: "lost" });

// ── ⑥ 글자 수 ──

/** 본보기 한도 — 검색어·DeepResearch 질문의 한도(서버 max_length 500, 입력창 maxlength)와 같다 */
const CHAR_MAX = 500;
/** [N자로 맞추기] — 한도 가까이(기본 90%) 모양을 바로 볼 수 있는 길이 */
const COUNT_NEAR_DEMO = 460;
const COUNT_USES = [
  `소장자료·논문 검색어(${SEARCH_QUERY_MAX}자)`,
  `${DEEP_RESEARCH} 질문(${QUESTION_MAX}자)`,
  `DeepRead 질문(${CHAT_MAX_CHARS}자)`,
];
/** 앱의 글자 수 칸은 모두 quiet 다(사용자 결정 2026-10-16) — 평소에는 화면에서만 숨고 한도 가까이부터 보인다. quiet 를 쓰지 않는 칸이 없어
 *  '평소' 모양(숫자만)은 지금 앱 어디에도 보이지 않는다 */
const COUNT_QUIET_NOTE =
  "검색창·질문 칸(DeepResearch·DeepRead 질문 포함)은 모두 quiet 라 한도 가까이(90%)부터만 글자 수가 보여요.\n" +
  "평소에는 화면에서만 숨고, 낭독기 알림 영역과 aria-describedby 는 그대로 남아요.\n" +
  "그래서 ‘평소’ 모양(숫자만)은 지금 앱 어디에도 보이지 않아요 — quiet 를 쓰지 않는 칸이 생길 때를 위한 모양이에요.";

const COUNT_SAMPLES = [
  { length: 120, name: "평소 (지금 앱에는 보이는 곳 없음)" },
  { length: 120, name: "평소 — quiet (검색창·질문 칸 — 화면에 보이지 않음)", quiet: true },
  { length: COUNT_NEAR_DEMO, name: "한도 가까이 (90%부터)" },
  { length: CHAR_MAX, name: "한도" },
].map(({ length, name, quiet }): SpecInfo & { length: number; quiet: boolean } => {
  const state = charCountState(length, CHAR_MAX);
  const hooks =
    state === "limit"
      ? [".skx-charcount--limit", '[data-state="limit"]', ".skx-charcount__msg", 'aria-live="polite"']
      : state === "near"
        ? [".skx-charcount--near", '[data-state="near"]']
        : quiet
          ? [".skx-charcount--quiet", '[data-state="normal"](화면에서만 숨김 — 공통 구역 규칙)']
          : [".skx-charcount", '[data-state="normal"]', ".skx-charcount__num"];
  const texts = [`${length}/${CHAR_MAX}`, ...(state === "limit" ? [charLimitMessage(CHAR_MAX)] : [])];
  // 숫자만 보이는 평소 모양은 quiet 를 쓰지 않는 칸의 것이다 — 앱의 글자 수 칸은 모두 quiet 라 지금은 나오는 곳이 없다(위 quiet 본보기)
  const uses =
    state === "normal" && !quiet
      ? ["지금 앱에는 없음 — 글자 수 칸이 모두 quiet 라 평소에는 숨어요(quiet 를 쓰지 않는 칸이 생기면 이 모양)"]
      : COUNT_USES;
  return { length, name, quiet: !!quiet, uses, hooks, texts };
});

/** 직접 입력해 보기의 quiet 켜기 — 켜면 검색창·질문 칸처럼 한도 가까이부터만 보인다 */
const typedQuiet = ref(false);

const typed = ref("공공도서관의 비대면 서비스가 청소년 이용자의 독서 습관에 준 영향은 무엇인가?");
const FILLER = " 도서관 이용 연구";

/** 입력창 글을 n 자로 맞춘다(모자라면 채우고 넘치면 자른다) — 가까움·한도 모양을 바로 보게 */
function fillTo(n: number): void {
  let text = typed.value;
  while (text.length < n) text += FILLER;
  typed.value = text.slice(0, Math.min(n, CHAR_MAX));
}

// ── ⑦ 확인 칸 ──

/** 컴포넌트 기본 버튼 글(SkxConfirm 의 cancelLabel 기본값) — 설명 줄에만 쓴다 */
const CANCEL_TEXT = "취소";

const CONFIRM_NOTE =
  "브라우저 확인 창·모달 대신 누른 버튼 바로 아래(흐름 안)에 펴는 확인이에요.\n" +
  "한 화면에 하나만 열리고, 묻던 일이 더는 맞지 않으면(절을 쓰기 시작함·단계가 바뀜) 저절로 접혀요.\n" +
  "Esc·[취소]로 닫으면 초점이 누른 버튼으로 돌아가요 — 그 버튼이 사라졌으면 그 자리의 제목으로 가요.\n" +
  "확인 버튼을 누르면 그 일이 끝날 때까지 일하는 중 모양(aria-busy)으로 남았다가 접혀요.\n" +
  "여기서는 처음부터 펴 두었어요(초점을 옮기지 않아요) — 닫은 뒤 [다시 펴기]로 열면 실제처럼 초점이 칸으로 가요.";

const CONFIRM_HOOKS = [
  ".skx-confirm",
  'role="alertdialog"',
  "aria-label(무엇을 확인하는지)",
  "aria-describedby → .skx-confirm__msg",
  ".skx-confirm__msg(pre-line — 문장마다 줄)",
  ".skx-confirm__actions",
  ".skx-confirm__ok",
  ".skx-confirm__cancel",
];

type ConfirmSampleId = "remake" | "rewrite" | "remove" | "busy";

interface ConfirmSample extends SpecInfo {
  id: ConfirmSampleId;
  message: string;
  confirmLabel: string;
  /** 칸의 이름(aria-label) — 실제 화면과 같은 꼴(본보기 절 이름) */
  label: string;
  /** 실제 화면이 넘기는 처음 초점 */
  focus: "confirm" | "cancel";
  focusNote: string;
  busy?: boolean;
}

const CONFIRM_SAMPLES: ConfirmSample[] = [
  {
    id: "remake",
    name: `${REMAKE_REPORT} — 여러 문장(문장마다 줄)`,
    uses: [
      `참고문헌 선택하기 — 목차를 만든 뒤 위·아래 버튼 묶음의 [${REMAKE_REPORT}](누른 묶음 아래)`,
      `보고서 — 다시 맞춤 필요 줄·대체 목차 줄의 [${REMAKE_REPORT}](그 줄 아래)`,
    ],
    hooks: CONFIRM_HOOKS,
    message: REMAKE_CONFIRM,
    confirmLabel: REMAKE_CONFIRM_OK,
    label: `${REMAKE_REPORT} 확인`,
    focus: "confirm",
    focusNote: `[${REMAKE_CONFIRM_OK}] — 골라 누른 일이라 엔터 한 번 더면 진행돼요(initial-focus="confirm")`,
    texts: [REMAKE_CONFIRM, REMAKE_CONFIRM_OK, CANCEL_TEXT],
  },
  {
    id: "rewrite",
    name: "절 다시 쓰기 — 수락·고친·직접 쓴 문단이 있을 때",
    uses: [
      "보고서 절 — 그런 문단이 있는 절의 [이 절 다시 쓰기](머리 아래)",
      "보고서 절 — 그런 절을 다시 쓰지 못했을 때 줄 안내의 [다시 시도](그 줄 아래)",
    ],
    hooks: CONFIRM_HOOKS,
    message: REWRITE_CONFIRM,
    confirmLabel: REWRITE_CONFIRM_OK,
    label: `${SECTION_LABELS.gap} 다시 쓰기 확인`,
    focus: "cancel",
    focusNote: `[${CANCEL_TEXT}] — 수락·고친·직접 쓴 문단을 되돌릴 수 없어 덜 파괴적인 쪽(컴포넌트 기본값)`,
    texts: [REWRITE_CONFIRM, REWRITE_CONFIRM_OK, CANCEL_TEXT],
  },
  {
    id: "remove",
    name: "문단 지우기 — 한 문장",
    uses: ["보고서 문단 — 문단마다의 [지우기](그 문단의 버튼 줄 아래)"],
    hooks: CONFIRM_HOOKS,
    message: REMOVE_CONFIRM,
    confirmLabel: REMOVE_CONFIRM_OK,
    label: `${SECTION_LABELS.gap} 1번째 문단 지우기 확인`,
    focus: "cancel",
    focusNote: `[${CANCEL_TEXT}] — 되돌릴 수 없는 지우기라 덜 파괴적인 쪽(컴포넌트 기본값)`,
    texts: [REMOVE_CONFIRM, REMOVE_CONFIRM_OK, CANCEL_TEXT],
  },
  {
    id: "busy",
    name: "일하는 중 — 확인 버튼을 누른 뒤",
    uses: ["위 세 자리 모두 — 확인한 일(다시 만들기·다시 쓰기·지우기)이 끝날 때까지. 끝나면 칸이 접혀요"],
    hooks: ['.skx-confirm__ok[aria-disabled="true"]', '[aria-busy="true"](확인 버튼)', '.skx-confirm__cancel[aria-disabled="true"]'],
    message: REMOVE_CONFIRM,
    confirmLabel: REMOVE_CONFIRM_OK,
    label: `${SECTION_LABELS.gap} 1번째 문단 지우기 확인`,
    focus: "confirm",
    focusNote: "옮기지 않아요 — 누른 확인 버튼에 초점이 남아요(disabled 가 아니라 aria-disabled 라서). 누름·Esc 는 무시해요",
    texts: [REMOVE_CONFIRM, REMOVE_CONFIRM_OK, CANCEL_TEXT],
    busy: true,
  },
];

/** 칸이 펴져 있는가 — 처음에는 모두 펴 둔다 */
const confirmShown = reactive<Record<ConfirmSampleId, boolean>>({ remake: true, rewrite: true, remove: true, busy: true });
/** [다시 펴기]로 연 칸만 실제처럼 처음 초점을 옮긴다 — 처음부터 펴 둔 칸이 페이지를 열자마자 초점을 빼앗지 않게 */
const confirmReopened = reactive<Partial<Record<ConfirmSampleId, boolean>>>({});

function reopenConfirm(id: ConfirmSampleId): void {
  confirmReopened[id] = true;
  confirmShown[id] = true;
}

/** 칸이 접히면 초점은 그 자리에 새로 나타나는 [다시 펴기]로(실제 화면의 '누른 버튼으로'에 해당) */
function reopenButton(id: ConfirmSampleId): HTMLElement | null {
  return document.getElementById(`dev-reopen-${id}`);
}

/** 확인 버튼 — 잠깐 일하는 중 모양이 됐다 접힌다(요청은 보내지 않는다) */
function simulateConfirm(id: ConfirmSampleId): void {
  if (retrying[id]) return;
  retrying[id] = true;
  later(() => {
    retrying[id] = false;
    confirmShown[id] = false;
  });
}

// ── ⑧~⑩ 공통 구역 밖 ──

/** 맨 위 안내 넷째 줄 */
const OUTSIDE_LEAD = "⑧~⑩ 는 공통 구역 밖에서 따로 꾸미는 자리예요 — 항목마다 ‘스타일 위치’에 고칠 파일과 클래스를 적었어요.";

/** '스타일 위치' 줄 — 고칠 파일·클래스에, 공통 구역을 따르지 않는다는 말을 붙인다 */
function styleLine(where: string): string {
  return `${where} — ‘[S] 공통 오류·빈 상태’ 구역을 따르지 않는 따로 꾸미는 자리예요.`;
}

/** 규칙이 null 을 줄 수 있는 글(해당 없음)을 걸러 문구 목록으로 */
const present = (texts: (string | null)[]): string[] => texts.filter((t): t is string => !!t);
/** 줄 안내용 문구를 토스트 한 줄로 — 딥리서치 화면이 원문 확인 실패를 토스트에 실을 때와 같다(문구가 없으면 null) */
const toastOf = (text: string | null): string | null => (text ? toastLine(text) : null);

type OutsideId =
  | "toast"
  | "statusChip"
  | "failedBadge"
  | "synthFailed"
  | "slotStates"
  | "muted"
  | "disabledReason"
  | "reportDraft"
  | "topicFailed"
  | "topicChecks"
  | "outlineProblems"
  | "sidebarEmpty"
  | "bookCover";

/** 공통 구역 밖 항목 — styleAt 은 고칠 파일·클래스(styleLine 이 공통 구역 밖이라는 말을 붙인다). texts 가 비면 글이 부품 안에만 있다 */
interface OutsideSample extends SpecInfo {
  id: OutsideId;
  styleAt: string;
}

// 본보기 내용 — 화면 문구가 아니라 실제 부품에 넣는 연구 질문·하위질문·절 제목·씨앗 글이다(안내 문구는 부품·상수가 만든다)
const SAMPLE_QUESTION = "공공도서관의 비대면 서비스는 이용 행태를 어떻게 바꾸었나?";
const SAMPLE_SUBQS = [
  "비대면 서비스가 늘면서 방문 이용은 어떻게 바뀌었나?",
  "청소년 이용자의 열람실 이용은 어떻게 바뀌었나?",
  "지역 도서관의 프로그램 운영은 어떻게 바뀌었나?",
] as const;
const SAMPLE_HEADINGS = ["비대면 서비스와 방문 이용의 변화", "청소년 이용자의 열람실 이용", "지역 도서관의 프로그램 운영"] as const;

// ⑧ 토스트
const TOAST_SAMPLE: OutsideSample = {
  id: "toast",
  name: "토스트 — 화면 아래 가운데 한 줄",
  uses: [
    "첫 화면·논문 검색 — 주소의 검색 기록을 복원하지 못함(없는 기록·서버에 닿지 못해 못 읽음)",
    "딥리서치 — [원문 보기]가 원문을 찾지 못하거나 불러오지 못함",
    "딥리서치 — Word·PDF 내려받기 실패",
    "딥리서치 — [링크 복사] 실패(주소창에서 직접 복사하도록 안내)",
    "딥리서치 — 링크 복사·Word 내려받기를 마쳤다는 안내",
  ],
  hooks: [".skx-toast", ".skx-toast-enter-active·-leave-active·-enter-from·-leave-to(나타남·사라짐)", 'role="status"', 'aria-live="polite"'],
  styleAt: "style_skovix.css 의 ‘── 토스트 ──’ 구역 .skx-toast",
  // 첫 화면의 기록 토스트(논문 검색의 PAPER_STATE_TEXT.missingHistory·historyUnavailable 도 같은 말)와 딥리서치의 원문·내려받기·링크 복사.
  // 딥리서치는 줄 안내용 두 줄 문구를 토스트에 실을 때 toastLine 으로 한 줄('A — B.')로 바꾼다 — 화면과 같은 함수·상수를 쓴다
  texts: present([
    BOOK_HISTORY_TEXT.missing,
    BOOK_HISTORY_TEXT.unavailable,
    toastOf(pdfCheckProblem(404)),
    toastOf(pdfCheckProblem(500)),
    REPORT_EXPORT_FAILED_TOAST.docx,
    REPORT_EXPORT_FAILED_TOAST.pdf,
    RESEARCH_TOAST_TEXT.linkCopyFailed,
    RESEARCH_TOAST_TEXT.linkCopied,
  ]),
};

// ⑨ 상태 배지·줄 상태

/** 멈춘 연구의 머리 상태 칩 — 실패·취소 */
const STOPPED_PHASES = ["failed", "canceled"] as const satisfies readonly ResearchPhase[];

/** 오류로 끝난 하위질문 — 탐색 경로·계획 카드의 한 줄 */
const FAILED_SUBQ: SubqView = {
  idx: 1,
  title: SAMPLE_SUBQS[1],
  seq: null,
  status: "failed",
  rounds: [],
  verdict: null,
  note: "",
  adopted: null,
  parseFailed: false,
  error: null,
};

/** 보고서 작성 현황·멈춘 초안의 절 자리 — 1절은 썼고, 2절은 서술을 받지 못했고, 3절은 차례를 기다린다 */
const DRAFT_SLOTS: DraftSlot[] = [
  { idx: 0, heading: SAMPLE_HEADINGS[0], status: "done", durationMs: 48_000, startedAt: null, sectionIndex: 0 },
  { idx: 1, heading: SAMPLE_HEADINGS[1], status: "failed", durationMs: 52_000, startedAt: null, sectionIndex: null },
  { idx: 2, heading: SAMPLE_HEADINGS[2], status: "waiting", durationMs: null, startedAt: null, sectionIndex: null },
];
/** 작성 현황 머리 — 끝난 절 둘(완료·실패), 남은 절 하나 */
const DRAFT_ETA: SynthEta = { done: 2, total: 3, runningIdx: null, runningElapsedMs: null, remainingMs: 50_000 };

/** 보고서 자리(첫 절이 나오기 전) — 근거를 모은 자리·오류로 끝난 자리·근거 없이 끝난 자리 */
const PLAN_SLOTS: PlanSlot[] = [
  { subqIdx: 0, title: SAMPLE_SUBQS[0], state: "collected", adopted: 4, round: null, sectionIdx: null },
  { subqIdx: 1, title: SAMPLE_SUBQS[1], state: "failed", adopted: null, round: null, sectionIdx: null },
  { subqIdx: 2, title: SAMPLE_SUBQS[2], state: "empty", adopted: 0, round: null, sectionIdx: null },
];

const BADGE_SAMPLES: OutsideSample[] = [
  {
    id: "statusChip",
    name: "연구 머리 상태 칩 — 실패·취소됨",
    uses: ["딥리서치 — 연구 머리(질문 아래)의 상태 칩 — 실패·취소로 끝난 연구"],
    hooks: [".rs-status", ".rs-status--failed", ".rs-status--canceled"],
    styleAt: "research.css 의 .rs-status--failed·.rs-status--canceled",
    texts: STOPPED_PHASES.map((phase) => phaseLabel(phase)),
  },
  {
    id: "failedBadge",
    name: "줄 배지 — 오류·실패",
    uses: [
      "딥리서치 — 탐색 경로·계획 카드에서 오류로 끝난 하위질문",
      "연구 작업대 보고서 — 쓰지 못한 절의 상태 배지",
      "보고서 자리의 오류 칩은 같은 모양의 다른 규칙(.rs-slot.is-failed — 아래 ‘보고서 자리’)",
    ],
    hooks: [".rs-badge", ".rs-badge--failed(본문색 글·테두리)"],
    styleAt: "research.css 의 .rs-badge--failed(작업대 절 배지도 같은 클래스)",
    texts: [subqStatusLabel(FAILED_SUBQ)],
  },
  {
    id: "synthFailed",
    name: "보고서 작성 현황 — 서술을 받지 못한 절",
    uses: ["딥리서치 — 보고서를 쓰는 동안 작성 현황 카드의 절 줄(그 절은 논문 목록만 싣는다)"],
    hooks: [".rs-synth__item.is-failed", ".rs-synth__icon(✕ — 본문색 테두리 원)", ".rs-synth__state"],
    styleAt: "research.css 의 .rs-synth__item.is-failed .rs-synth__icon",
    texts: [slotStateLabel(DRAFT_SLOTS[1]!, DRAFT_ETA)],
  },
  {
    id: "slotStates",
    name: "보고서 자리 — 오류·근거 없음",
    uses: ["딥리서치 — 승인 뒤 첫 절이 나오기 전 본문의 보고서 자리(하위질문마다 한 자리)"],
    hooks: [".rs-slot.is-failed .rs-slot__state(오류 — 본문색 테두리 칩)", ".rs-slot.is-empty(근거 없음 — 점선 한 줄로 접힘)"],
    styleAt: "research.css 의 .rs-slot.is-failed·.rs-slot.is-empty",
    texts: PLAN_SLOTS.filter((slot) => slot.state !== "collected").map((slot) => planSlotLabel(slot)),
  },
];

// ⑩ 흐린 안내 글·카드 안 안내

/** 멈춘 초안 — 실패·취소로 1절까지만 쓰고 멈춘 보고서(1절은 도입 글이 비었다 — INTROLESS 자리) */
const DRAFT_REPORT: ResearchReport = {
  question: SAMPLE_QUESTION,
  range: null,
  sections: [{ heading: SAMPLE_HEADINGS[0], intro: "", papers: [], future: [], evidence_chunks: {}, chunk_scores: {} }],
  evidence: {},
  trail: [],
  limitations: [],
};
const DRAFT_STOPPED = { slots: DRAFT_SLOTS, state: "interrupted" as DraftState, excluded: [] };

/** [보고서 만들기]를 막은 까닭 — 주제는 골랐고 담은 논문이 모자라다(세 편) */
const READING_HINT = outlineHint({
  topic_id: 1,
  subquestions: [],
  funnel: { reviewed: null, adopted: null, candidates: SAMPLE_HEADINGS.length, picked: SAMPLE_HEADINGS.length },
  items: SAMPLE_HEADINGS.map(
    (title, i): ReadingItem => ({
      cnts_id: `dev-reading-${i}`,
      state: "in",
      origin: "evidence",
      note: null,
      group_label: null,
      position: i,
      meta: { title, personal_author: null, pub_date: null, series_title: null },
      path: { subqs: [], revived: null, user: false },
    }),
  ),
  excluded: [],
} satisfies ReadingView);

/** 주제 카드를 만들 때 고른 키워드 — 지금 고른 키워드(concepts)와 같게 넘겨 '키워드가 바뀌었습니다'는 붙지 않는다 */
const TOPIC_KEYWORDS = ["청소년", "디지털 격차"];
/** 보고서 씨앗 자리의 카드 생성이 실패한 카드 — 점선 테두리·카드 안 안내·[다시] */
const TOPIC_FAILED: TopicItem = {
  id: 901,
  slot: 0,
  origin: "report_seed",
  state: "candidate",
  parent_id: null,
  seed: {
    key: "dev-future-0",
    kind: "future",
    section_idx: 1,
    subq_idx: null,
    heading: SAMPLE_HEADINGS[1],
    text: "청소년 이용자의 열람실 이용 변화를 따로 살핀 연구가 더 필요하다.",
    papers: [],
    adopted: null,
  },
  card: null,
  generation: { id: 31, status: "failed" },
  created_at: "2026-10-16T09:00:00Z",
};
/** 고른 키워드를 제목에 하나도 넣지 못하고 [F#] 밖 숫자를 쓴 카드 — 키워드 경고·'확인 필요' 표시 */
const CHECKED_CARD: NonNullable<TopicItem["card"]> = {
  title: "공공도서관 비대면 서비스와 열람실 이용의 변화",
  question: "비대면 서비스가 늘어난 뒤 열람실 이용은 얼마나 줄었나?",
  evidence: [],
  figure_sentence: null,
  figures: [],
  latest_year: 2023,
  edited: false,
  keywords: TOPIC_KEYWORDS,
  checks: { numbers: ["37%"], softened: 0, recovered: 0, missing_keywords: TOPIC_KEYWORDS },
  gen_id: 32,
};
const TOPIC_CHECKED: TopicItem = { ...TOPIC_FAILED, id: 902, card: CHECKED_CARD, generation: { id: 32, status: "done" } };

/** [목차 고치기]에서 묶음 이름·논문·연구 질문을 비운 채 승인하려 할 때 */
const OUTLINE_PROBLEMS = outlineProblems({ groups: [{ key: "g1", name: "", papers: [] }], question: "", method: "" }, true);

/**
 * AppSidebar.vue 의 scoped 스타일이 붙는 속성(data-v-…) — 빈 기록 줄에 붙여 사이드바의 규칙을 그대로 입힌다(사이드바를 고치면 여기도
 * 바뀐다). 컴파일러가 컴포넌트에 싣는 __scopeId 를 읽는다 — 없으면 붙이지 않아 모양만 빠진다
 */
const SIDEBAR_SCOPE: Record<string, string> = (() => {
  const scopeId = (AppSidebar as unknown as { __scopeId?: string }).__scopeId;
  return scopeId ? { [scopeId]: "" } : {};
})();

/** 없는 자료 번호 — 표지 요청이 실패해(404) BookCover 가 대체 그림을 그린다 */
const MISSING_BOOK_ID = "dev-gallery-no-cover";

const MUTED_SAMPLES: OutsideSample[] = [
  {
    id: "muted",
    name: "흐린 안내 글 — 빈 칸·경고",
    uses: [
      "딥리서치 보고서 — 한계를 찾지 못함·서술을 받지 못한 절·인용 칩에 맞는 대목 없음",
      "연구 작업대 — 더 쓸 씨앗·뽑힌 키워드가 없음, 아직 적지 않은 칸, 근거가 없어 쓰지 않은 절",
      "연구 작업대 — 목차를 만든 뒤 주제·참고문헌이 바뀜(다시 맞춤 필요 안내)",
      "연구 작업대 인용 근거 — 겹치는 대목을 못 찾음·대목 대신 초록을 보임",
    ],
    hooks: [".rs-muted", ".rs-cite__quote.rs-muted(인용 칩 팝오버)"],
    styleAt: "research.css 의 .rs-muted(연구 작업대도 같은 클래스)",
    texts: [moreLine(0), NO_LIMITS],
  },
  {
    id: "disabledReason",
    name: "막힌 버튼 + 까닭",
    uses: [
      "연구 작업대 참고문헌 — [보고서 만들기]를 못 누름(주제 없음·담은 논문이 모자람)",
      "연구 작업대 키워드 — [이 키워드로 다시 만들기]를 못 누름(고른 키워드가 모자람)",
      "연구 작업대 문단 고치기 — [저장]을 못 누름(빈 문단·글자 수 넘음)",
    ],
    hooks: [".rs-btn:disabled(흐림)", ".rs-muted(까닭 — 버튼이 aria-describedby 로 가리킨다)", ".wk-screen__next"],
    styleAt: "research.css 의 .rs-btn:disabled·.rs-muted",
    texts: present([READING_HINT, regenerateProblem([]), paragraphProblem("")]),
  },
  {
    id: "reportDraft",
    name: "보고서 안 안내 — 멈춘 초안",
    uses: [
      "딥리서치 — 실패·취소로 멈춘 연구의 보고서 칸(쓴 절까지만 초안으로)",
      "딥리서치 보고서 — 도입 서술·논문 요약을 받지 못한 절",
      "연구 작업대 — 목차·절의 다시 맞춤 필요 배지(.wk-outline__stale·.wk-psec__stale — 초안 배지와 같은 포인트색 테두리, work.css)",
    ],
    hooks: [".rs-badge--draft(초안 배지)", ".rs-report__intro(머리 글 — 왼쪽 포인트색 선)", ".rs-muted(못 쓴 절·도입 없는 절)"],
    styleAt: "research.css 의 .rs-badge--draft·.rs-report__intro·.rs-muted",
    texts: [draftBadge("interrupted").label, draftIntro(DRAFT_SLOTS, "interrupted"), INTROLESS],
  },
  {
    id: "topicFailed",
    name: "주제 카드 — 만들지 못함",
    uses: ["연구 작업대 제목 고르기 — 카드 생성 실패·근거 부족(씨앗을 받치는 논문이 모자람)·키워드를 만들지 못해 카드가 들어가지 않은 자리"],
    hooks: [".wk-topic--failed·--insufficient·--blocked(점선 테두리)", ".wk-topic__note(카드 안 안내 — 굵은 보조색, 두 문장이면 줄바꿈)", ".wk-topic__seed"],
    styleAt: "work.css 의 .wk-topic--failed·.wk-topic--insufficient·.wk-topic--blocked·.wk-topic__note",
    texts: present([cardNote("failed"), cardNote("insufficient"), cardNote("blocked")]),
  },
  {
    id: "topicChecks",
    name: "주제 카드 — 키워드 경고·확인 필요",
    uses: [
      "연구 작업대 제목 고르기 — 고른 키워드를 제목에 하나도 넣지 못한 카드·[F#] 밖 숫자를 쓴 카드",
      "연구 작업대 보고서 — 문장 옆 확인 필요 표시·머리의 [검토할 곳] 버튼(.wk-review__jump — 같은 점선)",
    ],
    hooks: [".wk-topic__kwwarn", ".wk-psec__check(점선 테두리 표시)", ".wk-review", ".wk-review__jump"],
    styleAt: "work.css 의 .wk-topic__kwwarn·.wk-psec__check·.wk-review__jump",
    texts: present([keywordWarning(CHECKED_CARD), cardNumbersLine(CHECKED_CARD), reviewLine({ unmarked: 2, numbers: 1, first: null })]),
  },
  {
    id: "outlineProblems",
    name: "편집 칸 아래 고칠 곳 목록",
    uses: ["연구 작업대 — [목차 고치기]에서 묶음 이름·논문·연구 질문·방법이 규칙에 맞지 않음([저장]·[승인] 막힘)"],
    hooks: [".wk-outline__problems(점 목록 — 본문색 작은 글)"],
    styleAt: "work.css 의 .wk-outline__problems",
    texts: OUTLINE_PROBLEMS,
  },
  {
    id: "sidebarEmpty",
    name: "사이드바 빈 기록",
    uses: ["사이드바 — DeepResearch·최근 검색 두 묶음이 모두 진짜 비었을 때(못 읽은 묶음은 제자리에서 ④ 줄 안내로 말해요)"],
    hooks: [".skx-history__empty", 'role="status"', ".skx-lnb 안의 글자 토큰(--skx-gray-1 → --skx-side-gray-1)"],
    styleAt: "AppSidebar.vue 의 scoped 스타일 .skx-history__empty",
    texts: [SIDEBAR_EMPTY],
  },
  {
    id: "bookCover",
    name: "표지 대체 그림",
    uses: [
      "소장자료 검색 결과 카드·도서 상세·관련 자료·상황별 추천 — 표지를 불러오지 못함(원본 없음 404·저장소 장애 503)",
      "논문 표지는 이 모양이 아니라 논문 기본 그림으로 바뀌어요",
    ],
    hooks: [".book-cover", ".placeholder", ".placeholder-text", "svg stroke(선색)"],
    styleAt: "BookCover.vue 의 scoped 스타일·svg stroke 속성(테마 토큰이 아닌 고정 색이라 두 테마에서 같아요)",
    texts: [],
  },
];

const OUTSIDE_SECTIONS: { id: string; title: string; note: string; samples: OutsideSample[] }[] = [
  {
    id: "dev-sec-toast",
    title: "⑧ 토스트 (.skx-toast)",
    note:
      "토스트는 한 문장·한 줄이에요(white-space: nowrap — 줄을 바꾸지 않아요).\n" +
      "두 가지를 말할 때는 '무엇을 못 했는지 — 할 일'로 이어 한 문장으로 써요.\n" +
      "실제 화면에서는 아래 가운데에 2.4~2.5초 떠 있다가 사라져요 — 여기서는 같은 마크업을 칸 안에 늘 보이게 그렸어요.\n" +
      "공통 컴포넌트가 없어 화면마다(Teleport) 같은 마크업을 직접 그려요.",
    samples: [TOAST_SAMPLE],
  },
  {
    id: "dev-sec-badge",
    title: "⑨ 상태 배지·줄 상태 (공통 구역 밖)",
    note:
      "딥리서치·연구 작업대의 상태를 말하는 배지와 목록 줄이에요.\n" +
      "빨강 없이 본문색 테두리·회색 글로 실패를 말해요.\n" +
      "research.css·work.css 에 따로 있어 ‘[S] 공통 오류·빈 상태’ 구역을 고쳐도 바뀌지 않아요.\n" +
      "작성 현황·보고서 자리는 실제 부품(SynthProgressCard·ReportSkeleton)에 본보기 절·하위질문을 넣어 그렸어요.",
    samples: BADGE_SAMPLES,
  },
  {
    id: "dev-sec-muted",
    title: "⑩ 흐린 안내 글·카드 안 안내 (공통 구역 밖)",
    note:
      "공통 컴포넌트를 거치지 않고 본문 안의 흐린 글·카드 안 글로 말하는 빈 칸·경고·막힌 까닭이에요.\n" +
      "보고서·주제 카드·다음 단계 버튼·표지는 실제 부품(ReportView·TopicCard·ReadingNextActions·BookCover)에 본보기 내용을 넣어 그렸어요.\n" +
      "부품 안의 버튼은 눌러도 아무 일도 하지 않아요([직접 고치기]는 편집 칸만 열려요).",
    samples: MUTED_SAMPLES,
  },
];

// ── ⑪ 이 모음에 그리지 않은 것 ──

const SKIPPED_NOTE =
  "이 모음에 그리지 않았지만 디자인할 때 알아 둘 자리예요.\n" +
  "글이 컴포넌트 안에만 있어 상수로 읽을 수 없는 것, 표시가 아예 없는 상태, SKOVIX 디자인 밖 화면이에요.";

const SKIPPED: { name: string; lines: string[] }[] = [
  {
    name: "따로 꾸미는 자리 — 글이 컴포넌트 안에만 있어요",
    lines: [
      "딥리서치 탐색 경로의 멈춘 지점 줄 — .rs-subq__stopped(research.css, 굵은 본문색 작은 글)",
      "첫 화면 AI 결과에서 1위 도서도 질문과 멀 때의 약한 결과 안내 — .skx-aip__notice(style_skovix.css, 큰 회색 글)",
      "사이드바 연구 줄의 실패·취소·알 수 없음 배지 — .skx-history-badge.is-failed·.is-canceled·.is-unknown(AppSidebar.vue scoped, 옅은 유리 알약에 회색 글)",
      "참고문헌 단계의 다시 맞춤 필요 — 회색 기본 배지(.rs-badge)를 흐린 안내 글 안에 둬요(ReadingStep)",
      "관련 자료 카드의 빈 요약·빈 추천 사유 — 평소 글 자리(.dt-rc__why-text — detail.css)에 빈 글을 적어요",
    ],
  },
  {
    name: "표시가 없는 상태",
    lines: [
      "예시 연구 목록을 읽지 못함 — 카드 칸을 그리지 않아요",
      "사이드바 기록 지우기 실패 — 화면 안내 없이 목록에서 빼요",
      "작성 중인 보고서의 [초안 저장]이 막힘 — 버튼 툴팁(title)만 있어요",
    ],
  },
  {
    name: "SKOVIX 디자인 밖",
    lines: [
      "관리자 잡 화면(/admin/jobs) — Tailwind 운영자 화면이에요(오류 줄은 왼쪽 호박색 선)",
      "보존 화면(/search-classic) — 구조를 그대로 두는 첫 화면이라 자체 scoped 스타일(.error-area·.empty·.ch-empty·.cart-empty·.ca-empty·.reason-error)을 써요",
      "DeepRead 첫 인사·멈춘 답의 꼬리 글 — 오류 표시가 아니라 평범한 AI 말풍선이에요",
    ],
  },
];

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
/* 여러 문장 설명은 문장마다 줄을 바꾼다('\n') */
.dev-gallery__note {
  margin: 0;
  font-size: 0.65rem;
  line-height: 1.6;
  color: var(--skx-gray-1);
  white-space: pre-line;
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
.dev-item__check {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.65rem;
  color: var(--skx-ink-2);
  cursor: pointer;
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
/* ⑧ 토스트 자리 — 토스트는 position: fixed(화면 아래 가운데)라, ① 액자처럼 transform 으로 이 칸을 고정 위치의 기준으로 바꿔
   칸 아래 가운데에 늘 떠 있게 한다. 바탕은 실제 화면처럼 페이지 바탕 */
.dev-toast-stage {
  position: relative;
  height: 7rem;
  padding: 0.8rem;
  overflow: hidden;
  transform: translateZ(0);
  background: var(--skx-page-bg);
  border-radius: var(--skx-radius-md);
}
/* ⑩ 사이드바 바탕 — 사이드바 틀(style_skovix.css 의 LNB 구역)과 같은 면과 글자 토큰(사이드바 안 글은 토큰을 다시 정의해 한 단계 밝다).
   빈 기록 줄의 모양은 AppSidebar.vue 의 scoped 규칙이 입힌다 */
.dev-side {
  padding: 0.4rem 0.8rem;
  background: var(--skx-frost-side-bg);
  border-radius: var(--skx-radius-lg);
  box-shadow: var(--skx-shadow-lnb);
  --skx-ink: var(--skx-side-ink);
  --skx-ink-2: var(--skx-side-ink-2);
  --skx-gray-1: var(--skx-side-gray-1);
  --skx-gray-2: var(--skx-side-gray-2);
}
/* ⑩ 표지 자리 — 결과 카드의 표지 폭쯤 */
.dev-cover {
  width: 6rem;
}
/* ⑪ 그리지 않은 것 목록 */
.dev-item__list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin: 0;
  padding-left: 1rem;
  font-size: 0.6rem;
  line-height: 1.6;
  color: var(--skx-ink-2);
}
</style>
