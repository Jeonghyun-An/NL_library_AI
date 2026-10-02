# 논문 상세 재구현 구현 계획 (round05a)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 딥리서치 보고서·논문 검색에서 연 논문 상세가 출처를 주소에 싣고, [돌아가기]로 처음 화면의 보던 자리까지 돌아가게 한다(A안). 같은 라운드에서 03 논문 상세 화면 나머지(①~⑧)와 원문 뷰어를 고친다.
- 주소 규칙: 상세 주소에 출처(`from=search`+`h`·`q` / `from=research`+`job`·`e`)와 돌아갈 자리(`at`·`y`)를 싣는다. 연관 논문으로 넘어가도 처음 출처와 자리를 잇고 `e`·`score` 만 뗀다.
- 돌아가기: 직전 기록이 출처면 `router.back()`, 아니면 출처 주소로 `router.push`. 사이드바는 출처를 따라 강조한다(보고서에서 왔으면 딥리서치 탭과 그 보고서).
- 위치 복원: 떠날 때 누른 요소(인용칩·결과 카드·제외 목록 항목)의 앵커와 화면 높이를 출처 주소에 싣고, 돌아온 화면이 다 그려진 뒤 그 요소를 같은 높이에 즉시 맞춘다. 인용칩이면 초점을 돌려 팝오버를 다시 연다. 맞춘 뒤 주소에서 `at`·`y` 를 지운다.
- 03 화면: 돌아가기 문구, 인용 맥락 배너, 관련도는 검색에서 왔을 때만, DeepRead 이름 통일, 원문 보기는 늘 원문 뷰어(KCI 는 보조 링크), "AI 요약" 탭과 기준 질문, 키워드 검색, 연관 논문 링크, AI 글 탭 캐시, 탭 제목, (선택) 이 논문으로 딥리서치.
- 원문 뷰어: Esc 닫기·초점 되돌리기·배경 고정, 머리의 쪽 표시·쪽 넘기기·인용 대목 넘기기, 열기 전 확인 공용화.

**Architecture:**
- 순수 로직은 `frontend/utils/` 의 새 모듈에 모으고 Vitest 로 검증한다.
  - `detailSource.ts`: 주소·앵커.
  - `restorePosition.ts`: 복원 계산·주소의 자리.
  - `aiCache.ts`: AI 글 캐시.
  - `paperDetail.ts`: 인용 맥락 배너·AI 요약 기준 질문.
  - `pdfViewer.ts`: 원문 뷰어 판단·열기 전 확인 요청.
  - `paperResearch.ts`: ⑧ 질문 초안.
  - 기존 `historyRoute.ts`·`browserId.ts` 에는 조금 더한다.
- 화면에 붙이는 일은 composable 둘이 맡는다.
  - `useRestorePosition.ts`: 돌아올 때 맞추기와 떠날 때 자리 싣기.
  - `usePdfOpener.ts`: 열기 전 확인과 뷰어 상태.
- 페이지·컴포넌트는 위 함수를 부르기만 한다. 대상은 `pages/papers/[id].vue`·`pages/papers/index.vue`·`pages/index.vue`·`pages/research/[id].vue`, `components/research/*`, `components/PdfViewer.vue`, `components/AppSidebar.vue` 다. 컴포넌트 마운트 도구가 없어(의존성 추가 금지) typecheck·build·grep 으로 확인한다.
- 백엔드는 바꾸지 않는다(D9). 배너는 기존 `GET /api/research/{id}`, 원문 확인은 기존 `GET /api/books/{id}/pdf` 를 쓴다. 배포는 `nl-lib-nuxt` 하나다.

**Tech Stack:** Nuxt 4.4 · Vue 3.5 · vue-router 5 · TypeScript(strict·`noUncheckedIndexedAccess`) · Vitest 3.2(node 환경, 순수 로직만) · pdf.js 4.0.379(`public/pdfjs` 고정본)

**설계 근거:** `docs/superpowers/specs/2026-10-01-round05a-paper-detail-design.md`(이하 spec) 전체. 기능 명세서 요약은 spec §0~§5 에 있다. 맥락은 round04b spec `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md` 의 §4(기록·주소 규칙)·§6·§7-4(인터랙티브함 최우선)·§14, round04c spec `docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md` 의 §11(제외한 논문 목록)이다.

**실행 전 확인:**
- 백엔드(`app/`)는 건드리지 않는다. 화면 태스크의 확인 단계마다 `git diff d7f7e95..HEAD --stat -- app` 이 비어 있는지 본다.
- 저장소 안의 `.worktrees/` 폴더는 다른 작업(dev 문서)용 사본이다. 읽지도 고치지도 검색하지도 않는다(Grep·find 에서 제외).
- 운영 배포(spec §9)와 화면 확인(spec §7 화면 ①~⑪)은 이 계획의 단계 밖이다. 각 태스크의 "화면 확인(선택)"은 운영 API 미리보기 `frontend-prod-api` 를 띄울 수 있을 때 한다. 공유 운영 서버라 배포는 **사용자 승인 뒤** 따로 한다. docker·배포 작업이 없어 `docs/ops/recurring-gotchas.md` 에 걸리는 항목은 없다.
- 화면 규칙: 인터랙티브함·키보드·aria·`prefers-reduced-motion` 을 지킨다. 자동 스크롤로 끌고 가지 않는다(복원은 즉시 이동). `v-html` 을 새로 쓰지 않는다(상세의 AI 요약 `v-html` 은 기존 코드다).

**계획 작성 시 검증:**
- 세 초안(주소·복원 / 상세 화면 / 원문 뷰어)을 이 순서로 조립했다. 겹치는 곳은 하나로 합쳤고, 이름·시그니처·순서를 맞췄다.
  - 사이드바 강조: 두 초안에 같은 변경이 있었다. detailSource 의 `isUuid`·`readDetailSource` 를 쓰는 쪽으로 Task 2 하나에 모으고 두 초안의 단언을 합쳤다. 대문자 잡 id 단언은 `ID1.toUpperCase()` 대신 `MIXED` 로 바꿨다. `ID1` 은 숫자뿐이라 대문자로 바꿔도 같은 문자열이어서 아무것도 검사하지 못한다.
  - 열기 전 확인: 상세 초안의 `usePdfCheck`(`pdfOpenProblem`) 대신 원문 뷰어 초안의 `usePdfOpener` 와 `pdfStatus`(테스트 있음) 하나를 쓴다.
  - [원문 보기] 버튼·KCI 보조 링크·상세의 PdfViewer 태그는 원문 뷰어 태스크(Task 11)가 맡는다. 상세 배너 태스크(Task 9)는 배너 글만 그리고, 배너의 [인용 대목 보기]는 Task 11 이 `citedPdfTarget` 으로 단다.
  - 인용 대목: `CiteContext.passages: { page }[]`(쪽 없는 대목을 뺐다) 대신 `chunks`(쪽 순, 쪽 없는 대목은 뒤)로 바꿨다. 배너의 "N곳"과 뷰어의 "n/N"이 같은 수를 센다.
  - 상세에 새로 붙이는 클래스는 `pd-` 접두로 통일했다(원문 뷰어 초안의 `skx-pdetail__kci`·`__pdf-note`·`__research` → `pd-kci`·`pd-pdf-note`·`pd-research`). 이 페이지의 `<style scoped>` 는 Task 8 이 한 번 만들고, 뒤 태스크(9·11·12)는 블록 끝의 `@media (prefers-reduced-motion: reduce)` 앞에 규칙을 더한다.
  - 상세의 [돌아가기]는 수식 키 판단을 Task 3 의 `isPlainClick` 으로 한다(같은 규칙을 두 번 쓰지 않게).
  - Task 11 에서 두 가지를 더했다. KCI 링크에는 스크린리더용 "(새 창)"을 붙였다. KCI 보조 링크가 붙는 버튼 줄(`.skx-pdetail__btns`)에는 좁은 화면에서 넘치지 않게 `flex-wrap` 을 줬다.
  - ReportView 의 제외 목록 펼치기는 ProgressPanel 과 같이 목록이 바뀔 때도 다시 본다(초안이 같은 자리에서 최종본으로 바뀔 때).
  - Task 5 의 grep 확인은 백틱으로 시작하는 `` `/papers/${ `` 템플릿 문자열만 찾는다. 초안의 `'/papers/\${'` 는 `pages/index.vue` 의 `${apiBase}/papers/${cntsId}/related` 에 걸려 "출력 없음"이 될 수 없었다(사본에서 확인).
  - Task 8 의 키워드 `<span>` "교체 전" 들여쓰기를 실제 파일(20칸)에 맞췄다.
- 이 문서의 코드 블록을 저장소 밖 사본에 Task 1→13 순서로 기계적으로 적용하고 각 Step 의 명령을 돌렸다. 사본은 d7f7e95 작업 트리의 `frontend/` 와 spec 이고, `node_modules` 는 정션으로 이었다.
  - "새 파일" 14개를 만들었다. "교체 전" 96개는 모두 그 시점의 대상 파일에서 한 곳씩만 맞았다.
  - 각 "실패 확인"·"통과 확인" 출력은 이 사본의 실측이다. 프론트는 21파일 / 406 → 27 / 469 passed 다.
  - `nuxi typecheck` 의 `error TS` 는 매 태스크 0건이다. 검사가 살아 있는지는 일부러 넣은 TS 오류·템플릿 오류가 잡히는 것으로 확인했다.
  - `npm run build` 는 Task 4·5·8·9·11·12 뒤 모두 `Build complete!` 다. 자동 import 이름 중복 경고도 없다.
  - 백엔드 전체 pytest 는 890 passed 다(d7f7e95 — 이 계획은 백엔드를 바꾸지 않는다).
- 확인하지 못한 것: 실제 화면(spec §7 화면 ①~⑪).
  - 원문 뷰어 초안은 작성 때 가짜 API 와 하네스 페이지로 브라우저에서 확인했다. 확인한 것은 Esc·초점·배경 고정·쪽 표시·인용 대목 넘기기·404/502 안내·⑧ 흐름이다. 조립 때 바꾼 배너 버튼과 클래스 이름은 브라우저에서 다시 보지 않았다.
  - 주소·복원과 상세 화면은 브라우저에서 보지 않았다. 각 태스크의 "화면 확인"과 Task 13 Step 6 이 방어선이다.
- 계획 검토에서 고친 것:
  - Task 4 Step 7 은 ④를 Task 8 로 미뤘는데 Task 8 Step 10 목록에 ④·⑥이 없었다. 둘을 더하고, Task 13 Step 6 에 spec §7 화면 ①~⑪ 수동 목록을 풀어 적었다.
  - Task 8 의 연관 논문 카드는 제목 링크라 키보드로 갈 수 있게 됐지만 '유사한 점'은 마우스를 올려야만 펼쳐졌다. `:focus-within` 으로 초점이 가도 펼친다.
  - Task 9 배너 CSS 주석에 있던 "(원문 뷰어 태스크)"를 뺐다. 코드 주석에는 계획의 작업 단위를 적지 않는다.
  - Task 3 에 `behavior: "instant"` 를 쓰는 까닭(spec §4 의 `'auto'` 와의 차이)을 적었다.
  - 고친 계획을 HEAD(`8ac17b9`)의 임시 git worktree 에 Task 1→13 순서로 다시 기계적으로 적용했다. 새 파일 14개, "교체 전" 96개가 모두 한 곳씩 맞았다. 각 Step 의 실패·통과 출력, 21 / 406 → 27 / 469, 매 태스크 typecheck 0건, Task 4·5·8·9·11·12 뒤 build 통과, 백엔드 890 passed 가 위 수치와 같았다.

---

## 테스트 명령

**프론트** — `frontend/` 에서 돈다. 서브에이전트의 작업 디렉터리는 매번 초기화되므로 각 Step 의 명령은 절대 경로로 적었다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/<이름>.test.ts   # 한 파일
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run                              # 전체
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"   # 출력이 없어야 한다
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1                # └  ✨ Build complete!
```

- Vitest 는 `environment: "node"` 로 `tests/unit/**/*.test.ts` 만 돈다. 컴포넌트 마운트 도구는 없다. 컴포넌트·페이지는 로직을 utils/composables 로 빼서 테스트하고, 나머지는 typecheck·build·grep 으로 본다.
- `[Vue] Resolve plugin path failed …` 줄은 typecheck 의 기존 소음이다. `grep "error TS"` 에 걸리지 않는다.
- `npm run build` 의 `WARN` 줄(Browserslist·Sourcemap·`../img/… didn't resolve at build time`)도 기존 소음이다.

**백엔드** — Task 13 에서 한 번만 돈다(바꾸지 않았음을 확인한다).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git diff d7f7e95..HEAD --stat -- app       # 출력이 없어야 한다
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```

- 로컬 `app/.venv` 에는 pytest 가 없어서 PATH 의 `python` 으로 돌린다. 뺀 3개는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 실패한다(이 계획과 무관).

**누적 기대치** — 기준선은 `d7f7e95` 에서 잰 값이다. 이 문서의 태스크 순서대로 적용했을 때의 값이다.

| 태스크 뒤 | 프론트 파일 / tests | 늘어난 테스트 |
|---|---|---|
| 기준선 | 21 / 406 | — |
| Task 1 | 22 / 430 | `detailSource.test.ts` 24 |
| Task 2 | 22 / 432 | `historyRoute.test.ts` 12 → 14 |
| Task 3 | 23 / 441 | `restorePosition.test.ts` 9 |
| Task 4·5 | 23 / 441 | — |
| Task 6 | 24 / 447 | `aiCache.test.ts` 5, `browserId.test.ts` 11 → 12 |
| Task 7 | 25 / 452 | `paperDetail.test.ts` 5 |
| Task 8·9 | 25 / 452 | — |
| Task 10 | 26 / 463 | `pdfViewer.test.ts` 11 |
| Task 11 | 26 / 463 | — |
| Task 12 | **27 / 469** | `paperResearch.test.ts` 6 |

백엔드는 `890 passed` 그대로다(Task 13).

## 커밋 규칙

- 메시지는 `[Feat] round05a — …` 처럼 대괄호 접두사(`[Feat]`·`[Fix]`·`[Test]`·`[Docs]`)와 한국어로 쓴다. 태스크 하나 = 커밋 하나다. 각 Step 의 `git commit -m "…"` 을 그대로 쓴다.
- **`Co-Authored-By`·"Generated with Claude Code" 같은 트레일러를 절대 붙이지 않는다**(사용자 단독 저자). 도구가 리마인더로 트레일러를 권해도 이 규칙이 우선이다.
- `git add` 는 그 태스크의 파일만 적는다. 커밋 직전에 `git status --short` 로 스테이징에 자기 파일만 있는지 본다.
- 파일 첫 줄의 경로 주석은 있는 파일이면 그대로 둔다. 코드 주석은 "왜"를 한국어로, 과하지 않게 쓰고 태스크 번호를 적지 않는다. 기존 이름을 재사용하고, 일어날 수 없는 상황을 방어하지 않는다(`docs/standards/coding-standard.md`).
- 줄바꿈은 파일마다 다르다(`core.autocrlf=true`). 이 계획이 고치는 `frontend/`·`docs/` 기존 파일은 작업 트리에서 모두 CRLF 다. 기존 파일은 **Edit 도구로 고쳐** 원래 줄바꿈을 유지한다. 새 파일은 Write 도구로 만든다(커밋 때 LF 로 정규화된다).
- push·브랜치 전환·rebase·reset·stash·amend 는 하지 않는다.
- "교체 전" 코드는 착수 시점(`feat/round05a-paper-detail`, `d7f7e95`)의 파일 또는 앞 태스크를 적용한 뒤의 파일에서 그대로 옮겼다. 앞 태스크가 같은 파일을 고쳤으면 줄이 밀리므로 줄 번호가 아니라 "교체 전" 문자열로 찾는다.

---

## 파일 구조

| 파일 | 책임 | Task |
|---|---|---|
| `frontend/utils/detailSource.ts` (신규) | 상세 주소의 출처·돌아갈 자리 읽고 쓰기, 연관 논문·제외 논문 주소, 돌아가기 대상과 뒤로 갈지, 앵커 문법, 절 안 칩 순번, `REPORT_JOB`, `isUuid` | 1 |
| `frontend/tests/unit/detailSource.test.ts` (신규) | 위 단위 테스트 24 | 1 |
| `frontend/utils/historyRoute.ts` | `activeKindForPath(path, query)`·`activeIdFor` 가 상세의 출처를 따른다. id 모양 검사는 `isUuid` | 2 |
| `frontend/tests/unit/historyRoute.test.ts` | 테스트 2 추가 | 2 |
| `frontend/components/AppSidebar.vue` | 첫 탭을 정할 때 `route.query` 도 넘긴다 | 2 |
| `frontend/utils/restorePosition.ts` (신규) | 복원 계산(`scrollDelta`·`targetTop`·`restoreStep`), `spotOf`, `isPlainClick`, 주소의 자리(`withSpot`·`withoutSpot`·`hasSpot`), `pageOfItem` | 3 |
| `frontend/tests/unit/restorePosition.test.ts` (신규) | 위 단위 테스트 9 | 3 |
| `frontend/composables/useRestorePosition.ts` (신규) | `useRestorePosition`·`useDetailLeave`·`stampExcludedLink` | 3 |
| `frontend/components/research/CitationChip.vue` | `anchor` prop·`data-anchor`, [논문 상세]가 출처·자리를 싣고 떠난다 | 4 |
| `frontend/components/research/ReportSectionBody.vue` | `sectionIdx` prop, `anchoredSection` 으로 칩마다 앵커 | 4 |
| `frontend/components/research/ReportView.vue` | `jobId`·`revealExcluded` prop, `REPORT_JOB` provide, 제외 목록 링크·앵커·펼치기 | 4 |
| `frontend/components/research/ProgressPanel.vue` | `revealExcluded` prop, 제외 링크·앵커·회차 펼치기 | 4 |
| `frontend/pages/research/[id].vue` | 잡 id·펼칠 논문 전달과 돌아올 때 복원(4) · 원문 보기 확인을 `usePdfOpener` 로, 뷰어에 `passages`(11) | 4·11 |
| `frontend/pages/papers/index.vue` | 카드 앵커·출처 주소·떠날 때 자리·돌아올 때 쪽과 자리(5) · DeepRead 이름(8) · `?draft=` 초안 채우기(12) | 5·8·12 |
| `frontend/pages/index.vue` | 논문 분기 주소 규칙(5) · DeepRead 이름(8) | 5·8 |
| `frontend/utils/aiCache.ts` (신규) | AI 요약·연관 이유 캐시 키·읽기·쓰기 | 6 |
| `frontend/utils/browserId.ts` | `safeSessionStorage` | 6 |
| `frontend/tests/unit/aiCache.test.ts` (신규) · `frontend/tests/unit/browserId.test.ts` | 단위 테스트 5 + 1 | 6 |
| `frontend/utils/paperDetail.ts` (신규) | 인용 맥락(`citeContext`)·AI 요약 기준 질문(`summaryQuestion`)·조사(`withRo`) | 7 |
| `frontend/tests/unit/paperDetail.test.ts` (신규) | 위 단위 테스트 5 | 7 |
| `frontend/pages/papers/[id].vue` | 돌아가기·탭 제목·관련도·연관 링크·키워드·이름·`<style scoped>`(8) · 배너 글·기준 질문·캐시(9) · 원문 보기·배너 버튼·뷰어(11) · 이 논문으로 딥리서치(12) | 8·9·11·12 |
| `frontend/types/research.ts` | `PdfPassage`, `OpenPdfPayload.passages` | 10 |
| `frontend/utils/pdfViewer.ts` (신규) | pdf.js 앱 읽기·Esc 판단·인용 대목·초점 되돌릴 곳·확인 요청 | 10 |
| `frontend/tests/unit/pdfViewer.test.ts` (신규) | 위 단위 테스트 11 | 10 |
| `frontend/composables/usePdfOpener.ts` (신규) | 열기 전 확인과 뷰어 상태 | 11 |
| `frontend/components/PdfViewer.vue` | 머리(쪽·인용 대목)·Esc·초점 되돌리기·배경 고정·`passages` | 11 |
| `frontend/utils/paperResearch.ts` (신규) | ⑧ 질문 초안·주소·읽기 | 12 |
| `frontend/tests/unit/paperResearch.test.ts` (신규) | 위 단위 테스트 6 | 12 |
| `frontend/components/research/SearchPlusMenu.vue` | `activateMode` 노출 | 12 |
| `docs/superpowers/specs/2026-10-01-round05a-paper-detail-design.md` | 머리 상태 줄 → 구현 완료(운영 배포 전) | 13 |

백엔드(`app/`)·DB·nginx 설정은 건드리지 않는다.

---

## 실행 순서

| 단계 | 태스크 | 선행·병렬 |
|---|---|---|
| 1 | Task 1 → 2 → 3 → 4 → 5 (주소 규칙·사이드바·위치 복원) | Task 2·3 은 Task 1 의 함수를 쓴다. Task 4·5 는 Task 1·3 을 쓴다. Task 4 와 5 는 파일이 겹치지 않아 Task 3 뒤 병렬 가능 |
| 2 | Task 6 → 7 → 8 → 9 (03 논문 상세 화면) | Task 6 은 독립이고 Task 7 은 Task 1 의 타입만 쓴다 — 둘은 순수 로직이라 단계 1 과 병렬 가능(Task 7 은 Task 1 뒤). Task 8 은 Task 1·3 을 쓰고, `pages/papers/index.vue`·`pages/index.vue` 를 Task 5 와 함께 고치므로 Task 5 뒤에 한다. Task 9 는 Task 6·7·8 뒤 |
| 3 | Task 10 → 11 (원문 뷰어) | Task 10 은 순수 로직이라 언제든 병렬 가능. Task 11 은 Task 4(`pages/research/[id].vue`)·Task 9(배너) 뒤 |
| 4 | Task 12 (이 논문으로 딥리서치, 선택) | Task 5(`pages/papers/index.vue`)·Task 11(상세 import 줄) 뒤 |
| 5 | Task 13 (최종 확인) | 전부 뒤 |

**병렬로 돌릴 때(같은 작업 트리)**:
- 같은 파일을 고치는 태스크는 동시에 돌리지 않는다(`pages/papers/[id].vue` 는 8 → 9 → 11 → 12 순서).
- 커밋은 한 번에 하나씩 한다. 커밋 직전에 `git status --short` 로 스테이징에 자기 파일만 있는지 본다.
- "누적 기대치"의 전체 수는 태스크 번호 순서대로 적용했을 때의 값이다. 병렬 중에는 다른 태스크가 테스트만 먼저 써 둔 상태가 섞여 전체 수가 다를 수 있다. 각 태스크는 자기 테스트 파일로 확인하고, 전체 수는 Task 13 에서 본다.
- `npm run build`·`npx nuxi typecheck` 는 `.nuxt`·`.output` 을 함께 쓴다. 두 태스크가 동시에 돌리지 않는다.

---

## 공유 계약 (정본)

태스크 사이에서 주고받는 이름·모양이다. 태스크 코드는 이 목록과 일치하도록 맞췄다.

### 주소·복원 (Task 1~5)

- `utils/detailSource.ts` — Task 1
  - `type DetailSource = { kind: "search"; h: string | null; q: string } | { kind: "research"; job: string; e: string | null } | { kind: "none" }`
  - `interface ReturnSpot { at: string | null; y: number | null }`
  - `readDetailSource(query): DetailSource` — `job`·`h` 는 UUID 모양만(소문자로), `e` 는 `E#` 모양만. 검색 출처는 `h`·`q` 가 모두 틀리면 출처 없음.
  - `readReturnSpot(query): ReturnSpot` — `at` 은 앵커 문법만, `y` 는 0 이상 정수만, `y` 만으로는 자리를 정하지 않는다.
  - `detailUrl(cntsId, source, spot?, extra?): string` — 쿼리 순서는 출처 → `at`·`y` → `extra`(`score`·`chat`).
  - `relatedDetailUrl(cntsId, source, spot): string` — 처음 출처와 자리를 잇고 `e`·`score` 를 뗀다.
  - `excludedDetailUrl(job, cnts, y?): string` — 제외 논문 링크(`e` 없음, `at=x-<cnts>`).
  - `backTarget(source, spot): { label: string; to: string }` — 라벨 "검색 결과로"(`/papers?h=&q=&at=&y=`) / "딥리서치 보고서로"(`/research/<job>?at=&y=`) / "검색으로"(`/`).
  - `shouldGoBack(historyBack: string | null, to: string): boolean` — 경로가 같고, `to` 에 `h` 가 있으면 `h` 가, 없으면 `q` 가 같을 때 true. `at`·`y` 는 견주지 않는다.
  - 앵커: `citeAnchor(sectionIdx, eid, n?)` = `c-<s>-<E#>[-<n>]`(n 은 같은 절의 같은 근거 칩 순번, 0 은 적지 않는다), `excludedAnchor(cnts)` = `x-<cnts>`, `resultAnchor(cnts)` = `p-<cnts>`, `type Anchor`·`parseAnchor(at): Anchor | null`, `anchorSelector(at)` = `[data-anchor="…"]`(문법 밖이면 null).
  - `anchoredSection(sec, sectionIdx): AnchoredSection` · `type AnchoredPart` — 그리는 순서(도입 → 대표 논문 → 향후 과제)로 칩마다 앵커를 붙인다.
  - `REPORT_JOB: InjectionKey<ComputedRef<string>>` — ReportView 가 provide, CitationChip 이 inject.
  - `isUuid(s): boolean` — historyRoute 도 쓴다.
