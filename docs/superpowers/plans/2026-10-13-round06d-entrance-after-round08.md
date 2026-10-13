# round06d 둘째 부분 — 입구·스타일 (round08 뒤 — 2026-10-13 개정, 같은 날 최종 결정 A~G 반영) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** round06d 의 둘째 부분(입구·스타일)을 round08(UI 다크 테마 — dev `bae4d75`, 테마 구조·핑크 `7adf93b` 까지) 위에 다시 쓴다. 원 계획 `docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md`(이하 **원 계획**)의 Task D8·L6·N1~N9·Z1~Z7 을 2026-10-12~13 사용자 결정과 **2026-10-13 최종 결정 A~G**(이 계획의 앞 글보다 우선 — '1-1')로 고친 것이다 — 별도 `/research` 홈 없이 DeepResearch 시작은 메인 입력창 + DeepResearch 모드 하나, 사이드바 [+ 연구 시작하기]는 늘 메인에서 새 연구(끝나지 않은 연구로 가는 분기 없음), DeepResearch 모드가 켜진 입력창(+ 메뉴 `SearchPlusMenu` 안)에 끝나지 않은 연구 한 줄 [보기]·[취소](한 번 확인), 메인 DeepResearch 모드의 예시 연구 카드, 사이드바 진행 중 줄의 단계 글(숫자 없이 — 기록의 상태만)과 '이전 연구 [n]'(시안 C), 탐색 방식(폭넓게 · 정밀하게, 기본 정밀하게), 연구 화면 머리·옆 칸·큰 진행 막대의 다크 토큰 맞춤과 보고서·절 자리의 읽기용 짙은 유리(`--skx-read-*` — `.skx-reading` 은 화면에 쓰지 않는다), "이렇게 이해했어요" 바인딩, 소장자료 결과 [DeepResearch로 이어서 조사하기](자르는 순서 1), 조건부 LNB 접기. 소장자료 결과 [담기 ▾]는 **보류**(사용자 답 대기 — 답이 없으면 하지 않는다). **nuxt 만이다** — 백엔드·스키마 변경 없음. 같은 브랜치 `feat/round06d-research-progress-screen` 에서 06d 앞부분(원 계획 D1~D7·L1~L5)이 끝나고 dev 를 받은 뒤(2026-10-13 `a084ff3` — 받음) 시작하고, 마무리(Z)는 06d 전체를 한 번에 dev 에 머지해 round08 운영 반영 **뒤에 따로** nuxt 로 배포한다(10/17~18).

**Architecture:** 판단은 모두 `utils/*.ts` 순수 함수에 두고 vitest 로 잰다 — `.vue` 는 그 결과를 그리기만 한다(프론트 vitest 는 node 환경). DeepResearch 를 시작하는 입력창의 판단은 `utils/researchStart.ts`(이 브라우저 기록에서 끝나지 않은 연구 — 진행 중·승인 대기 — 를 골라 한 줄의 글·[보기] 갈 곳·[취소] 잡 id 와 두 번 누르기 확인을 정한다)와 그것을 계산하는 `composables/useResearch.ts` 의 `useResearchStarter()` 한 곳이고(시작·알림 줄·취소 — 취소는 기존 `useResearchApi().cancel`), 그 줄은 공용 입력창 부품 `SearchPlusMenu.vue` 안에 있어 메인·`/papers`·논문 결과 검색바 어디서나 같다. 사이드바(`AppSidebar.vue`)의 [+ 연구 시작하기]는 round08 그대로 늘 새 연구이고, 진행 중 줄의 단계 글은 기록 응답의 상태·stage 만으로 정한다(`utils/sidebarResearch.ts` — 잡을 따로 읽지 않는다). 예시 연구는 `GET /api/research-works?example=1` + 예시마다 `GET /api/research/{id}/work` 의 `corpus`(`utils/researchExamples.ts`·`composables/useResearchWorks.ts` — `useState` 로 앱에서 한 번). 탐색 방식은 원 계획 N9 그대로(`utils/researchMode.ts`·`ResearchModePicker.vue` — + 메뉴에만). 다크 맞춤은 `research.css` 의 토큰 규칙(글자색에 `--skx-white` 를 쓰지 않고 산호 바탕 위 글자는 `--skx-on-accent`, 막대 빛은 `--skx-frost-line`, 카드·머리·막대 가장자리는 `--skx-frame-line`·`--skx-frost-hilite`)과 보고서·절 자리의 읽기용 짙은 유리(`.rs-card.rs-report` — `--skx-read-surface`·`--skx-read-*`)이고, 새 가드 테스트 `themeResearch.test.ts` 가 `research.css`·사이드바 스타일의 색 리터럴 0·`:root` 토큰만·이 규칙들·화면의 `.skx-reading` 0 을 지킨다(흰 종이에 찍는 인쇄 전용 문서만 `.skx-reading`).

**Tech Stack:** Nuxt 4(4.4)·Vue 3.5·TypeScript, vitest 3.2(node 환경 — DOM 없음), `nuxi typecheck`(vue-tsc), CSS(`assets/css/research.css` — `--skx-*` 토큰만, `AppSidebar.vue` scoped), round08 의 다크 토큰(`style_skovix.css` `:root` — 테마 블록 `html[data-theme="pink"]` 가 같은 토큰을 다시 선언)·읽기용 짙은 유리 토큰(`--skx-read-*`). 백엔드(Python 3.11·FastAPI·pytest)는 고치지 않고 회귀로만 돌린다.

---

## 1. 머리

### 1-1. 원 계획과 바뀐 것 — 원 Task → 처분

사용자 결정(2026-10-12~13 — 이 계획이 원 계획·spec 보다 우선)의 번호를 '결정 n' 으로 부른다: 결정 1 별도 시작 페이지 없음·시작 로직 한 곳, 결정 2 [+ 연구 시작하기] 분기·메인 알림 줄, 결정 3 예시 연구 카드, 결정 4 사이드바 단계 문구·이전 연구 [n], 결정 5 탐색 방식, 결정 6 round08 인계, 결정 7 D8 다크, 결정 8 L6·N8.

**2026-10-13 최종 결정 A~G(결정 1~8 과 이 계획의 앞 글보다 우선 — 아래 표·정함·Task 가 이것을 따른다):**
- **A** [+ 연구 시작하기](사이드바)는 늘 메인에서 DeepResearch 모드로 새 연구를 시작한다 — '끝나지 않은 연구가 있으면 그 연구 화면으로 이동'(결정 2 의 분기)은 없앤다(대회 시연에서 이전 연구로 가면 이상하다).
- **B** 끝나지 않은 연구(created·planning·approved·queued·running, 또는 승인 대기 awaiting_approval)가 이 브라우저에 있으면 공용 입력창 부품 `SearchPlusMenu.vue` 안에, DeepResearch 모드가 켜졌을 때 한 줄: '진행 중인 DeepResearch 1건 · [보기] [취소]'(승인 대기만 있으면 '승인 대기 중인 DeepResearch 1건 · [보기] [취소]'). [취소]는 기존 취소 API(`useResearchApi().cancel`)·한 번 확인('정말 취소'). 줄이 + 메뉴 안이라 메인·논문 결과(`/papers`)·논문 상세에서 온 입력창 어디서나 같다. 색·모양은 round08 의 팝오버·칩 토큰(`--skx-*` 만). 서버의 승인 429 `browser_active` 는 그대로(마지막 안전망). 시연 메모: 손님이 중간에 떠나면 [취소] 한 번(새로고침으로는 안 풀린다 — 잡은 서버에서 돌고 브라우저 ID 는 localStorage).
- **C** 보고서 본문·탐색 중 절 자리·연구 화면 면은 다크로 — `.skx-reading`(밝은 면)을 쓰지 않고 round08 의 읽기용 짙은 유리 토큰(`--skx-read-surface`, 글 `--skx-read-ink`·`--skx-read-ink-2`·`--skx-read-gray-1`, 줄간격 1.6, 흐림·반사광 없음). `research.css` 의 불투명 흰 카드 면은 06d 범위에서 `--skx-*` 토큰으로만. 색 리터럴 금지(테마 가드).
- **D** 사이드바 진행 중 줄의 단계 글은 숫자 없이 상태에 맞는 짧은 글(계획 중·근거 수집 중·보고서 작성 중), history 응답의 상태만으로 — 진행 중 잡을 30초마다 `GET /api/research/{id}` 로 읽지 않는다. 완료 줄에는 아무것도 붙이지 않는다. 진행 중 배지·'진행 중 N'은 round08 자리 그대로, '더 보기'는 시안 C('이전 연구 [n]' + 칩 + ⌄) 그대로.
- **E** [담기](원 N6·P8 8-2)는 **자른다**(사용자 2026-10-14 — 참고문헌·보고서는 자동화 방향이고 시연 흐름에도 없다). 마무리의 회귀 수·파일 목록에서 뺀다. 소장자료 결과 [DeepResearch로 이어서 조사하기](P8 8-1)는 [담기]와 별개라 남긴다(P8 머리).
- **F** 배포 순서: round08 은 이미 운영 이미지(`nl-lib-nuxt:latest`, `6b90e79` 기준)로 올라가 있고 운영 재배포만 남았다 — round08 을 먼저 운영에 반영하고 06d 는 그 뒤 따로 배포한다(Z4 Step 1·Z5 Step 0·롤백). `6b90e79` 에는 핑크 테마 구조가 없어(2026-10-13 확인) 핑크는 dev 로 빌드하는 06d 배포에 함께 나간다 — Z4 Step 2 에서 사용자에게 보인다.
- **G** 핑크 테마 브랜치(`feat/theme-pink`, `1b0eaa4`)와의 dev 머지 순서는 사용자가 정한다 — 06d 가 먼저 들어가면 핑크 쪽이 rebase, 반대면 06d 가 rebase(Z4 Step 1 의 확인 한 줄). **2026-10-13 확인(계획을 고친 때):** 핑크는 이미 dev 에 머지돼 있고(`7adf93b Merge feat/theme-pink into dev`, `origin/dev` 도 같다) 06d 브랜치도 그 dev 를 받았다(`a084ff3 Merge dev into feat/round06d-research-progress-screen — round08 UI 다크 테마·테마 구조(핑크) 받기`) — 그대로면 rebase 할 쪽이 없다. Z4 Step 1 이 다시 본다.

| 원 Task | 처분 | 이 계획 | 까닭 |
|---|---|---|---|
| (없음) | 새로 | **P1** dev 받기 확인·회귀 기준선 | 둘째 부분은 앞부분 + round08 위에서 시작한다. 앞부분 브랜치가 dev 를 받을 때 `[id].vue` import 한 곳이 부딪힌다(2026-10-13 `git merge-tree` 실측) |
| D8 머리·옆 칸 skx 토큰 | 고침 | **P2** | 결정 7 → **최종 결정 C** — round08 에서 `--skx-white` 가 짙은 청록(#152e28)이 되어 '글자색 --skx-white' 6곳·막대 빛 흐름이 뜻과 어긋난다. 카드 가장자리·막대 그림자·머리 칩·옆 칸 머리를 다크 토큰으로, 보고서·절 자리는 읽기용 짙은 유리(`--skx-read-*` — `.rs-card.rs-report` 한 규칙, `[id].vue` 는 고치지 않는다). `.skx-reading` 은 화면에 쓰지 않는다(흰 종이에 찍는 인쇄 전용 문서만 — 판단, P2 '알아 둘 것') |
| L6 dev 받기·"이렇게 이해했어요" 바인딩 | 고침 | **P7** | 결정 8. 06c 는 브랜치를 딴 dev(`d261476`)에 이미 있다(`ef202fb` ⊂ `d261476`, PlanCard `questionUsed` prop·`questionUsedFromSteps`·`understoodLine` 이 브랜치에 있음) — 원 L6 의 dev 받기·충돌 Step 은 없고 바인딩 두 곳만 |
| N1 문구 '소장자료검색' | 없앰 | — | 결정 6 — round08 이 메인 전환을 두 갈래(자료 검색 · 논문 검색 — `pages/index.vue:16`·`:53` '자료 검색어')로, 사이드바 탭을 걷고 최근 검색 칩을 '소장자료'(`utils/sidebarGroups.ts:28`)로 정리했다. `grep -c "도서검색" pages/index.vue` = 0. 남은 것 없음 |
| N2 기록 목록 total(`totalOf`) | 없앰 | — | 결정 1·4 — '모두 보기 (N)' 를 만들지 않으므로 total 을 읽을 곳이 없다. 06e 의 history total 백엔드는 06e 몫으로 남고 06d 프론트는 읽지 않는다 |
| N3 사이드바 단계·폴링·모두 보기 (N) | 고침 | **P3** | 결정 4 → **최종 결정 D** — 단계 글은 '진행 중' 줄에만, 숫자 없이 기록의 상태만으로(잡을 읽지 않는다 — 앞 개정의 잡 GET·`collectPosition` 도 없앰), 이어간 연구 줄의 단계·수·'생성 중'(원 정함 13)·생성 폴링은 넣지 않는다, '모두 보기 (N)' 없음, round08 의 '더 보기 (n) ▾' 를 시안 C '이전 연구 [n]' 으로 |
| N4 빠른검색 [딥리서치로 더 깊게] | 없앰 | — | 결정 6 — round08 이 논문 결과에 `.skx-deeper` [DeepResearch로 이어서 조사하기](`pages/papers/index.vue:170-174`·`continueAsDeepResearch` `:733-738`)로 만들었다. 소장자료 결과 쪽은 P8 8-1 |
| N5 `/research` 홈 | 없앰 | — | 결정 1. 예시 연구는 P5, 시작 판단은 P4 |
| N6 빠른검색 [담기 ▾] | **없앰(사용자 10-14)** | P8 8-2(하지 않는다) | 결정 6 → **최종 결정 E** — 사용자 답 대기, 답이 없으면 하지 않는다(기본은 자름). 계획 글(자리 `pages/index.vue:312` 의 'SKOVIX 추천 1권' 패널 아래, 담는 것은 추천 1권, 본문 `{"state": "in"}`)은 P8 Step 7~11 에 기록으로 둔다. 같은 자리의 소장자료 [DeepResearch로 이어서 조사하기](P8 8-1)는 한다 |
| N7 사이드바 예시 묶음 | 없앰 | P5 가 갈음 | 결정 3 — 예시 연구는 메인 DeepResearch 모드의 입력창 아래 한 곳 |
| N8 (조건부) LNB 접기 | 그대로 | **P9**(조건부) | 결정 8 — 06e 정함 30 계약 그대로, 앵커는 round08 뒤 `[id].vue:3-7`(그대로 남아 있다) |
| N9 탐색 방식 | 고침 | **P6** | 결정 5 — `/research` 홈 Step 8 없음, `ResearchModePicker` 는 + 메뉴(`SearchPlusMenu.vue`)에만, 다크 토큰(고른 칸 = 짙은 면·산호 글자, 홈 = 흰 10%), 입력 상자 아래 줄이 모자라면 줄바꿈 |
| (없음) | 새로 | **P4** 입력창(+ 메뉴) 안 끝나지 않은 연구 한 줄 [보기]·[취소] | 결정 1·2 → **최종 결정 A·B** — [+ 연구 시작하기] 분기 없음(늘 새 연구 — `AppSidebar.vue` 를 고치지 않는다), 줄은 메인 페이지가 아니라 `SearchPlusMenu.vue` 안, [취소]는 기존 취소 API·한 번 확인 |
| (없음) | 새로 | **P5** 예시 연구 카드 | 결정 3(원 N5 의 `exampleMeta`·`exampleRoute`·`listWorks` 를 옮겨 쓴다) |
| Z1~Z7 마무리 | 고침 | **Z1~Z7** | 06d 전체(앞부분 + 둘째 부분)를 한 번에 — 경계 목록·리뷰 영역·문서 구절·배포 확인 항목(`/research` 는 404 그대로). **최종 결정 F·G** — round08 을 먼저 운영 반영하고 06d 는 그 뒤 따로(Z4 Step 1·Z5 Step 0·롤백), 핑크와의 dev 머지 순서 확인 한 줄(Z4 Step 1) |

### 1-2. round08 뒤 코드 사실(2026-10-13 확인 — 읽기 전용 worktree `.worktrees/dev-read` = dev `bae4d75`, 앞부분 브랜치 `11072c4`)

- **2차 확인(같은 날 최종 결정을 반영할 때 — 이 줄이 아래 줄보다 새것):** 06d 브랜치는 L4·L5(`6f23179`·`d0f7a03`·`9f7c485`)가 끝나고 dev `7adf93b`(round08 + 핑크 테마 구조 — `1b0eaa4`·`94b56df`)를 받았다(`a084ff3` — P1 의 (가)). 핑크는 `style_skovix.css`(테마 블록 `html[data-theme="pink"]` 와 `html[data-theme="pink"] .skx-reading` — `:root` 의 토큰을 다시 선언만 한다)·`AppSidebar.vue`(톱니 `SettingsMenu` — `:258` 아래, 06d 앵커 밖)·`tests/unit/helpers/themeCss.ts`(테마 토큰 읽기 — `rootDecls`)·`utils/theme.ts`·`composables/useTheme.ts`·`nuxt.config.ts` 를 더하거나 고쳤고 `research.css`·`SearchPlusMenu.vue`·`useResearch.ts`·`pages/index.vue`·`landingStart.ts` 는 고치지 않았다. 핑크에서 `--skx-on-accent` 는 밝고(#f2f2f0) `--skx-primary`·`--skx-ink-strong` 은 짙다(#1a1115) — 테마마다 뒤집히는 토큰이 있어 P2 는 두 테마에서 같은 뜻인 토큰만 고른다. 사본(`a084ff3` — 저장소 밖 `git clone --shared`, `node_modules` 는 `round06d` 의 것을 정션) 실측: vitest `59 / 1231`, typecheck `error TS` 0, `Duplicated imports` MetaPart 2. 아래 줄 번호는 이 사본에서도 맞다 — 다만 `AppSidebar.vue` 는 `:258` 아래(script·scoped CSS)가 한 줄 밀렸고(예: `RESEARCH_ROW_LIMIT` `:294`·`startDeepResearch` `:447`·`.skx-history__more` `:635`), `style_skovix.css` 는 테마 구조가 `:root` 를 늘려 그 아래가 밀렸다(아래 줄의 `style_skovix.css` 번호는 `a084ff3` 값으로 적었다 — 2026-10-13 검증 때 고침).
- **취소 API·입력창 자리(P4):** `POST /api/research/{id}/cancel`(`app/api/research.py:342-361`)은 `CANCELLABLE_STATUSES`(created·planning·awaiting_approval·approved·queued·running — `:60-63`)에서만 전이하고 아니면 409 '취소할 수 없는 상태입니다'. 프론트는 `useResearchApi().cancel`(`composables/useResearch.ts:48-49`). + 메뉴 뿌리 `.rs-plus` 는 랜딩 입력 상자에서 grid 의 `plus` 칸(`.skx-search__box` — `style_skovix.css` `[S] 검색 입력`), 결과 검색바에서는 높이 3.2rem 알약(`.skx-rsearch` — `position: relative`) 안의 flex 칸이다. 오류 줄 `.rs-plus__error` 는 그 상자·바 아래에 절대 위치로 뜬다(`research.css` `.rs-plus__error`).
- **읽기용 짙은 유리 토큰(P2):** `:root` 의 `--skx-read-surface`(다크 `rgba(8, 22, 19, 0.62)` · 핑크 흰 55%)·`--skx-read-ink`·`--skx-read-ink-2`·`--skx-read-gray-1` — 결과 화면의 읽는 칸(`.skx-pai-main`·`.skx-pai-refs`·`.skx-pick__main`·`.skx-pick__book` — 바탕 `--skx-read-surface`·테두리 `--skx-frost-menu-line`, 그 칸 안에서 `--skx-ink` 등을 다시 정의)과 상세의 큰 틀(`detail.css` `.dt-frame`)이 쓴다. `ReportView.vue`·`ReportSkeleton.vue` 의 뿌리는 `<article class="rs-card rs-report …">` 다.

- **브랜치·머지:** 06d 브랜치는 `d261476`(06c 배포 기록 머지 — 06c `ef202fb` 포함)에서 땄고 지금 L3 spec 검토 반영(`11072c4`)까지다 — D7 품질 검토 반영 1~3(`66cd46c`·`1a6b9fd`·`2b4ed7d`)·L3(`5e69e48`)이 끝났고 **L4·L5 가 남았다**. `11072c4` 에 dev `bae4d75` 를 합친 사본(저장소 밖 `git clone --shared`)의 충돌은 `frontend/pages/research/[id].vue` 한 곳 — 06d 의 `import { queueLine } from "~/utils/queueLine";`(Task D2) ↔ round08 의 `import { DEEP_RESEARCH } from "~/utils/brand";`(같은 자리 — `import { safeLocalStorage } from "~/utils/browserId";` 바로 아래). round08 이 고친 연구 쪽 파일은 `[id].vue`(그 import·`useHead` 두 줄)·`ResearchHeader.vue`(kicker `{{ DEEP_RESEARCH }}`)·`SearchPlusMenu.vue`(`update:mode`·`clearMode`·`DEEP_RESEARCH`)·`utils/researchErrors.ts`(429 `browser_active` 문구를 `${DEEP_RESEARCH}` 로 — 06d 둘째 부분은 읽기만)뿐이고 `research.css`·`work.css` 는 고치지 않았다(round08 계획 '손대지 않는 것').
- **06e:** dev 에 없다(`git log --merges dev | grep -c round06e` = 0). 06e 브랜치도 `d261476` 에서 땄고 `[id].vue`·`work.css`·`pages/papers/index.vue`·`BookChat.vue`·`workPhase.ts` 등을 고친다 — `AppSidebar.vue`·`pages/index.vue`·`SearchPlusMenu.vue`·`useResearch.ts`·`research.css`·`ResearchHeader.vue` 는 고치지 않는다.
- **사이드바 `components/AppSidebar.vue`(round08):** DeepResearch 묶음 `:107-187` — 머리 `:108-122`, [+ 연구 시작하기] `:123-125` → `startDeepResearch`(`:446-449`, `router.push(deepResearchStartRoute())`), 줄의 배지 `:161` 뒤 `<!-- 06d: 단계 문구(stage text)는 이 배지 옆에 붙인다 -->`(`:162`), '더 보기 (n)' 버튼 `:176-185`, `<!-- 06d: 전용 화면으로 가는 '모두 보기 (N)' 줄 … -->`(`:186`). script: import `:273-287`(`landingStart` `:280`, `sidebarGroups` `:281-287`), `RESEARCH_ROW_LIMIT = 5`(`:293`), `researchHiddenCount`(`:333`), `badgeOf`(`:455-471` — completed·failed·canceled·awaiting_approval·없음 밖은 '진행 중'), `pollOnce`(`:476-479` — `history.refresh("research")`), 폴링은 `hasLiveResearch`(LIVE_STATUSES)일 때만·접혀 있어도 돈다, `onMounted`(`:499-517`). scoped CSS `.skx-history__more`(`:634-647`), 최근 검색 종류 칩 `.skx-history-chip`(`:704-713` — `--skx-glass-teal` 바탕·`--skx-teal-ink` 글자). 묶음 카드는 `--skx-teal-ink` 를 `--skx-research-teal-ink`(#80aba1)로 다시 정의한다(`:545-557`).
- **`utils/sidebarGroups.ts`(round08):** `LIVE_STATUSES = created·planning·approved·queued·running`(`:5`), `isLiveResearch(entry)`(`:30`), `hasActiveResearch`(`:39` — + awaiting_approval), `entryTime`(`:44`). **`utils/landingStart.ts`(round08):** `deepResearchStartRoute()`(`:8`)·`readStart`(`:13`)·`queryWithoutStart`(`:18`).
- **메인 `pages/index.vue`(round08):** 논문 패널 `:93-150`(`<ResearchSearchPlusMenu ref="plusMenu" … @update:mode="onPlusMode">` `:103-109`, 예시 칩 `:132-143`, 높이 맞춤 유령 링크 `:145-148`), 'SKOVIX 추천 1권' 패널 뒤 `<!-- 06d: [딥리서치로 더 깊게]·[담기] 는 이 패널 바로 아래(이 자리)에 … -->`(`:312`), `SUGGESTIONS`(`:399-410`), `deepResearch` ref(`:494` — + 메뉴의 `update:mode` 가 정본), `startFromQuery`(`:536-544`), `?start=` 감시(`:819-824`). 랜딩은 세로 가운데 정렬(`.skx-contents` `align-items: center` — `style_skovix.css:1351-1359`).
- **`components/research/SearchPlusMenu.vue`(round08):** 칩·오류 `:40-44`, import `:80-84`(`brand` `:82`), `useResearchStarter()` `:106`, 상태 `:113-115`, `activate` `:136-140`, `submit` 의 `startResearch(plan.question)` `:365`, `onMounted` `:405-415`. 랜딩 입력 상자에서 `.rs-plus` 는 상자의 아래 줄 왼쪽 칸이다(`.skx-search__box > .rs-plus { grid-area: plus }` — `style_skovix.css:1526`).
- **`composables/useResearch.ts`:** `useResearchStarter()`(`:53-69`) = `startResearch(question)`(만들기 + 기록) 하나.
- **토큰(`style_skovix.css` `:root` `:270-440`):** `--skx-white` #152e28(불투명 면), `--skx-on-accent` #0f2822(산호 위 글자), `--skx-ink-strong` #fff(제목), `--skx-ink` #ccc, `--skx-teal-ink` #80aba1, `--skx-glass-teal`, `--skx-frame-line`(흰 8%), `--skx-frost-hilite`(안쪽 위 하이라이트), `--skx-frost-bg`(흰 10%), `--skx-frost-menu-bg`·`--skx-frost-menu-line`(+ 메뉴 면), `--skx-shadow-banner`. `.skx-reading`(`:443-547`)은 같은 이름을 밝은 값으로 다시 정의한다(`--skx-white` #fff·`--skx-on-accent` #fff·`--skx-frame-line` #e3e1dc·`--skx-frost-hilite` none, 끝에 `color`·`background: var(--skx-page-bg)`). **지금 마크업에서 `.skx-reading` 을 쓰는 곳은 없다** — round08 이 뒤에 상세를 '전체 짙은 유리'로 바꿨다(`assets/css/detail.css:5`). 06d 도 화면에는 쓰지 않는다(최종 결정 C — 흰 종이에 찍는 인쇄 전용 문서만, P2).
- **`research.css`(round08 이 고치지 않음 — 앞부분 브랜치 줄):** 색 리터럴 0. 글자색 `var(--skx-white)` 6곳 — `.rs-btn`(`:148`)·`.rs-status--completed`(`:262`)·`.rs-plus__chip`(`:755`)·`.rs-plus__chip-x`(`:766`)·`.rs-synth__item.is-done .rs-synth__icon`(`:864`)·`.rs-pbar__stage.is-current`(`:1298`). `.rs-pbar__fill.is-running::after`(`:1351`)의 빛 흐름이 `color-mix(… var(--skx-white) 45% …)`. 인쇄 앵커 `/* ── 인쇄(PDF로 저장) ── … */` `:1474`(앞부분 L3 의 `.rs-round__state` 블록 `:1449-1472` 바로 아래), 인쇄 `.rs-print` `:1510`(줄 번호는 `11072c4` — 위 여섯 곳·빛 흐름은 L3 전과 같다).
- **기록 응답:** `HistoryResearchStatus` = `status`·`stage` + 이어간 연구에만 `phase`·`progress`·`generating`(`types/history.ts:70-79`, `app/repositories/history.py:227-237`). 진행 중 잡의 하위질문·절 수는 기록에 없다 → 잡(`GET /api/research/{id}` — `app/api/research.py:485-498`, steps 포함)을 읽어야 '3/6' 이 나온다 — 최종 결정 D 로 읽지 않고 숫자 없이 상태만 쓴다(P3). stage 는 `created → planned → explored → synthesized`(`app/models/research.py:32`) — 종합 중 잡은 `running` + `explored`.
- **예시·담기 API:** `GET /api/research-works`(`?example=1`)는 `{id, question, phase, created_at}` 만, 최근 것부터, 상한 50(`app/api/research_work.py:300-322`, 브라우저 ID 헤더 필수). `PUT /api/research/{id}/reading/{cnts_id}` 는 `Book` 표에 있는 cnts_id 면 소장자료도 받는다(`app/api/research_reading.py:63-64`·`:79`). 승인·재시도의 429 `browser_active`(`app/api/research.py:142-183`)는 그대로다 — 만들기(`POST /api/research`)는 막지 않는다.
- **한 이름 경고:** round08 뒤 `nuxi typecheck` 의 `Duplicated imports` 는 **2** — 둘 다 `MetaPart`(`utils/detailView.ts:23` · `utils/resultCard.ts:98`, round08). 원 계획의 '`Duplicated imports` 0' 은 이 계획에서 **'MetaPart 두 줄뿐'** 으로 읽는다(06d 가 고칠 파일이 아니다 — 완료노트 이월로 round08 에 넘긴다).
- **실측(2026-10-13 2차 — 최종 결정 반영 뒤, 저장소 밖 사본 `a084ff3`):** 이 계획의 P2~P7·P8 8-1 블록을 계획서 글 그대로(`old` 가 각각 한 번 맞음 — 계획서의 블록을 뽑아 얹는 스크립트로) 차례로 얹어 각 Task 의 실패·통과 수와 Task 마다 typecheck `error TS` 0·`Duplicated imports` MetaPart 2 를, 끝에서 전체 vitest `64 / 1272`·build `└  ✨ Build complete!`(한 이름 경고 MetaPart 둘)를 쟀다 — 각 Task 의 기대 수는 그 실측이다. 8-2([담기] — 보류)와 P9(조건부)는 이번에 재지 않았다(P9 는 앞 개정에서 06e 의 `workPanelOpen` 을 흉내 내어 typecheck 0 을 쟀다).
- **3차 검증(같은 날 — 최종 결정 A~G 반영본을 따로 검증):** 새 사본(`a084ff3`)에 P2~P7·P8 8-1 블록을 계획서 글 그대로 차례로 얹어 각 Task 의 실패(이름·수)·통과·전체 수(`60 / 1240` → … → `64 / 1272`)·typecheck 0·MetaPart 2 가 위 기대와 같았고, build 완료·Z1 Step 1 의 06d 묶음 열아홉 파일(`19 / 389`)·`researchDraft` 23·Z1 Step 2 의 마흔아홉 파일 목록과 경계 검사(고치지 않을 파일 빈 출력·단계 본문 그대로·색값 0·keyframes 1·'딥리서치' 0)·Z5 Step 6 의 번들 표식(`rs-pbar`·`rs-start-note` entry CSS, `skx-history__older` AppSidebar CSS, '정말 취소' JS, `rs-synth__bar` 0, `skx-holo` entry CSS)이 맞았다. 새 테스트에 변이 열넷(진행 중 우선·확인 창 400ms·최근 것 정렬·refId·취소 중 누름·stage explored·승인 대기 단계 글·버튼 글자 `--skx-white`·읽기 면 줄간격·색 리터럴·없는 토큰·카드 수·초안 공백·초안 길이)을 하나씩 넣어 모두 떨어졌다. 보류한 8-2 도 8-1 뒤에 얹으면 그대로 맞고(+1 파일·+4 — `65 / 1276`, typecheck 0), 06e 브랜치(`e55d5d9`)를 시험 머지하면 `pages/research/[id].vue` 는 자동으로 합쳐지고 충돌은 `pages/papers/[id].vue`(06e ↔ round08) 하나다. P8 Step 1 에 `queryWithoutStart` 묶음 이름 고침(이름만)을 더했다.

### 1-3. 실행 전 알아 둘 것

- **작업 위치:** worktree `C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d`(브랜치 `feat/round06d-research-progress-screen`). 모든 명령은 이 경로의 절대 경로로 쓴다. 저장소 루트(본 작업 폴더)와 다른 worktree(`.worktrees/dev-read`·`round06e`·`round08` 등)는 고치지 않는다 — 여러 세션이 같은 저장소를 쓴다. **본 작업 폴더에서 `git checkout`·`git stash` 를 하지 않는다**(2026-10-02 사고). dev 를 받을 때도 이 worktree 안에서 `git merge dev` 로 받는다.
- **앵커 규칙:** Edit 의 old 는 아래 각 Step 에 적은 글자 그대로다(줄 번호로 자리를 찾지 않는다). 줄 번호는 '1-2' 의 확인값(round08·앞부분 `11072c4` 기준 — 2차 확인 사본 `a084ff3` 에서도 맞음) — 이 계획의 앞 Task 가 같은 파일을 고쳤으면 밀려 있다. 기존 파일은 **Edit 도구로** 고친다(저장소 `core.autocrlf=true` — 작업 트리가 CRLF, Git Bash 의 sed·heredoc 은 LF 를 섞는다). 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다.
- **프론트 검증:** 파일 하나는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/<파일>`, 전체는 `… && npx vitest run`(끝의 `Test Files …`·`Tests …` 두 줄로 읽는다). 타입은 `… && npx nuxi typecheck 2>&1 | grep -c "error TS"`(기대 `0`), 한 이름 경고는 `… && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c`(기대 `      2 Duplicated imports "MetaPart"` 한 줄), 빌드는 `… && npm run build 2>&1 | tail -1`(기대 `└  ✨ Build complete!`). 각 Task 의 전체 vitest 기대는 **'앞 Task 뒤 수 + N'** 상대값이고, 괄호 안 절대값은 '1-2' 의 사본 실측(`a084ff3` — 2026-10-13 2차, P2~P8 8-1 을 계획서 글 그대로 얹어 잼)이다.
- **`.vue` 검증:** `.vue` 는 단위 테스트하지 않는다(node 환경, `@vue/test-utils`·jsdom 을 들이지 않는다). 판단·문구는 `utils/*.ts` 순수 함수로 빼서 vitest 로, `.vue`·`.css` 는 typecheck `0`·build 완료로, 움직임·배치는 Z1 Step 3(로컬 화면 — GET 만)과 Z6(운영)에서 본다. 프로젝트에 없는 패키지를 `npx` 로 받지 않는다. 대역은 `tests/unit/helpers/fakeHistory.ts`(`ID1`·`ID2`·`ID3`·`researchEntry`·`bookEntry`)·`helpers/memoryStorage.ts`(`MemoryStorage`)를 그대로 쓴다.
- **상수·이름:** Nuxt 자동 import 때문에 **한 이름은 한 파일만 내보낸다**. 새 이름은 '1-5 공통 계약' 의 파일에서만 export 한다(2026-10-13 `utils`·`composables`·`components`·`pages`·`types` 전수로 새 이름임을 확인 — `statusStageLine`·`olderToggle`·`researchStartState`·`startNotice`·`noticeCancelPress`·`noticeCancelLabel`·`NOTICE_CANCEL_ARM_MS`·`NoticeCancelStep`·`ResearchStartState`·`StartNotice`·`cancelResearch`·`pickExamples`·`exampleMeta`·`exampleRoute`·`EXAMPLE_CARD_MAX`·`readStartDraft`·`useResearchExamples`·`useResearchWorksApi` 등).
- **표기:** 화면 글은 `utils/brand.ts` 의 `DEEP_RESEARCH`('DeepResearch')로 쓴다 — 새 '딥리서치' 화면 글 금지(결정 6). 주석은 상관없다(Z1 Step 2 가 주석이 아닌 더한 줄의 '딥리서치' 를 센다).
- **CSS:** 새 블록은 `research.css` 의 인쇄 앵커 `/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */` **바로 위**에 넣는다(old = 그 한 줄, new = 자기 블록 + 빈 줄 + 그 한 줄) — P2 → P4 → P5 → P6 순서로 쌓인다(8-2 [담기]는 보류). 기존 규칙은 제자리에서 앵커 글자로 고친다. 새 색값(hex·rgb·rgba·hsl·색 이름)을 쓰지 않고 `--skx-*` 토큰만(P2 의 가드 테스트가 지킨다), 새 움직임은 `prefers-reduced-motion: reduce` 에서 멈춘다. 사이드바 스타일은 `AppSidebar.vue` 의 scoped 블록에 둔다(그 가드도 같은 테스트). 새 부품(`ResearchExampleCards`·`ResearchModePicker`)은 `<style>` 을 두지 않고 `research.css` 만 쓴다.
- **긴 글 접기(결정 6 — `components/ClampedPanel.vue`):** 둘째 부분이 새로 그리는 글에는 접고 펴는 긴 글이 없다 — 알림 줄은 한 줄, 사이드바 단계 문구는 한 줄 말줄임, 예시 카드의 질문은 리허설에서 고른 예시 질문(한두 줄)이다. 뒤에 접어야 할 긴 글이 생기면 새 접기를 만들지 않고 `ClampedPanel` 을 쓴다(예시 카드는 카드 전체가 링크라 그 안에 [더보기] 버튼을 넣지 않는다).
- **백엔드 회귀:** 06d 는 `app/` 를 한 글자도 바꾸지 않는다 — Z1 에서만 전체를 돌린다(`cd …/round06d/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors` — 실패 5·오류 1 은 로컬 의존성 기준선, 원 계획 머리 '기준선').
- **커밋:** `[Feat]`·`[Fix]`·`[Refactor]`·`[Test]`·`[Chore]`·`[Docs]` 접두어 + 한국어 서술형(`[Feat] round06d — …`). **`Co-Authored-By` 줄과 "Generated with Claude Code" 줄은 넣지 않는다**(사용자 규칙 — 다른 안내보다 우선). Task 마다 커밋 1~2개, `git add` 는 파일을 하나씩 적는다(`-A`·`.` 금지, 대괄호 경로는 따옴표로 — `"frontend/pages/research/[id].vue"`).
- **운영 금지:** P1~P9 의 어떤 Step 도 운영 서버·운영 DB 를 쓰지 않고 운영 API 에 쓰지 않는다. 운영 API 에 붙인 로컬 화면(`NUXT_DEV_API_TARGET` — `nuxt.config.ts` devProxy)에서 GET 만 하는 것은 된다 — 누르면 쓰는 버튼(승인·취소·입력창 한 줄의 [정말 취소]·[이 연구 이어가기]·DeepResearch 모드에서 보내기·[같은 질문으로 다시 시작])은 누르지 않는다 — 입력창 한 줄의 [취소] 첫 누름은 '정말 취소' 로 바꾸기만 해 써도 되고, [그대로 두기]로 되돌린다. `dev` 머지는 사용자 승인 뒤(Z4·Z7), 서버 명령은 **사용자가** 친다(Z5·Z6).
- **고치지 않는 파일:** `components/research/ReportView.vue`·`ReportSkeleton.vue`(보고서·절 자리의 면은 `research.css` 의 `.rs-card.rs-report` 로 준다)·`PlanCard.vue`(06c)·`CitationChip.vue`, `components/work/*`(06e — 근거 장부 `EvidenceLedger.vue` 는 앞부분 L5 몫), `components/BookChat.vue`, `utils/workPhase.ts`·`utils/researchErrors.ts`·`composables/useResearchWork.ts`·`types/work.ts`(06e — 읽기만), `utils/sidebarGroups.ts`·`utils/resultCard.ts`·`utils/detailView.ts`·`assets/css/style_skovix.css`·`assets/css/detail.css`(round08), `utils/theme.ts`·`composables/useTheme.ts`·`components/SettingsMenu.vue`·`tests/unit/helpers/themeCss.ts`(round08 테마 구조 — 핑크, `themeCss.ts` 는 읽기만), `pages/papers/index.vue`(round08·06e), `pages/search-classic.vue`(보존 화면), `work.css`(앞부분 L5 의 장부 블록 밖은 06e), `package.json`·`package-lock.json`, `app/` 전부·compose·`infra/`.

### 1-4. 이 부분에서 정한 것(정함 20~27 — 원 계획 정함 1~19 에 잇는다)

원 계획의 정함 13(사이드바 단계 줄 = `workPhase.stepLine` + 수 + '생성 중')·14('모두 보기 (N)')·15(`/research` 홈)·16([딥리서치로 더 깊게] = `/papers?draft=`)·18('소장자료검색' 문구)은 이 표가 갈음하거나 없앤다. 정함 17([담기] 본문 `{"state": "in"}`)·19(탐색 방식 — `/research` 홈 자리만 빠짐)는 그대로다. Z3 가 완료노트 §6 에 옮긴다.

| # | 결정 | 근거 |
|---|---|---|
| 정함 20 | **DeepResearch 시작 = 늘 새 연구, 끝나지 않은 연구는 입력창 안 한 줄(최종 결정 A·B 로 고침)** — 사이드바 [+ 연구 시작하기]는 round08 그대로 `/?start=deep-research`(끝나지 않은 연구로 가는 분기 없음). 입력창의 판단은 `utils/researchStart.ts` + `useResearchStarter()` 한 곳: 이 브라우저 기록(`useHistory().entries`)에서 진행 중(`sidebarGroups.LIVE_STATUSES` — 사이드바 배지 '진행 중'과 같은 상태)·승인 대기 연구를 가르고 각각 가장 최근 것부터(`entryTime`). DeepResearch 모드가 켜진 + 메뉴(`SearchPlusMenu.vue`) 안에 진행 중 → '진행 중인 DeepResearch n건 · [보기] [취소]', 승인 대기만 → '승인 대기 중인 DeepResearch n건 · [보기] [취소]'. [보기]·[취소]는 가장 최근 것, [취소]는 기존 취소 API·두 번 누르기('정말 취소' — 첫 누름 뒤 400ms 안의 누름은 받지 않는다) 뒤 기록 다시 읽기. **막지 않는다** — 보내기는 그대로, 서버의 승인 429 `browser_active` 가 마지막 안전망 | 최종 결정 A·B(2026-10-13 — 대회 시연에서 이전 연구로 가면 이상하다). 줄이 + 메뉴 안이라 메인·`/papers`·논문 결과 검색바(논문 결과·상세 `?draft=` 로 오는 길) 어디서나 같다. 기록 상태는 사이드바 폴링(30초)만큼 늦을 수 있어 막는 판단으로 쓰지 않는다. 손님이 중간에 떠난 연구는 새로고침으로 풀리지 않는다(잡은 서버에서 돌고 브라우저 ID 는 localStorage) — [취소] 한 번(시연 메모 — Z3 완료노트·Z6) |
| 정함 21 | **사이드바 단계 글 = 진행 중 줄에만, 숫자 없이 기록의 상태만으로(최종 결정 D 로 고침).** `statusStageLine`: created·planning → '계획 중', approved·queued → '대기 중', running → stage `explored`·`synthesized` 면 '보고서 작성 중', 아니면 '근거 수집 중'. 진행 중 잡을 `GET /api/research/{id}` 로 읽지 않는다(사이드바 네트워크는 round08 그대로). 완료·실패·취소·승인 대기 줄은 글 없음(배지가 말한다). 이어간 연구의 단계·수(원 정함 13)·생성 중 폴링은 넣지 않는다. 글자 `--skx-teal-ink`, 테두리·바탕 없음, round08 의 `<!-- 06d: 단계 문구 … -->` 자리(배지 바로 뒤) | 결정 4 → 최종 결정 D. 진행 중 잡의 수는 기록 응답에 없고('1-2'), 수를 내려고 30초마다 잡을 읽지 않는다. '대기 중' 은 결정 D 의 예(계획 중·근거 수집 중·보고서 작성 중) 밖 상태(approved·queued)에 맞춘 짧은 글 — 연구 어시스턴트의 생성 대기 글(`genQueueLine`)과 같은 말 |
| 정함 22 | **'더 보기 (n) ▾' → 시안 C '이전 연구 [n]'** — 묶음 맨 아래 구분선(`--skx-line`) 아래 한 줄: 왼쪽 '이전 연구' + 숨은 수 칩(최근 검색의 `.skx-history-chip` 그대로), 오른쪽 끝 ⌄(펼치면 뒤집힘). 펼치면 '접기'. aria-label '이전 연구 n건 더 보기'·'이전 연구 접기'(`olderToggle`). '모두 보기 (N)' 줄은 만들지 않는다 | 결정 4 |
| 정함 23 | **예시 연구 카드 = 메인 DeepResearch 모드의 입력창 아래 한 곳.** `GET /api/research-works?example=1` 의 앞 3개(`EXAMPLE_CARD_MAX` — 받은 순서 = 최근 것부터), 카드마다 '읽기 전용' 칩·질문·실행 시각(`corpus.at` KST)·코퍼스 범위(`scopeLine` — 연구 화면의 범위 띠와 같은 글), 누르면 도달한 단계 화면(`exampleRoute` — 사이드바의 이어간 연구 줄 `routeFor` 와 같은 규칙). 목록·시각·범위는 `useState` 로 앱에서 한 번만 읽는다. 예시가 없거나 못 읽으면 그리지 않는다. 사이드바에는 두지 않는다 | 결정 3. 원 N5 의 판단(`exampleMeta`·`exampleRoute` — 원 계획 정함 15 의 '예시마다 GET work 의 corpus')을 옮긴다. 예시는 리허설(10/23~25)에서 `scripts/research_eval/mark_example.py` 로 지정하기 전에는 없다 — 10/17~18 배포 직후에는 카드가 서지 않는 것이 맞다 |
| 정함 24 | **연구 화면 다크 맞춤(D8) — 토큰 규칙 + 읽기용 짙은 유리(최종 결정 C 로 고침).** ① 글자색에 `--skx-white` 를 쓰지 않고 산호 바탕(`--skx-primary`) 위 글자는 `--skx-on-accent` ② 막대 빛 흐름은 밝은 유리 선 `--skx-frost-line`(두 테마 모두 흰색 계열) ③ 카드·머리·막대 가장자리 = `--skx-frame-line` 1px + `--skx-frost-hilite`, 막대 그림자 `--skx-shadow-banner`, 카드 면은 불투명 면 `--skx-white` 그대로 ④ 머리 kicker 는 청록 칩(`--skx-glass-teal`·`--skx-teal-ink`), 질문 1.1rem·`--skx-ink-strong`, kicker·상태 배지는 단계 칩과 같은 크기(원 D8) ⑤ 옆 칸 카드 머리 `.rs-col-side .rs-card__title` + 청록 앞 막대 ⑥ 보고서(`ReportView` — 초안·최종본)·탐색 중 절 자리(`ReportSkeleton`)는 읽기용 짙은 유리 — `.rs-card.rs-report` 한 규칙(바탕 `--skx-read-surface` 를 불투명 면 위에, 글 톤 `--skx-read-*`, 테두리 `--skx-frost-menu-line`, 줄간격 1.6, 흐림·반사광 없음). `.skx-reading` 은 화면에 쓰지 않는다 — 흰 종이에 찍는 인쇄 전용 문서(`ReportPrint`)만, 화면 인쇄는 짙은 면을 그대로(`print-color-adjust: exact`). `themeResearch.test.ts` 가 ①②⑥ 과 색 리터럴 0·`:root` 토큰만을 지킨다 | 결정 7 → 최종 결정 C. 절 자리도 같은 면인 까닭: 첫 절이 오면 같은 자리에 초안(ReportView)이 서므로 면이 바뀌지 않게(두 부품의 뿌리가 같은 클래스라 한 규칙). 인쇄 전용 문서만 `.skx-reading` 인 까닭: 두 테마 모두에서 흰 종이·짙은 글자를 주는 토큰 묶음은 그것뿐이다(색 리터럴 금지, `--skx-on-accent` 는 핑크에서 밝다) — 판단이라 Z1 Step 3 에서 사용자에게 보인다 |
| 정함 25 | **소장자료 결과 [DeepResearch로 이어서 조사하기] = `/?start=deep-research&draft=<검색어>`(P8 8-1)** — 메인 입력창(논문 패널)에 결과의 검색어(`resultQuery`)를 채우고 DeepResearch 모드를 켠다. 시작은 하지 않는다. 초안은 줄바꿈·겹친 공백을 한 칸으로, 질문으로 쓸 수 없는 길이(`questionProblem` — 2자 미만·500자 초과)면 싣지 않는다(`deepResearchStartRoute(draft)`·`readStartDraft`). 'SKOVIX 추천 1권' 패널 아래 round08 주석 자리(`pages/index.vue:312`), **자르는 순서 1**. [담기 ▾](8-2 — 추천 1권을 이어간 연구 목록에 `PUT … {"state": "in"}`)는 **보류**(최종 결정 E — 사용자 답 대기, 답이 없으면 하지 않는다) | 결정 6 · 최종 결정 E. [DeepResearch로 이어서 조사하기]는 [담기]와 별개 — round08 이 논문 결과에만 만들고 소장자료 자리를 06d 에 남겼다. 결과 화면 검색바(`.skx-rsearch`)에는 + 메뉴가 없어 그 자리에서 모드를 켤 수 없다 — 사이드바 [+ 연구 시작하기]와 같은 랜딩 길(`?start=`)에 초안만 더한다. 메인 입력창으로 가므로 끝나지 않은 연구 한 줄·예시 카드·탐색 방식이 함께 선다 |
| 정함 26 | **탐색 방식 자리 = + 메뉴(`SearchPlusMenu.vue`)만** — 메인 입력창·`/papers` 랜딩·논문 결과 검색바가 같은 부품이라 세 곳 모두 DeepResearch 칩 옆에 선다. 고른 칸은 짙은 면(`--skx-white`)·산호 글자, 홈은 흰 10%(`--skx-frost-bg`), 입력 상자 아래 줄이 모자라면 줄바꿈(`.rs-plus:has(> .rs-mode)`), 휴대폰(≤480px) 랜딩 상자·결과 검색바에서는 설명을 숨긴다. (P6 품질 리뷰 반영) 고른 칸은 테두리(`--skx-border-c2`)로도 짚고(핑크 3:1), 설명은 `.rs-mode` 밖에서 늘 자기 줄·두 방식 설명을 한 칸에 겹쳐 고른 것만 보이며(칸을 바꿔도 묶음 자리·상자 높이 그대로), 결과 검색바는 + 메뉴 줄을 꺾지 않고 바 안쪽 폭(컨테이너 `rs-bar`) 34rem 이하에서 탐색 방식을 바 아래로 내린다. 나머지(두 칸 늘 함께·기본 정밀하게·기억·다시 시작은 원래 잡의 두 칸·머리 표시)는 원 정함 19 그대로 | 결정 5 |
| 정함 27 | **06d 앞부분과 한 번에 머지, round08 운영 반영 뒤에 따로 배포(최종 결정 F·G 로 고침)** — 둘째 부분은 같은 브랜치에서 앞부분 뒤에 하고, Z 는 06d 전체를 리뷰·문서·머지한다. 배포는 round08(이미 운영 이미지 `nl-lib-nuxt:latest` — `6b90e79` 기준, 운영 재배포만 남음)을 **먼저** 운영에 반영한 뒤 06d 를 따로 낸다 — 06d 의 되돌리기 태그 `:pre-round06d` 는 round08 이 든 이미지가 되고 되돌려도 다크 테마는 남는다. dev 머지 순서는 핑크 테마(`feat/theme-pink`)와 사용자가 정한다 | 결정 6 · 최종 결정 F·G. 2026-10-13 확인 — 핑크는 이미 dev `7adf93b` 에 있고 06d 는 그것을 받았다(`a084ff3`) |

### 1-5. 공통 계약 (이름·모양 — 모든 Task 가 이 이름을 쓴다)

본문 Task 의 코드가 정본이고 이 절은 색인이다. 원 계획 '공통 계약' 의 앞부분 이름(`researchProgress`·`planSlots`·`researchFollow`·`useSectionFollow`·`ReportSkeleton`·`ResearchProgressBar`·L4 의 `CandidatesEvent`·L5 의 `Ledger.reviewing`)은 그대로다.

**새 파일과 공개 이름(이 파일만 export)**

| 파일(새, `frontend/` 기준) | 공개 이름 | Task |
|---|---|---|
| `tests/unit/helpers/cssRules.ts` | 타입 `CssRule`, 함수 `cssRules(css)`(researchProgress.test.ts 안의 같은 함수를 옮김) | P2 |
| `tests/unit/themeResearch.test.ts` | (테스트) | P2 |
| `utils/sidebarResearch.ts` | 함수 `statusStageLine(r)`·`olderToggle(expanded, hidden)` | P3 |
| `utils/researchStart.ts` | 타입 `ResearchStartState`·`StartNotice`·`NoticeCancelStep`, 상수 `NOTICE_CANCEL_ARM_MS`(400), 함수 `researchStartState(items)`·`startNotice(state)`·`noticeCancelPress(step, armedAt, now)`·`noticeCancelLabel(step)` | P4 |
| `utils/researchExamples.ts` | 타입 `WorkListItem`·`WorkListOut`·`ExampleMeta`, 상수 `EXAMPLE_CARD_MAX`(3), 함수 `pickExamples`·`exampleMeta`·`exampleRoute`·`gatherExamples`(P5 품질 리뷰 — 목록과 범위를 다 받은 뒤 한 번에) | P5 |
| `composables/useResearchWorks.ts` | `useResearchWorksApi()`(`listWorks(example)`)·`useResearchExamples()`(P5). `useAddToWork()` 는 P8 8-2 — 하지 않음 | P5 |
| `components/research/ResearchExampleCards.vue` | props 없음, emit 없음 | P5 |
| `utils/researchMode.ts`·`components/research/ResearchModePicker.vue` | 원 계획 공통 계약의 N9 행 그대로 | P6 |
| `utils/addToWork.ts`·`components/research/AddToWorkMenu.vue` | (하지 않음 — 만들지 않는다) 원 계획 공통 계약의 N6 행 그대로(`WorkListItem` 은 `utils/researchExamples` 에서) | P8 8-2 |

**고치는 파일의 새·바뀐 공개 이름**

| 파일 | 바뀜 | Task |
|---|---|---|
| `composables/useResearch.ts` | `useResearchStarter()` 가 `{ startResearch, notice, cancelResearch }` 를 돌려준다(P4 — `notice: ComputedRef<StartNotice \| null>`, `cancelResearch(jobId)`), `startResearch(question, params?: ResearchParams)`(P6) | P4·P6 |
| `components/research/SearchPlusMenu.vue` | DeepResearch 모드일 때 끝나지 않은 연구 한 줄(P4), 탐색 방식 두 칸(P6) — 밖으로 내는 이름(`activateMode`·`clearMode`·`update:mode`)은 round08 그대로 | P4·P6 |
| `utils/landingStart.ts` | `deepResearchStartRoute(draft?)`(query 타입 `Record<string, string>`), `readStartDraft(query)` 새로, `queryWithoutStart` 가 `draft` 도 뺀다 | P8 8-1 |
| `components/research/ResearchHeader.vue` | 선택 prop `modeLine?: string \| null` | P6 |

**DOM·클래스·저장소**

| 이름 | 뜻 | Task |
|---|---|---|
| `.rs-card.rs-report`(`research.css` — `ReportView`·`ReportSkeleton` 의 뿌리) | 보고서·절 자리의 읽기용 짙은 유리 | P2 |
| `<article class="rs-print skx-reading">`(`ReportPrint.vue`) | 흰 종이에 찍는 인쇄 전용 문서만 밝은 읽는 면(화면에 그리지 않는다) | P2 |
| `.rs-col-side .rs-card__title`(+ `::before`) | 옆 칸 카드 머리 | P2 |
| `.skx-history-item__stage` · `.skx-history__older`(`.is-expanded`·`__older-chev`) | 사이드바 단계 문구 · 이전 연구 줄(`AppSidebar.vue` scoped) | P3 |
| `.rs-start-note`(`__text`·`__dot`·`__btn`·`.is-danger`) | + 메뉴 안 끝나지 않은 연구 한 줄(랜딩 상자에서는 칩 줄 아래, 결과 검색바에서는 바 아래 오른쪽) | P4 |
| `.rs-examples`(`__title`·`__note`·`__list`·`__card`·`__kicker`·`__q`·`__meta`) | 예시 연구 카드 | P5 |
| `.rs-mode*`·`.rs-head__meta`·`.rs-head__mode` | 탐색 방식(원 N9) | P6 |
| `.rs-basket*` · `.skx-deeper:has(> .rs-basket)` | [담기 ▾] · 그 줄 간격(하지 않음 — 만들지 않는다) | P8 8-2 |
| `useState` `skx:research-examples`·`skx:research-example-metas`·`skx:research-examples-loading` | 예시 목록·시각·범위·읽는 중 | P5 |
| localStorage `skx_research_mode` | 고른 탐색 방식(원 N9) | P6 |
| 주소 `/?start=deep-research&draft=<질문>` | 메인 입력창에 초안을 채워 DeepResearch 모드 | P8 8-1 |

**API(이미 있는 것만 — 백엔드 변경 없음):** `GET /api/research-works?example=1`·`GET /api/research/{id}/work`(P5), `POST /api/research/{id}/cancel`(P4 — 기존 취소 API, 입력창 한 줄의 [정말 취소]에서만), `POST /api/research` 본문 `{question, params: {broaden, query_context}}`(P6). 사이드바는 잡을 따로 읽지 않는다(P3 — 최종 결정 D). `GET /api/research-works`·`PUT /api/research/{id}/reading/{cnts_id}`(P8 8-2 [담기])는 보류.

### 1-6. 전역 실행 순서·의존·같은 파일 사슬

**순서:** (앞부분 D1~D7·L1~L5 — 원 계획) → **P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 8-1(자르는 순서 1 — 8-2 [담기]는 보류) → P9(조건부)** → Z1 → Z2 → Z3 → Z4 → Z5 → Z6 → Z7.

**의존:** P2 ← P1 · P3 ← P1 · P4 ← P2(`research.css` 블록 순서) · P5 ← P4(`research.css` 블록 순서) · P6 ← P4(`useResearch.ts`·`SearchPlusMenu.vue`)·P5(`research.css`) · P7 ← P6(`[id].vue`) · P8 8-1 ← P5(`pages/index.vue`) · P9 ← 06e dev 머지 · Z ← 전부.

**같은 파일 사슬(뒤 Task 의 Edit old 는 앞 Task 뒤 글자다):**
- `assets/css/research.css` — (앞부분 D2~L5) → P2 → P4 → P5 → P6(→ 8-2 보류).
- `pages/research/[id].vue` — (앞부분 … L5, dev 받기 `a084ff3`) → P6 → P7 → P9.
- `composables/useResearch.ts` — P4 → P6. `components/research/SearchPlusMenu.vue` — P4 → P6. `pages/index.vue` — P5 → P8 8-1(→ 8-2 보류). `composables/useResearchWorks.ts` — P5(→ 8-2 보류).
- 한 Task 만 고치는 파일: `tests/unit/researchProgress.test.ts`·`ReportPrint.vue`(P2), `AppSidebar.vue`(P3), `ResearchHeader.vue`(P6), `utils/landingStart.ts`·`tests/unit/landingStart.test.ts`(P8 8-1).

**테스트 수:** P2 +1 파일·+9 · P3 +1·+4 · P4 +1·+7 · P5 +1·+4 · P6 +1·+13 · P7 +0 · P8 8-1 +0·+4 · P9 +0 → **+5 파일·+41**(8-2 [담기]는 보류 — 하게 되면 +1·+4). 사본 실측(`a084ff3` — 2026-10-13 2차): `59 / 1231` → P2 `60 / 1240` → P3 `61 / 1244` → P4 `62 / 1251` → P5 `63 / 1255` → P6 `64 / 1268` → P7 같음 → P8 8-1 `64 / 1272`. 8-1 을 자르면 +5 파일·+37.

### 1-7. 다른 줄과의 경계

| 경계 | 내용 |
|---|---|
| 06e(연구 어시스턴트 — 아직 dev 밖) | `components/work/*`·`BookChat.vue`·`workPhase.ts`(06e 가 단계 이름을 '② 제목 고르기 ③ 참고문헌 선택하기 ④ 보고서'로 바꾼다)·`researchErrors.ts`·`useResearchWork.ts`·`types/work.ts`·`pages/papers/index.vue`·`[id].vue` 의 단계 본문(`<div v-if="stepMode" class="wk-body">` 블록)과 `workPanelOpen`·`work.css`(장부 블록 밖)는 06e. 06d 둘째 부분은 이 파일들을 고치지 않는다 — `useResearchWork.ts` 의 `useWorkApi().getWork`·`putReading`, `workPhase.ts` 의 `scopeLine`·`stepForPhase`, `researchErrors.ts` 의 `workErrorMessage` 를 읽기만 한다. 사이드바 단계 글은 진행 중 잡의 상태만(숫자 없이 — 최종 결정 D)이라 06e 의 이름 바꾸기와 겹치지 않는다(원 정함 13 을 없앴다). 06e 의 history `total`(H2)은 06d 가 읽지 않는다 |
| 06e 의 LNB 접기(정함 30) | 원 계획 N8 과 같은 계약 — P9. 06e 가 먼저 dev 에 들어오면 06d 가 `[id].vue:3-7` 두 곳을 단다, 06d 가 먼저면 06e 의 R6 이 단다 |
| 06e 와 round08 | 06e 브랜치도 round08 전 dev 에서 땄다 — 06e 의 dev 받기는 06e 몫. 06e 의 `[id].vue` '딥리서치 보고서 보기' 글은 round08 의 `DEEP_RESEARCH` 규칙과 어긋난다 — 06d 는 고치지 않고 Z3 완료노트·Z5 알림으로 06e 세션에 넘긴다 |
| 06c | 서버 `merge_params`·`DEFAULT_PARAMS`(0·0) 그대로. 06c 의 화면 한 줄(`questionUsedFromSteps`·`understoodLine`·PlanCard `questionUsed`)은 브랜치에 이미 있다 — P7 은 잇기만 |
| round08 | `AppSidebar.vue`·`pages/index.vue`·`SearchPlusMenu.vue`·`ResearchHeader.vue`·`landingStart.ts` 는 round08 이 만든 글 위에 06d 가 더한다(자리 주석 두 곳 `AppSidebar.vue:162`·`:186`, `pages/index.vue:312` 을 06d 가 걷는다). `sidebarGroups.ts`·`style_skovix.css`·`detail.css`·`resultCard.ts`·`detailView.ts` 는 고치지 않는다 — `MetaPart` 두 줄 경고는 round08 에 넘긴다 |
| round08 테마 구조(핑크 — dev `7adf93b`, 06d 는 `a084ff3` 에서 받음) | `html[data-theme]` 로 `--skx-*` 묶음을 바꾼다 — 06d 는 토큰만 쓰므로 두 테마에 같이 맞는다(P2 의 산호 위 글자 `--skx-on-accent`·빛 흐름 `--skx-frost-line`·읽기용 유리 `--skx-read-*`, P4 의 위험색 `--skx-danger`·`--skx-on-accent` 는 핑크 블록도 다시 선언한다). 06d 는 `style_skovix.css`·`SettingsMenu.vue`·`theme.ts`·`useTheme.ts` 를 고치지 않고 `tests/unit/helpers/themeCss.ts` 의 `rootDecls` 를 읽기만 한다(P2 가드). 머지 순서는 최종 결정 G(Z4 Step 1) |
| 백엔드 | 쓰는 API 는 모두 이미 있다('1-2'). 서버 문구 두 곳('진행 중인 딥리서치가 있습니다 …' `app/api/research.py:81`, '완료된 딥리서치만 …' `research_work.py:187`)은 서버를 건드리는 라운드 몫(round08 인계) |

### 1-8. 하지 않는 것

별도 `/research` 홈·'모두 보기 (N)'·history `total` 받기(결정 1·4), [+ 연구 시작하기]의 분기(끝나지 않은 연구 화면으로 이동 — 최종 결정 A), 메인 페이지(`pages/index.vue`)에 두는 알림 줄(최종 결정 B — + 메뉴 안), 사이드바의 진행 중 잡 GET·단계 숫자(최종 결정 D), 화면의 밝은 읽는 면 `.skx-reading`(최종 결정 C), 소장자료 결과 [담기 ▾](최종 결정 E — 보류), 사이드바 예시 연구 묶음(결정 3), 이어간 연구 줄의 단계·수·'생성 중'과 생성 폴링(결정 4 — 완료 줄 옆 '보고서 n절'·'참고문헌 n편' 없음), 논문 결과의 [딥리서치로 더 깊게](round08 `.skx-deeper` 가 대신), 논문 결과 카드의 [담기](결정 6 의 자리는 소장자료 추천 1권), 진행 중 연구가 있을 때 보내기를 막기(서버 429 가 안전망), 메인 [빠른검색|딥리서치] 모드 토글·도서 숨김(대회 뒤), 원 계획 '하지 않는 것' 의 나머지(시안 사이드바 진행 막대·skx 검색바·글자 스트리밍·다른 브라우저 이어가기·탐색 남은 시간 등), 백엔드·스키마 변경 전부, round08 파일의 정리(`MetaPart` 등).

---

## 2. 작업

### Task P1: 앞부분 끝·dev(round08) 받기 확인·회귀 기준선

**왜:** 둘째 부분은 앞부분(원 계획 D1~D7·L1~L5)과 round08(dev `bae4d75` — 테마 구조·핑크 `7adf93b` 까지) 위에서 시작한다 — 사이드바·메인·+ 메뉴·머리·`landingStart` 를 round08 의 글 위에 고치므로 dev 를 받지 않은 브랜치에서는 앵커가 맞지 않는다. 앞부분 세션이 끝나며 dev 를 받기로 했다 — **2026-10-13 받았다(`a084ff3` — dev `7adf93b`, 핑크 포함)**. 받았는지 다시 보고(그 뒤 dev 가 더 갔으면 같은 방법으로 받는다), 아니면 Step 3 으로 받는다. 받은 뒤의 수(vitest·typecheck·한 이름 경고·build)를 이 계획의 '앞 수' 로 잰다.

**Files:** 없음(받지 않았으면 merge 커밋 1개 — 충돌 푼 `frontend/pages/research/[id].vue`)

**알아 둘 것:**
- 앞부분이 끝났다는 표시는 L3~L5 의 이름이다 — `roundStatusLabel`(L3, `utils/researchEvents.ts`)·`CandidatesEvent`(L4, `types/research.ts`)·`reviewing`(L5, `utils/evidenceLedger.ts`).
- 충돌은 한 곳(2026-10-13 실측 — 브랜치 `11072c4`(L3 포함)에 dev 를 합친 사본. 남은 L4·L5 는 round08 이 고친 파일과 겹치지 않는다: L5 의 `[id].vue` 옆 칸 블록과 round08 의 두 줄(import·`useHead`)은 떨어져 있고, round08 은 `research.css`·`work.css`·`researchEvents.ts`·`types/research.ts`·`ProgressPanel.vue`·`evidenceLedger.ts` 를 고치지 않았다). dev 가 `bae4d75` 뒤로 더 갔으면(06e 머지 등) 다른 파일이 더 나올 수 있다 — 그때는 멈추고 사용자와 그 줄의 세션에 알린다(06e 의 `[id].vue` 단계 본문은 dev 쪽, 06d 가 고친 줄은 이 브랜치 쪽이 원칙 — 원 계획 Task L6 Step 3 '다른 파일이 충돌하면').
- `git fetch origin dev:dev` 가 `refusing to fetch into branch 'refs/heads/dev' checked out at …` 로 막히면 dev 를 checkout 한 worktree(대개 남은 `.worktrees/dev-merge`)가 있다 — 쓰이는지 사용자에게 묻고, 쓰이지 않으면 `git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge` 뒤 다시 한다(`.worktrees/dev-read` 는 detached 라 막지 않는다).
- 한 이름 경고는 round08 뒤 `MetaPart` 두 줄이 기준선이다('1-2').

- [ ] **Step 1: 앞부분이 끝났고 작업 트리가 깨끗한가**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git status --short
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git log --oneline -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "export function roundStatusLabel" frontend/utils/researchEvents.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "CandidatesEvent" frontend/types/research.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "reviewing" frontend/utils/evidenceLedger.ts
```

Expected: 빈 출력, 앞부분 마지막 커밋 한 줄(원 계획 L5 또는 그 품질 검토 반영·dev 머지 커밋), `1`, `1` 이상, `1` 이상. 셋 중 하나라도 `0` 이면 **여기서 멈춘다** — 앞부분이 끝나지 않았다(앞부분 세션을 기다린다).

- [ ] **Step 2: dev 를 받았는가**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d log --oneline -1 dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d merge-base --is-ancestor bae4d75 HEAD && echo "round08 받음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d log --oneline HEAD..dev | wc -l
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d log --oneline --merges dev | grep -c "feat/round06e-assistant-auto-report"
```

Expected: `fetch` 출력 없음(또는 `<옛>..<새>  dev -> dev` 한 줄), dev 마지막 커밋 한 줄(2026-10-13 `7adf93b Merge feat/theme-pink into dev …`), 그리고 둘 중 하나(2026-10-13 확인으로는 (가) — `a084ff3`) —
- (가) `round08 받음` 과 `0` → Step 3 을 건너뛰고 Step 4.
- (나) `round08 받음` 이 없거나 수가 `0` 이 아니다 → Step 3.

마지막 수(06e 머지)를 적어 둔다 — `0` 이면 P9 를 건너뛰고, `1` 이상이면 Step 3 의 merge 로 06e 도 함께 들어온다(그때 Step 3 의 충돌 규칙의 06e 줄을 본다).

- [ ] **Step 3: (나의 경우) dev 를 받고 import 한 곳을 푼다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git merge dev -m "Merge dev into feat/round06d-research-progress-screen — round08 UI 다크 테마(다크 토큰·사이드바 DeepResearch 묶음·메인 두 갈래·DeepResearch 표기) 받기"`

Expected: `CONFLICT (content): Merge conflict in frontend/pages/research/[id].vue` 한 줄(과 `Auto-merging …` 줄들), 끝 줄 `Automatic merge failed; fix conflicts and then commit the result.`. 다른 파일이 `CONFLICT` 로 나오면 위 '알아 둘 것' 둘째 줄대로 멈춘다.

`frontend/pages/research/[id].vue` — 충돌 표시가 든 글(고치기 전):

```text
import { safeLocalStorage } from "~/utils/browserId";
<<<<<<< HEAD
import { queueLine } from "~/utils/queueLine";
=======
import { DEEP_RESEARCH } from "~/utils/brand";
>>>>>>> dev
import { draftReport, draftSlots, synthEta, type SynthEta } from "~/utils/researchDraft";
```

고친 뒤(두 줄을 모두 남긴다 — round08 의 `useHead` 가 `DEEP_RESEARCH` 를, 앞부분 D2 의 `queueText` 가 `queueLine` 을 쓴다):

```text
import { safeLocalStorage } from "~/utils/browserId";
import { DEEP_RESEARCH } from "~/utils/brand";
import { queueLine } from "~/utils/queueLine";
import { draftReport, draftSlots, synthEta, type SynthEta } from "~/utils/researchDraft";
```

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -cE '^(<<<<<<<|=======|>>>>>>>)' "frontend/pages/research/[id].vue"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "frontend/pages/research/[id].vue" && git diff --name-only --diff-filter=U && git commit --no-edit --cleanup=strip && git log -1 --format=%B
```

Expected: `0`, 충돌 파일 목록은 빈 출력, 커밋 본문은 merge 메시지 한 줄(과 끝의 빈 줄)뿐 — `# Conflicts:` 줄이 없다(`--cleanup=strip` — 원 계획 Task L6 Step 3 과 같은 까닭). 메시지에 Co-Authored-By 줄을 넣지 않는다.

- [ ] **Step 4: 받은 뒤 회귀 — 이 계획의 기준선**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi prepare 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "06d: 단계 문구\|06d: 전용 화면으로 가는" components/AppSidebar.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "06d: \[딥리서치로 더 깊게\]" pages/index.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "export const DEEP_RESEARCH" utils/brand.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git status --short
```

Expected:
- `nuxi prepare` — `Types generated in .nuxt.` 꼴 한 줄(round08 이 더한 부품·utils 를 자동 import 표에 싣는다 — 이것 없이 vitest 를 먼저 돌리면 새 이름을 못 찾을 수 있다)
- typecheck `0`
- 한 이름 경고 — `      2 Duplicated imports "MetaPart"` 한 줄(round08 기준선. 다른 이름이 나오면 06d 앞부분과 round08 이 같은 이름을 내보낸다 — 그 이름·두 파일을 사용자에게 알리고 멈춘다)
- vitest 실패 0. 수를 적어 둔다 — **이 계획의 첫 '앞 수'**. 사본 실측(`a084ff3` — 2026-10-13 2차)은 `Test Files  59 passed (59)` / `Tests  1231 passed (1231)`(핑크 테마 테스트 포함 — 그 뒤 dev 나 앞부분이 더 갔으면 그만큼 다르다)
- `└  ✨ Build complete!`
- round08 자리 주석 — `2`·`1`(P3·P8 8-1 이 걷는다)
- `1`
- 빈 출력

이 Task 는 Step 3 의 merge 커밋 말고는 커밋이 없다.

---

### Task P2: D8 — 연구 화면을 다크 테마에 맞춘다(머리·옆 칸·큰 진행 막대·보고서의 읽기용 짙은 유리)

결정 7 · **최종 결정 C**(2026-10-13 — 밝은 면 `.skx-reading` 을 화면에 쓰지 않는다) · 원 계획 Task D8(spec §12-3 '스타일' 행 — 고치는 부품만 skx 토큰, skx 검색바는 넣지 않음). round08 이 `research.css` 를 고치지 않고 토큰 값만 다크로 바꿔, 연구 화면은 '짙은 청록 카드(`--skx-white` #152e28)·옅은 회색 글자'로 따라왔다. 그 위에서 어긋나는 넷 — 이름만 남은 `--skx-white` 를 글자색으로 쓴 곳, 다크에서 보이지 않는 옅은 그림자, 산호 막대 위로 어둡게 흐르는 빛, 오래 읽는 보고서의 면 — 을 토큰으로 맞춘다. 보고서(초안·최종본)와 탐색 중 절 자리는 결과 화면의 읽는 칸과 같은 **읽기용 짙은 유리**(`--skx-read-surface`·글 `--skx-read-ink`·`--skx-read-ink-2`·`--skx-read-gray-1`, 줄간격 1.6, 흐림·반사광 없음)다. 정함 24.

**Files:**
- Create: `frontend/tests/unit/helpers/cssRules.ts`(`researchProgress.test.ts` 안의 같은 함수를 옮김)
- Create: `frontend/tests/unit/themeResearch.test.ts`
- Modify: `frontend/tests/unit/researchProgress.test.ts`(import 한 줄·옮긴 함수 지움)
- Modify: `frontend/assets/css/research.css`(`.rs-card`·`.rs-btn`·머리 `.rs-head` ~ `.rs-status--completed`·`.rs-report` 뒤 읽기용 짙은 유리·`.rs-plus__chip`·`-x`·`.rs-synth__item.is-done .rs-synth__icon`·`.rs-pbar`·`.rs-pbar__stage.is-current`·`.rs-pbar__fill.is-running::after`·인쇄의 `.rs-page .rs-body` ~ `.rs-print`, 인쇄 앵커 위 '옆 칸 카드 머리' 블록)
- Modify: `frontend/components/research/ReportPrint.vue`(인쇄 전용 문서 `article` 에 `skx-reading` — 화면에 그리지 않는 흰 종이. 아래 '알아 둘 것' 의 인쇄 줄)

`pages/research/[id].vue`·`ReportView.vue`·`ReportSkeleton.vue` 는 고치지 않는다 — 두 부품의 뿌리가 `<article class="rs-card rs-report …">` 라 면은 `research.css` 의 `.rs-card.rs-report` 한 규칙으로 준다.

기준선: P1 Step 4 의 수.

**알아 둘 것:**
- **글자색 토큰:** round08 의 `--skx-white` 는 '불투명 면' 자리다(`style_skovix.css` `:root` 머리 주석). 산호 바탕 위 글자로 쓴 6곳('1-2')은 다크에서 짙은 청록 글자가 되어 우연히 읽히지만, 그 자리의 토큰은 `--skx-on-accent`(다크 #0f2822 · 핑크 #f2f2f0 — 테마마다 `--skx-primary` 와 짝)다. 이름과 뜻을 맞춰 두어야 테마를 바꿔도(round08 테마 구조 — 핑크는 `--skx-white` #fff·`--skx-primary` #1a1115) 깨지지 않는다.
- **막대 빛 흐름:** `color-mix(in srgb, var(--skx-white) 45%, transparent)` 는 다크에서 산호 막대 위로 **어두운** 띠가 흐른다. 글자색(`--skx-ink-strong`)을 섞으면 다크에서는 밝지만 핑크에서는 짙은 막대(#1a1115) 위에 짙은 띠라 보이지 않는다 → 두 테마 모두 흰색 계열인 밝은 유리 선 `--skx-frost-line`(다크 흰 24% · 핑크 흰 70%)을 그대로 쓴다.
- **가장자리:** 다크에서 `--skx-shadow-lnb`(검정 8%)는 거의 안 보여 카드가 바탕에 녹는다 → `--skx-frame-line`(흰 8% — 결과 화면 큰 틀과 같은 선) 1px + `--skx-frost-hilite`(안쪽 위 하이라이트). 큰 진행 막대는 본문 위에 붙어 떠 있으므로 `--skx-shadow-banner`(메뉴와 같은 짙은 그림자). 테두리는 tailwind preflight 의 `box-sizing: border-box` 라 막대 높이(`--rs-bar-h`)·옆 칸 top·위치 복원 오프셋이 그대로다. `.rs-card--error` 의 테두리(`--skx-line`)는 뒤에 오는 규칙이라 그대로 이긴다.
- **카드 면은 불투명 면 그대로:** `research.css` 의 카드·머리·막대 바탕은 `var(--skx-white)`(다크 짙은 청록 · 핑크 흰색)로 이미 토큰이다 — 최종 결정 C 의 '불투명 흰 카드 면은 06d 범위에서 `--skx-*` 토큰으로만' 에 맞고, 이 Task 는 그 면에 가장자리만 더한다. 움직이는 배경 위에서 본문 대비(4.5:1)를 불투명 면이 지킨다.
- **머리(원 D8 을 다크로):** kicker(`DEEP_RESEARCH` — round08)는 사이드바 묶음 이름과 같은 청록 칩(`--skx-glass-teal` 바탕·`--skx-teal-ink` 글자 — 사이드바의 `.skx-history-chip` 과 같은 짝), 질문은 1.1rem·`--skx-ink-strong`(round08 의 제목색 — 바로 아래 큰 막대 글줄 1rem 보다 한 단계 크게), kicker·상태 배지는 막대의 단계 칩(`.rs-pbar__stage` — 0.55rem·`0.1rem 0.45rem`·알약)과 같은 크기, 버튼 줄 간격 0.3rem. `ResearchHeader.vue` 마크업은 이 Task 에서 고치지 않는다(P6 이 상태 배지 줄을 묶는다).
- **옆 칸 카드 머리:** 원 D8 Step 2 그대로 `.rs-col-side .rs-card__title`(0.75rem·줄높이 1.6) + 앞 막대 — 막대 색만 남색 → 청록(`--skx-teal-ink`). 공용 `.rs-card__title` 은 본문 카드(보고서 작성 현황·실패·취소·보고서 오류)와 연구 어시스턴트 부품도 쓰므로 고치지 않는다.
- **보고서·절 자리 = 읽기용 짙은 유리(최종 결정 C):** 결과 화면의 읽는 칸(`.skx-pick__main`·`.skx-pai-main` 등 — `style_skovix.css` '읽는 칸')과 같은 토큰 — 바탕 `--skx-read-surface`, 그 면 안에서만 `--skx-ink`·`--skx-ink-2`·`--skx-gray-1` 을 `--skx-read-ink`·`--skx-read-ink-2`·`--skx-read-gray-1` 로 다시 정의, 테두리 `--skx-frost-menu-line`, 줄간격 1.6, 흐림(`backdrop-filter`)·반사광(`--skx-frost-reflect`·`-milk`)·위 하이라이트 없음. 읽는 칸은 큰 틀(`--skx-frame-bg`) 위에 겹쳐 짙어지지만 연구 화면의 카드는 움직이는 배경 위에 바로 서므로 **불투명 면(`--skx-white`) 위에 깐다**(`linear-gradient(var(--skx-read-surface), var(--skx-read-surface)), var(--skx-white)` — 다크에서 #152e28 보다 한 단계 짙은 초록, 핑크에서 흰색) — 띠가 밝게 지나가도 글자가 흐려지지 않는다. 보고서(`ReportView` — 초안이 같은 부품에서 최종본으로 바뀐다)와 탐색 중 절 자리(`ReportSkeleton`)의 뿌리가 모두 `.rs-card.rs-report` 라 한 규칙이 둘을 덮고, 첫 절이 오면 같은 자리에 초안이 서도 면이 바뀌지 않는다. 그 안의 작은 불투명 면(`.rs-report__intro`·인용 칩·[다운로드] 버튼 등 — `--skx-white`)은 그대로 둔다(글 톤만 읽기용으로 따라온다).
- **인쇄(판단 — Z1 Step 3 에서 사용자에게 보인다):** 다크 글 톤(본문 #ccc·읽는 면 #e6ebe9)이 흰 종이에 그대로 찍히면 거의 보이지 않는다. 두 테마 모두에서 '흰 면·짙은 글자' 를 주는 토큰 묶음은 `.skx-reading` 뿐이다(핑크도 `html[data-theme="pink"] .skx-reading` 이 중립 흰 면을 그대로 둔다 — 색 리터럴 없이 짙은 인쇄 글자를 줄 다른 토큰은 없다: `--skx-on-accent` 는 핑크에서 밝다). 그래서 **[PDF로 저장]의 인쇄 전용 문서(`ReportPrint` — 화면에서는 `display: none`, 누른 동안에만 body 에 붙는다)만** `.skx-reading` 을 단다 — 화면에 그리는 면이 아니라 결정 C 의 '화면 면' 밖이다. 화면 인쇄(Ctrl+P)의 보고서는 바탕이 빠지면 밝은 글자만 남으므로 `print-color-adjust: exact` 로 화면의 짙은 면을 그대로 찍는다(흰 종이에 짙은 글자는 [PDF로 저장]이 맡는다). 사용자가 인쇄 전용 문서도 짙게 두자고 하면 `ReportPrint.vue` 의 class 한 단어와 `themeResearch.test.ts` 의 그 단언 한 줄만 바꾼다(Fix 커밋 — 인쇄 글 톤은 완료노트 §7 이월).
- **카드 가장자리는 연구 화면 공용이다:** `.rs-card` 의 테두리·하이라이트는 연구 화면의 모든 카드 — 이어간 연구 단계 화면(`?s=` — 06b·06e 의 `components/work/*` 카드)도 — 에 함께 붙는다. 다크에서 카드가 바탕에 녹는 것은 그 화면도 같아 함께 맞추는 것이고, 06e 파일은 고치지 않는다(`work.css` 가 뒤에 실려 자기 테두리를 둔 `wk-*` 규칙은 그대로 이긴다). Z1 Step 3 에서 `?s=` 화면도 보고, Z5 알림으로 06e 세션에 알린다.
- **가드 테스트(`themeResearch.test.ts` — +9):** 처음부터 통과하는 가드 셋(파일·`:root` 토큰을 읽었다, 색 리터럴 0 — `research.css` 와 `AppSidebar.vue` 의 scoped 스타일, 쓰는 `--skx-*` 가 모두 `:root` 에 있다)·화면에 `.skx-reading` 이 없다(지금도 없다 — 앞으로 생기지 않게)와 이 Task 가 통과시키는 다섯(글자색 `--skx-white` 0, 산호 위 글자 `--skx-on-accent`, 빛 흐름 `--skx-frost-line`, 보고서·절 자리 읽기용 짙은 유리, 인쇄 전용 문서만 `.skx-reading`·화면 인쇄 `exact`). `:root` 토큰은 round08 테마 구조가 만든 `tests/unit/helpers/themeCss.ts` 의 `rootDecls` 를 쓰고(같은 읽기를 두 벌 두지 않는다), CSS 규칙 읽기는 `researchProgress.test.ts` 의 `cssRules` 를 `tests/unit/helpers/cssRules.ts` 로 옮겨 두 파일이 같이 쓴다(글자 그대로 옮김).

- [ ] **Step 1: 실패하는 테스트를 쓴다(그리고 CSS 규칙 읽기를 helper 로 옮긴다)**

`frontend/tests/unit/helpers/cssRules.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/helpers/cssRules.ts
// research.css 의 규칙 — 선택자(쉼표로 나눔)·감싼 @규칙(@media 등)·선언. 이 파일은 CSS 중첩·중괄호가 든 글자를 쓰지 않는다
export interface CssRule {
  at: string;
  selectors: string[];
  decls: Map<string, string>;
}

export function cssRules(css: string): CssRule[] {
  const src = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const squash = (s: string) => s.replace(/\s+/g, " ").trim();
  const rules: CssRule[] = [];
  const heads: string[] = [];
  let buf = "";
  for (const ch of src) {
    if (ch === "{") {
      heads.push(squash(buf));
      buf = "";
    } else if (ch === "}") {
      const head = heads.pop() ?? "";
      if (!head.startsWith("@") && buf.trim()) {
        const decls = new Map<string, string>();
        for (const d of buf.split(";")) {
          const colon = d.indexOf(":");
          if (colon > 0) decls.set(d.slice(0, colon).trim(), squash(d.slice(colon + 1)));
        }
        rules.push({ at: heads.filter((h) => h.startsWith("@")).join(" "), selectors: head.split(",").map(squash), decls });
      }
      buf = "";
    } else {
      buf += ch;
    }
  }
  return rules;
}
```

`frontend/tests/unit/themeResearch.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/themeResearch.test.ts
// round06d 2부 — DeepResearch 화면 스타일(assets/css/research.css)과 사이드바 스타일(AppSidebar.vue 의 scoped)은 round08 테마 토큰만
// 쓴다. ① 색 리터럴(#hex·rgb()·rgba()·hsl()·색 이름)이 없다 ② 쓰는 --skx-* 는 모두 style_skovix.css 의 :root 에 있다(없는 토큰을
// 쓰면 var() 가 비어 바탕·글자가 조용히 사라진다 — 테마 블록은 :root 의 토큰을 다시 선언만 한다) ③ --skx-white 는 이름만 남은 '불투명
// 면' 자리라 글자색으로 쓰지 않고, 산호 바탕(--skx-primary) 위 글자는 --skx-on-accent ④ 진행 막대의 빛 흐름은 밝은 유리 선
// ⑤ 보고서·탐색 중 절 자리는 읽기용 짙은 유리(--skx-read-*)이고 밝은 읽는 면(.skx-reading)은 화면에 쓰지 않는다 — 흰 종이에 찍는
// 인쇄 전용 문서만(사용자 결정 2026-10-13)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { cssRules } from "./helpers/cssRules";
import { rootDecls } from "./helpers/themeCss";

function read(rel: string): string {
  return readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf-8");
}

// 주석과 url(...) 안의 글은 검사하지 않는다(주석의 '흰 8%' 같은 설명·아이콘 경로)
function strip(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "").replace(/url\([^)]*\)/g, "");
}

const LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|(?<![\w-])(?:white|black|red|green|blue|gray|grey|currentcolor)(?![\w-])/gi;
const researchCss = read("../../assets/css/research.css");
const sidebarCss = read("../../components/AppSidebar.vue").match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] ?? "";
const declared = new Set(Object.keys(rootDecls));

function usedTokens(css: string): string[] {
  return [...new Set([...strip(css).matchAll(/var\(\s*(--skx-[\w-]+)/g)].map((m) => m[1]!))];
}

describe("DeepResearch 화면·사이드바 스타일 — 색은 토큰으로만", () => {
  it("research.css·사이드바 스타일·:root 토큰을 읽었다", () => {
    expect(researchCss.length).toBeGreaterThan(0);
    expect(sidebarCss).toMatch(/\.skx-history/);
    expect(declared.has("--skx-white")).toBe(true);
  });

  it("색 리터럴이 없다", () => {
    expect(strip(researchCss).match(LITERAL) ?? []).toEqual([]);
    expect(strip(sidebarCss).match(LITERAL) ?? []).toEqual([]);
  });

  it("쓰는 --skx-* 는 모두 :root 에 선언돼 있다", () => {
    expect(usedTokens(researchCss).filter((name) => !declared.has(name))).toEqual([]);
    expect(usedTokens(sidebarCss).filter((name) => !declared.has(name))).toEqual([]);
  });
});

describe("다크 테마의 글자색·빛(research.css)", () => {
  const rules = cssRules(researchCss);
  const names = (list: typeof rules) => list.map((r) => r.selectors.join(", "));

  it("--skx-white 는 글자색으로 쓰지 않는다 — round08 에서 불투명 면(다크 짙은 청록) 자리다", () => {
    expect(names(rules.filter((r) => r.decls.get("color") === "var(--skx-white)"))).toEqual([]);
  });

  it("산호 바탕(--skx-primary) 위 글자는 --skx-on-accent", () => {
    const onCoral = rules.filter((r) => r.decls.get("background") === "var(--skx-primary)" && r.decls.has("color"));
    expect(onCoral.length).toBeGreaterThan(0);
    expect(names(onCoral.filter((r) => r.decls.get("color") !== "var(--skx-on-accent)"))).toEqual([]);
  });

  it("진행 막대 채움의 빛 흐름은 밝은 유리 선(--skx-frost-line) — 짙은 면 색을 섞으면 산호 막대 위로 어두운 띠가 흐른다", () => {
    const sheen = rules.find((r) => r.selectors.includes(".rs-pbar__fill.is-running::after"))?.decls.get("background") ?? "";
    expect(sheen).toContain("var(--skx-frost-line)");
    expect(sheen).not.toContain("var(--skx-white)");
  });
});

describe("보고서·절 자리 — 읽기용 짙은 유리(밝은 읽는 면은 화면에 쓰지 않는다)", () => {
  const rules = cssRules(researchCss);

  it("보고서(초안·최종본)와 탐색 중 절 자리(뿌리 .rs-card.rs-report)는 결과 화면의 읽는 칸과 같은 토큰 — 줄간격 1.6, 흐림·반사광 없음", () => {
    const face = rules.find((r) => !r.at && r.selectors.includes(".rs-card.rs-report"));
    expect(face?.decls.get("background")).toContain("var(--skx-read-surface)");
    expect(face?.decls.get("background")).not.toMatch(/--skx-frost-(reflect|milk|fill)/);
    expect(face?.decls.has("backdrop-filter")).toBe(false);
    expect(face?.decls.get("--skx-ink")).toBe("var(--skx-read-ink)");
    expect(face?.decls.get("--skx-ink-2")).toBe("var(--skx-read-ink-2)");
    expect(face?.decls.get("--skx-gray-1")).toBe("var(--skx-read-gray-1)");
    expect(face?.decls.get("line-height")).toBe("1.6");
    // 두 부품의 뿌리가 그 클래스다 — 부품 파일을 고치지 않고 면을 준다
    expect(read("../../components/research/ReportView.vue")).toContain('<article class="rs-card rs-report"');
    expect(read("../../components/research/ReportSkeleton.vue")).toContain('<article class="rs-card rs-report rs-report--slots"');
  });

  it("밝은 읽는 면(.skx-reading)은 화면에 그리는 연구 페이지·부품·스타일에 없다", () => {
    for (const rel of [
      "../../pages/research/[id].vue",
      "../../components/research/ReportView.vue",
      "../../components/research/ReportSkeleton.vue",
    ]) {
      expect(read(rel)).not.toContain("skx-reading");
    }
    expect(strip(researchCss)).not.toContain("skx-reading");
  });

  it("흰 종이에 찍는 인쇄 전용 문서(화면에 그리지 않는다)만 밝은 읽는 면이고, 화면 인쇄의 보고서는 짙은 면을 그대로 찍는다", () => {
    expect(read("../../components/research/ReportPrint.vue")).toContain('<article class="rs-print skx-reading">');
    expect(rules.find((r) => !r.at && r.selectors.includes(".rs-print"))?.decls.get("display")).toBe("none");
    const screenPrint = rules.find((r) => r.at.includes("@media print") && r.selectors.includes(".rs-page .rs-report"));
    expect(screenPrint?.decls.get("print-color-adjust")).toBe("exact");
  });
});
```

`researchProgress.test.ts` — ① import 한 줄을 더한다.

**Edit** `frontend/tests/unit/researchProgress.test.ts` — old:

```ts
import { RUNNING_CAP, barFraction } from "~/utils/synthCard";
```

new:

```ts
import { RUNNING_CAP, barFraction } from "~/utils/synthCard";
import { cssRules } from "./helpers/cssRules";
```

② 파일 안의 같은 함수를 지운다(helper 로 옮겼다 — 뒤 describe 의 첫 주석 줄을 old 끝에 붙여 자리를 잡는다).

**Edit** `frontend/tests/unit/researchProgress.test.ts` — old:

```ts
// research.css 의 규칙 — 선택자(쉼표로 나눔)·감싼 @규칙(@media 등)·선언. 이 파일은 CSS 중첩·중괄호가 든 글자를 쓰지 않는다
interface CssRule {
  at: string;
  selectors: string[];
  decls: Map<string, string>;
}

function cssRules(css: string): CssRule[] {
  const src = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const squash = (s: string) => s.replace(/\s+/g, " ").trim();
  const rules: CssRule[] = [];
  const heads: string[] = [];
  let buf = "";
  for (const ch of src) {
    if (ch === "{") {
      heads.push(squash(buf));
      buf = "";
    } else if (ch === "}") {
      const head = heads.pop() ?? "";
      if (!head.startsWith("@") && buf.trim()) {
        const decls = new Map<string, string>();
        for (const d of buf.split(";")) {
          const colon = d.indexOf(":");
          if (colon > 0) decls.set(d.slice(0, colon).trim(), squash(d.slice(colon + 1)));
        }
        rules.push({ at: heads.filter((h) => h.startsWith("@")).join(" "), selectors: head.split(",").map(squash), decls });
      }
      buf = "";
    } else {
      buf += ch;
    }
  }
  return rules;
}

// 고정 진행 막대는 문서(창) 스크롤 위에 sticky 로 붙는다 — 브라우저는 초점 이동·scrollIntoView·#조각 이동에서 sticky 막대를 모르므로
```

new:

```ts
// 고정 진행 막대는 문서(창) 스크롤 위에 sticky 로 붙는다 — 브라우저는 초점 이동·scrollIntoView·#조각 이동에서 sticky 막대를 모르므로
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/themeResearch.test.ts tests/unit/researchProgress.test.ts`

Expected: `Test Files  1 failed | 1 passed (2)` / `Tests  5 failed | 27 passed (32)` — `researchProgress.test.ts` 23 은 그대로 통과(helper 로 옮긴 함수가 같다), `themeResearch.test.ts` 는 가드 셋과 `밝은 읽는 면(.skx-reading)은 화면에 그리는 …` 이 통과하고 다섯이 실패한다: `--skx-white 는 글자색으로 쓰지 않는다 …`(`expected [ '.rs-btn', …(5) ] to deeply equal []`), `산호 바탕(--skx-primary) 위 글자는 --skx-on-accent`(`expected [ '.rs-btn', …(4) ] to deeply equal []`), `진행 막대 채움의 빛 흐름은 …`(`expected 'linear-gradient(90deg, transparent, c…' to contain 'var(--skx-frost-line)'`), `보고서(초안·최종본)와 탐색 중 절 자리 …`(`.rs-card.rs-report` 규칙이 없어 `the given combination of arguments (undefined and string) is invalid for this assertion …`), `흰 종이에 찍는 인쇄 전용 문서 …`(`expected '<!-- frontend/components/research/Rep…' to contain '<article class="rs-print skx-reading">'`).

- [ ] **Step 3: 구현한다 — research.css**

① `.rs-card` — 카드 가장자리(`:81`).

**Edit** `frontend/assets/css/research.css` — old:

```css
.rs-card {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  padding: 1.2rem;
  background: var(--skx-white);
  border-radius: var(--skx-radius-lg);
  box-shadow: var(--skx-shadow-lnb);
}
```

new:

```css
/* 카드는 불투명 면(--skx-white — 다크 테마에서 짙은 청록)이라 움직이는 배경 위에서도 글자가 읽힌다. 다크에서는 옅은 그림자가 거의
   보이지 않아 가장자리를 흰 8% 선(--skx-frame-line — 결과 화면 큰 틀과 같은 선)과 위 하이라이트(--skx-frost-hilite)로 세운다 */
.rs-card {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  padding: 1.2rem;
  background: var(--skx-white);
  border: 1px solid var(--skx-frame-line);
  border-radius: var(--skx-radius-lg);
  box-shadow: var(--skx-frost-hilite), var(--skx-shadow-lnb);
}
```

② `.rs-btn` — 산호 버튼의 글자(`:148`).

**Edit** `frontend/assets/css/research.css` — old:

```css
  font-weight: 700;
  color: var(--skx-white);
  white-space: nowrap;
  text-decoration: none;
  background: var(--skx-primary);
```

new:

```css
  font-weight: 700;
  color: var(--skx-on-accent);
  white-space: nowrap;
  text-decoration: none;
  background: var(--skx-primary);
```

③ 머리 — `.rs-head` 부터 `.rs-status--completed` 까지(`:217-266`, 원 D8 Step 1 의 old 에 `.rs-head`·`.rs-status--completed` 를 더한 묶음).

**Edit** `frontend/assets/css/research.css` — old:

```css
.rs-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 1.2rem;
  background: var(--skx-white);
  border-radius: var(--skx-radius-lg);
  box-shadow: var(--skx-shadow-lnb);
}
.rs-head__main {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 0;
}
.rs-head__kicker {
  margin: 0;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-primary);
}
.rs-head__question {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.4;
  word-break: keep-all;
}
.rs-head__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.rs-status {
  align-self: flex-start;
  padding: 0.15rem 0.55rem;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-primary);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}
.rs-status--completed {
  color: var(--skx-white);
  background: var(--skx-primary);
  border-color: var(--skx-primary);
}
```

new:

```css
/* 머리 — 카드와 같은 불투명 면·가장자리(.rs-card 주석). 'DeepResearch' kicker 는 사이드바 묶음 이름과 같은 청록 칩, 질문은 화면의
   주인이라 제목 글자색(--skx-ink-strong)으로 바로 아래 큰 진행 막대의 글줄(1rem)보다 한 단계 크게 둔다. kicker·상태 배지·버튼 줄
   간격은 큰 진행 막대의 단계 칩(.rs-pbar__stage — 0.55rem·0.1rem 0.45rem·알약)과 같은 크기 체계 */
.rs-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 1.2rem;
  background: var(--skx-white);
  border: 1px solid var(--skx-frame-line);
  border-radius: var(--skx-radius-lg);
  box-shadow: var(--skx-frost-hilite), var(--skx-shadow-lnb);
}
.rs-head__main {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}
.rs-head__kicker {
  align-self: flex-start;
  margin: 0;
  padding: 0.1rem 0.5rem;
  font-size: 0.55rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-teal-ink);
  background: var(--skx-glass-teal);
  border-radius: var(--skx-radius-pill);
}
.rs-head__question {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-ink-strong);
  word-break: keep-all;
}
.rs-head__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem;
}
.rs-status {
  align-self: flex-start;
  padding: 0.1rem 0.45rem;
  font-size: 0.55rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-primary);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}
.rs-status--completed {
  color: var(--skx-on-accent);
  background: var(--skx-primary);
  border-color: var(--skx-primary);
}
```

④ 보고서·절 자리의 읽기용 짙은 유리 — `.rs-report` 바로 뒤(`:463`).

**Edit** `frontend/assets/css/research.css` — old:

```css
/* ── 보고서 ──────────────────────────────────────────────── */
.rs-report {
  gap: 1.2rem;
}
```

new:

```css
/* ── 보고서 ──────────────────────────────────────────────── */
.rs-report {
  gap: 1.2rem;
}
/* 보고서(초안·최종본 — ReportView)와 탐색 중 절 자리(ReportSkeleton)는 오래 읽는 면이라 결과 화면의 읽는 칸(.skx-pick__main 등 —
   round08)과 같은 '읽기용 짙은 유리'다: 바탕 --skx-read-surface, 글 톤은 이 면 안에서만 --skx-read-*(본문 거의 흰색)로 다시 정의,
   줄간격 1.6, 흐림·반사광·위 하이라이트 없음. 읽는 칸은 큰 틀 위에 겹쳐 짙어지지만 연구 화면의 카드는 움직이는 배경 위에 바로 서므로
   불투명 면(--skx-white) 위에 깐다 — 띠가 밝게 지나가도 글자가 흐려지지 않는다. 두 부품 모두 뿌리가 .rs-card.rs-report 라 부품 파일을
   고치지 않고, 첫 절이 오면 같은 자리에 초안이 서도 면이 그대로다. 밝은 읽는 면(.skx-reading)은 쓰지 않는다(사용자 결정 2026-10-13) */
.rs-card.rs-report {
  line-height: 1.6;
  color: var(--skx-ink);
  background: linear-gradient(var(--skx-read-surface), var(--skx-read-surface)), var(--skx-white);
  border-color: var(--skx-frost-menu-line);
  box-shadow: none;
  --skx-ink: var(--skx-read-ink);
  --skx-ink-2: var(--skx-read-ink-2);
  --skx-gray-1: var(--skx-read-gray-1);
}
```

⑤ + 메뉴의 켠 모드 칩과 × (`:755`·`:766`).

**Edit** `frontend/assets/css/research.css` — old:

```css
  font-weight: 700;
  color: var(--skx-white);
  background: var(--skx-primary);
  border-radius: var(--skx-radius-pill);
}
.rs-plus__chip-x {
  padding: 0 0.2rem;
  font-size: 0.7rem;
  line-height: 1;
  color: var(--skx-white);
```

new:

```css
  font-weight: 700;
  color: var(--skx-on-accent);
  background: var(--skx-primary);
  border-radius: var(--skx-radius-pill);
}
.rs-plus__chip-x {
  padding: 0 0.2rem;
  font-size: 0.7rem;
  line-height: 1;
  color: var(--skx-on-accent);
```

⑥ 보고서 작성 현황의 끝난 절 표시(`:864`).

**Edit** `frontend/assets/css/research.css` — old:

```css
.rs-synth__item.is-done .rs-synth__icon {
  color: var(--skx-white);
```

new:

```css
.rs-synth__item.is-done .rs-synth__icon {
  color: var(--skx-on-accent);
```

⑦ 큰 진행 막대 면(`:1262` 블록의 끝 넷 줄 — 앞부분 D4 가 만든 블록을 제자리에서 고친다).

**Edit** `frontend/assets/css/research.css` — old:

```css
  overflow: hidden;
  background: var(--skx-white);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-lnb);
}
.rs-pbar__stages {
```

new:

```css
  overflow: hidden;
  background: var(--skx-white);
  border: 1px solid var(--skx-frame-line);
  border-radius: var(--skx-radius-md);
  /* 다크에서는 옅은 그림자가 보이지 않아 아래로 지나가는 본문에 막대가 붙어 보인다 — 메뉴와 같은 짙은 그림자로 띄운다 */
  box-shadow: var(--skx-frost-hilite), var(--skx-shadow-banner);
}
.rs-pbar__stages {
```

⑧ 지금 단계 칩(`:1298`).

**Edit** `frontend/assets/css/research.css` — old:

```css
.rs-pbar__stage.is-current {
  color: var(--skx-white);
```

new:

```css
.rs-pbar__stage.is-current {
  color: var(--skx-on-accent);
```

⑨ 채움 끝의 빛 흐름(`:1351` 블록 안 한 줄 — `@media` 안의 같은 선택자는 `animation: none` 뿐이라 이 줄은 하나다).

**Edit** `frontend/assets/css/research.css` — old:

```css
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--skx-white) 45%, transparent), transparent);
```

new:

```css
  /* 빛은 밝은 유리 선(--skx-frost-line — 두 테마 모두 흰색 계열)이다. 짙은 면 색(--skx-white)을 섞으면 다크의 산호 막대 위로 어두운
     띠가 흐르고, 제목 글자색(--skx-ink-strong)을 섞으면 라이트(핑크)의 짙은 막대 위에서 보이지 않는다 */
  background: linear-gradient(90deg, transparent, var(--skx-frost-line), transparent);
```

⑩ 인쇄 — 화면 인쇄의 보고서와 인쇄 전용 문서(`@media print` 안 `:1507`·`:1510`).

**Edit** `frontend/assets/css/research.css` — old:

```css
  .rs-page .rs-body {
    display: block;
  }
  .rs-print {
    display: block;
    font-family: "맑은 고딕", "Malgun Gothic", "Pretendard", sans-serif;
```

new:

```css
  .rs-page .rs-body {
    display: block;
  }
  /* 화면 인쇄(Ctrl+P)의 보고서는 화면의 읽기용 짙은 유리를 그대로 찍는다 — 브라우저가 바탕을 빼고 찍으면 다크 테마의 밝은 글자만
     흰 종이에 남는다. 흰 종이에 짙은 글자는 [PDF로 저장]의 인쇄 전용 문서(.rs-print)가 맡는다 */
  .rs-page .rs-report {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  /* 인쇄 전용 문서는 밝은 읽는 면(.skx-reading — ReportPrint.vue)이라 두 테마 모두 흰 종이에 짙은 글자다. 그 면의 옅은 바탕은 찍지 않는다 */
  .rs-print {
    display: block;
    background: none;
    font-family: "맑은 고딕", "Malgun Gothic", "Pretendard", sans-serif;
```

⑪ 옆 칸 카드 머리 — 인쇄 앵커 바로 위(앞부분 L3 의 `.rs-round__state` 블록 뒤에 선다).

**Edit** `frontend/assets/css/research.css` — old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 옆 칸 카드 머리 ─────────────────────────────────────── */
/* 옆 칸의 진행 패널·근거 장부 머리를 같은 높이·글자로 맞추고 앞에 청록 세로 막대(사이드바 DeepResearch 묶음 이름과 같은 색)를
   단다. 공용 .rs-card__title 은 본문 카드(보고서 작성 현황·실패·취소·보고서 오류)와 연구 어시스턴트 부품도 쓰므로 고치지 않고
   옆 칸 안으로 좁힌다(좁은 화면 B 의 옆 칸도 같은 .rs-col-side). 앞 막대는 인라인 블록 — 장부 머리(.wk-ledger__head, baseline
   정렬)의 글자 기준선을 바꾸지 않는다 */
.rs-col-side .rs-card__title {
  font-size: 0.75rem;
  line-height: 1.6;
}
.rs-col-side .rs-card__title::before {
  content: "";
  display: inline-block;
  width: 0.25rem;
  height: 0.75rem;
  margin-right: 0.4rem;
  vertical-align: -0.1rem;
  background: var(--skx-teal-ink);
  border-radius: var(--skx-radius-pill);
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 4: 구현한다 — 인쇄 전용 문서**

**Edit** `frontend/components/research/ReportPrint.vue` — old:

```vue
    <article class="rs-print">
```

new:

```vue
    <!-- 흰 종이에 찍는 문서라 밝은 읽는 면 — 다크 테마의 밝은 글 톤이 흰 종이에 찍히지 않게 토큰을 밝은 면 값으로 바꾼다.
         화면에는 그리지 않는다(research.css 의 .rs-print — [PDF로 저장]을 누른 동안에만 body 에 붙는다) -->
    <article class="rs-print skx-reading">
```

- [ ] **Step 5: 확인한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/themeResearch.test.ts tests/unit/researchProgress.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -n -A5 "^\.rs-card__title {" assets/css/research.css
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- "frontend/pages/research/[id].vue" frontend/components/research/ReportView.vue frontend/components/research/ReportSkeleton.vue frontend/components/research/ResearchHeader.vue frontend/assets/css/style_skovix.css
```

Expected: `Test Files  2 passed (2)` / `Tests  32 passed (32)` · 전체 실패 0, `Test Files` 는 P1 수 + 1, `Tests` 는 P1 수 + 9(사본 `60 / 1240`) · `0` · `└  ✨ Build complete!` · 공용 `.rs-card__title` 여섯 줄 그대로(`margin: 0`·`font-size: 0.8rem`·`font-weight: 700`·`color: var(--skx-ink)` — 본문 카드 제목은 바뀌지 않는다) · 빈 출력(페이지·부품 마크업·round08 파일 그대로).

손 확인(선택 — Z1 Step 3 에서 함께 본다): 운영 API 에 붙인 로컬 화면에서 끝난 잡 하나를 열면 머리의 'DeepResearch' 가 청록 칩, 질문이 흰 글자로 한 단계 크고, 보고서 카드는 옆 카드보다 한 단계 짙은 초록 면에 거의 흰 글자(결과 화면의 읽는 칸과 같은 톤), 옆 칸 두 머리 앞에 청록 막대. [PDF로 저장] 미리보기는 흰 종이에 짙은 글자, Ctrl+P 미리보기는 보고서가 짙은 면 그대로 찍힌다. 사이드바 톱니의 [라이트]로 바꾸면 같은 자리가 흰 면·짙은 글자다.

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/tests/unit/helpers/cssRules.ts && git add frontend/tests/unit/themeResearch.test.ts && git add frontend/tests/unit/researchProgress.test.ts && git add frontend/assets/css/research.css && git add frontend/components/research/ReportPrint.vue && git status --short && git commit -m "[Feat] round06d — 연구 화면을 round08 다크 테마에 맞춘다(D8). 이름만 남은 '불투명 면' 토큰(--skx-white)을 글자색으로 쓰던 여섯 곳(버튼·완료 배지·켠 모드 칩·끝난 절 표시·지금 단계 칩)을 산호 위 글자 토큰(--skx-on-accent)으로, 큰 막대 빛 흐름을 두 테마 모두 흰색 계열인 밝은 유리 선(--skx-frost-line)으로 바꾼다. 다크에서 보이지 않는 옅은 그림자 대신 카드·머리·막대에 흰 8% 가장자리와 위 하이라이트를, 막대에는 짙은 그림자를 준다. 머리의 DeepResearch 를 사이드바 묶음과 같은 청록 칩으로, 질문을 흰 글자 1.1rem 으로, 상태 배지를 단계 칩과 같은 크기로, 옆 칸 두 카드 머리에 청록 앞 막대를 단다. 보고서(초안·최종본)와 탐색 중 절 자리는 결과 화면의 읽는 칸과 같은 읽기용 짙은 유리(--skx-read-surface·--skx-read-*, 줄간격 1.6, 흐림·반사광 없음 — 불투명 면 위에 깐다)이고 밝은 면(.skx-reading)은 화면에 쓰지 않는다(사용자 결정 2026-10-13). 흰 종이에 찍는 인쇄 전용 문서만 .skx-reading, 화면 인쇄는 짙은 면을 그대로 찍는다. 새 가드 테스트(themeResearch)가 research.css·사이드바 스타일의 색 리터럴 0·:root 토큰만·이 규칙들을 지키고, CSS 규칙 읽기는 helpers/cssRules 로 옮겨 같이 쓴다"
```

Expected: `A` 둘(`helpers/cssRules.ts`·`themeResearch.test.ts`)·`M` 셋, 커밋 1개.

---

### Task P3: 사이드바 — 진행 중 줄의 단계 글(숫자 없이)·'이전 연구 [n]'

결정 4 · **최종 결정 D**(2026-10-13) · 정함 21·22. round08 의 DeepResearch 묶음(`AppSidebar.vue:107-187`)에 둘을 넣는다 — 진행 중 줄의 배지 옆 단계 글('계획 중'·'대기 중'·'근거 수집 중'·'보고서 작성 중' — **숫자 없이, 기록 응답의 상태만으로**)과, '더 보기 (n)' 대신 구분선 아래 '이전 연구 [n]' 한 줄(시안 C). 진행 중 잡을 따로 읽지 않는다(30초마다 `GET /api/research/{id}` 없음), 완료 줄에는 아무것도 붙이지 않는다. 원 N3 의 이어간 연구 단계 줄·생성 폴링·'모두 보기 (N)'·배지 함수 옮기기도 하지 않는다. 진행 중 배지·'진행 중 N'(묶음 머리)은 round08 자리 그대로다.

**Files:**
- Create: `frontend/utils/sidebarResearch.ts`
- Create: `frontend/tests/unit/sidebarResearch.test.ts`
- Modify: `frontend/components/AppSidebar.vue`(템플릿 `:162` 자리·`:176-186`, script `sidebarGroups` import·`:294` 주석·`:334` 뒤·`badgeOf` 뒤 — `a084ff3` 줄, scoped CSS `.skx-history__more`)

기준선: P2 뒤 수.

**알아 둘 것:**
- **단계 글은 기록의 상태만으로(최종 결정 D):** 기록 목록 응답(`HistoryResearchStatus` — `status`·`stage`, '1-2')만 쓴다 — `created`·`planning` → '계획 중', `approved`·`queued` → '대기 중', `running` 은 `stage` 로 갈라 `explored`(탐색을 마치고 종합 중 — 보고서 작성부터 다시 시도한 잡도)·`synthesized` → '보고서 작성 중', 그 밖 → '근거 수집 중'. 진행 중 잡의 하위질문·절 수는 기록에 없고, 그것을 내려고 잡을 읽지 않는다 — 사이드바의 네트워크는 round08 그대로(마운트·진행 중일 때 30초마다 `history.refresh("research")`). 그래서 연구 화면의 큰 진행 막대(`researchProgress` — '하위질문 3/6')와 사이드바가 다른 번호를 말할 일이 없다(사이드바는 번호를 말하지 않는다). '대기 중' 은 결정 D 의 예(계획 중·근거 수집 중·보고서 작성 중) 밖의 상태에 맞춘 짧은 글이다 — 연구 어시스턴트의 생성 대기 문구(`genQueueLine` 의 '대기 중')와 같은 말.
- **어느 줄에:** 배지가 '진행 중'인 줄 = `sidebarGroups.isLiveResearch`(LIVE_STATUSES — created·planning·approved·queued·running). 승인 대기·완료·실패·취소·상태 모름은 글 없음(배지가 말한다). round08 의 폴링 조건(LIVE_STATUSES)·접힌 띠 점은 그대로다. 기록 상태는 폴링 간격(30초)만큼 늦을 수 있다 — 단계 글도 그만큼 늦다.
- **글 자리·모양:** round08 주석 `<!-- 06d: 단계 문구(stage text)는 이 배지 옆에 붙인다 -->` 자리(배지와 시각 사이). `--skx-teal-ink`(묶음 카드 안에서 `--skx-research-teal-ink` 로 다시 정의된다 — 핑크 테마도 같은 토큰), 0.6rem·굵게 600, 테두리·바탕 없음, 좁으면 말줄임(`min-width: 0`).
- **이전 연구 [n](시안 C):** `.skx-history__older` — 묶음 맨 아래 `border-top: 1px solid var(--skx-line)` 아래 한 줄, 왼쪽 '이전 연구' + 수 칩(최근 검색의 `.skx-history-chip` 을 그대로 다시 쓴다 — 같은 파일의 scoped 규칙), 오른쪽 끝 ⌄(`margin-left: auto`, 펼치면 `rotate(180deg)`, 움직임 줄이기에서 멈춤). 펼치면 '접기'(수 칩 없음). 버튼의 이름은 `aria-label`(`olderToggle` 의 '이전 연구 n건 더 보기'·'이전 연구 접기')이라 칩·⌄ 는 `aria-hidden`. 5줄 이하로 줄면 펼침을 푸는 round08 의 감시(`:345-353` — `a084ff3`)는 그대로다.
- round08 의 두 자리 주석(`:162`·`:186`)을 걷는다 — `:186` 의 '모두 보기 (N)' 은 만들지 않는다(결정 4). [+ 연구 시작하기](`startDeepResearch` — `router.push(deepResearchStartRoute())`)는 고치지 않는다(최종 결정 A — 늘 새 연구, P4).
- 테스트 +1 파일·+4(`sidebarResearch.test.ts`). 이 계획 앞 개정의 `collectPosition`(`researchProgress.ts` — 막대와 사이드바가 같은 번호를 쓰려던 것)은 사이드바가 번호를 말하지 않으므로 만들지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/sidebarResearch.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/sidebarResearch.test.ts
import { describe, expect, it } from "vitest";
import { olderToggle, statusStageLine } from "~/utils/sidebarResearch";

describe("statusStageLine — 진행 중인 연구 줄의 단계 글(기록의 상태·stage 만, 숫자 없이)", () => {
  it("계획 중·순서를 기다리는 중", () => {
    expect(statusStageLine({ status: "created", stage: "created" })).toBe("계획 중");
    expect(statusStageLine({ status: "planning", stage: "created" })).toBe("계획 중");
    expect(statusStageLine({ status: "approved", stage: "planned" })).toBe("대기 중");
    expect(statusStageLine({ status: "queued", stage: "planned" })).toBe("대기 중");
  });

  it("실행 중은 stage 로 가른다 — 탐색을 마쳤으면(explored) 보고서 작성, 아니면 근거 수집", () => {
    expect(statusStageLine({ status: "running", stage: "planned" })).toBe("근거 수집 중");
    expect(statusStageLine({ status: "running", stage: "explored" })).toBe("보고서 작성 중");
    expect(statusStageLine({ status: "running", stage: "synthesized" })).toBe("보고서 작성 중");
  });

  it("승인 대기·끝난 잡·상태를 모르는 기록은 null — 완료 줄에는 아무것도 붙이지 않는다(배지가 말한다)", () => {
    for (const status of ["awaiting_approval", "completed", "failed", "canceled"]) {
      expect(statusStageLine({ status, stage: "synthesized" })).toBeNull();
    }
    expect(statusStageLine(undefined)).toBeNull();
    expect(statusStageLine(null)).toBeNull();
  });
});

describe("olderToggle — 구분선 아래 '이전 연구 [n]' 한 줄", () => {
  it("접혀 있으면 '이전 연구'와 숨은 수 칩, 펼치면 '접기'", () => {
    expect(olderToggle(false, 3)).toEqual({ label: "이전 연구", count: 3, ariaLabel: "이전 연구 3건 더 보기" });
    expect(olderToggle(true, 0)).toEqual({ label: "접기", count: null, ariaLabel: "이전 연구 접기" });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/sidebarResearch.test.ts`

Expected: `Test Files  1 failed (1)` / `Tests  no tests` — 수집에서 `Error: Cannot find module '~/utils/sidebarResearch' imported from '…/frontend/tests/unit/sidebarResearch.test.ts'`.

- [ ] **Step 3: 구현한다 — 순수 함수**

`frontend/utils/sidebarResearch.ts` (새 파일, 전체):

```ts
// frontend/utils/sidebarResearch.ts
// 사이드바 DeepResearch 묶음(round08 AppSidebar)의 06d 몫 — 진행 중인 연구 줄의 단계 글과 구분선 아래 '이전 연구 [n]' 한 줄.
// 단계 글은 기록 목록(GET history)이 주는 잡의 상태·stage 로만 정하고 숫자를 붙이지 않는다 — 진행 중 잡의 하위질문·절 수는 기록 응답에
// 없고, 그것을 내려고 잡(GET /api/research/{id})을 따로 읽지 않는다. 완료 줄에는 아무것도 붙이지 않는다(사용자 결정 2026-10-13)
import type { HistoryResearchStatus } from "~/types/history";

// 진행 중(사이드바 배지 '진행 중' — sidebarGroups.LIVE_STATUSES)인 잡의 단계 글. 승인 대기·끝난 잡·상태 모름은 null(배지가 말한다).
// stage explored 는 탐색을 마치고 보고서를 쓰는 중이다(보고서 작성부터 다시 시도한 잡도)
export function statusStageLine(r: HistoryResearchStatus | null | undefined): string | null {
  switch (r?.status) {
    case "created":
    case "planning":
      return "계획 중";
    case "approved":
    case "queued":
      return "대기 중";
    case "running":
      return r.stage === "explored" || r.stage === "synthesized" ? "보고서 작성 중" : "근거 수집 중";
    default:
      return null;
  }
}

// 묶음이 처음 보이는 줄 수를 넘는 연구를 펼치는 한 줄(시안 C) — 접혀 있으면 '이전 연구' + 숨은 수 칩, 펼치면 '접기'
export function olderToggle(expanded: boolean, hidden: number): { label: string; count: number | null; ariaLabel: string } {
  return expanded
    ? { label: "접기", count: null, ariaLabel: "이전 연구 접기" }
    : { label: "이전 연구", count: hidden, ariaLabel: `이전 연구 ${hidden}건 더 보기` };
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/sidebarResearch.test.ts`

Expected: `Test Files  1 passed (1)` / `Tests  4 passed (4)`

- [ ] **Step 5: 사이드바에 단다 — `AppSidebar.vue`**

① 진행 중 줄의 배지 옆(round08 자리 주석을 갈음).

**Edit** `frontend/components/AppSidebar.vue` — old:

```vue
                      <span :class="['skx-history-badge', `is-${badgeOf(h).tone}`]">{{ badgeOf(h).label }}</span>
                      <!-- 06d: 단계 문구(stage text)는 이 배지 옆에 붙인다 -->
```

new:

```vue
                      <span :class="['skx-history-badge', `is-${badgeOf(h).tone}`]">{{ badgeOf(h).label }}</span>
                      <!-- 진행 중인 연구 줄에만 — 지금 단계('근거 수집 중' 등, 숫자 없이). 완료 줄에는 붙이지 않는다 -->
                      <span v-if="stageOf(h)" class="skx-history-item__stage">{{ stageOf(h) }}</span>
```

② '더 보기 (n)' → '이전 연구 [n]'(round08 의 '모두 보기' 자리 주석도 걷는다).

**Edit** `frontend/components/AppSidebar.vue` — old:

```vue
              <!-- 5줄을 넘는 딥리서치는 '더 보기'로 이 자리에서 펼친다 -->
              <button
                v-if="researchHiddenCount > 0 || researchExpanded"
                type="button"
                class="skx-history__more"
                :aria-expanded="researchExpanded"
                @click="researchExpanded = !researchExpanded"
              >
                {{ researchExpanded ? "접기" : `더 보기 (${researchHiddenCount})` }}
              </button>
              <!-- 06d: 전용 화면으로 가는 '모두 보기 (N)' 줄은 이 자리(더 보기 버튼 아래)에 둔다 — N 은 groups.researchTotal -->
```

new:

```vue
              <!-- 5줄을 넘는 연구는 구분선 아래 '이전 연구 [n]' 한 줄로 이 자리에서 펼친다(시안 C — 숫자는 최근 검색의 종류 칩과
                   같은 칩, 오른쪽 끝 ⌄, 펼치면 '접기') -->
              <button
                v-if="researchHiddenCount > 0 || researchExpanded"
                type="button"
                :class="['skx-history__older', researchExpanded && 'is-expanded']"
                :aria-expanded="researchExpanded"
                :aria-label="older.ariaLabel"
                @click="researchExpanded = !researchExpanded"
              >
                <span>{{ older.label }}</span>
                <span v-if="older.count !== null" class="skx-history-chip" aria-hidden="true">{{ older.count }}</span>
                <span class="skx-history__older-chev" aria-hidden="true">⌄</span>
              </button>
```

③ import — 진행 중 판단·사이드바 글.

**Edit** `frontend/components/AppSidebar.vue` — old:

```vue
import {
  countLiveResearch,
  entryTime,
  formatHistoryTime,
  groupSidebarHistory,
  hasActiveResearch,
} from "~/utils/sidebarGroups";
```

new:

```vue
import {
  countLiveResearch,
  entryTime,
  formatHistoryTime,
  groupSidebarHistory,
  hasActiveResearch,
  isLiveResearch,
} from "~/utils/sidebarGroups";
import { olderToggle, statusStageLine } from "~/utils/sidebarResearch";
```

④ 줄 수 주석(`:294`).

**Edit** `frontend/components/AppSidebar.vue` — old:

```vue
// 딥리서치 묶음이 처음 보이는 행 수 — 넘치는 만큼은 '더 보기 (N)' 로 이 자리에서 펼친다(전용 화면으로 가는 '모두 보기'는 템플릿의 06d 자리 주석)
```

new:

```vue
// DeepResearch 묶음이 처음 보이는 행 수 — 넘치는 만큼은 구분선 아래 '이전 연구 [n]' 한 줄로 이 자리에서 펼친다
```

⑤ 이전 연구 줄의 글(`:334` 뒤).

**Edit** `frontend/components/AppSidebar.vue` — old:

```vue
const researchHiddenCount = computed(() => groups.value.researchTotal - groups.value.research.length);
```

new:

```vue
const researchHiddenCount = computed(() => groups.value.researchTotal - groups.value.research.length);
const older = computed(() => olderToggle(researchExpanded.value, researchHiddenCount.value));
```

⑥ 단계 글 — `badgeOf` 바로 뒤.

**Edit** `frontend/components/AppSidebar.vue` — old:

```vue
    default:
      return { label: "진행 중", tone: "running" };
  }
}

```

new:

```vue
    default:
      return { label: "진행 중", tone: "running" };
  }
}

// 진행 중인 연구 줄(배지 '진행 중'과 같은 상태 — sidebarGroups.LIVE_STATUSES)에만 기록 목록이 주는 잡의 상태·stage 로 짧은 단계 글을
// 단다(utils/sidebarResearch — 숫자 없이). 그것을 내려고 잡을 따로 읽지 않는다(사용자 결정 2026-10-13). 승인 대기·완료·실패·취소 줄은
// 배지가 말한다
function stageOf(h: HistoryEntry): string | null {
  return h.kind === "research" && isLiveResearch(h) ? statusStageLine(h.research) : null;
}

```

⑦ scoped CSS — `.skx-history__more` 를 갈음하고 단계 글 규칙을 더한다.

**Edit** `frontend/components/AppSidebar.vue` — old:

```vue
/* 더 보기 / 접기 — 묶음 맨 아래의 조용한 글자 버튼 */
.skx-history__more {
  align-self: flex-start;
  padding: 0.2rem 0.4rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  font-size: 0.6rem;
  color: var(--skx-teal-ink);
  cursor: pointer;
}
.skx-history__more:hover {
  color: var(--skx-primary);
  background: var(--skx-frost-bg);
}
```

new:

```vue
/* 이전 연구 [n] / 접기 — 묶음 맨 아래 구분선 아래의 한 줄(시안 C). 숫자는 최근 검색의 종류 칩(.skx-history-chip)과 같은 칩,
   오른쪽 끝 ⌄ 는 펼치면 뒤집힌다 */
.skx-history__older {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  width: 100%;
  margin-top: 0.2rem;
  padding: 0.5rem 0.4rem 0.2rem;
  border: none;
  border-top: 1px solid var(--skx-line);
  border-radius: 0;
  background: none;
  font-size: 0.6rem;
  font-weight: 600;
  line-height: 1.5;
  color: var(--skx-teal-ink);
  text-align: left;
  cursor: pointer;
}
.skx-history__older:hover {
  color: var(--skx-primary);
}
.skx-history__older:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
.skx-history__older-chev {
  margin-left: auto;
  font-size: 0.7rem;
  line-height: 1;
  transition: transform 0.15s;
}
.skx-history__older.is-expanded .skx-history__older-chev {
  transform: rotate(180deg);
}
@media (prefers-reduced-motion: reduce) {
  .skx-history__older-chev {
    transition: none;
  }
}
/* 진행 중인 연구 줄의 단계 글 — 배지 옆의 청록 글자(테두리·바탕 없음), 좁으면 말줄임 */
.skx-history-item__stage {
  min-width: 0;
  overflow: hidden;
  font-size: 0.6rem;
  font-weight: 600;
  line-height: 1.5;
  color: var(--skx-teal-ink);
  white-space: nowrap;
  text-overflow: ellipsis;
}
```

- [ ] **Step 6: 확인한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "06d:\|skx-history__more" components/AppSidebar.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "useResearchApi\|initialResearchView" components/AppSidebar.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "router.push(deepResearchStartRoute())" components/AppSidebar.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected: `0`(자리 주석·옛 버튼이 없다 — 종료 코드 1 이 정상) · `0`(사이드바는 잡을 따로 읽지 않는다 — 결정 D) · `1`(결정 A — [+ 연구 시작하기]는 round08 그대로 늘 새 연구) · 실패 0, `Test Files` P2 뒤 + 1, `Tests` P2 뒤 + 4(사본 `61 / 1244`) · `0` · `      2 Duplicated imports "MetaPart"` · `└  ✨ Build complete!`.

손 확인(선택 — GET 만): 진행 중 연구가 있는 브라우저면 그 줄 배지 옆에 청록 '근거 수집 중'·'보고서 작성 중'(숫자 없음), 폴링(30초) 안에 바뀐다. 완료 줄에는 배지 말고 아무것도 없다. DeepResearch 기록이 6건 넘으면 묶음 맨 아래 구분선 아래 '이전 연구 [n] ⌄', 누르면 펼쳐지고 '접기 ⌃'. 브라우저 개발자 도구 Network 에 사이드바가 `/api/research/<id>` 를 부르지 않는다.

- [ ] **Step 7: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/sidebarResearch.ts && git add frontend/tests/unit/sidebarResearch.test.ts && git add frontend/components/AppSidebar.vue && git status --short && git commit -m "[Feat] round06d — 사이드바 DeepResearch 묶음의 진행 중 줄 배지 옆에 지금 단계를 청록 글자로 단다('계획 중'·'대기 중'·'근거 수집 중'·'보고서 작성 중'). 숫자는 붙이지 않고 기록 목록이 주는 잡의 상태·stage 로만 정한다 — 진행 중 잡을 따로 읽지 않는다(사용자 결정 2026-10-13). 완료·승인 대기 줄에는 붙이지 않는다. '더 보기 (n)' 은 구분선 아래 '이전 연구 [n] ⌄' 한 줄(시안 C — 숫자는 최근 검색의 종류 칩, 펼치면 '접기')로 바꾸고 '모두 보기 (N)' 자리는 걷는다"
```

Expected: `A` 둘·`M` 하나, 커밋 1개.

---

### Task P4: 늘 새 연구 + 입력창(+ 메뉴) 안 끝나지 않은 연구 한 줄 [보기]·[취소]

결정 1·2 · **최종 결정 A·B**(2026-10-13 — 이 Task 의 앞 글을 갈음) · 정함 20. **분기는 없다:** 사이드바 [+ 연구 시작하기]는 끝나지 않은 연구가 있어도 늘 메인에서 DeepResearch 모드로 새 연구를 시작한다(round08 의 `startDeepResearch` — `router.push(deepResearchStartRoute())` 그대로, 대회 시연에서 이전 연구로 가면 이상하다). 대신 공용 입력창 부품 `SearchPlusMenu.vue` 안에, DeepResearch 모드가 켜졌을 때 이 브라우저의 끝나지 않은 연구를 한 줄로 알린다 — '진행 중인 DeepResearch 1건 · [보기] [취소]'(승인 대기만 있으면 '승인 대기 중인 DeepResearch 1건 · [보기] [취소]'). [취소]는 기존 취소 API(`useResearchApi().cancel`)를 쓰고 한 번 더 눌러 확인한다('정말 취소'). 판단은 순수 함수(`utils/researchStart.ts` — vitest)와 `useResearchStarter()` 한 곳이다.

**Files:**
- Create: `frontend/utils/researchStart.ts`
- Create: `frontend/tests/unit/researchStart.test.ts`
- Modify: `frontend/composables/useResearch.ts`(vue import·`researchStart` import·`useResearchStarter` 머리와 끝)
- Modify: `frontend/components/research/SearchPlusMenu.vue`(오류 줄 뒤 알림 줄, `researchStart` import·`useResearchStarter` 줄·`watch(active, …)` 뒤 — 이 계획에서 처음 고친다, P6 이 뒤를 잇는다)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위 `.rs-start-note*` — P2 블록 뒤)

`components/AppSidebar.vue`·`pages/index.vue` 는 고치지 않는다(최종 결정 A — [+ 연구 시작하기]는 round08 그대로, 알림 줄은 + 메뉴 안).

기준선: P3 뒤 수.

**알아 둘 것:**
- **판단 재료:** `useHistory().entries`(사이드바가 마운트 때 읽고 진행 중이면 30초마다 다시 읽는 이 브라우저의 기록 — 메인·`/papers`·연구 화면 모두 `AppSidebar` 가 있어 늘 채워진다). 끝나지 않은 연구 = 진행 중(`sidebarGroups.isLiveResearch` — 사이드바 배지 '진행 중'과 같은 created·planning·approved·queued·running)과 승인 대기(`awaiting_approval`). 줄은 진행 중이 먼저, 없으면 승인 대기. 'n건' 은 그 묶음의 수, [보기]·[취소]는 그 가운데 가장 최근 것(`entryTime` — `updatedAt` 이 있으면 그것, 읽을 수 없는 시각은 가장 오래된 것 — `sidebarGroups` 의 정렬과 같은 규칙)이다. 여럿이면 하나를 취소한 뒤 다음 것이 줄에 선다. 잡 id 는 기록의 `refId`(없으면 `id` — `historyRoute.routeFor` 와 같은 규칙).
- **막지 않는다:** 보내기는 그대로다 — 기록 상태는 폴링 간격만큼 늦을 수 있어 막는 판단으로 쓰지 않는다. 서버의 승인 429 `browser_active`(같은 브라우저의 다른 잡이 approved·queued·running 이면 승인을 막는다 — `app/api/research.py`)가 마지막 안전망이다.
- **[취소] — 기존 API·한 번 확인:** `useResearchStarter().cancelResearch(jobId)` = `useResearchApi().cancel(jobId)`(`POST /api/research/{id}/cancel` — 서버 `CANCELLABLE_STATUSES` 에 승인 대기도 들어 있다) 뒤 `history.refresh("research")`(이 줄과 사이드바 배지가 함께 바뀐다 — 그새 끝나 409 '취소할 수 없는 상태입니다' 여도 다시 읽어 낡은 줄을 걷는다). 실수 방지는 두 번 누르기다: 첫 누름은 버튼을 '정말 취소'(위험색)로 바꾸고 옆에 [그대로 두기]를 세운다, 그 뒤 `NOTICE_CANCEL_ARM_MS`(400ms) 안의 누름은 받지 않는다(더블클릭 한 번에 확인까지 넘어가지 않게), 그 뒤의 두 번째 누름이 취소한다. 줄의 연구가 바뀌거나(취소·끝남·새 연구) 모드를 끄면 확인을 푼다. 실패 문구는 + 메뉴의 오류 줄(`.rs-plus__error` — `researchErrorMessage(e, 'DeepResearch를 취소하지 못했습니다')`).
- **자리:** 알림 줄은 + 메뉴 뿌리(`.rs-plus`) 안, 오류 줄 뒤다 — 그래서 메인 논문 패널·`/papers` 랜딩·논문 결과 검색바(논문 결과 [DeepResearch로 이어서 조사하기]·논문 상세 `?draft=` 로 모드가 켜지는 곳)·소장자료 결과 [DeepResearch로 이어서 조사하기](P8 8-1 — 메인으로 온다) 어디서나 같다. 랜딩 입력 상자(`.skx-search__box` — 아래 줄이 grid 의 `plus` 칸)에서는 줄바꿈(`.rs-plus:has(> .rs-start-note) { flex-wrap: wrap }`)으로 칩 줄 아래 한 줄 전체에 서고(보내기는 칩 줄 높이 — `align-self: start`), 높이가 정해진 결과 검색바(`.skx-rsearch` — 3.2rem 알약)에서는 바 아래 오른쪽에 뜬다(`position: absolute` — 오류 줄은 바 아래 왼쪽, + 메뉴·슬래시 목록이 그 위 `z-index` 40). 랜딩은 세로 가운데 정렬이라 알림 줄이 서면 입력 상자가 그 높이의 절반만큼 위로 간다 — 모드를 켤 때 한 번이고 Z1 Step 3 에서 본다.
- **모양(round08 팝오버·칩 토큰만):** 면은 + 메뉴 팝오버와 같은 `--skx-frost-menu-bg`·`--skx-frost-menu-line`·`--skx-radius-md`(결과 검색바에서 뜰 때는 `--skx-shadow-banner`), 버튼은 메뉴 칸과 같은 흰 10% 알약(`--skx-frost-bg`·hover `--skx-frost-bg-hover`), '정말 취소' 는 `--skx-danger` 바탕·`--skx-on-accent` 글자(round08 `:root` 주석 — 6:1 이상, 핑크는 짙은 빨강·밝은 글자), 초점 `--skx-accent`. 색 리터럴 없음(P2 의 가드가 지킨다).
- **`useResearchStarter` 는 + 메뉴(보내기·알림 줄)와 연구 화면(다시 시작)이 부른다** — 알림 줄의 `notice` 는 기록에서 계산만 하는 `computed` 라 연구 화면에서는 읽히지 않을 뿐 해가 없다. 지역 이름은 `notice` 다 — `startNotice`(같은 이름의 utils 함수 — Nuxt 자동 import)를 가리지 않는다.
- 테스트 +1 파일·+7.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchStart.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/researchStart.test.ts
import { describe, expect, it } from "vitest";
import { DEEP_RESEARCH } from "~/utils/brand";
import {
  NOTICE_CANCEL_ARM_MS,
  noticeCancelLabel,
  noticeCancelPress,
  researchStartState,
  startNotice,
} from "~/utils/researchStart";
import { ID1, ID2, ID3, bookEntry, researchEntry } from "./helpers/fakeHistory";

const ID4 = "44444444-4444-4444-8444-444444444444";
const ID5 = "55555555-5555-4555-8555-555555555555";
const T = (hour: number) => `2026-10-13T${String(hour).padStart(2, "0")}:00:00.000Z`;
const status = (s: string) => ({ research: { status: s, stage: "planned" } });

describe("researchStartState", () => {
  it("끝나지 않은 연구를 진행 중(순서 대기 포함)과 승인 대기로 가르고 각각 가장 최근 것부터 둔다", () => {
    const older = researchEntry(ID1, { createdAt: T(1), ...status("running") });
    const newer = researchEntry(ID2, { createdAt: T(3), ...status("queued") });
    const waiting = researchEntry(ID3, { createdAt: T(2), ...status("awaiting_approval") });
    const done = researchEntry(ID4, { createdAt: T(9), ...status("completed") });
    expect(researchStartState([older, newer, waiting, done, bookEntry(ID5, { createdAt: T(10) })])).toEqual({
      live: [newer, older],
      awaiting: [waiting],
    });
  });

  it("사이드바 배지의 진행 중 상태(created·planning·approved·queued·running)를 모두 진행 중으로 본다", () => {
    for (const s of ["created", "planning", "approved", "queued", "running"]) {
      expect(researchStartState([researchEntry(ID1, status(s))]).live.map((e) => e.id)).toEqual([ID1]);
    }
    for (const s of ["awaiting_approval", "completed", "failed", "canceled"]) {
      expect(researchStartState([researchEntry(ID1, status(s))]).live).toEqual([]);
    }
    // 상태를 모르는 기록(옛 기록·조회 실패)은 어느 쪽도 아니다
    expect(researchStartState([researchEntry(ID1)])).toEqual({ live: [], awaiting: [] });
  });

  it("시각은 updatedAt 이 있으면 그것을 보고, 읽을 수 없는 시각은 가장 오래된 것으로 친다", () => {
    const a = researchEntry(ID1, { createdAt: T(5), updatedAt: T(6), ...status("running") });
    const b = researchEntry(ID2, { createdAt: T(7), ...status("running") });
    const c = researchEntry(ID3, { createdAt: "어제", ...status("running") });
    const d = researchEntry(ID4, { createdAt: T(4), updatedAt: T(9), ...status("running") });
    expect(researchStartState([c, a, b, d]).live.map((e) => e.id)).toEqual([ID4, ID2, ID1, ID3]);
    expect(researchStartState([])).toEqual({ live: [], awaiting: [] });
  });
});

describe("startNotice — DeepResearch 모드 입력창의 한 줄", () => {
  it("진행 중인 연구가 있으면 그 수와 가장 최근 것 — 승인 대기가 함께 있어도 진행 중이 먼저", () => {
    const live = researchEntry(ID1, { createdAt: T(2), ...status("running") });
    const queued = researchEntry(ID2, { createdAt: T(1), ...status("queued") });
    const awaiting = researchEntry(ID3, { createdAt: T(3), ...status("awaiting_approval") });
    expect(startNotice(researchStartState([queued, awaiting, live]))).toEqual({
      text: `진행 중인 ${DEEP_RESEARCH} 2건`,
      jobId: ID1,
      to: { path: `/research/${ID1}` },
    });
  });

  it("승인 대기만 있으면 승인 대기 줄, 끝나지 않은 연구가 없으면 null — [보기]·[취소]는 기록의 잡 id(refId)", () => {
    const awaiting = researchEntry(ID2, { ...status("awaiting_approval"), refId: ID5 });
    expect(startNotice(researchStartState([awaiting]))).toEqual({
      text: `승인 대기 중인 ${DEEP_RESEARCH} 1건`,
      jobId: ID5,
      to: { path: `/research/${ID5}` },
    });
    expect(startNotice(researchStartState([researchEntry(ID1, status("completed"))]))).toBeNull();
  });
});

describe("noticeCancelPress · noticeCancelLabel — [취소]는 한 번 더 눌러 확인한다", () => {
  it("첫 누름은 '정말 취소'로 바꾸기만 하고, 확인은 잠깐 뒤의 두 번째 누름에서만 — 더블클릭 한 번에 넘어가지 않는다", () => {
    expect(noticeCancelPress("idle", 0, 1000)).toBe("arm");
    expect(noticeCancelPress("confirm", 1000, 1000 + NOTICE_CANCEL_ARM_MS - 1)).toBeNull();
    expect(noticeCancelPress("confirm", 1000, 1000 + NOTICE_CANCEL_ARM_MS)).toBe("run");
    // 취소하는 중에는 다시 받지 않는다
    expect(noticeCancelPress("busy", 1000, 99999)).toBeNull();
  });

  it("버튼 글은 취소 → 정말 취소 → 취소하는 중", () => {
    expect((["idle", "confirm", "busy"] as const).map(noticeCancelLabel)).toEqual(["취소", "정말 취소", "취소하는 중"]);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchStart.test.ts`

Expected: `Test Files  1 failed (1)` / `Tests  no tests` — 수집에서 `Error: Cannot find module '~/utils/researchStart' imported from '…/frontend/tests/unit/researchStart.test.ts'`.

- [ ] **Step 3: 구현한다 — 순수 함수**

`frontend/utils/researchStart.ts` (새 파일, 전체):

```ts
// frontend/utils/researchStart.ts
// DeepResearch 를 시작하는 입력창(+ 메뉴 — SearchPlusMenu)이 같이 쓰는 판단(06d 2부 — 사용자 결정 2026-10-12~13).
// 시작은 늘 새 연구다: 사이드바 [+ 연구 시작하기]는 끝나지 않은 연구가 있어도 그 화면으로 가지 않고 메인에서 DeepResearch 모드를 켠다
// (2026-10-13 — 대회 시연에서 이전 연구로 가면 이상하다). 대신 DeepResearch 모드가 켜진 입력창에 이 브라우저의 끝나지 않은 연구를
// 한 줄로 알리고 [보기]·[취소]를 둔다 — 진행 중(사이드바 배지 '진행 중'과 같은 sidebarGroups.LIVE_STATUSES)이 먼저, 없으면 승인 대기.
// 보내기는 막지 않는다 — 서버의 승인 429 browser_active 가 마지막 안전망이다(기록 상태는 사이드바 폴링 간격만큼 늦을 수 있다)
import type { HistoryEntry, ResearchEntry } from "~/types/history";
import { DEEP_RESEARCH } from "~/utils/brand";
import { routeFor, type HistoryRoute } from "~/utils/historyRoute";
import { entryTime, isLiveResearch } from "~/utils/sidebarGroups";

export interface ResearchStartState {
  /** 진행 중이거나 순서를 기다리는 연구 — 가장 최근 것부터 */
  live: ResearchEntry[];
  /** 계획 승인을 기다리는 연구 — 가장 최근 것부터 */
  awaiting: ResearchEntry[];
}

export interface StartNotice {
  /** '진행 중인 DeepResearch 1건' · '승인 대기 중인 DeepResearch 1건' */
  text: string;
  /** [취소]가 멈출 잡(그 묶음의 가장 최근 것) */
  jobId: string;
  /** [보기]가 갈 연구 화면 */
  to: HistoryRoute;
}

// [취소]의 한 번 확인 — idle → (첫 누름) confirm → (두 번째 누름) busy → idle
export type NoticeCancelStep = "idle" | "confirm" | "busy";

// 첫 누름 뒤 이만큼은 두 번째 누름을 받지 않는다 — 더블클릭 한 번에 확인까지 넘어가지 않게
export const NOTICE_CANCEL_ARM_MS = 400;

// 읽을 수 없는 시각은 가장 오래된 것으로 친다(sidebarGroups 와 같은 규칙). 같은 시각이면 먼저 온 것이 앞
function timeOf(entry: ResearchEntry): number {
  const ms = Date.parse(entryTime(entry));
  return Number.isNaN(ms) ? Number.NEGATIVE_INFINITY : ms;
}

function newestFirst(list: readonly ResearchEntry[]): ResearchEntry[] {
  return list
    .map((entry, i) => ({ entry, i, t: timeOf(entry) }))
    .sort((a, b) => (a.t === b.t ? a.i - b.i : b.t > a.t ? 1 : -1))
    .map((x) => x.entry);
}

export function researchStartState(items: readonly HistoryEntry[]): ResearchStartState {
  const research = items.filter((e): e is ResearchEntry => e.kind === "research");
  return {
    live: newestFirst(research.filter(isLiveResearch)),
    awaiting: newestFirst(research.filter((e) => e.research?.status === "awaiting_approval")),
  };
}

// DeepResearch 모드 입력창의 한 줄 — 진행 중이 먼저, 그다음 승인 대기. 둘 다 없으면 null
export function startNotice(state: ResearchStartState): StartNotice | null {
  const live = state.live.length > 0;
  const list = live ? state.live : state.awaiting;
  const target = list[0];
  if (!target) return null;
  return {
    text: `${live ? "진행 중인" : "승인 대기 중인"} ${DEEP_RESEARCH} ${list.length}건`,
    jobId: target.refId || target.id,
    to: routeFor(target),
  };
}

// [취소]를 눌렀을 때 — 처음이면 확인으로 바꾸고(arm), 확인 중이면 잠깐 뒤에만 취소한다(run). 받지 않는 누름은 null
export function noticeCancelPress(step: NoticeCancelStep, armedAt: number, now: number): "arm" | "run" | null {
  if (step === "idle") return "arm";
  if (step === "confirm" && now - armedAt >= NOTICE_CANCEL_ARM_MS) return "run";
  return null;
}

export function noticeCancelLabel(step: NoticeCancelStep): string {
  return step === "idle" ? "취소" : step === "confirm" ? "정말 취소" : "취소하는 중";
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchStart.test.ts`

Expected: `Test Files  1 passed (1)` / `Tests  7 passed (7)`

- [ ] **Step 5: 판단과 취소를 `useResearchStarter` 에 둔다**

**Edit** `frontend/composables/useResearch.ts` — old:

```ts
import { getCurrentInstance, onBeforeUnmount, onMounted, ref, shallowRef, toValue, watch, type MaybeRefOrGetter } from "vue";
```

new:

```ts
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, ref, shallowRef, toValue, watch, type MaybeRefOrGetter } from "vue";
```

**Edit** `frontend/composables/useResearch.ts` — old:

```ts
import { activeResearchId, httpStatus, researchErrorMessage } from "~/utils/researchErrors";
```

new:

```ts
import { activeResearchId, httpStatus, researchErrorMessage } from "~/utils/researchErrors";
import { researchStartState, startNotice } from "~/utils/researchStart";
```

**Edit** `frontend/composables/useResearch.ts` — old:

```ts
export function useResearchStarter() {
  const research = useResearchApi();
  const history = useHistory();

```

new:

```ts
// DeepResearch 를 시작하는 입력창(+ 메뉴 — SearchPlusMenu)이 쓰는 판단은 여기 한 곳이다 — 시작 요청(startResearch — 기록도 남긴다),
// DeepResearch 모드일 때 입력창의 한 줄(notice — 이 브라우저 기록의 끝나지 않은 연구, utils/researchStart)과 그 줄의 [취소]
// (cancelResearch). 사이드바 [+ 연구 시작하기]는 끝나지 않은 연구가 있어도 늘 메인에서 새 연구를 시작한다(사용자 결정 2026-10-13).
// 서버의 승인 429 browser_active 는 그대로 마지막 안전망이다
export function useResearchStarter() {
  const research = useResearchApi();
  const history = useHistory();
  const notice = computed(() => startNotice(researchStartState(history.entries.value)));

```

**Edit** `frontend/composables/useResearch.ts` — old:

```ts
    return job_id;
  }

  return { startResearch };
}
```

new:

```ts
    return job_id;
  }

  // 입력창 한 줄의 [취소] — 기존 취소 API 로 그 연구를 멈추고 기록을 다시 읽는다(이 줄과 사이드바 배지가 함께 바뀐다). 그새 끝나
  // 취소할 수 없어도(409) 기록을 다시 읽어 낡은 줄을 걷는다. 실패는 그대로 던진다 — 부르는 쪽이 문구를 보인다
  async function cancelResearch(jobId: string): Promise<void> {
    try {
      await research.cancel(jobId);
    } finally {
      await history.refresh("research");
    }
  }

  return { startResearch, notice, cancelResearch };
}
```

- [ ] **Step 6: + 메뉴 안의 한 줄 — `SearchPlusMenu.vue`**

① 오류 줄 바로 뒤(슬래시 명령 목록 앞).

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
    <p v-if="error" class="rs-plus__error" role="alert">{{ error }}</p>
    <!-- 슬래시 명령 목록: 초점은 입력창에 둔 채(aria-activedescendant) 방향키로 고른다.
```

new:

```vue
    <p v-if="error" class="rs-plus__error" role="alert">{{ error }}</p>
    <!-- DeepResearch 모드일 때 이 브라우저에 끝나지 않은 연구가 있으면 한 줄(사용자 결정 2026-10-13 — 판단은 useResearchStarter·
         utils/researchStart). [보기]는 그 연구 화면, [취소]는 한 번 더 눌러('정말 취소') 기존 취소 API 로 멈춘다. 보내기는 막지
         않는다 — 서버의 승인 429 browser_active 가 마지막 안전망이다. 랜딩 입력 상자에서는 칩 줄 아래, 결과 검색바에서는 바 아래에 선다 -->
    <div v-if="active?.id === 'deep-research' && notice" class="rs-start-note" role="group" :aria-labelledby="noteId">
      <span :id="noteId" class="rs-start-note__text" role="status">{{ notice.text }}</span>
      <span class="rs-start-note__dot" aria-hidden="true">·</span>
      <NuxtLink :to="notice.to" class="rs-start-note__btn">보기</NuxtLink>
      <button
        type="button"
        :class="['rs-start-note__btn', cancelStep !== 'idle' && 'is-danger']"
        :disabled="cancelStep === 'busy'"
        @click="onNoticeCancel"
      >
        {{ noticeCancelLabel(cancelStep) }}
      </button>
      <button v-if="cancelStep === 'confirm'" type="button" class="rs-start-note__btn" @click="cancelStep = 'idle'">
        그대로 두기
      </button>
    </div>
    <!-- 슬래시 명령 목록: 초점은 입력창에 둔 채(aria-activedescendant) 방향키로 고른다.
```

② import 한 줄(P6 이 이 앞 줄 `researchErrors` 를 앵커로 쓴다 — 그 뒤에 둔다).

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
import { researchErrorMessage } from "~/utils/researchErrors";
```

new:

```vue
import { researchErrorMessage } from "~/utils/researchErrors";
import { noticeCancelLabel, noticeCancelPress, type NoticeCancelStep } from "~/utils/researchStart";
```

③ 시작 판단에서 알림 줄과 취소를 받는다.

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
const { startResearch } = useResearchStarter();
```

new:

```vue
const { startResearch, notice, cancelResearch } = useResearchStarter();
```

④ 알림 줄의 [취소] — `update:mode` 감시 바로 뒤.

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
watch(active, (mode) => emit("update:mode", mode?.id ?? null), { flush: "sync" });
```

new:

```vue
watch(active, (mode) => emit("update:mode", mode?.id ?? null), { flush: "sync" });

// ── 끝나지 않은 연구 한 줄(DeepResearch 모드일 때만) ─────────
// [취소]는 두 번 눌러야 멈춘다 — 첫 누름은 '정말 취소'로 바꾸기만 하고, 잠깐(NOTICE_CANCEL_ARM_MS) 안의 누름은 받지 않는다(더블클릭
// 한 번에 확인까지 넘어가지 않게). 줄의 연구가 바뀌거나 모드를 끄면 확인을 푼다 — '정말 취소'가 다른 연구에 남지 않게
const noteId = useId();
const cancelStep = ref<NoticeCancelStep>("idle");
let cancelArmedAt = 0;

async function onNoticeCancel(): Promise<void> {
  const target = notice.value;
  if (!target) return;
  const now = Date.now();
  const press = noticeCancelPress(cancelStep.value, cancelArmedAt, now);
  if (press === "arm") {
    cancelStep.value = "confirm";
    cancelArmedAt = now;
    return;
  }
  if (press !== "run") return;
  cancelStep.value = "busy";
  error.value = "";
  try {
    await cancelResearch(target.jobId);
  } catch (e) {
    error.value = researchErrorMessage(e, `${DEEP_RESEARCH}를 취소하지 못했습니다`);
  } finally {
    cancelStep.value = "idle";
  }
}

watch([() => notice.value?.jobId, () => active.value?.id], () => {
  if (cancelStep.value === "confirm") cancelStep.value = "idle";
});
```

- [ ] **Step 7: 스타일 — `research.css`**

**Edit** `frontend/assets/css/research.css` — old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 끝나지 않은 DeepResearch 한 줄(+ 메뉴 안) ─────────────── */
/* DeepResearch 모드가 켜진 입력창에 이 브라우저의 끝나지 않은 연구를 알리는 한 줄(SearchPlusMenu — 메인·/papers 랜딩·결과 검색바가
   같은 부품). 면은 + 메뉴 팝오버와 같은 짙은 면·옅은 테두리, 버튼은 메뉴 칸과 같은 흰 10% 알약이고 '정말 취소'는 위험색이다.
   랜딩 입력 상자에서는 아래 줄(+ · 칩)의 다음 줄 전체로 내려 서고(보내기는 칩 줄 높이), 높이가 정해진 결과 검색바에서는 바 아래
   오른쪽에 뜬다(오류 문구는 바 아래 왼쪽, + 메뉴·슬래시 목록이 그 위) */
.rs-plus:has(> .rs-start-note) {
  flex-wrap: wrap;
  row-gap: 0.3rem;
}
.skx-search__box:has(> .rs-plus > .rs-start-note) > .skx-search__actions {
  align-self: start;
}
.rs-start-note {
  display: flex;
  flex: 1 0 100%;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem 0.4rem;
  min-width: 0;
  padding: 0.3rem 0.35rem 0.3rem 0.7rem;
  font-size: 0.6rem;
  line-height: 1.5;
  color: var(--skx-ink);
  background: var(--skx-frost-menu-bg);
  border: 1px solid var(--skx-frost-menu-line);
  border-radius: var(--skx-radius-md);
}
.skx-rsearch .rs-start-note {
  position: absolute;
  top: calc(100% + 0.4rem);
  right: 0;
  z-index: 30;
  flex: none;
  max-width: calc(100% - 2rem);
  box-shadow: var(--skx-shadow-banner);
}
.rs-start-note__text {
  font-weight: 700;
}
.rs-start-note__dot {
  color: var(--skx-gray-1);
}
.rs-start-note__btn {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.6rem;
  font-family: inherit;
  font-size: 0.6rem;
  font-weight: 700;
  line-height: 1.5;
  color: var(--skx-ink);
  text-decoration: none;
  white-space: nowrap;
  background: var(--skx-frost-bg);
  border: none;
  border-radius: var(--skx-radius-pill);
  cursor: pointer;
}
.rs-start-note__btn:hover {
  background: var(--skx-frost-bg-hover);
}
.rs-start-note__btn:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 1px;
}
.rs-start-note__btn.is-danger {
  color: var(--skx-on-accent);
  background: var(--skx-danger);
}
.rs-start-note__btn:disabled {
  opacity: 0.6;
  cursor: progress;
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 8: 확인한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "router.push(deepResearchStartRoute())" components/AppSidebar.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "rs-start-note" pages/index.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend/components/AppSidebar.vue frontend/pages/index.vue frontend/utils/landingStart.ts
```

Expected: `1`(결정 A — [+ 연구 시작하기]는 round08 그대로 늘 새 연구) · `0`(알림 줄은 메인 페이지가 아니라 + 메뉴 안 — 결정 B, 종료 코드 1 이 정상) · 실패 0, `Test Files` P3 뒤 + 1, `Tests` P3 뒤 + 7(사본 `62 / 1251`) · `0` · `      2 Duplicated imports "MetaPart"` · `└  ✨ Build complete!` · 빈 출력(P3 가 커밋한 사이드바 뒤로 이 Task 가 고친 것이 없다).

손 확인(선택 — GET 만, **보내지 않고 [정말 취소]를 누르지 않는다**): 진행 중 연구가 없는 브라우저에서 사이드바 [+ 연구 시작하기] → 메인 논문 패널에 DeepResearch 칩·입력창 초점, 알림 줄 없음. 진행 중 연구가 있는 브라우저에서도 [+ 연구 시작하기]는 메인으로 오고(그 연구 화면으로 가지 않는다) 칩 줄 아래 '진행 중인 DeepResearch 1건 · 보기 취소' → [보기] 가 그 연구로 → 돌아와 [취소] 한 번 → '정말 취소'·'그대로 두기' → [그대로 두기](운영 잡을 멈추지 않는다). 칩 × 로 모드를 끄면 줄이 사라진다. `/papers` 결과의 [DeepResearch로 이어서 조사하기] → 검색바 아래 오른쪽에 같은 줄.

- [ ] **Step 9: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchStart.ts && git add frontend/tests/unit/researchStart.test.ts && git add frontend/composables/useResearch.ts && git add frontend/components/research/SearchPlusMenu.vue && git add frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — DeepResearch 모드가 켜진 입력창(+ 메뉴 안)에 이 브라우저의 끝나지 않은 연구를 한 줄로 알린다: '진행 중인 DeepResearch n건 · [보기] [취소]'(진행 중이 없고 승인 대기만 있으면 '승인 대기 중인 …'). [보기]는 가장 최근 그 연구 화면, [취소]는 한 번 더 눌러('정말 취소' — 400ms 안의 두 번째 누름은 받지 않아 더블클릭으로 넘어가지 않는다) 기존 취소 API 로 멈추고 기록을 다시 읽는다. 줄이 + 메뉴 안이라 메인·/papers 랜딩·논문 결과 검색바 어디서나 같다. 사이드바 [+ 연구 시작하기]는 끝나지 않은 연구가 있어도 늘 메인에서 새 연구를 시작한다(사용자 결정 2026-10-13 — 대회 시연에서 이전 연구로 가면 이상하다). 판단은 utils/researchStart(vitest)와 useResearchStarter 한 곳, 보내기는 막지 않는다 — 승인의 429 browser_active 가 마지막 안전망"
```

Expected: `A` 둘·`M` 셋, 커밋 1개.

---

### Task P5: 예시 연구 카드 — 메인 DeepResearch 모드의 입력창 아래

결정 3 · 정함 23. 메인에서 DeepResearch 모드를 켜면 예시 칩 아래에 미리 돌린 실제 연구 카드 2~3개(질문·실행 시각·코퍼스 범위, 누르면 그 연구 화면 — 읽기 전용). 원 N5 의 예시 판단(`exampleMeta`·`exampleRoute`)과 목록 API 를 옮겨 쓰고, 원 N7(사이드바 예시 묶음)을 갈음한다.

**Files:**
- Create: `frontend/utils/researchExamples.ts`
- Create: `frontend/tests/unit/researchExamples.test.ts`
- Create: `frontend/composables/useResearchWorks.ts`
- Create: `frontend/components/research/ResearchExampleCards.vue`
- Modify: `frontend/pages/index.vue`(논문 패널 끝·import — 이 계획에서 처음 고친다. P4 는 메인 페이지를 고치지 않는다)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위 `.rs-examples*` — P4 블록 뒤)

기준선: P4 뒤 수.

**알아 둘 것:**
- **API(06d 는 백엔드를 바꾸지 않는다):** `GET /api/research-works?example=1` 은 `{id, question, phase, created_at}` 만, 최근 것부터(상한 50) — 앞 3개(`EXAMPLE_CARD_MAX`)만 쓴다. 실행 시각·범위는 예시마다 `GET /api/research/{id}/work` 의 `corpus`(`useWorkApi().getWork` — 06e 파일, 읽기만). `corpus.at` 은 잡이 끝난 시각 → `kstDateTime`(`utils/reportDocument.ts:377`) '2026년 10월 6일 09:30 실행', 범위는 `scopeLine(corpus)`(연구 화면 범위 띠와 같은 글 — '소장 KCI 적재분 N편(~YYYY) 기준 · 편수 추이는 동향이 아님'). 목록 API 는 브라우저 ID 헤더가 있어야 하므로(`list_works` 의 `get_browser_id` — `GET …/work` 는 헤더 없이도 읽힌다) 마운트 뒤에 읽는다.
- **한 번만 읽는다:** 목록·시각·범위·읽는 중을 `useState`(`skx:research-examples`·`skx:research-example-metas`·`skx:research-examples-loading`)에 두어 랜딩을 오가거나 모드를 다시 켜도 다시 읽지 않는다. 목록을 못 읽으면 `null` 로 남겨 다음에 다시 읽고, 범위를 못 읽은 카드는 그 줄만 뺀다. 예시가 없으면(리허설에서 `mark_example.py` 로 지정하기 전 — 10/17~18 배포 직후) 섹션을 그리지 않는다.
- **여는 곳:** `exampleRoute` = 도달한 단계 화면(`/research/{id}?s=<stepForPhase(phase)>` — 완료는 계획서 화면). 사이드바의 이어간 연구 줄(`historyRoute.routeFor`)과 같은 규칙이고, 예시는 쓰기 API 가 409 라 읽기 전용이다.
- **자리:** 논문 패널(`.skx-panel` — 세로 flex·gap 2rem) 안 `.skx-search` 뒤, `deepResearch` 일 때만. P4 의 끝나지 않은 연구 한 줄은 입력 상자 안(+ 메뉴)이라 카드와 자리가 겹치지 않는다. 부품은 명시 import 한다(round08 완료노트의 함정 후보 — 새 부품 파일을 자동 등록 못 해 로컬 dev 서버를 다시 띄워야 했던 일을 피한다). 카드 칸은 예시 칩과 같은 폭 흐름(`auto-fill, minmax(12rem, 1fr)` — 메인 폭 48rem 에서 세 칸, 휴대폰에서 한 칸).
- 테스트 +1 파일·+4. 부품·composable 은 typecheck·build 와 Z6 로 본다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchExamples.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/researchExamples.test.ts
import { describe, expect, it } from "vitest";
import { EXAMPLE_CARD_MAX, exampleMeta, exampleRoute, pickExamples, type WorkListItem } from "~/utils/researchExamples";
import { scopeLine } from "~/utils/workPhase";
import { ID1, ID2, ID3 } from "./helpers/fakeHistory";

const ID4 = "44444444-4444-4444-8444-444444444444";

function item(id: string, over: Partial<WorkListItem> = {}): WorkListItem {
  return { id, question: "공공도서관 서비스 품질 평가 연구가 궁금해", phase: "done", created_at: "2026-10-06T00:30:00Z", ...over };
}

describe("pickExamples", () => {
  it("메인 입력창 아래에는 받은 순서(최근 것부터)로 세 개까지만", () => {
    expect(EXAMPLE_CARD_MAX).toBe(3);
    expect(pickExamples([item(ID1), item(ID2), item(ID3), item(ID4)]).map((x) => x.id)).toEqual([ID1, ID2, ID3]);
    expect(pickExamples([item(ID1)]).map((x) => x.id)).toEqual([ID1]);
    expect(pickExamples([])).toEqual([]);
  });
});

describe("exampleMeta", () => {
  it("실행 시각은 corpus.at 의 KST, 범위는 범위 띠와 같은 scopeLine", () => {
    const corpus = { n_papers: 144748, from: "1980", to: "2017", at: "2026-10-06T00:30:00Z" };
    expect(exampleMeta(corpus)).toEqual({ ranAt: "2026년 10월 6일 09:30 실행", scope: scopeLine(corpus) });
  });

  it("코퍼스가 없거나 at 이 날짜가 아니면 그 칸은 null", () => {
    expect(exampleMeta(null)).toEqual({ ranAt: null, scope: null });
    expect(exampleMeta(undefined)).toEqual({ ranAt: null, scope: null });
    const noAt = { n_papers: 900, from: null, to: "2017", at: null };
    expect(exampleMeta(noAt)).toEqual({ ranAt: null, scope: scopeLine(noAt) });
    expect(exampleMeta({ n_papers: 900, from: null, to: null, at: "어제" }).ranAt).toBeNull();
    // 범위를 모르는(편수 0) 코퍼스도 실행 시각은 보인다
    expect(exampleMeta({ n_papers: 0, from: null, to: null, at: "2026-10-06T00:30:00Z" })).toEqual({
      ranAt: "2026년 10월 6일 09:30 실행",
      scope: null,
    });
  });
});

describe("exampleRoute", () => {
  it("예시 연구는 도달한 단계 화면으로 연다 — 사이드바의 이어간 연구 줄(historyRoute.routeFor)과 같은 규칙", () => {
    expect(exampleRoute({ id: ID1, phase: "reading" })).toEqual({ path: `/research/${ID1}`, query: { s: "reading" } });
    expect(exampleRoute({ id: ID2, phase: "done" })).toEqual({ path: `/research/${ID2}`, query: { s: "proposal" } });
    expect(exampleRoute({ id: ID3, phase: "topics" })).toEqual({ path: `/research/${ID3}`, query: { s: "topics" } });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchExamples.test.ts`

Expected: `Test Files  1 failed (1)` / `Tests  no tests` — 수집에서 `Error: Cannot find module '~/utils/researchExamples' imported from '…/frontend/tests/unit/researchExamples.test.ts'`.

- [ ] **Step 3: 구현한다 — 순수 함수**

`frontend/utils/researchExamples.ts` (새 파일, 전체):

```ts
// frontend/utils/researchExamples.ts
// 예시 연구(06d 2부 — 사용자 결정 2026-10-13: 메인에서 DeepResearch 모드를 켰을 때 입력창 아래 카드 2~3개, 사이드바에는 두지 않는다).
// 미리 돌린 실제 연구이고 읽기 전용이다(research_works.is_example — 쓰기 API 409). 카드에 실행 시각·코퍼스 범위를 함께 보인다
// (시연 정직성 규칙 — spec §12-3). .vue 는 그리기만 한다
import type { Corpus, WorkPhase } from "~/types/work";
import { kstDateTime } from "~/utils/reportDocument";
import { scopeLine, stepForPhase } from "~/utils/workPhase";

// GET /api/research-works(?example=1) 의 items[] — app/api/research_work.py list_works(상한 50, 최근 것부터)
export interface WorkListItem {
  id: string;
  question: string;
  phase: WorkPhase;
  created_at: string | null;
}

export interface WorkListOut {
  items: WorkListItem[];
}

export interface ExampleMeta {
  ranAt: string | null;
  scope: string | null;
}

// 메인 입력창 아래 카드 수(사용자 결정 '2~3개') — 예시 질문 칸과 같은 세 칸
export const EXAMPLE_CARD_MAX = 3;

export function pickExamples(items: readonly WorkListItem[]): WorkListItem[] {
  return items.slice(0, EXAMPLE_CARD_MAX);
}

// 카드의 실행 시각·코퍼스 범위. at 은 잡이 끝난 시각(research_works.corpus_snapshot — seeds.py). 모르는 칸은 null(그 줄을 그리지 않는다)
export function exampleMeta(corpus: Corpus | null | undefined): ExampleMeta {
  const at = corpus?.at ? new Date(corpus.at) : null;
  const ranAt = at && !Number.isNaN(at.getTime()) ? `${kstDateTime(at)} 실행` : null;
  return { ranAt, scope: scopeLine(corpus) };
}

// 예시 연구는 도달한 단계 화면으로 연다 — 사이드바의 이어간 연구 줄(historyRoute.routeFor)과 같은 규칙
export function exampleRoute(item: Pick<WorkListItem, "id" | "phase">): { path: string; query: { s: string } } {
  return { path: `/research/${encodeURIComponent(item.id)}`, query: { s: stepForPhase(item.phase) } };
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchExamples.test.ts`

Expected: `Test Files  1 passed (1)` / `Tests  4 passed (4)`

- [ ] **Step 5: 목록 API·카드 부품·자리**

`frontend/composables/useResearchWorks.ts` (새 파일, 전체):

```ts
// frontend/composables/useResearchWorks.ts
// 이어간 연구 목록(GET /api/research-works — ?example=1 이면 예시 연구)을 읽는다. 예시 연구 카드(메인 입력창 아래)가 쓴다
import type { WorkListItem, WorkListOut } from "~/utils/researchExamples";
import { exampleMeta, pickExamples, type ExampleMeta } from "~/utils/researchExamples";
import { useApi } from "./useApi";
import { useWorkApi } from "./useResearchWork";

export function useResearchWorksApi() {
  const api = useApi();
  return {
    listWorks: (example: boolean) => api<WorkListOut>("/research-works", { query: example ? { example: 1 } : {} }),
  };
}

// 메인 입력창 아래의 예시 연구 카드 — 목록과 예시마다의 실행 시각·범위(GET work 의 corpus)를 앱에서 한 번만 읽는다(랜딩을 오가거나
// DeepResearch 모드를 다시 켤 때마다 다시 읽지 않는다). 목록을 못 읽으면 null 로 두어 다음에 다시 읽고, 범위를 못 읽은 카드는 그 줄만 뺀다
export function useResearchExamples() {
  const { listWorks } = useResearchWorksApi();
  const workApi = useWorkApi();
  const examples = useState<WorkListItem[] | null>("skx:research-examples", () => null);
  const metas = useState<Record<string, ExampleMeta>>("skx:research-example-metas", () => ({}));
  const loading = useState<boolean>("skx:research-examples-loading", () => false);

  async function load(): Promise<void> {
    if (examples.value !== null || loading.value) return;
    loading.value = true;
    let list: WorkListItem[];
    try {
      list = pickExamples((await listWorks(true)).items);
    } catch (e) {
      console.warn("[research] 예시 연구를 읽지 못했다", e);
      return;
    } finally {
      loading.value = false;
    }
    examples.value = list;
    await Promise.all(
      list.map(async (ex) => {
        try {
          const work = await workApi.getWork(ex.id);
          metas.value = { ...metas.value, [ex.id]: exampleMeta(work.corpus) };
        } catch (e) {
          console.warn("[research] 예시 연구의 범위를 읽지 못했다", e);
        }
      }),
    );
  }

  return { examples, metas, load };
}
```

`frontend/components/research/ResearchExampleCards.vue` (새 파일, 전체):

```vue
<!-- frontend/components/research/ResearchExampleCards.vue -->
<!-- 메인에서 DeepResearch 모드를 켰을 때 입력창 아래에 서는 예시 연구 카드(06d 2부 — 사용자 결정 2026-10-13). 미리 돌린 실제 연구라
     읽기 전용이고(쓰기 API 409), 질문·실행 시각·코퍼스 범위를 보인다(시연 정직성 규칙). 누르면 그 연구 화면으로 간다.
     예시가 없거나(리허설에서 mark_example.py 로 지정하기 전) 목록을 못 읽으면 아무것도 그리지 않는다 -->
<template>
  <section v-if="examples?.length" class="rs-examples" aria-labelledby="rs-examples-title">
    <h2 id="rs-examples-title" class="rs-examples__title">예시 연구</h2>
    <p class="rs-examples__note">미리 돌려 둔 실제 연구입니다. 둘러볼 수 있고 바꿀 수는 없습니다.</p>
    <ul class="rs-examples__list">
      <li v-for="ex in examples" :key="ex.id">
        <NuxtLink :to="exampleRoute(ex)" class="rs-examples__card">
          <span class="rs-examples__kicker">읽기 전용</span>
          <span class="rs-examples__q">{{ ex.question }}</span>
          <span v-if="metas[ex.id]?.ranAt" class="rs-examples__meta">{{ metas[ex.id]?.ranAt }}</span>
          <span v-if="metas[ex.id]?.scope" class="rs-examples__meta">{{ metas[ex.id]?.scope }}</span>
        </NuxtLink>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useResearchExamples } from "~/composables/useResearchWorks";
import { exampleRoute } from "~/utils/researchExamples";

const { examples, metas, load } = useResearchExamples();

// 예시 목록 API 는 브라우저 ID 헤더가 있어야 한다 — 서버 렌더가 아니라 마운트 뒤에 읽는다(사이드바·논문 화면과 같은 관례)
onMounted(() => {
  void load();
});
</script>
```

`pages/index.vue` — 논문 패널 끝에 카드, import 한 줄(`useHistory` 줄 뒤).

**Edit** `frontend/pages/index.vue` — old:

```vue
            <span class="skx-reco-link skx-reco-link--ghost" aria-hidden="true">
              <span>내 상황에 맞는 도서 추천받기</span>
              <img src="/img/ico-arrow.svg" alt="" />
            </span>
          </div>
        </div>
```

new:

```vue
            <span class="skx-reco-link skx-reco-link--ghost" aria-hidden="true">
              <span>내 상황에 맞는 도서 추천받기</span>
              <img src="/img/ico-arrow.svg" alt="" />
            </span>
          </div>
          <!-- DeepResearch 모드일 때 예시 연구 카드(미리 돌린 실제 연구 — 읽기 전용). 예시가 없으면 그리지 않는다 -->
          <ResearchExampleCards v-if="deepResearch" />
        </div>
```

**Edit** `frontend/pages/index.vue` — old:

```vue
import { useHistory } from "~/composables/useHistory";
```

new:

```vue
import { useHistory } from "~/composables/useHistory";
import ResearchExampleCards from "~/components/research/ResearchExampleCards.vue";
```

`research.css` — 인쇄 앵커 위(P4 의 `.rs-start-note` 블록 뒤).

**Edit** `frontend/assets/css/research.css` — old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── DeepResearch 예시 연구(메인 입력창 아래) ──────────────── */
/* 메인에서 DeepResearch 모드를 켜면 예시 질문 칸 아래에 미리 돌린 실제 연구 카드 2~3개가 선다. 카드는 불투명 면이라 움직이는 배경
   위에서도 읽히고, '읽기 전용' 은 사이드바 묶음 이름과 같은 청록 칩, 실행 시각·코퍼스 범위는 작은 회색 글 */
.rs-examples {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
}
.rs-examples__title {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--skx-ink-strong);
}
.rs-examples__note {
  margin: 0;
  font-size: 0.6rem;
  line-height: 1.5;
  color: var(--skx-gray-1);
}
.rs-examples__list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
  gap: 0.45rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.rs-examples__card {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  height: 100%;
  padding: 0.8rem;
  color: var(--skx-ink);
  text-decoration: none;
  background: var(--skx-white);
  border: 1px solid var(--skx-frame-line);
  border-radius: var(--skx-radius-sm);
  transition: border-color 0.15s;
}
.rs-examples__card:hover,
.rs-examples__card:focus-visible {
  border-color: var(--skx-primary);
}
.rs-examples__card:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
.rs-examples__kicker {
  align-self: flex-start;
  padding: 0 0.4rem;
  font-size: 0.55rem;
  font-weight: 700;
  line-height: 1.6;
  color: var(--skx-teal-ink);
  background: var(--skx-glass-teal);
  border-radius: var(--skx-radius-pill);
}
.rs-examples__q {
  font-size: 0.7rem;
  font-weight: 600;
  line-height: 1.5;
  word-break: keep-all;
}
.rs-examples__meta {
  font-size: 0.55rem;
  line-height: 1.5;
  color: var(--skx-gray-1);
}
@media (prefers-reduced-motion: reduce) {
  .rs-examples__card {
    transition: none;
  }
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 6: 확인한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected: 실패 0, `Test Files` P4 뒤 + 1, `Tests` P4 뒤 + 4(사본 `63 / 1255`) · `0` · `      2 Duplicated imports "MetaPart"` · `└  ✨ Build complete!`.

손 확인(선택 — GET 만): 메인 논문 패널에서 + → DeepResearch 를 켜면 예시 칩 아래에 '예시 연구' 섹션(운영에 예시가 지정돼 있지 않으면 없다 — `curl -s "$API/research-works?example=1"` 이 `{"items":[]}` 면 그것이 맞다). 끄면 사라진다.

- [ ] **Step 7: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchExamples.ts && git add frontend/tests/unit/researchExamples.test.ts && git add frontend/composables/useResearchWorks.ts && git add frontend/components/research/ResearchExampleCards.vue && git add frontend/pages/index.vue && git add frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 메인에서 DeepResearch 모드를 켜면 입력창 아래(예시 칩 아래)에 예시 연구 카드를 세 개까지 보인다(사용자 결정 2026-10-13 — 사이드바에는 두지 않는다). 미리 돌린 실제 연구라 읽기 전용이고, 카드마다 질문·실행 시각(corpus.at KST)·코퍼스 범위(연구 화면 범위 띠와 같은 글 — 시연 정직성 규칙)를 보이며 누르면 그 연구가 도달한 단계 화면으로 간다. 목록(GET research-works?example=1)과 예시마다의 범위(GET work 의 corpus)는 useState 로 앱에서 한 번만 읽고, 예시가 없거나 못 읽으면 섹션을 그리지 않는다"
```

Expected: `A` 넷·`M` 둘, 커밋 1개.

---

### Task P6: 탐색 방식 — 폭넓게 · 정밀하게(원 N9 를 round08 뒤 코드에)

결정 5 · 원 계획 정함 19 · 정함 26. 원 계획 Task N9 의 설계(라벨 '탐색 방식', 폭넓게 `{broaden: 0, query_context: 0}` · 정밀하게 `{broaden: 1, query_context: 1}`, 기본 정밀하게, 늘 두 칸을 함께 싣는다, localStorage `skx_research_mode` 기억, [같은 질문으로 다시 시작]은 원래 잡의 두 칸, 연구 화면 머리의 작은 표시)를 그대로 두고 — `/research` 홈 Step(원 N9 Step 8)을 빼고, 앵커를 round08 뒤 `SearchPlusMenu.vue` 에 맞추고, 스타일을 다크 토큰으로 바꾼다.

**Files:**
- Create: `frontend/utils/researchMode.ts`(원 N9 Step 3 그대로 — 머리 주석의 '딥리서치' 만 'DeepResearch')
- Create: `frontend/tests/unit/researchMode.test.ts`(원 N9 Step 1 그대로 — 13)
- Create: `frontend/components/research/ResearchModePicker.vue`(원 N9 Step 6 그대로 — 머리 주석만)
- Modify: `frontend/composables/useResearch.ts`(P4 뒤 — `startResearch` 두 줄)
- Modify: `frontend/components/research/SearchPlusMenu.vue`(P4 뒤 — 칩 뒤 `:40-44`, import `:80`·`:82`·`:84`, 상태 `:114-117`, `activate` `:136-140`, `submit` `:365`, `onMounted` `:408-409` — round08 줄 번호. P4 가 더한 알림 줄(오류 줄 뒤)·`researchStart` import(`researchErrors` 줄 뒤)·`useResearchStarter` 줄·`watch(active, …)` 뒤 블록은 아래 앵커와 겹치지 않는다)
- Modify: `frontend/components/research/ResearchHeader.vue`(상태 배지 `:7`, props `:38-40`)
- Modify: `frontend/pages/research/[id].vue`(P1 뒤 — 머리 props·`researchErrors` import·`retryLabel` 뒤·`onRestart`. P2 는 이 파일을 고치지 않는다)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위 `.rs-mode*`·`.rs-head__meta`·`.rs-head__mode` — P5 블록 뒤)

기준선: P5 뒤 수.

**알아 둘 것:**
- 원 N9 의 '알아 둘 것' 가운데 선택지·두 칸 함께·백엔드 그대로(06c fastapi 가 운영에 있어야 한다 — 2026-10-12 나감)·부품 radiogroup·키가 + 메뉴의 가로채기에 걸리지 않음·기억·다시 시작·머리 표시 줄은 그대로 맞다. 바뀐 것만 적는다.
- **자리(정함 26):** `SearchPlusMenu.vue` 는 메인 논문 패널(`pages/index.vue:103`)·`/papers` 랜딩(`pages/papers/index.vue:15`)·논문 결과 검색바(`:46`)가 같이 쓴다 — DeepResearch 칩이 켜지면(+ 메뉴·슬래시 명령·`activateMode` — 메인의 `?start=`·논문 결과의 [DeepResearch로 이어서 조사하기]·상세의 `?draft=` 모두) 칩 바로 뒤에 선다(P4 의 끝나지 않은 연구 한 줄은 오류 줄 뒤라 그 아래 줄). `/research` 홈이 없으므로 원 N9 Step 8 은 없다.
- **round08·P4 뒤 앵커:** round08 이 `brand` import 를 `useResearch`·`menuNav` 사이에 넣었으므로(원 N9 '알아 둘 것' 의 round08 줄이 예상한 그대로) import 는 한 줄 앵커 셋으로 고치고, `browserId` 는 `brand` 바로 뒤에 둔다(경로 이름 순서). `researchMode` 는 `researchErrors` 바로 뒤 — P4 의 `researchStart` 줄 앞에 들어가 이름 순서가 맞는다. `clear`·`activateMode`·`update:mode`(round08)는 건드리지 않는다.
- **다크 스타일:** 칸 홈은 `--skx-frost-bg`(흰 10% — 입력 상자의 뿌연 유리 위), 고른 칸은 짙은 면(`--skx-white`)·산호 글자 — 켠 모드 칩(산호 바탕·짙은 글자)과 반대 모양이라 둘이 한 덩어리로 보이지 않는다. 초점 테두리는 `--skx-accent`(round08 의 다른 초점과 같다). 랜딩 입력 상자의 아래 줄(`.skx-search__box > .rs-plus` — grid 의 한 칸, round08 의 `.rs-plus` 는 줄바꿈이 없다)이 모자라면 칸이 다음 줄로 내려가게 `.rs-plus:has(> .rs-mode) { flex-wrap: wrap }`. 휴대폰(≤480px) 랜딩 상자와 결과 검색바에서는 설명(`.rs-mode__hint`)을 숨긴다 — 설명은 칸의 `title`·`aria-describedby` 로 남는다. 머리의 방식 알약 `.rs-head__mode` 는 P2 가 맞춘 `.rs-status` 와 같은 크기의 점선 알약(바탕 없음).
- `useResearchStarter().startResearch(question, params?)` — 부르는 곳은 `SearchPlusMenu` 의 보내기와 `[id].vue` 의 다시 시작 둘이다(Step 9 의 `grep` 이 확인).
- 테스트 +1 파일·+13.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchMode.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/researchMode.test.ts
import { describe, expect, it } from "vitest";
import {
  DEFAULT_RESEARCH_MODE,
  RESEARCH_MODES,
  RESEARCH_MODE_KEY,
  modeOfParams,
  modeParams,
  modeStep,
  readResearchMode,
  researchModeLabel,
  researchModeLine,
  restartParams,
  saveResearchMode,
} from "~/utils/researchMode";
import { MemoryStorage } from "./helpers/memoryStorage";

// 06c 배포 뒤 서버가 만든 잡의 params 모양 — 서버가 기본값을 채워 저장한다(app/api/research.py create_research)
const SERVER_DEFAULTS = { max_subquestions: 6, max_recheck: 3, exclude_off_topic: 1, critic_scope: 0 };

describe("modeParams · 선택지", () => {
  it("폭넓게는 두 칸 모두 0, 정밀하게는 두 칸 모두 1 — 늘 두 칸을 함께 싣는다", () => {
    expect(modeParams("broad")).toEqual({ broaden: 0, query_context: 0 });
    expect(modeParams("precise")).toEqual({ broaden: 1, query_context: 1 });
  });

  it("기본 선택은 정밀하게, 선택지는 폭넓게 · 정밀하게 순서", () => {
    expect(DEFAULT_RESEARCH_MODE).toBe("precise");
    expect(RESEARCH_MODES.map((m) => m.id)).toEqual(["broad", "precise"]);
    expect(RESEARCH_MODES.map((m) => researchModeLabel(m.id))).toEqual(["폭넓게", "정밀하게"]);
  });
});

describe("modeOfParams · researchModeLine", () => {
  it("두 칸이 모두 1 이면 정밀하게, 모두 0 이면 폭넓게(06c 배포 뒤·06d 전 잡)", () => {
    expect(modeOfParams({ ...SERVER_DEFAULTS, broaden: 1, query_context: 1 })).toBe("precise");
    expect(modeOfParams({ ...SERVER_DEFAULTS, broaden: 0, query_context: 0 })).toBe("broad");
    expect(researchModeLine({ ...SERVER_DEFAULTS, broaden: 1, query_context: 1 })).toBe("탐색 방식 · 정밀하게");
    expect(researchModeLine({ ...SERVER_DEFAULTS, broaden: 0, query_context: 0 })).toBe("탐색 방식 · 폭넓게");
  });

  it("두 칸이 모두 없으면(06c 전 잡·params 없음) null — 머리에 그리지 않는다", () => {
    expect(modeOfParams({})).toBeNull();
    expect(modeOfParams(SERVER_DEFAULTS)).toBeNull();
    expect(modeOfParams(null)).toBeNull();
    expect(modeOfParams(undefined)).toBeNull();
    expect(researchModeLine({})).toBeNull();
  });

  it("두 칸이 갈리면 어느 방식도 아니라 null, 한 칸만 있으면 없는 칸을 서버 기본값 0 으로 읽는다", () => {
    expect(modeOfParams({ broaden: 1, query_context: 0 })).toBeNull();
    expect(modeOfParams({ broaden: 0, query_context: 1 })).toBeNull();
    expect(modeOfParams({ broaden: 0 })).toBe("broad");
    expect(modeOfParams({ broaden: 1 })).toBeNull();
  });
});

describe("restartParams", () => {
  it("같은 질문으로 다시 시작할 때 원래 잡의 두 칸을 그대로 이어 쓴다(다른 칸은 싣지 않는다)", () => {
    expect(restartParams({ ...SERVER_DEFAULTS, broaden: 1, query_context: 1 })).toEqual({ broaden: 1, query_context: 1 });
    expect(restartParams({ ...SERVER_DEFAULTS, broaden: 0, query_context: 0 })).toEqual({ broaden: 0, query_context: 0 });
    expect(restartParams({ broaden: 1, query_context: 0 })).toEqual({ broaden: 1, query_context: 0 });
  });

  it("두 칸이 모두 없는 잡(06c 전 잡)은 기본 탐색 방식", () => {
    expect(restartParams(SERVER_DEFAULTS)).toEqual(modeParams(DEFAULT_RESEARCH_MODE));
    expect(restartParams({})).toEqual({ broaden: 1, query_context: 1 });
  });

  it("받은 params 를 고치지 않는다", () => {
    const params = { ...SERVER_DEFAULTS, broaden: 0, query_context: 0 };
    restartParams(params);
    modeOfParams(params);
    expect(params).toEqual({ ...SERVER_DEFAULTS, broaden: 0, query_context: 0 });
  });
});

describe("modeStep", () => {
  it("방향키로 옆 칸을 고르고 끝에서 돈다(radiogroup 관례), Home·End 는 처음·끝", () => {
    expect(modeStep("broad", "ArrowRight")).toBe("precise");
    expect(modeStep("broad", "ArrowDown")).toBe("precise");
    expect(modeStep("precise", "ArrowRight")).toBe("broad");
    expect(modeStep("precise", "ArrowLeft")).toBe("broad");
    expect(modeStep("broad", "ArrowUp")).toBe("precise");
    expect(modeStep("precise", "Home")).toBe("broad");
    expect(modeStep("broad", "End")).toBe("precise");
  });

  it("움직일 키가 아니면 null — 부품은 그 키를 막지 않는다(Tab·Space·Enter)", () => {
    expect(modeStep("broad", "Tab")).toBeNull();
    expect(modeStep("broad", " ")).toBeNull();
    expect(modeStep("broad", "Enter")).toBeNull();
  });
});

describe("readResearchMode · saveResearchMode", () => {
  it("고른 방식을 기억하고 다시 읽는다", () => {
    const storage = new MemoryStorage();
    saveResearchMode(storage, "broad");
    expect(storage.getItem(RESEARCH_MODE_KEY)).toBe("broad");
    expect(readResearchMode(storage)).toBe("broad");
  });

  it("저장소가 없거나 비었거나 모르는 값이면 기본 정밀하게", () => {
    expect(readResearchMode(null)).toBe("precise");
    expect(readResearchMode(new MemoryStorage())).toBe("precise");
    const storage = new MemoryStorage();
    storage.setItem(RESEARCH_MODE_KEY, "deep");
    expect(readResearchMode(storage)).toBe("precise");
  });

  it("막힌 저장소(읽기·쓰기가 던짐)에서도 던지지 않는다", () => {
    const blocked = {
      getItem: () => {
        throw new DOMException("막힘", "SecurityError");
      },
    } as unknown as Storage;
    expect(readResearchMode(blocked)).toBe("precise");
    const full = new MemoryStorage();
    full.failWith = new DOMException("쿼터 초과", "QuotaExceededError");
    expect(() => saveResearchMode(full, "broad")).not.toThrow();
    expect(() => saveResearchMode(null, "broad")).not.toThrow();
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchMode.test.ts`

Expected: `Test Files  1 failed (1)` / `Tests  no tests` — 수집에서 `Error: Cannot find module '~/utils/researchMode' imported from '…/frontend/tests/unit/researchMode.test.ts'`.

- [ ] **Step 3: 구현한다 — 순수 함수**

`frontend/utils/researchMode.ts` (새 파일, 전체):

```ts
// frontend/utils/researchMode.ts
// DeepResearch '탐색 방식'(spec D28 — 06c 판정 뒤 2026-10-12 사용자 결정). 06c 의 두 스위치를 서버 기본값으로 켜지 않고
// (app/services/research/state.py DEFAULT_PARAMS 는 0 그대로) 사용자가 DeepResearch를 시작할 때 고른다. 서버 기본값이 0 이라
// 화면이 고른 방식의 두 칸(broaden·query_context)을 늘 함께 싣는다 — query_context 만 1 이면 범위 용어(broaden 1 의
// 계획 단계가 뽑는다)가 비어 '국내 학술논문에서' 떼기만 한다
import type { ResearchParams } from "~/types/research";
import { menuStep } from "~/utils/menuNav";

export type ResearchMode = "broad" | "precise";

export interface ResearchModeOption {
  id: ResearchMode;
  label: string;
  hint: string;
}

// 잡 params 에 싣는 두 칸 — 서버 merge_params 가 정수 0~1 로 검증한다. interface 가 아니라 type 이어야
// ResearchParams(Record<string, number>)로 그대로 넘어간다(interface 에는 암묵 색인 서명이 없다)
export type ModeParams = { broaden: number; query_context: number };

export const RESEARCH_MODE_LABEL = "탐색 방식";
export const DEFAULT_RESEARCH_MODE: ResearchMode = "precise";
// 고른 방식의 기억 — 같은 브라우저의 편의일 뿐이다(없거나 읽지 못하면 기본 방식)
export const RESEARCH_MODE_KEY = "skx_research_mode";
// 화면의 칸 순서(폭넓게 · 정밀하게)
export const RESEARCH_MODES: readonly ResearchModeOption[] = [
  { id: "broad", label: "폭넓게", hint: "많이 찾지만 엉뚱한 논문이 섞일 수 있습니다" },
  {
    id: "precise",
    label: "정밀하게",
    hint: "질문의 범위를 검색어에 함께 넣어 엉뚱한 논문을 줄입니다. 관련 논문 몇 편을 놓칠 수 있습니다",
  },
];

const MODE_IDS: readonly ResearchMode[] = RESEARCH_MODES.map((m) => m.id);

function isResearchMode(value: unknown): value is ResearchMode {
  return value === "broad" || value === "precise";
}

// 서버가 검증한 값(0·1)만 온다 — 1 이 아니면 꺼짐으로 읽는다(없는 칸은 서버 기본값 0)
function switchOf(value: number | undefined): number {
  return value === 1 ? 1 : 0;
}

// 두 칸이 모두 없으면 06c 전 잡이거나 params 를 싣지 않은 응답이다(ResearchView.params 는 job.params ?? {})
function hasModeKeys(params: ResearchParams | null | undefined): params is ResearchParams {
  return !!params && ("broaden" in params || "query_context" in params);
}

export function modeParams(mode: ResearchMode): ModeParams {
  const on = mode === "precise" ? 1 : 0;
  return { broaden: on, query_context: on };
}

// 잡이 어느 방식으로 돌았나 — 두 칸이 갈리면(판정 도구로 나눠 돌린 잡 같은 경우) 어느 방식도 아니라 null
export function modeOfParams(params: ResearchParams | null | undefined): ResearchMode | null {
  if (!hasModeKeys(params)) return null;
  const broaden = switchOf(params.broaden);
  if (broaden !== switchOf(params.query_context)) return null;
  return broaden === 1 ? "precise" : "broad";
}

export function researchModeLabel(mode: ResearchMode): string {
  return RESEARCH_MODES.find((m) => m.id === mode)?.label ?? "";
}

// 연구 화면 머리의 작은 표시 — 방식을 모르면 null(그리지 않는다)
export function researchModeLine(params: ResearchParams | null | undefined): string | null {
  const mode = modeOfParams(params);
  return mode ? `${RESEARCH_MODE_LABEL} · ${researchModeLabel(mode)}` : null;
}

// 같은 질문으로 다시 시작할 때 실을 두 칸 — 원래 잡의 값을 그대로 이어 쓴다. 두 칸이 모두 없는 잡(06c 전)은 기본 방식
export function restartParams(params: ResearchParams | null | undefined): ModeParams {
  if (!hasModeKeys(params)) return modeParams(DEFAULT_RESEARCH_MODE);
  return { broaden: switchOf(params.broaden), query_context: switchOf(params.query_context) };
}

// radiogroup 의 키보드 관례 — 방향키로 옆 칸을 고르고(끝에서 돈다) Home·End 로 처음·끝. 움직일 키가 아니면 null
export function modeStep(current: ResearchMode, key: string): ResearchMode | null {
  const nav = key === "ArrowRight" ? "ArrowDown" : key === "ArrowLeft" ? "ArrowUp" : key;
  const next = menuStep(MODE_IDS.indexOf(current), nav, MODE_IDS.length);
  return next === null ? null : (MODE_IDS[next] ?? null);
}

export function readResearchMode(storage: Storage | null): ResearchMode {
  try {
    const stored = storage?.getItem(RESEARCH_MODE_KEY);
    return isResearchMode(stored) ? stored : DEFAULT_RESEARCH_MODE;
  } catch {
    return DEFAULT_RESEARCH_MODE;
  }
}

export function saveResearchMode(storage: Storage | null, mode: ResearchMode): void {
  try {
    storage?.setItem(RESEARCH_MODE_KEY, mode);
  } catch {
    // 막힌 저장소·쿼터 초과 — 이 화면에서 고른 값만 쓴다
  }
}
```

(`ModeParams` 는 `type` 이어야 `ResearchParams`(`Record<string, number>`)로 넘어간다 — 원 N9 작성 때 `interface` 로 두면 `TS2345` 두 줄. `isResearchMode`·`switchOf`·`hasModeKeys`·`MODE_IDS` 는 내보내지 않는다.)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchMode.test.ts`

Expected: `Test Files  1 passed (1)` / `Tests  13 passed (13)`

- [ ] **Step 5: `startResearch` 가 잡 params 를 받는다**

**Edit** `frontend/composables/useResearch.ts` — old:

```ts
  async function startResearch(question: string): Promise<string> {
    const { job_id } = await research.create(question);
```

new:

```ts
  // params 는 잡 파라미터(서버 merge_params 가 검증) — 탐색 방식의 두 칸(broaden·query_context)을 싣는다. 없으면 서버 기본값
  async function startResearch(question: string, params?: ResearchParams): Promise<string> {
    const { job_id } = await research.create(question, params);
```

- [ ] **Step 6: 탐색 방식 부품**

`frontend/components/research/ResearchModePicker.vue` (새 파일, 전체):

```vue
<!-- frontend/components/research/ResearchModePicker.vue -->
<!-- DeepResearch '탐색 방식'(spec D28) — 폭넓게 · 정밀하게 두 칸 선택(radiogroup). 고른 값은 v-model 로 주고받고,
     기억(localStorage)과 잡 params 싣기는 부르는 쪽이 한다 -->
<template>
  <div class="rs-mode">
    <span :id="labelId" class="rs-mode__label">{{ RESEARCH_MODE_LABEL }}</span>
    <div
      ref="group"
      class="rs-mode__group"
      role="radiogroup"
      :aria-labelledby="labelId"
      :aria-describedby="hintId"
      @keydown="onKeydown"
    >
      <!-- 고른 칸만 Tab 으로 들어온다(roving tabindex). 칸 사이는 방향키로 옮기며 고른다 -->
      <button
        v-for="m in RESEARCH_MODES"
        :key="m.id"
        type="button"
        role="radio"
        class="rs-mode__opt"
        :data-mode="m.id"
        :aria-checked="m.id === modelValue"
        :tabindex="m.id === modelValue ? 0 : -1"
        :title="m.hint"
        :disabled="disabled"
        @click="pick(m.id)"
      >
        {{ m.label }}
      </button>
    </div>
    <span :id="hintId" class="rs-mode__hint">{{ hint }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useId } from "vue";
import { RESEARCH_MODES, RESEARCH_MODE_LABEL, modeStep, type ResearchMode } from "~/utils/researchMode";

const props = withDefaults(defineProps<{ modelValue: ResearchMode; disabled?: boolean }>(), { disabled: false });
const emit = defineEmits<{ "update:modelValue": [mode: ResearchMode] }>();

const group = ref<HTMLElement | null>(null);
const labelId = useId();
const hintId = useId();
const hint = computed(() => RESEARCH_MODES.find((m) => m.id === props.modelValue)?.hint ?? "");

function pick(mode: ResearchMode): void {
  if (props.disabled || mode === props.modelValue) return;
  emit("update:modelValue", mode);
}

// 선택이 초점을 따른다(radiogroup 관례) — 옮긴 칸을 고르고 그 칸에 초점을 둔다. 방향키가 페이지를 굴리지 않게 막는다
function onKeydown(e: KeyboardEvent): void {
  if (props.disabled) return;
  const next = modeStep(props.modelValue, e.key);
  if (!next) return;
  e.preventDefault();
  pick(next);
  void nextTick(() => group.value?.querySelector<HTMLButtonElement>(`[data-mode="${next}"]`)?.focus());
}
</script>
```

- [ ] **Step 7: + 메뉴의 DeepResearch 칩 옆에 단다 — `SearchPlusMenu.vue`**

① 칩 바로 뒤.

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
      <button type="button" class="rs-plus__chip-x" :aria-label="`${active.label} 해제`" @click="clear">×</button>
    </span>
    <p v-if="error" class="rs-plus__error" role="alert">{{ error }}</p>
```

new:

```vue
      <button type="button" class="rs-plus__chip-x" :aria-label="`${active.label} 해제`" @click="clear">×</button>
    </span>
    <!-- DeepResearch 를 고르면 칩 옆에 탐색 방식(spec D28) — 고른 값을 잡 params 두 칸(broaden·query_context)으로 싣는다 -->
    <ResearchModePicker
      v-if="active?.id === 'deep-research'"
      :model-value="researchMode"
      :disabled="disabled || busy"
      @update:model-value="pickMode"
    />
    <p v-if="error" class="rs-plus__error" role="alert">{{ error }}</p>
```

② import — 한 줄 앵커 셋.

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
```

new:

```vue
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import ResearchModePicker from "~/components/research/ResearchModePicker.vue";
```

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
import { DEEP_RESEARCH } from "~/utils/brand";
```

new:

```vue
import { DEEP_RESEARCH } from "~/utils/brand";
import { safeLocalStorage } from "~/utils/browserId";
```

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
import { researchErrorMessage } from "~/utils/researchErrors";
```

new:

```vue
import { researchErrorMessage } from "~/utils/researchErrors";
import {
  DEFAULT_RESEARCH_MODE,
  modeParams,
  readResearchMode,
  saveResearchMode,
  type ResearchMode,
} from "~/utils/researchMode";
```

③ 상태.

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
const busy = ref(false);
const error = ref("");

let host: HTMLElement | null = null;
```

new:

```vue
const busy = ref(false);
const error = ref("");
// 탐색 방식 — 서버 렌더와 첫 그림이 같게 기본(정밀하게)으로 시작하고 마운트 뒤 기억한 값을 읽는다
const researchMode = ref<ResearchMode>(DEFAULT_RESEARCH_MODE);

let host: HTMLElement | null = null;
```

④ `activate` 바로 뒤.

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
function activate(mode: SearchMode): void {
  active.value = mode;
  error.value = "";
  if (field) field.placeholder = mode.placeholder;
}
```

new:

```vue
function activate(mode: SearchMode): void {
  active.value = mode;
  error.value = "";
  if (field) field.placeholder = mode.placeholder;
}

// 고른 탐색 방식은 같은 브라우저에 기억한다 — 편의일 뿐이라 저장이 막혀도 이 화면에서는 고른 값을 쓴다
function pickMode(mode: ResearchMode): void {
  researchMode.value = mode;
  saveResearchMode(safeLocalStorage(), mode);
}
```

⑤ 보내기.

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
    const jobId = await startResearch(plan.question);
```

new:

```vue
    const jobId = await startResearch(plan.question, modeParams(researchMode.value));
```

⑥ 마운트 — 기억한 방식을 읽는다.

**Edit** `frontend/components/research/SearchPlusMenu.vue` — old:

```vue
  basePlaceholder = field?.placeholder ?? "";
  focused.value = !!field && document.activeElement === field;
```

new:

```vue
  basePlaceholder = field?.placeholder ?? "";
  researchMode.value = readResearchMode(safeLocalStorage());
  focused.value = !!field && document.activeElement === field;
```

(슬래시 명령으로 칩 없이 바로 보낸 경우에도 `submit` 은 그때의 `researchMode`(기억한 값 또는 기본 정밀하게)를 싣는다. 메인 랜딩은 숨은 논문 패널의 이 부품도 마운트돼 있지만 두 칸은 칩이 켜졌을 때만 선다.)

- [ ] **Step 8: 다시 시작은 원래 잡의 방식을 잇고, 머리에 그 잡의 방식을 보인다**

`ResearchHeader.vue` ① 상태 배지를 한 줄로 묶고 옆에 방식, ② props.

**Edit** `frontend/components/research/ResearchHeader.vue` — old:

```vue
      <span class="rs-status" :class="`rs-status--${phase}`">{{ phaseLabel(phase) }}</span>
    </div>
```

new:

```vue
      <div class="rs-head__meta">
        <span class="rs-status" :class="`rs-status--${phase}`">{{ phaseLabel(phase) }}</span>
        <!-- 그 잡의 탐색 방식(spec D28) — 방식을 모르는 잡(06c 전 잡·params 없음·두 칸이 갈림)은 그리지 않는다 -->
        <span v-if="modeLine" class="rs-head__mode">{{ modeLine }}</span>
      </div>
    </div>
```

**Edit** `frontend/components/research/ResearchHeader.vue` — old:

```vue
  canRetry: boolean;
  busy: boolean;
}>();
```

new:

```vue
  canRetry: boolean;
  busy: boolean;
  // '탐색 방식 · 정밀하게' 꼴(researchModeLine) — 없거나 null 이면 그리지 않는다
  modeLine?: string | null;
}>();
```

`[id].vue`(P2 뒤) ③ 머리 props ④ import ⑤ `retryLabel` 뒤 ⑥ `onRestart`.

**Edit** `frontend/pages/research/[id].vue` — old:

```vue
          :busy="busy || restarting"
          @toggle-layout="toggleLayout"
```

new:

```vue
          :busy="busy || restarting"
          :mode-line="modeLine"
          @toggle-layout="toggleLayout"
```

**Edit** `frontend/pages/research/[id].vue` — old:

```vue
import { researchErrorMessage } from "~/utils/researchErrors";
```

new:

```vue
import { researchErrorMessage } from "~/utils/researchErrors";
import { researchModeLine, restartParams } from "~/utils/researchMode";
```

**Edit** `frontend/pages/research/[id].vue` — old:

```vue
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
```

new:

```vue
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
// 머리의 탐색 방식 — 두 칸이 다 0 이면 폭넓게, 두 칸이 없는 잡(06c 전)은 null(그리지 않는다)
const modeLine = computed(() => (view.value ? researchModeLine(view.value.params) : null));
```

**Edit** `frontend/pages/research/[id].vue` — old:

```vue
    const jobId = await startResearch(view.value.question);
```

new:

```vue
    // 원래 잡의 탐색 방식(broaden·query_context 두 칸)을 그대로 이어 쓴다 — 고르는 칸은 없다
    const jobId = await startResearch(view.value.question, restartParams(view.value.params));
```

(`[id].vue` 의 다른 두 [같은 질문으로 다시 시작] 버튼(실패·취소 카드)도 같은 `onRestart` 를 부른다.)

`research.css` — 인쇄 앵커 위(P5 의 `.rs-examples*` 블록 뒤).

**Edit** `frontend/assets/css/research.css` — old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── DeepResearch 탐색 방식(폭넓게 · 정밀하게 — spec D28) ─── */
/* + 메뉴에서 DeepResearch 를 고르면 칩 옆에 선다(메인 입력창·/papers 랜딩·결과 검색바 — 같은 SearchPlusMenu). 고른 칸은 옅은 흰
   홈 위에 짙은 면·산호 글자로 올라온다 — 켠 모드 칩(산호 바탕·짙은 글자)과 다른 모양이라 '켠 모드'와 '고른 방식'이 한 덩어리로
   보이지 않는다. 입력 상자의 아래 줄이 모자라면 칩 다음 줄로 내려간다 */
.rs-plus:has(> .rs-mode) {
  flex-wrap: wrap;
  row-gap: 0.3rem;
}
.rs-mode {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem 0.4rem;
  min-width: 0;
}
.rs-mode__label {
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-gray-1);
  white-space: nowrap;
}
.rs-mode__group {
  display: inline-flex;
  gap: 0.1rem;
  padding: 0.1rem;
  background: var(--skx-frost-bg);
  border-radius: var(--skx-radius-pill);
}
.rs-mode__opt {
  padding: 0.15rem 0.55rem;
  font-family: inherit;
  font-size: 0.6rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-gray-1);
  white-space: nowrap;
  background: none;
  border: none;
  border-radius: var(--skx-radius-pill);
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}
.rs-mode__opt[aria-checked="true"] {
  color: var(--skx-primary);
  background: var(--skx-white);
}
.rs-mode__opt:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 1px;
}
.rs-mode__opt:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
/* 고른 방식의 설명 — 자리가 있으면 칸 옆, 좁으면 다음 줄로 내려간다 */
.rs-mode__hint {
  flex: 1 1 12rem;
  font-size: 0.55rem;
  line-height: 1.4;
  color: var(--skx-gray-1);
}
/* 결과 검색바(한 줄)는 입력칸 자리가 좁다 — 설명은 칸의 title·aria-describedby 로만 두고, 좁은 화면은 라벨도 숨긴다
   (radiogroup 의 이름은 aria-labelledby 가 숨은 라벨에서도 읽는다). 휴대폰의 랜딩 입력 상자도 설명은 숨긴다 */
.skx-rsearch .rs-mode__hint {
  display: none;
}
@media (max-width: 768px) {
  .skx-rsearch .rs-mode__label {
    display: none;
  }
}
@media (max-width: 480px) {
  .skx-search__box .rs-mode__hint {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .rs-mode__opt {
    transition: none;
  }
}
/* 연구 화면 머리 — 상태 배지 옆에 그 잡의 탐색 방식(상태 배지와 같은 크기의 점선 알약) */
.rs-head__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 0.3rem;
}
.rs-head__mode {
  padding: 0.1rem 0.45rem;
  font-size: 0.55rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-gray-1);
  background: none;
  border: 1px dashed var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 9: 확인한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -rn "startResearch(" frontend/components frontend/pages
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- app
```

Expected: 실패 0, `Test Files` P5 뒤 + 1, `Tests` P5 뒤 + 13(사본 `64 / 1268`) · `0` · `      2 Duplicated imports "MetaPart"` · `└  ✨ Build complete!` · 두 줄 — `SearchPlusMenu.vue` 의 `startResearch(plan.question, modeParams(researchMode.value))`, `pages/research/[id].vue` 의 `startResearch(view.value.question, restartParams(view.value.params))`(두 번째 인자 없이 부르는 곳이 없다) · 빈 출력.

손 확인(선택 — GET 만, **보내지 않는다**): 메인에서 + → DeepResearch 를 고르면 칩 옆(좁으면 다음 줄)에 `탐색 방식` 두 칸, 처음 쓰는 브라우저면 `정밀하게` → ←→ 로 고른 칸이 바뀌고 초점이 따라간다, Tab 한 번에 두 칸을 지난다 → 새로고침 뒤 다시 켜면 고른 값이 남아 있다 → 칩 × 로 끄면 사라진다. 375px 에서 설명이 숨고 가로 스크롤이 없다. 끝난 잡의 연구 화면 머리: 06c 전 잡은 방식 표시 없음.

- [ ] **Step 10: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchMode.ts && git add frontend/tests/unit/researchMode.test.ts && git add frontend/components/research/ResearchModePicker.vue && git add frontend/composables/useResearch.ts && git add frontend/components/research/SearchPlusMenu.vue && git add frontend/components/research/ResearchHeader.vue && git add "frontend/pages/research/[id].vue" && git add frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — DeepResearch 를 시작할 때 고르는 '탐색 방식'(폭넓게 · 정밀하게, 기본 정밀하게 — spec D28)을 + 메뉴에 단다. DeepResearch 칩이 켜지면 칩 옆에 두 칸 선택(radiogroup — 방향키·Home·End, 고른 칸만 Tab)이 서고, 고른 방식을 잡 params 두 칸(폭넓게 broaden 0·query_context 0, 정밀하게 둘 다 1)으로 늘 함께 싣는다 — 서버 기본값은 0 그대로라 화면이 실어야 켜진다. 고른 값은 이 브라우저에 기억하고(skx_research_mode — 읽지 못하면 정밀하게), [같은 질문으로 다시 시작]은 원래 잡의 두 칸을 이어 쓰며, 연구 화면 머리의 상태 배지 옆에 그 잡의 방식을 작게 보인다(두 칸이 없는 06c 전 잡은 표시 없음). 별도 시작 페이지가 없어 메인 입력창·/papers·논문 결과 검색바가 같은 + 메뉴로 고른다. 스타일은 다크 토큰(고른 칸 = 짙은 면·산호 글자), 입력 상자 아래 줄이 모자라면 다음 줄로. 판단은 utils/researchMode.ts(vitest 13), 백엔드 변경 없음"
```

Expected: `A` 셋·`M` 다섯, 커밋 1개.

---

### Task P7: "이렇게 이해했어요" 바인딩 두 곳(원 L6)

결정 8 · spec §12-2 '화면 한 줄 — 06d 가 잇는 것'·§12-5. 06c 가 계획에 넘긴 넓힌 질문을 고르는 함수(`questionUsedFromSteps`)·문구(`understoodLine`)·PlanCard 의 `questionUsed` prop 을 만들었고, 06d 는 연구 화면의 두 곳 — 계획 중 카드와 승인 대기 PlanCard — 에 잇는다.

**Files:**
- Modify: `frontend/pages/research/[id].vue`(P6 뒤 — `researchEvents` import·`queueText` 아래·계획 중 카드·승인 대기 PlanCard)

기준선: P6 뒤 수.

**알아 둘 것:**
- **원 L6 의 dev 받기·충돌 Step 은 없다:** 06c(`ef202fb`)는 이 브랜치를 딴 dev(`d261476`)에 이미 들어 있다 — `utils/researchEvents.ts` 의 `questionUsedFromSteps(steps, question)`·`understoodLine(questionUsed)`(`이렇게 이해했어요: …`), `PlanCard.vue` 의 `questionUsed?: string | null` prop(`<p v-if="questionUsed" class="rs-muted rs-plan__understood">`)이 브랜치에 있다(2026-10-13 확인). Step 1 이 다시 본다.
- 원 L6 '알아 둘 것' 의 계약·계획 중 카드에도 뜬다·스타일은 더하지 않는다(`.rs-plan__understood` 는 규칙 없는 고리 — 06c 정함 22) 줄은 그대로 맞다. 앵커 넷은 앞부분 D2 와 이 계획 P6 이 바꾸지 않은 글이다(P6 은 머리 props·`researchErrors` import·`retryLabel`·`onRestart` 만 — P2 는 `[id].vue` 를 고치지 않는다).
- 테스트 +0(판단·문구는 06c 의 vitest 가 덮는다).

- [ ] **Step 1: 06c 의 이름이 브랜치에 있는가**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git merge-base --is-ancestor ef202fb HEAD && echo "06c 있음"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -n "export function questionUsedFromSteps\|export function understoodLine" frontend/utils/researchEvents.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "questionUsed" frontend/components/research/PlanCard.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -rln "export function questionUsedFromSteps\|export function understoodLine" frontend/utils frontend/composables
```

Expected: `06c 있음`, 두 줄(`export function questionUsedFromSteps(steps: ResearchStepRow[], question: string): string | null {`·`export function understoodLine(questionUsed: string): string {`), `3` 이상, `frontend/utils/researchEvents.ts` 한 줄(같은 이름을 내보내는 06d 파일이 없다). 다르면 06c 를 따른다(원 L6 Step 4 의 규칙).

- [ ] **Step 2: 두 곳에 잇는다**

**Edit** `frontend/pages/research/[id].vue` — old:

```vue
import { researchPhase } from "~/utils/researchEvents";
```

new:

```vue
import { questionUsedFromSteps, researchPhase, understoodLine } from "~/utils/researchEvents";
```

**Edit** `frontend/pages/research/[id].vue` — old:

```vue
const queueText = computed(() => (view.value ? queueLine(view.value.queue) : null));
```

new:

```vue
const queueText = computed(() => (view.value ? queueLine(view.value.queue) : null));
// 계획이 쓴 넓힌 질문("이렇게 이해했어요" 한 줄). 원 질문과 같거나(넓히기를 껐거나 원문으로 물러남) 넓히기 전 잡이면 null
const questionUsed = computed(() => (view.value ? questionUsedFromSteps(view.value.steps, view.value.question) : null));
```

**Edit** `frontend/pages/research/[id].vue` — old:

```vue
                <div class="rs-card__text">
                  <p>연구 계획을 세우는 중입니다</p>
                </div>
```

new:

```vue
                <div class="rs-card__text">
                  <p>연구 계획을 세우는 중입니다</p>
                  <!-- 넓히기가 끝나면 계획이 나오기 전에도 도는 계획 단계에 넓힌 질문이 먼저 실려 온다 -->
                  <p v-if="questionUsed" class="rs-muted rs-plan__understood">{{ understoodLine(questionUsed) }}</p>
                </div>
```

**Edit** `frontend/pages/research/[id].vue` — old:

```vue
                :max="maxSubquestions"
                editable
```

new:

```vue
                :max="maxSubquestions"
                :question-used="questionUsed"
                editable
```

(`<p v-if="questionUsed">` 안에서 `questionUsed` 는 `string` 으로 좁혀져 `understoodLine` 에 맞는다. `research.css` 는 고치지 않는다.)

- [ ] **Step 3: 확인한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "rs-plan__understood\|:question-used=\"questionUsed\"" "frontend/pages/research/[id].vue" && grep -c "rs-plan__understood" frontend/assets/css/research.css
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend/components/research/PlanCard.vue frontend/utils/researchEvents.ts frontend/types/research.ts
```

Expected: P6 뒤와 같은 수(+0) · `0` · `└  ✨ Build complete!` · `2` 와 `0`(두 곳에 잇고 CSS 규칙은 더하지 않았다 — 두 번째 `grep -c` 는 맞는 줄이 없어 종료 코드 1, `0` 이 맞다) · 빈 출력(06c 의 파일을 고치지 않았다).

- [ ] **Step 4: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "frontend/pages/research/[id].vue" && git status --short && git commit -m "[Feat] round06d — 계획 중 카드와 승인 대기 계획 카드에 '이렇게 이해했어요' 한 줄을 잇는다(06c). 06c 의 questionUsedFromSteps 가 마지막 계획 단계의 넓힌 질문을 고르고(원 질문과 같거나 06c 전 잡이면 null — 숨김) understoodLine 이 문구를 만든다 — 같은 판단·문구를 06d 가 따로 두지 않는다. 넓히기가 끝나면 계획이 나오기 전 도는 계획 단계에도 실려 와 계획 중 카드에 먼저 서고, 승인 대기에서는 PlanCard 의 questionUsed prop 으로 머리에 선다. 두 곳이 같은 클래스(rs-muted rs-plan__understood)를 쓰고 새 CSS 는 없다"
```

Expected: `M  frontend/pages/research/[id].vue`, 커밋 1개.

---

### Task P8: 소장자료 결과 [DeepResearch로 이어서 조사하기](8-1 — 한다)·[담기 ▾](8-2 — 하지 않음)

결정 6 · 정함 25 · **최종 결정 E**(2026-10-13) · 원 계획 정함 17·Task N6. round08 이 남긴 자리 — `pages/index.vue:312` 의 `<!-- 06d: [딥리서치로 더 깊게]·[담기] 는 이 패널 바로 아래(이 자리)에 들어간다 … -->`('SKOVIX 추천 1권' 패널 뒤·도서 목록 앞).

- **8-1 [DeepResearch로 이어서 조사하기] — 한다(자르는 순서 1).** [담기]와 별개다 — round08 은 논문 결과에만 `.skx-deeper` 를 만들고(`pages/papers/index.vue:170-174`) 소장자료 쪽 자리를 06d 몫으로 남겼고, 이 계획이 처음부터 06d 몫으로 두었다. 메인 입력창으로 가서 DeepResearch 모드를 켜므로 P4 의 한 줄·P5 의 예시 카드·P6 의 탐색 방식이 함께 선다(결정 A — 늘 새 연구라 이 길도 바뀐 것이 없다). 10/16 까지 끝내지 못하면 이 Task 를 가장 먼저 자른다 — 자르면 round08 의 자리 주석은 그대로 남는다.
- **8-2 [담기 ▾](원 N6) — 하지 않는다(사용자 2026-10-14 '자른다').** 사용자에게 다시 묻는 중이고 기본은 자른다(자르는 순서 1 의 앞 칸). 아래 Step 7~11 은 기록으로 남기고 **실행하지 않는다** — 마무리(Z)의 회귀 수·고친 파일 목록·리뷰 diff·배포 확인에서 뺐다. 사용자가 하자고 하면 그때 Step 7~11 을 8-1 뒤에 그대로 하고(앵커는 이 개정에서 P4·P5 뒤 글로 맞췄다), Z1 Step 1·2 의 목록에 `utils/addToWork.ts`·`tests/unit/addToWork.test.ts`·`components/research/AddToWorkMenu.vue` 셋과 +1 파일·+4 를 더한다.

**Files(8-1):**
- Modify: `frontend/utils/landingStart.ts`(`deepResearchStartRoute(draft?)`·`readStartDraft`·`queryWithoutStart`)
- Modify: `frontend/tests/unit/landingStart.test.ts`(import·`queryWithoutStart` describe 이름·it 넷)
- Modify: `frontend/pages/index.vue`(P5 뒤 — 자리 주석·`landingStart` import·`startFromQuery`·`continueAsDeepResearch`)

**Files(8-2 — 하지 않음, 하지 않는다):** Create `frontend/utils/addToWork.ts`·`frontend/tests/unit/addToWork.test.ts`·`frontend/components/research/AddToWorkMenu.vue`(원 N6 그대로, `WorkListItem` 만 `utils/researchExamples` 에서), Modify `frontend/composables/useResearchWorks.ts`(P5 뒤, `useAddToWork`)·`frontend/pages/index.vue`([담기 ▾]·import·`onAddToWork`)·`frontend/assets/css/research.css`(인쇄 앵커 위 `.rs-basket*` — P6 블록 뒤).

기준선: P7 뒤 수.

**알아 둘 것:**
- **[DeepResearch로 이어서 조사하기](8-1):** 논문 결과의 같은 버튼(round08 `.skx-deeper` — `pages/papers/index.vue:170-174`)과 같은 모양·같은 동작(시작하지 않고 입력창에 채워 모드를 켠다). 다만 메인 결과 화면의 검색바(`.skx-rsearch`)에는 + 메뉴가 없어 그 자리에서 모드를 켤 수 없다 — 사이드바 [+ 연구 시작하기]와 같은 랜딩 길 `?start=deep-research` 에 초안 `&draft=` 를 더해 메인 입력창(논문 패널)으로 간다(`router.push` — 뒤로 가기로 이 결과에 돌아온다). 초안은 화면 결과의 검색어(`resultQuery` — 입력창 글이 아니다), 줄바꿈·겹친 공백은 한 칸, 질문으로 쓸 수 없는 길이(`questionProblem` — 서버 `QUESTION_MIN` 2·`QUESTION_MAX` 500 과 같은 경계)면 싣지 않는다.
- **랜딩이 받는 순서:** 결과(`/?q=…&h=…`) → `/?start=deep-research&draft=…` 로 가면 같은 페이지의 두 감시가 생긴 순서대로 돈다 — 먼저 `h`·`q` 감시(`restoreFromQuery` — `h`·`q` 가 없어 `goLanding()` 이 결과를 걷고 입력창을 비운다, 이 부분은 await 전이라 곧바로), 다음 `start` 감시(`startFromQuery` — 초안을 읽고 주소에서 `start`·`draft` 를 지운 뒤 논문 패널·입력창에 초안·DeepResearch 모드). 주소를 지우는 `router.replace` 는 `h`·`q` 를 바꾸지 않아 감시가 다시 돌지 않는다.
- **(8-2 — 하지 않음) [담기 ▾]:** 원 N6 의 `AddToWorkMenu.vue`(키보드 관례 — 방향키·Home·End·Esc·바깥 클릭·초점 복귀)·`utils/addToWork.ts`(D17 빈 목록 문구 그대로·담기 본문 `{"state": "in"}`·고르는 줄 40자·알림 24자)·`useAddToWork`(메뉴를 처음 열 때 한 번 읽음, 담은 뒤 사이드바 기록 한 번 다시 읽기)를 그대로 쓴다. 담는 것은 'SKOVIX 추천 1권'(`topBook`) — 추천을 내세운 때(`topRecommended`)만. 서버는 `Book` 표에 있는 cnts_id 면 소장자료도 받는다(`app/api/research_reading.py:63-64`, origin `user`).
- **(8-2 — 하지 않음) 모양:** 두 버튼이 `.skx-deeper`(round08 — `margin-top: -1rem` 으로 AI 패널에 붙은 줄) 한 줄에 선다. [담기 ▾]는 옆 버튼과 같은 높이(2.4rem)의 테두리 알약, 메뉴는 + 메뉴와 같은 짙은 면(`--skx-frost-menu-bg`)에 버튼 아래 왼쪽 기준으로 열린다(줄의 왼쪽에 있으므로). 줄 간격은 `.skx-deeper:has(> .rs-basket) { gap: 0.5rem }`(style_skovix.css 를 고치지 않고 research.css 에서).
- **(8-2 — 하지 않음) 쓰는 요청은 클릭 처리기에서만:** 목록 GET 은 메뉴를 열 때(`@open`), PUT 은 항목을 고를 때(`@pick`)만. 구현 중 미리보기에서 항목을 누르지 않는다(운영 DB 에 쓴다).
- 테스트 +0 파일·+4(8-1 `landingStart.test.ts` +4). 8-2 를 하게 되면 +1 파일·+4(`addToWork.test.ts`).

- [ ] **Step 1: (8-1) 실패하는 테스트를 쓴다 — `landingStart.test.ts`**

**Edit** `frontend/tests/unit/landingStart.test.ts` — old:

```ts
import { START_DEEP_RESEARCH, deepResearchStartRoute, queryWithoutStart, readStart } from "~/utils/landingStart";
```

new:

```ts
import { START_DEEP_RESEARCH, deepResearchStartRoute, queryWithoutStart, readStart, readStartDraft } from "~/utils/landingStart";
```

`queryWithoutStart` 묶음 이름 — 이제 draft 도 지우므로 'start 만' 을 고친다(이름만, 단언은 그대로).

**Edit** `frontend/tests/unit/landingStart.test.ts` — old:

```ts
describe("queryWithoutStart — 처리한 뒤 주소에서 start 만 지운다", () => {
```

new:

```ts
describe("queryWithoutStart — 처리한 뒤 주소에서 start·draft 를 지운다", () => {
```

**Edit** `frontend/tests/unit/landingStart.test.ts` — old:

```ts
  it("start 가 없으면 같은 내용을 준다", () => {
    expect(queryWithoutStart({ q: "논문" })).toEqual({ q: "논문" });
    expect(queryWithoutStart({})).toEqual({});
  });
});
```

new:

```ts
  it("start 가 없으면 같은 내용을 준다", () => {
    expect(queryWithoutStart({ q: "논문" })).toEqual({ q: "논문" });
    expect(queryWithoutStart({})).toEqual({});
  });

  it("함께 온 질문 초안(draft)도 지운다 — 남기면 새로고침마다 고쳐 쓰던 글을 덮는다", () => {
    expect(queryWithoutStart({ start: "deep-research", draft: "국가 재정 운용", q: "논문" })).toEqual({ q: "논문" });
  });
});

describe("질문 초안(?draft=) — 소장자료 결과의 [DeepResearch로 이어서 조사하기]", () => {
  it("초안을 함께 싣는다 — 줄바꿈·겹친 공백은 한 칸으로", () => {
    expect(deepResearchStartRoute("  조선시대 고전소설을\n 연구한  자료 찾아줘 ")).toEqual({
      path: "/",
      query: { start: START_DEEP_RESEARCH, draft: "조선시대 고전소설을 연구한 자료 찾아줘" },
    });
  });

  it("질문으로 쓸 수 없는 초안(2자 미만·500자 초과·빈 글)은 싣지 않는다", () => {
    expect(deepResearchStartRoute("가")).toEqual(deepResearchStartRoute());
    expect(deepResearchStartRoute("가".repeat(501))).toEqual(deepResearchStartRoute());
    expect(deepResearchStartRoute("   ")).toEqual(deepResearchStartRoute());
  });

  it("readStartDraft 는 같은 규칙으로 읽고, 같은 키가 여럿이면 첫 값", () => {
    expect(readStartDraft({ start: "deep-research", draft: " 국가 재정  운용 " })).toBe("국가 재정 운용");
    expect(readStartDraft(parseQuery("start=deep-research&draft=%EB%85%B8%EC%9D%B8%20%EC%9A%B0%EC%9A%B8&draft=x"))).toBe("노인 우울");
    expect(readStartDraft({ draft: "가" })).toBeNull();
    expect(readStartDraft({})).toBeNull();
  });
});
```

- [ ] **Step 2: (8-1) 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/landingStart.test.ts`

Expected: `Test Files  1 failed (1)` / `Tests  3 failed | 7 passed (10)` — 실패 셋: `함께 온 질문 초안(draft)도 지운다 …`·`초안을 함께 싣는다 …`·`readStartDraft 는 같은 규칙으로 읽고 …`. `질문으로 쓸 수 없는 초안 …` 은 지금도 인자를 무시해 같은 주소를 내므로 통과한다(구현 뒤에도 통과해야 하는 경계다).

- [ ] **Step 3: (8-1) 구현한다 — `landingStart.ts`**

**Edit** `frontend/utils/landingStart.ts` — old:

```ts
// frontend/utils/landingStart.ts
// 사이드바 딥리서치 묶음의 [+ 연구 시작하기] — 랜딩('/')을 ?start=deep-research 로 열면 논문 패널에 딥리서치 모드를 켜고
// 입력창에 초점을 준다. 이미 '/' 에 있어도 쿼리가 바뀌므로 같은 경로로 동작하고, 처리한 뒤 쿼리는 지운다
import { firstValue } from "~/utils/detailSource";

export const START_DEEP_RESEARCH = "deep-research";

export function deepResearchStartRoute(): { path: string; query: { start: string } } {
  return { path: "/", query: { start: START_DEEP_RESEARCH } };
}
```

new:

```ts
// frontend/utils/landingStart.ts
// 사이드바 DeepResearch 묶음의 [+ 연구 시작하기]·소장자료 결과의 [DeepResearch로 이어서 조사하기] — 랜딩('/')을
// ?start=deep-research 로 열면 논문 패널에 DeepResearch 모드를 켜고 입력창에 초점을 준다. ?draft= 가 함께 오면 그 질문을 입력창에
// 채운다(연구는 시작하지 않는다). 이미 '/' 에 있어도 쿼리가 바뀌므로 같은 경로로 동작하고, 처리한 뒤 두 쿼리는 지운다
import { firstValue } from "~/utils/detailSource";
import { questionProblem } from "~/utils/researchInput";

export const START_DEEP_RESEARCH = "deep-research";

// 질문 초안 — 줄바꿈·겹친 공백은 한 칸으로. 질문으로 쓸 수 없는 길이(서버 QUESTION_MIN·MAX 와 같은 경계)면 싣지 않는다
function draftQuestion(text: string | undefined): string | null {
  const q = (text ?? "").replace(/\s+/g, " ").trim();
  return q && !questionProblem(q) ? q : null;
}

export function deepResearchStartRoute(draft?: string): { path: string; query: Record<string, string> } {
  const question = draftQuestion(draft);
  return { path: "/", query: question ? { start: START_DEEP_RESEARCH, draft: question } : { start: START_DEEP_RESEARCH } };
}
```

**Edit** `frontend/utils/landingStart.ts` — old:

```ts
/** 처리한 뒤 주소에 남길 쿼리 — start 만 뺀다(남기면 새로고침·뒤로 가기마다 다시 켜진다) */
export function queryWithoutStart<T extends Record<string, unknown>>(query: T): Omit<T, "start"> {
  const { start: _start, ...rest } = query;
  return rest;
}
```

new:

```ts
/** 함께 온 질문 초안(?draft=) — 없거나 질문으로 쓸 수 없으면 null */
export function readStartDraft(query: Record<string, unknown>): string | null {
  return draftQuestion(firstValue(query.draft));
}

/** 처리한 뒤 주소에 남길 쿼리 — start·draft 만 뺀다(남기면 새로고침·뒤로 가기마다 다시 켜지고 고쳐 쓰던 글을 초안이 덮는다) */
export function queryWithoutStart<T extends Record<string, unknown>>(query: T): Omit<T, "start" | "draft"> {
  const { start: _start, draft: _draft, ...rest } = query;
  return rest;
}
```

- [ ] **Step 4: (8-1) 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/landingStart.test.ts`

Expected: `Test Files  1 passed (1)` / `Tests  10 passed (10)`

- [ ] **Step 5: (8-1) 메인 — 버튼·초안 받기**

**Edit** `frontend/pages/index.vue` — old:

```vue
        <!-- 06d: [딥리서치로 더 깊게]·[담기] 는 이 패널 바로 아래(이 자리)에 들어간다 — 그때까지 DOM 을 만들지 않는다 -->
```

new:

```vue
        <!-- 이 결과에서 이어서 — [DeepResearch로 이어서 조사하기]는 메인 입력창에 이 검색어를 채우고 DeepResearch 모드를 켠다(시작은
             하지 않는다 — 논문 결과의 같은 버튼과 같은 모양) -->
        <div v-if="topBook && resultQuery" class="skx-deeper">
          <button type="button" class="skx-deeper__btn" @click="continueAsDeepResearch">
            <span aria-hidden="true">+</span> {{ DEEP_RESEARCH }}로 이어서 조사하기
          </button>
        </div>
```

**Edit** `frontend/pages/index.vue` — old:

```vue
import { queryWithoutStart, readStart } from "~/utils/landingStart";
```

new:

```vue
import { deepResearchStartRoute, queryWithoutStart, readStart, readStartDraft } from "~/utils/landingStart";
import { DEEP_RESEARCH } from "~/utils/brand";
```

**Edit** `frontend/pages/index.vue` — old:

```vue
async function startFromQuery() {
  if (route.path !== "/" || !readStart(route.query)) return;
  void router.replace({ query: queryWithoutStart(route.query) });
  if (view.value !== "landing") goLanding();
  mode.value = "paper";
  // 논문 패널이 보인 뒤에 켠다 — 숨은 패널의 입력창에는 초점이 가지 않는다
  await nextTick();
  plusMenu.value?.activateMode("deep-research");
}
```

new:

```vue
async function startFromQuery() {
  if (route.path !== "/" || !readStart(route.query)) return;
  // 소장자료 결과의 [DeepResearch로 이어서 조사하기]가 실은 질문 초안 — 주소에서 지우기 전에 읽는다
  const draft = readStartDraft(route.query);
  void router.replace({ query: queryWithoutStart(route.query) });
  if (view.value !== "landing") goLanding();
  mode.value = "paper";
  if (draft) currentQuery.value = draft;
  // 논문 패널이 보인 뒤에 켠다 — 숨은 패널의 입력창에는 초점이 가지 않는다. 초안이 있으면 초점이 글 끝에 간다
  await nextTick();
  plusMenu.value?.activateMode("deep-research");
}

// 소장자료 결과의 [DeepResearch로 이어서 조사하기] — 결과의 검색어를 메인 입력창(논문 패널)에 채우고 DeepResearch 모드를 켠다.
// 연구는 시작하지 않는다(고쳐 보내면 기존 흐름). 사이드바 [+ 연구 시작하기]와 같은 랜딩 주소(?start=)로 옮겨 뒤로 가기로 이 결과에
// 돌아온다. 입력창이 아니라 화면 결과의 검색어(resultQuery)를 싣는다
function continueAsDeepResearch() {
  void router.push(deepResearchStartRoute(resultQuery.value));
}
```

- [ ] **Step 6: (8-1) 확인하고 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "06d:" pages/index.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected: `0`(round08 자리 주석을 걷었다) · 실패 0, `Test Files` P7 뒤와 같음, `Tests` P7 뒤 + 4(사본 `64 / 1272`) · `0` · `└  ✨ Build complete!`.

손 확인(선택 — GET 만): 메인 자료 검색에서 검색한 결과의 추천 패널 아래 `+ DeepResearch로 이어서 조사하기` → 주소가 `/?start=…&draft=…` 를 거쳐 `/` 로 바뀌고 논문 패널 입력창에 그 검색어와 DeepResearch 칩·탐색 방식·(끝나지 않은 연구가 있으면) 칩 줄 아래 한 줄·(예시가 있으면) 카드가 선다. 브라우저 뒤로 가기 → 그 결과로 돌아온다. **보내지 않는다.**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/landingStart.ts && git add frontend/tests/unit/landingStart.test.ts && git add frontend/pages/index.vue && git status --short && git commit -m "[Feat] round06d — 소장자료 결과의 'SKOVIX 추천 1권' 패널 아래에 [DeepResearch로 이어서 조사하기]를 단다(round08 이 남긴 자리 — 논문 결과의 같은 버튼과 같은 모양). 메인 결과 검색바에는 + 메뉴가 없어, 사이드바 [+ 연구 시작하기]와 같은 랜딩 길(?start=deep-research)에 질문 초안(&draft= — 결과의 검색어, 줄바꿈·겹친 공백은 한 칸, 2자 미만·500자 초과면 싣지 않음)을 더해 메인 입력창에 채우고 DeepResearch 모드를 켠다. 시작은 하지 않는다. 처리한 뒤 주소에서 start·draft 를 지운다"
```

Expected: `M` 셋, 커밋 1개.

> **보류 — 아래 Step 7~11(8-2 [담기 ▾])은 하지 않는다(최종 결정 E — 사용자 답 대기, 답이 없으면 하지 않는다).** 기록으로 남긴다. 사용자가 하자고 하면 8-1 뒤에 그대로 하고 위 '8-2' 줄의 마무리 목록 보탬을 함께 한다.

- [ ] **Step 7: (8-2 — 하지 않음) 실패하는 테스트를 쓴다**

`frontend/tests/unit/addToWork.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/addToWork.test.ts
import { describe, expect, it } from "vitest";
import { ADD_TO_WORK_BODY, ADD_TO_WORK_EMPTY, addedLine, workChoiceLabel } from "~/utils/addToWork";

describe("addToWork", () => {
  it("이어간 연구가 없을 때의 문구는 D17 그대로", () => {
    expect(ADD_TO_WORK_EMPTY).toBe("보고서 끝 [이 연구 이어가기] 뒤에 담을 수 있습니다");
  });

  it("고르는 줄은 질문을 40자(코드포인트)에서 자른다", () => {
    const q = "노인의 우울과 사회적 지지에 관한 연구가 궁금해";
    expect(workChoiceLabel({ question: q })).toBe(q);
    expect(workChoiceLabel({ question: "가".repeat(40) })).toBe("가".repeat(40));
    expect(workChoiceLabel({ question: "가".repeat(41) })).toBe(`${"가".repeat(40)}…`);
    expect(workChoiceLabel({ question: "😀".repeat(41) })).toBe(`${"😀".repeat(40)}…`);
    // 줄바꿈·겹친 공백은 한 칸으로 줄인다 — 메뉴 한 줄에 선다
    expect(workChoiceLabel({ question: "  공공도서관\n 서비스  " })).toBe("공공도서관 서비스");
  });

  it("담은 뒤 알림은 「질문」 연구에 담았습니다", () => {
    expect(addedLine({ question: "공공도서관 서비스 품질 평가 연구가 궁금해" })).toBe(
      "「공공도서관 서비스 품질 평가 연구가 궁금해」 연구에 담았습니다",
    );
    expect(addedLine({ question: "가".repeat(30) })).toBe(`「${"가".repeat(24)}…」 연구에 담았습니다`);
  });

  it("담기 본문은 state in 하나다", () => {
    expect(ADD_TO_WORK_BODY).toEqual({ state: "in" });
  });
});
```

- [ ] **Step 8: (8-2 — 하지 않음) 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/addToWork.test.ts`

Expected: `Test Files  1 failed (1)` / `Tests  no tests` — 수집에서 `Error: Cannot find module '~/utils/addToWork' imported from '…/frontend/tests/unit/addToWork.test.ts'`.

- [ ] **Step 9: (8-2 — 하지 않음) 구현한다 — 순수 함수**

`frontend/utils/addToWork.ts` (새 파일, 전체):

```ts
// frontend/utils/addToWork.ts
// 소장자료 결과의 [담기 ▾](D17 — 06d 2부: 'SKOVIX 추천 1권' 패널 아래, 자르는 순서 1) — 이 브라우저의 이어간 연구를 골라
// 그 연구의 읽기 목록에 담는다
import type { WorkListItem } from "~/utils/researchExamples";

// 이어간 연구가 없을 때(D17 글자 그대로)
export const ADD_TO_WORK_EMPTY = "보고서 끝 [이 연구 이어가기] 뒤에 담을 수 있습니다";

// 담기 = 그 연구의 목록에 담음(in) — 후보(candidate)로 넣으면 사용자가 그 연구에서 다시 담아야 한다.
// 행이 없으면 서버가 origin user(자기점검이 뺀 논문이면 revived)로 만든다(app/api/research_reading.py put_reading)
export const ADD_TO_WORK_BODY = { state: "in" } as const;

const CHOICE_MAX = 40;
const ADDED_MAX = 24;

// 코드포인트로 센다 — UTF-16 단위로 자르면 이모지 같은 보충 문자가 반쪽으로 잘린다(paperResearch 의 clip 과 같은 규칙).
// 줄바꿈·겹친 공백은 한 칸으로 — 메뉴·토스트 한 줄에 선다
function clip(text: string, max: number): string {
  const chars = [...text.trim().replace(/\s+/g, " ")];
  return chars.length > max ? `${chars.slice(0, max).join("")}…` : chars.join("");
}

// 메뉴에서 고르는 줄 — 연구 질문
export function workChoiceLabel(item: Pick<WorkListItem, "question">): string {
  return clip(item.question, CHOICE_MAX);
}

// 담은 뒤 토스트
export function addedLine(item: Pick<WorkListItem, "question">): string {
  return `「${clip(item.question, ADDED_MAX)}」 연구에 담았습니다`;
}
```

(`clip` 은 내보내지 않는다 — `utils/paperResearch.ts` 의 같은 이름 함수도 비공개라 자동 import 가 겹치지 않는다.)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/addToWork.test.ts`

Expected: `Test Files  1 passed (1)` / `Tests  4 passed (4)`

- [ ] **Step 10: (8-2 — 하지 않음) 메뉴 부품·담기 상태·자리·스타일**

`frontend/components/research/AddToWorkMenu.vue` (새 파일, 전체):

```vue
<!-- frontend/components/research/AddToWorkMenu.vue -->
<!-- 소장자료 결과의 [담기 ▾](D17) — 이 브라우저의 이어간 연구를 골라 그 연구의 목록에 담는다.
     목록 읽기·담기는 부모(useAddToWork)가 한다 — 여기서는 메뉴만 연다(ReportDownloadMenu 와 같은 키보드 관례) -->
<template>
  <div ref="root" class="rs-basket" :data-cnts-id="cntsId" @keydown="onRootKeydown">
    <!-- 담는 동안(busy)은 메뉴가 열리지 않는다 — 한 번에 하나만 담는다. 글은 바꾸지 않는다 -->
    <button
      ref="trigger"
      type="button"
      class="rs-basket__btn"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-controls="open && !loading && works?.length ? menuId : undefined"
      :aria-busy="busy"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      담기 ▾
    </button>
    <!-- aria-controls 는 role="menu" 인 목록만 가리킨다(ReportDownloadMenu 와 같다) — 안내 글만 설 때는 가리킬 메뉴가 없다 -->
    <div v-if="open" class="rs-basket__menu">
      <p v-if="loading" class="rs-basket__note" role="status">
        <img src="/img/ico-spinner.svg" alt="" class="rs-basket__spin" />
        이어간 연구를 불러오는 중입니다
      </p>
      <p v-else-if="works === null" class="rs-basket__note" role="alert">
        이어간 연구 목록을 불러오지 못했습니다. 다시 열어 보세요.
      </p>
      <p v-else-if="!works.length" class="rs-basket__note">{{ ADD_TO_WORK_EMPTY }}</p>
      <ul v-else :id="menuId" ref="list" class="rs-basket__list" role="menu" aria-label="담을 연구" @keydown="onMenuKeydown">
        <li v-for="w in works" :key="w.id" role="none">
          <!-- tabindex=-1: 항목 사이는 방향키로 옮긴다. Tab 은 메뉴를 닫고 다음 요소로 간다 -->
          <button
            type="button"
            role="menuitem"
            tabindex="-1"
            class="rs-basket__item"
            :title="w.question"
            @click="choose(w.id)"
          >
            {{ workChoiceLabel(w) }}
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import { ADD_TO_WORK_EMPTY, workChoiceLabel } from "~/utils/addToWork";
import { menuStep } from "~/utils/menuNav";
import type { WorkListItem } from "~/utils/researchExamples";

const props = defineProps<{ cntsId: string; works: WorkListItem[] | null; loading: boolean; busy: boolean }>();
const emit = defineEmits<{ open: []; pick: [jobId: string] }>();

const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const list = ref<HTMLElement | null>(null);
const menuId = useId();
const open = ref(false);

function items(): HTMLElement[] {
  return Array.from(list.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
}

function focusItem(key: string): boolean {
  const all = items();
  const at = all.findIndex((el) => el === document.activeElement);
  const next = menuStep(at, key, all.length);
  if (next === null) return false;
  all[next]?.focus();
  return true;
}

// 열면 부모가 목록을 읽고(open — 이미 읽었으면 그대로), 항목이 있으면 첫 항목(위 방향키로 열면 마지막)으로 초점을 옮긴다
async function openMenu(key: "ArrowDown" | "ArrowUp" = "ArrowDown"): Promise<void> {
  if (props.busy) return;
  open.value = true;
  emit("open");
  await nextTick();
  focusItem(key);
}

function closeMenu(returnFocus: boolean): void {
  open.value = false;
  if (returnFocus) trigger.value?.focus();
}

function toggle(): void {
  if (open.value) closeMenu(false);
  else void openMenu();
}

function onTriggerKeydown(e: KeyboardEvent): void {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  e.preventDefault();
  if (open.value) focusItem(e.key === "ArrowUp" ? "End" : "Home");
  else void openMenu(e.key);
}

function onMenuKeydown(e: KeyboardEvent): void {
  // Tab 은 막지 않는다 — 버튼으로 초점을 돌려 둔 뒤 기본 동작이 그 앞뒤 요소로 옮긴다
  if (e.key === "Tab") {
    closeMenu(true);
    return;
  }
  if (focusItem(e.key)) e.preventDefault();
}

// 버튼에 초점이 있어도(마우스로 연 뒤) Esc 로 닫히게 묶음 전체에서 듣는다
function onRootKeydown(e: KeyboardEvent): void {
  if (e.key !== "Escape" || !open.value) return;
  e.preventDefault();
  e.stopPropagation();
  closeMenu(true);
}

function choose(jobId: string): void {
  closeMenu(true);
  emit("pick", jobId);
}

// 목록을 읽는 동안 연 메뉴는 항목이 늦게 선다 — 초점이 아직 버튼에 있으면 그때 첫 항목으로 옮긴다
watch(
  () => props.works,
  async () => {
    if (!open.value || document.activeElement !== trigger.value) return;
    await nextTick();
    focusItem("Home");
  },
);

function onDocumentClick(e: MouseEvent): void {
  if (root.value && e.target instanceof Node && !root.value.contains(e.target)) open.value = false;
}

// 한 화면에 메뉴가 여럿 설 수 있다 — 바깥 클릭은 열려 있는 동안만 듣는다
watch(open, (value) => {
  if (value) document.addEventListener("click", onDocumentClick);
  else document.removeEventListener("click", onDocumentClick);
});
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));
</script>
```

`composables/useResearchWorks.ts`(P5 뒤) — import 와 `useAddToWork`.

**Edit** `frontend/composables/useResearchWorks.ts` — old:

```ts
import type { WorkListItem, WorkListOut } from "~/utils/researchExamples";
import { exampleMeta, pickExamples, type ExampleMeta } from "~/utils/researchExamples";
import { useApi } from "./useApi";
import { useWorkApi } from "./useResearchWork";
```

new:

```ts
import { ref } from "vue";
import { ADD_TO_WORK_BODY, addedLine } from "~/utils/addToWork";
import type { WorkListItem, WorkListOut } from "~/utils/researchExamples";
import { exampleMeta, pickExamples, type ExampleMeta } from "~/utils/researchExamples";
import { useApi } from "./useApi";
import { useHistory } from "./useHistory";
import { useWorkApi } from "./useResearchWork";
```

**Edit** `frontend/composables/useResearchWorks.ts` — old:

```ts
  return { examples, metas, load };
}
```

new:

```ts
  return { examples, metas, load };
}

// [담기 ▾](D17) — 메뉴를 처음 열 때 이 브라우저의 이어간 연구를 한 번 읽고(이미 읽었으면 그대로), 고른 연구의 목록에 담는다
export function useAddToWork() {
  const { listWorks } = useResearchWorksApi();
  const workApi = useWorkApi();
  const history = useHistory();
  const works = ref<WorkListItem[] | null>(null);
  const loading = ref(false);
  const busy = ref(false);

  // 못 읽으면 null 로 두어 메뉴가 실패 문구를 보이고, 다시 열면 다시 읽는다
  async function load(): Promise<void> {
    if (works.value !== null || loading.value) return;
    loading.value = true;
    try {
      works.value = (await listWorks(false)).items;
    } catch (e) {
      console.warn("[research] 이어간 연구 목록을 읽지 못했다", e);
    } finally {
      loading.value = false;
    }
  }

  // 고른 연구의 목록에 담고 토스트 문구를 돌려준다. 실패는 그대로 던진다 — 부르는 쪽이 workErrorMessage(err, "담지 못했습니다")
  async function add(jobId: string, cntsId: string): Promise<string> {
    busy.value = true;
    try {
      await workApi.putReading(jobId, cntsId, ADD_TO_WORK_BODY);
    } finally {
      busy.value = false;
    }
    // 사이드바는 진행 중 연구가 있을 때만 폴링한다 — 담은 연구의 기록 시각이 바로 맞게 한 번 다시 읽는다. 실패는 refresh 가 안에서
    // 삼킨다(historyState) — 기다리지 않는다(useResearchWork 의 afterAction 선례)
    void history.refresh("research");
    const item = works.value?.find((w) => w.id === jobId);
    return item ? addedLine(item) : "연구에 담았습니다";
  }

  return { works, loading, busy, load, add };
}
```

`pages/index.vue`(8-1 뒤) — 버튼 줄에 [담기 ▾], import, 담기 처리기.

**Edit** `frontend/pages/index.vue` — old:

```vue
          <button type="button" class="skx-deeper__btn" @click="continueAsDeepResearch">
            <span aria-hidden="true">+</span> {{ DEEP_RESEARCH }}로 이어서 조사하기
          </button>
        </div>
```

new:

```vue
          <button type="button" class="skx-deeper__btn" @click="continueAsDeepResearch">
            <span aria-hidden="true">+</span> {{ DEEP_RESEARCH }}로 이어서 조사하기
          </button>
          <!-- 추천 1권을 이 브라우저의 이어간 연구 목록에 담기(D17) — 추천을 내세운 때만 -->
          <AddToWorkMenu
            v-if="topRecommended"
            :cnts-id="topBook.book_id"
            :works="addToWork.works.value"
            :loading="addToWork.loading.value"
            :busy="addToWork.busy.value"
            @open="addToWork.load()"
            @pick="onAddToWork($event, topBook.book_id)"
          />
        </div>
```

**Edit** `frontend/pages/index.vue` — old:

```vue
import { useHistory } from "~/composables/useHistory";
import ResearchExampleCards from "~/components/research/ResearchExampleCards.vue";
```

new:

```vue
import { useHistory } from "~/composables/useHistory";
import { useAddToWork } from "~/composables/useResearchWorks";
import AddToWorkMenu from "~/components/research/AddToWorkMenu.vue";
import ResearchExampleCards from "~/components/research/ResearchExampleCards.vue";
import { workErrorMessage } from "~/utils/researchErrors";
```

**Edit** `frontend/pages/index.vue` — old:

```vue
function continueAsDeepResearch() {
  void router.push(deepResearchStartRoute(resultQuery.value));
}
```

new:

```vue
function continueAsDeepResearch() {
  void router.push(deepResearchStartRoute(resultQuery.value));
}

// 추천 1권 [담기 ▾](D17) — 메뉴를 처음 열 때 이 브라우저의 이어간 연구를 한 번 읽는다. 담은 결과는 토스트로 알린다
const addToWork = useAddToWork();

async function onAddToWork(jobId: string, cntsId: string): Promise<void> {
  try {
    showToast(await addToWork.add(jobId, cntsId));
  } catch (e) {
    showToast(workErrorMessage(e, "담지 못했습니다"));
  }
}
```

`research.css` — 인쇄 앵커 위(P6 블록 뒤).

**Edit** `frontend/assets/css/research.css` — old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 소장자료 결과 [담기 ▾](D17) ───────────────────────────── */
/* 'SKOVIX 추천 1권' 패널 아래 [DeepResearch로 이어서 조사하기] 옆에 선다(그 줄 .skx-deeper — style_skovix.css). 버튼은 옆 버튼과
   같은 높이의 알약이고 테두리만 있다. 메뉴는 + 메뉴와 같은 짙은 면(--skx-frost-menu-bg)에 버튼 아래로 열린다 */
.skx-deeper:has(> .rs-basket) {
  flex-wrap: wrap;
  gap: 0.5rem;
}
.rs-basket {
  position: relative;
  display: inline-flex;
}
.rs-basket__btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  min-height: 2.4rem;
  padding: 0.5rem 1rem;
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-ink);
  background: none;
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
  cursor: pointer;
}
.rs-basket__btn:hover,
.rs-basket__btn[aria-expanded="true"] {
  border-color: var(--skx-primary);
}
.rs-basket__btn:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
.rs-basket__btn[aria-busy="true"] {
  cursor: progress;
}
.rs-basket__menu {
  position: absolute;
  top: calc(100% + 0.3rem);
  left: 0;
  z-index: 40;
  width: 16rem;
  max-width: 80vw;
  padding: 0.3rem;
  background: var(--skx-frost-menu-bg);
  border: 1px solid var(--skx-frost-menu-line);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-banner);
  transform-origin: top left;
  animation: rs-dl-in 0.14s ease-out;
}
.rs-basket__note {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  padding: 0.5rem;
  font-size: 0.6rem;
  line-height: 1.5;
  color: var(--skx-gray-1);
}
.rs-basket__spin {
  flex: none;
  width: 0.9rem;
  height: 0.9rem;
}
.rs-basket__list {
  max-height: 14rem;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}
.rs-basket__item {
  display: block;
  width: 100%;
  padding: 0.5rem;
  font-family: inherit;
  font-size: 0.65rem;
  line-height: 1.4;
  color: var(--skx-ink);
  text-align: left;
  background: none;
  border: none;
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.rs-basket__item:hover,
.rs-basket__item:focus-visible {
  background: var(--skx-frost-bg-hover);
  outline: none;
}
@media (prefers-reduced-motion: reduce) {
  .rs-basket__menu {
    animation: none;
  }
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 11: (8-2 — 하지 않음) 확인하고 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend/pages/papers/index.vue frontend/components/BookChat.vue frontend/composables/useResearchWork.ts
```

Expected: 실패 0, `Test Files` 8-1 뒤 + 1, `Tests` 8-1 뒤 + 4(2026-10-13 개정에서 다시 재지 않음 — 보류) · `0` · `      2 Duplicated imports "MetaPart"` · `└  ✨ Build complete!` · 빈 출력.

손 확인(운영 배포 뒤 Z6 — 구현 중에는 항목을 누르지 않는다): [담기 ▾] → 이어간 연구 목록 → 고르면 '「…」 연구에 담았습니다' 토스트 → 그 연구의 `?s=reading` 에 그 자료가 담음으로(들어온 경로 '사용자'). 이어간 연구가 없는 새 시크릿 창은 '보고서 끝 [이 연구 이어가기] 뒤에 담을 수 있습니다'. 키보드 ↓·↑·Esc·초점 복귀.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/addToWork.ts && git add frontend/tests/unit/addToWork.test.ts && git add frontend/components/research/AddToWorkMenu.vue && git add frontend/composables/useResearchWorks.ts && git add frontend/pages/index.vue && git add frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 소장자료 결과의 'SKOVIX 추천 1권' 패널 아래 [DeepResearch로 이어서 조사하기] 옆에 [담기 ▾]를 단다(D17 — round08 이 남긴 자리, 자르는 순서 1). 메뉴를 처음 열 때 이 브라우저의 이어간 연구를 한 번 읽고, 고르면 추천 1권을 PUT reading {state: in} 으로 그 연구의 목록에 담는다(행이 없으면 서버가 origin user 로 만든다). 이어간 연구가 없으면 '보고서 끝 [이 연구 이어가기] 뒤에 담을 수 있습니다'. 담은 뒤 토스트와 함께 사이드바 기록을 한 번 다시 읽는다. 메뉴는 내려받기 메뉴와 같은 키보드 관례(방향키·Esc·바깥 클릭·초점 복귀), 모양은 다크 토큰(+ 메뉴와 같은 짙은 면)"
```

Expected: `A` 셋·`M` 셋, 커밋 1개.

---

### Task P9: (조건부 — 06e 가 먼저 dev 에 머지됐을 때만) 딥리드 패널 열림 때 LNB 접기(원 N8)

결정 8 · 06e 계획 정함 30(원 계획 N8 과 같은 계약 문장). **조건:** P8 8-1(또는 P7 — 8-1 을 잘랐으면) 뒤, Z4 전에 Step 1 의 06e 머지 수가 `1` 이상이면 한다. `0` 이면 **건너뛴다** — 06e 가 늦게 머지하며 06e 계획의 R6 이 같은 두 곳을 단다. 건너뛴 사실을 완료노트(Z3)에 적는다.

**알아 둘 것:**
- 계약: 06e 는 ReadingStep·ProposalStep 의 emit `panel: [open: boolean]` 과 `[id].vue` 의 리스너 `@panel="workPanelOpen = $event"`, script 의 `const workPanelOpen = ref(false);`(`const { pdf, closePdf } = pdfOpener;` 뒤)까지 단다. 06d 는 리스너·새 ref·`watch(step)` 를 넣지 않고 `workPanelOpen` 을 읽기만 해 `[id].vue` 머리(`<div class="skx-app">` 와 `<AppSidebar` 두 줄 — round08 뒤에도 그대로, 앞부분·이 계획의 어떤 Task 도 고치지 않았다) 두 곳만 단다.
- round08 뒤의 사이드바: `AppSidebar` 의 `collapsed` prop 은 접힌 모양(`isCollapsed = !open || !!props.collapsed`)만 정하고, **폴링은 접혀 있어도 돈다**(round08 — 접힌 띠의 현미경 점이 낡지 않게). 원 N8 '알아 둘 것' 의 '접힌 동안 폴링을 쉬게 한다' 는 round08 뒤 맞지 않는다 — 고칠 것은 없다. 접힌 모양은 `.skx-app.is-lnb-collapsed .skx-lnb`(`style_skovix.css:1297-1326` — `a084ff3`)가 그린다 — 검색 화면(`pages/papers/index.vue:2-4`)과 같은 모양.
- 06e 를 받는 merge 에서 충돌이 나면 원 N8 Step 2 의 규칙(06e 블록은 dev 쪽, 06d 가 고친 줄은 이 브랜치 쪽, import 는 두 쪽 모두)을 따르고, `research.css`·`AppSidebar.vue`·`pages/index.vue`·`SearchPlusMenu.vue`·`useResearch.ts`·`ResearchHeader.vue` 가 충돌하면 06e 가 경계를 넘은 것이라 멈추고 06e 세션에 알린다('1-7').
- 2026-10-13 확인: 이 계획을 모두 얹은 사본에 06e 의 `const workPanelOpen = ref(false);` 를 흉내 내어 Step 4 의 두 곳을 단 typecheck `error TS` 0. 같은 사본에 06e 브랜치(`598c561` — 아직 `workPanelOpen` 을 달지 않은 때)를 시험 머지하면 `pages/research/[id].vue` 는 자동으로 합쳐지고 충돌은 `pages/papers/[id].vue`(06e ↔ round08 — 06e 의 dev 받기 몫) 하나였다. 06e 의 새 export 이름과 이 계획의 새 이름은 겹치지 않는다.

**Files:**
- Modify: `frontend/pages/research/[id].vue`(머리 두 곳 — merge dev 뒤)

기준선: P8 8-1(또는 P7) 뒤 수.

- [ ] **Step 1: 조건을 본다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git status --short
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git log --oneline --merges dev | grep -c "feat/round06e-assistant-auto-report"
```

Expected: 빈 출력 · 출력 없음 또는 한 줄 · `1` 이상이면 Step 2, `0` 이면 여기서 멈추고 체크박스 옆에 '건너뜀 — 06e 가 아직 dev 에 없다(06e 가 단다)' 로 적는다.

- [ ] **Step 2: dev 를 받는다(06e)**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git merge dev -m "Merge dev into feat/round06d-research-progress-screen — 06e 연구 어시스턴트 받기"`

Expected: `Merge made by the 'ort' strategy.` 와 06e 의 파일 목록(P1 Step 3 에서 이미 받았으면 `Already up to date.` — Step 3 로). 충돌이 나면 위 '알아 둘 것' 셋째 줄대로 풀고 `grep -cE '^(<<<<<<<|=======|>>>>>>>)' <파일>` 이 `0` 인 것을 본 뒤 그 파일만 `git add` 해 `git commit --no-edit --cleanup=strip`.

- [ ] **Step 3: 받은 뒤 그대로 도는지 본다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi prepare 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -n "workPanelOpen" "frontend/pages/research/[id].vue"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "is-lnb-collapsed" "frontend/pages/research/[id].vue"
```

Expected: `Types generated …` · 실패 0 — 나온 수를 이 Task 의 새 '앞 수' 로(앞 수 + 06e 가 더한 프론트 테스트) · `0` · `      2 Duplicated imports "MetaPart"`(다른 이름이 더 나오면 06e 와 06d·round08 이 같은 이름을 내보낸다 — 이름·파일을 06e 세션에 알리고 멈춘다) · `workPanelOpen` 세 줄(리스너 둘·ref 하나 — 06e 가 다른 이름을 썼으면 Step 4 에 그 이름을, 0 줄이면 계약이 어긋났다 — 06d 가 대신 달지 않고 멈춘다) · `0`(`1` 이상이면 06e 가 이미 달았다 — Step 4·5 를 건너뛰고 완료노트에 적는다).

- [ ] **Step 4: 머리 두 곳만 단다**

`frontend/pages/research/[id].vue` — old:

```vue
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
```

new:

```vue
  <div :class="['skx-app', workPanelOpen && 'is-lnb-collapsed']">
    <AppSidebar
      :collapsed="workPanelOpen"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
```

새 ref·리스너·`watch(step)` 는 넣지 않는다(06e 정함 30).

- [ ] **Step 5: 확인하고 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "frontend/pages/research/[id].vue" && git status --short && git commit -m "[Feat] round06d — 딥리드 패널이 열리면 연구 화면의 사이드바를 접는다(06e 패널 연결 — 06e 가 먼저 dev 에 들어와 늦게 머지하는 06d 가 단다, 06e 정함 30). 06e 가 단 workPanelOpen 을 읽기만 해 루트 is-lnb-collapsed 와 AppSidebar 의 collapsed 두 곳에 잇는다 — 검색 화면(DeepRead 패널)과 같은 모양이고 리스너·새 상태는 더하지 않는다"
```

Expected: `frontend/pages/research/[id].vue | 3 ++-`·`1 file changed, 2 insertions(+), 1 deletion(-)` · Step 3 과 같은 수(+0) · `0` · `└  ✨ Build complete!` · `M  frontend/pages/research/[id].vue`, 커밋 1개(Step 2 의 머지 커밋과 합쳐 2개).

---

## 3. 마무리

06d 전체(앞부분 D1~D7·L1~L5 + 둘째 부분 P1~P9 — P8 은 8-1 만, 8-2 [담기]는 보류)를 한 번에 — 전체 회귀·경계·영역별 정적 리뷰(Z1), 06c 판정 연계(Z2), 문서(Z3), `dev` 머지(Z4 — 사용자 승인, 핑크와의 순서 확인), 운영 배포(Z5 — 사용자, round08 운영 반영 뒤 따로, 10/17~18), 운영 처음부터 끝까지 1회(Z6 — 사용자), 배포 기록(Z7). 원 계획 Z1~Z7 을 이 범위에 맞게 고친 것이다 — 아래에 적지 않은 세부(리뷰어 공통 머리의 ①~⑧ 등)는 원 계획의 같은 Step 이 정본이다.

### Task Z1: 전체 회귀·경계 확인·영역별 정적 리뷰·반영

**왜:** dev 에 넣기 전에 한 번에 회귀를 보고, 이 줄이 손대지 말아야 할 곳(백엔드·06e 파일·round08 파일·`ReportView`·`researchDraft`)이 그대로인지 보고, 영역별 정적 리뷰(`.claude/agents/code-reviewer.md`)로 위험(한 이름 한 파일·선택 필드·reduced-motion·토큰·접근성·쓰는 요청이 그리기 경로에 없음·06c 계약·시작 판단 한 곳)을 본다. 리뷰 반영도 이 Task 안에서 끝내고 '리뷰를 마친 커밋'을 적는다.

**Files:** 리뷰 발견을 고치는 파일(발견에 따라 — 판단을 바꾸면 순수 함수의 실패 테스트부터). 저장소 밖 `C:/Users/LANDSOFT/round06d-eval/review/`(리뷰어에게 줄 diff — 저장소에 넣지 않는다).

**알아 둘 것:** `BASE=$(git merge-base HEAD dev)` 는 마지막으로 받은 dev(P1·P9 이 받은 커밋)다 — `git diff $BASE HEAD` 는 06d 자신의 변경만 보인다. code-reviewer 는 읽기 전용이라 diff 를 파일로 떠서 준다. 반영 커밋은 `[Fix] round06d — …`(Co-Authored-By 없음), 거절한 발견은 까닭을 완료노트 §3 에.

- [ ] **Step 1: 전체 회귀**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchLayout.test.ts tests/unit/queueLine.test.ts tests/unit/researchEvents.test.ts tests/unit/synthCard.test.ts tests/unit/restorePosition.test.ts tests/unit/evidenceLedger.test.ts tests/unit/researchDraft.test.ts tests/unit/workPhase.test.ts tests/unit/researchProgress.test.ts tests/unit/planSlots.test.ts tests/unit/researchFollow.test.ts tests/unit/useSectionFollow.test.ts tests/unit/themeResearch.test.ts tests/unit/sidebarResearch.test.ts tests/unit/sidebarGroups.test.ts tests/unit/researchStart.test.ts tests/unit/researchExamples.test.ts tests/unit/researchMode.test.ts tests/unit/landingStart.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchDraft.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | grep -o 'Duplicated imports "[A-Za-z]*"' | sort | uniq -c
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors
```

Expected:
- typecheck `0` · 한 이름 경고 `      2 Duplicated imports "MetaPart"`(round08 기준선 그대로 — 06d 가 더한 이름이 겹치지 않는다)
- vitest 전체 실패 0 — `Tests` 는 마지막으로 끝낸 프론트 Task(P9 를 했으면 P9, 아니면 P8 8-1 — 자르면 P7)의 수와 같다(이 Step 은 테스트를 더하지 않는다. 사본 `64 / 1272`)
- 06d 묶음 열아홉 파일(앞부분이 고치거나 기대는 열둘 + 둘째 부분 일곱 — 8-1 을 잘랐으면 `landingStart` 를 빼고 열여덟. 8-2 [담기]는 보류라 `addToWork` 가 없다) — 실패 0, 나온 수를 적어 둔다(완료노트 §4)
- `researchDraft.test.ts` — `Tests  23 passed (23)`(spec §12-7 '기존 테스트 그대로')
- build 의 한 이름 경고 `MetaPart` 두 줄, 마지막 줄 `└  ✨ Build complete!`
- 백엔드 `5 failed, N passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 원 계획 기준선과 같은 여섯 줄(`test_build_manifest` 2·`test_loaders` 3·`test_book_chat` 수집). N 은 받은 dev 의 수(06d 는 `app/` 을 바꾸지 않는다). 그 밖의 실패가 있으면 06d 가 아니라 받은 dev 의 것 — 멈추고 사용자와 그 줄의 세션에 알린다

- [ ] **Step 2: 경계 — 고친 파일·고치지 않을 파일·06e 블록·장부 블록·색값·표기·트레일러**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
BASE=$(git merge-base HEAD dev); echo "$BASE"
git diff --name-only $BASE HEAD -- app frontend scripts infra | LC_ALL=C sort
git diff --stat $BASE HEAD -- app docker-compose.yml docker-compose.dev.yml infra frontend/package.json frontend/package-lock.json frontend/components/work/WorkStepper.vue frontend/components/research/PlanCard.vue frontend/components/research/CitationChip.vue frontend/components/research/ReportView.vue frontend/components/BookChat.vue frontend/utils/researchDraft.ts frontend/tests/unit/researchDraft.test.ts frontend/utils/workPhase.ts frontend/utils/researchErrors.ts frontend/composables/useResearchWork.ts frontend/types/work.ts frontend/utils/citations.ts frontend/pages/search-classic.vue frontend/pages/papers/index.vue frontend/utils/sidebarGroups.ts frontend/assets/css/style_skovix.css frontend/assets/css/detail.css frontend/utils/resultCard.ts frontend/utils/detailView.ts
diff <(git show $BASE:"frontend/pages/research/[id].vue" | sed -n '/연구 어시스턴트 단계(?s=)/,/<div v-else class="rs-body"/p') <(sed -n '/연구 어시스턴트 단계(?s=)/,/<div v-else class="rs-body"/p' "frontend/pages/research/[id].vue") && echo "단계 본문 그대로"
git diff $BASE HEAD -- frontend/assets/css/research.css frontend/assets/css/work.css frontend/components frontend/pages | grep '^+' | grep -cE "#[0-9a-fA-F]{3,6}\b|rgba?\(|hsla?\("
git diff $BASE HEAD -- frontend/assets/css/research.css frontend/assets/css/work.css frontend/components | grep '^+' | grep -c "@keyframes"
git diff $BASE HEAD -- frontend | grep '^+' | grep '딥리서치' | grep -cvE '^\+\s*(//|<!--|/\*|\*)'
git diff $BASE HEAD -- frontend | grep '^+' | grep -cE "wk-rbar|--wk-bar-thick|reportBar"
git log $BASE..HEAD --format=%B | grep -ciE "Co-Authored-By|Generated with Claude Code"
git status --short
```

Expected:
- `BASE` — P1(또는 P9)이 받은 dev 커밋
- 고친 파일 목록 — 정확히 아래 마흔아홉(2026-10-13 사본 `a084ff3` 에 P2~P8 8-1 을 얹어 `git diff --name-only $(git merge-base HEAD dev) HEAD` 로 실측. 8-1 을 잘랐으면 `tests/unit/landingStart.test.ts`·`utils/landingStart.ts` 둘이 없고, 보류한 8-2 [담기]를 하게 되면 `components/research/AddToWorkMenu.vue`·`tests/unit/addToWork.test.ts`·`utils/addToWork.ts` 셋이 는다). 리뷰 반영으로 더한 파일이 있으면 그 파일과 까닭을 완료노트 §3 에

```text
frontend/assets/css/research.css
frontend/assets/css/work.css
frontend/components/AppSidebar.vue
frontend/components/research/ProgressPanel.vue
frontend/components/research/ReportPrint.vue
frontend/components/research/ReportSkeleton.vue
frontend/components/research/ResearchExampleCards.vue
frontend/components/research/ResearchHeader.vue
frontend/components/research/ResearchModePicker.vue
frontend/components/research/ResearchProgressBar.vue
frontend/components/research/SearchPlusMenu.vue
frontend/components/research/SynthProgressCard.vue
frontend/components/work/EvidenceLedger.vue
frontend/composables/useResearch.ts
frontend/composables/useResearchWorks.ts
frontend/composables/useRestorePosition.ts
frontend/composables/useSectionFollow.ts
frontend/pages/index.vue
frontend/pages/research/[id].vue
frontend/tests/unit/evidenceLedger.test.ts
frontend/tests/unit/helpers/cssRules.ts
frontend/tests/unit/landingStart.test.ts
frontend/tests/unit/planSlots.test.ts
frontend/tests/unit/queueLine.test.ts
frontend/tests/unit/researchEvents.test.ts
frontend/tests/unit/researchExamples.test.ts
frontend/tests/unit/researchFollow.test.ts
frontend/tests/unit/researchLayout.test.ts
frontend/tests/unit/researchMode.test.ts
frontend/tests/unit/researchProgress.test.ts
frontend/tests/unit/researchStart.test.ts
frontend/tests/unit/restorePosition.test.ts
frontend/tests/unit/sidebarResearch.test.ts
frontend/tests/unit/themeResearch.test.ts
frontend/tests/unit/useSectionFollow.test.ts
frontend/types/research.ts
frontend/utils/evidenceLedger.ts
frontend/utils/landingStart.ts
frontend/utils/planSlots.ts
frontend/utils/researchEvents.ts
frontend/utils/researchExamples.ts
frontend/utils/researchFollow.ts
frontend/utils/researchLayout.ts
frontend/utils/researchMode.ts
frontend/utils/researchProgress.ts
frontend/utils/researchStart.ts
frontend/utils/restorePosition.ts
frontend/utils/sidebarResearch.ts
frontend/utils/synthCard.ts
```

- 고치지 않을 파일 `diff --stat` — 빈 출력(백엔드·compose·인프라·패키지·06e 파일·06c PlanCard·CitationChip·ReportView·researchDraft·search-classic·논문 화면·round08 파일)
- `단계 본문 그대로`(06e 블록 — 원 계획 Z1 Step 2 와 같은 범위)
- 더한 줄의 색값 `0`
- 더한 `@keyframes` — `1`(앞부분 L5 의 `wk-review` — 둘째 부분은 새 keyframes 가 없다. 2026-10-13 사본에서 둘째 부분만 세면 `0`). 다르면 새 keyframes 마다 reduced-motion 규칙을 리뷰 A·C 에 함께 보인다
- 주석이 아닌 더한 줄의 '딥리서치' `0`(화면 글은 `DEEP_RESEARCH`)
- `wk-rbar|--wk-bar-thick|reportBar` `0`(06e 몫)
- 트레일러 `0`(종료 코드 1 이 정상)
- `git status --short` 빈 출력
- 원 계획 Z1 Step 2 의 `work.css` 장부 블록 hunk 검사(`S1 E1 S2 E2` 와 awk — '장부 블록 밖:' 줄이 없어야 한다)를 그대로 돌린다

- [ ] **Step 3: 로컬 화면을 운영 API 에 붙여 GET 으로만 본다(사용자와 함께 — P2 의 인쇄 판단·P4 의 한 줄 확인 포함)**

운영에 쓰지 않는다 — 누르면 쓰는 버튼(승인·취소·입력창 한 줄의 [정말 취소]·[이 연구 이어가기]·DeepResearch 모드에서 보내기·[같은 질문으로 다시 시작])은 누르지 않는다(입력창 한 줄의 [취소] 첫 누름은 '정말 취소' 로 바꾸기만 한다 — [그대로 두기]로 되돌린다). 포트는 다른 세션과 겹치지 않게 3016.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && NUXT_DEV_API_TARGET=https://skovix.landsoft.co.kr/api npx nuxi dev --port 3016
```

(백그라운드로 띄우고 다 보면 끈다.) 본다:
- `http://localhost:3016/` — 사이드바 [+ 연구 시작하기]: 끝나지 않은 연구가 있든 없든 메인 논문 패널 + DeepResearch 칩·입력창 초점·탐색 방식 두 칸(`정밀하게`)(최종 결정 A — 그 연구 화면으로 가지 않는다). 이 브라우저에 끝나지 않은 연구가 없으면 한 줄 없음, 있으면 칩 줄 아래 '진행 중인 DeepResearch n건 · 보기 취소'(승인 대기만이면 '승인 대기 중인 …') → [보기] 가 그 연구로 → 돌아와 [취소] 한 번 → '정말 취소'·'그대로 두기' → [그대로 두기]. 예시 연구가 운영에 지정돼 있으면 칩 아래 카드, 없으면 없음. 칩 × 로 끄면 두 칸·한 줄·카드가 사라진다. 모드를 켤 때(그리고 한 줄이 설 때) 입력 상자가 위로 움직이는 정도(세로 가운데 정렬)를 사용자에게 보인다. **예시 카드 배치(P5 품질 리뷰 — 사용자 결정):** 카드 섹션(패널 gap 2rem + 제목·안내 + 카드 — 약 12rem)이 서거나 걷힐 때 로고·전환·입력창이 그 절반만큼 움직인다 — 모드 켜기/끄기(칩 ×), 그리고 DeepResearch 를 켠 채 '자료 검색' 탭을 누를 때(`selectTab`→`dropDeepResearch` 로 카드가 걷혀 방금 누른 전환이 포인터 아래에서 내려간다 — round08 의 유령 링크·`.skx-chip` min-height 가 지키던 '갈래를 바꿔도 전환·입력창이 움직이지 않는다' 와 어긋난다). 이것을 보이고 그대로 둘지·바꿀지 사용자가 정한다. 고칠 때의 갈래: ① 카드를 가운데 정렬 흐름 밖(절대 위치)으로 — 입력창은 그대로지만 보통 창 높이에서는 카드가 화면 아래로 넘쳐 흐름 밖이라 `.skx-app`(min-height 100vh) 바로 아래 푸터(`app.vue` `.skx-footer`)와 겹친다(푸터 처리가 함께 필요) ② DeepResearch 모드의 랜딩만 위 기준 정렬 — 모드를 켜고 끌 때 한 번 움직이는 것은 같다 ③ 카드를 더 낮게(한 줄 카드 등) — 움직임만 준다 ④ 그대로. 비동기 이동은 고쳤다(P5 리뷰 반영 — 카드는 목록·범위를 다 받은 뒤 한 번에 서고, 랜딩이 뜰 때 미리 읽어 두어 모드를 켤 때 함께 선다. 다만 다른 화면에서 사이드바 [+ 연구 시작하기]로 처음 랜딩에 오면 첫 응답 뒤 한 번 선다). 끝나지 않은 연구가 없는 브라우저면 한 줄은 Z6 에서 본다.
- 자료 검색 하나 → 결과의 추천 패널 아래 `+ DeepResearch로 이어서 조사하기`(8-1 을 했으면) → 누르면 메인 논문 패널에 그 검색어 + DeepResearch 모드(보내지 않는다), 뒤로 가기로 결과에 돌아온다. [담기 ▾]는 없다(8-2 보류).
- `http://localhost:3016/papers` 에서 검색 하나 → 결과의 [DeepResearch로 이어서 조사하기] → 검색바에 칩·탐색 방식, (끝나지 않은 연구가 있으면) 검색바 아래 오른쪽에 같은 한 줄 — 결과 틀·오류 줄과 겹치는 모양을 사용자에게 보인다. **탐색 방식 자리(P6 품질 리뷰 — 사용자 확인):** 검색바 안쪽 폭이 34rem 보다 넓으면 칩 옆, 34rem 이하(LNB 가 열린 1100px 쯤 아래 노트북·휴대폰)면 입력칸이 사라지지 않게 바 아래 왼쪽에 + 메뉴 팝오버와 같은 면으로 내려 서고 한 줄·오류 줄은 그 아래로 간다 — 내린 줄이 결과 틀 위쪽에 약 20px 겹치는 모양을 보인다(375px·LNB 연 1024px). 메인 입력 상자에서는 두 칸을 번갈아 눌러 묶음 자리·상자 높이가 그대로이고, 톱니 [라이트](핑크)에서 고른 칸이 테두리로 구별되는지 본다.
- `http://localhost:3016/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383`(06b 운영 확인 잡 — completed·이어간 연구) — 큰 진행 막대 없음, 넓은 화면 2단, 머리 'DeepResearch' 청록 칩·흰 질문·상태 배지(방식 표시 없음 — 06c 전 잡), **보고서는 읽기용 짙은 유리**(옆 카드보다 한 단계 짙은 초록 면에 거의 흰 글자 — 결과 화면의 읽는 칸과 같은 톤, 최종 결정 C). 옆 칸 두 카드 머리의 청록 앞 막대. **인쇄 판단을 사용자에게 보인다**(P2 '알아 둘 것'): [PDF로 저장] 미리보기는 흰 종이·짙은 글자(인쇄 전용 문서만 `.skx-reading`), Ctrl+P 미리보기는 보고서가 짙은 면 그대로 — 인쇄 전용 문서도 짙게 두자고 하면 P2 의 그 한 줄을 Fix 커밋(Step 1·2 다시). 사이드바 톱니 [라이트](핑크)로 바꿔 같은 화면이 흰 면·짙은 글자로 깨지지 않는지 본다. 같은 잡의 `?s=proposal`(이어간 연구 단계 화면 — `.rs-card` 공용 가장자리를 06b·06e 카드도 받는다)에서 카드 가장자리가 어색하지 않다.
- 사이드바 DeepResearch 묶음 — 기록이 6건 넘는 브라우저면 구분선 아래 '이전 연구 [n] ⌄'. 진행 중 줄이 있으면 배지 옆 단계 글(숫자 없음), Network 에 사이드바의 `/api/research/<id>` 가 없다(최종 결정 D).
- 375px — 가로 스크롤 없음, 탐색 방식 설명이 숨는다, 논문 결과 검색바의 입력칸이 남는다(탐색 방식은 바 아래).
- 콘솔 오류 없음.

Expected: 위와 같다. 깨지는 화면이 있으면 그 Task 로 돌아가 고친 뒤 Step 1·2 를 다시.

- [ ] **Step 4: 영역별 정적 리뷰 — code-reviewer 다섯을 병렬로**

```bash
mkdir -p C:/Users/LANDSOFT/round06d-eval/review
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
BASE=$(git merge-base HEAD dev)
git diff $BASE HEAD -- frontend/utils/researchLayout.ts frontend/utils/researchProgress.ts frontend/utils/synthCard.ts frontend/components/research/ResearchProgressBar.vue frontend/components/research/SynthProgressCard.vue frontend/components/research/ReportPrint.vue frontend/utils/restorePosition.ts frontend/composables/useRestorePosition.ts "frontend/pages/research/[id].vue" frontend/assets/css/research.css frontend/tests/unit/themeResearch.test.ts frontend/tests/unit/helpers/cssRules.ts > C:/Users/LANDSOFT/round06d-eval/review/a-layout-bar-style.diff
git diff $BASE HEAD -- frontend/utils/researchFollow.ts frontend/composables/useSectionFollow.ts "frontend/pages/research/[id].vue" > C:/Users/LANDSOFT/round06d-eval/review/b-follow.diff
git diff $BASE HEAD -- frontend/utils/planSlots.ts frontend/components/research/ReportSkeleton.vue frontend/utils/researchEvents.ts frontend/types/research.ts frontend/components/research/ProgressPanel.vue frontend/utils/evidenceLedger.ts frontend/components/work/EvidenceLedger.vue frontend/assets/css/work.css "frontend/pages/research/[id].vue" > C:/Users/LANDSOFT/round06d-eval/review/c-explore.diff
git diff $BASE HEAD -- frontend/components/AppSidebar.vue frontend/utils/sidebarResearch.ts frontend/utils/researchStart.ts frontend/composables/useResearch.ts frontend/pages/index.vue frontend/utils/researchExamples.ts frontend/composables/useResearchWorks.ts frontend/components/research/ResearchExampleCards.vue frontend/utils/researchMode.ts frontend/components/research/ResearchModePicker.vue frontend/components/research/SearchPlusMenu.vue frontend/components/research/ResearchHeader.vue frontend/utils/landingStart.ts "frontend/pages/research/[id].vue" frontend/assets/css/research.css > C:/Users/LANDSOFT/round06d-eval/review/d-entry.diff
git diff $BASE HEAD -- frontend/tests > C:/Users/LANDSOFT/round06d-eval/review/e-tests.diff
wc -l C:/Users/LANDSOFT/round06d-eval/review/*.diff
```

Expected: 다섯 파일 모두 0 줄이 아니다.

`.claude/agents/code-reviewer.md`(subagent_type `code-reviewer`) 다섯을 **한 번에 병렬로** 띄운다. 공통 머리는 원 계획 Z1 Step 4 의 글에 다음 두 문장을 더해 쓴다: "이 줄의 둘째 부분 결정은 C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/docs/superpowers/plans/ 의 06d 둘째 부분 계획(정함 20~27 — 2026-10-12~13 사용자 결정과 2026-10-13 최종 결정 A~G 가 원 계획 정함 13~16·18 을 갈음)이다. round08(UI 다크 테마·테마 구조 — 핑크)의 토큰·읽기용 짙은 유리(`--skx-read-*`)·`DEEP_RESEARCH` 표기·`sidebarGroups.LIVE_STATUSES` 를 따르고 round08 파일(`style_skovix.css`·`sidebarGroups.ts`·`detail.css`·`resultCard.ts`·`theme.ts`·`helpers/themeCss.ts`)은 고치지 않는다. 화면에는 `.skx-reading` 을 쓰지 않는다(흰 종이에 찍는 인쇄 전용 문서만)." (Z3 가 둘째 부분 계획을 브랜치의 `docs/superpowers/plans/2026-10-13-round06d-part2-entry-style.md` 로 넣은 뒤면 그 경로를 쓴다.)

영역 줄:
- **[A 2단·큰 진행 막대·오프셋·다크 스타일]** diff `a-layout-bar-style.diff` — 원 계획 Z1 Step 4 의 A 줄 그대로에 더해: 글자색에 `--skx-white` 가 남지 않았고 산호 바탕 위 글자가 `--skx-on-accent` 인지, 막대 빛 흐름이 `--skx-frost-line` 인지(두 테마 모두 밝은 띠), 카드·머리·막대의 테두리가 막대 높이 오프셋(`--rs-bar-h` — border-box)을 바꾸지 않는지, `.rs-card.rs-report` 의 읽기용 짙은 유리가 `ReportView`·`ReportSkeleton` 둘의 뿌리에만 걸리고 그 안의 인용 팝오버·[다운로드]·[이 연구 이어가기] 카드가 `--skx-read-*` 글 톤으로 읽히는지(불투명 면 위에 깐 바탕이 움직이는 배경 위에서 대비를 지키는지), 화면에 `.skx-reading` 이 없고 인쇄 전용 문서(`ReportPrint`)만 붙는지·화면 인쇄 `print-color-adjust: exact`, 핑크 테마(`html[data-theme="pink"]`)에서 바꾼 토큰이 같은 뜻인지, 가드 테스트가 주석·url 을 빼고 세는지·`:root` 토큰을 `helpers/themeCss.ts` 의 `rootDecls` 로 읽는지.
- **[B 따라가기]** diff `b-follow.diff` — 원 계획 Z1 Step 4 의 B 줄 그대로.
- **[C 탐색 중 움직임]** diff `c-explore.diff` — 원 계획 Z1 Step 4 의 C 줄 그대로("이렇게 이해했어요" 는 P7).
- **[D 입구]** diff `d-entry.diff` — 특히: [+ 연구 시작하기]가 분기 없이 늘 새 연구인지(최종 결정 A — `AppSidebar.vue` 의 `startDeepResearch` 가 round08 그대로), 입력창 한 줄의 판단이 `researchStart.ts`·`useResearchStarter` 한 곳이고 줄이 `SearchPlusMenu.vue` 안 DeepResearch 모드일 때만인지(진행 중 = `LIVE_STATUSES` 와 같은 상태, 가장 최근 = `entryTime`, 진행 중이 승인 대기보다 먼저, 'n건' 과 [보기]·[취소] 대상, 막지 않음), [취소]가 기존 취소 API 뒤 기록을 다시 읽는지·두 번 누르기(첫 누름 arm·400ms 안 무시·줄의 연구가 바뀌거나 모드를 끄면 확인 풀기)·실패 문구·`NuxtLink`/버튼의 접근성 이름(`role=group`·`aria-labelledby`), 결과 검색바에서 뜨는 자리(+ 메뉴·슬래시 목록·오류 줄과 겹침), 사이드바 단계 글이 진행 중 줄에만·기록의 상태만으로(잡 GET 없음 — 최종 결정 D)·완료 줄에 없음, '이전 연구 [n]' 의 aria-label·칩·⌄·reduced-motion, 예시 카드가 `useState` 로 한 번만·브라우저 ID 헤더가 있는 마운트 뒤에 읽고 없으면 그리지 않는지·실행 시각 KST·범위 `scopeLine`·읽기 전용, 탐색 방식(원 Z1 Step 4 의 D 줄 '탐색 방식' 부분 — `/research` 홈 줄은 빼고), 소장자료 [DeepResearch로 이어서 조사하기]가 `resultQuery` 를 싣고 시작하지 않으며 `?start=`·`?draft=` 를 처리 뒤 지우는지·두 감시의 순서, 쓰는 요청([정말 취소]의 POST)이 클릭 처리기에서만인지, 화면 글에 새 '딥리서치' 가 없는지(`DEEP_RESEARCH`).
- **[E 테스트]** diff `e-tests.diff` — 원 계획 Z1 Step 4 의 E 줄에서 새 파일 목록을 `researchProgress·planSlots·researchFollow·useSectionFollow·themeResearch·sidebarResearch·researchStart·researchExamples·researchMode`(+ 고친 `landingStart`·`helpers/cssRules`)로 바꿔 쓴다. 특히: 기대값을 06e 함수(`scopeLine`·`stepForPhase`)의 출력으로 만들었는지, 사이드바 단계 글 테스트가 기록 응답 모양(`HistoryResearchStatus`)만 쓰는지, 입력창 한 줄 테스트가 두 번 누르기의 시간 경계(399·400ms)를 재는지, 대역(`helpers/fakeHistory`·`memoryStorage`)을 새로 만들지 않았는지, `helpers/cssRules.ts` 가 옮긴 함수와 글자 그대로인지.

Expected: 리뷰어마다 요약 + 결함 목록(없으면 "없음"). 영역·severity 별로 한 표로 모은다(완료노트 §3).

- [ ] **Step 5: 발견을 반영하고 리뷰를 마친 커밋을 적는다**

원 계획 Z1 Step 5 그대로 — high·medium 은 모두 고치고 low 는 판단해 까닭을 적는다, 계획의 결정(정함 1~27)과 다른 제안은 사용자에게 묻는다, 판단을 바꾸는 수정은 실패 테스트부터, 다 고친 뒤 Step 1·2 를 다시, 고친 것만 해당 영역 리뷰어에게 다시(최대 3회). 그 뒤:

Run: `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d rev-parse --short HEAD`

Expected: 커밋 해시 한 줄 — '리뷰를 마친 커밋'(완료노트 머리·§3, Z4 의 승인 요청).

---

### Task Z2: 06c 판정 연계 — 랜딩 논문 예시 셋을 판정 결과로 다시 본다

원 계획 Task Z2 그대로다(Step 1~4 — 06c 완료노트 §5-4·§5-5 의 질문별 값으로 판단, **어느 갈래로 볼지 먼저 사용자에게 묻는다** — 화면 기본 선택은 '정밀하게' = 갈래 1, 바꿀 문장은 사용자가 정한다). round08 뒤 자리만 바뀌었다: `SUGGESTIONS.paper`(`pages/index.vue:405-409`)와 그 위 주석 `// 보고서 정밀도가 높았던 질문(노인 우울 95%·다문화 아동 75~100%·공공도서관 82~86%)을 그 문장 그대로 쓴다`(`:398`)는 round08 이 옮기지 않은 글 그대로라 원 Z2 Step 4 의 old 가 맞는다. 예시 칩은 지금 '입력창에만 채운다'(round04c `2d8320d` — round08 이 유지)라 바꾼 문장도 누르면 채우기만 한다.

---

### Task Z3: 문서 — 둘째 부분 계획·완료노트(배포 전)·00_status·spec 맞춤

**왜:** D13(하위 라운드마다 완료노트), CLAUDE.md §3("문서와 코드가 어긋나면 코드가 실제이니 문서를 고친다"). 둘째 부분은 spec §12-3 입구(D26)를 사용자 결정으로 크게 바꿨다 — dev 머지 전에 spec 을 코드에 맞춘다.

**Files:**
- Create: `docs/superpowers/plans/2026-10-13-round06d-part2-entry-style.md`(이 계획서 — 원 계획 옆에 둔다)
- Create: `docs/roadmap/round06d-완료노트.md`
- Modify: `docs/roadmap/00_status.md`(round06 줄만)
- Modify: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`(머리 상태 줄·D22·D26 행·§12-1 표 06d 입구 행·§12-3 따라가기·절 자리·오프셋 행·입구 블록·§12-10 Q8 의 예시 노출 줄·§12-11 두 항목)
- Modify: `docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md`(원 계획 머리에 한 줄 — 둘째 부분은 새 계획이 갈음)

**알아 둘 것:** 기존 문서는 Edit 도구로(모두 CRLF). 아래 old 는 dev `bae4d75` 의 글 그대로다(2026-10-13 확인 — 각 old 가 한 번씩 맞는다). 06c·06e 의 기록이 같은 줄을 먼저 고쳤으면 지금 줄을 바탕으로 같은 구절만 넣는다. 날짜는 이 Task 를 하는 날.

- [ ] **Step 1: 둘째 부분 계획을 브랜치에 넣고 원 계획에 갈음 한 줄을 단다**

이 계획서를 `docs/superpowers/plans/2026-10-13-round06d-part2-entry-style.md` 로 복사한다. 원 계획 머리 — old:

```markdown
**Goal:** round06 세 줄 병렬(06c 질의 ∥ 06d 진행 화면·입구 ∥ 06e 연구 어시스턴트) 가운데 06d 줄
```

new:

```markdown
> **2026-10-13 개정:** Task D8·L6·N1~N9·Z1~Z7 은 `docs/superpowers/plans/2026-10-13-round06d-part2-entry-style.md`(06d 둘째 부분 — round08 뒤, 사용자 결정 2026-10-12~13: 별도 `/research` 홈 없음·시작은 메인 입력창 하나·예시 연구는 메인 DeepResearch 모드 카드·사이드바 단계 문구는 진행 중 줄에만·'이전 연구 [n]')이 갈음한다. 이 계획의 그 Task 들은 기록으로 남긴다.

**Goal:** round06 세 줄 병렬(06c 질의 ∥ 06d 진행 화면·입구 ∥ 06e 연구 어시스턴트) 가운데 06d 줄
```

- [ ] **Step 2: 완료노트를 쓴다(`docs/roadmap/round06d-완료노트.md`, 새 파일)**

원 계획 Z3 Step 1 의 틀(머리·한 줄 요약·§1 왜·§2 한 일·§3 리뷰·§4 검증·§5 배포 전·§6 결정·디자인 참조·§7 이월·§8 다음 진입점·상태)을 쓰되 이 부분에 맞게 다음을 바꾼다. 실측값(커밋·수·날짜)은 Z1·Z2 에서 적어 둔 값을 옮긴다 — 다 쓴 뒤 `grep -c '<[^>]*>' "docs/roadmap/round06d-완료노트.md"` 가 `0` 이다(꺾쇠 자리를 남기지 않는다).
- 머리 `plan:` 줄 — 원 계획(앞부분 Task 0·D1~D7·L1~L5)과 둘째 부분 계획(P1~P9·Z1~Z7, 정함 20~27·최종 결정 A~G) 둘을 적는다.
- 한 줄 요약의 입구 구절 — '입구는 별도 시작 페이지 없이 메인 입력창 하나다 — 사이드바 [+ 연구 시작하기]는 늘 새 연구, DeepResearch 모드가 켜진 입력창(+ 메뉴)에는 끝나지 않은 연구 한 줄 [보기]·[취소]와 예시 연구 카드·탐색 방식(폭넓게 · 정밀하게), 사이드바 진행 중 줄의 단계 글(숫자 없이)과 이전 연구 [n], 소장자료 결과 [DeepResearch로 이어서 조사하기]. 연구 화면은 round08 다크 테마에 맞추고 보고서·절 자리는 읽기용 짙은 유리.' (8-1 을 잘랐으면 소장자료 구절을 뺀다. [담기 ▾]는 보류라 적지 않는다.)
- §1 '왜 했나' 에 '입구 다시 정함(2026-10-12~13 사용자 결정·2026-10-13 최종 결정)' 한 항목 — 결정 1~8 과 그것을 고친 최종 결정 A~G 를 한 줄씩.
- §2 '한 일' 표 — 원 Z3 의 배치·큰 진행 막대·절 따라가기·탐색 중 절 자리·근거 수집 단계·검토 중 후보·06c 바인딩·06b 이월 행은 그대로, '입구'·'문구' 행은 지우고 다음 행을 넣는다: '다크 맞춤(D8)'(정함 24 의 ①~⑥), '입력창 한 줄·늘 새 연구'(정함 20), '사이드바'(정함 21·22), '예시 연구'(정함 23), '탐색 방식'(정함 19·26), '소장자료 결과'(정함 25 — 8-1 을 했는지, [담기]는 '보류(§7)'), 'LNB 접기'(P9 를 했는지).
- §4 검증 — Z1 Step 1 의 vitest 두 줄·06d 묶음 수·`researchDraft` 23·typecheck 0·한 이름 경고 MetaPart 둘(round08)·build·백엔드 줄.
- §6 결정 — 원 정함 1~12·17·19 를 그대로 옮기고, 13~16·18 은 '갈음 — 정함 21·23·25 / 없앰(결정 1·4·6)' 로 적고, 정함 20~27 을 이 계획 '1-4' 의 표 그대로 더한다. 조건부 줄: P8 8-1 했음/자름·8-2 [담기] 보류(사용자 답), P9 했음/건너뜀, 06c 판정 연계(Z2).
- 디자인 참조 — 원 Z3 의 문단에 더해: 'round08 다크 토큰 위에서 연구 화면을 맞췄다(정함 24). 보고서·절 자리는 결과 화면의 읽는 칸과 같은 읽기용 짙은 유리(--skx-read-*, 최종 결정 C) — 화면에 밝은 면(.skx-reading)은 없고 흰 종이에 찍는 인쇄 전용 문서만 그것을 쓴다(Z1 Step 3 에서 사용자에게 보인 인쇄 판단의 결과를 적는다). 두 테마(다크·핑크)에서 같은 뜻의 토큰만 썼다.'
- §7 이월 — 원 Z3 의 1~5 에 더해: ⑥ 예시 연구는 리허설(10/23~25)에서 `mark_example.py` 로 지정한 뒤 메인 DeepResearch 모드의 카드로 다시 본다 ⑦ round08 의 `MetaPart` 두 줄 경고(`utils/detailView.ts`·`utils/resultCard.ts`) — round08 몫 ⑧ 06e 의 '딥리서치 보고서 보기'(`[id].vue` 단계 본문) 글 — round08 표기 규칙과 어긋남, 06e 몫 ⑨ 서버 문구 두 곳('딥리서치') — 서버를 건드리는 라운드 ⑩ 자른 Task·건너뛴 P9 가 있으면 한 줄씩 ⑪ 소장자료 결과 [담기 ▾](원 N6 — P8 8-2) — 보류, 사용자 답 대기(계획 글은 둘째 부분 계획 P8 Step 7~11) ⑫ 화면 인쇄(Ctrl+P)는 짙은 면을 그대로 찍는다 — 흰 종이 인쇄는 [PDF로 저장](인쇄 전용 문서만 .skx-reading — 사용자 판단 결과) ⑬ 시연 메모 — 손님이 중간에 떠난 연구는 새로고침으로 풀리지 않는다(잡은 서버에서 돌고 브라우저 ID 는 localStorage), DeepResearch 모드 입력창 한 줄의 [취소] 한 번.

- [ ] **Step 3: `docs/roadmap/00_status.md` — round06 줄**

원 계획 Z3 Step 2 의 ①~⑤ 그대로(old 다섯이 dev `bae4d75` 에 한 번씩 있다 — 3행 `최종 갱신: 2026-10-12 (`, round06 머리 `** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색`, `- **round07 종료** — 적재 파이프라인 보강(`, 다음 할 일 `  - **06d 진행 화면·입구(10/17~18 배포 — nuxt 만)** — 브랜치 \`feat/round06d-research-progress-screen\`.`, 라운드 이력 `· 06d·06e 남음(2026-10-08 재정의 — spec §12) |`). 다만 ③ 의 06d 하위 줄 new 의 입구 구절을 '입구(별도 시작 페이지 없이 메인 입력창 하나 — [+ 연구 시작하기]는 늘 새 연구, DeepResearch 모드 입력창의 끝나지 않은 연구 한 줄 [보기]·[취소]·예시 연구 카드·탐색 방식, 사이드바 진행 중 줄 단계 글(숫자 없이)·이전 연구 [n], 소장자료 결과 [DeepResearch로 이어서 조사하기] — [담기]는 보류), round08 다크 테마 맞춤(보고서·절 자리는 읽기용 짙은 유리)' 으로 쓰고, '소장자료검색 문구' 구절을 뺀다. 06d 하위 줄 끝에 시연 메모 한 구절('손님이 떠난 연구는 입력창 한 줄의 [취소] — 새로고침으로 안 풀린다')을 더한다. 계획 줄에 둘째 부분 계획 경로를 더한다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "round06d-완료노트.md" docs/roadmap/00_status.md && grep -c "06d 진행 화면·입구(10/17~18 배포 — nuxt 만)" docs/roadmap/00_status.md`

Expected: `2`, `0`.

- [ ] **Step 4: spec 을 코드에 맞춘다(`docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`)**

원 계획 Z3 Step 3 의 ①(머리 상태 줄 — new 의 괄호 안 구절을 '처음부터 2단·큰 진행 막대·절 따라가기·탐색 중 절 자리·'검토 중' 후보·입구(메인 입력창 하나 — 2026-10-12~13 사용자 결정), `dev` 머지·nuxt 배포 대기' 로)·②(D22)·④(따라가기 행 세 군데)·⑤(절 자리 행)·⑥ 의 첫 항목(탐색 중 PlanCard — 그대로)·⑦(§12-10 고치지 않음 — 아래 ⑥ 의 Q8 줄은 예외)·⑨(오프셋 행)는 그대로 한다. 바꾸는 것:

① D26 행 — old:

```markdown
§9 의 06d 범위를 덮는다 |
```

new:

```markdown
§9 의 06d 범위를 덮는다. **2026-10-12~13 사용자 결정으로 고침(06d 둘째 부분 계획 정함 20~27·최종 결정 A~G):** 별도 `/research` 홈·'모두 보기 (N)' 은 만들지 않는다 — DeepResearch 시작은 메인 입력창 + DeepResearch 모드 하나, 사이드바 [+ 연구 시작하기]는 늘 새 연구. DeepResearch 모드가 켜진 입력창(+ 메뉴 — `SearchPlusMenu.vue`)에 끝나지 않은 연구 한 줄 [보기]·[취소](판단은 `utils/researchStart.ts`·`useResearchStarter` 한 곳). 예시 연구는 메인에서 DeepResearch 모드를 켰을 때 입력창 아래 카드, 사이드바는 진행 중 줄의 단계 글(숫자 없이)과 '이전 연구 [n]', 소장자료 결과 'SKOVIX 추천 1권' 아래 [DeepResearch로 이어서 조사하기]([담기 ▾]는 보류). '도서검색' 문구는 round08 이 두 갈래 전환(자료 검색 · 논문 검색)으로 정리했다 |
```

② §12-1 표의 06d 입구 행 — old:

```markdown
| 06d 빠른검색 [담기]·[딥리서치로 더 깊게], 사이드바 단계 표시·'모두 보기 (N)', `/research` 홈·예시 연구 | 06d(D26). N 의 kind 별 total 은 06e(fastapi — §12-5) |
```

new:

```markdown
| 06d 입구 — 메인 입력창 하나(DeepResearch 모드·탐색 방식·끝나지 않은 연구 한 줄 [보기]·[취소]·예시 연구 카드), [+ 연구 시작하기]는 늘 새 연구, 사이드바 진행 중 줄 단계 글(숫자 없이)·'이전 연구 [n]', 소장자료 결과 [DeepResearch로 이어서 조사하기] | 06d(D26 — 2026-10-12~13 사용자 결정·2026-10-13 최종 결정으로 고침: `/research` 홈·'모두 보기 (N)' 없음, 06d 는 history `total` 을 읽지 않는다, [담기 ▾]는 보류). 논문 결과의 [DeepResearch로 이어서 조사하기]는 round08 이 만들었다 |
```

③ §12-3 입구 블록 — `**입구(D26)**` 줄부터 `- **대회 뒤:** 메인 [빠른검색|딥리서치] 모드 토글·도서 숨김.` 줄까지(dev `bae4d75` `:554-570`)를 아래로 바꾼다. old 는 그 열일곱 줄 그대로다(`sed -n '/^\*\*입구(D26)\*\*/,/^- \*\*대회 뒤:\*\* 메인/p'` 로 뽑아 Edit 의 old 로 쓴다 — 줄이 길어 여기 옮겨 적지 않는다; 뽑은 글의 첫 줄이 `**입구(D26)**`, 끝 줄이 `- **대회 뒤:** 메인 [빠른검색|딥리서치] 모드 토글·도서 숨김.` 인지 본다). new:

```markdown
**입구(D26 — 2026-10-12~13 사용자 결정·2026-10-13 최종 결정 A~G 로 고침, 06d 둘째 부분 계획 정함 20~27)**
- **시작은 메인 입력창 하나:** 별도 시작 페이지(`/research` 홈)는 만들지 않는다. DeepResearch 는 메인 논문 패널 입력창의 + 메뉴·슬래시 명령 모드다(round08 — 전환은 자료 검색 · 논문 검색 두 갈래). 시작 판단(끝나지 않은 연구 한 줄·탐색 방식·시작 요청)은 `useResearchStarter`(`composables/useResearch.ts`)와 + 메뉴(`SearchPlusMenu.vue`) 한 곳이다 — 어느 입구로 와도 같은 판단.
- **사이드바 [+ 연구 시작하기]:** 늘 메인에서 DeepResearch 모드로 새 연구를 시작한다(`/?start=deep-research`) — 끝나지 않은 연구가 있어도 그 화면으로 가지 않는다(대회 시연에서 이전 연구로 가면 이상하다).
- **끝나지 않은 연구 한 줄:** 이 브라우저의 기록에 진행 중(created·planning·approved·queued·running — 사이드바 배지 '진행 중'과 같은 상태)이거나 승인 대기인 연구가 있으면 DeepResearch 모드가 켜진 + 메뉴 안에 한 줄 — '진행 중인 DeepResearch n건 · [보기] [취소]'(승인 대기만 있으면 '승인 대기 중인 …'). [보기]·[취소]는 가장 최근 것, [취소]는 기존 취소 API·한 번 확인('정말 취소'). 메인·`/papers` 랜딩·논문 결과 검색바 어디서나 같다. 막지는 않는다 — 서버의 승인 429 `browser_active` 가 마지막 안전망. 손님이 중간에 떠난 연구는 새로고침으로 풀리지 않는다(잡은 서버에서 돌고 브라우저 ID 는 localStorage) — [취소] 한 번.
- **예시 연구:** 메인에서 DeepResearch 모드를 켰을 때 입력창 아래 카드 2~3개(질문·실행 시각·코퍼스 범위 — 시연 정직성 규칙, 누르면 그 연구가 도달한 단계 화면, 읽기 전용 — `research_works.is_example`·쓰기 API 409). 목록은 `GET /api/research-works?example=1`, 시각·범위는 `GET /api/research/{id}/work` 의 `corpus`, 지정은 `scripts/research_eval/mark_example.py`. 사이드바에는 두지 않는다.
- **사이드바:** 진행 중 줄의 배지 옆에 지금 단계 글('계획 중'·'대기 중'·'근거 수집 중'·'보고서 작성 중' — 숫자 없이 기록 응답의 상태만으로, 잡을 따로 읽지 않는다), 글자 `--skx-teal-ink`. 완료 줄에는 붙이지 않는다. 5줄을 넘으면 구분선 아래 '이전 연구 [n]'(펼치면 '접기'). '모두 보기 (N)' 은 없다.
- **소장자료 결과:** 'SKOVIX 추천 1권' 아래 [DeepResearch로 이어서 조사하기](메인 입력창에 결과의 검색어를 채워 DeepResearch 모드 — 시작하지 않는다). [담기 ▾](추천 1권을 이어간 연구 목록에 — D17)는 보류(사용자 답 대기). 논문 결과의 [DeepResearch로 이어서 조사하기]는 round08 이 만들었다.
- **탐색 방식(D28):** + 메뉴에서 DeepResearch 를 고르면 칩 옆에 '탐색 방식' 두 칸(`ResearchModePicker.vue` — radiogroup), 고른 값을 잡 params `broaden`·`query_context` 두 칸으로 늘 함께 싣는다. 기억 localStorage `skx_research_mode`(읽지 못하면 정밀하게), [같은 질문으로 다시 시작]은 원래 잡의 두 칸, 연구 화면 머리에 그 잡의 방식(두 칸 다 0 → 폭넓게, 두 칸이 없거나 갈리면 표시 없음). 판단은 `utils/researchMode.ts`.
- **대회 뒤:** 메인 [빠른검색|딥리서치] 모드 토글·도서 숨김.
```

④ §12-10 Q8 의 예시 노출 줄 — old:

```markdown
  - 예시 연구 노출 자리 = `/research` 홈 한 곳, 들어가는 길 = '모두 보기 (N)'(§12-3) — 06d.
```

new:

```markdown
  - 예시 연구 노출 자리 = `/research` 홈 한 곳, 들어가는 길 = '모두 보기 (N)'(§12-3) — 06d. → 2026-10-13 사용자 결정으로 바꿈: 메인에서 DeepResearch 모드를 켰을 때 입력창 아래 카드(§12-3 입구).
```

⑤ §12-11 의 '소장자료검색' 항목 — old:

```markdown
- **'소장자료검색'으로 맞출 다른 문구** — 입력창 안내(`pages/index.vue:82`), 사이드바 묶음 이름(`AppSidebar.vue:150`).
```

new:

```markdown
- ~~**'소장자료검색'으로 맞출 다른 문구** — 입력창 안내(`pages/index.vue:82`), 사이드바 묶음 이름(`AppSidebar.vue:150`).~~ — round08 이 정리했다: 메인 전환은 두 갈래(자료 검색 · 논문 검색), 사이드바 탭은 걷고 최근 검색 칩은 '소장자료'. 06d 는 고치지 않았다.
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -cE "프로그램이 일으킨 스크롤은 플래그로 거른다|ReportView 자리 모드 또는|고정한 인용 팝오버|자리·모양은 06d 계획이 정한다|노출 자리는 \`/research\` 홈 한 곳이다" docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && grep -c "06d 둘째 부분 계획" docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`

Expected: `0`(옛 문구가 남지 않았다 — `자리·모양은 06d 계획이 정한다`·`노출 자리는 … 한 곳이다` 는 ③ 의 블록 바꾸기로 사라진다), `2`(D26 행·§12-3 입구 머리 줄).

- [ ] **Step 5: 반복 함정 — 이번에는 더하지 않는다는 판단을 적는다**

원 계획 Z3 Step 4 그대로(운영 전이라 더할 것이 없다 — Z7 이 다시 판단). round08 완료노트의 함정 후보('새 부품 파일을 로컬 dev 서버가 자동 등록 못 함')는 이 계획이 명시 import 로 피했다 — Z7 에서 함께 판단한다.

- [ ] **Step 6: 문서 리뷰 — code-reviewer 하나**

원 계획 Z3 Step 5 의 프롬프트에서 읽을 코드 목록을 이 계획 '1-5' 의 새 파일과 `AppSidebar.vue`·`pages/index.vue`·`useResearch.ts`·`landingStart.ts` 로 바꾸고, 정함 범위를 '정함 1~27(13~16·18 은 둘째 부분이 갈음)'으로, 상수 목록에 `EXAMPLE_CARD_MAX 3`·`NOTICE_CANCEL_ARM_MS 400`·'진행 중인 DeepResearch n건'·'승인 대기 중인 DeepResearch n건'·'정말 취소'·'이전 연구'·단계 글 넷('계획 중'·'대기 중'·'근거 수집 중'·'보고서 작성 중')을 더해 쓴다. 발견은 Edit 로 고친다(같은 커밋에).

- [ ] **Step 7: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && ! grep -n '<[^>]*>' "docs/roadmap/round06d-완료노트.md" && git add docs/superpowers/plans/2026-10-13-round06d-part2-entry-style.md && git add docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md && git add "docs/roadmap/round06d-완료노트.md" && git add docs/roadmap/00_status.md && git add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git status --short && git commit -m "[Docs] round06d — 둘째 부분 계획(입구·스타일 — round08 뒤, 사용자 결정 2026-10-12~13)과 원 계획의 갈음 한 줄, 완료노트(왜·한 일·리뷰·검증·결정 정함 1~27·조건부 Task 판정·이월, 배포 전), 현재 상태(round06 줄 — 06d 구현 완료·nuxt 배포 대기), spec 을 코드에 맞춘다: 머리 상태 줄, D22 구현 방식, D26 과 §12-3 입구 블록(별도 /research 홈 없이 메인 입력창 하나·[+ 연구 시작하기]는 늘 새 연구·입력창의 끝나지 않은 연구 한 줄·예시 연구 카드·사이드바 단계 글·이전 연구 [n]·소장자료 결과 [DeepResearch로 이어서 조사하기]·탐색 방식, [담기]는 보류), §12-1 06d 입구 행, §12-3 따라가기·절 자리·오프셋 행, §12-10 Q8 예시 노출 줄, §12-11 의 탐색 중 PlanCard·소장자료 문구"
```

Expected: `grep` 이 찍는 줄 없이 커밋 1개(`A` 둘·`M` 셋).

---

### Task Z4: (사용자 승인) dev 머지 — 머지 문 확인·P9 재확인·임시 worktree

원 계획 Task Z4 그대로(Step 1 머지 문 네 가지·`merge-tree` 충돌 확인·문서 충돌 규칙 → Step 2 승인 → Step 3 임시 worktree 에서 `--no-ff` 머지·push·지우기). 바뀐 것:
- Step 1 ② 의 L6 확인은 P7 확인이다(`:question-used="questionUsed"` `1`, `questionUsedFromSteps` `1` 이상 — 그대로 맞다). ③ 의 N8 은 P9 다.
- Step 1 에 한 줄 더 — **핑크 테마와의 dev 머지 순서(최종 결정 G):** `git -C C:/Users/LANDSOFT/mygit/NL_library_AI merge-base --is-ancestor 1b0eaa4 dev && echo "핑크 dev 에 있음"` · `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d merge-base --is-ancestor 1b0eaa4 HEAD && echo "06d 가 핑크를 받음"`. 둘 다 나오면(2026-10-13 그대로 — dev `7adf93b`·06d `a084ff3`) 어느 쪽도 rebase 하지 않는다 — 승인 요청에 그 사실만 적는다. 핑크가 dev 에 없으면(되돌렸거나 따로 승인을 기다리면) 머지 전에 사용자에게 순서를 묻는다: 06d 가 먼저 들어가면 핑크 쪽이 rebase, 핑크가 먼저면 06d 가 rebase(이 브랜치는 dev 를 merge 로 받아 왔으니 `git merge dev` 로 받아도 되는지 함께 묻는다). 핑크만 받은 줄(06d 가 핑크를 받았는데 dev 에는 없다)은 06d 머지가 핑크까지 dev 에 넣는다 — 그대로 가지 말고 멈춰 묻는다.
- Step 1 에 한 줄 더 — **round08 이 운영에 반영됐는가(최종 결정 F):** 사용자에게 서버에서 `docker exec nl-lib-nuxt sh -c 'grep -l "skx-holo" /app/.output/public/_nuxt/entry.*.css | wc -l'` 를 쳐 달라고 한다. `1` 이면 round08 이 운영에 있다. `0` 이면 round08 은 운영 이미지(`nl-lib-nuxt:latest` — `6b90e79` 기준)로만 올라가 있고 재배포가 남았다 — dev 머지는 해도 되지만 **Z5 는 round08 의 운영 반영(그 라운드의 Recreate·`nginx -s reload`·확인) 뒤로 미룬다**. 06d 와 round08 을 한 배포로 함께 내지 않는다.
- Step 2 승인 요청에 두 값(핑크 순서·round08 운영 반영)과 'round08 을 먼저 운영 반영하고 06d 는 그 뒤 따로 배포한다(최종 결정 F)' 를 함께 보인다. 한 줄 더 — **핑크는 06d 배포에 함께 나간다:** round08 운영 이미지(`6b90e79`)에는 핑크 테마 구조(`1b0eaa4`·`94b56df`)가 없고(2026-10-13 `git merge-base --is-ancestor 1b0eaa4 6b90e79` 실패 확인) 06d 는 핑크가 든 dev 로 빌드하므로, 설정 톱니의 [다크] [라이트]는 06d 배포로 처음 운영에 나가고 `:pre-round06d` 로 되돌리면 함께 빠진다. 핑크를 round08 재배포에 실으려면 그 재배포를 06d 머지 전 dev 로 다시 빌드해야 한다 — 어느 쪽인지 사용자가 정한다.
- Step 3 의 머지 메시지: `Merge feat/round06d-research-progress-screen into dev — round06d 진행 화면(처음부터 2단·큰 진행 막대·절 따라가기·탐색 중 절 자리·검토 중 후보·다크 맞춤과 보고서 읽기용 짙은 유리)·입구(메인 입력창 하나 — [+ 연구 시작하기]는 늘 새 연구, 입력창의 끝나지 않은 연구 한 줄 [보기]·[취소]·예시 연구 카드·탐색 방식, 사이드바 단계 글·이전 연구 [n], 소장자료 결과 [DeepResearch로 이어서 조사하기]), nuxt 만·스키마 변경 없음`(8-1 을 잘랐으면 소장자료 구절을 뺀다).

---

### Task Z5: (사용자) 운영 배포 — 경우 가르기·nuxt 빌드·Recreate·게이트웨이 reload (10/17~18)

원 계획 Task Z5 그대로(경우 A·B·C 표, 빌드 확인, pdfjs 복사, `build_dev_images.sh nuxt`, 되돌리기 태그 `:pre-round06d`, 경우 C 의 워커 셋 → fastapi, nuxt Recreate → `nginx -s reload`, 함정 3·12·16·20 — 경우 C 는 14·18·24). 바뀐 것:
- **Step 0(새로 — 최종 결정 F): round08 이 먼저 운영에 반영돼 있는가.** `docker exec nl-lib-nuxt sh -c 'grep -l "skx-holo" /app/.output/public/_nuxt/entry.*.css | wc -l'` 가 `1` 이 아니면 **여기서 멈춘다** — round08 을 먼저 운영에 반영한다(round08 은 이미 운영 이미지 `nl-lib-nuxt:latest` — `6b90e79` 기준 — 로 올라가 있고 재배포만 남았다: 그 라운드의 Recreate·`nginx -s reload`·화면 확인). round08 을 확인한 다음 날이든 같은 날이든 06d 는 **그 뒤 따로** 낸다. 그래야 되돌리기 태그 `:pre-round06d`(06d 빌드 전에 지금 `nl-lib-nuxt:latest` 를 태그)가 round08 이 든 이미지가 되어, 06d 를 되돌려도 다크 테마는 남는다. 핑크 테마 구조는 `6b90e79` 에 없어 이 06d 배포(dev 빌드)로 함께 나가고 되돌리면 함께 빠진다(Z4 Step 2 에서 사용자가 정한 대로 — round08 재배포를 dev 로 다시 빌드해 핑크를 먼저 실었으면 `:pre-round06d` 에도 핑크가 든다).
- Step 2 의 `curl … http://localhost:92/research` 는 배포 뒤에도 `404` 가 맞다(`/research` 홈이 없다).
- Step 6 의 확인을 이것으로 바꾼다:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/research
docker exec nl-lib-nuxt sh -c 'grep -l "rs-pbar" /app/.output/public/_nuxt/entry.*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "rs-synth__bar" /app/.output/public/_nuxt/*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "rs-mode__opt" /app/.output/public/_nuxt/entry.*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "rs-start-note" /app/.output/public/_nuxt/entry.*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "rs-examples__card" /app/.output/public/_nuxt/entry.*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "skx-history__older" /app/.output/public/_nuxt/*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "지금 쓰는 곳으로" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "탐색 방식" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "이전 연구" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "정말 취소" /app/.output/public/_nuxt/*.js | wc -l'
curl -s "$API/research-works?example=1" -H "x-session-id: $SID"; echo
```

Expected: `404` · `1` · `0` · `1` · `1` · `1` · `1`(사이드바 scoped CSS 청크) · 나머지 넷 각각 `1` 이상(2026-10-13 2차 사본 빌드에서 `rs-pbar`·`rs-mode__opt`·`rs-start-note`·`rs-examples__card` 는 entry CSS 하나, `rs-synth__bar` 는 0, `skx-history__older` 는 `AppSidebar.*.css` 하나, '탐색 방식'·'이전 연구'·'정말 취소'·'지금 쓰는 곳으로' 는 JS 청크 하나씩) · 예시 목록 `{"items":[]}`(리허설 전) 또는 지정한 예시들.
- 배포 뒤 알림: 경우 B 로 06d 가 먼저 나갔으면 06e 세션에 "06d 가 운영에 있다 — 06e 배포는 nuxt 를 dev(06d·round08 포함)로 만들고 LNB 연결(R6)은 06e 가 단다. `[id].vue` 단계 본문의 '딥리서치 보고서 보기' 는 round08 의 DEEP_RESEARCH 표기로. `research.css` 의 `.rs-card` 에 다크 가장자리(`--skx-frame-line` 1px·`--skx-frost-hilite`)가 붙어 단계 화면 카드도 받는다(보고서·절 자리 `.rs-card.rs-report` 만 읽기용 짙은 유리). 06e 계획의 '06d 몫'(`/research` 홈·빠른검색 [딥리서치로 더 깊게]·'소장자료검색' 문구·'모두 보기 (N)')은 사용자 결정 2026-10-12~13 으로 없어졌고 [담기]는 보류다(06d 둘째 부분 계획 정함 20~27·최종 결정 A~G)" 를 알린다.

---

### Task Z6: (사용자, 서버·브라우저) 운영 처음부터 끝까지 1회 — 진행 화면·입구·랜딩 예시

원 계획 Task Z6 의 Step 2~4(탐색 — 막대·절 자리·회차 상태·장부 더미·따라가기 / 작성·끝 — 막대 이어 차오름·따라가기·막힘·인쇄·돌아온 자리 / 좁은 화면)·Step 6(06c 판정 연계)·Step 7(다른 것이 나왔을 때)은 그대로 하되 다음을 바꿔 본다. Step 1 과 Step 5 는 아래 글로 갈음한다.

- Step 3 의 9(스타일) — '머리 kicker DeepResearch 는 청록 칩, 질문은 흰 글자로 한 단계 크다, 상태 배지는 단계 칩과 같은 크기, 옆 칸의 근거 장부·진행 패널 카드 머리 앞에 청록 막대(본문 카드 제목은 그대로), 카드·막대 가장자리에 옅은 선, 버튼·완료 배지·지금 단계 칩의 글자는 짙다(산호 위), 막대 빛 흐름은 밝은 띠, **보고서(초안·최종본)·탐색 중 절 자리는 옆 카드보다 한 단계 짙은 읽기용 유리에 거의 흰 글자**(초안이 최종본으로 바뀌어도 면이 그대로), [PDF로 저장] 은 흰 종이에 짙은 글자, Ctrl+P 는 짙은 면 그대로' 로 본다. 핑크가 이 배포로 처음 나갔으면(Z5 Step 0) 사이드바 톱니 [라이트]로 바꿔 같은 화면이 흰 면·짙은 글자로 깨지지 않는지도 한 번 본다.

- [ ] **Step 1: (브라우저, 1440px) 메인에서 시작 — 계획·승인 대기**

1. `/` — 전환 '논문 검색' 이 기본. 이 브라우저에 끝나지 않은 연구가 없을 때 사이드바 [+ 연구 시작하기] → 논문 패널 입력창에 DeepResearch 칩·초점·`탐색 방식` 두 칸(처음 쓰는 브라우저면 `정밀하게`), 한 줄 없음, 예시 연구가 지정돼 있으면 칩 아래 카드(리허설 전이면 없음). 예시 칩 `공공도서관 서비스 품질 평가 연구가 궁금해` 를 누르면 입력창에만 채워진다 → `정밀하게` 그대로 보낸다 → `/research/<잡 id>`. 잡 id 를 `J1` 로 적는다.
2. 계획 중·승인 대기·대기열 — 원 Z6 Step 1 의 2~4 그대로(막대 글줄·계획 중 카드 세로·'이렇게 이해했어요'). 이 동안 사이드바의 그 줄 배지 옆에 청록 '계획 중' → 승인 뒤 '대기 중'·'근거 수집 중'·'보고서 작성 중' 이 30초 안에 바뀐다(숫자 없음 — 정함 21). 완료 뒤 그 줄에는 배지 말고 아무것도 없다.
3. 탐색 방식 — 머리 상태 배지 옆 `탐색 방식 · 정밀하게`, 서버에서 원 Z6 Step 1 의 5 명령(`curl -s "$API/research/$J1" | grep -oE '"(broaden|query_context)": ?[0-9]+'`)이 두 칸 `1`.
4. 늘 새 연구·입력창 한 줄(정함 20) — `J1` 이 도는 동안 사이드바 [+ 연구 시작하기] → **메인으로 온다**(`J1` 화면으로 가지 않는다 — 최종 결정 A), 칩 줄 아래 '진행 중인 DeepResearch 1건 · 보기 취소' → [보기] 가 `J1` 로 간다. 돌아와 [취소] 한 번 → '정말 취소'·'그대로 두기' → [그대로 두기](J1 은 끝까지 둔다).

Expected: 넷 모두 위와 같다.

- [ ] **Step 5: (브라우저) 입구 — 사이드바·예시·소장자료 결과·탐색 방식**

1. 사이드바 — DeepResearch 묶음의 진행 중 줄에만 단계 글(숫자 없이 — 완료 줄에는 없다), 기록 6건 이상이면 구분선 아래 '이전 연구 [n] ⌄' → 펼치면 '접기', 키보드 Tab 으로 가 Enter 로 펼치고 접는다.
2. 승인 대기만 있을 때·[취소] — 새 질문 하나를 보내 계획이 서면(승인 대기) 그대로 두고, 다른 진행 중 연구가 없는 상태에서 사이드바 [+ 연구 시작하기] → 메인으로 가고 칩 줄 아래 '승인 대기 중인 DeepResearch 1건 · 보기 취소' → [보기] 가 그 연구로 간다. 돌아와 [취소] 를 빠르게 두 번(더블클릭) 눌러도 '정말 취소' 에서 멈추는지 본다 → 잠깐 뒤 한 번 더 → 줄이 사라지고 사이드바 그 줄 배지가 '취소'(이 확인이 운영에서 [정말 취소]를 누르는 유일한 곳 — 이 질문만 멈춘다).
3. 예시 연구(리허설에서 지정한 뒤 — 지정 전이면 '해당 없음') — 카드마다 '읽기 전용'·질문·'… 실행'(KST)·범위 글, 누르면 그 예시의 단계 화면.
4. 소장자료 결과(8-1 을 했으면) — 자료 검색 → 추천 패널 아래 `+ DeepResearch로 이어서 조사하기` → 메인 논문 패널에 그 검색어 + DeepResearch 칩(시작하지 않는다), 뒤로 가기로 결과. [담기 ▾]는 없다(보류).
5. LNB(P9 를 했으면) — 원 Z6 Step 5 의 6 그대로.
6. 탐색 방식 — 원 Z6 Step 5 의 7 그대로(`J2` 폭넓게 `0`·`0`, 기억, 다시 시작 `J3` 은 원래 방식, 06c 전 잡 머리 표시 없음). ④ 의 '`/research` 홈의 새 연구에도 같은 두 칸' 은 빼고, '`/papers` 랜딩·논문 결과 검색바의 + 메뉴에도 같은 두 칸(결과 검색바에는 설명 없음)' 으로 본다.
7. 결과 검색바의 한 줄 — `J2`(또는 `J3`)가 도는 동안 `/papers` 검색 결과의 [DeepResearch로 이어서 조사하기] → 검색바에 칩, 바 아래 오른쪽에 '진행 중인 DeepResearch 1건 · 보기 취소'(결과 틀 위에 떠 있고 + 메뉴를 열면 메뉴가 위). 375px 에서 가로 스크롤 없음.

Expected: 일곱 모두 위와 같다(자른 Task 의 항목은 '해당 없음').

---

### Task Z7: 배포 기록 — 기록 브랜치·dev 머지

원 계획 Task Z7 그대로(기록 브랜치 `docs/round06d-deploy-record` → 완료노트 §5-1~5-4·§7·상태 → 00_status·spec 머리 줄·반복 함정 판단 → 커밋 → 사용자 승인 뒤 임시 worktree 머지). 바뀐 것: §5-2 의 `/research` 는 '404 그대로(홈 없음)', §5-3 에 Z6 Step 1 의 4(늘 새 연구·입력창 한 줄)·Step 5 의 1~2·7(사이드바·승인 대기 줄·[취소] 두 번 누르기·결과 검색바의 줄)을 적고, §5-1 에 Z5 Step 0 의 round08 운영 반영 확인(언제 반영했는지)을 적는다. 00_status 다음 할 일의 06d 줄 new 의 남은 것은 '리허설(10/23~25)에서 예시 연구 지정 뒤 메인 DeepResearch 모드의 예시 카드(실행 시각·범위·읽기 전용) 다시 보기' 로 쓴다. 그 뒤 `dev→main` 머지·push(`/round-finish`)를 06d 에서 할지 round06 세 줄을 모두 마친 뒤 한 번에 할지 사용자에게 묻는다(round08 의 `main` 머지 대기와 함께 — round08 완료노트 '상태').

#### 롤백 (사용자, 서버)

원 계획 Z7 끝 '롤백' 그대로 — nuxt 는 `:pre-round06d` 태그로 되돌리고 `nginx -s reload`. 되돌린 뒤 `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/research` 는 배포 전과 같이 `404` 다(06d 는 이 주소를 만들지 않는다 — 원 계획의 '200 → 404' 확인은 빼고 `/` 의 `200` 과 화면만 본다). 최종 결정 F 대로 round08 을 먼저 반영했으면 `:pre-round06d` 는 round08 이 든 이미지라 되돌려도 다크 테마는 남는다(되돌린 뒤 `skx-holo` 확인이 `1`). 핑크 테마(설정 톱니 [다크] [라이트])는 06d 배포로 처음 나갔으면 함께 빠진다(Z5 Step 0) — 사용자에게 그렇게 알린다. Z5 Step 0 을 건너뛰어 round08 반영 전에 06d 를 냈다면 되돌리기가 round08 까지 걷는다 — 그러지 않는다. 되돌린 뒤에도 dev 에는 06d 가 있다 — 고쳐서 다시 낼지(`fix/round06d-live-check`), dev 에서 되돌릴지(revert, 사용자 승인) 정하기 전까지 dev 로 nuxt 를 빌드·Recreate 하지 않는다.
