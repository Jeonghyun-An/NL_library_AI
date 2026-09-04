# SKOVIX UI Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 도서/논문 검색 결과 UX 개선 — 컬렉션 개수 조정, DeepRead CTA, AI 표지 큐레이션 통합, 논문 참고논문 카드 클릭, 논문 상세 인터랙티브 레이아웃, 연관도 이원화 타입 준비

**Architecture:** 모두 프론트엔드 전용 변경. 백엔드 의존 항목(연관도 이원화)은 타입/UI만 준비하고 실제 분리 수치는 백엔드 배포 후 자동 활성화. 각 태스크는 독립적으로 커밋 가능.

**Tech Stack:** Nuxt 3, Vue 3 Composition API, TypeScript, CSS (style_skovix.css)

**범위에서 제외 (문구/용어 변경):** 텍스트 변경(DeepRead 명칭, 정합성→연관도 등)은 별도 진행. 이 계획서는 기능 구현만 다룸.

---

## 파일 변경 목록

| 파일 | 작업 |
|------|------|
| `frontend/pages/index.vue` | 컬렉션 개수 조정 UI + DeepRead CTA |
| `frontend/pages/books/[cnts_id].vue` | AI 생성 표지 큐레이션 탭 추가 |
| `frontend/pages/papers/index.vue` | 논문 상위 참고논문 카드 클릭 가능하게 |
| `frontend/pages/papers/[id].vue` | 인터랙티브 레이아웃 (chatOpen → 사이드패널) |
| `frontend/types/search.ts` | 연관도 이원화 타입 준비 |
| `frontend/assets/css/style_skovix.css` | 각 기능 스타일 추가 |

---

## Task 1: 컬렉션 개수 조정 UI

**Files:**
- Modify: `frontend/pages/index.vue`
- Modify: `frontend/assets/css/style_skovix.css`

**Context:** 현재 `fetchCuration()`은 `books.value.slice(0, 3)`으로 고정. 사용자가 3/5/10권 중 선택해 컬렉션 크기를 바꿀 수 있어야 함. 크기 변경 시 `fetchCuration` 재실행.

- [ ] **Step 1: `collectionSize` ref 추가 및 fetchCuration 수정**

`index.vue` script에서 `fetchCuration` 위에:
```typescript
const collectionSize = ref(3);

async function setCollectionSize(n: number) {
  if (collectionSize.value === n) return;
  collectionSize.value = n;
  if (books.value.length) await fetchCuration();
}
```

`fetchCuration` 내부 첫 줄:
```typescript
// 기존: const topBooks = books.value.slice(0, 3);
const topBooks = books.value.slice(0, collectionSize.value);
```

- [ ] **Step 2: 크기 선택 버튼 템플릿 추가**

`index.vue`의 `skx-ai-section` header 안, `<header class="skx-ai-header">` 블록 교체:
```html
<header class="skx-ai-header">
  <h2 class="skx-ai-header__title">AI 검색 결과</h2>
  <p v-if="keywordChips.length" class="skx-ai-header__keywords">
    키워드: {{ keywordChips.join(", ") }}
  </p>
  <div class="skx-collection-size">
    <span class="skx-collection-size__label">컬렉션</span>
    <div class="skx-collection-size__btns">
      <button
        v-for="n in [3, 5, 10]"
        :key="n"
        type="button"
        :class="['skx-collection-size__btn', collectionSize === n && 'is-active']"
        :disabled="curationLoading"
        @click="setCollectionSize(n)"
      >{{ n }}권</button>
    </div>
  </div>
</header>
```

- [ ] **Step 3: CSS 추가** (`style_skovix.css` 끝에 추가)

