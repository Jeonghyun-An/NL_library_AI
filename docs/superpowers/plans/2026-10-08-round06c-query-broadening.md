# round06 06c 질의 — 시작 질문 넓히기·검색어 합성·탐색 후보 이벤트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** round06 세 줄 병렬(06c 질의 ∥ 06d 진행 화면·입구 ∥ 06e 연구 어시스턴트) 가운데 06c 줄 — spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` §12-2·D25. 회의 결정 ⑥ 시작 질문 넓히기와 ⑦ 검색어 합성을 딥리서치에 넣는다. 개념 하나짜리 짧은 질문이 계획 프롬프트의 측면 목록을 그대로 옮겨 일반 틀 하위질문이 되는 것(06b 계획 30개 중 약 25개)과, 검색어가 동음이의 논문을 데려오는 것(06b 이월 §7-10·§7-11 — '컴퓨팅' 사고력·무선 자원할당)과, D18 이 하위질문에 붙인 '국내 학술논문에서' 군더더기(06b 이월 §7-12)를 다룬다. 탐색 후보 목록 이벤트(Q9 — 06d '검토 중' 더미의 재료)를 runner 가 낸다. 두 스위치(`broaden`·`query_context`)를 기본 0 으로 운영에 배포하고(10/13~14, 워커·fastapi), 배포 당일 고정 질문 5개를 두 갈래로 다시 판정해 결과대로 기본값을 켜는 커밋을 10/17~18 배포에 싣는다(Q4). 06c 는 세 줄 가운데 가장 먼저 `dev` 에 머지·운영 배포한다.

**Architecture:** 딥리서치 계획 태스크(`_plan_deep_research`, `celery-research-plan`)가 `make_plan` 바로 앞에서 새 모듈 `app/services/research/framing.py` 의 `frame_question` 으로 gemma 를 한 번(20초 상한) 불러 질문을 한 문장으로 넓히고 범위 용어 2~4개를 뽑는다(스위치 `broaden`). 계획 프롬프트(`research_plan.yaml`)·`planner.py`·`parse_plan`·`job.plan`(list[str])·승인 API 본문은 한 글자도 바꾸지 않고 `make_plan` 에 넘기는 질문만 바뀐다(D16 을 '프롬프트는 그대로, 입력만 넓힌다'로 읽는다 — D25). 결과는 plan step result(`question_used`·`terms`·`elapsed_ms`)에 담는다 — 스키마 변경 없음(JSONB 안 모양만). 실행 태스크(`_run_deep_research`, `celery-research`)는 마지막 plan step 의 `terms` 를 `ResearchState.terms`·체크포인트에 싣고, runner 의 `_search_query` 한 곳이 첫 검색어와 재검색 제안에 범위 용어를 합성하고 '국내 학술논문에서'를 뗀다(스위치 `query_context`) — 절 소제목·critic 의 하위질문·핵심 개념 입력은 `subq.text` 그대로다. runner 는 회차마다 자기점검 전에 `candidates` 이벤트(이번 검색이 이은 후보의 서지)를 스위치와 무관하게 낸다(저장하지 않는다). 한국어 낱말 맞추기·검색어 합성은 표준 라이브러리만 쓰는 순수 모듈 `app/services/research/terms.py` 에 두고 06e 의 제목 일치가 같은 `contains` 를 쓴다. 화면은 PlanCard 선택 prop·리듀서·타입까지만 만든다(`[id].vue` 바인딩은 06d). 판정 도구 `run_pair.py`·`score.py` 에 갈래별 잡 파라미터·갈래마다 제 계획으로 승인·계획 지표를 더한다.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2(asyncpg — 테스트는 대역 세션), Celery·Redis(redis.asyncio), httpx, jinja2 프롬프트 YAML(`services.prompts.get_prompt`), vLLM(gemma-3-12b), pytest; Nuxt 4·Vue 3.5·TypeScript·vitest(node 환경).

---

## 설계 정본과 이 계획의 자리

- **설계 정본:** `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` — §12-2(06c 질의 — 낱말 맞추기·넓히기·화면 한 줄·검색어 합성·탐색 후보 목록 이벤트·스위치), §12-5(파일 경계·같은 파일 순서), §12-6(일정·머지 문·배포·06c 기본값 커밋), §12-7(06c 판정·자동 테스트·운영 확인), 결정 D25(D16·D18 의 06b 범위를 덮는다), §12-10 Q4(판정 뒤 기본값)·Q9(탐색 후보 목록 이벤트 — 넣음). 형식·관례 정본은 06b 계획 `docs/superpowers/plans/2026-10-06-round06b-vertical-slice.md`(머리 규칙·Task 형식·대역 패턴·Task 37 배포 절차)다.
- **이 계획서:** `docs/superpowers/plans/2026-10-08-round06c-query-broadening.md`. 완료노트·00_status·README 가 이 경로를 적는다.
- **열린 질문의 상태(2026-10-08):** Q1(진행 화면 위 고정 영역 = 크게 보이는 진행 막대 하나 — spec §12-10)·Q7(한국어 드래프트)·Q8(spec 의 판단 모두 동의)·Q9(탐색 후보 목록 이벤트 넣음 — 06c emit, 06d '검토 중' 더미)는 해결됐다. Q1 은 06d 몫이고 06c 는 진행 화면 부품을 고치지 않는다 — 06c 의 `candidates` 이벤트는 그 막대가 아니라 근거 장부 '검토 중' 더미의 재료다. Q2·Q3 은 06e 몫으로 기본값대로 간다(Q2 마지막 단계 이름 '보고서' — 버튼 [보고서 만들기], Q3 근거 칩 표기 범위 S — 주제 카드 칩만) — 06c 는 둘 다 건드리지 않는다. **Q4 는 이 계획의 Task Z6 이 §12-7 규칙대로 정한다**(모두 좋아지면 켬, 엇갈리면 스위치를 나눠 다시 판정, 아니면 0). Q5·Q6 은 시연·리허설.
- **§12-11 '계획에서 정할 것':** 10항목 모두 06d·06e 몫이라 06c 에 걸린 항목은 없다. 06c 는 §12-11 항목을 정하지 않고, 선택 항목 '연구 맥락을 반영한 딥리드 첫 화면'도 하지 않는다. 이 줄이 spec 의 '예'·'제안'을 권고대로 정한 것은 아래 '06c 에서 정한 것' 정함 1~22 — 정함(권고) — 다(완료노트 §6 에 그대로 옮긴다).

---

## 실행 전 알아 둘 것

- **작업 위치:** worktree `C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c`(브랜치 `feat/round06c-query-broadening`) — Task 0 이 **그때의 `dev`** 에서 만든다. 모든 명령은 이 경로의 절대 경로로 쓴다. 저장소 루트 폴더(본 작업 폴더)와 다른 worktree(`.worktrees/round06-spec`·`round06d`·`round06e` 등)는 고치지 않는다 — 여러 세션이 같은 저장소를 쓴다. **본 작업 폴더에서 `git checkout`·`git stash` 를 하지 않는다**(2026-10-02 사고). 계획의 `파일:줄` 은 dev `da80f23`(= worktree `.worktrees/round06-spec` 의 코드) 기준이다(그 위의 spec 문서 커밋 셋 `2860595`·`65e257b`·`c5d05b0` 은 코드를 바꾸지 않는다). 앞 Task 가 바꾼 파일은 "Task Cn 뒤"로 적고, Edit 의 old 문자열은 줄 번호가 아니라 코드 글자로 잡는다.
- **백엔드 테스트:** 파일 하나는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/<파일> -q -p no:cacheprovider`(Git Bash 에서 한글이 깨지면 앞에 `PYTHONIOENCODING=utf-8`). 전체는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`.
- **기준선(2026-10-08 실측 — dev `da80f23` 코드, worktree `.worktrees/round06-spec`. Task 0 이 06c worktree 에서 다시 재고 같은 값이어야 한다):**
  - 백엔드 전체 **`5 failed, 2327 passed, 1 skipped, 2 warnings, 1 error`**. 실패 5 = `test_build_manifest.py` 2(Windows 경로 구분자 — `'originals/KC...KCI_FI001.pdf' == 'originals/KCI_FI001.pdf'`)·`test_loaders.py` 3(`ModuleNotFoundError: No module named 'pymarc'`), 오류 1 = `test_book_chat.py` 수집(`No module named 'FlagEmbedding'`) — 모두 로컬 의존성 문제로 원래 상태이고 06b 계획 머리의 '5 failed · 1 error' 와 같은 여섯 줄이다. 경고 2 는 `core/config.py:16`·`schemas/book.py:47` 의 `PydanticDeprecatedSince20`. 06b 계획 끝의 기대값(백엔드 2273 · vitest 38파일 697)보다 백엔드 54·vitest 2파일 35 많은 것은 06b 계획 뒤 dev 에 들어온 테스트다 — 이 계획의 기대값은 모두 2327 · 40파일 732 에서 센다.
  - 프론트 `nuxi typecheck` 오류 **`0`**, vitest **`Test Files  40 passed (40)` / `Tests  732 passed (732)`**, `npm run build` **`└  ✨ Build complete!`**. typecheck·build 에 나오는 `WARN Duplicated imports "queueLine"` 두 줄(06b 이월 §7-5 — 06d 가 지운다)과 typecheck 의 `[Vue] Resolve plugin path failed: vue-router/volar/sfc-route-blocks … Cannot find module '@vue/language-core'` 는 기준선에도 나오는 경고다.
- **기준선 읽는 법:** 각 Task 의 전체 검증은 "실패 5·오류 1 은 기준선과 같은 세 파일"로 읽는다. 각 Task 의 기대 수는 **"Task 앞 수 + N"** 상대값이다(앞 Task 를 계획 순서대로 마쳤을 때). pytest 끝의 `, 1 warning`·`, 2 warnings`(위 Pydantic 경고)는 기대값에 없어도 같은 결과다. 백엔드 전체는 보통 25~30초(npm 과 함께 돌면 50초 남짓)다.
- **로컬 대역 규칙(새로 만들지 않고 그대로 쓴다):** 로컬에 redis·celery·kombu·aiosqlite·torch·FlagEmbedding·pymilvus 가 없다.
  - `app/tests/test_research_tasks.py` 의 `_load_tasks`·`_stub_missing`·`_forget_on_teardown`·`_FakeSession`·`_FakeJob`·`_patch_pipeline`·`_Harness`·`_Result`(`scalar_one`·`scalar_one_or_none`·`all` 만 있다).
  - `app/tests/test_research_runner.py` 의 `_hits`·`_explore_table`·`_recorder`·`_of`·`_FakeCritic`·`_SuggestingCritic`.
  - `app/tests/test_research_eval.py` 의 `httpx.MockTransport`·`_fake_research_api`·`_report`·`_write_labels`·`_questions`.
  - 프롬프트 테스트는 `services.prompts.get_prompt` + `jinja2.meta.find_undeclared_variables`(`test_research_planner.py:127-139` 선례).
  - async 는 `asyncio.run` 으로 돈다 — `@pytest.mark.asyncio` 는 쓰지 않는다(pytest-asyncio 없음).
  - LLM 은 그 모듈의 `chat` 을 `monkeypatch.setattr` 로 바꾼다(`fake_chat(messages, *, params=None, timeout=None)`).
  - torch 계열을 끌어오는 모듈(`services.search.*`·`services.ingestion.embedder`·`indexer`)은 **함수 안에서** import 한다(함정 13).
- **프론트 테스트:** 새 worktree 에는 `frontend/node_modules`·`.nuxt` 가 없다 — **Task 0 에서 `npm ci` 를 먼저 한다**(`.nuxt` 가 없으면 vitest 가 `TSConfckParseError … .nuxt/tsconfig.app.json` 로 전부 실패한다). 파일 하나는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx vitest run tests/unit/<파일>`, 전체는 `npx vitest run`. `.vue` 는 단위 테스트하지 않는다 — 판단은 `utils/*.ts` 순수 함수로 빼서 vitest 로, `.vue` 는 `npx nuxi typecheck 2>&1 | grep -c "error TS"`(기대 `0`)와 `npm run build 2>&1 | tail -1`(`└  ✨ Build complete!`)로 확인한다. `nuxi typecheck` 는 `tests/` 도 보므로 타입에 필드를 더할 때는 **선택(`?`)으로** 더해 기존 픽스처를 깨지 않는다. **프로젝트에 없는 패키지를 `npx` 로 받지 않는다**(nuxi·vitest 는 프로젝트에 있다).
- **셸:** 명령마다 `cd <절대 경로> &&` 로 시작한다(에이전트 셸은 호출 사이에 cwd 가 초기화된다). 저장소는 `core.autocrlf=true` 라 작업 트리 파일이 CRLF 다 — 기존 파일은 **Edit 도구로** 고친다(Git Bash 의 sed·heredoc 은 LF 줄을 섞는다). 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다.
- **커밋:** `[Feat]`·`[Fix]`·`[Refactor]`·`[Test]`·`[Chore]`·`[Docs]` 접두어 + 한국어 서술형(`[Feat] round06c — …`, 화면은 `[Feat] round06c 프론트 — …`). **`Co-Authored-By` 줄과 "Generated with Claude Code" 줄은 넣지 않는다**(사용자 규칙 — 다른 안내보다 우선). Task 마다 커밋 1~3개, `git add` 는 파일을 하나씩 적는다(`-A`·`.` 금지, `.vue` 경로의 대괄호는 따옴표로).
- **운영 금지:** Task 0 과 파트 C·V 의 어떤 Step 도 운영 서버·운영 DB·운영 Redis·운영 vLLM·운영 API 를 부르지 않는다. `dev` 머지는 사용자 승인 뒤(Task Z3·Z7·Z8·Z9), 서버 명령은 **사용자가** 친다(Task Z4~Z6·Z9 — 계획은 명령과 확인 방법을 준다). 운영 API 에 잡을 만드는 판정(Task Z6)은 사용자 승인 뒤 개발 PC 에서 돌린다.
- **바꾸지 않는 것(D25·§12-2):** `app/services/research/planner.py`(통째로)·`app/domains/nl_library/prompts/research_plan.yaml`·`parse_plan`·`app/tests/test_research_planner.py` 의 계획 고정 테스트·`job.plan`(list[str])·승인 API 요청 본문·`app/api/research.py`·`app/services/research/explorer.py`·`critic.py`·`synthesizer.py`·`research_critique*.yaml`(sha256 잠금)·`research_synthesize.yaml`·`app/services/search/pipeline.py`. 절 소제목·critic 의 하위질문·핵심 개념 입력은 `subq.text` 그대로다. `research_tasks.py` 의 회수기 `reap_stale_research` 도 고치지 않는다.
- **함정(`docs/ops/recurring-gotchas.md`):** 13(무거운 import 는 함수 안)·14(스키마 변경 없음 — `create_all` 은 있는 테이블에 칼럼을 못 더한다, JSONB·잡 파라미터 안 모양만)·15(프롬프트에 예시·견본·"예:"·"예시" 금지, 개수는 코드가 자른다)·18(LLM 을 기다리는 동안 읽기 트랜잭션을 쥐지 않는다)·19(실제로 나는 실패 타입만 잡는다 — `except Exception` 폴백은 `SoftTimeLimitExceeded` 까지 삼킨다)·25(`guided_*` 를 params 에 두지 않는다 — `test_prompts.py` 가 새 YAML 도 훑는다)·26(LLM 이 입력을 베낀다 — 넓히기가 원 질문을 그대로 내는 것도 정상으로 받는다). 17(계획 워커 `celery-research-plan` 에는 GPU·모델 캐시가 없다 — 넓히기는 gemma `chat` 한 번뿐이고 검색·임베딩·리랭커를 부르지 않는다. 원문 대목·리랭커·Milvus 는 그 프로세스에서 돌리지 않는다)·27(vLLM 도구 호출 파서 — 넓히기는 tools 를 싣지 않는 평문 `chat` 이라 걸리지 않는다)은 하지 않을 것의 근거다. 배포(Task Z4)는 3·4·12·16·18·20·24 도 본다.

---

## 06c 에서 정한 것 — 정함(권고) (spec 이 '예'·'제안'으로 둔 것과 이 계획의 보강 — 결정과 근거)

아래 22개는 spec 이 '예'·'제안'으로 열어 둔 것을 권고대로 정했거나 구현에 필요한 보강을 더한 것이다 — 계획·완료노트는 '정함(권고) n' 으로 부르고, 줄여 '정함 n' 으로도 쓴다. spec 과 다르게 정한 셋(정함 7·10·21)은 **Task Z2 가 spec 을 이 결정에 맞춘다**(CLAUDE.md §3 — 코드가 실제다). spec 보다 자세히 정한 규칙(정함 9 의 입력 이름표 떼기·정함 12 의 `compose_query` 규칙)도 같은 Task 가 spec 에 적는다. 후보 이벤트의 이름·키(정함 3)는 다른 줄과의 계약이라 마무리로 미루지 않고 계획 확정 전에 spec 을 맞췄다(spec 브랜치 커밋 `c5d05b0` — Task 0 Step 1 이 dev 에 들어갔는지 확인한다).

| # | 결정 | 근거 |
|---|---|---|
| 정함 1 | **넓히기는 새 모듈 `app/services/research/framing.py`** — `planner.py` 는 한 글자도 고치지 않는다. 계획 태스크가 `make_plan` 처럼 함수 안에서 import 한다 | §12-2 '바꾸지 않는 것'을 파일 단위로 지킨다. `TestPlan` 대역은 `services.research.planner` 모듈을 통째로 바꿔치기하므로(`test_research_tasks.py:850-860`) 넓히기가 planner 안에 있으면 기존 테스트가 import 오류로 깨진다 |
| 정함 2 | **프롬프트 `app/domains/nl_library/prompts/research_frame.yaml`** — parser `plain`, params `max_tokens: 600`·`temperature: 0.2`, 변수 `question` 하나, 출력 JSON `{"question", "terms"}`, 예시 없음 | spec 의 '예'를 확정. 600 은 원 질문 500자 + 더한 말 + 용어 넷 + JSON·펜스 상한, 0.2 는 `research_concepts.yaml` 과 같다 |
| 정함 3 | **탐색 후보 이벤트 이름 `candidates`, 하위질문 키 `subq_idx`** | runner 의 `search`·`critique`·`counters` 와 `_StepRef.event`(`research_tasks.py:141`)가 모두 `subq_idx` 다 — 06d 리듀서가 한 키로 하위질문을 찾는다. 06d 와의 계약이라 계획 확정 전에 spec §12-2 를 이 글자로 맞췄다 |
| 정함 4 | **`candidates` 는 회차마다 늘 한 번** — 이은 근거가 없어도 `papers: []`. 순서는 `search` → `counters` → `candidates` → (자기점검 LLM) → `critique`. 스위치 0 이어도 회차마다 이벤트가 하나 는다 — 이벤트 종류의 전체 순서를 글자 그대로 단언하는 기존 테스트 `TestRoundEvents.test_counters_follow_each_search` 하나를 Task C7 이 고친다 | 06d 의 '다음 회차 후보가 앞 더미를 갈음'이 빈 목록으로도 성립한다. `papers` 순서 = 이번 검색이 이 하위질문에 이은 순서(`linked`) |
| 정함 5 | **plan step 결과에 `elapsed_ms` 를 더한다** — `{"subquestions", "question_used", "terms", "elapsed_ms"}`, 단계를 연 뒤(넓히기 + 계획) `time.monotonic()` 차의 정수 밀리초 | §12-7 계획 시간 지표가 읽는다. GET 의 steps 에는 시각 칸이 없다(`api/research.py:368-378`) — API·스키마를 바꾸지 않는다 |
| 정함 6 | **중간 알림은 `broaden` 1 일 때만** — 넓히기 뒤 결과와 무관하게 한 번 `_save_progress(db, step, {"question_used", "terms"})`. `broaden` 0 이면 넓히기 함수를 부르지 않는다 | 스위치 0 이면 계획 단계의 step 이벤트 순서까지 지금과 같다(완료 result 의 칸만 는다) |
| 정함 7 | **`content_words` 보강:** NFKC → casefold → **문장부호(`[^\w\s]`)를 공백으로** → 어절 나누기 → 어절 끝 조사 하나 떼기(맞는 것 중 가장 긴 것, 남는 것이 2자 미만이면 떼지 않음) → 2자 이상·`QUESTION_WORDS` 아님·**`PARTICLES` 자체(조사만 남은 어절) 아님** → 처음 나온 순서·중복 없이. **spec §12-2 정의와 다르다**(문장부호·조사 어절 규칙이 없다) | '궁금해?'·논문 버튼 꼴(「…」에서, ·)이 늘 원문으로 떨어지지 않게 한다. 「…」를 공백으로 바꾸면 남는 '에서' 같은 조사 어절은 내용어가 아니다 |
| 정함 8 | **`contains` 는 spec 글자 그대로**(NFKC → casefold → 공백 제거 뒤 부분 문자열, 아니면 word 의 낱말이 모두 순서대로) | 06e 제목 일치가 같은 함수를 쓴다(§12-4) |
| 정함 9 | **terms 정리:** 문자열만 → NFKC → 공백 정리 → 빈 것·`TERM_MAX_CHARS`(30)자 넘는 것 버림 → casefold 기준 중복 제거 → `MAX_TERMS`(4)에서 자름. 넓힌 질문이 공백 정리 뒤 비었거나 `FRAMED_QUESTION_MAX`(500)자를 넘으면 실패(원문). 넓힌 질문은 맨 앞 입력 이름표(`질문:`·`질문：` — `_ECHO_LABEL`)를 떼고 본다 — 모델이 user 메시지를 이름표째 옮기면 낱말 검사를 통과해 계획 입력·`question_used` 에 이름표가 실린다(함정 26, Task C3 `test_echoed_input_label_is_stripped`). 낱말 검사는 `content_words` 에 더해 원 질문의 **한 글자 어절**(조사·`QUESTION_WORDS`·`ONE_CHAR_FUNCTION_WORDS` — 및·등·왜·더·수·것 같은 잇는 말 — 제외)도 본다. 한 글자는 `contains`(부분 문자열)가 아니라 **어절 경계**로 대조한다 — 넓힌 문장을 같은 방식(NFKC·casefold·문장부호 공백)으로 나눈 어절 가운데 그 글자이거나 '그 글자 + `PARTICLES` 하나'(암의·뇌를·암에서)인 것이 있어야 한다(`_has_one_char_word`, C3 품질 검토 두 번, `test_question_that_drops_a_one_char_word_is_refused`·`test_one_char_word_is_matched_as_a_whole_word`) | 용어가 검색어에 붙으므로 긴 문장이 용어로 들어오면 검색어가 망가진다. 500 = `ResearchCreate.question` 상한(`api/research.py:90`). 한 글자 명사(암·뇌·법)는 `content_words` 의 2자 바닥에 걸려 '암 연구가 궁금해'(내용어 [])에 지어낸 주제·'암'→'종양'이 낱말 검사를 지나간다 — 계약(06e·score.py)은 두고 넓히기 검사만 엄하게 본다. `contains` 로 보면 '방법'·'기법'의 '법', '암호화'의 '암', '뇌물'의 '뇌'에 맞아 지어낸 주제가 지나간다('법'은 넓힌 문장에 흔히 붙는 '방법' 때문에 사실상 아무것도 막지 못한다). 목록에 없는 한 글자 말이 빠지거나 붙여 쓴 꼴('암환자')로 원문으로 물러나는 것은 안전한 쪽이다 |
| 정함 10 | **넓히기 실패 타입 `FRAME_FAILURES = (httpx.HTTPError, ValueError, KeyError, IndexError)`** — `chat` 이 실제로 내는 전송·상태·JSON 해석·응답 모양 오류. 원문으로 물러나는 범위는 이것과 빈 응답·검사 실패이고, 그 밖의 예외(코드 결함·태스크 제어 예외)는 올려 계획 실패로 닫는다. **spec §12-2 '오류 … 면 원 질문으로 계획한다 — 잡을 실패시키지 않는다' 와 다르다** | 함정 19 — 폴백이 `except Exception` 이면 `SoftTimeLimitExceeded` 까지 삼키고, 코드 결함도 '넓히기 실패 — 원문'으로 숨어 스위치를 켠 판정이 넓히기 없이 나온다 |
| 정함 11 | **검색어 합성은 runner 의 `_search_query(state, text)` 한 곳** — 첫 검색어(`runner.py:188`)와 재검색 제안(`_recheck_query` `:169` 에서 `_next_query` 에 넘기기 전). **`_next_query` 는 고치지 않는다** | 제안을 합성한 꼴로 바꿔 넘기므로 중복 비교·`subq.queries`·critic `tried_queries`(`critic.py:205`)·회차 기록의 `query`·`next_query`·`search` 이벤트의 `query` 가 모두 실제로 보낸 글이다(`explorer.py:98-100` 원칙). `:318` 은 이미 합성한 `next_query` 를 받는다 |
| 정함 12 | **`QUERY_FILLERS`·`compose_query` 도 `terms.py`** — 붙일지는 지금까지의 글(이어 붙인 용어 포함)에 `contains` 인지로 정하고, 군더더기를 지워 비면 원문으로 물러나며, 빈 용어는 건너뛴다(두 번 거쳐도 같다 — 군더더기만으로 된 글은 예외). **spec §12-2 의 '하위질문에 `contains` 가 아닌 것을 붙인다' 보다 자세하다** — Task Z2 가 spec 을 이 글에 맞춘다 | 순수 낱말 함수를 한 파일에 — score.py 복사본·06e 가 한 곳만 본다. 이어 붙인 용어와도 견주므로 서로 품는 용어가 두 번 붙지 않고, 합성한 글(재검색 제안이 고쳐 쓴 앞 검색어)을 다시 넣어도 용어가 두 번 붙지 않는다. 빈 용어를 건너뛰어야 끝 공백 때문에 두 번 거친 값이 달라지지 않는다(Task C1 '알아 둘 것') |
| 정함 13 | **`state.terms` 는 스위치와 무관하게 늘 담는다**(마지막 plan step result 의 `terms`, 없으면 `[]`). 검색어에 쓰는 것은 `query_context` 1 일 때뿐 | 나눠 판정할 때 `--plan shared` + `{broaden 1, query_context 1}` 이 '계획은 같고 검색어만 다른' 갈래가 된다(정함 20) |
| 정함 14 | **score.py 는 `contains` 만 복사한다** | score 는 `content_words` 를 쓰지 않는다. 복사본과 원본은 공용 고정 예제의 `contains` 칸으로 묶인다 |
| 정함 15 | **공용 고정 예제 `frontend/tests/fixtures/term_checks.json`** | `marker_checks.json` 선례 — 06e 화면 `keywordSpans` 도 같은 칸을 읽을 수 있다 |
| 정함 16 | **run_pair 에 `--param0`(기본 `{"critic_scope": 0}`)·`--param`(기본 `{"critic_scope": 1}`)·`--plan shared\|own`(기본 shared)** — 기본값만 주면 동작이 그대로다(출력 머리에 갈래 파라미터·계획 모드 한 줄 `갈래 0 {…} · 갈래 1 {…} · 계획 shared` 만 는다 — 완료노트에 어느 파라미터로 돌렸는지 남기는 재료) | 기본값을 켠 뒤에도 갈래 0 을 '지금 방식'으로 박아 둘 수 있다 |
| 정함 17 | **score.py `--plan-only`** — 라벨 없이 계획 지표만 찍는다 | 대조군은 '넓히기가 구체적인 질문을 그대로 두는가'만 본다 |
| 정함 18 | **대조군 질문 파일 `scripts/research_eval/questions_control.json`** — 실제 소장 논문 제목(`KCI_FI001933966`·`KCI_FI001023392`)으로 `paperResearchQuestion`(`frontend/utils/paperResearch.ts:17-27`) 꼴 질문 2개 | 고정 5문항 파일에 섞지 않는다(분모가 바뀐다 — §12-7) |
| 정함 19 | **시간 목표 'p50 5초 이하'는 판정 지표로만.** 코드 상한은 `BROADEN_TIMEOUT = 20`초(`chat` 의 최악은 timeout + 10초 — `llm_client.py:228-231`), `asyncio.timeout` 을 따로 걸지 않는다 | 잡 데드라인(`JOB_DEADLINE`)의 `TimeoutError` 판정(`research_tasks.py:497-505`)과 섞이지 않게 |
| 정함 20 | **스위치를 나눠 다시 판정하는 법** — `query_context` 효과: `--plan shared --param0 {broaden 0, query_context 0} --param {broaden 1, query_context 1}`(갈래 1 의 계획 단계가 terms 를 내지만 승인은 갈래 0 계획 — 검색어만 다르다). `broaden` 효과: `--plan own --param {broaden 1, query_context 0}`(계획만 다르다) | `broaden` 0 이면 terms 가 비어 `query_context` 단독 갈래는 군더더기만 뗀다 — spec '`query_context` 단독은 shared 모드'를 이렇게 읽는다 |
| 정함 21 | **화면 판단 = 순수 함수** `questionUsedFromSteps(steps, question)`(원 질문과 같으면 `null`)·`understoodLine(questionUsed)`(`이렇게 이해했어요: …`). PlanCard 검증은 이 두 함수의 vitest 와 `nuxi typecheck`·`npm run build` 로 한다. **spec §12-2 'vitest 로 그리기·숨기기까지 검증' 과 다르다** | 프론트 vitest 가 node 환경이라(`vitest.config.ts` `environment: "node"`, `@vue/test-utils`·DOM 환경 없음) 컴포넌트를 그리지 못한다 — 새 패키지를 들이지 않는다 |
| 정함 22 | **PlanCard 는 새 CSS 없이 `rs-muted` 를 다시 쓴다**(`<p class="rs-muted rs-plan__understood">`) | `research.css` 는 06d 파일이다(§12-5). `rs-plan__understood` 는 스타일 없는 고리다 — 06d 는 계획 중 카드에 같은 클래스 묶음을 달고 CSS 규칙은 더하지 않는다(`rs-muted` 로 줄이 맞는다. 나중에 스타일을 줄 때 한 규칙으로 함께 바뀐다) |

---

## 다른 줄과의 경계·머지 문 (§12-5·§12-6)

**06c 가 다른 줄에 주는 것(계약 — 06c 머지 뒤 이름·모양을 바꾸지 않는다)**

| 받는 줄 | 06c 가 주는 것 | 받는 쪽이 할 일 |
|---|---|---|
| 06e | `app/services/research/terms.py` 의 `contains(text, word) -> bool`·`content_words(text) -> list[str]`·`PARTICLES`·`QUESTION_WORDS` | 제목 키워드 일치는 06c 의 `dev` 머지 뒤 dev 를 받아 `from services.research.terms import contains` 로 쓴다. 06c 전에 같은 함수를 따로 두지 않는다 |
| 06e | 공용 고정 예제 `frontend/tests/fixtures/term_checks.json` 의 `contains` 칸 | 화면 `keywordSpans` 의 일치 규칙 테스트가 이 칸을 읽을 수 있다. 사례를 더하면 06c 의 두 테스트(`test_research_terms.py`·`test_research_eval.py`)도 통과해야 한다 |
| 06d | `questionUsedFromSteps(steps, question)`·`understoodLine(questionUsed)`(`frontend/utils/researchEvents.ts`), PlanCard 선택 prop `questionUsed` | `[id].vue` 의 계획 중 대기 카드(`:80-83`)와 승인 대기 PlanCard(`:84-92`)에 `questionUsedFromSteps(view.steps, view.question)` 를 잇는다. 탐색 중 PlanCard(`:97`)는 06d 판단 |
| 06d | SSE 이벤트 `candidates` — `{"kind": "candidates", "subq_idx", "round", "papers": [{cnts_id, title, personal_author, pub_date}]}`, 회차마다 `search`·`counters` 뒤·`critique` 앞 한 번, 빈 목록도 냄, 스냅숏·rounds 에 없음 | 이벤트 타입·`ResearchEvent` 합집합·리듀서·`evidenceLedger.ts` '검토 중' 더미 |
| 06d | plan step 결과의 `question_used`·`terms`·`elapsed_ms`(06c 는 `StepResult` 에 선택 칸만 더한다) | 06d 는 이 세 칸을 다시 정의하지 않는다 |

**같은 파일을 두 줄이 고치는 곳**
- `frontend/utils/researchEvents.ts`·`frontend/types/research.ts` — 06c 는 `StepResult` 칸 셋과 함수 둘만, 06d 는 `queueLine` 다시 내보내기 지우기·회차 미세 상태 라벨·`candidates` 타입과 리듀서. 서로 다른 함수·선언만 고치고, 늦게 머지하는 06d 가 dev 를 받아 맞춘다.
- `frontend/components/research/PlanCard.vue` 는 06c 만 고친다(06d 는 `[id].vue` 의 계획 중 카드에 같은 클래스 `rs-muted rs-plan__understood` 를 달 뿐 CSS 를 더하지 않는다).
- `app/workers/research_tasks.py` 는 06c 파일이다(계획 부분·실행 시작). 06e 는 고치지 않는다.
- 06c 는 `pages/research/[id].vue`·`assets/css/research.css`·`work.css`·`components/work/*`·`app/services/research_work/*`·`app/api/research_*.py`·`AppSidebar.vue`·`app/api/history.py`·`pages/index.vue` 를 건드리지 않는다.

**머지·배포 문(§12-6)**
- **06c 가 세 줄 중 먼저 `dev` 머지·운영 배포한다(10/13~14, 워커·fastapi).** 06d·06e 는 06c 운영 배포(Task Z4)가 끝난 뒤에만 dev 에 머지한다 — 06c 배포 이미지는 그때의 dev 로 만들므로, 먼저 들어온 06e 백엔드가 nuxt 없이 함께 나가지 않게 한다. Task Z3·Z4 가 dev 에 06d·06e 머지가 없는지 확인하고, Task Z4 끝에 두 줄 세션에 머지 문이 열렸다고 알린다.
- 06c 의 화면 한 줄(Task V3)은 dev 에 들어간 뒤 06d 의 `[id].vue` 바인딩과 함께 10/17~18 nuxt 배포에 나간다. **06c 배포는 nuxt 를 다시 만들지 않는다.**
- **06c 기본값 커밋(Q4 — 판정 결과)은 판정 날 배포하지 않고 10/17~18 배포(06e·06d)에 싣는다**(배포 한 번을 아끼고 10/19~21 운영 확인이 켠 상태로 돈다). 새 잡의 params 는 fastapi 가 만들 때 기본값으로 채워 저장하므로(`api/research.py:235`) fastapi 가 바뀌어야 켜진다 — 그 배포가 celery-research·celery-research-plan·fastapi 를 같은 이미지로 맞춘다.
- 랜딩 논문 예시 셋(`pages/index.vue` — 06d 파일, `89cede3`)은 06c 판정 질문(library·elderly·multicultural)과 같은 문장이다. 기본값을 켠 뒤 그 보고서를 다시 보고(Task Z9), 바꿀 것이 있으면 06d 가 고친다.

---

## 파트 순서와 Task ID

Task 는 파트 영문 접두 + 번호로 부른다(다른 Task 를 부를 때도 'Task C3' 꼴 그대로). 다른 줄의 Task 는 ID 가 아니라 내용으로 부른다(예: '06d 계획의 candidates 리듀서').

| 파트 | Task | 내용 |
|---|---|---|
| — | Task 0 | worktree·기준선 확인(선행 조건 — spec 의 후보 이벤트 계약이 dev 에 있는가) |
| C 백엔드 핵심 | Task C1 → C7 | C1 `terms.py`·공용 고정 예제 · C2 잡 파라미터·`ResearchState.terms` · C3 `research_frame.yaml`·`framing.py` · C4 계획 태스크에 넓히기·plan step 결과·중간 알림 · C5 실행 태스크가 `terms` 를 상태·체크포인트에 · C6 검색어 합성 · C7 `candidates` 이벤트 |
| V 판정 도구·화면 한 줄 | Task V1 → V3 | V1 `run_pair.py` `--param0`·`--param`·`--plan`·대조군 파일 · V2 `score.py` 계획 지표·`--plan-only`·`contains` 복사본·README 06c 재판정 절차 · V3 `questionUsedFromSteps`·`understoodLine`·PlanCard `questionUsed` |
| Z 마무리 | Task Z1 → Z9 | Z1 전체 회귀·정적 리뷰·반영 · Z2 문서(완료노트·00_status·spec 맞춤) · Z3 dev 머지(사용자 승인) · Z4 운영 배포(사용자) · Z5 운영 처음부터 끝까지 1회 · Z6 두 갈래 재판정 · Z7 기본값 커밋 · Z8 배포·판정 기록 · Z9 10/17~18 배포 뒤 확인 |

**의존·병렬:** 파트 C 는 ① C1 ∥ C2 → ② C3(C1) → C4(C2·C3) → C5(C4) ③ C6(C1·C2) → C7(C6, `test_research_tasks.py` 는 C5 뒤). 파트 V 는 V1 → V2(C1 의 고정 예제 필요)와 V3(독립 — 백엔드 코드에 기대지 않는다). 같은 파일 사슬(`research_tasks.py` C4 → C5, `runner.py` C6 → C7, `test_research_tasks.py` C4 → C5 → C7, `test_research_runner.py` C6 → C7, `test_research_eval.py` V1 → V2)은 이 순서로 적용한다 — 뒤 Task 의 Edit old 는 앞 Task 뒤 글자다. 파트 Z 는 C·V 가 모두 끝난 뒤 차례로 한다.

---

## 파일 구조 (만들고 고칠 파일과 책임)

**백엔드 — 새 파일** (`app/` 기준)

| 파일 | 책임 | Task |
|---|---|---|
| `services/research/terms.py` | 한국어 낱말 맞추기(`content_words`·`contains`)와 검색어 합성(`compose_query`), 상수 `PARTICLES`·`QUESTION_WORDS`·`QUERY_FILLERS` — 표준 라이브러리만(06e·score.py 복사본이 같은 규칙) | C1 |
| `services/research/framing.py` | 시작 질문 넓히기 — gemma 1회·20초(`frame_question`), 응답 해석·원 질문 낱말 보존 검사(`parse_frame`), 범위 용어 정리(`clean_terms`), 실패면 원문(`unframed`·`FRAME_FAILURES`) | C3 |
| `domains/nl_library/prompts/research_frame.yaml` | 넓히기 프롬프트(plain·600·0.2, 변수 `question`, 출력 `{"question", "terms"}`, 예시 없음) | C3 |
| `tests/test_research_terms.py` | `content_words`·`contains`·`compose_query`·공용 고정 예제 | C1 |
| `tests/test_research_framing.py` | 프롬프트 고정·해석·검사·실패 타입·용어 정리 | C3 |

**백엔드 — 고칠 파일**

| 파일 | 고치는 것 | Task |
|---|---|---|
| `services/research/state.py` | `DEFAULT_PARAMS`·`_PARAM_BOUNDS` 에 `broaden`·`query_context`(int 0~1, 기본 0), `ResearchState.terms`, 스냅숏 왕복 | C2 |
| `workers/research_tasks.py` | `_plan_deep_research` — 넓히기·중간 알림·plan step 결과(`question_used`·`terms`·`elapsed_ms`)(C4), `_plan_terms`·`_run_deep_research` 가 terms 를 새 상태에(C5) | C4·C5 |
| `models/research.py` | plan step result 모양 주석(:100) | C4 |
| `services/research/runner.py` | `_search_query`·첫 검색어·재검색 제안 합성(C6), 회차마다 `candidates` emit(C7) | C6·C7 |
| `tests/test_research_state.py` | 스위치 경계(0·1 만)·기본값 0(`test_query_switches_are_off_by_default` — 기본값을 단언하는 둘 중 하나)·`terms` 스냅숏 왕복·옛 스냅숏 | C2 |
| `tests/test_research_api.py` | 생성 API 가 스위치를 저장(`test_query_switches_are_saved_off_unless_asked` — 기본값을 단언하는 둘 중 하나)·0·1 밖은 422 | C2 |
| `tests/test_research_tasks.py` | `_Harness.framed`·`TestPlan._patch(…, frame=)`·계획 넓히기 테스트(C4), `_patch_pipeline(…, terms=)`·`TestPlanTerms`(C5), `TestLiveProgress` 하나(C7) | C4·C5·C7 |
| `tests/test_research_runner.py` | `TestQueryComposition`(C6), `test_counters_follow_each_search` 기대 순서 고침·`TestCandidatesEvent`(C7) | C6·C7 |
| `tests/test_research_eval.py` | run_pair 새 인자·대조군 파일(V1), score 계획 지표·`--plan-only`·복사본(V2) | V1·V2 |

**판정 도구** (`scripts/research_eval/`)

| 파일 | 책임 | Task |
|---|---|---|
| `run_pair.py` | 갈래별 잡 파라미터 `--param0`·`--param`(JSON 객체)과 갈래마다 제 계획으로 승인 `--plan own` — 기본값만 주면 06c 전과 동작이 그대로(출력 머리에 갈래 파라미터·계획 모드 한 줄만 는다) | V1 |
| `questions_control.json`(새) | 대조군 — 소장 논문 제목으로 만든 논문 버튼 꼴 질문 2개(고정 5문항과 따로) | V1 |
| `score.py` | 갈래마다 '넓힌 질문'·'계획 지표'(일반 틀·근거 0편·insufficient·계획 시간) 두 줄과 합계 한 줄, `--plan-only`(라벨 없이), `contains` 복사본 — 기존 출력 글자는 그대로 | V2 |
| `README.md` | '06c 재판정 (넓히기·검색어 합성)' 절차(V2), 판정 결과 요약(Task Z8) | V2·Z8 |
| `labels/*.csv` 5개 | 06c 판정에서 새로 나온 논문 줄만 덧붙인 라벨(`git add -f` — 리허설에서 다시 쓴다) | Z8 |

**프론트** (`frontend/` 기준)

| 파일 | 책임 | Task |
|---|---|---|
| `tests/fixtures/term_checks.json`(새) | `content_words`·`contains` 공용 고정 예제 — `terms.py`·score.py 복사본·06e `keywordSpans` 가 같은 칸을 읽는다 | C1 |
| `types/research.ts` | `StepResult` 선택 칸 `question_used`·`terms`·`elapsed_ms` | V3 |
| `utils/researchEvents.ts` | `questionUsedFromSteps`(원 질문과 같으면 null)·`understoodLine`('이렇게 이해했어요: …') — 06d 가 `[id].vue` 에서 부른다 | V3 |
| `components/research/PlanCard.vue` | 선택 prop `questionUsed`(기본 null), 머리 `<h2>` 뒤 한 줄(`rs-muted rs-plan__understood`, 새 CSS 없음) | V3 |
| `tests/unit/researchEvents.test.ts` | 두 함수와 계획 중간 알림 리듀서의 describe 셋 | V3 |

**문서**

| 파일 | 책임 | Task |
|---|---|---|
| `docs/roadmap/round06c-완료노트.md`(새) | 왜·한 일·리뷰·검증·결정(정함 1~22)·이월(Z2), 배포·운영 확인·판정(§5 — Z8), 10/17~18 배포 뒤 확인(§5-6 — Z9) | Z2·Z8·Z9 |
| `docs/roadmap/00_status.md` | round06 줄과 06c 하위 줄·다음 할 일·라운드 이력(round06 칸만) | Z2·Z8·Z9 |
| `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` | 머리 상태 줄·D25·§12-2·§12-7 을 코드에 맞춤(Z2), 판정 결과·§12-10 Q4 해결(Z8) | Z2·Z8 |
| `docs/ops/recurring-gotchas.md` | 운영 확인·판정에서 라이브에서만 드러난 것이 있을 때만 `## 28.` | Z8 |

**하지 않는 것:** 넓힌 문장을 고쳐 같은 잡에서 다시 계획하기(대회 뒤 — 사용자 "고도화로 냅두고"), 탐침 검색으로 넓히기(계획 워커에 GPU 없음), terms 를 critic·핵심 개념에 공급(대회 뒤), 하위질문을 차례로 만들기·인터뷰(대회 뒤), 계획 승인 단계 더하기(고치기는 지금처럼 하위질문 편집), 후보 이벤트의 화면(06d), `[id].vue` 바인딩(06d), 06c 배포에서 nuxt 다시 만들기.

---

## 작업

### Task 0: worktree·기준선 확인

**왜:** 06c 는 세 줄 가운데 처음으로 `dev` 에서 따는 줄이다. spec 의 후보 이벤트 계약(이름 `candidates`·키 `subq_idx`)과 10-08 회의 개정이 dev 에 있어야 06c·06d 가 같은 정본을 읽는다 — 그 확인이 이 계획의 선행 조건이다. worktree 는 본 작업 폴더에서 checkout 하지 않고 `git worktree add` 로 만든다(다른 세션이 깨진다). 시작 전에 테스트 수를 재 두어야 각 Task 가 더한 수와 깨뜨린 것을 가를 수 있다.

**Files:** 없음 (작업 환경과 기준선만 — 이 계획서가 dev 에 없을 때만 Step 3 의 계획 커밋 1개)

**알아 둘 것:**
- 로컬 `dev` 는 `origin/dev` 보다 뒤처져 있을 수 있다. `dev` 를 checkout 한 worktree 가 없으면 `git fetch origin dev:dev` 로 빨리 감는다(checkout 이 아니다). `refusing to fetch into branch 'refs/heads/dev' checked out at …` 이 나오면 그 worktree(대개 남은 `.worktrees/dev-merge`)가 있는 것이다 — 그 worktree 가 지금 쓰이는지 사용자에게 묻고, 쓰이지 않으면 `git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge` 뒤 다시 한다.
- 2026-10-08 실측: 로컬 `dev` = `origin/dev` = `da80f23`. spec 개정 커밋 셋 — `2860595`(10-08 회의 결정 D19~D27·§12)·`65e257b`(Q1·Q8·Q9 답)·`c5d05b0`(§12-2 탐색 후보 이벤트를 `candidates`·`{subq_idx, round, papers}` 로 맞춤 — 06d 와의 계약) — 은 브랜치 `docs/round06-meeting-1008-spec`(worktree `.worktrees/round06-spec`)에만 있다. 그 브랜치(세 줄 계획서가 함께 실릴 수 있다)를 dev 에 머지하는 것은 계획 확정 단계(사용자 승인)의 몫이다 — 이 Task 는 확인만 하고, 없으면 멈춘다.
- `.worktrees/dev-merge` 는 06b 가 남긴 빈 폴더다(06b 완료노트 §7-17, worktree 등록은 없음). `git worktree add` 는 빈 폴더에 그대로 만든다.
- 백엔드는 PATH 의 `python`(3.11.15, pytest 9.1)으로 돌린다.

- [ ] **Step 1: 선행 조건 — spec 개정과 후보 이벤트 계약이 dev 에 있는가**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline -1 dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI merge-base --is-ancestor 2860595 dev && echo "2860595 dev 에 있음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI merge-base --is-ancestor 65e257b dev && echo "65e257b dev 에 있음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI merge-base --is-ancestor c5d05b0 dev && echo "c5d05b0 dev 에 있음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI show dev:docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md | grep -c "subq_idx, round, papers"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI show dev:docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md | grep -c "subq_id, round"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline --merges da80f23..dev | grep -cE "feat/round06(c|d|e)-"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline da80f23..dev -- app frontend infra scripts docker-compose.yml
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c "worktrees/round06c "
git -C C:/Users/LANDSOFT/mygit/NL_library_AI branch --list feat/round06c-query-broadening
```

Expected:
- `fetch` — 이미 같으면 출력 없음, 앞서 있으면 `da80f23..<커밋>  dev -> dev` 한 줄
- `log -1 dev` — spec 브랜치를 머지한 커밋 한 줄(이 커밋을 '분기 dev' 로 적어 둔다 — 완료노트 머리에 쓴다)
- `2860595 dev 에 있음`·`65e257b dev 에 있음`·`c5d05b0 dev 에 있음` 세 줄(spec 브랜치를 squash·rebase 로 넣어 해시가 바뀌었으면 줄이 빠진다 — 그때는 아래 grep 둘과 `git show dev:docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md | grep -c "Q9. 탐색 후보 목록 이벤트"` 가 `1` 인지로 판단한다)
- `subq_idx, round, papers` → `1`, `subq_id, round` → `0`(2026-10-08 `c5d05b0` 의 spec 에서 실측한 값과 같다)
- 06c·06d·06e 머지 → `0`
- `da80f23..dev` 의 코드 커밋 → 빈 출력. 줄이 나오면(다른 라운드가 dev 에 코드를 넣었다) 적어 두고, 아래 Step 4·5 의 기준선을 새로 잰 값으로 갈음한다 — 각 Task 의 상대값('앞 수 + N')은 그대로 쓴다
- worktree → `0`, 브랜치 → 빈 출력

멈출 때: 세 커밋 중 하나라도 없거나(위 squash 예외 말고) `subq_idx` 확인이 `1`·`0` 이 아니면 **여기서 멈추고 사용자에게 알린다** — spec 브랜치의 dev 머지(후보 이벤트 계약 커밋 포함)가 먼저다(사용자 승인). 06c 를 옛 spec 의 dev 에서 따지 않는다. 06d·06e 머지가 이미 있으면 머지 문(§12-6)과 어긋나므로 역시 멈추고 묻는다.

- [ ] **Step 2: worktree·브랜치를 dev 에서 만든다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add -b feat/round06c-query-broadening .worktrees/round06c dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c status --short --branch
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c config --show-origin core.autocrlf
```

Expected:
- `Preparing worktree (new branch 'feat/round06c-query-broadening')` 와 `HEAD is now at <Step 1 의 dev 커밋> …`
- `status` — `## feat/round06c-query-broadening` 한 줄(변경 줄 없음)
- `log -1` — Step 1 의 dev 커밋과 같은 줄
- `file:C:/Program Files/Git/etc/gitconfig	true` — 작업 트리 파일이 CRLF 다. 기존 파일은 Edit 도구로 고친다

- [ ] **Step 3: 이 계획서를 브랜치에 넣는다 — dev 에 이미 있으면 건너뛴다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c cat-file -e HEAD:docs/superpowers/plans/2026-10-08-round06c-query-broadening.md && echo "계획서 있음" || echo "계획서 없음"
```

`계획서 있음` 이면 이 Step 은 끝이다. `계획서 없음` 이면 이 계획서를 연 파일 경로를 `PLAN_SRC` 에 넣고 브랜치의 첫 커밋으로 넣는다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && cp "$PLAN_SRC" docs/superpowers/plans/2026-10-08-round06c-query-broadening.md && git add docs/superpowers/plans/2026-10-08-round06c-query-broadening.md && git commit -m "[Docs] round06c 계획 — 시작 질문 넓히기·검색어 합성·탐색 후보 이벤트(Task 0 · C1~C7 · V1~V3 · Z1~Z9, 정함 1~22). 스위치 broaden·query_context 를 기본 0 으로 배포하고 배포 당일 고정 질문 5개 두 갈래 판정 뒤 기본값을 정한다(Q4), 기본값 커밋은 10/17~18 배포에 싣는다"
```

Expected: 커밋 1개, `git status --short` 빈 출력.

- [ ] **Step 4: 백엔드 기준선**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 마지막 줄 `5 failed, 2327 passed, 1 skipped, 2 warnings, 1 error`(25~30초). 그 위 요약 줄은 정확히 다음 여섯이다.

```text
FAILED tests/test_build_manifest.py::test_build_manifest_matching
FAILED tests/test_build_manifest.py::test_build_manifest_csv_input
FAILED tests/test_loaders.py::test_marc_mods_loader_detect_and_load
FAILED tests/test_loaders.py::test_profile_loaders_and_autodetect
FAILED tests/test_loaders.py::test_legacy_parser_import_paths_still_work
ERROR tests/test_book_chat.py
```

06c 가 건드리거나 기대는 파일의 기준선(각각 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/<파일> -q -p no:cacheprovider`, 2026-10-08 실측 — 끝의 `, 1 warning`·`, 2 warnings` 는 같은 결과로 본다):

| 파일 | passed | 고치는 Task | 파일 | passed | 고치는 Task |
|---|---|---|---|---|---|
| `test_research_state.py` | 78 | C2 | `test_research_planner.py` | 18 | (그대로 — 계획 고정 테스트) |
| `test_research_api.py` | 121 | C2 | `test_prompts.py` | 9 | (그대로 — 새 YAML 도 훑는다) |
| `test_research_tasks.py` | 106 | C4·C5·C7 | `test_research_critic.py` | 70 | (그대로 — sha256 잠금) |
| `test_research_runner.py` | 81 | C6·C7 | `test_research_explorer.py` | 26 | (그대로) |
| `test_research_eval.py` | 33 | V1·V2 | `test_research_synthesizer.py` | 111 | (그대로) |
| `test_research_terms.py` | 없음 | C1 이 만든다 | `test_research_llm_json.py` | 11 | (그대로 — framing 이 `extract_json` 을 쓴다) |
| `test_research_framing.py` | 없음 | C3 이 만든다 | `test_llm_client.py` | 69 | (그대로) |
| `test_research_models.py` | 18 | (그대로 — C4 는 주석만) | | | |

묶음 기준선(뒤 Task 가 다시 쓰는 명령):

```bash
# 딥리서치 묶음(06b 계획과 같다) — 456 passed, 2 warnings
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_tasks.py tests/test_research_api.py -q -p no:cacheprovider
# 06c 묶음 열 파일(C1·C3 이 새 파일 둘을 만든 뒤에는 Task Z1 의 열두 파일 명령을 쓴다) — 653 passed, 2 warnings
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_state.py tests/test_research_api.py tests/test_research_tasks.py tests/test_research_runner.py tests/test_research_eval.py tests/test_research_planner.py tests/test_prompts.py tests/test_research_critic.py tests/test_research_explorer.py tests/test_research_synthesizer.py -q -p no:cacheprovider
# 딥리서치 백엔드 전체 묶음(06b 계획과 같은 열두 파일) — 715 passed, 2 warnings
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_planner.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_citations.py tests/test_research_synthesizer.py tests/test_research_state.py tests/test_research_explorer.py tests/test_research_llm_json.py tests/test_research_scoring.py tests/test_research_tasks.py tests/test_research_api.py tests/test_research_eval.py -q -p no:cacheprovider
```

판정 라벨이 브랜치에 있는지 본다(06c 판정이 그 위에 새 줄만 덧붙인다 — 06b D18 재판정 뒤 318줄):

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c ls-files scripts/research_eval/labels | wc -l
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && python -c "import csv,glob; rows=[r for p in sorted(glob.glob('scripts/research_eval/labels/*.csv')) for r in csv.DictReader(open(p, encoding='utf-8-sig', newline=''))]; print(len(rows), sum(r['label']=='관련' for r in rows), sum(not (r.get('label') or '').strip() for r in rows))"
```

Expected: `5`, 그리고 `318 128 0`(줄 수 · 관련 · 라벨 칸이 빈 줄).

- [ ] **Step 5: 프론트 기준선**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npm ci
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx vitest run tests/unit/researchEvents.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npm run build 2>&1 | tail -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c status --short
```

Expected (2026-10-08 같은 코드에서 실측):
- `npm ci` — 35초 남짓, 786 패키지. 끝의 `npm audit` 안내(`37 vulnerabilities (3 low, 5 moderate, 21 high, 8 critical)`)는 실패가 아니다
- typecheck — `0`(`WARN Duplicated imports "queueLine"` 두 줄과 `[Vue] Resolve plugin path failed …` 경고는 기준선에도 나온다)
- vitest 전체 — `Test Files  40 passed (40)` / `Tests  732 passed (732)`
- `researchEvents.test.ts` — `Tests  102 passed (102)`(Task V3 가 이 파일에 describe 셋을 더한다)
- build — 30초 남짓, `└  ✨ Build complete!`(로그의 `error` 낱말은 `error-404`·`error-500` 청크 이름뿐이다)
- `git status --short` — 빈 출력(`node_modules`·`.nuxt`·`.output` 은 `.gitignore` 에 있다)

---

<!-- 조립: 파트 C(Task C1~C7)·파트 V(Task V1~V3) 가 이 자리에 들어간다 -->

---

---

## 파트 C — 백엔드 핵심

> **덮는 spec:** §12-2 의 백엔드 전부 — 낱말 맞추기 공용 순수 함수(`terms.py` — `content_words`·`contains`·`PARTICLES`·`QUESTION_WORDS`, 06e 가 같은 함수를 쓴다), 넓히기(`research_frame.yaml`·`framing.py`·`_plan_deep_research` 안 `make_plan` 앞 gemma 1회·`BROADEN_TIMEOUT` 20초·낱말 보존 검사·실패와 타임아웃 때 원문·terms 정리·plan step 결과 `{subquestions, question_used, terms, elapsed_ms}`·`_save_progress` 중간 알림·`app/models/research.py:100` 주석), 실행 태스크가 마지막 plan step 의 `terms` 를 `ResearchState`·스냅숏에, 검색어 합성(`compose_query`·`QUERY_FILLERS`·`runner.py` 첫 검색어와 재검색 제안·`subq.queries` 에 실제로 보낸 글·`_next_query` 중복 비교·critic `tried_queries`), 잡 파라미터 `broaden`·`query_context`(int 0~1, 기본 0, API 검증 경로 그대로), 탐색 후보 목록 이벤트 `candidates`(Q9 의 06c 몫), §12-7 자동 테스트의 백엔드 항목(스위치 0 이면 계획 입력·검색어가 지금과 글자 그대로, 계획 고정 테스트 그대로). 06c 정함 1~13·15·19 를 코드로 옮긴다.
> **순서:** C1 ∥ C2 → C3(C1) → C4(C2·C3) → C5(C4 뒤 같은 파일) / C6(C1·C2) → C7(C6 뒤 같은 파일, `test_research_tasks.py` 는 C5 뒤).
> **테스트 수 읽는 법:** 파일 하나의 기대 수는 dev `da80f23`(= `.worktrees/round06-spec` 코드)의 scratch 사본에 이 파트의 코드를 그대로 넣어 실측한 값이다 — Task 0 이 잰 기준선이 다르면 그 차이만큼 옮겨 읽는다. 전체 pytest 는 "Task 앞 수 + N" 으로 읽는다(파트 C 합계 **+110**: C1 +35 · C2 +19 · C3 +27 · C4 +5 · C5 +6 · C6 +9 · C7 +9). 파트 C 만 Task 0 기준선(`5 failed, 2327 passed, 1 skipped, 2 warnings, 1 error`) 위에 차례로 하면 C7 뒤 `5 failed, 2437 passed, 1 skipped, 2 warnings, 1 error` 다. 실패 5·오류 1 은 늘 기준선과 같은 파일(`test_build_manifest`·`test_loaders`·`test_book_chat`)이다.
> **바꾸지 않는 것(D25·§12-2 — 각 Task 의 확인 Step 이 diff 로 본다):** `app/services/research/planner.py`·`research_plan.yaml`·`parse_plan`·`test_research_planner.py`·`job.plan`(list[str])·승인 API 본문·`app/api/research.py`·`explorer.py`·`critic.py`·`synthesizer.py`·`research_critique.yaml`·`research_critique_question.yaml`·`research_synthesize.yaml`·`services/search/pipeline.py`. runner 의 `_next_query` 와 워커의 `_round_emitter` 도 그대로다.
> 기존 파일은 모두 CRLF 다 — **Edit 도구로** 고친다(아래 old 블록은 줄바꿈을 뺀 내용). 새 파일은 Write 로 만들고 줄바꿈은 커밋 때 git 이 맞춘다.

---

### Task C1: 낱말 맞추기·검색어 합성 순수 함수 — `terms.py` + 공용 고정 예제

**왜:** spec §12-2 '낱말 맞추기(공용 순수 함수)' — 넓히기 검사(Task C3)·검색어 합성(Task C6)·일반 틀 비율(Task V2 의 score.py 복사본)이 한국어 낱말을 같은 방식으로 나누고 맞춘다. 어절째 대조하면 '노인의'↔'노인' 같은 조사 차이로 넓히기가 거의 늘 원문으로 떨어진다. 06e 의 제목 키워드 일치도 06c 머지 뒤 같은 `contains` 를 import 한다(06c 정함 8). 검색어 합성 규칙(`compose_query` — 군더더기 `국내 학술논문에서` 떼기, 06b 이월 §7-12)도 같은 파일에 둔다(정함 12). score.py 는 app 을 import 하지 않아 복사본을 두므로 공용 고정 예제로 묶는다(정함 15, `marker_checks.json` 선례).

**Files:**
- Create: `app/services/research/terms.py`
- Create: `frontend/tests/fixtures/term_checks.json`
- Test: Create `app/tests/test_research_terms.py`

**알아 둘 것:**
- 표준 라이브러리만 쓴다(`re`·`unicodedata`·`collections.abc.Sequence`). DB·LLM·설정 없음 — 06e·score.py 복사본이 그대로 옮겨 쓸 수 있어야 한다.
- `content_words` 규칙(정함 7 — spec 정의에 문장부호·조사만 남은 어절 규칙을 더한 것): NFKC → casefold → 문장부호(`[^\w\s]`)를 공백으로 → 공백으로 어절 나누기 → 어절 끝 조사 하나 떼기(맞는 것 중 가장 긴 것 하나, 떼고 남은 것이 2자 미만이면 떼지 않는다) → 2자 이상·`QUESTION_WORDS` 아님·`PARTICLES` 자체(조사만 남은 어절) 아님 → 처음 나온 순서·중복 없이.
  - 조사는 하나만 뗀다 — `재무성과` 가 어절 하나로 오면 끝 `과` 를 떼어 `재무성` 이 된다(고정 질문 csr 은 `재무성과에` 라 `에` 만 떼어 `재무성과`). 넓히기 검사는 원 질문 낱말이 넓힌 문장에 **들어 있는지**만 보므로 이 경우 더 느슨해질 뿐 틀어지지 않는다 — spec 규칙 그대로 두고 고치지 않는다.
- `contains` 규칙(정함 8 — spec 글자 그대로): NFKC → casefold → 공백 제거 뒤 부분 문자열이면 참, 아니면 word 의 낱말이 모두 순서대로 들어 있으면 참(공백 지운 text 에서 차례로 찾는다 — '노인의 우울' 에 '노인 우울'). word 가 공백 제거 뒤 비면 거짓.
- `compose_query` 규칙: ① `QUERY_FILLERS` 를 글자 그대로 공백으로 바꾸고 공백 정리 ② 비면 text 의 공백만 정리한 글 ③ terms 를 차례로 보며 지금까지의 글에 `contains` 가 아닌 용어만 `' '` 로 붙인다. 용어도 공백을 정리하고 빈 용어는 건너뛴다(빈 용어는 `contains(…, "")` 가 늘 거짓이라 그대로 붙이면 끝에 공백이 남고(`'자원 할당 '`), 그 글을 다시 넣으면 공백이 정리돼 두 번 거친 값이 달라진다. 넓히기의 `clean_terms`(Task C3)와 `_plan_terms`(Task C5)가 이미 거르지만 `compose_query` 는 06e·score.py 가 옮겨 쓰는 순수 함수라 입력을 믿지 않는다). 제외할 뜻은 붙이지 않는다(terms 만).
  - **두 번 거쳐도 같다(멱등) — '군더더기만으로 된 글' 하나는 빼고.** 규칙 ②(군더더기를 지워 비면 text 로 물러난다)와 ③(용어를 붙인다)을 그대로 따르면 text 가 `국내 학술논문에서` 뿐일 때 첫 합성은 `국내 학술논문에서 클라우드`, 그것을 다시 넣으면 군더더기가 떨어져 `클라우드` 다. 하위질문이 군더더기 하나뿐인 경우는 계획 프롬프트상 나오지 않고, 재검색 제안이 그 꼴이어도 `_next_query` 가 합성한 꼴끼리 비교하므로 같은 검색을 두 번 돌리지 않는다 — 규칙을 바꾸지 않고 `compose_query` 독스트링에 적는다. `test_composing_twice_changes_nothing` 은 보통 경우만 고정한다.
- 고정 예제(Step 1 ① 의 JSON)의 칸 모양은 `{"content_words": [{text, words, note}], "contains": [{text, word, expected, note}]}` 로 고정한다 — Task V2 의 score.py 복사본 테스트(`test_contains_copy_matches_the_shared_fixture`)와 06e 화면 테스트가 같은 칸을 읽는다. `note` 는 pytest id 로 쓴다.
- 기대값은 규칙의 결과를 scratch 사본에서 실제로 돌려 맞췄다(ctl_library 질문은 Task V1 의 `questions_control.json` 과 같은 문장 — 「」·쉼표·가운뎃점·물음표가 공백이 되고, 남는 '에서' 는 조사만 남은 어절이라 버린다, '고객만족도' 는 '도' 를 떼어 '고객만족', '남은' 은 떼면 1자라 그대로, '무엇인가' 는 '가' 를 떼어 '무엇인').

- [ ] **Step 1: 공용 고정 예제와 실패하는 테스트를 쓴다**

① Create `frontend/tests/fixtures/term_checks.json`:

```json
{
  "content_words": [
    {
      "text": "컴퓨팅 자원에 대한 연구가 궁금해",
      "words": ["컴퓨팅", "자원"],
      "note": "고정 질문 computing — 질문 꼴 낱말(대한·연구·궁금해)을 뺀다"
    },
    {
      "text": "공공도서관 서비스 품질 평가 연구가 궁금해",
      "words": ["공공도서관", "서비스", "품질", "평가"],
      "note": "고정 질문 library"
    },
    {
      "text": "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
      "words": ["노인", "우울", "사회적", "지지"],
      "note": "고정 질문 elderly — 어절 끝 조사 하나(의·과·에)를 뗀다"
    },
    {
      "text": "다문화가정 아동의 언어 발달에 관한 연구가 궁금해",
      "words": ["다문화가정", "아동", "언어", "발달"],
      "note": "고정 질문 multicultural"
    },
    {
      "text": "기업의 사회적 책임과 재무성과에 관한 연구가 궁금해",
      "words": ["기업", "사회적", "책임", "재무성과"],
      "note": "고정 질문 csr"
    },
    {
      "text": "공공도서관 서비스 품질 평가가 궁금해?",
      "words": ["공공도서관", "서비스", "품질", "평가"],
      "note": "문장부호는 공백으로 — '궁금해?' 가 내용어로 남지 않는다"
    },
    {
      "text": "아이의 놀이와 제도",
      "words": ["아이", "놀이", "제도"],
      "note": "떼고 남는 것이 2자 미만이면 떼지 않는다 — '제도' 의 '도'"
    },
    {
      "text": "학교에서 가정으로",
      "words": ["학교", "가정"],
      "note": "맞는 조사 중 가장 긴 것 하나 — '으로' 를 '로' 보다 먼저"
    },
    {
      "text": "「공공도서관 서비스 고객만족도 평가체계에 관한 연구」에서 출발해, 공공도서관·고객만족도·평가체계 관련 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?",
      "words": ["공공도서관", "서비스", "고객만족", "평가체계", "출발해", "선행", "전개되어", "왔고", "주요", "쟁점", "남은", "과제", "무엇인"],
      "note": "대조군 ctl_library(논문 버튼 꼴) — 「」·쉼표·가운뎃점·물음표는 공백, 조사만 남은 어절 '에서' 는 버린다"
    }
  ],
  "contains": [
    {"text": "노인의 우울과 사회적 지지", "word": "노인 우울", "expected": true, "note": "낱말이 순서대로 — 사이에 조사가 끼어도 된다"},
    {"text": "노인의 우울", "word": "우울 노인", "expected": false, "note": "순서가 바뀌면 맞지 않는다"},
    {"text": "다문화 가정 아동", "word": "다문화가정", "expected": true, "note": "공백을 지우고 본다"},
    {"text": "기업의 사회적 책임과 재무 성과", "word": "재무성과", "expected": true, "note": "띄어 쓴 글에 붙여 쓴 낱말"},
    {"text": "ＣＳＲ과 재무성과", "word": "csr", "expected": true, "note": "NFKC(전각)·casefold(대소문자)"},
    {"text": "공공도서관 서비스", "word": "도서관", "expected": true, "note": "부분 문자열"},
    {"text": "컴퓨팅 자원 할당", "word": "클라우드", "expected": false, "note": "없는 낱말"},
    {"text": "컴퓨팅 자원", "word": "", "expected": false, "note": "빈 낱말은 늘 거짓"},
    {"text": "기업의 사회적 책임과 재무성과에 관한 연구", "word": "성과", "expected": true, "note": "score.py 가 원 질문에 든 측면 낱말('재무성과' 의 '성과')을 일반 틀로 세지 않는 근거"}
  ]
}
```

② Create `app/tests/test_research_terms.py`:

```python
"""services/research/terms.py — 한국어 낱말 맞추기·검색어 합성(순수 함수, 06c).

넓히기 검사·검색어 합성·일반 틀 비율이 같은 규칙으로 낱말을 나누고 맞춘다. scripts/research_eval/score.py 는 app 을
import 하지 않아 contains 복사본을 두고, 06e 화면의 키워드 하이라이트도 같은 규칙을 쓸 수 있다 — 공용 고정 예제
frontend/tests/fixtures/term_checks.json 을 함께 읽는다. 한쪽 규칙을 바꾸려면 이 파일을 고쳐야 하고, 그러면 다른 쪽
테스트가 깨진다(marker_checks.json 과 같은 방식).
"""
import json
from pathlib import Path

import pytest

from services.research.terms import (
    PARTICLES, QUERY_FILLERS, QUESTION_WORDS, compose_query, contains, content_words,
)

SHARED_FIXTURE = (
    Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "term_checks.json"
)
SHARED = json.loads(SHARED_FIXTURE.read_text(encoding="utf-8"))


class TestSharedFixture:
    def test_fixture_keeps_the_cases_both_sides_must_agree_on(self):
        # 예제를 줄여 대조를 약하게 만들지 못하게 — 고정 5문항·문장부호·짧은 나머지·긴 조사 먼저·논문 버튼 꼴,
        # 순서대로 맞음과 순서가 바뀐 틀림·공백 무시·NFKC·빈 낱말
        texts = [c["text"] for c in SHARED["content_words"]]
        for fixed in ("컴퓨팅 자원에 대한", "공공도서관 서비스 품질 평가 연구가", "노인의 우울과 사회적 지지",
                      "다문화가정 아동의 언어 발달", "기업의 사회적 책임과 재무성과"):
            assert any(fixed in t for t in texts), fixed
        assert any(t.endswith("?") for t in texts)
        assert any("제도" in c["words"] for c in SHARED["content_words"])
        assert any("으로" in t for t in texts)
        assert any(t.startswith("「") and "」에서 출발해," in t for t in texts)
        pairs = {(c["text"], c["word"]): c["expected"] for c in SHARED["contains"]}
        assert pairs[("노인의 우울과 사회적 지지", "노인 우울")] is True
        assert pairs[("노인의 우울", "우울 노인")] is False
        assert pairs[("다문화 가정 아동", "다문화가정")] is True
        assert pairs[("ＣＳＲ과 재무성과", "csr")] is True
        assert any(c["word"] == "" and c["expected"] is False for c in SHARED["contains"])
        assert all(set(c) == {"text", "words", "note"} for c in SHARED["content_words"])
        assert all(set(c) == {"text", "word", "expected", "note"} for c in SHARED["contains"])

    @pytest.mark.parametrize("case", SHARED["content_words"], ids=[c["note"] for c in SHARED["content_words"]])
    def test_content_words_match_the_shared_fixture(self, case):
        assert content_words(case["text"]) == case["words"]

    @pytest.mark.parametrize("case", SHARED["contains"], ids=[c["note"] for c in SHARED["contains"]])
    def test_contains_matches_the_shared_fixture(self, case):
        assert contains(case["text"], case["word"]) is case["expected"]


class TestContentWords:
    def test_constants_start_from_the_spec_values(self):
        # spec §12-2 의 처음 값 — 운영 질문을 보고 늘릴 수는 있어도 조용히 줄면 넓히기 검사가 느슨해진다
        assert PARTICLES == ("에서", "에게", "으로", "로", "의", "은", "는", "이", "가", "을", "를",
                             "와", "과", "에", "도", "만")
        assert QUESTION_WORDS == ("연구", "관한", "대한", "관련", "궁금해", "궁금합니다", "알려줘", "찾아줘",
                                  "무엇", "어떻게")
        assert QUERY_FILLERS == ("국내 학술논문에서",)

    def test_one_trailing_particle_is_stripped_longest_first(self):
        assert content_words("학교에서 가정으로 아동에게") == ["학교", "가정", "아동"]
        # 하나만 뗀다 — '평가에서도' 는 '도' 하나를 떼고 '평가에서' 로 남는다
        assert content_words("평가에서도") == ["평가에서"]

    def test_particle_is_kept_when_less_than_two_characters_remain(self):
        # '제도'·'남은'·'나이' 의 끝 글자는 조사 모양이지만 떼면 1자다
        assert content_words("제도 남은 나이") == ["제도", "남은", "나이"]

    def test_question_words_and_particle_only_tokens_are_dropped(self):
        assert content_words("무엇 어떻게 알려줘 찾아줘 궁금합니다 관련 연구는") == []
        # 「…」를 공백으로 바꾸면 남는 조사 어절('에서')은 내용어가 아니다
        assert content_words("「노인 우울」에서 출발해") == ["노인", "우울", "출발해"]

    def test_punctuation_splits_words(self):
        assert content_words("노인·우울, 지지(사회적)?") == ["노인", "우울", "지지", "사회적"]

    def test_words_are_normalized_and_kept_in_order_without_duplicates(self):
        # 전각·대문자는 NFKC·casefold 로 같은 낱말이 된다 — 처음 나온 자리에 한 번만
        assert content_words("ＣＳＲ과 공시, CSR 공시와 지배구조") == ["csr", "공시", "지배구조"]


class TestContains:
    def test_spaces_are_ignored_for_the_substring_match(self):
        assert contains("다문화 가정 아동", "다문화가정") is True
        assert contains("다문화가정 아동", "다문화 가정") is True

    def test_words_of_the_term_may_stand_apart_in_order(self):
        assert contains("노인이 겪는 우울과 사회적 지지", "노인 우울") is True

    def test_words_out_of_order_do_not_match(self):
        assert contains("노인이 겪는 우울", "우울 노인") is False

    def test_empty_word_never_matches(self):
        assert contains("컴퓨팅 자원", "") is False
        assert contains("컴퓨팅 자원", "   ") is False
        assert contains("", "컴퓨팅") is False


class TestComposeQuery:
    def test_fillers_are_removed_word_for_word_and_spaces_tidied(self):
        assert compose_query("국내 학술논문에서  공공도서관 서비스 품질 평가 방법", []) == "공공도서관 서비스 품질 평가 방법"
        # 글자 그대로만 지운다 — 띄어쓰기가 다르면 군더더기로 보지 않는다
        assert compose_query("국내학술논문에서 공공도서관", []) == "국내학술논문에서 공공도서관"

    def test_only_terms_missing_from_the_query_are_added_in_order(self):
        assert compose_query("컴퓨팅 자원 할당 방법", ["컴퓨팅 자원", "클라우드", "엣지 컴퓨팅"]) == (
            "컴퓨팅 자원 할당 방법 클라우드 엣지 컴퓨팅")

    def test_term_contained_in_an_added_term_is_not_added_again(self):
        # 이어 붙인 용어도 다음 비교에 든다 — '클라우드 컴퓨팅' 을 붙인 뒤 '클라우드' 는 이미 있다
        assert compose_query("자원 할당", ["클라우드 컴퓨팅", "클라우드"]) == "자원 할당 클라우드 컴퓨팅"

    def test_without_terms_only_fillers_are_removed(self):
        assert compose_query("국내 학술논문에서 노인 우울 측정 도구", []) == "노인 우울 측정 도구"
        assert compose_query("노인 우울 측정 도구", ()) == "노인 우울 측정 도구"

    def test_composing_twice_changes_nothing(self):
        terms = ["컴퓨팅 자원", "클라우드"]
        once = compose_query("국내 학술논문에서 컴퓨팅 자원 할당 방법", terms)
        assert once == "컴퓨팅 자원 할당 방법 클라우드"
        assert compose_query(once, terms) == once

    def test_query_left_empty_by_fillers_falls_back_to_the_text(self):
        assert compose_query(" 국내 학술논문에서 ", []) == "국내 학술논문에서"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_terms.py -q -p no:cacheprovider`

Expected: 수집 오류 — `E   ModuleNotFoundError: No module named 'services.research.terms'`, 끝 줄 `1 error in …s`(`Interrupted: 1 error during collection`).

- [ ] **Step 3: 구현한다**

Create `app/services/research/terms.py`:

```python
"""terms.py — 한국어 낱말 맞추기·검색어 합성(06c) — spec §12-2

넓히기 검사(framing)·검색어 합성(runner)·일반 틀 비율(scripts/research_eval/score.py)이 한국어 낱말을 같은
방식으로 나누고 맞춘다. 어절째 대조하면 '노인의'↔'노인' 같은 조사 차이로 넓히기가 거의 늘 원문으로 떨어진다.
06e 의 제목 키워드 일치(topic_card)도 이 contains 를 그대로 import 한다 — 같은 규칙을 따로 두지 않는다.
score.py 는 app 을 import 하지 않아 contains 복사본을 둔다. 복사본·06e 화면과 이 모듈은 공용 고정 예제
(frontend/tests/fixtures/term_checks.json)로 묶는다 — 규칙을 바꾸면 예제를 함께 고치고 양쪽 테스트가 통과해야 한다.

표준 라이브러리만 쓴다(순수 함수 — DB·LLM·설정 없음).
"""
import re
import unicodedata
from collections.abc import Sequence

# 어절 끝에서 떼는 조사(처음 값 — spec §12-2). 맞는 것 중 가장 긴 것 하나만 뗀다('으로'를 '로'보다 먼저)
PARTICLES: tuple[str, ...] = (
    "에서", "에게", "으로", "로", "의", "은", "는", "이", "가", "을", "를", "와", "과", "에", "도", "만",
)
# 질문 꼴 낱말 — 연구 주제가 아니라 묻는 말이라 내용어로 세지 않는다
QUESTION_WORDS: tuple[str, ...] = (
    "연구", "관한", "대한", "관련", "궁금해", "궁금합니다", "알려줘", "찾아줘", "무엇", "어떻게",
)
# 검색어에서 글자 그대로 지우는 군더더기. D18 계획 프롬프트가 하위질문에 붙이게 된 말이다(06b 이월 §7-12) —
# 하위질문 글(절 소제목)은 그대로 두고 검색어에서만 뗀다
QUERY_FILLERS: tuple[str, ...] = ("국내 학술논문에서",)

# 문장부호를 공백으로 — '궁금해?'·논문 버튼 꼴(「…」에서, 가·나 관련)이 어절째 원문으로 떨어지지 않게
_PUNCT = re.compile(r"[^\w\s]")
_BY_LENGTH = sorted(PARTICLES, key=len, reverse=True)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _strip_particle(token: str) -> str:
    """어절 끝 조사 하나를 뗀다. 떼고 남은 것이 2자 미만이면 떼지 않는다('제도'의 '도'는 조사가 아니다)."""
    for particle in _BY_LENGTH:
        if token.endswith(particle):
            stem = token[: -len(particle)]
            return stem if len(stem) >= 2 else token
    return token


def content_words(text: str) -> list[str]:
    """내용어 — NFKC·casefold, 문장부호는 공백, 어절 끝 조사 하나를 떼고, 2자 이상·질문 꼴 낱말 아님·
    조사만 남은 어절 아님. 처음 나온 순서대로 중복 없이."""
    out: list[str] = []
    for token in _PUNCT.sub(" ", _normalize(text or "")).split():
        word = _strip_particle(token)
        if len(word) < 2 or word in QUESTION_WORDS or word in PARTICLES or word in out:
            continue
        out.append(word)
    return out


def contains(text: str, word: str) -> bool:
    """text 에 word 가 들어 있는가 — NFKC·casefold·공백 제거 뒤 부분 문자열이거나, word 의 낱말이 모두
    순서대로 들어 있으면 참. word 가 비면(공백 제거 뒤) 거짓.

    공백을 지우고 보므로 '다문화 가정'↔'다문화가정'·'재무 성과'↔'재무성과' 가 맞고, 낱말을 차례로 찾으므로
    '노인의 우울'에 '노인 우울'이 맞는다(조사가 사이에 끼어도 된다). 순서가 바뀌면 맞지 않는다.
    """
    pieces = _normalize(word or "").split()
    if not pieces:
        return False
    flat = "".join(_normalize(text or "").split())
    if "".join(pieces) in flat:
        return True
    pos = 0
    for piece in pieces:
        found = flat.find(piece, pos)
        if found < 0:
            return False
        pos = found + len(piece)
    return True


def compose_query(text: str, terms: Sequence[str]) -> str:
    """검색어 합성(잡 파라미터 query_context 1) — QUERY_FILLERS 를 글자 그대로 지우고 공백을 정리한 뒤, terms 가운데
    지금까지의 글에 contains 가 아닌 용어만 차례로 ' ' 로 이어 붙인다(이어 붙인 용어도 다음 비교에 든다).

    군더더기를 지우고 남는 것이 없으면 text 의 공백만 정리한 글로 물러난다. 제외할 뜻은 붙이지 않는다 — terms 만
    붙인다(dense 검색은 부정을 몰라 오히려 그 논문을 끌어온다). 합성한 글을 다시 넣어도 같은 글이 나온다(군더더기만으로
    된 글이 물러난 경우는 빼고) — 재검색 제안이 앞 검색어(이미 합성한 글)를 고쳐 쓴 것이어도 용어가 두 번 붙지 않는다.
    """
    query = text
    for filler in QUERY_FILLERS:
        query = query.replace(filler, " ")
    query = " ".join(query.split()) or " ".join(text.split())
    for term in terms:
        term = " ".join(term.split())
        if term and not contains(query, term):
            query = f"{query} {term}"
    return query
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_terms.py -q -p no:cacheprovider`

Expected: `35 passed` (TestSharedFixture 19 = 예제 지키기 1 + 내용어 예제 9 + contains 예제 9, TestContentWords 6, TestContains 4, TestComposeQuery 6)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 파일. Task 앞 수 + 35 (Task 0 바로 뒤면 `5 failed, 2362 passed, 1 skipped, 2 warnings, 1 error`).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/services/research/terms.py app/tests/test_research_terms.py frontend/tests/fixtures/term_checks.json && git status --short && git commit -m "[Feat] round06c — 한국어 낱말 맞추기·검색어 합성 순수 함수(terms.py)와 공용 고정 예제: content_words 는 NFKC·casefold 뒤 문장부호를 공백으로 바꾸고 어절 끝 조사 하나(가장 긴 것, 남는 것이 2자 미만이면 그대로)를 떼어 질문 꼴 낱말·조사만 남은 어절을 뺀다. contains 는 공백을 지운 부분 문자열이거나 낱말이 모두 순서대로 들어 있으면 참이다(06e 제목 일치가 같은 함수를 쓴다). compose_query 는 '국내 학술논문에서' 를 글자 그대로 떼고 범위 용어 중 없는 것만 붙인다(06b 이월 §7-12). score.py 복사본·06e 화면과 묶는 공용 고정 예제 frontend/tests/fixtures/term_checks.json(고정 5문항·문장부호·짧은 나머지·논문 버튼 꼴·순서·NFKC)"
```

---

### Task C2: 잡 파라미터 `broaden`·`query_context` 와 `ResearchState.terms`

**왜:** spec §12-2 '스위치' — 잡 파라미터 `broaden`·`query_context`(int 0~1, 기본 0)를 `critic_scope` 와 같은 방식으로 `DEFAULT_PARAMS`·`_PARAM_BOUNDS` 에 더한다(`research_jobs.params` JSONB — 스키마 변경 없음, 함정 14). 판정 도구가 갈래마다 다른 값으로 잡을 만들고(§12-7), 기본값은 판정 뒤 Q4 로 정한다. 같은 Task 에서 `ResearchState.terms`(계획 단계가 뽑은 범위 용어)와 스냅숏 왕복을 더한다 — Task C5 가 채우고 Task C6 이 검색어에 쓴다. 06c 정함 13: `state.terms` 는 스위치와 무관하게 늘 담는다.

**Files:**
- Modify: `app/services/research/state.py` — `DEFAULT_PARAMS`(:18-34, `critic_scope` 뒤 두 칸과 주석), `_PARAM_BOUNDS`(:40-50), `ResearchState`(:165-183, `corpus_range` 뒤 `terms`), `snapshot_state`(:186-208), `restore_state`(:225-257)
- Test: Modify `app/tests/test_research_state.py` — `TestMergeParams.test_default_params_key_set_is_fixed`(:34-41) 키 집합, 새 테스트 여섯 함수(parametrize 포함 16개)
- Test: Modify `app/tests/test_research_api.py` — `TestCreate`(:288-331) 끝에 새 테스트 둘(parametrize 포함 3개)
- 고치지 않음: `app/api/research.py` — 검증은 `create_research` 의 `merge_params(req.params)`(:235) 한 곳이고 `ValueError` 를 422 로 바꾼다(지금 `critic_scope` 와 같은 길).

**알아 둘 것:**
- **기본값을 단언하는 테스트는 이 Task 의 둘뿐이다**(`test_research_state.py::TestMergeParams::test_query_switches_are_off_by_default`, `test_research_api.py::TestCreate::test_query_switches_are_saved_off_unless_asked`). 기본값 커밋(Q4 — 마무리)이 이 둘만 고치면 되게, 다른 Task 의 테스트는 스위치 값을 적는다(`{"broaden": 0}`·`merge_params({"query_context": 1, …})`).
- 값 검사 거부 문구는 `파라미터 broaden 가 허용 범위(0~1)를 벗어났다`·`파라미터 broaden 는 int 여야 한다`·`파라미터 broaden 에 bool 값은 쓸 수 없다` 다(`_validate_param` 그대로). 테스트의 `match=f"파라미터 {key}"` 는 콜론이 없어 '알 수 없는 파라미터: broaden'(키를 모를 때)에는 맞지 않는다 — 구현 전에는 실패하고, 구현 뒤에는 값 검사에서 거부돼야 통과한다(`critic_scope` 테스트와 같은 장치).
- 기존 `TestSnapshotRoundTrip`·`TestSeenPapers.test_snapshot_carries_every_state_field`(:349-353 — 스냅숏 키 집합 = `ResearchState` 필드 − job_id)가 `terms` 를 필드와 스냅숏 양쪽에 넣었는지 그대로 지킨다. `test_round_trip_is_stable`·`test_params_are_refilled_with_defaults` 도 고치지 않고 통과한다.
- 옛 워커는 모르는 키를 `알 수 없는 파라미터` 로 거부한다 — 배포는 워커를 fastapi 보다 먼저 Recreate 한다(Task Z4).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_state.py` — 키 집합. old:

```python
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
            "exclude_off_topic", "critic_scope",
        }
```

new:

```python
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
            "exclude_off_topic", "critic_scope", "broaden", "query_context",
        }
```

② 같은 파일 `TestMergeParams` 끝(`test_critic_scope_rejects_anything_else` 뒤). old:

```python
    @pytest.mark.parametrize("value", [2, -1, True, "1", 1.0])
    def test_critic_scope_rejects_anything_else(self, value):
        # '알 수 없는 파라미터: critic_scope' 가 아니라 값 검사에서 거부돼야 한다 — 그래서 콜론 없는 문구로 맞춘다
        with pytest.raises(ValueError, match="파라미터 critic_scope"):
            merge_params({"critic_scope": value})
```

new:

```python
    @pytest.mark.parametrize("value", [2, -1, True, "1", 1.0])
    def test_critic_scope_rejects_anything_else(self, value):
        # '알 수 없는 파라미터: critic_scope' 가 아니라 값 검사에서 거부돼야 한다 — 그래서 콜론 없는 문구로 맞춘다
        with pytest.raises(ValueError, match="파라미터 critic_scope"):
            merge_params({"critic_scope": value})

    def test_query_switches_are_off_by_default(self):
        # 06c 넓히기·검색어 합성은 운영 두 갈래 판정(spec §12-7) 뒤에 기본값을 바꿔 켠다. 기본값을 단언하는 테스트는
        # 이것과 test_research_api 의 test_query_switches_are_saved_off_unless_asked 둘뿐이다 — 다른 테스트는 값을 적는다
        assert (DEFAULT_PARAMS["broaden"], DEFAULT_PARAMS["query_context"]) == (0, 0)

    @pytest.mark.parametrize("key", ["broaden", "query_context"])
    @pytest.mark.parametrize("value", [0, 1])
    def test_query_switches_take_zero_or_one(self, key, value):
        # 판정 도구(run_pair --param)가 갈래마다 잡 파라미터로 준다
        assert merge_params({key: value})[key] == value

    @pytest.mark.parametrize("key", ["broaden", "query_context"])
    @pytest.mark.parametrize("value", [2, -1, True, "1"])
    def test_query_switches_reject_anything_else(self, key, value):
        # '알 수 없는 파라미터: …' 가 아니라 값 검사에서 거부돼야 한다 — 콜론 없는 문구로 맞춘다
        with pytest.raises(ValueError, match=f"파라미터 {key}"):
            merge_params({key: value})
```

③ 같은 파일 `TestState` 끝. old:

```python
    def test_corpus_range_defaults_to_none(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.corpus_range is None
```

new:

```python
    def test_corpus_range_defaults_to_none(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.corpus_range is None

    def test_new_state_has_no_terms(self):
        # 넓히지 않은 잡(broaden 0·06c 전 잡)은 범위 용어가 없다 — 검색어 합성은 군더더기만 뗀다
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.terms == []
```

④ 같은 파일 `TestSnapshotRoundTrip`. old:

```python
    def test_corpus_range_survives(self):
        # 보고서의 "수록 범위" 문구가 여기서 온다 — 떨어지면 재개한 보고서만 비어 보인다
        back = restore_state("j1", snapshot_state(_explored_state()))
        assert back.corpus_range == {"from": "2002", "to": "2026", "n_papers": 72054}
```

new:

```python
    def test_corpus_range_survives(self):
        # 보고서의 "수록 범위" 문구가 여기서 온다 — 떨어지면 재개한 보고서만 비어 보인다
        back = restore_state("j1", snapshot_state(_explored_state()))
        assert back.corpus_range == {"from": "2002", "to": "2026", "n_papers": 72054}

    def test_terms_survive(self):
        # 계획 단계가 뽑은 범위 용어 — 떨어지면 재개한 잡의 기록(스냅숏)만 용어를 잃는다
        st = _explored_state()
        st.terms = ["컴퓨팅 자원", "클라우드"]
        snap = snapshot_state(st)
        assert snap["terms"] == ["컴퓨팅 자원", "클라우드"]
        assert restore_state("j1", snap).terms == ["컴퓨팅 자원", "클라우드"]
```

⑤ 같은 파일 `TestSnapshotEvolution` — `test_params_are_refilled_with_defaults` 앞. old:

```python
    def test_params_are_refilled_with_defaults(self):
        """나중에 추가된 파라미터를 옛 스냅샷이 모르면 읽는 쪽이 KeyError 로 터진다."""
```

new:

```python
    def test_old_snapshot_without_terms_gets_no_terms(self):
        # 06c 전 스냅숏 — 그 잡은 넓히지 않았다
        snap = snapshot_state(_explored_state())
        del snap["terms"]
        assert restore_state("j1", snap).terms == []

    def test_params_are_refilled_with_defaults(self):
        """나중에 추가된 파라미터를 옛 스냅샷이 모르면 읽는 쪽이 KeyError 로 터진다."""
```

⑥ `app/tests/test_research_api.py` — `TestCreate` 끝. old:

```python
    def test_critic_scope_other_than_zero_or_one_is_422(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"critic_scope": 2}})
        assert res.status_code == 422
        assert "허용 범위" in res.json()["detail"]      # 모르는 키가 아니라 값 검사에서 거부
```

new:

```python
    def test_critic_scope_other_than_zero_or_one_is_422(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"critic_scope": 2}})
        assert res.status_code == 422
        assert "허용 범위" in res.json()["detail"]      # 모르는 키가 아니라 값 검사에서 거부

    def test_query_switches_are_saved_off_unless_asked(self, api):
        # 06c 넓히기·검색어 합성 — 지정하지 않으면 기본값을 채워 저장하고(워커가 같은 merge_params 로 읽는다),
        # 판정 도구(run_pair --param)는 갈래 1 에 1 을 준다
        plain = api.client.post("/api/research", json={"question": "독서 격차 연구"})
        asked = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                        "params": {"broaden": 1, "query_context": 1}})
        assert (plain.status_code, asked.status_code) == (200, 200)
        first, second = api.db.jobs.values()
        assert (first["params"]["broaden"], first["params"]["query_context"]) == (0, 0)
        assert (second["params"]["broaden"], second["params"]["query_context"]) == (1, 1)

    @pytest.mark.parametrize("key", ["broaden", "query_context"])
    def test_query_switch_other_than_zero_or_one_is_422(self, api, key):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구", "params": {key: 2}})
        assert res.status_code == 422
        assert "허용 범위" in res.json()["detail"]      # 모르는 키가 아니라 값 검사에서 거부
        assert api.db.jobs == {}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_state.py tests/test_research_api.py -q -p no:cacheprovider`

Expected: `20 failed, 198 passed, 1 warning` — 실패는 정확히 다음 20개:
- `test_research_state.py` 17개 — `TestMergeParams::test_default_params_key_set_is_fixed`(키 집합에 둘이 없다), `test_query_switches_are_off_by_default`(KeyError), `test_query_switches_take_zero_or_one` 4개(`알 수 없는 파라미터: broaden`), `test_query_switches_reject_anything_else` 8개(문구가 '알 수 없는 파라미터: …' 라 `파라미터 broaden` 에 맞지 않는다), `TestState::test_new_state_has_no_terms`(AttributeError), `TestSnapshotRoundTrip::test_terms_survive`(스냅숏에 `terms` 가 없다), `TestSnapshotEvolution::test_old_snapshot_without_terms_gets_no_terms`(KeyError 'terms')
- `test_research_api.py` 3개 — `TestCreate::test_query_switches_are_saved_off_unless_asked`(둘째 요청이 422 라 잡이 하나뿐), `test_query_switch_other_than_zero_or_one_is_422[broaden]`·`[query_context]`(422 이지만 문구가 '알 수 없는 파라미터')

- [ ] **Step 3: 구현한다**

`app/services/research/state.py`.

① `DEFAULT_PARAMS` 끝. old:

```python
    # 충분·부족은 두 갈래 모두 하위질문 기준이다. 운영에서 고정 질문을 두 갈래로 돌려 합격하면 기본값을 1 로 바꾼다
    "critic_scope": 0,
})
```

new:

```python
    # 충분·부족은 두 갈래 모두 하위질문 기준이다. 운영에서 고정 질문을 두 갈래로 돌려 합격하면 기본값을 1 로 바꾼다
    "critic_scope": 0,
    # 계획 전 gemma 1회로 질문을 한 문장으로 넓히고 범위 용어를 뽑을지(1). 0 = 원 질문 그대로 계획(06c, spec §12-2).
    # 계획 프롬프트는 그대로이고 make_plan 에 넘기는 질문만 바뀐다. 운영에서 두 갈래로 판정해 켠다(§12-7)
    "broaden": 0,
    # 검색어에 범위 용어를 합성하고 군더더기('국내 학술논문에서')를 뗄지(1). 0 = 하위질문·재검색 제안 글자 그대로.
    # 범위 용어는 계획 단계(broaden 1)가 뽑는다 — broaden 0 이면 용어가 없어 군더더기만 뗀다
    "query_context": 0,
})
```

② `_PARAM_BOUNDS` 끝. old:

```python
    "exclude_off_topic": (int, 0, 1),
    "critic_scope": (int, 0, 1),
}
```

new:

```python
    "exclude_off_topic": (int, 0, 1),
    "critic_scope": (int, 0, 1),
    "broaden": (int, 0, 1),
    "query_context": (int, 0, 1),
}
```

③ `ResearchState` — `corpus_range` 뒤. old:

```python
    corpus_range: dict | None = None
    # 보고서는 여기에 두지 않는다. synthesize() 가 반환값으로 넘기고 Celery
```

new:

```python
    corpus_range: dict | None = None
    # 계획 단계(넓히기, 잡 파라미터 broaden)가 뽑은 범위 용어 — 검색어 합성(query_context 1)의 재료. 실행 태스크가
    # 마지막 plan step 결과에서 읽어 담는다(스위치와 무관하게 늘 — 검색어에 쓰는 것은 query_context 1 일 때뿐).
    # 넓히지 않았거나 06c 전 잡이면 빈 목록이다
    terms: list[str] = field(default_factory=list)
    # 보고서는 여기에 두지 않는다. synthesize() 가 반환값으로 넘기고 Celery
```

④ `snapshot_state`. old:

```python
        "corpus_range": state.corpus_range,
        "subquestions": [asdict(s) for s in state.subquestions],
```

new:

```python
        "corpus_range": state.corpus_range,
        "terms": list(state.terms),
        "subquestions": [asdict(s) for s in state.subquestions],
```

⑤ `restore_state`. old:

```python
        corpus_range=snap.get("corpus_range"),
    )
```

new:

```python
        corpus_range=snap.get("corpus_range"),
        # 06c 전 스냅숏에는 없다 — 그 잡은 넓히지 않았으니 빈 목록이다
        terms=list(snap.get("terms") or []),
    )
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_state.py tests/test_research_api.py -q -p no:cacheprovider`

Expected: `218 passed, 1 warning` (state 78 → 94 · api 121 → 124)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_runner.py tests/test_research_tasks.py tests/test_research_synthesizer.py tests/test_research_critic.py -q -p no:cacheprovider`

Expected: `368 passed, 2 warnings` (runner 81 · tasks 106 · synthesizer 111 · critic 70 — 실패 0) — `ResearchState(…, params=merge_params({…}))` 로 상태를 세우는 기존 테스트가 새 두 칸(값 0)을 받아도 그대로 통과한다(러너·워커는 아직 이 칸을 읽지 않는다).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git diff --stat -- app/api/research.py`

Expected: 빈 출력

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 파일. Task 앞 수 + 19 (C1 바로 뒤면 `5 failed, 2381 passed, 1 skipped, 2 warnings, 1 error`).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/services/research/state.py app/tests/test_research_state.py app/tests/test_research_api.py && git status --short && git commit -m "[Feat] round06c — 잡 파라미터 broaden·query_context(int 0~1, 기본 0)와 ResearchState.terms(스냅숏 왕복): critic_scope 와 같은 길로 DEFAULT_PARAMS·_PARAM_BOUNDS 에 더해 API 는 merge_params 그대로 422 를 낸다(스키마 변경 없음 — research_jobs.params JSONB). terms 는 계획 단계가 뽑은 범위 용어로 스위치와 무관하게 늘 담고, 06c 전 스냅숏은 빈 목록으로 되살린다. 기본값을 단언하는 테스트는 state·API 의 둘뿐이다 — 판정 뒤 기본값 커밋이 이 둘만 고친다"
```

---

### Task C3: 넓히기 — `research_frame.yaml`·`framing.py`

**왜:** spec §12-2 '넓히기' — 개념 하나짜리 짧은 질문은 계획 프롬프트의 측면 목록(`research_plan.yaml:12`)을 그대로 옮겨 일반 틀이 된다(06b 계획 30개 중 약 25개). 계획 전에 gemma 를 한 번 불러 질문을 계획하기 좋은 한 문장으로 넓히고, 연구 범위를 정하는 용어(검색어 합성의 재료 — 06b 이월 §7-11 '컴퓨팅' 동음이의)를 뽑는다. 이 Task 는 프롬프트와 순수·LLM 함수만 만들고, 계획 태스크에 잇는 것은 Task C4 다. 06c 정함 1(새 모듈 — `planner.py` 는 한 글자도 고치지 않는다)·2(프롬프트)·9(terms·넓힌 질문 정리)·10(실패 타입)·19(20초).

**Files:**
- Create: `app/domains/nl_library/prompts/research_frame.yaml` (정함 2 — Step 3 ① 의 YAML 글 그대로)
- Create: `app/services/research/framing.py`
- Test: Create `app/tests/test_research_framing.py`
- 고치지 않음: `app/services/research/planner.py`·`app/domains/nl_library/prompts/research_plan.yaml`·`app/tests/test_research_planner.py`

**알아 둘 것:**
- 모듈 자리(정함 1): `TestPlan._patch`(`test_research_tasks.py:850-860`)는 `services.research.planner` 를 `make_plan` 하나만 든 모듈로 통째로 바꿔치기한다 — 넓히기가 planner 안에 있으면 그 대역 위에서 import 가 깨진다. `framing.py` 는 planner 를 import 하지 않는다.
- LLM 호출: `chat(messages, params=llm_params, timeout=BROADEN_TIMEOUT)` 한 번, `base_url`·`model` 인자 없음 = `LLM_BASE_URL`·`LLM_MODEL`(gemma). `chat` 기본 120초를 쓰지 않는다(`BOOK_CHAT_QUERY_REWRITE_TIMEOUT=20` 선례). `chat_full` 은 이 시간 안에서 재시도하고 최악은 timeout + 연결 10초다(`llm_client.py:228-231`). `asyncio.timeout` 을 따로 걸지 않는다 — 잡 데드라인(`_within_deadline` 의 `TimeoutError` 판정)과 섞이지 않게(정함 19).
- 실패 타입(정함 10, 함정 19): `FRAME_FAILURES = (httpx.HTTPError, ValueError, KeyError, IndexError)` — `_request_once` 가 실제로 내는 전송·상태(`raise_for_status`), 응답 본문 JSON 해석(`resp.json()` 의 `JSONDecodeError` ⊂ `ValueError`), 응답 모양(`data["choices"][0]`) 오류다. 그 밖의 예외(코드 결함·`SoftTimeLimitExceeded`)는 올린다 — Task C4 가 계획 실패로 닫는다. **spec §12-2:502 '잡을 실패시키지 않는다' 와 다르다** — 계획 머리 '06c 에서 정한 것' 표·마무리 spec 맞춤 몫(정함 10).
- 응답 검사(`parse_frame`): `extract_json`(`services/research/llm_json.py` — 펜스·산문 섞인 응답에서 첫 JSON 객체, 못 찾으면 None) → `"question"` 이 문자열이 아니면 None → 입력 이름표(`_ECHO_LABEL` — 맨 앞 `질문:`·`질문：`)를 떼고 공백 정리한 뒤 비었거나 `FRAMED_QUESTION_MAX`(500 = `ResearchCreate.question` 상한) 초과면 None → 원 질문의 `content_words` 가 하나라도 넓힌 문장에 `contains` 가 아니면 None(빠진 낱말을 경고에 적는다). 모델이 원 질문을 그대로 내도 정상이다(함정 26 — 프롬프트가 '이미 분명하면 그대로' 라고 했다). **(C3 품질 검토 반영)** 낱말 검사는 `content_words` 의 2자 바닥에 걸리는 한 글자 명사(암·뇌·법)도 본다 — 원 질문의 한 글자 어절(`content_words` 와 같은 NFKC·casefold·문장부호 공백 나누기, 조사·`QUESTION_WORDS`·`ONE_CHAR_FUNCTION_WORDS`(및·등·왜·더·수·것 같은 잇는 말) 제외)이 넓힌 문장에 어절로 없어도 같은 경고 한 줄과 함께 None. 그러지 않으면 '암 연구가 궁금해'(내용어 [])에 지어낸 주제를 낸 답도, '암'을 '종양'으로 바꾼 답도 지나간다(`test_question_that_drops_a_one_char_word_is_refused`). 한 글자는 `contains` 로 대조하지 않는다 — 넓힌 문장을 같은 방식으로 나눈 어절이 그 글자이거나 '그 글자 + `PARTICLES` 하나'(암의·뇌를·암에서)일 때만 들어 있다고 본다(`_has_one_char_word`). 부분 문자열로 보면 '법 관련 연구 알려줘'→'…교육 방법…', '암 연구가 궁금해'→'암호화…', '뇌 연구'→'뇌물…' 이 모두 지나간다(C3 두 번째 품질 검토 — 세 사례를 거절 테스트에, 홑 글자·조사 붙은 꼴·문장부호·NFKC 를 `test_one_char_word_is_matched_as_a_whole_word` 에 고정). 붙여 쓴 꼴('암환자')은 물러나지만 원 질문으로 물러나는 것은 안전한 쪽이다. `content_words`·`contains` 의 계약(06e·score.py 복사본)은 그대로다.
- 이름표 떼기(함정 26 재발 방지 '파서는 입력 이름표로 시작하는 답을 받지 않는다'): user 메시지가 `질문: …`(`research_plan.yaml:21-22` 와 같은 꼴)이라 모델이 `{"question": "질문: 노인의 …"}` 처럼 이름표째 내면 원 질문 낱말이 다 들어 있어 낱말 검사를 통과한다. 그대로 쓰면 계획 입력이 `질문: 질문: …` 이 되고 plan step 의 `question_used`(06d 의 '이렇게 이해했어요' 줄)에도 이름표가 실린다 — 그래서 검사 전에 뗀다(`test_echoed_input_label_is_stripped`).
- terms 정리(`clean_terms`, 정함 9): 문자열만 → NFKC → 공백 정리 → 빈 것·`TERM_MAX_CHARS`(30)자 넘는 것 버림 → casefold 기준 중복 제거 → 앞에서 `MAX_TERMS`(4)개. 개수는 모델에 맡기지 않는다(함정 15). 프롬프트의 '2개 이상 4개 이하' 는 범위 규칙이지 견본이 아니다(`research_concepts.yaml` 의 '2개 이상 5개 이하' 선례).
- 프롬프트(정함 2): 변수 `question` 하나, parser `plain`, params `max_tokens: 600`·`temperature: 0.2`, `"예:"`·`"예시"` 없음, `guided_*` 없음(함정 25 — `test_prompts.py:146` `test_nl_library_prompts_do_not_send_removed_vllm_guided_params` 가 새 YAML 도 훑는다). user 는 `질문: {{ question }}` 한 줄(`research_plan.yaml` 과 같은 꼴).
- 로그 접두는 `[framing]` — 마무리의 운영 확인이 `docker logs nl-lib-celery-research-plan 2>&1 | grep '\[framing\]'` 로 센다(스위치 0 이면 0줄). **원 질문으로 물러날 때마다 `[framing]` 경고는 정확히 한 줄이다** — 호출 실패는 `frame_question` 이, 응답을 쓰지 못한 까닭(JSON 을 못 읽음·question 이 문자열 아님·비었거나 너무 김·원 질문 낱말이 빠짐)은 `parse_frame` 이 그 자리에서 한 번 찍고, `frame_question` 은 `parse_frame` 이 None 을 돌려줘도 다시 찍지 않는다. 그래서 `grep -c '\[framing\]'` 가 물러난 잡 수이고, 낱말 검사에서 떨어진 수만은 `grep -c '\[framing\] 넓힌 질문이 원 질문 낱말'` 로 센다(Task Z6·완료노트 이월 4 의 재료).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

Create `app/tests/test_research_framing.py`:

```python
"""services/research/framing.py — 시작 질문 넓히기(06c, 잡 파라미터 broaden).

LLM 은 모듈의 chat 을 monkeypatch 로 바꾼다. async 는 asyncio.run 으로 돈다(pytest-asyncio 가 없다).
"""
import asyncio
import json
import logging

import httpx
import pytest
from jinja2 import Environment, meta

from services.prompts import get_prompt
from services.research import framing
from services.research.framing import (
    BROADEN_TIMEOUT, Framing, clean_terms, frame_question, parse_frame, unframed,
)

ELDERLY = "노인의 우울과 사회적 지지에 관한 연구가 궁금해"
COMPUTING = "컴퓨팅 자원에 대한 연구가 궁금해"


def _reply(question, terms=()) -> str:
    return json.dumps({"question": question, "terms": list(terms)}, ensure_ascii=False)


def _framing_lines(caplog) -> list[str]:
    # 원 질문으로 물러날 때마다 [framing] 경고는 정확히 한 줄이다 — 판정 뒤 이 줄 수로 물러난 잡을 센다
    return [r.getMessage() for r in caplog.records if "[framing]" in r.getMessage()]


class TestPrompt:
    def test_prompt_takes_only_the_question_and_keeps_its_params(self):
        tpl = get_prompt("research_frame")
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == {"question"}
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": 600, "temperature": 0.2}
        assert tpl.user == "질문: {{ question }}"
        # vLLM 이 guided_* 를 조용히 버린다(함정 25 — test_prompts 가 모든 YAML 을 훑는다)
        assert not [k for k in tpl.params if k.startswith("guided_")]

    def test_prompt_rules_keep_words_and_carry_no_examples(self):
        system, user, _ = get_prompt("research_frame").render(question=ELDERLY)
        assert "원 질문에 쓰인 낱말을 빼거나 바꾸지 않고 모두 그대로 씁니다" in system
        assert "원 질문을 그대로 씁니다" in system
        assert "괄호로 예를 늘어놓지 마세요" in system
        assert "빼야 할 뜻을 범위 용어로 쓰지 마세요" in system
        assert '"question"' in system and '"terms"' in system
        # 예시는 모델이 베낀다(함정 15) — 개수는 코드가 자른다
        assert "예:" not in system + user and "예시" not in system + user
        assert user == f"질문: {ELDERLY}"


class TestParseFrame:
    def test_broadened_question_that_keeps_every_word_is_used(self):
        raw = _reply("클라우드·엣지 환경에서 컴퓨팅 자원을 할당하고 관리하는 방법에 대한 연구 동향은 어떠한가",
                     ["컴퓨팅 자원 할당", "클라우드 컴퓨팅"])
        assert parse_frame(raw, COMPUTING) == Framing(
            "클라우드·엣지 환경에서 컴퓨팅 자원을 할당하고 관리하는 방법에 대한 연구 동향은 어떠한가",
            ["컴퓨팅 자원 할당", "클라우드 컴퓨팅"])

    def test_particle_change_still_keeps_the_word(self):
        # '노인의' → '노인이' — 어절째 대조하면 떨어지지만 내용어(노인)는 그대로 있다
        raw = _reply("노인이 겪는 우울과 사회적 지지의 관계를 다룬 국내 연구는 어디까지 왔는가", ["노인 우울"])
        framed = parse_frame(raw, ELDERLY)
        assert framed is not None and framed.question.startswith("노인이 겪는 우울")

    def test_question_that_drops_a_word_is_refused(self, caplog):
        raw = _reply("노인의 사회적 지지와 삶의 만족에 관한 연구 동향", ["사회적 지지"])
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert parse_frame(raw, ELDERLY) is None
        (line,) = _framing_lines(caplog)
        assert line.startswith("[framing] 넓힌 질문이 원 질문 낱말") and "우울" in line

    @pytest.mark.parametrize("raw", [
        _reply("   "),
        json.dumps({"question": 3, "terms": ["노인"]}),
        json.dumps({"terms": ["노인 우울"]}, ensure_ascii=False),
        _reply("노인의 우울과 사회적 지지 " + "가" * 500),
    ], ids=["blank", "not-a-string", "missing", "too-long"])
    def test_empty_non_string_or_too_long_question_is_refused(self, raw, caplog):
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert parse_frame(raw, ELDERLY) is None
        assert len(_framing_lines(caplog)) == 1

    def test_specific_question_returned_as_it_is_is_kept(self):
        # 함정 26 — 모델이 입력을 그대로 베껴도 정상이다(이미 구체적인 질문은 그대로 두라고 했다)
        question = "「공공도서관 서비스 고객만족도 평가체계에 관한 연구」에서 출발해, 선행 연구는 어떻게 전개되어 왔는가?"
        framed = parse_frame(_reply(question, ["공공도서관 고객만족도"]), question)
        assert framed == Framing(question, ["공공도서관 고객만족도"])

    def test_echoed_input_label_is_stripped(self):
        # 함정 26 — 입력 이름표('질문:')째 옮겨 낸 답은 낱말 검사를 통과한다. 떼지 않으면 계획 입력이
        # '질문: 질문: …' 이 되고 화면의 '이렇게 이해했어요' 줄에도 이름표가 실린다
        assert parse_frame(_reply("질문: " + ELDERLY, ["노인 우울"]), ELDERLY) == Framing(ELDERLY, ["노인 우울"])
        # 앞 공백·전각 콜론도 같은 이름표다
        assert parse_frame(_reply("  질문 ： " + ELDERLY), ELDERLY) == Framing(ELDERLY, [])

    @pytest.mark.parametrize("raw", [None, "", "질문을 넓혔습니다.", "[1, 2]", '{"question": "노인의'],
                             ids=["none", "empty", "prose", "list", "cut"])
    def test_unreadable_reply_is_refused(self, raw, caplog):
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert parse_frame(raw, ELDERLY) is None
        assert len(_framing_lines(caplog)) == 1


class TestCleanTerms:
    def test_terms_are_normalized_deduplicated_and_cut_at_four(self):
        raw = ["ＣＳＲ", "csr", "  재무   성과 ", "기업의 사회적 책임", "지배구조", "환경 경영"]
        assert clean_terms(raw) == ["CSR", "재무 성과", "기업의 사회적 책임", "지배구조"]

    def test_terms_that_are_not_strings_empty_or_too_long_are_dropped(self):
        raw = ["클라우드", 3, None, "", "   ", ["엣지"], "가" * 31, "나" * 30]
        assert clean_terms(raw) == ["클라우드", "나" * 30]
        assert clean_terms("클라우드") == [] and clean_terms(None) == []


def _status_error() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://gemma.test/v1/chat/completions")
    return httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))


class TestFrameQuestion:
    def test_gemma_is_called_once_with_the_broaden_timeout(self, monkeypatch):
        calls = []

        async def fake_chat(messages, **kw):
            calls.append((messages, kw))
            return _reply("노인이 겪는 우울과 사회적 지지의 관계에 관한 국내 연구 동향", ["노인 우울", "사회적 지지"])

        monkeypatch.setattr(framing, "chat", fake_chat)
        out = asyncio.run(frame_question(ELDERLY))

        assert out == Framing("노인이 겪는 우울과 사회적 지지의 관계에 관한 국내 연구 동향", ["노인 우울", "사회적 지지"])
        ((messages, kw),) = calls
        # 모델·엔드포인트를 넘기지 않는다 — LLM_BASE_URL·LLM_MODEL(gemma). 시간은 chat 기본 120초가 아니라 20초
        assert kw == {"params": {"max_tokens": 600, "temperature": 0.2}, "timeout": BROADEN_TIMEOUT}
        assert BROADEN_TIMEOUT == 20
        assert [m["role"] for m in messages] == ["system", "user"]
        assert messages[1]["content"] == f"질문: {ELDERLY}"

    @pytest.mark.parametrize("error", [
        httpx.ReadTimeout("응답 없음"), httpx.ConnectError("연결 거부"), _status_error(),
        ValueError("JSON 아님"), KeyError("choices"), IndexError("list index out of range"),
    ], ids=["read-timeout", "connect", "status", "json", "key", "index"])
    def test_llm_failure_keeps_the_original_question(self, monkeypatch, caplog, error):
        async def fake_chat(messages, *, params=None, timeout=None):
            raise error

        monkeypatch.setattr(framing, "chat", fake_chat)
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert asyncio.run(frame_question(ELDERLY)) == unframed(ELDERLY) == Framing(ELDERLY, [])
        (line,) = _framing_lines(caplog)
        assert line.startswith("[framing] 넓히기 호출 실패")

    def test_refused_reply_keeps_the_original_question(self, monkeypatch, caplog):
        async def fake_chat(messages, *, params=None, timeout=None):
            return _reply("사회적 지지에 관한 연구 동향", ["사회적 지지"])     # 노인·우울이 빠졌다

        monkeypatch.setattr(framing, "chat", fake_chat)
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert asyncio.run(frame_question(ELDERLY)) == Framing(ELDERLY, [])
        # 까닭은 parse_frame 이 한 줄 남긴다 — frame_question 이 다시 찍으면 낱말 검사 실패가 두 번 세진다
        assert len(_framing_lines(caplog)) == 1

    def test_unexpected_errors_are_not_swallowed(self, monkeypatch):
        # 함정 19 — 코드 결함을 '원문'으로 숨기면 스위치를 켠 판정이 넓히기 없이 나온다. 계획 태스크가 계획 실패로 닫는다
        async def fake_chat(messages, *, params=None, timeout=None):
            raise RuntimeError("코드 결함")

        monkeypatch.setattr(framing, "chat", fake_chat)
        with pytest.raises(RuntimeError, match="코드 결함"):
            asyncio.run(frame_question(ELDERLY))
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_framing.py -q -p no:cacheprovider`

Expected: 수집 오류 — `E   ImportError: cannot import name 'framing' from 'services.research'`, 끝 줄 `1 error in …s`. (참고: `framing.py` 만 만들고 YAML 을 빼먹으면 `11 failed, 16 passed, 1 warning` — 프롬프트를 렌더하는 테스트가 `FileNotFoundError: 프롬프트 템플릿 없음` 으로 떨어진다.)

- [ ] **Step 3: 구현한다**

① Create `app/domains/nl_library/prompts/research_frame.yaml` (아래 YAML 글 그대로 — 정함 2):

```yaml
parser: plain
params:
  # 상한일 뿐이다 — 한 문장(원 질문 500자 안쪽 + 더한 말)과 범위 용어·JSON·코드 펜스를 한국어 토큰으로 덮는다
  max_tokens: 600
  temperature: 0.2
system: |-
  당신은 국내 학술논문 코퍼스를 다루는 연구 사서입니다.
  연구자의 질문을 연구 계획을 세우기 좋은 한 문장으로 다시 쓰고, 그 연구의 범위를 정하는 용어를 뽑습니다.

  규칙:
  - 원 질문에 쓰인 낱말을 빼거나 바꾸지 않고 모두 그대로 씁니다.
  - 질문이 이미 연구 대상·맥락·범위를 분명히 정했으면 원 질문을 그대로 씁니다.
  - 질문이 짧거나 넓으면 원 질문이 가리키는 연구 대상·맥락·관점을 더해 한 문장으로 씁니다. 원 질문에 없는 새 주제를 지어내지 마세요.
  - 괄호로 예를 늘어놓지 마세요.
  - 범위 용어는 이 연구의 범위를 정하는 짧은 명사구입니다. 어느 질문에나 붙을 수 있는 일반적인 말은 넣지 마세요.
  - 빼야 할 뜻을 범위 용어로 쓰지 마세요. 범위 용어에는 포함할 뜻만 씁니다.

  반드시 JSON 객체 하나로만 응답하세요. 설명이나 다른 텍스트는 출력하지 마세요.
  객체의 키는 "question" 과 "terms" 둘입니다. "question" 은 다시 쓴 질문 한 문장이고, "terms" 는 범위 용어 문자열 2개 이상 4개 이하의 배열입니다.
user: |-
  질문: {{ question }}
```

② Create `app/services/research/framing.py`:

```python
"""framing.py — 시작 질문 넓히기(06c, 잡 파라미터 broaden) — spec §12-2

개념 하나짜리 짧은 질문은 계획 프롬프트의 측면 목록을 그대로 옮겨 일반 틀이 된다(06b 계획 30개 중 약 25개).
계획 전에 gemma 를 한 번 불러 질문을 계획하기 좋은 한 문장으로 넓히고, 연구 범위를 정하는 용어(terms — 검색어
합성 query_context 의 재료)를 뽑는다. 계획 프롬프트(research_plan.yaml)·parse_plan 은 그대로다 — make_plan 에 넘기는
질문만 바뀐다. planner.py 가 아니라 이 모듈에 두는 까닭: 계획 태스크 테스트가 planner 모듈을 통째로 바꿔치기한다.

넓힌 문장은 코드가 검사한다 — 원 질문의 내용어(terms.content_words)가 하나라도 넓힌 문장에 들어 있지 않으면
(terms.contains) 원 질문을 쓴다. 모델이 원 질문을 그대로 내도(함정 26) 정상이다 — 이미 구체적인 질문은 그대로
두라고 했다. 입력 이름표('질문:')째 옮겨 낸 답은 이름표를 떼고 본다(함정 26). 원 질문으로 물러나는 것은
FRAME_FAILURES(chat 의 전송·상태·JSON·응답 모양 오류)·빈 응답·검사 실패뿐이고, 그 밖의 예외는 올린다 — 코드 결함·
태스크 제어 예외(SoftTimeLimitExceeded)를 '원문'으로 숨기면 스위치를 켠 판정이 넓히기 없이 나온다(함정 19). 계획
태스크가 그 예외를 계획 실패로 닫는다. 물러날 때마다 [framing] 경고가 정확히 한 줄 남는다 — 판정 뒤 그 줄 수로 센다.
"""
import logging
import re
import unicodedata
from dataclasses import dataclass

import httpx

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research.terms import contains, content_words

log = logging.getLogger(__name__)

# 초 — chat 기본 120초를 쓰지 않는다(DeepRead 질의 재작성 BOOK_CHAT_QUERY_REWRITE_TIMEOUT=20 선례).
# chat 의 최악은 이 값 + 연결 10초다(llm_client.chat_full). 잡 데드라인과 섞이지 않게 asyncio.timeout 을 따로 걸지 않는다
BROADEN_TIMEOUT = 20
MAX_TERMS = 4
# 용어는 검색어에 붙는다 — 긴 문장이 용어로 들어오면 검색어가 망가진다
TERM_MAX_CHARS = 30
# api/research.py ResearchCreate.question 의 max_length 와 같다
FRAMED_QUESTION_MAX = 500
# chat 이 실제로 내는 실패 — 전송·상태(httpx.HTTPError), 응답 본문 JSON 해석(ValueError), 응답 모양(KeyError·IndexError)
FRAME_FAILURES = (httpx.HTTPError, ValueError, KeyError, IndexError)
# 넓히기 user 메시지의 이름표(research_frame.yaml '질문: {{ question }}') — 모델이 이름표째 옮겨 내면 낱말 검사를
# 통과하므로 떼고 본다(함정 26). 그대로 두면 계획 입력이 '질문: 질문: …' 이 되고 question_used 에도 실린다
_ECHO_LABEL = re.compile(r"^\s*질문\s*[:：]\s*")


@dataclass(frozen=True)
class Framing:
    question: str        # make_plan 에 넘길 질문 — 넓힌 문장, 넓히지 않았으면 원문 그대로
    terms: list[str]     # 범위 용어(clean_terms) — 넓히지 않았으면 []


def unframed(question: str) -> Framing:
    """넓히지 않은 계획 입력 — 스위치 0·실패·검사 실패가 모두 이 모양이다."""
    return Framing(question, [])


def _squash(text: str) -> str:
    return " ".join(text.split())


def clean_terms(raw: object) -> list[str]:
    """문자열만, NFKC, 공백 정리, 빈 것·TERM_MAX_CHARS 넘는 것 버림, casefold 기준 중복 제거, 앞에서 MAX_TERMS 개.

    개수는 모델에 맡기지 않고 코드가 자른다(함정 15).
    """
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        term = _squash(unicodedata.normalize("NFKC", item))
        if not term or len(term) > TERM_MAX_CHARS or term.casefold() in seen:
            continue
        seen.add(term.casefold())
        out.append(term)
    return out[:MAX_TERMS]


def parse_frame(raw: str | None, question: str) -> Framing | None:
    """넓히기 응답 → Framing. 쓸 수 없으면 None(호출 쪽이 원 질문으로 물러난다).

    JSON 객체를 읽지 못하거나, "question" 이 문자열이 아니거나, 입력 이름표를 떼고 공백 정리한 뒤 비었거나
    FRAMED_QUESTION_MAX 를 넘거나, 원 질문의 내용어가 하나라도 넓힌 문장에 들어 있지 않으면 None 이다. 물러나는
    까닭마다 그 자리에서 [framing] 경고를 한 줄 남긴다(frame_question 은 다시 찍지 않는다) — 판정 뒤 낱말 검사에서
    떨어진 수를 '[framing] 넓힌 질문이 원 질문 낱말' 줄 수로 센다.
    """
    data = extract_json(raw or "")
    if data is None:
        log.warning("[framing] 응답에서 JSON 객체를 읽지 못해 원 질문을 쓴다 — %r", (raw or "")[:120])
        return None
    framed = data.get("question")
    if not isinstance(framed, str):
        log.warning("[framing] 응답의 question 이 없거나 문자열이 아니어서 원 질문을 쓴다 — %r", (raw or "")[:120])
        return None
    framed = _squash(_ECHO_LABEL.sub("", framed))
    if not framed or len(framed) > FRAMED_QUESTION_MAX:
        log.warning("[framing] 넓힌 질문이 비었거나 %d자를 넘어 원 질문을 쓴다", FRAMED_QUESTION_MAX)
        return None
    missing = [word for word in content_words(question) if not contains(framed, word)]
    if missing:
        log.warning("[framing] 넓힌 질문이 원 질문 낱말 %s 를 빠뜨려 원 질문을 쓴다 — %r", missing, framed[:120])
        return None
    return Framing(framed, clean_terms(data.get("terms")))


async def frame_question(question: str) -> Framing:
    """gemma 한 번(모델 인자 없음 = LLM_BASE_URL·LLM_MODEL)으로 질문을 넓힌다. 실패하면 원 질문(unframed)."""
    system, user, llm_params = get_prompt("research_frame").render(question=question)
    try:
        raw = await chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            params=llm_params, timeout=BROADEN_TIMEOUT,
        )
    except FRAME_FAILURES as e:
        log.warning("[framing] 넓히기 호출 실패 — 원 질문으로 계획한다: %s: %s", type(e).__name__, e)
        return unframed(question)
    framed = parse_frame(raw, question)
    if framed is None:
        # 까닭은 parse_frame 이 그 자리에서 한 줄 남겼다 — 여기서 다시 찍으면 한 번 물러난 것이 두 줄로 세진다
        return unframed(question)
    return framed
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_framing.py -q -p no:cacheprovider`

Expected: `27 passed, 1 warning` (TestPrompt 2 · TestParseFrame 14(1+1+1+4+1+1+5) · TestCleanTerms 2 · TestFrameQuestion 9(1+6+1+1))

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_framing.py tests/test_research_planner.py tests/test_prompts.py -q -p no:cacheprovider`

Expected: `54 passed, 1 warning` (framing 27 · planner 18 · prompts 9 — 계획 고정 테스트 `test_plan_prompt_inputs_params_and_output_format_stay` 와 `test_nl_library_prompts_do_not_send_removed_vllm_guided_params`(새 YAML 도 훑는다)가 고치지 않고 통과한다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git diff --stat -- app/services/research/planner.py app/domains/nl_library/prompts/research_plan.yaml app/tests/test_research_planner.py`

Expected: 빈 출력

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 파일. Task 앞 수 + 27 (C2 바로 뒤면 `5 failed, 2408 passed, 1 skipped, 2 warnings, 1 error`).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/domains/nl_library/prompts/research_frame.yaml app/services/research/framing.py app/tests/test_research_framing.py && git status --short && git commit -m "[Feat] round06c — 시작 질문 넓히기(research_frame.yaml·framing.py): gemma 1회·20초(BROADEN_TIMEOUT)로 질문을 계획하기 좋은 한 문장과 범위 용어 {question, terms} 로 받는다. 원 질문의 내용어가 하나라도 넓힌 문장에 없으면 원 질문을 쓰고, 모델이 원 질문을 그대로 내도 정상이며 입력 이름표 '질문:' 째 낸 답은 이름표를 뗀다(함정 26). 원 질문으로 물러날 때마다 까닭을 [framing] 경고 한 줄로 남긴다(낱말 검사 실패를 두 번 세지 않는다). terms 는 NFKC·공백 정리·30자 상한·casefold 중복 제거·4개. chat 의 전송·상태·JSON·응답 모양 오류만 원 질문으로 물러나고 그 밖의 예외는 올린다(함정 19 — 계획 실패로 닫는다). 프롬프트에 예시는 없다(함정 15). planner.py·research_plan.yaml 은 그대로다"
```

---

### Task C4: 계획 태스크에 넓히기를 잇는다 — plan step 결과·중간 알림

**왜:** spec §12-2 '넓히기' 의 자리 — 계획 태스크 `_plan_deep_research`(`app/workers/research_tasks.py:525-566`)의 `make_plan`(`:545`) 바로 앞, 같은 태스크 안에서 gemma 1회(태스크를 나누지 않는다). `make_plan` 에 넘기는 질문만 넓힌 문장이고 계획 프롬프트·`parse_plan`·`job.plan`(list[str])·승인 본문은 그대로다(D16 을 D25 가 덮음). 저장은 스키마 변경 없이 plan step result 안 모양만 넓힌다 — `{"subquestions", "question_used", "terms", "elapsed_ms"}`(06c 정함 5 — §12-7 계획 시간 지표가 `elapsed_ms` 를 읽는다). 넓히기가 끝나면 단계를 running 그대로 두고 `{"question_used", "terms"}` 를 먼저 알린다(정함 6 — `_save_progress` 방식, broaden 1 일 때만). §12-7 자동 테스트 '스위치 0 이면 계획 입력이 지금과 글자 그대로'·'계획 고정 테스트 그대로'.

**Files:**
- Modify: `app/workers/research_tasks.py` — `_plan_deep_research`(:525-566): 함수 안 import(:526), `_step`(:542-543) 뒤 `started`, try 블록(:544-551), 완료 `_finish`(:553)
- Modify: `app/models/research.py:100` — plan 칸 주석
- Test: Modify `app/tests/test_research_tasks.py` — import(:13-30), `_Harness.__init__`(:237-252) 끝 `framed` 칸, `TestPlan._patch`(:850-860), `TestPlan` 끝(:891-904 `test_cancel_during_planning_is_not_revived` 뒤)에 상수 `BROAD` 와 새 테스트 다섯

**알아 둘 것:**
- **`TestPlan._patch` 는 넓히기를 늘 대역으로 바꾼다** — 시그니처 `_patch(self, monkeypatch, rt, job, make_plan, *, frame=None)`. 태스크가 함수 안에서 `from services.research.framing import frame_question, unframed` 하므로 부를 때의 모듈 속성(대역)을 읽는다. 기본 대역 `_unframed` 는 받은 질문을 `h.framed` 에 남기고 `framing.unframed(question)` 을 돌려준다. 그래서 4인자 호출 다섯 곳(`TestPlan` :869·:883·:900, `TestStatusEvents` :1078·:1093 의 `TestPlan()._patch(monkeypatch, rt, job, _plan)`)은 고치지 않고, 기본값 커밋(Q4)으로 `broaden` 기본이 1 이 돼도 진짜 `chat`(HTTP·재시도·20초 마감 — `llm_client.py:220-291`)을 부르지 않는다. 진짜 넓히기를 거치는 테스트는 `frame=framing.frame_question` 을 넘기고 `framing.chat` 만 바꾼다(키워드 인자는 `_patch` 가 대역을 깔기 전에 평가되므로 그 자리에서 진짜 함수가 넘어간다).
- `framing` 모듈은 테스트 파일 머리에서 import 한다(`from services.research import framing`) — 새 테스트가 클래스 상수 `BROAD = framing.Framing(...)` 과 `framing.frame_question`·`framing.chat` 을 쓴다. `framing` 은 httpx·`services.llm_client`·`services.prompts`·`llm_json`·`terms` 만 끌어온다(planner 테스트가 이미 같은 모듈을 머리에서 import 한다 — redis·celery 무관). `_patch` 가 `sys.modules` 의 planner 를 바꿔치기해도 framing 은 planner 를 import 하지 않는다.
- 스위치 값은 `job.params` 에 적는다(`{"broaden": 0}`·`{"broaden": 1}`) — `_FakeJob.params = {}`(:212) 기본값에 기대지 않는다(Task C2 '알아 둘 것' — 기본값은 판정 뒤 Task Z7 이 바꿀 수 있다).
- 넓히기 호출은 `make_plan` 과 **같은 try** 안에 둔다 — `frame_question` 이 올린 예외(FRAME_FAILURES 밖)는 계획 실패로 닫힌다(정함 10 — spec §12-2:502 '잡을 실패시키지 않는다' 와 일부러 다르다). `SoftTimeLimitExceeded` 는 먼저 다시 올린다(그대로). `test_unexpected_broadening_error_fails_the_plan` 이 이것을 고정한다 — Task C3 의 `test_unexpected_errors_are_not_swallowed` 는 `frame_question` 이 예외를 올리는지까지만 보므로, 넓히기 호출을 try 밖으로 옮기는 리팩터링은 이 테스트가 잡는다.
- 넓히기는 `_step`(INSERT 뒤 commit) 다음에 돈다 — 읽기 트랜잭션이 닫힌 채 LLM 을 기다린다(함정 18). 대역 `_FakeSession.in_txn` 으로 본다.
- `time` 은 이미 import 돼 있다(`research_tasks.py:14`, `_SynthProgress.clock` 이 쓴다). 지역 변수 이름 `framing` 은 이 모듈의 다른 이름과 겹치지 않는다.
- `api/research.py` 의 `_plan_known`·`_carries_plan`(:519-531)은 `result.subquestions` 만 보므로 중간 알림 행은 '계획을 안다' 로 세지 않는다 — API 를 고치지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_tasks.py` import. old:

```python
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql import operators
```

new:

```python
import uuid
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy.sql import operators
```

② 같은 파일. old:

```python
from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, snapshot_state,
)
```

new:

```python
from services.research import framing
from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, snapshot_state,
)
```

③ 같은 파일 `_Harness.__init__` 끝. old:

```python
        # 대기 순번 ZSET 에서 뺀 잡
        self.unmarked: list = []
```

new:

```python
        # 대기 순번 ZSET 에서 뺀 잡
        self.unmarked: list = []
        # 넓히기(frame_question) 대역이 받은 질문 — TestPlan._patch 가 채운다
        self.framed: list[str] = []
```

④ 같은 파일 `TestPlan._patch`. old:

```python
class TestPlan:
    def _patch(self, monkeypatch, rt, job, make_plan):
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])
        planner = types.ModuleType("services.research.planner")

        async def _make_plan(question, *, params):
            assert not h.session.in_txn, "계획(LLM) 직전에 읽기 트랜잭션이 열려 있다"
            return await make_plan(question, params)

        planner.make_plan = _make_plan
        monkeypatch.setitem(sys.modules, "services.research.planner", planner)
        return h
```

new:

```python
class TestPlan:
    def _patch(self, monkeypatch, rt, job, make_plan, *, frame=None):
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])
        planner = types.ModuleType("services.research.planner")

        async def _make_plan(question, *, params):
            assert not h.session.in_txn, "계획(LLM) 직전에 읽기 트랜잭션이 열려 있다"
            return await make_plan(question, params)

        planner.make_plan = _make_plan
        monkeypatch.setitem(sys.modules, "services.research.planner", planner)

        # 넓히기는 늘 대역으로 바꾼다 — broaden 기본값이 1 로 바뀌어도(06c 판정) 계획 태스크를 도는 테스트가 진짜
        # chat(HTTP·재시도, BROADEN_TIMEOUT 까지)을 부르지 않는다. 태스크는 함수 안에서 import 하므로 부를 때의 모듈
        # 속성(이 대역)을 읽는다. 기본 대역은 받은 질문을 남기고 원 질문 그대로 둔다. 진짜 넓히기를 거치는 테스트는
        # frame=framing.frame_question 을 넘기고 framing.chat 만 바꾼다
        async def _unframed(question):
            h.framed.append(question)
            return framing.unframed(question)

        monkeypatch.setattr(framing, "frame_question", frame or _unframed)
        return h
```

⑤ 같은 파일 `TestPlan` 끝(`test_cancel_during_planning_is_not_revived` 의 마지막 두 줄 뒤). old:

```python
        assert out["status"] == "canceled"
        assert job.status == "canceled" and job.plan is None
```

new:

```python
        assert out["status"] == "canceled"
        assert job.status == "canceled" and job.plan is None

    BROAD = framing.Framing(
        "청소년의 독서 격차가 생기는 원인과 격차를 줄이는 중재에 관한 국내 연구는 어디까지 왔나",
        ["청소년 독서", "독서 격차 중재"],
    )

    def test_switch_off_plans_the_original_question_and_records_it(self, monkeypatch):
        """broaden 0 이면 계획 입력이 지금과 글자 그대로다 — 넓히기를 부르지 않고 중간 알림도 없다. 완료 result 에는
        계획에 넘긴 질문(원문)·빈 용어·계획 시간이 더 실린다. 기본값이 바뀌어도 뜻이 같게 값을 적는다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")
        job.params = {"broaden": 0}
        asked = []

        async def _plan(question, params):
            asked.append(question)
            return ["하위1", "하위2"]

        h = self._patch(monkeypatch, rt, job, _plan)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "awaiting_approval"
        assert asked == [job.question] == ["독서 격차 연구는 어디까지 왔나"]
        assert h.framed == [] and h.progress == []
        _, status, result, _ = h.finished[-1]
        assert status == "done"
        assert set(result) == {"subquestions", "question_used", "terms", "elapsed_ms"}
        assert (result["subquestions"], result["question_used"], result["terms"]) == (
            ["하위1", "하위2"], job.question, [])
        assert isinstance(result["elapsed_ms"], int) and result["elapsed_ms"] >= 0
        assert job.plan == ["하위1", "하위2"]

    def test_switch_on_plans_the_broadened_question_and_announces_it_first(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")
        job.params = {"broaden": 1}
        order = []
        h = None

        async def _frame(question):
            order.append(("frame", question))
            return self.BROAD

        async def _plan(question, params):
            order.append(("plan", question, len(h.progress)))
            return ["하위1"]

        h = self._patch(monkeypatch, rt, job, _plan, frame=_frame)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "awaiting_approval"
        # 넓힌 질문을 계획보다 먼저 알린다(단계는 running 그대로) — 계획은 넓힌 문장으로 세운다
        assert order == [("frame", "독서 격차 연구는 어디까지 왔나"), ("plan", self.BROAD.question, 1)]
        assert [r for _, r in h.progress] == [{"question_used": self.BROAD.question, "terms": self.BROAD.terms}]
        assert [a[1] for a in h.announced] == ["running", "done"]
        result = h.finished[-1][2]
        assert {k: result[k] for k in ("subquestions", "question_used", "terms")} == {
            "subquestions": ["하위1"], "question_used": self.BROAD.question, "terms": self.BROAD.terms}
        # 원 질문은 그대로 남는다(보고서 머리·기록·critic_scope 1·핵심 개념이 읽는다). 계획은 make_plan 결과 그대로
        assert job.question == "독서 격차 연구는 어디까지 왔나"
        assert job.plan == ["하위1"]

    def test_broadening_waits_with_no_read_transaction_open(self, monkeypatch):
        # 함정 18 — 넓히기도 LLM 을 기다린다. 읽기 트랜잭션을 쥔 채 기다리면 FastAPI 기동 DDL 을 막는다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")
        job.params = {"broaden": 1}
        open_at_frame = []
        h = None

        async def _frame(question):
            open_at_frame.append(h.session.in_txn)
            return framing.unframed(question)

        async def _plan(question, params):
            return ["하위1"]

        h = self._patch(monkeypatch, rt, job, _plan, frame=_frame)
        asyncio.run(rt._plan_deep_research(str(job.id)))

        assert open_at_frame == [False]

    def test_failed_broadening_still_plans_the_original_question(self, monkeypatch):
        """진짜 frame_question 을 거친다 — 넓히기 LLM 이 시간을 넘겨도 잡은 원 질문으로 계획해 승인 대기로 간다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")
        job.params = {"broaden": 1}
        asked = []

        async def _timeout(messages, *, params=None, timeout=None):
            raise httpx.ReadTimeout("넓히기 응답 없음")

        async def _plan(question, params):
            asked.append(question)
            return ["하위1"]

        h = self._patch(monkeypatch, rt, job, _plan, frame=framing.frame_question)
        monkeypatch.setattr(framing, "chat", _timeout)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "awaiting_approval" and job.status == "awaiting_approval"
        assert asked == [job.question]
        # 실패여도 중간 알림은 한 번 — 원 질문 그대로라 화면은 '이렇게 이해했어요'를 숨긴다
        assert [r for _, r in h.progress] == [{"question_used": job.question, "terms": []}]
        result = h.finished[-1][2]
        assert (result["question_used"], result["terms"]) == (job.question, [])

    def test_unexpected_broadening_error_fails_the_plan(self, monkeypatch):
        """넓히기 밖 예외(코드 결함)는 원문으로 숨기지 않고 계획 실패로 닫는다(정함 10 — 함정 19)."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")
        job.params = {"broaden": 1}
        asked = []

        async def _broken(question):
            raise RuntimeError("넓히기 코드 결함")

        async def _plan(question, params):
            asked.append(question)
            return ["하위1"]

        h = self._patch(monkeypatch, rt, job, _plan, frame=_broken)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "failed" and job.status == "failed"
        assert asked == [] and h.progress == []
        _, status, result, _ = h.finished[-1]
        assert status == "failed" and "넓히기 코드 결함" in result["error"]
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `5 failed, 106 passed, 2 warnings` — 실패는 정확히 새 다섯이다:
- `TestPlan::test_switch_off_plans_the_original_question_and_records_it` — `assert {'subquestions'} == {'elapsed_ms', 'question_used', 'subquestions', 'terms'}`(완료 result 에 칸이 없다)
- `TestPlan::test_switch_on_plans_the_broadened_question_and_announces_it_first` — `order` 가 `[('plan', '독서 격차 연구는 어디까지 왔나', 0)]`(넓히기를 부르지 않는다)
- `TestPlan::test_broadening_waits_with_no_read_transaction_open` — `open_at_frame == []`
- `TestPlan::test_failed_broadening_still_plans_the_original_question` — `h.progress == []`(중간 알림이 없다)
- `TestPlan::test_unexpected_broadening_error_fails_the_plan` — `AssertionError: assert ('awaiting_approval' == 'failed'`(넓히기를 부르지 않아 대역의 예외가 나지 않고 원 질문으로 계획해 승인 대기로 간다)

기존 `TestPlan` 셋·`TestStatusEvents` 의 계획 둘은 통과한다(`_patch` 가 넓히기를 대역으로 바꾸고 지금 코드는 넓히기를 부르지 않는다).

- [ ] **Step 3: 구현한다**

① `app/workers/research_tasks.py` `_plan_deep_research` 머리. old:

```python
async def _plan_deep_research(job_id: str) -> dict:
    from services.research.planner import make_plan
```

new:

```python
async def _plan_deep_research(job_id: str) -> dict:
    from services.research.framing import frame_question, unframed
    from services.research.planner import make_plan
```

② 같은 함수 — 계획 단계. old:

```python
            step = await _step(db, jid, seq, "plan", "연구 계획 수립",
                               detail="질문을 하위질문으로 분해하는 중입니다")
            try:
                plan = await make_plan(question, params=params)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                log.exception("[research] 계획 수립 실패 job=%s", jid)
                await _finish(db, step, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e), expect=("planning",))

            await _finish(db, step, "done", {"subquestions": plan})
```

new:

```python
            step = await _step(db, jid, seq, "plan", "연구 계획 수립",
                               detail="질문을 하위질문으로 분해하는 중입니다")
            # 계획 시간(넓히기 + 계획) — 06c 판정의 계획 시간 지표가 plan step 결과의 elapsed_ms 를 읽는다
            started = time.monotonic()
            try:
                # 넓히기(06c, 잡 파라미터 broaden)는 계획 프롬프트를 그대로 두고 make_plan 에 넘기는 질문만 바꾼다.
                # 원 질문으로 물러나는 실패(FRAME_FAILURES·빈 응답·낱말 검사)는 frame_question 이 삼키고, 그 밖의
                # 예외는 아래에서 계획 실패로 닫는다(함정 19). job.question 은 원문 그대로다
                if params["broaden"]:
                    framing = await frame_question(question)
                    # 단계는 running 그대로 넓힌 질문을 먼저 알린다 — 계획 중 화면이 '이렇게 이해했어요'를 먼저 보인다.
                    # subquestions 가 없어 API 는 이 행을 '계획을 안다'로 세지 않는다
                    await _save_progress(db, step, {"question_used": framing.question, "terms": framing.terms})
                else:
                    framing = unframed(question)
                plan = await make_plan(framing.question, params=params)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                log.exception("[research] 계획 수립 실패 job=%s", jid)
                await _finish(db, step, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e), expect=("planning",))

            await _finish(db, step, "done", {
                "subquestions": plan, "question_used": framing.question, "terms": framing.terms,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            })
```

`_transition(…, plan=plan, …)`(:554-556)·실패 경로·바깥 except 는 그대로다.

③ `app/models/research.py:100` — plan 칸 주석. old:

```python
    # plan:       {"subquestions": [...]}                 LLM 원안 (승인본은 job.plan)
```

new:

```python
    # plan:       {"subquestions": [...], "question_used": "...", "terms": [...], "elapsed_ms": n}
    #             subquestions 는 LLM 원안(승인본은 job.plan). question_used 는 계획에 넘긴 질문 — 넓히기(잡 파라미터
    #             broaden 1)가 넓힌 한 문장, 끄거나 실패하면 원 질문(job.question 은 늘 원문). terms 는 넓히기가 뽑은
    #             범위 용어(검색어 합성 query_context 의 재료 — 실행 태스크가 ResearchState 에 싣는다), 넓히지 않았으면 [].
    #             elapsed_ms 는 넓히기 + 계획에 걸린 시간.
    #             도는 중(broaden 1, 넓히기가 끝난 뒤)에는 {"question_used", "terms"} 로 먼저 알린다 — subquestions 가
    #             없어 API 는 이 행을 '계획을 안다'로 세지 않는다. 06c 전 잡은 {"subquestions": [...]} 뿐이다.
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `111 passed, 2 warnings`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_planner.py tests/test_research_api.py tests/test_research_framing.py tests/test_research_models.py -q -p no:cacheprovider`

Expected: `187 passed, 1 warning` (planner 18 · api 124 · framing 27 · models 18 — 실패 0) — 계획 고정 테스트(`test_research_planner.py` 18)와 승인 API(`TestApprove` — 본문 `{"plan": [str]}`·422 6종), `test_research_models.py::TestResearchModelShape::test_step_kinds_are_exactly_what_the_worker_records`(워커 소스의 `_step` kind 집합 — 이 Task 는 `_step` 호출을 더하지 않는다)가 그대로 통과한다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git diff --stat $(git merge-base HEAD dev) -- app/services/research/planner.py app/domains/nl_library/prompts/research_plan.yaml app/domains/nl_library/prompts/research_critique.yaml app/domains/nl_library/prompts/research_critique_question.yaml app/domains/nl_library/prompts/research_synthesize.yaml app/api/research.py app/tests/test_research_planner.py`

Expected: 빈 출력

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 파일. Task 앞 수 + 5 (C3 바로 뒤면 `5 failed, 2413 passed, 1 skipped, 2 warnings, 1 error`).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/workers/research_tasks.py app/models/research.py app/tests/test_research_tasks.py && git status --short && git commit -m "[Feat] round06c — 계획 태스크가 broaden 1 이면 계획 전에 질문을 넓히고 먼저 알린다: _plan_deep_research 의 make_plan 앞에서 frame_question 을 한 번 부르고 단계를 running 그대로 {question_used, terms} 를 _save_progress 로 알린 뒤 넓힌 문장으로 계획한다. broaden 0 이면 넓히기를 부르지 않아 계획 입력이 지금과 글자 그대로다. 완료 result 는 {subquestions, question_used, terms, elapsed_ms}(끄거나 실패하면 원 질문·[]), job.question·job.plan·승인 본문은 그대로다. 넓히기 밖 예외는 계획 실패로 닫는다(함정 19 — 테스트로 고정). models 의 plan 칸 주석을 맞추고, TestPlan._patch 는 넓히기를 늘 대역으로 바꿔 기본값이 바뀌어도 진짜 chat 을 부르지 않게 한다"
```

---

### Task C5: 실행 태스크가 계획 단계의 `terms` 를 `ResearchState`·스냅숏에 싣는다

**왜:** spec §12-2 '실행 태스크(`_run_deep_research`)는 마지막 plan step 결과의 `terms` 를 `ResearchState` 에 담고 스냅숏에 넣는다'. 넓히기(Task C3·C4)는 계획 태스크에서 돌고, 검색은 승인 뒤 다른 태스크(`run_deep_research`)에서 돈다 — 그 사이 다리는 DB 의 plan step result 뿐이다(스키마 변경 없음). 필드와 스냅숏 왕복은 Task C2 가 만들었고, 이 Task 는 읽어서 채운다. 06c 정함 13: `state.terms` 는 스위치와 무관하게 늘 담는다(검색어에 쓰는 것은 `query_context` 1 일 때뿐 — Task C6). 그래야 나눠 판정할 때 `--plan shared` + 갈래 1 `{broaden 1, query_context 1}` 이 '계획은 같고 검색어만 다른' 갈래가 된다(정함 20).

**Files:**
- Modify: `app/workers/research_tasks.py` — 새 `_plan_terms`(`_corpus_range` :365-375 바로 뒤, `_transition` 앞), `_run_deep_research` 의 잡 읽기(dev :588-592 — Task C4 가 `_plan_deep_research` 에 줄을 더해 아래로 밀렸다, 글자로 찾는다)와 새 상태 만들기(dev :605-607)
- Test: Modify `app/tests/test_research_tasks.py` — `_patch_pipeline`(:255-323)의 시그니처·독스트링·`_plan_terms` 대역·대역 목록, 새 `class TestPlanTerms`(`TestPlan` 바로 뒤 = `class _RecordingSession(_FakeSession):` 앞)

**알아 둘 것:**
- `_plan_terms` 는 `select(ResearchStep.result)…order_by(ResearchStep.seq.desc()).limit(1)` 을 **`.scalar_one_or_none()`** 으로 받는다 — `.first()`·`.scalars()` 는 쓰지 않는다(`_corpus_range` 의 `.first()` 를 따라 하지 않는다). 테스트 대역 `_Result`(`test_research_tasks.py:124-137`)에는 `scalar_one`·`scalar_one_or_none`·`all` 만 있고, `_FakeSession.execute` 는 모르는 SELECT 에 `_Result(self.scalar)`(:172)를 돌려준다. `ResearchStep`·`select` 는 이미 import 돼 있다(`research_tasks.py:20`·:27-30).
- 지금은 잡마다 계획 단계가 하나다(`retry_research` 는 계획을 다시 돌리지 않는다 — `api/research.py:297-` 가 계획 없는 잡을 409 로 막고 실행 태스크만 다시 넣는다). 그래도 spec 이 '마지막 plan step' 이라 했으므로 `kind == "plan"` 중 seq 가 가장 큰 행을 읽는다 — 대회 뒤 '넓힌 문장 고쳐 다시 계획하기'(§12-9)가 계획 단계를 더 쓰게 돼도 그대로 맞다. 행이 없거나 06c 전 잡(`{"subquestions": [...]}`)이거나 모양이 다르면(`dict` 아님·`terms` 가 list 아님) `[]`, 원소는 비지 않은 문자열만 남긴다.
- 읽기 자리: `job = await db.get(...)` 과 같은 읽기 트랜잭션 안, `seq = await _next_seq(db, jid)`·`await db.commit()` **앞** — 이 commit 이 탐색(LLM) 전에 트랜잭션을 닫는다(함정 18 — `_patch_pipeline` 의 `_explore` 대역이 `assert not session.in_txn` 으로 본다).
- 스냅숏에서 되살린 잡(`stage == "explored"`, `restore_state` — dev :596)은 **스냅숏의 terms 를 쓴다** — 그 탐색이 실제로 쓴 용어다. 새 상태(`ResearchState(...)` — dev :605-607)에만 `terms=terms` 를 준다. 전멸 스냅숏을 버리고 탐색부터 다시 하는 경로(dev :597-601)도 새 상태라 계획 단계의 용어를 다시 읽는다.
- **`_patch_pipeline` 에 `_plan_terms` 대역을 반드시 넣는다** — `_run_deep_research` 를 도는 기존 테스트 수십 개는 `_FakeSession(job=job, scalar=0)`(:263)·`_StepTableSession`(:1677-) 을 쓰는데, 진짜 `_plan_terms` 가 그 위에서 돌면 모르는 SELECT 에 `_Result(0)`·`_Result(rows=…)` 를 받는다(지금 구현은 모양 검사로 `[]` 를 내지만, 기존 테스트 전부가 그 검사 하나에 기대게 된다). `_corpus_range` 를 대역으로 두는 것과 같은 까닭이다(:279-280·:316). 진짜 `_plan_terms` 는 `TestPlanTerms` 에서만 `_FakeSession(scalar=…)` 로 직접 부른다 — 그래서 SELECT 의 조건은 `TestPlanTerms` 만 지킨다. 첫 테스트는 SQL 글만이 아니라 바인드 값(`job_id_1`·`kind_1`)까지 보므로 `_RecordingSession`(:907 — 실행한 문장 객체를 남긴다. `TestPlanTerms` 보다 아래에 정의되지만 모듈 수준 클래스라 테스트를 실행할 때 보인다)을 쓴다. `_FakeSession.execute` 는 `str(stmt)` 만 남기는데(:162-172) SQL 글에는 바인드 값이 없다 — kind 글자가 틀려도(늘 빈 목록) 같은 글이고, `job_id` 조건이 빠지면(다른 잡의 마지막 계획 단계 용어를 붙인다) 칼럼 이름만 보는 단언으로는 잡히지 않는다. `_run_deep_research` 를 도는 다른 테스트는 모두 `_patch_pipeline` 의 대역을 거치므로 이 회귀를 잡을 곳이 이 테스트뿐이다.
- **Step 2 의 실패 모양:** `_patch_pipeline` 의 대역 목록은 `monkeypatch.setattr(rt, name, fn)`(raising 기본값 True)로 바꾸므로, 함수가 아직 없는 동안에는 `_patch_pipeline` 을 쓰는 **기존 테스트도 모두** `AttributeError: … has no attribute '_plan_terms'` 로 떨어진다. 실패 사유가 이것 하나뿐인지를 Step 2 의 둘째 명령으로 확인한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_tasks.py` — `_patch_pipeline` 머리. old:

```python
def _patch_pipeline(monkeypatch, rt, *, job, explored: list, synthesized: list,
                    explore=None, synthesize=None, session=None) -> _Harness:
    """DB·Redis·LLM 을 대역으로 바꾸고 호출만 기록한다.

    explore·synthesize 로 하위 동작을 끼워 넣는다(취소를 찍거나 예외를 던지는 식).
    session 을 주면 그 대역을 쓴다(research_steps 행까지 흉내 내야 할 때).
    """
```

new:

```python
def _patch_pipeline(monkeypatch, rt, *, job, explored: list, synthesized: list,
                    explore=None, synthesize=None, session=None,
                    terms: list[str] | None = None) -> _Harness:
    """DB·Redis·LLM 을 대역으로 바꾸고 호출만 기록한다.

    explore·synthesize 로 하위 동작을 끼워 넣는다(취소를 찍거나 예외를 던지는 식).
    session 을 주면 그 대역을 쓴다(research_steps 행까지 흉내 내야 할 때).
    terms 는 마지막 계획 단계의 범위 용어(_plan_terms 대역이 돌려준다 — 진짜 _plan_terms 는 TestPlanTerms 가 본다).
    """
```

② 같은 함수 — `_corpus_range` 대역 뒤. old:

```python
    async def _corpus_range(db):
        return {"from": "2002", "to": "2026", "n_papers": 7}
```

new:

```python
    async def _corpus_range(db):
        return {"from": "2002", "to": "2026", "n_papers": 7}

    async def _plan_terms(db, job_id):
        return list(terms or [])
```

③ 같은 함수 — 대역 목록. old:

```python
        ("_corpus_range", _corpus_range), ("publish", _publish),
```

new:

```python
        ("_corpus_range", _corpus_range), ("_plan_terms", _plan_terms), ("publish", _publish),
```

④ 같은 파일 — `TestPlan` 바로 뒤에 새 클래스. old:

```python
class _RecordingSession(_FakeSession):
    """실행한 문장 객체를 남긴다 — UPDATE 에 실제로 실은 값을 읽기 위해서다."""
```

new:

```python
class TestPlanTerms:
    """실행 태스크는 마지막 계획 단계가 뽑은 범위 용어를 ResearchState 와 체크포인트에 싣는다(06c)."""

    PLAN_RESULT = {"subquestions": ["하위1"], "question_used": "넓힌 질문",
                   "terms": ["컴퓨팅 자원", "클라우드"], "elapsed_ms": 1200}

    def test_reads_the_terms_of_the_latest_plan_step(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = _RecordingSession(scalar=self.PLAN_RESULT)
        jid = uuid.uuid4()

        assert asyncio.run(rt._plan_terms(db, jid)) == ["컴퓨팅 자원", "클라우드"]
        # 이 잡의 계획 단계 중 마지막 것 — job_id·kind 로 거르고 seq 내림차순 첫 행(다시 계획하기 — spec §12-9).
        # 바인드 값까지 본다 — job_id 조건이 빠지면 다른 잡의 용어를 붙이고, kind 글자가 틀리면 늘 빈 목록이다
        (stmt,) = db.stmts
        sql = str(stmt)
        assert "FROM research_steps" in sql and "ORDER BY research_steps.seq DESC" in sql and "LIMIT" in sql
        params = stmt.compile().params
        assert params["job_id_1"] == jid and params["kind_1"] == "plan"

    @pytest.mark.parametrize("result", [{"subquestions": ["하위1"]}, None],
                             ids=["before-06c", "no-plan-step"])
    def test_plan_step_without_terms_gives_none(self, monkeypatch, result):
        rt = _load_tasks(monkeypatch)
        assert asyncio.run(rt._plan_terms(_FakeSession(scalar=result), uuid.uuid4())) == []

    def test_values_that_are_not_strings_are_dropped(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        mixed = {"terms": ["클라우드", 3, None, "", "  ", ["엣지"], "엣지 컴퓨팅"]}
        assert asyncio.run(rt._plan_terms(_FakeSession(scalar=mixed), uuid.uuid4())) == ["클라우드", "엣지 컴퓨팅"]
        for odd in ({"terms": "클라우드"}, ["클라우드"], "클라우드"):
            assert asyncio.run(rt._plan_terms(_FakeSession(scalar=odd), uuid.uuid4())) == []

    def test_fresh_run_carries_the_terms_into_the_state_and_checkpoint(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        seen = []

        async def _record(state, subq):
            seen.append(list(state.terms))

        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[], explore=_record,
                        terms=["컴퓨팅 자원", "클라우드"])
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert seen == [["컴퓨팅 자원", "클라우드"], ["컴퓨팅 자원", "클라우드"]]
        assert job.state_snapshot["terms"] == ["컴퓨팅 자원", "클라우드"]

    def test_resumed_run_keeps_the_terms_of_its_snapshot(self, monkeypatch):
        # 종합만 다시 하는 재개 — 그 탐색이 쓴 용어가 남는다(그 사이 계획 단계를 다시 읽어 덮지 않는다)
        rt = _load_tasks(monkeypatch)
        snap = _explored_snapshot()
        snap["terms"] = ["스냅숏 용어"]
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=snap, status="queued")
        seen = []

        async def _record(state, should_stop):
            seen.append(list(state.terms))
            return {"sections": []}

        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[], synthesize=_record,
                        terms=["다른 용어"])
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert seen == [["스냅숏 용어"]]


class _RecordingSession(_FakeSession):
    """실행한 문장 객체를 남긴다 — UPDATE 에 실제로 실은 값을 읽기 위해서다."""
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `70 failed, 47 passed, 2 warnings` — 새 6개(`TestPlanTerms` 다섯 함수, parametrize 포함)와 `_patch_pipeline` 을 쓰는 기존 64개(Task C4 의 새 `TestPlan` 다섯 포함)가 모두 같은 까닭으로 떨어진다: `AttributeError: <module 'workers.research_tasks' …> has no attribute '_plan_terms'`(대역 목록이 아직 없는 이름을 바꾸려 한다 — `_plan_terms` 를 직접 부르는 셋은 `module 'workers.research_tasks' has no attribute '_plan_terms'`).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider --tb=line 2>&1 | grep "Error" | grep -vc "_plan_terms"`

Expected: `0` — `_plan_terms` 가 없다는 것 말고 다른 실패 사유가 없다.

- [ ] **Step 3: 구현한다**

① `app/workers/research_tasks.py` — `_corpus_range` 바로 뒤에 새 함수. old:

```python
    return {"from": row[0], "to": row[1], "n_papers": row[2]}


async def _transition(
```

new:

```python
    return {"from": row[0], "to": row[1], "n_papers": row[2]}


async def _plan_terms(db: AsyncSession, job_id: uuid.UUID) -> list[str]:
    """마지막 계획 단계가 뽑은 범위 용어(06c 넓히기) — 검색어 합성(query_context 1)의 재료.

    계획 단계가 여럿이면(다시 계획하기 — spec §12-9) seq 가 가장 큰 행을 읽는다. 행이나 terms 칸이 없거나(06c 전 잡)
    모양이 다르면 빈 목록이다 — 비지 않은 문자열만 남긴다.
    """
    result = (await db.execute(
        select(ResearchStep.result)
        .where(ResearchStep.job_id == job_id, ResearchStep.kind == "plan")
        .order_by(ResearchStep.seq.desc())
        .limit(1)
    )).scalar_one_or_none()
    terms = result.get("terms") if isinstance(result, dict) else None
    if not isinstance(terms, list):
        return []
    return [t for t in terms if isinstance(t, str) and t.strip()]


async def _transition(
```

② 같은 파일 `_run_deep_research` — 잡 읽기. old:

```python
            job = await db.get(ResearchJob, jid)
            stage, snapshot = job.stage, job.state_snapshot
            question, params, plan = job.question, job.params, job.plan
            seq = await _next_seq(db, jid)
            await db.commit()
```

new:

```python
            job = await db.get(ResearchJob, jid)
            stage, snapshot = job.stage, job.state_snapshot
            question, params, plan = job.question, job.params, job.plan
            # 같은 읽기 트랜잭션에서 읽는다 — 아래 commit 이 LLM(탐색) 전에 닫는다. 스냅숏에서 되살린 잡은 스냅숏의 용어를 쓴다
            terms = await _plan_terms(db, jid)
            seq = await _next_seq(db, jid)
            await db.commit()
```

③ 같은 함수 — 새 상태. old:

```python
                state = ResearchState(
                    job_id=str(jid), question=question, params=merge_params(params or {}),
                )
```

new:

```python
                state = ResearchState(
                    job_id=str(jid), question=question, params=merge_params(params or {}),
                    terms=terms,
                )
```

`restore_state`(스냅숏 경로)·`state.corpus_range = await _corpus_range(db)`·탐색 루프·체크포인트(`state_snapshot=snapshot_state(state)` — Task C2 가 `terms` 를 싣는다)는 그대로다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `117 passed, 2 warnings` (C4 뒤 111 + 6)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_state.py tests/test_research_models.py -q -p no:cacheprovider`

Expected: `112 passed` — 스냅숏 왕복(`TestSnapshotRoundTrip::test_terms_survive`·`TestSnapshotEvolution::test_old_snapshot_without_terms_gets_no_terms`)과 `test_step_kinds_are_exactly_what_the_worker_records`(이 Task 는 `_step` 호출을 더하지 않는다 — SELECT 만 한다)가 그대로다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 파일. Task 앞 수 + 6 (C4 바로 뒤면 `5 failed, 2419 passed, 1 skipped, 2 warnings, 1 error`).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/workers/research_tasks.py app/tests/test_research_tasks.py && git status --short && git commit -m "[Feat] round06c — 실행 태스크가 마지막 계획 단계의 범위 용어를 ResearchState·체크포인트에 싣는다: _plan_terms 가 kind plan 중 seq 가 가장 큰 단계의 result.terms 를 잡 읽기와 같은 트랜잭션에서 읽고(06c 전 잡·모양이 다르면 빈 목록, 비지 않은 문자열만) 새 상태에 담는다. 스위치와 무관하게 늘 담고 검색어에 쓰는 것은 query_context 1 일 때뿐이다. 스냅숏에서 되살린 잡은 그 탐색이 쓴 스냅숏의 용어를 그대로 쓴다. 테스트의 _patch_pipeline 은 _corpus_range 처럼 _plan_terms 도 대역으로 바꾸고 terms 키워드로 용어를 넣는다"
```

---

### Task C6: 검색어 합성 — 첫 검색어·재검색 제안

**왜:** spec §12-2 '검색어 합성' — 잡 파라미터 `query_context` 1 이면 첫 검색어(하위질문)와 재검색 제안에서 군더더기 `국내 학술논문에서`(D18 계획 프롬프트가 하위질문에 붙이게 된 말 — 06b 이월 §7-12)를 떼고, 계획 단계가 뽑은 범위 용어(`state.terms` — Task C5) 가운데 검색어에 없는 것만 붙인다(06b 이월 §7-10). `critic_scope` 0 이면 재검색 제안은 하위질문만 보고 만들어져 원 질문 맥락을 잃는다 — '컴퓨팅' 동음이의(06b 이월 §7-11)가 들어오는 자리다. 합성은 runner 의 `_search_query(state, text)` 한 곳이다(06c 정함 11) — 첫 검색어와 재검색 제안이 같은 함수를 거치므로 `_next_query` 의 중복 비교·`subq.queries`·critic `tried_queries`·회차 기록·이벤트가 모두 실제로 보낸 글이 된다. §12-7 자동 테스트 'compose 연결·`_next_query` 합성 꼴 비교·스위치 0 이면 검색어 글자 그대로'.

**Files:**
- Modify: `app/services/research/runner.py` — 모듈 독스트링(:1-10), import(:22-24 뒤), 새 `_search_query`(`_next_query` :61-67 바로 뒤), `_recheck_query` 의 마지막 줄(:169), `explore_subquestion` 의 첫 검색어(:188)
- Test: Modify `app/tests/test_research_runner.py` — 새 `class TestQueryComposition`(`TestRequery` :461-482 바로 뒤 = `class TestEvidenceOrder:` 앞)
- 고치지 않음: `app/services/research/critic.py`(:205 `tried_queries` 는 `subq.queries` 를 그대로 잇는다)·`explorer.py`·`synthesizer.py`·`app/services/search/pipeline.py`, runner 의 `_next_query`(:61-67)·`subq.queries.append(query)`(:201)·`query = next_query`(:318)

**알아 둘 것:**
- 합성 자리는 둘이다. ① 첫 검색어 `query = _search_query(state, subq.text)`(:188). ② 재검색 제안 — `_recheck_query` 가 `_next_query` 에 넘기기 **전에** 제안마다 `_search_query` 로 바꾼다(:169). `_next_query` 는 고치지 않는다: 비교 대상 `subq.queries` 가 이미 합성한 검색어라 합성한 꼴끼리 `query_key`(공백 정리·casefold — `planner.py:34-36`)로 비교된다. 글자로는 처음 보는 제안이어도 합성하면 이미 보낸 검색어와 같으면 건너뛴다(`test_suggestion_whose_composed_form_was_tried_is_skipped`).
- `_recheck_query` 가 돌려준 `next_query` 가 합성본이므로 `:318` 의 `query = next_query` 는 그대로 두면 된다 — 회차 기록 `next_query`·critique 이벤트 `next_query`·다음 회차 `search` 이벤트 `query`·`subq.queries`(:201)·trail `queries`(`synthesizer.py:351`)·search 단계 result `queries`(`research_tasks.py:645`)가 모두 실제로 보낸 글이다(`explorer.py:98-100` 원칙 — 기록은 실제로 보낸 검색어).
- critic 은 고치지 않는다(§12-5 'critic 은 `tried_queries` 가 합성본을 받는지만 확인'). 그 확인은 가짜 critic 이 아니라 **진짜 `critique`** 를 거친다 — `critic_module.chat` 만 대역으로 바꾸고 프롬프트의 `이미 시도한 검색어:` 줄(`critic.py:205` `", ".join(subq.queries)` → `research_critique.yaml:37`, critic_scope 1 갈래도 `research_critique_question.yaml:39` 에 같은 줄)을 읽는다(`test_critic_sees_the_composed_queries_it_tried`, 선례 `TestOriginalQuestion.test_job_param_picks_the_prompt` :442-458). critic 이 받는 하위질문은 `subq.text` 그대로다 — 절 소제목·critic 의 하위질문·핵심 개념 입력은 바뀌지 않는다(`test_critic_keeps_the_subquestion_text`). 검색 호출 모양(`explore_fn(query, params=params, db=db)`)·임베딩·리랭크도 그대로다 — 검색어 문자열만 바뀐다.
- `query_context` 0 이면 `_search_query` 가 text 를 그대로 돌려준다 — 하위질문·재검색 제안이 지금과 글자 그대로다(`test_switch_off_searches_the_subquestion_word_for_word` — 군더더기·용어가 있어도 그대로). `query_context` 1 이어도 `state.terms` 가 비면(broaden 0 잡·06c 전 잡) 군더더기만 뗀다(`test_empty_terms_only_remove_fillers`).
- 스위치 값은 기본값에 기대지 않고 `merge_params({"query_context": 0 또는 1, "max_recheck": …})` 로 적는다(Task C2 '알아 둘 것' — 기본값은 판정 뒤 Task Z7 이 바꿀 수 있다).
- Step 2 에서 새 9개 중 셋은 구현 전에도 통과한다 — `test_switch_off_searches_the_subquestion_word_for_word`·`test_terms_already_in_the_subquestion_are_not_repeated`(군더더기가 없고 용어가 이미 든 하위질문은 합성해도 글자 그대로다)·`test_critic_keeps_the_subquestion_text` 는 '바뀌지 않는 것'을 지키는 테스트다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_runner.py` — `TestRequery` 바로 뒤에 새 클래스. old:

```python
class TestEvidenceOrder:
    """evidence_ids 는 critic(20편)과 절(5편)이 앞에서 자른다 — 순서가 곧 선택이다."""
```

new:

```python
class TestQueryComposition:
    """검색어 합성(06c, 잡 파라미터 query_context) — 첫 검색어와 재검색 제안에서 '국내 학술논문에서' 를 떼고
    계획 단계의 범위 용어 중 없는 것을 붙인다. 하위질문 글(절 소제목·critic 의 하위질문)은 그대로다.
    스위치 값은 기본값에 기대지 않고 적는다(기본값은 06c 판정 뒤 바뀔 수 있다)."""

    TEXT = "국내 학술논문에서 컴퓨팅 자원 할당 방법"
    TERMS = ["컴퓨팅 자원", "클라우드"]

    def _state(self, switch, *, terms=TERMS, max_recheck=0):
        return ResearchState(job_id="j", question="컴퓨팅 자원에 대한 연구가 궁금해",
                             params=merge_params({"query_context": switch, "max_recheck": max_recheck}),
                             terms=list(terms))

    def _searched(self):
        sent = []

        async def _explore(query, *, params, db):
            sent.append(query)
            return _hits(["A"], query=query)
        return sent, _explore

    def test_switch_off_searches_the_subquestion_word_for_word(self):
        sent, explore = self._searched()
        sq = SubQuestion(idx=0, text=self.TEXT)
        asyncio.run(explore_subquestion(self._state(0, max_recheck=1), sq, db=None, explore_fn=explore,
                                        critique_fn=_SuggestingCritic(["국내 학술논문에서 가상화 기반 자원 스케줄링"]), emit=None))
        assert sent == [self.TEXT, "국내 학술논문에서 가상화 기반 자원 스케줄링"]
        assert sq.queries == sent

    def test_first_search_drops_fillers_and_adds_missing_terms(self):
        sent, explore = self._searched()
        asyncio.run(explore_subquestion(self._state(1), SubQuestion(idx=0, text=self.TEXT), db=None,
                                        explore_fn=explore, critique_fn=_FakeCritic(), emit=None))
        assert sent == ["컴퓨팅 자원 할당 방법 클라우드"]

    def test_terms_already_in_the_subquestion_are_not_repeated(self):
        sent, explore = self._searched()
        asyncio.run(explore_subquestion(self._state(1), SubQuestion(idx=0, text="클라우드 컴퓨팅 자원 할당"),
                                        db=None, explore_fn=explore, critique_fn=_FakeCritic(), emit=None))
        assert sent == ["클라우드 컴퓨팅 자원 할당"]

    def test_recheck_searches_the_composed_suggestion(self):
        sent, explore = self._searched()
        sq = SubQuestion(idx=0, text=self.TEXT)
        asyncio.run(explore_subquestion(self._state(1, max_recheck=1), sq, db=None, explore_fn=explore,
                                        critique_fn=_SuggestingCritic(["국내 학술논문에서 가상화 기반 자원 스케줄링"]), emit=None))
        # 재검색 제안은 critic_scope 0 이면 원 질문을 모르고 하위질문만 보고 만든다 — 동음이의가 들어오는 자리다
        assert sent == ["컴퓨팅 자원 할당 방법 클라우드", "가상화 기반 자원 스케줄링 컴퓨팅 자원 클라우드"]
        assert sq.queries == sent

    def test_suggestion_whose_composed_form_was_tried_is_skipped(self):
        # 제안 '컴퓨팅 자원 할당 방법' 은 글자로는 처음이지만 합성하면 첫 검색어와 같다 — 합성한 꼴끼리 비교해 건너뛴다
        sent, explore = self._searched()
        sq = SubQuestion(idx=0, text=self.TEXT)
        critic = _SuggestingCritic(["컴퓨팅 자원 할당 방법", "엣지 컴퓨팅 자원"])
        asyncio.run(explore_subquestion(self._state(1, max_recheck=1), sq, db=None, explore_fn=explore,
                                        critique_fn=critic, emit=None))
        assert sq.queries == ["컴퓨팅 자원 할당 방법 클라우드", "엣지 컴퓨팅 자원 클라우드"]

    def test_critic_sees_the_composed_queries_it_tried(self, monkeypatch):
        # spec §12-5 — critic 은 고치지 않고 tried_queries 가 합성본을 받는지만 본다. 진짜 critique 를 거쳐
        # 프롬프트의 '이미 시도한 검색어' 줄을 읽는다(critic.py 가 subq.queries 를 잇는 방식이 바뀌어도 잡힌다).
        # 합성한 꼴이어야 critic 이 같은 제안을 되풀이하지 않는다
        prompts = []
        replies = iter([
            '{"verdict": "insufficient", "note": "부족", "new_queries": ["가상화 기반 자원 스케줄링"], "off_topic": []}',
            '{"verdict": "sufficient", "note": "충분하다", "new_queries": [], "off_topic": []}',
        ])

        async def fake_chat(messages, *, params=None, timeout=None):
            prompts.append(messages[1]["content"])
            return next(replies)

        monkeypatch.setattr(critic_module, "chat", fake_chat)
        _, explore = self._searched()
        asyncio.run(explore_subquestion(self._state(1, max_recheck=1), SubQuestion(idx=0, text=self.TEXT),
                                        db=None, explore_fn=explore, emit=None))
        tried = [line for p in prompts for line in p.splitlines() if line.startswith("이미 시도한 검색어:")]
        assert tried == ["이미 시도한 검색어: 컴퓨팅 자원 할당 방법 클라우드",
                         "이미 시도한 검색어: 컴퓨팅 자원 할당 방법 클라우드, 가상화 기반 자원 스케줄링 컴퓨팅 자원 클라우드"]

    def test_round_history_and_events_carry_the_query_actually_sent(self):
        events, emit = _recorder()
        sent, explore = self._searched()
        sq = SubQuestion(idx=0, text=self.TEXT)
        asyncio.run(explore_subquestion(self._state(1, max_recheck=1), sq, db=None, explore_fn=explore,
                                        critique_fn=_SuggestingCritic(["가상화 기반 자원 스케줄링"]), emit=emit))
        assert [r["query"] for r in sq.rounds] == sent
        assert [r["next_query"] for r in sq.rounds] == ["가상화 기반 자원 스케줄링 컴퓨팅 자원 클라우드", None]
        assert [s["query"] for s in _of(events, "search")] == sent
        assert [c["next_query"] for c in _of(events, "critique")] == ["가상화 기반 자원 스케줄링 컴퓨팅 자원 클라우드", None]

    def test_critic_keeps_the_subquestion_text(self):
        # 검색어만 바뀐다 — critic 의 하위질문(과 절 소제목)은 하위질문 글 그대로다
        texts = []

        async def _critic(subq, evidence, *, params, question=None):
            texts.append(subq.text)
            return Verdict("sufficient", note="충분")

        _, explore = self._searched()
        sq = SubQuestion(idx=0, text=self.TEXT)
        asyncio.run(explore_subquestion(self._state(1), sq, db=None, explore_fn=explore,
                                        critique_fn=_critic, emit=None))
        assert texts == [self.TEXT] and sq.text == self.TEXT

    def test_empty_terms_only_remove_fillers(self):
        # 넓히지 않은 잡(broaden 0)은 용어가 없다 — 군더더기만 뗀다
        sent, explore = self._searched()
        asyncio.run(explore_subquestion(self._state(1, terms=[]), SubQuestion(idx=0, text=self.TEXT), db=None,
                                        explore_fn=explore, critique_fn=_FakeCritic(), emit=None))
        assert sent == ["컴퓨팅 자원 할당 방법"]


class TestEvidenceOrder:
    """evidence_ids 는 critic(20편)과 절(5편)이 앞에서 자른다 — 순서가 곧 선택이다."""
```

`asyncio`·`critic_module`·`ResearchState`·`SubQuestion`·`merge_params`·`Verdict`·`explore_subquestion` 은 파일 머리에서 이미 import 한다(:14-26 — `critic_module` 은 :23). `_hits`·`_FakeCritic`·`_SuggestingCritic`·`_recorder`·`_of` 는 이 파일의 대역 그대로다.

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_runner.py -q -p no:cacheprovider`

Expected: `6 failed, 84 passed, 2 warnings` — 실패는 정확히 다음 여섯이다(지금은 하위질문·제안을 글자 그대로 보낸다):
- `TestQueryComposition::test_first_search_drops_fillers_and_adds_missing_terms` — `assert ['국내 학술논문에서 컴퓨팅 자원 할당 방법'] == ['컴퓨팅 자원 할당 방법 클라우드']`
- `TestQueryComposition::test_recheck_searches_the_composed_suggestion` — 첫 검색어부터 `'국내 학술논문에서 …'`
- `TestQueryComposition::test_suggestion_whose_composed_form_was_tried_is_skipped` — `sq.queries` 가 `['국내 학술논문에서 컴퓨팅 자원 할당 방법', '컴퓨팅 자원 할당 방법']`(글자로 비교해 첫 제안을 새 검색어로 본다)
- `TestQueryComposition::test_critic_sees_the_composed_queries_it_tried` — `assert ['이미 시도한 검색어:...화 기반 자원 스케줄링'] == ['이미 시도한 검색어:... 컴퓨팅 자원 클라우드']`(첫 줄 차이 `'이미 시도한 검색어: 국내 학술논문에서 컴퓨팅 자원 할당 방법' != '이미 시도한 검색어: 컴퓨팅 자원 할당 방법 클라우드'`)
- `TestQueryComposition::test_round_history_and_events_carry_the_query_actually_sent` — `assert ['가상화 기반 자원 스케줄링', None] == ['가상화 기반 자원 스케줄링 컴퓨팅 자원 클라우드', None]`
- `TestQueryComposition::test_empty_terms_only_remove_fillers` — `assert ['국내 학술논문에서 컴퓨팅 자원 할당 방법'] == ['컴퓨팅 자원 할당 방법']`

- [ ] **Step 3: 구현한다**

`app/services/research/runner.py`.

① 모듈 독스트링 끝. old:

```python
진행 중계도 같은 이유로 emit 인자로 주입받는다. `services.research.relay` 를
여기서 import 하면 relay 가 물고 있는 `redis` 가 이 모듈을 여는 모든 곳에
필요해지고, 미설치 환경에서는 테스트 수집 단계가 통째로 죽는다
(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).
"""
```

new:

```python
진행 중계도 같은 이유로 emit 인자로 주입받는다. `services.research.relay` 를
여기서 import 하면 relay 가 물고 있는 `redis` 가 이 모듈을 여는 모든 곳에
필요해지고, 미설치 환경에서는 테스트 수집 단계가 통째로 죽는다
(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).

검색어는 _search_query 한 곳에서 만든다(06c, 잡 파라미터 query_context) — 첫 검색어와 재검색 제안이 같은 합성을
거치므로 subq.queries·회차 기록·search 이벤트·critic 의 tried_queries 가 모두 실제로 보낸 글이다. 절 소제목·critic 의
하위질문은 subq.text 그대로다.
"""
```

② import. old:

```python
from services.research.state import (
    Evidence, HitRow, ResearchState, SubQuestion, research_stats,
)
```

new:

```python
from services.research.state import (
    Evidence, HitRow, ResearchState, SubQuestion, research_stats,
)
from services.research.terms import compose_query
```

`terms.py` 는 표준 라이브러리만 import 한다(Task C1) — runner 를 여는 곳(워커·테스트)에 새 의존이 생기지 않는다.

③ `_next_query` 바로 뒤에 새 함수. old:

```python
    seen = {query_key(q) for q in tried}
    for q in suggestions:
        if query_key(q) not in seen:
            return q
    return None
```

new:

```python
    seen = {query_key(q) for q in tried}
    for q in suggestions:
        if query_key(q) not in seen:
            return q
    return None


def _search_query(state: ResearchState, text: str) -> str:
    """실제로 보낼 검색어. 잡 파라미터 query_context 가 1 이면 군더더기를 떼고 계획 단계의 범위 용어를 붙인다
    (terms.compose_query), 0 이면 text 글자 그대로다.

    첫 검색어(하위질문)와 재검색 제안이 같은 함수를 거친다 — 그래야 _next_query 의 중복 비교가 합성한 꼴끼리
    맞고, subq.queries(critic 의 tried_queries)·회차 기록·search 이벤트가 실제로 보낸 글이 된다(explorer 원칙).
    """
    if state.params["query_context"]:
        return compose_query(text, state.terms)
    return text
```

④ `_recheck_query` 의 마지막 줄. old:

```python
    return _next_query(verdict.new_queries, subq.queries)
```

new:

```python
    # 제안을 합성한 꼴로 바꿔 비교한다 — subq.queries 는 이미 합성한 검색어다
    return _next_query([_search_query(state, q) for q in verdict.new_queries], subq.queries)
```

⑤ `explore_subquestion` 의 첫 검색어. old:

```python
    emit = emit or _noop_emit
    params = state.params
    query = subq.text
```

new:

```python
    emit = emit or _noop_emit
    params = state.params
    query = _search_query(state, subq.text)
```

`subq.queries.append(query)`(:201)·`explore_fn(query, …)`(:202)·`query = next_query`(:318)·critique 호출(`subq` 그대로)은 고치지 않는다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_runner.py -q -p no:cacheprovider`

Expected: `90 passed, 2 warnings` (C5 뒤 81 + 9) — 기존 `TestRequery`·`TestRoundEvents`·`TestOriginalQuestion` 등은 `merge_params({...})` 의 `query_context` 가 0 이라 그대로 통과한다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_critic.py tests/test_research_explorer.py tests/test_research_synthesizer.py -q -p no:cacheprovider`

Expected: `207 passed, 2 warnings` — critic 프롬프트 sha256 잠금·`tried_queries` 렌더·explorer·synthesizer 테스트가 고치지 않고 통과한다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git diff --stat $(git merge-base HEAD dev) -- app/services/research/critic.py app/services/research/explorer.py app/services/research/synthesizer.py app/services/search/pipeline.py`

Expected: 빈 출력

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 파일. Task 앞 수 + 9 (C5 바로 뒤면 `5 failed, 2428 passed, 1 skipped, 2 warnings, 1 error`).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/services/research/runner.py app/tests/test_research_runner.py && git status --short && git commit -m "[Feat] round06c — 검색어 합성(query_context 1): 하위질문·재검색 제안에 범위 용어를 붙이고 '국내 학술논문에서' 를 뗀다(06b 이월 §7-10·§7-11·§7-12). runner 의 _search_query 한 곳에서 첫 검색어와 재검색 제안을 같은 compose_query 로 합성하므로 _next_query 의 중복 비교가 합성한 꼴끼리 맞고 subq.queries·critic tried_queries·회차 기록·search 이벤트가 실제로 보낸 글이다. query_context 0 이면 지금과 글자 그대로다. 절 소제목·critic 의 하위질문·검색 호출은 그대로이고 critic·explorer·synthesizer 는 고치지 않는다"
```

---

### Task C7: 탐색 후보 목록 이벤트 `candidates`

**왜:** spec §12-2 '탐색 후보 목록 이벤트'·Q9(06c 몫 — 백엔드만). 06d 의 근거 장부가 자기점검이 판정하기 전에 이번 검색이 이은 후보를 '검토 중' 더미로 세웠다가, 이어지는 `critique` 의 채택(`adopted_papers`)·뺌(`excluded_papers`)으로 옮긴다. 지금 화면은 `critique` 가 와야 비로소 논문이 보여 탐색 중 수십 초가 비어 보인다. 이벤트 이름 `candidates`·하위질문 키 `subq_idx`(06c 정함 3 — runner 의 `search`·`critique`·`counters` 와 `_StepRef.event`(`research_tasks.py:141`)가 모두 `subq_idx` 다, spec §12-2 는 커밋 `c5d05b0` 에서 이 글자로 맞췄다)는 06d 와의 계약이라 이름·키·모양을 바꾸지 않는다. 회차마다 늘 한 번, 이은 근거가 없어도 빈 목록으로 내고(정함 4), 스위치와 무관하다. §12-7 자동 테스트 '회차마다 자기점검 전에 한 번, 모양·linked 순서, 스냅숏에 없음'.

**Files:**
- Modify: `app/services/research/runner.py` — `explore_subquestion` 의 `await emit("counters", research_stats(state))`(dev :264 — Task C6 뒤 글자 그대로) 바로 뒤, `critique_fn` 호출 앞에 한 블록
- Test: Modify `app/tests/test_research_runner.py` — **기존 테스트 하나를 고친다:** `TestRoundEvents.test_counters_follow_each_search`(:325-334)의 기대 순서(:329-330). 그 뒤 파일 끝(`TestSharedChunkScore` 뒤)에 도우미 `_brief` 와 새 `class TestCandidatesEvent`
- Test: Modify `app/tests/test_research_tasks.py` — `TestLiveProgress`(:1319-) 에 테스트 하나(`test_section_progress_is_saved_on_the_synthesis_step` 앞)
- 고치지 않음: `app/workers/research_tasks.py` 의 `_round_emitter`(:220-231 — 모든 kind 를 `publish` 하고 `critique` 때만 `_save_progress` 한다), `app/services/research/relay.py`, `app/api/research.py`(SSE 는 relay 를 그대로 흘린다)

**알아 둘 것:**
- 모양(계획 머리 「다른 줄과의 경계」의 06d `candidates` 행 — 정함 3): `{"subq_idx": int, "round": int, "papers": [{"cnts_id", "title", "personal_author", "pub_date"}]}` — `papers` 는 `_paper_brief`(`runner.py:85-89`) 그대로다(`excluded_papers` 와 같은 서지 요약 — 06d 가 같은 그리기 함수를 쓸 수 있다). `emit(kind, payload)` 의 kind 가 SSE 이벤트의 `kind` 가 된다(`_round_emitter` → `relay.publish`).
- 자리: 이번 검색의 `linked`(:222-258 — 이 하위질문에 이은 근거 id, 이은 순서)가 확정되고 `subq.evidence_ids` 순위를 다시 매긴(:260-263) 뒤, `counters`(:264) 바로 다음, `critique_fn`(:267) 앞. 순서는 회차마다 `search` → `counters` → `candidates` → (자기점검 LLM) → `critique` 다.
- `papers` 순서는 `linked` 순서 = 이번 검색 결과가 이 하위질문에 이은 순서다(`build_evidence` 가 돌려준 순서, 다른 하위질문이 먼저 만든 근거의 재사용 링크 포함). 순위순(`evidence_ids` — 회차 1위가 앞자리, 나머지 점수순)이 아니다. 앞 회차에 무관하다고 뺀 논문(`subq.excluded_cnts` — :226)과 몫·전체 상한에 막힌 후보(:236-241)는 `linked` 에 들지 않으므로 후보도 아니다. `linked` 의 id 는 이 시점에 모두 `state.evidence` 에 있다(무관 제외는 critique 뒤에 지운다).
- **저장하지 않는다:** 화면 이벤트일 뿐이라 회차 기록(`subq.rounds`)·`state_snapshot`·단계 result 에 넣지 않는다. `_round_emitter` 는 `critique` 때만 진행을 저장하므로 `candidates` 는 흘리기만 한다 — 재접속한 화면에는 '검토 중' 더미가 없고, 지나간 후보는 `critique` 의 채택·뺌으로 이미 보인다(spec '복원하지 않는다').
- **스위치와 무관하게 늘 낸다**(정함 4) — 검색·판정을 바꾸지 않는다. 그래서 스위치 0 이어도 회차마다 이벤트가 하나 는다. 이벤트 종류의 전체 순서를 글자 그대로 단언하는 기존 테스트는 `TestRoundEvents.test_counters_follow_each_search`(:329-330) 하나뿐이라 그 기대 순서를 고친다(테스트 수는 늘지 않는다). 다른 테스트는 그대로 통과한다 — `TestExploreSubquestion.test_emit_is_called_for_progress`(:198-216)는 `in` 으로 보고, `TestRoundHistory.test_history_matches_what_was_streamed`(:387-403)는 `_of` 로 kind 를 골라 보며, `test_research_tasks.py` `TestLiveProgress.test_each_critique_saves_rounds_and_counters`(:1342-1343)는 `search`·`critique` 만 걸러 본다. 실제 runner 를 도는 테스트 파일은 이 둘(`test_research_runner.py`·`test_research_tasks.py`)뿐이다.
- 옛 화면(06c 배포 때 nuxt 는 재생성하지 않는다)은 모르는 이벤트를 무시한다(`frontend/utils/researchEvents.ts:329` `default: return view`). 타입·리듀서·'검토 중' 더미는 06d 몫이다.
- Step 2 에서 새 runner 테스트 8개 중 `test_candidates_are_not_kept_in_the_round_history` 하나는 구현 전에도 통과한다 — 회차 키 집합·스냅숏에 후보가 **없음**을 지키는 테스트다.

- [ ] **Step 1: 실패하는 테스트를 쓰고 기존 기대 순서를 고친다**

① `app/tests/test_research_runner.py` — `TestRoundEvents.test_counters_follow_each_search` 의 기대 순서. old:

```python
        assert [k for k, _ in events] == [
            "search", "counters", "critique", "search", "counters", "critique"]
```

new:

```python
        # 탐색 후보(candidates)는 counters 뒤·자기점검 전에 회차마다 한 번 — 스위치와 무관하게 늘 낸다(06c)
        assert [k for k, _ in events] == [
            "search", "counters", "candidates", "critique", "search", "counters", "candidates", "critique"]
```

counters 값 단언(:331-334)은 그대로 둔다.

② 같은 파일 끝(`TestSharedChunkScore` 의 마지막 테스트 끝)에 도우미와 새 클래스. old:

```python
        assert b.evidence_chunks == {"E1": ["P-c1"]}
        assert b.chunk_scores == {"P-c1": 0.95}
        assert a.chunk_scores == {"P-c1": 0.2}
```

new:

```python
        assert b.evidence_chunks == {"E1": ["P-c1"]}
        assert b.chunk_scores == {"P-c1": 0.95}
        assert a.chunk_scores == {"P-c1": 0.2}


def _brief(cnts_id):
    """_hits 서지(저자 없음)의 _paper_brief — candidates 이벤트의 papers 항목."""
    return {"cnts_id": cnts_id, "title": f"논문 {cnts_id}", "personal_author": None, "pub_date": "2008-06"}


class TestCandidatesEvent:
    """탐색 후보 목록(06c, Q9) — 회차마다 이번 검색이 이은 후보를 자기점검 전에 낸다. 06d 장부가 '검토 중' 더미를
    세웠다가 critique 의 채택·뺌으로 옮긴다. 화면 이벤트일 뿐이라 회차 기록·스냅숏에는 없다."""

    def _state(self, *texts, **params):
        st = ResearchState(job_id="j", question="q", params=merge_params(params))
        st.subquestions = [SubQuestion(idx=i, text=t) for i, t in enumerate(texts)]
        return st

    def _run(self, st, sq, explore, critic):
        events, emit = _recorder()
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=explore, critique_fn=critic, emit=emit))
        return events

    def test_each_round_streams_its_candidates_before_the_critique(self):
        st = self._state("가", max_recheck=1)
        events = self._run(st, st.subquestions[0],
                           _explore_table({"가": ["A", "B"], "보완": ["C"]}),
                           _ScriptedCritic(("insufficient", [], ["보완"]), ("sufficient", [], [])))
        assert [k for k, _ in events] == [
            "search", "counters", "candidates", "critique", "search", "counters", "candidates", "critique"]
        assert [(c["subq_idx"], c["round"]) for c in _of(events, "candidates")] == [(0, 1), (0, 2)]

    def test_candidates_follow_the_order_they_were_linked(self):
        # 이은 순서(검색 결과 순서)다 — 순위순(evidence_ids)이 아니다. 다른 하위질문이 먼저 만든 근거(A)도 든다
        st = self._state("가", "나", max_recheck=0)
        first, second = st.subquestions
        scores = {"가": [0.9], "나": [0.3, 0.5, 0.9]}
        table = {"가": ["A"], "나": ["B", "C", "A"]}

        async def _explore(query, *, params, db):
            return _hits(table[query], query=query, scores=scores[query])

        self._run(st, first, _explore, _ScriptedCritic(("sufficient", [], [])))
        events = self._run(st, second, _explore, _ScriptedCritic(("sufficient", [], [])))
        (candidates,) = _of(events, "candidates")
        assert [p["cnts_id"] for p in candidates["papers"]] == ["B", "C", "A"]
        # 순위는 회차 1위 B 가 앞자리, 나머지는 점수순 — 후보 순서와 다르다
        assert [st.evidence[e].cnts_id for e in second.evidence_ids] == ["B", "A", "C"]

    def test_candidates_carry_paper_briefs(self):
        st = self._state("가", max_recheck=0)
        events = self._run(st, st.subquestions[0], _explore_table({"가": ["A", "B"]}),
                           _ScriptedCritic(("sufficient", [], [])))
        assert _of(events, "candidates") == [
            {"subq_idx": 0, "round": 1, "papers": [_brief("A"), _brief("B")]}]

    def test_round_without_new_links_streams_an_empty_list(self):
        # 빈 목록도 낸다 — 06d 는 다음 회차 후보로 앞 더미를 갈음한다
        st = self._state("가", max_recheck=0)
        events = self._run(st, st.subquestions[0], _empty_explore, _ScriptedCritic(("sufficient", [], [])))
        assert _of(events, "candidates") == [{"subq_idx": 0, "round": 1, "papers": []}]

    def test_excluded_or_budget_blocked_papers_are_not_candidates(self):
        # 앞 회차에 무관하다고 뺀 B 는 다시 걸려도 잇지 않는다 — 후보도 아니다
        st = self._state("가", max_recheck=1)
        events = self._run(st, st.subquestions[0],
                           _explore_table({"가": ["A", "B"], "보완": ["B", "C"]}),
                           _ScriptedCritic(("insufficient", [2], ["보완"]), ("sufficient", [], [])))
        assert [[p["cnts_id"] for p in c["papers"]] for c in _of(events, "candidates")] == [["A", "B"], ["C"]]
        # 몫(하위질문 둘·전체 2편 → 1편)에 막힌 B 도 잇지 않는다
        st = self._state("가", "나", max_recheck=0, max_evidence=2, min_evidence_per_subq=1)
        events = self._run(st, st.subquestions[0], _explore_table({"가": ["A", "B"]}),
                           _ScriptedCritic(("sufficient", [], [])))
        assert [p["cnts_id"] for p in _of(events, "candidates")[0]["papers"]] == ["A"]
        assert st.subquestions[0].budget_capped == 1

    def test_candidates_are_not_kept_in_the_round_history(self):
        st = self._state("가", max_recheck=0)
        (sq,) = st.subquestions
        self._run(st, sq, _explore_table({"가": ["A"]}), _ScriptedCritic(("sufficient", [], [])))
        assert set(sq.rounds[0]) == {
            "round", "query", "found_chunks", "new_papers", "verdict", "note", "next_query", "excluded",
            "excluded_papers", "flagged", "flagged_papers", "adopted_papers"}
        from services.research.state import snapshot_state
        assert "candidates" not in json.dumps(snapshot_state(st), ensure_ascii=False)

    @pytest.mark.parametrize("switch", [0, 1])
    def test_candidates_are_streamed_whatever_the_switches(self, switch):
        st = ResearchState(job_id="j", question="q", params=merge_params(
            {"broaden": switch, "query_context": switch, "max_recheck": 0}))
        sq = SubQuestion(idx=0, text="가")
        st.subquestions = [sq]
        events = self._run(st, sq, _fake_explore, _ScriptedCritic(("sufficient", [], [])))
        assert [k for k, _ in events].count("candidates") == 1
```

`json`·`pytest` 는 파일 머리에서 이미 import 한다(:16·:21). `_ScriptedCritic`(:763-773 — `(verdict, off_topic, new_queries)` 튜플을 차례로 낸다)·`_explore_table`·`_empty_explore`·`_fake_explore`·`_hits`·`_recorder`·`_of` 는 이 파일의 대역 그대로다(모듈 수준이라 파일 끝 클래스에서도 보인다).

③ `app/tests/test_research_tasks.py` — `TestLiveProgress` 에 하나. old:

```python
    def test_section_progress_is_saved_on_the_synthesis_step(self, monkeypatch):
```

new:

```python
    def test_candidates_are_streamed_but_not_saved(self, monkeypatch):
        """탐색 후보(06c)는 화면 이벤트일 뿐이다 — 진짜 러너를 돌려 흘린 candidates 가 그대로 나가고, 진행 저장은
        자기점검(critique)에서만 한다. 단계 result 에 싣지 않으므로 재접속한 화면에는 '검토 중' 더미가 없다."""
        from services.research.critic import Verdict
        from services.research.runner import explore_subquestion

        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = None
        saved_at = []

        async def _hits_for(query, *, params, db):
            hit = {"book_id": "A", "chunk_id": "A-c1", "text": "대목", "page_start": 1, "page_end": 1,
                   "score": 0.9, "rank_score": 0.9}
            return [hit], {"A": {"title": "논문 A", "pub_date": "2008-06"}}

        async def _critic(subq, evidence, *, params, question=None):
            saved_at.append(len(h.progress))
            return Verdict("sufficient", note="충분")

        async def _real_round(state, subq):
            await explore_subquestion(state, subq, db=None, explore_fn=_hits_for, critique_fn=_critic,
                                      emit=h.emit)

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[], explore=_real_round)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [e[0] for e in h.events if e[0] in ("search", "counters", "candidates", "critique")] == [
            "search", "counters", "candidates", "critique"]
        (candidates,) = [e[1] for e in h.events if e[0] == "candidates"]
        assert candidates == {"subq_idx": 0, "round": 1, "papers": [
            {"cnts_id": "A", "title": "논문 A", "personal_author": None, "pub_date": "2008-06"}]}
        # 판정 전까지 저장 0번, 회차를 닫는 critique 에서 한 번 — 저장한 result 에 후보가 없다
        assert saved_at == [0] and len(h.progress) == 1
        assert set(h.progress[0][1]) == {"rounds", "counters"}
        assert "candidates" not in json.dumps(h.progress[0][1], ensure_ascii=False)

    def test_section_progress_is_saved_on_the_synthesis_step(self, monkeypatch):
```

`_patch_pipeline` 의 `_explore` 대역은 워커가 넘긴 진짜 `_round_emitter` 를 `h.emit` 에 둔다(`h.emit = emit`) — 이 테스트는 그 emit 으로 진짜 러너(`explore_subquestion`)를 돌려 `publish`(대역 `h.events`)와 `_save_progress`(대역 `h.progress`)를 함께 본다. `runner`·`critic` 은 이 테스트에서만 쓰므로 함수 안에서 import 한다(파일 머리 import 를 늘리지 않는다).

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_runner.py tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `9 failed, 207 passed, 2 warnings` — 실패는 정확히 다음 아홉이다(아직 `candidates` 를 내지 않는다):
- `test_research_runner.py::TestRoundEvents::test_counters_follow_each_search` — 고친 기대 순서: `assert ['search', 'c...', 'critique'] == ['search', 'c...ounters', ...]`
- `test_research_runner.py::TestCandidatesEvent::test_each_round_streams_its_candidates_before_the_critique` — 같은 순서 단언
- `test_research_runner.py::TestCandidatesEvent::test_candidates_follow_the_order_they_were_linked` — `ValueError: not enough values to unpack (expected 1, got 0)`
- `test_research_runner.py::TestCandidatesEvent::test_candidates_carry_paper_briefs` — `assert [] == [{'subq_idx': …}]`
- `test_research_runner.py::TestCandidatesEvent::test_round_without_new_links_streams_an_empty_list` — `assert [] == [{'subq_idx': …, 'papers': []}]`
- `test_research_runner.py::TestCandidatesEvent::test_excluded_or_budget_blocked_papers_are_not_candidates` — `assert [] == [['A', 'B'], ['C']]`
- `test_research_runner.py::TestCandidatesEvent::test_candidates_are_streamed_whatever_the_switches[0]`·`[1]` — `assert 0 == 1`
- `test_research_tasks.py::TestLiveProgress::test_candidates_are_streamed_but_not_saved` — 이벤트 순서 단언(`candidates` 가 없다)

`TestCandidatesEvent::test_candidates_are_not_kept_in_the_round_history` 는 이미 통과한다(지키는 테스트).

- [ ] **Step 3: 구현한다**

`app/services/research/runner.py` — `explore_subquestion` 의 counters 바로 뒤. old:

```python
        subq.evidence_ids = _rank_order(subq.evidence_ids + fresh, relevance, leaders)
        await emit("counters", research_stats(state))
```

new:

```python
        subq.evidence_ids = _rank_order(subq.evidence_ids + fresh, relevance, leaders)
        await emit("counters", research_stats(state))
        # 이번 검색이 이 하위질문에 이은 후보(이은 순서) — 자기점검이 판정하기 전에 화면이 '검토 중'으로 세운다(06d).
        # 화면 이벤트일 뿐이라 회차 기록(rounds)·스냅숏·단계 result 에 넣지 않는다 — 지나간 '검토 중'은 critique 의
        # 채택·뺌으로 이미 보인다. 검색·판정을 바꾸지 않으므로 스위치(broaden·query_context)와 무관하게 늘 내고,
        # 이은 근거가 없어도 빈 목록으로 낸다(다음 회차 후보가 앞 더미를 갈음한다)
        await emit("candidates", {
            "subq_idx": subq.idx, "round": round_no,
            "papers": [_paper_brief(state.evidence[e]) for e in linked],
        })
```

그 뒤의 `# 원 질문은 늘 넘긴다 …` 주석과 `critique_fn` 호출은 그대로다. 워커의 `_round_emitter` 는 고치지 않는다 — 새 kind 도 `publish` 로 흘리고, `critique` 가 아니므로 저장하지 않는다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_runner.py tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `216 passed, 2 warnings` (runner 90 → 98 · tasks 117 → 118 — 고친 `test_counters_follow_each_search` 는 수를 늘리지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git diff --stat -- app/workers/research_tasks.py app/services/research/relay.py app/api/research.py`

Expected: 빈 출력 — 이 Task 는 `_round_emitter`·relay·SSE API 를 고치지 않는다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 파일. Task 앞 수 + 9 (C6 바로 뒤면 `5 failed, 2437 passed, 1 skipped, 2 warnings, 1 error` — 파트 C 끝, Task 0 기준선 + 110).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/services/research/runner.py app/tests/test_research_runner.py app/tests/test_research_tasks.py && git status --short && git commit -m "[Feat] round06c — 탐색 후보 목록 이벤트(candidates): 회차마다 자기점검 전에 이번 검색이 이은 후보의 서지를 낸다(06d '검토 중' 더미의 재료). 모양은 {subq_idx, round, papers: [_paper_brief…]}(이은 순서, 이은 근거가 없으면 빈 목록)이고 회차 기록·스냅숏·단계 result 에 넣지 않는다 — _round_emitter 가 흘리기만 하고 저장은 critique 에서만 한다. 스위치와 무관하게 늘 내므로 이벤트 전체 순서를 단언하던 기존 test_counters_follow_each_search 의 기대 순서에 candidates 를 넣는다"
```

---

---

## 파트 V — 판정 도구·화면 한 줄

덮는 spec: §12-7 '06c 판정(두 갈래)' 의 도구(`run_pair.py --param`·`--plan own`)·지표(일반 틀 비율 — 측면 낱말 사전과 원 질문 부분 문자열 제외, 근거 0편·insufficient 하위질문 수, 계획 시간 `elapsed_ms`, 합격 x/5 와 제외 판정의 관련 합계는 찍되 판정에 쓰지 않음)·대조군(별도 질문 파일)·판정 절차(README), §12-2 '낱말 맞추기' 의 score.py 복사본 + 공용 고정 예제, §12-2 '화면 한 줄'(PlanCard 선택 prop `questionUsed`·리듀서 `questionUsedFromSteps`·타입). 06c 정함 14·15(읽기만)·16·17·18·19(지표)·20·21·22.

| Task | 하는 일 | 선행 |
|---|---|---|
| V1 | `run_pair.py` — `--param0`·`--param`·`--plan own`, 대조군 `questions_control.json` | 없음(파트 C 와 병렬) |
| V2 | `score.py` — 계획 지표·`--plan-only`·`contains` 복사본, README '06c 재판정' 절차 | Task C1(공용 고정 예제·`terms.contains`)·Task V1(같은 테스트 파일·README 가 run_pair 새 인자를 적는다) |
| V3 | 화면 한 줄 — `questionUsedFromSteps`·`understoodLine`·PlanCard `questionUsed`·`StepResult` 선택 칸 셋 | 없음(백엔드 코드에 기대지 않는다 — 모양만 따른다: 계획 머리 「다른 줄과의 경계·머지 문」의 06d plan step 결과 행·정함 5·6(Task C4)) |

파트 공통:
- 작업 위치는 `C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c`(브랜치 `feat/round06c-query-broadening`)다. 줄 번호는 dev `da80f23`(= `.worktrees/round06-spec` 의 코드) 기준이고, 파트 C 는 이 파트의 파일(`scripts/research_eval/*`·`app/tests/test_research_eval.py`·`frontend/types/research.ts`·`frontend/utils/researchEvents.ts`·`frontend/components/research/PlanCard.vue`·`frontend/tests/unit/researchEvents.test.ts`)을 고치지 않는다 — 그래서 아래 old 문자열은 `da80f23` 의 글자 그대로다(Task V2 는 Task V1 뒤 글자).
- 고칠 파일은 모두 CRLF 다 — **Edit 도구로** 고친다(heredoc·sed 금지). 새 파일(`questions_control.json`)은 Write 로 만들고 줄바꿈은 커밋 때 git 이 맞춘다.
- `app/tests/test_research_eval.py` 의 `da80f23` 실측은 `33 passed` 다(2026-10-08, 같은 커밋의 파일 사본). 파트 C 는 이 파일을 고치지 않으므로 Task V1 앞도 33 이다.
- 이 파트의 기대 출력은 `da80f23`(= round06-spec `65e257b` 의 코드) 사본에 아래 글을 그대로 적용해 실측했다 — Task V2 의 `terms.py`·`term_checks.json`·`test_research_terms.py` 는 이 계획 파트 C 의 Task C1 글을 그대로 넣어 쟀다(`test_research_terms.py` 35 + `test_research_eval.py` 47 = `82 passed`). 실제 실행에서는 Task C1 이 커밋한 파일을 쓴다(Task V2 Step 0 이 `contains` 본문이 같은지 견준다).
- Git Bash 에서 pytest 출력의 한글이 깨지면 명령 앞에 `PYTHONIOENCODING=utf-8` 을 붙인다(기대 출력의 판정에는 영향 없음).

---

### Task V1: `run_pair.py` — `--param0`·`--param`·`--plan own`·대조군 질문 파일

**왜:** spec §12-7 — 06c 판정은 critic 기준이 아니라 잡 파라미터 `broaden`·`query_context` 를 가른다. 그런데 `run_pair.py` 는 갈래 파라미터를 `{"critic_scope": n}` 으로 박아 두었고(`create_job` 36-40행), 갈래 1 을 늘 갈래 0 의 계획으로 승인한다(`run_question` 98-103행) — 넓히기는 계획을 바꾸는 스위치라 그대로 재면 효과가 0 이다. 갈래마다 잡 파라미터를 JSON 객체로 통째로 받고(`--param0`·`--param`, 정함 16), 갈래 1 도 제 계획으로 승인하는 모드(`--plan own`)를 더한다. 기본값만 주면 동작이 지금 그대로다(06a·06b 판정과 같은 도구 — 출력 머리에 갈래 파라미터·계획 모드 한 줄만 는다). 대조군(논문 버튼 꼴의 풍부한 질문)은 고정 5문항에 섞지 않고 별도 파일로 둔다(정함 18 — 분모가 바뀐다).

**Files:**
- Modify: `scripts/research_eval/run_pair.py` (`da80f23` 기준 독스트링 1-17행, 상수 26-29행, `create_job` 36-40행, `run_question` 91-106행, `main` 126-170행)
- Create: `scripts/research_eval/questions_control.json`
- Test: `app/tests/test_research_eval.py` (questions 절 끝 64행 뒤에 하나, run_pair 절 끝 553행 뒤 — `# ── mark_example.py` 머리 앞에 넷(매개변수 펼치면 여섯))

**알아 둘 것:**
- **이름을 바꾸지 않는 것:** `QUESTIONS`·`get_job`·`load_questions` 는 `score.py`·`make_labels.py` 가 import 한다(`score.py:31`, `make_labels.py` 의 `from run_pair import get_job`). `approve(client, api, job_id, plan=None)`·`wait_for`·`load_pairs`·`save_pairs` 도 그대로다.
- **기본값 = 지금 동작:** `DEFAULT_PARAMS0 = {"critic_scope": 0}`·`DEFAULT_PARAMS1 = {"critic_scope": 1}`·`--plan shared`. 기존 `test_run_question_approves_arm1_with_arm0_plan_and_no_browser_id`(params `[{"critic_scope": 0}, {"critic_scope": 1}]`·갈래 1 은 갈래 0 의 계획)는 **고치지 않고** 통과해야 한다. `run_question` 은 받은 dict 의 사본을 보낸다(호출한 쪽의 dict 를 고치지 않는다).
- **잘못 쓴 JSON:** `parse_params` 는 JSON 객체만 받는다 — 해석 실패(`json.JSONDecodeError`)와 객체가 아닌 값(`[1]`·`"x"`) 모두 `ValueError("잡 파라미터는 JSON 객체여야 한다: '…'")`. `main` 은 인자를 읽은 **바로 뒤**(출력 폴더 만들기·질문 파일 읽기·HTTP 보다 먼저) 둘을 해석하고, 실패하면 그 문구를 찍고 `2` 를 돌려준다 — 잘못 쓴 파라미터로 잡 10개를 만들기 시작하지 않는다. 키·값 범위(`broaden` 0~1 등)는 보지 않는다 — 잡을 만들 때 API 의 `merge_params` 가 422 로 막고, 그 질문은 `실패: HTTP 422 …` 로 찍힌다(지금 경로).
- **실행 기록 머리 한 줄(정함 16 의 옵션에 더한 출력):** `main` 이 질문을 돌리기 전에 `갈래 0 {params0 JSON} · 갈래 1 {params1 JSON} · 계획 {shared|own}` 을 한 번 찍는다 — 완료노트에 어느 파라미터로 돌렸는지 남기는 재료다. `json.dumps(…, ensure_ascii=False)` 라 `{"critic_scope": 0, "broaden": 1, "query_context": 1}` 꼴이다.
- **기본값을 켠 뒤(정함 16·Task Z7):** `DEFAULT_PARAMS0` 는 서버 기본값을 따라간다 — 06c 기본값 커밋 뒤 재판정은 늘 `--param0` 에 두 칸을 적는다(README '06c 재판정' 8, Task V2).
- **대조군 질문 파일(정함 18):** `frontend/utils/paperResearch.ts:17-27` `paperResearchQuestion(title, keywords)` 가 만드는 글 그대로 — `「{제목}」에서 출발해, {키워드 셋 ·로 이음} 관련 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?`. 제목은 라벨 파일에 있는 소장 논문 둘(`labels/elderly.csv` 5행 `KCI_FI001933966` 「노인의 규칙적 운동이 우울에 미치는 효과 분석과 이론 검증」, `labels/library.csv` 7행 `KCI_FI001023392` 「공공도서관 서비스 고객만족도 평가체계에 관한 연구」), 키워드는 제목의 핵심어 셋이다. 키는 `ctl_` 로 시작해 고정 5문항 키와 겹치지 않는다(pairs·라벨 파일 이름 규칙 `[a-z][a-z0-9_]*`).
- **셸 따옴표:** 서버(bash)·개발 PC(Git Bash) 모두 JSON 을 작은따옴표로 감싼다 — `--param '{"critic_scope": 0, "broaden": 1, "query_context": 1}'`.
- 테스트는 기존 `_fake_research_api`(409-442행, 절 머리 `# ── run_pair.py` 는 406행 — 잡을 만들 때 받은 `params` 와 승인 본문 `approved_with` 를 기록한다)를 그대로 쓴다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_eval.py` — questions 절 끝(64행 뒤). old:

```python
    # 운영 잡 2a56f8b6 의 질문 — 옛 잡과 견주지 않고 같은 질문을 두 갈래로 다시 돌린다(spec §8)
    assert items[0] == {"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"}


# ── score.py ────────────────────────────────────────────────────────────
```

new:

```python
    # 운영 잡 2a56f8b6 의 질문 — 옛 잡과 견주지 않고 같은 질문을 두 갈래로 다시 돌린다(spec §8)
    assert items[0] == {"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"}


def test_control_questions_are_rich_and_kept_apart_from_the_fixed_five():
    """06c 대조군 — 논문 상세 [이 논문으로 딥리서치] 꼴(utils/paperResearch.ts paperResearchQuestion)의 풍부한 질문.
    넓히기가 이미 구체적인 질문을 그대로 두는지 본다. 고정 5문항 파일에 섞으면 합격 질문의 분모가 바뀌므로
    따로 두고 키도 겹치지 않는다(spec §12-7)."""
    from run_pair import CONTROL_QUESTIONS, QUESTIONS, load_questions

    items = load_questions(CONTROL_QUESTIONS)
    keys = [q["key"] for q in items]
    assert 1 <= len(items) <= 2 and len(set(keys)) == len(items)
    assert not set(keys) & {q["key"] for q in load_questions(QUESTIONS)}
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", k) for k in keys)    # pairs 키·라벨 파일 이름과 같은 규칙
    assert all(set(q) == {"key", "question"} and 2 <= len(q["question"]) <= 500 for q in items)
    for q in items:
        text = q["question"]
        assert text.startswith("「") and "」에서 출발해," in text and text.endswith("무엇인가?")


# ── score.py ────────────────────────────────────────────────────────────
```

② 같은 파일 — run_pair 절 끝(`test_run_pair_main_reports_a_failed_question_and_keeps_the_others` 뒤, mark_example 머리 앞). old:

```python
    text = capsys.readouterr().out
    text.encode("cp949")
    assert "--only computing" in text


# ── mark_example.py ─────────────────────────────────────────────────────
```

new:

```python
    text = capsys.readouterr().out
    text.encode("cp949")
    assert "--only computing" in text


P0_06C = {"critic_scope": 0, "broaden": 0, "query_context": 0}
P1_06C = {"critic_scope": 0, "broaden": 1, "query_context": 1}


def test_run_question_gives_each_arm_the_params_it_was_given():
    """06c 판정은 critic 이 아니라 넓히기·검색어 합성 스위치를 가른다 — 갈래마다 잡 파라미터를 통째로 준다.
    계획 모드는 기본(shared) 그대로 — 갈래 1 은 갈래 0 의 계획으로 승인한다."""
    from run_pair import run_question

    state, handler = _fake_research_api()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        pair = run_question(client, API, "컴퓨팅 자원에 대한 연구가 궁금해", poll=0, timeout=60.0,
                            params0=P0_06C, params1=P1_06C, sleep=lambda _: None)

    assert pair == {"0": "job-1", "1": "job-2"}
    jobs = state["jobs"]
    assert [j["params"] for j in jobs.values()] == [P0_06C, P1_06C]
    assert jobs["job-1"]["approved_with"] is None
    assert jobs["job-2"]["approved_with"] == {"plan": ["job-1 계획 1", "job-1 계획 2"]}


def test_run_question_with_own_plan_approves_arm1_with_its_own_plan():
    """넓히기(broaden)는 계획을 바꾼다 — 갈래 1 을 갈래 0 의 계획으로 승인하면 효과가 0 이다(spec §12-7 --plan own)."""
    from run_pair import run_question

    state, handler = _fake_research_api()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        pair = run_question(client, API, "컴퓨팅 자원에 대한 연구가 궁금해", poll=0, timeout=60.0,
                            plan="own", sleep=lambda _: None)

    assert pair == {"0": "job-1", "1": "job-2"}
    jobs = state["jobs"]
    assert [j["params"] for j in jobs.values()] == [{"critic_scope": 0}, {"critic_scope": 1}]
    # 두 갈래 모두 본문 없이 — 저마다 제가 세운 계획으로 돈다
    assert jobs["job-1"]["approved_with"] is None and jobs["job-2"]["approved_with"] is None
    assert [j["status"] for j in jobs.values()] == ["completed", "completed"]


def test_run_pair_main_passes_params_and_plan_mode(tmp_path, capsys):
    from run_pair import main

    questions = tmp_path / "questions.json"
    questions.write_text(json.dumps([{"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"}],
                                    ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "pairs.json"
    state, handler = _fake_research_api()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--out", str(out), "--questions", str(questions), "--poll", "0",
                   "--param0", json.dumps(P0_06C), "--param", json.dumps(P1_06C), "--plan", "own"],
                  client=client)

    assert rc == 0
    jobs = state["jobs"]
    assert [j["params"] for j in jobs.values()] == [P0_06C, P1_06C]
    assert jobs["job-2"]["approved_with"] is None
    assert json.loads(out.read_text(encoding="utf-8")) == {"computing": {"0": "job-1", "1": "job-2"}}
    text = capsys.readouterr().out
    text.encode("cp949")
    # 어느 파라미터·계획 모드로 돌렸는지 실행 기록 머리에 남는다
    assert (f"갈래 0 {json.dumps(P0_06C)} · 갈래 1 {json.dumps(P1_06C)} · 계획 own") in text


@pytest.mark.parametrize("flag, value", [("--param", "[1]"), ("--param0", "{"), ("--param", '"x"')])
def test_run_pair_refuses_params_that_are_not_a_json_object(tmp_path, capsys, flag, value):
    """잘못 쓴 파라미터로 잡 10개를 만들기 시작하지 않는다 — HTTP·출력 폴더보다 먼저 본다."""
    from run_pair import main

    state, handler = _fake_research_api()
    out = tmp_path / "새 폴더" / "pairs.json"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--out", str(out), flag, value], client=client)

    assert rc == 2
    text = capsys.readouterr().out
    text.encode("cp949")
    assert f"잡 파라미터는 JSON 객체여야 한다: {value!r}" in text
    assert state["requests"] == [] and not out.parent.exists()


# ── mark_example.py ─────────────────────────────────────────────────────
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`

Expected: `7 failed, 33 passed` —
- `test_control_questions_are_rich_and_kept_apart_from_the_fixed_five` — `ImportError: cannot import name 'CONTROL_QUESTIONS' from 'run_pair'`
- `test_run_question_gives_each_arm_the_params_it_was_given` — `TypeError: run_question() got an unexpected keyword argument 'params0'`
- `test_run_question_with_own_plan_approves_arm1_with_its_own_plan` — `TypeError: run_question() got an unexpected keyword argument 'plan'`
- `test_run_pair_main_passes_params_and_plan_mode`·`test_run_pair_refuses_params_that_are_not_a_json_object[--param-[1]]`·`[--param0-{]`·`[--param-"x"]` — `SystemExit: 2`(argparse 가 `--param0`·`--param`·`--plan` 을 모른다)

기존 33개(기존 run_pair 테스트 다섯 포함)는 통과한다.

- [ ] **Step 3: 구현한다**

① `scripts/research_eval/run_pair.py` 독스트링 머리. old:

```python
r"""run_pair.py — critic 기준 스위치 두 갈래 실행 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

고정 질문(questions.json)마다 딥리서치 잡 두 개를 만든다.
  갈래 0 — params {"critic_scope": 0}(지금 기준). 계획이 나오면 그 계획 그대로 승인한다.
  갈래 1 — params {"critic_scope": 1}(원 질문 기준). 같은 질문으로 만들고 승인 본문 plan 에 갈래 0 의
           계획을 넘긴다 — 같은 하위질문으로 돌려 두 갈래의 차이가 critic 하나뿐이게 한다.
두 잡 모두
```

new:

```python
r"""run_pair.py — 잡 파라미터 두 갈래 실행 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

고정 질문(questions.json)마다 딥리서치 잡 두 개를 만든다.
  갈래 0 — params --param0(기본 {"critic_scope": 0} — 지금 기준). 계획이 나오면 그 계획 그대로 승인한다.
  갈래 1 — params --param(기본 {"critic_scope": 1} — 원 질문 기준). 같은 질문으로 만든다.
           --plan shared(기본)면 승인 본문 plan 에 갈래 0 의 계획을 넘긴다 — 같은 하위질문으로 돌려 두 갈래의 차이가
           파라미터(critic 기준 등)뿐이게 한다. --plan own 이면 갈래 1 도 제가 세운 계획 그대로 승인한다 — 계획을
           바꾸는 스위치(06c broaden)는 shared 로 재면 효과가 0 이다.
--param0·--param 은 JSON 객체 하나이고 잡 만들기 본문의 params 에 그대로 실린다(검증은 API 의 merge_params). 기본값만
주면 06a·06b 판정과 같은 동작이다. 질문 파일은 --questions 로 바꾼다 — 대조군 questions_control.json 은 고정 5문항에
섞지 않는다(합격 질문의 분모가 바뀐다).
두 잡 모두
```

② 같은 파일 독스트링 끝(실행 예). old:

```python
  docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
    --api http://localhost:8000/api --out /app/data/research_eval/pairs.json
"""
```

new:

```python
  docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
    --api http://localhost:8000/api --out /app/data/research_eval/pairs.json
06c 재판정(README '06c 재판정') — 두 갈래 모두 critic_scope 0, 갈래마다 제 계획:
  docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
    --api http://localhost:8000/api --out /app/data/research_eval/pairs_06c.json --plan own \
    --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' \
    --param '{"critic_scope": 0, "broaden": 1, "query_context": 1}'
"""
```

③ 같은 파일 상수·`parse_params`·`create_job`. old:

```python
QUESTIONS = HERE / "questions.json"
TERMINAL = ("completed", "failed", "canceled")
TRANSIENT_RETRIES = 3


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def create_job(client: httpx.Client, api: str, question: str, critic_scope: int) -> str:
    res = client.post(f"{api}/research",
                      json={"question": question, "params": {"critic_scope": critic_scope}})
    res.raise_for_status()
    return res.json()["job_id"]
```

new:

```python
QUESTIONS = HERE / "questions.json"
CONTROL_QUESTIONS = HERE / "questions_control.json"
TERMINAL = ("completed", "failed", "canceled")
TRANSIENT_RETRIES = 3
DEFAULT_PARAMS0 = {"critic_scope": 0}
DEFAULT_PARAMS1 = {"critic_scope": 1}
PLAN_MODES = ("shared", "own")


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_params(text: str) -> dict:
    """--param0·--param 의 값. JSON 객체만 받는다 — 키·값 범위는 잡을 만들 때 API(merge_params)가 본다."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"잡 파라미터는 JSON 객체여야 한다: {text!r}") from e
    if not isinstance(value, dict):
        raise ValueError(f"잡 파라미터는 JSON 객체여야 한다: {text!r}")
    return value


def create_job(client: httpx.Client, api: str, question: str, params: dict) -> str:
    res = client.post(f"{api}/research", json={"question": question, "params": params})
    res.raise_for_status()
    return res.json()["job_id"]
```

④ 같은 파일 `run_question`. old:

```python
def run_question(client: httpx.Client, api: str, question: str, *, poll: float, timeout: float,
                 sleep=time.sleep, clock=time.monotonic) -> dict[str, str]:
    """한 질문의 두 갈래를 만들어 승인하고 둘 다 completed 가 될 때까지 기다린다."""
    wait = {"poll": poll, "timeout": timeout, "sleep": sleep, "clock": clock}
    arm0 = create_job(client, api, question, 0)
    # 만들자마자 찍는다 — 이 뒤에 실패해도 어느 잡이 남았는지 안다
    print(f"  갈래 0 {arm0}", flush=True)
    plan = wait_for(client, api, arm0, "awaiting_approval", **wait)["plan"]
    approve(client, api, arm0)
    arm1 = create_job(client, api, question, 1)
    print(f"  갈래 1 {arm1}", flush=True)
    wait_for(client, api, arm1, "awaiting_approval", **wait)
    approve(client, api, arm1, plan)
    for job_id in (arm0, arm1):
```

new:

```python
def run_question(client: httpx.Client, api: str, question: str, *, poll: float, timeout: float,
                 params0: dict | None = None, params1: dict | None = None, plan: str = "shared",
                 sleep=time.sleep, clock=time.monotonic) -> dict[str, str]:
    """한 질문의 두 갈래를 만들어 승인하고 둘 다 completed 가 될 때까지 기다린다.

    params0·params1 이 None 이면 DEFAULT_PARAMS0·DEFAULT_PARAMS1. plan 이 "own" 이면 갈래 1 도 본문 없이(제 계획으로)
    승인한다 — "shared" 면 갈래 0 의 계획을 넘긴다.
    """
    wait = {"poll": poll, "timeout": timeout, "sleep": sleep, "clock": clock}
    arm0 = create_job(client, api, question, dict(DEFAULT_PARAMS0 if params0 is None else params0))
    # 만들자마자 찍는다 — 이 뒤에 실패해도 어느 잡이 남았는지 안다
    print(f"  갈래 0 {arm0}", flush=True)
    plan0 = wait_for(client, api, arm0, "awaiting_approval", **wait)["plan"]
    approve(client, api, arm0)
    arm1 = create_job(client, api, question, dict(DEFAULT_PARAMS1 if params1 is None else params1))
    print(f"  갈래 1 {arm1}", flush=True)
    wait_for(client, api, arm1, "awaiting_approval", **wait)
    approve(client, api, arm1, None if plan == "own" else plan0)
    for job_id in (arm0, arm1):
```

⑤ 같은 파일 `main` 의 인자. old:

```python
    ap = argparse.ArgumentParser(description="critic 기준 스위치 두 갈래 실행 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--out", required=True, type=Path, help="{질문키: {\"0\": 잡 id, \"1\": 잡 id}} 를 덧쓸 JSON")
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--only", default="", help="이 질문키만(쉼표로 이음). 실패한 질문을 다시 돌릴 때")
    ap.add_argument("--poll", type=float, default=5.0, help="상태 조회 간격(초)")
    ap.add_argument("--timeout", type=float, default=3600.0, help="잡 하나가 한 상태에 이르기까지 기다릴 초")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
```

new:

```python
    ap = argparse.ArgumentParser(description="잡 파라미터 두 갈래 실행 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--out", required=True, type=Path, help="{질문키: {\"0\": 잡 id, \"1\": 잡 id}} 를 덧쓸 JSON")
    ap.add_argument("--questions", type=Path, default=QUESTIONS,
                    help=f"질문 파일. 대조군은 {CONTROL_QUESTIONS.name}")
    ap.add_argument("--only", default="", help="이 질문키만(쉼표로 이음). 실패한 질문을 다시 돌릴 때")
    ap.add_argument("--poll", type=float, default=5.0, help="상태 조회 간격(초)")
    ap.add_argument("--timeout", type=float, default=3600.0, help="잡 하나가 한 상태에 이르기까지 기다릴 초")
    ap.add_argument("--param0", default=json.dumps(DEFAULT_PARAMS0), help="갈래 0 잡 파라미터(JSON 객체)")
    ap.add_argument("--param", default=json.dumps(DEFAULT_PARAMS1), help="갈래 1 잡 파라미터(JSON 객체)")
    ap.add_argument("--plan", choices=PLAN_MODES, default="shared",
                    help="shared = 갈래 1 을 갈래 0 의 계획으로 승인, own = 갈래마다 제 계획으로 승인")
    args = ap.parse_args(argv)

    # 잘못 쓴 파라미터로 잡을 만들기 시작하지 않게 — HTTP·파일 쓰기보다 먼저 본다
    try:
        params0, params1 = parse_params(args.param0), parse_params(args.param)
    except ValueError as e:
        print(e)
        return 2
    api = args.api.rstrip("/")
```

⑥ 같은 파일 `main` 의 질문 루프 앞·`run_question` 호출. old:

```python
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    failed: list[str] = []
    try:
        for q in questions:
            print(f"[{q['key']}] {q['question']}", flush=True)
            try:
                pair = run_question(client, api, q["question"], poll=args.poll, timeout=args.timeout)
```

new:

```python
    # 실행 기록(완료노트)에 어느 파라미터로 돌렸는지 남긴다
    print(f"갈래 0 {json.dumps(params0, ensure_ascii=False)} · 갈래 1 {json.dumps(params1, ensure_ascii=False)}"
          f" · 계획 {args.plan}", flush=True)
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    failed: list[str] = []
    try:
        for q in questions:
            print(f"[{q['key']}] {q['question']}", flush=True)
            try:
                pair = run_question(client, api, q["question"], poll=args.poll, timeout=args.timeout,
                                    params0=params0, params1=params1, plan=args.plan)
```

⑦ Create `scripts/research_eval/questions_control.json`(Write 도구):

```json
[
  {"key": "ctl_elderly", "question": "「노인의 규칙적 운동이 우울에 미치는 효과 분석과 이론 검증」에서 출발해, 노인·규칙적 운동·우울 관련 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?"},
  {"key": "ctl_library", "question": "「공공도서관 서비스 고객만족도 평가체계에 관한 연구」에서 출발해, 공공도서관·고객만족도·평가체계 관련 선행 연구는 어떻게 전개되어 왔고 주요 쟁점과 남은 과제는 무엇인가?"}
]
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`

Expected: `40 passed` (33 + 7 — 기존 `test_run_question_approves_arm1_with_arm0_plan_and_no_browser_id` 는 고치지 않고 통과)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 Task 0 기준선과 같은 파일(`test_build_manifest.py` 2·`test_loaders.py` 3, 오류 `test_book_chat.py` 수집). passed = Task V1 앞 수 + 7.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/scripts/research_eval && PYTHONIOENCODING=utf-8 python run_pair.py --api http://127.0.0.1:9/api --out C:/Users/LANDSOFT/AppData/Local/Temp/v1_check.json --param '[1]'; echo "rc=$?"`

Expected: `잡 파라미터는 JSON 객체여야 한다: '[1]'` 한 줄과 `rc=2` — 아무 주소에도 요청하지 않고, `v1_check.json` 도 만들지 않는다(포트 9 는 닿지 않는 주소 — 요청을 했다면 연결 오류가 찍힌다). `PYTHONIOENCODING=utf-8` 이 없으면 Git Bash 에서 표준 출력이 cp949 로 나가 한글이 깨져 기대 출력과 글자로 견줄 수 없다(`rc=2` 는 같다).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add scripts/research_eval/run_pair.py && git add scripts/research_eval/questions_control.json && git add app/tests/test_research_eval.py && git status --short && git commit -m "[Feat] round06c — run_pair 에 갈래별 잡 파라미터(--param0·--param)와 갈래마다 제 계획으로 승인(--plan own), 대조군 질문 파일을 더한다: 박혀 있던 critic_scope 대신 갈래마다 JSON 객체를 통째로 주고(기본 {critic_scope 0}·{critic_scope 1}·shared 라 06a·06b 판정과 같은 동작), JSON 객체가 아니면 잡을 만들기 전에 종료 코드 2 로 멈춘다. 넓히기(broaden)는 계획을 바꾸므로 갈래 1 을 갈래 0 의 계획으로 승인하면 효과가 0 이라 --plan own 을 둔다. 시작할 때 갈래 파라미터·계획 모드를 한 줄 찍는다. questions_control.json 은 논문 상세 [이 논문으로 딥리서치] 꼴 질문 2개(소장 논문 KCI_FI001933966·KCI_FI001023392 의 제목)로, 합격 질문의 분모가 바뀌지 않게 고정 5문항에 섞지 않는다(spec §12-7)"
```

---

### Task V2: `score.py` 계획 지표·`--plan-only`·`contains` 복사본 + README 06c 재판정 절차

**왜:** spec §12-7 — 06c 판정의 지표는 보고서 정밀도·관련 편수(기존 합계 줄) 말고도 ① 일반 틀 비율(측면 낱말 사전과 맞는 하위질문 — 원 질문에 이미 든 측면 낱말은 세지 않는다) ② 근거 0편·insufficient 하위질문 수 ③ 계획 시간(plan step 결과의 `elapsed_ms` — 정함 5, Task C4 가 남긴다)이다. 지금 `score.py` 는 이 셋을 세지 못한다 — "코드가 센다". 넓힌 질문(`question_used`)은 숫자는 아니지만 대조군 판단('이미 구체적인 질문을 그대로 두는가')과 판정 기록에 필요해 갈래마다 한 줄로 찍는다. 대조군은 라벨이 없으므로 라벨 없이 계획 지표만 찍는 `--plan-only`(정함 17)가 필요하다. 일반 틀 비율의 '들어 있음' 은 06c 의 낱말 맞추기 규칙(`terms.contains`)과 같아야 하는데 `score.py` 는 서버의 `/app/data/research_eval/` 에서 app 없이 HTTP 만으로 돈다 — 복사본을 두고 공용 고정 예제로 묶는다(§12-2, 정함 14·15). README 에는 06c 판정 9걸음(Task Z6~Z8 과 같은 순서)을 적는다.

**Files:**
- Modify: `scripts/research_eval/score.py` (`da80f23` 기준 독스트링 1행·13-22행, import 23-27행, 상수 38-39행, `format_totals` 끝 170행 뒤, `main` 173-242행)
- Modify: `scripts/research_eval/README.md` (1·3행, 표 9-12행, 끝 99행 뒤에 새 절 `## 06c 재판정 (넓히기·검색어 합성)`)
- Test: `app/tests/test_research_eval.py` (import 6-11행에 `io`, score 절 끝 — 253-288행 `test_score_prints_report_precision_per_arm_and_totals_without_changing_the_verdict` 뒤, `# ── make_labels.py` 머리 앞에 일곱)

**알아 둘 것:**
- **기존 출력 글자는 한 자도 바꾸지 않는다(Task Z6 Step 2 가 06b 채점 출력과 글자로 견준다):** `합격 질문:`·갈래 줄(`format_arm`)·`보고서 정밀도` 줄·합계 두 줄·`채점하지 못한 질문 …`·`라벨 칸이 빈 논문이 …`. 새 줄은 갈래마다 기존 두 줄(`format_arm`·`format_precision`) **뒤**에 둘(`  갈래 {arm}  넓힌 질문: …`·`  갈래 {arm}  계획 지표  일반 틀 g/n · 근거 0편 z · insufficient i · 계획 s`), 합계는 기존 합계 두 줄 **뒤**에 한 줄(`계획 지표 합계(채점한 k개 질문): 갈래 0 … · 갈래 1 …`). 기존 테스트는 부분 문자열로 보므로 그대로 통과한다 — 기존 테스트의 대역 응답(`{"job_id", "status", "report"}` 만)에도 새 줄이 `(기록 없음)`·`일반 틀 0/n`·`계획 -` 로 찍힐 뿐 깨지지 않는다.
- **합격 판정은 그대로다:** `passes`·`verdict`·분모(고정 질문 수)를 고치지 않는다. 계획 지표는 판정 함수에 들지 않는다(§12-7 '합격 x/5 는 함께 찍되 판정에 쓰지 않는다').
- **잡을 읽는 자리:** 지금은 `reports = {arm: get_job(…).get("report") …}`(212행)로 보고서만 남긴다. 계획 지표는 잡의 `question`·`plan`·`steps` 를 읽으므로 `jobs = {arm: get_job(client, api, arms[arm]) for arm in ARMS}` 로 잡을 남기고 `reports` 는 그 잡에서 꺼낸다 — GET 횟수는 같다(질문마다 2회). 잡을 읽지 못한 질문의 문구(`잡을 읽지 못했다(…) - 건너뛴다`)도 그대로다.
- **`plan_metrics(job)`(Task V2 Step 3 ③):** `question` = `job["question"]`(없으면 `report["question"]`), 하위질문 = `job["plan"]`(승인된 계획 — `--plan shared` 의 갈래 1 은 갈래 0 의 계획이 실려 있다), 없으면 `report.trail[].subquestion`. `zero_evidence` = trail 중 `evidence_count == 0`, `insufficient` = trail 중 `verdict == "insufficient"`(`synthesizer.assemble_report` 352-353행의 칸). `question_used`·`plan_ms` = steps 중 `kind == "plan"` 이고 `seq` 가 가장 큰 행의 `result.question_used`·`result.elapsed_ms` — 06c 전 잡은 없어 `None`. GET 의 steps 모양은 `api/research.py:368-378` `_steps`(`seq`·`kind`·`subq_idx`·`title`·`detail`·`status`·`result`).
- **일반 틀(`generic_frames`):** `ASPECT_WORDS`(Task V2 Step 3 ②) 가운데 원 질문에 `contains` 인 낱말을 먼저 빼고, 남은 낱말 중 하나라도 `contains` 인 하위질문을 센다. csr 의 원 질문 '재무성과' 는 '성과' 를 품으므로 '성과' 를 세지 않는다(띄어 쓴 '재무 성과' 하위질문도 마찬가지). 대조군 질문은 '…남은 과제는 무엇인가?' 라 '과제' 를 세지 않는다. 비율은 합계 줄에서만 낸다(분모 = 채점한 질문의 하위질문 수 합).
- **넓힌 질문 줄:** `question_used` 가 `None` 이면 `(기록 없음)`(06c 전 잡 — `pairs_20261008_d18` 의 06b 참고값), NFKC·공백 정리 뒤 원 질문과 같으면 `(원 질문 그대로)`(넓히기를 껐거나 원문으로 물러난 잡 — Task V3 의 `questionUsedFromSteps` 와 같은 비교), 아니면 넓힌 문장 그대로.
- **계획 시간:** `elapsed_ms` 를 `1.2초`(소수 한 자리)로, 없으면 `-`. 합계는 값이 있는 질문의 중앙값(`statistics.median` — 짝수 개면 가운데 둘의 평균)을 `계획 p50` 으로. poll 방식은 쓰지 않는다(정함 5).
- **`--plan-only`(정함 17):** 라벨 폴더·라벨 파일을 읽지 않는다. 질문마다 `[{key}] {잡 0 의 question}` 머리 + 갈래마다 계획 두 줄, 끝에 `계획 지표 합계 …` 한 줄만. 보고서가 없는 갈래도 건너뛰지 않는다(계획 지표는 잡의 계획·단계로 센다). `합격 질문:`·갈래 판정 줄·보고서 정밀도·두 합계 줄·`채점하지 못한 질문 …` 요약은 찍지 않는다 — pairs 에 없는 질문(`[key] pairs 에 없다 - …`)과 잡을 읽지 못한 질문(`[key] 잡을 읽지 못했다(…) - 건너뛴다`)은 지금 문구로 질문 줄에 찍힌다.
- **`contains` 복사본(정함 14):** `score.py` 는 `contains` 와 그것이 부르는 `_normalize`(NFKC → casefold) 만 복사한다(`content_words` 는 쓰지 않는다). **본문은 Task C1 이 쓴 `app/services/research/terms.py` 의 `contains`·`_normalize` 와 글자까지 같아야 한다** — 공백 지운 부분 문자열이면 참, 아니면 word 의 낱말을 **공백 지운 text** 에서 앞에서부터 차례로 찾는다('다문화 가정 아동의 언어 발달' 에 '다문화가정 언어' 가 참). Step 0 에서 둘을 견준다. 테스트는 ① 공용 고정 예제 `frontend/tests/fixtures/term_checks.json` 의 `contains` 칸(Task C1 이 만든다 — 이 Task 는 읽기만 하고 고치지 않는다. 계획 머리 「파일 구조」의 `tests/fixtures/term_checks.json` 행도 Task C1 만 적는다) ② 예제 밖의 갈림 사례(공백을 건너 이어진 낱말·공백뿐인 word·빈 text 등)에서 원본 `services.research.terms.contains` 와 같은 답 — 둘을 본다. 예제가 판정하지 못하는 구현 차이(예: '낱말이 순서대로' 를 공백 있는 글에서 찾는지 공백 지운 글에서 찾는지)도 ② 가 잡는다. 고정 예제는 모듈 머리가 아니라 **테스트 함수 안에서** 읽는다 — Task C1 전에 이 파일의 다른 테스트가 수집 오류로 함께 죽지 않게.
- **cp949:** 새 줄의 고정 글자(`·`·`「」`·`초`)는 cp949 에 있다 — 테스트가 `out.encode("cp949")` 로 본다. 그런데 `넓힌 질문:` 줄은 LLM(gemma)이 쓴 `question_used` 를 그대로 찍는다 — `—`(U+2014)·`–`(U+2013)는 cp949 에 없어서, `PYTHONIOENCODING` 없이 돌린 Git Bash(표준 출력 cp949 — Task V1 Step 4)에서는 `print` 가 `UnicodeEncodeError` 로 멈추고 합계 줄이 나오지 않는다(같은 사본에서 재현했다). 그래서 `main` 의 첫 줄(argparse 앞)이 `sys.stdout.reconfigure(errors="replace")` 로 그런 글자만 `?` 로 찍고 채점을 잇는다. 서버 `docker exec` 경로는 UTF-8 이라 그대로 찍힌다. 테스트 `test_score_keeps_going_when_the_broadened_question_has_a_letter_cp949_lacks` 가 cp949 표준 출력(`io.TextIOWrapper(io.BytesIO(), encoding="cp949")`)에서 이것을 본다.
- **README 새 절**은 Task Z6~Z8 의 순서·명령(옵션 글자는 정함 16·17 과 Task V1·V2 의 인자 그대로)이다. 결과는 마무리가 그 절 끝에 적는다(D18 절 선례) — 이 Task 는 절차만 쓴다.
- 셋 다 CRLF 파일이다 — Edit 도구로.

- [ ] **Step 0: 선행 조건을 확인한다(Task C1·V1)**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git log --oneline -1 -- app/services/research/terms.py frontend/tests/fixtures/term_checks.json && git log --oneline -1 -- scripts/research_eval/questions_control.json`

Expected: 두 줄 — Task C1 커밋(`[Feat] round06c — 한국어 낱말 맞추기·검색어 합성 순수 함수(terms.py)와 공용 고정 예제 …`)과 Task V1 커밋(`[Feat] round06c — run_pair 에 갈래별 잡 파라미터 …`). 하나라도 빠지면 그 Task 를 먼저 한다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && PYTHONIOENCODING=utf-8 python -c "import inspect, json, pathlib; from services.research import terms; print(inspect.getsource(terms.contains)); print(sorted(json.loads(pathlib.Path('../frontend/tests/fixtures/term_checks.json').read_text(encoding='utf-8'))))"`

Expected: `contains` 의 본문과 `['contains', 'content_words']`. 본문을 아래 Step 3 ③ 의 `_normalize`·`contains`(Task C1 의 글을 옮긴 것 — `pieces = _normalize(word or "").split()`, `flat = "".join(_normalize(text or "").split())`, 공백 지운 부분 문자열이면 참, 아니면 `pieces` 를 `flat` 에서 앞에서부터 차례로 찾는다)와 줄마다 견준다. **다르면 Task C1 의 본문을 그대로 옮긴다**(docstring 만 아래 것을 쓰고, C1 의 `contains` 가 부르는 모듈 도우미가 `_normalize` 와 다르면 그것도 같은 글로 `score.py` 에 옮긴다 — Step 3 ④). Step 4 의 `test_contains_copy_matches_the_shared_fixture` 가 두 쪽을 견주므로 어긋나면 거기서 실패한다(예: 낱말을 공백 있는 글에서 찾는 복사본은 `('다문화 가정 아동의 언어 발달', '다문화가정 언어')` 에서 `assert False is True` 로 떨어진다 — 같은 사본에서 확인했다).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_eval.py` — score 절 끝(`test_score_prints_report_precision_per_arm_and_totals_without_changing_the_verdict` 뒤, make_labels 머리 앞). old:

```python
    # 판정은 그대로 — computing 갈래 0 은 뺀 X 가 '관련'(과잉 제외 100%), 갈래 1 은 한 절에 무관 2편
    assert "합격 질문: 갈래 0 1/2 · 갈래 1 1/2" in out


# ── make_labels.py ──────────────────────────────────────────────────────
```

new:

```python
    # 판정은 그대로 — computing 갈래 0 은 뺀 X 가 '관련'(과잉 제외 100%), 갈래 1 은 한 절에 무관 2편
    assert "합격 질문: 갈래 0 1/2 · 갈래 1 1/2" in out


TERM_CHECKS = Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "term_checks.json"


def test_contains_copy_matches_the_shared_fixture():
    """score.py 는 app 을 import 하지 않는다(서버의 /app/data/research_eval/ 에서 HTTP 만으로 돈다) — terms.contains 의
    복사본을 두고 06c test_research_terms.py 와 같은 공용 고정 예제로 묶는다. 예제 밖의 갈림(공백을 건너 이어진 낱말·
    공백뿐인 word 등)에서도 원본과 같은 답을 내는지 함께 본다."""
    from score import contains
    from services.research.terms import contains as original

    cases = json.loads(TERM_CHECKS.read_text(encoding="utf-8"))["contains"]
    assert cases                                   # 예제가 비면 복사본을 묶지 못한다
    for case in cases:
        assert contains(case["text"], case["word"]) is case["expected"], case["note"]
    probes = [
        ("다문화 가정 아동의 언어 발달", "다문화가정 언어"),
        ("공공도서관 다문화 서비스", "공공 도서관"),
        ("ＡＩ 윤리 교육", "AI 윤리"),
        ("Digital Library Use", "digital library"),
        ("노인 복지와 우울", "우울 노인"),
        ("노인의 우울", "   "),
        ("성과", "재무 성과"),
        ("", "성과"),
    ]
    for text, word in probes + [(c["text"], c["word"]) for c in cases]:
        assert contains(text, word) is original(text, word), (text, word)


def test_generic_frames_skip_aspect_words_inside_the_question():
    """일반 틀 = 측면 낱말 사전과 맞는 하위질문. 원 질문에 이미 든 측면 낱말은 세지 않는다(spec §12-7)."""
    from score import ASPECT_WORDS, generic_frames

    assert ASPECT_WORDS == ("개념", "정의", "방법", "기법", "적용 분야", "성과", "한계", "과제", "동향", "발전 방향")
    csr = "기업의 사회적 책임과 재무성과에 관한 연구가 궁금해"
    assert generic_frames(csr, [
        "기업의 사회적 책임 활동이 재무성과에 미치는 영향",    # '성과' 는 원 질문의 '재무성과' 안에 있다 — 세지 않는다
        "기업의 사회적 책임 측정 방법",                       # 방법
        "업종별 기업의 사회적 책임과 재무 성과의 관계",         # 띄어 쓴 '재무 성과' 도 원 질문의 말이다
    ]) == 1
    computing = "컴퓨팅 자원에 대한 연구가 궁금해"
    assert generic_frames(computing, [
        "컴퓨팅 자원의 정의 및 개념",                         # 06a 에서 무관이 몰린 절
        "컴퓨팅 자원 관리 기법",
        "컴퓨팅 자원 할당의 적용 분야와 성과",
        "클라우드 환경의 컴퓨팅 자원 스케줄링",
    ]) == 3
    assert generic_frames(computing, []) == 0


def _plan_job(question, plan, *, used=None, elapsed_ms=None, trail=(), sections=()):
    """GET /research/{id} 가운데 계획 지표가 읽는 키 — 질문·승인된 계획·계획 단계 result·보고서(trail·절).
    used 가 None 이면 06c 전 잡처럼 계획 단계 result 에 subquestions 만 둔다."""
    result = {"subquestions": list(plan)}
    if used is not None:
        result |= {"question_used": used, "terms": [], "elapsed_ms": elapsed_ms}
    return {
        "question": question, "status": "completed", "plan": list(plan),
        "steps": [{"seq": 0, "kind": "plan", "subq_idx": None, "title": "연구 계획 수립", "detail": None,
                   "status": "done", "result": result}],
        "report": {
            "question": question,
            "sections": [{"heading": h, "papers": [{"cnts_id": c} for c in ids]} for h, ids in sections],
            "evidence": {},
            "trail": [{"subquestion": s, "evidence_count": n, "verdict": v, "excluded_papers": []}
                      for s, n, v in trail],
        },
    }


def test_plan_metrics_read_the_plan_the_trail_and_the_last_plan_step():
    from score import format_plan, format_question_used, plan_metrics

    question = "컴퓨팅 자원에 대한 연구가 궁금해"
    broadened = "클라우드·그리드 환경의 컴퓨팅 자원 관리에 대한 연구가 궁금해"
    plan = ["컴퓨팅 자원의 정의", "클라우드 컴퓨팅 자원 할당", "그리드 컴퓨팅 자원 관리 기법"]
    job = _plan_job(question, plan, used=broadened, elapsed_ms=3400, trail=[
        (plan[0], 0, "insufficient"), (plan[1], 4, "sufficient"), (plan[2], 2, "insufficient")])
    # 재시도로 계획 단계가 둘 — seq 가 큰 행이 지금 계획이다. 앞 시도의 넓힌 질문은 읽지 않는다
    job["steps"] = [{"seq": 0, "kind": "plan", "subq_idx": None, "title": "연구 계획 수립", "detail": None,
                     "status": "failed", "result": {"question_used": "앞 시도의 질문", "terms": []}},
                    {**job["steps"][0], "seq": 1},
                    {"seq": 2, "kind": "search", "subq_idx": 0, "title": plan[0], "detail": None,
                     "status": "done", "result": {}}]
    job["report"]["question"] = "보고서 머리 질문은 job.question 이 있으면 쓰지 않는다"

    m = plan_metrics(job)

    assert m == {"question": question, "question_used": broadened, "subquestions": 3, "generic": 2,
                 "zero_evidence": 1, "insufficient": 2, "plan_ms": 3400}
    assert format_question_used("1", m) == f"  갈래 1  넓힌 질문: {broadened}"
    assert format_plan("1", m) == "  갈래 1  계획 지표  일반 틀 2/3 · 근거 0편 1 · insufficient 2 · 계획 3.4초"
    # 넓히기를 껐거나 원문으로 물러난 잡 — 공백 차이만 있어도 원 질문 그대로다
    same = plan_metrics(_plan_job(question, plan, used=" 컴퓨팅  자원에 대한 연구가 궁금해", elapsed_ms=700))
    assert format_question_used("0", same) == "  갈래 0  넓힌 질문: (원 질문 그대로)"


def test_plan_metrics_of_a_job_before_06c_have_no_question_used_or_time():
    """06b 잡(pairs_20261008_d18)은 계획 단계 result 에 subquestions 만 있다 — 넓힌 질문·계획 시간은 '기록 없음'·'-' 이고
    일반 틀·근거 0편·insufficient 는 그대로 센다(spec §12-7 '계획에서 06b 잡으로 센다')."""
    from score import format_plan, format_question_used, plan_metrics

    question = "공공도서관 서비스 품질 평가 연구가 궁금해"
    plan = ["공공도서관 서비스 품질 평가의 개념과 정의", "공공도서관 서비스 품질 평가 방법",
            "공공도서관 이용자 만족도와 서비스 품질", "공공도서관 서비스 품질 평가의 한계와 과제"]
    trail = [(plan[0], 3, "sufficient"), (plan[1], 0, "insufficient"), (plan[2], 5, "sufficient"),
             (plan[3], 2, "sufficient")]

    m = plan_metrics(_plan_job(question, plan, trail=trail))

    assert m["question_used"] is None and m["plan_ms"] is None
    assert format_question_used("0", m) == "  갈래 0  넓힌 질문: (기록 없음)"
    assert format_plan("0", m) == "  갈래 0  계획 지표  일반 틀 3/4 · 근거 0편 1 · insufficient 1 · 계획 -"
    # 질문·계획·단계가 없는 잡(보고서만)은 보고서의 질문과 trail 의 하위질문으로 센다
    bare = plan_metrics({"report": _plan_job(question, plan, trail=trail)["report"]})
    assert (bare["question"], bare["subquestions"], bare["generic"]) == (question, 4, 3)


def test_score_prints_plan_metrics_per_arm_and_their_totals(tmp_path, capsys):
    """06c 판정 — 갈래마다 넓힌 질문·계획 지표 두 줄과 끝의 합계 한 줄. 합격 판정·기존 줄의 글자는 그대로다."""
    from score import main

    comp, lib = "컴퓨팅 자원에 대한 연구가 궁금해", "공공도서관 서비스 품질 평가 연구가 궁금해"
    comp0 = ["컴퓨팅 자원의 정의 및 개념", "컴퓨팅 자원 관리 기법", "클라우드 컴퓨팅 자원 할당"]
    comp1 = ["클라우드 환경의 컴퓨팅 자원 할당", "그리드 컴퓨팅 자원 스케줄링", "가상화 기반 컴퓨팅 자원 관리"]
    lib0 = ["공공도서관 서비스 품질 평가의 개념", "공공도서관 서비스 품질 평가 방법"]
    lib1 = ["공공도서관 이용자 만족도와 서비스 품질 평가", "SERVQUAL 을 이용한 공공도서관 서비스 품질 평가 방법"]
    jobs = {
        "job-1": _plan_job(comp, comp0, used=comp, elapsed_ms=800, sections=[(comp0[0], ["A", "B"])],
                           trail=[(comp0[0], 3, "sufficient"), (comp0[1], 0, "insufficient"),
                                  (comp0[2], 4, "sufficient")]),
        "job-2": _plan_job(comp, comp1, used="클라우드·그리드 환경의 컴퓨팅 자원 관리에 대한 연구가 궁금해",
                           elapsed_ms=3400, sections=[(comp1[0], ["A", "C"])],
                           trail=[(s, 3, "sufficient") for s in comp1]),
        "job-3": _plan_job(lib, lib0, used=lib, elapsed_ms=1200, sections=[(lib0[0], ["P"])],
                           trail=[(s, 4, "sufficient") for s in lib0]),
        "job-4": _plan_job(lib, lib1, used="공공도서관 이용자 관점의 서비스 품질 평가 연구가 궁금해",
                           elapsed_ms=4600, sections=[(lib1[0], ["P", "Q"])],
                           trail=[(lib1[0], 3, "sufficient"), (lib1[1], 0, "insufficient")]),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=jobs[request.url.path.rsplit("/", 1)[1]])

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"},
                                 "library": {"0": "job-3", "1": "job-4"}}), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    _write_labels(labels / "computing.csv", [("A", "관련"), ("B", "무관"), ("C", "관련")])
    _write_labels(labels / "library.csv", [("P", "관련"), ("Q", "관련")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--labels-dir", str(labels),
                   "--questions", str(_questions(tmp_path, "computing", "library"))], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    out.encode("cp949")
    assert "  갈래 0  넓힌 질문: (원 질문 그대로)" in out
    assert "  갈래 1  넓힌 질문: 클라우드·그리드 환경의 컴퓨팅 자원 관리에 대한 연구가 궁금해" in out
    assert "  갈래 0  계획 지표  일반 틀 2/3 · 근거 0편 1 · insufficient 1 · 계획 0.8초" in out
    assert "  갈래 1  계획 지표  일반 틀 1/2 · 근거 0편 1 · insufficient 1 · 계획 4.6초" in out
    # 갈래 줄 → 정밀도 줄 → 계획 두 줄 순서
    assert out.index("갈래 1  보고서 정밀도") < out.index("  갈래 1  넓힌 질문: 클라우드") < out.index(
        "  갈래 1  계획 지표  일반 틀 0/3")
    totals = ("계획 지표 합계(채점한 2개 질문): 갈래 0 일반 틀 4/5 (80.0%) · 근거 0편 1 · insufficient 1 · 계획 p50 1.0초"
              " · 갈래 1 일반 틀 1/5 (20.0%) · 근거 0편 1 · insufficient 1 · 계획 p50 4.0초")
    assert totals in out
    # 기존 줄은 글자 그대로 — 합격 x/5 와 제외 판정의 관련 합계도 함께 찍고(판정에 쓰지 않는다) 계획 합계는 그 뒤다
    assert "합격 질문: 갈래 0 2/2 · 갈래 1 2/2" in out
    assert out.index("제외 판정의 관련 합계: ") < out.index(totals)


def test_score_plan_only_needs_no_labels(tmp_path, capsys):
    """대조군(questions_control.json)은 라벨 없이 계획 지표만 본다 — 넓히기가 이미 구체적인 질문을 그대로 두는가."""
    from run_pair import CONTROL_QUESTIONS, load_questions
    from score import main

    control = {q["key"]: q["question"] for q in load_questions(CONTROL_QUESTIONS)}
    question = control["ctl_library"]
    plan0 = ["공공도서관 서비스 고객만족도 평가체계의 전개", "공공도서관 고객만족도 평가체계의 주요 쟁점",
             "공공도서관 서비스 고객만족도 평가체계의 남은 과제"]
    plan1 = plan0[:2] + ["공공도서관 고객만족도 평가체계 연구 동향"]
    jobs = {
        "job-1": _plan_job(question, plan0, used=question, elapsed_ms=900,
                           trail=[(s, 3, "sufficient") for s in plan0]),
        "job-2": _plan_job(question, plan1, used=question + " ", elapsed_ms=4100,
                           trail=[(plan1[0], 3, "sufficient"), (plan1[1], 0, "insufficient"),
                                  (plan1[2], 2, "sufficient")]),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=jobs[request.url.path.rsplit("/", 1)[1]])

    pairs = tmp_path / "pairs_control.json"
    pairs.write_text(json.dumps({"ctl_library": {"0": "job-1", "1": "job-2"}}), encoding="utf-8")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--plan-only", "--labels-dir", str(tmp_path / "없는 폴더"),
                   "--questions", str(CONTROL_QUESTIONS)], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    out.encode("cp949")
    assert f"[ctl_library] {question}" in out
    assert "[ctl_elderly] pairs 에 없다 - run_pair.py --only ctl_elderly 로 돌린다" in out
    # 원 질문의 '과제' 는 측면 낱말로 세지 않는다 — 갈래 1 의 '동향' 만 일반 틀이다
    assert "  갈래 0  넓힌 질문: (원 질문 그대로)" in out and "  갈래 1  넓힌 질문: (원 질문 그대로)" in out
    assert "  갈래 0  계획 지표  일반 틀 0/3 · 근거 0편 0 · insufficient 0 · 계획 0.9초" in out
    assert "  갈래 1  계획 지표  일반 틀 1/3 · 근거 0편 1 · insufficient 1 · 계획 4.1초" in out
    assert ("계획 지표 합계(채점한 1개 질문): 갈래 0 일반 틀 0/3 (0.0%) · 근거 0편 0 · insufficient 0 · 계획 p50 0.9초"
            " · 갈래 1 일반 틀 1/3 (33.3%) · 근거 0편 1 · insufficient 1 · 계획 p50 4.1초") in out
    # 라벨을 읽지 않으니 합격 판정·보고서 정밀도·라벨 안내 줄이 없다
    for absent in ("합격 질문:", "보고서 정밀도", "절별 무관", "라벨 파일이 없다", "제외 판정의 관련 합계"):
        assert absent not in out


def test_score_keeps_going_when_the_broadened_question_has_a_letter_cp949_lacks(tmp_path, monkeypatch):
    """넓힌 질문은 LLM 글이다 — cp949 에 없는 글자(—)가 들어 있어도, PYTHONIOENCODING 없이 돌린 Git Bash(표준 출력
    cp949)에서 채점이 멈추지 않는다. 그 글자만 ? 로 찍히고 뒤 줄(합계)까지 나온다."""
    from score import main

    question = "컴퓨팅 자원에 대한 연구가 궁금해"
    used = "클라우드 환경의 컴퓨팅 자원 — 관리에 대한 연구가 궁금해"
    plan = ["클라우드 환경의 컴퓨팅 자원 할당", "클라우드 환경의 컴퓨팅 자원 스케줄링"]
    jobs = {job_id: _plan_job(question, plan, used=used, elapsed_ms=2000,
                              trail=[(s, 3, "sufficient") for s in plan])
            for job_id in ("job-1", "job-2")}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=jobs[request.url.path.rsplit("/", 1)[1]])

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"}}), encoding="utf-8")
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp949")
    monkeypatch.setattr(sys, "stdout", console)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--plan-only",
                   "--questions", str(_questions(tmp_path, "computing"))], client=client)

    assert rc == 0
    console.flush()
    out = console.buffer.getvalue().decode("cp949")
    assert "  갈래 1  넓힌 질문: 클라우드 환경의 컴퓨팅 자원 ? 관리에 대한 연구가 궁금해" in out
    assert ("계획 지표 합계(채점한 1개 질문): 갈래 0 일반 틀 0/2 (0.0%) · 근거 0편 0 · insufficient 0 · 계획 p50 2.0초"
            " · 갈래 1 일반 틀 0/2 (0.0%) · 근거 0편 0 · insufficient 0 · 계획 p50 2.0초") in out


# ── make_labels.py ──────────────────────────────────────────────────────
```

② 같은 파일 import(6-11행) — 위 테스트가 cp949 표준 출력을 `io.TextIOWrapper` 로 흉내 낸다. old:

```python
import csv
import json
import re
```

new:

```python
import csv
import io
import json
import re
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`

Expected: `7 failed, 40 passed` —
- `test_contains_copy_matches_the_shared_fixture` — `ImportError: cannot import name 'contains' from 'score'`
- `test_generic_frames_skip_aspect_words_inside_the_question` — `ImportError: cannot import name 'ASPECT_WORDS' from 'score'`
- `test_plan_metrics_read_the_plan_the_trail_and_the_last_plan_step`·`test_plan_metrics_of_a_job_before_06c_have_no_question_used_or_time` — `ImportError: cannot import name 'format_plan' from 'score'`
- `test_score_prints_plan_metrics_per_arm_and_their_totals` — `AssertionError`(`  갈래 0  넓힌 질문: (원 질문 그대로)` 줄이 없다 — 기존 줄·`합격 질문: 갈래 0 2/2 · 갈래 1 2/2` 는 지금도 나온다)
- `test_score_plan_only_needs_no_labels`·`test_score_keeps_going_when_the_broadened_question_has_a_letter_cp949_lacks` — `SystemExit: 2`(argparse 가 `--plan-only` 를 모른다)

- [ ] **Step 3: 구현한다**

① `scripts/research_eval/score.py` 독스트링 첫 줄 — critic 전용 도구가 아니게 된다(Task V1 이 `run_pair.py` 머리를 고친 것과 짝). old:

```python
r"""score.py — critic 두 갈래 채점 (HTTP 만, DB 를 읽지도 쓰지도 않는다)
```

new:

```python
r"""score.py — 잡 파라미터 두 갈래 채점 (HTTP 만, DB 를 읽지도 쓰지도 않는다)
```

이어서 같은 파일 독스트링 끝과 import. old:

```python
견줄 수 있다. 합격 판정에는 쓰지 않는다.

실행 (서버):
  docker exec nl-lib-fastapi python /app/data/research_eval/score.py \
    --api http://localhost:8000/api --pairs /app/data/research_eval/pairs.json \
    --labels-dir /app/data/research_eval/labels
"""
import argparse
import csv
import json
import sys
from pathlib import Path
```

new:

```python
견줄 수 있다. 합격 판정에는 쓰지 않는다.
갈래마다 계획 지표 두 줄도 찍는다(06c — spec §12-7). '넓힌 질문' 은 마지막 계획 단계 result 의 question_used 다 — 원 질문과
같으면 '(원 질문 그대로)', 06c 전 잡이면 '(기록 없음)'. '계획 지표' 는 일반 틀(측면 낱말 사전 ASPECT_WORDS 와 맞는 하위질문 —
원 질문에 이미 든 측면 낱말은 세지 않는다)·근거 0편과 insufficient 하위질문 수(report.trail)·계획 시간(result.elapsed_ms)이다.
끝에 채점한 질문의 계획 지표 합계(일반 틀 비율·계획 시간 p50) 한 줄. 이 줄들도 합격 판정에는 쓰지 않는다 — 06c 판정은 보고서
정밀도·관련 편수와 이 지표로 하고, 합격 x/5 와 제외 판정의 관련 합계는 그대로 함께 적는다.
--plan-only 는 라벨을 읽지 않고 질문마다 계획 지표 두 줄과 끝의 합계 한 줄만 찍는다(대조군 questions_control.json).
넓힌 질문은 LLM 글이라 cp949 에 없는 글자(—)가 들 수 있다 — 표준 출력을 errors=replace 로 두어 cp949 콘솔에서도 그 글자만
? 로 찍고 채점을 잇는다.
contains 는 app/services/research/terms.py 의 contains 복사본이다 — 이 스크립트는 서버의 /app/data/research_eval/ 에서
app 없이 돈다(HTTP 만). 두 쪽은 공용 고정 예제 frontend/tests/fixtures/term_checks.json 으로 묶는다(고치면 둘 다 고친다).

실행 (서버):
  docker exec nl-lib-fastapi python /app/data/research_eval/score.py \
    --api http://localhost:8000/api --pairs /app/data/research_eval/pairs.json \
    --labels-dir /app/data/research_eval/labels
대조군(라벨 없이 계획 지표만):
  docker exec nl-lib-fastapi python /app/data/research_eval/score.py --plan-only \
    --api http://localhost:8000/api --pairs /app/data/research_eval/pairs_control.json \
    --questions /app/data/research_eval/questions_control.json
"""
import argparse
import csv
import json
import statistics
import sys
import unicodedata
from pathlib import Path
```

② 같은 파일 상수. old:

```python
ARMS = ("0", "1")
TOTAL_KEYS = ("relevant", "irrelevant", "unlabeled", "excluded", "excluded_labeled", "excluded_relevant")
```

new:

```python
ARMS = ("0", "1")
TOTAL_KEYS = ("relevant", "irrelevant", "unlabeled", "excluded", "excluded_labeled", "excluded_relevant")
# 일반 틀의 측면 낱말 사전 — spec §12-7 표 그대로다. 계획 프롬프트의 측면 목록(research_plan.yaml:12)과 같지 않다:
# 동향·발전 방향이 더 있고 '평가' 는 없다. 바꾸면 판정 지표가 바뀐다
ASPECT_WORDS: tuple[str, ...] = ("개념", "정의", "방법", "기법", "적용 분야", "성과", "한계", "과제", "동향", "발전 방향")
PLAN_TOTAL_KEYS = ("subquestions", "generic", "zero_evidence", "insufficient")
```

③ 같은 파일 — `format_totals` 뒤(`main` 앞)에 함수들. old(`format_totals` 의 끝):

```python
        + " · ".join(f"갈래 {arm} 관련 {totals[arm]['excluded_relevant']}/라벨 {totals[arm]['excluded_labeled']}"
                     f" (제외 {totals[arm]['excluded']}편)" for arm in ARMS),
    ]
```

new:

```python
        + " · ".join(f"갈래 {arm} 관련 {totals[arm]['excluded_relevant']}/라벨 {totals[arm]['excluded_labeled']}"
                     f" (제외 {totals[arm]['excluded']}편)" for arm in ARMS),
    ]


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def contains(text: str, word: str) -> bool:
    """app/services/research/terms.py 의 contains 복사본(이 스크립트는 app 을 import 하지 않는다) — 고치면 둘 다 고치고
    공용 고정 예제 frontend/tests/fixtures/term_checks.json 을 맞춘다. NFKC·casefold·공백 제거 뒤 부분 문자열이거나
    word 의 낱말이 모두 순서대로(공백 지운 text 에서 차례로) 들어 있으면 참. word 가 비면(공백 제거 뒤) 거짓."""
    pieces = _normalize(word or "").split()
    if not pieces:
        return False
    flat = "".join(_normalize(text or "").split())
    if "".join(pieces) in flat:
        return True
    pos = 0
    for piece in pieces:
        found = flat.find(piece, pos)
        if found < 0:
            return False
        pos = found + len(piece)
    return True


def generic_frames(question: str, subquestions: list[str]) -> int:
    """측면 낱말 사전과 맞는 하위질문 수. 원 질문에 이미 든 측면 낱말은 빼고 센다 — csr 의 '재무성과' 를 '성과' 로
    세면 원 질문을 그대로 지킨 하위질문까지 일반 틀이 된다."""
    aspects = [w for w in ASPECT_WORDS if not contains(question, w)]
    return sum(any(contains(sq, w) for w in aspects) for sq in subquestions)


def _last_plan_result(steps: list[dict]) -> dict:
    """재시도로 계획 단계가 여럿이면 seq 가 가장 큰 행이 지금 계획이다."""
    step = max((s for s in steps if s["kind"] == "plan"), key=lambda s: s["seq"], default=None)
    return (step or {}).get("result") or {}


def plan_metrics(job: dict) -> dict:
    """GET /research/{id} 한 잡의 계획 지표. 하위질문은 승인된 계획(job.plan — shared 모드의 갈래 1 은 갈래 0 의 계획),
    없으면 보고서 trail 의 하위질문이다. question_used·plan_ms 는 06c 전 잡이면 None."""
    report = job.get("report") or {}
    trail = report.get("trail") or []
    question = job.get("question") or report.get("question") or ""
    subquestions = job.get("plan") or [t["subquestion"] for t in trail]
    result = _last_plan_result(job.get("steps") or [])
    return {
        "question": question,
        "question_used": result.get("question_used"),
        "subquestions": len(subquestions),
        "generic": generic_frames(question, subquestions),
        "zero_evidence": sum(t.get("evidence_count") == 0 for t in trail),
        "insufficient": sum(t.get("verdict") == "insufficient" for t in trail),
        "plan_ms": result.get("elapsed_ms"),
    }


def _tidy(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _seconds(ms: float | None) -> str:
    return "-" if ms is None else f"{ms / 1000:.1f}초"


def format_question_used(arm_key: str, m: dict) -> str:
    used = m["question_used"]
    if used is None:
        shown = "(기록 없음)"
    elif _tidy(used) == _tidy(m["question"]):
        shown = "(원 질문 그대로)"
    else:
        shown = used
    return f"  갈래 {arm_key}  넓힌 질문: {shown}"


def format_plan(arm_key: str, m: dict) -> str:
    return (f"  갈래 {arm_key}  계획 지표  일반 틀 {m['generic']}/{m['subquestions']} · 근거 0편 {m['zero_evidence']}"
            f" · insufficient {m['insufficient']} · 계획 {_seconds(m['plan_ms'])}")


def _new_plan_total() -> dict:
    return dict.fromkeys(PLAN_TOTAL_KEYS, 0) | {"plan_ms": []}


def add_plan_totals(total: dict, m: dict) -> None:
    """질문 하나의 계획 지표를 그 갈래의 합계에 더한다 — 계획 시간은 p50 을 내려고 값을 모은다."""
    for key in PLAN_TOTAL_KEYS:
        total[key] += m[key]
    if m["plan_ms"] is not None:
        total["plan_ms"].append(m["plan_ms"])


def format_plan_totals(totals: dict[str, dict], scored: int) -> str:
    """채점한 질문의 계획 지표 합계 한 줄 — 일반 틀 비율은 하위질문 수의 합을 분모로, 계획 시간은 중앙값(p50)."""
    parts = []
    for arm in ARMS:
        t = totals[arm]
        rate = f"{t['generic'] / t['subquestions'] * 100:.1f}%" if t["subquestions"] else "-"
        p50 = statistics.median(t["plan_ms"]) if t["plan_ms"] else None
        parts.append(f"갈래 {arm} 일반 틀 {t['generic']}/{t['subquestions']} ({rate}) · 근거 0편 {t['zero_evidence']}"
                     f" · insufficient {t['insufficient']} · 계획 p50 {_seconds(p50)}")
    return f"계획 지표 합계(채점한 {scored}개 질문): " + " · ".join(parts)


def _plan_lines(arm: str, job: dict, total: dict) -> list[str]:
    m = plan_metrics(job)
    add_plan_totals(total, m)
    return [format_question_used(arm, m), format_plan(arm, m)]
```

④ (Step 0 에서 C1 의 `contains`·`_normalize` 본문이 위와 다르면 ③ 의 두 본문을 C1 의 글로 바꾼다 — `contains` 의 docstring 은 위 것을 둔다. C1 이 다른 이름의 도우미를 부르면 그 도우미를 `_normalize` 자리에 같은 이름·같은 글로 옮긴다. `score.py` 에는 지금 `_normalize`·`contains` 라는 이름이 없다 — `da80f23` 의 `score.py` 함수는 `load_labels`~`format_totals`·`main` 뿐이다.)

⑤ 같은 파일 `main` 의 머리와 인자 — 첫 줄(argparse 앞)에서 표준 출력을 `errors="replace"` 로 둔다(알아 둘 것 'cp949'). old:

```python
def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="critic 두 갈래 채점 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="run_pair.py 출력 JSON")
    ap.add_argument("--labels-dir", type=Path, default=HERE / "labels")
    ap.add_argument("--questions", type=Path, default=QUESTIONS, help="고정 질문 목록 — 합격 질문의 분모")
    args = ap.parse_args(argv)
```

new:

```python
def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # 넓힌 질문은 LLM 글 — cp949 콘솔에 없는 글자(—)로 채점이 멈추지 않게
    ap = argparse.ArgumentParser(description="두 갈래 채점 — critic 기준·06c 넓히기 등 잡 파라미터 갈래 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="run_pair.py 출력 JSON")
    ap.add_argument("--labels-dir", type=Path, default=HERE / "labels")
    ap.add_argument("--questions", type=Path, default=QUESTIONS, help="고정 질문 목록 — 합격 질문의 분모")
    ap.add_argument("--plan-only", action="store_true",
                    help="라벨 없이 계획 지표만 찍는다(대조군 questions_control.json)")
    args = ap.parse_args(argv)
```

⑥ 같은 파일 `main` 의 누적 변수. old:

```python
    totals = {arm: dict.fromkeys(TOTAL_KEYS, 0) for arm in ARMS}
    scored = 0
```

new:

```python
    totals = {arm: dict.fromkeys(TOTAL_KEYS, 0) for arm in ARMS}
    plan_totals = {arm: _new_plan_total() for arm in ARMS}
    scored = 0
```

⑦ 같은 파일 `main` 의 질문 루프 — 라벨 읽기를 `--plan-only` 가 아닐 때로 감싸고, 잡을 통째로 남기고, `--plan-only` 분기를 둔다. old:

```python
            path = args.labels_dir / f"{key}.csv"
            if not path.exists():
                print(f"[{key}] 라벨 파일이 없다: {path} - make_labels.py 를 먼저 돌린다")
                skipped.append(key)
                continue
            try:
                labels = load_labels(path)
            except ValueError as e:
                print(f"[{key}] {e}")
                return 2
            try:
                reports = {arm: get_job(client, api, arms[arm]).get("report") for arm in ("0", "1")}
            except httpx.HTTPError as e:
                print(f"[{key}] 잡을 읽지 못했다({type(e).__name__}: {e}) - 건너뛴다")
                skipped.append(key)
                continue
            if not all(reports.values()):
```

new:

```python
            if not args.plan_only:
                path = args.labels_dir / f"{key}.csv"
                if not path.exists():
                    print(f"[{key}] 라벨 파일이 없다: {path} - make_labels.py 를 먼저 돌린다")
                    skipped.append(key)
                    continue
                try:
                    labels = load_labels(path)
                except ValueError as e:
                    print(f"[{key}] {e}")
                    return 2
            try:
                jobs = {arm: get_job(client, api, arms[arm]) for arm in ARMS}
            except httpx.HTTPError as e:
                print(f"[{key}] 잡을 읽지 못했다({type(e).__name__}: {e}) - 건너뛴다")
                skipped.append(key)
                continue
            if args.plan_only:
                print(f"[{key}] {jobs['0'].get('question', '')}")
                scored += 1
                for arm in ARMS:
                    for line in _plan_lines(arm, jobs[arm], plan_totals[arm]):
                        print(line)
                continue
            reports = {arm: jobs[arm].get("report") for arm in ARMS}
            if not all(reports.values()):
```

⑧ 같은 파일 `main` 의 갈래 줄 뒤와 요약. old:

```python
                print(format_arm(arm, result))
                print(format_precision(arm, result["report"]))
    finally:
        if own:
            client.close()
    total = len(keys)
    print(f"합격 질문: 갈래 0 {passed['0']}/{total} · 갈래 1 {passed['1']}/{total}")
    if scored:
        for line in format_totals(totals, scored):
            print(line)
    if skipped:
```

new:

```python
                print(format_arm(arm, result))
                print(format_precision(arm, result["report"]))
                for line in _plan_lines(arm, jobs[arm], plan_totals[arm]):
                    print(line)
    finally:
        if own:
            client.close()
    if args.plan_only:
        if scored:
            print(format_plan_totals(plan_totals, scored))
        return 0
    total = len(keys)
    print(f"합격 질문: 갈래 0 {passed['0']}/{total} · 갈래 1 {passed['1']}/{total}")
    if scored:
        for line in format_totals(totals, scored):
            print(line)
        print(format_plan_totals(plan_totals, scored))
    if skipped:
```

⑨ `scripts/research_eval/README.md` 1행(제목)과 3행 앞부분 — critic 전용 도구가 아니게 된다(Task V1 의 `run_pair.py` 머리와 짝). old:

```markdown
# critic 두 갈래 판정 도구 (research_eval)

딥리서치 critic 의 기준 스위치(잡 파라미터 `critic_scope` — 0 = 지금 기준, 1 = 원 질문 기준)를 켤지 정하는 도구다. 고정 질문 5개를 운영에서 두 갈래로 돌리고, 사람이 단 라벨로 합격선을 센다(spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` D11·§8). 06a 배포 당일, 06b 배포 뒤 D18 재판정(아래 'D18 재판정'), 리허설(10/23~25)에 다시 돈다.
```

new:

```markdown
# 두 갈래 판정 도구 (research_eval)

딥리서치 잡 파라미터 스위치(`critic_scope` — 0 = 지금 기준, 1 = 원 질문 기준, 06c 의 `broaden`·`query_context`)를 켤지 정하는 도구다. 고정 질문 5개를 운영에서 두 갈래로 돌리고, 사람이 단 라벨로 합격선을 센다(spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` D11·§8). 06a 배포 당일, 06b 배포 뒤 D18 재판정(아래 'D18 재판정'), 06c 배포 당일 넓히기·검색어 합성 재판정(아래 '06c 재판정' — critic 기준이 아니라 `broaden`·`query_context` 를 가른다), 리허설(10/23~25)에 다시 돈다.
```

⑩ 같은 파일 표의 `questions.json`·`run_pair.py` 줄(9-10행). old:

```markdown
| `questions.json` | 고정 질문 5개 `[{key, question}]` — `key` 가 라벨 파일 이름이 된다 | — |
| `run_pair.py` | 질문마다 갈래 0·1 잡을 만들고(갈래 1 은 갈래 0 의 계획으로 승인) 완료까지 기다려 `{key: {"0": 잡 id, "1": 잡 id}}` 를 쓴다 | 안 씀(HTTP) |
```

new:

```markdown
| `questions.json` | 고정 질문 5개 `[{key, question}]` — `key` 가 라벨 파일 이름이 된다 | — |
| `questions_control.json` | 06c 대조군 — 논문 상세 [이 논문으로 딥리서치] 꼴(`frontend/utils/paperResearch.ts` `paperResearchQuestion`)의 풍부한 질문 2개(소장 논문 `KCI_FI001933966`·`KCI_FI001023392` 의 제목). `--questions` 로만 쓰고 고정 5문항에 섞지 않는다(합격 질문의 분모가 바뀐다) | — |
| `run_pair.py` | 질문마다 갈래 0·1 잡을 만들고 완료까지 기다려 `{key: {"0": 잡 id, "1": 잡 id}}` 를 쓴다. 갈래 잡 파라미터는 `--param0`(기본 `{"critic_scope": 0}`)·`--param`(기본 `{"critic_scope": 1}`) JSON 객체이고, 승인은 `--plan shared`(기본 — 갈래 1 을 갈래 0 의 계획으로)·`--plan own`(갈래마다 제 계획으로)이다. 시작할 때 `갈래 0 {…} · 갈래 1 {…} · 계획 …` 한 줄을 찍는다 | 안 씀(HTTP) |
```

⑪ 같은 파일 표의 `score.py` 줄(12행) 끝. old:

```markdown
끝에 채점한 질문의 합계 두 줄(보고서 정밀도·제외 판정의 관련 수)도 찍는다 — 06a 완료노트 §5-5 의 손 계산과 같은 셈이고 판정에는 쓰지 않는다 | 안 씀(HTTP) |
```

new:

```markdown
끝에 채점한 질문의 합계 두 줄(보고서 정밀도·제외 판정의 관련 수)도 찍는다 — 06a 완료노트 §5-5 의 손 계산과 같은 셈이고 판정에는 쓰지 않는다. 06c 부터 갈래마다 계획 지표 두 줄(`넓힌 질문:` — 그 잡의 계획 단계가 넓힌 질문, `계획 지표` — 일반 틀·근거 0편·insufficient 하위질문 수·계획 시간)과 끝에 `계획 지표 합계 …` 한 줄(일반 틀 비율·계획 시간 p50)도 찍는다. `--plan shared` 의 갈래 1 은 승인된 계획이 갈래 0 의 것이라, 그 갈래의 `넓힌 질문:` 으로 세운 계획이 아니다(일반 틀은 승인된 계획의 하위질문으로 센다). `--plan-only` 는 라벨 없이 계획 지표만 찍는다(대조군). 낱말 맞추기 `contains` 는 `app/services/research/terms.py` 의 복사본이다(공용 고정 예제 `frontend/tests/fixtures/term_checks.json` 으로 묶는다) | 안 씀(HTTP) |
```

⑫ 같은 파일 끝(D18 재판정 결과의 마지막 줄 뒤)에 새 절. old:

```markdown
출력 전체·비교 표·다음 경로는 완료노트 §5-4.
```

new:

````markdown
출력 전체·비교 표·다음 경로는 완료노트 §5-4.

## 06c 재판정 (넓히기·검색어 합성)

06c 는 잡 파라미터 스위치 둘을 더했다 — `broaden`(계획 전에 gemma 1회로 질문을 한 문장으로 넓히고 범위 용어를 뽑는다)·`query_context`(검색어에 범위 용어를 붙이고 `국내 학술논문에서` 를 뗀다), 둘 다 기본 0(spec D25·§12-2). 06c 운영 배포 당일, 같은 코퍼스 시점에 고정 질문 5개를 두 갈래로 돌려 기본값을 정한다(spec §12-7, 열린 질문 Q4). 갈래 0 = 지금 방식(두 스위치 0), 갈래 1 = 둘 다 켬, 두 갈래 모두 `critic_scope` 0. 넓히기는 계획을 바꾸므로 `--plan own`(갈래마다 제 계획)으로 돌린다 — shared 로 돌리면 갈래 1 이 갈래 0 의 계획으로 승인돼 넓히기 효과가 0 이다. 기준은 같은 날 돌린 갈래 0 이고(D11 의 같은 시점 상대 비교), 06b 값은 참고로만 본다 — 적재가 계속돼 같은 질문도 결과가 달라진다.

1. **라벨·스크립트 맞추기.** 서버 `labels/` 가 저장소의 라벨 파일(`labels/<질문키>.csv` 5개, D18 재판정 뒤 318줄, `메모` 칸 포함)과 같아야 한다. 다르거나 없으면 서버 파일을 `labels.pre-06c/` 로 옮겨 두고 저장소 파일을 올린다. 스크립트(`run_pair.py`·`score.py`)와 `questions_control.json` 도 06c 판으로 서버 폴더에 올린다(흐름 2 — 앱 이미지에 없다).
2. **06b 참고값.** 06b RUN(`pairs_20261008_d18.json`)에 새 `score.py` 를 먼저 돌린다(흐름 6 의 명령에서 `$RUN` 만 그 이름). 합격 질문·정밀도 줄은 D18 재판정 결과(위)와 같아야 하고, 새 계획 지표 줄이 06b 참고값이다 — 06b 잡에는 넓힌 질문·계획 시간 기록이 없어 `넓힌 질문: (기록 없음)`·`계획 -` 로 나오고, 일반 틀·근거 0편·insufficient 는 센다(spec §12-7 표의 '계획에서 06b 잡으로 센다'). 06b RUN 은 개발 PC 에서 돌려(위 'D18 재판정' 결과) 서버 폴더에 없을 수 있다 — 그대로 돌리면 `score.py` 가 파일을 찾지 못해 멈춘다. 없으면 06b 완료노트(`docs/roadmap/round06b-완료노트.md`) §5-4 의 잡 id 표로 `pairs_20261008_d18.json` 을 다시 써서 올리거나, 개발 PC 의 저장소 루트에서 `PYTHONIOENCODING=utf-8 python scripts/research_eval/score.py --api http://192.168.12.57:92/api --pairs <06b 판정 폴더>/pairs_20261008_d18.json --labels-dir scripts/research_eval/labels` 로 센다.
3. **두 갈래 실행.** 전제는 흐름 3 과 같다(`RESEARCH_QUEUE=q_research`). 06b RUN 과 섞이지 않게 새 이름을 쓴다.
   ```bash
   RUN=pairs_$(date +%Y%m%d)_06c
   docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
     --api http://localhost:8000/api --out /app/data/research_eval/$RUN.json --plan own \
     --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' \
     --param '{"critic_scope": 0, "broaden": 1, "query_context": 1}'
   ```
   첫 줄 `갈래 0 {"critic_scope": 0, "broaden": 0, "query_context": 0} · 갈래 1 {"critic_scope": 0, "broaden": 1, "query_context": 1} · 계획 own` 을 기록에 남긴다. 개발 PC(Git Bash)에서 운영 API 로 돌려도 된다(06b 선례) — `cd scripts/research_eval && PYTHONIOENCODING=utf-8 python run_pair.py --api http://192.168.12.57:92/api --out <폴더>/$RUN.json` 에 같은 `--plan`·`--param0`·`--param` 을 붙인다. 개발 PC 에서 돌렸으면 4·5·6 도 개발 PC 에서 같은 `--api`, 로컬 `--pairs`, 저장소 라벨의 로컬 사본(`labels/*.csv` 를 저장소 밖 폴더로 복사해 `--out-dir`·`--labels-dir` 에 준다 — 저장소 파일에 바로 덧붙이지 않게)으로 돈다(06c 계획의 판정 Task 와 같은 길 — 서버 `labels/` 를 맞출 일이 없다). 4·5·6 의 `make_labels.py`·`score.py` 명령에도 앞에 `PYTHONIOENCODING=utf-8` 을 붙인다 — 없으면 Git Bash 에서 한글이 깨지고, 넓힌 질문에 든 cp949 에 없는 글자(—)는 `?` 로 찍힌다(채점은 멈추지 않는다). JSON 객체가 아니면 잡을 만들지 않고 `잡 파라미터는 JSON 객체여야 한다: …` 를 찍고 끝난다(종료 코드 2).
4. **라벨 덧붙이기.** 흐름 4 의 명령(`$RUN` 만 새 이름). 새 줄은 D18 재판정 5 와 같은 위임 방식(Claude 판정자 셋 + 표가 갈린 줄은 최종 판정 — 사용자 이견이 없으면)으로 단다. 이미 단 318줄은 다시 달지 않는다.
5. **채점.** 흐름 6 의 명령(`$RUN` 만 새 이름). `판정 보류`·`라벨 칸이 빈 논문이 …` 가 없는 출력으로만 판정한다. 판정에 쓰는 줄은 `보고서 정밀도 합계 …`(정밀도·관련 편수)·`계획 지표 합계 …`(일반 틀 비율·근거 0편·insufficient·계획 p50)와 질문별 `넓힌 질문:` 줄이다. `합격 질문:`·`제외 판정의 관련 합계 …` 는 함께 적되 판정에 쓰지 않는다 — 06b 갈래 0 의 0/5 는 주로 과잉 제외 때문이라 계획이 좋아져도 움직이지 않을 수 있고, 넓히기가 하위질문을 좁히면 하위질문 기준 제외가 늘 수 있다.
6. **대조군.** 논문 버튼 꼴 질문 2개(`questions_control.json`)를 같은 두 갈래로 돌리고 라벨 없이 계획 지표만 센다.
   ```bash
   docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
     --api http://localhost:8000/api --out /app/data/research_eval/${RUN}_control.json --plan own \
     --questions /app/data/research_eval/questions_control.json \
     --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' \
     --param '{"critic_scope": 0, "broaden": 1, "query_context": 1}'
   docker exec nl-lib-fastapi python /app/data/research_eval/score.py --plan-only \
     --api http://localhost:8000/api --pairs /app/data/research_eval/${RUN}_control.json \
     --questions /app/data/research_eval/questions_control.json
   ```
   갈래 1 의 `넓힌 질문:` 이 `(원 질문 그대로)` 이거나 원 질문의 낱말을 모두 품고 주제를 바꾸지 않았는지, 갈래 1 의 일반 틀 비율·근거 0편이 갈래 0 보다 늘지 않았는지 본다.
7. **판단(Q4).** 같은 날 갈래 0 이 기준이다. **모두 좋아짐** — 보고서 정밀도·관련 편수가 기준 이상이고, 일반 틀 비율이 줄고, 근거 0편·insufficient 가 늘지 않고, 갈래 1 의 계획 p50 이 5초 이하이고, 대조군이 그대로 → 두 스위치 모두 1. **엇갈림** — 모두 좋아지지는 않았지만 ① 일반 틀 비율이 줄었거나 ② 보고서 정밀도 합계가 높아졌거나 관련 편수가 늘었다 → 스위치를 나눠 다시 판정한다(3 처럼 새 RUN 이름, 라벨은 4 처럼 새 논문만). 기준은 각 RUN 안의 갈래 0 이다. `query_context` 는 `--plan shared --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' --param '{"critic_scope": 0, "broaden": 1, "query_context": 1}'` RUN(갈래 1 의 계획 단계가 범위 용어를 내지만 승인은 갈래 0 의 계획 — 검색어만 다르다)에서 보고서 정밀도·관련 편수가 같거나 높고 근거 0편·insufficient 가 같거나 적으면 1 이다. 이 RUN 은 두 갈래의 계획이 같아(`score.py` 는 하위질문을 승인된 계획에서 센다) 일반 틀로 가르지 않는다. 이 RUN 의 갈래 1 `넓힌 질문:` 은 범위 용어를 뽑은 문장일 뿐, 계획은 갈래 0 의 것이다. `broaden` 은 `--plan own --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' --param '{"critic_scope": 0, "broaden": 1, "query_context": 0}'` RUN(계획만 다르다)에서 일반 틀 비율이 낮고, 정밀도·관련 편수가 같거나 높고, 근거 0편·insufficient 가 같거나 적고, 계획 p50 이 5초 이하이고, 대조군이 그대로이면 1 이다. `broaden` 0 이면 범위 용어가 비어 `query_context` 만 켠 갈래는 군더더기만 떼므로 이렇게 나눈다. **그 밖**(①② 모두 아님) → 둘 다 0.
8. **기본값 커밋.** 켜는 스위치가 있으면 `app/services/research/state.py` `DEFAULT_PARAMS` 의 그 칸을 1 로 바꾸고, 기본값을 단언하는 테스트 둘(`app/tests/test_research_state.py` `TestMergeParams`·`app/tests/test_research_api.py` `TestCreate` 의 기본값 테스트 — 06c 판 이름은 `test_query_switches_are_off_by_default`·`test_query_switches_are_saved_off_unless_asked`, 기본값 커밋 뒤 이름은 `test_query_switch_defaults_follow_the_06c_verdict`·`test_query_switches_are_saved_with_their_defaults_unless_asked`)을 맞춘 작은 커밋을 dev 에 한다 — 10/17~18 배포에 싣는다(spec §12-6). 기본값을 켠 뒤에는 `run_pair.py` 의 기본 갈래 0(`{"critic_scope": 0}`)이 켠 스위치를 따라가므로, 이후 재판정은 늘 `--param0` 에 두 칸을 적는다(3 의 명령처럼).
9. **기록.** 흐름 7 과 같다 — 덧붙인 라벨 파일을 저장소로 가져와 `git add -f`, RUN 의 잡 id·채점 출력·대조군 출력·비교 표는 `docs/roadmap/round06c-완료노트.md` 에, 결과 요약은 이 절 끝에 적는다. 켠 뒤(10/17~18 배포 뒤) 랜딩 논문 예시 셋(판정 질문과 같은 문장)의 보고서를 다시 본다 — 바꿀 것은 06d 가 고친다.
````

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`

Expected: `47 passed` (Task V1 뒤 40 + 7 — 기존 채점 테스트 여섯은 고치지 않고 통과한다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_terms.py tests/test_research_eval.py -q -p no:cacheprovider`

Expected: 실패 0 — 공용 고정 예제를 읽는 두 쪽(Task C1 의 `test_research_terms.py`·이 파일)이 함께 통과한다. 수는 Task C1 의 `test_research_terms.py` 수 + 47.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 Task 0 기준선과 같은 파일. passed = Task V2 앞 수 + 7.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && grep -c "^## 06c 재판정" scripts/research_eval/README.md && grep -c "questions_control.json" scripts/research_eval/README.md`

Expected: `1` 과 `5`(그 이름이 든 줄 수 — 표 1 · 걸음 1 의 본문 1 · 걸음 6 의 본문 1 · 걸음 6 의 명령 2).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add scripts/research_eval/score.py && git add scripts/research_eval/README.md && git add app/tests/test_research_eval.py && git status --short && git commit -m "[Feat] round06c — score 에 계획 지표(넓힌 질문·일반 틀·근거 0편·insufficient·계획 시간)와 --plan-only, README 06c 재판정 절차를 더한다: 갈래마다 '넓힌 질문:'(마지막 계획 단계 result 의 question_used — 원 질문과 같으면 '원 질문 그대로', 06c 전 잡은 '기록 없음')과 '계획 지표' 줄, 끝에 '계획 지표 합계'(일반 틀 비율·계획 p50) 줄을 찍는다. 일반 틀은 측면 낱말 사전(개념·정의·방법·기법·적용 분야·성과·한계·과제·동향·발전 방향)과 맞는 하위질문 수이고 원 질문에 이미 든 측면 낱말은 세지 않는다(csr '재무성과'). 낱말 맞추기 contains 는 app/services/research/terms.py 의 복사본이고(score 는 서버에서 app 없이 HTTP 만으로 돈다) 공용 고정 예제 term_checks.json 과 원본 대조로 묶는다. --plan-only 는 라벨 없이 대조군의 계획 지표만 찍는다. 넓힌 질문은 LLM 글이라 cp949 콘솔(PYTHONIOENCODING 없는 Git Bash)에서 없는 글자(—)로 채점이 멈추지 않게 표준 출력을 errors=replace 로 둔다. score·README 머리 설명을 critic 전용에서 잡 파라미터 두 갈래로 바꾼다. 합격 판정과 기존 출력의 글자는 그대로다. README 에 06c 판정 9걸음(06b 참고값·--plan own 두 갈래·대조군·Q4 판단과 스위치 나눠 다시 재기·기본값 커밋)을 적는다(spec §12-7)"
```

---

### Task V3: 화면 한 줄 — `questionUsedFromSteps`·`understoodLine`·PlanCard `questionUsed`

**왜:** spec §12-2 '화면 한 줄'·D25 — 넓히기를 켜면 계획은 원 질문이 아니라 넓힌 문장으로 세워진다. 사용자가 계획 카드에서 "이렇게 이해했어요: …" 한 줄로 그 문장을 보고, 마음에 들지 않으면 지금처럼 하위질문을 고친다(승인 단계를 더하지 않는다). 원 질문과 같으면(넓히기를 껐거나 원문으로 물러난 잡) 숨긴다. 06c 는 부품까지만 만든다 — 타입의 선택 칸 셋, 리듀서 옆 순수 함수 둘, PlanCard 의 선택 prop. `[id].vue` 의 바인딩 두 곳(계획 중 대기 카드 `:80-83`·승인 대기 PlanCard `:84-92`)은 06d 파일이라 06d 가 06c 머지 뒤 같은 함수로 잇는다(계획 머리 「다른 줄과의 경계·머지 문」). 06c 의 화면 변경은 어차피 10/17~18 nuxt 배포에 나가므로 미뤄서 잃는 것이 없다.

**Files:**
- Modify: `frontend/types/research.ts` (`StepResult` 73-93행 — `subquestions` 뒤에 선택 칸 셋)
- Modify: `frontend/utils/researchEvents.ts` (`planFromSteps` 723-725행 바로 뒤에 `questionUsedFromSteps`·`understoodLine`(내보냄)·`foldQuestion`(모듈 안))
- Modify: `frontend/components/research/PlanCard.vue` (header 4-7행의 `<h2>` 뒤 `<p>` 한 줄, script 54-61행 — import·props)
- Test: `frontend/tests/unit/researchEvents.test.ts` (import 17-36행, 파일 끝 1381행 뒤에 describe 셋)
- 고치지 않음: `frontend/pages/research/[id].vue`·`frontend/assets/css/research.css`(06d — §12-5)

**알아 둘 것:**
- **판단은 순수 함수 둘(정함 21):** node 환경 vitest(`vitest.config.ts` `environment: "node"`, `package.json` 에 `@vue/test-utils`·DOM 환경 없음)라 PlanCard 를 그려 보지 못한다 — '그릴지·숨길지·무슨 글을' 은 `questionUsedFromSteps`(null 이면 숨김)와 `understoodLine`(문구)이 정하고, PlanCard 는 prop 이 비지 않으면 `understoodLine(questionUsed)` 를 그대로 그린다. `.vue` 는 `nuxi typecheck` 오류 0 과 `npm run build` 로 본다. spec §12-2:512 의 'vitest 로 그리기·숨기기까지 검증' 과 다른 점은 마무리에서 spec 을 맞춘다(Task Z2 Step 3 ⑩).
- **`questionUsedFromSteps(steps, question)`(정함 21):** `latestOf(steps, "plan")?.result?.question_used`(재시도로 계획 단계가 여럿이면 seq 가 가장 큰 행 — `planFromSteps` 와 같은 고르기). 문자열이 아니면 null, 공백(줄바꿈 포함)을 한 칸으로 정리한 뒤 비었으면 null, NFKC·공백 정리 뒤 `question` 과 같으면 null, 아니면 **공백만 정리한** 넓힌 질문(NFKC 로 바꾸지 않은 서버 글)을 준다. 도는(`running`) 계획 단계의 중간 알림 result(`{"question_used", "terms"}` — Task C4·정함 6)도 같은 행이라 그대로 읽힌다. 마지막 계획 시도가 실패해 result 가 `{"error"}` 뿐이면 null — 앞 시도의 넓힌 질문을 보이지 않는다.
- **리듀서는 고치지 않는다:** `applyStep`(356-374행)은 이미 step 이벤트의 `result` 를 단계 행에 싣고, `subquestions` 가 없으면 `planFromSteps` 가 `[]` 라 계획이 비어 있다 — 중간 알림이 '계획을 안다' 로 바뀌지 않는다(서버 `_plan_known` 도 `subquestions` 만 본다 — Task C4 '알아 둘 것'). 이것을 describe `applyResearchEvent — 계획 중간 알림(06c)` 이 고정한다.
- **이름:** `planFromSteps` 는 내보내지 않는 모듈 함수다(723행 `function planFromSteps`) — 새 두 함수는 `export function` 이다. `questionUsedFromSteps`·`understoodLine` 은 다른 `utils/*.ts`·`composables/*` 에 없는 이름이라 Nuxt 자동 import 의 `Duplicated imports` 경고가 늘지 않는다(지금 경고는 `queueLine` 두 줄뿐 — 06b 이월, 06d 가 지운다).
- **PlanCard(정함 22):** 새 CSS 없이 `<p class="rs-muted rs-plan__understood">` — `rs-muted` 는 이미 6행이 쓰는 클래스다. `rs-plan__understood` 는 스타일이 없는 고리다 — 06d 는 같은 클래스 묶음을 계획 중 카드에도 달고 규칙은 더하지 않는다(`rs-muted` 로 줄이 맞는다). prop 은 `questionUsed?: string | null`(기본 `null`) — 지금 호출처(`[id].vue` 의 PlanCard 둘)는 이 prop 을 주지 않으므로 06c 만 머지된 화면은 지금과 같다.
- **타입(계획 머리 「다른 줄과의 경계·머지 문」의 plan step 결과 행):** `StepResult` 에 **선택(`?`)** 칸 셋 — `question_used?: string`·`terms?: string[]`·`elapsed_ms?: number`. 기존 픽스처를 깨지 않는다(`nuxi typecheck` 는 `tests/` 도 본다). 06d 는 이 셋을 다시 정의하지 않는다(같은 행).
- 네 파일 모두 CRLF — Edit 도구로.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `frontend/tests/unit/researchEvents.test.ts` import(17-36행). old:

```ts
  mergeEvidence,
  queueLine,
  refreshView,
  researchPhase,
  sectionGapToRecover,
  showsExcludedCounter,
  stopPoint,
  subqStatusLabel,
  synthClosePending,
  synthProgress,
  withPlan,
} from "~/utils/researchEvents";
```

new:

```ts
  mergeEvidence,
  questionUsedFromSteps,
  queueLine,
  refreshView,
  researchPhase,
  sectionGapToRecover,
  showsExcludedCounter,
  stopPoint,
  subqStatusLabel,
  synthClosePending,
  synthProgress,
  understoodLine,
  withPlan,
} from "~/utils/researchEvents";
```

② 같은 파일 끝(1381행 — `queueLine` describe 의 끝) 뒤. old:

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

const ASKED = "컴퓨팅 자원에 대한 연구가 궁금해";
const BROADENED = "클라우드·그리드 환경의 컴퓨팅 자원 관리에 대한 연구가 궁금해";

describe("questionUsedFromSteps — 이렇게 이해했어요(06c)", () => {
  it("넓힌 질문이 원 질문과 다르면 그 질문을 준다", () => {
    const done = step({
      result: { subquestions: ["클라우드 컴퓨팅 자원 할당"], question_used: BROADENED, terms: ["클라우드 컴퓨팅"], elapsed_ms: 3400 },
    });
    expect(questionUsedFromSteps([done], ASKED)).toBe(BROADENED);
    // 줄바꿈·겹친 공백은 한 칸으로 정리해 보인다
    const messy = step({ result: { question_used: `  클라우드·그리드 환경의\n컴퓨팅  자원 관리에 대한 연구가 궁금해 ` } });
    expect(questionUsedFromSteps([messy], ASKED)).toBe(BROADENED);
  });

  it("원 질문과 같으면 null — 공백·NFKC 차이만 있어도 같다(넓히기를 껐거나 실패한 잡)", () => {
    const off = step({ result: { subquestions: ["컴퓨팅 자원의 정의"], question_used: ASKED, terms: [], elapsed_ms: 700 } });
    expect(questionUsedFromSteps([off], ASKED)).toBeNull();
    expect(questionUsedFromSteps([step({ result: { question_used: " 컴퓨팅  자원에 대한 연구가 궁금해" } })], ASKED)).toBeNull();
    expect(questionUsedFromSteps([step({ result: { question_used: "ＡＩ 윤리 교육의 효과" } })], "AI 윤리 교육의 효과")).toBeNull();
  });

  it("question_used 가 없으면 null — 06c 전 잡·계획 단계 전", () => {
    expect(questionUsedFromSteps([step({ result: { subquestions: ["효과 측정"] } })], ASKED)).toBeNull();
    expect(questionUsedFromSteps([], ASKED)).toBeNull();
    // 보강 전 서버의 snapshot 행에는 result 가 없다
    expect(questionUsedFromSteps([step({ result: undefined })], ASKED)).toBeNull();
    expect(questionUsedFromSteps([step({ result: { question_used: "   " } })], ASKED)).toBeNull();
    // 계획 단계만 본다
    const search = step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", result: { question_used: BROADENED } });
    expect(questionUsedFromSteps([search], ASKED)).toBeNull();
  });

  it("계획 중(running) 단계의 중간 알림 result 도 읽는다", () => {
    const running = step({ status: "running", result: { question_used: BROADENED, terms: ["클라우드 컴퓨팅", "자원 할당"] } });
    expect(questionUsedFromSteps([running], ASKED)).toBe(BROADENED);
  });

  it("재시도로 계획 단계가 여럿이면 seq 가 가장 큰 행을 읽는다", () => {
    const older = step({ seq: 0, status: "failed", result: { question_used: "앞 시도의 넓힌 질문" } });
    const latest = step({ seq: 3, result: { subquestions: ["클라우드 컴퓨팅 자원 할당"], question_used: BROADENED } });
    expect(questionUsedFromSteps([latest, older], ASKED)).toBe(BROADENED);
    // 마지막 시도가 계획에서 실패하면(result 가 error 뿐) 앞 시도의 넓힌 질문을 보이지 않는다
    const failed = step({ seq: 5, status: "failed", result: { error: "계획 LLM 실패" } });
    expect(questionUsedFromSteps([older, latest, failed], ASKED)).toBeNull();
  });
});

describe("understoodLine", () => {
  it("'이렇게 이해했어요: …' 한 줄", () => {
    expect(understoodLine(BROADENED)).toBe(`이렇게 이해했어요: ${BROADENED}`);
  });
});

describe("applyResearchEvent — 계획 중간 알림(06c)", () => {
  it("subquestions 없는 running 계획 단계는 계획을 비운 채 두고 넓힌 질문을 단계 result 에 남긴다", () => {
    const planning = initialResearchView(job({ question: ASKED, status: "planning", stage: "created", plan: null }));
    const announced = applyResearchEvent(planning, {
      kind: "step", seq: 0, step_kind: "plan", subq_idx: null, title: "연구 계획 수립", status: "running",
      result: { question_used: BROADENED, terms: ["클라우드 컴퓨팅", "자원 할당"] },
    });
    expect(announced.plan).toEqual([]);
    expect(announced.subqs).toEqual([]);
    expect(researchPhase(announced)).toBe("planning");
    expect(questionUsedFromSteps(announced.steps, announced.question)).toBe(BROADENED);

    // 계획이 나오면 같은 단계가 하위질문과 함께 같은 넓힌 질문을 싣는다
    const plan = ["클라우드 컴퓨팅 자원 할당", "그리드 컴퓨팅 자원 관리"];
    const planned = applyResearchEvent(announced, {
      kind: "step", seq: 0, step_kind: "plan", subq_idx: null, title: "연구 계획 수립", status: "done",
      result: { subquestions: plan, question_used: BROADENED, terms: ["클라우드 컴퓨팅", "자원 할당"], elapsed_ms: 3400 },
    });
    expect(planned.plan).toEqual(plan);
    expect(questionUsedFromSteps(planned.steps, planned.question)).toBe(BROADENED);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx vitest run tests/unit/researchEvents.test.ts`

Expected: `Tests  7 failed | 102 passed (109)` — 새 it 일곱이 모두 `TypeError: (0 , questionUsedFromSteps) is not a function`(`understoodLine` describe 는 `(0 , understoodLine) is not a function`). vitest 는 타입을 검사하지 않으므로 `question_used` 칸이 아직 `StepResult` 에 없어도 테스트는 돈다. 기존 102개는 통과한다.

- [ ] **Step 3: 구현한다**

① `frontend/types/research.ts` `StepResult`. old:

```ts
export interface StepResult {
  subquestions?: string[];
  queries?: string[];
```

new:

```ts
export interface StepResult {
  subquestions?: string[];
  // 계획 단계(06c) — 계획에 넘긴 질문(넓히기를 껐거나 실패하면 원 질문)·범위 용어·넓히기와 계획에 걸린 시간(ms).
  // 넓히기가 끝나면 도는(running) 계획 단계 result 에 question_used·terms 만 먼저 실린다. 06c 전 잡에는 없다
  question_used?: string;
  terms?: string[];
  elapsed_ms?: number;
  queries?: string[];
```

② `frontend/utils/researchEvents.ts` — `planFromSteps` 바로 뒤. old:

```ts
function planFromSteps(steps: ResearchStepRow[]): string[] {
  return latestOf(steps, "plan")?.result?.subquestions ?? [];
}
```

new:

```ts
function planFromSteps(steps: ResearchStepRow[]): string[] {
  return latestOf(steps, "plan")?.result?.subquestions ?? [];
}

// 계획 카드 머리 "이렇게 이해했어요" 한 줄의 재료(06c) — 계획 단계가 계획에 넘긴 넓힌 질문. 원 질문과 같으면(넓히기를
// 껐거나 원 질문으로 물러난 잡) 보일 것이 없어 null 이다. 넓히기가 끝나면 도는(running) 계획 단계에도 실려 온다
export function questionUsedFromSteps(steps: ResearchStepRow[], question: string): string | null {
  const used = latestOf(steps, "plan")?.result?.question_used;
  if (typeof used !== "string") return null;
  const shown = used.replace(/\s+/g, " ").trim();
  if (!shown || foldQuestion(shown) === foldQuestion(question)) return null;
  return shown;
}

export function understoodLine(questionUsed: string): string {
  return `이렇게 이해했어요: ${questionUsed}`;
}

function foldQuestion(text: string): string {
  return text.normalize("NFKC").replace(/\s+/g, " ").trim();
}
```

③ `frontend/components/research/PlanCard.vue` 머리(4-7행). old:

```vue
      <h2 class="rs-card__title">{{ editable ? "연구 계획 확인" : "연구 계획" }}</h2>
      <p v-if="editable" class="rs-muted">
```

new:

```vue
      <h2 class="rs-card__title">{{ editable ? "연구 계획 확인" : "연구 계획" }}</h2>
      <p v-if="questionUsed" class="rs-muted rs-plan__understood">{{ understoodLine(questionUsed) }}</p>
      <p v-if="editable" class="rs-muted">
```

④ 같은 파일 script(54-61행). old:

```ts
import { subqStatusLabel } from "~/utils/researchEvents";
import { PLAN_ITEM_MAX, planProblem } from "~/utils/researchInput";

const props = withDefaults(
  defineProps<{ plan: string[]; max: number; editable?: boolean; busy?: boolean; subqs?: SubqView[] }>(),
  { editable: false, busy: false, subqs: () => [] },
);
```

new:

```ts
import { subqStatusLabel, understoodLine } from "~/utils/researchEvents";
import { PLAN_ITEM_MAX, planProblem } from "~/utils/researchInput";

// questionUsed — 계획이 쓴 넓힌 질문(06c). 원 질문과 같으면 null 로 받는다(판단은 questionUsedFromSteps)
const props = withDefaults(
  defineProps<{
    plan: string[];
    max: number;
    editable?: boolean;
    busy?: boolean;
    subqs?: SubqView[];
    questionUsed?: string | null;
  }>(),
  { editable: false, busy: false, subqs: () => [], questionUsed: null },
);
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx vitest run tests/unit/researchEvents.test.ts`

Expected: `Tests  109 passed (109)` (102 + 7)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx vitest run`

Expected: 실패 0. 파일 수는 Task 0 기준선 그대로(참고 기준선이면 `Test Files  40 passed (40)`), 테스트 수 = Task V3 앞 수 + 7(참고 기준선 732 에서 바로 하면 `Tests  739 passed (739)` — 같은 커밋 사본에서 실측). 파트 C 는 프론트 테스트를 더하지 않는다(Task C1 의 `term_checks.json` 은 vitest 가 읽지 않는다).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`

Expected: `0` (`<p v-if="questionUsed">` 안에서 `questionUsed` 가 `string` 으로 좁혀진다 — `understoodLine(max)` 처럼 잘못 넘기면 `PlanCard.vue(6,…): error TS2345` 로 잡히는 것을 같은 커밋 사본에서 확인했다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"`

Expected: `2` (기존 `queueLine` 두 줄뿐 — 새 이름이 자동 import 중복을 만들지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npm run build 2>&1 | tail -1`

Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git diff --stat HEAD -- "frontend/pages/research/[id].vue" frontend/assets/css/research.css`

Expected: 빈 출력 — 06d 파일은 고치지 않았다.

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add frontend/types/research.ts && git add frontend/utils/researchEvents.ts && git add frontend/components/research/PlanCard.vue && git add frontend/tests/unit/researchEvents.test.ts && git status --short && git commit -m "[Feat] round06c 프론트 — 계획 카드 머리에 '이렇게 이해했어요' 한 줄(PlanCard questionUsed·questionUsedFromSteps·understoodLine)을 더한다: questionUsedFromSteps 가 마지막 계획 단계 result 의 question_used(넓히기가 끝나면 도는 계획 단계에도 먼저 실린다)를 읽어 원 질문과 같으면(NFKC·공백 정리 뒤) null 을, 다르면 공백을 정리한 넓힌 질문을 준다. PlanCard 는 선택 prop questionUsed 가 있을 때만 그 줄을 그린다 — 새 CSS 없이 rs-muted, rs-plan__understood 는 스타일 없는 고리다(06d 가 계획 중 카드에 같은 클래스를 단다). StepResult 에 question_used·terms·elapsed_ms 선택 칸. 그리기·숨기기 판단은 순수 함수 vitest 로, PlanCard 는 typecheck·build 로 본다. [id].vue 바인딩(계획 중 대기 카드·승인 대기 PlanCard)은 06d"
```

---

---

### Task Z1: 전체 회귀·정적 리뷰·반영

**왜:** 파트 C·V 를 모두 마친 브랜치를 dev 에 넣기 전에 한 번에 회귀를 보고, 영역별 정적 리뷰(`.claude/agents/code-reviewer.md`)로 이 줄의 위험(스위치 0 의 글자 그대로·넓히기 실패 타입·트랜잭션·06d 계약·프롬프트 예시·바꾸지 않을 파일)을 확인한다(GIT_WORKFLOW — 리뷰 뒤 dev 머지). 리뷰 반영도 이 Task 안에서 끝내고 '리뷰를 마친 커밋'을 적는다 — 완료노트·dev 머지가 이 커밋을 가리킨다.

**Files:**
- Modify: 리뷰 발견을 고치는 파일(발견에 따라 — 각 수정은 테스트를 먼저 쓰고 고친다)
- 저장소 밖 작업 폴더: `C:/Users/LANDSOFT/round06c-eval/review/`(리뷰어에게 줄 diff — 저장소에 넣지 않는다)

**알아 둘 것:**
- code-reviewer 는 읽기 전용(Read·Grep·Glob)이라 git 을 돌리지 못한다 — 영역 diff 를 파일로 떠서 경로를 준다.
- 리뷰 반영 커밋도 `[Fix] round06c — …` 처럼 Co-Authored-By 없이 쓴다. 발견을 거절할 때는 까닭을 완료노트 §3 에 적는다(Task Z2).

- [ ] **Step 1: 전체 회귀**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: `5 failed, N passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 Task 0 기준선과 같은 세 파일(test_build_manifest 2·test_loaders 3·test_book_chat 수집). N 은 계획 순서상 마지막으로 끝낸 백엔드 Task(C7 또는 V2)의 '전체' 기대값과 같다(= 기준선 2327 + 파트 C·V 가 더한 테스트 수 — 이 Step 은 테스트를 더하지 않는다). 조립 순서(C1→C7→V1→V3)대로면 `5 failed, 2451 passed, 1 skipped, 2 warnings, 1 error`(2327 + 파트 C 110 + Task V1 7 + Task V2 7 — Task V3 은 프론트만이다). Task 0 기준선이 2327 과 다르면 그 차이만큼 옮겨 읽는다. 옮겨 읽은 값과도 다르면 Task 별 '통과 확인' 명령으로 어느 파일의 수가 다른지 센다. 나온 N 을 적어 둔다(완료노트 §4).

Run(06c 묶음 열두 파일): `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_terms.py tests/test_research_framing.py tests/test_research_state.py tests/test_research_api.py tests/test_research_tasks.py tests/test_research_runner.py tests/test_research_eval.py tests/test_research_planner.py tests/test_prompts.py tests/test_research_critic.py tests/test_research_explorer.py tests/test_research_synthesizer.py -q -p no:cacheprovider`

Expected: 실패 0. `M passed, 2 warnings` — M = Task 0 의 열 파일 653 + 파트 C·V 가 이 열두 파일에 더한 수(`test_research_terms.py`·`test_research_framing.py` 는 파일 전체). `test_research_planner.py`·`test_prompts.py`·`test_research_critic.py`·`test_research_explorer.py`·`test_research_synthesizer.py` 는 기준선 수 그대로다(18·9·70·26·111). 계획대로면 **M = 777**(653 + 124 — terms 35 · framing 27 · state 94 · api 124 · tasks 118 · runner 98 · eval 47 · planner 18 · prompts 9 · critic 70 · explorer 26 · synthesizer 111). Task 0 의 열 파일 기준선이 653 과 다르면 그 차이만큼 옮겨 읽는다. M 을 적어 둔다(Task Z7 이 다시 쓴다).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/frontend && npm run build 2>&1 | tail -1
```

Expected: typecheck `0` · vitest `Test Files  40 passed (40)` 과 Task V3 '통과 확인' 의 `Tests` 수(732 + V3 가 더한 수 — 파일 수는 V3 가 기존 파일에 더하므로 40 그대로. 계획대로면 `Tests  739 passed (739)` = 732 + 7, Task 0 기준선이 732 와 다르면 그 차이만큼 옮겨 읽는다) · `└  ✨ Build complete!`. 값을 적어 둔다.

- [ ] **Step 2: 경계·바꾸지 않을 파일·프롬프트·커밋 트레일러**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
BASE=$(git merge-base HEAD dev); echo "$BASE"
git diff --name-only $BASE HEAD -- app frontend scripts | LC_ALL=C sort
git diff --stat $BASE HEAD -- app/services/research/planner.py app/domains/nl_library/prompts/research_plan.yaml app/domains/nl_library/prompts/research_critique.yaml app/domains/nl_library/prompts/research_critique_question.yaml app/domains/nl_library/prompts/research_synthesize.yaml app/api/research.py app/tests/test_research_planner.py app/services/research/critic.py app/services/research/explorer.py app/services/research/synthesizer.py app/services/search/pipeline.py "frontend/pages/research/[id].vue" frontend/pages/index.vue frontend/assets/css/research.css frontend/assets/css/work.css frontend/components/work frontend/components/AppSidebar.vue app/services/research_work app/api/research_work.py app/api/research_topics.py app/api/research_reading.py app/api/research_proposal.py app/api/history.py app/alembic infra docker-compose.yml docker-compose.dev.yml
grep -cE "예:|예시|guided_" app/domains/nl_library/prompts/research_frame.yaml
grep -n "except Exception" app/services/research/framing.py app/services/research/terms.py
grep -nE "^(from|import) " app/services/research/terms.py
git log $BASE..HEAD --format=%B | grep -ciE "Co-Authored-By|Generated with Claude Code"
git status --short
```

Expected:
- `BASE` — Task 0 Step 2 의 dev 커밋
- 고친 파일 목록 — 정확히 다음 23줄(리뷰 반영으로 더한 파일이 있으면 그 파일과 까닭을 완료노트 §3 에 적는다. 이 계획서를 브랜치에 커밋했으면 `docs/` 라 이 목록에 들지 않는다):

```text
app/domains/nl_library/prompts/research_frame.yaml
app/models/research.py
app/services/research/framing.py
app/services/research/runner.py
app/services/research/state.py
app/services/research/terms.py
app/tests/test_research_api.py
app/tests/test_research_eval.py
app/tests/test_research_framing.py
app/tests/test_research_runner.py
app/tests/test_research_state.py
app/tests/test_research_tasks.py
app/tests/test_research_terms.py
app/workers/research_tasks.py
frontend/components/research/PlanCard.vue
frontend/tests/fixtures/term_checks.json
frontend/tests/unit/researchEvents.test.ts
frontend/types/research.ts
frontend/utils/researchEvents.ts
scripts/research_eval/README.md
scripts/research_eval/questions_control.json
scripts/research_eval/run_pair.py
scripts/research_eval/score.py
```

- 바꾸지 않을 파일 `diff --stat` — 빈 출력(계획 프롬프트·planner·계획 고정 테스트·critic/종합 프롬프트(sha256)·API·critic·explorer·synthesizer·검색 파이프라인·06d·06e 파일·마이그레이션·인프라·compose)
- 프롬프트 금지 문자열 — `0`(함정 15·25)
- `except Exception` — 빈 출력(종료 코드 1 은 맞는 줄이 없을 때의 정상 값 — 함정 19)
- `terms.py` import — 표준 라이브러리 줄만(`re`·`unicodedata`·`collections.abc`, 있으면 `from __future__ import annotations`). 06e 가 import 하므로 app 모듈을 끌어오지 않는다
- 트레일러 — `0`(종료 코드 1 은 정상. Git Bash 의 grep 은 `-i` 와 `-e` 여럿을 함께 주면 죽으므로 `-E` 한 패턴으로 쓴다)
- `git status --short` — 빈 출력

- [ ] **Step 3: 영역별 정적 리뷰 — code-reviewer 다섯을 병렬로**

리뷰어에게 줄 diff 를 저장소 밖에 뜬다:

```bash
mkdir -p C:/Users/LANDSOFT/round06c-eval/review
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
BASE=$(git merge-base HEAD dev)
git diff $BASE HEAD -- app/services/research/terms.py app/services/research/framing.py app/domains/nl_library/prompts/research_frame.yaml app/services/research/state.py app/workers/research_tasks.py app/models/research.py > C:/Users/LANDSOFT/round06c-eval/review/a-broaden.diff
git diff $BASE HEAD -- app/services/research/runner.py > C:/Users/LANDSOFT/round06c-eval/review/b-query-candidates.diff
git diff $BASE HEAD -- scripts/research_eval frontend/tests/fixtures/term_checks.json > C:/Users/LANDSOFT/round06c-eval/review/c-eval-tools.diff
git diff $BASE HEAD -- frontend/types/research.ts frontend/utils/researchEvents.ts frontend/components/research/PlanCard.vue frontend/tests/unit/researchEvents.test.ts > C:/Users/LANDSOFT/round06c-eval/review/d-frontend.diff
git diff $BASE HEAD -- app/tests > C:/Users/LANDSOFT/round06c-eval/review/e-tests.diff
wc -l C:/Users/LANDSOFT/round06c-eval/review/*.diff
```

Expected: 다섯 파일 모두 0 줄이 아니다.

`.claude/agents/code-reviewer.md` 서브에이전트(subagent_type `code-reviewer`) 다섯을 **한 번에 병렬로** 띄운다. 각 프롬프트는 아래 공통 머리 + 영역 줄이다.

공통 머리(그대로):

```text
round06c(딥리서치 시작 질문 넓히기·검색어 합성·탐색 후보 이벤트) 브랜치의 한 영역을 정적 리뷰한다. 저장소 C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c 의 파일과 아래 diff 파일을 읽는다. 설계 정본은 docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md §12-2·§12-5·§12-7 과 D25, 이 줄의 결정은 docs/superpowers/plans/2026-10-08-round06c-query-broadening.md 의 '06c 에서 정한 것'(정함 1~22) — 정함 7·10·21 은 spec 과 일부러 다르고, 정함 9(넓힌 질문의 입력 이름표 떼기)·12(compose_query 규칙)는 spec 보다 자세하다(문서는 나중에 맞춘다). 반복 함정 docs/ops/recurring-gotchas.md 13·14·15·18·19·25·26 과 대조한다. 공통으로 본다: ① 스위치(broaden·query_context)가 0 이면 계획 입력(make_plan 에 넘기는 질문 = job.question)과 검색어(subq.text·critic 제안 글자)가 지금과 글자 그대로이고, 계획 단계는 완료 result 의 칸만 늘며, 탐색 이벤트는 회차마다 counters 뒤 candidates 하나만 는다 ② 실패 처리는 실제로 나는 타입만 잡는다 — except Exception 이 없고 SoftTimeLimitExceeded 를 삼키지 않는다 ③ LLM 을 기다리는 동안 읽기 트랜잭션이 열려 있지 않다 ④ 스키마 변경이 없다(JSONB·잡 파라미터 안 모양만) ⑤ 스위치 값에 따라 결과가 달라지는 테스트는 기본값({})에 기대지 않고 값을 적는다(결과가 스위치와 무관한 테스트는 적지 않아도 된다) — 기본값을 단언하는 테스트는 test_query_switches_are_off_by_default·test_query_switches_are_saved_off_unless_asked 둘뿐이어야 한다. 보고는 code-reviewer 형식(severity·location·issue·suggestion), 읽은 근거만.
```

영역 줄(공통 머리 뒤에 하나씩):

```text
[A 넓히기] diff: C:/Users/LANDSOFT/round06c-eval/review/a-broaden.diff. 파일: app/services/research/terms.py, framing.py, app/domains/nl_library/prompts/research_frame.yaml, app/services/research/state.py, app/workers/research_tasks.py(_plan_deep_research·_plan_terms·_run_deep_research), app/models/research.py. 특히: terms.py 가 표준 라이브러리만 쓰고 content_words·contains·compose_query 가 정함 7·8·12 와 같은지(compose_query 를 두 번 거쳐도 같은지, 제외할 뜻을 붙이지 않는지), framing 의 FRAME_FAILURES·BROADEN_TIMEOUT 20·모델 인자 없음(gemma)·원 질문 낱말 보존 검사·terms 정리(정함 9)·원 질문을 그대로 낸 답도 정상(함정 26), 프롬프트에 예시·guided_* 가 없는지(함정 15·25), 계획 태스크가 broaden 1 일 때만 넓히고 중간 알림을 한 번 내는지, make_plan 이 framing.question 을 받고 job.question·job.plan 은 그대로인지, 완료 result 가 {subquestions, question_used, terms, elapsed_ms}인지, _plan_terms 가 select(ResearchStep.result)…order_by(seq desc).limit(1) 을 .scalar_one_or_none() 으로 받고 LLM 전에 같은 읽기 트랜잭션에서 읽는지, 되살린 잡은 스냅숏의 terms 를 덮지 않는지, ResearchState.terms 의 스냅숏 왕복과 옛 스냅숏([]).
[B 검색어 합성·후보 이벤트] diff: C:/Users/LANDSOFT/round06c-eval/review/b-query-candidates.diff. 파일: app/services/research/runner.py(읽기만: critic.py:200-216, explorer.py:98-115). 특히: _search_query 한 곳이 첫 검색어와 _recheck_query 의 제안에 쓰이고 _next_query 는 그대로인지, subq.queries·회차 query·next_query·search 이벤트 query·critic tried_queries 가 모두 실제로 보낸 합성 글인지, 절 소제목·critic 의 subq.text·핵심 개념 입력은 원문인지, candidates 가 counters 뒤·critique_fn 앞에 회차마다 한 번이고 모양이 {"subq_idx", "round", "papers": [_paper_brief…]}(06d 계약 — spec §12-2 의 'subq_idx, round, papers')인지, linked 순서·빈 목록·제외/예산으로 못 이은 논문은 빠지는지, rounds·스냅숏·step result 에 넣지 않는지.
[C 판정 도구] diff: C:/Users/LANDSOFT/round06c-eval/review/c-eval-tools.diff. 파일: scripts/research_eval/run_pair.py, score.py, questions_control.json, README.md, frontend/tests/fixtures/term_checks.json. 특히: 기본 인자만 주면 run_pair 의 동작이 06c 전 그대로인지(갈래 0 critic_scope 0·갈래 1 critic_scope 1·갈래 1 은 갈래 0 계획으로 승인 — 출력 머리에 갈래 파라미터·계획 모드 한 줄만 는다, 정함 16), --param0·--param 이 JSON 객체가 아니면 HTTP 없이 2 를 돌려주는지, --plan own 이면 갈래 1 을 본문 없이 승인하는지, score 의 기존 출력 글자(합격 질문·절별 무관·과잉 제외·보고서 정밀도·두 합계 줄)가 한 자도 바뀌지 않았는지, 계획 지표(일반 틀 — 원 질문에 든 측면 낱말 제외·근거 0편·insufficient·계획 시간 elapsed_ms)와 --plan-only, contains 복사본이 공용 고정 예제를 통과하는지, score 가 app 을 import 하지 않는지, cp949 콘솔에서 깨지지 않는지, README 의 06c 재판정 명령이 계획 Task Z6 과 같은지.
[D 화면 한 줄] diff: C:/Users/LANDSOFT/round06c-eval/review/d-frontend.diff. 파일: frontend/types/research.ts, utils/researchEvents.ts, components/research/PlanCard.vue, tests/unit/researchEvents.test.ts. 특히: StepResult 의 새 칸이 모두 선택(?)인지, questionUsedFromSteps 가 마지막 plan 단계(seq 가 가장 큰 행 — running 의 중간 알림 포함)를 읽고 NFKC·공백 정리 뒤 원 질문과 같으면 null 인지, understoodLine 문구가 '이렇게 이해했어요: …' 인지, PlanCard 의 questionUsed 가 선택 prop(기본 null)이고 새 CSS 없이 rs-muted·rs-plan__understood 인지, [id].vue·research.css 를 고치지 않았는지(06d 몫), 새 export 이름이 다른 utils 와 겹쳐 Nuxt 자동 import 경고를 늘리지 않는지.
[E 테스트] diff: C:/Users/LANDSOFT/round06c-eval/review/e-tests.diff. 파일: app/tests/test_research_terms.py, test_research_framing.py, test_research_state.py, test_research_api.py, test_research_tasks.py, test_research_runner.py, test_research_eval.py. 특히: 새 기능마다 실패 테스트가 먼저 있는지(TDD), 대역 패턴(_stub_missing·_FakeSession·_patch_pipeline·_Harness·MockTransport)을 새로 만들지 않고 썼는지, async 를 asyncio.run 으로 도는지(@pytest.mark.asyncio 없음), TestPlan._patch 가 넓히기를 늘 대역으로 바꿔 기본값이 1 이 돼도 진짜 chat 을 부르지 않는지, _patch_pipeline 이 _plan_terms 를 대역으로 바꾸는지, 고친 기존 테스트는 둘뿐인지 — Task C2 의 test_default_params_key_set_is_fixed(키 집합에 두 칸)와 Task C7 의 test_counters_follow_each_search(기대 순서). 고친 도우미는 _Harness(framed 칸)·TestPlan._patch(frame=)·_patch_pipeline(terms=·_plan_terms 대역)뿐인지, 스위치 값에 따라 결과가 달라지는 테스트가 값을 적는지(공통 ⑤).
```

Expected: 리뷰어마다 요약 1~2문장 + 결함 목록(없으면 "없음"). 다섯 보고를 영역·severity 별로 한 표로 모은다(완료노트 §3 의 재료).

- [ ] **Step 4: 발견을 반영하고 리뷰를 마친 커밋을 적는다**

- severity high·medium 은 모두 고친다. low 는 고칠지 판단하고, 고치지 않으면 까닭을 적는다(완료노트 §3). 리뷰어끼리 엇갈리거나 계획의 결정(정함 1~22)과 다른 제안은 고치기 전에 그 결정의 근거와 견주고, 결정을 바꿔야 하면 사용자에게 묻는다.
- 동작을 바꾸는 수정은 실패 테스트를 먼저 쓰고(실행해 실패 확인) 고친 뒤 통과를 본다. 커밋은 발견 묶음마다 `[Fix] round06c — <무엇을 왜>` 로, `git add` 는 파일을 하나씩 적는다.
- 다 고친 뒤 Step 1·Step 2 를 그대로 다시 돌린다. Expected: Step 1 의 N·M·vitest 수는 리뷰 반영으로 더한 테스트만큼 크고 나머지는 같다, Step 2 의 출력은 같다(고친 파일 목록에 새 파일이 들었으면 그 까닭이 적혀 있다).
- 그 뒤 고친 것만 해당 영역 리뷰어에게 다시 보인다(같은 공통 머리 + "앞 리뷰의 발견을 고친 diff 다 — 회귀가 없는지 본다", diff 는 `git diff <반영 전 커밋> HEAD`). 새 발견이 없을 때까지 되풀이한다(최대 3회 — 넘으면 남은 발견을 사용자에게 보인다).

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c rev-parse --short HEAD
```

Expected: 커밋 해시 한 줄 — '리뷰를 마친 커밋'으로 적어 둔다(완료노트 머리·§3, Task Z3 의 승인 요청).

---

### Task Z2: 문서 — 완료노트(배포 전)·00_status·spec 맞춤·반복 함정 판단

**왜:** D13(하위 라운드마다 완료노트), CLAUDE.md §3("문서와 코드가 어긋나면 코드가 실제이니 문서를 고친다"). 06c 는 spec 과 일부러 다르게 정한 셋(정함 7·10·21)과 spec 보다 자세히 정한 규칙(정함 9 의 입력 이름표 떼기·정함 12 의 `compose_query` 규칙), spec 이 '예'로 둔 이름(`framing.py`·`research_frame.yaml`·`compose_query`)·더한 칸(`elapsed_ms`)·판정 도구 옵션이 있다 — dev 머지 전에 spec 을 코드에 맞춘다(후보 이벤트의 이름·키는 계획 확정 전에 이미 맞췄다 — Task 0 Step 1). 배포·판정 결과(§5)는 Task Z8 이 채운다.

**Files:**
- Create: `docs/roadmap/round06c-완료노트.md`
- Modify: `docs/roadmap/00_status.md`(3행 최종 갱신·22행 round06 머리·26행 뒤 06c 하위 줄·53행 다음 할 일의 06c 줄·82행 라운드 이력 — round06 줄만)
- Modify: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`(3행 머리 상태 줄, 47행 D25, §12-2 491·497·501·502·506·507·512·518·520행, §12-7 723·724·733·738행)
- `docs/ops/recurring-gotchas.md` — 이 Task 에서는 고치지 않는다(운영 전이라 라이브에서만 드러난 것이 아직 없다. Task Z8 이 다시 판단한다)

**알아 둘 것:**
- 기존 문서는 **Edit 도구로** 고친다(모두 CRLF). 아래 old 는 `c5d05b0`(spec 브랜치 — Task 0 Step 1 이 dev 에 있는지 본 커밋) 글자 그대로이고, 줄 번호도 그 판이다(old 마다 그 파일에 한 번만 나온다 — 2026-10-08 실측). 그 뒤 계획 확정 커밋이나 다른 줄이 같은 줄을 먼저 고쳤으면 old 가 맞지 않는다 — 그때는 지금 줄을 바탕으로 같은 구절만 넣는다.
- `00_status.md` 는 round06 에 관한 줄만 고친다(3행은 모든 라운드가 함께 고치는 줄 — 06c 구절만 넣는다).
- 날짜는 이 Task 를 하는 날로 쓴다(아래 예는 계획 일정의 2026-10-13).

- [ ] **Step 1: 완료노트를 쓴다 (`docs/roadmap/round06c-완료노트.md`, 새 파일)**

꺾쇠 자리는 Task Z1 에서 실측한 값과 이 Step 을 하는 날로 바꿔 쓰고 꺾쇠를 남기지 않는다 — 다 쓴 뒤 `grep -c '<[^>]*>' "docs/roadmap/round06c-완료노트.md"` 가 `0` 이다. §5 는 배포 뒤 Task Z8 에서 채운다.

```markdown
# round06c 완료노트

날짜: <이 Step 을 하는 날, 예: 2026-10-13> (계획 2026-10-08 · 구현·리뷰 <구현을 시작한 날>~<Task Z1 을 마친 날> · `dev` 머지·운영 배포·두 갈래 재판정은 §5)
브랜치: `feat/round06c-query-broadening` (worktree `.worktrees/round06c`, dev `<Task 0 Step 2 의 dev 커밋 7자리>` 에서 분기 · 커밋 <git rev-list --count 그 커밋..HEAD 의 수>개 · 리뷰를 마친 커밋 `<Task Z1 Step 4 의 커밋>`)
spec: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` (D25, §12-2·§12-5·§12-6·§12-7, Q4·Q9)
plan: `docs/superpowers/plans/2026-10-08-round06c-query-broadening.md` (Task 0 · C1~C7 · V1~V3 · Z1~Z9, 정함 1~22)
교본: 대회 뒤 round06 한 권(D13) — 06c 는 그 책의 한 장이 된다

> 한 줄 요약: 딥리서치 계획 직전에 gemma 한 번으로 시작 질문을 한 문장으로 넓히고 범위 용어를 뽑아(스위치 `broaden`) 계획 프롬프트는 그대로 둔 채 입력만 넓혔고, 검색어에 범위 용어를 합성하고 '국내 학술논문에서'를 떼게 했다(스위치 `query_context`). 회차마다 자기점검 전에 탐색 후보 목록 이벤트 `candidates` 를 낸다(06d '검토 중' 더미의 재료). 두 스위치는 기본 0 으로 배포하고 배포 당일 두 갈래 판정으로 기본값을 정한다(§5). 스키마 변경은 없다.

---

## 1. 왜 했나

- **일반 틀 하위질문** — 개념 하나짜리 짧은 질문은 계획 프롬프트의 측면 목록(개념·정의, 방법·기법, 적용 분야, 성과·평가, 한계·과제)을 그대로 옮긴다. 06b 계획 30개 중 약 25개가 그랬다(spec §12-2). 논문 상세 [이 논문으로 딥리서치] 질문은 실제 제목·키워드·측면이 있어 잘 나뉜다 — 그 일을 계획 전에 자동으로 한다(회의 결정 ⑥, D25).
- **검색어의 동음이의** — 06b 재판정에서 남은 무관은 하위질문 문장이 아니라 검색어가 데려왔다('컴퓨팅' 사고력·무선 자원할당 — 06b 이월 §7-10·§7-11). D18 의 부작용으로 하위질문에 붙은 '국내 학술논문에서' 도 검색어에 섞였다(§7-12). 검색어에 범위 용어를 합성한다(회의 결정 ⑦, 사용자 결정 2026-10-08 "06c에 검색어 합성 넣어").
- **탐색 후보 목록(Q9)** — 회차마다 검토하는 후보를 화면이 '검토 중' 으로 먼저 세우게, runner 가 이벤트를 낸다(화면은 06d).

---

## 2. 한 일

| 영역 | 한 것 |
|---|---|
| 낱말 맞추기 | `app/services/research/terms.py` — `content_words`(NFKC·casefold·문장부호·조사 하나 떼기·질문 꼴 낱말과 조사만 남은 어절 제외)·`contains`(공백 무시 부분 문자열, 아니면 낱말이 순서대로)·`compose_query`, 상수 `PARTICLES`·`QUESTION_WORDS`·`QUERY_FILLERS`. 공용 고정 예제 `frontend/tests/fixtures/term_checks.json`(score.py 복사본·06e 가 같은 규칙) |
| 넓히기 | `research_frame.yaml`(예시 없음)·`framing.py` — gemma 1회·20초, 원 질문 낱말 보존 검사, 범위 용어 정리(30자·4개), `FRAME_FAILURES`·빈 응답·검사 실패면 원 질문. 계획 태스크가 `broaden` 1 이면 계획 전에 넓히고 `{question_used, terms}` 를 먼저 알린다. plan step 결과 `{subquestions, question_used, terms, elapsed_ms}` |
| 검색어 합성 | 실행 태스크가 마지막 plan step 의 `terms` 를 `ResearchState.terms`·체크포인트에 싣는다. runner `_search_query` 가 `query_context` 1 이면 첫 검색어·재검색 제안에 없는 범위 용어를 붙이고 '국내 학술논문에서' 를 뗀다 — `subq.queries`·critic `tried_queries`·회차 기록이 모두 실제로 보낸 글 |
| 탐색 후보 이벤트 | `candidates {subq_idx, round, papers}` — 회차마다 `counters` 뒤·자기점검 전에 한 번(빈 목록도), 스위치와 무관, 저장하지 않음 |
| 스위치 | 잡 파라미터 `broaden`·`query_context`(int 0~1, 기본 0 — `critic_scope` 와 같은 검증 경로) |
| 판정 도구 | `run_pair.py --param0·--param·--plan own`, 대조군 `questions_control.json`, `score.py` 계획 지표(넓힌 질문·일반 틀·근거 0편·insufficient·계획 시간)·`--plan-only`·`contains` 복사본, README '06c 재판정' 절차 |
| 화면 한 줄 | `StepResult` 선택 칸 셋, `questionUsedFromSteps`·`understoodLine`, PlanCard 선택 prop `questionUsed`(`[id].vue` 바인딩은 06d — 10/17~18 nuxt 배포) |

스키마 변경 없음 — 바뀐 모양은 plan step result(JSONB)·잡 파라미터·체크포인트 안이다. `planner.py`·`research_plan.yaml`·`parse_plan`·계획 고정 테스트·`job.plan`·승인 API·critic·explorer·synthesizer·검색 파이프라인·critic/종합 프롬프트(sha256)·06d·06e 파일·compose·인프라는 그대로다.

---

## 3. 리뷰

작업마다 구현 → spec 준수 → 품질 검토를 돌렸고, 끝에 영역 다섯(넓히기·검색어 합성과 후보 이벤트·판정 도구·화면 한 줄·테스트)의 정적 리뷰(`.claude/agents/code-reviewer.md`)를 병렬로 돌렸다. 테스트 영역은 고친 기존 테스트가 둘뿐인지 — Task C2 의 `test_default_params_key_set_is_fixed`(키 집합에 두 칸)와 Task C7 의 `test_counters_follow_each_search`(기대 순서) — 와 고친 도우미가 `_Harness`(`framed` 칸)·`TestPlan._patch`(`frame=`)·`_patch_pipeline`(`terms=`·`_plan_terms` 대역)뿐인지, 스위치 값에 따라 결과가 달라지는 테스트는 기본값(`{}`)에 기대지 않고 값을 적는지를 봤다. <영역별 발견 수(high·medium·low)와 반영 커밋 수·주요 수정 — 예: 'medium 2 · low 5, 수정 3커밋: …'>. <고치지 않은 발견과 까닭, 없으면 '거절한 발견 없음'>. 넘긴 것은 §7.

---

## 4. 검증

- 백엔드 pytest `5 failed, <Task Z1 Step 4 의 N> passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 Task 0 기준선과 같은 로컬 의존성 파일(test_build_manifest·test_loaders·test_book_chat). 기준선 2327.
- 06c 묶음 열두 파일 <Task Z1 Step 4 의 M> passed(기준선 열 파일 653).
- 프론트 vitest 40파일 <Task Z1 Step 4 의 수> · `nuxi typecheck` 오류 0 · `npm run build` 완료(<이 Step 을 하는 날>, dev 머지 전 — 기준선 40파일 732).
- 고친 파일 23개 밖은 그대로(계획 프롬프트·planner·계획 고정 테스트·critic/종합 프롬프트·API·critic·explorer·synthesizer·검색 파이프라인·06d·06e 파일·마이그레이션·인프라·compose diff 없음), 프롬프트에 예시·`guided_*` 없음, `except Exception` 없음, 커밋 트레일러 0.

---

## 5. `dev` 머지·운영 배포·재판정

배포 전 — 계획 Task Z3~Z7 의 결과를 Task Z8 의 기록 브랜치에서 채운다.

---

## 6. 결정

| # | 결정 |
|---|---|
| 정함 1 | 넓히기는 새 모듈 `framing.py` — `planner.py` 는 한 글자도 고치지 않는다(계획 태스크가 함수 안에서 import) |
| 정함 2 | 프롬프트 `research_frame.yaml` — plain·max_tokens 600·temperature 0.2, 변수 `question`, 출력 `{"question", "terms"}`, 예시 없음 |
| 정함 3 | 탐색 후보 이벤트 이름 `candidates`, 하위질문 키 `subq_idx`(runner 의 다른 이벤트와 같은 키 — spec §12-2 를 계획 확정 전에 맞춤) |
| 정함 4 | `candidates` 는 회차마다 늘 한 번(빈 목록도) — `search` → `counters` → `candidates` → `critique`. 기존 순서 테스트 하나(`test_counters_follow_each_search`)의 기대를 고쳤다 |
| 정함 5 | plan step 결과에 `elapsed_ms`(넓히기 + 계획) |
| 정함 6 | 중간 알림은 `broaden` 1 일 때만, 넓히기 결과와 무관하게 한 번 |
| 정함 7 | `content_words` — 문장부호를 공백으로, 조사만 남은 어절은 내용어가 아니다(spec 정의에 더함 — §12-2 를 맞췄다) |
| 정함 8 | `contains` 는 spec 글자 그대로(06e 제목 일치가 같은 함수) |
| 정함 9 | 범위 용어 정리(문자열·NFKC·공백·빈 것과 30자 초과 버림·casefold 중복 제거·4개), 넓힌 질문이 비었거나 500자 초과면 원문. 넓힌 질문은 맨 앞 입력 이름표(`질문:`·`질문：`)를 떼고 본다(이름표째 옮긴 답이 낱말 검사를 통과하지 않게 — 함정 26). 낱말 검사는 `content_words` 에 더해 원 질문의 한 글자 어절(암·뇌·법 — 2자 바닥에 걸린다. 및·등·왜·더·수·것 같은 잇는 말은 빼고)도 본다 — 한 글자는 부분 문자열이 아니라 어절 경계로(그 글자이거나 그 글자 + 조사 하나, '방법'의 '법'은 아니다)(C3 품질 검토 — '암 연구가 궁금해'에 지어낸 주제가 지나가지 않게) |
| 정함 10 | 넓히기가 원문으로 물러나는 범위 = `FRAME_FAILURES`(전송·상태·JSON·응답 모양 오류)·빈 응답·검사 실패, 그 밖의 예외는 계획 실패(함정 19 — spec 의 '잡을 실패시키지 않는다' 를 맞췄다) |
| 정함 11 | 검색어 합성은 runner `_search_query` 한 곳(첫 검색어·재검색 제안), `_next_query` 그대로 |
| 정함 12 | `QUERY_FILLERS`·`compose_query` 도 `terms.py` — 붙일지는 지금까지의 글(이어 붙인 용어 포함)에 `contains` 인지로, 군더더기만 남으면 원문, 빈 용어는 건너뜀(두 번 거쳐도 같다 — 군더더기만으로 된 글은 예외. spec §12-2 를 맞췄다) |
| 정함 13 | `state.terms` 는 스위치와 무관하게 늘 담고, 검색어에는 `query_context` 1 일 때만 |
| 정함 14 | score.py 는 `contains` 만 복사(공용 고정 예제로 묶음) |
| 정함 15 | 공용 고정 예제 `frontend/tests/fixtures/term_checks.json` |
| 정함 16 | run_pair `--param0`·`--param`·`--plan shared\|own` — 기본값은 06c 전 동작 그대로 |
| 정함 17 | score `--plan-only`(대조군 — 라벨 없이 계획 지표) |
| 정함 18 | 대조군 질문 파일 `questions_control.json`(소장 논문 제목 2개, 논문 버튼 꼴) — 고정 5문항에 섞지 않는다 |
| 정함 19 | 계획 p50 5초는 판정 지표로만, 코드 상한 `BROADEN_TIMEOUT = 20` |
| 정함 20 | 스위치를 나눠 판정 — `query_context` = shared + 갈래 1 `{broaden 1, query_context 1}`, `broaden` = own + 갈래 1 `{broaden 1, query_context 0}` |
| 정함 21 | 화면 판단은 순수 함수 `questionUsedFromSteps`·`understoodLine` 의 vitest, PlanCard 는 typecheck·build(node 환경 vitest — spec 의 '그리기·숨기기 vitest' 를 맞췄다) |
| 정함 22 | PlanCard 는 새 CSS 없이 `rs-muted`, `rs-plan__understood` 는 규칙 없는 고리(06d 도 규칙을 더하지 않는다) |

§12-11 '계획에서 정할 것' — 06c 에 걸린 항목은 없다(10항목 모두 06d·06e). 선택 항목 '연구 맥락을 반영한 딥리드 첫 화면'은 하지 않았다. 열린 질문 Q4(기본값)는 §5 의 판정으로 닫는다.

---

## 디자인 참조

해당 없음 — 디자인 트랙 미도입. 06c 의 화면 변경은 PlanCard 머리 한 줄(`rs-muted` 재사용)뿐이고 `rs-plan__understood` 는 규칙 없는 고리다(06d 도 CSS 를 더하지 않는다).

---

## 7. 이월

1. **넓힌 문장을 고쳐 같은 잡에서 다시 계획하기** — 대회 뒤(사용자 "고도화로 냅두고", spec §12-9). `awaiting_approval → created` 전이와 `_plan_known` 처리가 필요하다.
2. **범위 용어를 critic·핵심 개념에 공급** — 대회 뒤(spec §12-9 구조화 해석). 06c 의 `terms` 는 검색어에만 쓴다.
3. **`QUESTION_WORDS`·`QUERY_FILLERS` 를 운영 질문으로 늘릴지** — 처음 값은 spec 의 목록이다. 운영 질문의 질문 꼴 낱말·하위질문 군더더기를 모아 본 뒤 정한다.
4. **넓히기가 원 질문 낱말 검사에서 떨어진 비율** — 물러난 잡 수는 `grep -c '\[framing\]'`(물러날 때마다 정확히 한 줄), 그 가운데 낱말 검사에서 떨어진 수는 `grep -c '\[framing\] 넓힌 질문이 원 질문 낱말'` 로 센다(§5-4 에 판정 잡의 두 수를 적는다).
5. **화면 한 줄의 `[id].vue` 바인딩·`candidates` 의 화면** — 06d(10/17~18 nuxt 배포).
6. **06e 의 제목 일치** — 06c 머지 뒤 `services.research.terms.contains` 를 쓴다(06e).

---

## 8. 다음 라운드 진입점

- **06c 배포·판정(10/13~14)** — 계획 Task Z3~Z8. 운영 배포가 끝나면 06d·06e 의 dev 머지 문이 열린다(§12-6).
- **06e·06d(10/17~18 배포)** — 06c 기본값 커밋(판정 결과)을 그 배포에 싣는다. 배포 뒤 06c 확인은 계획 Task Z9.

---

## 상태
- [x] code-reviewer 정적 리뷰 통과(발견 사항 반영 완료) — 작업별 · 영역 다섯
- [x] 테스트 green — 백엔드 <N> · vitest <수> · typecheck 0 · build
- [ ] 수동 스모크 확인 — 운영 처음부터 끝까지 1회(§5)
- [ ] 두 갈래 재판정·기본값 결정(Q4 — §5)
- [ ] 문서 갱신 — `00_status` · spec · `scripts/research_eval/README.md` 06c 재판정 결과 (교본은 대회 뒤 round06 한 권 — D13)
- [ ] `dev` 머지 승인
- [ ] `dev→main` 머지 + push 완료
```

- [ ] **Step 2: `docs/roadmap/00_status.md` — round06 줄**

① 3행. old:

```markdown
최종 갱신: 2026-10-08 (round06c~06e 재정의 — 
```

new:

```markdown
최종 갱신: 2026-10-13 (round06c — 시작 질문 넓히기·검색어 합성·탐색 후보 이벤트 구현 완료(스위치 `broaden`·`query_context` 기본 0), `dev` 머지·운영 배포·두 갈래 재판정 대기. round06c~06e 재정의 — 
```

(old·new 모두 끝에 공백 하나가 있다 — 줄의 나머지는 그대로 이어진다.)

② 22행 머리. old:

```markdown
- **round06 — 06a 완료(2026-10-06) · 06b 완료(2026-10-08)** — 
```

new:

```markdown
- **round06 — 06a 완료(2026-10-06) · 06b 완료(2026-10-08) · 06c 구현 완료·`dev` 머지·운영 배포 대기** — 
```

③ 26행('06c~06e 재정의' 하위 줄) 뒤에 06c 하위 줄. old(26행의 끝):

```markdown
06b 가 8일 앞당겨 끝나 남는 날을 회의 항목에 쓴다(spec D19~D27·§12 — 이 spec 하나만 고쳤다, D13).
```

new:

```markdown
06b 가 8일 앞당겨 끝나 남는 날을 회의 항목에 쓴다(spec D19~D27·§12 — 이 spec 하나만 고쳤다, D13).
  - **06c 질의 — 구현 완료** — 브랜치 `feat/round06c-query-broadening`(worktree `.worktrees/round06c`, dev 에서 분기), 계획 `docs/superpowers/plans/2026-10-08-round06c-query-broadening.md`(Task 0 · C1~C7 · V1~V3 · Z1~Z9). 들어간 것: 계획 전 시작 질문 넓히기(새 모듈 `framing.py`·프롬프트 `research_frame.yaml` — gemma 1회·20초·원 질문 낱말 보존 검사, 실패하면 원 질문. 계획 프롬프트·`planner.py`·승인 본문 그대로), plan step 결과 `question_used`·`terms`·`elapsed_ms`, 검색어 합성(첫 검색어·재검색 제안에 범위 용어, '국내 학술논문에서' 떼기 — 06b 이월 §7-10~12), 탐색 후보 목록 이벤트 `candidates`(Q9 — 화면은 06d), 한국어 낱말 맞추기 `terms.py`(06e 가 같은 `contains` 를 쓴다), 스위치 `broaden`·`query_context`(기본 0), 판정 도구의 갈래별 파라미터·own 계획·계획 지표·대조군, PlanCard "이렇게 이해했어요" prop·리듀서(바인딩은 06d). 스키마 변경 없음. 배포·판정 절차는 계획 Task Z3~Z8. 상세: `round06c-완료노트.md`.
```

④ 53행 '다음 할 일'의 06c 줄 머리. old:

```markdown
  - **06c 질의(10/13~14 배포 — 워커·fastapi)** — 브랜치 `feat/round06c-query-broadening`.
```

new:

```markdown
  - **06c 질의 — 구현 완료, `dev` 머지·배포·두 갈래 재판정 대기(10/13~14 — 워커·fastapi)** — 계획 `docs/superpowers/plans/2026-10-08-round06c-query-broadening.md` 의 Task Z3(`dev` 머지, 사용자 승인) → Z4(fastapi 이미지 · 워커 셋 → fastapi → 게이트웨이 reload, 사용자) → Z5(운영 처음부터 끝까지 1회, 기본값 0) → Z6(두 갈래 재판정) → Z7(기본값 커밋 — 10/17~18 배포에 싣는다) → Z8(기록) 순서. 06d·06e 는 Z4 가 끝난 뒤에만 `dev` 에 머지한다. 브랜치 `feat/round06c-query-broadening`.
```

⑤ 82행 라운드 이력의 round06 칸 끝. old:

```markdown
· 06c·06d·06e 남음(2026-10-08 재정의 — spec §12) |
```

new:

```markdown
· 06c 구현 완료·배포 대기(`feat/round06c-query-broadening`) · [완료노트](round06c-완료노트.md) · 06d·06e 남음(2026-10-08 재정의 — spec §12) |
```

- [ ] **Step 3: spec 을 코드에 맞춘다 (`docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`)**

① 3행 머리 상태 줄. old:

```markdown
06b 완료(2026-10-08 운영 배포·재판정·`main` push).
```

new:

```markdown
06b 완료(2026-10-08 운영 배포·재판정·`main` push) · 06c 구현 완료(2026-10-13 — 스위치 `broaden`·`query_context` 기본 0, `dev` 머지·운영 배포·두 갈래 재판정 대기).
```

② 47행 D25 — 구현 방식. old:

```markdown
두 갈래 판정 뒤 켠다 | 개념 하나짜리
```

new:

```markdown
두 갈래 판정 뒤 켠다. **06c 구현:** 넓히기는 새 모듈 `app/services/research/framing.py`·프롬프트 `research_frame.yaml`(gemma 1회·20초)이고 `planner.py`·`research_plan.yaml` 은 한 글자도 바꾸지 않았다. 낱말 맞추기·검색어 합성은 순수 모듈 `app/services/research/terms.py`(06e 가 같은 `contains` 를 쓴다), 검색어 합성 자리는 runner 의 `_search_query` 한 곳(첫 검색어·재검색 제안)이다. 탐색 후보 이벤트 `candidates` 는 스위치와 무관하게 회차마다 낸다(06c 계획 정함 1~22) | 개념 하나짜리
```

③ 491행 내용어 — 문장부호. old:

```markdown
- 내용어 `content_words(text)`: NFKC → casefold → 공백으로 어절 나누기 →
```

new:

```markdown
- 내용어 `content_words(text)`: NFKC → casefold → 문장부호(`[^\w\s]`)를 공백으로 → 공백으로 어절 나누기 →
```

④ 491행 끝 — 조사만 남은 어절. old:

```markdown
`연구·관한·대한·관련·궁금해·궁금합니다·알려줘·찾아줘·무엇·어떻게`)이 아닌 것.
```

new:

```markdown
`연구·관한·대한·관련·궁금해·궁금합니다·알려줘·찾아줘·무엇·어떻게`)도, 조사만 남은 어절(`PARTICLES` 자체 — 「…」에서 를 공백으로 나눈 뒤의 '에서')도 아닌 것을 처음 나온 순서로 중복 없이(06c 계획 정함 7).
```

⑤ 497행 프롬프트 이름. old:

```markdown
- **프롬프트(새 파일, 예 `research_frame.yaml`):**
```

new:

```markdown
- **프롬프트(새 파일 `app/domains/nl_library/prompts/research_frame.yaml` — parser plain·max_tokens 600·temperature 0.2, 변수 `question` 하나. 넓히기 코드는 새 모듈 `app/services/research/framing.py` 이고 `planner.py` 는 고치지 않는다):**
```

⑥ 501행 terms 정리. old:

```markdown
`terms` 는 코드가 NFKC 정규화·중복 제거하고 4개에서 자른다.
```

new:

```markdown
`terms` 는 코드가 문자열만 받아 NFKC 정규화·공백 정리 뒤 빈 것과 30자 넘는 것을 버리고 casefold 기준 중복을 지워 4개에서 자른다. 넓힌 문장이 비었거나 500자(`ResearchCreate.question` 상한)를 넘으면 원문. 넓힌 문장은 맨 앞 입력 이름표(`질문:`·`질문：`)를 뗀 뒤 검사한다 — 모델이 user 메시지를 이름표째 옮기면 낱말 검사를 통과해 계획 입력·`question_used` 에 이름표가 실리기 때문이다(함정 26). 넓히기 검사는 `content_words` 에 더해 원 질문의 한 글자 어절(조사·질문 꼴 낱말·잇는 말 `ONE_CHAR_FUNCTION_WORDS` 제외)도 넓힌 문장에 어절로 있어야 한다 — 같은 방식(NFKC·casefold·문장부호 공백)으로 나눈 넓힌 문장의 어절이 그 글자이거나 '그 글자 + 조사 하나'(암의·뇌를)일 때만 들어 있다고 본다. 한 글자 명사(암·뇌·법)는 `content_words` 의 2자 바닥에 걸려 '암 연구가 궁금해'에 지어낸 주제를 낸 답도 지나가고, `contains`(부분 문자열)로 보면 '방법'·'암호화'·'뇌물' 안의 글자에도 맞기 때문이다(`content_words`·`contains` 정의는 그대로).
```

⑦ 502행 실패 범위(정함 10). old:

```markdown
오류·빈 응답·검사 실패면 원 질문으로 계획한다 — 잡을 실패시키지 않는다.
```

new:

```markdown
전송·상태·JSON 해석·응답 모양 오류(`FRAME_FAILURES = (httpx.HTTPError, ValueError, KeyError, IndexError)`)·빈 응답·검사 실패면 원 질문으로 계획한다 — 잡을 실패시키지 않는다. 그 밖의 예외(코드 결함·태스크 제어 예외 `SoftTimeLimitExceeded`)는 삼키지 않고 계획 실패로 닫는다(06c 계획 정함 10 — 함정 19: `except Exception` 폴백은 소프트 리밋까지 삼키고 결함을 '원문' 으로 숨겨 판정을 흐린다).
```

⑧ 506행 plan step 결과. old:

```markdown
plan step 결과를 `{"subquestions", "question_used", "terms"}` 로 넓힌다
```

new:

```markdown
plan step 결과를 `{"subquestions", "question_used", "terms", "elapsed_ms"}` 로 넓힌다(`elapsed_ms` 는 넓히기와 계획을 합친 시간 — §12-7 계획 시간 지표가 읽는다)
```

⑨ 507행 중간 알림. old:

```markdown
result 에 `question_used` 를 먼저 써 알린다
```

new:

```markdown
result 에 `{"question_used", "terms"}` 를 먼저 써 알린다(`broaden` 1 일 때만 — 0 이면 넓히기를 부르지 않고 중간 알림도 없다)
```

⑩ 512행 PlanCard 검증(정함 21). old:

```markdown
— vitest 로 그리기·숨기기까지 검증)
```

new:

```markdown
— 그리기·숨기기 판단은 순수 함수 `questionUsedFromSteps`·`understoodLine` 의 vitest 로, PlanCard 는 `nuxi typecheck`·`npm run build` 로 검증한다. 프론트 vitest 가 node 환경이라 컴포넌트를 그리지 못한다 — 06c 계획 정함 21)
```

⑪ 518행 검색어 합성 규칙의 자리. old:

```markdown
- **규칙(순수 함수, 예 `compose_query(text, terms)`):**
```

new:

```markdown
- **규칙(순수 함수 `compose_query(text, terms)` — `terms.py`. runner 의 `_search_query(state, text)` 한 곳이 첫 검색어와 재검색 제안에 쓴다. `_next_query` 는 그대로다):**
```

⑪-2 520행 검색어 합성 규칙(정함 12). old:

```markdown
  - `terms` 가운데 하위질문에 `contains` 가 아닌 것을 붙인다. `terms` 가 비면 군더더기만 뗀다.
```

new:

```markdown
  - 군더더기를 지워 남는 것이 없으면 하위질문의 공백만 정리한 글로 물러난다. 그 글에 `terms` 를 차례로 보며, 지금까지의 글(앞에서 이어 붙인 용어 포함)에 `contains` 가 아닌 용어만 공백 하나로 이어 붙인다 — 용어도 공백을 정리하고 빈 용어는 건너뛴다. `terms` 가 비면 군더더기만 뗀다. 합성한 글을 다시 넣어도 같은 글이 나온다(재검색 제안이 앞 검색어를 고쳐 써도 용어가 두 번 붙지 않는다) — 군더더기만으로 된 글이 물러난 경우는 빼고(06c 계획 정함 12).
```

⑫ 723행 `--param`. old:

```markdown
  - `--param` — 갈래 1 에 줄 잡 파라미터. 지금은 params 를 `{"critic_scope": n}` 으로 박아 둔다(`:36-40`).
```

new:

```markdown
  - `--param0`·`--param` — 갈래 0·1 에 줄 잡 파라미터(JSON 객체, 기본 `{"critic_scope": 0}`·`{"critic_scope": 1}` — 06c 전 동작 그대로). 06c 판정은 두 갈래에 `critic_scope`·`broaden`·`query_context` 를 모두 적는다 — 기본값을 켠 뒤에도 갈래 0 이 '지금 방식'이게.
```

⑬ 724행 `--plan own`·대조군·`--plan-only`. old:

```markdown
기본은 지금 동작(shared) 그대로.
```

new:

```markdown
기본은 지금 동작(shared) 그대로. 대조군 질문 파일은 `scripts/research_eval/questions_control.json`(논문 버튼 꼴 2개)이고, `score.py --plan-only` 는 라벨 없이 계획 지표만 찍는다.
```

⑭ 733행 계획 시간. old:

```markdown
| 계획 시간(plan step 결과의 `elapsed_ms`, 또는 `--poll 0.5` 로 created → awaiting_approval) |
```

new:

```markdown
| 계획 시간(plan step 결과의 `elapsed_ms` — poll 로 재지 않는다) |
```

⑮ 738행 나눠 판정하는 법(정함 20). old:

```markdown
엇갈리면 두 스위치를 나눠 다시 판정한다(`query_context` 단독은 shared 모드, `broaden` 은 own 모드).
```

new:

```markdown
엇갈리면 두 스위치를 나눠 다시 판정한다 — `query_context` 효과는 `--plan shared` + 갈래 1 `{broaden 1, query_context 1}`(갈래 1 의 계획 단계가 범위 용어를 내지만 승인은 갈래 0 계획 — 검색어만 다르다), `broaden` 효과는 `--plan own` + 갈래 1 `{broaden 1, query_context 0}`(계획만 다르다). `broaden` 0 이면 범위 용어가 비어 `query_context` 단독 갈래는 군더더기만 떼기 때문이다(06c 계획 정함 20).
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && grep -c "06c 계획 정함" docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && grep -c "예 \`research_frame.yaml\`\|예 \`compose_query\|vitest 로 그리기·숨기기까지 검증\|--poll 0.5" docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`

Expected: 첫 수 `6`(② D25 47행·③④ 491행·⑦ 502행·⑩ 512행·⑪-2 520행·⑮ 738행 — `grep -c` 는 줄마다 한 번 세고 ③④ 는 같은 줄이다. `65e257b`·`c5d05b0` 판 spec 에 ⑪-2 밖의 구절을 손으로 넣어 `5` 를 실측했고, ⑪-2 의 old 는 그 판의 520행 한 줄뿐이라 한 줄이 는다), 둘째 `0`(옛 '예'·검증 문구·poll 이 남지 않았다 — 종료 코드 1 은 맞는 줄이 없을 때의 정상 값).

- [ ] **Step 4: 반복 함정 — 이번에는 더하지 않는다는 판단을 적는다**

`docs/ops/recurring-gotchas.md` 는 라이브(docker·실데이터)에서만 드러난 패턴을 적는다. 06c 는 아직 운영 전이라 더할 것이 없다 — 완료노트 §5 에서 Task Z8 이 운영 확인·판정의 관찰을 보고 다시 판단한다(예: gemma 가 넓힌 문장에서 원 질문 낱말을 자주 바꿔 원문으로 떨어지면 함정 26 의 '입력을 다루는 LLM' 항목에 덧붙인다). 이 Step 은 파일을 고치지 않는다.

- [ ] **Step 5: 문서 리뷰 — code-reviewer 하나**

`.claude/agents/code-reviewer.md` 서브에이전트(subagent_type `code-reviewer`)에게 문서 일관성 리뷰를 맡긴다. 프롬프트:

```text
round06c 문서 리뷰(일관성). 저장소 C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c 에서 docs/roadmap/round06c-완료노트.md(새), docs/roadmap/00_status.md 의 round06 줄, docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md 의 머리 상태 줄·D25·§12-2·§12-7 을 읽고, 코드(app/services/research/terms.py·framing.py·runner.py·state.py, app/workers/research_tasks.py, app/domains/nl_library/prompts/research_frame.yaml, scripts/research_eval/run_pair.py·score.py·README.md, frontend/utils/researchEvents.ts·components/research/PlanCard.vue)와 계획 docs/superpowers/plans/2026-10-08-round06c-query-broadening.md 의 정함 1~22 에 맞는지 본다. 특히 spec §12-2 의 content_words 정의·terms 정리와 넓힌 질문의 입력 이름표 떼기·실패 범위·plan step 결과 모양·PlanCard 검증 방법·compose_query 규칙, §12-7 의 run_pair 옵션·계획 시간·나눠 판정하는 법이 코드와 같은지, 완료노트 §2·§6 이 코드와 같은지, 상수·이름(BROADEN_TIMEOUT 20·MAX_TERMS 4·TERM_MAX_CHARS 30·FRAMED_QUESTION_MAX 500·FRAME_FAILURES·QUERY_FILLERS·candidates·subq_idx)이 문서마다 같은지, stale 서술이 남았는지. 보고는 code-reviewer 형식.
```

Expected: 결함 목록(없으면 "없음"). 발견은 Edit 로 고친다(같은 커밋에 넣는다).

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && ! grep -n '<[^>]*>' "docs/roadmap/round06c-완료노트.md" && git add "docs/roadmap/round06c-완료노트.md" && git add docs/roadmap/00_status.md && git add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git status --short && git commit -m "[Docs] round06c — 완료노트(왜·한 일·리뷰·검증·결정 정함 1~22·이월, 배포 전)와 현재 상태(round06 줄 — 06c 구현 완료·배포 대기, 다음 할 일은 계획 Task Z3~Z8 의 머지·배포·두 갈래 재판정 순서), spec 을 코드에 맞춘다: 머리 상태 줄, D25 구현 방식(framing.py·research_frame.yaml·terms.py·_search_query·candidates), §12-2 content_words 의 문장부호와 조사만 남은 어절 규칙, terms 정리와 넓힌 질문의 입력 이름표 떼기, 넓히기 실패 범위(FRAME_FAILURES 밖의 예외는 계획 실패 — 함정 19), plan step 결과 elapsed_ms, 중간 알림은 broaden 1 일 때만, PlanCard 검증은 순수 함수 vitest 와 typecheck·build, compose_query 자리와 규칙(이어 붙인 용어와도 견줌·빈 용어 건너뜀·군더더기만이면 원문), §12-7 run_pair --param0·--param·대조군 파일·score --plan-only·계획 시간 elapsed_ms·스위치를 나눠 판정하는 법"
```

Expected: `grep` 이 찍는 줄 없이 커밋 1개(`git status --short` 의 세 줄 `A `·`M `·`M ` 과 커밋 요약만 나온다). 완료노트에 꺾쇠 자리가 남았으면 그 줄을 행 번호와 함께 찍고 커밋하지 않은 채 멈춘다 — Step 1 의 규칙대로 채운 뒤 같은 명령을 다시 돌린다.

---

### Task Z3: (사용자 승인) dev 머지 — 머지 문 확인·임시 worktree

**왜:** GIT_WORKFLOW — dev 머지는 매번 사용자 승인. §12-6 머지 문 — 06c 가 세 줄 중 먼저 dev 에 들어가고 먼저 배포한다(06e 백엔드가 06c 배포 이미지에 섞여 nuxt 없이 나가지 않게). dev 머지가 배포보다 먼저다 — 06c 가 운영에 있고 dev 에 없는 동안 다른 세션이 dev 로 `:latest` 를 빌드·Recreate 하면 06c 가 말없이 되돌려진다(06a 사용자 결정 2026-10-03). **머지 뒤 배포(Task Z4)를 미루지 않는다** — 그 사이 다른 세션이 dev 로 빌드한 이미지로 fastapi 만 Recreate 하면 새 fastapi 가 새 키(`broaden`·`query_context`)를 params 에 싣고, 옛 워커의 `merge_params` 가 그 키를 '알 수 없는 파라미터' 로 거부해 계획이 실패한다.

**Files:** 없음(머지 커밋만 — 충돌이 났으면 그 해결)

- [ ] **Step 1: 머지 문과 충돌을 미리 본다(작업 트리를 건드리지 않는다)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
git fetch origin dev:dev
BASE=$(git merge-base HEAD dev); echo "$BASE"
git log --oneline --merges $BASE..dev | grep -cE "feat/round06(d|e)-"
git log --oneline HEAD..dev
git merge-tree --write-tree --name-only dev HEAD; echo "exit=$?"
```

Expected:
- 06d·06e 머지 → `0`. **0 이 아니면 머지하지 않고 멈춘다** — 머지 문(§12-6)과 어긋났다. 이미 들어온 06d·06e 를 이 배포에 함께 낼지 사용자와 정한다(06e 백엔드가 nuxt 없이 나가면 옛 화면에 연쇄 없는 승인 목차만 남는다).
- `HEAD..dev` — 빈 출력이거나 문서 커밋뿐(다른 라운드의 코드 커밋이 있으면 적어 두고 Step 3 뒤 Task Z4 Step 2 의 규칙으로 처리한다)
- `merge-tree` — 트리 OID 한 줄과 `exit=0`(충돌 없음). `exit=1` 과 충돌 파일이 `docs/roadmap/00_status.md` 하나면 아래 규칙으로 푼다. 다른 파일이면 **머지를 멈추고** 사용자와 정한다.
- `00_status.md` 충돌 규칙: 어느 한쪽을 통째로 고르지 않는다. 3행은 dev 쪽 줄을 바탕으로 날짜를 머지하는 날로 바꾸고 괄호 맨 앞에 Task Z2 Step 2 ① 의 `round06c — … 재판정 대기. ` 구절만 넣는다. round06 줄과 그 아래 하위 줄은 세 줄이 함께 쓰는 블록이다 — dev 쪽 줄(06d·06e 구절이 있으면 그대로)을 남기고 이 브랜치의 06c 구절(머리의 '06c 구현 완료·…'·06c 하위 줄)만 더한다. 다음 할 일·라운드 이력의 round06 칸도 같은 방법이다. 다 풀면 `grep -cE '^(<<<<<<<|=======|>>>>>>>)' docs/roadmap/00_status.md` 가 `0`.

- [ ] **Step 2: 사용자에게 승인을 받는다**

리뷰를 마친 커밋(Task Z1 Step 4)·문서 커밋(Task Z2 Step 6)·Step 1 의 출력(머지 문 0·충돌 없음)을 보이고 "06c 를 dev 에 머지하고 이어서 운영 배포(Task Z4)를 한다" 는 승인을 받는다. 승인 문장과 날짜를 적어 둔다(완료노트 '상태').

- [ ] **Step 3: 임시 worktree 에서 머지하고 바로 지운다**

본 작업 폴더가 아니라 임시 worktree 에서 머지한다. 그 폴더 안으로 `cd` 하지 않는다 — 셸이 그 안에 있으면 Windows 가 폴더를 지우지 못해 빈 폴더가 남는다(06b 완료노트 §7-17).

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/dev-merge dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge merge --no-ff feat/round06c-query-broadening -m "Merge feat/round06c-query-broadening into dev — round06c 질의(시작 질문 넓히기·검색어 합성·탐색 후보 이벤트 candidates, 스위치 broaden·query_context 기본 0, 스키마 변경 없음)"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge push origin dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c dev-merge
```

Expected: 머지 커밋 한 줄(완료노트 §5-1 에 적는다), push 성공, 마지막 줄 `0`. 충돌이 났으면 Step 1 의 규칙으로 `.worktrees/dev-merge` 의 `docs/roadmap/00_status.md` 를 Edit 로 고친 뒤 `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge add docs/roadmap/00_status.md && git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge commit --no-edit` 로 머지를 끝내고 push 한다.

---

### Task Z4: (사용자, 서버) 운영 배포 — 워커 → fastapi → 게이트웨이 reload (10/13~14)

**왜:** §12-6 — 06c 배포는 워커·fastapi 다(nuxt 는 10/17~18). 스키마 단계는 없다(JSONB·잡 파라미터 안 모양만 — 함정 14). Step 1·3~6 은 **사용자가** 서버에서, Step 2 는 개발 PC 에서 한다.

**Files:** 없음

**알아 둘 것:**
- **순서의 까닭:** ① **워커가 fastapi 보다 먼저다** — 새 fastapi 는 새 잡의 params 에 `broaden`·`query_context` 를 채워 저장하는데(`api/research.py:235` `merge_params`), 옛 워커(`celery-research-plan` 의 계획, `celery-research` 의 실행)의 `merge_params` 는 모르는 키를 `알 수 없는 파라미터` 로 거부해 계획·실행이 실패한다. 워커를 먼저 바꾸면 그 사이 옛 fastapi 가 만든 잡은 키가 없어도 새 워커가 기본값으로 채운다. ② `celery-research-plan`(넓히기·계획)·`celery-research`(실행 시작의 terms·검색어 합성·후보 이벤트)가 06c 코드를 돌린다. ③ `celery-control`(회수기·적재 디스패처)은 06c 가 고친 코드를 쓰지 않지만 **같은 이미지로 맞춘다**(06b 선례 — 롤백과 다음 배포(10/17~18)의 '워커 셋이 fastapi 와 같은 이미지' 확인이 이 전제다). ④ 적재 워커(`celery-worker`·`celery-cpu`·`celery-llm`·`celery-embed`)와 `celery-beat` 는 Recreate 하지 않는다 — 스택 업데이트 금지(함정 16). ⑤ fastapi 를 Recreate 했으니 마지막에 `nginx -s reload`(함정 20). nuxt 는 Recreate 하지 않는다.
- **서버 명령은 처음부터 root 셸(`su - root`)에서 한다** — `sudo` 가 아니다. 셸을 바꾸면 `pg`·`pgq`·`OLD`·`NEW`·`API` 를 다시 정의한다.
- 함정: 3(운영은 `:latest`)·12(Portainer 에 pull 을 맡기지 않는다 — CLI `docker pull` 을 끝까지 기다린 뒤 "Re-pull image" 끄고 Recreate)·16(바뀐 컨테이너만)·18(fastapi Recreate 전 `idle in transaction` 0)·20(reload, 확인은 게이트웨이 92 경유)·24(browser_active 429 가 안 풀리면).

- [ ] **Step 1: (사용자, 서버) 전제 확인**

```bash
su - root                                                                              # 이 셸에서 끝까지 이어 쓴다
pg()  { docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; }
pgq() { docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA'; }
API=http://localhost:92/api
echo "SELECT version_num FROM alembic_version" | pgq                                  # 0007_research_work — 06c 는 바꾸지 않는다
OLD=$(docker inspect --format '{{.Image}}' nl-lib-fastapi); echo "$OLD" | cut -c1-19
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$OLD" ] && echo "$c 같음" || echo "$c 다름"
done                                                                                  # 셋 다 '같음'
docker exec nl-lib-fastapi printenv RESEARCH_QUEUE                                    # q_research
docker exec nl-lib-fastapi printenv MILVUS_RECREATE_ON_MISMATCH                       # false
echo "SELECT status, count(*) FROM ingest_job_items WHERE status IN ('dispatched', 'running') GROUP BY status" | pgq
echo "SELECT id, name, status FROM ingest_jobs WHERE status = 'running'" | pgq
```

Expected: `0007_research_work`, `sha256:e9481c0d2731`(06b 결정 재배포 이미지 — 그 뒤 다른 배포가 있었으면 그 이미지), 세 줄 '같음', `q_research`, `false`, 그리고 적재 in-flight 줄(없으면 빈 출력)과 도는 적재 잡(없으면 빈 출력) — 적재 둘은 수를 적어 두기만 한다.
- `다름` 이 있으면 배포를 멈추고 되돌릴 이미지를 사용자와 정한다(롤백은 넷이 같은 이미지라는 전제다).
- `alembic_version` 이 다르면 멈춘다(함정 14).
- `RESEARCH_QUEUE` 가 `q_research` 가 아니면 판정(Task Z6)의 갈래 1 승인이 429 `shared_queue` 로 막힌다 — 멈추고 묻는다.
- `MILVUS_RECREATE_ON_MISMATCH` 가 `false` 가 아니면 **멈춘다** — fastapi 기동·`celery-research` 검색·`celery-control` 정리가 부르는 `ensure_collection()` 이 스키마가 다를 때 컬렉션을 지우고 새로 만든다(함정 16 재발 방지).
- 적재 in-flight(`dispatched`·`running`)가 있어도 06c 배포는 할 수 있다 — 적재 워커(`celery-worker`·`celery-cpu`·`celery-llm`·`celery-embed`)는 Recreate 하지 않으므로 그 태스크는 끊기지 않는다(함정 16 — 바뀐 컨테이너만). `celery-control` Recreate 는 적재 디스패치 틱 하나를 끊을 뿐이고 다음 틱이 이어 간다. 다만 수가 많으면(대량 인덱싱 한창) 적재가 적은 시간으로 미루는 것을 사용자와 정한다.

- [ ] **Step 2: (개발 PC) 빌드 확인·fastapi 이미지 빌드**

운영 스택은 `:latest` 를 쓴다(함정 3). 빌드는 dev 와 같은 트리에서 한다 — 다르면 dev 에 있고 빌드에 없는 코드를 이 이미지가 말없이 되돌리거나, 그 반대를 다음 dev 빌드가 되돌린다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
(
  git fetch origin dev:dev || { echo "fetch 실패 — origin/dev 를 확인하지 못했다, 멈춘다"; exit 1; }
  git merge-base --is-ancestor HEAD dev || { echo "HEAD 에 dev 에 없는 커밋이 있다 — 멈춘다"; exit 1; }
  C=$(git log --oneline HEAD..dev -- app frontend infra docker-compose.yml scripts/build_dev_images.sh)
  [ -z "$C" ] || { printf 'dev 에 HEAD 에 없는 코드 커밋이 있다 — 멈춘다\n%s\n' "$C"; exit 1; }
  M=$(git log --oneline --merges da80f23..dev | grep -cE "feat/round06(d|e)-")      # da80f23 = 06c 계획 때의 dev — 06d·06e 머지는 모두 그 뒤다(ff-only 로 dev 를 받은 뒤에도 빠지지 않는다)
  [ "$M" = 0 ] || { echo "dev 에 06d·06e 머지가 있다 — 머지 문(§12-6)과 어긋난다, 멈춘다"; exit 1; }
  echo "빌드해도 된다: $(git rev-parse HEAD)"
)
```

마지막 줄이 `빌드해도 된다: <커밋>` 일 때만 빌드한다(그 커밋을 완료노트 §5-1 에 적는다). 멈췄으면:
- `fetch 실패` — `refusing to fetch into branch 'refs/heads/dev' checked out at …` 이면 Task Z3 의 임시 worktree 가 남아 있다(지운 뒤 다시). `[rejected] … (non-fast-forward)` 면 로컬 dev 에 origin 에 없는 커밋이 있다(머지 뒤 push 를 빠뜨렸으면 push 한 뒤 다시).
- `HEAD 에 dev 에 없는 커밋` — Task Z3 의 머지가 빠졌다. 머지부터 한다.
- `dev 에 HEAD 에 없는 코드 커밋` — 다른 라운드(06d·06e 가 아닌 것)가 먼저 dev 에 코드를 넣었다. 06c worktree 에서 `git merge --ff-only dev` → Task Z1 Step 1 의 회귀(백엔드 전체·06c 묶음·typecheck·vitest·build)를 다시 돌려 실패 0 을 본 뒤 → 위 확인부터 다시 하고 빌드한다. 다시 돈 수를 완료노트 §5-1 에 적는다.
- `06d·06e 머지가 있다` — 머지 문이 깨졌다. 빌드하지 않고 사용자와 정한다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi
```

Expected: `── FastAPI: landsoftdocker/nl-lib-fastapi:latest ──…` 뒤 build·push 로그, 끝에 `완료. Portainer에서 nl-lib-dev 스택 Pull & Redeploy 하면 반영됩니다.`(스크립트의 고정 안내 — 운영은 아래 Step 3~5 로 한다). nuxt 는 만들지 않는다(화면 한 줄은 10/17~18).

- [ ] **Step 3: (사용자, 서버) 되돌리기 태그를 남기고 새 이미지를 받는다**

```bash
docker tag "$OLD" landsoftdocker/nl-lib-fastapi:pre-round06c
docker pull landsoftdocker/nl-lib-fastapi:latest                                      # 7GB 남짓 — 끝까지 기다린다
NEW=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-fastapi:latest); echo "$NEW" | cut -c1-19
[ "$NEW" != "$OLD" ] && echo "새 fastapi 이미지 받음"                                 # pull 이 끝나기 전에 잡으면 옛 ID 다(06a 교훈)
```

Expected: pull 의 마지막 줄 `Status: Downloaded newer image for landsoftdocker/nl-lib-fastapi:latest`, 새 ID 앞 19자, `새 fastapi 이미지 받음`. pull 만으로는 아무 컨테이너도 다시 시작되지 않는다(함정 16).

- [ ] **Step 4: (사용자, 서버) 비었는지 확인**

`celery-research` 를 Recreate 하면 도는 딥리서치가 끊긴다(회수기가 45분 뒤 failed 로 거둔다). `celery-research-plan` 을 Recreate 하면 도는 계획과 연구 어시스턴트 생성이 끊긴다. 적재 워커는 건드리지 않지만 적재가 적은 시간에 한다.

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

Expected: 두 질의 모두 0행(있으면 끝나기를 기다린다 — 사용자 잡·생성을 취소하지 않는다), `q_research 0`·`q_research_plan 0`, 세 워커 모두 `- empty -`(`celery-control` 은 디스패치 틱이 도는 중이면 몇 초 뒤 다시). `inspect` 는 `-d` 가 없으면 적재 워커까지 모든 워커에 묻는다 — 한 워커를 볼 때는 `-d "celery@$(hostname)"` 로 좁힌다.

- [ ] **Step 5: (사용자, 서버) 컨테이너별 Recreate — 워커 셋 → fastapi → 게이트웨이**

Portainer 에서 컨테이너마다 Recreate 를 누르고 **"Re-pull image" 는 끈다**(서버에 받아 둔 `:latest` 를 쓴다 — 함정 12). 스택 업데이트는 하지 않는다(함정 16). 스키마 단계는 없다.

① `nl-lib-celery-research-plan` → ② `nl-lib-celery-research` → ③ `nl-lib-celery-control` 을 차례로 Recreate 한 뒤:

```bash
for c in nl-lib-celery-research-plan nl-lib-celery-research nl-lib-celery-control; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$NEW" ] && echo "$c 새 이미지" || echo "$c 옛 이미지"
done
docker exec nl-lib-celery-research-plan sh -c 'celery -A workers.celery_app inspect active_queues -d "celery@$(hostname)" --timeout 5' | grep -o "\* {'name': 'q_[a-z_]*'"
docker exec nl-lib-celery-research sh -c 'celery -A workers.celery_app inspect active_queues -d "celery@$(hostname)" --timeout 5' | grep -o "\* {'name': 'q_[a-z_]*'"
docker exec nl-lib-celery-research-plan ls /app/domains/nl_library/prompts/research_frame.yaml
docker exec -w /app nl-lib-celery-research-plan python -c "from services.research.framing import BROADEN_TIMEOUT, MAX_TERMS; from services.research.state import DEFAULT_PARAMS as P; print(BROADEN_TIMEOUT, MAX_TERMS, P['broaden'], P['query_context'])"
docker exec -w /app nl-lib-celery-research python -c "from services.research.runner import _search_query; from services.research.terms import QUERY_FILLERS, compose_query; print(QUERY_FILLERS, '|', compose_query('국내 학술논문에서 컴퓨팅 자원의 개념', ['클라우드 컴퓨팅']))"
```

Expected:
- 세 줄 모두 '새 이미지'(하나라도 '옛 이미지' 면 그 컨테이너를 다시 Recreate — 06b 배포에서 `celery-research` 가 한 번 옛 이미지로 나왔다)
- `* {'name': 'q_research_plan'` 한 줄, `* {'name': 'q_research'` 한 줄
- `/app/domains/nl_library/prompts/research_frame.yaml`
- `20 4 0 0`(넓히기 상한 20초·용어 4개·두 스위치 기본 0)
- `('국내 학술논문에서',) | 컴퓨팅 자원의 개념 클라우드 컴퓨팅`(군더더기를 떼고 없는 범위 용어를 붙인다)

④ fastapi 를 Recreate 하기 전에 `library_catalog` 를 쥔 채 멈춘 트랜잭션이 없는지 본다(함정 18 — lifespan 의 `ALTER TABLE library_catalog …` 가 배타 잠금을 기다리며 기동이 멈추고 그 뒤 조회가 줄 선다).

```bash
pg <<'SQL'
SELECT pid, state, xact_start, left(query, 80) FROM pg_stat_activity WHERE state = 'idle in transaction';
SQL
# 0행(또는 xact_start 가 몇 초 전인 것뿐)이면 Portainer 에서 nl-lib-fastapi 를 Recreate 한다
docker logs -f --since 1m nl-lib-fastapi 2>&1 | grep -m1 "Application startup complete"   # 모델을 올려 1~2분
[ "$(docker inspect --format '{{.Image}}' nl-lib-fastapi)" = "$NEW" ] && echo "fastapi 새 이미지"
echo "SELECT version_num FROM alembic_version" | pgq                                     # 0007_research_work 그대로
```

⑤ 게이트웨이를 reload 한다(함정 20 — fastapi 를 Recreate 했다).

```bash
docker exec nl-lib-gateway nginx -s reload
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/
```

Expected: `INFO:     Application startup complete.` 한 줄, `fastapi 새 이미지`, `0007_research_work`, `200`·`200`.

- [ ] **Step 6: (사용자, 서버) 반영 확인 — API 검증과 기본값**

게이트웨이(포트 92)를 거쳐 확인한다(컨테이너에 직접 붙는 확인은 함정 20 을 못 잡는다).

```bash
docker exec nl-lib-fastapi grep -c query_context /app/services/research/state.py
docker exec -w /app nl-lib-fastapi python -c "from services.research.state import merge_params; m = merge_params({}); print(m['broaden'], m['query_context'], m['critic_scope'])"
curl -s -w '\n%{http_code}\n' -X POST $API/research -H 'Content-Type: application/json' \
  -d '{"question":"공공도서관 서비스 품질 평가 연구가 궁금해","params":{"broaden":2}}'
curl -s -w '\n%{http_code}\n' -X POST $API/research -H 'Content-Type: application/json' \
  -d '{"question":"공공도서관 서비스 품질 평가 연구가 궁금해","params":{"query_context":true}}'
```

Expected: `grep -c` 가 `2` 이상(`DEFAULT_PARAMS`·`_PARAM_BOUNDS` 의 두 줄 — `0` 이면 옛 이미지다), `0 0 0`, 그리고 두 요청 모두 잡을 만들지 않고 422:

```text
{"detail":"파라미터 broaden 가 허용 범위(0~1)를 벗어났다: 2"}
422
{"detail":"파라미터 query_context 에 bool 값은 쓸 수 없다: True"}
422
```

배포가 끝났다 — 06d·06e 세션(사용자)에게 **머지 문이 열렸다**고 알린다(§12-6: 06d·06e 는 이제 dev 에 머지할 수 있다). 그리고 Task Z5·Z6 이 끝날 때까지는 다른 딥리서치·연구 어시스턴트 배포를 하지 않는다.

---

### Task Z5: (사용자, 서버·브라우저) 운영 처음부터 끝까지 1회 — 기본값 0

**왜:** §12-7 운영 확인(줄마다 배포 뒤 고정 질문 하나를 처음부터 끝까지)과 §8. 기본값 0 으로 배포했으므로 계획 입력·검색어는 06c 전과 같고, 바뀐 것은 plan step 결과의 칸(`question_used`·`terms`·`elapsed_ms`)과 회차마다 하나 느는 `candidates` 이벤트뿐이어야 한다. 06b 와 같은 질문(`computing` — 06b 기준 잡 `d8348de8`)으로 재야 단계 시간을 06a·06b 표와 견줄 수 있다. Task Z6(판정) 보다 먼저 한다 — 딥리서치가 함께 돌면 gemma 를 나눠 써 시간이 섞인다.

**Files:** 없음(결과는 Task Z8 이 완료노트 §5-3 에 적는다)

**알아 둘 것:** 만든 잡은 실제 기록으로 남는다(`x-session-id` 없이 만들어 브라우저 기록·실행 제한 밖이다 — run_pair 와 같다). SSE 를 받아 둘 파일은 서버의 `/data/nl-lib/data/`(fastapi 컨테이너 안 `/app/data/`) 아래에 둔다.

- [ ] **Step 1: (사용자, 서버) 잡을 만들고 계획을 본다**

```bash
J=$(curl -s -X POST $API/research -H 'Content-Type: application/json' \
  -d '{"question":"컴퓨팅 자원에 대한 연구가 궁금해"}' | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4); echo "$J"
until curl -s $API/research/$J | grep -q '"status":"awaiting_approval"'; do sleep 1; done
docker exec -i -e J=$J nl-lib-fastapi python - <<'PY'
import json, os, urllib.request
job = json.load(urllib.request.urlopen(f"http://localhost:8000/api/research/{os.environ['J']}"))
print(job["status"], {k: job["params"][k] for k in ("broaden", "query_context", "critic_scope")})
plan = [s for s in job["steps"] if s["kind"] == "plan"][-1]["result"]
print(sorted(plan), plan["question_used"] == job["question"], plan["terms"], plan["elapsed_ms"])
for i, sq in enumerate(job["plan"], 1):
    print(f"  {i}. {sq}")
PY
docker logs --since 10m nl-lib-celery-research-plan 2>&1 | grep -c '\[framing\]'
```

Expected:
- 잡 id 한 줄(완료노트 §5-3 에 적는다), `until` 은 몇 초 안에 끝난다
- `awaiting_approval {'broaden': 0, 'query_context': 0, 'critic_scope': 0}`
- `['elapsed_ms', 'question_used', 'subquestions', 'terms'] True [] <정수>` — 스위치 0 이면 원 질문 그대로·범위 용어 없음, `elapsed_ms` 는 계획만의 시간(06b 기준 계획 단계 4초 안쪽)
- 하위질문 6줄(06b 처럼 '국내 학술논문에서 …' 질문형일 수 있다 — 계획 프롬프트는 그대로다)
- `[framing]` 로그 `0`(스위치 0 이면 넓히기를 부르지 않는다)

- [ ] **Step 2: (사용자, 서버) SSE 를 받으며 승인하고 끝까지 기다린다**

```bash
curl -sN $API/research/$J/stream > /data/nl-lib/data/r06c_$J.sse & CURL_PID=$!
sleep 2
curl -s -X POST $API/research/$J/approve | grep -o '"status":"[a-z_]*"'
wait $CURL_PID; echo "스트림 끝"
curl -s $API/research/$J | grep -o '"status":"[a-z_]*"' | head -1
```

Expected: `"status":"approved"`, 몇 분 뒤 `스트림 끝`(잡이 끝나면 서버가 종료 프레임을 보내고 스트림을 닫는다), `"status":"completed"`.

- [ ] **Step 3: (사용자, 서버) 이벤트·검색어·보고서를 본다**

```bash
docker exec -i -e J=$J nl-lib-fastapi python - <<'PY'
import json, os, urllib.request
jid = os.environ["J"]
kinds, bad_shape = [], 0
for line in open(f"/app/data/r06c_{jid}.sse", encoding="utf-8"):
    if not line.startswith("data: "):
        continue
    ev = json.loads(line[6:])
    kind = ev.get("kind")
    if kind in ("search", "counters", "candidates", "critique"):
        kinds.append(kind)
    if kind == "candidates":
        keys_ok = set(ev) == {"kind", "subq_idx", "round", "papers"}
        papers_ok = all(set(p) == {"cnts_id", "title", "personal_author", "pub_date"} for p in ev["papers"])
        bad_shape += not (keys_ok and papers_ok)
bad_order = sum(1 for i, k in enumerate(kinds) if k == "candidates" and (
    i == 0 or kinds[i - 1] != "counters" or i + 1 >= len(kinds) or kinds[i + 1] != "critique"))
n_cand, n_crit = kinds.count("candidates"), kinds.count("critique")
print(f"candidates {n_cand} · critique {n_crit} · 순서 어긋남 {bad_order} · 모양 어긋남 {bad_shape}")
job = json.load(urllib.request.urlopen(f"http://localhost:8000/api/research/{jid}"))
trail = job["report"]["trail"]
first_ok = sum(t["queries"][:1] == [t["subquestion"]] for t in trail)
filler = sum("국내 학술논문에서" in q for t in trail for q in t["queries"])
print(f"첫 검색어 = 하위질문 글 {first_ok}/{len(trail)} · '국내 학술논문에서' 든 검색어 {filler}개")
print("rounds 에 candidates 칸:", any("candidates" in r for s in job["steps"] if s["kind"] == "search"
                                     for r in (s["result"] or {}).get("rounds", [])))
PY
pg <<SQL
SELECT round(extract(epoch FROM started_at - created_at)) AS before_run_sec,
       round(extract(epoch FROM finished_at - started_at)) AS run_sec
FROM research_jobs WHERE id = '$J';
SELECT kind, count(*) AS steps, round(extract(epoch FROM max(finished_at) - min(created_at))) AS sec
FROM research_steps WHERE job_id = '$J' GROUP BY kind ORDER BY min(created_at);
SQL
docker logs --since 30m nl-lib-celery-research 2>&1 | grep -ciE "error|traceback"
```

Expected:
- `candidates n · critique n · 순서 어긋남 0 · 모양 어긋남 0` — 두 수가 같고(회차마다 한 번) 6 이상(하위질문 6개 × 회차 1~4)
- `첫 검색어 = 하위질문 글 6/6`(스위치 0 — 검색어 글자 그대로), '국내 학술논문에서' 든 검색어 수는 기록만 한다(스위치 0 이라 떼지 않는다 — 판정 갈래 1 과 견줄 기준)
- `rounds 에 candidates 칸: False`(회차 기록·스냅숏에 넣지 않는다)
- 첫 질의 1행, 둘째 질의 `plan`·`search`·`synthesize` 세 줄. 06b 기준(`d8348de8`): `before_run_sec 5 · run_sec 144`, `plan 1단계 4초 · search 6단계 83초 · synthesize 1단계 61초` — 크게 다르면(계획이 10초를 넘는 등) 완료노트 §5-3 에 적고 `docker logs nl-lib-celery-research-plan` 을 본다
- 워커 오류 줄 수 `0`(0 이 아니면 그 줄을 보고 사용자에게 알린다)

- [ ] **Step 4: (사용자, 브라우저) 화면이 그대로인지 본다**

`http://192.168.12.57:92/research/<J>` 를 연다. nuxt 는 06c 전 이미지 그대로다 — PlanCard·진행 패널·근거 장부·보고서·이어가기 카드가 06b 와 같고, PlanCard 머리에 "이렇게 이해했어요" 줄이 **없다**(바인딩은 06d, 10/17~18). 개발자 도구 콘솔에 오류가 없다(옛 화면은 모르는 `candidates` 이벤트를 무시한다 — `researchEvents.ts:329` `default: return view`). 본 것을 완료노트 §5-3 에 적는다.

---

### Task Z6: 06c 두 갈래 재판정 (같은 날 — 사용자 승인 뒤 개발 PC 에서 운영 API 로)

**왜:** §12-7·Q4 — 기본값 0 으로 배포한 두 스위치를 켤지 같은 날 같은 코퍼스 시점의 상대 비교로 정한다(D11 방식). 갈래 0 = 지금 방식(`broaden` 0·`query_context` 0), 갈래 1 = 둘 다 켬, 고정 질문 5개, `critic_scope` 0, 갈래마다 제 계획으로 승인(`--plan own` — shared 면 넓히기 효과가 0 이다). 판정 도구는 06c worktree 의 `scripts/research_eval/`(Task V1·V2)을 개발 PC 에서 운영 게이트웨이 API 로 돌린다(06b D18 재판정과 같은 길 — `scripts/` 는 앱 이미지에 없다, 함정 4). 운영에 잡을 만드므로 **사용자 승인 뒤** 한다. 새 논문 줄의 라벨은 06a·06b 와 같은 위임(Claude 판정자 셋 + 최종 판정)이다(사용자 이견이 없으면 — §12-7).

**Files:** 없음(저장소 밖 작업 폴더 `C:/Users/LANDSOFT/round06c-eval/` — 실행 JSON·라벨 사본·새 줄 재료. 저장소에는 Task Z8 이 가져온다)

**알아 둘 것:**
- 이 Task 의 명령은 개발 PC 의 Git Bash 에서 06c worktree 를 cwd 로 돈다. 한글이 깨지면 `PYTHONIOENCODING=utf-8` 을 앞에 붙인다(아래 명령에 붙여 두었다).
- 잡 10개가 차례로 돈다(실행 워커 하나 — 약 20~25분). 셸이 끊기지 않게 돌리거나, 끊기면 `실패한 질문 …` 줄의 `--only …` 로 같은 `--out` 에 다시 돌린다.
- Task Z5 의 잡이 끝난 뒤 시작한다.

- [ ] **Step 1: 작업 폴더와 라벨 사본**

```bash
EVAL=C:/Users/LANDSOFT/round06c-eval; API=http://192.168.12.57:92/api
mkdir -p $EVAL/labels
cp C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/scripts/research_eval/labels/*.csv $EVAL/labels/
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python -c "import csv,glob; rows=[r for p in sorted(glob.glob('$EVAL/labels/*.csv')) for r in csv.DictReader(open(p, encoding='utf-8-sig', newline=''))]; print(len(rows), sum(r['label']=='관련' for r in rows), sum(not (r.get('label') or '').strip() for r in rows))"
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.12.57:92/health
```

Expected: `318 128 0`(06b D18 재판정 뒤의 라벨 — 저장소 판이 기준이다), `200`. 개발 PC 에서 돌리므로 서버의 `labels/` 를 맞출 일이 없다.

- [ ] **Step 2: 06b 참고값 — 새 `score.py` 로 06b D18 RUN 을 다시 센다**

spec §12-7 표의 06b 참고 열('기록 없음 — 계획에서 06b 잡으로 센다' 칸 포함)이 이것이다. 06b RUN 파일은 06b 판정 폴더에 있다. 없으면 06b 완료노트 §5-4 의 잡 id 표로 다시 쓴다:

```bash
ls C:/Users/LANDSOFT/round06b-eval/pairs_20261008_d18.json || cat > C:/Users/LANDSOFT/round06b-eval/pairs_20261008_d18.json <<'JSON'
{"computing": {"0": "d8348de8-ee7f-48f9-8ceb-20924ed6a383", "1": "c22d98c0-5bcb-41f1-8d06-ca01b7b1f630"},
 "library": {"0": "f852b920-2bf8-4f0f-a833-649af37944bf", "1": "6549ca61-4924-4070-bbb6-14f5b8c3156e"},
 "elderly": {"0": "ff5cb5b9-f67d-49c0-a900-f02d36d3fd99", "1": "2cafdcd0-fee5-4974-a636-cc57ef39a896"},
 "multicultural": {"0": "03ff48a5-84c3-48af-b74d-d6f75beb7d74", "1": "9132dffc-0b03-4286-a18a-72fc3b400ee9"},
 "csr": {"0": "ce0894d9-0ccf-40ff-bd7d-c9d4da7a7510", "1": "f583e55e-3951-484e-a5b2-38ff70259c58"}}
JSON
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python scripts/research_eval/score.py --api $API --pairs C:/Users/LANDSOFT/round06b-eval/pairs_20261008_d18.json --labels-dir $EVAL/labels | tee $EVAL/score_06b_reference.txt
```

Expected: 기존 줄(질문마다 갈래별 `절별 무관 …`·`보고서 정밀도 …`, `합격 질문: 갈래 0 0/5 · 갈래 1 2/5`, 합계 두 줄 `보고서 정밀도 합계(채점한 5개 질문): 갈래 0 73.0% (관련 65 · 무관 24, 라벨 없음 0편) · 갈래 1 61.3% (관련 57 · 무관 36, 라벨 없음 0편)`·`제외 판정의 관련 합계: 갈래 0 관련 35/라벨 107 (제외 107편) · 갈래 1 관련 0/라벨 0 (제외 0편)`)이 06b 완료노트 §5-4 '06b 채점' 출력과 글자 그대로 같다(Task V2 가 기존 출력을 바꾸지 않았다). 그 사이에 갈래마다 새 두 줄 `  갈래 n  넓힌 질문: (기록 없음)`(06c 전 잡)·`  갈래 n  계획 지표  일반 틀 g/6 · 근거 0편 z · insufficient i · 계획 -`, 끝에 `계획 지표 합계(채점한 5개 질문): 갈래 0 일반 틀 25/30 (83.3%) · … · 계획 p50 - · 갈래 1 일반 틀 25/30 (83.3%) · …`. 일반 틀은 두 갈래가 같다(06b 는 갈래 1 을 갈래 0 계획으로 승인했다) — 질문별로 computing 6 · library 6 · elderly 3 · multicultural 6 · csr 4(csr 은 원 질문의 '재무성과' 때문에 '성과' 를 세지 않는다)로 spec 표의 '약 25/30' 과 맞는다. 기존 줄이 06b 출력과 다르면 멈추고 score.py 의 기존 출력 변경부터 본다. 근거 0편·insufficient 합계를 완료노트 §5-4 의 06b 참고 열에 적는다.

- [ ] **Step 3: 두 갈래 실행 — 갈래마다 제 계획**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
RUN=pairs_$(date +%Y%m%d)_06c; echo "$RUN"                                             # 이 이름을 끝까지 쓴다
PYTHONIOENCODING=utf-8 python scripts/research_eval/run_pair.py --api $API --plan own \
  --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' \
  --param '{"critic_scope": 0, "broaden": 1, "query_context": 1}' \
  --out $EVAL/$RUN.json 2>&1 | tee $EVAL/$RUN.out
grep -c '"0":' $EVAL/$RUN.json
```

Expected: 첫 줄 `갈래 0 {"critic_scope": 0, "broaden": 0, "query_context": 0} · 갈래 1 {"critic_scope": 0, "broaden": 1, "query_context": 1} · 계획 own`(Task V1 — 어느 파라미터로 돌렸는지, 완료노트 §5-4 에 남긴다), 그 뒤 질문마다 `[<질문키>] <질문>`·`  갈래 0 <잡 id>`·`  갈래 1 <잡 id>`·`  완료: 갈래 0 … · 갈래 1 …` 네 줄 × 5, 마지막 `grep` `5`. `실패한 질문 …` 줄이 있으면 그 줄의 `--only …` 를 붙여 같은 `--out` 으로 다시 돌린다.

두 갈래의 계획·넓힌 질문·범위 용어·검색어를 나란히 본다(넓히기 효과의 첫 확인):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python - "$API" "$EVAL/$RUN.json" <<'PY' | tee $EVAL/${RUN}_plans.txt
import json, sys
import httpx
api, path = sys.argv[1], sys.argv[2]
with httpx.Client(timeout=30.0) as client:
    for key, arms in json.load(open(path, encoding="utf-8")).items():
        print(f"[{key}]")
        for arm in ("0", "1"):
            res = client.get(f"{api}/research/{arms[arm]}")
            res.raise_for_status()
            job = res.json()
            plan_steps = [s for s in job["steps"] if s["kind"] == "plan"]
            result = (plan_steps[-1]["result"] if plan_steps else None) or {}
            p = job["params"]
            print(f"  갈래 {arm} broaden={p.get('broaden')} query_context={p.get('query_context')}"
                  f" · 계획 {result.get('elapsed_ms')}ms · 범위 용어 {result.get('terms')}")
            print(f"    넓힌 질문: {result.get('question_used')}")
            for i, sq in enumerate(job.get("plan") or [], 1):
                print(f"    {i}. {sq}")
            for t in (job.get("report") or {}).get("trail") or []:
                print(f"    검색어: {t.get('queries')}")
PY
```

Expected: 질문마다 두 갈래. 갈래 0 — `broaden=0 query_context=0`, 범위 용어 `[]`, 넓힌 질문 = 원 질문, 첫 검색어 = 하위질문 글. 갈래 1 — `broaden=1 query_context=1`, 넓힌 질문이 원 질문 낱말을 모두 품은 한 문장(또는 원 질문 그대로 — 검사에서 떨어졌거나 이미 구체적), 범위 용어 2~4개(넓히기가 원문으로 물러났으면 `[]`), 검색어에 '국내 학술논문에서' 가 없고 하위질문에 없던 범위 용어가 붙었다, 계획 시간 수천 ms(5,000ms 안팎 이하가 목표). 출력 파일을 완료노트 §5-4 에 붙인다. 넓히기가 원문으로 물러난 수는 서버에서 센다(사용자):

```bash
docker logs --since 2h nl-lib-celery-research-plan 2>&1 | grep '\[framing\]'
docker logs --since 2h nl-lib-celery-research-plan 2>&1 | grep -c '\[framing\]'                              # 물러난 잡 수
docker logs --since 2h nl-lib-celery-research-plan 2>&1 | grep -c '\[framing\] 넓힌 질문이 원 질문 낱말'          # 낱말 검사에서 떨어진 수
```

Expected: 첫 명령은 경고 줄 그대로, 둘째는 물러난 잡 `0`~`5` — 원문으로 물러날 때마다 정확히 한 줄이다(Task C3). 까닭은 넓히기 호출 실패·JSON 객체를 읽지 못함·question 이 문자열 아님·비었거나 500자 초과·원 질문 낱말 빠짐 중 하나다. 셋째는 둘째 이하의 수다(`grep -c` 의 `0` 은 종료 코드 1 이 정상 값이다). 두 수와 까닭을 완료노트 §5-4 에 적는다(이월 4 의 재료).

- [ ] **Step 4: 라벨 파일에 새 논문만 덧붙이고 판정 재료를 뽑는다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python scripts/research_eval/make_labels.py --api $API --pairs $EVAL/$RUN.json --out-dir $EVAL/labels
```

Expected: `[<질문키>] N편(새 n) -> …/labels/<질문키>.csv` 다섯 줄 — `n` 을 적는다(spec 예상 합계 100~150).

새 줄(라벨 칸이 빈 줄)의 제목·초록·키워드를 질문별 파일로 뽑는다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python - "$API" "$EVAL" <<'PY'
import csv, json, sys
from pathlib import Path
import httpx
api, ev = sys.argv[1], Path(sys.argv[2])
questions = {q["key"]: q["question"] for q in json.loads(Path("scripts/research_eval/questions.json").read_text(encoding="utf-8"))}
with httpx.Client(timeout=30.0) as client:
    for key, question in questions.items():
        rows = []
        with open(ev / "labels" / f"{key}.csv", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("label") or "").strip():
                    continue
                res = client.get(f"{api}/books/{row['cnts_id']}")
                res.raise_for_status()
                book = res.json()
                rows.append({"key": key, "question": question, "cnts_id": row["cnts_id"], "title": book.get("title"),
                             "abstract": book.get("abstract"), "keyword": book.get("keyword")})
        (ev / f"newrows_{key}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{key}] 새 줄 {len(rows)}")
PY
```

Expected: 다섯 줄 `[<질문키>] 새 줄 n` — make_labels 의 '새 n' 과 질문마다 같다.

- [ ] **Step 5: (Claude 판정자 — 06a·06b 와 같은 위임) 새 줄 라벨**

라벨 기준은 원 질문이다 — 하위질문에서 벗어났어도 원 질문의 주제를 다루면 `관련`, 같은 단어를 다른 뜻으로 쓴 논문을 포함해 원 질문과 무관하면 `무관`(README 흐름 5). 이미 단 318줄은 고치지 않는다.

- 질문마다 `$EVAL/newrows_<질문키>.json` 의 줄을 서로 모르는 판정자 셋(서브에이전트 셋 — 셋의 줄 순서를 다르게)에게 원 질문·기준·제목·초록·키워드만 주고(갈래·채택/제외 정보를 주지 않는다) 따로 달게 한다. 표가 갈린 줄은 최종 판정자가 기준대로 다시 본다.
- `$EVAL/labels/<질문키>.csv` 의 **라벨 칸이 빈 줄에만** `label` 과 `메모`(`Claude 만장일치 3·0: <이유>` / `Claude 최종 판정(관련 a·무관 b): <이유>`)를 채운다 — 다른 줄과 칸은 손대지 않는다. 엑셀로 열지 않는다(BOM·`메모` 칸 유지 — 파이썬 `csv` 로 `encoding="utf-8-sig"` 로 읽고 `newline=""` 로 쓴다).
- 사람이 고칠 때(사용자가 원하면): 판정이 끝난 파일을 엑셀로 열어 고칠 줄의 `label` 을 바꾸고 `메모` 칸에 "기획자 수정: <이유>" 를 쓴 뒤 'CSV UTF-8' 로 저장한다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python -c "import csv,glob; rows=[r for p in sorted(glob.glob('$EVAL/labels/*.csv')) for r in csv.DictReader(open(p, encoding='utf-8-sig', newline=''))]; print(len(rows), sum(r['label']=='관련' for r in rows), sum(not (r.get('label') or '').strip() for r in rows))"
```

Expected: `<318 + 새 줄 합계> <관련 수> 0` — 라벨 칸이 빈 줄 0. 새 줄 수·판정자 셋의 표가 같은 줄 수·최종 판정 줄 수·사람이 고친 줄 수를 적는다(완료노트 §5-4).

- [ ] **Step 6: 채점**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python scripts/research_eval/score.py --api $API --pairs $EVAL/$RUN.json --labels-dir $EVAL/labels | tee $EVAL/score_$RUN.txt
```

Expected: 질문마다 `[<질문키>] <질문>` 과 갈래마다 네 줄(`절별 무관 …  과잉 제외 …  라벨 없음 0편  -> 합격|불합격` · `보고서 정밀도 …` · `넓힌 질문: …` · `계획 지표  일반 틀 g/6 · 근거 0편 z · insufficient i · 계획 s초`), `합격 질문: 갈래 0 a/5 · 갈래 1 b/5`, 합계 셋(`보고서 정밀도 합계 …`·`제외 판정의 관련 합계 …`·`계획 지표 합계(채점한 5개 질문): …`). `판정 보류`·`라벨 칸이 빈 논문이 …` 가 있으면 Step 5 로 돌아가 마저 단다. `채점하지 못한 질문 …` 이 있으면 그 질문의 라벨(Step 4)이나 잡(Step 3 `--only`)부터 다시 한다. 판정은 이 둘이 모두 없는 출력으로만 한다. 합격 x/5 와 '제외 판정의 관련 합계' 는 함께 적되 판정에 쓰지 않는다(§12-7 — 06b 갈래 0 의 0/5 는 주로 과잉 제외 때문이라 계획이 좋아져도 움직이지 않을 수 있다).

- [ ] **Step 7: 대조군 — 넓히기가 이미 구체적인 질문을 그대로 두는가**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python scripts/research_eval/run_pair.py --api $API --questions scripts/research_eval/questions_control.json --plan own \
  --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' \
  --param '{"critic_scope": 0, "broaden": 1, "query_context": 1}' \
  --out $EVAL/${RUN}_control.json 2>&1 | tee $EVAL/${RUN}_control.out
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && PYTHONIOENCODING=utf-8 python scripts/research_eval/score.py --api $API --plan-only --questions scripts/research_eval/questions_control.json --pairs $EVAL/${RUN}_control.json | tee $EVAL/score_${RUN}_control.txt
```

Expected: run_pair 의 첫 줄은 Step 3 과 같은 `갈래 0 {"critic_scope": 0, "broaden": 0, "query_context": 0} · 갈래 1 {"critic_scope": 0, "broaden": 1, "query_context": 1} · 계획 own`, 그 뒤 `ctl_elderly`·`ctl_library` 두 질문을 완료(잡 4개, 약 8분). score 는 질문마다 `[<키>] <질문>` 과 갈래마다 `넓힌 질문:`·`계획 지표` 두 줄, 끝에 `계획 지표 합계(채점한 2개 질문): …` 한 줄 — `합격 질문:`·보고서 정밀도 줄은 없다. **대조군 통과** = 갈래 1 의 `넓힌 질문:` 이 `(원 질문 그대로)` 이거나 원 질문의 논문 제목·키워드 셋을 모두 품고 주제를 바꾸지 않았고, 갈래 1 의 일반 틀 비율이 갈래 0 보다 높지 않고 근거 0편 합계가 갈래 0 보다 크지 않다.

- [ ] **Step 8: 판단(Q4) — 기준은 같은 날 갈래 0**

Step 6·7 의 합계 줄로 표를 만든다(완료노트 §5-4 에 그대로 — 06b 참고 열은 Step 2):

| 지표 | 좋아짐(갈래 1 이 갈래 0 대비) |
|---|---|
| 보고서 정밀도 합계 | 같거나 높다 |
| 관련 편수(보고서 정밀도 합계 줄의 '관련') | 같거나 많다 |
| 일반 틀 비율(`계획 지표 합계` 줄의 괄호 %) | 낮다 |
| 근거 0편 합계 | 같거나 적다 |
| insufficient 합계 | 같거나 적다 |
| 계획 p50 | 갈래 1 이 5.0초 이하 |
| 대조군 | Step 7 의 '대조군 통과' |

§12-7 의 세 갈래(모두 좋아지면 켬 · 엇갈리면 나눠 다시 · 아니면 0)를 이 표로 이렇게 읽는다(정함(권고) — '같거나' 칸은 지키는 조건이라, 실제로 나아졌는지는 핵심 둘로 가른다):
- **일곱 모두 '좋아짐' → 두 스위치 1**(Task Z7 의 (가)).
- **엇갈림** — 일곱 중 '좋아짐' 이 아닌 것이 있지만 핵심 둘 중 하나 이상이 엄밀히 나아졌다(① 일반 틀 비율이 낮아졌다 — 넓히기의 몫, ② 보고서 정밀도 합계가 높아졌거나 관련 편수가 늘었다 — 검색어 합성의 몫) **→ Step 9 로 스위치를 나눠 다시 판정한다.**
- **아니면**(핵심 둘 모두 엄밀히 나아지지 않았다 — 일반 틀 비율이 그대로이거나 높아졌고, 보고서 정밀도·관련 편수가 그대로이거나 줄었다) **→ 0 그대로**(Task Z7 건너뜀). 까닭과 다음 경로(예: 넓히기 프롬프트를 다시 볼지 — 06c 안에서는 고치지 않는다)를 완료노트 §5-4·§7 에 적고 사용자에게 알린다.

판단 문장과 까닭(어느 칸이 어떻게 움직였는지)을 적어 둔다 — 완료노트 §5-4 와 spec Q4(Task Z8)가 그대로 쓴다.

- [ ] **Step 9: (엇갈렸을 때만) 스위치를 나눠 다시 판정 — 정함 20**

두 RUN 을 더 돌린다(각 잡 10개 약 20분 + 새 줄 라벨). 기준은 각 RUN 안의 갈래 0 이다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
# query_context 효과 — 계획은 같고(갈래 1 을 갈래 0 계획으로 승인) 검색어만 다르다. 갈래 1 의 계획 단계가 범위 용어를 낸다
RUN_Q=pairs_$(date +%Y%m%d)_06c_q
PYTHONIOENCODING=utf-8 python scripts/research_eval/run_pair.py --api $API --plan shared \
  --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' \
  --param '{"critic_scope": 0, "broaden": 1, "query_context": 1}' \
  --out $EVAL/$RUN_Q.json 2>&1 | tee $EVAL/$RUN_Q.out
# broaden 효과 — 계획만 다르고 검색어는 합성하지 않는다
RUN_B=pairs_$(date +%Y%m%d)_06c_b
PYTHONIOENCODING=utf-8 python scripts/research_eval/run_pair.py --api $API --plan own \
  --param0 '{"critic_scope": 0, "broaden": 0, "query_context": 0}' \
  --param '{"critic_scope": 0, "broaden": 1, "query_context": 0}' \
  --out $EVAL/$RUN_B.json 2>&1 | tee $EVAL/$RUN_B.out
```

Expected: 두 RUN 모두 첫 줄에 갈래 파라미터·계획 모드 — `RUN_Q` 는 `갈래 0 {"critic_scope": 0, "broaden": 0, "query_context": 0} · 갈래 1 {"critic_scope": 0, "broaden": 1, "query_context": 1} · 계획 shared`, `RUN_B` 는 `갈래 0 {"critic_scope": 0, "broaden": 0, "query_context": 0} · 갈래 1 {"critic_scope": 0, "broaden": 1, "query_context": 0} · 계획 own` — 그리고 `완료:` 다섯 줄. 각 RUN 에 Step 4(make_labels — 같은 `$EVAL/labels` 에 덧붙인다)·Step 5(새 줄 라벨)·Step 6(score — `--pairs $EVAL/$RUN_Q.json`·`$EVAL/$RUN_B.json`, 출력 `score_$RUN_Q.txt`·`score_$RUN_B.txt`)을 그대로 한다.

스위치마다 정한다:
- `query_context` = 1: `RUN_Q` 에서 보고서 정밀도·관련 편수가 같거나 높고 근거 0편·insufficient 가 같거나 적다. 아니면 0.
- `broaden` = 1: `RUN_B` 에서 일반 틀 비율이 낮고, 보고서 정밀도·관련 편수가 같거나 높고, 근거 0편·insufficient 가 같거나 적고, 계획 p50 5.0초 이하이고, Step 7 대조군 통과. 아니면 0.

결과 `(broaden, query_context)` 가 `(1, 1)` 이면 Task Z7 (가), `(1, 0)` 이면 (나), `(0, 1)` 이면 (다), `(0, 0)` 이면 Task Z7 을 건너뛴다. 결정과 까닭을 적는다(완료노트 §5-4·§6, spec Q4 — Task Z8).

---

### Task Z7: 기본값 커밋 — 판정 결과(Q4)대로, 10/17~18 배포에 싣는다

**왜:** §12-6 — 기본값 커밋은 판정 날 바로 배포하지 않고 10/17~18 배포(06e·06d)에 싣는다(배포 한 번을 아끼고 10/19~21 운영 확인이 켠 상태로 돈다). 06c 는 이미 dev 에 있으므로 dev 에서 분기한 작은 브랜치에서 커밋하고 dev 머지(사용자 승인)로 올린다 — 06c worktree 의 `feat/round06c-query-broadening` 은 dev 에 들어가 있어 브랜치를 바꿔도 된다(본 작업 폴더에서는 바꾸지 않는다). Task Z6 의 결과가 `(0, 0)` 이면 이 Task 를 건너뛴다.

**Files:**
- Modify: `app/services/research/state.py`(`DEFAULT_PARAMS` 의 켜는 칸 값 — 주석은 0·1 의 뜻이라 그대로 맞다)
- Modify: `app/tests/test_research_state.py`(Task C2 의 `TestMergeParams.test_query_switches_are_off_by_default` → `test_query_switch_defaults_follow_the_06c_verdict`)
- Modify: `app/tests/test_research_api.py`(Task C2 의 `TestCreate.test_query_switches_are_saved_off_unless_asked` → `test_query_switches_are_saved_with_their_defaults_unless_asked`)

**알아 둘 것:**
- 기본값을 단언하는 테스트는 이 둘뿐이다 — 다른 06c 테스트는 스위치 값을 적었고(Task C4 `job.params = {"broaden": 0}`, C6 `merge_params({"query_context": 0, …})`), 계획 태스크를 도는 기존 테스트 다섯(`TestPlan`·`TestStatusEvents`, `_FakeJob.params = {}`)은 `TestPlan._patch` 가 넓히기를 늘 대역으로 바꾸므로(Task C4) 진짜 `chat`(HTTP·재시도, 20초 마감)을 부르지 않는다. `_statuses(h)` 는 status 이벤트만 거르므로 중간 알림(step 이벤트)이 늘어도 그대로다.
- 기본값을 켠 뒤에는 `run_pair.py` 의 기본 갈래 0(`DEFAULT_PARAMS0 = {"critic_scope": 0}`)이 켠 스위치를 따라가므로, 이후 재판정(리허설 10/23~25 포함)은 늘 `--param0` 에 두 칸을 적는다(Task Z6 Step 3 처럼).
- **10/17~18 전에는 dev 로 fastapi·워커 이미지를 빌드·배포하지 않는다** — 기본값이 그때 켜진다. 그 배포가 celery-research·celery-research-plan·fastapi 를 같은 이미지로 Recreate 한다(§12-6).

- [ ] **Step 1: dev 에서 분기한 브랜치**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
git status --short                                                                    # 비어 있어야 한다(판정 파일은 저장소 밖 폴더에 있다)
git fetch origin dev:dev && git switch -c fix/round06c-defaults dev
```

Expected: `Switched to a new branch 'fix/round06c-defaults'`. fetch 가 실패하면 Task Z4 Step 2 의 안내대로 푼 뒤 다시.

- [ ] **Step 2: 바꾸기 전 수를 센다(이 Task 의 '묶음 명령' — 열 파일)**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_state.py tests/test_research_api.py tests/test_research_tasks.py tests/test_research_runner.py tests/test_research_framing.py tests/test_research_terms.py tests/test_research_eval.py tests/test_research_planner.py tests/test_prompts.py tests/test_research_critic.py -q -p no:cacheprovider`

Expected: 실패 0. 나온 `K passed` 를 적어 둔다 — 아래를 고친 뒤에도 같은 K 다(테스트 둘의 이름과 기대만 바꾼다). K 는 06c 전 여덟 파일(`test_research_state`·`api`·`tasks`·`runner`·`eval`·`planner`·`prompts`·`critic`)의 516(2026-10-08 실측) + 파트 C·V 가 이 열 파일에 더한 수다. 계획대로면 **K = 640**(516 + 124 — state 94 · api 124 · tasks 118 · runner 98 · framing 27 · terms 35 · eval 47 · planner 18 · prompts 9 · critic 70). 06c 전 여덟 파일의 기준선이 516 과 다르거나 06c 머지 뒤 dev 에 이 열 파일의 테스트가 더 들어왔으면 그 차이만큼 옮겨 읽는다.

- [ ] **Step 3: 기본값을 바꾸고 기본값 테스트 둘만 깨지는 것을 본다**

`app/services/research/state.py` — 켜는 스위치의 값만 바꾼다(Edit 의 old 는 `DEFAULT_PARAMS` 안의 그 글자 — `_PARAM_BOUNDS` 의 `"broaden": (int, 0, 1),` 와 겹치지 않는다).
- `broaden` 을 켤 때((가)·(나)) — old `"broaden": 0,` → new `"broaden": 1,`
- `query_context` 를 켤 때((가)·(다)) — old `"query_context": 0,` → new `"query_context": 1,`

Run: Step 2 의 묶음 명령.

Expected: `2 failed` — 이 둘뿐이다:
- `tests/test_research_state.py::TestMergeParams::test_query_switches_are_off_by_default`
- `tests/test_research_api.py::TestCreate::test_query_switches_are_saved_off_unless_asked`

다른 실패가 나오면 멈추고 그 테스트가 기본값(`{}`)에 기대는지 본다 — 그 테스트도 스위치 값을 적도록 고쳐 같은 커밋에 넣고, 까닭을 완료노트 §5-6 에 적는다.

- [ ] **Step 4: 기본값 테스트 둘을 판정 결과로 바꾼다**

`app/tests/test_research_state.py` — `TestMergeParams` 안의 `def test_query_switches_are_off_by_default(self):` 줄부터 그 함수의 끝(다음 `def` 앞 빈 줄)까지를 Read 로 읽어 old 로 잡고, 아래로 바꾼다. 튜플은 결과대로 하나만 쓴다 — (가) `(1, 1)` · (나) `(1, 0)` · (다) `(0, 1)`.

```python
    def test_query_switch_defaults_follow_the_06c_verdict(self):
        # 06c 두 갈래 판정(완료노트 §5-4)으로 켠 스위치만 1 이다 — 0 의 뜻(원 질문 그대로 계획·하위질문 글자 그대로
        # 검색)은 잡 파라미터로 언제든 고를 수 있다
        assert (DEFAULT_PARAMS["broaden"], DEFAULT_PARAMS["query_context"]) == (1, 1)
```

`app/tests/test_research_api.py` — `TestCreate` 안의 `def test_query_switches_are_saved_off_unless_asked(self, api):` 함수 전체를 같은 방법으로 아래로 바꾼다. 첫 잡의 튜플은 위와 같은 값이다.

```python
    def test_query_switches_are_saved_with_their_defaults_unless_asked(self, api):
        # 지정하지 않은 잡은 06c 판정으로 정한 기본값을, 지정한 잡은 그 값을 저장한다 — 판정 도구의 갈래 0 이 늘 0 을 적는다
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"})
        assert res.status_code == 200
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"broaden": 0, "query_context": 0}})
        assert res.status_code == 200
        first, second = api.db.jobs.values()
        assert (first["params"]["broaden"], first["params"]["query_context"]) == (1, 1)
        assert (second["params"]["broaden"], second["params"]["query_context"]) == (0, 0)
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests/test_research_state.py tests/test_research_api.py tests/test_research_tasks.py tests/test_research_runner.py tests/test_research_framing.py tests/test_research_terms.py tests/test_research_eval.py tests/test_research_planner.py tests/test_prompts.py tests/test_research_critic.py -q -p no:cacheprovider --durations=5`

Expected: 실패 0, Step 2 와 같은 `K passed`. `slowest 5 durations` 목록에 10초 넘는 테스트가 없다(넓히기가 진짜 HTTP 로 20초 마감까지 기다리는 테스트가 없다 — Task C4 의 대역이 기본값 1 에서도 막는다).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: `5 failed, N passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 기준선과 같은 세 파일, N 은 Task Z1 Step 4 의 N 과 같다(06c 머지 뒤 dev 에 다른 라운드의 테스트가 들어왔으면 그만큼 다르다).

- [ ] **Step 5: 커밋 — 결과에 맞는 블록 하나만**

① (가) 둘 다 켤 때:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/services/research/state.py && git add app/tests/test_research_state.py && git add app/tests/test_research_api.py && git status --short && git commit -m "[Feat] round06c — 판정 결정을 켠다: DEFAULT_PARAMS broaden·query_context 0 → 1 — 06c 두 갈래 판정에서 넓히기·검색어 합성을 켠 갈래가 같은 날 갈래 0 보다 보고서 정밀도·관련 편수가 같거나 높고 일반 틀 비율이 줄고 근거 0편·insufficient 가 늘지 않았으며 계획 p50 이 5초 이하, 대조군도 그대로였다(spec §12-7·Q4). 새 잡부터 켜지고 이미 만든 잡은 저장된 params 그대로다. 10/17~18 배포(celery-research·celery-research-plan·fastapi)에 싣는다. 기본값 테스트 둘은 판정 결과를 단언하도록 이름과 기대를 바꾼다"
```

② (나) `broaden` 만 켤 때:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/services/research/state.py && git add app/tests/test_research_state.py && git add app/tests/test_research_api.py && git status --short && git commit -m "[Feat] round06c — 판정 결정을 켠다: DEFAULT_PARAMS broaden 0 → 1, query_context 는 0 그대로 — 06c 판정이 엇갈려 스위치를 나눠 다시 판정했고(--plan own + 갈래 1 broaden 1·query_context 0) 넓히기만 일반 틀 비율을 낮추면서 보고서 정밀도·관련 편수를 지키고 근거 0편·insufficient 를 늘리지 않았다(spec §12-7·Q4). 새 잡부터 켜지고 이미 만든 잡은 저장된 params 그대로다. 10/17~18 배포에 싣는다. 기본값 테스트 둘은 판정 결과를 단언하도록 이름과 기대를 바꾼다"
```

③ (다) `query_context` 만 켤 때:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add app/services/research/state.py && git add app/tests/test_research_state.py && git add app/tests/test_research_api.py && git status --short && git commit -m "[Feat] round06c — 판정 결정을 켠다: DEFAULT_PARAMS query_context 0 → 1, broaden 은 0 그대로 — 06c 판정이 엇갈려 스위치를 나눠 다시 판정했고(--plan shared + 갈래 1 broaden 1·query_context 1) 검색어 합성만 보고서 정밀도·관련 편수를 지키고 근거 0편·insufficient 를 늘리지 않았다(spec §12-7·Q4). broaden 0 이면 범위 용어가 비어 검색어 합성은 '국내 학술논문에서' 떼기만 한다. 새 잡부터 켜지고 이미 만든 잡은 저장된 params 그대로다. 10/17~18 배포에 싣는다. 기본값 테스트 둘은 판정 결과를 단언하도록 이름과 기대를 바꾼다"
```

Expected: `git status --short` 에 세 파일만 `M` 으로, 커밋 1개.

- [ ] **Step 6: (사용자 승인) dev 머지 — 배포는 하지 않는다**

Step 5 의 커밋과 Task Z6 의 판정 표를 사용자에게 보이고 "dev 에 머지하되 배포는 10/17~18 에 06e·06d 와 함께" 라는 승인을 받는다.

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/dev-merge dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge merge --no-ff fix/round06c-defaults -m "Merge fix/round06c-defaults into dev — round06c 판정 결정(기본값 — 10/17~18 배포에 싣는다)"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge push origin dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c dev-merge
```

Expected: 머지 커밋 한 줄(완료노트 §5-6 에 적는다), push 성공, 마지막 줄 `0`. 그 사이 dev 가 같은 파일(`state.py`·두 테스트)을 고쳐 충돌하면 사용자와 정한다.

머지한 뒤 06e·06d 세션(사용자)에게 알린다: "10/17~18 배포는 celery-research·celery-research-plan·fastapi 를 같은 이미지로 Recreate 하고, 배포 뒤 `DEFAULT_PARAMS` 의 `broaden`·`query_context` 를 확인한다(06c 계획 Task Z9)".

---

### Task Z8: 배포·판정 기록 — 기록 브랜치·dev 머지

**왜:** D13 — 완료노트에 배포·운영 확인·판정을 남기고, 라벨 CSV 를 저장소에 둔다(리허설 10/23~25 에 다시 쓴다). 06c 코드는 이미 dev 에 있으므로 기록 커밋은 dev 에서 분기한 브랜치에서 하고 dev 머지(사용자 승인)로 올린다.

**Files:**
- Modify: `docs/roadmap/round06c-완료노트.md`(머리 날짜·§5·§6 끝 줄·§7·상태), `docs/roadmap/00_status.md`(Task Z2 가 넣은 06c 구절), spec(머리 상태 줄·D25 끝·§12-10 Q4), `scripts/research_eval/README.md`('06c 재판정' 절 끝 결과), 필요하면 `docs/ops/recurring-gotchas.md`
- Modify(force add): `scripts/research_eval/labels/<질문키>.csv` 5개(덧붙인 판)

- [ ] **Step 1: 기록 브랜치와 라벨**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
git status --short                                                                    # 비어 있어야 한다
git fetch origin dev:dev && git switch -c docs/round06c-deploy-record dev
cp C:/Users/LANDSOFT/round06c-eval/labels/*.csv scripts/research_eval/labels/
git diff --stat -- scripts/research_eval/labels
git diff -- scripts/research_eval/labels | grep -c '^-[^-]'
```

Expected: 다섯 파일 모두 줄이 더해지기만 했다(`git diff --stat` 의 `+`), 마지막 줄 `0`(기존 318줄의 라벨·메모가 바뀌지 않았다). `0` 이 아니면 멈추고 그 줄을 본다 — make_labels 는 비어 있던 제목·저자만 채우므로 그런 줄만 허용한다.

- [ ] **Step 2: 완료노트 §5 를 채운다 (Edit 도구)**

머리 날짜 줄의 `` `dev` 머지·운영 배포·두 갈래 재판정은 §5`` 를 `` `dev` 머지 `<Task Z3 의 머지 커밋>` <날짜> · 운영 배포·처음부터 끝까지 1회·두 갈래 재판정 <날짜> — §5`` 로 바꾸고, §5 의 "배포 전 — …" 한 줄을 아래 하위 절로 바꾼다.

- **5-1. 머지와 이미지** — dev 머지 커밋(Task Z3), 빌드한 커밋(Task Z4 Step 2 — `빌드해도 된다:` 뒤 값), 다른 라운드를 ff-only 로 받았으면 그 사실과 다시 돈 테스트 수, 이미지 ID 앞 19자(`NEW`), 서버 되돌리기 태그 `:pre-round06c`.
- **5-2. 서버 배포** — Task Z4 Step 1·4~6 의 확인 결과(전제 — 이미지 넷 같음·`0007_research_work`·`q_research`, 워커 셋 → fastapi → reload, 컨테이너 안 `20 4 0 0`·`compose_query` 출력, 422 두 줄, `/health`·`/` 200, 머지 문을 연 시각).
- **5-3. 운영 처음부터 끝까지 1회** — 잡 `<J>`, Task Z5 의 출력 전체(params·plan step 결과·후보 이벤트 수·순서·모양·첫 검색어·rounds 칸·워커 오류 줄), 그리고 06a·06b 와 견준 표:

  | 단계 | 06a (`0a29e7d4`) | 06b (`d8348de8`) | 06c (`<J>`, 기본값 0) |
  |---|---|---|---|
  | 만들고 실행 시작까지 | 5초 | 5초 | `before_run_sec` |
  | 실행(탐색·종합) | 202초 | 144초 | `run_sec` |
  | 계획·탐색·종합 단계 | 1단계 2초 · 6단계 111초 · 1단계 91초 | 1단계 4초 · 6단계 83초 · 1단계 61초 | 둘째 질의 세 줄 |
  | plan step `elapsed_ms` | — | — | Step 1 의 값 |
  | 화면 | — | — | Task Z5 Step 4 에서 본 것 |

- **5-4. 두 갈래 재판정** — `RUN` 이름과 잡 id 표(질문 × 갈래), 대조군 RUN 의 잡 id, 각 RUN 출력의 첫 줄(갈래 파라미터·계획 모드 — `$RUN.out`·`${RUN}_control.out`, 나눠 판정했으면 `$RUN_Q.out`·`$RUN_B.out` 도), Step 3 의 계획·넓힌 질문·범위 용어·검색어 출력(`${RUN}_plans.txt`), `[framing]` 경고 두 수(물러난 잡 수 `grep -c '\[framing\]'`·낱말 검사에서 떨어진 수 `grep -c '\[framing\] 넓힌 질문이 원 질문 낱말'`)와 까닭, 라벨(새 줄 수·판정자 일치 수·최종 판정 수·사람이 고친 줄 수), `score.py` 출력 전체(Step 2 의 06b 참고·Step 6·Step 7 대조군, 나눠 판정했으면 `RUN_Q`·`RUN_B` 도), Step 8 의 판정 표(06b 참고 · 같은 날 갈래 0 · 갈래 1), 판정과 그 까닭(나눠 판정했으면 스위치마다).
- **5-5. 결정 커밋** — Task Z7 을 했으면 그 커밋·dev 머지 커밋·'10/17~18 배포에 싣는다', 안 했으면 "기본값 0 그대로 — 결정 커밋 없음"과 까닭.

§6 표 아래 문단의 "열린 질문 Q4(기본값)는 §5 의 판정으로 닫는다." 를 "열린 질문 Q4(기본값)는 §5-4 의 판정으로 닫았다 — `broaden` <0|1> · `query_context` <0|1>." 로 바꾼다. §7 이월에 판정에서 나온 것을 더한다(예: 넓히기가 원문으로 물러난 비율, 엇갈린 지표와 다음 경로, 계획 p50 이 5초를 넘었으면 그 값). '상태' 의 수동 스모크·두 갈래 재판정·문서 갱신·`dev` 머지 승인을 `[x]` 로(승인 문장과 날짜를 함께).

- [ ] **Step 3: README·00_status·spec·반복 함정 (Edit 도구)**

1. `scripts/research_eval/README.md` — '06c 재판정' 절(Task V2 가 만든 절) 끝에 `결과(<판정 날>):` 와 결과 요약 세 줄을 더한다: **실행**(`RUN` 이름·잡 수·실행 시간·대조군 RUN, 개발 PC 에서 운영 API 로), **라벨**(새 줄 수·방식 — 06a·06b 와 같은 위임, 사람이 고친 줄 수, 덧붙인 뒤 전체 줄 수·관련 수), **채점·결정**(일반 틀 비율 갈래 0 → 갈래 1, 보고서 정밀도 합계 두 갈래, 근거 0편·insufficient, 계획 p50, 대조군, 기본값 결정 — 출력 전체는 `docs/roadmap/round06c-완료노트.md` §5-4).
2. `docs/roadmap/00_status.md`:
   - 3행 — Task Z2 의 구절 `round06c — 시작 질문 넓히기·검색어 합성·탐색 후보 이벤트 구현 완료(스위치 \`broaden\`·\`query_context\` 기본 0), \`dev\` 머지·운영 배포·두 갈래 재판정 대기. ` 를 `round06c — \`dev\` 머지·운영 배포(워커 셋 → fastapi → reload)·처음부터 끝까지 1회·두 갈래 재판정(<판정 한 줄 — 예: 일반 틀 비율 83.3% → 30.0%, 보고서 정밀도 … → …>, 기본값 \`broaden\` <0|1> · \`query_context\` <0|1> — 10/17~18 배포에 싣는다). ` 로, 날짜를 이 Step 을 하는 날로.
   - 22행 머리 — `· 06c 구현 완료·\`dev\` 머지·운영 배포 대기**` 를 `· 06c 운영 배포·두 갈래 판정(<판정 날>)**` 로.
   - 06c 하위 줄 끝(`상세: \`round06c-완료노트.md\`.`) 뒤에 한 문장: `운영 배포·판정 <판정 날> — <판정 한 줄>, 기본값 커밋 \`<Task Z7 의 머지 커밋 또는 '없음'>\` 은 10/17~18 배포에 싣는다(완료노트 §5).`
   - 다음 할 일의 06c 줄 머리 — Task Z2 의 `  - **06c 질의 — 구현 완료, \`dev\` 머지·배포·두 갈래 재판정 대기(10/13~14 — 워커·fastapi)** — 계획 … 순서. 06d·06e 는 Z4 가 끝난 뒤에만 \`dev\` 에 머지한다.` 를 `  - **06c 질의 — 운영 배포·판정 끝(<판정 날>)** — 남은 것: 기본값 커밋이 10/17~18 배포에 실리는지와 배포 뒤 확인(계획 Task Z9 — 컨테이너의 기본값·새 잡 params·PlanCard 한 줄·랜딩 논문 예시 셋 보고서). 06d·06e 의 \`dev\` 머지 문은 열렸다.` 로.
   - 라운드 이력의 round06 칸 — `· 06c 구현 완료·배포 대기(\`feat/round06c-query-broadening\`)` 를 `· 06c 운영 배포·판정(<판정 날> — 기본값 \`broaden\` <0|1> · \`query_context\` <0|1>)` 로.
3. spec:
   - 3행 — Task Z2 의 `06c 구현 완료(2026-10-13 — 스위치 \`broaden\`·\`query_context\` 기본 0, \`dev\` 머지·운영 배포·두 갈래 재판정 대기)` 를 `06c 완료(<판정 날> 운영 배포·두 갈래 판정 — 기본값 \`broaden\` <0|1> · \`query_context\` <0|1>, 10/17~18 배포에 싣는다)` 로.
   - D25 행 — Task Z2 가 넣은 `(06c 계획 정함 1~22)` 바로 뒤에 `. **06c 판정(<판정 날>):** <일반 틀 비율·보고서 정밀도·근거 0편·계획 p50 한 구절>, 기본값 <결과>` 를 넣는다.
   - §12-10 Q4 — `- **Q4. 06c 판정 결과에 따른 기본값**(§12-7). [06c · 06c 판정 뒤(10/13~14) · §12-7 규칙 — 모두 좋아지면 켜고, 엇갈리면 나눠 다시 판정, 아니면 0]` 을 `- ~~**Q4. 06c 판정 결과에 따른 기본값**~~ — 해결(<판정 날>, §12-7 규칙): \`broaden\` <0|1> · \`query_context\` <0|1> — <한 줄 까닭>. 기본값 커밋은 10/17~18 배포에 싣는다(06c 완료노트 §5-4·§5-5).` 로.
4. `docs/ops/recurring-gotchas.md` — 운영 확인·판정에서 라이브에서만 드러난 패턴이 있었으면 `## 28. …`(증상·원인·해결·재발 방지)로 더한다. 없으면 고치지 않고 완료노트 §5 끝에 "반복 함정 — 더할 것 없음" 한 줄을 남긴다.

꺾쇠 자리는 모두 실측값으로 바꾼다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git diff -U0 -- "docs/roadmap/round06c-완료노트.md" docs/roadmap/00_status.md docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md scripts/research_eval/README.md docs/ops/recurring-gotchas.md | grep '^+[^+]' | grep -c '<[^>]*>'
```

Expected: `0`(더한 줄에 꺾쇠 자리가 남지 않았다 — 원래 있던 줄의 꺾쇠는 세지 않는다).

- [ ] **Step 4: 커밋하고 dev 머지(사용자 승인)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git add -f scripts/research_eval/labels/computing.csv scripts/research_eval/labels/library.csv scripts/research_eval/labels/elderly.csv scripts/research_eval/labels/multicultural.csv scripts/research_eval/labels/csr.csv && git add "docs/roadmap/round06c-완료노트.md" && git add docs/roadmap/00_status.md && git add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git add scripts/research_eval/README.md && git status --short && git commit -m "[Docs] round06c 운영 배포·판정 기록 — dev 머지·운영 배포(워커 셋 → fastapi → reload, 스키마 단계 없음, nuxt 그대로), computing 으로 처음부터 끝까지 1회(기본값 0 — 계획 입력·검색어 글자 그대로, 회차마다 candidates 한 번)와 단계 시간(06a·06b 표와 비교), 고정 질문 5개 두 갈래 재판정(갈래마다 제 계획, 덧붙인 라벨, 06b 참고값을 같은 도구로 다시 셈, 대조군)과 기본값 결정(Q4 — 10/17~18 배포에 싣는다). 라벨 CSV 5개(리허설에서 다시 쓴다)"
```

`docs/ops/recurring-gotchas.md` 를 고쳤으면 `git add docs/ops/recurring-gotchas.md` 를 `git status --short` 앞에 더한다.

Expected: `git status --short` 에 라벨 다섯·문서 넷(함정을 고쳤으면 다섯)만, 커밋 1개.

기록 커밋을 사용자에게 보이고 승인을 받은 뒤:

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/dev-merge dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge merge --no-ff docs/round06c-deploy-record -m "Merge docs/round06c-deploy-record into dev — round06c 운영 배포·두 갈래 판정 기록"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge push origin dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c dev-merge
```

Expected: 마지막 줄 `0`. 그다음 `dev→main` 머지·push(`/round-finish`)를 06c 에서 할지, round06 세 줄을 모두 마친 뒤 한 번에 할지 사용자에게 묻는다.

---

### Task Z9: (사용자, 서버·브라우저) 10/17~18 배포 뒤 06c 확인 — 기본값·화면 한 줄·랜딩 예시

**왜:** 06c 의 기본값 커밋과 화면 한 줄(PlanCard prop — 06d 가 `[id].vue` 에 잇는다)은 10/17~18 배포(06e·06d 계획의 배포)에 실려 나간다. §12-7 "켠 뒤 랜딩 논문 예시 셋(판정 질문과 같은 문장)의 보고서도 다시 본다". 그 배포가 06c 몫을 빠뜨리지 않았는지 06c 가 확인한다. Task Z7 을 건너뛰었으면(기본값 0) Step 1 의 기대값이 `0 0` 이고 Step 3 의 '이렇게 이해했어요' 는 보이지 않는다(바인딩만 확인한다).

**Files:** `docs/roadmap/round06c-완료노트.md`(§5-6 새 절)·`docs/roadmap/00_status.md`(06c 다음 할 일 줄) — Step 4 의 기록 커밋

- [ ] **Step 1: (사용자, 서버) 컨테이너의 기본값**

```bash
for c in nl-lib-fastapi nl-lib-celery-research nl-lib-celery-research-plan; do
  printf '%s ' $c; docker exec -w /app $c python -c "from services.research.state import DEFAULT_PARAMS as P; print(P['broaden'], P['query_context'])"
done
```

Expected: 세 줄 모두 Task Z6 의 결과(예: (가)면 `1 1`). 하나라도 다르면 그 배포가 06c 기본값 커밋 전 dev 로 빌드했거나 그 컨테이너를 Recreate 하지 않은 것이다 — 06e·06d 배포 담당(사용자)에게 알린다.

- [ ] **Step 2: (사용자, 서버) 랜딩 논문 예시 셋을 처음부터 끝까지**

```bash
API=http://localhost:92/api
for q in "노인의 우울과 사회적 지지에 관한 연구가 궁금해" "다문화가정 아동의 언어 발달에 관한 연구가 궁금해" "공공도서관 서비스 품질 평가 연구가 궁금해"; do
  J=$(curl -s -X POST $API/research -H 'Content-Type: application/json' -d "{\"question\":\"$q\"}" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
  until curl -s $API/research/$J | grep -q '"status":"awaiting_approval"'; do sleep 1; done
  curl -s -X POST $API/research/$J/approve > /dev/null
  echo "$J $q"
done
```

Expected: 잡 id 와 질문 세 줄(완료노트에 적는다). 셋이 차례로 돌아 약 8분 뒤 모두 `completed`(`curl -s $API/research/<J> | grep -o '"status":"[a-z_]*"' | head -1`).

```bash
for J in <위 세 잡 id>; do
  docker exec -i -e J=$J nl-lib-fastapi python - <<'PY'
import json, os, urllib.request
job = json.load(urllib.request.urlopen(f"http://localhost:8000/api/research/{os.environ['J']}"))
plan = [s for s in job["steps"] if s["kind"] == "plan"][-1]["result"]
print(job["status"], {k: job["params"][k] for k in ("broaden", "query_context")}, plan.get("elapsed_ms"), "ms")
print("  넓힌 질문:", plan.get("question_used"), "· 범위 용어:", plan.get("terms"))
print("  첫 검색어:", [t["queries"][:1] for t in job["report"]["trail"]])
PY
done
```

(`<위 세 잡 id>` 는 앞 명령이 찍은 세 id 를 공백으로 이어 넣는다.)

Expected: 셋 모두 `completed`, params 가 Step 1 과 같은 기본값, 켠 스위치대로 넓힌 질문·범위 용어·합성 검색어가 보인다.

- [ ] **Step 3: (사용자, 브라우저) 화면 한 줄과 보고서**

- 새 질문 하나(예: `컴퓨팅 자원에 대한 연구가 궁금해`)를 화면에서 시작한다 — 계획 중 대기 카드와 승인 대기 PlanCard 머리에 `이렇게 이해했어요: <넓힌 질문>` 한 줄이 보인다(`broaden` 1 이고 넓힌 질문이 원 질문과 다를 때만 — 같으면 줄이 없다). 승인하지 않고 취소해도 된다.
- Step 2 의 세 잡 보고서를 연다(`http://192.168.12.57:92/research/<J>`). 06c 판정의 같은 질문 갈래 1 보고서(완료노트 §5-4)와 견주어 무관 논문이 몰린 절·동음이의가 없는지 본다. 랜딩 예시 문구를 바꿀 것이 있으면(예: 넓힌 질문이 원 질문과 너무 달라 보고서가 엇나감) 06d 에 알린다(`pages/index.vue` 는 06d 파일 — §12-5).

- [ ] **Step 4: 기록 커밋 — dev 에서 분기한 브랜치, dev 머지(사용자 승인)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c
git status --short
git fetch origin dev:dev && git switch -c docs/round06c-defaults-check dev
```

완료노트 §5 끝에 `### 5-6. 10/17~18 배포 뒤 확인` 을 더한다(Step 1 의 세 줄, Step 2 의 잡 id·출력, Step 3 에서 본 것, 06d 에 넘긴 것). `00_status.md` 다음 할 일의 06c 줄(Task Z8 Step 3 의 `  - **06c 질의 — 운영 배포·판정 끝(<판정 날>)** — 남은 것: …` 줄)을 `  - **06c 질의 — 끝(<이 Step 을 하는 날>)** — 기본값 \`broaden\` <0|1> · \`query_context\` <0|1> 이 10/17~18 배포로 운영에 켜졌고 랜딩 논문 예시 셋을 다시 봤다(완료노트 §5-6).` 으로 바꾼다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06c && git diff -U0 -- "docs/roadmap/round06c-완료노트.md" docs/roadmap/00_status.md | grep '^+[^+]' | grep -c '<[^>]*>' ; git add "docs/roadmap/round06c-완료노트.md" && git add docs/roadmap/00_status.md && git status --short && git commit -m "[Docs] round06c — 10/17~18 배포 뒤 확인: 컨테이너 셋의 기본값(broaden·query_context), 랜딩 논문 예시 셋을 처음부터 끝까지 돌린 잡과 보고서, 계획 카드의 '이렇게 이해했어요' 한 줄(06d 바인딩)"
```

Expected: 첫 수 `0`, 커밋 1개. 사용자 승인 뒤 Task Z8 Step 4 와 같은 임시 worktree 명령으로 `docs/round06c-defaults-check` 를 dev 에 머지·push 하고 worktree 를 지운다(머지 메시지 `Merge docs/round06c-defaults-check into dev — round06c 10/17~18 배포 뒤 확인`, 마지막 줄 `0`).

---

#### 롤백 (사용자, 서버)

Task Z4~Z6 의 확인이 틀리거나 운영 오류가 나면 되돌린다. 06c 가 쓴 것(plan step result 의 새 칸·잡 params 의 새 키)은 지우지 않는다 — 다시 배포하면 그대로 쓴다.

1. 딥리서치가 빈 때 한다 — Task Z4 Step 4 의 두 질의가 모두 0행이고 세 워커의 `inspect active` 가 비었다.
2. 이미지 태그를 되돌린다: `docker tag landsoftdocker/nl-lib-fastapi:pre-round06c landsoftdocker/nl-lib-fastapi:latest`. 스키마·백업 되돌리기는 없다(06c 는 바꾸지 않았다).
3. **fastapi 를 먼저** 되돌린다 — Task Z4 Step 5 ④ 의 `idle in transaction` 질의가 0행인지 본 뒤 Portainer 에서 `nl-lib-fastapi` Recreate("Re-pull image" 끔). 새 fastapi 가 만든 잡은 params 에 `broaden`·`query_context` 가 있어 옛 워커의 `merge_params` 가 '알 수 없는 파라미터' 로 거부한다 — fastapi 를 되돌린 뒤 새로 만드는 잡은 괜찮지만, 06c 배포 동안 만들어 아직 끝나지 않은 잡(created·awaiting_approval·approved·queued)은 옛 워커에서 실패한다. 그런 잡이 있으면 끝나기를 기다리거나 사용자에게 알리고 다시 만들게 한다(끝난 잡은 영향이 없다).
4. 그다음 `nl-lib-celery-research-plan` → `nl-lib-celery-research` → `nl-lib-celery-control` 을 Recreate("Re-pull image" 끔) → `docker exec nl-lib-gateway nginx -s reload` → `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health` 가 `200`. `docker exec nl-lib-celery-research-plan ls /app/domains/nl_library/prompts/research_frame.yaml` 이 `No such file or directory` 면 옛 이미지다.
5. 되돌린 뒤에도 dev 에는 06c 가 있다(dev 머지가 배포보다 먼저다 — Task Z3). 고쳐서 다시 배포할지, dev 에서 06c 를 되돌릴지(revert, 사용자 승인) 정하기 전까지 dev 로 `fastapi`·`celery-research*`·`celery-control` 이미지를 빌드·Recreate 하지 않는다. 06d·06e 세션에도 머지 문이 다시 닫혔다고 알린다.
6. 기본값만 되돌릴 때(10/17~18 배포 뒤): dev 에서 분기한 브랜치에서 Task Z7 의 커밋을 `git revert <그 커밋>` 으로 되돌려 dev 머지(사용자 승인) 뒤 워커 셋 + fastapi 를 같은 순서로 재배포한다. 급하면 새 잡을 만들 때 `params` 에 `{"broaden": 0, "query_context": 0}` 을 실어 그 잡만 지금 방식으로 돌린다.
