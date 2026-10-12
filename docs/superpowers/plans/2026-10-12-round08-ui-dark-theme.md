# round08 — UI 다크 테마 개편 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans. 단계는 `- [ ]` 체크박스.
> 사용자 방침(2026-10-11): 기획 문서에 토큰을 쓰지 않는다 — 이 계획은 작업·파일·검증 기준만 적고 코드 전문은 싣지 않는다. 구현자는 각 작업의 "기준"을 만족하게 직접 쓴다.

**Goal:** spec `docs/superpowers/specs/2026-10-12-round08-ui-dark-theme-design.md` 의 정책 1~8 을 nuxt 화면에 반영한다.
**Architecture:** 색은 `style_skovix.css` 의 `--skx-*` 변수만 다크 값으로 바꾸고(딥리서치 `research.css`·`work.css` 는 이미 이 변수만 쓰므로 손대지 않는다), 읽는 면은 변수를 밝은 값으로 다시 정의하는 `.skx-paper` 범위 클래스로 밝힌다. 화면 구조 변경은 `pages/index.vue`·`pages/papers/index.vue`·`components/AppSidebar.vue` 세 곳에 모은다.
**Tech Stack:** Nuxt 4 · Vue 3 · 전역 CSS(`nuxt.config.ts` css 배열: tailwind → style_skovix → research → work) · vitest(Node, 순수 함수만).

**검증 공통(작업마다):** `cd frontend && npx vitest run`(기준 40 files/739 통과) · 구조를 바꾼 작업은 `npx nuxi typecheck` · 화면은 로컬 미리보기 `http://localhost:3005`(운영 API, `NUXT_DEV_API_TARGET=https://skovix.landsoft.co.kr/api npx nuxi dev --port 3005 --host 0.0.0.0`)에서 확인. 커밋은 `[Feat]`·`[Style]`·`[Fix]` 꺾쇠 접두, Co-Authored-By 없음.

**손대지 않는 것:** `assets/css/research.css`·`work.css`(06d·06e 몫), 서버 코드, `pages/search-classic.vue` 삭제 금지, `public/css/style_skovix.css`(참조 없는 옛 사본 — 그대로).

---

## 테마 값 (Figma '임시 UI 개선' 2536:16697·2536:16720·2539:19954 에서 뽑음)

| 쓰임 | 값 |
|---|---|
| 바탕 | `#0f2822` + 배경 그림 `public/img/bg-glass.webp`(Figma 2282:13342, 1920×1080 → WebP 8KB, scratchpad `r08/bg-glass.webp`) cover·fixed |
| 유리 카드 | `rgba(255,255,255,.10)`·옅은 것 `.05`·청록 유리 `rgba(128,171,161,.10)`, `backdrop-filter: blur(4px)`, 테두리 `rgba(255,255,255,.12~.20)` |
| 불투명 면(딥리서치 등 `--skx-white` 자리) | `#16302a` 안팎 — 글자 대비 4.5:1 이상 |
| 글자 | 제목 `#ffffff` · 본문 `#cccccc` · 보조 `#b7bfbd` · 흐림 `#879491` · 청록 강조 `#80aba1` |
| 포인트 | 산호 `#f8c4b7`(진한 쪽 `#f4b19e`), 버튼 그라데이션 `#f8c4b7 → #fff5ed`, 위 글자 `#0f2822` |
| 반경 | 8px(카드 기본) · 12/16px(패널) · 44px(알약) |
| 글꼴 | Pretendard(이미 씀) |
| 밝은 읽는 면(`.skx-paper`) | 바탕 `#f6f5f2`, 카드 `#ffffff`, 글자 `#1d211f`·`#454545`·`#666`, 선 `#e3e1dc`, 포인트는 진한 산호 `#c9604a` |

---

### Task 1: 다크 토큰과 바탕

**Files:** Modify `frontend/assets/css/style_skovix.css`(:root 185-215·html/body 156-169·`.skx-app` 317-323·`.skx-footer` 5020 부근), `frontend/app.vue`(:root 23-47, body 55-61), `frontend/assets/css/tailwind.css`(스크롤바 색); Create `frontend/public/img/bg-glass.webp`(scratchpad 에서 복사); Test `frontend/tests/unit/themeTokens.test.ts`