```css
/* ── 컬렉션 크기 선택 ──────────────────── */
.skx-collection-size {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.skx-collection-size__label {
  font-size: 12px;
  color: var(--ink-3, #9ca3af);
}
.skx-collection-size__btns {
  display: flex;
  gap: 4px;
}
.skx-collection-size__btn {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid var(--border, #e5e7eb);
  background: #fff;
  color: var(--ink-2, #374151);
  cursor: pointer;
  transition: all 0.15s;
}
.skx-collection-size__btn:hover:not(:disabled) {
  border-color: var(--violet, #6366f1);
  color: var(--violet, #6366f1);
}
.skx-collection-size__btn.is-active {
  background: var(--violet, #6366f1);
  border-color: var(--violet, #6366f1);
  color: #fff;
}
.skx-collection-size__btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

- [ ] **Step 4: 동작 확인**

브라우저에서 도서 검색 후:
- 컬렉션 버튼 3권/5권/10권 클릭 → 활성 표시 변경 확인
- 5권 클릭 → AI 큐레이션이 5권 기준으로 재생성되는 것 확인
- 검색 결과가 3개 미만일 때 5권 클릭해도 에러 없는 것 확인 (slice는 결과보다 많아도 안전)

- [ ] **Step 5: 커밋**

```bash
git add frontend/pages/index.vue frontend/assets/css/style_skovix.css
git commit -m "[Feat] 컬렉션 개수 조정 UI 추가 (3/5/10권)"
```

---

## Task 2: 컬렉션 → DeepRead 연결 CTA

**Files:**
- Modify: `frontend/pages/index.vue`
- Modify: `frontend/assets/css/style_skovix.css`

**Context:** AI 큐레이션 답변 아래, 컬렉션 목록이 끝난 후 사용자가 자연스럽게 DeepRead로 넘어갈 수 있는 CTA 블록. 첫 번째 curationItem 기준으로 딥리드 진입.

- [ ] **Step 1: CTA 블록 템플릿 추가**

`index.vue`의 `skx-ai-answer__list` 닫는 `</ul>` 바로 아래:
```html
<!-- DeepRead CTA -->
<div
  v-if="curationItems.length && !curationLoading"
  class="skx-deepread-cta"
>
  <span class="skx-deepread-cta__text">컬렉션에서 책과 직접 대화해보세요</span>
  <button
    type="button"
    class="skx-deepread-cta__btn"
    @click="navigateTo(`/books/${curationItems[0].book_id}?q=${encodeURIComponent(currentQuery)}&chat=1`)"
  >
    DeepRead 시작하기
    <img src="/img/ico-arrow.svg" alt="" />
  </button>
</div>
```

- [ ] **Step 2: CSS 추가** (`style_skovix.css` 끝에 추가)

```css
/* ── 컬렉션 DeepRead CTA ───────────────── */
.skx-deepread-cta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
  border: 1px solid #ddd6fe;
  border-radius: 10px;
  flex-wrap: wrap;
}
.skx-deepread-cta__text {
  font-size: 13px;
  color: #4c1d95;
  font-weight: 500;
}
.skx-deepread-cta__btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: var(--violet, #6366f1);
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
  transition: opacity 0.15s;
  white-space: nowrap;
}
.skx-deepread-cta__btn img {
  width: 14px;
  filter: brightness(0) invert(1);
}
.skx-deepread-cta__btn:hover {
  opacity: 0.88;
}
```

- [ ] **Step 3: 동작 확인**

도서 검색 후 AI 큐레이션 영역 하단:
- CTA 블록 표시 확인
- "DeepRead 시작하기" 클릭 → 해당 도서 상세 페이지로 이동 + 채팅 패널 자동 열림 확인
- curationLoading 중에는 CTA 표시 안 됨 확인

- [ ] **Step 4: 커밋**

```bash
git add frontend/pages/index.vue frontend/assets/css/style_skovix.css
git commit -m "[Feat] 컬렉션 하단 DeepRead CTA 추가"
```

---

## Task 3: AI 생성 표지 큐레이션 탭 통합

**Files:**
- Modify: `frontend/pages/books/[cnts_id].vue`
- Modify: `frontend/assets/css/style_skovix.css`

**Context:** 현재 `detailTabs = [추천 이유, 줄거리, 소개]`. 여기에 "AI 표지" 탭을 추가해 큐레이션 섹션 안에서 표지를 보여주고 "AI가 생성한 표지"임을 명시.

- [ ] **Step 1: detailTabs에 AI 표지 탭 추가**

`books/[cnts_id].vue`의 `detailTabs` 배열:
```typescript
const detailTabs = [
  { key: "reason", label: "추천 이유" },
  { key: "plot", label: "줄거리" },
  { key: "intro", label: "소개" },
  { key: "cover", label: "AI 표지" },
];
```

- [ ] **Step 2: 표지 탭 콘텐츠 템플릿 추가**

`books/[cnts_id].vue`에서 `<p v-else-if="detailTab === 'intro'"...` 블록 바로 아래:
```html
<div v-else-if="detailTab === 'cover'" class="skx-curation-cover">
  <div class="skx-curation-cover__img-wrap">
    <BookCover :book-id="cnts_id" size="large" />
  </div>
  <p class="skx-curation-cover__label">
    <img src="/img/logo-mark.svg" alt="" class="skx-curation-cover__ai-icon" />
    AI가 도서 내용을 분석해 생성한 표지입니다
  </p>
