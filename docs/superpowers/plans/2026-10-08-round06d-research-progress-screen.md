# round06 06d 진행 화면·입구 — 처음부터 2단·큰 진행 막대·절 따라가기·탐색 중 움직임·입구 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** round06 세 줄 병렬(06c 질의 ∥ 06d 진행 화면·입구 ∥ 06e 연구 어시스턴트) 가운데 06d 줄 — spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` §12-3·D22·D26. 회의 뒤 결정 "인터랙티브·다이내믹, 진행이 뿅뿅 보이게"를 딥리서치 진행 화면에 넣는다: 넓은 화면은 처음부터 2단(A), 화면 위에 고정한 **크게 보이는 진행 막대 하나**(Q1 — 작은 단계 표시·막대 위 큰 글줄·오른쪽 퍼센트, 탐색 중에도 같은 막대), 지금 진행하는 절을 스크롤이 따라가고 사용자가 스크롤하면 멈추고 '↓ 지금 쓰는 곳으로' 알약, 탐색 중 본문의 하위질문별 절 자리('근거 N편 ✓'), 진행 패널 회차 줄의 '자기점검 중'·'재검색 중', 06c 탐색 후보 이벤트로 근거 장부에 '검토 중' 더미(Q9). 입구(D26)는 `/research` 홈(새 연구·진행 중·내 연구·예시 연구), 사이드바 이어간 연구 줄의 단계와 '모두 보기 (N)', 논문 빠른검색 [딥리서치로 더 깊게]·[담기 ▾], '도서검색' → '소장자료검색' 문구다. 06b 이월 §7-1(대기 카드 가로 배치)·§7-5(`queueLine` 다시 내보내기)와 06c 의 "이렇게 이해했어요" 바인딩 두 곳을 함께 한다. 06c 판정 뒤 사용자 결정(2026-10-12, spec D28)으로 딥리서치를 시작할 때 고르는 '탐색 방식'(폭넓게 · 정밀하게, 기본 정밀하게 — 고른 방식을 잡 params `broaden`·`query_context` 두 칸으로 싣는다)도 넣는다(Task N9). **nuxt 만이다** — 백엔드·스키마 변경 없음. 06c 운영 배포(10/13~14) 뒤에만 `dev` 에 머지하고 10/17~18 에 nuxt 로 배포한다.

**Architecture:** 판단은 모두 `utils/*.ts` 순수 함수(`researchProgress`·`planSlots`·`researchFollow`·`sidebarResearch`·`researchHome`·`addToWork`·`researchMode`)에 두고 vitest 로 잰다 — `.vue` 는 그 결과를 그리기만 한다(프론트 vitest 는 node 환경이라 컴포넌트를 그리지 못한다). 연구 화면 `pages/research/[id].vue` 한 곳이 진행 막대 보기(`barView`)·절 자리(`planSlotList`)·따라가기(`useSectionFollow`)를 만든다. 고정 진행 영역은 `ResearchHeader` 아래 `position: sticky; top: 0` 의 새 `ResearchProgressBar.vue` 하나이고, 높이를 CSS 토큰으로 고정해(값은 `:root` 의 `--rs-bar-area-h` 한 곳, `.rs-page` 의 `--rs-bar-h` 는 막대가 서 있으면 그 값·없으면 `0px`) A 옆 칸 `top`·문서 스크롤 칸(html)의 `scroll-padding-top`(초점 이동·절 이동 `scrollIntoView`·#조각 이동 — D4 품질 검토 반영)·위치 복원 inset 이 같은 값을 읽는다. 퍼센트는 탐색 111 : 작성 91(round06a 실측) 가중 전체 진행이라 작성이 시작돼도 뒤로 가지 않고, 탐색 비율은 하위질문 몫 + 열린 회차의 다가감(반감기 6초, 상한 `RUNNING_CAP` 0.9)이다. 따라가기는 사용자 입력 이벤트(세로 휠·터치 이동·스크롤 키·페이지 스크롤바 누르기)로만 멈추고 `scroll` 이벤트로 가르지 않는다. 탐색 후보는 06c 의 SSE `candidates` 를 리듀서가 `SubqView.reviewing?` 으로 받아 `ledgerFrom` 의 세 번째 묶음 '검토 중'으로 그리고, 같은 하위질문의 점검(`critique`)·스냅숏과 잡 종료(종료 이벤트·끝난 잡으로 다시 맞추는 `refreshView`)가 지운다. 입구는 history 목록 응답의 `total?`(06e fastapi — 없으면 N 없이)을 `useHistory().totalOf(kind)` 로 받고, `/research` 홈은 history 를 50건씩 직접 읽으며 예시 연구는 `GET /api/research-works?example=1` + `GET /api/research/{id}/work` 의 `corpus` 로 실행 시각·범위를 보인다. [담기] 는 `PUT /api/research/{job}/reading/{cnts_id}` 본문 `{"state": "in"}` 이다. 탐색 방식은 `utils/researchMode.ts` 가 고른 방식 → 잡 params 두 칸을 정하고 새 `ResearchModePicker.vue`(radiogroup)를 + 메뉴(`SearchPlusMenu.vue`)와 `/research` 홈이 쓴다 — 서버 기본값이 0 이라 화면이 늘 두 칸을 함께 싣고(`useResearchStarter().startResearch(question, params)`), 연구 화면 머리가 그 잡의 방식을 보인다. 06e 파일(`WorkStepper.vue`·`workPhase.ts`·`researchErrors.ts`·`useResearchWork.ts`·`BookChat.vue`·`[id].vue:57-75`)은 읽기만 한다.

**Tech Stack:** Nuxt 4(4.4)·Vue 3.5·TypeScript, vitest 3.2(node 환경 — DOM 없음), `nuxi typecheck`(vue-tsc), CSS(`assets/css/research.css` 와 `work.css` 의 근거 장부 블록 — `--skx-*` 토큰만), SSE(`/api/research/{id}/stream`). 백엔드(Python 3.11·FastAPI·pytest)는 고치지 않고 회귀로만 돌린다.

---

## 설계 정본과 이 계획의 자리

- **설계 정본:** `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` — §12-3(06d 진행 화면·입구 — 이 줄의 절), §12-5(파일 경계·같은 파일 순서), §12-6(일정·머지 문·자르는 순서·배포), §12-7(06d vitest 목록·운영 확인), §12-8(장면 1 '근거가 떨어지며 보고서가 자란다'), 결정 D22(진행 화면)·D26(입구)·D17([담기] 는 이어간 연구에만), §12-10 Q1(큰 진행 막대 — 해결)·Q8(spec 의 판단 모두 동의 — 해결)·Q9(탐색 후보 목록 이벤트 — 넣음). 형식·관례 정본은 06b 계획 `docs/superpowers/plans/2026-10-06-round06b-vertical-slice.md`(머리 규칙·Task 형식·보강 6 의 같은 파일 사슬 규칙·Task 37 배포 절차)다.
- **이 계획서:** `docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md`. 완료노트·00_status 가 이 경로를 적는다.
- **열린 질문의 상태(2026-10-08):** Q1·Q7·Q8·Q9 는 해결됐다. Q1 은 이 줄의 몫이다 — 막대 두께 `--rs-bar-thick: 1rem`(768px 이하 `0.75rem`), 막대 위 큰 글줄 1rem 굵게('보고서 작성 중 · 3/6절 — 「절 제목」' / '근거 수집 중 · 하위질문 3/6 — 「하위질문」'), 오른쪽 퍼센트 1.25rem 굵게, 그 위 작은 단계 표시(계획 · 근거 수집 · 보고서 작성 · 완료), 탐색 중에도 같은 막대. Q2(마지막 단계 이름 — 답이 없으면 '보고서')·Q3(근거 칩 — 답이 없으면 주제 카드만 S)은 06e 몫이고, 06d 사이드바는 단계 이름을 `utils/workPhase.ts` 에서 읽어 06e 의 이름 바꾸기를 따라간다(정함 13). Q4 는 06c 판정 몫이었고 2026-10-12 에 해결됐다 — 서버 기본값 0 그대로, 사용자가 고르는 탐색 방식(D28)을 06d 가 넣는다(Task N9 — 아래 '10-12 사용자 결정' 줄). 06d 는 그 결과로 랜딩 논문 예시 셋도 다시 본다(Task Z2·Z6). Q5·Q6 은 시연·리허설.
- **10-11 사용자 확인 — Q1 막대는 보고서 화면에도:** 사용자 "보고서 화면에도 넣으라고 한 것이 맞아". 큰 진행 막대는 06d 딥리서치 진행 화면만이 아니라 06e 자동 보고서 화면(이어간 연구의 보고서 단계 `?s=proposal` — `ProposalStep.vue`, 절을 차례로 쓰는 중)에도 선다. **그 막대는 06e 몫이다**(06e 계획 정함 28 — `ProposalStep.vue` 의 `.wk-rbar`, `work.css` 토큰 `--wk-bar-thick`, 계산 `reportBar`). 06d 의 고정 막대(`.rs-pbar`)는 단계 화면에서 서지 않으므로(`showsProgressBar(phase, stepMode)` — Task D3 테스트) 한 화면에 큰 막대 둘이 서지 않는다. 두 막대는 Q1 치수(두께 1rem·768px 이하 0.75rem, 큰 글줄 1rem 굵게, 퍼센트 1.25rem 굵게)를 **값으로만** 맞춘다 — 06d 는 `.wk-rbar`·`--wk-bar-thick` 를 정의하지 않고(Task Z1 Step 2 가 확인), 06e 는 `--rs-bar-thick` 를 import 하지 않는다. 06d 의 Task·테스트 수는 이 확인으로 바뀌지 않는다.
- **§12-11 '계획에서 정할 것' 중 이 줄에 걸린 것 — 권고대로 정했다(정함(권고)):** '탐색 중 읽기 전용 PlanCard 를 절 자리가 대신할지·옆 칸 폭' → 대신한다(지운다), 옆 칸 폭 17rem 그대로(정함 9 · Task L2). ''소장자료검색'으로 맞출 다른 문구' → 입력창 안내(`pages/index.vue:82`)와 사이드바 기록 탭(`AppSidebar.vue:150` '도서')·그 탭의 빈/지우기 문구까지 맞춘다(정함 18 · Task N1). 선택 항목 '연구 맥락을 반영한 딥리드 첫 화면'은 **하지 않는다**(06e 범위이기도 하다). 나머지 §12-11 항목은 06e 몫이다.
- **10-12 사용자 결정 — 탐색 방식(spec D28):** 06c 두 갈래 판정 뒤 사용자 "응 넣자. 정확하게로 가자. 탐색 방식: 폭넓게 · 정밀하게 로 가자"(06c 완료노트 §5-4). 서버 기본값(`DEFAULT_PARAMS` `broaden` 0 · `query_context` 0)은 그대로 두고(기본값 커밋 없음), 딥리서치를 시작하는 자리에 '탐색 방식' 선택지(폭넓게 = 두 칸 0 · 정밀하게 = 두 칸 1, 기본 정밀하게)를 06d 가 넣는다 — spec §12-3 이 '자리·모양은 06d 계획이 정한다' 로 넘겼고, 이 계획이 정함 19 와 Task N9 로 정했다. 백엔드 변경은 없다. 이 줄과 Task N9 는 06c 배포 기록 브랜치(`docs/round06c-deploy-record`)에서 더했다.

---

## 실행 전 알아 둘 것

- **작업 위치:** worktree `C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d`(브랜치 `feat/round06d-research-progress-screen`) — Task 0 이 **그때의 `dev`** 에서 만든다. 모든 명령은 이 경로의 절대 경로로 쓴다. 저장소 루트 폴더(본 작업 폴더)와 다른 worktree(`.worktrees/round06-spec`·`round06c`·`round06e` 등)는 고치지 않는다 — 여러 세션이 같은 저장소를 쓴다. **본 작업 폴더에서 `git checkout`·`git stash` 를 하지 않는다**(2026-10-02 사고). 06c·06e 의 dev 를 받을 때도 이 worktree 안에서 `git merge dev` 로 받는다(Task L6·N8).
- **줄 번호 규칙:** 계획의 `파일:줄` 은 dev `da80f23`(= worktree `.worktrees/round06-spec` 의 코드 — 그 위의 문서 커밋 셋은 코드를 바꾸지 않는다) 기준이다. **같은 파일을 앞 Task 가 이미 바꿨으면 그 뒤의 줄은 밀려 있다** — 그런 자리는 각 Task 가 **앵커 글자**(da80f23 에 있고 앞 Task 들이 바꾸지 않는 한 줄)로 적었고 줄 번호는 '(da80f23 :N)' 참고값이다. Edit 의 old 는 그 앵커 글자로 잡는다(줄 번호로 자리를 찾지 않는다). 그 파일을 처음 고치는 Task 의 줄 번호는 da80f23 그대로 맞다. Task 0 이 dev 의 `frontend` 가 da80f23 과 같은지 확인한다.
- **프론트 테스트(이 줄의 본 검증):** 새 worktree 에는 `frontend/node_modules`·`.nuxt` 가 없다 — **Task 0 에서 `npm ci` 를 먼저 한다**(`.nuxt` 가 없으면 vitest 가 `TSConfckParseError … .nuxt/tsconfig.app.json` 로 전부 실패한다). 파일 하나는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/<파일>`, 전체는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`. 타입은 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`(기대 `0`), 빌드는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`(기대 `└  ✨ Build complete!`). 자동 import 경고는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"` — 기준선 `2`, Task D2 뒤 `0`, 그 뒤 늘 `0`.
- **`.vue` 검증:** `.vue` 는 단위 테스트하지 않는다. 판단·문구는 `utils/*.ts` 순수 함수로 빼서 vitest 로, `.vue`·`.css` 는 typecheck `0` 과 build 완료로 확인하고, 움직임(따라가기·막대 차오름·장부 더미)은 마무리 운영 확인(Task Z6)에서 본다. `nuxi typecheck` 는 `tests/` 도 보므로 06a·06b 타입(`SubqView`·`ResearchView`·`HistoryListOut`·`ListResult` 등)에 더하는 필드는 **선택(`?`)** 으로 더하고, 새 키는 값이 있을 때만 싣는다(기존 `toEqual` 픽스처를 깨지 않게).
- **프론트 대역(새로 만들지 않고 그대로 쓴다):** vitest 는 Nuxt 를 띄우지 않는다(`vitest.config.ts` — `environment: "node"`, 별칭 `~/` 만) — 자동 import 가 없으므로 utils 는 쓰는 것을 모두 명시해 import 한다. API 를 부르는 함수는 fetcher 를 인자로 받아 `tests/unit/historyStore.test.ts:67` 의 `fakeFetcher` 처럼 가짜로 잰다. 기록 픽스처는 `tests/unit/helpers/fakeHistory.ts`(`ID1`·`ID2`·`ID3`·`T0`·`bookEntry` 등), 저장소는 `tests/unit/helpers/memoryStorage.ts` 를 쓴다. **프로젝트에 없는 패키지를 `npx` 로 받지 않는다**(nuxi·vitest 는 프로젝트에 있다 — `@vue/test-utils`·jsdom 을 들이지 않는다).
- **상수·이름:** Nuxt 자동 import 때문에 **한 이름은 한 파일만 내보낸다**(06b 보강 8 — 두 파일이 같은 이름을 내보내면 `WARN Duplicated imports` 가 나고 하나가 말없이 무시된다). 새 이름은 아래 '공통 계약' 의 파일에서만 export 한다. `RUNNING_CAP` 은 `utils/synthCard.ts` 가 내보내고 `utils/researchProgress.ts` 는 import 한다. 06c 의 `questionUsedFromSteps`·`understoodLine` 을 06d 가 따로 만들지 않는다.
- **CSS 자리:** `research.css` 의 새 블록은 모두 앵커 `/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */`(da80f23 `:1252`) **바로 위**에 Edit 로 넣는다 — old = 그 한 줄, new = 자기 블록 + 빈 줄 + 그 한 줄. 기존 규칙을 고치는 것은 제자리에서 고치되 각 Task 에 적은 앵커 글자로 자리를 잡는다. 같은 선택자를 두 Task 가 정의하지 않는다. `work.css` 는 근거 장부 블록(`:75-166` · `:1216-1220`)만 고친다(Task L5). 새 색값(hex·rgba)을 쓰지 않고 `--skx-*` 토큰만 쓴다. 새 움직임은 모두 `@media (prefers-reduced-motion: reduce)` 에서 멈춘다.
- **백엔드 회귀:** 06d 는 `app/` 아래를 한 글자도 바꾸지 않는다. 전체는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`(Git Bash 에서 한글이 깨지면 앞에 `PYTHONIOENCODING=utf-8`). 이 줄은 백엔드 테스트를 쓰지 않으므로 로컬 대역 규칙(`_stub_missing`·`_load_*`·`_forget_on_teardown`·`asyncio.run`·torch 계열 함수 안 import — 06b 머리)은 읽을 때만 걸린다. 실패 5·오류 1 은 로컬 의존성 문제로 원래 상태다(아래 기준선). 그 밖의 실패가 나오면 06d 가 아니라 dev 에서 받은 코드다 — 멈추고 알린다.
- **기준선(2026-10-08 실측 — dev `da80f23` 코드, worktree `.worktrees/round06-spec`. Task 0 이 06d worktree 에서 다시 재고 같은 값이어야 한다):**
  - 백엔드 전체 **`5 failed, 2327 passed, 1 skipped, 2 warnings, 1 error`**. 실패 5 = `test_build_manifest.py` 2(Windows 경로 구분자 — `'originals/KC...KCI_FI001.pdf' == 'originals/KCI_FI001.pdf'`)·`test_loaders.py` 3(`ModuleNotFoundError: No module named 'pymarc'`), 오류 1 = `test_book_chat.py` 수집(`No module named 'FlagEmbedding'`) — 06b 계획 머리의 '5 failed · 1 error' 와 같은 여섯 줄이다. 경고 2 는 `core/config.py:16`·`schemas/book.py:47` 의 `PydanticDeprecatedSince20`. 06b 끝(2273)보다 54 많은 것은 06b 리뷰 반영·운영 수정 테스트다.
  - 프론트 `nuxi typecheck` 오류 **`0`**, vitest **`Test Files  40 passed (40)` / `Tests  732 passed (732)`**, `npm run build` **`└  ✨ Build complete!`**. 06d 가 고치거나 기대는 테스트 열한 파일 묶음은 **`Test Files  11 passed (11)` / `Tests  299 passed (299)`**(Task 0 Step 5). typecheck·build 에 두 번씩 나오는 `WARN Duplicated imports "queueLine"`(06b 이월 §7-5 — `utils/researchEvents.ts:107` 의 다시 내보내기, Task D2 가 지운다)과 typecheck 의 `[Vue] Resolve plugin path failed: vue-router/volar/sfc-route-blocks … Cannot find module '@vue/language-core'` 는 기준선에도 나오는 경고다. build 로그의 `error` 낱말은 `error-404`·`error-500` 청크 이름뿐이다.
- **기준선 읽는 법:** 각 Task 의 기대 수는 **"Task 앞 수 + N"** 상대값이다(앞 Task 를 아래 실행 순서대로 마쳤을 때). vitest 는 끝의 `Test Files … passed (…)`·`Tests … passed (…)` 두 줄로 읽는다. 백엔드 전체는 "실패 5·오류 1 은 기준선과 같은 세 파일" 로 읽고, pytest 끝의 `, 1 warning`·`, 2 warnings` 는 기대값에 없어도 같은 결과다. Task L6·N8 이 dev 를 받으면 06c·06e 의 테스트가 함께 들어온다 — 그 Task 의 '통과 확인' 에 적은 대로 merge 뒤 수를 새 '앞 수' 로 삼는다.
- **셸:** 명령마다 `cd <절대 경로> &&` 로 시작한다(에이전트 셸은 호출 사이에 cwd 가 초기화된다). 저장소는 `core.autocrlf=true` 라 작업 트리 파일이 CRLF 다 — 기존 파일은 **Edit 도구로** 고친다(Git Bash 의 sed·heredoc 은 LF 줄을 섞는다). 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다.
- **커밋:** `[Feat]`·`[Fix]`·`[Refactor]`·`[Test]`·`[Chore]`·`[Docs]` 접두어 + 한국어 서술형(`[Feat] round06d — …`). **`Co-Authored-By` 줄과 "Generated with Claude Code" 줄은 넣지 않는다**(사용자 규칙 — 다른 안내보다 우선). Task 마다 커밋 1~2개, `git add` 는 파일을 하나씩 적는다(`-A`·`.` 금지, `.vue` 경로의 대괄호는 따옴표로 — `"frontend/pages/research/[id].vue"`).
- **운영 금지:** Task 0 과 파트 D·L·N 의 어떤 Step 도 운영 서버·운영 DB 를 쓰지 않고 운영 API 에 쓰지 않는다. 운영 API 에 붙인 로컬 화면(`NUXT_DEV_API_TARGET` — `nuxt.config.ts:27-33` devProxy)에서 GET 만 하는 것은 된다 — 누르면 쓰는 버튼(승인·취소·[이 연구 이어가기]·[담기]·[계획 세우기])은 누르지 않는다. `dev` 머지는 사용자 승인 뒤(Task Z4·Z7), 서버 명령은 **사용자가** 친다(Task Z5·Z6 — 계획은 명령과 확인 방법을 준다).
- **고치지 않는 파일:** `frontend/components/work/WorkStepper.vue`(06e), `components/research/PlanCard.vue`(06c), `components/research/CitationChip.vue`, `components/research/ReportView.vue`(정함 8 — 절 자리는 새 부품), `components/BookChat.vue`(06e), `utils/workPhase.ts`·`utils/researchErrors.ts`·`composables/useResearchWork.ts`·`types/work.ts`(06e — **읽기만**), `utils/citations.ts`(06e), `utils/researchDraft.ts`·`tests/unit/researchDraft.test.ts`(spec — 그대로), `pages/research/[id].vue:57-75`(06e 단계 본문 — 리스너 `@panel` 과 `workPanelOpen` 도 06e 가 단다), `pages/papers/index.vue:564-569`(06e 가 BookChat 에 `doc-kind="paper"` 를 넣는다), `pages/search-classic.vue`(보존 화면), `work.css` 의 근거 장부 블록 밖, `package.json`·`package-lock.json`, `app/` 전부·compose·`infra/`.
- **함정(`docs/ops/recurring-gotchas.md`):** 06d 는 nuxt 만이라 배포(Task Z5)에서 3(운영은 `:latest`)·12(Portainer 에 pull 을 맡기지 않는다)·16(바뀐 컨테이너만 Recreate)·20(nuxt Recreate 뒤 `nginx -s reload`)이 걸린다. 06c 기본값 커밋을 함께 내는 경우(Task Z5 경우 C)는 14(스키마 변경 없음 — `alembic_version` 그대로)·18(fastapi Recreate 전 `idle in transaction` 0)·24(browser_active 429 가 안 풀리면)도 본다.

---

## 06d 에서 정한 것 (spec 이 '예'·'제안'으로 둔 것과 이 계획의 보강 — 결정과 근거)

spec 과 다르게 읽은 것(정함 4·7 — Claude 해석)과 §12-11 을 닫은 것(정함 9·18), spec 이 06d 계획에 넘긴 탐색 방식의 자리·모양(정함 19)은 **Task Z3 가 spec 을 이 결정에 맞춘다**(CLAUDE.md §3 — 코드가 실제다). 완료노트 §6 에 그대로 옮긴다.

| # | 결정 | 근거 |
|---|---|---|
| 정함 1 | **진행 막대 하나 = 두 구간 가중 전체 진행.** `fraction = (EXPLORE_WEIGHT × 탐색 비율 + SYNTH_WEIGHT × 작성 비율) ÷ 202`(탐색 중 작성 비율 0, 작성 중 탐색 비율 1). 오른쪽 퍼센트는 `Math.floor(fraction × 100)`. 계획 중·승인 대기·대기열은 퍼센트 없이(null) 단계 글줄만, 채움 0 | spec §12-3 '두 구간 가중치 111:91 상수'. 퍼센트를 구간마다 0 부터 다시 세면 작성 시작 때 막대가 뒤로 간다 |
| 정함 2 | **탐색 비율** = 하위질문마다 몫을 더해 하위질문 수로 나눔. 끝남·실패 1, 대기 0, 도는 하위질문 = `min(RUNNING_CAP, (점검이 끝난 회차 수 + 열린 회차의 다가감) ÷ maxRounds)`, `maxRounds = max_recheck + 1`(params 가 없거나 이상하면 `DEFAULT_MAX_RECHECK + 1` = 4). 열린 회차의 다가감 = `RUNNING_CAP × (1 − 0.5^(경과 ÷ ROUND_HALF_LIFE_MS))`, `ROUND_HALF_LIFE_MS = 6000`. 경과의 시작은 **화면이 그 회차를 처음 본 시각**(`activeRoundKey` 가 바뀐 때) — 서버가 회차 시각을 주지 않는다 | spec '탐색 비율 = 끝난 하위질문 + 도는 하위질문의 회차 몫', '추정 증가도 상한 0.9', 'useNow 를 exploring 에도'. 실측 202초 중 탐색 111초 ÷ 6 하위질문 ≈ 회차당 십수 초 |
| 정함 3 | **고정 진행 영역의 높이는 토큰으로 고정한다** — `.rs-pbar { height: var(--rs-bar-h) }`, 큰 글줄은 한 줄 말줄임. 오프셋(옆 칸 top·문서 `scroll-padding-top`·위치 복원)은 모두 같은 높이 토큰을 읽는다(`--rs-bar-h` — 문서 스크롤 칸 html 은 `.rs-page` 의 값을 읽지 못해 `:root` 의 `--rs-bar-area-h` 를 읽는다). 막대가 없을 때 `--rs-bar-h: 0px`. 막대 높이는 문서 `scroll-padding-top` 한 곳에만 — `.rs-section` 의 `scroll-margin-top` 에 다시 더하지 않는다(D4 품질 검토 반영) | spec '치수는 research.css 의 토큰(`--rs-bar-thick`·`--rs-bar-h`)으로'. 높이를 재는 ResizeObserver 를 두면 오프셋이 프레임마다 흔들린다 |
| 정함 4 | **따라가기를 멈추는 것은 사용자 입력뿐** — 세로 휠(Ctrl 없음)·터치 이동(`touchmove`)·스크롤 키(`FOLLOW_KEYS`, 입력칸 밖 — 수식 키 조합은 페이지를 굴리는 Ctrl+Home/End·Cmd+↑/↓·Option+↑/↓ 만, D6 품질 검토 반영)·페이지 스크롤바 누르기(`pointerdown` 의 `clientX >= documentElement.clientWidth`). `scroll` 이벤트로 가르지 않는다. **spec §12-3 '프로그램이 일으킨 스크롤은 플래그로 거른다' 를 이것으로 갈음한다**(Claude 해석) | 브라우저 스크롤 앵커링·절 펼침·위치 붙잡기(`useRestorePosition.hold`)가 내는 `scroll` 을 플래그로 다 거를 수 없다. 프로그램 스크롤(`scrollIntoView`)은 입력 이벤트를 내지 않는다 |
| 정함 5 | **막힘(옮기지 않음)** = 위치 복원 중(`restore.pending`) · 원문 뷰어 열림(`pdf`) · **열린 인용 팝오버**(DOM 에 `.rs-page .rs-cite__pop` 이 있음 — 고정·hover 를 가리지 않는다). 막힌 동안 대상이 바뀌면 옮기지 않고 다음 바뀜에 옮긴다. 최종본(완료)은 대상이 null 이라 멈춘다 | `CitationChip.vue` 를 고치지 않는다(고정 여부를 밖에 알리지 않는다). hover 로 연 팝오버를 읽는 중에도 끌고 가지 않는 편이 맞다 |
| 정함 6 | **상세에서 돌아온 화면(`restore.anchor !== null`)은 따라가기를 멈춘 채 시작**하고 알약만 띄운다. 현황 카드의 절을 눌러 옮기면(`jumpToSection`) 따라가기를 멈춘다 | 사용자가 고른 자리를 다음 절이 시작될 때 빼앗지 않는다. 같은 까닭으로 따라가기는 화면을 연 순간(새로고침·사이드바로 들어옴)의 대상을 기준으로만 삼고 다음 바뀜부터 옮긴다(Task D7 — 파트 D 끝 '파트 메모' 4) — 그래서 탐색이 시작될 때 첫 하위질문 자리로는 옮기지 않고 다음 하위질문부터 따라간다(Task Z6 Step 2 항목 5 가 이것을 기대로 본다) |
| 정함 7 | **알약 문구** — 작성 중 `↓ 지금 쓰는 곳으로`(spec 그대로), 탐색 중 `↓ 지금 찾는 곳으로`(Claude 해석) | 탐색 중에는 쓰는 글이 없다 |
| 정함 8 | **탐색 중 절 자리는 새 `ReportSkeleton.vue`**(ReportView 자리 모드 아님). 하위질문 번호와 절 번호가 달라 자리 머리에 'N.' 대신 작은 '하위질문 N' 을 단다 | ReportView 는 보고서·초안 두 모드와 제외 목록·위치 복원을 이미 품는다. `draftReport`·`draftSlots` 를 건드리지 않는다는 제약과 맞다 |
| 정함 9 | **§12-11 '탐색 중 읽기 전용 PlanCard·옆 칸 폭' — 정함(권고).** 탐색 중 읽기 전용 PlanCard(`[id].vue:97`)는 지우고 절 자리가 대신한다. 옆 칸 폭 `--rs-side-width: 17rem` 은 그대로 | 같은 하위질문 목록·상태를 본문에 두 번 그리지 않는다. 옆 칸에 더하는 것('검토 중' 더미)은 장부 목록 안이라 폭을 넓힐 까닭이 없다 |
| 정함 10 | **근거 장부를 옆 칸 맨 위(진행 패널 위)로 옮긴다 — 늘** | spec '근거가 떨어져 들어옴 — 배치만 옮긴다'. 떨어지는 효과가 긴 타임라인 아래 화면 밖에서 일어나지 않게 |
| 정함 11 | **'검토 중' 더미 상태는 `SubqView.reviewing?`**(선택 필드 — 없으면 키를 두지 않는다). 후보 이벤트(`candidates` — 하위질문 키 `subq_idx`)가 세우고, 같은 하위질문의 `critique`·`snapshot`·그 회차 판정이 실린 진행 저장, **그리고 잡 종료(완료·실패·취소 이벤트, 끝난 잡으로 다시 맞추는 `refreshView`)** 가 지운다. 다음 회차 후보는 갈음한다 — **빈 후보(`papers: []`)도 갈음 = 비움**(06c 는 회차마다 늘 후보를 내고 빈 목록도 낸다). 빈 후보는 하위질문을 새로 만들지 않는다 | spec Q9 행. 재접속·새로고침은 더미 없음 |
| 정함 12 | **회차 미세 상태는 새 함수 `roundStatusLabel`(회차 줄)** 로 둔다. `subqStatusLabel` 은 그대로(06c 파일 PlanCard 도 읽는다) | 함수 출력이 바뀌면 06c PlanCard 화면과 기존 테스트가 함께 바뀐다 |
| 정함 13 | **사이드바 단계 줄 = `workPhase.stepLine(phase)` + 단계 수(후보 n · n편 담음 · n/6절) + 진행 중 생성이면 '생성 중'** — 06d 는 단계 이름 문자열을 새로 쓰지 않는다 | spec §12-5 '사이드바 단계 이름은 workPhase.ts 의 것' — 06e 의 이름 바꾸기가 따라온다 |
| 정함 14 | **'모두 보기 (N)' 의 N = history 목록 응답의 `total`**(kind 를 준 요청의 그 kind 전체 수 — 06e 가 싣는다). 응답에 없으면 `null` → '모두 보기' 만 | spec §12-3. 06d 가 읽는 자리는 `createServerStore().list` 한 줄이다 |
| 정함 15 | **`/research` 홈의 '진행 중·내 연구' 는 history 목록을 직접 50건씩 읽는다**(`[더 보기]` = `before` 커서). 사이드바의 30건 상태(`useHistory`)와 따로 둔다. 예시 연구의 실행 시각·범위는 예시마다 `GET /api/research/{id}/work` 의 `corpus`(`at`·`n_papers`·`from`·`to`)에서 | N 이 30을 넘으면 사이드바 목록으로는 '모두' 가 안 된다. `GET /api/research-works?example=1` 은 `{id, question, phase, created_at}` 만 준다(`app/api/research_work.py:300-322`) — 06d 는 백엔드를 바꾸지 않는다 |
| 정함 16 | **[딥리서치로 더 깊게] = `/papers?draft=<검색어>` 로 옮긴다** — 기존 `restoreFromQuery` → `goLanding` → `fillResearchDraft`(`pages/papers/index.vue:895-903`)가 랜딩 입력창에 딥리서치 칩을 켠 채 채운다. 바로 시작하지 않는다 | spec 'fillResearchDraft 재사용'. 결과 화면 검색바의 + 메뉴에는 ref 가 없다 |
| 정함 17 | **[담기] = `PUT /api/research/{job}/reading/{cnts_id}` 본문 `{"state": "in"}`(담음)** | '담기' 는 그 연구의 목록에 넣는 것 — 후보로 넣으면 다시 담아야 한다. 백엔드는 행이 없으면 origin `user` 로 만든다(`app/api/research_reading.py:79-116`) |
| 정함 18 | **§12-11 ''소장자료검색'으로 맞출 다른 문구' — 정함(권고).** 입력창 안내(`pages/index.vue:82`)와 사이드바 탭(`AppSidebar.vue:150` '도서')·그 탭의 빈/지우기 문구(`:155`·`:160`)도 '소장자료' 로 맞춘다. 랜딩 머리 문구(`:12-15`)·결과 화면 문구는 그대로 | 탭 이름은 '소장자료검색' 인데 기록 탭이 '도서' 면 같은 기록을 두 이름으로 부른다. 기능·kind(`book`)·주소는 그대로 |
| 정함 19 | **탐색 방식 — 폭넓게 · 정밀하게, 기본 정밀하게(spec D28 — 06c 판정 뒤 2026-10-12 사용자 결정).** 딥리서치를 시작하는 자리(+ 메뉴의 딥리서치 칩 옆 — 랜딩 두 곳·결과 검색바, `/research` 홈의 새 연구)에 라벨 '탐색 방식' 의 두 칸 선택(radiogroup)을 두고, 고른 방식을 잡 params 두 칸으로 **늘 함께** 싣는다 — 폭넓게 `{broaden: 0, query_context: 0}`(지금 방식) · 정밀하게 `{broaden: 1, query_context: 1}`. 고른 값은 localStorage `skx_research_mode` 에 기억한다(편의 — 읽지 못하면 정밀하게). [같은 질문으로 다시 시작]은 고르지 않고 원래 잡의 두 칸을 이어 쓴다(두 칸이 없는 06c 전 잡은 정밀하게). 연구 화면 머리의 상태 배지 옆에 그 잡의 방식을 작게 보인다(두 칸 다 0 → 폭넓게, 두 칸이 없음·갈림 → 표시 없음). 백엔드는 그대로 — Task N9 | 사용자 "응 넣자. 정확하게로 가자. 탐색 방식: 폭넓게 · 정밀하게 로 가자"(06c 완료노트 §5-4). 미리 정한 판정 규칙으로는 두 스위치 모두 0 이라 서버 기본값(`DEFAULT_PARAMS`)은 0 그대로다 — 그래서 화면이 두 칸을 실어야 켜진다. `query_context` 만 1 이면 범위 용어가 비어(용어는 `broaden` 1 의 계획 단계가 뽑는다) '국내 학술논문에서' 떼기만 한다(06c 계획 정함 20). 서버 `merge_params` 가 두 칸을 정수 0~1 로 검증한다(`app/services/research/state.py:56-57`). 다시 시작이 고르는 칸 없이 원래 방식을 잇는 것·머리 표시·기억은 이 계획의 보강이다 |

---

## 공통 계약 (이름·모양 — 모든 Task 가 이 이름을 쓴다)

본문 Task 의 코드가 정본이고, 이 절은 파트 사이에 이름이 어긋나지 않게 보는 색인이다. 이름을 바꿔야 하면 쓰는 Task 를 모두 함께 바꾼다.

**새 파일과 공개 이름(이 파일만 export)** — 2026-10-08 utils·composables export 전수로 모두 새 이름임을 확인했다(`synthProgress`·`slotStateLabel`·`barFraction` 과 다르다).

| 파일(새, `frontend/` 기준) | 공개 이름 | Task |
|---|---|---|
| `utils/researchProgress.ts` | 타입 `ProgressStage`·`ProgressStageItem`·`ProgressInput`·`ProgressBarView`, 상수 `PROGRESS_STAGES`·`EXPLORE_WEIGHT`(111)·`SYNTH_WEIGHT`(91)·`DEFAULT_MAX_RECHECK`(3)·`ROUND_HALF_LIFE_MS`(6000), 함수 `progressStage`·`progressStages`·`maxRoundsOf`·`exploreFraction`·`overallFraction`·`activeRoundKey`·`showsProgressBar`·`progressBarView` | D3 |
| `components/research/ResearchProgressBar.vue` | props `{ view: ProgressBarView }`, emit 없음 | D4 |
| `utils/planSlots.ts` | 타입 `PlanSlotState`·`PlanSlot`, 함수 `slotElementId`·`sectionOfSubq`·`planSlots`·`planSlotLabel`·`newlyCollected`·`showsPlanSlots` | L1 |
| `components/research/ReportSkeleton.vue` | props `{ slots: PlanSlot[] }`, emit 없음 | L2 |
| `utils/researchFollow.ts` | 타입 `FollowInput`, 상수 `FOLLOW_KEYS`·`FOLLOW_PILL_WRITE`·`FOLLOW_PILL_EXPLORE`, 함수 `breaksFollow`·`sectionElementId`·`followTarget`·`followBlocked`·`shouldFollowMove`·`followPill`·`followBehavior` | D6 |
| `composables/useSectionFollow.ts` | 타입 `SectionFollow`, 함수 `useSectionFollow` | D7 |
| `utils/sidebarResearch.ts` | 상수 `LIVE_RESEARCH_STATUSES`, 함수 `isLiveResearch`·`researchRowLine`·`researchBadge`·`allResearchLabel` | N3 |
| `utils/researchHome.ts` | 타입 `WorkListItem`·`WorkListOut`·`ResearchPage`, 상수 `HOME_PAGE_SIZE`(50), 함수 `homeGroups`·`exampleMeta`·`exampleRoute` | N5(자르면 N7 이 일부) |
| `composables/useResearchWorks.ts` | `useResearchWorksApi`(N5), `useAddToWork`(N6) | N5·N6 |
| `pages/research/index.vue` | 페이지 `/research` | N5 |
| `utils/addToWork.ts` | 상수 `ADD_TO_WORK_EMPTY`·`ADD_TO_WORK_BODY`, 함수 `workChoiceLabel`·`addedLine` | N6 |
| `components/research/AddToWorkMenu.vue` | props `{ cntsId: string; works: WorkListItem[] \| null; loading: boolean; busy: boolean }`, emits `open: []`·`pick: [jobId: string]` | N6 |
| `utils/researchMode.ts` | 타입 `ResearchMode`(`"broad" \| "precise"`)·`ResearchModeOption`·`ModeParams`(type — `{ broaden: number; query_context: number }`), 상수 `RESEARCH_MODE_LABEL`·`DEFAULT_RESEARCH_MODE`(`"precise"`)·`RESEARCH_MODE_KEY`(`"skx_research_mode"`)·`RESEARCH_MODES`, 함수 `modeParams`·`modeOfParams`·`researchModeLabel`·`researchModeLine`·`restartParams`·`modeStep`·`readResearchMode`·`saveResearchMode` | N9 |
| `components/research/ResearchModePicker.vue` | props `{ modelValue: ResearchMode; disabled?: boolean }`, emits `update:modelValue: [mode: ResearchMode]` | N9 |

**고치는 파일의 새·바뀐 공개 이름**

| 파일 | 바뀜 | Task |
|---|---|---|
| `utils/researchLayout.ts` | `LAYOUT_BEFORE_REPORT`·`LAYOUT_WITH_REPORT` 삭제, `WIDE_LAYOUT: ResearchLayout = "A"` 새로, `effectiveLayout(override, wide)`(세 번째 인자 삭제) | D1 |
| `utils/researchEvents.ts` | `export { queueLine } from "~/utils/queueLine"`(:105-107) 삭제(D2), `roundStatusLabel(sq, r)` 새로(L3), `applyResearchEvent` 의 `case "candidates"`·비공개 `applyCandidates`(L4) | D2·L3·L4 |
| `utils/synthCard.ts` | `RUNNING_CAP`(:6) 을 `export const` 로 | D3 |
| `utils/restorePosition.ts` · `composables/useRestorePosition.ts` | `insetTargetTop(y, viewportHeight, inset)` 새로 · opts `{ maxWaitMs?: number; topInset?: () => number }` | D5 |
| `utils/restorePosition.ts` | 타입 `ScrollAncestor`·`ScrollHolder`, 함수 `scrollHolder(chain)`·`boxScrollDelta(el, box, viewportHeight, targetY)` 새로 — 위치 복원이 안쪽 스크롤 칸(A 의 옆 칸)·고정 칸 안의 요소를 칸을 굴려 맞추고 창으로 끌지 않는다(`useRestorePosition` 의 비공개 `holderOf`·`alignInBox`) | D1 품질 검토 반영 |
| `types/research.ts` | `CandidatesEvent`·`ReviewingView` 새로, `SubqView.reviewing?`, `ResearchEvent` 에 `CandidatesEvent` | L4 |
| `utils/evidenceLedger.ts` | `Ledger.reviewing: LedgerPaper[]`(필수), `hasLedger`·`ledgerFrom`·`ledgerLine` 규칙 확장 | L5 |
| `types/history.ts` · `utils/historyStore.ts` · `utils/historyState.ts` · `composables/useHistory.ts` | `HistoryListOut.total?` · `ListResult.total?`(`list` 가 `total: res.total ?? null`) · `HistoryState.totalOf(kind)` · `UseHistory.totalOf(kind)` | N2 |
| `utils/paperResearch.ts` | `deeperResearchUrl(query): string \| null` | N4 |
| `composables/useResearch.ts` | `useResearchStarter().startResearch(question, params?: ResearchParams)`(두 번째 인자 새로 — 없으면 서버 기본값) | N9 |
| `components/research/ResearchHeader.vue` | 선택 prop `modeLine?: string \| null`(`researchModeLine` 의 글 — 없으면 그리지 않는다) | N9 |

**DOM id·클래스·CSS 토큰**

| 이름 | 뜻 | 정하는 Task |
|---|---|---|
| `--rs-bar-thick` | `.rs-page` 에 `1rem`, 768px 이하 `0.75rem` | D4 |
| `--rs-bar-h` | `.rs-page` 에 `0px`, `.rs-page.has-progressbar` 에 고정 진행 영역 전체 높이(`var(--rs-bar-area-h)`) — 막대 높이·옆 칸 top 이 읽는다 | D4 |
| `--rs-bar-area-h` | `:root` 에 고정 진행 영역 전체 높이 `5.6rem`(768px 이하 `5.2rem`) — 값은 여기 한 곳. `.rs-page.has-progressbar` 의 `--rs-bar-h` 와 문서 `scroll-padding-top` 이 읽는다 | D4 품질 검토 반영 |
| `html:has(.rs-page.has-progressbar)` | 막대가 서 있는 동안 문서 스크롤 칸의 `scroll-padding-top: var(--rs-bar-area-h)` — 초점 이동·`scrollIntoView`(절 이동·따라가기)·#조각 이동이 막대 밑을 보이는 곳으로 치지 않는다(WCAG 2.2 2.4.11). `scrollBy`·`scrollTo` 에는 걸리지 않아 위치 복원은 D5 의 inset 으로 따로 내린다. `.rs-section` 의 `scroll-margin-top` 은 `1.2rem` 그대로(막대 높이를 다시 더하면 두 번 내려간다 — `researchProgress.test.ts` 의 research.css 여백 두 `it` 이 지킨다) | D4 품질 검토 반영 |
| `.has-progressbar` | `<main class="rs-page">` 에 막대가 서 있을 때 | D4 |
| `.rs-pbar`(`__stages`·`__stage`·`__line`·`__text`·`__pct`·`__track`·`__fill.is-running`) | 큰 진행 막대(`position: sticky; top: 0; z-index: 5`) — 옛 `.rs-synth__bar`·`.rs-synth__fill` 은 지운다. Task D8 은 고치지 않는다(같은 선택자를 두 Task 가 정의하지 않는다) | D4 |
| `#rs-sec-{절}` · `#rs-slot-{하위질문}` | 보고서 절(기존, `ReportView.vue:27`) · 탐색 중 절 자리(`slotElementId`) | — · L1 |
| `.rs-slot`·`.rs-report--slots`·`.rs-slot__kicker`·`.rs-slot__state` | 탐색 중 절 자리 | L2 |
| `.rs-card__text` | 대기 카드의 글 묶음(세로) | D2 |
| `.rs-plan__understood` | "이렇게 이해했어요" 한 줄의 고리(06c 가 PlanCard 에 단다) — 06d 는 계획 중 카드에도 같은 클래스를 달고 **CSS 규칙은 더하지 않는다** | 06c · L6 |
| `.rs-follow-pill` | 따라가기 알약(`work.css` 의 `.wk-pill` 패턴을 `research.css` 로 옮겨 씀 — `work.css` 는 고치지 않는다) | D7 |
| `.rs-round__state` | 회차 줄 미세 상태 | L3 |
| `.wk-ledger__list--reviewing`·`.wk-ledger__paper.is-reviewing`·`@keyframes wk-review` | 장부 '검토 중' 더미(`work.css` 근거 장부 블록 안) | L5 |
| `.rs-deeper`·`.rs-home*`·`.rs-basket*` | 빠른검색 카드·`/research` 홈·담기 메뉴 | N4·N5·N6 |
| `.skx-history-item__step`·`.skx-history__all` | 사이드바 단계 줄·모두 보기(`AppSidebar.vue` scoped) | N3 |
| `.rs-mode`(`__label`·`__group`·`__opt`·`__hint`) | 탐색 방식 두 칸 선택(`ResearchModePicker.vue`) | N9 |
| `.rs-head__meta`·`.rs-head__mode` | 연구 화면 머리의 상태 배지 줄·그 잡의 탐색 방식 알약 | N9 |
| localStorage `skx_research_mode` | 고른 탐색 방식의 기억(`"broad"`·`"precise"` — 편의일 뿐, 읽지 못하면 정밀하게) | N9 |

**API·이벤트(06d 는 백엔드를 바꾸지 않는다 — 읽기만)**

| 경로·이벤트 | 모양 | 쓰는 Task |
|---|---|---|
| SSE `candidates` | `{"kind": "candidates", "subq_idx": int, "round": int, "papers": [{"cnts_id", "title", "personal_author", "pub_date"}]}` — 06c 가 회차마다 `search`·`counters` 뒤·`critique` 앞에 늘 한 번(빈 목록도). 옛 워커는 보내지 않는다 — 더미 없이 지금처럼 | L4·L5 |
| `GET /api/history?kind=research&limit=&before=` | `{"items": […], "next_cursor": str \| null, "total"?: int}` — `total` 은 06e fastapi 부터 | N2·N5 |
| `GET /api/research-works` · `?example=1` | `{"items": [{"id", "question", "phase", "created_at"}]}`(상한 50) | N5·N6 |
| `GET /api/research/{id}/work` | WorkView — `corpus: {n_papers, from, to, at}` | N5 |
| `PUT /api/research/{id}/reading/{cnts_id}` | 본문 `{"state": "in"}` → ReadingItem. 404 `논문이 없습니다`, 409 예시 연구 | N6 |
| `POST /api/research` · `GET /api/research/{id}` | 만들기 본문 `{"question", "params": {"broaden": 0\|1, "query_context": 0\|1}}`(`merge_params` 가 정수 0~1 로 검증, 모르는 키·범위 밖은 422) → 잡은 기본값을 채운 params 를 저장하고 GET 의 `params` 로 돌려준다(06c fastapi 부터 두 칸이 있다) | N9 |

---

## 다른 줄과의 경계·머지 문 (§12-5·§12-6)

**06c(질의 — `feat/round06c-query-broadening`)에서 받는 것(06c 를 따른다)**

| 06d 가 기대는 것 | 06c 가 만드는 것 | 06d 자리 | 어긋나면 |
|---|---|---|---|
| 탐색 후보 이벤트 | `runner.py` 회차 루프의 `emit("counters", …)` 바로 뒤·`critique_fn` 앞에 `emit("candidates", {"subq_idx", "round", "papers"})` — 하위질문 키는 runner 의 `search`·`critique` 와 같은 `subq_idx`(spec §12-2 의 옛 `subq_id` 는 계획 확정 전에 고쳤다), 회차마다 늘 한 번·빈 목록도, 스냅숏·rounds·step result 에 없음 | Task L4(타입·리듀서)·L5(장부) | 06c 를 따른다 — L4 Step 0 이 06c 계획을, L6 이 머지된 코드를 다시 확인하고 다르면 06d 쪽 이름을 고친다 |
| "이렇게 이해했어요" | `utils/researchEvents.ts` 의 `questionUsedFromSteps(steps, question): string \| null`(숨김 판단 포함)·`understoodLine(questionUsed): string`(= `이렇게 이해했어요: …`, 접두를 함수가 붙인다), PlanCard 선택 prop `questionUsed`, `StepResult.question_used?`·`terms?`·`elapsed_ms?` | Task L6 | 06c 이름·시그니처를 그대로 쓴다 — 같은 판단·문구 함수를 06d 가 따로 만들지 않는다 |
| `PlanCard.vue` | 06c 만 고친다 | 06d 는 prop 만 넘긴다 | — |
| `researchEvents.ts`·`types/research.ts` | 06c 는 함수 둘(`planFromSteps` 옆)과 `StepResult` 칸 셋만 | 06d 는 다시 내보내기 지우기(D2)·`roundStatusLabel`(L3)·후보 이벤트(L4) | 서로 다른 블록 — 늦게 머지하는 06d 가 L6 에서 dev 를 받아 맞춘다 |
| 랜딩 논문 예시 셋 | 06c 판정 질문(library·elderly·multicultural)과 같은 문장(`pages/index.vue:681-685`, `89cede3`) | 06d 파일 | 06c 판정 뒤 Task Z2 가 판단하고, 바꿀 것이 있을 때만 06d 가 고친다 |
| 탐색 방식(spec D28) | 06c 의 두 스위치 `broaden`·`query_context` — 서버 `DEFAULT_PARAMS` 0 그대로(판정 결과 기본값 커밋 없음), `merge_params` 가 정수 0~1 로 검증(`app/services/research/state.py:56-57`). 06c 계획의 '10/17~18 배포 뒤 06c 확인'(06c 쪽 Task Z9)이 06d 의 탐색 방식이 새 잡 params 로 실리는지 본다 | Task N9(`utils/researchMode.ts` 의 `modeParams`·`restartParams`, `SearchPlusMenu.vue`·`useResearch.ts`·`/research` 홈·`[id].vue` 다시 시작) | 06c 를 따른다 — 키 이름·값 범위가 바뀌면 `modeParams`·`restartParams` 와 그 테스트를 고친다. 06c 는 화면 파일을 더 고치지 않는다 |

**06e(연구 어시스턴트 — `feat/round06e-assistant-auto-report`)와의 경계**

| 경계 | 내용 |
|---|---|
| 연구 화면 머리 | 고정 진행 영역은 끝나지 않은 잡에만 서고(`showsProgressBar` 가 completed·failed·canceled 에서 false — Task D3 테스트가 보증), 06e 의 `WorkStepper` 는 이어가기가 completed 잡에서만 되므로 끝난 잡에만 선다 — 한 화면에 함께 서지 않는다. 06d 는 `WorkStepper.vue` 를 고치지 않는다 |
| 보고서 화면의 큰 진행 막대(10-11 사용자 확인) | 06e 가 보고서 단계 화면(`ProposalStep.vue`, 단계 화면 = stepMode)의 머리 목차 위에 자기 막대 `.wk-rbar`(토큰 `--wk-bar-thick` — `work.css` 의 06e 자리, 근거 장부 블록 밖)를 그린다(06e 계획 정함 28). 06d 의 `.rs-pbar` 는 stepMode 에서 서지 않으므로 겹치지 않는다. Q1 치수는 두 토큰(`research.css` 의 `--rs-bar-thick` · `work.css` 의 `--wk-bar-thick`)에 같은 값으로 있다 — 시각 디자인 담당이 고칠 때 둘을 함께 고친다(완료노트 '디자인 참조'). 06d 는 06e 의 막대 부품·계산·CSS 를 만들지도 고치지도 않는다 |
| `[id].vue` | `:57-75`(단계 본문)는 06e. 나머지는 06d. import 블록이 겹칠 수 있다 — 늦게 머지하는 쪽이 dev 를 받아 맞춘다 |
| LNB 접기 | 06e 는 ReadingStep·ProposalStep 의 emit `panel: [open: boolean]` 과 `[id].vue:73-74` 의 리스너 `@panel="workPanelOpen = $event"`, script 의 `const workPanelOpen = ref(false);` 까지 단다. `AppSidebar :collapsed="workPanelOpen"` 와 루트 `is-lnb-collapsed`(`[id].vue:3-7` 두 곳)는 늦게 머지하는 줄이 단다 — 06d 가 늦으면 Task N8, 06e 가 늦으면 06e 계획의 LNB 연결 Task. 06d 는 리스너·새 ref·`watch(step)` 를 넣지 않고 `workPanelOpen` 을 읽기만 한다 |
| 읽기만 하는 06e 파일 | `workPhase.ts`(`stepLine`·`stepForPhase`·`scopeLine`)·`researchErrors.ts`(`workErrorMessage`·`researchErrorMessage`·`activeResearchId`)·`useResearchWork.ts`(`useWorkApi().getWork`·`putReading`)·`types/work.ts`(`Corpus`·`WorkPhase`). 06e 가 문구를 바꾸면 사이드바·홈이 따라온다 — 06d 테스트는 그 함수의 출력으로 기대값을 만든다(N3) |
| history total | 06e 가 `app/api/history.py`·`app/repositories/history.py`·`app/schemas/history.py` 에 kind 별 `total` 을 싣는다. 프론트 타입·나르기·그리기는 06d(N2·N3) — 06e 는 프론트 기록 파일을 건드리지 않는다. 06e 가 늦게 배포돼도 06d 는 N 없이 그린다 |
| `work.css` | 06d 는 근거 장부 블록(`:75-166`·`:1216-1220`)만, 나머지는 06e. `EvidenceLedger.vue`·`utils/evidenceLedger.ts` 는 `components/work/` 에 있지만 06d 몫 |
| `pages/papers/index.vue` | 06d 파일. 06e 는 `:564-569` BookChat 에 `doc-kind="paper"` 한 속성만 넣는다 — 06d(N4·N6)와 다른 자리 |
| 딥리서치 시작 자리·잡 params(탐색 방식) | `components/research/SearchPlusMenu.vue`·`composables/useResearch.ts`(`useResearchStarter`)·`components/research/ResearchHeader.vue` 는 06d 파일이다(Task N9). 06e 계획은 세 파일을 고치지 않고 딥리서치 잡을 새로 만들지도 않는다([이 연구 이어가기]·생성은 끝난 잡에 붙는다) — 탐색 방식과 겹치는 자리가 없다. `useResearch.ts` 가 import 하는 `researchErrors.ts`(06e)는 그대로 읽기만 한다 |

**머지·배포 문(§12-6)**
- **06d 는 06c 운영 배포(10/13~14)가 끝난 뒤에만 `dev` 에 머지한다.** 06c 배포 이미지는 그때의 dev 로 만들므로 그 전에 들어가면 06c 배포 판정이 흐려진다. 06c 의 화면 한 줄(PlanCard prop·리듀서)은 dev 에 들어간 뒤 06d 가 `[id].vue` 에 이어(Task L6) 10/17~18 nuxt 배포에 함께 나간다.
- **06e 와의 순서는 묶이지 않는다** — 기본은 06e → 06d(그러면 06d 가 Task N8 을 하고 머지). 06e 가 10/17 까지 들어오지 못하면 06d 가 먼저 머지·배포(nuxt 만 — 06c 기본값 커밋이 아직 운영에 없으면 함께, Task Z5 경우 C)하고 N8 은 건너뛴다(06e 가 단다).
- **06c 기본값 커밋(Q4 — 판정 결과)** 은 10/17~18 배포에 실린다. 그 배포를 06d 가 하게 되면(06e 가 늦을 때) 워커 셋 → fastapi → nuxt 순서를 따른다(Task Z5 경우 C). → **2026-10-12 판정 결과 기본값 커밋은 없다**(서버 기본값 0 그대로 — 06c 완료노트 §5-5). 켜는 길은 06d 의 탐색 방식(Task N9)이 잡 params 로 싣는 것이다. dev 기본값이 운영과 같으므로 Task Z5 의 경우 C 는 생기지 않을 것이다 — 경우 표는 그대로 두고 Step 1 의 출력으로 가른다. 06d nuxt 는 06c fastapi(두 칸을 아는 `merge_params`)가 운영에 있어야 한다 — 2026-10-12 에 나갔다.
- **자르는 순서(spec §12-6 — 06d 몫):** 뒤처지면 Task N6([담기]) → Task N5(`/research` 홈) 순으로 하지 않는다. N5 를 자르면 Task N7 을 한다. **자르지 않는 것:** 파트 D·L 전부(진행 화면의 움직임 — 따라가기·탐색 중 절 자리·근거 수집 단계, 'A 로만 되돌리면 같은 평' 09-28).

---

## 파트 순서와 Task ID

Task 는 파트 영문 접두 + 번호로 부른다(다른 Task 를 부를 때도 'Task D3' 꼴 그대로). 파트 안 번호는 실행 순서이고 접미 글자(D4b 꼴)는 쓰지 않는다. 다른 줄의 Task 는 ID 가 아니라 내용으로 부른다(예: '06c 계획의 candidates emit', '06e 계획의 운영 배포 Task').

| 파트 | Task | 내용 |
|---|---|---|
| — | Task 0 | worktree·기준선 확인 |
| D 진행 화면 뼈대 | D1 → D8 | D1 처음부터 2단 · D2 06b 이월(`queueLine`·대기 카드) · D3 진행 막대 순수 함수 · D4 큰 진행 막대 부품·고정 영역·현황 카드 막대 옮기기 · D5 오프셋 · D6 따라가기 판단 순수 함수 · D7 따라가기 연결·알약 · D8 머리·옆 칸 skx 토큰 |
| L 탐색 중 움직임 | L1 → L6 | L1 절 자리 순수 함수 · L2 `ReportSkeleton.vue`·연결 · L3 회차 미세 상태 · L4 후보 이벤트 타입·리듀서 · L5 장부 '검토 중' 더미·장부 배치 · L6 (선행 조건 — 06c dev 머지 뒤) dev 받기·"이렇게 이해했어요" 바인딩 |
| N 입구 | N1 → N9 | N1 문구 '소장자료검색' · N2 기록 목록 total · N3 사이드바 단계·폴링·모두 보기 (N) · N4 [딥리서치로 더 깊게] · N5 `/research` 홈(자르는 순서 2) · N6 [담기 ▾](자르는 순서 1) · N7 (조건부 — N5 를 잘랐을 때만) 사이드바 예시 묶음 · N8 (조건부 — 06e 가 먼저 dev 에 머지됐을 때만) LNB 접기 연결 · N9 탐색 방식(폭넓게 · 정밀하게 — 10-12 사용자 결정 D28, 실행은 N6(또는 N7) 뒤·L6 앞 — 번호를 다시 매기지 않으려고 N9) |
| Z 마무리 | Z1 → Z7 | Z1 전체 회귀·경계 확인·정적 리뷰·반영 · Z2 06c 판정 연계(랜딩 논문 예시 셋) · Z3 문서(완료노트·00_status·spec) · Z4 dev 머지(사용자 승인) · Z5 운영 배포(사용자) · Z6 운영 처음부터 끝까지 1회(사용자) · Z7 배포 기록 |

**전역 실행 순서(파트가 서로의 파일·이름을 쓴다 — 이 순서로 한다):** Task 0 → D1 → D2 → D3 → D4 → D5 → L1 → L2 → D6 → D7 → L3 → L4 → L5 → D8 → N1 → N2 → N3 → N4 → N5 → N6 → N7(조건부) → N9 → L6(선행 조건) → N8(조건부) → Z1 → Z2 → Z3 → Z4 → Z5 → Z6 → Z7.

**의존:** D3 ← D2 · D4 ← D3 · D5 ← D4 · L2 ← L1·D5 · D6 ← L1 · D7 ← D6·L2·D5 · L3 ← D2 · L4 ← L3 · L5 ← L4 · D8 ← D4·L5 · N3 ← N1·N2 · N5 ← N3 · N6 ← N5·N4 · N7 ← N3 · N9 ← D8(머리 `.rs-status` 크기)·N6(또는 N7 — `research.css` 블록 순서, N5 를 했으면 홈 페이지) · L6 ← L5·D2·06c dev 머지 · N8 ← L6·06e dev 머지 · Z ← 전부. L6 은 06c 가 dev 에 들어오지 않았으면 기다린다 — 나머지 Task 와 Z1 의 회귀·리뷰는 먼저 끝내 둘 수 있다(06d dev 머지는 어차피 06c 운영 배포 뒤다). 그때는 L6 뒤 Z1 Step 1~2 를 다시 돌린다.

**같은 파일 사슬(뒤 Task 의 Edit old 는 앞 Task 뒤 글자다):**
- `pages/research/[id].vue` — D1 → D2 → D4 → D5 → L2 → D7 → L5 → N9 → L6 → N8(조건부). `:57-75` 는 어느 Task 도 손대지 않는다. N9 의 앵커(머리 `:busy`·`@toggle-layout` 두 줄, `researchErrors` import, `retryLabel`, `onRestart` 의 `startResearch`)는 앞 Task 들이 바꾸지 않고, L6·N8 의 앵커와도 겹치지 않는다.
- `assets/css/research.css` — D2 → D4 → D5 → L2 → D7 → L3 → D8 → N4 → N5 → N6 → N9.
- `pages/research/index.vue` — N5 → N9(N5 를 했을 때만).
- `utils/researchEvents.ts` — D2 → L3 → L4 → (L6 merge — 06c 함수 둘이 들어온다, 06d 는 고치지 않음). `tests/unit/researchEvents.test.ts` — D2 → L3 → L4.
- `components/AppSidebar.vue` — N1 → N3 → N7(조건부). `pages/papers/index.vue` — N4 → N6. `composables/useResearchWorks.ts`·`utils/researchHome.ts` — N5 → N6(또는 N7).
- 한 Task 만 고치는 파일: `types/research.ts`(L4), `utils/synthCard.ts`(D3), `SynthProgressCard.vue`(D4), `evidenceLedger.ts`·`EvidenceLedger.vue`·`work.css`·`evidenceLedger.test.ts`(L5), `ProgressPanel.vue`(L3), 기록 네 파일·두 테스트(N2), `restorePosition.ts`·`useRestorePosition.ts`·`restorePosition.test.ts`(D5), `pages/index.vue`(N1 — Task Z2 는 바꿀 것이 있을 때만), `SearchPlusMenu.vue`·`composables/useResearch.ts`·`ResearchHeader.vue`(N9 — 줄 번호가 da80f23 그대로).

**테스트 수 어림(Task 마다 실측으로 적는다):** 기준선 + D3 18 + D5 3 + L1 13 + D6 12 + L3 3 + L4 11 + L5 5 + N2 4 + N3 8 + N4 2 + N5 4 + N6 4 + N9 13 ≈ **+100**(D1·D2·D4·D7·D8·L2·L6·N1·N8 은 +0. N7 은 N5 를 잘랐을 때만이고 그때는 N5 의 +4 대신 +3 — N6 도 하지 않으므로 그 경우 합계 +100 − 4 − 4 + 3 = **+95**), 새 테스트 파일 7개(`researchProgress`·`planSlots`·`researchFollow`·`sidebarResearch`·`researchHome`·`addToWork`·`researchMode`). 실행 중 더한 것: D1 품질 검토 반영 +6(`restorePosition.test.ts` 의 `scrollHolder`·`boxScrollDelta` — Task D5 '알아 둘 것'), D3 품질 검토 반영 +3(`researchProgress.test.ts` 의 재시도 모양), D4 품질 검토 반영 +2(`researchProgress.test.ts` 의 research.css 문서 스크롤 여백 — Task D5 '알아 둘 것'), D6 품질 검토 반영 +4(`researchFollow.test.ts` 12 → 15 — 수식 키 조합 둘·재시도의 갈 곳, `planSlots.test.ts` 13 → 14 — 재시도 모양 — Task D6·L1 '알아 둘 것'). 뒤 Task 의 'da80f23 기준' 절대값은 이 수만큼 크다 — 상대값으로 읽는다.

---

## 파일 구조 (만들고 고칠 파일과 책임)

**프론트 — 새 파일** (`frontend/` 기준)

| 파일 | 책임 | Task |
|---|---|---|
| `utils/researchProgress.ts` | 큰 진행 막대의 단계 표시·큰 글줄·퍼센트·채움·깜빡임과 그리는 조건(순수) — 탐색 비율·두 구간 가중·열린 회차 다가감 | D3 |
| `components/research/ResearchProgressBar.vue` | 고정 진행 영역의 큰 진행 막대(단계 칩·글줄·퍼센트·`role="progressbar"`) — 보기만 받아 그린다 | D4 |
| `utils/planSlots.ts` | 탐색 중 하위질문별 절 자리의 상태·라벨·절 번호 대응(`headings` ↔ 하위질문 글)·새로 모인 자리(순수) | L1 |
| `components/research/ReportSkeleton.vue` | 승인 뒤 첫 절 전까지 본문에 서는 하위질문별 절 자리('하위질문 N'·skeleton·'근거 N편 ✓'·'근거 없음' 접힘) | L2 |
| `utils/researchFollow.ts` | 따라가기를 멈추는 입력·따라갈 대상 id·막힘·옮길지·알약 문구·움직임 방식(순수) | D6 |
| `composables/useSectionFollow.ts` | 창 입력 이벤트를 걸고 대상이 바뀌면 `scrollIntoView` 로 옮기는 따라가기 상태·알약(`resume`·`pause`) | D7 |
| `utils/sidebarResearch.ts` | 사이드바 연구 줄의 진행 중 판단·단계 줄(`workPhase.stepLine` + 수 + '생성 중')·잡 상태 배지(사이드바·/research 홈 공용)·'모두 보기 (N)' 라벨(순수) | N3 |
| `utils/researchHome.ts` | `/research` 홈의 진행 중·내 연구 묶음, 예시 연구의 실행 시각·범위, 예시 연구 주소(순수) | N5(자르면 N7 이 `WorkListItem`·`WorkListOut`·`exampleMeta`·`exampleRoute` 만) |
| `composables/useResearchWorks.ts` | 이어간 연구 목록·기록 목록 50건 읽기(`useResearchWorksApi`), [담기] 목록·담기 상태(`useAddToWork`) | N5·N6(N7 은 `listWorks` 만) |
| `pages/research/index.vue` | `/research` 홈 — 새 연구 시작·진행 중·내 연구·[더 보기]·예시 연구(읽기 전용·실행 시각·코퍼스 범위). 새 연구에 탐색 방식(N9) | N5·N9 |
| `utils/addToWork.ts` | [담기] 의 빈 목록 문구(D17)·담기 본문·고르는 줄·담은 뒤 알림(순수) | N6 |
| `components/research/AddToWorkMenu.vue` | 논문 결과 카드의 [담기 ▾] 메뉴(열기·고르기·Esc·바깥 클릭·초점 복귀) | N6 |
| `utils/researchMode.ts` | 탐색 방식(폭넓게 · 정밀하게) — 선택지·기본값, 방식 → 잡 params 두 칸, 잡 params → 방식·머리 글, 다시 시작의 두 칸, radiogroup 키, 기억 읽기·쓰기(try/catch)(순수) | N9 |
| `components/research/ResearchModePicker.vue` | 탐색 방식 두 칸 선택(`role="radiogroup"`·`aria-checked`·roving tabindex·방향키·Home·End, 고른 칸의 설명) — v-model 만 주고받는다 | N9 |
| `tests/unit/researchProgress.test.ts`·`planSlots.test.ts`·`researchFollow.test.ts`·`sidebarResearch.test.ts`·`researchHome.test.ts`·`addToWork.test.ts`·`researchMode.test.ts` | 위 순수 함수의 vitest | D3·L1·D6·N3·N5(N7)·N6·N9 |

**프론트 — 고칠 파일**

| 파일 | 고치는 것 | Task |
|---|---|---|
| `pages/research/[id].vue` | 배치 계산(D1), 대기 카드·`queueLine` import(D2), 막대 자리·`barView`·`useNow` exploring(D4), 위치 복원 inset(D5), 절 자리 연결·탐색 중 PlanCard 지움(L2), 따라가기·알약·`jumpToSection` 멈춤(D7), 옆 칸 장부를 맨 위로(L5), "이렇게 이해했어요" 두 곳(L6), LNB 두 곳(N8 — 조건부), 머리의 탐색 방식·다시 시작의 잡 params(N9) | D1·D2·D4·D5·L2·D7·L5·N9·L6·N8 |
| `utils/researchLayout.ts` · `tests/unit/researchLayout.test.ts` | 넓은 화면 처음부터 A, `effectiveLayout` 두 인자 | D1 |
| `utils/researchEvents.ts` | `queueLine` 다시 내보내기 지움(D2), `roundStatusLabel`(L3), `candidates` 리듀서·`reviewing` 지우기(L4) | D2·L3·L4 |
| `tests/unit/queueLine.test.ts` · `tests/unit/researchEvents.test.ts` | 다시 내보내기 테스트 뒤집기·import(D2), 회차 미세 상태·후보 이벤트 describe(L3·L4) | D2·L3·L4 |
| `assets/css/research.css` | `.rs-card__text`(D2), 토큰·`.rs-pbar*`·옛 `.rs-synth__bar` 지움·인쇄·문서 `scroll-padding-top`(D4·그 품질 검토 반영), 옆 칸 top(D5), `.rs-slot*`(L2), `.rs-follow-pill`(D7), `.rs-round__state`(L3), 머리·상태·옆 칸 카드 머리(D8), `.rs-deeper`(N4), `.rs-home*`(N5), `.rs-basket*`(N6), `.rs-mode*`·`.rs-head__meta`·`.rs-head__mode`(N9) | D2~N9 |
| `utils/synthCard.ts` | `RUNNING_CAP` export | D3 |
| `components/research/SynthProgressCard.vue` | 작은 막대 걷기(절 목록·[초안 저장]·요약은 그대로) | D4 |
| `utils/restorePosition.ts` · `composables/useRestorePosition.ts` · `tests/unit/restorePosition.test.ts` | `insetTargetTop`·`topInset` | D5 |
| `components/research/ProgressPanel.vue` | 회차 줄 미세 상태 | L3 |
| `types/research.ts` | `CandidatesEvent`·`ReviewingView`·`SubqView.reviewing?` | L4 |
| `utils/evidenceLedger.ts` · `components/work/EvidenceLedger.vue` · `assets/css/work.css`(근거 장부 블록) · `tests/unit/evidenceLedger.test.ts` | '검토 중' 묶음·알림·흐린 카드와 반짝임·장부 간격 | L5 |
| `pages/index.vue` | '소장자료검색'·낭독·입력창 안내(N1), 랜딩 논문 예시(Task Z2 — 바꿀 것이 있을 때만) | N1·Z2 |
| `components/AppSidebar.vue` | 기록 탭 '소장자료'(N1), 연구 줄 단계·폴링 조건·모두 보기(N3), 예시 묶음(N7 — 조건부) | N1·N3·N7 |
| `types/history.ts` · `utils/historyStore.ts` · `utils/historyState.ts` · `composables/useHistory.ts` · `tests/unit/historyStore.test.ts` · `tests/unit/historyState.test.ts` | 기록 목록 `total` 받기·`totalOf` | N2 |
| `utils/paperResearch.ts` · `tests/unit/paperResearch.test.ts` · `pages/papers/index.vue` | `deeperResearchUrl`·답 끝 카드(N4), 결과 카드 [담기 ▾](N6) | N4·N6 |
| `components/research/SearchPlusMenu.vue` | 딥리서치 칩 옆 탐색 방식 두 칸·기억 읽기·`submit` 이 잡 params 를 싣는다 — 06d 파일(06e·06c 는 고치지 않는다) | N9 |
| `composables/useResearch.ts` | `useResearchStarter().startResearch(question, params?)` — 잡 params 를 `create` 에 넘긴다(나머지는 그대로) | N9 |
| `components/research/ResearchHeader.vue` | 상태 배지를 `.rs-head__meta` 한 줄로 묶고 옆에 그 잡의 탐색 방식(선택 prop `modeLine`) — Task D8 은 이 파일을 고치지 않는다 | N9 |

**문서**(Task Z3·Z7): `docs/roadmap/round06d-완료노트.md`(새), `docs/roadmap/00_status.md`(round06 줄만), spec(머리 상태 줄·D22·D26·§12-3 두 행·§12-11 두 항목), 필요하면 `docs/ops/recurring-gotchas.md`.

## 하지 않는 것

사이드바 시안 묶음(탭 대신 묶음·'● 진행 중 1' 배지·줄마다 진행 막대 — 대회 뒤, Q8), 메인 [빠른검색|딥리서치] 모드 토글·도서 숨김(대회 뒤, D26), 연구 화면 머리 위 skx 검색바(대회 뒤, Q8), 글자 스트리밍·타자 효과(절이 끝나면 나타나는 `rs-reveal` 그대로), 다른 브라우저 이어가기 목록(대회 뒤 — D4 소유·보안과 함께, [담기] 는 같은 브라우저의 이어간 연구만), ETA 표본 섞임(리허설 전 — 06b 이월 §7-1), 탐색 남은 시간(대회 뒤 — 백엔드 단계 시각 필요, §12-9), 원문 뷰어 안 하이라이트·외부 확인 링크·[주제로 넓히기](대회 뒤 / 06e), 연구 맥락을 반영한 딥리드 첫 화면(§12-11 선택 — 하지 않는다), 06e 자동 보고서 화면의 큰 진행 막대(10-11 사용자 확인 — 06e 계획 정함 28, 06e 몫), 탐색 방식의 서버 기본값 바꾸기(D28 — `DEFAULT_PARAMS` 0 그대로)·두 스위치를 따로 고르는 칸·다른 잡 파라미터(`max_recheck` 등) 고르기, 백엔드·스키마 변경 전부.

---

## 작업

### Task 0: worktree·기준선 확인

**왜:** 06d 는 그때의 `dev` 에서 따는 줄이다. spec 개정(10-08 회의 D19~D27·§12, Q1·Q8·Q9 답, 후보 이벤트 계약 `subq_idx`)이 dev 에 있어야 06c·06d·06e 가 같은 정본을 읽는다 — 그 확인이 이 계획의 선행 조건이다. worktree 는 본 작업 폴더에서 checkout 하지 않고 `git worktree add` 로 만든다(다른 세션이 깨진다). 시작 전에 테스트 수를 재 두어야 각 Task 가 더한 수와 깨뜨린 것을 가를 수 있다. 계획의 줄 번호가 da80f23 기준이므로 dev 의 `frontend` 가 그 뒤 바뀌었는지도 본다.

**Files:** 없음 (작업 환경과 기준선만 — 이 계획서가 dev 에 없을 때만 Step 3 의 계획 커밋 1개)

**알아 둘 것:**
- 로컬 `dev` 는 `origin/dev` 보다 뒤처져 있을 수 있다. `dev` 를 checkout 한 worktree 가 없으면 `git fetch origin dev:dev` 로 빨리 감는다(checkout 이 아니다). `refusing to fetch into branch 'refs/heads/dev' checked out at …` 이 나오면 그 worktree(대개 남은 `.worktrees/dev-merge`)가 있는 것이다 — 그 worktree 가 지금 쓰이는지 사용자에게 묻고, 쓰이지 않으면 `git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge` 뒤 다시 한다.
- 2026-10-08 실측: 로컬 `dev` = `origin/dev` = `da80f23`. spec 개정 커밋 셋(`2860595`·`65e257b`·`c5d05b0` — 마지막이 §12-2 후보 이벤트 키를 `subq_idx` 로 맞춘 커밋)은 브랜치 `docs/round06-meeting-1008-spec` 에만 있다. 그 브랜치를 dev 에 머지하는 것은 계획 확정 단계(사용자 승인)의 몫이다 — 이 Task 는 확인만 하고, 없으면 멈춘다.
- 06d 는 06c 보다 먼저 딸 수도 뒤에 딸 수도 있다(구현은 10/10~ 병렬). 06c 가 이미 dev 에 머지돼 있으면 기준선이 06c 테스트만큼 크고, Task L6 의 dev 받기는 새로 받을 것이 없을 수 있다 — Step 1 의 출력으로 갈라 적어 둔다.
- `.worktrees/dev-merge` 는 06b 가 남긴 빈 폴더일 수 있다(06b 완료노트 §7-17, worktree 등록은 없음). `git worktree add` 는 빈 폴더에 그대로 만든다.

- [ ] **Step 1: 선행 조건 — spec 개정이 dev 에 있는가, dev 는 어디까지 왔나**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline -1 dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI merge-base --is-ancestor 2860595 dev && echo "2860595 dev 에 있음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI merge-base --is-ancestor 65e257b dev && echo "65e257b dev 에 있음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI show dev:docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md | grep -c "subq_idx, round, papers"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline --merges da80f23..dev | grep -c "feat/round06d-"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline --merges da80f23..dev | grep -cE "feat/round06(c|e)-"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI diff --stat da80f23 dev -- frontend
git -C C:/Users/LANDSOFT/mygit/NL_library_AI ls-tree --name-only dev docs/superpowers/plans/ | grep -c "round06c"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c "worktrees/round06d "
git -C C:/Users/LANDSOFT/mygit/NL_library_AI branch --list feat/round06d-research-progress-screen
```

Expected:
- `fetch` — 이미 같으면 출력 없음, 앞서 있으면 `da80f23..<커밋>  dev -> dev` 한 줄
- `log -1 dev` — spec 브랜치를 머지한 커밋(또는 그 뒤) 한 줄. 이 커밋을 '분기 dev' 로 적어 둔다(완료노트 머리에 쓴다)
- `2860595 dev 에 있음`·`65e257b dev 에 있음` 두 줄
- `subq_idx, round, papers` → `1`(후보 이벤트 계약이 dev 의 spec 에 있다)
- 06d 머지 → `0`
- 06c·06e 머지 → `0`(06c 보다 먼저 땄다) 또는 `1`(06c 가 먼저 머지됐다 — 06e 는 06c 운영 배포 뒤라 이 시점에 없다). 값을 적어 둔다
- `diff --stat da80f23 dev -- frontend` — 06c·06e 머지가 0 이면 빈 출력(계획의 da80f23 줄 번호가 그대로 맞다). 06c 가 머지돼 있으면 06c 의 화면 한 줄 파일만 나온다: `frontend/components/research/PlanCard.vue`·`frontend/tests/fixtures/term_checks.json`·`frontend/tests/unit/researchEvents.test.ts`·`frontend/types/research.ts`·`frontend/utils/researchEvents.ts` — 이때 `researchEvents.ts`·`types/research.ts` 의 줄은 계획의 da80f23 값보다 밀려 있으니 그 두 파일은 처음 고치는 Task(D2·L4)도 앵커 글자로 자리를 잡는다. 다른 파일이 나오면 적어 두고 그 파일을 고치는 Task 를 앵커 글자로 한다
- `round06c` 계획 → `1` 이면 Task L4 Step 0 이 dev 의 06c 계획을 읽는다. `0` 이면 `.worktrees/round06c/docs/superpowers/plans/` 의 사본을 읽는다
- worktree → `0`, 브랜치 → 빈 출력

멈출 때: 두 커밋 중 하나라도 없거나 `subq_idx` 확인이 `1` 이 아니면 **여기서 멈추고 사용자에게 알린다** — spec 브랜치의 dev 머지(사용자 승인)가 먼저다. 06d 를 옛 spec 의 dev 에서 따지 않는다. 06d 머지가 이미 있으면(다른 세션이 이 줄을 이미 넣었다) 역시 멈추고 묻는다.

- [ ] **Step 2: worktree·브랜치를 dev 에서 만든다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add -b feat/round06d-research-progress-screen .worktrees/round06d dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d status --short --branch
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d config --show-origin core.autocrlf
```

Expected:
- `Preparing worktree (new branch 'feat/round06d-research-progress-screen')` 와 `HEAD is now at <Step 1 의 dev 커밋> …`
- `status` — `## feat/round06d-research-progress-screen` 한 줄(변경 줄 없음)
- `log -1` — Step 1 의 dev 커밋과 같은 줄
- `file:C:/Program Files/Git/etc/gitconfig	true` — 작업 트리 파일이 CRLF 다. 기존 파일은 Edit 도구로 고친다

- [ ] **Step 3: 이 계획서를 브랜치에 넣는다 — dev 에 이미 있으면 건너뛴다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d cat-file -e HEAD:docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md && echo "계획서 있음" || echo "계획서 없음"
```

`계획서 있음` 이면 이 Step 은 끝이다. `계획서 없음` 이면 이 계획서를 연 파일 경로를 `PLAN_SRC` 에 넣고 브랜치의 첫 커밋으로 넣는다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && cp "$PLAN_SRC" docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md && git add docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md && git commit -m "[Docs] round06d 계획 — 진행 화면·입구(Task 0 · D1~D8 · L1~L6 · N1~N9 · Z1~Z7, 정함 1~19). 넓은 화면 처음부터 2단, 위에 고정한 큰 진행 막대 하나(Q1 — 단계 표시·큰 글줄·퍼센트, 탐색 중에도 같은 막대), 지금 진행하는 절 따라가기·알약, 탐색 중 하위질문별 절 자리, 회차 미세 상태, 06c 후보 이벤트로 근거 장부 '검토 중' 더미(Q9), /research 홈·사이드바 단계·모두 보기 (N)·빠른검색 [딥리서치로 더 깊게]·[담기]·'소장자료검색' 문구, 딥리서치를 시작할 때 고르는 탐색 방식(폭넓게 · 정밀하게, 기본 정밀하게 — D28). nuxt 만, 06c 운영 배포 뒤 dev 머지, 10/17~18 배포"
```

Expected: 커밋 1개, `git status --short` 빈 출력.

- [ ] **Step 4: 백엔드 기준선(06d 는 바꾸지 않는다 — 회귀의 기준만)**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 마지막 줄 `5 failed, 2327 passed, 1 skipped, 2 warnings, 1 error`(25~30초 — npm 과 함께 돌면 50초 남짓). 그 위 요약 줄은 정확히 다음 여섯이다.

```text
FAILED tests/test_build_manifest.py::test_build_manifest_matching
FAILED tests/test_build_manifest.py::test_build_manifest_csv_input
FAILED tests/test_loaders.py::test_marc_mods_loader_detect_and_load
FAILED tests/test_loaders.py::test_profile_loaders_and_autodetect
FAILED tests/test_loaders.py::test_legacy_parser_import_paths_still_work
ERROR tests/test_book_chat.py
```

Step 1 에서 06c 머지가 `1` 이었으면 `passed` 는 2327 에 06c 가 더한 백엔드 테스트 수만큼 크다 — 나온 수를 적어 두고(실패 5·오류 1 은 같은 여섯 줄) Task Z1 의 기준으로 쓴다.

- [ ] **Step 5: 프론트 기준선**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm ci
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchLayout.test.ts tests/unit/queueLine.test.ts tests/unit/researchEvents.test.ts tests/unit/synthCard.test.ts tests/unit/restorePosition.test.ts tests/unit/evidenceLedger.test.ts tests/unit/historyStore.test.ts tests/unit/historyState.test.ts tests/unit/paperResearch.test.ts tests/unit/researchDraft.test.ts tests/unit/workPhase.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d status --short
```

Expected (2026-10-08 같은 코드에서 실측):
- `npm ci` — 35초 남짓, 786 패키지. 끝의 `npm audit` 안내(`37 vulnerabilities (3 low, 5 moderate, 21 high, 8 critical)`)는 실패가 아니다
- typecheck 오류 — `0`
- `Duplicated imports` — `2`(`queueLine` 경고 두 줄 — Task D2 가 `0` 으로 만든다). `[Vue] Resolve plugin path failed …` 경고는 기준선에도 나온다
- vitest 전체 — `Test Files  40 passed (40)` / `Tests  732 passed (732)`
- 06d 묶음 열한 파일 — `Test Files  11 passed (11)` / `Tests  299 passed (299)`. 파일별 수와 고치는 Task:

  | 파일 | Tests | 고치는 Task | 파일 | Tests | 고치는 Task |
  |---|---|---|---|---|---|
  | `researchLayout.test.ts` | 3 | D1(전체 다시 쓰기, 3 → 3) | `historyStore.test.ts` | 58 | N2 |
  | `queueLine.test.ts` | 5 | D2(+0) | `historyState.test.ts` | 21 | N2 |
  | `researchEvents.test.ts` | 102 | D2(import)·L3·L4 | `paperResearch.test.ts` | 10 | N4 |
  | `synthCard.test.ts` | 24 | (그대로 — D3 은 `RUNNING_CAP` export 만) | `researchDraft.test.ts` | 23 | (그대로 — spec §12-7) |
  | `restorePosition.test.ts` | 18 | D5 | `workPhase.test.ts` | 20 | (그대로 — 06e 파일, 사이드바가 읽기만) |
  | `evidenceLedger.test.ts` | 15 | L5 | 새 일곱 파일 | 없음 | D3·L1·D6·N3·N5(N7)·N6·N9 가 만든다 |

- build — 30초 남짓, `└  ✨ Build complete!`(로그의 `error` 낱말은 `error-404`·`error-500` 청크 이름뿐이다)
- `git status --short` — 빈 출력(`node_modules`·`.nuxt`·`.output` 은 `.gitignore` 에 있다)

Step 1 에서 06c 머지가 `1` 이었으면 vitest 전체·`researchEvents.test.ts`(·묶음 합계)가 06c 의 화면 한 줄 테스트만큼 크다 — 나온 수를 적어 두고 각 Task 의 '앞 수' 로 쓴다.

---

## 파트 D — 진행 화면 뼈대 — 2단·큰 진행 막대·따라가기

spec §12-3 '진행 화면(D22)' 표 가운데 이 파트가 덮는 행: **처음부터 2단(A)**(Task D1) · **고정 진행 영역 = Q1 큰 진행 막대**(순수 함수 Task D3, 부품·연결·현황 카드 막대 옮기기 Task D4) · **오프셋**(Task D5) · **지금 진행하는 절 따라가기**(판단 Task D6, 연결·알약 Task D7) · **스타일 — 머리·진행 영역·옆 칸 skx 토큰**(Task D8, 진행 영역 자체는 D4) · **06b 이월 §7-1·§7-5**(Task D2). '글이 나타나는 방식'(절이 끝나면 나타남 — `rs-reveal`)은 바꿀 것이 없어 Task 가 없다. 이 파트의 결정은 계획 머리 '정함' 표의 정함 1~7 이다(두 구간 가중 진행·탐색 비율·막대 높이 토큰·입력으로만 멈춤·막힘·돌아온 화면은 멈춘 채 시작·알약 문구).

**10-11 사용자 확인('보고서 화면에도 넣으라고 한 것이 맞아')과 이 파트:** 큰 진행 막대는 이 파트의 딥리서치 진행 화면(탐색 중·보고서 작성 중 — 초안 절이 쌓이는 보고서 화면)에 서고, 06e 자동 보고서 화면(이어간 연구 `?s=proposal`)의 같은 크기 막대는 06e 몫이다(06e 계획 정함 28 — `.wk-rbar`·`--wk-bar-thick`). 이 파트의 막대는 단계 화면(stepMode)·끝난 잡에서 서지 않으므로(`showsProgressBar` — Task D3 테스트) 한 화면에 큰 막대 둘이 서지 않는다. 두 막대는 Q1 치수(두께 1rem·768px 이하 0.75rem, 큰 글줄 1rem 굵게, 퍼센트 1.25rem 굵게)를 **값으로만** 맞춘다 — 이 파트는 `.wk-rbar`·`--wk-bar-thick` 를 정의하지 않는다(Task D4 확인). 이 확인으로 이 파트의 Task·테스트 수는 바뀌지 않는다.

실행 순서는 파트 L 과 엇갈린다: D1 → D2 → D3 → D4 → D5 → (L1 → L2) → D6 → D7 → (L3 → L4 → L5) → D8. `[id].vue`·`research.css` 의 자리는 **D1 만 da80f23 줄 그대로**이고 D2 부터는 각 Step 의 앵커 글자(Edit 의 old)로 잡는다 — 줄 번호는 '(da80f23 :N)' 참고값이다.

---

### Task D1: 처음부터 2단 — `effectiveLayout` 에서 보고서 조건 빼기

spec §12-3 '처음부터 2단(A)' 행 · D22 · Q8(토글 유지 동의). round04c `2e3d87a` 는 "보고서 전에는 문서형(B), 보고서 자리가 생기면 2단(A)" 으로 바꾸고 손으로 고른 보기를 보고서가 나올 때 풀었다. 06d 는 탐색 중에도 본문(하위질문별 절 자리 — Task L2)과 옆 칸(진행 패널·근거 장부)을 함께 보이려고 넓은 화면을 처음부터 A 로 연다. **앞으로 고친다 — revert 하지 않는다**(뒤 커밋 `df61ae8`·`e520256`·`616963a` 와 충돌하고, 2e3d87a 가 지운 localStorage 기억 `skx_research_layout` 이 되살아난다).

**알아 둘 것:**
- `LAYOUT_BEFORE_REPORT`·`LAYOUT_WITH_REPORT` 를 지우고 `WIDE_LAYOUT = "A"` 하나로 둔다(공통 계약 '고치는 파일의 새·바뀐 공개 이름' 표). 부르는 곳은 `[id].vue:327` 과 테스트뿐이다 — `utils/researchReport.ts:114` 의 `reportSlot(…, hasReport, …)` 인자는 이름만 같은 다른 것이다.
- 보고서가 나올 때 고른 보기를 풀던 `watch(hasReport, …)`(da80f23 :333-336)를 지운다 — 남기면 [문서형으로 보기]를 고른 사람이 첫 절이 완성되는 순간 A 로 끌려간다. 고른 보기는 이번 방문 동안 그대로 따르고 저장하지 않는다(2e3d87a 그대로).
- [문서형으로 보기] 토글(`canToggle`·`toggleLayout`, `ResearchHeader.vue:10-12`)은 그대로다. 좁은 화면(<`WIDE_MIN_PX` 1200)은 늘 B.
- `[id].vue` 를 이 줄에서 처음 고치는 Task 라 줄 번호가 da80f23 그대로다.

**Files:**
- Modify: `frontend/utils/researchLayout.ts`(전체 18줄 — 다시 쓴다)
- Modify: `frontend/pages/research/[id].vue`(:320-336 배치 블록)
- Test: `frontend/tests/unit/researchLayout.test.ts`(전체 다시 쓰기 — 3 → 3)

기준선: Task 0 실측(Task 0 기준선이 da80f23 과 같으면 vitest `40 files / 732`).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchLayout.test.ts` (전체를 다음으로 바꾼다):

```ts
// frontend/tests/unit/researchLayout.test.ts
import { describe, expect, it } from "vitest";
import { WIDE_LAYOUT, effectiveLayout } from "~/utils/researchLayout";

describe("effectiveLayout", () => {
  it("넓은 화면은 처음부터 2단이다 — 보고서를 기다리지 않는다", () => {
    expect(WIDE_LAYOUT).toBe("A");
    expect(effectiveLayout(null, true)).toBe("A");
  });

  it("넓은 화면은 손으로 고른 보기를 먼저 따른다", () => {
    expect(effectiveLayout("B", true)).toBe("B");
    expect(effectiveLayout("A", true)).toBe("A");
  });

  it("좁은 화면은 고른 보기와 무관하게 B 다", () => {
    expect(effectiveLayout("A", false)).toBe("B");
    expect(effectiveLayout("B", false)).toBe("B");
    expect(effectiveLayout(null, false)).toBe("B");
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchLayout.test.ts`
Expected: `Test Files 1 failed (1)` / `Tests 1 failed | 2 passed (3)` — `× effectiveLayout > 넓은 화면은 처음부터 2단이다 — 보고서를 기다리지 않는다` 가 `AssertionError: expected undefined to be 'A' // Object.is equality`(`expect(WIDE_LAYOUT).toBe("A")` 줄 — 이름이 아직 없다). 나머지 둘은 옛 함수에서도 통과한다(세 번째 인자 없이 불러도 고른 보기·좁은 화면 규칙은 같다).

- [ ] **Step 3: 구현한다**

`frontend/utils/researchLayout.ts` (전체를 다음으로 바꾼다):

```ts
// frontend/utils/researchLayout.ts
export type ResearchLayout = "A" | "B";

// 넓은 화면은 처음부터 2단(A)이다 — 탐색 중에도 본문(하위질문별 절 자리)과 옆 칸(진행 패널·근거 장부)을 함께 보고,
// 보고서가 나와도 배치가 바뀌지 않는다(spec D22 — round04c 의 '보고서 전 문서형(B) → 보고서 뒤 2단' 전환을 앞으로 고침).
// 아래 값은 화면 기획자가 정할 값이다. 바뀌면 값만 바꾼다.
export const WIDE_LAYOUT: ResearchLayout = "A";
export const WIDE_MIN_PX = 1200;
export const SHOW_LAYOUT_TOGGLE = true;

// 2단은 폭이 모자라면 본문이 좁아져 읽을 수 없다 — 좁은 화면은 선택과 무관하게 B 다.
// override 는 이번 방문에서 사용자가 손으로 고른 보기다(저장하지 않는다). 단계가 바뀌어도 그대로 따른다
export function effectiveLayout(override: ResearchLayout | null, wide: boolean): ResearchLayout {
  if (!wide) return "B";
  return (SHOW_LAYOUT_TOGGLE ? override : null) ?? WIDE_LAYOUT;
}
```

`frontend/pages/research/[id].vue` — 배치 블록(da80f23 :320-336). `:245` 의 import(`SHOW_LAYOUT_TOGGLE, WIDE_MIN_PX, effectiveLayout, type ResearchLayout`)는 이름이 그대로라 고치지 않는다. old:

```ts
// ── 배치 A·B ──────────────────────────────────────────────
// 보고서 자리가 생기면(초안의 첫 절이 나오거나 완료) 2단으로 바뀐다 — 보고서 섹션을 그리는 조건과 같다
const hasReport = computed(() => !!reportState.value || !!draft.value);
// 서버 렌더에는 폭을 모르므로 넓은 화면으로 두고, 마운트 뒤 실제 폭으로 맞춘다
const wide = ref(true);
// 손으로 고른 보기는 이번 방문의 지금 단계에서만 따른다. 저장해 두면 한 번 고른 사람은 보고서가 나와도 바뀌지 않는다
const layoutOverride = ref<ResearchLayout | null>(null);
const layout = computed(() => effectiveLayout(layoutOverride.value, wide.value, hasReport.value));
// 단계 화면(stepMode)은 탐색·보고서 배치(rs-body)를 그리지 않는다 — 머리에서 보기 전환을 걷는다(눌러도 바뀌지 않다가
// [보고서 보기]로 돌아가는 순간 그때 고른 배치가 갑자기 적용된다). 이어가지 않은 딥리서치·보고서 화면은 그대로다(D15)
const canToggle = computed(() => SHOW_LAYOUT_TOGGLE && wide.value && !stepMode.value);
let media: MediaQueryList | null = null;

// 보고서가 나오는(또는 재시도로 사라지는) 순간 자동 보기로 돌아간다
watch(hasReport, () => {
  layoutOverride.value = null;
});

function onMediaChange(e: MediaQueryListEvent): void {
```

new:

```ts
// ── 배치 A·B ──────────────────────────────────────────────
// 넓은 화면은 처음부터 2단이다 — 탐색 중에도 본문(절 자리)과 옆 칸(진행 패널·근거 장부)을 함께 본다(spec D22)
// 서버 렌더에는 폭을 모르므로 넓은 화면으로 두고, 마운트 뒤 실제 폭으로 맞춘다
const wide = ref(true);
// 손으로 고른 보기는 이번 방문 동안 따른다(저장하지 않는다). 보고서가 나와도 풀지 않는다 — 문서형을 고른 사람이 첫 절이
// 완성되는 순간 2단으로 끌려가지 않게
const layoutOverride = ref<ResearchLayout | null>(null);
const layout = computed(() => effectiveLayout(layoutOverride.value, wide.value));
// 단계 화면(stepMode)은 탐색·보고서 배치(rs-body)를 그리지 않는다 — 머리에서 보기 전환을 걷는다(눌러도 바뀌지 않다가
// [보고서 보기]로 돌아가는 순간 그때 고른 배치가 갑자기 적용된다). 이어가지 않은 딥리서치·보고서 화면은 그대로다(D15)
const canToggle = computed(() => SHOW_LAYOUT_TOGGLE && wide.value && !stepMode.value);
let media: MediaQueryList | null = null;

function onMediaChange(e: MediaQueryListEvent): void {
```

(`watch` 는 `watch(phase, …)`·`watch(step, …)` 가 계속 쓰므로 `:208` import 는 그대로다.)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchLayout.test.ts`
Expected: `Test Files 1 passed (1)` / `Tests 3 passed (3)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: `Test Files` · `Tests` 모두 Task 0 기준선과 같다(+0 — 기준선이 da80f23 과 같으면 `Test Files 40 passed (40)` / `Tests 732 passed (732)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -rn "LAYOUT_BEFORE_REPORT\|LAYOUT_WITH_REPORT\|hasReport\.value" frontend/utils frontend/pages frontend/components frontend/composables frontend/tests`
Expected: (빈 출력)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchLayout.ts "frontend/pages/research/[id].vue" frontend/tests/unit/researchLayout.test.ts && git status --short && git commit -m "[Feat] round06d — 딥리서치 진행 화면을 넓은 화면에서 처음부터 2단(A)으로 연다(D22). researchLayout 의 LAYOUT_BEFORE_REPORT·LAYOUT_WITH_REPORT 를 WIDE_LAYOUT 하나로 바꾸고 effectiveLayout 에서 보고서 조건(hasReport)을 뺀다 — 탐색 중에도 본문과 옆 칸(진행 패널·근거 장부)을 함께 본다. 보고서가 나올 때 고른 보기를 풀던 watch 를 지운다(남기면 문서형을 고른 사람이 첫 절 완성 때 2단으로 끌려간다). round04c 2e3d87a 를 앞으로 고친 것이다 — revert 하지 않아 그때 지운 localStorage 기억은 되살아나지 않는다. [문서형으로 보기] 토글은 그대로, 좁은 화면은 늘 문서형"
```

---

### Task D2: 06b 이월 — `queueLine` 다시 내보내기 지우기·대기 카드 세로 배치

spec §12-3 '06b 이월' 행 · 06b 완료노트 §7-5(`researchEvents.ts` 의 `export { queueLine } from "~/utils/queueLine"` 때문에 Nuxt 자동 import 가 같은 이름을 두 파일에서 보고 typecheck·build 마다 `WARN Duplicated imports "queueLine"` 을 두 줄씩 낸다 — 기준선 `baseline_typecheck.txt`·`baseline_build.txt` 에 있다) · §7-1(대기 카드 `.rs-card--wait` 가 `flex-direction: row` 라 대기열 카드의 두 `<p>`(본문·순번)가 가로로 늘어선다).

**알아 둘 것:**
- 커밋 두 개다 — ① 다시 내보내기를 지우고 부르는 곳을 `~/utils/queueLine` 으로(`[Refactor]`) ② 대기 카드 세로 배치(`[Fix]`).
- 다시 내보내기를 읽는 곳은 `pages/research/[id].vue:234` 와 테스트 두 파일(`queueLine.test.ts:4`·`researchEvents.test.ts:26`)뿐이다. `ProgressPanel.vue:137-138` 은 주석일 뿐 import 하지 않는다. 연구 어시스턴트 쪽(`ProposalSection.vue:225`·`ProposalStep.vue:113`·`topicDeck.ts:15`)은 이미 `~/utils/queueLine` 에서 `genQueueLine` 을 읽는다.
- 대기 카드 글 묶음 `.rs-card__text`(세로·gap 0.2rem)는 Task L6 이 같은 묶음 안에 "이렇게 이해했어요" 한 줄을 더하는 자리다(공통 계약 'DOM id·클래스·CSS 토큰' 표). 계획 중 카드에도 묶음을 둔다(지금은 `<p>` 하나). 대기열 카드에도 스피너를 달고 둘 다 `role="status"`(이 화면의 다른 대기 카드 `:68`·`:176` 과 같게).
- `[id].vue` 의 :80-96(템플릿)·:232-234(import)는 D1 이 고친 :320-336 보다 위라 줄이 밀리지 않았다. `research.css` 는 이 줄에서 처음 고친다.

**Files:**
- Modify: `frontend/utils/researchEvents.ts`(:105-108 — 주석 두 줄·다시 내보내기·뒤 빈 줄)
- Modify: `frontend/pages/research/[id].vue`(:232-234 import, :80-83 계획 중 카드, :93-96 대기열 카드)
- Modify: `frontend/assets/css/research.css`(:79-83 `.rs-card--wait` 바로 아래)
- Test: `frontend/tests/unit/queueLine.test.ts`(:4·:6-13), `frontend/tests/unit/researchEvents.test.ts`(:17-36 import)

기준선: Task D1 뒤 수(da80f23 이면 `40 files / 732`).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/queueLine.test.ts` — old:

```ts
import { queueLine as queueLineFromEvents } from "~/utils/researchEvents";

describe("queueLine — 옮긴 자리", () => {
  it("researchEvents 가 같은 함수를 다시 내보낸다(호출처·기존 테스트가 그대로다)", () => {
    expect(queueLineFromEvents).toBe(queueLine);
```

new:

```ts
import * as events from "~/utils/researchEvents";

describe("queueLine — 옮긴 자리", () => {
  it("queueLine 은 utils/queueLine 한 곳에서만 내보낸다 — researchEvents 는 다시 내보내지 않는다", () => {
    // 같은 이름을 두 파일이 내보내면 Nuxt 자동 import 가 'Duplicated imports' 경고를 내고 한쪽을 버린다(06b 이월 §7-5)
    expect("queueLine" in events).toBe(false);
```

(그 아래 세 줄 `expect(queueLine({ ahead: 2, etaSec: 1500 })).toBe("앞에 2건 · 약 25분");` 등은 그대로다 — `:3` 의 `import { genQueueLine, queueLine } from "~/utils/queueLine";` 이 읽는 함수다.)

`frontend/tests/unit/researchEvents.test.ts` — import 를 옮긴다. old:

```ts
} from "~/types/research";
import {
  applyApproval,
```

new:

```ts
} from "~/types/research";
import { queueLine } from "~/utils/queueLine";
import {
  applyApproval,
```

그리고 old:

```ts
  mergeEvidence,
  queueLine,
  refreshView,
```

new:

```ts
  mergeEvidence,
  refreshView,
```

(`:1369` 의 `describe("queueLine — queued 문구 뒤에 덧붙이는 순번")` 은 그대로 — 같은 함수를 새 자리에서 읽는다.)

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/queueLine.test.ts tests/unit/researchEvents.test.ts`
Expected: `Test Files 1 failed | 1 passed (2)` / `Tests 1 failed | 106 passed (107)` — `× queueLine — 옮긴 자리 > queueLine 은 utils/queueLine 한 곳에서만 내보낸다 — researchEvents 는 다시 내보내지 않는다` 가 `AssertionError: expected true to be false // Object.is equality`. researchEvents 102 는 새 자리의 `queueLine` 으로 그대로 통과한다.

- [ ] **Step 3: 다시 내보내기를 지우고 부르는 곳을 옮긴다**

`frontend/utils/researchEvents.ts` — old:

```ts
// 대기 순번 문구는 utils/queueLine.ts 로 옮겼다(연구 어시스턴트의 생성 대기 문구와 한곳에) — 호출처·기존 테스트가
// 그대로 쓰게 여기서 다시 내보낸다
export { queueLine } from "~/utils/queueLine";

// 승인·재시도 응답이 실은 순번(api/research.py approve·retry) — 첫 하트비트(15초)를 기다리지 않고 바로 보인다.
```

new:

```ts
// 승인·재시도 응답이 실은 순번(api/research.py approve·retry) — 첫 하트비트(15초)를 기다리지 않고 바로 보인다.
```

`frontend/pages/research/[id].vue` — import(da80f23 :232-234). old:

```ts
import { safeLocalStorage } from "~/utils/browserId";
import { draftReport, draftSlots, synthEta, type SynthEta } from "~/utils/researchDraft";
import { queueLine, researchPhase } from "~/utils/researchEvents";
```

new:

```ts
import { safeLocalStorage } from "~/utils/browserId";
import { queueLine } from "~/utils/queueLine";
import { draftReport, draftSlots, synthEta, type SynthEta } from "~/utils/researchDraft";
import { researchPhase } from "~/utils/researchEvents";
```

(Task L6 은 이 `import { researchPhase } from "~/utils/researchEvents";` 한 줄을 앵커로 06c 의 이름 둘을 더한다 — 글자를 바꾸지 않는다.)

- [ ] **Step 4: 통과·경고 사라짐을 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/queueLine.test.ts tests/unit/researchEvents.test.ts`
Expected: `Test Files 2 passed (2)` / `Tests 107 passed (107)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Task D1 뒤와 같은 수(+0 — da80f23 이면 `Test Files 40 passed (40)` / `Tests 732 passed (732)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"`
Expected: `0` (Task 0 기준선은 `2`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | grep -c "Duplicated imports"`
Expected: `0` (기준선 `2`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

- [ ] **Step 5: 커밋한다(①)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchEvents.ts "frontend/pages/research/[id].vue" frontend/tests/unit/queueLine.test.ts frontend/tests/unit/researchEvents.test.ts && git status --short && git commit -m "[Refactor] round06d — researchEvents 의 queueLine 다시 내보내기를 지운다(06b 이월 §7-5). 같은 이름을 utils/queueLine 과 researchEvents 두 파일이 내보내 Nuxt 자동 import 가 typecheck·build 마다 'Duplicated imports \"queueLine\"' 경고를 냈다. 연구 화면과 두 테스트가 ~/utils/queueLine 에서 직접 읽고, queueLine 테스트는 researchEvents 가 이 이름을 내보내지 않음을 고정한다"
```

- [ ] **Step 6: 대기 카드를 세로로 쌓는다**

`frontend/pages/research/[id].vue` — 계획 중 카드(da80f23 :80-83). old:

```html
              <div v-if="phase === 'planning'" class="rs-card rs-card--wait">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <p>연구 계획을 세우는 중입니다</p>
              </div>
```

new:

```html
              <div v-if="phase === 'planning'" class="rs-card rs-card--wait" role="status">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <div class="rs-card__text">
                  <p>연구 계획을 세우는 중입니다</p>
                </div>
              </div>
```

대기열 카드(da80f23 :93-96). old:

```html
              <div v-else-if="phase === 'queued'" class="rs-card rs-card--wait">
                <p>앞선 연구가 끝나면 시작합니다</p>
                <p v-if="queueText" class="rs-muted">{{ queueText }}</p>
              </div>
```

new:

```html
              <div v-else-if="phase === 'queued'" class="rs-card rs-card--wait" role="status">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <div class="rs-card__text">
                  <p>앞선 연구가 끝나면 시작합니다</p>
                  <p v-if="queueText" class="rs-muted">{{ queueText }}</p>
                </div>
              </div>
```

`frontend/assets/css/research.css` — `.rs-card--wait`(da80f23 :79-83) 바로 아래. old:

```css
.rs-card--wait {
  flex-direction: row;
  align-items: center;
  font-size: 0.75rem;
}
```

new:

```css
.rs-card--wait {
  flex-direction: row;
  align-items: center;
  font-size: 0.75rem;
}
/* 대기 카드의 글 묶음 — 스피너 옆에 본문과 덧붙인 줄(대기 순번·이해한 질문)을 세로로 쌓는다 */
.rs-card__text {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}
```

- [ ] **Step 7: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Step 4 와 같은 수(+0)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

- [ ] **Step 8: 커밋한다(②)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "frontend/pages/research/[id].vue" frontend/assets/css/research.css && git status --short && git commit -m "[Fix] round06d — 대기 카드의 글 두 줄이 가로로 늘어서던 것을 세로로 쌓는다(06b 이월 §7-1). .rs-card--wait 는 스피너와 글을 가로로 두는 카드라 대기열 카드의 본문·순번 <p> 두 개가 한 줄에 붙었다 — 글을 .rs-card__text 묶음(세로)에 넣는다. 계획 중 카드도 같은 묶음을 쓰고(뒤에 '이렇게 이해했어요' 한 줄이 들어올 자리), 대기열 카드에도 스피너를 달고 두 카드 모두 role=status"
```

---

### Task D3: 진행 막대 순수 함수 `utils/researchProgress.ts`

spec §12-3 '고정 진행 영역' 행(Q1 — 작은 단계 표시·막대 위 큰 글줄·오른쪽 퍼센트, 탐색 중에도 같은 막대, 탐색 비율 = 끝난 하위질문 + 도는 하위질문의 회차 몫, 두 구간 가중치 111:91 상수, 추정 증가 상한 0.9) · §12-7 06d vitest '고정 진행 영역을 그리는 조건·진행 비율·큰 진행 막대의 글줄' · 정함 1·2. 막대에 무엇을 그릴지(단계 칩 상태·글줄·퍼센트·채움 폭·빛 흐름)와 막대를 그릴지를 이 파일의 순수 함수가 정하고, 부품(Task D4)은 그리기만 한다.

**알아 둘 것:**
- **막대 하나 = 두 구간 가중 전체 진행(정함 1).** `fraction = (111 × 탐색 비율 + 91 × 작성 비율) ÷ 202`. 탐색 중에는 작성 비율을 싣지 않고, 작성이 시작되면 탐색 구간은 다 찬 것(1)으로 본다 — 구간마다 0 부터 다시 세면 작성이 시작되는 순간 막대가 뒤로 간다. 작성 비율은 지금 현황 카드 막대와 같은 `barFraction(eta)`(`utils/synthCard.ts:38-53`)다. 퍼센트는 `Math.floor(fraction × 100)` — 다 차기 전에 100 이 보이지 않게 내림. 계획 중·승인 대기·대기열은 퍼센트 없이(`null`) 단계 글줄만, 채움 0.
- **탐색 비율(정함 2).** 하위질문마다 몫을 더해 하위질문 수로 나눈다 — 끝남·실패 1, 대기 0, 도는 하위질문은 `min(RUNNING_CAP, (점검이 끝난 회차 수 + 열린 회차의 다가감) ÷ maxRounds)`. '점검이 끝난 회차' = `RoundView.verdict !== null`(critique 이벤트·진행 저장이 채운다 — `researchEvents.ts:390-420`). '열린 회차' = 회차가 아직 없거나(첫 검색 전) 마지막 회차가 검색만 끝나고 판정을 기다린다(`verdict === null` — `applySearch` 가 만든 회차, `:376-388`). 다가감 = `RUNNING_CAP × (1 − 0.5^(경과 ÷ 6000))` — `barFraction` 의 첫 절 다가감(`synthCard.ts:49`)과 같은 꼴, 반감기만 회차 크기(실측 탐색 111초 ÷ 6 하위질문 ≈ 회차당 십수 초)에 맞춘 6초. 경과는 **화면이 그 회차를 처음 본 뒤** 지난 시간이다(서버는 회차 시각을 주지 않는다 — Task D4 가 `activeRoundKey` 가 바뀐 시각을 잰다). 판정이 나면 열린 회차의 다가감(≤ 0.9)이 끝난 회차 한 칸(1)으로 바뀌어 막대는 늘 앞으로만 간다.
- **`maxRounds = max_recheck + 1`.** 잡 파라미터의 재검색 상한(`app/services/research/state.py:20` 기본 3, `:42` 검증 범위 정수 0~10)에 첫 검색 한 번을 더한다. 값이 없거나 범위 밖이면 `DEFAULT_MAX_RECHECK + 1` = 4. `ResearchParams` 는 `Record<string, number>`(`types/research.ts:19`).
- **`RUNNING_CAP` 은 `utils/synthCard.ts:6` 이 내보내고 이 파일은 import 한다** — 지금은 `const` 다. 같은 0.9 를 이 파일에 따로 두면 두 막대의 상한이 따로 놀고, 같은 이름을 두 파일이 내보내면 Nuxt 자동 import 가 `WARN Duplicated imports` 를 낸다(Task D2 가 없앤 경고). 이 파일의 새 이름은 모두 `.nuxt/imports.d.ts`(da80f23)에 없는 이름이다.
- **`activeRoundKey` 는 회차가 아직 없을 때도 1회차로 센다**(`${idx}:${Math.max(1, rounds.length)}:${마지막 회차 verdict ?? "open"}`) — 하위질문이 막 돌기 시작한 때(회차 없음)와 첫 검색 이벤트가 온 때(1회차·판정 없음)는 같은 열린 회차라, 열쇠가 바뀌어 다가감이 0 으로 돌아가며 막대가 뒤로 가지 않게 한다(파트 D 끝 '파트 메모' 1).
- **`showsProgressBar(phase, stepMode)` 가 머리 겹침 없음의 보증이다** — 끝난 잡(completed·failed·canceled)과 단계 화면(stepMode — 끝난 잡의 이어간 연구)에서는 false. WorkStepper(06e — 끝난 잡에만)·06e 자동 보고서의 큰 막대(`?s=proposal` 단계 화면)와 한 화면에 서지 않는다. 06e 파일은 고치지 않는다.
- **큰 글줄(테스트가 글자 그대로 고정한다):** 계획 중 `연구 계획을 세우는 중` · 승인 대기 `계획 확인 대기 · 승인하면 근거 수집을 시작합니다` · 대기열 `대기열 · ${queueNote}`(순번 문구가 없으면 `대기열 · 앞선 연구가 끝나면 시작합니다`) · 탐색 `근거 수집 중 · 하위질문 ${k}/${n} — 「${하위질문}」`(k = 도는 하위질문, 없으면 첫 대기 하위질문, 그것도 없으면 마지막 하위질문 · 하위질문이 없으면 `근거 수집을 시작하는 중`) · 작성 `보고서 작성 중 · ${i}/${n}절 — 「${절 제목}」`(i = 쓰는 절, 절 사이면 다음 절 · 절 수를 모르면 `보고서 작성을 준비하는 중` · 다 끝났으면 `보고서를 마무리하는 중`). 절 제목은 `draftSlots` 의 `heading`(`researchDraft.ts:145-148` — 이름이 없으면 `절 N`).
- 픽스처는 `SubqView`·`RoundView`·`DraftSlot`·`SynthEta` 를 손으로 만든다(`researchEvents.test.ts`·`synthCard.test.ts` 처럼 작은 공장 함수). vitest 는 Nuxt 를 띄우지 않으므로 쓰는 이름은 모두 명시 import 한다.

**Files:**
- Create: `frontend/utils/researchProgress.ts`
- Modify: `frontend/utils/synthCard.ts`(:5-6 — `RUNNING_CAP` 을 내보낸다)
- Test: `frontend/tests/unit/researchProgress.test.ts`(새 파일 — 18)

기준선: Task D2 뒤 수(da80f23 기준선이면 vitest `40 files / 732`).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchProgress.test.ts` (새 파일):

```ts
// frontend/tests/unit/researchProgress.test.ts
import { describe, expect, it } from "vitest";
import type { RoundView, StepStatus, SubqView } from "~/types/research";
import type { DraftSlot, DraftSlotStatus, SynthEta } from "~/utils/researchDraft";
import {
  DEFAULT_MAX_RECHECK,
  EXPLORE_WEIGHT,
  PROGRESS_STAGES,
  ROUND_HALF_LIFE_MS,
  SYNTH_WEIGHT,
  activeRoundKey,
  exploreFraction,
  maxRoundsOf,
  overallFraction,
  progressBarView,
  progressStage,
  progressStages,
  showsProgressBar,
  type ProgressInput,
} from "~/utils/researchProgress";
import { RUNNING_CAP, barFraction } from "~/utils/synthCard";

function round(n: number, over: Partial<RoundView> = {}): RoundView {
  return {
    round: n, query: `질의 ${n}`, foundChunks: 10, newPapers: 3, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [], ...over,
  };
}

function subq(idx: number, status: StepStatus, rounds: RoundView[] = [], title = `하위질문 ${idx + 1}`): SubqView {
  return {
    idx, title, seq: idx + 1, status, rounds,
    verdict: null, note: "", adopted: null, parseFailed: false, error: null,
  };
}

function eta(over: Partial<SynthEta> = {}): SynthEta {
  return { done: 0, total: 0, runningIdx: null, runningElapsedMs: null, remainingMs: null, ...over };
}

function slot(idx: number, heading: string, status: DraftSlotStatus = "waiting"): DraftSlot {
  return { idx, heading, status, durationMs: null, startedAt: null, sectionIndex: null };
}

function input(over: Partial<ProgressInput> = {}): ProgressInput {
  return {
    phase: "exploring", subqs: [], maxRounds: 4, roundElapsedMs: null, eta: eta(), slots: [], queueNote: null, ...over,
  };
}

// 점검이 끝나고 다음 회차로 재검색하는 회차
const rechecked = (n: number) => round(n, { verdict: "insufficient", nextQuery: `다음 검색어 ${n}` });

describe("progressStage·progressStages", () => {
  it("계획·승인 대기·대기열은 계획, 탐색은 근거 수집, 종합은 보고서 작성, 완료는 완료, 실패·취소는 null", () => {
    expect(progressStage("planning")).toBe("plan");
    expect(progressStage("awaiting")).toBe("plan");
    expect(progressStage("queued")).toBe("plan");
    expect(progressStage("exploring")).toBe("collect");
    expect(progressStage("synthesizing")).toBe("write");
    expect(progressStage("completed")).toBe("done");
    expect(progressStage("failed")).toBeNull();
    expect(progressStage("canceled")).toBeNull();
  });

  it("지금 단계만 current 이고 앞 단계는 done, 뒤 단계는 todo", () => {
    expect(PROGRESS_STAGES.map((s) => s.label)).toEqual(["계획", "근거 수집", "보고서 작성", "완료"]);
    expect(progressStages("collect")).toEqual([
      { key: "plan", label: "계획", state: "done" },
      { key: "collect", label: "근거 수집", state: "current" },
      { key: "write", label: "보고서 작성", state: "todo" },
      { key: "done", label: "완료", state: "todo" },
    ]);
    expect(progressStages("plan").map((s) => s.state)).toEqual(["current", "todo", "todo", "todo"]);
    expect(progressStages("write").map((s) => s.state)).toEqual(["done", "done", "current", "todo"]);
  });
});

describe("maxRoundsOf", () => {
  it("max_recheck + 1 회차, 값이 없거나 범위 밖이면 기본 3 + 1", () => {
    expect(DEFAULT_MAX_RECHECK).toBe(3);
    expect(maxRoundsOf({ max_recheck: 2 })).toBe(3);
    expect(maxRoundsOf({ max_recheck: 0 })).toBe(1);
    expect(maxRoundsOf({ max_recheck: 10 })).toBe(11);
    expect(maxRoundsOf({})).toBe(4);
    expect(maxRoundsOf({ max_recheck: 11 })).toBe(4);
    expect(maxRoundsOf({ max_recheck: -1 })).toBe(4);
    expect(maxRoundsOf({ max_recheck: 1.5 })).toBe(4);
  });
});

describe("exploreFraction", () => {
  it("끝난·실패한 하위질문은 1, 대기는 0 으로 센다", () => {
    expect(exploreFraction([subq(0, "done"), subq(1, "failed"), subq(2, "pending"), subq(3, "pending")], 4, null)).toBe(0.5);
    expect(exploreFraction([subq(0, "done")], 4, null)).toBe(1);
  });

  it("도는 하위질문은 점검이 끝난 회차 ÷ 최대 회차 몫이다", () => {
    // 1회차 점검이 끝나 재검색을 기다린다(다음 회차의 검색 이벤트 전) — 열린 회차가 없어 다가감도 없다
    expect(exploreFraction([subq(0, "running", [rechecked(1)]), subq(1, "pending")], 4, 30_000)).toBe(0.125);
    expect(exploreFraction([subq(0, "running", [rechecked(1), rechecked(2)])], 4, null)).toBe(0.5);
    // 충분 판정으로 끝나기 직전(단계 닫기 전)도 점검이 끝난 회차만큼이다
    expect(exploreFraction([subq(0, "running", [round(1, { verdict: "sufficient" })])], 4, null)).toBe(0.25);
    // 최대 회차가 2 면 같은 1회차가 절반이다
    expect(exploreFraction([subq(0, "running", [rechecked(1)])], 2, null)).toBe(0.5);
  });

  it("검색만 끝난 회차는 경과 시간으로 다가가되 회차 한 칸의 0.9 를 넘지 않는다", () => {
    const open = [subq(0, "running", [round(1)])];
    expect(exploreFraction(open, 4, null)).toBe(0);
    expect(exploreFraction(open, 4, 0)).toBe(0);
    // 반감기 하나가 지나면 한 칸(1/4)의 0.9 × 1/2
    expect(exploreFraction(open, 4, ROUND_HALF_LIFE_MS)).toBeCloseTo((RUNNING_CAP * 0.5) / 4, 10);
    // 회차가 아직 없는(첫 검색 전) 하위질문도 열린 회차로 다가간다
    expect(exploreFraction([subq(0, "running")], 4, ROUND_HALF_LIFE_MS)).toBeCloseTo((RUNNING_CAP * 0.5) / 4, 10);
    // 아무리 오래 기다려도 한 칸의 0.9 를 넘지 않는다
    expect(exploreFraction(open, 4, 600_000)).toBeLessThanOrEqual(RUNNING_CAP / 4);
    // 점검이 끝난 3회차 + 열린 4회차는 하위질문 몫 상한 0.9 에서 멈춘다
    const last = [subq(0, "running", [rechecked(1), rechecked(2), rechecked(3), round(4)])];
    expect(exploreFraction(last, 4, 600_000)).toBe(RUNNING_CAP);
  });

  it("하위질문이 없으면 0", () => {
    expect(exploreFraction([], 4, 5_000)).toBe(0);
  });
});

describe("overallFraction", () => {
  it("탐색 구간은 111, 작성 구간은 91 의 몫이다 — 탐색을 마치면 111/202", () => {
    expect(EXPLORE_WEIGHT).toBe(111);
    expect(SYNTH_WEIGHT).toBe(91);
    expect(overallFraction("collect", 0, 0)).toBe(0);
    expect(overallFraction("collect", 0.5, 0)).toBeCloseTo(55.5 / 202, 10);
    expect(overallFraction("collect", 1, 0)).toBeCloseTo(111 / 202, 10);
    // 탐색 중에는 작성 비율을 싣지 않는다
    expect(overallFraction("collect", 1, 0.8)).toBeCloseTo(111 / 202, 10);
  });

  it("작성 중에는 barFraction 을 작성 구간에 싣고 1 을 넘지 않는다", () => {
    // 작성이 시작되면 탐색 구간은 다 찬 것으로 본다 — 막대가 뒤로 가지 않는다
    expect(overallFraction("write", 0.3, 0)).toBeCloseTo(111 / 202, 10);
    expect(overallFraction("write", 1, 0.5)).toBeCloseTo((111 + 45.5) / 202, 10);
    const e = eta({ done: 2, total: 4, runningIdx: 2, runningElapsedMs: 10_000, remainingMs: 30_000 });
    expect(overallFraction("write", 1, barFraction(e))).toBeCloseTo((111 + 91 * barFraction(e)) / 202, 10);
    expect(overallFraction("write", 1, 1)).toBe(1);
    expect(overallFraction("write", 1, 1.4)).toBe(1);
  });
});

describe("progressBarView", () => {
  it("끝난 잡(완료·실패·취소)은 그리지 않는다", () => {
    for (const phase of ["completed", "failed", "canceled"] as const) {
      expect(progressBarView(input({ phase }))).toBeNull();
    }
  });

  it("계획 중·승인 대기·대기열은 퍼센트 없이 단계 글줄만 — 대기열은 순번 문구를 잇는다", () => {
    expect(progressBarView(input({ phase: "planning" }))).toEqual({
      stages: progressStages("plan"),
      line: "연구 계획을 세우는 중",
      percent: null,
      fraction: 0,
      running: false,
      valueText: "연구 계획을 세우는 중",
    });
    expect(progressBarView(input({ phase: "awaiting" }))?.line).toBe("계획 확인 대기 · 승인하면 근거 수집을 시작합니다");
    expect(progressBarView(input({ phase: "queued", queueNote: "앞에 2건 · 약 25분" }))?.line).toBe("대기열 · 앞에 2건 · 약 25분");
    const queued = progressBarView(input({ phase: "queued" }));
    expect(queued?.line).toBe("대기열 · 앞선 연구가 끝나면 시작합니다");
    expect(queued?.percent).toBeNull();
  });

  it("탐색 중 글줄은 '근거 수집 중 · 하위질문 k/n — 「하위질문」'", () => {
    const subqs = [
      subq(0, "done", [], "노인 우울과 가족 지지"),
      subq(1, "done", [], "지역사회 지지의 효과"),
      subq(2, "running", [round(1)], "사회적 지지 척도 비교"),
      subq(3, "pending"),
      subq(4, "pending"),
      subq(5, "pending"),
    ];
    const v = progressBarView(input({ subqs }))!;
    expect(v.line).toBe("근거 수집 중 · 하위질문 3/6 — 「사회적 지지 척도 비교」");
    expect(v.stages.find((s) => s.state === "current")?.key).toBe("collect");
    expect(v.valueText).toBe(`${v.line} · ${v.percent}%`);
    expect(progressBarView(input({ subqs: [] }))!.line).toBe("근거 수집을 시작하는 중");
  });

  it("도는 하위질문이 없으면(하위질문 사이) 다음 대기 하위질문 번호를 쓴다", () => {
    const between = [subq(0, "done", [], "가"), subq(1, "pending", [], "나"), subq(2, "pending", [], "다")];
    expect(progressBarView(input({ subqs: between }))!.line).toBe("근거 수집 중 · 하위질문 2/3 — 「나」");
    // 모두 끝났고 종합 단계 행이 아직 없으면 마지막 하위질문
    const ended = [subq(0, "done", [], "가"), subq(1, "failed", [], "나")];
    expect(progressBarView(input({ subqs: ended }))!.line).toBe("근거 수집 중 · 하위질문 2/2 — 「나」");
  });

  it("작성 중 글줄은 '보고서 작성 중 · i/n절 — 「절 제목」'", () => {
    const slots = [
      slot(0, "가족 지지", "done"), slot(1, "지역사회 지지", "done"), slot(2, "척도 비교", "running"),
      slot(3, "정책 함의"), slot(4, "연구 공백"), slot(5, "종합"),
    ];
    const v = progressBarView(input({
      phase: "synthesizing", slots, eta: eta({ done: 2, total: 6, runningIdx: 2, runningElapsedMs: 5_000, remainingMs: 120_000 }),
    }))!;
    expect(v.line).toBe("보고서 작성 중 · 3/6절 — 「척도 비교」");
    expect(v.stages.map((s) => s.state)).toEqual(["done", "done", "current", "todo"]);
    // 앞 절이 끝나고 다음 절이 아직 시작되지 않았으면 다음 절
    const gap = progressBarView(input({ phase: "synthesizing", slots, eta: eta({ done: 3, total: 6 }) }))!;
    expect(gap.line).toBe("보고서 작성 중 · 4/6절 — 「정책 함의」");
  });

  it("절 수를 모르면 준비 중, 모든 절이 끝나면 마무리 중", () => {
    expect(progressBarView(input({ phase: "synthesizing", eta: eta({ total: 0 }) }))!.line).toBe("보고서 작성을 준비하는 중");
    const end = progressBarView(input({ phase: "synthesizing", eta: eta({ done: 6, total: 6, remainingMs: 0 }) }))!;
    expect(end.line).toBe("보고서를 마무리하는 중");
    expect(end.percent).toBe(100);
  });

  it("퍼센트는 내림 정수이고 깜빡임(running)은 도는 것이 있을 때만 켠다", () => {
    // 탐색을 마친 순간 = 111/202 = 54.95…% → 54
    const start = progressBarView(input({ phase: "synthesizing", eta: eta({ total: 6 }) }))!;
    expect(start.fraction).toBeCloseTo(111 / 202, 10);
    expect(start.percent).toBe(54);
    expect(start.running).toBe(false);
    expect(progressBarView(input({ phase: "synthesizing", eta: eta({ total: 6, runningIdx: 0, runningElapsedMs: 1_000 }) }))!.running)
      .toBe(true);
    const exploring = progressBarView(input({ subqs: [subq(0, "running"), subq(1, "pending")] }))!;
    expect(exploring.running).toBe(true);
    expect(exploring.percent).toBe(0);
    // 2개 중 1개 끝 = 탐색 비율 0.5 → 55.5/202 = 27.47…% → 27
    const idle = progressBarView(input({ subqs: [subq(0, "done"), subq(1, "pending")] }))!;
    expect(idle.running).toBe(false);
    expect(idle.percent).toBe(27);
  });
});

describe("showsProgressBar", () => {
  it("끝나지 않은 잡에만 그리고 단계 화면(stepMode)에는 그리지 않는다", () => {
    for (const phase of ["planning", "awaiting", "queued", "exploring", "synthesizing"] as const) {
      expect(showsProgressBar(phase, false)).toBe(true);
    }
    for (const phase of ["completed", "failed", "canceled"] as const) {
      expect(showsProgressBar(phase, false)).toBe(false);
    }
    expect(showsProgressBar(null, false)).toBe(false);
    // 단계 화면은 끝난 잡의 이어간 연구에만 선다 — WorkStepper·06e 자동 보고서의 큰 막대와 한 화면에 서지 않는다
    expect(showsProgressBar("completed", true)).toBe(false);
    expect(showsProgressBar("synthesizing", true)).toBe(false);
  });
});

describe("activeRoundKey", () => {
  it("도는 하위질문의 회차가 늘거나 판정이 날 때만 바뀌고, 도는 하위질문이 없으면 null", () => {
    expect(activeRoundKey([subq(0, "done"), subq(1, "pending")])).toBeNull();
    const started = activeRoundKey([subq(0, "done"), subq(1, "running")]);
    const searched = activeRoundKey([subq(0, "done"), subq(1, "running", [round(1)])]);
    // 첫 검색이 와도 같은 열린 회차다 — 다가감이 0 으로 돌아가지 않는다
    expect(searched).toBe(started);
    // 같은 회차에 값만 바뀌어도 그대로다
    expect(activeRoundKey([subq(0, "done"), subq(1, "running", [round(1, { foundChunks: 25 })])])).toBe(searched);
    const judged = activeRoundKey([subq(0, "done"), subq(1, "running", [rechecked(1)])]);
    expect(judged).not.toBe(searched);
    const next = activeRoundKey([subq(0, "done"), subq(1, "running", [rechecked(1), round(2)])]);
    expect(next).not.toBe(judged);
    expect(next).not.toBe(searched);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchProgress.test.ts`
Expected: `FAIL tests/unit/researchProgress.test.ts` — `Error: Cannot find module '~/utils/researchProgress' imported from '…/frontend/tests/unit/researchProgress.test.ts'.` / `Test Files 1 failed (1)` / `Tests no tests`

- [ ] **Step 3: `RUNNING_CAP` 을 내보낸다**

`frontend/utils/synthCard.ts` — old:

```ts
// 쓰는 중인 절이 끝나기 전에 막대가 다 차 보이면 멈춘 것처럼 읽힌다 — 끝날 때까지 이 비율 아래에 둔다
const RUNNING_CAP = 0.9;
```

new:

```ts
// 쓰는 중인 절이 끝나기 전에 막대가 다 차 보이면 멈춘 것처럼 읽힌다 — 끝날 때까지 이 비율 아래에 둔다.
// 큰 진행 막대(utils/researchProgress.ts)의 탐색 구간 추정도 같은 상한을 쓴다 — 이 이름은 이 파일만 내보낸다(Nuxt 자동 import)
export const RUNNING_CAP = 0.9;
```

- [ ] **Step 4: `utils/researchProgress.ts` 를 만든다**

`frontend/utils/researchProgress.ts` (새 파일):

```ts
// frontend/utils/researchProgress.ts
// 연구 화면 위에 고정되는 큰 진행 막대(spec §12-3 '고정 진행 영역', Q1). 작은 단계 표시·막대 위 큰 글줄·오른쪽
// 퍼센트·채움 폭을 정한다. 막대 하나가 근거 수집(탐색)과 보고서 작성(종합) 두 구간을 실측 시간 비율로 나눠 싣는다 — 구간마다
// 0 부터 다시 세면 작성이 시작될 때 막대가 뒤로 간다. 막대는 실제 이벤트로만 움직이고, 이벤트 사이의 추정 증가는 상한
// RUNNING_CAP(synthCard — 작성 막대와 같은 값)을 넘지 않는다
import type { ResearchParams, SubqView } from "~/types/research";
import type { DraftSlot, SynthEta } from "~/utils/researchDraft";
import type { ResearchPhase } from "~/utils/researchEvents";
import { RUNNING_CAP, barFraction } from "~/utils/synthCard";

export type ProgressStage = "plan" | "collect" | "write" | "done";

export interface ProgressStageItem {
  key: ProgressStage;
  label: string;
  state: "done" | "current" | "todo";
}

export const PROGRESS_STAGES: readonly { key: ProgressStage; label: string }[] = [
  { key: "plan", label: "계획" },
  { key: "collect", label: "근거 수집" },
  { key: "write", label: "보고서 작성" },
  { key: "done", label: "완료" },
];
// 두 구간의 몫 — round06a 실측 한 번(202초) 중 탐색 111초·종합 91초(round06a-완료노트 :95)
export const EXPLORE_WEIGHT = 111;
export const SYNTH_WEIGHT = 91;
// 잡 파라미터에 재검색 상한이 없을 때의 값(app/services/research/state.py DEFAULT_PARAMS["max_recheck"])
export const DEFAULT_MAX_RECHECK = 3;
// 열린 회차(검색·자기점검을 기다리는 중)는 6초마다 남은 거리의 절반씩 다가간다 — 실측 회차 하나가 십수 초다
export const ROUND_HALF_LIFE_MS = 6_000;

export interface ProgressInput {
  phase: ResearchPhase;
  subqs: readonly SubqView[];
  maxRounds: number;
  // 열린 회차를 화면이 처음 본 뒤 지난 시간(모르면 null) — 서버는 회차 시각을 주지 않는다
  roundElapsedMs: number | null;
  eta: SynthEta;
  slots: readonly DraftSlot[];
  // 대기 순번 문구(queueLine) — 대기 중이 아니거나 순번을 모르면 null
  queueNote: string | null;
}

export interface ProgressBarView {
  stages: ProgressStageItem[];
  // 막대 위 큰 글줄
  line: string;
  // 0~100 내림 정수. 계획·승인 대기·대기열은 null(퍼센트를 그리지 않는다)
  percent: number | null;
  // 0~1 채움 폭
  fraction: number;
  // 채움 끝의 빛 흐름 — 도는 하위질문·쓰는 절이 있을 때만
  running: boolean;
  // 화면 읽기 프로그램이 막대에서 읽는 글(aria-valuetext)
  valueText: string;
}

const STAGE_OF: Record<ResearchPhase, ProgressStage | null> = {
  planning: "plan",
  awaiting: "plan",
  queued: "plan",
  exploring: "collect",
  synthesizing: "write",
  completed: "done",
  failed: null,
  canceled: null,
};
const ENDED_PHASES: readonly ResearchPhase[] = ["completed", "failed", "canceled"];

export function progressStage(phase: ResearchPhase): ProgressStage | null {
  return STAGE_OF[phase];
}

export function progressStages(current: ProgressStage): ProgressStageItem[] {
  const at = PROGRESS_STAGES.findIndex((s) => s.key === current);
  return PROGRESS_STAGES.map((s, i): ProgressStageItem => ({ ...s, state: i < at ? "done" : i === at ? "current" : "todo" }));
}

// 하위질문 하나가 돌 수 있는 회차 수 = 재검색 상한 + 첫 검색. 서버 검증 범위(state.py :42 — 정수 0~10) 밖이면 기본값
export function maxRoundsOf(params: ResearchParams): number {
  const v = params.max_recheck;
  return typeof v === "number" && Number.isInteger(v) && v >= 0 && v <= 10 ? v + 1 : DEFAULT_MAX_RECHECK + 1;
}

// 회차가 열려 있다 — 첫 검색 전(회차 없음)이거나 마지막 회차가 검색만 끝나고 자기점검을 기다린다
function roundOpen(sq: SubqView): boolean {
  const last = sq.rounds[sq.rounds.length - 1];
  return !last || last.verdict === null;
}

function roundApproach(elapsedMs: number | null): number {
  if (elapsedMs === null) return 0;
  return RUNNING_CAP * (1 - 0.5 ** (Math.max(0, elapsedMs) / ROUND_HALF_LIFE_MS));
}

function subqShare(sq: SubqView, maxRounds: number, roundElapsedMs: number | null): number {
  switch (sq.status) {
    case "done":
    case "failed":
      return 1;
    case "pending":
      return 0;
    case "running": {
      const closed = sq.rounds.filter((r) => r.verdict !== null).length;
      const open = roundOpen(sq) ? roundApproach(roundElapsedMs) : 0;
      return Math.min(RUNNING_CAP, (closed + open) / Math.max(1, maxRounds));
    }
  }
}

// 탐색 비율 = 하위질문마다의 몫(끝남·실패 1, 대기 0, 도는 하위질문은 회차 몫)의 평균
export function exploreFraction(subqs: readonly SubqView[], maxRounds: number, roundElapsedMs: number | null): number {
  if (!subqs.length) return 0;
  const sum = subqs.reduce((acc, sq) => acc + subqShare(sq, maxRounds, roundElapsedMs), 0);
  return Math.min(1, sum / subqs.length);
}

// 탐색 중에는 작성 비율을 싣지 않고, 작성이 시작되면 탐색 구간은 다 찬 것으로 본다 — 막대가 뒤로 가지 않는다
export function overallFraction(stage: "collect" | "write", explore: number, synth: number): number {
  const e = stage === "write" ? 1 : clamp01(explore);
  const s = stage === "write" ? clamp01(synth) : 0;
  return Math.min(1, (EXPLORE_WEIGHT * e + SYNTH_WEIGHT * s) / (EXPLORE_WEIGHT + SYNTH_WEIGHT));
}

// 도는 하위질문의 회차 열쇠 — 회차가 늘거나 판정이 날 때만 바뀐다(화면이 이 열쇠가 바뀐 시각을 열린 회차의 시작으로 잰다).
// 회차가 아직 없을 때도 1회차로 센다: 첫 검색 이벤트가 와도 같은 열린 회차라 다가감이 0 으로 돌아가지 않는다
export function activeRoundKey(subqs: readonly SubqView[]): string | null {
  const sq = subqs.find((s) => s.status === "running");
  if (!sq) return null;
  const last = sq.rounds[sq.rounds.length - 1];
  return `${sq.idx}:${Math.max(1, sq.rounds.length)}:${last?.verdict ?? "open"}`;
}

// 끝나지 않은 잡에만 그린다. 단계 화면(stepMode — 끝난 잡의 이어간 연구)에는 WorkStepper 가 서므로 그리지 않는다
export function showsProgressBar(phase: ResearchPhase | null, stepMode: boolean): boolean {
  return phase !== null && !ENDED_PHASES.includes(phase) && !stepMode;
}

export function progressBarView(input: ProgressInput): ProgressBarView | null {
  const stage = progressStage(input.phase);
  if (stage === null || stage === "done") return null;
  const stages = progressStages(stage);
  if (stage === "plan") {
    const line = planLine(input.phase, input.queueNote);
    return { stages, line, percent: null, fraction: 0, running: false, valueText: line };
  }
  const collecting = stage === "collect";
  const line = collecting ? collectLine(input.subqs) : writeLine(input.eta, input.slots);
  const fraction = collecting
    ? overallFraction("collect", exploreFraction(input.subqs, input.maxRounds, input.roundElapsedMs), 0)
    : overallFraction("write", 1, barFraction(input.eta));
  const running = collecting ? input.subqs.some((s) => s.status === "running") : input.eta.runningIdx !== null;
  const percent = Math.floor(fraction * 100);
  return { stages, line, percent, fraction, running, valueText: `${line} · ${percent}%` };
}

function planLine(phase: ResearchPhase, queueNote: string | null): string {
  if (phase === "awaiting") return "계획 확인 대기 · 승인하면 근거 수집을 시작합니다";
  if (phase === "queued") return `대기열 · ${queueNote ?? "앞선 연구가 끝나면 시작합니다"}`;
  return "연구 계획을 세우는 중";
}

// 도는 하위질문, 없으면(하위질문 사이) 다음 대기 하위질문, 그것도 없으면(종합 단계 행 전) 마지막 하위질문
function collectLine(subqs: readonly SubqView[]): string {
  if (!subqs.length) return "근거 수집을 시작하는 중";
  const running = subqs.findIndex((s) => s.status === "running");
  const waiting = subqs.findIndex((s) => s.status === "pending");
  const at = running >= 0 ? running : waiting >= 0 ? waiting : subqs.length - 1;
  return `근거 수집 중 · 하위질문 ${at + 1}/${subqs.length} — 「${subqs[at]!.title}」`;
}

function writeLine(eta: SynthEta, slots: readonly DraftSlot[]): string {
  if (eta.total <= 0) return "보고서 작성을 준비하는 중";
  if (eta.done >= eta.total) return "보고서를 마무리하는 중";
  const i = (eta.runningIdx ?? eta.done) + 1;
  return `보고서 작성 중 · ${i}/${eta.total}절 — 「${slots[i - 1]?.heading ?? `절 ${i}`}」`;
}

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchProgress.test.ts`
Expected: `Test Files 1 passed (1)` / `Tests 18 passed (18)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchProgress.test.ts tests/unit/synthCard.test.ts`
Expected: `Test Files 2 passed (2)` / `Tests 42 passed (42)`(synthCard 24 는 `export` 한 단어만 바뀌어 그대로)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Task D2 뒤 수 + 파일 1·테스트 18(da80f23 기준선이면 `Test Files 41 passed (41)` / `Tests 750 passed (750)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"`
Expected: `0`(새 이름·`RUNNING_CAP` 이 다른 파일의 내보내기와 겹치지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchProgress.ts frontend/utils/synthCard.ts frontend/tests/unit/researchProgress.test.ts && git status --short && git commit -m "[Feat] round06d — 큰 진행 막대의 단계·글줄·퍼센트를 정하는 순수 함수(utils/researchProgress.ts)를 더한다(Q1·정함 1·2). 막대 하나가 근거 수집(탐색)과 보고서 작성(종합)을 실측 111:91 로 나눠 싣는다 — 작성이 시작돼도 막대가 뒤로 가지 않는다. 탐색 비율은 끝난 하위질문 + 도는 하위질문의 회차 몫(점검이 끝난 회차 ÷ (max_recheck + 1))이고, 검색만 끝난 회차는 화면이 그 회차를 본 뒤의 경과로 다가가되 상한 0.9 를 넘지 않는다. 큰 글줄은 '근거 수집 중 · 하위질문 k/n — 「…」'·'보고서 작성 중 · i/n절 — 「…」', 퍼센트는 내림 정수, 계획·승인 대기·대기열은 퍼센트 없이 단계 글줄만. 끝난 잡과 단계 화면(stepMode)에는 그리지 않는다(WorkStepper·06e 보고서 막대와 한 화면에 서지 않음). synthCard 의 RUNNING_CAP 을 내보내 두 막대가 같은 상한을 쓴다"
```

---

### Task D4: 큰 진행 막대 부품·고정 영역 연결·현황 카드 막대 옮기기

spec §12-3 '고정 진행 영역' 행(화면 위 sticky top 0, 그 아래 본문만 스크롤, completed·failed·canceled 가 아닐 때만, 작성 단계의 `rs-synth__bar` 를 이 영역으로 옮기고 카드에서는 지움, 절 목록·[초안 저장]은 카드에 남음, 상태 배지는 머리에 그대로, `useNow` 를 exploring 에도, 토큰 `--rs-bar-thick`·`--rs-bar-h`) · '머리 겹침 없음'(WorkStepper 를 고치지 않음) · Q1(두께 1rem·768px 이하 0.75rem, 큰 글줄 1rem 굵게, 퍼센트 1.25rem 굵게, 작은 단계 표시) · 정함 3(높이를 토큰으로 고정). Task D3 의 `progressBarView` 를 그리는 부품을 만들고 연구 화면 머리 바로 아래에 붙인다.

**알아 둘 것:**
- **부품은 그리기만 한다.** `ResearchProgressBar.vue` 는 `view: ProgressBarView` 하나만 받는다(공통 계약 '새 파일과 공개 이름' 표, emit 없음). 단계 칩은 `<ol>` 에 지금 단계만 `aria-current="step"`, 막대는 `role="progressbar"` + `aria-valuenow`(퍼센트가 없으면 속성 없음)·`aria-valuetext`(`valueText`). **`aria-live` 는 두지 않는다** — 1초마다 바뀌는 퍼센트를 읽어 대지 않게. 절이 끝날 때의 알림은 현황 카드(`SynthProgressCard.vue:49`)·장부가 이미 한다.
- **높이는 토큰으로 고정한다(정함 3).** `.rs-pbar { height: var(--rs-bar-h) }`, 큰 글줄은 한 줄 말줄임(`title` 속성에 전체 글). `--rs-bar-h` 는 `.rs-page` 에 `0px`, 막대가 서 있을 때(`<main class="rs-page has-progressbar">`) `5.6rem`(768px 이하 `5.2rem`) — 내용(단계 칩 ≈1.1rem + 글줄 ≈1.5rem + 막대 1rem/0.75rem + 간격 0.7rem)을 세로 가운데에 두고 위아래 ≈0.65rem 이 남는 값이다. 막대를 그리는 조건(`barView !== null`)과 클래스를 다는 조건이 같은 계산이라 둘이 어긋나지 않는다. 오프셋(옆 칸 top·`scroll-margin-top`·위치 복원)은 Task D5 가 이 토큰으로 맞춘다.
- **D4 품질 검토 반영(이 Task 뒤에 들어왔다 — 아래 Step 의 CSS 는 처음 글 그대로 둔다):** 새 sticky 막대가 화면 위 112px(768px 이하 ≈75px) 띠를 덮는데 문서에 `scroll-padding-top` 이 없어, 브라우저가 초점을 받은 요소가 보이는지 따질 때 막대를 몰라 Shift+Tab 으로 위로 올라갈 때 초안의 인용 칩·버튼, 승인 대기 PlanCard 편집 칸, 현황 카드 항목이 막대 뒤에 가린 채 초점을 받았다(WCAG 2.2 2.4.11 — 이 Task 가 새로 만든 회귀). 그래서 높이 값을 `:root` 의 `--rs-bar-area-h`(`5.6rem`·768px 이하 `5.2rem` — 값은 여기 한 곳)로 올리고 `.rs-page.has-progressbar { --rs-bar-h: var(--rs-bar-area-h) }`, `html:has(.rs-page.has-progressbar) { scroll-padding-top: var(--rs-bar-area-h) }` 를 더했다(html 은 `.rs-page` 의 값을 읽지 못한다 — 인쇄 CSS 의 `body:has(.rs-page)` 가 선례. `:has` 를 모르는 브라우저에서도 막대 자체의 높이는 `.rs-page` 쪽이라 그대로 선다). `scroll-padding` 은 `scrollIntoView` 에도 걸리므로 절 이동(`jumpToSection`)·따라가기(D7)는 이미 막대 아래로 내려가고, **`.rs-section` 의 `scroll-margin-top` 은 `1.2rem` 그대로 둔다**(D5 Step 6 ② 를 걷었다 — 다시 더하면 두 번 내려간다). `researchProgress.test.ts` 에 research.css 를 읽는 `it` 둘(+2 — 화면 폭 조건마다 문서 여백 = 막대 높이, `scroll-margin-top` 에 `--rs-bar` 없음)을 더했다.
- **치수는 Q1 값 그대로** — 막대 두께 `--rs-bar-thick: 1rem`(1rem = 20px, 지금 카드 막대 0.4rem 의 2.5배)·768px 이하 `0.75rem`, 글줄 1rem 굵게, 퍼센트 1.25rem 굵게. 06e 자동 보고서의 큰 막대(`.wk-rbar`·`--wk-bar-thick`, 06e 계획 정함 28)와 **값으로만** 맞춘다 — 이 Task 는 그 이름을 정의하지 않는다(Step 5 확인).
- **채움은 현황 카드 막대를 크게 옮긴 것이다.** 옛 `.rs-synth__fill`(`transition: width 1s linear`, `is-running::after` 의 `rs-sheen` 빛 흐름 — research.css da80f23 :785-804)을 `.rs-pbar__fill` 로 옮기고 옛 규칙·옛 reduced-motion 줄(:921·:925)은 지운다. `@keyframes rs-sheen`(:899)은 새 채움이 쓰므로 그대로 둔다. 새 움직임은 `prefers-reduced-motion` 에서 멈춘다.
- **현황 카드는 막대만 걷는다** — 머리 요약(`synthSummary` — '2/6 절 완료 · 약 1분 남음')·절 목록·[초안 저장](actions 슬롯)·절 완료 알림은 그대로다. `barFraction` 은 이제 `utils/researchProgress.ts` 가 부르므로 카드의 import 와 `percent` 만 지운다.
- **`useNow` 를 탐색 중에도 켠다**(spec — `[id].vue:271`). 탐색 중 열린 회차의 다가감이 1초마다 막대를 민다. 열린 회차의 경과는 `activeRoundKey`(Task D3)가 바뀐 시각(`roundSeenAt`)부터 잰다 — 시계(`now`)는 1초마다만 바뀌므로 `now − roundSeenAt` 이 잠깐 음수일 수 있어 0 에서 자른다. 연구 화면은 내용(`view`)을 마운트 뒤에 받으므로(서버 렌더는 '불러오는 중' 카드) 서버 렌더 시각과 어긋날 일이 없다.
- **자리:** `roundKey`·`roundSeenAt`·`roundElapsedMs`·`barView` 는 한 자리 — 앵커 `const stepMode = computed(…)`(da80f23 :294) 바로 아래(Task D3 의 `activeRoundKey`·`progressBarView` 를 부르는 한 자리 — 계획 머리 '같은 파일 사슬'). 그 위에 정의된 `now`(:271)·`slots`(:272)·`eta`(:273)·`queueText`(:259)를 읽는다. 막대는 `ResearchHeader` 바로 뒤·WorkStepper 주석 앞 — 끝난 잡에만 서는 WorkStepper 와 끝나지 않은 잡에만 서는 막대는 같은 자리에 함께 서지 않는다.
- `[id].vue` 는 D1(:320-336)·D2(:80-96·:232-234) 뒤다 — 아래 Edit 의 old 는 모두 앵커 글자로 잡는다. `research.css` 는 D2 가 :83 뒤에 `.rs-card__text` 를 넣은 뒤다(`.rs-page` :7-15 는 그보다 위라 그대로).
- 테스트는 없다(+0) — 판단은 Task D3 가 본다. 부품·연결·CSS 는 typecheck `0` 과 build 로 확인하고, 막대가 실제로 차오르는지는 마무리 운영 확인에서 본다.

**Files:**
- Create: `frontend/components/research/ResearchProgressBar.vue`
- Modify: `frontend/components/research/SynthProgressCard.vue`(:14-24 막대, :56-63 import, :75 `percent`)
- Modify: `frontend/pages/research/[id].vue`(D1·D2 뒤 — `<main class="rs-page">`, WorkStepper 주석 앞, import 두 곳, `useNow`, `const stepMode = computed(` 아래)
- Modify: `frontend/assets/css/research.css`(D2 뒤 — `.rs-page` :7-15, `.rs-synth__bar` ~ `.rs-synth__fill.is-running::after`(da80f23 :778-804), 현황 카드 reduced-motion(da80f23 :920-930), 인쇄 앵커 위 새 블록, 인쇄 숨김 목록)

기준선: Task D3 뒤 수(da80f23 이면 `41 files / 750`).

- [ ] **Step 1: 큰 진행 막대 부품을 만든다**

`frontend/components/research/ResearchProgressBar.vue` (새 파일):

```vue
<!-- frontend/components/research/ResearchProgressBar.vue -->
<template>
  <!-- 연구 화면 위에 고정되는 큰 진행 막대(spec §12-3 고정 진행 영역·Q1). 보기는 utils/researchProgress.ts 의
       progressBarView 가 만들고 여기서는 그리기만 한다. aria-live 는 두지 않는다 — 1초마다 바뀌는 퍼센트를 읽어 대지 않게
       (절이 끝날 때의 알림은 현황 카드·근거 장부가 한다) -->
  <div class="rs-pbar" role="group" aria-label="연구 진행">
    <ol class="rs-pbar__stages">
      <li
        v-for="s in view.stages"
        :key="s.key"
        class="rs-pbar__stage"
        :class="`is-${s.state}`"
        :aria-current="s.state === 'current' ? 'step' : undefined"
      >
        {{ s.label }}
      </li>
    </ol>
    <div class="rs-pbar__line">
      <p class="rs-pbar__text" :title="view.line">{{ view.line }}</p>
      <p v-if="view.percent !== null" class="rs-pbar__pct">{{ view.percent }}%</p>
    </div>
    <div
      class="rs-pbar__track"
      role="progressbar"
      aria-label="연구 진행"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="view.percent ?? undefined"
      :aria-valuetext="view.valueText"
    >
      <span class="rs-pbar__fill" :class="{ 'is-running': view.running }" :style="{ width: `${width}%` }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ProgressBarView } from "~/utils/researchProgress";

const props = defineProps<{ view: ProgressBarView }>();

// 채움 폭은 0.1% 단위 — 1초마다 다시 재는 폭을 같은 1초 transition 으로 이어 붙인다(research.css .rs-pbar__fill)
const width = computed(() => Math.round(props.view.fraction * 1000) / 10);
</script>
```

- [ ] **Step 2: 현황 카드에서 작은 막대를 걷는다**

`frontend/components/research/SynthProgressCard.vue` — 막대(:13-26). old:

```vue
    </header>

    <div
      class="rs-synth__bar"
      role="progressbar"
      aria-label="보고서 작성 진행"
      aria-valuemin="0"
      :aria-valuemax="eta.total || 1"
      :aria-valuenow="Math.min(eta.done, eta.total)"
      :aria-valuetext="summary"
    >
      <span class="rs-synth__fill" :class="{ 'is-running': eta.runningIdx !== null }" :style="{ width: `${percent}%` }" />
    </div>

    <ol v-if="slots.length" class="rs-synth__list">
```

new:

```vue
    </header>

    <!-- 진행 막대는 연구 화면 위 고정 진행 영역(ResearchProgressBar)으로 옮겼다. 이 카드는 요약·절 목록·초안 저장만 -->
    <ol v-if="slots.length" class="rs-synth__list">
```

import(:56-63). old:

```ts
import {
  barFraction,
  finishedAnnouncement,
  newlyFinished,
  slotStateLabel,
  synthSummary,
  type SlotHoverEvent,
} from "~/utils/synthCard";
```

new:

```ts
import { finishedAnnouncement, newlyFinished, slotStateLabel, synthSummary, type SlotHoverEvent } from "~/utils/synthCard";
```

`percent`(:74-76). old:

```ts
const summary = computed(() => synthSummary(props.eta));
const percent = computed(() => Math.round(barFraction(props.eta) * 1000) / 10);
const canJump = computed(() => props.slots.some((s) => s.sectionIndex !== null));
```

new:

```ts
const summary = computed(() => synthSummary(props.eta));
const canJump = computed(() => props.slots.some((s) => s.sectionIndex !== null));
```

- [ ] **Step 3: 연구 화면에 고정 진행 영역을 붙인다**

`frontend/pages/research/[id].vue` ① 막대가 서 있음을 페이지에 단다(오프셋 토큰이 읽는다). old:

```html
    <main class="rs-page">
```

new:

```html
    <main class="rs-page" :class="{ 'has-progressbar': !!barView }">
```

② 머리 바로 뒤·WorkStepper 앞. old:

```html
        <!-- 이어간 연구에만 단다 — 이어가지 않은 딥리서치의 머리는 지금과 같다 -->
```

new:

```html
        <!-- 고정 진행 영역 — 끝나지 않은 잡에만 선다. 끝난 잡의 이어간 연구에 서는 아래 WorkStepper 와 함께 서지 않는다 -->
        <ResearchProgressBar v-if="barView" :view="barView" />
        <!-- 이어간 연구에만 단다 — 이어가지 않은 딥리서치의 머리는 지금과 같다 -->
```

③ import 두 곳. old:

```ts
import ResearchHeader from "~/components/research/ResearchHeader.vue";
```

new:

```ts
import ResearchHeader from "~/components/research/ResearchHeader.vue";
import ResearchProgressBar from "~/components/research/ResearchProgressBar.vue";
```

old:

```ts
import { SHOW_LAYOUT_TOGGLE, WIDE_MIN_PX, effectiveLayout, type ResearchLayout } from "~/utils/researchLayout";
```

new:

```ts
import { SHOW_LAYOUT_TOGGLE, WIDE_MIN_PX, effectiveLayout, type ResearchLayout } from "~/utils/researchLayout";
import { activeRoundKey, maxRoundsOf, progressBarView, showsProgressBar } from "~/utils/researchProgress";
```

④ 시계를 탐색 중에도 켠다(da80f23 :270-271). old:

```ts
// 절이 쌓이는 동안만 1초마다 시계를 읽는다 — 쓰는 중인 절의 경과·남은 시간·막대가 따라 움직인다
const now = useNow(computed(() => phase.value === "synthesizing"));
```

new:

```ts
// 근거를 모으는 동안·절이 쌓이는 동안만 1초마다 시계를 읽는다 — 쓰는 중인 절의 경과·남은 시간과 큰 진행 막대(탐색 중에는
// 열린 회차의 다가감)가 따라 움직인다
const now = useNow(computed(() => phase.value === "synthesizing" || phase.value === "exploring"));
```

⑤ 막대 보기 — 앵커 `const stepMode = computed(…)`(da80f23 :294) 바로 아래. old:

```ts
const stepMode = computed(() => step.value !== null && phase.value === "completed" && work.exists.value !== false);
```

new:

```ts
const stepMode = computed(() => step.value !== null && phase.value === "completed" && work.exists.value !== false);

// ── 큰 진행 막대(고정 진행 영역) ──────────────────────────
// 열린 회차(검색·자기점검을 기다리는 회차)는 화면이 그 회차를 처음 본 때부터 잰 경과로 다가간다 — 서버는 회차 시각을 주지
// 않는다. 회차가 늘거나 판정이 나면 열쇠가 바뀌어 0 부터 다시 센다(그때 점검이 끝난 회차 한 칸이 늘어 막대는 뒤로 가지 않는다)
const roundKey = computed(() => (view.value ? activeRoundKey(view.value.subqs) : null));
const roundSeenAt = ref<number | null>(null);
watch(
  roundKey,
  (k) => {
    roundSeenAt.value = k ? Date.now() : null;
  },
  { immediate: true },
);
// 시계는 1초마다만 바뀐다 — 열쇠가 바뀐 직후에는 시계가 그 시각보다 앞일 수 있어 0 에서 자른다
const roundElapsedMs = computed(() => (roundSeenAt.value === null ? null : Math.max(0, now.value - roundSeenAt.value)));
// 끝나지 않은 잡에만 선다 — 끝나면 머리 상태 배지만 남고, 끝난 잡의 단계 화면(stepMode)에는 WorkStepper 가 선다(한 화면에
// 큰 막대와 단계 막대가 함께 서지 않는다). 이어간 연구의 보고서 단계(?s=proposal)의 큰 막대는 06e 몫이다
const barView = computed(() =>
  view.value && phase.value && showsProgressBar(phase.value, stepMode.value)
    ? progressBarView({
        phase: phase.value,
        subqs: view.value.subqs,
        maxRounds: maxRoundsOf(view.value.params),
        roundElapsedMs: roundElapsedMs.value,
        eta: eta.value,
        slots: slots.value,
        queueNote: queueText.value,
      })
    : null,
);
```

(`ref`·`watch`·`computed` 는 `:208` 의 vue import 에 이미 있다.)

- [ ] **Step 4: 막대 스타일을 옮기고 토큰을 둔다**

`frontend/assets/css/research.css` ① 토큰(da80f23 :6-15 — D2 보다 위라 그대로). old:

```css
/* ── 페이지 골격 ─────────────────────────────────────────── */
.rs-page {
  --rs-side-width: 17rem;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 1.2rem;
  min-width: 0;
  color: var(--skx-ink);
}
```

new:

```css
/* ── 페이지 골격 ─────────────────────────────────────────── */
/* --rs-bar-thick: 큰 진행 막대의 두께(Q1). --rs-bar-h: 화면 위에 고정한 진행 영역 전체 높이 — 막대가 없으면 0px.
   옆 칸 top·절 scroll-margin-top·돌아온 자리 맞추기가 이 값을 읽는다(정함 3 — 높이를 재지 않고 토큰으로 고정한다) */
.rs-page {
  --rs-side-width: 17rem;
  --rs-bar-thick: 1rem;
  --rs-bar-h: 0px;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 1.2rem;
  min-width: 0;
  color: var(--skx-ink);
}
.rs-page.has-progressbar {
  --rs-bar-h: 5.6rem;
}
@media (max-width: 768px) {
  .rs-page {
    --rs-bar-thick: 0.75rem;
  }
  .rs-page.has-progressbar {
    --rs-bar-h: 5.2rem;
  }
}
```

② 현황 카드의 작은 막대 규칙을 지운다(da80f23 :778-804). old:

```css
.rs-synth__bar {
  position: relative;
  height: 0.4rem;
  overflow: hidden;
  background: var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}
.rs-synth__fill {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 0;
  overflow: hidden;
  background: var(--skx-primary);
  border-radius: inherit;
  /* 폭은 1초마다 다시 잰다 — 같은 1초로 이어 붙여 멈춤 없이 늘어나 보이게 한다 */
  transition: width 1s linear;
}
.rs-synth__fill.is-running::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--skx-white) 45%, transparent), transparent);
  transform: translateX(-100%);
  animation: rs-sheen 1.8s ease-in-out infinite;
}
.rs-synth__list {
```

new:

```css
.rs-synth__list {
```

③ 현황 카드 reduced-motion 에서 옛 채움 두 줄을 뺀다(da80f23 :920-930). old:

```css
@media (prefers-reduced-motion: reduce) {
  .rs-synth__fill,
  .rs-synth__item {
    transition: none;
  }
  .rs-synth__fill.is-running::after,
  .rs-synth__item.is-running .rs-synth__icon,
  .rs-synth__icon.is-fresh {
    animation: none;
  }
}
```

new:

```css
@media (prefers-reduced-motion: reduce) {
  .rs-synth__item {
    transition: none;
  }
  .rs-synth__item.is-running .rs-synth__icon,
  .rs-synth__icon.is-fresh {
    animation: none;
  }
}
```

④ 큰 진행 막대 — 인쇄 앵커 바로 위. old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 큰 진행 막대(고정 진행 영역) ────────────────────────── */
/* 끝나지 않은 잡의 연구 화면 위에 붙는다(sticky top 0) — 그 아래 본문만 스크롤한다. 높이는 토큰(--rs-bar-h)으로 고정하고 글줄은
   한 줄로 말줄임한다 — 높이가 흔들리면 옆 칸·절 이동·돌아온 자리의 오프셋이 따라 흔들린다. 치수(두께 --rs-bar-thick·글줄 1rem·
   퍼센트 1.25rem)는 06e 자동 보고서의 큰 막대와 값으로 맞춘다. 인용 팝오버(z-index 30)·메뉴(40)는 이 막대 위로 뜬다 */
.rs-pbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.35rem;
  height: var(--rs-bar-h);
  padding: 0 1.2rem;
  overflow: hidden;
  background: var(--skx-white);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-lnb);
}
.rs-pbar__stages {
  display: flex;
  gap: 0.3rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.rs-pbar__stage {
  padding: 0.1rem 0.45rem;
  font-size: 0.55rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-gray-2);
  white-space: nowrap;
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-pill);
}
.rs-pbar__stage.is-done {
  color: var(--skx-ink-2);
  border-color: var(--skx-border-c1);
}
.rs-pbar__stage.is-current {
  color: var(--skx-white);
  background: var(--skx-primary);
  border-color: var(--skx-primary);
}
.rs-pbar__line {
  display: flex;
  align-items: baseline;
  gap: 0.8rem;
  min-width: 0;
}
.rs-pbar__text {
  flex: 1;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rs-pbar__pct {
  flex-shrink: 0;
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  color: var(--skx-primary);
}
.rs-pbar__track {
  position: relative;
  flex-shrink: 0;
  height: var(--rs-bar-thick);
  overflow: hidden;
  background: var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}
/* 채움은 보고서 작성 현황 카드에 있던 작은 막대의 채움을 크게 옮긴 것 — 폭은 1초마다 다시 재므로 같은 1초로 이어 붙여
   멈춤 없이 늘어나 보이게 한다 */
.rs-pbar__fill {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 0;
  overflow: hidden;
  background: var(--skx-primary);
  border-radius: inherit;
  transition: width 1s linear;
}
.rs-pbar__fill.is-running::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--skx-white) 45%, transparent), transparent);
  transform: translateX(-100%);
  animation: rs-sheen 1.8s ease-in-out infinite;
}
@media (max-width: 768px) {
  .rs-pbar {
    padding: 0 0.8rem;
  }
}
@media (prefers-reduced-motion: reduce) {
  .rs-pbar__fill {
    transition: none;
  }
  .rs-pbar__fill.is-running::after {
    animation: none;
  }
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

⑤ 화면 그대로 인쇄(Ctrl+P)에서도 막대를 뺀다 — 인쇄 숨김 목록(da80f23 :1277-1282). old:

```css
  .rs-page .rs-col-side,
```

new:

```css
  .rs-page .rs-col-side,
  .rs-page .rs-pbar,
```

- [ ] **Step 5: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Task D3 뒤와 같은 수(+0 — da80f23 이면 `Test Files 41 passed (41)` / `Tests 750 passed (750)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -rn "rs-synth__bar\|rs-synth__fill" components assets pages utils`
Expected: (빈 출력 — 작은 막대의 마크업·규칙이 모두 걷혔다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "rs-sheen" assets/css/research.css`
Expected: `2`(keyframes 한 곳 + `.rs-pbar__fill.is-running::after` 한 곳 — 옛 채움의 쓰임이 새 채움으로 옮겨 갔다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -n "wk-rbar\|--wk-bar-thick" assets/css/research.css components/research/ResearchProgressBar.vue`
Expected: (빈 출력 — 06e 자동 보고서 막대의 이름은 06d 가 정의하지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -nE "#[0-9a-fA-F]{3,6}\b|rgba?\(" assets/css/research.css`
Expected: (빈 출력 — `--skx-*` 토큰만 쓴다)

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/components/research/ResearchProgressBar.vue frontend/components/research/SynthProgressCard.vue "frontend/pages/research/[id].vue" frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 연구 화면 위에 큰 진행 막대를 고정한다(Q1 — 작은 단계 표시·막대 위 큰 글줄·오른쪽 퍼센트, 탐색 중에도 같은 막대). 새 ResearchProgressBar 가 progressBarView 를 그리고, 머리 아래에 sticky top 0 으로 붙어 그 아래 본문만 스크롤한다. 끝나지 않은 잡에만 서고(끝나면 머리 상태 배지만), 단계 화면·인쇄에서는 그리지 않는다. 막대 두께 --rs-bar-thick 1rem(768px 이하 0.75rem), 영역 높이 --rs-bar-h 를 토큰으로 고정해 오프셋이 같은 값을 읽게 한다. 보고서 작성 현황 카드의 작은 막대(rs-synth__bar)는 이 영역으로 옮기고 카드에서 지운다 — 요약·절 목록·[초안 저장]은 카드에 남는다. 탐색 중에도 1초 시계(useNow)를 켜 열린 회차의 다가감이 막대를 민다"
```

---

### Task D5: 오프셋 — 옆 칸·절 스크롤 여백·위치 복원

spec §12-3 '오프셋' 행(고정 진행 영역의 높이만큼 A 의 옆 칸 `top`, `.rs-section` 의 `scroll-margin-top`, 위치 복원 `useRestorePosition.ts:151,172` 를 내린다) · 정함 3. 막대가 화면 위에 붙은 뒤 옆 칸·옮겨 간 절 제목·상세에서 돌아온 자리가 막대 밑에 숨지 않게 한다. **옮겨 간 절 제목(`.rs-section` 의 `scroll-margin-top`)의 몫은 D4 품질 검토 반영의 문서 `scroll-padding-top` 이 이미 맡았다** — 이 Task 는 옆 칸과 위치 복원만 한다(아래 '알아 둘 것' 둘째 줄).

**알아 둘 것:**
- **두 곳 모두 막대 높이 하나를 읽는다**(Task D4 — `--rs-bar-h` 는 막대가 없으면 `0px`, 있으면 `var(--rs-bar-area-h)` = `5.6rem`/`5.2rem`). CSS(옆 칸 `top`·`max-height`)는 `--rs-bar-h` 를 바로 쓰고, 위치 복원은 JS 라 막대 요소의 높이를 읽는다.
- **D4 품질 검토 반영(이 Task 앞에 들어왔다) — `.rs-section` 의 `scroll-margin-top` 은 고치지 않는다.** D4 반영이 `html:has(.rs-page.has-progressbar) { scroll-padding-top: var(--rs-bar-area-h) }` 를 더했다(키보드 초점 이동이 막대 뒤에 가린 요소로 가던 회귀 — WCAG 2.2 2.4.11). `scroll-padding` 은 `scrollIntoView` 에도 걸리므로 현황 카드에서 절을 눌러 옮기는 `jumpToSection`(`scrollIntoView({ block: "start" })`)·Task D7 의 따라가기·탐색 중 절 자리(Task L2 — `rs-section rs-slot`)는 이미 막대 아래 + `scroll-margin-top: 1.2rem` 자리로 간다. 처음 계획의 Step 6 ②(`scroll-margin-top: calc(var(--rs-bar-h, 0px) + 1.2rem)`)는 막대 높이를 두 번 더해 절 이동 오프셋이 두 배가 되므로 걷었다 — `researchProgress.test.ts` 의 research.css 여백 `it`('scroll-margin-top 에 다시 더하지 않는다')이 그 줄을 넣으면 실패한다. 반대로 `scrollBy`·`scrollTo` 에는 `scroll-padding` 이 걸리지 않으므로 위치 복원(창·칸을 `scrollBy` 로 굴린다)은 아래 `insetTargetTop` 이 그대로 필요하다. 옆 칸은 안쪽 스크롤 칸이라 문서 여백과 겹치지 않는다(칸 안의 초점 이동은 칸을 굴리고, 칸 자체는 Step 6 뒤 막대 아래에 붙는다).
- **위치 복원은 `insetTargetTop` 으로 내린다**(이 Task 의 Step 3 — 공통 계약 '고치는 파일의 새·바뀐 공개 이름' 표). `targetTop(y, 화면 높이)`(:45-48 — 떠날 때의 높이, 모르면 화면 1/3) 과 막대 높이 중 더 아래. 맞춘 높이(`top`)는 `:150` 에서 한 번 정하고 `:151`(맞추기)·`:172`(붙잡기 `hold`)가 그대로 쓰므로 `:150` 한 줄만 바꾼다. 막대가 없는 화면(`pages/papers/index.vue:626` — `topInset` 을 넘기지 않음, 끝난 연구)은 inset 0 이라 지금과 같다.
- **inset 은 막대의 '높이'다(위치 bottom 이 아니다 — 파트 D 끝 '파트 메모' 2).** 돌아온 화면은 맞추기 전에 맨 위로 올라가 있다(`useRestorePosition.ts:200`) — 그때 막대는 머리 아래 제자리라 `getBoundingClientRect().bottom` 은 머리 높이까지 더한 값이다. 맞춘 뒤(요소로 굴린 뒤)에는 막대가 화면 맨 위(top 0)에 붙어 가리는 것은 막대 높이만큼이다. `topInset` 은 맞추는 순간에 부르는 함수라 그때의 막대 유무를 본다(완료된 연구로 돌아오면 막대가 없어 0).
- `progressInset` 은 함수 선언이라 `const restore = …` 바로 위에 두어도 되고 호이스팅된다. `useRestorePosition` 의 import 에서 `targetTop` 은 더 쓰지 않으므로 뺀다(`insetTargetTop` 이 안에서 부른다).
- `restorePosition.test.ts` 는 기존 18 + 3. 기존 describe(`scrollDelta·targetTop` :28-40) 바로 뒤에 둔다.
- **D1 품질 검토 반영(이 Task 앞에 들어왔다):** D1 로 탐색 중·탐색 도중 실패·취소처럼 보고서·초안이 없는 잡도 A 로 그려져, 제외 논문 앵커(`x-…` — 이 단계들에서는 진행 패널 회차 타임라인에만 있다)가 sticky·`overflow-y: auto` 옆 칸 안에 들어간다. 그 상태에서 상세에서 돌아오면 `window.scrollBy` 만으로는 칸 안쪽에 잘린 앵커가 보이지 않고, `hold` 가 15초 동안 매 프레임 창을 바닥까지 끌었다. 그래서 `utils/restorePosition.ts` 에 `scrollHolder`(조상 모양 → 창·안쪽 스크롤 칸·고정 칸)·`boxScrollDelta`(칸이 보이는 범위 안에서 목표 높이에 가장 가깝게)를 더하고, `useRestorePosition` 이 맞출 때 칸 → 창 한 번 → 칸 순서로 맞추며, 붙잡을 때는 칸을 굴리고 고정 칸 안이면 창을 굴리지 않게 했다(+6 테스트). **이 Task 의 앵커는 모두 그대로 한 번씩 맞는다**(import 두 곳·머리 주석·opts·`const top = targetTop(…)` 한 줄·`targetTop` 블록·테스트 import·`scrollDelta·targetTop` describe 끝). 그래서 `restorePosition.test.ts` 는 이 Task 앞 **24** → 뒤 **27** 이다(Step 2·4 의 수). `top` 은 `alignInBox`·`hold` 도 그대로 쓰므로 Step 5 의 `const top = insetTargetTop(…)` 한 줄이 칸 맞추기에도 막대 높이를 넣는다. 옆 칸은 Step 6 뒤 막대 아래(`--rs-bar-h` + 1.2rem)부터 시작해 칸이 보이는 범위가 막대 밑으로 들어가지 않는다.

**Files:**
- Modify: `frontend/utils/restorePosition.ts`(:44-48 `targetTop` 바로 아래)
- Modify: `frontend/composables/useRestorePosition.ts`(:12-29 import, :45-54 머리 주석·opts, :150)
- Modify: `frontend/pages/research/[id].vue`(앵커 `const restore = useRestorePosition(restoreReady);` — da80f23 :314)
- Modify: `frontend/assets/css/research.css`(`.rs-body--A .rs-col-side` da80f23 :33-38 — `.rs-section` 의 `scroll-margin-top` 은 D4 품질 검토 반영 뒤 고치지 않는다)
- Test: `frontend/tests/unit/restorePosition.test.ts`(import :4-22, `describe("scrollDelta·targetTop"` 뒤 — 18 → 21, D1 품질 검토 반영 뒤라 24 → 27)

기준선: Task D4 뒤 수(da80f23 이면 `41 files / 750`).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/restorePosition.test.ts` ① import. old:

```ts
  holdsReturnSpot,
  isPlainClick,
```

new:

```ts
  holdsReturnSpot,
  insetTargetTop,
  isPlainClick,
```

② `describe("scrollDelta·targetTop", …)` 바로 뒤(da80f23 :40 의 `});` 다음). old:

```ts
    expect(targetTop(null, 900)).toBe(300);
  });
});

describe("restoreStep", () => {
```

new:

```ts
    expect(targetTop(null, 900)).toBe(300);
  });
});

describe("insetTargetTop", () => {
  it("고정 막대가 가리는 높이면 막대 바로 아래로 내린다", () => {
    expect(insetTargetTop(40, 800, 112)).toBe(112);
    expect(insetTargetTop(40, 800, 111.2)).toBe(112);
    expect(insetTargetTop(240, 800, 112)).toBe(240);
  });

  it("막대가 없으면(0) targetTop 과 같다", () => {
    expect(insetTargetTop(240, 800, 0)).toBe(targetTop(240, 800));
    expect(insetTargetTop(900, 600, 0)).toBe(targetTop(900, 600));
    expect(insetTargetTop(240, 800, -5)).toBe(240);
  });

  it("떠날 때 높이를 모르면 화면 1/3 과 막대 아래 중 더 아래", () => {
    expect(insetTargetTop(null, 900, 112)).toBe(300);
    expect(insetTargetTop(null, 300, 112)).toBe(112);
  });
});

describe("restoreStep", () => {
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/restorePosition.test.ts`
Expected: `Test Files 1 failed (1)` / `Tests 3 failed | 24 passed (27)`(D1 품질 검토 반영의 +6 — 그 전 계획 값은 `18 passed (21)`) — `insetTargetTop` 의 세 `it` 이 모두 `TypeError: (0 , insetTargetTop) is not a function`

- [ ] **Step 3: `insetTargetTop` 을 만든다**

`frontend/utils/restorePosition.ts` — `targetTop`(:44-48) 바로 아래. old:

```ts
// 떠날 때 높이를 모르면(새 창 링크를 높이 없이 연 경우) 화면 위쪽 1/3 에 둔다
export function targetTop(y: number | null, viewportHeight: number): number {
  if (y === null) return Math.round(viewportHeight / 3);
  return Math.min(y, Math.max(0, viewportHeight - KEEP_VISIBLE_PX));
}
```

new:

```ts
// 떠날 때 높이를 모르면(새 창 링크를 높이 없이 연 경우) 화면 위쪽 1/3 에 둔다
export function targetTop(y: number | null, viewportHeight: number): number {
  if (y === null) return Math.round(viewportHeight / 3);
  return Math.min(y, Math.max(0, viewportHeight - KEEP_VISIBLE_PX));
}

// 고정 진행 막대가 화면 위를 가리면 그 아래로 내린다 — inset 은 막대가 화면 위에 붙었을 때 가리는 높이(막대가 없으면 0)
export function insetTargetTop(y: number | null, viewportHeight: number, inset: number): number {
  return Math.max(targetTop(y, viewportHeight), Math.ceil(Math.max(0, inset)));
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/restorePosition.test.ts`
Expected: `Test Files 1 passed (1)` / `Tests 27 passed (27)`(D1 품질 검토 반영 뒤 — 그 전 계획 값은 `21 passed (21)`)

- [ ] **Step 5: 위치 복원이 막대 높이만큼 내려 맞추게 한다**

`frontend/composables/useRestorePosition.ts` ① import(:12-29). old:

```ts
  stateWithSpot,
  stateWithoutSpot,
  targetTop,
  withSpot,
  withoutSpot,
} from "~/utils/restorePosition";
```

new:

```ts
  stateWithSpot,
  stateWithoutSpot,
  withSpot,
  withoutSpot,
} from "~/utils/restorePosition";
```

같은 import 의 앞쪽. old:

```ts
  holdDelta,
  isUserMove,
```

new:

```ts
  holdDelta,
  insetTargetTop,
  isUserMove,
```

② 머리 주석·opts(:45-54). old:

```ts
 * 쓰는 화면은 definePageMeta({ scrollToTop: (to) => !holdsReturnSpot(to.query, history.state) }) 로 Nuxt 의 스크롤을 끈다
 */
export function useRestorePosition(
  ready: Ref<boolean> | ComputedRef<boolean>,
  opts: { maxWaitMs?: number } = {},
): { pending: Readonly<Ref<boolean>>; anchor: Anchor | null } {
```

new:

```ts
 * 쓰는 화면은 definePageMeta({ scrollToTop: (to) => !holdsReturnSpot(to.query, history.state) }) 로 Nuxt 의 스크롤을 끈다.
 * topInset 은 화면 위에 고정된 영역(연구 화면의 큰 진행 막대)이 가리는 높이 — 맞추는 순간에 불러 그 아래로 맞춘다(없으면 0)
 */
export function useRestorePosition(
  ready: Ref<boolean> | ComputedRef<boolean>,
  opts: { maxWaitMs?: number; topInset?: () => number } = {},
): { pending: Readonly<Ref<boolean>>; anchor: Anchor | null } {
```

③ 맞출 높이(:150 — `:151` 맞추기와 `:172` 붙잡기는 이 `top` 을 그대로 쓴다). old:

```ts
        const top = targetTop(spot.y, window.innerHeight);
```

new:

```ts
        const top = insetTargetTop(spot.y, window.innerHeight, opts.topInset?.() ?? 0);
```

`frontend/pages/research/[id].vue` — 앵커 `const restore = useRestorePosition(restoreReady);`(da80f23 :314). old:

```ts
const restore = useRestorePosition(restoreReady);
```

new:

```ts
// 고정 진행 막대가 화면 위에 붙어 가리는 높이 — 돌아온 자리를 그 아래로 맞춘다. 맞추는 순간에는 화면이 맨 위라 막대가 머리
// 아래 제자리에 있으므로 위치(bottom)가 아니라 높이를 쓴다(맞춘 뒤에는 막대가 화면 맨 위에 붙는다). 막대가 없으면 0
function progressInset(): number {
  return document.querySelector<HTMLElement>(".rs-page .rs-pbar")?.getBoundingClientRect().height ?? 0;
}
const restore = useRestorePosition(restoreReady, { topInset: progressInset });
```

- [ ] **Step 6: 옆 칸을 막대 아래로 내린다**

`frontend/assets/css/research.css` ① A 의 옆 칸(da80f23 :33-38 — 앞 Task 들이 이 위에 줄을 더하지 않았다. D4 와 그 품질 검토 반영이 `.rs-page` 규칙 둘레에 줄을 더해 줄 번호만 밀렸다). old:

```css
.rs-body--A .rs-col-side {
  position: sticky;
  top: 1.2rem;
  max-height: calc(100vh - 2.4rem);
  overflow-y: auto;
}
```

new:

```css
/* 고정 진행 막대(--rs-bar-h — 막대가 없으면 0px) 바로 아래에 붙는다 */
.rs-body--A .rs-col-side {
  position: sticky;
  top: calc(var(--rs-bar-h) + 1.2rem);
  max-height: calc(100vh - 2.4rem - var(--rs-bar-h));
  overflow-y: auto;
}
```

② (걷음 — D4 품질 검토 반영) 절 이동 자리 `.rs-section` 의 `scroll-margin-top` 은 `1.2rem` 그대로 둔다. 막대 높이는 D4 반영의 `html:has(.rs-page.has-progressbar) { scroll-padding-top: var(--rs-bar-area-h) }` 가 이미 `scrollIntoView` 에 넣는다 — 여기에 다시 더하면 절 이동이 막대 높이만큼 더 내려가고 `researchProgress.test.ts` 의 research.css 여백 `it` 이 실패한다. 그 규칙의 주석도 D4 반영이 이미 고쳤다.

- [ ] **Step 7: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Task D4 뒤 수 + 3(da80f23 이면 `Test Files 41 passed (41)` / `Tests 753 passed (753)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "insetTargetTop" composables/useRestorePosition.ts && grep -cw "targetTop" composables/useRestorePosition.ts`
Expected: `2` 다음 줄 `0`(import 와 맞출 높이 한 곳이 `insetTargetTop` 이고, `targetTop` 을 직접 부르는 곳은 남지 않았다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "var(--rs-bar-h" assets/css/research.css`
Expected: `3`(옆 칸 `top`·`max-height`, `.rs-pbar` `height` — 옆 칸과 막대가 같은 토큰을 읽는다. 처음 계획 값 `4` 의 `.rs-section` `scroll-margin-top` 은 D4 품질 검토 반영으로 걷었다 — 문서 여백은 `var(--rs-bar-area-h)` 라 이 grep 에 잡히지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "scroll-padding-top: var(--rs-bar-area-h);" assets/css/research.css && grep -c "scroll-margin-top: 1.2rem;" assets/css/research.css`
Expected: `1` 다음 줄 `1`(D4 품질 검토 반영의 문서 여백 그대로, 절 이동 자리는 막대 높이를 다시 더하지 않음)

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/restorePosition.ts frontend/composables/useRestorePosition.ts "frontend/pages/research/[id].vue" frontend/assets/css/research.css frontend/tests/unit/restorePosition.test.ts && git status --short && git commit -m "[Feat] round06d — 고정 진행 막대의 높이만큼 옆 칸·상세에서 돌아온 자리를 내린다(spec §12-3 오프셋·정함 3). A 의 옆 칸 top 과 높이가 막대 높이 토큰(--rs-bar-h — 막대가 없으면 0px)을 더한다. 절 이동 자리(.rs-section scroll-margin-top)는 D4 품질 검토 반영의 문서 scroll-padding-top 이 이미 막대 아래로 내리므로 그대로 둔다. 위치 복원은 새 insetTargetTop(떠날 때의 높이와 막대 아래 중 더 아래)으로 맞춰 돌아온 칩·항목이 막대 밑에 숨지 않는다 — useRestorePosition 에 topInset 을 더하고 연구 화면은 막대 요소의 높이를 넘긴다(맞추는 순간에는 화면이 맨 위라 위치가 아니라 높이를 쓴다). 막대가 없는 화면(논문 검색·끝난 연구)은 지금과 같다"
```

---

### Task D6: 따라가기 판단 순수 함수 `utils/researchFollow.ts`

spec §12-3 '지금 진행하는 절 따라가기' 행(기본 켬, 종합 중 `eta.runningIdx`, 탐색 중 도는 하위질문의 절 자리, 사용자 스크롤(휠·터치·키·스크롤바)이면 멈추고 "↓ 지금 쓰는 곳으로" 알약, 프로그램 스크롤은 거름, 위치 복원 중·원문 뷰어·고정 인용 팝오버·최종본 뒤 멈춤, `prefers-reduced-motion` 이면 즉시 이동, 켜고 끄는 판단은 순수 함수 + vitest — `ledgerFollowing` 선례) · §12-7 06d vitest '따라가기 켜고 끄기' · 정함 4·5·7. 창 이벤트·스크롤은 Task D7 의 composable 이 하고, 무엇이 따라가기를 멈추는지·어디로 갈지·지금 옮길지·알약 글은 이 파일의 순수 함수가 정한다(`utils/evidenceLedger.ts` 의 `ledgerFollowing` 이 장부 목록 따라가기를 순수 함수로 뺀 것과 같은 꼴).

**알아 둘 것:**
- **선행: Task L1** — `utils/planSlots.ts` 의 `slotElementId`(`rs-slot-${하위질문 번호}`)·`PlanSlot`(Task L1 — `subqIdx`·`sectionIdx` 등)을 import 한다. Step 0 이 있는지 본다.
- **멈추는 것은 사용자 입력뿐이다(정함 4).** 세로 휠(Ctrl 없음 — Ctrl+휠은 확대, 가로가 앞서는 휠은 트랙패드 옆 밀기)·터치 이동(`touchmove` — 탭(`touchstart`)은 아니다)·스크롤 키(`FOLLOW_KEYS` — 입력칸 밖. 수식 키 조합은 페이지를 굴리는 것만 멈춘다: Ctrl+Home/End(Windows·Linux 의 문서 처음·끝 — Chromium 은 Firefox 에 맞춰 Ctrl 조합 가운데 이 둘만 굴린다)·Cmd+↑/↓(macOS 의 문서 처음·끝)·Option+↑/↓(macOS 의 PageUp/PageDown). Ctrl+PageUp/PageDown(탭 전환)·Alt+Home(브라우저 홈)·Ctrl/Cmd+Space(입력기 전환)·Ctrl+방향키·수식 키 둘 이상은 멈추지 않는다 — **D6 품질 검토 반영**: 처음 계획은 수식 키가 하나라도 있으면 멈추지 않아 Ctrl+Home/End 로 질문을 다시 읽으러 가도 따라가기가 화면을 도로 끌고 갔다. 플랫폼은 가르지 않는다 — Windows 의 Alt+↑/↓ 처럼 굴리지 않는 곳에서 멈춰도 알약으로 다시 켤 수 있다)·페이지 스크롤바 누르기(`pointerdown` 의 `clientX >= document.documentElement.clientWidth` — 스크롤바는 문서 폭 바깥 띠다). `scroll` 이벤트로 가르지 않는다 — 브라우저 스크롤 앵커링·절이 펼쳐지며 밀린 자리·돌아온 자리 붙잡기(`useRestorePosition.hold`)가 내는 `scroll` 을 플래그로 다 거를 수 없다. 화면이 부른 `scrollIntoView` 는 입력 이벤트를 내지 않으므로 저절로 걸러진다 — spec 의 '프로그램이 일으킨 스크롤은 플래그로 거른다'를 이것으로 갈음한다(Claude 해석, 완료노트에 적는다). 휠의 세로 판정은 `isUserMove`(`utils/restorePosition.ts:76-80`)와 같은 기준(세로가 가로 이상)이다.
- **갈 곳(`followTarget`).** 종합 중이고 초안이 있으면 쓰는 절 `rs-sec-${eta.runningIdx}`(`ReportView.vue:27` 의 절 id — 초안은 아직 쓰지 않은 절까지 자리를 그린다, `ReportView.vue:165-175`). 종합 중이고 초안 전(첫 절이 끝나기 전 — 본문은 Task L2 의 절 자리)이면 `sectionIdx === eta.runningIdx` 인 자리의 `rs-slot-${subqIdx}`(하위질문 번호와 절 번호가 다르다 — 근거 0 하위질문은 절이 되지 않는다). 대응을 아직 모르면(절 제목이 오기 전) null — 엉뚱한 자리로 끌지 않는다. 탐색 중이면 도는 하위질문의 `rs-slot-${idx}` — 이번 시도의 행만 본다(`stopPoint`·`researchProgress` 와 같은 `exploreAttemptStart`·`fromEarlierAttempt` 규칙, D6 품질 검토 반영 — 탐색부터 다시 도는 재시도에서 이전 시도에 running 으로 남은 행은 도는 하위질문이 아니다. 회수기가 running 단계를 닫으므로 일관성을 위한 것). 절 사이·하위질문 사이(도는 것이 없음)와 그 밖의 단계(계획·대기·완료·실패·취소)는 null — 최종본 뒤에는 따라가지 않는다.
- **`sectionElementId(idx)` 는 이 파일이 내보낸다** — `ReportView.vue:27`·`[id].vue` 의 `jumpToSection`(da80f23 :365)이 쓰는 같은 글자(`rs-sec-${idx}`)다. 그 두 곳은 고치지 않는다(ReportView 는 정함 8 로 고치지 않는 파일).
- **막힘(`followBlocked`, 정함 5)** = 돌아온 자리를 맞추는 중(`restore.pending`)·원문 뷰어를 연 동안(`pdf`)·인용 팝오버가 열린 동안(고정·hover 를 가리지 않는다 — `CitationChip.vue` 는 팝오버를 열 때만 `.rs-cite__pop` 을 그린다(`:25-26` `v-if="open"`), 고정 여부를 밖에 알리지 않으므로 DOM 으로 본다 — Task D7). `shouldFollowMove` 는 따라가는 중·막히지 않음·대상이 있음·대상이 바뀜일 때만 참이다.
- **알약(`followPill`, 정함 7)** — 따라가기를 멈췄고 갈 곳이 있을 때만: 종합 중 `↓ 지금 쓰는 곳으로`(spec 그대로), 탐색 중 `↓ 지금 찾는 곳으로`(탐색 중에는 쓰는 글이 없다 — Claude 해석). `followBehavior` 는 움직임 줄이기면 `auto`(즉시), 아니면 `smooth`.
- 새 이름은 모두 `.nuxt/imports.d.ts`(da80f23)·06c·06e 계획에 없는 이름이다.

**Files:**
- Create: `frontend/utils/researchFollow.ts`
- Test: `frontend/tests/unit/researchFollow.test.ts`(새 파일 — 12)

기준선: Task L2 뒤 수(계획 머리 '테스트 수 어림' 대로면 da80f23 기준 `42 files / 766` — Task L1 이 파일 1·테스트 13 을 더한다).

- [ ] **Step 0: 선행 Task L1 을 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "export function slotElementId\|export interface PlanSlot {" utils/planSlots.ts`
Expected: `2`(없으면 Task L1 을 먼저 한다 — 이 Task 는 그 두 이름을 import 한다)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchFollow.test.ts` (새 파일):

```ts
// frontend/tests/unit/researchFollow.test.ts
import { describe, expect, it } from "vitest";
import type { StepStatus, SubqView } from "~/types/research";
import type { PlanSlot } from "~/utils/planSlots";
import type { SynthEta } from "~/utils/researchDraft";
import {
  FOLLOW_KEYS,
  FOLLOW_PILL_EXPLORE,
  FOLLOW_PILL_WRITE,
  breaksFollow,
  followBehavior,
  followBlocked,
  followPill,
  followTarget,
  sectionElementId,
  shouldFollowMove,
  type FollowInput,
} from "~/utils/researchFollow";

type KeyInput = Extract<FollowInput, { type: "keydown" }>;

function key(k: string, over: Partial<KeyInput> = {}): KeyInput {
  return { type: "keydown", key: k, editable: false, ctrlKey: false, metaKey: false, altKey: false, ...over };
}

function eta(over: Partial<SynthEta> = {}): SynthEta {
  return { done: 0, total: 0, runningIdx: null, runningElapsedMs: null, remainingMs: null, ...over };
}

function subq(idx: number, status: StepStatus): SubqView {
  return {
    idx, title: `하위질문 ${idx + 1}`, seq: idx + 1, status, rounds: [],
    verdict: null, note: "", adopted: null, parseFailed: false, error: null,
  };
}

function slot(subqIdx: number, over: Partial<PlanSlot> = {}): PlanSlot {
  return { subqIdx, title: `하위질문 ${subqIdx + 1}`, state: "collected", adopted: 3, round: null, sectionIdx: null, ...over };
}

function target(over: Partial<Parameters<typeof followTarget>[0]> = {}): string | null {
  return followTarget({ phase: "synthesizing", eta: eta(), hasDraft: false, slots: [], subqs: [], ...over });
}

describe("breaksFollow", () => {
  it("세로 휠은 멈추고 가로 휠·Ctrl+휠(확대)은 멈추지 않는다", () => {
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 120, ctrlKey: false })).toBe(true);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: -40, ctrlKey: false })).toBe(true);
    expect(breaksFollow({ type: "wheel", deltaX: 80, deltaY: 10, ctrlKey: false })).toBe(false);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 0, ctrlKey: false })).toBe(false);
    expect(breaksFollow({ type: "wheel", deltaX: 0, deltaY: 120, ctrlKey: true })).toBe(false);
  });

  it("터치로 끌면 멈춘다", () => {
    expect(breaksFollow({ type: "touchmove" })).toBe(true);
  });

  it("스크롤 키는 멈추되 입력칸 안의 키·수식 키를 함께 누른 키는 멈추지 않는다", () => {
    expect(FOLLOW_KEYS).toEqual(["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "]);
    for (const k of FOLLOW_KEYS) expect(breaksFollow(key(k))).toBe(true);
    expect(breaksFollow(key("Tab"))).toBe(false);
    expect(breaksFollow(key("a"))).toBe(false);
    expect(breaksFollow(key(" ", { editable: true }))).toBe(false);
    expect(breaksFollow(key("ArrowDown", { editable: true }))).toBe(false);
    expect(breaksFollow(key("ArrowLeft", { altKey: true }))).toBe(false);
    expect(breaksFollow(key("End", { ctrlKey: true }))).toBe(false);
    expect(breaksFollow(key("ArrowDown", { metaKey: true }))).toBe(false);
  });

  it("페이지 스크롤바를 누르면 멈추고 본문을 누르면 멈추지 않는다", () => {
    expect(breaksFollow({ type: "pointerdown", clientX: 1425, viewportWidth: 1425 })).toBe(true);
    expect(breaksFollow({ type: "pointerdown", clientX: 1432, viewportWidth: 1425 })).toBe(true);
    expect(breaksFollow({ type: "pointerdown", clientX: 700, viewportWidth: 1425 })).toBe(false);
    expect(breaksFollow({ type: "pointerdown", clientX: 1424, viewportWidth: 1425 })).toBe(false);
  });
});

describe("followTarget", () => {
  it("작성 중 초안이 있으면 쓰는 절(rs-sec-i)로 간다", () => {
    expect(sectionElementId(4)).toBe("rs-sec-4");
    expect(target({ eta: eta({ done: 2, total: 5, runningIdx: 2 }), hasDraft: true })).toBe("rs-sec-2");
  });

  it("작성 중 첫 절 전에는 쓰는 절의 하위질문 자리(rs-slot-k)로 간다", () => {
    // 하위질문 1 은 근거가 없어 절이 되지 않았다 — 절 0 은 하위질문 1, 절 1 은 하위질문 3 이다
    const slots = [
      slot(0, { state: "writing", sectionIdx: 0 }),
      slot(1, { state: "empty", adopted: 0 }),
      slot(2, { sectionIdx: 1 }),
    ];
    expect(target({ eta: eta({ total: 2, runningIdx: 0 }), slots })).toBe("rs-slot-0");
    expect(target({ eta: eta({ total: 2, runningIdx: 1 }), slots })).toBe("rs-slot-2");
    // 절 번호와 자리의 대응을 아직 모르면(절 제목이 오기 전) 옮기지 않는다
    expect(target({ eta: eta({ total: 2, runningIdx: 0 }), slots: [slot(0), slot(1)] })).toBeNull();
  });

  it("탐색 중에는 도는 하위질문의 자리로 간다", () => {
    expect(target({ phase: "exploring", subqs: [subq(0, "done"), subq(1, "running"), subq(2, "pending")] })).toBe("rs-slot-1");
  });

  it("도는 것이 없거나 계획·대기·끝난 단계면 null", () => {
    expect(target({ phase: "exploring", subqs: [subq(0, "done"), subq(1, "pending")] })).toBeNull();
    // 절 사이(앞 절이 끝나고 다음 절이 아직 시작되지 않음)
    expect(target({ eta: eta({ done: 1, total: 3 }), hasDraft: true })).toBeNull();
    for (const phase of ["planning", "awaiting", "queued", "completed", "failed", "canceled"] as const) {
      expect(target({ phase, eta: eta({ total: 3, runningIdx: 1 }), hasDraft: true, subqs: [subq(0, "running")] })).toBeNull();
    }
    expect(target({ phase: null })).toBeNull();
  });
});

describe("shouldFollowMove", () => {
  it("따라가는 중이고 막히지 않았고 대상이 바뀌었을 때만 옮긴다", () => {
    const s = { following: true, blocked: false, target: "rs-sec-2", last: "rs-sec-1" };
    expect(shouldFollowMove(s)).toBe(true);
    expect(shouldFollowMove({ ...s, last: null })).toBe(true);
    expect(shouldFollowMove({ ...s, following: false })).toBe(false);
    expect(shouldFollowMove({ ...s, blocked: true })).toBe(false);
    expect(shouldFollowMove({ ...s, target: null })).toBe(false);
    expect(shouldFollowMove({ ...s, last: "rs-sec-2" })).toBe(false);
  });
});

describe("followBlocked", () => {
  it("위치 복원 중·원문 뷰어·열린 인용 팝오버면 막는다", () => {
    const none = { restoring: false, pdfOpen: false, popoverOpen: false };
    expect(followBlocked(none)).toBe(false);
    expect(followBlocked({ ...none, restoring: true })).toBe(true);
    expect(followBlocked({ ...none, pdfOpen: true })).toBe(true);
    expect(followBlocked({ ...none, popoverOpen: true })).toBe(true);
  });
});

describe("followPill", () => {
  it("따라가기를 멈췄고 갈 곳이 있을 때만 띄운다 — 작성 중 '↓ 지금 쓰는 곳으로', 탐색 중 '↓ 지금 찾는 곳으로'", () => {
    expect(FOLLOW_PILL_WRITE).toBe("↓ 지금 쓰는 곳으로");
    expect(FOLLOW_PILL_EXPLORE).toBe("↓ 지금 찾는 곳으로");
    expect(followPill({ phase: "synthesizing", following: false, target: "rs-sec-2" })).toBe(FOLLOW_PILL_WRITE);
    expect(followPill({ phase: "exploring", following: false, target: "rs-slot-1" })).toBe(FOLLOW_PILL_EXPLORE);
    expect(followPill({ phase: "synthesizing", following: true, target: "rs-sec-2" })).toBeNull();
    expect(followPill({ phase: "synthesizing", following: false, target: null })).toBeNull();
    expect(followPill({ phase: "completed", following: false, target: "rs-sec-2" })).toBeNull();
  });
});

describe("followBehavior", () => {
  it("움직임 줄이기면 즉시(auto), 아니면 부드럽게(smooth)", () => {
    expect(followBehavior(true)).toBe("auto");
    expect(followBehavior(false)).toBe("smooth");
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchFollow.test.ts`
Expected: `FAIL tests/unit/researchFollow.test.ts` — `Error: Cannot find module '~/utils/researchFollow' imported from '…/frontend/tests/unit/researchFollow.test.ts'.` / `Test Files 1 failed (1)` / `Tests no tests`

- [ ] **Step 3: `utils/researchFollow.ts` 를 만든다**

`frontend/utils/researchFollow.ts` (새 파일):

```ts
// frontend/utils/researchFollow.ts
// 지금 진행하는 절 따라가기(spec §12-3, D22)의 켜고 끄는 판단. 창 이벤트·스크롤은 composables/useSectionFollow.ts 가 한다.
// 따라가기를 멈추는 것은 사용자 입력뿐이다(정함 4) — scroll 이벤트로 가르지 않는다. 브라우저의 스크롤 앵커링·절이 펼쳐지며 밀린
// 자리·돌아온 자리 붙잡기(useRestorePosition)가 내는 scroll 을 플래그로 다 거를 수 없고, 화면이 부른 scrollIntoView 는 입력
// 이벤트를 내지 않아 저절로 걸러진다(spec 의 '프로그램 스크롤은 플래그로 거른다'를 이것으로 갈음한다)
import type { SubqView } from "~/types/research";
import { slotElementId, type PlanSlot } from "~/utils/planSlots";
import type { SynthEta } from "~/utils/researchDraft";
import type { ResearchPhase } from "~/utils/researchEvents";

// 창에서 받은 입력 — 이벤트마다 판단에 쓰는 값만 옮긴다(viewportWidth = document.documentElement.clientWidth)
export type FollowInput =
  | { type: "wheel"; deltaX: number; deltaY: number; ctrlKey: boolean }
  | { type: "touchmove" }
  | { type: "keydown"; key: string; editable: boolean; ctrlKey: boolean; metaKey: boolean; altKey: boolean }
  | { type: "pointerdown"; clientX: number; viewportWidth: number };

// 페이지를 굴리는 키(" " 는 Space)
export const FOLLOW_KEYS: readonly string[] = ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "];
export const FOLLOW_PILL_WRITE = "↓ 지금 쓰는 곳으로";
// 탐색 중에는 쓰는 글이 없다 — 도는 하위질문의 자리로 간다
export const FOLLOW_PILL_EXPLORE = "↓ 지금 찾는 곳으로";

export function breaksFollow(e: FollowInput): boolean {
  switch (e.type) {
    case "wheel": {
      // 세로가 앞설 때만 — 가로 휠(트랙패드 옆 밀기)·Ctrl+휠(확대)은 화면을 굴리지 않는다
      const dy = Math.abs(e.deltaY);
      return !e.ctrlKey && dy > 0 && dy >= Math.abs(e.deltaX);
    }
    case "touchmove":
      return true;
    case "keydown":
      // 입력칸 안의 키(글자 사이 이동·공백)와 수식 키를 함께 누른 키(뒤로 가기·탭 이동 등)는 페이지를 굴리지 않는다
      return !e.editable && !e.ctrlKey && !e.metaKey && !e.altKey && FOLLOW_KEYS.includes(e.key);
    case "pointerdown":
      // 페이지 스크롤바는 문서 폭(clientWidth) 바깥 띠다 — 그 띠를 누르거나 끄는 것은 사용자가 굴리는 것이다
      return e.clientX >= e.viewportWidth;
  }
}

// 보고서 절의 자리 id — ReportView 의 절 <section> 과 현황 카드의 jumpToSection 이 같은 글자를 쓴다
export function sectionElementId(idx: number): string {
  return `rs-sec-${idx}`;
}

// 따라갈 자리. 종합 중 초안이 있으면 쓰는 절, 첫 절 전이면 그 절이 될 하위질문의 자리(절 번호를 아는 자리만),
// 탐색 중이면 도는 하위질문의 자리. 쓰는·도는 것이 없거나(사이) 그 밖의 단계(최종본 포함)는 null
export function followTarget(input: {
  phase: ResearchPhase | null;
  eta: SynthEta;
  hasDraft: boolean;
  slots: readonly PlanSlot[];
  subqs: readonly SubqView[];
}): string | null {
  if (input.phase === "synthesizing") {
    const idx = input.eta.runningIdx;
    if (idx === null) return null;
    if (input.hasDraft) return sectionElementId(idx);
    const slot = input.slots.find((s) => s.sectionIdx === idx);
    return slot ? slotElementId(slot.subqIdx) : null;
  }
  if (input.phase === "exploring") {
    const running = input.subqs.find((s) => s.status === "running");
    return running ? slotElementId(running.idx) : null;
  }
  return null;
}

// 옮기지 않는 때 — 돌아온 자리를 맞추는 중, 원문 뷰어를 연 동안, 인용 팝오버를 읽는 동안(고정·hover 를 가리지 않는다)
export function followBlocked(c: { restoring: boolean; pdfOpen: boolean; popoverOpen: boolean }): boolean {
  return c.restoring || c.pdfOpen || c.popoverOpen;
}

export function shouldFollowMove(s: { following: boolean; blocked: boolean; target: string | null; last: string | null }): boolean {
  return s.following && !s.blocked && s.target !== null && s.target !== s.last;
}

export function followPill(s: { phase: ResearchPhase | null; following: boolean; target: string | null }): string | null {
  if (s.following || s.target === null) return null;
  if (s.phase === "synthesizing") return FOLLOW_PILL_WRITE;
  if (s.phase === "exploring") return FOLLOW_PILL_EXPLORE;
  return null;
}

// 움직임 줄이기를 켠 사람에게는 부드럽게 굴리지 않고 곧바로 옮긴다
export function followBehavior(reducedMotion: boolean): "auto" | "smooth" {
  return reducedMotion ? "auto" : "smooth";
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchFollow.test.ts`
Expected: `Test Files 1 passed (1)` / `Tests 12 passed (12)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Task L2 뒤 수 + 파일 1·테스트 12(계획 머리 '테스트 수 어림' 대로면 da80f23 기준 `Test Files 43 passed (43)` / `Tests 778 passed (778)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchFollow.ts frontend/tests/unit/researchFollow.test.ts && git status --short && git commit -m "[Feat] round06d — 지금 진행하는 절 따라가기의 켜고 끄는 판단을 순수 함수(utils/researchFollow.ts)로 둔다(spec §12-3·정함 4·5·7). 따라가기를 멈추는 것은 사용자 입력뿐이다 — 세로 휠(Ctrl+휠·가로 휠 제외)·터치 이동·스크롤 키(입력칸 밖·수식 키 없음)·페이지 스크롤바 누르기. scroll 이벤트로 가르지 않아 화면이 부른 이동·스크롤 앵커링은 저절로 걸러진다. 갈 곳은 종합 중 쓰는 절(초안 전에는 그 절이 될 하위질문 자리 — 대응을 모르면 옮기지 않음), 탐색 중 도는 하위질문 자리, 그 밖·최종본 뒤에는 없다. 위치 복원 중·원문 뷰어·열린 인용 팝오버 동안은 옮기지 않고, 멈췄을 때 알약은 '↓ 지금 쓰는 곳으로'(탐색 중 '↓ 지금 찾는 곳으로'), 움직임 줄이기면 즉시 옮긴다"
```

---

### Task D7: 따라가기 연결 — `useSectionFollow`·알약

spec §12-3 '지금 진행하는 절 따라가기' 행의 연결 — 기본 켬, 대상이 바뀌면 그 자리로 스크롤, 사용자 스크롤이면 멈추고 "↓ 지금 쓰는 곳으로" 알약, 위치 복원 중·원문 뷰어·고정 인용 팝오버·최종본 뒤 멈춤, reduced-motion 이면 즉시 이동, 알약 CSS 는 `work.css:613-622` 를 고치지 않고 `research.css` 로 옮겨 씀(`[id].vue:273`·`:314-318`·`:356-377`) · D22 가 round04b spec §7-4 '자동 스크롤로 끌고 가지 않는다'(지금 `[id].vue:363` 의 주석 '사용자가 누를 때만 옮긴다')를 덮는다 · 정함 4~7. Task D6 의 판단을 창 이벤트·`scrollIntoView` 에 잇는다.

**알아 둘 것:**
- **선행: Task L2·D5·D6.** L2 가 연구 화면에 만든 `planSlotList`(`computed(() => (view.value ? planSlots(view.value) : []))` — Task L2)와 절 자리 `<section :id="slotElementId(…)" class="rs-section rs-slot">`(ReportSkeleton)이 있어야 탐색 중·첫 절 전 대상이 DOM 에 있다. D4 품질 검토 반영의 문서 `scroll-padding-top`(막대 높이 — `html:has(.rs-page.has-progressbar)`)과 `.rs-section` 의 `scroll-margin-top: 1.2rem` 이 있어 `scrollIntoView({ block: "start" })` 가 절 제목을 막대 밑에 숨기지 않는다(처음 계획은 D5 가 `scroll-margin-top` 에 막대 높이를 더했으나 그 몫을 문서 여백이 맡아 걷었다 — Task D5 '알아 둘 것'). D5 는 옆 칸을 막대 아래로 내린다. Step 0 이 확인한다.
- **`useSectionFollow`(이 Task 의 Step 1).** 창에 `wheel`·`touchmove`·`keydown`·`pointerdown` 을 capture·passive 로 마운트 때 걸고 언마운트 때 푼다(`useRestorePosition.ts:73-79` 의 걸기·풀기와 같은 꼴 — 그쪽은 탭(`touchstart`)도 움직임으로 보지만 따라가기는 끄는 것(`touchmove`)만 본다). 입력은 `breaksFollow`(D6)로 가른다. 키의 `editable` 은 입력칸·메뉴·목록 상자·대화상자 안(`input, textarea, select, [contenteditable], [role='menu'], [role='listbox'], [role='dialog']`)에서 누른 키 — 그 안의 방향키·Space 는 페이지를 굴리지 않는다(인용 팝오버도 `role="dialog"`). 초점이 간 버튼(`button, [role='button'], summary` — 인용칩·현황 카드의 절) 위의 Space 도 `editable` 로 본다 — 버튼이 누름으로 받아 페이지를 굴리지 않는다(방향키는 버튼 위에서도 굴리므로 Space 만).
- **모달이 페이지를 묶은 동안의 입력은 멈춤으로 보지 않는다.** 원문 뷰어(`PdfViewer.vue:153-158` `lockPage`)와 온보딩(`OnboardingModal.vue:47-51` `lock`)은 열린 동안 `documentElement` 의 `overflow` 를 숨겨 페이지를 묶는다 — 둘 다 `role="dialog" aria-modal="true"`(`PdfViewer.vue:5`·`OnboardingModal.vue:5`)이고 열린 동안만 DOM 에 있다. 원문 쪽(PDF)은 iframe(`PdfViewer.vue:33`) 안이라 그 위의 휠은 이 창에 오지 않지만, 뷰어 머리 줄과 어두운 바탕(`.pdf-overlay` — `aria-modal` 바깥 부모) 위의 휠·터치는 창의 capture 리스너에 닿는다. 그대로 두면 원문을 보는 동안 멈추고 닫은 뒤에도 꺼진 채 알약만 남아 정함 5('막힌 동안 바뀐 대상은 다음 바뀜에 옮긴다')가 원문 뷰어에서 지켜지지 않는다. 그래서 `onInput` 은 멈출 입력일 때 `document.querySelector("[aria-modal='true']")` 가 있으면 멈추지 않는다 — 대상 요소의 조상으로 보지 않고 문서에 있는지로 보는 까닭은 바탕(`.pdf-overlay`·`.wk-modal`)이 `aria-modal` 요소 바깥이라서다. 모달이 열린 동안 바뀐 대상은 막힘(원문 뷰어 `pdf`)으로 지나가고, 닫은 뒤 다음 바뀜에 옮긴다.
- **옮기기.** 대상이 바뀌면 `shouldFollowMove`(따라가는 중·막히지 않음·바뀜) → `nextTick`(대상 자리가 DOM 에 붙은 뒤) → `requestAnimationFrame`(배치가 끝난 다음 프레임) → 그 순간 다시 따라가는 중인지·막혔는지 보고 `getElementById(t).scrollIntoView({ behavior: followBehavior(prefers-reduced-motion), block: "start" })`. 막힌 동안 바뀐 대상은 지나간 것으로 두고 다음 바뀜에 옮긴다(정함 5). 알약(`resume`)은 다시 켜며 지금 대상으로 곧바로 옮긴다 — 사용자가 누른 이동이라 막힘을 보지 않는다.
- **처음 본 대상은 기준으로만 삼는다**(파트 D 끝 '파트 메모' 4) — 연구 화면을 연 순간(새로고침·사이드바로 들어옴)의 대상으로 곧바로 끌고 내려가지 않고, 다음 바뀜(다음 절·다음 하위질문)부터 옮긴다. 대상은 `view` 를 받은 뒤 처음 생기므로 서버 렌더에서는 늘 null 이고, 첫 감시 호출은 막힘(`document`)을 보지 않는다.
- **멈춘 채 시작(정함 6)** — 상세에서 돌아온 화면(`restore.anchor !== null`)은 사용자가 고른 자리를 다음 절이 시작될 때 빼앗지 않게 멈춘 채 시작하고 알약만 띄운다. 현황 카드의 절을 눌러 옮기면(`jumpToSection`) 따라가기를 멈춘다 — 고른 절을 읽는 동안 끌고 가지 않는다.
- **막힘(정함 5)은 옮기려는 순간에 본다** — `restore.pending`(돌아온 자리를 맞추는 중)·`pdf`(원문 뷰어 — `usePdfOpener`, da80f23 :513-514)·`document.querySelector(".rs-page .rs-cite__pop")`(열린 인용 팝오버 — `CitationChip.vue` 는 고치지 않는다). 그래서 따라가기 절은 `pdf` 를 정의하는 '원문 보기' 절 뒤, 앵커 `// ── 내려받기(Word·PDF) ──…`(da80f23 :521) 바로 위에 둔다. `jumpToSection`(:364)은 그보다 위에 있지만 누를 때만 도는 함수라 뒤에서 만든 `follow` 를 읽어도 된다.
- **알약**은 `rs-body` 를 닫는 `</div>` 바로 뒤 — `.rs-page`(세로 flex)의 마지막 자식이라 `position: sticky; bottom: 1rem` 으로 화면 아래 가운데에 붙는다(`work.css:613-622` `.wk-pill` 패턴 — `work.css` 는 06e 파일이라 고치지 않고 `research.css` 의 `.rs-follow-pill` 로 옮겨 쓴다). `rs-btn` 이라 인쇄 숨김(`.rs-page .rs-btn`)이 이미 덮는다. 단계 화면(stepMode)에서는 대상이 늘 null(완료 잡)이라 서지 않는다.
- 글이 나타나는 방식은 바꾸지 않는다 — 절은 지금처럼 끝나면 나타난다(`rs-reveal`, 타자 효과 없음).
- 테스트는 없다(+0) — 판단은 Task D6 가 본다. 움직임(따라감·멈춤·알약·팝오버 동안 멈춤·즉시 이동)은 마무리 운영 확인(Task Z6 Step 2·3)에서 본다 — 막힘 항목(Step 3 항목 4)에 '원문 뷰어를 열어 머리 줄·어두운 바탕 위에서 휠을 굴려도 닫은 뒤 알약 없이 다음 절에서 따라간다'가, 따라가기 항목(Step 2 항목 5)에 '첫 하위질문에서는 옮기지 않고 다음 하위질문부터'(처음 본 대상은 기준)가 있다.

**Files:**
- Create: `frontend/composables/useSectionFollow.ts`
- Modify: `frontend/pages/research/[id].vue`(D1·D2·D4·D5·L2 뒤 — 앵커 글자: `function jumpToSection(` 와 그 위 주석, `// ── 내려받기(Word·PDF) ──…`, `</aside>` + `</div>`, import 두 곳)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위 새 블록)

기준선: Task D6 뒤 수(계획 머리 '테스트 수 어림' 대로면 da80f23 기준 `43 files / 778`).

- [ ] **Step 0: 선행 Task 를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "const planSlotList = computed" "pages/research/[id].vue" && grep -c "slotElementId" components/research/ReportSkeleton.vue && grep -c "top: calc(var(--rs-bar-h) + 1.2rem);" assets/css/research.css && grep -c "scroll-padding-top: var(--rs-bar-area-h);" assets/css/research.css && grep -c "export function followTarget" utils/researchFollow.ts`
Expected: `1`·`1` 이상·`1`·`1`·`1` 다섯 줄(하나라도 0 이면 Task L2·D5·D4 품질 검토 반영·D6 을 먼저 한다 — 셋째 줄은 D5 의 옆 칸 `top`, 넷째 줄은 절 이동을 막대 아래로 내리는 문서 여백)

- [ ] **Step 1: 따라가기 composable 을 만든다**

`frontend/composables/useSectionFollow.ts` (새 파일):

```ts
// frontend/composables/useSectionFollow.ts
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type ComputedRef, type Ref } from "vue";
import type { ResearchPhase } from "~/utils/researchEvents";
import { breaksFollow, followBehavior, followPill, shouldFollowMove, type FollowInput } from "~/utils/researchFollow";

// 따라가기를 멈추는 사용자 입력. scroll 은 넣지 않는다 — 화면이 부른 이동·스크롤 앵커링도 scroll 을 낸다(utils/researchFollow.ts 머리)
const USER_INPUTS = ["wheel", "touchmove", "keydown", "pointerdown"] as const;
// 키를 스스로 쓰는 자리 — 안에서 누른 방향키·Space 는 페이지를 굴리지 않는다(입력칸·메뉴·목록 상자·대화상자)
const KEY_OWNERS = "input, textarea, select, [contenteditable], [role='menu'], [role='listbox'], [role='dialog']";
// Space 를 누름으로 받는 자리 — 초점이 간 버튼(인용칩·현황 카드의 절)·펼침 머리 위의 Space 는 페이지를 굴리지 않는다
const SPACE_OWNERS = "button, [role='button'], summary";
// 페이지를 묶는 모달 — 원문 뷰어(PdfViewer.vue lockPage)·온보딩(OnboardingModal.vue lock)이 열린 동안 documentElement 의 overflow 를
// 숨긴다. 그동안의 입력(뷰어 머리 줄·어두운 바탕 위의 휠·터치 포함)은 페이지를 굴리지 않는다. PDF 쪽 위의 휠은 iframe 안이라 이 창에 오지 않는다
const PAGE_LOCKERS = "[aria-modal='true']";

export interface SectionFollow {
  following: Readonly<Ref<boolean>>;
  pill: ComputedRef<string | null>;
  // 알약 — 다시 따라가며 지금 대상으로 곧바로 옮긴다
  resume(): void;
  // 현황 카드에서 절을 눌러 옮길 때
  pause(): void;
}

function ownsKeys(t: EventTarget | null): boolean {
  return t instanceof Element && t.closest(KEY_OWNERS) !== null;
}

function ownsSpace(t: EventTarget | null): boolean {
  return t instanceof Element && t.closest(SPACE_OWNERS) !== null;
}

// 창 이벤트를 판단 함수가 읽는 모양으로 옮긴다. 버튼 위의 Space 는 누름이라 입력칸 안의 키처럼 본다(editable)
function inputOf(e: Event): FollowInput | null {
  switch (e.type) {
    case "wheel": {
      const w = e as WheelEvent;
      return { type: "wheel", deltaX: w.deltaX, deltaY: w.deltaY, ctrlKey: w.ctrlKey };
    }
    case "touchmove":
      return { type: "touchmove" };
    case "keydown": {
      const k = e as KeyboardEvent;
      const editable = ownsKeys(k.target) || (k.key === " " && ownsSpace(k.target));
      return { type: "keydown", key: k.key, editable, ctrlKey: k.ctrlKey, metaKey: k.metaKey, altKey: k.altKey };
    }
    case "pointerdown":
      return { type: "pointerdown", clientX: (e as PointerEvent).clientX, viewportWidth: document.documentElement.clientWidth };
    default:
      return null;
  }
}

/**
 * 지금 진행하는 절을 스크롤이 따라가게 한다(spec D22). 대상(자리 id)이 바뀌면 그 자리로 옮기고, 사용자가 직접 굴리면 멈춘다 —
 * 멈춘 동안은 알약 글(pill)을 내고, 알약을 누르면(resume) 다시 따라가며 지금 대상으로 곧바로 옮긴다.
 * 처음 본 대상은 기준으로만 삼는다 — 들어온 화면을 곧바로 끌고 내려가지 않고 다음 바뀜부터 옮긴다. 막힌 동안(isBlocked) 바뀐
 * 대상은 지나간 것으로 두고 다음 바뀜에 옮긴다. 모달이 페이지를 묶은 동안의 입력은 멈춤으로 보지 않는다 — 원문 뷰어를 닫으면
 * 따라가던 대로 다음 바뀜에 옮긴다
 */
export function useSectionFollow(opts: {
  phase: ComputedRef<ResearchPhase | null>;
  target: ComputedRef<string | null>;
  // 옮기려는 순간에 부른다(DOM 을 본다)
  isBlocked: () => boolean;
  // 상세에서 돌아온 화면(restore.anchor !== null) — 사용자가 고른 자리를 빼앗지 않게 멈춘 채 시작한다
  startPaused: boolean;
}): SectionFollow {
  const following = ref(!opts.startPaused);
  const pill = computed(() => followPill({ phase: opts.phase.value, following: following.value, target: opts.target.value }));
  // 마지막으로 옮겨 간(또는 지나간) 대상
  let last: string | null = null;
  let primed = false;
  let frame = 0;

  function onInput(e: Event): void {
    if (!following.value) return;
    const input = inputOf(e);
    if (!input || !breaksFollow(input)) return;
    // 모달이 페이지를 묶은 동안은 굴려도 페이지가 움직이지 않는다 — 멈추면 닫은 뒤에도 꺼진 채 알약만 남는다
    if (document.querySelector(PAGE_LOCKERS)) return;
    pause();
  }

  // 대상 자리가 DOM 에 붙은 뒤(nextTick) 배치가 끝난 다음 프레임에 옮긴다. 옮기는 순간에 다시 본다 — 그 사이 사용자가 굴렸거나
  // 팝오버를 열었을 수 있다. 알약으로 다시 켠 이동(force)은 막힘을 보지 않는다 — 사용자가 누른 이동이다
  function move(id: string, force: boolean): void {
    void nextTick(() => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (!following.value || (!force && opts.isBlocked())) return;
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        document.getElementById(id)?.scrollIntoView({ behavior: followBehavior(reduce), block: "start" });
      });
    });
  }

  function resume(): void {
    following.value = true;
    const t = opts.target.value;
    last = t;
    if (t !== null) move(t, true);
  }

  function pause(): void {
    following.value = false;
  }

  watch(
    opts.target,
    (t) => {
      if (!primed) {
        primed = t !== null;
        last = t;
        return;
      }
      if (t !== null && shouldFollowMove({ following: following.value, blocked: opts.isBlocked(), target: t, last })) {
        move(t, false);
      }
      if (t !== null) last = t;
    },
    { immediate: true },
  );

  onMounted(() => {
    for (const type of USER_INPUTS) window.addEventListener(type, onInput, { capture: true, passive: true });
  });

  onBeforeUnmount(() => {
    for (const type of USER_INPUTS) window.removeEventListener(type, onInput, true);
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  });

  return { following, pill, resume, pause };
}
```

- [ ] **Step 2: 연구 화면에 잇는다**

`frontend/pages/research/[id].vue` ① 현황 카드에서 절을 누르면 따라가기를 멈춘다(da80f23 :363-366). old:

```ts
// 사용자가 누를 때만 옮긴다 — 절이 완성될 때마다 끌고 가면 초안을 읽던 자리를 잃는다
function jumpToSection(idx: number): void {
  const el = document.getElementById(`rs-sec-${idx}`);
  if (!el) return;
```

new:

```ts
// 현황 카드에서 절을 누르면 그 절로 옮기고 따라가기를 멈춘다 — 고른 절을 읽는 동안 다음 절이 시작돼도 끌고 가지 않는다(알약으로
// 다시 켠다). 절이 시작될 때마다 옮기는 것은 아래 따라가기(useSectionFollow)가 맡는다(spec D22 가 round04b §7-4 를 덮음)
function jumpToSection(idx: number): void {
  const el = document.getElementById(`rs-sec-${idx}`);
  if (!el) return;
  // follow 는 아래 '지금 진행하는 절 따라가기' 절에서 만든다 — 이 함수는 누를 때만 돌아 그때는 이미 있다
  follow.pause();
```

② 따라가기 — 원문 보기 절 뒤, 앵커 `// ── 내려받기(Word·PDF) ──…`(da80f23 :521) 바로 위. old:

```ts
// ── 내려받기(Word·PDF) ────────────────────────────────────
```

new:

```ts
// ── 지금 진행하는 절 따라가기 ─────────────────────────────
// 종합 중에는 쓰는 절(초안 전에는 그 절이 될 하위질문 자리), 탐색 중에는 도는 하위질문 자리로 스크롤이 따라간다(spec D22).
// 사용자가 직접 굴리면 멈추고 알약으로 다시 켠다. 돌아온 자리를 맞추는 중·원문 뷰어·열린 인용 팝오버 동안은 옮기지 않고,
// 상세에서 돌아온 화면은 멈춘 채 시작한다(고른 자리를 빼앗지 않게). 최종본 뒤에는 대상이 없어 멈춘다
const followTargetId = computed(() =>
  followTarget({
    phase: phase.value,
    eta: eta.value,
    hasDraft: !!draft.value,
    slots: planSlotList.value,
    subqs: view.value?.subqs ?? [],
  }),
);
const follow = useSectionFollow({
  phase,
  target: followTargetId,
  isBlocked: () =>
    followBlocked({
      restoring: restore.pending.value,
      pdfOpen: !!pdf.value,
      popoverOpen: !!document.querySelector(".rs-page .rs-cite__pop"),
    }),
  startPaused: restore.anchor !== null,
});

// ── 내려받기(Word·PDF) ────────────────────────────────────
```

③ 알약 — `rs-body` 를 닫는 줄 바로 뒤(da80f23 :190-191 — `</aside>` 는 파일에 하나). old:

```html
          </aside>
        </div>
```

new:

```html
          </aside>
        </div>
        <!-- 따라가기를 멈춘 동안만 뜬다 — 누르면 지금 쓰는(찾는) 곳으로 옮기고 다시 따라간다. 화면 아래 가운데에 붙는다 -->
        <button v-if="follow.pill.value" type="button" class="rs-btn rs-btn--small rs-follow-pill" @click="follow.resume()">
          {{ follow.pill.value }}
        </button>
```

④ import 두 곳. old:

```ts
import { useRestorePosition } from "~/composables/useRestorePosition";
```

new:

```ts
import { useRestorePosition } from "~/composables/useRestorePosition";
import { useSectionFollow } from "~/composables/useSectionFollow";
```

old(Task D4 가 더한 줄):

```ts
import { activeRoundKey, maxRoundsOf, progressBarView, showsProgressBar } from "~/utils/researchProgress";
```

new:

```ts
import { activeRoundKey, maxRoundsOf, progressBarView, showsProgressBar } from "~/utils/researchProgress";
import { followBlocked, followTarget } from "~/utils/researchFollow";
```

- [ ] **Step 3: 알약 스타일을 둔다**

`frontend/assets/css/research.css` — 인쇄 앵커 바로 위(Task L2 의 `.rs-slot*` 블록 뒤). old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 따라가기 알약 ───────────────────────────────────────── */
/* 사용자가 굴려 따라가기를 멈춘 동안만 뜬다 — 화면 아래 가운데에 붙어 있다가 누르면 지금 쓰는(찾는) 곳으로 옮긴다.
   work.css 의 .wk-pill 패턴(sticky·가운데·그림자)을 옮겨 쓴다(work.css 는 고치지 않는다). 인쇄에서는 .rs-btn 규칙이 뺀다 */
.rs-follow-pill {
  position: sticky;
  bottom: 1rem;
  z-index: 4;
  align-self: center;
  box-shadow: var(--skx-shadow-lnb);
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 4: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Task D6 뒤와 같은 수(+0 — 계획 머리 '테스트 수 어림' 대로면 da80f23 기준 `Test Files 43 passed (43)` / `Tests 778 passed (778)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "사용자가 누를 때만 옮긴다" "pages/research/[id].vue" ; grep -c "follow.pause();" "pages/research/[id].vue"`
Expected: `0` 다음 줄 `1`(round04b §7-4 의 '누를 때만' 주석이 걷히고, 절을 누른 이동이 따라가기를 멈춘다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "PAGE_LOCKERS" composables/useSectionFollow.ts ; grep -c "SPACE_OWNERS" composables/useSectionFollow.ts`
Expected: `2` 다음 줄 `2`(각각 정의와 쓰는 곳 — 모달이 페이지를 묶은 동안의 입력과 버튼 위 Space 는 따라가기를 멈추지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat HEAD -- frontend/assets/css/work.css frontend/components/research/CitationChip.vue frontend/components/research/ReportView.vue`
Expected: (빈 출력 — 알약은 `work.css` 를 고치지 않고 옮겨 썼고, 팝오버·절 id 부품은 그대로다)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/composables/useSectionFollow.ts "frontend/pages/research/[id].vue" frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 지금 쓰는 절을 스크롤이 따라가고, 사용자가 스크롤하면 멈추고 '↓ 지금 쓰는 곳으로' 알약을 띄운다(D22 — round04b §7-4 '누를 때만 옮긴다'를 덮음). 새 useSectionFollow 가 창의 휠·터치 이동·스크롤 키·스크롤바 누르기로만 멈추고(원문 뷰어 같은 모달이 페이지를 묶은 동안의 입력과 버튼 위 Space 는 페이지를 굴리지 않아 빼고 — 원문을 보고 닫아도 따라가기가 꺼지지 않는다), 대상(종합 중 쓰는 절 — 첫 절 전에는 그 하위질문 자리, 탐색 중 도는 하위질문 자리)이 바뀌면 다음 프레임에 그 자리로 옮긴다(움직임 줄이기면 즉시). 돌아온 자리를 맞추는 중·원문 뷰어·열린 인용 팝오버 동안은 옮기지 않고, 상세에서 돌아온 화면은 멈춘 채 시작하며, 현황 카드에서 절을 눌러 옮기면 멈춘다. 연구 화면을 연 순간의 대상으로는 끌고 내려가지 않고 다음 바뀜부터 옮긴다. 알약은 work.css 의 .wk-pill 패턴을 research.css 의 .rs-follow-pill 로 옮겨 쓴다"
```

---

### Task D8: 스타일 — 머리·옆 칸 skx 토큰

spec §12-3 '스타일' 행(고치는 부품만 skx 토큰 — 머리·진행 영역·옆 칸, skx 검색바는 넣지 않음 — Q8 동의) · §12-1 표 '06d 연구 화면 머리·research.css 스타일 통일'. 진행 영역(큰 진행 막대)은 Task D4 가 처음부터 skx 토큰으로 입혔고, 이 Task 는 머리(kicker·질문·상태 배지·버튼 줄)와 옆 칸 카드 머리를 같은 크기 체계로 맞춘다. 마지막에 두는 까닭은 옆 칸의 장부 배치(Task L5)가 끝난 뒤 두 카드 머리를 함께 보고 맞추기 위해서다.

**알아 둘 것:**
- **`--skx-*` 토큰만 쓴다** — 새 색값(hex·rgba)을 넣지 않는다(`research.css:2-4` 머리 주석의 규칙). 쓰는 토큰: `--skx-primary`·`--skx-border-c1`·`--skx-white`·`--skx-ink`·`--skx-radius-pill`(`style_skovix.css:186-214`).
- **머리:** kicker '딥리서치'(`ResearchHeader.vue:5`)를 skx 칩으로 — 옅은 남색 바탕(`--skx-border-c1`)·남색 글자(`--skx-primary`)·알약 모서리. `.rs-head__main` 이 세로 flex 라 `align-self: flex-start` 로 글자 폭만 차지하게 한다. 질문(`h1.rs-head__question`)은 1rem → 1.1rem — 바로 아래 큰 진행 막대의 글줄(1rem 굵게)보다 한 단계 크게 두어 화면의 주인(질문)이 막대 글줄에 묻히지 않게 한다. 상태 배지(`.rs-status`)·kicker 는 큰 진행 막대의 단계 칩(`.rs-pbar__stage` — 0.55rem·`0.1rem 0.45rem`·알약, Task D4)과 같은 크기, 버튼 줄 간격은 단계 칩 사이(0.3rem)와 같게. 상태 배지는 머리에 그대로 둔다(spec — 끝나면 이것만 남는다). `.rs-head`(카드 바탕·그림자)와 상태별 색(`.rs-status--completed`·`--failed`·`--canceled`)은 그대로다.
- **옆 칸 카드 머리는 새 규칙 `.rs-col-side .rs-card__title` 로 좁힌다.** 공용 `.rs-card__title`(da80f23 :68-73)은 제자리에서 고치지 않는다 — 본문 카드(`SynthProgressCard.vue:6` 보고서 작성 현황, `[id].vue` 의 실패·취소·보고서 오류 카드 da80f23 :111·:119·:170, `PlanCard.vue:5`)와 연구 어시스턴트 부품(`ContinueResearchCard.vue:6`·`OutlineEditor.vue:5`·`ProposalSection.vue:5`·`ProposalStep.vue:24·28·76`)도 이 클래스를 쓴다. 옆 칸 안에서만 걸리는 것은 진행 패널(`ProgressPanel.vue:4`)·근거 장부(`EvidenceLedger.vue:8`) 둘이다 — 좁은 화면 B 의 옆 칸도 같은 `.rs-col-side` 라 함께 바뀐다.
- 옆 칸 두 머리를 같은 높이·글자로: 글자 0.75rem·줄높이 1.6(= 1.2rem 높이), 앞에 남색 세로 막대(`::before` — 인라인 블록이라 장부 머리(`.wk-ledger__head` 의 `align-items: baseline`, `work.css:76-81`)의 글자 기준선을 바꾸지 않는다).
- **`ResearchHeader.vue` 는 마크업 그대로** — 클래스만으로 입혀 고칠 것이 없다. `.rs-pbar*` 도 Task D4 가 이미 같은 칩 체계로 써서 이 Task 는 고치지 않는다(같은 선택자를 두 Task 가 정의하지 않는다).
- `research.css` 는 D2·D4·D5·L2·D7·L3 뒤다 — 머리 규칙은 앵커 글자(`.rs-head__main {` ~ `.rs-status {…}`, da80f23 :194-227)로, 새 규칙은 인쇄 앵커 바로 위(Task L3 의 `.rs-round__state` 블록 뒤)에 넣는다.
- 테스트는 없다(+0). 마무리 운영 확인(Task Z6 Step 3 항목 9)이 '본문 카드 제목(보고서 작성 현황·실패·취소·보고서 오류)과 연구 어시스턴트 단계 화면의 카드 제목은 그대로'를 본다.

**Files:**
- Modify: `frontend/assets/css/research.css`(머리 `.rs-head__main` ~ `.rs-status`, 인쇄 앵커 위 새 블록)

기준선: Task L5 뒤 수(계획 머리 '테스트 수 어림' 대로면 da80f23 기준 `43 files / 797` — Task L4 는 +11).

- [ ] **Step 1: 머리를 skx 칩·크기 체계로 입힌다**

`frontend/assets/css/research.css` — 머리(da80f23 :194-227). old:

```css
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
```

new:

```css
.rs-head__main {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}
/* kicker 는 skx 칩(옅은 남색 바탕), kicker·상태 배지는 큰 진행 막대의 단계 칩(.rs-pbar__stage)과 같은 크기 */
.rs-head__kicker {
  align-self: flex-start;
  margin: 0;
  padding: 0.1rem 0.5rem;
  font-size: 0.55rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-primary);
  background: var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}
/* 바로 아래 큰 진행 막대의 글줄(1rem)보다 한 단계 크게 — 화면의 주인인 질문이 막대 글줄에 묻히지 않게 */
.rs-head__question {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  line-height: 1.4;
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
```

- [ ] **Step 2: 옆 칸 카드 머리를 같은 높이·글자로 맞춘다**

`frontend/assets/css/research.css` — 인쇄 앵커 바로 위. old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 옆 칸 카드 머리(skx 토큰) ─────────────────────────── */
/* 옆 칸의 진행 패널·근거 장부 머리를 같은 높이·글자로 맞춘다. 공용 .rs-card__title 은 본문 카드(보고서 작성 현황·실패·취소·
   보고서 오류)와 연구 어시스턴트 부품도 쓰므로 고치지 않고 옆 칸 안으로 좁힌다(좁은 화면 B 의 옆 칸도 같은 .rs-col-side).
   앞 막대는 인라인 블록 — 장부 머리(.wk-ledger__head, baseline 정렬)의 글자 기준선을 바꾸지 않는다 */
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
  background: var(--skx-primary);
  border-radius: var(--skx-radius-pill);
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 3: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -nE "#[0-9a-fA-F]{3,6}\b|rgba?\(" assets/css/research.css`
Expected: (빈 출력 — 새 색값 없이 `--skx-*` 토큰만)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -n -A5 "^\.rs-card__title {" assets/css/research.css`
Expected: 여섯 줄 — `.rs-card__title {` · `  margin: 0;` · `  font-size: 0.8rem;` · `  font-weight: 700;` · `  color: var(--skx-ink);` · `}`(공용 규칙 본문이 da80f23 그대로 — 본문 카드 제목은 바뀌지 않는다. 줄 번호 앞자리는 Task D4 가 `.rs-page` 에 줄을 더해 da80f23 의 68 보다 뒤다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "^\.rs-col-side \.rs-card__title" assets/css/research.css`
Expected: `2`(머리 규칙과 앞 막대 `::before` — 옆 칸 안으로 좁힌 새 규칙만)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat HEAD -- frontend/components/research/ResearchHeader.vue frontend/components/research/ProgressPanel.vue frontend/components/work/EvidenceLedger.vue`
Expected: (빈 출력 — 마크업은 그대로, CSS 만 입혔다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Task L5 뒤와 같은 수(+0 — 계획 머리 '테스트 수 어림' 대로면 da80f23 기준 `Test Files 43 passed (43)` / `Tests 797 passed (797)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

- [ ] **Step 4: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 연구 화면 머리·옆 칸을 skx 토큰으로 입힌다(spec §12-3 스타일 — 고치는 부품만). 머리의 '딥리서치' kicker 를 skx 칩(옅은 남색 바탕·알약)으로, 질문을 1.1rem 으로 키워 큰 진행 막대 글줄보다 한 단계 크게 두고, kicker·상태 배지·버튼 줄 간격을 진행 막대의 단계 칩과 같은 크기 체계로 맞춘다. 옆 칸의 진행 패널·근거 장부 머리는 새 규칙(.rs-col-side .rs-card__title)으로 같은 높이·글자에 남색 앞 막대를 단다 — 공용 .rs-card__title 은 본문 카드·연구 어시스턴트 부품도 쓰므로 고치지 않는다. 새 색값 없이 --skx-* 토큰만, 마크업은 그대로, skx 검색바는 넣지 않는다(대회 뒤)"
```

---

### 파트 메모 — 계획이 정한 세부

인터페이스(파일·공개 이름·시그니처·모양·DOM id·클래스)는 계획 머리 '공통 계약' 과 각 Task 의 코드가 정본이다. 아래 '뼈대' 는 이 계획을 쓸 때 파트끼리 맞춘 초안(계획서에 들지 않는다)이고, 이 절은 그 초안이 정하지 않았거나 글이 달라진 곳과 까닭을 남긴다.

1. **`activeRoundKey` 의 회차 수 칸(Task D3).** 뼈대 §3-3 은 `${idx}:${rounds.length}:${마지막 회차 verdict ?? "open"}` 이다. 이 파트는 `Math.max(1, rounds.length)` 를 쓴다 — 하위질문이 막 돌기 시작한 때(회차 없음 → 뼈대 열쇠 `k:0:open`)와 첫 검색 이벤트가 온 때(1회차·판정 없음 → `k:1:open`)는 같은 열린 회차인데, 뼈대 글자대로면 열쇠가 바뀌어 `roundSeenAt` 이 다시 잡히고 그때까지 쌓인 다가감이 0 으로 돌아가 막대가 뒤로 간다. 함수 이름·시그니처·'회차가 늘거나 판정이 날 때만 바뀐다'는 뜻은 그대로다(테스트 `searched === started` 가 고정).
2. **`progressInset` 은 막대의 높이를 쓴다(Task D5).** 뼈대 §4 D5 는 `.rs-pbar` 의 `getBoundingClientRect().bottom` 이다. 돌아온 화면은 맞추기 전에 맨 위로 올라가 있어(`useRestorePosition.ts:200`) 그 순간 막대는 머리 아래 제자리에 있고, `bottom` 은 머리 높이까지 더한 값이라 돌아온 칩이 막대 아래로 머리 높이만큼 더 내려간다. 맞춘 뒤에는 막대가 화면 맨 위(top 0)에 붙어 가리는 것은 막대 높이뿐이므로 `getBoundingClientRect().height` 를 넘긴다. `insetTargetTop` 의 이름·시그니처·뜻('inset 은 막대가 가리는 높이')은 그대로다. 선택자는 `.rs-page .rs-pbar` 로 좁혔다.
3. **`jumpToSection` 의 `follow.pause()` 자리(Task D7).** 뼈대는 '첫 줄'이다. 이 파트는 `if (!el) return;` 뒤에 둔다 — 옮길 절이 DOM 에 없어 아무 데도 가지 않은 누름이 따라가기만 끄고 알약을 띄우지 않게.
4. **`useSectionFollow` 는 처음 본 대상을 기준으로만 삼는다(Task D7 — 뼈대에 없는 규칙).** 연구 화면을 연 순간(새로고침·사이드바로 들어옴)의 대상으로 곧바로 끌고 내려가지 않고 다음 바뀜부터 옮긴다 — 첫 감시 호출(서버 렌더 포함)이 `document` 를 보지 않는 효과도 있다. 알약(`resume`)으로 다시 켠 이동은 사용자가 누른 것이라 막힘(`isBlocked`)을 보지 않는다. 공개 모양(`SectionFollow`·`useSectionFollow(opts)`)은 뼈대 그대로다.
5. **키 입력의 `editable` 범위(Task D7).** 뼈대 `FollowInput` 의 `editable` 을 '입력칸'보다 넓게 — `input, textarea, select, [contenteditable], [role='menu'], [role='listbox'], [role='dialog']` 안에서 누른 키로 본다(그 안의 방향키·Space 는 페이지를 굴리지 않는다 — 인용 팝오버·다운로드 메뉴·온보딩 모달). 초점이 간 버튼(`button, [role='button'], summary`) 위의 Space 도 `editable` 로 본다. 또 모달(`[aria-modal='true']` — 원문 뷰어·온보딩)이 문서에 있는 동안의 입력은 휠·터치까지 멈춤으로 보지 않는다 — 모달 안의 휠·터치와 버튼 위 Space 는 페이지를 굴리지 않는다. `breaksFollow` 의 규칙·테스트는 뼈대 그대로다(거르는 것은 composable 의 `onInput`·`inputOf`).
6. **`useRestorePosition` 의 import 에서 `targetTop` 을 뺀다(Task D5).** 뼈대 §4 D5 는 `insetTargetTop` 을 더한다고만 적었다. `:150` 을 바꾸면 `targetTop` 을 부르는 곳이 남지 않아(안에서 `insetTargetTop` 이 부른다) 쓰지 않는 import 를 걷는다.
7. **Task D4 는 커밋 하나다**(뼈대 '1~2'). CSS 옮김과 부품·연결이 서로 없으면 화면이 깨지는(막대 없이 카드 막대만 사라지거나, 막대가 두 개 서는) 한 덩어리라 나누지 않았다. 부품의 채움 폭은 템플릿 식 대신 `width` computed(같은 값 — `Math.round(fraction × 1000) / 10`)로 둔다.
8. **Task D8 은 `.rs-pbar*` 를 고치지 않는다**(뼈대 '`.rs-pbar*`(D4 블록 다듬기만)'). D4 가 처음부터 머리와 같은 칩 체계(0.55rem·`0.1rem 0.45rem`·알약)로 썼고, 같은 선택자를 두 Task 가 정의하지 않는 규칙에 맞춘다. D8 의 새 규칙은 뼈대대로 `.rs-col-side .rs-card__title`(와 그 `::before`) 하나다.
9. **`--rs-bar-h` 값**은 뼈대 그대로(`5.6rem`·768px 이하 `5.2rem`)다 — 실제 글자 크기(단계 칩 ≈1.1rem + 글줄 ≈1.5rem + 막대 1rem/0.75rem + 간격 0.7rem)를 세로 가운데에 두고 위아래 ≈0.65rem 이 남는다. 768px 이하에서는 막대 좌우 안쪽 여백도 `1.2rem` → `0.8rem` 으로 줄인다(같은 `.rs-pbar` 블록 안 — 뼈대에 없는 작은 덧붙임).

---

## 파트 L — 탐색 중 움직임 — 절 자리·근거 수집 단계·검토 중 더미·이해한 질문 바인딩

spec §12-3 '진행 화면(D22)' 표 가운데 이 파트가 덮는 행: **탐색 중 절 자리**(순수 함수 Task L1, 부품·연결 Task L2 — 정함 8·9) · **근거가 떨어져 들어옴·근거 수집 단계**(회차 미세 상태 Task L3 — 정함 12, 장부 배치 Task L5 — 정함 10) · **탐색 후보 '검토 중' 더미(Q9)**(이벤트 타입·리듀서 Task L4 — 정함 11, 장부 묶음·움직임 Task L5) · §12-2·§12-5 **"이렇게 이해했어요" 바인딩 두 곳**(Task L6 — 06c 가 dev 에 머지된 뒤에만 하는 선행 조건 Task). §12-7 06d vitest 의 '절 자리와 headings 대응'(L1)·'회차 미세 상태 라벨'(L3)·'탐색 후보 더미'(L4·L5) 항목과 'researchDraft 그대로'(L1 확인)도 여기서 본다.

실행 순서는 파트 D 와 엇갈린다: … D5 → **L1 → L2** → D6 → D7 → **L3 → L4 → L5** → D8 → N1 … N7 → **L6**(06c dev 머지 뒤) → N8. 기대 테스트 수는 모두 'Task 앞 수 + N' 이다(앞 Task 를 이 순서로 마쳤을 때). `[id].vue`·`research.css`·`researchEvents.ts`·`researchEvents.test.ts` 는 앞 Task(D1·D2·D4·D5·D7, 이 파트의 앞 Task)가 먼저 고친 파일이라 자리는 모두 **앵커 글자(Edit 의 old)** 로 잡는다 — 줄 번호는 '(da80f23 :N)' 참고값이다. 06c 가 Task 0 전에 이미 dev 에 들어와 있었으면 `researchEvents.ts`·`types/research.ts`·`researchEvents.test.ts` 의 줄이 더 밀려 있지만 아래 앵커는 06c 가 고치지 않는 글자라 그대로 맞는다(그때 `researchEvents.test.ts` 의 수는 06c 의 7개만큼 크다).

> 이 파트의 코드·테스트·기대 출력은 da80f23 과 같은 코드의 사본(round06-spec worktree 사본)에 Task D1·D2 의 글을 먼저 넣은 뒤 이 파트의 글을 Task 순서대로 그대로 넣어 실측했다 — 각 Step 2 의 실패 수·메시지, Step 4 의 통과 수, `nuxi typecheck` 오류 0, `npm run build` 완료. L6 은 06c 계획의 화면 한 줄 Task(타입 칸 셋·`questionUsedFromSteps`·`understoodLine`·PlanCard prop·테스트 describe 셋)를 base 에서 딴 가지에 넣고 `git merge` 해 충돌 모양과 해결 뒤 수(115 + 7 = 122 — 검토 반영으로 Task L4 가 한 개 늘어 지금 글로는 116 + 7 = 123)를 쟀다. 검토 반영(파트 끝) 뒤에는 고친 글의 코드 블록을 그대로 뽑아 새 사본에 파트 D 와 함께 Task 순서대로 다시 넣어 L1~L5 의 수·`nuxi typecheck`·`npm run build` 를 다시 쟀다.

---

### Task L1: 절 자리 순수 함수 `utils/planSlots.ts`

spec §12-3 '탐색 중 절 자리' 행 · §12-7 '절 자리와 headings 대응'. 승인 뒤(대기열·탐색·종합 첫 절 전) 본문에 하위질문마다 절 자리를 세울 재료를 순수 함수로 정한다 — 무엇을 그릴지(상태·라벨·절 번호 대응·새로 모인 자리·그리는 단계)는 여기서 vitest 로 보고, `.vue`(Task L2)는 그리기만 한다.

**알아 둘 것:**
- **하위질문 번호 ≠ 절 번호.** 워커는 근거가 있는 하위질문만 절로 쓴다(`synthesizer.py:535` `targets = [sq for sq in state.subquestions if sq.evidence_ids]`). 절 이벤트는 `subq_idx` 를 싣고(`:540` `info = {"subq_idx": sq.idx, "heading": sq.text, "headings": headings}`), 첫 절을 쓰기 시작할 때 절 제목 전부(`headings` = 하위질문 글, `:537`)를 싣는다. 그래서 `sectionOfSubq` 는 ① 받은 절의 `subqIdx` ② 아직 쓰지 않은 절은 `headings[i]` 를 계획 하위질문 글과 NFC·공백 정리 뒤 같은 글로 맞춘다. 자리의 key·id 는 하위질문 번호다(`slotElementId` = `rs-slot-{하위질문}` — Task D6 의 `followTarget` 이 이 이름을 읽는다).
- **종합 시작(`started`)과 대응을 앎(`mapped`)을 나눈다**(이 Task 가 정하는 자리 상태 규칙 — 테스트가 고정). 워커는 종합 단계를 열 때 result 없는 running step 이벤트를 먼저 보내고(`research_tasks.py:166`·`:666`) 절 제목은 첫 절 이벤트에서야 온다 — 그 사이 `synthFrom`(`researchEvents.ts:517-535`)이 `synth.status = "running"`·`headings = []` 를 만든다. 근거 0(`adopted === 0` — `runner.py:308` 의 `len(subq.evidence_ids)`)은 시작에서 접고, 근거 수를 모르는 옛 잡(`adopted === null`)은 대응을 안 뒤 절이 없을 때만 접는다. **`adopted > 0` 인 자리는 접지 않는다**(제목 맞춤이 빗나가도 '근거 없음'으로 잠깐 접혔다 펴지지 않게).
- **근거 0편으로 끝난 자리(종합 시작 전)는 상태 `collected` 그대로, 라벨은 `근거 0편`(✓ 없음)이고 튀어 오르지 않는다.** spec §12-3 은 '근거가 모이면 근거 N편 ✓'·'근거 0 자리는 종합이 시작되면 근거 없음으로 접는다' 라서 접는 시점은 spec 대로 종합 시작이다. 다만 그 전에 성공 표시(✓)와 축하 움직임(`newlyCollected` → `rs-pop`)을 내지 않는다 — 06b 기록에 과잉 제외 80~100% 질문이 있어 전부 무관 제외(`runner.py:308` `adopted = len(subq.evidence_ids)` = 0)가 운영에서 실제로 나온다.
- `round` 는 도는 하위질문의 `rounds.length` 인데 **회차가 아직 없으면 `null`**(하위질문 단계가 막 열려 검색 전) — 라벨이 '근거 수집 중 · 0회차'가 되지 않게 '근거 수집 중'으로 둔다(`subqStatusLabel` 이 `sq.rounds.length ?` 로 가르는 것과 같다).
- **(D6 품질 검토 반영) 탐색부터 다시 도는 재시도(stage=planned)에서 이번 시도가 아직 닿지 않은 하위질문은 대기다.** 재시도는 idx 0 부터 새 seq 로 search 행을 쌓고, `rebuild` 의 `latestBySubq` 는 아직 닿지 않은 하위질문에 이전 시도의 행(done·failed 와 그 근거 수·오류)을 남긴다. `planSlots` 는 `exploreAttemptStart(view.subqs)`·`fromEarlierAttempt(sq, since)`(`researchEvents.ts` — D3 품질 검토 반영 8b34f58 이 `stopPoint`·`researchProgress` 에 쓴 규칙)로 그 행을 상태 `pending`·근거 수 `null` 로 보고 자리 상태를 정한다 — 처음 계획대로면 1차 시도가 [근거 4편·근거 2편·실패]로 끝난 잡을 다시 시도할 때 새 하위질문 0 이 근거 수집 중인 동안 자리 1·2 가 '근거 2편 ✓'·'오류'로 서고, 같은 화면의 큰 진행 막대는 그 자리를 대기로 보아 서로 다른 말을 했다. 테스트 `planSlots.test.ts` 13 → 14.
- `draftReport`·`draftSlots`(`utils/researchDraft.ts`)·`tests/unit/researchDraft.test.ts` 는 고치지 않는다(spec). 이 파일은 `view` 를 읽기만 한다(테스트가 고정).
- 이름은 공통 계약('새 파일과 공개 이름' 표의 `utils/planSlots.ts` 행) 그대로 이 파일만 내보낸다 — `synthCard.ts` 의 `slotStateLabel`·`newlyFinished` 와 이름이 다르다(Nuxt 자동 import 충돌 없음).

**Files:**
- Create: `frontend/utils/planSlots.ts`
- Test: Create `frontend/tests/unit/planSlots.test.ts`

기준선: Task D5 뒤 수.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

Create `frontend/tests/unit/planSlots.test.ts`:

```ts
// frontend/tests/unit/planSlots.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchJob, ResearchView, RoundView, SubqView, SynthSectionView, SynthView } from "~/types/research";
import {
  newlyCollected,
  planSlotLabel,
  planSlots,
  sectionOfSubq,
  showsPlanSlots,
  slotElementId,
  type PlanSlot,
} from "~/utils/planSlots";
import { initialResearchView } from "~/utils/researchEvents";

const TITLES = ["효과 측정", "교사 인식", "정책 과제"];

function job(over: Partial<ResearchJob> = {}): ResearchJob {
  return {
    job_id: "11111111-1111-4111-8111-111111111111",
    question: "AI 윤리 교육의 효과",
    status: "running",
    stage: "planned",
    plan: TITLES,
    report: null,
    last_error: null,
    steps: [],
    ...over,
  };
}

function round(n: number, over: Partial<RoundView> = {}): RoundView {
  return {
    round: n, query: `질의 ${n}`, foundChunks: 10, newPapers: 3, verdict: "insufficient", note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [], ...over,
  };
}

function subq(idx: number, over: Partial<SubqView> = {}): SubqView {
  return {
    idx, title: TITLES[idx] ?? `하위질문 ${idx + 1}`, seq: idx + 1, status: "done", rounds: [round(1)],
    verdict: "sufficient", note: "", adopted: 3, parseFailed: false, error: null, ...over,
  };
}

function sec(idx: number, status: SynthSectionView["status"], over: Partial<SynthSectionView> = {}): SynthSectionView {
  return { idx, status, subqIdx: idx, heading: null, startedAt: null, durationMs: null, section: null, ...over };
}

function synthOf(over: Partial<SynthView> = {}): SynthView {
  return { seq: null, status: null, total: 0, sections: [], headings: [], evidence: {}, retiredSeq: null, ...over };
}

function viewWith(subqs: SubqView[], synth: Partial<SynthView> = {}): ResearchView {
  return { ...initialResearchView(job()), subqs, synth: synthOf(synth) };
}

function slot(subqIdx: number, state: PlanSlot["state"], over: Partial<PlanSlot> = {}): PlanSlot {
  return { subqIdx, title: TITLES[subqIdx] ?? "", state, adopted: 3, round: null, sectionIdx: null, ...over };
}

describe("sectionOfSubq", () => {
  it("synth 이벤트의 subq_idx 를 먼저 쓴다", () => {
    // 절 0 은 하위질문 0, 절 1 은 하위질문 2(하위질문 1 은 근거가 없어 절이 되지 않았다)
    const map = sectionOfSubq(synthOf({ sections: [sec(0, "done", { subqIdx: 0 }), sec(1, "running", { subqIdx: 2 })] }), TITLES);
    expect([...map]).toEqual([[0, 0], [2, 1]]);
    // 절 제목이 다른 하위질문의 글과 같아도 절 이벤트가 실은 하위질문 번호가 이긴다
    const disagree = sectionOfSubq(
      synthOf({ headings: ["효과 측정"], sections: [sec(0, "running", { subqIdx: 1 })] }),
      TITLES,
    );
    expect([...disagree]).toEqual([[1, 0]]);
  });

  it("subq_idx 를 모르면 headings 를 계획 하위질문 글과 공백 정리 뒤 맞춘다", () => {
    // 절 이벤트에 subq_idx 가 없는(옛 콜백) 절과 아직 쓰기 시작하지 않은 절 — 제목 글로만 맞춘다. 조합형(NFD) 글도 같은 글이다
    const map = sectionOfSubq(
      synthOf({
        headings: ["  효과   측정 ", "정책\n과제".normalize("NFD")],
        sections: [sec(0, "running", { subqIdx: null })],
      }),
      TITLES,
    );
    expect([...map]).toEqual([[0, 0], [2, 1]]);
  });

  it("근거 0 하위질문은 절이 되지 않아 하위질문 번호와 절 번호가 어긋난다", () => {
    const map = sectionOfSubq(synthOf({ headings: ["효과 측정", "정책 과제"] }), TITLES);
    expect(map.get(0)).toBe(0);
    expect(map.has(1)).toBe(false);
    expect(map.get(2)).toBe(1);
  });
});

describe("planSlots", () => {
  it("하위질문마다 자리를 만들고 key 는 하위질문 번호다 — 대기·근거 수집 중(회차)·근거 N편", () => {
    const v = viewWith([
      subq(0, { adopted: 4 }),
      subq(1, { status: "running", rounds: [round(1), round(2, { verdict: null })], verdict: "insufficient", adopted: 2 }),
      subq(2, { status: "pending", seq: null, rounds: [], verdict: null, adopted: null }),
    ]);
    expect(planSlots(v)).toEqual([
      { subqIdx: 0, title: "효과 측정", state: "collected", adopted: 4, round: null, sectionIdx: null },
      { subqIdx: 1, title: "교사 인식", state: "collecting", adopted: 2, round: 2, sectionIdx: null },
      { subqIdx: 2, title: "정책 과제", state: "waiting", adopted: null, round: null, sectionIdx: null },
    ]);
    // 하위질문 단계가 막 열려 회차가 아직 없으면 회차를 적지 않는다
    expect(planSlots(viewWith([subq(0, { status: "running", rounds: [], adopted: null })]))[0]!.round).toBeNull();
  });

  it("종합이 시작되면 근거 0 자리는 '근거 없음'으로 접는다", () => {
    const v = viewWith(
      [subq(0, { adopted: 4 }), subq(1, { adopted: 0 }), subq(2, { adopted: 3 })],
      { seq: 9, status: "running", total: 2, headings: ["효과 측정", "정책 과제"], sections: [sec(0, "running", { subqIdx: 0 })] },
    );
    expect(planSlots(v).map((s) => [s.subqIdx, s.state, s.sectionIdx])).toEqual([
      [0, "writing", 0],
      [1, "empty", null],
      [2, "collected", 1],
    ]);
    // 근거 수를 모르는 옛 잡(adopted null)은 대응을 알게 된 뒤에도 절이 없으면 접는다
    const legacy = viewWith(
      [subq(0, { adopted: null }), subq(1, { adopted: null })],
      { seq: 9, status: "running", total: 1, headings: ["효과 측정"], sections: [sec(0, "running", { subqIdx: 0 })] },
    );
    expect(planSlots(legacy).map((s) => s.state)).toEqual(["writing", "empty"]);
  });

  it("종합 단계가 열렸지만 절 제목이 아직 없으면 근거를 모은 자리는 접지 않는다 — 근거 0 자리만 접는다", () => {
    // 워커가 종합 단계를 열고(결과 없는 running 단계 이벤트) 첫 절 이벤트를 보내기 전 — 대응을 아직 모른다
    const v = viewWith(
      [subq(0, { adopted: 4 }), subq(1, { adopted: 0 }), subq(2, { adopted: null })],
      { seq: 9, status: "running", headings: [], sections: [] },
    );
    expect(planSlots(v).map((s) => s.state)).toEqual(["collected", "empty", "collected"]);
  });

  it("종합 중 첫 절 전에는 쓰는 절의 자리를 '작성 중'으로 둔다", () => {
    // 하위질문 0 은 근거가 없어 절 0 이 하위질문 1 이다. 절 이벤트가 subq_idx 를 싣지 않아도 절 제목으로 맞춘다
    const v = viewWith(
      [subq(0, { adopted: 0 }), subq(1, { adopted: 2 }), subq(2, { adopted: 5 })],
      { seq: 9, status: "running", total: 2, headings: ["교사 인식", "정책 과제"], sections: [sec(0, "running", { subqIdx: null })] },
    );
    expect(planSlots(v).map((s) => [s.state, s.sectionIdx])).toEqual([
      ["empty", null],
      ["writing", 0],
      ["collected", 1],
    ]);
  });

  it("실패한 하위질문은 오류, 하위질문이 없으면 빈 목록", () => {
    const v = viewWith([subq(0), subq(1, { status: "failed", adopted: null, error: "시간 상한" })]);
    expect(planSlots(v).map((s) => s.state)).toEqual(["collected", "failed"]);
    expect(planSlots(viewWith([]))).toEqual([]);
  });

  it("받은 화면 상태(view)를 고치지 않는다", () => {
    const v = viewWith(
      [subq(0), subq(1, { status: "running", rounds: [round(1)] }), subq(2, { adopted: 0 })],
      { seq: 9, status: "running", headings: ["효과 측정"], sections: [sec(0, "running")] },
    );
    const before = JSON.stringify(v);
    planSlots(v);
    expect(JSON.stringify(v)).toBe(before);
  });
});

describe("planSlotLabel", () => {
  it("상태마다 짧은 글 — 대기·근거 수집 중 · n회차·근거 N편 ✓·이 절을 쓰는 중·근거 없음·오류", () => {
    expect(planSlotLabel(slot(0, "waiting", { adopted: null }))).toBe("대기");
    expect(planSlotLabel(slot(0, "collecting", { round: 2 }))).toBe("근거 수집 중 · 2회차");
    expect(planSlotLabel(slot(0, "collecting", { round: null }))).toBe("근거 수집 중");
    expect(planSlotLabel(slot(0, "collected", { adopted: 4 }))).toBe("근거 4편 ✓");
    expect(planSlotLabel(slot(0, "collected", { adopted: null }))).toBe("근거 수집 완료");
    // 근거 0편으로 끝난 자리(종합 시작 전)는 성공 표시(✓)를 달지 않는다
    expect(planSlotLabel(slot(0, "collected", { adopted: 0 }))).toBe("근거 0편");
    expect(planSlotLabel(slot(0, "writing", { sectionIdx: 0 }))).toBe("이 절을 쓰는 중");
    expect(planSlotLabel(slot(0, "empty", { adopted: 0 }))).toBe("근거 없음");
    expect(planSlotLabel(slot(0, "failed", { adopted: null }))).toBe("오류");
  });
});

describe("newlyCollected", () => {
  it("직전 상태와 견줘 이번에 근거 수집을 마친 자리만 — 처음 그릴 때는 없다", () => {
    const slots = [slot(0, "collected"), slot(1, "collected"), slot(2, "collecting", { round: 1 })];
    expect(newlyCollected(null, slots)).toEqual([]);
    const prev = new Map<number, PlanSlot["state"]>([[0, "collecting"], [1, "collected"], [2, "waiting"]]);
    expect(newlyCollected(prev, slots)).toEqual([0]);
    expect(newlyCollected(new Map([[0, "collected"], [1, "collected"], [2, "collecting"]]), slots)).toEqual([]);
    // 근거 0편으로 끝난 자리는 튀어 오르지 않는다
    expect(newlyCollected(new Map([[0, "collecting"]]), [slot(0, "collected", { adopted: 0 })])).toEqual([]);
  });
});

describe("showsPlanSlots", () => {
  it("대기열·탐색 중·종합 첫 절 전에만 그린다", () => {
    expect(showsPlanSlots("queued", false)).toBe(true);
    expect(showsPlanSlots("exploring", false)).toBe(true);
    expect(showsPlanSlots("synthesizing", false)).toBe(true);
    expect(showsPlanSlots("synthesizing", true)).toBe(false);
    for (const p of ["planning", "awaiting", "completed", "failed", "canceled"] as const) {
      expect(showsPlanSlots(p, false)).toBe(false);
    }
    expect(showsPlanSlots(null, false)).toBe(false);
  });
});

describe("slotElementId", () => {
  it("자리 id 는 rs-slot-{하위질문 번호}", () => {
    expect(slotElementId(0)).toBe("rs-slot-0");
    expect(slotElementId(5)).toBe("rs-slot-5");
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/planSlots.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  no tests` — `Error: Cannot find module '~/utils/planSlots' imported from '…/frontend/tests/unit/planSlots.test.ts'.`(파일이 아직 없다)

- [ ] **Step 3: 구현한다**

Create `frontend/utils/planSlots.ts`:

```ts
// frontend/utils/planSlots.ts
// 탐색 중 절 자리 — 승인 뒤(대기열·탐색·종합 첫 절 전) 본문에 하위질문마다 세우는 보고서 자리의 상태.
// 하위질문 번호와 절 번호는 다르다: 근거가 없는 하위질문은 절이 되지 않는다(synthesizer.py — 종합 대상은 evidence_ids 가
// 있는 하위질문). 그래서 자리는 하위질문 번호로 세우고, 절 번호는 종합 이벤트(절의 subq_idx, 없으면 절 제목 = 하위질문 글)로
// 맞춘다. 화면 상태(view)만 읽는다 — 초안(draftReport·draftSlots)은 건드리지 않는다
import type { ResearchView, StepStatus, SynthView } from "~/types/research";
import type { ResearchPhase } from "~/utils/researchEvents";

export type PlanSlotState = "waiting" | "collecting" | "collected" | "writing" | "empty" | "failed";

export interface PlanSlot {
  // key·자리 id 의 번호 — 하위질문 번호다(절 번호가 아니다)
  subqIdx: number;
  // 하위질문 글
  title: string;
  state: PlanSlotState;
  // 근거 편수(SubqView.adopted) — 근거 수를 모르는 옛 잡은 null
  adopted: number | null;
  // collecting 일 때 지금 회차(회차가 아직 없으면 null), 아니면 null
  round: number | null;
  // 종합 이벤트로 알게 된 절 번호 — 근거 0 이거나 아직 모르면 null
  sectionIdx: number | null;
}

export function slotElementId(subqIdx: number): string {
  return `rs-slot-${subqIdx}`;
}

// 절 제목(하위질문 글)과 계획 하위질문 글을 견주는 꼴 — 조합형·완성형 차이와 공백 차이를 지운다
function sameText(s: string): string {
  return s.normalize("NFC").trim().replace(/\s+/g, " ");
}

// 하위질문 번호 → 절 번호. ① 절 이벤트가 실은 subq_idx(쓰기 시작한 절) ② 남은 절은 절 제목 목록(headings — 첫 절을
// 쓰기 시작할 때 전부 온다)을 계획 하위질문 글과 같은 글로 맞춘다. titles[i] = 하위질문 i 의 글
export function sectionOfSubq(synth: SynthView, titles: readonly string[]): Map<number, number> {
  const out = new Map<number, number>();
  const taken = new Set<number>();
  for (const s of synth.sections) {
    if (s.subqIdx === null || out.has(s.subqIdx) || taken.has(s.idx)) continue;
    out.set(s.subqIdx, s.idx);
    taken.add(s.idx);
  }
  synth.headings.forEach((heading, idx) => {
    if (taken.has(idx)) return;
    const key = sameText(heading);
    if (!key) return;
    const subqIdx = titles.findIndex((t, i) => !out.has(i) && sameText(t) === key);
    if (subqIdx < 0) return;
    out.set(subqIdx, idx);
    taken.add(idx);
  });
  return out;
}

export function planSlots(view: ResearchView): PlanSlot[] {
  const { synth } = view;
  // 종합 시작 = 종합 단계가 열렸다. 대응을 앎 = 절 제목이나 절 이벤트가 하나라도 왔다 — 워커는 종합 단계를 열 때 결과 없는
  // 단계 이벤트를 먼저 보내고 절 제목은 첫 절 이벤트에서야 오므로, 그 사이는 시작했지만 대응을 모른다
  const started = synth.status !== null || synth.headings.length > 0;
  const mapped = synth.headings.length > 0 || synth.sections.length > 0;
  const size = view.subqs.reduce((n, sq) => Math.max(n, sq.idx + 1), 0);
  const titles = Array.from({ length: size }, (_, i) => view.subqs.find((sq) => sq.idx === i)?.title ?? "");
  const sectionOf = sectionOfSubq(synth, titles);
  return view.subqs.map((sq) => {
    const sectionIdx = sectionOf.get(sq.idx) ?? null;
    const writing = sectionIdx !== null && synth.sections.some((s) => s.idx === sectionIdx && s.status === "running");
    return {
      subqIdx: sq.idx,
      title: sq.title,
      state: slotState(sq.status, sq.adopted, sectionIdx, writing, started, mapped),
      adopted: sq.adopted,
      round: sq.status === "running" && sq.rounds.length ? sq.rounds.length : null,
      sectionIdx,
    };
  });
}

// 근거 0(adopted 0)은 절이 되지 않으므로 종합이 시작되면 접는다. 근거 수를 모르는 옛 잡은 대응을 알게 된 뒤 절이 없을 때만
// 접는다. 근거를 모은 자리(adopted > 0)는 대응을 몰라도(제목 맞춤이 빗나가도) 접지 않는다 — 잠깐 '근거 없음'으로 접혔다가
// 다시 펼쳐지지 않게
function slotState(
  status: StepStatus,
  adopted: number | null,
  sectionIdx: number | null,
  writing: boolean,
  started: boolean,
  mapped: boolean,
): PlanSlotState {
  switch (status) {
    case "failed":
      return "failed";
    case "running":
      return "collecting";
    case "pending":
      return "waiting";
    case "done":
      if (writing) return "writing";
      if (started && adopted === 0) return "empty";
      if (mapped && adopted === null && sectionIdx === null) return "empty";
      return "collected";
  }
}

export function planSlotLabel(slot: PlanSlot): string {
  switch (slot.state) {
    case "waiting":
      return "대기";
    case "collecting":
      return slot.round !== null ? `근거 수집 중 · ${slot.round}회차` : "근거 수집 중";
    case "collected":
      // 근거 0편으로 끝난 자리는 성공 표시(✓)를 달지 않는다 — 종합이 시작되면 '근거 없음'으로 접힌다
      if (slot.adopted === null) return "근거 수집 완료";
      return slot.adopted > 0 ? `근거 ${slot.adopted}편 ✓` : "근거 0편";
    case "writing":
      return "이 절을 쓰는 중";
    case "empty":
      return "근거 없음";
    case "failed":
      return "오류";
  }
}

// 직전 상태와 견줘 이번에 근거 수집을 마친 자리(하위질문 번호). 처음 그릴 때(prev 가 null)는 없다 — 다시 연 화면에서 이미
// 모은 자리가 한꺼번에 튀어 오르지 않게(움직임은 실제 이벤트가 올 때만 — synthCard.newlyFinished 와 같은 규칙).
// 근거 0편으로 끝난 자리는 튀어 오르지 않는다(모은 것이 없다)
export function newlyCollected(prev: ReadonlyMap<number, PlanSlotState> | null, slots: readonly PlanSlot[]): number[] {
  if (!prev) return [];
  return slots
    .filter((s) => s.state === "collected" && s.adopted !== 0 && prev.get(s.subqIdx) !== "collected")
    .map((s) => s.subqIdx);
}

// 절 자리를 그리는 단계 — 승인 뒤 대기열·탐색 중, 종합 중이면 첫 절이 완성되기 전(초안이 생기면 초안이 그 자리에 선다)
export function showsPlanSlots(phase: ResearchPhase | null, hasDraft: boolean): boolean {
  return phase === "queued" || phase === "exploring" || (phase === "synthesizing" && !hasDraft);
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/planSlots.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  13 passed (13)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchDraft.test.ts`
Expected: `Tests  23 passed (23)` — 초안 테스트는 그대로다(파일을 고치지 않았다, spec §12-7)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: 실패 0 — `Test Files` 는 Task D5 뒤 수 + 1(새 파일), `Tests` 는 Task D5 뒤 수 + 13

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend/utils/researchDraft.ts frontend/tests/unit/researchDraft.test.ts`
Expected: (빈 출력)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/planSlots.ts frontend/tests/unit/planSlots.test.ts && git status --short && git commit -m "[Feat] round06d — 탐색 중 하위질문별 절 자리의 상태·절 번호 대응을 정하는 순수 함수(planSlots)를 더한다. 자리는 하위질문 번호로 세운다 — 근거 0 하위질문은 절이 되지 않아 하위질문 번호와 절 번호가 어긋나므로, 절 이벤트의 subq_idx 를 먼저 쓰고 남은 절은 절 제목(headings = 하위질문 글)을 NFC·공백 정리 뒤 계획 하위질문 글과 맞춘다. 상태는 대기·근거 수집 중(n회차)·근거 N편 ✓·이 절을 쓰는 중·근거 없음·오류이고, 근거 0 자리는 종합이 시작되면 접되 근거를 모은 자리는 첫 절 제목이 오기 전에도 접지 않는다. 근거 0편으로 끝난 자리는 접히기 전에도 ✓ 없이 '근거 0편'이고 튀어 오르지 않는다. 그리는 단계는 대기열·탐색 중·종합 첫 절 전. 초안(draftReport·draftSlots)은 건드리지 않는다"
```

---

### Task L2: 탐색 중 절 자리 부품 `ReportSkeleton.vue`·연구 화면 연결

spec §12-3 '탐색 중 절 자리' 행(정함 8 — 새 `ReportSkeleton.vue`, ReportView 자리 모드 아님) · §12-11 '탐색 중 읽기 전용 PlanCard 를 절 자리가 대신할지·옆 칸 폭'(**정함(권고)** 정함 9 — 대신한다, 옆 칸 폭 17rem 그대로) · '글이 나타나는 방식'(타자 효과 없음 — 바꾸지 않음). 실행 202초 가운데 탐색 111초 동안 본문이 읽기 전용 PlanCard 하나뿐이던 자리에, 하위질문마다 절 자리를 세워 근거가 모일 때마다 '근거 N편 ✓'이 찍히게 한다.

**알아 둘 것:**
- **부품은 새 파일이다(정함 8).** ReportView 는 최종본·초안 두 모드와 제외 목록·인용칩 주입을 이미 품고, `draftReport`·`draftSlots` 를 건드리지 않는다는 제약(spec)과도 맞는다. 자리 머리에는 절 번호 'N.' 대신 작은 '하위질문 N'을 단다 — 근거 0 하위질문 때문에 둘이 어긋난다(`ReportView.vue:79-80` 제외 목록 묶음 번호와 같은 이유).
- **자리 `<section>` 은 `class="rs-section rs-slot"`** 이라 `.rs-section` 의 `scroll-margin-top: 1.2rem`·윤곽선 규칙을 함께 받고, 막대 높이는 D4 품질 검토 반영의 문서 `scroll-padding-top` 이 더한다 — Task D7 의 따라가기가 `#rs-slot-{하위질문}`(Task L1 `slotElementId`)으로 옮겨 와도 제목이 고정 막대 밑에 숨지 않는다. `tabindex="-1"` 은 ReportView 의 절(`:31`)과 같다.
- **'근거 N편 ✓' 튀어 오름**은 SynthProgressCard 의 `fresh`(`:78-97`)와 같은 방식이다 — `newlyCollected`(Task L1) + 900ms 타이머, 기존 `rs-pop` keyframes. 처음 그릴 때(다시 연 화면)는 `prev` 가 없어 움직이지 않는다(시연 정직성). 알림(aria-live)은 두지 않는다 — 같은 순간 근거 장부가 '근거 n편 채택'을 읽는다(`EvidenceLedger.vue:103-108`).
- **줄 모양(`.rs-skeleton` 3줄 — 기존 `research.css:1013-1031`, reduced-motion 이면 이미 멈춘다)** 은 아직 쓰이지 않은 자리(대기·근거 수집 중·작성 중)에만 둔다. 근거 없음은 점선 한 줄로 접고, 근거를 모은 자리는 상태 글이 대신한다. `research.css` 에 새 keyframes 를 더하지 않는다(마무리의 keyframes 수 확인 — 이 파트의 새 keyframes 는 Task L5 의 `work.css` `wk-review` 하나).
- **연구 화면 연결:** 탐색 중 읽기 전용 PlanCard(da80f23 `:97`)를 지우면 계획 블록(`<section v-if="phase !== 'completed'"`)이 탐색 중에 빈 섹션으로 남으므로 조건에서 `exploring` 도 뺀다(빈 `rs-block` 이 2단 본문 맨 위에 간격만 남기지 않게). 보고서 블록 조건에 `slotsShown` 을 더하고, `<template v-if="shownReport">` 다음·실패 카드 앞에 `ReportSkeleton` 분기를 둔다. `reportState` 는 `completed` 일 때만 값이 있어(`utils/researchReport.ts:114-118` `reportSlot`) 절 자리(대기열·탐색·종합 첫 절 전)와 겹치지 않고, 종합 중 첫 절이 완성되면 `draft` 가 생겨 `shownReport`(초안)가 같은 블록의 첫 분기로 선다 — 뒤의 실패·불러오는 중 카드는 그대로다.
- 좁은 화면(배치 B)은 계획(1) → 옆 칸(2) → 보고서 블록(3) 순(`research.css:42-50`)이라 절 자리는 진행 패널·장부 아래에 선다. 그대로 둔다.
- `focusScreenTitle`(`[id].vue:448-456`)이 찾는 `.rs-report__question` 을 자리 머리 h2 도 쓰지만, 그 함수는 단계(`?s=`)가 바뀔 때(끝난 잡)만 돌아 절 자리와 함께 설 일이 없다.
- `[id].vue` 는 D1·D2·D4·D5 가 먼저 고쳤다 — 아래 old 는 그 Task 들이 바꾸지 않는 글자다. 순수 함수 import 는 앵커 `import { SHOW_LAYOUT_TOGGLE, …"~/utils/researchLayout";`(D1 뒤에도 같은 글자) 바로 아래에 넣으므로 D4 가 그 아래에 넣은 `~/utils/researchProgress` import 바로 위에 선다.

**Files:**
- Create: `frontend/components/research/ReportSkeleton.vue`
- Modify: `frontend/pages/research/[id].vue`(import 두 줄 · 앵커 `const draft = computed(` 아래 computed 둘 · 계획 블록 조건 · 탐색 중 PlanCard 줄 지움 · 보고서 블록 조건 · ReportSkeleton 분기)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위에 `.rs-report--slots`·`.rs-slot*` 블록)

기준선: Task L1 뒤 수.

- [ ] **Step 1: 부품을 만든다**

Create `frontend/components/research/ReportSkeleton.vue`:

```vue
<!-- frontend/components/research/ReportSkeleton.vue -->
<template>
  <!-- 승인 뒤(대기열·탐색·종합 첫 절 전) 본문에 세우는 보고서의 자리. 하위질문마다 한 자리이고 근거가 모이면
       '근거 N편 ✓'을 찍는다. 자리 번호는 하위질문 번호다 — 근거가 없는 하위질문은 절이 되지 않아 절 번호와 다르므로
       'N.' 대신 작은 '하위질문 N'을 단다. 첫 절이 완성되면 이 자리 대신 초안(ReportView)이 선다.
       자리 id(rs-slot-N)는 지금 진행하는 곳 따라가기가 옮겨 오는 자리다 — rs-section 이라 고정 막대 밑 여백도 함께 받는다 -->
  <article class="rs-card rs-report rs-report--slots" aria-labelledby="rs-slots-title">
    <header class="rs-report__head">
      <div>
        <h2 id="rs-slots-title" class="rs-report__question">보고서 자리</h2>
        <p class="rs-muted">하위질문마다 근거를 모으면 그 자리에 절이 쓰입니다.</p>
      </div>
    </header>

    <section
      v-for="s in slots"
      :id="slotElementId(s.subqIdx)"
      :key="s.subqIdx"
      class="rs-section rs-slot"
      :class="`is-${s.state}`"
      tabindex="-1"
    >
      <p class="rs-slot__kicker">하위질문 {{ s.subqIdx + 1 }}</p>
      <h3 class="rs-section__heading">{{ s.title }}</h3>
      <span class="rs-slot__state" :class="{ 'is-fresh': fresh.includes(s.subqIdx) }">{{ planSlotLabel(s) }}</span>
      <!-- 아직 쓰이지 않은 자리만 줄 모양을 둔다. 근거 없음은 한 줄로 접고, 근거를 모은 자리는 상태 글이 대신한다 -->
      <div v-if="SKELETON_STATES.includes(s.state)" class="rs-skeleton" aria-hidden="true">
        <span class="rs-skeleton__line" />
        <span class="rs-skeleton__line" />
        <span class="rs-skeleton__line" />
      </div>
    </section>
  </article>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { newlyCollected, planSlotLabel, slotElementId, type PlanSlot, type PlanSlotState } from "~/utils/planSlots";

const props = defineProps<{ slots: PlanSlot[] }>();

const SKELETON_STATES: readonly PlanSlotState[] = ["waiting", "collecting", "writing"];
// '근거 N편 ✓'이 튀어 오르는 시간(research.css 의 rs-pop 과 맞춘다 — SynthProgressCard 와 같다)
const FRESH_MS = 900;

const fresh = ref<number[]>([]);
let prev: Map<number, PlanSlotState> | null = null;
let freshTimer: ReturnType<typeof setTimeout> | null = null;

// 효과는 실제 이벤트가 자리를 바꿨을 때만이다 — 처음 그릴 때(다시 연 화면)는 prev 가 없어 튀어 오르지 않는다
watch(
  () => props.slots,
  (slots) => {
    const idxs = newlyCollected(prev, slots);
    prev = new Map(slots.map((s) => [s.subqIdx, s.state]));
    if (!idxs.length) return;
    fresh.value = idxs;
    if (freshTimer) clearTimeout(freshTimer);
    freshTimer = setTimeout(() => {
      fresh.value = [];
    }, FRESH_MS);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (freshTimer) clearTimeout(freshTimer);
});
</script>
```

- [ ] **Step 2: 연구 화면에 잇는다**

`frontend/pages/research/[id].vue` — 부품 import(da80f23 :213-214). old:

```ts
import ReportPrint from "~/components/research/ReportPrint.vue";
import ReportView from "~/components/research/ReportView.vue";
```

new:

```ts
import ReportPrint from "~/components/research/ReportPrint.vue";
import ReportSkeleton from "~/components/research/ReportSkeleton.vue";
import ReportView from "~/components/research/ReportView.vue";
```

순수 함수 import(da80f23 :245 — D1 뒤에도 같은 글자. D4 의 `~/utils/researchProgress` import 가 이 줄 바로 아래에 있다). old:

```ts
import { SHOW_LAYOUT_TOGGLE, WIDE_MIN_PX, effectiveLayout, type ResearchLayout } from "~/utils/researchLayout";
```

new:

```ts
import { SHOW_LAYOUT_TOGGLE, WIDE_MIN_PX, effectiveLayout, type ResearchLayout } from "~/utils/researchLayout";
import { planSlots, showsPlanSlots } from "~/utils/planSlots";
```

절 자리 computed — 앵커 `const draft = computed(`(da80f23 :276) 바로 아래. old:

```ts
const draft = computed(() => (view.value && draftState.value ? draftReport(view.value) : null));
```

new:

```ts
const draft = computed(() => (view.value && draftState.value ? draftReport(view.value) : null));
// 승인 뒤 첫 절 전까지 본문에 세우는 하위질문별 절 자리 — 대기열·탐색 중·종합 첫 절 전에만 그리고, 첫 절이
// 완성되면(초안이 생기면) 초안이 그 자리에 선다. 자리는 하위질문 번호로 세운다(절 번호와 다르다 — utils/planSlots)
const planSlotList = computed(() => (view.value ? planSlots(view.value) : []));
const slotsShown = computed(() => showsPlanSlots(phase.value, !!draft.value));
```

(Task D7 이 `planSlotList` 를 `followTarget` 에 넘긴다 — 이름을 바꾸지 않는다.)

계획 블록 조건(da80f23 :79). old:

```html
            <section v-if="phase !== 'completed'" class="rs-block rs-block--plan">
```

new:

```html
            <!-- 탐색 중에는 계획 블록을 그리지 않는다 — 하위질문 목록·상태는 본문의 절 자리(ReportSkeleton)가 보인다 -->
            <section v-if="phase !== 'completed' && phase !== 'exploring'" class="rs-block rs-block--plan">
```

탐색 중 읽기 전용 PlanCard(da80f23 :97 — D2 가 대기열 카드에 줄을 더해 밀려 있다). old(이 한 줄과 줄끝):

```html
              <PlanCard v-else-if="phase === 'exploring'" :plan="view.plan" :max="maxSubquestions" :subqs="view.subqs" />
```

new: 빈 글 — 줄째 지운다. 뒤의 `<SynthProgressCard v-else-if="phase === 'synthesizing'"` 가 대기열 카드 바로 다음 분기가 된다. 승인 대기 PlanCard 는 그대로라 `PlanCard` import·`maxSubquestions` 는 계속 쓰인다.

보고서 블록 조건(da80f23 :126). old:

```html
            <section v-if="reportState || draft" class="rs-block rs-block--report">
```

new:

```html
            <section v-if="reportState || draft || slotsShown" class="rs-block rs-block--report">
```

절 자리 분기 — `<template v-if="shownReport">` 를 닫는 `</template>` 다음 줄의 실패 카드(da80f23 :169 — `phase === 'failed'` 카드와 글자가 달라 파일에 하나) 바로 위. old:

```html
              <div v-else-if="reportState === 'failed'" class="rs-card rs-card--error">
```

new:

```html
              <ReportSkeleton v-else-if="slotsShown" :slots="planSlotList" />
              <div v-else-if="reportState === 'failed'" class="rs-card rs-card--error">
```

- [ ] **Step 3: 자리 스타일을 더한다**

`frontend/assets/css/research.css` — 인쇄 앵커 바로 위(Task D7 의 `.rs-follow-pill`·Task L3 의 `.rs-round__state` 는 이 Task 뒤에 같은 앵커 위로 들어온다). old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 탐색 중 절 자리(ReportSkeleton) ────────────────────── */
/* 승인 뒤 첫 절 전까지 본문에 서는 하위질문별 자리. 자리 머리의 '하위질문 N'은 절 번호가 아니라 하위질문 번호다.
   근거를 모은 자리는 상태 글이 파랗게 '근거 N편 ✓', 근거 없음은 점선 한 줄로 접는다 */
.rs-report--slots {
  gap: 0.7rem;
}
.rs-slot {
  gap: 0.35rem;
  padding: 0.7rem 0.9rem;
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
}
.rs-slot__kicker {
  margin: 0;
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--skx-primary);
}
.rs-slot__state {
  align-self: flex-start;
  padding: 0.1rem 0.45rem;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-gray-1);
  background: var(--skx-white);
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-pill);
}
.rs-slot.is-collecting .rs-slot__state,
.rs-slot.is-collected .rs-slot__state,
.rs-slot.is-writing .rs-slot__state {
  color: var(--skx-primary);
  border-color: var(--skx-border-c2);
}
.rs-slot.is-failed .rs-slot__state {
  color: var(--skx-ink);
  border-color: var(--skx-ink);
}
.rs-slot.is-waiting .rs-section__heading {
  color: var(--skx-gray-2);
}
.rs-slot.is-empty {
  flex-direction: row;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.2rem 0.5rem;
  padding: 0.4rem 0.9rem;
  border-style: dashed;
}
.rs-slot.is-empty .rs-section__heading {
  font-size: 0.7rem;
  font-weight: 400;
  color: var(--skx-gray-2);
}
.rs-slot__state.is-fresh {
  animation: rs-pop 0.9s cubic-bezier(0.34, 1.56, 0.64, 1);
}
@media (prefers-reduced-motion: reduce) {
  .rs-slot__state.is-fresh {
    animation: none;
  }
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

(`.rs-section` 규칙(da80f23 :459·:985)보다 뒤에 있어 같은 선택자 세기에서 `.rs-slot` 의 `gap`·`border-radius` 가 이긴다. `.rs-slot__state` 는 flex 항목이라 `rs-pop` 의 transform 이 먹는다. 색은 모두 `--skx-*` 토큰 — Task D8 의 hex·rgba 없음 확인에 걸리지 않는다.)

- [ ] **Step 4: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: 실패 0 — Task L1 뒤와 같은 수(+0)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0` (`:slots="planSlotList"` 가 `PlanSlot[]` 로 맞는다 — 다른 값을 넘기면 `error TS2322: Type '…' is not assignable to type 'PlanSlot[]'` 로 잡히는 것을 사본에서 확인했다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "v-else-if=\"phase === 'exploring'\"" "frontend/pages/research/[id].vue"`
Expected: `0` (탐색 중 읽기 전용 PlanCard 가 없다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "^@keyframes" frontend/assets/css/research.css`
Expected: Task L2 앞과 같은 수(da80f23 `9` — 파트 D·L 은 `research.css` 에 keyframes 를 더하지 않는다)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/components/research/ReportSkeleton.vue "frontend/pages/research/[id].vue" frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 승인 뒤 본문에 하위질문별 절 자리를 세우고 근거가 모이면 '근거 N편 ✓'를 찍는다(ReportSkeleton). 대기열·탐색 중·종합 첫 절 전에 보고서 블록에 서고, 첫 절이 완성돼 초안이 생기면 초안이 그 자리를 잇는다. 자리 머리는 절 번호 대신 '하위질문 N' — 근거 0 하위질문은 절이 되지 않아 둘이 어긋난다. 근거 없음은 종합이 시작되면 한 줄로 접는다. 탐색 중 읽기 전용 PlanCard 는 지운다(§12-11 정함(권고) — 같은 목록·상태를 두 번 그리지 않는다, 옆 칸 폭 17rem 그대로). 자리는 rs-section 이라 고정 막대 밑 여백을 함께 받는다. 새 keyframes 없이 rs-pop·rs-shimmer 를 쓰고 움직임 줄이기면 멈춘다"
```

---

### Task L3: 회차 미세 상태 `roundStatusLabel`·진행 패널

spec §12-3 '근거가 떨어져 들어옴·근거 수집 단계' 행의 회차 줄 미세 상태(검색어가 있고 판정이 없으면 '자기점검 중', 다음 검색어가 있으면 '재검색 중') · §12-7 '회차 미세 상태 라벨' · 정함 12. 탐색 중 진행 패널의 회차 줄은 자기점검(LLM) 결과가 올 때까지 수십 초 동안 검색어 한 줄로 멈춰 보인다 — 지금 무엇을 하는지를 그 줄에 붙인다.

**알아 둘 것:**
- 회차는 `search` 이벤트에서 생기고(`applySearch` da80f23 `:376-388` — 검색어·대목 수, 판정 `null`) `critique` 가 판정·다음 검색어를 채운다(`applyCritique` `:390-420`). 그래서 마지막 회차가 '검색어 있음·판정 없음'이면 자기점검을 기다리는 중이고, 판정이 다음 검색어를 냈는데 다음 회차의 검색이 아직 안 왔으면 다시 찾는 중이다. 다음 검색이 오면 새 회차가 마지막이 되어 앞 회차의 '재검색 중'은 사라진다.
- 마지막 회차는 `rounds` 의 끝이다(`upsertRound`·`mergeRounds` 가 회차 번호 순으로 둔다 — `:624-631`). 견주기는 객체가 아니라 회차 번호로 한다 — 템플릿이 넘기는 `r` 은 같은 배열의 원소지만 테스트·다른 호출처가 따로 만든 회차를 넘겨도 맞게.
- **`subqStatusLabel` 은 그대로다(정함 12)** — 06c 파일 PlanCard(`PlanCard.vue:35`)도 읽고 기존 테스트(`researchEvents.test.ts:177` `'탐색 중 · 2회차'`)가 고정한다. 회차 줄에만 새 함수를 단다.
- '자기점검 중'만 점이 깜빡인다 — 템플릿이 `is-checking`(`r.verdict === null` — `roundStatusLabel` 이 '자기점검 중'을 주는 조건과 같은 칸)을 단다. 깜빡임은 기존 `rs-blink` keyframes(`.rs-badge--live::before` 선례, `research.css:976-983`)이고 reduced-motion 이면 멈춘다. 새 keyframes 없음.
- 타임라인은 live 영역이 아니다(진행 패널에서 읽히는 것은 강조 카드 `.rs-highlight` 하나 — `ProgressPanel.vue:33`). 새 칩도 `aria-live="off"` 로 두어 회차마다 읽지 않는다.
- `researchEvents.ts`·`researchEvents.test.ts` 는 D2 가 먼저 고쳤다(다시 내보내기 지움·`queueLine` import 를 `~/utils/queueLine` 으로). 아래 old 는 D2 가 바꾸지 않는 글자다. 새 describe 는 `queueLine` describe 의 끝(앵커) 바로 뒤에 넣는다 — 06c 가 Task 0 전에 dev 에 들어와 그 뒤에 06c 의 describe 가 있어도 그 앞에 끼어들 뿐 결과는 같다.

**Files:**
- Modify: `frontend/utils/researchEvents.ts`(앵커 `subqStatusLabel` 의 닫는 `}` 와 `export function synthProgress(` 사이 — da80f23 `:173-175`)
- Modify: `frontend/components/research/ProgressPanel.vue`(회차 줄 검색어 span `:63` 뒤, import `:124-133`)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위에 `.rs-round__state`)
- Test: `frontend/tests/unit/researchEvents.test.ts`(import 목록, `queueLine` describe 끝 뒤에 새 describe)

기준선: Task D7 뒤 수. `researchEvents.test.ts` 는 `102`(06c 가 Task 0 전에 dev 에 있었으면 `109`).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchEvents.test.ts` — import 목록. old:

```ts
  researchPhase,
  sectionGapToRecover,
```

new:

```ts
  researchPhase,
  roundStatusLabel,
  sectionGapToRecover,
```

같은 파일 — `queueLine` describe 의 끝(da80f23 `:1379-1381`) 뒤. old:

```ts
    expect(queueLine({ ahead: 1, etaSec: 0 })).toBe("앞에 1건 · 약 1분");
  });
});
```

new:

```ts
    expect(queueLine({ ahead: 1, etaSec: 0 })).toBe("앞에 1건 · 약 1분");
  });
});

describe("roundStatusLabel — 회차 줄 미세 상태", () => {
  const FIRST_SEARCH: ResearchEvent = { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 };
  const RECHECK: ResearchEvent = {
    kind: "critique", subq_idx: 0, verdict: "insufficient", note: "초등 대상 연구가 없다", adopted: 5,
    parse_failed: false, capped: 0, round: 1, next_query: "초등 AI 윤리 교육 효과", will_recheck: true,
  };

  it("도는 하위질문의 마지막 회차가 검색어만 있고 판정이 없으면 '자기점검 중'", () => {
    const first = run([SEARCH_STARTED, FIRST_SEARCH]).subqs[0]!;
    expect(roundStatusLabel(first, first.rounds[0]!)).toBe("자기점검 중");
    // 2회차 검색 뒤 점검을 기다리는 장면 — 마지막 회차(2회차)에만 단다
    const second = run(AWAITING_ROUND2_CRITIQUE).subqs[0]!;
    expect(second.rounds.map((r) => roundStatusLabel(second, r))).toEqual([null, "자기점검 중"]);
  });

  it("마지막 회차에 다음 검색어가 있으면 '재검색 중'", () => {
    const sq = run([SEARCH_STARTED, FIRST_SEARCH, RECHECK]).subqs[0]!;
    expect(roundStatusLabel(sq, sq.rounds[0]!)).toBe("재검색 중");
  });

  it("끝난 하위질문·앞 회차·판정이 난 마지막 회차(충분)는 null", () => {
    const enough = run([
      SEARCH_STARTED,
      FIRST_SEARCH,
      { ...RECHECK, verdict: "sufficient", note: "충분", next_query: null, will_recheck: false },
    ]).subqs[0]!;
    expect(roundStatusLabel(enough, enough.rounds[0]!)).toBeNull();
    // 끝난 하위질문 — 저장본 회차에 다음 검색어가 남아 있어도 적지 않는다
    const done = initialResearchView(job({
      steps: [PLAN_ROW, step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "done", result: { rounds: [ROUND1, ROUND2] } })],
    })).subqs[0]!;
    expect(done.rounds.map((r) => roundStatusLabel(done, r))).toEqual([null, null]);
    // 앞 회차 — 재검색을 낸 1회차는 2회차가 시작되면 적지 않는다
    const second = run(AWAITING_ROUND2_CRITIQUE).subqs[0]!;
    expect(roundStatusLabel(second, second.rounds[0]!)).toBeNull();
  });
});
```

(`SEARCH_STARTED`·`ROUND1`·`ROUND2`·`AWAITING_ROUND2_CRITIQUE`·`PLAN_ROW`·`run`·`job`·`step` 은 이 파일 머리의 기존 픽스처다 — da80f23 `:38-114`.)

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchEvents.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  3 failed | 102 passed (105)` — 새 it 셋이 모두 `TypeError: (0 , roundStatusLabel) is not a function`. 기존 102 는 통과한다(06c 가 먼저 들어와 있었으면 `3 failed | 109 passed (112)`).

- [ ] **Step 3: 구현한다**

`frontend/utils/researchEvents.ts` — `subqStatusLabel` 바로 뒤. old:

```ts
    case "failed":
      return "오류";
  }
}

export function synthProgress(
```

new:

```ts
    case "failed":
      return "오류";
  }
}

// 회차 줄의 미세 상태 — 도는 하위질문의 마지막 회차에만 단다. 검색어가 있고 판정이 아직 없으면 자기점검(LLM)을
// 기다리는 중이고, 판정이 다음 검색어를 냈으면 그 검색어로 다시 찾는 중이다(다음 회차의 검색이 오면 그 회차가 마지막이
// 된다). 끝난 하위질문·앞 회차·재검색 없이 판정이 난 회차는 적지 않는다. 하위질문 줄의 상태(subqStatusLabel)는
// PlanCard 도 읽으므로 그대로 두고 회차 줄에만 단다
export function roundStatusLabel(sq: SubqView, r: RoundView): string | null {
  if (sq.status !== "running") return null;
  const last = sq.rounds[sq.rounds.length - 1];
  if (!last || last.round !== r.round) return null;
  if (r.verdict === null && r.query) return "자기점검 중";
  if (r.nextQuery) return "재검색 중";
  return null;
}

export function synthProgress(
```

(`SubqView`·`RoundView` 는 이 파일 머리 import(da80f23 `:2-37`)에 이미 있다.)

`frontend/components/research/ProgressPanel.vue` — 회차 줄의 검색어 span(`:63`) 뒤. old:

```html
                <span class="rs-round__query">‘{{ r.query }}’</span>
```

new:

```html
                <span class="rs-round__query">‘{{ r.query }}’</span>
                <!-- 도는 하위질문의 마지막 회차에만 — 점검을 기다리는 중(점이 깜빡인다)·다음 검색어로 다시 찾는 중 -->
                <span
                  v-if="roundStatusLabel(sq, r)"
                  class="rs-round__state"
                  :class="{ 'is-checking': r.verdict === null }"
                  aria-live="off"
                >{{ roundStatusLabel(sq, r) }}</span>
```

같은 파일 import(`:124-133`). old:

```ts
  flaggedLabel,
  showsExcludedCounter,
```

new:

```ts
  flaggedLabel,
  roundStatusLabel,
  showsExcludedCounter,
```

`frontend/assets/css/research.css` — 인쇄 앵커 바로 위. old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 회차 줄 미세 상태 ──────────────────────────────────── */
/* 도는 하위질문의 마지막 회차 — '자기점검 중'(점검 LLM 을 기다린다, 점이 깜빡인다)·'재검색 중'(다음 검색어로 다시 찾는다) */
.rs-round__state {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0 0.4rem;
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--skx-primary);
  border: 1px solid var(--skx-border-c2);
  border-radius: var(--skx-radius-pill);
}
.rs-round__state.is-checking::before {
  content: "";
  width: 0.3rem;
  height: 0.3rem;
  background: var(--skx-primary);
  border-radius: 50%;
  animation: rs-blink 1.2s ease-in-out infinite;
}
@media (prefers-reduced-motion: reduce) {
  .rs-round__state.is-checking::before {
    animation: none;
  }
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

(진행 패널은 인쇄에서 옆 칸째 빠지므로(`.rs-page .rs-col-side`) 인쇄 규칙은 더하지 않는다.)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchEvents.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  105 passed (105)`(06c 가 먼저 들어와 있었으면 `112`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: 실패 0 — `Test Files` 는 Task D7 뒤와 같고 `Tests` 는 Task D7 뒤 수 + 3

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend/components/research/PlanCard.vue`
Expected: (빈 출력 — `subqStatusLabel` 과 PlanCard 는 그대로다)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchEvents.ts frontend/components/research/ProgressPanel.vue frontend/assets/css/research.css frontend/tests/unit/researchEvents.test.ts && git status --short && git commit -m "[Feat] round06d — 진행 패널 회차 줄에 '자기점검 중'·'재검색 중'을 붙인다(roundStatusLabel). 도는 하위질문의 마지막 회차가 검색어만 있고 판정이 없으면 자기점검(LLM)을 기다리는 중이고, 판정이 다음 검색어를 냈으면 다시 찾는 중이다 — 점검 결과가 올 때까지 수십 초 동안 회차 줄이 멈춰 보이지 않게 한다. 끝난 하위질문·앞 회차·충분 판정이 난 회차는 적지 않는다. 하위질문 줄의 subqStatusLabel 은 PlanCard(06c)도 읽어 그대로 둔다. 자기점검 중은 기존 rs-blink 로 점이 깜빡이고 움직임 줄이기면 멈춘다"
```

---

### Task L4: 탐색 후보 이벤트 타입·리듀서(`candidates`)

spec §12-3 '탐색 후보 검토 중 더미(Q9)' 행의 타입·리듀서 부분(`types/research.ts` 이벤트 타입, `utils/researchEvents.ts` 리듀서 — 판정이 오면 지움, 다음 회차 후보가 앞 더미를 갈음, 재접속·스냅숏이면 더미 없음) · §12-2 '탐색 후보 목록 이벤트'(06c 가 낸다) · §12-7 '탐색 후보 더미' · 정함 11. 장부에 그리는 일은 Task L5 다.

**이벤트 모양(정본 = 06c 계획 — 06c 와 다르면 06c 를 따른다):** 이름 `candidates`, `{"subq_idx": int, "round": int, "papers": [{"cnts_id", "title", "personal_author", "pub_date"}]}`. 06c 계획의 탐색 후보 Task 가 `runner.py` 회차 루프의 `await emit("counters", research_stats(state))` 바로 뒤·`critique_fn` 앞에 `await emit("candidates", {"subq_idx": subq.idx, "round": round_no, "papers": [_paper_brief(state.evidence[e]) for e in linked]})` 를 낸다 — 회차마다 늘 한 번(순서 `search` → `counters` → `candidates` → `critique`), 이은 근거가 없어도 `papers: []`, 스냅숏·회차 기록·단계 result 에는 없다. **하위질문 키는 `subq_idx`** 다 — runner 의 `search`(`runner.py:209-212`)·`critique`(`:306-308`)와 같은 키이고 spec §12-2 는 커밋 `c5d05b0` 에서 이 글자로 맞췄다(이 Task 를 만든 지시문의 `subq_id` 는 옛 글자 — 06c 를 따른다). `papers` 는 `_paper_brief`(`runner.py:85-89`) 그대로라 뺀 논문 `ExcludedPaper`(`types/research.ts:53-58`)와 같은 모양이다.

**알아 둘 것:**
- **상태는 `SubqView.reviewing?: ReviewingView`(선택 필드 — 공통 계약 '고치는 파일의 새·바뀐 공개 이름' 표의 `types/research.ts` 행, 정함 11).** 값이 있을 때만 키를 둔다 — `SubqView` 를 `toEqual` 로 견주는 기존 테스트(`researchEvents.test.ts:171` 등)를 깨지 않게. `toEqual` 은 값이 `undefined` 인 키를 없는 키와 같게 보므로 새 테스트는 키가 없는지를 `"reviewing" in sq` 로 본다.
- **리듀서 규칙(정함 11 + 06c 계획 정함 4):** 후보가 있으면 그 하위질문의 `reviewing` 을 세우고 앞 후보를 갈음한다. **빈 후보는 갈음 = 비움** — 그 하위질문이 있고 `reviewing` 이 있을 때만 키를 지우고, 아니면 `view` 를 그대로 돌려준다(`updateSubq`(da80f23 `:693-698`)는 모르는 번호에 `emptySubq` 를 덧붙이므로 빈 후보로 유령 하위질문을 만들지 않게 먼저 본다). 같은 하위질문의 `critique` 가 지운다(`applyCritique` 의 갱신 함수). 진행 저장 step 이벤트는 `rebuild` → `buildSubq` 를 거치므로 `buildSubq` 가 `carry.reviewing` 을 잇되, 새 회차 기록에 그 회차의 판정(`verdict !== null`)이 있으면 잇지 않는다(점검 이벤트를 놓치고 진행 저장만 받은 경우). `applySnapshot` 은 rebuild 뒤 모든 하위질문에서 지운다 — 후보는 저장되지 않아 다시 오지 않는다(spec '재접속하면 더미 없이').
- **끝난 잡도 지운다(정함 11 의 '잡 종료'). 길이 둘이다.** ① 종료 이벤트(`done`·`failed`·`canceled`) — 취소는 API 가 곧바로 잡을 끝내고 스트림을 닫는다(워커는 하위질문 경계에서만 멈춰 돌던 점검을 마저 하지만 그 `critique` 는 화면에 오지 않는다). ② GET 으로만 다시 맞추는 `refreshView`(da80f23 `researchEvents.ts:269-278`) — `rebuild({ ...fresh, subqs: prev.subqs, … })` 가 `buildSubq` 로 앞 화면의 `reviewing` 을 잇는다. 스트림이 `CLOSED` 되면 `useResearch.ts:211-229`(`es.onerror` → `scheduleReconnect`)에서 `refresh` → `refreshView`(`:151`)로 맞추는데, 그 사이 잡이 실패·취소됐으면 종료 이벤트가 오지 않고 끝난 잡이라 `connect` 도 하지 않아(`:155`) `snapshot` 도 오지 않는다. 그래서 리듀서의 끝난 잡 세 분기와 `refreshView`(맞춘 잡이 끝난 상태일 때 — `isTerminalStatus`) 두 곳에서 `clearReviewing` 을 부른다. 지우지 않으면 취소·실패한 잡의 장부에 '검토 중 n'이 영영 남는다(EvidenceLedger 는 `live` 와 상관없이 `ledger.reviewing` 을 그린다). 테스트 둘을 더한다(이 Task 의 새 it 은 모두 11개 — +11).
- 06c 전 워커·06c 를 모르는 화면: 옛 워커는 이 이벤트를 보내지 않아 지금과 같고, 옛 화면은 모르는 이벤트를 `default: return view`(`:329-330`)로 넘긴다.
- 키 지우기는 복사 뒤 `delete`(선택 필드라 TS 가 허용한다 — `historyState.ts:37` 선례). 구조 분해로 버리는 변수를 만들지 않는다.
- `researchEvents.ts` 는 D2·L3 이, `researchEvents.test.ts` 는 D2·L3 이 먼저 고쳤다 — 아래 old 는 그 Task 들이 바꾸지 않는 글자다. `types/research.ts` 는 이 줄에서 이 Task 만 고친다(06c 의 `StepResult` 칸 셋은 L6 의 merge 로 들어온다 — 서로 다른 블록).

**Files:**
- Modify: `frontend/types/research.ts`(`QueueEvent` da80f23 `:337-342` 뒤 `CandidatesEvent`, 유니온 `:344-355` 끝, `SubqView` `:394-405` 끝의 선택 필드와 그 뒤 `ReviewingView`)
- Modify: `frontend/utils/researchEvents.ts`(import 두 이름 · `refreshView` 끝 · `applyResearchEvent` 의 switch(`case "candidates"`·끝난 잡 셋) · `applySnapshot` · `applyCritique` 갱신 함수 · `applyCritique` 뒤 새 `applyCandidates` · `buildSubq` · `emptySubq` 앞 새 `withoutReviewing`·`clearReviewing`)
- Test: `frontend/tests/unit/researchEvents.test.ts`(type import 한 이름, L3 의 describe 뒤에 새 describe)

기준선: Task L3 뒤 수. `researchEvents.test.ts` 는 `105`(06c 가 먼저 들어와 있었으면 `112`).

- [ ] **Step 0: 06c 계획의 이벤트 모양을 다시 본다(안전망)**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && (git show dev:docs/superpowers/plans/2026-10-08-round06c-query-broadening.md 2>/dev/null || cat C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/docs/superpowers/plans/2026-10-08-round06c-query-broadening.md) | grep -A 3 'await emit("candidates"'`
Expected: 06c 계획 본문의 구현 블록 한 곳(이 글자는 06c 계획에 한 번 — 탐색 후보 Task 의 runner 구현 Step)이 다음 네 줄로 나온다:

```
        await emit("candidates", {
            "subq_idx": subq.idx, "round": round_no,
            "papers": [_paper_brief(state.evidence[e]) for e in linked],
        })
```

06c 가 이미 구현 커밋을 냈으면 코드로도 본다 — Run: `grep -A 3 'await emit("candidates"' C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app/services/research/runner.py` → 같은 네 줄(06c worktree 가 없거나 아직 구현 전이면 `No such file` 또는 빈 출력 — 계획 본문만 본다).

다르면(이름이 `candidates` 가 아니거나 키가 `subq_idx` 가 아니거나 `papers` 항목 칸이 다르면) **06c 를 따른다** — 이 Task 의 `CandidatesEvent`·`applyCandidates`·테스트 픽스처(`candidates()` 도우미)를 06c 의 이름으로 바꿔 쓰고 사용자와 06c 세션에 알린다. 06c 계획 파일이 두 곳 모두 없으면 멈추고 06c 세션에 계획 위치를 묻는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchEvents.test.ts` — 타입 import(da80f23 `:3-16`). old:

```ts
import type {
  CritiqueEvent,
```

new:

```ts
import type {
  CandidatesEvent,
  CritiqueEvent,
```

같은 파일 — Task L3 이 더한 describe 의 끝 뒤. old:

```ts
    const second = run(AWAITING_ROUND2_CRITIQUE).subqs[0]!;
    expect(roundStatusLabel(second, second.rounds[0]!)).toBeNull();
  });
});
```

new:

```ts
    const second = run(AWAITING_ROUND2_CRITIQUE).subqs[0]!;
    expect(roundStatusLabel(second, second.rounds[0]!)).toBeNull();
  });
});

describe("탐색 후보 — candidates 이벤트", () => {
  // 워커(runner)의 _paper_brief 모양 — 뺀 논문(excluded_papers)과 같다. 서지가 없는 칸은 null 로 온다
  const PAPERS = [
    { cnts_id: "C1", title: " 초등 AI 윤리 수업의 효과 ", personal_author: "김철수; 이영희", pub_date: "2019-03" },
    { cnts_id: "C2", title: null, personal_author: null, pub_date: null },
  ];
  const PAPERS_VIEW = [
    { cntsId: "C1", title: "초등 AI 윤리 수업의 효과", personalAuthor: "김철수; 이영희", pubDate: "2019-03" },
    { cntsId: "C2", title: "", personalAuthor: null, pubDate: null },
  ];
  const FIRST_SEARCH: ResearchEvent = { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 };
  const RECHECK: CritiqueEvent = {
    kind: "critique", subq_idx: 0, verdict: "insufficient", note: "초등 대상 연구가 없다", adopted: 5,
    parse_failed: false, capped: 0, round: 1, next_query: "초등 AI 윤리 교육 효과", will_recheck: true,
  };
  function candidates(subqIdx: number, round: number, papers = PAPERS): CandidatesEvent {
    return { kind: "candidates", subq_idx: subqIdx, round, papers };
  }
  // 1회차 검색 직후 후보를 받고 자기점검을 기다리는 장면(워커의 순서: search → counters → candidates → critique)
  const REVIEWING: ResearchEvent[] = [SEARCH_STARTED, FIRST_SEARCH, { kind: "counters", ...SAVED }, candidates(0, 1)];

  it("후보 이벤트가 그 하위질문에 '검토 중' 후보를 세운다(서지 모양은 뺀 논문과 같다)", () => {
    const v = run(REVIEWING);
    expect(v.subqs[0]!.reviewing).toEqual({ round: 1, papers: PAPERS_VIEW });
    // 회차 기록은 그대로다 — 후보는 장부에 세우는 화면 상태일 뿐이다
    expect(v.subqs[0]!.rounds.map((r) => [r.round, r.verdict, r.adoptedPapers.length])).toEqual([[1, null, 0]]);
  });

  it("같은 하위질문의 점검(critique)이 오면 검토 중을 지운다", () => {
    const before = run(REVIEWING);
    expect(before.subqs[0]!.reviewing?.papers).toHaveLength(2);
    const after = applyResearchEvent(before, RECHECK);
    expect("reviewing" in after.subqs[0]!).toBe(false);
    expect(after.subqs[0]!.rounds[0]!.verdict).toBe("insufficient");
  });

  it("판정 전에 다음 회차 후보가 오면 앞 후보를 갈음한다", () => {
    const next = { cnts_id: "C3", title: "교사 연수와 윤리 수업", personal_author: "박민수", pub_date: "2021" };
    const v = run([...REVIEWING, candidates(0, 2, [next])]);
    expect(v.subqs[0]!.reviewing).toEqual({
      round: 2,
      papers: [{ cntsId: "C3", title: "교사 연수와 윤리 수업", personalAuthor: "박민수", pubDate: "2021" }],
    });
  });

  it("빈 후보 이벤트는 앞 회차의 검토 중을 지운다", () => {
    // 1회차 점검을 놓친 채 2회차가 이은 근거 없이(papers: []) 왔다 — 앞 회차의 '검토 중'이 남지 않는다
    const before = run(REVIEWING);
    expect(before.subqs[0]!.reviewing?.round).toBe(1);
    const after = applyResearchEvent(before, candidates(0, 2, []));
    expect("reviewing" in after.subqs[0]!).toBe(false);
  });

  it("다른 하위질문의 점검은 검토 중을 지우지 않는다", () => {
    const v = run([...REVIEWING, candidates(1, 1)]);
    expect(v.subqs[1]!.reviewing?.round).toBe(1);
    const next = applyResearchEvent(v, RECHECK);
    expect("reviewing" in next.subqs[0]!).toBe(false);
    expect(next.subqs[1]!.reviewing).toEqual({ round: 1, papers: PAPERS_VIEW });
  });

  it("진행 저장 step 이벤트는 검토 중을 남기고, 그 회차의 판정이 실린 step 이면 지운다", () => {
    // 2회차 검색 뒤 후보를 받고 점검을 기다린다 — 1회차 기록만 실은 진행 저장은 2회차 후보를 지우지 않는다
    const waiting = run([...AWAITING_ROUND2_CRITIQUE, candidates(0, 2)]);
    const kept = applyResearchEvent(waiting, { ...SEARCH_STARTED, result: { rounds: [ROUND1], counters: LIVE } });
    expect(kept.subqs[0]!.reviewing).toEqual({ round: 2, papers: PAPERS_VIEW });
    // 2회차 점검 이벤트를 놓치고 그 판정이 실린 진행 저장만 받았다
    const judged = applyResearchEvent(kept, { ...SEARCH_STARTED, result: { rounds: [ROUND1, ROUND2], counters: LIVE } });
    expect("reviewing" in judged.subqs[0]!).toBe(false);
    expect(judged.subqs[0]!.rounds.map((r) => r.verdict)).toEqual(["insufficient", "sufficient"]);
  });

  it("snapshot 은 검토 중을 지운다 — 재접속하면 더미 없이 그린다", () => {
    const before = run(REVIEWING);
    expect(before.subqs[0]!.reviewing).toBeDefined();
    const v = applyResearchEvent(before, {
      kind: "snapshot",
      steps: [PLAN_ROW, step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "running" })],
      job: { status: "running", stage: "planned", plan: ["효과 측정", "교사 인식"] },
    });
    expect(v.subqs.some((s) => "reviewing" in s)).toBe(false);
    // 라이브로 받은 회차는 그대로 남는다
    expect(v.subqs[0]!.rounds.map((r) => r.query)).toEqual(["효과 측정"]);
  });

  it("처음 연 화면(initialResearchView)에는 검토 중이 없고, 검토 중이 없는 하위질문에 빈 후보가 오면 view 를 그대로 돌려준다 — 모르는 번호에도 하위질문을 덧붙이지 않는다", () => {
    const opened = initialResearchView(job({ steps: [PLAN_ROW, SAVED_SEARCH_ROW] }));
    expect(opened.subqs.some((s) => "reviewing" in s)).toBe(false);
    expect(applyResearchEvent(opened, candidates(0, 2, []))).toBe(opened);
    expect(applyResearchEvent(opened, candidates(5, 1, []))).toBe(opened);
    expect(opened.subqs.map((s) => s.idx)).toEqual([0, 1]);
  });

  it("검토 중이 없는 하위질문에는 reviewing 키를 두지 않는다(기존 모양 그대로)", () => {
    const v = run(REVIEWING);
    expect("reviewing" in v.subqs[0]!).toBe(true);
    expect("reviewing" in v.subqs[1]!).toBe(false);
    // 하위질문을 다시 지어도(승인한 계획 반영 — rebuild) 검토 중은 그 하위질문에만 남고 다른 하위질문에 키가 생기지 않는다
    const rebuilt = withPlan(v, ["효과 측정", "교사 인식"]);
    expect(rebuilt.subqs[0]!.reviewing).toEqual({ round: 1, papers: PAPERS_VIEW });
    expect("reviewing" in rebuilt.subqs[1]!).toBe(false);
  });

  it("끝난 잡(완료·실패·취소 이벤트)은 검토 중을 지운다 — 스트림이 닫혀 점검이 오지 않는다", () => {
    const before = run(REVIEWING);
    expect(before.subqs[0]!.reviewing).toBeDefined();
    const ends: ResearchEvent[] = [
      { kind: "canceled", status: "canceled" },
      { kind: "failed", status: "failed", error: "시간 상한" },
      { kind: "done", status: "completed" },
    ];
    for (const end of ends) {
      expect(applyResearchEvent(before, end).subqs.some((s) => "reviewing" in s)).toBe(false);
    }
  });

  it("끝난 잡으로 다시 맞추면(refreshView) 검토 중을 지운다 — 재연결 사이에 끝난 잡은 종료 이벤트도 snapshot 도 오지 않는다", () => {
    const before = run(REVIEWING);
    expect(before.subqs[0]!.reviewing).toBeDefined();
    // 스트림이 끊겨(CLOSED) GET 으로만 다시 맞추는 사이에 잡이 실패했다 — 앞 화면의 하위질문을 잇는 길에서도 남지 않는다
    const v = refreshView(before, job({
      status: "failed",
      steps: [PLAN_ROW, step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "failed", result: { error: "시간 상한" } })],
    }));
    expect(v.status).toBe("failed");
    expect(v.subqs.some((s) => "reviewing" in s)).toBe(false);
  });
});
```

(`SAVED`·`LIVE`·`SAVED_SEARCH_ROW`·`withPlan`·`refreshView` 는 이 파일의 기존 픽스처·import 다. vitest 는 타입을 보지 않으므로 `CandidatesEvent` 가 아직 없어도 테스트는 돈다 — `import type` 은 지워진다.)

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchEvents.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  10 failed | 106 passed (116)` — 아직 `case "candidates"` 가 없어 `default` 가 view 를 그대로 돌려준다. 실패 열의 첫 메시지: `expected undefined to deeply equal { Object (round, papers) }`·`Target cannot be null or undefined.`·`expected undefined to deeply equal { round: 2, papers: [ { …(4) } ] }`·`expected undefined to be 1`(둘)·`expected undefined to deeply equal { Object (round, papers) }`·`expected undefined to be defined`(셋 — snapshot·끝난 잡·refreshView)·`expected false to be true`. 통과하는 새 it 하나는 `처음 연 화면(initialResearchView)에는 검토 중이 없고, …` — 지금도 맞아야 하는 것을 지키는 테스트다. 06c 가 먼저 들어와 있었으면 `10 failed | 113 passed (123)`. (refreshView it 은 Step 3 에서 `refreshView` 고침만 빼고 넣으면 `expected true to be false` 로 떨어지는 것을 사본에서 확인했다 — 앞 화면의 검토 중을 잇는 길을 실제로 지킨다.)

- [ ] **Step 3: 타입과 리듀서를 구현한다**

`frontend/types/research.ts` — `QueueEvent` 뒤(da80f23 `:337-342`). old:

```ts
export interface QueueEvent {
  kind: "queue";
  ahead: number;
  eta_sec: number | null;
}
```

new:

```ts
export interface QueueEvent {
  kind: "queue";
  ahead: number;
  eta_sec: number | null;
}

// 워커(runner)의 탐색 후보 목록 — 회차마다 search·counters 뒤·자기점검(critique) 전에 늘 한 번 온다. 이은 근거가 없어도
// papers: [] 로 온다. 하위질문 키는 search·critique 와 같은 subq_idx 다. 스냅숏·회차 기록에는 없다 — 재접속하면 오지
// 않는다. papers 는 runner._paper_brief 모양(뺀 논문 ExcludedPaper 와 같다)이고, 이번 회차에 점검할 근거를 이은 순서다
export interface CandidatesEvent {
  kind: "candidates";
  subq_idx: number;
  round?: number;
  papers: ExcludedPaper[];
}
```

같은 파일 — 이벤트 유니온 끝(`:354-355`). old:

```ts
  | CanceledEvent
  | QueueEvent;
```

new:

```ts
  | CanceledEvent
  | QueueEvent
  | CandidatesEvent;
```

같은 파일 — `SubqView` 끝(`:402-405`)과 그 뒤. old:

```ts
  adopted: number | null;
  parseFailed: boolean;
  error: string | null;
}
```

new:

```ts
  adopted: number | null;
  parseFailed: boolean;
  error: string | null;
  // 자기점검을 기다리는 탐색 후보(후보 이벤트 candidates 가 세운다). 있을 때만 키를 둔다 — 없는 하위질문에 null 로 채우지 않는다
  reviewing?: ReviewingView;
}

// 화면 상태 — 그 하위질문의 '검토 중' 후보. 같은 하위질문의 점검(critique)·그 회차 판정이 실린 진행 저장·snapshot·잡 종료가
// 지운다(저장되지 않는 값이라 재접속하면 없다). round 는 후보가 온 회차(이벤트에 없으면 null)
export interface ReviewingView {
  round: number | null;
  papers: ExcludedPaperView[];
}
```

(이 old 네 줄은 파일에 한 번이다 — `SubqView` 만 `adopted`·`parseFailed`·`error` 순으로 끝난다.)

`frontend/utils/researchEvents.ts` — 머리 import(da80f23 `:2-37`) 두 곳. old:

```ts
  AdoptedPaperView,
  CountersPayload,
```

new:

```ts
  AdoptedPaperView,
  CandidatesEvent,
  CountersPayload,
```

old:

```ts
  ResearchView,
  RoundSource,
```

new:

```ts
  ResearchView,
  ReviewingView,
  RoundSource,
```

`refreshView` 끝 — 맞춘 잡이 끝난 상태면 앞 화면이 잇던 '검토 중'을 지운다(da80f23 `:276-277` — `return { ...merged, counters, highlight };` 는 파일에 한 번). old:

```ts
  const highlight = merged.status === "running" ? (prev.highlight ?? latestHighlight(merged.subqs)) : null;
  return { ...merged, counters, highlight };
```

new:

```ts
  const highlight = merged.status === "running" ? (prev.highlight ?? latestHighlight(merged.subqs)) : null;
  // 끝난 잡은 스트림이 닫혀 점검이 더 오지 않는다 — 앞 화면이 잇던 '검토 중' 후보를 남기지 않는다(재연결 사이에 끝난
  // 잡은 종료 이벤트도 snapshot 도 오지 않고 이 GET 으로만 맞춘다)
  const settled = isTerminalStatus(merged.status) ? clearReviewing(merged) : merged;
  return { ...settled, counters, highlight };
```

(`isTerminalStatus` 는 같은 파일의 함수(da80f23 `:88`)이고, `clearReviewing` 은 아래에서 더하는 함수 선언이라 호이스팅된다.)

`applyResearchEvent` 의 switch — 점검 다음에 후보(da80f23 `:314-315`). old:

```ts
    case "critique":
      return applyCritique(view, event);
```

new:

```ts
    case "critique":
      return applyCritique(view, event);
    case "candidates":
      return applyCandidates(view, event);
```

같은 switch — 끝난 잡 셋(`:320-325`). old:

```ts
    case "done":
      return { ...view, status: "completed", highlight: null, queue: null };
    case "failed":
      return { ...view, status: "failed", lastError: event.error ?? view.lastError, highlight: null, queue: null };
    case "canceled":
      return { ...view, status: "canceled", highlight: null, queue: null };
```

new:

```ts
    // 끝난 잡은 스트림이 닫혀 점검이 더 오지 않는다 — '검토 중' 후보를 남기지 않는다
    case "done":
      return { ...clearReviewing(view), status: "completed", highlight: null, queue: null };
    case "failed":
      return { ...clearReviewing(view), status: "failed", lastError: event.error ?? view.lastError, highlight: null, queue: null };
    case "canceled":
      return { ...clearReviewing(view), status: "canceled", highlight: null, queue: null };
```

`applySnapshot`(앵커 `function applySnapshot(view: ResearchView, event: SnapshotEvent): ResearchView {`, da80f23 `:350-353`). old:

```ts
  if (!next.plan.length) next.plan = planFromSteps(next.steps);
  const rebuilt = rebuild(next);
  if (rebuilt.highlight || rebuilt.status !== "running") return rebuilt;
```

new:

```ts
  if (!next.plan.length) next.plan = planFromSteps(next.steps);
  // 스냅숏은 재접속·상태가 바뀔 때 온다 — 탐색 후보는 저장되지 않아 다시 오지 않으므로 '검토 중'은 지우고 저장된 장부만
  // 그린다. 지나간 후보는 점검의 채택·뺌으로 이미 보인다
  const rebuilt = clearReviewing(rebuild(next));
  if (rebuilt.highlight || rebuilt.status !== "running") return rebuilt;
```

`applyCritique` 의 갱신 함수(앵커 `function applyCritique(view: ResearchView, event: CritiqueEvent): ResearchView {`, da80f23 `:407-410`). old:

```ts
    return {
      ...sq,
      rounds: upsertRound(sq.rounds, entry),
      verdict: event.verdict,
```

new:

```ts
    // 이 하위질문의 '검토 중' 후보는 이 점검으로 채택·뺌이 정해졌다 — 지운다
    return {
      ...withoutReviewing(sq),
      rounds: upsertRound(sq.rounds, entry),
      verdict: event.verdict,
```

`applyCritique` 바로 뒤에 `applyCandidates`(da80f23 `:419-420` — `applyCritique` 의 마지막 두 줄. `return { ...next, highlight };` 는 파일에 한 번). old:

```ts
  return { ...next, highlight };
}
```

new:

```ts
  return { ...next, highlight };
}

// 워커의 탐색 후보(candidates) — 회차마다 검색 뒤·자기점검 전에 한 번 온다. 그 하위질문의 '검토 중' 후보를 세우고(앞 후보는
// 갈음한다), 같은 하위질문의 점검·그 회차 판정이 실린 진행 저장·snapshot·잡 종료가 지운다. 빈 후보(papers: [])는
// 갈음 = 비움이다 — 점검을 놓친 채 다음 회차가 빈 후보로 와도 앞 회차의 '검토 중'이 남지 않는다. updateSubq 는 모르는
// 번호에 빈 하위질문을 덧붙이므로 빈 후보는 그 하위질문에 검토 중이 있을 때만 고친다(유령 하위질문을 만들지 않는다)
function applyCandidates(view: ResearchView, event: CandidatesEvent): ResearchView {
  if (!event.papers.length) {
    const sq = view.subqs.find((s) => s.idx === event.subq_idx);
    return sq?.reviewing ? updateSubq(view, event.subq_idx, withoutReviewing) : view;
  }
  const reviewing: ReviewingView = { round: event.round ?? null, papers: event.papers.map(toExcludedPaperView) };
  return updateSubq(view, event.subq_idx, (sq) => ({ ...sq, reviewing }));
}
```

`buildSubq`(앵커 `function buildSubq(`, da80f23 `:496-511`) — 두 곳. old:

```ts
  const fallbackStatus: StepStatus = trail ? (trail.failed ? "failed" : "done") : "pending";
  return {
```

new:

```ts
  const fallbackStatus: StepStatus = trail ? (trail.failed ? "failed" : "done") : "pending";
  // 탐색 후보('검토 중')는 저장되지 않는 화면 상태라 단계 행이 다시 지어져도 잇는다. 다만 새 회차 기록에 그 회차의
  // 판정이 실렸으면(점검 이벤트를 놓치고 진행 저장만 받았다) 잇지 않는다
  const rv = carry?.reviewing;
  const reviewing = rv && !rounds.some((x) => x.round === rv.round && x.verdict !== null) ? rv : undefined;
  return {
```

old:

```ts
      error: r.error ?? null,
    },
  };
}
```

new:

```ts
      error: r.error ?? null,
      ...(reviewing ? { reviewing } : {}),
    },
  };
}
```

(`carry` 는 같은 시도일 때만 앞 하위질문이다(`:479`) — 재시도로 새 탐색 단계가 열리면 앞 시도의 검토 중도 잇지 않는다. `rounds` 는 이미 `mergeRounds` 로 라이브 회차와 합친 값(`:493`)이다.)

`emptySubq` 바로 앞에 두 도우미(앵커 `function emptySubq(idx: number, title: string): SubqView {`, da80f23 `:700`). old:

```ts
function emptySubq(idx: number, title: string): SubqView {
```

new:

```ts
// '검토 중' 후보 키를 뺀 하위질문 — 없으면 같은 객체를 돌려준다. 키를 null 로 남기지 않는다(기존 모양 그대로)
function withoutReviewing(sq: SubqView): SubqView {
  if (!sq.reviewing) return sq;
  const rest = { ...sq };
  delete rest.reviewing;
  return rest;
}

function clearReviewing(view: ResearchView): ResearchView {
  return view.subqs.some((s) => s.reviewing) ? { ...view, subqs: view.subqs.map(withoutReviewing) } : view;
}

function emptySubq(idx: number, title: string): SubqView {
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchEvents.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  116 passed (116)`(06c 가 먼저 들어와 있었으면 `123`) — 기존 `toEqual` 테스트가 모두 그대로 통과한다(키를 늘 싣고 있으면 여기서 깨진다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: 실패 0 — `Tests` 는 Task L3 뒤 수 + 11(`researchDraft.test.ts`·`evidenceLedger.test.ts` 등 `SubqView` 를 쓰는 다른 파일도 그대로 통과)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0` (`ResearchEvent` 유니온에 `CandidatesEvent` 가 들어가 `case "candidates"` 의 `event` 가 좁혀진다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/types/research.ts frontend/utils/researchEvents.ts frontend/tests/unit/researchEvents.test.ts && git status --short && git commit -m "[Feat] round06d — 06c 의 탐색 후보 이벤트(candidates)를 받아 하위질문에 '검토 중' 후보를 세우고 판정·재접속에 지운다. 모양은 06c 그대로 {subq_idx, round, papers: [_paper_brief…]}(CandidatesEvent)이고 화면 상태는 SubqView.reviewing(선택 — 있을 때만 키를 둔다). 다음 회차 후보는 앞 후보를 갈음하고 빈 후보는 비운다(모르는 번호·검토 중 없는 하위질문에 빈 후보가 오면 view 그대로). 같은 하위질문의 critique, 그 회차 판정이 실린 진행 저장, snapshot, 끝난 잡(완료·실패·취소 이벤트와 끝난 잡으로 다시 맞추는 refreshView — 스트림이 닫혀 점검이 오지 않는다)이 지운다. 옛 워커는 이 이벤트를 보내지 않아 지금과 같다"
```

---

### Task L5: 근거 장부 '검토 중' 더미·장부 배치

spec §12-3 '탐색 후보 검토 중 더미(Q9)' 행의 장부 부분(`utils/evidenceLedger.ts` `ledgerFrom` 세 번째 묶음, `components/work/EvidenceLedger.vue`, `work.css` 근거 장부 블록 — 흐린 카드 + 미세한 반짝임, 판정 뒤 채택 `wk-drop`·뺌 `wk-sink`, reduced-motion) · '근거가 떨어져 들어옴 — EvidenceLedger 를 그대로 쓰고 배치만 옮긴다'(정함 10 — 장부를 옆 칸 맨 위로) · §12-8 장면 1. Task L4 가 세운 `SubqView.reviewing` 을 장부에 그린다.

**알아 둘 것:**
- **세 번째 묶음 `Ledger.reviewing`(필수 칸 — 공통 계약 '고치는 파일의 새·바뀐 공개 이름' 표의 `utils/evidenceLedger.ts` 행).** 하위질문 순 → 후보 순으로, **채택 더미에 이미 있는 논문은 빼고** 중복 없이 모은다(06c 의 후보는 이번 검색이 이은 근거 전부라 앞 회차에서 이미 채택된 논문도 들어 있다 — `runner.py` 의 `linked` 는 재사용 링크를 포함한다). `round` = `reviewing.round ?? 0`, `isNew` = true, 여러 하위질문이 같은 논문을 후보로 이으면 `subqIdx` 를 모은다. 서지는 후보가 실은 것을 먼저, 비었으면 장부가 앞에서 모은 서지(채택의 새 채택·뺀 논문 목록)를 쓴다.
- **뺌 더미에는 검토 중인 논문을 두지 않는다** — 다른 하위질문이 뺀 논문을 이 하위질문이 다시 후보로 이었으면 판정 전에는 검토 중에만 있다(더미 셋에 같은 논문이 함께 있지 않다 — 기존 '두 더미' 규칙(`:97-98`)의 연장). 그래서 `reviewing` 을 `dropped` 보다 먼저 만든다.
- `hasLedger` 는 첫 회차의 후보가 점검 전에 왔을 때(채택 목록이 어디에도 없을 때)도 참이다 — 그래야 첫 '검토 중'이 보인다. `ledgerLine` 은 검토 중이 있을 때만 ` · 검토 중 n` 을 잇는다(없으면 지금 글자 그대로 — `채택 n · 뺌 n`).
- **탐색 중 한 번 선 장부 카드는 탐색이 끝날 때까지 둔다(부품의 `seenLive`).** 잡의 첫 점검이 채택 0편(후보 전부 무관 제외 — `runner.py:92-102` `_adopted_papers` 는 제외 뒤 `subq.evidence_ids` 만 싣는다)이면, 후보 이벤트에 선 카드가 리듀서가 `reviewing` 을 지우는 순간 `adoptedPapers` 가 어디에도 없어 `hasLedger` 가 거짓이 되어 카드째 사라지고(뺌 더미의 `wk-sink` 도 보이지 않는다) 다음 회차 후보에 다시 선다. 06d 전에는 첫 채택 전까지 카드가 아예 없었으므로 이 깜빡임은 '검토 중'이 새로 만드는 동작이다. `hasLedger` 는 06a 전 잡을 가리는 판단이라 그대로 두고, `EvidenceLedger.vue` 의 `shown` 이 `hasLedger(…) || (live && seenLive)` 를 본다 — 탐색이 끝나면(`live` 거짓) 지금처럼 `hasLedger` 만 본다.
- **'검토 중' 묶음은 채택 목록 끝 바로 아래, 뺌 묶음 앞에 둔다.** spec §12-3 Q9 행은 '오른쪽 장부의 그 하위질문 자리에' 검토 중 카드를 세웠다가 판정 뒤 채택이 떨어져 박힌다고 적는다. 장부에는 하위질문별 칸이 없고 채택 목록은 하위질문 순이라 도는 하위질문의 자리가 목록 끝이다(`EvidenceLedger.vue:119-122` '새 채택은 지금 도는 하위질문 묶음(목록 끝)에 들고'). 그래서 후보는 그 끝 바로 아래에 섰다가, 판정이 오면 채택은 바로 위 목록 끝에 떨어지고(`follow` 가 그 줄을 보이게 옮긴다) 뺀 것은 바로 아래 뺌 더미로 가라앉는다. 카드마다 '하위질문 N' 을 단다(채택·뺌 줄과 같은 `subqLabel`).
- **판정 뒤 움직임은 기존 코드 그대로다.** 점검이 오면 리듀서(Task L4)가 `reviewing` 을 지우고 그 회차의 `adoptedPapers`·`excludedPapers` 가 채워진다 → `newlyAdded`(`:135-138`)가 그 논문을 새 채택·새 뺌으로 잡고 `.is-fresh` 로 `wk-drop`·`wk-sink` 가 돈다(`EvidenceLedger.vue:87-117`). 검토 중 카드는 떨어지지 않고 흐린 점선 카드가 천천히 반짝인다(`@keyframes wk-review` — 이 파트의 유일한 새 keyframes). 새로 선 후보는 알림 줄에 `후보 n편 검토 중` 으로 읽힌다(채택·뺌과 같은 `announceSeq` 방식). 후보만 선 바뀜은 앞서 떨어지던 채택·뺌의 `fresh` 를 끊지 않는다.
- **배치(정함 10):** 근거 장부를 옆 칸 맨 위(진행 패널 위)로 옮긴다 — 진행 패널의 탐색 타임라인이 길어져 장부가 화면 밖 아래에서 떨어지지 않게. 장부는 빈 때부터 마운트돼 있어야 첫 회차의 채택이 떨어지므로(`EvidenceLedger.vue:3-5`) 감싸개 `wk-side-ledger` 는 그대로 늘 그리고, 간격 규칙만 `margin-top` → `margin-bottom` 으로 바꾼다(`work.css:1216-1220`). 좁은 화면(B)도 옆 칸 안의 순서라 같다.
- `work.css` 는 근거 장부 블록(`:75-166`)과 `:1216-1220` 만 고친다(계획 머리 '실행 전 알아 둘 것'의 CSS 자리 — 나머지는 06e). `.wk-pill` 등 다른 블록은 그대로다.
- 커밋 둘 — ① '검토 중' 묶음(유틸·테스트·부품·장부 CSS) ② 장부를 옆 칸 맨 위로(`[id].vue`·`work.css` 간격 한 규칙). ② 는 `work.css` 의 다른 hunk 라 ① 을 커밋한 뒤 고친다(`git add -p` 를 쓰지 않는다).
- `[id].vue` 는 D1·D2·D4·D5·L2·D7 이 먼저 고쳤다. 옆 칸 `<aside class="rs-col-side">` … `</aside>` 안은 그 Task 들이 바꾸지 않는다(D7 의 알약은 `</aside>` 다음 `</div>` 뒤에 선다).

**Files:**
- Modify: `frontend/utils/evidenceLedger.ts`(머리 주석 `:2-5`, `LedgerPaper.round` 주석 `:14-15`, `Ledger` `:20-23`, `hasLedger` `:31-34`, `ledgerFrom` 의 뺌 앞(`:97-104`)과 반환 `:126`, `ledgerLine` `:129-131`)
- Modify: `frontend/components/work/EvidenceLedger.vue`(채택 목록 끝 `:22` 과 뺌 묶음 `:24` 사이 검토 중 묶음, `shown` `:70`, `prevDropped` `:79` 뒤, watch `:93-111`)
- Modify: `frontend/assets/css/work.css`(근거 장부 블록의 reduced-motion `:160-165` 자리 — 검토 중 규칙·`wk-review`, `:1216-1220` 간격)
- Modify: `frontend/pages/research/[id].vue`(옆 칸 `<aside class="rs-col-side">` 안 순서 — da80f23 `:183-190`)
- Test: `frontend/tests/unit/evidenceLedger.test.ts`(도우미 하나, `:81`·`:133` 기대값, 새 describe·새 it)

기준선: Task L4 뒤 수. `evidenceLedger.test.ts` 는 `15`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/evidenceLedger.test.ts` — `subq` 도우미(`:23-28`) 뒤에 도우미 하나. old:

```ts
function subq(idx: number, rounds: RoundView[]): SubqView {
  return {
    idx, title: `하위질문 ${idx + 1}`, seq: idx + 1, status: "done", rounds,
    verdict: "sufficient", note: "", adopted: null, parseFailed: false, error: null,
  };
}
```

new:

```ts
function subq(idx: number, rounds: RoundView[]): SubqView {
  return {
    idx, title: `하위질문 ${idx + 1}`, seq: idx + 1, status: "done", rounds,
    verdict: "sufficient", note: "", adopted: null, parseFailed: false, error: null,
  };
}

// 후보 이벤트(candidates)를 받아 자기점검을 기다리는 하위질문(리듀서가 세운 '검토 중' — SubqView.reviewing)
function reviewingSubq(idx: number, rounds: RoundView[], round: number | null, papers: ExcludedPaperView[]): SubqView {
  return { ...subq(idx, rounds), status: "running", verdict: null, reviewing: { round, papers } };
}
```

같은 파일 `:81` — 장부 모양이 세 묶음이 된다. old:

```ts
    expect(ledgerFrom([subq(0, [round(1, { verdict: null })])])).toEqual({ adopted: [], dropped: [] });
```

new:

```ts
    expect(ledgerFrom([subq(0, [round(1, { verdict: null })])])).toEqual({ adopted: [], dropped: [], reviewing: [] });
```

같은 파일 — `describe("ledgerLine·newlyAdded"` 바로 앞에 새 describe. old:

```ts
describe("ledgerLine·newlyAdded", () => {
```

new:

```ts
describe("ledgerFrom — 검토 중", () => {
  it("검토 중 = 하위질문의 후보 가운데 채택 더미에 없는 논문, 하위질문 순", () => {
    const l = ledgerFrom([
      subq(0, [round(1, { adoptedPapers: [adopted("C1", 1, C1)] })]),
      // 앞 하위질문이 이미 채택한 C1 은 검토 중에 두지 않는다(같은 논문이 두 더미에 함께 있지 않다)
      reviewingSubq(1, [round(1, { verdict: null })], 1, [
        excluded("C1", C1.title), excluded("C4", "온라인 수업의 윤리"), excluded("C5", "교사 연수 효과"),
      ]),
      reviewingSubq(2, [round(1), round(2), round(3, { verdict: null })], 3, [excluded("C5", "교사 연수 효과"), excluded("C6")]),
    ]);
    expect(l.reviewing).toEqual([
      { cntsId: "C4", title: "온라인 수업의 윤리", personalAuthor: "김철수", pubDate: "2015", subqIdx: [1], round: 1, isNew: true },
      { cntsId: "C5", title: "교사 연수 효과", personalAuthor: "김철수", pubDate: "2015", subqIdx: [1, 2], round: 1, isNew: true },
      { cntsId: "C6", title: null, personalAuthor: null, pubDate: null, subqIdx: [2], round: 3, isNew: true },
    ]);
    expect(l.adopted.map((p) => p.cntsId)).toEqual(["C1"]);
  });

  it("검토 중인 논문은 뺌 더미에 두지 않는다", () => {
    // 하위질문 1 이 뺀 X1 을 하위질문 2 가 다시 후보로 이었다 — 판정 전에는 검토 중에만 있고, 서지는 뺀 논문 목록에서 찾는다
    const l = ledgerFrom([
      subq(0, [round(1, { adoptedPapers: [adopted("C1", 1, C1)], excludedPapers: [excluded("X1", "무관한 논문 1")] })]),
      reviewingSubq(1, [round(1, { verdict: null })], 1, [excluded("X1")]),
    ]);
    expect(l.dropped).toEqual([]);
    expect(l.reviewing).toEqual([
      { cntsId: "X1", title: "무관한 논문 1", personalAuthor: "김철수", pubDate: "2015", subqIdx: [1], round: 1, isNew: true },
    ]);
  });

  it("점검 뒤(리듀서가 검토 중을 지움) 채택된 후보는 newlyAdded 로 새 채택이 된다", () => {
    const before = ledgerFrom([
      reviewingSubq(0, [round(1, { verdict: null })], 1, [excluded("C2", C2.title), excluded("X2", "무관한 논문 2")]),
    ]);
    expect(before.reviewing.map((p) => p.cntsId)).toEqual(["C2", "X2"]);
    expect(before.adopted).toEqual([]);
    // 점검이 오면 리듀서가 reviewing 을 지우고 그 회차에 판정·채택·뺌을 싣는다 — 채택은 떨어지고(wk-drop) 뺀 것은 가라앉는다(wk-sink)
    const after = ledgerFrom([
      subq(0, [round(1, { adoptedPapers: [adopted("C2", 1, C2)], excludedPapers: [excluded("X2", "무관한 논문 2")] })]),
    ]);
    expect(after.reviewing).toEqual([]);
    expect(newlyAdded(new Set(before.adopted.map((p) => p.cntsId)), after.adopted)).toEqual(["C2"]);
    expect(newlyAdded(new Set(before.dropped.map((p) => p.cntsId)), after.dropped)).toEqual(["X2"]);
  });

  it("hasLedger 는 채택 목록이 없어도 검토 중이 있으면 그린다", () => {
    // 첫 회차의 후보가 왔지만 아직 점검 전 — 채택 목록은 어디에도 없다
    expect(hasLedger([reviewingSubq(0, [round(1, { verdict: null })], 1, [excluded("C1", C1.title)])])).toBe(true);
    expect(hasLedger([subq(0, [round(1, { verdict: null })])])).toBe(false);
  });
});

describe("ledgerLine·newlyAdded", () => {
```

같은 파일 — `ledgerLine` 테스트(`:131-134`). old:

```ts
    expect(ledgerLine({ adopted: [], dropped: [] })).toBe("채택 0 · 뺌 0");
  });
```

new:

```ts
    expect(ledgerLine({ adopted: [], dropped: [], reviewing: [] })).toBe("채택 0 · 뺌 0");
  });

  it("검토 중이 있으면 '· 검토 중 n' 을 잇는다", () => {
    const waiting = ledgerFrom([
      reviewingSubq(0, [round(1, { adoptedPapers: [adopted("C1", 1, C1)] }), round(2, { verdict: null })], 2, [
        excluded("C2", C2.title), excluded("C3", C3.title),
      ]),
    ]);
    expect(ledgerLine(waiting)).toBe("채택 1 · 뺌 0 · 검토 중 2");
  });
```

(`adopted`·`excluded`·`round`·`C1`~`C3` 는 이 파일 머리의 기존 도우미다 — `:6-32`. `excluded(id, title)` 은 제목이 있으면 저자 `김철수`·연도 `2015` 를 싣는다.)

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/evidenceLedger.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  6 failed | 14 passed (20)` — 실패 여섯: `ledgerFrom — 채택 > 검색만 끝나고 점검을 기다리는 회차는 …`(`expected { adopted: [], dropped: [] } to deeply equal { adopted: [], dropped: [], …(1) }`), 새 describe 넷(`expected undefined to deeply equal [ { cntsId: 'C4', …(6) }, …(2) ]`·`expected [ { cntsId: 'X1', …(6) } ] to deeply equal []`·`TypeError: Cannot read properties of undefined (reading 'map')`·`expected false to be true`), `ledgerLine·newlyAdded > 검토 중이 있으면 …`(`expected '채택 1 · 뺌 0' to be '채택 1 · 뺌 0 · 검토 중 2'`). 바꾼 `ledgerLine({ …, reviewing: [] })` 줄은 지금도 통과한다(남는 칸을 읽지 않는다).

- [ ] **Step 3: 장부 묶음을 구현한다**

`frontend/utils/evidenceLedger.ts` — 머리 주석(`:2-5`). old:

```ts
// 근거 장부(spec §3·§4 S2) — 탐색 중 채택 논문이 쌓이고 자기점검이 뺀 논문이 '뺌' 더미로 내려가는 딥리서치 화면의
// 시각화. 재료는 06a 가 받아 둔 회차 기록(SubqView.rounds[].adoptedPapers·excludedPapers)뿐이다 — 점검 이벤트와
// 진행 저장본이 같은 모양으로 채우므로 라이브로 본 장부와 다시 연 화면의 장부가 같다. 새 SSE 처리는 없다
import type { RoundView, SubqView } from "~/types/research";
```

new:

```ts
// 근거 장부(spec §3·§4 S2) — 탐색 중 채택 논문이 쌓이고 자기점검이 뺀 논문이 '뺌' 더미로 내려가는 딥리서치 화면의
// 시각화. 채택·뺌의 재료는 06a 가 받아 둔 회차 기록(SubqView.rounds[].adoptedPapers·excludedPapers)뿐이다 — 점검 이벤트와
// 진행 저장본이 같은 모양으로 채우므로 라이브로 본 장부와 다시 연 화면의 장부가 같다.
// 후보 이벤트(candidates)로 리듀서가 세운 '검토 중'(SubqView.reviewing)을 세 번째 묶음으로 둔다. 저장되지 않는 화면 상태라
// 재접속·끝난 잡에는 없다
import type { RoundView, SubqView } from "~/types/research";
```

같은 파일 — `LedgerPaper.round` 주석(`:14`). old:

```ts
  // 채택: 처음 채택된 회차 · 뺌: 처음 뺀 회차
  round: number;
```

new:

```ts
  // 채택: 처음 채택된 회차 · 뺌: 처음 뺀 회차 · 검토 중: 후보가 온 회차(모르면 0)
  round: number;
```

`Ledger`(`:20-23`). old:

```ts
export interface Ledger {
  adopted: LedgerPaper[];
  dropped: LedgerPaper[];
}
```

new:

```ts
export interface Ledger {
  adopted: LedgerPaper[];
  dropped: LedgerPaper[];
  // 자기점검을 기다리는 후보 — 판정이 오면 채택·뺌으로 옮긴다
  reviewing: LedgerPaper[];
}
```

`hasLedger`(`:31-34`). old:

```ts
// 회차 끝 채택 목록을 기록하기 전 잡(06a 전)은 어느 회차에도 목록이 없다 — 장부를 그리지 않는다
export function hasLedger(subqs: SubqView[]): boolean {
  return subqs.some((sq) => sq.rounds.some((r) => r.adoptedPapers.length > 0));
}
```

new:

```ts
// 회차 끝 채택 목록을 기록하기 전 잡(06a 전)은 어느 회차에도 목록이 없다 — 장부를 그리지 않는다. 첫 회차의 후보가
// 점검 전에 왔으면(검토 중) 채택 목록이 없어도 그린다
export function hasLedger(subqs: SubqView[]): boolean {
  return subqs.some((sq) => !!sq.reviewing?.papers.length || sq.rounds.some((r) => r.adoptedPapers.length > 0));
}
```

`ledgerFrom` — 뺌 더미 앞(`:97-104`)에 검토 중을 먼저 만들고 뺌에서 뺀다. old:

```ts
  // 뺌: 탐색이 지나간 순서(하위질문 순 → 회차 순)로 중복 없이. 다른 하위질문이나 뒤 회차에 다시 채택된 논문은 빼지
  // 않은 것으로 본다 — 장부의 두 더미에 같은 논문이 함께 있지 않다
  const dropped = new Map<string, LedgerPaper>();
  for (const sq of subqs) {
    const last = lastChecked(sq);
    for (const r of sq.rounds) {
      for (const p of r.excludedPapers) {
        if (adopted.has(p.cntsId)) continue;
```

new:

```ts
  // 검토 중: 하위질문 순 → 후보 순으로 채택 더미에 없는 후보를 중복 없이. 서지는 후보가 실은 것을 먼저, 없으면 앞에서
  // 모은 서지를 쓴다. 판정 전이라 모두 새로 든 것이다
  const reviewing = new Map<string, LedgerPaper>();
  for (const sq of subqs) {
    if (!sq.reviewing) continue;
    for (const p of sq.reviewing.papers) {
      if (adopted.has(p.cntsId)) continue;
      const known = reviewing.get(p.cntsId);
      if (known) {
        addSubq(known, sq.idx);
        continue;
      }
      const b = bib.get(p.cntsId);
      reviewing.set(p.cntsId, {
        cntsId: p.cntsId,
        title: p.title || b?.title || null,
        personalAuthor: p.personalAuthor ?? b?.personalAuthor ?? null,
        pubDate: p.pubDate ?? b?.pubDate ?? null,
        subqIdx: [sq.idx],
        round: sq.reviewing.round ?? 0,
        isNew: true,
      });
    }
  }

  // 뺌: 탐색이 지나간 순서(하위질문 순 → 회차 순)로 중복 없이. 다른 하위질문이나 뒤 회차에 다시 채택된 논문, 다른 하위질문이
  // 다시 후보로 이어 검토 중인 논문은 두지 않는다 — 장부의 더미 셋에 같은 논문이 함께 있지 않다
  const dropped = new Map<string, LedgerPaper>();
  for (const sq of subqs) {
    const last = lastChecked(sq);
    for (const r of sq.rounds) {
      for (const p of r.excludedPapers) {
        if (adopted.has(p.cntsId) || reviewing.has(p.cntsId)) continue;
```

반환과 `ledgerLine`(`:126-131`). old:

```ts
  return { adopted: [...adopted.values()], dropped: [...dropped.values()] };
}

export function ledgerLine(l: Ledger): string {
  return `채택 ${l.adopted.length} · 뺌 ${l.dropped.length}`;
}
```

new:

```ts
  return { adopted: [...adopted.values()], dropped: [...dropped.values()], reviewing: [...reviewing.values()] };
}

export function ledgerLine(l: Ledger): string {
  const head = `채택 ${l.adopted.length} · 뺌 ${l.dropped.length}`;
  return l.reviewing.length ? `${head} · 검토 중 ${l.reviewing.length}` : head;
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/evidenceLedger.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  20 passed (20)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: 실패 0 — `Tests` 는 Task L4 뒤 수 + 5

- [ ] **Step 5: 장부 부품과 스타일에 '검토 중'을 그린다**

`frontend/components/work/EvidenceLedger.vue` — 채택 목록 끝(`:22`)과 뺌 묶음(`:24`) 사이. 채택 목록의 닫는 `</ol>` 은 파일에 둘이지만 그 뒤에 빈 줄과 뺌 묶음 `<template>` 이 오는 자리는 하나다. old:

```html
    </ol>

    <template v-if="ledger.dropped.length">
```

new:

```html
    </ol>

    <!-- 검토 중 — 후보 이벤트(candidates)로 세운 이번 회차의 후보. 채택 목록 끝(지금 도는 하위질문의 묶음) 바로 아래에
         선다 — 점검이 끝나면 리듀서가 지우고, 채택은 바로 위 목록 끝에 떨어져 박히고(wk-drop) 뺀 것은 아래 뺌 더미로
         가라앉는다(wk-sink). 저장되지 않는 값이라 다시 연 화면·끝난 잡에는 없다 -->
    <template v-if="ledger.reviewing.length">
      <h3 class="wk-ledger__pile-title">검토 중 {{ ledger.reviewing.length }}</h3>
      <ol class="wk-ledger__list wk-ledger__list--reviewing" aria-label="자기점검을 기다리는 후보">
        <li v-for="p in ledger.reviewing" :key="p.cntsId" class="wk-ledger__paper is-reviewing">
          <span class="wk-ledger__title">{{ p.title || p.cntsId }}</span>
          <span class="wk-ledger__meta">{{ byline(p) }} · 하위질문 {{ subqLabel(p) }}</span>
        </li>
      </ol>
    </template>

    <template v-if="ledger.dropped.length">
```

같은 파일 script — 카드를 그리는 조건(`:70`). old:

```ts
const shown = computed(() => hasLedger(props.subqs));
```

new:

```ts
// 탐색 중 한 번 선 장부는 탐색이 끝날 때까지 둔다 — 첫 점검이 채택 0편(후보 전부 무관 제외)이면 검토 중이 지워지는
// 순간 채택 목록이 어디에도 없어 카드째 사라졌다가 다음 회차 후보에 다시 선다(뺌 더미가 가라앉는 것도 보이지 않는다)
const seenLive = ref(false);
const shown = computed(() => hasLedger(props.subqs) || (props.live && seenLive.value));
watch(
  [shown, () => props.live],
  ([s, live]) => {
    if (s && live) seenLive.value = true;
  },
  { immediate: true },
);
```

(`ref`·`watch` 는 이 파일 머리 import(`:49`)에 이미 있다. `shown` 만 보면 장부가 이미 선 채로 `live` 가 켜질 때(앞 시도의 채택이 남은 채 다시 도는 잡처럼 `shown` 이 바뀌지 않는 경우) `seenLive` 가 켜지지 않으므로 `live` 도 함께 본다. 판단이 한 줄이라 `utils` 로 빼지 않고 `nuxi typecheck`·`npm run build` 로 본다.)

같은 파일 script — 직전 장부의 기준선(`:78-79`). old:

```ts
let prevDropped: Set<string> | null = null;
```

new:

```ts
let prevDropped: Set<string> | null = null;
let prevReviewing: Set<string> | null = null;
```

같은 파일 — `watch(ledger, …)` 본문(`:93-111`). old:

```ts
    const adopted = props.live ? newlyAdded(prevAdopted, l.adopted) : [];
    const dropped = props.live ? newlyAdded(prevDropped, l.dropped) : [];
    prevAdopted = new Set(l.adopted.map((p) => p.cntsId));
    prevDropped = new Set(l.dropped.map((p) => p.cntsId));
    if (props.live) {
      follow(adoptedList, adopted.length > 0);
      follow(droppedList, dropped.length > 0);
    }
    if (!adopted.length && !dropped.length) return;
    fresh.value = { adopted, dropped };
    announcement.value = [
      adopted.length ? `근거 ${adopted.length}편 채택` : "",
      dropped.length ? `${dropped.length}편 뺌` : "",
    ]
      .filter(Boolean)
      .join(", ");
    // 같은 문장이 연달아 와도 읽히게 새 노드로 넣는다(템플릿의 알림 영역 주석)
    announceSeq.value += 1;
    if (freshTimer) clearTimeout(freshTimer);
```

new:

```ts
    const adopted = props.live ? newlyAdded(prevAdopted, l.adopted) : [];
    const dropped = props.live ? newlyAdded(prevDropped, l.dropped) : [];
    // 검토 중은 떨어지지 않고 흐린 카드로 선다(반짝임은 CSS) — 새로 선 후보 수만 알린다
    const reviewing = props.live ? newlyAdded(prevReviewing, l.reviewing) : [];
    prevAdopted = new Set(l.adopted.map((p) => p.cntsId));
    prevDropped = new Set(l.dropped.map((p) => p.cntsId));
    prevReviewing = new Set(l.reviewing.map((p) => p.cntsId));
    if (props.live) {
      follow(adoptedList, adopted.length > 0);
      follow(droppedList, dropped.length > 0);
    }
    if (!adopted.length && !dropped.length && !reviewing.length) return;
    announcement.value = [
      reviewing.length ? `후보 ${reviewing.length}편 검토 중` : "",
      adopted.length ? `근거 ${adopted.length}편 채택` : "",
      dropped.length ? `${dropped.length}편 뺌` : "",
    ]
      .filter(Boolean)
      .join(", ");
    // 같은 문장이 연달아 와도 읽히게 새 노드로 넣는다(템플릿의 알림 영역 주석)
    announceSeq.value += 1;
    // 후보만 선 바뀜은 앞서 떨어지던 채택·뺌의 효과를 끊지 않는다
    if (!adopted.length && !dropped.length) return;
    fresh.value = { adopted, dropped };
    if (freshTimer) clearTimeout(freshTimer);
```

(그 아래 `freshTimer = setTimeout(…, FRESH_MS);` 와 `{ immediate: true }` 는 그대로다. 기준선은 지금처럼 마운트 때 잡는다 — 다시 연 화면은 처음부터 `prevReviewing` 이 빈 집합이고 리듀서가 후보를 세우지 않으므로 알림도 없다.)

`frontend/assets/css/work.css` — 근거 장부 블록 끝의 reduced-motion(`:160-165`, `@keyframes wk-sink` 바로 뒤). old:

```css
@media (prefers-reduced-motion: reduce) {
  .wk-ledger__paper.is-fresh,
  .wk-ledger__list--dropped .wk-ledger__paper.is-fresh {
    animation: none;
  }
}
```

new:

```css
/* 검토 중 — 후보 이벤트(candidates)로 세운 이번 회차의 후보. 흐린 점선 카드가 천천히 반짝이다 점검이 끝나면 채택(wk-drop)·
   뺌(wk-sink)으로 옮긴다. 후보 목록은 채택 목록보다 낮게 둔다 — 아래 뺌 더미가 옆 칸 밖으로 밀려나지 않게 */
.wk-ledger__list--reviewing {
  max-height: 9rem;
}
.wk-ledger__paper.is-reviewing {
  opacity: 0.7;
  border-style: dashed;
  border-color: var(--skx-border-c2);
  animation: wk-review 1.6s ease-in-out infinite;
}
@keyframes wk-review {
  50% {
    opacity: 0.45;
  }
}
@media (prefers-reduced-motion: reduce) {
  .wk-ledger__paper.is-fresh,
  .wk-ledger__list--dropped .wk-ledger__paper.is-fresh,
  .wk-ledger__paper.is-reviewing {
    animation: none;
  }
}
```

(이 블록은 `/* ── 진행 막대(WorkStepper) ── */`(`:167`) 앞, 근거 장부 블록 안에 머문다. `wk-review` 의 0%·100% 는 카드의 `opacity: 0.7` 을 쓴다 — `rs-blink` 와 같은 꼴.)

- [ ] **Step 6: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff -U0 -- frontend/assets/css/work.css | grep "^@@"`
Expected: 두 줄 `@@ -159,0 +160,16 @@`·`@@ -162 +178,2 @@` — 근거 장부 블록의 reduced-motion 자리(`:159-165`)뿐이다. 06e 몫의 다른 블록을 건드리지 않았다(Task 0 이 06e 를 받지 않은 dev 에서 땄으면 `work.css` 는 da80f23 그대로라 이 줄 번호가 맞다)

- [ ] **Step 7: 커밋한다(①)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/evidenceLedger.ts frontend/components/work/EvidenceLedger.vue frontend/assets/css/work.css frontend/tests/unit/evidenceLedger.test.ts && git status --short && git commit -m "[Feat] round06d — 근거 장부에 '검토 중' 후보를 세웠다가 점검 뒤 채택은 떨어져 박히고 뺀 것은 가라앉게 한다. ledgerFrom 이 06c 후보 이벤트로 세운 SubqView.reviewing 을 세 번째 묶음(reviewing)으로 모은다 — 하위질문 순, 이미 채택된 논문은 빼고, 검토 중인 논문은 뺌 더미에 두지 않는다(더미 셋에 같은 논문이 함께 있지 않다). 검토 중 묶음은 채택 목록 끝(지금 도는 하위질문의 자리) 바로 아래·뺌 더미 앞에 서고, 점검이 오면 리듀서가 검토 중을 지우고 그 회차의 채택은 바로 위 목록 끝에, 뺀 것은 바로 아래 뺌 더미로 기존 wk-drop·wk-sink 로 움직인다. 검토 중 카드는 흐린 점선에 천천히 반짝이고(wk-review, 움직임 줄이기면 멈춤) 새로 선 후보는 '후보 n편 검토 중'으로 읽힌다. 첫 후보가 점검 전에 와도 장부를 그리고 머리 줄에 '· 검토 중 n'을 잇는다. 탐색 중 한 번 선 장부 카드는 탐색이 끝날 때까지 둔다 — 첫 점검이 채택 0편이어도 카드가 사라졌다 다시 서지 않는다"
```

- [ ] **Step 8: 근거 장부를 옆 칸 맨 위로 옮긴다**

`frontend/pages/research/[id].vue` — 옆 칸(da80f23 `:183-190`, `<aside class="rs-col-side">` 는 파일에 하나). old:

```html
          <aside class="rs-col-side">
            <ProgressPanel :view="view" :phase="phase" :reveal-excluded="revealExcluded" :queue-note="queueText" />
            <!-- 근거 장부 — 회차마다 채택 논문이 쌓이고 critic 이 뺀 논문은 '뺌'으로 내려간다. 바깥 v-if 없이 늘 그린다:
                 장부가 빈 때부터 떠 있어야 첫 회차의 채택이 떨어진다. 06a 전 잡은 컴포넌트가 카드를 그리지 않는다 -->
            <div class="wk-side-ledger">
              <EvidenceLedger :subqs="view.subqs" :live="phase === 'exploring'" />
            </div>
          </aside>
```

new:

```html
          <aside class="rs-col-side">
            <!-- 근거 장부 — 옆 칸 맨 위. 회차마다 '검토 중' 후보가 섰다가 점검 뒤 채택 논문은 떨어져 쌓이고 critic 이 뺀 논문은
                 '뺌'으로 내려간다 — 긴 탐색 타임라인 아래 화면 밖에서 일어나지 않게 진행 패널 위에 둔다. 바깥 v-if 없이 늘 그린다:
                 장부가 빈 때부터 떠 있어야 첫 회차의 채택이 떨어진다. 06a 전 잡은 컴포넌트가 카드를 그리지 않는다 -->
            <div class="wk-side-ledger">
              <EvidenceLedger :subqs="view.subqs" :live="phase === 'exploring'" />
            </div>
            <ProgressPanel :view="view" :phase="phase" :reveal-excluded="revealExcluded" :queue-note="queueText" />
          </aside>
```

`frontend/assets/css/work.css` — 옆 칸 장부 간격(`:1216-1220`). old:

```css
/* 진행 패널 아래 근거 장부 — 옆 칸(rs-col-side)에는 간격 규칙이 없다. 감싸개는 늘 그려지므로(장부가 빈 때부터 떠 있어야
   첫 회차가 떨어진다) 간격은 장부 카드가 있을 때만 — 06a 전 잡에 빈 간격이 남지 않게 */
.wk-side-ledger .wk-ledger {
  margin-top: 1.2rem;
}
```

new:

```css
/* 옆 칸 맨 위 근거 장부(진행 패널 위) — 옆 칸(rs-col-side)에는 간격 규칙이 없다. 감싸개는 늘 그려지므로(장부가 빈 때부터
   떠 있어야 첫 회차가 떨어진다) 간격은 장부 카드가 있을 때만 — 06a 전 잡에 빈 간격이 남지 않게 */
.wk-side-ledger .wk-ledger {
  margin-bottom: 1.2rem;
}
```

- [ ] **Step 9: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Step 4 와 같은 수(+0)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -n "wk-side-ledger\|<ProgressPanel" "frontend/pages/research/[id].vue"`
Expected: 두 줄, `class="wk-side-ledger"` 의 줄 번호가 `<ProgressPanel` 보다 작다(장부가 먼저)

- [ ] **Step 10: 커밋한다(②)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "frontend/pages/research/[id].vue" frontend/assets/css/work.css && git status --short && git commit -m "[Feat] round06d — 근거 장부를 연구 화면 옆 칸 맨 위(진행 패널 위)로 옮긴다(정함 10). 탐색 타임라인이 길어지면 장부가 화면 밖 아래에 있어 '검토 중'이 서고 채택이 떨어지는 움직임이 보이지 않았다. 장부는 빈 때부터 마운트돼 있어야 첫 회차가 떨어지므로 감싸개는 그대로 늘 그리고, 장부 카드 간격만 아래쪽(margin-bottom)으로 바꾼다. EvidenceLedger 부품과 떨어지는 효과(wk-drop·wk-sink)는 그대로다"
```

---

### Task L6: (선행 조건 — 06c dev 머지 뒤) dev 받기·"이렇게 이해했어요" 바인딩 두 곳

spec §12-2 '화면 한 줄 — 06d 가 잇는 것'(`[id].vue` 계획 중 대기 카드 da80f23 `:80-83`, 승인 대기 PlanCard `:84-92`) · §12-5 '"이렇게 이해했어요" 바인딩' · §12-6 '06c 의 화면 한 줄은 dev 에 들어간 뒤 06d 가 이어 nuxt 배포에'. 넓히기를 켜면 계획은 원 질문이 아니라 넓힌 문장으로 세워진다 — 06c 가 그 문장을 고르는 함수·문구·PlanCard prop 을 만들고, 06d 는 dev 를 받아 연구 화면의 두 곳에 잇는다.

**선행 조건:** 06c(`feat/round06c-query-broadening`)가 dev 에 머지돼 있어야 한다. 아니면 이 Task 를 멈추고(나머지 Task·마무리의 회귀·리뷰는 먼저 끝내 둔다) 06c 가 들어온 뒤 돌아온다 — 06d 의 dev 머지는 어차피 06c 운영 배포(10/13~14) 뒤다. 06e 와의 순서와는 묶이지 않는다(06e 가 먼저 dev 에 있으면 이 merge 로 06e 도 함께 들어온다 — 그때 Task N8 의 merge 는 받을 것이 없을 수 있다).

**알아 둘 것:**
- **06c 계약(06c 계획 정함 21·22 — 06c 계획의 화면 한 줄 Task):** `utils/researchEvents.ts` 의 `questionUsedFromSteps(steps: ResearchStepRow[], question: string): string | null` — 마지막 계획 단계 result 의 `question_used` 가 문자열이 아니거나 비었거나, NFKC·공백 정리 뒤 원 질문과 같으면 `null`(숨김 판단이 함수 안에 있다). `understoodLine(questionUsed: string): string` = `이렇게 이해했어요: …`(접두를 함수가 붙인다 — 템플릿에 접두를 다시 쓰지 않는다). PlanCard 선택 prop `questionUsed?: string | null`(null 이 아니면 머리에 `<p class="rs-muted rs-plan__understood">`). `StepResult.question_used?`·`terms?`·`elapsed_ms?`. **06d 는 같은 판단·문구 함수를 따로 만들지 않는다** — 같은 이름을 두 파일이 내보내면 Nuxt 자동 import 가 `WARN Duplicated imports` 를 되살린다(Task D2 가 없앤 경고와 같은 꼴).
- **계획 중 카드에도 뜬다.** 06c 는 넓히기가 끝나면 계획이 나오기 전에 도는(running) 계획 단계의 result 에 `{question_used, terms}` 를 먼저 싣는다(06c 정함 6 — 중간 알림). `applyStep` 은 그 result 를 단계 행에 그대로 싣고(`researchEvents.ts:356-374`) `subquestions` 가 없어 계획은 비어 있으므로 화면은 계획 중 그대로다 — 그 사이 계획 중 카드에 한 줄이 선다. 승인 대기에서는 PlanCard 머리에 선다.
- **스타일은 더하지 않는다(공통 계약 'DOM id·클래스·CSS 토큰' 표의 `.rs-plan__understood` 행).** `.rs-muted`(`research.css:95-100` — `margin: 0`·0.65rem·`--skx-gray-1`)만으로 PlanCard 머리(`.rs-card__head` gap 0.2rem)와 대기 카드 글 묶음(Task D2 의 `.rs-card__text` gap 0.2rem) 안에서 줄이 맞는다. 두 곳이 같은 클래스 묶음(`rs-muted rs-plan__understood`)을 써서 나중에 스타일을 줄 때 한 규칙으로 함께 바뀐다(06c 계획도 `rs-plan__understood` 를 규칙 없는 고리로 적었다 — 06c 정함 22).
- **merge 충돌(사본에서 실측):** 06c 가 Task 0 뒤에 dev 에 들어왔으면 `frontend/tests/unit/researchEvents.test.ts` 한 파일이 두 곳에서 충돌한다 — ① import 목록(06c 는 `mergeEvidence,` 와 `queueLine,` 사이에 `questionUsedFromSteps,`, `synthProgress,` 뒤에 `understoodLine,` 을 넣었고 06d 는 D2 에서 `queueLine,` 을 지우고 L3 에서 `roundStatusLabel,` 을 넣었다) ② 파일 끝(06d 의 describe 둘 — 회차 미세 상태·탐색 후보 — 과 06c 의 describe 셋 — `questionUsedFromSteps`·`understoodLine`·계획 중간 알림 — 이 같은 자리에 붙었다). `types/research.ts`·`utils/researchEvents.ts`·`PlanCard.vue` 는 서로 다른 블록이라 저절로 합쳐진다. 06c 가 Task 0 전에 이미 dev 에 있었으면 충돌 없이 `Already up to date.`(또는 다른 커밋만)다.
- 06c 의 백엔드(`app/…`)·문서·`frontend/tests/fixtures/term_checks.json` 도 이 merge 로 들어온다 — 06d 는 그 파일을 고치지 않는다(마무리의 '고치지 않은 파일' 확인은 `dev...HEAD` 라 06d 자신의 변경만 본다).

**Files:**
- (merge) dev — 06c 의 `frontend/types/research.ts`·`frontend/utils/researchEvents.ts`·`frontend/components/research/PlanCard.vue`·`frontend/tests/unit/researchEvents.test.ts`·`frontend/tests/fixtures/term_checks.json`·백엔드·문서(06e 가 먼저 들어왔으면 06e 의 파일도)
- Modify: `frontend/pages/research/[id].vue`(researchEvents import · 앵커 `const queueText = computed(` 아래 computed 하나 · 계획 중 카드 · 승인 대기 PlanCard prop)

기준선: 앞 Task(N9 — 전역 실행 순서에서 이 Task 바로 앞) 뒤 수.

- [ ] **Step 1: 선행 조건을 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git log dev --merges --oneline | grep -c "round06c-query-broadening"`
Expected: `1` 이상

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git show dev:frontend/utils/researchEvents.ts | grep -c "export function questionUsedFromSteps\|export function understoodLine"`
Expected: `2`

둘 중 하나라도 `0` 이면 **여기서 멈춘다** — 06c 가 아직 dev 에 없다. 다음 Task(N8)로 가지 않고, 06c 머지를 기다린다(마무리 Task 의 회귀·리뷰는 먼저 돌려 두고 이 Task 뒤에 다시 돌린다).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git status --short`
Expected: (빈 출력 — 고친 채 남은 파일이 없다. 있으면 그 Task 를 먼저 커밋한다)

- [ ] **Step 2: dev 를 받는다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git merge dev -m "Merge dev into feat/round06d-research-progress-screen — 06c 질의(PlanCard '이렇게 이해했어요' 한 줄·questionUsedFromSteps·candidates 이벤트) 받기"`
Expected: 다음 셋 중 하나 —
- (가) 06c 가 Task 0 뒤에 dev 에 들어왔다: `Auto-merging frontend/types/research.ts`·`Auto-merging frontend/utils/researchEvents.ts` 와 함께 `CONFLICT (content): Merge conflict in frontend/tests/unit/researchEvents.test.ts`, 끝 줄 `Automatic merge failed; fix conflicts and then commit the result.` → Step 3
- (나) 06c 가 Task 0 전에 이미 dev 에 있었고 그 뒤 dev 가 그대로다: `Already up to date.` → Step 3 을 건너뛰고 Step 4
- (다) 충돌 없이 merge 커밋이 생겼다(06c 는 Task 0 전에 있었고 그 뒤 다른 커밋만 들어왔다) → Step 4

(메시지에 Co-Authored-By 줄을 넣지 않는다.)

- [ ] **Step 3: 충돌을 푼다(가의 경우)**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --name-only --diff-filter=U`
Expected: `frontend/tests/unit/researchEvents.test.ts` 한 줄(06e 도 함께 들어왔으면 아래 '다른 파일' 규칙의 파일이 더 나올 수 있다)

`researchEvents.test.ts` 는 **06d 쪽 파일을 바탕으로 06c 의 두 import 이름과 파일 끝 describe 묶음을 다시 붙인다.** 06c 가 이 파일에 한 일은 그 둘뿐이다(06c 계획의 화면 한 줄 Task).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git checkout --ours frontend/tests/unit/researchEvents.test.ts && git show dev:frontend/tests/unit/researchEvents.test.ts | grep -c "^const ASKED = "`
Expected: `Updated 1 path from the index` 와 `1` — 06c 의 describe 묶음은 `const ASKED = "…";` 로 시작해 파일 끝까지다

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && (printf '\n'; git show dev:frontend/tests/unit/researchEvents.test.ts | sed -n '/^const ASKED = /,$p') >> frontend/tests/unit/researchEvents.test.ts && tail -3 frontend/tests/unit/researchEvents.test.ts`
Expected: 06c 의 마지막 describe(`applyResearchEvent — 계획 중간 알림(06c)`) 끝 세 줄 — `    expect(questionUsedFromSteps(planned.steps, planned.question)).toBe(BROADENED);`·`  });`·`});`

(`git show` 는 저장소 글(LF)을 내므로 붙인 부분만 LF 다 — `core.autocrlf=true` 라 `git add` 때 맞춰지니 그대로 둔다. `grep -c "^const ASKED = "` 가 `0` 이면 06c 의 실제 글이 계획과 다르다 — `git diff $(git merge-base HEAD dev) dev -- frontend/tests/unit/researchEvents.test.ts` 로 06c 가 파일 끝에 더한 describe 묶음을 보고 그 묶음을 파일 끝에 옮겨 적는다.)

이어서 import 목록에 06c 의 두 이름을 넣는다(Edit 도구). old:

```ts
  mergeEvidence,
  refreshView,
```

new:

```ts
  mergeEvidence,
  questionUsedFromSteps,
  refreshView,
```

old:

```ts
  synthProgress,
  withPlan,
```

new:

```ts
  synthProgress,
  understoodLine,
  withPlan,
```

**`queueLine,` 은 되살리지 않는다** — 06d 는 `researchEvents` 의 다시 내보내기를 지웠고(Task D2) 이 파일은 `import { queueLine } from "~/utils/queueLine";` 으로 읽는다. 되살리면 `queueLine` describe 가 `undefined` 를 부르고 typecheck 가 `has no exported member 'queueLine'` 으로 떨어진다.

**다른 파일이 충돌하면(06e 가 먼저 dev 에 들어왔을 때):** `[id].vue` — 06e 의 단계 본문(`<div v-if="stepMode" class="wk-body">` 블록, da80f23 `:57-75`)·리스너·`workPanelOpen` 은 06e 쪽을, 06d 가 고친 다른 hunk 는 06d 쪽을 남기고, import 블록은 두 쪽 줄을 모두 남긴다(한 줄에 한 이름 묶음). `work.css` — 06d 는 근거 장부 블록과 `.wk-side-ledger .wk-ledger` 간격만 고쳤으니 나머지 hunk 는 06e 쪽. 같은 줄을 두 쪽이 다르게 바꿨으면 멈추고 06e 세션과 맞춘다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "^<<<<<<<\|^=======\|^>>>>>>>" frontend/tests/unit/researchEvents.test.ts`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/tests/unit/researchEvents.test.ts && git diff --name-only --diff-filter=U && git commit --no-edit --cleanup=strip && git log -1 --format=%B`
Expected: 충돌 파일 목록은 빈 출력, 그다음 커밋 본문은 `Merge dev into feat/round06d-research-progress-screen — 06c 질의(PlanCard '이렇게 이해했어요' 한 줄·questionUsedFromSteps·candidates 이벤트) 받기` 한 줄(과 끝의 빈 줄)뿐이다 — 본문에 `# Conflicts:`·`#(탭)frontend/tests/unit/researchEvents.test.ts` 줄이 없다. `--no-edit` 만 쓰면 정리 모드가 whitespace 라(저장소에 `commit.cleanup` 설정이 없다) MERGE_MSG 의 `# Conflicts` 두 줄이 커밋 본문에 남는다 — 같은 PC 의 git 2.50.1 로 재 보았고, 저장소의 최근 merge 30개 본문에는 `# Conflicts` 가 0건이다. (다른 파일을 풀었으면 그 파일도 `git add <파일>` 로 하나씩 더한 뒤 커밋한다)

- [ ] **Step 4: 06c 의 실제 이름을 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -n "export function questionUsedFromSteps\|export function understoodLine" frontend/utils/researchEvents.ts`
Expected: 두 줄 — `export function questionUsedFromSteps(steps: ResearchStepRow[], question: string): string | null {`·`export function understoodLine(questionUsed: string): string {`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -n "questionUsed" frontend/components/research/PlanCard.vue`
Expected: 세 줄 이상 — `<p v-if="questionUsed" class="rs-muted rs-plan__understood">{{ understoodLine(questionUsed) }}</p>`·`questionUsed?: string | null;`·`{ editable: false, busy: false, subqs: () => [], questionUsed: null },`(그 위 주석 줄이 함께 나올 수 있다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -A 3 'await emit("candidates"' app/services/research/runner.py`
Expected: 네 줄(Task L4 Step 0 의 기대와 같은 글자·들여쓰기) — `await emit("candidates", {`·`"subq_idx": subq.idx, "round": round_no,`·`"papers": [_paper_brief(state.evidence[e]) for e in linked],`·`})`(Task L4 의 `CandidatesEvent` 와 같다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -rln "export function questionUsedFromSteps\|export function understoodLine" frontend/utils frontend/composables`
Expected: `frontend/utils/researchEvents.ts` 한 줄 — 같은 이름을 내보내는 06d 파일이 없다

이름·시그니처·후보 이벤트 칸이 위와 다르면 **06c 를 따른다**: 함수 이름이 다르면 Step 6 의 바인딩을 그 이름으로 쓰고, 후보 이벤트 칸(`subq_idx`·`round`·`papers`)이 다르면 이 Task 안에서 `types/research.ts` 의 `CandidatesEvent`·`researchEvents.ts` 의 `applyCandidates`·Task L4 테스트의 `candidates()` 도우미를 06c 의 칸으로 고쳐 `[Fix] round06d — 06c 후보 이벤트 필드 이름에 맞춘다 …` 커밋을 먼저 낸다(파일은 `git add` 로 하나씩).

- [ ] **Step 5: 받은 뒤 회귀를 본다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchEvents.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  123 passed (123)`(L4 뒤 116 + 06c 의 7 — (나)·(다)의 경우는 이미 `123`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: 실패 0 — `Tests` 는 Step 2 앞 수 + dev 가 더한 테스트 수(06c 만 받았으면 + 7, 06e 도 받았으면 06e 의 프론트 테스트 수만큼 더, (나)면 + 0). 나온 수를 이 뒤 Task 의 '앞 수' 로 삼는다

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"`
Expected: `0`

- [ ] **Step 6: 두 곳에 잇는다**

`frontend/pages/research/[id].vue` — researchEvents import(Task D2 가 만든 줄). old:

```ts
import { researchPhase } from "~/utils/researchEvents";
```

new:

```ts
import { questionUsedFromSteps, researchPhase, understoodLine } from "~/utils/researchEvents";
```

넓힌 질문 computed — 앵커 `const queueText = computed(`(da80f23 `:259`) 바로 아래. old:

```ts
const queueText = computed(() => (view.value ? queueLine(view.value.queue) : null));
```

new:

```ts
const queueText = computed(() => (view.value ? queueLine(view.value.queue) : null));
// 계획이 쓴 넓힌 질문("이렇게 이해했어요" 한 줄). 원 질문과 같거나(넓히기를 껐거나 원문으로 물러남) 넓히기 전 잡이면 null
const questionUsed = computed(() => (view.value ? questionUsedFromSteps(view.value.steps, view.value.question) : null));
```

계획 중 카드 — Task D2 가 만든 글 묶음(da80f23 `:80-83` 자리). old:

```html
                <div class="rs-card__text">
                  <p>연구 계획을 세우는 중입니다</p>
                </div>
```

new:

```html
                <div class="rs-card__text">
                  <p>연구 계획을 세우는 중입니다</p>
                  <!-- 넓히기가 끝나면 계획이 나오기 전에도 도는 계획 단계에 넓힌 질문이 먼저 실려 온다 -->
                  <p v-if="questionUsed" class="rs-muted rs-plan__understood">{{ understoodLine(questionUsed) }}</p>
                </div>
```

승인 대기 PlanCard(da80f23 `:84-92` — 속성 줄 사이에 한 줄). old:

```html
              <PlanCard
                v-else-if="phase === 'awaiting'"
                :plan="view.plan"
                :max="maxSubquestions"
                editable
```

new:

```html
              <PlanCard
                v-else-if="phase === 'awaiting'"
                :plan="view.plan"
                :max="maxSubquestions"
                :question-used="questionUsed"
                editable
```

(`<p v-if="questionUsed">` 안에서 `questionUsed` 는 `string` 으로 좁혀져 `understoodLine` 에 맞는다. `research.css` 는 고치지 않는다.)

- [ ] **Step 7: 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: Step 5 와 같은 수(+0 — 판단·문구는 06c 의 vitest 가 덮는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS\|Duplicated imports"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "rs-plan__understood\|:question-used=\"questionUsed\"" "frontend/pages/research/[id].vue" && grep -c "rs-plan__understood" frontend/assets/css/research.css`
Expected: `2` 와 `0` — 두 곳에 잇고 CSS 규칙은 더하지 않았다

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend/components/research/PlanCard.vue frontend/utils/researchEvents.ts frontend/types/research.ts`
Expected: (빈 출력 — 이 Step 들은 06c 의 파일을 고치지 않는다)

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "frontend/pages/research/[id].vue" && git status --short && git commit -m "[Feat] round06d — 계획 중 카드와 승인 대기 계획 카드에 '이렇게 이해했어요' 한 줄을 잇는다(06c). 06c 의 questionUsedFromSteps 가 마지막 계획 단계의 넓힌 질문을 고르고(원 질문과 같거나 06c 전 잡이면 null — 숨김) understoodLine 이 문구를 만든다 — 같은 판단·문구를 06d 가 따로 두지 않는다. 넓히기가 끝나면 계획이 나오기 전 도는 계획 단계에도 실려 와 계획 중 카드에 먼저 서고, 승인 대기에서는 PlanCard 의 questionUsed prop 으로 머리에 선다. 두 곳이 같은 클래스(rs-muted rs-plan__understood)를 쓰고 새 CSS 는 없다"
```

---

### 파트 메모 — 계획이 정한 세부

인터페이스(파일·공개 이름·시그니처·모양·DOM id·클래스)는 계획 머리 '공통 계약' 과 각 Task 의 코드가 정본이다. 아래 '뼈대' 는 이 계획을 쓸 때 파트끼리 맞춘 초안(계획서에 들지 않는다)이고, 이 절은 그 초안이 정하지 않았거나 글이 달라진 곳과 까닭을 남긴다.

1. **Task L4 — 끝난 잡도 '검토 중'을 지운다(종료 이벤트 셋과, 끝난 잡으로 다시 맞추는 `refreshView`). 테스트가 +9 가 아니라 +11 이다.** 뼈대 §3-3 은 critique·snapshot·그 회차 판정이 실린 진행 저장만 지운다고 했다. 취소는 API 가 곧바로 잡을 끝내고 스트림을 닫아 돌던 하위질문의 `critique` 가 화면에 오지 않고, `refreshView` 는 `buildSubq` 로 앞 화면의 값을 이어서 취소·실패한 잡의 장부에 '검토 중 n'이 영영 남는다(da80f23 `researchEvents.ts:320-325` 의 끝난 잡 분기는 `subqs` 를 그대로 두고, `:272` 의 `refreshView` 는 `rebuild({ ...fresh, subqs: prev.subqs, … })` 로 앞 하위질문을 잇는다 — 스트림이 `CLOSED` 된 뒤 `useResearch.ts` 의 재연결 GET 으로만 맞추는 사이 잡이 끝나면 종료 이벤트도 snapshot 도 오지 않는다). 리듀서의 끝난 잡 세 분기와 `refreshView`(맞춘 잡이 `isTerminalStatus` 일 때)에 `clearReviewing` 을 더하고 `it("끝난 잡(완료·실패·취소 이벤트)은 검토 중을 지운다 — 스트림이 닫혀 점검이 오지 않는다")`·`it("끝난 잡으로 다시 맞추면(refreshView) 검토 중을 지운다 — 재연결 사이에 끝난 잡은 종료 이벤트도 snapshot 도 오지 않는다")` 를 더했다. 뼈대의 아홉 이름은 그대로다. 파트 L 의 테스트 수는 L1 13 + L3 3 + **L4 11** + L5 5 = **32**(뼈대 어림 30 보다 2 많다 — 계획 머리 '테스트 수 어림' 과 Task D8 의 기준선 `797` 이 이 수로 맞춰져 있다).
2. **후보 이벤트의 하위질문 키는 `subq_idx` 다.** 이 파트를 만든 지시문은 `{subq_id, round, papers}` 라고 적었지만 06c 계획의 탐색 후보 Task(`emit("candidates", {"subq_idx": subq.idx, …})`)·06c 계획 정함 3·이 줄 뼈대·spec 커밋 `c5d05b0` 이 모두 `subq_idx` 다 — 지시문의 단서('06c 뼈대와 다르면 06c 쪽을 따른다')대로 06c 를 따랐다. Task L4 Step 0·Task L6 Step 4 가 실제 06c 글·코드로 다시 본다.
3. **Task L1 — `PlanSlot.round` 는 회차가 아직 없으면 `null`.** 뼈대는 'collecting 일 때 지금 회차(rounds.length)' 라고 했다. 하위질문 단계가 막 열려 검색 전이면 `rounds.length` 가 0 이라 '근거 수집 중 · 0회차'가 된다 — `subqStatusLabel` 처럼 회차가 있을 때만 적는다(테스트가 고정).
4. **Task L1 — `planSlots` 가 `sectionOfSubq` 에 넘기는 `titles` 는 `view.subqs` 를 하위질문 번호 자리에 놓은 배열이다**(빈 자리는 빈 글). 뼈대는 `titles` 의 출처를 적지 않았다. `view.plan` 이 아니라 화면의 하위질문 글을 쓴다 — 계획을 모르는 옛 잡도 하위질문 글은 있다.
5. **Task L3 — '자기점검 중'만 깜빡이게 템플릿이 `is-checking`(`r.verdict === null`)을 단다.** 뼈대는 '자기점검 중은 rs-blink 깜빡임'까지만 적었다. 라벨 글자로 가르지 않고 `roundStatusLabel` 의 조건과 같은 칸을 본다. `aria-live="off"` 는 뼈대 그대로 둔다(타임라인은 live 영역이 아니라 없어도 같다).
6. **Task L5 — 커밋을 둘로 나눴다**(뼈대 '1~2'). `work.css` 의 두 hunk 를 `git add -p` 없이 나누려고 ① 을 커밋한 뒤 ② 의 간격 규칙을 고친다. 그 밖에 뼈대가 정하지 않은 것: 검토 중 목록 `max-height: 9rem`(채택 목록 14rem 보다 낮게), 검토 중 서지는 후보가 실은 것을 먼저·없으면 장부가 모은 서지, 후보만 선 바뀜은 채택·뺌의 `fresh` 를 끊지 않는다, 알림은 `후보 n편 검토 중` 을 채택·뺌 앞에 둔다. **뼈대와 글이 다른 것 둘(검토 반영):** ① 검토 중 묶음 자리 — 뼈대 §4 L5 는 '채택 목록(:12-22) 위' 라고 적었지만 spec §12-3 Q9 행 '오른쪽 장부의 그 하위질문 자리에' 에 맞춰 채택 목록 끝(지금 도는 하위질문의 묶음) 바로 아래·뺌 묶음 앞에 둔다. 장부에는 하위질문별 칸이 없어 '그 하위질문 자리' 를 '도는 하위질문의 채택이 떨어질 목록 끝 바로 아래 + 카드마다 하위질문 N' 으로 읽었다(Claude 해석 — 완료노트로 넘긴다). 클래스·DOM 이름은 그대로다. ② `EvidenceLedger.vue` 의 `shown` 이 `hasLedger(…) || (live && seenLive)` — 탐색 중 한 번 선 카드는 탐색이 끝날 때까지 둔다(`hasLedger` 는 뼈대 그대로).
7. **Task L6 — `.rs-plan__understood` 에 CSS 규칙을 더하지 않는다(뼈대 L6·06c 정함 22 와 같다 — 06c 계획의 화면 한 줄 Task 도 규칙 없는 고리로 적었다).**
8. **Task L6 — merge 충돌은 `researchEvents.ts`·`types/research.ts` 가 아니라 `researchEvents.test.ts` 에서 난다.** 뼈대는 '충돌이 나면 `researchEvents.ts`·`types/research.ts` 는 서로 다른 함수·블록이라 두 쪽을 모두 남긴다' 고 했다. 사본 merge 로 재 보니 그 둘은 저절로 합쳐지고, 테스트 파일이 import 목록과 파일 끝 두 곳에서 충돌한다(파일 끝은 diff 가 두 쪽의 마지막 `  });`·`});` 를 공통으로 잡아 표시만 지우면 문법이 깨진다). 그래서 Step 3 을 '06d 쪽 파일 + 06c 의 import 두 이름 + 06c 의 `const ASKED` 이하 묶음' 으로 적었다 — `queueLine,` 을 되살리지 않는 것이 핵심이다.
9. **Task L2 — 계획 블록 조건에서 `exploring` 을 뺀다.** 뼈대에 있는 대로이고, 덧붙여 '탐색 중 읽기 전용 PlanCard 만 지우면 빈 `rs-block--plan` 섹션이 남는다' 는 까닭을 Task 에 적었다. 절 자리에는 aria-live 알림을 두지 않는다(같은 순간 장부가 채택을 읽는다).
10. **Task L1 — 근거 0편으로 끝난 자리(종합 시작 전)는 상태 `collected` 그대로, 라벨 `근거 0편`(✓ 없음)이고 `newlyCollected` 에서 빠진다(검토 반영).** 뼈대 §3-1 은 `collected` 라벨을 '근거 N편 ✓' 하나로 적었다. spec §12-3 '근거가 모이면 근거 N편 ✓' 에 맞춰 근거가 없을 때 성공 표시와 튀어 오름을 내지 않는다. 접는 시점(종합 시작 → `empty` '근거 없음')과 공개 이름·모양은 그대로이고 it 수도 그대로(13)다.

#### 다른 파트·줄에 기대는 것

- **파트 D:** D2 의 `import { researchPhase } from "~/utils/researchEvents";` 한 줄과 계획 중 카드의 `.rs-card__text` 묶음(L6 의 앵커), D2 가 바꾼 `researchEvents.test.ts` import(`queueLine` 을 `~/utils/queueLine` 에서), D4 의 `~/utils/researchProgress` import 가 `~/utils/researchLayout` import 바로 아래에 있다는 것(L2 의 import 자리), D4 품질 검토 반영의 문서 `scroll-padding-top: var(--rs-bar-area-h)` 와 `.rs-section` `scroll-margin-top: 1.2rem`(L2 의 자리에 적용 — 처음 계획의 D5 `calc(var(--rs-bar-h, 0px) + 1.2rem)` 은 걷었다), D7 이 L2 의 `planSlotList`·L1 의 `slotElementId`·`PlanSlot` 를 쓴다, D7 의 알약은 `</aside>` 다음 `</div>` 뒤라 L5 의 옆 칸 블록과 겹치지 않는다, D8 은 L5 뒤에 `.rs-col-side .rs-card__title` 로 장부·진행 패널 카드 머리를 입힌다. Task D8 의 기준선·기대 수 `797` 은 L4 의 +11 을 넣은 값이다 — 사본에서 D1~D7·L1~L5·D8 뒤 `Test Files 43 passed (43)` / `Tests 797 passed (797)` 로 쟀다.
- **06c:** 탐색 후보 Task(`runner.py` 의 `candidates` — L4·L5 의 재료, 06c 워커 배포 10/13~14 전에는 이벤트가 오지 않아 더미 없이 지금처럼), 화면 한 줄 Task(`questionUsedFromSteps`·`understoodLine`·PlanCard `questionUsed`·`StepResult` 칸 셋 — L6). 06c 가 Task 0 전에 dev 에 들어와 있으면 `researchEvents.test.ts` 의 수가 +7 이고 L6 의 merge 는 충돌 없이 끝난다(각 Task 에 두 경우의 수를 적었다).
- **06e:** 이 파트는 06e 파일을 고치지 않는다. 06e 가 L6 보다 먼저 dev 에 들어왔으면 L6 의 merge 로 함께 들어오고(그때의 충돌 규칙은 L6 Step 3), Task N8 의 merge 는 받을 것이 없을 수 있다.
- **마무리(Task Z1·Z6):** Task Z1 Step 2 의 더한 `@keyframes` `1` 은 이 파트의 L5 `wk-review` 하나다(`research.css` 는 파트 D·L 이 더하지 않고, `work.css` 는 da80f23 `4` → `5`). Task Z6 Step 1~3 의 '탐색 중 절 자리·근거 N편 ✓·회차 미세 상태·장부 맨 위·검토 중 → 채택 떨어짐/뺌 가라앉음·새로고침하면 더미 없음·취소한 잡에 검토 중 없음(이 절의 1)·계획 중/승인 대기 이렇게 이해했어요' 항목을 이 파트가 만든다.

---

## 파트 N — 입구 — /research 홈·사이드바·빠른검색·문구

spec §12-3 '입구(D26)' 와 D17 을 덮는다: **문구**(랜딩 '도서검색' → '소장자료검색'·낭독 문구, §12-11 의 입력창 안내·사이드바 기록 탭 이름까지 — 정함 18, Task N1) · **사이드바 단계 표시**(이어간 연구 줄의 단계 — 정함 13, 폴링 조건에 진행 중 생성, 목록 끝 '모두 보기 (N)' — 정함 14, Task N2·N3) · **빠른검색 [딥리서치로 더 깊게]**(정함 16, Task N4) · **예시 연구 노출 = `/research` 홈**(새 연구 시작·진행 중·내 연구·예시 연구 — 정함 15, Task N5) · **빠른검색 [담기 ▾]**(D17·정함 17, Task N6) · **탐색 방식**(06c 판정 뒤 2026-10-12 사용자 결정 D28 — 딥리서치를 시작하는 자리의 폭넓게 · 정밀하게 선택, 정함 19, Task N9). 조건부 둘: N5 를 잘랐을 때의 사이드바 '예시 연구' 묶음(Task N7), 06e 가 먼저 dev 에 머지됐을 때의 딥리드 패널 LNB 접기 연결(Task N8 — 실행은 Task L6 뒤). 랜딩 논문 예시 셋(06c 판정 뒤 다시 확인)은 이 파트에 Task 가 없다 — Task Z2 가 판정 결과로 보고 바꿀 것이 있을 때만 고친다. 대회 뒤(하지 않음): 메인 [빠른검색|딥리서치] 모드 토글·도서 숨김·사이드바 시안 묶음(탭 대신 묶음·'● 진행 중 1' 배지·줄마다 진행 막대)·연구 화면 머리 위 skx 검색바.

이 파트는 nuxt 만이고 쓰는 백엔드는 이미 있다(`GET /api/research-works`·`GET /api/research/{id}/work`·`PUT /api/research/{id}/reading/{cnts_id}`·`GET /api/history`). 기록 목록의 `total` 은 06e fastapi 가 싣는다 — 없는 응답(06e 전 서버)에서는 '모두 보기' 만 그린다. 06e 파일(`utils/workPhase.ts`·`utils/researchErrors.ts`·`composables/useResearchWork.ts`·`types/work.ts`)은 읽기만 하고, 사이드바·홈의 단계 글은 `workPhase.stepLine` 출력 그대로라 06e 의 이름 바꾸기(제목 고르기·참고문헌 선택하기·보고서)가 따라온다.

**실행 순서:** Task D8 → N1 → N2 → N3 → N4 → N5 → N6 → N7(조건부) → N9 → (Task L6) → N8(조건부). N9 는 번호를 다시 매기지 않으려고 N6 바로 뒤에 적었다 — N5·N6 을 잘랐으면 N7 뒤에 한다. **자르는 순서(spec §12-6):** 뒤처지면 N6 → N5 순으로 하지 않는다. N5 를 자르면 N7 을 한다(그때는 N6 도 하지 않는다 — N6 은 N5 가 만든 `useResearchWorks.ts`·`WorkListItem` 을 쓴다). N9 는 자르는 순서에 들지 않는다(사용자 결정 D28 — N5 를 잘랐으면 홈 Step 만 건너뛴다).

**같은 파일 사슬:** `components/AppSidebar.vue` N1 → N3 → N7 · `pages/papers/index.vue` N4 → N6 · `assets/css/research.css`(파트 D·L 뒤) N4 → N5 → N6 → N9 — 넷 모두 인쇄 앵커 `/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */` 바로 위에 넣으므로 N5 블록은 N4 블록 뒤, N6 블록은 N5 블록 뒤, N9 블록은 N6 블록 뒤에 선다 · `composables/useResearchWorks.ts`·`utils/researchHome.ts` N5 → N6(또는 N7) · `pages/research/index.vue` N5 → N9. 기록 네 파일·두 테스트(N2), `pages/index.vue`(N1)는 이 파트만 고친다 — 줄 번호가 da80f23 그대로다.

**작성 때 실측(검증 근거):** da80f23 코드 위에 파트 N 만 얹어 이 계획의 코드 그대로 잰 값 — vitest `40 files / 732` → N1 732 → N2 736 → N3 744(41 files) → N4 746 → N5 750(42) → N6 754(43), 각 단계 typecheck `error TS` 0, N6 뒤 build `└  ✨ Build complete!`. N7 경로(N4 → N7)는 `42 files / 749`·typecheck 0·build 완료(검토 반영 뒤 다시 잼). N8 은 06e 의 `const workPanelOpen = ref(false);` 를 흉내 내어 typecheck 0. N9 는 2026-10-12 에 따로 쟀다 — dev `ef202fb`(06c 머지까지, 파트 D·L·N 없이) 위에 N9 만 얹어 `40 files / 739` → `41 files / 752`, typecheck `error TS` 0, build 완료(홈 Step 8 은 N5 페이지가 없어 빼고 — Task N9 끝 '작성 때 확인'). 실제 실행에서는 파트 D·L 의 테스트가 앞에 있으므로 전체 수는 'Task 앞 수 + N' 으로 읽고, 파일 하나씩 돌리는 수(이 파트만 고치는 파일)는 아래 값 그대로다.

---

### Task N1: 문구 — 소장자료검색

spec §12-3 입구 '문구'(랜딩 탭 `pages/index.vue:50` '도서검색' → '소장자료검색', 낭독 문구 `:77`)·D26, 그리고 §12-11 ''소장자료검색'으로 맞출 다른 문구' — **정함(권고)**(정함 18): 입력창 안내(`:82`)와 사이드바 기록 탭 이름(`AppSidebar.vue:150` '도서')·그 탭의 빈/지우기 문구(`:155`·`:160`)도 '소장자료'로 맞춘다. 탭 이름이 '소장자료검색'인데 기록 탭이 '도서'면 같은 기록을 두 이름으로 부른다. 기능·kind(`book`)·주소·랜딩 머리 문구(`:12-15`)·결과 화면 문구(`:1180` 'AI가 가장 적합한 도서를 찾았어요!')는 그대로다. `/search-classic` 은 보존 화면이라 건드리지 않는다.

**알아 둘 것:**
- 두 파일 모두 이 줄에서 처음 고친다 — 줄 번호가 da80f23 그대로다(`AppSidebar.vue` 는 Task N3·N7 이 뒤에 고친다).
- 문구를 고정한 테스트가 없다(`grep -rn "도서검색\|도서 검색" frontend/tests` 빈 출력 — 작성 때 확인). 테스트 +0.
- '소장자료'는 '딥리서치'와 같은 넉 자라 기록 탭 폭(`.skx-history__tab` 은 `flex: 1`, 12px)이 그대로 맞는다.

**Files:**
- Modify: `frontend/pages/index.vue`(:50·:77·:82)
- Modify: `frontend/components/AppSidebar.vue`(:149-163 — 세 줄)

기준선: Task D8 뒤 수(이 Task 는 테스트를 더하지 않는다).

- [ ] **Step 1: 랜딩 탭·낭독·입력창 안내를 고친다**

`frontend/pages/index.vue` :50 — 고치기 전:

```vue
            <span class="skx-tab__label">도서검색</span>
```

고친 뒤:

```vue
            <span class="skx-tab__label">소장자료검색</span>
```

`frontend/pages/index.vue` :77 — 고치기 전:

```vue
                <span class="skx-sr-only">도서 검색어</span>
```

고친 뒤:

```vue
                <span class="skx-sr-only">소장자료 검색어</span>
```

`frontend/pages/index.vue` :82 — 고치기 전:

```vue
                  placeholder="찾고싶은 도서를 문장으로 검색해보세요!"
```

고친 뒤:

```vue
                  placeholder="찾고싶은 소장자료를 문장으로 검색해보세요!"
```

- [ ] **Step 2: 사이드바 기록 탭 이름과 그 탭의 빈·지우기 문구를 고친다**

`frontend/components/AppSidebar.vue` :149-163 — 고치기 전:

```ts
const TABS: Array<{ kind: HistoryKind; label: string }> = [
  { kind: "book", label: "도서" },
  { kind: "paper", label: "논문" },
  { kind: "research", label: "딥리서치" },
];
const EMPTY_TEXT: Record<HistoryKind, string> = {
  book: "도서 검색 기록이 없습니다.",
  paper: "논문 검색 기록이 없습니다.",
  research: "딥리서치 기록이 없습니다. 논문 검색창의 + 에서 시작해 보세요.",
};
const CLEAR_TEXT: Record<HistoryKind, string> = {
  book: "도서 검색 기록을 모두 지울까요?",
  paper: "논문 검색 기록을 모두 지울까요?",
  research: "딥리서치 기록을 모두 지울까요? 보고서 자체는 지워지지 않습니다.",
};
```

고친 뒤(`book` 의 세 줄만 바뀐다):

```ts
const TABS: Array<{ kind: HistoryKind; label: string }> = [
  { kind: "book", label: "소장자료" },
  { kind: "paper", label: "논문" },
  { kind: "research", label: "딥리서치" },
];
const EMPTY_TEXT: Record<HistoryKind, string> = {
  book: "소장자료 검색 기록이 없습니다.",
  paper: "논문 검색 기록이 없습니다.",
  research: "딥리서치 기록이 없습니다. 논문 검색창의 + 에서 시작해 보세요.",
};
const CLEAR_TEXT: Record<HistoryKind, string> = {
  book: "소장자료 검색 기록을 모두 지울까요?",
  paper: "논문 검색 기록을 모두 지울까요?",
  research: "딥리서치 기록을 모두 지울까요? 보고서 자체는 지워지지 않습니다.",
};
```

- [ ] **Step 3: 확인한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "도서검색" pages/index.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "소장자료" pages/index.vue components/AppSidebar.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend/pages/search-classic.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected:
- `0`(옛 탭 이름이 남지 않았다 — `grep -c` 는 맞는 줄이 없으면 종료 코드 1 이고 `0` 을 찍는다)
- `pages/index.vue:3` · `components/AppSidebar.vue:3`
- 빈 출력(`/search-classic` 그대로)
- vitest — `Test Files  (Task D8 뒤 파일 수) passed` / `Tests  (Task D8 뒤 수) passed`, 실패 0(+0)
- `0`
- `└  ✨ Build complete!`

- [ ] **Step 4: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/pages/index.vue frontend/components/AppSidebar.vue && git status --short && git commit -m "[Feat] round06d — 랜딩 탭 '도서검색'을 '소장자료검색'으로 바꾸고 낭독 문구·입력창 안내('찾고싶은 소장자료를 문장으로 검색해보세요!')도 같은 말로 맞춘다. 사이드바 기록 탭 '도서'와 그 탭의 빈·지우기 문구도 '소장자료'로 바꾼다 — 탭 이름과 기록 탭 이름이 같은 말이어야 한다(spec §12-11 권고대로 정함). 기능·kind(book)·주소·결과 화면 문구·/search-classic 은 그대로"
```

Expected: `git status --short` 가 `M  frontend/components/AppSidebar.vue`·`M  frontend/pages/index.vue` 두 줄, 커밋 1개.

---

### Task N2: 기록 목록 total 받기(`totalOf`)

spec §12-3 '사이드바 단계 표시 — 모두 보기 (N) 의 N 은 기록 목록의 kind 별 total'(06e 가 fastapi 에 싣는다, 06d 는 응답에 없으면 N 없이), §12-5(기록 프론트 파일은 06d 몫). 정함 14. 이 Task 는 수를 받아 두기만 하고 그리는 것은 Task N3 이다.

**알아 둘 것:**
- **응답 모양:** 06e(06e 계획의 기록 total Task)는 `GET /api/history` 응답에 `total: int | null` 을 싣는다 — 이 브라우저의 그 kind 의 지우지 않은 기록 전부의 수이고 `before` 와 무관하다. 06e 전 서버는 키가 없다. `HistoryListOut.total?`·`ListResult.total?` 는 **선택 필드**다(06b 머리 — 기존 `toEqual` 픽스처를 깨지 않게).
- **누가 수를 싣나:** 서버 저장소 `createServerStore().list` 만 `total: res.total ?? null` 을 싣는다(06e 전 서버면 `null`). 하이브리드 저장소는 서버가 되면 서버 결과를 그대로 돌려주고(`historyStore.ts:633-636` — `return res.value`), 서버가 안 되면 브라우저 캐시 목록(`createLocalStore().list` :373-386)을 돌려준다 — 그 목록에는 **`total` 키가 없다**. 상태(`historyState`)는 키가 있을 때(`!== undefined`)만 수를 바꾼다 — 잠깐 오프라인이 된 동안 알던 수를 지우지 않는다. `null` 은 '서버가 수를 주지 않았다'로 받아 그대로 null 로 둔다.
- **지우기와 수:** `remove(id)` 는 지우기 전에 목록에서 그 기록의 kind 를 찾아, 알던 수가 숫자면 1 줄인다(0 밑으로 내리지 않는다). 목록에 없던 기록(다른 탭이 만든 것)은 kind 를 몰라 건드리지 않는다. `clear(kind)` 는 그 kind 를 0 으로 둔다. 목록을 읽는 사이 이 탭에서 지운 기록은 늦게 온 서버 수에 아직 들어 있으므로, `refresh` 는 응답에서 버린 기록 수만큼 빼서 받는다(기존 `removedAt` 규칙과 같은 자리). 새 기록(`add`·`upsertResearch`)은 세지 않는다 — 다음 `refresh` 가 맞춘다(사이드바는 마운트 때 `load`, 진행 중 연구가 있으면 30초 폴링으로 다시 읽는다).
- **테스트 대역:** `tests/unit/helpers/fakeHistory.ts` 의 `fakeServer`·`networkError`, `historyStore.test.ts:67` 의 `fakeFetcher`, `historyState.test.ts` 의 `setup`·`setupHybrid` 를 그대로 쓴다 — 새 대역을 만들지 않는다. `fakeServer().list` 는 `total` 을 싣지 않으므로 수를 싣는 응답은 `store.list.mockImplementationOnce` 로 준다.

**Files:**
- Modify: `frontend/types/history.ts`(:132-135 `HistoryListOut`)
- Modify: `frontend/utils/historyStore.ts`(:35-38 `ListResult`, :160 `createServerStore().list` 의 return)
- Modify: `frontend/utils/historyState.ts`(:21-31 `HistoryState`, :47 아래, `byKind` 뒤, :101-104 `refresh`, :158-160 `remove`, :170-171 `clear`, :227 return)
- Modify: `frontend/composables/useHistory.ts`(:98 `UseHistory`, :114 return)
- Test: `frontend/tests/unit/historyStore.test.ts`(describe `createServerStore` — 58 → 59)
- Test: `frontend/tests/unit/historyState.test.ts`(:6 import, describe `createHistoryState` 끝 — 21 → 24)

기준선(Task N1 뒤): 전체는 Task D8 뒤와 같은 수. 두 파일 `Tests  79 passed (79)`(58 + 21).

- [ ] **Step 1: 실패하는 테스트를 쓴다 — 서버 저장소**

`frontend/tests/unit/historyStore.test.ts` — describe `createServerStore` 의 둘째 `it` 줄(파일에 하나)을 old 로 잡고 그 앞에 새 `it` 을 넣는다. old:

```ts
  it("get 은 404 면 null, 다른 오류는 그대로 던진다", async () => {
```

new:

```ts
  it("목록 응답의 total 을 싣고, 없으면(06e 전 서버) null", async () => {
    const withTotal = fakeFetcher(() => ({ items: [wire()], next_cursor: null, total: 42 }));
    expect((await createServerStore(withTotal.fetcher).list("book")).total).toBe(42);
    const empty = fakeFetcher(() => ({ items: [], next_cursor: null, total: 0 }));
    expect((await createServerStore(empty.fetcher).list("research")).total).toBe(0);
    const before06e = fakeFetcher(() => ({ items: [wire()], next_cursor: null }));
    expect((await createServerStore(before06e.fetcher).list("book")).total).toBeNull();
  });

  it("get 은 404 면 null, 다른 오류는 그대로 던진다", async () => {
```

- [ ] **Step 2: 실패하는 테스트를 쓴다 — 기록 상태**

`frontend/tests/unit/historyState.test.ts` :6 — 고치기 전:

```ts
import { ID1, ID2, ID3, bookEntry, fakeServer, httpError, paperEntry, researchEntry } from "./helpers/fakeHistory";
```

고친 뒤:

```ts
import {
  ID1,
  ID2,
  ID3,
  bookEntry,
  fakeServer,
  httpError,
  networkError,
  paperEntry,
  researchEntry,
} from "./helpers/fakeHistory";
```

파일 끝 — describe `createHistoryState` 의 마지막 `it`(`upsertResearch 가 서버의 기록을 읽는 사이 딥리서치 기록을 비우면 …`)의 끝과 describe 닫는 줄을 old 로 잡는다(같은 줄로 끝나는 `it` 이 하나 더 있지만 그 뒤에는 `});` 가 아니라 빈 줄과 `it(` 이 온다 — 아래 세 줄 묶음은 파일에 하나다). old:

```ts
    expect(state.byKind("research").value).toEqual([]);
  });
});
```

new:

```ts
    expect(state.byKind("research").value).toEqual([]);
  });

  it("refresh(kind) 가 그 kind 의 total 을 기억하고 totalOf 가 돌려준다", async () => {
    const { store, state } = setup();
    store.rows.set(ID2, researchEntry(ID2));
    const total = state.totalOf("research");
    expect(total.value).toBeNull();
    store.list.mockImplementationOnce(async (kind?: HistoryKind) => ({
      items: [...store.rows.values()].filter((e) => !kind || e.kind === kind),
      nextCursor: null,
      total: 42,
    }));
    await state.refresh("research");
    // 한 쪽(30건)만 읽어도 수는 그 kind 전체다 — 먼저 받아 둔 계산 값이 따라온다
    expect(total.value).toBe(42);
    expect(state.totalOf("research")).toBe(total);
    expect(state.totalOf("book").value).toBeNull();
    // 서버가 수를 주지 않으면(06e 전 서버 — createServerStore 가 null 로 싣는다) 모르는 값으로 돌아간다
    store.list.mockImplementationOnce(async () => ({ items: [], nextCursor: null, total: null }));
    await state.refresh("research");
    expect(total.value).toBeNull();
  });

  it("total 을 모르는 목록(로컬로 물러남)은 알던 값을 지우지 않는다", async () => {
    const { server, state } = setupHybrid();
    server.rows.set(ID2, researchEntry(ID2));
    server.list.mockImplementationOnce(async (kind?: HistoryKind) => ({
      items: [...server.rows.values()].filter((e) => !kind || e.kind === kind),
      nextCursor: null,
      total: 5,
    }));
    await state.refresh("research");
    expect(state.totalOf("research").value).toBe(5);
    // 서버가 안 되면 하이브리드 저장소가 브라우저 캐시로 답한다 — 그 목록에는 수가 없다
    server.fail(networkError());
    await state.refresh("research");
    expect(state.byKind("research").value.map((e) => e.id)).toEqual([ID2]);
    expect(state.totalOf("research").value).toBe(5);
  });

  it("clear 는 0, remove 는 알던 값에서 하나 줄인다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, paperEntry(ID1));
    store.rows.set(ID2, paperEntry(ID2, { title: "다른 논문" }));
    store.list.mockImplementationOnce(async (kind?: HistoryKind) => ({
      items: [...store.rows.values()].filter((e) => !kind || e.kind === kind),
      nextCursor: null,
      total: 40,
    }));
    await state.refresh("paper");
    await state.remove(ID1);
    expect(state.totalOf("paper").value).toBe(39);
    // 목록에 없는 기록은 종류를 몰라 수를 건드리지 않는다
    await state.remove(ID3);
    expect(state.totalOf("paper").value).toBe(39);
    // 목록을 읽는 사이 지운 기록은 늦게 온 서버 수에 아직 들어 있다 — 응답에서 버린 만큼 뺀다
    let release!: () => void;
    const released = new Promise<void>((resolve) => {
      release = resolve;
    });
    store.list.mockImplementationOnce(async (kind?: HistoryKind) => {
      const items = [...store.rows.values()].filter((e) => !kind || e.kind === kind);
      await released;
      return { items, nextCursor: null, total: 39 };
    });
    const refreshing = state.refresh("paper");
    await state.remove(ID2);
    release();
    await refreshing;
    expect(state.totalOf("paper").value).toBe(38);
    await state.clear("paper");
    expect(state.totalOf("paper").value).toBe(0);
    // 수를 모르던 종류도 비운 뒤에는 0 이다
    await state.clear("book");
    expect(state.totalOf("book").value).toBe(0);
  });
});
```

- [ ] **Step 3: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/historyStore.test.ts tests/unit/historyState.test.ts`

Expected: `Test Files  2 failed (2)` / `Tests  4 failed | 79 passed (83)`.
- `× createServerStore > 목록 응답의 total 을 싣고, 없으면(06e 전 서버) null` — `AssertionError: expected undefined to be 42 // Object.is equality`(`list` 가 아직 `total` 을 싣지 않는다)
- `× createHistoryState > refresh(kind) 가 그 kind 의 total 을 기억하고 totalOf 가 돌려준다`·`× … total 을 모르는 목록(로컬로 물러남)은 알던 값을 지우지 않는다`·`× … clear 는 0, remove 는 알던 값에서 하나 줄인다` — 셋 다 `TypeError: state.totalOf is not a function`

- [ ] **Step 4: 구현한다 — 선 모양·서버 저장소**

`frontend/types/history.ts` :132-135 — 고치기 전:

```ts
export interface HistoryListOut {
  items: HistoryItemOut[];
  next_cursor: string | null;
}
```

고친 뒤:

```ts
export interface HistoryListOut {
  items: HistoryItemOut[];
  next_cursor: string | null;
  // kind 를 준 목록이면 그 kind 의 지우지 않은 기록 전체 수(before 와 무관 — 사이드바 '모두 보기 (N)').
  // 06e 서버부터 싣는다 — 그 전 서버에는 키가 없다
  total?: number | null;
}
```

`frontend/utils/historyStore.ts` :35-38 — 고치기 전:

```ts
export interface ListResult {
  items: HistoryEntry[];
  nextCursor: string | null;
}
```

고친 뒤:

```ts
export interface ListResult {
  items: HistoryEntry[];
  nextCursor: string | null;
  // 서버 목록만 싣는다 — null 은 서버가 수를 주지 않았다(06e 전 서버). 브라우저 저장소의 목록(편지함이 남았거나
  // 서버가 안 될 때)에는 키가 없다 — 받는 쪽은 알던 수를 그대로 둔다
  total?: number | null;
}
```

`frontend/utils/historyStore.ts` :160(`createServerStore` 의 `list`) — 고치기 전:

```ts
      return { items: res.items.map(fromWire), nextCursor: res.next_cursor };
```

고친 뒤:

```ts
      return { items: res.items.map(fromWire), nextCursor: res.next_cursor, total: res.total ?? null };
```

- [ ] **Step 5: 구현한다 — 기록 상태 `totalOf`**

`frontend/utils/historyState.ts` — `HistoryState` 의 마지막 줄(:30) 아래. old:

```ts
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
}

/** 반응형 목록에는 무거운 필드를 두지 않는다 — 복원은 get(id) 로 상세를 읽는다 */
```

new:

```ts
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
  // 그 kind 의 기록 전체 수(사이드바 '모두 보기 (N)'). 서버가 아직 주지 않았으면 null
  totalOf(kind: HistoryKind): ComputedRef<number | null>;
}

/** 반응형 목록에는 무거운 필드를 두지 않는다 — 복원은 get(id) 로 상세를 읽는다 */
```

:46-47 — old:

```ts
  const entries = ref<HistoryEntry[]>([]);
  const kindViews = new Map<HistoryKind, ComputedRef<HistoryEntry[]>>();
```

new:

```ts
  const entries = ref<HistoryEntry[]>([]);
  const kindViews = new Map<HistoryKind, ComputedRef<HistoryEntry[]>>();
  // kind 별 전체 수 — 서버 목록 응답의 total 이 정본이다. 새 기록(add·upsertResearch)은 세지 않고 다음 refresh 가 맞춘다
  const totals = ref<Partial<Record<HistoryKind, number | null>>>({});
  const totalViews = new Map<HistoryKind, ComputedRef<number | null>>();
```

`byKind` 함수(:65-72)의 끝 — old:

```ts
      kindViews.set(kind, view);
    }
    return view;
  }
```

new:

```ts
      kindViews.set(kind, view);
    }
    return view;
  }

  function totalOf(kind: HistoryKind): ComputedRef<number | null> {
    let view = totalViews.get(kind);
    if (!view) {
      view = computed(() => totals.value[kind] ?? null);
      totalViews.set(kind, view);
    }
    return view;
  }

  function setTotal(kind: HistoryKind, value: number | null): void {
    totals.value = { ...totals.value, [kind]: value };
  }
```

`refresh` 안(:101-104) — old:

```ts
          const { items } = await store().list(k, { limit: HISTORY_PAGE_SIZE });
          if ((clearedAt.get(k) ?? 0) > since) return;
          const kept = items.filter((e) => (removedAt.get(e.id) ?? 0) <= since);
          entries.value = [...entries.value.filter((e) => e.kind !== k), ...kept.map(toListItem)];
```

new:

```ts
          const { items, total } = await store().list(k, { limit: HISTORY_PAGE_SIZE });
          if ((clearedAt.get(k) ?? 0) > since) return;
          const kept = items.filter((e) => (removedAt.get(e.id) ?? 0) <= since);
          entries.value = [...entries.value.filter((e) => e.kind !== k), ...kept.map(toListItem)];
          // 수를 실은 서버 목록만 받는다 — 브라우저 저장소의 목록(키 없음)은 알던 수를 지우지 않는다.
          // 읽는 사이 지운 기록은 서버 수에 아직 들어 있으니 응답에서 버린 만큼 뺀다
          if (total !== undefined) setTotal(k, total === null ? null : Math.max(0, total - (items.length - kept.length)));
```

`remove`(:158-160) — old:

```ts
  async function remove(id: string): Promise<void> {
    removedAt.set(id, ++deleteSeq);
    drop(id);
```

new:

```ts
  async function remove(id: string): Promise<void> {
    removedAt.set(id, ++deleteSeq);
    // 지우기 전에 종류를 알아 둔다 — 목록에 없던 기록(다른 탭이 만든 것 등)이면 수를 건드리지 않는다
    const kind = entries.value.find((e) => e.id === id)?.kind;
    drop(id);
    const known = kind ? totals.value[kind] : undefined;
    if (kind && typeof known === "number") setTotal(kind, Math.max(0, known - 1));
```

`clear`(:170-171) — old:

```ts
    clearedAt.set(kind, ++deleteSeq);
    entries.value = entries.value.filter((e) => e.kind !== kind);
```

new:

```ts
    clearedAt.set(kind, ++deleteSeq);
    entries.value = entries.value.filter((e) => e.kind !== kind);
    setTotal(kind, 0);
```

:227 — 고치기 전:

```ts
  return { entries, byKind, refresh, add, patch, remove, clear, get, upsertResearch };
```

고친 뒤:

```ts
  return { entries, byKind, refresh, add, patch, remove, clear, get, upsertResearch, totalOf };
```

- [ ] **Step 6: 구현한다 — `useHistory`**

`frontend/composables/useHistory.ts` :98-99 — old:

```ts
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
}
```

new:

```ts
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
  // 그 kind 의 기록 전체 수(사이드바 '모두 보기 (N)') — 06e 전 서버면 null
  totalOf(kind: HistoryKind): ComputedRef<number | null>;
}
```

:114-115 — old:

```ts
    upsertResearch: s.upsertResearch,
  };
```

new:

```ts
    upsertResearch: s.upsertResearch,
    totalOf: s.totalOf,
  };
```

(`ComputedRef` 는 :2 에서, `HistoryKind` 는 :3 에서 이미 import 한다.)

- [ ] **Step 7: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/historyStore.test.ts tests/unit/historyState.test.ts`
Expected: `Test Files  2 passed (2)` / `Tests  83 passed (83)`(historyStore 59 + historyState 24)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run`
Expected: 실패 0, `Tests` 는 Task N1 뒤 수 + 4(파일 수 그대로)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`(`nuxi typecheck` 는 `tests/` 도 본다 — `mockImplementationOnce` 가 `total` 을 더 실은 응답을 돌려도 타입 오류가 없다, 작성 때 확인)

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/types/history.ts frontend/utils/historyStore.ts frontend/utils/historyState.ts frontend/composables/useHistory.ts frontend/tests/unit/historyStore.test.ts frontend/tests/unit/historyState.test.ts && git status --short && git commit -m "[Feat] round06d — 기록 목록 응답의 kind 별 total 을 받아 둔다(useHistory().totalOf(kind)). 06e 서버가 싣는 total 을 서버 저장소가 그대로 나르고 06e 전 서버면 null 로 둔다 — 사이드바는 수 없이 '모두 보기' 만 그린다. 서버가 안 될 때의 브라우저 캐시 목록에는 수가 없어 알던 값을 지우지 않는다. 지우면 알던 수에서 하나, 비우면 0, 목록을 읽는 사이 지운 기록은 늦게 온 서버 수에서 뺀다. 새 기록은 세지 않고 다음 refresh 가 맞춘다"
```

Expected: `M` 여섯 줄, 커밋 1개.

---

### Task N3: 사이드바 단계 표시·폴링 조건·모두 보기 (N)

spec §12-3 '사이드바 단계 표시': 이어간 연구 줄에 단계를 작게 넣는다(06b history 응답의 `phase`·`progress`·`generating` — `app/schemas/history.py:47-54`(`ResearchStatus`, 세 필드는 :51-54), 단계 이름은 `utils/workPhase.ts` 의 것), 폴링 조건에 '진행 중 생성이 있는 이어간 연구'를 더한다(`AppSidebar.vue:165-166`·`:185`, §6-4), 목록 끝 '모두 보기 (N)' → `/research`(total 이 없으면 N 없이). 지금 탭 구조(`AppSidebar.vue:149-153`)의 딥리서치 탭에 넣는다 — 시안 묶음은 대회 뒤(Q8). D26. 정함 13·14.

**알아 둘 것:**
- **단계 줄(정함 13):** `researchRowLine` = `[stepLine(phase), 수, generating ? "생성 중" : ""]` 를 ` · ` 로 잇고 빈 칸은 뺀다. 수 — topics: `progress.topics > 0` 이면 `후보 ${n}` · reading: `progress.reading > 0` 이면 `${n}편 담음` · proposal: `progress.sections_total` 이 있으면 `${sections ?? 0}/${sections_total}절` · done: 없음. `phase` 가 없으면(이어가지 않은 딥리서치·06a 전 서버) null — 그 줄은 지금처럼 배지와 시각만 있다(D15). **06d 는 단계 이름 문자열을 새로 쓰지 않는다** — 06e 가 `PHASE_LINE` 을 '2/4 단계 · 제목 고르는 중'·'3/4 단계 · 참고문헌 고르는 중'·'4/4 단계 · 보고서 쓰는 중' 으로 바꾸면 사이드바가 따라온다. 테스트도 기대값을 `stepLine(phase)` 호출로 만든다(06e 의 이름 바꾸기에 깨지지 않게).
- **폴링(spec §6-4):** `isLiveResearch` = 잡 상태가 `LIVE_RESEARCH_STATUSES`(지금 `AppSidebar.vue:165` 의 다섯 — created·planning·approved·queued·running, 승인 대기는 사용자가 움직여야 바뀌므로 뺀다)이거나 `generating === true`. 끝난 잡이라도 이어간 연구의 생성(주제 카드·목차·절)이 도는 동안 30초 폴링이 이어진다 — 단계 줄의 수가 바뀐다.
- **모두 보기(정함 14):** `allResearchLabel(total)` — `null` 이면 `모두 보기`, 숫자면 `모두 보기 (N)`(0 이면 `모두 보기 (0)`). **목록이 비어도 그린다** — 빈 목록이면 `<p class="skx-history__empty">`(:96)만 그려지고 `<ul>` 이 없는데, `/research` 홈(예시 연구가 보이는 단 한 곳 — spec §12-3)으로 가는 길은 이 링크뿐이다. 대회에서 직접 써 볼 전문가(D1)는 기록이 없는 새 브라우저로 온다. 링크는 `<p v-if>`/`<ul v-else>` 사슬 뒤의 별개 요소라 빈 문구 아래·목록 아래 어느 쪽에서도 선다. `.skx-history` 는 세로 flex(`style_skovix.css:472-479`)이고 목록만 `overflow-y: auto` 라 링크(`flex: none`)는 목록이 길어도 늘 보인다.
- **배지 함수를 옮긴다(공통 계약 '새 파일과 공개 이름' 표의 `utils/sidebarResearch.ts` 행 — 파트 N 끝 '파트 메모' 1):** `badgeOf` 의 상태 → 배지 switch(:206-222)를 `utils/sidebarResearch.ts` 의 `researchBadge` 로 옮긴다 — Task N5 의 `/research` 홈 줄이 같은 배지를 쓴다(같은 판단을 두 곳에 두지 않는다). 사이드바의 `badgeOf` 는 이 함수를 부르기만 한다. 문구·tone 은 그대로다.
- **색값:** 새 규칙은 `--skx-*` 토큰만 쓴다(Task Z1 의 색값 0 검사 — 기존 scoped 규칙의 rgba·hex 는 그대로 둔다). 링크의 hover 는 배경 대신 밑줄이다.
- 템플릿은 Task N1 이 고친 script 의 세 줄보다 위라 줄이 그대로지만, Edit 의 old 는 아래 앵커 글자로 잡는다.

**Files:**
- Create: `frontend/utils/sidebarResearch.ts`
- Modify: `frontend/components/AppSidebar.vue`(템플릿 :105 뒤·:124 뒤, script import·:164-165·:182-186·:206-222, scoped CSS `.skx-history-item__meta .skx-history-item__time` 뒤)
- Test: `frontend/tests/unit/sidebarResearch.test.ts`(새 파일)

기준선(Task N2 뒤): 전체 Task N1 뒤 수 + 4.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/sidebarResearch.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/sidebarResearch.test.ts
import { describe, expect, it } from "vitest";
import type { HistoryResearchStatus } from "~/types/history";
import {
  LIVE_RESEARCH_STATUSES,
  allResearchLabel,
  isLiveResearch,
  researchBadge,
  researchRowLine,
} from "~/utils/sidebarResearch";
import { stepLine } from "~/utils/workPhase";

// 끝난 딥리서치 — 이어간 연구는 phase·progress·generating 을 더 싣는다(app/schemas/history.py ResearchStatus)
function done(over: Partial<HistoryResearchStatus> = {}): HistoryResearchStatus {
  return { status: "completed", stage: "synthesized", ...over };
}

describe("isLiveResearch", () => {
  it("진행 중 잡 상태면 참, 승인 대기·끝난 잡·상태 없음은 거짓", () => {
    expect(LIVE_RESEARCH_STATUSES).toEqual(["created", "planning", "approved", "queued", "running"]);
    for (const status of LIVE_RESEARCH_STATUSES) expect(isLiveResearch({ status, stage: "planned" })).toBe(true);
    expect(isLiveResearch({ status: "awaiting_approval", stage: "planned" })).toBe(false);
    expect(isLiveResearch(done())).toBe(false);
    expect(isLiveResearch(done({ status: "failed" }))).toBe(false);
    expect(isLiveResearch(undefined)).toBe(false);
    expect(isLiveResearch(null)).toBe(false);
  });

  it("끝난 잡이라도 이어간 연구에 진행 중 생성이 있으면 참", () => {
    expect(isLiveResearch(done({ phase: "topics", generating: true }))).toBe(true);
    expect(isLiveResearch(done({ phase: "topics", generating: false }))).toBe(false);
  });
});

describe("researchRowLine", () => {
  it("이어가지 않은 연구(phase 없음)는 null", () => {
    expect(researchRowLine(done())).toBeNull();
    expect(researchRowLine(done({ phase: null, progress: null, generating: false }))).toBeNull();
    expect(researchRowLine({ status: "running", stage: "planned" })).toBeNull();
    expect(researchRowLine(undefined)).toBeNull();
  });

  it("단계 글은 workPhase.stepLine 을 그대로 쓰고 단계마다 수를 잇는다", () => {
    // 기대값을 stepLine 으로 만든다 — 06e 가 단계 이름을 바꿔도(제목 고르기·참고문헌 선택하기·보고서) 깨지지 않는다
    const progress = { topics: 4, reading: 12, sections: 3, sections_total: 6 };
    expect(researchRowLine(done({ phase: "topics", progress }))).toBe(`${stepLine("topics")} · 후보 4`);
    expect(researchRowLine(done({ phase: "reading", progress }))).toBe(`${stepLine("reading")} · 12편 담음`);
    expect(researchRowLine(done({ phase: "proposal", progress }))).toBe(`${stepLine("proposal")} · 3/6절`);
    expect(researchRowLine(done({ phase: "done", progress }))).toBe(stepLine("done"));
    // 후보·담음이 0 이면 수를 붙이지 않는다. 절은 전체 수를 알면 0 부터 센다
    const zero = { topics: 0, reading: 0, sections: 0, sections_total: 6 };
    expect(researchRowLine(done({ phase: "topics", progress: zero }))).toBe(stepLine("topics"));
    expect(researchRowLine(done({ phase: "reading", progress: zero }))).toBe(stepLine("reading"));
    expect(researchRowLine(done({ phase: "proposal", progress: { sections_total: 6 } }))).toBe(
      `${stepLine("proposal")} · 0/6절`,
    );
  });

  it("진행 중 생성이 있으면 '생성 중'을 잇는다", () => {
    expect(researchRowLine(done({ phase: "topics", progress: { topics: 2 }, generating: true }))).toBe(
      `${stepLine("topics")} · 후보 2 · 생성 중`,
    );
    expect(researchRowLine(done({ phase: "proposal", progress: {}, generating: true }))).toBe(
      `${stepLine("proposal")} · 생성 중`,
    );
  });

  it("progress 가 비었으면(06a 연구) 수를 붙이지 않는다", () => {
    expect(researchRowLine(done({ phase: "reading", progress: {} }))).toBe(stepLine("reading"));
    expect(researchRowLine(done({ phase: "proposal", progress: null }))).toBe(stepLine("proposal"));
    expect(researchRowLine(done({ phase: "topics" }))).toBe(stepLine("topics"));
  });
});

describe("researchBadge", () => {
  it("잡 상태로 배지를 고르고, 상태가 없으면 '알 수 없음'(사이드바·/research 홈이 같이 쓴다)", () => {
    expect(researchBadge(done())).toEqual({ label: "완료", tone: "done" });
    expect(researchBadge(done({ status: "failed" }))).toEqual({ label: "실패", tone: "failed" });
    expect(researchBadge(done({ status: "canceled" }))).toEqual({ label: "취소", tone: "canceled" });
    expect(researchBadge({ status: "awaiting_approval", stage: "planned" })).toEqual({ label: "승인 대기", tone: "waiting" });
    expect(researchBadge({ status: "queued", stage: "planned" })).toEqual({ label: "진행 중", tone: "running" });
    expect(researchBadge({ status: "running", stage: "explored" })).toEqual({ label: "진행 중", tone: "running" });
    expect(researchBadge(undefined)).toEqual({ label: "알 수 없음", tone: "unknown" });
  });
});

describe("allResearchLabel", () => {
  it("total 을 알면 '모두 보기 (N)'(0 이면 '모두 보기 (0)'), 모르면 '모두 보기'", () => {
    expect(allResearchLabel(12)).toBe("모두 보기 (12)");
    expect(allResearchLabel(0)).toBe("모두 보기 (0)");
    expect(allResearchLabel(null)).toBe("모두 보기");
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
// 사이드바 딥리서치 탭(과 /research 홈)의 줄 — 폴링할 연구, 이어간 연구의 단계 한 줄, 배지, '모두 보기 (N)'.
// 단계 이름은 workPhase.stepLine 을 그대로 읽는다(06e 의 이름 바꾸기가 따라온다 — 여기서 단계 글을 새로 쓰지 않는다)
import type { HistoryResearchStatus } from "~/types/history";
import { stepLine } from "~/utils/workPhase";

// 이 상태의 딥리서치가 있으면 배지가 바뀔 수 있다 — 승인 대기는 사용자가 움직여야 바뀌므로 뺀다
export const LIVE_RESEARCH_STATUSES: readonly string[] = ["created", "planning", "approved", "queued", "running"];

// 사이드바가 30초마다 다시 읽을 연구 — 잡이 도는 중이거나, 끝난 잡이라도 이어간 연구에 진행 중 생성(queued·running)이
// 있으면 단계 줄의 수('후보 n'·'n/6절')가 바뀐다(spec §6-4)
export function isLiveResearch(r: HistoryResearchStatus | null | undefined): boolean {
  if (!r) return false;
  return LIVE_RESEARCH_STATUSES.includes(r.status) || r.generating === true;
}

// 이어간 연구 줄에 작게 넣는 단계 한 줄 — `2/4 단계 · 주제 고르는 중 · 후보 4 · 생성 중`. 이어가지 않은 연구는 null
// (지금처럼 배지만). 수는 06b progress(카드가 있는 후보·담음·채운 절) — 0 이거나 모르면(06a 연구의 빈 progress) 뺀다
export function researchRowLine(r: HistoryResearchStatus | null | undefined): string | null {
  if (!r?.phase) return null;
  const phase = r.phase;
  const p = r.progress ?? {};
  let count = "";
  if (phase === "topics" && (p.topics ?? 0) > 0) count = `후보 ${p.topics}`;
  else if (phase === "reading" && (p.reading ?? 0) > 0) count = `${p.reading}편 담음`;
  else if (phase === "proposal" && p.sections_total) count = `${p.sections ?? 0}/${p.sections_total}절`;
  return [stepLine(phase), count, r.generating ? "생성 중" : ""].filter(Boolean).join(" · ");
}

// 잡 상태 배지 — 사이드바 줄과 /research 홈의 줄이 같은 이름을 쓴다. 상태를 모르면(기록에 상태가 없음) '알 수 없음'
export function researchBadge(r: HistoryResearchStatus | null | undefined): { label: string; tone: string } {
  switch (r?.status) {
    case "completed":
      return { label: "완료", tone: "done" };
    case "failed":
      return { label: "실패", tone: "failed" };
    case "canceled":
      return { label: "취소", tone: "canceled" };
    case "awaiting_approval":
      return { label: "승인 대기", tone: "waiting" };
    case undefined:
      return { label: "알 수 없음", tone: "unknown" };
    default:
      return { label: "진행 중", tone: "running" };
  }
}

// 딥리서치 탭 목록 끝의 /research 링크. total 은 기록 목록 응답의 kind 별 수(06e 서버부터) — 모르면 N 없이
export function allResearchLabel(total: number | null): string {
  return total === null ? "모두 보기" : `모두 보기 (${total})`;
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/sidebarResearch.test.ts tests/unit/workPhase.test.ts`
Expected: `Test Files  2 passed (2)` / `Tests  28 passed (28)`(sidebarResearch 8 + workPhase 20 — 06e 파일 `workPhase.ts` 는 읽기만 했다)

- [ ] **Step 5: 사이드바에 단계 줄·모두 보기를 단다**

`frontend/components/AppSidebar.vue` — 항목 버튼 안(:105-106). old:

```vue
              <span class="skx-history-item__query">{{ h.title }}</span>
              <span class="skx-history-item__meta">
```

new:

```vue
              <span class="skx-history-item__query">{{ h.title }}</span>
              <!-- 이어간 연구에만 — 그 연구의 단계·수. 이어가지 않은 딥리서치는 지금처럼 배지만 -->
              <span v-if="rowLineOf(h)" class="skx-history-item__step">{{ rowLineOf(h) }}</span>
              <span class="skx-history-item__meta">
```

목록 끝(:124-126 — `</ul>` 은 파일에 하나). old:

```vue
        </ul>
      </ClientOnly>
    </div>
```

new:

```vue
        </ul>
        <!-- 목록이 비어도 건다 — 예시 연구가 보이는 /research 홈으로 가는 길은 이 링크뿐이다(기록 없는 새 브라우저) -->
        <NuxtLink v-if="historyTab === 'research'" to="/research" class="skx-history__all">
          {{ allResearchLabel(researchTotal) }}
        </NuxtLink>
      </ClientOnly>
    </div>
```

- [ ] **Step 6: script — import·폴링 조건·수·배지**

import(:144) — old:

```ts
import { activeIdFor, activeKindForPath, routeFor } from "~/utils/historyRoute";
```

new:

```ts
import { activeIdFor, activeKindForPath, routeFor } from "~/utils/historyRoute";
import { allResearchLabel, isLiveResearch, researchBadge, researchRowLine } from "~/utils/sidebarResearch";
```

진행 중 상태 집합(:164-166 — `utils/sidebarResearch.ts` 의 `LIVE_RESEARCH_STATUSES` 로 옮겼다). old:

```ts
// 이 상태의 딥리서치가 있으면 배지가 바뀔 수 있다 — 승인 대기는 사용자가 움직여야 바뀌므로 뺀다
const LIVE_STATUSES = new Set(["created", "planning", "approved", "queued", "running"]);
const POLL_MS = 30_000;
```

new:

```ts
const POLL_MS = 30_000;
```

폴링 조건(:182-186) — old:

```ts
const hasLiveResearch = computed(() =>
  history
    .byKind("research")
    .value.some((h) => h.kind === "research" && !!h.research && LIVE_STATUSES.has(h.research.status)),
);
```

new:

```ts
// 잡이 도는 연구와 생성이 도는 이어간 연구가 있으면 30초마다 다시 읽는다 — 배지·단계 줄이 바뀐다
const hasLiveResearch = computed(() =>
  history.byKind("research").value.some((h) => h.kind === "research" && isLiveResearch(h.research)),
);
// 딥리서치 기록 전체 수 — 06e 전 서버면 null('모두 보기'만)
const researchTotal = history.totalOf("research");
```

배지(:206-222) — old:

```ts
function badgeOf(h: HistoryEntry): { label: string; tone: string } {
  const status = h.kind === "research" ? h.research?.status : undefined;
  switch (status) {
    case "completed":
      return { label: "완료", tone: "done" };
    case "failed":
      return { label: "실패", tone: "failed" };
    case "canceled":
      return { label: "취소", tone: "canceled" };
    case "awaiting_approval":
      return { label: "승인 대기", tone: "waiting" };
    case undefined:
      return { label: "알 수 없음", tone: "unknown" };
    default:
      return { label: "진행 중", tone: "running" };
  }
}
```

new:

```ts
function badgeOf(h: HistoryEntry): { label: string; tone: string } {
  return researchBadge(h.kind === "research" ? h.research : undefined);
}

function rowLineOf(h: HistoryEntry): string | null {
  return h.kind === "research" ? researchRowLine(h.research) : null;
}
```

- [ ] **Step 7: scoped CSS**

`<style scoped>` 의 `.skx-history-item__meta .skx-history-item__time` 규칙 뒤 — old:

```css
.skx-history-item__meta .skx-history-item__time {
  width: auto;
}
```

new:

```css
.skx-history-item__meta .skx-history-item__time {
  width: auto;
}
/* 이어간 연구의 단계 한 줄 — 배지와 같은 작은 글, 넘치면 말줄임 */
.skx-history-item__step {
  width: 100%;
  font-size: 0.5rem;
  font-weight: 600;
  line-height: 1.5;
  color: var(--skx-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.skx-history__all {
  flex: none;
  align-self: flex-start;
  padding: 0.2rem 0.4rem;
  border-radius: var(--skx-radius-sm);
  font-size: 0.6rem;
  font-weight: 600;
  color: var(--skx-primary);
  text-decoration: none;
}
.skx-history__all:hover,
.skx-history__all:focus-visible {
  text-decoration: underline;
}
```

- [ ] **Step 8: 전체 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "LIVE_STATUSES" components/AppSidebar.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected:
- `0`(옛 상수가 남지 않았다)
- vitest 실패 0, `Test Files` 는 Task N2 뒤 + 1, `Tests` 는 Task N2 뒤 수 + 8
- `0`
- `0`(Task D2 뒤 그대로 — 새 이름은 모두 이 파일에서만 내보낸다)
- `└  ✨ Build complete!`

확인(손 — 마무리 운영 확인 Task Z6 Step 5 에 이미 있다): 기록이 없는 새 시크릿 창의 딥리서치 탭에도 빈 문구 아래 '모두 보기'(06e fastapi 배포 전이면 N 없이)가 서고 `/research` 로 간다. 이어간 연구 줄에 `stepLine` 의 단계 글과 수가 붙고, 생성이 도는 동안 '생성 중'.

- [ ] **Step 9: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/sidebarResearch.ts frontend/tests/unit/sidebarResearch.test.ts frontend/components/AppSidebar.vue && git status --short && git commit -m "[Feat] round06d — 사이드바 딥리서치 탭의 이어간 연구 줄에 단계를 작게 넣는다(workPhase.stepLine 그대로 + 후보 n·n편 담음·n/6절 + 생성 중 — 06d 는 단계 이름을 새로 쓰지 않아 06e 의 이름 바꾸기가 따라온다). 폴링 조건에 진행 중 생성이 있는 이어간 연구를 더하고, 목록 끝에 /research 로 가는 '모두 보기 (N)'(기록 total — 06e 전 서버면 N 없이)를 단다. 링크는 기록이 없어도 빈 문구 아래에 선다 — 예시 연구로 가는 길은 이것뿐이다. 상태 → 배지 판단은 utils/sidebarResearch.ts 로 옮겨 /research 홈과 함께 쓴다"
```

Expected: `A  frontend/tests/unit/sidebarResearch.test.ts`·`A  frontend/utils/sidebarResearch.ts`·`M  frontend/components/AppSidebar.vue`, 커밋 1개.

---

### Task N4: 빠른검색 [딥리서치로 더 깊게]

spec §12-3 '빠른검색(D17)' 첫 줄 — 답 끝 [딥리서치로 더 깊게] 카드: 그 질문을 입력창에 딥리서치 칩을 켠 채 채운다, 바로 시작하지 않는다(`fillResearchDraft` 재사용). D17('새 딥리서치는 답 끝 [딥리서치로 더 깊게] 로만 시작한다')·D26. 정함 16.

**알아 둘 것:**
- **흐름(정함 16):** 카드는 `NuxtLink` 로 `/papers?draft=<검색어>` 에 간다. 같은 페이지라 다시 마운트되지 않고, 쿼리 감시(`pages/papers/index.vue:1082-1087` — `h`·`q`)가 `h`·`q` 가 사라진 것을 보고 `restoreFromQuery`(:907)를 부른다 → `h`·`q` 가 없으니 `goLanding()` → `fillResearchDraft()`(:895-903)가 `?draft=` 를 지우고(`router.replace`) 랜딩 입력창에 그 질문을 넣은 뒤 `nextTick` 에 + 메뉴의 딥리서치 칩을 켠다. 검색·딥리서치는 시작하지 않는다 — 사용자가 고쳐 쓰고 보낸다. 결과 화면 검색바의 + 메뉴(:46)에는 ref 가 없어 그 자리에서 칩을 켤 수 없다 — 그래서 랜딩으로 보낸다. 상세 페이지의 [이 논문으로 딥리서치](`paperResearchUrl`)와 같은 `?draft=` 주소다.
- **검색어:** 검색바(`currentQuery` — 사용자가 고치는 중일 수 있다)가 아니라 화면 결과의 검색어 `resultQuery`(:616 — 검색·기록 복원이 앞뒤 공백을 떼어 넣는다)로 만든다. 줄바꿈·겹친 공백은 한 칸으로 줄이고, 질문으로 쓸 수 없는 길이(`questionProblem` — 2자 미만·500자 초과, 서버 `QUESTION_MIN`·`QUESTION_MAX` 와 같은 경계)면 `null` 이라 카드를 그리지 않는다.
- **그리는 조건:** AI 답이 끝났을 때(`aiText && !aiLoading`) — 기존 DeepRead 안내(`skx-ai-hint`, :186-190)와 같은 조건이고 그 바로 아래 `.skx-pai` 칸(세로 flex·gap 0.8rem, 옅은 보라 바탕) 안에 흰 카드로 선다.
- `:564-569`(BookChat — 06e 가 `doc-kind="paper"` 를 넣는다)는 건드리지 않는다. 이 Task 가 `pages/papers/index.vue` 를 처음 고친다 — 줄 번호가 da80f23 그대로다(Task N6 은 이 Task 뒤의 글로 자리를 잡는다).

**Files:**
- Modify: `frontend/utils/paperResearch.ts`(import 한 줄, `paperResearchUrl` :29-31 아래 함수)
- Modify: `frontend/pages/papers/index.vue`(:186-191 카드, :592 import, :647-649 아래 computed)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위 `.rs-deeper*`)
- Test: `frontend/tests/unit/paperResearch.test.ts`(:4 import, 끝에 describe — 10 → 12)

기준선(Task N3 뒤): 전체 Task N2 뒤 + 8. `paperResearch.test.ts` 는 `Tests  10 passed (10)`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/paperResearch.test.ts` :4 — 고치기 전:

```ts
import { paperResearchQuestion, paperResearchUrl, readResearchDraft } from "~/utils/paperResearch";
```

고친 뒤:

```ts
import { deeperResearchUrl, paperResearchQuestion, paperResearchUrl, readResearchDraft } from "~/utils/paperResearch";
```

파일 끝(describe `paperResearchUrl · readResearchDraft` 의 닫는 `});` 뒤)에 붙인다 — old:

```ts
    expect(readResearchDraft({ draft: [" 질문 ", "다른"] })).toBe("질문");
  });
});
```

new:

```ts
    expect(readResearchDraft({ draft: [" 질문 ", "다른"] })).toBe("질문");
  });
});

describe("deeperResearchUrl", () => {
  it("검색어를 공백 정리해 ?draft= 주소로 만든다(readResearchDraft 가 그대로 읽는다)", () => {
    const url = deeperResearchUrl("  노인의 우울과\n 사회적   지지  ");
    expect(url).toBe(paperResearchUrl("노인의 우울과 사회적 지지"));
    expect(readResearchDraft(parseQuery(url!.split("?")[1] ?? ""))).toBe("노인의 우울과 사회적 지지");
  });

  it("질문으로 쓸 수 없는 길이(2자 미만·500자 초과)면 null", () => {
    expect(deeperResearchUrl("")).toBeNull();
    expect(deeperResearchUrl("  가  ")).toBeNull();
    expect(deeperResearchUrl("가".repeat(501))).toBeNull();
    expect(deeperResearchUrl("가".repeat(500))).toBe(paperResearchUrl("가".repeat(500)));
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/paperResearch.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  2 failed | 10 passed (12)` — 새 두 `it` 이 `TypeError: (0 , deeperResearchUrl) is not a function`(아직 내보내지 않는다).

- [ ] **Step 3: 구현한다 — 순수 함수**

`frontend/utils/paperResearch.ts` :3 — 고치기 전:

```ts
import { firstValue } from "~/utils/detailSource";
```

고친 뒤:

```ts
import { firstValue } from "~/utils/detailSource";
import { questionProblem } from "~/utils/researchInput";
```

`paperResearchUrl`(:29-31) 바로 뒤 — old:

```ts
export function paperResearchUrl(question: string): string {
  return `/papers?${new URLSearchParams({ draft: question })}`;
}
```

new:

```ts
export function paperResearchUrl(question: string): string {
  return `/papers?${new URLSearchParams({ draft: question })}`;
}

// 빠른검색 답 끝 [딥리서치로 더 깊게](D17) — 그 검색어를 같은 ?draft= 로 넘긴다. /papers 의 fillResearchDraft 가
// 랜딩 입력창에 딥리서치 칩을 켠 채 채운다(바로 시작하지 않는다). 질문으로 쓸 수 없는 길이면 null — 카드를 그리지 않는다
export function deeperResearchUrl(query: string): string | null {
  const q = query.trim().replace(/\s+/g, " ");
  return questionProblem(q) ? null : paperResearchUrl(q);
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/paperResearch.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  12 passed (12)`

- [ ] **Step 5: 답 끝 카드를 단다**

`frontend/pages/papers/index.vue` :186-191 — DeepRead 안내와 AI 칸 닫는 줄(파일에 하나). old:

```vue
              더 깊이 알고 싶은 논문은 <strong>DeepRead</strong>로 자유롭게
              질문하며 분석해보세요
            </p>
          </section>
```

new:

```vue
              더 깊이 알고 싶은 논문은 <strong>DeepRead</strong>로 자유롭게
              질문하며 분석해보세요
            </p>
            <!-- 이 검색어를 딥리서치로 — 랜딩 입력창에 딥리서치 칩을 켠 채 채운다(바로 시작하지 않는다, D17) -->
            <div v-if="deeperUrl && aiText && !aiLoading" class="rs-deeper">
              <p class="rs-deeper__text">
                <strong>딥리서치</strong>는 이 질문을 하위질문으로 나눠 근거 논문을 모으고 인용이 달린 보고서를 씁니다.
              </p>
              <NuxtLink :to="deeperUrl" class="rs-btn rs-btn--small">딥리서치로 더 깊게</NuxtLink>
            </div>
          </section>
```

import(:592) — 고치기 전:

```ts
import { readResearchDraft } from "~/utils/paperResearch";
```

고친 뒤:

```ts
import { deeperResearchUrl, readResearchDraft } from "~/utils/paperResearch";
```

computed — `renderedAiText`(:647-649) 바로 뒤. old:

```ts
const renderedAiText = computed(() =>
  aiText.value ? (marked.parse(aiText.value) as string) : "",
);
```

new:

```ts
const renderedAiText = computed(() =>
  aiText.value ? (marked.parse(aiText.value) as string) : "",
);
// 답 끝 [딥리서치로 더 깊게] 의 주소 — 화면 결과의 검색어로 만든다(검색바는 고치는 중일 수 있다)
const deeperUrl = computed(() => deeperResearchUrl(resultQuery.value));
```

- [ ] **Step 6: 스타일**

`frontend/assets/css/research.css` — 인쇄 앵커 한 줄을 old 로 잡는다(파트 D·L 이 앞에 블록을 넣었어도 글자가 같다). old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 빠른검색 답 끝 [딥리서치로 더 깊게] ──────────────────── */
/* 논문 검색 결과의 AI 답 칸(.skx-pai — 옅은 보라 바탕) 안에 흰 카드로 선다 */
.rs-deeper {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  padding: 0.7rem 0.8rem;
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
}
.rs-deeper__text {
  flex: 1 1 14rem;
  margin: 0;
  font-size: 0.65rem;
  line-height: 1.5;
  color: var(--skx-gray-1);
}
.rs-deeper__text strong {
  font-weight: 700;
  color: var(--skx-primary);
}
/* NuxtLink 라 style_skovix.css 의 a:hover·a:visited(color: inherit, 0,1,1)가 .rs-btn(0,1,0)의 흰 글자를 덮는다 */
.rs-deeper .rs-btn,
.rs-deeper .rs-btn:visited,
.rs-deeper .rs-btn:hover {
  color: var(--skx-white);
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

(버튼이 `<a>`(NuxtLink)인 `.rs-btn` 은 지금 `[id].vue:13` 의 오류 카드 하나뿐이고 `.rs-btn:hover`·`a.rs-btn` 규칙이 없어 드러난 적이 없다. 전역 `a, a:visited, a:hover { color: inherit; }`(`style_skovix.css:170-174`)가 이기면 남색 바탕에 body 글자색 `#111` 이 와 대비가 약 2.5:1 로 떨어진다 — 위 마지막 규칙의 특이성 (0,2,0)·(0,3,0)이 전역 규칙을 이긴다.)

- [ ] **Step 7: 전체 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff -- frontend/pages/papers/index.vue | grep -cE "BookChat|doc-kind"
```

Expected: vitest 실패 0, `Tests` 는 Task N3 뒤 수 + 2(파일 수 그대로) · `0` · `└  ✨ Build complete!` · `0`(06e 의 BookChat 자리를 건드리지 않았다).

확인(손 — Task Z6 Step 5 에 이미 있다): `/papers` 에서 검색해 AI 답이 끝나면 답 끝에 카드(버튼에 마우스를 올려도, 한 번 누른 뒤 같은 검색으로 돌아와도 버튼 글자가 흰색) → 누르면 주소가 `/papers?draft=…` 를 거쳐 `/papers` 로 바뀌고 랜딩 입력창에 그 질문과 딥리서치 칩이 켜진다(검색·딥리서치를 시작하지 않는다).

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/paperResearch.ts frontend/tests/unit/paperResearch.test.ts frontend/pages/papers/index.vue frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 논문 빠른검색의 AI 답 끝에 [딥리서치로 더 깊게] 카드를 단다(D17). 화면 결과의 검색어를 공백 정리해 상세의 [이 논문으로 딥리서치] 와 같은 ?draft= 주소로 넘기면 기존 fillResearchDraft 가 랜딩 입력창에 그 질문을 딥리서치 칩과 함께 채운다 — 바로 시작하지 않고 사용자가 고쳐 보낸다. 질문으로 쓸 수 없는 길이(2자 미만·500자 초과)면 카드를 그리지 않는다"
```

Expected: `M` 네 줄, 커밋 1개.

---

### Task N5: `/research` 홈(새 연구·진행 중·내 연구·예시 연구) — 자르는 순서 2

spec §12-3 입구 '예시 연구 노출': 노출 자리는 `/research` 홈 한 곳(새 `pages/research/index.vue` — 새 연구 시작·진행 중·내 연구·예시 연구, §6-6, Q8 동의), 들어가는 길은 사이드바 딥리서치 탭의 '모두 보기 (N)'(Task N3), 읽기 전용(`research_works.is_example` — 쓰기 API 409)·실행 시각·코퍼스 범위 표시(시연 정직성 규칙), 목록은 `GET /api/research-works?example=1`. D26. 정함 15.

**알아 둘 것:**
- **진행 중·내 연구(정함 15):** history 목록을 직접 50건씩 읽는다(`GET /api/history?kind=research&limit=50&before=` — 서버 상한 `le=100`, `app/api/history.py:82`). `[더 보기]` 는 `next_cursor` 를 `before` 로 보낸다. 사이드바의 30건 상태(`useHistory`)와 따로 둔다 — N 이 30을 넘으면 사이드바 목록으로는 '모두'가 안 되고, 홈의 첫 쪽이 사이드바가 쓰는 브라우저 캐시(하이브리드 저장소의 `replaceKind`)를 갈아 끼우지도 않게 **서버 저장소**(`createServerStore` — 선 모양 → 화면 모양 `fromWire`·`total` 이 한 곳)로 읽는다. 진행 중 = `isLiveResearch`(잡이 돌거나 이어간 연구의 생성이 돎 — Task N3) 또는 승인 대기(사용자가 움직일 차례), 나머지(완료·실패·취소·상태 모름)가 내 연구다 — 둘 다 받은 순서(최신순). 줄은 제목·배지(`researchBadge` — 사이드바와 같은 판단)·단계 줄(`researchRowLine`)·날짜, 링크는 `routeFor(entry)`(`utils/historyRoute.ts` — 읽기만, 이어간 연구는 그 단계 화면 `?s=`). 쪽 경계가 밀려 같은 기록이 다시 오면 한 번만 둔다.
- **예시 연구:** `GET /api/research-works?example=1` 은 `{id, question, phase, created_at}` 만 준다(`app/api/research_work.py:300-322`, 상한 50) — 06d 는 백엔드를 바꾸지 않으므로 실행 시각·범위는 예시마다 `GET /api/research/{id}/work` 의 `corpus`(`useWorkApi().getWork` — 06e 파일, 읽기만)에서 읽는다. `corpus.at` 은 잡이 끝난 시각(`app/services/research_work/seeds.py:69`)이고 `kstDateTime`(`utils/reportDocument.ts:376`)으로 `2026년 10월 6일 09:30 실행`, 범위는 `scopeLine(corpus)`(`utils/workPhase.ts` — 범위 띠와 같은 글). 목록을 못 읽거나 예시가 없으면 섹션을 그리지 않는다(리허설 10/23~25 의 `mark_example.py` 지정 전에는 없다). 카드에 '읽기 전용' 배지와 `stepLine(phase)`, 링크는 `exampleRoute` = 도달한 단계 화면(`stepForPhase`).
- **새 연구 시작:** textarea(`maxlength` = `QUESTION_MAX` 500) + `[계획 세우기]`(`questionProblem` 이 있으면 막힘) → `useResearchStarter().startResearch(q)`(기록도 남긴다 — `composables/useResearch.ts:53-69`) → `navigateTo('/research/' + id)`. 오류는 `researchErrorMessage(e, "새 연구를 시작하지 못했습니다")`, 입력은 지우지 않는다. 429 `browser_active` 면 `[id].vue:50-52` 처럼 '진행 중인 연구 보기' 링크(`activeResearchId`)를 단다 — **지금 서버는 연구 만들기(`POST /api/research`)에서 이 429 를 내지 않고 승인·재시도(`app/api/research.py` `_to_run_queue` :142-183, 쓰는 곳 :274·:324)에서만 낸다.** 그래서 두 번째 질문은 잡이 만들어지고 연구 화면의 [승인] 에서 막힌다(그 화면이 같은 링크를 단다). 홈의 링크는 서버가 만들기에서도 막게 바뀌어도 같은 안내가 서게 둔 방어다. 엔터로 보내되 한글 조합 중의 엔터는 보내지 않는다(`SearchPlusMenu.vue` 와 같은 규칙).
- **API 는 마운트 뒤:** 기록·예시 API 는 브라우저 ID 헤더(`x-session-id` — `useApi`)가 있어야 한다 — 서버 렌더가 아니라 `onMounted` 에서 읽는다(사이드바·논문 화면과 같은 관례).
- **화면 골격:** `AppSidebar` + `<main class="rs-page rs-home">`(가운데 52rem). `.rs-page` 의 세로 flex·gap 과 공용 부품(`.rs-card`·`.rs-card--wait`·`.rs-card--error`·`.rs-btn`·`.rs-badge`·`.rs-muted`·`.rs-head__kicker`)을 그대로 쓴다 — 머리 kicker 는 Task D8 이 연구 화면과 함께 skx 칩으로 입힌 모양을 따른다. 새 규칙은 `.rs-home*` 만이고 `--skx-*` 토큰만 쓴다(새 색값 없음). 줄의 배지는 `rs-badge--${tone}` 인데 공용 `research.css:159-180` 에는 `--running`·`--done`·`--failed` 만 있다 — `researchBadge` 의 나머지 tone(`waiting`·`canceled`·`unknown` — 사이드바는 `AppSidebar.vue:352-365` 의 `is-*` 로 구분한다)이 기본 회색으로 섞이지 않게 `.rs-home .rs-badge--waiting`(옅은 남색 바탕·남색 글자)·`.rs-home .rs-badge--canceled`·`--unknown`(옅은 회색 글자)을 `.rs-home*` 블록 안에 둔다(공용 `.rs-badge` 규칙은 고치지 않는다). 사이드바 탭은 `/research` 경로에서 이미 딥리서치다(`activeKindForPath` — `utils/historyRoute.ts:56`).
- `research.css` 블록은 인쇄 앵커 바로 위 — Task N4 의 `.rs-deeper` 블록 뒤에 선다.
- **자르는 순서 2(spec §12-6):** 10/16 까지 끝내지 못해 자르면 이 Task 를 하지 않고(Task N6 도 하지 않는다) Task N7 을 한다.

**Files:**
- Create: `frontend/utils/researchHome.ts`
- Create: `frontend/composables/useResearchWorks.ts`
- Create: `frontend/pages/research/index.vue`
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위 `.rs-home*`)
- Test: `frontend/tests/unit/researchHome.test.ts`(새 파일)

기준선(Task N4 뒤): 전체 Task N3 뒤 + 2.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchHome.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/researchHome.test.ts
import { describe, expect, it } from "vitest";
import { HOME_PAGE_SIZE, exampleMeta, exampleRoute, homeGroups } from "~/utils/researchHome";
import { scopeLine } from "~/utils/workPhase";
import { ID1, ID2, ID3, researchEntry } from "./helpers/fakeHistory";

const ID4 = "44444444-4444-4444-8444-444444444444";
const ID5 = "55555555-5555-4555-8555-555555555555";
const ID6 = "66666666-6666-4666-8666-666666666666";

describe("homeGroups", () => {
  it("진행 중(진행 상태·승인 대기·진행 중 생성)과 내 연구로 나누고 받은 순서를 지킨다", () => {
    const running = researchEntry(ID1, { research: { status: "running", stage: "planned" } });
    const done = researchEntry(ID2, { research: { status: "completed", stage: "synthesized" } });
    const waiting = researchEntry(ID3, { research: { status: "awaiting_approval", stage: "planned" } });
    const generating = researchEntry(ID4, {
      research: { status: "completed", stage: "synthesized", phase: "topics", progress: {}, generating: true },
    });
    const failed = researchEntry(ID5, { research: { status: "failed", stage: "planned" } });
    // 상태를 모르는 기록(조회 실패·옛 기록)은 내 연구에 둔다
    const unknown = researchEntry(ID6);
    const { live, mine } = homeGroups([running, done, waiting, generating, failed, unknown]);
    expect(live.map((e) => e.id)).toEqual([ID1, ID3, ID4]);
    expect(mine.map((e) => e.id)).toEqual([ID2, ID5, ID6]);
    expect(HOME_PAGE_SIZE).toBe(50);
  });
});

describe("exampleMeta", () => {
  it("실행 시각은 corpus.at 의 KST, 범위는 scopeLine", () => {
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
  it("예시 연구는 도달한 단계 화면(stepForPhase)으로 연다", () => {
    expect(exampleRoute({ id: ID1, phase: "reading" })).toEqual({ path: `/research/${ID1}`, query: { s: "reading" } });
    expect(exampleRoute({ id: ID2, phase: "done" })).toEqual({ path: `/research/${ID2}`, query: { s: "proposal" } });
    expect(exampleRoute({ id: ID3, phase: "topics" })).toEqual({ path: `/research/${ID3}`, query: { s: "topics" } });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchHome.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  no tests` — 수집에서 `Error: Cannot find module '~/utils/researchHome' imported from '…/frontend/tests/unit/researchHome.test.ts'`.

- [ ] **Step 3: 구현한다 — 순수 함수**

`frontend/utils/researchHome.ts` (새 파일, 전체):

```ts
// frontend/utils/researchHome.ts
// /research 홈(D26) — 진행 중·내 연구 나누기, 예시 연구의 실행 시각·범위 줄과 여는 주소(.vue 는 그리기만 한다)
import type { ResearchEntry } from "~/types/history";
import type { Corpus, WorkPhase } from "~/types/work";
import { kstDateTime } from "~/utils/reportDocument";
import { isLiveResearch } from "~/utils/sidebarResearch";
import { scopeLine, stepForPhase } from "~/utils/workPhase";

// GET /api/research-works(?example=1) 의 items[] — app/api/research_work.py list_works(상한 50)
export interface WorkListItem {
  id: string;
  question: string;
  phase: WorkPhase;
  created_at: string | null;
}

export interface WorkListOut {
  items: WorkListItem[];
}

// 딥리서치 기록 한 쪽 — total 은 06e 서버부터(없으면 null)
export interface ResearchPage {
  entries: ResearchEntry[];
  nextCursor: string | null;
  total: number | null;
}

// 홈은 사이드바(30건)보다 한 번에 많이 읽는다 — 서버 상한(app/api/history.py limit le=100) 안
export const HOME_PAGE_SIZE = 50;

// 진행 중 = 잡이 돌거나 이어간 연구의 생성이 도는 연구, 그리고 계획 승인을 기다리는 연구(사용자가 움직일 차례).
// 나머지(완료·실패·취소·상태 모름)가 내 연구다. 둘 다 받은 순서(최신순)를 지킨다
export function homeGroups(entries: readonly ResearchEntry[]): { live: ResearchEntry[]; mine: ResearchEntry[] } {
  const live: ResearchEntry[] = [];
  const mine: ResearchEntry[] = [];
  for (const e of entries) {
    if (isLiveResearch(e.research) || e.research?.status === "awaiting_approval") live.push(e);
    else mine.push(e);
  }
  return { live, mine };
}

// 예시 연구 카드의 실행 시각·코퍼스 범위(시연 정직성 규칙 — spec §12-3). at 은 잡이 끝난 시각
// (research_works.corpus_snapshot, seeds.py). 모르는 칸은 null — 카드가 그 줄을 그리지 않는다
export function exampleMeta(corpus: Corpus | null | undefined): { ranAt: string | null; scope: string | null } {
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

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchHome.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  4 passed (4)`

- [ ] **Step 5: 구현한다 — 목록 API**

`frontend/composables/useResearchWorks.ts` (새 파일, 전체 — Task N6 이 `useAddToWork` 를 더한다):

```ts
// frontend/composables/useResearchWorks.ts
// /research 홈과 빠른검색 [담기] 가 읽는 연구 목록 — 이어간 연구(GET /api/research-works), 예시 연구(?example=1),
// 이 브라우저의 딥리서치 기록 한 쪽(GET /api/history?kind=research). 사이드바의 기록 상태(useHistory — 30건)와 따로 읽는다
import type { ResearchEntry } from "~/types/history";
import { createServerStore, type HistoryFetcher } from "~/utils/historyStore";
import { HOME_PAGE_SIZE, type ResearchPage, type WorkListOut } from "~/utils/researchHome";
import { useApi } from "./useApi";

export function useResearchWorksApi() {
  const api = useApi();
  // 기록 목록은 기록 가게의 서버 저장소로 읽는다(선 모양 → 화면 모양 fromWire·total 이 한 곳). 하이브리드 저장소를
  // 거치지 않는다 — 홈의 첫 쪽(50건)이 사이드바가 쓰는 브라우저 캐시를 갈아 끼우지 않게. 타입 단언은 useHistory 와 같은 까닭
  const history = createServerStore(api as unknown as HistoryFetcher);
  return {
    listWorks: (example: boolean) => api<WorkListOut>("/research-works", { query: example ? { example: 1 } : {} }),
    async listResearch(before?: string): Promise<ResearchPage> {
      const res = await history.list("research", { limit: HOME_PAGE_SIZE, before });
      return {
        entries: res.items.filter((e): e is ResearchEntry => e.kind === "research"),
        nextCursor: res.nextCursor,
        total: res.total ?? null,
      };
    },
  };
}
```

- [ ] **Step 6: 구현한다 — 홈 페이지**

`frontend/pages/research/index.vue` (새 파일, 전체):

```vue
<!-- frontend/pages/research/index.vue -->
<!-- 딥리서치 홈(D26) — 새 연구 시작·진행 중·내 연구·예시 연구. 들어오는 길은 사이드바 딥리서치 탭의 '모두 보기 (N)' -->
<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="rs-page rs-home">
      <header class="rs-home__head">
        <p class="rs-head__kicker">딥리서치</p>
        <h1 class="rs-home__title">연구</h1>
        <p class="rs-muted">질문 하나를 하위질문으로 나눠 소장 KCI 논문에서 근거를 모으고, 인용이 달린 보고서를 씁니다.</p>
      </header>

      <!-- 새 연구 — 계획을 세운 뒤 연구 화면에서 승인하면 근거 수집을 시작한다 -->
      <section class="rs-card" aria-labelledby="rs-home-new">
        <h2 id="rs-home-new" class="rs-card__title">새 연구 시작</h2>
        <label class="rs-home__field">
          <span class="skx-sr-only">연구 질문</span>
          <textarea
            v-model="question"
            class="rs-home__input"
            rows="3"
            :maxlength="QUESTION_MAX"
            placeholder="알고 싶은 연구 질문을 문장으로 적어 보세요"
            :disabled="starting"
            @keydown.enter.exact="onEnter"
          ></textarea>
        </label>
        <div class="rs-home__new-foot">
          <p v-if="startError" class="rs-home__problem" role="alert">
            {{ startError }}
            <NuxtLink v-if="activeJobId" :to="`/research/${encodeURIComponent(activeJobId)}`">진행 중인 연구 보기</NuxtLink>
          </p>
          <p v-else-if="question.trim() && problem" class="rs-home__problem">{{ problem }}</p>
          <button type="button" class="rs-btn" :disabled="starting || !!problem" @click="start">
            {{ starting ? "시작하는 중…" : "계획 세우기" }}
          </button>
        </div>
      </section>

      <div v-if="listState === 'loading'" class="rs-card rs-card--wait" role="status">
        <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
        <p>연구 기록을 불러오는 중입니다</p>
      </div>
      <div v-else-if="listState === 'error'" class="rs-card rs-card--error">
        <p>연구 기록을 불러오지 못했습니다.</p>
        <div class="rs-card__actions">
          <button type="button" class="rs-btn" @click="loadFirst">다시 불러오기</button>
        </div>
      </div>
      <template v-else>
        <p v-if="!entries.length" class="rs-card rs-muted">연구 기록이 없습니다. 위에서 질문을 입력해 시작해 보세요.</p>

        <!-- 진행 중(잡이 돌거나 승인을 기다리거나 이어간 연구의 생성이 도는 연구) → 내 연구. 비어 있는 묶음은 그리지 않는다 -->
        <section
          v-for="block in blocks"
          :key="block.id"
          class="rs-home__block"
          :aria-labelledby="`rs-home-${block.id}`"
        >
          <h2 :id="`rs-home-${block.id}`" class="rs-home__heading">{{ block.title }}</h2>
          <ul class="rs-home__list">
            <li v-for="row in block.rows" :key="row.id" class="rs-home__row">
              <NuxtLink :to="row.to" class="rs-home__link">
                <span class="rs-home__q">{{ row.title }}</span>
                <span class="rs-home__meta">
                  <span :class="['rs-badge', `rs-badge--${row.badge.tone}`]">{{ row.badge.label }}</span>
                  <span v-if="row.step" class="rs-home__step">{{ row.step }}</span>
                  <span class="rs-home__time">{{ row.day }}</span>
                </span>
              </NuxtLink>
            </li>
          </ul>
        </section>

        <div v-if="nextCursor" class="rs-home__more">
          <p v-if="moreError" class="rs-home__problem" role="alert">{{ moreError }}</p>
          <button type="button" class="rs-btn rs-btn--ghost" :disabled="loadingMore" @click="loadMore">
            {{ loadingMore ? "불러오는 중…" : "더 보기" }}
          </button>
        </div>
      </template>

      <!-- 예시 연구 — 미리 돌린 실제 기록, 읽기 전용(쓰기 API 409). 실행 시각·코퍼스 범위를 함께 보인다(시연 정직성 규칙) -->
      <section v-if="examples.length" class="rs-home__block" aria-labelledby="rs-home-examples">
        <h2 id="rs-home-examples" class="rs-home__heading">예시 연구</h2>
        <p class="rs-muted">미리 돌려 둔 실제 연구입니다. 둘러볼 수 있고 바꿀 수는 없습니다.</p>
        <ul class="rs-home__examples">
          <li v-for="ex in examples" :key="ex.id" class="rs-card rs-home__example">
            <div class="rs-home__example-head">
              <span class="rs-badge">읽기 전용</span>
              <span class="rs-home__step">{{ stepLine(ex.phase) }}</span>
            </div>
            <NuxtLink :to="exampleRoute(ex)" class="rs-home__example-q">{{ ex.question }}</NuxtLink>
            <p v-if="exampleMetas[ex.id]?.ranAt" class="rs-muted">{{ exampleMetas[ex.id]?.ranAt }}</p>
            <p v-if="exampleMetas[ex.id]?.scope" class="rs-muted">{{ exampleMetas[ex.id]?.scope }}</p>
          </li>
        </ul>
      </section>
    </main>

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useResearchStarter } from "~/composables/useResearch";
import { useWorkApi } from "~/composables/useResearchWork";
import { useResearchWorksApi } from "~/composables/useResearchWorks";
import type { ResearchEntry } from "~/types/history";
import { routeFor, type HistoryRoute } from "~/utils/historyRoute";
import { activeResearchId, researchErrorMessage } from "~/utils/researchErrors";
import { exampleMeta, exampleRoute, homeGroups, type WorkListItem } from "~/utils/researchHome";
import { QUESTION_MAX, questionProblem } from "~/utils/researchInput";
import { researchBadge, researchRowLine } from "~/utils/sidebarResearch";
import { stepLine } from "~/utils/workPhase";

useHead({ title: "딥리서치 — 연구" });

const worksApi = useResearchWorksApi();
const workApi = useWorkApi();
const { startResearch } = useResearchStarter();

// ── 새 연구 시작 ──────────────────────────────────────────
const question = ref("");
const starting = ref(false);
const startError = ref("");
// 같은 브라우저의 다른 딥리서치에 막혔으면(429 browser_active) 그 연구 id — [id].vue 의 안내와 같은 링크를 단다.
// 지금 서버는 만들기에서 이 429 를 내지 않고 승인·재시도에서 낸다(api/research.py _to_run_queue) — 바뀌어도 같은 안내가 서게 둔다
const activeJobId = ref<string | null>(null);
const problem = computed(() => questionProblem(question.value));

async function start(): Promise<void> {
  const q = question.value.trim();
  if (starting.value || questionProblem(q)) return;
  starting.value = true;
  startError.value = "";
  activeJobId.value = null;
  try {
    const jobId = await startResearch(q);
    await navigateTo(`/research/${jobId}`);
  } catch (e) {
    // 입력은 지우지 않는다 — 고쳐서 다시 보낼 수 있어야 한다
    startError.value = researchErrorMessage(e, "새 연구를 시작하지 못했습니다");
    activeJobId.value = activeResearchId(e);
  } finally {
    starting.value = false;
  }
}

// 한글 조합 중의 엔터는 글자 확정용이다 — 여기서 보내면 마지막 글자가 빠지거나 두 번 간다(SearchPlusMenu 와 같은 규칙)
function onEnter(e: KeyboardEvent): void {
  e.preventDefault();
  if (e.isComposing) return;
  void start();
}

// ── 진행 중·내 연구 ───────────────────────────────────────
// 이 브라우저의 딥리서치 기록을 50건씩 읽는다([더 보기] = before 커서). 사이드바(30건)와 따로 둔다
const entries = ref<ResearchEntry[]>([]);
const nextCursor = ref<string | null>(null);
const listState = ref<"loading" | "ready" | "error">("loading");
const loadingMore = ref(false);
const moreError = ref("");

interface HomeRow {
  id: string;
  title: string;
  to: HistoryRoute;
  badge: { label: string; tone: string };
  step: string | null;
  day: string;
}

function rowOf(e: ResearchEntry): HomeRow {
  const at = new Date(e.updatedAt ?? e.createdAt);
  return {
    id: e.id,
    title: e.title,
    to: routeFor(e),
    badge: researchBadge(e.research),
    step: researchRowLine(e.research),
    day: Number.isNaN(at.getTime()) ? "" : at.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" }),
  };
}

const blocks = computed(() => {
  const { live, mine } = homeGroups(entries.value);
  return [
    { id: "live", title: "진행 중", rows: live.map(rowOf) },
    { id: "mine", title: "내 연구", rows: mine.map(rowOf) },
  ].filter((b) => b.rows.length > 0);
});

async function loadFirst(): Promise<void> {
  listState.value = "loading";
  try {
    const page = await worksApi.listResearch();
    entries.value = page.entries;
    nextCursor.value = page.nextCursor;
    listState.value = "ready";
  } catch (e) {
    console.warn("[research] 연구 기록을 읽지 못했다", e);
    listState.value = "error";
  }
}

async function loadMore(): Promise<void> {
  if (!nextCursor.value || loadingMore.value) return;
  loadingMore.value = true;
  moreError.value = "";
  try {
    const page = await worksApi.listResearch(nextCursor.value);
    // 읽는 사이 새 기록이 생기면 쪽 경계가 밀려 같은 기록이 다시 올 수 있다 — 한 번만 둔다
    const seen = new Set(entries.value.map((e) => e.id));
    entries.value = [...entries.value, ...page.entries.filter((e) => !seen.has(e.id))];
    nextCursor.value = page.nextCursor;
  } catch (e) {
    console.warn("[research] 다음 쪽을 읽지 못했다", e);
    moreError.value = "더 불러오지 못했습니다. 잠시 뒤 다시 눌러 보세요.";
  } finally {
    loadingMore.value = false;
  }
}

// ── 예시 연구 ─────────────────────────────────────────────
// 목록은 {id, question, phase, created_at} 만 준다 — 실행 시각·범위는 예시마다 GET work 의 corpus 에서 읽는다.
// 목록을 못 읽으면 섹션을 그리지 않고, 범위를 못 읽은 카드는 그 줄만 뺀다
const examples = ref<WorkListItem[]>([]);
const exampleMetas = ref<Record<string, ReturnType<typeof exampleMeta>>>({});

async function loadExamples(): Promise<void> {
  try {
    examples.value = (await worksApi.listWorks(true)).items;
  } catch (e) {
    console.warn("[research] 예시 연구를 읽지 못했다", e);
    return;
  }
  await Promise.all(
    examples.value.map(async (ex) => {
      try {
        const work = await workApi.getWork(ex.id);
        exampleMetas.value = { ...exampleMetas.value, [ex.id]: exampleMeta(work.corpus) };
      } catch (e) {
        console.warn("[research] 예시 연구의 범위를 읽지 못했다", e);
      }
    }),
  );
}

// 기록·예시 API 는 브라우저 ID 헤더가 있어야 한다 — 서버 렌더가 아니라 마운트 뒤에 읽는다
onMounted(() => {
  void loadFirst();
  void loadExamples();
});

// ── 토스트 ────────────────────────────────────────────────
const toast = ref("");
let toastTimer: ReturnType<typeof setTimeout> | null = null;

function showToast(msg: string): void {
  toast.value = msg;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = "";
  }, 2400);
}
</script>
```

- [ ] **Step 7: 스타일**

`frontend/assets/css/research.css` — 인쇄 앵커 한 줄을 old 로 잡는다(Task N4 의 `.rs-deeper` 블록 뒤에 선다). old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── /research 홈 ──────────────────────────────────────── */
.rs-home {
  max-width: 52rem;
  margin: 0 auto;
}
.rs-home__head {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.rs-home__title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 700;
  line-height: 1.4;
}
.rs-home__field {
  display: block;
}
.rs-home__input {
  width: 100%;
  min-height: 4.5rem;
  padding: 0.6rem 0.7rem;
  font-family: inherit;
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--skx-ink);
  resize: vertical;
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-sm);
}
.rs-home__input:focus {
  outline: none;
  border-color: var(--skx-primary);
}
.rs-home__new-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.6rem;
}
.rs-home__problem {
  flex: 1 1 12rem;
  margin: 0;
  font-size: 0.6rem;
  color: var(--skx-ink);
}
.rs-home__problem a {
  font-weight: 700;
  color: var(--skx-primary);
}
.rs-home__block {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.rs-home__heading {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 700;
}
.rs-home__list {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  overflow: hidden;
  list-style: none;
  background: var(--skx-white);
  border-radius: var(--skx-radius-lg);
  box-shadow: var(--skx-shadow-lnb);
}
.rs-home__row + .rs-home__row {
  border-top: 1px solid var(--skx-border-c1);
}
.rs-home__link {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.7rem 1rem;
  color: inherit;
  text-decoration: none;
}
.rs-home__link:hover .rs-home__q,
.rs-home__link:focus-visible .rs-home__q {
  color: var(--skx-primary);
  text-decoration: underline;
}
.rs-home__link:focus-visible {
  outline: 2px solid var(--skx-border-c2);
  outline-offset: -2px;
}
.rs-home__q {
  font-size: 0.7rem;
  font-weight: 600;
  line-height: 1.5;
  word-break: keep-all;
}
.rs-home__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}
.rs-home__step {
  font-size: 0.6rem;
  font-weight: 600;
  color: var(--skx-primary);
}
.rs-home__time {
  font-size: 0.6rem;
  color: var(--skx-gray-2);
}
/* 배지 — 공용 .rs-badge 에는 running·done·failed 모양만 있다. researchBadge 의 나머지 tone 도 사이드바처럼 서로 구분해 보인다 */
.rs-home .rs-badge--waiting {
  color: var(--skx-primary);
  background: var(--skx-border-c1);
  border-color: var(--skx-border-c1);
}
.rs-home .rs-badge--canceled,
.rs-home .rs-badge--unknown {
  color: var(--skx-gray-2);
}
.rs-home__more {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}
.rs-home__examples {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
  gap: 0.8rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.rs-home__example {
  gap: 0.4rem;
}
.rs-home__example-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}
.rs-home__example-q {
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1.5;
  color: var(--skx-ink);
  text-decoration: none;
  word-break: keep-all;
}
.rs-home__example-q:hover,
.rs-home__example-q:focus-visible {
  color: var(--skx-primary);
  text-decoration: underline;
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 8: 전체 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff -- frontend/assets/css/research.css | grep '^+' | grep -cE "#[0-9a-fA-F]{3,6}\b|rgba?\("
```

Expected: vitest 실패 0, `Test Files` 는 Task N4 뒤 + 1, `Tests` 는 Task N4 뒤 수 + 4 · `0` · `0` · `└  ✨ Build complete!` · `0`(새 색값 없음).

확인(선택 — 운영에 쓰지 않는다): Task Z1 Step 3 의 미리보기(`NUXT_DEV_API_TARGET=https://skovix.landsoft.co.kr/api npx nuxi dev --port 3016`)로 `http://localhost:3016/research` 를 GET 으로만 연다 — 기록이 없는 브라우저면 '연구 기록이 없습니다. …', 예시가 지정돼 있지 않으면 예시 섹션 없음, 콘솔 오류 없음. **[계획 세우기] 는 누르지 않는다**(운영에 잡을 만든다).

- [ ] **Step 9: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchHome.ts frontend/tests/unit/researchHome.test.ts frontend/composables/useResearchWorks.ts "frontend/pages/research/index.vue" frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — /research 홈을 만든다(D26). 새 연구 시작(질문 → 계획 세우기 → 연구 화면), 진행 중(잡이 돌거나 승인을 기다리거나 이어간 연구의 생성이 도는 연구)·내 연구(이 브라우저의 딥리서치 기록을 50건씩, [더 보기] 는 before 커서 — 사이드바 30건 상태와 따로 읽는다), 예시 연구(GET /api/research-works?example=1 — 읽기 전용 배지, 예시마다 GET work 의 corpus 로 실행 시각(KST)·코퍼스 범위를 보인다, 예시가 없으면 섹션 없음). 줄의 배지·단계 글은 사이드바와 같은 함수를 쓴다. 사이드바의 '모두 보기 (N)' 가 이곳으로 온다"
```

Expected: `A` 넷(`researchHome.ts`·`researchHome.test.ts`·`useResearchWorks.ts`·`pages/research/index.vue`)·`M  frontend/assets/css/research.css`, 커밋 1개.

---

### Task N6: 빠른검색 [담기 ▾] — 자르는 순서 1

spec §12-3 '빠른검색(D17)' 둘째 줄 — 결과 카드 [담기 ▾]: 이어간 연구를 고른다(`GET /api/research-works`), `PUT …/reading/{cnts_id}` 가 소장 논문을 origin `user` 로 넣는다(`app/api/research_reading.py:79-116`), 이어간 연구가 없으면 D17 문구, 백엔드는 이미 있다. D17. 정함 17.

**알아 둘 것:**
- **담기 본문(정함 17):** `{"state": "in"}`(담음). '담기'는 그 연구의 목록에 넣는 것이다 — 후보(`candidate`)로 넣으면 사용자가 그 연구에서 다시 담아야 한다. 행이 없으면 서버가 origin `user`(자기점검이 뺀 논문이면 `revived`)로 만들고 상태를 `in` 으로 둔다(`put_reading` — 보낸 필드만 바꾼다). 이미 있는 논문이면 상태만 `in` 으로 바뀐다. 404 는 서버 문구 `논문이 없습니다`, 예시 연구는 409 — `workErrorMessage(err, "담지 못했습니다")`(`utils/researchErrors.ts:96` — 06e 파일, 읽기만)가 404 의 서버 문구를 그대로 보인다.
- **고르는 목록:** `GET /api/research-works`(example 아님) = 이 브라우저가 이어간 연구 중 기록에 남은 것(`app/api/research_work.py:300-322`, 상한 50). 다른 브라우저 이어가기 목록은 대회 뒤(06b 이월 §7-1). 목록은 **한 화면에서 한 번만** 읽는다(메뉴를 처음 열 때 — 결과 카드 20~100장이 `useAddToWork()` 한 벌을 나눠 쓴다). 못 읽으면 `null` 로 두어 메뉴가 실패 문구를 보이고 다시 열면 다시 읽는다. 비었으면 D17 문구 `보고서 끝 [이 연구 이어가기] 뒤에 담을 수 있습니다`(글자 그대로).
- **담은 뒤:** 토스트 `「질문(24자)」 연구에 담았습니다`. 그리고 사이드바 기록을 한 번 다시 읽는다(`void useHistory().refresh("research")`) — 사이드바는 진행 중 연구·생성이 있을 때만 30초 폴링하므로(`AppSidebar.vue:236-247`) 끝난 연구에 담으면 Task N3 의 '… · n편 담음' 이 다음 이동까지 그대로다. PUT reading 이 progress 를 다시 센다(`research_reading.py:119`). `refresh` 의 실패는 `historyState.refresh` 가 안에서 삼키므로(`historyState.ts:105-106`) 기다리지 않는다(`useResearchWork.ts` 의 사이드바 다시 읽기 선례).
- **자리(파트 N 끝 '파트 메모' 2):** 카드 오른쪽 칸은 `width: 8.4rem`(`style_skovix.css:3787-3795`)이고 버튼 줄(`.skx-paper-item__btn-row`)에는 '원문 보기'(flex 1)와 인용 버튼(2.05rem)이 이미 있어 세 번째 버튼이 들어가지 않는다. 그래서 버튼 줄 **아래**·DeepRead 버튼 **위**에 한 줄을 다 쓰는 [담기 ▾] 를 둔다(버튼 줄의 두 버튼은 그대로). 카드(`<article class="skx-paper-item">`)에는 클릭 처리기가 없어(제목 `h3` 에만 있다) 메뉴 클릭이 상세로 가지 않는다.
- **메뉴 부품:** `components/research/AddToWorkMenu.vue` — `ReportDownloadMenu.vue` 의 키보드 관례 그대로(`aria-haspopup="menu"`·`aria-expanded`·`aria-controls`, 방향키·Home·End 는 `menuStep`(`utils/menuNav.ts`), Tab 은 닫고 다음 요소로, Esc 는 묶음 전체에서 듣고 버튼으로 초점 복귀, 바깥 클릭으로 닫힘). 카드마다 메뉴가 있으므로 바깥 클릭 리스너는 **열려 있는 동안만** 건다. 목록을 읽는 동안 연 메뉴는 항목이 늦게 서므로 초점이 아직 버튼에 있으면 그때 첫 항목으로 옮긴다. 담는 동안(`busy`)은 어느 카드의 메뉴도 열리지 않는다(한 번에 하나만 담는다). 메뉴의 움직임은 기존 `rs-dl-in`(research.css :1207 — 내려받기 메뉴)을 다시 쓰고 `prefers-reduced-motion` 에서 멈춘다 — 새 `@keyframes` 없음.
- **쓰는 요청은 클릭 처리기에서만:** 목록 GET 은 메뉴를 열 때(`@open`), PUT 은 항목을 고를 때(`@pick`)만 — 화면을 그리는 경로·computed·watch 에서 부르지 않는다.
- `pages/papers/index.vue` 는 Task N4 가 먼저 고쳤다 — 아래 자리는 모두 앵커 글자로 잡는다. `:564-569`(BookChat — 06e)는 건드리지 않는다. `research.css` 블록은 인쇄 앵커 바로 위 — Task N5 의 `.rs-home*` 블록 뒤에 선다.
- **자르는 순서 1(spec §12-6):** 뒤처지면 이 Task 를 가장 먼저 하지 않는다.

**Files:**
- Create: `frontend/utils/addToWork.ts`
- Create: `frontend/components/research/AddToWorkMenu.vue`
- Modify: `frontend/composables/useResearchWorks.ts`(Task N5 뒤 — import·`useAddToWork` 더함)
- Modify: `frontend/pages/papers/index.vue`(Task N4 뒤 — 결과 카드 버튼 줄 아래, script import 셋, `showToast` 뒤)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위 `.rs-basket*`)
- Test: `frontend/tests/unit/addToWork.test.ts`(새 파일)

기준선(Task N5 뒤): 전체 Task N4 뒤 + 4.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

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

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/addToWork.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  no tests` — 수집에서 `Error: Cannot find module '~/utils/addToWork' imported from '…/frontend/tests/unit/addToWork.test.ts'`.

- [ ] **Step 3: 구현한다 — 순수 함수**

`frontend/utils/addToWork.ts` (새 파일, 전체):

```ts
// frontend/utils/addToWork.ts
// 빠른검색 결과 카드의 [담기 ▾](D17) — 이 브라우저의 이어간 연구를 골라 그 연구의 읽기 목록에 담는다
import type { WorkListItem } from "~/utils/researchHome";

// 이어간 연구가 없을 때(D17 글자 그대로) — 새 딥리서치는 답 끝 [딥리서치로 더 깊게] 로만 시작한다
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

(`clip` 은 내보내지 않는다 — `utils/paperResearch.ts` 의 같은 이름 함수도 비공개라 Nuxt 자동 import 가 겹치지 않는다.)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/addToWork.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  4 passed (4)`

- [ ] **Step 5: 구현한다 — 목록·담기 상태 `useAddToWork`**

`frontend/composables/useResearchWorks.ts`(Task N5 뒤) — import 묶음. old:

```ts
import type { ResearchEntry } from "~/types/history";
import { createServerStore, type HistoryFetcher } from "~/utils/historyStore";
import { HOME_PAGE_SIZE, type ResearchPage, type WorkListOut } from "~/utils/researchHome";
import { useApi } from "./useApi";
```

new:

```ts
import { ref } from "vue";
import type { ResearchEntry } from "~/types/history";
import { ADD_TO_WORK_BODY, addedLine } from "~/utils/addToWork";
import { createServerStore, type HistoryFetcher } from "~/utils/historyStore";
import { HOME_PAGE_SIZE, type ResearchPage, type WorkListItem, type WorkListOut } from "~/utils/researchHome";
import { useApi } from "./useApi";
import { useHistory } from "./useHistory";
import { useWorkApi } from "./useResearchWork";
```

파일 끝 — `useResearchWorksApi` 의 닫는 줄. old:

```ts
        total: res.total ?? null,
      };
    },
  };
}
```

new:

```ts
        total: res.total ?? null,
      };
    },
  };
}

// 빠른검색 결과 카드의 [담기 ▾](D17) — 한 화면(검색 결과)의 모든 카드가 이 한 벌을 나눠 쓴다
export function useAddToWork() {
  const { listWorks } = useResearchWorksApi();
  const workApi = useWorkApi();
  const history = useHistory();
  const works = ref<WorkListItem[] | null>(null);
  const loading = ref(false);
  const busy = ref(false);

  // 메뉴를 처음 열 때 이 브라우저의 이어간 연구를 한 번만 읽는다(이미 읽었으면 그대로). 못 읽으면 null 로 두어
  // 메뉴가 실패 문구를 보이고, 다시 열면 다시 읽는다
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
    // 사이드바는 진행 중 연구·생성이 있을 때만 폴링한다 — 끝난 연구에 담아도 그 줄의 'n편 담음' 이 바로 맞게 한 번
    // 다시 읽는다. 실패는 refresh 가 안에서 삼킨다(historyState) — 기다리지 않는다(useResearchWork 의 afterAction 선례)
    void history.refresh("research");
    const item = works.value?.find((w) => w.id === jobId);
    return item ? addedLine(item) : "연구에 담았습니다";
  }

  return { works, loading, busy, load, add };
}
```

(`useResearchWork.ts`·`researchErrors.ts` 는 06e 파일 — 읽기만 한다. `putReading(jobId, cnts, body: ReadingPut)` 은 `useResearchWork.ts:67-68`.)

- [ ] **Step 6: 구현한다 — 메뉴 부품**

`frontend/components/research/AddToWorkMenu.vue` (새 파일, 전체):

```vue
<!-- frontend/components/research/AddToWorkMenu.vue -->
<!-- 빠른검색 결과 카드의 [담기 ▾](D17) — 이 브라우저의 이어간 연구를 골라 그 연구의 목록에 담는다.
     목록 읽기·담기는 부모(useAddToWork)가 한다 — 여기서는 메뉴만 연다(ReportDownloadMenu 와 같은 키보드 관례) -->
<template>
  <div ref="root" class="rs-basket" :data-cnts-id="cntsId" @keydown="onRootKeydown">
    <!-- 담는 동안(busy)은 모든 카드의 메뉴가 열리지 않는다 — 한 번에 하나만 담는다. 글은 바꾸지 않는다(다른 카드까지
         '담는 중'으로 읽히지 않게) -->
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
import type { WorkListItem } from "~/utils/researchHome";

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

// 카드마다 메뉴가 하나씩 있다(한 쪽에 20~100장) — 바깥 클릭은 열려 있는 동안만 듣는다
watch(open, (value) => {
  if (value) document.addEventListener("click", onDocumentClick);
  else document.removeEventListener("click", onDocumentClick);
});
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));
</script>
```

- [ ] **Step 7: 결과 카드에 단다**

`frontend/pages/papers/index.vue` — 결과 카드의 인용 버튼 끝·버튼 줄 닫기·DeepRead 버튼 시작(da80f23 :449-454). 같은 인용 아이콘 줄이 AI 답 칸(:141)에도 있지만 들여쓰기가 다르고 `skx-btn-ptalk` 는 파일에 하나라 아래 여섯 줄 묶음은 하나다. old:

```vue
                      <img src="/img/ico-paper-bookmark.svg" alt="" />
                    </button>
                  </div>
                  <button
                    type="button"
                    class="skx-btn-ptalk"
```

new:

```vue
                      <img src="/img/ico-paper-bookmark.svg" alt="" />
                    </button>
                  </div>
                  <!-- 이어간 연구에 담기(D17) — 버튼 줄(8.4rem)에는 세 번째 버튼이 들어가지 않아 한 줄을 따로 쓴다 -->
                  <AddToWorkMenu
                    :cnts-id="paper.book_id"
                    :works="addToWork.works.value"
                    :loading="addToWork.loading.value"
                    :busy="addToWork.busy.value"
                    @open="addToWork.load()"
                    @pick="onAddToWork($event, paper.book_id)"
                  />
                  <button
                    type="button"
                    class="skx-btn-ptalk"
```

(`addToWork` 는 ref 를 담은 보통 객체라 템플릿이 풀어 주지 않는다 — `.value` 로 넘긴다.)

script import — `marked` 줄 뒤(da80f23 :582). old:

```ts
import { marked } from "marked";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
```

new:

```ts
import { marked } from "marked";
import AddToWorkMenu from "~/components/research/AddToWorkMenu.vue";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
import { useAddToWork } from "~/composables/useResearchWorks";
```

`paperResearch` import(Task N4 가 고친 줄) 뒤 — old:

```ts
import { deeperResearchUrl, readResearchDraft } from "~/utils/paperResearch";
```

new:

```ts
import { deeperResearchUrl, readResearchDraft } from "~/utils/paperResearch";
import { workErrorMessage } from "~/utils/researchErrors";
```

`showToast` 뒤·계산 묶음 앞(da80f23 :676-677). old:

```ts
// ── 계산 ─────────────────────────────────────────────────────
const hasResults = computed(() => paperResult.value !== null || loading.value);
```

new:

```ts
// ── 이어간 연구에 담기(D17) ─────────────────────────────────
// 메뉴를 처음 열 때 이 브라우저의 이어간 연구를 한 번 읽는다(모든 카드가 나눠 쓴다). 담은 결과는 토스트로 알린다
const addToWork = useAddToWork();

async function onAddToWork(jobId: string, cntsId: string): Promise<void> {
  try {
    showToast(await addToWork.add(jobId, cntsId));
  } catch (e) {
    showToast(workErrorMessage(e, "담지 못했습니다"));
  }
}

// ── 계산 ─────────────────────────────────────────────────────
const hasResults = computed(() => paperResult.value !== null || loading.value);
```

- [ ] **Step 8: 스타일**

`frontend/assets/css/research.css` — 인쇄 앵커 한 줄을 old 로 잡는다(Task N5 의 `.rs-home*` 블록 뒤에 선다). old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 빠른검색 결과 카드 [담기 ▾] ──────────────────────────── */
/* 카드 오른쪽 칸(8.4rem)의 버튼 줄에는 세 번째 버튼이 들어가지 않는다 — 버튼 줄 아래·DeepRead 위에 한 줄을 다 쓴다 */
.rs-basket {
  position: relative;
  display: flex;
}
.rs-basket__btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
  font-family: inherit;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--skx-primary);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.rs-basket__btn:hover,
.rs-basket__btn[aria-expanded="true"] {
  border-color: var(--skx-border-c2);
}
.rs-basket__btn[aria-busy="true"] {
  cursor: progress;
}
.rs-basket__menu {
  position: absolute;
  top: calc(100% + 0.3rem);
  right: 0;
  z-index: 40;
  width: 16rem;
  max-width: 80vw;
  padding: 0.3rem;
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-banner);
  transform-origin: top right;
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
  background: var(--skx-border-c1);
  outline: none;
}
@media (prefers-reduced-motion: reduce) {
  .rs-basket__menu {
    animation: none;
  }
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

- [ ] **Step 9: 전체 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff -- frontend/pages/papers/index.vue | grep -cE "BookChat|doc-kind"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff -- frontend/assets/css/research.css frontend/components/research/AddToWorkMenu.vue | grep '^+' | grep -cE "#[0-9a-fA-F]{3,6}\b|rgba?\(|@keyframes"
```

Expected: vitest 실패 0, `Test Files` 는 Task N5 뒤 + 1, `Tests` 는 Task N5 뒤 수 + 4 · `0` · `0` · `└  ✨ Build complete!` · `0` · `0`(새 색값·새 keyframes 없음 — 새 파일 `AddToWorkMenu.vue` 는 `git diff` 에 안 나오므로 `grep -cE "#[0-9a-fA-F]{3,6}\b|rgba?\(" frontend/components/research/AddToWorkMenu.vue` 로도 `0` 을 본다).

확인(손 — Task Z6 Step 5 에 이미 있다): 결과 카드의 [담기 ▾] → 이어간 연구가 목록에 나온다 → 고르면 `「…」 연구에 담았습니다` 토스트 → 그 연구의 `?s=reading` 에 그 논문이 담음으로 들어와 있다(들어온 경로 '사용자'), 사이드바 그 연구 줄의 'n편 담음' 이 새로고침 없이 는다. 이어간 연구가 없는 새 시크릿 창에서는 D17 문구. 키보드 — 버튼에서 ↓ 로 열고 ↑↓ 로 옮기고 Esc 로 닫으면 초점이 버튼으로 돌아온다. **이 확인은 운영 배포 뒤 사용자가 한다** — 구현 중 미리보기에서 담기를 누르지 않는다(운영 DB 에 쓴다).

- [ ] **Step 10: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/addToWork.ts frontend/tests/unit/addToWork.test.ts frontend/components/research/AddToWorkMenu.vue frontend/composables/useResearchWorks.ts frontend/pages/papers/index.vue frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 논문 빠른검색 결과 카드에 [담기 ▾] 를 단다(D17). 메뉴를 처음 열 때 이 브라우저의 이어간 연구를 한 번 읽어 모든 카드가 나눠 쓰고, 고르면 PUT reading {state: in} 으로 그 연구의 목록에 담는다(행이 없으면 서버가 origin user 로 만든다). 이어간 연구가 없으면 '보고서 끝 [이 연구 이어가기] 뒤에 담을 수 있습니다'. 담은 뒤 토스트와 함께 사이드바 기록을 한 번 다시 읽어 그 연구 줄의 'n편 담음' 이 바로 맞는다. 카드 오른쪽 칸 폭 때문에 버튼 줄 아래에 한 줄로 두고, 메뉴는 내려받기 메뉴와 같은 키보드 관례(방향키·Esc·바깥 클릭·초점 복귀)다"
```

Expected: `A` 셋(`addToWork.ts`·`addToWork.test.ts`·`AddToWorkMenu.vue`)·`M` 셋(`useResearchWorks.ts`·`pages/papers/index.vue`·`research.css`), 커밋 1개.

---

### Task N9: 탐색 방식 — 폭넓게 · 정밀하게

spec D28(06c 판정 뒤 2026-10-12 사용자 결정 — 사용자 "응 넣자. 정확하게로 가자. 탐색 방식: 폭넓게 · 정밀하게 로 가자")·§12-3 입구 '탐색 방식' 줄("자리·모양은 06d 계획이 정한다"). 정함 19. **실행 순서: Task N6 뒤**(N5·N6 을 잘랐으면 Task N7 뒤) · Task L6·N8 앞 — 파트 N 의 번호를 다시 매기지 않으려고 N9 로 두고 N6 바로 뒤에 적었다. N5 를 자른 경로에서 N7 뒤로 미루는 까닭: N7 은 일부 커밋한 N5 를 `git revert` 로 되돌리는데, 그 전에 이 Task 가 인쇄 앵커 위(`.rs-home*` 블록 바로 뒤)에 블록을 넣으면 되돌리기가 이웃 줄에서 부딪힌다.

이 Task 는 06c 배포 기록 브랜치(`docs/round06c-deploy-record`)에서 계획에 더했다 — 06d worktree 의 계획서에 이 Task 가 없으면(그 브랜치가 dev 에 머지되기 전에 땄다) `git -C C:/Users/LANDSOFT/mygit/NL_library_AI show dev:docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md` 의 계획서를 정본으로 읽는다.

**알아 둘 것:**
- **선택지(정함 19):** 라벨 `탐색 방식`, 칸 `폭넓게`(잡 params `{broaden: 0, query_context: 0}` — 지금 방식, 많이 찾지만 엉뚱한 논문이 섞일 수 있다) · `정밀하게`(`{broaden: 1, query_context: 1}` — 넓히기가 뽑은 범위 용어를 검색어에 붙여 엉뚱한 논문을 줄인다, 관련 논문 몇 편을 놓칠 수 있다), **기본 선택 `정밀하게`**. 근거는 06c 두 갈래 판정(06c 완료노트 §5-4 — 둘 다 켠 갈래: 보고서 정밀도 68.7% → 77.6%·무관 31 → 19, 관련 68 → 66·insufficient 16 → 23·대조군 미달)과 그 뒤 사용자 결정이다. 칸의 설명 문구는 `RESEARCH_MODES[].hint` 한 곳에 둔다.
- **화면이 늘 두 칸을 함께 싣는다:** 서버 `DEFAULT_PARAMS` 는 `broaden` 0·`query_context` 0 그대로다(`app/services/research/state.py:36`·`:39`, 기본값 커밋 없음 — 06c 완료노트 §5-5). 그래서 정밀하게는 화면이 실어야만 켜지고, 폭넓게도 `{broaden: 0, query_context: 0}` 를 실어 서버 기본값이 나중에 바뀌어도 고른 방식 그대로 돈다. `query_context` 만 1 이면 범위 용어(`broaden` 1 의 계획 단계가 뽑는다)가 비어 '국내 학술논문에서' 떼기만 한다(06c 계획 정함 20) — 두 칸을 따로 고르게 하지 않는다.
- **백엔드는 그대로다:** `POST /api/research` 가 본문 `{question, params}` 를 받고(`app/api/research.py:89-91` `ResearchCreate.params: dict`) `merge_params` 가 모르는 키·타입·범위를 거부해 422 를 낸다(`:234-237`, `state.py:56-57`(`broaden`·`query_context` 정수 0~1)·`:61-66`). 만든 잡은 기본값을 채운 params 를 저장하고(`research.py:235`·`:241`) `GET /api/research/{id}` 가 그대로 돌려준다(`:493` `"params": job.params`). 화면의 `useResearchApi().create(question, params = {})`(`composables/useResearch.ts:38-39`)도 이미 params 를 싣는다 — 바꾸는 것은 `useResearchStarter().startResearch` 가 params 를 넘겨받는 것뿐이다. `types/research.ts` 의 `ResearchParams`(`Record<string, number>`)·`ResearchJob.params?` 는 그대로 쓴다.
- **06c fastapi 가 운영에 있어야 한다:** 06c 전 fastapi 의 `merge_params` 는 `broaden` 을 모르는 키로 거부한다(422 `알 수 없는 파라미터: broaden`) — 06d nuxt 가 06c 전 fastapi 와 만나면 딥리서치 시작이 모두 막힌다. 06c 워커·fastapi 는 2026-10-12 운영에 나갔다(06c 완료노트 §5). Task Z5 Step 1 의 서버 확인이 `None None` 이면 멈추고, 롤백으로 fastapi 를 06c 전 이미지로 되돌릴 때는 nuxt 도 함께 되돌린다.
- **자리:** `SearchPlusMenu.vue` 는 랜딩 두 곳(`pages/index.vue:166` 논문 패널·`pages/papers/index.vue:15`)과 결과 검색바(`pages/papers/index.vue:46`)가 같이 쓰는 부품이다 — 딥리서치 칩이 켜지면(`active?.id === "deep-research"` — + 메뉴·슬래시 명령·`activateMode` 모두) 칩 바로 뒤에 두 칸 선택이 서고, 칩을 끄면(×) 함께 사라진다. 상세의 [이 논문으로 딥리서치]와 [딥리서치로 더 깊게](Task N4)는 `?draft=` → `fillResearchDraft` → `activateMode` 로 칩을 켜므로 같은 자리에 선다(따로 고칠 것 없음). `/research` 홈(Task N5)의 새 연구에도 같은 부품을 둔다(Step 8 — N5 를 잘랐으면 건너뛴다). [같은 질문으로 다시 시작]은 고르는 칸 없이 원래 잡의 방식을 잇는다(Step 9).
- **부품 `ResearchModePicker.vue`(radiogroup):** `role="radiogroup"` — 이름은 보이는 라벨 '탐색 방식'(`aria-labelledby`), 설명은 고른 칸의 hint(`aria-describedby`). 칸은 `<button role="radio" :aria-checked>` 이고 고른 칸만 `tabindex="0"`(roving — Tab 한 번에 묶음을 지난다). ←→↑↓ 는 옆 칸을 고르고 그 칸으로 초점을 옮기며(선택이 초점을 따른다 — WAI-ARIA radio group 관례, 끝에서 돈다) Home·End 는 처음·끝이다. Space·Enter 는 button 의 기본 클릭으로 고른다. 키 판단은 순수 함수 `modeStep`(기존 `utils/menuNav.ts` 의 `menuStep` 을 쓴다). 부품은 v-model 만 주고받고, 기억과 잡 params 싣기는 부르는 쪽이 한다.
- **키가 SearchPlusMenu 의 가로채기에 걸리지 않는다:** 부모 상자의 캡처 리스너 `onHostKeydown`(`SearchPlusMenu.vue:360-371`)은 `e.target === field`(입력창)일 때만 키를 쓰고 `onHostClick`(`:373-379`)은 `.skx-send` 만 본다 — 칸의 키·클릭은 부품까지 그대로 간다. 방향키는 부품이 `preventDefault` 해 페이지가 구르지 않는다. 페이지의 엔터 검색(`@keydown.enter`)은 입력창에만 달려 있어 칸 위의 엔터와 섞이지 않는다.
- **기억(사용자 편의일 뿐):** localStorage `skx_research_mode`(`"broad"`·`"precise"`). `readResearchMode`·`saveResearchMode` 가 try/catch 로 감싸고, 저장소가 없거나(`safeLocalStorage()` 가 null — 서버 렌더·막힌 저장소) 던지거나 모르는 값이면 기본 '정밀하게' 다. 서버 렌더와 첫 그림이 같게 기본으로 시작하고 `onMounted` 에서 읽는다. round04c 가 지운 레이아웃 기억(`skx_research_layout`, `2e3d87a`)과 다른 키다 — Task D1 의 '배치 기억 없음' 을 되살리는 것이 아니다.
- **다시 시작(`[id].vue` 의 `onRestart`):** `restartParams(view.params)` — 원래 잡의 두 칸을 그대로(1 이면 1, 아니면 0) 싣는다. 두 칸이 모두 없는 잡(06c 전 잡)은 기본 '정밀하게'. 다른 칸(`max_recheck` 등)은 지금처럼 싣지 않는다(서버 기본값).
- **머리 표시:** `researchModeLine(view.params)` — 두 칸이 모두 1 이면 `탐색 방식 · 정밀하게`, 모두 0 이면 `탐색 방식 · 폭넓게`(06c 배포 뒤·06d 전에 만든 잡, 선택을 거치지 않고 만든 잡 — 판정 도구의 기본 갈래 등), 두 칸이 모두 없으면(06c 전 잡·params 를 싣지 않은 응답 — `initialResearchView` 의 `params: job.params ?? {}`, `utils/researchEvents.ts:247`) 그리지 않는다. 두 칸이 갈리면(판정 도구로 나눠 돌린 잡 같은 경우) 어느 방식도 아니라 그리지 않는다. 자리는 상태 배지 옆 — `ResearchHeader.vue` 의 상태 배지(`:7`)를 `.rs-head__meta` 한 줄로 묶고 옆에 `.rs-head__mode`(상태 배지와 같은 크기의 점선 알약)를 둔다. Task D8 은 이 파일의 마크업을 고치지 않았다 — `ResearchHeader.vue` 를 고치는 Task 는 이것 하나다.
- **round08(UI 다크 테마 — 브랜치 `feat/round08-ui-dark-theme`)이 먼저 dev 에 들어오면** `SearchPlusMenu.vue` 의 script(`clear`·`activateMode`·`update:mode` emit, `brand` import)가 바뀐다. 이 Task 의 앵커는 그 바뀐 곳을 피해 골랐다. 처음 확인한 `6fd1769` 뒤에 그 브랜치에 들어온 `c1e8221`(2026-10-12 15:34 — 딥리서치 표기를 `DEEP_RESEARCH` 상수로)이 `useResearch`·`menuNav` 두 import 줄 사이에 `import { DEEP_RESEARCH } from "~/utils/brand";` 를 넣어 처음의 네 줄 import 앵커가 맞지 않았다(0번) — 그래서 Step 7 ② 를 한 줄 앵커 셋으로 나눴다. 나눈 뒤 dev `ef202fb`·round08 `6fd1769`·`c1e8221` 세 판의 `SearchPlusMenu.vue` 에 Step 7 의 Edit 여덟(①·②-1~3·③~⑥)을 얹어 모두 한 번씩 맞는 것을, `c1e8221` 의 `ResearchHeader.vue`(Step 9 ①②)·`[id].vue`(Step 9 ③~⑥)·`useResearch.ts`(Step 5)·`research.css`(Step 10)에도 이 Task 의 Edit 가 모두 한 번씩 맞는 것을 확인했다(2026-10-12, 계획서 블록을 그대로 뽑아 얹는 스크립트). 그래도 맞지 않으면 같은 자리를 지금 글자로 잡는다. **round08 이 06d worktree 를 딴 뒤에 dev 에 들어오면**(이 Task 를 마친 뒤 Task L6·N8 의 `git merge dev` 가 데려온다) `SearchPlusMenu.vue` 의 import 한 곳이 부딪힌다 — 이 Task 가 `useResearch`·`menuNav` 사이에 넣은 `import { safeLocalStorage } from "~/utils/browserId";` 와 round08 이 같은 자리에 넣은 `import { DEEP_RESEARCH } from "~/utils/brand";` 다. 두 줄을 모두 남기고 `brand` → `browserId` 순서로 둔다(dev `ef202fb` 를 바탕, 이 Task 를 얹은 글을 ours, `c1e8221` 을 theirs 로 `git merge-file` 해 본 결과 충돌은 이 한 곳이고 `ResearchHeader.vue`·`[id].vue` 의 이 Task 자리는 저절로 합쳐졌다 — 파트 D·L 의 다른 hunk 는 이 흉내에 들지 않았다).
- 판단은 `utils/researchMode.ts` 순수 함수다(vitest 13). `.vue` 는 typecheck·build 와 손 확인, 운영 확인은 Task Z6.

**Files:**
- Create: `frontend/utils/researchMode.ts`
- Create: `frontend/components/research/ResearchModePicker.vue`
- Modify: `frontend/composables/useResearch.ts`(`useResearchStarter().startResearch` :57-58)
- Modify: `frontend/components/research/SearchPlusMenu.vue`(칩 뒤 :41-43, import 한 줄 앵커 셋 :79·:81·:82, 상태 :110-111, `activate` 뒤 :132-136, `submit` :347, `onMounted` :390-391 — 앞 Task 가 고치지 않는 파일이라 da80f23 줄 번호 그대로)
- Modify: `frontend/pages/research/index.vue`(Task N5 를 했을 때만 — 새 연구 카드·import·상태·`start`·`onMounted`)
- Modify: `frontend/components/research/ResearchHeader.vue`(상태 배지 :7, props :32-39)
- Modify: `frontend/pages/research/[id].vue`(머리 props — da80f23 :33, import — :235 아래, `retryLabel` — :264 아래, `onRestart` — :401. 앞 Task 들이 이 파일을 고쳤으므로 앵커 글자로 잡는다)
- Modify: `frontend/assets/css/research.css`(인쇄 앵커 위 `.rs-mode*`·`.rs-head__meta`·`.rs-head__mode`)
- Test: `frontend/tests/unit/researchMode.test.ts`(새 파일 — 13)

기준선(Task N6 뒤): 전체 Task N5 뒤 + 4. N5·N6 을 잘랐으면 Task N7 뒤(Task N4 뒤 + 3).

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
Expected: `FAIL tests/unit/researchMode.test.ts` — `Error: Cannot find module '~/utils/researchMode' imported from '…/frontend/tests/unit/researchMode.test.ts'.` / `Test Files  1 failed (1)` / `Tests  no tests`

- [ ] **Step 3: 구현한다 — 순수 함수**

`frontend/utils/researchMode.ts` (새 파일, 전체):

```ts
// frontend/utils/researchMode.ts
// 딥리서치 '탐색 방식'(spec D28 — 06c 판정 뒤 2026-10-12 사용자 결정). 06c 의 두 스위치를 서버 기본값으로 켜지 않고
// (app/services/research/state.py DEFAULT_PARAMS 는 0 그대로) 사용자가 딥리서치를 시작할 때 고른다. 서버 기본값이 0 이라
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

(`ModeParams` 를 `interface` 로 두면 부르는 두 곳에서 `TS2345: Argument of type 'ModeParams' is not assignable to parameter of type 'ResearchParams'` 가 난다 — 작성 때 실측. 공개 이름은 모두 새 이름이다 — 2026-10-12 `frontend` 의 utils·composables·components 와 06d·06e 계획 전수로 확인했다. `isResearchMode`·`switchOf`·`hasModeKeys`·`MODE_IDS` 는 내보내지 않는다.)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchMode.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  13 passed (13)`

- [ ] **Step 5: `startResearch` 가 잡 params 를 받는다**

`frontend/composables/useResearch.ts` :57-58 — old:

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

(`ResearchParams` 는 이 파일이 이미 import 한다(:9). 부르는 곳 — SearchPlusMenu·`/research` 홈·`[id].vue` 다시 시작 — 은 아래 Step 에서 모두 두 번째 인자를 싣는다. 인자를 빼면 서버 기본값(= 폭넓게)으로 돈다.)

- [ ] **Step 6: 탐색 방식 부품을 만든다**

`frontend/components/research/ResearchModePicker.vue` (새 파일, 전체):

```vue
<!-- frontend/components/research/ResearchModePicker.vue -->
<!-- 딥리서치 '탐색 방식'(spec D28) — 폭넓게 · 정밀하게 두 칸 선택(radiogroup). 고른 값은 v-model 로 주고받고,
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

- [ ] **Step 7: + 메뉴의 딥리서치 칩 옆에 단다 — `SearchPlusMenu.vue`**

`frontend/components/research/SearchPlusMenu.vue` ① 칩 바로 뒤(:41-43). old:

```vue
      <button type="button" class="rs-plus__chip-x" :aria-label="`${active.label} 해제`" @click="clear">×</button>
    </span>
    <p v-if="error" class="rs-plus__error" role="alert">{{ error }}</p>
```

new:

```vue
      <button type="button" class="rs-plus__chip-x" :aria-label="`${active.label} 해제`" @click="clear">×</button>
    </span>
    <!-- 딥리서치를 고르면 칩 옆에 탐색 방식(spec D28) — 고른 값을 잡 params 두 칸(broaden·query_context)으로 싣는다 -->
    <ResearchModePicker
      v-if="active?.id === 'deep-research'"
      :model-value="researchMode"
      :disabled="disabled || busy"
      @update:model-value="pickMode"
    />
    <p v-if="error" class="rs-plus__error" role="alert">{{ error }}</p>
```

② import — 한 줄 앵커 셋(:79·:81·:82). 네 줄을 한 번에 잡지 않는다 — round08 의 `c1e8221` 이 `useResearch`·`menuNav` 두 줄 사이에 `import { DEEP_RESEARCH } from "~/utils/brand";` 를 넣어 네 줄 앵커가 맞지 않는다(아래 '알아 둘 것' 의 round08 줄). 셋 모두 Edit 를 따로 한다.

②-1 old:

```ts
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
```

new:

```ts
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import ResearchModePicker from "~/components/research/ResearchModePicker.vue";
```

②-2 old:

```ts
import { menuStep } from "~/utils/menuNav";
```

new:

```ts
import { safeLocalStorage } from "~/utils/browserId";
import { menuStep } from "~/utils/menuNav";
```

②-3 old:

```ts
import { researchErrorMessage } from "~/utils/researchErrors";
```

new:

```ts
import { researchErrorMessage } from "~/utils/researchErrors";
import {
  DEFAULT_RESEARCH_MODE,
  modeParams,
  readResearchMode,
  saveResearchMode,
  type ResearchMode,
} from "~/utils/researchMode";
```

(세 Edit 뒤의 import 블록은 dev 에서 네 줄 앵커로 한 번에 고친 것과 글자 그대로 같다. round08 이 먼저 들어왔으면 `brand` 줄이 `useResearch` 와 `browserId` 사이에 남는다 — 경로 이름 순서 그대로다.)

③ 상태(:110-111). old:

```ts
const busy = ref(false);
const error = ref("");

let host: HTMLElement | null = null;
```

new:

```ts
const busy = ref(false);
const error = ref("");
// 탐색 방식 — 서버 렌더와 첫 그림이 같게 기본(정밀하게)으로 시작하고 마운트 뒤 기억한 값을 읽는다
const researchMode = ref<ResearchMode>(DEFAULT_RESEARCH_MODE);

let host: HTMLElement | null = null;
```

④ `activate` 바로 뒤(:132-136 — round08 이 바꾸는 `clear`·`activateMode` 를 피한 자리). old:

```ts
function activate(mode: SearchMode): void {
  active.value = mode;
  error.value = "";
  if (field) field.placeholder = mode.placeholder;
}
```

new:

```ts
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

⑤ `submit`(:347). old:

```ts
    const jobId = await startResearch(plan.question);
```

new:

```ts
    const jobId = await startResearch(plan.question, modeParams(researchMode.value));
```

⑥ `onMounted`(:390-391). old:

```ts
  basePlaceholder = field?.placeholder ?? "";
  focused.value = !!field && document.activeElement === field;
```

new:

```ts
  basePlaceholder = field?.placeholder ?? "";
  researchMode.value = readResearchMode(safeLocalStorage());
  focused.value = !!field && document.activeElement === field;
```

(슬래시 명령으로 칩 없이 바로 보낸 경우에도 `submit` 은 그때의 `researchMode`(기억한 값 또는 기본 정밀하게)를 싣는다. 메인 랜딩은 숨은 논문 패널의 이 부품도 마운트돼 있지만 두 칸은 칩이 켜졌을 때만 선다.)

- [ ] **Step 8: (Task N5 를 했을 때만) `/research` 홈의 새 연구에도 단다 — `pages/research/index.vue`**

N5 를 잘랐으면(N7 을 했으면) 이 Step 은 건너뛰고 체크박스 옆에 '건너뜀 — N5 를 자름' 으로 적는다. 앵커는 Task N5 Step 6 의 글 그대로다(N6 은 이 파일을 고치지 않는다).

① 새 연구 카드 — 입력창과 아래 줄 사이. old:

```vue
            :disabled="starting"
            @keydown.enter.exact="onEnter"
          ></textarea>
        </label>
        <div class="rs-home__new-foot">
```

new:

```vue
            :disabled="starting"
            @keydown.enter.exact="onEnter"
          ></textarea>
        </label>
        <!-- 탐색 방식(spec D28) — + 메뉴의 딥리서치와 같은 부품·같은 기억 -->
        <ResearchModePicker :model-value="researchMode" :disabled="starting" @update:model-value="pickMode" />
        <div class="rs-home__new-foot">
```

② import 셋. old:

```ts
import { computed, onMounted, ref } from "vue";
import { useResearchStarter } from "~/composables/useResearch";
```

new:

```ts
import { computed, onMounted, ref } from "vue";
import ResearchModePicker from "~/components/research/ResearchModePicker.vue";
import { useResearchStarter } from "~/composables/useResearch";
```

old:

```ts
import { routeFor, type HistoryRoute } from "~/utils/historyRoute";
```

new:

```ts
import { safeLocalStorage } from "~/utils/browserId";
import { routeFor, type HistoryRoute } from "~/utils/historyRoute";
```

old:

```ts
import { QUESTION_MAX, questionProblem } from "~/utils/researchInput";
```

new:

```ts
import { QUESTION_MAX, questionProblem } from "~/utils/researchInput";
import {
  DEFAULT_RESEARCH_MODE,
  modeParams,
  readResearchMode,
  saveResearchMode,
  type ResearchMode,
} from "~/utils/researchMode";
```

③ 상태. old:

```ts
const problem = computed(() => questionProblem(question.value));
```

new:

```ts
const problem = computed(() => questionProblem(question.value));
// 탐색 방식 — + 메뉴의 딥리서치와 같은 기억(skx_research_mode). 서버 렌더와 같게 기본으로 시작해 마운트 뒤 읽는다
const researchMode = ref<ResearchMode>(DEFAULT_RESEARCH_MODE);

function pickMode(mode: ResearchMode): void {
  researchMode.value = mode;
  saveResearchMode(safeLocalStorage(), mode);
}
```

④ `start`. old:

```ts
    const jobId = await startResearch(q);
```

new:

```ts
    const jobId = await startResearch(q, modeParams(researchMode.value));
```

⑤ `onMounted`. old:

```ts
onMounted(() => {
  void loadFirst();
  void loadExamples();
});
```

new:

```ts
onMounted(() => {
  researchMode.value = readResearchMode(safeLocalStorage());
  void loadFirst();
  void loadExamples();
});
```

(새 연구 카드는 `.rs-card` 의 세로 flex·gap 0.8rem 이라 따로 간격을 주지 않는다. 고른 칸의 설명은 칸 옆, 좁으면 다음 줄로 내려간다 — Step 10 의 `.rs-mode__hint`.)

- [ ] **Step 9: 다시 시작은 원래 잡의 방식을 잇고, 머리에 그 잡의 방식을 보인다**

`frontend/components/research/ResearchHeader.vue` ① 상태 배지(:7). old:

```vue
      <span class="rs-status" :class="`rs-status--${phase}`">{{ phaseLabel(phase) }}</span>
    </div>
```

new:

```vue
      <div class="rs-head__meta">
        <span class="rs-status" :class="`rs-status--${phase}`">{{ phaseLabel(phase) }}</span>
        <!-- 그 잡의 탐색 방식(spec D28) — 방식을 모르는 잡(06c 전 잡·params 없음)은 그리지 않는다 -->
        <span v-if="modeLine" class="rs-head__mode">{{ modeLine }}</span>
      </div>
    </div>
```

② props(:32-39). old:

```ts
  canRetry: boolean;
  busy: boolean;
}>();
```

new:

```ts
  canRetry: boolean;
  busy: boolean;
  // '탐색 방식 · 정밀하게' 꼴(researchModeLine) — 없거나 null 이면 그리지 않는다
  modeLine?: string | null;
}>();
```

`frontend/pages/research/[id].vue` ③ 머리 props(da80f23 :33 — 앞 Task 들이 바꾸지 않는 두 줄). old:

```html
          :busy="busy || restarting"
          @toggle-layout="toggleLayout"
```

new:

```html
          :busy="busy || restarting"
          :mode-line="modeLine"
          @toggle-layout="toggleLayout"
```

④ import(da80f23 :235 — 앞 Task 들이 바꾸지 않는 줄. Task L6 의 앵커 `import { researchPhase } from "~/utils/researchEvents";` 는 건드리지 않는다). old:

```ts
import { researchErrorMessage } from "~/utils/researchErrors";
```

new:

```ts
import { researchErrorMessage } from "~/utils/researchErrors";
import { researchModeLine, restartParams } from "~/utils/researchMode";
```

⑤ `retryLabel`(da80f23 :264) 바로 뒤. old:

```ts
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
```

new:

```ts
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
// 머리의 탐색 방식 — 두 칸이 다 0 이면 폭넓게, 두 칸이 없는 잡(06c 전)은 null(그리지 않는다)
const modeLine = computed(() => (view.value ? researchModeLine(view.value.params) : null));
```

⑥ `onRestart`(da80f23 :401). old:

```ts
    const jobId = await startResearch(view.value.question);
```

new:

```ts
    // 원래 잡의 탐색 방식(broaden·query_context 두 칸)을 그대로 이어 쓴다 — 고르는 칸은 없다
    const jobId = await startResearch(view.value.question, restartParams(view.value.params));
```

(`[id].vue` 의 다른 두 [같은 질문으로 다시 시작] 버튼(실패·취소 카드, da80f23 :115·:121)도 같은 `onRestart` 를 부른다 — 따로 고칠 것이 없다.)

- [ ] **Step 10: 스타일**

`frontend/assets/css/research.css` — 인쇄 앵커 한 줄을 old 로 잡는다(Task N6 의 `.rs-basket*` 블록 뒤에 선다 — N5·N6 을 잘랐으면 Task N4 의 `.rs-deeper` 블록 뒤). old:

```css
/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

new:

```css
/* ── 딥리서치 탐색 방식(폭넓게 · 정밀하게 — spec D28) ──────── */
/* + 메뉴에서 딥리서치를 고르면 칩 옆에, /research 홈은 새 연구 입력창 아래에 선다. 고른 칸은 옅은 남색 홈 위에 흰 바탕·
   남색 글자로 올라온다 — 칩(남색 바탕·흰 글자)과 다른 모양이라 '켠 모드'와 '고른 방식'이 한 덩어리로 보이지 않는다 */
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
  background: var(--skx-border-c1);
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
  outline: 2px solid var(--skx-primary);
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
/* 결과 검색바(한 줄 4.4rem)는 입력칸 자리가 좁다 — 설명은 칸의 title·aria-describedby 로만 두고, 좁은 화면은 라벨도
   숨긴다(radiogroup 의 이름은 aria-labelledby 가 숨은 라벨에서도 읽는다) */
.skx-rsearch .rs-mode__hint {
  display: none;
}
@media (max-width: 768px) {
  .skx-rsearch .rs-mode__label {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .rs-mode__opt {
    transition: none;
  }
}
/* 연구 화면 머리 — 상태 배지 옆에 그 잡의 탐색 방식(상태 배지와 같은 크기의 옅은 점선 알약) */
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
  background: var(--skx-white);
  border: 1px dashed var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
```

(`.rs-head__mode` 의 크기는 Task D8 이 맞춘 `.rs-status`(0.55rem·`0.1rem 0.45rem`·줄높이 1.4)와 같다 — `.rs-head__meta` 의 `align-items: flex-start` 와 `.rs-status` 의 `align-self: flex-start` 가 같아 두 알약이 한 줄에 나란히 선다. 머리는 인쇄에서 숨는다(`.rs-page .rs-head` — 인쇄 블록). 새 색값·새 `@keyframes` 없이 `--skx-*` 토큰만, 새 움직임(칸 바뀜의 transition)은 움직임 줄이기에서 멈춘다.)

- [ ] **Step 11: 전체 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -rn "startResearch(" frontend/components frontend/pages
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff -- frontend/assets/css/research.css | grep '^+' | grep -cE "#[0-9a-fA-F]{3,6}\b|rgba?\(|@keyframes"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- app
```

Expected: vitest 실패 0, `Test Files` 는 이 Task 앞 + 1, `Tests` 는 이 Task 앞 수 + 13 · `0` · `0`(새 이름이 겹치지 않는다) · `└  ✨ Build complete!` · 세 줄 — `SearchPlusMenu.vue` 의 `startResearch(plan.question, modeParams(researchMode.value))`, `pages/research/[id].vue` 의 `startResearch(view.value.question, restartParams(view.value.params))`, `pages/research/index.vue` 의 `startResearch(q, modeParams(researchMode.value))`(N5 를 잘랐으면 앞의 둘 — 두 번째 인자 없이 부르는 곳이 남지 않았다) · `0` · 빈 출력(백엔드 그대로).

확인(손 — 로컬 화면을 운영 API 에 붙여 GET 으로만, Task Z1 Step 3 과 같은 명령): `/papers` 에서 + → 딥리서치를 고르면 칩 옆에 `탐색 방식` 두 칸이 서고 `정밀하게` 가 골라져 있다(처음 쓰는 브라우저) → ←→ 로 고른 칸이 바뀌고 초점이 따라간다, Tab 한 번에 두 칸을 지난다 → 새로고침 뒤 다시 딥리서치를 켜면 고른 값이 남아 있다 → 칩 × 로 끄면 두 칸도 사라진다. 375px 에서 랜딩 상자 안 설명이 다음 줄로 내려가고 가로 스크롤이 없다, 결과 검색바에는 설명이 없다. **보내지 않는다** — 보내면 운영에 잡이 생긴다(잡 params 는 운영 배포 뒤 Task Z6 이 본다).

- [ ] **Step 12: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchMode.ts frontend/tests/unit/researchMode.test.ts frontend/components/research/ResearchModePicker.vue frontend/composables/useResearch.ts frontend/components/research/SearchPlusMenu.vue frontend/pages/research/index.vue frontend/components/research/ResearchHeader.vue "frontend/pages/research/[id].vue" frontend/assets/css/research.css && git status --short && git commit -m "[Feat] round06d — 딥리서치를 시작할 때 고르는 '탐색 방식'(폭넓게 · 정밀하게, 기본 정밀하게 — spec D28)을 단다. + 메뉴에서 딥리서치를 고르면 칩 옆에 두 칸 선택(radiogroup — 방향키·Home·End, 고른 칸만 Tab)이 서고, 고른 방식을 잡 params 두 칸(폭넓게 broaden 0·query_context 0, 정밀하게 둘 다 1)으로 늘 함께 싣는다 — 서버 기본값은 0 그대로라 화면이 실어야 켜지고, query_context 만 켜면 범위 용어가 비어 효과가 없다. 고른 값은 이 브라우저에 기억한다(skx_research_mode — 읽지 못하면 정밀하게). /research 홈의 새 연구도 같은 부품을 쓰고, [같은 질문으로 다시 시작] 은 원래 잡의 두 칸을 이어 쓰며, 연구 화면 머리의 상태 배지 옆에 그 잡의 방식을 작게 보인다(두 칸 다 0 이면 폭넓게, 두 칸이 없는 06c 전 잡은 표시 없음). 판단은 utils/researchMode.ts 순수 함수(vitest 13), 백엔드 변경 없음"
```

N5 를 잘랐으면 `git add` 에서 `frontend/pages/research/index.vue` 를 빼고 메시지의 `/research 홈의 새 연구도 같은 부품을 쓰고, ` 를 지운다.

Expected: `A` 셋(`researchMode.ts`·`researchMode.test.ts`·`ResearchModePicker.vue`)·`M` 여섯(`useResearch.ts`·`SearchPlusMenu.vue`·`pages/research/index.vue`·`ResearchHeader.vue`·`[id].vue`·`research.css` — N5 를 잘랐으면 다섯), 커밋 1개.

**작성 때 확인(2026-10-12):** 이 Task 의 코드를 dev `ef202fb`(06c 머지까지 든 코드 — 파트 D·L·N 없이)의 `frontend` 사본에 얹어 쟀다 — Step 2 의 실패 메시지, Step 4 의 `13 passed`, 전체 vitest `40 files / 739` → `41 files / 752`, typecheck `error TS` 0(처음 `ModeParams` 를 interface 로 두었을 때 위 `TS2345` 두 줄이 나와 type 으로 고쳤다), `Duplicated imports` 는 그 사본의 기준선 `queueLine` 둘 그대로(새 이름은 겹치지 않는다 — Task D2 뒤에는 `0`), `npm run build` `└  ✨ Build complete!`, 빌드 산출물의 entry CSS 에 `rs-mode__opt`, JS 청크 하나에 `탐색 방식`. 검증 때 다시 쟀다(같은 날, Step 7 ② 를 한 줄 앵커 셋으로 나눈 뒤) — 계획서의 블록을 그대로 뽑아 같은 사본에 얹는 스크립트로 Step 2 의 실패 메시지(`Cannot find module '~/utils/researchMode'`·`Test Files  1 failed (1)`·`Tests  no tests`), Step 4 의 `13 passed (13)`, 전체 `41 files / 752`, typecheck `error TS` 0·`Duplicated imports` 2(기준선 `queueLine`), Step 5·7·9·10 의 Edit 열여섯(1·8·6·1)이 모두 한 번씩 맞음, 나눈 ② 로 얹은 결과가 처음 글로 얹은 결과와 파일마다 바이트까지 같음을 봤다. Step 8(`/research` 홈)은 Task N5 Step 6 의 페이지 글을 사본에 두고(N3·N5 의 새 파일 `sidebarResearch.ts`·`researchHome.ts`·`useResearchWorks.ts` 도 계획서 블록 그대로) Edit 일곱이 모두 한 번씩 맞았고, typecheck `error TS` 는 N2 를 얹지 않아 생기는 `composables/useResearchWorks.ts(21,20): error TS2339: Property 'total' does not exist on type 'ListResult'.` 한 줄뿐(이 Task 의 줄에는 없음), build 완료다 — 실행 때 Step 11 의 typecheck·build 가 다시 본다. 손 확인(화면)은 하지 않았다.

---

### Task N7: (조건부 — Task N5 를 잘랐을 때만) 사이드바 '예시 연구' 묶음·'모두 보기' 걷기

**조건:** 10/16 까지 Task N5 를 끝내지 못해 자르기로 했을 때만 한다(자르는 순서 2 — 그때는 Task N6 도 하지 않는다). **N5 를 했으면 이 Task 는 건너뛴다** — 계획의 Step 체크박스 옆에 '건너뜀 — N5 를 함' 으로 적는다. 자르기로 한 것은 완료노트(Task Z3)에 적는다.

spec §12-3 '`/research` 홈을 자르면(§12-6) 예시 연구는 사이드바 딥리서치 탭 맨 아래 '예시 연구' 묶음으로 보이고 '모두 보기'는 그리지 않는다', §12-6 자르는 순서. D26.

**알아 둘 것:**
- **시작 상태:** Task N4 뒤(N5·N6 없음). N5 를 일부 커밋한 뒤 자르기로 했으면 먼저 그 커밋을 되돌린다(커밋하지 않은 N5 변경이 있으면 그 전에 사용자에게 버려도 되는지 물은 뒤 버린다 — 작업 트리가 더러우면 revert 가 멈춘다) — `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d log --oneline -5` 로 `/research 홈` 커밋을 찾아 되돌린다 — git 기본 메시지(`Revert "…"`·`This reverts commit …`)는 커밋 규칙(대괄호 접두 + 한국어)에 어긋나므로 `--no-commit` 으로 되돌리고 메시지를 직접 단다:

  ```bash
  git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d revert --no-commit <커밋> && git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d commit -m "[Chore] round06d — /research 홈 커밋(<짧은 해시>)을 되돌린다 — 자르는 순서 2(spec §12-6)로 홈을 미루고 사이드바 '예시 연구' 묶음(Task N7)으로 간다"
  cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git status --short
  cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && ls frontend/utils/researchHome.ts frontend/composables/useResearchWorks.ts
  ```

  Expected: `[feat/round06d-research-progress-screen <해시>] [Chore] round06d — /research 홈 커밋(…)을 되돌린다 …` 와 `delete mode` 줄이 그 커밋이 만든 새 파일 수만큼(Task N5 Step 9 의 커밋 그대로면 `5 files changed, … deletions(-)` 에 `delete mode` 넷 — `pages/research/index.vue`·`utils/researchHome.ts`·`composables/useResearchWorks.ts`·`tests/unit/researchHome.test.ts`, `research.css` 는 `.rs-home*` 블록만 빠진다), 커밋 1개 · `status` 빈 출력 · `ls` 두 줄 모두 `ls: cannot access '…': No such file or directory`. 아래 새 파일 둘(`utils/researchHome.ts`·`composables/useResearchWorks.ts`)이 이 worktree 에 없어야 한다.
- **만드는 것은 N5 의 일부만:** `utils/researchHome.ts` 의 `WorkListItem`·`WorkListOut`·`exampleMeta`·`exampleRoute`, `composables/useResearchWorks.ts` 의 `useResearchWorksApi().listWorks` 와 테스트 셋(Task N5 의 `describe("exampleMeta")` 두 `it` 과 `it("예시 연구는 도달한 단계 화면(stepForPhase)으로 연다")` — 글자 그대로). 이름·모양은 공통 계약 그대로라 대회 뒤 홈을 만들 때 이 두 파일에 나머지(`homeGroups`·`HOME_PAGE_SIZE`·`ResearchPage`·`listResearch` 등)를 더하면 된다.
- **묶음은 기록이 없어도 그린다:** 조건은 `historyTab === 'research'` 와 예시가 하나 이상인 것뿐이고 `activeList.length` 를 보지 않는다 — 빈 문구 `<p>` 아래에도 선다(Task N3 의 '모두 보기' 와 같은 까닭: 기록 없는 새 브라우저가 예시 연구를 보는 길). 예시가 없거나(리허설 지정 전) 못 읽으면 묶음을 그리지 않는다. 줄은 질문 + `읽기 전용 · ${stepLine(phase)}` + 실행 시각(`exampleMeta(corpus).ranAt` — `2026년 10월 6일 09:30 실행`), 링크는 `exampleRoute`(도달한 단계 화면).
- **실행 시각·범위(spec §12-3 '실행 시각·코퍼스 범위를 표시한다' — 시연 정직성 규칙):** 연 연구 화면의 범위 띠(`CorpusScopeNote` — `scopeLine`)는 편수·끝 연도만 그리고 `corpus.at` 을 쓰지 않는다(`utils/workPhase.ts:105-110`, 머리 `ResearchHeader` 에도 시각이 없다 — `corpus.at` 을 화면에 쓰는 곳은 내려받은 문서 `utils/proposalDocument.ts:202` 뿐). 그래서 실행 시각은 사이드바 줄이 보인다 — 목록은 `{id, question, phase, created_at}` 만 주므로 Task N5 처럼 예시마다 `useWorkApi().getWork(id)`(06e 파일 `composables/useResearchWork.ts` — 읽기만)의 `corpus` 로 `exampleMeta` 를 만든다. 범위 문장은 좁은 줄에서 말줄임으로 잘리므로 줄에 넣지 않고 연 화면의 범위 띠에 맡긴다. 시각을 못 읽은 예시는 그 줄만 시각 없이 선다.
- **한 번만 읽는다:** 사이드바는 페이지마다 다시 마운트된다(각 페이지가 `<AppSidebar>` 를 그린다) — 예시 목록과 실행 시각은 `useState("skx:example-works")`·`useState("skx:example-metas")` 에 두고 처음 마운트 때 한 번만 읽는다(목록을 못 읽으면 다음 마운트에 다시, 시각만 못 읽은 예시는 다음 새로고침에). 마운트 뒤에 읽는다(브라우저 ID 헤더).
- **'모두 보기' 를 걷는다:** Task N3 의 링크와 `researchTotal` 을 지운다. `allResearchLabel`(`utils/sidebarResearch.ts`)·`useHistory().totalOf`(Task N2)는 테스트와 함께 남는다 — 홈을 만들면 다시 쓴다(완료노트에 '남겨 둠' 으로 적는다).

**Files:**
- Create: `frontend/utils/researchHome.ts`(일부)
- Create: `frontend/composables/useResearchWorks.ts`(일부)
- Modify: `frontend/components/AppSidebar.vue`(Task N3 뒤 — 모두 보기 자리·import·`researchTotal`·`onMounted`·scoped CSS)
- Test: `frontend/tests/unit/researchHome.test.ts`(새 파일 — 3)

기준선(Task N4 뒤): 전체 Task N3 뒤 + 2.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/researchHome.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/researchHome.test.ts
import { describe, expect, it } from "vitest";
import { exampleMeta, exampleRoute } from "~/utils/researchHome";
import { scopeLine } from "~/utils/workPhase";
import { ID1, ID2, ID3 } from "./helpers/fakeHistory";

describe("exampleMeta", () => {
  it("실행 시각은 corpus.at 의 KST, 범위는 scopeLine", () => {
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
  it("예시 연구는 도달한 단계 화면(stepForPhase)으로 연다", () => {
    expect(exampleRoute({ id: ID1, phase: "reading" })).toEqual({ path: `/research/${ID1}`, query: { s: "reading" } });
    expect(exampleRoute({ id: ID2, phase: "done" })).toEqual({ path: `/research/${ID2}`, query: { s: "proposal" } });
    expect(exampleRoute({ id: ID3, phase: "topics" })).toEqual({ path: `/research/${ID3}`, query: { s: "topics" } });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchHome.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  no tests` — 수집에서 `Error: Cannot find module '~/utils/researchHome' imported from '…/frontend/tests/unit/researchHome.test.ts'`.

- [ ] **Step 3: 구현한다 — 순수 함수·목록 API(일부)**

`frontend/utils/researchHome.ts` (새 파일, 전체):

```ts
// frontend/utils/researchHome.ts
// 예시 연구 목록(D26)의 모양·실행 시각과 여는 주소 — /research 홈을 미뤄 사이드바 딥리서치 탭의 '예시 연구' 묶음이 쓴다.
// 대회 뒤 홈을 만들면 이 파일에 진행 중·내 연구 묶음 함수를 더한다
import type { Corpus, WorkPhase } from "~/types/work";
import { kstDateTime } from "~/utils/reportDocument";
import { scopeLine, stepForPhase } from "~/utils/workPhase";

// GET /api/research-works(?example=1) 의 items[] — app/api/research_work.py list_works(상한 50)
export interface WorkListItem {
  id: string;
  question: string;
  phase: WorkPhase;
  created_at: string | null;
}

export interface WorkListOut {
  items: WorkListItem[];
}

// 예시 연구의 실행 시각·코퍼스 범위(시연 정직성 규칙 — spec §12-3). at 은 잡이 끝난 시각
// (research_works.corpus_snapshot, seeds.py). 모르는 칸은 null — 그 줄을 그리지 않는다.
// 사이드바 줄은 좁아 ranAt 만 쓰고, 범위는 연 연구 화면의 범위 띠(CorpusScopeNote)가 보인다
export function exampleMeta(corpus: Corpus | null | undefined): { ranAt: string | null; scope: string | null } {
  const at = corpus?.at ? new Date(corpus.at) : null;
  const ranAt = at && !Number.isNaN(at.getTime()) ? `${kstDateTime(at)} 실행` : null;
  return { ranAt, scope: scopeLine(corpus) };
}

// 예시 연구는 도달한 단계 화면으로 연다 — 사이드바의 이어간 연구 줄(historyRoute.routeFor)과 같은 규칙
export function exampleRoute(item: Pick<WorkListItem, "id" | "phase">): { path: string; query: { s: string } } {
  return { path: `/research/${encodeURIComponent(item.id)}`, query: { s: stepForPhase(item.phase) } };
}
```

`frontend/composables/useResearchWorks.ts` (새 파일, 전체):

```ts
// frontend/composables/useResearchWorks.ts
// 예시 연구 목록(GET /api/research-works?example=1) — /research 홈을 미뤄(Task N7) 사이드바의 '예시 연구' 묶음이 읽는다
import type { WorkListOut } from "~/utils/researchHome";
import { useApi } from "./useApi";

export function useResearchWorksApi() {
  const api = useApi();
  return {
    listWorks: (example: boolean) => api<WorkListOut>("/research-works", { query: example ? { example: 1 } : {} }),
  };
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchHome.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  3 passed (3)`

- [ ] **Step 5: 사이드바 — 모두 보기를 예시 묶음으로 바꾼다**

`frontend/components/AppSidebar.vue`(Task N3 뒤) — 템플릿의 모두 보기 자리. old:

```vue
        <!-- 목록이 비어도 건다 — 예시 연구가 보이는 /research 홈으로 가는 길은 이 링크뿐이다(기록 없는 새 브라우저) -->
        <NuxtLink v-if="historyTab === 'research'" to="/research" class="skx-history__all">
          {{ allResearchLabel(researchTotal) }}
        </NuxtLink>
```

new:

```vue
        <!-- /research 홈을 미뤘다 — 예시 연구는 딥리서치 탭 맨 아래 묶음으로 보인다. 기록이 없어도(빈 문구 아래) 건다 -->
        <div v-if="historyTab === 'research' && examples.length" class="skx-history__examples">
          <p class="skx-history__group">예시 연구</p>
          <ul class="skx-history__list">
            <li v-for="ex in examples" :key="ex.id">
              <NuxtLink :to="exampleRoute(ex)" class="skx-history-item">
                <span class="skx-history-item__query">{{ ex.question }}</span>
                <span class="skx-history-item__step">읽기 전용 · {{ stepLine(ex.phase) }}</span>
                <!-- 실행 시각(시연 정직성 규칙, spec §12-3) — 범위는 연 연구 화면의 범위 띠가 보인다 -->
                <span v-if="exampleMetas[ex.id]?.ranAt" class="skx-history-item__time">{{ exampleMetas[ex.id]?.ranAt }}</span>
              </NuxtLink>
            </li>
          </ul>
        </div>
```

import(Task N3 이 더한 줄) — old:

```ts
import { allResearchLabel, isLiveResearch, researchBadge, researchRowLine } from "~/utils/sidebarResearch";
```

new:

```ts
import { useWorkApi } from "~/composables/useResearchWork";
import { useResearchWorksApi } from "~/composables/useResearchWorks";
import { exampleMeta, exampleRoute, type WorkListItem } from "~/utils/researchHome";
import { isLiveResearch, researchBadge, researchRowLine } from "~/utils/sidebarResearch";
import { stepLine } from "~/utils/workPhase";
```

`researchTotal`(Task N3 이 더한 두 줄) — old:

```ts
// 딥리서치 기록 전체 수 — 06e 전 서버면 null('모두 보기'만)
const researchTotal = history.totalOf("research");
```

new:

```ts
// 예시 연구 — 페이지를 옮겨 사이드바가 다시 마운트돼도 한 번만 읽는다. 못 읽으면 묶음을 그리지 않고 다음 마운트에 다시 읽는다.
// 목록은 {id, question, phase, created_at} 만 준다 — 실행 시각은 예시마다 GET work 의 corpus 에서 읽고, 못 읽은 줄은 시각만 뺀다
const worksApi = useResearchWorksApi();
const workApi = useWorkApi();
const examples = useState<WorkListItem[]>("skx:example-works", () => []);
const exampleMetas = useState<Record<string, ReturnType<typeof exampleMeta>>>("skx:example-metas", () => ({}));
const examplesLoaded = useState<boolean>("skx:example-works-loaded", () => false);

async function loadExamples(): Promise<void> {
  if (examplesLoaded.value) return;
  examplesLoaded.value = true;
  try {
    examples.value = (await worksApi.listWorks(true)).items;
  } catch (e) {
    examplesLoaded.value = false;
    console.warn("[sidebar] 예시 연구를 읽지 못했다", e);
    return;
  }
  await Promise.all(
    examples.value.map(async (ex) => {
      try {
        const work = await workApi.getWork(ex.id);
        exampleMetas.value = { ...exampleMetas.value, [ex.id]: exampleMeta(work.corpus) };
      } catch (e) {
        console.warn("[sidebar] 예시 연구의 실행 시각을 읽지 못했다", e);
      }
    }),
  );
}
```

`onMounted` 끝(da80f23 :262-264) — old:

```ts
  syncPolling();
  document.addEventListener("visibilitychange", onVisibility);
});
```

new:

```ts
  syncPolling();
  document.addEventListener("visibilitychange", onVisibility);
  void loadExamples();
});
```

scoped CSS — Task N3 의 `.skx-history__all` 두 규칙. old:

```css
.skx-history__all {
  flex: none;
  align-self: flex-start;
  padding: 0.2rem 0.4rem;
  border-radius: var(--skx-radius-sm);
  font-size: 0.6rem;
  font-weight: 600;
  color: var(--skx-primary);
  text-decoration: none;
}
.skx-history__all:hover,
.skx-history__all:focus-visible {
  text-decoration: underline;
}
```

new:

```css
/* 예시 연구 묶음 — 기록 목록 아래에 늘 보이게 높이를 줄여 따로 굴린다 */
.skx-history__examples {
  display: flex;
  flex: none;
  flex-direction: column;
  gap: 0.4rem;
  padding-top: 0.6rem;
  border-top: 1px solid var(--skx-border-c1);
}
.skx-history__examples .skx-history__list {
  max-height: 9rem;
}
.skx-history__examples .skx-history-item {
  text-decoration: none;
}
.skx-history__group {
  margin: 0;
  padding: 0 0.4rem;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-gray-1);
}
```

(예시 줄의 `<li>` 에는 `skx-history__row` 를 달지 않는다 — 그 클래스는 지우기 버튼 자리(`padding-right: 1.6rem`)를 띄운다.)

- [ ] **Step 6: 전체 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && grep -c "skx-history__all\|researchTotal" components/AppSidebar.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected: `0`(모두 보기가 남지 않았다) · vitest 실패 0, `Test Files` 는 Task N4 뒤 + 1, `Tests` 는 Task N4 뒤 수 + 3 · `0` · `└  ✨ Build complete!`.

확인(손 — Task Z6 Step 5-2 의 'N5 를 잘랐으면' 갈래): 기록이 없는 새 시크릿 창의 딥리서치 탭 빈 문구 아래 '예시 연구' 묶음(예시가 지정돼 있을 때 — 리허설 10/23~25 `mark_example.py` 뒤) — 줄마다 질문·'읽기 전용 · 단계'·`… 실행`(KST 실행 시각), 줄을 누르면 그 예시 연구의 도달한 단계 화면이 열리고 범위 띠에 코퍼스 범위가 보인다.

- [ ] **Step 7: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/utils/researchHome.ts frontend/composables/useResearchWorks.ts frontend/tests/unit/researchHome.test.ts frontend/components/AppSidebar.vue && git status --short && git commit -m "[Feat] round06d — /research 홈을 미루고 예시 연구를 사이드바 딥리서치 탭 맨 아래 '예시 연구' 묶음으로 보인다(spec §12-3 — 홈을 자르면). GET /api/research-works?example=1 을 처음 마운트 때 한 번 읽고, 줄은 질문과 '읽기 전용 · 단계'에 예시마다 GET work 의 corpus 로 읽은 실행 시각(KST — 시연 정직성 규칙, 범위는 연 화면의 범위 띠), 누르면 도달한 단계 화면을 연다. 기록이 없어도 빈 문구 아래에 서고 예시가 없으면 그리지 않는다. 갈 곳이 없어진 '모두 보기' 는 걷는다(total 받기·라벨 함수는 홈을 만들 때 다시 쓰게 남긴다)"
```

Expected: `A` 셋·`M  frontend/components/AppSidebar.vue`, 커밋 1개(N5 를 되돌렸으면 그 `[Chore] … 되돌린다` 커밋이 앞에 하나 더).

---

### Task N8: (조건부 — 06e 가 먼저 dev 에 머지됐을 때만) 딥리드 패널 열림 때 LNB 접기 연결

**조건:** Task L6 뒤, 06d 를 dev 에 머지하기 직전(Task Z4 전)에 Step 1 의 06e 머지 수가 `1` 이상이면 한다. `0` 이면 **건너뛴다** — 06e 가 늦게 머지하며 06e 계획의 LNB 연결 Task 가 같은 두 곳을 단다(spec §12-5·§12-6). 건너뛴 사실을 완료노트(Task Z3)에 적는다. 06e 가 10/17 까지 들어오지 못해 06d 를 먼저 머지하기로 했으면 역시 건너뛴다.

spec §12-5 '딥리드 패널이 열릴 때 LNB 접기'·§12-4 배치(1440px·LNB 펼침이면 참고문헌 표가 빠듯 — 검색 화면 선례 `pages/papers/index.vue:2-4`). 06b 이월 없음.

**알아 둘 것 — LNB 접기 계약(06e 계획 정함 30 과 같은 문장):** 06e 는 ReadingStep·ProposalStep 의 emit `panel: [open: boolean]` 과 `[id].vue:73-74` 의 리스너 `@panel="workPanelOpen = $event"`, script 의 `const workPanelOpen = ref(false);`(`:514` 뒤)까지 단다. `AppSidebar :collapsed="workPanelOpen"` 와 루트 `is-lnb-collapsed`(`[id].vue:3-7` 두 곳)는 늦게 머지하는 줄이 단다 — 06d 가 늦으면 06d Task N8 이, 06e 가 늦으면 06e 계획의 LNB 연결 Task 가 이 두 곳만 고친다. **06d N8 은 리스너·새 ref·`watch(step)` 를 넣지 않고 `workPanelOpen` 을 읽기만 한다**(같은 요소에 `@panel` 이 두 번 붙으면 Vue 컴파일 오류다). 단계를 옮기면 ReadingStep·ProposalStep 이 내려가며 `onBeforeUnmount` 에서 `panel` false 를 낸다 — 06d 가 따로 풀 것이 없다.

**알아 둘 것 — 그 밖:**
- `[id].vue:3-7` 은 파트 D·L 의 어느 Task 도 고치지 않았다(D4 는 `:9` 의 `<main class="rs-page">` 부터) — 아래 old 가 da80f23 글자 그대로다.
- 루트 클래스와 prop 을 함께 다는 것은 검색 화면(`pages/papers/index.vue:2-4` — `:class="['skx-app', chatPaperId && 'is-lnb-collapsed']"` + `:collapsed="!!chatPaperId"`)과 같은 모양이다. `.skx-app.is-lnb-collapsed .skx-lnb`(`style_skovix.css:598-611`)가 접고, `AppSidebar` 의 `collapsed` prop(`AppSidebar.vue:146`·`:175` `isCollapsed`)은 접힌 동안 폴링을 쉬게 한다(`pollOnce` — `isCollapsed` 면 건너뜀).
- dev 를 받으면 06e 의 프론트 테스트가 함께 들어온다 — 받은 뒤의 수를 이 Task 의 새 '앞 수' 로 삼는다(계획 머리 '기준선 읽는 법').
- `git fetch origin dev:dev` 가 `refusing to fetch into branch 'refs/heads/dev' checked out at …` 로 막히면 Task 0 의 '알아 둘 것' 첫 줄대로 한다(그 worktree 를 쓰는지 사용자에게 묻고 지운 뒤 다시).

**Files:**
- Modify: `frontend/pages/research/[id].vue`(:3-7 두 곳 — merge dev 뒤)

기준선(Task L6 뒤): Task L6 의 '통과 확인' 수.

- [ ] **Step 1: 조건을 본다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git status --short
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git fetch origin dev:dev
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git log --oneline --merges dev | grep -c "feat/round06e-assistant-auto-report"
```

Expected:
- `status` — 빈 출력(받기 전에 작업 트리가 깨끗해야 한다)
- `fetch` — 출력 없음 또는 `<옛>..<새>  dev -> dev` 한 줄
- 06e 머지 → `1` 이상이면 이 Task 를 한다. `0` 이면 여기서 멈추고 '건너뜀 — 06e 가 아직 dev 에 없다(06e 가 단다)' 로 적는다

(06e 가 루트 클래스를 이미 달았는지는 dev 를 받은 뒤 Step 3 에서 본다 — 지금의 06d `[id].vue` 에는 06e 변경이 아직 없어(Task L6 이 06e 까지 받은 경우만 빼고) 여기서 보면 늘 `0` 이다.)

- [ ] **Step 2: dev 를 받는다(06e 연구 어시스턴트)**

Run: `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d merge dev -m "Merge dev into feat/round06d-research-progress-screen — 06e 연구 어시스턴트 받기"`

Expected: `Merge made by the 'ort' strategy.` 와 06e 의 파일 목록(Task L6 이 06e 를 이미 받았으면 `Already up to date.` — 그대로 Step 3 로 간다).

충돌이 나면(대개 `frontend/pages/research/[id].vue` 의 import 블록·`work.css`) 어느 한쪽을 통째로 고르지 않는다:
- `[id].vue` — 06e 블록(`<!-- 연구 어시스턴트 단계(?s=) …` 부터 `<div v-else class="rs-body" …>` 앞까지, 06e 의 `@panel` 리스너 포함)과 06e 가 더한 script(`const workPanelOpen = ref(false);` 등)는 dev 쪽, 06d 가 고친 그 밖의 줄(배치·막대·따라가기·절 자리·옆 칸·"이렇게 이해했어요")은 이 브랜치 쪽. import 는 두 쪽의 줄을 모두 남긴다(같은 줄이면 하나만).
- `work.css` — 06d 는 근거 장부 블록(`근거 장부(EvidenceLedger)` 블록과 `.wk-side-ledger .wk-ledger` 간격 규칙 — 이 브랜치 쪽 주석은 Task L5 가 바꾼 '옆 칸 맨 위 근거 장부(진행 패널 위)')만 고쳤다 — 그 블록은 이 브랜치 쪽, 나머지는 dev 쪽.
- 그 밖의 `frontend/` 파일이 충돌하면 멈추고 사용자와 06e 세션에 알린다(06e 와 06d 가 같은 줄을 고치지 않는다는 경계가 깨졌다).

다 풀면:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -cE '^(<<<<<<<|=======|>>>>>>>)' "frontend/pages/research/[id].vue" frontend/assets/css/work.css
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "frontend/pages/research/[id].vue" && git add frontend/assets/css/work.css && git commit --no-edit
```

Expected: 두 파일 모두 `:0`, 머지 커밋 1개(충돌이 났던 파일만 `git add` 한다 — 위는 두 파일이 충돌했을 때의 예).

- [ ] **Step 3: 받은 뒤 그대로 도는지 본다(06d 변경 전)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -n "workPanelOpen" "frontend/pages/research/[id].vue"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "is-lnb-collapsed" "frontend/pages/research/[id].vue"
```

Expected:
- vitest 실패 0 — 나온 `Test Files`·`Tests` 를 적어 두고 이 Task 의 새 '앞 수' 로 삼는다(Task L6 뒤 수 + 06e 가 더한 프론트 테스트 수)
- `0`
- `0` — `1` 이상이면 06e 와 06d 가 같은 이름을 서로 다른 파일에서 내보낸다(Nuxt 자동 import 가 하나를 말없이 버린다). 경고 줄의 이름·두 파일을 사용자와 06e 세션에 알리고 멈춘다
- `workPanelOpen` 세 줄 — `@panel="workPanelOpen = $event"` 두 줄(ReadingStep·ProposalStep)과 `const workPanelOpen = ref(false);` 한 줄. 06e 가 다른 이름을 썼으면 Step 4 의 두 곳에 **06e 의 이름을 그대로** 쓴다. 0 줄이면(06e 가 리스너를 달지 않았다) 계약이 어긋났다 — 06d 가 리스너를 대신 달지 않고 멈춰 06e 세션에 알린다
- `is-lnb-collapsed` → `0`(아직 아무도 달지 않았다 — Step 4 로 간다). `1` 이상이면 06e 쪽이 이미 달았다 — 계약과 다르지만 같은 결과이므로 Step 4~5 를 건너뛰고(Step 4 의 old 가 맞지 않는다) 완료노트(Task Z3)에 적는다. 그때 Step 2 의 머지 커밋 말고는 커밋할 것이 없다(Step 6 도 건너뛴다)

- [ ] **Step 4: 루트 클래스와 사이드바 prop 두 곳만 단다**

`frontend/pages/research/[id].vue` :3-5 — 고치기 전:

```vue
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
```

고친 뒤:

```vue
  <div :class="['skx-app', workPanelOpen && 'is-lnb-collapsed']">
    <AppSidebar
      :collapsed="workPanelOpen"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
```

새 ref·리스너·`watch(step)` 는 넣지 않는다(06e 정함 30).

- [ ] **Step 5: 확인한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff --stat -- frontend
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "is-lnb-collapsed" "frontend/pages/research/[id].vue"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected:
- `frontend/pages/research/[id].vue | 3 ++-` 와 `1 file changed, 2 insertions(+), 1 deletion(-)`(두 곳만 — 06e 의 리스너·ref 를 건드리지 않았다)
- `1`
- vitest 실패 0, Step 3 에서 적은 수와 같다(+0)
- `0`(작성 때 06e 의 `const workPanelOpen = ref(false);` 를 흉내 내어 같은 두 곳을 단 typecheck 가 0 이었다)
- `└  ✨ Build complete!`

확인(손 — 마무리 운영 확인 Task Z6): 이어간 연구의 `?s=reading` 에서 논문 행의 딥리드 패널을 열면 사이드바가 접히고, 닫으면 펼쳐진다. 패널을 연 채 단계를 옮기면(제목 고르기·보고서) 사이드바가 다시 펼쳐진다.

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "frontend/pages/research/[id].vue" && git status --short && git commit -m "[Feat] round06d — 딥리드 패널이 열리면 연구 화면의 사이드바를 접는다(06e 패널 연결 — 06e 가 먼저 dev 에 들어와 늦게 머지하는 06d 가 단다). 06e 가 단 workPanelOpen 을 읽기만 해 루트 is-lnb-collapsed 와 AppSidebar 의 collapsed 두 곳에 잇는다 — 검색 화면(DeepRead 패널)과 같은 모양이고 리스너·새 상태는 더하지 않는다"
```

Expected: `M  frontend/pages/research/[id].vue`(git 은 대괄호 경로를 따옴표로 감싸지 않는다), 커밋 1개(Step 2 의 머지 커밋과 합쳐 2개).

---

### 파트 메모 — 계획이 정한 세부

인터페이스(파일·공개 이름·시그니처·모양·DOM id·클래스)는 계획 머리 '공통 계약' 과 각 Task 의 코드가 정본이다. 아래 표의 '뼈대' 는 이 계획을 쓸 때 파트끼리 맞춘 초안(계획서에 들지 않는다)이고, 이 절은 그 초안이 정하지 않았거나 글이 달라진 곳과 까닭을 남긴다.

| # | 뼈대 | 이 파트 | 까닭 |
|---|---|---|---|
| 1 | `utils/sidebarResearch.ts` 공개 이름 = `LIVE_RESEARCH_STATUSES`·`isLiveResearch`·`researchRowLine`·`allResearchLabel`, Task N3 테스트 +7 | **`researchBadge(r): { label; tone }` 를 더한다**(사이드바 `badgeOf` 의 상태 → 배지 switch 를 옮김) — 테스트 `describe("researchBadge")` 의 `it("잡 상태로 배지를 고르고, 상태가 없으면 '알 수 없음'(사이드바·/research 홈이 같이 쓴다)")` 하나를 더해 **N3 +8**, 파트 N 합계 **+22**(뼈대 +21 — 계획 머리 '테스트 수 어림' 에 반영돼 있다) | Task N5 의 `/research` 홈 줄이 사이드바와 같은 배지를 쓴다 — 같은 판단을 `.vue` 두 곳에 두지 않는다(판단은 utils 순수 함수로). 새 이름은 utils·composables·06c·06e 계획 어디에도 없다(작성 때 전수 확인). 공통 계약 '새 파일과 공개 이름' 표의 `utils/sidebarResearch.ts` 행에 넣었다 |
| 2 | Task N6 의 [담기 ▾] 자리 = 결과 카드 버튼 줄(`skx-paper-item__btn-row`) **안** 끝 — 인용 버튼 `</button>` 과 `</div>` 사이 | 버튼 줄 **아래**·DeepRead 버튼 위의 한 줄(`</div>` 뒤). old 는 인용 아이콘 `<img>`·`</button>`·`</div>` 세 줄에 DeepRead 버튼의 앞 세 줄을 더한 여섯 줄 | 카드 오른쪽 칸이 `width: 8.4rem`(`style_skovix.css:3787-3795`)이고 버튼 줄에 '원문 보기'(flex 1)·인용 버튼(2.05rem)이 이미 있어 세 번째 버튼이 들어가지 않는다 |
| 3 | Task N5 '429 browser_active 의 진행 중 연구 링크는 `[id].vue:50-52` 처럼' | 그대로 달되(`activeResearchId`) **방어로만** 둔다고 코드 주석·알아 둘 것에 적는다 | 지금 서버는 연구 만들기(`POST /api/research`, `app/api/research.py:229-247`)에서 429 를 내지 않고 승인·재시도(`_to_run_queue`)에서만 낸다 — 두 번째 질문은 잡이 만들어지고 연구 화면의 [승인] 에서 막힌다(그 화면이 같은 링크를 단다). Task Z6 Step 5-3 의 기대도 이 동작('잡이 만들어져 연구 화면으로 가고, [승인] 을 누르면 진행 중인 연구 안내와 링크')으로 적었다 |
| 4 | Task N2 '`refresh` 가 `total !== undefined` 일 때만 그 kind 값을 바꾼다' | 같은 조건에 더해, 목록을 읽는 사이 이 탭에서 지운 기록 수(응답에서 버린 수)를 서버 수에서 뺀다 — 테스트 `clear 는 0, remove 는 알던 값에서 하나 줄인다` 가 이 경우를 함께 덮는다(이름·수 그대로) | 기존 `removedAt` 규칙(늦게 온 응답이 지운 기록을 되살리지 않는다)과 같은 자리 — 빼지 않으면 지운 직후 수가 다시 하나 늘어 보인다 |
| 5 | Task N7 '예시 연구 묶음 — `GET /api/research-works?example=1` 목록(링크 `exampleRoute`)', N7 이 만드는 것 `exampleRoute`·`WorkListItem`(테스트 +1) | 줄은 질문 + `읽기 전용 · ${stepLine(phase)}` + 실행 시각(`exampleMeta(corpus).ranAt` — 예시마다 `getWork`), 목록·시각은 `useState("skx:example-works")`·`useState("skx:example-metas")` 에 두어 처음 마운트 때 한 번만 읽는다. 범위 문장은 줄에 넣지 않는다. N7 이 `exampleMeta` 와 그 테스트 둘도 만든다 — **N7 테스트 +3**(뼈대 +1 — 계획 머리 '테스트 수 어림' 은 'N5 의 +4 대신 +3' 으로, 파일 구조 표는 N7 이 `WorkListItem`·`WorkListOut`·`exampleMeta`·`exampleRoute`·`listWorks` 를 만든다고 적었다) | 사이드바는 페이지마다 다시 마운트된다. spec §12-3 은 예시 연구에 실행 시각·코퍼스 범위를 표시하라고 한다 — 연 화면의 범위 띠(`scopeLine`)는 범위만 그리고 시각(`corpus.at`)은 어디에도 없어 시각은 줄이 보인다. 좁은 줄에 범위 문장을 넣으면 말줄임으로 잘린다 — 범위는 연 연구 화면의 범위 띠가 보인다 |
| 6 | Task N3 '`<span v-if="h.kind === 'research' && researchRowLine(h.research)" …>`' | `rowLineOf(h)` 함수 하나로 조건과 글을 함께 읽는다 | 템플릿에서 유니온 좁히기를 두 번 쓰지 않게 — 결과는 같다 |

**작성 때 확인한 것(실행자가 다시 볼 필요 없음):** 위 코드를 da80f23 의 `frontend` 사본에 Task 순서대로 얹어 각 실패 메시지(Step '실패를 확인한다'의 기대 출력)와 통과 수, typecheck `error TS` 0(일부러 넣은 타입 오류는 `.vue`·`utils`·`tests` 모두에서 잡히는 것도 확인), N6 뒤 `npm run build` 완료, N7 경로·N8(06e 변수 흉내) typecheck 0 을 실측했다. `research.css`·`AppSidebar.vue` 에 더한 줄에 새 색값(hex·rgba)·새 `@keyframes` 가 없다(Task Z1 Step 2 의 검사와 같은 식).

---

## 마무리

파트 D·L·N 을 모두 마친 뒤 — 전체 회귀·경계·정적 리뷰(Task Z1), 06c 판정 연계(Task Z2), 문서(Task Z3), `dev` 머지(Task Z4 — 사용자 승인), 운영 배포(Task Z5 — 사용자), 운영 처음부터 끝까지 1회(Task Z6 — 사용자), 배포 기록(Task Z7).

### Task Z1: 전체 회귀·경계 확인·영역별 정적 리뷰·반영

**왜:** 파트 D·L·N 을 모두 마친 브랜치를 dev 에 넣기 전에 한 번에 회귀를 보고, 이 줄이 손대지 말아야 할 곳(백엔드·06e 파일·`[id].vue:57-75`·`work.css` 장부 블록 밖·`researchDraft`)이 그대로인지 확인하고, 영역별 정적 리뷰(`.claude/agents/code-reviewer.md`)로 이 줄의 위험(한 이름 한 파일·선택 필드·reduced-motion·토큰·접근성·쓰는 요청이 그리기 경로에 없음·06c 계약)을 본다(GIT_WORKFLOW — 리뷰 뒤 dev 머지). 리뷰 반영도 이 Task 안에서 끝내고 '리뷰를 마친 커밋'을 적는다 — 완료노트·dev 머지가 이 커밋을 가리킨다.

**Files:**
- Modify: 리뷰 발견을 고치는 파일(발견에 따라 — 각 수정은 판단을 순수 함수 쪽에서 실패 테스트를 먼저 쓰고 고친다)
- 저장소 밖 작업 폴더: `C:/Users/LANDSOFT/round06d-eval/review/`(리뷰어에게 줄 diff — 저장소에 넣지 않는다)

**알아 둘 것:**
- Task L6 이 06c 를 기다리는 중이면 이 Task 를 L6 전에 먼저 돌려도 된다 — 그때는 L6(·N8) 뒤 Step 1·2 를 다시 돌리고, L6·N8 의 diff 만 해당 영역 리뷰어에게 다시 보인다(Step 4 의 되풀이 규칙).
- code-reviewer 는 읽기 전용(Read·Grep·Glob)이라 git 을 돌리지 못한다 — 영역 diff 를 파일로 떠서 경로를 준다.
- `BASE=$(git merge-base HEAD dev)` 는 마지막으로 받은 dev 다 — L6·N8 이 dev 를 받았으면 그 커밋이고, `git diff $BASE HEAD` 는 06d 자신의 변경만 보인다.
- 리뷰 반영 커밋도 `[Fix] round06d — …` 처럼 Co-Authored-By 없이 쓴다. 발견을 거절할 때는 까닭을 완료노트 §3 에 적는다(Task Z3).

- [ ] **Step 1: 전체 회귀**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchLayout.test.ts tests/unit/queueLine.test.ts tests/unit/researchEvents.test.ts tests/unit/synthCard.test.ts tests/unit/restorePosition.test.ts tests/unit/evidenceLedger.test.ts tests/unit/historyStore.test.ts tests/unit/historyState.test.ts tests/unit/paperResearch.test.ts tests/unit/researchDraft.test.ts tests/unit/workPhase.test.ts tests/unit/researchProgress.test.ts tests/unit/planSlots.test.ts tests/unit/researchFollow.test.ts tests/unit/sidebarResearch.test.ts tests/unit/researchHome.test.ts tests/unit/addToWork.test.ts tests/unit/researchMode.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx vitest run tests/unit/researchDraft.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected:
- typecheck 오류 `0` · `Duplicated imports` `0`(D2 가 지운 경고가 되살아나지 않았다 — 한 이름 한 파일)
- vitest 전체 — 실패 0. `Test Files` 는 기준선 파일 수 + 7(N6 을 잘랐으면 + 6 — `addToWork.test.ts` 가 없다), `Tests` 는 계획 순서상 마지막으로 끝낸 프론트 Task(N8 을 했으면 N8, 아니면 L6)의 '통과 확인' 수와 같다(= Task 0 의 기준선 + 파트 D·L·N 이 더한 수 + L6·N8 이 dev 에서 받은 06c·06e 테스트 수 — 이 Step 은 테스트를 더하지 않는다). 다르면 Task 별 '통과 확인' 명령으로 어느 파일의 수가 다른지 센다
- 06d 묶음 열여덟 파일(Task N9 의 `researchMode.test.ts` 포함) — 실패 0. N6 을 잘랐으면 명령에서 `tests/unit/addToWork.test.ts` 를 빼고 열일곱 파일. 나온 수를 적어 둔다(완료노트 §4)
- `researchDraft.test.ts` — `Tests  23 passed (23)`(Task 0 과 같다 — spec §12-7 '기존 테스트 그대로')
- build 의 `Duplicated imports` `0`, 마지막 줄 `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: `5 failed, N passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 Task 0 기준선과 같은 여섯 줄(test_build_manifest 2·test_loaders 3·test_book_chat 수집). 06d 는 `app/` 을 바꾸지 않으므로(Step 2 의 diff 가 빈 출력) N 은 마지막으로 받은 dev 의 수다 — 기준선 2327 에 L6·N8 이 받은 06c·06e 백엔드 테스트를 더한 수. 그 밖의 실패가 있으면 06d 가 아니라 받은 dev 의 것이다 — 멈추고 사용자와 그 줄의 세션에 알린다. 나온 N 을 적어 둔다(완료노트 §4).

- [ ] **Step 2: 경계 — 고친 파일·고치지 않을 파일·06e 블록·장부 블록·색값·커밋 트레일러**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
BASE=$(git merge-base HEAD dev); echo "$BASE"
git diff --name-only $BASE HEAD -- app frontend scripts infra | LC_ALL=C sort
git diff --stat $BASE HEAD -- app docker-compose.yml docker-compose.dev.yml infra frontend/package.json frontend/package-lock.json frontend/components/work/WorkStepper.vue frontend/components/research/PlanCard.vue frontend/components/research/CitationChip.vue frontend/components/research/ReportView.vue frontend/components/BookChat.vue frontend/utils/researchDraft.ts frontend/tests/unit/researchDraft.test.ts frontend/utils/workPhase.ts frontend/utils/researchErrors.ts frontend/composables/useResearchWork.ts frontend/types/work.ts frontend/utils/citations.ts frontend/pages/search-classic.vue
diff <(git show $BASE:"frontend/pages/research/[id].vue" | sed -n '/연구 어시스턴트 단계(?s=)/,/<div v-else class="rs-body"/p') <(sed -n '/연구 어시스턴트 단계(?s=)/,/<div v-else class="rs-body"/p' "frontend/pages/research/[id].vue") && echo "단계 본문 그대로"
git diff $BASE HEAD -- frontend/pages/papers/index.vue | grep -cE "BookChat|doc-kind"
S1=$(git show $BASE:frontend/assets/css/work.css | grep -n "근거 장부(EvidenceLedger)" | cut -d: -f1)
E1=$(git show $BASE:frontend/assets/css/work.css | grep -n "진행 막대(WorkStepper)" | cut -d: -f1)
S2=$(git show $BASE:frontend/assets/css/work.css | grep -n "진행 패널 아래 근거 장부" | cut -d: -f1)
E2=$((S2 + 4)); echo "$S1 $E1 $S2 $E2"
git diff -U0 $BASE HEAD -- frontend/assets/css/work.css | awk -v s1=$S1 -v e1=$E1 -v s2=$S2 -v e2=$E2 '/^@@/{split($2,a,/[-,]/); s=a[2]+0; if (!((s>=s1 && s<e1) || (s>=s2 && s<=e2))) print "장부 블록 밖:", $0}'
git diff $BASE HEAD -- frontend/assets/css/research.css frontend/assets/css/work.css frontend/components frontend/pages | grep '^+' | grep -cE "#[0-9a-fA-F]{3,6}\b|rgba?\("
git diff $BASE HEAD -- frontend/assets/css/research.css frontend/assets/css/work.css | grep '^+' | grep -c "@keyframes"
git diff $BASE HEAD -- frontend | grep '^+' | grep -cE "wk-rbar|--wk-bar-thick|reportBar"
git log $BASE..HEAD --format=%B | grep -ciE "Co-Authored-By|Generated with Claude Code"
git status --short
```

Expected:
- `BASE` — Task 0 Step 2 의 dev 커밋, 또는 L6·N8 이 받은 dev 커밋
- 고친 파일 목록 — 정확히 다음 줄들(이 계획서를 브랜치에 커밋했으면 `docs/` 라 이 목록에 들지 않는다). **N6 을 잘랐으면** `frontend/components/research/AddToWorkMenu.vue`·`frontend/tests/unit/addToWork.test.ts`·`frontend/utils/addToWork.ts` 셋이 없다. **N5 를 잘랐으면** `frontend/pages/research/index.vue` 가 없다(N7 이 `researchHome.ts`·`useResearchWorks.ts`·`researchHome.test.ts` 를 만든다). `frontend/components/research/ResearchHeader.vue` 는 Task N9 만 고친다(머리의 탐색 방식 — Task D8 은 클래스만으로 입혀 마크업을 고치지 않는다). Task N9 가 더한 여섯 줄 — `ResearchHeader.vue`·`ResearchModePicker.vue`·`SearchPlusMenu.vue`·`composables/useResearch.ts`·`tests/unit/researchMode.test.ts`·`utils/researchMode.ts` — 은 N5·N6 을 잘라도 남는다. 리뷰 반영으로 더한 파일이 있으면 그 파일과 까닭을 완료노트 §3 에 적는다

```text
frontend/assets/css/research.css
frontend/assets/css/work.css
frontend/components/AppSidebar.vue
frontend/components/research/AddToWorkMenu.vue
frontend/components/research/ProgressPanel.vue
frontend/components/research/ReportSkeleton.vue
frontend/components/research/ResearchHeader.vue
frontend/components/research/ResearchModePicker.vue
frontend/components/research/ResearchProgressBar.vue
frontend/components/research/SearchPlusMenu.vue
frontend/components/research/SynthProgressCard.vue
frontend/components/work/EvidenceLedger.vue
frontend/composables/useHistory.ts
frontend/composables/useResearch.ts
frontend/composables/useResearchWorks.ts
frontend/composables/useRestorePosition.ts
frontend/composables/useSectionFollow.ts
frontend/pages/index.vue
frontend/pages/papers/index.vue
frontend/pages/research/[id].vue
frontend/pages/research/index.vue
frontend/tests/unit/addToWork.test.ts
frontend/tests/unit/evidenceLedger.test.ts
frontend/tests/unit/historyState.test.ts
frontend/tests/unit/historyStore.test.ts
frontend/tests/unit/paperResearch.test.ts
frontend/tests/unit/planSlots.test.ts
frontend/tests/unit/queueLine.test.ts
frontend/tests/unit/researchEvents.test.ts
frontend/tests/unit/researchFollow.test.ts
frontend/tests/unit/researchHome.test.ts
frontend/tests/unit/researchLayout.test.ts
frontend/tests/unit/researchMode.test.ts
frontend/tests/unit/researchProgress.test.ts
frontend/tests/unit/restorePosition.test.ts
frontend/tests/unit/sidebarResearch.test.ts
frontend/types/history.ts
frontend/types/research.ts
frontend/utils/addToWork.ts
frontend/utils/evidenceLedger.ts
frontend/utils/historyState.ts
frontend/utils/historyStore.ts
frontend/utils/paperResearch.ts
frontend/utils/planSlots.ts
frontend/utils/researchEvents.ts
frontend/utils/researchFollow.ts
frontend/utils/researchHome.ts
frontend/utils/researchLayout.ts
frontend/utils/researchMode.ts
frontend/utils/researchProgress.ts
frontend/utils/restorePosition.ts
frontend/utils/sidebarResearch.ts
frontend/utils/synthCard.ts
```

- 고치지 않을 파일 `diff --stat` — 빈 출력(백엔드·compose·인프라·패키지·06e 파일·06c PlanCard·CitationChip·ReportView·researchDraft·search-classic)
- `단계 본문 그대로` — `[id].vue` 의 06e 블록(`<!-- 연구 어시스턴트 단계(?s=) …` 주석 da80f23 `:55` 부터 `<div v-else class="rs-body" …>` `:77` 까지 — 06e 단계 본문 `:57-75` 와 그 앞 주석·뒤 줄)이 06d 변경으로 바뀌지 않았다. 06e 가 그 안에 단 리스너(`@panel`)는 BASE 에 이미 있으므로 diff 에 나오지 않는다
- `BookChat|doc-kind` — `0`(06e 의 한 속성 자리를 건드리지 않았다)
- `S1 E1 S2 E2` — da80f23 이면 `75 167 1216 1220`(06e 를 받았으면 그 위치). awk 는 빈 출력(`work.css` 의 hunk 가 모두 근거 장부 블록 안이다)
- 더한 줄의 색값 — `0`(`--skx-*` 토큰만)
- 더한 `@keyframes` — `1`(L5 의 `wk-review` — `research.css` 의 새 움직임은 기존 `rs-sheen`·`rs-pop`·`rs-blink` 를 다시 쓴다). 수가 다르면 새 keyframes 마다 `@media (prefers-reduced-motion: reduce)` 에서 멈추는 규칙이 있는지 리뷰 A·C 영역에 함께 보인다
- `wk-rbar|--wk-bar-thick|reportBar` — `0`(06e 보고서 화면의 큰 막대는 06e 몫이다 — 10-11 사용자 확인·06e 계획 정함 28. 06d 가 그 이름을 만들거나 고치지 않았다. 종료 코드 1 은 정상)
- 트레일러 — `0`(종료 코드 1 은 맞는 줄이 없을 때의 정상 값. Git Bash 의 grep 은 `-i` 와 `-e` 여럿을 함께 주면 죽으므로 `-E` 한 패턴으로 쓴다)
- `git status --short` — 빈 출력

- [ ] **Step 3: (선택) 로컬 화면을 운영 API 에 붙여 GET 으로만 본다**

리뷰 전에 화면이 SSR·하이드레이션에서 깨지지 않는지 한 번 본다. 운영에 쓰지 않는다 — 아래에서 누르면 쓰는 버튼(승인·취소·[이 연구 이어가기]·[담기]·[계획 세우기]·딥리서치 칩을 켠 입력창의 보내기·[같은 질문으로 다시 시작])은 누르지 않는다. 포트는 다른 세션의 미리보기(3000)와 겹치지 않게 3016 을 쓴다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && NUXT_DEV_API_TARGET=https://skovix.landsoft.co.kr/api npx nuxi dev --port 3016
```

(이 명령은 백그라운드로 띄우고, 다 보면 그 프로세스를 끈다.) 브라우저로 본다:
- `http://localhost:3016/` — 랜딩 탭 '소장자료검색', 입력창 안내 '찾고싶은 소장자료를 문장으로 검색해보세요!'
- `http://localhost:3016/research` — `/research` 홈이 서고(N5 를 했으면) 기록이 없는 브라우저라 '연구 기록이 없습니다. …' 문구, 사이드바 딥리서치 탭의 빈 문구 아래 '모두 보기'(06e fastapi 배포 전이면 N 없이)
- `http://localhost:3016/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383` — 06b 운영 확인 잡(completed·이어간 연구): 고정 진행 막대 **없음**, 넓은 화면 2단, 옆 칸 맨 위 근거 장부, 머리에 WorkStepper(06e 파일 그대로), 상태 배지 옆 탐색 방식 표시 **없음**(06c 전 잡 — params 에 `broaden`·`query_context` 가 없다)
- `http://localhost:3016/papers` — + 메뉴에서 딥리서치를 고르면 칩 옆에 `탐색 방식` 두 칸이 서고 `정밀하게` 가 골라져 있다, ←→ 로 고른 칸이 바뀐다(Task N9 — 보내지 않는다)
- 콘솔 오류 없음

Expected: 위 다섯. 깨지는 화면이 있으면 그 Task 로 돌아가 고친 뒤 Step 1·2 를 다시 돈다.

- [ ] **Step 4: 영역별 정적 리뷰 — code-reviewer 다섯을 병렬로**

리뷰어에게 줄 diff 를 저장소 밖에 뜬다:

```bash
mkdir -p C:/Users/LANDSOFT/round06d-eval/review
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
BASE=$(git merge-base HEAD dev)
git diff $BASE HEAD -- frontend/utils/researchLayout.ts frontend/utils/researchProgress.ts frontend/utils/synthCard.ts frontend/components/research/ResearchProgressBar.vue frontend/components/research/SynthProgressCard.vue frontend/components/research/ResearchHeader.vue frontend/utils/restorePosition.ts frontend/composables/useRestorePosition.ts "frontend/pages/research/[id].vue" frontend/assets/css/research.css > C:/Users/LANDSOFT/round06d-eval/review/a-layout-bar.diff
git diff $BASE HEAD -- frontend/utils/researchFollow.ts frontend/composables/useSectionFollow.ts "frontend/pages/research/[id].vue" > C:/Users/LANDSOFT/round06d-eval/review/b-follow.diff
git diff $BASE HEAD -- frontend/utils/planSlots.ts frontend/components/research/ReportSkeleton.vue frontend/utils/researchEvents.ts frontend/types/research.ts frontend/components/research/ProgressPanel.vue frontend/utils/evidenceLedger.ts frontend/components/work/EvidenceLedger.vue frontend/assets/css/work.css "frontend/pages/research/[id].vue" > C:/Users/LANDSOFT/round06d-eval/review/c-explore.diff
git diff $BASE HEAD -- frontend/pages/index.vue frontend/components/AppSidebar.vue frontend/types/history.ts frontend/utils/historyStore.ts frontend/utils/historyState.ts frontend/composables/useHistory.ts frontend/utils/sidebarResearch.ts frontend/utils/researchHome.ts frontend/composables/useResearchWorks.ts frontend/pages/research/index.vue frontend/utils/paperResearch.ts frontend/pages/papers/index.vue frontend/utils/addToWork.ts frontend/components/research/AddToWorkMenu.vue frontend/utils/researchMode.ts frontend/components/research/ResearchModePicker.vue frontend/components/research/SearchPlusMenu.vue frontend/composables/useResearch.ts frontend/components/research/ResearchHeader.vue "frontend/pages/research/[id].vue" frontend/assets/css/research.css > C:/Users/LANDSOFT/round06d-eval/review/d-entry.diff
git diff $BASE HEAD -- frontend/tests > C:/Users/LANDSOFT/round06d-eval/review/e-tests.diff
wc -l C:/Users/LANDSOFT/round06d-eval/review/*.diff
```

Expected: 다섯 파일 모두 0 줄이 아니다(N5·N6 를 잘랐어도 d 는 N1~N4 로 0 이 아니다).

`.claude/agents/code-reviewer.md` 서브에이전트(subagent_type `code-reviewer`) 다섯을 **한 번에 병렬로** 띄운다. 각 프롬프트는 아래 공통 머리 + 영역 줄이다.

공통 머리(그대로):

```text
round06d(딥리서치 진행 화면·입구 — nuxt 만) 브랜치의 한 영역을 정적 리뷰한다. 저장소 C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d 의 파일과 아래 diff 파일을 읽는다. 설계 정본은 docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md §12-3·§12-5·§12-6·§12-7 과 D22·D26·D17·Q1·Q9, 이 줄의 결정은 docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md 의 '06d 에서 정한 것'(정함 1~19 — 정함 4·7 은 spec 과 일부러 다르게 읽었다, 정함 19 는 06c 판정 뒤 사용자 결정 spec D28 의 자리·모양, spec 문서는 이 리뷰 뒤 계획 Task Z3 가 맞춘다)과 '공통 계약'. 코딩 표준 docs/standards/coding-standard.md, 반복 함정 docs/ops/recurring-gotchas.md 와 대조한다. 공통으로 본다: ① app/·compose·infra·package.json 을 바꾸지 않았고 06e 파일(WorkStepper.vue·workPhase.ts·researchErrors.ts·useResearchWork.ts·types/work.ts·BookChat.vue·citations.ts)과 PlanCard.vue·CitationChip.vue·ReportView.vue·researchDraft.ts 는 읽기만 한다 ② Nuxt 자동 import — 한 이름은 한 파일만 export 한다(같은 이름을 두 utils·composables 가 내보내지 않는다), utils 는 쓰는 것을 모두 명시해 import 한다 ③ 06a·06b 타입에 더한 필드는 선택(?)이고 새 키는 값이 있을 때만 싣는다(기존 toEqual 픽스처 그대로) ④ 새 움직임(transition·animation·scrollIntoView smooth)은 prefers-reduced-motion 에서 멈추거나 즉시다 ⑤ CSS 는 --skx-* 토큰만 쓰고 새 색값이 없으며 research.css 의 새 블록은 인쇄 앵커 위에, work.css 는 근거 장부 블록 안에만 ⑥ 접근성 — 버튼은 button, 메뉴·진행 막대의 role·aria(aria-valuenow·aria-valuetext·aria-current·aria-haspopup·aria-expanded), 초점 복귀, aria-live 를 남발하지 않는다 ⑦ 화면을 그리는 경로·computed·watch 가 쓰는 요청(POST·PUT·DELETE)을 하지 않는다 — 쓰는 요청은 사용자 클릭 처리기에서만 ⑧ 순수 함수가 받은 객체를 고치지 않는다. 보고는 code-reviewer 형식(severity·location·issue·suggestion), 읽은 근거만.
```

영역 줄(공통 머리 뒤에 하나씩):

```text
[A 2단·큰 진행 막대·오프셋·스타일] diff: C:/Users/LANDSOFT/round06d-eval/review/a-layout-bar.diff. 파일: frontend/utils/researchLayout.ts, researchProgress.ts, synthCard.ts, components/research/ResearchProgressBar.vue, SynthProgressCard.vue, ResearchHeader.vue, utils/restorePosition.ts, composables/useRestorePosition.ts, pages/research/[id].vue(배치·barView·roundKey·useNow·progressInset), assets/css/research.css(토큰·.rs-pbar*·옛 .rs-synth__bar 지움·문서 scroll-padding-top·옆 칸 top·머리·옆 칸 카드 머리·인쇄). 특히: 넓은 화면은 처음부터 A 이고 override 를 푸는 watch·localStorage 기억이 없는지(2e3d87a 를 revert 하지 않고 앞으로 고쳤는지), progressBarView 의 글줄이 계획의 표(planning·awaiting·queued·exploring·synthesizing)와 글자 그대로인지, 퍼센트가 두 구간 가중(111:91)으로 작성 시작 때 뒤로 가지 않고 RUNNING_CAP 0.9 를 넘지 않는지, 막대가 completed·failed·canceled·stepMode 에서 서지 않는지(WorkStepper 와도, 06e 보고서 단계 화면의 자기 막대 .wk-rbar — 10-11 사용자 확인·06e 계획 정함 28 — 와도 한 화면에 함께 서지 않음. 06d 가 .wk-rbar·--wk-bar-thick·reportBar 를 만들거나 고치지 않았고, Q1 치수 값 1rem·0.75rem·1rem·1.25rem 이 --rs-bar-thick 쪽에 그대로인지), 막대 높이 하나(:root 의 --rs-bar-area-h → .rs-page 의 --rs-bar-h)를 옆 칸 top·문서 scroll-padding-top(html:has(.rs-page.has-progressbar) — 키보드 초점 이동이 막대 뒤에 가린 요소로 가지 않게, WCAG 2.2 2.4.11)·위치 복원 inset 이 함께 읽고, 막대 높이가 .rs-section scroll-margin-top(1.2rem 그대로)에 두 번 더해지지 않았는지, useNow 가 exploring 에도 켜지는지, 인쇄에서 .rs-pbar 가 숨는지, 현황 카드에 작은 막대가 남지 않고 절 목록·[초안 저장]은 그대로인지, 공용 .rs-card__title 규칙은 그대로이고 옆 칸만 .rs-col-side .rs-card__title 로 바꿨는지.
[B 따라가기] diff: C:/Users/LANDSOFT/round06d-eval/review/b-follow.diff. 파일: frontend/utils/researchFollow.ts, composables/useSectionFollow.ts, pages/research/[id].vue(followTargetId·follow·jumpToSection·알약), assets/css/research.css(.rs-follow-pill). 특히: 멈추는 것이 사용자 입력뿐인지(세로 휠·touchmove·FOLLOW_KEYS 입력칸 밖 — 수식 키 조합은 굴리는 Ctrl+Home/End·Cmd+↑/↓·Option+↑/↓ 만·스크롤바 pointerdown — scroll 이벤트로 가르지 않음, 정함 4), 가로 휠·Ctrl+휠·입력칸 안 키·굴리지 않는 수식 키 조합(Ctrl+PageUp/PageDown·Alt+Home·Ctrl/Cmd+Space)은 멈추지 않는지, 막힘(restore.pending·pdf·.rs-page .rs-cite__pop)이면 옮기지 않고 다음 바뀜에 옮기는지(정함 5), 상세에서 돌아온 화면은 멈춘 채 시작하는지(정함 6), 대상이 바뀔 때만 옮기는지(같은 대상으로 되풀이 스크롤 없음), reduced-motion 이면 behavior auto 인지, 창 리스너를 언마운트 때 모두 푸는지(passive·capture 옵션이 걸 때와 풀 때 같은지), nextTick·requestAnimationFrame 뒤 getElementById 가 null 이면 조용히 넘어가는지, 알약 문구(작성 '↓ 지금 쓰는 곳으로'·탐색 '↓ 지금 찾는 곳으로')와 누르면 곧바로 옮기는지, work.css 의 .wk-pill 을 고치지 않았는지.
[C 탐색 중 움직임] diff: C:/Users/LANDSOFT/round06d-eval/review/c-explore.diff. 파일: frontend/utils/planSlots.ts, components/research/ReportSkeleton.vue, utils/researchEvents.ts(roundStatusLabel·applyCandidates·applyCritique·applySnapshot·buildSubq), types/research.ts, components/research/ProgressPanel.vue, utils/evidenceLedger.ts, components/work/EvidenceLedger.vue, assets/css/work.css(근거 장부 블록), pages/research/[id].vue(planSlotList·slotsShown·ReportSkeleton 분기·탐색 중 PlanCard 지움·옆 칸 순서·questionUsed). 특히: 절 자리의 key·id 가 하위질문 번호이고 절 번호 대응이 synth 이벤트의 subq_idx 를 먼저, 없으면 headings 와 하위질문 글을 NFC·공백 정리 뒤 맞추는지, '종합 시작'과 '대응을 앎'을 나눠 근거를 모은 자리(adopted > 0)는 접지 않는지, draftReport·draftSlots 를 건드리지 않는지, ReportSkeleton 이 completed 의 보고서·실패·로딩 분기와 겹치지 않는지, candidates 리듀서가 subq_idx 로 하위질문을 찾고 빈 papers 는 reviewing 키를 지우되 모르는 번호·reviewing 없는 하위질문이면 같은 view 를 돌려주는지(유령 하위질문 없음), critique·snapshot·판정이 실린 step 과 잡 종료(done·failed·canceled 이벤트, 끝난 잡으로 다시 맞추는 refreshView)가 reviewing 을 지우는지, reviewing 키를 값이 있을 때만 싣는지, 장부의 검토 중이 채택 더미와 겹치지 않고 뺌 더미에 두지 않는지, 알림이 announceSeq 방식으로 한 번만 나는지, wk-review 가 reduced-motion 에서 멈추는지, 장부가 옆 칸 맨 위인지, "이렇게 이해했어요" 가 06c 의 questionUsedFromSteps·understoodLine 을 쓰고 같은 이름을 06d 가 따로 만들지 않았는지(접두를 템플릿에 다시 쓰지 않음), roundStatusLabel 이 subqStatusLabel 을 바꾸지 않았는지.
[D 입구] diff: C:/Users/LANDSOFT/round06d-eval/review/d-entry.diff. 파일: frontend/pages/index.vue, components/AppSidebar.vue, types/history.ts, utils/historyStore.ts, utils/historyState.ts, composables/useHistory.ts, utils/sidebarResearch.ts, utils/researchHome.ts, composables/useResearchWorks.ts, pages/research/index.vue, utils/paperResearch.ts, pages/papers/index.vue, utils/addToWork.ts, components/research/AddToWorkMenu.vue. 특히: 문구가 '소장자료검색'·'소장자료'로 맞고 kind(book)·주소·/search-classic 은 그대로인지, total 이 없는 응답(06e 전 서버)에서 null 로 받아 '모두 보기' 만 그리는지, 로컬로 물러난 목록이 알던 total 을 지우지 않는지, remove·clear 의 total 조정, 모두 보기가 기록이 없어도(빈 문구 아래) 서는지, 사이드바 단계 줄이 workPhase.stepLine 을 쓰고 단계 이름 문자열을 새로 쓰지 않는지, 폴링 조건(isLiveResearch)이 진행 중 생성을 포함하는지, /research 홈이 history 를 50건씩 읽고 [더 보기]가 before 커서를 쓰는지, 예시 연구의 실행 시각(corpus.at KST)·범위(scopeLine)·읽기 전용 표시, 새 연구 시작의 429 browser_active 링크(방어 — 지금 서버는 만들기에서 429 를 내지 않고 승인·재시도에서 낸다), [딥리서치로 더 깊게]가 바로 시작하지 않고 ?draft= 로 입력창만 채우는지(길이 검사 questionProblem), [담기]가 PUT reading {"state":"in"} 이고 이어간 연구가 없으면 D17 문구 그대로인지, 담은 뒤 useHistory().refresh("research") 를 기다리지 않고 부르는지, 메뉴의 Esc·바깥 클릭·초점 복귀, 결과 카드 버튼 줄의 기존 버튼과 BookChat(:564-569) 자리를 건드리지 않았는지. 탐색 방식(Task N9 — 정함 19, 파일: utils/researchMode.ts, components/research/ResearchModePicker.vue·SearchPlusMenu.vue·ResearchHeader.vue, composables/useResearch.ts, pages/research/index.vue 의 새 연구, pages/research/[id].vue 의 modeLine·onRestart, research.css 의 .rs-mode*·.rs-head__meta·.rs-head__mode): 딥리서치를 시작하는 곳(startResearch 를 부르는 곳 모두)이 두 칸(broaden·query_context)을 함께 싣는지 — 폭넓게 {0,0}·정밀하게 {1,1}, 기본 정밀하게, query_context 만 싣는 길이 없는지, 다시 시작이 원래 잡의 두 칸을 잇고 두 칸이 없는 잡은 기본인지, 머리 표시가 두 칸 다 0 이면 폭넓게·두 칸이 없거나 갈리면 그리지 않는지, radiogroup 접근성(role·aria-checked·aria-labelledby·aria-describedby·roving tabindex·방향키·Home·End·선택이 초점을 따름)과 칸의 키가 SearchPlusMenu 의 캡처 리스너(입력창 엔터·.skx-send)에 걸리지 않는지, localStorage(skx_research_mode)를 try/catch 로 읽고 쓰며 서버 렌더와 첫 그림이 같은지(마운트 뒤 읽음)·레이아웃 기억(skx_research_layout)을 되살리지 않았는지, 고르기·기억이 서버에 쓰지 않는지(쓰는 요청은 보내기 클릭의 startResearch 뿐), ModeParams 가 ResearchParams 로 넘어가는지.
[E 테스트] diff: C:/Users/LANDSOFT/round06d-eval/review/e-tests.diff. 파일: frontend/tests/unit/ 의 새 일곱 파일(researchProgress·planSlots·researchFollow·sidebarResearch·researchHome·addToWork·researchMode)과 고친 파일(researchLayout·queueLine·researchEvents·restorePosition·evidenceLedger·historyStore·historyState·paperResearch). 특히: 새 판단마다 실패 테스트가 먼저 있는지(TDD — 커밋 순서), spec §12-7 06d vitest 목록(배치·그리는 조건·진행 비율·따라가기 켜고 끄기·절 자리와 headings 대응·회차 미세 상태·후보 더미·큰 막대 글줄)이 모두 덮였는지, 기대값을 06e 함수(stepLine·stepForPhase·scopeLine)의 출력으로 만들어 06e 의 문구 바꾸기에 깨지지 않는지, 기존 toEqual 픽스처를 고친 곳이 evidenceLedger 의 reviewing 두 곳과 queueLine 다시 내보내기 테스트뿐인지, 대역(fakeFetcher·helpers/fakeHistory·memoryStorage)을 새로 만들지 않고 썼는지, DOM·타이머에 기대는 테스트가 없는지(node 환경), researchDraft.test.ts 를 고치지 않았는지.
```

Expected: 리뷰어마다 요약 1~2문장 + 결함 목록(없으면 "없음"). 다섯 보고를 영역·severity 별로 한 표로 모은다(완료노트 §3 의 재료).

- [ ] **Step 5: 발견을 반영하고 리뷰를 마친 커밋을 적는다**

- severity high·medium 은 모두 고친다. low 는 고칠지 판단하고, 고치지 않으면 까닭을 적는다(완료노트 §3). 리뷰어끼리 엇갈리거나 계획의 결정(정함 1~19)과 다른 제안은 고치기 전에 그 결정의 근거와 견주고, 결정을 바꿔야 하면 사용자에게 묻는다.
- 판단을 바꾸는 수정은 그 순수 함수의 실패 테스트를 먼저 쓰고(실행해 실패 확인) 고친 뒤 통과를 본다. `.vue`·`.css` 만의 수정은 typecheck `0`·build 완료로 확인한다. 커밋은 발견 묶음마다 `[Fix] round06d — <무엇을 왜>` 로, `git add` 는 파일을 하나씩 적는다.
- 다 고친 뒤 Step 1·Step 2 를 그대로 다시 돌린다. Expected: Step 1 의 vitest 수는 리뷰 반영으로 더한 테스트만큼 크고 나머지는 같다, Step 2 의 출력은 같다(고친 파일 목록에 새 파일이 들었으면 그 까닭이 적혀 있다).
- 그 뒤 고친 것만 해당 영역 리뷰어에게 다시 보인다(같은 공통 머리 + "앞 리뷰의 발견을 고친 diff 다 — 회귀가 없는지 본다", diff 는 `git diff <반영 전 커밋> HEAD`). 새 발견이 없을 때까지 되풀이한다(최대 3회 — 넘으면 남은 발견을 사용자에게 보인다).

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d rev-parse --short HEAD
```

Expected: 커밋 해시 한 줄 — '리뷰를 마친 커밋'으로 적어 둔다(완료노트 머리·§3, Task Z4 의 승인 요청).

---

### Task Z2: 06c 판정 연계 — 랜딩 논문 예시 셋을 판정 결과로 다시 본다

**왜:** spec §12-5·§12-7 "랜딩 논문 예시 셋(`pages/index.vue` — 06d 파일)은 06c 판정 질문과 같은 문장이다. 06c 판정 뒤 다시 확인하고, 바꿀 것이 있으면 06d 가 고친다." 06c 의 두 갈래 판정(10/13~14)은 이 셋(`library`·`elderly`·`multicultural`)을 갈래 0(지금 방식)·갈래 1(넓히기·검색어 합성)로 돌려 질문별 보고서 정밀도와 기본값 결정(Q4)을 06c 완료노트 §5-4·§5-5 에 남긴다. dev 머지 전에 그 기록으로 판단하고(이 Task), 기본값을 켠 운영에서 실제 보고서를 다시 보는 것은 배포 뒤 Task Z6 Step 5 가 한다.

**Files:**
- Modify(바꿀 때만): `frontend/pages/index.vue`(`SUGGESTIONS.paper` 의 그 문장 한 줄과 그 위 주석의 정밀도 수 — da80f23 `:673-674`·`:681-685`)

**알아 둘 것:**
- 판단 규칙: 06c 가 켠 기본값의 갈래(둘 다 0 이면 갈래 0 — 랜딩 예시의 결과는 06b 때와 같은 방식이라 바꿀 까닭이 없다)에서 그 질문의 보고서 정밀도가 **같은 날 갈래 0 보다 낮으면** '떨어짐'이다. 떨어진 질문이 없으면 고치지 않는다. 
- **2026-10-12 판정 결과 — 어느 갈래로 볼지 먼저 사용자에게 묻는다:** 서버 기본값은 둘 다 0(갈래 0)이지만 화면의 기본 선택은 탐색 방식 '정밀하게'(= 갈래 1 — Task N9·정함 19)라, 랜딩 예시를 누른 사람은 기본 선택을 바꾸지 않으면 갈래 1 의 결과를 본다. 06c 완료노트 §5-5 가 이 판단을 06d 에 넘겼다 — 갈래 1 로 보면 본 실행에서 `library` 가 같은 날 갈래 0 보다 낮다(93.3% → 84.6%, `elderly`·`multicultural` 은 낮지 않다), 단독 실행은 셋 모두 낮다(06c 완료노트 §7-10). Step 3 에 들기 전에 이 두 갈래의 값을 보이고 어느 쪽으로 판단할지 묻는다. 
- 바꿀 문장은 사용자가 정한다. 후보는 2026-10-08 랜딩 예시를 고른 방식(운영 검색 API 로 상위 결과를 보고 판정자 둘 이상이 따로 확인 — `89cede3` 커밋 설명)으로 확인한 문장만 낸다 — 06c 판정·대조군에서 정밀도가 높았던 문장이 먼저다. 이 Task 는 새 후보를 찾는 조사를 하지 않는다(필요하면 사용자에게 그 조사를 따로 제안한다).

- [ ] **Step 1: 06c 판정 기록이 dev 에 있는가**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI show dev:docs/roadmap/round06c-완료노트.md | grep -nE "^### 5-4|^### 5-5|broaden|query_context" | head -20
```

Expected: `### 5-4. 두 갈래 재판정`·`### 5-5. 결정 커밋` 줄과 기본값(`broaden` <0|1> · `query_context` <0|1>)이 적힌 줄. `fatal: path … does not exist` 이거나 §5-4 가 없으면 06c 의 배포·판정 기록이 아직 dev 에 없다 — 이 Task 를 멈추고 기다린다(06d 의 dev 머지는 어차피 06c 운영 배포 뒤다 — Task Z4).

- [ ] **Step 2: 질문별 표를 읽는다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI show dev:docs/roadmap/round06c-완료노트.md | sed -n '/^### 5-4/,/^### 5-5/p' | grep -nE "library|elderly|multicultural|정밀도|판정"
```

Expected: 세 질문 키마다 같은 날 갈래 0·갈래 1 의 보고서 정밀도가 든 줄(06c 계획의 판정 표 — '06b 참고 · 같은 날 갈래 0 · 갈래 1')과 판정 줄. 세 질문의 두 값과 결정된 기본값을 적어 둔다(완료노트 §6 끝 '06c 판정 연계' 줄 — Task Z3).

- [ ] **Step 3: 판단하고 — 떨어진 질문이 없으면 여기서 끝낸다**

- 기본값이 둘 다 0 이거나, 켠 갈래에서 세 질문 모두 같은 날 갈래 0 이상이면: **고치지 않는다.** 완료노트 §6 끝에 `06c 판정 연계(Task Z2): 랜딩 논문 예시 셋 — 확인함, 그대로(library … · elderly … · multicultural …)` 를 적는다(Task Z3 가 쓴다). 이 Task 는 커밋이 없다.
- 떨어진 질문이 있으면: 그 질문·두 값·까닭을 사용자에게 보이고 "바꿀지, 무엇으로 바꿀지" 를 묻는다. 사용자가 그대로 두기로 하면 위와 같이 적고 끝낸다. 바꾸기로 하면 Step 4.

- [ ] **Step 4: (바꾸기로 했을 때만) 그 한 줄과 주석을 고친다**

`frontend/pages/index.vue` — `SUGGESTIONS` 의 `paper:` 배열 안에서 바꿀 문장 한 줄을 Edit 한다. 예: `공공도서관` 문장을 바꿀 때 old 는

```ts
    "공공도서관 서비스 품질 평가 연구가 궁금해",
```

이고 new 는 같은 들여쓰기(4칸)·큰따옴표·끝 쉼표로 사용자가 정한 문장 한 줄이다. 그 위 주석(앵커 `// 보고서 정밀도가 높았던 질문(노인 우울 95%·다문화 아동 75~100%·공공도서관 82~86%)을 그 문장 그대로 쓴다`)의 괄호 안에서 바꾼 질문의 이름과 정밀도를 06c 판정(또는 새 문장을 확인한 조사)의 값으로 바꾼다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && sed -n '/^  paper: \[/,/^  \],/p' pages/index.vue
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d/frontend && npm run build 2>&1 | tail -1
```

Expected: `paper: [` 와 문장 세 줄·`],` — 바꾼 한 줄만 새 문장, typecheck `0`, `└  ✨ Build complete!`.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add frontend/pages/index.vue && git status --short && git commit -m "[Fix] round06d — 랜딩 논문 예시 「<바꾼 문장>」 을 「<새 문장>」 으로 바꾼다 — 06c 두 갈래 판정에서 켠 기본값(broaden <0|1> · query_context <0|1>)으로 이 질문의 보고서 정밀도가 같은 날 갈래 0 보다 낮았다(<갈래 0 값> → <켠 갈래 값>, 06c 완료노트 §5-4). 새 문장은 <확인한 방법 — 예: 06c 판정·대조군에서 정밀도 n% 였던 질문, 사용자 결정 날짜>. 예시 칩은 누르면 입력창에만 채우고 논문은 + 메뉴로 딥리서치를 시작할 때도 쓰인다"
```

꺾쇠 자리는 모두 실제 값으로 바꿔 쓰고 꺾쇠를 남기지 않는다. Expected: `git status --short` 에 `M  frontend/pages/index.vue` 한 줄, 커밋 1개. 이 수정이 리뷰 뒤라 Task Z1 Step 1 의 typecheck·vitest·build 를 한 번 더 돌린다(vitest 수는 같다).

---

### Task Z3: 문서 — 완료노트(배포 전)·00_status·spec 맞춤·반복 함정 판단

**왜:** D13(하위 라운드마다 완료노트), CLAUDE.md §3("문서와 코드가 어긋나면 코드가 실제이니 문서를 고친다"). 06d 는 spec 과 다르게 읽은 것(정함 4 — 따라가기 멈춤을 입력 이벤트로, 정함 7 — 탐색 중 알약 문구)과 spec 이 둘 중 하나로 둔 것(정함 8 — `ReportSkeleton.vue`), §12-11 에서 정한 것(정함 9·18)이 있다 — dev 머지 전에 spec 을 코드에 맞춘다. 배포·운영 확인 결과(§5)는 Task Z7 이 채운다.

**Files:**
- Create: `docs/roadmap/round06d-완료노트.md`
- Modify: `docs/roadmap/00_status.md`(3행 최종 갱신·round06 머리·round06 하위 줄 끝·다음 할 일의 06d 줄·라운드 이력의 round06 칸 — round06 줄만)
- Modify: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`(머리 상태 줄, D22·D26 행, §12-3 '지금 진행하는 절 따라가기'·'탐색 중 절 자리'·'오프셋' 행과 입구의 '탐색 방식' 줄, §12-11 두 항목)
- `docs/ops/recurring-gotchas.md` — 이 Task 에서는 고치지 않는다(운영 전이라 라이브에서만 드러난 것이 아직 없다. Task Z7 이 다시 판단한다)

**알아 둘 것:**
- 기존 문서는 **Edit 도구로** 고친다(모두 CRLF). 아래 old 는 `c5d05b0`(spec 브랜치) 글자 그대로다. 06c·06e 의 문서 커밋이 L6·N8 로 이 브랜치에 들어와 같은 줄을 먼저 고쳤으면 old 가 맞지 않는다 — 그때는 지금 줄을 바탕으로 같은 구절만 넣는다(아래 각 항목에 그 규칙을 적었다).
- `00_status.md` 는 round06 에 관한 줄만 고친다(3행은 모든 라운드가 함께 고치는 줄 — 06d 구절만 넣는다).
- 날짜는 이 Task 를 하는 날로 쓴다(아래 예는 계획 일정의 2026-10-16).
- 입구 구절은 자른 Task 에 따라 셋 중 하나를 쓴다 — **(가)** N5·N6 를 다 했다 · **(나)** N6 만 잘랐다 · **(다)** N5·N6 를 잘랐다(N7 을 했다). 아래 문서마다 (가)(나)(다) 글을 적었다.

- [ ] **Step 1: 완료노트를 쓴다 (`docs/roadmap/round06d-완료노트.md`, 새 파일)**

꺾쇠 자리는 Task Z1·Z2 에서 실측·판단한 값과 이 Step 을 하는 날로 바꿔 쓰고 꺾쇠를 남기지 않는다 — 다 쓴 뒤 `grep -c '<[^>]*>' "docs/roadmap/round06d-완료노트.md"` 가 `0` 이다(이 노트에는 HTML 태그 꼴 글을 쓰지 않는다 — 부품 이름은 꺾쇠 없이 쓴다). §5 는 배포 뒤 Task Z7 에서 채운다.

```markdown
# round06d 완료노트

날짜: <이 Step 을 하는 날, 예: 2026-10-16> (계획 2026-10-08 · 구현·리뷰 <구현을 시작한 날>~<Task Z1 을 마친 날> · `dev` 머지·운영 배포·처음부터 끝까지 1회는 §5)
브랜치: `feat/round06d-research-progress-screen` (worktree `.worktrees/round06d`, dev `<Task 0 Step 2 의 dev 커밋 7자리>` 에서 분기 · 커밋 <git rev-list --count 그 커밋..HEAD 의 수>개 · 리뷰를 마친 커밋 `<Task Z1 Step 5 의 커밋>`)
spec: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` (D22·D26·D17·D28, §12-3·§12-5·§12-6·§12-7, Q1·Q8·Q9)
plan: `docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md` (Task 0 · D1~D8 · L1~L6 · N1~N9 · Z1~Z7, 정함 1~19)
교본: 대회 뒤 round06 한 권(D13) — 06d 는 그 책의 한 장이 된다

> 한 줄 요약: 딥리서치 진행 화면을 움직이게 했다 — 넓은 화면은 처음부터 2단, 위에 고정한 큰 진행 막대 하나(단계 표시·큰 글줄·퍼센트, 탐색 중에도 같은 막대), 지금 진행하는 절을 스크롤이 따라가고 사용자가 스크롤하면 멈추고 알약을 띄운다. 탐색 중에는 본문에 하위질문별 절 자리가 서고, 진행 패널 회차 줄에 '자기점검 중'·'재검색 중'이 붙고, 06c 후보 이벤트로 근거 장부에 '검토 중' 후보가 섰다가 점검 뒤 채택·뺌으로 옮겨 간다. 입구는 <입구 한 구절 — (가) '/research 홈(새 연구·진행 중·내 연구·예시 연구)·사이드바 단계와 모두 보기 (N)·빠른검색 [딥리서치로 더 깊게]·[담기 ▾]·소장자료검색 문구' (나) '/research 홈·사이드바 단계와 모두 보기 (N)·빠른검색 [딥리서치로 더 깊게]·소장자료검색 문구([담기]는 미룸)' (다) '사이드바 단계와 예시 연구 묶음·빠른검색 [딥리서치로 더 깊게]·소장자료검색 문구(/research 홈·[담기]는 미룸)'>. 딥리서치를 시작하는 자리에는 '탐색 방식'(폭넓게 · 정밀하게, 기본 정밀하게 — 06c 판정 뒤 사용자 결정 D28)을 두어 고른 방식을 잡 params 두 칸으로 싣는다. nuxt 만 — 백엔드·스키마 변경은 없다.

---

## 1. 왜 했나

- **"인터랙티브·다이내믹, 진행이 뿅뿅 보이게"** — 10-08 회의 뒤 결정(D22). 실행 202초(탐색 111 + 종합 91) 의 절반 이상 동안 본문에는 읽기 전용 PlanCard 하나뿐이었다(`round06a-완료노트.md:95`). 09-28 "A 가 덜 인터랙티브" 가 B 로 바꾼 이유였으므로 A 로만 되돌리지 않고 움직임을 함께 넣었다.
- **큰 진행 막대(Q1)** — 사용자 "현재 절 작성 중에 보여지는 커다란 프로그레스바 필요, 시안의 막대는 너무 작음"(10-08). 탐색 중에도 같은 막대를 쓰는 것은 Claude 해석이다. 10-11 사용자 확인("보고서 화면에도 넣으라고 한 것이 맞아")으로 06e 자동 보고서 화면에도 같은 치수의 막대가 선다 — 그 막대는 06e 가 만들었고(06e 계획 정함 28), 06d 막대는 단계 화면에 서지 않아 겹치지 않는다.
- **입구(D26)** — 대회에서 직접 써 볼 전문가가 예시 연구에 닿는 길, 사이드바에서 이어간 연구의 단계를 보는 것, 빠른검색에서 딥리서치로 넘어가는 길(D17), '도서검색' → '소장자료검색'.
- **06b 이월** — §7-1 대기 카드 `.rs-card--wait` 가로 배치, §7-5 `queueLine` 다시 내보내기 경고. 06c 의 "이렇게 이해했어요" 바인딩 두 곳(spec §12-5).
- **탐색 방식(D28)** — 06c 두 갈래 판정은 미리 정한 규칙으로 두 스위치 모두 0 이었고(보고서 정밀도는 올랐지만 관련 편수·insufficient·대조군 미달), 사용자가 "응 넣자. 정확하게로 가자. 탐색 방식: 폭넓게 · 정밀하게 로 가자" 로 정했다(2026-10-12). 서버 기본값은 0 그대로라 화면이 고른 방식을 잡 params 로 실어야 켜진다.

---

## 2. 한 일

| 영역 | 한 것 |
|---|---|
| 배치 | 넓은 화면은 처음부터 2단(A), 좁은 화면은 B — round04c `2e3d87a` 를 앞으로 고침(revert 아님, localStorage 기억은 되살리지 않음). [문서형으로 보기] 토글 그대로 |
| 큰 진행 막대 | 새 `ResearchProgressBar.vue`·`utils/researchProgress.ts` — 단계 표시(계획·근거 수집·보고서 작성·완료), 큰 글줄('근거 수집 중 · 하위질문 k/n — 「…」'·'보고서 작성 중 · i/n절 — 「…」'), 퍼센트(탐색 111 : 작성 91 가중, 상한 0.9), 끝나지 않은 잡에만·단계 화면과 인쇄에서는 없음. 현황 카드의 작은 막대는 걷었다. 토큰 `--rs-bar-thick`·`--rs-bar-h`, 옆 칸·절 이동·돌아온 자리를 막대 높이만큼 내림 |
| 절 따라가기 | `utils/researchFollow.ts`·`useSectionFollow` — 종합 중 쓰는 절, 탐색 중 도는 하위질문의 절 자리를 따라간다. 세로 휠·터치·스크롤 키·스크롤바 누르기면 멈추고 '↓ 지금 쓰는 곳으로'(탐색 중 '↓ 지금 찾는 곳으로') 알약. 위치 복원 중·원문 뷰어·인용 팝오버면 옮기지 않음, 움직임 줄이기면 즉시 |
| 탐색 중 절 자리 | `utils/planSlots.ts`·`ReportSkeleton.vue` — 하위질문마다 자리('대기'·'근거 수집 중 · n회차'·'근거 N편 ✓'·'이 절을 쓰는 중'·'근거 없음'·'오류'), 절 번호 대응은 synth 이벤트의 하위질문 번호를 먼저·없으면 절 제목과 하위질문 글. 탐색 중 읽기 전용 PlanCard 를 대신한다 |
| 근거 수집 단계 | 진행 패널 회차 줄의 '자기점검 중'·'재검색 중'(`roundStatusLabel`) |
| 검토 중 후보(Q9) | SSE `candidates` → `SubqView.reviewing?` → 근거 장부 세 번째 묶음 '검토 중'(흐린 카드·반짝임), 점검이 오면 채택은 떨어지고 뺀 것은 가라앉음, 다음 회차 후보·빈 후보가 갈음, 재접속·스냅숏이면 없음. 장부를 옆 칸 맨 위로 |
| 06c 바인딩 | 계획 중 카드와 승인 대기 PlanCard 에 "이렇게 이해했어요" 한 줄(06c 의 `questionUsedFromSteps`·`understoodLine` — 06c 머지 `<Task L6 이 받은 dev 커밋 7자리>`) |
| 입구 | <(가) '/research 홈(새 연구 시작·진행 중·내 연구·[더 보기]·예시 연구 — 읽기 전용·실행 시각·코퍼스 범위), 사이드바 이어간 연구 줄 단계(workPhase.stepLine + 수 + 생성 중)·진행 중 생성 폴링·모두 보기 (N)(N = 06e 의 total, 없으면 N 없이), 논문 빠른검색 답 끝 [딥리서치로 더 깊게](?draft= → 입력창에 딥리서치 칩과 함께), 결과 카드 [담기 ▾](이어간 연구 고르기 → PUT reading {"state":"in"})' (나) (가)에서 [담기 ▾] 를 뺀 글 + '[담기] 는 자름(§7)' (다) '사이드바 이어간 연구 줄 단계·진행 중 생성 폴링·딥리서치 탭 맨 아래 예시 연구 묶음(모두 보기는 그리지 않음), [딥리서치로 더 깊게], /research 홈·[담기] 는 자름(§7)'> |
| 문구 | 랜딩 '도서검색' → '소장자료검색'·낭독·입력창 안내, 사이드바 기록 탭 '도서' → '소장자료'(빈·지우기 문구 포함). kind·주소·`/search-classic` 그대로 |
| 탐색 방식(D28) | `utils/researchMode.ts`·새 `ResearchModePicker.vue`(radiogroup — 방향키·Home·End, 고른 칸만 Tab) — + 메뉴의 딥리서치 칩 옆과 `/research` 홈의 새 연구(N5 를 잘랐으면 '과 `/research` 홈의 새 연구' 를 지운다)에 '탐색 방식' 두 칸(폭넓게 `broaden` 0·`query_context` 0 · 정밀하게 둘 다 1, 기본 정밀하게), 고른 방식을 잡 params 두 칸으로 늘 함께 싣는다(`startResearch(question, params)`), 기억은 localStorage `skx_research_mode`(편의 — 읽지 못하면 정밀하게), [같은 질문으로 다시 시작]은 원래 잡의 두 칸을 잇고, 연구 화면 머리의 상태 배지 옆에 그 잡의 방식(두 칸 다 0 → 폭넓게, 두 칸이 없는 06c 전 잡은 표시 없음). 백엔드 그대로 |
| 06b 이월 | `queueLine` 다시 내보내기 지움(`WARN Duplicated imports` 0), 대기 카드 글 세로 배치 |
| LNB 접기 | <N8 을 했으면 '06e 가 먼저 머지돼 딥리드 패널이 열리면 연구 화면 사이드바를 접는다(`[id].vue` 두 곳 — 06e 의 workPanelOpen 을 읽기만)', 건너뛰었으면 '06d 가 먼저 머지 — 06e 가 늦게 머지하며 단다(§7)'> |

nuxt 만 — `app/`·compose·인프라·패키지는 그대로다. 고치지 않은 부품: WorkStepper·PlanCard·CitationChip·ReportView·BookChat·`researchDraft`·`workPhase`·`researchErrors`·`useResearchWork`·`citations`·`/search-classic`, `[id].vue` 의 06e 단계 본문.

---

## 3. 리뷰

작업마다 구현 → spec 준수 → 품질 검토를 돌렸고, 끝에 영역 다섯(2단·큰 진행 막대·오프셋·스타일 / 따라가기 / 탐색 중 움직임 / 입구 / 테스트)의 정적 리뷰(`.claude/agents/code-reviewer.md`)를 병렬로 돌렸다. <영역별 발견 수(high·medium·low)와 반영 커밋 수·주요 수정 — 예: 'medium 3 · low 6, 수정 4커밋: …'>. <고치지 않은 발견과 까닭, 없으면 '거절한 발견 없음'>. 넘긴 것은 §7.

---

## 4. 검증

- 프론트 vitest <Task Z1 Step 5 의 파일 수>파일 <수> · `nuxi typecheck` 오류 0 · `Duplicated imports` 0 · `npm run build` 완료(<이 Step 을 하는 날>, dev 머지 전 — 기준선 40파일 732). 06d 묶음 <열여덟|열일곱> 파일 <수>(기준선 열한 파일 299), `researchDraft.test.ts` 23 그대로.
- 백엔드 pytest `5 failed, <Task Z1 Step 5 의 N> passed, 1 skipped, 2 warnings, 1 error` — 06d 는 `app/` 을 바꾸지 않았다(받은 dev 의 수). 실패 5·오류 1 은 Task 0 기준선과 같은 로컬 의존성 파일.
- 경계: 고친 파일은 `frontend/` 의 <수>개뿐, 고치지 않을 파일(백엔드·compose·인프라·패키지·06e 파일·PlanCard·CitationChip·ReportView·researchDraft·search-classic) diff 없음, `[id].vue` 의 06e 단계 본문 그대로, `work.css` 는 근거 장부 블록 안만, 새 색값 0, 커밋 트레일러 0.

---

## 5. `dev` 머지·운영 배포

배포 전 — 계획 Task Z4~Z6 의 결과를 Task Z7 의 기록 브랜치에서 채운다.

---

## 6. 결정

| # | 결정 |
|---|---|
| 정함 1 | 진행 막대 하나 = 두 구간 가중 전체 진행(탐색 111 : 작성 91), 퍼센트는 내림 정수, 계획·승인 대기·대기열은 퍼센트 없이 |
| 정함 2 | 탐색 비율 = 하위질문 몫의 평균, 도는 하위질문은 점검이 끝난 회차 + 열린 회차의 다가감(반감기 6초) ÷ (max_recheck + 1), 상한 0.9. 열린 회차의 시작은 화면이 처음 본 시각 |
| 정함 3 | 고정 진행 영역의 높이는 토큰 `--rs-bar-h` 로 고정, 오프셋이 모두 그 값을 읽는다 |
| 정함 4 | 따라가기를 멈추는 것은 사용자 입력뿐(세로 휠·터치 이동·스크롤 키·스크롤바 누르기) — spec 의 '프로그램 스크롤은 플래그로 거른다' 를 이것으로 갈음했다(Claude 해석 — §12-3 을 맞췄다) |
| 정함 5 | 막힘 = 위치 복원 중·원문 뷰어·열린 인용 팝오버(고정·hover 가리지 않음) |
| 정함 6 | 상세에서 돌아온 화면은 따라가기를 멈춘 채 시작, 현황 카드에서 절을 누르면 멈춤. 화면을 연 순간의 대상은 기준으로만 삼고 다음 바뀜부터 옮긴다(탐색이 시작될 때 첫 하위질문 자리로는 옮기지 않는다) |
| 정함 7 | 알약 — 작성 중 '↓ 지금 쓰는 곳으로', 탐색 중 '↓ 지금 찾는 곳으로'(Claude 해석 — §12-3 을 맞췄다) |
| 정함 8 | 탐색 중 절 자리는 새 `ReportSkeleton.vue`(ReportView 자리 모드 아님), 자리 머리는 '하위질문 N' |
| 정함 9 | §12-11 — 탐색 중 읽기 전용 PlanCard 를 절 자리가 대신한다, 옆 칸 폭 17rem 그대로(정함(권고)) |
| 정함 10 | 근거 장부를 옆 칸 맨 위로 |
| 정함 11 | '검토 중' = `SubqView.reviewing?`, 후보 이벤트가 세우고 점검·스냅숏·판정이 실린 진행 저장과 잡 종료(종료 이벤트·끝난 잡으로 다시 맞추는 `refreshView`)가 지운다, 빈 후보도 갈음(비움) |
| 정함 12 | 회차 미세 상태는 새 `roundStatusLabel`, `subqStatusLabel` 그대로 |
| 정함 13 | 사이드바 단계 줄 = `workPhase.stepLine` + 수 + '생성 중' — 단계 이름을 새로 쓰지 않는다 |
| 정함 14 | '모두 보기 (N)' 의 N = history 목록의 `total`(06e), 없으면 N 없이 |
| 정함 15 | `/research` 홈은 history 를 50건씩 직접 읽는다, 예시 연구의 실행 시각·범위는 `corpus` 에서 |
| 정함 16 | [딥리서치로 더 깊게] = `/papers?draft=` — 입력창에 딥리서치 칩과 함께 채우고 시작하지 않는다 |
| 정함 17 | [담기] = `PUT reading` 본문 `{"state": "in"}` |
| 정함 18 | §12-11 — 입력창 안내와 사이드바 기록 탭도 '소장자료'로 맞춘다, 랜딩 머리·결과 화면 문구는 그대로(정함(권고)) |
| 정함 19 | 탐색 방식(spec D28 — 06c 판정 뒤 2026-10-12 사용자 결정) — 폭넓게 `{broaden 0, query_context 0}` · 정밀하게 `{broaden 1, query_context 1}`, 기본 정밀하게, 화면이 늘 두 칸을 함께 싣는다(서버 기본값 0 그대로). 다시 시작은 원래 잡의 두 칸을 잇고, 머리에 그 잡의 방식을 보인다(두 칸이 없거나 갈리면 표시 없음), 고른 값은 이 브라우저에 기억한다 |

조건부 Task: N5 <했음|자름 — N7 을 했다> · N6 <했음|자름> · N8 <했음 — 06e 머지 `<커밋>` 뒤|건너뜀 — 06d 가 먼저 머지>. 06e 의 history `total`: <06d 배포 때 운영에 있었음 — '모두 보기 (N)'|아직 없음 — '모두 보기' 만, 06e 배포 뒤 N 이 선다>. 06c 판정 연계(Task Z2): <'랜딩 논문 예시 셋 — 확인함, 그대로(…)' 또는 '「…」 → 「…」 로 바꿈(커밋 …, 까닭 …)'>. §12-11 의 '연구 맥락을 반영한 딥리드 첫 화면'(선택)은 하지 않았다. 열린 질문(§12-10)에 06d 가 바꾼 것은 없다.

---

## 디자인 참조

디자인 트랙 미도입 — 시각 디자인 담당이 고칠 수 있게 치수는 `research.css` 의 토큰(`--rs-bar-thick`·`--rs-bar-h`)으로 두었고, 색은 `--skx-*` 토큰만 썼다. Q1 막대 치수(두께 1rem·768px 이하 0.75rem, 큰 글줄 1rem, 퍼센트 1.25rem)는 06e 자동 보고서 화면의 막대(10-11 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아" — 06e `work.css` 의 `--wk-bar-thick`)에도 같은 값으로 있다 — 한쪽을 고치면 다른 쪽도 함께 고친다. 06d 의 막대는 단계 화면에 서지 않으므로 한 화면에 큰 막대는 늘 하나다. 06c 의 스타일 고리 `rs-plan__understood` 에는 규칙을 더하지 않았다(`rs-muted` 로 줄이 맞는다).

---

## 7. 이월

1. **사이드바 시안 묶음·메인 [빠른검색|딥리서치] 모드 토글·도서 숨김·연구 화면 skx 검색바** — 대회 뒤(D26·Q8).
2. **다른 브라우저 이어가기 목록** — 대회 뒤(D4 소유·보안과 함께). [담기] 는 같은 브라우저의 이어간 연구만 고른다.
3. **ETA 표본 섞임** — 06b 이월 §7-1, 리허설 전에 다시 본다.
4. **탐색 남은 시간·회차 시각** — 서버가 회차 시각을 주지 않아 열린 회차의 다가감은 화면이 처음 본 시각부터 센다(정함 2 — 새로고침하면 그 회차는 0 부터). 단계 시각을 step 이벤트에 실으면(대회 뒤, §12-9) 정확해진다.
5. **'검토 중' 더미는 재접속·새로고침에 없다** — 설계대로(Q9). 후보는 스냅숏·rounds 에 저장하지 않는다.
6. **예시 연구** — 리허설(10/23~25)에서 `mark_example.py` 로 지정한 뒤 `/research` 홈(또는 사이드바 예시 묶음)의 실행 시각·범위·읽기 전용을 다시 본다.
7. <자른 Task 가 있으면 한 줄씩 — 예: '[담기 ▾](N6) — 10/16 까지 끝내지 못해 잘랐다(spec §12-6 자르는 순서 1). 대회 뒤.'>
8. <N8 을 건너뛰었으면 'LNB 접기 연결(`[id].vue:3-7` 두 곳) — 06d 가 먼저 머지했으므로 늦게 머지하는 06e 가 단다(06e 의 workPanelOpen).', 했으면 이 줄을 지운다>

---

## 8. 다음 라운드 진입점

- **06d 배포(10/17~18)** — 계획 Task Z4(`dev` 머지) → Z5(nuxt 배포 — 06e·06c 기본값과의 경우 가르기) → Z6(운영 처음부터 끝까지 1회) → Z7(기록).
- **그 뒤** — 10/19~21 운영 확인·수정 → 10/22 대회 배포 → 10/23 동결·리허설(예시 연구 지정·3~5명 동시 사용 — §12-8).

---

## 상태
- [x] code-reviewer 정적 리뷰 통과(발견 사항 반영 완료) — 작업별 · 영역 다섯
- [x] 테스트 green — vitest <수> · typecheck 0 · build · 백엔드 회귀(실패 5·오류 1 기준선 그대로)
- [ ] 수동 스모크 확인 — 운영 처음부터 끝까지 1회(§5)
- [ ] 문서 갱신 — `00_status` · spec (교본은 대회 뒤 round06 한 권 — D13)
- [ ] `dev` 머지 승인
- [ ] `dev→main` 머지 + push 완료
```

- [ ] **Step 2: `docs/roadmap/00_status.md` — round06 줄**

① 3행. 지금 줄의 머리를 본다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && sed -n '3p' docs/roadmap/00_status.md | grep -o '^최종 갱신: [0-9-]* ('
```

Expected: `최종 갱신: 2026-10-NN (` 꼴 한 줄(06c 가 고쳤으면 그 날짜 — Git Bash 의 `cut -c` 는 바이트로 자르므로 한글 줄에는 쓰지 않는다). 그 글자를 old 로 잡고 new 는 날짜를 이 Step 을 하는 날로 바꾼 뒤 괄호 바로 뒤에 06d 구절을 넣는다. 예: old `최종 갱신: 2026-10-14 (` → new

```markdown
최종 갱신: 2026-10-16 (round06d — 진행 화면·입구 구현 완료(처음부터 2단·큰 진행 막대·절 따라가기·탐색 중 절 자리·'검토 중' 후보·입구), `dev` 머지·nuxt 배포 대기. 
```

(new 끝에 공백 하나가 있다 — 줄의 나머지는 그대로 이어진다.)

② round06 머리. old:

```markdown
** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색
```

new:

```markdown
 · 06d 구현 완료·`dev` 머지·nuxt 배포 대기** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색
```

(new 는 공백으로 시작한다 — 앞의 06c·06e 구절 뒤에 붙는다.)

③ round06 하위 줄 끝 — 06d 하위 줄을 round06 블록 맨 끝(다음 최상위 줄 `- **round07 종료**` 바로 앞)에 넣는다. old:

```markdown
- **round07 종료** — 적재 파이프라인 보강(
```

new — (가)(나)(다) 중 하나의 입구 구절로:

```markdown
  - **06d 진행 화면·입구 — 구현 완료** — 브랜치 `feat/round06d-research-progress-screen`(worktree `.worktrees/round06d`, dev 에서 분기), 계획 `docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md`(Task 0 · D1~D8 · L1~L6 · N1~N9 · Z1~Z7). 들어간 것: 넓은 화면 처음부터 2단(round04c `2e3d87a` 를 앞으로 고침), 연구 화면 위에 고정한 큰 진행 막대 하나(Q1 — 단계 표시·큰 글줄·퍼센트, 탐색 111 : 작성 91 가중 전체 진행, 탐색 중에도 같은 막대 — 현황 카드의 작은 막대는 걷음), 지금 진행하는 절 따라가기(사용자 입력이면 멈추고 '↓ 지금 쓰는 곳으로'·'↓ 지금 찾는 곳으로' 알약), 탐색 중 하위질문별 절 자리('근거 N편 ✓' — 탐색 중 읽기 전용 PlanCard 대신), 회차 미세 상태('자기점검 중'·'재검색 중'), 06c 후보 이벤트로 근거 장부 '검토 중' 더미(Q9 — 장부는 옆 칸 맨 위로), "이렇게 이해했어요" 바인딩 두 곳(06c), 딥리서치를 시작하는 자리의 탐색 방식(폭넓게 · 정밀하게, 기본 정밀하게 — D28, 고른 방식을 잡 params `broaden`·`query_context` 두 칸으로), 입구(<(가) '`/research` 홈 — 새 연구·진행 중·내 연구·예시 연구, 사이드바 이어간 연구 줄 단계·모두 보기 (N), 빠른검색 [딥리서치로 더 깊게]·[담기 ▾]' (나) '`/research` 홈 — 새 연구·진행 중·내 연구·예시 연구, 사이드바 이어간 연구 줄 단계·모두 보기 (N), 빠른검색 [딥리서치로 더 깊게] — [담기] 는 자름' (다) '사이드바 이어간 연구 줄 단계·딥리서치 탭 예시 연구 묶음, 빠른검색 [딥리서치로 더 깊게] — `/research` 홈·[담기] 는 자름'>), '소장자료검색'·사이드바 '소장자료' 문구, 06b 이월 §7-1(대기 카드 세로)·§7-5(`queueLine` 다시 내보내기). nuxt 만 — 백엔드·스키마 변경 없음. 배포 절차는 계획 Task Z4~Z6. 상세: `round06d-완료노트.md`.
- **round07 종료** — 적재 파이프라인 보강(
```

④ 다음 할 일의 06d 줄 머리. old:

```markdown
  - **06d 진행 화면·입구(10/17~18 배포 — nuxt 만)** — 브랜치 `feat/round06d-research-progress-screen`.
```

new:

```markdown
  - **06d 진행 화면·입구 — 구현 완료, `dev` 머지·nuxt 배포 대기(10/17~18)** — 계획 `docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md` 의 Task Z4(`dev` 머지, 사용자 승인 — 06c 운영 배포 뒤, 기본 06e 먼저) → Z5(nuxt 배포, 사용자 — 06e 와 함께면 한 번에, 06d 먼저면 nuxt 만 또는 06c 기본값과 함께) → Z6(운영 처음부터 끝까지 1회) → Z7(기록) 순서. 브랜치 `feat/round06d-research-progress-screen`.
```

(줄의 나머지 — 처음부터 2단·… 설명 — 는 그대로 이어진다.)

⑤ 라운드 이력의 round06 칸. 지금 칸의 '남음' 구절에서 06d 를 뺀다. old 가 `· 06d·06e 남음(2026-10-08 재정의 — spec §12) |` 이면 new:

```markdown
· 06d 구현 완료·배포 대기(`feat/round06d-research-progress-screen`) · [완료노트](round06d-완료노트.md) · 06e 남음(2026-10-08 재정의 — spec §12) |
```

06e 가 먼저 기록돼 old 가 `· 06d 남음(2026-10-08 재정의 — spec §12) |` 이면 new 는 `· 06d 구현 완료·배포 대기(\`feat/round06d-research-progress-screen\`) · [완료노트](round06d-완료노트.md) |` 다(06c 가 아직 '06c·06d·06e 남음' 그대로 두었으면 old 를 그 구절로 잡고 `06c·06e 남음` 을 남긴다).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "round06d-완료노트.md" docs/roadmap/00_status.md && grep -c "06d 진행 화면·입구(10/17~18 배포 — nuxt 만)" docs/roadmap/00_status.md && sed -n '3p' docs/roadmap/00_status.md | grep -c "round06d — 진행 화면·입구 구현 완료"`

Expected: `2`(하위 줄의 '상세'·라운드 이력), `0`(옛 다음 할 일 머리가 남지 않았다), `1`.

- [ ] **Step 3: spec 을 코드에 맞춘다 (`docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`)**

① 3행 머리 상태 줄. old:

```markdown
. **06c~06e 는 2026-10-08 시연 회의와 같은 날
```

new:

```markdown
 · 06d 구현 완료(2026-10-16 — 처음부터 2단·큰 진행 막대·절 따라가기·탐색 중 절 자리·'검토 중' 후보·입구, `dev` 머지·nuxt 배포 대기). **06c~06e 는 2026-10-08 시연 회의와 같은 날
```

(06c·06e 가 같은 자리 앞에 구절을 넣었어도 이 old 는 그대로 맞는다 — 06d 구절이 그 뒤에 붙는다.)

② D22 행 — 구현 방식. old:

```markdown
round04b spec 은 고치지 않고 덮는 사실만 여기 남긴다(D13) |
```

new:

```markdown
round04b spec 은 고치지 않고 덮는 사실만 여기 남긴다(D13). **06d 구현:** 큰 진행 막대는 새 `ResearchProgressBar.vue`·`utils/researchProgress.ts`(퍼센트 = 탐색 111 : 작성 91 가중 전체 진행 — 작성 시작 때 뒤로 가지 않는다), 따라가기는 `utils/researchFollow.ts`·`useSectionFollow` — 사용자 입력(세로 휠·터치·스크롤 키·스크롤바)으로만 멈춘다, 탐색 중 절 자리는 새 `ReportSkeleton.vue`·`utils/planSlots.ts`, '검토 중' 더미는 `SubqView.reviewing?` 와 장부의 세 번째 묶음이다(06d 계획 정함 1~18) |
```

③ D26 행 — 입구. old:

```markdown
§9 의 06d 범위를 덮는다 |
```

new — (가)(나)(다) 중 하나:

```markdown
§9 의 06d 범위를 덮는다. **06d 구현:** <(가) '`/research` 홈(새 연구·진행 중·내 연구·예시 연구 — history 를 50건씩 직접 읽고, 예시는 `GET /api/research-works?example=1` + work 의 `corpus`), 사이드바 단계 줄은 `workPhase.stepLine` + 수 + 생성 중, 모두 보기 (N) 의 N 은 history 목록의 `total`(없으면 N 없이), [딥리서치로 더 깊게] = `/papers?draft=`, [담기] = `PUT reading {"state": "in"}`, 문구는 입력창 안내·사이드바 기록 탭까지 소장자료로' (나) (가)에서 '[담기] = …' 를 '[담기] 는 자름(자르는 순서 1)' 으로 (다) '`/research` 홈·[담기] 는 자름(자르는 순서 1·2) — 예시 연구는 사이드바 딥리서치 탭 맨 아래 묶음, 사이드바 단계 줄은 `workPhase.stepLine` + 수 + 생성 중, [딥리서치로 더 깊게] = `/papers?draft=`, 문구는 입력창 안내·사이드바 기록 탭까지 소장자료로'>(06d 계획 정함 13~18) |
```

④ §12-3 '지금 진행하는 절 따라가기' 행 — 정함 4·5·6·7. 세 군데를 Edit 한다.

old:

```markdown
멈추고 '↓ 지금 쓰는 곳으로' 알약을 띄운다(누르면 다시 따라감).
```

new:

```markdown
멈추고 '↓ 지금 쓰는 곳으로'(탐색 중에는 '↓ 지금 찾는 곳으로' — 06d 계획 정함 7) 알약을 띄운다(누르면 다시 따라감).
```

old:

```markdown
프로그램이 일으킨 스크롤은 플래그로 거른다.
```

new:

```markdown
프로그램이 일으킨 스크롤(`scrollIntoView`)은 입력 이벤트를 내지 않으므로 멈추는 것은 사용자 입력(세로 휠·터치 이동·스크롤 키·페이지 스크롤바 누르기)뿐이고 `scroll` 이벤트로 가르지 않는다 — 스크롤 앵커링·절 펼침·위치 붙잡기가 내는 `scroll` 을 플래그로 다 거를 수 없다(06d 계획 정함 4).
```

old:

```markdown
위치 복원 중·원문 뷰어나 고정한 인용 팝오버가 열렸을 때·최종본으로 바뀐 뒤에는 멈춘다.
```

new:

```markdown
위치 복원 중·원문 뷰어나 인용 팝오버(고정·hover 를 가리지 않는다 — `CitationChip.vue` 는 그대로)가 열렸을 때·최종본으로 바뀐 뒤에는 멈추고, 상세에서 돌아온 화면은 따라가기를 멈춘 채 시작한다(06d 계획 정함 5·6).
```

⑤ §12-3 '탐색 중 절 자리' 행의 자리 칸. old:

```markdown
새 유틸 `planSlots(view)` + ReportView 자리 모드 또는 새 `ReportSkeleton.vue`
```

new:

```markdown
새 유틸 `utils/planSlots.ts`(`planSlots(view)`) + 새 `ReportSkeleton.vue`(ReportView 자리 모드는 쓰지 않았다 — 06d 계획 정함 8)
```

⑥ §12-11 두 항목. old:

```markdown
- **탐색 중 읽기 전용 PlanCard**(`[id].vue:97`)를 절 자리가 대신할지, 옆 칸 폭(17rem).
```

new:

```markdown
- ~~**탐색 중 읽기 전용 PlanCard**(`[id].vue:97`)를 절 자리가 대신할지, 옆 칸 폭(17rem).~~ — 정함(권고 — 06d 계획 정함 9): 대신한다(탐색 중 PlanCard 를 지우고 `ReportSkeleton` 이 선다). 옆 칸 폭 17rem 그대로.
```

old:

```markdown
- **'소장자료검색'으로 맞출 다른 문구** — 입력창 안내(`pages/index.vue:82`), 사이드바 묶음 이름(`AppSidebar.vue:150`).
```

new:

```markdown
- ~~**'소장자료검색'으로 맞출 다른 문구** — 입력창 안내(`pages/index.vue:82`), 사이드바 묶음 이름(`AppSidebar.vue:150`).~~ — 정함(권고 — 06d 계획 정함 18): 둘 다 맞췄다 — 입력창 안내 '찾고싶은 소장자료를 문장으로 검색해보세요!', 사이드바 기록 탭 '소장자료'(그 탭의 빈·지우기 문구 포함). 랜딩 머리 문구·결과 화면 문구는 그대로.
```

⑦ §12-10 은 고치지 않는다 — 06d 가 바꾼 열린 질문은 없다(Q1·Q8·Q9 는 이미 해결로 적혀 있고, Q4 는 06c 기록이 D28 과 함께 해결로 적었다).

⑧ §12-3 입구의 '탐색 방식' 줄 — 자리·모양(정함 19). old:

```markdown
— 자리·모양은 06d 계획이 정한다.
```

new:

```markdown
— **06d 구현:** + 메뉴에서 딥리서치를 고르면 칩 옆에 '탐색 방식' 두 칸 선택(`ResearchModePicker.vue` — radiogroup, 고른 칸만 Tab·방향키로 고름)이 서고 `/research` 홈의 새 연구도 같은 부품을 쓴다. 고른 값은 이 브라우저에 기억하고(localStorage `skx_research_mode` — 읽지 못하면 정밀하게), [같은 질문으로 다시 시작]은 고르는 칸 없이 원래 잡의 두 칸을 잇는다(두 칸이 없는 06c 전 잡은 정밀하게). 연구 화면 머리의 상태 배지 옆에 그 잡의 방식을 작게 보인다(두 칸 다 0 → 폭넓게, 두 칸이 없거나 갈리면 표시 없음). 판단은 `utils/researchMode.ts`(06d 계획 정함 19).
```

(N5 를 잘랐으면 new 의 첫 문장을 `+ 메뉴에서 딥리서치를 고르면 칩 옆에 '탐색 방식' 두 칸 선택(`ResearchModePicker.vue` — radiogroup, 고른 칸만 Tab·방향키로 고름)이 선다.` 로 쓴다 — `/research` 홈 구절을 뺀다.)

⑨ §12-3 '오프셋' 행 — 절 이동 자리의 몫을 문서 여백이 맡은 것(정함 3 · D4 품질 검토 반영). old:

```markdown
| 오프셋 | A 옆 칸 `top`·`.rs-section` 의 `scroll-margin-top`·위치 복원 자리 맞춤을 막대 높이(`--rs-bar-h`)만큼 내린다(안 그러면 이동한 절 제목이 막대 밑에 숨는다).
```

new:

```markdown
| 오프셋 | A 옆 칸 `top`·위치 복원 자리 맞춤을 막대 높이(`--rs-bar-h`)만큼 내리고, 막대가 서 있는 동안 문서 스크롤 칸(html)에 `scroll-padding-top`(막대 높이 — `:root` 의 `--rs-bar-area-h`)을 둬 초점 이동·절 이동(`scrollIntoView`)·#조각 이동이 막대 밑을 보이는 곳으로 치지 않게 한다(안 그러면 이동한 절 제목·키보드 초점을 받은 요소가 막대 밑에 숨는다 — WCAG 2.2 2.4.11). `.rs-section` 의 `scroll-margin-top` 은 `1.2rem` 그대로다 — 막대 높이를 두 번 더하지 않는다(06d 계획 정함 3).
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && grep -c "06d 계획 정함" docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && grep -cE "프로그램이 일으킨 스크롤은 플래그로 거른다|ReportView 자리 모드 또는|고정한 인용 팝오버|자리·모양은 06d 계획이 정한다|scroll-margin-top.·위치 복원 자리 맞춤" docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && grep -c "06d 구현 완료(" docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`

Expected: 첫 수 `8`(D22·D26·§12-3 따라가기 행·§12-3 절 자리 행·§12-3 탐색 방식 줄·§12-3 오프셋 행·§12-11 두 항목 — 줄마다 한 번 세므로 여덟 줄. 따라가기 행은 세 군데를 고쳤지만 한 줄이다), 둘째 `0`(옛 문구가 남지 않았다), 셋째 `1`.

- [ ] **Step 4: 반복 함정 — 이번에는 더하지 않는다는 판단을 적는다**

`docs/ops/recurring-gotchas.md` 는 라이브(docker·실데이터)에서만 드러난 패턴을 적는다. 06d 는 아직 운영 전이라 더할 것이 없다 — Task Z7 이 운영 확인의 관찰을 보고 다시 판단한다(예: 고정 막대와 브라우저 스크롤 앵커링이 겹쳐 따라가기가 흔들리면, 또는 nuxt Recreate 뒤 옛 청크를 들고 있던 탭이 동적 import 404 를 내면). 이 Step 은 파일을 고치지 않는다.

- [ ] **Step 5: 문서 리뷰 — code-reviewer 하나**

`.claude/agents/code-reviewer.md` 서브에이전트(subagent_type `code-reviewer`)에게 문서 일관성 리뷰를 맡긴다. 프롬프트:

```text
round06d 문서 리뷰(일관성). 저장소 C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d 에서 docs/roadmap/round06d-완료노트.md(새), docs/roadmap/00_status.md 의 round06 줄, docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md 의 머리 상태 줄·D22·D26·§12-3(지금 진행하는 절 따라가기·탐색 중 절 자리 행)·§12-11 을 읽고, 코드(frontend/utils/researchProgress.ts·researchFollow.ts·planSlots.ts·researchLayout.ts·evidenceLedger.ts·sidebarResearch.ts·researchHome.ts·addToWork.ts·paperResearch.ts, composables/useSectionFollow.ts, components/research/ResearchProgressBar.vue·ReportSkeleton.vue, pages/research/[id].vue, pages/research/index.vue(있으면), components/AppSidebar.vue, pages/index.vue, utils/researchMode.ts, components/research/ResearchModePicker.vue·SearchPlusMenu.vue·ResearchHeader.vue)와 계획 docs/superpowers/plans/2026-10-08-round06d-research-progress-screen.md 의 정함 1~19 에 맞는지 본다. 탐색 방식(D28·정함 19)은 문서마다 폭넓게 {broaden 0, query_context 0} · 정밀하게 {1, 1} · 기본 정밀하게 · 서버 기본값 0 그대로 · 다시 시작은 원래 잡의 두 칸 · 머리 표시(두 칸이 없거나 갈리면 없음)가 같은지도 본다. 특히 상수·문구(EXPLORE_WEIGHT 111·SYNTH_WEIGHT 91·RUNNING_CAP 0.9·ROUND_HALF_LIFE_MS 6000·HOME_PAGE_SIZE 50·'↓ 지금 쓰는 곳으로'·'↓ 지금 찾는 곳으로'·D17 문구·'소장자료')가 문서마다 같은지, 완료노트 §2·§6 과 입구 구절이 실제로 한 Task(N5·N6·N7·N8 을 했는지)와 맞는지, spec 의 따라가기 행이 정함 4~7 과 같은지, stale 서술('플래그로 거른다'·'ReportView 자리 모드 또는')이 남았는지. 보고는 code-reviewer 형식.
```

Expected: 결함 목록(없으면 "없음"). 발견은 Edit 로 고친다(같은 커밋에 넣는다).

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && ! grep -n '<[^>]*>' "docs/roadmap/round06d-완료노트.md" && git add "docs/roadmap/round06d-완료노트.md" && git add docs/roadmap/00_status.md && git add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git status --short && git commit -m "[Docs] round06d — 완료노트(왜·한 일·리뷰·검증·결정 정함 1~19·조건부 Task 판정·이월, 배포 전)와 현재 상태(round06 줄 — 06d 구현 완료·nuxt 배포 대기, 다음 할 일은 계획 Task Z4~Z7 의 머지·배포·운영 확인 순서), spec 을 코드에 맞춘다: 머리 상태 줄, D22·D26 구현 방식(ResearchProgressBar·researchProgress·researchFollow·ReportSkeleton·planSlots·reviewing, 입구), §12-3 따라가기 — 멈추는 것은 사용자 입력뿐(플래그 문구를 갈음 — 정함 4)·인용 팝오버는 고정·hover 를 가리지 않음·돌아온 화면은 멈춘 채 시작·탐색 중 알약 문구, 탐색 중 절 자리는 ReportSkeleton, §12-3 탐색 방식의 자리·모양(정함 19 — + 메뉴 칩 옆 두 칸·홈·다시 시작·머리 표시), §12-11 의 탐색 중 PlanCard·소장자료 문구를 정함(권고)으로 닫음"
```

Expected: `grep` 이 찍는 줄 없이 커밋 1개(`git status --short` 의 세 줄 `A `·`M `·`M ` 과 커밋 요약만 나온다). 완료노트에 꺾쇠 자리가 남았으면 그 줄을 행 번호와 함께 찍고 커밋하지 않은 채 멈춘다 — Step 1 의 규칙대로 채운 뒤 같은 명령을 다시 돌린다.

---

### Task Z4: (사용자 승인) dev 머지 — 머지 문 확인·N8 재확인·임시 worktree

**왜:** GIT_WORKFLOW — dev 머지는 매번 사용자 승인. §12-6 머지 문 — 06d 는 06c 운영 배포(10/13~14)가 끝난 뒤에만 dev 에 들어가고, 06c 의 화면 한 줄을 이어 단 채(L6) 나간다. 06e 와의 순서는 묶이지 않지만 06e 가 먼저 들어왔으면 LNB 접기(N8)를 단 뒤 머지한다. dev 머지가 배포보다 먼저다 — 06d 가 운영에 있고 dev 에 없는 동안 다른 세션이 dev 로 `:latest` 를 빌드·Recreate 하면 06d 가 말없이 되돌려진다(06a 사용자 결정 2026-10-03). **머지 뒤 배포(Task Z5)를 미루지 않는다.**

**Files:** 없음(머지 커밋만 — 문서 충돌이 났으면 그 해결)

- [ ] **Step 1: 머지 문 네 가지를 확인한다(작업 트리를 건드리지 않는다)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
git fetch origin dev:dev
git log --oneline --merges dev | grep -c "feat/round06c-query-broadening"
git show dev:docs/roadmap/round06c-완료노트.md | grep -cE "^### 5-2"
grep -c ':question-used="questionUsed"' "frontend/pages/research/[id].vue"
grep -c "questionUsedFromSteps" "frontend/pages/research/[id].vue"
git log --oneline --merges dev | grep -c "feat/round06e-assistant-auto-report"
grep -c "is-lnb-collapsed" "frontend/pages/research/[id].vue"
git merge-base --is-ancestor $(git log --format=%H --merges -1 --grep="feat/round06e-assistant-auto-report" dev 2>/dev/null || echo HEAD) HEAD && echo "06e 머지를 받았다(또는 06e 머지 없음)"
git log --oneline --merges dev | grep -c "feat/round06d-"
```

Expected와 판단:
- ① 06c 머지 → `1` 이상, 06c 완료노트 `### 5-2`(서버 배포 기록) → `1` — 06c 운영 배포가 끝났다. 둘 중 하나라도 `0` 이면 **머지하지 않고 멈춘다**(머지 문이 아직 닫혀 있다 — 06c 세션의 배포·기록을 기다린다. 사용자가 06c 배포가 끝났다고 따로 확인해 주면 그 문장을 적고 진행한다).
- ② PlanCard 의 `:question-used="questionUsed"` 바인딩 → `1`, `questionUsedFromSteps` → `1` 이상(import 와 computed) — Task L6 을 했다. 둘 중 하나라도 `0` 이면 L6 부터 한다. (커밋 메시지로 가르지 않는다 — '이렇게 이해했어요' 는 Task D2 의 커밋과 L6 의 merge 커밋 메시지에도 있어 L6 을 하지 않았어도 1 이상이 나온다.)
- ③ 06e 머지 → `0` 이면 06d 가 먼저 들어간다 — `is-lnb-collapsed` 는 `0` 이 맞다(N8 건너뜀). 오늘이 10/17 전이면 사용자에게 "06e 를 기다릴지, 06d 를 먼저 넣을지" 묻는다(기본 순서는 06e 먼저). `1` 이상이면 06e 가 먼저 들어왔다 — `is-lnb-collapsed` 가 `1` 이상이고(N8 을 했다) 바로 다음 줄이 `06e 머지를 받았다(또는 06e 머지 없음)` 여야 한다. 06e 머지가 있는데 N8 을 하지 않았거나 그 머지를 받지 않았으면 **이 Task 를 멈추고 Task N8 을 한다**(N8 이 dev 를 받고 LNB 두 곳을 단다) → Task Z1 Step 1·2 를 다시 돌린다 → 바뀐 것만 해당 영역 리뷰어에게 보인다(Task Z1 Step 5 의 되풀이 규칙) → 이 Step 부터 다시.
- ④ 06d 머지 → `0`.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
git log --oneline HEAD..dev
git merge-tree --write-tree --name-only dev HEAD; echo "exit=$?"
```

Expected:
- `HEAD..dev` — 빈 출력이거나 L6·N8 뒤 dev 에 들어온 커밋(06c 의 기록·기본값 커밋, 다른 라운드의 문서 등). 코드 커밋이 있으면 적어 둔다(Task Z5 Step 1 의 빌드 확인이 처리한다)
- `merge-tree` — 트리 OID 한 줄과 `exit=0`(충돌 없음). `exit=1` 이면 충돌 파일을 본다:
  - `docs/roadmap/00_status.md`·`docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` 만이면 아래 규칙으로 푼다.
  - `frontend/` 의 파일이 나오면(06e 가 N8 뒤 다시 들어왔거나 다른 라운드가 같은 줄을 고쳤다) **머지를 멈추고** 06d worktree 에서 `git merge dev` 로 먼저 받아 푼 뒤(06e 몫 `[id].vue:57-75`·리스너·`workPanelOpen` 은 dev 쪽, 그 밖은 06d 쪽) Task Z1 Step 1·2 를 다시 돌리고 이 Step 부터 다시 한다. 푸는 방법이 분명하지 않으면 사용자와 정한다.
- 문서 충돌 규칙: 어느 한쪽을 통째로 고르지 않는다. `00_status.md` 3행은 dev 쪽 줄을 바탕으로 날짜를 머지하는 날로 바꾸고 괄호 맨 앞에 Task Z3 Step 2 ① 의 `round06d — … nuxt 배포 대기. ` 구절만 넣는다. round06 머리·하위 줄·다음 할 일·라운드 이력은 세 줄이 함께 쓰는 블록이다 — dev 쪽 줄(06c·06e 구절이 있으면 그대로)을 남기고 이 브랜치의 06d 구절(머리의 ` · 06d 구현 완료·…`·06d 하위 줄·06d 다음 할 일 줄·이력의 06d 칸)만 더한다. spec 3행·D22·D26 도 같은 방법이다 — dev 쪽 글에 06d 구절만 더한다. 다 풀면 `grep -cE '^(<<<<<<<|=======|>>>>>>>)' docs/roadmap/00_status.md docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` 가 두 줄 모두 `:0`.

- [ ] **Step 2: 사용자에게 승인을 받는다**

리뷰를 마친 커밋(Task Z1 Step 5)·문서 커밋(Task Z3 Step 6)·Task Z2 의 판단(그대로 / 바꿈)·Step 1 의 출력(머지 문 네 가지·충돌 없음)과 Task Z5 의 배포 경우(06e 와 함께 / nuxt 만 / 06c 기본값과 함께 — Task Z5 Step 1 의 표)를 보이고 "06d 를 dev 에 머지하고 이어서 배포(Task Z5)를 한다" 는 승인을 받는다. 승인 문장과 날짜를 적어 둔다(완료노트 '상태').

- [ ] **Step 3: 임시 worktree 에서 머지하고 바로 지운다**

본 작업 폴더가 아니라 임시 worktree 에서 머지한다. 그 폴더 안으로 `cd` 하지 않는다 — 셸이 그 안에 있으면 Windows 가 폴더를 지우지 못해 빈 폴더가 남는다(06b 완료노트 §7-17).

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/dev-merge dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge merge --no-ff feat/round06d-research-progress-screen -m "Merge feat/round06d-research-progress-screen into dev — round06d 진행 화면(처음부터 2단·큰 진행 막대·절 따라가기·탐색 중 절 자리·검토 중 후보)·입구(/research 홈·사이드바 단계·빠른검색), nuxt 만·스키마 변경 없음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge push origin dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c dev-merge
```

N5·N6 를 잘랐으면 머지 메시지의 괄호 안 입구 구절을 그에 맞게 줄인다(예: (다) `입구(사이드바 단계·예시 묶음·빠른검색 [딥리서치로 더 깊게])`).

Expected: 머지 커밋 한 줄(완료노트 §5-1 에 적는다), push 성공, 마지막 줄 `0`. 충돌이 났으면 Step 1 의 문서 규칙으로 `.worktrees/dev-merge` 의 두 문서를 Edit 로 고친 뒤 `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge add docs/roadmap/00_status.md && git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge commit --no-edit` 로 머지를 끝내고 push 한다.

---

### Task Z5: (사용자) 운영 배포 — 경우 가르기·nuxt 빌드·Recreate·게이트웨이 reload (10/17~18)

**왜:** §12-6 — 06d 는 nuxt 만이다(스키마 단계 없음). 10/17~18 배포는 원래 06e·06d 를 함께(워커 셋 → fastapi → nuxt → reload, 06c 기본값 커밋 포함) 낸다. 06d 가 그 배포의 어느 몫을 맡는지는 그때의 dev 와 운영 상태로 정해진다 — Step 1 이 가른다. Step 1 의 빌드는 개발 PC, 나머지는 **사용자가** 서버에서 한다.

**Files:** 없음

**알아 둘 것:**
- **경우 셋.** **A** — 06e 가 dev 에 있고 아직 운영에 없다(기본 순서): 배포 한 번으로 06c 기본값·06e·06d 를 함께 낸다. 순서·명령의 정본은 06e 계획의 운영 배포 Task(워커 셋 → fastapi → nuxt → reload)이고, nuxt 이미지는 06d 머지가 든 dev 로 한 번만 만든다. 06d 는 그 배포의 nuxt Recreate 뒤 Step 6 의 06d 확인을 더한다. **B** — 06d 와 함께 나갈 백엔드가 없다(06e 가 이미 운영에 나갔거나, 06e 가 dev 에 없고 06c 기본값도 이미 운영과 같다): nuxt 만(Step 2·3·5·6). **C** — 06e 가 dev 에 없고(06d 먼저) dev 의 06c 기본값이 운영과 다르다: fastapi 이미지도 만들어 워커 셋 → fastapi → nuxt → reload(Step 2~6 전부).
- nuxt 만 Recreate 하면 도는 딥리서치·생성은 끊기지 않는다(백엔드 그대로). 화면을 보던 사용자는 새로고침하면 새 화면을 받는다. 워커·fastapi 를 Recreate 하는 경우 C 만 '비었는지 확인'이 필요하다.
- **서버 명령은 처음부터 root 셸(`su - root`)에서 한다** — `sudo` 가 아니다. 셸을 바꾸면 `pg`·`pgq`·`API`·`OLD`·`NEW`·`OLD_NUXT`·`NEW_NUXT` 를 다시 정의한다.
- 함정: 3(운영은 `:latest`)·12(Portainer 에 pull 을 맡기지 않는다 — CLI `docker pull` 을 끝까지 기다린 뒤 "Re-pull image" 끄고 Recreate)·16(바뀐 컨테이너만 — 스택 업데이트 금지)·20(Recreate 뒤 `nginx -s reload`, 확인은 게이트웨이 92 경유). 경우 C 는 14·18·24 도.

- [ ] **Step 1: (개발 PC·서버) 경우를 가르고, 빌드 확인 뒤 이미지를 만든다**

개발 PC:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
git fetch origin dev:dev
git log --oneline --merges dev | grep -c "feat/round06e-assistant-auto-report"
git show dev:app/services/research/state.py | grep -E '^ +"(broaden|query_context)": [01],'
```

Expected: 06e 머지 수(`0` 또는 `1`), 그리고 dev 의 기본값 두 줄(예: `    "broaden": 1,`·`    "query_context": 1,`).

서버(root 셸):

```bash
su - root                                                                              # 이 셸에서 끝까지 이어 쓴다
API=http://localhost:92/api
SID=$(cat /proc/sys/kernel/random/uuid)
curl -s "$API/history?kind=research&limit=1" -H "x-session-id: $SID"; echo
docker exec -w /app nl-lib-fastapi python -c "from services.research.state import DEFAULT_PARAMS as P; print(P.get('broaden'), P.get('query_context'))"
```

Expected: 첫 줄 `{"items":[],"next_cursor":null}`(06e fastapi 가 운영에 없다) 또는 `{"items":[],"next_cursor":null,"total":0}`(있다 — 새 브라우저 ID 라 0), 둘째 줄 운영 기본값(예: `0 0`). 둘째 줄이 `None None` 이면 운영 fastapi 가 06c 전 이미지다 — 06d nuxt 는 딥리서치를 시작할 때 `broaden`·`query_context` 를 싣고(Task N9) 06c 전 `merge_params` 는 그 키를 422 로 거부하므로, **여기서 멈추고** 06c 세션(사용자)과 정한다.

| 06e dev 머지 | 운영 history 에 `total` | dev 기본값 = 운영 기본값 | 경우 |
|---|---|---|---|
| 1 | 없음 | — | **A** — 06e 세션(사용자)과 배포를 한 번으로 합친다. 06e 계획의 운영 배포 Task 를 따른다 — 그 Task 의 빌드 확인·nuxt 빌드는 아래 빌드 확인을 지난 dev 트리로 **한 번만**(누가 빌드할지 사용자가 정한다). 이 Task 는 Step 6 만 한다 |
| 1 | 있음 | 같음 | **B** — Step 2·3·5·6 |
| 0 | 없음 | 같음 | **B** — Step 2·3·5·6 |
| 0 | 없음 | 다름 | **C** — Step 2~6 전부 |
| 1 | 있음 | 다름 · 또는 0 | 있음 | — | 예상 밖이다 — 멈추고 사용자와 정한다 |

빌드 확인(개발 PC) — 빌드는 dev 와 같은 트리에서 한다(다르면 dev 에 있고 빌드에 없는 코드를 이 이미지가 말없이 되돌리거나, 그 반대를 다음 dev 빌드가 되돌린다):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
(
  git fetch origin dev:dev || { echo "fetch 실패 — origin/dev 를 확인하지 못했다, 멈춘다"; exit 1; }
  git merge-base --is-ancestor HEAD dev || { echo "HEAD 에 dev 에 없는 커밋이 있다 — 멈춘다"; exit 1; }
  C=$(git log --oneline HEAD..dev -- app frontend infra docker-compose.yml scripts/build_dev_images.sh)
  [ -z "$C" ] || { printf 'dev 에 HEAD 에 없는 코드 커밋이 있다 — 멈춘다\n%s\n' "$C"; exit 1; }
  echo "빌드해도 된다: $(git rev-parse HEAD)"
)
```

마지막 줄이 `빌드해도 된다: <커밋>` 일 때만 빌드한다(그 커밋을 완료노트 §5-1 에 적는다). 멈췄으면:
- `fetch 실패` — `refusing to fetch into branch 'refs/heads/dev' checked out at …` 이면 Task Z4 의 임시 worktree 가 남아 있다(지운 뒤 다시). `[rejected] … (non-fast-forward)` 면 로컬 dev 에 origin 에 없는 커밋이 있다(머지 뒤 push 를 빠뜨렸으면 push 한 뒤 다시).
- `HEAD 에 dev 에 없는 커밋` — Task Z4 의 머지가 빠졌다. 머지부터 한다.
- `dev 에 HEAD 에 없는 코드 커밋` — 머지(--no-ff) 커밋 뒤에 dev 에 코드가 더 들어왔거나, 머지 커밋이 dev 쪽 코드를 함께 가져왔다. 06d worktree 에서 `git merge --ff-only dev` → Task Z1 Step 1 의 회귀(typecheck·`Duplicated imports`·vitest·06d 묶음·build·백엔드 전체)를 다시 돌려 실패 0 을 본 뒤 → 위 확인부터 다시 하고 빌드한다. 다시 돈 수를 완료노트 §5-1 에 적는다. 새로 들어온 것이 06e 머지면 경우 표를 다시 본다.

이미지(개발 PC, 위 확인이 '빌드해도 된다' 로 끝난 같은 폴더) — 원문 뷰어(`frontend/public/pdfjs`, gitignore)를 본 작업 폴더에서 복사한 뒤 nuxt 를 만든다(06b Task 37 Step 9 와 같다):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && cp -r C:/Users/LANDSOFT/mygit/NL_library_AI/frontend/public/pdfjs frontend/public/ && ls frontend/public/pdfjs/web/viewer.html && git status --short
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && NL_LIB_NUXT_IMAGE=landsoftdocker/nl-lib-nuxt:latest bash scripts/build_dev_images.sh nuxt
```

경우 C 이면 fastapi 도 만든다(워커 셋과 fastapi 가 같은 app 이미지):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi
```

Expected: `frontend/public/pdfjs/web/viewer.html`, `git status --short` 빈 출력(pdfjs 는 `frontend/.gitignore:26` 에 있다), `── Nuxt: landsoftdocker/nl-lib-nuxt:latest ──…` 뒤 build·push 로그, 끝에 `완료. Portainer에서 nl-lib-dev 스택 Pull & Redeploy 하면 반영됩니다.`(스크립트의 고정 안내 — 운영은 아래 Step 으로 한다). 경우 C 는 `── FastAPI: landsoftdocker/nl-lib-fastapi:latest ──…` 도 같은 끝줄로 끝난다.

- [ ] **Step 2: (사용자, 서버) 전제 확인**

```bash
pg()  { docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; }
pgq() { docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA'; }
echo "SELECT version_num FROM alembic_version" | pgq                                  # 0007_research_work — 06d 는 바꾸지 않는다
OLD_NUXT=$(docker inspect --format '{{.Image}}' nl-lib-nuxt); echo "$OLD_NUXT" | cut -c1-19
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/research                 # 06d 전 — /research 는 없는 주소
OLD=$(docker inspect --format '{{.Image}}' nl-lib-fastapi); echo "$OLD" | cut -c1-19
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$OLD" ] && echo "$c 같음" || echo "$c 다름"
done
```

Expected: `0007_research_work`, nuxt 이미지 ID 앞 19자, `/research` → `404`, fastapi 이미지 ID 앞 19자, 세 줄 '같음'.
- `alembic_version` 이 다르면 멈춘다(함정 14).
- 경우 C 에서 '다름' 이 있으면 배포를 멈추고 되돌릴 이미지를 사용자와 정한다(롤백은 넷이 같은 이미지라는 전제다). 경우 B 는 워커·fastapi 를 건드리지 않으므로 '다름' 이어도 진행하되 완료노트 §5-2 에 적는다.

- [ ] **Step 3: (사용자, 서버) 되돌리기 태그를 남기고 새 이미지를 받는다**

```bash
docker tag "$OLD_NUXT" landsoftdocker/nl-lib-nuxt:pre-round06d
docker pull landsoftdocker/nl-lib-nuxt:latest                                         # 끝까지 기다린다
NEW_NUXT=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-nuxt:latest); echo "$NEW_NUXT" | cut -c1-19
[ "$NEW_NUXT" != "$OLD_NUXT" ] && echo "새 nuxt 이미지 받음"                           # pull 이 끝나기 전에 잡으면 옛 ID 다(06a 교훈)
```

경우 C 이면 이어서:

```bash
docker tag "$OLD" landsoftdocker/nl-lib-fastapi:pre-round06d
docker pull landsoftdocker/nl-lib-fastapi:latest                                      # 7GB 남짓 — 끝까지 기다린다
NEW=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-fastapi:latest); echo "$NEW" | cut -c1-19
[ "$NEW" != "$OLD" ] && echo "새 fastapi 이미지 받음"
```

Expected: pull 의 마지막 줄 `Status: Downloaded newer image for landsoftdocker/nl-lib-nuxt:latest`, 새 ID 앞 19자, `새 nuxt 이미지 받음`(경우 C 는 fastapi 도 같은 꼴 세 줄). pull 만으로는 아무 컨테이너도 다시 시작되지 않는다(함정 16).

- [ ] **Step 4: (사용자, 서버 — 경우 C 만) 비었는지 확인 → 워커 셋 → fastapi**

`celery-research` 를 Recreate 하면 도는 딥리서치가 끊긴다(회수기가 45분 뒤 failed 로 거둔다). `celery-research-plan` 을 Recreate 하면 도는 계획·생성이 끊긴다. 적재 워커는 건드리지 않지만 적재가 적은 시간에 한다.

```bash
pg <<'SQL'
SELECT id, status, stage, created_at FROM research_jobs
WHERE status IN ('created', 'planning', 'approved', 'queued', 'running');
SELECT id, work_id, kind, status, created_at FROM research_generations
WHERE status IN ('queued', 'running');
SQL
for q in q_research q_research_plan; do echo "$q $(docker exec nl-lib-redis redis-cli LLEN $q)"; done
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  echo "== $c"; docker exec $c sh -c 'celery -A workers.celery_app inspect active -d "celery@$(hostname)" --timeout 5'
done
```

Expected: 두 질의 모두 0행(있으면 끝나기를 기다린다 — 사용자 잡·생성을 취소하지 않는다), `q_research 0`·`q_research_plan 0`, 세 워커 모두 `- empty -`(`celery-control` 은 디스패치 틱이 도는 중이면 몇 초 뒤 다시).

Portainer 에서 컨테이너마다 Recreate 를 누르고 **"Re-pull image" 는 끈다**(함정 12). 스택 업데이트는 하지 않는다(함정 16). ① `nl-lib-celery-research` → ② `nl-lib-celery-research-plan` → ③ `nl-lib-celery-control` 을 차례로 Recreate 한 뒤:

```bash
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$NEW" ] && echo "$c 새 이미지" || echo "$c 옛 이미지"
done
for c in nl-lib-celery-research nl-lib-celery-research-plan; do
  printf '%s ' $c; docker exec -w /app $c python -c "from services.research.state import DEFAULT_PARAMS as P; print(P['broaden'], P['query_context'])"
done
```

Expected: 세 줄 모두 '새 이미지'(하나라도 '옛 이미지' 면 그 컨테이너를 다시 Recreate — 06b 배포에서 `celery-research` 가 한 번 옛 이미지로 나왔다), 두 워커의 기본값이 Step 1 의 dev 기본값과 같다(예: `nl-lib-celery-research 1 1`).

④ fastapi 를 Recreate 하기 전에 `library_catalog` 를 쥔 채 멈춘 트랜잭션이 없는지 본다(함정 18).

```bash
pg <<'SQL'
SELECT pid, state, xact_start, left(query, 80) FROM pg_stat_activity WHERE state = 'idle in transaction';
SQL
# 0행(또는 xact_start 가 몇 초 전인 것뿐)이면 Portainer 에서 nl-lib-fastapi 를 Recreate 한다
docker logs -f --since 1m nl-lib-fastapi 2>&1 | grep -m1 "Application startup complete"   # 모델을 올려 1~2분
[ "$(docker inspect --format '{{.Image}}' nl-lib-fastapi)" = "$NEW" ] && echo "fastapi 새 이미지"
docker exec -w /app nl-lib-fastapi python -c "from services.research.state import DEFAULT_PARAMS as P; print(P['broaden'], P['query_context'])"
echo "SELECT version_num FROM alembic_version" | pgq                                     # 0007_research_work 그대로
```

Expected: `INFO:     Application startup complete.` 한 줄, `fastapi 새 이미지`, Step 1 의 dev 기본값, `0007_research_work`.

- [ ] **Step 5: (사용자, 서버) nuxt Recreate → 게이트웨이 reload**

Portainer 에서 `nl-lib-nuxt` 를 Recreate 한다("Re-pull image" 끔). 그 뒤 게이트웨이를 reload 한다(함정 20 — Recreate 한 컨테이너의 새 IP 를 nginx 가 다시 읽는다).

```bash
[ "$(docker inspect --format '{{.Image}}' nl-lib-nuxt)" = "$NEW_NUXT" ] && echo "nuxt 새 이미지"
docker exec nl-lib-gateway nginx -s reload
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/
```

Expected: `nuxt 새 이미지`, `200`·`200`. 502 가 나오면 reload 를 빠뜨렸거나 nuxt 가 아직 뜨는 중이다 — `docker logs --since 1m nl-lib-nuxt` 에 `Listening on http://0.0.0.0:3000` 이 보인 뒤 reload 와 확인을 다시 한다.

- [ ] **Step 6: (사용자, 서버) 06d 가 운영 nuxt 에 들었는지 — 경우 A·B·C 모두**

게이트웨이(포트 92)를 거쳐 확인한다(컨테이너에 직접 붙는 확인은 함정 20 을 못 잡는다). 경우 A 는 06e 계획의 배포 Task 가 nuxt Recreate·reload 를 마친 뒤 이 Step 을 한다.

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/research
docker exec nl-lib-nuxt sh -c 'grep -l "rs-pbar" /app/.output/public/_nuxt/entry.*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "rs-synth__bar" /app/.output/public/_nuxt/*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "지금 쓰는 곳으로" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "소장자료검색" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "탐색 방식" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "rs-mode__opt" /app/.output/public/_nuxt/entry.*.css | wc -l'
curl -s "$API/research-works?example=1" -H "x-session-id: $SID"; echo
```

Expected:
- `/research` → `200`(N5 를 했다). N5 를 잘랐으면 `404` 그대로가 맞다
- `rs-pbar` 가 든 entry CSS → `1`, 옛 `rs-synth__bar` → `0`(작은 막대를 걷었다)
- `지금 쓰는 곳으로`·`소장자료검색` 이 든 JS 청크 → 각각 `1` 이상
- `탐색 방식` 이 든 JS 청크 → `1` 이상, `rs-mode__opt` 가 든 entry CSS → `1`(Task N9 — 작성 때 로컬 빌드에서 각각 `1`)
- 예시 연구 목록 — `{"items":[]}`(리허설 10/23~25 에 `mark_example.py` 로 지정하기 전) 또는 지정한 예시들

배포가 끝났다. 경우 C 였으면 06c 세션(사용자)에게 "06c 기본값 커밋이 이 배포(워커 셋 → fastapi)로 운영에 나갔다 — 06c 계획의 '10/17~18 배포 뒤 06c 확인'을 하면 된다" 고 알린다. 경우 B 로 06d 가 먼저 나갔으면 06e 세션에 "06d 가 운영에 있다 — 06e 배포는 nuxt 를 dev(06d 포함)로 만들고 LNB 연결은 06e 가 단다" 고 알린다. 그리고 Task Z6 이 끝날 때까지 다른 nuxt 배포를 하지 않는다.

---

### Task Z6: (사용자, 서버·브라우저) 운영 처음부터 끝까지 1회 — 진행 화면·입구·랜딩 예시

**왜:** §12-7 운영 확인(줄마다 배포 뒤 고정 질문 하나를 처음부터 끝까지)과 §8. 06d 의 움직임(막대 차오름·따라가기·절 자리·장부 더미)은 `.vue` 라 단위 테스트가 없고 운영에서만 실제 이벤트로 본다. 질문은 랜딩 논문 예시 `공공도서관 서비스 품질 평가 연구가 궁금해`(06c 판정 질문 `library` 와 같은 문장)로 한다 — 랜딩 입구·06c 의 화면 한 줄·켠 기본값·§12-7 '랜딩 논문 예시 셋을 다시 본다' 를 한 번에 본다. 06c 의 `candidates` 는 06c 워커가 운영에 있어야 온다(10/13~14 배포 — Task Z4 Step 1 ① 이 확인했다).

**Files:** 없음(결과는 Task Z7 이 완료노트 §5-3·§5-4 에 적는다)

**알아 둘 것:**
- 만든 연구·이어간 연구·담은 논문은 실제 기록으로 남는다(사용자 자신의 브라우저 기록).
- 브라우저는 운영 주소(`http://192.168.12.57:92` 또는 `https://skovix.landsoft.co.kr`)로 연다. 넓은 화면은 1440px 창, 좁은 화면은 개발자 도구의 기기 모드로 768px·375px. '동작 줄이기'는 개발자 도구 Rendering 의 `prefers-reduced-motion: reduce` 흉내로 본다.
- 본 것은 단계마다 짧게 적어 둔다(통과 / 다름 + 무엇이). 다른 것이 나오면 그 자리에서 고치지 않고 모아서 Step 7 에서 정한다.

- [ ] **Step 1: (브라우저, 1440px) 랜딩에서 시작 — 계획·승인 대기**

1. `/` — 탭 '소장자료검색'(옛 '도서검색' 없음), 입력창 안내 '찾고싶은 소장자료를 문장으로 검색해보세요!'. 논문 탭에서 예시 칩 `공공도서관 서비스 품질 평가 연구가 궁금해` 를 누르면 입력창에만 채워진다 → + 메뉴에서 딥리서치를 고르면 칩 옆에 `탐색 방식` 두 칸(폭넓게 · 정밀하게)이 서고 이 브라우저에서 처음 고르는 것이면 `정밀하게` 가 골라져 있다(Task N9 — 다른 값이 골라져 있으면 이 브라우저에 기억된 값이다, `정밀하게` 로 고른다) → 그대로 보낸다 → `/research/<잡 id>` 로 옮긴다. 잡 id 를 적는다(아래 5 의 `J1`).
2. 계획 중 — 넓은 화면은 처음부터 2단(옆 칸 진행 패널), 위 고정 막대에 작은 단계 표시('계획' 강조)와 큰 글줄 `연구 계획을 세우는 중`, 퍼센트 없음. 계획 중 카드는 스피너와 글이 세로로 놓인다(06b 이월 §7-1). 06c `broaden` 이 켜져 있고 넓힌 질문이 원 질문과 다르면 카드에 `이렇게 이해했어요: …` 한 줄.
3. 승인 대기 — 막대 글줄 `계획 확인 대기 · 승인하면 근거 수집을 시작합니다`, PlanCard 머리에 `이렇게 이해했어요: …`(위와 같은 조건). 승인한다.
4. 대기열에 서면 막대 글줄 `대기열 · …`(순번 문구)와 대기 카드(스피너·글 세로).
5. 탐색 방식(Task N9) — 머리의 상태 배지 옆에 `탐색 방식 · 정밀하게`. 서버의 잡 params 두 칸이 `1`·`1` 이다 — 서버(Task Z5 의 root 셸, `API=http://localhost:92/api`)에서 1 의 잡 id 를 `J1` 에 넣고 아래 명령을 친다.

```bash
curl -s "$API/research/$J1" | grep -oE '"(broaden|query_context)": ?[0-9]+'
```

Expected: 다섯 모두 위와 같다. 5 의 명령은 두 줄 — `broaden` 과 `query_context` 가 모두 `1`(서버 기본값은 0 이므로 화면이 두 칸을 실었다는 뜻이다. JSON 의 콜론 뒤 공백은 서버 직렬화에 따라 있거나 없다). 빈 출력이면 잡 응답에 두 칸이 없다 — 운영 fastapi 가 06c 전 이미지인지 Task Z5 Step 1 의 기본값 확인부터 다시 본다. `0`·`0` 이면 화면이 정밀하게를 싣지 않은 것이다 — Step 7 에서 정한다.

- [ ] **Step 2: (브라우저, 1440px) 탐색 — 막대·절 자리·회차 상태·장부 더미·따라가기**

1. 막대 — 단계 '근거 수집' 강조, 글줄 `근거 수집 중 · 하위질문 k/n — 「…」`, 퍼센트가 이벤트마다 늘고 뒤로 가지 않으며 탐색이 끝날 무렵 55% 안팎(111/202)에서 작성으로 넘어간다. 채움 끝의 빛 흐름이 돈다.
2. 본문 — 읽기 전용 PlanCard 는 없고 '보고서 자리' 카드에 하위질문마다 자리(머리 '하위질문 N'·제목·skeleton·상태 '대기'·'근거 수집 중 · n회차'·'근거 N편 ✓').
3. 옆 칸 — 근거 장부가 맨 위, 그 아래 진행 패널. 진행 패널 회차 줄에 `자기점검 중`(깜빡임)·`재검색 중`.
4. 장부 '검토 중' — 회차마다 '검토 중 n' 묶음에 흐린 후보 카드(제목·저자·연도)가 섰다가, 점검 뒤 채택은 위 '채택' 으로 떨어져 박히고 뺀 것은 '뺌' 으로 가라앉는다. 이때 새로고침하면 더미 없이 지금 장부만 그려진다. 탐색 중에 [취소] 한 잡의 장부에는 '검토 중' 묶음이 남지 않는다(이 잡은 끝까지 돌리므로 다른 잡 — 예 Step 4 에서 새로 돌린 잡 — 이 탐색 중일 때 본다. 재연결 사이에 끝난 잡도 같은 규칙 — Task L4).
5. 따라가기 — 첫 하위질문이 도는 순간에는 옮기지 않고(처음 본 대상은 기준 — 정함 6), 다음 하위질문부터 스크롤이 도는 하위질문의 자리로 옮겨 가고 그 자리 머리가 막대 밑에 숨지 않는다. 마우스 휠을 굴리면 멈추고 `↓ 지금 찾는 곳으로` 알약이 뜬다 → 누르면 지금 자리로 옮겨 다시 따라간다. 가로 스크롤·Ctrl+휠(확대)은 멈추지 않는다.

장부 더미가 하나도 서지 않으면 서버에서 후보 이벤트가 오는지 본다(다음 잡에서 — 이 잡이 끝나기 전이면 이 잡에서):

```bash
J=<브라우저 주소의 잡 id>
timeout 300 curl -sN $API/research/$J/stream | grep -o '"kind": "[a-z_]*"' | sort | uniq -c
```

Expected: `candidates` 줄의 수가 회차 수(하위질문마다 1회 이상)만큼, 그 밖에 `search`·`counters`·`critique`·`snapshot` 등. `candidates` 가 없으면 운영 워커가 06c 전 이미지다 — 06c 세션에 알린다(06d 화면은 이벤트가 없으면 더미 없이 지금처럼 그리는 것이 맞다).

- [ ] **Step 3: (브라우저, 1440px) 작성·끝 — 막대 이어 차오름·절 따라가기·막힘·인쇄·돌아온 자리**

1. 작성 — 막대 단계 '보고서 작성' 강조, 글줄 `보고서 작성 중 · i/n절 — 「…」`, 퍼센트가 탐색 끝 값에서 이어 차오른다(뒤로 가지 않는다). 첫 절 전에는 쓰는 절의 자리가 '이 절을 쓰는 중', 근거 0 자리는 '근거 없음' 으로 접힌다. 첫 절이 오면 절 자리 대신 초안이 선다.
2. 보고서 작성 현황 카드 — 절 목록·[초안 저장]은 그대로, 작은 막대는 없다.
3. 따라가기 — 스크롤이 지금 쓰는 절로 옮겨 가고 절 제목이 막대 밑에 숨지 않는다. 휠을 굴리면 멈추고 `↓ 지금 쓰는 곳으로` → 누르면 다시 따라간다. 현황 카드에서 절 하나를 누르면 그 절로 옮기고 따라가기가 멈춘다(알약이 뜬다) — 그 절 제목은 막대 바로 아래에 조금(1.2rem) 띄워 서고, 막대 아래에 막대 높이만 한 빈 틈이 생기지 않는다(막대 높이를 두 번 더하지 않음 — D4 품질 검토 반영). 초안을 아래로 굴린 뒤 Shift+Tab 으로 위로 올라가면 초점을 받은 인용 칩·버튼이 막대 밑에 가린 채 남지 않고 창이 굴러 막대 아래에 보인다(문서 `scroll-padding-top` — WCAG 2.2 2.4.11).
4. 막힘 — 인용 칩에 마우스를 올려(또는 눌러 고정해) 팝오버를 연 동안, 원문 뷰어를 연 동안에는 다음 절이 시작돼도 끌려가지 않는다. 닫은 뒤 다음 절이 시작되면 옮겨 간다(따라가는 중이었으면). 원문 뷰어를 열어 머리 줄·어두운 바탕 위에서 휠을 굴려도, 닫은 뒤 알약 없이 다음 절에서 따라간다(모달이 페이지를 묶은 동안의 입력은 멈춤이 아니다 — Task D7).
5. 돌아온 자리 — 작성 중에 인용 칩 → 논문 상세 → 브라우저 뒤로: 떠난 자리로 돌아오고 그 자리가 막대 밑에 가리지 않으며, 따라가기는 멈춘 채 알약만 떠 있다.
6. 움직임 줄이기(개발자 도구 Rendering 흉내) — 막대 채움의 transition·빛 흐름이 멈추고, 따라가기는 부드럽게가 아니라 즉시 옮긴다. 장부 더미의 반짝임도 없다.
7. 끝 — 막대가 사라지고 머리 상태 배지만 남는다. Ctrl+P 인쇄 미리보기에 막대·알약이 없다.
8. 보고서 끝 [이 연구 이어가기] → 머리에 06e 의 단계 막대(WorkStepper)만 선다 — 고정 진행 막대와 함께 서지 않는다. 06e 가 운영에 있으면 보고서 단계(`?s=proposal`)에서 [보고서 만들기] 뒤 절을 쓰는 동안 06e 보고서 화면의 큰 막대(목차 위 — 10-11 사용자 확인, 06e 계획 정함 28)가 서고, 06d 의 고정 막대는 그 화면에 함께 서지 않는다. 두 막대의 두께·큰 글줄·퍼센트 크기가 같아 보인다(1440px·768px 에서 각각 1rem·0.75rem). 06e 막대의 글줄·퍼센트 동작은 06e 운영 확인 몫이다 — 여기서는 '한 화면에 큰 막대 하나'와 크기만 본다.
9. 스타일(D8) — 옆 칸의 근거 장부·진행 패널 카드 머리만 새 모양이고, 본문 카드 제목(보고서 작성 현황·실패·취소·보고서 오류)과 연구 어시스턴트 단계 화면의 카드 제목은 전과 같다. 머리 kicker '딥리서치' 는 skx 칩 모양.

Expected: 아홉 모두 위와 같다.

- [ ] **Step 4: (브라우저, 768px·375px) 좁은 화면**

같은 잡(끝났으면 새 질문 하나를 승인해 탐색 중에 — 새 질문은 + 메뉴의 탐색 방식에서 `폭넓게` 를 골라 시작하고 그 잡 id 를 적는다, Step 5 의 7 이 `J2` 로 쓴다)을 768px·375px 로 본다 — B 배치(문서형), 막대 두께가 얇아지고(0.75rem) 큰 글줄은 한 줄 말줄임, 퍼센트·단계 칩이 겹치지 않는다, 가로 스크롤이 생기지 않는다, 알약이 화면 안에 선다, 절 자리 머리가 막대 밑에 숨지 않는다.

Expected: 위와 같다.

- [ ] **Step 5: (브라우저) 입구 — 사이드바·`/research` 홈·빠른검색**

1. 사이드바 — 기록 탭 이름 '소장자료'(빈·지우기 문구도 '소장자료'), 딥리서치 탭의 Step 3 에서 이어간 연구 줄에 단계 글(06e 의 이름 — 예 `주제` 또는 06e 가 바꾼 이름)과 수, 생성이 도는 동안 '생성 중' 이 붙고 30초 안에 바뀐다(폴링). 목록 끝 `모두 보기 (N)`(06e fastapi 가 운영에 없으면 `모두 보기`).
2. 기록이 없는 새 시크릿 창 — 딥리서치 탭의 빈 문구 아래에도 `모두 보기` 가 서고 `/research` 로 간다(N5 를 잘랐으면 링크 대신 '예시 연구' 묶음 — 줄마다 질문·'읽기 전용 · 단계'·`… 실행`(KST 실행 시각)이 보이고, 예시가 없으면 묶음도 없다).
3. `/research` 홈(N5) — 새 연구 시작 입력창·[계획 세우기](빈 칸·1자면 막힘), 진행 중·내 연구 묶음(50건 넘으면 [더 보기]), 예시 연구 섹션(예시가 아직 없으면 섹션 없음). 첫 잡이 도는 동안 같은 브라우저에서 질문을 넣고 [계획 세우기] 를 누르면 잡이 만들어져 연구 화면으로 간다. 그 화면에서 [승인] 을 누르면 진행 중인 연구 안내와 그 링크가 뜬다(429 `browser_active` — 브라우저당 1건. 지금 서버는 연구 만들기(`POST /api/research`)에서는 429 를 내지 않고 승인·재시도에서 낸다). 홈의 링크는 서버가 만들기에서도 막게 바뀔 때를 대비한 방어다.
4. 논문 빠른검색 — `/papers` 에서 검색해 AI 답이 끝나면 답 끝 [딥리서치로 더 깊게] 카드(버튼에 마우스를 올려도, 한 번 누른 뒤 같은 검색으로 돌아와 visited 가 돼도 버튼 글자가 흰색) → 누르면 주소가 `/papers?draft=…` 를 거쳐 `/papers` 로 바뀌고 랜딩 입력창에 그 질문과 딥리서치 칩이 켜진다(시작하지 않는다).
5. [담기 ▾](N6) — 결과 카드의 [담기 ▾] → Step 3 에서 이어간 연구가 목록에 나온다 → 고르면 `「…」 연구에 담았습니다` 토스트 → 그 연구의 참고문헌 선택하기(`?s=reading`)에 그 논문이 담음으로 들어와 있다(들어온 경로 '사용자'). 사이드바 그 연구 줄의 `n편 담음` 이 새로고침 없이 바로 는다. 이어간 연구가 없는 새 시크릿 창에서는 `보고서 끝 [이 연구 이어가기] 뒤에 담을 수 있습니다`. 키보드 — [담기 ▾] 에 초점을 두고 ↓ 로 열고, ↑↓ 로 옮기고, Esc 로 닫으면 초점이 [담기 ▾] 버튼으로 돌아온다.
6. LNB(N8 을 했으면) — 참고문헌 선택하기에서 딥리드 패널을 열면 연구 화면의 사이드바가 접히고, 닫거나 단계를 옮기면 펼쳐진다.
7. 탐색 방식(Task N9) — ① Step 4 에서 새 질문을 돌리지 않았으면 여기서 `/papers` + 메뉴로 딥리서치를 켜고 `폭넓게` 를 골라 질문 하나를 보낸 뒤, 계획이 서면 [취소] 한다(브라우저당 1건 — 앞 잡이 끝난 뒤). 그 잡 id 를 `J2` 에 넣는다. ② 그 잡 머리에 `탐색 방식 · 폭넓게`, 아래 명령의 둘째 잡이 `0`·`0`(첫째 `J1` 은 `1`·`1` 그대로). ③ 같은 브라우저에서 `/papers` + 메뉴로 딥리서치를 다시 켜면 `폭넓게` 가 골라져 있다(기억) — `정밀하게` 로 되돌려 둔다. 새 시크릿 창에서는 `정밀하게`. ④ 키보드 — 고른 칸에 Tab 한 번으로 들어오고 ←→ 로 고른 칸이 바뀐다, 칩 × 로 딥리서치를 끄면 두 칸도 사라진다, `/research` 홈(N5 를 했으면)의 새 연구에도 같은 두 칸. ⑤ `J2` 를 취소했으면(① 또는 Step 2 의 4) 그 화면의 [같은 질문으로 다시 시작] → 새 잡(`J3`)의 두 칸이 `0`·`0`(원래 잡의 방식 그대로) → 확인 뒤 `J3` 은 [취소] 한다. `J2` 가 끝까지 돌았으면(완료된 잡에는 이 버튼이 없다) ⑤ 는 '해당 없음' 이고 아래 명령에서 `"$J3"` 을 뺀다. ⑥ 06c 배포(2026-10-12) 전에 만든 잡(사이드바·기록에 있으면 — 예 Task Z1 Step 3 의 06b 운영 확인 잡 `d8348de8-ee7f-48f9-8ceb-20924ed6a383`)의 머리에는 탐색 방식 표시가 없다.

```bash
for J in "$J1" "$J2" "$J3"; do echo "$J $(curl -s "$API/research/$J" | grep -oE '"(broaden|query_context)": ?[0-9]+' | tr '\n' ' ')"; done
```

Expected: 일곱 모두 위와 같다(자른 Task 의 항목은 '해당 없음'). 7 의 명령은 잡마다 한 줄(⑤ 가 해당 없으면 두 줄) — `J1` 은 두 칸 `1`, `J2`·`J3` 은 두 칸 `0`.

- [ ] **Step 6: (브라우저) 06c 판정 연계 — 랜딩 논문 예시 셋의 보고서**

§12-7 "켠 뒤 랜딩 논문 예시 셋의 보고서도 다시 본다". `library` 는 Step 1~3 의 잡이다. 나머지 둘은 06c 계획의 '10/17~18 배포 뒤 06c 확인' 이 이미 돌렸으면(06c 완료노트 §5-6 의 잡 id) 그 보고서를 열어 보고, 아니면 랜딩 예시 칩으로 `노인의 우울과 사회적 지지에 관한 연구가 궁금해`·`다문화가정 아동의 언어 발달에 관한 연구가 궁금해` 를 차례로 돌린다(브라우저당 1건 — 앞 잡이 끝난 뒤 다음. 탐색 방식은 화면 기본 `정밀하게` 그대로 — 사람들이 기본으로 보는 결과다, Task Z2 에서 사용자가 다른 갈래로 보기로 했으면 그 방식으로). 세 보고서에서 무관 논문이 몰린 절·동음이의 논문이 없는지 본다(06c 판정의 같은 질문·같은 갈래(정밀하게 = 갈래 1) 보고서와 견준다).

Expected: 세 보고서 모두 무관이 몰린 절이 없다. 몰린 절이 있으면 잡 id·절·논문을 적고 Step 7 에서 사용자와 정한다.

- [ ] **Step 7: 다른 것이 나왔을 때 — 모아서 정한다**

Step 1~6 에서 다른 것이 없으면 이 Step 은 끝이다. 있으면 목록(무엇이·어디서·재현 방법)을 사용자에게 보이고 하나씩 정한다:
- 고칠 것 — dev 에서 분기한 브랜치 `fix/round06d-live-check` 에서 고친다(06d worktree 에서 `git status --short` 가 빈 것을 본 뒤 `git fetch origin dev:dev && git switch -c fix/round06d-live-check dev`). 판단을 고치면 순수 함수의 실패 테스트부터, `.vue`·`.css` 만이면 typecheck·build. 커밋은 `[Fix] round06d — <무엇을 왜>`. 그 뒤 Task Z1 Step 1·2 의 회귀 → 사용자 승인 → 임시 worktree 머지(Task Z4 Step 3 의 명령, 머지 메시지 `Merge fix/round06d-live-check into dev — round06d 운영 확인 반영`) → Task Z5 의 경우 B 절차(Step 1 빌드 확인·nuxt 빌드 → Step 2·3·5·6)로 nuxt 만 다시 낸다.
- 랜딩 예시를 바꿀 것(Step 6) — 위와 같은 브랜치에서 Task Z2 Step 4 의 방법으로 고친다.
- 미룰 것 — 완료노트 §7 이월에 적는다(Task Z7).

---

### Task Z7: 배포 기록 — 기록 브랜치·dev 머지

**왜:** D13 — 완료노트에 dev 머지·배포·운영 확인을 남긴다. 06d 코드는 이미 dev 에 있으므로 기록 커밋은 dev 에서 분기한 브랜치에서 하고 dev 머지(사용자 승인)로 올린다.

**Files:**
- Modify: `docs/roadmap/round06d-완료노트.md`(머리 날짜·§5·§7·상태), `docs/roadmap/00_status.md`(Task Z3 가 넣은 06d 구절), spec(머리 상태 줄), 필요하면 `docs/ops/recurring-gotchas.md`

- [ ] **Step 1: 기록 브랜치**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d
git status --short
git fetch origin dev:dev && git switch -c docs/round06d-deploy-record dev
```

Expected: `git status --short` 빈 출력, `Switched to a new branch 'docs/round06d-deploy-record'`. Task Z6 Step 7 에서 `fix/round06d-live-check` 를 썼으면 그 브랜치가 dev 에 머지된 뒤 따는 것이다(fetch 가 그 머지를 가져온다). fetch 가 실패하면 Task Z5 Step 1 의 안내대로 푼 뒤 다시.

- [ ] **Step 2: 완료노트 §5 를 채운다 (Edit 도구)**

머리 날짜 줄의 `` `dev` 머지·운영 배포·처음부터 끝까지 1회는 §5`` 를 `` `dev` 머지 `<Task Z4 의 머지 커밋>` <날짜> · 운영 배포·처음부터 끝까지 1회 <날짜> — §5`` 로 바꾸고, §5 의 "배포 전 — …" 한 줄을 아래 하위 절로 바꾼다.

- **5-1. 머지와 이미지** — dev 머지 커밋(Task Z4), 머지 문 네 가지의 값(06c 머지·배포 기록, L6 커밋, 06e 머지 여부와 N8), 배포 경우(A·B·C 와 까닭 — Task Z5 Step 1 의 표 값), 빌드한 커밋(`빌드해도 된다:` 뒤 값), `--ff-only` 로 받았으면 그 사실과 다시 돈 테스트 수, 이미지 ID 앞 19자(`NEW_NUXT`, 경우 C 는 `NEW` 도), 서버 되돌리기 태그 `:pre-round06d`.
- **5-2. 서버 배포** — Task Z5 Step 2~6 의 확인 결과(`0007_research_work`, 경우 C 의 비었는지·워커 셋 새 이미지·기본값·fastapi, nuxt 새 이미지, reload, `/health`·`/` 200, `/research` 404 → 200, CSS·JS 청크 확인 수, 예시 연구 목록). 경우 A 면 '06e 계획의 배포 Task 로 함께 — 06e 완료노트 §5' 와 이 Task 의 Step 6 값.
- **5-3. 운영 처음부터 끝까지 1회** — 잡 id, Task Z6 Step 1~5 에서 단계마다 본 것(통과 / 다름), 탐색 방식의 잡 params 확인(Step 1 의 5·Step 5 의 7 — `J1`·`J2`·`J3` 과 두 칸 값, 출력을 붙이지 않았으면 '사용자 실행, 출력 미첨부'), 장부 더미를 진단했으면 그 출력, Step 7 에서 고친 것(브랜치·커밋·재배포) 또는 '고칠 것 없음'.
- **5-4. 06c 판정 연계** — Task Z2 의 판단(06c 판정 표의 세 질문 값·결정), Task Z6 Step 6 의 세 보고서 잡 id 와 본 것, 바꾼 예시가 있으면 그 커밋.

§7 이월에 운영 확인에서 미룬 것을 더한다. '상태' 의 수동 스모크·문서 갱신·`dev` 머지 승인을 `[x]` 로(승인 문장과 날짜를 함께).

- [ ] **Step 3: 00_status·spec·반복 함정 (Edit 도구)**

1. `docs/roadmap/00_status.md`:
   - 3행 — Task Z3 의 구절 `round06d — 진행 화면·입구 구현 완료(처음부터 2단·큰 진행 막대·절 따라가기·탐색 중 절 자리·'검토 중' 후보·입구), \`dev\` 머지·nuxt 배포 대기. ` 를 `round06d — \`dev\` 머지·운영 배포(<경우 — 예: nuxt 만 / 06e 와 함께 워커 셋 → fastapi → nuxt / 06c 기본값과 함께 워커 셋 → fastapi → nuxt>)·처음부터 끝까지 1회(<한 줄 — 예: 진행 화면·입구 모두 통과, 고친 것 n건>). ` 로, 날짜를 이 Step 을 하는 날로.
   - round06 머리 — ` · 06d 구현 완료·\`dev\` 머지·nuxt 배포 대기**` 를 ` · 06d 운영 배포(<배포 날>)**` 로.
   - 06d 하위 줄 끝(`상세: \`round06d-완료노트.md\`.`) 뒤에 한 문장: `운영 배포 <배포 날> — <경우와 한 줄 결과>(완료노트 §5).`
   - 다음 할 일의 06d 줄 머리 — Task Z3 의 `  - **06d 진행 화면·입구 — 구현 완료, \`dev\` 머지·nuxt 배포 대기(10/17~18)** — 계획 … Z7(기록) 순서.` 를 `  - **06d 진행 화면·입구 — 운영 배포·확인 끝(<배포 날>)** — 남은 것: 리허설(10/23~25)에서 예시 연구 지정 뒤 \`/research\` 홈(또는 사이드바 예시 묶음)의 실행 시각·범위·읽기 전용 다시 보기<, 이월이 있으면 '· 이월 n건(완료노트 §7)'>.` 로.
   - 라운드 이력의 round06 칸 — `· 06d 구현 완료·배포 대기(\`feat/round06d-research-progress-screen\`)` 를 `· 06d 운영 배포(<배포 날>)` 로.
2. spec 3행 — Task Z3 의 ` · 06d 구현 완료(2026-10-16 — 처음부터 2단·큰 진행 막대·절 따라가기·탐색 중 절 자리·'검토 중' 후보·입구, \`dev\` 머지·nuxt 배포 대기)` 를 ` · 06d 완료(<배포 날> 운영 배포·처음부터 끝까지 1회)` 로(Task Z3 를 한 날이 2026-10-16 이 아니면 그 날짜의 글을 old 로 잡는다).
3. `docs/ops/recurring-gotchas.md` — 운영 확인에서 라이브에서만 드러난 패턴이 있었으면 `## 28. …`(증상·원인·해결·재발 방지 — 06c·06e 가 먼저 28 을 썼으면 그다음 번호)로 더한다. 없으면 고치지 않고 완료노트 §5 끝에 "반복 함정 — 더할 것 없음" 한 줄을 남긴다.

꺾쇠 자리는 모두 실측값으로 바꾼다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git diff -U0 -- "docs/roadmap/round06d-완료노트.md" docs/roadmap/00_status.md docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md docs/ops/recurring-gotchas.md | grep '^+[^+]' | grep -c '<[^>]*>'
```

Expected: `0`(더한 줄에 꺾쇠 자리가 남지 않았다 — 원래 있던 줄의 꺾쇠는 세지 않는다).

- [ ] **Step 4: 커밋하고 dev 머지(사용자 승인)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06d && git add "docs/roadmap/round06d-완료노트.md" && git add docs/roadmap/00_status.md && git add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git status --short && git commit -m "[Docs] round06d 운영 배포 기록 — dev 머지·운영 배포(nuxt — 배포 경우와 순서, 스키마 단계 없음), 랜딩 예시 질문으로 처음부터 끝까지 1회(처음부터 2단·큰 진행 막대·탐색 중 절 자리·회차 미세 상태·장부 '검토 중' 후보·절 따라가기와 알약·막힘·인쇄·돌아온 자리·좁은 화면, 입구 — 사이드바 단계·모두 보기·/research 홈·빠른검색, 탐색 방식 — 정밀하게로 시작한 잡 params 두 칸 1 · 폭넓게 0·다시 시작은 원래 방식), 06c 판정 연계(랜딩 논문 예시 셋)"
```

`docs/ops/recurring-gotchas.md` 를 고쳤으면 `git add docs/ops/recurring-gotchas.md` 를 `git status --short` 앞에 더한다.

Expected: `git status --short` 에 문서 셋(함정을 고쳤으면 넷)만 `M`, 커밋 1개.

기록 커밋을 사용자에게 보이고 승인을 받은 뒤:

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/dev-merge dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge merge --no-ff docs/round06d-deploy-record -m "Merge docs/round06d-deploy-record into dev — round06d 운영 배포·확인 기록"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge push origin dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c dev-merge
```

Expected: 머지 커밋 한 줄, push 성공, 마지막 줄 `0`. 그 사이 06c·06e 의 기록이 같은 문서 줄을 고쳐 충돌하면 Task Z4 Step 1 의 문서 충돌 규칙으로 푼다. 그다음 `dev→main` 머지·push(`/round-finish`)를 06d 에서 할지, round06 세 줄을 모두 마친 뒤 한 번에 할지 사용자에게 묻는다.

---

#### 롤백 (사용자, 서버)

Task Z5·Z6 의 확인이 틀리거나 운영 오류(화면이 깨짐·연구 화면 500·막대가 내용을 가림 등)가 나면 되돌린다. 06d 는 서버에 아무것도 쓰지 않으므로 되돌릴 데이터가 없다 — [담기] 로 담은 논문·이어간 연구는 06b 의 읽기 목록 그대로라 옛 화면에서도 보인다.

1. **nuxt(경우 A·B·C 모두):** `docker tag landsoftdocker/nl-lib-nuxt:pre-round06d landsoftdocker/nl-lib-nuxt:latest` → Portainer 에서 `nl-lib-nuxt` Recreate("Re-pull image" 끔) → `docker exec nl-lib-gateway nginx -s reload` → `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/` 가 `200`, `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/research` 가 `404`(옛 화면). 경우 A 에서 06e 까지 되돌릴 때는 06e 계획의 롤백을 따른다 — 그때의 nuxt 되돌리기 태그는 06e 의 것을 쓴다(06e 와 함께 만든 한 이미지다).
2. **경우 C 에서 06c 기본값까지 되돌릴 때:** 딥리서치·생성이 빈 때 한다(Task Z5 Step 4 의 두 질의 0행·세 워커 `- empty -`). `docker tag landsoftdocker/nl-lib-fastapi:pre-round06d landsoftdocker/nl-lib-fastapi:latest` → **fastapi 를 먼저**(`idle in transaction` 0 을 본 뒤) Recreate → `nl-lib-celery-research` → `nl-lib-celery-research-plan` → `nl-lib-celery-control` Recreate("Re-pull image" 끔) → reload. 06c 는 이미 운영에 있었으므로 새 fastapi 가 만든 잡의 params 키(`broaden`·`query_context`)를 옛 워커도 안다 — 끝나지 않은 잡이 실패하지 않는다. 기본값만 되돌리려면 06c 계획의 롤백(기본값 커밋 revert)을 따른다. fastapi 를 `:pre-round06d` 보다 더 옛(06c 전) 이미지로 되돌리면 06d nuxt 가 싣는 탐색 방식 두 칸을 `merge_params` 가 422 로 거부해 딥리서치 시작이 모두 막힌다(Task N9) — 그때는 nuxt 도 함께 되돌린다.
3. 되돌린 뒤에도 dev 에는 06d 가 있다(dev 머지가 배포보다 먼저다 — Task Z4). 고쳐서 다시 배포할지(Task Z6 Step 7 의 `fix/round06d-live-check` 길), dev 에서 06d 를 되돌릴지(revert, 사용자 승인) 정하기 전까지 dev 로 `nuxt` 이미지를 빌드·Recreate 하지 않는다. 06e 세션에도 알린다(06e 배포가 dev 로 nuxt 를 만들면 06d 가 다시 나간다).