- [ ] 실패하는 테스트: `style_skovix.css` 의 `:root` 블록을 읽어 `--skx-ink` 대 `--skx-white` 대비 4.5:1 이상, `--skx-gray-1` 대 `--skx-white` 4.5:1 이상, `.skx-paper` 블록의 같은 쌍도 4.5:1 이상을 검사한다(대비 계산은 테스트 안 작은 함수 — WCAG 상대 휘도).
- [ ] `--skx-*` 값을 위 표대로 바꾸고 새 토큰을 더한다: `--skx-glass`·`--skx-glass-2`·`--skx-glass-teal`·`--skx-glass-border`·`--skx-blur`·`--skx-accent`·`--skx-accent-strong`·`--skx-accent-grad`·`--skx-on-accent`·`--skx-ink-strong`·`--skx-teal-ink`. `--skx-primary` 는 산호로, `--skx-search-grad`·`--skx-page-bg` 는 다크로(바탕 그림 + `#0f2822`).
- [ ] html/body 글자색·`.skx-footer` 바탕 하드코딩을 토큰으로. app.vue 의 `--bg`·`--surface`·`--ink*`·`--line*` 은 **그대로 둔다**(search-classic·TopResult·CitationModal 이 쓰는 밝은 체계 — Task 7 에서 `.skx-paper` 로 감싼다). body 바탕은 `var(--skx-page-bg)`.
- [ ] `.skx-paper` 범위 클래스: 안에서 `--skx-*` 를 표의 밝은 값으로 다시 정의하고 `color: var(--skx-ink)`.
- [ ] 테스트 통과·vitest 전체·커밋 `[Style] round08 — 다크 글래스 토큰·바탕·.skx-paper`.
- **기준:** 미리보기에서 바탕이 다크 그림, 딥리서치 화면(`/research/<아무 잡>`)도 다크 면으로 깨지지 않고 읽힌다(남는 어긋남은 기록만 — 06d·06e 머지 뒤 맞춤).

### Task 2: style_skovix.css 하드코딩 색 → 토큰

**Files:** Modify `frontend/assets/css/style_skovix.css`(약 280곳)

- [ ] `#333`·`#454545`·`#111` → `var(--skx-ink)`, `#666` → `--skx-gray-1`, `#999` → `--skx-gray-2`, `#ccc`·`#ddd`·`#e*` 선 → `--skx-line`, 배경 `#fff` → `--skx-white`(또는 카드면 `--skx-glass`), 글자 `#fff` 가 진한 바탕 위면 `--skx-on-accent`, `rgba(0,0,0,.12)` 그림자·선 → `--skx-glass-border`. 색마다 쓰임(배경/글자/선)을 보고 바꾼다 — 기계 치환 금지.
- [ ] 쓰지 않는 `.skx-result-card--chat-open`·`.skx-chat-side`(4812-4878)는 손대지 않는다.
- [ ] 미리보기 메인·결과·상세에서 흰 바탕에 흰 글자 같은 깨짐이 없는지 확인 → 커밋 `[Style] round08 — style_skovix 하드코딩 색을 토큰으로`.

### Task 3: 아이콘 색

**Files:** Modify `frontend/assets/css/style_skovix.css`; 아이콘 `<img src="/img/*.svg">` 를 쓰는 템플릿(`pages/index.vue`·`pages/papers/index.vue`·`pages/papers/[id].vue`·`pages/books/[cnts_id].vue`·`components/AppSidebar.vue`·`components/BookChat.vue`)

- [ ] 단색 아이콘에 `skx-ico` 클래스(다크: `filter: brightness(0) invert(.82)`), 강조 아이콘에 `skx-ico--accent`(산호 근사 filter). `.skx-paper .skx-ico { filter: none }`.
- [ ] 기준: 사이드바·결과 카드·채팅 패널 아이콘이 다크에서 보이고, 밝은 읽는 면 안에서는 원래 색. 커밋 `[Style] round08 — 아이콘 색을 다크·밝은 면에 맞춘다`.