</div>
```

- [ ] **Step 3: CSS 추가** (`style_skovix.css` 끝에 추가)

```css
/* ── AI 표지 큐레이션 탭 ───────────────── */
.skx-curation-cover {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  padding: 4px 0;
}
.skx-curation-cover__img-wrap {
  width: 140px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0,0,0,.12);
}
.skx-curation-cover__label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-3, #9ca3af);
}
.skx-curation-cover__ai-icon {
  width: 14px;
  height: 14px;
  opacity: 0.6;
}
```

- [ ] **Step 4: 동작 확인**

도서 상세 페이지에서:
- AI 큐레이션 섹션에 "AI 표지" 탭 표시 확인
- 클릭 시 표지 이미지 + "AI가 도서 내용을 분석해 생성한 표지입니다" 라벨 표시 확인
- 표지가 없는 경우 BookCover의 placeholder 표시 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/pages/books/[cnts_id].vue frontend/assets/css/style_skovix.css
git commit -m "[Feat] AI 생성 표지를 큐레이션 탭으로 통합"
```

---

## Task 4: 논문 상위 참고논문 카드 클릭 가능하게

**Files:**
- Modify: `frontend/pages/papers/index.vue`
- Modify: `frontend/assets/css/style_skovix.css`

**Context:** 현재 `skx-pai-refs` 영역의 논문들(aiRefs)은 단순 텍스트 표시. `aiRefs`는 `{ num, book_id, title, authors }` 구조로 이미 `book_id`를 가지고 있음. 클릭 시 논문 상세로 이동.

- [ ] **Step 1: skx-pai-ref 클릭 가능하게 수정**

`papers/index.vue`의 `skx-pai-refs__scroll` 내부, 기존 `skx-pai-ref` div를 교체:
```html
<div
  v-for="ref in aiRefs"
  :key="ref.num"
  class="skx-pai-ref skx-pai-ref--clickable"
  role="button"
  tabindex="0"
  :aria-label="`${ref.title} 상세보기`"
  @click="navigateTo(`/papers/${ref.book_id}?q=${encodeURIComponent(currentQuery)}`)"
  @keydown.enter="navigateTo(`/papers/${ref.book_id}?q=${encodeURIComponent(currentQuery)}`)"
>
  <div class="skx-pai-ref__num">{{ ref.num }}</div>
  <div class="skx-pai-ref__body">
    <p class="skx-pai-ref__title">{{ ref.title }}</p>
    <p class="skx-pai-ref__author">{{ ref.authors }}</p>
  </div>
  <img class="skx-pai-ref__chevron" src="/img/ico-arrow.svg" alt="" />
</div>
```

- [ ] **Step 2: CSS 추가** (`style_skovix.css` 끝에 추가)

```css
/* ── 논문 참고문헌 카드 클릭 ──────────── */
.skx-pai-ref--clickable {
  cursor: pointer;
  transition: background 0.15s;
}
.skx-pai-ref--clickable:hover {
  background: var(--bg-hover, #f5f3ff);
  border-radius: 8px;
}
.skx-pai-ref__chevron {
  width: 14px;
  flex-shrink: 0;
  opacity: 0.35;
  transform: rotate(-90deg);
  margin-left: auto;
}
```

- [ ] **Step 3: 동작 확인**

논문 검색 후 AI 브리핑 우측 참고논문 목록에서:
- 호버 시 배경색 변경 확인
- 클릭 시 `/papers/${book_id}?q=...` 로 이동 확인
- 키보드 Tab + Enter 동작 확인

- [ ] **Step 4: 커밋**

```bash
git add frontend/pages/papers/index.vue frontend/assets/css/style_skovix.css
git commit -m "[Feat] 논문 AI 브리핑 참고논문 카드 클릭 가능하게"
```

---

## Task 5: 논문 상세 인터랙티브 레이아웃