- `utils/historyRoute.ts` — Task 2
  - `activeKindForPath(path, query = {})` — 두 번째 인자를 받도록 넓혔다(기존 호출은 그대로). 상세의 `from=research&job=<UUID>` 은 `"research"`.
  - `activeIdFor(path, query, v1Map?)` — 시그니처 그대로. 상세의 `from=research` 는 그 잡 id, `from=search&h=` 는 그 기록 id.
- `utils/restorePosition.ts` — Task 3: `RESTORE_MAX_WAIT_MS`(2000)·`RESTORE_RETRY_MS`(100), `scrollDelta(elementTop, targetY)`, `targetTop(y, viewportHeight)`, `restoreStep(found, now, deadline): "align" | "retry" | "give-up"`, `spotOf(el, at): ReturnSpot`, `isPlainClick(e)`, `type QueryValue`, `hasSpot(query)`, `withSpot(query, spot)`, `withoutSpot(query)`, `pageOfItem(ids, id, pageSize)`.
- `composables/useRestorePosition.ts` — Task 3
  - `useRestorePosition(ready: Ref<boolean> | ComputedRef<boolean>, opts?: { maxWaitMs?: number }): { pending: Readonly<Ref<boolean>>; anchor: Anchor | null }` — 들어온 순간 주소의 `at`·`y` 만 본다. ready 가 된 뒤 보이는 요소를 같은 화면 높이로 즉시 맞추고(`scrollBy`), 인용칩이면 `focus({ preventScroll: true })`, 끝나면 `router.replace` 로 `at`·`y` 를 뗀다. 사용자가 먼저 움직이면 멈추고, 최대 대기 뒤 포기한다.
  - `useDetailLeave(): { leave(url, spot): Promise<void> }` — 떠나기 전에 이 화면 주소에도 `at`·`y` 를 `router.replace` 로 싣고 상세로 간다.
  - `stampExcludedLink(e, job, cnts)` — 새 창 제외 논문 링크의 `href` 에 누르는 순간의 높이를 싣는다.
  - 화면 규약: 이 composable 을 쓰는 페이지는 `definePageMeta({ scrollToTop: (to) => !to.query.at })` 를 둔다.
- 컴포넌트 props — Task 4: CitationChip `anchor: string`, ReportSectionBody `sectionIdx: number`, ReportView `jobId: string`·`revealExcluded?: string | null`, ProgressPanel `revealExcluded?: string | null`. 앵커를 받는 요소는 `data-anchor` 속성을 단다(인용칩 버튼·제외 목록 링크·검색 결과 카드 `article`).

### 상세 화면 (Task 6~9)

- `utils/aiCache.ts` — Task 6: `summaryCacheKey(paperId, question)`, `relatedCacheKey(paperId, relatedId)`, `readAiCache(storage, key): string | null`, `writeAiCache(storage, key, text): void`(빈 글·서버의 생성 실패 문구는 담지 않고, 용량 초과·막힌 저장소는 무시한다). 키 접두 `skx:ai:`.
- `utils/browserId.ts` — Task 6: `safeSessionStorage(): Storage | null`.
- `utils/paperDetail.ts` — Task 7: `interface CiteContext { question: string; label: string; chunks: ReportChunk[] }`(chunks 는 쪽 순, 쪽 없는 대목은 뒤), `citeContext(job, eid, cntsId): CiteContext | null`(근거 번호가 이 논문 것일 때만), `summaryQuestion(source, job): string`(검색어 / 보고서 질문 / 작성 중이면 잡 질문 / 빈 문자열), `withRo(word)`.
- `pages/papers/[id].vue` 페이지 스코프 — Task 8·9: `source`·`spot`·`back`(한 번만 읽는다), `onBack`, `cite`·`loadResearch`, `streamPaperReason(query)`, `readSSE(...): Promise<boolean>`([DONE] 까지 받았으면 true).

### 원문 뷰어·⑧ (Task 10~12)

- `types/research.ts` — Task 10: `interface PdfPassage { page: number | null; label: string }`, `OpenPdfPayload.passages?: PdfPassage[]`.
- `utils/pdfViewer.ts` — Task 10: `PdfJsApp`, `pdfJsApp(win)`, `viewerOwnsEscape(app)`, `citedPassages(chunks)`, `citedPdfTarget(cntsId, title, chunks): OpenPdfPayload`(첫 대목의 쪽에서 연다), `focusReturnTarget(path)`, `pdfStatus(url, headers, fetchFn?)`.
- `composables/usePdfOpener.ts` — Task 11: `usePdfOpener() → { pdf, checking, openPdf(target): Promise<string | null>, closePdf }`. 문제 문구는 돌려주기만 한다(딥리서치는 토스트, 상세는 누른 버튼 아래). `pdfCheckProblem` 은 `utils/researchErrors.ts` 에 그대로 둔다.
- `components/PdfViewer.vue` — Task 11: props `cntsId`·`title?`·`page?`·`passages?: PdfPassage[]`, emit `close`.
- `pages/papers/[id].vue` 페이지 스코프 — Task 11: `pdf`·`checkingPdf`·`openPdf`·`closePdf`·`pdfProblem`·`openOriginal`(머리의 [원문 보기]), `bannerPdfProblem`·`openCitedPassages(chunks)`(배너의 [인용 대목 보기]).
- `utils/paperResearch.ts` — Task 12: `paperResearchQuestion(title, keywords)`, `paperResearchUrl(question)`, `readResearchDraft(query)`. `SearchPlusMenu` 는 `defineExpose({ activateMode(id: SearchModeId) })`. `/papers` 는 `?draft=` 를 받아 채운 뒤 주소에서 지운다.

### 처음 계약에서 바뀐 것

- **CitationChip 의 inject**: 처음에는 ReportView 가 `{ jobId, sectionIdx }` 를 provide 하기로 했다. 그런데 provide 값은 컴포넌트마다 하나라 절마다 다른 `sectionIdx` 를 줄 수 없다. 같은 절에 같은 칩이 여러 번 나오면 순번도 필요하다. 그래서 provide 로는 `jobId`(`REPORT_JOB`)만 내리고, `sectionIdx` 는 ReportSectionBody 의 prop 으로 받는다. 앵커는 `anchoredSection` 이 계산해 CitationChip 에 `anchor` prop 으로 넘긴다.
- **PdfViewer 의 대목 목록**: `passages?: { page: number }[]` 대신 `PdfPassage[]`(`page: number | null` + 쪽 표시 `label`)로 정했다. 쪽 정보가 없는 대목도 세어야 배너의 "N곳"과 뷰어의 "n/N"이 같아진다.
- **열기 전 확인 공용 유틸**: `pdfCheckProblem` 을 옮기지 않고 `utils/researchErrors.ts` 에 둔다. 확인 요청은 `utils/pdfViewer.ts` 의 `pdfStatus`, 상태와 열기는 `composables/usePdfOpener.ts` 가 맡는다.
- **캐시 모듈 이름**: `utils/aiCache.ts`. 세션 저장소는 `utils/browserId.ts` 의 `safeSessionStorage` 로 연다.
- **historyRoute**: `activeKindForPath` 가 `query` 를 받도록 넓혔다. `activeIdFor` 는 그대로다.

---

## 단계 1 — 주소 규칙·사이드바·위치 복원 (Task 1~5)

- 범위는 spec §3(주소 규칙)·§4(떠날 때·돌아올 때)·D5(사이드바 강조)다.
- Task 1 이 주소·앵커 규칙을, Task 3 이 복원 도구를 만들고, Task 4·5 가 보고서·검색 결과 화면에 붙인다. 상세 페이지의 [돌아가기]·연관 논문 링크는 단계 2 의 Task 8 이 붙인다.

### Task 1: 논문 상세 주소 규칙 `utils/detailSource.ts`

계약 추가(공유 계약에 더한 것):
- `isUuid(s)`: 기록 id·잡 id의 모양을 한 곳에서 검사한다. Task 2에서 historyRoute도 이것을 쓴다.
- `type Anchor`와 `parseAnchor(at)`: spec §3에 이름만 나와 있던 것을 공개한다.
- `excludedDetailUrl(job, cnts, y?)`: 제외 논문 링크 주소.
- `anchoredSection(sec, sectionIdx)`과 타입 `AnchoredPart`·`AnchoredSection`: 한 절의 칩마다 앵커를 붙인다.
- `REPORT_JOB: InjectionKey<ComputedRef<string>>`.
- **계약 조정**: provide 값은 컴포넌트마다 하나다. 그래서 ReportView가 한 번 provide해서는 절마다 다른 `sectionIdx`를 줄 수 없다. 같은 절에 같은 칩이 여러 번 나오면 순번 n도 필요하다. 그래서 provide로는 `jobId`(`REPORT_JOB`)만 내린다. `sectionIdx`는 ReportSectionBody의 prop으로 받고, 앵커는 `anchoredSection`이 계산해 CitationChip에 `anchor` prop으로 넘긴다(Task 4).

**Files:**
- Create: `frontend/utils/detailSource.ts`
- Create: `frontend/tests/unit/detailSource.test.ts`

- [ ] **Step 1: 실패 테스트 작성** — `frontend/tests/unit/detailSource.test.ts` (새 파일)

```ts
// frontend/tests/unit/detailSource.test.ts
import { describe, expect, it } from "vitest";
import type { ReportSection } from "~/types/research";
import {
  anchorSelector,
  anchoredSection,
  backTarget,
  citeAnchor,
  detailUrl,
  excludedAnchor,
  excludedDetailUrl,
  isUuid,
  parseAnchor,
  readDetailSource,
  readReturnSpot,
  relatedDetailUrl,
  resultAnchor,
  shouldGoBack,
} from "~/utils/detailSource";
import { ID1, ID2 } from "./helpers/fakeHistory";

const MIXED = "AbCdEf01-2345-4789-abcd-0123456789ab";
const NO_SPOT = { at: null, y: null };

function section(over: Partial<ReportSection> = {}): ReportSection {
  return { heading: "절", intro: "", papers: [], future: [], evidence_chunks: {}, chunk_scores: {}, ...over };
}

describe("isUuid", () => {
  it("버전을 가리지 않고 UUID 모양만 받는다", () => {
    expect(isUuid(ID1)).toBe(true);
    expect(isUuid(MIXED)).toBe(true);
    expect(isUuid("1727000000000")).toBe(false);
    expect(isUuid("../../admin")).toBe(false);
  });
});

describe("readDetailSource", () => {
  it("검색 출처는 h·q 를 읽고 h 는 소문자로 맞춘다", () => {
    expect(readDetailSource({ from: "search", h: MIXED, q: " 딥러닝 " })).toEqual({
      kind: "search",
      h: MIXED.toLowerCase(),
      q: "딥러닝",
    });
    expect(readDetailSource({ from: "search", q: "딥러닝" })).toEqual({ kind: "search", h: null, q: "딥러닝" });
    expect(readDetailSource({ from: "search", h: ID1 })).toEqual({ kind: "search", h: ID1, q: "" });
  });

  it("딥리서치 출처는 잡 id 가 UUID 일 때만, 근거 번호는 E# 모양만 받는다", () => {
    expect(readDetailSource({ from: "research", job: ID2, e: "E3" })).toEqual({ kind: "research", job: ID2, e: "E3" });
    expect(readDetailSource({ from: "research", job: ID2, e: "<b>" })).toEqual({ kind: "research", job: ID2, e: null });
    expect(readDetailSource({ from: "research", job: "abc", e: "E3" })).toEqual({ kind: "none" });
  });

  it("from 이 없거나 모르는 값, 기록·검색어가 모두 틀린 검색 출처는 출처 없음이다", () => {
    expect(readDetailSource({ q: "딥러닝", h: ID1 })).toEqual({ kind: "none" });
    expect(readDetailSource({ from: "elsewhere", job: ID2 })).toEqual({ kind: "none" });
    expect(readDetailSource({ from: "search", h: "../../admin", q: "  " })).toEqual({ kind: "none" });
  });

  it("배열은 첫 값을 쓴다", () => {
    expect(readDetailSource({ from: ["research", "search"], job: [ID2, ID1] })).toEqual({
      kind: "research",
      job: ID2,
      e: null,
    });
  });
});

describe("readReturnSpot", () => {
  it("앵커 문법에 맞는 at 과 0 이상 정수 y 를 읽는다", () => {
    expect(readReturnSpot({ at: "c-2-E3-1", y: "240" })).toEqual({ at: "c-2-E3-1", y: 240 });
    expect(readReturnSpot({ at: "p-KCI_FI001484593", y: "0" })).toEqual({ at: "p-KCI_FI001484593", y: 0 });
  });

  it("문법 밖의 at 은 버리고, y 만으로는 자리를 정하지 않는다", () => {
    expect(readReturnSpot({ at: 'x-"]<b>', y: "10" })).toEqual(NO_SPOT);
    expect(readReturnSpot({ y: "10" })).toEqual(NO_SPOT);
  });

  it("음수·소수·없는 y 는 버리고 at 은 남긴다", () => {
    expect(readReturnSpot({ at: "x-C1", y: "-4" })).toEqual({ at: "x-C1", y: null });
    expect(readReturnSpot({ at: "x-C1", y: "12.5" })).toEqual({ at: "x-C1", y: null });
    expect(readReturnSpot({ at: "x-C1" })).toEqual({ at: "x-C1", y: null });
  });
});

describe("detailUrl·relatedDetailUrl·excludedDetailUrl", () => {
  const search = { kind: "search", h: ID1, q: "nlp" } as const;
  const research = { kind: "research", job: ID2, e: "E3" } as const;

  it("출처·돌아갈 자리·덧붙일 값을 순서대로 싣는다", () => {
    expect(detailUrl("CNTS-1", search, { at: "p-CNTS-1", y: 320 }, { score: "0.83" })).toBe(
      `/papers/CNTS-1?from=search&h=${ID1}&q=nlp&at=p-CNTS-1&y=320&score=0.83`,
    );
    expect(detailUrl("CNTS-1", research, { at: "c-0-E3", y: 120 })).toBe(
      `/papers/CNTS-1?from=research&job=${ID2}&e=E3&at=c-0-E3&y=120`,
    );
  });

  it("출처가 없으면 덧붙일 값만 싣는다", () => {
    expect(detailUrl("CNTS-1", { kind: "none" })).toBe("/papers/CNTS-1");
    expect(detailUrl("CNTS-1", { kind: "none" }, undefined, { chat: "1" })).toBe("/papers/CNTS-1?chat=1");
  });

  it("y 는 at 이 있을 때만 싣는다", () => {
    expect(detailUrl("CNTS-1", research, { at: null, y: 40 })).toBe(`/papers/CNTS-1?from=research&job=${ID2}&e=E3`);
    expect(detailUrl("CNTS-1", research, { at: "x-CNTS-1", y: null })).toBe(
      `/papers/CNTS-1?from=research&job=${ID2}&e=E3&at=x-CNTS-1`,
    );
  });

  it("만든 주소를 다시 읽으면 같은 출처·자리가 나온다", () => {
    const src = { kind: "search", h: ID1, q: "딥러닝 자연어 처리" } as const;
    const url = new URL(detailUrl("CNTS-1", src, { at: "p-CNTS-1", y: 15 }), "http://local");
    const query = Object.fromEntries(url.searchParams);
    expect(readDetailSource(query)).toEqual(src);
    expect(readReturnSpot(query)).toEqual({ at: "p-CNTS-1", y: 15 });
  });

  it("연관 논문은 처음 출처와 돌아갈 자리를 잇고 e·score 는 뗀다", () => {
    expect(relatedDetailUrl("CNTS-9", research, { at: "c-1-E3", y: 200 })).toBe(
      `/papers/CNTS-9?from=research&job=${ID2}&at=c-1-E3&y=200`,
    );
    expect(relatedDetailUrl("CNTS-9", search, { at: "p-CNTS-1", y: 80 })).toBe(
      `/papers/CNTS-9?from=search&h=${ID1}&q=nlp&at=p-CNTS-1&y=80`,
    );
    expect(relatedDetailUrl("CNTS-9", { kind: "none" }, NO_SPOT)).toBe("/papers/CNTS-9");
  });

  it("제외한 논문 링크는 근거 번호 없이 그 항목 앵커를 싣는다", () => {
    expect(excludedDetailUrl(ID2, "C1")).toBe(`/papers/C1?from=research&job=${ID2}&at=x-C1`);
    expect(excludedDetailUrl(ID2, "C1", 88)).toBe(`/papers/C1?from=research&job=${ID2}&at=x-C1&y=88`);
  });
});

describe("backTarget", () => {
  it("검색 출처는 검색 결과 주소로, 자리를 함께 넘긴다", () => {
    expect(backTarget({ kind: "search", h: ID1, q: "nlp" }, { at: "p-CNTS-1", y: 300 })).toEqual({
      label: "검색 결과로",
      to: `/papers?h=${ID1}&q=nlp&at=p-CNTS-1&y=300`,
    });
    expect(backTarget({ kind: "search", h: null, q: "nlp" }, NO_SPOT)).toEqual({
      label: "검색 결과로",
      to: "/papers?q=nlp",
    });
  });

  it("딥리서치 출처는 보고서 주소로 간다", () => {
    expect(backTarget({ kind: "research", job: ID2, e: "E3" }, { at: "c-0-E3", y: 120 })).toEqual({
      label: "딥리서치 보고서로",
      to: `/research/${ID2}?at=c-0-E3&y=120`,
    });
    expect(backTarget({ kind: "research", job: ID2, e: null }, NO_SPOT)).toEqual({
      label: "딥리서치 보고서로",
      to: `/research/${ID2}`,
    });
  });

  it("출처가 없으면 홈 검색으로 간다", () => {
    expect(backTarget({ kind: "none" }, { at: "p-CNTS-1", y: 10 })).toEqual({ label: "검색으로", to: "/" });
  });
});

describe("shouldGoBack", () => {
  it("직전 기록이 같은 보고서면 at·y 가 달라도 뒤로 간다", () => {
    expect(shouldGoBack(`/research/${ID2}?at=c-0-E3&y=120`, `/research/${ID2}?at=c-0-E3&y=99`)).toBe(true);
    expect(shouldGoBack(`/research/${ID2}`, `/research/${ID2}?at=c-0-E3&y=120`)).toBe(true);
  });

  it("검색 결과는 같은 기록 id 면, 기록 id 가 없으면 같은 검색어면 뒤로 간다", () => {
    expect(shouldGoBack(`/papers?q=nlp&h=${ID1}&at=p-C1&y=5`, `/papers?h=${ID1}&q=nlp&at=p-C1&y=5`)).toBe(true);
    expect(shouldGoBack(`/papers?q=nlp&h=${ID2}`, `/papers?h=${ID1}&q=nlp`)).toBe(false);
    expect(shouldGoBack("/papers?q=nlp", "/papers?q=nlp&at=p-C1&y=5")).toBe(true);
    expect(shouldGoBack("/papers?q=other", "/papers?q=nlp")).toBe(false);
  });

  it("직전 기록이 없거나 다른 화면(연관 논문 등)이면 뒤로 가지 않는다", () => {
    expect(shouldGoBack(null, `/research/${ID2}`)).toBe(false);
    expect(shouldGoBack(`/papers/CNTS-1?from=research&job=${ID2}`, `/research/${ID2}`)).toBe(false);
    expect(shouldGoBack(`/research/${ID1}`, `/research/${ID2}`)).toBe(false);
    expect(shouldGoBack(`/?h=${ID1}&q=경제`, "/")).toBe(false);
    expect(shouldGoBack("/", "/")).toBe(true);
  });
});

describe("앵커", () => {
  it("인용칩·제외 목록·검색 결과 앵커를 만들고 다시 읽는다", () => {
    expect(citeAnchor(2, "E3")).toBe("c-2-E3");
    expect(citeAnchor(2, "E3", 1)).toBe("c-2-E3-1");
    expect(excludedAnchor("KCI_FI001484593")).toBe("x-KCI_FI001484593");
    expect(resultAnchor("CNTS-00049204004")).toBe("p-CNTS-00049204004");
    expect(parseAnchor(citeAnchor(0, "E12", 2))).toEqual({ kind: "cite", section: 0, eid: "E12", n: 2 });
    expect(parseAnchor(citeAnchor(3, "E1"))).toEqual({ kind: "cite", section: 3, eid: "E1", n: 0 });
    expect(parseAnchor(excludedAnchor("C1"))).toEqual({ kind: "excluded", cnts: "C1" });
    expect(parseAnchor(resultAnchor("CNTS-1"))).toEqual({ kind: "result", cnts: "CNTS-1" });
  });

  it("문법 밖의 값은 null — 선택자에 따옴표·괄호·공백이 끼지 않는다", () => {
    for (const bad of ["", "c-01-E3", "c-1-X3", "c-1-E3-0", "q-C1", 'p-C1"]', "x-", "p-a b"]) {
      expect(parseAnchor(bad)).toBeNull();
      expect(anchorSelector(bad)).toBeNull();
    }
    expect(anchorSelector("c-1-E3-2")).toBe('[data-anchor="c-1-E3-2"]');
  });
});

describe("anchoredSection", () => {
  it("그리는 순서(도입 → 대표 논문 → 향후 과제)대로 같은 근거 칩에 순번을 붙인다", () => {
    const sec = section({
      intro: "앞 [E1] 가운데 [E2] 뒤 [E1]",
      papers: [{ cnts_id: "C1", summary: "요약", evidence: ["E1", "E3"] }],
      future: [{ text: "과제 [E3]", evidence: ["E3"] }],
    });
    const out = anchoredSection(sec, 4);
    expect(out.intro).toEqual([
      { type: "text", text: "앞 " },
      { type: "cite", eid: "E1", anchor: "c-4-E1" },
      { type: "text", text: " 가운데 " },
      { type: "cite", eid: "E2", anchor: "c-4-E2" },
      { type: "text", text: " 뒤 " },
      { type: "cite", eid: "E1", anchor: "c-4-E1-1" },
    ]);
    expect(out.papers).toEqual([
      {
        paper: sec.papers[0],
        chips: [
          { eid: "E1", anchor: "c-4-E1-2" },
          { eid: "E3", anchor: "c-4-E3" },
        ],
      },
    ]);
    expect(out.future).toEqual([
      [
        { type: "text", text: "과제 " },
        { type: "cite", eid: "E3", anchor: "c-4-E3-1" },
      ],
    ]);
  });

  it("도입이 비면 도입 조각이 없다", () => {
    expect(anchoredSection(section(), 0)).toEqual({ intro: [], papers: [], future: [] });
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/detailSource.test.ts`
Expected: FAIL — `Error: Cannot find module '~/utils/detailSource' imported from '…/tests/unit/detailSource.test.ts'.` · `Test Files  1 failed (1)` · `Tests  no tests`

- [ ] **Step 3: 구현** — `frontend/utils/detailSource.ts` (새 파일)