### Task 4: 목업 숨김

**Files:** Create `frontend/utils/featureFlags.ts`(`SHOW_MOCKS = false` 하나); Modify `components/AppSidebar.vue`(저장목록 46-51·프로필 129-135), `pages/index.vue`(북마크 525-534·신작도서 블록 255-285), `pages/books/[cnts_id].vue`(북마크 78-84), `pages/papers/[id].vue`(북마크 68-76)

- [ ] 각 요소를 `v-if="SHOW_MOCKS"` 로 감싼다(코드는 남김). `@save`·`@cart` 핸들러는 그대로 둬도 된다.
- [ ] 커밋 `[Feat] round08 — 동작 없는 목업(저장목록·북마크·프로필·신작도서 숫자)을 숨긴다`.

### Task 5: 사이드바 — [새 검색] · 딥리서치 묶음 · 최근 검색

**Files:** Create `frontend/utils/sidebarGroups.ts`; Test `frontend/tests/unit/sidebarGroups.test.ts`; Modify `components/AppSidebar.vue`(템플릿 55-126, scoped 272-402), `assets/css/style_skovix.css`(`.skx-lnb` 326-617)

- [ ] 실패하는 테스트: `groupSidebarHistory(items)` 가 `{ research, recent }` 를 돌려준다 — research 는 kind 'research' 만(진행 중 상태 먼저, 그다음 최신순), recent 는 kind 'book'·'paper' 를 최신순으로 섞고 각 항목에 종류 라벨('소장자료'·'논문'). 빈 입력·시간 같은 항목 순서 고정 사례 포함. 항목 모양은 `utils/historyStore.ts` 의 기존 타입을 쓴다.
- [ ] 구현 → 통과.
- [ ] 템플릿: 로고·접기 → [새 검색](`/` 로) → '딥리서치' 묶음(기존 배지 계산 206-222 재사용, 최대 5줄) → '최근 검색'(라벨 칩 + 질의 + 상대 시간, 기존 삭제 동작 유지). 탭(69-81)은 걷는다. `useHistory()`·폴링(234-253)·`collapsed` prop·`skx:lnb-open` 은 그대로.
- [ ] 유리 카드 스타일(`--skx-glass`·blur). 커밋 `[Feat] round08 — 사이드바를 새 검색·딥리서치 묶음·최근 검색으로`.
- **기준:** 기록 클릭 복원·삭제·전체 삭제·딥리서치 상태 배지 30초 갱신이 전과 같다. 06d N3(단계 표시)·06e H2(total)가 붙을 자리는 딥리서치 묶음 줄·묶음 머리다.

### Task 6: 메인 — 세 갈래 전환

**Files:** Modify `pages/index.vue`(hero 11-20·탭 23-70·`setMode` 806-809·도서 패널 73-160·논문 패널 163-252), `assets/css/style_skovix.css`

- [ ] 전환 [소장자료 검색 · 논문 검색 · 딥리서치]: '딥리서치'는 논문 패널 + `SearchPlusMenu` 의 `activateMode('deep-research')`(papers/index.vue 893-902 와 같은 방식), 다른 갈래로 가면 모드 해제.
- [ ] hero: 로고 'skovix' + 한 줄 '넓게 찾고 깊게 확인하는, 도서관의 AI 탐색'(소개서와 같은 말). 입력창은 유리 카드.
- [ ] '컬렉션 N권' 드롭다운(110-143) 제거(`collectionSize`·`COLLECTION_SIZES` 도 걷는다 — 컬렉션은 Task 7 에서 없앤다). '내 상황에 맞는 도서 추천받기'는 소장자료 갈래에서만 작은 링크로.
- [ ] 예시 칩은 기존 `SUGGESTIONS` 그대로(운영 검증 예시), 카드 모양만 유리로.
- [ ] 커밋 `[Feat] round08 — 메인을 세 갈래 전환·유리 입력창으로`.

### Task 7: 검색 결과 같은 틀 + DeepRead 옆 패널