**Files:**
- Modify: `frontend/pages/papers/[id].vue`
- Modify: `frontend/assets/css/style_skovix.css`

**Context:** 현재 논문 상세에서 채팅 패널(`chatOpen`)이 열리면 오버레이 방식. `chatOpen = true` 일 때 메인 콘텐츠가 좌측으로 밀리고 우측에 채팅이 붙는 사이드패널 레이아웃으로 변경. 패널 닫기 버튼도 추가.

- [ ] **Step 1: 레이아웃 클래스 조건부 추가**

`papers/[id].vue` template에서 `<div class="skx-result-card">` 를:
```html
<div :class="['skx-result-card', chatOpen && 'skx-result-card--chat-open']">
```

- [ ] **Step 2: 채팅 패널 인라인 래퍼 추가**

현재 `<PaperChat ... />` (또는 채팅 컴포넌트) 앞뒤로 래퍼 추가. 현재 파일에서 chatOpen 관련 컴포넌트를 찾아 다음과 같이 변경:
```html
<!-- 채팅 사이드패널 -->
<Transition name="skx-chat-slide">
  <aside v-if="chatOpen" class="skx-chat-side">
    <button
      type="button"
      class="skx-chat-side__close"
      aria-label="채팅 닫기"
      @click="chatOpen = false"
    >
      <img src="/img/ico-arrow.svg" alt="" />
    </button>
    <!-- 기존 채팅 컴포넌트 그대로 -->
    <BookChat :cnts-id="paperId" @close="chatOpen = false" />
  </aside>
</Transition>
```

- [ ] **Step 3: CSS 추가** (`style_skovix.css` 끝에 추가)

```css
/* ── 논문 상세 인터랙티브 레이아웃 ───── */
.skx-result-card--chat-open {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 0;
  align-items: start;
}
.skx-result-card--chat-open .skx-pdetail {
  overflow-y: auto;
  max-height: calc(100vh - 80px);
}
.skx-chat-side {
  position: sticky;
  top: 24px;
  height: calc(100vh - 80px);
  border-left: 1px solid var(--border, #e5e7eb);
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.skx-chat-side__close {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--ink-3, #9ca3af);
  background: none;
  border: none;
  border-bottom: 1px solid var(--border, #e5e7eb);
  cursor: pointer;
  text-align: left;
  width: 100%;
}
.skx-chat-side__close img {
  width: 14px;
  transform: rotate(90deg);
  opacity: 0.5;
}
/* 슬라이드 트랜지션 */
.skx-chat-slide-enter-active,
.skx-chat-slide-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.skx-chat-slide-enter-from,
.skx-chat-slide-leave-to {
  transform: translateX(20px);
  opacity: 0;
}
@media (max-width: 768px) {
  .skx-result-card--chat-open {
    grid-template-columns: 1fr;
  }
  .skx-chat-side {
    position: fixed;
    top: 0; right: 0; bottom: 0;
    width: 100%;
    max-width: 400px;
    z-index: 200;
    box-shadow: -4px 0 20px rgba(0,0,0,.15);
  }
}
```

- [ ] **Step 4: 동작 확인**

논문 상세에서 "논문과 대화하기" 클릭:
- 우측 채팅 패널 슬라이드인 확인
- 메인 콘텐츠가 좌측에 유지되는 것 확인
- 닫기 버튼으로 패널 사라짐 확인
- 모바일(768px 이하)에서는 전체화면 오버레이로 표시 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/pages/papers/[id].vue frontend/assets/css/style_skovix.css
git commit -m "[Feat] 논문 상세 DeepRead 사이드패널 인터랙티브 레이아웃"
```

---

## Task 6: 연관도 이원화 — 타입 준비 및 UI (백엔드 배포 전 준비)

**Files:**
- Modify: `frontend/types/search.ts`
- Modify: `frontend/pages/index.vue`
- Modify: `frontend/pages/books/[cnts_id].vue`
- Modify: `frontend/assets/css/style_skovix.css`

**Context:** 현재 `BookChunkGroup`은 `best_score` 하나만 가짐. 백엔드에서 `title_score`와 `content_score`를 분리해서 내려주면 자동으로 이원화 표시되도록 준비. `title_score`가 없으면 기존 `best_score` 단일 표시 유지 (하위 호환).

- [ ] **Step 1: 타입에 optional 필드 추가**

`frontend/types/search.ts`의 `BookChunkGroup`:
```typescript
export interface BookChunkGroup {
  book_id: string;
  book_info?: BookInfo;
  best_score: number;
  title_score?: number;    // 백엔드 배포 후 활성화
  content_score?: number;  // 백엔드 배포 후 활성화
  chunks: ChunkHit[];
  reason?: string;
}
```

- [ ] **Step 2: index.vue 도서 카드 태그 수정**

`index.vue`에서 `skx-tag--score` 스팬을 감싸는 부분을:
```html
<template v-if="item.title_score !== undefined && item.content_score !== undefined">
  <span class="skx-tag skx-tag--score">
    제목 {{ Math.round(item.title_score * 100) }}%
  </span>
  <span class="skx-tag skx-tag--score skx-tag--score-content">
    내용 {{ Math.round(item.content_score * 100) }}%
  </span>