```ts
// frontend/utils/detailSource.ts
import type { ComputedRef, InjectionKey } from "vue";
import type { ReportPaper, ReportSection } from "~/types/research";
import { splitCitations } from "~/utils/citations";

// 논문 상세의 출처. 주소만으로 돌아갈 곳·사이드바 강조·배너·AI 요약 기준이 정해진다(새 탭·새로고침에도)
export type DetailSource =
  | { kind: "search"; h: string | null; q: string }
  | { kind: "research"; job: string; e: string | null }
  | { kind: "none" };

// 돌아가서 맞출 요소의 앵커와, 떠날 때 그 요소의 화면 높이(px). 픽셀 좌표가 아니라 요소 기준이라
// 배치(A/B)·창 크기가 바뀌어도 같은 자리를 찾는다
export interface ReturnSpot {
  at: string | null;
  y: number | null;
}

// n 은 같은 절에서 같은 근거 칩의 순번(0 부터, 0 은 앵커에 적지 않는다)
export type Anchor =
  | { kind: "cite"; section: number; eid: string; n: number }
  | { kind: "excluded"; cnts: string }
  | { kind: "result"; cnts: string };

export type AnchoredPart = { type: "text"; text: string } | { type: "cite"; eid: string; anchor: string };

export interface AnchoredSection {
  intro: AnchoredPart[];
  papers: Array<{ paper: ReportPaper; chips: Array<{ eid: string; anchor: string }> }>;
  future: AnchoredPart[][];
}

// 인용칩의 [논문 상세]가 돌아올 보고서의 잡 id — ReportView 가 내려 주고 칩이 받는다(절·본문 부품을 거치지 않게)
export const REPORT_JOB: InjectionKey<ComputedRef<string>> = Symbol("report-job");

// 서버 기록 id 는 브라우저 v4 · 잡 id v4 · v1 이전분 uuid5 가 섞여 있어 버전을 가리지 않는다
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const EID = /^E\d+$/;
const PIXELS = /^\d{1,6}$/;
// 앵커는 [data-anchor="…"] 선택자에 그대로 들어간다 — 따옴표·괄호·공백이 낄 수 없는 모양만 받는다
const CITE_ANCHOR = /^c-(0|[1-9]\d*)-(E\d+)(?:-([1-9]\d*))?$/;
const ITEM_ANCHOR = /^([xp])-([A-Za-z0-9_.-]{1,64})$/;
// 주소 비교용 기준 — 경로와 쿼리만 본다
const BASE = "http://local";

function firstValue(v: unknown): string | undefined {
  const s = Array.isArray(v) ? v[0] : v;
  return typeof s === "string" && s.trim() ? s.trim() : undefined;
}

export function isUuid(s: string): boolean {
  return UUID.test(s);
}

function idOf(v: unknown): string | null {
  const s = firstValue(v);
  return s && isUuid(s) ? s.toLowerCase() : null;
}

export function readDetailSource(query: Record<string, unknown>): DetailSource {
  const from = firstValue(query.from);
  if (from === "search") {
    const h = idOf(query.h);
    const q = firstValue(query.q) ?? "";
    return h || q ? { kind: "search", h, q } : { kind: "none" };
  }
  if (from === "research") {
    const job = idOf(query.job);
    const e = firstValue(query.e);
    return job ? { kind: "research", job, e: e && EID.test(e) ? e : null } : { kind: "none" };
  }
  return { kind: "none" };
}

// y 는 at 이 가리키는 요소의 높이라 at 없이는 쓰지 않는다
export function readReturnSpot(query: Record<string, unknown>): ReturnSpot {
  const raw = firstValue(query.at);
  const at = raw && parseAnchor(raw) ? raw : null;
  const y = firstValue(query.y);
  return { at, y: at && y && PIXELS.test(y) ? Number(y) : null };
}

function appendSpot(params: URLSearchParams, spot: ReturnSpot): void {
  if (!spot.at) return;
  params.set("at", spot.at);
  if (spot.y !== null) params.set("y", String(spot.y));
}

function withQuery(path: string, params: URLSearchParams): string {
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export function detailUrl(
  cntsId: string,
  source: DetailSource,
  spot?: ReturnSpot,
  extra: Record<string, string> = {},
): string {
  const params = new URLSearchParams();
  if (source.kind === "search") {
    params.set("from", "search");
    if (source.h) params.set("h", source.h);
    if (source.q) params.set("q", source.q);
  } else if (source.kind === "research") {
    params.set("from", "research");
    params.set("job", source.job);
    if (source.e) params.set("e", source.e);
  }
  if (spot) appendSpot(params, spot);
  for (const [key, value] of Object.entries(extra)) params.set(key, value);
  return withQuery(`/papers/${encodeURIComponent(cntsId)}`, params);
}

// 연관 논문으로 넘어가도 처음 출처와 돌아갈 자리를 잇는다 — 몇 편을 넘겨 봐도 [돌아가기]는 처음 화면의 그 자리로 간다.
// 인용 근거 번호(e)·관련도(score)는 처음 논문의 것이라 뗀다
export function relatedDetailUrl(cntsId: string, source: DetailSource, spot: ReturnSpot): string {
  return detailUrl(cntsId, source.kind === "research" ? { ...source, e: null } : source, spot);
}

// 보고서·탐색 타임라인의 "제외한 논문" 링크 — 인용한 근거가 아니라 e 가 없다
export function excludedDetailUrl(job: string, cnts: string, y: number | null = null): string {
  return detailUrl(cnts, { kind: "research", job, e: null }, { at: excludedAnchor(cnts), y });
}

export function backTarget(source: DetailSource, spot: ReturnSpot): { label: string; to: string } {
  const params = new URLSearchParams();
  switch (source.kind) {
    case "search":
      if (source.h) params.set("h", source.h);
      if (source.q) params.set("q", source.q);
      appendSpot(params, spot);
      return { label: "검색 결과로", to: withQuery("/papers", params) };
    case "research":
      appendSpot(params, spot);
      return { label: "딥리서치 보고서로", to: withQuery(`/research/${source.job}`, params) };
    case "none":
      return { label: "검색으로", to: "/" };
  }
}

// 직전 기록(vue-router 의 history.state.back)이 돌아갈 곳이면 router.back() 으로 브라우저 상태를 그대로 쓴다.
// 자리(at·y)는 견주지 않는다 — 떠날 때 출처 주소에 실어 둔 자리와 상세 주소의 자리는 같은 요소를 가리킨다
export function shouldGoBack(historyBack: string | null, to: string): boolean {
  if (!historyBack) return false;
  const back = new URL(historyBack, BASE);
  const target = new URL(to, BASE);
  if (back.pathname !== target.pathname) return false;
  const h = target.searchParams.get("h");
  if (h) return back.searchParams.get("h") === h;
  return back.searchParams.get("q") === target.searchParams.get("q");
}

export function citeAnchor(sectionIdx: number, eid: string, n = 0): string {
  return n ? `c-${sectionIdx}-${eid}-${n}` : `c-${sectionIdx}-${eid}`;
}

export function excludedAnchor(cnts: string): string {
  return `x-${cnts}`;
}

export function resultAnchor(cnts: string): string {
  return `p-${cnts}`;
}

export function parseAnchor(at: string): Anchor | null {
  const cite = CITE_ANCHOR.exec(at);
  if (cite) return { kind: "cite", section: Number(cite[1]), eid: cite[2]!, n: Number(cite[3] ?? 0) };
  const item = ITEM_ANCHOR.exec(at);
  if (!item) return null;
  return item[1] === "x" ? { kind: "excluded", cnts: item[2]! } : { kind: "result", cnts: item[2]! };
}

export function anchorSelector(at: string): string | null {
  return parseAnchor(at) ? `[data-anchor="${at}"]` : null;
}

// 한 절에 같은 근거 칩이 여러 번 나오면 그리는 순서(도입 → 대표 논문 → 향후 과제)대로 순번을 붙인다 —
// 돌아왔을 때 사용자가 누른 바로 그 칩을 찾는다
export function anchoredSection(sec: ReportSection, sectionIdx: number): AnchoredSection {
  const seen = new Map<string, number>();
  const anchorFor = (eid: string): string => {
    const n = seen.get(eid) ?? 0;
    seen.set(eid, n + 1);
    return citeAnchor(sectionIdx, eid, n);
  };
  const withAnchors = (text: string): AnchoredPart[] =>
    splitCitations(text).map((part) => (part.type === "cite" ? { ...part, anchor: anchorFor(part.eid) } : part));
  return {
    intro: sec.intro ? withAnchors(sec.intro) : [],
    papers: sec.papers.map((paper) => ({
      paper,
      chips: paper.evidence.map((eid) => ({ eid, anchor: anchorFor(eid) })),
    })),
    future: sec.future.map((f) => withAnchors(f.text)),
  };
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/detailSource.test.ts`
Expected: `Test Files  1 passed (1)` · `Tests  24 passed (24)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/utils/detailSource.ts frontend/tests/unit/detailSource.test.ts && git commit -m "[Feat] round05a — 논문 상세 주소 규칙(utils/detailSource): 출처(from=search·research)와 돌아갈 자리(at·y)를 읽고 쓰고, 연관 논문은 처음 출처와 자리를 이으며 e·score 를 뗀다. 돌아가기 대상(검색 결과로·딥리서치 보고서로·검색으로)과 직전 기록으로 뒤로 갈지 판단, 인용칩·제외 목록·결과 카드 앵커 문법과 절 안 칩 순번"
```

---

### Task 2: 사이드바가 상세의 출처를 따라 강조 (D5)

계약 추가: `activeKindForPath(path, query = {})`. 두 번째 인자를 받도록 시그니처를 넓힌다(기존 호출은 그대로 동작한다). `activeIdFor`는 시그니처가 그대로이고 규칙만 더한다. 상세의 `from=research&job=`은 딥리서치 탭과 그 잡을 강조한다. `from=search&h=`는 지금처럼 논문 탭과 h를 강조한다. 잡 id 모양이 틀리면 출처 없음으로 보고 논문 탭에 둔다. 기록·잡 id 모양 검사는 detailSource의 `isUuid` 하나로 모은다. 탭 제목(`useHead` "논문 제목 — 논문")은 Task 8이 맡는다.

선행: Task 1(`readDetailSource`·`isUuid`).

**Files:**
- Modify: `frontend/utils/historyRoute.ts`
- Modify: `frontend/components/AppSidebar.vue`
- Test: `frontend/tests/unit/historyRoute.test.ts`

- [ ] **Step 1: 실패 테스트 추가** — `frontend/tests/unit/historyRoute.test.ts` (Edit, CRLF 유지)

교체 전:
```ts
    expect(activeKindForPath("/papersX")).toBe("book");
  });
});
```
교체 후:
```ts
    expect(activeKindForPath("/papersX")).toBe("book");
  });

  it("보고서에서 온 상세는 딥리서치 탭, 검색에서 온 상세는 논문 탭이다 — 잡 id 모양이 틀리면 논문 탭", () => {
    expect(activeKindForPath("/papers/CNTS-2", { from: "research", job: ID1, e: "E3" })).toBe("research");
    expect(activeKindForPath("/papers/CNTS-2", { from: "search", h: ID2, q: "nlp" })).toBe("paper");
    expect(activeKindForPath("/papers/CNTS-2", { from: "research", job: "../admin" })).toBe("paper");
    expect(activeKindForPath("/papers", { from: "research", job: ID1 })).toBe("paper");
  });
});
```

교체 전:
```ts
    expect(activeIdFor("/", {})).toBeNull();
  });
});
```
교체 후:
```ts
    expect(activeIdFor("/", {})).toBeNull();
  });

  it("상세는 출처의 잡·기록을 강조한다 — 잡 id 는 소문자로 맞추고 모양이 틀리면 버린다", () => {
    expect(activeIdFor("/papers/CNTS-2", { from: "research", job: ID1, e: "E3" })).toBe(ID1);
    expect(activeIdFor("/papers/CNTS-2", { from: "research", job: MIXED })).toBe(MIXED.toLowerCase());
    expect(activeIdFor("/papers/CNTS-2", { from: "search", h: ID2, q: "nlp" })).toBe(ID2);
    expect(activeIdFor("/papers/CNTS-2", { from: "search", q: "nlp" })).toBeNull();
    expect(activeIdFor("/papers/CNTS-2", { from: "research", job: "nope" })).toBeNull();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/historyRoute.test.ts`
Expected: `Tests  2 failed | 12 passed (14)` — "보고서에서 온 상세는 딥리서치 탭…"(`expected 'paper' to be 'research'`), "상세는 출처의 잡·기록을 강조한다…"(`expected null to be '11111111-1111-4111-8111-111111111111'`)

- [ ] **Step 3: 구현** — `frontend/utils/historyRoute.ts` (Edit, CRLF 유지)

교체 전:
```ts
import type { HistoryEntry, HistoryKind } from "~/types/history";
```
교체 후:
```ts
import type { HistoryEntry, HistoryKind } from "~/types/history";
import { isUuid, readDetailSource } from "~/utils/detailSource";
```

교체 전:
```ts
// 서버 기록 id 는 브라우저 v4 · 잡 id v4 · v1 이전분 uuid5 가 섞여 있어 버전을 가리지 않는다
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const V1_ID = /^\d{10,16}$/;
```
교체 후:
```ts
const V1_ID = /^\d{10,16}$/;
```

교체 전:
```ts
  if (raw && UUID.test(raw)) out.h = raw.toLowerCase();
```
교체 후:
```ts
  if (raw && isUuid(raw)) out.h = raw.toLowerCase();
```

교체 전:
```ts
export function activeKindForPath(path: string): HistoryKind {
  if (path === "/research" || path.startsWith("/research/")) return "research";
  if (path === "/papers" || path.startsWith("/papers/")) return "paper";
  return "book";
}

export function activeIdFor(
  path: string,
  query: Record<string, unknown>,
  v1Map: Record<string, string> = {},
): string | null {
  const match = /^\/research\/([^/?#]+)/.exec(path);
  if (match) return decodeURIComponent(match[1]!);
  return readHistoryQuery(query, v1Map).h ?? null;
}
```
교체 후:
```ts
// 보고서에서 온 상세(from=research)는 그 보고서를 읽던 중으로 본다 — 사이드바가 딥리서치 탭과 그 보고서를 강조한다
export function activeKindForPath(path: string, query: Record<string, unknown> = {}): HistoryKind {
  if (path === "/research" || path.startsWith("/research/")) return "research";
  if (path.startsWith("/papers/") && readDetailSource(query).kind === "research") return "research";
  if (path === "/papers" || path.startsWith("/papers/")) return "paper";
  return "book";
}

export function activeIdFor(
  path: string,
  query: Record<string, unknown>,
  v1Map: Record<string, string> = {},
): string | null {
  const match = /^\/research\/([^/?#]+)/.exec(path);
  if (match) return decodeURIComponent(match[1]!);
  const source = path.startsWith("/papers/") ? readDetailSource(query) : null;
  if (source?.kind === "research") return source.job;
  return readHistoryQuery(query, v1Map).h ?? null;
}
```

- [ ] **Step 4: 사이드바 연결** — `frontend/components/AppSidebar.vue` (Edit, CRLF 유지)

사이드바는 페이지마다 새로 마운트되므로 첫 탭만 정하면 된다.

교체 전:
```ts
const historyTab = ref<HistoryKind>(activeKindForPath(route.path));
```
교체 후:
```ts
const historyTab = ref<HistoryKind>(activeKindForPath(route.path, route.query));
```

- [ ] **Step 5: 통과·타입 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/historyRoute.test.ts`
Expected: `Tests  14 passed (14)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: 실패 0건(누적 기대치 표의 Task 2 줄)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/utils/historyRoute.ts frontend/tests/unit/historyRoute.test.ts frontend/components/AppSidebar.vue && git commit -m "[Feat] round05a — 보고서에서 온 논문 상세(from=research&job=)는 사이드바가 딥리서치 탭과 그 보고서를 강조한다(검색에서 온 상세는 그대로 논문 탭과 그 기록, 잡 id 모양이 틀리면 논문 탭). 기록·잡 id 모양 검사는 detailSource 의 isUuid 하나로 모은다"
```

---

### Task 3: 보던 위치 복원 도구 (순수 계산 + composable)

계약 추가:
- `utils/restorePosition.ts`: `RESTORE_MAX_WAIT_MS`, `RESTORE_RETRY_MS`, `scrollDelta(elementTop, targetY)`, `targetTop(y, viewportHeight)`, `restoreStep(found, now, deadline)`, `type RestoreStep`, `spotOf(el, at)`, `isPlainClick(e)`, `type QueryValue`, `hasSpot`, `withSpot`, `withoutSpot`, `pageOfItem(ids, id, pageSize)`.
- `useRestorePosition(ready, opts?)`는 `{ pending, anchor }`를 돌려준다.
- `useDetailLeave(): { leave(url, spot) }`: 떠나기 전에 **출처 화면 주소에도 at·y를 `router.replace`로 실어 둔다**. 그래야 상세의 [돌아가기]가 `router.back()`을 고르거나 브라우저 뒤로 가기로 돌아와도 맞출 자리가 주소에 남는다. spec §7 ② 확인 항목을 위해 필요하다.
- `stampExcludedLink(e, job, cnts)`: 새 창으로 여는 제외 논문 링크에 누르는 순간의 높이를 싣는다.
- **화면 규약**: 이 composable을 쓰는 페이지는 `definePageMeta({ scrollToTop: (to) => !to.query.at })`를 둔다. Nuxt 기본 스크롤(`node_modules/nuxt/dist/pages/runtime/router.options.js`)은 page:loading:end 다음 프레임에 맨 위나 저장 위치로 움직이는데, 이것과 경합하지 않게 하기 위해서다.
- 맞출 때의 `scrollBy`·`scrollTo`는 `behavior: "instant"`로 쓴다. spec §4의 `behavior: 'auto'`는 "즉시"라는 뜻인데, `auto`는 CSS `scroll-behavior: smooth`가 붙으면 부드럽게 굴러간다. `instant`는 CSS와 상관없이 즉시 옮긴다.

선행: Task 1(`ReturnSpot`·앵커 함수·`excludedDetailUrl`).

**Files:**
- Create: `frontend/utils/restorePosition.ts`
- Create: `frontend/tests/unit/restorePosition.test.ts`
- Create: `frontend/composables/useRestorePosition.ts`

- [ ] **Step 1: 실패 테스트 작성** — `frontend/tests/unit/restorePosition.test.ts` (새 파일)

```ts
// frontend/tests/unit/restorePosition.test.ts
import { describe, expect, it } from "vitest";
import {
  hasSpot,
  isPlainClick,
  pageOfItem,
  restoreStep,
  scrollDelta,
  spotOf,
  targetTop,
  withSpot,
  withoutSpot,
} from "~/utils/restorePosition";

function click(over: Partial<Pick<MouseEvent, "button" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">> = {}) {
  return { button: 0, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...over };
}

describe("scrollDelta·targetTop", () => {
  it("요소를 목표 높이에 두려면 그 차이만큼 굴린다", () => {
    expect(scrollDelta(900, 240)).toBe(660);
    expect(scrollDelta(100, 240)).toBe(-140);
    expect(scrollDelta(240.6, 240)).toBe(1);
  });

  it("목표 높이는 떠날 때의 높이, 창이 줄었으면 요소가 보이는 데까지 올리고, 모르면 위쪽 1/3", () => {
    expect(targetTop(240, 800)).toBe(240);
    expect(targetTop(900, 600)).toBe(552);
    expect(targetTop(null, 900)).toBe(300);
  });
});

describe("restoreStep", () => {
  it("요소가 있으면 맞추고, 없으면 기한까지 다시 찾고, 넘기면 포기한다", () => {
    expect(restoreStep(true, 5000, 1000)).toBe("align");
    expect(restoreStep(false, 900, 1000)).toBe("retry");
    expect(restoreStep(false, 1000, 1000)).toBe("give-up");
  });
});

describe("주소의 자리", () => {
  it("자리를 싣거나 떼도 다른 쿼리는 그대로 두고 원본을 고치지 않는다", () => {
    const query = { q: "nlp", h: "id-1", at: "p-C0", y: "3" };
    expect(withSpot(query, { at: "p-C1", y: 120 })).toEqual({ q: "nlp", h: "id-1", at: "p-C1", y: "120" });
    expect(withoutSpot(query)).toEqual({ q: "nlp", h: "id-1" });
    expect(query).toEqual({ q: "nlp", h: "id-1", at: "p-C0", y: "3" });
  });

  it("y 를 모르면 at 만 싣는다", () => {
    expect(withSpot({}, { at: "x-C1", y: null })).toEqual({ at: "x-C1" });
  });

  it("at·y 중 하나라도 있으면 뗄 자리가 있다", () => {
    expect(hasSpot({ q: "nlp" })).toBe(false);
    expect(hasSpot({ at: "p-C1" })).toBe(true);
    expect(hasSpot({ y: "10" })).toBe(true);
  });
});

describe("spotOf", () => {
  it("누른 요소의 지금 화면 높이를 반올림해 싣고, 위로 넘친 요소는 0 으로 둔다", () => {
    expect(spotOf({ getBoundingClientRect: () => ({ top: 240.6 }) as DOMRect }, "c-0-E1")).toEqual({
      at: "c-0-E1",
      y: 241,
    });
    expect(spotOf({ getBoundingClientRect: () => ({ top: -12 }) as DOMRect }, "p-C1")).toEqual({ at: "p-C1", y: 0 });
  });
});

describe("isPlainClick", () => {
  it("수식 키 없는 왼쪽 클릭만 이 탭에서 옮긴다", () => {
    expect(isPlainClick(click())).toBe(true);
    expect(isPlainClick(click({ ctrlKey: true }))).toBe(false);
    expect(isPlainClick(click({ metaKey: true }))).toBe(false);
    expect(isPlainClick(click({ shiftKey: true }))).toBe(false);
    expect(isPlainClick(click({ button: 1 }))).toBe(false);
  });
});