**Files:** Modify `pages/index.vue`(결과 290-630·AI 큐레이션 334-422·카드 471-608), `pages/papers/index.vue`(AI 76-191·카드 356-461·채팅 패널 548-571), `assets/css/style_skovix.css`, `components/CitationModal.vue`(모달 안쪽에 `.skx-paper`)

- [ ] 소장자료 결과의 AI 영역(사용자 결정 2026-10-12 — 초기 SKOVIX 와 같게): **1위 도서 한 권 + 질문 기준 추천 이유 스트리밍**. 논문과 같은 2단(`.skx-pai` 구조) — 왼쪽 추천 이유(도서 상세 '추천 이유' 탭이 쓰는 스트리밍 API·`pages/books/[cnts_id].vue` `streamReason` 과 같은 호출, 접고 펼치기), 오른쪽 1위 도서 카드(표지·제목·서지·[DeepRead]·[원문 보기]). 컬렉션 호출(`useCuration`·`/books/curate`)과 'AI 컬렉션' 태그·위로 고정은 걷는다(composable 파일은 남겨도 됨). 제목은 'AI 검색 결과'.
- [ ] 카드 공통 배치: 왼쪽 표지 · 가운데(관련도·키워드 칩, 제목, 서지) · 오른쪽 버튼 열([원문 보기][인용(논문만)] / 강조 [DeepRead]). 논문 카드의 `:data-anchor`(360) 유지.
- [ ] DeepRead: 소장자료·논문 결과 카드 모두 `chatPaperId`(papers/index.vue 633 방식)로 오른쪽 패널을 연다. index.vue 에 같은 `aside.skx-chat-panel` + `BookChat` 을 둔다(새 부품 만들지 않음). 패널은 다크 유리.
- [ ] '총 N건 · 정렬'(논문 194-341) 줄을 유리 바 모양으로. 소장자료에는 새 정렬을 만들지 않는다.
- [ ] AI 결과 아래 06d N4·N6 가 들어올 자리는 비워 두고(빈 DOM 없음), 계획 비고에만 적는다.
- [ ] 커밋 `[Feat] round08 — 소장자료·논문 결과를 같은 틀로, DeepRead 는 옆 패널`.
- **기준:** 결과 → DeepRead → 패널 대화 → 닫기, 원문 보기(PdfViewer), 인용 모달, 뒤로가기 위치 복원(`restorePosition`) 이 전처럼 된다.

### Task 8: 상세 화면 — 틀 다크, 읽는 면 밝게

**Files:** Modify `pages/books/[cnts_id].vue`(`div.skx-result-card` 30-414), `pages/papers/[id].vue`(`div.skx-result-card` 8), `pages/search-classic.vue`(루트), `components/PdfViewer.vue`(필요하면)

- [ ] 두 상세의 `.skx-result-card` 에 `skx-paper` 를 더한다. 오른쪽 `aside.skx-chat-panel` 은 다크 그대로. 인라인 `#c00`·`#bbb`·`#999`(books 19·278·284, papers/[id] 283·320·335, index 326, papers/index 70·91·348)는 토큰으로.
- [ ] `search-classic.vue` 루트에도 `skx-paper` — 옛 화면은 밝게 남는다(지우지 않음).
- [ ] 커밋 `[Style] round08 — 상세는 다크 틀 안에 밝은 읽는 면`.

### Task 9: 전체 확인·정리

- [ ] vitest 전체 · `npx nuxi typecheck` · `npm run build`.
- [ ] 미리보기 스크린샷: 메인(세 갈래 각각) · 소장자료 결과 · 논문 결과 · DeepRead 패널 · 사이드바 접힘/펼침 · 두 상세 · 딥리서치 진행/보고서 · `/recommend` · `/search-classic` · 모바일 폭(390px) 한 번.
- [ ] 영역별 정적 리뷰(`.claude/agents/code-reviewer.md`) → 반영.
- [ ] 문서: 완료노트(`docs/roadmap/round08-완료노트.md`)·`00_status.md` 한 줄·06d·06e 에게 넘길 말(겹치는 N1·N3·N4·N6·R6·H2 의 새 자리) — 짧게.
- [ ] dev 머지·nuxt 배포는 사용자 승인 뒤.