</template>
<template v-else>
  <span class="skx-tag skx-tag--score">
    연관도 {{ Math.round((item.best_score || 0) * 100) }}%
  </span>
</template>
```

- [ ] **Step 3: books/[cnts_id].vue 상세 페이지 태그 수정**

`books/[cnts_id].vue`에서 `skx-tag--score` 부분을:
```html
<template v-if="titleScore !== undefined && contentScore !== undefined">
  <span class="skx-tag skx-tag--score">제목 {{ titleScore }}%</span>
  <span class="skx-tag skx-tag--score skx-tag--score-content">내용 {{ contentScore }}%</span>
</template>
<template v-else-if="matchScore">
  <span class="skx-tag skx-tag--score">연관도 {{ matchScore }}%</span>
</template>
```

그리고 script에 computed 추가:
```typescript
const titleScore = computed(() => {
  const s = route.query.title_score;
  return s ? Math.round(Number(s) * 100) : undefined;
});
const contentScore = computed(() => {
  const s = route.query.content_score;
  return s ? Math.round(Number(s) * 100) : undefined;
});
```

(상세 페이지는 query param으로 점수를 전달받는 구조 — `openDetail` 함수에서 navigate 시 `title_score`, `content_score` query 추가도 함께 수정)

- [ ] **Step 4: openDetail에 score query param 추가**

`index.vue`의 `openDetail` 함수에서 navigate URL에 score 파라미터 추가:
```typescript
function openDetail(item: BookChunkGroup) {
  const params = new URLSearchParams({
    q: currentQuery.value,
    score: String(item.best_score),
  });
  if (item.title_score !== undefined)
    params.set("title_score", String(item.title_score));
  if (item.content_score !== undefined)
    params.set("content_score", String(item.content_score));
  navigateTo(`/books/${item.book_id}?${params}`);
}
```

(`openDetail` 함수 현재 위치 확인 후 동일 패턴으로 수정)

- [ ] **Step 5: CSS 추가** (`style_skovix.css` 끝에 추가)

```css
/* ── 연관도 이원화 태그 ────────────────── */
.skx-tag--score-content {
  background: var(--green-lt, #ecfdf5);
  color: var(--green, #047857);
  border-color: var(--green-border, #a7f3d0);
}
```

- [ ] **Step 6: 동작 확인**

- 백엔드가 `title_score`/`content_score`를 아직 안 내려주므로 기존 "연관도 XX%" 단일 태그로 표시됨 (정상)
- 타입 에러 없이 빌드 확인: `npx nuxi typecheck` (또는 개발서버 실행 후 TypeScript 에러 없음 확인)

- [ ] **Step 7: 커밋**

```bash
git add frontend/types/search.ts frontend/pages/index.vue frontend/pages/books/[cnts_id].vue frontend/assets/css/style_skovix.css
git commit -m "[Feat] 연관도 이원화 타입/UI 준비 (제목+내용 분리, 백엔드 배포 후 자동 활성화)"
```

---

## 백엔드 별도 작업 (이 계획서 범위 외)

| 항목 | 내용 |
|------|------|
| 연관도 분리 API | `BookChunkGroup` 응답에 `title_score`, `content_score` 필드 추가. 프론트엔드는 준비 완료 상태 |
| 논문 연관도 정확도 | 논문 검색 점수가 너무 낮게 나오는 문제 — 임베딩/리랭크 파라미터 조정 |