describe("pageOfItem", () => {
  it("목록에서 그 항목이 있는 쪽(1부터)을 찾는다", () => {
    const ids = ["a", "b", "c", "d", "e"];
    expect(pageOfItem(ids, "a", 2)).toBe(1);
    expect(pageOfItem(ids, "d", 2)).toBe(2);
    expect(pageOfItem(ids, "e", 2)).toBe(3);
    expect(pageOfItem(ids, "z", 2)).toBeNull();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/restorePosition.test.ts`
Expected: FAIL — `Error: Cannot find module '~/utils/restorePosition' imported from '…/tests/unit/restorePosition.test.ts'.` · `Test Files  1 failed (1)` · `Tests  no tests`

- [ ] **Step 3: 순수 계산 구현** — `frontend/utils/restorePosition.ts` (새 파일)

```ts
// frontend/utils/restorePosition.ts
import type { ReturnSpot } from "~/utils/detailSource";

// 내용이 준비된 뒤에도 늦게 붙는 목록(탐색 타임라인의 이벤트 재생 등)을 이만큼 기다린다
export const RESTORE_MAX_WAIT_MS = 2000;
export const RESTORE_RETRY_MS = 100;
// 창이 줄어 떠날 때의 높이가 화면 밖이면 요소가 이만큼은 보이게 올린다
const KEEP_VISIBLE_PX = 48;

export type QueryValue = string | null | (string | null)[];
export type RestoreStep = "align" | "retry" | "give-up";

export function scrollDelta(elementTop: number, targetY: number): number {
  return Math.round(elementTop - targetY);
}

// 떠날 때 높이를 모르면(새 창 링크를 높이 없이 연 경우) 화면 위쪽 1/3 에 둔다
export function targetTop(y: number | null, viewportHeight: number): number {
  if (y === null) return Math.round(viewportHeight / 3);
  return Math.min(y, Math.max(0, viewportHeight - KEEP_VISIBLE_PX));
}

export function restoreStep(found: boolean, now: number, deadline: number): RestoreStep {
  if (found) return "align";
  return now < deadline ? "retry" : "give-up";
}

export function spotOf(el: Pick<Element, "getBoundingClientRect">, at: string): ReturnSpot {
  return { at, y: Math.max(0, Math.round(el.getBoundingClientRect().top)) };
}

// 새 창·새 탭으로 여는 클릭(수식 키·가운데 버튼)은 브라우저에 맡긴다
export function isPlainClick(e: Pick<MouseEvent, "button" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">): boolean {
  return e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey;
}

export function hasSpot(query: Readonly<Record<string, unknown>>): boolean {
  return "at" in query || "y" in query;
}

export function withoutSpot(query: Readonly<Record<string, QueryValue>>): Record<string, QueryValue> {
  const out = { ...query };
  delete out.at;
  delete out.y;
  return out;
}

export function withSpot(query: Readonly<Record<string, QueryValue>>, spot: ReturnSpot): Record<string, QueryValue> {
  const out = withoutSpot(query);
  if (spot.at) {
    out.at = spot.at;
    if (spot.y !== null) out.y = String(spot.y);
  }
  return out;
}

export function pageOfItem(ids: readonly string[], id: string, pageSize: number): number | null {
  const i = ids.indexOf(id);
  return i < 0 ? null : Math.floor(i / pageSize) + 1;
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/restorePosition.test.ts`
Expected: `Test Files  1 passed (1)` · `Tests  9 passed (9)`

- [ ] **Step 5: composable 구현** — `frontend/composables/useRestorePosition.ts` (새 파일)

```ts
// frontend/composables/useRestorePosition.ts
import { nextTick, onBeforeUnmount, onMounted, ref, watch, type ComputedRef, type Ref } from "vue";
import {
  anchorSelector,
  excludedAnchor,
  excludedDetailUrl,
  parseAnchor,
  readReturnSpot,
  type Anchor,
  type ReturnSpot,
} from "~/utils/detailSource";
import {
  RESTORE_MAX_WAIT_MS,
  RESTORE_RETRY_MS,
  hasSpot,
  restoreStep,
  scrollDelta,
  spotOf,
  targetTop,
  withSpot,
  withoutSpot,
} from "~/utils/restorePosition";

// 사용자가 먼저 움직이면 맞추지 않는다 — 읽기 시작한 화면을 끌고 가지 않게
const USER_MOVES = ["wheel", "touchstart", "keydown", "pointerdown"] as const;

/**
 * 상세에서 돌아온 화면(주소의 at·y)에서, 떠날 때 누른 요소를 같은 화면 높이에 즉시 맞춘다.
 * ready 는 그 요소가 든 내용(보고서·복원한 결과 목록)이 그려질 준비가 됐는지 — 화면이 정한다.
 * 쓰는 화면은 definePageMeta({ scrollToTop: (to) => !to.query.at }) 로 Nuxt 의 스크롤을 끈다
 */
export function useRestorePosition(
  ready: Ref<boolean> | ComputedRef<boolean>,
  opts: { maxWaitMs?: number } = {},
): { pending: Readonly<Ref<boolean>>; anchor: Anchor | null } {
  const route = useRoute();
  const router = useRouter();
  // 들어온 순간의 주소만 본다 — 이 화면을 떠나기 직전 주소에 at·y 를 다시 싣는데(useDetailLeave) 그때 맞추면 안 된다
  const spot = readReturnSpot(route.query);
  const selector = spot.at ? anchorSelector(spot.at) : null;
  const anchor = spot.at ? parseAnchor(spot.at) : null;
  const pending = ref(selector !== null);
  let deadline = 0;
  let scheduled = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  function stop(): void {
    if (timer) clearTimeout(timer);
    timer = null;
    for (const type of USER_MOVES) window.removeEventListener(type, finish, true);
  }

  function finish(): void {
    if (!pending.value) return;
    pending.value = false;
    stop();
    // 맞춘 뒤에는 주소에서 뗀다 — 새로고침·링크 복사에 옛 자리가 따라가지 않게
    if (hasSpot(route.query)) void router.replace({ query: withoutSpot(route.query) });
  }

  // 접힌 목록 안의 사본(display:none)은 높이가 없다 — 화면에 보이는 첫 요소를 고른다
  function visibleTarget(): HTMLElement | null {
    return (
      Array.from(document.querySelectorAll<HTMLElement>(selector!)).find((el) => el.getClientRects().length > 0) ?? null
    );
  }

  function tryAlign(): void {
    timer = null;
    if (!pending.value) return;
    const el = visibleTarget();
    switch (restoreStep(el !== null, Date.now(), deadline)) {
      case "retry":
        timer = setTimeout(tryAlign, RESTORE_RETRY_MS);
        return;
      case "align":
        window.scrollBy({
          top: scrollDelta(el!.getBoundingClientRect().top, targetTop(spot.y, window.innerHeight)),
          behavior: "instant",
        });
        // 인용칩은 초점을 돌려 주면 칩의 초점 열림으로 팝오버가 다시 열린다
        if (anchor?.kind === "cite") el!.focus({ preventScroll: true });
        break;
      case "give-up":
        // 보고서가 다른 시도로 바뀌었거나 결과가 바뀌어 요소가 없다 — 오류 없이 맨 위에 둔다
        break;
    }
    finish();
  }

  // 내용이 DOM 에 붙은 뒤(nextTick) 배치가 끝난 다음 프레임에 잰다. 기한은 내용이 준비된 때부터 센다 —
  // 늦게 붙는 목록은 기다리되 느린 응답 시간은 기한에 넣지 않는다
  function schedule(): void {
    if (!pending.value || scheduled) return;
    scheduled = true;
    deadline = Date.now() + (opts.maxWaitMs ?? RESTORE_MAX_WAIT_MS);
    void nextTick(() => requestAnimationFrame(tryAlign));
  }

  onMounted(() => {
    if (!pending.value) return;
    // Nuxt 가 맞추지 않으므로(scrollToTop) 내용을 기다리는 동안은 맨 위에 둔다
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    for (const type of USER_MOVES) window.addEventListener(type, finish, { capture: true, passive: true });
    watch(
      ready,
      (ok) => {
        if (ok) schedule();
      },
      { immediate: true },
    );
  });

  onBeforeUnmount(stop);

  return { pending, anchor };
}

/**
 * 상세로 떠날 때 이 화면 주소에도 자리(at·y)를 실어 둔다 — 상세의 [돌아가기]가 router.back() 을 고르거나
 * 브라우저 뒤로 가기로 돌아와도 그 기록의 주소에 맞출 자리가 남아 있다
 */
export function useDetailLeave(): { leave: (url: string, spot: ReturnSpot) => Promise<void> } {
  const route = useRoute();
  const router = useRouter();

  async function leave(url: string, spot: ReturnSpot): Promise<void> {
    await router.replace({ query: withSpot(route.query, spot) });
    await navigateTo(url);
  }

  return { leave };
}

// 새 창으로 여는 제외 논문 링크 — 이 화면은 그대로 두고, 누르는 순간의 항목 높이만 새 창 주소에 싣는다.
// 오른쪽 버튼(auxclick)에서도 실어 두면 메뉴의 "새 탭에서 열기"도 같은 자리를 받는다
export function stampExcludedLink(e: MouseEvent, job: string, cnts: string): void {
  const link = e.currentTarget as HTMLAnchorElement;
  link.href = excludedDetailUrl(job, cnts, spotOf(link, excludedAnchor(cnts)).y);
}
```

- [ ] **Step 6: 전체 테스트·타입 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: 실패 0건(누적 기대치 표의 Task 3 줄)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/utils/restorePosition.ts frontend/tests/unit/restorePosition.test.ts frontend/composables/useRestorePosition.ts && git commit -m "[Feat] round05a — 보던 위치 복원 도구: 돌아온 화면이 내용을 그린 뒤 떠날 때 누른 요소를 같은 화면 높이에 즉시 맞추고(인용칩은 초점까지 돌려 팝오버를 다시 연다) 주소에서 at·y 를 뗀다. 접힌 사본은 건너뛰고, 늦게 붙는 목록은 잠시 기다리며, 사용자가 먼저 움직이면 맞추지 않는다. 떠날 때는 이 화면 주소에도 자리를 실어 뒤로 가기로 돌아와도 같은 자리를 찾는다"
```

---

### Task 4: 딥리서치 보고서 — 떠날 때 링크와 돌아올 때 복원

계약 추가(props):
- CitationChip: `anchor: string`
- ReportSectionBody: `sectionIdx: number`
- ReportView: `jobId: string`, `revealExcluded?: string | null`
- ProgressPanel: `revealExcluded?: string | null`

`pages/research/[id].vue`에서 이 태스크가 고치는 곳은 네 군데다: ReportView 태그와 ProgressPanel 태그의 속성, import 한 줄, `shownReport` 바로 뒤의 블록. 같은 파일의 원문 보기 부분(`pdf`·`openPdf`)은 Task 11이 고친다.

선행: Task 1(`REPORT_JOB`·`detailUrl`·`excludedDetailUrl`·`excludedAnchor`·`anchoredSection`), Task 3(`useRestorePosition`·`useDetailLeave`·`stampExcludedLink`·`isPlainClick`·`spotOf`).

**Files:**
- Modify: `frontend/components/research/CitationChip.vue`
- Modify: `frontend/components/research/ReportSectionBody.vue`
- Modify: `frontend/components/research/ReportView.vue`
- Modify: `frontend/components/research/ProgressPanel.vue`
- Modify: `frontend/pages/research/[id].vue`

- [ ] **Step 1: CitationChip — 앵커와 [논문 상세] 링크** — `frontend/components/research/CitationChip.vue` (Edit, CRLF 유지)

교체 전:
```vue
      :aria-label="`근거 ${eid}: ${title}`"
      @click="togglePin"
    >
```
교체 후:
```vue
      :aria-label="`근거 ${eid}: ${title}`"
      :data-anchor="anchor"
      @click="togglePin"
    >
```

교체 전:
```vue
        <NuxtLink :to="`/papers/${evidence.cnts_id}`" class="rs-btn rs-btn--small rs-btn--ghost">논문 상세</NuxtLink>
```
교체 후:
```vue
        <!-- 누르는 순간의 칩 높이를 주소에 실어야 해서 NuxtLink 대신 직접 옮긴다 -->
        <a
          :href="detailHref(evidence.cnts_id, null)"
          class="rs-btn rs-btn--small rs-btn--ghost"
          @click="goDetail($event, evidence.cnts_id)"
          @auxclick="goDetail($event, evidence.cnts_id)"
        >논문 상세</a>
```

교체 전:
```ts
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import type { OpenPdfPayload, ReportChunk, ReportEvidence } from "~/types/research";
import { chunkListKey, citeLabel, metaLine, pageLabel, pdfPage } from "~/utils/citations";
import { hideOnPointerLeave, stepChunk } from "~/utils/researchReport";

const props = defineProps<{ eid: string; evidence?: ReportEvidence; chunks: ReportChunk[] }>();
```
교체 후:
```ts
import { computed, inject, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { OpenPdfPayload, ReportChunk, ReportEvidence } from "~/types/research";
import { chunkListKey, citeLabel, metaLine, pageLabel, pdfPage } from "~/utils/citations";
import { REPORT_JOB, detailUrl } from "~/utils/detailSource";
import { hideOnPointerLeave, stepChunk } from "~/utils/researchReport";
import { isPlainClick, spotOf } from "~/utils/restorePosition";

// anchor: 돌아왔을 때 이 칩을 다시 찾는 열쇠(같은 절의 같은 근거는 순번으로 가른다)
const props = defineProps<{ eid: string; anchor: string; evidence?: ReportEvidence; chunks: ReportChunk[] }>();
```

교체 전:
```ts
// 포인터가 칩·팝오버 위에 있는지 — 초점이 어디로도 옮겨 가지 않고 빠질 때 닫을지 가른다
let hovering = false;
```
교체 후:
```ts
// 포인터가 칩·팝오버 위에 있는지 — 초점이 어디로도 옮겨 가지 않고 빠질 때 닫을지 가른다
let hovering = false;
const reportJob = inject(REPORT_JOB)!;
const { leave } = useDetailLeave();
```

교체 전:
```ts
    page: current.value ? pdfPage(current.value) : undefined,
  });
}
```
교체 후:
```ts
    page: current.value ? pdfPage(current.value) : undefined,
  });
}

function detailHref(cnts: string, y: number | null): string {
  return detailUrl(cnts, { kind: "research", job: reportJob.value, e: props.eid }, { at: props.anchor, y });
}

// 누르는 순간의 칩 높이를 싣는다 — [딥리서치 보고서로]·뒤로 가기로 돌아오면 이 칩을 같은 화면 높이에 맞추고
// 초점을 돌려 팝오버를 다시 연다. 새 창·새 탭으로 여는 클릭은 브라우저에 맡기되 주소에는 같은 자리를 싣는다
function goDetail(e: MouseEvent, cnts: string): void {
  const spot = spotOf(chip.value!, props.anchor);
  const url = detailHref(cnts, spot.y);
  if (!isPlainClick(e)) {
    (e.currentTarget as HTMLAnchorElement).href = url;
    return;
  }
  e.preventDefault();
  void leave(url, spot);
}
```

- [ ] **Step 2: ReportSectionBody — 절 번호를 받아 칩마다 앵커** — `frontend/components/research/ReportSectionBody.vue` (Edit, CRLF 유지)

교체 전:
```vue
  <div class="rs-section__body">
    <p v-if="sec.intro" class="rs-section__intro">
      <template v-for="(part, pi) in splitCitations(sec.intro)" :key="pi">
        <template v-if="part.type === 'text'">{{ part.text }}</template>
        <CitationChip
          v-else
          :eid="part.eid"
          :evidence="evidence[part.eid]"
          :chunks="citeChunks(sec, evidence[part.eid], part.eid)"
          @open-pdf="$emit('open-pdf', $event)"
        />
      </template>
    </p>
    <p v-else class="rs-muted">{{ INTROLESS }}</p>

    <template v-if="sec.papers.length">
      <h4 class="rs-section__sub">대표 논문</h4>
      <ul class="rs-papers">
        <li v-for="p in sec.papers" :key="p.cnts_id" class="rs-paper">
          <span class="rs-paper__who">{{ paperByline(paperMeta(p)) }}</span>
          <span v-if="paperMeta(p)?.title" class="rs-paper__title">{{ paperMeta(p)?.title }}</span>
          <span class="rs-paper__summary">{{ p.summary || NO_SUMMARY }}</span>
          <CitationChip
            v-for="eid in p.evidence"
            :key="eid"
            :eid="eid"
            :evidence="evidence[eid]"
            :chunks="citeChunks(sec, evidence[eid], eid)"
            @open-pdf="$emit('open-pdf', $event)"
          />
        </li>
      </ul>
    </template>

    <template v-if="sec.future.length">
      <h4 class="rs-section__sub">향후 과제</h4>
      <ul class="rs-future">
        <li v-for="(f, fi) in sec.future" :key="fi">
          <template v-for="(part, pi) in splitCitations(f.text)" :key="pi">
            <template v-if="part.type === 'text'">{{ part.text }}</template>
            <CitationChip
              v-else
              :eid="part.eid"
              :evidence="evidence[part.eid]"
              :chunks="citeChunks(sec, evidence[part.eid], part.eid)"
              @open-pdf="$emit('open-pdf', $event)"
            />
          </template>
        </li>
      </ul>
    </template>
  </div>
```
교체 후:
```vue
  <div class="rs-section__body">
    <p v-if="sec.intro" class="rs-section__intro">
      <template v-for="(part, pi) in cites.intro" :key="pi">
        <template v-if="part.type === 'text'">{{ part.text }}</template>
        <CitationChip
          v-else
          :eid="part.eid"
          :anchor="part.anchor"
          :evidence="evidence[part.eid]"
          :chunks="citeChunks(sec, evidence[part.eid], part.eid)"
          @open-pdf="$emit('open-pdf', $event)"
        />
      </template>
    </p>
    <p v-else class="rs-muted">{{ INTROLESS }}</p>

    <template v-if="sec.papers.length">
      <h4 class="rs-section__sub">대표 논문</h4>
      <ul class="rs-papers">
        <li v-for="row in cites.papers" :key="row.paper.cnts_id" class="rs-paper">
          <span class="rs-paper__who">{{ paperByline(paperMeta(row.paper)) }}</span>
          <span v-if="paperMeta(row.paper)?.title" class="rs-paper__title">{{ paperMeta(row.paper)?.title }}</span>
          <span class="rs-paper__summary">{{ row.paper.summary || NO_SUMMARY }}</span>
          <CitationChip
            v-for="c in row.chips"
            :key="c.anchor"
            :eid="c.eid"
            :anchor="c.anchor"
            :evidence="evidence[c.eid]"
            :chunks="citeChunks(sec, evidence[c.eid], c.eid)"
            @open-pdf="$emit('open-pdf', $event)"
          />
        </li>
      </ul>
    </template>

    <template v-if="sec.future.length">
      <h4 class="rs-section__sub">향후 과제</h4>
      <ul class="rs-future">
        <li v-for="(parts, fi) in cites.future" :key="fi">
          <template v-for="(part, pi) in parts" :key="pi">
            <template v-if="part.type === 'text'">{{ part.text }}</template>
            <CitationChip
              v-else
              :eid="part.eid"
              :anchor="part.anchor"
              :evidence="evidence[part.eid]"
              :chunks="citeChunks(sec, evidence[part.eid], part.eid)"
              @open-pdf="$emit('open-pdf', $event)"
            />
          </template>
        </li>
      </ul>
    </template>
  </div>
```

교체 전:
```ts
import type { EvidenceMeta, OpenPdfPayload, ReportEvidence, ReportPaper, ReportSection } from "~/types/research";
import { citeChunks, splitCitations } from "~/utils/citations";
import { INTROLESS, NO_SUMMARY, paperByline } from "~/utils/researchReport";
import CitationChip from "./CitationChip.vue";

const props = defineProps<{ sec: ReportSection; evidence: Record<string, ReportEvidence> }>();
defineEmits<{ "open-pdf": [payload: OpenPdfPayload] }>();
```
교체 후:
```ts
import { computed } from "vue";
import type { EvidenceMeta, OpenPdfPayload, ReportEvidence, ReportPaper, ReportSection } from "~/types/research";
import { citeChunks } from "~/utils/citations";
import { anchoredSection } from "~/utils/detailSource";
import { INTROLESS, NO_SUMMARY, paperByline } from "~/utils/researchReport";
import CitationChip from "./CitationChip.vue";

// sectionIdx: 보고서에 보이는 절 번호(0부터) — 칩 앵커는 이 번호로 돌아올 자리를 찾는다
const props = defineProps<{ sec: ReportSection; sectionIdx: number; evidence: Record<string, ReportEvidence> }>();
defineEmits<{ "open-pdf": [payload: OpenPdfPayload] }>();

// 칩마다 돌아올 자리의 앵커를 붙인 본문 조각 — 같은 절의 같은 근거는 그리는 순서로 가른다
const cites = computed(() => anchoredSection(props.sec, props.sectionIdx));
```

- [ ] **Step 3: ReportView — 잡 id provide, 절 번호 전달, 제외 목록 링크, 접힌 목록 펼치기** — `frontend/components/research/ReportView.vue` (Edit, CRLF 유지)

교체 전:
```vue
      <ReportSectionBody v-if="row.sec" :sec="row.sec" :evidence="report.evidence" @open-pdf="$emit('open-pdf', $event)" />
```
교체 후:
```vue
      <ReportSectionBody
        v-if="row.sec"
        :sec="row.sec"
        :section-idx="row.idx"
        :evidence="report.evidence"
        @open-pdf="$emit('open-pdf', $event)"
      />
```

교체 전:
```vue
            <li v-for="p in g.papers" :key="p.cntsId">
              <a :href="`/papers/${p.cntsId}`" target="_blank" rel="noopener">
                {{ excludedPaperLine(p) }}<span class="rs-sr-only"> (새 창)</span>
              </a>
            </li>
```
교체 후:
```vue
            <li v-for="p in g.papers" :key="p.cntsId">
              <a
                :href="excludedDetailUrl(jobId, p.cntsId)"
                :data-anchor="excludedAnchor(p.cntsId)"
                target="_blank"
                rel="noopener"
                @click="stampExcludedLink($event, jobId, p.cntsId)"
                @auxclick="stampExcludedLink($event, jobId, p.cntsId)"
              >
                {{ excludedPaperLine(p) }}<span class="rs-sr-only"> (새 창)</span>
              </a>
            </li>
```

교체 전:
```ts
import { computed, ref } from "vue";
import type { OpenPdfPayload, ReportSection, ResearchReport } from "~/types/research";
```
교체 후:
```ts
import { computed, provide, ref, watch } from "vue";
import { stampExcludedLink } from "~/composables/useRestorePosition";
import type { OpenPdfPayload, ReportSection, ResearchReport } from "~/types/research";
import { REPORT_JOB, excludedAnchor, excludedDetailUrl } from "~/utils/detailSource";
```

교체 전:
```ts
  defineProps<{
    report: ResearchReport;
    generatedAt: string | null;
    draft?: { slots: DraftSlot[]; state: DraftState; excluded: ExcludedGroup[] } | null;
    highlightIdx?: number | null;
  }>(),
  { draft: null, highlightIdx: null },
);
defineEmits<{ "open-pdf": [payload: OpenPdfPayload]; "copy-link": [] }>();
```
교체 후:
```ts
  defineProps<{
    report: ResearchReport;
    jobId: string;
    generatedAt: string | null;
    draft?: { slots: DraftSlot[]; state: DraftState; excluded: ExcludedGroup[] } | null;
    highlightIdx?: number | null;
    // 새 창으로 연 제외 논문에서 돌아와 맞출 논문 — 접힌 목록을 펼쳐 둬야 그 항목의 자리가 생긴다
    revealExcluded?: string | null;
  }>(),
  { draft: null, highlightIdx: null, revealExcluded: null },
);
defineEmits<{ "open-pdf": [payload: OpenPdfPayload]; "copy-link": [] }>();

// 인용칩의 [논문 상세]가 이 보고서로 돌아올 주소를 만든다 — 절·본문 부품을 거치지 않고 칩이 받는다
provide(REPORT_JOB, computed(() => props.jobId));
```

교체 전:
```ts
// 초안이 같은 자리에서 최종본으로 바뀌어도 이 부품은 그대로라 펼친 상태가 이어진다
const excludedOpen = ref(false);
```
교체 후:
```ts
// 초안이 같은 자리에서 최종본으로 바뀌어도 이 부품은 그대로라 펼친 상태가 이어진다
const excludedOpen = ref(false);

// 맞출 논문이 든 접힌 목록을 펼친다. 초안이 같은 자리에서 최종본으로 바뀌면 목록도 바뀌므로 목록이 바뀔 때도
// 다시 본다 — 맞추고 나면 화면이 revealExcluded 를 비워 사용자가 접은 목록을 다시 펼치지 않는다
watch(
  [() => props.revealExcluded, excluded],
  ([cnts, groups]) => {
    if (cnts && groups.some((g) => g.papers.some((p) => p.cntsId === cnts))) excludedOpen.value = true;
  },
  { immediate: true },
);
```

- [ ] **Step 4: ProgressPanel — 제외 링크와 회차 펼치기** — `frontend/components/research/ProgressPanel.vue` (Edit, CRLF 유지)

교체 전:
```vue
                  <li v-for="p in r.excludedPapers" :key="p.cntsId">
                    <a :href="`/papers/${p.cntsId}`" target="_blank" rel="noopener">
                      {{ excludedPaperLine(p) }}<span class="rs-sr-only"> (새 창)</span>
                    </a>
                  </li>
```
교체 후:
```vue
                  <li v-for="p in r.excludedPapers" :key="p.cntsId">
                    <a
                      :href="excludedDetailUrl(view.jobId, p.cntsId)"
                      :data-anchor="excludedAnchor(p.cntsId)"
                      target="_blank"
                      rel="noopener"
                      @click="stampExcludedLink($event, view.jobId, p.cntsId)"
                      @auxclick="stampExcludedLink($event, view.jobId, p.cntsId)"
                    >
                      {{ excludedPaperLine(p) }}<span class="rs-sr-only"> (새 창)</span>
                    </a>
                  </li>
```

교체 전:
```ts
import { computed, shallowRef, useId } from "vue";
import type { ResearchView } from "~/types/research";
```
교체 후:
```ts
import { computed, shallowRef, useId, watch } from "vue";
import { stampExcludedLink } from "~/composables/useRestorePosition";
import type { ResearchView } from "~/types/research";
import { excludedAnchor, excludedDetailUrl } from "~/utils/detailSource";
```

교체 전:
```ts
const props = defineProps<{ view: ResearchView; phase: ResearchPhase }>();
```
교체 후:
```ts
// revealExcluded: 새 창으로 연 제외 논문에서 돌아와 맞출 논문 — 그 논문을 뺀 회차를 펼쳐 둬야 자리가 생긴다
const props = defineProps<{ view: ResearchView; phase: ResearchPhase; revealExcluded?: string | null }>();
```

교체 전:
```ts
function panelId(subqIdx: number, round: number): string {
  return `${uid}-excluded-${subqIdx}-${round}`;
}
```
교체 후:
```ts
function panelId(subqIdx: number, round: number): string {
  return `${uid}-excluded-${subqIdx}-${round}`;
}

// 타임라인은 이벤트를 다시 받으며 늦게 채워질 수 있어 회차 목록이 바뀔 때도 다시 본다 —
// 맞추고 나면 화면이 revealExcluded 를 비워 사용자가 접은 회차를 다시 펼치지 않는다
watch(
  [() => props.revealExcluded, () => props.view.subqs],
  ([cnts, subqs]) => {
    if (!cnts) return;
    const keys = subqs.flatMap((sq) =>
      sq.rounds.filter((r) => r.excludedPapers.some((p) => p.cntsId === cnts)).map((r) => roundKey(sq.idx, r.round)),
    );
    if (keys.length) openRounds.value = new Set([...openRounds.value, ...keys]);
  },
  { immediate: true },
);
```

- [ ] **Step 5: research/[id].vue — 잡 id·펼칠 논문 전달, 돌아올 때 복원** — `frontend/pages/research/[id].vue` (Edit, CRLF 유지)

교체 전:
```vue
                <ReportView
                  :report="shownReport"
                  :generated-at="reportState === 'ready' ? view.finishedAt : null"
                  :draft="draftMode"
                  :highlight-idx="linkedIdx"
                  @open-pdf="openPdf"
```
교체 후:
```vue
                <ReportView
                  :report="shownReport"
                  :job-id="view.jobId"
                  :generated-at="reportState === 'ready' ? view.finishedAt : null"
                  :draft="draftMode"
                  :highlight-idx="linkedIdx"
                  :reveal-excluded="revealExcluded"
                  @open-pdf="openPdf"
```

교체 전:
```vue
            <ProgressPanel :view="view" :phase="phase" />
```
교체 후:
```vue
            <ProgressPanel :view="view" :phase="phase" :reveal-excluded="revealExcluded" />
```

교체 전:
```ts
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
```
교체 후:
```ts
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
import { useRestorePosition } from "~/composables/useRestorePosition";
```

교체 전:
```ts
const shownReport = computed(() => (reportState.value === "ready" ? view.value?.report : draft.value?.report) ?? null);
```
교체 후:
```ts
const shownReport = computed(() => (reportState.value === "ready" ? view.value?.report : draft.value?.report) ?? null);

// ── 상세에서 돌아온 자리 ──────────────────────────────────
// 보고서는 비동기로 다시 그려 브라우저·Nuxt 의 스크롤 복원이 내용보다 먼저 끝난다 — 돌아온 주소(at)면 Nuxt 는
// 맞추지 않고, 누른 칩·항목을 내용이 그려진 뒤 직접 맞춘다. 완료된 연구는 최종본을 받은 뒤에 맞춘다 —
// 초안 위에서 맞추면 서론·한계가 붙는 순간 자리가 밀린다
definePageMeta({ scrollToTop: (to) => !to.query.at });
const restoreReady = computed(() => !!view.value && !!phase.value && reportState.value !== "loading");
const restore = useRestorePosition(restoreReady);
// 맞추는 동안만 알린다 — 다 맞춘 뒤 사용자가 접은 목록을 다시 펼치지 않게
const revealExcluded = computed(() =>
  restore.pending.value && restore.anchor?.kind === "excluded" ? restore.anchor.cnts : null,
);
```

- [ ] **Step 6: 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: 실패 0건(이 태스크는 테스트 수를 바꾸지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && grep -rn 'papers/\${' components/research`
Expected: 출력 없음(앵커·출처가 빠진 상세 링크가 남지 않음)

- [ ] **Step 7: 화면 확인(선택, `frontend-prod-api` 미리보기)**

- 보고서 중간의 인용칩 → [논문 상세]: 주소가 `/papers/<id>?from=research&job=…&e=E#&at=c-…&y=…`이어야 한다.
- 거기서 브라우저 뒤로 가기: 같은 칩이 같은 높이에 오고 팝오버가 열린 뒤, 주소에서 at·y가 빠져야 한다(spec §7 ②).
- 제외 논문 링크를 새 탭으로 열면 주소에 `at=x-…&y=…`가 있어야 한다.
- [딥리서치 보고서로]를 쓰는 ①③④ 흐름은 Task 8이 들어간 뒤 확인한다.

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/components/research/CitationChip.vue frontend/components/research/ReportSectionBody.vue frontend/components/research/ReportView.vue frontend/components/research/ProgressPanel.vue "frontend/pages/research/[id].vue" && git commit -m "[Feat] round05a — 딥리서치 보고서에서 논문 상세로 갈 때 출처와 자리를 싣고 돌아오면 그 자리로: 인용칩 [논문 상세]·제외한 논문 링크(보고서·탐색 타임라인)에 잡·근거 번호와 누른 칩·항목의 앵커·화면 높이를 싣고, 보고서로 돌아오면 최종본이 그려진 뒤 같은 칩을 같은 높이에 맞춰 팝오버를 다시 연다. 접힌 제외 목록·회차는 맞추는 동안 펼친다"
```

---

### Task 5: 논문 검색 결과 — 카드 링크·앵커와 돌아올 때 복원

참고: `pages/index.vue`의 논문 분기(`openDetail`·`openDetailWithChat`)는 지금 실행될 수 없는 코드다. 결과 화면의 `mode`는 항상 book이고, 논문 검색은 `/papers`로 넘어가며, `papers.value`는 빈 배열만 들어간다. 그래서 여기서는 주소 형식만 같은 규칙으로 맞추고 앵커·복원은 달지 않는다. spec §7 ⑥(메인 논문 탭)의 실제 흐름은 `/` → `/papers` → 카드이므로 이 태스크의 `pages/papers/index.vue`가 그 흐름을 맡는다.

선행: Task 1(`detailUrl`·`resultAnchor`·`ReturnSpot`), Task 3(`useRestorePosition`·`useDetailLeave`·`pageOfItem`·`spotOf`).

**Files:**
- Modify: `frontend/pages/papers/index.vue`
- Modify: `frontend/pages/index.vue`

- [ ] **Step 1: papers/index.vue 템플릿** — `frontend/pages/papers/index.vue` (Edit, CRLF 유지)

교체 전:
```vue
                        @click="navigateTo(detailUrl(ref.book_id))"
```
교체 후:
```vue
                        @click="navigateTo(paperDetailUrl(ref.book_id))"
```

교체 전:
```vue
              <article
                v-for="paper in pagedPapers"
                :key="paper.book_id"
                class="skx-paper-item"
              >
```
교체 후:
```vue
              <article
                v-for="paper in pagedPapers"
                :key="paper.book_id"
                class="skx-paper-item"
                :data-anchor="resultAnchor(paper.book_id)"
              >
```

교체 전:
```vue
                    @click="goToDetail(paper)"
```
교체 후:
```vue
                    @click="goToDetail(paper, $event)"
```

교체 전:
```vue
                    @click.stop="navigateTo(detailUrl(paper.book_id, { chat: '1' }))"
```
교체 후:
```vue
                    @click.stop="goToDetail(paper, $event, { chat: '1' })"
```

- [ ] **Step 2: papers/index.vue 스크립트** — `frontend/pages/papers/index.vue` (Edit, CRLF 유지)

교체 전:
```ts
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { slimPaperResult } from "~/utils/historySnapshot";
```
교체 후:
```ts
import { useHistory } from "~/composables/useHistory";
import { useDetailLeave, useRestorePosition } from "~/composables/useRestorePosition";
import { safeLocalStorage } from "~/utils/browserId";
import { detailUrl, resultAnchor, type ReturnSpot } from "~/utils/detailSource";
import { slimPaperResult } from "~/utils/historySnapshot";
import { pageOfItem, spotOf } from "~/utils/restorePosition";
```

교체 전:
```ts
const loading = ref(false);
const error = ref<string | null>(null);
const paperResult = ref<BookSearchResponse | null>(null);
```
교체 후:
```ts
const loading = ref(false);
const error = ref<string | null>(null);
const paperResult = ref<BookSearchResponse | null>(null);

// ── 상세에서 돌아온 자리 ──────────────────────────────────────
// 결과는 기록에서 비동기로 복원해 브라우저·Nuxt 의 스크롤 복원이 목록보다 먼저 끝난다 — 돌아온 주소(at)면
// Nuxt 는 맞추지 않고, 누른 카드를 목록이 그려진 뒤 직접 맞춘다
definePageMeta({ scrollToTop: (to) => !to.query.at });
const restore = useRestorePosition(computed(() => paperResult.value !== null && !loading.value));
const { leave } = useDetailLeave();
```

교체 전:
```ts
// 상세로 갈 때 기록 id 를 넘긴다 — 상세에서도 사이드바가 이 기록을 강조하고, 뒤로가기가 재검색 없이 복원된다
function detailUrl(bookId: string, extra: Record<string, string> = {}): string {
  // q 는 검색바가 아니라 화면 결과의 검색어다 — 함께 넘기는 h 와 같은 검색을 가리키게
  const params = new URLSearchParams({ q: resultQuery.value, ...extra });
  if (currentHistoryId.value) params.set("h", currentHistoryId.value);
  return `/papers/${bookId}?${params}`;
}

function goToDetail(paper: any) {
  navigateTo(detailUrl(paper.book_id));
}
```
교체 후:
```ts
// 상세로 갈 때 출처(이 검색 기록)를 넘긴다 — 상세에서도 사이드바가 이 기록을 강조하고, [검색 결과로]가 재검색 없이
// 복원된다. q 는 검색바가 아니라 화면 결과의 검색어다(함께 넘기는 h 와 같은 검색). 관련도는 상세 머리 카드가 보인다
function paperDetailUrl(bookId: string, spot?: ReturnSpot, extra: Record<string, string> = {}): string {
  const score = aiRefPaperMap.value.get(bookId)?.best_score;
  return detailUrl(
    bookId,
    { kind: "search", h: currentHistoryId.value, q: resultQuery.value },
    spot,
    score === undefined ? extra : { score: String(score), ...extra },
  );
}

// 누른 카드의 지금 화면 높이를 싣고 떠난다 — [검색 결과로]·뒤로 가기로 돌아오면 이 카드를 같은 높이에 맞춘다
function goToDetail(paper: BookChunkGroup, e: MouseEvent, extra: Record<string, string> = {}) {
  const card = (e.currentTarget as HTMLElement).closest<HTMLElement>("[data-anchor]")!;
  const spot = spotOf(card, resultAnchor(paper.book_id));
  void leave(paperDetailUrl(paper.book_id, spot, extra), spot);
}
```

교체 전:
```ts
  aiExpanded.value = true;
  currentPage.value = 1;
  sortBy.value = "relevance";
  selectedGrade.value = grade || "all";
```
교체 후:
```ts
  aiExpanded.value = true;
  sortBy.value = "relevance";
  selectedGrade.value = grade || "all";
  // 정렬·필터를 정한 뒤에 찾아야 화면 목록과 같은 순서다
  currentPage.value = returnPage();
```

교체 전:
```ts
// ── AI 요약 SSE ───────────────────────────────────────────────
type SummarySource = {
```
교체 후:
```ts
// 상세에서 돌아왔으면 그 카드가 있는 쪽을 연다 — 첫 쪽만 열면 다음 쪽에서 누른 카드의 자리를 찾지 못한다.
// 쪽 크기·정렬은 기록에 없어 기본값으로 찾는다
function returnPage(): number {
  const anchor = restore.pending.value ? restore.anchor : null;
  if (anchor?.kind !== "result") return 1;
  return pageOfItem(filteredPapers.value.map((p) => p.book_id), anchor.cnts, pageSize.value) ?? 1;
}

// ── AI 요약 SSE ───────────────────────────────────────────────
type SummarySource = {
```

교체 전:
```ts
watch(currentPage, () => window.scrollTo({ top: 0, behavior: "smooth" }));
```
교체 후:
```ts
// 돌아온 카드의 쪽을 여는 동안에는 맨 위로 올리지 않는다 — 그 카드 자리를 맞추는 중이다
watch(currentPage, () => {
  if (!restore.pending.value) window.scrollTo({ top: 0, behavior: "smooth" });
});
```

- [ ] **Step 3: pages/index.vue 논문 분기 주소 규칙** — `frontend/pages/index.vue` (Edit, CRLF 유지)

교체 전:
```ts
import { awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import type { BookChunkGroup } from "~/types/search";
import type { BookEntry, BookSnapshot } from "~/types/history";
```
교체 후:
```ts
import { awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import { detailUrl } from "~/utils/detailSource";
import type { BookChunkGroup } from "~/types/search";
import type { BookEntry, BookSnapshot } from "~/types/history";
```

교체 전:
```ts
function openDetail(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(
      `/papers/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}`,
    );
    return;
  }
```
교체 후:
```ts
// 논문 상세의 출처는 결과의 검색어로 싣는다(입력창 글자가 아니다). 이 화면의 기록은 도서 기록이라 h 로 싣지 않는다 —
// [검색 결과로]가 논문 검색에서 같은 검색어로 다시 찾는다
function paperDetailUrl(bookId: string, extra: Record<string, string> = {}): string {
  return detailUrl(bookId, { kind: "search", h: null, q: resultQuery.value }, undefined, extra);
}

function openDetail(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(paperDetailUrl(item.book_id));
    return;
  }
```

교체 전:
```ts
function openDetailWithChat(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(
      `/papers/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}&chat=1`,
    );
    return;
  }
```
교체 후:
```ts
function openDetailWithChat(item: BookChunkGroup) {
  if (mode.value === "paper") {
    navigateTo(paperDetailUrl(item.book_id, { chat: "1" }));
    return;
  }
```

- [ ] **Step 4: 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: 실패 0건(이 태스크는 테스트 수를 바꾸지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run(상세 주소를 손으로 이어 붙이는 곳이 남지 않았는지 — 백틱으로 시작하는 `/papers/${` 템플릿 문자열만 찾는다. `${apiBase}/papers/…` API 주소는 걸리지 않는다):
```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && grep -n '`/papers/\${' pages/index.vue pages/papers/index.vue
```
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && git diff d7f7e95..HEAD --stat -- app`
Expected: 출력 없음(백엔드 변경 없음)

- [ ] **Step 5: 화면 확인(선택, `frontend-prod-api`)**

- 검색 결과 둘째 쪽 중간의 카드 → 상세: 주소에 `from=search&h=…&q=…&at=p-…&y=…&score=…`가 있어야 한다.
- 브라우저 뒤로 가기: 재검색(`/papers/search` 요청) 없이 둘째 쪽이 열리고, 그 카드가 같은 높이에 오고, 주소에서 at·y가 빠져야 한다.
- 사이드바는 논문 탭과 그 기록을 강조해야 한다.

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/pages/papers/index.vue frontend/pages/index.vue && git commit -m "[Feat] round05a — 논문 검색 결과에서 상세로 갈 때 출처(from=search·기록 h·결과 검색어 q)와 관련도, 누른 카드의 앵커·화면 높이를 싣고, 돌아오면 재검색 없이 그 카드가 있는 쪽을 열어 같은 높이에 맞춘다(맞추는 동안은 쪽 바꿈 맨 위 이동을 멈춘다). 메인 화면 논문 분기도 같은 주소 규칙을 쓴다"
```

---

## 단계 2 — 03 논문 상세 화면 (Task 6~9)

- 범위는 spec §5 ①②③⑤⑥⑦, ④의 이름(DeepRead), D6(캐시)·D7(배너·기준 질문)이다. ④의 원문 보기 통일과 배너의 [인용 대목 보기]는 단계 3 의 Task 11 이 맡는다.
- Task 6·7 은 순수 로직(테스트 먼저)이고, Task 8·9 가 상세 페이지에 붙인다.

### Task 6: AI 요약·연관 이유 캐시 규칙 (D6)

계약 추가:
- `frontend/utils/aiCache.ts`
  - `summaryCacheKey(paperId: string, question: string): string`
  - `relatedCacheKey(paperId: string, relatedId: string): string`
  - `readAiCache(storage: Storage | null, key: string): string | null`
  - `writeAiCache(storage: Storage | null, key: string, text: string): void`
- `frontend/utils/browserId.ts`
  - `safeSessionStorage(): Storage | null`

**Files:**
- Create: `frontend/utils/aiCache.ts`
- Modify: `frontend/utils/browserId.ts`
- Test: `frontend/tests/unit/aiCache.test.ts` (새 파일)
- Test: `frontend/tests/unit/browserId.test.ts`

- [ ] **Step 1: 실패 테스트 작성 (1/2)** — `frontend/tests/unit/aiCache.test.ts` (새 파일)

```ts
// frontend/tests/unit/aiCache.test.ts
import { describe, expect, it } from "vitest";
import { readAiCache, relatedCacheKey, summaryCacheKey, writeAiCache } from "~/utils/aiCache";
import { MemoryStorage } from "./helpers/memoryStorage";

describe("캐시 키", () => {
  it("AI 요약은 논문과 기준 질문으로, 연관 이유는 두 논문으로 가른다", () => {
    expect(summaryCacheKey("CNTS-1", "딥러닝")).not.toBe(summaryCacheKey("CNTS-1", "자연어"));
    expect(summaryCacheKey("CNTS-1", "딥러닝")).not.toBe(summaryCacheKey("CNTS-2", "딥러닝"));
    expect(relatedCacheKey("CNTS-1", "CNTS-2")).not.toBe(relatedCacheKey("CNTS-2", "CNTS-1"));
    expect(summaryCacheKey("CNTS-1", "CNTS-2")).not.toBe(relatedCacheKey("CNTS-1", "CNTS-2"));
  });
});

describe("readAiCache·writeAiCache", () => {
  it("쓴 글을 같은 키로 다시 읽는다", () => {
    const s = new MemoryStorage();
    const key = summaryCacheKey("CNTS-1", "딥러닝");
    writeAiCache(s, key, "핵심 요약");
    expect(readAiCache(s, key)).toBe("핵심 요약");
    expect(readAiCache(s, summaryCacheKey("CNTS-1", "자연어"))).toBeNull();
  });

  it("빈 글과 서버가 보낸 생성 실패 문구는 담지 않는다", () => {
    const s = new MemoryStorage();
    writeAiCache(s, "k1", "  ");
    writeAiCache(s, "k2", "앞부분 요약 분석 생성 중 오류가 발생했습니다.");
    expect(s.length).toBe(0);
  });

  it("용량 초과·막힌 저장소·저장소 없음은 조용히 넘긴다", () => {
    const small = new MemoryStorage(10);
    expect(() => writeAiCache(small, "key", "아주 긴 요약 글입니다")).not.toThrow();
    expect(readAiCache(small, "key")).toBeNull();
    const blocked = new MemoryStorage();
    blocked.failWith = new Error("SecurityError");
    expect(() => writeAiCache(blocked, "key", "요약")).not.toThrow();
    expect(() => writeAiCache(null, "key", "요약")).not.toThrow();
    expect(readAiCache(null, "key")).toBeNull();
  });

  it("읽기가 막혀도 null 이다", () => {
    const broken = {
      getItem: () => {
        throw new Error("SecurityError");
      },
    } as unknown as Storage;
    expect(readAiCache(broken, "key")).toBeNull();
  });
});
```

- [ ] **Step 2: 실패 테스트 작성 (2/2)** — `frontend/tests/unit/browserId.test.ts` (Edit, CRLF 유지)

교체 전:
```ts
  readOrCreateBrowserId,
  safeLocalStorage,
} from "~/utils/browserId";
```
교체 후:
```ts
  readOrCreateBrowserId,
  safeLocalStorage,
  safeSessionStorage,
} from "~/utils/browserId";
```

교체 전:
```ts
describe("safeLocalStorage", () => {
  it("window 가 없는 서버 렌더에서는 null", () => {
    expect(safeLocalStorage()).toBeNull();
  });
});
```
교체 후:
```ts
describe("safeLocalStorage", () => {
  it("window 가 없는 서버 렌더에서는 null", () => {
    expect(safeLocalStorage()).toBeNull();
  });
});

describe("safeSessionStorage", () => {
  it("window 가 없는 서버 렌더에서는 null", () => {
    expect(safeSessionStorage()).toBeNull();
  });
});
```

- [ ] **Step 3: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/aiCache.test.ts tests/unit/browserId.test.ts`
Expected:
- `aiCache.test.ts` 는 `Error: Cannot find module '~/utils/aiCache' imported from '…/tests/unit/aiCache.test.ts'.` 로 파일 전체가 실패한다.
- `browserId.test.ts` 는 `TypeError: (0 , safeSessionStorage) is not a function` 으로 1건 실패한다.
- 합계 `Test Files  2 failed (2)` · `Tests  1 failed | 11 passed (12)`

- [ ] **Step 4: 최소 구현 (1/2)** — `frontend/utils/aiCache.ts` (새 파일)

```ts
// frontend/utils/aiCache.ts
// 논문 상세의 AI 요약·연관 이유를 탭 안에서 다시 쓴다 — 상세를 오갈 때마다 같은 글을 GPU 로 다시 만들지 않게.
// sessionStorage 라 탭을 닫으면 사라진다. 막힌 저장소·용량 초과는 캐시 없이 새로 만들 뿐이다
const PREFIX = "skx:ai:";
// 서버(services/search/paper_summary)는 생성 실패를 글로 보내고 스트림을 정상으로 닫는다 —
// 담아 두면 탭을 닫을 때까지 실패 문구만 다시 보인다
const FAILED_TAIL = /오류가 발생했습니다\.?\s*$/;

export function summaryCacheKey(paperId: string, question: string): string {
  return `${PREFIX}summary:${paperId}:${question}`;
}

export function relatedCacheKey(paperId: string, relatedId: string): string {
  return `${PREFIX}related:${paperId}:${relatedId}`;
}

export function readAiCache(storage: Storage | null, key: string): string | null {
  try {
    return storage?.getItem(key) || null;
  } catch {
    return null;
  }
}

export function writeAiCache(storage: Storage | null, key: string, text: string): void {
  if (!text.trim() || FAILED_TAIL.test(text)) return;
  try {
    storage?.setItem(key, text);
  } catch {
    // 용량 초과·막힌 저장소 — 다음에 다시 만든다
  }
}
```

- [ ] **Step 5: 최소 구현 (2/2)** — `frontend/utils/browserId.ts` (Edit, CRLF 유지)

교체 전:
```ts
export function safeLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}
```
교체 후:
```ts
export function safeLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

// 탭 하나에서만 쓰는 캐시용(논문 상세의 AI 글) — 서버 렌더·막힌 저장소에서는 null
export function safeSessionStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}
```

- [ ] **Step 6: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/aiCache.test.ts tests/unit/browserId.test.ts`
Expected: `Test Files  2 passed (2)` · `Tests  17 passed (17)`(`aiCache` 5건, `browserId` 12건)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/utils/aiCache.ts frontend/utils/browserId.ts frontend/tests/unit/aiCache.test.ts frontend/tests/unit/browserId.test.ts && git commit -m "[Feat] round05a — 논문 상세의 AI 요약·연관 이유를 탭 안에 캐시하는 규칙: 키는 논문+기준 질문(연관 이유는 두 논문), 빈 글·서버의 생성 실패 문구는 담지 않고 막힌 저장소·용량 초과는 무시한다"
```

---

### Task 7: 인용 맥락 배너와 AI 요약 기준 질문 규칙 (D7)

선행: Task 1(`DetailSource` 타입). 여기서는 타입만 가져다 쓴다.

계약 추가 (`frontend/utils/paperDetail.ts`):
- `interface CiteContext { question: string; label: string; chunks: ReportChunk[] }` — `chunks` 는 그 근거의 인용 대목 전부를 쪽 순으로(쪽 정보가 없는 대목은 빼지 않고 뒤에) 둔다. 배너의 "인용 대목 N곳"은 `chunks.length`, [인용 대목 보기]는 Task 11 에서 `citedPdfTarget(…, cite.chunks)` 로 연다 — 둘이 같은 대목 수를 센다.
- `citeContext(job: Pick<ResearchJob, "question" | "report">, eid: string | null, cntsId: string): CiteContext | null`
- `summaryQuestion(source: DetailSource, job: Pick<ResearchJob, "question" | "report"> | null): string`
- `withRo(word: string): string`

**Files:**
- Create: `frontend/utils/paperDetail.ts`
- Test: `frontend/tests/unit/paperDetail.test.ts` (새 파일)

- [ ] **Step 1: 실패 테스트 작성** — `frontend/tests/unit/paperDetail.test.ts` (새 파일)

```ts
// frontend/tests/unit/paperDetail.test.ts
import { describe, expect, it } from "vitest";
import type { ReportEvidence, ResearchJob } from "~/types/research";
import { citeContext, summaryQuestion, withRo } from "~/utils/paperDetail";

function chunk(id: string, page: number) {
  return { chunk_id: id, text: `대목 ${id}`, page_start: page, page_end: page, score: 0.5 };
}

const evidence: ReportEvidence = {
  cnts_id: "CNTS-1",
  meta: { title: "AI 윤리 교육", personal_author: "김철수; 이영희", pub_date: "2019-03" },
  // 쪽은 0부터 센다 — 0 은 쪽 정보 없음(citations.pdfPage)
  chunks: [chunk("c1", 7), chunk("c2", 0), chunk("c3", 2)],
};

function job(over: Partial<Pick<ResearchJob, "question" | "report">> = {}): Pick<ResearchJob, "question" | "report"> {
  return {
    question: "AI 윤리 교육의 효과",
    report: {
      question: "AI 윤리 교육의 효과는?",
      range: null,
      sections: [],
      evidence: { E3: evidence },
      trail: [],
      limitations: [],
    },
    ...over,
  };
}

describe("citeContext", () => {
  it("보고서 질문·인용 표기와 쪽 순 인용 대목을 만든다 — 쪽 정보가 없는 대목은 빼지 않고 뒤에 둔다", () => {
    expect(citeContext(job(), "E3", "CNTS-1")).toEqual({
      question: "AI 윤리 교육의 효과는?",
      label: "김 2019",
      chunks: [chunk("c3", 2), chunk("c1", 7), chunk("c2", 0)],
    });
  });

  it("근거 번호가 없거나 다른 논문의 것이거나 보고서가 아직 없으면 배너를 내지 않는다", () => {
    expect(citeContext(job(), null, "CNTS-1")).toBeNull();
    expect(citeContext(job(), "E9", "CNTS-1")).toBeNull();
    expect(citeContext(job(), "E3", "CNTS-2")).toBeNull();
    expect(citeContext(job({ report: null }), "E3", "CNTS-1")).toBeNull();
  });
});

describe("summaryQuestion", () => {
  it("검색에서 왔으면 결과의 검색어, 보고서에서 왔으면 보고서 질문", () => {
    expect(summaryQuestion({ kind: "search", h: null, q: "딥러닝" }, null)).toBe("딥러닝");
    expect(summaryQuestion({ kind: "research", job: "j", e: "E3" }, job())).toBe("AI 윤리 교육의 효과는?");
  });

  it("보고서가 아직 없으면 잡 질문, 잡을 못 읽었거나 출처가 없으면 빈 문자열", () => {
    expect(summaryQuestion({ kind: "research", job: "j", e: null }, job({ report: null }))).toBe("AI 윤리 교육의 효과");
    expect(summaryQuestion({ kind: "research", job: "j", e: null }, null)).toBe("");
    expect(summaryQuestion({ kind: "none" }, job())).toBe("");
  });
});

describe("withRo", () => {
  it("받침(ㄹ 제외)이 있으면 '으로', 없으면 '로' — 숫자는 읽는 소리로 가린다", () => {
    expect(withRo("김 2019")).toBe("김 2019로");
    expect(withRo("김 2020")).toBe("김 2020으로");
    expect(withRo("이 2016")).toBe("이 2016으로");
    expect(withRo("박 2023")).toBe("박 2023으로");
    expect(withRo("E7")).toBe("E7로");
    expect(withRo("김")).toBe("김으로");
    expect(withRo("서울")).toBe("서울로");
    expect(withRo("Smith")).toBe("Smith로");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/paperDetail.test.ts`
Expected: FAIL — `Error: Cannot find module '~/utils/paperDetail' imported from '…/tests/unit/paperDetail.test.ts'.` · `Test Files  1 failed (1)` · `Tests  no tests`

- [ ] **Step 3: 최소 구현** — `frontend/utils/paperDetail.ts` (새 파일)

```ts
// frontend/utils/paperDetail.ts
import type { ReportChunk, ResearchJob } from "~/types/research";
import { citeLabel, pdfPage } from "./citations";
import type { DetailSource } from "./detailSource";

type JobText = Pick<ResearchJob, "question" | "report">;

export interface CiteContext {
  question: string;
  label: string;
  // 인용 대목 — 쪽 순이라 첫 대목이 첫 인용 쪽이다. 쪽 정보가 없는 대목도 빼지 않고 뒤에 둔다 —
  // 배너의 "인용 대목 N곳"과 원문 뷰어의 "n/N"이 같은 수를 센다
  chunks: ReportChunk[];
}

// 쪽 정보가 없는 대목(pdfPage 가 undefined)을 맨 뒤로 보내는 정렬 값
const NO_PAGE = Number.MAX_SAFE_INTEGER;

// 보고서에서 온 상세의 인용 맥락 배너. 보고서가 아직 없거나(작성 중) 근거 번호가 이 논문의 것이 아니면 내지 않는다 —
// 주소의 e 를 고쳐 쓰면 다른 논문의 대목을 이 논문 것처럼 보이게 된다
export function citeContext(job: JobText, eid: string | null, cntsId: string): CiteContext | null {
  if (!eid || !job.report) return null;
  const evidence = job.report.evidence[eid];
  if (!evidence || evidence.cnts_id !== cntsId) return null;
  return {
    question: job.report.question || job.question,
    label: citeLabel(evidence.meta, eid),
    chunks: [...evidence.chunks].sort((a, b) => (pdfPage(a) ?? NO_PAGE) - (pdfPage(b) ?? NO_PAGE)),
  };
}

// AI 요약의 기준 질문 — 검색에서 왔으면 결과의 검색어, 보고서에서 왔으면 보고서 질문(작성 중이면 잡 질문).
// 빈 문자열이면 요약을 만들지 않고 소개글을 보인다
export function summaryQuestion(source: DetailSource, job: JobText | null): string {
  if (source.kind === "search") return source.q;
  if (source.kind === "research" && job) return job.report?.question || job.question;
  return "";
}

// "김 2019로"·"김 2020으로" — 끝 글자에 받침이 있으면(ㄹ 제외) "으로". 숫자는 읽는 소리로 가린다(0 십·백·천, 3 삼, 6 육).
// 한글·숫자가 아니면(영문 성) 받침을 알 수 없어 "로"로 둔다
const DIGIT_BATCHIM = new Set(["0", "3", "6"]);
const HANGUL_FIRST = 0xac00;
const HANGUL_LAST = 0xd7a3;
const RIEUL = 8;

function needsEuro(ch: string): boolean {
  if (DIGIT_BATCHIM.has(ch)) return true;
  const code = ch.charCodeAt(0);
  if (code < HANGUL_FIRST || code > HANGUL_LAST) return false;
  const jong = (code - HANGUL_FIRST) % 28;
  return jong !== 0 && jong !== RIEUL;
}

export function withRo(word: string): string {
  return `${word}${needsEuro(word.slice(-1)) ? "으로" : "로"}`;
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/paperDetail.test.ts`
Expected: `Test Files  1 passed (1)` · `Tests  5 passed (5)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/utils/paperDetail.ts frontend/tests/unit/paperDetail.test.ts && git commit -m "[Feat] round05a — 인용 맥락 배너와 AI 요약 기준 질문을 보고서에서 만드는 규칙: 근거 번호가 이 논문 것일 때만 배너를 내고 인용 대목은 쪽 순으로 모두 넘기며(쪽 정보 없는 대목은 뒤), 기준 질문은 검색어 또는 보고서 질문. '김 2019로'의 조사도 받침으로 가린다"
```

---

### Task 8: 논문 상세 — 돌아가기·탭 제목·관련도·연관 논문 링크·키워드 검색·이름 통일 (§5 ①③⑤⑥⑦ 링크, ④ 이름, D5)

선행: Task 1(`readDetailSource`·`readReturnSpot`·`backTarget`·`shouldGoBack`·`relatedDetailUrl`), Task 3(`isPlainClick`).

여기서는 [원문 보기]를 건드리지 않는다 — 원문 보기를 늘 원문 뷰어로 여는 일과 KCI 보조 링크는 Task 11이 맡는다.

**Files:**
- Modify: `frontend/pages/papers/[id].vue`
- Modify: `frontend/pages/papers/index.vue` (DeepSearch 를 DeepRead 로)
- Modify: `frontend/pages/index.vue` (DeepSearch 를 DeepRead 로)

세 파일 모두 CRLF 다. 반드시 Edit 도구로 고친다.

- [ ] **Step 1: 돌아가기** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```vue
        <!-- 뒤로가기 -->
        <button type="button" class="skx-pdetail__back" @click="$router.back()">
          <img src="/img/ico-arrow.svg" alt="" />
          검색 목록 돌아가기
        </button>
```
교체 후:
```vue
        <!-- 돌아가기 — 직전 화면이 출처면 브라우저 뒤로(그 화면 상태 그대로), 새 탭·연관 논문을 거쳐 왔으면 출처 주소로 간다 -->
        <a :href="back.to" class="skx-pdetail__back pd-back" @click="onBack">
          <img src="/img/ico-arrow.svg" alt="" />
          {{ back.label }}
        </a>
```

- [ ] **Step 2: DeepRead 이름 통일(버튼·대화 패널 제목)** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```vue
                <span class="skx-btn-talk__label">DeepSearch</span>
```
교체 후:
```vue
                <span class="skx-btn-talk__label">DeepRead</span>
```

교체 전:
```vue
            DeepSearch<template v-if="paper?.title"
```
교체 후:
```vue
            DeepRead<template v-if="paper?.title"
```

- [ ] **Step 3: 키워드를 누르면 새 검색** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```vue
                    <span
                      v-for="kw in keywords"
                      :key="kw"
                      class="skx-keyword"
                      >{{ kw }}</span
                    >
```
교체 후:
```vue
                    <!-- 키워드를 누르면 그 키워드로 새 논문 검색을 연다 -->
                    <NuxtLink
                      v-for="kw in keywords"
                      :key="kw"
                      :to="{ path: '/papers', query: { q: kw } }"
                      class="skx-keyword pd-keyword"
                      :aria-label="`${kw} — 이 키워드로 논문 검색`"
                      >{{ kw }}</NuxtLink
                    >
```

- [ ] **Step 4: 연관 논문 링크는 처음 출처를 잇는다** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```vue
              <article
                v-for="rel in relatedItems"
                :key="rel.book_id"
                class="skx-prelate-card"
                style="cursor: pointer"
                @click="navigateTo(`/papers/${rel.book_id}`)"
              >
                <div class="skx-prelate-card__info">
                  <span class="skx-prelate-card__score"
                    >연관도 {{ relatedScore(rel.score) }}%</span
                  >
                  <div class="skx-prelate-card__title-row">
                    <h3 class="skx-prelate-card__title">
                      {{ rel.book_info?.title || rel.book_id }}
                    </h3>
```
교체 후:
```vue
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
```

- [ ] **Step 5: 스크립트 — 출처·돌아가기·관련도·탭 제목·탭 이름** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```ts
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";

const route = useRoute();
```
교체 후:
```ts
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { backTarget, readDetailSource, readReturnSpot, relatedDetailUrl, shouldGoBack } from "~/utils/detailSource";
import { isPlainClick } from "~/utils/restorePosition";

const route = useRoute();
const router = useRouter();
```

교체 전:
```ts
const paperId = route.params.id as string;

const matchScore = computed(() => {
  const s = route.query.score;
  return s ? Math.round(Number(s) * 100) : null;
});
```
교체 후:
```ts
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
```

교체 전:
```ts
// Data
const paper = ref<any>(null);
const loading = ref(false);
```
교체 후:
```ts
// Data
const paper = ref<any>(null);
const loading = ref(false);

useHead({ title: () => (paper.value?.title ? `${paper.value.title} — 논문` : "논문") });
```

교체 전:
```ts
  { key: "ai-summary", label: "AI가 분석한 연구 핵심" },
```
교체 후:
```ts
  { key: "ai-summary", label: "AI 요약" },
```

- [ ] **Step 6: 새 요소 스타일** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지) — 이 페이지에는 `<style>` 블록이 없어 `</script>` 뒤에 scoped 블록을 새로 단다. 뒤 태스크(9·11·12)는 이 블록 끝의 `@media (prefers-reduced-motion: reduce)` 앞에 규칙을 더한다.

교체 전:
```vue
</script>
```
교체 후:
```vue
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
@media (prefers-reduced-motion: reduce) {
  .pd-keyword {
    transition: none;
  }
}
</style>
```

- [ ] **Step 7: DeepRead 이름 통일(검색 결과 화면)** — `frontend/pages/papers/index.vue` (Edit, CRLF 유지)

교체 전:
```vue
                        aria-label="DeepSearch"
```
교체 후:
```vue
                        aria-label="DeepRead"
```

교체 전:
```vue
            더 깊이 알고 싶은 논문은 <strong>DeepSearch</strong>로 자유롭게
```
교체 후:
```vue
            더 깊이 알고 싶은 논문은 <strong>DeepRead</strong>로 자유롭게
```

교체 전:
```vue
                    <img src="/img/ico-chat.svg" alt="" />
                    DeepSearch
```
교체 후:
```vue
                    <img src="/img/ico-chat.svg" alt="" />
                    DeepRead
```

교체 전:
```vue
          DeepSearch<template v-if="chatPaperTitle"
```
교체 후:
```vue
          DeepRead<template v-if="chatPaperTitle"
```

- [ ] **Step 8: DeepRead 이름 통일(메인 화면)** — `frontend/pages/index.vue` (Edit, CRLF 유지)

교체 전:
```vue
                    <span class="skx-btn-chat__label">{{
                      mode === "paper" ? "DeepSearch" : "DeepRead"
                    }}</span>
```
교체 후:
```vue
                    <span class="skx-btn-chat__label">DeepRead</span>
```

- [ ] **Step 9: 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && grep -rn "DeepSearch" frontend/pages frontend/components`
Expected: 출력 없음

Run(출처 없이 옮기는 옛 이동이 남지 않았는지):
```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && grep -n 'navigateTo(`/papers/\|검색 목록 돌아가기\|\$router.back' "frontend/pages/papers/[id].vue"
```
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && grep -n "const refsOpen = ref(false)" "frontend/pages/papers/[id].vue"`
Expected: 1줄. 참고문헌 아코디언은 이미 접힌 채로 시작하므로 바꾸지 않는다(§5 ⑥).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: 실패 0건(이 태스크는 테스트 수를 바꾸지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

- [ ] **Step 10: 화면 확인(선택, `frontend-prod-api`)** — Task 4·5 와 함께 spec §7 ①③④⑤⑥⑦⑧ 을 본다.

- 보고서 인용칩 → [논문 상세] → [딥리서치 보고서로]: 같은 칩이 같은 높이에 오고 팝오버가 열린다(①).
- 상세 → 연관 논문 2편 → [딥리서치 보고서로]: 처음 칩 자리로 간다(③).
- 보고서의 "제외한 논문"을 새 탭으로 열고 그 탭에서 [딥리서치 보고서로]: 접힌 제외 목록이 펼쳐진 채 그 항목이 같은 높이에 온다(④).
- 검색 결과 중간 카드 → 상세 → [검색 결과로]: 재검색 없이 그 카드 자리(⑤).
- 메인 화면 논문 탭에서 검색(`/papers` 로 넘어간다) → 카드 → 상세 → [검색 결과로]: ⑤와 같다(⑥).
- 주소 직접 입력(`/papers/<id>`) → "검색으로" → 홈(⑦).
- 사이드바 강조와 탭 제목 "논문 제목 — 논문"(⑧).
- 연관 논문 카드의 제목 링크에 Tab 으로 초점을 주면 마우스를 올린 것처럼 '유사한 점'이 펼쳐진다.

- [ ] **Step 11: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add "frontend/pages/papers/[id].vue" frontend/pages/papers/index.vue frontend/pages/index.vue && git commit -m "[Feat] round05a — 논문 상세: 돌아가기는 출처로(검색 결과로/딥리서치 보고서로/검색으로, 직전이 출처면 브라우저 뒤로), 탭 제목 '논문 제목 — 논문', 관련도는 검색에서 왔을 때만, 연관 논문은 처음 출처를 잇는 카드 링크, 키워드는 새 논문 검색, 'AI 요약' 탭, DeepSearch 를 DeepRead 로 통일"
```

---

### Task 9: 논문 상세 — 인용 맥락 배너·AI 요약 기준 질문·캐시 적용 (§5 ②⑤⑦, D6·D7)

선행: Task 6(`aiCache`·`safeSessionStorage`), Task 7(`citeContext`·`summaryQuestion`·`withRo`), Task 8(돌아가기 링크·`source`·`<style scoped>` 블록).

배너의 [인용 대목 보기] 버튼과 원문을 열지 못했을 때의 안내는 원문 뷰어 태스크(Task 11)가 단다. 여기서는 배너 글("딥리서치 보고서 ‘질문’에서 김 2019로 인용됨 · 인용 대목 N곳")만 그린다.

**Files:**
- Modify: `frontend/pages/papers/[id].vue`

CRLF 파일이다. 반드시 Edit 도구로 고친다.

- [ ] **Step 1: 인용 맥락 배너** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지) — Task 8 의 돌아가기 링크 바로 뒤

교체 전:
```vue
          {{ back.label }}
        </a>

        <div v-if="loading" style="padding: 40px; text-align: center">
```
교체 후:
```vue
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
          </div>
        </section>

        <div v-if="loading" style="padding: 40px; text-align: center">
```

- [ ] **Step 2: 스크립트 — 가져오기** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```ts
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { backTarget, readDetailSource, readReturnSpot, relatedDetailUrl, shouldGoBack } from "~/utils/detailSource";
```
교체 후:
```ts
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useResearchApi } from "~/composables/useResearch";
import type { ResearchJob } from "~/types/research";
import { readAiCache, relatedCacheKey, summaryCacheKey, writeAiCache } from "~/utils/aiCache";
import { safeSessionStorage } from "~/utils/browserId";
import { backTarget, readDetailSource, readReturnSpot, relatedDetailUrl, shouldGoBack } from "~/utils/detailSource";
import { citeContext, summaryQuestion, withRo, type CiteContext } from "~/utils/paperDetail";
```

- [ ] **Step 3: 스크립트 — 보고서 읽기** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```ts
const thumbnailUrl = ref(`${config.public.apiBase}/books/${paperId}/thumbnail`);

function showToast(msg: string) {
```
교체 후:
```ts
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
```

- [ ] **Step 4: AI 요약 기준 질문과 캐시** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```ts
async function streamPaperReason() {
  const query = (route.query.q as string) || "";
  if (!query) {
    summaryText.value = paper.value?.introduction || "";
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
    await readSSE(resp, (json) => {
      if (json.text) summaryText.value += json.text;
    });
  } catch {
```
교체 후:
```ts
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
```

- [ ] **Step 5: 연관 이유 캐시와 readSSE 완료 여부** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```ts
async function streamRelatedReason(relatedId: string) {
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
    await readSSE(resp, (json) => {
```
교체 후:
```ts
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
```

교체 전:
```ts
          [relatedId]: (relatedReasons.value[relatedId] || "") + json.text,
        };
      }
    });
  } catch {
```
교체 후:
```ts
          [relatedId]: (relatedReasons.value[relatedId] || "") + json.text,
        };
      }
    });
    if (finished) writeAiCache(safeSessionStorage(), key, relatedReasons.value[relatedId] ?? "");
  } catch {
```

교체 전:
```ts
async function readSSE(resp: Response, onEvent: (json: any) => void) {
```
교체 후:
```ts
// [DONE] 까지 받았으면 true — 도중에 끊긴 글은 캐시에 담지 않는다
async function readSSE(resp: Response, onEvent: (json: any) => void): Promise<boolean> {
```

교체 전:
```ts
      if (raw === "[DONE]") return;
```
교체 후:
```ts
      if (raw === "[DONE]") return true;
```

교체 전:
```ts
      try {
        onEvent(JSON.parse(raw));
      } catch {
        /* skip */
      }
    }
  }
}
```
교체 후:
```ts
      try {
        onEvent(JSON.parse(raw));
      } catch {
        /* skip */
      }
    }
  }
  return false;
}
```

- [ ] **Step 6: 마운트 순서** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```ts
onMounted(async () => {
  await fetchPaper();
  if (route.query.chat === "1") chatOpen.value = true;
  streamPaperReason();
  fetchRelated();
  nextTick(() => updateVtabSlider());
});
```
교체 후:
```ts
onMounted(async () => {
  // 보고서는 논문과 함께 읽는다 — 보고서에서 온 상세는 AI 요약의 기준 질문이 보고서 질문이다
  const research = loadResearch();
  await fetchPaper();
  if (route.query.chat === "1") chatOpen.value = true;
  fetchRelated();
  nextTick(() => updateVtabSlider());
  streamPaperReason(summaryQuestion(source, await research));
});
```

- [ ] **Step 7: 배너 스타일** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지) — Task 8 의 scoped 스타일 끝

교체 전:
```css
@media (prefers-reduced-motion: reduce) {
  .pd-keyword {
    transition: none;
  }
}
</style>
```
교체 후:
```css
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
@media (prefers-reduced-motion: reduce) {
  .pd-keyword {
    transition: none;
  }
}
</style>
```

- [ ] **Step 8: 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && grep -n 'route.query.q as string' "frontend/pages/papers/[id].vue"`
Expected: 출력 없음 — AI 요약 기준 질문은 출처(`summaryQuestion`)로만 정한다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: 실패 0건(이 태스크는 테스트 수를 바꾸지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && git diff d7f7e95..HEAD --stat -- app`
Expected: 출력 없음(백엔드 변경 없음)

- [ ] **Step 9: 화면 확인(선택, `frontend-prod-api`)**

- 보고서 인용칩 → [논문 상세]: 머리 위에 "딥리서치 보고서 ‘…’에서 ○ 2019로 인용됨 · 인용 대목 N곳" 배너가 보이고, AI 요약 탭은 보고서 질문 기준으로 만든다.
- 주소의 `e` 를 다른 논문의 근거 번호로 바꾸면 배너가 사라진다.
- 상세 → 다른 화면 → 뒤로: AI 요약·연관 이유 스트림 요청(`/papers/reason/stream`·`/papers/related-reason/stream`)이 다시 나가지 않는다(spec §7 ⑨).

- [ ] **Step 10: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add "frontend/pages/papers/[id].vue" && git commit -m "[Feat] round05a — 논문 상세: 보고서에서 왔으면 인용 맥락 배너(보고서 질문·인용 표기·인용 대목 수), AI 요약 기준은 검색어 또는 보고서 질문(없으면 소개글), AI 요약·연관 이유는 끝까지 받은 글만 탭 안에 캐시해 상세를 오갈 때 다시 만들지 않는다"
```

---

## 단계 3 — 원문 뷰어 (Task 10·11)

- 범위는 spec §6, §5 ④(원문 보기는 늘 원문 뷰어, KCI 는 보조 링크), §5 ②의 [인용 대목 보기]다.
- 인용칩 팝오버의 [원문 보기]는 지금처럼 그 대목의 쪽만 넘긴다(대목 목록은 넘기지 않는다 — 끝의 "이 계획에서 다루지 않는 것" 참고).

### Task 10: 원문 뷰어 로직 — 인용 대목 목록·Esc 판단·초점 되돌릴 곳·열기 전 확인 요청 (spec §6)

계약 추가:
- `types/research.ts`:
  - `interface PdfPassage { page: number | null; label: string }` 를 더한다. 처음 계약의 `{ page: number }[]` 대신 이 모양으로 정했다. 쪽 정보가 없는 대목도 세어야 배너의 "N곳"과 뷰어의 "n/N"이 같아진다.
  - `OpenPdfPayload` 에 `passages?: PdfPassage[]` 를 더한다.
- `utils/pdfViewer.ts`(신규): `PdfJsApp`, `pdfJsApp(win)`, `viewerOwnsEscape(app)`, `citedPassages(chunks)`, `citedPdfTarget(cntsId, title, chunks): OpenPdfPayload`, `focusReturnTarget(path)`, `pdfStatus(url, headers, fetchFn?)`.
- `pdfCheckProblem` 은 `utils/researchErrors.ts` 에 그대로 두고 재사용한다(옮기지 않는다).

**Files:**
- Modify: `frontend/types/research.ts` (`OpenPdfPayload`, d7f7e95 기준 417~421행)
- Create: `frontend/utils/pdfViewer.ts`
- Test: `frontend/tests/unit/pdfViewer.test.ts`

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `frontend/tests/unit/pdfViewer.test.ts` (새 파일)

```ts
// frontend/tests/unit/pdfViewer.test.ts
import { describe, expect, it } from "vitest";
import {
  citedPassages,
  citedPdfTarget,
  focusReturnTarget,
  pdfJsApp,
  pdfStatus,
  viewerOwnsEscape,
  type PdfJsApp,
} from "~/utils/pdfViewer";

function app(over: Partial<PdfJsApp> = {}): PdfJsApp {
  return {
    initializedPromise: Promise.resolve(),
    page: 1,
    pagesCount: 10,
    eventBus: { on: () => {} },
    findBar: { opened: false },
    secondaryToolbar: { isOpen: false },
    overlayManager: { active: null },
    ...over,
  };
}

// Node 에는 DOM 이 없다 — 초점 되돌리기가 읽는 isConnected·matches·querySelector 만 흉내 낸다
function node(name: string, opts: { connected?: boolean; focusable?: boolean; inner?: HTMLElement } = {}): HTMLElement {
  return {
    name,
    isConnected: opts.connected ?? true,
    matches: () => opts.focusable ?? false,
    querySelector: () => opts.inner ?? null,
  } as unknown as HTMLElement;
}

describe("pdfJsApp", () => {
  it("iframe 창의 PDFViewerApplication 을 읽고, 없으면 null", () => {
    const a = app();
    expect(pdfJsApp({ PDFViewerApplication: a } as unknown as Window)).toBe(a);
    expect(pdfJsApp({} as Window)).toBeNull();
    expect(pdfJsApp(null)).toBeNull();
  });
});

describe("viewerOwnsEscape", () => {
  it("찾기 막대·보조 도구 줄·대화상자가 열려 있으면 Esc 를 pdf.js 에 맡긴다", () => {
    expect(viewerOwnsEscape(app({ findBar: { opened: true } }))).toBe(true);
    expect(viewerOwnsEscape(app({ secondaryToolbar: { isOpen: true } }))).toBe(true);
    expect(viewerOwnsEscape(app({ overlayManager: { active: {} } }))).toBe(true);
  });

  it("아무것도 열려 있지 않거나 앱을 못 읽으면 뷰어를 닫는다", () => {
    expect(viewerOwnsEscape(app())).toBe(false);
    expect(viewerOwnsEscape(null)).toBe(false);
  });
});

describe("citedPassages", () => {
  it("대목마다 pdf.js 쪽(1부터)과 쪽 표시를 만들고, 쪽 정보가 없는 대목도 센다", () => {
    expect(
      citedPassages([
        { page_start: 2, page_end: 3 },
        { page_start: 0, page_end: 0 },
        { page_start: 6, page_end: 6 },
      ]),
    ).toEqual([
      { page: 3, label: "p.3–4" },
      { page: null, label: "쪽 정보 없음" },
      { page: 7, label: "p.7" },
    ]);
  });
});

describe("citedPdfTarget", () => {
  it("첫 대목의 쪽에서 열고 대목 목록을 함께 넘긴다", () => {
    expect(citedPdfTarget("C1", "논문", [{ page_start: 4, page_end: 4 }, { page_start: 9, page_end: 9 }])).toEqual({
      cntsId: "C1",
      title: "논문",
      page: 5,
      passages: [
        { page: 5, label: "p.5" },
        { page: 10, label: "p.10" },
      ],
    });
  });

  it("첫 대목에 쪽 정보가 없으면 첫 쪽에서 연다", () => {
    expect(citedPdfTarget("C1", "논문", [{ page_start: 0, page_end: 0 }]).page).toBeUndefined();
  });
});

describe("focusReturnTarget", () => {
  it("연 버튼이 남아 있으면 그 버튼으로 돌려준다", () => {
    const opener = node("원문 보기", { focusable: true });
    expect(focusReturnTarget([opener, node("버튼 묶음")])).toBe(opener);
  });

  it("연 버튼이 사라졌으면 남은 가장 가까운 조상 안의 첫 초점 요소로 돌려준다", () => {
    const chip = node("인용칩", { focusable: true });
    const opener = node("팝오버의 원문 보기", { connected: false, focusable: true });
    const pop = node("팝오버", { connected: false });
    const wrap = node("칩 묶음", { inner: chip });
    expect(focusReturnTarget([opener, pop, wrap])).toBe(chip);
  });

  it("돌려줄 곳이 없으면 null", () => {
    expect(focusReturnTarget([])).toBeNull();
    expect(focusReturnTarget([node("사라진 버튼", { connected: false, focusable: true })])).toBeNull();
  });
});

describe("pdfStatus", () => {
  it("확인 요청의 상태를 돌려주고, 본문은 받지 않게 요청을 끊는다", async () => {
    let seen: RequestInit | undefined;
    const fake = (async (_url: string | URL | Request, init?: RequestInit) => {
      seen = init;
      return new Response(null, { status: 404 });
    }) as typeof fetch;
    expect(await pdfStatus("/api/books/C1/pdf", { "x-session-id": "s1" }, fake)).toBe(404);
    expect(seen?.headers).toEqual({ "x-session-id": "s1" });
    expect(seen?.signal?.aborted).toBe(true);
  });

  it("요청 자체가 실패하면 null", async () => {
    const fake = (async () => {
      throw new TypeError("Failed to fetch");
    }) as typeof fetch;
    expect(await pdfStatus("/api/books/C1/pdf", {}, fake)).toBeNull();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/pdfViewer.test.ts`
Expected: FAIL — `Error: Cannot find module '~/utils/pdfViewer' imported from '…/tests/unit/pdfViewer.test.ts'.` · `Test Files  1 failed (1)` · `Tests  no tests`

- [ ] **Step 3: 타입을 더한다** — `frontend/types/research.ts` (Edit, CRLF 유지)

교체 전:
```ts
export interface OpenPdfPayload {
  cntsId: string;
  title: string;
  page?: number;
}
```
교체 후:
```ts
// 원문 뷰어 머리의 "인용 대목 n/N" 한 칸. page 는 pdf.js 쪽 번호(1부터), 쪽 정보가 없으면 null
export interface PdfPassage {
  page: number | null;
  label: string;
}

export interface OpenPdfPayload {
  cntsId: string;
  title: string;
  page?: number;
  passages?: PdfPassage[];
}
```

- [ ] **Step 4: 최소 구현** — `frontend/utils/pdfViewer.ts` (새 파일)

```ts
// frontend/utils/pdfViewer.ts
import type { OpenPdfPayload, PdfPassage, ReportChunk } from "~/types/research";
import { pageLabel, pdfPage } from "./citations";

// 원문 뷰어(public/pdfjs — pdf.js 4.0.379 고정)의 앱 객체 중 머리의 쪽 표시와 Esc 판단에 쓰는 부분만 적는다
export interface PdfJsApp {
  readonly initializedPromise: Promise<void>;
  page: number;
  readonly pagesCount: number;
  readonly eventBus: { on(name: string, listener: (evt: { pageNumber: number }) => void): void };
  readonly findBar?: { opened: boolean };
  readonly secondaryToolbar?: { isOpen: boolean };
  readonly overlayManager?: { active: unknown };
}

// 뷰어는 같은 출처(/pdfjs/web/viewer.html)라 iframe 창의 앱 객체를 바로 읽는다. 없으면(로드 전·내부 API 변경) null
export function pdfJsApp(win: Window | null): PdfJsApp | null {
  return (win as (Window & { PDFViewerApplication?: PdfJsApp }) | null)?.PDFViewerApplication ?? null;
}

// 찾기 막대·보조 도구 줄·pdf.js 대화상자가 열려 있으면 Esc 는 그것부터 닫는다(pdf.js 동작) —
// 이때 뷰어까지 닫으면 한 번 눌러 둘이 닫힌다
export function viewerOwnsEscape(app: PdfJsApp | null): boolean {
  return !!(app?.findBar?.opened || app?.secondaryToolbar?.isOpen || app?.overlayManager?.active);
}

// 쪽 정보가 없는 대목(page_start 0)도 빼지 않는다 — 배너의 "인용 대목 N곳"과 뷰어의 "n/N"이 같은 수를 센다
export function citedPassages(chunks: readonly Pick<ReportChunk, "page_start" | "page_end">[]): PdfPassage[] {
  return chunks.map((c) => ({ page: pdfPage(c) ?? null, label: pageLabel(c) }));
}

// 인용 대목으로 원문을 열 때의 뷰어 입력 — 첫 대목의 쪽에서 연다
export function citedPdfTarget(
  cntsId: string,
  title: string,
  chunks: readonly Pick<ReportChunk, "page_start" | "page_end">[],
): OpenPdfPayload {
  const passages = citedPassages(chunks);
  return { cntsId, title, page: passages[0]?.page ?? undefined, passages };
}

const FOCUSABLE =
  "button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex='-1'])";

// 뷰어를 닫을 때 초점을 돌려줄 곳. path 는 연 순간의 초점 요소부터 위로 올라간 조상들이다. 연 버튼이 그사이
// 사라졌으면(딥리서치 인용 팝오버는 초점이 뷰어로 옮겨 가면 닫히며 안의 [원문 보기]도 빠진다) 아직 문서에
// 남은 가장 가까운 조상 안의 첫 초점 요소 — 그 인용칩 — 로 돌려준다
export function focusReturnTarget(path: readonly HTMLElement[]): HTMLElement | null {
  const home = path.find((el) => el.isConnected);
  if (!home) return null;
  return home.matches(FOCUSABLE) ? home : home.querySelector<HTMLElement>(FOCUSABLE);
}

// 원문 보기 전 확인 요청의 HTTP 상태. 요청 자체가 실패하면 null(pdfCheckProblem 이 판단을 뷰어에 맡긴다)
export async function pdfStatus(
  url: string,
  headers: Record<string, string>,
  fetchFn: typeof fetch = fetch,
): Promise<number | null> {
  const ctrl = new AbortController();
  try {
    const res = await fetchFn(url, { headers, signal: ctrl.signal });
    return res.status;
  } catch {
    return null;
  } finally {
    // 본문은 필요 없다 — 뷰어가 다시 받는다. 끊지 않으면 PDF 전체를 두 번 내려받는다
    ctrl.abort();
  }
}
```

- [ ] **Step 5: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/pdfViewer.test.ts`
Expected: `Test Files  1 passed (1)` · `Tests  11 passed (11)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/types/research.ts frontend/utils/pdfViewer.ts frontend/tests/unit/pdfViewer.test.ts && git commit -m "[Feat] round05a — 원문 뷰어 로직(인용 대목 목록·Esc 를 pdf.js 에 맡길지·닫을 때 초점을 돌려줄 곳·열기 전 확인 요청)을 utils/pdfViewer 로 모은다"
```

---

### Task 11: 원문 뷰어 머리·Esc·초점과 열기 전 확인 공용화 — 상세 원문 보기를 늘 뷰어로, 배너 [인용 대목 보기] (spec §6, §5 ②④)

계약 추가:
- `composables/usePdfOpener.ts`: `usePdfOpener() → { pdf, checking, openPdf(target): Promise<string | null>, closePdf }`. `openPdf` 는 문제가 있을 때만 그 문구를 돌려주고, 문제가 없으면 뷰어를 연다. 확인 중에 또 누르면 무시하고 null 을 돌려준다. 문구를 어디에 보일지는 화면이 정한다(딥리서치는 토스트, 논문 상세는 누른 버튼 아래).
- `components/PdfViewer.vue`: 속성 `passages?: PdfPassage[]`.
- `pages/papers/[id].vue` 페이지 스코프: `pdf`·`checkingPdf`·`openPdf`·`closePdf`·`pdfProblem`·`openOriginal`(머리의 [원문 보기]), `bannerPdfProblem`·`openCitedPassages(chunks)`(배너의 [인용 대목 보기] — `citedPdfTarget(paperId, 제목, cite.chunks)` 로 첫 인용 쪽에서 연다).
- 처음 계약의 "열기 전 확인 공용 유틸(`pdfCheckProblem` 재사용·이동)"은 `pdfCheckProblem` 을 `utils/researchErrors.ts` 에 그대로 두고 `usePdfOpener` 가 부르는 것으로 정했다.

선행: Task 10(`PdfPassage`·`utils/pdfViewer`), Task 9(배너), Task 8(`<style scoped>` 블록), Task 4(`pages/research/[id].vue` 의 import 줄 — 겹치지 않는다).

인용칩 팝오버의 [원문 보기]는 지금처럼 그 대목의 쪽만 넘긴다 — `CitationChip.vue` 는 이 태스크에서 고치지 않는다. 대목 넘기기(`passages`)는 상세 배너의 [인용 대목 보기]만 쓴다.

**Files:**
- Create: `frontend/composables/usePdfOpener.ts`
- Modify: `frontend/components/PdfViewer.vue` (템플릿·스크립트 전체, 스타일 끝)
- Modify: `frontend/pages/research/[id].vue` (PdfViewer 태그·import·`pdfBase`·원문 보기 함수)
- Modify: `frontend/pages/papers/[id].vue` (원문 보기 버튼 묶음·배너 버튼·PdfViewer 태그·스크립트·스타일)

- [ ] **Step 1: 열기 전 확인 composable** — `frontend/composables/usePdfOpener.ts` (새 파일)

```ts
// frontend/composables/usePdfOpener.ts
import { ref } from "vue";
import type { OpenPdfPayload } from "~/types/research";
import { pdfStatus } from "~/utils/pdfViewer";
import { pdfCheckProblem } from "~/utils/researchErrors";
import { apiHeaders, apiUrl } from "./useApi";

// 원문 뷰어를 열기 전에 파일이 있는지 먼저 묻는다 — 없는 원문을 그대로 열면 pdf.js 의 영문 오류 화면이 뜬다.
// 알릴 문구는 돌려주기만 하고 어디에 보일지는 화면이 정한다(딥리서치는 토스트, 논문 상세는 누른 버튼 옆)
export function usePdfOpener() {
  const pdf = ref<OpenPdfPayload | null>(null);
  const checking = ref(false);

  async function openPdf(target: OpenPdfPayload): Promise<string | null> {
    // 확인이 끝나기 전에 또 누르면 무시한다 — 뷰어가 두 번 열리거나 문구가 뒤섞이지 않게
    if (checking.value) return null;
    checking.value = true;
    const problem = pdfCheckProblem(await pdfStatus(apiUrl(`/books/${encodeURIComponent(target.cntsId)}/pdf`), apiHeaders()));
    checking.value = false;
    if (!problem) pdf.value = target;
    return problem;
  }

  function closePdf(): void {
    pdf.value = null;
  }

  return { pdf, checking, openPdf, closePdf };
}
```

- [ ] **Step 2: PdfViewer 템플릿** — `frontend/components/PdfViewer.vue` (Edit, CRLF 유지. 첫 줄 경로 주석이 없던 파일이라 이번에 단다)

교체 전:
```vue
<template>
  <Teleport to="body">
    <div class="pdf-overlay" @click.self="$emit('close')">
      <div class="pdf-modal">

        <div class="pdf-header">
          <span class="pdf-title" :title="title">{{ title }}</span>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>

        <iframe
          class="pdf-frame"
          :src="viewerUrl"
          allowfullscreen
        />

      </div>
    </div>
  </Teleport>
</template>
```
교체 후:
```vue
<!-- frontend/components/PdfViewer.vue -->
<template>
  <Teleport to="body">
    <div class="pdf-overlay" @click.self="$emit('close')">
      <div class="pdf-modal" role="dialog" aria-modal="true" :aria-label="dialogLabel">

        <div class="pdf-header">
          <span class="pdf-title" :title="title">{{ title }}</span>
          <!-- pdf.js 를 못 읽으면(문서를 받기 전·내부 API 변경) 쪽 표시만 숨기고 뷰어는 그대로 쓴다 -->
          <template v-if="total > 0">
            <div class="pdf-pager" role="group" aria-label="쪽 이동">
              <button type="button" class="pdf-step" aria-label="이전 쪽" :aria-disabled="page <= 1" @click="stepPage(-1)">‹</button>
              <span class="pdf-count">{{ page }} / {{ total }}쪽</span>
              <button type="button" class="pdf-step" aria-label="다음 쪽" :aria-disabled="page >= total" @click="stepPage(1)">›</button>
            </div>
            <div v-if="cited.length" class="pdf-pager pdf-pager--cite" role="group" aria-label="인용 대목 이동">
              <span class="pdf-count" aria-live="polite">인용 대목 {{ passageIdx + 1 }}/{{ cited.length }} · {{ cited[passageIdx]?.label }}</span>
              <button type="button" class="pdf-step" aria-label="이전 인용 대목" :aria-disabled="passageIdx <= 0" @click="stepPassage(-1)">‹</button>
              <button
                type="button"
                class="pdf-step"
                aria-label="다음 인용 대목"
                :aria-disabled="passageIdx >= cited.length - 1"
                @click="stepPassage(1)"
              >
                ›
              </button>
            </div>
          </template>
          <button ref="closeBtn" type="button" class="close-btn" aria-label="원문 닫기" title="닫기 (Esc)" @click="$emit('close')">✕</button>
        </div>

        <iframe
          ref="frame"
          class="pdf-frame"
          :src="viewerUrl"
          :title="`${title || '논문'} 원문`"
          allowfullscreen
          @load="onFrameLoad"
        />

      </div>
    </div>
  </Teleport>
</template>
```

- [ ] **Step 3: PdfViewer 스크립트** — `frontend/components/PdfViewer.vue` (Edit, CRLF 유지)

교체 전:
```vue
<script setup lang="ts">
const props = defineProps<{
  cntsId: string;
  title?: string;
  page?: number;
}>();

defineEmits<{ close: [] }>();

const viewerUrl = computed(() => {
  const file = encodeURIComponent(`/api/books/${props.cntsId}/pdf`);
  // pdf.js 뷰어는 해시의 page 로 첫 화면 쪽을 정한다(1부터 센다)
  const hash = props.page && props.page > 0 ? `#page=${props.page}` : "";
  return `/pdfjs/web/viewer.html?file=${file}${hash}`;
});
</script>
```
교체 후:
```vue
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { PdfPassage } from "~/types/research";
import { focusReturnTarget, pdfJsApp, viewerOwnsEscape, type PdfJsApp } from "~/utils/pdfViewer";
import { stepChunk } from "~/utils/researchReport";

const props = defineProps<{
  cntsId: string;
  title?: string;
  page?: number;
  passages?: PdfPassage[];
}>();

const emit = defineEmits<{ close: [] }>();

const viewerUrl = computed(() => {
  const file = encodeURIComponent(`/api/books/${props.cntsId}/pdf`);
  // pdf.js 뷰어는 해시의 page 로 첫 화면 쪽을 정한다(1부터 센다)
  const hash = props.page && props.page > 0 ? `#page=${props.page}` : "";
  return `/pdfjs/web/viewer.html?file=${file}${hash}`;
});

const dialogLabel = computed(() => (props.title ? `원문 보기: ${props.title}` : "원문 보기"));
const frame = ref<HTMLIFrameElement | null>(null);
const closeBtn = ref<HTMLButtonElement | null>(null);
// pdf.js 가 알려 주는 지금 쪽·전체 쪽. 전체가 0 이면 아직 문서를 못 읽은 것이라 머리의 쪽 표시를 숨긴다
const page = ref(props.page ?? 1);
const total = ref(0);
const cited = computed(() => props.passages ?? []);
const passageIdx = ref(0);
let app: PdfJsApp | null = null;

function goPage(n: number): void {
  if (!app || n === page.value) return;
  app.page = n;
}

// stepChunk 는 0부터 세는 칸을 넘긴다 — 쪽은 1부터 세므로 하나 빼서 넘기고 되돌린다
function stepPage(delta: number): void {
  goPage(stepChunk(page.value - 1, delta, total.value) + 1);
}

function stepPassage(delta: number): void {
  passageIdx.value = stepChunk(passageIdx.value, delta, cited.value.length);
  const target = cited.value[passageIdx.value]?.page;
  if (target) goPage(target);
}

// iframe 은 로드마다 새 창이라 듣기도 매번 붙인다
async function onFrameLoad(): Promise<void> {
  const win = frame.value?.contentWindow ?? null;
  // 초점이 뷰어 안에 있으면 키 입력이 이 문서까지 오지 않는다 — Esc 는 뷰어 창에서도 듣는다.
  // 캡처로 들어야 찾기 막대가 Esc 로 먼저 닫히기 전에 열려 있었는지 볼 수 있다
  win?.addEventListener("keydown", onFrameKeydown, true);
  const found = pdfJsApp(win);
  if (!found) return;
  await found.initializedPromise;
  app = found;
  const sync = () => {
    total.value = found.pagesCount;
    page.value = found.page;
  };
  found.eventBus.on("pagesinit", sync);
  found.eventBus.on("pagechanging", (evt) => {
    page.value = evt.pageNumber;
  });
  // 듣기를 붙이기 전에 문서가 이미 열렸을 수 있다
  if (found.pagesCount > 0) sync();
}

function onFrameKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape" && !viewerOwnsEscape(app)) emit("close");
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape") emit("close");
}

// 열려 있는 동안 배경(#__nuxt — 뷰어는 body 로 옮겨 그려진다)은 초점·클릭을 받지 않게 하고 스크롤도 묶는다.
// Tab 이 뷰어 밖으로 새지 않고, 겹친 화면을 굴려도 읽던 자리가 그대로 남는다. 스크롤바가 있던 화면은
// 그 자리를 남겨 배경이 옆으로 밀리지 않게 한다
function lockPage(on: boolean): void {
  const root = document.documentElement;
  const hasBar = window.innerWidth > root.clientWidth;
  document.getElementById("__nuxt")?.toggleAttribute("inert", on);
  root.style.overflow = on ? "hidden" : "";
  root.style.scrollbarGutter = on && hasBar ? "stable" : "";
}

// 연 순간의 초점 요소부터 위로 올라간 조상들 — 닫을 때 초점을 돌려줄 곳을 찾는다(focusReturnTarget)
const returnPath: HTMLElement[] = [];

onMounted(() => {
  for (let el = document.activeElement; el instanceof HTMLElement && el !== document.body; el = el.parentElement) {
    returnPath.push(el);
  }
  lockPage(true);
  document.addEventListener("keydown", onKeydown);
  closeBtn.value?.focus();
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
  lockPage(false);
  // 배경은 그대로 있으니 돌려준 초점 때문에 화면이 움직이지 않게 한다
  focusReturnTarget(returnPath)?.focus({ preventScroll: true });
});
</script>
```

- [ ] **Step 4: PdfViewer 스타일** — `frontend/components/PdfViewer.vue` (Edit, CRLF 유지) — 파일 끝

교체 전:
```css
.close-btn:hover { background: rgba(255, 80, 80, 0.3); }

.pdf-frame {
  flex: 1;
  width: 100%;
  border: none;
}
</style>
```
교체 후:
```css
.close-btn:hover { background: rgba(255, 80, 80, 0.3); }

.pdf-pager {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.pdf-pager--cite {
  padding-left: 12px;
  border-left: 1px solid rgba(255, 255, 255, 0.12);
}
.pdf-count {
  font-size: 12px;
  color: #c8c8e0;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.pdf-step {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: rgba(255, 255, 255, 0.08);
  color: #e0e0f0;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s;
}
.pdf-step:hover { background: rgba(255, 255, 255, 0.16); }
.pdf-step[aria-disabled="true"] {
  opacity: 0.35;
  cursor: default;
  background: rgba(255, 255, 255, 0.08);
}
.pdf-step:focus-visible,
.close-btn:focus-visible {
  outline: 2px solid #a5b4fc;
  outline-offset: 2px;
}

@media (max-width: 640px) {
  /* 좁은 화면은 제목을 한 줄 차지하게 두고 쪽·인용 대목 넘기기와 닫기를 다음 줄로 내린다 */
  .pdf-header { flex-wrap: wrap; height: auto; padding: 8px 12px; row-gap: 6px; }
  .pdf-title { flex-basis: 100%; }
  .close-btn { margin-left: auto; }
}

@media (prefers-reduced-motion: reduce) {
  .pdf-step,
  .close-btn { transition: none; }
}

.pdf-frame {
  flex: 1;
  width: 100%;
  border: none;
}
</style>
```

- [ ] **Step 5: 딥리서치 페이지가 공용 확인을 쓰게** — `frontend/pages/research/[id].vue` (Edit, CRLF 유지)

교체 전:
```vue
    <PdfViewer v-if="pdf" :cnts-id="pdf.cntsId" :title="pdf.title" :page="pdf.page" @close="pdf = null" />
```
교체 후:
```vue
    <PdfViewer v-if="pdf" :cnts-id="pdf.cntsId" :title="pdf.title" :page="pdf.page" :passages="pdf.passages" @close="closePdf" />
```

교체 전:
```ts
import { apiHeaders, apiUrl } from "~/composables/useApi";
import { useNow } from "~/composables/useNow";
```
교체 후:
```ts
import { useNow } from "~/composables/useNow";
import { usePdfOpener } from "~/composables/usePdfOpener";
```

교체 전:
```ts
import { pdfCheckProblem, researchErrorMessage } from "~/utils/researchErrors";
```
교체 후:
```ts
import { researchErrorMessage } from "~/utils/researchErrors";
```

교체 전:
```ts
const { startResearch } = useResearchStarter();
const pdfBase = apiUrl("/books");
```
교체 후:
```ts
const { startResearch } = useResearchStarter();
```

교체 전:
```ts
const pdf = ref<OpenPdfPayload | null>(null);

// 확인 요청의 HTTP 상태. 요청 자체가 실패하면 null
async function pdfStatus(cntsId: string): Promise<number | null> {
  const ctrl = new AbortController();
  try {
    const res = await fetch(`${pdfBase}/${encodeURIComponent(cntsId)}/pdf`, { headers: apiHeaders(), signal: ctrl.signal });
    return res.status;
  } catch {
    return null;
  } finally {
    // 본문은 필요 없다 — 뷰어가 다시 받는다. 끊지 않으면 PDF 전체를 두 번 내려받는다
    ctrl.abort();
  }
}

async function openPdf(target: OpenPdfPayload): Promise<void> {
  const problem = pdfCheckProblem(await pdfStatus(target.cntsId));
  if (problem) showToast(problem);
  else pdf.value = target;
}
```
교체 후:
```ts
const pdfOpener = usePdfOpener();
const { pdf, closePdf } = pdfOpener;

async function openPdf(target: OpenPdfPayload): Promise<void> {
  const problem = await pdfOpener.openPdf(target);
  if (problem) showToast(problem);
}
```

- [ ] **Step 6: 논문 상세 템플릿 — 원문 보기는 늘 뷰어로, KCI 는 보조 링크, 배너의 [인용 대목 보기]** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```vue
                <a
                  v-if="paper.url"
                  :href="paper.url"
                  target="_blank"
                  rel="noopener"
                  class="skx-btn-pview-sm"
                  >원문 보기</a
                >
                <button
                  v-else
                  type="button"
                  class="skx-btn-pview-sm"
                  @click="pdfModal = true"
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
              </div>
```
교체 후:
```vue
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
```

교체 전:
```vue
              <span aria-hidden="true">·</span> 인용 대목 {{ cite.chunks.length }}곳
            </p>
          </div>
        </section>
```
교체 후:
```vue
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
```

교체 전:
```vue
    <!-- PDF 뷰어 모달 -->
    <PdfViewer
      v-if="pdfModal"
      :cnts-id="paperId"
      :title="paper?.title"
      @close="pdfModal = false"
    />
```
교체 후:
```vue
    <!-- PDF 뷰어 모달 -->
    <PdfViewer
      v-if="pdf"
      :cnts-id="pdf.cntsId"
      :title="pdf.title"
      :page="pdf.page"
      :passages="pdf.passages"
      @close="closePdf"
    />
```

- [ ] **Step 7: 논문 상세 스크립트 — 가져오기·`pdfModal` 제거·열기 함수** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```ts
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useResearchApi } from "~/composables/useResearch";
import type { ResearchJob } from "~/types/research";
```
교체 후:
```ts
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { usePdfOpener } from "~/composables/usePdfOpener";
import { useResearchApi } from "~/composables/useResearch";
import type { ReportChunk, ResearchJob } from "~/types/research";
```

교체 전:
```ts
import { citeContext, summaryQuestion, withRo, type CiteContext } from "~/utils/paperDetail";
import { isPlainClick } from "~/utils/restorePosition";
```
교체 후:
```ts
import { citeContext, summaryQuestion, withRo, type CiteContext } from "~/utils/paperDetail";
import { citedPdfTarget } from "~/utils/pdfViewer";
import { isPlainClick } from "~/utils/restorePosition";
```

교체 전:
```ts
const citationModal = ref(false);
const pdfModal = ref(false);
const toast = ref("");
```
교체 후:
```ts
const citationModal = ref(false);
const toast = ref("");
```

교체 전:
```ts
function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

async function fetchPaper() {
```
교체 후:
```ts
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

async function openOriginal() {
  pdfProblem.value = (await openPdf({ cntsId: paperId, title: paper.value?.title ?? "" })) ?? "";
}

// 첫 인용 쪽에서 열고 머리의 "인용 대목 n/N" 으로 대목을 넘겨 본다
async function openCitedPassages(chunks: readonly ReportChunk[]) {
  bannerPdfProblem.value = (await openPdf(citedPdfTarget(paperId, paper.value?.title ?? "", chunks))) ?? "";
}

async function fetchPaper() {
```

- [ ] **Step 8: 논문 상세 스타일** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지) — scoped 스타일 끝의 `@media` 앞

교체 전:
```css
@media (prefers-reduced-motion: reduce) {
  .pd-keyword {
    transition: none;
  }
}
</style>
```
교체 후:
```css
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
@media (prefers-reduced-motion: reduce) {
  .pd-keyword {
    transition: none;
  }
}
</style>
```

- [ ] **Step 9: 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: 실패 0건(이 태스크는 테스트 수를 바꾸지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && grep -n "pdfBase\|function pdfStatus\|pdfCheckProblem" "frontend/pages/research/[id].vue"`
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && grep -n "pdfModal" "frontend/pages/papers/[id].vue"`
Expected: 출력 없음 — 원문 보기가 확인을 건너뛰는 길이 없다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && grep -c "v-html" frontend/components/PdfViewer.vue`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && git diff d7f7e95..HEAD --stat -- app`
Expected: 출력 없음

- [ ] **Step 10: 화면 확인(선택, `frontend-prod-api`)** — spec §7 ⑩

- 상세 → [원문 보기]
  - 뷰어가 뜨고, 닫기 버튼에 초점이 가고, 머리에 "n / N쪽"이 보인다. ‹ › 로 쪽이 넘어간다.
  - Esc 로 닫힌다. 뷰어 안을 한 번 누른 뒤 Esc 를 눌러도 닫힌다. Ctrl+F 로 찾기 막대를 연 뒤에는 첫 Esc 가 찾기 막대만 닫는다.
  - 닫으면 [원문 보기]에 초점이 돌아온다.
  - 열려 있는 동안 배경 위에서 휠을 굴려도 배경이 움직이지 않는다. Tab 이 배경으로 나가지 않는다.
- PDF 가 없는 논문 → 버튼 아래에 "원문 파일이 없습니다 KCI에서 원문 페이지 열기"가 뜨고, 뷰어는 열리지 않는다.
- 보고서에서 온 상세의 배너 [인용 대목 보기] → 첫 인용 쪽에서 열리고 머리에 "인용 대목 1/N · p.…"가 보이며 ‹ › 로 대목을 넘긴다(쪽 정보가 없는 대목은 쪽을 옮기지 않는다).
- 딥리서치 인용칩 → [원문 보기]
  - 그 대목의 쪽에서 열린다.
  - Esc 로 닫으면 칩(또는 팝오버의 [원문 보기])에 초점이 돌아온다.
  - 없는 원문이면 지금처럼 토스트가 뜬다.

- [ ] **Step 11: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/composables/usePdfOpener.ts frontend/components/PdfViewer.vue "frontend/pages/research/[id].vue" "frontend/pages/papers/[id].vue" && git commit -m "[Feat] round05a — 원문 뷰어에 Esc 닫기·초점 되돌리기·배경 고정과 쪽 표시·쪽 넘기기·인용 대목 넘기기를 더하고, 열기 전 확인을 usePdfOpener 로 모아 논문 상세 원문 보기를 늘 뷰어로 연다(없으면 버튼 아래 안내, KCI 는 보조 링크). 인용 맥락 배너의 [인용 대목 보기]는 첫 인용 쪽에서 열고 대목을 넘겨 본다"
```

---

## 단계 4 — 이 논문으로 딥리서치 (Task 12, 선택)

- spec §5 ⑧. "시간이 되면" 하는 마지막 기능 태스크다.

### Task 12 (선택·마지막 기능 태스크): 이 논문으로 딥리서치 — 질문 초안을 논문 검색 입력창에 칩과 함께 (§5 ⑧)

spec §5 ⑧ 은 "시간이 되면" 하는 선택 항목이다. 건너뛰면 Task 13 의 누적 수에서 이 태스크 몫(파일 1 · 테스트 6)을 뺀다.

계약 추가:
- `utils/paperResearch.ts`: `paperResearchQuestion(title, keywords)`, `paperResearchUrl(question)`, `readResearchDraft(query)`.
- `components/research/SearchPlusMenu.vue`: `defineExpose({ activateMode(id: SearchModeId) })`.
- `/papers` 가 받는 쿼리 키 `draft`(채운 뒤 주소에서 지운다).

선행: Task 8(상세의 `keywords` computed 는 이름 그대로 쓴다), Task 11(상세의 import 줄 `citedPdfTarget`), Task 5(`pages/papers/index.vue` 의 import 줄 — 겹치지 않는다).

**Files:**
- Create: `frontend/utils/paperResearch.ts`
- Test: `frontend/tests/unit/paperResearch.test.ts`
- Modify: `frontend/components/research/SearchPlusMenu.vue` (`clear` 다음)
- Modify: `frontend/pages/papers/index.vue` (랜딩 입력창 ref·import·`goLanding` 뒤·`restoreFromQuery` 의 랜딩 분기)
- Modify: `frontend/pages/papers/[id].vue` (연관 논문 절 뒤·`keywords` 뒤·import·`<style scoped>`)

- [ ] **Step 1: 실패하는 테스트** — `frontend/tests/unit/paperResearch.test.ts` (새 파일)

```ts
// frontend/tests/unit/paperResearch.test.ts
import { describe, expect, it } from "vitest";
import { paperResearchQuestion, paperResearchUrl, readResearchDraft } from "~/utils/paperResearch";
import { questionProblem } from "~/utils/researchInput";

describe("paperResearchQuestion", () => {
  it("제목과 앞 키워드 세 개로 질문 초안을 만든다", () => {
    expect(paperResearchQuestion(" 청소년  SNS 이용과 우울 ", ["SNS", " 우울 ", "", "청소년", "패널"])).toBe(
      "「청소년 SNS 이용과 우울」에서 출발해, SNS·우울·청소년 관련 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?",
    );
  });

  it("키워드가 없으면 제목만으로 묻는다", () => {
    expect(paperResearchQuestion("공공도서관 이용 행태", [])).toBe(
      "「공공도서관 이용 행태」에서 출발해, 이 주제의 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?",
    );
  });

  it("제목이 없으면 초안을 만들지 않는다", () => {
    expect(paperResearchQuestion("  ", ["키워드"])).toBe("");
  });

  it("긴 제목·키워드는 잘라 서버 질문 한도 안에 둔다", () => {
    const q = paperResearchQuestion("가".repeat(400), ["나".repeat(100), "다".repeat(100), "라".repeat(100)]);
    expect(q).toContain(`「${"가".repeat(120)}…」`);
    expect(q).toContain(`${"나".repeat(30)}…·`);
    expect(questionProblem(q)).toBeNull();
  });
});

describe("paperResearchUrl · readResearchDraft", () => {
  it("주소에 실은 초안을 그대로 읽는다", () => {
    const q = "「제목 & 부제」에서 출발해, 이 주제의 선행 연구는?";
    const url = new URL(paperResearchUrl(q), "http://x");
    expect(url.pathname).toBe("/papers");
    expect(readResearchDraft(Object.fromEntries(url.searchParams))).toBe(q);
  });

  it("없거나 빈 값이면 null, 배열이면 첫 값", () => {
    expect(readResearchDraft({})).toBeNull();
    expect(readResearchDraft({ draft: "  " })).toBeNull();
    expect(readResearchDraft({ draft: [" 질문 ", "다른"] })).toBe("질문");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/paperResearch.test.ts`
Expected: FAIL — `Error: Cannot find module '~/utils/paperResearch' imported from '…/tests/unit/paperResearch.test.ts'.` · `Test Files  1 failed (1)` · `Tests  no tests`

- [ ] **Step 3: 최소 구현** — `frontend/utils/paperResearch.ts` (새 파일)

```ts
// frontend/utils/paperResearch.ts
// 논문 상세의 [이 논문으로 딥리서치] — 제목·키워드로 질문 초안을 만들어 논문 검색 입력창으로 넘긴다

// 부제까지 붙은 긴 제목이나 문장형 키워드가 질문을 다 차지하지 않게 자른다(서버 한도 QUESTION_MAX 500자 안쪽)
const TITLE_MAX = 120;
const KEYWORD_MAX = 30;
const KEYWORDS = 3;

// 파이썬 len 과 같게 코드포인트로 센다(researchInput 과 같은 이유)
function clip(text: string, max: number): string {
  const chars = [...text];
  return chars.length > max ? `${chars.slice(0, max).join("")}…` : text;
}

// 조사(을/를·와/과)는 앞 글자의 받침에 따라 바뀐다 — 제목·키워드 바로 뒤에는 받침과 무관한 말만 붙인다
export function paperResearchQuestion(title: string, keywords: readonly string[]): string {
  const name = title.trim().replace(/\s+/g, " ");
  if (!name) return "";
  const picked = keywords
    .map((k) => k.trim())
    .filter(Boolean)
    .slice(0, KEYWORDS)
    .map((k) => clip(k, KEYWORD_MAX));
  const topic = picked.length ? `${picked.join("·")} 관련` : "이 주제의";
  return `「${clip(name, TITLE_MAX)}」에서 출발해, ${topic} 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?`;
}

export function paperResearchUrl(question: string): string {
  return `/papers?${new URLSearchParams({ draft: question })}`;
}

// /papers 가 받는 질문 초안(?draft=). 없거나 빈 값이면 null
export function readResearchDraft(query: Record<string, unknown>): string | null {
  const raw = Array.isArray(query.draft) ? query.draft[0] : query.draft;
  return typeof raw === "string" && raw.trim() ? raw.trim() : null;
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/paperResearch.test.ts`
Expected: `Test Files  1 passed (1)` · `Tests  6 passed (6)`

- [ ] **Step 5: 입력창 컴포넌트가 밖에서 칩을 켤 수 있게** — `frontend/components/research/SearchPlusMenu.vue` (Edit, CRLF 유지)

교체 전:
```ts
function clear(): void {
  active.value = null;
  error.value = "";
  if (field) field.placeholder = basePlaceholder;
  field?.focus();
}
```
교체 후:
```ts
function clear(): void {
  active.value = null;
  error.value = "";
  if (field) field.placeholder = basePlaceholder;
  field?.focus();
}

// 페이지가 칩을 켠 채 입력창을 채울 때 쓴다(논문 상세의 [이 논문으로 딥리서치]가 넘긴 질문 초안).
// 초안은 고쳐 쓰라고 주는 것이라 초점을 글 끝에 둔다
function activateMode(id: SearchModeId): void {
  const mode = modeFor(id);
  if (!mode) return;
  activate(mode);
  if (!field) return;
  field.focus();
  field.setSelectionRange(field.value.length, field.value.length);
}

defineExpose({ activateMode });
```

- [ ] **Step 6: `/papers` 가 초안을 받아 랜딩 입력창에 채우게** — `frontend/pages/papers/index.vue` (Edit, CRLF 유지)

교체 전:
```vue
            <ResearchSearchPlusMenu v-model="currentQuery" kind="paper" :disabled="loading" />
```
교체 후:
```vue
            <ResearchSearchPlusMenu ref="plusMenu" v-model="currentQuery" kind="paper" :disabled="loading" />
```

교체 전:
```ts
import { awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import type { BookSearchResponse, BookChunkGroup } from "~/types/search";
```
교체 후:
```ts
import { awaitsV1Map, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import { readResearchDraft } from "~/utils/paperResearch";
import type { SearchModeId } from "~/utils/slashCommand";
import type { BookSearchResponse, BookChunkGroup } from "~/types/search";
```

교체 전:
```ts
  pdfItem.value = null;
  citeModalOpen.value = false;
  chatPaperId.value = null;
}
```
교체 후:
```ts
  pdfItem.value = null;
  citeModalOpen.value = false;
  chatPaperId.value = null;
}

// 논문 상세의 [이 논문으로 딥리서치]가 넘긴 질문 초안(?draft=) — 검색하지 않고 랜딩 입력창에 딥리서치 칩을
// 켠 채 채운다. 주소에서는 지운다: 남겨 두면 새로고침·뒤로 가기로 올 때마다 고쳐 쓰던 글을 초안이 다시 덮는다
const plusMenu = ref<{ activateMode: (id: SearchModeId) => void } | null>(null);

function fillResearchDraft() {
  const draft = readResearchDraft(route.query);
  if (!draft) return;
  router.replace({ query: {} });
  currentQuery.value = draft;
  // 입력창 값이 바뀐 뒤에 켜야 초점이 글 끝에 간다
  nextTick(() => plusMenu.value?.activateMode("deep-research"));
}
```

`router.replace({ query: {} })` 로 `draft` 만 지우면 `h`·`q` 감시는 값이 그대로(둘 다 없음)라 다시 돌지 않는다.

교체 전:
```ts
      // 뒤로가기 등) 결과 화면과 진행 중인 요청을 직접 걷는다. 안 걷으면 주소는 '/papers' 인데 결과가 남는다
      goLanding();
      return;
```
교체 후:
```ts
      // 뒤로가기 등) 결과 화면과 진행 중인 요청을 직접 걷는다. 안 걷으면 주소는 '/papers' 인데 결과가 남는다
      goLanding();
      fillResearchDraft();
      return;
```

- [ ] **Step 7: 상세에 칸을 더한다** — `frontend/pages/papers/[id].vue` (Edit, CRLF 유지)

교체 전:
```vue
                </div>
              </article>
            </div>
          </section>
        </template>
      </main>
```
교체 후:
```vue
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
```

교체 전:
```ts
import { citedPdfTarget } from "~/utils/pdfViewer";
```
교체 후:
```ts
import { paperResearchQuestion, paperResearchUrl } from "~/utils/paperResearch";
import { citedPdfTarget } from "~/utils/pdfViewer";
```

교체 전:
```ts
  // 4. 레거시 summary 내장 키워드 섹션
  if (typeof paper.value?.summary === "string" && paper.value.summary) {
    return parseLegacySummary(paper.value.summary).keywords;
  }
  return [];
});
```
교체 후:
```ts
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
```

교체 전:
```css
@media (prefers-reduced-motion: reduce) {
  .pd-keyword {
    transition: none;
  }
}
</style>
```
교체 후:
```css
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
```

- [ ] **Step 8: 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: 실패 0건(누적 기대치 표의 Task 12 줄)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI && git diff d7f7e95..HEAD --stat -- app`
Expected: 출력 없음

수동 확인(선택, `frontend-prod-api`):
- 상세 아래 "이 논문으로 딥리서치"에 초안이 보인다.
- [입력창에서 고쳐 쓰고 시작하기]를 누르면 `/papers` 로 간다.
  - 주소는 `?draft` 가 지워진 `/papers` 다.
  - 입력창에 초안이 채워지고, 딥리서치 칩이 켜지고, placeholder 는 "연구 질문을 입력하세요"다.
  - 초점은 글 끝에 있다. 고쳐 쓴 뒤 엔터를 치면 딥리서치가 시작된다.
- 뒤로 가기를 누르면 상세로 돌아온다.
- 주의: dev 서버를 처음 띄우고 처음 들어가면 Vite 의 의존성 최적화가 페이지를 한 번 새로고침한다. 그러면 이미 `draft` 를 지운 주소로 다시 그려 입력창이 비어 보인다. 실제 동작 문제가 아니므로 수동 확인은 한 번 들어갔다 나온 뒤에 한다.

- [ ] **Step 9: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/utils/paperResearch.ts frontend/tests/unit/paperResearch.test.ts frontend/components/research/SearchPlusMenu.vue frontend/pages/papers/index.vue "frontend/pages/papers/[id].vue" && git commit -m "[Feat] round05a — 논문 상세에 이 논문으로 딥리서치를 더한다: 제목·키워드로 만든 질문 초안을 논문 검색 입력창에 딥리서치 칩을 켠 채 채우고(바로 시작하지 않고 고쳐 보내게), 초안 주소(?draft)는 채운 뒤 지운다"
```

---

## 단계 5 — 최종 확인 (Task 13)

### Task 13: 최종 확인과 spec 상태 갱신

**Files:**
- Modify: `docs/superpowers/specs/2026-10-01-round05a-paper-detail-design.md` (3행 머리 상태 줄)

- [ ] **Step 1: 프론트 전체 테스트·타입검사·빌드**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1
```
기대 출력:
- vitest: `Test Files  27 passed (27)`, `Tests  469 passed (469)`(기준선 21 / 406). Task 12 를 건너뛰었으면 `26 passed (26)`, `463 passed (463)`.
- typecheck: 출력 없음.
- build: `└  ✨ Build complete!`.

- [ ] **Step 2: 백엔드 무변경 확인과 백엔드 전체 테스트**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git diff d7f7e95..HEAD --stat -- app
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력:
- 첫 명령: 출력 없음(D9 — 백엔드 변경 없음).
- 둘째 명령: `890 passed`(경고 2건은 기존 것). 백엔드를 바꾸지 않았으니 기준선(d7f7e95)과 같은 수다. 뺀 3개 파일은 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 죽는다(이 계획과 무관).

- [ ] **Step 3: 커밋 저자·트레일러 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git log --format='%h %an <%ae> %s' d7f7e95..HEAD
git log --format=%B d7f7e95..HEAD | grep -ciE "co-authored-by|generated with claude"
```
기대:
- 첫 명령: 계획 문서 커밋(`[Docs] round05a — 논문 상세 재구현 구현 계획`)과 Task 1~12 커밋 12개(Task 12 를 건너뛰었으면 11개)가 모두 저장소 사용자(`git config user.name` — Hyonii) 이름으로 나온다. 그 사이에 다른 커밋(검토 반영·수정 커밋 등)이 끼었으면 그것도 같은 저자여야 한다.
- 둘째 명령: `0`.
- 하나라도 트레일러가 나오면 멈추고 사용자에게 알린다. 이미 쌓인 커밋의 메시지를 고치려면 사용자 승인 아래 비대화형 rebase 가 필요하다.

- [ ] **Step 4: spec 머리 상태 줄 갱신** — `docs/superpowers/specs/2026-10-01-round05a-paper-detail-design.md` (Edit, 원래 줄바꿈 유지)

교체 전:
```markdown
> 상태: 설계 확정(2026-10-01, 사용자 승인 — A안) · 구현 전
```
교체 후:
```markdown
> 상태: 설계 확정(2026-10-01, 사용자 승인 — A안) · 구현 완료(운영 배포 전)
```

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && git add docs/superpowers/specs/2026-10-01-round05a-paper-detail-design.md && git commit -m "[Docs] round05a — spec 상태를 구현 완료(운영 배포 전)로 고친다: 상세 주소의 출처·돌아갈 자리, 돌아가기와 보던 위치 복원, 사이드바 강조, 03 화면(배너·DeepRead·원문 보기 통일·AI 요약 기준과 캐시·키워드 검색·연관 논문 링크·탭 제목·이 논문으로 딥리서치), 원문 뷰어(Esc·초점·쪽 표시·인용 대목 넘기기·열기 전 확인) 구현, 프론트 vitest·타입검사·빌드와 백엔드 전체 pytest 통과(백엔드 변경 없음)"
```

Task 12 를 건너뛰었으면 메시지의 "·이 논문으로 딥리서치" 를 뺀다.

- [ ] **Step 6: 남은 일 알리기(이 계획에서 실행하지 않는다)**

사용자에게 다음을 알린다.
- 화면 확인(spec §7 화면 ①~⑪): 운영 API 미리보기 `frontend-prod-api` 로 아래 수동 목록을 본다. 각 태스크의 "화면 확인" 항목을 모은 것이다.
  - ① 보고서 중간의 인용칩 → [논문 상세] → [딥리서치 보고서로]: 그 칩이 떠날 때와 같은 화면 높이에 오고 팝오버가 열린다. 주소에서 `at`·`y` 가 빠진다.
  - ② 같은 흐름을 [딥리서치 보고서로] 대신 브라우저 뒤로 가기로 해도 ①과 같다.
  - ③ 상세 → 연관 논문 2편 → [딥리서치 보고서로]: 처음 누른 칩 자리로 간다. 연관 논문 주소에는 `e` 가 없고 `at`·`y` 는 처음 것이다.
  - ④ 보고서·탐색 타임라인의 "제외한 논문"을 새 탭으로 열고 그 탭에서 [딥리서치 보고서로]: 접힌 제외 목록·회차가 펼쳐진 채 그 항목이 같은 높이에 온다.
  - ⑤ 검색 결과 둘째 쪽 중간의 카드 → 상세 → [검색 결과로]: `/papers/search` 요청 없이(`/api/history/<h>` 한 번) 둘째 쪽이 열리고 그 카드가 같은 높이에 온다.
  - ⑥ 메인 화면 논문 탭에서 검색(`/papers` 로 넘어간다) → 카드 → 상세 → [검색 결과로]: ⑤와 같다.
  - ⑦ 주소 직접 입력(`/papers/<id>`): 돌아가기 문구가 "검색으로"이고 누르면 홈으로 간다.
  - ⑧ 사이드바: 보고서에서 온 상세는 딥리서치 탭과 그 보고서, 검색에서 온 상세는 논문 탭과 그 기록을 강조한다. 탭 제목은 "논문 제목 — 논문"이다.
  - ⑨ 상세 → 다른 화면 → 뒤로 → 앞으로: 네트워크 탭에 `/papers/reason/stream`·`/papers/related-reason/stream` 요청이 다시 나가지 않는다.
  - ⑩ 원문 뷰어: Esc 로 닫힌다(뷰어 안을 누른 뒤에도). 닫으면 연 버튼으로 초점이 돌아온다. 머리의 쪽 표시·쪽 넘기기, 배너 [인용 대목 보기]의 인용 대목 넘기기, PDF 없는 논문의 안내를 본다(Task 11 Step 10).
  - ⑪ 딥리서치 화면의 ①·④를 배치 A(2단)와 B(한 줄) 둘 다에서 본다. 상세에 있는 동안 창 폭을 바꿔 배치가 바뀌어도 같은 요소 자리로 돌아와야 한다.
- 운영 배포(spec §9): `nl-lib-nuxt` 이미지 빌드·푸시 → 서버 pull → Recreate(Portainer re-pull 끔) → `docker exec nl-lib-gateway nginx -s reload`. 공유 운영 서버라 **사용자 승인 뒤** 한다.
- 라운드 마무리(완료노트·교본·dev 머지)는 라운드 종료 절차(`GIT_WORKFLOW.md`, `.claude/skills/round-finish/SKILL.md`)를 따른다.

---

## 이 계획에서 다루지 않는 것

- 03-1 도서 상세의 같은 문제(돌아가기·위치) — spec §8. 같은 유틸(`detailSource`·`useRestorePosition`)을 쓸 수 있게 만들었지만 적용은 다음 라운드다.
- 대목 위치 강조(pdf.js 검색)와 pdf.js 기본 도구 줄 정리 — spec §6·§8. 그래서 머리의 쪽 표시와 pdf.js 도구 줄의 쪽 입력칸이 함께 보인다.
- 인용칩 팝오버의 [원문 보기]에 그 절의 대목 목록(passages)을 넘기는 것 — 지금은 쪽만 넘긴다. 대목 넘기기는 상세 배너의 [인용 대목 보기]만 쓴다.
- 검색 결과 화면 오른쪽 "AI 분석 결과" 참고 논문 목록에서 연 상세의 자리 복원 — 결과 카드(`p-<cnts>`)만 자리를 싣는다.
- 메인 화면(`pages/index.vue`) 논문 분기의 앵커·복원 — 그 분기는 지금 실행될 수 없는 코드라 주소 형식만 맞췄다(Task 5 참고).
- 배치 A 에서 진행 패널(자체 스크롤)에만 있는 제외 논문의 자리 — 복원은 창 스크롤만 움직인다. 보고서에 같은 항목이 있으면(round04c 뒤의 보고서·작성 중 초안) DOM 순서상 보고서 쪽 항목으로 맞추므로, 제외 목록이 없는 옛 보고서만 해당한다.
- AI 글 캐시의 만료·용량 관리 — sessionStorage 라 탭을 닫으면 사라지고, 용량을 넘으면 캐시 없이 새로 만든다.
- 백엔드 변경, 운영 배포(spec §9), 화면 확인(spec §7 화면 ①~⑪) — 배포는 사용자 승인 뒤 따로 한다.
