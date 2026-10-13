# round06 06e 연구 어시스턴트 — 보고서 자동 산출·내보내기 기본값·참고문헌 선택하기·딥리드·인용 근거·제목 고르기·근거 칩·기록 total·PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** round06 세 줄 병렬(06c 질의 ∥ 06d 진행 화면·입구 ∥ 06e 연구 어시스턴트) 가운데 06e 줄 — spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` §12-4·D20·D21·D23·D24·D27 과 D26 의 N(기록 목록 kind 별 total). 10-08 시연 회의 결정 ①③④⑤를 이어간 연구에 넣는다. ① **보고서 자동 산출(최우선, D20)** — 참고문헌 선택하기의 [보고서 만들기] 한 번으로 목차가 자동 확정되고(연구 질문 = 첫 후보, 없으면 고른 카드의 질문), 보고서 화면이 선행연구 묶음·연구 공백 절을 문서 순서대로 하나씩 넣는다. 화면 머리에 **크게 보이는 진행 막대**(사용자 Q1 답을 보고서 화면에도 — 2026-10-11 사용자 확인)·머리 목차·문서 자리 1~6, 연구 배경·방법 칸(승인 상태에서 쓰고 버전 충돌은 한 번 다시), '검토할 곳' 줄, 연구 공백 '확인했다' 단정 다듬기(06b 이월 §7-13). [목차 고치기]·절 다시 쓰기·문단 [수락]·[다시]·[고치기]·직접 쓰기는 선택 기능으로 남는다. ② **내보내기 기본값(D21)** — Word(·PDF) 기본은 모든 문단·워터마크 없음, 공개 부록은 절별 문단 상태 개수(모델 이름·시도 기록 뺌), '수락한 문단만' 선택지. ③ **참고문헌 선택하기·오른쪽 딥리드·인용 근거(D24)** — 단계 이름 '제목 고르기'·'참고문헌 선택하기'·'보고서'(Q2 기본), 논문 제목을 누르면 오른쪽 딥리드 패널, 보고서의 인용 칩을 누르면 오른쪽 인용 근거 탭(모델이 본 원문 대목 하이라이트·[원문 보기]·[이 논문과 대화하기]), 딥리드 논문 프롬프트(§12-11). ④ **제목 고르기(D23)** — 후보 키워드 칩(LLM 후보 + 채택 논문 키워드 편수, 위 3개 미리 선택)·카드 제목에 키워드(06c `terms.contains` 로 검사)·하이라이트·[이 키워드로 다시 만들기]. ⑤ **근거 칩 표기(D27 — Q3 기본 S, 주제 카드 칩만)**, 사이드바 '모두 보기 (N)' 의 kind 별 total(fastapi — 그리기는 06d), **PDF**(마지막 Task — 10/16 조건). 워커(`celery-research-plan` 의 생성 실행기)·fastapi·nuxt 를 바꾸고 스키마는 바꾸지 않는다. 06c 운영 배포(10/13~14)가 끝난 뒤에만 `dev` 에 머지하고 10/17~18 에 배포한다(06c 기본값 커밋을 함께 싣는다).

**Architecture:** 스키마는 그대로다 — 바뀌는 모양은 모두 JSONB(`outline.auto`·`outline.background`, 절 `basis.question`, 카드 `keywords`·`checks.missing_keywords`, 개념 생성의 `input.paper_keywords`·`output.candidates`, 카드 생성의 `input.keywords`)와 응답(ProposalView `section_gens`, WorkView `concept_candidates`, HistoryListOut `total`, BookOut `doc_type`) 안이다(함정 14). 목차 자동 확정은 워커의 반영(`outline.apply`)이 하고, 절 연쇄는 **화면**이 한다 — 원문 대목 고르기(리랭커·Milvus)가 FastAPI 프로세스에만 있어(함정 17) 워커가 목차 뒤에 절 생성을 이어 넣을 수 없다. 연쇄 판정(`autoChainOn`·`autoTargets`·`nextAutoSection`)은 `utils/proposalView.ts` 의 순수 함수로 서버 값(`outline.auto`·`section_gens`)에서 매번 다시 계산하므로 탭을 닫았다 와도 남은 절부터 이어 넣는다(`composables/useAutoReport.ts` — 앞 POST 응답 뒤 다음 키, 생성 완료는 기다리지 않는다). 주제 카드는 주제 행만 이어가기 때 만들고 `topic_card` 생성은 개념(키워드) 생성을 반영할 때 같은 트랜잭션에서 **씨앗 자리마다 한 번** 넣는다(`topic_card.enqueue_seed_cards` — done 반영과 취소 API 가 같은 함수). 제목의 키워드 일치는 06c 의 `services.research.terms.contains` 를 그대로 쓰고(06c dev 머지 뒤 — Task K9), 세 번 다 놓친 카드는 `Executor.soft_check` 로 마지막 무른 통과 출력을 보관해 경고를 단 채 보인다. 딥리드는 `BookChat.vue` 의 스트림을 `composables/useDeepReadChat.ts` + 순수 SSE 파서(`utils/deepReadSse.ts`)로 빼서 `cntsId` 감시·논문별 대화 `store`·AbortController 를 더하고, 공용 패널 `DeepReadPanel.vue`(탭 [인용 근거 | 딥리드])를 ReadingStep·ProposalStep 이 각자 쥔다. 인용 근거는 새 조회 `GET /api/research/{job_id}/sections/{key}/sources` 가 그 절 생성 행의 `input.papers`(초록 ≤600·대목 ≤1200)를 읽는다 — 서지·Milvus·리랭커를 부르지 않는다. 화면 판단은 모두 `utils/*.ts` 순수 함수에 두고 vitest 로 재며 `.vue` 는 그리기만 한다. `pages/research/[id].vue` 는 `:57-75`(단계 본문)와 `workPanelOpen` 두 줄만 06e 다(LNB 접기 연결은 늦게 머지하는 줄 — 정함 30).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2(Postgres — 테스트는 stdlib sqlite3 사본 `tests/history_sqlite.py`), Celery·Redis, httpx, Jinja2 프롬프트(`StrictUndefined`), vLLM(gemma·Qwen — `services/research_work/routing.py`), BGE-M3·jina 리랭커·Milvus(FastAPI 프로세스에서만), pytest 9.1. Nuxt 4(4.4)·Vue 3.5·TypeScript, vitest 3.2(node 환경 — DOM 없음), `nuxi typecheck`(vue-tsc), docx(동적 import), SSE(`fetch` + `ReadableStream`), CSS(`assets/css/work.css` — `--skx-*` 토큰만).

---

## 설계 정본과 이 계획의 자리

- **설계 정본:** `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` — §12-4(06e 연구 어시스턴트 — 이 줄의 절), §12-1(원래 06c·06d 항목의 처분표 — PDF 는 '싸면 06e'), §12-5(파일 경계·같은 파일 순서), §12-6(일정·머지 문·06e·06d 순서·06c 기본값 커밋·자르는 순서·배포), §12-7(06e pytest·vitest 목록·운영 확인), §12-8(장면 2·3), §12-11(계획에서 정할 것), 결정 D20(보고서 자동 산출)·D21(내보내기 기본값)·D23(제목 고르기)·D24(참고문헌 선택하기·오른쪽 딥리드·인용 근거)·D27(근거 칩 표기)·D26 의 N. 형식·관례 정본은 06b 계획 `docs/superpowers/plans/2026-10-06-round06b-vertical-slice.md`(머리 규칙·Task 형식·`_stub_missing` 대역·`asyncio.run`·'`.vue` 는 단위 테스트하지 않음'·선택 필드·Task 37 배포 절차)다.
- **이 계획서:** `docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md`. 완료노트·00_status 가 이 경로를 적는다.
- **열린 질문의 상태(2026-10-11):** Q1·Q7·Q8·Q9 는 해결됐다. **Q1(큰 진행 막대)은 06d 의 몫이지만 06e 보고서 화면에도 같은 크기 규칙의 막대를 둔다** — 이 계획이 그렇게 판단했고 사용자가 2026-10-11 "보고서 화면에도 넣으라고 한 것이 맞아" 로 확인했다(정함 28 · Task A3 `reportBar`·Task A5 그리기). Q2(마지막 단계 이름)·Q3(근거 칩 표기 범위)은 답이 없어 spec 의 '답이 없을 때' 값으로 만든다 — Q2 '보고서'(버튼 [보고서 만들기] — 이름 낱말은 상수 하나 `FINAL_STEP_NAME`, 정함 1), Q3 범위 S(주제 카드 칩만 — `topicDeck.ts` 만, `citeLabel` 그대로, 정함 2). Q4 는 06c 판정 몫 — 06e 는 그 기본값 커밋이 dev 에 있으면 10/17~18 배포(Task Z5)에 함께 싣는다. Q5·Q6 은 시연·리허설. Q9(탐색 후보 이벤트)는 06c·06d 몫이라 06e 와 무관하다. **계획을 쓰다 새로 생긴 질문 하나** — 딥리드의 참고문헌 질문이 끊기는 기존 버그(`book_chat.py:118`)는 계획 검토에서 Task S2 에 넣기로 정했다(정함 31 — 사용자가 빼라면 S2 의 `_book_references`·`:118` 갈음·그 테스트를 빼고 S2 의 백엔드 수를 +6 에서 +5 로 되돌린다).
- **§12-11 '계획에서 정할 것' 중 이 줄에 걸린 것 — 권고대로 정했다(정함(권고))**: 아래 '§12-11 항목 중 이 줄에 걸린 것' 표. 권고가 없는 '문단 버튼 줄을 접을지'는 이 계획이 정했다(접지 않는다 — 정함 12). 선택 항목 '연구 맥락을 반영한 딥리드 첫 화면'은 **하지 않는다**(정함 19). '탐색 중 읽기 전용 PlanCard·옆 칸 폭'·''소장자료검색' 문구'는 06d 몫이다.

---

## 실행 전 알아 둘 것

- **작업 위치:** worktree `C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e`(브랜치 `feat/round06e-assistant-auto-report`) — Task 0 이 **그때의 `dev`** 에서 만든다. 모든 명령은 이 경로의 절대 경로로 쓴다. 저장소 루트 폴더(본 작업 폴더)와 다른 worktree(`.worktrees/round06-spec`·`round06c`·`round06d` 등)는 고치지 않는다 — 여러 세션이 같은 저장소를 쓴다. **본 작업 폴더에서 `git checkout`·`git stash` 를 하지 않는다**(2026-10-02 사고). 06c·06d 의 dev 를 받을 때도 이 worktree 안에서 `git merge dev` 로 받는다(Task K9 Step 1·Task R6 Step 1).
- **줄 번호 규칙:** 계획의 `파일:줄` 은 dev `da80f23`(= worktree `.worktrees/round06-spec` 의 코드 — 그 위의 문서 커밋은 코드를 바꾸지 않는다) 기준이다. **같은 파일을 앞 Task 가 이미 바꿨으면 그 뒤의 줄은 밀려 있다** — 본문은 그 자리를 "Task Xn 뒤 기준" 으로 적고, Edit 의 old 는 줄 번호가 아니라 글자로 잡는다(아래 '같은 파일 — 고치는 순서와 범위' 표의 순서대로 적용했을 때의 글자다). 그 파일을 처음 고치는 Task 의 줄 번호는 da80f23 그대로 맞다. Task 0 이 dev 의 `app`·`frontend` 가 da80f23 과 같은지 확인한다(06c 가 먼저 머지됐으면 06c 파일만 다르다 — 06e 파일과 겹치지 않는다).
- **백엔드 테스트:** 파일 하나는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/<파일> -q -p no:cacheprovider`(Git Bash 에서 한글이 깨지면 앞에 `PYTHONIOENCODING=utf-8`). 전체는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`. pytest-asyncio 가 없어 async 는 `asyncio.run` 으로 돌고 `@pytest.mark.asyncio` 는 쓰지 않는다. 로컬에 redis·celery·kombu·aiosqlite·FlagEmbedding·pymilvus·torch·pymarc 가 없다(2026-10-11 확인) — 기존 대역 패턴을 그대로 쓴다: 테스트 파일의 `_stub_missing`·`_load_*`·`_forget_on_teardown`(`test_research_proposal_api.py`·`test_research_topics_api.py`·`test_research_work_api.py` 등), 한 테스트 안에서만 끼우고 되돌리는 `_stub_missing_module(monkeypatch, name, cache_clear=…)`(`test_embed_index_guard.py:17-31`), 무거운 모듈을 대역 위에서 **새로 import** 해야 하면 `test_search_chunk_answer_flag.py:24-53` 의 `_stubbed_pipeline` 꼴(새로 올린 모듈은 teardown 에서 직접 빼고 원래 항목·부모 속성은 monkeypatch 가 되돌린다 — `_stub_missing_module` 은 원래 없던 키를 되돌리지 못해 대역에 묶인 모듈이 뒤 테스트로 샌다. Task S2 의 `_stubbed_book_chat` 이 이 꼴이고 같은 되돌림 테스트를 하나 둔다). 새 대역은 **모듈 머리에서 `sys.modules` 에 바로 끼우지 않고** fixture 안에서 끼운다, DB 는 `tests/history_sqlite.py` 의 sqlite 사본. torch·FlagEmbedding·pymilvus 를 끌어오는 모듈(`services.search.*`·`services.ingestion.embedder`·`indexer`·`services.chat.book_chat`)은 **함수 안에서** import 한다(함정 13).
- **프론트 테스트:** 새 worktree 에는 `frontend/node_modules`·`.nuxt` 가 없다 — **Task 0 에서 `npm ci` 를 먼저 한다**(`.nuxt` 가 없으면 vitest 가 `TSConfckParseError … .nuxt/tsconfig.app.json` 로 전부 실패한다). 파일 하나는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/<파일>`, 전체는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`. 타입은 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`(기대 `0`), 빌드는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`(기대 `└  ✨ Build complete!`). 자동 import 경고는 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"` — 기준선 `2`(06b 이월 §7-5 `queueLine` — 06d 가 먼저 머지돼 지웠으면 `0`), 06e 는 이 수를 늘리지 않는다. **프로젝트에 없는 패키지를 `npx` 로 받지 않는다**(nuxi·vitest 는 프로젝트에 있다 — `@vue/test-utils`·jsdom 을 들이지 않는다).
- **`.vue` 검증:** `.vue` 는 단위 테스트하지 않는다. 판단·문구는 `utils/*.ts` 순수 함수(·composable)로 빼서 vitest 로, `.vue`·`.css` 는 typecheck `0` 과 build 완료로 확인하고, 화면 동작(막대 차오름·연쇄·패널·초점·하이라이트)은 마무리 운영 확인(Task Z6)에서 본다. vitest 는 Nuxt 를 띄우지 않는다(`vitest.config.ts` — `environment: "node"`, 별칭 `~/` 만) — utils·composable 은 쓰는 것을 모두 명시해 import 한다. `nuxi typecheck` 는 `tests/` 도 보므로 06b 타입(`Outline`·`ProposalView`·`WorkView`·`TopicCard` 등)에 더하는 필드는 **선택(`?`)** 으로 더한다(기존 픽스처를 깨지 않게).
- **상수·이름:** Nuxt 자동 import 때문에 **한 이름은 한 파일만 내보낸다**(06b 보강 8 — 두 파일이 같은 이름을 내보내면 `WARN Duplicated imports` 가 나고 하나가 말없이 무시된다). 새 이름은 아래 '공통 계약' 1-6 의 파일에서만 export 한다. 백엔드 상수는 1-1 의 모듈에만 둔다.
- **CSS 자리:** `work.css` 의 새 묶음은 모두 06b 보강 6 의 표시 줄 `/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */`(da80f23 `:1231`) **바로 위**에 Edit 로 넣는다 — old = 그 한 줄, new = 자기 묶음 + 빈 줄 + 그 한 줄. **근거 장부 블록(`/* ── 근거 장부(EvidenceLedger)` 부터 `/* ── 진행 막대(WorkStepper)` 앞까지 — da80f23 `:75-166`, 그리고 `/* 진행 패널 아래 근거 장부` 부터 그 규칙의 `}` 까지 — `:1216-1220`)은 06d 몫이라 건드리지 않는다.** 같은 선택자를 두 Task 가 정의하지 않는다. `--skx-*` 토큰만 쓰고 새 색값(hex·rgba)을 쓰지 않는다. 새 움직임은 `@media (prefers-reduced-motion: reduce)` 에서 멈춘다. `style_skovix.css` 의 `.skx-chat-side`(`:4823-4877`)는 재사용만 하고 고치지 않는다.
- **프롬프트:** 새·바뀐 프롬프트(`research_concepts.yaml`·`research_topic_card.yaml`·새 `book_chat.paper.yaml`)에 개수 예시·원소가 든 배열 견본·"예:"·"예시"·예시 제목을 두지 않는다(함정 15). 다시 만들 때 이전 제목을 주지 않는다(함정 26). 개수(후보 상한 10·미리 선택 3)는 코드가 정한다. 각 프롬프트는 테스트가 실제 YAML 을 렌더해 변수 집합과 금지 문자열을 고정한다.
- **FastAPI 쪽 무거운 계산:** 06e 는 새 임베딩·Milvus·리랭커 호출을 더하지 않는다 — 인용 근거 조회는 생성 행의 저장값만 읽고(정함 23), 이어가기의 논문 키워드는 `BookRepository.get_by_cnts_ids`(DB)만 읽는다. 실패 처리는 실제로 나는 타입만 잡는다 — `except Exception` 금지(함정 19).
- **셸:** 명령마다 `cd <절대 경로> &&` 로 시작한다(에이전트 셸은 호출 사이에 cwd 가 초기화된다). 저장소는 `core.autocrlf=true` 라 작업 트리 파일이 CRLF 다 — 기존 파일은 **Edit 도구로** 고친다(Git Bash 의 sed·heredoc 은 LF 줄을 섞는다). 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다.
- **커밋:** `[Feat]`·`[Fix]`·`[Refactor]`·`[Test]`·`[Chore]`·`[Docs]` 접두어 + 한국어 서술형(`[Feat] round06e — …`, 화면은 `[Feat] round06e 프론트 — …`). **`Co-Authored-By` 줄과 "Generated with Claude Code" 줄은 넣지 않는다**(사용자 규칙 — 다른 안내보다 우선). Task 마다 커밋 1~3개, `git add` 는 파일을 하나씩 적는다(`-A`·`.` 금지, `.vue` 경로의 대괄호는 따옴표로 — `"frontend/pages/research/[id].vue"`).
- **운영 금지:** Task 0 과 파트 A·X·R·S·K·H 의 어떤 Step 도 운영 서버·운영 DB·운영 Redis·운영 vLLM 에 쓰거나 부르지 않는다. 운영 API 에 붙인 로컬 화면(`NUXT_DEV_API_TARGET=http://192.168.12.57:92/api` — `nuxt.config.ts:27-33` devProxy)에서 GET 만 하는 것은 된다 — 누르면 쓰는 버튼([보고서 만들기]·[이 절 쓰기]·[담음]·[이 키워드로 다시 만들기]·칸 저장·Word·PDF·딥리드 질문 보내기)은 누르지 않는다. Task K1 의 측정 스크립트는 개발 PC 에서 `--dry-run` 만 하고 서버 실행은 사용자가 한다(Task Z1). `dev` 머지는 사용자 승인 뒤(Task Z4·Z7), 서버 명령은 **사용자가** 친다(Task Z5·Z6 — 계획은 명령과 확인 방법을 준다).
- **고치지 않는 파일:** `frontend/components/research/*`(`ReportPrint.vue` 는 Task H3 이 import 만), `frontend/assets/css/research.css`, `frontend/components/work/EvidenceLedger.vue`·`frontend/utils/evidenceLedger.ts`(06d), `work.css` 의 근거 장부 블록, `frontend/utils/citations.ts`(Q3 S — `citeLabel` 그대로, `splitAuthors`·`pubYear` 는 import 만), `frontend/utils/researchEvents.ts`·`frontend/types/research.ts`(06c·06d), `frontend/components/AppSidebar.vue`·`frontend/pages/index.vue`(06d), `frontend/types/history.ts`·`frontend/utils/historyStore.ts`(기록 프론트 — 06d), `frontend/composables/useReportExport.ts`, `frontend/assets/css/style_skovix.css`, `pages/research/[id].vue` 의 `:57-75`·script `workPanelOpen` 두 줄 밖(Task R6 을 하면 `:3-7` 두 곳도), `pages/papers/index.vue`·`pages/papers/[id].vue` 의 BookChat `doc-kind="paper"` 한 속성 밖, `frontend/tests/fixtures/term_checks.json`(06c 정본 — 읽기만), `app/services/research/*`·`app/workers/research_tasks.py`·`app/workers/research_work_tasks.py`, 딥리서치 프롬프트(`research_plan.yaml`·`research_critique*.yaml`·`research_synthesize.yaml`), `docker-compose*.yml`·`infra/`·`app/alembic/`, `frontend/package.json`·`package-lock.json`.
- **함정(`docs/ops/recurring-gotchas.md`):** 3(운영은 `:latest`)·4(`scripts/`·`research/` 는 이미지에 없다 — `/app/data/…` 에 두고 `-e PYTHONPATH=/app`)·10(jsonb `?` 는 키 존재만 — K1 측정)·11(정렬 걸린 `LIMIT` 은 표본이 아니다 — K1 측정)·12(Portainer 에 pull 을 맡기지 않는다)·13(무거운 import 는 함수 안)·14(스키마 변경 없음 — JSONB 안 모양만, `alembic_version` 그대로)·15(프롬프트 예시 개수를 베낀다)·16(바뀐 컨테이너만 Recreate)·17(원문 대목·리랭커·Milvus 는 FastAPI 프로세스에만 — 절 연쇄가 화면에 있는 까닭)·18(fastapi Recreate 전 `idle in transaction` 0)·19(실패 타입·asyncio 데드라인)·20(fastapi·nuxt Recreate 뒤 `nginx -s reload`)·24(browser_active 429 가 안 풀리면)·26(LLM 이 입력을 베낀다 — 다시 만들 때 이전 제목을 주지 않는다)·27(vLLM 도구 파서 — 06e 는 도구 호출을 쓰지 않는다, 운영 확인 때 생성 실패가 몰리면 먼저 본다).
- **기준선(2026-10-08 실측 — dev `da80f23` 코드, worktree `.worktrees/round06-spec`. 06e 묶음은 2026-10-11 같은 곳에서 실측. Task 0 이 06e worktree 에서 다시 재고 같은 값이어야 한다 — 06c 가 먼저 dev 에 머지됐으면 그만큼 크다):**
  - 백엔드 전체 **`5 failed, 2327 passed, 1 skipped, 2 warnings, 1 error`**. 실패 5 = `test_build_manifest.py` 2(Windows 경로 구분자 — `'originals/KC...KCI_FI001.pdf' == 'originals/KCI_FI001.pdf'`)·`test_loaders.py` 3(`ModuleNotFoundError: No module named 'pymarc'`), 오류 1 = `test_book_chat.py` 수집(`No module named 'FlagEmbedding'`) — 06b 계획 머리의 '5 failed · 1 error' 와 같은 여섯 줄이다. 경고 2 는 `core/config.py:16`·`schemas/book.py:47` 의 `PydanticDeprecatedSince20`. 06b 계획 끝(2273)보다 54 많은 것은 06b 리뷰 반영·운영 수정 테스트다. 06e 가 고치거나 기대는 백엔드 테스트 스물한 파일 묶음은 **`744 passed, 2 warnings`**(Task 0 Step 4 의 표 — 2026-10-11 실측).
  - 프론트 `nuxi typecheck` 오류 **`0`**, vitest **`Test Files  40 passed (40)` / `Tests  732 passed (732)`**, `npm run build` **`└  ✨ Build complete!`**. 06e 가 고치거나 기대는 프론트 테스트 열세 파일 묶음은 **`Test Files  13 passed (13)` / `Tests  221 passed (221)`**(Task 0 Step 5 의 표). typecheck·build 에 두 번씩 나오는 `WARN Duplicated imports "queueLine"`(`utils/researchEvents.ts:107` 의 다시 내보내기 — 06d 가 지운다)과 typecheck 의 `[Vue] Resolve plugin path failed: vue-router/volar/sfc-route-blocks … Cannot find module '@vue/language-core'` 는 기준선에도 나오는 경고다. `npm ci` 끝의 `37 vulnerabilities (3 low, 5 moderate, 21 high, 8 critical)` 는 안내이지 실패가 아니다. build 로그의 `error` 낱말은 `error-404`·`error-500` 청크 이름뿐이다.
- **기준선 읽는 법:** 각 Task 의 기대 수는 **"Task 앞 수 + N"** 상대값이다(N = 그 Task 가 더한 테스트 수, 매개변수는 펼친 수 — 앞 Task 를 아래 '전역 실행 순서' 대로 마쳤을 때). vitest 는 끝의 `Test Files … passed (…)`·`Tests … passed (…)` 두 줄로 읽는다. 백엔드 전체는 "실패 5·오류 1 은 기준선과 같은 세 파일" 로 읽고, pytest 끝의 `, 1 warning`·`, 2 warnings`(`PydanticDeprecatedSince20`)는 기대값에 없어도 같은 결과다. Task K9 Step 1(06c dev 받기)·Task R6 Step 1(06d dev 받기)이 dev 를 받으면 그 줄의 테스트가 함께 들어온다 — 그 Task 에 적은 대로 merge 뒤 수를 새 '앞 수' 로 삼는다.

---

## 06e 에서 정한 것 (spec 이 '제안'·'권고'로 둔 것과 열린 질문의 기본값, 이 계획의 보강 — 결정과 근거)

spec 과 다르게 읽거나 좁힌 것(정함 9·10·22·23·29 — 실제 코드에 맞춤)과 spec 이 가정했지만 코드에 없던 것(정함 18 — `BookOut.doc_type`), §12-10·§12-11 을 닫은 것(정함 1·2·7·11·12·14~19·28)은 **Task Z3 가 spec 을 이 결정에 맞춘다**(CLAUDE.md §3 — 코드가 실제다). 완료노트 §6 에 그대로 옮긴다.

| # | 정함 | 근거 |
|---|---|---|
| 정함 1 | **Q2 기본 = 마지막 단계 이름 '보고서'.** 이름 낱말은 상수 하나 `FINAL_STEP_NAME = "보고서"`(`utils/workPhase.ts`, Task A3)에서 만들고, **상수는 조사가 붙지 않는 꼴에만 쓴다** — 버튼 `[보고서 만들기]`·`[보고서 다시 만들기]`, 진행 막대 `보고서 작성 중 · n/m절`, 단계 제목·`STEP_NAMES`, 이동 버튼 `보고서 단계로`, Word 파일 이름 접두(`보고서_<주제>_<날짜>.docx`)·문서 머리 `보고서 초안 · 원 질문 …`. `${FINAL_STEP_NAME}를`·`${FINAL_STEP_NAME}로` 처럼 조사를 붙여 만드는 문구는 두지 않는다('연구 초안를' 이 된다). 조사가 붙는 문장(확인 창 `보고서를 다시 만들면 …`·ProposalSection 안내·ProposalStep 안내·온보딩 본문)은 글자 그대로 '보고서'를 쓴다. 사용자 답이 '연구 초안'이면 ① 상수 한 줄 ② `grep -rn "보고서[를로가는의은이]" frontend/components/work frontend/utils/workPhase.ts frontend/utils/readingList.ts` 가 내는 문장 가운데 마지막 단계를 가리키는 것(앞에 '딥리서치 '가 붙은 글 — Task R1 이 붙인 `TopicsStep.vue:8`·`OutlineEditor.vue:92`·`CandidateDrawer.vue:7`·`topicDeck.ts` `SEED_KIND_LABEL`·`[id].vue:60` 과 온보딩 ② 본문 — 은 그대로) ③ 그 문자열을 기대하는 테스트를 고친다. '목차'·'딥리서치' 용어는 그대로 | spec §12-10 Q2 '답이 없을 때 = 보고서' |
| 정함 2 | **Q3 기본 = 범위 S(주제 카드 칩만).** `utils/topicDeck.ts` 의 `evidenceChips` 만 바꾸고 `citeLabel`(`utils/citations.ts:51-56`)·보고서 `CitationChip`·`OutlineEditor`·`ProposalSection`·`paperDetail` 은 그대로 | spec §12-10 Q3 |
| 정함 3 | **자동 승인은 질문이 있을 때만.** `outline.apply` 는 `question = questions[0]` → 없으면 `topic.question` → 둘 다 비면 `None`(공백을 정리하고 2자 미만은 없는 것으로 본다 — `PUT …/outline` 의 승인 하한 `APPROVE_NEEDS_QUESTION` 2자와 같아야 자동 승인한 목차를 [목차 고치기]로 다시 승인할 때 422 가 나지 않는다, Task A1). 질문이 있으면 `state "approved"`·`approved_at`·`auto: true`, 없으면 06b 처럼 `draft`·`auto: false`(사용자가 질문을 쓰고 승인) — 빈 질문으로 승인하면 이후 PUT 이 `APPROVE_NEEDS_QUESTION` 422 를 낸다 | `research_proposal.py:258-259` |
| 정함 4 | **[보고서 다시 만들기] 는 이미 쓴 절을 다시 쓰지 않는다.** 새 apply 가 `auto` 를 다시 붙이지만 연쇄의 대상은 '절도 생성 기록도 없는 키'(spec §12-4)라, 이미 쓴 절은 그대로 남고(주제·묶음·연구 질문이 바뀐 절에는 '다시 맞춤 필요' + [이 절 다시 쓰기]) 아직 쓰지 않은 절(새로 생긴 묶음 절과 06b 때 쓰지 않은 기존 키)만 자동으로 쓴다. 확인 창 문구에 이것을 적는다(Task A5 — 두 화면 같은 글, '연구 배경은 그대로 둡니다'와 '연구 질문'은 Task X3) | spec §12-4 '대상'·'목차를 고쳐 다시 승인하면' — 사용자 글을 덮지 않는다 |
| 정함 5 | **근거 없음 409 는 code 를 단다.** `POST …/sections/{key}/generate` 의 `NO_SECTION_PAPERS`(`research_proposal.py:395-396`)를 `detail={"code": "no_section_papers", "message": "이 절에 넣을 논문이 없습니다"}` 로 바꾼다 — 화면 문구는 `detailMessage` 가 message 를 그대로 읽고, 연쇄는 문자열이 아니라 code 로 가른다 | 06b `version_conflict` 와 같은 모양(`research_proposal.py:94-96`) |
| 정함 6 | **연쇄는 보고서 화면(ProposalStep)이 열려 있을 때 돈다.** 조건은 매번 서버 값(`outline.auto`·`section_gens`)으로 다시 계산하므로 탭을 닫았다 와서 `?s=proposal` 을 열면 남은 절부터 이어 넣는다. 다른 단계 화면에 있는 동안은 넣지 않는다 | spec §12-4 '탭을 닫았다 와도' |
| 정함 7 | **연구 배경 = `outline.background` 자유 글**(§12-11 권고). `OutlinePut.background: str \| None = None` — `None` 이면 저장된 값을 지킨다(옛 화면·[목차 고치기]의 PUT 이 배경을 지우지 않게). 상한 `OUTLINE_BACKGROUND_MAX = 2000`. **Word·PDF 의 '2. 연구 배경' 에도 싣는다**(Task X5 — `proposalDocument.ts:120-121`): 적었으면 그 글, 없으면 흐린 `연구 배경을 아직 적지 않았습니다.` — '다음 단계에서 씁니다'(`NOT_YET` :40)는 D20 으로 다음 단계가 없어 지운다. 새 반영(apply — [보고서 다시 만들기])은 연구 배경을 지우지 않고 옛 목차에서 이어 받는다 — 방법은 D20 대로 빈칸(Task X1) | §12-11 '연구 배경 저장'(바꿀 곳에 `proposalDocument.ts:120-121`) |
| 정함 8 | **방법·배경 칸은 문서 2절·6절 자리에서 바로 쓴다.** 저장은 `PUT /outline` 에 저장된 묶음·질문을 그대로 싣고 `approve = (state == "approved")` — 승인 목차는 승인 그대로, 06b 의 초안 목차는 초안 그대로. 409 `version_conflict` 면 응답의 `version` 으로 **한 번만** 다시 보내고 두 번째 409 는 오류 줄 | spec §12-4 '연구 배경·방법' |
| 정함 9 | **연구 질문 바뀜 = 절 basis 의 `question`.** 절 입력의 `basis` 에 그때의 `research_question`(= `outline.question or outline.topic.question or ""`, `research_proposal.py:402` 와 같은 식)을 싣고, `stale_flags` 는 basis 에 `question` 키가 **있는 절만** 지금 값과 견준다 — 06b 에 쓴 절은 키가 없어 이 이유로는 stale 이 되지 않는다 | spec §12-4 '연구 질문을 바꿔도' |
| 정함 10 | **연구 공백 단정은 '소장 코퍼스 범위' 문장에서만 바꾼다.** 새 상수 `GAP_CLAIM_REWRITES`(쌍 목록)를 `soften_claims` 가 문장마다(`(?<=[.!?。])\s+` 로 나눔) 적용하되, 그 문장이 `GAP_CLAIM_CONTEXT`(`코퍼스` 또는 `소장 논문·소장 자료·소장 문헌·소장 학술논문` — 코퍼스 범위를 말하는 낱말)를 품을 때만이다. '분석한 결과·검토한 결과' 같은 말은 문맥으로 쓰지 않는다 — 선행연구 요약에 아주 흔해('김(2015)[E1]은 노인 300명을 분석한 결과 … 낮추는 것으로 확인되었다'), `soften_claims` 가 모든 절·문단 다시 쓰기(`check_paragraph` 를 거쳐)·사용자 고친 글·주제 카드(직접)에 같이 도는 지금 구조에서 인용한 발견까지 바꾼다. 절 키로 가르지 않는다(`soften_claims` 의 시그니처와 호출처 — `check_paragraph` 둘·직접 둘 — 그대로) — 06b 이월 §7-13 의 실제 문장 '소장 코퍼스를 분석한 결과 … 충분하지 않음을 확인했다'는 코퍼스 낱말로 잡힌다. 기존 `CLAIM_REWRITES` 는 그대로 | 06b 이월 §7-13(완료노트 :355), 오탐 방지 — 호출처 `section.py:48`·`paragraph_edit.py:60`·`topic_card.py:170-171`·`research_topics.py:70` |
| 정함 11 | **검토 단서(§12-11 권고):** 보고서 머리에 `검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m`(둘 다 0 이면 숨김, 누르면 첫 자리로 스크롤·초점) — 넣는다. '근거 없음' **보이는 배지**는 넣지 않고 지금의 밑줄 표시(`wk-psec__unmarked`)에 화면낭독용 `(근거 표시 없음)` 만 더한다(문장마다 배지를 달면 자동 보고서가 배지로 덮인다). 공개 부록에는 같은 수를 한 줄 싣는다 | §12-11 '검토할 곳 요약·근거 없음 배지·부록 수' |
| 정함 12 | **문단 버튼 줄은 접지 않는다**(§12-11 '접을지') — 지금처럼 늘 보인다. hover·포커스로만 보이면 터치·키보드에서 [수락]·[고치기]를 못 찾고, 대회 전에 화면 규칙을 하나 더 늘리지 않는다 | §12-11 — 권고 없음, 이 계획이 정함 |
| 정함 13 | **내보내기(D21):** `ProposalDocInput.includeProposed` 를 `acceptedOnly: boolean`(기본 false)으로 바꾼다. 기본은 네 상태 전부·워터마크 없음, 켜면 `accepted·edited·authored` 만·워터마크 없음. 파일 이름 꼬리는 켰을 때만 `_수락문단만`. `UNREVIEWED_WATERMARK` 는 지운다(`ReportDoc.watermark` 필드와 `reportDocx`·`ReportPrint` 의 그리기는 그대로 — 보고서 출력 불변). `footprintLine` 머리도 'AI 작성 n문단 중 …'으로 맞춘다 | D21·spec §12-4 내보내기 |
| 정함 14 | **키워드 후보 원천(§12-11 권고):** LLM 후보(개념 생성을 넓힘) + 채택 논문 키워드(`library_catalog.keyword` 나눈 것 ∪ `extra.keywords`)의 문서 빈도를 코드로 합친다. 채움률은 Task K1 의 1회성 측정으로 보고 상수 `PAPER_KEYWORD_MIN_N` 을 정한다 — 채택 논문 중 키워드가 하나라도 있는 비율이 50% 이상이면 1(논문에만 있는 후보도 1편부터), 미만이면 2(보조 — 2편 이상 겹친 것만). 기본값 1 로 구현하고 측정 뒤 한 줄 커밋 | §12-11 '키워드 후보 원천' |
| 정함 15 | **키워드 최소 선택 수 2**(§12-11 권고) — [이 키워드로 다시 만들기]는 고른 키워드가 2개 이상일 때만(화면이 먼저 막고 서버도 409 `KEYWORDS_TOO_FEW`). 처음 미리 선택(PRESELECT 3, 후보가 3개 미만이면 모두)은 이 하한을 보지 않는다. 선택 상한은 지금의 `CONCEPTS_MAX = 5`(서버 PATCH `MAX_CONCEPTS` 5) 그대로. **직접 더하기는 남긴다** — 후보에 없는 말을 칩으로 더해 고른 상태로 둔다(출처 배지 '직접') | §12-11 '키워드 최소 선택 수·직접 더하기' |
| 정함 16 | **고른(`picked`) 카드는 키워드를 바꿔도 다시 만들지 않는다**(§12-11 권고), 사용자가 고친 카드(`card.edited`)·직접 쓴 카드(origin user)·접은 카드도 대상이 아니다 | §12-11 |
| 정함 17 | **세 번 다 놓친 카드(§12-11 권고):** `Executor` 에 선택 필드 `soft_check` 를 더해 `run_generation` 이 '무른 검사만 통과한 마지막 출력'을 보관하고, 끝내 엄격한 검사를 못 넘으면 빈 결과 대신 그 출력을 그 모델 이름으로 돌려준다. 주제 카드의 무른 검사 = 지금의 검사(근거 2편 이상), 엄격한 검사 = 그에 더해 키워드 하나 이상 일치. 화면은 `card.checks.missing_keywords` 가 `card.keywords` 전부일 때 '제목에 「…」 없음' 경고를 단다 | §12-11 '키워드를 세 번 다 놓친 카드' |
| 정함 18 | **딥리드 논문 프롬프트 채택(§12-11 권고):** 새 `book_chat.paper.yaml` + `book_chat.chat_prompt(book)`. `BookOut` 에는 `doc_type` 이 없다(`schemas/book.py:46-70`) — `BookOut.doc_type: Optional[str] = None` 한 줄을 더한다(예외 파일, 응답에 필드 하나 더해질 뿐) | §12-11 · spec 이 가정한 `book.doc_type` 이 지금 응답 모델에 없음 |
| 정함 19 | **'연구 맥락을 반영한 딥리드 첫 화면'은 하지 않는다**(§12-11 '선택' — 공통 맥락 지시) | — |
| 정함 20 | **딥리드 대화 보관:** 단계 화면(ReadingStep·ProposalStep)이 각자 `Map<cnts_id, DeepReadMessage[]>` 하나를 쥐어 BookChat 의 `store` 로 넘긴다 — 같은 단계 안에서 논문을 오가면 이어지고, 단계를 옮기거나 새로고침하면 비운다. 서버 저장 없음 | spec §12-4·§12-9 |
| 정함 21 | **스트림을 끊을 때의 대화:** 닫기·논문 바꾸기로 끊은 답은 버리지 않고 받은 글 + `\n\n(답을 받다가 멈췄습니다)`(받은 글이 없으면 `(답을 받기 전에 멈췄습니다)`)를 assistant 메시지로 그 논문의 대화에 남긴다 — 다음 질문의 history 가 user/assistant 짝을 잃지 않게 | BookChat 의 history 는 직전까지의 메시지 전부(`BookChat.vue:124-126`) |
| 정함 22 | **출처 칩은 미리보기 토글을 지킨다.** `<span @click>` → `<button type="button" :aria-pressed>`(누르면 지금처럼 대목 미리보기). 원문 열기는 미리보기 안 [원문 보기] 버튼이고 `pdfLinks` prop(기본 false)이 켜진 곳(연구 화면 패널)에서만 그린다 — 기존 네 화면은 동작이 그대로다. **칩 글자는 지금 그대로 저장값**(`sourceLabel` = `p.${page_start}` + 다르면 `–${page_end}` — `BookChat.vue:26`)이다: 서버가 같은 날값으로 LLM 문맥 `[p.X–Y]` 를 만들어(`book_chat.py:155`) 답 글에도 그 숫자가 나오므로, `citations.pageLabel`(0부터 센 값 + 1)로 바꾸면 칩이 답 글과 한 쪽씩 어긋나고 기존 네 화면도 바뀐다. 원문 열기 입력만 `sourcePdfTarget` = `citedPdfTarget(cntsId, title, [src])`(0부터 센 쪽 → 뷰어 쪽 +1, `pdfViewer.ts:66-73`) | 기존 화면 회귀 0, `book_chat.py:155`·`:206-209`, `citations.ts:94-103` |
| 정함 23 | **인용 근거 조회 모양:** spec 그대로 맨 위가 `{E#: {cnts_id, abstract, excerpt}}` 지도다. 어느 생성인지는 쿼리 `?gen=<id>`(화면이 문단의 절 `gen_id` 또는 쓰는 중이면 `drafts[key].gen_id`)로 고르고, 없으면 저장된 절의 `gen_id` → 그 키의 열린 section 생성 순. 초록·대목은 그 생성 행의 `input.papers[i]`(`abstract` ≤600·`excerpt` ≤1200)에서 읽는다 — 서지·Milvus·리랭커를 부르지 않는다 | spec §12-4 인용 근거 A안 |
| 정함 24 | **인용 칩은 저장된 문단에서만 패널을 연다.** 흐르는 글(`ProposalSection.vue:32-37`)의 칩은 지금처럼 `<span>` 이다 — 절이 끝나면 문단이 다시 나뉘어 문장 번호가 바뀐다 | — |
| 정함 25 | **카드 생성 시점의 이벤트:** 개념 반영(워커)이 넣은 카드 생성은 queued 이벤트를 따로 보내지 않는다 — 화면은 concepts done 에 `topics`·`work` 를 다시 읽어(RELOAD) 새 queued 생성을 본다. 취소 API 가 넣은 카드는 커밋 뒤 queued 이벤트를 보낸다 | 06b 정함 10(생성 done → 조회 다시 읽기) |
| 정함 26 | **기록 total 은 따로 센다.** `HistoryRepository.list` 의 반환 모양(2-튜플)은 그대로 두고 `count(session_id, kind) -> int` 를 더해 API 가 둘 다 부른다 — 기존 저장소 테스트를 깨지 않는다. `total` 은 `before` 와 무관한 '지우지 않은 그 kind 전부'의 수 | spec D26·§12-3 |
| 정함 27 | **PDF 는 보고서 화면이 스스로 인쇄한다.** ProposalStep 이 자기 `useReportExport()` 의 `printPdf` 와 `<ReportPrint v-if="printDoc">` 를 쥔다(`[id].vue:196` 의 ReportPrint 는 06d 영역이라 건드리지 않는다). 문서는 Word 와 같은 `buildProposalDocument`(같은 기본값) | spec §12-4 PDF·§12-5 |
| 정함 28 | **자동 보고서에도 큰 진행 막대를 둔다(사용자 Q1 답을 06e 보고서 화면에도 적용 — 이 계획의 판단을 사용자가 2026-10-11 확인: "보고서 화면에도 넣으라고 한 것이 맞아").** 사용자 답 "현재 절 작성중에 보여지는 커다란 프로그레스바 필요, 예시 막대는 너무 작음"을 spec 은 06d 딥리서치 진행 화면에만 적었고 §12-3 은 그 막대를 단계 화면(stepMode)에 그리지 않는다. 그런데 06e 자동 보고서도 '절을 차례로 쓰는 중'인 화면이다(§12-8 장면 3) — 이 계획이 06e 에도 넣자고 판단했고 사용자가 그 판단이 맞다고 확인했다. 그래서 보고서 화면 머리 목차 위에 같은 크기 규칙의 막대를 둔다 — 막대 두께 `--wk-bar-thick: 1rem`(768px 이하 0.75rem), 막대 바로 위 큰 글줄(1rem 굵게) `보고서 작성 중 · 3/6절 — 「지금 쓰는 절 이름」`, 오른쪽 끝 퍼센트(1.25rem 굵게), 쓰는 중이면 채움에 `is-running` 움직임(reduced-motion 이면 멈춤). 06d 의 `research.css` 토큰·부품은 import 하지 않고 값만 맞춘다(`work.css` 토큰 — 시각 디자인 담당이 고칠 자리). 단계 칩은 두지 않는다 — 같은 화면 위 WorkStepper 가 단계 표시다. 계산은 순수 함수 `reportBar`(Task A3), 그리기는 Task A5. spec 은 Task Z3 이 맞춘다 — §12-3 오프셋 행의 '단계 화면(`stepMode`)에서는 그리지 않는다'는 06d 막대 이야기이고 06e 보고서 화면은 자기 막대(`.wk-rbar`)를 따로 그린다는 것을 덧붙인다 | 사용자 확인 2026-10-11(하네스 전달), spec §12-3 :542·:543, §12-8 :755 |
| 정함 29 | **씨앗 카드 '한 번만' 은 씨앗 자리 행마다 판정한다.** `enqueue_seed_cards` 는 `slot is not None and origin == "report_seed"` 인 주제 행마다 그 행 id 를 target 으로 하는 `topic_card` 생성이 (상태 무관) 하나도 없을 때만 그 행에 넣는다 — '그 연구에 topic_card 생성이 하나라도 있으면 []' 로 하면, 개념 생성이 줄을 서는 사이(디스패처 전역 1건 — 여럿이 함께 쓰면 몇 분) [다른 방향]을 누른 연구는 그 origin other 카드 때문에 씨앗 카드 4장이 영영 생기지 않는다. spec §12-4 '그 연구에 topic_card 생성이 한 번도 없을 때만'은 '그 씨앗 자리에 카드 생성이 한 번도 없을 때만'으로 읽는다(완료노트·spec 메모에 범위를 적는다). 그와 함께 **[다른 방향]은 개념(키워드) 생성이 열려 있으면 409 `KEYWORDS_BUSY`**(Task K4 — [이 키워드로 다시 만들기]와 같은 규칙) — 비어 있는 `work.concepts` 를 키워드로 넘긴 카드를 만들지 않는다 | `research_topics.py:120-156`(개념 생성 검사 없음), `research_work.py:123-129` `_concepts_open` |
| 정함 30 | **딥리드 패널 LNB 접기 계약(06d 계획과 같은 문장):** "06e 는 ReadingStep·ProposalStep 의 emit `panel: [open: boolean]` 과 `[id].vue:73-74` 의 리스너 `@panel="workPanelOpen = $event"`, script 의 `const workPanelOpen = ref(false);`(`:514` 뒤)까지 단다. `AppSidebar :collapsed="workPanelOpen"` 와 루트 `is-lnb-collapsed`(`[id].vue:3-7` 두 곳)는 늦게 머지하는 줄이 단다 — 06d 가 늦으면 06d 계획의 LNB 접기 연결 Task 가, 06e 가 늦으면 이 계획의 Task R6 이 이 두 곳만 고친다. 06d 의 그 Task 는 리스너·새 ref·`watch(step)` 를 넣지 않고 `workPanelOpen` 을 읽기만 한다." 단계를 옮기면 ReadingStep·ProposalStep 이 내려가며 `onBeforeUnmount` 에서 `panel` false 를 내므로 `watch(step)` 가 필요 없다 | 계획 비평 — 06d 쪽 처음 안(`deepPanelOpen`·`@<06e emit>`·`watch(step)`)과 겹치면 같은 요소에 `@panel` 이 두 번(Vue 컴파일 오류 Duplicate attribute), spec §12-5 :689 |
| 정함 31 | **딥리드의 참고문헌 질문이 끊기는 기존 버그를 06e 에서 고친다 — Task S2(계획 검토에서 정함. 사용자가 빼라면 S2 의 함수·`:118` 갈음·테스트를 빼고 S2 의 백엔드 +6 을 +5 로 되돌린다).** `services/chat/book_chat.py:117-118` 은 참고문헌 의도(`_REF_INTENT_KEYWORDS` `:19-22` — '참고문헌'·'인용'·'출처'·'reference' 등)일 때 `(book.extra or {}).get("references", [])` 를 읽는데, 엔드포인트가 넘기는 `book` 은 `BookRepository.get_by_cnts_id` 가 돌려준 `BookOut`(`app/api/book.py:647-651`)이라 `extra` 가 없다 — `AttributeError` 로 스트림이 끊기고 화면은 `CHAT_ERROR_TEXT` 를 보인다. `book.extra` 를 읽는 코드는 0b51e68 부터이고 지금은 기존 네 화면(논문 상세·논문 검색 채팅 패널·도서 상세·TopResult)도 같은 길로 끊긴다 — spec §12-4·D24 범위 밖이다. 06e 의 오른쪽 딥리드도 같은 길을 쓰므로 '출처'·'인용'이 든 질문이 끊긴다 — 인용 근거 탭에서 [이 논문과 대화하기]로 넘어가 '출처가 어디야?'처럼 묻는 장면(spec §12-8 장면 3)이 바로 이 길이다. Task S2 가 작은 함수 `_book_references(book)` 로 `BookOut.references`(`schemas/book.py:66-67` — `extra["references"]` 를 노출한다)를 `getattr` 로 읽게 하고(속성이 없거나 None 이면 빈 목록) `:118` 을 그것으로 바꾼다. 테스트 1(`test_book_references_reads_the_book_out_field` — `test_book_chat_prompt.py` 의 대역 fixture 위). 기존 네 화면도 같은 엔드포인트라 함께 고쳐진다. Task Z6 Step 4 에서 참고문헌 의도 질문 하나를 보내 본다 | Task S2 작성 중 발견(`book_chat.py:117-118`·`schemas/book.py:47-73`·`app/api/book.py:645-651`) |

---

## 공통 계약 (이름·모양 — 모든 Task 가 이 이름을 쓴다)

파트 A·X·R·S·K·H 는 여기 적힌 이름·모양·시그니처를 그대로 쓴다. 각 이름을 **처음 만드는 Task** 를 표마다 적었다 — 뒤 Task 는 그 이름을 import 만 한다. 줄 번호는 da80f23 기준이다.

### 1-1. 백엔드 상수

| 모듈 | 이름 = 값 | Task |
|---|---|---|
| `app/services/research_work/shapes.py` | `OUTLINE_BACKGROUND_MAX = 2000` (`OUTLINE_METHOD_MAX` 아래 줄) | X1 |
| `app/services/research_work/outline.py` | 함수 `_now() -> str`(UTC `isoformat()` — 테스트가 monkeypatch), `auto_question(output: dict, input: dict) -> str \| None` | A1 |
| `app/api/research_proposal.py` | `NO_SECTION_PAPERS_CODE = "no_section_papers"`(A2) · `NO_SECTION_SOURCE_GEN = "이 절의 생성 기록이 아닙니다"`(S1) · `NEED_READING` 문구를 `f"담은 논문이 {MIN_READING_FOR_OUTLINE}편 이상이어야 보고서를 만듭니다"`(A1) · `VERSION_CONFLICT` 문구를 `"다른 곳에서 보고서가 바뀌었습니다 — 다시 불러온 뒤 고쳐 주세요"`·`IF_MATCH_FORMAT` 문구를 `"If-Match 는 보고서 버전 숫자입니다"`(R1) | A1·A2·S1·R1 |
| `app/api/research_work.py` | `CONCEPTS_BUSY` 문구를 `"키워드를 만드는 중입니다 — 끝난 뒤 고쳐 주세요"`·`patch_work` 의 422 detail 을 `"키워드를 1개 이상 넣어 주세요"`(키워드 칩 화면에 '핵심 개념' 오류가 뜨지 않게) | R1 |
| `app/services/research_work/markers.py` | `GAP_CLAIM_CONTEXT = re.compile(r"(?:코퍼스\|소장\s*(?:학술논문\|논문\|자료\|문헌))")`(표 안이라 세로줄 앞에 역슬래시를 붙였다 — 코드에는 붙이지 않는다)(정함 10 — '분석한 결과' 같은 말은 문맥이 아니다), `GAP_CLAIM_TAIL = "(소장 코퍼스에서 확인하지 않은 공백 후보)"`, `GAP_CLAIM_REWRITES: tuple[tuple[str, str], ...]`(아래 X2 의 다섯 쌍) | X2 |
| `app/services/research_work/keywords.py`(새, 순수) | `MAX_KEYWORD_CANDIDATES = 10` · `PRESELECT = 3` · `MIN_PICKED_KEYWORDS = 2` · `PAPER_KEYWORDS_INPUT_MAX = 30` · `PAPER_KEYWORD_MIN_N = 1`(K1 측정으로 1 또는 2) · `KEYWORD_LEN_MAX = 40`(= `concepts.MAX_CONCEPT_LEN`) · `GENERIC_KEYWORDS: frozenset[str]`(처음 값 — `keyword_key` 로 비교: "연구 성과", "국내 학술논문 코퍼스", "국내 학술논문", "학술논문", "연구 분야", "발전 방향", "측정 및 평가", "연구 동향", "선행연구", "연구 방법", "개념 및 정의", "한계 및 과제", "적용 분야", "향후 과제") | K2 |
| `app/api/research_topics.py` | `KEYWORDS_BUSY = "키워드를 고르는 중입니다 — 끝난 뒤 다시 만들어 주세요"`(K4 — [다른 방향]이 먼저 쓴다) · `KEYWORDS_TOO_FEW = f"키워드를 {MIN_PICKED_KEYWORDS}개 이상 고르세요"`(= '키워드를 2개 이상 고르세요' — 최소 수를 따라간다) · `NOTHING_TO_REGENERATE = "다시 만들 AI 카드가 없습니다"` · `REGENERATE_LOCK_TARGET = "regenerate"`(K6) | K4·K6 |
| `app/services/research_work/concepts.py` | `MIN_CONCEPTS` 를 지운다(`MAX_CONCEPTS, MAX_CONCEPT_LEN = 5, 40` — 검사가 '모델 후보 하나 이상'이 되어 쓰는 곳이 없다. `MAX_CONCEPT_LEN` 은 `keywords.KEYWORD_LEN_MAX` 와 같은 값임을 테스트로 고정한다 — `keywords` 가 `concepts` 를 import 하면 순환) | K2 |
| `app/services/research_work/generate.py` | `Executor.soft_check: Callable[[dict], bool] \| None = None`(선택 필드, `is_empty` 다음) | K9 |

### 1-2. JSONB·응답 모양 (스키마 변경 없음 — 모두 JSONB·응답 안)

```text
Outline(research_proposals.outline) 에 더함:
  "auto": bool            — 06e apply 가 승인까지 한 목차만 true(06b 목차엔 키 없음, 질문이 없어 draft 로 둔 목차는 false) (A1)
  "background": str       — 연구 배경 자유 글. 키가 없으면 "" 로 읽는다. PUT 이 쓰고, apply([보고서 다시 만들기])는
                            옛 목차에 있으면 그대로 이어 싣는다(없으면 키를 두지 않는다)        (X1)
Section.basis 에 더함:
  "question": str         — 이 절을 쓸 때의 연구 질문(06e 부터 — 06b 절엔 키 없음)              (X1)
Card(research_topics.card) 에 더함:
  "keywords": [str]       — 이 카드를 만들 때 넘긴 고른 키워드(입력 그대로)                    (K4 입력·K9 저장)
  "checks.missing_keywords": [str] — keywords 중 제목에 contains 가 아닌 것                    (K9)
concepts 생성 input 에 더함:
  "paper_keywords": [{"text": str, "n": int}]  — 채택 논문 키워드 문서 빈도(FastAPI 가 이어가기 때)  (K2)
concepts 생성 output(06e):
  {"concepts": [str],                       — 미리 선택(PRESELECT) = research_works.concepts 에 반영
   "candidates": [{"text": str, "source": "llm"|"paper"|"both", "n": int}]}   — n = 논문 편수(LLM 만이면 0)
  옛 행: {"concepts": [str]} — candidates 없음
topic_card 생성 input 에 더함:
  "keywords": [str]       — 옛 행은 input.get("keywords") or []                                 (K4)
```

```text
ProposalView(GET …/proposal · PUT 응답) 에 더함:
  "section_gens": {절 키: {"gen_id": int, "status": "queued"|"running"|"done"|"failed"|"canceled"}}   (A2)
      — kind section·target 있는 생성 행 중 키별 id 가 가장 큰 것(상태 무관)
WorkView(GET …/work · continue · PATCH · SSE snapshot) 에 더함:
  "concept_candidates": [{"text", "source", "n"}] | null   — 최신 done concepts 생성의 output.candidates (K3)
HistoryListOut(GET /api/history) 에 더함:
  "total": int | null      — 이 브라우저·이 kind(없으면 전부)의 지우지 않은 기록 수, before 무관   (H2)
BookOut(GET /api/books/{cnts_id} 등) 에 더함:
  "doc_type": str | null                                                                       (S2)
```

### 1-3. API

| 메서드·경로 | 요청 | 응답 | 오류 | Task |
|---|---|---|---|---|
| `PUT /api/research/{job_id}/outline` | 기존 + `background?: str \| null`(≤2000, null·생략 = 그대로) | ProposalView + ETag | 기존 + 422(길이) | X1 |
| `POST /api/research/{job_id}/sections/{key}/generate` | 그대로 | 그대로 | 409 근거 없음 detail → `{"code": "no_section_papers", "message": NO_SECTION_PAPERS}` | A2 |
| `GET /api/research/{job_id}/sections/{key}/sources?gen=<int>` (새) | `gen` 선택 | `{"E1": {"cnts_id": str, "abstract": str, "excerpt": {"chunk_id": str, "page_start": int\|null, "page_end": int\|null, "text": str} \| null}, …}` | 422 `SECTION_NOT_WRITABLE`(키), 404 `NO_SECTION`(절도 열린 생성도 없음), 404 `NO_SECTION_SOURCE_GEN`(gen 이 이 연구·이 키의 section 생성이 아님), 404 연구 없음 | S1 |
| `POST /api/research/{job_id}/topics/regenerate` (새) | 본문 없음 | `{"topic_ids": [int], "gen_ids": [int], "skipped": int}` | 409 `EXAMPLE_READ_ONLY`·`KEYWORDS_TOO_FEW`·`KEYWORDS_BUSY`·`NOTHING_TO_REGENERATE` | K6 |
| `POST /api/research/{job_id}/topics/generate`([다른 방향]) | 그대로 | 그대로 | 기존 + 409 `KEYWORDS_BUSY`(개념 생성이 열려 있을 때 — 정함 29). 카드 input 에 지금 `work.concepts` 를 keywords 로 | K4 |
| `POST /api/research/{job_id}/work/continue` | 그대로 | WorkView(+`concept_candidates`) | 그대로 — topic_card 생성을 넣지 않는다(주제 행 slot 1~4 는 넣음), concepts input 에 `paper_keywords` | K2·K3·K5 |
| `POST /api/research/{job_id}/generations/{gid}/cancel` | 그대로 | 그대로 | 그대로 — kind concepts 를 취소하면 같은 트랜잭션에서 씨앗 카드(키워드 없이)를 넣고 커밋 뒤 queued 이벤트 | K5 |
| `GET /api/history?kind=&limit=&before=` | 그대로 | `{items, next_cursor, total}` | 그대로 | H2 |

### 1-4. 이벤트

- 새 이벤트 종류 없음. `generation` done 의 `result`: outline → `{"fallback": bool, "auto": bool}`(A1), concepts → `{"concepts": [str], "cards": [gen_id]}`(K5).
- 프론트 `RELOAD.concepts = ["topics", "work"]`(`utils/workEvents.ts:27`, K7).

### 1-5. 프론트 타입 (`frontend/types/work.ts` — 모두 선택 필드로 더한다)

```ts
// A3
export interface SectionGen { gen_id: number; status: GenStatus }
// Outline 에: auto?: boolean;  (A3)   background?: string;  (X3)
// ProposalView 에: section_gens?: Record<string, SectionGen>;  (A3)
// OutlinePut 에: background?: string;  (X3)
// ProposalSection.basis 에: question?: string;  (X3)

// S3
export interface SectionSourceExcerpt { chunk_id: string; page_start: number | null; page_end: number | null; text: string }
export interface SectionSource { cnts_id: string; abstract: string; excerpt: SectionSourceExcerpt | null }
export type SectionSources = Record<string, SectionSource>;
export interface CitePick { key: string; pid: string; si: number; eid: string; cntsId: string; genId: number; sentence: string }

// K7
export interface KeywordCandidate { text: string; source: "llm" | "paper" | "both"; n: number }
// WorkView 에: concept_candidates?: KeywordCandidate[] | null;
// TopicCard 에: keywords?: string[];   TopicCard.checks 에: missing_keywords?: string[];
```

`frontend/types/history.ts`·`utils/historyStore.ts` 등 기록 쪽 프론트 타입·가게는 06e 가 고치지 않는다 — `HistoryListOut.total?` 는 06d 가 단다(06d 계획의 기록 total 받기 Task, spec §12-5 의 06e 경계는 백엔드 세 파일뿐). 06e(H2)는 응답에 `total` 을 싣기만 한다. 딥리드 타입은 `utils/deepReadSse.ts` 가 내보낸다(R2): `DeepReadSource { page_start: number; page_end: number; text: string }`, `DeepReadMessage { role: "user" | "assistant"; content: string; sources?: DeepReadSource[]; pinnedChip?: number }`.

### 1-6. 프론트 상수·함수 (한 이름은 한 파일만 내보낸다 — Nuxt 자동 import 중복 경고)

| 파일 | 내보내는 이름(시그니처) | Task |
|---|---|---|
| `utils/workPhase.ts` | `FINAL_STEP_NAME = "보고서"`, `MAKE_REPORT = \`${FINAL_STEP_NAME} 만들기\``, `REMAKE_REPORT = \`${FINAL_STEP_NAME} 다시 만들기\`` | A3 |
| `utils/workPhase.ts` | `STEP_NAMES: Readonly<Record<"explore" \| WorkStep, string>>` = `{ explore: "탐색", topics: "제목 고르기", reading: "참고문헌 선택하기", proposal: FINAL_STEP_NAME }`(지금의 비공개 `STEP_LABEL` 을 이것으로 갈음 — 06d 사이드바가 읽을 수 있게 내보냄), `ONBOARDING_LEAD: string`, `stepLine(phase)` 시그니처 그대로 | R1 |
| `utils/proposalView.ts` | `sectionKeysOf(p: ProposalView): string[]`(목차 묶음 순서 → "gap" — `proposalDocument.printedKeys` 는 이것을 부른다), `autoChainOn(p: ProposalView \| null, work: WorkView \| null): boolean`, `autoTargets(p: ProposalView): string[]`, `nextAutoSection(p: ProposalView, skip: ReadonlySet<string>): string \| null`, `isNoSectionPapers(err: unknown): boolean`, `interface TocItem { key: string; no: string; label: string; anchor: string; status: SectionStatus \| "text" \| "blank" \| "skipped" }`, `docToc(p: ProposalView, state: WorkState, skipped: ReadonlySet<string>): TocItem[]`(anchor 는 아래 1-7 '문서 자리 id' 표), `interface ReportBar { label: string; done: number; total: number; percent: number; running: boolean }`, `reportBar(p: ProposalView, state: WorkState, skipped: ReadonlySet<string>, stopped = false): ReportBar \| null`(정함 28 — 조사 없는 꼴 `` `${FINAL_STEP_NAME} 작성 중 · ${done}/${total}절 — 「${이름}」` ``. `stopped` 가 참이면(연쇄가 오류로 멈춤) 남은 절을 세지 않아 쓰는 절이 없을 때 null — [이어서 쓰기] 줄만 남는다. 끝난 절 = done·failed·건너뜀·생성 기록이 있는 쓰기 전(취소) 절), `outlineBackground(outline: Outline): string`(`Outline.background` 타입 필드는 X3 이 더하므로 그 전에도 읽게 교차 타입으로 읽는다 — X3 뒤에도 그대로 컴파일된다) | A3 |
| `utils/proposalView.ts` | `putOnceMore<T>(put: (version: number) => Promise<T>, version: number): Promise<T>` | X3 |
| `utils/proposalView.ts` | `interface ReviewSpots { unmarked: number; numbers: number; first: { key: string; pid: string } \| null }`, `reviewSpots(p: ProposalView): ReviewSpots`, `reviewLine(r: ReviewSpots): string \| null` | X4 |
| `utils/outlineEdit.ts` | `OUTLINE_BACKGROUND_MAX = 2000`, `fieldPut(outline: Outline, patch: { method?: string; background?: string }): OutlinePut` | X3 |
| `utils/proposalDocument.ts` | `ProposalDocInput.acceptedOnly: boolean`(← `includeProposed`), `proposalFileName(topicTitle: string, date: Date, acceptedOnly: boolean): string`, `disclosureLines(p: ProposalView, acceptedOnly: boolean, now: Date): string[]`, `printedKeys`·`printedProposedCount` 그대로(이름·의미), `UNREVIEWED_WATERMARK` 삭제 | X5 |
| `utils/deepReadSse.ts`(새) | `DeepReadSource`·`DeepReadMessage`·`type DeepReadEvent = { type: "text"; text: string } \| { type: "sources"; sources: DeepReadSource[] } \| { type: "done" }`, `parseSse(buffer: string, chunk: string): { buffer: string; events: DeepReadEvent[] }`, `CHAT_ERROR_TEXT = "오류가 발생했습니다. 다시 시도해주세요."`, `CHAT_STOPPED_TEXT = "(답을 받다가 멈췄습니다)"`, `CHAT_STOPPED_EMPTY = "(답을 받기 전에 멈췄습니다)"` | R2 |
| `composables/useDeepReadChat.ts`(새) | `useDeepReadChat(opts: { cntsId: () => string; store?: () => Map<string, DeepReadMessage[]> \| undefined; fetchFn?: typeof fetch }): { messages: Ref<DeepReadMessage[]>; streamingText: Ref<string>; isStreaming: Ref<boolean>; send(text: string): Promise<void>; stop(): void }` — 옵션·반환 모양에 이름을 붙여 `DeepReadChatOptions`·`DeepReadChat` 으로 함께 내보낸다(이 파일만) | R2 |
| `utils/deepRead.ts`(새) | `type DocKind = "book" \| "paper"`, `interface ChatCopy { greeting(title?: string): string; placeholder: string; inputLabel: string; sendLabel: string }`, `chatCopy(kind: DocKind): ChatCopy`, `sourceLabel(src: DeepReadSource): string`, `sourcePdfTarget(cntsId: string, title: string, src: DeepReadSource): OpenPdfPayload` | R3 |
| `utils/deepRead.ts` | `type PanelTab = "sources" \| "chat"`, `PANEL_SIDE_MIN_PX = 1200`, `PANEL_FULL_MAX_PX = 768`, `type PanelMode = "side" \| "drawer" \| "full"`, `panelMode(width: number): PanelMode`, `interface PanelPaper { cntsId: string; meta: PaperMeta }`, `panelHead(p: PanelPaper): { title: string; byline: string }`, `panelTabs(step: "reading" \| "proposal"): PanelTab[]` | R4 |
| `utils/readingList.ts` | `firstPathChunk(item: ReadingItem): { label: string; chunk: PathChunk } \| null` | R5 |
| `utils/citationEvidence.ts`(새) | `NGRAM_N = 2`, `EXCERPT_MATCH_MIN = 0.2`(S3 검토 반영 — 파트 S 메모 12), `excerptSentences(text: string): string[]`, `ngramOverlap(a: string, b: string, n?: number): number`, `citedClaims(sentence: string, eid?: string): string[]`(S3 3차 검토 반영 — 메모 12), `bestExcerptSentence(cited: string, excerpt: string, eid?: string): number \| null`, `excerptParts(excerpt: string, cited: string, eid?: string): { text: string; mark: boolean }[]`(`eid` 는 3차 검토 반영 — 누른 칩의 근거 번호, S4 가 `CitePick.eid` 를 넘긴다), `citationPdfTarget(source: SectionSource, title: string): OpenPdfPayload` | S3 |
| `utils/topicDeck.ts` | `MIN_PICKED_KEYWORDS = 2`, `type CardStatus` 에 `"blocked"`, `cardStatus(item: TopicItem, concepts?: WorkGeneration \| null): CardStatus`, `keywordSpans(title: string, keywords: readonly string[]): { text: string; mark: boolean }[]`, `keywordsChanged(card: TopicCard, concepts: readonly string[]): boolean`, `keywordWarning(card: TopicCard): string \| null`, `interface KeywordChip { text: string; pressed: boolean; badge: string \| null }`, `keywordChips(candidates: readonly KeywordCandidate[] \| null \| undefined, picked: readonly string[]): KeywordChip[]`, `toggleKeyword(picked: readonly string[], text: string): string[]`, `regenerateProblem(picked: readonly string[]): string \| null`, `aiCardsStale(topics: TopicsView, concepts: readonly string[], conceptsGen?: WorkGeneration \| null): boolean`(다시 만들 AI 자리 — 키워드 생성이 실패해 카드가 없는 씨앗 자리(`blocked`)도 세고 다시 만드는 중인 카드는 세지 않는다), `cardRemakingNote(item: TopicItem): string \| null`(다시 만드는 중인 카드의 '새 키워드로 다시 만드는 중입니다'), `canPick` 은 시그니처 그대로 카드 생성이 열린 카드면 거짓 | K7 |
| `utils/topicDeck.ts` | `SHORT_TITLE_MAX = 18`(← 비공개 `CHIP_TITLE_CHARS = 12` 를 지움), `chipLabel(meta: PaperMeta \| undefined, cntsId: string): string`, `chipTooltip(meta: PaperMeta \| undefined, cntsId: string): string` | H1 |
| `composables/useAutoReport.ts`(새) | 아래 1-7 | A4 |
| `composables/useResearchWork.ts` `useWorkApi()` | `getSectionSources(jobId: string, key: string, gen: number) => api<SectionSources>(\`${job(jobId)}/sections/${encodeURIComponent(key)}/sources\`, { query: { gen } })`(S3), `regenerateTopics(jobId: string) => api<{ topic_ids: number[]; gen_ids: number[]; skipped: number }>(\`${job(jobId)}/topics/regenerate\`, { method: "POST" })`(K7) | S3·K7 |

### 1-7. 컴포저블·컴포넌트 인터페이스

```ts
// composables/useAutoReport.ts (A4)
export interface AutoReportDeps {
  proposal: Readonly<Ref<ProposalView | null>>;
  work: Readonly<Ref<WorkView | null>>;
  generate: (key: string) => Promise<unknown>;   // api.generateSection(jobId, key)
  reload: () => Promise<void>;                    // proposal·work 를 다시 읽는다
}
export interface AutoReportHandle {
  running: Readonly<Ref<boolean>>;
  stopped: Readonly<Ref<string | null>>;          // 멈춘 까닭(workErrorMessage) — null 이면 멈추지 않음
  skipped: Readonly<Ref<ReadonlySet<string>>>;    // 409 no_section_papers 로 건너뛴 절 키(이 방문만)
  resume: () => void;                             // [이어서 쓰기]
}
export function useAutoReport(deps: AutoReportDeps): AutoReportHandle;
```

| 컴포넌트 | props 더함·바뀜 | emits 더함 | Task |
|---|---|---|---|
| `components/work/ProposalSection.vue` | `skipped?: boolean`·`autoNext?: boolean`(A5 — `autoNext` 는 연쇄가 돌고 멈추지 않았을 때 남은 절, 쓰기 전 안내가 '차례가 오면 자동으로 씁니다'), `activeCite?: { pid: string; si: number; eid?: string } \| null`(`eid` — 한 문장에 칩이 둘이면 누른 칩만 펼침), `panelId?: string`(S4), `jobId` prop 은 지운다(S4 — 지우는 상세 링크만 썼다) | `cite: [pick: CitePick, el: HTMLElement]`(S4) | A5·S4 |
| `components/work/ProposalStep.vue` | 그대로 | `"open-pdf": [payload: OpenPdfPayload]`, `panel: [open: boolean]`(S4) | S4 |
| `components/work/ReadingStep.vue` | 그대로 | `panel: [open: boolean]`(R5) | R5 |
| `components/work/ReadingTable.vue` | `activeId?: string \| null`, `panelId?: string` | `open: [cnts: string, el: HTMLElement]` | R5 |
| `components/work/DocField.vue`(새) | `{ fieldId: string; label: string; value: string; max: number; placeholder: string; readOnly: boolean; busy: boolean }` | `save: [text: string]` | X3 |
| `components/work/DeepReadPanel.vue`(새) | `{ panelId: string; paper: PanelPaper \| null; tabs: readonly PanelTab[]; tab: PanelTab; detailHref: string \| null; store: Map<string, DeepReadMessage[]> }`; 슬롯 `extra`(머리 아래)·`sources`(인용 근거 탭 본문) | `close: []`, `"update:tab": [tab: PanelTab]`, `"open-pdf": [payload: OpenPdfPayload]`, `detail: [e: MouseEvent]` | R4 |
| `components/work/CitationSource.vue`(새) | `{ pick: CitePick; meta: PaperMeta \| null; source: SectionSource \| null; loading: boolean; error: string \| null }` | `"open-pdf": [payload: OpenPdfPayload]`, `chat: []` | S4 |
| `components/BookChat.vue` | `docKind?: DocKind`(기본 "book"), `store?: Map<string, DeepReadMessage[]>`, `pdfLinks?: boolean`(기본 false) | `"open-pdf": [payload: OpenPdfPayload]` | R2·R3 |
| `components/work/ConceptChips.vue` | `{ concepts: string[]; candidates: KeywordCandidate[] \| null; generation: WorkGeneration \| null; readOnly: boolean; busy: boolean; stale: boolean }` | `save: [concepts: string[]]`(그대로 — [키워드만 저장]), `regenerate: [concepts: string[]]`(새), `retry: [genId: number]`(그대로 — `ConceptChips.vue:71`) | K8 |
| `components/work/TopicCard.vue`·`TopicDeck.vue` | `concepts: string[]`, `conceptsGen: WorkGeneration \| null` 더함(TopicDeck 은 그대로 내려 준다) | 그대로 | K8 |

- 패널 id: ReadingStep `wk-panel-reading`, ProposalStep `wk-panel-proposal`. 패널 제목 id `${panelId}-title`.
- `[id].vue` 바인딩(정함 30 — 06d 계획의 LNB 접기 연결 Task 와 같은 계약): `<ReadingStep … @open-pdf="openPdf" @panel="workPanelOpen = $event" />`(:73, R5), `<ProposalStep … @open-pdf="openPdf" @panel="workPanelOpen = $event" />`(:74, S4). script 한 줄 `const workPanelOpen = ref(false);`(+ 주석 한 줄)을 `:514`(`const { pdf, closePdf } = pdfOpener;`) 바로 뒤에 넣는다(R5 — §12-5 의 `:57-75` 밖이지만 리스너가 쓸 변수라 06e 가 넣는 유일한 script 줄). **06d 의 LNB 접기 연결 Task 는 리스너·새 ref·`watch(step)` 를 넣지 않고 `workPanelOpen` 을 읽기만 한다** — 늦게 머지하는 줄(06d 의 그 Task 또는 이 계획의 Task R6)이 고치는 곳은 `[id].vue:3-7` 의 루트 `is-lnb-collapsed` 와 `AppSidebar :collapsed="workPanelOpen"` 두 곳뿐이다. 이름(`panel`·`workPanelOpen`)을 바꾸려면 06d 계획과 함께 바꾼다.
- 문서 자리 id(보고서 화면 — `docToc` 의 anchor 와 같은 글자. A5 가 모두 그리고 X3 이 2·6절 칸을 DocField 로 바꾼다):

| 문서 자리 | id | 그리는 것 | Task |
|---|---|---|---|
| 1 주제 | `wk-doc-topic` | `outline.topic.title`(목차가 없으면 자리 없음) | A5 |
| 2 연구 배경 | `wk-doc-background` | A5: `outline.background` 글 또는 흐린 `연구 배경을 아직 적지 않았습니다.` → X3: DocField | A5·X3 |
| 3.n 선행연구 묶음 | `wk-sec-<key>`(예 `wk-sec-prior.g1` — `ProposalSection.vue:3` 의 기존 `:id` 그대로) | ProposalSection | A5 |
| 4 연구 공백 | `wk-sec-gap` | ProposalSection | A5 |
| 5 연구 질문 | `wk-doc-question` | `outline.question`, 없으면 흐린 `연구 질문을 아직 정하지 않았습니다 — [목차 고치기]에서 고르세요.` — 자동 확정이 고른 질문을 사용자가 여기서 본다 | A5 |
| 6 방법 | `wk-doc-method` | A5: `outline.method` 글 또는 흐린 `방법을 아직 적지 않았습니다.` → X3: DocField. 머리 목차·자리 제목의 이름은 `SECTION_LABELS.method` 의 `방법 제안`(Word 6절 제목 `proposalDocument.ts:135` 과 같은 말) | A5·X3 |

  - 1·2·5·6 자리는 `<section :id class="rs-card wk-doc__part">` 와 `h3 class="wk-doc__part-title" tabindex="-1"`(`1. 주제` …)이다. 머리 목차 항목을 누르면 그 id 로 `scrollIntoView` 하고 그 안의 첫 `h3` 에 `focus({ preventScroll: true })` — ProposalSection 의 `h3`(`:5`)에도 A5 가 `tabindex="-1"` 를 더한다.

### 1-8. CSS (`frontend/assets/css/work.css` — 06b 보강 6 의 '이어 붙이는 자리' 표시 줄(`:1231`)을 old 로 잡고 그 위에 한 묶음씩 더한다. 근거 장부 블록 `:75-166`·`:1216-1220` 은 건드리지 않는다)

| 선택자 묶음 | Task |
|---|---|
| `.wk-doc`·`.wk-doc__toc`·`.wk-doc__toc-head`·`.wk-doc__toc-list`·`.wk-doc__toc-item`·`.wk-doc__toc-no`·`.wk-doc__toc-label`·`.wk-doc__toc-status`·`.wk-doc__part`·`.wk-doc__part-title`·`.wk-doc__text`·`.wk-doc__resume`(`.wk-doc__status` 는 쓰지 않는다), 문서 자리마다 `scroll-margin-top: 6rem` | A5 |
| `.wk-rbar`(토큰 `--wk-bar-thick: 1rem` 를 여기 정의, `@media (max-width: 768px)` 에서 `0.75rem`)·`.wk-rbar__line`(1rem 굵게)·`.wk-rbar__pct`(1.25rem 굵게, 오른쪽 끝)·`.wk-rbar__track`·`.wk-rbar__fill`·`.wk-rbar__fill.is-running`(움직임 — `prefers-reduced-motion` 이면 멈춤, 쓰는 중이면 채움에 최소 폭). 막대는 `position: sticky; top: 0.5rem`(`.wk-pill` 선례 — 절이 아래로 쌓여도 밀려 사라지지 않게) | A5(정함 28) |
| `.wk-docfield`·`.wk-docfield__line`·`.wk-docfield__text`·`.wk-docfield__count` | X3 |
| `.wk-review`·`.wk-review__jump`·`.wk-psec__item:focus-visible`(문단 `li` 의 `tabindex="-1"` 초점) | X4 |
| `.wk-split`(토큰 `--wk-panel-w: 22rem` 를 여기 정의)·`.wk-split__main`·`.wk-split.is-panel-open`·`.wk-panel`·`.wk-panel__head`·`.wk-panel__title`·`.wk-panel__byline`·`.wk-panel__close`·`.wk-panel__tabs`·`.wk-panel__tab`·`.wk-panel__body`·`.wk-panel__extra`·`.wk-panel__heading`·`.wk-panel__detail`·`.wk-panel__chat`·`.wk-panel__sources`·`.wk-panel .skx-chat-*`(BookChat 여백 덮기)·`@keyframes wk-panel-in`·`.wk-panel-backdrop` + `@media (max-width: 1199px)`(오버레이 서랍 — 루트에 `.skx-chat-side` 클래스를 함께 달아 모양 재사용)·`@media (max-width: 768px)`(전체 폭)·`prefers-reduced-motion` | R4 |
| `.wk-reading__open`·`.wk-reading__detail`·`.wk-reading__row--active`·`.wk-panel__save`·`.wk-panel__path`·`.wk-panel__path .wk-path__quote`(기존 `.wk-path__quote` 재사용 — 여백만) | R5 |
| `.wk-cite`·`.wk-cite__card`·`.wk-cite__title`·`.wk-cite__byline`·`.wk-cite__quote`·`.wk-cite__heading`·`.wk-cite__text`·`.wk-cite__excerpt`·`.wk-cite__mark`·`.wk-cite__actions`·`.wk-psec__sent.is-cited`·`button.wk-psec__cite`(버튼 기본값 지우기·펼침·초점 — `.wk-psec__cite` 모양은 그대로)·`@media (forced-colors: active)` | S4 |
| `.wk-kw`(제목 속 `<mark>`)·`.wk-kwchip`·`.wk-kwchip[aria-pressed="true"]`·`.wk-kwchip__badge`·`.wk-topic__kwwarn`·`.wk-topic__kwchanged`·`.wk-concepts__regen`·`.wk-topic--blocked`(06b 의 `.wk-concept`·`.wk-concept__remove` 는 쓰지 않게 되지만 지우지 않는다 — 시각 디자인 담당 정리 몫) | K8 |

보조 선택자는 그 묶음 이름(`wk-doc`·`wk-rbar`·`wk-docfield`·`wk-review`·`wk-panel`·`wk-reading`·`wk-cite`·`wk-kw`·`wk-concepts`·`wk-topic`) 아래에만 둔다 — 다른 Task 의 이름과 겹치지 않는다. `style_skovix.css` 의 `.skx-chat-side` 블록(`:4823-4877`)은 고치지 않는다 — 06e 경계에 있지만 재사용만 하고 덮어쓰기는 `work.css` 의 `.wk-panel.skx-chat-side` 로 한다(전역 CSS 를 대회 전에 흔들지 않는다).

### 1-9. 공용 고정 예제

- **일치(참·거짓)의 정본은 06c 의 `frontend/tests/fixtures/term_checks.json` 의 `contains` 칸이다**(06c 계획의 공용 고정 예제 — `{"text", "word", "expected", "note"}`, 06c 의 terms.py Task 가 만들고 06c 의 두 테스트(`test_research_terms.py`·`test_research_eval.py`)가 지킨다). 06e 는 그 파일을 고치지 않고 읽기만 한다(K9 — 06c dev 머지 뒤). 같은 사례를 06e 파일에 다시 두지 않는다 — 규칙이 바뀌면 두 파일을 따로 맞추게 된다.
- `frontend/tests/fixtures/keyword_match.json`(새, K7) — 06e 에만 필요한 **하이라이트 자리**만 둔다: `[{ "text": str, "word": str, "marked": [str], "note": str }]`(`marked` 가 비면 일치하지 않음). 사례마다 `term_checks.json` 의 `contains` 칸과 같은 text/word 를 쓰고(06c 사례 가운데 하이라이트를 볼 만한 것), 06e 에만 있는 사례(영문 casefold)는 note 에 '06e 만'을 적는다. 처음 사례:
  1. `노인의 우울과 사회적 지지` / `노인 우울` → `["노인", "우울"]`(낱말이 순서대로 — term_checks 와 같은 사례)
  2. `노인의 우울` / `우울 노인` → `[]`(순서가 다르다 — 같은 사례)
  3. `다문화 가정 아동` / `다문화가정` → `["다문화 가정"]`(공백 무시 — 원문 자리는 공백을 품는다, 같은 사례)
  4. `ＣＳＲ과 재무성과` / `csr` → `["ＣＳＲ"]`(NFKC·casefold — 원문 글자 그대로 감싼다, 같은 사례)
  5. `공공도서관 서비스` / `도서관` → `["도서관"]`(부분 문자열 — 같은 사례)
  6. `컴퓨팅 자원 할당` / `클라우드` → `[]`(같은 사례)
  7. `Digital Library Use` / `digital library` → `["Digital Library"]`(casefold — 06e 만)
  - 읽는 쪽: 프론트 K7 은 이 파일로 `keywordSpans` 의 자리를 본다(06c 머지 전에도 돈다). K9 는 ① 백엔드 — `contains(text, word) == bool(marked)` 를 이 파일로, ② 프론트 — `term_checks.json` 의 `contains` 칸 전부에서 `keywordSpans(text, [word]).some((p) => p.mark) === expected` 를 본다(빈 word 는 표시 없음 = false). pytest 경로는 `Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "<파일>"`(`marker_checks.json` 선례).
  - `keywordSpans` 의 원문 자리 매핑: 원문 코드포인트마다 `ch.normalize("NFKC").toLowerCase()` 를 이어 붙이며 각 글자의 원문 위치를 기록한다(공백은 건너뛴 별도 배열로 공백 제거 대조). K9 ② 에서 06c 사례와 어긋나면 `keywordSpans` 를 고친다 — `term_checks.json` 은 고치지 않는다(정본).

---

## 다른 줄과의 경계·머지 문 (§12-5·§12-6)

**06e 가 고치는 것(§12-5)** — `app/services/research_work/*`, `app/api/research_{work,topics,reading,proposal}.py`(이 계획은 `research_reading.py` 를 고치지 않는다), `app/workers/research_work_tasks.py`(경계 안이지만 이 계획은 고치지 않는다 — 워커 `_close` 의 `has_queued → send_dispatch` 가 새 카드 생성을 그대로 집는다), 프롬프트 `research_concepts.yaml`·`research_topic_card.yaml`·새 `book_chat.paper.yaml`, `app/services/chat/book_chat.py`, 기록 total(`app/api/history.py`·`app/repositories/history.py`·`app/schemas/history.py`), `components/work/*`(EvidenceLedger 제외), `work.css`(근거 장부 블록 제외), `types/work.ts`, `composables/useResearchWork.ts`·`useReadingSaves.ts`(`:53` 문구)·새 `useAutoReport.ts`·`useDeepReadChat.ts`, `utils/work*`·`proposal*`·`topicDeck`·`readingList`·`outlineEdit`·새 `deepRead*`·`citationEvidence`, `BookChat.vue`, `[id].vue:57-75`.

**예외(이 계획이 경계 밖에서 고치는 줄 — 다른 줄은 이 줄을 건드리지 않는다)**
- `frontend/pages/papers/index.vue:564-569`(06d 파일)·`frontend/pages/papers/[id].vue:433-437` — BookChat 에 `doc-kind="paper"` 한 속성(Task R3, spec §12-5).
- `frontend/pages/research/[id].vue` script `:514`(`const { pdf, closePdf } = pdfOpener;`) 뒤 `workPanelOpen` 두 줄(주석 한 줄 + `const workPanelOpen = ref(false);` — Task R5). 리스너가 쓸 변수다. 06d 는 이 두 줄을 고치지 않고 AppSidebar 연결 때 이 변수를 읽는다(정함 30).
- `app/schemas/book.py` `BookOut.doc_type`(Task S2) — 어느 줄의 경계에도 없다. 응답에 선택 필드 하나가 더해질 뿐이다.
- `app/models/research_work.py` 머리 주석(Task A1·X1·K4·K9) — 주석만. 06c 는 `app/models/research.py` 만 고친다.
- `app/scripts/verify_prompt_parity.py`(Task S2) — 줄 몇 개(`book_chat.paper` 렌더 확인).

**06c(질의 — `feat/round06c-query-broadening`)에서 받는 것(06c 를 따른다)**

| 06e 가 기대는 것 | 06c 가 만드는 것 | 06e 자리 | 어긋나면 |
|---|---|---|---|
| 낱말 일치 `contains(text: str, word: str) -> bool` | `app/services/research/terms.py` — NFKC → casefold → 공백 제거 뒤 부분 문자열, 아니면 낱말이 모두 순서대로('노인 우울' ↔ '노인의 우울') | Task K9(`topic_card.keyword_misses`) | K9 Step 1 이 dev 를 받은 뒤 `grep -n "^def contains"` 로 시그니처를 확인한다 — 이름·인자 순서가 다르면 06e 호출부만 맞추고 본문 '알아 둘 것'에 적는다 |
| 일치 참·거짓의 공용 고정 예제 | `frontend/tests/fixtures/term_checks.json`(`{"text", "word", "expected", "note"}` — 06c 의 terms.py Task 가 만들고 06c 의 두 테스트 `test_research_terms.py`·`test_research_eval.py` 가 지킨다) | Task K9(프론트 `keywordSpans` 가 그 `contains` 칸과 같은 참·거짓인지) | 06e 는 그 파일을 고치지 않는다 — 어긋나면 `keywordSpans` 를 고친다(정본은 06c). 06e 의 `keyword_match.json`(Task K7)은 하이라이트 자리만 둔다 |
| 06c 기본값 커밋(Q4 — `app/services/research/state.py` `DEFAULT_PARAMS` 의 `broaden`·`query_context`) | 06c 판정 뒤 dev 에 들어간다 | 06e 는 그 파일을 고치지 않는다 — dev 에 있으면 10/17~18 배포(Task Z5)의 워커·fastapi 이미지에 함께 실린다 | Task Z5 Step 1 이 dev 값과 운영 값을 적고, 배포 뒤 06c 세션에 06c 계획의 '10/17~18 배포 뒤 06c 확인'을 알린다 |
| 06c 의 탐색 후보 이벤트(`candidates`)·`questionUsedFromSteps`·PlanCard `questionUsed`·`researchEvents.ts`·`types/research.ts` | — | 06e 는 쓰지 않고 고치지 않는다 | — |

**06d(진행 화면·입구 — `feat/round06d-research-progress-screen`)와의 경계**

| 경계 | 내용 |
|---|---|
| 연구 화면 머리 | 06d 의 고정 진행 막대는 끝나지 않은 잡에만 서고, 06e 의 `WorkStepper`·보고서 화면의 큰 막대(정함 28 — `ProposalStep` 안)는 이어간 연구(이어가기는 completed 잡에서만 된다)의 단계 화면에만 선다 — 한 화면에 함께 서지 않는다. `WorkStepper.vue` 는 06e 파일이고 06d 는 고치지 않는다. 06e 는 06d 의 `research.css` 토큰·부품(`ResearchProgressBar.vue`)을 import 하지 않고 `work.css` 에 같은 크기 규칙의 값만 둔다 |
| `[id].vue` | `:57-75`(단계 본문)와 script `workPanelOpen` 두 줄은 06e, 그 밖은 06d. import 블록이 겹칠 수 있다 — 늦게 머지하는 쪽이 dev 를 받아 맞춘다 |
| LNB 접기(정함 30 — 06d 계획과 같은 문장) | "06e 는 ReadingStep·ProposalStep 의 emit `panel: [open: boolean]` 과 `[id].vue:73-74` 의 리스너 `@panel="workPanelOpen = $event"`, script 의 `const workPanelOpen = ref(false);`(`:514` 뒤)까지 단다. `AppSidebar :collapsed="workPanelOpen"` 와 루트 `is-lnb-collapsed`(`[id].vue:3-7` 두 곳)는 늦게 머지하는 줄이 단다 — 06d 가 늦으면 06d 계획의 LNB 접기 연결 Task 가, 06e 가 늦으면 이 계획의 Task R6 이 이 두 곳만 고친다. 06d 의 그 Task 는 리스너·새 ref·`watch(step)` 를 넣지 않고 `workPanelOpen` 을 읽기만 한다." 이름(`panel`·`workPanelOpen`)을 바꾸려면 두 계획을 함께 고친다 |
| 06d 가 읽기만 하는 06e 파일 | `utils/workPhase.ts`(`stepLine`·`stepForPhase`·`scopeLine`, 그리고 Task R1 이 내보내는 `STEP_NAMES`)·`composables/useResearchWork.ts`(`useWorkApi().getWork`·`putReading`)·`types/work.ts`(`Corpus`·`WorkPhase`)·`utils/researchErrors.ts`. 06e 는 이 파일의 **기존 export 이름·시그니처를 지키고 새 이름만 더한다** — 06d 테스트는 그 함수의 출력으로 기대값을 만들어 06e 의 이름 바꾸기에 깨지지 않는다. 06d 는 단계 이름 문자열을 새로 쓰지 않는다 |
| '모두 보기 (N)' | 06e(Task H2)는 응답(`app/schemas/history.py`)에 `total` 을 싣기만 한다. 프론트 타입 `types/history.ts` 의 `HistoryListOut.total?`·`utils/historyStore.ts`·`useHistory`·`AppSidebar.vue` 로 나르고 그리는 것은 06d 다 — 06e 는 프론트 기록 파일을 건드리지 않는다. 06d 는 `total` 이 없으면 N 없이 그린다 — 머지 순서에 묶이지 않는다 |
| `work.css` | 근거 장부 블록은 06d, 나머지는 06e. 06e 의 새 묶음은 표시 줄 위에만 더한다 |
| `pages/papers/index.vue` | 06d 파일. 06e 는 `:564-569` BookChat 에 `doc-kind="paper"` 한 속성만(Task R3) — 06d 의 [딥리서치로 더 깊게]·[담기 ▾] 와 다른 자리 |
| 고치지 않는 06d 파일 | `EvidenceLedger.vue`·`utils/evidenceLedger.ts`·`research.css`·`components/research/*`(`ReportPrint.vue` 는 H3 이 import 만)·`AppSidebar.vue`·랜딩 `pages/index.vue` |

**머지·배포 문(§12-6)**
- **06e 는 06c 운영 배포(10/13~14)가 끝난 뒤에만 `dev` 에 머지한다.** 06c 배포는 그때의 dev 로 워커·fastapi 이미지를 만든다 — 06e 가 먼저 들어가면 06e 백엔드(목차 자동 승인·카드 시점 변경)가 nuxt 없이 함께 나가 옛 화면에 연쇄 없는 승인 목차·카드 없는 주제가 남는다. Task Z4 Step 1 이 이 문을 확인한다.
- **06d 와의 순서는 묶이지 않는다** — 기본은 06e → 06d 이고 배포는 한 번(10/17~18, 워커 셋 → fastapi → nuxt → reload — nuxt 이미지는 06e·06d 가 다 든 dev 로 한 번만 만든다, Task Z5 경우 가). 06e 가 10/17 까지 못 들어오면 06d 가 먼저 머지·배포(nuxt 만)하고 LNB 접기 연결·`[id].vue` 맞춤은 늦게 머지하는 06e 가 한다(Task R6, Task Z5 경우 다).
- **06c 기본값 커밋**은 판정 날 배포하지 않고 10/17~18 배포에 싣는다 — 새 잡의 params 는 fastapi 가 만들 때 기본값으로 채우므로(`app/api/research.py:235`) fastapi 가 바뀌어야 켜진다. 06e 배포가 celery-research·celery-research-plan·celery-control·fastapi 를 같은 이미지로 Recreate 하므로 dev 에 있는 기본값이 그대로 나간다(Task Z5 — 그 값을 배포 기록에 적는다).
- **자르는 순서(spec §12-6 — 06e 몫):** 뒤처지면 **Task H3(PDF)** 를 하지 않는다(10/16 조건 — Task 머리에 적었다). 그다음 자를 것은 06e 에 없다(근거 칩 다섯 곳 통일 M 은 이미 하지 않는다 — Q3 S). **자르지 않는 것:** 보고서 자동 산출(파트 A — 회의 '최우선'), 내보내기 기본값과 공개 부록(Task X5 — 자동 산출이 수락 관문을 없애 지금 기본 Word 는 빈 절로 나간다, D21), 시연 정직성 규칙.

---

## 파트 순서와 Task ID

Task 는 파트 영문 접두 + 번호로 부른다(다른 Task 를 부를 때도 'Task A3' 꼴 그대로). 파트 안 번호는 실행 순서이고 접미 글자(A4b 꼴)는 쓰지 않는다. 다른 줄의 Task 는 ID 가 아니라 내용으로 부른다(예: '06c 계획의 terms.py', '06d 계획의 LNB 접기 연결 Task'). 파트 순서는 spec §12-4 의 제안 순서다 — 보고서 자동 산출 → 내보내기 기본값 → 참고문헌 선택하기·딥리드·인용 근거 → 제목 고르기 → 근거 칩 표기 → 기록 total → PDF.

| 파트 | Task | 내용 |
|---|---|---|
| — | Task 0 | worktree·기준선 확인 |
| A 보고서 자동 산출(D20) | A1 → A5 | A1 목차 자동 확정 — `outline.apply` 가 승인 목차(`auto`)로 저장 · A2 ProposalView 의 절 키별 마지막 section 생성·근거 없음 409 에 code · A3 자동 산출 판정 순수 함수(남은 절·머리 목차·진행 막대)·타입·버튼 이름 상수 · A4 절 연쇄 `useAutoReport` · A5 보고서 화면(큰 진행 막대·머리 목차·문서 자리 1~6·[보고서 만들기]) |
| X 보고서 마무리·내보내기 기본값(D20 남은 항목·D21) | X1 → X5 | X1 연구 배경 저장·연구 질문이 바뀌어도 '다시 맞춤 필요' · X2 연구 공백 단정 다듬기 · X3 연구 배경·방법 칸(승인 상태에서 쓰고 버전 충돌은 한 번 다시) · X4 검토할 곳 요약 · X5 내보내기 기본값·문단 상태 이름 |
| R 단계 이름·참고문헌 선택하기·오른쪽 딥리드(D23 이름·D24) | R1 → R6 | R1 단계 이름 바꾸기(보이는 글만) · R2 딥리드 스트림 분리(SSE 파서·`useDeepReadChat`) · R3 BookChat 문서 종류·출처 칩 버튼·논문 화면 두 호출처 · R4 오른쪽 딥리드 패널 부품 · R5 참고문헌 선택하기 — 제목을 누르면 오른쪽 딥리드 · **R6 (조건부 — 06d 가 먼저 dev 에 머지됐을 때만)** LNB 접기 연결 |
| S 인용 근거·딥리드 논문 프롬프트(D24) | S1 → S4 | S1 인용 근거 조회 API · S2 딥리드 논문 프롬프트(`book_chat.paper.yaml`) · S3 인용 근거 하이라이트 순수 함수·타입·조회 · S4 인용 칩을 누르면 오른쪽 인용 근거 탭 |
| K 제목 고르기(D23) | K1 → K9 | K1 논문 키워드 채움률 1회성 측정 · K2 후보 키워드(원천 합치기·일반어·위 3개) · K3 WorkView 에 키워드 후보 · K4 카드 입력에 고른 키워드·제목 규칙 한 줄·[다른 방향]도 지금 키워드 · K5 카드는 키워드가 정해진 뒤 씨앗 자리마다 한 번 · K6 [이 키워드로 다시 만들기] · K7 키워드 판정 순수 함수·공용 고정 예제 · K8 키워드 칩·제목 하이라이트·다시 만들기 화면 · **K9 (선행 조건 — 06c dev 머지 뒤)** 제목 키워드 검사·세 번 놓친 카드 |
| H 근거 칩·기록 total·PDF | H1 → H3 | H1 근거 칩 표기(Q3 S) · H2 기록 목록 kind 별 total · **H3 (조건부 — 10/16 까지 앞 Task 가 다 끝났을 때만)** 보고서 PDF 내보내기 |
| Z 마무리 | Z1 → Z7 | Z1 K1 측정 결과 반영(사용자 서버 실행 → 상수 판정) · Z2 전체 회귀·경계 확인·영역별 정적 리뷰·반영 · Z3 문서(완료노트·00_status·spec) · Z4 dev 머지(사용자 승인 — 머지 문·조건부 Task 판정) · Z5 운영 배포(사용자 — 워커 셋 → fastapi → nuxt → reload) · Z6 운영 처음부터 끝까지 1회(사용자) · Z7 배포 기록 |

**전역 실행 순서(파트가 서로의 파일·이름을 쓴다 — 이 순서로 한다):** Task 0 → A1 → A2 → A3 → A4 → A5 → X1 → X2 → X3 → X4 → X5 → R1 → R2 → R3 → R4 → R5 → S1 → S2 → S3 → S4 → R6(조건부) → K1 → K2 → K3 → K4 → K5 → K6 → K7 → K8 → K9(선행 조건) → H1 → H2 → H3(조건부) → Z1 → Z2 → Z3 → Z4 → Z5 → Z6 → Z7.
- **R6 은 파트 R 에 적혀 있지만 S4 뒤에 한다** — S4 가 `[id].vue:74` 의 리스너를 단 뒤라야 두 단계 화면의 패널이 모두 LNB 를 접는다. 판정은 Task R6 Step 1 대로 `git log dev --oneline --merges | grep -c "feat/round06d-research-progress-screen"`(06d 의 LNB 접기 연결 조건과 대칭 — 문서 브랜치 머지를 세지 않는다)이고, 06e 의 dev 머지 직전(Task Z4 Step 1)에 한 번 더 본다. S4 를 마친 때 06d 가 dev 에 없으면 건너뛰고 Task Z4 Step 1 에서 다시 본다(06d 가 그 사이 들어왔으면 그때 R6 을 한다).
- **K9 는 06c 가 dev 에 들어온 뒤에만 한다.** K8 을 마쳤을 때 06c 가 dev 에 없으면 H1·H2 를 먼저 하고 돌아온다(`topicDeck.test.ts` 의 K9 it 와 H1 it 는 서로 다른 describe 라 순서가 바뀌어도 Edit old 가 겹치지 않는다). 06e 의 dev 머지는 어차피 06c 운영 배포 뒤라 K9 없이 머지하는 경우는 없다(Task Z4 Step 1).
- **H3 은 맨 마지막이다** — 10/16 에 A1~H2(K9 포함, R6 은 조건대로)가 모두 끝났을 때만 한다.
- **Z1 은 K1 을 커밋한 뒤 언제든 사용자에게 맡길 수 있다**(서버의 읽기 전용 SELECT) — 결과 커밋은 Z2 의 회귀 전에 들어간다.

**의존:** A2 ← A1 · A4 ← A3 · A5 ← A2·A3·A4 · X1 ← A2 · X3 ← A5 · X4 ← X3 · X5 ← X4·A3 · R1 ← A5·X3·X5 · R3 ← R2 · R4 ← R3 · R5 ← R1·R4 · S1 ← X1 · S4 ← R4·R5·S3·X5 · R6 ← R5·S4·06d dev 머지 · K2 ← K1(판정은 뒤 — 상수 기본 1) · K3 ← K2 · K4 ← K3 · K5 ← K4 · K6 ← K5 · K7 ← R1 · K8 ← K7 · K9 ← K4·K7·06c dev 머지 · H1 ← K7 · H3 ← X5·S4 · Z ← 전부. A3·X2·R2·S2·S3·K1·H2 는 앞 Task 에 기대지 않는다(순서만 위와 같다).

**병렬:** 백엔드 줄기(A1→A2→X1→S1 · X2 · S2 · K2→K3→K4→K5→K6→K9 · H2)와 프론트 줄기는 서로 코드에 기대지 않는다(공통 계약의 모양만). 프론트 안에서는 A3→A4→A5→X3→X4→X5→R1 이 한 사슬이고 R2→R3→R4, S3, K7 은 그 사슬과 독립이다(R5·S4·K8·H1·H3 이 다시 합친다). 한 세션이 순서대로 하는 것이 기본이고, 나눠 맡길 때는 아래 '같은 파일' 표의 순서를 지킨다(06b 병렬 시도 교훈 — 줄을 멈출 때는 파일 신호가 아니라 작업 중지로, `round06b-완료노트.md:46`).

### 같은 파일 — 고치는 순서와 범위

> 같은 파일은 이 순서로만 고친다. 뒤 Task 의 Edit old 는 앞 Task 뒤의 글자다(본문은 "Task Xn 뒤 기준" 으로 적는다). `work.css` 는 1-8 의 표시 줄 규칙.

| 파일 | 순서: Task(범위) |
|---|---|
| `app/services/research_work/outline.py` | A1(`apply`·`_now`·`auto_question`) → X1(`apply` 의 연구 배경 이어 받기·`select` import·docstring) |
| `app/api/research_proposal.py` | A1(`NEED_READING` :53) → A2(`NO_SECTION_PAPERS_CODE` 상수·:395-396 detail) → X1(import·`OutlinePut` :74-78·`put_outline` :260-266) → R1(`IF_MATCH_FORMAT` :57·`VERSION_CONFLICT` :58) → S1(`NO_SECTION_SOURCE_GEN`·`Query` import·파일 끝 새 핸들러) |
| `app/services/research_work/proposal_views.py` | A2(`section_gens_of`·`proposal_view` 결과 키·docstring) → X1(`stale_flags` 절 루프·docstring :3-6) → S1(`section_sources`) |
| `app/models/research_work.py`(주석만) | A1(Outline `auto`) → X1(Outline `background`·Section basis `question`) → K4(Card `keywords`) → K9(Card checks `missing_keywords`) |
| `app/services/research_work/topic_card.py` | K4(`_build`·docstring) → K5(`enqueue_seed_cards`·import) → K6(`apply` 의 고른 카드 검사·docstring) → K9(`contains` import·`keyword_misses`·`_bind`·`_check`·`_soft_check`·`EXECUTOR`) |
| `app/services/research_work/generate.py` | K2(`Executor.check` 주석 :47 — 주석만) → K9(docstring·`Executor.soft_check`·`run_generation`) |
| `app/api/research_work.py` | R1(`CONCEPTS_BUSY` :53·`patch_work` 422 :252 문구) → K2(`continue_research` 의 concepts input·import) → K3(`_concept_candidates`·`_view`) → K5(`continue_research` 카드 루프·docstring·`cancel_generation`) |
| `app/services/research_work/views.py` | K3(`work_view` 의 `concept_candidates`) |
| `app/api/research_topics.py` | K4(`KEYWORDS_BUSY`·`_concepts_open` import·`generate_topics` 409·:149 keywords) → K6(상수 셋·`regenerate_topics`) |
| `app/tests/test_research_work_outline.py` | A1 → X1(`TestApply.test_a_new_outline_keeps_the_research_background`) |
| `app/tests/test_research_proposal_api.py` | A1 → A2 → X1 → S1(R1 은 고치지 않는다 — `:591` 이 `VERSION_CONFLICT` 를 상수 이름으로 읽는다) |
| `app/tests/test_research_work_topic_card.py` | K4 → K5 → K6(`TestApply.test_a_picked_topic_stays_picked` ✎) → K9 |
| `app/tests/test_research_work_executor.py` | K2(`TestExecutorFields::test_concepts_marks_an_empty_done_as_retryable` — 개념 실행기에 `bind`) → K5(`TestApplyDelegation::test_concepts_keep_the_06a_branch` — 반영 결과의 `cards`) → K9(무른 검사) |
| `app/tests/test_research_work_tasks.py` | K2(`TestDispatch` 두 테스트 — 저장 출력의 `candidates`·일반어만 낸 답) → K5(`TestDispatch` 두 이벤트 result 의 `cards`) |
| `app/tests/test_research_work_api.py` | R1(`:510` `CONCEPTS_BUSY` 글자 기대 — 매개변수 둘) → K2(`TestContinue` 두 테스트 — 대역 lambda·paper_keywords) → K3(`TestContinue` WorkView dict·`TestGetWork`) → K5(`TestContinueSeeds`·`TestCancelGeneration`) |
| `app/tests/test_research_work_views.py` | K3 |
| `app/tests/test_research_topics_api.py` | K4(`TestOtherDirection`) → K5(`TestEndToEnd`) → K6(`TestRegenerate`) |
| `frontend/types/work.ts` | A3(`SectionGen`·`Outline.auto`·`ProposalView.section_gens`) → X3(`Outline.background`·`OutlinePut.background`·basis `question`) → S3(인용 근거 타입·`CitePick`) → K7(키워드 타입) |
| `frontend/utils/workPhase.ts` | A3(`FINAL_STEP_NAME`·버튼 상수) → R1(`STEP_NAMES`·`PHASE_LINE`·`ONBOARDING_*`·`continueCard`) |
| `frontend/utils/proposalView.ts` | A3(자동 산출 함수·`sectionKeysOf`·`docToc`·`reportBar`) → X3(`putOnceMore`) → X4(`reviewSpots`·`reviewLine`) → X5(`footprintLine`) |
| `frontend/utils/proposalDocument.ts` | A3(`printedKeys` 본문 한 줄) → X5(나머지 전부) |
| `frontend/utils/topicDeck.ts` | R1(`SEED_KIND_LABEL` :34·`conceptsNote` 문구) → K7(키워드 함수·`cardStatus`·`cardNote`·`canPick`·`cardRemakingNote`) → H1(`evidenceChips`·칩 표기) |
| `frontend/utils/readingList.ts` | R1(`outlineHint` 문구) → R5(`firstPathChunk`) |
| `frontend/utils/deepRead.ts`(새) | R3(만듦 — 문구·출처) → R4(패널 함수) |
| `frontend/composables/useResearchWork.ts` | S3(`getSectionSources`) → K7(`regenerateTopics`) |
| `frontend/components/work/ProposalStep.vue` | A5(큰 진행 막대·머리 목차·문서 자리 1·2·5·6·연쇄·[목차 고치기]·버튼 이름) → X3(2·6절 자리를 DocField 로) → X4(검토할 곳 줄) → X5(내보내기 카드) → R1(제목·문구) → S4(`.wk-split`·패널·emits) → H3(PDF) |
| `frontend/components/work/ProposalSection.vue` | A5(:3-6 머리·:5 `h3 tabindex`·`skipped`·:195-197) → X3(:19-22 다시 맞춤 안내에 '연구 질문') → X4(문단 `li` `tabindex`·sr-only) → X5(`STATE_LABELS`) → S4(인용 칩 버튼·상세 링크 함수와 `jobId` prop 삭제·`activeCite`) |
| `frontend/components/work/ReadingStep.vue` | A5(버튼·확인 문구) → X3(`REMAKE_CONFIRM`) → R1(제목·문구) → R5(패널) |
| `frontend/components/work/ReadingTable.vue` | R1(:3 `aria-label`) → R5(:29-37 제목 버튼·상세 링크·`activeId`·`panelId`·emit `open`) |
| `frontend/components/work/OutlineEditor.vue` | R1(:10·:14·:92·:201-202 문구)만 — A5 는 부르는 쪽(ProposalStep)에서 접기만 한다 |
| `frontend/components/work/CandidateDrawer.vue` | R1(:7 문구)만 |
| `frontend/components/work/TopicsStep.vue` | R1(제목·문구) → K8(키워드 연결) |
| `frontend/components/work/ConceptChips.vue` | R1(보이는 '키워드') → K8(토글 칩으로 다시 짬) |
| `frontend/components/BookChat.vue` | R2(script → composable) → R3(props·문구·출처 칩·aria-live) |
| `frontend/pages/research/[id].vue` | R1(:60 요약 띠 버튼 글) → R5(:73 `@panel`·script :514 뒤 두 줄) → S4(:74) → R6(조건부 :3-7) |
| `frontend/assets/css/work.css` | A5 → X3 → X4 → R4 → R5 → S4 → K8(각자 1-8 의 묶음, 표시 줄 위) |
| `frontend/tests/unit/proposalView.test.ts` | A3 → X3 → X4 → X5 |
| `frontend/tests/unit/topicDeck.test.ts` | R1(`seedLine` 기대 :194·:198·`conceptsNote` 기대 :305-312) → K7 → H1 → K9(`term_checks.json` 일치 it — 06c 머지 뒤라 H1 보다 늦을 수 있다. 서로 다른 describe 라 순서가 바뀌어도 Edit old 가 겹치지 않는다) |
| `frontend/tests/unit/readingList.test.ts` | R1 → R5 |
| `frontend/tests/unit/deepRead.test.ts`(새) | R3 → R4 |
| `frontend/tests/unit/workPhase.test.ts` | A3 → R1 |

**각 Task 의 기대 수(파트 본문 '통과 확인' 의 'Task 앞 + N' — 매개변수는 펼친 수, 통합 사본 실측):**
- 백엔드: A1 +3 · A2 +2 · X1 +6(목차 반영이 연구 배경을 이어 받는 테스트 1 포함) · X2 +15(그대로 남는 사례 5·CLAIM 삽입 문맥 2 포함) · S1 +10(`test_unknown_key_is_422` 매개변수 셋) · S2 +6(`test_prompts.py` +1 · 새 `test_book_chat_prompt.py` 5 — `_book_references` 1 포함) · K2 +47(새 `test_research_work_keywords.py` 44 · `test_research_work_concepts.py` +3) · K3 +3 · K4 +6 · K5 +10 · K6 +8(`TestApply.test_a_picked_topic_stays_picked` 매개변수 +1 포함) · K9 +14 · H2 +3 = **+133**, 새 테스트 파일 2개(`test_research_work_keywords.py`·`test_book_chat_prompt.py`). K1·R1 은 +0(R1 은 `test_research_work_api.py:510` 의 글자 기대만 ✎), Z1 은 판정이 2 이거나 구분자를 더할 때만 +1 씩.
- 프론트: A3 +24 · A4 +11 · X3 +8 · X4 +4 · X5 +1(`proposalDocument.test.ts` 18 → 19 — '미수락 문단도 넣기' 두 it 을 하나로 합치고 연구 배경 it·'수락한 문단만'의 검토할 곳 it 을 더한다) · R1 +1 · R2 +10 · R3 +4 · R4 +3 · R5 +3 · S3 +12 · K7 +18(검토 반영의 `canPick`·`cardRemakingNote` it 과 blocked 씨앗 자리 `aiCardsStale` it 포함) · H1 +2 · K9 +9(06c `term_checks.json` 의 contains 사례 — 처음부터 통과) = **+110**, 새 테스트 파일 5개(`useAutoReport`·`deepReadSse`·`useDeepReadChat`·`deepRead`·`citationEvidence`) — `Test Files` 40 → 45. A5·X5 의 화면 몫·R6·S4·K8·H3 은 `.vue` 라 +0.

---

## 파일 구조 (만들고 고칠 파일과 책임)

**백엔드 — 새 파일** (`app/` 기준)

| 파일 | 책임 | Task |
|---|---|---|
| `services/research_work/keywords.py` | 키워드 후보 정리(NFKC·공백·1~40자·일반어 거르기)·목록 키워드 나누기·채택 논문 키워드의 문서 빈도·LLM 후보와 합치기(출처·편수·상한 10)·위 3개 미리 선택(순수) | K2 |
| `domains/nl_library/prompts/book_chat.paper.yaml` | 딥리드 논문 변형 프롬프트 — `book_chat.yaml` 과 같은 변수·params, 글만 '논문'(예시 없음) | S2 |
| `tests/test_research_work_keywords.py` | `keywords.py` 의 정리·나누기·편수·합치기·미리 선택 | K2 |
| `tests/test_book_chat_prompt.py` | `chat_prompt(book)` 가 논문·책을 가르는지, `BookOut.doc_type` — FlagEmbedding·pymilvus 대역은 `_stubbed_book_chat` fixture 안에서만(`test_search_chunk_answer_flag.py:24-53` 꼴 — 새로 import 한 모듈을 teardown 에서 빼는지 보는 되돌림 테스트 포함) | S2 |

**백엔드 — 고칠 파일**

| 파일 | 고치는 것 | Task |
|---|---|---|
| `services/research_work/outline.py` | `apply` 가 질문이 있으면 승인 목차(`state approved`·`approved_at`·`auto: true`)로, 새 `_now`·`auto_question`, 반환 `{"fallback", "auto"}`(A1), 옛 목차의 연구 배경을 새 목차에 이어 받음(X1) | A1·X1 |
| `api/research_proposal.py` | `NEED_READING` 문구(A1), 근거 없음 409 의 `{"code", "message"}`(A2), `OutlinePut.background`·`put_outline`(X1), `VERSION_CONFLICT`·`IF_MATCH_FORMAT` 문구(R1), 새 `GET …/sections/{key}/sources`(S1) | A1·A2·X1·R1·S1 |
| `services/research_work/proposal_views.py` | `section_gens_of`·ProposalView `section_gens`(A2), `stale_flags` 의 연구 질문 비교(X1), `section_sources`(S1) | A2·X1·S1 |
| `models/research_work.py` | JSONB 모양 머리 주석만(Outline `auto`·`background`, Section basis `question`, Card `keywords`·`checks.missing_keywords`) | A1·X1·K4·K9 |
| `services/research_work/shapes.py` | `OUTLINE_BACKGROUND_MAX = 2000` | X1 |
| `services/research_work/progress.py` | `sections_filled` 가 `outline.background` 도 연구 배경으로 센다 | X1 |
| `services/research_work/section_input.py` | 선행연구·연구 공백 절 입력의 `basis` 에 연구 질문 | X1 |
| `services/research_work/markers.py` | `GAP_CLAIM_CONTEXT`·`GAP_CLAIM_TAIL`·`GAP_CLAIM_REWRITES` — 코퍼스 범위 문장의 '확인했다' 단정을 공백 후보 투로(`soften_claims`) | X2 |
| `services/chat/book_chat.py` | `chat_prompt(book)` — `doc_type` 이 있으면 그 변형 프롬프트, `_book_references(book)` — 참고문헌 의도 질문이 `BookOut.references` 를 읽는다(속성 없음·None 은 빈 목록 — 정함 31) | S2 |
| `schemas/book.py` | `BookOut.doc_type: Optional[str] = None`(예외 파일) | S2 |
| `scripts/verify_prompt_parity.py` | `book_chat.paper` 가 같은 변수로 렌더되고 base 와 다른지 | S2 |
| `services/research_work/concepts.py` | 개념 생성을 키워드 후보로 넓힘 — `concepts_input(job, paper_keywords=…)`, `_parse`·`_bind`·`_check`·`_empty`, `EXECUTOR.bind`, 쓰지 않게 된 `MIN_CONCEPTS` 지움 | K2 |
| `domains/nl_library/prompts/research_concepts.yaml` | '키워드 후보', 출력 키 `keywords`, 개수·예시 없음 | K2 |
| `api/research_work.py` | `CONCEPTS_BUSY`·`patch_work` 422 문구(R1), 이어가기의 `paper_keywords`(K2), `_concept_candidates`·`_view`(K3), 이어가기는 주제 행만·취소면 씨앗 카드(K5) | R1·K2·K3·K5 |
| `services/research_work/views.py` | `work_view(…, concept_candidates=…)` | K3 |
| `services/research_work/seeds.py` | `topic_input(…, keywords=…)` | K4 |
| `services/research_work/topic_card.py` | `_build` 의 `keywords`(K4), `enqueue_seed_cards`(K5), `apply` 가 고른 카드를 새 결과로 덮지 않음(K6), `keyword_misses`·`_bind`·`_check`·`_soft_check`·`EXECUTOR.soft_check`(K9) | K4·K5·K6·K9 |
| `domains/nl_library/prompts/research_topic_card.yaml` | `{% if keywords %}` 제목 규칙 한 줄(예시 제목·이전 제목 없음) | K4 |
| `api/research_topics.py` | [다른 방향]의 409 `KEYWORDS_BUSY`·지금 키워드(K4), 새 `POST …/topics/regenerate`(K6) | K4·K6 |
| `services/research_work/apply.py` | 개념 반영 뒤 늘 `enqueue_seed_cards` → 결과 `{"concepts", "cards"}` | K5 |
| `services/research_work/generate.py` | `Executor.check` 주석의 '개념 2개 이상'을 지금 규칙으로(K2 — 주석만), `Executor.soft_check`, `run_generation` 이 무른 통과 출력을 보관해 끝내 엄격한 검사를 못 넘으면 그것을 돌려준다(K9) | K2·K9 |
| `repositories/history.py` | `count(session_id, kind)`(+ `list` 와 같은 where 를 쓰는 `_live`) | H2 |
| `api/history.py` | `list_history` 가 `total` 을 싣는다 | H2 |
| `schemas/history.py` | `HistoryListOut.total: int \| None = None` | H2 |
| 기존 테스트 | `test_research_work_outline.py`(A1·X1) · `test_research_proposal_api.py`(A1·A2·X1·S1) · `test_research_work_section_input.py`·`test_research_work_enqueue.py`(X1) · `test_research_work_markers.py`·`test_research_work_paragraph_edit.py`(X2) · `test_prompts.py`(S2) · `test_research_work_concepts.py`(K2) · `test_research_work_api.py`(R1·K2·K3·K5) · `test_research_work_views.py`(K3) · `test_research_work_seeds.py`(K4) · `test_research_work_topic_card.py`(K4·K5·K6·K9) · `test_research_topics_api.py`(K4·K5·K6) · `test_research_work_dispatch.py`(K5) · `test_research_work_tasks.py`(K2·K5) · `test_research_work_executor.py`(K2·K5·K9) · `test_research_work_generate.py`(K9) · `test_history_repository.py`·`test_history_api.py`(H2) | — |

고치지 않는다: `workers/research_work_tasks.py`·`workers/research_tasks.py`(회수기 — `_close` 의 `has_queued` → `send_dispatch` 가 새 카드 생성을 집는다), `services/research/*`, 딥리서치 프롬프트, `alembic/`.

**1회성(`research/`)**: `research/round06e-keyword-candidates/README.md`(목적·판정 규칙·실행 방법·결과 칸)·`measure.py`(읽기 전용 SELECT — 채움률·최근 연구 20건의 채택 논문 키워드 비율·653 원문 표본·연구별 키워드 수) — Task K1, 서버 실행 결과 `out/fill_rate.md` 와 README '결과'는 Task Z1.

**프론트 — 새 파일** (`frontend/` 기준)

| 파일 | 책임 | Task |
|---|---|---|
| `composables/useAutoReport.ts` | 보고서 화면의 절 연쇄 — 남은 절을 하나씩 넣고(앞 응답 뒤 다음), 근거 없음은 건너뛰고, 그 밖의 오류는 멈춰 [이어서 쓰기] | A4 |
| `components/work/DocField.vue` | 보고서 2·6절 자리의 연구 배경·방법 칸(보기 ↔ 고치기·남은 글자 수·예시 연구는 보기만) | X3 |
| `utils/deepReadSse.ts` | 딥리드 SSE 파서·메시지 타입·오류·멈춤 문구(순수) | R2 |
| `composables/useDeepReadChat.ts` | 딥리드 스트림 — 논문별 대화 `store`·`cntsId` 감시·AbortController·멈춘 답 남기기 | R2 |
| `utils/deepRead.ts` | 책·논문 문구, 출처 칩 표기(저장값 그대로)·원문 열기 대상(R3), 패널 모드·머리·탭(R4)(순수) | R3·R4 |
| `components/work/DeepReadPanel.vue` | 오른쪽 패널 — 탭 [인용 근거 \| 딥리드], 머리 서지·[논문 상세 ↗]·닫기, 2단 sticky·서랍·전체 폭, 초점 가두기·Esc | R4 |
| `utils/citationEvidence.ts` | 대목 문장 나누기·글자 n-gram 겹침·가장 많이 겹친 문장·하이라이트 조각·원문 열기 대상(순수) | S3 |
| `components/work/CitationSource.vue` | 인용 근거 탭 — 논문 카드·대목 하이라이트(없으면 초록)·[원문 보기]·[이 논문과 대화하기] | S4 |
| `tests/fixtures/keyword_match.json` | 제목 하이라이트 자리의 공용 사례 `{text, word, marked, note}`(06c `term_checks.json` 과 같은 text/word + 06e 만의 영문 사례) | K7 |
| `tests/unit/useAutoReport.test.ts`·`deepReadSse.test.ts`·`useDeepReadChat.test.ts`·`deepRead.test.ts`·`citationEvidence.test.ts` | 위 순수 함수·composable 의 vitest | A4·R2·R3·R4·S3 |

**프론트 — 고칠 파일**

| 파일 | 고치는 것 | Task |
|---|---|---|
| `types/work.ts` | `SectionGen`·`Outline.auto?`·`ProposalView.section_gens?`(A3), `Outline.background?`·`OutlinePut.background?`·basis `question?`(X3), 인용 근거 타입·`CitePick`(S3), 키워드 타입(K7) — 모두 선택 필드 | A3·X3·S3·K7 |
| `utils/workPhase.ts` | `FINAL_STEP_NAME`·`MAKE_REPORT`·`REMAKE_REPORT`(A3), `STEP_NAMES`(비공개 `STEP_LABEL` 을 갈음)·단계 문구·`ONBOARDING_LEAD`·온보딩·`continueCard`(R1) | A3·R1 |
| `utils/proposalView.ts` | `sectionKeysOf`·`autoChainOn`·`autoTargets`·`nextAutoSection`·`isNoSectionPapers`·`docToc`·`reportBar`(A3), `putOnceMore`(X3), `reviewSpots`·`reviewLine`(X4), `footprintLine` 머리(X5) | A3·X3·X4·X5 |
| `utils/proposalDocument.ts` | `printedKeys` 가 `sectionKeysOf` 를 부름(A3), `acceptedOnly`·워터마크 없음·2절 연구 배경·부록 상태별 개수·파일 이름(X5) | A3·X5 |
| `utils/outlineEdit.ts` | `OUTLINE_BACKGROUND_MAX`·`fieldPut` | X3 |
| `utils/topicDeck.ts` | `SEED_KIND_LABEL`('딥리서치 보고서의 향후 과제')·`conceptsNote` 문구(R1), 키워드 판정 함수·`cardStatus`(`blocked`)·`cardNote`·`canPick`·`cardRemakingNote`(K7), 근거 칩 `chipLabel`·`chipTooltip`·`SHORT_TITLE_MAX`(H1) | R1·K7·H1 |
| `utils/readingList.ts` | `outlineHint` 문구(R1), `firstPathChunk`(R5) | R1·R5 |
| `utils/workEvents.ts` | `RELOAD.concepts` 에 `topics` | K7 |
| `composables/useResearchWork.ts` | `useWorkApi()` 에 `getSectionSources`(S3)·`regenerateTopics`(K7) | S3·K7 |
| `composables/useReadingSaves.ts` | `:53` 문구 | R1 |
| `components/work/ProposalStep.vue` | 큰 진행 막대·머리 목차·문서 자리·연쇄·[목차 고치기]·버튼 이름(A5), 2·6절 DocField(X3), '검토할 곳' 줄(X4), 내보내기 카드(X5), 단계 이름(R1), `.wk-split`·패널·emits(S4), PDF(H3) | A5·X3·X4·X5·R1·S4·H3 |
| `components/work/ProposalSection.vue` | `h3 tabindex`·`skipped`·안내 문구·머리 목차 번호 붙은 절 이름(A5), 다시 맞춤 안내에 '연구 질문'(X3), 문단 `li` 초점·화면낭독 `(근거 표시 없음)`(X4), 상태 이름 'AI 작성 · 검토 전'(X5), 인용 칩 버튼·`activeCite`·`jobId` prop 삭제(S4) | A5·X3·X4·X5·S4 |
| `components/work/ReadingStep.vue` | [보고서 만들기]·확인 문구(A5), 확인 문구의 연구 배경·연구 질문(X3), 단계 이름(R1), `.wk-split`·딥리드 패널·[담음]·첫 대목(R5) | A5·X3·R1·R5 |
| `components/work/ReadingTable.vue` | `aria-label`(R1), 제목 버튼·[논문 상세 ↗]·행 강조(R5) | R1·R5 |
| `components/work/OutlineEditor.vue`·`OnboardingModal.vue`·`FunnelCounter.vue`·`WorkStepper.vue`·`CandidateDrawer.vue` | 단계 이름(보이는 글·`WorkStepper.vue:3` 주석), 딥리서치 보고서를 가리키는 글에 '딥리서치'(`OutlineEditor.vue:92`·`CandidateDrawer.vue:7` — 같은 줄의 '읽기 후보'는 '참고문헌 후보') | R1 |
| `components/work/TopicsStep.vue` | 단계 이름·문구(R1), 키워드 후보·다시 만들기 연결(K8 — ConceptChips 의 `stale` 은 `aiCardsStale(topics, view.concepts, conceptGen)`) | R1·K8 |
| `components/work/ConceptChips.vue` | '키워드'(R1), 후보 토글 칩·배지·직접 더하기·[이 키워드로 다시 만들기](K8) | R1·K8 |
| `components/work/TopicCard.vue`·`TopicDeck.vue` | 제목 키워드 하이라이트·'제목에 「…」 없음'·'키워드가 바뀌었습니다'·`cardStatus(item, conceptsGen)` | K8 |
| `components/BookChat.vue` | 스트림 → `useDeepReadChat`(R2), `docKind`·`store`·`pdfLinks`·출처 칩 버튼·[원문 보기]·`aria-live`(R3) | R2·R3 |
| `pages/research/[id].vue` | `:60` 요약 띠 버튼 글 `[딥리서치 보고서 보기]`(R1), `:73`·`:74` 의 `@open-pdf`·`@panel`, script `workPanelOpen` 두 줄(R5·S4), 루트 `is-lnb-collapsed`·`AppSidebar :collapsed`(R6 — 조건부) | R1·R5·S4·R6 |
| `pages/papers/index.vue`·`pages/papers/[id].vue` | BookChat 에 `doc-kind="paper"` 한 속성(예외) | R3 |
| `assets/css/work.css` | 표시 줄 위에 묶음 — `.wk-doc*`·`.wk-rbar*`(A5), `.wk-docfield*`(X3), `.wk-review*`(X4), `.wk-split*`·`.wk-panel*`(R4), `.wk-reading__open` 등(R5), `.wk-cite*`(S4), `.wk-kw*`·`.wk-kwchip*`·`.wk-topic__kw*`(K8) | A5·X3·X4·R4·R5·S4·K8 |
| 기존 테스트 | `proposalView.test.ts`(A3·X3·X4·X5) · `workPhase.test.ts`(A3·R1) · `outlineEdit.test.ts`(X3) · `proposalDocument.test.ts`(X5) · `readingList.test.ts`(R1·R5) · `topicDeck.test.ts`(R1·K7·H1·K9) · `workEvents.test.ts`(K7) | — |

고치지 않는다: '실행 전 알아 둘 것'의 '고치지 않는 파일' 목록(특히 `citations.ts`·`citations.test.ts`·`components/research/*`·`EvidenceLedger`·`types/history.ts`·`historyStore.ts`·`term_checks.json`).

**문서**(Task Z1·Z3·Z7): `research/round06e-keyword-candidates/README.md`·`out/fill_rate.md`(Z1), `docs/roadmap/round06e-완료노트.md`(새 — Z3, §5 는 Z7), `docs/roadmap/00_status.md`(round06 줄만), spec(머리 상태 줄·D2·D20·D21·D23·D24·D27·§12-3 오프셋 행 한 구절·§12-4 의 줄 번호·카드 시점 한 문장·§12-10 Q2·Q3·§12-11 아홉 항목), 필요하면 `docs/ops/recurring-gotchas.md`(Z7).

---

## spec 항목 → Task 대응 (06e 범위 — 하지 않는 것 포함)

| spec 항목 | Task |
|---|---|
| D20 [보고서 만들기] 한 번 — 누르는 것(ReadingStep :63-70·:56, 담음 5편 조건 그대로) | A3(이름 상수)·A5 |
| D20 목차 자동 확정(question 첫 후보 → 카드 질문, method "", approved, approved_at, auto) | A1 |
| D20 절 연쇄 — 도는 조건(approved·auto·예시 아님) | A3(`autoChainOn`)·A4 |
| D20 PUT /outline 은 auto 를 지킨다 · [보고서 다시 만들기] 는 새 apply 라 auto 가 다시 | A1(테스트로 고정)·A5(확인 문구 — 정함 4) |
| D20 대상 = 절도 생성 기록도 없는 키 · ProposalView 에 절 키별 마지막 section 생성 · WorkView 를 쓰지 않음 | A2·A3 |
| D20 failed·canceled 키는 다시 넣지 않음 | A3(`autoTargets` — 기록이 있으면 대상 아님) |
| D20 하나씩 — 앞 POST 응답 뒤 다음, 생성 완료는 기다리지 않음 | A4 |
| D20 409 NO_SECTION_PAPERS → 그 절만 '근거가 없어 쓰지 않았습니다' 후 다음 | A2(code)·A3(`isNoSectionPapers`)·A4·A5 |
| D20 그 밖의 4xx·5xx·네트워크 → 멈추고 [이어서 쓰기] | A4·A5 |
| D20 탭을 닫았다 와도 이어 넣음 | A4(조건을 서버 값으로 다시 계산 — 정함 6) |
| D20 절 여럿을 한 엔드포인트로 묶지 않는다 | 안 함 — 묶는 엔드포인트를 만들지 않는다(최악 300초) |
| D20 화면 — 목차가 머리 목차, 절 자리 상태 재사용, 문구 두 곳(ProposalStep :56·ProposalSection :195-197) | A3(`docToc`)·A5(머리 목차·문서 자리 1~6 — 자동 확정한 연구 질문이 5절 자리에 보인다) |
| 사용자 Q1 답 '현재 절 작성 중 커다란 프로그레스바'(06e 자동 보고서 화면에도 적용 — 이 계획의 판단, 2026-10-11 사용자 확인) | A3(`reportBar`)·A5(막대 그리기 — 정함 28) |
| D20 연구 배경은 자동으로 쓰지 않음 — 사용자 칸(저장 §12-11) | X1·X3 |
| D20 방법 — 승인 상태에서도 쓰는 칸, approve:true 유지 | X3(정함 8) |
| D20 연쇄 중 409 version_conflict → 응답 version 으로 한 번, 두 번째면 오류 | X3(`putOnceMore`) |
| D20 선택 기능 지우지 않음([목차 고치기]·절 다시 쓰기·문단 수락·다시·고치기·직접 쓰기) | A5(OutlineEditor 를 [목차 고치기] 뒤로 — 지우지 않음) |
| D20 목차를 고쳐 다시 승인하면 쓴 절은 '다시 맞춤 필요'와 [이 절 다시 쓰기]만 | A3(대상 규칙)·기존 stale(06b) |
| D20 연구 질문을 바꿔도 '다시 맞춤 필요'(질문을 절 basis 로) | X1(정함 9) |
| D20 검토 단서 '검토할 곳: …' | X4(+X5 부록 한 줄 — 정함 11) |
| D20·06b 이월 §7-13 연구 공백 '확인했다' 단정 · 두 번 거쳐도 같음 · 사용자가 고친 글도 | X2(정함 10) |
| D20 결과·논의·가설 수치를 쓰지 않음(D2) | 안 함 — 그대로(생성 범위 변경 없음) |
| D21 Word 기본 = 전부·워터마크 없음 | X5 |
| D21 부록 = 절별 문단 상태 개수·날짜·결과·논의 미포함, 모델 이름·시도 기록 뺌 | X5 |
| D21 '수락한 문단만' 선택지 유지(워터마크 없음) | X5 |
| D21 바꿀 곳 `proposalDocument.ts` :39·:75·:108·:69·:150-153·:42-44·:170-172·:255-274, `ProposalStep.vue:75-94`, `proposalDocument.test.ts` | X5 |
| 문단 상태 보이는 이름 'AI 작성 · 검토 전'(Q8 동의), 저장 값 그대로 | X5 |
| 딥리서치 보고서 내보내기 출력 그대로 | X5(기존 테스트 '보고서 문서 모델은 watermark 키를 만들지 않는다' 유지)·안 함(보고서 쪽 코드 변경 없음) |
| PDF(싸면 — 마지막 Task, 10/16 조건, ReportPrint 재사용, 같은 기본값) | H3(조건부) |
| D23 단계 ② 이름 '제목 고르기'(TopicsStep :6, ReadingStep :48, workPhase :16·:21·:117, OnboardingModal :12, workPhase.test) | R1 |
| D23 핵심 개념 칩 → 키워드 칩(보이는 글) | R1·K8 |
| D23 후보 상한 10·하한 없음·개수는 코드가 자름·프롬프트에 개수 없음·일반어 금지 목록 | K2 |
| D23 순서(LLM 먼저, 논문 키워드만 있는 것 편수 내림차순, 둘 다면 LLM 자리에 편수)·PRESELECT 3 | K2 |
| D23 원천 — 개념 생성을 후보로 넓힘 + 채택 논문 키워드 문서 빈도·이어가기 때 FastAPI 가 input 에 | K2 |
| D23 논문 키워드 채움률 1회성 측정 | K1(스크립트)·Z1(서버 실행·판정) |
| D23 저장(스키마 변경 없음) — output {concepts, candidates}, research_works.concepts = 선택, 선택 저장은 PATCH …/work | K2·K3·K8(PATCH 그대로) |
| D23 WorkView concept_candidates(최신 done 개념 생성 따로 조회) | K3 |
| D23 카드 시점 — 주제 행은 이어가기, topic_card 생성은 개념 반영 때 같은 트랜잭션 | K5 |
| D23 한 번만 · done(빈 결과 포함)과 cancel 이 한 함수 · 취소면 키워드 없이 · failed 는 [다시 부르기] done 때 · 회수기 안 고침 | K5('한 번만' = 씨앗 자리 행마다 — 정함 29)·K4(개념 생성 중 [다른 방향] 409) |
| D23 화면 — 빈 카드 waiting / '키워드를 다시 부르면 카드를 만듭니다' · RELOAD.concepts 에 topics | K7·K8 |
| D23 제목 규칙 — input keywords(옛 행 `or []`)·프롬프트 `{% if keywords %}` 한 줄·StrictUndefined 라 _build 가 늘 넘김·예시 제목 없음·이전 제목 안 줌 | K4 |
| D23 검사 — `_bind` 가 keywords·missing_keywords, 일치 = 06c contains, 하나도 없으면 재시도 사다리 | K9 |
| D23 세 번 다 놓친 카드(§12-11) | K9(정함 17)·K7·K8(경고) |
| D23 하이라이트 `keywordSpans` `<mark>`·백엔드와 공용 고정 예제 | K7·K8·K9 |
| D23 [이 키워드로 다시 만들기] 새 엔드포인트(edited 아닌 AI 카드만·열린 생성 건너뜀) | K6·K8 |
| D23 [다른 방향]도 지금 키워드 | K4(개념 생성이 열려 있으면 409 `KEYWORDS_BUSY` — 정함 29) |
| D23 '키워드가 바뀌었습니다' | K7·K8 |
| D23 칩 UI(aria-pressed·출처·편수 배지·후보 없는 옛·예시 연구는 concepts 를 선택된 칩) | K7·K8 |
| D23 주의 — 묶음 수 ≤ 키워드 수 | K7·K6(최소 선택 2 — 정함 15) |
| D23 [더 구체적으로] 를 대신함 | 해당 없음 — refine 은 만들지 않는다(D19) |
| D27 근거 칩 표기 — 제1저자 전체 이름 연도·SHORT_TITLE_MAX 18·툴팁 서지 한 줄 | H1 |
| D27·Q3 범위 S(topicDeck 만) | H1(정함 2) |
| Q3 범위 M(`citeLabel` 다섯 곳 통일) | 안 함 — Q3 기본 S. 보고서 칩·상세 인용 배너의 '성 연도'는 그대로(완료노트 이월에 적는다) |
| 06b 이월 §7-14 성만 보이는 칩 | H1(주제 카드 칩만) |
| D24 단계 ③ 이름 '참고문헌 선택하기'(workPhase :17·22·122·166, ReadingStep :6·25, WorkStepper :3, OnboardingModal :12, TopicsStep :8·58, ProposalStep :30·35·147, OutlineEditor :10, FunnelCounter :3, useReadingSaves :53, workPhase.test) | R1 |
| D24·Q2 단계 ④ 이름 '보고서' | A3(상수)·R1·X5(파일 이름·문서 머리) |
| D24 논문을 누르면 오른쪽 딥리드(button aria-expanded aria-controls·행 강조·[논문 상세 ↗] detailHref·goDetail 유지) | R5 |
| D24 공용 패널 부품(탭 [인용 근거 \| 딥리드], 머리 = 행 meta + [논문 상세 ↗] + 닫기) | R4 |
| D24 단계 ③ 딥리드 탭만·[담음] 토글·들어온 경로 첫 대목(접어 둠)·ReadingStep 이 쥐어 useReadingSaves 사슬 | R5 |
| D24 단계 ④ 두 탭·[담음] 없음·ProposalStep 이 쥔다 | S4 |
| D24 예시 연구는 [담음] 끔·대화는 염 | R5 |
| D24 배치(2단 sticky 22rem, 1200px 미만 오버레이 서랍 `.skx-chat-side` 재사용, 768px 이하 전체 폭) | R4 |
| D24 1440px·LNB 펼침이면 패널 열 때 LNB 접기 | R5(emit·리스너)·R6(조건부)·06d(기본 순서) |
| D24 초점 가두기·Esc·닫으면 누른 자리로·스트리밍 답 aria-live | R4·R3(aria-live)·R5·S4(초점 복귀) |
| D24 BookChat — cntsId 감시로 대화 바꾸기·선택 prop store | R2(정함 20) |
| D24 BookChat — AbortController 로 닫기·논문 바꾸기에서 끊기 | R2(정함 21) |
| D24 BookChat — 스트림 로직 composable + 순수 SSE 파서 vitest | R2 |
| D24 BookChat — docKind(기본 book) 책/논문 문구 :6·:54·:55·:63 | R3 |
| D24 논문 화면 두 호출처 `doc-kind="paper"`(예외) | R3 |
| D24 출처 칩 `<span @click>` → `<button>` + open-pdf 로 연구 화면 openPdf | R3(정함 22)·R5(ReadingStep 이 이미 올린다)·S4([id].vue:74) |
| D24 BookChat 좁은 화면 | R4(서랍·전체 폭) |
| D24 기존 네 화면 회귀 확인 | R3(확인 항목)·Z6(운영 확인 Step 8) |
| D24 서버는 대화를 저장하지 않는다 | 안 함 — 대화 저장은 §12-9 고도화 |
| D24 인용 근거 A안 — 칩 → 오른쪽 인용 근거 탭(논문 카드 + 대목 하이라이트 + [원문 보기] + [이 논문과 대화하기]) | S4 |
| D24 데이터 — input.papers[i].excerpt, 새 조회 GET …/sections/{key}/sources(쓰는 중이면 drafts 의 gen_id, 대목 없으면 초록만) | S1(정함 23) |
| D24 [원문 보기]는 [id].vue:74 의 ProposalStep 에 @open-pdf | S4 |
| D24 하이라이트 — 본문 쪽 누른 칩의 문장, 대목 쪽 글자 n-gram 최대 겹침 문장 | S3·S4 |
| D24 리랭커 점수·원문 뷰어 안 하이라이트 | 안 함 — §12-9 대회 뒤 |
| D24 딥리서치 보고서 CitationChip 팝오버 그대로 | 안 함 — `CitationChip.vue` 를 고치지 않는다 |
| D26 N 의 kind 별 total(fastapi) | H2(정함 26) |
| D26 '모두 보기 (N)' 그리기·history 가게로 나르기 | 해당 없음 — 06d |
| §12-11 키워드 후보 원천 | K1·K2(정함 14) |
| §12-11 키워드 최소 선택 수·직접 더하기 | K6·K7·K8(정함 15) |
| §12-11 고른 카드 다시 만들지 않음 | K6(정함 16) |
| §12-11 세 번 다 놓친 카드 | K9(정함 17) |
| §12-11 연구 배경 저장 | X1·X3(정함 7) |
| §12-11 문단 버튼 줄 접기 | 안 함 — 정함 12 |
| §12-11 '검토할 곳'·'근거 없음' 배지·부록 수 | X4·X5(정함 11 — 보이는 배지는 안 함) |
| §12-11 딥리드 프롬프트 논문 변형 | S2(정함 18) |
| §12-11 연구 맥락 딥리드 첫 화면 | 안 함 — 정함 19 |
| §12-11 탐색 중 PlanCard·옆 칸 폭, '소장자료검색' 다른 문구 | 해당 없음 — 06d |
| 06b 이월 §7-3 개념 칩을 고쳐도 소속을 다시 세지 않음 | 해당 없음 — 06b 규칙 그대로(PATCH 가 소속을 비우고 목차 때 다시 센다) |
| 06b 이월 §7-6 `Section.model` 늘 null | 해당 없음 — D21 로 부록에 모델을 싣지 않는다 |
| §12-7 06e pytest 목록(목차 자동 승인·절 키별 마지막 생성·CLAIM '확인했다'·키워드 후보 정제·제목 일치·카드 한 번만·다시 만들기·sources·질문 변경 stale·total) | A1·A2·X2·K2·K3·K9·K5·K6·S1·X1·H2 |
| §12-7 06e vitest 목록(남은 절 고르기·연구 공백 409·proposalDocument·칩 표기·키워드 하이라이트·SSE 파서·대화 중단·논문별 대화) | A3·A4·X5·H1·K7·K9(06c 고정 예제)·R2 |
| §12-7 운영 확인([보고서 만들기] 한 번에서 Word 까지 소요·대기 순번) | Z6 |
| §12-6 배포(워커·fastapi·nuxt, 10/17~18, 스키마 변경 없음) | Z4(머지 문)·Z5 |

## §12-11 항목 중 이 줄에 걸린 것 — 정함(권고)

완료노트 §6 과 spec §12-11(Task Z3)에 '정함 → 06e 계획 정함 n' 으로 남긴다.

| §12-11 항목 | 정함 | Task |
|---|---|---|
| 키워드 후보 원천 | 정함(권고) — LLM 후보 + 채택 논문 키워드 문서 빈도를 합친다. K1 채움률 ≥50% 면 `PAPER_KEYWORD_MIN_N = 1`, 미만이면 2(보조) — 판정은 Task Z1 | K1·K2·Z1 |
| 키워드 최소 선택 수 | 정함(권고) — 2. 직접 더하기는 남긴다(이 계획의 판단) | K6·K7·K8 |
| 고른 카드도 키워드를 바꾸면 다시 만들지 | 정함(권고) — 다시 만들지 않는다 | K6 |
| 키워드를 세 번 다 놓친 카드 | 정함(권고) — 무른 검사로 마지막 통과 출력을 보관해 '제목에 ○○ 없음' 경고를 단 채 보인다 | K9·K7·K8 |
| 연구 배경 저장 | 정함(권고) — `outline.background` 자유 글(대안 `sections.background` 는 안 함). Word·PDF 2절에도 싣는다(`proposalDocument.ts:120-121` — 정함 7) | X1·X3·X5 |
| 문단 버튼 줄을 기본으로 접을지 | 정함(이 계획의 판단 — 권고 없음) — 접지 않는다 | — |
| '검토할 곳' 요약·'근거 없음' 배지·부록 수 | 정함(권고 + 판단) — 요약 넣음, 보이는 배지 안 넣음(sr-only 만), 부록 수 넣음 | X4·X5 |
| 딥리드 프롬프트의 논문 변형 | 정함(권고) — 채택(`book_chat.paper.yaml` + `chat_prompt`, `BookOut.doc_type`) | S2 |
| 연구 맥락을 반영한 딥리드 첫 화면 | 정함 — 하지 않는다(선택 항목) | — |
| 탐색 중 읽기 전용 PlanCard·옆 칸 폭, '소장자료검색' 문구 | 06d 몫 — 06e 무관 | — |

## 하지 않는 것

**대회 뒤(spec §12-9 — 사용자가 정한 것과 spec 이 미룬 것):** 딥리드 대화 서버 저장(정함 20 — 단계 화면의 세션만), 리랭커 뒷받침 점수(인용 근거 하이라이트가 대신한다 — D24), 원문 뷰어 안 하이라이트, 외부 확인 링크·[주제로 넓히기], 원래 06c 깊이 항목(특징 추출·공백 격자·4번째 격자 카드·[연관 더 찾기]), [더 구체적으로](refine — [이 키워드로 다시 만들기]가 대신한다), 나머지 4절 생성(연구 배경은 사용자가 쓰는 칸 — D20), 연구 맥락을 반영한 딥리드 첫 화면(§12-11 선택 — 정함 19).

**06e 에서 하지 않는 것(이 계획의 결정):** 근거 칩 다섯 곳 통일(Q3 M — `citeLabel`·보고서 `CitationChip`·상세 인용 배너의 '성 연도'는 그대로, 정함 2), 절 여럿을 한 엔드포인트로 묶기(최악 300초 — spec §12-4), 연쇄를 다른 단계 화면에서도 돌리기(정함 6), 흐르는 글(쓰는 중인 절)의 인용 칩으로 패널 열기(정함 24), 문단 버튼 줄 접기(정함 12), '근거 없음' 보이는 배지(정함 11 — 화면낭독 글만), 결과·논의·가설 수치 생성(D2), 스키마 변경(함정 14), 회수기(`workers/research_tasks.py`)·`workers/research_work_tasks.py` 수정, 딥리서치 보고서 `CitationChip` 팝오버 변경, 06d 의 `research.css` 토큰·부품 import(정함 28 — 값만 같게).

**06d 몫:** 진행 화면(고정 진행 막대·따라가기·탐색 중 절 자리·근거 장부 '검토 중'), 사이드바 단계 표시·'모두 보기 (N)' 그리기와 기록 프론트 타입·가게, `/research` 홈·예시 연구 화면, 빠른검색 [딥리서치로 더 깊게]·[담기], '소장자료검색' 문구, `[id].vue` 의 `:57-75`·`workPanelOpen` 밖(LNB 연결은 늦게 머지하는 줄 — 06e 가 늦을 때만 Task R6).

**06c 몫:** 시작 질문 넓히기·검색어 합성·`terms.py`·스위치와 두 갈래 판정·기본값 커밋(06e 는 `contains` 를 import 하고 기본값 커밋을 배포에 싣기만 한다).

---

## 작업

### Task 0: worktree·기준선 확인

**왜:** 06e 는 그때의 `dev` 에서 따는 줄이다. spec 개정(10-08 회의 D19~D27·§12, Q1·Q8·Q9 답)이 dev 에 있어야 06c·06d·06e 가 같은 정본을 읽는다 — 그 확인이 이 계획의 선행 조건이다. worktree 는 본 작업 폴더에서 checkout 하지 않고 `git worktree add` 로 만든다(다른 세션이 깨진다). 시작 전에 테스트 수를 재 두어야 각 Task 가 더한 수와 깨뜨린 것을 가를 수 있다. 계획의 줄 번호가 da80f23 기준이므로 dev 의 `app`·`frontend` 가 그 뒤 바뀌었는지도 본다.

**Files:** 없음 (작업 환경과 기준선만 — 이 계획서가 dev 에 없을 때만 Step 3 의 계획 커밋 1개)

**알아 둘 것:**
- 로컬 `dev` 는 `origin/dev` 보다 뒤처져 있을 수 있다. `dev` 를 checkout 한 worktree 가 없으면 `git fetch origin dev:dev` 로 빨리 감는다(checkout 이 아니다). `refusing to fetch into branch 'refs/heads/dev' checked out at …` 이 나오면 그 worktree(대개 남은 `.worktrees/dev-merge`)가 있는 것이다 — 그 worktree 가 지금 쓰이는지 사용자에게 묻고(다른 줄의 머지 중일 수 있다), 쓰이지 않으면 `git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge` 뒤 다시 한다.
- 2026-10-11 실측: 로컬 `dev` = `origin/dev` = `da80f23`, `.worktrees/round06c`·`round06d`·`round06e` 는 아직 없다. spec 개정 커밋 셋(`2860595`·`65e257b`·`c5d05b0`)은 브랜치 `docs/round06-meeting-1008-spec` 에만 있다. 그 브랜치를 dev 에 머지하는 것은 계획 확정 단계(사용자 승인)의 몫이다 — 이 Task 는 확인만 하고, 없으면 멈춘다.
- 06e 는 06c 보다 먼저 딸 수도 뒤에 딸 수도 있다(구현은 10/10~ 병렬). 06c 가 이미 dev 에 머지돼 있으면 기준선이 06c 테스트만큼 크고 Task K9 의 dev 받기는 새로 받을 것이 없을 수 있다. 06d 가 06c 운영 배포 뒤 06e 보다 먼저 dev 에 들어와 있으면 Task R6 을 하게 된다 — Step 1 의 출력으로 갈라 적어 둔다.
- `.worktrees/dev-merge` 는 06b 가 남긴 빈 폴더일 수 있다(06b 완료노트 §7-17, worktree 등록은 없음). `git worktree add` 는 빈 폴더에 그대로 만든다.

- [ ] **Step 1: 선행 조건 — spec 개정이 dev 에 있는가, dev 는 어디까지 왔나**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline -1 dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI merge-base --is-ancestor 2860595 dev && echo "2860595 dev 에 있음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI merge-base --is-ancestor 65e257b dev && echo "65e257b dev 에 있음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI show dev:docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md | grep -c "^### 12-4. 06e 연구 어시스턴트"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline --merges da80f23..dev | grep -c "feat/round06e-"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline --merges da80f23..dev | grep -cE "feat/round06c-"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI log --oneline --merges da80f23..dev | grep -cE "feat/round06d-"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI diff --name-only da80f23 dev -- app frontend | grep -E "services/research_work/|api/research_(work|topics|proposal)\.py|api/history\.py|repositories/history\.py|schemas/(history|book)\.py|services/chat/book_chat\.py|prompts/(research_concepts|research_topic_card|book_chat)|components/work/|components/BookChat\.vue|assets/css/work\.css|types/work\.ts|composables/use(ResearchWork|ReadingSaves)\.ts|utils/(work|proposal|topicDeck|readingList|outlineEdit)|pages/research/\[id\]\.vue|pages/papers/"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI ls-tree --name-only dev docs/superpowers/plans/ | grep -c "round06e"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c "worktrees/round06e "
git -C C:/Users/LANDSOFT/mygit/NL_library_AI branch --list feat/round06e-assistant-auto-report
```

Expected:
- `fetch` — 이미 같으면 출력 없음, 앞서 있으면 `da80f23..<커밋>  dev -> dev` 한 줄
- `log -1 dev` — spec 브랜치를 머지한 커밋(또는 그 뒤) 한 줄. 이 커밋을 '분기 dev' 로 적어 둔다(완료노트 머리에 쓴다)
- `2860595 dev 에 있음`·`65e257b dev 에 있음` 두 줄, `### 12-4. 06e 연구 어시스턴트` → `1`
- 06e 머지 → `0`
- 06c 머지 → `0`(06c 보다 먼저 땄다) 또는 `1`(06c 가 먼저 머지됐다), 06d 머지 → `0`(기본) 또는 `1`(06d 가 먼저 머지됐다 — Task R6 을 하게 된다). 두 값을 적어 둔다
- 06e 파일 겹침 — 06d 머지가 `0` 이면 빈 출력(06c 는 06e 파일을 고치지 않는다 — 계획의 da80f23 줄 번호가 그대로 맞다). 06d 머지가 `1` 이면 06d 의 `frontend/pages/research/[id].vue`·`frontend/pages/papers/index.vue`·`frontend/assets/css/work.css`(근거 장부 블록)·`frontend/components/work/EvidenceLedger.vue` 가 나온다 — 그 넷은 처음 고치는 Task(R1·R3·A5 — `[id].vue` 는 R1 의 `:60` 버튼 글이 처음이다)도 줄 번호가 아니라 글자로 자리를 잡는다(`EvidenceLedger.vue` 는 06e 가 고치지 않는다). 그 밖의 파일이 나오면 적어 두고 그 파일을 고치는 Task 를 글자 앵커로 한다
- `round06e` 계획 → `1` 이면 이 계획서가 dev 에 있다(Step 3 건너뜀), `0` 이면 Step 3 에서 넣는다
- worktree → `0`, 브랜치 → 빈 출력

멈출 때: 두 커밋 중 하나라도 없거나 `12-4` 확인이 `1` 이 아니면 **여기서 멈추고 사용자에게 알린다** — spec 브랜치의 dev 머지(사용자 승인)가 먼저다. 06e 를 옛 spec 의 dev 에서 따지 않는다. 06e 머지가 이미 있으면(다른 세션이 이 줄을 이미 넣었다) 역시 멈추고 묻는다.

- [ ] **Step 2: worktree·브랜치를 dev 에서 만든다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add -b feat/round06e-assistant-auto-report .worktrees/round06e dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e status --short --branch
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e config --show-origin core.autocrlf
```

Expected:
- `Preparing worktree (new branch 'feat/round06e-assistant-auto-report')` 와 `HEAD is now at <Step 1 의 dev 커밋> …`
- `status` — `## feat/round06e-assistant-auto-report` 한 줄(변경 줄 없음)
- `log -1` — Step 1 의 dev 커밋과 같은 줄
- `file:C:/Program Files/Git/etc/gitconfig	true` — 작업 트리 파일이 CRLF 다. 기존 파일은 Edit 도구로 고친다

- [ ] **Step 3: 이 계획서를 브랜치에 넣는다 — dev 에 이미 있으면 건너뛴다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e cat-file -e HEAD:docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md && echo "계획서 있음" || echo "계획서 없음"
```

`계획서 있음` 이면 이 Step 은 끝이다. `계획서 없음` 이면 이 계획서를 연 파일 경로를 `PLAN_SRC` 에 넣고 브랜치의 첫 커밋으로 넣는다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && cp "$PLAN_SRC" docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md && git add docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md && git commit -m "[Docs] round06e 계획 — 연구 어시스턴트(Task 0 · A1~A5 · X1~X5 · R1~R6 · S1~S4 · K1~K9 · H1~H3 · Z1~Z7, 정함 1~31). [보고서 만들기] 한 번에 목차 자동 확정·절 자동 작성과 큰 진행 막대(사용자 Q1 답을 보고서 화면에도 — 10-11 확인), 내보내기 기본값(모든 문단·워터마크 없음·부록 상태별 개수), 단계 이름(제목 고르기·참고문헌 선택하기·보고서)·오른쪽 딥리드·인용 근거, 후보 키워드 칩과 제목 반영, 근거 칩 표기(주제 카드만), 기록 total, PDF(10/16 조건). 워커·fastapi·nuxt, 스키마 변경 없음, 06c 운영 배포 뒤 dev 머지, 10/17~18 배포"
```

Expected: 커밋 1개, `git status --short` 빈 출력.

- [ ] **Step 4: 백엔드 기준선**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 마지막 줄 `5 failed, 2327 passed, 1 skipped, 2 warnings, 1 error`(25~30초 — `npm ci` 와 함께 돌면 50초 남짓). 그 위 요약 줄은 정확히 다음 여섯이다.

```text
FAILED tests/test_build_manifest.py::test_build_manifest_matching
FAILED tests/test_build_manifest.py::test_build_manifest_csv_input
FAILED tests/test_loaders.py::test_marc_mods_loader_detect_and_load
FAILED tests/test_loaders.py::test_profile_loaders_and_autodetect
FAILED tests/test_loaders.py::test_legacy_parser_import_paths_still_work
ERROR tests/test_book_chat.py
```

Step 1 에서 06c(·06d) 머지가 `1` 이었으면 `passed` 는 2327 에 그 줄이 더한 백엔드 테스트 수만큼 크다 — 나온 수를 적어 두고(실패 5·오류 1 은 같은 여섯 줄) 각 Task 의 '앞 수' 와 Task Z2 의 기준으로 쓴다.

06e 가 고치거나 기대는 백엔드 테스트 스물한 파일 묶음:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_outline.py tests/test_research_proposal_api.py tests/test_research_work_section_input.py tests/test_research_work_enqueue.py tests/test_research_work_markers.py tests/test_research_work_paragraph_edit.py tests/test_prompts.py tests/test_research_work_concepts.py tests/test_research_work_api.py tests/test_research_work_views.py tests/test_research_work_seeds.py tests/test_research_work_topic_card.py tests/test_research_topics_api.py tests/test_research_work_dispatch.py tests/test_research_work_generate.py tests/test_research_work_executor.py tests/test_research_work_tasks.py tests/test_history_repository.py tests/test_history_api.py tests/test_embed_index_guard.py tests/test_research_work_models.py -q -p no:cacheprovider
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -c "import importlib.util as u; print([m for m in ('FlagEmbedding', 'pymilvus', 'pymarc', 'redis', 'celery', 'kombu', 'aiosqlite', 'torch') if u.find_spec(m) is None])"
```

Expected (2026-10-11 같은 코드에서 실측): 첫 줄 `744 passed, 2 warnings`(20초 남짓), 둘째 줄 `['FlagEmbedding', 'pymilvus', 'pymarc', 'redis', 'celery', 'kombu', 'aiosqlite', 'torch']`(로컬에 없는 모듈 — 대역 규칙이 이것을 전제한다. 하나라도 빠지면 그 모듈이 생긴 것이다 — Task S2 의 대역 fixture 는 설치된 환경에서 진짜를 읽으므로 그대로 돈다). 파일별 수(각각 `python -m pytest tests/<파일> -q -p no:cacheprovider`)와 고치는 Task:

| 파일 | passed | 고치는 Task | 파일 | passed | 고치는 Task |
|---|---|---|---|---|---|
| `test_research_work_outline.py` | 28 | A1·X1 | `test_research_work_seeds.py` | 22 | K4 |
| `test_research_proposal_api.py` | 95 | A1·A2·X1·S1 | `test_research_work_topic_card.py` | 49 | K4·K5·K6·K9 |
| `test_research_work_section_input.py` | 40 | X1(✎ 둘) | `test_research_topics_api.py` | 36 | K4·K5·K6 |
| `test_research_work_enqueue.py` | 25 | X1 | `test_research_work_dispatch.py` | 32 | K5 |
| `test_research_work_markers.py` | 52 | X2 | `test_research_work_generate.py` | 20 | K9 |
| `test_research_work_paragraph_edit.py` | 19 | X2 | `test_research_work_executor.py` | 12 | K2(✎)·K5(✎)·K9 |
| `test_prompts.py` | 9 | S2 | `test_history_repository.py` | 59 | H2 |
| `test_research_work_concepts.py` | 29 | K2 | `test_history_api.py` | 45 | H2 |
| `test_research_work_api.py` | 82 | R1(✎ `:510`)·K2·K3·K5 | `test_embed_index_guard.py` | 6 | (그대로 — S2 의 대역이 새지 않는지) |
| `test_research_work_views.py` | 17 | K3 | `test_research_work_models.py` | 40 | (그대로 — 모델은 주석만) |
| `test_research_work_tasks.py` | 27 | K2·K5(✎ `TestDispatch`) | 새 두 파일 | 없음 | `test_research_work_keywords.py`(K2)·`test_book_chat_prompt.py`(S2) |

- [ ] **Step 5: 프론트 기준선**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm ci
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/proposalView.test.ts tests/unit/workPhase.test.ts tests/unit/outlineEdit.test.ts tests/unit/proposalDocument.test.ts tests/unit/readingList.test.ts tests/unit/topicDeck.test.ts tests/unit/workEvents.test.ts tests/unit/citations.test.ts tests/unit/reportDocx.test.ts tests/unit/reportDocument.test.ts tests/unit/useResearchWork.test.ts tests/unit/useReadingSaves.test.ts tests/unit/pdfViewer.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e status --short
```

Expected (2026-10-08·10-11 같은 코드에서 실측):
- `npm ci` — 35초 남짓, 786 패키지. 끝의 `npm audit` 안내(`37 vulnerabilities (3 low, 5 moderate, 21 high, 8 critical)`)는 실패가 아니다
- typecheck 오류 — `0`
- `Duplicated imports` — `2`(`queueLine` 경고 두 줄 — Step 1 에서 06d 머지가 `1` 이었으면 06d 가 지워 `0`). 이 값을 적어 둔다 — 06e 는 늘리지 않는다(Task Z2). `[Vue] Resolve plugin path failed …` 경고는 기준선에도 나온다
- vitest 전체 — `Test Files  40 passed (40)` / `Tests  732 passed (732)`
- 06e 묶음 열세 파일 — `Test Files  13 passed (13)` / `Tests  221 passed (221)`. 파일별 수와 고치는 Task:

  | 파일 | Tests | 고치는 Task | 파일 | Tests | 고치는 Task |
  |---|---|---|---|---|---|
  | `proposalView.test.ts` | 20 | A3·X3·X4·X5 | `citations.test.ts` | 18 | (그대로 — Q3 S, `citeLabel` 그대로) |
  | `workPhase.test.ts` | 20 | A3·R1 | `reportDocx.test.ts` | 4 | (그대로 — 보고서 워터마크 그리기는 남는다) |
  | `outlineEdit.test.ts` | 16 | X3 | `reportDocument.test.ts` | 27 | (그대로 — 딥리서치 보고서 내보내기 불변) |
  | `proposalDocument.test.ts` | 18 | X5 | `useResearchWork.test.ts` | 7 | (그대로 — S3·K7 은 `useWorkApi` 에 함수만 더한다) |
  | `readingList.test.ts` | 19 | R1·R5 | `useReadingSaves.test.ts` | 4 | (그대로 — R1 은 문구만) |
  | `topicDeck.test.ts` | 26 | R1·K7·H1·K9 | `pdfViewer.test.ts` | 15 | (그대로 — R3·S3 가 `citedPdfTarget` 을 import) |
  | `workEvents.test.ts` | 27 | K7 | 새 다섯 파일 | 없음 | A4·R2·R3(R4)·S3 이 만든다 |

- build — 30초 남짓, `└  ✨ Build complete!`(로그의 `error` 낱말은 `error-404`·`error-500` 청크 이름뿐이다)
- `git status --short` — 빈 출력(`node_modules`·`.nuxt`·`.output` 은 `.gitignore` 에 있다)

Step 1 에서 06c(·06d) 머지가 `1` 이었으면 vitest 전체가 그 줄의 화면 테스트만큼 크다 — 나온 수를 적어 두고 각 Task 의 '앞 수' 로 쓴다(06e 묶음 열세 파일은 06c·06d 가 고치지 않아 `221` 그대로다).

---

<!-- 조립: 파트 A(Task A1~A5)·파트 X(Task X1~X5)·파트 R(Task R1~R6)·파트 S(Task S1~S4)·파트 K(Task K1~K9)·파트 H(Task H1~H3) 가 이 자리에 들어간다 — 실행은 '파트 순서와 Task ID' 의 전역 실행 순서대로(R6 은 S4 뒤, K9 는 06c dev 머지 뒤, H3 은 맨 끝) -->

---

---

## 파트 A — 보고서 자동 산출

spec §12-4 '보고서 자동 산출(D20)' 가운데 화면 흐름을 덮는다 — 누르는 것([목차 만들기]→[보고서 만들기], [목차 다시 만들기]→[보고서 다시 만들기], 담음 5편 조건 그대로), 목차 자동 확정(서버 `outline.apply` — 연구 질문 = 첫 후보 → 고른 카드의 질문, 방법 빈칸, `state` approved·`approved_at`·`auto` true), 절 연쇄(화면 — 도는 조건 approved·auto·예시 아님, PUT `/outline` 은 auto 를 지킨다, [보고서 다시 만들기]는 새 apply 라 auto 가 다시 붙는다, 대상 = 절도 그 키의 section 생성 기록도 없는 키를 문서 순서 `prior.g1`~`g4` → `gap`, ProposalView 의 절 키별 마지막 section 생성 `section_gens`, 판정은 `utils/proposalView.ts` 순수 함수, failed·canceled 키는 다시 넣지 않음, 하나씩 — 앞 POST 응답 뒤 다음, 409 `no_section_papers` 면 그 절만 '근거가 없어 쓰지 않았습니다' 후 다음 키, 그 밖의 4xx·5xx·네트워크 오류면 멈추고 [이어서 쓰기], 탭을 닫았다 와도 이어 넣음), 보고서 화면(머리 목차·절 자리 상태 재사용 `ProposalSection.vue:24-72`·문구 두 곳 `ProposalStep.vue:56`·`ProposalSection.vue:195-197`), 사용자 Q1 답의 큰 진행 막대(뼈대 정함 28 — 10-11 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아", 그래서 계획 머리의 확인 질문은 두지 않는다). 선택 기능([목차 고치기]·절 다시 쓰기·문단 [수락]·[다시]·[고치기]·직접 쓰기)은 지우지 않는다 — [목차 고치기]는 승인한 목차에서 접어 둔 편집기를 여는 단추가 된다. 연구 배경·방법 칸(Task X3)·검토할 곳(Task X4)·내보내기(Task X5)·단계 이름(Task R1)은 다른 파트다.

Task A1·Task A2 는 백엔드(fastapi 와 생성 워커 `celery-research-plan` — `outline.apply` 는 워커가 부른다), Task A3~Task A5 는 nuxt 다. 백엔드 줄기(Task A1→Task A2)와 프론트 줄기(Task A3→Task A4→Task A5)는 서로 코드에 기대지 않는다(뼈대 1장 계약 모양만) — 순서대로 하되 한쪽이 막히면 다른 쪽을 먼저 해도 된다. 파트 A 는 06c 의 코드(`terms.py` 등)를 쓰지 않는다 — 선행 조건 Step 이 없다.

검증: 이 파트의 old/new 블록을 dev `da80f23` 과 같은 트리의 사본에 Task 순서대로 글자 그대로 적용해 잰 값이다(2026-10-11) — 백엔드 전체 `5 failed, 2332 passed, 1 skipped, 2 warnings, 1 error`(기준선 2327 + 5), vitest `41 files / 767 passed`(기준선 40 / 732 + 35), `nuxi typecheck` 오류 0, `npm run build` 완료(`Duplicated imports` 2줄 — 기준선과 같다). 앞 파트가 없으므로 Task A1 의 '앞'은 Task 0 기준선이다.

---

### Task A1: 목차 자동 확정 — outline.apply 가 승인 목차(auto)로 저장한다

spec §12-4 '목차 자동 확정(서버)'·'PUT `/outline` 은 `auto` 를 그대로 둔다'·'[보고서 다시 만들기]는 새 apply 라 `auto` 가 다시 붙는다', D20, 뼈대 정함 3. [보고서 만들기] 한 번이 목차 생성 1건을 넣고(06b `POST …/outline` 그대로), 그 반영이 목차를 곧바로 승인한다 — 화면의 절 연쇄(Task A4)는 `auto` 가 참인 승인 목차에서만 돈다.

**알아 둘 것:**
- **질문을 고르는 규칙(`auto_question`):** 첫 후보(`output.questions[0]`) → 없으면 고른 카드의 질문(`input.topic.question`) → 둘 다 비면 `None`. 공백을 정리하고 2자 미만은 없는 것으로 본다 — `PUT …/outline` 의 승인 하한(`APPROVE_NEEDS_QUESTION`, `research_proposal.py:258-259`)과 같아야 자동 승인한 목차를 [목차 고치기]로 다시 승인할 때 422 가 나지 않는다. 빈 결과(fallback)는 `_empty`(`outline.py:156-159`)가 이미 카드 질문 하나를 후보로 채우므로 모델이 실패해도 대개 질문이 있다.
- **질문이 없을 때(정함 3):** 06b 처럼 `state` draft·`question` null·`approved_at` null 로 두고 `auto` 는 false 다 — 사용자가 [목차 고치기]에서 질문을 써서 승인한다(그 목차는 auto 가 false 라 연쇄가 돌지 않는다 — 06b 와 같은 손 흐름).
- **`approved_at`:** `PUT …/outline` 과 같은 모양(`datetime.now(timezone.utc).isoformat()`, `research_proposal.py:265`)을 새 `_now()` 가 만든다 — 테스트가 `monkeypatch.setattr("services.research_work.outline._now", …)` 로 바꿔 끼운다(`apply` 가 모듈 전역 이름으로 부른다).
- **반환:** generation 이벤트의 `result` 가 `{"fallback": bool, "auto": bool}` 이 된다(뼈대 1-4). 이 값을 기대하는 다른 테스트는 없다(`grep -rn '"fallback"' app/tests` 는 outline 테스트뿐 — 확인함).
- **PUT `/outline` 은 고치지 않는다:** `put_outline` 은 저장된 목차를 `dict(proposal.outline)` 로 복사한 뒤 `groups`·`question`·`method`·`state`·`approved_at` 만 `update` 하므로(`research_proposal.py:256-266`) `auto` 키는 그대로 남는다. 새 테스트 `test_saving_keeps_the_auto_mark` 는 이 동작을 **고정**하는 테스트라 구현 전에도 통과한다(실패 확인 단계의 기대 출력에 적었다). 승인을 풀면(`approve: false`) `state` 가 draft 가 되어 연쇄는 `state` 로 멈춘다 — `auto` 를 지우지 않는다.
- **문구:** `NEED_READING`(`research_proposal.py:53`)을 '…이상이어야 보고서를 만듭니다'로. 조사가 붙는 문장이라 '보고서'를 글자 그대로 쓴다(뼈대 정함 1 — 백엔드에는 `FINAL_STEP_NAME` 이 없다).
- `models/research_work.py` 는 머리 주석만 바뀐다 — `test_research_work_models.py`(0007 과 ORM 비교)는 그대로 통과한다. 스키마 변경 없음(함정 14 — JSONB 안 모양만).
- 세 파일 모두 CRLF 다 — Edit 도구로 고친다.

**Files:**
- Modify: `app/services/research_work/outline.py` (머리 docstring :10-11, import 줄 :13-15, `_empty` :156-159 아래에 `_now`·`auto_question`, `apply` :162-189)
- Modify: `app/api/research_proposal.py` (:53 `NEED_READING`)
- Modify: `app/models/research_work.py` (머리 주석 Outline :32-36)
- Test: `app/tests/test_research_work_outline.py` (import :24-26, `TestRegistry`·반영 머리 :201-206, `_setup` :214-221, `TestApply` :248-끝)
- Test: `app/tests/test_research_proposal_api.py` (`TestCreateOutline.test_five_picked_papers_are_needed` :505-509, `TestPutOutline.test_saving_without_approval_is_a_draft` :557-567 뒤)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_work_outline.py` — import 에 `auto_question` 을 더한다. old:

```python
from services.research_work.outline import (
    EXECUTOR, FALLBACK_GROUP_NAME, PROMPT, clean_questions, outline_input,
)
```

new:

```python
from services.research_work.outline import (
    EXECUTOR, FALLBACK_GROUP_NAME, PROMPT, auto_question, clean_questions, outline_input,
)
```

같은 파일 — `TestRegistry` 와 반영 절 머리 사이에 `TestAutoQuestion` 을 넣는다. old:

```python
class TestRegistry:
    def test_outline_is_registered(self):
        assert EXECUTORS["outline"] is EXECUTOR


# ── 반영 ────────────────────────────────────────────────────────────
```

new:

```python
class TestRegistry:
    def test_outline_is_registered(self):
        assert EXECUTORS["outline"] is EXECUTOR


class TestAutoQuestion:
    def test_first_candidate_then_the_card_question_then_none(self):
        card = {"topic": {**TOPIC, "question": "  카드의   질문인가? "}}
        assert auto_question({"questions": ["첫 후보인가?", "둘째 후보인가?"]}, card) == "첫 후보인가?"
        assert auto_question({"questions": []}, card) == "카드의 질문인가?"
        assert auto_question({}, card) == "카드의 질문인가?"
        assert auto_question({"questions": ["   "]}, card) == "카드의 질문인가?"
        # 공백만이거나 2자 미만이면 없는 것 — 승인 PUT 의 하한(APPROVE_NEEDS_QUESTION)과 같다
        assert auto_question({"questions": []}, {"topic": {**TOPIC, "question": "   "}}) is None
        assert auto_question({"questions": []}, {"topic": {**TOPIC, "question": "가"}}) is None
        assert auto_question({}, {}) is None


# ── 반영 ────────────────────────────────────────────────────────────
```

같은 파일 — `_setup` 이 생성 입력을 받게 한다(질문이 하나도 없는 입력을 넣으려고). old:

```python
def _setup(engine, *, outline=None, version=1):
    jid = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, jid, phase="proposal")
    for cnts_id in ("C1", "C2", "C3"):
        add_reading(engine, jid, cnts_id, state="in")
    add_proposal(engine, jid, version=version, outline=outline)
    gid = add_generation(engine, jid, kind="outline", status="running", target=OUTLINE_TARGET, input=INPUT)
    return jid, gid
```

new:

```python
def _setup(engine, *, outline=None, version=1, input=INPUT):
    jid = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, jid, phase="proposal")
    for cnts_id in ("C1", "C2", "C3"):
        add_reading(engine, jid, cnts_id, state="in")
    add_proposal(engine, jid, version=version, outline=outline)
    gid = add_generation(engine, jid, kind="outline", status="running", target=OUTLINE_TARGET, input=input)
    return jid, gid
```

같은 파일 — `TestApply` 를 06e 반영으로 바꾼다(파일 끝까지). old:

```python
class TestApply:
    def test_writes_a_draft_outline_and_bumps_the_version(self, engine):
        jid, gid = _setup(engine)
        output = EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT)

        payload, pending = _apply(engine, gid, output)

        assert payload == {"fallback": False}
        assert pending == []                       # 반영은 커밋하지 않는다 — 위 커밋은 테스트가 했다
        row = _proposal(engine, jid)
        assert row["version"] == 2
        assert row["outline"] == {
            "topic": TOPIC, "basis": "concept", "concepts": ["노인의 우울", "사회적 지지"],
            "groups": [{"key": "prior.g1", "name": "노년기 우울의 요인", "hint": "노인의 우울",
                        "papers": ["C1", "C2"]},
                       {"key": "prior.g2", "name": "가족·사회 지지망", "hint": "사회적 지지", "papers": ["C3"]}],
            "questions": output["questions"], "question": None, "method": "", "state": "draft",
            "gen_id": gid, "approved_at": None,
        }
        with engine.connect() as conn:
            progress = conn.execute(sa.select(ResearchWork.__table__.c.progress)
                                    .where(ResearchWork.__table__.c.id == jid)).scalar_one()
        assert progress["reading"] == 3 and progress["sections_total"] == 6

    def test_fallback_outline_is_flagged(self, engine):
        jid, gid = _setup(engine)

        payload, _ = _apply(engine, gid, EXECUTOR.empty(INPUT))

        assert payload == {"fallback": True}
        outline = _proposal(engine, jid)["outline"]
        assert [g["name"] for g in outline["groups"]] == ["노인의 우울", "사회적 지지"]
        assert outline["questions"] == [TOPIC["question"]]

    def test_a_new_outline_replaces_an_approved_one(self, engine):
        approved = {"state": "approved", "groups": [], "question": "옛 질문?", "approved_at": "2026-10-10"}
        jid, gid = _setup(engine, outline=approved, version=5)

        _apply(engine, gid, EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT))

        row = _proposal(engine, jid)
        assert row["version"] == 6
        assert (row["outline"]["state"], row["outline"]["question"]) == ("draft", None)
```

new:

```python
NOW = "2026-10-17T01:02:03+00:00"
FIRST = "사회적 지지의 유형에 따라 노인 우울은 어떻게 다른가?"      # GOOD 의 첫 후보


class TestApply:
    def test_writes_an_approved_auto_outline_with_the_first_question(self, engine, monkeypatch):
        # 06e(D20) — [보고서 만들기] 한 번으로 목차를 자동 확정한다: 연구 질문 = 첫 후보, 방법 빈칸, 승인·auto 표시
        monkeypatch.setattr("services.research_work.outline._now", lambda: NOW)
        jid, gid = _setup(engine)
        output = EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT)

        payload, pending = _apply(engine, gid, output)

        assert payload == {"fallback": False, "auto": True}
        assert pending == []                       # 반영은 커밋하지 않는다 — 위 커밋은 테스트가 했다
        row = _proposal(engine, jid)
        assert row["version"] == 2
        assert row["outline"] == {
            "topic": TOPIC, "basis": "concept", "concepts": ["노인의 우울", "사회적 지지"],
            "groups": [{"key": "prior.g1", "name": "노년기 우울의 요인", "hint": "노인의 우울",
                        "papers": ["C1", "C2"]},
                       {"key": "prior.g2", "name": "가족·사회 지지망", "hint": "사회적 지지", "papers": ["C3"]}],
            "questions": output["questions"], "question": FIRST, "method": "", "state": "approved",
            "gen_id": gid, "approved_at": NOW, "auto": True,
        }
        with engine.connect() as conn:
            progress = conn.execute(sa.select(ResearchWork.__table__.c.progress)
                                    .where(ResearchWork.__table__.c.id == jid)).scalar_one()
        assert progress["reading"] == 3 and progress["sections_total"] == 6

    def test_fallback_outline_is_flagged(self, engine, monkeypatch):
        # 모델이 끝내 실패해도 빈 결과가 카드 질문 하나를 후보로 채운다 — 그 질문으로 자동 승인한다
        monkeypatch.setattr("services.research_work.outline._now", lambda: NOW)
        jid, gid = _setup(engine)

        payload, _ = _apply(engine, gid, EXECUTOR.empty(INPUT))

        assert payload == {"fallback": True, "auto": True}
        outline = _proposal(engine, jid)["outline"]
        assert [g["name"] for g in outline["groups"]] == ["노인의 우울", "사회적 지지"]
        assert outline["questions"] == [TOPIC["question"]]
        assert (outline["question"], outline["state"], outline["approved_at"], outline["auto"]) == (
            TOPIC["question"], "approved", NOW, True)

    def test_a_new_outline_replaces_an_approved_one(self, engine, monkeypatch):
        # [보고서 다시 만들기]는 새 반영이다 — 옛 승인·질문·방법을 버리고 새 첫 후보로 다시 자동 승인한다(auto 가 다시 붙는다)
        monkeypatch.setattr("services.research_work.outline._now", lambda: NOW)
        approved = {"state": "approved", "groups": [], "question": "옛 질문?", "method": "옛 방법",
                    "approved_at": "2026-10-10"}
        jid, gid = _setup(engine, outline=approved, version=5)

        _apply(engine, gid, EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT))

        row = _proposal(engine, jid)
        assert row["version"] == 6
        out = row["outline"]
        assert (out["state"], out["question"], out["method"], out["approved_at"], out["auto"]) == (
            "approved", FIRST, "", NOW, True)

    def test_no_question_at_all_stays_a_draft_without_auto(self, engine):
        # 후보도 카드 질문도 없으면 06b 처럼 초안으로 둔다 — 빈 질문으로 승인하면 [목차 고치기]의 PUT 이 422 다(정함 3)
        bare = {**INPUT, "topic": {**TOPIC, "question": ""}}
        jid, gid = _setup(engine, input=bare)

        payload, _ = _apply(engine, gid, EXECUTOR.empty(bare))

        assert payload == {"fallback": True, "auto": False}
        out = _proposal(engine, jid)["outline"]
        assert (out["questions"], out["question"], out["state"], out["approved_at"], out["auto"]) == (
            [], None, "draft", None, False)
```

`app/tests/test_research_proposal_api.py` — 문구가 '보고서'로 바뀐다. old:

```python
        assert res.status_code == 409 and res.json()["detail"] == "담은 논문이 5편 이상이어야 목차를 만듭니다"
```

new:

```python
        assert res.status_code == 409 and res.json()["detail"] == "담은 논문이 5편 이상이어야 보고서를 만듭니다"
```

같은 파일 — `TestPutOutline` 에 auto 를 지키는 테스트를 더한다. old:

```python
        out = res.json()["outline"]
        assert (out["state"], out["question"], out["approved_at"]) == ("draft", None, None)
        assert res.headers["etag"] == "4"
```

new:

```python
        out = res.json()["outline"]
        assert (out["state"], out["question"], out["approved_at"]) == ("draft", None, None)
        assert res.headers["etag"] == "4"

    def test_saving_keeps_the_auto_mark(self, api):
        # 06e — 자동 확정한 목차(auto)를 [목차 고치기]·방법 저장으로 PUT 해도 auto 는 그대로다(절 연쇄가 읽는다).
        # 승인을 풀면(approve false) 연쇄는 state 로 멈춘다 — auto 를 지우지 않는다
        jid = _work_job(api.engine)
        outline = {**OUTLINE, "topic": {**OUTLINE["topic"], "id": _topic_id(api.engine, jid)},
                   "question": OUTLINE["questions"][0], "state": "approved",
                   "approved_at": "2026-10-17T01:02:03+00:00", "auto": True}
        add_proposal(api.engine, jid, version=2, outline=outline)

        first = api.client.put(f"/api/research/{jid}/outline", json=_put_body(approve=True),
                               headers={"If-Match": "2"})
        second = api.client.put(f"/api/research/{jid}/outline", json=_put_body(approve=False),
                                headers={"If-Match": "3"})

        assert first.status_code == 200 and second.status_code == 200
        assert (first.json()["outline"]["state"], first.json()["outline"]["auto"]) == ("approved", True)
        assert (second.json()["outline"]["state"], second.json()["outline"]["auto"]) == ("draft", True)
        assert _proposal(api.engine, jid)["outline"]["auto"] is True
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_outline.py -q -p no:cacheprovider`

Expected: `Interrupted: 1 error during collection`(끝 줄 `2 warnings, 1 error`) — `ImportError: cannot import name 'auto_question' from 'services.research_work.outline'`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_proposal_api.py -q -p no:cacheprovider`

Expected: `1 failed, 95 passed` — 실패는 `test_five_picked_papers_are_needed`(문구). 새 `test_saving_keeps_the_auto_mark` 는 지금도 통과한다 — PUT 이 저장된 목차를 복사해 고치므로 `auto` 가 남는다(이 Task 가 고정하는 동작)

- [ ] **Step 3: 반영을 고친다**

`app/services/research_work/outline.py` — 머리 docstring 끝에 자동 확정을 적는다. old:

```python
반영(apply)은 research_proposals.outline 을 Outline 모양으로 바꾸고 version 을 올린다 — 화면이 들고 있던
옛 version 의 PUT 은 409 가 된다. 행은 POST .../outline 이 미리 만든다. 커밋은 디스패처(finish)가 한다.
"""
import re

from sqlalchemy import update
```

new:

```python
반영(apply)은 research_proposals.outline 을 Outline 모양으로 바꾸고 version 을 올린다 — 화면이 들고 있던
옛 version 의 PUT 은 409 가 된다. 행은 POST .../outline 이 미리 만든다. 커밋은 디스패처(finish)가 한다.
06e 부터 반영이 목차를 자동 확정한다(D20 — [보고서 만들기] 한 번): 연구 질문 = 첫 후보, 없으면 고른 카드의 질문
(auto_question), 방법 빈칸, state approved·approved_at 지금·auto true — 화면의 절 연쇄가 auto 를 읽는다. 질문이 하나도
없으면 06b 처럼 초안(auto false)으로 둔다 — 빈 질문으로 승인하면 [목차 고치기]의 PUT 이 422 가 된다.
"""
import re
from datetime import datetime, timezone

from sqlalchemy import update
```

같은 파일 — `_empty` 아래에 승인 시각·질문 고르기를 더한다. old:

```python
def _empty(input: dict) -> dict:
    question = (input.get("topic") or {}).get("question") or ""
    return {"group_names": {g["key"]: _fallback_name(g.get("hint")) for g in input["groups"]},
            "questions": [question] if question else [], "fallback": True}
```

new:

```python
def _empty(input: dict) -> dict:
    question = (input.get("topic") or {}).get("question") or ""
    return {"group_names": {g["key"]: _fallback_name(g.get("hint")) for g in input["groups"]},
            "questions": [question] if question else [], "fallback": True}


def _now() -> str:
    """자동 승인 시각(UTC ISO) — PUT .../outline 의 approved_at 과 같은 모양. 테스트가 바꿔 끼운다."""
    return datetime.now(timezone.utc).isoformat()


def auto_question(output: dict, input: dict) -> str | None:
    """자동 확정의 연구 질문 — 첫 후보(output.questions[0]), 없으면 고른 카드의 질문(input.topic.question), 둘 다
    비면 None. 공백을 정리하고 2자 미만(공백만 포함)은 없는 것으로 본다 — PUT .../outline 의 승인 하한과 같아야
    자동 승인한 목차를 [목차 고치기]로 다시 승인할 수 있다. 빈 결과(fallback)는 _empty 가 이미 카드 질문을 후보로 채운다."""
    candidates = list(output.get("questions") or [])[:1] + [(input.get("topic") or {}).get("question")]
    for raw in candidates:
        text = " ".join(raw.split()) if isinstance(raw, str) else ""
        if len(text) >= 2:
            return text
    return None
```

같은 파일 — `apply` 가 자동 확정한다. old:

```python
async def apply(db, gen, output: dict) -> dict:
    """research_proposals.outline ← Outline(state draft) · version + 1 · 진행 요약. 커밋하지 않는다.
    concepts 는 목차를 만들 때의 핵심 개념 — 뒤에 개념을 고치면 조회가 목차에 '다시 맞춤 필요' 를 붙인다."""
    input = dict(gen.input or {})
    names = output.get("group_names") or {}
    outline = {
```

new:

```python
async def apply(db, gen, output: dict) -> dict:
    """research_proposals.outline ← Outline · version + 1 · 진행 요약. 커밋하지 않는다.
    연구 질문이 있으면 자동 승인한다(state approved·approved_at·auto true — 06e D20), 없으면 06b 처럼 초안(auto false).
    승인한 목차가 있어도 통째로 바꾼다([보고서 다시 만들기] — 새 반영이라 auto 가 다시 붙는다).
    concepts 는 목차를 만들 때의 핵심 개념 — 뒤에 개념을 고치면 조회가 목차에 '다시 맞춤 필요' 를 붙인다.
    반환은 generation 이벤트의 result({fallback, auto})."""
    input = dict(gen.input or {})
    names = output.get("group_names") or {}
    question = auto_question(output, input)
    auto = question is not None
    outline = {
```

같은 파일 — 같은 함수의 dict 끝과 반환. old:

```python
        "questions": list(output.get("questions") or []),
        "question": None,
        "method": "",
        "state": "draft",
        "gen_id": gen.id,
        "approved_at": None,
    }
```

new:

```python
        "questions": list(output.get("questions") or []),
        "question": question,
        "method": "",
        "state": "approved" if auto else "draft",
        "gen_id": gen.id,
        "approved_at": _now() if auto else None,
        "auto": auto,
    }
```

같은 파일 — 반환. old:

```python
    await refresh_progress(db, gen.work_id)
    return {"fallback": bool(output.get("fallback"))}
```

new:

```python
    await refresh_progress(db, gen.work_id)
    return {"fallback": bool(output.get("fallback")), "auto": auto}
```

`app/api/research_proposal.py` — 문구. old:

```python
NEED_READING = f"담은 논문이 {MIN_READING_FOR_OUTLINE}편 이상이어야 목차를 만듭니다"
```

new:

```python
NEED_READING = f"담은 논문이 {MIN_READING_FOR_OUTLINE}편 이상이어야 보고서를 만듭니다"
```

`app/models/research_work.py` — 머리 주석의 Outline 모양에 `auto` 를 적는다. old:

```python
               "questions": [str], "question": str|null, "method": str,
               "state": "draft"|"approved", "gen_id": int|null, "approved_at": iso|null}
```

new:

```python
               "questions": [str], "question": str|null, "method": str,
               "state": "draft"|"approved", "gen_id": int|null, "approved_at": iso|null,
               "auto": bool}                                         — 06e 반영이 자동 승인한 목차만 true
                                                                       (06b 목차엔 키 없음 — 화면 절 연쇄가 읽는다)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_outline.py tests/test_research_proposal_api.py -q -p no:cacheprovider`

Expected: `126 passed, 2 warnings` (outline 28 + 2 · 계획서 API 95 + 1)

같은 틀을 쓰는 기존 테스트(디스패처·워커·모델 — 반영 결과 모양이 바뀌어도 그대로인지):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_dispatch.py tests/test_research_work_tasks.py tests/test_research_work_models.py tests/test_research_work_executor.py -q -p no:cacheprovider`

Expected: 실패 0 — 수는 이 Task 전과 같다

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: `5 failed, (Task 앞 + 3) passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 기준선과 같은 세 파일(`test_build_manifest.py`·`test_loaders.py`·`test_book_chat.py` 수집)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/outline.py app/api/research_proposal.py app/models/research_work.py app/tests/test_research_work_outline.py app/tests/test_research_proposal_api.py && git status --short && git commit -m "[Feat] round06e — 목차 반영이 목차를 자동 확정한다(D20 보고서 자동 산출의 서버 쪽). 연구 질문은 첫 후보, 없으면 고른 카드의 질문(auto_question — 공백 정리, 2자 미만은 없음으로 승인 PUT 하한과 맞춘다), 방법은 빈칸, state approved·approved_at·auto true 로 저장하고 generation result 에 auto 를 싣는다 — 화면의 절 연쇄가 auto 가 참인 승인 목차에서만 돈다. 질문이 하나도 없으면 06b 처럼 초안(auto false)으로 두어 사용자가 질문을 써서 승인한다. [보고서 다시 만들기]는 새 반영이라 auto 가 다시 붙고, PUT /outline 은 저장된 목차를 복사해 고치므로 auto 를 지킨다(테스트로 고정). 담음 부족 409 문구를 '보고서를 만듭니다'로"
```

---

### Task A2: ProposalView 에 절 키별 마지막 section 생성 · 근거 없음 409 에 code

spec §12-4 절 연쇄 '대상 — 생성 기록은 ProposalView 에 새로 싣는 절 키별 마지막 section 생성 `{gen_id, status}` 로 본다'·'응답 처리 — 409 `NO_SECTION_PAPERS` 면 그 절만 건너뛰고 다음 키', 뼈대 정함 5. 화면의 절 연쇄(Task A3·Task A4)가 읽는 재료 두 가지를 서버가 싣는다.

**알아 둘 것:**
- **`section_gens` 는 `_proposal_response` 가 이미 읽은 생성 행에서 만든다** — `research_proposal.py:131` 이 그 연구의 생성을 모두(`order_by(G.id)`) 읽어 `proposal_view` 에 넘긴다. 새 조회는 없다. WorkView 는 끝난 생성을 최근 10건만 싣기 때문에(`research_work.py:132-142`) 화면 연쇄가 쓰지 않는다(spec).
- **모양:** `{절 키: {"gen_id": int, "status": str}}` — kind `section` 이고 target 이 있는 행 중 키별 id 가 가장 큰 것, 상태 무관(queued·running·done·failed·canceled 모두). 목차·문단 다시 쓰기(`paragraph` — target `<키>#<pid>`)·개념 생성은 뺀다.
- **409 detail 모양:** `{"code": "no_section_papers", "message": NO_SECTION_PAPERS}` — 06b `version_conflict`(`research_proposal.py:94-96`)와 같은 꼴. 화면의 [이 절 쓰기] 오류 문구는 그대로다 — `detailMessage`(`frontend/utils/researchErrors.ts:18-23`)가 객체 detail 의 `message` 를 읽는다(`workErrorMessage` → `researchErrorMessage` → `detailMessage`). 문자열 detail 을 기대하던 프론트 코드는 없다(`grep -rn "넣을 논문이 없습니다" frontend` 빈 출력 — 확인함).
- 두 파일 모두 CRLF — Edit 도구로 고친다. 스키마 변경 없음.

**Files:**
- Modify: `app/services/research_work/proposal_views.py` (머리 docstring :11-12 drafts 줄 아래, `drafts_of` :83-93 아래에 `section_gens_of`, `proposal_view` 반환 dict :145 `"drafts"` 줄 아래)
- Modify: `app/api/research_proposal.py` (`NO_SECTION_PAPERS` :290 아래 상수, `generate_section` :395-396)
- Test: `app/tests/test_research_proposal_api.py` (import :33-35, `TestCitedAndDrafts` 끝 :155 뒤에 `TestSectionGens`, `TestProposalView.test_no_proposal_yet` :159-167, `TestGetProposal.test_view_with_outline_sections_drafts_and_disclosure` :373, `TestGenerateSection.test_gap_without_any_seed_paper_is_409` — 줄 번호는 dev `da80f23` 기준이고 Task A1 이 이 파일 가운데(`TestPutOutline`)에 테스트 하나를 더해 그 뒤가 밀렸다. 자리는 아래 old 글자로 찾는다)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_proposal_api.py` — import 에 `section_gens_of` 를 더한다. old:

```python
from services.research_work.proposal_views import (
    cited_papers, disclosure_of, drafts_of, paper_ids, proposal_view, stale_flags,
)
```

new:

```python
from services.research_work.proposal_views import (
    cited_papers, disclosure_of, drafts_of, paper_ids, proposal_view, section_gens_of, stale_flags,
)
```

같은 파일 — `TestCitedAndDrafts` 와 `TestProposalView` 사이에 `TestSectionGens` 를 넣는다. old:

```python
        assert paper_ids(proposal, gens) == ["C1", "C2", "C3", "C7", "C8"]
        assert paper_ids(None, []) == []


class TestProposalView:
```

new:

```python
        assert paper_ids(proposal, gens) == ["C1", "C2", "C3", "C7", "C8"]
        assert paper_ids(None, []) == []


class TestSectionGens:
    """06e 절 연쇄의 재료 — 화면은 '절도 그 키의 section 생성 기록도 없는 키' 만 자동으로 넣는다(spec §12-4)."""

    def test_last_section_generation_per_key_whatever_its_status(self):
        gens = [_gen(53, "section", "failed", target="prior.g1"),
                _gen(50, "section", "done", target="prior.g1"),     # 같은 키의 옛 생성 — id 가 큰 53 이 남는다
                _gen(51, "section", "canceled", target="gap"),
                _gen(54, "section", "queued", target="prior.g2"),
                _gen(55, "section", "running", target="prior.g3")]
        assert section_gens_of(gens) == {
            "prior.g1": {"gen_id": 53, "status": "failed"},
            "gap": {"gen_id": 51, "status": "canceled"},
            "prior.g2": {"gen_id": 54, "status": "queued"},
            "prior.g3": {"gen_id": 55, "status": "running"},
        }

    def test_other_kinds_and_rows_without_a_target_are_left_out(self):
        gens = [_gen(60, "outline", "done", target=OUTLINE_TARGET),
                _gen(61, "paragraph", "running", target="prior.g1#p1"),   # 문단 다시 쓰기는 절 생성 기록이 아니다
                _gen(62, "section", "done", target=None),
                _gen(63, "concepts", "done")]
        assert section_gens_of(gens) == {}
        assert section_gens_of([]) == {}


class TestProposalView:
```

같은 파일 — 계획서 행이 없는 응답에도 빈 `section_gens`. old:

```python
        assert view == {"version": 0, "outline": None, "sections": {}, "drafts": {}, "papers": {},
                        "references": {}, "corpus": corpus_of(job),
                        "stale": {"outline": False, "sections": {}}, "disclosure": {"steps": []},
                        "topic_source": None}
```

new:

```python
        assert view == {"version": 0, "outline": None, "sections": {}, "drafts": {}, "section_gens": {},
                        "papers": {}, "references": {}, "corpus": corpus_of(job),
                        "stale": {"outline": False, "sections": {}}, "disclosure": {"steps": []},
                        "topic_source": None}
```

같은 파일 — API 조회가 `section_gens` 를 싣는다. old:

```python
        assert body["drafts"] == {"prior.g2": {"gen_id": writing, "evidence": {"E1": "C3"}, "figures": []}}
```

new:

```python
        assert body["drafts"] == {"prior.g2": {"gen_id": writing, "evidence": {"E1": "C3"}, "figures": []}}
        # 06e 절 연쇄의 재료 — 키별 마지막 section 생성. prior.g1 은 절만 있고 생성 행이 없다, 목차 생성은 빠진다
        assert body["section_gens"] == {"prior.g2": {"gen_id": writing, "status": "running"}}
```

같은 파일 — 근거 없음 409 의 detail 이 code 를 단다. old:

```python
        assert (res.status_code, res.json()["detail"]) == (409, "이 절에 넣을 논문이 없습니다")
```

new:

```python
        # 06e — 화면의 절 연쇄는 문구가 아니라 code 로 '이 절만 건너뜀' 을 가른다. 문구는 message 그대로(detailMessage 가 읽는다)
        assert (res.status_code, res.json()["detail"]) == (
            409, {"code": "no_section_papers", "message": "이 절에 넣을 논문이 없습니다"})
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_proposal_api.py -q -p no:cacheprovider`

Expected: `Interrupted: 1 error during collection`(끝 줄 `1 warning, 1 error`) — `ImportError: cannot import name 'section_gens_of' from 'services.research_work.proposal_views'`

- [ ] **Step 3: 응답에 싣고 409 에 code 를 단다**

`app/services/research_work/proposal_views.py` — 머리 docstring 에 한 줄. old:

```python
- drafts 는 쓰는 중(queued·running)인 절 생성의 입력에서 [E#]·[F#] 지도를 꺼낸 것 — 스트리밍 조각을 화면이
  칩으로 그리는 재료다.
```

new:

```python
- drafts 는 쓰는 중(queued·running)인 절 생성의 입력에서 [E#]·[F#] 지도를 꺼낸 것 — 스트리밍 조각을 화면이
  칩으로 그리는 재료다.
- section_gens 는 절 키별 마지막 section 생성 {gen_id, status}(상태 무관) — 06e 화면의 절 연쇄가 '절도 생성 기록도
  없는 키' 를 고르는 재료다(spec §12-4). WorkView 는 끝난 생성을 최근 10건만 실어 연쇄가 쓰지 않는다.
```

같은 파일 — `drafts_of` 아래에 `section_gens_of`. old:

```python
            "figures": list(inp.get("figures") or []),
        }
    return out


def paper_ids(proposal, generations) -> list[str]:
```

new:

```python
            "figures": list(inp.get("figures") or []),
        }
    return out


def section_gens_of(generations) -> dict[str, dict]:
    """절 키 → 그 키의 마지막(id 가 가장 큰) section 생성 {gen_id, status} — 상태 무관(failed·canceled 도 기록이다).
    target 없는 행·다른 kind(목차·문단 다시 쓰기 target '<키>#<pid>' 등)는 뺀다."""
    out: dict[str, dict] = {}
    for g in sorted(generations, key=lambda g: g.id):
        if g.kind == "section" and g.target:
            out[g.target] = {"gen_id": g.id, "status": g.status}
    return out


def paper_ids(proposal, generations) -> list[str]:
```

같은 파일 — `proposal_view` 반환에 키를 더한다. old:

```python
        "drafts": drafts_of(_open_sections(generations)),
        "papers": {cnts_id: book_meta(cnts_id, books.get(cnts_id)) for cnts_id in ids},
```

new:

```python
        "drafts": drafts_of(_open_sections(generations)),
        "section_gens": section_gens_of(generations),
        "papers": {cnts_id: book_meta(cnts_id, books.get(cnts_id)) for cnts_id in ids},
```

`app/api/research_proposal.py` — 상수. old:

```python
NO_SECTION_PAPERS = "이 절에 넣을 논문이 없습니다"
```

new:

```python
NO_SECTION_PAPERS = "이 절에 넣을 논문이 없습니다"
# 06e — 근거 없음 409 의 detail code. 화면의 절 연쇄는 문구가 아니라 이 code 로 '그 절만 건너뛰고 다음 키' 를 가른다
NO_SECTION_PAPERS_CODE = "no_section_papers"
```

같은 파일 — `generate_section` 의 409. old:

```python
    if not cnts_ids:
        raise HTTPException(status_code=409, detail=NO_SECTION_PAPERS)
```

new:

```python
    if not cnts_ids:
        # 구조화한 detail(version_conflict 와 같은 꼴) — 화면 문구는 detailMessage 가 message 를 그대로 읽는다
        raise HTTPException(status_code=409, detail={"code": NO_SECTION_PAPERS_CODE, "message": NO_SECTION_PAPERS})
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_proposal_api.py -q -p no:cacheprovider`

Expected: `98 passed, 2 warnings` (Task A1 뒤 96 + 2)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: `5 failed, (Task 앞 + 2) passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 기준선과 같은 세 파일

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/proposal_views.py app/api/research_proposal.py app/tests/test_research_proposal_api.py && git status --short && git commit -m "[Feat] round06e — 계획서 조회(ProposalView)에 절 키별 마지막 section 생성 {gen_id, status}(section_gens, 상태 무관)를 싣고 근거 없음 409 에 code(no_section_papers)를 단다. 화면의 절 연쇄가 '절도 생성 기록도 없는 키' 를 고르고(WorkView 는 끝난 생성을 최근 10건만 싣는다) 근거 없는 절만 건너뛰는 재료다. _proposal_response 가 이미 읽은 생성 행에서 만들어 새 조회가 없고, 409 문구는 message 그대로라 [이 절 쓰기]의 오류 문구는 바뀌지 않는다"
```

---

### Task A3: 자동 산출 판정 — 순수 함수(남은 절·머리 목차·진행 막대)·타입·버튼 이름 상수

spec §12-4 절 연쇄 '도는 조건'·'대상'·'failed·canceled 키는 다시 넣지 않는다'·'고르는 판정은 `utils/proposalView.ts` 의 순수 함수'·'화면 — 목차가 문서의 머리 목차', Q2 기본(뼈대 정함 1), 사용자 Q1 답 '절 작성 중 커다란 프로그레스바'를 자동 보고서에도 둔다(뼈대 정함 28 — 10-11 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아"). 이 Task 는 계산만 한다 — 그리기는 Task A5, 연쇄를 돌리는 컴포저블은 Task A4.

**알아 둘 것:**
- **서버 모양만 본다** — Task A1·Task A2 의 서버 코드가 없어도 돈다(타입은 선택 필드 `auto?`·`section_gens?` — 옛 응답·기존 픽스처를 깨지 않는다, 06b 머리 규칙).
- **이름 상수(정함 1):** `FINAL_STEP_NAME = "보고서"` 는 조사가 붙지 않는 꼴에만 쓴다 — 버튼 `MAKE_REPORT`·`REMAKE_REPORT`, 진행 막대 글줄 `보고서 작성 중 · n/m절 — 「…」`. 조사가 붙는 문장(확인 창·안내 문구)은 글자 그대로 '보고서'(Task A5). 단계 이름 표(`STEP_NAMES`)는 파트 R(Task R1)이 같은 파일에 더한다.
- **`sectionKeysOf` 가 절 차례의 정본이 된다** — 지금 `proposalDocument.printedKeys`(:217-219)가 같은 식(목차 묶음 → `"gap"`)이다. `proposalDocument.ts` 는 `proposalView.ts` 를 import 하므로 정본을 `proposalView.ts` 에 두고 `printedKeys` 는 그것을 부른다(반대로 두면 순환 import). 이름·뜻·기존 테스트(`proposalDocument.test.ts:291-313`)는 그대로다.
- **도는 조건(`autoChainOn`):** `outline.state === "approved" && outline.auto === true && !work.is_example && 목차 생성(kind outline, target "outline")이 열려 있지 않음`. 06b 때 승인한 목차(auto 없음)는 돌지 않는다 — 사용자가 [보고서 만들기]를 누르지 않았는데 남은 절을 쓰지 않는다(spec). 목차를 다시 만드는 동안은 멈추고, 새 목차가 반영되면(조회를 다시 읽으면) 다시 돈다.
- **대상(`autoTargets`):** 문서 순서 키 가운데 `!p.sections[k] && !p.section_gens?.[k]` — 생성 기록은 상태 무관이라 failed·canceled 로 끝난 키도 다시 넣지 않는다(그 절의 [다시 시도]에 맡긴다). `section_gens` 가 없는 옛 서버 응답은 절이 없는 키를 모두 고른다(06e fastapi 가 먼저 나가므로 운영에는 없는 경우 — 배포 순서 워커 → fastapi → nuxt).
- **근거 없음(`isNoSectionPapers`):** 409 이고 detail 이 객체이며 `code === "no_section_papers"`(Task A2). 접근은 `researchErrors.versionConflict`(:66-73)와 같은 꼴 — `httpStatus` 는 `status`·`statusCode`·`response.status` 를 읽는다.
- **머리 목차(`docToc`)** — 여섯 자리, anchor 는 보고서 화면의 자리 id(뼈대 1-7 표)와 같은 글자다. 테스트가 anchor 를 글자로 고정한다(Task A5 가 그 id 로 자리를 그린다). 라벨은 문서(Word — `proposalDocument.ts:117-136`)와 같은 말: `주제`·`연구 배경`·묶음 이름(Word 의 `3.n 묶음 이름`)·`연구 공백`·`연구 질문`·`방법 제안`(`SECTION_LABELS`).
- **연구 배경 글(`outlineBackground`)** — `Outline.background` 타입 필드는 파트 X(Task X3)가 더한다. 이 Task 는 그 전이라 교차 타입 `Outline & { background?: unknown }` 으로 읽는 작은 함수를 내보낸다(문자열이 아니면 `""`) — Task X3 이 필드를 더한 뒤에도 그대로 컴파일된다. 서버 저장(Task X1) 전에는 늘 빈 글이다.
- **진행 막대(`reportBar` — 정함 28):** 절이 끝날 때만 움직인다(추정 증가 없음 — 절 하나 평균 8초, `round06b-완료노트.md:108`). 키마다 `sectionStatus(k, state)`:
  - 끝난 절 = `done`·`failed`, 또는 쓰기 전(`empty`)인데 건너뛰었거나(skipped) 생성 기록이 있는 키(취소로 끝남).
  - 쓰는 절 = `writing`·`queued`.
  - 남은 절 = 연쇄가 돌 때(`autoChainOn`) `autoTargets` 중 쓰기 전이고 건너뛰지 않은 키 — 넷째 인자 `stopped`(연쇄가 오류로 멈춤)가 참이면 남은 절은 없다고 본다.
  - 쓰는 절도 남은 절도 없으면 `null`(다 썼거나, 연쇄가 돌지 않는 목차에서 손으로 쓰는 절이 없을 때 — 막대를 걷는다). 지금 절 = 쓰는 중 첫 키 → 대기 첫 키 → 남은 첫 키. `label` = `` `${FINAL_STEP_NAME} 작성 중 · ${done}/${total}절 — 「${sectionLabel(지금 절, outline)}」` ``, `percent` = `Math.round(done / total * 100)`, `running` = 지금 절이 쓰는 중.
  - 넷째 인자는 뼈대 시그니처 `reportBar(p, state, skipped)` 에 더한 선택 인자다(기본 false — 파트 메모).
- 모든 파일이 CRLF — Edit 도구로 고친다.

**Files:**
- Modify: `frontend/types/work.ts` (`Outline` :183-195 끝, `ProposalView` :243-255 앞에 `SectionGen`·끝에 `section_gens?`)
- Modify: `frontend/utils/workPhase.ts` (`WORK_STEPS` :9 아래)
- Modify: `frontend/utils/proposalView.ts` (import :13-14, 파일 끝 `addParagraph` :190-192 아래)
- Modify: `frontend/utils/proposalDocument.ts` (import :13, `printedKeys` :215-219)
- Test: `frontend/tests/unit/proposalView.test.ts` (import :3-30, 파일 끝에 describe 여섯)
- Test: `frontend/tests/unit/workPhase.test.ts` (import :5-18, 파일 끝에 describe 하나)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/proposalView.test.ts` — import 를 넓힌다. old:

```ts
import type {
  Outline,
  Paragraph,
  ParaState,
  ProposalSection,
  ProposalView,
  WorkGeneration,
  WorkState,
} from "~/types/work";
import {
  GAP_NOTE,
  MAX_PARAGRAPH_CHARS,
  SECTION_LABELS,
  acceptParagraph,
  addParagraph,
  checkLine,
  editParagraph,
  failedParagraphGens,
  footprint,
  footprintLine,
  openParagraphGens,
  paragraphParts,
  paragraphProblem,
  paragraphViews,
  removeParagraph,
  sectionLabel,
  sectionStatus,
} from "~/utils/proposalView";
```

new:

```ts
import type {
  Outline,
  Paragraph,
  ParaState,
  ProposalSection,
  ProposalView,
  WorkGeneration,
  WorkState,
  WorkView,
} from "~/types/work";
import {
  GAP_NOTE,
  MAX_PARAGRAPH_CHARS,
  SECTION_LABELS,
  acceptParagraph,
  addParagraph,
  autoChainOn,
  autoTargets,
  checkLine,
  docToc,
  editParagraph,
  failedParagraphGens,
  footprint,
  footprintLine,
  isNoSectionPapers,
  nextAutoSection,
  openParagraphGens,
  outlineBackground,
  paragraphParts,
  paragraphProblem,
  paragraphViews,
  removeParagraph,
  reportBar,
  sectionKeysOf,
  sectionLabel,
  sectionStatus,
} from "~/utils/proposalView";
import { FINAL_STEP_NAME } from "~/utils/workPhase";
```

같은 파일 — 끝(`describe("절 PUT 본문", …)` 뒤)에 자동 산출 판정을 더한다. old:

```ts
  it("지우기는 그 문단을 빼고, 더하기는 id 없는 사용자 작성 문단을 끝에 붙인다", () => {
    expect(removeParagraph(sec, "p2").paragraphs.map((p) => p.id)).toEqual(["p1", "p3"]);
    expect(addParagraph(sec, "더한 글.").paragraphs.at(-1)).toEqual({ id: null, text: "더한 글.", state: "authored" });
    expect(addParagraph(sec, "더한 글.").paragraphs).toHaveLength(4);
  });
});
```

new:

```ts
  it("지우기는 그 문단을 빼고, 더하기는 id 없는 사용자 작성 문단을 끝에 붙인다", () => {
    expect(removeParagraph(sec, "p2").paragraphs.map((p) => p.id)).toEqual(["p1", "p3"]);
    expect(addParagraph(sec, "더한 글.").paragraphs.at(-1)).toEqual({ id: null, text: "더한 글.", state: "authored" });
    expect(addParagraph(sec, "더한 글.").paragraphs).toHaveLength(4);
  });
});

// ── 보고서 자동 산출(06e D20) ─────────────────────────────────
// 묶음 둘(prior.g1·prior.g2) + 연구 공백 = 자동으로 쓰는 절 셋. [보고서 만들기]의 반영이 자동 승인한 목차(auto)다
function autoOutline(over: Partial<Outline> = {}): Outline {
  return {
    ...outline(),
    groups: [
      { key: "prior.g1", name: "노인의 우울", hint: "노인 우울", papers: ["KCI_A"] },
      { key: "prior.g2", name: "세대 간 지지", hint: "사회적 지지", papers: ["KCI_B"] },
    ],
    auto: true,
    ...over,
  };
}

function autoProposal(over: Partial<ProposalView> = {}): ProposalView {
  return { ...proposal({}), outline: autoOutline(), section_gens: {}, ...over };
}

// 화면 상태 — 계획서는 p, 생성 목록은 gens(연구의 다른 칸은 over 로 바꾼다)
function autoState(p: ProposalView, gens: WorkGeneration[] = [], over: Partial<WorkView> = {}): WorkState {
  const s = state(gens);
  return { ...s, work: { ...s.work!, ...over }, proposal: p };
}

function outlineGen(id: number, status: WorkGeneration["status"]): WorkGeneration {
  return { ...gen(id, status, "outline"), kind: "outline" };
}

describe("sectionKeysOf — 자동으로 쓰는 절의 차례", () => {
  it("목차 묶음 순서 → 연구 공백, 목차가 없으면 연구 공백만(printedKeys 와 같은 범위)", () => {
    expect(sectionKeysOf(autoProposal())).toEqual(["prior.g1", "prior.g2", "gap"]);
    const reversed = autoOutline({ groups: [...autoOutline().groups].reverse() });
    expect(sectionKeysOf(autoProposal({ outline: reversed }))).toEqual(["prior.g2", "prior.g1", "gap"]);
    expect(sectionKeysOf(autoProposal({ outline: null }))).toEqual(["gap"]);
  });
});

describe("autoChainOn — 자동 산출이 도는 조건", () => {
  it("승인·auto·예시 아님·목차 생성 없음이면 돈다", () => {
    const p = autoProposal();
    expect(autoChainOn(p, autoState(p).work)).toBe(true);
    // 끝난 목차 생성은 막지 않는다
    expect(autoChainOn(p, autoState(p, [outlineGen(40, "done")]).work)).toBe(true);
  });

  it("06b 목차(auto 없음)·auto false 는 돌지 않는다 — [보고서 만들기]를 누르지 않은 연구의 남은 절을 쓰지 않는다", () => {
    const before06e: Outline = { ...autoOutline() };
    delete before06e.auto;
    const old = autoProposal({ outline: before06e });
    expect(autoChainOn(old, autoState(old).work)).toBe(false);
    const off = autoProposal({ outline: autoOutline({ auto: false }) });
    expect(autoChainOn(off, autoState(off).work)).toBe(false);
  });

  it("초안 목차는 돌지 않는다 — 질문이 없어 자동 승인하지 못했거나 [목차 고치기]에서 승인을 푼 목차", () => {
    const p = autoProposal({ outline: autoOutline({ state: "draft", approved_at: null }) });
    expect(autoChainOn(p, autoState(p).work)).toBe(false);
  });

  it("예시 연구는 돌지 않는다(쓰기가 409)", () => {
    const p = autoProposal();
    expect(autoChainOn(p, autoState(p, [], { is_example: true }).work)).toBe(false);
  });

  it("목차를 다시 만드는 중이면 돌지 않는다", () => {
    const p = autoProposal();
    expect(autoChainOn(p, autoState(p, [outlineGen(40, "queued")]).work)).toBe(false);
    expect(autoChainOn(p, autoState(p, [outlineGen(40, "running")]).work)).toBe(false);
  });

  it("조회 전(null)·목차 없음은 돌지 않는다", () => {
    const p = autoProposal();
    expect(autoChainOn(null, autoState(p).work)).toBe(false);
    expect(autoChainOn(p, null)).toBe(false);
    const none = autoProposal({ outline: null });
    expect(autoChainOn(none, autoState(none).work)).toBe(false);
  });
});

describe("autoTargets·nextAutoSection — 남은 절 고르기", () => {
  const four = autoOutline({
    groups: ["prior.g1", "prior.g2", "prior.g3", "prior.g4"].map((key, i) => ({
      key,
      name: `묶음 ${i + 1}`,
      hint: "",
      papers: [`KCI_${i}`],
    })),
  });

  it("문서 순서 prior.g1~g4 → gap", () => {
    expect(autoTargets(autoProposal({ outline: four }))).toEqual(["prior.g1", "prior.g2", "prior.g3", "prior.g4", "gap"]);
  });

  it("쓴 절은 빼고 생성 기록이 있는 키(failed·canceled 포함)도 뺀다 — 실패한 절은 그 절의 [다시 시도]에 맡긴다", () => {
    const p = autoProposal({
      outline: four,
      sections: { "prior.g1": section([para("p1", "proposed")]) },
      section_gens: {
        "prior.g2": { gen_id: 61, status: "failed" },
        "prior.g3": { gen_id: 62, status: "canceled" },
        "prior.g4": { gen_id: 63, status: "running" },
      },
    });
    expect(autoTargets(p)).toEqual(["gap"]);
  });

  it("section_gens 가 없는 옛 응답은 절이 없는 키를 모두 고른다", () => {
    const p = autoProposal({ sections: { "prior.g1": section([para("p1", "proposed")]) } });
    delete p.section_gens;
    expect(autoTargets(p)).toEqual(["prior.g2", "gap"]);
  });

  it("skip 의 키(이 방문에서 넣었거나 근거가 없어 건너뛴 키)는 건너뛴다", () => {
    const p = autoProposal();
    expect(nextAutoSection(p, new Set())).toBe("prior.g1");
    expect(nextAutoSection(p, new Set(["prior.g1"]))).toBe("prior.g2");
    expect(nextAutoSection(p, new Set(["prior.g1", "prior.g2"]))).toBe("gap");
  });

  it("남은 키가 없으면 null", () => {
    expect(nextAutoSection(autoProposal(), new Set(["prior.g1", "prior.g2", "gap"]))).toBeNull();
    const all = autoProposal({
      section_gens: {
        "prior.g1": { gen_id: 1, status: "done" },
        "prior.g2": { gen_id: 2, status: "done" },
        gap: { gen_id: 3, status: "queued" },
      },
    });
    expect(nextAutoSection(all, new Set())).toBeNull();
  });
});

describe("isNoSectionPapers — 근거 없음 409", () => {
  const fetchError = (status: number, detail: unknown) =>
    Object.assign(new Error(`HTTP ${status}`), { status, statusCode: status, data: { detail } });

  it("409 이고 detail code 가 no_section_papers 일 때만 참", () => {
    expect(isNoSectionPapers(fetchError(409, { code: "no_section_papers", message: "이 절에 넣을 논문이 없습니다" }))).toBe(true);
  });

  it("문자열 detail(06e 전 서버)·다른 code·404·네트워크 오류는 거짓", () => {
    expect(isNoSectionPapers(fetchError(409, "이 절에 넣을 논문이 없습니다"))).toBe(false);
    expect(isNoSectionPapers(fetchError(409, "이 절을 쓰는 중입니다"))).toBe(false);
    expect(isNoSectionPapers(fetchError(409, { code: "version_conflict", version: 3, message: "다른 곳에서 바뀌었습니다" }))).toBe(false);
    expect(isNoSectionPapers(fetchError(404, { code: "no_section_papers", message: "이 절에 넣을 논문이 없습니다" }))).toBe(false);
    expect(isNoSectionPapers(new TypeError("Failed to fetch"))).toBe(false);
    expect(isNoSectionPapers(null)).toBe(false);
  });
});

describe("docToc — 머리 목차", () => {
  it("여섯 자리를 문서 순서로 — anchor 는 보고서 화면의 자리 id 와 같은 글자", () => {
    const p = autoProposal({
      outline: autoOutline({ method: "설문 조사" }),
      sections: { "prior.g1": section([para("p1", "proposed")]) },
    });
    const s = autoState(p, [gen(50, "done"), gen(51, "running", "prior.g2")]);
    expect(docToc(p, s, new Set()).map((i) => [i.key, i.no, i.label, i.anchor, i.status])).toEqual([
      ["topic", "1", "주제", "wk-doc-topic", "text"],
      ["background", "2", "연구 배경", "wk-doc-background", "blank"],
      ["prior.g1", "3.1", "노인의 우울", "wk-sec-prior.g1", "done"],
      ["prior.g2", "3.2", "세대 간 지지", "wk-sec-prior.g2", "writing"],
      ["gap", "4", "연구 공백", "wk-sec-gap", "empty"],
      ["question", "5", "연구 질문", "wk-doc-question", "text"],
      ["method", "6", "방법 제안", "wk-doc-method", "text"],
    ]);
  });

  it("배경·질문·방법이 비면 blank — 배경을 적었으면 text", () => {
    const statuses = (p: ProposalView) => docToc(p, autoState(p), new Set()).map((i) => i.status);
    const blank = autoProposal({ outline: autoOutline({ question: null, method: "  " }) });
    expect(statuses(blank)).toEqual(["text", "blank", "empty", "empty", "empty", "blank", "blank"]);
    // 연구 배경은 Outline.background 글이다 — 키가 없는 응답(필드를 열기 전 서버)은 빈 글이다
    const written = autoProposal({ outline: { ...autoOutline(), background: "농촌 노인의 고립이 커졌다." } as Outline });
    expect(statuses(written)[1]).toBe("text");
    expect(outlineBackground(written.outline!)).toBe("농촌 노인의 고립이 커졌다.");
    expect(outlineBackground(autoOutline())).toBe("");
  });

  it("근거가 없어 건너뛴 쓰기 전 절은 skipped — 손으로 다시 쓰기 시작하면 그 절의 상태", () => {
    const p = autoProposal();
    const gapOf = (s: WorkState, skipped: ReadonlySet<string>) => docToc(p, s, skipped).find((i) => i.key === "gap")!.status;
    expect(gapOf(autoState(p), new Set(["gap"]))).toBe("skipped");
    expect(gapOf(autoState(p, [gen(70, "queued", "gap")]), new Set(["gap"]))).toBe("queued");
  });

  it("목차가 없으면 빈 목록", () => {
    const p = autoProposal({ outline: null });
    expect(docToc(p, autoState(p), new Set())).toEqual([]);
  });
});

describe("reportBar — 보고서 작성 중 큰 진행 막대", () => {
  it("쓰는 절이 있으면 '보고서 작성 중 · 1/3절 — 「…」'과 33%", () => {
    const p = autoProposal({
      sections: { "prior.g1": section([para("p1", "proposed")]) },
      section_gens: { "prior.g1": { gen_id: 50, status: "done" }, "prior.g2": { gen_id: 51, status: "running" } },
    });
    expect(reportBar(p, autoState(p, [gen(50, "done"), gen(51, "running", "prior.g2")]), new Set())).toEqual({
      label: "보고서 작성 중 · 1/3절 — 「선행연구 검토 · 세대 간 지지」",
      done: 1,
      total: 3,
      percent: 33,
      running: true,
    });
  });

  it("쓰는 절이 없어도 연쇄가 남은 절을 넣을 참이면 다음 절 이름 — 대기 중인 절이 있으면 그 절", () => {
    const p = autoProposal();
    expect(reportBar(p, autoState(p), new Set())).toEqual({
      label: "보고서 작성 중 · 0/3절 — 「선행연구 검토 · 노인의 우울」",
      done: 0,
      total: 3,
      percent: 0,
      running: false,
    });
    const queued = autoProposal({ section_gens: { gap: { gen_id: 52, status: "queued" } } });
    expect(reportBar(queued, autoState(queued, [gen(52, "queued", "gap")]), new Set())).toMatchObject({
      label: "보고서 작성 중 · 0/3절 — 「연구 공백」",
      running: false,
    });
  });

  it("건너뛴 절·실패한 절·취소로 끝난 쓰기 전 절은 끝난 수에 든다", () => {
    const p = autoProposal({
      section_gens: { "prior.g1": { gen_id: 50, status: "failed" }, "prior.g2": { gen_id: 51, status: "running" } },
    });
    expect(reportBar(p, autoState(p, [gen(50, "failed"), gen(51, "running", "prior.g2")]), new Set(["gap"]))).toEqual({
      label: "보고서 작성 중 · 2/3절 — 「선행연구 검토 · 세대 간 지지」",
      done: 2,
      total: 3,
      percent: 67,
      running: true,
    });
    const canceled = autoProposal({ section_gens: { "prior.g1": { gen_id: 50, status: "canceled" } } });
    expect(reportBar(canceled, autoState(canceled, [gen(50, "canceled")]), new Set())).toMatchObject({
      label: "보고서 작성 중 · 1/3절 — 「선행연구 검토 · 세대 간 지지」",
      done: 1,
      percent: 33,
    });
  });

  it("다 썼거나, auto 없는 목차·멈춘 연쇄에 쓰는 절이 없으면 null", () => {
    const done = autoProposal({
      sections: {
        "prior.g1": section([para("p1", "proposed")]),
        "prior.g2": section([para("p1", "proposed")], { key: "prior.g2", gen_id: 51 }),
        gap: section([para("p1", "proposed")], { key: "gap", gen_id: 52 }),
      },
      section_gens: {
        "prior.g1": { gen_id: 50, status: "done" },
        "prior.g2": { gen_id: 51, status: "done" },
        gap: { gen_id: 52, status: "done" },
      },
    });
    const doneGens = [gen(50, "done"), gen(51, "done", "prior.g2"), gen(52, "done", "gap")];
    expect(reportBar(done, autoState(done, doneGens), new Set())).toBeNull();
    const old = autoProposal({ outline: autoOutline({ auto: false }) });
    expect(reportBar(old, autoState(old), new Set())).toBeNull();
    // 06b 목차라도 손으로 쓰는 절이 있으면 그 절을 보인다
    expect(reportBar(old, autoState(old, [gen(60, "running", "gap")]), new Set())!.label).toBe(
      "보고서 작성 중 · 0/3절 — 「연구 공백」",
    );
    // 연쇄가 오류로 멈추면(넷째 인자) 남은 절로는 막대를 세우지 않는다
    const p = autoProposal();
    expect(reportBar(p, autoState(p), new Set(), true)).toBeNull();
    const none = autoProposal({ outline: null });
    expect(reportBar(none, autoState(none), new Set())).toBeNull();
  });

  it("조사를 붙이지 않는다 — FINAL_STEP_NAME 뒤가 ' 작성 중'", () => {
    const p = autoProposal();
    const label = reportBar(p, autoState(p), new Set())!.label;
    expect(label.startsWith(`${FINAL_STEP_NAME} 작성 중 · `)).toBe(true);
    expect(label).not.toMatch(new RegExp(`${FINAL_STEP_NAME}[을를이가은는의로]`));
  });
});
```

`frontend/tests/unit/workPhase.test.ts` — import 에 이름 셋. old:

```ts
import {
  ONBOARDING_KEY,
  ONBOARDING_STEPS,
  WORK_STEPS,
```

new:

```ts
import {
  FINAL_STEP_NAME,
  MAKE_REPORT,
  ONBOARDING_KEY,
  ONBOARDING_STEPS,
  REMAKE_REPORT,
  WORK_STEPS,
```

같은 파일 — 끝(`describe("온보딩", …)` 뒤)에 더한다. old:

```ts
    expect(ONBOARDING_STEPS.map((s) => s.title)).toEqual(["주제", "읽기 목록", "계획서"]);
    for (const s of ONBOARDING_STEPS) {
      expect(s.body.length).toBeGreaterThan(0);
      expect(s.decide.length).toBeGreaterThan(0);
    }
  });
});
```

new:

```ts
    expect(ONBOARDING_STEPS.map((s) => s.title)).toEqual(["주제", "읽기 목록", "계획서"]);
    for (const s of ONBOARDING_STEPS) {
      expect(s.body.length).toBeGreaterThan(0);
      expect(s.decide.length).toBeGreaterThan(0);
    }
  });
});

describe("FINAL_STEP_NAME·버튼 이름", () => {
  it("마지막 단계 이름은 '보고서'(Q2 기본) — 버튼은 조사 없는 꼴로 이름에서 만든다", () => {
    expect(FINAL_STEP_NAME).toBe("보고서");
    expect(MAKE_REPORT).toBe(`${FINAL_STEP_NAME} 만들기`);
    expect(REMAKE_REPORT).toBe(`${FINAL_STEP_NAME} 다시 만들기`);
    expect([MAKE_REPORT, REMAKE_REPORT]).toEqual(["보고서 만들기", "보고서 다시 만들기"]);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/proposalView.test.ts tests/unit/workPhase.test.ts`

Expected: `Tests  24 failed | 40 passed (64)`(`Test Files  2 failed (2)`) — 새 it 24개가 모두 실패한다(`TypeError: (0 , sectionKeysOf) is not a function` 등 — 없는 이름은 `undefined` 로 들어온다). 기존 it 40개(proposalView 20·workPhase 20)는 그대로 통과

- [ ] **Step 3: 타입·상수·판정을 쓴다**

`frontend/types/work.ts` — `Outline` 에 `auto`. old:

```ts
  approved_at: string | null;
  // 목차를 만들 때의 핵심 개념
  concepts?: string[];
}
```

new:

```ts
  approved_at: string | null;
  // 목차를 만들 때의 핵심 개념
  concepts?: string[];
  // [보고서 만들기]의 반영이 자동 승인한 목차만 true — 화면의 절 연쇄가 읽는다(06e D20. 06b 목차엔 키가 없다)
  auto?: boolean;
}
```

같은 파일 — `ProposalView` 앞에 `SectionGen`. old:

```ts
export interface ProposalView {
  version: number;
```

new:

```ts
// 절 키별 마지막 section 생성(상태 무관) — 06e 절 연쇄가 '절도 생성 기록도 없는 키' 를 고르는 재료
export interface SectionGen {
  gen_id: number;
  status: GenStatus;
}

export interface ProposalView {
  version: number;
```

같은 파일 — `ProposalView` 끝에 `section_gens`. old:

```ts
  // 고른 주제의 출처(공개 부록용) — 주제가 없으면 null
  topic_source?: { origin: TopicItem["origin"]; edited: boolean } | null;
}
```

new:

```ts
  // 고른 주제의 출처(공개 부록용) — 주제가 없으면 null
  topic_source?: { origin: TopicItem["origin"]; edited: boolean } | null;
  // 절 키 → 그 키의 마지막 section 생성(06e 서버부터 — 옛 응답엔 없다)
  section_gens?: Record<string, SectionGen>;
}
```

`frontend/utils/workPhase.ts` — `WORK_STEPS` 아래에 이름 상수. old:

```ts
export const WORK_STEPS: readonly WorkStep[] = ["topics", "reading", "proposal"];
```

new:

```ts
export const WORK_STEPS: readonly WorkStep[] = ["topics", "reading", "proposal"];

// 마지막 단계(④)의 이름 — 사용자 답(Q2)이 없을 때의 기본 '보고서'(06e 정함 1). 조사가 붙지 않는 꼴(버튼·진행 막대 글줄·
// 단계 이름)에만 이 상수를 쓴다. 조사가 붙는 문장은 글자 그대로 '보고서'를 쓴다 — `${FINAL_STEP_NAME}를` 은 이름이
// 바뀌면 틀린다('연구 초안를')
export const FINAL_STEP_NAME = "보고서";
export const MAKE_REPORT = `${FINAL_STEP_NAME} 만들기`;
export const REMAKE_REPORT = `${FINAL_STEP_NAME} 다시 만들기`;
```

`frontend/utils/proposalView.ts` — import 두 줄. old:

```ts
import { sentenceFlags, splitMarkers, type MarkerPart, type SentenceFlag } from "~/utils/figureMarkers";
import { latestGeneration, openGeneration } from "~/utils/workEvents";
```

new:

```ts
import { sentenceFlags, splitMarkers, type MarkerPart, type SentenceFlag } from "~/utils/figureMarkers";
import { httpStatus } from "~/utils/researchErrors";
import { latestGeneration, openGeneration } from "~/utils/workEvents";
import { FINAL_STEP_NAME } from "~/utils/workPhase";
```

같은 파일 — 끝에 자동 산출 판정을 더한다. old:

```ts
export function addParagraph(section: ProposalSection, text: string): SectionPut {
  return { paragraphs: [...section.paragraphs.map(entry), { id: null, text, state: "authored" }] };
}
```

new:

```ts
export function addParagraph(section: ProposalSection, text: string): SectionPut {
  return { paragraphs: [...section.paragraphs.map(entry), { id: null, text, state: "authored" }] };
}

// ── 보고서 자동 산출(06e D20) — [보고서 만들기] 한 번으로 목차를 자동 확정하고 절을 문서 순서대로 넣는다 ──

// 화면이 쓰는 절의 차례 — 목차 묶음 순서(prior.g1~g4) → 연구 공백. 계획서 화면의 절 목록·문서(proposalDocument.printedKeys)·
// 자동 산출이 모두 이 순서다. 목차가 없으면 연구 공백만
export function sectionKeysOf(p: ProposalView): string[] {
  return [...(p.outline?.groups.map((g) => g.key) ?? []), "gap"];
}

// 절 연쇄가 도는 조건 — [보고서 만들기]의 반영이 자동 승인한 목차(state approved·auto)이고, 예시 연구가 아니고(쓰기가 409),
// 목차를 다시 만드는 중이 아닐 때. 06b 때 승인한 목차(auto 없음)·[목차 고치기]에서 승인을 푼 목차는 돌지 않는다.
// 조건은 늘 서버 값으로 다시 계산한다 — 탭을 닫았다 와도 같은 조건으로 이어 넣는다(spec §12-4)
export function autoChainOn(p: ProposalView | null, work: WorkView | null): boolean {
  const outline = p?.outline;
  if (!outline || !work) return false;
  return (
    outline.state === "approved" &&
    outline.auto === true &&
    !work.is_example &&
    !openGeneration({ work }, "outline", "outline")
  );
}

// 자동으로 쓸 절 — 문서 순서에서 절도, 그 키의 section 생성 기록(상태 무관 — failed·canceled 포함)도 없는 키. 실패·취소로
// 끝난 절은 다시 넣지 않고 그 절의 [다시 시도]에 맡긴다. section_gens 가 없는 옛 서버 응답은 절이 없는 키를 모두 고른다
export function autoTargets(p: ProposalView): string[] {
  const gens = p.section_gens ?? {};
  return sectionKeysOf(p).filter((k) => !p.sections[k] && !gens[k]);
}

// 다음에 넣을 절 — skip(이 방문에서 이미 넣었거나 근거가 없어 건너뛴 키)을 뺀 첫 키, 없으면 null
export function nextAutoSection(p: ProposalView, skip: ReadonlySet<string>): string | null {
  return autoTargets(p).find((k) => !skip.has(k)) ?? null;
}

// 절 쓰기가 '그 절에 넣을 논문이 없어' 막혔다 — 409 detail {code: "no_section_papers", message}(06e 서버). 연쇄는 그 절만
// 건너뛰고 다음 키로 간다. 문자열 detail(06e 전 서버)·다른 409(쓰는 중·승인 전)는 아니다
export function isNoSectionPapers(err: unknown): boolean {
  if (httpStatus(err) !== 409) return false;
  const data = (err as { data?: unknown } | null)?.data;
  const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : null;
  return !!detail && typeof detail === "object" && (detail as { code?: unknown }).code === "no_section_papers";
}

// 연구 배경 글 — Outline.background 키가 없는 응답(필드를 열기 전 서버)은 빈 글이다
export function outlineBackground(outline: Outline): string {
  const value = (outline as Outline & { background?: unknown }).background;
  return typeof value === "string" ? value : "";
}

// 머리 목차의 한 항목. anchor 는 보고서 화면의 자리 id(ProposalStep — 1·2·5·6 은 wk-doc-*, 절은 ProposalSection 의 wk-sec-<key>)
export interface TocItem {
  key: string;
  no: string;
  label: string;
  anchor: string;
  status: SectionStatus | "text" | "blank" | "skipped";
}

// 머리 목차 — 문서 순서의 여섯 자리(1 주제·2 연구 배경·3.n 선행연구 묶음·4 연구 공백·5 연구 질문·6 방법 제안 — Word 의 절
// 제목과 같은 말). 글 자리는 적었으면 text, 비면 blank. 절은 그 절의 상태(sectionStatus), 근거가 없어 연쇄가 건너뛴 쓰기 전
// 절은 skipped. 목차가 없으면 빈 목록
export function docToc(p: ProposalView, state: WorkState, skipped: ReadonlySet<string>): TocItem[] {
  const outline = p.outline;
  if (!outline) return [];
  const filled = (text: string | null | undefined): TocItem["status"] => (text?.trim() ? "text" : "blank");
  const sectionItem = (key: string, no: string, label: string): TocItem => {
    const status = sectionStatus(key, state);
    return { key, no, label, anchor: `wk-sec-${key}`, status: status === "empty" && skipped.has(key) ? "skipped" : status };
  };
  return [
    { key: "topic", no: "1", label: SECTION_LABELS.topic!, anchor: "wk-doc-topic", status: filled(outline.topic.title) },
    {
      key: "background",
      no: "2",
      label: SECTION_LABELS.background!,
      anchor: "wk-doc-background",
      status: filled(outlineBackground(outline)),
    },
    ...outline.groups.map((g, i) => sectionItem(g.key, `3.${i + 1}`, g.name)),
    sectionItem("gap", "4", SECTION_LABELS.gap!),
    { key: "question", no: "5", label: SECTION_LABELS.question!, anchor: "wk-doc-question", status: filled(outline.question) },
    { key: "method", no: "6", label: SECTION_LABELS.method!, anchor: "wk-doc-method", status: filled(outline.method) },
  ];
}

// 보고서 화면 머리의 큰 진행 막대(06e 정함 28 — 사용자 Q1 답 '현재 절 작성 중에 보이는 커다란 프로그레스바'를 자동 보고서에도)
export interface ReportBar {
  label: string;
  done: number;
  total: number;
  percent: number;
  running: boolean;
}

// 절이 끝날 때만 움직인다(추정 증가 없음 — 절 하나 평균 8초). 끝난 절 = 다 썼거나(done) 실패했거나, 쓰기 전인데 근거가 없어
// 건너뛰었거나 생성 기록이 있는(취소로 끝난) 절. 쓰는 절 = 대기·쓰는 중. 남은 절 = 연쇄가 돌 때 아직 넣지 않은 절(건너뛴 키
// 빼고) — stopped(연쇄가 오류로 멈춤)면 없다고 본다. 쓰는 절도 남은 절도 없으면 null(다 썼거나, 연쇄가 돌지 않는 목차에서
// 손으로 쓰는 절이 없을 때 — 막대를 걷는다). 글줄은 조사 없는 꼴(정함 1)
export function reportBar(
  p: ProposalView,
  state: WorkState,
  skipped: ReadonlySet<string>,
  stopped = false,
): ReportBar | null {
  const outline = p.outline;
  if (!outline) return null;
  const keys = sectionKeysOf(p);
  const gens = p.section_gens ?? {};
  const status = new Map(keys.map((k) => [k, sectionStatus(k, state)] as const));
  const done = keys.filter((k) => {
    const st = status.get(k);
    return st === "done" || st === "failed" || (st === "empty" && (skipped.has(k) || gens[k] !== undefined));
  }).length;
  const active = keys.filter((k) => status.get(k) === "writing" || status.get(k) === "queued");
  const pending =
    !stopped && autoChainOn(p, state.work)
      ? autoTargets(p).filter((k) => status.get(k) === "empty" && !skipped.has(k))
      : [];
  const current = active.find((k) => status.get(k) === "writing") ?? active[0] ?? pending[0];
  if (current === undefined) return null;
  const total = keys.length;
  return {
    label: `${FINAL_STEP_NAME} 작성 중 · ${done}/${total}절 — 「${sectionLabel(current, outline)}」`,
    done,
    total,
    percent: Math.round((done / total) * 100),
    running: status.get(current) === "writing",
  };
}
```

`frontend/utils/proposalDocument.ts` — import 에 `sectionKeysOf`. old:

```ts
import { GAP_NOTE, SECTION_LABELS, footprint, footprintLine, sectionLabel } from "~/utils/proposalView";
```

new:

```ts
import { GAP_NOTE, SECTION_LABELS, footprint, footprintLine, sectionKeysOf, sectionLabel } from "~/utils/proposalView";
```

같은 파일 — `printedKeys` 는 정본을 부른다(이름·뜻 그대로). old:

```ts
// 문서가 그리는 절 — 목차 순서(선행연구 묶음 → 연구 공백). 계획서 화면의 절 목록(ProposalStep)도 이 범위를 쓴다 —
// 절을 더하면(06c 연구 배경 등) 화면과 문서가 함께 바뀐다
export function printedKeys(p: ProposalView): string[] {
  return [...(p.outline?.groups.map((g) => g.key) ?? []), "gap"];
}
```

new:

```ts
// 문서가 그리는 절 — 목차 순서(선행연구 묶음 → 연구 공백). 계획서 화면의 절 목록(ProposalStep)과 06e 자동 산출의 차례도
// 이 범위다 — 정본은 proposalView.sectionKeysOf(이 파일이 proposalView 를 import 하므로 반대로 두면 순환 import)
export function printedKeys(p: ProposalView): string[] {
  return sectionKeysOf(p);
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/proposalView.test.ts tests/unit/workPhase.test.ts tests/unit/proposalDocument.test.ts`

Expected: `Test Files  3 passed (3)` / `Tests  82 passed (82)` (proposalView 20 + 23 · workPhase 20 + 1 · proposalDocument 18 그대로)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`

Expected: 실패 0 — `Test Files` 수는 그대로, `Tests` 는 Task 앞 + 24

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`

Expected: `0`

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/types/work.ts frontend/utils/workPhase.ts frontend/utils/proposalView.ts frontend/utils/proposalDocument.ts frontend/tests/unit/proposalView.test.ts frontend/tests/unit/workPhase.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 보고서 자동 산출의 판정을 순수 함수로 둔다. 연쇄가 도는 조건(autoChainOn — 자동 승인 목차·예시 아님·목차 생성 없음), 남은 절(autoTargets·nextAutoSection — 절도 생성 기록도 없는 키를 문서 순서로, failed·canceled 는 다시 넣지 않음), 근거 없음 409(isNoSectionPapers), 머리 목차 여섯 자리(docToc — anchor 는 보고서 화면 자리 id), 큰 진행 막대(reportBar — '보고서 작성 중 · n/m절 — 「절」'·퍼센트, 절이 끝날 때만 움직임 — 사용자 Q1 답을 자동 보고서에도). 절 차례의 정본을 sectionKeysOf 로 옮기고 printedKeys 는 그것을 부른다. 타입은 선택 필드(Outline.auto·ProposalView.section_gens·SectionGen), 마지막 단계 이름 상수 FINAL_STEP_NAME '보고서'(Q2 기본)와 버튼 이름 MAKE_REPORT·REMAKE_REPORT"
```

---

### Task A4: 절 연쇄 — useAutoReport

spec §12-4 절 연쇄 '하나씩'·'응답 처리'·'탭을 닫았다 와도'·'절 여럿을 한 엔드포인트로 묶지 않는다', 뼈대 정함 6. 보고서 화면(ProposalStep — Task A5)이 쥐는 컴포저블이다. 판정은 Task A3 의 순수 함수(`autoChainOn`·`nextAutoSection`·`isNoSectionPapers`)를 부른다.

**알아 둘 것:**
- **왜 화면이 넣나:** 원문 대목 고르기(리랭커·Milvus)는 FastAPI 프로세스에만 있어(함정 17, `research_work/passages.py:1-13`) 생성 워커가 목차 뒤에 절 생성을 이어 넣을 수 없다. 절 여럿을 한 엔드포인트로 묶지 않는다 — 요청 하나의 대목 고르기가 최악 약 60초라 묶으면 게이트웨이 120초를 넘는다(spec).
- **동작(뼈대 1-7 계약):** `watch([proposal, work], kick, { immediate: true })`. `kick` = 돌고 있지 않고·멈추지 않았고·`autoChainOn` 이고·다음 키가 있으면 루프. 루프 = 키 하나 → `await generate(key)` → 성공이면 `requested` 에 넣고 다음, `isNoSectionPapers(e)` 면 `skipped` 에 넣고 다음, 그 밖의 오류(409 쓰는 중·승인 전·5xx·네트워크)면 `stopped = workErrorMessage(e, "보고서를 이어 쓰지 못했습니다")` 하고 멈춤. 루프가 끝나면 `reload()` 한 번(넣은 생성의 대기 순번·`section_gens` 를 한 번에 맞춘다). 생성이 끝나기는 기다리지 않는다 — 실행 순서는 디스패처(우선순위 → 만든 순, `dispatch.py:75-109`).
- **뼈대에 더한 것 셋(파트 메모):**
  1. 다음 키를 고를 때 연구의 생성 목록(`work.generations` — SSE 이벤트로 계획서보다 먼저 바뀐다)에 그 키의 section 생성이 있으면 건너뛴다 — 사용자가 연쇄 중에 손으로 [이 절 쓰기]를 누른 절을 또 넣으면 409 `SECTION_BUSY` 로 연쇄가 멈춘다. '생성 기록이 있는 키는 대상이 아니다'(spec)를 계획서를 다시 읽기 전에도 지키는 것이다.
  2. 루프가 끝나 `running` 을 내린 뒤 `kick()` 을 한 번 더 부른다 — 도는 동안의 watch 는 `running` 에 막혀 그사이 들어온 변화(새 목차 등)를 놓친다. 키마다 넣음·건너뜀·멈춤 셋 중 하나로 끝나므로 같은 키를 두 번 넣지 않는다.
  3. 목차의 `gen_id` 가 바뀌면([보고서 다시 만들기] — 새 반영) 이 방문의 `skipped`·`stopped`·`requested` 를 비우고 다시 돈다 — 묶음을 다시 나눠 근거가 생겼을 수 있다. 이미 넣은 키는 새 계획서의 `section_gens` 가 막는다.
- **탭을 닫았다 와도(정함 6):** 조건·대상을 늘 서버 값(`outline.auto`·`section_gens`)으로 계산하므로 보고서 화면을 다시 열면 남은 절부터 넣는다. 이 컴포저블은 ProposalStep 이 살아 있는 동안만 돈다 — 다른 단계 화면에서는 넣지 않는다. scope 가 끝나면(`onScopeDispose` — 컴포넌트가 내려가면) 다음 키·다시 읽기를 하지 않는다(보낸 요청 하나는 끝까지 간다).
- **단위 테스트를 한다** — 이 컴포저블은 Nuxt 자동 import(`$fetch`·`useRuntimeConfig`)를 쓰지 않고 `vue` 와 `utils` 만 import 한다(`useReadingSaves.test.ts` 와 같은 꼴 — 요청·다시 읽기를 손으로 끝내는 Deferred). `onScopeDispose` 는 `effectScope()` 안에서 부른다(테스트도 `scope.run` → `scope.stop`). 06b 의 'composable 은 단위 테스트하지 않는다'는 Nuxt 자동 import 를 쓰는 `useResearchWork` 의 말이다.

**Files:**
- Create: `frontend/composables/useAutoReport.ts`
- Test (Create): `frontend/tests/unit/useAutoReport.test.ts`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

새 파일 `frontend/tests/unit/useAutoReport.test.ts` 전체:

```ts
// frontend/tests/unit/useAutoReport.test.ts
import { describe, expect, it } from "vitest";
import { effectScope, shallowRef } from "vue";
import { useAutoReport } from "~/composables/useAutoReport";
import type { GenKind, Outline, ProposalView, WorkGeneration, WorkView } from "~/types/work";

interface Deferred {
  resolve: () => void;
  reject: (err: unknown) => void;
}

function httpError(status: number, detail?: unknown): Error & { status: number } {
  return Object.assign(new Error(`HTTP ${status}`), { status, statusCode: status }, detail === undefined ? {} : { data: { detail } });
}

const NO_PAPERS = { code: "no_section_papers", message: "이 절에 넣을 논문이 없습니다" };

// 묶음 둘(prior.g1·prior.g2) + 연구 공백 — [보고서 만들기]의 반영이 자동 승인한 목차
function outline(over: Partial<Outline> = {}): Outline {
  return {
    topic: { id: 12, title: "세대 간 지지와 노인 우울", question: "q?" },
    basis: "concept",
    groups: [
      { key: "prior.g1", name: "노인의 우울", hint: "노인 우울", papers: ["KCI_A"] },
      { key: "prior.g2", name: "세대 간 지지", hint: "사회적 지지", papers: ["KCI_B"] },
    ],
    questions: ["a?"],
    question: "a?",
    method: "",
    state: "approved",
    gen_id: 41,
    approved_at: "2026-10-17T01:00:00Z",
    auto: true,
    ...over,
  };
}

function proposal(over: Partial<ProposalView> = {}): ProposalView {
  return {
    version: 3,
    outline: outline(),
    sections: {},
    drafts: {},
    papers: {},
    references: {},
    corpus: null,
    stale: { outline: false, sections: {} },
    disclosure: { steps: [] },
    section_gens: {},
    ...over,
  };
}

function work(over: Partial<WorkView> = {}): WorkView {
  return {
    id: "job",
    phase: "proposal",
    concepts: [],
    memo: null,
    is_example: false,
    progress: {},
    generations: [],
    ...over,
  };
}

function gen(id: number, kind: GenKind, target: string, status: WorkGeneration["status"]): WorkGeneration {
  return { id, kind, target, status, model: null, error: null, position: null };
}

// 절 쓰기 요청(POST)·다시 읽기를 하나씩 손으로 끝낸다 — 기록(log)으로 보낸 차례를 본다
function setup(p: ProposalView | null = proposal(), w: WorkView | null = work()) {
  const log: string[] = [];
  const posts: Deferred[] = [];
  const reloads: Deferred[] = [];
  const proposalRef = shallowRef<ProposalView | null>(p);
  const workRef = shallowRef<WorkView | null>(w);
  const scope = effectScope();
  const auto = scope.run(() =>
    useAutoReport({
      proposal: proposalRef,
      work: workRef,
      generate: (key: string) => {
        log.push(`POST ${key}`);
        return new Promise<void>((resolve, reject) => posts.push({ resolve, reject }));
      },
      reload: () => {
        log.push("GET");
        return new Promise<void>((resolve) => reloads.push({ resolve, reject: () => {} }));
      },
    }),
  )!;
  return { auto, log, posts, reloads, proposalRef, workRef, scope };
}

// 루프의 다음 단계·watch 가 돌 만큼 마이크로태스크를 비운다
async function flush(): Promise<void> {
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
}

describe("useAutoReport — 남은 절을 하나씩 넣는다", () => {
  it("앞 요청의 응답을 받은 뒤 다음 키를 문서 순서로 넣는다 — 생성이 끝나기는 기다리지 않는다", async () => {
    const { auto, log, posts } = setup();
    await flush();
    expect(log).toEqual(["POST prior.g1"]);
    expect(auto.running.value).toBe(true);
    posts[0]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2"]);
    posts[1]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap"]);
  });

  it("근거 없음(409 code)은 skipped 에 넣고 다음 키로 간다", async () => {
    const { auto, log, posts } = setup();
    posts[0]!.resolve();
    await flush();
    posts[1]!.reject(httpError(409, NO_PAPERS));
    await flush();
    expect([...auto.skipped.value]).toEqual(["prior.g2"]);
    expect(auto.stopped.value).toBeNull();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap"]);
  });

  it("409 절 쓰는 중·500·네트워크 오류면 다음 키를 넣지 않고 멈춘 까닭을 남긴다", async () => {
    const cases: [unknown, string][] = [
      [httpError(409, "이 절을 쓰는 중입니다"), "이 절을 쓰는 중입니다"],
      [httpError(500), "보고서를 이어 쓰지 못했습니다"],
      [new TypeError("Failed to fetch"), "보고서를 이어 쓰지 못했습니다 — 네트워크 연결을 확인하세요"],
    ];
    for (const [err, message] of cases) {
      const { auto, log, posts, reloads } = setup();
      posts[0]!.reject(err);
      await flush();
      expect(auto.stopped.value).toBe(message);
      // 멈춰도 다시 읽기는 한 번 — 그사이 바뀐 서버 상태로 화면을 맞춘다
      expect(log).toEqual(["POST prior.g1", "GET"]);
      reloads[0]!.resolve();
      await flush();
      expect(auto.running.value).toBe(false);
      expect(log).toEqual(["POST prior.g1", "GET"]);
    }
  });

  it("resume 은 멈춤을 풀고 같은 조건으로 다시 돈다 — 멈춘 키부터", async () => {
    const { auto, log, posts, reloads } = setup();
    posts[0]!.reject(httpError(500));
    await flush();
    reloads[0]!.resolve();
    await flush();
    auto.resume();
    expect(auto.stopped.value).toBeNull();
    await flush();
    expect(log).toEqual(["POST prior.g1", "GET", "POST prior.g1"]);
    expect(auto.running.value).toBe(true);
  });

  it("auto 없음·예시·초안·목차를 다시 만드는 중·조회 전이면 부르지 않고, 조건이 서면 그때 돈다", async () => {
    const before06e: Outline = outline();
    delete before06e.auto;
    const cases: [ProposalView | null, WorkView | null][] = [
      [proposal({ outline: before06e }), work()],
      [proposal(), work({ is_example: true })],
      [proposal({ outline: outline({ state: "draft", approved_at: null }) }), work()],
      [proposal(), work({ generations: [gen(40, "outline", "outline", "queued")] })],
      [null, work()],
    ];
    for (const [p, w] of cases) {
      const { auto, log } = setup(p, w);
      await flush();
      expect(log).toEqual([]);
      expect(auto.running.value).toBe(false);
    }
    // 목차 생성이 끝나 계획서를 다시 읽으면(자동 승인 목차가 들어오면) 그때 돈다 — 탭을 닫았다 와도 같은 조건
    const { log, proposalRef } = setup(null, work());
    proposalRef.value = proposal();
    await flush();
    expect(log).toEqual(["POST prior.g1"]);
  });

  it("넣을 키가 다 끝나면 다시 읽기를 한 번 — 다시 읽은 뒤 남은 절이 없으면 더 넣지 않는다", async () => {
    const { auto, log, posts, reloads, proposalRef } = setup();
    for (let i = 0; i < 3; i += 1) {
      posts[i]!.resolve();
      await flush();
    }
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap", "GET"]);
    expect(auto.running.value).toBe(true);
    // 다시 읽은 계획서에는 세 키의 생성 기록이 있다
    proposalRef.value = proposal({
      section_gens: {
        "prior.g1": { gen_id: 51, status: "queued" },
        "prior.g2": { gen_id: 52, status: "queued" },
        gap: { gen_id: 53, status: "queued" },
      },
    });
    reloads[0]!.resolve();
    await flush();
    expect(auto.running.value).toBe(false);
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap", "GET"]);
  });

  it("다시 읽기 전에도 넣은 키를 또 넣지 않는다", async () => {
    const { log, posts, reloads, workRef } = setup();
    for (let i = 0; i < 3; i += 1) {
      posts[i]!.resolve();
      await flush();
    }
    // 다시 읽기를 기다리는 동안 이벤트로 연구가 바뀌어 watch 가 불려도 새 루프를 열지 않는다
    workRef.value = work({ progress: { sections: 0 } });
    await flush();
    // 다시 읽은 계획서가 아직 생성 기록을 싣지 못했어도(옛 값 그대로) 이 방문에서 넣은 키는 다시 넣지 않는다
    reloads[0]!.resolve();
    await flush();
    workRef.value = work({ progress: { sections: 1 } });
    await flush();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "POST gap", "GET"]);
  });

  it("생성 목록에 그 키의 절 생성이 있으면(손으로 [이 절 쓰기]) 계획서를 다시 읽기 전이라도 넣지 않는다", async () => {
    const { log, posts, workRef } = setup();
    // 사용자가 연구 공백을 손으로 쓰기 시작했다 — 이벤트로 생성 목록에 먼저 들어온다
    workRef.value = work({ generations: [gen(60, "section", "gap", "queued")] });
    posts[0]!.resolve();
    await flush();
    posts[1]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "GET"]);
  });

  it("scope 가 끝나면(화면을 떠나면) 다음 키도 다시 읽기도 하지 않는다", async () => {
    const { log, posts, scope } = setup();
    scope.stop();
    posts[0]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1"]);
  });

  it("목차를 새로 만들면(gen_id 가 바뀌면) 건너뜀·멈춤을 비우고 새 목차로 처음부터 같은 조건으로 돈다", async () => {
    const { auto, log, posts, reloads, proposalRef } = setup();
    posts[0]!.reject(httpError(409, NO_PAPERS));
    await flush();
    posts[1]!.reject(httpError(500));
    await flush();
    reloads[0]!.resolve();
    await flush();
    expect([...auto.skipped.value]).toEqual(["prior.g1"]);
    expect(auto.stopped.value).toBe("보고서를 이어 쓰지 못했습니다");
    // [보고서 다시 만들기] — 새 반영이 묶음을 다시 나눈 목차(gen_id 42)를 다시 읽었다
    proposalRef.value = proposal({ outline: outline({ gen_id: 42 }) });
    await flush();
    expect(auto.skipped.value.size).toBe(0);
    expect(auto.stopped.value).toBeNull();
    expect(log).toEqual(["POST prior.g1", "POST prior.g2", "GET", "POST prior.g1"]);
  });

  it("도는 동안 들어온 변화(새 목차)는 루프가 끝난 뒤 다시 본다", async () => {
    const { log, posts, reloads, proposalRef, workRef } = setup();
    // 첫 절을 넣는 사이 [보고서 다시 만들기]를 눌렀다 — 목차 생성이 열리면 연쇄는 다음 키를 넣지 않는다
    workRef.value = work({ generations: [gen(43, "outline", "outline", "queued")] });
    posts[0]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "GET"]);
    // 다시 읽기를 기다리는 사이 새 목차가 반영됐다 — 그때의 watch 는 도는 중이라 막힌다
    workRef.value = work({ generations: [gen(43, "outline", "outline", "done")] });
    proposalRef.value = proposal({
      outline: outline({ gen_id: 43 }),
      section_gens: { "prior.g1": { gen_id: 51, status: "queued" } },
    });
    await flush();
    expect(log).toEqual(["POST prior.g1", "GET"]);
    reloads[0]!.resolve();
    await flush();
    expect(log).toEqual(["POST prior.g1", "GET", "POST prior.g2"]);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/useAutoReport.test.ts`

Expected: `Test Files  1 failed (1)` / `Tests  no tests` — `Error: Cannot find module '~/composables/useAutoReport' imported from '…/tests/unit/useAutoReport.test.ts'`(파일이 아직 없다)

- [ ] **Step 3: 컴포저블을 쓴다**

새 파일 `frontend/composables/useAutoReport.ts` 전체:

```ts
// frontend/composables/useAutoReport.ts
// 보고서 자동 산출의 절 연쇄(06e D20, spec §12-4) — [보고서 만들기]의 반영이 자동 승인한 목차에서 남은 절을 문서 순서대로
// 하나씩 넣는다. 원문 대목 고르기(리랭커·Milvus)는 FastAPI 에만 있어 워커가 목차 뒤에 절 생성을 이어 넣을 수 없다(함정 17).
// 앞 POST 의 응답(gen_id)을 받으면 다음 키를 넣고, 생성이 끝나기는 기다리지 않는다(실행 순서는 디스패처). 조건·대상은 늘
// 서버 값(목차 auto·section_gens)으로 다시 계산한다 — 탭을 닫았다 와서 보고서 화면을 열면 남은 절부터 잇는다(06e 정함 6 —
// 보고서 화면(ProposalStep)이 살아 있는 동안만 돈다). 판정은 utils/proposalView.ts 의 순수 함수다
import { getCurrentScope, onScopeDispose, ref, shallowRef, watch, type Ref } from "vue";
import type { ProposalView, WorkView } from "~/types/work";
import { autoChainOn, isNoSectionPapers, nextAutoSection } from "~/utils/proposalView";
import { workErrorMessage } from "~/utils/researchErrors";

export interface AutoReportDeps {
  proposal: Readonly<Ref<ProposalView | null>>;
  work: Readonly<Ref<WorkView | null>>;
  // 절 하나의 생성을 넣는다(POST …/sections/{key}/generate)
  generate: (key: string) => Promise<unknown>;
  // 계획서·연구를 다시 읽는다 — 조회 오류는 useResearchWork 의 errorOf 가 맡는다
  reload: () => Promise<void>;
}

export interface AutoReportHandle {
  running: Readonly<Ref<boolean>>;
  // 멈춘 까닭(workErrorMessage) — null 이면 멈추지 않았다. 화면은 [이어서 쓰기]를 보인다
  stopped: Readonly<Ref<string | null>>;
  // 409 no_section_papers 로 건너뛴 절 키(이 방문만 — 생성 기록이 남지 않아 그 방문에서는 다시 넣지 않는다)
  skipped: Readonly<Ref<ReadonlySet<string>>>;
  // [이어서 쓰기] — 멈춤을 풀고 같은 조건으로 다시 돈다
  resume: () => void;
}

const STOP_FALLBACK = "보고서를 이어 쓰지 못했습니다";

export function useAutoReport(deps: AutoReportDeps): AutoReportHandle {
  const running = ref(false);
  const stopped = ref<string | null>(null);
  const skipped = shallowRef<ReadonlySet<string>>(new Set());
  // 이 방문에서 생성을 넣은 키 — 다시 읽기 전(계획서의 section_gens 가 아직 옛 값)에도 같은 키를 또 넣지 않는다
  let requested = new Set<string>();
  let disposed = false;

  // 다음에 넣을 절. 연구의 생성 목록(이벤트로 계획서보다 먼저 바뀐다)에 절 생성이 있는 키도 뺀다 — 손으로 [이 절 쓰기]를
  // 눌렀거나 다른 탭이 넣은 절을 또 넣으면 409(이 절을 쓰는 중)로 연쇄가 멈춘다
  function next(): string | null {
    const p = deps.proposal.value;
    const w = deps.work.value;
    if (disposed || stopped.value !== null || !p || !autoChainOn(p, w)) return null;
    const skip = new Set<string>([...skipped.value, ...requested]);
    for (const g of w?.generations ?? []) if (g.kind === "section" && g.target) skip.add(g.target);
    return nextAutoSection(p, skip);
  }

  async function run(): Promise<void> {
    running.value = true;
    try {
      for (let key = next(); key !== null; key = next()) {
        try {
          await deps.generate(key);
          requested.add(key);
        } catch (e) {
          if (!isNoSectionPapers(e)) {
            // 그 밖의 4xx(쓰는 중·승인 전 등)·5xx·네트워크 — 멈추고 [이어서 쓰기]
            stopped.value = workErrorMessage(e, STOP_FALLBACK);
            break;
          }
          // 그 절에 넣을 논문이 없다 — 그 절만 '근거가 없어 쓰지 않았습니다' 를 보이고 다음 키로
          skipped.value = new Set([...skipped.value, key]);
        }
      }
      // 넣은 생성(대기 순번)과 생성 기록(section_gens)을 한 번에 맞춘다
      if (!disposed) await deps.reload().catch(() => undefined);
    } finally {
      running.value = false;
    }
    // 도는 동안의 watch 는 running 에 막혔다 — 그사이 들어온 변화로 남은 절이 생겼으면 다시 돈다
    kick();
  }

  function kick(): void {
    if (running.value || next() === null) return;
    void run();
  }

  function resume(): void {
    stopped.value = null;
    kick();
  }

  // 목차를 새로 만들면([보고서 다시 만들기] — 새 반영이라 gen_id 가 바뀐다) 이 방문의 건너뜀·멈춤·넣은 키를 비우고 새 목차로
  // 처음부터 같은 조건으로 돈다 — 묶음을 다시 나눠 근거가 생겼을 수 있다. 이미 넣은 키는 새 계획서의 생성 기록이 막는다
  watch(
    () => deps.proposal.value?.outline?.gen_id ?? null,
    (now, was) => {
      if (was === null || now === was) return;
      skipped.value = new Set();
      stopped.value = null;
      requested = new Set();
      kick();
    },
  );
  watch([() => deps.proposal.value, () => deps.work.value], () => kick(), { immediate: true });

  if (getCurrentScope()) {
    onScopeDispose(() => {
      disposed = true;
    });
  }

  return { running, stopped, skipped, resume };
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/useAutoReport.test.ts`

Expected: `Test Files  1 passed (1)` / `Tests  11 passed (11)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`

Expected: 실패 0 — `Test Files` Task 앞 + 1, `Tests` Task 앞 + 11

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`

Expected: `0`

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/composables/useAutoReport.ts frontend/tests/unit/useAutoReport.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 보고서 자동 산출의 절 연쇄(useAutoReport). 자동 승인 목차에서 절도 생성 기록도 없는 키를 문서 순서대로 하나씩 넣는다 — 앞 POST 의 응답을 받으면 다음 키, 생성 완료는 기다리지 않는다. 근거 없음 409(no_section_papers)는 그 절만 건너뛰고, 그 밖의 4xx·5xx·네트워크 오류면 멈추고 까닭을 남긴다([이어서 쓰기] = resume). 끝나면 다시 읽기 한 번. 조건은 늘 서버 값으로 다시 계산해 탭을 닫았다 와도 남은 절부터 잇고, 생성 목록에 이미 있는 절(손으로 쓴 절)은 넣지 않으며, 목차를 새로 만들면 건너뜀·멈춤을 비운다. 화면을 떠나면 다음 키를 넣지 않는다"
```

---

### Task A5: 보고서 화면 — 큰 진행 막대·머리 목차·문서 자리 1~6·[보고서 만들기]

spec §12-4 '누르는 것'·'화면'(목차가 문서의 머리 목차, 절 자리 상태 재사용 `ProposalSection.vue:24-72`, 문구 두 곳 `ProposalStep.vue:56`·`ProposalSection.vue:195-197`)·'선택 기능(지우지 않는다)'·'[목차 만들기]→[보고서 만들기]', 뼈대 정함 4, 사용자 Q1 답의 큰 진행 막대(정함 28 — 그리기. 10-11 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아"). Task A3 의 판정과 Task A4 의 연쇄를 화면에 잇는다.

**알아 둘 것:**
- **누르는 것:** 참고문헌 화면(ReadingStep)의 [목차 만들기]·[목차 다시 만들기]와 보고서 화면(ProposalStep)의 '아직 목차가 없습니다' 카드 버튼·[목차 다시 만들기]를 `MAKE_REPORT`·`REMAKE_REPORT`(Task A3)로. 담음 5편 조건(`canOutline` — `readingList.canMakeOutline`)·부르는 API(`POST …/outline`)는 그대로다 — 한 번 누르면 목차 생성 → 반영이 자동 승인(Task A1) → 보고서 화면이 열려 있으면 절 연쇄(Task A4)가 남은 절을 넣는다.
- **확인 창(정함 4):** [보고서 다시 만들기]는 새 반영이라 목차·질문·방법·승인을 통째로 바꾸고 `auto` 가 다시 붙지만, 연쇄의 대상은 '절도 생성 기록도 없는 키'라 이미 쓴 절은 다시 쓰지 않는다 — 두 화면의 `REMAKE_CONFIRM` 이 같은 글로 이것을 적는다. 반영이 방법을 빈칸으로 되돌리므로(Task A1) 읽기 화면의 확인 창에도 '방법'을 넣는다(뼈대 Task A5 의 ReadingStep 문구에 '방법'을 더하고 두 곳을 바로잡은 것 — 파트 메모 8). '다시 맞춤 필요'는 늘 붙지 않는다 — `stale_flags`(`proposal_views.py:36-53`)는 주제가 바뀌면 모든 절(`basis.topic_id` 비교 :49), 묶음 논문이 바뀌면 그 선행연구 절(:50-51)에 붙이므로 '주제나 묶음이 바뀐 절에는 붙습니다'로 적는다. 연쇄가 쓰는 것은 '새로 생긴 절'이 아니라 '아직 쓰지 않은 절'(절도 생성 기록도 없는 키)이다 — 06b 때 일부만 쓴 목차를 다시 만들면 쓰지 않은 기존 키도 자동으로 쓴다.
- **보고서 화면의 차례(승인 목차):** ① 큰 진행 막대(`reportBar` 가 null 이 아닐 때만) ② 연쇄가 멈췄고 남은 절이 있으면 까닭과 [이어서 쓰기] ③ 머리 목차(`docToc` — 머리에 [목차 고치기] 토글) ④ [목차 고치기]를 펴면 `OutlineEditor`(지금의 편집·If-Match 승인 흐름 그대로 — 지우지 않는다) ⑤ AI 기여 미터와 안내(:55-57 문구 — `outline.auto` 로 자동 산출 안내와 손으로 쓰는 안내를 가른다) ⑥ 문서 자리 — `wk-doc-topic`(1)·`wk-doc-background`(2)·ProposalSection(3.n·4 — 기존 `wk-sec-<key>`)·`wk-doc-question`(5)·`wk-doc-method`(6) ⑦ 내려받기 카드(그대로 — 파트 X 의 Task X5 가 고친다). 자리 id·`h3 tabindex="-1"` 은 뼈대 1-7 표 그대로다(Task A3 테스트가 anchor 를 글자로 고정). 2·6 자리는 이 Task 에서 글 또는 흐린 안내만 그리고 Task X3 이 DocField 로 바꾼다.
- **[목차 고치기]:** 승인 목차는 편집기를 접어 둔 채 시작하고(자동 확정이 기본), 초안 목차(06b 목차·질문이 없어 자동 승인하지 못한 목차)는 승인하러 편집기를 늘 편다 — `editorShown = !approved || outlineOpen`. 초안 목차를 편집기의 [목차 승인]으로 승인하면 `approved` 가 참이 되어 그대로는 편집기가 곧바로 내려가므로, `saveOutline` 이 승인(`body.approve`)이면 `outlineOpen` 을 먼저 참으로 둔다 — 06b 처럼 고치던 목차가 그 자리에서 '승인함'으로 바뀐다(뼈대의 'outlineOpen 처음 값 = state !== approved' 가 노린 효과. 처음 값으로 정하면 계획서를 읽기 전에 화면이 설 때 참이 되어 승인 목차도 펴진 채 시작한다 — 파트 메모 7). 예시 연구는 버튼 글이 '목차 자세히 보기'다(편집기가 읽기 전용으로 그린다).
- **큰 진행 막대(정함 28):** 두께 토큰 `--wk-bar-thick: 1rem`(768px 이하 0.75rem)을 `.wk-rbar` 에 둔다 — 06d `research.css` 의 `--rs-bar-thick` 와 값만 같고 import 하지 않는다(06d 파일). 막대 위 큰 글줄 1rem 굵게(`보고서 작성 중 · 2/3절 — 「선행연구 검토 · 세대 간 지지」`), 오른쪽 끝 퍼센트 1.25rem 굵게, 쓰는 중이면 채움에 빛이 흐른다(`is-running`, reduced-motion 이면 멈춤 — 빛 색은 새 색값 없이 `color-mix(in srgb, var(--skx-white) 35%, transparent)`, `research.css:801` 의 `.rs-synth__fill.is-running` 선례와 같은 꼴이라 Task Z2 의 '더한 줄의 색값 0' 검사를 지킨다). 단계 칩은 두지 않는다 — 같은 화면 위 WorkStepper 가 단계 표시다. `role="progressbar"` 의 `aria-valuetext` 가 글줄을 읽으므로 따로 `role="status"` 줄을 두지 않는다. 절 자리가 아래로 쌓이며 흐르는 동안 화면 위에 붙어 있게 `position: sticky; top: 0.5rem`(같은 파일 `.wk-pill` 선례) — 머리 목차로 옮겨 간 자리가 막대에 가리지 않게 자리마다 `scroll-margin-top: 6rem`. 연쇄가 오류로 멈추면 넷째 인자(`stopped`)로 남은 절을 세지 않아, 쓰는 절이 없으면 막대가 걷히고 [이어서 쓰기] 줄만 남는다. 인쇄에서는 뺀다.
- **절 자리 제목에 번호:** ProposalSection 의 `label` 을 머리 목차 번호를 붙인 글(`3.1 선행연구 검토 · 노인의 우울`·`4. 연구 공백`)로 넘긴다 — 문서 자리 1·2·5·6 의 `1. 주제` 꼴과 Word 의 절 번호에 맞춘다. 문단 버튼의 화면낭독 이름(`paraName` — `${label} n번째 문단`)도 이 글을 쓴다.
- **ProposalSection:** `h3` 에 `tabindex="-1"`(머리 목차가 초점을 옮긴다), prop 둘 — `skipped?: boolean`(쓰기 전 절이 건너뛴 절이면 배지 '근거 없음'과 `role="status"` 안내), `autoNext?: boolean`(연쇄가 이 절을 곧 넣을 참). :195-197 의 쓰기 전 안내는 셋으로 가른다 — 건너뜀 → 근거 없음 안내, `autoNext` → '차례가 오면 자동으로 씁니다', 그 밖 → [이 절 쓰기]를 누르라는 안내. '자동으로 씁니다'를 조건 없이 그리면 연쇄가 돌지 않는 쓰기 전 절에서도 그렇게 알린다 — 06b 때 승인한 목차(`auto` 없음 — 운영에 실제 연구가 있다, `round06b-완료노트.md` §5-3), 생성 기록이 있는 쓰기 전 키(취소로 끝났거나 WorkView 최근 10건 밖의 빈 결과 — `autoTargets` 는 빼지만 `sectionStatus` 는 'empty', `proposalView.ts:60-66`), 연쇄가 멈춘 동안. 근거 없음 409 는 사실상 연구 공백 절에서만 난다 — 선행연구 묶음은 비지 않고(`assign_groups` 는 논문이 있는 키만 고른다 `membership.py:119-127`, PUT 은 빈 묶음을 `EMPTY_GROUP` 으로 막는다 `research_proposal.py:227-228`), 연구 공백의 논문은 고른 주제의 씨앗(`gap_seeds(topic.seed, job.report)` — `section_input.py:34-47`, `research_proposal.py:393`)에서 온다. 그래서 건너뛴 절 안내는 담은 논문·묶음을 바꾸라고 하지 않고 다른 주제를 고른 뒤 [보고서 다시 만들기]로 맞추라고 한다. 상태 모양(대기·쓰는 중·스트리밍 글·실패 — :24-72)은 그대로 재사용한다(spec).
- **연쇄 연결:** `useAutoReport({ proposal, work: workView, generate: (k) => api.generateSection(props.jobId, k), reload })` — reload 는 계획서·연구를 함께 다시 읽고 사이드바 기록을 새로 고친다(`afterAction` — 다른 쓰기 동작과 같다). 손으로 누르는 [이 절 쓰기]·[다시]·[수락] 등은 그대로 `act()` 를 탄다. 연쇄가 아직 넣을 절 `autoLeft`(연쇄가 돌 때 `autoTargets` 에서 건너뛴 키를 뺀 것)를 두 곳이 읽는다 — 절 자리의 `autoNext`(멈춘 동안은 빈 집합 — [이어서 쓰기]를 눌러야 쓴다)와 멈춘 줄(`autoStopped && autoLeft.length`). `stopped` 는 `resume()`·목차 `gen_id` 가 바뀔 때만 비워지므로, 멈춘 뒤 남은 절을 손으로 다 쓰면 할 일이 없는 경고와 [이어서 쓰기]가 남는다 — useAutoReport(Task A4)의 계약·테스트는 그대로 두고 화면에서 가린다.
- **고치지 않는 것(같은 파일을 뒤 Task 가 고친다):** ProposalStep 의 제목(:6)·'불러오는 중'(:19)·:29-32 안내·[읽기 목록으로](:35)·`CONFLICT`(:120)·`remakeWhy`(:147)는 Task R1, 내려받기 카드(:75-94)·`downloadWord` 는 Task X5, ReadingStep 의 :6·:8-9·:12·:25·:48·:51 은 Task R1 이 고친다 — 이 Task 의 old 블록은 그 줄을 글자 그대로 둔다.
- `.vue` 는 단위 테스트하지 않는다 — `nuxi typecheck` 오류 0·`npm run build` 완료·vitest 전체 그대로로 확인하고, 브라우저 확인은 마무리 운영 확인에 넘긴다(아래 Step 5).
- 네 파일 모두 CRLF — Edit 도구로 고친다.

**Files:**
- Modify: `frontend/components/work/ReadingStep.vue` (:56-58 [목차 다시 만들기], :66-68 [목차 만들기], script import :85-86, script 머리 주석 :89, `REMAKE_CONFIRM` :93-95, `makeOutline` 오류 문구 :156)
- Modify: `frontend/components/work/ProposalStep.vue` (:33-34 버튼, :44-73 승인 목차 자리, `REMAKE_CONFIRM` :121-123, script import :102-115, `remakeWhy` :145-149 아래, `makeOutline` :194-201, `saveOutline` :203-205)
- Modify: `frontend/components/work/ProposalSection.vue` (:3-6 머리, :195-197 안내, props :229-237, `stale` :264 아래)
- Modify: `frontend/assets/css/work.css` (끝 표시 줄 :1231 위)

- [ ] **Step 1: 읽기 화면(ReadingStep)의 버튼·확인 창·오류 문구**

`frontend/components/work/ReadingStep.vue` — [목차 다시 만들기]. old:

```vue
            @click="makeOutline(true)"
          >
            목차 다시 만들기
          </button>
```

new:

```vue
            @click="makeOutline(true)"
          >
            {{ REMAKE_REPORT }}
          </button>
```

같은 파일 — [목차 만들기]. old:

```vue
          @click="makeOutline(false)"
        >
          목차 만들기
        </button>
```

new:

```vue
          @click="makeOutline(false)"
        >
          {{ MAKE_REPORT }}
        </button>
```

같은 파일 — import 에 버튼 이름. old:

```ts
import { canMakeOutline, outlineHint } from "~/utils/readingList";
import { httpStatus, workErrorMessage } from "~/utils/researchErrors";
```

new:

```ts
import { canMakeOutline, outlineHint } from "~/utils/readingList";
import { httpStatus, workErrorMessage } from "~/utils/researchErrors";
import { MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";
```

같은 파일 — script 머리 주석의 버튼 이름(다른 파트는 주석을 고치지 않는다 — 여기서 고치지 않으면 옛 이름이 남는다). old:

```ts
// 담음 5편 이상이면 [목차 만들기] → POST .../outline 뒤 계획서 단계로 간다
```

new:

```ts
// 담음 5편 이상이면 [보고서 만들기] → POST .../outline 뒤 마지막 단계로 간다(반영이 목차를 자동 확정하고 그 화면이 절을 차례로
// 넣는다 — 06e D20)
```

같은 파일 — 확인 창(정함 4). old:

```ts
// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 바꾼다 — 다시 만들기 전에 묻는다
const REMAKE_CONFIRM =
  "목차를 다시 만들면 지금 목차(묶음 이름·연구 질문·승인)가 새로 만든 목차로 바뀝니다. 계속할까요?";
```

new:

```ts
// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 바꾼다 — 다시 만들기 전에 묻는다. 새 반영은 다시 자동 승인하지만
// 절 연쇄는 절도 생성 기록도 없는 키만 쓴다 — 이미 쓴 절은 다시 쓰지 않는다(06e 정함 4)
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다. 이미 쓴 절은 지우지 않고(주제나 묶음이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";
```

같은 파일 — 오류 문구. old:

```ts
    error.value = workErrorMessage(err, "목차를 만들지 못했습니다");
```

new:

```ts
    error.value = workErrorMessage(err, "보고서를 만들지 못했습니다");
```

- [ ] **Step 2: 보고서 화면(ProposalStep) — 막대·머리 목차·문서 자리·연쇄**

`frontend/components/work/ProposalStep.vue` — '아직 목차가 없습니다' 카드의 버튼. old:

```vue
        <div v-if="!readOnly" class="rs-card__actions">
          <button type="button" class="rs-btn" :disabled="busy" @click="makeOutline">목차 만들기</button>
```

new:

```vue
        <div v-if="!readOnly" class="rs-card__actions">
          <button type="button" class="rs-btn" :disabled="busy" @click="makeOutline">{{ MAKE_REPORT }}</button>
```

같은 파일 — 승인 목차 자리(:44-73)를 막대·머리 목차·접는 편집기·문서 자리로. 내려받기 카드(:75-94)와 그 뒤는 그대로다. old:

```vue
      <div v-else-if="canRemake" class="wk-proposal__remake">
        <p class="rs-muted">{{ remakeWhy }}</p>
        <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="makeOutline">
          목차 다시 만들기
        </button>
      </div>
      <OutlineEditor :proposal="proposal" :read-only="readOnly" :busy="busy || !!outlineGen" @save="saveOutline" />

      <template v-if="approved">
        <div class="rs-card wk-proposal__intro">
          <AiFootprintMeter :proposal="proposal" />
          <p class="rs-muted">
            절마다 [이 절 쓰기]를 누르세요. 선행연구 검토는 묶음마다 씁니다 — 모든 절을 한 번에 쓰는 버튼은 없습니다.
          </p>
        </div>
        <ProposalSection
          v-for="key in writableKeys"
          :key="key"
          :section-key="key"
          :label="sectionLabel(key, proposal.outline)"
          :proposal="proposal"
          :state="state"
          :read-only="readOnly"
          :busy="busy"
          :job-id="jobId"
          @write="write(key)"
          @save="saveSection(key, $event)"
          @regenerate="regenerate(key, $event)"
          @retry="retry"
        />
```

new:

```vue
      <div v-else-if="canRemake" class="wk-proposal__remake">
        <p class="rs-muted">{{ remakeWhy }}</p>
        <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="makeOutline">
          {{ REMAKE_REPORT }}
        </button>
      </div>

      <template v-if="approved">
        <!-- 큰 진행 막대(06e 정함 28) — 절을 차례로 쓰는 동안만 서고 다 쓰면 걷힌다. 글줄·퍼센트는 valuetext 로 읽힌다 -->
        <div
          v-if="bar"
          class="wk-rbar"
          role="progressbar"
          :aria-valuenow="bar.percent"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuetext="bar.label"
        >
          <p class="wk-rbar__line">{{ bar.label }}</p>
          <span class="wk-rbar__pct">{{ bar.percent }}%</span>
          <div class="wk-rbar__track">
            <div class="wk-rbar__fill" :class="{ 'is-running': bar.running }" :style="{ width: `${bar.percent}%` }" />
          </div>
        </div>
        <!-- 연쇄가 멈춘 줄 — 남은 절이 있을 때만(멈춘 뒤 남은 절을 손으로 다 쓰면 이어서 쓸 것이 없어 걷는다) -->
        <div v-if="autoStopped && autoLeft.length" class="rs-alert wk-doc__resume" role="alert">
          <p>{{ autoStopped }} — [이어서 쓰기]를 누르면 남은 절부터 다시 씁니다.</p>
          <button type="button" class="rs-btn rs-btn--small" :disabled="autoRunning" @click="resumeAuto">이어서 쓰기</button>
        </div>
        <nav class="rs-card wk-doc__toc" aria-labelledby="wk-doc-toc-title">
          <div class="wk-doc__toc-head">
            <h3 id="wk-doc-toc-title" class="rs-card__title">목차</h3>
            <button
              type="button"
              class="rs-btn rs-btn--small rs-btn--ghost"
              :aria-expanded="outlineOpen"
              :aria-controls="outlineOpen ? 'wk-outline-editor' : undefined"
              @click="outlineOpen = !outlineOpen"
            >
              {{ readOnly ? "목차 자세히 보기" : "목차 고치기" }}
            </button>
          </div>
          <ol class="wk-doc__toc-list">
            <li v-for="item in toc" :key="item.key">
              <button type="button" class="wk-doc__toc-item" :class="`is-${item.status}`" @click="goPart(item.anchor)">
                <span class="wk-doc__toc-no">{{ item.no }}</span>
                <span class="wk-doc__toc-label">{{ item.label }}</span>
                <span v-if="TOC_STATUS[item.status]" class="wk-doc__toc-status">{{ TOC_STATUS[item.status] }}</span>
              </button>
            </li>
          </ol>
        </nav>
      </template>
      <!-- [목차 고치기] — 승인 목차는 접어 두고, 초안 목차(06b·질문이 없어 자동 승인하지 못한 목차)는 승인하러 늘 편다 -->
      <div v-if="editorShown" id="wk-outline-editor">
        <OutlineEditor :proposal="proposal" :read-only="readOnly" :busy="busy || !!outlineGen" @save="saveOutline" />
      </div>

      <template v-if="approved">
        <div class="rs-card wk-proposal__intro">
          <AiFootprintMeter :proposal="proposal" />
          <!-- 절을 차례로 쓰는 것은 [보고서 만들기]가 자동 승인한 목차(auto)뿐 — 06b 때 승인했거나 초안을 손으로 승인한 목차는 손으로 쓴다 -->
          <p v-if="proposal.outline.auto" class="rs-muted">
            [보고서 만들기]로 목차가 서면 선행연구 묶음·연구 공백 절을 차례로 씁니다. 다 쓴 문단은 그대로 두어도 되고,
            [수락]·[다시]·[고치기]로 다듬을 수 있습니다.
          </p>
          <p v-else class="rs-muted">
            절마다 [이 절 쓰기]를 누르면 씁니다. 다 쓴 문단은 [수락]·[다시]·[고치기]로 다듬을 수 있습니다.
          </p>
        </div>
        <div class="wk-doc">
          <section id="wk-doc-topic" class="rs-card wk-doc__part" aria-labelledby="wk-doc-topic-title">
            <h3 id="wk-doc-topic-title" class="wk-doc__part-title" tabindex="-1">1. {{ SECTION_LABELS.topic }}</h3>
            <p class="wk-doc__text">{{ proposal.outline.topic.title }}</p>
          </section>
          <section id="wk-doc-background" class="rs-card wk-doc__part" aria-labelledby="wk-doc-background-title">
            <h3 id="wk-doc-background-title" class="wk-doc__part-title" tabindex="-1">2. {{ SECTION_LABELS.background }}</h3>
            <p v-if="background.trim()" class="wk-doc__text">{{ background }}</p>
            <p v-else class="rs-muted">연구 배경을 아직 적지 않았습니다.</p>
          </section>
          <ProposalSection
            v-for="key in writableKeys"
            :key="key"
            :section-key="key"
            :label="partLabel(key)"
            :proposal="proposal"
            :state="state"
            :read-only="readOnly"
            :busy="busy"
            :job-id="jobId"
            :skipped="autoSkipped.has(key)"
            :auto-next="autoNext.has(key)"
            @write="write(key)"
            @save="saveSection(key, $event)"
            @regenerate="regenerate(key, $event)"
            @retry="retry"
          />
          <section id="wk-doc-question" class="rs-card wk-doc__part" aria-labelledby="wk-doc-question-title">
            <h3 id="wk-doc-question-title" class="wk-doc__part-title" tabindex="-1">5. {{ SECTION_LABELS.question }}</h3>
            <p v-if="proposal.outline.question" class="wk-doc__text">{{ proposal.outline.question }}</p>
            <p v-else class="rs-muted">연구 질문을 아직 정하지 않았습니다 — [목차 고치기]에서 고르세요.</p>
          </section>
          <section id="wk-doc-method" class="rs-card wk-doc__part" aria-labelledby="wk-doc-method-title">
            <h3 id="wk-doc-method-title" class="wk-doc__part-title" tabindex="-1">6. {{ SECTION_LABELS.method }}</h3>
            <p v-if="proposal.outline.method.trim()" class="wk-doc__text">{{ proposal.outline.method }}</p>
            <p v-else class="rs-muted">방법을 아직 적지 않았습니다.</p>
          </section>
        </div>
```

같은 파일 — script import. old:

```ts
import ProposalSection from "~/components/work/ProposalSection.vue";
import { useReportExport } from "~/composables/useReportExport";
import { useWorkApi, type ResearchWorkHandle } from "~/composables/useResearchWork";
import type { OutlinePut, SectionPut, WorkStep } from "~/types/work";
import { isFallbackOutline } from "~/utils/outlineEdit";
import { buildProposalDocument, printedKeys, printedProposedCount } from "~/utils/proposalDocument";
import { sectionLabel } from "~/utils/proposalView";
import { genQueueLine } from "~/utils/queueLine";
import { httpStatus, versionConflict, workErrorMessage } from "~/utils/researchErrors";
import { openGeneration } from "~/utils/workEvents";
```

new:

```ts
import ProposalSection from "~/components/work/ProposalSection.vue";
import { useAutoReport } from "~/composables/useAutoReport";
import { useReportExport } from "~/composables/useReportExport";
import { useWorkApi, type ResearchWorkHandle } from "~/composables/useResearchWork";
import type { OutlinePut, SectionPut, WorkStep } from "~/types/work";
import { isFallbackOutline } from "~/utils/outlineEdit";
import { buildProposalDocument, printedKeys, printedProposedCount } from "~/utils/proposalDocument";
import {
  SECTION_LABELS,
  autoChainOn,
  autoTargets,
  docToc,
  outlineBackground,
  reportBar,
  sectionLabel,
  type TocItem,
} from "~/utils/proposalView";
import { genQueueLine } from "~/utils/queueLine";
import { httpStatus, versionConflict, workErrorMessage } from "~/utils/researchErrors";
import { openGeneration } from "~/utils/workEvents";
import { MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";
```

같은 파일 — 확인 창(정함 4 — ReadingStep 과 같은 글). old:

```ts
// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 덮는다(계약 보강 4) — 다시 만들기 전에 묻는다
const REMAKE_CONFIRM =
  "목차를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다. 쓴 절은 남지만 '다시 맞춤 필요'가 붙습니다. 계속할까요?";
```

new:

```ts
// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 덮는다(계약 보강 4) — 다시 만들기 전에 묻는다. 새 반영은 다시
// 자동 승인하지만 절 연쇄는 절도 생성 기록도 없는 키만 쓴다 — 이미 쓴 절은 다시 쓰지 않는다(06e 정함 4)
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다. 이미 쓴 절은 지우지 않고(주제나 묶음이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";
```

같은 파일 — `remakeWhy` 아래에 연쇄·막대·머리 목차·접는 편집기. old:

```ts
const remakeWhy = computed(() =>
  proposal.value?.stale.outline
    ? "주제나 읽기 목록이 바뀌었습니다 — 목차를 다시 만들면 지금 담은 논문으로 묶음을 새로 나눕니다(지금 목차를 바꿉니다)."
    : "모델이 목차 초안을 만들지 못했습니다 — 다시 만들어 볼 수 있습니다.",
);
```

new:

```ts
const remakeWhy = computed(() =>
  proposal.value?.stale.outline
    ? "주제나 읽기 목록이 바뀌었습니다 — 목차를 다시 만들면 지금 담은 논문으로 묶음을 새로 나눕니다(지금 목차를 바꿉니다)."
    : "모델이 목차 초안을 만들지 못했습니다 — 다시 만들어 볼 수 있습니다.",
);

// ── 보고서 자동 산출(06e D20) ─────────────────────────────
// [보고서 만들기]의 반영이 자동 승인한 목차에서 남은 절을 문서 순서대로 하나씩 넣는다 — 이 화면이 열려 있는 동안만 돌고,
// 조건은 서버 값으로 다시 계산해 탭을 닫았다 와도 남은 절부터 잇는다(useAutoReport, 정함 6)
const {
  running: autoRunning,
  stopped: autoStopped,
  skipped: autoSkipped,
  resume: resumeAuto,
} = useAutoReport({
  proposal,
  work: workView,
  generate: (key) => api.generateSection(props.jobId, key),
  reload: async () => {
    await Promise.all([props.work.reload("proposal"), props.work.reload("work")]);
    props.work.afterAction();
  },
});
// 연쇄가 아직 넣을 절 — 문서 순서에서 절도 생성 기록도 없고 근거가 없어 건너뛰지도 않은 키. 연쇄가 돌지 않는 목차(06b 때
// 승인한 목차·초안·예시 연구·목차를 다시 만드는 중)면 빈 목록이다. 멈춘 뒤 남은 절을 손으로 다 쓰면 비어 멈춘 줄이 걷힌다
// (useAutoReport 의 stopped 는 resume·새 목차에서만 비워진다)
const autoLeft = computed(() => {
  const p = proposal.value;
  return p && autoChainOn(p, workView.value) ? autoTargets(p).filter((k) => !autoSkipped.value.has(k)) : [];
});
// 쓰기 전 절 안내가 '차례가 오면 자동으로 씁니다' 를 말해도 되는 키 — 멈춘 동안은 [이어서 쓰기]를 눌러야 쓰므로 뺀다
const autoNext = computed(() => new Set<string>(autoStopped.value ? [] : autoLeft.value));
// 머리의 큰 진행 막대(정함 28) — 절이 끝날 때만 차오르고, 다 쓰면 걷힌다. 연쇄가 멈추면 쓰는 절이 있을 때만
const bar = computed(() =>
  proposal.value ? reportBar(proposal.value, state.value, autoSkipped.value, autoStopped.value !== null) : null,
);
// 머리 목차 — 문서 순서의 여섯 자리(anchor = 아래 자리 id)
const toc = computed(() => (proposal.value ? docToc(proposal.value, state.value, autoSkipped.value) : []));
const TOC_STATUS: Record<TocItem["status"], string> = {
  text: "",
  blank: "비어 있음",
  empty: "쓰기 전",
  queued: "대기 중",
  writing: "쓰는 중",
  done: "씀",
  failed: "실패",
  skipped: "근거 없음",
};
const background = computed(() => (proposal.value?.outline ? outlineBackground(proposal.value.outline) : ""));
// [목차 고치기] — 승인 목차는 편집기를 접어 둔 채 시작한다(자동 확정이 기본). 초안 목차는 승인하러 늘 펴고, 편집기에서
// 승인하면 saveOutline 이 outlineOpen 을 참으로 둬 편 채로 남는다
const outlineOpen = ref(false);
const editorShown = computed(() => !approved.value || outlineOpen.value);

// 절 자리 제목 — 머리 목차의 번호를 붙인다(3.1 선행연구 검토 · 묶음 이름, 4. 연구 공백 — Word 의 절 번호와 같다)
function partLabel(key: string): string {
  const label = sectionLabel(key, proposal.value?.outline ?? null);
  const no = toc.value.find((i) => i.key === key)?.no;
  if (!no) return label;
  return `${no.includes(".") ? no : `${no}.`} ${label}`;
}

// 머리 목차 항목 — 그 자리로 옮기고 자리 제목(h3 tabindex="-1")에 초점을 둔다(화면낭독기가 어디로 왔는지 읽는다)
function goPart(anchor: string): void {
  const el = document.getElementById(anchor);
  if (!el) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  el.querySelector<HTMLElement>("h3")?.focus({ preventScroll: true });
}
```

같은 파일 — `makeOutline` 의 실패 문구. old:

```ts
    await Promise.all([props.work.reload("work"), props.work.reload("proposal")]);
  }, "목차를 만들지 못했습니다");
}
```

new:

```ts
    await Promise.all([props.work.reload("work"), props.work.reload("proposal")]);
  }, "보고서를 만들지 못했습니다");
}
```

같은 파일 — `saveOutline` — 초안 목차를 편집기에서 승인해도 편집기를 접지 않는다(`editorShown` 은 `!approved || outlineOpen` 이라 승인 순간 내려간다). old:

```ts
function saveOutline(body: OutlinePut): void {
  const p = proposal.value;
  if (!p) return;
```

new:

```ts
function saveOutline(body: OutlinePut): void {
  const p = proposal.value;
  if (!p) return;
  // 초안 목차를 승인해도 편집기를 접지 않는다(editorShown) — 고치던 목차가 통째로 사라지지 않고 그 자리에서 '승인함'으로
  // 바뀐다(06b 와 같다). 접기는 머리 목차의 [목차 고치기] 토글로
  if (body.approve) outlineOpen.value = true;
```

- [ ] **Step 3: 절 자리(ProposalSection) — 초점·건너뛴 절·안내 문구**

`frontend/components/work/ProposalSection.vue` — 머리. old:

```vue
    <header class="wk-psec__head">
      <h3 :id="`wk-sec-title-${sectionKey}`" class="rs-card__title">{{ label }}</h3>
      <span class="rs-badge" :class="STATUS_BADGES[status]">{{ STATUS_LABELS[status] }}</span>
```

new:

```vue
    <header class="wk-psec__head">
      <!-- tabindex="-1" — 보고서 화면의 머리 목차가 이 제목으로 초점을 옮긴다 -->
      <h3 :id="`wk-sec-title-${sectionKey}`" class="rs-card__title" tabindex="-1">{{ label }}</h3>
      <span class="rs-badge" :class="STATUS_BADGES[status]">{{ skippedNow ? "근거 없음" : STATUS_LABELS[status] }}</span>
```

같은 파일 — 쓰기 전 안내(spec 문구 고치기) — 건너뜀·자동으로 쓸 절·그 밖을 셋으로 가른다. old:

```vue
    <p v-if="!section && status === 'empty'" class="rs-muted">
      아직 쓰지 않은 절입니다. [이 절 쓰기]를 누르면 문장이 흘러나오고, 끝나면 문단마다 [수락]·[다시]·[고치기]로 받아들입니다.
    </p>
```

new:

```vue
    <!-- 근거 없음 409 는 사실상 연구 공백 절에서만 난다 — 그 논문은 담은 논문·묶음이 아니라 고른 주제의 씨앗에서 온다 -->
    <p v-if="skippedNow" class="rs-muted" role="status">
      근거가 없어 쓰지 않았습니다 — 이 절은 고른 주제의 씨앗(딥리서치 보고서의 향후 과제·부족한 하위질문)에 이은 논문으로
      쓰는데, 이은 논문이 없습니다. 다른 주제를 고른 뒤 [보고서 다시 만들기]로 맞추세요.
    </p>
    <!-- '자동으로 씁니다'는 연쇄가 이 절을 곧 넣을 때만 — 06b 때 승인한 목차·취소로 끝난 절·연쇄가 멈춘 동안은 손으로 쓴다 -->
    <p v-else-if="!section && status === 'empty' && autoNext" class="rs-muted">
      아직 쓰지 않은 절입니다 — 차례가 오면 자동으로 씁니다. 지금 쓰려면 [이 절 쓰기]를 누르세요.
    </p>
    <p v-else-if="!section && status === 'empty'" class="rs-muted">
      아직 쓰지 않은 절입니다. [이 절 쓰기]를 누르면 문장이 흘러나오고, 끝나면 문단마다 [수락]·[다시]·[고치기]로 다듬을 수
      있습니다.
    </p>
```

같은 파일 — prop. old:

```ts
  readOnly: boolean;
  busy: boolean;
  jobId: string;
}>();
```

new:

```ts
  readOnly: boolean;
  busy: boolean;
  jobId: string;
  // 보고서 자동 산출이 근거가 없어(409 no_section_papers) 건너뛴 절 — 이 방문만(06e)
  skipped?: boolean;
  // 보고서 자동 산출이 이 절을 곧 넣을 참이다(연쇄가 돌고 멈추지 않았고 남은 절에 든다) — 쓰기 전 안내가 '자동으로 씁니다'
  autoNext?: boolean;
}>();
```

같은 파일 — `stale` 아래. old:

```ts
const stale = computed(() => !!section.value && props.proposal.stale.sections[props.sectionKey] === true);
```

new:

```ts
const stale = computed(() => !!section.value && props.proposal.stale.sections[props.sectionKey] === true);
// 자동 산출이 근거가 없어 건너뛴 쓰기 전 절 — 손으로 다시 쓰기 시작하면(대기·쓰는 중) 그 상태를 보인다
const skippedNow = computed(() => !!props.skipped && !section.value && status.value === "empty");
```

- [ ] **Step 4: 막대·머리 목차·문서 자리 스타일**

`frontend/assets/css/work.css` — 끝 표시 줄 바로 위에 한 묶음. old:

```css
/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

new:

```css
/* ── 보고서 화면 — 큰 진행 막대·머리 목차·문서 자리(06e Task A5) ── */
/* 큰 진행 막대(06e 정함 28 — 사용자 Q1 답 '현재 절 작성 중에 보이는 커다란 프로그레스바'를 자동 보고서에도). 두께는 06d
   research.css 의 --rs-bar-thick 과 같은 값이지만 import 하지 않고 이 파일의 토큰으로 둔다(시각 디자인 담당이 고칠 자리).
   절 자리가 아래로 쌓이며 흐르는 동안 화면 위에 붙어 있다(.wk-pill 과 같은 sticky) */
.wk-rbar {
  --wk-bar-thick: 1rem;
  position: sticky;
  top: 0.5rem;
  z-index: 2;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 0.4rem 0.8rem;
  padding: 0.8rem 1rem;
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-lnb);
}
.wk-rbar__line {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-ink);
  overflow-wrap: anywhere;
}
.wk-rbar__pct {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  color: var(--skx-primary);
}
.wk-rbar__track {
  grid-column: 1 / -1;
  height: var(--wk-bar-thick);
  overflow: hidden;
  background: var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}
.wk-rbar__fill {
  height: 100%;
  background: var(--skx-primary);
  border-radius: inherit;
  transition: width 0.4s ease;
}
/* 쓰는 절이 있는 동안 채움 위로 빛이 흐른다 — 퍼센트는 절이 끝날 때만 오르므로 멈춰 보이지 않게. 첫 절을 쓰는 동안(0%)도
   조금은 보이게 최소 폭을 둔다 */
.wk-rbar__fill.is-running {
  min-width: calc(var(--wk-bar-thick) * 2);
  background-image: linear-gradient(90deg, transparent 0%, color-mix(in srgb, var(--skx-white) 35%, transparent) 50%, transparent 100%);
  background-size: 200% 100%;
  animation: wk-rbar-flow 1.6s linear infinite;
}
@keyframes wk-rbar-flow {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}
@media (max-width: 768px) {
  .wk-rbar {
    --wk-bar-thick: 0.75rem;
  }
}
@media (prefers-reduced-motion: reduce) {
  .wk-rbar__fill {
    transition: none;
  }
  .wk-rbar__fill.is-running {
    animation: none;
  }
}
@media print {
  .rs-page .wk-rbar {
    display: none !important;
  }
}
/* 연쇄가 멈춘 줄 — 까닭과 [이어서 쓰기] */
.wk-doc__resume {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.wk-doc__resume p {
  margin: 0;
}
/* 머리 목차 — 문서 순서의 여섯 자리. 항목을 누르면 그 자리로 옮긴다 */
.wk-doc__toc {
  gap: 0.5rem;
}
.wk-doc__toc-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.wk-doc__toc-list {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.wk-doc__toc-item {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  width: 100%;
  padding: 0.3rem 0.5rem;
  font: inherit;
  font-size: 0.7rem;
  text-align: left;
  color: var(--skx-ink);
  background: none;
  border: 0;
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.wk-doc__toc-item:hover {
  background: var(--skx-border-c1);
}
.wk-doc__toc-item:focus-visible {
  outline: 2px solid var(--skx-border-c2);
  outline-offset: 1px;
}
.wk-doc__toc-no {
  flex-shrink: 0;
  min-width: 1.6rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--skx-gray-1);
}
.wk-doc__toc-label {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.wk-doc__toc-status {
  flex-shrink: 0;
  font-size: 0.6rem;
  color: var(--skx-gray-1);
}
.wk-doc__toc-item.is-queued .wk-doc__toc-status,
.wk-doc__toc-item.is-writing .wk-doc__toc-status {
  font-weight: 700;
  color: var(--skx-primary);
}
.wk-doc__toc-item.is-failed .wk-doc__toc-status,
.wk-doc__toc-item.is-skipped .wk-doc__toc-status {
  color: var(--skx-ink);
}
/* 문서 자리 — 1 주제·2 연구 배경·5 연구 질문·6 방법 제안(3·4 는 ProposalSection) */
.wk-doc {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.wk-doc__part {
  gap: 0.4rem;
}
.wk-doc__part-title {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.wk-doc__text {
  margin: 0;
  font-size: 0.7rem;
  line-height: 1.7;
  white-space: pre-line;
  color: var(--skx-ink);
}
/* 머리 목차로 옮겨 온 자리가 위에 붙은 진행 막대에 가리지 않게 */
.wk-doc__part,
.wk-doc .wk-psec {
  scroll-margin-top: 6rem;
}

/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

- [ ] **Step 5: 타입·빌드·전체 테스트를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`

Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`

Expected: `└  ✨ Build complete!` (`WARN Duplicated imports "queueLine"` 두 줄은 기준선과 같다 — 새 `Duplicated imports` 경고가 없어야 한다: `npm run build 2>&1 | grep -c "Duplicated imports"` 가 기준선 값 그대로)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`

Expected: 실패 0 — 수는 Task 앞과 같다(이 Task 는 테스트를 더하지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff --stat -- frontend/assets/css/work.css && git diff -U0 -- frontend/assets/css/work.css | grep "^@@"`

Expected: 바뀐 곳이 끝 표시 줄 위 한 덩어리뿐이다(`@@` 줄 하나 — 근거 장부 블록 `:75-166`·`:1215-1220` 을 건드리지 않는다)

브라우저 확인(마무리 운영 확인에 넘긴다 — 운영 스택 nuxt 로 볼 때): ① 참고문헌 화면에 [보고서 만들기], 목차가 있으면 [보고서 다시 만들기](확인 창 새 문구) ② 누르면 보고서 화면에서 '목차를 만드는 중' → 목차가 서면 큰 진행 막대(1rem 두께·`보고서 작성 중 · 0/3절 — 「…」`·퍼센트)가 서고 절이 끝날 때마다 차오르며 다 쓰면 걷힌다, 스크롤해도 막대가 위에 붙어 있다, 768px 이하 0.75rem ③ 머리 목차 항목을 누르면 그 자리로 가고 제목에 초점(1 주제·5 연구 질문 — 자동 확정이 고른 질문) ④ [목차 고치기]를 누르면 편집기가 펴지고 승인 흐름 그대로 ⑤ 근거 없는 절(사실상 연구 공백)은 '근거 없음' 배지와 '다른 주제를 고른 뒤 [보고서 다시 만들기]로 맞추세요' 안내 ⑥ 서버를 잠깐 막아 오류가 나면 [이어서 쓰기]가 서고 누르면 남은 절부터, 멈춘 채 남은 절을 [이 절 쓰기]로 다 쓰면 그 줄이 걷힌다 ⑦ 탭을 닫았다 `?s=proposal` 을 다시 열면 남은 절부터 ⑧ 06b 때 승인한 목차(auto 없음)는 연쇄·막대가 없고 안내 카드는 '절마다 [이 절 쓰기]를 누르면 씁니다', 쓰기 전 절은 '[이 절 쓰기]를 누르면 문장이 흘러나오고…'다('자동으로 씁니다'가 없다) ⑨ 예시 연구는 연쇄가 돌지 않고 '목차 자세히 보기' ⑩ 초안 목차(질문이 없어 자동 승인하지 못한 목차)를 편집기의 [목차 승인]으로 승인해도 편집기가 접히지 않고 '승인함'으로 바뀐다.

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/components/work/ReadingStep.vue frontend/components/work/ProposalStep.vue frontend/components/work/ProposalSection.vue frontend/assets/css/work.css && git status --short && git commit -m "[Feat] round06e 프론트 — 보고서 화면을 자동 산출로 바꾼다. [목차 만들기]·[목차 다시 만들기]를 [보고서 만들기]·[보고서 다시 만들기]로(담음 5편 조건 그대로, 다시 만들기 확인 창은 이미 쓴 절은 지우지 않고 아직 쓰지 않은 절만 자동으로 쓴다는 글). 승인 목차 위에 큰 진행 막대('보고서 작성 중 · n/m절 — 「절」'·퍼센트, 두께 1rem·768px 이하 0.75rem, 위에 붙음 — 사용자 Q1 답을 자동 보고서에도)와 머리 목차(여섯 자리, 누르면 그 자리로 가 제목에 초점), 문서 자리 1 주제·2 연구 배경·3·4 절·5 연구 질문·6 방법을 문서 순서로 그린다. 절 연쇄(useAutoReport)를 잇고 멈추면 남은 절이 있는 동안 까닭과 [이어서 쓰기]. [목차 고치기]는 승인 목차에서 접어 두는 토글로 남기고(초안 목차는 늘 펴고, 편집기에서 승인해도 접지 않는다), 근거가 없어 건너뛴 절은 '근거 없음' 배지와 다른 주제로 다시 만들라는 안내. 색은 --skx-* 토큰만(쓰는 중 빛은 color-mix — 새 색값 없음). 쓰기 전 절 안내와 계획서 안내는 연쇄가 그 절을 넣을 참일 때만 '자동으로 씁니다'라고 한다(06b 때 승인한 목차·취소로 끝난 절·멈춘 동안은 [이 절 쓰기] 안내)"
```

---

## 파트 메모 — 뼈대와 다른 점

뼈대의 이름·시그니처·모양·상수·테스트 이름은 그대로 썼다. 아래는 더하거나 좁힌 곳과 그 까닭이다(다른 파트가 기대는 계약은 바뀌지 않는다 — 더한 것은 모두 선택 인자이거나 이 파트 안에서만 쓰는 이름).

| # | Task | 뼈대 | 이 파트 | 까닭 |
|---|---|---|---|---|
| 1 | Task A1 | `auto_question` = 첫 후보 → 카드 질문 → `None`(공백만이면 None) | 공백을 정리하고 **2자 미만도 없는 것**으로 본다 | `PUT …/outline` 의 승인 하한(`APPROVE_NEEDS_QUESTION` — 2자, `research_proposal.py:258-259`)과 같아야 자동 승인한 목차를 [목차 고치기]로 다시 승인할 때 422 가 나지 않는다(정함 3 의 취지) |
| 2 | Task A3 | `reportBar(p, state, skipped)` | 넷째 선택 인자 `stopped = false` — 참이면 남은 절을 세지 않는다 | 연쇄가 오류로 멈춘 뒤에도 '보고서 작성 중 · …'이 남으면 아무것도 쓰지 않는데 쓰는 듯 보인다. 쓰는 절이 있으면 그대로 서고, 없으면 걷혀 [이어서 쓰기] 줄만 남는다. `reportBar` 를 부르는 곳은 Task A5 뿐이다 |
| 3 | Task A3 | 끝난 절 = done·failed·skipped | + 쓰기 전인데 **생성 기록이 있는**(취소로 끝난) 절. 남은 절은 상태가 '쓰기 전'인 것만 | 취소된 절은 `sectionStatus` 가 '쓰기 전'이라 끝난 수에 들지 않으면 막대가 끝까지 차지 않는다. 남은 절을 '쓰기 전'으로 좁혀 이벤트로 먼저 들어온 대기·실패 절이 두 번 세지지 않게 했다 |
| 4 | Task A3 | (없음) | `outlineBackground(outline): string` 을 더 내보낸다(`utils/proposalView.ts`) | `Outline.background` 타입 필드는 Task X3 이 더한다 — Task A3·Task A5 가 그 전에 `outline.background` 를 읽으면 `nuxi typecheck` 가 깨진다. 교차 타입으로 읽어 Task X3 뒤에도 그대로 컴파일된다. Task X3·Task X5 는 필드가 생긴 뒤 `outline.background` 를 바로 읽어도 된다(Task A5 의 2절 자리는 Task X3 이 DocField 로 바꾸며 이 함수를 계속 쓰거나 지워도 된다 — 다른 호출처는 `docToc` 하나) |
| 5 | Task A3 | 머리 목차 6 = '방법' | 라벨 `방법 제안`(`SECTION_LABELS.method`) | Word 의 절 제목(`proposalDocument.ts:135` `6. ${SECTION_LABELS.method}`)과 같은 말로 맞춘다. anchor(`wk-doc-method`)는 그대로 |
| 6 | Task A4 | 테스트 8개 | 11개 — ＋ '생성 목록에 그 키의 절 생성이 있으면 넣지 않는다'·'목차를 새로 만들면 건너뜀·멈춤을 비운다'·'도는 동안 들어온 변화는 루프가 끝난 뒤 다시 본다' | 뼈대 동작 계약에 세 가지를 더했다(Task A4 '알아 둘 것'): ① 연쇄 중 손으로 누른 [이 절 쓰기]의 절을 또 넣으면 409 쓰는 중으로 연쇄가 멈춘다 ② [보고서 다시 만들기]로 묶음이 바뀌면 근거가 생겼을 수 있다 ③ 도는 동안의 watch 는 `running` 에 막혀 새 목차를 놓친다(뼈대의 '다시 읽기 뒤 watch 가 다시 kick' 은 다시 읽기가 `running` 이 참일 때 끝나 막힌다). 세 동작마다 테스트가 있다(구현에서 빼면 그 테스트가 실패하는 것을 확인함) |
| 7 | Task A5 | `outlineOpen` 처음 값 = `state !== "approved"` | `outlineOpen = ref(false)` + `editorShown = !approved \|\| outlineOpen` + `saveOutline` 이 승인(`body.approve`)이면 `outlineOpen = true` | 뼈대가 노린 효과(초안 목차는 편집기를 펴고, 편집기에서 승인해도 편 채로 남는다)를 내되 처음 값에 기대지 않는다 — 처음 값으로 정하면 계획서를 읽기 전(proposal 이 아직 null)에 화면이 설 때 참이 되어 승인 목차도 펴진 채 시작한다. `saveOutline` 줄이 없으면 초안을 승인하는 순간 `approved` 가 참이 되어 편집기가 곧바로 내려간다(검토에서 찾음 — 처음 판은 '같은 효과'라고 잘못 적었다). 승인을 풀어 초안이 된 목차도 편집기가 늘 펴진다. 토글 버튼은 머리 목차 카드 머리에 두고, 예시 연구는 '목차 자세히 보기' |
| 8 | Task A5 | ReadingStep `REMAKE_CONFIRM` = "…목차(묶음 이름·연구 질문·승인)… 이미 쓴 절은 지우지 않고 '다시 맞춤 필요'를 붙이며, 새로 생긴 절만 자동으로 씁니다…" | 두 화면이 같은 글 — '방법'을 넣고, '다시 맞춤 필요'는 '주제나 묶음이 바뀐 절에는 붙습니다'로, '새로 생긴 절만'은 '아직 쓰지 않은 절만'으로 | Task A1 의 반영은 방법을 빈칸으로 되돌린다(06b ProposalStep 확인 창은 이미 '방법'을 적었다). `stale_flags` 는 주제가 바뀌면 모든 절, 묶음 논문이 바뀌면 그 선행연구 절에 붙인다(`proposal_views.py:49-51`) — 둘 다 그대로면 붙지 않아 '붙이며'는 늘 맞지 않는다. 연쇄 대상은 '절도 생성 기록도 없는 키'라 06b 때 일부만 쓴 목차의 쓰지 않은 기존 키도 자동으로 쓴다 — '새로 생긴 절만'이 아니다 |
| 9 | Task A5 | (없음) | ProposalSection `label` 에 머리 목차 번호를 붙인다(`partLabel` — `3.1 선행연구 검토 · …`·`4. 연구 공백`), 건너뛴 쓰기 전 절의 배지 '근거 없음' | 문서 자리 1·2·5·6 의 `1. 주제` 꼴(뼈대 1-7)·Word 절 번호와 맞추고, 머리 목차의 '근거 없음'과 절 배지를 같은 말로 둔다 |
| 10 | Task A5 | ProposalStep `makeOutline` 오류 문구는 목록에 없음 | `"보고서를 만들지 못했습니다"` | ReadingStep :156 과 같은 버튼의 같은 실패라 같은 말로 |
| 11 | Task A5 | `.wk-rbar*`·`.wk-doc*` 선택자 목록 | 막대를 `position: sticky; top: 0.5rem`(`.wk-pill` 선례)로 두고 자리마다 `scroll-margin-top: 6rem`, 쓰는 중 채움 최소 폭. 클래스 더함 `.wk-doc__toc-head`·`.wk-doc__toc-list`·`.wk-doc__toc-no`·`.wk-doc__toc-label`·`.wk-doc__text`, `.wk-doc__status` 는 쓰지 않음 | 사용자 답 '현재 절 작성 중에 보이는 커다란 프로그레스바' — 절이 아래로 쌓이며 흐르는 동안 막대가 스크롤에 밀려 사라지지 않게. 첫 절을 쓰는 동안(0%)도 움직임이 보이게 |
| 12 | Task A5 | ProposalSection prop 은 `skipped?` 하나, :195-197 새 안내 한 줄('차례가 오면 자동으로 씁니다'), :55-57 안내 카드 문구 하나 | prop `autoNext?: boolean` 을 더하고(ProposalStep 의 `autoNext` — 연쇄가 돌고 멈추지 않았을 때의 남은 절) 쓰기 전 안내를 셋(건너뜀·`autoNext`·그 밖)으로, 안내 카드를 `outline.auto` 로 둘로 가른다 | 연쇄가 돌지 않는 쓰기 전 절에서도 '자동으로 씁니다'라고 알리지 않게 — 06b 때 승인한 목차(`auto` 없음, 운영에 실제 연구가 있다), 생성 기록이 있는 쓰기 전 키(취소로 끝남·WorkView 최근 10건 밖의 빈 결과), 연쇄가 멈춘 동안. 06b 목차 화면에는 [보고서 만들기] 버튼도 없다 |
| 13 | Task A5 | `stopped` 면 `rs-alert` + [이어서 쓰기] | `autoStopped && autoLeft.length` — 남은 절이 있을 때만 | `stopped` 는 `resume()`·목차 `gen_id` 가 바뀔 때만 비워진다 — 멈춘 뒤 남은 절을 손으로 다 쓰면 할 일이 없는데 경고와 버튼이 남는다. Task A4 의 계약·테스트는 그대로 두고 화면에서 가린다(테스트 수가 바뀌지 않는다) |

**다른 파트·줄에 기대는 것 / 뒤 Task 가 알아야 할 것**
- 파트 A 는 06c 코드(`terms.py`)를 쓰지 않는다 — 선행 조건 Step 이 없다. 06c 운영 배포 뒤에만 dev 에 머지한다는 줄 규칙(§12-6)은 마무리 작성자 몫이다.
- 배포: Task A1(`outline.apply`)은 생성 워커 `celery-research-plan` 이 돌린다 — 워커가 fastapi 보다 먼저 새 이미지여야 자동 승인 목차가 생긴다(마무리 배포 순서 워커 → fastapi → nuxt 그대로). 옛 nuxt 가 잠깐 남아 있으면 자동 승인된 목차에 절 연쇄가 돌지 않을 뿐이다(사용자가 [이 절 쓰기]로 쓸 수 있다).
- 같은 파일을 뒤에 고치는 Task(뼈대 §3 표): `ProposalStep.vue` 는 Task X3(2·6 자리를 DocField 로 — 자리 `section`·`h3`·id 는 Task A5 그대로 둔다), Task X4(머리 목차 `nav.wk-doc__toc` 아래 `.wk-review` 줄), Task X5(내려받기 카드 — Task A5 는 글자 그대로 두었다), Task R1(:6·:19·:29-32·:35·:120·:147 — Task A5 는 그 줄을 바꾸지 않았다. Task R1 이 `FINAL_STEP_NAME` 을 쓰려면 Task A5 가 더한 `import { MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";` 줄에 이름을 더한다), Task S4(`.wk-split`·패널·emits), Task H3(PDF). `ReadingStep.vue` 는 Task R1(:6·:8-9·:12 의 '[목차 다시 만들기]'·:25·:48·:51 — Task A5 는 그대로 두고 :89 주석만 고쳤다, :12 의 버튼 이름은 Task R1 이 `[${REMAKE_REPORT}]` 로)·Task R5. `ProposalSection.vue` 는 Task X4(:98 sr-only)·Task X5(`STATE_LABELS`)·Task S4(인용 칩) — Task A5 는 :3-6 머리·:195-197·props(`skipped?`·`autoNext?`)·`skippedNow` 만 고쳤다. `proposalView.ts` 는 Task X3(`putOnceMore`)·Task X4(`reviewSpots`)·Task X5(`footprintLine`) — Task A3 은 import 두 줄과 파일 끝 묶음만 더했다. `types/work.ts` 의 `Outline` 끝은 Task A3 뒤 `auto?: boolean;` 이 마지막 줄이다(Task X3 이 `background?` 를 그 뒤에 더한다).
- 틀(06e-frame)의 컴포넌트 표 `ProposalSection.vue` 행은 Task A5 의 prop 을 `skipped?: boolean` 하나로 적었다 — Task A5 가 `autoNext?: boolean` 을 더했다(메모 12). Task S4 가 잡는 old(props 의 `jobId: string;` 한 줄·ProposalStep 의 `:job-id="jobId"` 한 줄)와 겹치지 않는다 — 두 줄 다 Task A5 뒤에도 그대로 한 번씩 있다.
- `utils/proposalView.ts` 가 `~/utils/workPhase`(FINAL_STEP_NAME)·`~/utils/researchErrors`(httpStatus)를 새로 import 한다 — `workPhase.ts` 가 `proposalView.ts` 를 import 하면 순환이 생기니 Task R1 이 `STEP_NAMES` 등을 더할 때 `proposalView` 를 import 하지 않는다(지금은 하지 않는다).
- 실행자가 확인할 것: ① Task A5 뒤 브라우저 확인(Step 5 의 열 항목)은 마무리 운영 확인에 넣는다 ② 운영 확인에서 [보고서 만들기] 한 번에서 마지막 절까지의 소요 시간과 생성 대기 순번을 기록한다(spec §12-7) ③ 06b 때 승인하고 일부 절만 쓴 연구를 열어 연쇄·막대가 서지 않고(auto 없음) 쓰기 전 절 안내에 '자동으로 씁니다'가 없는 것을 본다.

---

## 파트 X — 보고서 마무리·내보내기 기본값

덮는 spec 항목: §12-4 보고서 자동 산출(D20) 가운데 '연구 배경·방법'(배경은 §12-11 권고대로 `outline.background` 자유 글 — 뼈대 정함 7, 방법·배경은 승인 상태에서 문서 2절·6절 자리에서 쓰고 `PUT /outline` 의 `approve:true` 를 지킨다 — 정함 8, 연쇄 중 409 `version_conflict` 면 응답 version 으로 한 번만 다시 보낸다), '연구 질문을 바꿔도 다시 맞춤 필요'(질문을 절 basis 로 — 정함 9), '검토 단서'(§12-11 권고 — 머리 '검토할 곳' 줄은 넣고 보이는 '근거 없음' 배지는 넣지 않으며 부록에 같은 수 — 정함 11), '연구 공백 단정'(06b 이월 §7-13 — 정함 10), §12-4 '내보내기 기본값(D21)' 전부(기본 = 네 상태 전부·워터마크 없음, 부록 = 절별 문단 상태 개수·날짜·결과·논의 미포함 — 모델 이름·시도 기록 뺌, '수락한 문단만' 선택지 유지 — 정함 13)와 문단 상태의 보이는 이름 'AI 작성 · 검토 전'(Q8 동의, 저장 값 그대로). 딥리서치 보고서 내보내기 출력은 그대로다(`reportDocument.ts`·`reportDocx.ts`·`ReportPrint.vue` 를 고치지 않는다 — Task X5 확인 Step).

순서: X1(백엔드 — 같은 파일을 먼저 고치는 Task A1·A2 뒤) → X2(백엔드, 선행 없음) → X3(프론트 — Task A5 의 보고서 화면 구조 뒤) → X4(X3 뒤) → X5(X4 의 `reviewSpots` 와 Task A3 의 `FINAL_STEP_NAME` 뒤). 백엔드 둘(X1·X2)과 프론트 셋(X3~X5)은 서로 코드에 기대지 않는다(뼈대 1장 계약 모양만).

기대 수는 'Task 앞 + N' 상대값이고, 괄호 안 값은 dev `da80f23` 에 Task A3 의 최소 대역(`sectionKeysOf`·`FINAL_STEP_NAME`·`httpStatus` import)만 얹은 통합 사본에서 X1~X5 를 차례로 적용해 잰 값이다(백엔드는 A1·A2 없이 — 그래서 `test_research_proposal_api.py` 는 A1·A2 가 더하는 3개만큼 적다). 예외로 X1 의 목차 반영 테스트(`test_research_work_outline.py`)는 A1 의 자동 확정에 기대므로 06e-A 를 적용한 사본에서 쟀다(A1 뒤 30 → 31). 파트 X 가 더하는 수: 백엔드 X1 +6·X2 +15, vitest X3 +8·X4 +4·X5 +1.

---

### Task X1: 연구 배경 저장 · 연구 질문이 바뀌어도 '다시 맞춤 필요'

spec §12-4 '연구 배경·방법 — 연구 배경은 사용자가 쓰는 칸(저장 §12-11)'·'연구 질문을 바꿔도 다시 맞춤 필요가 붙도록 질문을 절 basis 에 넣는다', §12-11 '연구 배경 저장'(권고 — `outline.background` 자유 글), 뼈대 정함 7·9. 화면(문서 2절 칸)은 Task X3 이 단다 — 이 Task 는 서버만이다.

- **저장(`PUT /outline`):** `OutlinePut.background: str | None = Field(None, max_length=OUTLINE_BACKGROUND_MAX)`. `None`(본문에서 뺐거나 `null`)이면 저장된 값을 지킨다 — 배경을 모르는 [목차 고치기](`toOutlinePut` 은 배경을 싣지 않는다, Task X3)와 배포 사이 옛 화면의 PUT 이 배경을 지우지 않게. 실으면 앞뒤 공백을 떼어 `outline["background"]` 에 쓰고, 빈 글(`""`)이면 비운다. 상한 2000자는 pydantic 이 떼기 전 글자 수(코드 포인트)로 본다 — 화면(`fieldPut`)이 떼고 보낸다.
- **[보고서 다시 만들기]도 배경을 지킨다:** `outline.apply`(목차 반영 — Task A1)는 목차를 통째로 갈아 끼우고 방법을 빈칸으로 되돌리지만(spec D20), 연구 배경은 사용자가 직접 쓴 자유 글(2000자까지)이라 말없이 지우지 않는다 — 반영이 옛 목차를 읽어 배경이 있으면 새 목차에 이어 받는다. 적은 적이 없으면(없음·빈 글) 키를 두지 않는다(키가 없으면 `""` 로 읽는다 — 뼈대 1-2. A1 의 반영 테스트가 새 목차 dict 를 통째로 견주므로 키를 늘 넣지 않는다). 두 화면의 확인 창 문구는 Task X3 이 맞춘다(연구 배경은 그대로·연구 질문이 바뀐 절에도 '다시 맞춤 필요').
- **진행 'n/6절':** `sections_filled` 의 연구 배경 = `_text(outline.get("background")) or _written(sections.get("background"))` — 06b 의 절 자리(`sections.background`)를 세던 것은 남긴다(06b 에서 그 절을 쓰는 길은 없지만 지울 까닭도 없다). `put_outline` 은 이미 `refresh_progress`(`:276`)를 부르므로 저장하면 사이드바 진행이 바로 따라온다.
- **질문 바뀜(정함 9):** `prior_input`·`gap_input` 이 basis 에 `"question": research_question` 을 싣는다 — 워커의 절 반영(`section.py:121` `dict(inp.get("basis") …)`)이 그대로 `sections[key].basis` 로 옮긴다. `stale_flags` 는 basis 에 `question` **키가 있는 절만** 지금의 연구 질문(`_research_question(outline)` = `outline.question or outline.topic.question or ""` — 절을 쓸 때 `generate_section` 이 프롬프트에 넣는 식 `research_proposal.py:402` 와 같다)과 견준다. 06b 에 쓴 절은 키가 없어 이 이유로는 stale 이 되지 않는다(06b 절을 모두 '다시 맞춤 필요'로 덮지 않게). 방법·배경 칸의 저장(Task X3 의 `fieldPut`)은 저장된 질문을 그대로 실어 보내므로 절에 배지가 붙지 않는다.
- **알아 둘 것(앞 Task 뒤 기준):** `research_proposal.py` 는 Task A1(`NEED_READING` `:53`)·A2(`NO_SECTION_PAPERS_CODE`·`:395-396` detail)가, `proposal_views.py` 는 A2(`section_gens_of`·결과 키·docstring 한 줄)가, `test_research_proposal_api.py` 는 A1(`TestPutOutline.test_saving_keeps_the_auto_mark`)·A2(`TestSectionGens` 등)가, `models/research_work.py` 머리 주석은 A1(Outline `auto`)이 먼저 고친다. 이 Task 가 잡는 old 는 그 Task 들이 건드리지 않는 자리다(shapes import `:45-48`·`OutlinePut` `:74-78`·`put_outline` `:242-243`·`:260-266`, docstring `:3-6`·`stale_flags` `:36-52`, `TestStaleFlags` 끝·`TestPutOutline` 끝, Outline 의 questions 줄·Section 의 basis 줄). `outline.py`·`test_research_work_outline.py` 는 A1 이 바꾼 뒤의 글을 old 로 잡는다(import `from sqlalchemy import update` `:19` 는 A1 이 그대로 두는 줄, `apply` docstring 의 '승인한 목차가 있어도 통째로 바꾼다' 줄과 dict 끝 `"auto": auto,` 는 A1 이 쓴 줄, 테스트는 A1 의 `test_a_new_outline_replaces_an_approved_one` 끝 단언). Edit 가 old 를 못 찾으면 그 이름의 블록을 찾아 '교체 후'로 갈음한다.
- 스키마 변경 없음(함정 14 — JSONB 안 모양만). `models/research_work.py` 는 머리 주석만이라 `test_research_work_models.py`(0007 과 ORM 비교)는 그대로 통과한다. 이 파일은 spec §12-5 의 06e 백엔드 경계(`app/services/research_work/*` 등) 밖이지만 계획 머리의 '예외(이 계획이 경계 밖에서 고치는 줄)' 목록에 이미 있다(JSONB 모양 머리 주석만 — A1·X1·K4·K9, 06c 는 `app/models/research.py:100` 만 고친다). 완료노트의 경계 예외에 함께 적는다.

**Files:**
- Modify: `app/services/research_work/shapes.py` (`OUTLINE_BACKGROUND_MAX` — `:27` 아래)
- Modify: `app/api/research_proposal.py` (shapes import `:45-48`, `OutlinePut` `:74-78`, `put_outline` docstring `:242-243`·`outline.update` 뒤 `:266`)
- Modify: `app/services/research_work/progress.py` (`sections_filled` docstring `:34-35`·`:43`)
- Modify: `app/services/research_work/section_input.py` (`prior_input` docstring·basis `:114-122`, `gap_input` basis `:136`)
- Modify: `app/services/research_work/proposal_views.py` (머리 docstring `:3-6`, 새 `_research_question`, `stale_flags` `:36-53`)
- Modify: `app/services/research_work/outline.py` (import `:19`, `apply` docstring·새 목차 dict 뒤 — Task A1 뒤)
- Modify: `app/models/research_work.py` (머리 주석 Outline·Section — 경계 예외, 위 '스키마 변경 없음' 항목)
- Test: `app/tests/test_research_proposal_api.py` (＋ `TestStaleFlags` 둘, ＋ `TestPutOutline` 둘)
- Test: `app/tests/test_research_work_section_input.py` (✎ `TestPriorInput.test_shape`·`TestGapInput.test_shape`)
- Test: `app/tests/test_research_work_enqueue.py` (＋ `TestSectionsFilled.test_background_written_in_the_outline_counts`)
- Test: `app/tests/test_research_work_outline.py` (＋ `TestApply.test_a_new_outline_keeps_the_research_background` — A1 뒤)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_proposal_api.py` — `TestStaleFlags` 끝(`test_no_outline_is_not_stale` `:104-106` 뒤)에 두 테스트를 더한다. 교체 전:

```python
    def test_no_outline_is_not_stale(self):
        flags = stale_flags(SimpleNamespace(topic_id=None), {}, {}, set())
        assert flags == {"outline": False, "sections": {}}
```

교체 후:

```python
    def test_no_outline_is_not_stale(self):
        flags = stale_flags(SimpleNamespace(topic_id=None), {}, {}, set())
        assert flags == {"outline": False, "sections": {}}

    def test_a_changed_research_question_needs_a_refit_of_written_sections(self):
        # 06e(spec §12-4) — [목차 고치기]로 연구 질문을 바꾸면 그 앞에 쓴 절에 '다시 맞춤 필요'가 붙는다
        def asked(key: str, question: str, **kw) -> dict:
            # 06e 부터 쓴 절 — basis 에 그 절을 쓸 때의 연구 질문이 있다
            sec = _section(key, **kw)
            return {**sec, "basis": {**sec["basis"], "question": question}}

        work = SimpleNamespace(topic_id=12, concepts=CONCEPTS)
        outline = {**OUTLINE, "question": "가는 나인가?"}
        sections = {"prior.g1": asked("prior.g1", "가는 나인가?", papers=["C1", "C2"]),
                    "gap": asked("gap", "옛 질문인가?")}
        assert stale_flags(work, outline, sections, {"C1", "C2", "C3"}) == {
            "outline": False, "sections": {"prior.g1": False, "gap": True}}
        # 목차에 고른 질문이 없으면 절을 쓸 때(research_proposal.generate_section)처럼 목차 주제의 질문과 견준다
        no_question = {**OUTLINE, "question": None}
        same = stale_flags(work, no_question, {"gap": asked("gap", CARD["question"])}, {"C1", "C2", "C3"})
        other = stale_flags(work, no_question, {"gap": asked("gap", "가는 나인가?")}, {"C1", "C2", "C3"})
        assert (same["sections"], other["sections"]) == ({"gap": False}, {"gap": True})

    def test_sections_written_before_06e_have_no_question_and_stay_fresh(self):
        # 06b 에 쓴 절은 basis 에 question 키가 없다 — 질문을 바꿔도 이 이유로는 다시 맞춤이 되지 않는다
        work = SimpleNamespace(topic_id=12, concepts=CONCEPTS)
        sections = {"prior.g1": _section("prior.g1", papers=["C1", "C2"]), "gap": _section("gap")}
        assert "question" not in sections["gap"]["basis"]
        for question in ("가는 나인가?", None):
            assert stale_flags(work, {**OUTLINE, "question": question}, sections, {"C1", "C2", "C3"}) == {
                "outline": False, "sections": {"prior.g1": False, "gap": False}}
```

`app/tests/test_research_proposal_api.py` — `TestPutOutline` 끝(`test_example_work_is_read_only` 뒤, `class TestAppWiring` 앞 — 06b `:639-646`)에 두 테스트를 더한다. 교체 전:

```python
    def test_example_work_is_read_only(self, api):
        jid = _with_outline(api)
        _set_work(api.engine, jid, is_example=True)
        assert api.client.put(f"/api/research/{jid}/outline", json=_put_body(),
                              headers={"If-Match": "2"}).status_code == 409


class TestAppWiring:
```

교체 후:

```python
    def test_example_work_is_read_only(self, api):
        jid = _with_outline(api)
        _set_work(api.engine, jid, is_example=True)
        assert api.client.put(f"/api/research/{jid}/outline", json=_put_body(),
                              headers={"If-Match": "2"}).status_code == 409

    def test_background_is_saved_trimmed_and_kept_when_left_out(self, api):
        # 06e(§12-11 권고) — 연구 배경은 outline.background 자유 글. 앞뒤 공백을 떼어 저장하고, 싣지 않은 PUT(생략·null —
        # [목차 고치기]·옛 화면)은 저장된 배경을 지킨다. 빈 글("")은 지운다. 적은 배경은 진행 'n/6절'에도 센다
        jid = _with_outline(api)
        url = f"/api/research/{jid}/outline"

        first = api.client.put(url, json=_put_body(background="  농촌 독거노인의 사회적 고립이 깊어지고 있다.\n"),
                               headers={"If-Match": "2"})
        kept = api.client.put(url, json=_put_body(), headers={"If-Match": "3"})
        null = api.client.put(url, json=_put_body(background=None), headers={"If-Match": "4"})

        assert [r.status_code for r in (first, kept, null)] == [200, 200, 200]
        assert {r.json()["outline"]["background"] for r in (first, kept, null)} == {
            "농촌 독거노인의 사회적 고립이 깊어지고 있다."}
        # 주제·연구 질문·방법 + 연구 배경 = 4절(묶음 절·연구 공백은 아직 쓰지 않았다)
        assert _work_row(api.engine, jid)["progress"]["sections"] == 4

        cleared = api.client.put(url, json=_put_body(background=""), headers={"If-Match": "5"})
        assert cleared.status_code == 200 and cleared.json()["outline"]["background"] == ""
        assert _proposal(api.engine, jid)["outline"]["background"] == ""
        assert _work_row(api.engine, jid)["progress"]["sections"] == 3

    def test_background_over_the_limit_is_422(self, api):
        jid = _with_outline(api)
        url = f"/api/research/{jid}/outline"
        res = api.client.put(url, json=_put_body(background="가" * 2001), headers={"If-Match": "2"})
        assert res.status_code == 422 and _proposal(api.engine, jid)["version"] == 2
        assert api.client.put(url, json=_put_body(background="가" * 2000), headers={"If-Match": "2"}).status_code == 200


class TestAppWiring:
```

`app/tests/test_research_work_section_input.py` — `TestPriorInput.test_shape` 의 basis 단언(`:405-406`). 교체 전:

```python
        # 다시 맞춤 판정의 기준은 묶음의 논문 전부(넣지 못한 7번째 포함)
        assert inp["basis"] == {"topic_id": 12, "papers": GROUP["papers"]}
```

교체 후:

```python
        # 다시 맞춤 판정의 기준은 묶음의 논문 전부(넣지 못한 7번째 포함)와 이 절을 쓸 때의 연구 질문(06e)
        assert inp["basis"] == {"topic_id": 12, "papers": GROUP["papers"],
                                "question": "가족 지지는 농촌 독거노인의 우울을 낮추는가?"}
```

`app/tests/test_research_work_section_input.py` — `TestGapInput.test_shape` 의 basis 단언(`:426`). 교체 전:

```python
        assert inp["basis"] == {"topic_id": 12, "papers": ["KCI_A", "KCI_B", "KCI_C"]}
```

교체 후:

```python
        assert inp["basis"] == {"topic_id": 12, "papers": ["KCI_A", "KCI_B", "KCI_C"], "question": "rq"}
```

`app/tests/test_research_work_enqueue.py` — `TestSectionsFilled.test_background_counts_when_written`(`:261-264`) 뒤에 더한다. 교체 전:

```python
    def test_background_counts_when_written(self):
        sections = {"prior.g1": _section("가"), "prior.g2": _section("나"), "gap": _section("다"),
                    "background": _section("라")}
        assert sections_filled(_outline(), sections) == 6
```

교체 후:

```python
    def test_background_counts_when_written(self):
        sections = {"prior.g1": _section("가"), "prior.g2": _section("나"), "gap": _section("다"),
                    "background": _section("라")}
        assert sections_filled(_outline(), sections) == 6

    def test_background_written_in_the_outline_counts(self):
        # 06e(§12-11 권고) — 연구 배경은 사용자가 목차에 적는 자유 글(outline.background)이다. 공백뿐이면 세지 않는다
        sections = {"prior.g1": _section("가"), "prior.g2": _section("나"), "gap": _section("다")}
        assert sections_filled(_outline(background="농촌 독거노인의 고립이 깊어진다."), sections) == 6
        assert sections_filled(_outline(background="  "), sections) == 5
        assert sections_filled(_outline(), sections) == 5
```

`app/tests/test_research_work_outline.py` — `TestApply.test_a_new_outline_replaces_an_approved_one`(Task A1 이 고친 테스트)의 끝 단언 뒤에 더한다. 교체 전:

```python
        out = row["outline"]
        assert (out["state"], out["question"], out["method"], out["approved_at"], out["auto"]) == (
            "approved", FIRST, "", NOW, True)
```

교체 후:

```python
        out = row["outline"]
        assert (out["state"], out["question"], out["method"], out["approved_at"], out["auto"]) == (
            "approved", FIRST, "", NOW, True)

    def test_a_new_outline_keeps_the_research_background(self, engine, monkeypatch):
        # 06e(§12-11 권고) — 연구 배경은 사용자가 쓰는 자유 글이다. [보고서 다시 만들기]가 목차를 통째로 바꿔도 이어 받는다.
        # 적은 적이 없는(빈 글) 목차를 다시 만들면 키를 두지 않는다
        monkeypatch.setattr("services.research_work.outline._now", lambda: NOW)
        written = {"state": "approved", "groups": [], "question": "옛 질문?", "method": "옛 방법",
                   "approved_at": "2026-10-10", "background": "농촌 독거노인의 고립이 깊어지고 있다."}
        jid, gid = _setup(engine, outline=written, version=5)
        blank_jid, blank_gid = _setup(engine, outline={**written, "background": ""}, version=5)

        _apply(engine, gid, EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT))
        _apply(engine, blank_gid, EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT))

        out = _proposal(engine, jid)["outline"]
        assert (out["background"], out["question"], out["method"]) == ("농촌 독거노인의 고립이 깊어지고 있다.", FIRST, "")
        assert "background" not in _proposal(engine, blank_jid)["outline"]
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_proposal_api.py -q -p no:cacheprovider`
Expected: `3 failed, <X1 앞 이 파일의 수 + 1> passed, 2 warnings`(A1·A2 뒤 이 파일이 98 이면 `3 failed, 99 passed` — dev `da80f23` 만 놓고 잰 값 `3 failed, 96 passed`). 실패 셋:
- `TestStaleFlags::test_a_changed_research_question_needs_a_refit_of_written_sections` — `AssertionError: assert {'outline': F...'gap': False}} == {'outline': F... 'gap': True}}`
- `TestPutOutline::test_background_is_saved_trimmed_and_kept_when_left_out` — `KeyError: 'background'`(지금 `OutlinePut` 은 모르는 칸을 버린다)
- `TestPutOutline::test_background_over_the_limit_is_422` — `assert (200 == 422)`

`test_sections_written_before_06e_have_no_question_and_stay_fresh` 는 지금도 통과한다 — 06b 절이 이 이유로 stale 이 되지 않는 것을 고정하는 테스트다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_section_input.py tests/test_research_work_enqueue.py -q -p no:cacheprovider`
Expected: `3 failed, 63 passed, 2 warnings` — `TestPriorInput::test_shape`·`TestGapInput::test_shape`(basis 에 `question` 이 없다 — `AssertionError: assert {'topic_id': ...} == {'topic_id': ...}`)와 `TestSectionsFilled::test_background_written_in_the_outline_counts`(`assert 5 == 6`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_outline.py -q -p no:cacheprovider`
Expected: `1 failed, <X1 앞 이 파일의 수> passed, 2 warnings`(A1 뒤 `1 failed, 30 passed`) — `TestApply::test_a_new_outline_keeps_the_research_background` — `KeyError: 'background'`(지금 반영은 옛 목차의 배경을 버린다)

- [ ] **Step 3: 구현한다**

`app/services/research_work/shapes.py` — `OUTLINE_METHOD_MAX`(`:27`) 아래. 교체 전:

```python
OUTLINE_METHOD_MAX = 1000
```

교체 후:

```python
OUTLINE_METHOD_MAX = 1000
OUTLINE_BACKGROUND_MAX = 2000   # 연구 배경(outline.background — 사용자가 쓰는 자유 글, 06e §12-11 권고) 글자 상한
```

`app/api/research_proposal.py` — shapes import(`:45-48`) — 줄 길이 120자 안으로 다시 나눈다. 교체 전:

```python
from services.research_work.shapes import (
    GAP_KEY, GROUP_LABEL_MAX, MAX_GROUPS, MAX_PARAGRAPH_CHARS, MAX_PARAGRAPHS_PUT, MIN_READING_FOR_OUTLINE,
    OUTLINE_METHOD_MAX, OUTLINE_QUESTION_MAX, OUTLINE_TARGET, PHASE_ORDER, WRITABLE_SECTION_KEYS,
)
```

교체 후:

```python
from services.research_work.shapes import (
    GAP_KEY, GROUP_LABEL_MAX, MAX_GROUPS, MAX_PARAGRAPH_CHARS, MAX_PARAGRAPHS_PUT, MIN_READING_FOR_OUTLINE,
    OUTLINE_BACKGROUND_MAX, OUTLINE_METHOD_MAX, OUTLINE_QUESTION_MAX, OUTLINE_TARGET, PHASE_ORDER,
    WRITABLE_SECTION_KEYS,
)
```

`app/api/research_proposal.py` — `OutlinePut`(`:74-78`). 교체 전:

```python
class OutlinePut(BaseModel):
    groups: list[OutlineGroupIn] = Field(min_length=1, max_length=MAX_GROUPS)
    question: str = Field(max_length=OUTLINE_QUESTION_MAX)
    method: str = Field(max_length=OUTLINE_METHOD_MAX)
    approve: bool
```

교체 후:

```python
class OutlinePut(BaseModel):
    groups: list[OutlineGroupIn] = Field(min_length=1, max_length=MAX_GROUPS)
    question: str = Field(max_length=OUTLINE_QUESTION_MAX)
    method: str = Field(max_length=OUTLINE_METHOD_MAX)
    approve: bool
    # 연구 배경(06e) — None(생략)이면 저장된 값을 지킨다: 배경을 모르는 [목차 고치기]·옛 화면의 PUT 이 지우지 않게
    background: str | None = Field(None, max_length=OUTLINE_BACKGROUND_MAX)
```

`app/api/research_proposal.py` — `put_outline` docstring(`:242-243`). 교체 전:

```python
    """목차 고치기·승인. approve 면 state approved(승인 시각), 아니면 draft — 승인한 목차를 고쳐 저장하면 다시
    승인해야 절을 쓴다. version 이 다르면 409(조건부 UPDATE 로 확인과 쓰기를 한 문장에)."""
```

교체 후:

```python
    """목차 고치기·승인. approve 면 state approved(승인 시각), 아니면 draft — 승인한 목차를 고쳐 저장하면 다시
    승인해야 절을 쓴다. version 이 다르면 409(조건부 UPDATE 로 확인과 쓰기를 한 문장에).
    연구 배경(background)은 실었을 때만 앞뒤 공백을 떼어 바꾼다("" 면 지움) — 싣지 않으면 저장된 값 그대로다(06e)."""
```

`app/api/research_proposal.py` — `put_outline` 의 `outline.update`(`:260-266`) 뒤 — 조건부 UPDATE(`:267-271`) 앞. 교체 전:

```python
        "approved_at": datetime.now(timezone.utc).isoformat() if req.approve else None,
    })
```

교체 후:

```python
        "approved_at": datetime.now(timezone.utc).isoformat() if req.approve else None,
    })
    if req.background is not None:
        outline["background"] = req.background.strip()
```

`app/services/research_work/progress.py` — `sections_filled` docstring(`:34-35`). 교체 전:

```python
    주제 = 목차의 주제 제목, 연구 질문·방법 제안 = 목차에서 고른·적은 값, 연구 배경·연구 공백 = 글이 있는
    문단이 있는 절. 선행연구 검토는 목차의 묶음이 하나 이상이고 모든 묶음 절(prior.gN)이 써졌을 때 1절이다.
```

교체 후:

```python
    주제 = 목차의 주제 제목, 연구 질문·방법 제안 = 목차에서 고른·적은 값, 연구 배경 = 목차에 적은 글(06e
    outline.background — 06b 의 절 자리 sections.background 도 센다), 연구 공백 = 글이 있는 문단이 있는 절.
    선행연구 검토는 목차의 묶음이 하나 이상이고 모든 묶음 절(prior.gN)이 써졌을 때 1절이다.
```

`app/services/research_work/progress.py` — `sections_filled` 의 연구 배경(`:43`). 교체 전:

```python
        "background": _written(sections.get("background")),
```

교체 후:

```python
        "background": _text(outline.get("background")) or _written(sections.get("background")),
```

`app/services/research_work/section_input.py` — `prior_input` docstring(`:114-115`). 교체 전:

```python
    """선행연구 묶음 하나(group = 목차의 {key, name, hint, papers})의 절 입력(계약 §3). 논문은 section_papers 로
    6편까지. basis.papers 는 묶음의 논문 전부다 — 목차에서 묶음을 바꾸면 '다시 맞춤 필요'가 뜨게(계약 §4 stale)."""
```

교체 후:

```python
    """선행연구 묶음 하나(group = 목차의 {key, name, hint, papers})의 절 입력(계약 §3). 논문은 section_papers 로
    6편까지. basis.papers 는 묶음의 논문 전부다 — 목차에서 묶음을 바꾸면 '다시 맞춤 필요'가 뜨게(계약 §4 stale).
    basis.question 은 이 절을 쓸 때의 연구 질문이다 — 질문을 바꿔도 '다시 맞춤 필요'가 뜨게(06e)."""
```

`app/services/research_work/section_input.py` — `prior_input` 의 basis(`:122`). 교체 전:

```python
        "basis": {"topic_id": topic.get("id"), "papers": list(group.get("papers") or [])},
```

교체 후:

```python
        "basis": {"topic_id": topic.get("id"), "papers": list(group.get("papers") or []),
                  "question": research_question},
```

`app/services/research_work/section_input.py` — `gap_input` 의 basis(`:136`). 교체 전:

```python
        "basis": {"topic_id": topic.get("id"), "papers": cnts},
```

교체 후:

```python
        "basis": {"topic_id": topic.get("id"), "papers": cnts, "question": research_question},
```

`app/services/research_work/proposal_views.py` — 머리 docstring 의 다시 맞춤 항목(`:3-6`). 교체 전:

```python
- 다시 맞춤 필요(stale)는 저장하지 않고 조회 때 센다(계약 §4): 목차는 고른 주제가 바뀌었거나 묶음 논문 합집합이
  지금 담음과 다르거나 핵심 개념이 목차를 만들 때(outline.concepts)와 다르거나 고른 카드의 제목이 목차의
  topic.title 과 다르면(호출부가 넘긴 경우만), 선행연구 절(prior.gN)은 주제가 바뀌었거나 그 절의 근거 논문이 그 묶음 논문과 다르면,
  그 밖의 절은 주제가 바뀌었으면. 앞 단계를 바꿔도 뒤 단계를 지우지 않고 배지만 붙인다(spec §4).
```

교체 후:

```python
- 다시 맞춤 필요(stale)는 저장하지 않고 조회 때 센다(계약 §4): 목차는 고른 주제가 바뀌었거나 묶음 논문 합집합이
  지금 담음과 다르거나 핵심 개념이 목차를 만들 때(outline.concepts)와 다르거나 고른 카드의 제목이 목차의
  topic.title 과 다르면(호출부가 넘긴 경우만), 선행연구 절(prior.gN)은 주제가 바뀌었거나 그 절의 근거 논문이 그 묶음 논문과 다르면,
  그 밖의 절은 주제가 바뀌었으면. 06e 부터 쓴 절(basis 에 question 이 있는 절)은 그때의 연구 질문이 지금과 달라도
  다시 맞춤이다 — 06b 에 쓴 절은 키가 없어 이 이유로는 붙지 않는다. 앞 단계를 바꿔도 뒤 단계를 지우지 않고 배지만
  붙인다(spec §4).
```

`app/services/research_work/proposal_views.py` — `stale_flags` 머리(`:36-38`) — 그 위에 `_research_question` 을 둔다. 교체 전:

```python
def stale_flags(work, outline: dict, sections: dict, picked: set[str], topic_title: str | None = None) -> dict:
    """topic_title 은 고른 카드의 지금 제목(호출부가 고른 주제 행에서 읽는다) — None 이면 제목은 견주지 않는다."""
    topic_id = work.topic_id
```

교체 후:

```python
def _research_question(outline: dict) -> str:
    """절을 쓸 때 프롬프트에 넣는 연구 질문 — 목차에 고른 질문, 없으면 목차 주제의 질문(research_proposal.generate_section
    과 같은 식). 절 basis.question 과 견준다."""
    return (outline or {}).get("question") or ((outline or {}).get("topic") or {}).get("question") or ""


def stale_flags(work, outline: dict, sections: dict, picked: set[str], topic_title: str | None = None) -> dict:
    """topic_title 은 고른 카드의 지금 제목(호출부가 고른 주제 행에서 읽는다) — None 이면 제목은 견주지 않는다."""
    topic_id = work.topic_id
```

`app/services/research_work/proposal_views.py` — `stale_flags` 의 절 루프(`:50-52`). 교체 전:

```python
        if key.startswith("prior."):
            stale = stale or key not in groups or set(basis.get("papers") or []) != groups[key]
        flags[key] = stale
```

교체 후:

```python
        if key.startswith("prior."):
            stale = stale or key not in groups or set(basis.get("papers") or []) != groups[key]
        if "question" in basis:
            stale = stale or basis["question"] != _research_question(outline)
        flags[key] = stale
```

`app/models/research_work.py` — 머리 주석 Outline 의 questions 줄(`:35` — Task A1 이 그 아래 state 줄 끝에 `auto` 를 더했다). 교체 전:

```python
               "questions": [str], "question": str|null, "method": str,
```

교체 후:

```python
               "questions": [str], "question": str|null, "method": str,
               "background": str,                                    — 연구 배경 자유 글(06e — 키가 없으면 "")
```

`app/models/research_work.py` — 머리 주석 Section 의 basis 줄(`:38-39`). 교체 전:

```python
               "basis": {"topic_id": int|null, "papers": [cnts_id]}, "note": str|null,
               "paragraphs": [Paragraph], "model": str|null, "updated_at": iso}
```

교체 후:

```python
               "basis": {"topic_id": int|null, "papers": [cnts_id], "question": str}, "note": str|null,
               "paragraphs": [Paragraph], "model": str|null, "updated_at": iso}
                                                                     — basis.question 은 06e 부터(06b 절엔 없음)
```

`app/services/research_work/outline.py` — import(`:19`, A1 이 그대로 둔 줄). 교체 전:

```python
from sqlalchemy import update
```

교체 후:

```python
from sqlalchemy import select, update
```

`app/services/research_work/outline.py` — `apply` docstring 의 다시 만들기 줄(Task A1 이 쓴 줄). 교체 전:

```python
    승인한 목차가 있어도 통째로 바꾼다([보고서 다시 만들기] — 새 반영이라 auto 가 다시 붙는다).
```

교체 후:

```python
    승인한 목차가 있어도 통째로 바꾼다([보고서 다시 만들기] — 새 반영이라 auto 가 다시 붙는다). 연구 배경(background —
    사용자가 쓰는 자유 글)만 옛 목차에서 이어 받는다.
```

`app/services/research_work/outline.py` — `apply` 의 새 목차 dict 끝(Task A1 의 `"auto": auto,`) 뒤, UPDATE 앞. 교체 전:

```python
        "auto": auto,
    }
    await db.execute(
```

교체 후:

```python
        "auto": auto,
    }
    # 연구 배경은 사용자가 쓰는 자유 글이다(06e) — 새 반영이 목차를 통째로 바꿔도 지우지 않는다. 적은 적이 없으면 키를
    # 두지 않는다(키가 없으면 "" 로 읽는다)
    old = await db.scalar(select(ResearchProposal.outline).where(ResearchProposal.work_id == gen.work_id))
    if (old or {}).get("background"):
        outline["background"] = old["background"]
    await db.execute(
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_proposal_api.py tests/test_research_work_section_input.py tests/test_research_work_enqueue.py -q -p no:cacheprovider`
Expected: 실패 0 — `<X1 앞 세 파일 합 + 5> passed, 2 warnings`(A1·A2 뒤면 `168 passed` — 계획서 API 102 · 절 입력 40 · 진행 26, dev `da80f23` 만 놓고 `165 passed`)

절 반영·모델 주석·목차를 함께 쓰는 테스트(basis 를 통째로 옮기는 워커 반영·0007 비교·목차 반영):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_section.py tests/test_research_work_models.py tests/test_research_work_outline.py -q -p no:cacheprovider`
Expected: 실패 0 — `<X1 앞 세 파일 합 + 1> passed, 2 warnings`(절·모델은 이 Task 전과 같고 목차는 +1 — A1 뒤 `test_research_work_outline.py` 31)

- [ ] **Step 5: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`
Expected: `5 failed, (Task 앞 + 6) passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 기준선과 같은 세 파일(`test_build_manifest.py`·`test_loaders.py`·`test_book_chat.py` 수집)

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/shapes.py && git add app/api/research_proposal.py && git add app/services/research_work/progress.py && git add app/services/research_work/section_input.py && git add app/services/research_work/proposal_views.py && git add app/services/research_work/outline.py && git add app/models/research_work.py && git add app/tests/test_research_proposal_api.py && git add app/tests/test_research_work_section_input.py && git add app/tests/test_research_work_enqueue.py && git add app/tests/test_research_work_outline.py && git status --short && git commit -m "[Feat] round06e — 연구 배경을 목차의 자유 글(outline.background)로 저장하고, 연구 질문이 바뀌어도 쓴 절에 '다시 맞춤 필요'를 붙인다(spec §12-4·§12-11 권고). PUT /outline 에 background 를 더한다 — 2000자까지, 실었을 때만 앞뒤 공백을 떼어 바꾸고(빈 글이면 지움) 싣지 않으면 저장된 값을 지킨다: 배경을 모르는 [목차 고치기]·옛 화면의 PUT 이 지우지 않게. [보고서 다시 만들기](새 목차 반영)도 목차를 통째로 바꾸되 적은 연구 배경은 이어 받는다 — 사용자가 쓴 글을 말없이 지우지 않게. 진행 'n/6절'은 목차에 적은 연구 배경을 센다. 절 입력의 basis 에 그때의 연구 질문을 싣고, stale_flags 는 basis 에 question 이 있는 절만 지금 질문(목차 질문, 없으면 목차 주제의 질문 — 절을 쓸 때와 같은 식)과 견준다. 06b 에 쓴 절은 키가 없어 이 이유로는 붙지 않는다. 스키마 변경 없음(JSONB 안 모양만)"
```

---

### Task X2: 연구 공백 단정 다듬기 — '확인했다'·'확인되었다'

spec §12-4 '연구 공백 단정(06b 이월 §7-13)', 뼈대 정함 10. 06b 운영 1회의 연구 공백 1번째 문단이 '소장 코퍼스를 분석한 결과 … 충분하지 않음을 확인했다'고 단정해 절 머리의 '확인하지 않은 공백 후보'와 어긋났다(완료노트 §7-13) — 06e 는 사람의 수락 관문이 빠지므로(D20) 이 단정을 코드가 고친다.

- **문맥으로 가른다(정함 10):** `soften_claims` 가 기존 `CLAIM_REWRITES` 를 거친 뒤 글을 문장으로 나누고(`(?<=[.!?。])\s+` — 나눈 공백은 그대로 다시 잇는다), 문장이 `GAP_CLAIM_CONTEXT`(`코퍼스` 또는 `소장 학술논문·논문·자료·문헌`)를 품을 때만 `GAP_CLAIM_REWRITES` 다섯 쌍을 차례로 적용한다. '분석한 결과·검토한 결과' 같은 말은 문맥으로 쓰지 않는다 — 선행연구 요약('김(2015)[E1]은 노인 300명을 분석한 결과 … 확인되었다')에 흔해 `soften_claims` 가 모든 절·문단 다시 쓰기·사용자가 고친 글·주제 카드에 같이 도는 지금 구조에서 인용한 발견까지 바꾼다. 절 키로 가르지 않는다 — `soften_claims` 시그니처와 호출처(`check_paragraph` 를 거쳐 — `section.py:48`·`paragraph_edit.py:60`, 직접 — `topic_card.py:170-171`·`research_topics.py:70` `_soft`)는 그대로다.
- **CLAIM_REWRITES 가 넣은 말은 문맥이 아니다:** `CLAIM_REWRITES`(`markers.py:27-38`)가 바꿔 넣는 말('소장 코퍼스에서 확인하지 못했다'·'소장 코퍼스에서 확인되지 않았다'·'소장 코퍼스에서 확인한 범위에서')에 '코퍼스'가 들어 있다. 바꾼 뒤의 글로 문맥을 보면 원래 코퍼스 낱말이 없던 인용 발견('선행연구에서 최초로 … 확인되었다'·'김(2015)[E1]은 … 연구가 거의 없다고 지적했고 … 확인되었다')까지 공백 후보로 바뀐다 — 그래서 문맥은 그 말(`_CLAIM_INSERTS`)을 지운 문장에서 본다. 원문 기준 판정과 같고 두 번 거쳐도 같다(두 번째에는 CLAIM 이 걸리지 않고, 넣은 말을 지운 문맥도 첫 번째와 같다).
- **다섯 쌍(뼈대 계약 그대로, 문장 끝 단정만):** ① `않음을 확인했다/확인하였다/확인할 수 있었다/알 수 있었다` → `않은 것으로 보인다(…)` ② `없음을 …` → `없는 것으로 보인다(…)` ③ `함을 …` → `한 것으로 보인다(…)` ④ `것으로/것이 확인되었다/확인됐다` → `것으로 보인다(…)` ⑤ `확인되었다/확인됐다` → `보인다(…)`. 꼬리 `GAP_CLAIM_TAIL` = `(소장 코퍼스에서 확인하지 않은 공백 후보)` 는 `shapes.GAP_NOTE` 로 만든다(같은 글을 두 번 적지 않는다 — 값은 뼈대 1-1 과 같다). 다섯 패턴 끝에 `(?![가-힣])` 를 붙여 '확인되었다는 점'처럼 말이 이어지는 자리는 바꾸지 않는다(파트 메모 1). 바꾼 글에는 다시 걸리는 말이 없다 — '확인하지 않은' 은 어느 패턴에도 맞지 않아 두 번 거쳐도 같다.
- **사용자가 고친 글:** spec 의 '`paragraph_edit.py:192-209`'는 지금 `revalidate`(`:48-65`)다 — 글이 바뀐 문단·새 문단은 이미 `check_paragraph` 를 다시 타므로 코드 변경 없이 테스트로 고정한다.
- **남는 한계(완료노트에 적는다):** 코퍼스 낱말이 앞 문장에만 있고 단정이 다음 문장에 있으면('소장 코퍼스를 살펴보았다. 관련 연구가 없음을 확인했다.') 잡지 못한다. 글이 25자쯤 늘어 문단 상한(`MAX_PARAGRAPH_CHARS` 3000)에 걸릴 수 있다는 것은 기존 `PARAGRAPH_TOO_LONG` 문구(`research_proposal.py:292-296`)가 이미 알린다.

**Files:**
- Modify: `app/services/research_work/markers.py` (머리 docstring·import `:12-18`, 새 상수 `:39` 아래, `soften_claims` `:68-74`)
- Test: `app/tests/test_research_work_markers.py` (import, ＋ `TestGapClaims` — 매개변수 펼쳐 14)
- Test: `app/tests/test_research_work_paragraph_edit.py` (＋ `TestRevalidate.test_a_user_edited_gap_claim_is_softened_again`)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_work_markers.py` — import(`:15-18`). 교체 전:

```python
from services.research_work.markers import (
    CLAIM_REWRITES, FIGURE_MARKER, FigureResult, check_figures, check_paragraph, figure,
    numbers_outside, soften_claims,
)
```

교체 후:

```python
from services.research_work.markers import (
    CLAIM_REWRITES, FIGURE_MARKER, GAP_CLAIM_REWRITES, GAP_CLAIM_TAIL, FigureResult, check_figures,
    check_paragraph, figure, numbers_outside, soften_claims,
)
```

`app/tests/test_research_work_markers.py` — `TestSoftenClaims` 끝(`test_rewrites_are_pattern_and_replacement_pairs` `:137-139`) 뒤에 새 클래스. 교체 전:

```python
    def test_rewrites_are_pattern_and_replacement_pairs(self):
        assert CLAIM_REWRITES and all(
            isinstance(p, str) and isinstance(r, str) for p, r in CLAIM_REWRITES)
```

교체 후:

```python
    def test_rewrites_are_pattern_and_replacement_pairs(self):
        assert CLAIM_REWRITES and all(
            isinstance(p, str) and isinstance(r, str) for p, r in CLAIM_REWRITES)


class TestGapClaims:
    """06e(06b 이월 §7-13) — 소장 코퍼스 범위를 말하는 문장의 '…확인했다'·'…확인되었다' 단정은 '확인하지 않은 공백
    후보' 투로 바꾼다. 문맥은 '코퍼스'·'소장 논문/자료/문헌/학술논문' 낱말이 든 문장뿐이다 — 선행연구 절의 인용
    발견('김(2015)[E1]은 … 분석한 결과 … 확인되었다')은 그대로 둔다(뼈대 정함 10)."""

    TAIL = "(소장 코퍼스에서 확인하지 않은 공백 후보)"

    @pytest.mark.parametrize("text, expected", [
        ("소장 코퍼스를 분석한 결과 노인 우울 연구는 충분하지 않음을 확인했다.",
         f"소장 코퍼스를 분석한 결과 노인 우울 연구는 충분하지 않은 것으로 보인다{TAIL}."),
        ("코퍼스에서 관련 연구가 없음을 확인할 수 있었다.", f"코퍼스에서 관련 연구가 없는 것으로 보인다{TAIL}."),
        ("소장 논문을 검토한 결과 실증 연구가 부족함을 확인하였다.",
         f"소장 논문을 검토한 결과 실증 연구가 부족한 것으로 보인다{TAIL}."),
        ("소장 자료를 조사한 결과 연구가 드문 것으로 확인됐다.", f"소장 자료를 조사한 결과 연구가 드문 것으로 보인다{TAIL}."),
        ("코퍼스를 살펴본 결과 이 공백이 확인되었다.", f"코퍼스를 살펴본 결과 이 공백이 보인다{TAIL}."),
    ], ids=["않음을 확인했다(06b 실제 문장)", "없음을 확인할 수 있었다", "함을 확인하였다", "것으로 확인됐다", "확인되었다"])
    def test_corpus_sentences_become_gap_candidates(self, text, expected):
        softened, n = soften_claims(text)

        assert (softened, n) == (expected, 1)
        assert soften_claims(softened) == (softened, 0)          # 두 번 거쳐도 같다

    @pytest.mark.parametrize("text", [
        "김(2015)[E1]은 노인 300명을 분석한 결과 사회적 지지가 우울을 낮추는 것으로 확인되었다.",
        "분석한 결과 집단 간 차이가 유의함을 확인하였다.",
        "김(2015)[E1]에서 효과가 확인되었다.",
        "효과가 있음을 확인했다.",
        # 코퍼스 문장이라도 문장 끝의 단정만 바꾼다 — '확인되었다는' 처럼 말이 이어지면 그대로
        "소장 코퍼스에서 확인되었다는 점은 한계다.",
    ])
    def test_cited_findings_in_prior_sections_are_left_alone(self, text):
        assert soften_claims(text) == (text, 0)

    def test_only_the_corpus_sentence_of_a_paragraph_changes(self):
        first = "김(2015)[E1]은 노인 300명을 분석한 결과 사회적 지지가 우울을 낮추는 것으로 확인되었다."
        text = f"{first} 소장 코퍼스를 분석한 결과 농촌 노인 연구는 충분하지 않음을 확인했다."

        softened, n = soften_claims(text)

        assert softened == f"{first} 소장 코퍼스를 분석한 결과 농촌 노인 연구는 충분하지 않은 것으로 보인다{self.TAIL}."
        assert n == 1
        # 문단 검사도 같은 글·같은 수 — 절 생성·문단 다시 쓰기·사용자가 고친 글이 모두 check_paragraph 를 탄다
        checked, _, checks = check_paragraph(text, valid_e={"E1"}, valid_f=set(), evidence={"E1": "KCI_A"})
        assert (checked, checks["softened"]) == (softened, 1)

    @pytest.mark.parametrize("text, expected", [
        ("선행연구에서 최초로 우울 감소 효과가 확인되었다.",
         "선행연구에서 소장 코퍼스에서 확인한 범위에서 처음으로 우울 감소 효과가 확인되었다."),
        ("김(2015)[E1]은 농촌 노인에 대한 연구가 거의 없다고 지적했고 지지의 효과가 확인되었다.",
         "김(2015)[E1]은 농촌 노인에 대한 연구를 소장 코퍼스에서 확인하지 못했다고 지적했고 지지의 효과가 확인되었다."),
    ])
    def test_corpus_words_put_in_by_claim_rewrites_are_not_context(self, text, expected):
        # CLAIM_REWRITES 가 넣은 '소장 코퍼스에서 확인…' 의 '코퍼스'로는 인용 발견을 공백 후보로 바꾸지 않는다 — CLAIM 만 한 번
        assert soften_claims(text) == (expected, 1)
        assert soften_claims(expected) == (expected, 0)

    def test_rewrites_are_pattern_and_replacement_pairs(self):
        assert GAP_CLAIM_TAIL == self.TAIL
        assert len(GAP_CLAIM_REWRITES) == 5 and all(
            isinstance(p, str) and isinstance(r, str) and r.endswith(GAP_CLAIM_TAIL) for p, r in GAP_CLAIM_REWRITES)
```

`app/tests/test_research_work_paragraph_edit.py` — `TestRevalidate` 끝(`test_paragraph_with_the_stored_text_keeps_its_stored_checks` 의 끝 단언 `:85-86`) 뒤. 교체 전:

```python
        assert (out[2]["text"], out[2]["state"], out[2]["cites"]) == ("셋째 문단을 고쳤다 [E2].", "edited", ["KCI_B"])
        assert (out[2]["checks"]["dropped"], out[2]["checks"]["dropped_f"], out[2]["checks"]["softened"]) == (1, 0, 0)
```

교체 후:

```python
        assert (out[2]["text"], out[2]["state"], out[2]["cites"]) == ("셋째 문단을 고쳤다 [E2].", "edited", ["KCI_B"])
        assert (out[2]["checks"]["dropped"], out[2]["checks"]["dropped_f"], out[2]["checks"]["softened"]) == (1, 0, 0)

    def test_a_user_edited_gap_claim_is_softened_again(self):
        """06e(06b 이월 §7-13) — 사용자가 고친 글도 생성 때와 같은 검사(check_paragraph)를 다시 탄다. 연구 공백 단정을
        써 넣어도 공백 후보 투로 바뀌고 softened 로 센다(spec 의 'paragraph_edit.py:192-209' 는 지금 revalidate)."""
        paragraphs = [{**_p("p1", "", "edited"), "text": "소장 코퍼스를 분석한 결과 관련 연구가 충분하지 않음을 확인했다 [E1]."}]

        (out,) = revalidate(SECTION, paragraphs)

        assert out["text"] == ("소장 코퍼스를 분석한 결과 관련 연구가 충분하지 않은 것으로 보인다"
                               "(소장 코퍼스에서 확인하지 않은 공백 후보) [E1].")
        assert (out["cites"], out["checks"]["softened"]) == (["KCI_A"], 1)
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_markers.py -q -p no:cacheprovider`
Expected: `Interrupted: 1 error during collection`(끝 줄 `1 error`) — `ImportError: cannot import name 'GAP_CLAIM_REWRITES' from 'services.research_work.markers'`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_paragraph_edit.py -q -p no:cacheprovider`
Expected: `1 failed, 19 passed` — `TestRevalidate::test_a_user_edited_gap_claim_is_softened_again`(글이 그대로 '…않음을 확인했다 [E1].')

- [ ] **Step 3: 구현한다**

`app/services/research_work/markers.py` — 머리 docstring 끝(`:12-14`)과 import(`:15-18`). 교체 전:

```python
- 소장 코퍼스 밖을 단정하는 표현('연구가 없다'·'전무하다'·'최초로')은 "소장 코퍼스에서 확인하지 못했다" 투로
  바꾼다(soften_claims) — 이 시스템은 소장 KCI 적재분만 보았다(spec §4 시연 정직성).
"""
import re
from typing import NamedTuple

from services.research.citations import bind_markers, normalize_markers
```

교체 후:

```python
- 소장 코퍼스 밖을 단정하는 표현('연구가 없다'·'전무하다'·'최초로')은 "소장 코퍼스에서 확인하지 못했다" 투로
  바꾼다(soften_claims) — 이 시스템은 소장 KCI 적재분만 보았다(spec §4 시연 정직성).
- 소장 코퍼스 범위를 말하는 문장('코퍼스'·'소장 논문/자료/문헌' 낱말이 든 문장)의 '…않음을 확인했다'·'…확인되었다'
  단정은 '…것으로 보인다(소장 코퍼스에서 확인하지 않은 공백 후보)' 투로 바꾼다(06e — 06b 이월 §7-13). 확인 검색을
  거치지 않은 공백이라 '확인했다' 고 쓸 수 없다. 인용한 발견('김(2015)[E1]은 … 확인되었다')은 문맥 낱말이 없어 그대로다
  — 위 규칙이 바꿔 넣은 '소장 코퍼스에서 확인…' 의 '코퍼스'는 문맥으로 보지 않는다.
"""
import re
from typing import NamedTuple

from services.research.citations import bind_markers, normalize_markers
from services.research_work.shapes import GAP_NOTE
```

`app/services/research_work/markers.py` — `_REWRITES`(`:39`) 아래에 새 상수. 교체 전:

```python
_REWRITES = tuple((re.compile(pattern), repl) for pattern, repl in CLAIM_REWRITES)
```

교체 후:

```python
_REWRITES = tuple((re.compile(pattern), repl) for pattern, repl in CLAIM_REWRITES)

# 연구 공백 단정(06e) — 이 낱말이 든 문장에서만 바꾼다. '분석한 결과·검토한 결과' 는 선행연구 요약에도 흔해 문맥으로 쓰지 않는다
GAP_CLAIM_CONTEXT = re.compile(r"(?:코퍼스|소장\s*(?:학술논문|논문|자료|문헌))")
GAP_CLAIM_TAIL = f"({GAP_NOTE})"
# 문장 끝 단정만 — 뒤에 한글이 이어지면('확인되었다는 점') 바꾸지 않는다
_CONFIRMED = r"(?:확인했다|확인하였다|확인할 수 있었다|알 수 있었다)(?![가-힣])"
# (정규식, 바꿀 말) — 앞에서부터 차례로. 바꾼 글('…것으로 보인다(…확인하지 않은 공백 후보)')에는 다시 걸리는 말이 없다
GAP_CLAIM_REWRITES: tuple[tuple[str, str], ...] = (
    (rf"않음을\s*{_CONFIRMED}", f"않은 것으로 보인다{GAP_CLAIM_TAIL}"),
    (rf"없음을\s*{_CONFIRMED}", f"없는 것으로 보인다{GAP_CLAIM_TAIL}"),
    (rf"함을\s*{_CONFIRMED}", f"한 것으로 보인다{GAP_CLAIM_TAIL}"),
    (r"것(?:으로|이)\s*확인(?:되었다|됐다)(?![가-힣])", f"것으로 보인다{GAP_CLAIM_TAIL}"),
    (r"확인(?:되었다|됐다)(?![가-힣])", f"보인다{GAP_CLAIM_TAIL}"),
)
_GAP_REWRITES = tuple((re.compile(pattern), repl) for pattern, repl in GAP_CLAIM_REWRITES)
# 문장 경계 — 마침표·물음표·느낌표 뒤 공백. 나눈 공백은 그대로 다시 잇는다(split 의 잡는 괄호)
_SENTENCE_BREAK = re.compile(r"((?<=[.!?。])\s+)")
# CLAIM_REWRITES 가 넣는 말 — 이 말의 '코퍼스'는 문맥으로 보지 않는다(인용 발견이 공백 후보로 바뀌지 않게, 두 번 거쳐도 같게)
_CLAIM_INSERTS = re.compile(r"소장 코퍼스에서 확인(?:하지 못했다|되지 않았다|한 범위에서)")
```

`app/services/research_work/markers.py` — `soften_claims`(`:68-74`). 교체 전:

```python
def soften_claims(text: str) -> tuple[str, int]:
    """소장 코퍼스 밖을 단정하는 표현을 바꾼다. (바꾼 글, 바꾼 수)."""
    total = 0
    for pattern, repl in _REWRITES:
        text, n = pattern.subn(repl, text)
        total += n
    return text, total
```

교체 후:

```python
def soften_claims(text: str) -> tuple[str, int]:
    """소장 코퍼스 밖을 단정하는 표현을 바꾸고, 소장 코퍼스 범위를 말하는 문장의 연구 공백 단정을 공백 후보 투로
    바꾼다. (바꾼 글, 바꾼 수)."""
    total = 0
    for pattern, repl in _REWRITES:
        text, n = pattern.subn(repl, text)
        total += n
    parts = _SENTENCE_BREAK.split(text)
    for i in range(0, len(parts), 2):            # 짝수 자리가 문장, 홀수 자리가 나눈 공백
        # 문맥은 위에서 바꿔 넣은 말을 뺀 문장에서 본다 — 원문에 코퍼스 낱말이 있던 문장만 공백 단정으로 다룬다
        if not GAP_CLAIM_CONTEXT.search(_CLAIM_INSERTS.sub("", parts[i])):
            continue
        for pattern, repl in _GAP_REWRITES:
            parts[i], n = pattern.subn(repl, parts[i])
            total += n
    return "".join(parts), total
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_markers.py tests/test_research_work_paragraph_edit.py -q -p no:cacheprovider`
Expected: `86 passed`(검사 52 + 14 · 문단 고치기 19 + 1 — 기존 `TestSoftenClaims`·공용 고정 예제 `marker_checks.json` 사례는 그대로 통과한다: 원문에 '코퍼스' 낱말이 든 문장이 없고, CLAIM_REWRITES 가 바꿔 넣은 '소장 코퍼스에서 확인하지 못했다' 등은 문맥으로 보지 않는다)

`soften_claims` 를 타는 다른 길(절 생성은 `check_paragraph` 를 거쳐, 주제 카드·직접 쓴 카드는 직접, 계획서 API):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_section.py tests/test_research_work_topic_card.py tests/test_research_topics_api.py tests/test_research_proposal_api.py -q -p no:cacheprovider`
Expected: 실패 0 — 수는 이 Task 전과 같다

- [ ] **Step 5: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`
Expected: `5 failed, (Task 앞 + 15) passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 기준선과 같은 세 파일

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/markers.py && git add app/tests/test_research_work_markers.py && git add app/tests/test_research_work_paragraph_edit.py && git status --short && git commit -m "[Feat] round06e — 연구 공백 단정을 다듬는다(06b 이월 §7-13). 소장 코퍼스 범위를 말하는 문장('코퍼스'·'소장 논문/자료/문헌/학술논문' 낱말이 든 문장)의 '…않음을 확인했다'·'…없음을 확인할 수 있었다'·'…함을 확인하였다'·'…것으로 확인됐다'·'…확인되었다'를 '…것으로 보인다(소장 코퍼스에서 확인하지 않은 공백 후보)' 투로 바꾼다(GAP_CLAIM_REWRITES 다섯 쌍, 문장 끝 단정만). 확인 검색을 거치지 않은 공백이라 '확인했다'고 쓸 수 없다 — 사람의 수락 관문이 빠지는 자동 보고서(D20)라 코드가 고친다. 선행연구 절의 인용 발견('김(2015)[E1]은 … 분석한 결과 … 확인되었다')은 문맥 낱말이 없어 그대로다 — 기존 규칙(CLAIM_REWRITES)이 바꿔 넣은 '소장 코퍼스에서 확인…' 의 '코퍼스'도 문맥으로 보지 않아 '최초로 … 확인되었다' 같은 인용 발견이 공백 후보로 바뀌지 않는다. 두 번 거쳐도 같고, soften_claims 를 타는 절 생성·문단 다시 쓰기·사용자가 고친 글·주제 카드에 함께 걸린다(사용자가 고친 글은 테스트로 고정)"
```

---

### Task X3: 연구 배경·방법 칸 — 승인 상태에서 쓰고 버전 충돌은 한 번 다시

spec §12-4 '방법은 사용자가 쓴다 — 승인 상태에서도 쓸 수 있는 칸을 문서 6절 자리에 두고 `PUT /outline` 에 `approve:true` 를 유지해 저장한다'·'연쇄 중에는 절이 반영될 때마다 version 이 올라 409 `version_conflict` — 응답의 version 으로 한 번 다시 보낸다, 두 번째도 409 면 오류', 연구 배경 칸(§12-11 — 저장은 Task X1), 뼈대 정함 7·8.

- **저장 본문 `fieldPut(outline, { background? | method? })`(1-6 계약):** 저장된 묶음(키·이름·논문 순서)과 연구 질문(`outline.question ?? ""`)을 그대로 싣고 `approve = (outline.state === "approved")` — 승인 목차는 승인 그대로(false 로 보내면 초안이 되어 절 쓰기가 409, `research_proposal.py:264`·`:367`), 06b 의 초안 목차·질문이 없어 초안으로 둔 목차(Task A1)는 초안 그대로. 보내지 않은 방법은 저장된 값, 보내지 않은 배경은 `background` 키를 싣지 않는다(서버가 지킨다 — Task X1). 앞뒤 공백은 뗀다. 묶음 이름은 서버가 이미 정리한 저장 값이라 다시 다듬지 않는다. `toOutlinePut`([목차 고치기])은 배경을 싣지 않는다 — 그대로 두고 테스트로 고정한다.
- **한 번 다시 `putOnceMore(put, version)`:** 첫 409 의 detail 이 `version_conflict` 면(`researchErrors.versionConflict` 가 지금 version 을 준다) 그 version 으로 한 번만 다시 부른다. 절 반영은 목차를 바꾸지 않으므로 같은 본문을 다시 보내도 덮어쓸 것이 없다. 두 번째 409·다른 오류는 그대로 던진다 — 부르는 쪽 `act` 가 지금처럼 `versionConflict` 면 계획서를 다시 읽고 `CONFLICT` 를 알린다(칸은 열린 채 글이 남는다).
- **칸 `DocField.vue`(1-7 계약 props·emit 그대로):** 보기 — 적은 글을 줄마다 문단으로(Word 의 2절·6절과 같은 나눔 `lines`), 비었으면 흐린 '아직 적지 않았습니다.', 그 아래 [적기]/[고치기](글이 있으면 고치기). 편집 — textarea(남은 글자 수, 넘으면 [저장] 꺼짐 — 서버와 같은 코드 포인트·앞뒤 공백 뗀 수), [저장]·[그만두기], Esc 는 그만두기. 저장은 `save` 를 올리고 결과를 기다린다: `busy` 가 풀린 뒤 값이 보낸 글과 같으면 칸을 닫고 [고치기]로 초점을 돌리고, 아니면(실패) 칸·글을 그대로 둔다 — `ProposalSection` 의 고치기 칸과 같은 방식(`pending`·`watch(busy)`, `ProposalSection.vue:404-475`). 예시 연구(`readOnly`)는 보기만이다. `placeholder` 는 textarea 안내 글이다(보기의 빈 글은 위 한 문장 — 자리 제목 `2. 연구 배경`·`6. …` 이 바로 위에 있다).
- **자리:** Task A5 가 그린 문서 2절(`<section id="wk-doc-background">`)·6절(`<section id="wk-doc-method">`)의 `section`·`h3`·id 는 그대로 두고(머리 목차 anchor 가 바뀌지 않는다 — 뼈대 1-7), `h3` 아래 A5 의 글·흐린 안내 두 줄(`<p v-if=…>`·`<p v-else class="rs-muted">…아직 적지 않았습니다.</p>`)만 DocField 로 바꾼다. 2절 칸의 값은 A5 의 `background` computed(`outlineBackground(outline)` — 문자열이 아니면 `""`)를 그대로 받는다 — A5 의 computed 와 `outlineBackground` import 가 쓰는 곳 없이 남지 않게. 칸의 `busy` 는 화면의 `busy || !!outlineGen` — 목차를 다시 만드는 동안 `PUT /outline` 은 409 `OUTLINE_BUSY` 다. 자동 연쇄(Task A4 `useAutoReport`)는 `act`·`busy` 를 쓰지 않으므로 절을 쓰는 동안에도 칸을 저장할 수 있다 — 그 사이 version 충돌은 `putOnceMore` 가 받는다.
- **다시 맞춤 안내:** Task X1 로 연구 질문 바뀜도 절의 '다시 맞춤 필요' 사유가 된다 — `ProposalSection.vue:19-22` 의 안내 '주제나 목차의 묶음이 바뀌었습니다'에 '연구 질문'을 더한다(파트 메모 4).
- **[보고서 다시 만들기] 확인 창:** Task A5 가 두 화면(`ProposalStep.vue`·`ReadingStep.vue`)에 같은 글로 둔 `REMAKE_CONFIRM` 은 '이미 쓴 절은 지우지 않고(주제나 묶음이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다'라 적는다. X1 뒤에는 새 반영이 새 첫 후보를 연구 질문으로 고르므로 06e 에 쓴 절은 질문이 바뀌어도 그 표시가 붙고, 연구 배경은 새 반영이 이어 받는다(Task X1). 두 문구를 같은 새 글로 바꾼다 — '연구 배경은 그대로 둡니다'를 더하고 '주제나 묶음이'를 '주제·묶음·연구 질문이'로. A5 가 바로잡은 '주제'와 '아직 쓰지 않은 절만'(연쇄 대상은 절도 생성 기록도 없는 키 — Task A5 '알아 둘 것'의 확인 창 항목)은 그대로 지킨다.
- **방법 칸이 둘:** [목차 고치기]를 펼치면 `OutlineEditor` 의 방법 칸(06b)도 보인다. 둘 다 같은 `outline.method` 를 저장하고 저장 뒤 계획서를 다시 읽으므로 어긋나지 않는다 — 이 Task 는 OutlineEditor 를 고치지 않는다.
- **알아 둘 것(앞 Task 뒤 기준):** `ProposalStep.vue` 는 Task A5(큰 진행 막대·머리 목차·문서 자리 1·2·5·6·연쇄·[목차 고치기] 토글·버튼 이름·확인 창)가 먼저 고친다. 아래 ProposalStep 의 Edit 는 A5 가 건드리지 않는 자리(컴포넌트 import 줄, `~/utils/outlineEdit` import 줄, `function write(` 머리)와 A5 가 쓴 글(`~/utils/proposalView` import 목록의 두 줄, 문서 2절·6절의 두 줄, `REMAKE_CONFIRM`)을 글자 그대로 잡는다. `ReadingStep.vue` 는 A5(버튼·확인 창·오류 문구) 뒤이고 이 Task 는 `REMAKE_CONFIRM` 한 자리만 고친다 — 그 뒤의 R1(단계 이름)·R5(패널)는 이 자리를 잡지 않는다. `proposalView.ts`·`types/work.ts` 는 Task A3 가 먼저 고친다 — 아래 old 는 A3 가 건드리지 않는 줄이다(`researchErrors` import 는 A3 가 더한 줄 — 없으면 한 줄을 새로 더한다). `.vue` 는 단위 테스트하지 않는다 — 판단은 `fieldPut`·`putOnceMore` 로 빼서 vitest, `.vue` 는 `nuxi typecheck` 오류 0 과 `npm run build` 로 확인한다.

**Files:**
- Modify: `frontend/types/work.ts` (`Outline.background?`, `ProposalSection.basis.question?`, `OutlinePut.background?`)
- Modify: `frontend/utils/outlineEdit.ts` (`OUTLINE_BACKGROUND_MAX` — `:9` 아래, `fieldPut` — `toOutlinePut` `:78-85` 뒤)
- Modify: `frontend/utils/proposalView.ts` (`researchErrors` import, `putOnceMore` — `addParagraph` 뒤)
- Create: `frontend/components/work/DocField.vue`
- Modify: `frontend/components/work/ProposalStep.vue` (import 셋, `REMAKE_CONFIRM`, `saveField`, 문서 2절·6절 자리의 내용)
- Modify: `frontend/components/work/ReadingStep.vue` (`REMAKE_CONFIRM` — A5 뒤 `:96-97`)
- Modify: `frontend/components/work/ProposalSection.vue` (다시 맞춤 안내 `:19-22`)
- Modify: `frontend/assets/css/work.css` (`.wk-docfield*` — 이어 붙이는 자리 표시 줄 위)
- Test: `frontend/tests/unit/outlineEdit.test.ts` (import, ＋ `toOutlinePut` it 하나, ＋ describe `fieldPut — 승인 상태를 지키는 본문` it 넷)
- Test: `frontend/tests/unit/proposalView.test.ts` (import, ＋ describe `putOnceMore — 버전 충돌 한 번 재전송` it 셋)

기준선(Task A5 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 를 +8 한다(`outlineEdit.test.ts` 16 → 21, `proposalView.test.ts` A3 뒤 수 + 3).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/outlineEdit.test.ts` — `~/utils/outlineEdit` import(`:8-19`). 교체 전:

```ts
import {
  OUTLINE_METHOD_MAX,
  OUTLINE_QUESTION_MAX,
  draftFrom,
```

교체 후:

```ts
import {
  OUTLINE_BACKGROUND_MAX,
  OUTLINE_METHOD_MAX,
  OUTLINE_QUESTION_MAX,
  draftFrom,
  fieldPut,
```

`frontend/tests/unit/outlineEdit.test.ts` — describe `toOutlinePut`(`:151-165`) 끝에 it 하나를 더하고, 그 뒤에 describe `fieldPut` 을 더한다. 교체 전:

```ts
    expect(toOutlinePut(d, false).approve).toBe(false);
  });
});
```

교체 후:

```ts
    expect(toOutlinePut(d, false).approve).toBe(false);
  });

  it("연구 배경은 싣지 않는다 — 서버가 저장된 배경을 지킨다([목차 고치기]가 배경을 지우지 않게)", () => {
    expect("background" in toOutlinePut(draft(), true)).toBe(false);
  });
});

describe("fieldPut — 승인 상태를 지키는 본문", () => {
  const approved = outline({
    question: "다듬은 질문?",
    method: "설문 조사",
    state: "approved",
    approved_at: "2026-10-17T01:00:00Z",
    background: "농촌 노인의 고립",
  });

  it("승인한 목차는 approve true — 묶음·논문 순서·연구 질문을 저장된 그대로 싣는다", () => {
    expect(fieldPut(approved, { method: "면담" })).toEqual({
      groups: [
        { key: "prior.g1", name: "노인의 우울", papers: ["KCI_A", "KCI_B", "KCI_C"] },
        { key: "prior.g2", name: "사회적 지지", papers: ["KCI_D", "KCI_E"] },
      ],
      question: "다듬은 질문?",
      method: "면담",
      approve: true,
    });
  });

  it("초안 목차(06b 목차·질문이 없어 초안으로 둔 목차)는 approve false — 칸을 저장해도 승인되지 않는다", () => {
    const put = fieldPut(outline(), { method: "면담" });
    expect([put.approve, put.question]).toEqual([false, ""]);
  });

  it("연구 배경만 보내면 방법은 저장된 값이고, 배경을 보내지 않으면 background 키가 없다", () => {
    expect(fieldPut(approved, { background: "도시 노인과 견준다" })).toMatchObject({
      method: "설문 조사",
      background: "도시 노인과 견준다",
    });
    expect("background" in fieldPut(approved, { method: "면담" })).toBe(false);
  });

  it("앞뒤 공백을 지운다 — 공백뿐이면 그 칸을 비운다", () => {
    expect(fieldPut(approved, { background: "  배경 첫 줄\n둘째 줄 \n" }).background).toBe("배경 첫 줄\n둘째 줄");
    expect(fieldPut(approved, { method: "  면담 \n" }).method).toBe("면담");
    expect(fieldPut(approved, { background: "   " }).background).toBe("");
    expect(OUTLINE_BACKGROUND_MAX).toBe(2000);
  });
});
```

`frontend/tests/unit/proposalView.test.ts` — import 목록의 `  paragraphViews,` 줄(A3 가 이 목록에 이름을 더했어도 이 줄은 그대로 있다). 교체 전:

```ts
  paragraphViews,
```

교체 후:

```ts
  paragraphViews,
  putOnceMore,
```

`frontend/tests/unit/proposalView.test.ts` — describe `절 PUT 본문` 끝(`:320-322`) 뒤에 더한다(A3 가 그 뒤에 describe 를 더했어도 이 자리 그대로). 교체 전:

```ts
    expect(addParagraph(sec, "더한 글.").paragraphs).toHaveLength(4);
  });
});
```

교체 후:

```ts
    expect(addParagraph(sec, "더한 글.").paragraphs).toHaveLength(4);
  });
});

describe("putOnceMore — 버전 충돌 한 번 재전송", () => {
  const conflict = (version: number) => ({
    status: 409,
    data: { detail: { code: "version_conflict", version, message: "다른 곳에서 보고서가 바뀌었습니다" } },
  });

  it("첫 409 version_conflict 는 응답의 version 으로 한 번 더 보낸다", async () => {
    const seen: number[] = [];
    const put = async (v: number): Promise<string> => {
      seen.push(v);
      if (seen.length === 1) throw conflict(9);
      return "저장";
    };
    await expect(putOnceMore(put, 7)).resolves.toBe("저장");
    expect(seen).toEqual([7, 9]);
  });

  it("두 번째도 409 면 그 오류를 던진다 — 부르는 쪽(act)이 다시 읽고 알린다", async () => {
    const seen: number[] = [];
    const second = conflict(10);
    const put = async (v: number): Promise<string> => {
      seen.push(v);
      throw seen.length === 1 ? conflict(9) : second;
    };
    await expect(putOnceMore(put, 7)).rejects.toBe(second);
    expect(seen).toEqual([7, 9]);
  });

  it("버전 충돌이 아닌 오류는 다시 보내지 않고 곧바로 던진다", async () => {
    for (const err of [{ status: 500 }, { status: 409, data: { detail: "목차를 만드는 중입니다" } }, new TypeError("fetch failed")]) {
      const seen: number[] = [];
      const put = async (v: number): Promise<string> => {
        seen.push(v);
        throw err;
      };
      await expect(putOnceMore(put, 7)).rejects.toBe(err);
      expect(seen).toEqual([7]);
    }
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/outlineEdit.test.ts tests/unit/proposalView.test.ts`
Expected: `Test Files  2 failed (2)` / `Tests  7 failed | <X3 앞 두 파일 합 + 1> passed (<X3 앞 두 파일 합 + 8>)`(통합 사본 값 `7 failed | 37 passed (44)` — A3 가 `proposalView.test.ts` 에 더한 it 만큼 passed·합계가 늘어난다). 실패 일곱:
- `fieldPut — 승인 상태를 지키는 본문 > …` 넷 — `TypeError: (0 , fieldPut) is not a function`
- `putOnceMore — 버전 충돌 한 번 재전송 > …` 셋 — `TypeError: (0 , putOnceMore) is not a function`

`toOutlinePut > 연구 배경은 싣지 않는다 …` 는 지금도 통과한다 — [목차 고치기]가 배경을 지우지 않는 것을 고정하는 테스트다.

- [ ] **Step 3: 타입·저장 본문·한 번 다시를 구현한다**

`frontend/types/work.ts` — `Outline` 의 끝(`:193-194` — Task A3 가 그 아래에 `auto?` 를 더했다). 교체 전:

```ts
  // 목차를 만들 때의 핵심 개념
  concepts?: string[];
```

교체 후:

```ts
  // 목차를 만들 때의 핵심 개념
  concepts?: string[];
  // 연구 배경 — 사용자가 문서 2절 자리에 적는 자유 글(06e). 키가 없으면 아직 적지 않았다
  background?: string;
```

`frontend/types/work.ts` — `ProposalSection.basis`(`:220`). 교체 전:

```ts
  basis: { topic_id: number | null; papers: string[] };
```

교체 후:

```ts
  // question — 이 절을 쓸 때의 연구 질문(06e 부터. 06b 절엔 없다 — 바뀌면 서버가 다시 맞춤 필요를 붙인다)
  basis: { topic_id: number | null; papers: string[]; question?: string };
```

`frontend/types/work.ts` — `OutlinePut`(`:281-286`). 교체 전:

```ts
export interface OutlinePut {
  groups: { key: string; name: string; papers: string[] }[];
  question: string;
  method: string;
  approve: boolean;
}
```

교체 후:

```ts
export interface OutlinePut {
  groups: { key: string; name: string; papers: string[] }[];
  question: string;
  method: string;
  approve: boolean;
  // 실을 때만 바뀐다 — 싣지 않으면 서버가 저장된 연구 배경을 지킨다
  background?: string;
}
```

`frontend/utils/outlineEdit.ts` — 상수(`:9`) 아래. 교체 전:

```ts
export const OUTLINE_METHOD_MAX = 1000;
```

교체 후:

```ts
export const OUTLINE_METHOD_MAX = 1000;
export const OUTLINE_BACKGROUND_MAX = 2000;
```

`frontend/utils/outlineEdit.ts` — `toOutlinePut`(`:78-85`) 뒤에 `fieldPut` 을 더한다. 교체 전:

```ts
export function toOutlinePut(d: OutlineDraft, approve: boolean): OutlinePut {
  return {
    groups: d.groups.map((g) => ({ key: g.key, name: g.name.trim(), papers: [...g.papers] })),
    question: d.question.trim(),
    method: d.method.trim(),
    approve,
  };
}
```

교체 후:

```ts
export function toOutlinePut(d: OutlineDraft, approve: boolean): OutlinePut {
  return {
    groups: d.groups.map((g) => ({ key: g.key, name: g.name.trim(), papers: [...g.papers] })),
    question: d.question.trim(),
    method: d.method.trim(),
    approve,
  };
}

// 문서의 연구 배경(2절)·방법(6절) 칸 저장 본문(06e) — 저장된 묶음·논문 순서·연구 질문을 그대로 싣고 승인 상태를 지킨다:
// 승인한 목차는 approve true(false 로 보내면 초안이 되어 절 쓰기가 409), 초안 목차는 false. 보내지 않은 방법은 저장된
// 값을 싣고, 보내지 않은 연구 배경은 키를 싣지 않는다(서버가 저장된 값을 지킨다)
export function fieldPut(outline: Outline, patch: { method?: string; background?: string }): OutlinePut {
  return {
    groups: outline.groups.map((g) => ({ key: g.key, name: g.name, papers: [...g.papers] })),
    question: outline.question ?? "",
    method: (patch.method ?? outline.method).trim(),
    approve: outline.state === "approved",
    ...(patch.background !== undefined ? { background: patch.background.trim() } : {}),
  };
}
```

`frontend/utils/proposalView.ts` — `~/utils/researchErrors` import — Task A3 가 `isNoSectionPapers` 때문에 `httpStatus` 로 더한 줄(그 줄이 없으면 `import { versionConflict } from "~/utils/researchErrors";` 한 줄을 다른 import 아래에 더한다). 교체 전:

```ts
import { httpStatus } from "~/utils/researchErrors";
```

교체 후:

```ts
import { httpStatus, versionConflict } from "~/utils/researchErrors";
```

`frontend/utils/proposalView.ts` — `addParagraph`(`:190-192`) 뒤에 `putOnceMore` 를 더한다. 교체 전:

```ts
export function addParagraph(section: ProposalSection, text: string): SectionPut {
  return { paragraphs: [...section.paragraphs.map(entry), { id: null, text, state: "authored" }] };
}
```

교체 후:

```ts
export function addParagraph(section: ProposalSection, text: string): SectionPut {
  return { paragraphs: [...section.paragraphs.map(entry), { id: null, text, state: "authored" }] };
}

// 연구 배경·방법 저장(PUT /outline) — 보고서를 자동으로 쓰는 동안 절이 반영될 때마다 version 이 올라 409 version_conflict
// 를 받는다. 절 반영은 목차를 바꾸지 않아 덮어쓸 것이 없으므로 응답의 지금 version 으로 한 번만 다시 보낸다(spec §12-4).
// 두 번째 409 와 그 밖의 오류는 그대로 던진다 — 부르는 쪽(ProposalStep act)이 다시 읽고 알린다
export async function putOnceMore<T>(put: (version: number) => Promise<T>, version: number): Promise<T> {
  try {
    return await put(version);
  } catch (e) {
    const current = versionConflict(e);
    if (current === null) throw e;
    return put(current);
  }
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/outlineEdit.test.ts tests/unit/proposalView.test.ts`
Expected: `Test Files  2 passed (2)` / `Tests  <X3 앞 두 파일 합 + 8> passed`(통합 사본 `44 passed (44)`)

- [ ] **Step 5: 화면 — DocField 와 문서 2절·6절 칸**

Create `frontend/components/work/DocField.vue`:

```vue
<!-- frontend/components/work/DocField.vue -->
<!-- 보고서 문서의 사용자 칸(2 연구 배경·6 방법, round06e) — 보기 ↔ [고치기] 편집. 저장은 부르는 쪽(ProposalStep)이
     PUT /outline 으로 하고, 결과가 오면(busy 가 풀리고 값이 보낸 글과 같으면) 칸을 닫고 [고치기]로 초점을 돌린다 -->
<template>
  <div class="wk-docfield">
    <template v-if="editing">
      <label :for="`${fieldId}-text`" class="rs-sr-only">{{ label }} 고치기</label>
      <textarea
        :id="`${fieldId}-text`"
        ref="boxEl"
        v-model="text"
        class="wk-docfield__text"
        rows="5"
        :placeholder="placeholder"
        :disabled="busy"
        :aria-describedby="`${fieldId}-count`"
        @keydown.esc.prevent="cancel"
      />
      <p :id="`${fieldId}-count`" class="wk-docfield__count" :class="{ 'is-over': left < 0 }">
        {{ left < 0 ? `${max}자까지입니다 — ${-left}자를 줄여 주세요` : `${left}자 남음` }}
      </p>
      <div class="rs-card__actions">
        <button type="button" class="rs-btn rs-btn--small" :disabled="busy || left < 0" @click="save">저장</button>
        <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="cancel">그만두기</button>
      </div>
    </template>
    <template v-else>
      <p v-for="(line, i) in lines" :key="i" class="wk-docfield__line">{{ line }}</p>
      <p v-if="!lines.length" class="rs-muted">아직 적지 않았습니다.</p>
      <div v-if="!readOnly" class="rs-card__actions">
        <button ref="editEl" type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="open">
          {{ lines.length ? "고치기" : "적기" }}<span class="rs-sr-only"> {{ label }}</span>
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

const props = defineProps<{
  fieldId: string;
  label: string;
  value: string;
  max: number;
  placeholder: string;
  // 예시 연구는 보기만 — 쓰기 API 가 409 로 막는다
  readOnly: boolean;
  busy: boolean;
}>();
const emit = defineEmits<{ save: [text: string] }>();

const editing = ref(false);
const text = ref("");
const boxEl = ref<HTMLTextAreaElement | null>(null);
const editEl = ref<HTMLButtonElement | null>(null);
// 보낸 글 — 저장이 끝났는지(busy 가 풀린 뒤 값이 이 글과 같은지)로 칸을 닫는다. 실패하면 칸과 글이 그대로 남는다
let pending: string | null = null;

// 사용자가 줄을 나눠 적을 수 있다 — 보기에서는 줄마다 문단(Word 의 2절·6절과 같은 나눔)
const lines = computed(() =>
  props.value
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean),
);
// 서버 상한은 앞뒤 공백을 뗀 글의 코드 포인트 수(파이썬 len)로 본다 — fieldPut 이 떼고 보낸다
const left = computed(() => props.max - Array.from(text.value.trim()).length);

function open(): void {
  text.value = props.value;
  editing.value = true;
  void nextTick(() => boxEl.value?.focus());
}

function close(): void {
  editing.value = false;
  pending = null;
  void nextTick(() => editEl.value?.focus());
}

function cancel(): void {
  if (!props.busy) close();
}

function save(): void {
  const next = text.value.trim();
  if (next === props.value.trim()) {
    close();
    return;
  }
  pending = next;
  emit("save", next);
}

watch(
  () => props.busy,
  (now, was) => {
    if (!was || now || pending === null) return;
    if (props.value.trim() === pending) close();
    else pending = null;
  },
);
</script>
```

`frontend/components/work/ProposalSection.vue` — 다시 맞춤 안내(`:19-22`) — 연구 질문이 바뀐 것도 다시 맞춤 사유가 된다(Task X1). 교체 전:

```vue
    <p v-if="stale" class="rs-muted">
      이 절을 쓴 뒤 주제나 목차의 묶음이 바뀌었습니다. 쓴 문단은 그대로 두었습니다 — 바뀐 목차로 맞추려면 이 절을 다시
      쓰세요.
    </p>
```

교체 후:

```vue
    <p v-if="stale" class="rs-muted">
      이 절을 쓴 뒤 주제나 목차의 묶음·연구 질문이 바뀌었습니다. 쓴 문단은 그대로 두었습니다 — 바뀐 목차로 맞추려면 이
      절을 다시 쓰세요.
    </p>
```

`frontend/assets/css/work.css` — 이어 붙이는 자리 표시 줄(Task A5 뒤에도 파일 맨 끝 줄) 위에 한 묶음. 교체 전:

```css
/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

교체 후:

```css
/* ── 보고서 문서의 사용자 칸(DocField — 2 연구 배경·6 방법, round06e) ── */
.wk-docfield {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.wk-docfield__line {
  margin: 0;
  font-size: 0.7rem;
  line-height: 1.75;
  color: var(--skx-ink);
}
.wk-docfield__text {
  box-sizing: border-box;
  width: 100%;
  padding: 0.4rem 0.5rem;
  font: inherit;
  font-size: 0.65rem;
  line-height: 1.6;
  color: var(--skx-ink);
  background: var(--skx-white);
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-sm);
  resize: vertical;
}
.wk-docfield__count {
  margin: 0;
  font-size: 0.55rem;
  color: var(--skx-gray-1);
  text-align: right;
}
.wk-docfield__count.is-over {
  font-weight: 700;
  color: var(--skx-ink);
}

/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

`frontend/components/work/ProposalStep.vue` — 컴포넌트 import(06b `:104` — A5 뒤 `:176`, A5 가 고치지 않는 줄). 교체 전:

```ts
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
```

교체 후:

```ts
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import DocField from "~/components/work/DocField.vue";
```

같은 파일 — `~/utils/outlineEdit` import(06b `:110`). 교체 전:

```ts
import { isFallbackOutline } from "~/utils/outlineEdit";
```

교체 후:

```ts
import { OUTLINE_BACKGROUND_MAX, OUTLINE_METHOD_MAX, fieldPut, isFallbackOutline } from "~/utils/outlineEdit";
```

같은 파일 — `~/utils/proposalView` import(Task A5 가 `autoChainOn`·`autoTargets` 를 더하며 이미 여러 줄로 편 목록)에 `putOnceMore` 를 이름 알파벳 순 자리(`outlineBackground` 뒤)에 더한다. 목록의 두 줄만 잡는다 — Task X4 는 이 목록의 끝 네 줄(`reportBar,` ~ `} from …`)을 잡아 두 이름을 더 넣으므로 이 교체와 겹치지 않는다. 교체 전:

```ts
  outlineBackground,
  reportBar,
```

교체 후:

```ts
  outlineBackground,
  putOnceMore,
  reportBar,
```

같은 파일 — 확인 창 `REMAKE_CONFIRM`(Task A5 가 쓴 글 — 위 주석 두 줄은 그대로). 교체 전:

```ts
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다. 이미 쓴 절은 지우지 않고(주제나 묶음이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";
```

교체 후:

```ts
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다 — 연구 배경은 그대로 둡니다. 이미 쓴 절은 지우지 않고(주제·묶음·연구 질문이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";
```

같은 파일 — `function write(key: string): void {`(06b `:213`, A5 는 이 함수를 그대로 둔다 — [이 절 쓰기]) 바로 앞에 `saveField` 를 더한다. 교체 전:

```ts
function write(key: string): void {
```

교체 후:

```ts
// 문서의 연구 배경(2절)·방법(6절) 칸 — 승인 상태를 지킨 채(fieldPut) PUT /outline. 보고서를 자동으로 쓰는 동안에는 절이
// 반영될 때마다 version 이 올라 409 version_conflict 가 난다 — 응답의 version 으로 한 번만 다시 보낸다(putOnceMore). 두 번째도
// 409 면 act 가 보고서를 다시 읽고 CONFLICT 를 알린다(칸은 열린 채 글이 남아 다시 저장할 수 있다)
function saveField(field: "background" | "method", text: string): void {
  const p = proposal.value;
  const outline = p?.outline;
  if (!p || !outline) return;
  const patch = field === "background" ? { background: text } : { method: text };
  void act(
    async () => {
      await putOnceMore((v) => api.putOutline(props.jobId, v, fieldPut(outline, patch)), p.version);
      await props.work.reload("proposal");
      say(field === "background" ? "연구 배경을 저장했습니다" : "방법을 저장했습니다");
    },
    field === "background" ? "연구 배경을 저장하지 못했습니다" : "방법을 저장하지 못했습니다",
  );
}

function write(key: string): void {
```

같은 파일 `<template>` — Task A5 가 그린 문서 2절 자리(`<section id="wk-doc-background" …>`)의 `h3` 아래 두 줄(12칸 들여쓰기 — `section`·`h3` 는 그대로). 교체 전:

```vue
            <p v-if="background.trim()" class="wk-doc__text">{{ background }}</p>
            <p v-else class="rs-muted">연구 배경을 아직 적지 않았습니다.</p>
```

교체 후(값은 A5 의 `background` computed — `outlineBackground` 로 읽은 글):

```vue
            <DocField
              field-id="wk-docfield-background"
              label="연구 배경"
              :value="background"
              :max="OUTLINE_BACKGROUND_MAX"
              placeholder="이 연구가 왜 필요한지 — 연구 대상과 문제 상황, 이 주제를 보게 된 맥락을 적습니다. AI 는 이 칸을 쓰지 않습니다."
              :read-only="readOnly"
              :busy="busy || !!outlineGen"
              @save="saveField('background', $event)"
            />
```

같은 파일 `<template>` — 문서 6절 자리(`<section id="wk-doc-method" …>`)의 `h3` 아래 두 줄. 교체 전:

```vue
            <p v-if="proposal.outline.method.trim()" class="wk-doc__text">{{ proposal.outline.method }}</p>
            <p v-else class="rs-muted">방법을 아직 적지 않았습니다.</p>
```

교체 후:

```vue
            <DocField
              field-id="wk-docfield-method"
              label="방법"
              :value="proposal.outline?.method ?? ''"
              :max="OUTLINE_METHOD_MAX"
              placeholder="연구 설계·대상·자료 수집과 분석 방법을 적습니다. AI 는 이 칸을 쓰지 않습니다."
              :read-only="readOnly"
              :busy="busy || !!outlineGen"
              @save="saveField('method', $event)"
            />
```

`frontend/components/work/ReadingStep.vue` — 확인 창 `REMAKE_CONFIRM`(Task A5 가 ProposalStep 과 같은 글로 쓴 자리, A5 뒤 `:96-97` — 위 주석 두 줄은 그대로). 교체 전:

```ts
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다. 이미 쓴 절은 지우지 않고(주제나 묶음이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";
```

교체 후:

```ts
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다 — 연구 배경은 그대로 둡니다. 이미 쓴 절은 지우지 않고(주제·묶음·연구 질문이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";
```

두 칸이 들어갔고 A5 의 흐린 안내 글이 남지 않았는지, 2절 칸이 A5 의 `background` computed 를 쓰는지(`outlineBackground` 는 import 와 computed 두 곳), 두 화면의 확인 창이 같은 새 글인지 본다:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -c "<DocField" components/work/ProposalStep.vue && grep -c "아직 적지 않았습니다" components/work/ProposalStep.vue && grep -c ':value="background"' components/work/ProposalStep.vue && grep -c "outlineBackground" components/work/ProposalStep.vue && grep -c "주제·묶음·연구 질문이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만" components/work/ProposalStep.vue components/work/ReadingStep.vue`
Expected: `2`·`0`·`1`·`2` 다음 `components/work/ProposalStep.vue:1`·`components/work/ReadingStep.vue:1`(빈 칸 안내는 이제 DocField 가 그린다)

- [ ] **Step 6: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <X3 앞과 같은 수> passed` / `Tests <X3 앞 + 8> passed`(dev `da80f23` 에 A3 대역만 얹고 잰 값 `40 passed (40)` / `740 passed (740)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep "Duplicated imports" | grep -c -E "fieldPut|putOnceMore|OUTLINE_BACKGROUND_MAX|DocField"`
Expected: `0`(새 이름이 다른 utils·컴포넌트와 겹치지 않는다 — 기존 `queueLine` 경고 두 줄은 기준선 그대로)

브라우저 확인은 마무리 운영 확인에 넘긴다(로컬 미리보기를 운영 API 에 붙여 저장하면 운영 연구가 바뀐다 — 운영 쓰기 금지). 볼 것: 보고서가 절을 쓰는 동안 2절에 연구 배경을 적어 [저장]하면 '연구 배경을 저장했습니다'가 뜨고 칸이 닫혀 [고치기]에 초점이 온다(연쇄 중 version 충돌을 한 번 다시 보내 넘는다), 6절 방법도 같고 승인이 풀리지 않는다(절 쓰기가 계속된다), 예시 연구는 [고치기]가 없다, Word 2절에 적은 배경이 실린다(Task X5).

- [ ] **Step 7: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/types/work.ts && git add frontend/utils/outlineEdit.ts && git add frontend/utils/proposalView.ts && git add frontend/components/work/DocField.vue && git add frontend/components/work/ProposalStep.vue && git add frontend/components/work/ReadingStep.vue && git add frontend/components/work/ProposalSection.vue && git add frontend/assets/css/work.css && git add frontend/tests/unit/outlineEdit.test.ts && git add frontend/tests/unit/proposalView.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 보고서 문서 2절·6절 자리에 연구 배경·방법 칸(DocField)을 둔다(spec §12-4 연구 배경·방법). 저장 본문 fieldPut 은 저장된 묶음·연구 질문을 그대로 싣고 승인 상태를 지킨다 — 승인 목차는 approve true(false 면 초안이 되어 절 쓰기가 409), 초안 목차는 false, 보내지 않은 배경은 키를 싣지 않아 서버가 지킨다. 보고서를 자동으로 쓰는 동안에는 절이 반영될 때마다 version 이 올라 409 version_conflict 가 나므로 응답의 version 으로 한 번만 다시 보낸다(putOnceMore) — 두 번째도 409 면 지금처럼 다시 읽고 알린다. 칸은 보기 ↔ [고치기] 편집(남은 글자 수, Esc 는 그만두기)이고, 저장이 끝나면 칸을 닫고 [고치기]로 초점을 돌린다. 예시 연구는 보기만이다. 연구 질문이 바뀐 것도 절의 다시 맞춤 사유가 되어 절 안내 문구와 [보고서 다시 만들기] 확인 창(보고서·참고문헌 선택하기 두 화면)에 더하고, 확인 창에 연구 배경은 그대로 둔다고 적는다"
```

---

### Task X4: 검토할 곳 요약

spec §12-4 '검토 단서(제안) — 문서 머리에 "검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m"(누르면 그 자리로)', §12-11 "'검토할 곳' 요약·'근거 없음' 배지·부록 수", 뼈대 정함 11. 수락 관문이 빠지면 코드 검사 표시(`check_paragraph` — 근거 표시 없는 문장 `checks.unmarked`·[F#] 밖 숫자 `checks.numbers`)가 사실상 유일한 검토 단서다.

- **세기 `reviewSpots(p)`(1-6 계약):** `sectionKeysOf(p)`(Task A3 — 목차 묶음 순서 → `gap`) 순서로 저장된 문단의 `checks.unmarked` 합·`checks.numbers.length` 합을 세고, 둘 중 하나라도 있는 첫 문단을 `first: {key, pid}` 로 준다. 목차에서 빠진 옛 절은 세지 않는다(화면·문서에 없다). 흐르는 글(쓰는 중인 절)은 문단이 아직 없어 세지 않는다 — 절이 끝나 다시 읽으면 늘어난다. 직접 쓴 문단의 `checks` 가 비어 있을 수 있어(서버가 다시 검사해 채우기 전 `{}` — `paragraph_edit.merge_paragraphs`) 없는 칸은 0 으로 센다.
- **줄 `reviewLine(r)`:** `검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m` — 0 인 칸은 빼고 둘 다 0 이면 `null`(줄을 그리지 않는다). 같은 줄을 공개 부록에도 싣는다(Task X5 — 정함 11 '부록 수').
- **화면:** Task A5 의 머리 목차(`class="wk-doc__toc"`) 바로 아래에 `<p class="wk-review">` — 줄 글자는 버튼이고 누르면 첫 문단(`[data-anchor="${paraAnchor(key, pid)}"]` — `ProposalSection.vue:80` 이 이미 단다)으로 스크롤하고 초점을 옮긴다. 문단 `li` 는 초점을 받지 못하므로 `tabindex="-1"` 를 단다(파트 메모 5). 그 절을 다시 쓰는 중이라 문단이 그려지지 않았으면 그 절의 제목(`#wk-sec-title-<key>` — Task A5 가 `tabindex="-1"` 를 달았다)으로 간다. 옆에 흐린 한 줄 '코드 검사가 표시한 곳입니다. 원문과 맞는지 확인하세요.'. `role="status"` 는 달지 않는다 — 절이 끝날 때마다 수가 바뀌어 읽기가 쏟아진다.
- **'근거 없음' 배지는 넣지 않는다(정함 11):** 문장마다 배지를 달면 자동 보고서가 배지로 덮인다. 지금의 점선 밑줄(`wk-psec__unmarked`, `title` 만 있다 — 화면낭독기는 `title` 을 읽지 않을 때가 많다)에 화면낭독용 `(근거 표시 없음)` 만 더한다.
- **알아 둘 것(앞 Task 뒤 기준):** `proposalView.ts`·`proposalView.test.ts` 는 Task A3·X3 뒤다 — 새 함수는 X3 의 `putOnceMore` 뒤에, 새 describe 는 X3 의 describe 뒤에 둔다. `ProposalStep.vue` 는 A5·X3 뒤다 — 템플릿 자리는 A5 의 머리 목차 `nav` 끝(`</ol>`·`</nav>`·`</template>` 세 줄), script 자리는 `onMounted(` 호출 앞(A5·X3 가 옮기지 않는다), import 는 X3 이 여러 줄로 편 `~/utils/proposalView` 목록과 X3 이 고친 `~/utils/outlineEdit` 줄을 글자 그대로 잡는다. `ProposalSection.vue` 는 A5(`:5` `h3`·`skipped`·`:195-197`)·X3(`:19-22`) 뒤다 — 이 Task 의 자리(`:75-81` `li`·`:98-114` 문장 span)는 그 Task 들이 건드리지 않는다.

**Files:**
- Modify: `frontend/utils/proposalView.ts` (`ReviewSpots`·`reviewSpots`·`reviewLine` — `putOnceMore` 뒤)
- Modify: `frontend/components/work/ProposalStep.vue` (import 둘, `review`·`reviewText`·`jumpToReview`, 머리 목차 아래 `.wk-review` 줄)
- Modify: `frontend/components/work/ProposalSection.vue` (문단 `li` 의 `tabindex="-1"`, 근거 표시 없는 문장의 sr-only)
- Modify: `frontend/assets/css/work.css` (`.wk-review*`·`.wk-psec__item:focus-visible`)
- Test: `frontend/tests/unit/proposalView.test.ts` (import, ＋ describe `reviewSpots·reviewLine` it 넷)

기준선(Task X3 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 를 +4 한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/proposalView.test.ts` — import 목록의 `  removeParagraph,` 줄. 교체 전:

```ts
  removeParagraph,
```

교체 후:

```ts
  removeParagraph,
  reviewLine,
  reviewSpots,
```

`frontend/tests/unit/proposalView.test.ts` — describe `putOnceMore`(Task X3) 끝 뒤에 더한다. 교체 전:

```ts
      await expect(putOnceMore(put, 7)).rejects.toBe(err);
      expect(seen).toEqual([7]);
    }
  });
});
```

교체 후:

```ts
      await expect(putOnceMore(put, 7)).rejects.toBe(err);
      expect(seen).toEqual([7]);
    }
  });
});

describe("reviewSpots·reviewLine", () => {
  const checked = (unmarked: number, numbers: string[]) => ({ ...NO_CHECKS, unmarked, numbers });

  it("문서 순서(목차 묶음 → 연구 공백)로 세고 첫 자리를 준다", () => {
    const base = proposal({
      gap: section([{ ...para("p1", "proposed"), checks: checked(1, ["2017"]) }], { key: "gap" }),
      "prior.g2": section([para("p1", "accepted"), { ...para("p2", "proposed"), checks: checked(0, ["9", "30"]) }], {
        key: "prior.g2",
      }),
      "prior.g1": section([para("p1", "proposed"), para("p2", "edited")]),
    });
    const groups = [...base.outline!.groups, { key: "prior.g2", name: "사회적 지지", hint: "사회적 지지", papers: ["KCI_B"] }];
    const p = { ...base, outline: { ...base.outline!, groups } };
    expect(reviewSpots(p)).toEqual({ unmarked: 1, numbers: 3, first: { key: "prior.g2", pid: "p2" } });
    expect(reviewLine(reviewSpots(p))).toBe("검토할 곳: 근거 없는 문장 1 · 확인 필요 숫자 3");
  });

  it("0 인 칸은 줄에서 뺀다", () => {
    expect(reviewLine({ unmarked: 2, numbers: 0, first: { key: "gap", pid: "p1" } })).toBe("검토할 곳: 근거 없는 문장 2");
    expect(reviewLine({ unmarked: 0, numbers: 1, first: { key: "gap", pid: "p1" } })).toBe("검토할 곳: 확인 필요 숫자 1");
  });

  it("검토할 곳이 없으면 null", () => {
    const p = proposal({ "prior.g1": section([para("p1", "accepted")]) });
    expect(reviewSpots(p)).toEqual({ unmarked: 0, numbers: 0, first: null });
    expect(reviewLine(reviewSpots(p))).toBeNull();
    expect(reviewLine(reviewSpots(proposal({})))).toBeNull();
  });

  it("목차에서 빠진 옛 절은 세지 않는다 — 문서에 실리지 않고 화면에도 없다", () => {
    const orphan = section([{ ...para("p1", "proposed"), checks: checked(2, ["5"]) }], { key: "prior.g3" });
    expect(reviewSpots(proposal({ "prior.g3": orphan }))).toEqual({ unmarked: 0, numbers: 0, first: null });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/proposalView.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  4 failed | <X4 앞 이 파일의 수> passed (<X4 앞 이 파일의 수 + 4>)`(통합 사본 `4 failed | 23 passed (27)`). 실패 넷은 `reviewSpots·reviewLine > …` — `TypeError: (0 , reviewSpots) is not a function`·`TypeError: (0 , reviewLine) is not a function`

- [ ] **Step 3: 세기·줄을 구현한다**

`frontend/utils/proposalView.ts` — `putOnceMore`(Task X3) 뒤에 더한다. 교체 전:

```ts
    const current = versionConflict(e);
    if (current === null) throw e;
    return put(current);
  }
}
```

교체 후:

```ts
    const current = versionConflict(e);
    if (current === null) throw e;
    return put(current);
  }
}

// 검토할 곳(06e, §12-11 권고) — 수락 관문이 빠진 자동 보고서에서 코드 검사 표시(근거 표시 없는 문장·[F#] 밖 숫자)가 사실상
// 유일한 검토 단서다. 문서가 그리는 절(목차 묶음 → 연구 공백)의 저장된 문단만 센다 — 목차에서 빠진 옛 절은 화면·문서에 없다.
// first 는 둘 중 하나라도 있는 첫 문단(머리 줄을 누르면 그 자리로 간다)
export interface ReviewSpots {
  unmarked: number;
  numbers: number;
  first: { key: string; pid: string } | null;
}

export function reviewSpots(p: ProposalView): ReviewSpots {
  const out: ReviewSpots = { unmarked: 0, numbers: 0, first: null };
  for (const key of sectionKeysOf(p)) {
    for (const para of p.sections[key]?.paragraphs ?? []) {
      // 직접 쓴 문단은 저장 전 checks 가 {} 일 수 있다(서버가 다시 검사해 채운다) — 없는 칸은 0 으로 센다
      const unmarked = para.checks?.unmarked ?? 0;
      const numbers = para.checks?.numbers?.length ?? 0;
      out.unmarked += unmarked;
      out.numbers += numbers;
      if (!out.first && (unmarked || numbers)) out.first = { key, pid: para.id };
    }
  }
  return out;
}

// 머리 한 줄 '검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m' — 0 인 칸은 빼고, 둘 다 0 이면 null(줄을 그리지 않는다).
// 공개 부록에도 같은 줄을 싣는다(proposalDocument.disclosureLines)
export function reviewLine(r: ReviewSpots): string | null {
  const parts = [r.unmarked ? `근거 없는 문장 ${r.unmarked}` : "", r.numbers ? `확인 필요 숫자 ${r.numbers}` : ""].filter(
    Boolean,
  );
  return parts.length ? `검토할 곳: ${parts.join(" · ")}` : null;
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/proposalView.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  <X4 앞 이 파일의 수 + 4> passed`(통합 사본 `27 passed (27)`)

- [ ] **Step 5: 화면 — 머리 '검토할 곳' 줄과 문단 초점**

`frontend/components/work/ProposalStep.vue` — `~/utils/proposalView` import(Task A5 가 여러 줄로 편 목록 — Task X3 이 `putOnceMore` 를 더했다)에 `reviewLine`·`reviewSpots` 를 이름 알파벳 순 자리(`reportBar` 뒤)에 더한다. 교체 전:

```ts
  reportBar,
  sectionLabel,
  type TocItem,
} from "~/utils/proposalView";
```

교체 후:

```ts
  reportBar,
  reviewLine,
  reviewSpots,
  sectionLabel,
  type TocItem,
} from "~/utils/proposalView";
```

같은 파일 — `~/utils/outlineEdit` import(Task X3 이 고친 줄) 바로 앞에 한 줄을 더한다(import 는 경로 알파벳 순 — `~/utils/detailSource` 가 `~/utils/outlineEdit` 앞이다). 교체 전:

```ts
import { OUTLINE_BACKGROUND_MAX, OUTLINE_METHOD_MAX, fieldPut, isFallbackOutline } from "~/utils/outlineEdit";
```

교체 후:

```ts
import { paraAnchor } from "~/utils/detailSource";
import { OUTLINE_BACKGROUND_MAX, OUTLINE_METHOD_MAX, fieldPut, isFallbackOutline } from "~/utils/outlineEdit";
```

같은 파일 — script 의 `onMounted(() => {`(06b `:151`) 바로 앞에 더한다. 교체 전:

```ts
onMounted(() => {
```

교체 후:

```ts
// 검토할 곳(06e) — 머리 한 줄. 누르면 첫 자리로 간다
const review = computed(() => (proposal.value ? reviewSpots(proposal.value) : null));
const reviewText = computed(() => (review.value ? reviewLine(review.value) : null));

// 첫 자리 문단(li — ProposalSection 이 tabindex="-1" 를 단다)으로 스크롤하고 초점을 옮긴다. 그 절을 다시 쓰는 중이라 문단이
// 그려지지 않았으면 그 절의 제목으로 간다
function jumpToReview(): void {
  const first = review.value?.first;
  if (!first) return;
  const el =
    document.querySelector<HTMLElement>(`[data-anchor="${paraAnchor(first.key, first.pid)}"]`) ??
    document.getElementById(`wk-sec-title-${first.key}`);
  if (!el) return;
  el.scrollIntoView({ block: "center" });
  el.focus({ preventScroll: true });
}

onMounted(() => {
```

같은 파일 `<template>` — Task A5 가 그린 머리 목차(`<nav class="rs-card wk-doc__toc" …>`)의 닫는 태그 바로 뒤, 승인 목차 `template` 이 닫히기 전에 더한다(A5 의 큰 진행 막대 `.wk-rbar` 와 머리 목차는 그대로 둔다). 교체 전:

```vue
          </ol>
        </nav>
      </template>
```

교체 후:

```vue
          </ol>
        </nav>
        <p v-if="reviewText" class="wk-review">
          <button type="button" class="wk-review__jump" @click="jumpToReview">
            {{ reviewText }}<span class="rs-sr-only"> — 첫 자리로 가기</span>
          </button>
          <span class="rs-muted">코드 검사가 표시한 곳입니다. 원문과 맞는지 확인하세요.</span>
        </p>
      </template>
```

`frontend/components/work/ProposalSection.vue` — 문단 `li`(`:75-81`)에 `tabindex="-1"` — 머리 '검토할 곳' 줄이 이 문단으로 초점을 옮긴다. 교체 전:

```vue
        class="wk-psec__item"
        :class="`is-${p.state}`"
        :data-anchor="paraAnchor(sectionKey, p.id)"
      >
```

교체 후:

```vue
        class="wk-psec__item"
        :class="`is-${p.state}`"
        :data-anchor="paraAnchor(sectionKey, p.id)"
        tabindex="-1"
      >
```

`frontend/components/work/ProposalSection.vue` — 근거 표시 없는 문장(`:98-114`)의 끝에 화면낭독용 한 마디(뼈대 정함 11 — 보이는 배지는 두지 않는다). 교체 전:

```vue
                  <span v-else class="wk-psec__cite is-pending">[{{ part.fid }}]</span>
                </template>
              </span>
```

교체 후:

```vue
                  <span v-else class="wk-psec__cite is-pending">[{{ part.fid }}]</span>
                </template>
                <span v-if="s.unmarked" class="rs-sr-only">(근거 표시 없음)</span>
              </span>
```

`frontend/assets/css/work.css` — 이어 붙이는 자리 표시 줄 위에 한 묶음(Task X3 의 `.wk-docfield` 묶음 아래). 교체 전:

```css
/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

교체 후:

```css
/* ── 검토할 곳(보고서 머리 한 줄, round06e) — 문단의 '확인 필요' 표시(.wk-psec__check)와 같은 점선 ── */
.wk-review {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  font-size: 0.6rem;
}
.wk-review__jump {
  padding: 0.25rem 0.6rem;
  font: inherit;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--skx-ink);
  background: var(--skx-white);
  border: 1px dashed var(--skx-ink);
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.wk-review__jump:hover {
  background: var(--skx-border-c1);
}
.wk-review__jump:focus-visible,
.wk-psec__item:focus-visible {
  outline: 2px solid var(--skx-border-c2);
  outline-offset: 2px;
}

/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

`.wk-review` 줄이 한 번 들어갔는지 본다:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -c 'class="wk-review"' components/work/ProposalStep.vue && grep -c "(근거 표시 없음)" components/work/ProposalSection.vue`
Expected: `1` 다음 `1`

- [ ] **Step 6: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Tests <X4 앞 + 4> passed`(통합 사본 `744 passed (744)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep "Duplicated imports" | grep -c -E "reviewSpots|reviewLine|ReviewSpots"`
Expected: `0`

브라우저 확인(마무리 운영 확인): 자동으로 쓴 보고서에 근거 표시 없는 문장·[F#] 밖 숫자가 있으면 머리 목차 아래 '검토할 곳: …' 줄이 서고, 누르면 그 문단이 화면 가운데로 오며 키보드로 눌렀으면 초점 테두리가 보인다. 없으면 줄이 없다. 화면낭독기가 밑줄 문장 끝에서 '(근거 표시 없음)'을 읽는다.

- [ ] **Step 7: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/utils/proposalView.ts && git add frontend/components/work/ProposalStep.vue && git add frontend/components/work/ProposalSection.vue && git add frontend/assets/css/work.css && git add frontend/tests/unit/proposalView.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 보고서 머리 목차 아래에 '검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m' 한 줄을 둔다(spec §12-4 검토 단서, §12-11 권고). 수락 관문이 빠진 자동 보고서에서는 코드 검사 표시가 사실상 유일한 검토 단서다. reviewSpots 가 문서가 그리는 절(목차 묶음 → 연구 공백)의 저장된 문단만 세고(목차에서 빠진 옛 절은 세지 않는다) 첫 자리를 주며, 줄을 누르면 그 문단으로 스크롤하고 초점을 옮긴다(문단 li 에 tabindex -1, 문단이 아직 그려지지 않았으면 그 절 제목). 0 인 칸은 빼고 둘 다 0 이면 줄을 그리지 않는다. 문장마다의 '근거 없음' 배지는 자동 보고서를 덮어 넣지 않고, 점선 밑줄 문장에 화면낭독용 '(근거 표시 없음)'만 더한다"
```

---

### Task X5: 내보내기 기본값(D21)·문단 상태 이름

D21, spec §12-4 '내보내기 기본값' 전부·'문단 상태의 보이는 이름'(Q8 동의)·'딥리서치 보고서 내보내기 출력은 그대로', 뼈대 정함 7(Word 2절)·11(부록 수)·13. 06e 는 [보고서 만들기] 한 번으로 절을 자동으로 쓰므로(D20) 지금 기본(수락한 문단만)이면 Word 가 모든 절을 '받아들인 문단이 없습니다'로 낸다(`proposalDocument.ts:39`·`:106-109`).

- **기본 = 네 상태 전부·워터마크 없음:** `ProposalDocInput.includeProposed` → `acceptedOnly: boolean`(기본 false). `shown` = `acceptedOnly ? ACCEPTED_ONLY : ALL_STATES`. `UNREVIEWED_WATERMARK` 와 반환의 `watermark` 키를 지운다 — `ReportDoc.watermark` 필드와 `reportDocx`(`:68-75`)·`ReportPrint.vue:7` 의 그리기는 그대로 둔다(딥리서치 보고서 출력 불변 — 그리기 길은 손으로 만든 문서 모델로 테스트에 남긴다). 파일 이름은 `${FINAL_STEP_NAME}_<주제 앞 20자>_<날짜>.docx`, '수락한 문단만'을 켰을 때만 꼬리 `_수락문단만`.
- **빈 절 문구:** 절이 없거나 문단을 모두 지운 절은 `아직 쓰지 않았습니다.`(그대로), '수락한 문단만'을 켰는데 실을 문단이 없는 절은 `수락한 문단이 없습니다 — '수락한 문단만'을 끄면 AI 작성 문단도 실립니다.`
- **2절 연구 배경(정함 7):** `outline.background`(Task X1·X3)를 적었으면 줄마다 문단, 없으면 흐린 `연구 배경을 아직 적지 않았습니다.` — 6절 방법(`:136`)과 같은 꼴. '다음 단계에서 씁니다'(`NOT_YET` — 쓰는 곳 `:121` 하나)는 D20 으로 다음 단계가 없어 지운다.
- **부록(D21):** `DISCLOSURE_INTRO` 새 글, `disclosureLines(p, acceptedOnly, now)` = `문단 상태: …`(footprintLine — 머리 'AI 작성 n문단 중 …') → 고른 주제의 출처(있을 때) → 절별 `<절 이름>: 문단 N개 — AI 작성·검토 전 p·수락 a·수정 e·직접 작성 u`(0 인 상태는 지금처럼 뺀다, `MIX_LABELS` 순서·이름) → 실은 문단(기본 `모든 문단(검토 전 AI 작성 문단 n개 포함)`, 켜면 `수락·수정·직접 쓴 문단만(검토 전 AI 작성 문단 n개는 싣지 않음)`, n 이 0 이면 `…(검토 전 AI 작성 문단 없음)` — n 은 문서가 그리는 절에서만 센 `printedProposedCount`) → 검토할 곳 `reviewLine(reviewSpots(…))`(Task X4 — 있을 때. 부록은 '이 문서'를 밝히는 줄이라 '수락한 문단만'을 켜면 문서에 실은 문단만 센다 — 빠진 검토 전 문단의 표시는 세지 않는다. 기본이면 화면 머리 줄과 같은 수) → `작성 일시 <한국 시각>` → `결과·논의 미포함 — …`(그대로). 생성 단계·모델·시도 줄(`KIND_LABELS`·`OUTCOME_LABELS`·`stepName`·`stepLine`, `:45-60`·`:252-275`)은 지운다 — `research_generations.model`·`output.attempts` 저장과 `ProposalView.disclosure` 응답은 그대로다.
- **문서 머리:** `metaBlocks` 첫 줄 `${FINAL_STEP_NAME} 초안 · 원 질문 …`. `FINAL_STEP_NAME` 은 조사가 붙지 않는 꼴에만 쓴다(뼈대 정함 1 — 파일 이름 접두·문서 머리).
- **화면:** 문단 상태 띠 `STATE_LABELS.proposed` 'AI 제안 · 검토 전' → 'AI 작성 · 검토 전'(저장 값 그대로), 화면 AI 기여 막대(`AiFootprintMeter` — `footprintLine` 을 그린다)도 'AI 작성 n문단 중'으로 따라온다. 내보내기 카드(`ProposalStep.vue:75-94`)의 체크 `수락한 문단만 싣기 — 검토 전 AI 작성 n문단을 뺍니다`(n 이 0 이면 꺼짐 — 지금처럼), 설명 한 줄, ref `includeProposed` → `acceptedOnly`, `downloadWord` 의 입력 이름과 `console.warn` 글(`'[research] 보고서 내보내기 실패'` — Task R1 의 마지막 grep 이 '계획서'를 찾지 않게).
- **알아 둘 것(앞 Task 뒤 기준):** `proposalDocument.ts` 는 Task A3 가 `printedKeys` 본문(`return sectionKeysOf(p);`)과 `~/utils/proposalView` import(`sectionKeysOf`)를 먼저 고쳤다 — 아래 import old 는 그 뒤의 줄이다(A3 가 줄을 다르게 적었으면 그 목록에 `reviewLine`·`reviewSpots` 두 이름만 더한다). `proposalView.ts` 는 A3·X3·X4 뒤이고 이 Task 는 `footprint` 주석·`footprintLine` 한 줄만 고친다. `ProposalStep.vue` 의 내보내기 카드(`<div class="rs-card wk-proposal__export">`)와 내려받기 script(`includeProposed` ref·`downloadWord`)는 A5·X3·X4 가 옮기지 않는다 — Edit 가 old 를 못 찾으면(들여쓰기가 A5 로 바뀌었으면) 그 블록을 찾아 '교체 후'로 갈음하고 들여쓰기는 그 자리 그대로 둔다. 내보내기 카드의 버튼 줄(`:89-93`)은 고치지 않는다 — Task H3(PDF)이 이 Task 뒤의 `acceptedOnly`·`downloadWord` 글을 old 로 잡는다(아래 교체 후와 글자까지 같아야 한다).
- **딥리서치 보고서 출력 그대로:** `reportDocument.ts`·`reportDocx.ts`·`ReportPrint.vue` 를 고치지 않는다(Step 5 의 `git diff --stat` 확인). 기존 테스트 '보고서 문서 모델은 watermark 키를 만들지 않는다'(`proposalDocument.test.ts:364`)는 그대로 통과한다.

**Files:**
- Modify: `frontend/utils/proposalDocument.ts` (import, 머리 주석·상수·`proposalFileName` `:24-70`, `buildProposalDocument` `:75-78`·`:106-111`·`:120-121`·`:141`·`:149-154`, `disclosureLines` `:157-177` → 새 `disclosureLines`·`includedLine`, `metaBlocks` `:205`, `printedProposedCount` 주석, `stepName`·`stepLine` 삭제)
- Modify: `frontend/utils/proposalView.ts` (`footprint` 주석 `:127`·`footprintLine` `:139`)
- Modify: `frontend/components/work/ProposalSection.vue` (`STATE_LABELS.proposed` `:255-256`, 주석 `:299`)
- Modify: `frontend/components/work/ProposalStep.vue` (내보내기 카드 `:77-88`, 주석 `:139`, `:245`, `downloadWord` `:257`·`:263`)
- Test: `frontend/tests/unit/proposalDocument.test.ts` (✎ it 14·describe 이름 하나, ＋2, −1 — 18 → 19)
- Test: `frontend/tests/unit/proposalView.test.ts` (✎ describe `footprint · footprintLine` 둘째 it)

기준선(Task X4 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 를 +1 한다(`proposalDocument.test.ts` 18 → 19 — '미수락 문단도 넣기' 두 it 을 하나로 합치고, 연구 배경 it 하나와 '수락한 문단만'의 검토할 곳 it 하나를 더한다).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/proposalDocument.test.ts` — 입력의 `includeProposed`·`disclosureLines(p, bool)`·`_미검토포함`·`'미검토 AI 초안'` 을 쓰는 it 은 모두 바뀐다. 뼈대 X5 의 목록에 더해 `buildProposalDocument` 의 둘째 it(참고문헌 `:174`)도 바뀐다 — 기본이 모든 문단이 되어 검토 전 문단이 인용한 KCI_B 가 문서 번호 2 를 받는다(파트 메모 7).

`frontend/tests/unit/proposalDocument.test.ts` — import 에서 지운 상수를 뺀다(`:6-14`). 교체 전:

```ts
import {
  UNREVIEWED_WATERMARK,
  buildProposalDocument,
```

교체 후:

```ts
import {
  buildProposalDocument,
```

`frontend/tests/unit/proposalDocument.test.ts` — `input()` 의 입력 이름(`:123`). 교체 전:

```ts
    includeProposed: false,
```

교체 후:

```ts
    acceptedOnly: false,
```

`frontend/tests/unit/proposalDocument.test.ts` — describe `buildProposalDocument` 첫 it(`:144-160`) — 이름과 기대 줄. 교체 전:

```ts
  it("6절을 목차 순서로 싣고 기본은 받아들인 문단만 — 검토 전 문단·워터마크는 없다", () => {
    const doc = buildProposalDocument(input(), NOW);
    expect(lines(doc).filter((l) => !l.startsWith("meta") && !l.startsWith("bullets"))).toEqual([
      "title: 세대 간 지지와 노인 우울",
      "heading1: 1. 주제",
      "para: 세대 간 지지와 노인 우울",
      "heading1: 2. 연구 배경",
      "para~: 이 초안에는 아직 없습니다 — 다음 단계에서 씁니다.",
      "heading1: 3. 선행연구 검토",
      "heading2: 3.1 노인의 우울",
      "para: 노인 우울 연구는 6편이다 [1].",
      "heading2: 3.2 사회적 지지",
      "para: 지지는 우울을 낮춘다 [1][2].",
      "heading1: 4. 연구 공백",
      "para~: 소장 코퍼스에서 확인하지 않은 공백 후보로만 적은 절입니다.",
      "para: 직접 쓴 공백 문단이다.",
      "heading1: 5. 연구 질문",
```

교체 후:

```ts
  it("기본은 네 상태 문단을 모두 싣고 워터마크가 없다", () => {
    const doc = buildProposalDocument(input(), NOW);
    expect(lines(doc).filter((l) => !l.startsWith("meta") && !l.startsWith("bullets"))).toEqual([
      "title: 세대 간 지지와 노인 우울",
      "heading1: 1. 주제",
      "para: 세대 간 지지와 노인 우울",
      "heading1: 2. 연구 배경",
      "para~: 연구 배경을 아직 적지 않았습니다.",
      "heading1: 3. 선행연구 검토",
      "heading2: 3.1 노인의 우울",
      "para: 노인 우울 연구는 6편이다 [1].",
      "para: 검토 전 문단이다 [2].",
      "heading2: 3.2 사회적 지지",
      "para: 지지는 우울을 낮춘다 [1][3].",
      "heading1: 4. 연구 공백",
      "para~: 소장 코퍼스에서 확인하지 않은 공백 후보로만 적은 절입니다.",
      "para: 직접 쓴 공백 문단이다.",
      "para: 검토 전 공백이다 [2].",
      "heading1: 5. 연구 질문",
```

`frontend/tests/unit/proposalDocument.test.ts` — 같은 it 의 파일 이름(`:171`)과 다음 it 의 참고문헌(`:174-180` — 기본이 모든 문단이라 검토 전 문단이 인용한 KCI_B 가 2번이 된다). 교체 전:

```ts
    expect("watermark" in doc).toBe(false);
    expect(doc.fileName).toBe("연구계획서_세대_간_지지와_노인_우울_20261014.docx");
  });

  it("인용 번호는 논문마다 문서에 처음 나온 순서이고 참고문헌 글은 서버가 만든 것을 쓴다", () => {
    const doc = buildProposalDocument(input(), NOW);
    expect(doc.references).toEqual([
      { n: 1, eid: "KCI_A", text: "김철수 (2015). 노인 우울 연구. 노년학. UCI I410-1" },
      { n: 2, eid: "KCI_C", text: "사회적 지지 척도." },
    ]);
  });
```

교체 후:

```ts
    expect("watermark" in doc).toBe(false);
    expect(doc.fileName).toBe("보고서_세대_간_지지와_노인_우울_20261014.docx");
  });

  it("인용 번호는 논문마다 문서에 처음 나온 순서이고 참고문헌 글은 서버가 만든 것을 쓴다", () => {
    const doc = buildProposalDocument(input(), NOW);
    expect(doc.references).toEqual([
      { n: 1, eid: "KCI_A", text: "김철수 (2015). 노인 우울 연구. 노년학. UCI I410-1" },
      { n: 2, eid: "KCI_B", text: "이영희 (2012). 가족 지지. UCI I410-2" },
      { n: 3, eid: "KCI_C", text: "사회적 지지 척도." },
    ]);
  });
```

`frontend/tests/unit/proposalDocument.test.ts` — meta it(`:185`). 교체 전:

```ts
      "연구계획서 초안 · 원 질문 노인의 우울과 사회적 지지에 관한 연구가 궁금해",
```

교체 후:

```ts
      "보고서 초안 · 원 질문 노인의 우울과 사회적 지지에 관한 연구가 궁금해",
```

`frontend/tests/unit/proposalDocument.test.ts` — '미수락 문단도 넣기' 두 it(`:194-211`)을 하나로 갈음하고, 흐린 안내 it(`:213-226`)을 고치고, 연구 배경 it 을 더한다. 교체 전:

```ts
  it("미수락 문단도 넣으면 검토 전 문단이 실리고 워터마크·파일 이름 꼬리가 붙는다", () => {
    const doc = buildProposalDocument(input({ includeProposed: true }), NOW);
    expect(lines(doc)).toContain("para: 검토 전 문단이다 [2].");
    expect(lines(doc)).toContain("para: 검토 전 공백이다 [2].");
    expect(doc.watermark).toBe(UNREVIEWED_WATERMARK);
    expect(doc.fileName).toBe("연구계획서_세대_간_지지와_노인_우울_20261014_미검토포함.docx");
    expect(doc.references.map((r) => r.eid)).toEqual(["KCI_A", "KCI_B", "KCI_C"]);
  });

  it("켜도 검토 전 문단이 하나도 없으면 워터마크를 달지 않는다", () => {
    const p = proposal();
    const sections = Object.fromEntries(
      Object.entries(p.sections).map(([k, s]) => [k, { ...s, paragraphs: s.paragraphs.filter((x) => x.state !== "proposed") }]),
    );
    const doc = buildProposalDocument(input({ includeProposed: true, proposal: { ...p, sections } }), NOW);
    expect("watermark" in doc).toBe(false);
    expect(doc.fileName.endsWith("_20261014.docx")).toBe(true);
  });

  it("쓰지 않은 절·받아들인 문단이 없는 절·목차가 없는 계획서는 흐린 안내로 둔다", () => {
    const p = proposal();
    const onlyProposed = { ...p, sections: { "prior.g1": p.sections["prior.g1"]!, gap: { ...p.sections.gap!, paragraphs: [para("p2", "proposed", "x [E1].")] } } };
    const out = lines(buildProposalDocument(input({ proposal: onlyProposed }), NOW));
    expect(out).toContain("para~: 아직 쓰지 않았습니다.");
    expect(out).toContain("para~: 받아들인 문단이 없습니다 — 화면에서 [수락]하거나 '미수락 문단도 넣기'를 켜면 실립니다.");

    const empty = lines(buildProposalDocument(input({ proposal: proposal({ outline: null, sections: {} }) }), NOW));
    expect(empty[0]).toBe("title: 노인의 우울과 사회적 지지에 관한 연구가 궁금해");
    expect(empty).toContain("para~: 주제를 아직 고르지 않았습니다.");
    expect(empty).toContain("para~: 목차를 아직 만들지 않았습니다.");
    expect(empty).toContain("para~: 목차에서 연구 질문을 아직 정하지 않았습니다.");
    expect(empty).toContain("para~: 방법을 아직 적지 않았습니다.");
  });
```

교체 후:

```ts
  it("'수락한 문단만'을 켜면 수락·수정·직접 작성만 — 워터마크 없음·파일 이름 꼬리 _수락문단만", () => {
    const doc = buildProposalDocument(input({ acceptedOnly: true }), NOW);
    const out = lines(doc);
    expect(out.some((l) => l.startsWith("para: 검토 전"))).toBe(false);
    expect(out).toContain("para: 노인 우울 연구는 6편이다 [1].");
    expect(out).toContain("para: 지지는 우울을 낮춘다 [1][2].");
    expect(out).toContain("para: 직접 쓴 공백 문단이다.");
    expect("watermark" in doc).toBe(false);
    expect(doc.fileName).toBe("보고서_세대_간_지지와_노인_우울_20261014_수락문단만.docx");
    expect(doc.references.map((r) => r.eid)).toEqual(["KCI_A", "KCI_C"]);
  });

  it("쓰지 않은 절·'수락한 문단만'에 실을 문단이 없는 절·목차가 없는 보고서는 흐린 안내로 둔다", () => {
    const p = proposal();
    const onlyProposed = { ...p, sections: { "prior.g1": p.sections["prior.g1"]!, gap: { ...p.sections.gap!, paragraphs: [para("p2", "proposed", "x [E1].")] } } };
    const out = lines(buildProposalDocument(input({ proposal: onlyProposed, acceptedOnly: true }), NOW));
    expect(out).toContain("para~: 아직 쓰지 않았습니다.");
    expect(out).toContain("para~: 수락한 문단이 없습니다 — '수락한 문단만'을 끄면 AI 작성 문단도 실립니다.");
    // 기본(모든 문단)이면 같은 절의 검토 전 문단이 실리고 안내가 없다
    const all = lines(buildProposalDocument(input({ proposal: onlyProposed }), NOW));
    expect(all).toContain("para: x [2].");
    expect(all.some((l) => l.includes("수락한 문단이 없습니다"))).toBe(false);
    // 문단을 모두 지운 절은 쓰지 않은 절과 같다 — '수락한 문단만'을 꺼도 켜도 같은 안내
    const emptied = { ...p, sections: { ...p.sections, gap: { ...p.sections.gap!, paragraphs: [] } } };
    for (const acceptedOnly of [false, true]) {
      const shown = lines(buildProposalDocument(input({ proposal: emptied, acceptedOnly }), NOW));
      expect(shown.filter((l) => l === "para~: 아직 쓰지 않았습니다.")).toHaveLength(1);
    }

    const empty = lines(buildProposalDocument(input({ proposal: proposal({ outline: null, sections: {} }) }), NOW));
    expect(empty[0]).toBe("title: 노인의 우울과 사회적 지지에 관한 연구가 궁금해");
    expect(empty).toContain("para~: 주제를 아직 고르지 않았습니다.");
    expect(empty).toContain("para~: 연구 배경을 아직 적지 않았습니다.");
    expect(empty).toContain("para~: 목차를 아직 만들지 않았습니다.");
    expect(empty).toContain("para~: 목차에서 연구 질문을 아직 정하지 않았습니다.");
    expect(empty).toContain("para~: 방법을 아직 적지 않았습니다.");
  });

  it("연구 배경을 적으면 2절에 싣고, 없으면 흐린 안내 — '다음 단계에서 씁니다'는 없다", () => {
    const p = proposal();
    const written = { ...p, outline: { ...p.outline!, background: "농촌 독거노인이 늘고 있다.\n\n 지지망 연구는 도시에 몰려 있다. " } };
    const out = lines(buildProposalDocument(input({ proposal: written }), NOW));
    const at = out.indexOf("heading1: 2. 연구 배경");
    expect(out.slice(at + 1, at + 4)).toEqual([
      "para: 농촌 독거노인이 늘고 있다.",
      "para: 지지망 연구는 도시에 몰려 있다.",
      "heading1: 3. 선행연구 검토",
    ]);
    const blank = { ...p, outline: { ...p.outline!, background: "   " } };
    expect(lines(buildProposalDocument(input({ proposal: blank }), NOW))).toContain("para~: 연구 배경을 아직 적지 않았습니다.");
    expect(lines(buildProposalDocument(input(), NOW)).some((l) => l.includes("다음 단계에서 씁니다"))).toBe(false);
  });
```

`frontend/tests/unit/proposalDocument.test.ts` — describe `disclosureLines` 전체(`:238-289`). 교체 전:

```ts
describe("disclosureLines", () => {
  it("문단 상태 비율·절별 상태·실은 문단·생성 단계·결과·논의 미포함을 싣는다", () => {
    expect(disclosureLines(proposal(), false)).toEqual([
      "문단 상태: AI 제안 4문단 중 수락 1·수정 1·검토 전 2 · 직접 쓴 문단 1",
      "선행연구 검토 · 노인의 우울: 문단 2개 — 수락 1·검토 전 1",
      "선행연구 검토 · 사회적 지지: 문단 1개 — 수정 1",
      "연구 공백: 문단 2개 — 직접 작성 1·검토 전 1",
      "이 문서에 실은 문단: 수락·수정·직접 쓴 문단(검토 전 AI 제안은 싣지 않음)",
      `목차: gemma-3-12b · ${kstDateTime(new Date("2026-10-14T05:05:00Z"))}`,
      `절 초안(선행연구 검토 · 노인의 우울): gemma-3-12b · ${kstDateTime(new Date("2026-10-14T05:20:00Z"))} — 시도 2회: gemma-3-12b 끊김 → gemma-3-12b 완료`,
      "문단 다시 쓰기(연구 공백 p2): 모델 출력 없음(기본값으로 채움) · 완료 시각 기록 없음",
      "결과·논의 미포함 — 결과·논의·가설 수치는 AI 가 쓰지 않았고 이 문서에도 없습니다.",
    ]);
  });

  it("미수락 문단을 넣으면 그 수와 워터마크를 적는다", () => {
    expect(disclosureLines(proposal(), true)).toContain(
      "이 문서에 실은 문단: 수락·수정·직접 쓴 문단과 검토 전 AI 제안 2문단(쪽마다 '미검토 AI 초안' 표시)",
    );
  });

  it("실은 문단 수는 문서가 그리는 절에서만 센다 — 목차에서 빠진 옛 절의 검토 전 문단은 워터마크처럼 세지 않는다", () => {
    // (a) 옛 절(prior.g3)에 검토 전 문단이 남아 있어도 실은 수는 목차 묶음·연구 공백의 2문단이다
    const p = proposal();
    const withOrphan = {
      ...p,
      sections: { ...p.sections, "prior.g3": section("prior.g3", { E1: "KCI_C" }, [para("p1", "proposed", "옛 절 [E1].")]) },
    };
    expect(disclosureLines(withOrphan, true)).toContain(
      "이 문서에 실은 문단: 수락·수정·직접 쓴 문단과 검토 전 AI 제안 2문단(쪽마다 '미검토 AI 초안' 표시)",
    );

    // (b) 검토 전 문단이 옛 절에만 있으면 문서에 싣지 않으므로 워터마크도, 실었다는 줄도 없다
    const printed = Object.fromEntries(
      Object.entries(withOrphan.sections).map(([k, s]) => [
        k,
        k === "prior.g3" ? s : { ...s, paragraphs: s.paragraphs.filter((x) => x.state !== "proposed") },
      ]),
    );
    const orphanOnly = { ...withOrphan, sections: printed };
    expect(disclosureLines(orphanOnly, true)).toContain("이 문서에 실은 문단: 수락·수정·직접 쓴 문단(검토 전 AI 제안은 싣지 않음)");
    expect("watermark" in buildProposalDocument(input({ includeProposed: true, proposal: orphanOnly }), NOW)).toBe(false);
  });

  it("고른 주제의 출처를 문단 상태 다음 줄에 적는다 — 출처를 모르면 적지 않는다", () => {
    const second = (source: ProposalView["topic_source"]) => disclosureLines(proposal({ topic_source: source }), false)[1];
    expect(second({ origin: "user", edited: false })).toBe("주제: 사용자가 직접 쓴 주제");
    expect(second({ origin: "report_seed", edited: true })).toBe("주제: AI 주제 카드(사용자가 고침)");
    expect(second({ origin: "other", edited: false })).toBe("주제: AI 주제 카드");
    expect(second(null)).toBe("선행연구 검토 · 노인의 우울: 문단 2개 — 수락 1·검토 전 1");
  });
});
```

교체 후:

```ts
describe("disclosureLines", () => {
  it("상태별 개수·실은 문단·검토할 곳·날짜·결과·논의 미포함 — 모델·시도 줄은 없다", () => {
    const p = proposal();
    // 연구 공백 1번째 문단에 코드 검사 표시(근거 표시 없는 문장 1·[F#] 밖 숫자 1)가 있다
    const flagged = { ...NO_CHECKS, unmarked: 1, numbers: ["2017"] };
    const gap = { ...p.sections.gap!, paragraphs: p.sections.gap!.paragraphs.map((x) => (x.id === "p1" ? { ...x, checks: flagged } : x)) };
    const out = disclosureLines({ ...p, sections: { ...p.sections, gap } }, false, NOW);
    expect(out).toEqual([
      "문단 상태: AI 작성 4문단 중 수락 1·수정 1·검토 전 2 · 직접 쓴 문단 1",
      "선행연구 검토 · 노인의 우울: 문단 2개 — AI 작성·검토 전 1·수락 1",
      "선행연구 검토 · 사회적 지지: 문단 1개 — 수정 1",
      "연구 공백: 문단 2개 — AI 작성·검토 전 1·직접 작성 1",
      "이 문서에 실은 문단: 모든 문단(검토 전 AI 작성 문단 2개 포함)",
      "검토할 곳: 근거 없는 문장 1 · 확인 필요 숫자 1",
      `작성 일시 ${kstDateTime(NOW)}`,
      "결과·논의 미포함 — 결과·논의·가설 수치는 AI 가 쓰지 않았고 이 문서에도 없습니다.",
    ]);
    // 생성 기록(disclosure.steps — 모델·시도)은 저장돼 있어도 싣지 않는다(D21)
    expect(out.some((l) => l.includes("gemma") || l.includes("시도"))).toBe(false);
    // 검토할 곳이 없으면 그 줄이 없다
    expect(disclosureLines(p, false, NOW).some((l) => l.startsWith("검토할 곳"))).toBe(false);
  });

  it("'수락한 문단만'을 켜면 싣지 않은 검토 전 AI 작성 문단 수를 적는다", () => {
    expect(disclosureLines(proposal(), true, NOW)).toContain(
      "이 문서에 실은 문단: 수락·수정·직접 쓴 문단만(검토 전 AI 작성 문단 2개는 싣지 않음)",
    );
  });

  it("'수락한 문단만'을 켜면 검토할 곳도 문서에 실은 문단에서만 센다 — 빠진 검토 전 문단의 표시는 세지 않는다", () => {
    const p = proposal();
    // 검토 전(proposed) 문단인 '선행연구 검토 · 노인의 우울' p2 에만 근거 표시 없는 문장 1
    const g1 = p.sections["prior.g1"]!;
    const flagged = {
      ...g1,
      paragraphs: g1.paragraphs.map((q) => (q.id === "p2" ? { ...q, checks: { ...NO_CHECKS, unmarked: 1 } } : q)),
    };
    const withFlag = { ...p, sections: { ...p.sections, "prior.g1": flagged } };
    expect(disclosureLines(withFlag, false, NOW)).toContain("검토할 곳: 근거 없는 문장 1");
    expect(disclosureLines(withFlag, true, NOW).some((l) => l.startsWith("검토할 곳"))).toBe(false);
  });

  it("실은 문단 수는 문서가 그리는 절에서만 센다 — 목차에서 빠진 옛 절의 검토 전 문단은 세지 않는다", () => {
    // (a) 옛 절(prior.g3)에 검토 전 문단이 남아 있어도 수는 목차 묶음·연구 공백의 2문단이다
    const p = proposal();
    const withOrphan = {
      ...p,
      sections: { ...p.sections, "prior.g3": section("prior.g3", { E1: "KCI_C" }, [para("p1", "proposed", "옛 절 [E1].")]) },
    };
    expect(disclosureLines(withOrphan, true, NOW)).toContain(
      "이 문서에 실은 문단: 수락·수정·직접 쓴 문단만(검토 전 AI 작성 문단 2개는 싣지 않음)",
    );
    expect(disclosureLines(withOrphan, false, NOW)).toContain("이 문서에 실은 문단: 모든 문단(검토 전 AI 작성 문단 2개 포함)");

    // (b) 검토 전 문단이 옛 절에만 있으면 문서가 그리는 절에는 없다
    const printed = Object.fromEntries(
      Object.entries(withOrphan.sections).map(([k, s]) => [
        k,
        k === "prior.g3" ? s : { ...s, paragraphs: s.paragraphs.filter((x) => x.state !== "proposed") },
      ]),
    );
    const orphanOnly = { ...withOrphan, sections: printed };
    expect(disclosureLines(orphanOnly, true, NOW)).toContain("이 문서에 실은 문단: 수락·수정·직접 쓴 문단만(검토 전 AI 작성 문단 없음)");
    expect(disclosureLines(orphanOnly, false, NOW)).toContain("이 문서에 실은 문단: 모든 문단(검토 전 AI 작성 문단 없음)");
  });

  it("고른 주제의 출처를 문단 상태 다음 줄에 적는다 — 출처를 모르면 적지 않는다", () => {
    const second = (source: ProposalView["topic_source"]) => disclosureLines(proposal({ topic_source: source }), false, NOW)[1];
    expect(second({ origin: "user", edited: false })).toBe("주제: 사용자가 직접 쓴 주제");
    expect(second({ origin: "report_seed", edited: true })).toBe("주제: AI 주제 카드(사용자가 고침)");
    expect(second({ origin: "other", edited: false })).toBe("주제: AI 주제 카드");
    expect(second(null)).toBe("선행연구 검토 · 노인의 우울: 문단 2개 — AI 작성·검토 전 1·수락 1");
  });
});
```

`frontend/tests/unit/proposalDocument.test.ts` — describe `printedKeys·printedProposedCount` 의 둘째·셋째 it(`:315-333`) — 첫 it(`:309`)은 그대로. 교체 전:

```ts
  it("검토 전 문단은 문서가 그리는 절에서만 센다 — 옛 절에만 남은 검토 전 문단은 0 이고 워터마크도 없다", () => {
    expect(printedProposedCount(proposal())).toBe(2);
    expect(printedProposedCount(withOrphan(proposal()))).toBe(2);

    const orphanOnly = withoutPrintedProposed(withOrphan(proposal()));
    expect(printedProposedCount(orphanOnly)).toBe(0);
    expect("watermark" in buildProposalDocument(input({ includeProposed: true, proposal: orphanOnly }), NOW)).toBe(false);
    expect(printedProposedCount(proposal({ outline: null, sections: {} }))).toBe(0);
  });

  it("미수락 문단을 켰을 때 워터마크·파일 이름 꼬리·공개 부록의 실은 수가 이 수와 맞는다", () => {
    for (const p of [proposal(), withOrphan(proposal()), withoutPrintedProposed(withOrphan(proposal()))]) {
      const n = printedProposedCount(p);
      const doc = buildProposalDocument(input({ includeProposed: true, proposal: p }), NOW);
      expect("watermark" in doc).toBe(n > 0);
      expect(doc.fileName.endsWith("_미검토포함.docx")).toBe(n > 0);
      expect(disclosureLines(p, true).some((l) => l.includes(`검토 전 AI 제안 ${n}문단(`))).toBe(n > 0);
    }
  });
});
```

교체 후:

```ts
  it("검토 전 문단은 문서가 그리는 절에서만 센다 — 옛 절에만 남은 검토 전 문단은 0", () => {
    expect(printedProposedCount(proposal())).toBe(2);
    expect(printedProposedCount(withOrphan(proposal()))).toBe(2);
    expect(printedProposedCount(withoutPrintedProposed(withOrphan(proposal())))).toBe(0);
    expect(printedProposedCount(proposal({ outline: null, sections: {} }))).toBe(0);
  });

  it("'수락한 문단만'을 켰을 때 빠지는 수·파일 이름 꼬리 _수락문단만·공개 부록의 싣지 않은 수가 이 수와 맞는다", () => {
    // 본문 문단(흐리지 않은 para) 수 — 이 고정 예제의 문단은 줄바꿈이 없어 문단 하나가 한 줄이다
    const body = (d: ReportDoc) => d.blocks.filter((b) => b.type === "para" && !b.muted).length;
    for (const p of [proposal(), withOrphan(proposal()), withoutPrintedProposed(withOrphan(proposal()))]) {
      const n = printedProposedCount(p);
      const all = buildProposalDocument(input({ proposal: p }), NOW);
      const only = buildProposalDocument(input({ acceptedOnly: true, proposal: p }), NOW);
      expect(body(all) - body(only)).toBe(n);
      expect(only.fileName.endsWith("_수락문단만.docx")).toBe(true);
      expect(all.fileName.endsWith("_수락문단만.docx")).toBe(false);
      expect("watermark" in only || "watermark" in all).toBe(false);
      expect(disclosureLines(p, true, NOW).some((l) => l.includes(`검토 전 AI 작성 문단 ${n}개는 싣지 않음`))).toBe(n > 0);
    }
  });
});
```

`frontend/tests/unit/proposalDocument.test.ts` — describe `proposalFileName`(`:336-342`)과 워터마크 describe 의 이름·앞 두 it(`:344-362`) — 셋째 it '보고서 문서 모델은 watermark 키를 만들지 않는다'(`:364`)는 그대로. 교체 전:

```ts
describe("proposalFileName", () => {
  it("주제 앞 20자·한국 날짜·미검토 꼬리 — 파일 이름에 못 쓰는 글자는 뺀다", () => {
    expect(proposalFileName("노인 우울/사회적 지지: 연구?", NOW, false)).toBe("연구계획서_노인_우울사회적_지지_연구_20261014.docx");
    expect(proposalFileName("가".repeat(30), NOW, true)).toBe(`연구계획서_${"가".repeat(20)}_20261014_미검토포함.docx`);
    expect(proposalFileName("  ", NOW, false)).toBe("연구계획서_초안_20261014.docx");
  });
});

describe("계획서 Word 의 워터마크", () => {
  async function unzip(target: ReportDoc): Promise<JSZip> {
    return JSZip.loadAsync(await (await toDocxBlob(target)).arrayBuffer());
  }

  it("워터마크가 있으면 쪽마다 쓰는 머리글에 회색 굵은 글로 싣는다", async () => {
    const zip = await unzip(buildProposalDocument(input({ includeProposed: true }), NOW));
    const headers = Object.keys(zip.files).filter((name) => /^word\/header\d+\.xml$/.test(name));
    expect(headers.length).toBeGreaterThan(0);
    const xml = (await zip.file(headers[0]!)?.async("string")) ?? "";
    expect(xml).toContain(UNREVIEWED_WATERMARK);
    expect(xml).toContain("<w:b/>");
    expect(xml).toContain('<w:color w:val="999999"/>');
  });

  it("워터마크가 없으면 머리글을 만들지 않는다 — 보고서 문서와 같은 구성", async () => {
    const zip = await unzip(buildProposalDocument(input(), NOW));
    expect(Object.keys(zip.files).filter((name) => /^word\/header\d+\.xml$/.test(name))).toEqual([]);
  });
```

교체 후:

```ts
describe("proposalFileName", () => {
  it("보고서 접두·주제 앞 20자·한국 날짜·'수락한 문단만' 꼬리 — 파일 이름에 못 쓰는 글자는 뺀다", () => {
    expect(proposalFileName("노인 우울/사회적 지지: 연구?", NOW, false)).toBe("보고서_노인_우울사회적_지지_연구_20261014.docx");
    expect(proposalFileName("가".repeat(30), NOW, true)).toBe(`보고서_${"가".repeat(20)}_20261014_수락문단만.docx`);
    expect(proposalFileName("  ", NOW, false)).toBe("보고서_초안_20261014.docx");
  });
});

describe("보고서 Word — 워터마크 없음", () => {
  async function unzip(target: ReportDoc): Promise<JSZip> {
    return JSZip.loadAsync(await (await toDocxBlob(target)).arrayBuffer());
  }

  it("기본·'수락한 문단만' 모두 머리글(워터마크)을 만들지 않는다", async () => {
    for (const acceptedOnly of [false, true]) {
      const zip = await unzip(buildProposalDocument(input({ acceptedOnly }), NOW));
      expect(Object.keys(zip.files).filter((name) => /^word\/header\d+\.xml$/.test(name))).toEqual([]);
    }
  });

  it("워터마크를 그리는 길(reportDocx)은 그대로다 — watermark 가 있는 문서 모델은 쪽마다 머리글에 회색 굵은 글로 싣는다", async () => {
    const zip = await unzip({ ...buildProposalDocument(input(), NOW), watermark: "검토용 사본" });
    const headers = Object.keys(zip.files).filter((name) => /^word\/header\d+\.xml$/.test(name));
    expect(headers.length).toBeGreaterThan(0);
    const xml = (await zip.file(headers[0]!)?.async("string")) ?? "";
    expect(xml).toContain("검토용 사본");
    expect(xml).toContain("<w:b/>");
    expect(xml).toContain('<w:color w:val="999999"/>');
  });
```

`frontend/tests/unit/proposalView.test.ts` — describe `footprint · footprintLine` 둘째 it(`:265-269`). 교체 전:

```ts
  it("AI 제안 = 검토 전 + 수락 + 수정, 사용자 작성은 따로 적는다", () => {
    expect(footprintLine({ proposed: 0, accepted: 7, edited: 2, authored: 0 })).toBe("AI 제안 9문단 중 수락 7·수정 2");
    expect(footprintLine({ proposed: 2, accepted: 5, edited: 2, authored: 1 })).toBe(
      "AI 제안 9문단 중 수락 5·수정 2·검토 전 2 · 직접 쓴 문단 1",
    );
```

교체 후:

```ts
  it("AI 작성 = 검토 전 + 수락 + 수정, 사용자 작성은 따로 적는다", () => {
    expect(footprintLine({ proposed: 0, accepted: 7, edited: 2, authored: 0 })).toBe("AI 작성 9문단 중 수락 7·수정 2");
    expect(footprintLine({ proposed: 2, accepted: 5, edited: 2, authored: 1 })).toBe(
      "AI 작성 9문단 중 수락 5·수정 2·검토 전 2 · 직접 쓴 문단 1",
    );
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/proposalDocument.test.ts tests/unit/proposalView.test.ts`
Expected: `Test Files  2 failed (2)` / `Tests  14 failed | <X5 앞 두 파일 합 − 13> passed (<X5 앞 두 파일 합 + 1>)`(통합 사본 `14 failed | 32 passed (46)`). 실패 열넷:
- `footprint · footprintLine > AI 작성 = 검토 전 + 수락 + 수정, …` — `expected 'AI 제안 9문단 중 수락 7·수정 2' to be 'AI 작성 9문단 중 수락 7·수정 2'`
- `buildProposalDocument >` 여섯 — `기본은 네 상태 문단을 모두 싣고 워터마크가 없다`·`인용 번호는 …`·`meta 에 원 질문 …`·`'수락한 문단만'을 켜면 …`·`쓰지 않은 절·'수락한 문단만'에 실을 문단이 없는 절 …`·`연구 배경을 적으면 2절에 싣고 …`(기대 줄·파일 이름 `보고서_…`·참고문헌 셋이 아직 옛 기본)
- `disclosureLines >` 다섯 — 옛 부록 줄(모델·시도 줄, '이 문서에 실은 문단: 수락·수정·직접 쓴 문단(…)', 검토할 곳 줄 없음)
- `printedKeys·printedProposedCount … > '수락한 문단만'을 켰을 때 빠지는 수 …` — 옛 코드는 `acceptedOnly` 를 몰라 빠지는 수가 0
- `proposalFileName > 보고서 접두 …` — `연구계획서_…`

`보고서 Word — 워터마크 없음` 의 세 it 은 지금도 통과한다 — 옛 코드는 `acceptedOnly` 를 모르고 `includeProposed` 가 없어 워터마크를 달지 않고, 손으로 만든 문서 모델의 워터마크는 `reportDocx` 가 이미 그린다(고정하는 테스트).

- [ ] **Step 3: 구현한다**

`frontend/utils/proposalDocument.ts` — 타입 import(`:2-11`) — 생성 단계 줄(`stepName`·`stepLine`)을 지우면 쓰지 않는 셋을 뺀다. 교체 전:

```ts
import type {
  DisclosureStep,
  GenKind,
  Outline,
  PaperMeta,
  ParaState,
  ProposalSection,
  ProposalView,
  WorkView,
} from "~/types/work";
```

교체 후:

```ts
import type { PaperMeta, ParaState, ProposalSection, ProposalView, WorkView } from "~/types/work";
```

`frontend/utils/proposalDocument.ts` — `~/utils/proposalView` import(`:13` — Task A3 가 `sectionKeysOf` 를 더한 줄). 교체 전:

```ts
import { GAP_NOTE, SECTION_LABELS, footprint, footprintLine, sectionKeysOf, sectionLabel } from "~/utils/proposalView";
```

교체 후:

```ts
import {
  GAP_NOTE,
  SECTION_LABELS,
  footprint,
  footprintLine,
  reviewLine,
  reviewSpots,
  sectionKeysOf,
  sectionLabel,
} from "~/utils/proposalView";
```

`frontend/utils/proposalDocument.ts` — `workPhase` import 와 머리 주석·상수·`proposalFileName`(`:24-70`) — `UNREVIEWED_WATERMARK`·`EXPORTED`·`NOT_YET`·`KIND_LABELS`·`OUTCOME_LABELS` 를 지우고 `ALL_STATES`·`ACCEPTED_ONLY` 를 둔다. 교체 전:

```ts
import { scopeLine } from "~/utils/workPhase";

// 계획서 Word — 보고서와 같은 문서 모델(ReportDoc)로 만들어 useReportExport·reportDocx·ReportPrint 를 그대로 탄다

export const UNREVIEWED_WATERMARK = "미검토 AI 초안";

export interface ProposalDocInput {
  question: string;
  url: string;
  proposal: ProposalView;
  work: WorkView;
  includeProposed: boolean;
}

// 기본은 사용자가 받아들인 문단만(수락·고침·직접 작성). 검토 전 AI 제안은 사용자가 켤 때만 싣고 워터마크를 단다
const EXPORTED: readonly ParaState[] = ["accepted", "edited", "authored"];
const NOT_YET = "이 초안에는 아직 없습니다 — 다음 단계에서 씁니다.";
const RESULTS_LATER = "연구 후 직접 씁니다.";
const DISCLOSURE_INTRO =
  "이 초안의 문단은 연구 어시스턴트의 AI(대형 언어 모델)가 제안한 글을 사용자가 검토해 받아들이거나 고친 것입니다. " +
  "문단 상태는 AI 제안(검토 전)·AI 작성(수락)·AI 작성(사용자가 고침)·사용자 작성으로 저장하고, 수락만 한 문단도 AI 작성으로 셉니다.";
const KIND_LABELS: Record<GenKind, string> = {
  concepts: "핵심 개념",
  topic_card: "주제 카드",
  refine: "주제 다듬기",
  facet: "논문 특징",
  outline: "목차",
  section: "절 초안",
  paragraph: "문단 다시 쓰기",
};
const OUTCOME_LABELS: Record<string, string> = {
  ok: "완료",
  parse: "해석 실패",
  check: "검사 미달",
  transport: "전송 실패",
  broken: "끊김",
};
const MIX_LABELS: { state: ParaState; label: string }[] = [
  { state: "accepted", label: "수락" },
  { state: "edited", label: "수정" },
  { state: "authored", label: "직접 작성" },
  { state: "proposed", label: "검토 전" },
];

export function proposalFileName(topicTitle: string, date: Date, withProposed: boolean): string {
  return `연구계획서_${fileHead(topicTitle) || "초안"}_${kstYmd(date)}${withProposed ? "_미검토포함" : ""}.docx`;
}
```

교체 후:

```ts
import { FINAL_STEP_NAME, scopeLine } from "~/utils/workPhase";

// 보고서(연구계획서형 초안) Word — 딥리서치 보고서와 같은 문서 모델(ReportDoc)로 만들어 useReportExport·reportDocx·ReportPrint
// 를 그대로 탄다. 기본은 네 상태 문단을 모두 싣고 워터마크를 달지 않는다 — 어느 문단을 AI 가 썼는지는 끝의 AI 사용 공개
// 부록이 문단 상태별 개수로 밝힌다(D21). 이 문서 모델은 ReportDoc.watermark 를 만들지 않는다

export interface ProposalDocInput {
  question: string;
  url: string;
  proposal: ProposalView;
  work: WorkView;
  // '수락한 문단만' — 켜면 검토 전 AI 작성 문단(proposed)을 빼고 수락·수정·직접 작성만 싣는다(워터마크 없음)
  acceptedOnly: boolean;
}

const ALL_STATES: readonly ParaState[] = ["proposed", "accepted", "edited", "authored"];
const ACCEPTED_ONLY: readonly ParaState[] = ["accepted", "edited", "authored"];
const RESULTS_LATER = "연구 후 직접 씁니다.";
const DISCLOSURE_INTRO =
  "이 초안의 문단은 연구 어시스턴트의 AI(대형 언어 모델)가 소장 KCI 논문을 근거로 작성했고, 사용자가 검토해 수락·수정하거나 " +
  "직접 쓴 문단이 섞여 있습니다. 문단 상태는 AI 작성·검토 전 / 수락 / 수정 / 직접 작성 네 가지로 저장합니다.";
// 부록의 절별 문단 상태 — 화면 띠(ProposalSection 의 STATE_LABELS)와 같은 말, 이 순서로
const MIX_LABELS: { state: ParaState; label: string }[] = [
  { state: "proposed", label: "AI 작성·검토 전" },
  { state: "accepted", label: "수락" },
  { state: "edited", label: "수정" },
  { state: "authored", label: "직접 작성" },
];

export function proposalFileName(topicTitle: string, date: Date, acceptedOnly: boolean): string {
  return `${FINAL_STEP_NAME}_${fileHead(topicTitle) || "초안"}_${kstYmd(date)}${acceptedOnly ? "_수락문단만" : ""}.docx`;
}
```

`frontend/utils/proposalDocument.ts` — `buildProposalDocument` 머리(`:75-78`). 교체 전:

```ts
  const shown: readonly ParaState[] = input.includeProposed ? [...EXPORTED, "proposed"] : EXPORTED;
  // 번호는 논문(cnts_id)마다 문서에 처음 나온 순서다 — 절마다 [E#] 가 가리키는 논문이 달라도 한 논문은 한 번호다
  const numbers = new Map<string, number>();
  let shownProposed = 0;
```

교체 후:

```ts
  const shown = input.acceptedOnly ? ACCEPTED_ONLY : ALL_STATES;
  // 번호는 논문(cnts_id)마다 문서에 처음 나온 순서다 — 절마다 [E#] 가 가리키는 논문이 달라도 한 논문은 한 번호다
  const numbers = new Map<string, number>();
```

`frontend/utils/proposalDocument.ts` — `sectionBlocks` 의 빈 절 문구(`:106-111`). 교체 전:

```ts
    const paragraphs = section.paragraphs.filter((x) => shown.includes(x.state));
    if (!paragraphs.length) {
      return [muted("받아들인 문단이 없습니다 — 화면에서 [수락]하거나 '미수락 문단도 넣기'를 켜면 실립니다.")];
    }
    shownProposed += paragraphs.filter((x) => x.state === "proposed").length;
    return paragraphs.flatMap((x) => lines(x.text).map((line): DocBlock => ({ type: "para", runs: runs(line, section) })));
```

교체 후:

```ts
    const paragraphs = section.paragraphs.filter((x) => shown.includes(x.state));
    if (!paragraphs.length) {
      // 문단을 모두 지운 절은 쓰지 않은 절과 같다. '수락한 문단만'에 실을 문단이 없으면 끄는 길을 알린다
      return [
        muted(
          input.acceptedOnly && section.paragraphs.length
            ? "수락한 문단이 없습니다 — '수락한 문단만'을 끄면 AI 작성 문단도 실립니다."
            : "아직 쓰지 않았습니다.",
        ),
      ];
    }
    return paragraphs.flatMap((x) => lines(x.text).map((line): DocBlock => ({ type: "para", runs: runs(line, section) })));
```

`frontend/utils/proposalDocument.ts` — 2절 연구 배경(`:120-121`, 뼈대 정함 7). 교체 전:

```ts
    heading(`2. ${SECTION_LABELS.background}`),
    muted(NOT_YET),
```

교체 후:

```ts
    heading(`2. ${SECTION_LABELS.background}`),
    // 연구 배경은 사용자가 보고서 화면 2절 칸에 적는 글(outline.background, 06e) — AI 가 쓰지 않는다
    ...(outline?.background?.trim() ? lines(outline.background).map(plain) : [muted("연구 배경을 아직 적지 않았습니다.")]),
```

`frontend/utils/proposalDocument.ts` — 부록 줄 부르기(`:141`). 교체 전:

```ts
    { type: "bullets", items: disclosureLines(p, input.includeProposed).map((line) => [{ text: xmlSafe(line) }]) },
  );
```

교체 후:

```ts
    { type: "bullets", items: disclosureLines(p, input.acceptedOnly, now).map((line) => [{ text: xmlSafe(line) }]) },
  );
```

`frontend/utils/proposalDocument.ts` — 반환과 `disclosureLines`(`:149-177`) — watermark 키를 지우고, 부록에서 생성 단계 줄을 빼고 실은 문단·검토할 곳·작성 일시 줄을 둔다. 교체 전:

```ts
  return {
    fileName: proposalFileName(title, now, shownProposed > 0),
    blocks,
    references,
    ...(shownProposed > 0 ? { watermark: UNREVIEWED_WATERMARK } : {}),
  };
}

// 부록 "AI 사용 공개" — 문단 상태 비율·고른 주제의 출처·절별 상태·실은 문단·생성 단계(모델·완료 시각·시도)·결과·논의 미포함.
// 시도는 모델·결과만 싣는다 — 실패 사유(error)에는 내부 주소가 들어 있어 문서에 내보내지 않는다
export function disclosureLines(p: ProposalView, includeProposed: boolean): string[] {
  const f = footprint(p);
  // 실은 검토 전 문단은 문서가 그리는 절(목차 묶음·연구 공백)에서만 센다 — 워터마크·파일 이름 꼬리(shownProposed)와 같은 범위다
  const included = printedProposedCount(p);
  const out = [`문단 상태: ${footprintLine(f)}`];
  if (p.topic_source) out.push(topicSourceLine(p.topic_source));
  for (const key of sectionKeys(p)) {
    const section = p.sections[key];
    if (section) out.push(`${sectionLabel(key, p.outline)}: ${stateMix(section)}`);
  }
  out.push(
    includeProposed && included
      ? `이 문서에 실은 문단: 수락·수정·직접 쓴 문단과 검토 전 AI 제안 ${included}문단(쪽마다 '${UNREVIEWED_WATERMARK}' 표시)`
      : "이 문서에 실은 문단: 수락·수정·직접 쓴 문단(검토 전 AI 제안은 싣지 않음)",
  );
  for (const step of p.disclosure.steps) out.push(stepLine(step, p.outline));
  out.push("결과·논의 미포함 — 결과·논의·가설 수치는 AI 가 쓰지 않았고 이 문서에도 없습니다.");
  return out;
}
```

교체 후:

```ts
  return { fileName: proposalFileName(title, now, input.acceptedOnly), blocks, references };
}

// 부록 "AI 사용 공개"(D21) — 문단 상태 비율·고른 주제의 출처·절별 문단 상태 개수·실은 문단·검토할 곳(실은 문단에서 센다)·
// 작성 일시·결과·논의 미포함. 모델 이름·생성별 시도 기록은 싣지 않는다('AI 작성·검토' 수준 — 저장(research_generations
// .model·attempts)은 그대로)
export function disclosureLines(p: ProposalView, acceptedOnly: boolean, now: Date): string[] {
  const out = [`문단 상태: ${footprintLine(footprint(p))}`];
  if (p.topic_source) out.push(topicSourceLine(p.topic_source));
  for (const key of sectionKeys(p)) {
    const section = p.sections[key];
    if (section) out.push(`${sectionLabel(key, p.outline)}: ${stateMix(section)}`);
  }
  out.push(includedLine(acceptedOnly, printedProposedCount(p)));
  // '수락한 문단만'이면 문서에 실은 문단만 센다 — 빠진 검토 전 문단의 검토 단서는 이 문서의 것이 아니다
  const counted = acceptedOnly
    ? {
        ...p,
        sections: Object.fromEntries(
          Object.entries(p.sections).map(([k, s]): [string, ProposalSection] => [
            k,
            { ...s, paragraphs: s.paragraphs.filter((x) => ACCEPTED_ONLY.includes(x.state)) },
          ]),
        ),
      }
    : p;
  const review = reviewLine(reviewSpots(counted));
  if (review) out.push(review);
  out.push(`작성 일시 ${kstDateTime(now)}`);
  out.push("결과·논의 미포함 — 결과·논의·가설 수치는 AI 가 쓰지 않았고 이 문서에도 없습니다.");
  return out;
}

// 실은 문단 줄 — 검토 전 AI 작성 문단은 문서가 그리는 절(목차 묶음·연구 공백)에서만 센다(화면 '수락한 문단만' 체크의 수와 같다)
function includedLine(acceptedOnly: boolean, proposed: number): string {
  if (acceptedOnly) {
    return proposed
      ? `이 문서에 실은 문단: 수락·수정·직접 쓴 문단만(검토 전 AI 작성 문단 ${proposed}개는 싣지 않음)`
      : "이 문서에 실은 문단: 수락·수정·직접 쓴 문단만(검토 전 AI 작성 문단 없음)";
  }
  return proposed
    ? `이 문서에 실은 문단: 모든 문단(검토 전 AI 작성 문단 ${proposed}개 포함)`
    : "이 문서에 실은 문단: 모든 문단(검토 전 AI 작성 문단 없음)";
}
```

`frontend/utils/proposalDocument.ts` — `metaBlocks` 첫 줄(`:205`). 교체 전:

```ts
    `연구계획서 초안 · 원 질문 ${input.question}`,
```

교체 후:

```ts
    `${FINAL_STEP_NAME} 초안 · 원 질문 ${input.question}`,
```

`frontend/utils/proposalDocument.ts` — `printedProposedCount` 주석(`:221-222`). 교체 전:

```ts
// 문서에 실릴 수 있는 검토 전 AI 제안 수 — 문서가 그리는 절에서만 센다. 목차를 다시 만들며 빠진 옛 절(prior.g3 등)은
// 문서에 실리지 않는다. 공개 부록의 '실은 문단' 줄과 화면의 '미수락 문단도 넣기(워터마크)' 토글이 이 수를 쓴다
```

교체 후:

```ts
// 문서에 실릴 수 있는 검토 전 AI 작성 문단 수 — 문서가 그리는 절에서만 센다. 목차를 다시 만들며 빠진 옛 절(prior.g3 등)은
// 문서에 실리지 않는다. 공개 부록의 '실은 문단' 줄과 화면의 '수락한 문단만' 체크가 이 수를 쓴다
```

`frontend/utils/proposalDocument.ts` — `stepName`·`stepLine`(`:252-275`)을 지운다. 교체 전은 두 함수와 그 뒤 빈 줄, 다음 함수 `fallbackReference` 의 머리 줄까지이고, 교체 후는 그 머리 줄만이다 — 결과는 `stateMix` 의 `}` 다음 빈 줄 하나, 그 다음 `function fallbackReference`. 교체 전:

```ts
function stepName(step: DisclosureStep, outline: Outline | null): string {
  const label = KIND_LABELS[step.kind] ?? step.kind;
  if (!step.target) return label;
  if (step.kind === "section") return `${label}(${sectionLabel(step.target, outline)})`;
  if (step.kind === "paragraph") {
    const [key = "", pid = ""] = step.target.split("#");
    return `${label}(${sectionLabel(key, outline)} ${pid})`;
  }
  if (step.kind === "topic_card") return `${label}(#${step.target})`;
  return label;
}

function stepLine(step: DisclosureStep, outline: Outline | null): string {
  const model = step.model ?? "모델 출력 없음(기본값으로 채움)";
  const done = step.finished_at ? new Date(step.finished_at) : null;
  const when = done && !Number.isNaN(done.getTime()) ? kstDateTime(done) : "완료 시각 기록 없음";
  const tries =
    step.attempts.length > 1
      ? ` — 시도 ${step.attempts.length}회: ${step.attempts
          .map((a) => `${a.model} ${OUTCOME_LABELS[a.outcome] ?? a.outcome}`)
          .join(" → ")}`
      : "";
  return `${stepName(step, outline)}: ${model} · ${when}${tries}`;
}

function fallbackReference(cnts: string, meta: PaperMeta | undefined): string {
```

교체 후:

```ts
function fallbackReference(cnts: string, meta: PaperMeta | undefined): string {
```

`frontend/utils/proposalView.ts` — `footprintLine`(`:139`) — 머리 'AI 제안' → 'AI 작성'(D21 — 화면 AI 기여 막대와 공개 부록이 같은 말). 교체 전:

```ts
    ? `AI 제안 ${ai}문단 중 수락 ${f.accepted}·수정 ${f.edited}${f.proposed ? `·검토 전 ${f.proposed}` : ""}`
```

교체 후:

```ts
    ? `AI 작성 ${ai}문단 중 수락 ${f.accepted}·수정 ${f.edited}${f.proposed ? `·검토 전 ${f.proposed}` : ""}`
```

`frontend/utils/proposalView.ts` — `footprint` 주석(`:127`). 교체 전:

```ts
// 문단 상태로 센 기여 — 수락만 한 문단도 AI 작성으로 센다(spec §3)
```

교체 후:

```ts
// 문단 상태로 센 기여 — 검토 전·수락만 한 문단도 AI 작성으로 센다(spec §3·D21)
```

`frontend/components/work/ProposalSection.vue` — `STATE_LABELS.proposed`(`:255-256`). 교체 전:

```vue
const STATE_LABELS: Record<ParaState, string> = {
  proposed: "AI 제안 · 검토 전",
```

교체 후:

```vue
const STATE_LABELS: Record<ParaState, string> = {
  // 보고서를 자동으로 쓴 글이라 '제안'을 뺀다(D21) — 저장 값 proposed 는 그대로
  proposed: "AI 작성 · 검토 전",
```

`frontend/components/work/ProposalSection.vue` — 주석(`:299`). 교체 전:

```vue
// 잇는 그 문단의 띠(AI 제안 · 검토 전 등) — 스크린리더의 컨트롤 목록에서 어느 절의 몇째 문단인지 구별되게
```

교체 후:

```vue
// 잇는 그 문단의 띠(AI 작성 · 검토 전 등) — 스크린리더의 컨트롤 목록에서 어느 절의 몇째 문단인지 구별되게
```

`frontend/components/work/ProposalStep.vue` — 내보내기 카드(`<div class="rs-card wk-proposal__export">` — 06b `:77-88`)의 체크·설명. 제목 줄(`:76`)과 버튼 줄(`:89-93`)은 그대로. 교체 전:

```vue
          <label class="wk-proposal__toggle">
            <input v-model="includeProposed" type="checkbox" :disabled="!printedProposed" />
            미수락 문단도 넣기(워터마크) — 검토 전 AI 제안 {{ printedProposed }}문단
          </label>
          <p class="rs-muted">
            {{
              includeProposed && printedProposed
                ? "문서 쪽마다 '미검토 AI 초안' 워터마크가 붙습니다."
                : "기본은 수락·수정·직접 쓴 문단만 싣습니다."
            }}
            끝에 참고문헌과 AI 사용 공개 부록이 붙습니다.
          </p>
```

교체 후:

```vue
          <label class="wk-proposal__toggle">
            <input v-model="acceptedOnly" type="checkbox" :disabled="!printedProposed" />
            수락한 문단만 싣기 — 검토 전 AI 작성 {{ printedProposed }}문단을 뺍니다
          </label>
          <p class="rs-muted">기본은 모든 문단을 싣습니다. 끝에 참고문헌과 AI 사용 공개 부록(문단 상태별 개수)이 붙습니다.</p>
```

`frontend/components/work/ProposalStep.vue` — `printedProposed` 주석(`:139`). 교체 전:

```vue
// 문서에 실릴 검토 전 문단 — 목차를 다시 만들며 빠진 옛 절은 문서에 실리지 않아 세지 않는다(공개 부록·워터마크와 같은 수)
```

교체 후:

```vue
// 문서에 실릴 검토 전 문단 — 목차를 다시 만들며 빠진 옛 절은 문서에 실리지 않아 세지 않는다(공개 부록·'수락한 문단만'과 같은 수)
```

`frontend/components/work/ProposalStep.vue` — 내려받기 머리(`:245`). 교체 전:

```vue
const includeProposed = ref(false);
```

교체 후:

```vue
const acceptedOnly = ref(false);
```

`frontend/components/work/ProposalStep.vue` — `downloadWord` 의 입력(`:257`). 교체 전:

```vue
    { question: props.question, url: proposalUrl(), proposal: p, work: w, includeProposed: includeProposed.value },
```

교체 후:

```vue
    { question: props.question, url: proposalUrl(), proposal: p, work: w, acceptedOnly: acceptedOnly.value },
```

`frontend/components/work/ProposalStep.vue` — `downloadWord` 의 경고 글(`:263`). 교체 전:

```vue
    console.warn("[research] 계획서 내보내기 실패", e);
```

교체 후:

```vue
    console.warn("[research] 보고서 내보내기 실패", e);
```

`UNREVIEWED_WATERMARK`·`includeProposed`·생성 단계 줄을 쓰는 곳이 남지 않았는지 본다:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -rn "UNREVIEWED_WATERMARK\|includeProposed\|미검토\|미수락\|KIND_LABELS\|OUTCOME_LABELS\|NOT_YET" utils components composables pages tests; grep -n "stepName\|stepLine" utils/proposalDocument.ts`
Expected: 빈 출력(`workPhase.stepLine` 은 진행 막대의 다른 함수라 두 번째 grep 은 `proposalDocument.ts` 만 본다)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/proposalDocument.test.ts tests/unit/proposalView.test.ts`
Expected: `Test Files  2 passed (2)` / `Tests  <X5 앞 두 파일 합 + 1> passed`(통합 사본 `46 passed (46)`)

- [ ] **Step 5: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`(ProposalStep 이 `acceptedOnly` 로 문서를 만들고, `includeProposed` 를 쓰는 곳이 없다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Tests <X5 앞 + 1> passed`(통합 사본 `745 passed (745)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

딥리서치 보고서 내보내기는 고치지 않았는지 본다:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff --stat HEAD -- frontend/utils/reportDocument.ts frontend/utils/reportDocx.ts frontend/components/research/ReportPrint.vue frontend/composables/useReportExport.ts`
Expected: 빈 출력

브라우저 확인(마무리 운영 확인): 자동으로 쓴 보고서를 Word 로 내려받으면 검토 전 문단까지 모두 실리고 워터마크가 없다, 2절에 적은 연구 배경이 실린다(안 적었으면 흐린 안내), 부록에 절별 상태 개수·실은 문단·검토할 곳·작성 일시·결과·논의 미포함이 있고 모델 이름·시도 줄이 없다, 파일 이름이 `보고서_<주제>_<날짜>.docx` 다. '수락한 문단만'을 켜면 검토 전 문단이 빠지고 파일 이름 끝이 `_수락문단만` 이다. 문단 띠가 'AI 작성 · 검토 전'이다.

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/utils/proposalDocument.ts && git add frontend/utils/proposalView.ts && git add frontend/components/work/ProposalSection.vue && git add frontend/components/work/ProposalStep.vue && git add frontend/tests/unit/proposalDocument.test.ts && git add frontend/tests/unit/proposalView.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 보고서 내보내기 기본값을 '모든 문단·워터마크 없음'으로 바꾼다(D21). 보고서를 자동으로 쓰면 수락 관문이 없어 옛 기본(수락한 문단만)은 모든 절이 '받아들인 문단이 없습니다'로 나간다. '수락한 문단만'은 선택지로 남기고(acceptedOnly — 켜면 수락·수정·직접 작성만, 워터마크 없음, 파일 이름 꼬리 _수락문단만) 미검토 워터마크를 지운다(ReportDoc.watermark 와 그리는 길은 그대로 — 딥리서치 보고서 출력 불변). 끝의 AI 사용 공개 부록은 절별 문단 상태 개수(AI 작성·검토 전 / 수락 / 수정 / 직접 작성)·실은 문단·검토할 곳(문서에 실은 문단에서 센다)·작성 일시·결과·논의 미포함만 싣고 모델 이름·생성별 시도 기록은 뺀다(저장은 그대로). 2절에 사용자가 적은 연구 배경을 싣고 '다음 단계에서 씁니다'를 지운다. 파일 이름·문서 머리는 '보고서', 문단 띠의 proposed 는 'AI 작성 · 검토 전'(저장 값 그대로), 기여 막대 머리는 'AI 작성 n문단 중'"
```

---

## 파트 메모 — 뼈대와 다른 점

이름·시그니처·모양·상수(뼈대 1장)는 모두 그대로 썼다(`OUTLINE_BACKGROUND_MAX`·`GAP_CLAIM_CONTEXT`·`GAP_CLAIM_TAIL`·`GAP_CLAIM_REWRITES`·`fieldPut`·`putOnceMore`·`ReviewSpots`·`reviewSpots`·`reviewLine`·`ProposalDocInput.acceptedOnly`·`proposalFileName(…, acceptedOnly)`·`disclosureLines(p, acceptedOnly, now)`·`DocField` props·emit, Outline `background`·Section basis `question`). 다른 점은 아래 여덟이다.

1. **X2 — 다섯 패턴 끝에 `(?![가-힣])`.** 뼈대의 정규식 그대로면 '소장 코퍼스에서 확인되었다는 점은 한계다'의 '확인되었다'가 '보인다(…)는 점'으로 바뀌어 문장이 깨진다. 문장 끝 단정만 바꾸도록 뒤에 한글이 이어지면 맞지 않게 했다 — 뼈대가 든 다섯 사례·두 번 거침은 그대로 통과하고, 그대로 남는 사례에 이 문장을 하나 더했다(그대로 남는 it 이 매개변수 4 → 5, 그래서 X2 는 +13 — 검토 반영 1 로 +2 더해 지금은 +15).
2. **X2 — `GAP_CLAIM_TAIL = f"({GAP_NOTE})"`.** 값은 뼈대 1-1 의 `"(소장 코퍼스에서 확인하지 않은 공백 후보)"` 와 같다. 같은 글이 `shapes.GAP_NOTE`(절 머리 note)에 이미 있어 두 번 적지 않으려고 `markers.py` 가 `shapes` 를 import 한다(`shapes` 는 상수만 있는 모듈이라 순환이 없다).
3. **X3 — 테스트 하나 더: `toOutlinePut > 연구 배경은 싣지 않는다`.** 뼈대가 '`toOutlinePut` 은 background 를 싣지 않는다(서버가 지킨다)'고 정한 동작을 고정한다([목차 고치기]가 배경을 지우지 않는 근거). 그래서 X3 은 +7 이 아니라 +8 이다.
4. **X3 — `ProposalSection.vue:19-22` 다시 맞춤 안내에 '연구 질문'을 더했다.** 뼈대 X3 파일 목록에 없는 한 줄이다. X1 로 질문 바뀜도 절의 '다시 맞춤 필요' 사유가 되는데 안내가 '주제나 목차의 묶음이 바뀌었습니다'만 말하면 질문을 바꾼 사용자가 까닭을 모른다. 공유 파일 순서(`ProposalSection.vue`: A5 → X4 → X5 → S4)에 X3 이 A5 와 X4 사이로 들어간다 — 자리가 겹치지 않는다.
5. **X4 — 문단 `li` 에 `tabindex="-1"`·`.wk-psec__item:focus-visible`, 문단이 없으면 절 제목으로.** 뼈대는 '`querySelector` 로 스크롤·초점'만 적었는데 `li` 는 초점을 받지 못한다. 그 절을 다시 쓰는 중이라 문단 목록이 그려지지 않으면(`ProposalSection.vue:74` `status !== 'writing'`) 그 절 제목(`#wk-sec-title-<key>` — A5 가 `tabindex="-1"`)으로 간다. 줄 옆에 흐린 설명 한 줄('코드 검사가 표시한 곳입니다…')을 더했다.
6. **X5 — 부록 '실은 문단' 줄에 수를 싣고, 날짜 줄은 `작성 일시 ${kstDateTime(now)}`.** 뼈대의 기본 문구 `모든 문단(검토 전 AI 작성 문단 포함)` 은 검토 전 문단이 0 일 때도 '포함'이라 적어 사실과 어긋나므로 `모든 문단(검토 전 AI 작성 문단 n개 포함)`·`…(검토 전 AI 작성 문단 없음)` 으로 했다('수락한 문단만'도 n 이 0 이면 '없음'). 날짜는 뼈대의 `kstYmd(now)` 가 파일 이름용 `20261014` 꼴이라 문서 머리 '생성 일시'와 같은 `kstDateTime`(`2026년 10월 14일 15:05`)을 썼다. 절별 상태 줄은 지금처럼 0 인 상태를 뺀다(`stateMix` 규칙 그대로 — 라벨·순서만 바뀐다).
7. **X5 — 테스트 목록에 `buildProposalDocument` 둘째 it(참고문헌 `:174`)이 더 바뀐다.** 기본이 모든 문단이 되어 검토 전 문단이 인용한 KCI_B 가 문서 번호 2 를 받는다(KCI_C 는 3). 뼈대 목록에 없던 ✎ 하나다. '문단을 모두 지운 절'은 기본·'수락한 문단만' 모두 `아직 쓰지 않았습니다.` 로 정했다(뼈대가 정하지 않은 경우 — 테스트에 넣었다).
8. **X1 — `TestPutOutline.test_background_is_saved_trimmed_and_kept_when_left_out` 이 진행 'n/6절'(4 → 3)도 본다.** API 를 거쳐 `refresh_progress` 가 연구 배경을 세는지 한 번에 확인한다(뼈대의 같은 테스트 이름 그대로, 단언만 하나 더). 연구 질문 식은 `proposal_views._research_question`(비공개)로 두고 `generate_section`(`research_proposal.py:402`)은 고치지 않았다 — 같은 식이라는 것을 주석에 적었다.

## 파트 메모 — 다른 파트·줄에 기대는 것, 실행자가 확인할 것

- **Task A1·A2(같은 백엔드 파일):** X1 의 old 는 A1(`NEED_READING`·Outline 주석 `auto`·`TestPutOutline.test_saving_keeps_the_auto_mark`)·A2(`NO_SECTION_PAPERS_CODE`·`section_gens_of`·`TestSectionGens`)가 건드리지 않는 줄이다. 예외로 `outline.py`·`test_research_work_outline.py` 는 A1 이 쓴 글(`apply` docstring 의 다시 만들기 줄·dict 끝 `"auto": auto,`·`test_a_new_outline_replaces_an_approved_one` 끝 단언)을 old 로 잡는다 — 계획 머리의 같은 파일 순서 표에 `outline.py` A1 → X1, 기존 테스트 표에 `test_research_work_outline.py`(A1·X1)를 적는다. 기대 수는 A1·A2 뒤 `test_research_proposal_api.py` 98 을 전제로 적었다(A1 +1·A2 +2) — 실제 수가 다르면 상대값(+4)으로 읽는다.
- **Task A3(프론트 계약):** `sectionKeysOf`(X4 `reviewSpots`), `FINAL_STEP_NAME`(X5 파일 이름·문서 머리), `proposalView.ts` 의 `~/utils/researchErrors` import(`isNoSectionPapers` 의 `httpStatus` — X3 이 `versionConflict` 를 더한다), `proposalDocument.ts` 의 `sectionKeysOf` import·`printedKeys` 본문(X5 의 import old), `types/work.ts` 의 `Outline.auto?`(X3 의 old 는 그 위 `concepts?` 줄). 통합 사본은 이 넷만 대역으로 얹고 X3~X5 를 쟀다.
- **Task A5(보고서 화면 구조):** X3 은 A5 의 문서 2절·6절 자리(`<section id="wk-doc-background">`·`<section id="wk-doc-method">`, `h3.wk-doc__part-title` 아래 두 줄)와 `~/utils/proposalView` import 목록(A5 가 편 여러 줄 — X3 은 `outlineBackground,`·`reportBar,` 두 줄을 잡는다)·`background` computed, 두 화면(`ProposalStep.vue`·`ReadingStep.vue`)의 `REMAKE_CONFIRM` 을 글자 그대로 잡는다 — 계획 머리의 같은 파일 순서 표에서 `ReadingStep.vue` 는 A5 → X3 → R1 → R5 가 된다(R1·R5 는 `REMAKE_CONFIRM` 을 잡지 않는다). X4 는 머리 목차(`class="wk-doc__toc"`)와 ProposalSection `h3` 의 `tabindex="-1"`(절 제목 초점)을, 둘 다 ProposalStep 의 `act`·`say`·`busy`·`readOnly`·`outlineGen`·`api`·`props.work` 를 쓴다(06b 그대로의 이름 — A5 가 이름을 바꿨으면 그 이름으로). A5 의 큰 진행 막대(`.wk-rbar` — 뼈대 정함 28, 10-11 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아")는 파트 X 가 건드리지 않는다. '검토할 곳' 줄은 막대·머리 목차 **아래**에 선다. 계획 머리의 정함 28 질문 한 줄은 사용자가 답했으므로 머리 작성자가 '사용자 확인(10-11)'으로 바꿔 적으면 된다.
- **Task H3(PDF):** H3 의 old 가 X5 뒤의 글자를 전제한다 — `// ── Word 내려받기 ───…` 주석 아래 `const acceptedOnly = ref(false);`, `downloadWord` 의 입력 `acceptedOnly: acceptedOnly.value` 와 경고 `"[research] 보고서 내보내기 실패"`, 내보내기 카드의 버튼 줄(06b `:89-93`, X5 가 고치지 않음). X5 의 교체 후는 이 글자 그대로다.
- **Task R1(단계 이름):** R1 의 마지막 grep('계획서'·'핵심 개념' 등)에서 X5 몫 — `proposalDocument.ts:69`(파일 이름)·`:205`(문서 머리)·`ProposalStep.vue:263`(`console.warn`)·`KIND_LABELS`(지움)는 X5 가 고쳤다. `proposalDocument.ts` 에 남는 '계획서'는 주석 둘(`printedKeys` 위 '계획서 화면의 절 목록'·머리 '연구계획서형 초안')뿐이다. ProposalStep 의 보이는 '계획서'(제목 `:6`·`:19`·`CONFLICT` `:120`)는 R1 몫이다.
- **Task S4·K·R:** `ProposalSection.vue` 는 X5 뒤 S4 가 인용 칩을 고친다 — X4 가 단 `li` 의 `tabindex="-1"`·sr-only 는 S4 의 자리(`:101-109` 칩·`:349-371` 상세 함수)와 겹치지 않는다. `work.css` 는 X3·X4 가 표시 줄 위에 묶음 둘을 더했다 — R4·R5·S4·K8 은 그 아래(표시 줄 바로 위)에 잇는다.
- **06c·06d 와는 기대는 것이 없다.** X2 는 06c 의 `terms.py` 를 쓰지 않는다. `work.css` 근거 장부 블록(`:75-166`·`:1215-1220`)·`research.css`·`reportDocument.ts`·`reportDocx.ts`·`ReportPrint.vue` 를 고치지 않는다.
- **완료노트에 넣을 것:** X2 의 남는 한계(코퍼스 낱말이 앞 문장에만 있는 단정은 못 잡는다, 코퍼스 문장 안의 효과 없음 결과 '차이가 없음을 확인했다'는 공백 후보로 바뀐다), [보고서 다시 만들기]가 방법은 빈칸으로 되돌리지만(D20) 연구 배경은 이어 받는다는 것(X1), 정함 11 의 판단(보이는 '근거 없음' 배지는 넣지 않고 sr-only·머리 줄·부록 수만), D21 로 부록에서 모델·시도 줄을 뺐다는 것(저장은 그대로 — 필요하면 DB 의 `research_generations` 로 본다), 방법 칸이 [목차 고치기] 안과 문서 6절에 둘 있다는 것.
- **실행자가 확인할 것:** 통합 사본(`da80f23` + A3 대역 + X1~X5)에서 백엔드 연구 어시스턴트 테스트(계획서 API·절 입력·진행·검사·문단 고치기·절·주제 카드·주제 API·모델)와 vitest 전체 `40 files / 744`(검토 반영 4 의 it 하나를 더하면 745)·`nuxi typecheck` 오류 0·`npm run build` 완료(WARN 57줄 — 기준선과 같음, 새 `Duplicated imports` 없음)를 확인했다. 통합 사본의 백엔드 전체 실행은 `scripts/`·`research/`·compose 파일이 없어 그것을 읽는 다른 테스트 파일(`test_build_canary_manifest.py` 등)이 사본에서만 실패했다 — 06e worktree 에서는 기준선대로 '실패 5·오류 1, 세 파일'로 읽는다. ProposalStep 의 A5 자리(2·6절·머리 목차)는 사본에 A5 가 없어 같은 이름의 자리를 흉내 내 typecheck 만 확인했다 — 실제 A5 뒤 Step 5 의 grep 두 개(`<DocField` 2·흐린 안내 0, `wk-review` 1)로 자리를 확인한다.

## 파트 메모 — 파트 사이 일관성 반영

1. **반영 — X3 의 교체 전 세 블록이 Task A5 의 최종 글과 달랐다(critical).** A5 는 검토 반영으로 `~/utils/proposalView` import 에 `autoChainOn`·`autoTargets` 를 더해 여러 줄 목록으로 폈고, 두 화면 `REMAKE_CONFIRM` 을 '(주제나 묶음이 바뀐 절에는 …) 아직 쓰지 않은 절만 자동으로 씁니다'로 바로잡았다(06e-A 파트 메모 8·검토 반영 2). X3 의 import 교체 전/후를 그 목록의 `outlineBackground,`·`reportBar,` 두 줄과 `putOnceMore` 를 넣은 세 줄로, 두 확인 창의 교체 전을 A5 최종 글로, 교체 후를 A5 의 바로잡음을 지킨 글('연구 배경은 그대로 둡니다' + '주제·묶음·연구 질문이 바뀐 절에는' + '아직 쓰지 않은 절만')로 고쳤다. Step 5 의 확인 grep·'확인 창' 설명·X4 의 import 설명·검토 반영 2·3 의 문구를 함께 맞췄다. X4 의 import old(끝 네 줄)는 그대로 맞는다.

---

## 파트 R — 단계 이름·참고문헌 선택하기·오른쪽 딥리드 패널

덮는 spec 항목: §12-4 '제목 고르기 — 이름'·'참고문헌 선택하기·오른쪽 딥리드·인용 근거(D24)' 가운데 이름·논문을 누르면 오른쪽 딥리드·패널(공용 부품)·배치·BookChat 을 끼우기 전 고칠 것·두 호출처 `doc-kind="paper"`·기존 네 화면 회귀·서버는 대화를 저장하지 않는다, D23 의 '핵심 개념 칩 → 키워드 칩'(보이는 글), Q2 기본 '보고서'(정함 1), §12-5 의 LNB 접기 연결(정함 30). 단계 ④ 의 인용 근거 탭·인용 칩(S1~S4)·딥리드 논문 프롬프트(S2)는 파트 S 다.

- **Task R1** — 단계 이름(② 제목 고르기 ③ 참고문헌 선택하기 ④ 보고서)과 '핵심 개념' → '키워드'를 보이는 글에서만 바꾸고, 단계 화면에서 딥리서치 보고서를 가리키는 글에는 '딥리서치'를 붙인다(④ '보고서'와 갈리게). 키(`topics`·`reading`·`proposal`)·주소 `?s=`·API·식별자는 그대로다.
- **Task R2** — BookChat 의 스트림을 순수 SSE 파서(`utils/deepReadSse.ts`)와 `useDeepReadChat` 으로 뺀다(cntsId 감시·논문별 대화 store·AbortController).
- **Task R3** — BookChat 문서 종류(`docKind`)·출처 칩 버튼·[원문 보기](`open-pdf`)·끝난 답 `aria-live`, 논문 화면 두 호출처에 `doc-kind="paper"`.
- **Task R4** — 오른쪽 딥리드 패널 부품 `DeepReadPanel.vue`(머리·탭·배치·초점 가두기·Esc)와 `.wk-split`·`.wk-panel` CSS.
- **Task R5** — 참고문헌 선택하기의 제목을 누르면 오른쪽 딥리드([담음] 토글·들어온 경로 첫 대목·[논문 상세 ↗]), 패널 열림 emit 과 `[id].vue` 리스너.
- **Task R6 (조건부)** — 06d 가 먼저 dev 에 머지됐을 때만 `[id].vue:3-7` 의 LNB 접기 연결.

순서: R1(A5·X3·X5 뒤 — 같은 화면 파일) → R2 → R3 → R4 → R5. R2~R4 는 R1 과 코드가 겹치지 않는다(순서만 R1 뒤). R6 은 이 자리에 적지만 **파트 S 의 S4 뒤에 판정·실행한다**(전역 실행 순서 S4 → R6 → K1) — ProposalStep 쪽 리스너(S4)가 그때 있다. 그때 06d 가 dev 에 없으면 건너뛰고, dev 머지 Task(Task Z4) Step 1 이 다시 판정한다.

이 파트의 프론트 Task 는 모두 nuxt 다. R1 만 fastapi 문구 네 줄(`research_proposal.py`·`research_work.py`)을 함께 고친다(서버 응답 문구 — 워커 무관). 06e worktree 의 파일이 CRLF 로 체크아웃됐으면 Edit 도구로 고친다(아래 old/new 는 줄 끝과 무관한 글자다). 이 파트의 모든 '교체 전/교체 후'·새 파일은 dev `da80f23` 프론트에 A3·A5 몫(이름 상수·두 버튼·import)을 흉내 내 얹은 통합 사본에 차례로 적용해 글자가 맞는지, vitest·`nuxi typecheck`(오류 0)·`npm run build`(완료, `Duplicated imports` 는 기준선의 `queueLine` 둘뿐)를 확인했다.

---

### Task R1: 단계 이름 바꾸기 — 보이는 글만

spec §12-4 제목 고르기 '이름'·참고문헌 선택하기 '이름', Q2 기본 '보고서'(정함 1 — Q2 가 함께 묻는 '딥리서치' 용어 포함), D23 '핵심 개념 칩 → 키워드 칩'(보이는 글). 진행 막대·이어가기 카드·온보딩·단계 화면 제목·버튼·안내·오류 문구가 '② 주제 ③ 읽기 목록 ④ 계획서'와 '핵심 개념'을 쓰고 있다. 이 Task 는 그 글을 '② 제목 고르기 ③ 참고문헌 선택하기 ④ 보고서'와 '키워드'로 바꾸고, ④ 이름과 겹치는 '보고서'(딥리서치 보고서를 가리키는 글)는 '딥리서치 보고서'로 쓴다.

**알아 둘 것:**
- **바꾸는 것은 보이는 글뿐이다.** 단계 키·주소 `?s=`·API 경로·식별자(`STEP_KEYS`·`ReadingStep`·`concepts` 등)·주석은 그대로 둔다. 주석 가운데 `WorkStepper.vue:3` 만 단계 이름을 적은 안내라 고친다(아래 grep 확인이 주석을 걸러도 이 줄은 HTML 주석 한 줄이 아니라 이름 목록이라 맞춰 둔다).
- **이름의 정본은 `workPhase.STEP_NAMES` 하나다(1-6 계약).** 지금의 비공개 `STEP_LABEL`(:14-19)을 내보내는 `STEP_NAMES` 로 갈음한다 — 진행 막대(`stepperItems`)·이어가기 카드(`continueCard` 의 미리보기)·온보딩(`ONBOARDING_STEPS` 의 제목·새 `ONBOARDING_LEAD`)이 이것을 읽고, 06d 사이드바도 이것과 `stepLine` 을 import 한다(06d 는 단계 이름 문자열을 따로 쓰지 않는다 — 06d 가 먼저 머지돼 있으면 06e 머지와 함께 이름이 따라 바뀐다).
- **마지막 단계 이름은 Task A3 의 `FINAL_STEP_NAME`("보고서")에서 오고, 조사가 붙지 않는 꼴에만 쓴다(정함 1).** `STEP_NAMES.proposal`·`4/4 단계 · ${FINAL_STEP_NAME} 쓰는 중`·ProposalStep 제목 `{{ FINAL_STEP_NAME }}`·ReadingStep 이동 버튼 `{{ FINAL_STEP_NAME }} 단계로`. 조사가 붙는 문장은 '보고서'를 글자 그대로 쓴다('보고서를 불러오는 중입니다'·'보고서에 쓸 논문을 담습니다'·'… 3단계를 거쳐 보고서 초안까지'). 버튼 이름을 문장에 넣을 때는 `[${MAKE_REPORT}]를` 꼴이라 조사가 '만들기' 뒤에 붙는다(이름이 바뀌어도 '…만들기]를' 이 맞다).
- **딥리서치 보고서를 가리키는 보이는 글에는 '딥리서치'를 붙인다(Q2 의 '딥리서치' 용어 — 정함 1).** ④ 이름이 '보고서'가 되면 단계 화면에서 같은 낱말이 두 뜻으로 쓰인다 — 바꾸기 전 TopicsStep `:8` 한 문장 안에서도 '「…」 보고서에서 이어 갈 주제'(딥리서치)와 '보고서를 만듭니다'(④)가 겹친다. 단계 화면(맨 위 요약 띠 포함)에서 딥리서치 보고서를 가리키는 글은 다음 다섯 곳과 온보딩 ② 본문(Step 3)이다: `TopicsStep.vue:8`(머리 안내), `OutlineEditor.vue:92`(4. 연구 공백 줄의 안내), `CandidateDrawer.vue:7`(critic 서랍 안내 — 같은 줄의 옛 이름 '읽기 후보'도 '참고문헌 후보'로), `pages/research/[id].vue:60`(요약 띠의 [보고서 보기] → [딥리서치 보고서 보기] — `goStep(null)` 은 ④ 가 아니라 딥리서치 보고서로 간다. §12-5 의 06e 자리 `:57-75` 안이다), `topicDeck.ts:34`(`SEED_KIND_LABEL.future` — 주제 카드 머리 줄 `seedLine`, `topicDeck.test.ts:194`·`:198` 이 이 글자를 기대해 ✎). 딥리서치 화면 자체(`[id].vue` 의 `rs-body` 쪽 '최종 보고서를 불러오는 중' 등 `:130-178`)는 06d 자리이고 그 화면에는 ④ 가 없어 그대로, `utils/researchReport.ts` 의 딥리서치 보고서 부품도 그대로다. 마지막 단계 이름이 '연구 초안'으로 바뀌어도(정함 1 의 전환 절차) 앞에 '딥리서치 '가 붙은 이 여섯 글은 고치지 않는다 — grep `보고서[를로가는의은이]` 이 내더라도 그대로 둔다.
- **앞 Task 뒤 기준:** `utils/workPhase.ts` 는 A3 가 `WORK_STEPS`(:9) 바로 아래에 `FINAL_STEP_NAME`·`MAKE_REPORT`·`REMAKE_REPORT` 를 둔 뒤다 — 이 Task 의 `STEP_NAMES` 가 `FINAL_STEP_NAME` 을, `ONBOARDING_STEPS` 가 `MAKE_REPORT` 를 읽으므로 두 상수가 `STEP_KEYS` 보다 위에 있어야 한다(모듈 첫 평가 때 `const` 는 선언 전에 읽을 수 없다). `workPhase.test.ts` 는 A3 가 import 목록에 세 이름을 더하고 끝에 describe `FINAL_STEP_NAME·버튼 이름` 을 붙인 뒤다. `ReadingStep.vue` 는 A5(버튼 글·확인 문구·오류 문구), `ProposalStep.vue` 는 A5·X3·X4·X5 가 먼저 고친다. 이 Task 의 old 는 모두 그 Task 들이 건드리지 않는 줄이다(뼈대 §3 표). 둘 다 A5 가 넣은 `import { MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";` 에 `FINAL_STEP_NAME` 을 더한다 — A5 가 import 를 다른 꼴로 두었으면 같은 import 문에 이름만 더하고, 이미 들어 있으면 그대로 둔다.
- **'핵심 개념' → '키워드'(보이는 글):** `ConceptChips.vue` 머리·빼기 버튼 이름·입력 칸(뒤에 Task K8 이 토글 칩으로 다시 짠다 — 이 Task 의 글을 바탕으로 쓴다), `TopicsStep.vue` 오류 문구 둘, `topicDeck.conceptsNote` 넷, `OutlineEditor.vue` 셋, `ProposalStep.vue:30`, 서버 `CONCEPTS_BUSY`(`research_work.py:53`)와 `patch_work` 의 422 문구(`:252`). 딥리서치 보고서의 `EXCLUDED_WHY`(`utils/researchReport.ts:48` '하위질문의 핵심 개념')는 다른 뜻이라 그대로 둔다.
- **서버 문구:** `research_proposal.py` 의 `VERSION_CONFLICT`(:58 — 화면에 보이는 409 문구)와 `IF_MATCH_FORMAT`(:57). `test_research_proposal_api.py:591` 은 상수를 읽어(`api.router.VERSION_CONFLICT`) 고치지 않아도 통과한다. `test_research_work_api.py:510` 은 `CONCEPTS_BUSY` 글자를 기대해 고친다. 프론트 `researchErrors.test.ts:106` 의 `CONFLICT` 는 손으로 쓴 응답 픽스처라 그대로 둔다(`utils/researchErrors.ts` 는 06e 파일이 아니고 문구를 만들지 않는다).
- **남는 옛 이름 확인(Step 8):** 찾는 옛 이름은 '계획서'·'읽기 목록'·'읽기 후보'·'주제 고르기'·'핵심 개념'이다('읽기 후보'는 `ReadingTable.vue:3` aria-label 과 `CandidateDrawer.vue:7` 안내 — '읽기 목록'만 찾으면 서랍 안내가 빠진다). `grep` 이 주석 줄을 걸러도 `OutlineEditor.vue:73`(`:72` 에서 시작한 HTML 주석의 둘째 줄) 한 줄은 남는다 — 그것만 나와야 한다. 기준선에서 보이는 글로 남던 `proposalDocument.ts:46`(`KIND_LABELS`)·`:69`·`:205`·`ProposalStep.vue:263` 은 Task X5 가 이미 고쳤다. 그 밖의 줄(A5·X3·X4 가 새로 쓴 글 등)이 나오면 이 Task 에서 '보고서'·'참고문헌'·'키워드' 로 고치고 커밋 메시지에 적는다.
- 줄 번호는 dev `da80f23` 기준이다(A3 가 `workPhase.ts`·`workPhase.test.ts` 위쪽에 줄을 더해 몇 줄 밀린다 — old 글자로 잡는다).

**Files:**
- Modify: `frontend/utils/workPhase.ts` (`STEP_LABEL` :14-19 → `STEP_NAMES`, `PHASE_LINE` :20-25, `stepperItems` :58, `ONBOARDING_KEY`·`ONBOARDING_STEPS` :113-131 사이에 `ONBOARDING_LEAD`, `continueCard` :166)
- Modify: `frontend/components/work/OnboardingModal.vue` (:12, import :31)
- Modify: `frontend/components/work/WorkStepper.vue` (:3 주석)
- Modify: `frontend/components/work/TopicsStep.vue` (:6-9, :58, :151, :156)
- Modify: `frontend/components/work/ReadingStep.vue` (:6-12, :25, :48-51, workPhase import)
- Modify: `frontend/components/work/ProposalStep.vue` (:6, :19, :30-31, :35, :120, :147, workPhase import)
- Modify: `frontend/components/work/OutlineEditor.vue` (:10, :14, :92, :201-202)
- Modify: `frontend/components/work/CandidateDrawer.vue` (:7)
- Modify: `frontend/components/work/FunnelCounter.vue` (:3)
- Modify: `frontend/components/work/ReadingTable.vue` (:3)
- Modify: `frontend/components/work/ConceptChips.vue` (:5, :16, :31-32)
- Modify: `frontend/composables/useReadingSaves.ts` (:53)
- Modify: `frontend/utils/topicDeck.ts` (`SEED_KIND_LABEL` :34, `conceptsNote` :223-230)
- Modify: `frontend/utils/readingList.ts` (`outlineHint` :147-150)
- Modify: `frontend/pages/research/[id].vue` (:60 요약 띠 버튼 글 — §12-5 의 06e 자리 `:57-75` 안)
- Modify: `app/api/research_proposal.py` (:57-58)
- Modify: `app/api/research_work.py` (:53, :252)
- Test: `frontend/tests/unit/workPhase.test.ts` (import 둘, :84-90, :96-98, :197-206, :216, :232-234)
- Test: `frontend/tests/unit/readingList.test.ts` (:244, :246)
- Test: `frontend/tests/unit/topicDeck.test.ts` (:194, :198, :305-312)
- Test: `app/tests/test_research_work_api.py` (:510)

기준선(X5 적용 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료, 백엔드 `test_research_work_api.py` `82 passed`(dev `da80f23` 값 — 파트 K 가 이 파일을 고치기 전이다). 이 Task 는 vitest 를 +1 한다(`workPhase.test.ts` 의 새 it 하나 — 나머지는 고친 it).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/workPhase.test.ts` — import 목록에 두 이름을 더한다(A3 가 더한 이름과 상관없이 아래 두 줄은 목록에 하나씩 있다).

교체 전:

```ts
  ONBOARDING_KEY,
```

교체 후:

```ts
  ONBOARDING_KEY,
  ONBOARDING_LEAD,
```

교체 전:

```ts
  WORK_STEPS,
```

교체 후:

```ts
  STEP_NAMES,
  WORK_STEPS,
```

같은 파일 — describe `stepForPhase·stepLine` 의 둘째 it 와 describe 끝(dev `:84-90`), 그 뒤에 새 describe `단계 이름` 을 둔다. 교체 전:

```ts
  it("진행 막대 옆 한 줄", () => {
    expect(stepLine("topics")).toBe("2/4 단계 · 주제 고르는 중");
    expect(stepLine("reading")).toBe("3/4 단계 · 읽기 목록 만드는 중");
    expect(stepLine("proposal")).toBe("4/4 단계 · 계획서 쓰는 중");
    expect(stepLine("done")).toBe("4/4 단계 · 완료");
  });
});
```

교체 후:

```ts
  it("진행 막대 옆 한 줄", () => {
    expect(stepLine("topics")).toBe("2/4 단계 · 제목 고르는 중");
    expect(stepLine("reading")).toBe("3/4 단계 · 참고문헌 고르는 중");
    expect(stepLine("proposal")).toBe("4/4 단계 · 보고서 쓰는 중");
    expect(stepLine("done")).toBe("4/4 단계 · 완료");
  });
});

describe("단계 이름", () => {
  it("STEP_NAMES 는 사이드바가 읽는 단계 이름이다", () => {
    expect(STEP_NAMES).toEqual({ explore: "탐색", topics: "제목 고르기", reading: "참고문헌 선택하기", proposal: "보고서" });
    // 진행 막대·이어가기 카드·온보딩이 같은 이름을 쓴다 — 화면마다 이름을 다시 쓰지 않는다
    expect(stepperItems("topics", null).map((i) => i.label)).toEqual(Object.values(STEP_NAMES));
    expect(ONBOARDING_STEPS.map((s) => s.title)).toEqual([STEP_NAMES.topics, STEP_NAMES.reading, STEP_NAMES.proposal]);
    // 마지막 단계 이름은 조사가 붙지 않는 꼴에만 쓴다(06e 정함 1) — '보고서를'·'보고서로' 를 상수로 만들지 않는다
    expect(stepLine("proposal")).toBe(`4/4 단계 · ${STEP_NAMES.proposal} 쓰는 중`);
  });
});
```

같은 파일 — describe `stepperItems` 첫 it 의 기대(dev `:96-98`). 교체 전:

```ts
      { key: "topics", label: "주제", state: "done", clickable: true },
      { key: "reading", label: "읽기 목록", state: "current", clickable: false },
      { key: "proposal", label: "계획서", state: "todo", clickable: false },
```

교체 후:

```ts
      { key: "topics", label: "제목 고르기", state: "done", clickable: true },
      { key: "reading", label: "참고문헌 선택하기", state: "current", clickable: false },
      { key: "proposal", label: "보고서", state: "todo", clickable: false },
```

같은 파일 — describe `continueCard` 첫 it(dev `:197-206`). 교체 전:

```ts
  it("이어가지 않았으면 4단계 미리보기(탐색 끝 · 주제 · 읽기 목록 · 계획서)와 [이 연구 이어가기]", () => {
    const card = continueCard(false, null);
    expect(card).toMatchObject({ title: "이 연구 이어가기", label: "이 연구 이어가기", action: "continue", note: null });
    expect(card.preview).toEqual([
      { label: "탐색 끝", state: "done" },
      { label: "주제", state: "todo" },
      { label: "읽기 목록", state: "todo" },
      { label: "계획서", state: "todo" },
    ]);
  });
```

교체 후:

```ts
  it("이어가지 않았으면 4단계 미리보기(탐색 끝 · 제목 고르기 · 참고문헌 선택하기 · 보고서)와 [이 연구 이어가기]", () => {
    const card = continueCard(false, null);
    expect(card).toMatchObject({
      title: "이 연구 이어가기",
      body: "탐색이 끝났습니다. 제목 고르기 → 참고문헌 선택하기 → 보고서 3단계를 거쳐 보고서 초안까지 이어 갈 수 있습니다.",
      label: "이 연구 이어가기",
      action: "continue",
      note: null,
    });
    expect(card.preview).toEqual([
      { label: "탐색 끝", state: "done" },
      { label: "제목 고르기", state: "todo" },
      { label: "참고문헌 선택하기", state: "todo" },
      { label: "보고서", state: "todo" },
    ]);
  });
```

같은 파일 — `이어간 연구면 지금 단계와 [이어간 연구 열기]` 의 기대 한 줄(dev `:216`). 교체 전:

```ts
      body: "3/4 단계 · 읽기 목록 만드는 중",
```

교체 후:

```ts
      body: "3/4 단계 · 참고문헌 고르는 중",
```

같은 파일 — describe `온보딩` 의 it 머리(dev `:232-234`, 아래 `for` 줄부터는 그대로). 교체 전:

```ts
  it("브라우저 저장 열쇠와 세 단계(주제·읽기 목록·계획서)의 설명·결정할 것", () => {
    expect(ONBOARDING_KEY).toBe("skx_work_onboarded");
    expect(ONBOARDING_STEPS.map((s) => s.title)).toEqual(["주제", "읽기 목록", "계획서"]);
```

교체 후:

```ts
  it("브라우저 저장 열쇠와 세 단계(제목 고르기·참고문헌 선택하기·보고서)의 설명·결정할 것", () => {
    expect(ONBOARDING_KEY).toBe("skx_work_onboarded");
    expect(ONBOARDING_LEAD).toBe("제목 고르기 → 참고문헌 선택하기 → 보고서 3단계를 거쳐 보고서 초안까지 갑니다.");
    expect(ONBOARDING_STEPS.map((s) => s.title)).toEqual(["제목 고르기", "참고문헌 선택하기", "보고서"]);
    // 마지막 단계는 [보고서 만들기] 한 번으로 목차·절이 서는 흐름을 알린다(D20)
    expect(ONBOARDING_STEPS[1]!.decide).toContain("[보고서 만들기]");
    expect(ONBOARDING_STEPS[2]!.body).toContain("[보고서 만들기]");
```

`frontend/tests/unit/readingList.test.ts` — describe `canMakeOutline·outlineHint` 둘째 it 의 두 단언. 교체 전(`:244`):

```ts
    expect(outlineHint(view(four))).toBe("담은 논문이 4편입니다 — 5편 이상 담으면 목차를 만들 수 있습니다");
```

교체 후:

```ts
    expect(outlineHint(view(four))).toBe("담은 논문이 4편입니다 — 5편 이상 담으면 보고서를 만들 수 있습니다");
```

교체 전(`:246`):

```ts
    expect(outlineHint(view(five, { topic_id: null }))).toBe("주제를 먼저 고르세요 — 고른 주제로 목차를 만듭니다");
```

교체 후:

```ts
    expect(outlineHint(view(five, { topic_id: null }))).toBe("주제를 먼저 고르세요 — 고른 주제로 보고서를 만듭니다");
```

`frontend/tests/unit/topicDeck.test.ts` — describe `seedLine` 의 두 단언(주제 카드 머리 줄 — 딥리서치 보고서의 향후 과제). 교체 전(`:194`):

```ts
    expect(seedLine(SEED)).toBe("보고서의 향후 과제 · 노인 우울과 사회적 지지의 관계");
```

교체 후:

```ts
    expect(seedLine(SEED)).toBe("딥리서치 보고서의 향후 과제 · 노인 우울과 사회적 지지의 관계");
```

교체 전(`:198`):

```ts
    expect(seedLine({ ...SEED, heading: "  " })).toBe("보고서의 향후 과제");
```

교체 후:

```ts
    expect(seedLine({ ...SEED, heading: "  " })).toBe("딥리서치 보고서의 향후 과제");
```

같은 파일 — describe `핵심 개념 칩` 의 it `conceptsNote — …`(describe 이름은 테스트 안의 이름이라 그대로 둔다 — 뒤 파트가 이 이름으로 자리를 잡는다). 교체 전(`:305-312`):

```ts
    expect(conceptsNote([], running)).toBe(`핵심 개념을 뽑는 중입니다 · ${genQueueLine(running)}`);
    expect(conceptsNote([], gen({ kind: "concepts", target: null, status: "failed" }))).toBe(
      "핵심 개념을 뽑지 못했습니다 — 직접 넣거나 [다시] 를 누르세요",
    );
    expect(conceptsNote([], gen({ kind: "concepts", target: null, status: "done" }))).toBe(
      "뽑힌 핵심 개념이 없습니다 — 직접 넣거나 [다시] 를 누르세요",
    );
    expect(conceptsNote([], null)).toBe("핵심 개념 넣기 — 원 질문의 핵심 개념을 칩으로 더하세요");
```

교체 후:

```ts
    expect(conceptsNote([], running)).toBe(`키워드를 뽑는 중입니다 · ${genQueueLine(running)}`);
    expect(conceptsNote([], gen({ kind: "concepts", target: null, status: "failed" }))).toBe(
      "키워드를 뽑지 못했습니다 — 직접 넣거나 [다시] 를 누르세요",
    );
    expect(conceptsNote([], gen({ kind: "concepts", target: null, status: "done" }))).toBe(
      "뽑힌 키워드가 없습니다 — 직접 넣거나 [다시] 를 누르세요",
    );
    expect(conceptsNote([], null)).toBe("키워드 넣기 — 원 질문의 키워드를 칩으로 더하세요");
```

`app/tests/test_research_work_api.py` — `TestPatchWork.test_concepts_cannot_change_while_concepts_are_being_made`(매개변수 둘). 교체 전(`:509-510`):

```python
        assert res.status_code == 409
        assert res.json()["detail"] == "핵심 개념을 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
```

교체 후:

```python
        assert res.status_code == 409
        assert res.json()["detail"] == "키워드를 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/workPhase.test.ts tests/unit/readingList.test.ts tests/unit/topicDeck.test.ts`
Expected: `Test Files  3 failed (3)` / `Tests  9 failed | <R1 앞 세 파일 합 − 8> passed (<R1 앞 세 파일 합 + 1>)`(A3 가 `workPhase.test.ts` 에 it 1개를 더했다면 `9 failed | 58 passed (67)` — 통합 사본 실측). 실패 아홉:
- `stepForPhase·stepLine > 진행 막대 옆 한 줄` — `AssertionError: expected '2/4 단계 · 주제 고르는 중' to be '2/4 단계 · 제목 고르는 중'`
- `단계 이름 > STEP_NAMES 는 사이드바가 읽는 단계 이름이다` — `AssertionError: expected undefined to deeply equal { explore: '탐색', …(3) }`
- `stepperItems > 탐색은 늘 끝난 단계이고, 도달한 단계가 지금 단계, 그 뒤는 아직이다` — `AssertionError: expected [ { key: 'explore', …(3) }, …(3) ] to deeply equal …`
- `continueCard > 이어가지 않았으면 4단계 미리보기(탐색 끝 · 제목 고르기 · 참고문헌 선택하기 · 보고서)와 [이 연구 이어가기]` — `AssertionError: expected { title: '이 연구 이어가기', …(5) } to match object …`
- `continueCard > 이어간 연구면 지금 단계와 [이어간 연구 열기]` — `AssertionError: expected { title: '이어간 연구', …(5) } to match object …`
- `온보딩 > 브라우저 저장 열쇠와 세 단계(제목 고르기·참고문헌 선택하기·보고서)의 설명·결정할 것` — `AssertionError: expected undefined to be '제목 고르기 → 참고문헌 선택하기 → 보고서 3단계를 거쳐 보고서 …'`
- `canMakeOutline·outlineHint > 담음이 모자라면 몇 편인지, 주제가 없으면 주제를 먼저 고르라고 알린다` — 옛 '목차를 만들 수 있습니다'
- `seedLine > 씨앗 종류와 절 소제목을 잇고, 씨앗이 없으면 null 이다` — `AssertionError: expected '보고서의 향후 과제 · 노인 우울과 사회적 지지의 관계' to be '딥리서치 보고서의 향후 과제 · 노인 우울과 사회적 지지의 관계'`
- `핵심 개념 칩 > conceptsNote — 뽑는 중이면 대기 문구를 잇고, 비었으면 넣기·다시를 안내한다` — 옛 '핵심 개념을 뽑는 중입니다'

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_api.py -q -p no:cacheprovider`
Expected: `2 failed, 80 passed`(dev `da80f23` 값) — `FAILED tests/test_research_work_api.py::TestPatchWork::test_concepts_cannot_change_while_concepts_are_being_made[queued]`·`[running]`(`AssertionError: assert '핵심 개념을 만드는 중입니다 — 끝난 뒤 고쳐 주세요' == '키워드를 만드는 중입니다 — 끝난 뒤 고쳐 주세요'`)

- [ ] **Step 3: 단계 이름의 정본 — `workPhase.ts`**

`frontend/utils/workPhase.ts` — 교체 전(dev `:11-25`):

```ts
// 진행 막대는 ① 탐색(딥리서치 — 이어갈 때 이미 끝나 있다)부터 센다
type StepKey = "explore" | WorkStep;
const STEP_KEYS: readonly StepKey[] = ["explore", ...WORK_STEPS];
const STEP_LABEL: Record<StepKey, string> = {
  explore: "탐색",
  topics: "주제",
  reading: "읽기 목록",
  proposal: "계획서",
};
const PHASE_LINE: Record<WorkPhase, string> = {
  topics: "2/4 단계 · 주제 고르는 중",
  reading: "3/4 단계 · 읽기 목록 만드는 중",
  proposal: "4/4 단계 · 계획서 쓰는 중",
  done: "4/4 단계 · 완료",
};
```

교체 후:

```ts
// 진행 막대는 ① 탐색(딥리서치 — 이어갈 때 이미 끝나 있다)부터 센다
type StepKey = "explore" | WorkStep;
const STEP_KEYS: readonly StepKey[] = ["explore", ...WORK_STEPS];
// 단계의 보이는 이름(spec §12-4 D23·D24 — 키·주소 ?s=·API 는 그대로). 진행 막대·이어가기 카드·온보딩이 쓰고 사이드바(06d)도
// 이것을 읽는다 — 화면마다 이름을 다시 쓰지 않는다. 마지막 단계 이름은 FINAL_STEP_NAME 하나에서 온다(06e 정함 1)
export const STEP_NAMES: Readonly<Record<"explore" | WorkStep, string>> = {
  explore: "탐색",
  topics: "제목 고르기",
  reading: "참고문헌 선택하기",
  proposal: FINAL_STEP_NAME,
};
const PHASE_LINE: Record<WorkPhase, string> = {
  topics: "2/4 단계 · 제목 고르는 중",
  reading: "3/4 단계 · 참고문헌 고르는 중",
  proposal: `4/4 단계 · ${FINAL_STEP_NAME} 쓰는 중`,
  done: "4/4 단계 · 완료",
};
```

같은 파일 — `stepperItems` 의 반환 줄(dev `:58`). 교체 전:

```ts
    return { key, label: STEP_LABEL[key], state, clickable: state !== "todo" && key !== viewing };
```

교체 후:

```ts
    return { key, label: STEP_NAMES[key], state, clickable: state !== "todo" && key !== viewing };
```

같은 파일 — 온보딩(dev `:113-131`). 교체 전:

```ts
export const ONBOARDING_KEY = "skx_work_onboarded";

export const ONBOARDING_STEPS: readonly { title: string; body: string; decide: string }[] = [
  {
    title: "주제",
    body: "보고서의 향후 과제와 근거가 부족했던 하위질문에서 주제 카드를 만듭니다. 카드마다 연구 질문과 근거 논문이 붙습니다.",
    decide: "카드 하나를 고릅니다. 카드를 고치거나 직접 쓸 수도 있습니다.",
  },
  {
    title: "읽기 목록",
    body: "탐색에서 채택한 논문이 후보로 들어와 있습니다. 논문마다 들어온 경로를 볼 수 있고, 자기점검이 뺀 논문도 되살릴 수 있습니다.",
    decide: "읽을 논문을 담습니다. 5편 이상 담으면 목차를 만들 수 있습니다.",
  },
  {
    title: "계획서",
    body: "담은 논문으로 목차를 만들고 선행연구와 연구 공백 절을 근거 인용과 함께 씁니다. 결과·논의는 쓰지 않습니다.",
    decide: "목차를 승인하고 문단을 수락하거나 고친 뒤 Word 로 내려받습니다.",
  },
];
```

교체 후:

```ts
export const ONBOARDING_KEY = "skx_work_onboarded";

// 안내 머리 한 줄 — 단계 이름 뒤에는 조사를 붙이지 않는다('3단계를 거쳐')
export const ONBOARDING_LEAD = `${STEP_NAMES.topics} → ${STEP_NAMES.reading} → ${STEP_NAMES.proposal} 3단계를 거쳐 보고서 초안까지 갑니다.`;

export const ONBOARDING_STEPS: readonly { title: string; body: string; decide: string }[] = [
  {
    title: STEP_NAMES.topics,
    body: "딥리서치 보고서의 향후 과제와 근거가 부족했던 하위질문에서 제목 카드를 만듭니다. 고른 키워드가 카드 제목에 들어가고, 카드마다 연구 질문과 근거 논문이 붙습니다.",
    decide: "카드 하나를 고릅니다. 키워드를 바꿔 카드를 다시 만들거나, 카드를 고치거나 직접 쓸 수도 있습니다.",
  },
  {
    title: STEP_NAMES.reading,
    body: "탐색에서 채택한 논문이 후보로 들어와 있습니다. 제목을 누르면 오른쪽에서 그 논문과 대화(딥리드)할 수 있고, 들어온 경로를 보거나 자기점검이 뺀 논문을 되살릴 수 있습니다.",
    decide: `보고서에 쓸 논문을 담습니다. 5편 이상 담으면 [${MAKE_REPORT}]를 누를 수 있습니다.`,
  },
  {
    title: STEP_NAMES.proposal,
    body: `[${MAKE_REPORT}] 한 번으로 목차가 서고 선행연구·연구 공백 절을 근거 인용과 함께 씁니다. 결과·논의는 쓰지 않습니다.`,
    decide: "다 쓴 보고서를 읽고 필요하면 문단을 고치거나 수락한 뒤 Word 로 내려받습니다.",
  },
];
```

같은 파일 — `continueCard` 의 이어가기 안내(dev `:166`). 교체 전:

```ts
    body: "탐색이 끝났습니다. 주제 → 읽기 목록 → 계획서를 거쳐 연구계획서 초안까지 이어 갈 수 있습니다.",
```

교체 후:

```ts
    body: `탐색이 끝났습니다. ${STEP_NAMES.topics} → ${STEP_NAMES.reading} → ${STEP_NAMES.proposal} 3단계를 거쳐 보고서 초안까지 이어 갈 수 있습니다.`,
```

`STEP_LABEL` 을 쓰는 곳이 남지 않았는지 본다:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -rn "STEP_LABEL\b" utils components pages composables`
Expected: 빈 출력(`WorkStepper.vue` 의 `STATE_LABEL` 은 다른 이름이라 `\b` 로 걸러진다)

- [ ] **Step 4: 단계 화면·부품의 보이는 글**

`frontend/components/work/OnboardingModal.vue` — 교체 전(`:12`):

```html
        <p class="wk-modal__lead">주제 → 읽기 목록 → 계획서 3단계를 거쳐 연구계획서 초안까지 갑니다.</p>
```

교체 후:

```html
        <p class="wk-modal__lead">{{ ONBOARDING_LEAD }}</p>
```

교체 전(`:31`):

```ts
import { ONBOARDING_STEPS } from "~/utils/workPhase";
```

교체 후:

```ts
import { ONBOARDING_LEAD, ONBOARDING_STEPS } from "~/utils/workPhase";
```

`frontend/components/work/WorkStepper.vue` — 교체 전(`:3`):

```html
  <!-- 이어간 연구에만 그린다(spec §4) — ① 탐색 ② 주제 ③ 읽기 목록 ④ 계획서. 끝난 단계와 지금 단계는 눌러 다시 연다 -->
```

교체 후:

```html
  <!-- 이어간 연구에만 그린다(spec §4) — ① 탐색 ② 제목 고르기 ③ 참고문헌 선택하기 ④ 보고서(이름은 workPhase.STEP_NAMES).
       끝난 단계와 지금 단계는 눌러 다시 연다 -->
```

`frontend/components/work/TopicsStep.vue` — 교체 전(`:6-9`):

```html
      <h2 id="wk-topics-title" class="wk-screen__title" tabindex="-1">주제 고르기</h2>
      <p class="rs-muted">
        「{{ question }}」 보고서에서 이어 갈 주제를 하나 고릅니다. 고른 주제로 읽기 목록과 계획서를 만듭니다.
      </p>
```

교체 후:

```html
      <h2 id="wk-topics-title" class="wk-screen__title" tabindex="-1">제목 고르기</h2>
      <p class="rs-muted">
        「{{ question }}」 딥리서치 보고서에서 이어 갈 주제를 하나 고릅니다. 고른 주제로 참고문헌을 고르고 보고서를 만듭니다.
      </p>
```

(앞 '보고서'는 딥리서치 보고서, 뒤 '보고서'는 ④ — 알아 둘 것의 '딥리서치' 규칙.)

교체 전(`:58`):

```html
        <button type="button" class="rs-btn" @click="emit('go', 'reading')">읽기 목록으로</button>
```

교체 후:

```html
        <button type="button" class="rs-btn" @click="emit('go', 'reading')">참고문헌 선택하기로</button>
```

교체 전(`:151`):

```ts
    "핵심 개념을 저장하지 못했습니다",
```

교체 후:

```ts
    "키워드를 저장하지 못했습니다",
```

교체 전(`:156`):

```ts
  void act(() => api.retryGeneration(props.jobId, genId), ["work"], "핵심 개념을 다시 부르지 못했습니다");
```

교체 후:

```ts
  void act(() => api.retryGeneration(props.jobId, genId), ["work"], "키워드를 다시 부르지 못했습니다");
```

`frontend/components/work/ReadingStep.vue` — 머리(`:6-12`, A5 는 이 줄들을 고치지 않는다). 교체 전:

```html
      <h2 id="wk-reading-title" class="wk-screen__title" tabindex="-1">읽기 목록</h2>
      <p class="rs-muted">
        「{{ question }}」 탐색의 채택 근거가 후보로 들어와 있습니다. 읽을 논문을 담고, 담은 논문으로 계획서의 선행연구
        목차를 만듭니다.
      </p>
      <p v-if="topicTitle" class="wk-screen__picked">고른 주제 <strong>{{ topicTitle }}</strong></p>
      <p v-if="reading?.stale" class="rs-muted"><span class="rs-badge">다시 맞춤 필요</span> 목차를 만든 뒤 고른 주제가 바뀌었습니다 — 담은 논문을 다시 보고 [목차 다시 만들기]로 맞추세요.</p>
```

교체 후:

```html
      <h2 id="wk-reading-title" class="wk-screen__title" tabindex="-1">참고문헌 선택하기</h2>
      <p class="rs-muted">
        「{{ question }}」 탐색의 채택 근거가 후보로 들어와 있습니다. 보고서에 쓸 논문을 담습니다.
      </p>
      <p v-if="topicTitle" class="wk-screen__picked">고른 주제 <strong>{{ topicTitle }}</strong></p>
      <p v-if="reading?.stale" class="rs-muted"><span class="rs-badge">다시 맞춤 필요</span> 목차를 만든 뒤 고른 주제가 바뀌었습니다 — 담은 논문을 다시 보고 [{{ REMAKE_REPORT }}]로 맞추세요.</p>
```

교체 전(`:25`):

```html
      <p>읽기 목록을 불러오는 중입니다</p>
```

교체 후:

```html
      <p>참고문헌 후보를 불러오는 중입니다</p>
```

교체 전(`:48-51` — A5 는 그 아래 :52-69 의 두 버튼 글만 고친다):

```html
          주제 고르기
        </button>
        <template v-else-if="outlineMade">
          <button type="button" class="rs-btn" @click="emit('go', 'proposal')">계획서로</button>
```

교체 후:

```html
          제목 고르기
        </button>
        <template v-else-if="outlineMade">
          <button type="button" class="rs-btn" @click="emit('go', 'proposal')">{{ FINAL_STEP_NAME }} 단계로</button>
```

같은 파일 script — A5 가 넣은 workPhase import. 교체 전:

```ts
import { MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";
```

교체 후:

```ts
import { FINAL_STEP_NAME, MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";
```

`frontend/components/work/ProposalStep.vue` — 교체 전(`:6`):

```html
      <h2 id="wk-proposal-title" class="wk-proposal__title" tabindex="-1">연구계획서</h2>
```

교체 후:

```html
      <h2 id="wk-proposal-title" class="wk-proposal__title" tabindex="-1">{{ FINAL_STEP_NAME }}</h2>
```

교체 전(`:19`):

```html
      <p>계획서를 불러오는 중입니다</p>
```

교체 후:

```html
      <p>보고서를 불러오는 중입니다</p>
```

교체 전(`:30-31` — 그 아래 :34 의 버튼 글은 A5 가 고쳤다):

```html
          읽기 목록에 논문을 5편 이상 담으면 목차를 만들 수 있습니다. 선행연구 묶음의 수와 배정은 담은 논문의 핵심 개념
          소속으로 서버가 정합니다.
```

교체 후:

```html
          참고문헌에 논문을 5편 이상 담으면 보고서를 만들 수 있습니다. 선행연구 묶음의 수와 배정은 담은 논문의 키워드
          소속으로 서버가 정합니다.
```

교체 전(`:35`):

```html
          <button type="button" class="rs-btn rs-btn--ghost" @click="emit('go', 'reading')">읽기 목록으로</button>
```

교체 후:

```html
          <button type="button" class="rs-btn rs-btn--ghost" @click="emit('go', 'reading')">참고문헌 선택하기로</button>
```

교체 전(`:120`):

```ts
const CONFLICT = "다른 곳에서 계획서가 바뀌어 다시 불러왔습니다 — 바뀐 내용을 확인한 뒤 다시 해 주세요";
```

교체 후:

```ts
const CONFLICT = "다른 곳에서 보고서가 바뀌어 다시 불러왔습니다 — 바뀐 내용을 확인한 뒤 다시 해 주세요";
```

교체 전(`:147`):

```ts
    ? "주제나 읽기 목록이 바뀌었습니다 — 목차를 다시 만들면 지금 담은 논문으로 묶음을 새로 나눕니다(지금 목차를 바꿉니다)."
```

교체 후:

```ts
    ? "주제나 참고문헌이 바뀌었습니다 — 목차를 다시 만들면 지금 담은 논문으로 묶음을 새로 나눕니다(지금 목차를 바꿉니다)."
```

같은 파일 script — A5 가 넣은 workPhase import. 교체 전:

```ts
import { MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";
```

교체 후:

```ts
import { FINAL_STEP_NAME, MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";
```

`frontend/components/work/OutlineEditor.vue` — 교체 전(`:10`):

```html
      목차를 만든 뒤 주제나 읽기 목록이 바뀌었습니다. 지금 목차는 지우지 않고 그대로 두었습니다 — 바뀐 목록으로 묶음을
```

교체 후:

```html
      목차를 만든 뒤 주제나 참고문헌이 바뀌었습니다. 지금 목차는 지우지 않고 그대로 두었습니다 — 바뀐 목록으로 묶음을
```

교체 전(`:14`):

```html
      모델이 목차 초안을 만들지 못해 묶음 이름은 묶음의 핵심 개념으로, 연구 질문 후보는 고른 주제의 질문으로 채웠습니다.
```

교체 후:

```html
      모델이 목차 초안을 만들지 못해 묶음 이름은 묶음의 키워드로, 연구 질문 후보는 고른 주제의 질문으로 채웠습니다.
```

교체 전(`:92` — 4. 연구 공백 줄. 이 '보고서'는 딥리서치 보고서다):

```html
        <p class="rs-muted">보고서의 향후 과제와 근거가 부족했던 하위질문으로 씁니다 — {{ gapNote }}로만 적습니다.</p>
```

교체 후:

```html
        <p class="rs-muted">딥리서치 보고서의 향후 과제와 근거가 부족했던 하위질문으로 씁니다 — {{ gapNote }}로만 적습니다.</p>
```

교체 전(`:201-202`):

```ts
      ? "핵심 개념이 비어 담은 논문의 하위질문 소속으로 묶음을 나눴습니다."
      : "묶음 수와 배정은 담은 논문의 핵심 개념 소속으로 서버가 정했습니다.";
```

교체 후:

```ts
      ? "키워드가 비어 담은 논문의 하위질문 소속으로 묶음을 나눴습니다."
      : "묶음 수와 배정은 담은 논문의 키워드 소속으로 서버가 정했습니다.";
```

`frontend/components/work/FunnelCounter.vue` — 교체 전(`:3`):

```html
  <p class="wk-funnel"><span class="rs-sr-only">읽기 목록 깔때기: </span>{{ line }}</p>
```

교체 후:

```html
  <p class="wk-funnel"><span class="rs-sr-only">참고문헌 후보 깔때기: </span>{{ line }}</p>
```

`frontend/components/work/ReadingTable.vue` — 교체 전(`:3`):

```html
  <ol v-if="rows.length" class="wk-reading" aria-label="읽기 후보">
```

교체 후:

```html
  <ol v-if="rows.length" class="wk-reading" aria-label="참고문헌 후보">
```

`frontend/components/work/CandidateDrawer.vue` — critic 서랍 안내(`:6-7` 의 둘째 줄 — 옛 이름 '읽기 후보'와 딥리서치 보고서를 가리키는 '보고서'). 교체 전(`:7`):

```html
      critic 메모를 함께 보입니다. [되살리기] 를 누르면 읽기 후보로 들어옵니다 — 보고서는 바뀌지 않습니다.
```

교체 후:

```html
      critic 메모를 함께 보입니다. [되살리기] 를 누르면 참고문헌 후보로 들어옵니다 — 딥리서치 보고서는 바뀌지 않습니다.
```

`frontend/pages/research/[id].vue` — 단계 화면 맨 위 요약 띠의 버튼(§12-5 의 06e 자리 `:57-75` 안 — `goStep(null)` 은 ?s= 를 지워 딥리서치 보고서로 간다). 교체 전(`:60`):

```html
            <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="goStep(null)">보고서 보기</button>
```

교체 후:

```html
            <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="goStep(null)">딥리서치 보고서 보기</button>
```

`frontend/components/work/ConceptChips.vue` — 교체 전(`:5`):

```html
      <h3 id="wk-concepts-title" class="wk-concepts__title">핵심 개념</h3>
```

교체 후:

```html
      <h3 id="wk-concepts-title" class="wk-concepts__title">키워드</h3>
```

교체 전(`:16`):

```html
          :aria-label="`핵심 개념 ${concept} 빼기`"
```

교체 후:

```html
          :aria-label="`키워드 ${concept} 빼기`"
```

교체 전(`:31-32`):

```html
        :placeholder="full ? `핵심 개념은 ${CONCEPTS_MAX}개까지입니다` : '핵심 개념 넣기 — Enter 로 더합니다'"
        aria-label="핵심 개념 넣기"
```

교체 후:

```html
        :placeholder="full ? `키워드는 ${CONCEPTS_MAX}개까지입니다` : '키워드 넣기 — Enter 로 더합니다'"
        aria-label="키워드 넣기"
```

- [ ] **Step 5: utils·composable 의 보이는 글**

`frontend/composables/useReadingSaves.ts` — 교체 전(`:53`):

```ts
      deps.error.value = workErrorMessage(err, "읽기 목록을 고치지 못했습니다");
```

교체 후:

```ts
      deps.error.value = workErrorMessage(err, "참고문헌 목록을 고치지 못했습니다");
```

`frontend/utils/topicDeck.ts` — 주제 카드 머리 줄(`seedLine`)의 씨앗 종류 이름(`SEED_KIND_LABEL` `:33-36` 가운데 한 줄 — 바로 위 `CHIP_TITLE_CHARS` 두 줄 `:31-32` 는 Task H1 이 잡는 자리라 건드리지 않는다). 교체 전(`:34`):

```ts
  future: "보고서의 향후 과제",
```

교체 후:

```ts
  future: "딥리서치 보고서의 향후 과제",
```

같은 파일 — `conceptsNote` 안(`:223-230`, 함수 머리·`case "ready"` 는 그대로). 교체 전:

```ts
      return line ? `핵심 개념을 뽑는 중입니다 · ${line}` : "핵심 개념을 뽑는 중입니다";
    }
    case "failed":
      return "핵심 개념을 뽑지 못했습니다 — 직접 넣거나 [다시] 를 누르세요";
    case "empty":
      return generation
        ? "뽑힌 핵심 개념이 없습니다 — 직접 넣거나 [다시] 를 누르세요"
        : "핵심 개념 넣기 — 원 질문의 핵심 개념을 칩으로 더하세요";
```

교체 후:

```ts
      return line ? `키워드를 뽑는 중입니다 · ${line}` : "키워드를 뽑는 중입니다";
    }
    case "failed":
      return "키워드를 뽑지 못했습니다 — 직접 넣거나 [다시] 를 누르세요";
    case "empty":
      return generation
        ? "뽑힌 키워드가 없습니다 — 직접 넣거나 [다시] 를 누르세요"
        : "키워드 넣기 — 원 질문의 키워드를 칩으로 더하세요";
```

`frontend/utils/readingList.ts` — `outlineHint` 안(`:147-150`). 교체 전:

```ts
  if (view.topic_id === null) return "주제를 먼저 고르세요 — 고른 주제로 목차를 만듭니다";
  const n = pickedCount(view);
  if (n < MIN_READING_FOR_OUTLINE) {
    return `담은 논문이 ${n}편입니다 — ${MIN_READING_FOR_OUTLINE}편 이상 담으면 목차를 만들 수 있습니다`;
```

교체 후:

```ts
  if (view.topic_id === null) return "주제를 먼저 고르세요 — 고른 주제로 보고서를 만듭니다";
  const n = pickedCount(view);
  if (n < MIN_READING_FOR_OUTLINE) {
    return `담은 논문이 ${n}편입니다 — ${MIN_READING_FOR_OUTLINE}편 이상 담으면 보고서를 만들 수 있습니다`;
```

- [ ] **Step 6: 서버 문구**

`app/api/research_proposal.py` — 교체 전(`:57-58`, A1·A2·X1 은 이 두 줄을 고치지 않는다):

```python
IF_MATCH_FORMAT = "If-Match 는 계획서 버전 숫자입니다"
VERSION_CONFLICT = "다른 곳에서 계획서가 바뀌었습니다 — 다시 불러온 뒤 고쳐 주세요"
```

교체 후:

```python
IF_MATCH_FORMAT = "If-Match 는 보고서 버전 숫자입니다"
VERSION_CONFLICT = "다른 곳에서 보고서가 바뀌었습니다 — 다시 불러온 뒤 고쳐 주세요"
```

`app/api/research_work.py` — 교체 전(`:53`):

```python
CONCEPTS_BUSY = "핵심 개념을 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
```

교체 후:

```python
CONCEPTS_BUSY = "키워드를 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
```

교체 전(`:252`, `patch_work` 안):

```python
            raise HTTPException(status_code=422, detail="핵심 개념을 1개 이상 넣어 주세요")
```

교체 후:

```python
            raise HTTPException(status_code=422, detail="키워드를 1개 이상 넣어 주세요")
```

- [ ] **Step 7: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/workPhase.test.ts tests/unit/readingList.test.ts tests/unit/topicDeck.test.ts`
Expected: `Test Files  3 passed (3)` / `Tests  <R1 앞 세 파일 합 + 1> passed`(통합 사본 `67 passed (67)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_api.py tests/test_research_proposal_api.py -q -p no:cacheprovider`
Expected: 실패 0 — `<82 + R1 앞 test_research_proposal_api.py 의 수> passed`(dev `da80f23` 만 놓고 `177 passed` — A1·A2·X1 이 더한 수만큼 늘어난다)

- [ ] **Step 8: 남은 옛 이름을 찾는다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -rn "계획서\|읽기 목록\|읽기 후보\|주제 고르기\|핵심 개념" frontend/components/work frontend/utils/workPhase.ts frontend/utils/proposal*.ts frontend/utils/readingList.ts frontend/utils/topicDeck.ts frontend/composables/useReadingSaves.ts | grep -v -E '^[^:]+:[0-9]+:[[:space:]]*(//|<!--)'`
Expected: 한 줄 — `frontend/components/work/OutlineEditor.vue:73:                       주제 카드·계획서 문단의 버튼과 같은 관례) -->`(`:72` 에서 시작한 HTML 주석의 둘째 줄). 다른 줄이 나오면 그 줄이 주석 안인지 보고, 보이는 글이면 이 Task 에서 고친 뒤 다시 돌린다(알아 둘 것).

딥리서치 보고서를 가리키는 다섯 곳에 '딥리서치'가 붙었는지 본다(온보딩 ② 본문은 `workPhase.ts` 라 A3 가 줄을 밀어 여기서 세지 않는다 — Step 3 의 글 그대로):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -n "딥리서치 보고서" frontend/components/work/TopicsStep.vue frontend/components/work/OutlineEditor.vue frontend/components/work/CandidateDrawer.vue frontend/utils/topicDeck.ts "frontend/pages/research/[id].vue"`
Expected: 다섯 줄(06d 가 06e 분기 전에 dev 에 들어와 있었으면 `[id].vue` 줄 번호만 다르다 — 글자로 본다):

```text
frontend/components/work/TopicsStep.vue:8:        「{{ question }}」 딥리서치 보고서에서 이어 갈 주제를 하나 고릅니다. 고른 주제로 참고문헌을 고르고 보고서를 만듭니다.
frontend/components/work/OutlineEditor.vue:92:        <p class="rs-muted">딥리서치 보고서의 향후 과제와 근거가 부족했던 하위질문으로 씁니다 — {{ gapNote }}로만 적습니다.</p>
frontend/components/work/CandidateDrawer.vue:7:      critic 메모를 함께 보입니다. [되살리기] 를 누르면 참고문헌 후보로 들어옵니다 — 딥리서치 보고서는 바뀌지 않습니다.
frontend/utils/topicDeck.ts:34:  future: "딥리서치 보고서의 향후 과제",
frontend/pages/research/[id].vue:60:            <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="goStep(null)">딥리서치 보고서 보기</button>
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -rn 'detail="[^"]*\(계획서\|핵심 개념\)\|= "[^"]*\(계획서\|핵심 개념\)' app/api/research_*.py`
Expected: 빈 출력(화면에 나가는 문구 상수·`detail=` 글에 옛 이름이 없다 — 모듈 docstring·주석의 '계획서'·'핵심 개념'은 개발 문서라 그대로 둔다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -n "VERSION_CONFLICT =\|IF_MATCH_FORMAT =\|CONCEPTS_BUSY =\|1개 이상 넣어" app/api/research_proposal.py app/api/research_work.py`
Expected: 네 줄(줄 번호는 앞 Task 가 밀었으면 다르다):

```text
app/api/research_proposal.py:57:IF_MATCH_FORMAT = "If-Match 는 보고서 버전 숫자입니다"
app/api/research_proposal.py:58:VERSION_CONFLICT = "다른 곳에서 보고서가 바뀌었습니다 — 다시 불러온 뒤 고쳐 주세요"
app/api/research_work.py:53:CONCEPTS_BUSY = "키워드를 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
app/api/research_work.py:252:            raise HTTPException(status_code=422, detail="키워드를 1개 이상 넣어 주세요")
```

- [ ] **Step 9: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <R1 앞과 같은 수> passed` / `Tests <R1 앞 + 1> passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep "Duplicated imports" | grep -c -E "STEP_NAMES|ONBOARDING_LEAD"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff -U0 HEAD -- "frontend/pages/research/[id].vue" | grep "^[+-][^+-]"`
Expected: 두 줄뿐(§12-5 — 06e 자리 `:57-75` 안의 요약 띠 버튼 글. 이 Task 가 `[id].vue` 를 처음 고친다):

```text
-            <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="goStep(null)">보고서 보기</button>
+            <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="goStep(null)">딥리서치 보고서 보기</button>
```

- [ ] **Step 10: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/utils/workPhase.ts && git add frontend/components/work/OnboardingModal.vue && git add frontend/components/work/WorkStepper.vue && git add frontend/components/work/TopicsStep.vue && git add frontend/components/work/ReadingStep.vue && git add frontend/components/work/ProposalStep.vue && git add frontend/components/work/OutlineEditor.vue && git add frontend/components/work/CandidateDrawer.vue && git add frontend/components/work/FunnelCounter.vue && git add frontend/components/work/ReadingTable.vue && git add frontend/components/work/ConceptChips.vue && git add frontend/composables/useReadingSaves.ts && git add frontend/utils/topicDeck.ts && git add frontend/utils/readingList.ts && git add "frontend/pages/research/[id].vue" && git add frontend/tests/unit/workPhase.test.ts && git add frontend/tests/unit/readingList.test.ts && git add frontend/tests/unit/topicDeck.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 단계 이름을 ② 제목 고르기 ③ 참고문헌 선택하기 ④ 보고서로, '핵심 개념'을 '키워드'로 바꾼다(보이는 글만 — 단계 키·주소 ?s=·API 는 그대로). 이름의 정본은 workPhase 가 내보내는 STEP_NAMES 하나이고 진행 막대·이어가기 카드·온보딩(새 ONBOARDING_LEAD)이 이것을 읽는다 — 06d 사이드바도 이것과 stepLine 을 읽어 따라 바뀐다. 마지막 단계 이름은 FINAL_STEP_NAME 에서 오고 조사가 붙지 않는 꼴(제목·'보고서 단계로'·'4/4 단계 · 보고서 쓰는 중')에만 쓴다. 온보딩은 키워드로 제목 카드를 만들고 제목을 누르면 딥리드가 열리며 [보고서 만들기] 한 번으로 목차·절이 서는 06e 흐름으로 고쳐 쓴다. ④ 이름과 겹치지 않게 단계 화면에서 딥리서치 보고서를 가리키는 글(제목 고르기 머리 안내·연구 공백 줄 안내·critic 서랍 안내·주제 카드 머리 줄·요약 띠의 [딥리서치 보고서 보기])에는 '딥리서치'를 붙이고, 서랍 안내의 '읽기 후보'도 '참고문헌 후보'로 맞춘다. 딥리서치 보고서의 '하위질문의 핵심 개념'(제외 사유)은 다른 뜻이라 그대로 둔다"
```

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/api/research_proposal.py && git add app/api/research_work.py && git add app/tests/test_research_work_api.py && git status --short && git commit -m "[Feat] round06e — 서버가 화면에 내는 문구의 단계 이름을 맞춘다: 버전 충돌 409 와 If-Match 형식 422 는 '계획서'를 '보고서'로, 개념 생성 중 409(CONCEPTS_BUSY)와 빈 개념 422 는 '핵심 개념'을 '키워드'로. 상수 이름·응답 모양은 그대로다"
```

---

### Task R2: 딥리드 스트림 분리 — SSE 파서·useDeepReadChat

spec §12-4 'BookChat 을 끼우기 전 고칠 것' — cntsId 감시로 대화 바꾸기·선택 prop `store`·`AbortController` 로 닫기·논문 바꾸기에서 끊기·스트림 로직을 composable + 순수 SSE 파서로 빼서 vitest, 정함 20·21. 오른쪽 패널(Task R4·R5)이 BookChat 하나에 논문을 바꿔 넘기므로, 끼우기 전에 대화 흐름을 고친다.

**알아 둘 것:**
- **지금 BookChat 의 두 결함:** ① `cntsId` 를 감시하지 않는다(`BookChat.vue:77-80`) — 같은 BookChat 에 다른 논문을 넘기면 앞 논문의 대화가 남고, 다음 질문이 앞 논문의 대화를 `history` 로 싣는다. 논문 검색 결과 채팅 패널(`pages/papers/index.vue:564-569`)이 `:key` 없이 `chatPaperId` 만 바꿔 이미 이 버그가 있다 — composable 의 `watch(cntsId)` 가 부르는 쪽을 고치지 않고 함께 고친다(store 가 없으면 비운다). ② 스트림을 끊을 장치가 없다 — 패널을 닫거나 논문을 바꿔도 받던 답이 계속 흐른다. `AbortController` 로 끊는다.
- **끊은 답(정함 21):** 받은 글 + `\n\n(답을 받다가 멈췄습니다)`(받은 글이 없으면 `(답을 받기 전에 멈췄습니다)`)를 assistant 메시지로 **그 논문의 대화에** 남긴다 — 질문만 남으면 다음 질문의 `history` 가 user 두 개로 이어진다. 논문을 바꿔 끊긴 경우 `messages` 는 이미 새 논문 대화로 바뀌었으므로, `send` 가 시작할 때 쥔 그 논문의 배열(`run.list`)에 넣는다.
- **늦게 끝난 읽기:** `stop()` 은 곧바로 `current = null`·`isStreaming = false` 로 두고, 끊긴 `send` 는 `current !== run` 을 보고 아무것도 하지 않고 돌아간다 — 그 사이 새 논문에서 보낸 질문의 상태를 건드리지 않는다.
- **논문별 대화(정함 20):** `store` 가 있으면 그 논문의 배열을 그대로 쥔다 — `messages.value` 에 넣는 것이 곧 store 에 남는다(ref 가 감싼 reactive 프록시가 원래 배열을 고친다). 그래서 패널을 닫았다 다시 열거나 논문을 오가면 대화가 이어진다. 서버는 대화를 저장하지 않는다(요청마다 `history`).
- **SSE 읽기는 지금과 같다(`BookChat.vue:143-165`):** `\n` 으로 나눠 마지막 조각을 남기고 `data: ` 줄만, `{"text"}`·`{"sources"}`·`[DONE]`, 깨진 JSON 은 버린다. 지금 코드의 `[DONE]` 은 안쪽 `for` 만 빠져 그 조각의 남은 줄을 버리고 스트림 끝까지 읽는다 — 서버는 `[DONE]` 을 마지막에 보내므로(`services/chat/book_chat.py` 끝 `yield "data: [DONE]\n\n"`) `[DONE]` 에서 읽기를 끝내는 새 구현과 결과가 같다. 오류(`!resp.ok`·네트워크)는 지금처럼 받은 글을 버리고 `오류가 발생했습니다. 다시 시도해주세요.`(`CHAT_ERROR_TEXT` — `:167` 의 글 그대로).
- **테스트 환경은 node 다(`vitest.config.ts`).** `useApi` 는 Nuxt 의 `useRuntimeConfig` 를 읽어 `vi.mock("~/composables/useApi", …)` 로 주소 조립만 흉내 낸다(`usePdfOpener.test.ts:5-9` 관례 — composable 이 `./useApi` 로 import 해도 같은 모듈로 잡힌다). `Response`·`ReadableStream`·`TextEncoder`·`DOMException` 은 Node 22 전역이다. composable 은 `vue` 의 `ref`·`watch`·`onScopeDispose` 를 import 한다(테스트가 Nuxt 자동 import 없이 돈다). 테스트는 `effectScope` 안에서 부르고 `scope.stop()` 으로 BookChat 이 내려가는 것을 흉내 낸다.
- **BookChat 은 script 만 바꾼다**(템플릿 `:1-71` 은 Task R3). 지금 script 는 `ref`·`nextTick` 을 Nuxt 자동 import 에 기댔다 — 다른 부품처럼 `vue` 에서 import 한다. `store` prop 은 composable 을 잇는 이 Task 에서 단다(1-7 표 'R2·R3'), `docKind`·`pdfLinks`·`open-pdf` 는 R3 이다. 기존 네 화면(논문 상세·논문 검색 결과 채팅·도서 상세·`TopResult`)은 `store` 를 넘기지 않아 논문이 바뀌면 대화를 비운다 — 지금 '바뀌지 않는' 버그 대신이다.
- **입력 칸 초점:** 지금처럼 답을 다 받으면 입력 칸으로 돌아간다. 다만 논문을 바꿔 끊긴 경우(보낼 때의 `cntsId` 와 다르면)는 옮기지 않는다 — 사용자가 표에서 누른 다음 제목에 초점이 있다. 패널을 닫아 끊긴 경우는 BookChat 이 내려가 `inputEl` 이 없다.
- **이름(1-6):** `DeepReadSource`·`DeepReadMessage`·`DeepReadEvent`·`parseSse`·`CHAT_ERROR_TEXT`·`CHAT_STOPPED_TEXT`·`CHAT_STOPPED_EMPTY` 는 `utils/deepReadSse.ts` 만, `useDeepReadChat`(옵션·반환 타입 이름 `DeepReadChatOptions`·`DeepReadChat`)은 `composables/useDeepReadChat.ts` 만 내보낸다 — dev `da80f23` 에서 `grep -rnwE "parseSse|DeepReadMessage|useDeepReadChat|CHAT_ERROR_TEXT" frontend/utils frontend/composables frontend/components frontend/pages` 빈 출력(확인함).

**Files:**
- Create: `frontend/utils/deepReadSse.ts`
- Create: `frontend/composables/useDeepReadChat.ts`
- Modify: `frontend/components/BookChat.vue` (script `:73-180` 전부)
- Test: Create `frontend/tests/unit/deepReadSse.test.ts`, Create `frontend/tests/unit/useDeepReadChat.test.ts`

기준선(R1 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 파일을 +2, 테스트를 +10 한다(`deepReadSse.test.ts` 3·`useDeepReadChat.test.ts` 7).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

Create `frontend/tests/unit/deepReadSse.test.ts`:

```ts
// frontend/tests/unit/deepReadSse.test.ts
import { describe, expect, it } from "vitest";
import { parseSse } from "~/utils/deepReadSse";

describe("parseSse", () => {
  it("조각 경계에 걸린 줄은 남겨 두었다가 다음 조각과 잇는다", () => {
    const first = parseSse("", 'data: {"text": "노인 우울은"}\n\ndata: {"te');
    expect(first.events).toEqual([{ type: "text", text: "노인 우울은" }]);
    expect(first.buffer).toBe('data: {"te');
    const second = parseSse(first.buffer, 'xt": " 사회적 지지와"}\n\n');
    expect(second.events).toEqual([{ type: "text", text: " 사회적 지지와" }]);
    expect(second.buffer).toBe("");
  });

  it("글·출처·[DONE] 을 차례대로 읽고, [DONE] 뒤의 줄은 읽지 않는다", () => {
    const sources = [{ page_start: 5, page_end: 7, text: "가족 지지가 높을수록 우울이 낮았다." }];
    const chunk = [
      'data: {"text": "답"}',
      "",
      `data: ${JSON.stringify({ sources })}`,
      "",
      "data: [DONE]",
      "",
      'data: {"text": "뒤에 온 글"}',
      "",
    ].join("\n");
    expect(parseSse("", chunk)).toEqual({
      buffer: "",
      events: [{ type: "text", text: "답" }, { type: "sources", sources }, { type: "done" }],
    });
    // 서버가 줄 끝에 \r 을 붙여도(\r\n) 같은 값이다
    expect(parseSse("", "data: [DONE]\r\n").events).toEqual([{ type: "done" }]);
  });

  it("data: 가 아닌 줄·깨진 JSON·빈 글·모르는 모양은 버린다", () => {
    const chunk = [
      ": keep-alive",
      "event: message",
      "data: {깨진",
      'data: {"text": ""}',
      'data: {"other": 1}',
      "data: 3",
      'data: {"text": "남는 글"}',
      "",
    ].join("\n");
    expect(parseSse("", chunk).events).toEqual([{ type: "text", text: "남는 글" }]);
  });
});
```

Create `frontend/tests/unit/useDeepReadChat.test.ts`:

```ts
// frontend/tests/unit/useDeepReadChat.test.ts
import { describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { useDeepReadChat } from "~/composables/useDeepReadChat";
import { CHAT_ERROR_TEXT, CHAT_STOPPED_EMPTY, CHAT_STOPPED_TEXT, type DeepReadMessage } from "~/utils/deepReadSse";

// useApi 는 Nuxt 런타임 설정을 읽는다 — 여기서는 주소 조립만 흉내 낸다(usePdfOpener.test 와 같다)
vi.mock("~/composables/useApi", () => ({
  apiUrl: (path: string) => `/api${path}`,
  apiHeaders: (extra: Record<string, string> = {}) => ({ ...extra, "x-session-id": "sid" }),
}));

// 스트림을 손으로 흘리는 fetch — 부를 때마다 새 본문을 만들고, signal 이 abort 되면 진짜 fetch 처럼 본문을 AbortError 로 끊는다
function streamFetch() {
  const enc = new TextEncoder();
  const calls: { url: string; init: RequestInit }[] = [];
  let ctl: ReadableStreamDefaultController<Uint8Array> | null = null;
  const fetchFn = vi.fn((url: string, init: RequestInit) => {
    calls.push({ url, init });
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        ctl = c;
      },
    });
    const stream = ctl!;
    init.signal?.addEventListener("abort", () => stream.error(new DOMException("aborted", "AbortError")));
    return Promise.resolve(new Response(body, { status: 200 }));
  });
  return {
    fetchFn: fetchFn as unknown as typeof fetch,
    calls,
    push: (text: string) => ctl!.enqueue(enc.encode(text)),
    end: () => ctl!.close(),
  };
}

// 스트림 읽기는 여러 마이크로태스크를 건넌다 — 한 차례 매크로태스크까지 비운다
const flush = () => new Promise<void>((r) => setTimeout(r, 0));

function setup(opts: { id?: string; store?: Map<string, DeepReadMessage[]>; fetchFn?: typeof fetch } = {}) {
  const net = streamFetch();
  const id = ref(opts.id ?? "KCI_1");
  const scope = effectScope();
  const chat = scope.run(() =>
    useDeepReadChat({ cntsId: () => id.value, store: () => opts.store, fetchFn: opts.fetchFn ?? net.fetchFn }),
  )!;
  return { ...net, id, scope, chat };
}

describe("useDeepReadChat", () => {
  it("보낸 질문과 그 앞 대화를 history 로 싣는다", async () => {
    const { chat, calls, push, end } = setup();
    const first = chat.send("  이 논문의 대상은?  ");
    await flush();
    push('data: {"text": "노인 300명입니다."}\n\ndata: [DONE]\n\n');
    end();
    await first;

    const second = chat.send("방법은?");
    await flush();
    expect(calls).toHaveLength(2);
    const { url, init } = calls[1]!;
    expect(url).toBe("/api/books/chat/KCI_1");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json", "x-session-id": "sid" });
    expect(init.signal).toBeInstanceOf(AbortSignal);
    expect(JSON.parse(String(init.body))).toEqual({
      message: "방법은?",
      history: [
        { role: "user", content: "이 논문의 대상은?" },
        { role: "assistant", content: "노인 300명입니다." },
      ],
    });
    // 답을 받는 동안 또 보내면 무시한다
    await chat.send("셋째 질문");
    expect(calls).toHaveLength(2);
    chat.stop();
    await second;
  });

  it("흐른 글을 모아 두었다가 끝나면 출처와 함께 답 메시지가 된다", async () => {
    const { chat, push, end } = setup();
    const sent = chat.send("결론은?");
    await flush();
    expect(chat.isStreaming.value).toBe(true);
    expect(chat.messages.value).toEqual([{ role: "user", content: "결론은?" }]);

    push('data: {"text": "가족 지지가"}\n\n');
    await flush();
    expect(chat.streamingText.value).toBe("가족 지지가");

    const sources = [{ page_start: 5, page_end: 5, text: "가족 지지가 높을수록 우울이 낮았다." }];
    push(`data: {"text": " 우울을 낮춘다(p.5)."}\n\ndata: ${JSON.stringify({ sources })}\n\ndata: [DONE]\n\n`);
    end();
    await sent;
    expect(chat.messages.value).toEqual([
      { role: "user", content: "결론은?" },
      { role: "assistant", content: "가족 지지가 우울을 낮춘다(p.5).", sources },
    ]);
    expect(chat.streamingText.value).toBe("");
    expect(chat.isStreaming.value).toBe(false);
  });

  it("응답 오류(5xx)·네트워크 오류면 오류 문구를 답으로 남긴다", async () => {
    const failing = vi.fn().mockResolvedValue(new Response("x", { status: 500 }));
    const { chat } = setup({ fetchFn: failing as unknown as typeof fetch });
    await chat.send("질문");
    expect(chat.messages.value.at(-1)).toEqual({ role: "assistant", content: CHAT_ERROR_TEXT });
    expect(chat.isStreaming.value).toBe(false);

    const offline = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const other = setup({ fetchFn: offline as unknown as typeof fetch });
    await other.chat.send("질문");
    expect(other.chat.messages.value.at(-1)).toEqual({ role: "assistant", content: CHAT_ERROR_TEXT });
  });

  it("cntsId 가 바뀌면 스트림을 끊고 받던 글을 그 논문 대화에 남긴 뒤 store 의 새 논문 대화로 바꾼다", async () => {
    const earlier: DeepReadMessage[] = [
      { role: "user", content: "이 논문은?" },
      { role: "assistant", content: "척도 타당화 연구입니다." },
    ];
    const store = new Map<string, DeepReadMessage[]>([["KCI_2", earlier]]);
    const { chat, id, calls, push } = setup({ store });
    const sent = chat.send("대상은?");
    await flush();
    push('data: {"text": "노인"}\n\n');
    await flush();

    id.value = "KCI_2";
    await nextTick();
    expect(calls[0]!.init.signal!.aborted).toBe(true);
    expect(chat.messages.value).toEqual(earlier);
    expect(chat.isStreaming.value).toBe(false);
    expect(chat.streamingText.value).toBe("");
    await sent;
    // 끊긴 답도 user/assistant 짝을 지켜 남는다(다음 질문의 history 가 어긋나지 않게)
    expect(store.get("KCI_1")).toEqual([
      { role: "user", content: "대상은?" },
      { role: "assistant", content: `노인\n\n${CHAT_STOPPED_TEXT}` },
    ]);

    // 앞 논문으로 돌아오면 store 의 그 논문 대화가 이어진다
    id.value = "KCI_1";
    await nextTick();
    expect(chat.messages.value).toEqual(store.get("KCI_1"));
  });

  it("store 가 없으면 논문을 바꿀 때 대화를 비운다", async () => {
    const { chat, id, push, end } = setup();
    const sent = chat.send("질문");
    await flush();
    push("data: [DONE]\n\n");
    end();
    await sent;
    expect(chat.messages.value).toHaveLength(2);

    id.value = "KCI_9";
    await nextTick();
    expect(chat.messages.value).toEqual([]);
  });

  it("stop 은 fetch 의 signal 을 abort 하고 받은 글을 '멈췄습니다'와 남긴다 — 받은 글이 없으면 그 문구만", async () => {
    const { chat, calls, push } = setup();
    const first = chat.send("첫 질문");
    await flush();
    chat.stop();
    await first;
    expect(calls[0]!.init.signal!.aborted).toBe(true);
    expect(chat.messages.value.at(-1)).toEqual({ role: "assistant", content: CHAT_STOPPED_EMPTY });

    const second = chat.send("둘째 질문");
    await flush();
    push('data: {"text": "반쯤 받은 답"}\n\n');
    await flush();
    chat.stop();
    await second;
    expect(chat.messages.value.at(-1)).toEqual({ role: "assistant", content: `반쯤 받은 답\n\n${CHAT_STOPPED_TEXT}` });
    expect(chat.isStreaming.value).toBe(false);
    // 멈춘 뒤에 부른 stop 은 아무것도 하지 않는다
    chat.stop();
    expect(chat.messages.value).toHaveLength(4);
  });

  it("scope 가 끝나면(패널을 닫아 BookChat 이 내려가면) 스트림을 끊는다", async () => {
    const store = new Map<string, DeepReadMessage[]>();
    const { chat, scope, calls, push } = setup({ store });
    const sent = chat.send("질문");
    await flush();
    push('data: {"text": "받던 글"}\n\n');
    await flush();

    scope.stop();
    await sent;
    expect(calls[0]!.init.signal!.aborted).toBe(true);
    expect(store.get("KCI_1")).toEqual([
      { role: "user", content: "질문" },
      { role: "assistant", content: `받던 글\n\n${CHAT_STOPPED_TEXT}` },
    ]);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/deepReadSse.test.ts tests/unit/useDeepReadChat.test.ts`
Expected: `Test Files  2 failed (2)` / `Tests  no tests` — `Error: Cannot find module '~/utils/deepReadSse' imported from '…/tests/unit/deepReadSse.test.ts'`·`Error: Cannot find module '~/composables/useDeepReadChat' imported from '…/tests/unit/useDeepReadChat.test.ts'`

- [ ] **Step 3: SSE 파서와 대화 모양을 만든다**

Create `frontend/utils/deepReadSse.ts`:

```ts
// frontend/utils/deepReadSse.ts
// 딥리드(논문·책 1편과의 대화 — POST /api/books/chat/{cnts_id})의 SSE 조각 읽기와 대화 모양. 서버(services/chat/book_chat.py)는
// `data: {"text": …}` 를 흘리고, 답에서 인용한 대목이 있으면 `data: {"sources": […]}` 하나, 끝에 `data: [DONE]` 을 보낸다.
// 대화는 서버에 저장하지 않는다 — 요청마다 앞 대화를 history 로 싣는다(spec §12-4 D24)

// 출처 대목의 쪽은 저장된 값 그대로다(0부터 센다 — 서버가 LLM 문맥에도 같은 값 [p.X–Y] 를 싣는다, book_chat.py:155)
export interface DeepReadSource {
  page_start: number;
  page_end: number;
  text: string;
}

// pinnedChip 은 화면이 쥐는 값 — 펼친 출처 칩의 번호(BookChat 의 대목 미리보기)
export interface DeepReadMessage {
  role: "user" | "assistant";
  content: string;
  sources?: DeepReadSource[];
  pinnedChip?: number;
}

export type DeepReadEvent = { type: "text"; text: string } | { type: "sources"; sources: DeepReadSource[] } | { type: "done" };

export const CHAT_ERROR_TEXT = "오류가 발생했습니다. 다시 시도해주세요.";
// 닫기·논문 바꾸기로 끊은 답의 꼬리 — 끊긴 답도 대화에 남겨 다음 질문의 history 가 user/assistant 짝을 잃지 않게 한다(06e 정함 21)
export const CHAT_STOPPED_TEXT = "(답을 받다가 멈췄습니다)";
export const CHAT_STOPPED_EMPTY = "(답을 받기 전에 멈췄습니다)";

const DATA = "data: ";

// 받은 조각(chunk)을 앞 조각의 남은 줄(buffer)에 이어 줄 단위로 읽는다. 마지막 줄은 아직 덜 왔을 수 있어 buffer 로 남긴다.
// data: 줄만 읽고, 깨진 JSON·모르는 모양은 버린다. [DONE] 을 만나면 그 뒤 줄은 읽지 않는다(BookChat 의 옛 읽기와 같다)
export function parseSse(buffer: string, chunk: string): { buffer: string; events: DeepReadEvent[] } {
  const lines = (buffer + chunk).split("\n");
  const rest = lines.pop() ?? "";
  const events: DeepReadEvent[] = [];
  for (const line of lines) {
    if (!line.startsWith(DATA)) continue;
    const payload = line.slice(DATA.length).trim();
    if (payload === "[DONE]") {
      events.push({ type: "done" });
      return { buffer: "", events };
    }
    let evt: unknown;
    try {
      evt = JSON.parse(payload);
    } catch {
      continue;
    }
    if (!evt || typeof evt !== "object") continue;
    const { text, sources } = evt as { text?: unknown; sources?: unknown };
    if (typeof text === "string" && text) events.push({ type: "text", text });
    else if (Array.isArray(sources)) events.push({ type: "sources", sources: sources as DeepReadSource[] });
  }
  return { buffer: rest, events };
}
```

- [ ] **Step 4: 대화 흐름 composable 을 만든다**

Create `frontend/composables/useDeepReadChat.ts`:

```ts
// frontend/composables/useDeepReadChat.ts
import { onScopeDispose, type Ref, ref, watch } from "vue";
import {
  CHAT_ERROR_TEXT,
  CHAT_STOPPED_EMPTY,
  CHAT_STOPPED_TEXT,
  type DeepReadMessage,
  type DeepReadSource,
  parseSse,
} from "~/utils/deepReadSse";
import { apiHeaders, apiUrl } from "./useApi";

export interface DeepReadChatOptions {
  cntsId: () => string;
  // 논문별 대화를 쥐는 곳(연구 화면의 단계 패널 — 06e 정함 20). 있으면 논문을 오갈 때 대화를 이어 쓰고, 없으면 비운다
  store?: () => Map<string, DeepReadMessage[]> | undefined;
  fetchFn?: typeof fetch;
}

export interface DeepReadChat {
  messages: Ref<DeepReadMessage[]>;
  streamingText: Ref<string>;
  isStreaming: Ref<boolean>;
  send(text: string): Promise<void>;
  stop(): void;
}

interface Run {
  ctrl: AbortController;
  list: DeepReadMessage[];
}

// 딥리드 대화의 흐름(BookChat 에서 뺐다 — spec §12-4). 논문(cntsId)이 바뀌면 받던 답을 끊고 그 논문의 대화로 바꾸며,
// 닫히면(scope 끝) 끊는다. 끊은 답은 받은 글 + '멈췄습니다'로 그 논문의 대화에 남는다(06e 정함 21)
export function useDeepReadChat(opts: DeepReadChatOptions): DeepReadChat {
  // store 가 있으면 그 논문의 배열을 그대로 쥔다 — messages 에 쓰는 것이 곧 store 에 남는다
  function thread(id: string): DeepReadMessage[] {
    const store = opts.store?.();
    if (!store) return [];
    let list = store.get(id);
    if (!list) {
      list = [];
      store.set(id, list);
    }
    return list;
  }

  const messages = ref<DeepReadMessage[]>(thread(opts.cntsId()));
  const streamingText = ref("");
  const isStreaming = ref(false);
  // 지금 받는 답 — 끊긴 뒤 늦게 끝난 읽기가 다음 답의 상태를 건드리지 않게 이것과 견준다
  let current: Run | null = null;

  function stop(): void {
    const run = current;
    if (!run) return;
    current = null;
    run.ctrl.abort();
    const got = streamingText.value;
    run.list.push({ role: "assistant", content: got ? `${got}\n\n${CHAT_STOPPED_TEXT}` : CHAT_STOPPED_EMPTY });
    streamingText.value = "";
    isStreaming.value = false;
  }

  async function send(raw: string): Promise<void> {
    const text = raw.trim();
    if (!text || current) return;
    const list = messages.value;
    list.push({ role: "user", content: text });
    const history = list.slice(0, -1).map((m) => ({ role: m.role, content: m.content }));
    const run: Run = { ctrl: new AbortController(), list };
    current = run;
    isStreaming.value = true;
    streamingText.value = "";
    let sources: DeepReadSource[] | undefined;
    let failed = false;
    try {
      const fetchFn = opts.fetchFn ?? fetch;
      const resp = await fetchFn(apiUrl(`/books/chat/${opts.cntsId()}`), {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ message: text, history }),
        signal: run.ctrl.signal,
      });
      if (!resp.ok || !resp.body) throw new Error("응답 오류");
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      reading: while (current === run) {
        const { done, value } = await reader.read();
        if (done || current !== run) break;
        const parsed = parseSse(buffer, decoder.decode(value, { stream: true }));
        buffer = parsed.buffer;
        for (const evt of parsed.events) {
          if (evt.type === "done") break reading;
          if (evt.type === "text") streamingText.value += evt.text;
          else sources = evt.sources;
        }
      }
    } catch {
      failed = true;
    }
    // stop() 이 이미 끊고 남겼다(닫기·논문 바꾸기)
    if (current !== run) return;
    current = null;
    run.list.push(
      failed
        ? { role: "assistant", content: CHAT_ERROR_TEXT }
        : { role: "assistant", content: streamingText.value, ...(sources ? { sources } : {}) },
    );
    streamingText.value = "";
    isStreaming.value = false;
  }

  watch(opts.cntsId, (id) => {
    stop();
    messages.value = thread(id);
  });
  onScopeDispose(stop);

  return { messages, streamingText, isStreaming, send, stop };
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/deepReadSse.test.ts tests/unit/useDeepReadChat.test.ts`
Expected: `Test Files  2 passed (2)` / `Tests  10 passed (10)`

- [ ] **Step 6: BookChat 의 script 를 composable 로 바꾼다**

`frontend/components/BookChat.vue` — script 전부. 교체 전(`:73-180`):

```ts
<script setup lang="ts">
import { marked } from "marked";
import { apiHeaders, apiUrl } from "~/composables/useApi";

const props = defineProps<{
  cntsId: string;
  bookTitle?: string;
}>();
defineEmits<{ (e: "close"): void }>();

interface Source {
  page_start: number;
  page_end: number;
  text: string;
}
interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  pinnedChip?: number;
}

const messages = ref<Message[]>([]);
const inputText = ref("");
const isStreaming = ref(false);
const streamingText = ref("");
const messagesEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);

function formatText(text: string) {
  if (!text) return "";
  return marked.parse(text) as string;
}

function scrollBottom() {
  nextTick(() => {
    if (messagesEl.value)
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
  });
}

async function send() {
  const text = inputText.value.trim();
  if (!text || isStreaming.value) return;

  messages.value.push({ role: "user", content: text });
  inputText.value = "";
  isStreaming.value = true;
  streamingText.value = "";
  scrollBottom();

  const history = messages.value
    .slice(0, -1)
    .map((m) => ({ role: m.role, content: m.content }));

  let pendingSources: Source[] | undefined;

  try {
    const resp = await fetch(apiUrl(`/books/chat/${props.cntsId}`), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ message: text, history }),
    });

    if (!resp.ok || !resp.body) throw new Error("응답 오류");

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      const lines = buf.split("\n");
      buf = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") break;
        try {
          const evt = JSON.parse(payload);
          if (evt.text) {
            streamingText.value += evt.text;
            scrollBottom();
          } else if (evt.sources) {
            pendingSources = evt.sources;
          }
        } catch {}
      }
    }
  } catch {
    streamingText.value = "오류가 발생했습니다. 다시 시도해주세요.";
  }

  messages.value.push({
    role: "assistant",
    content: streamingText.value,
    sources: pendingSources,
  });
  streamingText.value = "";
  isStreaming.value = false;
  scrollBottom();
  nextTick(() => inputEl.value?.focus());
}
</script>
```

교체 후:

```ts
<script setup lang="ts">
import { marked } from "marked";
import { nextTick, ref, watch } from "vue";
import { useDeepReadChat } from "~/composables/useDeepReadChat";
import type { DeepReadMessage } from "~/utils/deepReadSse";

// 딥리드 대화 칸 — 논문 상세·논문 검색 결과 채팅·도서 상세·TopResult 와 연구 화면의 오른쪽 패널(06e)이 함께 쓴다.
// 대화 흐름(보내기·스트림 읽기·끊기·논문별 대화)은 useDeepReadChat 이 맡고 여기서는 그리기·입력·스크롤만 한다.
// store 를 넘기면(연구 화면 패널) 논문을 오갈 때 대화가 이어지고, 없으면 논문이 바뀔 때 비운다
const props = defineProps<{
  cntsId: string;
  bookTitle?: string;
  store?: Map<string, DeepReadMessage[]>;
}>();
defineEmits<{ (e: "close"): void }>();

const { messages, streamingText, isStreaming, send: sendChat } = useDeepReadChat({
  cntsId: () => props.cntsId,
  store: () => props.store,
});
const inputText = ref("");
const messagesEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);

function formatText(text: string) {
  if (!text) return "";
  return marked.parse(text) as string;
}

function scrollBottom() {
  nextTick(() => {
    if (messagesEl.value)
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
  });
}

// 질문·답이 쌓이거나 글이 흐르거나 다른 논문의 대화로 바뀌면 맨 아래로
watch([messages, () => messages.value.length, streamingText], scrollBottom);

async function send() {
  const text = inputText.value.trim();
  if (!text || isStreaming.value) return;
  inputText.value = "";
  const sentFor = props.cntsId;
  await sendChat(text);
  // 답을 다 받았을 때만 입력 칸으로 돌아간다 — 논문을 바꿔 끊긴 경우 초점은 사용자가 누른 곳에 둔다
  if (props.cntsId === sentFor) nextTick(() => inputEl.value?.focus());
}
</script>
```

템플릿(`:1-71`)은 그대로다 — `messages`·`isStreaming`·`streamingText`·`inputText`·`formatText`·`send`·`msg.pinnedChip` 이 같은 이름으로 남는다(`msg.pinnedChip` 을 고치는 것도 reactive 배열 안의 원소라 그대로 다시 그린다).

- [ ] **Step 7: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <R2 앞 + 2> passed` / `Tests <R2 앞 + 10> passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep "Duplicated imports" | grep -c -E "parseSse|DeepRead|CHAT_"`
Expected: `0`

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/utils/deepReadSse.ts && git add frontend/composables/useDeepReadChat.ts && git add frontend/tests/unit/deepReadSse.test.ts && git add frontend/tests/unit/useDeepReadChat.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 딥리드 대화 흐름을 순수 SSE 파서(utils/deepReadSse.parseSse)와 useDeepReadChat 으로 뺀다. 논문(cntsId)이 바뀌면 받던 답을 AbortController 로 끊고 그 논문의 대화로 바꾸며(store 가 있으면 이어 쓰고 없으면 비운다), scope 가 끝나면(패널을 닫으면) 끊는다. 끊은 답은 받은 글 + '(답을 받다가 멈췄습니다)'로 그 논문의 대화에 남겨 다음 질문의 history 가 user/assistant 짝을 잃지 않게 한다. 끊긴 뒤 늦게 끝난 읽기는 지금 답과 견주어 상태를 건드리지 않는다. SSE 읽기·오류 문구는 BookChat 의 지금 동작과 같다"
```

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/components/BookChat.vue && git status --short && git commit -m "[Refactor] round06e 프론트 — BookChat 의 대화 흐름을 useDeepReadChat 으로 옮기고 선택 prop store(논문별 대화)를 단다. 템플릿은 그대로다. 같은 BookChat 에 다른 논문을 넘기면 앞 논문 대화가 남아 다음 질문의 history 로 실리던 버그(논문 검색 결과 채팅 패널 — :key 없음)가 부르는 쪽을 고치지 않고 함께 낫는다. 자동 import 에 기대던 ref·nextTick 을 vue 에서 import 한다"
```

---

### Task R3: BookChat 문서 종류·출처 칩 버튼·논문 화면 두 호출처

spec §12-4 'BookChat 을 끼우기 전 고칠 것' 가운데 '문구가 책이다 — `docKind`'·'출처 칩 `<span @click>` → `<button>` + `open-pdf`'·'두 호출처 `doc-kind="paper"`(예외)'·'기존 네 화면 회귀'·배치의 '스트리밍 답 `aria-live`', 정함 22.

**알아 둘 것:**
- **문구(1-6 `chatCopy`):** 책은 지금 글 그대로(`:6` 인사·`:54` placeholder·`:55` 입력 이름), 논문은 `안녕하세요! 《제목》 논문에 대해 궁금한 것을 자유롭게 물어보세요!`(제목이 없으면 `이 논문에 대해`)·`논문에 대해서 자유롭게 질문해보세요!`·`논문에 대한 질문 입력`. 보내기 버튼 이름(`:63` `aria-label="검색"`)은 둘 다 `질문 보내기` 로 고친다 — 기존 네 화면에서 바뀌는 보이는(듣는) 글은 이 이름뿐이다. 문구는 `utils/deepRead.ts` 의 순수 함수라 vitest 로 고정한다.
- **출처 칩(정함 22):** `<span @click>` 을 `<button type="button" :aria-pressed>` 로 바꾸고 누르면 지금처럼 대목 미리보기를 펼치고 접는다(키보드로도 누를 수 있다). 칩 글자는 지금 그대로 **저장값**이다 — `sourceLabel` = `p.${page_start}` + 다르면 `–${page_end}`(`:26` 과 같은 식). 서버가 같은 날값으로 LLM 문맥 `[p.X–Y]` 를 만들어(`book_chat.py:155`) 답 글의 쪽 표기와 칩이 맞는다 — `citations.pageLabel`(+1)로 바꾸면 한 쪽씩 어긋나고 기존 네 화면이 바뀐다. 이름은 보이는 글자로 시작하고 숨김 꼬리 ` 대목 보기` 를 붙인다(코드베이스 관례 — `ReadingTable.vue:244-246`). `<button>` 의 글꼴은 `.skx-app button { font-family: inherit }`(`style_skovix.css:235-238`)와 tailwind preflight 가 상속시키고 크기·테두리·배경은 `.skx-chat-source-chip`(`:2690-2709`)이 정해 모양이 span 때와 같다 — 브라우저 확인 항목.
- **[원문 보기]:** 펼친 대목 아래에 두고 `pdfLinks` prop(기본 false)이 켜진 곳 — 연구 화면의 오른쪽 패널(Task R4 가 `:pdf-links="true"`) — 에서만 그린다. 누르면 `open-pdf` 로 `sourcePdfTarget(cntsId, bookTitle || cntsId, src)` = `citedPdfTarget(cntsId, title, [src])`(`utils/pdfViewer.ts:66-73` — 0부터 센 저장값을 뷰어 쪽 +1)를 낸다. 그래서 'p.5' 칩의 [원문 보기]는 원문 6쪽을 연다(뷰어 대목 이름은 `pageLabel` 의 'p.6' — 뷰어 쪽 번호와 같은 글). 쪽 정보가 0 이면 쪽 없이 연다. 기존 네 화면은 `pdfLinks` 를 넘기지 않아 동작이 그대로다. 버튼 여백은 패널 안에서만 그리므로 Task R4 의 CSS(`.wk-panel .skx-chat-source-open`)가 준다.
- **`aria-live`:** 스트리밍 칸(`:36-45`) 자체에 달면 글이 흐르는 동안 토막마다 읽힌다. 그래서 칸 밖에 숨김 live 영역(`.skx-sr-only` — `style_skovix.css:239-248`)을 두고 **방금 보낸 질문의 답을 다 받았을 때만** 그 답(마크다운을 그린 HTML)을 싣는다. 논문을 바꿔 다른 대화를 펼칠 때는 싣지 않아 옛 답을 다시 읽지 않는다(파트 메모).
- **두 호출처 `doc-kind="paper"`(§12-5 예외 — 이 한 속성만):** `pages/papers/index.vue:564-569`(06d 파일 — 06d 는 이 줄을 건드리지 않는다)·`pages/papers/[id].vue:433-437`. 도서 상세(`pages/books/[cnts_id].vue:434`)·`TopResult.vue:198` 은 책이라 그대로다.
- **props 기본값:** `withDefaults(defineProps<…>(), { docKind: "book", pdfLinks: false })`. emits 는 `close`(지금 선언만 있고 쓰지 않는다 — 부르는 쪽 `@close` 를 지키려 그대로 둔다)와 `open-pdf`.
- **회귀 확인 항목(브라우저 — 마무리 운영 확인에 넘긴다):** 논문 상세(`/papers/<id>` 오른쪽 DeepRead)·논문 검색 결과 채팅 패널(다른 논문의 DeepRead 를 누르면 대화가 비고 새 인사가 '논문' 문구)·도서 상세(인사·placeholder 가 '책' 문구 그대로)·`TopResult` DeepRead — `TopResult` 를 쓰는 곳은 보존 화면 `/search-classic` 하나뿐이다(`pages/search-classic.vue:204` 맨 위 결과·`:265` '추천 도서 살펴보기'로 고른 책 — 일반 도서 검색 화면에는 없다). `/search-classic` 에서 검색 → 맨 위 결과의 [DeepRead]: '책' 문구 그대로, 질문·답·출처 칩 미리보기. [대화 닫기] 뒤 다시 [DeepRead] 를 눌러도 같은 책이면 대화가 남는다(`TopResult.vue:197-202` 는 `v-show` 로 BookChat 마운트를 지킨다 — 그대로). 다른 검색어로 맨 위 결과가 바뀌거나 살펴보기에서 다른 책을 고르면 대화가 비는 것은 R2 의 의도된 변화다(지금은 옛 책의 대화가 새 책 화면에 남는다 — `store` 를 넘기지 않으므로 이제 `cntsId` 감시가 비운다). 넷 모두 질문·흐르는 답·출처 칩 미리보기 펼침·접기가 지금처럼 되고, [원문 보기]는 보이지 않는다.

**Files:**
- Create: `frontend/utils/deepRead.ts`
- Modify: `frontend/components/BookChat.vue` (템플릿 `:5-7`·`:16-32`·`:46` 뒤·`:54-55`·`:63`, script 의 import·props·emits·`send`·새 함수 둘 — R2 뒤 기준)
- Modify: `frontend/pages/papers/index.vue` (`:564-569` 에 한 속성)
- Modify: `frontend/pages/papers/[id].vue` (`:433-437` 에 한 속성)
- Test: Create `frontend/tests/unit/deepRead.test.ts`

기준선(R2 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 파일을 +1, 테스트를 +4 한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

Create `frontend/tests/unit/deepRead.test.ts`:

```ts
// frontend/tests/unit/deepRead.test.ts
import { describe, expect, it } from "vitest";
import { chatCopy, sourceLabel, sourcePdfTarget } from "~/utils/deepRead";

describe("chatCopy·sourceLabel·sourcePdfTarget", () => {
  it("책은 지금 문구 그대로, 논문은 '논문' 문구 — 보내기 버튼 이름은 둘 다 '질문 보내기'", () => {
    const book = chatCopy("book");
    expect(book.greeting("어린 왕자")).toBe("안녕하세요! 《어린 왕자》에 대해 궁금한 것을 자유롭게 물어보세요!");
    expect(book.greeting()).toBe("안녕하세요! 이 자료에 대해 궁금한 것을 자유롭게 물어보세요!");
    expect(book.placeholder).toBe("책에 대해서 자유롭게 질문해보세요!");
    expect(book.inputLabel).toBe("책에 대한 질문 입력");
    expect(book.sendLabel).toBe("질문 보내기");

    const paper = chatCopy("paper");
    expect(paper.greeting("노인의 우울과 사회적 지지")).toBe(
      "안녕하세요! 《노인의 우울과 사회적 지지》 논문에 대해 궁금한 것을 자유롭게 물어보세요!",
    );
    expect(paper.greeting()).toBe("안녕하세요! 이 논문에 대해 궁금한 것을 자유롭게 물어보세요!");
    expect(paper.placeholder).toBe("논문에 대해서 자유롭게 질문해보세요!");
    expect(paper.inputLabel).toBe("논문에 대한 질문 입력");
    expect(paper.sendLabel).toBe("질문 보내기");
  });

  it("출처 칩 글자는 저장값 그대로 — 서버가 답 글에 쓴 쪽 표기와 같다(BookChat 의 지금 표기)", () => {
    expect(sourceLabel({ page_start: 5, page_end: 5, text: "" })).toBe("p.5");
    expect(sourceLabel({ page_start: 5, page_end: 7, text: "" })).toBe("p.5–7");
  });

  it("p.5 칩은 원문 6쪽을 연다 — 저장값은 0부터 세어 뷰어 쪽은 하나 크다", () => {
    expect(sourcePdfTarget("KCI_1", "제목", { page_start: 5, page_end: 7, text: "대목" })).toEqual({
      cntsId: "KCI_1",
      title: "제목",
      page: 6,
      passages: [{ page: 6, label: "p.6–8" }],
    });
  });

  it("쪽 정보가 없으면(0) 쪽 없이 연다", () => {
    expect(sourcePdfTarget("KCI_1", "제목", { page_start: 0, page_end: 0, text: "대목" })).toEqual({
      cntsId: "KCI_1",
      title: "제목",
      page: undefined,
      passages: [{ page: null, label: "쪽 정보 없음" }],
    });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/deepRead.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  no tests` — `Error: Cannot find module '~/utils/deepRead' imported from '…/tests/unit/deepRead.test.ts'`

- [ ] **Step 3: 문구·출처 함수를 만든다**

Create `frontend/utils/deepRead.ts`:

```ts
// frontend/utils/deepRead.ts
// 딥리드(BookChat)의 문서 종류별 문구·출처 칩 표기·원문 열기 입력. 연구 화면의 오른쪽 패널(06e)과 기존 네 화면이 함께 쓴다
import type { OpenPdfPayload } from "~/types/research";
import type { DeepReadSource } from "~/utils/deepReadSse";
import { citedPdfTarget } from "~/utils/pdfViewer";

// 책(도서 상세·TopResult)인지 논문(논문 상세·논문 검색·연구 화면 패널)인지 — 기본은 책(지금 문구)
export type DocKind = "book" | "paper";

export interface ChatCopy {
  greeting(title?: string): string;
  placeholder: string;
  inputLabel: string;
  sendLabel: string;
}

const COPY: Record<DocKind, ChatCopy> = {
  book: {
    greeting: (title) => `안녕하세요! ${title ? `《${title}》에 대해` : "이 자료에 대해"} 궁금한 것을 자유롭게 물어보세요!`,
    placeholder: "책에 대해서 자유롭게 질문해보세요!",
    inputLabel: "책에 대한 질문 입력",
    sendLabel: "질문 보내기",
  },
  paper: {
    greeting: (title) => `안녕하세요! ${title ? `《${title}》 논문에 대해` : "이 논문에 대해"} 궁금한 것을 자유롭게 물어보세요!`,
    placeholder: "논문에 대해서 자유롭게 질문해보세요!",
    inputLabel: "논문에 대한 질문 입력",
    sendLabel: "질문 보내기",
  },
};

export function chatCopy(kind: DocKind): ChatCopy {
  return COPY[kind];
}

// 출처 칩 글자 — 저장값 그대로(0부터 센 쪽). 서버가 같은 값으로 LLM 문맥 [p.X–Y] 를 만들어 답 글에도 그 숫자가 나온다
// (book_chat.py:155). citations.pageLabel(+1)로 바꾸면 칩이 답 글과 한 쪽씩 어긋난다(06e 정함 22)
export function sourceLabel(src: DeepReadSource): string {
  return `p.${src.page_start}${src.page_end !== src.page_start ? `–${src.page_end}` : ""}`;
}

// 출처 대목으로 원문을 연다 — 0부터 센 저장값을 뷰어 쪽(+1)으로(pdfViewer.citedPdfTarget). 쪽 정보가 0 이면 쪽 없이 연다
export function sourcePdfTarget(cntsId: string, title: string, src: DeepReadSource): OpenPdfPayload {
  return citedPdfTarget(cntsId, title, [src]);
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/deepRead.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  4 passed (4)`

- [ ] **Step 5: BookChat — 문구·출처 칩 버튼·[원문 보기]·끝난 답 live**

`frontend/components/BookChat.vue` 템플릿 — 빈 상태 인사(`:5-7`). 교체 전:

```html
      <div v-if="messages.length === 0 && !isStreaming" class="skx-chat-msg skx-chat-msg--ai">
        안녕하세요! <template v-if="bookTitle">《{{ bookTitle }}》에 대해</template><template v-else>이 자료에 대해</template> 궁금한 것을 자유롭게 물어보세요!
      </div>
```

교체 후:

```html
      <div v-if="messages.length === 0 && !isStreaming" class="skx-chat-msg skx-chat-msg--ai">
        {{ copy.greeting(bookTitle) }}
      </div>
```

출처 칩(`:16-32`). 교체 전:

```html
        <!-- 출처 칩 -->
        <div v-if="msg.sources?.length" class="skx-chat-sources">
          <div class="skx-chat-source-chips">
            <span
              v-for="(src, si) in msg.sources"
              :key="si"
              class="skx-chat-source-chip"
              :class="{ 'is-active': msg.pinnedChip === si }"
              @click="msg.pinnedChip = msg.pinnedChip === si ? undefined : si"
            >
              p.{{ src.page_start }}{{ src.page_end !== src.page_start ? `–${src.page_end}` : '' }}
            </span>
          </div>
          <div v-if="msg.pinnedChip !== undefined" class="skx-chat-source-preview">
            {{ msg.sources[msg.pinnedChip]?.text }}
          </div>
        </div>
```

교체 후:

```html
        <!-- 출처 칩 — 누르면 그 대목을 아래에 펼치고 다시 누르면 접는다(키보드로도 누른다). 원문 열기는 펼친 대목 아래
             [원문 보기]이고 pdfLinks 인 곳(연구 화면 오른쪽 패널)에만 둔다 — 기존 네 화면은 지금처럼 미리보기만 -->
        <div v-if="msg.sources?.length" class="skx-chat-sources">
          <div class="skx-chat-source-chips">
            <button
              v-for="(src, si) in msg.sources"
              :key="si"
              type="button"
              class="skx-chat-source-chip"
              :class="{ 'is-active': msg.pinnedChip === si }"
              :aria-pressed="msg.pinnedChip === si"
              @click="msg.pinnedChip = msg.pinnedChip === si ? undefined : si"
            >
              {{ sourceLabel(src) }}<span class="skx-sr-only"> 대목 보기</span>
            </button>
          </div>
          <div v-if="msg.pinnedChip !== undefined" class="skx-chat-source-preview">
            {{ msg.sources[msg.pinnedChip]?.text }}
          </div>
          <button
            v-if="pdfLinks && pinnedSource(msg)"
            type="button"
            class="rs-btn rs-btn--small rs-btn--ghost skx-chat-source-open"
            @click="openSource(msg)"
          >
            원문 보기
          </button>
        </div>
```

메시지 칸 끝(`:43-46` — 스트리밍 칸 뒤, 입력 칸 앞)에 숨김 live 영역. 교체 전:

```html
          <span class="skx-chat-typing__dot"></span>
        </div>
      </template>
    </div>
```

교체 후:

```html
          <span class="skx-chat-typing__dot"></span>
        </div>
      </template>
    </div>
    <!-- 화면낭독기용 — 방금 보낸 질문의 답을 다 받으면 한 번 읽는다. 흐르는 글은 토막마다 읽히지 않게 싣지 않는다 -->
    <div class="skx-sr-only" aria-live="polite" v-html="liveHtml" />
```

입력 칸(`:54-55`). 교체 전:

```html
        placeholder="책에 대해서 자유롭게 질문해보세요!"
        aria-label="책에 대한 질문 입력"
```

교체 후:

```html
        :placeholder="copy.placeholder"
        :aria-label="copy.inputLabel"
```

보내기 버튼(`:63`). 교체 전:

```html
        aria-label="검색"
```

교체 후:

```html
        :aria-label="copy.sendLabel"
```

script — import(Task R2 뒤 기준). 교체 전:

```ts
import { marked } from "marked";
import { nextTick, ref, watch } from "vue";
import { useDeepReadChat } from "~/composables/useDeepReadChat";
import type { DeepReadMessage } from "~/utils/deepReadSse";
```

교체 후:

```ts
import { marked } from "marked";
import { computed, nextTick, ref, watch } from "vue";
import { useDeepReadChat } from "~/composables/useDeepReadChat";
import type { OpenPdfPayload } from "~/types/research";
import { type DocKind, chatCopy, sourceLabel, sourcePdfTarget } from "~/utils/deepRead";
import type { DeepReadMessage, DeepReadSource } from "~/utils/deepReadSse";
```

script — props·emits. 교체 전:

```ts
// store 를 넘기면(연구 화면 패널) 논문을 오갈 때 대화가 이어지고, 없으면 논문이 바뀔 때 비운다
const props = defineProps<{
  cntsId: string;
  bookTitle?: string;
  store?: Map<string, DeepReadMessage[]>;
}>();
defineEmits<{ (e: "close"): void }>();
```

교체 후:

```ts
// store 를 넘기면(연구 화면 패널) 논문을 오갈 때 대화가 이어지고, 없으면 논문이 바뀔 때 비운다.
// docKind 는 문구(책/논문), pdfLinks 는 출처 대목의 [원문 보기](open-pdf 로 부르는 쪽의 원문 뷰어를 연다)
const props = withDefaults(
  defineProps<{
    cntsId: string;
    bookTitle?: string;
    store?: Map<string, DeepReadMessage[]>;
    docKind?: DocKind;
    pdfLinks?: boolean;
  }>(),
  { docKind: "book", pdfLinks: false },
);
const emit = defineEmits<{ close: []; "open-pdf": [payload: OpenPdfPayload] }>();

const copy = computed(() => chatCopy(props.docKind));
```

script — 입력 칸 ref 뒤. 교체 전:

```ts
const inputText = ref("");
const messagesEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);
```

교체 후:

```ts
const inputText = ref("");
const messagesEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLTextAreaElement | null>(null);
// 화면낭독기가 읽을 끝난 답(HTML) — 방금 보낸 질문의 답만 싣는다(논문을 바꿔 다른 대화를 펼칠 때 옛 답을 다시 읽지 않게)
const liveHtml = ref("");
```

script — `send` 와 새 함수 둘. 교체 전:

```ts
async function send() {
  const text = inputText.value.trim();
  if (!text || isStreaming.value) return;
  inputText.value = "";
  const sentFor = props.cntsId;
  await sendChat(text);
  // 답을 다 받았을 때만 입력 칸으로 돌아간다 — 논문을 바꿔 끊긴 경우 초점은 사용자가 누른 곳에 둔다
  if (props.cntsId === sentFor) nextTick(() => inputEl.value?.focus());
}
```

교체 후:

```ts
async function send() {
  const text = inputText.value.trim();
  if (!text || isStreaming.value) return;
  inputText.value = "";
  liveHtml.value = "";
  const sentFor = props.cntsId;
  await sendChat(text);
  // 답을 다 받았을 때만 읽고 입력 칸으로 돌아간다 — 논문을 바꿔 끊긴 경우 초점은 사용자가 누른 곳에 둔다
  if (props.cntsId !== sentFor) return;
  const last = messages.value.at(-1);
  if (last?.role === "assistant") liveHtml.value = formatText(last.content);
  nextTick(() => inputEl.value?.focus());
}

// 펼친 출처 대목 — 없으면 null
function pinnedSource(msg: DeepReadMessage): DeepReadSource | null {
  return msg.pinnedChip === undefined ? null : (msg.sources?.[msg.pinnedChip] ?? null);
}

function openSource(msg: DeepReadMessage): void {
  const src = pinnedSource(msg);
  if (src) emit("open-pdf", sourcePdfTarget(props.cntsId, props.bookTitle || props.cntsId, src));
}
```

- [ ] **Step 6: 논문 화면 두 호출처에 문서 종류를 단다**

`frontend/pages/papers/index.vue` — 교체 전(`:564-569`):

```html
        <BookChat
          v-if="chatPaperId"
          :cnts-id="chatPaperId"
          :book-title="chatPaperTitle"
          @close="chatPaperId = null"
        />
```

교체 후:

```html
        <BookChat
          v-if="chatPaperId"
          :cnts-id="chatPaperId"
          :book-title="chatPaperTitle"
          doc-kind="paper"
          @close="chatPaperId = null"
        />
```

`frontend/pages/papers/[id].vue` — 교체 전(`:433-437`):

```html
        <BookChat
          :cnts-id="paperId"
          :book-title="paper?.title"
          @close="chatOpen = false"
        />
```

교체 후:

```html
        <BookChat
          :cnts-id="paperId"
          :book-title="paper?.title"
          doc-kind="paper"
          @close="chatOpen = false"
        />
```

- [ ] **Step 7: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <R3 앞 + 1> passed` / `Tests <R3 앞 + 4> passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep "Duplicated imports" | grep -c -E "chatCopy|sourceLabel|sourcePdfTarget|DocKind|ChatCopy"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff -U0 -- frontend/pages/papers/index.vue "frontend/pages/papers/[id].vue" | grep "^[+-] "`
Expected: 두 줄뿐 — `+          doc-kind="paper"` 가 파일마다 하나(§12-5 예외 — 다른 줄은 바뀌지 않았다)

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/utils/deepRead.ts && git add frontend/tests/unit/deepRead.test.ts && git add frontend/components/BookChat.vue && git add frontend/pages/papers/index.vue && git add "frontend/pages/papers/[id].vue" && git status --short && git commit -m "[Feat] round06e 프론트 — BookChat 에 문서 종류(docKind, 기본 book)를 두어 논문 화면은 '논문' 문구로 인사·질문 칸을 그리고, 출처 칩을 키보드로 누를 수 있는 버튼(aria-pressed — 누르면 지금처럼 대목 미리보기)으로 바꾼다. 칩 글자는 서버가 답 글에 쓴 쪽과 같은 저장값 그대로다. pdfLinks 가 켜진 곳(연구 화면 오른쪽 패널)에서만 펼친 대목 아래 [원문 보기]를 그려 open-pdf 로 원문 뷰어를 연다(0부터 센 쪽을 뷰어 쪽으로 — 'p.5' 칩은 원문 6쪽). 방금 보낸 질문의 답을 다 받으면 숨김 live 영역이 한 번 읽는다(흐르는 글은 토막마다 읽지 않는다). 보내기 버튼 이름은 '검색'에서 '질문 보내기'로. 논문 상세·논문 검색 결과의 두 호출처에 doc-kind=\"paper\" 한 속성만 더한다 — 도서 상세·TopResult 는 그대로다"
```

---

### Task R4: 오른쪽 딥리드 패널 부품

spec §12-4 '패널(공용 부품 — 탭 `[인용 근거 | 딥리드]`)'·'머리는 행 데이터만으로(제목·저자·연도·학술지) + [논문 상세 ↗] + 닫기'·'딥리드 탭 본문은 BookChat 대화'·'배치'(단계 본문 안 2단 그리드 sticky `--wk-panel-w: 22rem`·1200px 미만 오버레이 서랍 `.skx-chat-side` 재사용·768px 이하 전체 폭)·접근성(초점 가두기·Esc·스트리밍 답 aria-live 는 R3). 단계 ③ 은 Task R5, 단계 ④ 는 Task S4 가 이 부품을 쥔다.

**알아 둘 것:**
- **무엇을 열지는 단계 화면이 쥔다(1-7 계약):** `paper`(`PanelPaper | null` — null 이면 닫힘)·`tab`·`tabs`·`detailHref`·`store`(논문별 대화). 이 부품은 그리기와 키보드만 맡고 `close`·`update:tab`(`v-model:tab`)·`open-pdf`·`detail` 을 낸다. 닫은 뒤 누른 자리(행 제목·인용 칩)로 초점을 돌리는 것도 누른 요소를 아는 여는 쪽(R5·S4)이 한다.
- **루트는 조각(배경 + `<aside>`)이고 `paper` 가 있을 때만 그린다.** 패널을 닫으면 BookChat 이 내려가 `useDeepReadChat` 의 `onScopeDispose` 가 받던 답을 끊고 그 논문의 대화에 남긴다(R2). 열린 채 논문만 바뀌면 BookChat 은 그대로이고 `cntsId` 가 바뀐다 — `:key` 로 다시 만들지 않는다(대화 바꾸기는 R2 의 `watch(cntsId)`).
- **딥리드는 탭을 옮겨도 내리지 않는다(`v-show`)** — 단계 ④ 에서 인용 근거 탭으로 옮겨도 받던 답이 끊기지 않는다. 인용 근거 탭 본문은 슬롯 `sources`(S4 의 `CitationSource`), 머리 아래 슬롯 `extra`(R5 의 [담음]·들어온 경로).
- **머리(`panelHead`):** 제목(없으면 cnts_id)과 `저자 · 연도 · 학술지` 가운데 있는 것 — 저자는 `splitAuthors` 로 나눠 쉼표로 잇는다(H1 의 `chipTooltip` 과 같은 구분). [논문 상세 ↗]는 `detailHref` 가 있을 때만, 누르면 `detail` 로 MouseEvent 를 넘긴다(돌아올 자리를 남기는 이동은 여는 쪽 — R5 의 `onDetail`).
- **배치 경계는 한 값:** `PANEL_SIDE_MIN_PX = 1200`·`PANEL_FULL_MAX_PX = 768`(`utils/deepRead.ts`)과 `work.css` 의 `@media (max-width: 1199px)`·`(max-width: 768px)` 가 같은 경계다. 1rem = 20px 라 `--wk-panel-w: 22rem` 은 440px — 1440px·LNB 펼침이면 표가 빠듯해 패널이 열리면 LNB 를 접는다(연결은 R5 의 emit·R6).
- **`.skx-chat-side` 재사용(전역 CSS 는 고치지 않는다 — 1-8):** 루트에 `.skx-chat-side`(`style_skovix.css:4823-4877` — 흰 바탕·세로 flex·`overflow: hidden`, 768px 이하 오른쪽 고정)를 함께 달고 `work.css` 의 `.wk-panel.skx-chat-side`(클래스 둘 — 전역 규칙보다 늘 앞선다)로만 덮는다. 전역의 768px 이하 `max-width: 400px` 는 전체 폭을 위해 `max-width: none` 으로 덮는다. 서랍은 `z-index: 200`(전역 모바일 `.skx-chat-side` 와 같은 값), 배경 199 — 원문 뷰어(`PdfViewer` `.pdf-overlay` 1000)·온보딩(`.wk-modal` 1000)이 그 위에 뜬다. 서랍 그림자와 배경은 새 색값 없이 `--skx-ink`(#333333) 토큰을 섞어 쓴다 — `color-mix(in srgb, var(--skx-ink) 15%, transparent)`·`… 25% …`(같은 파일 `.wk-modal` 배경 `work.css:250` 의 `color-mix(in srgb, var(--skx-ink) 45%, transparent)` 꼴, 1-8 '`--skx-*` 토큰만'·Task Z2 의 '더한 줄의 색값 0'). 전역 모바일 `.skx-chat-side` 의 `rgba(0, 0, 0, 0.15)` 그림자(`style_skovix.css:4875`)와 보기는 거의 같다.
- **BookChat 여백:** `.skx-chat-messages`(위 여백 3rem)·`.skx-chat-input-wrap`(위 2rem)·`.skx-chat-msg`(최대 13rem)는 논문 상세 옆 칸에 맞춘 값이라 `.wk-panel` 안에서만 줄인다.
- **Esc 는 패널에서 듣는다(문서가 아니라):** 초점이 패널 안에 있을 때 어느 배치에서나 닫는다. 원문 뷰어는 body 로 옮겨 그려지고 `#__nuxt` 를 `inert` 로 만들어(`PdfViewer.vue` `lockPage`) 뷰어가 열린 동안 패널은 키를 받지 않는다 — 뷰어의 Esc 와 겹치지 않는다.
- **초점 가두기:** 서랍·전체 폭(`panelMode(window.innerWidth) !== "side"`)에서만 Tab·Shift+Tab 을 처음·끝에서 돌린다(숨긴 탭 본문 — `offsetParent === null` — 은 뺀다). 2단(side)은 화면을 덮지 않아 가두지 않는다. 열릴 때(닫힘 → 열림) 제목(`h2 tabindex="-1"`)으로 초점을 옮긴다 — 열린 채 다른 논문으로 바꿀 때는 옮기지 않는다(표에서 다음 제목을 이어 누를 수 있게).
- **탭:** 탭이 둘 이상일 때만 `role="tablist"`·`role="tab"`·`aria-selected`·`aria-controls`, 고른 탭만 `tabindex="0"`(나머지 -1)과 좌우 방향키(WAI-ARIA 탭 관례). 단계 ③ 은 딥리드 하나라 탭 줄 없이 본문만 그린다.
- `.vue` 는 단위 테스트하지 않는다 — 배치·머리·탭 판단은 `utils/deepRead.ts` 순수 함수로 vitest, 부품은 typecheck·build 와 브라우저 확인(R5 뒤 — 패널이 화면에 붙는 Task).

**Files:**
- Modify: `frontend/utils/deepRead.ts` (머리 주석·import 두 줄, `sourcePdfTarget` 뒤에 패널 함수 — R3 뒤 기준)
- Create: `frontend/components/work/DeepReadPanel.vue`
- Modify: `frontend/assets/css/work.css` (표시 줄 위에 `.wk-split`·`.wk-panel` 묶음)
- Test: `frontend/tests/unit/deepRead.test.ts` (import, 새 describe)

기준선(R3 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 를 +3 한다(`deepRead.test.ts` 4 → 7).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/deepRead.test.ts` — import. 교체 전:

```ts
import { chatCopy, sourceLabel, sourcePdfTarget } from "~/utils/deepRead";
```

교체 후:

```ts
import type { PaperMeta } from "~/types/work";
import {
  PANEL_FULL_MAX_PX,
  PANEL_SIDE_MIN_PX,
  chatCopy,
  panelHead,
  panelMode,
  panelTabs,
  sourceLabel,
  sourcePdfTarget,
} from "~/utils/deepRead";
```

같은 파일 끝 — 첫 describe 의 마지막 it 와 describe 끝 뒤에 새 describe. 교체 전:

```ts
  it("쪽 정보가 없으면(0) 쪽 없이 연다", () => {
    expect(sourcePdfTarget("KCI_1", "제목", { page_start: 0, page_end: 0, text: "대목" })).toEqual({
      cntsId: "KCI_1",
      title: "제목",
      page: undefined,
      passages: [{ page: null, label: "쪽 정보 없음" }],
    });
  });
});
```

교체 후:

```ts
  it("쪽 정보가 없으면(0) 쪽 없이 연다", () => {
    expect(sourcePdfTarget("KCI_1", "제목", { page_start: 0, page_end: 0, text: "대목" })).toEqual({
      cntsId: "KCI_1",
      title: "제목",
      page: undefined,
      passages: [{ page: null, label: "쪽 정보 없음" }],
    });
  });
});

describe("panelMode·panelHead·panelTabs", () => {
  it("1200px 이상은 본문 옆 2단, 769~1199px 는 오른쪽 서랍, 768px 이하는 전체 폭", () => {
    expect([PANEL_SIDE_MIN_PX, PANEL_FULL_MAX_PX]).toEqual([1200, 768]);
    expect(panelMode(1440)).toBe("side");
    expect(panelMode(1200)).toBe("side");
    expect(panelMode(1199)).toBe("drawer");
    expect(panelMode(769)).toBe("drawer");
    expect(panelMode(768)).toBe("full");
    expect(panelMode(375)).toBe("full");
  });

  it("머리는 행의 서지만으로 — 저자·연도·학술지 가운데 있는 것만 잇고, 제목이 없으면 cnts_id", () => {
    const meta: PaperMeta = {
      title: " 노인의 우울과 사회적 지지 ",
      personal_author: "김철수; 이영희",
      pub_date: "2015-03",
      series_title: "노인복지연구",
    };
    expect(panelHead({ cntsId: "KCI_A", meta })).toEqual({
      title: "노인의 우울과 사회적 지지",
      byline: "김철수, 이영희 · 2015 · 노인복지연구",
    });
    expect(panelHead({ cntsId: "KCI_B", meta: { ...meta, personal_author: null, series_title: " " } })).toEqual({
      title: "노인의 우울과 사회적 지지",
      byline: "2015",
    });
    expect(
      panelHead({ cntsId: "KCI_C", meta: { title: "", personal_author: null, pub_date: null, series_title: null } }),
    ).toEqual({ title: "KCI_C", byline: "" });
  });

  it("참고문헌 선택하기는 딥리드 탭만, 보고서는 인용 근거·딥리드 두 탭", () => {
    expect(panelTabs("reading")).toEqual(["chat"]);
    expect(panelTabs("proposal")).toEqual(["sources", "chat"]);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/deepRead.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  3 failed | 4 passed (7)`. 실패 셋:
- `panelMode·panelHead·panelTabs > 1200px 이상은 본문 옆 2단, …` — `AssertionError: expected [ undefined, undefined ] to deeply equal [ 1200, 768 ]`
- `panelMode·panelHead·panelTabs > 머리는 행의 서지만으로 — …` — `TypeError: (0 , panelHead) is not a function`
- `panelMode·panelHead·panelTabs > 참고문헌 선택하기는 딥리드 탭만, …` — `TypeError: (0 , panelTabs) is not a function`

- [ ] **Step 3: 패널 판단 함수를 더한다**

`frontend/utils/deepRead.ts` — 머리 주석과 import(Task R3 이 만든 파일). 교체 전:

```ts
// frontend/utils/deepRead.ts
// 딥리드(BookChat)의 문서 종류별 문구·출처 칩 표기·원문 열기 입력. 연구 화면의 오른쪽 패널(06e)과 기존 네 화면이 함께 쓴다
import type { OpenPdfPayload } from "~/types/research";
import type { DeepReadSource } from "~/utils/deepReadSse";
import { citedPdfTarget } from "~/utils/pdfViewer";
```

교체 후:

```ts
// frontend/utils/deepRead.ts
// 딥리드(BookChat)의 문서 종류별 문구·출처 칩 표기·원문 열기 입력, 단계 화면 오른쪽 패널(DeepReadPanel)의 배치·머리·탭.
// 연구 화면의 오른쪽 패널(06e)과 기존 네 화면이 함께 쓴다
import type { OpenPdfPayload } from "~/types/research";
import type { PaperMeta } from "~/types/work";
import { pubYear, splitAuthors } from "~/utils/citations";
import type { DeepReadSource } from "~/utils/deepReadSse";
import { citedPdfTarget } from "~/utils/pdfViewer";
```

같은 파일 끝. 교체 전:

```ts
export function sourcePdfTarget(cntsId: string, title: string, src: DeepReadSource): OpenPdfPayload {
  return citedPdfTarget(cntsId, title, [src]);
}
```

교체 후:

```ts
export function sourcePdfTarget(cntsId: string, title: string, src: DeepReadSource): OpenPdfPayload {
  return citedPdfTarget(cntsId, title, [src]);
}

// ── 단계 화면 오른쪽 패널(spec §12-4 D24) ─────────────────────────
// 탭 — 인용 근거(보고서 인용 칩이 연다)·딥리드(BookChat)
export type PanelTab = "sources" | "chat";

// 배치 경계(px) — 이 폭 이상은 단계 본문 옆 2단(sticky), 그 미만은 오른쪽 서랍, PANEL_FULL_MAX_PX 이하는 전체 폭 서랍.
// work.css 의 @media (max-width: 1199px)·(max-width: 768px) 와 같은 값이다
export const PANEL_SIDE_MIN_PX = 1200;
export const PANEL_FULL_MAX_PX = 768;

export type PanelMode = "side" | "drawer" | "full";

// 서랍·전체 폭이면 패널이 화면을 덮어 Tab 초점을 패널 안에 가둔다(DeepReadPanel)
export function panelMode(width: number): PanelMode {
  if (width >= PANEL_SIDE_MIN_PX) return "side";
  return width > PANEL_FULL_MAX_PX ? "drawer" : "full";
}

// 패널이 여는 논문 — 머리는 행 데이터(서지)만으로 그린다
export interface PanelPaper {
  cntsId: string;
  meta: PaperMeta;
}

// 머리 — 제목(없으면 cnts_id)과 '저자 · 연도 · 학술지' 가운데 있는 것. 저자는 splitAuthors 로 나눠 쉼표로 잇는다
export function panelHead(p: PanelPaper): { title: string; byline: string } {
  const byline = [splitAuthors(p.meta.personal_author).join(", "), pubYear(p.meta.pub_date), p.meta.series_title]
    .map((s) => (s ?? "").trim())
    .filter(Boolean)
    .join(" · ");
  return { title: p.meta.title?.trim() || p.cntsId, byline };
}

// 단계마다 쓰는 탭 — 참고문헌 선택하기는 누른 문장이 없어 딥리드만, 보고서는 인용 근거·딥리드
export function panelTabs(step: "reading" | "proposal"): PanelTab[] {
  return step === "reading" ? ["chat"] : ["sources", "chat"];
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/deepRead.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  7 passed (7)`

- [ ] **Step 5: 패널 부품을 만든다**

Create `frontend/components/work/DeepReadPanel.vue`:

```vue
<!-- frontend/components/work/DeepReadPanel.vue -->
<template>
  <template v-if="paper">
    <!-- 1200px 미만(서랍·전체 폭)에서만 보이는 배경 — 누르면 닫는다. 넓은 화면에서는 CSS 가 숨긴다 -->
    <div class="wk-panel-backdrop" aria-hidden="true" @click="emit('close')" />
    <aside
      :id="panelId"
      ref="root"
      class="wk-panel skx-chat-side"
      role="complementary"
      :aria-labelledby="`${panelId}-title`"
      @keydown="onKeydown"
    >
      <header class="wk-panel__head">
        <div class="wk-panel__heading">
          <!-- tabindex="-1" — 패널이 열리면 이 제목으로 초점을 옮긴다 -->
          <h2 :id="`${panelId}-title`" ref="titleEl" class="wk-panel__title" tabindex="-1">{{ head.title }}</h2>
          <p v-if="head.byline" class="wk-panel__byline">{{ head.byline }}</p>
        </div>
        <a v-if="detailHref" :href="detailHref" class="wk-panel__detail" @click="emit('detail', $event)">논문 상세 ↗</a>
        <button type="button" class="rs-icon-btn wk-panel__close" aria-label="패널 닫기" title="닫기 (Esc)" @click="emit('close')">
          ✕
        </button>
      </header>
      <div v-if="$slots.extra" class="wk-panel__extra">
        <slot name="extra" />
      </div>
      <div v-if="tabs.length > 1" class="wk-panel__tabs" role="tablist" aria-label="패널 보기">
        <button
          v-for="t in tabs"
          :id="tabId(t)"
          :key="t"
          type="button"
          role="tab"
          class="wk-panel__tab"
          :aria-selected="tab === t"
          :aria-controls="bodyId"
          :tabindex="tab === t ? 0 : -1"
          @click="emit('update:tab', t)"
          @keydown="onTabKey($event, t)"
        >
          {{ TAB_LABEL[t] }}
        </button>
      </div>
      <div
        :id="bodyId"
        class="wk-panel__body"
        :role="tabs.length > 1 ? 'tabpanel' : undefined"
        :aria-labelledby="tabs.length > 1 ? tabId(tab) : undefined"
      >
        <!-- 딥리드는 탭을 옮겨도 내리지 않는다(v-show) — 받던 답이 끊기지 않게. 패널을 닫으면 내려가며 끊는다 -->
        <div v-show="tab === 'chat'" class="wk-panel__chat">
          <BookChat
            :cnts-id="paper.cntsId"
            :book-title="paper.meta.title?.trim() || undefined"
            doc-kind="paper"
            :store="store"
            :pdf-links="true"
            @open-pdf="(payload) => emit('open-pdf', payload)"
          />
        </div>
        <div v-if="tab === 'sources'" class="wk-panel__sources">
          <slot name="sources" />
        </div>
      </div>
    </aside>
  </template>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import BookChat from "~/components/BookChat.vue";
import type { OpenPdfPayload } from "~/types/research";
import { type PanelPaper, type PanelTab, panelHead, panelMode } from "~/utils/deepRead";
import type { DeepReadMessage } from "~/utils/deepReadSse";

// 단계 화면 오른쪽 패널(spec §12-4 D24) — 머리(논문 제목·서지·[논문 상세 ↗]·닫기)와 탭 [인용 근거 | 딥리드].
// 무엇을 열지(paper — null 이면 닫힘)·어느 탭인지(tab)·논문별 대화(store)는 단계 화면이 쥐고, 이 부품은 그리기와 키보드만 맡는다.
// 닫은 뒤 누른 자리(행 제목·인용 칩)로 초점을 돌리는 것도 누른 요소를 아는 여는 쪽이 한다
const props = defineProps<{
  panelId: string;
  paper: PanelPaper | null;
  tabs: readonly PanelTab[];
  tab: PanelTab;
  detailHref: string | null;
  store: Map<string, DeepReadMessage[]>;
}>();
const emit = defineEmits<{
  close: [];
  "update:tab": [tab: PanelTab];
  "open-pdf": [payload: OpenPdfPayload];
  detail: [e: MouseEvent];
}>();

const TAB_LABEL: Record<PanelTab, string> = { sources: "인용 근거", chat: "딥리드" };
const FOCUSABLE =
  "button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), summary, [tabindex]:not([tabindex='-1'])";

const root = ref<HTMLElement | null>(null);
const titleEl = ref<HTMLElement | null>(null);
const head = computed(() => (props.paper ? panelHead(props.paper) : { title: "", byline: "" }));
const bodyId = computed(() => `${props.panelId}-body`);

function tabId(t: PanelTab): string {
  return `${props.panelId}-tab-${t}`;
}

// 닫혀 있다가 열릴 때만 제목으로 초점을 옮긴다(화면낭독기가 무엇이 열렸는지 읽는다). 열린 채 다른 논문으로 바꿀 때는
// 옮기지 않는다 — 표에서 다음 제목을 이어 누를 수 있게
watch(
  () => props.paper !== null,
  async (open) => {
    if (!open) return;
    await nextTick();
    titleEl.value?.focus({ preventScroll: true });
  },
);

// Esc 는 어느 배치에서나 닫는다 — 초점이 패널 안에 있을 때만(문서가 아니라 패널에서 들어 원문 뷰어 등 위에 뜬 창의 Esc 와
// 겹치지 않는다). 서랍·전체 폭(1200px 미만)은 화면을 덮으므로 Tab 이 패널 밖으로 나가지 않게 처음·끝에서 돌린다
function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape") {
    emit("close");
    return;
  }
  if (e.key !== "Tab" || !root.value || panelMode(window.innerWidth) === "side") return;
  // 숨긴 탭 본문(v-show)의 요소는 뺀다
  const items = [...root.value.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
  const first = items[0];
  const last = items[items.length - 1];
  if (!first || !last) return;
  const active = document.activeElement;
  if (e.shiftKey && (active === first || active === titleEl.value)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && active === last) {
    e.preventDefault();
    first.focus();
  }
}

// 탭 목록의 방향키(WAI-ARIA 탭 관례) — 옆 탭을 고르고 그 탭에 초점
async function onTabKey(e: KeyboardEvent, t: PanelTab): Promise<void> {
  if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
  e.preventDefault();
  const n = props.tabs.length;
  const next = props.tabs[(props.tabs.indexOf(t) + (e.key === "ArrowRight" ? 1 : n - 1)) % n];
  if (!next) return;
  emit("update:tab", next);
  await nextTick();
  document.getElementById(tabId(next))?.focus();
}
</script>
```

- [ ] **Step 6: 2단·서랍 CSS 를 더한다**

`frontend/assets/css/work.css` — 맨 끝 표시 줄(A5·X3·X4 의 묶음은 이미 그 위에 있다). 교체 전:

```css
/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

교체 후:

```css
/* ── 오른쪽 딥리드 패널(DeepReadPanel — 06e R4, spec §12-4 D24). 1200px 이상은 단계 본문 옆 2단(sticky, 폭 --wk-panel-w),
   그 미만은 오른쪽 서랍, 768px 이하는 전체 폭. 루트에 style_skovix.css 의 .skx-chat-side(논문 상세 옆 칸)를 함께 달아
   흰 바탕·세로 칸 모양을 물려받고, 여기서는 .wk-panel.skx-chat-side 로만 덮는다(전역 CSS 는 고치지 않는다) ── */
.wk-split {
  --wk-panel-w: 22rem;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1.2rem;
  align-items: start;
  min-width: 0;
}
.wk-split.is-panel-open {
  grid-template-columns: minmax(0, 1fr) var(--wk-panel-w);
}
.wk-split__main {
  min-width: 0;
}
.wk-panel.skx-chat-side {
  position: sticky;
  top: 1.2rem;
  width: auto;
  max-width: none;
  height: calc(100vh - 2.4rem);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-lnb);
}
.wk-panel__head {
  display: flex;
  flex-shrink: 0;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.8rem 0.9rem;
  border-bottom: 1px solid var(--skx-border-c1);
}
.wk-panel__heading {
  flex: 1;
  min-width: 0;
}
.wk-panel__title {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--skx-ink);
  overflow-wrap: anywhere;
}
.wk-panel__title:focus {
  outline: none;
}
.wk-panel__title:focus-visible {
  outline: 2px solid var(--skx-border-c2);
  outline-offset: 2px;
}
.wk-panel__byline {
  margin: 0.15rem 0 0;
  font-size: 0.6rem;
  color: var(--skx-gray-1);
  overflow-wrap: anywhere;
}
.wk-panel__detail,
.wk-panel__detail:visited {
  flex-shrink: 0;
  font-size: 0.6rem;
  font-weight: 700;
  line-height: 1.9;
  color: var(--skx-primary);
  white-space: nowrap;
}
.wk-panel__detail:hover,
.wk-panel__detail:focus-visible {
  text-decoration: underline;
}
.wk-panel__close {
  flex-shrink: 0;
}
.wk-panel__extra {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  gap: 0.5rem;
  max-height: 40%;
  padding: 0.6rem 0.9rem;
  overflow-y: auto;
  border-bottom: 1px solid var(--skx-border-c1);
}
.wk-panel__tabs {
  display: flex;
  flex-shrink: 0;
  gap: 0.3rem;
  padding: 0.4rem 0.9rem 0;
  border-bottom: 1px solid var(--skx-border-c1);
}
.wk-panel__tab {
  padding: 0.35rem 0.6rem;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--skx-gray-1);
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
}
.wk-panel__tab[aria-selected="true"] {
  color: var(--skx-primary);
  border-bottom-color: var(--skx-primary);
}
.wk-panel__tab:focus-visible {
  outline: 2px solid var(--skx-border-c2);
  outline-offset: -2px;
}
.wk-panel__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.wk-panel__chat {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 0 0.9rem 0.9rem;
}
.wk-panel__sources {
  flex: 1;
  min-height: 0;
  padding: 0.8rem 0.9rem;
  overflow-y: auto;
}
/* BookChat 은 논문 상세 옆 칸(머리가 겹쳐 뜨는 모양)에 맞춘 여백이라 패널 안에서는 줄인다. 말풍선은 패널 폭을 따른다 */
.wk-panel .skx-chat-messages {
  margin-top: 0;
  padding-top: 0.8rem;
}
.wk-panel .skx-chat-msg {
  max-width: 90%;
}
.wk-panel .skx-chat-input-wrap {
  margin-top: 0.8rem;
}
.wk-panel .skx-chat-source-open {
  margin-top: 0.3rem;
}
.wk-panel-backdrop {
  display: none;
}
@media (max-width: 1199px) {
  .wk-split.is-panel-open {
    grid-template-columns: minmax(0, 1fr);
  }
  .wk-panel.skx-chat-side {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    z-index: 200;
    width: min(var(--wk-panel-w), 100%);
    height: auto;
    border-width: 0 0 0 1px;
    border-radius: 0;
    box-shadow: -4px 0 20px color-mix(in srgb, var(--skx-ink) 15%, transparent);
  }
  .wk-panel-backdrop {
    position: fixed;
    inset: 0;
    z-index: 199;
    display: block;
    background: color-mix(in srgb, var(--skx-ink) 25%, transparent);
  }
}
@media (max-width: 768px) {
  .wk-panel.skx-chat-side {
    width: 100%;
    border-left-width: 0;
  }
}
@media (max-width: 1199px) and (prefers-reduced-motion: no-preference) {
  .wk-panel.skx-chat-side {
    animation: wk-panel-in 0.2s ease-out;
  }
}
@keyframes wk-panel-in {
  from {
    transform: translateX(1.5rem);
    opacity: 0;
  }
  to {
    transform: none;
    opacity: 1;
  }
}

/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

- [ ] **Step 7: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <R4 앞과 같은 수> passed` / `Tests <R4 앞 + 3> passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep "Duplicated imports" | grep -c -E "panelMode|panelHead|panelTabs|PanelTab|PanelPaper|PanelMode|PANEL_"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff --stat -- frontend/assets/css/style_skovix.css`
Expected: 빈 출력(`.skx-chat-side` 는 재사용만 — 전역 CSS 는 그대로)

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/utils/deepRead.ts && git add frontend/tests/unit/deepRead.test.ts && git add frontend/components/work/DeepReadPanel.vue && git add frontend/assets/css/work.css && git status --short && git commit -m "[Feat] round06e 프론트 — 단계 화면 오른쪽 딥리드 패널 부품(DeepReadPanel)을 만든다. 머리는 행의 서지만으로 제목과 '저자 · 연도 · 학술지'를 그리고 [논문 상세 ↗]·닫기를 둔다. 탭 [인용 근거 | 딥리드]는 단계마다 고르고(참고문헌 선택하기는 딥리드만), 딥리드는 탭을 옮겨도 내리지 않아 받던 답이 끊기지 않는다. 무엇을 열지·탭·논문별 대화는 단계 화면이 쥐고 부품은 그리기와 키보드만 맡는다 — 열릴 때 제목으로 초점, 패널 안 Esc 로 닫기, 1200px 미만 서랍·768px 이하 전체 폭에서는 Tab 을 패널 안에 가둔다. 배치는 단계 본문 안 2단 그리드(sticky, --wk-panel-w 22rem)이고 서랍은 style_skovix.css 의 .skx-chat-side 모양을 루트에 함께 달아 물려받은 뒤 work.css 에서만 덮는다(전역 CSS 는 그대로, 서랍 그림자·배경은 --skx-ink 를 color-mix 로 섞어 새 색값을 쓰지 않는다)"
```

---

### Task R5: 참고문헌 선택하기 — 제목을 누르면 오른쪽 딥리드

spec §12-4 '논문을 누르면 오른쪽 딥리드'(제목을 `<button aria-expanded aria-controls>` 로·그 행 강조·상세 이동은 작은 [논문 상세 ↗] — `detailHref`·`goDetail` 그대로)·'단계 ③ 은 딥리드 탭만·[담음] 토글·들어온 경로 첫 대목(접어 둠)·패널을 ReadingStep 이 쥐어 [담음]이 `useReadingSaves` 사슬을 탄다'·'예시 연구는 [담음] 끔·대화는 염', §12-5 '패널 열림 emit 과 `[id].vue:73` 리스너', 정함 20·30.

**알아 둘 것:**
- **표(`ReadingTable.vue`):** 제목 `<a>`(`:31-37`)를 `<button class="wk-reading__title wk-reading__open" :aria-expanded :aria-controls>` 로 바꾸고 누르면 `open(cnts, 누른 버튼)` 을 낸다. 상세로 떠나는 링크는 서지 줄(`.wk-reading__meta`) 끝의 작은 `논문 상세 ↗` 로 옮긴다 — `:href`·`@click`·`@auxclick`·`@contextmenu` 와 `detailHref`·`goDetail`(`:259-274`)이 그대로라 돌아오는 자리 복원·새 탭·오른쪽 클릭 메뉴가 지금처럼 된다(`goDetail` 의 `link.closest("li")` 도 같은 행). `aria-controls` 는 그 행이 열려 있을 때만 단다(닫힌 패널의 id 를 가리키지 않게 — 같은 파일 [경로] 버튼 `:90-91` 과 같은 관례). 열린 행은 `wk-reading__row--active` 로 강조한다.
- **패널은 ReadingStep 이 쥔다:** 상태 `panel`(`{ cntsId, opener }` — opener 는 누른 제목 버튼, DOM 요소라 `shallowRef`), 논문별 대화 `chatStore = new Map<string, DeepReadMessage[]>()`(정함 20 — 단계를 옮기거나 새로고침하면 비운다). 같은 제목을 다시 누르면 닫는다(`aria-expanded` 와 같은 뜻). 패널의 논문은 **지금 표의 행**(`reading.items`)에서 읽는다 — [담음]을 누른 뒤 다시 읽은 상태가 패널에도 그대로 보인다.
- **[담음] 토글(단계 ③ 만):** `aria-pressed` 가 담음이고(눌림 = 꽉 찬 `rs-btn`, 안 눌림 = `rs-btn--ghost`), 누르면 `update(cnts, { state: in ? "candidate" : "in" })` — 표의 체크 상자와 같은 저장 사슬(`useReadingSaves`)이다. 예시 연구·뺀 논문(`out`)·목차를 만드는 중(`busy`)이면 꺼 두고 까닭을 한 줄 적는다(표의 체크 상자 `:22` 와 같은 조건). 대화는 예시 연구에서도 연다 — `/books/chat` 은 연구 쓰기 API 가 아니다.
- **들어온 경로 첫 대목:** `firstPathChunk(item)`(새 순수 함수 — `pathLines` 와 같은 순서의 첫 매칭 대목, 라벨 `하위질문 n · 대목 p.x`)을 `<details>` 로 접어 두고, 펼치면 대목 글과 [원문 보기](`pathPdfTarget` — 표의 [경로] 와 같은 입력). 매칭 대목이 없으면(되살림·직접 담음만) 그리지 않는다.
- **패널 머리의 [논문 상세 ↗]:** `readingDetailUrl(cnts)` = `detailUrl(cnts, { kind: "research", job, e: null, s: "reading" }, { at: readingAnchor(cnts), y: null })` — 표의 상세 링크와 같은 출처이고, 행 높이 대신 앵커만 싣는다(패널에서 누를 때는 행이 화면 어디에 있는지 재지 않는다 — 돌아오면 그 행으로 간다). 그냥 누르면 `leave(url, { at, y: null })`, 새 탭·가운데 버튼은 브라우저에 맡긴다(`isPlainClick`).
- **닫기:** 패널의 ✕·Esc·배경을 누르면 `closePanel` — 다음 그림 뒤 누른 제목 버튼으로 초점을 돌린다. 그 사이 표를 다시 그려 요소가 바뀌었으면 같은 행(`[data-anchor="r-<cnts>"]`)의 제목 버튼을 찾는다.
- **패널 열림 emit(정함 30):** `panel: [open: boolean]` — 열리고 닫힐 때(`panelPaper` 가 있는지) 내고, 단계를 옮겨 이 화면이 내려갈 때 `onBeforeUnmount` 에서 false 를 낸다(그래서 연구 화면은 `watch(step)` 가 필요 없다). `[id].vue` 는 `:73` 에 `@panel="workPanelOpen = $event"`, script `:514`(`const { pdf, closePdf } = pdfOpener;`) 바로 뒤에 `const workPanelOpen = ref(false);`(+ 주석 한 줄)만 단다 — §12-5 의 `:57-75` 밖이지만 리스너가 쓸 변수라 06e 가 넣는 유일한 script 줄이다. `AppSidebar :collapsed` 와 루트 `is-lnb-collapsed`(`:3-7`)는 늦게 머지하는 줄이 단다(Task R6 또는 06d 계획의 조건부 LNB 접기 연결). `ref` 는 이미 import 돼 있다(`:208`).
- **ReadingStep 템플릿은 통째로 갈음한다** — 루트를 `.wk-split` 으로 감싸면 안쪽이 모두 한 단 들어간다. 아래 '교체 전'은 A5·R1 뒤의 기대 모습이다. A5 가 두 버튼(`{{ REMAKE_REPORT }}`·`{{ MAKE_REPORT }}`)의 글을 다른 꼴로 두었으면 '교체 후'의 같은 두 자리도 A5 의 꼴을 그대로 옮긴다(그 밖은 R1 이 쓴 글이다). 머리 안내에 '제목을 누르면 오른쪽에서 그 논문과 대화할 수 있습니다.' 한 문장을 더한다.
- **CSS:** `.wk-reading__title` 은 `<a>` 에 쓰던 글자 모양 그대로 버튼에 함께 단다. `.wk-reading__open` 은 버튼 기본 모양(테두리·배경·안쪽 여백·가운데 정렬)만 지운다 — `font: inherit` 를 쓰지 않는다(같은 요소의 `.wk-reading__title` 크기·굵기를 뒤에 오는 규칙이 덮는다, 글꼴 이름은 `.skx-app button` 이 이미 상속시킨다). `a:visited`(전역 `style_skovix.css` — 특이성 0,1,1)가 링크 색을 덮지 않게 `.wk-reading__detail:visited` 를 함께 적는다.
- `.vue` 는 단위 테스트하지 않는다 — 첫 대목 고르기는 `utils/readingList.firstPathChunk` 로 vitest, 화면은 typecheck·build 와 브라우저 확인 항목(마무리 운영 확인에 넘긴다): 1440px 에서 제목을 누르면 표 옆에 22rem 패널이 서고(LNB 접기는 R6 뒤) 행이 강조된다 · 같은 제목을 다시 누르면 닫히고 초점이 그 제목으로 돌아온다 · 다른 제목을 누르면 패널의 논문·대화가 바뀌고 앞 논문으로 돌아오면 대화가 이어진다 · [담음]이 표의 체크와 함께 바뀐다 · 1100px 에서 오른쪽 서랍(배경을 누르면 닫힘·Tab 이 패널 안에서 돈다) · 1199px 이하(서랍·전체 폭)에서 제목에 초점이 있을 때 입력 칸을 클릭하면 초점이 입력 칸에 머물고(제목으로 되돌아가지 않는다), Tab·Shift+Tab 으로 상세 링크·닫기·출처 칩·입력 칸·보내기 단추를 모두 지나 처음·끝에서 돈다 · 같은 폭에서 출처 칩을 펼친 뒤 Tab 으로 펼친 대목(넘치는 스크롤 영역)·[원문 보기]·뒤 메시지·입력 칸까지 가고, 출처 칩 없는 답이 쌓여 넘친 대화 칸에서도 Tab 으로 입력 칸에 닿는다(처음으로 감기지 않는다) · 질문을 보내 입력 칸·보내기 단추가 잠기면 초점이 제목으로 돌아와 Esc 로 닫힌다·375px 에서 전체 폭 · 대화 출처 칩의 [원문 보기]·들어온 경로 [원문 보기]가 원문 뷰어를 연다 · 예시 연구는 [담음]이 꺼지고 대화는 된다.

**Files:**
- Modify: `frontend/utils/readingList.ts` (`pathPdfTarget` :136 위에 `firstPathChunk`)
- Modify: `frontend/components/work/ReadingTable.vue` (행 class :8-13, 제목·서지 :29-41, props·emits :138-141, `togglePath` 뒤 `openRow`)
- Modify: `frontend/components/work/ReadingStep.vue` (`<template>` 전부, script 의 import·emits·`update` 뒤 패널 — A5·R1 뒤 기준)
- Modify: `frontend/pages/research/[id].vue` (:73, :514 뒤 두 줄)
- Modify: `frontend/assets/css/work.css` (표시 줄 위에 R5 묶음)
- Test: `frontend/tests/unit/readingList.test.ts` (import, describe `pathPdfTarget` 앞에 새 describe)

기준선(R4 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 를 +3 한다(`readingList.test.ts` 19 → 22).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/readingList.test.ts` — import 목록. 교체 전:

```ts
  fieldValue,
```

교체 후:

```ts
  fieldValue,
  firstPathChunk,
```

같은 파일 — describe `pathPdfTarget` 바로 앞에 새 describe(`CHUNK`·`subq`·`row` 는 파일 머리의 픽스처). 교체 전:

```ts
describe("pathPdfTarget", () => {
```

교체 후:

```ts
describe("firstPathChunk — 패널의 첫 대목", () => {
  it("[경로] 와 같은 순서의 첫 매칭 대목 — 대목이 없는 하위질문은 건너뛴다", () => {
    const second: PathChunk = { ...CHUNK, chunk_id: "KCI_A#9", page_start: 9, page_end: 10 };
    const item = row({
      path: { subqs: [subq({ chunks: [CHUNK, second] }), subq({ idx: 1, chunks: [second] })], revived: null, user: false },
    });
    expect(firstPathChunk(item)).toEqual({ label: "하위질문 1 · 대목 p.4", chunk: CHUNK });
    const later = row({ path: { subqs: [subq(), subq({ idx: 1, chunks: [second] })], revived: null, user: false } });
    expect(firstPathChunk(later)).toEqual({ label: "하위질문 2 · 대목 p.10–11", chunk: second });
  });

  it("매칭 대목이 하나도 없으면 null — 쪽을 모르는 대목은 '쪽 정보 없음'으로 적는다", () => {
    expect(firstPathChunk(row({ path: { subqs: [subq()], revived: null, user: false } }))).toBeNull();
    const bare: PathChunk = { chunk_id: "KCI_A#0", page_start: null, page_end: null, score: null, text: "초록" };
    expect(firstPathChunk(row({ path: { subqs: [subq({ chunks: [bare] })], revived: null, user: false } }))).toEqual({
      label: "하위질문 1 · 대목 쪽 정보 없음",
      chunk: bare,
    });
  });

  it("되살림·직접 담음만 있는 논문은 null", () => {
    const revived = row({
      origin: "revived",
      path: { subqs: [], revived: { subq_idx: 1, subquestion: "사회적 지지 측정 도구", round: 2, note: "" }, user: false },
    });
    expect(firstPathChunk(revived)).toBeNull();
    expect(firstPathChunk(row({ origin: "user", path: { subqs: [], revived: null, user: true } }))).toBeNull();
  });
});

describe("pathPdfTarget", () => {
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/readingList.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  3 failed | 19 passed (22)` — 실패 셋 모두 `TypeError: (0 , firstPathChunk) is not a function`(`firstPathChunk — 패널의 첫 대목 > [경로] 와 같은 순서의 첫 매칭 대목 …`·`> 매칭 대목이 하나도 없으면 null …`·`> 되살림·직접 담음만 있는 논문은 null`)

- [ ] **Step 3: 첫 대목을 고른다**

`frontend/utils/readingList.ts` — `pathPdfTarget` 머리 주석(`:136`) 앞. 교체 전:

```ts
// 경로의 대목 하나로 원문을 연다 — 그 대목의 쪽에서(쪽 정보가 없으면 첫 쪽)
```

교체 후:

```ts
// 오른쪽 딥리드 패널의 '들어온 경로' 첫 대목(spec §12-4 D24 — 접어 둔다). [경로](pathLines)와 같은 순서의 첫 매칭 대목이고,
// 매칭 대목이 없으면(되살림·직접 담음만이거나 대목이 저장되지 않음) null
export function firstPathChunk(item: ReadingItem): { label: string; chunk: PathChunk } | null {
  for (const sq of item.path.subqs) {
    const chunk = sq.chunks[0];
    if (chunk) return { label: `하위질문 ${sq.idx + 1} · 대목 ${pageLabel(chunkPages(chunk))}`, chunk };
  }
  return null;
}

// 경로의 대목 하나로 원문을 연다 — 그 대목의 쪽에서(쪽 정보가 없으면 첫 쪽)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/readingList.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  22 passed (22)`

- [ ] **Step 5: 표 — 제목은 패널을 여는 버튼, 상세는 작은 링크**

`frontend/components/work/ReadingTable.vue` — 행 class(`:8-13`). 교체 전:

```html
        'wk-reading__row--fresh': fresh.has(item.cnts_id),
      }"
```

교체 후:

```html
        'wk-reading__row--fresh': fresh.has(item.cnts_id),
        'wk-reading__row--active': activeId === item.cnts_id,
      }"
```

제목·서지(`:29-41`). 교체 전:

```html
      <div class="wk-reading__main">
        <!-- 누르는 순간의 행 높이를 주소에 실어야 해서 NuxtLink 대신 직접 옮긴다(CitationChip 과 같다) -->
        <a
          :href="detailHref(item.cnts_id, null)"
          class="wk-reading__title"
          @click="goDetail($event, item.cnts_id)"
          @auxclick="goDetail($event, item.cnts_id)"
          @contextmenu="goDetail($event, item.cnts_id)"
        >{{ rowTitle(item) }}</a>
        <p class="wk-reading__meta">
          <span>{{ paperByline(item.meta) }}</span>
          <span class="rs-badge">{{ originLabel(item.origin) }}</span>
        </p>
```

교체 후:

```html
      <div class="wk-reading__main">
        <!-- 제목을 누르면 화면을 떠나지 않고 오른쪽 패널에 이 논문의 딥리드가 열린다(spec §12-4 D24) -->
        <button
          type="button"
          class="wk-reading__title wk-reading__open"
          :aria-expanded="activeId === item.cnts_id"
          :aria-controls="activeId === item.cnts_id ? panelId : undefined"
          @click="openRow(item.cnts_id, $event)"
        >{{ rowTitle(item) }}</button>
        <p class="wk-reading__meta">
          <span>{{ paperByline(item.meta) }}</span>
          <span class="rs-badge">{{ originLabel(item.origin) }}</span>
          <!-- 상세로 떠나는 링크. 누르는 순간의 행 높이를 주소에 실어야 해서 NuxtLink 대신 직접 옮긴다(CitationChip 과 같다) -->
          <a
            :href="detailHref(item.cnts_id, null)"
            class="wk-reading__detail"
            @click="goDetail($event, item.cnts_id)"
            @auxclick="goDetail($event, item.cnts_id)"
            @contextmenu="goDetail($event, item.cnts_id)"
          >논문 상세 ↗<span class="rs-sr-only"> {{ rowName(item) }}</span></a>
        </p>
```

script — props·emits(`:139-141`). 교체 전:

```ts
// reordering 은 ReadingStep 에 순서 저장이 남아 있는 동안(그 묶음을 다시 읽기까지) 참이다
const props = defineProps<{ items: ReadingItem[]; readOnly: boolean; busy: boolean; reordering: boolean; jobId: string }>();
const emit = defineEmits<{ update: [cnts: string, body: ReadingPut]; "open-pdf": [payload: OpenPdfPayload] }>();
```

교체 후:

```ts
// reordering 은 ReadingStep 에 순서 저장이 남아 있는 동안(그 묶음을 다시 읽기까지) 참이다.
// 제목은 오른쪽 딥리드 패널을 여는 버튼이다(open 으로 emit — 패널은 ReadingStep 이 쥔다). activeId 는 패널에 열린 논문,
// panelId 는 그 패널의 id(aria-controls)
const props = defineProps<{
  items: ReadingItem[];
  readOnly: boolean;
  busy: boolean;
  reordering: boolean;
  jobId: string;
  activeId?: string | null;
  panelId?: string;
}>();
const emit = defineEmits<{
  update: [cnts: string, body: ReadingPut];
  "open-pdf": [payload: OpenPdfPayload];
  open: [cnts: string, el: HTMLElement];
}>();
```

script — `togglePath`(`:254-256`) 뒤. 교체 전:

```ts
function togglePath(cnts: string): void {
  openPath.value = openPath.value === cnts ? null : cnts;
}
```

교체 후:

```ts
function togglePath(cnts: string): void {
  openPath.value = openPath.value === cnts ? null : cnts;
}

// 누른 제목 버튼을 함께 넘긴다 — 패널을 닫으면 ReadingStep 이 그리로 초점을 돌린다
function openRow(cnts: string, e: MouseEvent): void {
  emit("open", cnts, e.currentTarget as HTMLElement);
}
```

- [ ] **Step 6: ReadingStep — 2단 그리드와 패널**

`frontend/components/work/ReadingStep.vue` — `<template>` 전부. 교체 전(A5·R1 뒤):

```html
<template>
  <section class="wk-screen" aria-labelledby="wk-reading-title">
    <header class="wk-screen__head">
      <!-- tabindex="-1" — 단계를 옮기면 연구 화면이 이 제목으로 초점을 옮긴다 -->
      <h2 id="wk-reading-title" class="wk-screen__title" tabindex="-1">참고문헌 선택하기</h2>
      <p class="rs-muted">
        「{{ question }}」 탐색의 채택 근거가 후보로 들어와 있습니다. 보고서에 쓸 논문을 담습니다.
      </p>
      <p v-if="topicTitle" class="wk-screen__picked">고른 주제 <strong>{{ topicTitle }}</strong></p>
      <p v-if="reading?.stale" class="rs-muted"><span class="rs-badge">다시 맞춤 필요</span> 목차를 만든 뒤 고른 주제가 바뀌었습니다 — 담은 논문을 다시 보고 [{{ REMAKE_REPORT }}]로 맞추세요.</p>
      <p v-if="readOnly" class="rs-muted">예시 연구는 읽기 전용입니다 — 미리 돌린 실제 기록을 그대로 보여 줍니다.</p>
    </header>

    <CorpusScopeNote :corpus="corpus" />
    <p v-if="error" class="rs-alert" role="alert">{{ error }}</p>

    <div v-if="!reading && loadError" class="rs-card rs-state">
      <p>{{ loadError }}</p>
      <button type="button" class="rs-btn" @click="reloadAll(['reading'])">다시 불러오기</button>
    </div>
    <div v-else-if="!reading" class="rs-card rs-card--wait">
      <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
      <p>참고문헌 후보를 불러오는 중입니다</p>
    </div>
    <template v-else>
      <FunnelCounter :funnel="reading.funnel" />
      <ReadingTable
        :items="reading.items"
        :read-only="readOnly"
        :busy="busy"
        :reordering="saves.reordering.value"
        :job-id="jobId"
        @update="update"
        @open-pdf="(payload) => emit('open-pdf', payload)"
      />
      <CandidateDrawer
        v-if="reading.excluded.length"
        :excluded="reading.excluded"
        :read-only="readOnly"
        :busy="busy"
        @revive="(cnts) => update(cnts, { state: 'candidate' })"
      />
      <div class="wk-screen__next">
        <p v-if="hint" class="rs-muted">{{ hint }}</p>
        <button v-if="reading.topic_id === null" type="button" class="rs-btn rs-btn--ghost" @click="emit('go', 'topics')">
          제목 고르기
        </button>
        <template v-else-if="outlineMade">
          <button type="button" class="rs-btn" @click="emit('go', 'proposal')">{{ FINAL_STEP_NAME }} 단계로</button>
          <button
            type="button"
            class="rs-btn rs-btn--ghost"
            :disabled="readOnly || busy || !canOutline"
            @click="makeOutline(true)"
          >
            {{ REMAKE_REPORT }}
          </button>
        </template>
        <button
          v-else
          type="button"
          class="rs-btn"
          :disabled="readOnly || busy || !canOutline"
          @click="makeOutline(false)"
        >
          {{ MAKE_REPORT }}
        </button>
      </div>
    </template>
  </section>
</template>
```

교체 후:

```html
<template>
  <!-- 제목을 누르면 오른쪽에 그 논문의 딥리드 패널이 열린다(spec §12-4 D24) — 넓은 화면은 본문 옆 2단, 좁으면 서랍 -->
  <div class="wk-split" :class="{ 'is-panel-open': panelPaper !== null }">
    <section class="wk-screen wk-split__main" aria-labelledby="wk-reading-title">
      <header class="wk-screen__head">
        <!-- tabindex="-1" — 단계를 옮기면 연구 화면이 이 제목으로 초점을 옮긴다 -->
        <h2 id="wk-reading-title" class="wk-screen__title" tabindex="-1">참고문헌 선택하기</h2>
        <p class="rs-muted">
          「{{ question }}」 탐색의 채택 근거가 후보로 들어와 있습니다. 보고서에 쓸 논문을 담습니다. 제목을 누르면 오른쪽에서
          그 논문과 대화할 수 있습니다.
        </p>
        <p v-if="topicTitle" class="wk-screen__picked">고른 주제 <strong>{{ topicTitle }}</strong></p>
        <p v-if="reading?.stale" class="rs-muted"><span class="rs-badge">다시 맞춤 필요</span> 목차를 만든 뒤 고른 주제가 바뀌었습니다 — 담은 논문을 다시 보고 [{{ REMAKE_REPORT }}]로 맞추세요.</p>
        <p v-if="readOnly" class="rs-muted">예시 연구는 읽기 전용입니다 — 미리 돌린 실제 기록을 그대로 보여 줍니다.</p>
      </header>

      <CorpusScopeNote :corpus="corpus" />
      <p v-if="error" class="rs-alert" role="alert">{{ error }}</p>

      <div v-if="!reading && loadError" class="rs-card rs-state">
        <p>{{ loadError }}</p>
        <button type="button" class="rs-btn" @click="reloadAll(['reading'])">다시 불러오기</button>
      </div>
      <div v-else-if="!reading" class="rs-card rs-card--wait">
        <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
        <p>참고문헌 후보를 불러오는 중입니다</p>
      </div>
      <template v-else>
        <FunnelCounter :funnel="reading.funnel" />
        <ReadingTable
          :items="reading.items"
          :read-only="readOnly"
          :busy="busy"
          :reordering="saves.reordering.value"
          :job-id="jobId"
          :active-id="panelPaper?.cntsId ?? null"
          :panel-id="PANEL_ID"
          @update="update"
          @open="openPanel"
          @open-pdf="(payload) => emit('open-pdf', payload)"
        />
        <CandidateDrawer
          v-if="reading.excluded.length"
          :excluded="reading.excluded"
          :read-only="readOnly"
          :busy="busy"
          @revive="(cnts) => update(cnts, { state: 'candidate' })"
        />
        <div class="wk-screen__next">
          <p v-if="hint" class="rs-muted">{{ hint }}</p>
          <button v-if="reading.topic_id === null" type="button" class="rs-btn rs-btn--ghost" @click="emit('go', 'topics')">
            제목 고르기
          </button>
          <template v-else-if="outlineMade">
            <button type="button" class="rs-btn" @click="emit('go', 'proposal')">{{ FINAL_STEP_NAME }} 단계로</button>
            <button
              type="button"
              class="rs-btn rs-btn--ghost"
              :disabled="readOnly || busy || !canOutline"
              @click="makeOutline(true)"
            >
              {{ REMAKE_REPORT }}
            </button>
          </template>
          <button
            v-else
            type="button"
            class="rs-btn"
            :disabled="readOnly || busy || !canOutline"
            @click="makeOutline(false)"
          >
            {{ MAKE_REPORT }}
          </button>
        </div>
      </template>
    </section>

    <DeepReadPanel
      :panel-id="PANEL_ID"
      :paper="panelPaper"
      :tabs="PANEL_TABS"
      tab="chat"
      :detail-href="panelDetailHref"
      :store="chatStore"
      @close="closePanel"
      @open-pdf="(payload) => emit('open-pdf', payload)"
      @detail="onDetail"
    >
      <template #extra>
        <div v-if="panelItem" class="wk-panel__save">
          <!-- 표의 [담음] 과 같은 저장(update) — 누른 상태(aria-pressed)가 담음이다 -->
          <button
            type="button"
            class="rs-btn rs-btn--small"
            :class="{ 'rs-btn--ghost': panelItem.state !== 'in' }"
            :aria-pressed="panelItem.state === 'in'"
            :disabled="readOnly || busy || panelItem.state === 'out'"
            @click="togglePanelSave"
          >
            담음
          </button>
          <span v-if="readOnly" class="rs-muted">예시 연구는 담을 수 없습니다 — 대화는 할 수 있습니다.</span>
          <span v-else-if="panelItem.state === 'out'" class="rs-muted">뺀 논문입니다 — 표에서 [되돌리기]를 누르면 담을 수 있습니다.</span>
        </div>
        <details v-if="panelPath" class="wk-panel__path">
          <summary>들어온 경로 — {{ panelPath.label }}</summary>
          <p class="wk-path__quote">{{ panelPath.chunk.text }}</p>
          <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="openPathChunk">원문 보기</button>
        </details>
      </template>
    </DeepReadPanel>
  </div>
</template>
```

script — vue·부품 import. 교체 전:

```ts
import { computed, onMounted, ref } from "vue";
import CandidateDrawer from "~/components/work/CandidateDrawer.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
```

교체 후:

```ts
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import CandidateDrawer from "~/components/work/CandidateDrawer.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import DeepReadPanel from "~/components/work/DeepReadPanel.vue";
```

script — composable·utils import(R1 뒤 기준 — 그 아래 workPhase import 줄은 그대로). 교체 전:

```ts
import { useReadingSaves } from "~/composables/useReadingSaves";
import { type ResearchWorkHandle, useWorkApi } from "~/composables/useResearchWork";
import type { OpenPdfPayload } from "~/types/research";
import type { ReadingPut, WorkResource, WorkStep } from "~/types/work";
import { canMakeOutline, outlineHint } from "~/utils/readingList";
import { httpStatus, workErrorMessage } from "~/utils/researchErrors";
```

교체 후:

```ts
import { useReadingSaves } from "~/composables/useReadingSaves";
import { type ResearchWorkHandle, useWorkApi } from "~/composables/useResearchWork";
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { OpenPdfPayload } from "~/types/research";
import type { ReadingPut, WorkResource, WorkStep } from "~/types/work";
import { type PanelPaper, panelTabs } from "~/utils/deepRead";
import type { DeepReadMessage } from "~/utils/deepReadSse";
import { detailUrl, readingAnchor } from "~/utils/detailSource";
import { canMakeOutline, firstPathChunk, outlineHint, pathPdfTarget } from "~/utils/readingList";
import { httpStatus, workErrorMessage } from "~/utils/researchErrors";
import { isPlainClick } from "~/utils/restorePosition";
```

script — emits(`:91`). 교체 전:

```ts
const emit = defineEmits<{ go: [step: WorkStep]; "open-pdf": [payload: OpenPdfPayload] }>();
```

교체 후:

```ts
const emit = defineEmits<{ go: [step: WorkStep]; "open-pdf": [payload: OpenPdfPayload]; panel: [open: boolean] }>();
```

script — `update`(`:138-141`) 뒤에 패널. 교체 전:

```ts
function update(cnts: string, body: ReadingPut): void {
  if (readOnly.value) return;
  saves.enqueue(cnts, body);
}
```

교체 후:

```ts
function update(cnts: string, body: ReadingPut): void {
  if (readOnly.value) return;
  saves.enqueue(cnts, body);
}

// ── 오른쪽 딥리드 패널(spec §12-4 D24) ─────────────────────────
// 이 단계는 딥리드 탭만 둔다. [담음] 은 표와 같은 저장 사슬(update → useReadingSaves)을 탄다. 논문별 대화는 이 방문 동안만
// 이 화면이 쥔다 — 단계를 옮기거나 새로고침하면 비운다(서버는 대화를 저장하지 않는다, 06e 정함 20)
const PANEL_ID = "wk-panel-reading";
const PANEL_TABS = panelTabs("reading");
const chatStore = new Map<string, DeepReadMessage[]>();
const { leave } = useDetailLeave();
// opener — 패널을 연 행 제목 버튼. 닫으면 그리로 초점을 돌린다
const panel = shallowRef<{ cntsId: string; opener: HTMLElement | null } | null>(null);
// 패널의 논문은 지금 표의 행에서 읽는다 — [담음] 을 누른 뒤 다시 읽은 상태가 패널에도 그대로 보인다
const panelItem = computed(() => {
  const id = panel.value?.cntsId;
  return id ? (reading.value?.items.find((i) => i.cnts_id === id) ?? null) : null;
});
const panelPaper = computed<PanelPaper | null>(() =>
  panelItem.value ? { cntsId: panelItem.value.cnts_id, meta: panelItem.value.meta } : null,
);
const panelPath = computed(() => (panelItem.value ? firstPathChunk(panelItem.value) : null));
const panelDetailHref = computed(() => (panelItem.value ? readingDetailUrl(panelItem.value.cnts_id) : null));

// 상세에서 [연구 화면으로]·뒤로 가기로 돌아오면 이 단계(s=reading)의 그 행(r-<cnts>)으로 돌아온다 — 표의 [논문 상세 ↗] 와 같은 출처
function readingDetailUrl(cnts: string): string {
  return detailUrl(cnts, { kind: "research", job: props.jobId, e: null, s: "reading" }, { at: readingAnchor(cnts), y: null });
}

// 같은 제목을 다시 누르면 닫는다(제목 버튼의 aria-expanded 와 같은 뜻)
function openPanel(cnts: string, el: HTMLElement): void {
  if (panel.value?.cntsId === cnts) {
    closePanel();
    return;
  }
  panel.value = { cntsId: cnts, opener: el };
}

// 닫으면 누른 행 제목으로 초점을 돌린다 — 그 사이 표를 다시 그려 요소가 바뀌었으면 같은 행의 제목 버튼을 찾는다
function closePanel(): void {
  const was = panel.value;
  panel.value = null;
  if (!was) return;
  void nextTick(() => {
    const back = was.opener?.isConnected
      ? was.opener
      : document.querySelector<HTMLElement>(`[data-anchor="${readingAnchor(was.cntsId)}"] .wk-reading__open`);
    back?.focus();
  });
}

// [담음] 토글 — 예시 연구·뺀 논문은 버튼이 꺼져 있다(update 도 예시 연구를 막는다)
function togglePanelSave(): void {
  const item = panelItem.value;
  if (!item || item.state === "out") return;
  update(item.cnts_id, { state: item.state === "in" ? "candidate" : "in" });
}

function openPathChunk(): void {
  const item = panelItem.value;
  const path = panelPath.value;
  if (item && path) emit("open-pdf", pathPdfTarget(item, path.chunk));
}

// [논문 상세 ↗] — 새 창·새 탭은 브라우저에 맡기고(주소에 돌아올 자리가 이미 있다), 그냥 누르면 지금 주소에 자리를 남기고 떠난다
function onDetail(e: MouseEvent): void {
  const item = panelItem.value;
  if (!item || !isPlainClick(e)) return;
  e.preventDefault();
  void leave(readingDetailUrl(item.cnts_id), { at: readingAnchor(item.cnts_id), y: null });
}

// 패널이 열리고 닫히는 것을 연구 화면에 알린다 — 넓은 화면에서 왼쪽 메뉴(LNB)를 접는다(06e 정함 30). 단계를 옮기면 이 화면이
// 내려가며 닫힘을 알리므로 연구 화면은 단계를 따로 보지 않는다
watch(
  () => panelPaper.value !== null,
  (open) => emit("panel", open),
);
onBeforeUnmount(() => emit("panel", false));
```

- [ ] **Step 7: 연구 화면 — 패널 열림 리스너**

`frontend/pages/research/[id].vue` — 교체 전(`:73`):

```html
          <ReadingStep v-else-if="step === 'reading'" :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" @open-pdf="openPdf" />
```

교체 후:

```html
          <ReadingStep v-else-if="step === 'reading'" :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" @open-pdf="openPdf" @panel="workPanelOpen = $event" />
```

교체 전(`:513-514`):

```ts
const pdfOpener = usePdfOpener();
const { pdf, closePdf } = pdfOpener;
```

교체 후:

```ts
const pdfOpener = usePdfOpener();
const { pdf, closePdf } = pdfOpener;
// 단계 화면(ReadingStep·ProposalStep)의 오른쪽 딥리드 패널이 열려 있는지 — 왼쪽 메뉴(LNB) 접기가 읽는다(06e 정함 30)
const workPanelOpen = ref(false);
```

- [ ] **Step 8: 표·패널 [담음] CSS 를 더한다**

`frontend/assets/css/work.css` — 맨 끝 표시 줄(R4 묶음은 그 위에 있다). 교체 전:

```css
/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

교체 후:

```css
/* ── 참고문헌 선택하기 — 제목을 누르면 오른쪽 딥리드(06e R5). 제목은 링크 모양을 지킨 버튼, 상세는 서지 줄 끝의 작은 링크 ── */
.wk-reading__open {
  padding: 0;
  text-align: left;
  background: none;
  border: 0;
  cursor: pointer;
}
.wk-reading__open[aria-expanded="true"] {
  color: var(--skx-primary);
}
.wk-reading__detail,
.wk-reading__detail:visited {
  font-weight: 700;
  color: var(--skx-primary);
  white-space: nowrap;
}
.wk-reading__detail:hover,
.wk-reading__detail:focus-visible {
  text-decoration: underline;
}
.wk-reading__row--active {
  border-color: var(--skx-primary);
  box-shadow: inset 0 0 0 1px var(--skx-primary);
}
.wk-panel__save {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.6rem;
  font-size: 0.6rem;
}
.wk-panel__path {
  font-size: 0.62rem;
  line-height: 1.5;
}
.wk-panel__path > summary {
  font-weight: 700;
  color: var(--skx-ink);
  cursor: pointer;
}
.wk-panel__path[open] > summary {
  margin-bottom: 0.4rem;
}
.wk-panel__path .wk-path__quote {
  display: block;
  margin: 0 0 0.4rem;
}

/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

- [ ] **Step 9: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <R5 앞과 같은 수> passed` / `Tests <R5 앞 + 3> passed`(파트 R 전체로는 파트 R 앞 + 3 files / + 21 tests — 통합 사본에서 A3 를 it 1개로 흉내 내 dev `40 files / 732` 에서 `43 files / 754`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep "Duplicated imports" | grep -c "firstPathChunk"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff -U0 HEAD -- "frontend/pages/research/[id].vue" | grep "^[+-][^+-]"`
Expected: 네 줄뿐(§12-5 — `[id].vue` 는 `:73` 과 script 두 줄):

```text
-          <ReadingStep v-else-if="step === 'reading'" :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" @open-pdf="openPdf" />
+          <ReadingStep v-else-if="step === 'reading'" :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" @open-pdf="openPdf" @panel="workPanelOpen = $event" />
+// 단계 화면(ReadingStep·ProposalStep)의 오른쪽 딥리드 패널이 열려 있는지 — 왼쪽 메뉴(LNB) 접기가 읽는다(06e 정함 30)
+const workPanelOpen = ref(false);
```

- [ ] **Step 10: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/utils/readingList.ts && git add frontend/tests/unit/readingList.test.ts && git add frontend/components/work/ReadingTable.vue && git add frontend/components/work/ReadingStep.vue && git add "frontend/pages/research/[id].vue" && git add frontend/assets/css/work.css && git status --short && git commit -m "[Feat] round06e 프론트 — 참고문헌 선택하기에서 논문 제목을 누르면 화면을 떠나지 않고 오른쪽에 그 논문의 딥리드가 열린다. 제목은 aria-expanded·aria-controls 를 단 버튼이고 열린 행을 강조하며, 같은 제목을 다시 누르면 닫혀 초점이 그 제목으로 돌아온다. 상세로 떠나는 것은 서지 줄 끝의 작은 [논문 상세 ↗](돌아오는 자리·새 탭 그대로)다. 패널은 ReadingStep 이 쥔다 — [담음] 토글은 표와 같은 저장 사슬을 타고(예시 연구·뺀 논문은 끈다, 대화는 연다), 들어온 경로의 첫 대목(firstPathChunk)을 접어 두며, 논문별 대화는 이 방문 동안 이어진다. 패널이 열리고 닫히는 것을 panel 로 알리고(단계를 옮기면 내려가며 닫힘), 연구 화면은 :73 리스너와 workPanelOpen 한 줄만 단다 — LNB 연결은 늦게 머지하는 줄이 단다(06e 정함 30)"
```

---

### Task R6 (조건부): 딥리드 패널이 열리면 LNB 접기 — AppSidebar collapsed 연결

> **조건: 06d(`feat/round06d-research-progress-screen`)가 06e 보다 먼저 dev 에 머지됐을 때만 한다.** 06d 가 아직이면 이 Task 를 건너뛰고 완료노트 '이월'에 "LNB 접기 연결(`[id].vue:3-7` 두 곳)은 늦게 머지하는 06d 의 조건부 LNB 접기 연결이 단다 — 06d 는 06e 의 `workPanelOpen` 을 읽기만 한다(정함 30, spec §12-5)"를 적는다. 건너뛰었어도 dev 머지 Task(Task Z4) Step 1 이 다시 판정한다 — 그 사이 06d 가 들어왔으면 그때 이 Task 를 한다.
> **실행 시점:** 이 Task 는 파트 R 자리에 적지만 **S4 뒤**(전역 실행 순서 — S4 → R6 → K1)에 판정하고 한다 — 보고서 화면의 리스너(S4 의 `[id].vue:74`)가 있어야 두 단계 화면의 패널이 모두 LNB 를 접는다.

spec §12-4 배치 '1440px·LNB 펼침이면 패널이 열릴 때 LNB 를 접는다'·§12-5 '둘 중 늦게 머지하는 줄이 함께 단다', 정함 30. 리스너(`:73`·`:74` 의 `@panel="workPanelOpen = $event"`)와 변수(`const workPanelOpen = ref(false);`)는 R5·S4 가 이미 달았다 — 이 Task 는 `[id].vue:3-7` 의 두 곳만 고친다(06d 계획의 조건부 LNB 접기 연결과 같은 범위). 새 ref·리스너·`watch(step)` 를 더하지 않는다.

**알아 둘 것:**
- **검색 화면 선례(`pages/papers/index.vue:2-4`):** 루트 `:class="['skx-app', chatPaperId && 'is-lnb-collapsed']"` 와 `<AppSidebar :collapsed="!!chatPaperId">`. `AppSidebar` 의 `collapsed?: boolean` prop(`AppSidebar.vue:146`)은 접힘 상태를 더하기만 한다(`isCollapsed = !open.value || !!props.collapsed` — `:175`). 루트의 `is-lnb-collapsed` 는 `style_skovix.css:598-615` 가 LNB 폭을 3.2rem 으로 줄이는 규칙이다.
- **06d 의 `[id].vue` 변경과의 관계:** 06d 는 `<main class="rs-page">`(`:9`)의 class·import 블록·여러 블록을 고치지만 `:3-4`(`<div class="skx-app">`·`<AppSidebar` 여는 줄)는 이 계약대로 남겨 둔다(06d 계획의 조건부 LNB 접기 연결 — 06e 가 먼저 머지되면 06d 가 같은 두 곳을 고친다). Step 1 의 merge 에서 `[id].vue` 가 겹치면 06e 쪽(`:73`·`:74`·`:514` 뒤 두 줄)과 06d 쪽을 모두 살린다.
- **dev 를 받으면 06d 의 테스트가 함께 들어온다** — Step 2 에서 다시 잰 수를 이 Task 와 그 뒤 Task 의 새 '앞 수' 로 삼는다(계획 머리 '기준선 읽는 법').
- 패널이 닫히면(`workPanelOpen` false) LNB 는 사용자가 펼쳐 둔 상태로 돌아온다 — prop 은 접힘을 더할 뿐 사용자의 접기 상태(`open`)를 바꾸지 않는다.

**Files:**
- Modify: `frontend/pages/research/[id].vue` (`:3-4` — 루트 class·`AppSidebar` prop 두 곳)

기준선(S4 뒤 + 06d dev 머지를 받은 뒤 — Step 2 에서 잰다): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 테스트를 더하지 않는다(+0).

- [ ] **Step 1: 조건을 판정하고 dev 를 받는다**

Run: `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e log dev --oneline --merges | grep -c "feat/round06d-research-progress-screen"`
Expected: `0` 이면 06d 가 아직 dev 에 없다 — **여기서 멈추고 이 Task 를 건너뛴다**(위 조건의 이월 문장을 완료노트 초안에 적는다). `1` 이상이면 아래 merge 로 간다.

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e merge dev -m "Merge dev into feat/round06e-assistant-auto-report — 06d 진행 화면·입구 받기(LNB 접기 연결 전)"
```

Expected: `Merge made by the 'ort' strategy.`(이미 받았으면 `Already up to date.`). 충돌이 나면 `git status` 의 충돌 파일을 열어 두 줄의 변경을 모두 살려 고친 뒤 `git add <파일>` 을 하나씩 하고 `git commit --no-edit` — `[id].vue` 는 06e 가 `:73`·`:74`·`:514` 뒤 두 줄, 06d 가 그 밖이다.

- [ ] **Step 2: 받은 상태를 보고 새 앞 수를 잰다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -n "workPanelOpen" "frontend/pages/research/[id].vue"`
Expected: 세 줄 — `<ReadingStep …@panel="workPanelOpen = $event" />`·`<ProposalStep …@panel="workPanelOpen = $event" />`(S4)·`const workPanelOpen = ref(false);`(06d 가 같은 이름을 새로 만들지 않았다 — 정함 30). 줄이 더 있으면(06d 가 리스너나 ref 를 더 달았다) 같은 요소의 `@panel` 이 두 번이 되거나 `workPanelOpen` 이 두 번 선언된다 — 06d 쪽 줄을 지우지 말고 멈춰 06d 세션에 알린다(계약 위반).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -c "is-lnb-collapsed" "frontend/pages/research/[id].vue"; sed -n 3,4p "frontend/pages/research/[id].vue"; grep -n "collapsed?: boolean" frontend/components/AppSidebar.vue`
Expected: `0`, 그다음 두 줄 `  <div class="skx-app">`·`    <AppSidebar`(아직 LNB 연결이 없다 — 06d 의 LNB 접기 연결은 06e 가 먼저 머지됐을 때만 06d 가 한다), 끝으로 `AppSidebar.vue` 에서 `const props = defineProps<{ collapsed?: boolean }>();` 한 줄(06d 가 prop 을 늘렸으면 `collapsed?: boolean` 이 든 그 줄 — 이름이 바뀌었으면 Step 3 에서 그 이름을 쓴다). `is-lnb-collapsed` 가 `1` 이상이면 06d 가 이미 두 곳을 달았다 — 계약과 다르지만 결과가 같으므로 Step 3 을 건너뛰고 Step 4 의 확인만 한 뒤 완료노트 '이월'에 그 사실을 적는다(커밋 없음).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <S4 뒤 + 06d 가 더한 파일 수> passed` / `Tests <S4 뒤 + 06d 가 더한 수> passed`. 나온 두 수를 적어 둔다 — 이 Task 와 그 뒤 Task(K1~)의 새 '앞 수' 다. 실패가 있고 06e 파일이 아니면 받은 06d 의 것이다 — 멈추고 사용자와 06d 세션에 알린다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest -q -p no:cacheprovider 2>&1 | tail -1`
Expected: `5 failed, <S4 뒤 + 06d 가 더한 수> passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 Task 0 기준선과 같은 세 파일(`test_build_manifest.py` 2·`test_loaders.py` 3·`test_book_chat.py` 수집 오류). 나온 passed 수를 새 '앞 수' 로 적어 둔다.

- [ ] **Step 3: LNB 접기를 잇는다**

`frontend/pages/research/[id].vue` — 교체 전(`:3-4`):

```html
  <div class="skx-app">
    <AppSidebar
```

교체 후:

```html
  <div :class="['skx-app', workPanelOpen && 'is-lnb-collapsed']">
    <AppSidebar
      :collapsed="workPanelOpen"
```

- [ ] **Step 4: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <Step 2 에서 적은 수> passed` / `Tests <Step 2 에서 적은 수> passed`(+0)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff -U0 HEAD -- "frontend/pages/research/[id].vue" | grep "^[+-][^+-]"`
Expected: 세 줄뿐(Step 3 을 건너뛰었으면 빈 출력):

```text
-  <div class="skx-app">
+  <div :class="['skx-app', workPanelOpen && 'is-lnb-collapsed']">
+      :collapsed="workPanelOpen"
```

브라우저 확인 항목(마무리 운영 확인에 넘긴다): 1440px·LNB 펼침에서 참고문헌 선택하기의 제목을 누르면 LNB 가 접히고(3.2rem) 패널을 닫으면 펼쳐진다 · 보고서 화면의 인용 칩(S4)도 같다 · 패널을 연 채 단계를 옮기면 LNB 가 펼쳐진다(단계 화면이 내려가며 `panel` false).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add "frontend/pages/research/[id].vue" && git status --short && git commit -m "[Feat] round06e 프론트 — 단계 화면의 오른쪽 딥리드 패널이 열리면 연구 화면의 왼쪽 메뉴(LNB)를 접는다(1440px 에서 표가 빠듯해지지 않게 — 검색 화면 선례와 같은 루트 is-lnb-collapsed·AppSidebar collapsed). 06d 가 먼저 dev 에 머지돼 늦게 머지하는 06e 가 [id].vue 의 두 곳만 단다 — 리스너와 workPanelOpen 은 R5·S4 가 이미 달았다(06e 정함 30)"
```

---

## 파트 메모 — 뼈대와 다른 점

1. **R1 범위를 서버 문구 두 줄 더 넓혔다.** 뼈대는 서버에서 `VERSION_CONFLICT` 만 고치지만, 같은 화면에 그대로 보이는 서버 문구 `IF_MATCH_FORMAT`(`research_proposal.py:57` '계획서 버전')·`CONCEPTS_BUSY`(`research_work.py:53` '핵심 개념을 만드는 중')·`patch_work` 의 422(`:252` '핵심 개념을 1개 이상')도 함께 고친다 — 키워드 칩 화면에서 '핵심 개념' 오류가 뜨지 않게. `test_research_work_api.py:510` 이 글자를 기대해 ✎ 한다(매개변수 둘). **뼈대 §3 공유 파일 표의 `app/api/research_work.py`·`app/tests/test_research_work_api.py` 줄 맨 앞에 'R1(문구 두 줄 / :510 기대 한 줄)'을 더해야 한다** — 파트 K(K2·K3·K5)는 이 줄들을 old 로 잡지 않지만 R1 뒤 상태를 전제로 한다.
2. **R1 의 `workPhase.test.ts` ✎ 줄:** 뼈대의 `:97-98` 에 `:96`(topics 라벨 '주제')도 들어간다(한 it 의 세 줄). `:85-87`·`:197-204`·`:216`·`:232-234` 는 뼈대 그대로이고, `:197` 의 it 은 미리보기와 함께 이어가기 안내(`body`)도 기대하게 했다.
3. **R1 의 온보딩·이어가기 글:** 뼈대는 ④ 의 본문·결정만 정했다. ② ③ 의 본문·결정도 06e 흐름(키워드가 제목에 들어감·제목을 누르면 딥리드·[보고서 만들기])으로 고쳐 썼고, 이어가기 안내는 조사 규칙(정함 1) 때문에 `… → 보고서 3단계를 거쳐 보고서 초안까지` 꼴이다(`${STEP_NAMES.proposal}를` 을 만들지 않는다). 테스트는 `ONBOARDING_LEAD` 를 글자로, ③ 결정·④ 본문은 `[보고서 만들기]` 를 품는지만 본다.
4. **R1 의 남는 옛 이름 확인 기대값:** 뼈대는 '주석 줄만'이라고 했다. 실제 명령은 `//`·`<!--` 로 시작하는 줄을 걸러서 `OutlineEditor.vue:73`(HTML 주석의 둘째 줄) 한 줄이 남는다 — 기대 출력에 그 한 줄을 적었다. 서버 문구는 상수·`detail=` 글을 찾는 grep 으로 따로 본다.
5. **R2 composable 의 타입 이름:** 1-6 의 인라인 모양을 그대로 두고 이름만 붙여 내보낸다 — 옵션 `DeepReadChatOptions`, 반환 `DeepReadChat`(같은 composable 파일만 — 다른 utils 와 겹치지 않는다).
6. **R3 의 `aria-live`:** 뼈대는 '스트리밍 칸(`:36-45`)에 `aria-live="polite"`'다. 그 칸에 달면 글이 흐르는 동안 토막마다 읽혀, 칸 밖 숨김 live 영역(`.skx-sr-only`)에 **방금 보낸 질문의 끝난 답만** 싣는다(논문을 바꿔 다른 대화를 펼칠 때는 싣지 않는다). spec 의 '스트리밍 답은 aria-live'(답을 화면낭독기가 읽는다)는 지킨다.
7. **R3 의 [원문 보기] 버튼 class `skx-chat-source-open`:** BookChat 안의 이름이라 `skx-` 접두를 따랐고 여백 CSS 는 패널 안에서만 그리므로 R4 묶음의 `.wk-panel .skx-chat-source-open` 에 둔다. 출처 칩 버튼의 숨김 꼬리 ` 대목 보기` 를 더했다(이름은 보이는 글자로 시작하는 관례).
8. **R4 CSS 선택자:** 1-8 표의 이름에 더해 `.wk-panel__heading`(제목·서지 묶음)·`.wk-panel__detail`(머리의 [논문 상세 ↗])·`.wk-panel__chat`·`.wk-panel__sources`(탭 본문)·`.wk-panel .skx-chat-messages|msg|input-wrap|source-open`(BookChat 여백 덮기)·`@keyframes wk-panel-in`(서랍 움직임 — reduced-motion 이면 없음)을 쓴다. 모두 `.wk-panel` 이름 아래라 다른 파트와 겹치지 않는다.
9. **R4 Esc 범위:** '모든 모드에서 Esc → close' 를 문서가 아니라 패널(`<aside>`)의 keydown 으로 듣는다 — 초점이 패널 안에 있을 때만 닫힌다. 서랍·전체 폭은 초점이 패널 안에 갇혀 늘 그렇고, 2단(side)에서는 표에서 누른 Esc 가 패널을 닫지 않는다(원문 뷰어·온보딩의 문서 Esc 와 겹치지 않게).
10. **R4 루트는 조각(배경 `div` + `<aside>`)이다** — 배경은 1200px 미만에서만 CSS 로 보인다. `paper` 가 null 이면 아무것도 그리지 않는다(뼈대 1-7 의 `paper: PanelPaper | null` 을 '닫힘'으로 읽었다).
11. **R5 [논문 상세 ↗] 자리:** 뼈대의 '제목 옆 작은 링크'를 서지 줄(`.wk-reading__meta`) 끝에 둔다 — 새 감싸개 class 없이 기존 flex 줄에 들어간다. 숨김 꼬리 `「제목」` 을 붙여 행마다 링크 이름이 갈린다(같은 파일의 관례).
12. **R5 패널 열림 emit 의 근거:** 뼈대의 `watch(panel, …)` 대신 `panelPaper`(표에 그 행이 있는지)로 낸다 — 뜻은 같고, 다시 읽은 목록에서 행이 사라지면(드묾) 패널이 닫힌 것과 emit 이 어긋나지 않는다. `panel` 은 DOM 요소를 쥐어 `shallowRef` 다.
13. **R5 ReadingStep 템플릿은 통째로 갈음한다**(루트를 `.wk-split` 으로 감싸 안쪽이 한 단 들어간다). A5 가 두 버튼 글을 다른 꼴로 두었으면 그 꼴을 옮기라고 Task 에 적었다. ReadingStep 은 R5 뒤에 고치는 Task 가 없어(뼈대 §3 — A5 → R1 → R5) 들여쓰기를 맞췄다 — 파트 S 의 S4 는 ProposalStep 뒤에 H3 가 있어 안쪽 들여쓰기를 옮기지 않는다고 정했다(두 파일의 방식이 다른 까닭). 머리 안내에 '제목을 누르면 오른쪽에서 그 논문과 대화할 수 있습니다.' 한 문장을 더했다.
14. **R5 CSS 재사용:** 들어온 경로 대목 글은 기존 `.wk-path__quote` 를 쓰고 `.wk-panel__path .wk-path__quote` 로 여백만 맞춘다(새 이름을 두지 않는다).
15. **R6 실행 시점·선행·판정:** 뼈대의 '선행 R5·S4' 를 지키려 Task 머리에 'S4 뒤(전역 실행 순서 S4 → R6 → K1)에 판정·실행, 건너뛰었으면 Task Z4 Step 1 이 다시 판정'을 적었다. 조건 판정은 06d 계획의 LNB 접기 연결 조건과 대칭인 `git log dev --oneline --merges | grep -c "feat/round06d-research-progress-screen"` 이다(뼈대의 `grep -i round06d` 보다 좁다 — 문서 브랜치 `docs/round06d-…` 머지를 잘못 세지 않게). 계획 머리가 'R6 Step 1 = 06d dev 받기'로 부르므로 Step 1 이 판정과 `git merge dev` 를 함께 하고, Step 2 가 받은 상태(`workPanelOpen` 세 줄·`is-lnb-collapsed` 0)와 06d 테스트가 들어온 새 '앞 수'(vitest·백엔드)를 잰다. 06d 가 계약과 달리 두 곳을 이미 달았으면(`is-lnb-collapsed` ≥ 1) Step 3 을 건너뛴다(06d 계획의 같은 Task 와 대칭).

---

## 파트 S — 인용 근거 패널·딥리드 논문 프롬프트

덮는 spec 항목: §12-4 '참고문헌 선택하기·오른쪽 딥리드·인용 근거(D24)' 가운데 **인용 근거 A안** — 데이터(`research_generations.input.papers[i].excerpt`, 새 조회 `GET /api/research/{id}/sections/{key}/sources`, 쓰는 중인 절은 drafts 의 gen_id, 대목이 없으면 초록만 — 뼈대 정함 23) → **Task S1**, 하이라이트(본문 쪽 누른 칩이 든 문장, 대목 쪽 글자 n-gram 이 가장 많이 겹치는 문장 — 화면 계산) → **Task S3**(순수 함수·타입·조회), 보고서 인용 칩 → 오른쪽 패널 인용 근거 탭(논문 카드 + 원문 대목 하이라이트 + [원문 보기] + [이 논문과 대화하기] — 같은 자리가 딥리드 탭으로), 단계 ④ 는 두 탭·[담음] 없음·ProposalStep 이 쥔다, [원문 보기]는 `[id].vue:74` 의 ProposalStep 에 `@open-pdf`, 닫으면 누른 칩으로 초점 복귀, 패널 열림 emit(LNB 접기 재료 — 정함 30), 딥리서치 보고서의 `CitationChip.vue` 팝오버는 그대로(정함 24 — 흐르는 글의 칩은 span 그대로) → **Task S4**. §12-11 '딥리드 프롬프트의 논문 변형' 권고 채택(정함 18 — `book_chat.paper.yaml` + `chat_prompt(book)`, `BookOut.doc_type`) → **Task S2**.

하지 않는 것: 리랭커 뒷받침 점수·원문 뷰어 안 하이라이트(spec §12-4 — 대회 뒤·§12-9), 연구 맥락을 반영한 딥리드 첫 화면(정함 19), 딥리드 대화 서버 저장(§12-4·§12-9).

순서: S1(A2·X1 뒤 — 같은 `research_proposal.py`·`proposal_views.py`·`test_research_proposal_api.py`) → S2(선행 없음 — 백엔드 줄기 어디서든) → S3(선행 없음 — 프론트 순수 함수) → S4(R4·R5·S3·X5 뒤 — 패널 부품·`.wk-split`·`[id].vue` 의 `workPanelOpen` 을 쓰고, `ProposalSection.vue`·`ProposalStep.vue` 는 A5→X3→X4→X5→R1 뒤 기준 — ProposalStep 의 detailSource import 는 X4 가 더한 줄을 고친다). 배포: S1·S2 는 fastapi(S2 의 프롬프트 파일은 fastapi 이미지에 실린다 — 딥리드 대화는 FastAPI 엔드포인트가 부른다), S3·S4 는 nuxt.

---

### Task S1: 인용 근거 조회 API — GET …/sections/{key}/sources

spec §12-4 '인용 근거 A안 — 데이터'·'새 조회'·'대목이 없으면 초록만', 뼈대 정함 23. 보고서 문단의 인용 칩을 누르면 화면이 그 문장을 쓸 때 모델에 넘긴 원문 대목을 보여야 한다. 대목은 절 쓰기 API(`generate_section`)가 생성을 넣을 때 이미 골라 `research_generations.input.papers[i].excerpt`(`{chunk_id, page_start, page_end, text ≤1200}` — `passages.pick_excerpt`, `section_input._papers`)에 저장했는데 지금 화면에는 내려오지 않는다(`proposal_views.drafts_of` 는 evidence·figures 만). 이 Task 는 그 생성 행의 input 만 읽어 `{E#: {cnts_id, abstract, excerpt}}` 로 돌려주는 읽기 전용 조회를 더한다.

**알아 둘 것:**
- **어느 생성인가:** 쿼리 `gen`(화면이 문단의 절 `gen_id` 를 싣는다 — Task S4)이 있으면 그 행. 이 연구·kind section·target == key 가 아니면 404 `NO_SECTION_SOURCE_GEN`(다른 절·다른 연구·문단 다시 쓰기(paragraph) 생성·없는 id 모두). `gen` 이 없으면 저장된 절의 `gen_id` 행 → 없으면 그 키의 열린(queued·running) section 생성 중 id 가 가장 큰 것 → 다 없으면 404 `NO_SECTION`. 끝난(실패·취소) 생성만 있는 절은 읽을 입력이 없는 것으로 본다. 화면은 저장된 문단에서만 패널을 여므로(정함 24) 늘 `gen` 을 싣지만, `gen` 없는 순서도 spec 의 '쓰는 중인 절은 drafts 의 gen_id' 를 그대로 받는다.
- **문단 다시 쓰기·사용자가 고친 문단도 같은 입력이다:** 문단 [다시]는 그 절을 쓴 section 생성의 input(같은 [E#] 번호)으로 돈다(`regenerate_paragraph` — `research_proposal.py:503-509`). 사용자가 고친 글도 절의 evidence 지도로 다시 검사한다. 그래서 절의 `gen_id` 생성 입력 하나가 그 절 모든 문단의 근거 번호표다.
- **무거운 것을 부르지 않는다:** 서지(BookRepository)·Milvus·리랭커를 부르지 않는다 — 초록(`ABSTRACT_CHARS` 600자 안)·대목(`EXCERPT_CHARS` 1200자 안)은 그 생성이 모델에 넘긴 그대로다. 그래서 FastAPI 의 동기 대목 고르기·세션 규칙(함정 17·18)에 걸리지 않는 짧은 읽기다. 응답의 대목은 네 칸(`chunk_id`·`page_start`·`page_end`·`text`)만 고정해 싣고, 글이 비거나 대목이 없으면(Milvus 를 못 읽은 논문 — `pick_excerpt` 가 None) `excerpt: null` — 화면이 초록만 보인다. 쪽은 저장값(0부터 센다) 그대로다(화면 `pageLabel` 이 +1).
- **예시 연구도 읽는다** — 쓰기가 아니므로 `_writable` 을 부르지 않는다(spec §12-4 '예시 연구에서는 대화는 연다'와 같은 결).
- **키 검사:** `WRITABLE_SECTION_KEYS`(`prior.g1`~`g4`·`gap`) 밖이면 422 `SECTION_NOT_WRITABLE`(절 쓰기 API 와 같은 문구 — `research_proposal.py:285`). 순서는 뼈대대로 키 422 → 연구 404(`_get_work` — '이어간 연구가 없습니다') → 생성.
- **앞 Task 뒤 기준:** `research_proposal.py` 는 A1(`NEED_READING`)·A2(`NO_SECTION_PAPERS_CODE`·근거 없음 409 detail)·X1(shapes import·`OutlinePut`·`put_outline`)·R1(`VERSION_CONFLICT`)이 먼저 고친다. 이 Task 가 잡는 old 는 그 Task 들이 건드리지 않는 자리다 — `from fastapi import …` 한 줄, `from services.research_work.proposal_views import paper_ids, proposal_view` 한 줄, 파일 끝 `regenerate_paragraph` 의 마지막 네 줄. `proposal_views.py` 는 A2(`section_gens_of` — `drafts_of` 아래, `proposal_view` 결과 키, docstring)·X1(`stale_flags`·docstring :3-6)이 먼저 고친다 — 이 Task 는 `_reference` 바로 위(`paper_ids` 와 `_reference` 사이)에 넣어 A2 의 자리와 겹치지 않는다. 테스트 파일은 A1·A2·X1(·R1)이 고친 뒤다 — 이 Task 는 import 목록에 이름 하나와 파일 끝(`TestRegenerateParagraph.test_example_work_is_read_only` 뒤)만 고친다.
- 세 파일 모두 CRLF 다 — Edit 도구로 고친다.

**Files:**
- Modify: `app/services/research_work/proposal_views.py` (머리 docstring 끝에 한 줄 묶음, `_reference` :119-120 바로 위에 `_excerpt`·`section_sources`)
- Modify: `app/api/research_proposal.py` (`from fastapi import …` :16, `proposal_views` import :41, 파일 끝 :513-516 뒤에 상수 `NO_SECTION_SOURCE_GEN`·핸들러 `get_section_sources`)
- Test: `app/tests/test_research_proposal_api.py` (`proposal_views` import 목록 :35-37, 파일 끝 :1174-1176 뒤)

기준선(X1 적용 뒤): 계획서 API 테스트 실패 0. 이 Task 는 +10(매개변수 펼친 수 — `test_unknown_key_is_422` 가 셋)이다(dev `da80f23` 만 놓고 잰 값: `test_research_proposal_api.py` 95 → 105, 백엔드 전체 passed +10 — 통합 사본 실측).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_proposal_api.py` — 맨 위 `from services.research_work.proposal_views import (…)` 의 이름 목록에 `section_sources` 를 `stale_flags` 바로 앞에 더한다. 이 Task 는 늘 A2 뒤에 돈다 — A2 가 이 줄에 `section_gens_of` 를 더한 뒤의 줄이 old:

```python
    cited_papers, disclosure_of, drafts_of, paper_ids, proposal_view, section_gens_of, stale_flags,
```

new(116자 — 120자 안):

```python
    cited_papers, disclosure_of, drafts_of, paper_ids, proposal_view, section_gens_of, section_sources, stale_flags,
```

(참고 — dev `da80f23` 의 줄은 `…, proposal_view, stale_flags,` 다. 그 줄이 보이면 A2 가 아직 안 된 것이다 — A2 를 먼저 한다.)

같은 파일 — 파일 끝에 인용 근거 조회 테스트를 더한다. old(파일의 마지막 테스트 — A·X·R 의 어느 Task 도 고치지 않는다):

```python
    def test_example_work_is_read_only(self, api):
        jid, _ = _para_work(api.engine, is_example=True)
        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p2/regenerate").status_code == 409
```

new:

```python
    def test_example_work_is_read_only(self, api):
        jid, _ = _para_work(api.engine, is_example=True)
        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p2/regenerate").status_code == 409


# ── 인용 근거 조회 (06e Task S1) ─────────────────────────────────────────

SOURCE_EXCERPT = {"chunk_id": "KCI_A__0004", "page_start": 4, "page_end": 5,
                  "text": "가족 지지가 높은 노인일수록 우울 점수가 낮았다. 배우자 유무는 차이가 없었다."}
SOURCE_INPUT = {
    **PARA_SOURCE_INPUT,
    "papers": [{**PARA_SOURCE_INPUT["papers"][0], "abstract": "가족 지지와 우울 초록", "excerpt": SOURCE_EXCERPT},
               {**PARA_SOURCE_INPUT["papers"][1], "abstract": "사회적 지지 척도 초록", "excerpt": None}],
}
SOURCE_VIEW = {
    "E1": {"cnts_id": "KCI_A", "abstract": "가족 지지와 우울 초록", "excerpt": SOURCE_EXCERPT},
    "E2": {"cnts_id": "KCI_B", "abstract": "사회적 지지 척도 초록", "excerpt": None},
}


class TestSectionSourcesShape:
    def test_maps_each_number_to_the_paper_its_abstract_and_its_excerpt(self):
        assert section_sources(SOURCE_INPUT) == SOURCE_VIEW
        # 번호나 논문이 없는 원소는 뺀다(drafts_of 와 같은 규칙). 저장된 대목에 다른 키가 있어도 응답은 네 칸뿐이다
        odd = {"papers": [{"eid": "E1", "cnts_id": ""}, {"cnts_id": "KCI_C"},
                          {"eid": "E4", "cnts_id": "KCI_D", "abstract": "초록",
                           "excerpt": {**SOURCE_EXCERPT, "score": 0.9}}]}
        assert section_sources(odd) == {"E4": {"cnts_id": "KCI_D", "abstract": "초록", "excerpt": SOURCE_EXCERPT}}
        assert section_sources({}) == {} and section_sources({"papers": None}) == {}

    def test_a_paper_without_an_excerpt_keeps_its_abstract_only(self):
        # 대목을 못 읽은 논문(Milvus 실패 — excerpt None)과 글이 빈 대목은 초록만 싣는다. 초록이 없으면 빈 글
        inp = {"papers": [{"eid": "E1", "cnts_id": "KCI_A", "abstract": "초록만", "excerpt": None},
                          {"eid": "E2", "cnts_id": "KCI_B", "abstract": None,
                           "excerpt": {**SOURCE_EXCERPT, "text": "   "}}]}
        assert section_sources(inp) == {"E1": {"cnts_id": "KCI_A", "abstract": "초록만", "excerpt": None},
                                        "E2": {"cnts_id": "KCI_B", "abstract": "", "excerpt": None}}


def _src_work(engine, *, is_example: bool = False) -> tuple[uuid.UUID, int]:
    """prior.g1 이 써진 연구 — 저장된 절의 gen_id 가 가리키는 section 생성 행(대목이 든 입력)."""
    jid = _sec_work(engine, is_example=is_example, proposal=False)
    source = add_generation(engine, jid, kind="section", status="done", target="prior.g1",
                            input=SOURCE_INPUT, output={"paragraphs": []})
    add_proposal(engine, jid, version=3, outline=_sec_outline(_topic_id(engine, jid)),
                 sections={"prior.g1": {**SEC_STORED, "gen_id": source}})
    return jid, source


def _sources(api, jid, key: str = "prior.g1", gen: int | None = None):
    params = {} if gen is None else {"gen": gen}
    return api.client.get(f"/api/research/{jid}/sections/{key}/sources", params=params)


class TestGetSectionSources:
    def test_the_written_section_reads_its_own_generation(self, api):
        jid, _ = _src_work(api.engine)
        # 그 뒤 실패한 다시 쓰기 — 저장된 절의 문단은 앞 생성의 입력 번호로 쓰였다
        add_generation(api.engine, jid, kind="section", status="failed", target="prior.g1",
                       input={"papers": [{"eid": "E1", "cnts_id": "KCI_Z", "abstract": "다른 입력", "excerpt": None}]})

        res = _sources(api, jid)

        assert res.status_code == 200 and res.json() == SOURCE_VIEW
        assert api.events == [] and api.dispatch.calls == 0          # 읽기만 한다

    def test_gen_query_reads_a_draft_being_written(self, api):
        jid, source = _src_work(api.engine)
        rewrite_input = {"papers": [{"eid": "E1", "cnts_id": "KCI_C", "abstract": "독거 노인 초록",
                                     "excerpt": {**SOURCE_EXCERPT, "chunk_id": "KCI_C__0001", "text": "독거 노인 대목."}}]}
        rewriting = add_generation(api.engine, jid, kind="section", status="running", target="prior.g1",
                                   input=rewrite_input)
        gap_input = {"papers": [{"eid": "E1", "cnts_id": "KCI_D", "abstract": "농촌 노인 초록", "excerpt": None}]}
        gap = add_generation(api.engine, jid, kind="section", status="queued", target="gap", input=gap_input)

        # 화면이 고른 생성(gen) — 다시 쓰는 중인 절의 입력이든 저장된 절의 입력이든 그 행을 읽는다
        assert _sources(api, jid, gen=rewriting).json() == {"E1": {
            "cnts_id": "KCI_C", "abstract": "독거 노인 초록",
            "excerpt": {**SOURCE_EXCERPT, "chunk_id": "KCI_C__0001", "text": "독거 노인 대목."}}}
        assert _sources(api, jid, gen=source).json() == SOURCE_VIEW
        # gen 이 없으면 저장된 절의 생성이 먼저고, 절이 아직 없는 키는 그 키의 열린 생성이다
        assert _sources(api, jid).json() == SOURCE_VIEW
        gap_view = {"E1": {"cnts_id": "KCI_D", "abstract": "농촌 노인 초록", "excerpt": None}}
        assert _sources(api, jid, key="gap").json() == gap_view
        assert _sources(api, jid, key="gap", gen=gap).json() == gap_view

    def test_a_generation_of_another_section_is_404(self, api):
        jid, _ = _src_work(api.engine)
        other_key = add_generation(api.engine, jid, kind="section", status="done", target="prior.g2",
                                   input=SOURCE_INPUT)
        paragraph = add_generation(api.engine, jid, kind="paragraph", status="done", target="prior.g1#p1",
                                   input=SOURCE_INPUT)
        _, other_work = _src_work(api.engine)

        for gen in (other_key, paragraph, other_work, 999999):
            res = _sources(api, jid, gen=gen)
            assert (res.status_code, res.json()["detail"]) == (404, "이 절의 생성 기록이 아닙니다")

    def test_no_section_and_no_open_generation_is_404(self, api):
        jid, _ = _src_work(api.engine)
        # 끝난(실패·취소) 생성만 있는 절은 읽을 입력이 없다 — 절도 열린 생성도 없다
        add_generation(api.engine, jid, kind="section", status="failed", target="gap", input=SOURCE_INPUT)
        add_generation(api.engine, jid, kind="section", status="canceled", target="gap", input=SOURCE_INPUT)

        res = _sources(api, jid, key="gap")

        assert (res.status_code, res.json()["detail"]) == (404, "절이 없습니다")
        missing = _sources(api, uuid.uuid4())
        assert (missing.status_code, missing.json()["detail"]) == (404, "이어간 연구가 없습니다")

    @pytest.mark.parametrize("key", ["background", "prior.g5", "topic"])
    def test_unknown_key_is_422(self, api, key):
        jid, _ = _src_work(api.engine)
        res = _sources(api, jid, key=key)
        assert (res.status_code, res.json()["detail"]) == (422, "이 절은 아직 쓸 수 없습니다")

    def test_example_work_can_be_read(self, api):
        jid, source = _src_work(api.engine, is_example=True)
        assert _sources(api, jid).json() == SOURCE_VIEW
        assert _sources(api, jid, gen=source).json() == SOURCE_VIEW
```

(`PARA_SOURCE_INPUT`·`SEC_STORED`·`_sec_work`·`_sec_outline`·`_topic_id`·`api` fixture 는 이 파일에 이미 있다 — `_sec_work(…, proposal=False)` 뒤 `add_proposal` 로 절을 넣는 꼴은 `_para_work`(`:1100-1112`)와 같다. `api` fixture 는 BookRepository 를 대역으로 바꾸지 않는다 — 이 조회는 서지를 읽지 않으므로 `sec_books` 를 쓰지 않는다.)

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_proposal_api.py -q -p no:cacheprovider`
Expected: 수집 오류 — `E   ImportError: cannot import name 'section_sources' from 'services.research_work.proposal_views'` 와 `!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!` · `1 warning, 1 error`

- [ ] **Step 3: 응답 모양과 조회를 구현한다**

`app/services/research_work/proposal_views.py` — 머리 docstring 의 맨 끝(닫는 `"""` 바로 앞 — A2·X1 이 더한 줄이 있으면 그 뒤)에 다음 두 줄을 더한다:

```text
- section_sources 는 인용 근거 조회(GET …/sections/{key}/sources)의 응답 — 절 생성 입력의 [E#] 마다 논문·초록·
  원문 대목. 그 생성이 모델에 넘긴 그대로를 읽는다(서지·Milvus·리랭커를 다시 부르지 않는다).
```

같은 파일 — `paper_ids` 와 `_reference` 사이에 두 함수를 넣는다. old(A2·X1 이 건드리지 않는 자리):

```python
def _reference(cnts_id: str, book) -> str:
    return build_citation(book)["korean"] if book is not None else f"서지 정보 없음 ({cnts_id})."
```

new:

```python
def _excerpt(value) -> dict | None:
    """저장된 원문 대목 → 응답 모양 {chunk_id, page_start, page_end, text}. 대목이 없거나(Milvus 를 못 읽음) 글이
    비면 None — 화면이 초록만 보인다. 쪽은 저장값 그대로다(0부터 센다 — 화면 pageLabel 이 +1 해 보인다)."""
    if not value or not (value.get("text") or "").strip():
        return None
    return {"chunk_id": value.get("chunk_id") or "", "page_start": value.get("page_start"),
            "page_end": value.get("page_end"), "text": value["text"]}


def section_sources(gen_input: dict) -> dict[str, dict]:
    """인용 근거 조회(GET …/sections/{key}/sources)의 응답 — 절 생성 입력의 papers 를 {E#: {cnts_id, abstract,
    excerpt}} 로. 순서는 입력 순서(= 번호 순 — section_input._papers 가 E1 부터 매긴다). 초록·대목은 그 생성이
    모델에 넘긴 그대로라(초록 ABSTRACT_CHARS·대목 EXCERPT_CHARS 자 안) 서지·Milvus·리랭커를 다시 부르지 않는다.
    eid·cnts_id 가 없는 원소는 뺀다(drafts_of 와 같은 규칙)."""
    out: dict[str, dict] = {}
    for p in (gen_input or {}).get("papers") or []:
        if not p.get("eid") or not p.get("cnts_id"):
            continue
        out[p["eid"]] = {"cnts_id": p["cnts_id"], "abstract": p.get("abstract") or "",
                         "excerpt": _excerpt(p.get("excerpt"))}
    return out


def _reference(cnts_id: str, book) -> str:
    return build_citation(book)["korean"] if book is not None else f"서지 정보 없음 ({cnts_id})."
```

`app/api/research_proposal.py` — import 두 줄. old:

```python
from fastapi import APIRouter, Depends, Header, HTTPException, Response
```

new:

```python
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
```

old:

```python
from services.research_work.proposal_views import paper_ids, proposal_view
```

new:

```python
from services.research_work.proposal_views import paper_ids, proposal_view, section_sources
```

같은 파일 — 파일 끝(`regenerate_paragraph` 의 마지막 네 줄 뒤)에 조회를 더한다. old:

```python
    await db.commit()
    _send_dispatch()
    await publish_work(jid, "generation", queued_event(gen_id, "paragraph", target))
    return {"gen_id": gen_id}
```

new:

```python
    await db.commit()
    _send_dispatch()
    await publish_work(jid, "generation", queued_event(gen_id, "paragraph", target))
    return {"gen_id": gen_id}


# ── 인용 근거 조회 (06e — D24 인용 근거 A안) ─────────────────────────────

NO_SECTION_SOURCE_GEN = "이 절의 생성 기록이 아닙니다"


@router.get("/api/research/{job_id}/sections/{key}/sources")
async def get_section_sources(job_id: str, key: str, gen: int | None = Query(None),
                              db: AsyncSession = Depends(get_db)):
    """인용 근거 — 그 절을 쓸 때 모델에 넘긴 근거 논문의 초록·원문 대목 {E#: {cnts_id, abstract, excerpt}}.

    어느 생성인지는 gen(화면이 문단의 절 gen_id 를 싣는다)으로 고르고 — 이 연구·이 키의 section 생성이 아니면 404 —
    없으면 저장된 절의 gen_id → 그 키의 열린 section 생성(id 가 가장 큰 것) 순이다. 절도 열린 생성도 없으면 404.
    생성 행의 input 만 읽는다 — 대목은 절 쓰기 API 가 생성을 넣을 때 이미 골라 저장했으므로 서지·Milvus·리랭커를
    부르지 않는다(spec §12-4). 읽기라 예시 연구도 읽는다."""
    if key not in WRITABLE_SECTION_KEYS:
        raise HTTPException(status_code=422, detail=SECTION_NOT_WRITABLE)
    jid = _job_uuid(job_id)
    await _get_work(db, jid)
    G = ResearchGeneration
    if gen is not None:
        row = await db.get(G, gen)
        if row is None or row.work_id != jid or row.kind != "section" or row.target != key:
            raise HTTPException(status_code=404, detail=NO_SECTION_SOURCE_GEN)
    else:
        proposal = await db.get(ResearchProposal, jid)
        section = dict((proposal.sections or {}).get(key) or {}) if proposal is not None else {}
        source_id = section.get("gen_id")
        row = await db.get(G, source_id) if source_id is not None else None
        if row is not None and (row.work_id != jid or row.kind != "section"):
            row = None
        if row is None:
            row = (await db.execute(
                select(G).where(G.work_id == jid, G.kind == "section", G.target == key,
                                G.status.in_(GEN_OPEN_STATUSES))
                .order_by(G.id.desc()).limit(1)
            )).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=NO_SECTION)
    return section_sources(dict(row.input or {}))
```

(`WRITABLE_SECTION_KEYS`·`SECTION_NOT_WRITABLE`·`NO_SECTION`·`GEN_OPEN_STATUSES`·`ResearchGeneration`·`ResearchProposal`·`select`·`_job_uuid`·`_get_work` 는 이 파일에 이미 있다 — `SECTION_NOT_WRITABLE`·`NO_SECTION` 은 `:285`·`:289`. 저장된 절의 생성 행 검사는 `regenerate_paragraph`(`:503-506`)와 같은 꼴이다 — 연구·kind 만 보고, 끝난 상태든 아니든 그 행의 입력을 읽는다. 경로가 `PUT /api/research/{job_id}/sections/{key}` 와 마디 수가 달라 라우팅이 겹치지 않는다.)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_proposal_api.py -q -p no:cacheprovider`
Expected: `(Task 앞 + 10) passed, 2 warnings`(dev `da80f23` 만 놓고 잰 값 `105 passed`)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`
Expected: `5 failed, (Task 앞 + 10) passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 기준선과 같은 세 파일(`test_build_manifest.py`·`test_loaders.py`·`test_book_chat.py` 수집)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/proposal_views.py app/api/research_proposal.py app/tests/test_research_proposal_api.py && git status --short && git commit -m "[Feat] round06e — 인용 근거 조회 GET /api/research/{id}/sections/{key}/sources 를 더한다(D24 인용 근거 A안의 데이터). 그 절을 쓸 때 모델에 넘긴 근거 논문의 초록·원문 대목을 {E#: {cnts_id, abstract, excerpt}} 로 돌려준다 — 생성은 쿼리 gen(화면이 문단의 절 gen_id 를 싣는다)으로 고르고, 없으면 저장된 절의 gen_id → 그 키의 열린 section 생성 순이다. 생성 행의 input 만 읽어 서지·Milvus·리랭커를 부르지 않는다(대목은 절 쓰기 때 이미 골라 저장했다). 대목이 없으면(Milvus 를 못 읽은 논문) 초록만 싣고, 이 연구·이 절의 section 생성이 아닌 gen 은 404, 절도 열린 생성도 없으면 404, 쓰지 않는 절 키는 422, 예시 연구도 읽는다"
```

---

### Task S2: 딥리드 논문 프롬프트 — book_chat.paper.yaml

spec §12-11 '딥리드 프롬프트의 논문 변형'(권고 채택 — 뼈대 정함 18). 연구 화면의 오른쪽 딥리드(R4·R5·S4)는 논문 1편과의 기존 대화(`POST /api/books/chat/{cnts_id}` → `stream_book_chat`)를 끼운다. 그런데 `book_chat.py:135` 가 `get_prompt("book_chat")` 로 문서 종류를 넘기지 않아 논문에도 책 문구('전담 독서 도우미'·'[책 요약]'·'이 책에서는 다루지 않습니다')가 나간다. 이 Task 는 논문 변형 프롬프트 파일을 더하고 `chat_prompt(book)` 가 `doc_type` 으로 고르게 한다. 같은 대화 길에서 참고문헌 의도 질문('인용'·'출처'가 든 질문)이 `AttributeError` 로 끊기는 기존 버그(`book_chat.py:118`)도 함께 고친다(검토 반영 — 아래 '알아 둘 것'). 화면 문구(BookChat 의 인사·입력 칸)는 R3 의 `docKind` 가 맡는다 — 이 Task 는 서버 쪽만이다.

**알아 둘 것:**
- **고르는 규칙:** `get_prompt(name, doc_type)` 의 해석 순서(`services/prompts.py:48-58` — `{name}.{doc_type}.yaml` → `{name}.yaml`)를 그대로 쓴다. `chat_prompt(book) = get_prompt("book_chat", getattr(book, "doc_type", None) or None)` — 논문(`paper`)만 새 파일이고, 책·문학·정책·빈 값·속성이 없는 객체는 기본 `book_chat.yaml` 이다(문학·정책 변형은 만들지 않는다 — 그 화면은 06e 범위 밖).
- **`BookOut` 에 `doc_type` 이 없다:** 대화 엔드포인트(`api/book.py:637-653` `chat_with_book`)는 `BookRepository.get_by_cnts_id` 의 `BookOut` 을 넘기는데(`repositories/book.py:19-24`), `BookOut`(`schemas/book.py:46-70`)에는 ORM 의 `doc_type` 칼럼(`models/book.py:62`)이 없다 — `getattr` 만으로는 늘 None 이라 논문 변형을 고르지 못한다. `BookOut.doc_type: Optional[str] = None` 한 줄을 더한다(정함 18 — 예외 파일. `from_attributes=True` 라 ORM 값이 그대로 실리고, `GET /api/books/{cnts_id}` 등 응답에 필드 하나가 더해질 뿐이다. 응답 dict 전체를 견주는 기존 테스트는 없다 — 통합 사본 전체 실행으로 확인).
- **참고문헌 의도 질문이 끊기는 기존 버그를 함께 고친다(검토 반영 — 계획 머리 정함 31 을 '고친다'로 정한다):** `book_chat.py:113-121` 은 질문에 `_REF_INTENT_KEYWORDS`(`:19-22` — '참고문헌'·'인용'·'출처'·'reference' 등)가 부분 문자열로 들어 있으면 `(book.extra or {}).get("references", [])`(`:118`)를 읽는다. 그런데 넘어오는 `book` 은 `BookRepository.get_by_cnts_id` 의 `BookOut`(`api/book.py:647-651`)이라 `extra` 가 없다 — `AttributeError: 'BookOut' object has no attribute 'extra'` 로 첫 조각 전에 스트림이 끊긴다(0b51e68 부터). 06e 에서는 인용 근거 탭에서 [이 논문과 대화하기]로 넘어간 사용자가 '이 인용 근거가 맞아?'·'출처가 어디야?' 처럼 묻는 장면(spec §12-8 장면 3 — 시연의 딥리드 장면)이 바로 그 길이다. `BookOut.references`(`schemas/book.py:66-67` — `extra["references"]` 를 싣는 칸, ORM `Book` 도 같은 이름의 property `models/book.py:92-94`)를 읽는 작은 함수 `_book_references(book)` 로 빼고(`getattr` — 속성이 없거나 None 이면 빈 목록) `:118` 을 그것으로 바꾼다. 테스트는 그 함수를 새 테스트 파일의 대역 fixture 위에서 고정한다(+1).
- **프롬프트 글:** 기본과 같은 params(`max_tokens 10000`·`temperature 0.3`)·같은 변수(`title`·`author`·`pub_date`·`summary`·`themes`)·빈 `user`(코드가 히스토리·검색 컨텍스트로 만든다). 글만 논문으로 바꾸고 규칙 한 줄('논문이 밝히지 않은 수치나 결론을 만들지 마세요')을 더한다. 쪽 언급 규칙('관련 내용의 출처(페이지)를 자연스럽게 언급하세요')은 그대로 둔다 — 출처 칩은 답 글의 쪽 표기(`p.X`·`X페이지`)로 대목을 고른다(`_find_cited_hits`, `book_chat.py:63-84`). 예시·개수는 넣지 않는다(함정 15).
- **테스트 대역(뼈대 비평 #11):** `services.chat.book_chat` 은 머리에서 `services.ingestion.embedder`(FlagEmbedding)·`indexer`(pymilvus)를 import 한다 — 로컬 venv 에는 둘 다 없어 `test_book_chat.py` 가 수집 오류다(기준선의 오류 1). 새 테스트 파일은 대역을 **fixture 안에서** 끼우고 되돌린다. 꼴은 `test_search_chunk_answer_flag.py:24-53` 의 `_stubbed_pipeline` 을 따른다 — 미설치 무거운 모듈만 MagicMock 으로 꽂고, 캐시된 우리 모듈(`book_chat`·`embedder`·`indexer`)과 부모 패키지 속성을 monkeypatch 로 비운 뒤 새로 import 해 넘기고, 끝나면 **새로 올린 모듈을 직접 뺀다**. `test_embed_index_guard.py:17-31` 의 `_stub_missing_module` 은 `monkeypatch.delitem(…, raising=False)` 만 써서 원래 없던 키(여기서 새로 import 한, 더미에 묶인 `indexer` 등)가 teardown 뒤에도 남는다(그 파일의 docstring 이 말하는 오염 — `test_search_chunk_answer_flag.py` 가 이 문제를 고친 꼴이다). 되돌림은 `test_loader_leaves_sys_modules_as_it_found_them` 으로 고정한다(같은 이름의 테스트가 `test_search_chunk_answer_flag.py:56-62` 에 있다).
- **`verify_prompt_parity.py` 는 지금 돌지 않는다:** 82b4998 에서 `scripts/` → `app/scripts/` 로 옮긴 뒤 `APP = Path(__file__).resolve().parents[1] / "app"`(`:7`)가 `app/app` 을 가리키고(`python scripts/verify_prompt_parity.py` → `ModuleNotFoundError: No module named 'services'`, `python -m scripts.verify_prompt_parity` → `FileNotFoundError: … app\app\domains\nl_library\prompts …` — 계획 작성 때 실측), 견주는 원본 상수(`git show HEAD:app/services/chat/book_chat.py` 의 `_SYSTEM_TEMPLATE`)도 이미 없다. spec 의 '동등성 맞춤'대로 `book_chat` 줄 뒤에 논문 변형 줄을 더하되(기본 줄은 그대로), 정본 검사는 `test_prompts.py` 의 새 테스트다. 스크립트 경로 고치기는 이 Task 범위가 아니다(완료노트 이월 한 줄).
- **배포:** fastapi 이미지(프롬프트 YAML 은 `app/domains` 아래라 이미지에 실린다 — 함정 4 의 `scripts/`·`research/` 와 다르다). 워커는 이 경로를 쓰지 않는다.
- 고치는 기존 파일은 모두 CRLF 다 — Edit 도구로 고친다. 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다.

**Files:**
- Create: `app/domains/nl_library/prompts/book_chat.paper.yaml`
- Modify: `app/services/chat/book_chat.py` (`_find_cited_hits` :63 바로 위에 `chat_prompt`·`_book_references`, :118 `refs`, :135 `tpl`)
- Modify: `app/schemas/book.py` (`BookOut` 의 `created_at` :60 아래 한 줄)
- Modify: `app/scripts/verify_prompt_parity.py` (:84-88 `book_chat` 줄 뒤)
- Test: `app/tests/test_prompts.py` (import :6-9, `test_nl_library_prompts_do_not_send_removed_vllm_guided_params` :146 앞에 새 테스트)
- Create: `app/tests/test_book_chat_prompt.py`

기준선: 이 Task 는 백엔드 passed 를 +6 한다(`test_prompts.py` 9 → 10, 새 `test_book_chat_prompt.py` 5 — dev `da80f23` 만 놓고 잰 통합 사본 실측. `test_prompts.py` 는 06e 의 다른 Task 가 고치지 않는다).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_prompts.py` — import 에 jinja2 meta 를 더한다. old:

```python
import pytest
import yaml

from services.prompts import PromptLibrary
```

new:

```python
import pytest
import yaml
from jinja2 import Environment, meta

from services.prompts import PromptLibrary
```

같은 파일 — `test_nl_library_prompts_exist_and_render` 뒤(그 테스트의 기본 `book_chat` 단언 `:124-126` 은 그대로 둔다)에 논문 변형 테스트를 넣는다. old:

```python
def test_nl_library_prompts_do_not_send_removed_vllm_guided_params():
```

new:

```python
def test_book_chat_paper_variant_keeps_the_variables_and_params():
    """딥리드 논문 변형(round06e) — book_chat.paper.yaml 은 기본 book_chat.yaml 과 같은 변수·params·빈 user 로
    렌더되고 글만 '논문'이다(호출부 book_chat.chat_prompt 가 doc_type 으로 고른다). 변형이 없는 종류는 기본으로
    물러난다. 쪽 언급 규칙은 그대로다 — 출처 칩(_find_cited_hits)이 답 글의 쪽 표기로 대목을 고른다.
    예시·개수는 넣지 않는다(함정 15)."""
    real_dir = Path(__file__).resolve().parents[1] / "domains" / "nl_library" / "prompts"
    env = Environment()

    def variables(name: str) -> set[str]:
        data = yaml.safe_load((real_dir / name).read_text(encoding="utf-8"))
        return meta.find_undeclared_variables(env.parse(data["system"] + data["user"]))

    assert variables("book_chat.paper.yaml") == variables("book_chat.yaml") == {
        "title", "author", "pub_date", "summary", "themes"}

    lib = PromptLibrary(real_dir)
    values = {"title": "t", "author": "a", "pub_date": ", 2024", "summary": "s", "themes": "th"}
    base_s, base_u, base_p = lib.get("book_chat").render(**values)
    paper_s, paper_u, paper_p = lib.get("book_chat", doc_type="paper").render(**values)
    assert paper_p == base_p == {"max_tokens": 10000, "temperature": 0.3}
    assert paper_u == base_u == ""
    assert paper_s.startswith('당신은 논문 "t" (a, 2024) 의 전담 읽기 도우미입니다.')
    assert "[논문 요약]\ns" in paper_s and "[핵심 주제]\nth" in paper_s
    assert "이 논문에서는 다루지 않습니다" in paper_s and "페이지" in paper_s
    assert "책" not in paper_s and paper_s != base_s
    assert not re.search(r"예:|예시|\d+\s*(?:개|가지|문장|줄)", paper_s)
    for dt in ("book", "literature", "policy", None):
        assert lib.get("book_chat", doc_type=dt).render(**values)[0] == base_s


def test_nl_library_prompts_do_not_send_removed_vllm_guided_params():
```

`app/tests/test_book_chat_prompt.py` (새 파일, 전체):

```python
"""test_book_chat_prompt.py — 딥리드 대화의 시스템 프롬프트 고르기(services/chat/book_chat.chat_prompt, round06e).

논문(doc_type paper)은 book_chat.paper.yaml, 그 밖(책·문학·정책·doc_type 없음)은 기본 book_chat.yaml 이다. 연구 화면의
오른쪽 딥리드(D24)가 논문에 책 문구('전담 독서 도우미'·'이 책에서는')를 내던 것을 고친다(spec §12-11 권고 채택). 참고문헌
의도 질문('인용'·'출처' 등)이 BookOut 에 없는 extra 를 읽어 끊기던 것도 고친다(_book_references).

book_chat 은 임베딩(FlagEmbedding)·Milvus(pymilvus)를 물고 오는 embedder·indexer 를 머리에서 import 한다 — 로컬 venv
에는 둘 다 없어(test_book_chat.py 는 그래서 수집 오류다) 미설치일 때만 더미를 꽂고 새로 import 한다. 더미와 새로 올린
모듈은 끝나면 import 전 그대로 되돌린다(test_search_chunk_answer_flag.py 의 _stubbed_pipeline 과 같은 방식) — 뒤에 도는
test_embed_index_guard.py 등이 더미에 묶인 embedder·indexer 를 물려받지 않게.
"""
import importlib
import sys
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from schemas.book import BookOut

_HEAVY = ("FlagEmbedding", "pymilvus")
_CACHED = ("services.chat.book_chat", "services.ingestion.embedder", "services.ingestion.indexer")
VARS = {"title": "노인 우울 연구", "author": "김철수", "pub_date": ", 2019", "summary": "요약", "themes": "우울, 지지"}


def _stubbed_book_chat(monkeypatch):
    """더미 위에서 book_chat 을 새로 import 해 넘기고, 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 없던 키를 되돌릴 목록에 올리지 않는다 — 여기서 새로 import 한 모듈(더미 pymilvus 에
    묶인 indexer 등)은 직접 빼고, 원래 있던 항목·부모 패키지 속성은 monkeypatch 가 되돌리게 둔다."""
    for name in _HEAVY:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    for name in _CACHED:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield importlib.import_module("services.chat.book_chat")
    for name in _CACHED:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)


@pytest.fixture
def book_chat(monkeypatch):
    yield from _stubbed_book_chat(monkeypatch)


def test_a_paper_gets_the_paper_prompt(book_chat):
    system, user, params = book_chat.chat_prompt(SimpleNamespace(doc_type="paper")).render(**VARS)

    assert system.startswith('당신은 논문 "노인 우울 연구" (김철수, 2019) 의 전담 읽기 도우미입니다.')
    assert "[논문 요약]\n요약" in system and "이 논문에서는 다루지 않습니다" in system
    assert user == "" and params == {"max_tokens": 10000, "temperature": 0.3}


def test_a_book_or_a_missing_doc_type_gets_the_base_prompt(book_chat):
    base = book_chat.get_prompt("book_chat").render(**VARS)[0]
    assert "전담 독서 도우미" in base

    # 변형이 없는 종류(문학·정책)·빈 값·속성이 없는 객체(옛 호출부)는 모두 기본으로 물러난다
    for book in (SimpleNamespace(doc_type="book"), SimpleNamespace(doc_type="literature"),
                 SimpleNamespace(doc_type=None), SimpleNamespace(doc_type=""), SimpleNamespace()):
        assert book_chat.chat_prompt(book).render(**VARS)[0] == base


def test_book_references_reads_the_book_out_field(book_chat):
    # 참고문헌 의도('인용'·'출처' 등)일 때 읽는 목록 — 대화 엔드포인트가 넘기는 BookOut 에는 extra 가 없고 references 가
    # extra["references"] 를 싣는다. 옛 식 (book.extra or {}) 는 AttributeError 로 스트림을 끊었다
    at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    paper = BookOut(id=uuid.uuid4(), cnts_id="KCI_1", title="노인 우울 연구", created_at=at,
                    references=["김(2019)", "이(2020)"])
    assert book_chat._book_references(paper) == ["김(2019)", "이(2020)"]
    assert book_chat._book_references(BookOut(id=uuid.uuid4(), cnts_id="B1", title="책", created_at=at)) == []
    # 속성이 없거나 None 이어도 빈 목록이다
    assert book_chat._book_references(SimpleNamespace()) == []
    assert book_chat._book_references(SimpleNamespace(references=None)) == []


def test_loader_leaves_sys_modules_as_it_found_them():
    snapshot = {name: sys.modules.get(name) for name in _CACHED}
    with pytest.MonkeyPatch.context() as mp:
        loader = _stubbed_book_chat(mp)
        next(loader)
        next(loader, None)
    assert {name: sys.modules.get(name) for name in _CACHED} == snapshot


def test_book_out_carries_doc_type():
    # 대화 엔드포인트(api/book.py chat_with_book)는 BookRepository.get_by_cnts_id 의 BookOut 을 넘긴다 — ORM 의
    # doc_type 이 실려야 chat_prompt 가 고른다. 없으면 None(옛 서지)
    at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    row = SimpleNamespace(id=uuid.uuid4(), cnts_id="KCI_1", title="노인 우울 연구", created_at=at, doc_type="paper")
    assert BookOut.model_validate(row).doc_type == "paper"
    assert BookOut(id=uuid.uuid4(), cnts_id="B1", title="책", created_at=at).doc_type is None
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_prompts.py tests/test_book_chat_prompt.py -q -p no:cacheprovider`
Expected: `5 failed, 10 passed, 2 warnings` — `test_book_chat_paper_variant_keeps_the_variables_and_params`(`FileNotFoundError: … book_chat.paper.yaml`), `test_a_paper_gets_the_paper_prompt`·`test_a_book_or_a_missing_doc_type_gets_the_base_prompt`(`AttributeError: module 'services.chat.book_chat' has no attribute 'chat_prompt'`), `test_book_references_reads_the_book_out_field`(`AttributeError: module 'services.chat.book_chat' has no attribute '_book_references'`), `test_book_out_carries_doc_type`(`AttributeError: 'BookOut' object has no attribute 'doc_type'`). `test_loader_leaves_sys_modules_as_it_found_them` 는 대역 도우미만 보므로 이미 통과한다(기존 9 + 1)

- [ ] **Step 3: 프롬프트 파일·고르기·응답 필드를 더한다**

`app/domains/nl_library/prompts/book_chat.paper.yaml` (새 파일, 전체):

```yaml
parser: plain
params:
  max_tokens: 10000
  temperature: 0.3
system: |-
  당신은 논문 "{{ title }}" ({{ author }}{{ pub_date }}) 의 전담 읽기 도우미입니다.
  이 논문의 내용을 바탕으로 사용자와 심층적인 대화를 나눕니다.

  [논문 요약]
  {{ summary }}

  [핵심 주제]
  {{ themes }}

  답변 규칙:
  - 반드시 제공된 [참고 내용]을 근거로 답변하세요.
  - 논문에 없는 내용은 "이 논문에서는 다루지 않습니다"라고 솔직하게 말하세요.
  - 관련 내용의 출처(페이지)를 자연스럽게 언급하세요.
  - 논문이 밝히지 않은 수치나 결론을 만들지 마세요.
  - 추측이나 창작은 하지 마세요.
  - 한국어로 답변하세요.
# 논문 변형 — 변수·params·빈 user 는 book_chat.yaml 과 같다(services/chat/book_chat.chat_prompt 가 doc_type 으로 고른다).
# user 메시지는 코드에서 히스토리·검색 컨텍스트로 동적 구성 — 템플릿 없음
user: ""
```

`app/services/chat/book_chat.py` — `_find_cited_hits` 바로 위에 고르기 함수와 참고문헌 목록 함수를 넣는다. old:

```python
def _find_cited_hits(response_text: str, hits: list[SearchHit]) -> list[SearchHit]:
```

new:

```python
def chat_prompt(book):
    """대화 시스템 프롬프트 — 문서 종류(doc_type)의 변형이 있으면 그것(논문 → book_chat.paper.yaml), 없으면 기본
    book_chat.yaml(책 문구). doc_type 이 비었거나 그 속성이 없는 객체도 기본으로 간다(get_prompt 의 해석 순서)."""
    return get_prompt("book_chat", getattr(book, "doc_type", None) or None)


def _book_references(book) -> list[str]:
    """참고문헌 의도('참고문헌'·'인용'·'출처' 등)일 때 모델에 넘길 목록. 대화 엔드포인트가 넘기는 BookOut 에는 extra 가
    없고 references 칸이 extra["references"] 를 싣는다(ORM Book 도 같은 이름의 property). 없으면 빈 목록."""
    return list(getattr(book, "references", None) or [])


def _find_cited_hits(response_text: str, hits: list[SearchHit]) -> list[SearchHit]:
```

같은 파일 — 참고문헌 의도의 목록을 BookOut 에 있는 칸으로 읽는다. old:

```python
        refs: list[str] = (book.extra or {}).get("references", [])
```

new:

```python
        refs = _book_references(book)
```

같은 파일 — 시스템 프롬프트를 고른다. old:

```python
    tpl = get_prompt("book_chat")
```

new:

```python
    tpl = chat_prompt(book)   # 논문이면 논문 문구(book_chat.paper.yaml)
```

`app/schemas/book.py` — `BookOut` 에 문서 종류를 싣는다. old:

```python
    created_at:       datetime
```

new:

```python
    created_at:       datetime
    # 문서 종류(book/paper/literature/policy — 프로파일 doc_types). 딥리드 대화가 프롬프트 변형을 고른다(book_chat.chat_prompt)
    doc_type:         Optional[str] = None
```

(`created_at:       datetime` 은 이 파일에 한 번뿐이다 — `BookOut` 의 `:60`.)

`app/scripts/verify_prompt_parity.py` — 기본 `book_chat` 줄 뒤에 논문 변형 줄을 더한다(기본 줄은 그대로). old:

```python
check("book_chat.system", bc["_SYSTEM_TEMPLATE"].format(
    title="T", author="A", pub_date=", D", summary="S", themes="TH"), s)
assert p == {"max_tokens": 10000, "temperature": 0.3}
```

new:

```python
check("book_chat.system", bc["_SYSTEM_TEMPLATE"].format(
    title="T", author="A", pub_date=", D", summary="S", themes="TH"), s)
assert p == {"max_tokens": 10000, "temperature": 0.3}
# 딥리드 논문 변형(round06e) — 옮겨 온 원본 상수가 없는 새 파일이라 바이트 비교 대신 같은 변수·params 로 렌더되고
# 글이 기본(책)과 다른지만 본다. 정본 검사는 tests/test_prompts.py 의 test_book_chat_paper_variant_keeps_the_variables_and_params
s_paper, _, p_paper = lib.get("book_chat", "paper").render(
    title="T", author="A", pub_date=", D", summary="S", themes="TH")
assert s_paper != s and "논문" in s_paper, "book_chat.paper 가 기본과 같다"
assert p_paper == p, "book_chat.paper params"
print("OK   book_chat.paper.system (기본과 다른 논문 문구 · 같은 params)")
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_prompts.py tests/test_book_chat_prompt.py -q -p no:cacheprovider`
Expected: `15 passed, 2 warnings`

대역이 뒤 테스트로 새지 않는지 — 무거운 모듈을 대역으로 쓰는 파일들을 새 파일 뒤에 한 프로세스로 돌린다:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_book_chat_prompt.py tests/test_embed_index_guard.py tests/test_job_runtime.py tests/test_research_work_membership.py tests/test_research_work_section_input.py tests/test_search_chunk_answer_flag.py tests/test_search_research_path.py tests/test_stage_enrichment.py -q -p no:cacheprovider`
Expected: 실패 0 — `199 passed, 2 warnings`(맨 앞 `tests/test_book_chat_prompt.py` 를 빼고 같은 명령을 돌리면 `194 passed` — 차이가 새 파일의 5 뿐이다. dev `da80f23` 통합 사본 실측이며, 이 여덟 파일은 06e 의 다른 Task 가 고치지 않는다)

변형 줄이 문법상 맞는지 본다(스크립트 자체는 위 '알아 둘 것'대로 돌지 않는다 — 같은 검사를 한 줄로 돌린다):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -c "import ast; ast.parse(open('scripts/verify_prompt_parity.py', encoding='utf-8').read()); print('ok')" && python -c "from pathlib import Path; from services.prompts import PromptLibrary; lib = PromptLibrary(Path('domains/nl_library/prompts')); v = dict(title='T', author='A', pub_date=', D', summary='S', themes='TH'); s, _, p = lib.get('book_chat').render(**v); sp, _, pp = lib.get('book_chat', 'paper').render(**v); print(sp != s and '논문' in sp, pp == p)"`
Expected: `ok` 다음 줄 `True True`

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`
Expected: `5 failed, (Task 앞 + 6) passed, 1 skipped, 2 warnings, 1 error` — 오류 1 은 그대로 `test_book_chat.py` 수집(`FlagEmbedding` 없음 — 새 파일의 대역은 fixture 안에서만 끼우므로 수집 단계의 그 오류를 바꾸지 않는다), 실패 5 는 기준선과 같은 두 파일. `test_embed_index_guard.py` 6개가 기준선처럼 통과하는지 출력에서 본다

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/domains/nl_library/prompts/book_chat.paper.yaml app/services/chat/book_chat.py app/schemas/book.py app/scripts/verify_prompt_parity.py app/tests/test_prompts.py app/tests/test_book_chat_prompt.py && git status --short && git commit -m "[Feat] round06e — 딥리드 대화가 논문에는 논문 프롬프트를 쓴다(spec §12-11 권고 채택). 새 book_chat.paper.yaml(기본과 같은 변수·params·빈 user, 글만 논문 — '전담 읽기 도우미'·'[논문 요약]'·'이 논문에서는 다루지 않습니다', 밝히지 않은 수치·결론을 만들지 않는다는 규칙 한 줄, 쪽 언급 규칙은 출처 칩이 쓰므로 그대로)과 book_chat.chat_prompt(book) — get_prompt('book_chat', doc_type) 의 해석 순서로 논문만 변형, 나머지는 기본. 대화 엔드포인트가 넘기는 BookOut 에 doc_type 이 없어 BookOut.doc_type(선택)을 더한다. 같은 길에서 참고문헌 의도 질문('인용'·'출처' 등이 든 질문)이 BookOut 에 없는 extra 를 읽어 AttributeError 로 끊기던 것도 BookOut.references 를 읽는 _book_references 로 고친다. 동등성 검사는 test_prompts 에 변수 집합·params·금지 글을 고정하고 verify_prompt_parity 에 같은 줄을 더한다. 새 테스트의 FlagEmbedding·pymilvus 대역은 fixture 안에서 끼우고 새로 올린 모듈까지 되돌린다(_stubbed_pipeline 과 같은 꼴)"
```

---

### Task S3: 인용 근거 하이라이트 — 순수 함수·타입·조회

spec §12-4 '하이라이트(제안)' — 본문 쪽은 누른 칩이 든 문장(`sentenceFlags` 의 문장 번호), 대목 쪽은 인용한 문장과 글자 n-gram 이 가장 많이 겹치는 대목 문장(화면 계산), 뼈대 정함 23. 이 Task 는 Task S4 의 화면이 쓸 판단을 순수 함수로 빼서 vitest 로 고정하고, 인용 근거 조회(Task S1)의 응답 타입과 호출 함수를 더한다. `.vue` 는 고치지 않는다.

- **문장 나누기 `excerptSentences(text)`:** 문장 끝(`.`·`!`·`?`·`。`) 뒤 공백에서 나누고(`(?<=[.!?。])\s+`), 앞뒤 공백을 떼고 빈 조각은 버린다. 대목은 원문 글 그대로라 `[E#]` 표기가 없다 — 본문 쪽 `sentenceFlags`(`figureMarkers.ts:47-61` — 마침표 뒤에 붙은 `[E#]` 묶음을 앞 문장으로 센다)와 다른 규칙이 맞다. 고리점 뒤에 공백이 없으면 나누지 않는다(원문의 '…。다음' 은 한 조각).
- **겹침 `ngramOverlap(a, b, n = NGRAM_N)`:** 두 글을 각각 NFKC → `[E#]`·`[F#]` 표기 빼기(전각 표기도 NFKC 뒤 잡힌다) → 소문자 → 공백·문장부호·기호(`\p{P}`·`\p{S}`) 빼기 한 뒤, 코드포인트 단위 글자 n-gram 의 **서로 다른 것** 집합끼리 교집합 크기를 센다. `NGRAM_N = 2` — 한국어는 조사·어미가 붙어 낱말 단위로는 같은 말이 잘 겹치지 않는다('가족 지지가'·'가족지지는' 이 '가족·족지·지지' 셋을 나눈다). n 보다 짧은 글은 n-gram 이 없어 0 이다.
- **고르기 `bestExcerptSentence(cited, excerpt)`:** `excerptSentences(excerpt)` 가운데 겹침이 가장 큰 문장의 번호. 같으면 앞 문장, 모두 0 이면 null(번역·요약해 쓴 문장 — 화면은 강조 없이 대목 전체를 보이고 그렇다고 알린다, Task S4). → **S3 quality 검토 반영(계획과 다른 점 — 파트 S 메모 12, 사용자 판단 대기):** 겹친 수 대신 인용 문장을 덮는 정도(논문 상투구·어미 2-gram 은 무게 0, 나머지는 대목 안 IDF 로 무게를 단 2-gram 의 덮는 비율)가 가장 큰 문장이고, 인용 문장이 상투구뿐이거나 그 값이 `EXCERPT_MATCH_MIN = 0.2` 아래면 null 이다. → **3차 검토 반영(근거가 둘 이상인 문장):** 선택 인자 `eid`(누른 칩의 근거 번호)를 받으면 인용 문장 대신 `citedClaims(sentence, eid)` — 그 번호가 든 마커 묶음 앞의 절(앞 마커 묶음이나 문장 머리부터), 묶음에 근거가 둘 이상이면 그 절을 쉼표·이음 어미 뒤에서 나눈 조각까지 — 의 후보마다 덮는 정도를 재어 가장 큰 값을 쓴다(근거가 하나인 문장은 후보가 문장 하나라 같다). `excerptParts` 도 `eid` 를 받아 그대로 넘긴다. 아래 Step 의 코드·테스트는 처음 계획 그대로 두었다 — 실제 코드는 커밋을 본다.
- **조각 `excerptParts(excerpt, cited)`:** 대목을 문장 경계에서 나누되 사이 공백을 남겨 그대로 이어 붙인다 — 고른 문장만 `mark: true`, 문장 앞뒤 공백은 강조 밖, 이웃한 같은 표시 조각은 하나로 합친다. 조각의 글을 이으면 원문 글자 그대로다(화면이 `<mark>` 로만 감싼다).
- **원문 열기 `citationPdfTarget(source, title)`:** 대목이 있으면 `citedPdfTarget(cnts, title, [{ page_start: excerpt.page_start ?? 0, page_end: excerpt.page_end ?? excerpt.page_start ?? 0 }])`(`pdfViewer.ts:66-73` — 0부터 센 저장값을 뷰어 쪽으로 +1, 0 은 쪽 없이 열고 대목 이름 '쪽 정보 없음'), 없으면 `{ cntsId, title }`(논문 처음부터). 대목 이름(`passages[0].label` — `pageLabel` 의 'p.6–8')은 Task S4 의 대목 머리가 그대로 쓴다.
- **타입(뼈대 1-5):** `SectionSourceExcerpt`·`SectionSource`·`SectionSources`·`CitePick` 은 새 인터페이스다(기존 타입에 필드를 더하지 않아 기존 픽스처가 깨지지 않는다). 서버 모양 그대로 snake_case(`cnts_id`·`page_start`), 화면 상태인 `CitePick` 만 camelCase(`cntsId`·`genId` — `OpenPdfPayload` 와 같은 관례).
- **조회 `getSectionSources(jobId, key, gen)`:** `useWorkApi()` 에 한 줄 — `api<SectionSources>(\`${job(jobId)}/sections/${encodeURIComponent(key)}/sources\`, { query: { gen } })`(`$fetch` 의 query 옵션). 절 키의 점(`prior.g1`)은 그대로 경로에 실린다(`generateSection` 과 같은 인코딩).

**알아 둘 것:**
- **이름(1-6 계약):** `NGRAM_N`·`excerptSentences`·`ngramOverlap`·`bestExcerptSentence`·`excerptParts`·`citationPdfTarget` 은 이 파일만 내보낸다(Nuxt 자동 import 중복 없음 — dev `da80f23` 에서 `grep -rn "export .*\(NGRAM_N\|excerptSentences\|ngramOverlap\|bestExcerptSentence\|excerptParts\|citationPdfTarget\)" frontend/utils frontend/composables` 빈 출력). 정규식 상수(`SENTENCE_SPLIT`·`SENTENCE_SPLIT_KEEP`·`MARKERS`·`NOISE`)와 도우미 `grams`, S3 검토 반영의 상투구 목록(`BOILERPLATE`·`BOILERPLATE_GRAMS` — 파트 S 메모 12)은 내보내지 않는다. 3차 검토 반영의 `citedClaims` 는 내보내고(`frontend/` 에 같은 이름 없음 — `grep -rn "export .*citedClaims" frontend/utils frontend/composables frontend/components` 는 이 파일 한 줄), 그 정규식·상수(`CITE_GROUP`·`CITE_ID`·`CLAUSE_SPLIT`·`CLAUSE_EDGE`·`CLAIM_MIN_GRAMS`)와 도우미 `contentGrams` 는 내보내지 않는다.
- **앞 Task 뒤 기준:** `types/work.ts` 는 A3(`SectionGen`·`Outline.auto`·`ProposalView.section_gens`)·X3(`Outline.background`·`OutlinePut.background`·basis `question`)이 먼저 고친다 — 이 Task 는 그 Task 들이 건드리지 않는 `// ── 요청 본문 ──` 머리 줄(`:257`) 바로 위에 새 타입을 넣는다. `useResearchWork.ts` 는 이 Task 가 06e 에서 처음 고친다(K7 은 뒤 — K7 의 `regenerateTopics` 는 `generateTopics` 바로 뒤에 들어가 이 Task 의 자리(`retryGeneration` 뒤)와 겹치지 않는다).
- 정규식의 뒤보기(`(?<=…)`)는 이미 화면 코드에 있다(`figureMarkers.ts:20` 의 `NUMBER`) — 같은 브라우저 지원 범위다.
- 고치는 두 파일(`types/work.ts`·`useResearchWork.ts`)은 CRLF 다 — Edit 도구로 고친다.

**Files:**
- Modify: `frontend/types/work.ts` (`// ── 요청 본문 ──` :257 바로 위)
- Modify: `frontend/composables/useResearchWork.ts` (type import `SectionPut,` :24 아래, `retryGeneration` :88-89 뒤)
- Create: `frontend/utils/citationEvidence.ts`
- Test: `frontend/tests/unit/citationEvidence.test.ts` (새 파일)

기준선(R1 적용 뒤 — 이 Task 는 그 사슬과 독립이라 순서만 뒤다): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 를 +1 파일·+12 한다(dev `da80f23` 만 놓고 잰 값: 전체 `40 files / 732` → `41 files / 744` — 통합 사본 실측).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/citationEvidence.test.ts` (새 파일, 전체):

```ts
// frontend/tests/unit/citationEvidence.test.ts
import { describe, expect, it } from "vitest";
import type { SectionSource } from "~/types/work";
import {
  NGRAM_N,
  bestExcerptSentence,
  citationPdfTarget,
  excerptParts,
  excerptSentences,
  ngramOverlap,
} from "~/utils/citationEvidence";

const EXCERPT =
  "연구 대상은 농촌 노인 300명이다. 가족 지지가 높은 노인일수록 우울 점수가 낮았다.  배우자 유무는 차이가 없었다!";
const CITED = "가족 지지가 높을수록 노인의 우울이 낮다고 보고되었다 [E1].";

function source(excerpt: SectionSource["excerpt"]): SectionSource {
  return { cnts_id: "KCI_A", abstract: "초록", excerpt };
}

describe("excerptSentences·ngramOverlap", () => {
  it("문장 끝(. ! ? 。) 뒤 공백에서 나누고 앞뒤 공백·빈 조각은 버린다", () => {
    expect(excerptSentences(EXCERPT)).toEqual([
      "연구 대상은 농촌 노인 300명이다.",
      "가족 지지가 높은 노인일수록 우울 점수가 낮았다.",
      "배우자 유무는 차이가 없었다!",
    ]);
    expect(excerptSentences("  첫 문장。둘째 문장? 셋째  ")).toEqual(["첫 문장。둘째 문장?", "셋째"]);
    expect(excerptSentences("   ")).toEqual([]);
  });

  it("서로 다른 글자 2-gram 가운데 겹친 수 — 공백·문장부호·대소문자·전각은 보지 않는다", () => {
    expect(NGRAM_N).toBe(2);
    // '가족' '족지' '지지' 셋이 겹친다 — 띄어쓰기가 달라도 같다
    expect(ngramOverlap("가족 지지", "가족지지가")).toBe(3);
    expect(ngramOverlap("ＣＳＲ 성과", "csr, 성과!")).toBe(ngramOverlap("csr성과", "csr성과"));
    expect(ngramOverlap("가", "가")).toBe(0);                 // n 보다 짧으면 n-gram 이 없다
    expect(ngramOverlap("노인 우울", "도서관 이용")).toBe(0);
  });

  it("[E#]·[F#] 표기는 세지 않는다", () => {
    expect(ngramOverlap("[E1] [F2]", "[E1] [F2]")).toBe(0);
    expect(ngramOverlap("우울 [E12].", "우울")).toBe(1);
  });
});

describe("bestExcerptSentence — 인용 문장과 가장 많이 겹치는 대목 문장", () => {
  it("가장 많이 겹친 문장의 번호", () => {
    expect(bestExcerptSentence(CITED, EXCERPT)).toBe(1);
  });

  it("겹친 수가 같으면 앞 문장", () => {
    expect(bestExcerptSentence("노인 우울", "노인 복지. 우울 증상. 노인 건강.")).toBe(0);
  });

  it("겹침이 없으면 null", () => {
    expect(bestExcerptSentence("도서관 이용", EXCERPT)).toBeNull();
    expect(bestExcerptSentence(CITED, "")).toBeNull();
  });

  it("마커는 세지 않는다 — 대목에 같은 [E1] 이 있어도 고르지 않는다", () => {
    expect(bestExcerptSentence("[E1] [E2].", "다른 말이다 [E1]. 또 다른 말 [E2].")).toBeNull();
  });
});

describe("excerptParts", () => {
  it("가장 많이 겹친 문장만 표시하고, 조각을 이으면 원문 글자 그대로다", () => {
    const parts = excerptParts(EXCERPT, CITED);
    expect(parts).toEqual([
      { text: "연구 대상은 농촌 노인 300명이다. ", mark: false },
      { text: "가족 지지가 높은 노인일수록 우울 점수가 낮았다.", mark: true },
      { text: "  배우자 유무는 차이가 없었다!", mark: false },
    ]);
    expect(parts.map((p) => p.text).join("")).toBe(EXCERPT);
  });

  it("겹치는 문장이 없으면 표시 없이 한 조각, 앞뒤 공백도 남긴다", () => {
    expect(excerptParts(" 다른 이야기. 또 다른 이야기 ", "노인 우울")).toEqual([
      { text: " 다른 이야기. 또 다른 이야기 ", mark: false },
    ]);
    expect(excerptParts("", CITED)).toEqual([]);
  });
});

describe("citationPdfTarget", () => {
  it("대목의 쪽(0부터 센 저장값)을 뷰어 쪽으로 열고 대목 이름을 붙인다", () => {
    const target = citationPdfTarget(source({ chunk_id: "KCI_A__0004", page_start: 5, page_end: 7, text: "대목" }), "논문");
    expect(target).toEqual({ cntsId: "KCI_A", title: "논문", page: 6, passages: [{ page: 6, label: "p.6–8" }] });
    const single = citationPdfTarget(source({ chunk_id: "c", page_start: 5, page_end: null, text: "대목" }), "논문");
    expect(single.passages).toEqual([{ page: 6, label: "p.6" }]);
  });

  it("쪽 정보가 0·없음이면 쪽 없이 연다", () => {
    const target = citationPdfTarget(source({ chunk_id: "c", page_start: null, page_end: null, text: "대목" }), "논문");
    expect(target.page).toBeUndefined();
    expect(target.passages).toEqual([{ page: null, label: "쪽 정보 없음" }]);
  });

  it("대목이 없으면(초록만) 논문을 처음부터 연다", () => {
    expect(citationPdfTarget(source(null), "논문")).toEqual({ cntsId: "KCI_A", title: "논문" });
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/citationEvidence.test.ts`
Expected: `FAIL  tests/unit/citationEvidence.test.ts` · `Error: Cannot find module '~/utils/citationEvidence' imported from '…/tests/unit/citationEvidence.test.ts'` · `Test Files  1 failed (1)` · `Tests  no tests`

- [ ] **Step 3: 타입·조회·판단 함수를 더한다**

`frontend/types/work.ts` — `// ── 요청 본문 ──` 머리 줄 바로 위에 인용 근거 타입을 넣는다. old:

```ts
// ── 요청 본문 ──────────────────────────────────────────────
export interface WorkPatch {
```

new:

```ts
// 인용 근거(GET …/sections/{key}/sources) — 그 절을 쓸 때 모델에 넘긴 근거 논문의 초록·원문 대목. 쪽은 0부터 센 저장값
export interface SectionSourceExcerpt {
  chunk_id: string;
  page_start: number | null;
  page_end: number | null;
  text: string;
}

export interface SectionSource {
  cnts_id: string;
  abstract: string;
  // 대목을 읽지 못한 논문(Milvus 실패)은 null — 초록만 보인다
  excerpt: SectionSourceExcerpt | null;
}

// [E#] → 그 번호의 근거
export type SectionSources = Record<string, SectionSource>;

// 보고서 문단에서 누른 인용 칩 — 절 키·문단 id·문장 번호(sentenceFlags 순서)·근거 번호·논문·그 절의 생성·그 문장 글
export interface CitePick {
  key: string;
  pid: string;
  si: number;
  eid: string;
  cntsId: string;
  genId: number;
  sentence: string;
}

// ── 요청 본문 ──────────────────────────────────────────────
export interface WorkPatch {
```

`frontend/composables/useResearchWork.ts` — type import 목록에 한 이름. old:

```ts
  SectionPut,
  TopicCreate,
```

new:

```ts
  SectionPut,
  SectionSources,
  TopicCreate,
```

같은 파일 — `useWorkApi()` 끝에 조회를 더한다. old:

```ts
    retryGeneration: (jobId: string, gid: number) =>
      api<{ gen_id: number }>(`${job(jobId)}/generations/${gid}/retry`, { method: "POST" }),
  };
}
```

new:

```ts
    retryGeneration: (jobId: string, gid: number) =>
      api<{ gen_id: number }>(`${job(jobId)}/generations/${gid}/retry`, { method: "POST" }),
    // 인용 근거 — 문단의 절 gen_id 로 그 생성이 모델에 넘긴 초록·원문 대목을 읽는다(읽기라 예시 연구도 된다)
    getSectionSources: (jobId: string, key: string, gen: number) =>
      api<SectionSources>(`${job(jobId)}/sections/${encodeURIComponent(key)}/sources`, { query: { gen } }),
  };
}
```

`frontend/utils/citationEvidence.ts` (새 파일, 전체):

```ts
// frontend/utils/citationEvidence.ts
// 인용 근거 탭(보고서 단계 오른쪽 패널, D24 A안)의 판단 — 누른 인용 칩의 문장과 그 문장을 쓸 때 모델에 넘긴 원문 대목
// (GET …/sections/{key}/sources 의 excerpt)을 견줘 대목 쪽에서 강조할 문장을 고른다. 리랭커 점수는 쓰지 않는다(대회
// 뒤) — 화면이 글자 n-gram 겹침만 센다(spec §12-4 하이라이트). 본문 쪽 강조는 누른 칩이 든 문장이다(sentenceFlags 의 번호)
import type { OpenPdfPayload } from "~/types/research";
import type { SectionSource } from "~/types/work";
import { citedPdfTarget } from "~/utils/pdfViewer";

// 글자 2-gram — 한국어는 조사·어미가 붙어 낱말 단위로는 같은 말이 잘 겹치지 않는다
export const NGRAM_N = 2;

// 문장 끝(마침표·물음표·느낌표·고리점) 뒤 공백에서 나눈다 — 대목은 원문 그대로라 [E#] 표기가 없다(본문 쪽 sentenceFlags 와 다른 규칙)
const SENTENCE_SPLIT = /(?<=[.!?。])\s+/;
// 같은 자리에서 나누되 사이 공백을 남긴다(excerptParts 가 원문 글자를 하나도 빼지 않게)
const SENTENCE_SPLIT_KEEP = /((?<=[.!?。])\s+)/;
const MARKERS = /\[[EF]\p{Nd}+\]/gu;
// 공백·문장부호·기호는 겹침으로 세지 않는다
const NOISE = /[\s\p{P}\p{S}]/gu;

export function excerptSentences(text: string): string[] {
  return text
    .split(SENTENCE_SPLIT)
    .map((s) => s.trim())
    .filter(Boolean);
}

function grams(text: string, n: number): Set<string> {
  const chars = Array.from(text.normalize("NFKC").replace(MARKERS, "").toLowerCase().replace(NOISE, ""));
  const out = new Set<string>();
  for (let i = 0; i + n <= chars.length; i += 1) out.add(chars.slice(i, i + n).join(""));
  return out;
}

// 두 글의 글자 n-gram(서로 다른 것) 가운데 겹친 수. [E#]·[F#] 표기·공백·문장부호는 빼고, NFKC·소문자로 맞춘 뒤 센다
export function ngramOverlap(a: string, b: string, n: number = NGRAM_N): number {
  const left = grams(a, n);
  let count = 0;
  for (const g of grams(b, n)) if (left.has(g)) count += 1;
  return count;
}

// 인용한 문장과 가장 많이 겹치는 대목 문장의 번호(excerptSentences 순서). 같으면 앞 문장, 모두 0 이면 null
export function bestExcerptSentence(cited: string, excerpt: string): number | null {
  const sentences = excerptSentences(excerpt);
  let best: number | null = null;
  let top = 0;
  for (let i = 0; i < sentences.length; i += 1) {
    const score = ngramOverlap(cited, sentences[i]!);
    if (score > top) {
      top = score;
      best = i;
    }
  }
  return best;
}

// 대목을 그대로 이어 붙인 조각 — 강조할 문장(bestExcerptSentence)만 mark. 조각을 이으면 원문 글자 그대로다
export function excerptParts(excerpt: string, cited: string): { text: string; mark: boolean }[] {
  const best = bestExcerptSentence(cited, excerpt);
  const parts: { text: string; mark: boolean }[] = [];
  const push = (text: string, mark: boolean) => {
    if (!text) return;
    const last = parts[parts.length - 1];
    if (last && last.mark === mark) last.text += text;
    else parts.push({ text, mark });
  };
  let index = 0;
  for (const piece of excerpt.split(SENTENCE_SPLIT_KEEP)) {
    if (!piece.trim()) {
      push(piece, false);
      continue;
    }
    // 문장 앞뒤 공백은 강조 밖에 둔다
    const lead = piece.length - piece.trimStart().length;
    const core = piece.trim();
    push(piece.slice(0, lead), false);
    push(core, index === best);
    push(piece.slice(lead + core.length), false);
    index += 1;
  }
  return parts;
}

// [원문 보기] — 대목이 있으면 그 쪽에서 연다(저장값은 0부터 센다 — citedPdfTarget 이 뷰어 쪽으로 +1, 0 은 쪽 없이).
// 대목이 없으면(초록만) 논문을 처음부터 연다
export function citationPdfTarget(source: SectionSource, title: string): OpenPdfPayload {
  const excerpt = source.excerpt;
  if (!excerpt) return { cntsId: source.cnts_id, title };
  const start = excerpt.page_start ?? 0;
  return citedPdfTarget(source.cnts_id, title, [{ page_start: start, page_end: excerpt.page_end ?? start }]);
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/citationEvidence.test.ts`
Expected: `Test Files  1 passed (1)` · `Tests  12 passed (12)`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files  (Task 앞 + 1) passed` · `Tests  (Task 앞 + 12) passed`(dev `da80f23` 만 놓고 잰 값 `41 passed (41)` · `744 passed (744)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"`
Expected: `2`(기준선의 `queueLine` 두 줄 그대로 — 새 이름이 다른 파일과 겹치지 않는다)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/types/work.ts frontend/composables/useResearchWork.ts frontend/utils/citationEvidence.ts frontend/tests/unit/citationEvidence.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 인용 근거 하이라이트의 판단을 순수 함수로 더한다(D24 인용 근거 A안, spec §12-4 하이라이트). citationEvidence — 대목을 문장 끝 뒤 공백에서 나누고(excerptSentences), 인용한 문장과 대목 문장의 글자 2-gram(서로 다른 것) 겹침을 세어(ngramOverlap — [E#]·[F#] 표기·공백·문장부호는 빼고 NFKC·소문자로) 가장 많이 겹치는 문장을 고른다(같으면 앞, 없으면 null). excerptParts 는 대목을 원문 글자 그대로 조각내 고른 문장만 표시하고, citationPdfTarget 은 대목의 쪽(0부터 센 저장값)을 뷰어 쪽으로 연다(대목이 없으면 처음부터). 인용 근거 조회 타입(SectionSource·SectionSources·CitePick)과 useWorkApi.getSectionSources 를 더한다"
```

---

### Task S4: 인용 칩을 누르면 오른쪽 인용 근거 탭

spec §12-4 '인용 근거 A안' — 보고서(마지막 단계) 문단의 인용 칩을 누르면 화면을 떠나지 않고 오른쪽 패널이 인용 근거 탭으로 열린다(그 논문 카드 + 그 문장을 쓸 때 모델에 넘긴 원문 대목 하이라이트 + [원문 보기] + [이 논문과 대화하기] — 같은 자리가 딥리드 탭으로). '단계 ④ 는 두 탭·[담음] 없음·ProposalStep 이 쥔다', '[원문 보기]는 `[id].vue:74` 의 ProposalStep 에 `@open-pdf`', '닫으면 누른 자리(인용 칩)로 초점 복귀', 패널 열림 emit(정함 30), '딥리서치 보고서의 인용칩 팝오버(`CitationChip.vue`)는 그대로', 뼈대 정함 24(흐르는 글의 칩은 span 그대로).

- **칩(ProposalSection):** 저장된 문단의 칩(06b `:101-109` — 논문 상세로 떠나는 `<a>`)을 `<button type="button" class="wk-psec__cite" :aria-expanded :aria-controls="panelId" :data-cite>` 로 바꾸고, 누르면 `cite` 를 올린다(`CitePick` = 절 키·문단 id·문장 번호 `si`(`sentenceFlags` 순서 — `paragraphViews` 가 이미 나눈 번호)·근거 번호·논문·절의 `gen_id`·그 문장 글 + 누른 요소). 문장 span 에 `wk-psec__sent` 를 달고 `activeCite` 의 문단·문장이면 `is-cited`(본문 쪽 강조). 상세로 떠나는 함수(`detailHref`·`goDetail` 06b `:348-371`)와 그 import(`useDetailLeave`·`detailUrl`·`isPlainClick`·`spotOf`)는 지운다 — 상세 이동은 패널 머리의 [논문 상세 ↗](같은 주소·같은 돌아올 자리)가 맡는다. 흐르는 글(`liveBlocks`, 06b `:32-37`)의 칩은 span 그대로다(정함 24 — 절이 끝나면 문단이 다시 나뉘어 문장 번호가 바뀐다).
- **패널(ProposalStep):** 루트를 `.wk-split`(R4 의 공용 배치 — ReadingStep 과 같은 규칙)으로 감싸고 `<DeepReadPanel panel-id="wk-panel-proposal" :tabs="panelTabs('proposal')">` 를 늘 그리고 `:paper` 로 열고 닫는다(닫힘 = null — R4 의 패널은 paper 가 null 이면 아무것도 그리지 않는다). 인용 근거 탭(슬롯 `sources`)은 새 `CitationSource`, 딥리드 탭은 패널 안 BookChat(R4 — `doc-kind="paper"`·`:store="chatStore"`·`:pdf-links="true"`). 대목은 `getSectionSources(jobId, key, genId)`(Task S3)로 읽고 `${key}#${genId}` 마다 한 번만 부른다(같은 절의 다른 칩은 캐시). 늦게 온 응답은 순번으로 버린다. 패널이 열리고 닫힐 때 `panel` 을 올리고 내려갈 때(`onBeforeUnmount`) false 를 올린다(정함 30 — 연구 화면의 `workPanelOpen`). [원문 보기](대목·BookChat 출처 칩 모두)는 `open-pdf` 로 올려 연구 화면의 `openPdf` 가 연다.
- **CitationSource:** 논문 카드(제목·저자 줄 — R4 의 `panelHead`, 그리고 인용한 문장 — `[E#]`·`[F#]` 표기를 뺀 글. 좁은 화면에서는 패널이 본문을 덮어 본문 쪽 강조가 안 보인다), 대목이 있으면 `excerptParts`(누른 칩의 `eid` 를 셋째 인자로 — S3 3차 검토 반영, 파트 S 메모 12)를 `<mark class="wk-cite__mark">` 로 감싸 보이고 머리에 대목 이름(`citationPdfTarget` 의 `passages[0].label` — 뷰어와 같은 'p.6–8'), 겹치는 문장이 없으면 그렇다는 한 줄, 대목이 없으면 초록 + '원문 대목을 읽지 못해 초록을 보입니다', 조회 중·오류 줄, [원문 보기](`citationPdfTarget`)·[이 논문과 대화하기](`chat` → 같은 패널을 딥리드 탭으로).
- **화면 판단은 Task S3 의 순수 함수**(`excerptParts`·`citationPdfTarget`)와 R4 의 `panelTabs`·`panelHead` 를 쓴다 — 이 Task 는 `.vue` 만 고친다(단위 테스트 없음 — typecheck·build·vitest 전체 그대로).

**알아 둘 것:**
- **선행(Step 1 이 확인한다):** R2(`utils/deepReadSse.ts` 의 `DeepReadMessage`)·R3/R4(`utils/deepRead.ts` 의 `PanelTab`·`PanelPaper`·`panelHead`·`panelTabs`, `components/work/DeepReadPanel.vue` — 뼈대 1-7 의 props `{ panelId; paper; tabs; tab; detailHref; store }`·슬롯 `sources`·emits `close`·`update:tab`·`open-pdf`·`detail`, CSS `.wk-split*`·`.wk-panel*`)·R5(`[id].vue` script 의 `const workPanelOpen = ref(false);` 와 `:73` 의 `@panel` 리스너)·S3(`getSectionSources`·`CitePick`·`citationEvidence`)·X4(ProposalStep 의 `import { paraAnchor } from "~/utils/detailSource";` 한 줄 — Step 4 ④ 가 이 줄에 `detailUrl` 을 더한다)·X5(ProposalSection `STATE_LABELS`·ProposalStep 내보내기 카드). `ProposalSection.vue`·`ProposalStep.vue` 는 A5→X3→X4→X5→R1 이 먼저 고친다.
- **앞 Task 뒤 기준 — 이 Task 가 잡는 old 는 그 Task 들이 건드리지 않는 자리다:** ProposalSection — 저장 문단의 문장 span 여는 줄(06b `:98` — X4 는 이 span 안에 화면낭독용 `(근거 표시 없음)` 만 더한다: 정함 11), 칩 `<a>` 블록(`:101-109`), import 세 곳(`:204-207`·`:226`), props 의 `jobId: string;` 한 줄(`:236` — A5 는 `skipped?` 를 더할 뿐), emits 한 줄(`:238`), '논문 상세로' 블록(`:348-371`). ProposalStep — 템플릿 루트 여는 줄 둘(`:2-3`)과 닫는 줄(`:98-101` 의 `  </section>` · `</template>` · 빈 줄 · `<script setup lang="ts">`), ProposalSection 의 `:job-id="jobId"` 한 줄(06b `:68` — A5 가 `<div class="wk-doc">` 안으로 옮겨 12칸 들여쓰기다), emits 한 줄(`:118`), import 묶음(`:102-115` — 앞 Task 가 더한 import 는 그대로 두고 이름·줄만 더한다), **X4 가 더한 `import { paraAnchor } from "~/utils/detailSource";` 한 줄**(X4 Step 5 — `jumpToReview` 가 쓴다. 이 Task 는 새 detailSource import 를 더하지 않고 이 줄에 `detailUrl` 을 더한다 — 같은 모듈을 두 번 import 하면 `paraAnchor` 가 두 번 선언돼 `TS2300 Duplicate identifier`), script 맨 끝(`</script>` 바로 앞). Edit 가 old 를 못 찾으면 이 글의 이름(블록·속성)으로 자리를 찾아 '교체 후'로 갈음한다.
- **큰 진행 막대(정함 28 — 10-11 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아"):** A5 가 보고서 화면 머리(승인 목차 자리 위)에 그리는 큰 진행 막대(`.wk-rbar`)·머리 목차는 `<section class="wk-proposal">` 안이라 이 Task 가 감싼 뒤에도 본문 칸(`.wk-split__main`)에 남는다 — 패널이 열려도 막대는 본문 칸 폭으로 서서 절이 끝날 때마다 차오르고, 연쇄가 도는 동안에도 이미 쓴 절의 저장 문단 칩은 패널을 연다(쓰는 중인 절의 흐르는 칩은 span 그대로). 막대를 패널 위나 밖으로 옮기지 않는다.
- **들여쓰기:** ProposalStep 은 루트 `<section class="wk-proposal">` 을 `<div class="wk-split">` 로 감싸되 **안의 줄 들여쓰기를 옮기지 않는다** — 감싸개 여는·닫는 줄과 `<section>` 여는·닫는 줄이 같은 두 칸에 선다. 화면 전체 들여쓰기를 옮기면 diff 가 파일 전체가 되고, 뒤의 H3(PDF)가 잡는 old(내보내기 카드의 버튼 줄)가 어긋난다.
- **`jobId` prop:** ProposalSection 의 `jobId` 는 상세 링크(`detailHref`)만 썼다 — 그 함수를 지우며 prop 도 지우고, ProposalStep 의 `:job-id="jobId"` 줄을 새 바인딩 셋(`:active-cite`·`:panel-id`·`@cite`)으로 갈음한다(뼈대 1-7 은 ProposalSection props 를 '더함'만 적었다 — 파트 메모 4).
- **`activeCite` 에 `eid?` 를 더한다:** 뼈대 1-7 의 `{ pid: string; si: number } | null` 만으로는 한 문장에 칩이 둘(`[E1][E2]`)일 때 둘 다 펼침(`aria-expanded="true"`)이 된다 — 누른 칩만 펼침이 되게 선택 필드 `eid?` 를 더한다(파트 메모 3). ProposalStep 은 절 키가 같은 ProposalSection 에만 넘긴다(`activeCite?.key === key ? activeCite : null`).
- **본문 강조를 떼는 때:** 절을 다시 써서 그 절의 `gen_id` 가 누른 칩의 `genId` 와 달라지면 같은 문단·문장 번호가 다른 글을 가리킨다 — `activeCite` 를 null 로 두어 강조와 펼침을 뗀다. 패널의 근거는 그대로 둔다(그 문장을 쓸 때의 입력이고, 카드에 인용한 문장이 남아 있다).
- **토글·초점:** 펼친 칩을 다시 누르면 닫는다(인용 근거 탭일 때 — `aria-expanded` 토글). 닫으면 누른 칩으로 초점을 돌려준다(spec — 닫으면 누른 자리로). 그 사이 보고서를 다시 읽어 칩이 새로 그려졌으면(`isConnected` 가 거짓) `#wk-sec-<key> [data-cite="<pid>:<si>:<eid>"]` 로 같은 자리의 칩을, 절을 다시 쓰는 중이라 문단이 없으면 그 절 제목(`wk-sec-title-<key>` — A5 가 `tabindex="-1"` 를 달았다)을 찾는다. 패널 안 초점 가두기·Esc·열릴 때 제목 초점은 R4 의 몫이다.
- **[논문 상세 ↗]:** 패널 머리의 링크(`detailHref`)는 06b 칩 링크와 같은 주소(`detailUrl(cnts, { kind: "research", job, e: null, s: "proposal" }, { at: paraAnchor(key, pid), y })`)다. 높이(`y`)는 누르는 순간에만 잴 수 있어 링크의 `href`(`panelDetailHref`)는 `y: null` 로 그리고, `onDetail` 이 누르는 순간 누른 칩의 문단(`[data-anchor="<paraAnchor>"]` — 칩이 새로 그려졌어도 앵커로 다시 찾는다)의 화면 높이를 `spotOf` 로 재어 **그 자리를 실은 주소**로 떠난다(06b `goDetail` 의 `detailHref(cnts, pid, spot.y)` 후 `leave(url, spot)` 와 같다). 상세 화면은 연관 논문으로 넘어갈 때 주소의 자리를 그대로 잇고(`relatedDetailUrl`), router.back() 을 못 쓰는 [돌아가기]는 그 자리로 간다(`backTarget`) — 주소에 높이가 없으면 앵커로만 맞춘다. 그냥 누르면(`isPlainClick`) `leave`, Ctrl·Shift 클릭은 높이를 실은 주소로 `href` 를 갈음해 새 탭에 맡긴다(06b 와 같다). 가운데 버튼·메뉴('새 탭에서 열기')는 R4 의 패널이 `click` 에서만 `detail` 을 올려 링크 그대로(문단 앵커만 — 높이 없음)다. 06b 는 `auxclick`·`contextmenu` 에서도 높이를 찍었는데, 그러려면 R4 부품을 고쳐야 해 이 Task 는 하지 않는다(새 탭의 [돌아가기]는 같은 문단에 맞추되 화면 높이는 기본 자리다).
- **패널은 늘 그리고 `paper` 로 연다(닫힘 = null):** R4 의 `DeepReadPanel` 은 `<template v-if="paper">` 로 닫힘을 그리고, 열릴 때의 제목 초점을 `watch(() => props.paper !== null)`(즉시 실행 아님)로 옮긴다(06e-R.md R4 Step 5). `v-if` 로 마운트하면 처음부터 paper 가 있어 제목 초점이 빠진다 — R5 의 ReadingStep 처럼 `v-if` 없이 `:paper="panelPaper"`(패널이 닫히면 null)·`:tab="panel?.tab ?? 'sources'"` 를 넘긴다. 열린 채 다른 칩을 누르면 paper 만 바뀌어 초점은 칩에 남는다(R4 의 규칙 — 이어 누를 수 있게).
- **대화 보관:** `chatStore = new Map<string, DeepReadMessage[]>()` 를 이 단계 화면이 쥔다(정함 20 — 같은 단계 안에서 논문을 오가면 이어지고, 단계를 옮기거나 새로고침하면 비운다). [이 논문과 대화하기]로 바꾼 딥리드 탭은 패널의 `cntsId`(누른 칩의 논문)로 BookChat 을 연다.
- **[이 논문과 대화하기] 뒤 초점:** 이 버튼은 R4 패널의 인용 근거 탭 본문(`<div v-if="tab === 'sources'">` 의 슬롯) 안에 있다 — 누르면 탭이 chat 으로 바뀌며 본문이 DOM 에서 빠져 초점이 body 로 떨어진다. R4 의 Esc 는 `<aside @keydown>` 에서만 듣고 Tab 가두기는 패널 처음·끝 보초가 하므로(body 에서 누른 Tab 은 보초를 거치지 않는다) 그대로 두면 키보드 사용자가 Esc 로 닫지 못하고 서랍·전체 폭(1200px 미만)에서는 Tab 이 패널 밖으로 빠진다(spec §12-4 '초점 가두기·Esc'). 그래서 `openChat` 이 탭을 바꾼 뒤 `nextTick` 에 딥리드 탭 단추(R4 의 id 규칙 `${panelId}-tab-${t}` — `wk-panel-proposal-tab-chat`)로 초점을 옮긴다(탭 방향키로 옮길 때 R4 `onTabKey` 가 하는 것과 같은 자리).
- **예시 연구:** 패널·대화·[원문 보기]는 모두 읽기라 예시 연구에서도 연다(쓰기 버튼이 없다 — 보고서 단계에는 [담음]이 없다).
- **바꾸지 않는 것:** `components/research/CitationChip.vue`(딥리서치 보고서 팝오버), `utils/citations.ts`(`citeLabel` — Q3 범위 S), `.wk-psec__cite` 의 모양(색·모서리 — 버튼 기본값만 지운다).
- 고치는 기존 파일은 모두 CRLF 다 — Edit 도구로 고친다. `[id].vue` 경로의 대괄호는 git 명령에서 따옴표로 감싼다.

**Files:**
- Modify: `frontend/components/work/ProposalSection.vue` (문장 span 여는 줄 :98, 칩 :101-109, import :204-207·:226, props `jobId` :236, emits :238, '논문 상세로' 블록 :348-371)
- Create: `frontend/components/work/CitationSource.vue`
- Modify: `frontend/components/work/ProposalStep.vue` (템플릿 루트 :2-3·:98-101, ProposalSection 바인딩 :68, import :102-115·X4 가 더한 detailSource import 한 줄, emits :118, script 끝)
- Modify: `frontend/pages/research/[id].vue` (:74 ProposalStep 한 줄)
- Modify: `frontend/assets/css/work.css` (표시 줄 `:1231` 위 — R5 묶음 뒤)

기준선(S3·R5 적용 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료(WARN 줄 수 기준선 그대로). 이 Task 는 테스트를 더하지 않는다 — 판단은 Task S3(`citationEvidence`)·R4(`panelTabs`·`panelHead`)의 함수가 이미 테스트한다. 통합 사본 실측(검토 반영 — 처음에는 dev `da80f23` 에 R2·R4·R5 몫만 흉내 낸 사본에서 재서 X4 가 ProposalStep 에 더한 detailSource import 와의 겹침을 보지 못했다): dev `da80f23` 의 프론트에 **A3·A4·A5·X3·X4·X5 를 얹은 검토 사본**(vitest `41 files / 779`)에 R2·R4·R5 몫(`DeepReadMessage`·`PanelTab`·`PanelPaper`·`panelHead`·`panelTabs`, `DeepReadPanel.vue` 의 1-7 계약과 06e-R.md R4 의 닫힘 꼴(`<template v-if="paper">`·열림 초점 watch), `workPanelOpen`)을 흉내 내고 S3 와 이 Task 의 Step 2~6 을 이 글의 old/new 그대로 얹었다 — 갈음 22곳(S3 3·ProposalSection 8·ProposalStep 9·[id].vue 1·work.css 1)의 old 가 모두 한 번씩 맞았고(ProposalStep 은 script 끝 덧붙이기 1 더), typecheck 오류 0(`Duplicated imports` 2 — 기준선 그대로)·`npm run build` 완료(WARN 57 — 기준선과 같다)·vitest `42 files / 791`(S3 의 +1 파일·+12 뿐)을 확인했다. 같은 사본에서 ④ 대신 옛 글(③ 에 `import { detailUrl, paraAnchor } from "~/utils/detailSource";` 를 새로 더함)로 바꾸면 `ProposalStep.vue(235,21)·(237,10): error TS2300: Duplicate identifier 'paraAnchor'` 두 건이 난다. R1(보이는 글·workPhase import 만 고친다)은 이 Task 의 old 를 건드리지 않아 얹지 않았다.

- [ ] **Step 1: 선행을 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && ls components/work/DeepReadPanel.vue && grep -oE "export (function|const|type|interface) (panelTabs|panelHead|PanelPaper|PanelTab)\b" utils/deepRead.ts | sort -u | wc -l && grep -c "export interface DeepReadMessage" utils/deepReadSse.ts && grep -c "const workPanelOpen = ref(false);" "pages/research/[id].vue" && grep -c "getSectionSources" composables/useResearchWork.ts && grep -c 'from "~/utils/detailSource"' components/work/ProposalStep.vue`
Expected: `components/work/DeepReadPanel.vue` 다음 줄마다 `4` · `1` · `1` · `1` · `1`(하나라도 다르면 R2~R5·S3·X4 가 끝나지 않은 것이다 — 그 Task 를 먼저 한다. 마지막 `1` 은 X4 가 ProposalStep 에 더한 `import { paraAnchor } from "~/utils/detailSource";` 한 줄 — Step 4 ④ 가 이 줄에 `detailUrl` 을 더한다)

- [ ] **Step 2: ProposalSection — 칩을 패널 여는 버튼으로**

`frontend/components/work/ProposalSection.vue` — 저장 문단의 문장 span 여는 줄. old:

```vue
              <span :class="{ 'wk-psec__unmarked': s.unmarked }" :title="s.unmarked ? '근거 표시가 없는 문장' : undefined">
```

new:

```vue
              <span
                class="wk-psec__sent"
                :class="{ 'wk-psec__unmarked': s.unmarked, 'is-cited': isActiveSentence(p.id, si) }"
                :title="s.unmarked ? '근거 표시가 없는 문장' : undefined"
              >
```

같은 파일 — 칩. old:

```vue
                  <a
                    v-else-if="part.type === 'cite'"
                    class="wk-psec__cite"
                    :href="detailHref(section.evidence[part.eid] ?? '', p.id, null)"
                    :title="paperTitle(section.evidence[part.eid])"
                    @click="goDetail($event, section.evidence[part.eid] ?? '', p.id)"
                    @auxclick="goDetail($event, section.evidence[part.eid] ?? '', p.id)"
                    @contextmenu="goDetail($event, section.evidence[part.eid] ?? '', p.id)"
                  >{{ citeText(section.evidence[part.eid], part.eid) }}</a>
```

new:

```vue
                  <button
                    v-else-if="part.type === 'cite'"
                    type="button"
                    class="wk-psec__cite"
                    :data-cite="citeKey(p.id, si, part.eid)"
                    :aria-expanded="isOpenCite(p.id, si, part.eid)"
                    :aria-controls="panelId"
                    :title="paperTitle(section.evidence[part.eid])"
                    @click="onCite($event, p.id, si, part.eid, s.text)"
                  >{{ citeText(section.evidence[part.eid], part.eid) }}</button>
```

(`paragraphParts` 는 그 절의 evidence 에 있는 번호만 `cite` 로, 없는 번호는 `badcite` 로 나눈다 — `cite` 칩의 `section.evidence[part.eid]` 는 늘 있다. `si` 는 바깥 `v-for="(s, si) in sentences"` 의 문장 번호다.)

같은 파일 — import 세 곳. old:

```ts
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { Figure, ParaState, ProposalView, SectionPut, WorkState } from "~/types/work";
```

new:

```ts
import type { CitePick, Figure, ParaState, ProposalView, SectionPut, WorkState } from "~/types/work";
```

old:

```ts
import { detailUrl, paraAnchor } from "~/utils/detailSource";
```

new:

```ts
import { paraAnchor } from "~/utils/detailSource";
```

old:

```ts
import { genQueueLine } from "~/utils/queueLine";
import { isPlainClick, spotOf } from "~/utils/restorePosition";
```

new:

```ts
import { genQueueLine } from "~/utils/queueLine";
```

(`paraAnchor` 는 문단 `<li :data-anchor>` 가 그대로 쓴다.)

같은 파일 — props 의 `jobId` 줄을 새 두 prop 으로 갈음한다(A5 의 `skipped?` 등 다른 줄은 그대로). old:

```ts
  jobId: string;
```

new:

```ts
  // 오른쪽 패널이 보이는 인용 — ProposalStep 이 이 절의 것만 넘긴다. 그 문장을 강조하고 그 칩을 펼침으로 둔다
  activeCite?: { pid: string; si: number; eid?: string } | null;
  // 오른쪽 패널의 id — 칩의 aria-controls
  panelId?: string;
```

같은 파일 — emits. old:

```ts
const emit = defineEmits<{ write: []; save: [body: SectionPut]; regenerate: [pid: string]; retry: [genId: number] }>();
```

new:

```ts
const emit = defineEmits<{
  write: [];
  save: [body: SectionPut];
  regenerate: [pid: string];
  retry: [genId: number];
  // 인용 칩 — 누른 칩(초점을 돌려줄 자리)과 함께 올린다
  cite: [pick: CitePick, el: HTMLElement];
}>();
```

같은 파일 — '논문 상세로' 블록을 인용 칩 함수로 갈음한다. old:

```ts
// ── 논문 상세로 — 돌아오면 이 문단에 맞춘다 ───────────────
const { leave } = useDetailLeave();

function detailHref(cnts: string, pid: string, y: number | null): string {
  return detailUrl(
    cnts,
    { kind: "research", job: props.jobId, e: null, s: "proposal" },
    { at: paraAnchor(props.sectionKey, pid), y },
  );
}

function goDetail(e: MouseEvent, cnts: string, pid: string): void {
  if (!cnts) return;
  const at = paraAnchor(props.sectionKey, pid);
  const item = (e.currentTarget as HTMLElement).closest<HTMLElement>("[data-anchor]");
  const spot = item ? spotOf(item, at) : { at, y: null };
  const url = detailHref(cnts, pid, spot.y);
  if (e.type === "contextmenu" || !isPlainClick(e)) {
    (e.currentTarget as HTMLAnchorElement).href = url;
    return;
  }
  e.preventDefault();
  void leave(url, spot);
}
```

new:

```ts
// ── 인용 칩 → 오른쪽 인용 근거 패널(D24 A안 — 패널은 ProposalStep 이 쥔다) ──
// 칩은 저장된 문단에서만 패널을 연다 — 흐르는 글(liveBlocks)의 칩은 span 그대로다: 절이 끝나면 문단이 다시 나뉘어
// 문장 번호가 바뀐다. 논문 상세로 떠나는 길은 패널 머리의 [논문 상세 ↗] 가 맡는다(돌아오는 자리는 이 문단)
function citeKey(pid: string, si: number, eid: string): string {
  return `${pid}:${si}:${eid}`;
}

// 누른 칩이 든 문장 — 본문 쪽 강조(sentenceFlags 의 문장 번호)
function isActiveSentence(pid: string, si: number): boolean {
  return props.activeCite?.pid === pid && props.activeCite.si === si;
}

// 패널이 그 칩의 논문을 보이는 중인가 — 한 문장에 칩이 둘이면 누른 칩만 펼침
function isOpenCite(pid: string, si: number, eid: string): boolean {
  return isActiveSentence(pid, si) && (props.activeCite?.eid ?? eid) === eid;
}

function onCite(e: MouseEvent, pid: string, si: number, eid: string, sentence: string): void {
  const sec = section.value;
  const cntsId = sec?.evidence[eid];
  if (!sec || !cntsId) return;
  emit("cite", { key: props.sectionKey, pid, si, eid, cntsId, genId: sec.gen_id, sentence }, e.currentTarget as HTMLElement);
}
```

남은 상세 링크 흔적이 없는지 본다:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -n "detailHref\|goDetail\|useDetailLeave\|isPlainClick\|spotOf\|detailUrl\|jobId" components/work/ProposalSection.vue`
Expected: 빈 출력

- [ ] **Step 3: CitationSource — 인용 근거 탭 본문**

`frontend/components/work/CitationSource.vue` (새 파일, 전체):

```vue
<!-- frontend/components/work/CitationSource.vue -->
<!-- 오른쪽 패널의 인용 근거 탭 본문(D24 A안) — 인용한 논문 카드 + 그 문장을 쓸 때 모델에 넘긴 원문 대목(가장 많이
     겹치는 문장을 강조) + [원문 보기] + [이 논문과 대화하기]. 조회·패널은 ProposalStep 이 쥐고 이 부품은 그리기만 한다 -->
<template>
  <div class="wk-cite">
    <section class="wk-cite__card" aria-label="인용한 논문">
      <p class="wk-cite__title">{{ head.title }}</p>
      <p v-if="head.byline" class="rs-muted wk-cite__byline">{{ head.byline }}</p>
      <blockquote class="wk-cite__quote"><span class="rs-sr-only">인용한 문장: </span>{{ quote }}</blockquote>
    </section>

    <p v-if="loading" class="rs-muted" role="status">원문 대목을 불러오는 중입니다</p>
    <p v-else-if="error" class="rs-alert" role="alert">{{ error }}</p>
    <section v-else-if="source?.excerpt" class="wk-cite__excerpt" aria-label="모델에 넘긴 원문 대목">
      <p class="wk-cite__heading">
        이 문장을 쓸 때 넘긴 원문 대목<span v-if="pageText" class="rs-muted"> · {{ pageText }}</span>
      </p>
      <p class="wk-cite__text">
        <template v-for="(part, i) in parts" :key="i">
          <mark v-if="part.mark" class="wk-cite__mark">{{ part.text }}</mark>
          <template v-else>{{ part.text }}</template>
        </template>
      </p>
      <p v-if="!marked" class="rs-muted">
        인용한 문장과 겹치는 대목 문장을 찾지 못했습니다 — 대목 전체를 그대로 보입니다.
      </p>
    </section>
    <section v-else-if="source" class="wk-cite__excerpt" aria-label="초록">
      <p class="wk-cite__heading">원문 대목을 읽지 못해 초록을 보입니다</p>
      <p class="wk-cite__text">{{ source.abstract || "초록이 없습니다." }}</p>
    </section>
    <p v-else class="rs-muted">이 인용의 근거 기록을 찾지 못했습니다 — [원문 보기]로 논문을 직접 확인하세요.</p>

    <div class="wk-cite__actions">
      <button type="button" class="rs-btn rs-btn--small" @click="emit('open-pdf', pdfTarget)">원문 보기</button>
      <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="emit('chat')">이 논문과 대화하기</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { OpenPdfPayload } from "~/types/research";
import type { CitePick, PaperMeta, SectionSource } from "~/types/work";
import { citationPdfTarget, excerptParts } from "~/utils/citationEvidence";
import { panelHead } from "~/utils/deepRead";

const props = defineProps<{
  pick: CitePick;
  meta: PaperMeta | null;
  source: SectionSource | null;
  loading: boolean;
  error: string | null;
}>();
const emit = defineEmits<{ "open-pdf": [payload: OpenPdfPayload]; chat: [] }>();

const head = computed(() =>
  props.meta ? panelHead({ cntsId: props.pick.cntsId, meta: props.meta }) : { title: props.pick.cntsId, byline: "" },
);
// 인용한 문장 — 좁은 화면에서는 패널이 본문을 덮어 강조한 문장이 보이지 않는다. [E#]·[F#] 표기는 빼고 보인다
const quote = computed(() => props.pick.sentence.replace(/\s*\[[EF]\d+\]/g, "").trim());
// 누른 칩의 근거 번호를 넘긴다 — 한 문장에 근거가 둘 이상이면 그 칩이 받치는 말로 고른다(S3 3차 검토 반영 — 파트 S 메모 12)
const parts = computed(() =>
  props.source?.excerpt ? excerptParts(props.source.excerpt.text, props.pick.sentence, props.pick.eid) : [],
);
// 겹치는 문장이 없으면(번역·요약해 쓴 문장 등) 강조 없이 대목 전체를 보이고 그렇다고 알린다
const marked = computed(() => parts.value.some((p) => p.mark));
// 대목이 없으면 논문을 처음부터 연다(citationPdfTarget). 근거 기록을 못 찾았을 때도 같다
const pdfTarget = computed<OpenPdfPayload>(() =>
  props.source ? citationPdfTarget(props.source, head.value.title) : { cntsId: props.pick.cntsId, title: head.value.title },
);
// 대목 이름은 뷰어와 같은 글(pageLabel — 'p.6–8'·'쪽 정보 없음')
const pageText = computed(() => (props.source?.excerpt ? (pdfTarget.value.passages?.[0]?.label ?? null) : null));
</script>
```

(`rs-sr-only`·`rs-alert`·`rs-btn--small`·`rs-btn--ghost`·`rs-muted` 는 기존 부품 클래스다 — ProposalSection·ProposalStep 이 같은 이름을 쓴다. `source` 가 null 이고 오류도 조회 중도 아니면 조회 응답에 그 번호가 없는 것이다 — 서버는 절 입력의 번호를 모두 싣으므로 실제로는 칩과 응답의 생성이 어긋났을 때만이다.)

- [ ] **Step 4: ProposalStep — 패널을 쥔다**

`frontend/components/work/ProposalStep.vue` — 템플릿 루트를 `.wk-split` 으로 감싼다(안의 줄 들여쓰기는 옮기지 않는다 — 위 '알아 둘 것'). old:

```vue
<template>
  <section class="wk-proposal" aria-labelledby="wk-proposal-title">
```

new:

```vue
<template>
  <!-- 오른쪽 패널(인용 근거·딥리드)이 열리면 본문 | 패널 2단 — .wk-split 은 ReadingStep 과 같은 공용 배치다 -->
  <div class="wk-split" :class="{ 'is-panel-open': !!panel }">
  <section class="wk-proposal wk-split__main" aria-labelledby="wk-proposal-title">
```

같은 파일 — 템플릿 끝에 패널을 더하고 감싸개를 닫는다. old:

```vue
  </section>
</template>

<script setup lang="ts">
```

new:

```vue
  </section>
  <DeepReadPanel
    :panel-id="PANEL_ID"
    :paper="panelPaper"
    :tabs="PANEL_TABS"
    :tab="panel?.tab ?? 'sources'"
    :detail-href="panelDetailHref"
    :store="chatStore"
    @update:tab="setTab"
    @close="closePanel"
    @open-pdf="emit('open-pdf', $event)"
    @detail="onDetail"
  >
    <template #sources>
      <CitationSource
        v-if="panel?.pick"
        :pick="panel.pick"
        :meta="panelPaper?.meta ?? null"
        :source="panelSource"
        :loading="sourcesLoading"
        :error="sourcesError"
        @open-pdf="emit('open-pdf', $event)"
        @chat="openChat"
      />
    </template>
  </DeepReadPanel>
  </div>
</template>

<script setup lang="ts">
```

같은 파일 — `<ProposalSection …>` 의 `:job-id` 줄을 패널 바인딩 셋으로 갈음한다(A5 의 `:skipped` 등 다른 줄은 그대로. 바인딩의 `key` 는 `v-for="key in writableKeys"` 루프 변수다 — A5 도 이 이름을 그대로 쓴다). A5 가 ProposalSection 을 `<div class="wk-doc">` 안으로 옮겨 이 줄은 12칸 들여쓰기다 — old:

```vue
            :job-id="jobId"
```

new(같은 12칸):

```vue
            :active-cite="activeCite?.key === key ? activeCite : null"
            :panel-id="PANEL_ID"
            @cite="onCite"
```

같은 파일 — emits. old:

```ts
const emit = defineEmits<{ go: [step: WorkStep] }>();
```

new:

```ts
const emit = defineEmits<{
  go: [step: WorkStep];
  // [원문 보기] — 연구 화면의 원문 뷰어(openPdf)가 연다
  "open-pdf": [payload: OpenPdfPayload];
  // 오른쪽 패널이 열렸는지 — 연구 화면이 LNB 를 접는 재료(workPanelOpen)
  panel: [open: boolean];
}>();
```

같은 파일 — import 묶음. 앞 Task(A5·X3·X4·X5)가 더한 import 는 그대로 두고 아래 다섯 곳(①~⑤)만 맞춘다(06b 줄을 old 로 적었다 — 앞 Task 가 같은 줄에 이름을 더했으면 그 줄에 아래 이름만 더한다. ①②③⑤ 의 old 는 A5·X3·X4·X5·R1 뒤에도 글자 그대로 남는 줄이고, ④ 는 X4 가 더한 줄이다):

① `from "vue"` 에 `nextTick`·`onBeforeUnmount`·`shallowRef`·`watch` 가운데 없는 것을 알파벳 순으로 더한다. 06b old:

```ts
import { computed, onMounted, ref } from "vue";
```

new(06b 기준):

```ts
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
```

② 부품 import 두 줄을 알파벳 자리에 넣는다. 06b old:

```ts
import AiFootprintMeter from "~/components/work/AiFootprintMeter.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
```

new:

```ts
import AiFootprintMeter from "~/components/work/AiFootprintMeter.vue";
import CitationSource from "~/components/work/CitationSource.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import DeepReadPanel from "~/components/work/DeepReadPanel.vue";
```

③ `useResearchWork` import 뒤에 상세 이동·원문 타입, `~/types/work` 에 세 이름, 그 뒤에 패널·대화 import. 06b old(A5·X3·X4·X5 는 이 두 줄을 바꾸지 않는다):

```ts
import { useWorkApi, type ResearchWorkHandle } from "~/composables/useResearchWork";
import type { OutlinePut, SectionPut, WorkStep } from "~/types/work";
```

new(06b 기준 — `~/types/work` 줄에 앞 Task 가 더한 이름이 있으면 그대로 두고 `CitePick`·`PaperMeta`·`SectionSources` 만 알파벳 자리에 더한다. `~/utils/detailSource` 는 여기 더하지 않는다 — ④):

```ts
import { useWorkApi, type ResearchWorkHandle } from "~/composables/useResearchWork";
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { OpenPdfPayload } from "~/types/research";
import type { CitePick, OutlinePut, PaperMeta, SectionPut, SectionSources, WorkStep } from "~/types/work";
import { panelTabs, type PanelPaper, type PanelTab } from "~/utils/deepRead";
import type { DeepReadMessage } from "~/utils/deepReadSse";
```

④ X4 가 더한 detailSource import 에 상세 주소 함수를 더한다(새 줄을 더하면 `paraAnchor` 가 두 번 선언돼 `TS2300 Duplicate identifier 'paraAnchor'` — typecheck·build 가 깨진다. 줄의 자리는 X4 가 둔 그대로다). old(X4 Step 5 가 더한 줄):

```ts
import { paraAnchor } from "~/utils/detailSource";
```

new:

```ts
import { detailUrl, paraAnchor } from "~/utils/detailSource";
```

⑤ `researchErrors` import 뒤에 클릭 판별·자리 도우미. old:

```ts
import { httpStatus, versionConflict, workErrorMessage } from "~/utils/researchErrors";
```

new:

```ts
import { httpStatus, versionConflict, workErrorMessage } from "~/utils/researchErrors";
import { isPlainClick, spotOf } from "~/utils/restorePosition";
```

(`workErrorMessage` 는 06b 부터 이미 import 돼 있다 — 대목 조회 오류 문구에 쓴다. 고친 뒤 `grep -c 'from "~/utils/detailSource"' components/work/ProposalStep.vue` 는 그대로 `1` 이다.)

같은 파일 — script 의 맨 끝(`</script>` 바로 앞, 앞 Task 가 둔 마지막 함수 뒤)에 패널 묶음을 더한다:

```ts

// ── 오른쪽 패널 — 인용 근거·딥리드(D24) ─────────────────
// 인용 칩을 누르면 인용 근거 탭으로 열리고, [이 논문과 대화하기]는 같은 자리를 딥리드 탭으로 바꾼다. 보고서 단계에는
// [담음]을 두지 않는다 — 바꾸면 목차가 '다시 맞춤 필요'가 된다(spec §12-4)
interface ProposalPanel {
  cntsId: string;
  tab: PanelTab;
  pick: CitePick | null;
  // 닫으면 초점을 돌려줄 칩
  opener: HTMLElement | null;
}

const PANEL_ID = "wk-panel-proposal";
const PANEL_TABS = panelTabs("proposal");
// 통째로 바꿔 끼운다(shallowRef) — 칩 요소를 반응형으로 감싸지 않는다
const panel = shallowRef<ProposalPanel | null>(null);
// 딥리드 대화 — 이 단계 안에서 논문을 오가면 이어지고, 단계를 옮기거나 새로고침하면 비운다(서버 저장 없음)
const chatStore = new Map<string, DeepReadMessage[]>();
// 인용 근거는 절 생성마다 한 번 읽는다 — 같은 절의 다른 칩은 다시 부르지 않는다
const sourceCache = new Map<string, SectionSources>();
const sources = shallowRef<SectionSources | null>(null);
const sourcesLoading = ref(false);
const sourcesError = ref<string | null>(null);
let sourcesSeq = 0;
const { leave } = useDetailLeave();

const panelPaper = computed<PanelPaper | null>(() => {
  const p = panel.value;
  if (!p) return null;
  // 서지가 없는 논문은 서버 book_meta 와 같이 cnts_id 를 제목 자리에 쓴다
  const meta: PaperMeta = proposal.value?.papers[p.cntsId] ?? {
    title: p.cntsId,
    personal_author: null,
    pub_date: null,
    series_title: null,
  };
  return { cntsId: p.cntsId, meta };
});
const panelSource = computed(() => {
  const pick = panel.value?.pick;
  return pick && sources.value ? (sources.value[pick.eid] ?? null) : null;
});
// 본문 쪽 강조 — 절을 다시 써서 gen_id 가 바뀌면 같은 문장 번호가 다른 글을 가리키므로 강조를 뗀다(패널의 근거는
// 그대로 둔다 — 그 문장을 쓸 때의 입력이다)
const activeCite = computed(() => {
  const pick = panel.value?.pick;
  if (!pick || proposal.value?.sections[pick.key]?.gen_id !== pick.genId) return null;
  return { key: pick.key, pid: pick.pid, si: pick.si, eid: pick.eid };
});
// [논문 상세 ↗] 의 링크 주소 — 높이(y)는 누르는 순간에만 잴 수 있어 링크에는 문단 앵커만 싣는다. 그냥 누르기·Ctrl·Shift
// 클릭은 onDetail 이 그때 잰 높이를 실은 주소로 갈음하고, 가운데 버튼·메뉴는 이 주소 그대로다
const panelDetailHref = computed(() => {
  const p = panel.value;
  return p ? detailUrlOf(p, null) : null;
});

// 연구 화면이 LNB 를 접는 재료 — 단계를 옮기면 이 화면이 내려가며 닫힘을 알린다(연구 화면에 watch(step) 가 필요 없다)
watch(
  () => panel.value !== null,
  (open) => emit("panel", open),
);
onBeforeUnmount(() => emit("panel", false));

function samePick(a: CitePick, b: CitePick): boolean {
  return a.key === b.key && a.pid === b.pid && a.si === b.si && a.eid === b.eid;
}

function onCite(pick: CitePick, el: HTMLElement): void {
  const now = panel.value;
  // 펼친 칩을 다시 누르면 닫는다(aria-expanded 토글)
  if (now?.pick && now.tab === "sources" && samePick(now.pick, pick)) {
    closePanel();
    return;
  }
  panel.value = { cntsId: pick.cntsId, tab: "sources", pick, opener: el };
  void loadSources(pick);
}

// 늦게 온 응답은 버린다 — 그 사이 다른 칩을 눌렀으면 그 칩의 근거가 보여야 한다(받은 것은 캐시에만 남긴다)
async function loadSources(pick: CitePick): Promise<void> {
  const cacheKey = `${pick.key}#${pick.genId}`;
  const seq = ++sourcesSeq;
  sourcesError.value = null;
  const cached = sourceCache.get(cacheKey);
  if (cached) {
    sources.value = cached;
    sourcesLoading.value = false;
    return;
  }
  sources.value = null;
  sourcesLoading.value = true;
  try {
    const got = await api.getSectionSources(props.jobId, pick.key, pick.genId);
    sourceCache.set(cacheKey, got);
    if (seq === sourcesSeq) sources.value = got;
  } catch (e) {
    if (seq === sourcesSeq) sourcesError.value = workErrorMessage(e, "원문 대목을 불러오지 못했습니다");
  } finally {
    if (seq === sourcesSeq) sourcesLoading.value = false;
  }
}

function setTab(tab: PanelTab): void {
  if (panel.value) panel.value = { ...panel.value, tab };
}

// [이 논문과 대화하기] — 같은 자리를 딥리드 탭으로 바꾼다. 누른 버튼은 인용 근거 탭 본문(v-if)과 함께 사라지므로 초점을
// 딥리드 탭 단추로 옮긴다 — body 로 떨어지면 패널의 Esc(aside 의 keydown)·Tab 가두기(처음·끝 보초)가 듣지 못한다
function openChat(): void {
  setTab("chat");
  void nextTick(() => document.getElementById(`${PANEL_ID}-tab-chat`)?.focus());
}

// 닫으면 누른 칩으로 초점을 돌려준다. 그 사이 보고서를 다시 읽어 칩이 새로 그려졌으면 같은 자리의 칩을, 절을 다시
// 쓰는 중이라 문단이 없으면 그 절 제목(tabindex -1)을 찾는다
function closePanel(): void {
  const p = panel.value;
  panel.value = null;
  if (!p) return;
  void nextTick(() => {
    const pick = p.pick;
    const again = pick
      ? (document.querySelector<HTMLElement>(
          `#${CSS.escape(`wk-sec-${pick.key}`)} [data-cite="${CSS.escape(`${pick.pid}:${pick.si}:${pick.eid}`)}"]`,
        ) ?? document.getElementById(`wk-sec-title-${pick.key}`))
      : null;
    (p.opener?.isConnected ? p.opener : again)?.focus();
  });
}

// 상세 주소 — 출처는 이 연구의 보고서 단계, 돌아올 자리는 누른 칩의 문단(06b 칩 링크와 같은 주소)
function detailUrlOf(p: ProposalPanel, y: number | null): string {
  const at = p.pick ? paraAnchor(p.pick.key, p.pick.pid) : null;
  return detailUrl(p.cntsId, { kind: "research", job: props.jobId, e: null, s: "proposal" }, { at, y });
}

// [논문 상세 ↗] — 누르는 순간 누른 칩의 문단 높이를 재어 상세 주소와 이 화면 주소(돌아올 자리)에 함께 싣는다(06b goDetail
// 과 같다 — 상세가 연관 논문으로 넘어가도 높이가 이어져 router.back() 을 못 쓰는 [돌아가기]도 같은 높이로 온다). 칩이 새로
// 그려졌어도 문단은 앵커로 다시 찾는다. 그냥 누르면 떠나고, Ctrl·Shift 클릭은 높이를 실은 주소를 새 탭에 맡긴다
function onDetail(e: MouseEvent): void {
  const p = panel.value;
  if (!p) return;
  const at = p.pick ? paraAnchor(p.pick.key, p.pick.pid) : null;
  const item = at ? document.querySelector<HTMLElement>(`[data-anchor="${CSS.escape(at)}"]`) : null;
  const spot = item && at ? spotOf(item, at) : { at, y: null };
  const url = detailUrlOf(p, spot.y);
  if (!isPlainClick(e)) {
    (e.currentTarget as HTMLAnchorElement).href = url;
    return;
  }
  e.preventDefault();
  void leave(url, spot);
}
```

(`api`·`proposal`·`props.jobId` 는 이 파일에 이미 있다 — `const api = useWorkApi();`·`const proposal = computed(() => state.value.proposal);`. 템플릿이 쓰는 `PANEL_ID`·`PANEL_TABS`·`panel`·`panelPaper`·`panelSource`·`activeCite`·`panelDetailHref`·`chatStore`·`sourcesLoading`·`sourcesError`·`setTab`·`openChat`·`closePanel`·`onCite`·`onDetail` 은 script setup 의 최상위 이름이라 템플릿에서 바로 읽힌다. `panelDetailHref` 가 부르는 `detailUrlOf` 는 함수 선언이라 아래에 있어도 된다. `onDetail` 의 `e.currentTarget` 은 R4 패널의 `<a>` 다 — R4 가 `@click="emit('detail', $event)"` 로 같은 이벤트를 곧바로 올리므로(동기 호출) 처리 중에는 그대로다.)

- [ ] **Step 5: 연구 화면 — [원문 보기]·패널 열림을 잇는다**

`frontend/pages/research/[id].vue` — ProposalStep 줄(`:74` — R5 는 그 위 ReadingStep 줄만 고쳤다). old:

```vue
          <ProposalStep v-else :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" />
```

new:

```vue
          <ProposalStep v-else :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" @open-pdf="openPdf" @panel="workPanelOpen = $event" />
```

(`openPdf`(`:516-519`)는 이미 있고 `workPanelOpen` 은 R5 가 `:514` 뒤에 넣었다 — 이 Task 는 이 한 줄만 고친다. LNB 접기(`AppSidebar :collapsed`·루트 `is-lnb-collapsed`)는 R6(조건부) 또는 06d N8 의 몫이다 — 정함 30.)

- [ ] **Step 6: 스타일 — 칩 버튼·본문 강조·인용 근거 탭**

`frontend/assets/css/work.css` — 표시 줄 바로 위(R5 묶음 뒤)에 이 Task 의 묶음을 더한다. old:

```css
/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

new:

```css
/* ── 보고서 인용 칩 → 오른쪽 인용 근거 탭(Task S4 — D24 A안) ── */
/* 저장된 문단의 칩은 패널을 여는 버튼이다 — 모양은 .wk-psec__cite 그대로 두고 버튼 기본값만 지운다 */
button.wk-psec__cite {
  font-family: inherit;
  vertical-align: baseline;
  border: 0;
  cursor: pointer;
}
button.wk-psec__cite:hover,
button.wk-psec__cite[aria-expanded="true"] {
  color: var(--skx-white);
  background: var(--skx-primary);
}
button.wk-psec__cite:focus-visible {
  outline: 2px solid var(--skx-border-c2);
  outline-offset: 1px;
}
/* 누른 칩이 든 문장 — 형광펜처럼 글줄 아래쪽만 칠한다(근거 없는 문장의 점선 밑줄과 겹쳐도 둘 다 보인다) */
.wk-psec__sent.is-cited {
  background: linear-gradient(transparent 55%, var(--skx-border-c1) 55%);
}
.wk-cite {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.wk-cite__card {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.6rem 0.7rem;
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
}
.wk-cite__title {
  margin: 0;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.wk-cite__byline {
  margin: 0;
  font-size: 0.55rem;
}
.wk-cite__quote {
  margin: 0;
  padding-left: 0.5rem;
  font-size: 0.6rem;
  line-height: 1.6;
  color: var(--skx-ink-2);
  border-left: 2px solid var(--skx-primary);
}
.wk-cite__excerpt {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.wk-cite__heading {
  margin: 0;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.wk-cite__text {
  margin: 0;
  font-size: 0.65rem;
  line-height: 1.75;
  color: var(--skx-ink);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
/* 대목 쪽 강조 — 인용한 문장과 글자가 가장 많이 겹치는 문장 */
.wk-cite__mark {
  padding: 0 0.1rem;
  color: var(--skx-ink);
  background: var(--skx-border-c1);
  border-radius: var(--skx-radius-sm);
  box-shadow: inset 0 -2px 0 var(--skx-primary);
}
.wk-cite__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
/* 고대비 모드는 배경색을 지운다 — 강조한 문장·대목을 테두리로 남긴다 */
@media (forced-colors: active) {
  .wk-psec__sent.is-cited,
  .wk-cite__mark {
    outline: 1px solid CanvasText;
  }
}

/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

(색·모서리는 `--skx-*` 토큰만 읽는다 — `work.css` 머리 규칙. 근거 장부 블록(`:75-166`·`:1215-1220`)은 건드리지 않는다.)

- [ ] **Step 7: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`(슬롯 안 `panel.pick` 은 `v-if="panel?.pick"` 이 좁힌다. 계획 작성 때 통합 사본에서 이 글의 코드를 그대로 얹어 오류 0 을 확인했다 — 템플릿도 검사됨을 일부러 틀린 emit 으로 확인했다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files` / `Tests` 가 이 Task 앞과 같은 수(이 Task 는 테스트를 더하지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep -c "Duplicated imports"`
Expected: `2`(기준선의 `queueLine` 두 줄 그대로 — 새 부품 이름 `CitationSource` 가 다른 파일과 겹치지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff --stat -- frontend/components/research/CitationChip.vue frontend/utils/citations.ts frontend/assets/css/research.css frontend/assets/css/style_skovix.css`
Expected: 빈 출력(딥리서치 보고서 팝오버·`citeLabel`·연구 화면·전역 CSS 는 그대로)

브라우저 확인 항목은 마무리 운영 확인에 넘긴다(이 Task 는 `.vue` 라 단위 테스트하지 않는다):
1. 보고서 화면에서 저장된 문단의 인용 칩을 누르면 오른쪽에 패널이 인용 근거 탭으로 열리고, 그 칩이 든 문장이 형광펜처럼 강조되며 칩이 펼침(진한 칩)이 된다. 같은 칩을 다시 누르면 닫히고 초점이 그 칩으로 돌아온다.
2. 탭 본문: 논문 제목·저자 줄·인용한 문장(표기 없음), '이 문장을 쓸 때 넘긴 원문 대목 · p.n' 과 대목 안 가장 많이 겹치는 문장의 `<mark>` 강조. 대목이 없는 논문(Milvus 를 못 읽은 논문)은 '원문 대목을 읽지 못해 초록을 보입니다'와 초록.
3. [원문 보기] → 원문 뷰어가 대목의 쪽(대목 이름과 같은 쪽)에서 열린다. 뷰어를 닫으면 [원문 보기]로 초점이 돌아온다.
4. [이 논문과 대화하기] → 같은 패널이 딥리드 탭으로 바뀌고 논문 문구('《제목》 논문에 대해 …' — R3)와 논문 프롬프트(S2 — 답이 '이 논문에서는 …'으로 말한다)로 대화한다. 다른 칩의 같은 논문으로 돌아오면 대화가 이어진다(정함 20). 출처 칩 미리보기의 [원문 보기]도 뷰어를 연다. [이 논문과 대화하기]를 키보드(Tab 으로 가서 Enter)로 누르면 초점이 '딥리드' 탭 단추로 가고, 거기서 Esc 로 패널이 닫히며 초점이 누른 칩으로 돌아온다(1200px 미만에서는 Tab 이 패널 밖으로 나가지 않는다). '이 인용 근거가 맞아?'·'이 논문의 참고문헌은?' 처럼 '인용'·'참고문헌'이 든 질문도 끊기지 않고 답이 온다(S2 의 `_book_references`).
5. Esc·닫기·(1200px 미만) 배경 누르기로 닫히고 초점이 누른 칩으로 돌아온다. 1440px 에서 패널이 열리면 LNB 가 접힌다(R6 또는 06d N8 이 단 뒤 — 정함 30). 1200px 미만에서 인용 근거 본문이 넘치면 Tab 이 '인용 근거' 탭 단추 다음에 그 본문으로 가고(방향키로 스크롤된다) 다시 Tab 이면 처음(상세 링크)으로 감기며, 처음에서 Shift+Tab 이면 그 본문으로 온다.
6. [논문 상세 ↗] → 상세 주소에 `at=g-<절 키>-<문단 id>`·`y=<숫자>` 가 실리고, [돌아가기]로 오면 누른 칩의 문단이 누를 때와 같은 화면 높이에 온다. 상세에서 연관 논문을 한 번 거친 뒤 [돌아가기]로 와도 같은 높이다(주소의 자리가 이어진다). Ctrl+클릭은 새 탭으로 열리고(새 탭 주소에도 `y=` 가 실린다) 이 화면은 그대로다. 가운데 버튼·메뉴의 '새 탭에서 열기'는 `at=` 만 실린다(높이 없음 — 알아 둘 것).
7. 쓰는 중인 절(흐르는 글)의 칩은 눌러도 아무것도 하지 않는다(span 그대로). 예시 연구에서도 칩·패널·대화·[원문 보기]가 열린다.
8. 딥리서치 보고서(이어가지 않은 연구)의 인용칩 팝오버는 지금과 같다.
9. [보고서 만들기] 뒤 자동 산출이 도는 동안 앞서 쓴 절의 칩을 눌러 패널을 열어도 큰 진행 막대(A5 — 정함 28)가 본문 칸 머리에 남아 절이 끝날 때마다 차오른다. 1440px·패널 열림에서 막대·퍼센트가 본문 칸 폭 안에 들어온다.

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/components/work/ProposalSection.vue frontend/components/work/CitationSource.vue frontend/components/work/ProposalStep.vue "frontend/pages/research/[id].vue" frontend/assets/css/work.css && git status --short && git commit -m "[Feat] round06e 프론트 — 보고서 인용 칩을 누르면 오른쪽 패널이 인용 근거 탭으로 열린다(D24 인용 근거 A안). 저장된 문단의 칩을 논문 상세로 떠나는 링크에서 패널을 여는 버튼(aria-expanded·aria-controls)으로 바꾸고 누른 칩이 든 문장을 강조한다 — 흐르는 글의 칩은 그대로다. 보고서 화면이 패널을 쥐어(.wk-split, 탭 인용 근거|딥리드, 담음 없음) 인용 근거 탭에 논문 카드·인용한 문장·그 문장을 쓸 때 넘긴 원문 대목(가장 많이 겹치는 문장을 mark)·[원문 보기]·[이 논문과 대화하기]를 보이고(CitationSource), 대목은 절 생성마다 한 번 읽는다. [논문 상세 ↗]는 패널 머리로 옮겨 같은 주소·같은 돌아올 자리(누르는 순간의 문단 높이를 상세 주소에도 싣는다)로 간다. [이 논문과 대화하기]는 초점을 딥리드 탭으로 옮겨 Esc·Tab 가두기가 이어지고, 닫으면 누른 칩으로 초점을 돌려주고, 패널 열림을 연구 화면에 올려(workPanelOpen) [원문 보기]를 연구 화면의 원문 뷰어에 잇는다. 딥리서치 보고서의 인용칩 팝오버는 그대로"
```

---

## 파트 메모 — 뼈대와 다른 점

1. **S1 — 응답의 대목을 네 칸으로 고정하고 글이 빈 대목은 null 로 낸다(`_excerpt`).** 뼈대는 `"excerpt": p.get("excerpt")`(저장값 그대로)였다. 저장 모양이 바뀌거나 다른 키가 끼어도 응답 계약(1-3 의 `{chunk_id, page_start, page_end, text} | null`)이 흔들리지 않게 네 칸만 골라 싣고, 글이 빈 대목은 화면이 '대목 없음 → 초록'으로 그리도록 null 로 둔다. 테스트 `test_maps_each_number_to_the_paper_its_abstract_and_its_excerpt`(다른 키 `score` 를 떼는지)·`test_a_paper_without_an_excerpt_keeps_its_abstract_only`(빈 글 → null)가 고정한다. `section_sources` 의 위치는 뼈대가 정하지 않아 A2 의 `section_gens_of`(`drafts_of` 아래)와 겹치지 않게 `paper_ids` 와 `_reference` 사이로 정했다.
2. **S2 — 테스트 대역은 `_stub_missing_module` 이 아니라 `test_search_chunk_answer_flag.py` 의 `_stubbed_pipeline` 꼴(`_stubbed_book_chat`)이고, 테스트가 하나 더 있다(`test_loader_leaves_sys_modules_as_it_found_them`).** 뼈대는 `test_embed_index_guard.py:17-43` 의 `_stub_missing_module` 과 같은 꼴을 적었다. 그 함수는 `monkeypatch.delitem(…, raising=False)` 로 캐시만 비워, 원래 없던 키(여기서 새로 import 한, 더미 pymilvus·FlagEmbedding 에 묶인 `book_chat`·`embedder`·`indexer`)가 teardown 뒤에도 sys.modules 에 남는다 — 뼈대가 막으려던 '뒤 테스트가 대역을 물려받는' 일이 그대로 난다. 저장소가 이 문제를 고친 꼴(`test_search_chunk_answer_flag.py:24-53` — 새로 올린 모듈을 직접 빼고 원래 항목·부모 속성은 monkeypatch 가 되돌림)을 따르고, 같은 이름의 되돌림 테스트(그 파일 `:56-62`)를 하나 더한다. 뼈대의 fixture 이름 `book_chat(monkeypatch)`·테스트 셋의 이름은 그대로다. 그래서 S2 의 새 파일은 3 이 아니라 5 개다(이 되돌림 테스트 1 + 메모 11 의 `_book_references` 테스트 1 — 백엔드 +6).
3. **S4 — `activeCite` 에 선택 필드 `eid?` 를 더했다**(뼈대 1-7 `{ pid: string; si: number } | null`). 한 문장에 칩이 둘(`[E1][E2]`)이면 문단·문장만으로는 두 칩이 함께 펼침(`aria-expanded="true"`)이 된다 — 누른 칩만 펼침이 되게 했다. 본문 강조(문장)는 `pid`·`si` 만 본다. 선택 필드라 뼈대 모양을 넘기는 호출도 그대로 돈다.
4. **S4 — ProposalSection 의 `jobId` prop 을 지웠다**(뼈대 1-7 은 props 를 '더함'만 적었다). 그 prop 은 지우는 상세 링크(`detailHref`)만 썼다 — 남기면 쓰이지 않는 prop 이 되고, ProposalStep 의 `:job-id="jobId"` 줄을 새 바인딩 셋(`:active-cite`·`:panel-id`·`@cite`)으로 갈음하는 편이 Edit 자리도 하나로 줄어든다.
5. **S4 — 칩에 `data-cite="<pid>:<si>:<eid>"` 를 달고, 닫을 때 초점 복귀를 그것으로 다시 찾는다.** 뼈대는 '닫으면 opener 로 초점'만 적었다. 패널이 열린 사이 보고서를 다시 읽으면(문단 수락·다른 절 생성 완료) `v-for` 가 칩 요소를 새로 그려 쥔 opener 가 문서에서 빠진다 — 같은 자리의 칩, 그것도 없으면(절을 다시 쓰는 중) 그 절 제목(A5 의 `tabindex="-1"`)으로 돌려준다.
6. **S4 — 본문 강조는 절의 `gen_id` 가 누른 칩의 `genId` 와 같을 때만 둔다.** 뼈대에 없는 규칙이다. 절을 다시 쓰면 같은 문단 id·문장 번호가 다른 글을 가리켜 엉뚱한 문장이 강조되므로 강조·펼침을 뗀다. 패널의 근거는 그 문장을 쓸 때의 입력이라 그대로 둔다.
7. **S4 — CitationSource 카드에 인용한 문장(`[E#]`·`[F#]` 표기를 뺀 글)을 더 보인다.** 뼈대는 '논문 카드(제목·byline)'였다. 1200px 미만 서랍·768px 이하 전체 폭에서는 패널이 본문을 덮어 본문 쪽 강조(`is-cited`)가 보이지 않는다 — 대목 강조가 무엇과 겹친 것인지 패널 안에서 읽히게 했다. 근거 기록을 못 찾은 칩(응답에 그 번호가 없음)도 [원문 보기]는 논문 처음부터 열고 한 줄로 알린다.
8. **S4 — 펼친 칩을 다시 누르면 패널을 닫는다(토글).** 뼈대는 여는 동작만 적었다 — `aria-expanded` 를 단 버튼은 다시 누르면 접히는 것이 관례라 인용 근거 탭일 때 닫는다(딥리드 탭으로 바꾼 뒤 같은 칩을 누르면 인용 근거 탭으로 돌아간다).
9. **S4 — CSS 묶음에 1-8 의 이름 밖 선택자를 더했다:** `button.wk-psec__cite`(버튼 기본값 지우기·펼침·초점 모양 — `.wk-psec__cite` 의 모양은 그대로), `.wk-cite__title`·`__byline`·`__quote`·`__heading`·`__text`, `@media (forced-colors: active)`(고대비에서 배경 강조가 사라지면 테두리로). 모두 `wk-cite` 묶음 안이라 다른 Task 의 이름과 겹치지 않는다.
10. **S4 — ProposalStep 의 안쪽 줄 들여쓰기를 옮기지 않는다.** 루트를 `.wk-split` 로 감싸면서 안쪽 화면 전체를 두 칸 들이면 diff 가 파일 전체가 되고 H3 가 잡는 old(내보내기 카드의 버튼 줄)가 어긋난다 — 감싸개와 `<section>` 이 같은 두 칸에 선다. H3 는 이미 'S4 뒤 루트 `.wk-split` 의 마지막 자식으로 `ReportPrint`'를 적었다(06e-H.md) — 패널 다음 자리가 된다.
11. **S2 — 딥리드의 참고문헌 질문이 끊기는 기존 버그를 고친다(검토 반영 — 처음에는 '발견(고치지 않음)'이었다).** `book_chat.py:117-118` 은 참고문헌 의도('참고문헌'·'인용'·'출처' 등 — 부분 문자열)일 때 `(book.extra or {}).get("references", [])` 를 읽는데, 넘어오는 `book` 은 `BookOut` 이라 `extra` 가 없다(`schemas/book.py` — 대신 `references: list[str]` 이 `extra["references"]` 를 싣는다) — `AttributeError: 'BookOut' object has no attribute 'extra'` 로 스트림이 끊긴다(0b51e68 부터). 06e 의 인용 근거 탭 → [이 논문과 대화하기] 장면(spec §12-8 장면 3)에서는 '이 인용 근거가 맞아?'·'출처가 어디야?' 같은 첫 질문이 바로 이 길이라, 뼈대 범위 밖이어도 S2 에 함께 넣었다 — `_book_references(book)`(`getattr` 로 `references` — 속성이 없거나 None 이면 빈 목록)와 테스트 1(백엔드 +1). 계획 머리의 정함 31(06e-frame.md — '고치지 않는다(기본값)'·Z6 은 참고문헌 의도 낱말을 넣지 않는다·완료노트 두 갈래)은 '고친다 — Task S2' 로 맞춰야 한다. 사용자가 고치지 말라면 S2 의 `_book_references`·`:118` 갈음·그 테스트를 빼고 기대 수를 되돌린다(`test_book_chat_prompt.py` 4 · Step 2 `4 failed, 10 passed` · Step 4 `14 passed`·`198 passed` · 전체 `+5`).
12. **S3 — 대목 문장 고르기를 '겹친 2-gram 수가 가장 큰 문장(모두 0 이면 null)'에서 '인용 문장을 덮는 정도가 가장 큰 문장(하한 아래면 null)'으로 바꿨다(quality 검토 반영 — spec §12-4 '제안'의 설계라 사용자 판단 대기).** 뼈대의 겹친 수는 하한도 정규화도 없어, 한국어 대목에서는 어미·흔한 낱말 2-gram('였다'·'하였'·'연구'·'이다')이 거의 늘 겹쳐 null 갈래가 사실상 타지 않았다 — 인용 문장 '선행 연구들은 사회적 자본이 지역 공동체의 회복력에 기여한다고 보고하였다'를 대목 '본 연구는 2019년 전국 패널 자료를 이용하였다. …'와 견주면 무관한 첫 문장이 '연구'·'하였'·'였다' 셋으로 강조되어, S4 가 그 문장을 '이 문장을 쓸 때 넘긴 원문 대목'의 근거처럼 `<mark>` 로 보이고 '겹치는 대목 문장을 찾지 못했습니다' 줄은 나오지 않았다(spec '인용이라는 말을 정확히 쓴다' — 뒷받침을 넘겨 말하지 않는다 — 와 어긋남). 흔한 말을 많이 품은 긴 문장으로도 쏠렸다. 이제 덮는 정도 = 인용 문장 2-gram 가운데 그 문장에도 있는 것의 무게 합 ÷ 인용 문장 2-gram 의 무게 합(0~1), 무게 = 대목 안 IDF `ln((대목 문장 수 + 1) ÷ 그 2-gram 이 나오는 대목 문장 수(대목에 없으면 1))` 이다 — 여러 문장에 두루 나오는 어미·흔한 낱말은 가볍고, 대목이 한 문장이면 그냥 덮는 비율이다. 가장 큰 값이 `EXCERPT_MATCH_MIN = 0.2`(새로 내보내는 이름 — 1-6 에 더함, `frontend/` 에 같은 이름 없음) 아래면 null. → **2차 검토 반영(상투구 무게 0):** 위 '합성 대목 다섯·인용 문장 열다섯으로 맞는 문장 0.26~0.77·무관 0.11 이하'는 상투구가 대목 안에서 되풀이되거나 인용 문장이 긴 예에서만 맞았다. 무게를 대목 하나(4~8문장) 안에서만 세므로 대목에 한 번만 나오는 학술 상투구('것으로 나타났다'·'을 대상으로'·'에 미치는 영향을 분석하였다'·'유의하게')가 오히려 가장 무거운 무게(df=1)를 받아, 내용이 무관한 짧은 인용 문장이 하한을 넉넉히 넘었다 — 대목 '이 연구는 대학생 500명을 대상으로 학업 스트레스가 수면의 질에 미치는 영향을 분석하였다. 구조방정식 모형을 적용한 결과 학업 스트레스는 수면의 질을 유의하게 낮추는 것으로 나타났다. …'에 '노인의 신체활동은 인지 기능 저하를 늦추는 것으로 나타났다' 0.321, '기업의 사회적 책임 활동은 고객 충성도를 유의하게 높이는 것으로 나타났다' 0.324, '중학생을 대상으로 한 연구에서 부모의 양육 태도가 자아존중감에 미치는 영향을 분석하였다' 0.44 로 셋 다 강조되었고, 맞는 문장이 0.18~0.30 에 머무는 경우도 있어 하한이 두 무리를 가르지 못했다(가장 흔한 한국어 논문 문형에서 S4 가 무관한 문장을 '넘긴 원문 대목'의 근거로 보였을 것이다). '어미·흔한 낱말만 겹치는 무관 문장' 테스트도 IDF 덕분이 아니라 그 인용 문장이 길어서(2-gram 약 33개 가운데 3개만 겹침) 통과했다. 그래서 상투구·어미 목록(`BOILERPLATE` — '는 것으로 나타났다'·'것으로 확인되었다' 등 결과 서술, '을 대상으로 한'·'에 미치는 영향을 분석하였다'·'영향을 미치지 않았다', '유의하게'·'본 연구는'·'연구 결과'·'분석 결과', '보고하였다'·'확인되었다' 등, '하였다'·'었다'·'았다'·'에서'·'에 따른' 같은 어미·조사 — 띄어쓰기를 뺀 이어진 2-gram 까지)의 2-gram 은 무게 0 으로 두고(분자·분모 모두에서 빠진다 — 인용 문장이 상투구뿐이면 null), 나머지는 그대로 대목 안 IDF 다. 내용을 가리키는 말('관계'·'효과'·'매개'·'차이')은 넣지 않았다. IDF 범위를 절 응답 전체 대목으로 넓히는 것만으로는 무관 문장이 0.21~0.36 으로 모자랐다(검토자 계산). 초록 꼴 대목 다섯·인용 문장 서른셋(무관 14·맞는 19)으로 다시 재면 무관은 0.13 이하(바꾸기 전 14개 가운데 9개가 0.26~0.46 으로 강조), 맞는 문장은 0.24~0.83(바꾸기 전 하나가 0.18 로 놓침)이다 — 운영 대목으로 재지 않았으므로 Z6 Step 6 에서 무관 문장 강조와 '찾지 못했습니다' 줄의 빈도를 함께 보고, 상투구 목록에 없는 문형('~로 드러났다' 등)으로 무관 문장이 강조되면 목록에 더하거나 하한을 올리고, '찾지 못했습니다' 줄이 잦으면 하한을 낮출지 본다. **남는 한계(사용자 판단 몫):** 글자 2-gram 겹침은 뜻을 보지 않는다 — 같은 주제어를 나누되 결론이 반대인 문장('우울을 낮췄다' ↔ '우울과 무관했다')은 그대로 강조된다. 이 한계를 받아들이면 S4 의 대목 머리·강조 설명을 '근거'가 아니라 '인용한 문장과 가장 비슷한 대목 문장' 류로 낮추는 것도 선택지다(지금 S4 는 탭 이름이 '인용 근거', 대목 머리가 '이 문장을 쓸 때 넘긴 원문 대목'이고 `<mark>` 한 문장을 따로 부르는 글은 없다 — 예를 들어 강조 아래에 '인용한 문장과 가장 비슷한 대목 문장을 표시했습니다' 한 줄을 더하는 식). `ngramOverlap`(겹친 수)은 1-6 계약대로 남기되 고르기에는 더 쓰지 않는다. 테스트: '겹친 수가 같으면 앞 문장'의 입력을 무게가 같은 두 문장('노인 복지. 우울 증상.')으로 바꾸고(옛 입력은 '여러 문장에 나오는 말보다 한 문장에만 나오는 말을 무겁게' 테스트로 남김), 하한·어미만 겹치는 무관 문장 → null·흔한 말을 더 많이 나누는 긴 문장보다 짧은 정답·`excerptParts` 의 무관 대목 → 표시 없음을 더해 citationEvidence 12 → 16. 2차 검토 반영으로 대목에 한 번만 나오는 상투구만 겹치는 짧은 무관 문장 → null(위 반례 셋과 독거노인 대목·패널 대목의 반례 둘)·상투구로만 된 인용 문장 → null·상투구가 섞인 맞는 인용 문장은 그대로 고름(다섯)을 더하고 `excerptParts` 의 무관 대목 → 표시 없음에 상투구 반례 하나를 더해 16 → 19. → **3차 검토 반영(근거가 둘 이상인 문장):** 덮는 정도의 분모가 칩이 든 문장 전체라, 근거가 둘 이상인 문장 — 절 프롬프트가 '문장마다 그 문장을 받치는 근거를 [E#] 표기로'(`research_section_prior.yaml`·`research_section_gap.yaml`) 붙이게 하고 백엔드 픽스처에도 나오는 꼴(`test_research_work_section.py` 의 '[E2] [E7]'·`test_research_proposal_api.py` 의 '[E2] [E9]') — 은 다른 논문 몫의 말이 분모를 키워 논문마다 덮는 정도가 하한 아래로 갈라졌다: '가족 지지는 노인의 우울을 낮추고, 학업 스트레스는 대학생의 수면의 질을 떨어뜨린다 [E1][E2].'는 E1(독거노인 대목)의 맞는 문장이 0.181, '가족과 친구의 지지는 독거노인의 우울을 낮추며 [E1], 대학생에게서는 학업 스트레스가 수면의 질을 낮춘다 [E2].'의 E1 은 0.145 로 null 이었다(잘못된 강조가 아니라 '찾지 못했습니다' 줄로 떨어지는 안전한 쪽 실패지만, 근거를 묶는 선행 연구 절에서는 많은 칩이 강조 없이 나올 수 있었다). 앞 두 차례의 측정 묶음(합성 33개)과 테스트는 모두 근거가 하나인 문장이라 이 갈래를 재지도 고정하지도 않았다. 그래서 `citedClaims(sentence, eid)`(새로 내보내는 이름 — 1-6 에 더함, `frontend/` 에 같은 이름 없음)가 누른 칩의 번호가 받치는 말 후보를 만든다 — 그 번호가 든 마커 묶음(사이에 공백·쉼표·가운뎃점만 있는 [E#] 들 — `[E1][E2]`·`[E1] [E2]`·`[E1], [E2]`. [F#] 는 절을 나누지 않는다) 앞의 절(앞 마커 묶음이나 문장 머리부터 — 같은 번호가 여러 번이면 그 절들을 이은 것과 하나씩), 그리고 묶음에 근거가 둘 이상이면 어느 말이 어느 논문 몫인지 모르므로 그 절을 쉼표·이음 어미('-고'·'-며'·'-면서'·'-지만'·'-으나') 뒤에서 나눈 조각까지다. 상투구 밖 2-gram 이 셋 미만인 후보('선행 연구들 [E1][E2]은 …' 의 '선행 연구들'·머리의 '또한')는 빼고, 남는 것이 없으면(번호가 문장에 없을 때도) 문장 그대로다. `bestExcerptSentence`·`excerptParts` 는 선택 인자 `eid` 를 받아 후보마다 덮는 정도를 재고 가장 큰 값을 그 대목 문장의 값으로 쓴다 — 하한·무게·상투구 목록은 그대로이고, `eid` 가 없거나 근거가 하나인 문장은 후보가 문장 하나라 전과 같다(앞의 합성 33개는 값이 바뀌지 않는다). S4 의 `CitationSource` 는 `excerptParts(…, props.pick.sentence, props.pick.eid)` 로 부른다(S4 의 글·코드 블록을 고쳤다 — 계획과 다른 점). 문장 끝에 몰린 마커를 위해 하한을 근거 수로 나누는 것(0.2 ÷ k)도 재 봤으나 두 근거가 같은 말을 함께 받치는 꼴('노인의 우울은 가족 지지와 친구 지지가 높을수록 낮다 [E1][E2].')에서 무관한 중학생 스마트폰 대목이 '높을수록 … 낮' 만으로 0.150 이 되어 0.1 을 넘었고, 분모에 대목 문장 쪽 덮는 정도를 섞는 것은 짧은 대목 문장이 긴 인용 문장에 쉽게 덮여 택하지 않았다. 합성 측정 — 테스트의 대목 넷(대학생 수면·독거노인·농촌 노인·패널)과 새로 쓴 셋(기업 사회적 책임·유아 놀이·중학생 스마트폰), 근거가 둘 이상인 문장 열(가운데 마커가 있는 넷·끝에 몰린 묶음만 있는 다섯 — 넷은 말을 나눠 받치고 하나는 함께 받친다·같은 번호가 두 번인 하나): 맞는 짝 20개는 문장 전체로 재면 0.130~0.596 이고 8개가 null 이었는데 좁히고 나눈 뒤 0.303~1.0 으로 모두 골랐다(같은 대목에서 연구 목적 문장과 결과 문장이 비슷하게 덮이면 앞의 목적 문장을 고르는 일은 그대로다). 주제가 겹치지 않는 대목과의 짝 89개는 전에 0.150 이하였고, 뒤에는 한 절(같은 절에 붙은 칩 둘)이 0.200 으로 하한에 닿았다 — '독거노인에게는 친구 지지의 효과가 남성에서 더 컸다'가 기업 사회적 책임 대목의 '환경 활동의 효과가 기부 활동보다 컸다'와 '의효·효과·과가·컸다' 넷(상투구 밖 20개 가운데)을 나눈다. 같은 글을 근거가 하나인 문장으로 쓰면 좁히기 전 코드도 0.200 으로 강조하므로, 좁히기가 새 문형을 만든 것이 아니라 근거가 하나인 짧은 문장에 이미 있던 한계('효과가 … 컸다'·'높을수록 … 낮았다' 같은 결과 문형은 내용어가 섞여 상투구 목록에 넣지 않았다)가 가운데 마커의 절에도 걸리게 된 것이다 — 하한을 이 한 예에 맞춰 올리지 않았다(위 '무관 0.13 이하'는 근거가 하나인 33개 묶음의 값이고, 이 새 묶음으로는 성립하지 않는다). 남는 한계: 나누는 자리는 쉼표·이음 어미뿐이라 '-고'로 끝나는 명사('최고 ')에서도 나뉘고(조각은 후보를 늘릴 뿐 절 전체도 후보로 남는다), 마커가 주어 뒤에 붙은 꼴은 문장 전체로 잰다. 테스트: `citedClaims` 다섯(번호 없음·가운데 마커의 절·끝에 몰린 묶음의 조각·같은 번호 두 번·짧은 조각과 없는 번호)과 `bestExcerptSentence` 의 근거가 둘 이상인 문장 다섯(가운데 마커 — 번호 없이는 null 이던 것·끝에 몰린 묶음 — 검토 반례 포함·함께 받치는 꼴·무관 대목은 그대로 null·근거가 하나인 문장은 번호를 넘겨도 같다), `excerptParts` 의 번호 넘김 하나를 더해 19 → 30(바꾸기 전 여덟 it 실패 확인 — 함께 받치는 꼴·무관 대목·근거 하나인 세 it 은 지금 동작을 고정한다). 운영 확인 Z6 Step 6 에 여러 [E#] 가 붙은 문장의 칩을 따로 보는 항목을 더했다. 사용자가 뼈대대로 두라면 `bestExcerptSentence` 를 겹친 수로 되돌리고 `EXCERPT_MATCH_MIN`·`BOILERPLATE`·`citedClaims`·`eid` 인자·새 테스트·바꾼 입력과 S4 의 셋째 인자를 되돌린다. 3차 반영만 되돌리려면 `citedClaims`·`eid` 인자·그 테스트 열하나·S4 의 셋째 인자를 빼면 된다(그러면 근거가 둘 이상인 문장의 칩은 위처럼 상당수 '찾지 못했습니다' 줄로 떨어진다).

---

## 파트 K — 제목 고르기 — 후보 키워드·제목 반영

덮는 spec 항목: §12-4 '제목 고르기(D23)' 가운데 이름 바꾸기(Task R1 몫)를 뺀 전부 — 후보 키워드(상한 10·하한 없음·프롬프트에 개수 없음·일반어 금지 목록·순서·PRESELECT 3·원천 두 가지·논문 키워드 채움률 1회성 측정), 저장(스키마 변경 없음 — 개념 생성 output `{concepts, candidates}`·`research_works.concepts` = 고른 키워드·선택 저장은 기존 `PATCH …/work`·WorkView `concept_candidates`), 카드 시점(주제 행은 이어가기 때, `topic_card` 생성은 개념 반영·취소 때 씨앗 자리마다 한 번만 — 정함 29), 제목 규칙(input `keywords`·프롬프트 `{% if keywords %}` 한 줄·예시 제목·이전 제목 없음), 검사(06c `terms.contains`·재시도 사다리·세 번 놓친 카드 — 정함 17), 하이라이트(`keywordSpans`·공용 고정 예제), [이 키워드로 다시 만들기](새 엔드포인트·[다른 방향]도 지금 키워드·'키워드가 바뀌었습니다'), 칩 UI(토글 칩·출처·편수 배지·옛 연구는 concepts 를 고른 칩으로), §12-11 '키워드 후보 원천'·'키워드 최소 선택 수·직접 더하기'·'고른 카드는 다시 만들지 않음'·'세 번 다 놓친 카드'(정함 14·15·16·17).

순서: Task K1(1회성 측정 — 판정은 마무리) → Task K2(후보 생성) → Task K3(WorkView 후보) → Task K4(카드 입력·제목 규칙·[다른 방향]) → Task K5(카드 시점) → Task K6(다시 만들기 엔드포인트) → Task K7(프론트 순수 함수) → Task K8(화면) → Task K9(제목 검사 — **06c dev 머지 뒤**). 백엔드 줄기(Task K2→Task K6)와 프론트 줄기(Task K7→Task K8)는 1장 계약 모양만 공유한다. Task K9 은 06c 를 기다리는 동안 파트 H(Task H1·Task H2)를 먼저 해도 된다.

이 파트의 테스트 수(샌드박스 실측 — dev `da80f23` 사본에 06c 계획의 `terms.py`·공용 고정 예제 `term_checks.json`(contains 9 사례)을 흉내 내 넣고 Task K1~Task K9 를 차례로 적용): 백엔드 +88(Task K2 +47 · Task K3 +3 · Task K4 +6 · Task K5 +10 · Task K6 +8 · Task K9 +14), vitest +27(Task K7 +18 · Task K9 +9). 파트 K 가 고치는 백엔드 테스트 파일은 06e 에서 이 파트만 고치므로 파일 단위 기대 수는 dev `da80f23` 값에 앞 K Task 를 더한 실측 그대로 적는다. 전체 실행은 'Task 앞 + N'.

---

### Task K1: 논문 키워드 채움률 1회성 측정 — research/round06e-keyword-candidates/

**왜:** spec §12-4 '논문 키워드 채움률은 착수 전에 한 번 잰다(1회성 — `research/round06e-keyword-candidates/`). 낮으면 보조로 둔다'·§12-11 '키워드 후보 원천'(정함 14). 키워드 후보의 논문 쪽 원천(`library_catalog.keyword` 653 $a 를 나눈 것 ∪ `extra.keywords`)이 채택 논문에 얼마나 차 있는지 몰라, 상수 `PAPER_KEYWORD_MIN_N`(논문에만 있는 후보의 최소 편수)을 1 로 둘지 2(보조)로 둘지 정할 근거가 없다. 측정은 운영 DB 를 읽어야 하므로 도구만 지금 만들고 서버 실행·판정 커밋은 마무리에서 한다(Task K2 는 기본값 1 로 구현한다). 1회성이라 `research/` 에 스크립트와 산출물을 함께 둔다(CLAUDE.md §1).

**Files:**
- Create: `research/round06e-keyword-candidates/measure.py`
- Create: `research/round06e-keyword-candidates/README.md`
- Create(서버 실행 산출물, 마무리에서 커밋): `research/round06e-keyword-candidates/out/fill_rate.md`

**알아 둘 것:**
- **읽기 전용** — SELECT 만, 트랜잭션을 `SET TRANSACTION READ ONLY` 로 열고 `statement_timeout` 120초. DB 주소는 `core.config` 의 `DATABASE_URL_SYNC`(`postgresql://…` — psycopg2, 앱 이미지 `requirements.txt:13` 에 있다). 뼈대가 적은 `DATABASE_URL` 은 asyncpg URL(`postgresql+asyncpg://`)이라 동기 엔진에 쓸 수 없다(파트 메모).
- **SQL 이 피할 함정**(README '판정' 칸에도 적는다): 함정 10 — `extra->'keywords'` 가 '비지 않음'은 jsonb `?` 로 세지 않는다(빈 배열이 '있음'으로 든다). `jsonb_typeof(…) = 'array'` 이고 `jsonb_array_length(…) > 0` 일 때만 센다 — 길이는 `CASE` 안에서만 부른다(배열이 아닌 값에 부르면 오류이고 Postgres 는 AND 의 계산 순서를 보장하지 않는다). `keyword` 칼럼은 `keyword IS NOT NULL AND btrim(keyword) <> ''`. 함정 11 — ③ 원문 표본은 `ORDER BY random() LIMIT 20`. ② 의 '최근 20건'은 표본이 아니라 대상의 정의(시연·실사용에 가까운 최근 연구)라 `ORDER BY created_at DESC LIMIT 20` 그대로 두고 README 에 그 뜻을 적는다. `CAST(… AS jsonb)` 로 쓴다(함정 7 — `text()` 안에서 `::` 캐스트를 피한다).
- 판정: ② ≥ 50% → `PAPER_KEYWORD_MIN_N = 1`, < 50% → 2. ③ 으로 `split_catalog_keywords` 구분자(`[;,]`)를 확인한다. 서버 실행·결과 반영은 마무리(뼈대 §7-1).
- 서버 경로: `research/` 는 앱 이미지에 없다(함정 4) — 폴더를 `/data/nl-lib/data/round06e-keyword-candidates/`(컨테이너 안 `/app/data/…`)로 옮기고 `docker exec -e PYTHONPATH=/app nl-lib-fastapi …`. 개발 PC 에서는 `--dry-run`(SQL 만 찍는다)만 돌린다 — 운영 DB 에 붙지 않는다.
- pytest 대상이 아니다(1회성). `--dry-run` 출력으로 확인한다.

- [ ] **Step 1: 측정 스크립트를 쓴다**

`research/round06e-keyword-candidates/measure.py` (새 파일, 전체):

```python
r"""measure.py — 논문 키워드 채움률 1회성 측정 (round06e Task K1 — spec §12-4 '논문 키워드 채움률은 착수 전에 한 번 잰다')

06e 의 키워드 후보는 LLM 후보(개념 생성을 넓힘)에 채택 논문의 소장 키워드 문서 빈도를 코드로 합친다(계획 06e 정함 14).
논문 쪽 원천은 library_catalog.keyword(653 $a — 구분자로 이은 글)와 extra.keywords(적재 enrichment 가 뽑은 배열)다.
채움률이 낮으면 논문 키워드는 보조로만 둔다 — 2편 이상 겹친 것만 후보에 든다(keywords.PAPER_KEYWORD_MIN_N = 2).

읽기 전용이다 — SELECT 만 하고 트랜잭션을 READ ONLY 로 연다. 출력은 markdown 표(stdout).
  ① 소장 논문 전체(doc_type='paper')의 653 키워드·추출 키워드·둘 중 하나가 있는 비율
  ② 최근 이어간 연구 RECENT_WORKS 건(research_works 최근순)의 채택 논문(research_reading origin evidence) 중
     키워드가 하나라도 있는 비율과 연구별 분포 — 판정의 기준
  ③ 653 키워드 원문 표본 SAMPLE_SIZE 개(ORDER BY random() — 함정 11) — 구분자 확인용
  ④ ② 의 연구별로 서로 다른 키워드 수(1편 이상·2편 이상) — 판정이 2 일 때 남는 후보 수를 가늠한다
함정 10: extra->'keywords' 를 jsonb ? 로 세지 않는다(빈 배열이 '있음'으로 든다) — 배열이고 길이가 0 보다 클 때만 센다.
Postgres 는 AND 의 계산 순서를 보장하지 않아 jsonb_array_length 는 CASE 안에서만 부른다(배열이 아니면 오류).

실행(서버 — research/ 는 앱 이미지에 없다, 함정 4): README.md '실행'. 개발 PC 에서는 --dry-run 만 돌린다(SQL 만 찍는다).
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))   # 개발 PC 에서 돌릴 때 — 컨테이너는 PYTHONPATH=/app

RECENT_WORKS = 20     # 판정 대상 — 표본이 아니라 '시연·실사용에 가까운 최근 연구'라는 정의다(ORDER BY created_at DESC 그대로)
SAMPLE_SIZE = 20      # 653 키워드 원문 표본 — 구분자를 눈으로 본다(ORDER BY random())
THRESHOLD = 0.5       # ② 의 비율이 이 값 이상이면 PAPER_KEYWORD_MIN_N = 1, 아래면 2

HAS_CATALOG = "(lc.keyword IS NOT NULL AND btrim(lc.keyword) <> '')"
HAS_EXTRACTED = ("(CASE WHEN jsonb_typeof(lc.extra->'keywords') = 'array' "
                 "THEN jsonb_array_length(lc.extra->'keywords') ELSE 0 END > 0)")
HAS_ANY = f"({HAS_CATALOG} OR {HAS_EXTRACTED})"
RECENT = f"""
recent AS (
  SELECT id, created_at FROM research_works
  WHERE deleted_at IS NULL AND is_example = false
  ORDER BY created_at DESC
  LIMIT {RECENT_WORKS}
)"""

SQL_CATALOG = f"""
SELECT count(*) AS papers,
       count(*) FILTER (WHERE {HAS_CATALOG}) AS catalog_keyword,
       count(*) FILTER (WHERE {HAS_EXTRACTED}) AS extracted_keywords,
       count(*) FILTER (WHERE {HAS_ANY}) AS any_keyword
FROM library_catalog lc
WHERE lc.doc_type = 'paper'"""

SQL_RECENT = f"""
WITH {RECENT.strip()}
SELECT CAST(r.id AS text) AS work_id, r.created_at,
       count(rr.cnts_id) AS papers,
       count(rr.cnts_id) FILTER (WHERE {HAS_ANY}) AS any_keyword
FROM recent r
LEFT JOIN research_reading rr ON rr.work_id = r.id AND rr.origin = 'evidence'
LEFT JOIN library_catalog lc ON lc.cnts_id = rr.cnts_id
GROUP BY r.id, r.created_at
ORDER BY r.created_at DESC"""

SQL_SAMPLE = f"""
SELECT lc.cnts_id, lc.keyword
FROM library_catalog lc
WHERE lc.doc_type = 'paper' AND {HAS_CATALOG}
ORDER BY random()
LIMIT {SAMPLE_SIZE}"""

SQL_OVERLAP = f"""
WITH {RECENT.strip()},
words AS (
  SELECT rr.work_id, rr.cnts_id, lower(btrim(k.word)) AS word
  FROM recent r
  JOIN research_reading rr ON rr.work_id = r.id AND rr.origin = 'evidence'
  JOIN library_catalog lc ON lc.cnts_id = rr.cnts_id
  CROSS JOIN LATERAL regexp_split_to_table(coalesce(lc.keyword, ''), '[;,]') AS k(word)
  UNION
  SELECT rr.work_id, rr.cnts_id, lower(btrim(k.word))
  FROM recent r
  JOIN research_reading rr ON rr.work_id = r.id AND rr.origin = 'evidence'
  JOIN library_catalog lc ON lc.cnts_id = rr.cnts_id
  CROSS JOIN LATERAL jsonb_array_elements_text(
    CASE WHEN jsonb_typeof(lc.extra->'keywords') = 'array' THEN lc.extra->'keywords'
         ELSE CAST('[]' AS jsonb) END) AS k(word)
),
counted AS (
  SELECT work_id, word, count(DISTINCT cnts_id) AS n FROM words WHERE word <> '' GROUP BY work_id, word
)
SELECT CAST(work_id AS text) AS work_id,
       count(*) AS words_n1,
       count(*) FILTER (WHERE n >= 2) AS words_n2
FROM counted
GROUP BY work_id
ORDER BY work_id"""

QUERIES = (
    ("① 소장 논문 전체의 키워드 채움", SQL_CATALOG),
    (f"② 최근 이어간 연구 {RECENT_WORKS}건의 채택 논문 — 판정 기준", SQL_RECENT),
    (f"③ 653 키워드 원문 표본 {SAMPLE_SIZE}개 — 구분자 확인", SQL_SAMPLE),
    ("④ 연구별 서로 다른 키워드 수(1편 이상·2편 이상)", SQL_OVERLAP),
)


def _cell(value) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[tuple]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _rate(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "—"


def _default_url() -> str:
    from core.config import get_settings     # 컨테이너 env(DB_*)로 만든 동기 URL(psycopg2 — 앱 이미지에 있다)

    return get_settings().DATABASE_URL_SYNC


def report(conn) -> str:
    from sqlalchemy import text

    out: list[str] = ["# round06e 논문 키워드 채움률", ""]
    (papers, catalog, extracted, any_kw), = conn.execute(text(SQL_CATALOG)).all()
    out += [f"## {QUERIES[0][0]}", "", _table(
        ["논문 수", "653 키워드", "추출 키워드", "둘 중 하나", "비율"],
        [(papers, catalog, extracted, any_kw, _rate(any_kw, papers))]), ""]

    rows = conn.execute(text(SQL_RECENT)).all()
    total = sum(r.papers for r in rows)
    with_any = sum(r.any_keyword for r in rows)
    out += [f"## {QUERIES[1][0]}", "", _table(
        ["연구", "이어간 시각", "채택 논문", "키워드 있음", "비율"],
        [(r.work_id, r.created_at, r.papers, r.any_keyword, _rate(r.any_keyword, r.papers)) for r in rows]
        + [("합계", "", total, with_any, _rate(with_any, total))]), ""]
    if total:
        decided = 1 if with_any / total >= THRESHOLD else 2
        out += [f"판정: 비율 {_rate(with_any, total)} — 기준 {THRESHOLD:.0%} {'이상' if decided == 1 else '미만'} "
                f"→ PAPER_KEYWORD_MIN_N = {decided}", ""]
    else:
        out += ["판정: 이어간 연구의 채택 논문이 없다 — 기본값 PAPER_KEYWORD_MIN_N = 1 그대로", ""]

    sample = conn.execute(text(SQL_SAMPLE)).all()
    out += [f"## {QUERIES[2][0]}", "", _table(["cnts_id", "keyword 원문"], [tuple(r) for r in sample]), ""]

    overlap = conn.execute(text(SQL_OVERLAP)).all()
    out += [f"## {QUERIES[3][0]}", "", _table(
        ["연구", "키워드(1편 이상)", "키워드(2편 이상)"], [tuple(r) for r in overlap]), ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="논문 키워드 채움률 1회성 측정(읽기 전용)")
    ap.add_argument("--dry-run", action="store_true", help="DB 에 붙지 않고 SQL 만 찍는다")
    ap.add_argument("--db", default=None, help="동기 DB URL(postgresql://…) — 없으면 core.config 의 DATABASE_URL_SYNC")
    args = ap.parse_args(argv)
    # 표는 파일로 받아 커밋한다(out/fill_rate.md) — Windows 콘솔(cp949)·python -I(PYTHONIOENCODING 무시)에서도 UTF-8 로 쓴다
    sys.stdout.reconfigure(encoding="utf-8")
    if args.dry_run:
        for title, sql in QUERIES:
            print(f"-- {title}\n{sql.strip()};\n")
        return 0
    from sqlalchemy import create_engine, text

    engine = create_engine(args.db or _default_url())
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout = '120s'"))
            print(report(conn))
            conn.rollback()
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: README 를 쓴다**

`research/round06e-keyword-candidates/README.md` (새 파일, 전체):

````markdown
# round06e — 논문 키워드 채움률 (1회성)

06e '제목 고르기'(spec D23·§12-4)의 키워드 후보는 두 원천을 코드로 합친다(계획 06e 정함 14 — §12-11 '키워드 후보 원천' 권고).

1. **LLM 후보** — 키워드 생성(kind `concepts`, gemma)이 원 질문·하위질문에서 중요한 순서대로 낸 키워드.
2. **채택 논문의 소장 키워드** — 이어가기 때 FastAPI 가 채택 논문의 `library_catalog.keyword`(653 $a — 구분자로 이은 글)를 나눈 것과 `extra.keywords`(적재 enrichment 가 뽑은 배열)의 **문서 빈도**(그 키워드를 가진 논문 수)를 세어 생성 input 의 `paper_keywords` 에 싣는다(`app/services/research_work/keywords.py` 의 `paper_keyword_counts`).

논문 쪽 원천이 얼마나 차 있는지 몰라 착수 전에 한 번 잰다(spec §12-4 '논문 키워드 채움률은 착수 전에 한 번 잰다 — 낮으면 보조로 둔다').

## 판정 규칙

- 기준은 ② **최근 이어간 연구 20건의 채택 논문 중 키워드(653 또는 추출)가 하나라도 있는 논문의 비율**이다. 소장 전체(①)가 아니라 실제로 후보가 될 논문(채택 근거)을 본다.
  - **50% 이상** → `PAPER_KEYWORD_MIN_N = 1` — 논문에만 있는 후보도 1편부터 후보에 든다(구현 기본값).
  - **50% 미만** → `PAPER_KEYWORD_MIN_N = 2` — 보조로만: 2편 이상 겹친 논문 키워드만 후보에 든다(LLM 후보와 겹친 것은 편수와 상관없이 출처 'AI · 논문 n편'으로 남는다).
- ③ 의 원문 표본으로 `split_catalog_keywords` 의 구분자(기본 `;`·`,`, NFKC 뒤 앞뒤 공백 정리)가 맞는지 본다. 다른 구분자(예: `/`·`|`)가 보이면 그 정규식을 고친다.
- ④ 는 판정이 2 일 때 연구마다 남는 논문 후보 수를 가늠하는 참고다(서버 SQL 의 `lower(btrim())` 은 코드의 `keyword_key`(NFKC → 공백 제거 → casefold)보다 느슨하다 — 띄어쓰기만 다른 같은 말은 둘로 센다).

### SQL 이 피하는 함정

- **함정 10** — `extra->'keywords'` 가 '비지 않음'은 jsonb `?`(키 있음)로 세지 않는다. 빈 배열이 '있음'으로 든다. `jsonb_typeof(…) = 'array'` 이고 `jsonb_array_length(…) > 0` 일 때만 센다(길이는 `CASE` 안에서만 부른다 — 배열이 아닌 값에 부르면 오류이고, Postgres 는 AND 의 계산 순서를 보장하지 않는다). `keyword` 칼럼은 `keyword IS NOT NULL AND btrim(keyword) <> ''`. ② 의 '키워드가 하나라도 있음'도 같은 두 조건의 OR 이다.
- **함정 11** — ③ 의 원문 표본은 정렬 걸린 `LIMIT` 이 아니라 `ORDER BY random() LIMIT 20` 이다(앞부분 편중을 피한다).
- ② 의 '최근 20건'은 표본이 아니라 **대상의 정의**(시연·실사용에 가까운 최근 연구)라 `ORDER BY created_at DESC LIMIT 20` 그대로 둔다. 예시 연구(`is_example`)·지운 연구(`deleted_at`)는 뺀다.

## 실행

읽기 전용이다 — 트랜잭션을 `READ ONLY` 로 열고 `statement_timeout` 120초를 건다. 개발 PC 에서는 SQL 만 찍어 본다(운영 DB 에 붙지 않는다).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && python -I research/round06e-keyword-candidates/measure.py --dry-run
```

서버(사용자, root 셸 — `research/` 는 앱 이미지에 없다, 함정 4): 이 폴더를 `/data/nl-lib/data/round06e-keyword-candidates/` 로 옮긴 뒤(일반 계정 홈으로 받은 뒤 root 셸에서 `cp`)

```bash
mkdir -p /data/nl-lib/data/round06e-keyword-candidates/out
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06e-keyword-candidates/measure.py \
  > /data/nl-lib/data/round06e-keyword-candidates/out/fill_rate.md
```

DB 주소는 컨테이너 env(`DB_*`)로 만든 `DATABASE_URL_SYNC`(psycopg2)다. 끝나면 서버의 `out/fill_rate.md` 를 이 폴더로 가져와 커밋하고 아래 '결과'를 채운다.

## 결과

(서버 실행 뒤 채운다 — `out/fill_rate.md` 의 ①·② 합계 줄·판정 줄·③ 에서 본 구분자, 그리고 그에 따른 결정: `PAPER_KEYWORD_MIN_N` 을 1 로 둘지 2 로 바꿀지, `split_catalog_keywords` 구분자를 고칠지. 바꾸면 그 커밋 해시를 적는다.)
````

- [ ] **Step 3: dry-run 으로 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && python -I research/round06e-keyword-candidates/measure.py --dry-run | grep -c "^-- "`

Expected: `4`(질의 넷의 머리 줄 — `-- ① 소장 논문 전체의 키워드 채움` … `-- ④ 연구별 서로 다른 키워드 수(1편 이상·2편 이상)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && python -I research/round06e-keyword-candidates/measure.py --dry-run | head -3`

Expected:

```text
-- ① 소장 논문 전체의 키워드 채움
SELECT count(*) AS papers,
       count(*) FILTER (WHERE (lc.keyword IS NOT NULL AND btrim(lc.keyword) <> '')) AS catalog_keyword,
```

- [ ] **Step 4: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add research/round06e-keyword-candidates/measure.py research/round06e-keyword-candidates/README.md && git status --short && git commit -m "[Chore] round06e — 논문 키워드 채움률 1회성 측정 도구(research/round06e-keyword-candidates/)를 더한다. 최근 이어간 연구 20건의 채택 논문 가운데 653 키워드·추출 키워드(extra.keywords)가 하나라도 있는 비율로 키워드 후보의 논문 쪽 하한 PAPER_KEYWORD_MIN_N(50% 이상 1, 미만 2 — 보조)을 정하고, 653 원문 표본으로 구분자를 본다(spec §12-4·§12-11 키워드 후보 원천). 읽기 전용(READ ONLY 트랜잭션·statement_timeout 120초)이고 jsonb 빈 배열을 '있음'으로 세지 않으며(함정 10) 원문 표본은 ORDER BY random()(함정 11). 서버 실행과 판정 커밋은 마무리 — README '실행'"
```

---

### Task K2: 후보 키워드 — 원천 합치기·일반어 거르기·위 3개 미리 선택

**왜:** spec §12-4 '후보 키워드'·'저장'(D23, 정함 14·15). 06b 의 핵심 개념 생성(gemma)은 '2~5개'를 프롬프트로 시켜 일반어가 섞였고('측정 및 평가 · 연구 분야 · 발전 방향' — `round06b-완료노트.md:87`), 개수를 프롬프트에 적으면 모델이 그 수를 채우려 한다(함정 15). 06e 는 이 생성을 '키워드 후보'로 넓힌다 — 모델은 중요한 순서대로 키워드만 내고, 코드가 ① 정리·일반어 거르기 ② 채택 논문의 소장 키워드 문서 빈도와 합치기(출처·편수) ③ 상한 10 자르기 ④ 위 3개 미리 선택을 한다. 생성 종류 이름(`concepts`)·`research_works.concepts`(= 고른 키워드)·PATCH·목차 묶음 배정은 그대로 돈다. 논문 키워드는 이어가기 때 FastAPI 가 읽어 생성 input 에 싣는다(워커는 DB 텍스트만 — §6-3).

**Files:**
- Create: `app/services/research_work/keywords.py`
- Create: `app/tests/test_research_work_keywords.py`
- Modify: `app/services/research_work/concepts.py` (docstring 1-9·import 10-14·상수 16, `concepts_input` 45-53, `_parse` 68-72, `EXECUTOR` 75-83 — `clean_concepts`·`MAX_CONCEPTS` 는 그대로)
- Modify: `app/domains/nl_library/prompts/research_concepts.yaml` (params 주석 3-4, system 8-22)
- Modify: `app/api/research_work.py` (import 35-46, `WorkPatch` 주석 64, `continue_research` 의 개념 생성 넣기 208-211)
- Modify: `app/services/research_work/generate.py` (`Executor.check` 주석 47 — 주석만)
- Test: `app/tests/test_research_work_concepts.py` (import 5-17, `TestCleanConcepts.test_limits` 32-33, `TestConceptsInput` 61-77, `TestPrompt` 91-118, `TestExecutor` 125-155)
- Test: `app/tests/test_research_work_api.py` (import 31-33, `TestContinue` 264-302)
- Test: `app/tests/test_research_work_executor.py` (`TestExecutorFields.test_concepts_marks_an_empty_done_as_retryable` 83-88)
- Test: `app/tests/test_research_work_tasks.py` (`TestDispatch` 261-262·300)

**알아 둘 것:**
- **`keywords.py` 는 순수 모듈이다** — `re`·`unicodedata` 만 import. `concepts.py` 가 이 모듈을 import 하므로 거꾸로 가져오지 않는다(순환). 그래서 글자 상한 `KEYWORD_LEN_MAX = 40` 은 `concepts.MAX_CONCEPT_LEN`(40, 그대로 둔다)과 같은 값을 따로 두고 `TestCleanKeyword.test_limits` 가 둘이 같음을 고정한다.
- 같은 말 판정 `keyword_key` = NFKC → 공백 모두 제거 → casefold — `clean_concepts` 의 중복 열쇠(`"".join(text.split()).casefold()`)와 같다(NFKC 를 앞에 둔다). 일반어 목록 `GENERIC_KEYWORDS` 도 이 열쇠로 견준다 — '연구분야'·'발전  방향'·'선행 연구' 도 걸린다.
- **순서:** LLM 후보를 낸 순서대로(논문에도 있으면 source `both`·n 편수, 없으면 `llm`·0) → 논문에만 있고 `n >= PAPER_KEYWORD_MIN_N` 인 것을 편수 내림차순(같으면 받은 순 — 안정 정렬) → 앞 10개. `paper_keyword_counts` 의 '같은 편수면 처음 나온 순'은 `books` dict 의 순서다 — `BookRepository.get_by_cnts_ids`(`repositories/book.py:26-36`)는 DB 순서로 돌려주므로 **이어가기가 후보(읽기 목록 후보) 순서로 다시 줄 세워 넘긴다**.
- **해석·합치기·검사:** `_parse` 는 `{"llm": [...]}` 만 낸다(키 `keywords`, 06e 전 프롬프트의 `concepts` 키도 읽는다 — 배포 사이에 옛 워커가 넣은 행을 새 워커가 다시 부를 수 있다). `run_generation` 이 `bind` 를 검사 전에 부르므로(`generate.py:87-88`) `_bind` 가 논문 키워드와 합쳐 `{"concepts": 미리 선택, "candidates": 후보}` 를 만들고, `_check` 는 '모델 후보(llm·both)가 하나라도 남았나'를 본다 — 일반어만 낸 답은 내용 검사 미달로 다시 부른다. 끝내 못 얻으면 `_empty` 가 논문 키워드만 후보로 두고 미리 고르지 않는다(`is_empty` 가 참 → [다시] 가능, `apply_result` 는 칩을 건드리지 않는다).
- **`MIN_CONCEPTS` 를 지운다** — 검사가 '모델 후보 하나 이상'이 되어 쓰는 곳이 없다(`api/research_work.py:39` 는 `MAX_CONCEPTS` 만 import). `test_limits` 를 함께 고친다(뼈대 테스트 목록 밖의 ✎ — 파트 메모). '개념 2개 이상' 규칙을 말하던 주석 두 곳(`api/research_work.py:64` `WorkPatch`·`generate.py:47` `Executor.check`)도 함께 고친다(CLAUDE.md §3 — 코드와 어긋난 주석).
- **프롬프트:** 출력 키 `keywords`, 개수·예시를 적지 않는다(함정 15 — '2개 이상 5개 이하' 두 곳을 지운다). 변수는 `question`·`subquestions` 그대로라 `test_template_reads_only_the_question_and_subquestions` 는 그대로 통과한다. `max_tokens: 400` 은 그대로 두고 주석만 고친다(키워드 하나 40자 이내 — 수십 개가 와도 덮는다).
- **이어가기:** `concepts_input(job, paper_keywords=…)` — **키워드 인자로** 넘긴다. 기존 `TestContinue.test_creates_the_work…` 의 대역이 인자 하나짜리 lambda 라 위치 인자면 TypeError 다(대역을 `lambda job, paper_keywords=None:` 로 고친다). 서지 조회는 후보가 없으면 `get_by_cnts_ids([])` 가 DB 를 읽지 않고 `{}` 다. 같은 트랜잭션의 짧은 SELECT 하나라 함정 18(세션을 쥔 채 기다리지 않기)과 무관하다.
- **뼈대 목록 밖에서 함께 깨지는 테스트(실측):** `test_research_work_concepts.py` 의 `TestConceptsInput` 두 dict(`paper_keywords` 키)·`test_build_renders_the_real_template`('2개 이상 5개 이하')·`test_unreadable_answers_parse_to_none` 의 `'{"keywords": ["가", "나"]}'` 매개변수(이제 읽힌다 — `{"terms": …}` 로 바꾼다), `test_research_work_executor.py::TestExecutorFields::test_concepts_marks_an_empty_done_as_retryable`(`ex.bind` 가 생겼다), `test_research_work_tasks.py::TestDispatch` 의 `test_concepts_generation_runs_to_done`(저장 출력에 `candidates`)·`test_no_answer_after_three_calls_is_done_with_no_concepts`(개념 1개 답이 이제 통과 — 일반어만 낸 답으로 바꾼다). `CONCEPTS_INPUT`(`test_research_work_tasks.py:30`, `headings` 가 있고 `paper_keywords` 가 없는 옛 행 모양)은 그대로 두어 옛 행 경로를 함께 지킨다.
- `research/round06-qwen-check/`(06a 1회성 도구)는 `EXECUTOR.parse(...)["concepts"]` 를 읽어 이 Task 뒤 `smoke_check.py` 가 `KeyError: 'concepts'` 로 떨어진다 — 끝난 실험이라 다시 돌리지 않으므로 고치지 않는다. `research/round06b-topic-card-check/smoke_check.py` 는 그대로 `smoke OK`(샌드박스 실측).
- **앞 Task 가 먼저 고친 같은 파일(뼈대 §3 표 밖 — 파트 R 메모 1):** Task R1 이 `app/api/research_work.py` 의 `CONCEPTS_BUSY`(:53)·`patch_work` 의 422 문구(:252)를 '키워드'로, `app/tests/test_research_work_api.py` 의 `TestPatchWork.test_concepts_cannot_change_while_concepts_are_being_made` 기대(:510)를 먼저 고친다. 한 줄씩 글자만 바꾸므로 줄 번호는 dev `da80f23` 그대로이고, 이 Task·Task K3·Task K5 의 old 는 그 줄들을 잡지 않는다. 파일 단위 기대 수(`api 82`)도 Task R1 이 바꾸지 않는다(고친 테스트뿐).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_work_keywords.py` (새 파일, 전체):

```python
"""services/research_work/keywords.py — 제목 고르기의 키워드 후보(순수 함수, round06e D23).

LLM 후보와 채택 논문의 소장 키워드(문서 빈도)를 합치는 규칙 — 정리·일반어 거르기·순서·출처·편수·상한·미리 선택.
DB·LLM 을 쓰지 않는다. 서지는 BookRepository 가 돌려주는 BookOut 과 같은 이름의 속성만 가진 대역이다.
"""
from types import SimpleNamespace

import pytest

from services.research_work import keywords
from services.research_work.concepts import MAX_CONCEPT_LEN
from services.research_work.keywords import (
    GENERIC_KEYWORDS, KEYWORD_LEN_MAX, MAX_KEYWORD_CANDIDATES, MIN_PICKED_KEYWORDS, PAPER_KEYWORD_MIN_N,
    PAPER_KEYWORDS_INPUT_MAX, PRESELECT, clean_keyword, keyword_key, merge_candidates, paper_keyword_counts,
    preselect, split_catalog_keywords,
)


def _book(keyword: str | None = None, extracted: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(keyword=keyword, extracted_keywords=extracted or [])


class TestKeywordKey:
    def test_spaces_case_and_full_width_are_the_same_word(self):
        assert keyword_key("AI 윤리") == keyword_key("ai윤리") == keyword_key("ＡＩ　윤리") == "ai윤리"

    def test_different_words_stay_different(self):
        assert keyword_key("노인 우울") != keyword_key("우울 노인")


class TestCleanKeyword:
    def test_limits(self):
        assert (MAX_KEYWORD_CANDIDATES, PRESELECT, MIN_PICKED_KEYWORDS, PAPER_KEYWORDS_INPUT_MAX) == (10, 3, 2, 30)
        assert PAPER_KEYWORD_MIN_N in (1, 2)
        # 칩(research_works.concepts)과 같은 글자 상한 — 후보를 골라 PATCH 로 저장할 때 잘리지 않는다
        assert KEYWORD_LEN_MAX == MAX_CONCEPT_LEN == 40

    def test_tidies_spaces_and_normalizes(self):
        assert clean_keyword("  노인   우울 ") == "노인 우울"
        assert clean_keyword("ＡＩ　윤리") == "AI 윤리"

    @pytest.mark.parametrize("raw", [None, 3, ["노인 우울"], {"text": "노인 우울"}, "", "   ", "가" * 41])
    def test_non_strings_empty_and_too_long_give_none(self, raw):
        assert clean_keyword(raw) is None

    def test_forty_characters_pass(self):
        assert clean_keyword("가" * 40) == "가" * 40

    @pytest.mark.parametrize("raw", ["연구 성과", "국내 학술논문 코퍼스", "연구분야", "발전  방향", "측정 및 평가", "선행 연구"])
    def test_generic_words_are_dropped_whatever_the_spacing(self, raw):
        # 06b 운영 개념에 섞였던 말('측정 및 평가 · 연구 분야 · 발전 방향' — round06b-완료노트 :87)
        assert clean_keyword(raw) is None

    def test_the_generic_list_holds_the_words_seen_in_production(self):
        assert {"연구 성과", "국내 학술논문 코퍼스", "연구 분야", "발전 방향", "측정 및 평가"} <= GENERIC_KEYWORDS


class TestSplitCatalogKeywords:
    def test_semicolons_and_commas(self):
        assert split_catalog_keywords("노인 우울; 사회적 지지,가족 지지 ;") == ["노인 우울", "사회적 지지", "가족 지지"]

    def test_full_width_separators_are_normalized_first(self):
        assert split_catalog_keywords("노인 우울；사회적 지지，가족") == ["노인 우울", "사회적 지지", "가족"]

    @pytest.mark.parametrize("raw", [None, "", " ; , "])
    def test_empty_values(self, raw):
        assert split_catalog_keywords(raw) == []


class TestPaperKeywordCounts:
    def test_counts_papers_not_mentions(self):
        # 한 논문 안에서 같은 말(653 과 추출 키워드에 둘 다, 띄어쓰기만 다름)은 한 번만 센다
        books = {"C1": _book("노인 우울; 노인우울", ["노인 우울"]), "C2": _book("노인 우울")}
        assert paper_keyword_counts(books) == [{"text": "노인 우울", "n": 2}]

    def test_catalog_and_extracted_keywords_are_joined(self):
        books = {"C1": _book("노인 우울", ["사회적 지지"]), "C2": _book(None, ["사회적 지지", "가족 지지"])}
        assert paper_keyword_counts(books) == [
            {"text": "사회적 지지", "n": 2}, {"text": "노인 우울", "n": 1}, {"text": "가족 지지", "n": 1}]

    def test_more_papers_first_then_the_order_they_came_in(self):
        books = {"C1": _book("가; 나"), "C2": _book("다; 나"), "C3": _book("다")}
        assert [k["text"] for k in paper_keyword_counts(books)] == ["나", "다", "가"]

    def test_generic_and_non_string_keywords_are_dropped(self):
        books = {"C1": _book("연구 동향; 노인 우울", ["선행연구", 3, None])}
        assert paper_keyword_counts(books) == [{"text": "노인 우울", "n": 1}]

    def test_keeps_the_first_thirty(self):
        books = {f"C{i}": _book(f"키워드{i}") for i in range(PAPER_KEYWORDS_INPUT_MAX + 5)}
        out = paper_keyword_counts(books)
        assert len(out) == PAPER_KEYWORDS_INPUT_MAX and out[0] == {"text": "키워드0", "n": 1}

    def test_no_books(self):
        assert paper_keyword_counts({}) == []


class TestMergeCandidates:
    def test_model_candidates_come_first_in_the_order_given(self):
        out = merge_candidates(["청소년", "독서 격차"], [{"text": "학교 도서관", "n": 9}])
        assert [(c["text"], c["source"]) for c in out] == [
            ("청소년", "llm"), ("독서 격차", "llm"), ("학교 도서관", "paper")]

    def test_paper_only_words_follow_by_paper_count(self):
        paper = [{"text": "가", "n": 1}, {"text": "나", "n": 3}, {"text": "다", "n": 3}]
        assert merge_candidates([], paper) == [
            {"text": "나", "source": "paper", "n": 3}, {"text": "다", "source": "paper", "n": 3},
            {"text": "가", "source": "paper", "n": 1}]

    def test_a_word_in_both_keeps_the_model_place_with_the_paper_count(self):
        out = merge_candidates(["청소년", "독서 격차"], [{"text": "독서격차", "n": 4}, {"text": "가정 환경", "n": 2}])
        assert out == [{"text": "청소년", "source": "llm", "n": 0}, {"text": "독서 격차", "source": "both", "n": 4},
                       {"text": "가정 환경", "source": "paper", "n": 2}]

    def test_at_most_ten(self):
        out = merge_candidates([f"모델{i}" for i in range(8)], [{"text": f"논문{i}", "n": 5} for i in range(8)])
        assert len(out) == MAX_KEYWORD_CANDIDATES
        assert [c["source"] for c in out] == ["llm"] * 8 + ["paper"] * 2

    def test_paper_words_below_the_minimum_count_are_dropped(self, monkeypatch):
        # 채움률이 낮으면(Task K1 판정 2) 논문에만 있는 말은 2편 이상 겹친 것만 — 모델과 겹친 말은 편수와 상관없이 남는다
        monkeypatch.setattr(keywords, "PAPER_KEYWORD_MIN_N", 2)
        out = merge_candidates(["독서 격차"], [{"text": "독서 격차", "n": 1}, {"text": "가", "n": 1}, {"text": "나", "n": 2}])
        assert out == [{"text": "독서 격차", "source": "both", "n": 1}, {"text": "나", "source": "paper", "n": 2}]

    def test_no_generic_words_and_no_repeats(self):
        out = merge_candidates(["연구 동향", "독서 격차", "독서격차", 3], [{"text": "발전 방향", "n": 9}])
        assert out == [{"text": "독서 격차", "source": "llm", "n": 0}]

    @pytest.mark.parametrize("bad", [None, "독서 격차", {"text": 3, "n": 2}, {"text": "가", "n": 0},
                                     {"text": "가", "n": "2"}, {"text": "가", "n": True}])
    def test_malformed_paper_entries_are_skipped(self, bad):
        assert merge_candidates([], [bad]) == []


class TestPreselect:
    def test_the_first_three(self):
        cands = merge_candidates(["가", "나", "다", "라"], [])
        assert preselect(cands) == ["가", "나", "다"]

    def test_fewer_than_three_are_all_picked(self):
        assert preselect(merge_candidates(["가"], [])) == ["가"]
        assert preselect([]) == []
```

② `app/tests/test_research_work_concepts.py` — import 에서 `MIN_CONCEPTS` 를 뺀다(키워드 생성의 검사는 '모델 후보 하나 이상'이라 쓰는 곳이 없어진다). old:

```python
from services.research_work.concepts import (
    EXECUTOR, MAX_CONCEPT_LEN, MAX_CONCEPTS, MIN_CONCEPTS, clean_concepts, concepts_input,
)
```

new:

```python
from services.research_work.concepts import (
    EXECUTOR, MAX_CONCEPT_LEN, MAX_CONCEPTS, clean_concepts, concepts_input,
)
```

③ 같은 파일 `TestCleanConcepts.test_limits`. old:

```python
    def test_limits(self):
        assert (MIN_CONCEPTS, MAX_CONCEPTS, MAX_CONCEPT_LEN) == (2, 5, 40)
```

new:

```python
    def test_limits(self):
        # 사용자가 고른·고친 칩(PATCH .../work)의 개수·글자 상한 — 키워드 후보 수(keywords.MAX_KEYWORD_CANDIDATES)와 다르다
        assert (MAX_CONCEPTS, MAX_CONCEPT_LEN) == (5, 40)
```

④ 같은 파일 `TestConceptsInput` — 입력에 `paper_keywords` 가 늘 실린다(기존 두 테스트의 기대 dict ✎, 새 테스트 하나). old:

```python
class TestConceptsInput:
    def test_question_and_plan_only(self):
        # 보고서 절 제목은 하위질문 글 그대로라 넣지 않는다 — _job 의 report 에 절이 있어도 읽지 않는다
        assert concepts_input(_job()) == {
            "question": "청소년 독서 격차 연구는 어디까지 왔나",
            "subquestions": ["독서 격차의 정의", "독서 격차를 줄이는 프로그램"],
        }
```

new:

```python
class TestConceptsInput:
    def test_question_and_plan_only(self):
        # 보고서 절 제목은 하위질문 글 그대로라 넣지 않는다 — _job 의 report 에 절이 있어도 읽지 않는다
        assert concepts_input(_job()) == {
            "question": "청소년 독서 격차 연구는 어디까지 왔나",
            "subquestions": ["독서 격차의 정의", "독서 격차를 줄이는 프로그램"],
            "paper_keywords": [],
        }

    def test_paper_keywords_ride_along(self):
        # 이어가기(FastAPI)가 채택 논문의 소장 키워드 문서 빈도를 세어 넘긴다 — 워커는 DB 를 읽지 않는다(§6-3)
        paper = [{"text": "독서 격차", "n": 3}, {"text": "학교 도서관", "n": 1}]
        out = concepts_input(_job(), paper_keywords=paper)
        assert out["paper_keywords"] == paper and out["paper_keywords"] is not paper
```

⑤ 같은 파일 `TestConceptsInput.test_missing_plan_and_report`. old:

```python
        assert concepts_input(_job(plan=None, report=None)) == {
            "question": "청소년 독서 격차 연구는 어디까지 왔나", "subquestions": [],
        }
```

new:

```python
        assert concepts_input(_job(plan=None, report=None)) == {
            "question": "청소년 독서 격차 연구는 어디까지 왔나", "subquestions": [], "paper_keywords": [],
        }
```

⑥ 같은 파일 `TestPrompt.test_build_renders_the_real_template` — 출력 키가 `keywords` 이고 개수를 적지 않는다. old:

```python
        assert "2개 이상 5개 이하" in system and '"concepts"' in system
```

new:

```python
        assert '"keywords"' in system and "키워드" in system and "개 이상" not in system
```

⑦ 같은 파일 `TestPrompt.test_format_is_described_without_a_sample_list` 와 새 테스트 — 출력 키·개수 숫자가 없음을 고정한다. old:

```python
    def test_format_is_described_without_a_sample_list(self):
        """원소가 든 배열 견본({"concepts": ["<핵심 개념>"]})을 두면 모델이 그 개수를 따라 개념 1개만 내
        검사(2개 이상)에서 떨어진다(함정 15). 형식은 말로만 적는다 — 템플릿 어디에도 대괄호가 없다."""
        tpl = get_prompt("research_concepts")
        assert "[" not in tpl.system and "[" not in tpl.user
        assert "문자열" in tpl.system and "배열" in tpl.system
```

new:

```python
    def test_format_is_described_without_a_sample_list(self):
        """원소가 든 배열 견본({"keywords": ["<키워드>"]})을 두면 모델이 그 개수를 따라 키워드 1개만 낸다(함정 15).
        형식은 말로만 적는다 — 템플릿 어디에도 대괄호가 없다. 키는 06e 부터 keywords 다."""
        tpl = get_prompt("research_concepts")
        assert "[" not in tpl.system and "[" not in tpl.user
        assert "문자열" in tpl.system and "배열" in tpl.system
        assert '"keywords"' in tpl.system and '"concepts"' not in tpl.system

    def test_no_count_is_written_in_the_prompt(self):
        # 후보 수는 코드가 자른다(MAX_KEYWORD_CANDIDATES) — 프롬프트에 개수를 적으면 모델이 그 수를 채우려 일반어를 끼운다
        tpl = get_prompt("research_concepts")
        for text in (tpl.system, tpl.user):
            assert re.search(r"\d+\s*개", text) is None
            assert "예:" not in text and "예시" not in text
```

⑧ 같은 파일 머리 import — 새 테스트가 쓰는 `re`. old:

```python
import asyncio
from types import SimpleNamespace
```

new:

```python
import asyncio
import re
from types import SimpleNamespace
```

⑨ 같은 파일 `TestExecutor` — 해석은 모델 후보 목록(`llm`)만 내고, 합치기·미리 선택은 `bind` 가 한다. 검사는 '모델 후보 하나 이상', 끝내 못 얻으면 논문 키워드만 후보로 둔다. old:

````python
    def test_parse_cleans_the_list(self):
        raw = '```json\n{"concepts": ["독서 격차", "청소년", "독서  격차"]}\n```'
        assert EXECUTOR.parse(raw) == {"concepts": ["독서 격차", "청소년"]}

    @pytest.mark.parametrize("raw", ["개념을 찾지 못했다", '{"concepts": "독서 격차"}', '{"keywords": ["가", "나"]}'])
    def test_unreadable_answers_parse_to_none(self, raw):
        assert EXECUTOR.parse(raw) is None

    def test_check_needs_two_concepts(self):
        assert EXECUTOR.check({"concepts": ["독서 격차", "청소년"]}) is True
        assert EXECUTOR.check({"concepts": ["독서 격차"]}) is False

    def test_empty_result_has_no_concepts(self):
        assert EXECUTOR.empty(concepts_input(_job())) == {"concepts": []}

    def test_one_concept_is_asked_again_through_the_common_rule(self, monkeypatch):
        # 핵심 개념의 주 모델은 gemma(LLM_*)다 — 06a Qwen 표본 결정
        cfg = routing.get_settings()
        monkeypatch.setattr(cfg, "LLM_BASE_URL", "http://gemma.test/v1")
        monkeypatch.setattr(cfg, "LLM_MODEL", "gemma-test")
        answers = ['{"concepts": ["독서 격차"]}', '{"concepts": ["독서 격차", "청소년", "독서 격차"]}']
        seen = []

        async def fake_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            seen.append(model)
            return LLMResult(content=answers.pop(0), finish_reason="stop")

        result = asyncio.run(run_generation(EXECUTOR, concepts_input(_job()), chat_fn=fake_chat))

        assert seen == ["gemma-test", "gemma-test"]
        assert result.output == {"concepts": ["독서 격차", "청소년"]} and result.model == "gemma-test"
````

new:

````python
    def test_parse_cleans_the_list(self):
        # 정리·일반어 거르기·같은 말 지우기(띄어쓰기·대소문자 무시)만 하고 순서는 모델이 낸 그대로다
        raw = '```json\n{"keywords": ["독서 격차", "청소년", "독서  격차", "연구 동향", "학교도서관"]}\n```'
        assert EXECUTOR.parse(raw) == {"llm": ["독서 격차", "청소년", "학교도서관"]}
        # 06e 전 프롬프트의 키(concepts)도 읽는다 — 배포 사이에 옛 워커가 넣은 행을 새 워커가 다시 부를 수 있다
        assert EXECUTOR.parse('{"concepts": ["독서 격차"]}') == {"llm": ["독서 격차"]}

    @pytest.mark.parametrize("raw", ["키워드를 찾지 못했다", '{"keywords": "독서 격차"}', '{"terms": ["가", "나"]}'])
    def test_unreadable_answers_parse_to_none(self, raw):
        assert EXECUTOR.parse(raw) is None

    def test_bind_merges_paper_keywords_and_preselects_three(self):
        paper = [{"text": "독서격차", "n": 3}, {"text": "학교 도서관", "n": 2}, {"text": "연구 동향", "n": 5}]
        out = EXECUTOR.bind(EXECUTOR.parse('{"keywords": ["독서 격차", "청소년", "가정 환경"]}'),
                            concepts_input(_job(), paper_keywords=paper))
        assert out == {
            "concepts": ["독서 격차", "청소년", "가정 환경"],
            "candidates": [{"text": "독서 격차", "source": "both", "n": 3},
                           {"text": "청소년", "source": "llm", "n": 0},
                           {"text": "가정 환경", "source": "llm", "n": 0},
                           {"text": "학교 도서관", "source": "paper", "n": 2}],
        }

    def test_check_needs_one_candidate_from_the_model(self):
        bound = EXECUTOR.bind({"llm": ["독서 격차"]}, concepts_input(_job()))
        assert EXECUTOR.check(bound) is True
        # 논문 키워드만 남았다 — 모델이 실패한 것이라 다시 부른다
        paper_only = EXECUTOR.bind({"llm": []}, concepts_input(_job(), paper_keywords=[{"text": "독서 격차", "n": 2}]))
        assert paper_only["candidates"] == [{"text": "독서 격차", "source": "paper", "n": 2}]
        assert EXECUTOR.check(paper_only) is False

    def test_empty_result_has_no_concepts(self):
        # 끝내 못 얻으면 미리 고르지 않고 논문 키워드만 후보로 둔다 — 사용자가 고르거나 [다시]
        assert EXECUTOR.empty(concepts_input(_job())) == {"concepts": [], "candidates": []}
        out = EXECUTOR.empty(concepts_input(_job(), paper_keywords=[{"text": "학교 도서관", "n": 2}]))
        assert out == {"concepts": [], "candidates": [{"text": "학교 도서관", "source": "paper", "n": 2}]}
        assert EXECUTOR.is_empty(out) is True

    def test_only_generic_words_are_asked_again_through_the_common_rule(self, monkeypatch):
        # 키워드 생성의 주 모델은 gemma(LLM_*)다 — 06a Qwen 표본 결정
        cfg = routing.get_settings()
        monkeypatch.setattr(cfg, "LLM_BASE_URL", "http://gemma.test/v1")
        monkeypatch.setattr(cfg, "LLM_MODEL", "gemma-test")
        answers = ['{"keywords": ["연구 동향", "선행연구"]}', '{"keywords": ["독서 격차", "청소년", "독서 격차"]}']
        seen = []

        async def fake_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            seen.append(model)
            return LLMResult(content=answers.pop(0), finish_reason="stop")

        result = asyncio.run(run_generation(EXECUTOR, concepts_input(_job()), chat_fn=fake_chat))

        assert seen == ["gemma-test", "gemma-test"]
        assert [a["outcome"] for a in result.attempts] == ["check", "ok"]
        assert result.output == {
            "concepts": ["독서 격차", "청소년"],
            "candidates": [{"text": "독서 격차", "source": "llm", "n": 0}, {"text": "청소년", "source": "llm", "n": 0}],
        }
        assert result.model == "gemma-test"
````

⑩ `app/tests/test_research_work_api.py` `TestContinue.test_creates_the_work_its_candidates_and_one_concepts_generation` — 대역이 키워드 인자를 받게(이어가기가 `concepts_input(job, paper_keywords=…)` 로 부른다 — 인자 하나짜리 lambda 면 TypeError). old:

```python
        monkeypatch.setattr(api.router, "concepts_input",
                            lambda job: {"question": job.question, "marker": 1})
```

new:

```python
        monkeypatch.setattr(api.router, "concepts_input",
                            lambda job, paper_keywords=None: {"question": job.question, "marker": 1})
```

⑪ 같은 파일 `TestContinue.test_concepts_input_reads_the_job` — 채택 논문(C1·C2)의 소장 키워드 문서 빈도가 입력에 실린다. old:

```python
    def test_concepts_input_reads_the_job(self, api):
        # 가짜 없이 — 핵심 개념 생성 입력이 잡 행(질문·계획·보고서)에서 만들어지는지
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        (gen,) = _rows(api.engine, ResearchGeneration)
        same_job = SimpleNamespace(id=jid, question="청소년 독서 격차", plan=["독서 격차의 원인"],
                                   report=REPORT, state_snapshot=SNAPSHOT, params={})
        assert gen["input"] == json.loads(json.dumps(api.router.concepts_input(same_job)))
        assert gen["input"]["question"] == "청소년 독서 격차"
```

new:

```python
    def test_concepts_input_reads_the_job(self, api):
        # 가짜 없이 — 키워드 생성 입력이 잡 행(질문·계획)과 채택 논문(C1·C2)의 소장 키워드에서 만들어지는지.
        # 653 키워드(구분자로 이은 글)와 추출 키워드(extra.keywords)를 합쳐 논문 수로 센다 — 같은 수면 후보 순서(C1 먼저)
        add_book(api.engine, "C1", keyword="독서 격차; 학교 도서관")
        add_book(api.engine, "C2", extra={"keywords": ["학교 도서관", "가정 환경", "연구 동향"]})
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        (gen,) = _rows(api.engine, ResearchGeneration)
        paper = [{"text": "학교 도서관", "n": 2}, {"text": "독서 격차", "n": 1}, {"text": "가정 환경", "n": 1}]
        same_job = SimpleNamespace(id=jid, question="청소년 독서 격차", plan=["독서 격차의 원인"],
                                   report=REPORT, state_snapshot=SNAPSHOT, params={})
        assert gen["input"] == json.loads(json.dumps(api.router.concepts_input(same_job, paper_keywords=paper)))
        assert gen["input"]["question"] == "청소년 독서 격차"
        assert gen["input"]["paper_keywords"] == paper
```

⑫ 같은 파일 머리 import — `add_book`. old:

```python
from history_sqlite import (
    SID_A, SID_B, AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
```

new:

```python
from history_sqlite import (
    SID_A, SID_B, AsyncSessionOverSync, add_book, add_generation, add_research_job, add_work, make_engine,
)
```

⑬ `app/tests/test_research_work_executor.py` `TestExecutorFields.test_concepts_marks_an_empty_done_as_retryable` — 키워드 생성 실행기는 06e 부터 `bind`(후보 합치기)를 쓴다. old:

```python
        assert not ex.is_empty({"concepts": ["독서 격차", "청소년"]})
        assert (ex.bind, ex.stream, ex.apply) == (None, False, None)
```

new:

```python
        assert not ex.is_empty({"concepts": ["독서 격차", "청소년"]})
        # 06e — 모델 후보와 채택 논문 키워드를 bind 가 합친다(concepts._bind). 반영은 apply_result 의 concepts 분기 그대로
        assert ex.bind is concepts._bind and (ex.stream, ex.apply) == (False, None)
```

⑭ `app/tests/test_research_work_tasks.py` `TestDispatch.test_concepts_generation_runs_to_done` — 저장되는 출력에 후보(`candidates`)가 함께 실린다(이 테스트의 입력 `CONCEPTS_INPUT` 은 06a 모양 그대로 — `paper_keywords` 가 없는 옛 행도 돈다). old:

```python
        assert row["output"] == {"concepts": ["독서 격차", "청소년"],
                                 "attempts": [{"model": "gemma-test", "outcome": "ok"}]}
```

new:

```python
        assert row["output"] == {"concepts": ["독서 격차", "청소년"],
                                 "candidates": [{"text": "독서 격차", "source": "llm", "n": 0},
                                                {"text": "청소년", "source": "llm", "n": 0}],
                                 "attempts": [{"model": "gemma-test", "outcome": "ok"}]}
```

⑮ 같은 파일 `TestDispatch.test_no_answer_after_three_calls_is_done_with_no_concepts` — 개념 1개는 06e 부터 통과다(검사가 '모델 후보 하나 이상'). 두 번째 답을 일반어만 낸 답으로 바꾼다. old:

```python
        env = _Env(monkeypatch, wt, replies=["모르겠다", '{"concepts": ["하나"]}', "{}"])
```

new:

```python
        env = _Env(monkeypatch, wt, replies=["모르겠다", '{"keywords": ["연구 동향", "선행연구"]}', "{}"])
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_keywords.py -q -p no:cacheprovider`

Expected: 수집 오류 — `ImportError: cannot import name 'keywords' from 'services.research_work'` · `Interrupted: 1 error during collection`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_concepts.py tests/test_research_work_api.py tests/test_research_work_executor.py tests/test_research_work_tasks.py -q -p no:cacheprovider`

Expected: `15 failed, 138 passed, 2 warnings` — 실패는 정확히 다음 15개(샌드박스 실측):
- `test_research_work_concepts.py` 11개 — `TestConceptsInput` 셋(`test_question_and_plan_only`·`test_paper_keywords_ride_along`·`test_missing_plan_and_report` — `paper_keywords` 가 없고 인자를 받지 않는다), `TestPrompt` 셋(`test_build_renders_the_real_template`·`test_format_is_described_without_a_sample_list`·`test_no_count_is_written_in_the_prompt` — 키가 `concepts`, '2개 이상 5개 이하'), `TestExecutor` 다섯(`test_parse_cleans_the_list`·`test_bind_merges_paper_keywords_and_preselects_three`·`test_check_needs_one_candidate_from_the_model`·`test_empty_result_has_no_concepts`·`test_only_generic_words_are_asked_again_through_the_common_rule` — 해석이 `{"concepts"}`, `bind` 없음)
- `test_research_work_api.py::TestContinue::test_concepts_input_reads_the_job` — `concepts_input` 이 `paper_keywords` 인자를 받지 않는다(TypeError)
- `test_research_work_executor.py::TestExecutorFields::test_concepts_marks_an_empty_done_as_retryable` — `ex.bind` 가 None
- `test_research_work_tasks.py::TestDispatch` 둘 — `test_concepts_generation_runs_to_done`(출력에 `candidates` 없음)·`test_no_answer_after_three_calls_is_done_with_no_concepts`(일반어 답을 06b 해석이 거르지 못한다)

- [ ] **Step 3: 구현한다**

① `app/services/research_work/keywords.py` (새 파일, 전체):

```python
"""keywords.py — 제목 고르기의 키워드 후보 (순수 함수, round06e D23 — spec §12-4 '후보 키워드', 계획 06e 정함 14·15)

후보 = LLM 후보(개념 생성을 넓힌 것 — concepts.py) + 채택 논문의 소장 키워드(library_catalog.keyword 를 나눈 것 ∪
extra.keywords) 문서 빈도. 둘을 코드가 합쳐 출처(source)·편수(n)를 단다.
  - 순서: LLM 후보를 LLM 이 낸 순서대로 먼저, 논문 키워드에만 있는 후보는 편수 내림차순(같으면 먼저 나온 것)으로 뒤에.
    두 원천에 다 있으면 LLM 자리에 편수를 단다(source "both").
  - 개수는 코드가 자른다 — 상한 MAX_KEYWORD_CANDIDATES, 하한은 없다(있는 만큼). 프롬프트에는 개수를 적지 않는다(함정 15).
  - 일반어('연구 성과'·'국내 학술논문 코퍼스'·'연구 분야'·'발전 방향' 등 — 06b 운영 개념에 섞였다)는 GENERIC_KEYWORDS 로 거른다.
  - 위 PRESELECT 개를 미리 고른다 — research_works.concepts(고른 키워드)가 된다.
논문 키워드는 이어가기 때 FastAPI 가 읽어 개념 생성 input 의 paper_keywords 에 싣는다 — 워커는 DB 텍스트만 쓴다(§6-3).
같은 말 판정은 keyword_key(NFKC → 공백 제거 → casefold)다 — clean_concepts 의 중복 열쇠와 같다.
DB·LLM·무거운 import 가 없다(concepts.py 가 이 모듈을 import 한다 — 거꾸로 가져오지 않는다).
"""
import re
import unicodedata

MAX_KEYWORD_CANDIDATES = 10     # 후보 상한 — 하한은 없다
PRESELECT = 3                   # 처음에 미리 고르는 후보 수(후보가 적으면 모두)
MIN_PICKED_KEYWORDS = 2         # [이 키워드로 다시 만들기]의 최소 선택 수 — 선행연구 묶음 수 ≤ 키워드 수(membership)
PAPER_KEYWORDS_INPUT_MAX = 30   # 개념 생성 input 에 싣는 논문 키워드 수 상한(편수 많은 순)
PAPER_KEYWORD_MIN_N = 1         # 논문에만 있는 후보의 최소 편수 — Task K1 채움률 측정으로 1 또는 2(README '결과')
KEYWORD_LEN_MAX = 40            # 키워드 한 개 글자 상한 — 칩(concepts.MAX_CONCEPT_LEN)과 같다
# 어느 질문에나 붙는 일반어 — keyword_key 로 견준다(띄어쓰기·대소문자·전각 무시). 운영에서 더 나오면 여기에 더한다
GENERIC_KEYWORDS: frozenset[str] = frozenset({
    "연구 성과", "국내 학술논문 코퍼스", "국내 학술논문", "학술논문", "연구 분야", "발전 방향", "측정 및 평가",
    "연구 동향", "선행연구", "연구 방법", "개념 및 정의", "한계 및 과제", "적용 분야", "향후 과제",
})

_CATALOG_SEP = re.compile(r"[;,]")


def keyword_key(text: str) -> str:
    """같은 말 판정 열쇠 — NFKC 뒤 공백을 모두 지우고 casefold."""
    return "".join(unicodedata.normalize("NFKC", text).split()).casefold()


_GENERIC_KEYS = frozenset(keyword_key(w) for w in GENERIC_KEYWORDS)


def clean_keyword(raw: object) -> str | None:
    """문자열만, NFKC·공백 정리, 1~KEYWORD_LEN_MAX 자, 일반어가 아니면 정리한 글. 아니면 None."""
    if not isinstance(raw, str):
        return None
    text = " ".join(unicodedata.normalize("NFKC", raw).split())
    if not 1 <= len(text) <= KEYWORD_LEN_MAX or keyword_key(text) in _GENERIC_KEYS:
        return None
    return text


def split_catalog_keywords(raw: str | None) -> list[str]:
    """library_catalog.keyword(653 $a 를 이은 글) → 키워드 조각. NFKC 뒤 ';'·',' 로 나눈다(전각 '；'·'，' 도 NFKC 로
    같아진다). 빈 조각은 버린다 — 정리·일반어 거르기는 clean_keyword 의 몫이다."""
    if not isinstance(raw, str):
        return []
    return [p.strip() for p in _CATALOG_SEP.split(unicodedata.normalize("NFKC", raw)) if p.strip()]


def paper_keyword_counts(books: dict) -> list[dict]:
    """채택 논문의 서지({cnts_id: BookOut}) → [{"text", "n"}] — n 은 그 키워드를 가진 논문 수(문서 빈도).

    키워드는 keyword 를 나눈 것과 extracted_keywords 를 합친다. 한 논문 안에서 같은 말은 한 번만 센다. 정리·일반어를
    거른 뒤 편수 내림차순, 같으면 처음 나온 순(books 의 순서 — 부르는 쪽이 후보 순서로 넘긴다). 앞
    PAPER_KEYWORDS_INPUT_MAX 개만."""
    counts: dict[str, int] = {}
    shown: dict[str, str] = {}
    for book in books.values():
        seen: set[str] = set()
        raw = [*split_catalog_keywords(getattr(book, "keyword", None)),
               *(getattr(book, "extracted_keywords", None) or [])]
        for item in raw:
            text = clean_keyword(item)
            if text is None:
                continue
            key = keyword_key(text)
            if key in seen:
                continue
            seen.add(key)
            shown.setdefault(key, text)
            counts[key] = counts.get(key, 0) + 1
    order = sorted(counts, key=lambda k: -counts[k])       # 안정 정렬 — 같은 편수는 처음 나온 순 그대로
    return [{"text": shown[k], "n": counts[k]} for k in order[:PAPER_KEYWORDS_INPUT_MAX]]


def merge_candidates(llm: list[str], paper: list[dict]) -> list[dict]:
    """LLM 후보 + 논문 키워드 → [{"text", "source": "llm"|"paper"|"both", "n"}](앞 MAX_KEYWORD_CANDIDATES 개).

    LLM 후보를 낸 순서대로 먼저 — 논문에도 있으면 source both·n 편수, 없으면 llm·0. 그 뒤 논문에만 있고
    n >= PAPER_KEYWORD_MIN_N 인 것을 편수 내림차순(같으면 받은 순)으로. 같은 말(keyword_key)은 한 번만, 일반어는 뺀다.
    paper 의 원소는 개념 생성 input 에서 읽은 값이라 모양이 틀린 것(글이 아님·편수가 1 미만)은 건너뛴다."""
    papers: dict[str, dict] = {}
    for item in paper or []:
        if not isinstance(item, dict):
            continue
        text, n = clean_keyword(item.get("text")), item.get("n")
        if text is None or not isinstance(n, int) or isinstance(n, bool) or n < 1:
            continue
        papers.setdefault(keyword_key(text), {"text": text, "n": n})
    out: list[dict] = []
    used: set[str] = set()
    for raw in llm or []:
        text = clean_keyword(raw)
        if text is None:
            continue
        key = keyword_key(text)
        if key in used:
            continue
        used.add(key)
        hit = papers.get(key)
        out.append({"text": text, "source": "both" if hit else "llm", "n": hit["n"] if hit else 0})
    rest = [p for key, p in papers.items() if key not in used and p["n"] >= PAPER_KEYWORD_MIN_N]
    rest.sort(key=lambda p: -p["n"])
    out += [{"text": p["text"], "source": "paper", "n": p["n"]} for p in rest]
    return out[:MAX_KEYWORD_CANDIDATES]


def preselect(candidates: list[dict]) -> list[str]:
    """처음에 미리 고르는 키워드 — 후보 앞 PRESELECT 개(적으면 모두). 최소 선택 수(MIN_PICKED_KEYWORDS)는 보지 않는다."""
    return [c["text"] for c in candidates[:PRESELECT]]
```

② `app/services/research_work/concepts.py` 머리 docstring·import·상수. old:

```python
"""concepts.py — 핵심 개념 생성(kind=concepts, gemma) — spec §5-2

입력은 원 질문 + 하위질문(승인된 계획), 출력은 원 질문의 핵심 개념 2~5개. 보고서 절 제목은 넣지 않는다 —
절 제목은 하위질문 글 그대로(synthesizer 의 heading = sq.text)라 새 정보가 없고, 측면 틀 낱말(정의·방법론·
한계)의 무게만 두 배로 만든다(06a Qwen 표본에서 개념이 절 제목을 옮겼다). 06a 에 만든 생성 행의 input 에
남은 headings 키는 읽지 않는다.
개수·중복은 모델에 맡기지 않고 코드가 자르고 지운다(함정 15). 끝내 2개를 못 얻으면 비운 채
done 이고, 화면은 '핵심 개념 넣기' 입력을 보인다(사용자가 PATCH .../work 로 넣는다).
"""
import unicodedata

from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research_work.generate import Executor

MIN_CONCEPTS, MAX_CONCEPTS, MAX_CONCEPT_LEN = 2, 5, 40
```

new:

```python
"""concepts.py — 키워드 후보 생성(kind=concepts, gemma) — spec §5-2, 06e §12-4 '후보 키워드'(D23)

06e 부터 이 생성은 '제목 고르기'의 키워드 후보를 낸다(생성 종류 이름 concepts·research_works.concepts 는 그대로 —
고른 키워드가 칩이고 목차 묶음 배정이 같은 값을 쓴다). 입력은 원 질문 + 하위질문(승인된 계획) + 채택 논문의 소장
키워드 문서 빈도(paper_keywords — 이어가기 때 FastAPI 가 싣는다), 출력은
{"concepts": [미리 고른 키워드], "candidates": [{"text", "source", "n"}]}. 후보를 합치는 규칙(순서·출처·편수·상한·
일반어·미리 고르기)은 keywords.py 에 있다. 모델은 키워드만 중요한 순서대로 내고, 개수는 프롬프트에 적지 않고 코드가
자른다(함정 15). 모델이 낸 후보가 일반어를 거른 뒤 하나도 없으면 내용 검사 미달로 다시 부르고, 끝내 없으면
논문 키워드만 후보로 둔 채 concepts 를 비워 done 이다(화면은 [다시]·직접 더하기를 보인다).
보고서 절 제목은 넣지 않는다 — 절 제목은 하위질문 글 그대로(synthesizer 의 heading = sq.text)라 새 정보가 없고,
측면 틀 낱말(정의·방법론·한계)의 무게만 두 배로 만든다(06a Qwen 표본에서 개념이 절 제목을 옮겼다). 06a 에 만든 생성
행의 input 에 남은 headings 키는 읽지 않는다. 06e 전에 만든 행(paper_keywords 없음)은 논문 후보 없이 돈다.
"""
import unicodedata

from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research_work.generate import Executor
from services.research_work.keywords import clean_keyword, keyword_key, merge_candidates, preselect

# 칩(research_works.concepts) 규칙 — 사용자가 고른·고친 칩(PATCH .../work)의 개수·글자 상한.
# 글자 상한은 키워드 후보(keywords.KEYWORD_LEN_MAX)와 같다(test_research_work_keywords 가 고정)
MAX_CONCEPTS, MAX_CONCEPT_LEN = 5, 40
```

③ 같은 파일 `concepts_input`. old:

```python
def concepts_input(job) -> dict:
    """완료된 딥리서치 잡(ResearchJob) → 생성 입력. research_generations.input 에 그대로 담긴다.

    원 질문과 승인된 하위질문만 담는다(보고서 절 제목을 넣지 않는 까닭은 모듈 docstring).
    """
    return {
        "question": job.question,
        "subquestions": [s for s in (job.plan or []) if isinstance(s, str)],
    }
```

new:

```python
def concepts_input(job, paper_keywords: list[dict] | None = None) -> dict:
    """완료된 딥리서치 잡(ResearchJob) → 생성 입력. research_generations.input 에 그대로 담긴다.

    원 질문과 승인된 하위질문, 그리고 채택 논문의 키워드 문서 빈도(keywords.paper_keyword_counts — 이어가기가 읽어
    넘긴다)를 담는다. 보고서 절 제목을 넣지 않는 까닭은 모듈 docstring.
    """
    return {
        "question": job.question,
        "subquestions": [s for s in (job.plan or []) if isinstance(s, str)],
        "paper_keywords": list(paper_keywords or []),
    }
```

④ 같은 파일 `_parse`·`EXECUTOR` — 해석·합치기·검사·빈 결과. old:

```python
def _parse(raw: str) -> dict | None:
    data = extract_json(raw)
    if data is None or not isinstance(data.get("concepts"), list):
        return None
    return {"concepts": clean_concepts(data["concepts"])}


EXECUTOR = Executor(
    kind="concepts",
    build=_build,
    parse=_parse,
    check=lambda output: len(output["concepts"]) >= MIN_CONCEPTS,
    empty=lambda input: {"concepts": []},
    # 빈 결과로 끝난 done 은 다시 부를 수 있다(api/research_work._retryable — 06a 의 concepts 특례를 옮긴 것)
    is_empty=lambda output: not (output or {}).get("concepts"),
)
```

new:

```python
def _parse(raw: str) -> dict | None:
    """원문 → {"llm": [모델이 낸 키워드 — 정리·일반어 거름·중복 제거, 낸 순서]}. 키는 keywords — 06e 전 프롬프트의
    concepts 키도 읽는다(배포 사이에 옛 워커가 넣은 행을 새 워커가 다시 부를 수 있다). 목록이 아니면 None."""
    data = extract_json(raw)
    if data is None:
        return None
    items = data.get("keywords")
    if items is None:
        items = data.get("concepts")
    if not isinstance(items, list):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = clean_keyword(item)
        if text is None or keyword_key(text) in seen:
            continue
        seen.add(keyword_key(text))
        out.append(text)
    return {"llm": out}


def _bind(output: dict, input: dict) -> dict:
    """모델 후보 + 논문 키워드(input.paper_keywords) → {"concepts": 미리 고른 키워드, "candidates": 후보}."""
    candidates = merge_candidates(output.get("llm") or [], input.get("paper_keywords") or [])
    return {"concepts": preselect(candidates), "candidates": candidates}


def _check(output: dict) -> bool:
    """모델이 낸 후보가 하나라도 남았는가 — 논문 키워드만 남았으면 모델이 실패한 것이라 다시 부른다."""
    return any(c["source"] in ("llm", "both") for c in output.get("candidates") or [])


def _empty(input: dict) -> dict:
    """끝내 모델 후보를 못 얻은 결과 — 논문 키워드만 후보로 두고 미리 고르지 않는다(사용자가 고르거나 [다시])."""
    return {"concepts": [], "candidates": merge_candidates([], input.get("paper_keywords") or [])}


EXECUTOR = Executor(
    kind="concepts",
    build=_build,
    parse=_parse,
    check=_check,
    empty=_empty,
    bind=_bind,
    # 빈 결과로 끝난 done 은 다시 부를 수 있다(api/research_work._retryable — 06a 의 concepts 특례를 옮긴 것)
    is_empty=lambda output: not (output or {}).get("concepts"),
)
```

⑤ `app/domains/nl_library/prompts/research_concepts.yaml` — 키워드 후보로 넓힌다. 개수·예시를 적지 않고(함정 15) 출력 키는 `keywords`. 변수(question·subquestions)는 그대로다. old:

```yaml
params:
  # 상한일 뿐이다 — 규칙의 최대(개념 5개 x 40자 + JSON·코드 펜스)를 한국어 토큰으로 넉넉히 덮는다.
  # 200 이면 잘린 JSON 이 해석 실패로 세어지고 같은 한도로 다시 물어 또 잘린다
  max_tokens: 400
  temperature: 0.2
system: |-
  당신은 국내 학술논문 코퍼스를 다루는 연구 사서입니다.
  연구자의 원 질문에서 핵심 개념을 뽑습니다.

  핵심 개념은 원 질문이 무엇을 연구하려는지 가리키는 짧은 명사구입니다.
  하위질문은 원 질문을 이해하기 위한 참고 자료입니다. 하위질문에만 나오고 원 질문의 주제가 아닌 개념은 넣지 마세요.

  규칙:
  - 핵심 개념은 2개 이상 5개 이하입니다.
  - 개념 하나는 40자 이내의 명사구로 씁니다. 문장으로 쓰지 마세요.
  - 같은 개념을 다른 말로 되풀이하지 마세요.
  - 어느 질문에나 붙을 수 있는 일반적인 말만으로 된 개념은 넣지 마세요.
  - 원 질문에 쓰인 말을 살려 씁니다.

  반드시 JSON 객체 하나로만 응답하세요. 설명이나 다른 텍스트는 출력하지 마세요.
  객체의 키는 "concepts" 하나이고, 값은 핵심 개념 문자열들의 배열입니다. 배열에는 2개 이상 5개 이하의 개념을 담습니다.
```

new:

```yaml
params:
  # 상한일 뿐이다 — 개수는 프롬프트에 적지 않고 코드가 자른다(keywords.MAX_KEYWORD_CANDIDATES). 모델이 낸 키워드 수십 개
  # (하나 40자 이내) + JSON·코드 펜스를 한국어 토큰으로 넉넉히 덮는다. 잘린 JSON 은 해석 실패로 세어지고 같은 한도로 다시 묻는다
  max_tokens: 400
  temperature: 0.2
system: |-
  당신은 국내 학술논문 코퍼스를 다루는 연구 사서입니다.
  연구자의 원 질문으로 연구 주제의 제목을 지을 때 쓸 키워드 후보를 냅니다.

  키워드는 원 질문이 무엇을 연구하려는지 가리키는 짧은 명사구입니다. 연구자는 후보 가운데 몇 개를 골라 연구 주제 제목에 넣습니다.
  하위질문은 원 질문을 이해하기 위한 참고 자료입니다. 하위질문에만 나오고 원 질문의 주제가 아닌 말은 넣지 마세요.

  규칙:
  - 중요한 키워드부터 차례로 씁니다.
  - 키워드 하나는 40자 이내의 명사구로 씁니다. 문장으로 쓰지 마세요.
  - 같은 키워드를 다른 말로 되풀이하지 마세요.
  - 어느 질문에나 붙을 수 있는 일반적인 말만으로 된 키워드는 넣지 마세요.
  - 원 질문에 쓰인 말을 살려 씁니다.

  반드시 JSON 객체 하나로만 응답하세요. 설명이나 다른 텍스트는 출력하지 마세요.
  객체의 키는 "keywords" 하나이고, 값은 키워드 문자열들의 배열입니다.
```

⑥ `app/api/research_work.py` import — 서지 조회와 논문 키워드 세기. old:

```python
from models.research_work import (
    GEN_OPEN_STATUSES, PRIORITY_USER, ResearchGeneration, ResearchReading, ResearchTopic, ResearchWork,
)
from services.research.relay import publish_work, subscribe_work
from services.research_work.concepts import MAX_CONCEPTS, clean_concepts, concepts_input
```

new:

```python
from models.research_work import (
    GEN_OPEN_STATUSES, PRIORITY_USER, ResearchGeneration, ResearchReading, ResearchTopic, ResearchWork,
)
from repositories.book import BookRepository
from services.research.relay import publish_work, subscribe_work
from services.research_work.concepts import MAX_CONCEPTS, clean_concepts, concepts_input
```

⑦ 같은 파일 import — `services.research_work.executors` 줄 다음에 키워드 세기. old:

```python
from services.research_work.executors import EXECUTORS
from services.research_work.progress import refresh_progress
```

new:

```python
from services.research_work.executors import EXECUTORS
from services.research_work.keywords import paper_keyword_counts
from services.research_work.progress import refresh_progress
```

⑧ 같은 파일 `continue_research` — 개념(키워드) 생성 입력에 채택 논문의 소장 키워드 문서 빈도를 싣는다. **키워드 인자로** 넘긴다(기존 테스트의 대역이 `lambda job, paper_keywords=None` 이다). old:

```python
    await db.execute(insert(ResearchGeneration).values(
        work_id=jid, kind="concepts", priority=PRIORITY_USER, status="queued",
        input=concepts_input(job),
    ))
```

new:

```python
    # 키워드 후보의 논문 쪽 원천 — 채택 논문(읽기 목록 후보)의 소장 키워드 문서 빈도(spec §12-4, 06e 정함 14).
    # 서지는 DB 순서로 오므로 후보 순서로 다시 줄 세운다 — 같은 편수면 앞 후보의 키워드가 먼저다
    ids = [c["cnts_id"] for c in candidates]
    books = await BookRepository(db).get_by_cnts_ids(ids)
    in_order = {c: books[c] for c in ids if c in books}
    await db.execute(insert(ResearchGeneration).values(
        work_id=jid, kind="concepts", priority=PRIORITY_USER, status="queued",
        input=concepts_input(job, paper_keywords=paper_keyword_counts(in_order)),
    ))
```

⑨ 같은 파일 `WorkPatch` 주석(dev `da80f23` `:64`) — 생성 쪽 검사가 '개념 2개 이상'에서 '모델 후보 하나 이상'(`concepts._check`)으로 바뀌었다(CLAUDE.md §3 — 코드와 어긋난 주석을 고친다). old:

```python
    # 사용자가 고친 핵심 개념은 1~5개(LLM 결과의 '2개 이상' 검사는 생성 쪽 규칙이다)
```

new:

```python
    # 사용자가 고른·고친 키워드는 1~5개(키워드 생성의 '모델 후보 하나 이상' 검사는 생성 쪽 규칙이다 — concepts._check)
```

⑩ `app/services/research_work/generate.py` `Executor.check` 주석(`:47`) — 예로 들던 '개념 2개 이상' 규칙이 없어졌다. 지금 있는 규칙(주제 카드 근거 2편 이상)으로 바꾼다. old:

```python
    check: Callable[[dict], bool]                      # 내용 검사(예: 개념 2개 이상)
```

new:

```python
    check: Callable[[dict], bool]                      # 내용 검사(예: 주제 카드 근거 2편 이상)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_keywords.py tests/test_research_work_concepts.py tests/test_research_work_api.py tests/test_research_work_executor.py tests/test_research_work_tasks.py -q -p no:cacheprovider`

Expected: `197 passed, 2 warnings` (keywords 44 · concepts 32 · api 82 · executor 12 · tasks 27 — concepts 는 기준선 29 에 `test_paper_keywords_ride_along`·`test_no_count_is_written_in_the_prompt`·`test_bind_merges_paper_keywords_and_preselects_three` 셋을 더했다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 세 파일(`test_build_manifest`·`test_loaders`·`test_book_chat`), 통과 = Task 앞 + 47

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/keywords.py app/services/research_work/concepts.py app/domains/nl_library/prompts/research_concepts.yaml app/api/research_work.py app/services/research_work/generate.py app/tests/test_research_work_keywords.py app/tests/test_research_work_concepts.py app/tests/test_research_work_api.py app/tests/test_research_work_executor.py app/tests/test_research_work_tasks.py && git status --short && git commit -m "[Feat] round06e — 핵심 개념 생성을 '제목 고르기'의 키워드 후보로 넓힌다(D23, spec §12-4). 모델은 중요한 순서대로 키워드만 내고(프롬프트에 개수·예시 없음 — 함정 15, 출력 키 keywords) 코드가 정리·일반어 금지 목록(GENERIC_KEYWORDS — 06b 운영 개념의 '측정 및 평가·연구 분야·발전 방향' 등)·채택 논문의 소장 키워드(653 을 나눈 것 ∪ extra.keywords) 문서 빈도 합치기·상한 10·위 3개 미리 선택을 한다(새 keywords.py). 출력은 {concepts: 미리 고른 키워드, candidates: [{text, source llm|paper|both, n 편수}]} — research_works.concepts·PATCH·목차 묶음 배정은 그대로. 논문 키워드는 이어가기 때 FastAPI 가 후보 순서로 세어 생성 input 의 paper_keywords 에 싣는다. 모델 후보가 일반어를 거른 뒤 하나도 없으면 내용 검사 미달로 다시 부르고, 끝내 없으면 논문 키워드만 후보로 둔 채 비워 done. 06e 전 프롬프트의 concepts 키도 읽는다. 쓰지 않게 된 MIN_CONCEPTS 를 지우고, '개념 2개 이상'을 말하던 주석 두 곳(WorkPatch·Executor.check)을 지금 규칙으로 고친다"
```

---

### Task K3: WorkView 에 키워드 후보 — 최신 done 개념 생성을 따로 조회

**왜:** spec §12-4 '저장 — WorkView 에 `concept_candidates` 를 싣는다. 끝난 생성은 최근 10건만 읽으므로(`research_work.py:132-142`) 최신 done 개념 생성을 따로 조회한다'. 화면(Task K8 의 토글 칩)은 후보·출처·편수를 연구 응답 하나로 받는다 — 생성 output 을 따로 읽는 API 를 두지 않는다. 카드·절 생성이 쌓이면 키워드 생성은 '최근 끝난 10건'에서 밀려나므로 따로 한 줄 읽는다.

**Files:**
- Modify: `app/services/research_work/views.py` (`work_view` 18-36)
- Modify: `app/api/research_work.py` (`_view` 145-148 앞에 `_concept_candidates`)
- Test: `app/tests/test_research_work_views.py` (`TestWorkView` 221-)
- Test: `app/tests/test_research_work_api.py` (`TestContinue.test_creates_the_work…` 의 WorkView dict 273-279, `TestGetWork` 443-476)

**알아 둘 것:**
- `work_view(work, generations, queue, concept_candidates=None)` — 키워드 인자를 끝에 더해 기존 호출(테스트의 위치 인자 셋)이 그대로 돈다. 응답에는 키를 늘 싣는다(값이 없으면 `None`) — 화면 타입은 선택 필드(`concept_candidates?: KeywordCandidate[] | null`, Task K7).
- `_concept_candidates` 는 `G.output` 한 칸만 `status == "done"`·`kind == "concepts"`·`id DESC LIMIT 1` 로 읽는다. 06e 전 생성의 output 은 `{"concepts": [...], "attempts": [...]}` 라 `candidates` 가 없어 `None` 이다 — 화면은 지금 concepts 를 고른 칩으로 그린다(spec §12-4 칩 UI). 열린(다시 부른) 키워드 생성은 보지 않는다 — 끝나면 그 결과가 최신 done 이 된다.
- 이어가기·GET·PATCH·연구 SSE 의 snapshot(`stream_work` `:401`·`_fresh_work_view` `:447`)이 모두 `_view` 를 타서 함께 싣는다. 조용한 하트비트는 `_view` 를 부르지 않으므로(`test_quiet_heartbeat_reads_only_the_open_generations` 가 문장 2개를 고정) 그 테스트는 그대로다.
- `TestContinue.test_creates_the_work_its_candidates_and_one_concepts_generation` 은 WorkView 전체를 견준다(`:273-279`) — 새 키를 더하므로 기대 dict 에 `"concept_candidates": None` 을 넣는다(Task K2 의 대역 ✎ 과 다른 줄).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_work_views.py` `TestWorkView.test_shape` — 응답에 `concept_candidates` 키가 늘 실린다(값이 없으면 None). old:

```python
                {"id": 7, "kind": "topic_card", "target": "12", "status": "queued",
                 "model": None, "error": None,
                 "position": 2, "eta_sec": 120, "others_ahead": True},
            ],
        }
```

new:

```python
                {"id": 7, "kind": "topic_card", "target": "12", "status": "queued",
                 "model": None, "error": None,
                 "position": 2, "eta_sec": 120, "others_ahead": True},
            ],
            "concept_candidates": None,
        }

    def test_concept_candidates_ride_along(self):
        # 06e 키워드 후보 — 라우터가 최신 done 키워드 생성에서 따로 읽어 넘긴 값을 그대로 싣는다
        work = SimpleNamespace(id=uuid.uuid4(), phase="topics", concepts=["독서 격차"], memo=None, is_example=False,
                               progress={}, topic_id=None, corpus_snapshot=None)
        cands = [{"text": "독서 격차", "source": "both", "n": 3}, {"text": "학교 도서관", "source": "paper", "n": 2}]
        assert work_view(work, [], {}, concept_candidates=cands)["concept_candidates"] == cands
        assert work_view(work, [], {})["concept_candidates"] is None
```

② `app/tests/test_research_work_api.py` `TestContinue.test_creates_the_work_its_candidates_and_one_concepts_generation` — WorkView 전체를 견주는 dict 에 새 키(이어가기 직후에는 끝난 키워드 생성이 없어 None). old:

```python
            "generations": [{"id": gen["id"], "kind": "concepts", "target": None,
                             "status": "queued", "model": None, "error": None,
                             "position": POSITION, "eta_sec": ETA, "others_ahead": False}],
        }
```

new:

```python
            "generations": [{"id": gen["id"], "kind": "concepts", "target": None,
                             "status": "queued", "model": None, "error": None,
                             "position": POSITION, "eta_sec": ETA, "others_ahead": False}],
            "concept_candidates": None,
        }
```

③ 같은 파일 `TestGetWork` 끝(`test_carries_the_picked_topic_the_corpus_and_the_wait` 뒤)에 두 테스트. old:

```python
        assert (body["topic_id"], body["corpus"]) == (7, CORPUS)
        assert {g["id"]: (g["position"], g["eta_sec"], g["others_ahead"]) for g in body["generations"]} == {
            queued: (POSITION, ETA, False), done: (None, None, False)}
```

new:

```python
        assert (body["topic_id"], body["corpus"]) == (7, CORPUS)
        assert {g["id"]: (g["position"], g["eta_sec"], g["others_ahead"]) for g in body["generations"]} == {
            queued: (POSITION, ETA, False), done: (None, None, False)}

    def test_carries_the_latest_done_concept_candidates(self, api):
        # 끝난 생성은 최근 RECENT_FINISHED 건만 싣는다 — 키워드 후보는 그와 따로, 가장 새 done 키워드 생성에서 읽는다
        jid = _work_job(api.engine, concepts=["독서 격차"])
        old = [{"text": "옛 후보", "source": "llm", "n": 0}]
        new = [{"text": "독서 격차", "source": "both", "n": 3}, {"text": "학교 도서관", "source": "paper", "n": 2}]
        add_generation(api.engine, jid, status="done", output={"concepts": ["옛 후보"], "candidates": old})
        add_generation(api.engine, jid, status="done", output={"concepts": ["독서 격차"], "candidates": new})
        for _ in range(11):
            add_generation(api.engine, jid, kind="topic_card", status="done", target="7")
        add_generation(api.engine, jid, status="queued")             # 열린 키워드 생성(다시 부름)은 보지 않는다

        body = api.client.get(f"/api/research/{jid}/work").json()

        assert body["concept_candidates"] == new
        # 최근 끝난 생성 10건을 카드 생성이 채워 키워드 생성은 목록에 없다 — 그래도 후보는 온다
        assert [g["kind"] for g in body["generations"] if g["status"] == "done"] == ["topic_card"] * 10

    def test_an_old_concepts_output_without_candidates_is_null(self, api):
        # 06e 전 키워드(개념) 생성의 output 은 {"concepts": [...]} 뿐이다 — 화면은 concepts 를 고른 칩으로 그린다
        jid = _work_job(api.engine, concepts=["독서 격차"])
        add_generation(api.engine, jid, status="done", output={"concepts": ["독서 격차"], "attempts": []})
        add_generation(api.engine, jid, status="failed")
        no_gen = _work_job(api.engine)

        assert api.client.get(f"/api/research/{jid}/work").json()["concept_candidates"] is None
        assert api.client.get(f"/api/research/{no_gen}/work").json()["concept_candidates"] is None
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_views.py tests/test_research_work_api.py -q -p no:cacheprovider`

Expected: `5 failed, 97 passed, 2 warnings` — `test_research_work_views.py::TestWorkView` 의 `test_shape`(키 없음)·`test_concept_candidates_ride_along`(인자 없음), `test_research_work_api.py` 의 `TestContinue::test_creates_the_work_its_candidates_and_one_concepts_generation`·`TestGetWork::test_carries_the_latest_done_concept_candidates`·`TestGetWork::test_an_old_concepts_output_without_candidates_is_null`(응답에 키 없음 — KeyError)

- [ ] **Step 3: 구현한다**

① `app/services/research_work/views.py` `work_view` — 시그니처·docstring. old:

```python
def work_view(work, generations, queue: dict[int, dict]) -> dict:
    """연구 한 건. generations 는 호출부가 고른 생성(열린 것 전부 + 최근 끝난 것)이고 id 순으로 싣는다.
    queue 는 대기 중(queued) 생성마다 dispatch.queue_info 의 결과(position·eta_sec·others_ahead) — 없는 생성은
    기다리지 않는다(position·eta_sec 는 None). corpus 는 이어가기 때 담은 코퍼스 스냅숏이다."""
```

new:

```python
def work_view(work, generations, queue: dict[int, dict], concept_candidates: list[dict] | None = None) -> dict:
    """연구 한 건. generations 는 호출부가 고른 생성(열린 것 전부 + 최근 끝난 것)이고 id 순으로 싣는다.
    queue 는 대기 중(queued) 생성마다 dispatch.queue_info 의 결과(position·eta_sec·others_ahead) — 없는 생성은
    기다리지 않는다(position·eta_sec 는 None). corpus 는 이어가기 때 담은 코퍼스 스냅숏이다.
    concept_candidates 는 최신 done 키워드(개념) 생성의 output.candidates(06e 제목 고르기) — 호출부가 따로 읽어 넘기고,
    06e 전 생성이거나 끝난 키워드 생성이 없으면 None 이다(키는 늘 싣는다)."""
```

② 같은 함수의 반환 dict 끝. old:

```python
        "generations": [
            {"id": g.id, "kind": g.kind, "target": g.target, "status": g.status,
             "model": g.model, "error": g.error, **_waiting(queue.get(g.id))}
            for g in sorted(generations, key=lambda g: g.id)
        ],
    }
```

new:

```python
        "generations": [
            {"id": g.id, "kind": g.kind, "target": g.target, "status": g.status,
             "model": g.model, "error": g.error, **_waiting(queue.get(g.id))}
            for g in sorted(generations, key=lambda g: g.id)
        ],
        "concept_candidates": concept_candidates,
    }
```

③ `app/api/research_work.py` — `_generations` 아래에 `_concept_candidates`, `_view` 가 넘긴다. 이어가기·GET·PATCH·연구 SSE 의 snapshot(`stream_work`·`_fresh_work_view`)이 모두 `_view` 를 타서 함께 싣는다. old:

```python
async def _view(db: AsyncSession, work: ResearchWork) -> dict:
    gens = await _generations(db, work.id)
    queue = {g.id: await queue_info(db, g) for g in gens if g.status == "queued"}
    return work_view(work, gens, queue)
```

new:

```python
async def _concept_candidates(db: AsyncSession, jid: uuid.UUID) -> list[dict] | None:
    """가장 새 done 키워드(개념) 생성의 후보(output.candidates — 06e 제목 고르기). 끝난 생성은 최근 RECENT_FINISHED 건만
    응답에 실어(_generations) 카드·절 생성이 쌓이면 키워드 생성이 밀려나므로 따로 읽는다. 06e 전 생성의 output 은
    {"concepts": [...]} 뿐이라 None — 화면은 지금 concepts 를 고른 칩으로 그린다."""
    G = ResearchGeneration
    output = await db.scalar(
        select(G.output).where(G.work_id == jid, G.kind == "concepts", G.status == "done")
        .order_by(G.id.desc()).limit(1)
    )
    candidates = output.get("candidates") if isinstance(output, dict) else None
    return candidates if isinstance(candidates, list) else None


async def _view(db: AsyncSession, work: ResearchWork) -> dict:
    gens = await _generations(db, work.id)
    queue = {g.id: await queue_info(db, g) for g in gens if g.status == "queued"}
    return work_view(work, gens, queue, concept_candidates=await _concept_candidates(db, work.id))
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_views.py tests/test_research_work_api.py -q -p no:cacheprovider`

Expected: `102 passed, 2 warnings` (views 18 · api 84)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 세 파일, 통과 = Task 앞 + 3

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/views.py app/api/research_work.py app/tests/test_research_work_views.py app/tests/test_research_work_api.py && git status --short && git commit -m "[Feat] round06e — 연구 응답(WorkView)에 키워드 후보 concept_candidates 를 싣는다(spec §12-4 저장). 최신 done 키워드(개념) 생성의 output.candidates 를 따로 한 줄 읽는다 — 끝난 생성은 최근 10건만 응답에 실어 카드·절 생성이 쌓이면 키워드 생성이 밀려난다. 06e 전 생성(output 에 candidates 없음)·끝난 키워드 생성이 없는 연구는 null 이고 키는 늘 싣는다. 이어가기·GET·PATCH·SSE snapshot 이 모두 _view 를 타서 같은 모양이다"
```

---

### Task K4: 카드 입력에 고른 키워드·제목 규칙 한 줄·[다른 방향]도 지금 키워드

**왜:** spec §12-4 '제목 규칙'·'[다른 방향]도 지금 고른 키워드를 넘긴다(`research_topics.py:149`)'·정함 29. 카드 제목에 고른 키워드를 최소 하나 넣게 하려면 ① 카드 생성 input 에 그때 고른 키워드가 있어야 하고(`seeds.topic_input`) ② 프롬프트가 키워드가 있을 때만 '제목에 하나 이상 글자 그대로' 규칙 한 줄을 붙여야 한다. 예시 제목은 넣지 않고(함정 15), 다시 만들 때 이전 제목을 주지 않는다(함정 26 — 모델이 입력을 옮긴다). [다른 방향]은 키워드(개념) 생성이 열려 있는 동안 막는다 — 끝나기 전의 `work.concepts` 는 비어 있어 키워드 없는 카드가 된다(정함 29).

**Files:**
- Modify: `app/services/research_work/seeds.py` (`topic_input` 175-191 — spec 의 ':346-362' 는 옛 줄)
- Modify: `app/services/research_work/topic_card.py` (머리 docstring 12행 뒤, `_build` 59-67)
- Modify: `app/domains/nl_library/prompts/research_topic_card.yaml` (system 규칙 끝 15행 뒤)
- Modify: `app/api/research_topics.py` (import 20, 상수 39 뒤, `generate_topics` 120-156)
- Modify: `app/models/research_work.py` (머리 주석 Card 29-31 — 주석만)
- Test: `app/tests/test_research_work_seeds.py` (`TestTopicInput` 167-181)
- Test: `app/tests/test_research_work_topic_card.py` (import 7-8, `TestPrompt` 55-71, `TestBuild` 81-93)
- Test: `app/tests/test_research_topics_api.py` (`TestOtherDirection` 끝 — 289-)

**알아 둘 것:**
- 렌더러는 `StrictUndefined` 다(`app/services/prompts.py:22`) — 템플릿이 `keywords` 를 쓰면 `_build` 가 늘 넘겨야 한다. 06e 전 행(다시 부르기 `generations/{gid}/retry` 가 `gen.input` 을 그대로 복사한다 — `research_work.py:378-381`)에는 `keywords` 키가 없으므로 `input.get("keywords") or []` 로 읽고 빈 글을 넘긴다. 문자열 아닌 원소는 거른다.
- **YAML 의 Jinja 줄:** `{%- if keywords %}`·`{%- endif %}` 의 `-` 가 앞 줄바꿈을 지운다 — 키워드가 없으면 06b 프롬프트와 **글자까지 같다**(`test_the_keyword_rule_is_there_only_when_keywords_are_given` 이 그대로 견준다). 키워드는 `" · "` 로 잇는다(`노인 우울 · 사회적 지지`) — 괄호(「」)로 감싸면 모델이 괄호째 제목에 옮길 수 있어 쓰지 않는다. 사용자 메시지(원 질문·씨앗·근거)는 바꾸지 않는다.
- **`TestPrompt.test_no_array_sample_no_example_and_no_figures` 는 고친다**(뼈대는 '그대로 통과 확인'이라 적었지만 실측으로 깨진다) — 지금 검사는 `{{ }}` 만 빼고 `"{"` 를 찾아 `{%- if keywords %}` 에서 떨어진다. Jinja 문(`{% … %}`)도 빼고 보게 한다(배열·JSON 견본 금지라는 뜻은 그대로).
- **뼈대 목록 밖의 ✎:** `test_research_work_seeds.py::TestTopicInput::test_shape` — 입력 dict 에 `"keywords": []` 키가 생겨 전체 비교가 깨진다.
- `generate_topics` 의 409 는 `_writable` 뒤·잠금 전이다 — 넣은 행이 없어 되돌릴 것이 없다. `_concepts_open` 은 06a 라우터의 도우미(`research_work.py:123-129`)를 `:20` 의 같은 import 줄로 가져온다(잡 id·연구 없음·예시 연구 규칙을 두 라우터가 같이 쓰는 기존 방식). 기존 `TestOtherDirection` 테스트는 키워드 생성 행이 없는 연구(`_work_job`)라 새 409 에 걸리지 않는다(실측).
- 카드 입력의 키워드는 `list(work.concepts or [])` — 06a·06b 연구도 그때 칩을 그대로 넘긴다. 기존 `test_two_cards_from_unused_seeds` 의 기대값(`topic_input(QUESTION, seed, REPORT, tid)`)은 `keywords` 기본값이 빈 목록이라 그대로 같다.
- `TestBuild.test_old_rows_without_keywords_still_build` 는 구현 전에도 통과한다(지금 `_build` 는 키워드를 몰라도 돈다) — 구현 뒤 렌더러가 `keywords` 를 요구할 때 옛 행이 깨지지 않게 지키는 회귀 테스트다.
- `test_409_while_keywords_are_being_made` 는 매개변수 둘(queued·running)이라 +2 다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_work_seeds.py` `TestTopicInput.test_shape` — 입력에 `keywords` 가 늘 실린다(넘기지 않으면 빈 목록). old:

```python
            "adopted": 12,
            "corpus": {"n_papers": 144748, "from": "1980", "to": "2017"},
        }

    def test_missing_range_and_counts_are_null(self):
```

new:

```python
            "adopted": 12,
            "corpus": {"n_papers": 144748, "from": "1980", "to": "2017"},
            "keywords": [],
        }

    def test_topic_input_carries_the_keywords_or_an_empty_list(self):
        # 06e D23 — 카드를 만들 때 고른 키워드(work.concepts)를 입력에 싣는다. 넘긴 목록을 복사해 둔다
        seed = pick_seeds(REPORT, limit=1)[0]
        picked = ["노인 우울", "사회적 지지"]
        made = topic_input("q", seed, REPORT, 12, keywords=picked)
        assert made["keywords"] == picked and made["keywords"] is not picked
        assert topic_input("q", seed, REPORT, 12, keywords=None)["keywords"] == []

    def test_missing_range_and_counts_are_null(self):
```

② `app/tests/test_research_work_topic_card.py` `TestPrompt` — 변수 집합에 `keywords`, 키워드 규칙 줄 테스트를 더하고, 배열·JSON 견본 검사가 Jinja 문(`{% if %}`)을 견본으로 세지 않게 한다(그 검사는 `{{ }}` 만 빼고 '{' 를 찾아 지금 그대로면 `{%- if keywords %}` 에서 떨어진다). old:

```python
        assert names == {"question", "heading", "seed", "evidence_list"}

    def test_no_array_sample_no_example_and_no_figures(self):
        # 함정 15 — 원소가 든 배열 견본·JSON 견본·예시는 개수와 분야를 베끼게 한다. 수치는 모델에 주지 않는다(정함 3)
        tpl = get_prompt(PROMPT)
        for text in (tpl.system, tpl.user):
            assert "[" not in text and "{" not in text.replace("{{", "").replace("}}", "")
```

new:

```python
        assert names == {"question", "heading", "seed", "evidence_list", "keywords"}

    def test_the_keyword_rule_is_there_only_when_keywords_are_given(self):
        # 06e D23 — 고른 키워드가 있을 때만 규칙 한 줄. 없으면(옛 행·키워드 없이 넣은 카드) 06b 프롬프트와 글자까지 같다
        rule = "- title 에 다음 키워드 가운데 하나 이상을 글자 그대로 넣습니다: 노인 우울 · 사회적 지지"
        plain, _ = EXECUTOR.build(INPUT)
        with_kw, _ = EXECUTOR.build({**INPUT, "keywords": ["노인 우울", "사회적 지지"]})
        assert rule in with_kw[0]["content"] and "키워드" not in plain[0]["content"]
        assert with_kw[0]["content"].replace("\n" + rule, "") == plain[0]["content"]
        # 사용자 메시지(원 질문·씨앗·근거)는 그대로다 — 다시 만들 때도 이전 제목을 주지 않는다(함정 26)
        assert with_kw[1]["content"] == plain[1]["content"]

    def test_no_array_sample_no_example_and_no_figures(self):
        # 함정 15 — 원소가 든 배열 견본·JSON 견본·예시는 개수와 분야를 베끼게 한다. 수치는 모델에 주지 않는다(정함 3).
        # Jinja 문({% if %})과 변수({{ }})는 견본이 아니다 — 빼고 본다
        tpl = get_prompt(PROMPT)
        for text in (tpl.system, tpl.user):
            body = re.sub(r"\{%.*?%\}", "", text).replace("{{", "").replace("}}", "")
            assert "[" not in body and "{" not in body
```

③ 같은 파일 머리 import — `re`. old:

```python
import asyncio
import json
```

new:

```python
import asyncio
import json
import re
```

④ 같은 파일 `TestBuild` 끝에 옛 행 테스트. old:

```python
        assert "144748" not in user and "144,748" not in user
        assert params == {"max_tokens": 400, "temperature": 0.3}
```

new:

```python
        assert "144748" not in user and "144,748" not in user
        assert params == {"max_tokens": 400, "temperature": 0.3}

    def test_old_rows_without_keywords_still_build(self):
        # 06e 전에 넣은 행엔 keywords 키가 없다 — 다시 부르기(retry)가 그 input 을 그대로 쓴다. 렌더러가 StrictUndefined
        # (services/prompts.py)라 _build 가 늘 넘겨야 한다. 빈 목록·None 도 키워드 규칙이 없는 프롬프트다
        assert "keywords" not in INPUT
        for inp in (INPUT, {**INPUT, "keywords": []}, {**INPUT, "keywords": None}):
            messages, _ = EXECUTOR.build(inp)
            assert "키워드" not in messages[0]["content"]
```

⑤ `app/tests/test_research_topics_api.py` `TestOtherDirection` 끝(`test_example_work_is_read_only` 뒤)에 두 테스트. 기존 `TestOtherDirection` 테스트는 키워드 생성 행이 없는 연구라(`_work_job`) 새 409 에 걸리지 않는다. old:

```python
    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        res = api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"})
        assert res.status_code == 409 and res.json()["detail"] == "예시 연구는 읽기 전용입니다"
        assert _rows(api.engine, ResearchTopic) == []
```

new:

```python
    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        res = api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"})
        assert res.status_code == 409 and res.json()["detail"] == "예시 연구는 읽기 전용입니다"
        assert _rows(api.engine, ResearchTopic) == []

    def test_cards_take_the_current_keywords(self, api):
        # 06e D23 — [다른 방향]도 지금 고른 키워드(work.concepts)를 카드 입력에 넘긴다(spec §12-4)
        jid = _work_job(api.engine, concepts=["노인 우울", "사회적 지지"])
        add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)

        res = api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"})

        assert res.status_code == 200
        made = [t for t in _rows(api.engine, ResearchTopic) if t["origin"] == "other"]
        gens = _rows(api.engine, ResearchGeneration)
        assert len(gens) == 2 and [g["input"]["keywords"] for g in gens] == [["노인 우울", "사회적 지지"]] * 2
        for topic, gen in zip(made, gens):
            assert gen["input"] == topic_input(QUESTION, topic["seed"], REPORT, topic["id"],
                                               keywords=["노인 우울", "사회적 지지"])

    @pytest.mark.parametrize("status", ["queued", "running"])
    def test_409_while_keywords_are_being_made(self, api, status):
        # 정함 29 — 키워드 생성이 끝나기 전의 work.concepts 는 비어 있다. 그 값으로 카드를 만들지 않는다
        jid = _work_job(api.engine)
        concepts = add_generation(api.engine, jid, kind="concepts", status=status)

        res = api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"})

        assert res.status_code == 409
        assert res.json()["detail"] == "키워드를 고르는 중입니다 — 끝난 뒤 다시 만들어 주세요"
        assert _rows(api.engine, ResearchTopic) == []
        assert [g["id"] for g in _rows(api.engine, ResearchGeneration)] == [concepts]
        assert api.dispatch.calls == 0 and api.events == []
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_seeds.py tests/test_research_work_topic_card.py tests/test_research_topics_api.py -q -p no:cacheprovider`

Expected: `7 failed, 106 passed, 2 warnings` — `test_research_work_seeds.py::TestTopicInput` 의 `test_shape`·`test_topic_input_carries_the_keywords_or_an_empty_list`(키·인자 없음), `test_research_work_topic_card.py::TestPrompt` 의 `test_variables_are_fixed`·`test_the_keyword_rule_is_there_only_when_keywords_are_given`(변수·규칙 줄 없음), `test_research_topics_api.py::TestOtherDirection` 의 `test_cards_take_the_current_keywords`(input 에 keywords 없음)·`test_409_while_keywords_are_being_made[queued]`·`[running]`(200 이 온다)

- [ ] **Step 3: 구현한다**

① `app/services/research_work/seeds.py` `topic_input`(dev `da80f23` `:175-191` — spec 의 ':346-362' 는 옛 줄) — 시그니처·docstring. old:

```python
def topic_input(question: str, seed: dict, report: dict, topic_id: int) -> dict:
    """주제 카드 생성 1건의 입력(계약 §3 topic_card input). 근거 후보는 E1 부터 차례로 번호를 붙인다 —
    호출마다 붙이는 로컬 번호이고 카드에는 cnts_id 로 저장한다(spec §3 [E#])."""
```

new:

```python
def topic_input(question: str, seed: dict, report: dict, topic_id: int, keywords: list[str] | None = None) -> dict:
    """주제 카드 생성 1건의 입력(계약 §3 topic_card input). 근거 후보는 E1 부터 차례로 번호를 붙인다 —
    호출마다 붙이는 로컬 번호이고 카드에는 cnts_id 로 저장한다(spec §3 [E#]). keywords 는 카드를 만들 때 고른
    키워드(06e D23 — work.concepts)이고 제목 규칙·검사가 읽는다. 06e 전 행에는 이 키가 없다(읽는 쪽이 or [])."""
```

② 같은 함수의 반환 dict 끝. old:

```python
        "adopted": seed.get("adopted"),
        "corpus": _corpus(report if isinstance(report, dict) else {}),
    }
```

new:

```python
        "adopted": seed.get("adopted"),
        "corpus": _corpus(report if isinstance(report, dict) else {}),
        "keywords": list(keywords or []),
    }
```

③ `app/services/research_work/topic_card.py` 머리 docstring — '표현' 줄 다음에 키워드 줄. old:

```python
  - 표현: 제목·질문의 단정 표현은 soften_claims 로 바꾸고, [F#] 밖 숫자는 numbers_outside 로 센다('확인 필요').
```

new:

```python
  - 표현: 제목·질문의 단정 표현은 soften_claims 로 바꾸고, [F#] 밖 숫자는 numbers_outside 로 센다('확인 필요').
  - 키워드(06e D23): 고른 키워드(input.keywords)를 넘기면 프롬프트에 '제목에 하나 이상 글자 그대로' 규칙 한 줄이 붙는다.
    예시 제목·이전 제목은 주지 않는다(함정 15·26). 06e 전 행(keywords 없음)은 06b 프롬프트 그대로다.
```

④ 같은 파일 `_build`. old:

```python
    system, user, params = get_prompt(PROMPT).render(
        question=input.get("question") or "",
        heading=seed.get("heading") or "",
        seed=seed.get("text") or "",
        evidence_list=_evidence_list(input.get("papers") or []),
    )
```

new:

```python
    system, user, params = get_prompt(PROMPT).render(
        question=input.get("question") or "",
        heading=seed.get("heading") or "",
        seed=seed.get("text") or "",
        evidence_list=_evidence_list(input.get("papers") or []),
        # 렌더러가 StrictUndefined 라(services/prompts.py) 늘 넘긴다 — 빈 글이면 프롬프트의 키워드 규칙 줄이 빠진다
        keywords=" · ".join(k for k in (input.get("keywords") or []) if isinstance(k, str)),
    )
```

⑤ `app/domains/nl_library/prompts/research_topic_card.yaml` — 규칙 목록 끝에 키워드가 있을 때만 한 줄. `{%-`·`-%}` 가 앞 줄바꿈을 지워 키워드가 없으면 06b 프롬프트와 글자까지 같다. 예시 제목은 넣지 않는다(함정 15). old:

```yaml
  - '연구가 없다'·'전무하다'·'최초' 처럼 단정하지 않습니다. 주어진 논문으로 확인한 것만 씁니다.
```

new:

```yaml
  - '연구가 없다'·'전무하다'·'최초' 처럼 단정하지 않습니다. 주어진 논문으로 확인한 것만 씁니다.
  {%- if keywords %}
  - title 에 다음 키워드 가운데 하나 이상을 글자 그대로 넣습니다: {{ keywords }}
  {%- endif %}
```

⑥ `app/api/research_topics.py` import — 06a 라우터 도우미 줄에 `_concepts_open`(키워드 생성이 열려 있나). old:

```python
from api.research_work import _get_job, _get_work, _job_uuid, _send_dispatch, _writable
```

new:

```python
from api.research_work import _concepts_open, _get_job, _get_work, _job_uuid, _send_dispatch, _writable
```

⑦ 같은 파일 상수. old:

```python
EMPTY_CARD_NEEDS_BOTH = "빈 카드는 제목과 연구 질문을 함께 보내 주세요"
```

new:

```python
EMPTY_CARD_NEEDS_BOTH = "빈 카드는 제목과 연구 질문을 함께 보내 주세요"
# 키워드(개념) 생성이 열려 있는 동안의 [다른 방향]·[이 키워드로 다시 만들기] — 그동안 work.concepts 는 비었거나 곧 바뀐다
KEYWORDS_BUSY = "키워드를 고르는 중입니다 — 끝난 뒤 다시 만들어 주세요"
```

⑧ 같은 파일 `generate_topics`([다른 방향]) — docstring·키워드 생성 중 409(정함 29 — 잠금 전이라 되돌릴 것이 없다)·카드 입력에 지금 키워드. old:

```python
    """[다른 방향] — 쓰지 않은 보고서 씨앗으로 카드 OTHER_DIRECTION_CARDS 장(origin other, 자리 없음). 연구별
    잠금이 '쓴 씨앗 읽기 → 주제·생성 넣기' 를 한 줄로 세운다 — 두 번 눌러도 같은 씨앗이 두 장 되지 않는다."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    job = await _get_job(db, jid)
```

new:

```python
    """[다른 방향] — 쓰지 않은 보고서 씨앗으로 카드 OTHER_DIRECTION_CARDS 장(origin other, 자리 없음). 연구별
    잠금이 '쓴 씨앗 읽기 → 주제·생성 넣기' 를 한 줄로 세운다 — 두 번 눌러도 같은 씨앗이 두 장 되지 않는다.
    카드 입력에는 지금 고른 키워드(work.concepts)를 싣는다(06e D23). 키워드 생성이 열려 있으면 409 — 끝나기 전의
    concepts 는 비어 있어 키워드 없는 카드가 된다(06e 정함 29)."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    if await _concepts_open(db, jid):
        raise HTTPException(status_code=409, detail=KEYWORDS_BUSY)
    job = await _get_job(db, jid)
```

⑨ 같은 함수의 카드 입력(dev `da80f23` `:149`). old:

```python
        gen_id = await enqueue_generation(db, jid, kind="topic_card", target=str(topic_id),
                                          input=topic_input(job.question, seed, report, topic_id))
```

new:

```python
        gen_id = await enqueue_generation(
            db, jid, kind="topic_card", target=str(topic_id),
            input=topic_input(job.question, seed, report, topic_id, keywords=list(work.concepts or [])),
        )
```

⑩ `app/models/research_work.py` 머리 주석의 Card 모양(주석만 — Task A1·Task X1 이 고친 Outline·Section 줄과 겹치지 않는다). old:

```python
  Card      = {"title": str, "question": str, "evidence": [cnts_id], "figure_sentence": str|null,
               "figures": [Figure], "latest_year": int|null, "edited": bool,
               "checks": {"numbers": [str], "softened": int, "recovered": int}, "gen_id": int|null}
```

new:

```python
  Card      = {"title": str, "question": str, "evidence": [cnts_id], "figure_sentence": str|null,
               "figures": [Figure], "latest_year": int|null, "edited": bool,
               "keywords": [str],                               — 만들 때 넘긴 고른 키워드(06e — 옛 카드엔 없음)
               "checks": {"numbers": [str], "softened": int, "recovered": int}, "gen_id": int|null}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_seeds.py tests/test_research_work_topic_card.py tests/test_research_topics_api.py tests/test_research_work_api.py tests/test_research_work_models.py -q -p no:cacheprovider`

Expected: `237 passed, 2 warnings` (seeds 23 · topic_card 51 · topics 39 · api 84 · models 40 — `test_research_work_models.py` 는 머리 주석만 바뀐 ORM 이 0007 과 같은지 그대로 본다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 세 파일, 통과 = Task 앞 + 6

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/seeds.py app/services/research_work/topic_card.py app/domains/nl_library/prompts/research_topic_card.yaml app/api/research_topics.py app/models/research_work.py app/tests/test_research_work_seeds.py app/tests/test_research_work_topic_card.py app/tests/test_research_topics_api.py && git status --short && git commit -m "[Feat] round06e — 주제 카드 입력에 고른 키워드(keywords)를 싣고, 키워드가 있을 때만 프롬프트에 'title 에 다음 키워드 가운데 하나 이상을 글자 그대로 넣습니다' 한 줄을 붙인다(D23, spec §12-4 제목 규칙). 키워드가 없으면 06b 프롬프트와 글자까지 같고({%- if %}), 06e 전 행(keywords 없음)도 그대로 돈다 — 렌더러가 StrictUndefined 라 _build 가 늘 넘긴다. 예시 제목·이전 제목은 주지 않는다(함정 15·26). [다른 방향]도 지금 고른 키워드를 넘기고, 키워드 생성이 열려 있는 동안은 409 KEYWORDS_BUSY(06e 정함 29 — 끝나기 전의 concepts 는 비어 있다). 프롬프트 견본 검사는 Jinja 문을 견본으로 세지 않게 고친다"
```

---

### Task K5: 카드는 키워드가 정해진 뒤 씨앗 자리마다 한 번만 — 이어가기·개념 반영·취소

**왜:** spec §12-4 '카드 시점'(D23), 정함 25·29. 지금은 이어가기 때 개념 1건과 카드 4건이 한꺼번에 줄을 선다(`research_work.py:208-224`) — 카드가 키워드를 모른 채 만들어진다. 06e 는 주제 행(slot 1~4, 씨앗)만 이어가기 때 넣고, `topic_card` 생성은 키워드(개념) 생성을 반영할 때(`apply.py:23-31`) 같은 트랜잭션에서 그때 고른 키워드로 넣는다. 넣는 함수 하나(`topic_card.enqueue_seed_cards`)를 done 반영(세 번 다 못 얻은 빈 결과도 done — §6-3)과 취소 API 가 부른다. '한 번만'은 **씨앗 자리 행마다** 본다(정함 29) — '그 연구에 카드 생성이 하나라도 있으면 안 넣음'으로 하면 키워드 생성이 줄을 서는 사이 [다른 방향]이 먼저 카드를 만든 연구는 씨앗 카드 4장이 영영 생기지 않는다(Task K4 가 키워드 생성이 열린 동안의 [다른 방향]을 막지만, 키워드 생성이 failed 인 사이에는 [다른 방향]이 열린다).

**Files:**
- Modify: `app/services/research_work/topic_card.py` (Task K4 뒤 기준 — import 17-26, `apply` 끝(dev `da80f23` `:216` — Task K4 뒤 `:220`) 뒤에 `enqueue_seed_cards`)
- Modify: `app/services/research_work/apply.py` (import 10-11, `apply_result` 14-31)
- Modify: `app/api/research_work.py` (Task K2·Task K3 뒤 기준 — import 의 enqueue·seeds 줄, `continue_research` docstring 180-183·씨앗 루프 212-224, `cancel_generation` 325-348)
- Test: `app/tests/test_research_work_topic_card.py` (import, 파일 끝에 `TestEnqueueSeedCards`)
- Test: `app/tests/test_research_work_dispatch.py` (import 13-15, `TestApplyResult` 359-395)
- Test: `app/tests/test_research_work_api.py` (`TestContinueSeeds` 367-441, `TestCancelGeneration` 끝 768-771, `TestEndToEnd` 1123)
- Test: `app/tests/test_research_work_tasks.py` (`TestDispatch` 268·311)
- Test: `app/tests/test_research_work_executor.py` (`TestApplyDelegation.test_concepts_keep_the_06a_branch` 205)
- Test: `app/tests/test_research_topics_api.py` (`TestEndToEnd` 562-)

**알아 둘 것:**
- **`enqueue_seed_cards(db, work_id, keywords) -> list[tuple[int, int]]`** — ① `slot IS NOT NULL AND origin = 'report_seed'` 주제 행을 slot 순으로 읽고 ② 그 행 id 들을 target 으로 하는 `topic_card` 생성이 (상태 무관 — queued·running·done·failed·canceled) 이미 있는 target 집합을 한 번에 읽어 그 행은 건너뛴다 ③ 남은 행이 없으면 `[]`(잡도 읽지 않는다) ④ 있으면 잡의 `question`·`report` 두 칸만 읽어(`select(ResearchJob.question, ResearchJob.report)` — 연구 id = 잡 id) 행마다 `enqueue_generation(…, kind="topic_card", target=str(tid), input=topic_input(…, keywords=keywords))`(우선순위 기본 `PRIORITY_USER` — 이어가기가 넣던 값과 같다). `None`(그 사이 열린 생성)이면 그 자리는 건너뛴다. 커밋하지 않는다 — 디스패처 `finish`·취소 API 의 트랜잭션에 묶인다(도는 사이 취소돼 `finish` 가 반영을 되돌리면 카드 생성도 함께 사라진다). origin other·user 카드는 보지 않는다.
- **import 순환 없음** — `topic_card` 가 `enqueue`(모델만)·`seeds`(순수)·`models.research` 를 import 하고, `apply` 가 `topic_card` 를 import 한다(`apply` 는 이미 `executors`→`topic_card` 를 거친다). `api/research_work.py` 도 `topic_card` 를 import 한다(이미 `executors` 로 거친다).
- **반영(워커):** `apply_result` 의 concepts 분기는 개념이 있으면 지금처럼 칩을 쓰고(빈 결과면 칩을 건드리지 않는다) **그 뒤 늘** `enqueue_seed_cards(db, gen.work_id, concepts)` — 빈 결과면 키워드 없이 넣는다. result 는 `{"concepts": [...], "cards": [gen_id]}`(1-4). 넣은 카드의 queued 이벤트는 따로 보내지 않는다 — 화면이 concepts done 에 `topics`·`work` 를 다시 읽는다(정함 25, Task K7 의 `RELOAD.concepts`). 워커 `_close` 가 `has_queued` 를 보고 다음 디스패치를 보낸다(`research_work_tasks.py:241-242`) — 회수기·`research_work_tasks.py` 는 고치지 않는다.
- **취소(API):** kind concepts 를 queued 에서 취소하면 같은 트랜잭션에서 `enqueue_seed_cards(db, jid, [])` → 커밋 → generation canceled 이벤트 → 카드가 있으면 `_send_dispatch()` 와 카드마다 `queued_event`(정함 25 — 화면이 다시 읽을 계기가 없다). 그 밖의 kind 취소는 지금과 같다(디스패치 없음 — 기존 `test_queued_generation_is_canceled` 는 씨앗 자리가 없는 연구라 그대로 통과한다).
- **failed(회수기·예외)** 는 카드가 들어가지 않는다 — 키워드 [다시 부르기](retry)가 done 이 될 때 들어간다. 화면은 그동안 빈 슬롯을 'blocked'(키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다)로 그린다(Task K7·Task K8). 키워드를 직접 넣고 저장했으면 [이 키워드로 다시 만들기](Task K6 — 카드 없는 후보 씨앗 행도 대상)로 카드를 받는다.
- **이어가기:** 씨앗 루프는 주제 행만 넣는다(`RETURNING` 이 필요 없어 `db.execute`). `topic_input` 은 이어가기에서 쓰지 않으므로 import 에서 뺀다 — 그래서 `test_a_failure_while_adding_cards_leaves_nothing_behind` 가 꽂던 대역 자리(`api.router.topic_input`)가 없어진다. 실패를 주제 행 INSERT 에서 DB 쪽이 내게 바꾼다(`before_cursor_execute` 에서 RuntimeError — 감싸이지 않고 그대로 올라온다, 실측). 이 테스트는 구현 전에도 통과한다(지금 이어가기도 주제 행을 같은 문장으로 넣는다).
- **뼈대 목록 밖의 ✎(실측):** `test_research_work_api.py` 의 `test_second_continue_adds_no_topic_or_card`(생성 5 → 1)·`TestEndToEnd::test_continue_then_the_dispatcher_fills_the_concepts`(payload 에 `cards`), `test_research_work_tasks.py::TestDispatch` 의 두 이벤트 result, `test_research_work_executor.py::TestApplyDelegation::test_concepts_keep_the_06a_branch`(payload 에 `cards`). `test_research_topics_api.py::TestEndToEnd` 는 가짜 LLM 이 06e 키(`keywords`)로 답하고 카드 제목에 고른 키워드를 넣게 바꾼다 — Task K9 의 제목 검사가 들어와도 첫 답에 통과한다.
- **SQLite 대역의 부분 유니크 인덱스**(`ux_research_generations_running` — 연구마다 running 1건, `sqlite_where` 로 테스트에도 있다) 때문에 `test_a_second_concepts_result_queues_no_more_cards` 는 첫 키워드 생성을 done, 둘째를 running 으로 둔다(반영은 상태를 보지 않는다).
- **배포 순서(마무리 §7-10 그대로):** 워커(celery-research-plan)를 fastapi 보다 먼저 바꾼다. fastapi 만 새것이면 이어가기가 카드 생성을 넣지 않는데 옛 워커의 반영도 넣지 않아 그 사이 이어간 연구의 카드가 생기지 않는다. 06b 에 이어간 연구(이미 카드 생성이 있다)는 새 반영이 자리마다 건너뛰어 그대로다.
- `test_a_seed_slot_that_already_has_a_card_generation_gets_none` 은 매개변수 셋(done·failed·canceled)이라 +3 이다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_work_topic_card.py` 머리 import — 씨앗 카드 테스트가 쓰는 잡 모델·카드 입력. old:

```python
from models.research_work import GEN_KINDS, ResearchGeneration, ResearchTopic, ResearchWork
```

new:

```python
from models.research import ResearchJob
from models.research_work import GEN_KINDS, ResearchGeneration, ResearchTopic, ResearchWork
```

② 같은 파일 import 의 실행기 모듈 줄 다음. old:

```python
from services.research_work.markers import numbers_outside, soften_claims
```

new:

```python
from services.research_work.markers import numbers_outside, soften_claims
from services.research_work.seeds import topic_input
```

③ 같은 파일 끝(`TestApply` 뒤)에 붙인다:

```python
# ── 씨앗 카드 넣기(enqueue_seed_cards — 06e D23 '카드 시점') ──────────────────────

SEED_QUESTION = "노인의 우울과 사회적 지지에 관한 연구가 궁금해"
SEED_REPORT = {
    "range": {"from": "1980", "to": "2017", "n_papers": 144748},
    "evidence": {"E1": {"cnts_id": "P1", "meta": {"title": "노인의 사회적 지지와 우울의 관계", "pub_date": "2013"}},
                 "E2": {"cnts_id": "P2", "meta": {"title": "독거노인의 사회적 관계망", "pub_date": "2015"}}},
}
KEYWORDS = ["노인 우울", "사회적 지지"]


def _seed(n: int) -> dict:
    return {"key": f"future:{n}:0", "kind": "future", "section_idx": n, "subq_idx": n, "heading": f"절 {n}",
            "text": f"씨앗 {n}", "papers": ["P1", "P2"], "adopted": 5}


def _seed_work(engine, slots: int = 4) -> tuple:
    """이어가기가 남긴 모양 — 잡(질문·보고서)·연구·씨앗 자리 주제 행(slot 1~), 카드 생성은 아직 없다."""
    wid = add_research_job(engine, status="completed", stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == wid)
                     .values(question=SEED_QUESTION, report=SEED_REPORT))
    add_work(engine, wid)
    return wid, [add_topic(engine, wid, slot=n, seed=_seed(n)) for n in range(1, slots + 1)]


def _enqueue(engine, wid, keywords, *, commit: bool = True):
    async def _go():
        db = AsyncSessionOverSync(engine)
        try:
            out = await topic_card.enqueue_seed_cards(db, wid, keywords)
            await (db.commit() if commit else db.rollback())
            return out
        finally:
            await db.close()

    return asyncio.run(_go())


def _card_gens(engine, wid):
    table = ResearchGeneration.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table).where(table.c.work_id == wid, table.c.kind == "topic_card")
                            .order_by(table.c.id)).mappings().all()


class TestEnqueueSeedCards:
    def test_one_card_generation_per_seed_slot_with_the_keywords(self, engine):
        wid, tids = _seed_work(engine)

        out = _enqueue(engine, wid, KEYWORDS)

        gens = _card_gens(engine, wid)
        assert out == [(tid, g["id"]) for tid, g in zip(tids, gens)]
        assert [(g["target"], g["status"], g["priority"]) for g in gens] == [(str(t), "queued", 10) for t in tids]
        for n, (tid, gen) in enumerate(zip(tids, gens), start=1):
            assert gen["input"] == topic_input(SEED_QUESTION, _seed(n), SEED_REPORT, tid, keywords=KEYWORDS)

    @pytest.mark.parametrize("status", ["done", "failed", "canceled"])
    def test_a_seed_slot_that_already_has_a_card_generation_gets_none(self, engine, status):
        # 상태와 상관없이 — 카드 생성을 한 번 넣은 자리는 다시 넣지 않는다(키워드를 다시 불러 반영돼도 또 들어가지 않는다)
        wid, tids = _seed_work(engine)
        add_generation(engine, wid, kind="topic_card", status=status, target=str(tids[0]))

        out = _enqueue(engine, wid, KEYWORDS)

        assert [tid for tid, _ in out] == tids[1:]
        assert len(_card_gens(engine, wid)) == 4
        assert _enqueue(engine, wid, KEYWORDS) == []            # 두 번째 반영은 아무것도 넣지 않는다

    def test_other_direction_cards_do_not_block_the_seed_cards(self, engine):
        # 키워드 생성이 줄을 서는 사이 [다른 방향]이 먼저 카드를 만든 연구 — '그 연구에 카드 생성이 하나라도 있으면 안
        # 넣는다'로 하면 씨앗 카드 4장이 영영 생기지 않는다(06e 정함 29). 판정은 씨앗 자리 행마다다
        wid, tids = _seed_work(engine)
        other = add_topic(engine, wid, origin="other", seed=_seed(9))
        add_generation(engine, wid, kind="topic_card", status="done", target=str(other))

        out = _enqueue(engine, wid, KEYWORDS)

        assert [tid for tid, _ in out] == tids

    def test_user_and_other_direction_topics_get_none(self, engine):
        wid, tids = _seed_work(engine, slots=2)
        add_topic(engine, wid, origin="other", seed=_seed(8))
        add_topic(engine, wid, origin="user", card={"title": "내 주제", "question": "내 질문?", "evidence": []})

        out = _enqueue(engine, wid, [])

        assert [tid for tid, _ in out] == tids
        # 키워드 없이 넣으면(취소·빈 결과) 입력의 keywords 가 비고 프롬프트에 키워드 규칙이 붙지 않는다
        assert [g["input"]["keywords"] for g in _card_gens(engine, wid)] == [[], []]

    def test_does_not_commit(self, engine):
        wid, _ = _seed_work(engine)

        assert len(_enqueue(engine, wid, KEYWORDS, commit=False)) == 4
        assert _card_gens(engine, wid) == []
```

④ `app/tests/test_research_work_dispatch.py` 머리 import — `add_topic`. old:

```python
from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
```

new:

```python
from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_topic, add_work, make_engine,
)
```

⑤ 같은 파일 `TestApplyResult.test_concepts_replace_the_chips_and_reset_membership` — 결과에 넣은 카드 생성 id(`cards`). old:

```python
        row = _work_row(engine, w1)
        assert payload == {"concepts": ["독서 격차", "청소년"]}
```

new:

```python
        row = _work_row(engine, w1)
        assert payload == {"concepts": ["독서 격차", "청소년"], "cards": []}      # 이 연구엔 씨앗 자리가 없다
```

⑥ 같은 파일 `TestApplyResult.test_an_empty_result_keeps_the_chips` 와 새 테스트 둘 — 빈 결과도 씨앗 카드를 (키워드 없이) 넣는 자리이고, 두 번째 결과는 카드를 더 넣지 않는다. old:

```python
        payload, log = _call(engine, _apply)

        row = _work_row(engine, w1)
        assert payload == {"concepts": []} and log == []
        assert (row["concepts"], row["concept_members"]) == (["사용자 개념"], {"사용자 개념": ["C1"]})
```

new:

```python
        payload, log = _call(engine, _apply)

        row = _work_row(engine, w1)
        assert payload == {"concepts": [], "cards": []}
        # 씨앗 자리를 찾는 읽기만 있다 — 이 연구엔 주제 행이 없어 연구도 생성도 바꾸지 않는다
        assert not [s for s in log if s.startswith(("INSERT", "UPDATE"))]
        assert (row["concepts"], row["concept_members"]) == (["사용자 개념"], {"사용자 개념": ["C1"]})

    def test_an_empty_result_still_queues_the_seed_cards_without_keywords(self, engine):
        # 06e D23 — 세 번 다 못 얻은 빈 결과도 done 이다. 칩은 그대로 두고 씨앗 카드는 키워드 없이 넣는다
        w1 = _work(engine, concepts=["사용자 개념"])
        tids = [add_topic(engine, w1, slot=n, seed={"key": f"future:{n}:0", "heading": "절", "text": "씨앗",
                                                     "papers": ["P1", "P2"], "adopted": 3}) for n in (1, 2)]
        gid = _gen(engine, w1, minute=0, kind="concepts", status="running", started_at=T0)

        async def _apply(db):
            payload = await apply_result(db, await db.get(ResearchGeneration, gid), {"concepts": []})
            await db.commit()
            return payload

        payload, _ = _call(engine, _apply)

        with engine.connect() as conn:
            cards = conn.execute(sa.select(GEN).where(GEN.c.kind == "topic_card").order_by(GEN.c.id)).mappings().all()
        assert payload == {"concepts": [], "cards": [c["id"] for c in cards]}
        assert [(c["target"], c["status"], c["input"]["keywords"]) for c in cards] == [
            (str(t), "queued", []) for t in tids]
        assert _work_row(engine, w1)["concepts"] == ["사용자 개념"]

    def test_a_second_concepts_result_queues_no_more_cards(self, engine):
        # 키워드를 다시 불러(retry) 두 번째 결과가 반영돼도 씨앗 카드는 자리마다 한 번만 — 칩만 바뀐다
        w1 = _work(engine)
        add_topic(engine, w1, slot=1, seed={"key": "future:1:0", "heading": "절", "text": "씨앗",
                                            "papers": ["P1", "P2"], "adopted": 3})
        first = _gen(engine, w1, minute=0, kind="concepts", status="done", started_at=T0)
        second = _gen(engine, w1, minute=1, kind="concepts", status="running", started_at=T0)

        def _apply(gid: int, concepts: list[str]) -> dict:
            async def _go(db):
                payload = await apply_result(db, await db.get(ResearchGeneration, gid), {"concepts": concepts})
                await db.commit()
                return payload

            return _call(engine, _go)[0]

        assert len(_apply(first, ["독서 격차", "청소년"])["cards"]) == 1
        assert _apply(second, ["가정 환경", "독서 격차"]) == {"concepts": ["가정 환경", "독서 격차"], "cards": []}
        with engine.connect() as conn:
            cards = conn.execute(sa.select(GEN).where(GEN.c.kind == "topic_card")).mappings().all()
        assert [c["input"]["keywords"] for c in cards] == [["독서 격차", "청소년"]]
        assert _work_row(engine, w1)["concepts"] == ["가정 환경", "독서 격차"]
```

⑦ `app/tests/test_research_work_api.py` `TestContinueSeeds` 첫 테스트 — 이름과 기대를 바꾼다(카드 생성은 아직 없다). old:

```python
    def test_report_seeds_become_four_topics_each_with_one_card_generation(self, api):
        jid = _seed_job(api.engine)

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 200
        topics = _rows(api.engine, ResearchTopic)
        assert [(t["slot"], t["origin"], t["state"], t["card"], t["seed"]["key"]) for t in topics] == [
            (n, "report_seed", "candidate", {}, key) for n, key in enumerate(SEED_KEYS, start=1)]
        assert all(t["corpus_snapshot"] == CORPUS and t["parent_id"] is None for t in topics)
        gens = _rows(api.engine, ResearchGeneration)
        assert [(g["kind"], g["target"], g["priority"], g["status"]) for g in gens] == [
            ("concepts", None, 10, "queued"),
            *[("topic_card", str(t["id"]), 10, "queued") for t in topics]]
        for topic, gen in zip(topics, gens[1:]):
            assert gen["input"] == topic_input("청소년 독서 격차", topic["seed"], SEED_REPORT, topic["id"])
        (work,) = _rows(api.engine, ResearchWork)
```

new:

```python
    def test_report_seeds_become_four_topics_without_card_generations_yet(self, api):
        # 06e D23 '카드 시점' — 주제 행(씨앗 자리 slot 1~4)은 이어가기 때, 카드 생성은 키워드가 정해진 뒤 키워드 생성의
        # 반영(apply_result)·취소(cancel)가 고른 키워드로 넣는다(topic_card.enqueue_seed_cards)
        jid = _seed_job(api.engine)

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 200
        topics = _rows(api.engine, ResearchTopic)
        assert [(t["slot"], t["origin"], t["state"], t["card"], t["seed"]["key"]) for t in topics] == [
            (n, "report_seed", "candidate", {}, key) for n, key in enumerate(SEED_KEYS, start=1)]
        assert all(t["corpus_snapshot"] == CORPUS and t["parent_id"] is None for t in topics)
        gens = _rows(api.engine, ResearchGeneration)
        assert [(g["kind"], g["target"], g["priority"], g["status"]) for g in gens] == [
            ("concepts", None, 10, "queued")]
        (work,) = _rows(api.engine, ResearchWork)
```

⑧ 같은 클래스 `test_second_continue_adds_no_topic_or_card` — 생성은 키워드 생성 1건뿐이다. old:

```python
        assert len(_rows(api.engine, ResearchTopic)) == 4
        assert len(_rows(api.engine, ResearchGeneration)) == 5
```

new:

```python
        assert len(_rows(api.engine, ResearchTopic)) == 4
        assert len(_rows(api.engine, ResearchGeneration)) == 1
```

⑨ 같은 클래스 `test_a_failure_while_adding_cards_leaves_nothing_behind` → 주제 행 넣기 실패로. 이어가기는 이제 `topic_input` 을 부르지 않는다(대역을 꽂을 자리가 없다) — 주제 행 INSERT 에서 DB 쪽이 실패하게 한다. old:

```python
    def test_a_failure_while_adding_cards_leaves_nothing_behind(self, api, monkeypatch):
        # 씨앗 카드까지 한 커밋이다 — 중간에 실패하면 연구 행도 남지 않아 다음 이어가기가 처음부터 만든다
        def _broken(*args, **kwargs):
            raise RuntimeError("카드 입력을 만들지 못했다")

        monkeypatch.setattr(api.router, "topic_input", _broken)
        jid = _seed_job(api.engine)

        with pytest.raises(RuntimeError):
            api.client.post(f"/api/research/{jid}/work/continue", headers=A)
```

new:

```python
    def test_a_failure_while_adding_topics_leaves_nothing_behind(self, api):
        # 주제 행까지 한 커밋이다 — 주제 행을 넣다 실패하면 연구 행·후보·키워드 생성도 남지 않아 다음 이어가기가 처음부터 만든다
        def _broken(conn, cursor, statement, params, context, executemany):
            if statement.startswith("INSERT INTO research_topics"):
                raise RuntimeError("주제 행을 넣지 못했다")

        jid = _seed_job(api.engine)
        sa.event.listen(api.engine, "before_cursor_execute", _broken)
        try:
            with pytest.raises(RuntimeError):
                api.client.post(f"/api/research/{jid}/work/continue", headers=A)
        finally:
            sa.event.remove(api.engine, "before_cursor_execute", _broken)
```

⑩ 같은 파일 `TestCancelGeneration` 끝(`test_example_work_is_read_only` 뒤)에 새 테스트. old:

```python
    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        gid = add_generation(api.engine, jid)
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/cancel").status_code == 409
```

new:

```python
    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        gid = add_generation(api.engine, jid)
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/cancel").status_code == 409

    def test_canceling_concepts_queues_the_seed_cards_without_keywords(self, api):
        # 06e D23 — 사용자가 키워드 생성을 취소하면 같은 트랜잭션에서 씨앗 카드를 키워드 없이 넣는다. 워커 반영과 달리
        # 화면이 다시 읽을 계기(concepts done)가 없어 커밋 뒤 디스패치와 카드마다 queued 이벤트를 보낸다(06e 정함 25)
        jid = _seed_job(api.engine)
        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200
        (concepts,) = _rows(api.engine, ResearchGeneration)
        api.events.clear()
        api.dispatch.calls = 0

        res = api.client.post(f"/api/research/{jid}/generations/{concepts['id']}/cancel")

        assert res.status_code == 200 and res.json() == {"gen_id": concepts["id"], "status": "canceled"}
        topics = _rows(api.engine, ResearchTopic)
        first, *cards = _rows(api.engine, ResearchGeneration)
        assert first["status"] == "canceled"
        assert [(c["kind"], c["target"], c["status"]) for c in cards] == [
            ("topic_card", str(t["id"]), "queued") for t in topics]
        for topic, card in zip(topics, cards):
            assert card["input"] == topic_input("청소년 독서 격차", topic["seed"], SEED_REPORT, topic["id"], keywords=[])
        assert api.dispatch.calls == 1
        assert api.events == [
            (str(jid), "generation", {"gen_id": concepts["id"], "gen_kind": "concepts", "target": None,
                                      "status": "canceled", "model": None, "result": None}),
            *[(str(jid), "generation", {"gen_id": c["id"], "gen_kind": "topic_card", "target": c["target"],
                                        "status": "queued", "model": None, "result": None}) for c in cards],
        ]
```

⑪ 같은 파일 `TestEndToEnd.test_continue_then_the_dispatcher_fills_the_concepts` — 반영 결과에 `cards`(이 잡의 보고서엔 씨앗이 없다). old:

```python
        assert closed and payload == {"concepts": ["독서 격차", "청소년"]}
```

new:

```python
        assert closed and payload == {"concepts": ["독서 격차", "청소년"], "cards": []}
```

⑫ `app/tests/test_research_work_tasks.py` `TestDispatch.test_concepts_generation_runs_to_done` — generation done 이벤트의 result 에 `cards`. old:

```python
            "model": "gemma-test", "result": {"concepts": ["독서 격차", "청소년"]},
```

new:

```python
            "model": "gemma-test", "result": {"concepts": ["독서 격차", "청소년"], "cards": []},
```

⑬ 같은 파일 `test_no_answer_after_three_calls_is_done_with_no_concepts`. old:

```python
        assert env.events[0][2]["result"] == {"concepts": []}
```

new:

```python
        assert env.events[0][2]["result"] == {"concepts": [], "cards": []}
```

⑭ `app/tests/test_research_work_executor.py` `TestApplyDelegation.test_concepts_keep_the_06a_branch`. old:

```python
        assert payload == {"concepts": ["노인 우울", "사회적 지지"]}
```

new:

```python
        assert payload == {"concepts": ["노인 우울", "사회적 지지"], "cards": []}
```

⑮ `app/tests/test_research_topics_api.py` `TestEndToEnd.test_continue_makes_four_cards_then_one_is_picked` — 이어가기는 씨앗 자리만 만들고, 키워드 반영이 그 키워드를 실은 카드 4건을 넣는다. 가짜 LLM 은 06e 키(`keywords`)로 답하고 카드 제목에 고른 키워드를 넣는다(Task K9 의 제목 검사 뒤에도 첫 답에 통과한다). old:

```python
    def test_continue_makes_four_cards_then_one_is_picked(self, api):
        # 이어가기(씨앗 4장) → 디스패처가 생성을 하나씩 집어 실행기·결과 적용·닫기 → 주제 조회 → 고르기
```

new:

```python
    def test_continue_makes_four_cards_then_one_is_picked(self, api):
        # 이어가기(씨앗 자리 4) → 디스패처가 키워드 생성을 집어 반영 — 그 트랜잭션에서 고른 키워드를 실은 카드 4건이 줄에
        # 선다(06e D23) → 카드를 하나씩 집어 실행기·결과 적용·닫기 → 주제 조회 → 고르기
```

⑯ 같은 테스트의 가짜 LLM. old:

```python
            if "향후 과제(씨앗)" in messages[-1]["content"]:
                content = {"title": "독거노인 지지망 연구", "question": "지지망은 우울을 낮추는가?",
                           "evidence": ["E1", "E2"]}
            else:
                content = {"concepts": ["노인 우울", "사회적 지지"]}
```

new:

```python
            if "향후 과제(씨앗)" in messages[-1]["content"]:
                content = {"title": "독거노인의 사회적 지지와 우울", "question": "지지망은 우울을 낮추는가?",
                           "evidence": ["E1", "E2"]}
            else:
                content = {"keywords": ["노인 우울", "사회적 지지"]}
```

⑰ 같은 테스트 — 드레인 뒤 카드 입력의 키워드를 본다. old:

```python
        assert asyncio.run(_drain()) == ["concepts", "topic_card", "topic_card", "topic_card", "topic_card"]
```

new:

```python
        assert asyncio.run(_drain()) == ["concepts", "topic_card", "topic_card", "topic_card", "topic_card"]
        cards = [g for g in _rows(api.engine, ResearchGeneration) if g["kind"] == "topic_card"]
        assert [g["input"]["keywords"] for g in cards] == [["노인 우울", "사회적 지지"]] * 4
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_topic_card.py tests/test_research_work_dispatch.py tests/test_research_work_api.py tests/test_research_work_tasks.py tests/test_research_work_executor.py tests/test_research_topics_api.py -q -p no:cacheprovider`

Expected: `19 failed, 236 passed, 2 warnings` — 실패는 정확히 다음 19개(샌드박스 실측):
- `test_research_work_topic_card.py::TestEnqueueSeedCards` 7개(매개변수 포함) — `enqueue_seed_cards` 가 없다(AttributeError)
- `test_research_work_dispatch.py::TestApplyResult` 4개 — `test_concepts_replace_the_chips_and_reset_membership`·`test_an_empty_result_keeps_the_chips`(payload 에 `cards` 없음)·`test_an_empty_result_still_queues_the_seed_cards_without_keywords`·`test_a_second_concepts_result_queues_no_more_cards`(카드를 넣지 않는다)
- `test_research_work_api.py` 4개 — `TestContinueSeeds::test_report_seeds_become_four_topics_without_card_generations_yet`·`test_second_continue_adds_no_topic_or_card`(이어가기가 카드 생성 4건을 넣는다), `TestCancelGeneration::test_canceling_concepts_queues_the_seed_cards_without_keywords`(카드를 넣지 않는다), `TestEndToEnd::test_continue_then_the_dispatcher_fills_the_concepts`(payload)
- `test_research_work_tasks.py::TestDispatch` 2개 — 이벤트 result 에 `cards` 없음
- `test_research_work_executor.py::TestApplyDelegation::test_concepts_keep_the_06a_branch` — payload
- `test_research_topics_api.py::TestEndToEnd::test_continue_makes_four_cards_then_one_is_picked` — 이어가기가 넣은 카드 input 의 `keywords` 가 `[]` 다(AssertionError `[[], [], [], []] == [['노인 우울', '사회적 지지']]*4` — Task K4 뒤 `topic_input` 은 키워드가 없으면 빈 목록을 싣는다)

- [ ] **Step 3: 구현한다**

① `app/services/research_work/topic_card.py` import(Task K4 뒤 기준 — Task K4 는 import 를 고치지 않았다). old:

```python
from sqlalchemy import select, update

from models.research_work import ResearchTopic
from services.prompts import get_prompt
```

new:

```python
from sqlalchemy import select, update

from models.research import ResearchJob
from models.research_work import ResearchGeneration, ResearchTopic
from services.prompts import get_prompt
```

② 같은 파일 import — 생성 넣기·카드 입력. old:

```python
from services.research_work.generate import Executor
from services.research_work.markers import figure, numbers_outside, soften_claims
from services.research_work.progress import refresh_progress
```

new:

```python
from services.research_work.enqueue import enqueue_generation
from services.research_work.generate import Executor
from services.research_work.markers import figure, numbers_outside, soften_claims
from services.research_work.progress import refresh_progress
from services.research_work.seeds import topic_input
```

③ 같은 파일 — `apply` 끝과 `EXECUTOR` 사이에 `enqueue_seed_cards`. old:

```python
    await db.execute(update(ResearchTopic).where(ResearchTopic.id == topic_id).values(**values))
    await refresh_progress(db, gen.work_id)
    return {"topic_id": topic_id, "state": values["state"]}
```

new:

```python
    await db.execute(update(ResearchTopic).where(ResearchTopic.id == topic_id).values(**values))
    await refresh_progress(db, gen.work_id)
    return {"topic_id": topic_id, "state": values["state"]}


async def enqueue_seed_cards(db, work_id, keywords: list[str]) -> list[tuple[int, int]]:
    """보고서 씨앗 자리(slot 이 있는 report_seed 주제 행)마다 카드 생성 1건을 고른 키워드로 넣는다 — 06e D23 '카드 시점'.

    키워드(개념) 생성의 반영(apply_result 의 concepts 분기 — 세 번 다 못 얻은 빈 결과도 done 이다)과 그 생성의 취소
    (api/research_work.cancel_generation — 키워드 없이)가 이 함수 하나를 부른다. '한 번만'은 씨앗 자리 행마다 본다 —
    그 행을 target 으로 하는 topic_card 생성이 (상태와 상관없이) 하나라도 있으면 건너뛴다(06e 정함 29): 키워드를 다시
    불러 반영돼도 카드가 또 들어가지 않고, 키워드 생성이 줄을 서는 사이 [다른 방향](origin other)이 먼저 카드를 만들어도
    씨앗 카드는 들어간다. 그 사이 열린 생성이 생겨 enqueue_generation 이 None 이면 그 자리도 건너뛴다.
    커밋하지 않는다 — 부르는 쪽의 트랜잭션(디스패처 finish·취소 API)에 묶인다. 돌려주는 값은 [(topic_id, gen_id)].
    """
    T, G = ResearchTopic, ResearchGeneration
    rows = (await db.execute(
        select(T.id, T.seed).where(T.work_id == work_id, T.slot.is_not(None), T.origin == "report_seed")
        .order_by(T.slot, T.id)
    )).all()
    if not rows:
        return []
    made = set((await db.execute(
        select(G.target).where(G.work_id == work_id, G.kind == "topic_card",
                               G.target.in_([str(r.id) for r in rows]))
    )).scalars().all())
    todo = [r for r in rows if str(r.id) not in made]
    if not todo:
        return []
    job = (await db.execute(
        select(ResearchJob.question, ResearchJob.report).where(ResearchJob.id == work_id)
    )).first()
    question = job.question if job is not None else ""
    report = job.report if job is not None and isinstance(job.report, dict) else {}
    cards: list[tuple[int, int]] = []
    for row in todo:
        gen_id = await enqueue_generation(
            db, work_id, kind="topic_card", target=str(row.id),
            input=topic_input(question, row.seed or {}, report, row.id, keywords=keywords),
        )
        if gen_id is not None:
            cards.append((row.id, gen_id))
    return cards
```

④ `app/services/research_work/apply.py` — import 와 concepts 분기. 빈 결과여도 씨앗 카드는 넣는다(키워드 없이). old:

```python
from models.research_work import ResearchWork
from services.research_work.executors import EXECUTORS
```

new:

```python
from models.research_work import ResearchWork
from services.research_work.executors import EXECUTORS
from services.research_work.topic_card import enqueue_seed_cards
```

⑤ 같은 파일 `apply_result`. old:

```python
    concepts: research_works.concepts 를 바꾸고 개념 소속(concept_members)을 비운다 — 소속은 FastAPI 가
    개념 임베딩으로 다시 계산한다(spec §5-3, 06c). 세 번 다 못 얻은 빈 결과면 연구를 건드리지 않는다 —
    빈 결과를 다시 부르기 전에 사용자가 넣은 칩과 소속을 아무 결과 없이 지우면 안 된다.
    그 밖의 kind 는 실행기의 apply(있으면)를 부르고 그 반환값을 result 로 낸다. 실행기나 apply 가 없으면
    하는 일이 없다(result {}).
    """
    if gen.kind == "concepts":
        concepts = list(output.get("concepts") or [])
        if concepts:
            await db.execute(
                update(ResearchWork)
                .where(ResearchWork.id == gen.work_id)
                .values(concepts=concepts, concept_members={})
            )
        return {"concepts": concepts}
```

new:

```python
    concepts: research_works.concepts 를 바꾸고 개념 소속(concept_members)을 비운다 — 소속은 FastAPI 가
    개념 임베딩으로 다시 계산한다(spec §5-3, 06c). 세 번 다 못 얻은 빈 결과면 연구를 건드리지 않는다 —
    빈 결과를 다시 부르기 전에 사용자가 넣은 칩과 소속을 아무 결과 없이 지우면 안 된다.
    그 뒤 늘 씨앗 자리 카드 생성을 넣는다(06e D23 '카드 시점' — topic_card.enqueue_seed_cards, 자리마다 한 번만).
    concepts 는 미리 고른 키워드라 카드 입력의 keywords 가 되고, 빈 결과면 키워드 없이 넣는다. 넣은 카드의 queued
    이벤트는 따로 보내지 않는다 — 화면이 concepts done 에 topics·work 를 다시 읽는다(06e 정함 25). 워커 _close 가
    queued 를 보고 다음 디스패치를 보낸다. result 는 {"concepts", "cards": [gen_id]}.
    그 밖의 kind 는 실행기의 apply(있으면)를 부르고 그 반환값을 result 로 낸다. 실행기나 apply 가 없으면
    하는 일이 없다(result {}).
    """
    if gen.kind == "concepts":
        concepts = list(output.get("concepts") or [])
        if concepts:
            await db.execute(
                update(ResearchWork)
                .where(ResearchWork.id == gen.work_id)
                .values(concepts=concepts, concept_members={})
            )
        cards = await enqueue_seed_cards(db, gen.work_id, concepts)
        return {"concepts": concepts, "cards": [gen_id for _, gen_id in cards]}
```

⑥ `app/api/research_work.py` import(Task K2·Task K3 뒤 기준) — 이어가기가 카드 입력을 만들지 않으므로 `topic_input` 을 빼고, 취소 API 가 쓰는 씨앗 카드 넣기·queued 이벤트 모양. old:

```python
from services.research_work.enqueue import lock_key
```

new:

```python
from services.research_work.enqueue import lock_key, queued_event
```

⑦ 같은 파일 import 의 seeds 줄. old:

```python
from services.research_work.seeds import corpus_of, pick_seeds, topic_input
from services.research_work.shapes import PHASE_ORDER, TOPIC_SEED_SLOTS
```

new:

```python
from services.research_work.seeds import corpus_of, pick_seeds
from services.research_work.shapes import PHASE_ORDER, TOPIC_SEED_SLOTS
from services.research_work.topic_card import enqueue_seed_cards
```

⑧ 같은 파일 `continue_research` docstring. old:

```python
    """[이 연구 이어가기]. 완료된 잡만, 멱등 — 연구 행을 새로 만든 요청만 후보·핵심 개념 생성·보고서 씨앗
    주제 카드(최대 TOPIC_SEED_SLOTS 장, 카드 1장 = 생성 1건)를 넣는다. 동시에 두 번 눌러도 ON CONFLICT DO NOTHING
    이 한쪽만 행을 만들게 하고, 넣는 것은 모두 그 요청의 커밋 하나에 묶인다. 이미 이어간 연구(06a 에서 이어간
    것 포함)에는 아무것도 더 넣지 않는다 — 그 연구는 주제 화면의 [다른 방향] 으로 카드를 받는다(정함 15)."""
```

new:

```python
    """[이 연구 이어가기]. 완료된 잡만, 멱등 — 연구 행을 새로 만든 요청만 후보·키워드(개념) 생성·보고서 씨앗 주제 행
    (최대 TOPIC_SEED_SLOTS 개, slot 1~)을 넣는다. 씨앗 자리의 카드 생성(카드 1장 = 생성 1건)은 여기서 넣지 않는다 —
    키워드가 정해진 뒤 키워드 생성의 반영(apply_result)·취소(cancel_generation)가 고른 키워드로 넣는다(06e D23,
    topic_card.enqueue_seed_cards). 동시에 두 번 눌러도 ON CONFLICT DO NOTHING 이 한쪽만 행을 만들게 하고, 넣는 것은
    모두 그 요청의 커밋 하나에 묶인다. 이미 이어간 연구(06a 에서 이어간 것 포함)에는 아무것도 더 넣지 않는다 — 그
    연구는 주제 화면의 [다른 방향] 으로 카드를 받는다(06b 정함 15)."""
```

⑨ 같은 함수의 씨앗 루프 — 주제 행만 넣는다. old:

```python
    for slot, seed in enumerate(pick_seeds(report, limit=TOPIC_SEED_SLOTS), start=1):
        # 주제 행 id 가 생성의 target 이다 — 행을 먼저 넣고 RETURNING 으로 id 를 받는다
        topic_id = await db.scalar(
            insert(ResearchTopic)
            .values(work_id=jid, slot=slot, origin="report_seed", seed=seed, card={},
                    state="candidate", corpus_snapshot=corpus)
            .returning(ResearchTopic.id)
        )
        await db.execute(insert(ResearchGeneration).values(
            work_id=jid, kind="topic_card", target=str(topic_id), priority=PRIORITY_USER, status="queued",
            input=topic_input(job.question, seed, report, topic_id),
        ))
```

new:

```python
    for slot, seed in enumerate(pick_seeds(report, limit=TOPIC_SEED_SLOTS), start=1):
        # 카드 생성은 키워드가 정해진 뒤에 넣는다(06e D23) — 여기서는 씨앗 자리 주제 행만
        await db.execute(
            insert(ResearchTopic)
            .values(work_id=jid, slot=slot, origin="report_seed", seed=seed, card={},
                    state="candidate", corpus_snapshot=corpus)
        )
```

⑩ 같은 파일 `cancel_generation` — docstring 끝 문장과 커밋 앞뒤. old:

```python
    읽은 뒤 디스패처가 집었으면 조건부 UPDATE 가 바꾸지 않아 409 다. 디스패치는 보내지 않는다."""
```

new:

```python
    읽은 뒤 디스패처가 집었으면 조건부 UPDATE 가 바꾸지 않아 409 다. 키워드(개념) 생성을 취소하면 같은 트랜잭션에서
    씨앗 자리 카드를 키워드 없이 넣고(06e D23 — topic_card.enqueue_seed_cards), 그때만 커밋 뒤 디스패치와 카드마다
    queued 이벤트를 보낸다(06e 정함 25). 그 밖의 취소는 디스패치를 보내지 않는다."""
```

⑪ 같은 함수 본문 끝. old:

```python
    if res.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태입니다")
    await db.commit()
    await publish_work(jid, "generation", event)
    return {"gen_id": gen_id, "status": "canceled"}
```

new:

```python
    if res.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태입니다")
    cards = await enqueue_seed_cards(db, jid, []) if gen.kind == "concepts" else []
    await db.commit()
    await publish_work(jid, "generation", event)
    if cards:
        _send_dispatch()
        for topic_id, card_gen in cards:
            await publish_work(jid, "generation", queued_event(card_gen, "topic_card", str(topic_id)))
    return {"gen_id": gen_id, "status": "canceled"}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_topic_card.py tests/test_research_work_dispatch.py tests/test_research_work_api.py tests/test_research_work_tasks.py tests/test_research_work_executor.py tests/test_research_topics_api.py -q -p no:cacheprovider`

Expected: `255 passed, 2 warnings` (topic_card 58 · dispatch 34 · api 85 · tasks 27 · executor 12 · topics 39)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 세 파일, 통과 = Task 앞 + 10

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/topic_card.py app/services/research_work/apply.py app/api/research_work.py app/tests/test_research_work_topic_card.py app/tests/test_research_work_dispatch.py app/tests/test_research_work_api.py app/tests/test_research_work_tasks.py app/tests/test_research_work_executor.py app/tests/test_research_topics_api.py && git status --short && git commit -m "[Feat] round06e — 씨앗 카드 생성을 키워드가 정해진 뒤 넣는다(D23, spec §12-4 카드 시점). 이어가기는 주제 행(씨앗 자리 slot 1~4)만 넣고, topic_card 생성은 키워드(개념) 생성의 반영(apply_result — 세 번 다 못 얻은 빈 결과도 done 이라 키워드 없이)과 그 생성의 취소(cancel API — 키워드 없이)가 같은 트랜잭션에서 topic_card.enqueue_seed_cards 로 그때 고른 키워드를 실어 넣는다. '한 번만'은 씨앗 자리 행마다 — 그 행을 target 으로 한 카드 생성이 상태와 상관없이 있으면 건너뛴다(06e 정함 29, [다른 방향] 카드가 먼저 있어도 씨앗 카드는 들어간다). 반영 결과는 {concepts, cards}, 취소가 넣은 카드는 커밋 뒤 디스패치·queued 이벤트를 보낸다(정함 25). 회수기·워커 태스크는 그대로"
```

---

### Task K6: [이 키워드로 다시 만들기] — POST …/topics/regenerate

**왜:** spec §12-4 '[이 키워드로 다시 만들기]'(D23), §12-11 '키워드 최소 선택 수'·'고른 카드도 다시 만들지'(정함 15·16). 칩을 바꾼 뒤 카드를 새 키워드로 받으려면 새 엔드포인트가 필요하다 — 기존 [다시](`research_work.py:351-387`)는 옛 input(그때 키워드)을 그대로 복사해 쓸 수 없다. 대상은 고치지 않은(`card.edited` 아님) AI 카드(origin report_seed·other)의 후보·근거 부족 상태뿐이다. 고른(picked) 카드는 다시 만들지 않는다 — 다시 만들면 목차에 '다시 맞춤 필요'가 붙는다(권고). 다시 만드는 사이 그 카드를 고르는 경로도 막는다 — 06b 에서는 [다시]가 카드 없는 자리에만 있어 고를 수 없었는데, 이 엔드포인트가 내용이 있는 AI 카드에 새 생성을 넣으면서 처음 열린다(`pick_topic` 은 `topic.card` 만 보고, `topic_card.apply` 는 picked 행도 덮는다). 선행연구 묶음 수가 키워드 수 이하라(`membership.py:97-128`, `:120`) 키워드가 둘 이상일 때만 받는다(권고 2).

**Files:**
- Modify: `app/api/research_topics.py` (Task K4 뒤 기준 — 머리 docstring 3-4, import 24, 상수, `generate_topics` 뒤에 새 핸들러)
- Modify: `app/services/research_work/topic_card.py` (Task K5 뒤 기준 — `apply` docstring 201-205·edited 검사 213-214 뒤)
- Test: `app/tests/test_research_topics_api.py` (Task K4 뒤 기준 — `TestOtherDirection` 끝과 '직접 쓰기·직접 고치기' 머리 사이에 새 절)
- Test: `app/tests/test_research_work_topic_card.py` (Task K5 뒤 기준 — `TestApply.test_a_picked_topic_stays_picked` 401-406 ✎)

**알아 둘 것:**
- 순서: `_writable` → 키워드 `< MIN_PICKED_KEYWORDS`(keywords.py, 2) 면 409 `KEYWORDS_TOO_FEW` → 키워드 생성이 열려 있으면 409 `KEYWORDS_BUSY`(Task K4 상수) → 연구별 잠금 `lock_key(jid, "topic_card", REGENERATE_LOCK_TARGET)`(`"regenerate"` — 주제 id 숫자 문자열과 겹치지 않는 이름, `OTHER_LOCK_TARGET` 과 같은 방식) → 대상 읽기(id 순 — 씨앗 자리가 먼저 만들어졌다) → 행마다 `enqueue_generation`. 그 주제의 카드 생성이 열려 있으면 `None` 이고(enqueue 가 같은 대상 열린 생성을 막는다 — `enqueue.py:34-38`, spec 의 ':251-255' 는 옛 줄) `skipped` 로 센다 — 넣은 행이 없으니 되돌리지 않는다.
- 넣은 것도 건너뛴 것도 없으면 롤백하고 409 `NOTHING_TO_REGENERATE`. 건너뛴 것만 있으면 200(`{"topic_ids": [], "gen_ids": [], "skipped": n}`)이고 디스패치는 보내지 않는다. 넣은 것이 있으면 커밋 → `_send_dispatch()` → 카드마다 queued 이벤트([다른 방향]과 같은 순서 — `enqueue.py` 머리 docstring).
- 입력은 `topic_input(job.question, row.seed, report, row.id, keywords=list(work.concepts))` — 씨앗과 지금 키워드뿐이다. 카드의 지금 제목을 주지 않는다(함정 26). 카드는 새 결과가 반영될 때까지 그대로 보인다(`topic_card.apply` 가 그 행만 바꾼다). 그 사이 [직접 고치기]는 409 `CARD_BUSY`(`edit_topic` — 카드 생성이 열려 있으면)이고, 그래도 고친 카드(`card.edited`)는 반영이 덮지 않는다(`topic_card.apply` 의 edited 검사 — dev `:206-207`, Task K5 뒤 `:213-214`).
- **다시 만드는 사이의 [고르기](06e 정함 16):** 화면은 카드 생성이 열린 카드를 고르지 않게 막고 '새 키워드로 다시 만드는 중입니다'를 단다(Task K7 `canPick`·`cardRemakingNote`, Task K8). 두 탭이 거의 같이 누른 경우는 서버가 막는다 — `topic_card.apply` 의 edited 검사 바로 뒤에서 고른 카드(state picked·제목 있음)면 덮지 않고 `{"topic_id", "state": "picked"}` 를 돌려준다(새 카드든 빈 결과든). 06b 에서는 고른 카드에 열린 카드 생성이 생길 수 없어 동작이 바뀌지 않는다 — 다만 고른 카드가 새 카드로 바뀌는 것을 단언하던 `TestApply.test_a_picked_topic_stays_picked` 를 새 규칙으로 바꾼다(✎ — 매개변수 둘이라 +1). `pick_topic` 에서 409 로 막는 대안은 쓰지 않는다 — 고르기를 늦출 까닭이 서버에는 없고, 반영 쪽에서 막으면 두 탭 경합까지 한 곳에서 끝난다.
- `KEYWORDS_TOO_FEW` 는 `f"키워드를 {MIN_PICKED_KEYWORDS}개 이상 고르세요"` — 1-1 의 값('키워드를 2개 이상 고르세요')과 같은 글을 상수에서 만든다.
- 구현 전 POST `…/topics/regenerate` 는 `PATCH …/topics/{tid}` 만 맞아 405 다(새 테스트 7개 실패). `{tid}` 는 int 라 경로 'regenerate' 와 겹치지 않는다. 고른 카드 테스트 둘도 구현 전에는 떨어진다(새 카드면 카드가 바뀌고, 빈 결과면 state 가 insufficient).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `app/tests/test_research_topics_api.py` — `TestOtherDirection` 끝(Task K4 가 더한 `test_409_while_keywords_are_being_made` 뒤)과 '직접 쓰기·직접 고치기' 머리 사이에 새 절. old:

```python
        assert [g["id"] for g in _rows(api.engine, ResearchGeneration)] == [concepts]
        assert api.dispatch.calls == 0 and api.events == []


# ── 직접 쓰기·직접 고치기 ─────────────────────────────────────────────
```

new:

```python
        assert [g["id"] for g in _rows(api.engine, ResearchGeneration)] == [concepts]
        assert api.dispatch.calls == 0 and api.events == []


# ── 이 키워드로 다시 만들기(06e D23) ──────────────────────────────────

KEYWORDS = ["노인 우울", "사회적 지지"]


class TestRegenerate:
    def test_ai_cards_are_queued_again_with_the_current_keywords(self, api):
        # 지금 고른 키워드로 AI 카드(씨앗 카드·다른 방향 카드)를 다시 만든다. 카드는 새 결과가 올 때까지 그대로다
        jid = _work_job(api.engine, concepts=KEYWORDS)
        seed_card = add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)
        add_generation(api.engine, jid, kind="topic_card", status="done", target=str(seed_card))
        thin = add_topic(api.engine, jid, slot=2, seed=SEEDS[1], state="insufficient")
        add_generation(api.engine, jid, kind="topic_card", status="done", target=str(thin))
        other = add_topic(api.engine, jid, origin="other", seed=SEEDS[4], card=CARD)

        res = api.client.post(f"/api/research/{jid}/topics/regenerate")

        assert res.status_code == 200
        new = [g for g in _rows(api.engine, ResearchGeneration) if g["status"] == "queued"]
        assert res.json() == {"topic_ids": [seed_card, thin, other], "gen_ids": [g["id"] for g in new],
                              "skipped": 0}
        for tid, seed, gen in zip((seed_card, thin, other), (SEEDS[0], SEEDS[1], SEEDS[4]), new):
            assert (gen["kind"], gen["target"]) == ("topic_card", str(tid))
            # 입력은 씨앗과 지금 키워드뿐이다 — 이전 제목을 주지 않는다(함정 26)
            assert gen["input"] == topic_input(QUESTION, seed, REPORT, tid, keywords=KEYWORDS)
        assert _topic(api.engine, seed_card)["card"] == CARD
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "generation", {
            "gen_id": g["id"], "gen_kind": "topic_card", "target": g["target"], "status": "queued",
            "model": None, "result": None}) for g in new]

    def test_edited_user_picked_and_folded_cards_are_left_alone(self, api):
        # 06e 정함 16 — 고른 카드는 키워드를 바꿔도 다시 만들지 않는다(목차 '다시 맞춤 필요'를 피한다). 사용자가 고친
        # 카드·직접 쓴 카드·접은 카드도 대상이 아니다
        jid = _work_job(api.engine, concepts=KEYWORDS)
        add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card={**CARD, "edited": True})
        add_topic(api.engine, jid, slot=2, seed=SEEDS[1], card=CARD, state="picked")
        add_topic(api.engine, jid, slot=3, seed=SEEDS[2], card=CARD, state="folded")
        add_topic(api.engine, jid, origin="user", card=CARD)
        target = add_topic(api.engine, jid, slot=4, seed=SEEDS[3], card=CARD)

        res = api.client.post(f"/api/research/{jid}/topics/regenerate")

        assert res.status_code == 200 and res.json()["topic_ids"] == [target]
        assert [g["target"] for g in _rows(api.engine, ResearchGeneration)] == [str(target)]

    def test_a_card_being_made_is_skipped_and_counted(self, api):
        # 열린 카드 생성은 건너뛴다(enqueue_generation 이 None — 기존 [다시]와 같은 규칙)
        jid = _work_job(api.engine, concepts=KEYWORDS)
        busy = add_topic(api.engine, jid, slot=1, seed=SEEDS[0])
        open_gen = add_generation(api.engine, jid, kind="topic_card", status="running", target=str(busy))
        idle = add_topic(api.engine, jid, slot=2, seed=SEEDS[1], card=CARD)

        res = api.client.post(f"/api/research/{jid}/topics/regenerate")

        assert res.status_code == 200
        (new,) = [g for g in _rows(api.engine, ResearchGeneration) if g["id"] != open_gen]
        assert res.json() == {"topic_ids": [idle], "gen_ids": [new["id"]], "skipped": 1}

        # 만드는 중인 카드만 남았으면 넣은 것 없이 200 — 건너뛴 수만 알리고 디스패치도 보내지 않는다
        only = _work_job(api.engine, concepts=KEYWORDS)
        tid = add_topic(api.engine, only, slot=1, seed=SEEDS[0])
        add_generation(api.engine, only, kind="topic_card", status="queued", target=str(tid))
        calls = api.dispatch.calls
        again = api.client.post(f"/api/research/{only}/topics/regenerate")
        assert again.status_code == 200 and again.json() == {"topic_ids": [], "gen_ids": [], "skipped": 1}
        assert api.dispatch.calls == calls

    def test_fewer_than_two_keywords_is_409(self, api):
        # 06e 정함 15 — 선행연구 묶음 수는 키워드 수 이하다(membership) — 키워드 1개면 묶음도 1개
        jid = _work_job(api.engine, concepts=["노인 우울"])
        add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)

        res = api.client.post(f"/api/research/{jid}/topics/regenerate")

        assert res.status_code == 409 and res.json()["detail"] == "키워드를 2개 이상 고르세요"
        assert _rows(api.engine, ResearchGeneration) == [] and api.dispatch.calls == 0

    def test_409_while_keywords_are_being_made(self, api):
        jid = _work_job(api.engine, concepts=KEYWORDS)
        add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)
        concepts = add_generation(api.engine, jid, kind="concepts", status="queued")

        res = api.client.post(f"/api/research/{jid}/topics/regenerate")

        assert res.status_code == 409
        assert res.json()["detail"] == "키워드를 고르는 중입니다 — 끝난 뒤 다시 만들어 주세요"
        assert [g["id"] for g in _rows(api.engine, ResearchGeneration)] == [concepts]

    def test_nothing_to_regenerate_is_409(self, api):
        jid = _work_job(api.engine, concepts=KEYWORDS)
        add_topic(api.engine, jid, origin="user", card=CARD)

        res = api.client.post(f"/api/research/{jid}/topics/regenerate")

        assert res.status_code == 409 and res.json()["detail"] == "다시 만들 AI 카드가 없습니다"
        assert _rows(api.engine, ResearchGeneration) == [] and api.events == []

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, concepts=KEYWORDS, is_example=True)
        add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)

        res = api.client.post(f"/api/research/{jid}/topics/regenerate")

        assert res.status_code == 409 and res.json()["detail"] == "예시 연구는 읽기 전용입니다"
        assert _rows(api.engine, ResearchGeneration) == []


# ── 직접 쓰기·직접 고치기 ─────────────────────────────────────────────
```

② `app/tests/test_research_work_topic_card.py` `TestApply.test_a_picked_topic_stays_picked` ✎ — 고른 카드는 다시 만든 결과로 덮지 않는다(새 카드·빈 결과 두 매개변수). 지금 테스트는 고른 카드가 새 카드로 바뀌는 것을 단언한다 — 06b 에서는 고른 카드에 열린 생성이 생길 수 없어 실제로 일어나지 않던 경로다. old:

```python
    def test_a_picked_topic_stays_picked(self, engine):
        _, tid, gid = _setup(engine, card={"title": "옛 카드", "question": "옛 질문?"}, state="picked")

        assert _apply(engine, gid, _bound(GOOD))["state"] == "picked"

        assert _topic_row(engine, tid)["card"]["title"] == "독거노인의 지지망 유형과 우울"
```

new:

```python
    @pytest.mark.parametrize("answer", ["card", "empty"])
    def test_a_picked_card_is_not_overwritten_by_a_regeneration(self, engine, answer):
        # 06e 정함 16 — [이 키워드로 다시 만들기] 가 도는 사이 고른 카드는 새 카드로도, 빈 결과(근거 부족)로도 덮지
        # 않는다 — 덮으면 목차에 '다시 맞춤 필요'가 붙는다. 06b 에서는 고른 카드에 열린 생성이 생길 수 없었다
        old = {"title": "옛 카드", "question": "옛 질문?"}
        _, tid, gid = _setup(engine, card=old, state="picked")
        output = _bound(GOOD) if answer == "card" else {"card": None}

        assert _apply(engine, gid, output) == {"topic_id": tid, "state": "picked"}

        row = _topic_row(engine, tid)
        assert (row["card"], row["state"]) == (old, "picked")
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_topics_api.py tests/test_research_work_topic_card.py -q -p no:cacheprovider`

Expected: `9 failed, 96 passed, 2 warnings` — `test_research_topics_api.py::TestRegenerate` 7개 모두(405 Method Not Allowed — 경로가 없다), `test_research_work_topic_card.py::TestApply::test_a_picked_card_is_not_overwritten_by_a_regeneration[card]`(고른 카드가 새 카드로 바뀐다)·`[empty]`(state 가 insufficient 로 온다)

- [ ] **Step 3: 구현한다**

① `app/api/research_topics.py` import — 최소 선택 수. old:

```python
from services.research_work.enqueue import enqueue_generation, lock_key, queued_event
```

new:

```python
from services.research_work.enqueue import enqueue_generation, lock_key, queued_event
from services.research_work.keywords import MIN_PICKED_KEYWORDS
```

② 같은 파일 상수(Task K4 뒤 기준 — `KEYWORDS_BUSY` 는 Task K4 가 두었다). old:

```python
KEYWORDS_BUSY = "키워드를 고르는 중입니다 — 끝난 뒤 다시 만들어 주세요"
# [다른 방향] 의 연구별 잠금 대상 — 주제 카드 생성의 target(주제 id 숫자 문자열)과 겹치지 않는 이름
OTHER_LOCK_TARGET = "other-direction"
```

new:

```python
KEYWORDS_BUSY = "키워드를 고르는 중입니다 — 끝난 뒤 다시 만들어 주세요"
KEYWORDS_TOO_FEW = f"키워드를 {MIN_PICKED_KEYWORDS}개 이상 고르세요"
NOTHING_TO_REGENERATE = "다시 만들 AI 카드가 없습니다"
# [다른 방향] 의 연구별 잠금 대상 — 주제 카드 생성의 target(주제 id 숫자 문자열)과 겹치지 않는 이름
OTHER_LOCK_TARGET = "other-direction"
# [이 키워드로 다시 만들기] 의 연구별 잠금 대상 — 같은 까닭으로 주제 id 와 겹치지 않는 이름
REGENERATE_LOCK_TARGET = "regenerate"
```

③ 같은 파일 — `generate_topics`([다른 방향]) 끝과 `create_topic`([직접 쓰기]) 사이에 새 핸들러. old:

```python
    for topic_id, gen_id in zip(topic_ids, gen_ids):
        await publish_work(jid, "generation", queued_event(gen_id, "topic_card", str(topic_id)))
    return {"topic_ids": topic_ids, "gen_ids": gen_ids}


@router.post("/api/research/{job_id}/topics")
```

new:

```python
    for topic_id, gen_id in zip(topic_ids, gen_ids):
        await publish_work(jid, "generation", queued_event(gen_id, "topic_card", str(topic_id)))
    return {"topic_ids": topic_ids, "gen_ids": gen_ids}


@router.post("/api/research/{job_id}/topics/regenerate")
async def regenerate_topics(job_id: str, db: AsyncSession = Depends(get_db)):
    """[이 키워드로 다시 만들기] — 지금 고른 키워드(work.concepts)로 AI 카드를 다시 만든다(06e D23, 정함 15·16).

    대상은 보고서 씨앗 카드(origin report_seed·other) 가운데 후보(candidate)·근거 부족(insufficient)이고 사용자가 고치지
    않은(card.edited 아님) 것 — 고른 카드(picked)·접은 카드·직접 쓴 카드(origin user)·고친 카드는 그대로 둔다(고른 카드를
    다시 만들면 목차에 '다시 맞춤 필요'가 붙는다 — §12-11 권고). 카드를 만드는 중인 주제는 건너뛰고 skipped 로 센다
    (enqueue_generation 이 None — 기존 [다시]와 같은 규칙). 입력은 씨앗과 지금 키워드뿐이고 이전 제목은 주지 않는다
    (함정 26). 키워드가 MIN_PICKED_KEYWORDS 개 미만이면 409(선행연구 묶음 수 ≤ 키워드 수 — membership), 키워드 생성이
    열려 있으면 409. 연구별 잠금이 '대상 읽기 → 생성 넣기'를 한 줄로 세운다. 넣은 것도 건너뛴 것도 없으면 409."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    keywords = list(work.concepts or [])
    if len(keywords) < MIN_PICKED_KEYWORDS:
        raise HTTPException(status_code=409, detail=KEYWORDS_TOO_FEW)
    if await _concepts_open(db, jid):
        raise HTTPException(status_code=409, detail=KEYWORDS_BUSY)
    job = await _get_job(db, jid)
    report = job.report if isinstance(job.report, dict) else {}
    await db.execute(select(func.pg_advisory_xact_lock(lock_key(jid, "topic_card", REGENERATE_LOCK_TARGET))))
    rows = (await db.execute(
        select(ResearchTopic)
        .where(ResearchTopic.work_id == jid, ResearchTopic.origin.in_(("report_seed", "other")),
               ResearchTopic.state.in_(("candidate", "insufficient")))
        .order_by(ResearchTopic.id)
    )).scalars().all()
    topic_ids: list[int] = []
    gen_ids: list[int] = []
    skipped = 0
    for row in rows:
        if (row.card or {}).get("edited"):
            continue
        gen_id = await enqueue_generation(
            db, jid, kind="topic_card", target=str(row.id),
            input=topic_input(job.question, row.seed or {}, report, row.id, keywords=keywords),
        )
        if gen_id is None:          # 그 카드를 만드는 중이다 — 넣은 행이 없어 되돌릴 것도 없다
            skipped += 1
            continue
        topic_ids.append(row.id)
        gen_ids.append(gen_id)
    if not gen_ids and not skipped:
        await db.rollback()
        raise HTTPException(status_code=409, detail=NOTHING_TO_REGENERATE)
    await db.commit()
    if gen_ids:
        _send_dispatch()
    for topic_id, gen_id in zip(topic_ids, gen_ids):
        await publish_work(jid, "generation", queued_event(gen_id, "topic_card", str(topic_id)))
    return {"topic_ids": topic_ids, "gen_ids": gen_ids, "skipped": skipped}


@router.post("/api/research/{job_id}/topics")
```

④ 같은 파일 머리 docstring 첫 단락 — 새 엔드포인트를 적는다. old:

```python
조회(TopicsView)·[다른 방향](쓰지 않은 보고서 씨앗으로 카드 2장 더)·[직접 쓰기](사용자 카드, LLM 없음)·
[직접 고치기](제목·연구 질문만, card.edited)·[고르기](다음 단계로 갈 주제 하나 — phase 를 reading 으로 올린다).
```

new:

```python
조회(TopicsView)·[다른 방향](쓰지 않은 보고서 씨앗으로 카드 2장 더)·[직접 쓰기](사용자 카드, LLM 없음)·
[직접 고치기](제목·연구 질문만, card.edited)·[고르기](다음 단계로 갈 주제 하나 — phase 를 reading 으로 올린다)·
[이 키워드로 다시 만들기](06e — 지금 고른 키워드로 고치지 않은 AI 카드를 다시).
```

⑤ `app/services/research_work/topic_card.py` `apply`(Task K5 뒤 기준 — docstring 201-205·edited 검사 213-214) — 고른 카드는 다시 만든 결과로 덮지 않는다(06e 정함 16). 다시 만드는 사이 [고르기]는 화면이 먼저 막고(Task K7 `canPick`), 두 탭이 거의 같이 누른 경우는 여기서 막는다. old:

```python
    카드가 있으면 state 는 candidate(이미 고른 주제면 picked 그대로), 없으면 card 를 비우고 insufficient.
    그 사이 사용자가 직접 고친 카드(card.edited)는 덮지 않는다 — 다시 부르기(빈 카드의 retry)가 사용자의 글을
    지우면 안 된다."""
```

new:

```python
    카드가 있으면 state 는 candidate(이미 고른 주제면 picked 그대로), 없으면 card 를 비우고 insufficient.
    그 사이 사용자가 직접 고친 카드(card.edited)는 덮지 않는다 — 다시 부르기(빈 카드의 retry)가 사용자의 글을
    지우면 안 된다. 고른 카드(picked — 제목이 있다)도 덮지 않는다 — [이 키워드로 다시 만들기](06e)가 도는 사이
    고른 카드의 제목·질문·근거가 바뀌면 목차에 '다시 맞춤 필요'가 붙는다(06e 정함 16)."""
```

⑥ 같은 함수 — edited 검사 바로 뒤에 고른 카드 검사. old:

```python
    if (row.card or {}).get("edited"):
        return {"topic_id": topic_id, "state": row.state}
    card = output.get("card")
```

new:

```python
    if (row.card or {}).get("edited"):
        return {"topic_id": topic_id, "state": row.state}
    # 06e 정함 16 — 고른 카드는 다시 만든 결과(새 카드든 빈 결과든)로 덮지 않는다. 06b 에서는 고른 카드에 열린 카드
    # 생성이 생길 수 없어(다시 부르기는 카드 없는 자리뿐) 동작이 바뀌지 않는다
    if row.state == "picked" and (row.card or {}).get("title"):
        return {"topic_id": topic_id, "state": "picked"}
    card = output.get("card")
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_topics_api.py tests/test_research_work_topic_card.py -q -p no:cacheprovider`

Expected: `105 passed, 2 warnings` (topics 46 · topic_card 59)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 세 파일, 통과 = Task 앞 + 8

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/api/research_topics.py app/services/research_work/topic_card.py app/tests/test_research_topics_api.py app/tests/test_research_work_topic_card.py && git status --short && git commit -m "[Feat] round06e — [이 키워드로 다시 만들기] 엔드포인트 POST /api/research/{id}/topics/regenerate 를 더한다(D23, spec §12-4). 저장된 키워드(work.concepts)로 고치지 않은 AI 카드(origin report_seed·other 의 후보·근거 부족)를 카드 1장 = 생성 1건으로 다시 넣는다 — 고른 카드·고친 카드·직접 쓴 카드·접은 카드는 그대로(06e 정함 16), 만드는 중인 카드는 건너뛰고 skipped 로 센다. 입력은 씨앗과 지금 키워드뿐 — 이전 제목을 주지 않는다(함정 26). 키워드가 2개 미만이면 409 KEYWORDS_TOO_FEW(묶음 수 ≤ 키워드 수 — 정함 15), 키워드 생성이 열려 있으면 409 KEYWORDS_BUSY, 다시 만들 카드가 없으면 409 NOTHING_TO_REGENERATE. 연구별 잠금이 대상 읽기와 생성 넣기를 한 줄로 세운다. 다시 만드는 사이 두 탭에서 고른 카드는 반영이 덮지 않는다 — topic_card.apply 에 고른 카드 검사를 더하고, 고른 카드가 새 카드로 바뀌던 06b 테스트를 새 규칙으로 바꾼다"
```

---

### Task K7: 키워드 판정 — 순수 함수·타입·공용 고정 예제

**왜:** spec §12-4 '하이라이트(`keywordSpans`·백엔드와 공용 고정 예제)'·'카드의 `card.keywords` 가 지금 선택과 다르면 "키워드가 바뀌었습니다"'·'칩 UI(aria-pressed·출처·편수 배지·옛 연구는 concepts 를 선택된 칩)'·'화면 — 빈 카드 waiting / 키워드를 다시 부르면 카드를 만듭니다'·'`RELOAD.concepts` 에 topics'·'최소 선택 수 2', 정함 15·17. `.vue` 는 단위 테스트하지 않으므로 화면(Task K8)의 판단을 `utils/topicDeck.ts` 의 순수 함수로 먼저 만들고 vitest 로 고정한다.

**Files:**
- Create: `frontend/tests/fixtures/keyword_match.json`
- Modify: `frontend/types/work.ts` (`WorkView` 41-51 앞에 `KeywordCandidate`, `WorkView`·`TopicCard` 78-88 에 선택 필드)
- Modify: `frontend/utils/topicDeck.ts` (Task R1 뒤 기준 — 타입 import 4-13, `CardStatus` 17, 상수 27-28, `cardStatus` 60-71, `cardNote` 79-92, `canPick` 94-96, 파일 끝에 키워드 함수)
- Modify: `frontend/utils/workEvents.ts` (`RELOAD` 25-34)
- Modify: `frontend/composables/useResearchWork.ts` (`useWorkApi()` 의 `generateTopics` 55-59 뒤)
- Test: `frontend/tests/unit/topicDeck.test.ts` (Task R1 뒤 기준 — import 3-23, describe `cardStatus` 100-124, describe `canPick` 151-158, 파일 끝)
- Test: `frontend/tests/unit/workEvents.test.ts` (describe `reloadFor` 68-76, `applyWorkEvent — generation` 의 189-193)

**알아 둘 것:**
- **앞 Task 와 같은 파일(§3 공유 파일 표):** `topicDeck.ts`·`topicDeck.test.ts` 는 Task R1 이 먼저 고친다(`conceptsNote` 문구 `:219-233`·테스트 `:305-312` — '핵심 개념' → '키워드'). 이 Task 의 old 는 그 자리를 잡지 않는다 — 새 함수·describe 는 **파일 끝에 붙인다**. Task H1(뒤)이 잡는 자리(`import { citeLabel } …` 한 줄, `CHIP_TITLE_CHARS` 두 줄, `shortTitle`·`evidenceChips` 블록, 테스트 import 의 `  cardStatus,`·`  seedLine,` 줄)도 건드리지 않는다 — 새 import 이름은 그 두 줄을 피해 알파벳 순 자리에 넣는다. `types/work.ts` 는 Task A3·Task X3·Task S3 가 먼저 고치지만(Outline·ProposalView·인용 근거 타입) `WorkView`·`TopicCard` 는 건드리지 않는다. `useResearchWork.ts` 는 Task S3 가 `getSectionSources` 를 먼저 더한다 — 이 Task 는 `generateTopics` 바로 뒤에 넣어 겹치지 않는다.
- **`keywordSpans` 의 일치 규칙 = 06c `terms.contains`**(spec §12-2 — NFKC → casefold → 공백 제거 뒤 부분 문자열, 아니면 낱말 조각이 모두 순서대로). 원문 글자(코드포인트)마다 `ch.normalize("NFKC").toLowerCase()` 를 이어 붙이며 각 UTF-16 단위의 원문 글자 순번(`at`)을 기록하고 공백은 건너뛴다(1-9). 맞은 자리를 원문 순번으로 되돌려 원문 글자 그대로 감싼다 — 전각 'ＣＳＲ' 은 'csr' 로 맞추고 'ＣＳＲ' 을, 공백을 지우고 맞춘 '다문화가정' 은 원문 '다문화 가정' 을 감싼다. 키워드마다 처음 맞은 자리만 감싸고 겹치거나 맞닿은 자리는 합친다. 차이(알려진 한계 — 완료노트): JS `toLowerCase` 는 Python `casefold` 와 몇 글자(ß 등)에서 다르고, NFKC 를 글자마다 해 결합 자모(분리형 한글)를 합치지 못한다 — 둘 다 소장 논문 제목·키워드에는 드물다. Task K9 이 06c 의 `term_checks.json` 전부로 서버와 같은 참·거짓을 고정한다.
- **고정 예제 `keyword_match.json` 은 하이라이트 자리만**(`{text, word, marked, note}`) — 일치 참·거짓의 정본은 06c 의 `frontend/tests/fixtures/term_checks.json` 이다(06e 는 읽기만 — 1-9). 사례는 그 `contains` 칸과 같은 text/word 여섯에 06e 만의 영문 사례 하나. vitest 는 `it.each(CASES)("$note", …)` 라 사례마다 테스트 하나다(note 가 서로 달라야 한다). 백엔드 쪽 대조(`contains == bool(marked)`)는 06c 가 dev 에 들어온 뒤 Task K9 가 단다 — 이 Task 의 vitest 는 06c 없이도 돈다.
- **`cardStatus(item, concepts?)`** — 두 번째 인자가 없으면 지금과 같다(`canPick` 은 그대로 한 인자로 부른다). 생성 기록이 없는 빈 카드: state insufficient → insufficient(그대로). 빈 **씨앗 자리**(slot 이 있고 origin report_seed)는 키워드 생성이 있으면 `waiting`(노트 '차례를 기다리는 중입니다' 그대로 — TopicCard 가 대기 뼈대를 그린다), 그 생성이 failed 면 `blocked`(노트 `키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다`). waiting 은 키워드 생성이 열려 있을 때만이 아니다 — 씨앗 자리 카드 생성은 키워드 반영·취소와 **같은 트랜잭션**에 들어가는데(Task K5) 워커는 그 카드의 queued 이벤트를 따로 보내지 않고(정함 25) 취소 API 는 canceled 이벤트를 queued 이벤트보다 먼저 보낸다. 그래서 done·canceled 이벤트가 `state.work.generations` 에 먼저 들어오고(`applyGeneration`) topics·work 를 다시 읽기 전까지는 그 자리에 카드 생성이 없다 — 그 사이도 기다리는 중이다('카드를 만들지 못했습니다'가 잠깐 비치지 않게 — spec §12-8 장면 2 의 바로 그 순간). '키워드가 정해졌는데 카드 생성이 없는 씨앗 자리'가 오래 남는 경우는 없다(06b 이어가기는 자리마다 카드 생성을 같은 커밋에 넣었고, 06a 에서 이어간 연구에는 씨앗 행이 없다). 씨앗 자리가 아닌 빈 카드는 지금처럼 failed. 생성 기록이 있으면 생성 상태가 먼저다. `cardNote` 의 switch 는 반환 타입이 `string | null` 이라 `blocked` 를 빼면 typecheck 가 떨어진다.
- **다시 만드는 중인 카드(06e 정함 16):** 카드는 있는데 그 카드 생성이 열려 있으면(`[이 키워드로 다시 만들기]` — Task K6) `canPick` 이 거짓이고 `cardRemakingNote` 가 '새 키워드로 다시 만드는 중입니다'다. `cardStatus` 는 카드가 먼저라 ready 그대로다 — 막지 않으면 [고르기]가 켜진 채 고른 뒤 새 결과가 고른 카드를 바꾼다(서버도 Task K6 에서 막는다). dev 의 `canPick` 첫 단언 `item({ card: CARD })` 는 픽스처 기본 생성이 queued 라 06e 에서는 '다시 만드는 중'이 된다 — 끝난 생성으로 바꾼다(✎).
- `keywordsChanged` — 06e 전 카드(`keywords` 없음)는 무엇으로 만들었는지 몰라 알리지 않는다(false), 순서·띄어쓰기·대소문자는 보지 않는다(`conceptKey` — `addConcept` 의 중복 열쇠). `keywordWarning` — 키워드가 있고 그 전부가 `missing_keywords` 일 때만, **사용자가 고친 카드는 알리지 않는다**(서버 검사가 고친 제목을 다시 보지 않는다 — `edit_topic` 은 `missing_keywords` 를 다시 세지 않는다). `keywordChips` 배지: llm `AI 후보` · paper `논문 n편` · both `AI · 논문 n편` · 후보에 없는 고른 말 `직접`, 후보가 없으면(null·undefined·빈 목록) 고른 것을 눌린 칩으로만. `toggleKeyword` 는 `CONCEPTS_MAX`(5 — 서버 PATCH `MAX_CONCEPTS` 와 같다)를 넘기지 않는다. `aiCardsStale(topics, concepts, conceptsGen?)` — '다시 만들 AI 자리가 있다': 지금 키워드와 다른 키워드로 만든 AI 후보 카드(다시 만드는 중인 카드는 빼고), 그리고 키워드 생성이 실패해 카드가 없는 빈 씨앗 자리(`cardStatus(item, conceptsGen) === "blocked"`). 뒤의 것이 없으면 키워드 생성이 failed 인 연구에서 키워드를 직접 넣고 [키워드만 저장]을 누른 사용자가 막다른 길에 선다 — [다시]는 칩이 비어 있을 때만이고(`conceptsRetryable`), 저장 뒤 `dirty` 는 거짓이라 [이 키워드로 다시 만들기]도 숨는다. 서버 regenerate(Task K6)는 카드가 `{}` 인 후보 씨앗 행도 넣으므로 버튼만 보이면 카드가 들어간다. 세 번째 인자는 뼈대 1-6 시그니처에 없던 선택 인자다(이름은 그대로 — 파트 메모). origin user·고친·고른 카드는 세지 않는다(정함 16).
- **이름(1-6 계약 — 한 이름 한 파일):** `MIN_PICKED_KEYWORDS`·`keywordSpans`·`keywordsChanged`·`keywordWarning`·`KeywordChip`·`keywordChips`·`toggleKeyword`·`regenerateProblem`·`aiCardsStale`·`cardRemakingNote`(1-6 밖 — 파트 메모) 는 `topicDeck.ts` 만 내보낸다(dev `da80f23` 의 utils·composables 에 같은 이름 없음 — 확인함). `pages/index.vue:708` 에 지역 변수 `const keywordChips = ref(...)` 가 있지만 자동 import 는 파일 안 선언이 가린다 — 샌드박스 `nuxi typecheck` 오류 0·`npm run build` 의 WARN 57(기준선과 같음, 새 'Duplicated imports' 없음). 비공개 도우미(`flatten`·`keywordRanges`·`candidateBadge`·`remaking`)는 내보내지 않는다.
- **`RELOAD.concepts = ["topics", "work"]`**(1-4) — 키워드 반영이 씨앗 카드 생성을 넣으므로(Task K5) 주제 목록을 다시 읽어야 빈 슬롯이 '기다리는 중'이 된다. `workEvents.test.ts` 의 두 단언(`reloadFor`·'연구를 아직 받지 않았으면')을 함께 고친다(뒤의 것은 뼈대 목록 밖 ✎). 하트비트 재동기화 it 은 topic_card·concepts 가 같은 조회로 모여 그대로 `["topics", "work"]` 다.

- [ ] **Step 1: 고정 예제와 실패하는 테스트를 쓴다**

① `frontend/tests/fixtures/keyword_match.json` (새 파일, 전체 — 하이라이트 자리만. 일치 참·거짓의 정본은 06c 의 `term_checks.json` 이고 이 파일은 그 `contains` 칸과 같은 text/word 를 쓴다. 06e 만의 사례는 note 에 '06e 만'):

```json
[
  {"text": "노인의 우울과 사회적 지지", "word": "노인 우울", "marked": ["노인", "우울"], "note": "낱말이 순서대로 — 조각마다 감싼다(term_checks 와 같은 사례)"},
  {"text": "노인의 우울", "word": "우울 노인", "marked": [], "note": "순서가 바뀌면 맞지 않는다(같은 사례)"},
  {"text": "다문화 가정 아동", "word": "다문화가정", "marked": ["다문화 가정"], "note": "공백을 지우고 맞춘다 — 원문 자리는 공백을 품는다(같은 사례)"},
  {"text": "ＣＳＲ과 재무성과", "word": "csr", "marked": ["ＣＳＲ"], "note": "NFKC·casefold — 원문 글자 그대로 감싼다(같은 사례)"},
  {"text": "공공도서관 서비스", "word": "도서관", "marked": ["도서관"], "note": "부분 문자열(같은 사례)"},
  {"text": "컴퓨팅 자원 할당", "word": "클라우드", "marked": [], "note": "없는 낱말(같은 사례)"},
  {"text": "Digital Library Use", "word": "digital library", "marked": ["Digital Library"], "note": "영문 대소문자 — 06e 만"}
]
```

② `frontend/tests/unit/topicDeck.test.ts` 머리 import(Task R1 뒤 기준 — Task R1 은 import 를 고치지 않는다). 타입 import 에 `KeywordCandidate`, 값 import 에 새 이름(목록의 알파벳 순 자리 — Task H1 이 잡는 `  cardStatus,`·`  seedLine,` 줄은 그대로 둔다), 고정 예제. old:

```ts
import type { PaperMeta, TopicCard, TopicItem, TopicSeed, TopicsView, WorkGeneration } from "~/types/work";
import { genQueueLine } from "~/utils/queueLine";
import {
  addConcept,
```

new:

```ts
import type {
  KeywordCandidate,
  PaperMeta,
  TopicCard,
  TopicItem,
  TopicSeed,
  TopicsView,
  WorkGeneration,
} from "~/types/work";
import { genQueueLine } from "~/utils/queueLine";
import {
  addConcept,
  aiCardsStale,
```

③ 같은 import 목록의 가운데. old:

```ts
  evidenceChips,
  liveTopics,
  moreLine,
```

new:

```ts
  evidenceChips,
  keywordChips,
  keywordSpans,
  keywordWarning,
  keywordsChanged,
  liveTopics,
  MIN_PICKED_KEYWORDS,
  moreLine,
  regenerateProblem,
```

④ 같은 import 목록의 끝과 고정 예제. old:

```ts
  topicProblem,
} from "~/utils/topicDeck";
```

new:

```ts
  toggleKeyword,
  topicProblem,
} from "~/utils/topicDeck";
import keywordMatch from "../fixtures/keyword_match.json";
```

⑤ 같은 파일 describe `cardStatus` 끝에 it 하나 — 생성 기록이 없는 빈 카드(06e 부터 키워드를 기다리는 씨앗 자리). old:

```ts
  it("생성 기록이 없는 빈 카드·제목이 빈 카드는 카드가 없는 것으로 본다", () => {
    expect(cardStatus(item({ state: "insufficient", generation: null }))).toBe("insufficient");
    expect(cardStatus(item({ generation: null }))).toBe("failed");
    expect(cardStatus(item({ card: { ...CARD, title: " " }, generation: { id: 41, status: "done" } }))).toBe("insufficient");
  });
});
```

new:

```ts
  it("생성 기록이 없는 빈 카드·제목이 빈 카드는 카드가 없는 것으로 본다", () => {
    expect(cardStatus(item({ state: "insufficient", generation: null }))).toBe("insufficient");
    expect(cardStatus(item({ generation: null }))).toBe("failed");
    expect(cardStatus(item({ card: { ...CARD, title: " " }, generation: { id: 41, status: "done" } }))).toBe("insufficient");
  });

  it("생성 기록이 없는 빈 씨앗 자리는 키워드 생성이 있으면 waiting, 실패했으면 blocked 다(06e — 카드는 키워드가 정해진 뒤 들어간다)", () => {
    const concepts = (status: WorkGeneration["status"]) => gen({ id: 40, kind: "concepts", target: null, status });
    expect(cardStatus(item({ generation: null }), concepts("queued"))).toBe("waiting");
    expect(cardStatus(item({ generation: null }), concepts("running"))).toBe("waiting");
    // 씨앗 자리 카드 생성은 키워드 반영·취소와 같은 트랜잭션에 들어간다 — done·canceled 이벤트가 온 뒤 topics·work 를
    // 다시 읽기 전까지는 그 생성이 목록에 없다. 그 사이도 기다리는 중이다('카드를 만들지 못했습니다'가 비치지 않게)
    expect(cardStatus(item({ generation: null }), concepts("done"))).toBe("waiting");
    expect(cardStatus(item({ generation: null }), concepts("canceled"))).toBe("waiting");
    expect(cardStatus(item({ generation: null }), concepts("failed"))).toBe("blocked");
    expect(cardNote("blocked")).toBe("키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다");
    // 씨앗 자리가 아닌 빈 카드는 지금처럼 failed, 근거 부족은 그대로, 생성이 있으면 생성 상태가 먼저다
    expect(cardStatus(item({ generation: null, slot: null, origin: "other" }), concepts("done"))).toBe("failed");
    expect(cardStatus(item({ generation: null, slot: null, origin: "other" }), concepts("failed"))).toBe("failed");
    expect(cardStatus(item({ state: "insufficient", generation: null }), concepts("running"))).toBe("insufficient");
    expect(cardStatus(item({ generation: { id: 41, status: "running" } }), concepts("failed"))).toBe("making");
  });
});
```

⑥ 같은 파일 끝에 붙인다(Task R1 이 고친 describe `핵심 개념 칩` 뒤):

```ts
// ── 제목 고르기 — 키워드(06e D23) ──

// 06e 만의 하이라이트 자리 — 일치(참·거짓)의 정본은 06c 의 term_checks.json 이다(사례는 그 contains 칸과 같은 text/word)
interface KeywordMatchCase {
  text: string;
  word: string;
  marked: string[];
  note: string;
}
const MATCH_CASES: KeywordMatchCase[] = keywordMatch;

describe("keywordSpans — keyword_match.json 의 하이라이트 자리", () => {
  it("고정 예제가 맞음·안 맞음·공백 무시·전각·영문 사례를 다 갖고 있다", () => {
    expect(MATCH_CASES.some((c) => c.marked.length === 0)).toBe(true);
    expect(MATCH_CASES.some((c) => c.marked.length > 1)).toBe(true);
    expect(MATCH_CASES.some((c) => c.marked.some((m) => /\s/.test(m)))).toBe(true);
    expect(MATCH_CASES.some((c) => c.text !== c.text.normalize("NFKC"))).toBe(true);
    expect(MATCH_CASES.some((c) => /[A-Za-z]/.test(c.text))).toBe(true);
  });

  it.each(MATCH_CASES)("$note", (c) => {
    const parts = keywordSpans(c.text, [c.word]);
    expect(parts.filter((p) => p.mark).map((p) => p.text)).toEqual(c.marked);
    expect(parts.map((p) => p.text).join("")).toBe(c.text);
  });

  it("여러 키워드는 각자 처음 맞은 자리를, 겹치는 자리는 하나로 감싼다", () => {
    expect(keywordSpans("독거노인의 사회적 지지와 우울", ["사회적 지지", "노인 우울", "지지"])).toEqual([
      { text: "독거", mark: false },
      { text: "노인", mark: true },
      { text: "의 ", mark: false },
      { text: "사회적 지지", mark: true },
      { text: "와 ", mark: false },
      { text: "우울", mark: true },
    ]);
    expect(keywordSpans("노인 우울", [])).toEqual([{ text: "노인 우울", mark: false }]);
    expect(keywordSpans("", ["노인"])).toEqual([]);
  });
});

describe("keywordsChanged·keywordWarning", () => {
  const made: TopicCard = { ...CARD, keywords: ["노인 우울", "사회적 지지"] };

  it("카드를 만든 키워드와 지금 고른 키워드가 다르면 바뀌었다 — 순서·띄어쓰기는 보지 않고, 06e 전 카드는 알리지 않는다", () => {
    expect(keywordsChanged(made, ["사회적지지", "노인 우울"])).toBe(false);
    expect(keywordsChanged(made, ["노인 우울"])).toBe(true);
    expect(keywordsChanged(made, ["노인 우울", "가족 지지"])).toBe(true);
    expect(keywordsChanged({ ...made, keywords: [] }, ["노인 우울"])).toBe(true);
    expect(keywordsChanged(CARD, ["노인 우울"])).toBe(false);
  });

  it("제목에 고른 키워드가 하나도 없을 때만 경고하고, 사용자가 고친 카드는 알리지 않는다", () => {
    const missed: TopicCard = { ...made, checks: { ...CARD.checks, missing_keywords: ["노인 우울", "사회적 지지"] } };
    expect(keywordWarning(missed)).toBe("제목에 「노인 우울」·「사회적 지지」 없음");
    expect(keywordWarning({ ...missed, checks: { ...CARD.checks, missing_keywords: ["노인 우울"] } })).toBeNull();
    expect(keywordWarning({ ...missed, edited: true })).toBeNull();
    expect(keywordWarning({ ...CARD, keywords: [] })).toBeNull();
    expect(keywordWarning(CARD)).toBeNull();
  });
});

describe("keywordChips·toggleKeyword·regenerateProblem", () => {
  const CANDS: KeywordCandidate[] = [
    { text: "노인 우울", source: "both", n: 4 },
    { text: "사회적 지지", source: "llm", n: 0 },
    { text: "독거노인", source: "paper", n: 3 },
  ];

  it("후보를 낸 순서대로, 고른 것은 눌린 칩·출처와 편수 배지, 후보에 없는 고른 말은 뒤에 '직접'", () => {
    expect(keywordChips(CANDS, ["사회적지지", "가족 돌봄"])).toEqual([
      { text: "노인 우울", pressed: false, badge: "AI · 논문 4편" },
      { text: "사회적 지지", pressed: true, badge: "AI 후보" },
      { text: "독거노인", pressed: false, badge: "논문 3편" },
      { text: "가족 돌봄", pressed: true, badge: "직접" },
    ]);
  });

  it("후보가 없는 연구(06e 전·예시)는 고른 키워드를 눌린 칩으로만 보인다", () => {
    const want = [{ text: "노인 우울", pressed: true, badge: null }];
    expect(keywordChips(null, ["노인 우울"])).toEqual(want);
    expect(keywordChips(undefined, ["노인 우울"])).toEqual(want);
    expect(keywordChips([], ["노인 우울"])).toEqual(want);
  });

  it("toggleKeyword — 고른 것은 빼고 아니면 뒤에 더하되 칩 상한(5)을 넘지 않는다, regenerateProblem — 둘 미만이면 까닭", () => {
    expect(toggleKeyword(["노인 우울", "사회적 지지"], "노인우울")).toEqual(["사회적 지지"]);
    expect(toggleKeyword(["노인 우울"], "독거노인")).toEqual(["노인 우울", "독거노인"]);
    const full = ["가", "나", "다", "라", "마"];
    expect(toggleKeyword(full, "바")).toEqual(full);
    expect(MIN_PICKED_KEYWORDS).toBe(2);
    expect(regenerateProblem(["노인 우울"])).toBe("키워드를 2개 이상 고르면 다시 만들 수 있습니다");
    expect(regenerateProblem(["노인 우울", "독거노인"])).toBeNull();
  });
});

describe("aiCardsStale — 다시 만들 AI 자리가 있다", () => {
  const made: TopicCard = { ...CARD, keywords: ["노인 우울", "사회적 지지"] };
  const now = ["노인 우울", "독거노인"];
  const concepts = (status: WorkGeneration["status"]) => gen({ id: 40, kind: "concepts", target: null, status });

  it("지금 키워드와 다른 키워드로 만든 AI 후보 카드가 있을 때 — 고른·고친·직접 쓴 카드와 다시 만드는 중인 카드는 세지 않는다", () => {
    const done = { id: 41, status: "done" as const };
    expect(aiCardsStale(deck([item({ card: made, generation: done })]), now)).toBe(true);
    expect(aiCardsStale(deck([item({ card: made, generation: done })]), ["사회적 지지", "노인 우울"])).toBe(false);
    expect(aiCardsStale(deck([item({ card: made, state: "picked" })]), now)).toBe(false);
    expect(aiCardsStale(deck([item({ card: { ...made, edited: true } })]), now)).toBe(false);
    expect(aiCardsStale(deck([item({ card: made, origin: "user", seed: null })]), now)).toBe(false);
    expect(aiCardsStale(deck([item({ card: null, state: "insufficient" })]), now)).toBe(false);
    expect(aiCardsStale(deck([item({ card: made, generation: { id: 52, status: "running" } })]), now)).toBe(false);
  });

  it("키워드 생성이 실패해 카드가 들어가지 않은 빈 씨앗 자리(blocked)도 다시 만들 자리다 — 키워드를 직접 넣고 저장한 뒤의 길", () => {
    const blocked = deck([item({ card: null, generation: null })]);
    expect(aiCardsStale(blocked, now, concepts("failed"))).toBe(true);
    // 키워드 생성이 끝난 직후(카드 생성을 다시 읽기 전)는 기다리는 중이라 세지 않는다
    expect(aiCardsStale(blocked, now, concepts("done"))).toBe(false);
    expect(aiCardsStale(blocked, now)).toBe(false);
  });
});
```

⑦ `frontend/tests/unit/workEvents.test.ts` describe `reloadFor` — 키워드(concepts) 반영이 씨앗 카드 생성을 넣으므로 주제 목록도 다시 읽는다. old:

```ts
  it("끝난 생성의 종류로 다시 읽을 조회를 정하고, 모든 종류가 연구(work)도 다시 읽는다", () => {
    expect(reloadFor("concepts")).toEqual(["work"]);
```

new:

```ts
  it("끝난 생성의 종류로 다시 읽을 조회를 정하고, 모든 종류가 연구(work)도 다시 읽는다", () => {
    // 06e — 키워드 반영이 씨앗 카드 생성을 넣는다(D23). 주제 목록을 다시 읽어야 빈 슬롯이 '기다리는 중'이 된다
    expect(reloadFor("concepts")).toEqual(["topics", "work"]);
```

⑧ 같은 파일 describe `applyWorkEvent — generation` 의 '연구를 아직 받지 않았으면' it — 같은 까닭. old:

```ts
    const out = applyWorkEvent(initialWorkState(), genEvent({ gen_kind: "concepts", target: null, status: "done" }));
    expect(out.state.work).toBeNull();
    expect(out.reload).toEqual(["work"]);
```

new:

```ts
    const out = applyWorkEvent(initialWorkState(), genEvent({ gen_kind: "concepts", target: null, status: "done" }));
    expect(out.state.work).toBeNull();
    expect(out.reload).toEqual(["topics", "work"]);
```

⑨ `frontend/tests/unit/topicDeck.test.ts` describe `canPick`(dev `da80f23` `:151-158`) — 다시 만드는 중인 카드(카드는 있고 카드 생성이 열려 있다)는 고르지 않는다(06e 정함 16). 지금 첫 단언의 `item({ card: CARD })` 는 픽스처 기본 생성이 queued 라 06e 에서는 '다시 만드는 중'이다 — 끝난(done) 생성과 생성 기록 없는 사용자 카드로 바꾼다(✎). old:

```ts
describe("canPick", () => {
  it("카드가 있는 후보만 고를 수 있다", () => {
    expect(canPick(item({ card: CARD }))).toBe(true);
```

new:

```ts
describe("canPick", () => {
  it("카드를 새 키워드로 다시 만드는 중이면(카드 생성이 열려 있으면) 고르지 않고 그 줄을 보인다(06e 정함 16)", () => {
    for (const status of ["queued", "running"] as const) {
      const remaking = item({ card: CARD, generation: { id: 52, status } });
      expect(canPick(remaking)).toBe(false);
      expect(cardRemakingNote(remaking)).toBe("새 키워드로 다시 만드는 중입니다");
    }
    expect(cardRemakingNote(item({ card: CARD, generation: { id: 52, status: "done" } }))).toBeNull();
    expect(cardRemakingNote(item({ card: CARD, generation: null, origin: "user" }))).toBeNull();
    // 카드가 없는 자리의 열린 생성은 대기 뼈대(cardStatus waiting·making)가 알린다
    expect(cardRemakingNote(item({ generation: { id: 52, status: "running" } }))).toBeNull();
  });

  it("카드가 있는 후보만 고를 수 있다", () => {
    expect(canPick(item({ card: CARD, generation: { id: 41, status: "done" } }))).toBe(true);
    expect(canPick(item({ card: CARD, generation: null, origin: "user" }))).toBe(true);
```

⑩ `frontend/tests/unit/topicDeck.test.ts` 머리 import — `cardRemakingNote`(알파벳 순 자리 — Task H1 이 잡는 `  cardStatus,` 줄은 그대로 둔다). old:

```ts
  cardNote,
```

new:

```ts
  cardNote,
  cardRemakingNote,
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/topicDeck.test.ts tests/unit/workEvents.test.ts`

Expected: `Tests  19 failed | 52 passed (71)` — `topicDeck.test.ts` 17개(새 it 18개 가운데 고정 예제의 모양만 보는 '고정 예제가 맞음·안 맞음…' it 하나는 통과 — 나머지는 `keywordSpans`·`cardRemakingNote` 등이 없어 TypeError, `cardStatus` 새 it 은 'failed' 가 오고 `canPick` 새 it 은 다시 만드는 중인 카드에 참이 온다. 고친 `canPick` 첫 it 은 그대로 통과), `workEvents.test.ts` 2개(`reloadFor("concepts")` 가 `["work"]`)

- [ ] **Step 3: 구현한다**

① `frontend/types/work.ts` — `WorkView` 앞에 `KeywordCandidate`, `WorkView` 에 선택 필드(Task A3·Task X3·Task S3 가 고친 Outline·ProposalView·인용 근거 타입과 겹치지 않는 자리). old:

```ts
export interface WorkView {
  id: string;
  phase: WorkPhase;
  concepts: string[];
  memo: string | null;
  is_example: boolean;
  progress: Partial<WorkProgress>;
  topic_id?: number | null;
  corpus?: Corpus | null;
  generations: WorkGeneration[];
}
```

new:

```ts
// 키워드 후보(06e 제목 고르기 — 키워드 생성 output.candidates). source 는 출처(모델·채택 논문의 소장 키워드·둘 다),
// n 은 그 키워드를 가진 채택 논문 수(모델만이면 0)
export interface KeywordCandidate {
  text: string;
  source: "llm" | "paper" | "both";
  n: number;
}

export interface WorkView {
  id: string;
  phase: WorkPhase;
  concepts: string[];
  memo: string | null;
  is_example: boolean;
  progress: Partial<WorkProgress>;
  topic_id?: number | null;
  corpus?: Corpus | null;
  generations: WorkGeneration[];
  // 최신 done 키워드 생성의 후보(06e) — 06e 전 생성·키워드 생성이 끝나지 않은 연구는 null
  concept_candidates?: KeywordCandidate[] | null;
}
```

② 같은 파일 `TopicCard` — 만들 때 넘긴 키워드와 제목에 없는 키워드(서버 Task K9). old:

```ts
  latest_year: number | null;
  edited: boolean;
  checks: { numbers: string[]; softened: number; recovered: number };
  gen_id: number | null;
}
```

new:

```ts
  latest_year: number | null;
  edited: boolean;
  // 카드를 만들 때 넘긴 고른 키워드(06e) — 06e 전 카드·사용자 카드엔 없다
  keywords?: string[];
  // missing_keywords — keywords 가운데 제목에 들어 있지 않은 것(06e)
  checks: { numbers: string[]; softened: number; recovered: number; missing_keywords?: string[] };
  gen_id: number | null;
}
```

③ `frontend/utils/topicDeck.ts` 타입 import(Task R1 뒤 기준 — Task R1 은 `conceptsNote` 문구만 고친다). old:

```ts
  GenStatus,
  PaperMeta,
```

new:

```ts
  GenStatus,
  KeywordCandidate,
  PaperMeta,
```

④ 같은 파일 `CardStatus`. old:

```ts
export type CardStatus = "waiting" | "making" | "ready" | "insufficient" | "failed";
```

new:

```ts
// blocked — 키워드 생성이 실패해 씨앗 카드가 아직 들어가지 않은 자리(06e D23 — 키워드를 다시 부르면 카드가 들어간다)
export type CardStatus = "waiting" | "making" | "ready" | "insufficient" | "failed" | "blocked";
```

⑤ 같은 파일 상수(Task H1 이 잡는 `CHIP_TITLE_CHARS` 줄은 건드리지 않는다). old:

```ts
export const CONCEPTS_MAX = 5;
export const CONCEPT_LEN_MAX = 40;
```

new:

```ts
export const CONCEPTS_MAX = 5;
export const CONCEPT_LEN_MAX = 40;
// [이 키워드로 다시 만들기] 의 최소 선택 수(keywords.MIN_PICKED_KEYWORDS) — 선행연구 묶음 수가 키워드 수 이하다
export const MIN_PICKED_KEYWORDS = 2;
```

⑥ 같은 파일 `cardStatus`(dev `da80f23` `:60-71`). old:

```ts
// 카드가 있으면 ready. 없으면 그 주제의 마지막 카드 생성으로 가른다 — 끝났는데(done) 카드가 없으면 근거 부족이고
// (서버 topic_card.apply 가 state 를 insufficient 로 둔다), 실패·취소면 failed. 생성 기록이 없는 빈 카드는
// 다시 부를 생성도 없으므로 근거 부족(state 가 그렇다면) 또는 failed 로 둔다
export function cardStatus(item: TopicItem): CardStatus {
  if (cardOf(item)) return "ready";
  const g = item.generation;
  if (!g) return item.state === "insufficient" ? "insufficient" : "failed";
```

new:

```ts
// 카드가 있으면 ready. 없으면 그 주제의 마지막 카드 생성으로 가른다 — 끝났는데(done) 카드가 없으면 근거 부족이고
// (서버 topic_card.apply 가 state 를 insufficient 로 둔다), 실패·취소면 failed. 생성 기록이 없는 빈 씨앗 자리(slot 이 있는
// 보고서 씨앗)는 06e 부터 키워드가 정해지기를 기다린다(D23) — 씨앗 자리 카드 생성은 키워드 생성의 반영·취소와 같은
// 트랜잭션에 들어간다. 그래서 키워드 생성(concepts)이 열려 있을 때뿐 아니라 done·canceled 이벤트와 topics·work 다시 읽기
// 사이도 waiting 이고, 키워드 생성이 실패했으면 카드가 들어가지 않아 blocked. 그 밖은 근거 부족(state 가 그렇다면) 또는 failed
export function cardStatus(item: TopicItem, concepts?: WorkGeneration | null): CardStatus {
  if (cardOf(item)) return "ready";
  const g = item.generation;
  if (!g) {
    if (item.state === "insufficient") return "insufficient";
    if (concepts && item.slot !== null && item.origin === "report_seed") {
      return concepts.status === "failed" ? "blocked" : "waiting";
    }
    return "failed";
  }
```

⑦ 같은 파일 `cardNote`. old:

```ts
    case "failed":
      return "카드를 만들지 못했습니다";
    case "ready":
      return null;
  }
}
```

new:

```ts
    case "failed":
      return "카드를 만들지 못했습니다";
    case "blocked":
      return "키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다";
    case "ready":
      return null;
  }
}
```

⑧ 같은 파일 끝(`conceptsNote` 뒤)에 붙인다:

```ts
// ── 제목 고르기 — 키워드(06e D23) ──

// 원문 → 글자 맞추기용 평평한 글. 원문 글자(코드포인트)마다 NFKC·소문자로 바꾼 글자를 잇고 공백은 뺀다. at[k] 는 평평한
// 글의 k 번째 UTF-16 단위가 나온 원문 글자 순번이다 — 맞은 자리를 원문 그대로 감싸려고(전각 'ＣＳＲ' 은 'csr' 로 맞추고
// 'ＣＳＲ' 을 감싼다, 공백을 지우고 맞춘 '다문화가정' 은 원문 '다문화 가정' 을 감싼다)
function flatten(chars: readonly string[]): { flat: string; at: number[] } {
  let flat = "";
  const at: number[] = [];
  chars.forEach((ch, i) => {
    for (const c of ch.normalize("NFKC").toLowerCase()) {
      if (/\s/.test(c)) continue;
      flat += c;
      for (let u = 0; u < c.length; u += 1) at.push(i);
    }
  });
  return { flat, at };
}

// 낱말 하나의 맞은 자리(원문 글자 순번 [처음, 끝]) — 서버 06c terms.contains 와 같은 규칙: 공백을 지운 글에서 낱말 전체가
// 부분 문자열이면 그 자리, 아니면 낱말 조각이 모두 순서대로 있을 때 조각마다. 하나라도 없으면 맞지 않는다(빈 배열)
function keywordRanges(flat: string, at: readonly number[], word: string): [number, number][] {
  const pieces = word.normalize("NFKC").toLowerCase().split(/\s+/).filter(Boolean);
  if (!pieces.length) return [];
  const joined = pieces.join("");
  const hit = flat.indexOf(joined);
  if (hit >= 0) return [[at[hit]!, at[hit + joined.length - 1]!]];
  const out: [number, number][] = [];
  let pos = 0;
  for (const piece of pieces) {
    const found = flat.indexOf(piece, pos);
    if (found < 0) return [];
    out.push([at[found]!, at[found + piece.length - 1]!]);
    pos = found + piece.length;
  }
  return out;
}

// 카드 제목 속 키워드 자리 — <mark> 로 감쌀 조각. 이어 붙이면 원문 그대로다. 키워드마다 처음 맞은 자리만(서버 검사와 같은
// '들어 있음' 판정), 겹치거나 맞닿은 자리는 하나로 합친다. 일치 규칙의 정본은 06c 의 frontend/tests/fixtures/term_checks.json
export function keywordSpans(title: string, keywords: readonly string[]): { text: string; mark: boolean }[] {
  const chars = [...title];
  if (!chars.length) return [];
  const { flat, at } = flatten(chars);
  const ranges = keywords.flatMap((k) => keywordRanges(flat, at, k)).sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const [start, end] of ranges) {
    const last = merged[merged.length - 1];
    if (last && start <= last[1] + 1) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  const parts: { text: string; mark: boolean }[] = [];
  let pos = 0;
  for (const [start, end] of merged) {
    if (start > pos) parts.push({ text: chars.slice(pos, start).join(""), mark: false });
    parts.push({ text: chars.slice(start, end + 1).join(""), mark: true });
    pos = end + 1;
  }
  if (pos < chars.length) parts.push({ text: chars.slice(pos).join(""), mark: false });
  return parts;
}

// 카드를 만들 때 넘긴 키워드(card.keywords)가 지금 고른 키워드와 다른가 — 순서·띄어쓰기·대소문자는 보지 않는다.
// 06e 전 카드(keywords 없음)는 무엇으로 만들었는지 모르니 알리지 않는다
export function keywordsChanged(card: TopicCard, concepts: readonly string[]): boolean {
  if (!card.keywords) return false;
  const made = new Set(card.keywords.map(conceptKey));
  const now = new Set(concepts.map(conceptKey));
  return made.size !== now.size || [...made].some((k) => !now.has(k));
}

// 고른 키워드를 제목에 하나도 넣지 못한 카드 — 서버가 세 번 다 놓친 카드를 버리지 않고 마지막 답을 보관한다(06e 정함 17).
// 사용자가 고친 카드는 서버 검사가 고친 제목을 보지 않아 알리지 않는다
export function keywordWarning(card: TopicCard): string | null {
  const keywords = card.keywords ?? [];
  const missing = new Set(card.checks?.missing_keywords ?? []);
  if (card.edited || !keywords.length || !keywords.every((k) => missing.has(k))) return null;
  return `제목에 ${keywords.map((k) => `「${k}」`).join("·")} 없음`;
}

export interface KeywordChip {
  text: string;
  pressed: boolean;
  badge: string | null;
}

function candidateBadge(c: KeywordCandidate): string {
  if (c.source === "paper") return `논문 ${c.n}편`;
  if (c.source === "both") return `AI · 논문 ${c.n}편`;
  return "AI 후보";
}

// 키워드 칩 — 후보(최신 키워드 생성)를 낸 순서대로, 고른 것은 눌린 칩. 후보에 없는 고른 말(직접 더한 것)은 뒤에 '직접'.
// 후보가 없는 연구(06e 전·예시 연구)는 지금 고른 키워드를 눌린 칩으로만 보인다
export function keywordChips(
  candidates: readonly KeywordCandidate[] | null | undefined,
  picked: readonly string[],
): KeywordChip[] {
  if (!candidates?.length) return picked.map((text) => ({ text, pressed: true, badge: null }));
  const pickedKeys = new Set(picked.map(conceptKey));
  const shown = new Set(candidates.map((c) => conceptKey(c.text)));
  return [
    ...candidates.map((c) => ({ text: c.text, pressed: pickedKeys.has(conceptKey(c.text)), badge: candidateBadge(c) })),
    ...picked.filter((text) => !shown.has(conceptKey(text))).map((text) => ({ text, pressed: true, badge: "직접" })),
  ];
}

// 칩 하나를 누르면 — 고른 것이면 빼고, 아니면 뒤에 더한다. 고른 수는 칩 상한(CONCEPTS_MAX — 서버 PATCH 와 같다)을 넘지 않는다
export function toggleKeyword(picked: readonly string[], text: string): string[] {
  const key = conceptKey(text);
  if (picked.some((p) => conceptKey(p) === key)) return picked.filter((p) => conceptKey(p) !== key);
  if (picked.length >= CONCEPTS_MAX) return [...picked];
  return [...picked, text];
}

// [이 키워드로 다시 만들기] 를 막는 까닭 — 선행연구 묶음 수가 키워드 수 이하라 둘 이상 골라야 한다(서버도 409)
export function regenerateProblem(picked: readonly string[]): string | null {
  return picked.length < MIN_PICKED_KEYWORDS
    ? `키워드를 ${MIN_PICKED_KEYWORDS}개 이상 고르면 다시 만들 수 있습니다`
    : null;
}

// 다시 만들 AI 자리가 있는가 — 칩을 고치지 않아도 [이 키워드로 다시 만들기] 를 보일 때. ① 지금 키워드와 다른 키워드로
// 만든 AI 후보 카드(다시 만드는 중인 카드는 빼고), ② 키워드 생성이 실패해 카드가 들어가지 않은 빈 씨앗 자리(blocked —
// 키워드를 직접 넣고 [키워드만 저장] 한 뒤 카드를 받는 길. 서버 regenerate 는 카드 없는 후보 씨앗 행도 넣는다). 고른 카드·
// 고친 카드·사용자가 쓴 카드는 다시 만들지 않으므로 세지 않는다(06e 정함 16). conceptsGen 은 최신 키워드 생성(cardStatus)
export function aiCardsStale(
  topics: TopicsView,
  concepts: readonly string[],
  conceptsGen?: WorkGeneration | null,
): boolean {
  return topics.items.some((item) => {
    if (item.state === "candidate" && cardStatus(item, conceptsGen) === "blocked") return true;
    const card = cardOf(item);
    return (
      item.origin !== "user" && item.state === "candidate" && card !== null && !card.edited &&
      !remaking(item) && keywordsChanged(card, concepts)
    );
  });
}
```

⑨ `frontend/utils/workEvents.ts` `RELOAD`(dev `da80f23` `:26-34`). old:

```ts
// 생성이 끝나면 다시 읽을 조회. 모든 kind 가 work 도 다시 읽는다 — 진행 요약(progress)과 남은 생성의 순번이 바뀐다
const RELOAD: Record<GenKind, readonly WorkResource[]> = {
  concepts: ["work"],
```

new:

```ts
// 생성이 끝나면 다시 읽을 조회. 모든 kind 가 work 도 다시 읽는다 — 진행 요약(progress)과 남은 생성의 순번이 바뀐다.
// 키워드(concepts) 반영은 씨앗 카드 생성을 넣는다(06e D23) — 주제 목록을 다시 읽어야 빈 슬롯이 '기다리는 중'이 된다
const RELOAD: Record<GenKind, readonly WorkResource[]> = {
  concepts: ["topics", "work"],
```

⑩ `frontend/composables/useResearchWork.ts` `useWorkApi()` — `generateTopics` 바로 뒤(Task S3 가 더한 `getSectionSources` 와 겹치지 않는 자리). old:

```ts
    generateTopics: (jobId: string) =>
      api<{ topic_ids: number[]; gen_ids: number[] }>(`${job(jobId)}/topics/generate`, {
        method: "POST",
        body: { mode: "other" },
      }),
```

new:

```ts
    generateTopics: (jobId: string) =>
      api<{ topic_ids: number[]; gen_ids: number[] }>(`${job(jobId)}/topics/generate`, {
        method: "POST",
        body: { mode: "other" },
      }),
    // [이 키워드로 다시 만들기] — 저장된 키워드(work.concepts)로 고치지 않은 AI 카드를 다시(06e). skipped = 만드는 중이라 건너뛴 수
    regenerateTopics: (jobId: string) =>
      api<{ topic_ids: number[]; gen_ids: number[]; skipped: number }>(`${job(jobId)}/topics/regenerate`, {
        method: "POST",
      }),
```

⑪ `frontend/utils/topicDeck.ts` `canPick`(dev `da80f23` `:94-96`) — 다시 만드는 중인 카드는 고르지 않는다, 그 카드에 붙이는 줄(06e 정함 16 — 서버 `topic_card.apply` 의 고른 카드 검사는 Task K6). old:

```ts
export function canPick(item: TopicItem): boolean {
  return item.state === "candidate" && cardStatus(item) === "ready";
}
```

new:

```ts
// 카드는 있는데 그 카드 생성이 열려 있다 — [이 키워드로 다시 만들기](06e)가 넣은 새 카드를 기다리는 중
function remaking(item: TopicItem): boolean {
  return cardOf(item) !== null && item.generation !== null && OPEN.includes(item.generation.status);
}

// 다시 만드는 중인 카드는 고르지 않는다 — 고른 카드는 다시 만든 결과로 덮지 않으므로(서버 topic_card.apply,
// 06e 정함 16) 고르면 새 카드가 버려진다
export function canPick(item: TopicItem): boolean {
  return item.state === "candidate" && cardStatus(item) === "ready" && !remaking(item);
}

// 다시 만드는 중인 카드에 붙이는 줄 — 새 결과가 반영될 때까지 지금 카드를 그대로 보인다
export function cardRemakingNote(item: TopicItem): string | null {
  return remaking(item) ? "새 키워드로 다시 만드는 중입니다" : null;
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/topicDeck.test.ts tests/unit/workEvents.test.ts`

Expected: `Tests  71 passed (71)` (topicDeck 44 · workEvents 27 — topicDeck 은 Task R1 뒤 26 에 18 을 더했다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run 2>&1 | tail -4`

Expected: 실패 0, `Tests` = Task 앞 + 18(파일 수 그대로 — 새 테스트 파일 없음)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`

Expected: `0`(새 타입 필드는 모두 선택 — 기존 픽스처·부품이 그대로다. `cardStatus` 의 두 번째 인자도 선택)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/tests/fixtures/keyword_match.json frontend/types/work.ts frontend/utils/topicDeck.ts frontend/utils/workEvents.ts frontend/composables/useResearchWork.ts frontend/tests/unit/topicDeck.test.ts frontend/tests/unit/workEvents.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 제목 고르기 판정 순수 함수를 더한다(D23, spec §12-4). keywordSpans(제목 속 고른 키워드 자리 — 06c terms.contains 와 같은 일치 규칙, 원문 글자 그대로 감싼다)·keywordsChanged('키워드가 바뀌었습니다' — 06e 전 카드는 알리지 않는다)·keywordWarning(세 번 다 놓친 카드의 '제목에 「…」 없음' — 고친 카드는 알리지 않는다)·keywordChips(후보 토글 칩 — 출처·편수 배지, 후보에 없는 고른 말은 '직접', 후보 없는 연구는 고른 것만)·toggleKeyword(상한 5)·regenerateProblem(2개 미만)·aiCardsStale(다시 만들 AI 자리 — 키워드와 다른 AI 카드, 키워드 생성이 실패해 카드가 없는 씨앗 자리). cardStatus 는 생성 기록 없는 빈 씨앗 자리를 키워드 생성이 있으면 waiting(반영·취소 이벤트와 다시 읽기 사이 포함 — 카드 생성은 같은 트랜잭션에 들어간다), 실패면 blocked('키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다')로. 다시 만드는 중인 카드(카드 생성이 열린 카드)는 canPick 이 거짓이고 cardRemakingNote 가 그 줄을 준다(06e 정함 16). 타입 KeywordCandidate·WorkView.concept_candidates·TopicCard.keywords·checks.missing_keywords(모두 선택), RELOAD.concepts 에 topics, useWorkApi.regenerateTopics. 하이라이트 자리 고정 예제 keyword_match.json(일치 참·거짓의 정본은 06c term_checks.json)"
```

---

### Task K8: 키워드 칩·제목 하이라이트·다시 만들기 화면

**왜:** spec §12-4 '칩 UI'·'하이라이트(`TopicCard.vue:32` `<mark>`)'·'[이 키워드로 다시 만들기] — 칩을 바꾸면 보인다'·'키워드가 바뀌었습니다'·'화면 — 빈 카드 waiting / 키워드를 다시 부르면 카드를 만듭니다', 정함 15·16·17. Task K7 의 판정을 화면에 잇는다 — 핵심 개념 칩([×] 빼기)을 후보 토글 칩으로 다시 짜고, 카드 제목의 고른 키워드를 감싸고, 칩을 바꾸거나 키워드와 다른 카드가 있으면 [이 키워드로 다시 만들기]를 보인다.

**Files:**
- Modify: `frontend/components/work/ConceptChips.vue` (전체를 갈음 — Task R1 의 보이는 글 '키워드' 를 품는다)
- Modify: `frontend/components/work/TopicCard.vue` (템플릿 32-33·[직접 고치기] 81-89, script import 97·99-110, props 113-122, `numbersLine` 129 뒤)
- Modify: `frontend/components/work/TopicDeck.vue` (템플릿 9-12·25, script 64-69·79)
- Modify: `frontend/components/work/TopicsStep.vue` (Task R1 뒤 기준 — ConceptChips 15-23, TopicDeck 45-47, import 72, `conceptGen` 96 뒤, `retryCard` 159 앞)
- Modify: `frontend/assets/css/work.css` (이어 붙이는 자리 표시 줄 위에 한 묶음)

**알아 둘 것:**
- `.vue` 는 단위 테스트하지 않는다 — 판단은 모두 Task K7 의 순수 함수다. 확인은 `npx nuxi typecheck`(오류 0)·`npm run build`(완료, WARN 수가 Task 앞과 같다 — 새 'Duplicated imports' 없음)·vitest 전체(그대로).
- **ConceptChips(1-7):** props `{ concepts, candidates, generation, readOnly, busy, stale }`, emits `save`(그대로)·`regenerate`(새)·`retry`(그대로 `[genId: number]` — 1-7 표의 `retry: []` 는 '그대로'라 지금 시그니처를 지킨다, 파트 메모). 칩은 `<button type="button" class="wk-kwchip" :aria-pressed>` + 배지, 상한(5)이 차면 고르지 않은 칩은 막는다. **직접 더하기는 남긴다**(정함 15 — 지금의 `addConcept` 규칙, 배지 '직접'). [키워드만 저장]은 지금의 [저장]이다(목차 묶음에만 쓰고 카드를 다시 만들지 않을 때 — 저장하면 카드에 '키워드가 바뀌었습니다'가 붙고 [이 키워드로 다시 만들기]가 그대로 보인다). [이 키워드로 다시 만들기]는 고른 것이 저장과 다르거나(`dirty`) `stale` 일 때 보이고, 둘 미만이면 막고 까닭(`regenerateProblem`)을 `aria-describedby` 로 잇는다. 생성 상태 줄(`conceptsNote` — Task R1 문구)·[다시]는 그대로.
- **TopicCard:** 제목 `<h3>` 안을 `keywordSpans(card.title, card.keywords ?? [])` 조각으로 — 같은 파일의 수치 문장(`figurePieces` — `:40-43`)과 같은 `<template v-for>` 방식이라 조각 사이에 공백이 끼지 않는다. 경고 줄(`.wk-topic__kwwarn`), '키워드가 바뀌었습니다'(`.wk-topic__kwchanged` — 고른·고친·사용자 카드엔 없다, 정함 16). `cardStatus(item, conceptsGen)` 로 빈 씨앗 자리의 waiting·blocked — blocked 는 대기 뼈대 없이 씨앗 글과 노트를 보이고 [다시] 가 없다(`retryId` 는 insufficient·failed 만 — 다시 부를 것은 키워드 칩의 [다시]나 [이 키워드로 다시 만들기]다). 다시 만드는 중인 카드는 `cardRemakingNote` 줄('새 키워드로 다시 만드는 중입니다')을 달고 [고르기](`canPick`)·[직접 고치기](서버 409 `CARD_BUSY`)를 막으며 그동안 '키워드가 바뀌었습니다'는 달지 않는다(06e 정함 16).
- **TopicDeck:** 받은 `concepts`·`conceptsGen` 을 카드에 내려 주고, 키워드를 고르는 동안 [다른 방향]을 막는다(서버 409 `KEYWORDS_BUSY` — Task K4. 뼈대에 없던 작은 더함 — 파트 메모).
- **TopicsStep:** ConceptChips 에 `candidates = view.concept_candidates ?? null`·`stale = aiCardsStale(topics, view.concepts, conceptGen)`(키워드 생성이 실패해 카드가 없는 씨앗 자리도 센다 — Task K7), `@regenerate`: 고른 것이 저장과 다르면 `patchWork({ concepts })` → `regenerateTopics(jobId)` → `act` 가 `topics`·`work` 를 다시 읽고 `afterAction()`, 오류는 `workErrorMessage`, 409 면 `topics`·`work` 를 다시 읽는다(기존 `act` 그대로). 이 함수는 `retryCard` 앞에 둔다 — Task R1 이 고친 `saveConcepts`·`retryConcepts` 의 오류 문구 줄(`:151`·`:156`)을 old 로 잡지 않는다.
- **CSS(1-8 Task K8 묶음):** `.wk-kwchip`·`[aria-pressed="true"]`·`:disabled`·`:focus-visible`·`__badge`, `.wk-kw`(제목 속 `<mark>` — 배경 `--skx-border-c1`), `.wk-topic__kwwarn`·`.wk-topic__kwchanged`. 1-8 표 밖으로 `.wk-concepts__regen`(다시 만들기 줄)과 `.wk-topic--blocked`(근거 부족·실패와 같은 점선)를 함께 둔다(파트 메모). `--skx-*` 토큰만 읽는다. 06b 의 `.wk-concept`·`.wk-concept__remove` 는 쓰는 곳이 없어지지만 지우지 않는다(시각 디자인 담당이 정리할 자리).
- 화면 확인(브라우저)은 마무리 운영 확인(뼈대 §7-11 — '키워드 후보 칩(위 3개 켜짐·출처·편수 배지) → 카드 4장 제목에 키워드 하이라이트 → 칩 바꾸고 [이 키워드로 다시 만들기]')에서 한다. 이 Task 에서 운영 API 를 부르지 않는다.

- [ ] **Step 1: 구현한다**

① `frontend/components/work/ConceptChips.vue` — 파일 전체를 다음으로 갈음한다(Task R1 이 바꾼 보이는 글 '키워드' 를 그대로 품는다. 칩 [×] 빼기는 토글 칩으로 바뀐다):

```vue
<!-- frontend/components/work/ConceptChips.vue -->
<template>
  <section class="wk-concepts" aria-labelledby="wk-concepts-title" :aria-busy="status === 'making'">
    <div class="wk-concepts__head">
      <h3 id="wk-concepts-title" class="wk-concepts__title">키워드</h3>
      <p v-if="note" class="rs-muted" aria-live="polite">{{ note }}</p>
    </div>
    <p v-if="editable && chips.length" id="wk-concepts-help" class="rs-muted">
      카드 제목에 넣을 키워드를 고르세요 — 고른 키워드가 하나 이상 들어간 제목으로 카드를 만듭니다.
    </p>

    <ul v-if="chips.length" class="wk-concepts__list" aria-label="키워드 후보">
      <li v-for="chip in chips" :key="chip.text">
        <button
          type="button"
          class="wk-kwchip"
          :aria-pressed="chip.pressed"
          :aria-describedby="editable ? 'wk-concepts-help' : undefined"
          :disabled="!editable || busy || (!chip.pressed && full)"
          @click="toggle(chip.text)"
        >
          <span>{{ chip.text }}</span>
          <span v-if="chip.badge" class="wk-kwchip__badge">{{ chip.badge }}</span>
        </button>
      </li>
    </ul>

    <div v-if="editable" class="wk-concepts__edit">
      <input
        v-model="input"
        class="wk-edit__input wk-concepts__input"
        type="text"
        :maxlength="CONCEPT_LEN_MAX"
        :placeholder="full ? `키워드는 ${CONCEPTS_MAX}개까지 고릅니다` : '후보에 없는 키워드 — Enter 로 더합니다'"
        aria-label="키워드 직접 더하기"
        :disabled="busy || full"
        @keydown.enter="onEnter"
      />
      <button
        type="button"
        class="rs-btn rs-btn--small rs-btn--ghost"
        :disabled="busy || full || !input.trim()"
        @click="add"
      >
        더하기
      </button>
      <button
        type="button"
        class="rs-btn rs-btn--small rs-btn--ghost"
        :disabled="busy || !dirty || !draft.length"
        @click="save"
      >
        키워드만 저장
      </button>
      <button v-if="dirty" type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="reset">
        되돌리기
      </button>
    </div>
    <div v-if="editable && (dirty || stale)" class="wk-concepts__regen">
      <button
        type="button"
        class="rs-btn rs-btn--small"
        :disabled="busy || problem !== null"
        :aria-describedby="problem ? 'wk-concepts-problem' : undefined"
        @click="regenerate"
      >
        이 키워드로 다시 만들기
      </button>
      <p v-if="problem" id="wk-concepts-problem" class="rs-muted">{{ problem }}</p>
    </div>
    <div v-if="retryable" class="rs-card__actions">
      <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="retry">다시</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { KeywordCandidate, WorkGeneration } from "~/types/work";
import {
  CONCEPTS_MAX,
  CONCEPT_LEN_MAX,
  addConcept,
  conceptsNote,
  conceptsRetryable,
  conceptsStatus,
  keywordChips,
  regenerateProblem,
  toggleKeyword,
} from "~/utils/topicDeck";

// 주제 단계 맨 위 키워드 칩(06e D23 — 06b 의 핵심 개념 칩을 후보 토글 칩으로). 후보(최신 키워드 생성)를 누르면 고르고
// 다시 누르면 뺀다. 후보에 없는 말은 직접 더한다(배지 '직접'). 고친 칩은 emit 만 하고 저장(PATCH work)·다시 만들기
// (POST topics/regenerate)는 TopicsStep 이 한다. [이 키워드로 다시 만들기] 는 고른 것이 저장된 것과 다르거나, 지금
// 키워드와 다른 키워드로 만든 AI 카드가 있을 때(stale) 보인다 — 둘 미만이면 누를 수 없고 까닭을 적는다
const props = defineProps<{
  concepts: string[];
  candidates: KeywordCandidate[] | null;
  generation: WorkGeneration | null;
  readOnly: boolean;
  busy: boolean;
  stale: boolean;
}>();
const emit = defineEmits<{ save: [concepts: string[]]; regenerate: [concepts: string[]]; retry: [genId: number] }>();

const draft = ref<string[]>([...props.concepts]);
const input = ref("");

const status = computed(() => conceptsStatus(props.concepts, props.generation));
const note = computed(() => conceptsNote(props.concepts, props.generation));
// 생성이 열려 있으면 서버 PATCH 가 409(만드는 중) — 그동안은 칩을 고치지 않는다
const editable = computed(() => !props.readOnly && status.value !== "making");
const retryable = computed(() => !props.readOnly && conceptsRetryable(props.concepts, props.generation));
const chips = computed(() => keywordChips(props.candidates, draft.value));
const full = computed(() => draft.value.length >= CONCEPTS_MAX);
const dirty = computed(() => !sameList(draft.value, props.concepts));
const problem = computed(() => regenerateProblem(draft.value));

function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((c, i) => c === b[i]);
}

// 저장했거나 생성이 칩을 채우면 새 목록을 받는다 — 고치던 중(저장 전)이면 사용자가 고른 칩을 덮지 않는다
watch(
  () => props.concepts,
  (next, before) => {
    if (sameList(draft.value, before ?? [])) draft.value = [...next];
  },
);

function toggle(text: string): void {
  draft.value = toggleKeyword(draft.value, text);
}

function add(): void {
  const next = addConcept(draft.value, input.value);
  if (next === draft.value) return;
  draft.value = next;
  input.value = "";
}

// 한글 조합 중의 Enter 는 글자를 확정하는 키다 — 그때 더하면 조합 중인 글자가 빠진 채 들어간다
function onEnter(e: KeyboardEvent): void {
  if (e.isComposing) return;
  e.preventDefault();
  add();
}

function reset(): void {
  draft.value = [...props.concepts];
  input.value = "";
}

function save(): void {
  if (!dirty.value || !draft.value.length) return;
  emit("save", [...draft.value]);
}

function regenerate(): void {
  if (problem.value) return;
  emit("regenerate", [...draft.value]);
}

function retry(): void {
  if (props.generation) emit("retry", props.generation.id);
}
</script>
```

② `frontend/components/work/TopicCard.vue` 템플릿 — 제목 하이라이트(dev `da80f23` `:32`)·키워드 경고·'키워드가 바뀌었습니다'·다시 만드는 중 줄. old:

```vue
      <h3 :id="titleId" class="wk-topic__title">{{ card.title }}</h3>
      <p class="wk-topic__question">{{ card.question }}</p>
```

new:

```vue
      <!-- 고른 키워드가 든 자리는 <mark> — 서버 제목 검사와 같은 일치 규칙(keywordSpans, 06e D23) -->
      <h3 :id="titleId" class="wk-topic__title">
        <template v-for="(part, i) in titleParts" :key="i">
          <mark v-if="part.mark" class="wk-kw">{{ part.text }}</mark>
          <template v-else>{{ part.text }}</template>
        </template>
      </h3>
      <p v-if="kwWarning" class="wk-topic__kwwarn">{{ kwWarning }}</p>
      <p class="wk-topic__question">{{ card.question }}</p>
      <p v-if="kwChanged" class="wk-topic__kwchanged">키워드가 바뀌었습니다</p>
      <p v-if="remakingNote" class="wk-topic__note">{{ remakingNote }}</p>
```

③ 같은 파일 script import. old:

```vue
import type { Figure, PaperMeta, TopicItem, TopicPatch } from "~/types/work";
```

new:

```vue
import type { Figure, PaperMeta, TopicItem, TopicPatch, WorkGeneration } from "~/types/work";
```

④ 같은 파일 topicDeck import. old:

```vue
  cardNumbersLine,
  cardStatus,
  evidenceChips,
  seedLine,
  topicProblem,
} from "~/utils/topicDeck";
```

new:

```vue
  cardNumbersLine,
  cardRemakingNote,
  cardStatus,
  evidenceChips,
  keywordSpans,
  keywordWarning,
  keywordsChanged,
  seedLine,
  topicProblem,
} from "~/utils/topicDeck";
```

⑤ 같은 파일 props 와 상태 — 지금 고른 키워드·키워드 생성(빈 씨앗 자리의 waiting·blocked). old:

```vue
const props = defineProps<{
  item: TopicItem;
  papers: Record<string, PaperMeta>;
  picked: boolean;
  readOnly: boolean;
  busy: boolean;
}>();
const emit = defineEmits<{ pick: []; edit: [body: TopicPatch]; retry: [genId: number]; arrived: [el: HTMLElement] }>();

const status = computed(() => cardStatus(props.item));
```

new:

```vue
// concepts·conceptsGen — 지금 고른 키워드와 그 생성(06e D23). 빈 씨앗 자리는 키워드가 정해지기를 기다린다(cardStatus)
const props = defineProps<{
  item: TopicItem;
  papers: Record<string, PaperMeta>;
  picked: boolean;
  readOnly: boolean;
  busy: boolean;
  concepts: string[];
  conceptsGen: WorkGeneration | null;
}>();
const emit = defineEmits<{ pick: []; edit: [body: TopicPatch]; retry: [genId: number]; arrived: [el: HTMLElement] }>();

const status = computed(() => cardStatus(props.item, props.conceptsGen));
```

⑥ 같은 파일 — `numbersLine` 계산 다음에 키워드 셋. old:

```vue
const numbersLine = computed(() => (card.value ? cardNumbersLine(card.value) : null));
```

new:

```vue
const numbersLine = computed(() => (card.value ? cardNumbersLine(card.value) : null));
// 제목 속 고른 키워드(카드를 만들 때 넘긴 키워드), 하나도 못 넣은 카드의 경고, 지금 고른 키워드와 다른 키워드로 만든 카드.
// '바뀌었습니다'는 다시 만들 대상(고르지 않은·고치지 않은 AI 카드)에만 단다 — 고른 카드는 다시 만들지 않는다(06e 정함 16)
const titleParts = computed(() => (card.value ? keywordSpans(card.value.title, card.value.keywords ?? []) : []));
const kwWarning = computed(() => (card.value ? keywordWarning(card.value) : null));
// [이 키워드로 다시 만들기] 가 넣은 새 카드를 기다리는 중 — 새 결과가 반영될 때까지 지금 카드를 그대로 보이고 [고르기]
// (canPick)·[직접 고치기](서버 409 CARD_BUSY)는 막는다. 그동안은 '바뀌었습니다'를 달지 않는다(06e 정함 16)
const remakingNote = computed(() => cardRemakingNote(props.item));
const kwChanged = computed(
  () =>
    card.value !== null &&
    remakingNote.value === null &&
    !props.picked &&
    props.item.origin !== "user" &&
    !card.value.edited &&
    keywordsChanged(card.value, props.concepts),
);
```

⑦ `frontend/components/work/TopicDeck.vue` 템플릿 — 카드에 지금 키워드·키워드 생성, [다른 방향]은 키워드를 고르는 동안 막는다(서버도 409 `KEYWORDS_BUSY` — Task K4). old:

```vue
        :picked="item.id === topics.picked_id"
        :read-only="readOnly"
        :busy="busy"
```

new:

```vue
        :picked="item.id === topics.picked_id"
        :read-only="readOnly"
        :busy="busy"
        :concepts="concepts"
        :concepts-gen="conceptsGen"
```

⑧ 같은 파일 [다른 방향] 버튼. old:

```vue
        :disabled="readOnly || busy || topics.seeds_left <= 0"
        @click="emit('more')"
```

new:

```vue
        :disabled="readOnly || busy || topics.seeds_left <= 0 || keywordsBusy"
        @click="emit('more')"
```

⑨ 같은 파일 script. old:

```vue
import type { TopicCreate, TopicPatch, TopicsView } from "~/types/work";
import { TOPIC_QUESTION_MAX, TOPIC_TITLE_MAX, deckOrder, moreLine, topicProblem } from "~/utils/topicDeck";

// 주제 카드 덱(spec §4 S3) — 카드 순서는 deckOrder, [다른 방향]·[직접 쓰기] 는 의도만 emit 한다.
// 카드 도착(arrived)은 그대로 올린다 — 화면 밖인지 보고 알약을 띄우는 것은 TopicsStep 이다
const props = defineProps<{ topics: TopicsView; readOnly: boolean; busy: boolean }>();
```

new:

```vue
import type { TopicCreate, TopicPatch, TopicsView, WorkGeneration } from "~/types/work";
import {
  TOPIC_QUESTION_MAX,
  TOPIC_TITLE_MAX,
  conceptsStatus,
  deckOrder,
  moreLine,
  topicProblem,
} from "~/utils/topicDeck";

// 주제 카드 덱(spec §4 S3) — 카드 순서는 deckOrder, [다른 방향]·[직접 쓰기] 는 의도만 emit 한다.
// 카드 도착(arrived)은 그대로 올린다 — 화면 밖인지 보고 알약을 띄우는 것은 TopicsStep 이다.
// concepts·conceptsGen 은 카드로 내려 준다(제목 하이라이트·'키워드가 바뀌었습니다'·빈 씨앗 자리 — 06e D23)
const props = defineProps<{
  topics: TopicsView;
  concepts: string[];
  conceptsGen: WorkGeneration | null;
  readOnly: boolean;
  busy: boolean;
}>();
```

⑩ 같은 파일 — `items` 계산 다음. old:

```vue
const items = computed(() => deckOrder(props.topics.items));
```

new:

```vue
const items = computed(() => deckOrder(props.topics.items));
// 키워드를 고르는 중에는 [다른 방향] 을 막는다 — 끝나기 전의 키워드는 비어 있다(서버 409, 06e 정함 29)
const keywordsBusy = computed(() => conceptsStatus(props.concepts, props.conceptsGen) === "making");
```

⑪ `frontend/components/work/TopicsStep.vue` 템플릿의 ConceptChips(Task R1 이 고친 제목·설명 줄 :6·:8 과 겹치지 않는 자리). old:

```vue
    <ConceptChips
      v-if="view"
      :concepts="view.concepts"
      :generation="conceptGen"
      :read-only="readOnly"
      :busy="busy"
      @save="saveConcepts"
      @retry="retryConcepts"
    />
```

new:

```vue
    <ConceptChips
      v-if="view"
      :concepts="view.concepts"
      :candidates="view.concept_candidates ?? null"
      :generation="conceptGen"
      :read-only="readOnly"
      :busy="busy"
      :stale="cardsStale"
      @save="saveConcepts"
      @regenerate="regenerate"
      @retry="retryConcepts"
    />
```

⑫ 같은 파일 템플릿의 TopicDeck. old:

```vue
      <TopicDeck
        :topics="topics"
        :read-only="readOnly"
```

new:

```vue
      <TopicDeck
        :topics="topics"
        :concepts="view?.concepts ?? []"
        :concepts-gen="conceptGen"
        :read-only="readOnly"
```

⑬ 같은 파일 script import. old:

```vue
import { deckQueueLine, liveTopics } from "~/utils/topicDeck";
```

new:

```vue
import { aiCardsStale, deckQueueLine, liveTopics } from "~/utils/topicDeck";
```

⑭ 같은 파일 — `conceptGen` 계산 다음에 `cardsStale`. old:

```vue
const conceptGen = computed(() => latestGeneration(state.value, "concepts"));
```

new:

```vue
const conceptGen = computed(() => latestGeneration(state.value, "concepts"));
// 다시 만들 AI 자리가 있다(지금 키워드와 다른 키워드로 만든 AI 카드, 키워드 생성이 실패해 카드가 없는 씨앗 자리) —
// 칩을 고치지 않아도 [이 키워드로 다시 만들기] 를 보인다
const cardsStale = computed(() =>
  topics.value && view.value ? aiCardsStale(topics.value, view.value.concepts, conceptGen.value) : false,
);
```

⑮ 같은 파일 — `retryCard` 앞에 `regenerate`(Task R1 이 고친 `saveConcepts`·`retryConcepts` 의 오류 문구 줄과 겹치지 않는 자리). old:

```vue
function retryCard(genId: number): void {
```

new:

```vue
// [이 키워드로 다시 만들기] — 고른 칩이 저장된 것과 다르면 먼저 저장(PATCH work)하고 그 키워드로 AI 카드를 다시 만든다
// (POST topics/regenerate). 409(키워드가 둘 미만·키워드를 고르는 중·다시 만들 카드 없음)면 act 가 주제·연구를 다시 읽는다
function regenerate(concepts: string[]): void {
  void act(
    async () => {
      const saved = view.value?.concepts ?? [];
      if (concepts.length !== saved.length || concepts.some((c, i) => c !== saved[i])) {
        props.work.setWork(await api.patchWork(props.jobId, { concepts }));
      }
      await api.regenerateTopics(props.jobId);
    },
    ["topics", "work"],
    "카드를 다시 만들지 못했습니다",
  );
}

function retryCard(genId: number): void {
```

⑯ `frontend/assets/css/work.css` — 이어 붙이는 자리 표시 줄 바로 위에 한 묶음(앞 Task 들이 표시 줄 위에 더한 묶음 뒤 — 표시 줄을 old 로 잡는다). old:

```css
/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

new:

```css
/* ── 키워드 칩·제목 하이라이트(06e Task K8 — 제목 고르기 D23) ── */
/* 후보 토글 칩 — 고른 칩(aria-pressed)은 실선·주색, 고르지 않은 칩은 점선·회색. 배지는 출처·편수(AI 후보·논문 n편·직접) */
.wk-kwchip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.55rem;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--skx-gray-1);
  background: var(--skx-white);
  border: 1px dashed var(--skx-line);
  border-radius: var(--skx-radius-pill);
  cursor: pointer;
}
.wk-kwchip[aria-pressed="true"] {
  color: var(--skx-primary);
  background: var(--skx-border-c1);
  border-style: solid;
  border-color: var(--skx-border-c2);
}
.wk-kwchip:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.wk-kwchip:focus-visible {
  outline: 2px solid var(--skx-primary);
  outline-offset: 2px;
}
.wk-kwchip__badge {
  font-size: 0.5rem;
  font-weight: 400;
  color: var(--skx-gray-1);
}
.wk-concepts__regen {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}
/* 카드 제목 속 고른 키워드 */
.wk-kw {
  padding: 0 0.1rem;
  color: inherit;
  background: var(--skx-border-c1);
  border-radius: var(--skx-radius-sm);
}
.wk-topic__kwwarn {
  margin: 0;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-ink-2);
}
.wk-topic__kwchanged {
  align-self: flex-start;
  margin: 0;
  padding: 0.05rem 0.45rem;
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--skx-gray-1);
  border: 1px dashed var(--skx-line);
  border-radius: var(--skx-radius-pill);
}
/* 키워드 생성이 실패해 카드가 아직 없는 씨앗 자리 — 근거 부족·실패 슬롯과 같은 점선 */
.wk-topic--blocked {
  border-style: dashed;
  border-color: var(--skx-line);
}

/* ── 이어 붙이는 자리: 화면 task 는 이 줄 바로 위에 한 묶음씩 더한다(이 줄은 지우지 않는다) ── */
```

⑰ `frontend/components/work/TopicCard.vue` 템플릿 [직접 고치기](dev `da80f23` `:81-89`) — 다시 만드는 중에는 막는다(서버 `edit_topic` 이 카드 생성이 열려 있으면 409 `CARD_BUSY`). old:

```vue
        :disabled="readOnly || busy"
        data-edit-open
```

new:

```vue
        :disabled="readOnly || busy || remakingNote !== null"
        data-edit-open
```

- [ ] **Step 2: 타입·빌드·단위 테스트를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`

Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`

Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep -c "WARN"`

Expected: Task 앞과 같은 수(기준선 57 — 샌드박스 실측 57, 새 'Duplicated imports' 없음)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run 2>&1 | tail -4`

Expected: 실패 0, `Tests` = Task 앞 + 0

- [ ] **Step 3: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/components/work/ConceptChips.vue frontend/components/work/TopicCard.vue frontend/components/work/TopicDeck.vue frontend/components/work/TopicsStep.vue frontend/assets/css/work.css && git status --short && git commit -m "[Feat] round06e 프론트 — 제목 고르기 화면(D23, spec §12-4 칩 UI·하이라이트). 키워드 칩을 후보 토글 칩(aria-pressed — 출처·편수 배지 AI 후보·논문 n편·직접, 상한 5)으로 다시 짜고 직접 더하기는 남긴다. 고른 것이 저장과 다르거나 지금 키워드와 다른 키워드로 만든 AI 카드가 있으면 [이 키워드로 다시 만들기](2개 미만이면 막고 까닭을 잇는다 — 저장이 다르면 PATCH work 뒤 POST topics/regenerate). 카드 제목의 고른 키워드를 <mark> 로 감싸고, 세 번 다 놓친 카드엔 '제목에 「…」 없음', 키워드가 바뀐 AI 카드엔 '키워드가 바뀌었습니다'(고른·고친·직접 쓴 카드엔 없다). 빈 씨앗 자리는 키워드가 정해질 때까지 기다리는 중, 키워드 생성이 실패하면 '키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다'(그 자리도 [이 키워드로 다시 만들기]를 보이는 까닭이다). 다시 만드는 중인 카드는 '새 키워드로 다시 만드는 중입니다'를 달고 [고르기]·[직접 고치기]를 막는다. 키워드를 고르는 동안 [다른 방향]은 막는다"
```

---

### Task K9: 제목 키워드 검사·세 번 놓친 카드 — 06c `terms.contains`

**조건(이 Task 머리 — 그대로 지킨다):** **06c 가 dev 에 머지된 뒤에만 한다.** Step 1 에서 머지를 확인하지 못하면 이 Task 를 미루고 파트 H(Task H1·Task H2)를 먼저 한다. 06c 의 `contains` 와 같은 함수를 06e 에 따로 두지 않는다(06c 뼈대 §4 — 중복 구현 금지).

**왜:** spec §12-4 '검사'(`_bind` 가 `card.keywords`·`card.checks.missing_keywords`, 일치 = 06c `contains`, 하나도 없으면 재시도 사다리 `generate.py:67-102`), §12-11 '키워드를 세 번 다 놓친 카드'(정함 17). 지금 규칙으로는 세 번 다 놓친 카드가 빈 결과('근거 부족' — 잘못된 안내)가 된다. 권고대로 실행기에 무른 검사(`Executor.soft_check`)를 더해 `run_generation` 이 '무른 검사만 넘은 마지막 출력'을 보관하고, 끝내 엄격한 검사를 못 넘으면 그 출력을 그 모델 이름으로 돌려준다 — 주제 카드의 무른 검사는 06b 검사(근거 2편 이상), 엄격한 검사는 그에 더해 고른 키워드가 제목에 하나 이상. 화면은 `missing_keywords` 가 `keywords` 전부일 때 '제목에 「…」 없음' 경고를 단다(Task K7·Task K8). 서버 일치와 화면 하이라이트가 같은 참·거짓인지 06c 의 공용 고정 예제(`term_checks.json`)로 묶는다.

**Files:**
- Modify: `app/services/research_work/generate.py` (docstring 12-13 뒤, `Executor` 53 뒤, `run_generation` 69-102 — `run_stream_generation` 은 그대로)
- Modify: `app/services/research_work/topic_card.py` (Task K4·Task K5·Task K6 뒤 기준 — 머리 docstring 의 Task K4 키워드 줄, import 22, `_clean` 뒤에 `keyword_misses`, `_bind`·`_check`·`EXECUTOR`)
- Modify: `app/models/research_work.py` (Task K4 뒤 기준 — 머리 주석 Card checks — 주석만)
- Test: `app/tests/test_research_work_generate.py` (파일 끝)
- Test: `app/tests/test_research_work_executor.py` (`TestExecutorFields.test_new_fields_follow_the_06a_five_with_defaults` 76-81)
- Test: `app/tests/test_research_work_topic_card.py` (Task K4·Task K5·Task K6 뒤 기준 — import, `TestBind.test_card_shape`, `TestCheck` 앞·안, `TestThroughTheCommonRule` 끝)
- Test: `frontend/tests/unit/topicDeck.test.ts` (Task K7 뒤 기준 — import, 파일 끝)

**알아 둘 것:**
- **선행 조건(Step 1):** 06c 머지 커밋을 dev 에서 찾고 → 06e 브랜치에 dev 를 받는다(06c 는 06e 파일을 고치지 않는다 — §12-5, 충돌이 나면 멈추고 사용자와 정한다) → `contains` 시그니처가 `def contains(text: str, word: str) -> bool:` 인지, `frontend/tests/fixtures/term_checks.json` 이 있는지 본다(이름·인자 순서가 다르면 호출부 `keyword_misses` 한 곳만 맞추고 완료노트 '알아 둘 것'에 적는다) → 백엔드·vitest 전체를 다시 돌려 06c 가 더한 수를 이 Task 의 'Task 앞' 으로 적는다.
- **무른 검사:** `Executor.soft_check: Callable[[dict], bool] | None = None` — 선택 필드를 **맨 끝**(`is_empty` 다음)에 둔다(frozen dataclass — 06a 의 다섯 위치 인자 실행기가 그대로 돈다). `run_generation` 은 검사 미달 출력이 `soft_check` 를 넘으면 `(output, model)` 을 덮어쓰며 보관하고(마지막 것), 사다리가 끝나면 보관한 것이 있으면 `GenerationResult(output, model, attempts)`, 없으면 지금처럼 `empty`. attempts 의 그 시도는 `check` 로 남는다(공개 부록 모양 그대로). 엄격한 검사를 넘은 답이 나오면 보관한 것은 버리고 그 답이다. 스트리밍 경로(`run_stream_generation`)는 쓰지 않는다 — 절·문단 실행기는 `soft_check` 를 두지 않는다.
- **카드:** `_bind` 가 `card.keywords`(input 그대로 — 문자열만)와 `card.checks.missing_keywords = keyword_misses(title, keywords)` 를 싣는다. 검사에 쓰는 제목은 다듬은 뒤(단정 표현 바꿈·`TOPIC_TITLE_MAX` 자르기)의 제목 — 화면이 보이는 글과 같다. `_check`(엄격) = `_soft_check`(근거 2편) and (키워드 없음 or 놓친 수 < 키워드 수). 키워드 없이 넣은 카드(취소·빈 결과·06e 전 행)는 06b 검사 그대로다. `is_empty` 는 그대로(카드가 None 일 때만) — 보관한 카드는 빈 결과가 아니라 [다시] 대상이 아니다(경고를 단 채 보이고, 사용자는 [직접 고치기]나 [이 키워드로 다시 만들기]를 쓴다).
- **공용 고정 예제(1-9):** 백엔드 `TestKeywordMatchFixture` 는 `keyword_match.json`(Task K7) 사례마다 `contains(text, word) == bool(marked)` 와 `keyword_misses` 를 본다 — 06c `term_checks.json` 의 `contains` 칸은 06c 의 두 테스트가 이미 지킨다. 프론트는 `term_checks.json` 의 `contains` 칸 전부에서 `keywordSpans(text, [word]).some((p) => p.mark) === expected` 를 본다(빈 word 는 표시 없음 = false). 이 프론트 테스트는 **처음부터 통과**한다(Task K7 의 `keywordSpans` 가 같은 규칙 — 샌드박스에서 06c 계획의 공용 고정 예제 `term_checks.json` 의 contains 9 사례로 실측). 어긋나면 `keywordSpans` 를 고친다 — `term_checks.json` 은 06c 가 지키는 정본이라 고치지 않는다. pytest 경로는 `Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "keyword_match.json"`(`marker_checks.json` 선례 — `test_research_work_markers.py:20-22`).
- `test_research_topics_api.py::TestEndToEnd` 는 Task K5 가 카드 제목에 고른 키워드를 넣게 바꿔 두어 이 Task 뒤에도 첫 답에 통과한다(그대로).
- topicDeck.test.ts 의 수는 Task H1 이 먼저 끝났는지에 따라 다르다(Task H1 +2) — 'Task 앞 + 9' 로 읽는다.

- [ ] **Step 1: 선행 조건 — 06c 가 dev 에 머지됐는지 보고 dev 를 받는다**

Run: `git -C C:/Users/LANDSOFT/mygit/NL_library_AI log dev --oneline --merges | grep -c "feat/round06c-query-broadening"`

Expected: `1` 이상(06c 기능 브랜치의 머지 커밋 `… Merge feat/round06c-query-broadening into dev — …` — 계획 머리 Task 0·Task Z4 와 같은 판정이고, 06c 의 문서·기록 브랜치 머지는 세지 않는다). **`0` 이면 여기서 멈추고** 이 Task 를 미룬다(Task H1·H2 를 먼저) — 06c 코드 없이 나아가면 `from services.research.terms import contains` 에서 깨진다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git merge --no-ff dev -m "Merge dev into feat/round06e-assistant-auto-report — 06c 의 terms.contains·공용 고정 예제 term_checks.json 받기(제목 키워드 검사 선행)"`

Expected: 충돌 없이 머지 커밋 하나(메시지는 이 저장소의 머지 커밋 꼴 `Merge X into Y — 한국어 설명`). 충돌이 나면 `git merge --abort` 후 사용자와 정한다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -n "^def contains" app/services/research/terms.py && ls frontend/tests/fixtures/term_checks.json`

Expected: `NNN:def contains(text: str, word: str) -> bool:` 한 줄과 `frontend/tests/fixtures/term_checks.json`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors 2>&1 | tail -1`

Expected: 실패 5·오류 1 이 기준선과 같은 세 파일이고 통과 수는 06c 가 더한 만큼 늘었다 — 이 값을 이 Task 의 백엔드 'Task 앞' 으로 적는다

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run 2>&1 | tail -4`

Expected: 실패 0 — 이 값을 이 Task 의 vitest 'Task 앞' 으로 적는다

- [ ] **Step 2: 실패하는 테스트를 쓴다**

① `app/tests/test_research_work_generate.py` 끝에 붙인다:

```python
# ── 무른 검사(soft_check — 06e 정함 17) ──────────────────────────────────


def _soft(n: int) -> str:
    """엄격한 검사(ok)는 못 넘고 무른 검사(soft)만 넘는 답 — n 으로 어느 답인지 가른다."""
    return json.dumps({"ok": False, "soft": True, "n": n})


def _soft_executor(*, soft: bool = True) -> Executor:
    """엄격한 검사와 무른 검사를 함께 가진 실행기 — 주제 카드(근거 2편 / 근거 2편 + 제목 키워드)와 같은 모양."""
    return Executor(
        kind="facet", build=lambda inp: (MESSAGES, dict(PARAMS)), parse=_parse,
        check=lambda out: out.get("ok") is True,
        empty=lambda inp: {"empty": True},
        soft_check=(lambda out: out.get("soft") is True) if soft else None,
    )


def _run_soft(chat: _ScriptedChat, *, soft: bool = True) -> GenerationResult:
    return asyncio.run(run_generation(_soft_executor(soft=soft), {"q": "질문"}, chat_fn=chat))


class TestSoftCheck:
    def test_a_strict_pass_wins_over_a_kept_soft_pass(self, cfg):
        chat = _ScriptedChat({"qwen-test": [_soft(1), OK]})

        result = _run_soft(chat)

        assert result.output == {"ok": True} and result.model == "qwen-test"
        assert _outcomes(result) == ["check", "ok"]

    def test_three_soft_passes_return_the_last_one_with_its_model(self, cfg):
        # 세 번 다 엄격한 검사를 놓쳤다 — 빈 결과 대신 무른 검사를 넘은 마지막 답을 그 모델 이름으로 낸다
        chat = _ScriptedChat({"qwen-test": [_soft(1), _soft(2)], "gemma-test": [_soft(3)]})

        result = _run_soft(chat)

        assert chat.models == ["qwen-test", "qwen-test", "gemma-test"]
        assert result.output == {"ok": False, "soft": True, "n": 3} and result.model == "gemma-test"

    def test_without_soft_check_the_empty_result_is_unchanged(self, cfg):
        chat = _ScriptedChat({"qwen-test": [_soft(1), _soft(2)], "gemma-test": [_soft(3)]})

        result = _run_soft(chat, soft=False)

        assert result.output == {"empty": True} and result.model is None

    def test_attempts_record_check_for_soft_passes(self, cfg):
        # 무른 검사만 넘은 시도도 공개 부록(attempts)에는 check 다 — 뒤 시도가 해석에 실패해도 보관한 답을 낸다
        chat = _ScriptedChat({"qwen-test": [_soft(1), NOT_JSON], "gemma-test": [THIN]})

        result = _run_soft(chat)

        assert _outcomes(result) == ["check", "parse", "check"]
        assert result.output == {"ok": False, "soft": True, "n": 1} and result.model == "qwen-test"
```

② `app/tests/test_research_work_executor.py` `TestExecutorFields.test_new_fields_follow_the_06a_five_with_defaults` — 06e 의 선택 필드 `soft_check`(기본 None). old:

```python
        assert [f.name for f in dataclasses.fields(Executor)] == [
            "kind", "build", "parse", "check", "empty", "bind", "stream", "apply", "is_empty"]
        ex = _plain()
        assert (ex.bind, ex.stream, ex.apply, ex.is_empty) == (None, False, None, None)
```

new:

```python
        assert [f.name for f in dataclasses.fields(Executor)] == [
            "kind", "build", "parse", "check", "empty", "bind", "stream", "apply", "is_empty", "soft_check"]
        ex = _plain()
        assert (ex.bind, ex.stream, ex.apply, ex.is_empty, ex.soft_check) == (None, False, None, None, None)
```

③ `app/tests/test_research_work_topic_card.py` 머리 import — 고정 예제 경로·06c 일치 함수·제목 검사. old:

```python
import asyncio
import json
import re
```

new:

```python
import asyncio
import json
import re
from pathlib import Path
```

④ 같은 파일 import 의 `services.prompts` 줄 다음. old:

```python
from services.prompts import get_prompt
```

new:

```python
from services.prompts import get_prompt
from services.research.terms import contains
```

⑤ 같은 파일 topic_card import. old:

```python
from services.research_work.topic_card import (
    EXECUTOR, FIG_ADOPTED, FIG_CORPUS, FIG_LATEST, PROMPT, card_figures, evidence_ids, figure_sentence,
)
```

new:

```python
from services.research_work.topic_card import (
    EXECUTOR, FIG_ADOPTED, FIG_CORPUS, FIG_LATEST, PROMPT, card_figures, evidence_ids, figure_sentence,
    keyword_misses,
)
```

⑥ 같은 파일 `TestBind.test_card_shape` — 카드에 넘긴 키워드와 제목에 없는 키워드(이 INPUT 은 06e 전 행 모양이라 둘 다 빈 목록). old:

```python
            "latest_year": 2015,
            "edited": False,
            "checks": {"numbers": [], "softened": 0, "recovered": 0},
            "gen_id": None,
        }}
```

new:

```python
            "latest_year": 2015,
            "edited": False,
            "keywords": [],
            "checks": {"numbers": [], "softened": 0, "recovered": 0, "missing_keywords": []},
            "gen_id": None,
        }}
```

⑦ 같은 파일 — `TestCheck` 앞에 공용 고정 예제(백엔드 쪽), `TestCheck` 에 두 테스트. old:

```python
class TestCheck:
    def test_needs_two_evidence_chips(self):
```

new:

```python
# 06e 화면 keywordSpans 가 감싸는 자리(Task K7) — 일치(참·거짓)의 정본은 06c 의 term_checks.json 이고 06c 테스트가 지킨다.
# 여기서는 하이라이트 사례도 서버 제목 검사(06c contains)와 같은 참·거짓인지만 본다
KEYWORD_MATCH = json.loads(
    (Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "keyword_match.json")
    .read_text(encoding="utf-8"))


class TestKeywordMatchFixture:
    @pytest.mark.parametrize("case", KEYWORD_MATCH, ids=[c["note"] for c in KEYWORD_MATCH])
    def test_contains_agrees_with_the_highlight_cases(self, case):
        assert contains(case["text"], case["word"]) is bool(case["marked"])
        assert keyword_misses(case["text"], [case["word"]]) == ([] if case["marked"] else [case["word"]])


class TestCheck:
    def test_a_title_without_any_keyword_fails_the_strict_check(self):
        # 06e D23 — 고른 키워드가 제목에 하나도 없으면 엄격한 검사 미달(공통 규칙이 다시 부른다). 하나라도 있으면 통과
        inp = {**INPUT, "keywords": ["농촌 노인", "지지망 유형"]}
        hit = _bound(GOOD, inp)                      # 제목 '독거노인의 지지망 유형과 우울' 에 '지지망 유형'이 있다
        assert hit["card"]["keywords"] == ["농촌 노인", "지지망 유형"]
        assert hit["card"]["checks"]["missing_keywords"] == ["농촌 노인"]
        assert EXECUTOR.check(hit) is True
        miss = _bound({**GOOD, "title": "독거노인의 관계망과 우울"}, inp)
        assert miss["card"]["checks"]["missing_keywords"] == ["농촌 노인", "지지망 유형"]
        assert EXECUTOR.check(miss) is False
        # 무른 검사(06b 의 근거 2편)는 넘는다 — 세 번 다 놓치면 이 카드를 보관한다(06e 정함 17)
        assert EXECUTOR.soft_check(miss) is True
        assert EXECUTOR.soft_check(_bound({**GOOD, "evidence": ["E1"]}, inp)) is False

    def test_no_keywords_means_no_keyword_rule(self):
        # 키워드 없이 넣은 카드(취소·빈 결과)와 06e 전 행은 06b 검사 그대로다
        card = _bound({**GOOD, "title": "아무 낱말"}, {**INPUT, "keywords": []})
        assert card["card"]["checks"]["missing_keywords"] == [] and EXECUTOR.check(card) is True
        assert EXECUTOR.check(_bound({**GOOD, "title": "아무 낱말"})) is True

    def test_needs_two_evidence_chips(self):
```

⑧ 같은 파일 `TestThroughTheCommonRule` 끝에 한 테스트. old:

```python
        result, seen = _run({primary: [one, one], fallback: [one]})
        assert seen == [primary, primary, fallback]
        assert result.output == {"card": None} and result.model is None
        assert [a["outcome"] for a in result.attempts] == ["check", "check", "check"]
```

new:

```python
        result, seen = _run({primary: [one, one], fallback: [one]})
        assert seen == [primary, primary, fallback]
        assert result.output == {"card": None} and result.model is None
        assert [a["outcome"] for a in result.attempts] == ["check", "check", "check"]

    def test_three_misses_keep_the_last_card_with_its_warning(self, cfg):
        # 세 번 다 제목에 키워드를 못 넣었다 — 빈 결과('근거 부족' — 잘못된 안내) 대신 마지막 카드를 그 모델 이름으로
        # 보관하고, 화면은 card.checks.missing_keywords 로 '제목에 「…」 없음' 경고를 단다(06e 정함 17)
        inp = {**INPUT, "keywords": ["농촌 노인", "우울 선별"]}
        primary, fallback = _models()
        first = _reply({**GOOD, "title": "독거노인의 지지망과 우울"})
        last = _reply({**GOOD, "title": "독거노인 지지망 유형"})
        answers = {primary: [first, first], fallback: [last]}
        seen: list[str] = []

        async def fake_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            seen.append(model)
            return LLMResult(content=answers[model].pop(0), finish_reason="stop")

        result = asyncio.run(run_generation(EXECUTOR, inp, chat_fn=fake_chat))

        assert seen == [primary, primary, fallback]
        assert [a["outcome"] for a in result.attempts] == ["check", "check", "check"]
        assert result.model == fallback and EXECUTOR.is_empty(result.output) is False
        assert result.output["card"]["title"] == "독거노인 지지망 유형"
        assert result.output["card"]["checks"]["missing_keywords"] == ["농촌 노인", "우울 선별"]
```

⑨ `frontend/tests/unit/topicDeck.test.ts` 머리 — Task K7 이 더한 고정 예제 import 다음에 06c 의 고정 예제. old:

```ts
import keywordMatch from "../fixtures/keyword_match.json";
```

new:

```ts
import keywordMatch from "../fixtures/keyword_match.json";
import termChecks from "../fixtures/term_checks.json";
```

⑩ 같은 파일 끝에 붙인다(Task H1 이 먼저 끝났으면 Task H1 의 describe 뒤 — 서로 다른 describe 라 순서와 상관없다):

```ts
// 06c 의 공용 고정 예제 — 서버 terms.contains(제목 키워드 검사)와 화면 keywordSpans(하이라이트)가 같은 참·거짓이어야 한다.
// 어긋나면 keywordSpans 를 고친다 — term_checks.json 은 06c 가 지키는 정본이라 고치지 않는다(06e Task K9)
interface TermCase {
  text: string;
  word: string;
  expected: boolean;
  note: string;
}
const TERM_CASES: TermCase[] = termChecks.contains;

describe("keywordSpans 는 06c term_checks.json 의 contains 칸과 같은 참·거짓", () => {
  it.each(TERM_CASES)("$note", (c) => {
    expect(keywordSpans(c.text, [c.word]).some((p) => p.mark)).toBe(c.expected);
  });
});
```

- [ ] **Step 3: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_topic_card.py -q -p no:cacheprovider`

Expected: 수집 오류 — `ImportError: cannot import name 'keyword_misses' from 'services.research_work.topic_card'` · `Interrupted: 1 error during collection`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_generate.py tests/test_research_work_executor.py -q -p no:cacheprovider`

Expected: `5 failed, 31 passed, 2 warnings` — `TestSoftCheck` 넷(`Executor` 가 `soft_check` 를 받지 않는다 — TypeError)과 `TestExecutorFields::test_new_fields_follow_the_06a_five_with_defaults`(필드 목록)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/topicDeck.test.ts`

Expected: 실패 0 — 새 describe 의 9개(06c `term_checks.json` 의 contains 사례)가 처음부터 통과한다(`Tests` = Task 앞 + 9). 하나라도 떨어지면 Step 4 에서 `keywordSpans` 를 그 사례에 맞게 고친다

- [ ] **Step 4: 구현한다**

① `app/services/research_work/generate.py` 머리 docstring — bind 단락 다음. old:

```python
해석한 결과는 실행기의 bind(06b)가 있으면 검사 전에 입력으로 맞춘다 — 모델이 낸 근거 번호를 cnts_id 로
바꾸고 문단을 마커 검사하는 일처럼 입력이 있어야 하는 정리다. 끝내 못 얻은 빈 결과(empty)에는 하지 않는다.
```

new:

```python
해석한 결과는 실행기의 bind(06b)가 있으면 검사 전에 입력으로 맞춘다 — 모델이 낸 근거 번호를 cnts_id 로
바꾸고 문단을 마커 검사하는 일처럼 입력이 있어야 하는 정리다. 끝내 못 얻은 빈 결과(empty)에는 하지 않는다.

무른 검사(soft_check, 06e 정함 17 — 주제 카드 제목의 키워드): 엄격한 검사(check)는 못 넘었지만 soft_check 를 넘은
출력은 그 모델과 함께 마지막 것으로 보관한다. 사다리가 끝나도록 엄격한 검사를 넘은 답이 없으면 빈 결과 대신 그것을
돌려준다(attempts 에는 그 시도가 check 로 남는다). 스트리밍(run_stream_generation)은 쓰지 않는다.
```

② 같은 파일 `Executor` — `is_empty` 다음에 선택 필드. old:

```python
    is_empty: Callable[[dict], bool] | None = None     # done 인데 빈 결과인가 — 다시 부르기(retry)를 허용한다
```

new:

```python
    is_empty: Callable[[dict], bool] | None = None     # done 인데 빈 결과인가 — 다시 부르기(retry)를 허용한다
    # 06e 의 선택 필드 — check 를 못 넘어도 이것을 넘은 마지막 출력을 빈 결과 대신 낸다(정함 17)
    soft_check: Callable[[dict], bool] | None = None
```

③ 같은 파일 `run_generation` 머리. old:

```python
    content_failures = 0
    attempts: list[dict] = []
    for _ in range(MAX_CALLS):
        base_url, model = endpoint(route)
        try:
```

new:

```python
    content_failures = 0
    attempts: list[dict] = []
    soft: tuple[dict, str] | None = None     # 무른 검사만 넘은 마지막 출력과 그 모델(06e 정함 17)
    for _ in range(MAX_CALLS):
        base_url, model = endpoint(route)
        try:
```

④ 같은 함수 — 검사 미달 자리와 끝(`run_stream_generation` 은 그대로). old:

```python
        outcome = "parse" if output is None else "check"
        # 진단용 원문 앞부분과 끝난 이유(length 면 잘림)는 로그에만 남긴다 — attempts 는 공개 부록에 실린다
```

new:

```python
        outcome = "parse" if output is None else "check"
        if output is not None and executor.soft_check is not None and executor.soft_check(output):
            soft = (output, model)
        # 진단용 원문 앞부분과 끝난 이유(length 면 잘림)는 로그에만 남긴다 — attempts 는 공개 부록에 실린다
```

⑤ 같은 함수의 끝. old:

```python
        content_failures += 1
        if content_failures >= 2:
            route, switched = other(route), True
    return GenerationResult(output=executor.empty(input), model=None, attempts=attempts)


async def run_stream_generation(
```

new:

```python
        content_failures += 1
        if content_failures >= 2:
            route, switched = other(route), True
    if soft is not None:
        # 엄격한 검사를 끝내 못 넘었다 — 빈 결과 대신 무른 검사를 넘은 마지막 출력을 그 모델 이름으로 낸다
        return GenerationResult(output=soft[0], model=soft[1], attempts=attempts)
    return GenerationResult(output=executor.empty(input), model=None, attempts=attempts)


async def run_stream_generation(
```

⑥ `app/services/research_work/topic_card.py` 머리 docstring — Task K4 가 더한 키워드 줄에 검사를 잇는다. old:

```python
  - 키워드(06e D23): 고른 키워드(input.keywords)를 넘기면 프롬프트에 '제목에 하나 이상 글자 그대로' 규칙 한 줄이 붙는다.
    예시 제목·이전 제목은 주지 않는다(함정 15·26). 06e 전 행(keywords 없음)은 06b 프롬프트 그대로다.
```

new:

```python
  - 키워드(06e D23): 고른 키워드(input.keywords)를 넘기면 프롬프트에 '제목에 하나 이상 글자 그대로' 규칙 한 줄이 붙는다.
    예시 제목·이전 제목은 주지 않는다(함정 15·26). 06e 전 행(keywords 없음)은 06b 프롬프트 그대로다.
    검사는 06c 의 terms.contains(NFKC·casefold·공백 무시, 아니면 낱말이 순서대로)로 제목에 든 키워드를 보고
    card.keywords·card.checks.missing_keywords 에 싣는다. 하나도 없으면 엄격한 검사 미달로 다시 부르고, 세 번 다
    놓치면 근거 검사(무른 검사)만 넘은 마지막 카드를 보관한다 — 화면이 '제목에 ○○ 없음' 경고를 단다(06e 정함 17).
```

⑦ 같은 파일 import — 06c 일치 함수. old:

```python
from services.research.llm_json import extract_json
```

new:

```python
from services.research.llm_json import extract_json
from services.research.terms import contains
```

⑧ 같은 파일 — `_clean` 다음에 `keyword_misses`, `_bind` docstring. old:

```python
def _clean(value: str) -> str:
    return " ".join(strip_markers(value or "").split())


def _bind(output: dict, input: dict) -> dict:
    """해석한 출력 → {"card": Card | None}(계약 §4 Card). 제목이나 질문이 비면 card 는 None."""
```

new:

```python
def _clean(value: str) -> str:
    return " ".join(strip_markers(value or "").split())


def keyword_misses(title: str, keywords: list[str]) -> list[str]:
    """keywords 가운데 title 에 들어 있지 않은 것(06c terms.contains — 화면 keywordSpans 와 같은 일치 규칙)."""
    return [k for k in keywords if not contains(title, k)]


def _bind(output: dict, input: dict) -> dict:
    """해석한 출력 → {"card": Card | None}(계약 §4 Card). 제목이나 질문이 비면 card 는 None.
    고른 키워드(input.keywords — 06e)를 카드에 싣고, 다듬은 제목(단정 표현 바꿈·글자 상한 뒤)에 없는 것을
    checks.missing_keywords 에 센다."""
```

⑨ 같은 함수 본문. old:

```python
    figures = card_figures(input.get("adopted"), latest_year, input.get("corpus"))
    return {"card": {
```

new:

```python
    figures = card_figures(input.get("adopted"), latest_year, input.get("corpus"))
    keywords = [k for k in (input.get("keywords") or []) if isinstance(k, str)]
    return {"card": {
```

⑩ 같은 함수의 카드 dict. old:

```python
        "latest_year": latest_year,
        "edited": False,
        "checks": {"numbers": numbers_outside(f"{title}\n{question}"),
                   "softened": soft_title + soft_question, "recovered": recovered},
        "gen_id": None,
    }}
```

new:

```python
        "latest_year": latest_year,
        "edited": False,
        "keywords": keywords,
        "checks": {"numbers": numbers_outside(f"{title}\n{question}"),
                   "softened": soft_title + soft_question, "recovered": recovered,
                   "missing_keywords": keyword_misses(title, keywords)},
        "gen_id": None,
    }}
```

⑪ 같은 파일 `_check` → 무른 검사·엄격한 검사. old:

```python
def _check(output: dict) -> bool:
    card = output.get("card")
    return card is not None and len(card["evidence"]) >= MIN_TOPIC_EVIDENCE
```

new:

```python
def _soft_check(output: dict) -> bool:
    """무른 검사 — 06b 의 검사 그대로(직접 받치는 근거 MIN_TOPIC_EVIDENCE 편 이상)."""
    card = output.get("card")
    return card is not None and len(card["evidence"]) >= MIN_TOPIC_EVIDENCE


def _check(output: dict) -> bool:
    """엄격한 검사 — 무른 검사에 더해, 고른 키워드를 넘겼으면 제목에 하나 이상 들어 있다(06e D23). 하나도 없으면 공통
    규칙의 내용 검사 미달로 다시 부르고, 세 번 다 놓치면 run_generation 이 무른 검사를 넘은 마지막 카드를 낸다(정함 17)."""
    if not _soft_check(output):
        return False
    card = output["card"]
    keywords = card.get("keywords") or []
    return not keywords or len(card["checks"].get("missing_keywords") or []) < len(keywords)
```

⑫ 같은 파일 `EXECUTOR`. old:

```python
    apply=apply,
    is_empty=lambda out: (out or {}).get("card") is None,
)
```

new:

```python
    apply=apply,
    is_empty=lambda out: (out or {}).get("card") is None,
    soft_check=_soft_check,
)
```

⑬ `app/models/research_work.py` 머리 주석의 Card checks(Task K4 뒤 기준 — 주석만). old:

```python
               "checks": {"numbers": [str], "softened": int, "recovered": int}, "gen_id": int|null}
```

new:

```python
               "checks": {"numbers": [str], "softened": int, "recovered": int,
                          "missing_keywords": [str]},           — keywords 중 제목에 없는 것(06e)
               "gen_id": int|null}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_generate.py tests/test_research_work_executor.py tests/test_research_work_topic_card.py tests/test_research_topics_api.py tests/test_research_work_tasks.py -q -p no:cacheprovider`

Expected: `178 passed, 2 warnings` (generate 24 · executor 12 · topic_card 69 · topics 46 · tasks 27 — topic_card 는 Task K6 뒤 59 에 고정 예제 7·검사 2·세 번 놓친 카드 1 을 더했다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 5·오류 1 은 기준선과 같은 세 파일, 통과 = Task 앞(Step 1 에서 적은 값) + 14

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run 2>&1 | tail -4`

Expected: 실패 0, `Tests` = Task 앞(Step 1 에서 적은 값) + 9

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`

Expected: `0`(테스트의 JSON import 타입 — `termChecks.contains` 는 `{text, word, expected, note}[]`)

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/services/research_work/generate.py app/services/research_work/topic_card.py app/models/research_work.py app/tests/test_research_work_generate.py app/tests/test_research_work_executor.py app/tests/test_research_work_topic_card.py frontend/tests/unit/topicDeck.test.ts && git status --short && git commit -m "[Feat] round06e — 주제 카드 제목의 키워드 검사와 세 번 다 놓친 카드 보관(D23, spec §12-4 검사·§12-11, 06e 정함 17). 일치는 06c terms.contains(NFKC·casefold·공백 무시, 아니면 낱말이 순서대로)로 보고 카드에 keywords·checks.missing_keywords 를 싣는다. 고른 키워드가 제목에 하나도 없으면 내용 검사 미달로 다시 부르고, 세 번 다 놓치면 빈 결과('근거 부족' — 잘못된 안내) 대신 근거 검사만 넘은 마지막 카드를 그 모델 이름으로 보관한다 — 생성 틀에 선택 필드 Executor.soft_check 를 더해 run_generation 이 무른 검사만 넘은 마지막 출력을 낸다(스트리밍 경로는 그대로). 서버 일치와 화면 keywordSpans 를 06c 의 공용 고정 예제 term_checks.json·06e keyword_match.json 으로 묶는다"
```

---

## 파트 메모 — 뼈대와 다른 점

| # | 뼈대 | 이 파트 | 까닭 |
|---|---|---|---|
| 1 | Task K1 `measure.py` 는 `DATABASE_URL`·sqlalchemy 동기 엔진 | `core.config` 의 `DATABASE_URL_SYNC`(`postgresql://` — psycopg2) | `DATABASE_URL` 은 asyncpg URL(`postgresql+asyncpg://`)이라 동기 엔진에 쓸 수 없다. psycopg2 는 앱 이미지에 있다(`requirements.txt:13`) |
| 2 | Task K2 '`clean_concepts`·`MAX_CONCEPTS` 는 그대로' — `MIN_CONCEPTS` 언급 없음 | `MIN_CONCEPTS` 를 지운다(`MAX_CONCEPTS, MAX_CONCEPT_LEN = 5, 40`) | 검사가 '모델 후보 하나 이상'(`_check`)이 되어 쓰는 곳이 없다. `concepts.MAX_CONCEPT_LEN` 은 그대로 두고 `keywords.KEYWORD_LEN_MAX` 와 같은 값임을 테스트로 고정한다(`keywords` 가 `concepts` 를 import 하면 순환) |
| 3 | Task K2 테스트 목록 | 목록 밖 ✎ 7개를 더한다 — `test_research_work_concepts.py` 의 `test_limits`·`TestConceptsInput` 두 dict·`test_build_renders_the_real_template`·`test_unreadable_answers_parse_to_none`(매개변수 하나를 `{"terms": …}` 로), `test_research_work_executor.py::test_concepts_marks_an_empty_done_as_retryable`, `test_research_work_tasks.py` 두 테스트 | 실측으로 깨진다 — 입력 dict 에 `paper_keywords`, 프롬프트 문구, `keywords` 키가 이제 읽힘, 실행기에 `bind`, 저장 출력에 `candidates`, 개념 1개 답이 이제 통과 |
| 4 | Task K3 | 뼈대 그대로 | — |
| 5 | Task K4 `TestPrompt.test_no_array_sample_no_example_and_no_figures`(그대로 통과 확인) | ✎ — Jinja 문(`{% … %}`)을 빼고 견본 검사 | 지금 검사는 `{{ }}` 만 빼고 `"{"` 를 찾아 `{%- if keywords %}` 에서 떨어진다(실측). 뜻(배열·JSON 견본 금지)은 그대로 |
| 6 | Task K4 테스트 목록 | `test_research_work_seeds.py::TestTopicInput::test_shape` ✎ 를 더한다. `test_409_while_keywords_are_being_made` 는 queued·running 매개변수 둘 | 입력 dict 에 `keywords` 키가 생겨 전체 비교가 깨진다 |
| 7 | Task K5 `test_a_failure_while_adding_cards_leaves_nothing_behind` ✎(주제 행 넣기 실패로) | 이름을 `test_a_failure_while_adding_topics_leaves_nothing_behind` 로 바꾸고 `before_cursor_execute` 로 주제 행 INSERT 에서 실패시킨다 | 이어가기가 `topic_input` 을 부르지 않아 대역을 꽂을 자리가 없다 |
| 8 | Task K5 테스트 목록 | 목록 밖 ✎ 5개 — `test_second_continue_adds_no_topic_or_card`, `test_research_work_api.py::TestEndToEnd`, `test_research_work_tasks.py` 두 이벤트, `test_research_work_executor.py::test_concepts_keep_the_06a_branch`. `test_a_seed_slot_that_already_has_a_card_generation_gets_none` 은 done·failed·canceled 매개변수 셋 | 실측으로 깨진다(생성 수·반영 결과의 `cards`) |
| 9 | Task K6 상수 `KEYWORDS_TOO_FEW = "키워드를 2개 이상 고르세요"` | `f"키워드를 {MIN_PICKED_KEYWORDS}개 이상 고르세요"` | 같은 글. 최소 수가 바뀌면 문구가 따라온다 |
| 10 | Task K6 '넣은 것이 없고 skipped 도 0 이면 409' | 그대로 + 건너뛴 것만 있으면 200·빈 목록·디스패치 없음(테스트로 고정) | 뼈대가 정하지 않은 경우를 정했다 |
| 11 | Task K7 `keywordsChanged`·`keywordWarning` | `card.keywords` 가 없는 카드(06e 전)는 '바뀌었습니다'를 달지 않고, 사용자가 고친 카드(`card.edited`)는 경고를 달지 않는다 | 06e 전 카드는 무엇으로 만들었는지 모른다. 고친 제목은 서버가 다시 검사하지 않는다(`edit_topic` 은 `missing_keywords` 를 다시 세지 않는다) |
| 12 | Task K7 테스트 목록 | `workEvents.test.ts` 의 '연구를 아직 받지 않았으면' it ✎ 를 더한다. `keywordSpans` describe 는 고정 예제 모양 it·사례마다 it(`it.each` 7)·여러 키워드 it | 실측으로 깨진다(`reload`). 사례마다 it 은 `marker_checks.json` 선례 |
| 13 | 1-7 ConceptChips emits `retry: []`(그대로) | `retry: [genId: number]` 그대로 | '그대로'의 지금 시그니처가 `[genId: number]` 다(`ConceptChips.vue:71`) |
| 14 | Task K8 ConceptChips 기능 목록에 [저장] 없음 | [키워드만 저장]으로 남긴다(`save` emit 그대로) | 목차 묶음에만 쓰고 카드를 다시 만들지 않는 길. 저장하면 카드에 '키워드가 바뀌었습니다'가 붙어 [이 키워드로 다시 만들기]가 그대로 보인다 |
| 15 | Task K8 | TopicDeck 이 키워드를 고르는 동안 [다른 방향]을 막는다 | 서버가 409 `KEYWORDS_BUSY`(Task K4)로 막는 것을 화면이 먼저 막는다 |
| 16 | 1-8 Task K8 CSS 묶음 | `.wk-concepts__regen`·`.wk-topic--blocked` 를 더한다. 06b 의 `.wk-concept`·`.wk-concept__remove` 는 쓰지 않게 되지만 지우지 않는다 | 새 줄·새 상태(`blocked`)의 모양. 남는 규칙은 시각 디자인 담당 정리 몫 |
| 17 | Task K9 프론트 `term_checks.json` 일치 it(＋) | 처음부터 통과(실패 확인 단계에서 '실패 0' 을 기대) | Task K7 의 `keywordSpans` 가 같은 규칙이라 — 06c 계획의 공용 고정 예제 `term_checks.json`(contains 9 사례)으로 샌드박스 실측 |
| 18 | Task K6 — `topic_card.apply` 는 그대로(뼈대에 없음) | `apply` 의 edited 검사 바로 뒤에 고른 카드 검사 — state picked·제목 있음이면 새 카드든 빈 결과든 덮지 않는다. `TestApply.test_a_picked_topic_stays_picked` ✎(매개변수 둘 — +1) | 검토 반영. [이 키워드로 다시 만들기]가 도는 사이 고른 카드가 바뀌면 06e 정함 16 이 깨진다 |
| 19 | 1-6 Task K7 `cardStatus` — 생성 기록 없는 빈 카드는 concepts 가 열려 있으면 waiting, failed 면 blocked, 그 밖 failed | 빈 씨앗 자리(slot 있음·origin report_seed)만 — concepts 가 있으면 waiting(done·canceled 포함), failed 면 blocked. 씨앗 자리가 아니면 failed | 검토 반영. 씨앗 자리 카드 생성은 키워드 반영·취소와 같은 트랜잭션에 들어가 이벤트와 다시 읽기 사이에 생성이 없다 |
| 20 | 1-6 Task K7 `cardNote("blocked")` = `키워드를 다시 부르면 카드를 만듭니다` | `키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다` | 검토 반영. 키워드를 직접 넣고 저장한 사용자의 길을 함께 알린다 |
| 21 | 1-6 Task K7 `aiCardsStale(topics, concepts)` | `aiCardsStale(topics, concepts, conceptsGen?)` — blocked 씨앗 자리도 세고 다시 만드는 중인 카드는 세지 않는다(이름 그대로) | 검토 반영. 키워드 생성 failed 뒤 직접 저장한 연구가 막다른 길에 서지 않게 |
| 22 | 1-6 Task K7 이름 목록 | `cardRemakingNote` 를 더하고 `canPick` 이 다시 만드는 중인 카드를 막는다. Task K8 TopicCard 는 그 줄을 달고 [직접 고치기]도 막는다 | 검토 반영 — 06e 정함 16 의 화면 쪽 |

---

## 파트 H — 근거 칩 표기·기록 total·PDF

덮는 spec 항목: §12-4 '근거 칩 표기(D27)'의 범위 S(Q3 기본 — 정함 2)와 06b 이월 §7-14 중 주제 카드 칩만 → **Task H1**(§7-14 가 관찰한 보고서 절 인용 칩 `ProposalSection.vue:345` 은 범위 S 라 '성 연도' 그대로 — 완료노트 이월에 'Q3 M 과 함께 §7-14 의 보고서 인용 칩 남음'을 적는다). D26 의 N — 기록 목록 kind 별 total(§12-3 '모두 보기 (N)'·§12-5 '06e 가 fastapi 에 싣는다', 정함 26) → **Task H2**. §12-4 'PDF(싸면)'·§12-1 처분표 'PDF 내보내기'·D21 'Word·PDF 기본'(정함 27) → **Task H3**(조건부 — 이 계획의 마지막 Task). 하지 않는 것: Q3 범위 M(`citeLabel` 을 쓰는 다섯 곳 통일 — 보고서 인용칩·목차·절·논문 상세는 '성 연도' 그대로, 완료노트 이월), 기록 프론트(`types/history.ts`·`utils/historyStore.ts`·사이드바 '모두 보기 (N)' 그리기 — 06d 계획의 기록 total 받기(`totalOf`)·사이드바 단계 표시).

순서: Task H1(Task K7 뒤 — 같은 `topicDeck.ts`·`topicDeck.test.ts`) → Task H2(선행 없음 — Task K9 가 06c 머지를 기다리는 동안 먼저 해도 된다) → Task H3(계획의 마지막 Task, 머리 조건이 맞을 때만).

---

### Task H1: 근거 칩 표기 — 제1저자 전체 이름 연도 (Q3 S)

spec §12-4 '근거 칩 표기(D27)'·Q3 기본 S(정함 2)·06b 이월 §7-14 와 같은 문제(주제 카드 칩만). 주제 카드의 근거 칩 라벨이 지금은 보고서 인용칩과 같은 `citeLabel`('성 연도' — `utils/citations.ts:51-56`, 한글 이름은 첫 글자만 남아 '최 2018', 복성 '남궁민' → '남', `:45`)이라 같은 성이 많은 코퍼스에서 칩끼리 가를 수 없다(같은 문제가 06b 완료노트 §7-14 에 보고서 절 인용 칩으로 적혀 있다 — 이 Task 는 주제 카드 칩만 고친다). 이 Task 는 주제 카드 칩만 '제1저자 전체 이름 연도'(최성훈 2018)로 바꾼다.

- **라벨 `chipLabel(meta, cntsId)`:** 제1저자 = `splitAuthors(meta.personal_author)[0]`(보고서 참고문헌·`citeLabel` 과 같은 구분 — `;`·`|`·`·` 먼저, 쉼표는 조각마다 한글이 있거나 띄어 쓴 이름일 때만)에서 `외 n인` 꼬리(`citations.firstAuthorSurname` 과 같은 정규식)를 뗀다. 한글 이름(`/^[가-힣\s]+$/`)은 공백만 빼고 전체(띄어 쓴 복성 '남궁 민' → '남궁민'), 그 밖(영문 '성, 이름'·'Jane Doe')은 적힌 그대로. 연도 = `pubYear(meta.pub_date)` — 있으면 `` `${이름} ${연도}` ``, 없으면 이름만. 저자가 없으면(칸이 비거나 공백뿐) 제목 앞 `SHORT_TITLE_MAX = 18` 자(코드포인트, 넘으면 자른 끝 공백을 떼고 `…`)를 이름 자리에 쓴다. 저자도 제목도 없거나 서지가 없으면 `cntsId`.
- **툴팁 `chipTooltip(meta, cntsId)`:** 서지 한 줄 — `[제목, 저자, 학술지, 연도]` 가운데 빈칸이 아닌 것을 `" · "` 로 잇는다. 저자 칸은 `splitAuthors` 로 나눠 `", "` 로 잇는다(원문 구분자 `;`·`|` 를 그대로 보이지 않게 — 라벨과 같은 구분). 서지가 없거나 모든 칸이 비면 `cntsId`. 지금 툴팁(`TopicCard.vue:36` 의 `:title="chip.title"`)은 제목만이었다.
- **범위 S:** `citeLabel` 과 그것을 쓰는 네 곳(`components/research/CitationChip.vue:95`·`components/work/OutlineEditor.vue:212`·`components/work/ProposalSection.vue:345`·`utils/paperDetail.ts:27`)과 `tests/unit/citations.test.ts` 는 고치지 않는다. `topicDeck.ts` 는 `citations.ts` 에서 `pubYear`·`splitAuthors` 만 import 한다(`citeLabel` import 는 없어진다). `TopicCard.vue` 는 `evidenceChips` 의 모양(`{ cntsId, label, title }`)이 그대로라 고치지 않는다.

**알아 둘 것:**
- **앞 Task 뒤 기준:** `frontend/utils/topicDeck.ts`·`frontend/tests/unit/topicDeck.test.ts` 는 Task R1(`conceptsNote` 문구)·Task K7(키워드 함수·`cardStatus`·`cardNote`·import 목록)이 먼저 고친다. 이 Task 가 잡는 old 는 Task R1·Task K7 이 건드리지 않는 자리다 — `topicDeck.ts` 의 `import { citeLabel } from "~/utils/citations";` 한 줄, `CHIP_TITLE_CHARS` 두 줄(dev `da80f23` `:31-32`), `shortTitle`·`evidenceChips` 블록(`:98-118`), 테스트의 import 목록 `  cardStatus,` 한 줄·`  seedLine,` 한 줄, describe `evidenceChips`(`:160-181`)의 첫 it 와 describe 끝. Edit 가 old 를 못 찾으면(앞 Task 가 그 자리를 바꿨으면) 함수·it 이름으로 그 블록을 찾아 아래 '교체 후'로 통째 갈음한다.
- **이름(1-6 계약):** `SHORT_TITLE_MAX`·`chipLabel`·`chipTooltip` 은 이 파일만 내보낸다(Nuxt 자동 import 중복 없음 — dev `da80f23` 에서 `grep -rn "chipLabel\|chipTooltip\|SHORT_TITLE_MAX" frontend/utils frontend/composables frontend/components frontend/pages` 빈 출력). 정규식 상수 `HANGUL_NAME`·`OTHERS_TAIL` 과 도우미 `firstAuthorName`·`shortTitle` 은 내보내지 않는다(`citations.ts` 의 같은 이름 `HANGUL_NAME` 도 비공개라 겹치지 않는다).
- `.vue` 는 고치지 않는다 — 칩 모양 CSS(`.wk-topic__chip`, `work.css` — `display: inline-block`, 칩 목록은 `flex-wrap: wrap`)가 긴 라벨('가족 지지가 노인 우울에 미치는… 2013')을 줄바꿈으로 받는다.

**Files:**
- Modify: `frontend/utils/topicDeck.ts` (import 한 줄, `CHIP_TITLE_CHARS` 두 줄 → `SHORT_TITLE_MAX`·정규식 둘, `shortTitle`·`evidenceChips` → `shortTitle`·`firstAuthorName`·`chipLabel`·`chipTooltip`·`evidenceChips`)
- Test: `frontend/tests/unit/topicDeck.test.ts` (import 셋 더함, describe `evidenceChips` 첫 it ✎, 새 it 둘)

기준선(Task K7 적용 뒤): typecheck 오류 0, 전체 vitest 실패 0, build 완료. 이 Task 는 vitest 를 +2 한다(dev `da80f23` 만 놓고 잰 값: `topicDeck.test.ts` 26 → 28, 전체 `40 files / 732` → `734` — 통합 사본 실측).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/topicDeck.test.ts` — 맨 위 `import { … } from "~/utils/topicDeck";` 목록에 세 이름을 더한다(목록은 알파벳 순 — Task K7 이 더한 이름과 상관없이 아래 두 줄은 그 목록에 하나씩 있다).

교체 전:

```ts
  cardStatus,
```

교체 후:

```ts
  cardStatus,
  chipLabel,
  chipTooltip,
```

교체 전:

```ts
  seedLine,
```

교체 후:

```ts
  seedLine,
  SHORT_TITLE_MAX,
```

describe `evidenceChips`(dev `da80f23` `:160-181`)의 첫 it — 교체 전(`:167-172`):

```ts
  it("보고서 인용칩과 같은 '저자 연도' 라벨과 전체 제목을 준다", () => {
    expect(evidenceChips(CARD, PAPERS)).toEqual([
      { cntsId: "KCI_A", label: "김 2015", title: "노인의 우울과 사회적 지지" },
      { cntsId: "KCI_B", label: "가족 지지가 노인 우울…", title: "가족 지지가 노인 우울에 미치는 영향 연구" },
    ]);
  });
```

교체 후:

```ts
  it("제1저자 전체 이름과 연도를 라벨로, 서지 한 줄을 툴팁으로 — 저자가 없으면 제목 앞 18자와 연도", () => {
    expect(evidenceChips(CARD, PAPERS)).toEqual([
      {
        cntsId: "KCI_A",
        label: "김철수 2015",
        title: "노인의 우울과 사회적 지지 · 김철수, 이영희 · 노인복지연구 · 2015",
      },
      {
        cntsId: "KCI_B",
        label: "가족 지지가 노인 우울에 미치는… 2013",
        title: "가족 지지가 노인 우울에 미치는 영향 연구 · 2013",
      },
    ]);
    // 18자까지는 자르지 않고, 넘으면 18자 뒤에 말줄임(자른 끝의 공백은 뗀다 — KCI_B 의 18번째 글자는 공백이다)
    const untitled = (title: string): PaperMeta => ({ title, personal_author: null, pub_date: null, series_title: null });
    expect(SHORT_TITLE_MAX).toBe(18);
    expect(chipLabel(untitled("가".repeat(18)), "K")).toBe("가".repeat(18));
    expect(chipLabel(untitled("가".repeat(19)), "K")).toBe(`${"가".repeat(18)}…`);
  });
```

둘째 it(`저자를 모르면 제목 앞부분(짧으면 그대로), 서지가 없으면 cnts_id 로 가른다` — `:174-180`)은 그대로 둔다(새 규칙에서도 `KCI_C` 는 저자·연도 없는 짧은 제목 `지지망 분석`, `KCI_Z` 는 서지가 없어 `KCI_Z` 로 같다). describe 끝 — 교체 전(`:178-181`):

```ts
      { cntsId: "KCI_Z", label: "KCI_Z", title: "KCI_Z" },
    ]);
  });
});
```

교체 후(같은 describe 안에 it 둘을 더한다):

```ts
      { cntsId: "KCI_Z", label: "KCI_Z", title: "KCI_Z" },
    ]);
  });

  it("복성·외 n인·영문 이름·연도 없음", () => {
    const meta = (personal_author: string | null, pub_date: string | null = "2018-05"): PaperMeta => ({
      title: "사회적 지지 척도의 타당화",
      personal_author,
      pub_date,
      series_title: null,
    });
    expect(chipLabel(meta("최성훈"), "K1")).toBe("최성훈 2018");
    // 한글 이름은 공백만 빼고 전체 — 띄어 쓴 복성도 붙인다
    expect(chipLabel(meta("남궁 민"), "K1")).toBe("남궁민 2018");
    expect(chipLabel(meta("선우 현정 외 2인"), "K1")).toBe("선우현정 2018");
    expect(chipLabel(meta("최성훈외3인"), "K1")).toBe("최성훈 2018");
    // 여러 저자는 제1저자만(쉼표·세미콜론·세로줄·가운뎃점 — splitAuthors 와 같은 구분)
    expect(chipLabel(meta("김철수, 이영희"), "K1")).toBe("김철수 2018");
    expect(chipLabel(meta("Jane Doe | 박지원"), "K1")).toBe("Jane Doe 2018");
    // 영문 '성, 이름' 은 적힌 그대로
    expect(chipLabel(meta("Smith, John"), "K1")).toBe("Smith, John 2018");
    // 연도를 모르면 이름만
    expect(chipLabel(meta("이영희", null), "K1")).toBe("이영희");
    expect(chipLabel(meta("이영희", "발행년 미상"), "K1")).toBe("이영희");
    // 저자 칸이 공백뿐이면 저자가 없는 것 — 짧은 제목과 연도
    expect(chipLabel(meta("  ", "2019"), "K1")).toBe("사회적 지지 척도의 타당화 2019");
    // 저자도 제목도 없으면 연도가 있어도 cnts_id
    expect(chipLabel({ title: " ", personal_author: null, pub_date: "2019", series_title: null }, "K2")).toBe("K2");
    expect(chipLabel(undefined, "KCI_Z")).toBe("KCI_Z");
  });

  it("툴팁은 서지 한 줄", () => {
    expect(
      chipTooltip(
        { title: " 노인의 우울과 사회적 지지 ", personal_author: "김철수; 이영희", pub_date: "2015-03", series_title: "노인복지연구" },
        "KCI_A",
      ),
    ).toBe("노인의 우울과 사회적 지지 · 김철수, 이영희 · 노인복지연구 · 2015");
    // 빈 칸(공백뿐인 칸 포함)은 건너뛴다
    expect(chipTooltip({ title: "지지망 분석", personal_author: null, pub_date: null, series_title: " " }, "KCI_C")).toBe(
      "지지망 분석",
    );
    expect(chipTooltip({ title: "", personal_author: "Smith, John", pub_date: "2020", series_title: null }, "KCI_D")).toBe(
      "Smith, John · 2020",
    );
    // 서지가 없거나 모든 칸이 비면 cnts_id
    expect(chipTooltip(undefined, "KCI_Z")).toBe("KCI_Z");
    expect(chipTooltip({ title: " ", personal_author: null, pub_date: null, series_title: null }, "KCI_E")).toBe("KCI_E");
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/topicDeck.test.ts`
Expected: `Test Files  1 failed (1)` / `Tests  3 failed | <Task H1 앞 이 파일의 수 − 1> passed (<Task H1 앞 이 파일의 수 + 2>)`(dev `da80f23` 만 놓고 잰 값 `3 failed | 25 passed (28)` — Task R1·Task K7 이 더한 it 만큼 passed·합계가 늘어난다). 실패 셋:
- `evidenceChips > 제1저자 전체 이름과 연도를 라벨로, …` — `AssertionError: expected [ { cntsId: 'KCI_A', …(2) }, …(1) ] to deeply equal [ { cntsId: 'KCI_A', …(2) }, …(1) ]`(라벨이 아직 `김 2015`·`가족 지지가 노인 우울…`)
- `evidenceChips > 복성·외 n인·영문 이름·연도 없음` — `TypeError: (0 , chipLabel) is not a function`
- `evidenceChips > 툴팁은 서지 한 줄` — `TypeError: (0 , chipTooltip) is not a function`

- [ ] **Step 3: 칩 라벨·툴팁을 구현한다**

`frontend/utils/topicDeck.ts` — 교체 전(`:14`):

```ts
import { citeLabel } from "~/utils/citations";
```

교체 후:

```ts
import { pubYear, splitAuthors } from "~/utils/citations";
```

교체 전(`:31-32`):

```ts
// 저자를 모르는 근거 칩은 제목 앞부분으로 가른다
const CHIP_TITLE_CHARS = 12;
```

교체 후:

```ts
// 근거 칩 — 저자를 모르는 논문은 제목 앞 이만큼(코드포인트)과 연도로 가른다(spec §12-4 D27)
export const SHORT_TITLE_MAX = 18;
// 한글 이름(띄어 쓴 복성 '남궁 민' 포함)은 공백만 빼고 전체를 쓴다. 영문 이름('Smith, John')은 적힌 그대로
const HANGUL_NAME = /^[가-힣\s]+$/;
// '최성훈 외 2인' 의 꼬리 — citations.firstAuthorSurname 과 같은 규칙
const OTHERS_TAIL = /\s*외\s*\d*\s*인?\s*$/;
```

교체 전(`:98-118`):

```ts
function shortTitle(title: string | null | undefined): string | null {
  const chars = [...(title ?? "").trim()];
  if (!chars.length) return null;
  return chars.length > CHIP_TITLE_CHARS ? `${chars.slice(0, CHIP_TITLE_CHARS).join("")}…` : chars.join("");
}

// 근거 칩 — 보고서 인용칩과 같은 '저자 연도' 라벨(citeLabel). 단계 화면에는 REPORT_JOB provide 가 없어
// CitationChip 을 쓰지 않는다. 저자를 모르면 제목 앞부분, 서지가 없으면 cnts_id
export function evidenceChips(
  card: TopicCard,
  papers: Record<string, PaperMeta>,
): { cntsId: string; label: string; title: string }[] {
  return card.evidence.map((cntsId) => {
    const meta = papers[cntsId];
    return {
      cntsId,
      label: citeLabel(meta, shortTitle(meta?.title) ?? cntsId),
      title: meta?.title?.trim() || cntsId,
    };
  });
}
```

교체 후:

```ts
// 자른 끝의 공백은 떼고 말줄임을 붙인다 — '… 미치는 …' 가 아니라 '… 미치는…'
function shortTitle(title: string | null | undefined): string | null {
  const chars = [...(title ?? "").trim()];
  if (!chars.length) return null;
  return chars.length > SHORT_TITLE_MAX ? `${chars.slice(0, SHORT_TITLE_MAX).join("").trimEnd()}…` : chars.join("");
}

// 제1저자의 전체 이름 — '외 n인' 꼬리를 떼고, 한글 이름은 공백을 빼 붙인다(복성 그대로). 저자가 없으면 null
function firstAuthorName(personal: string | null | undefined): string | null {
  const first = splitAuthors(personal)[0]?.replace(OTHERS_TAIL, "").trim();
  if (!first) return null;
  return HANGUL_NAME.test(first) ? first.replace(/\s/g, "") : first;
}

// 근거 칩 라벨(D27, Q3 범위 S) — '제1저자 전체 이름 연도'(최성훈 2018). '성 연도'(최 2018)는 같은 성이 많아 칩만으로
// 가를 수 없었다(06b 이월 §7-14 와 같은 문제). 저자가 없으면 짧은 제목과 연도, 저자도 제목도 없으면 cnts_id, 연도를 모르면 이름만.
// 보고서 인용칩·목차·절·논문 상세의 citeLabel('성 연도')은 그대로 둔다
export function chipLabel(meta: PaperMeta | undefined, cntsId: string): string {
  const who = firstAuthorName(meta?.personal_author) ?? shortTitle(meta?.title);
  if (!who) return cntsId;
  const year = pubYear(meta?.pub_date);
  return year ? `${who} ${year}` : who;
}

// 근거 칩 툴팁 — 서지 한 줄(제목 · 저자 · 학술지 · 연도 가운데 있는 것). 저자는 칩과 같은 구분(splitAuthors)으로 나눠
// 쉼표로 잇는다. 서지가 없거나 모든 칸이 비면 cnts_id
export function chipTooltip(meta: PaperMeta | undefined, cntsId: string): string {
  if (!meta) return cntsId;
  const parts = [meta.title, splitAuthors(meta.personal_author).join(", "), meta.series_title, pubYear(meta.pub_date)]
    .map((s) => (s ?? "").trim())
    .filter(Boolean);
  return parts.length ? parts.join(" · ") : cntsId;
}

// 근거 칩 — 라벨은 chipLabel, 툴팁(title)은 chipTooltip. 단계 화면에는 REPORT_JOB provide 가 없어 CitationChip 을 쓰지 않는다
export function evidenceChips(
  card: TopicCard,
  papers: Record<string, PaperMeta>,
): { cntsId: string; label: string; title: string }[] {
  return card.evidence.map((cntsId) => {
    const meta = papers[cntsId];
    return { cntsId, label: chipLabel(meta, cntsId), title: chipTooltip(meta, cntsId) };
  });
}
```

옛 상수·옛 import·옛 호출이 이 파일에 더 없는지 본다(`chipLabel` 머리 주석에 `citeLabel('성 연도')` 라는 말이 남으므로 낱말 하나로 찾지 않고 옛 import 꼴 `{ citeLabel }` 과 옛 호출 꼴 `citeLabel(meta` 로 찾는다):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -n "CHIP_TITLE_CHARS\|citeLabel(meta\|{ citeLabel }" utils/topicDeck.ts`
Expected: 빈 출력(고치기 전에는 넷이 나온다 — dev `da80f23` 에서 `14:import { citeLabel } …`·`32:const CHIP_TITLE_CHARS = 12;`·`101:  return chars.length > CHIP_TITLE_CHARS …`·`114:      label: citeLabel(meta, …`, Task R1·Task K7 뒤에는 줄 번호만 다르다 — 통합 사본 실측)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/topicDeck.test.ts`
Expected: `Test Files  1 passed (1)` / `Tests  <Task H1 앞 이 파일의 수 + 2> passed`(dev `da80f23` 만 놓고 `28 passed (28)`)

- [ ] **Step 5: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files <Task H1 앞과 같은 수> passed` / `Tests <Task H1 앞 + 2> passed`(dev `da80f23` 만 놓고 `40 passed (40)` / `734 passed (734)`)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep -E "Duplicated imports|Build complete" | sed 's/, the one from.*//'`
Expected: `Duplicated imports` 줄이 Task H1 앞과 같다(dev `da80f23` 기준 `WARN Duplicated imports "queueLine"` 두 줄 — 글자 앞뒤에 색 코드가 붙어 나온다. 이 worktree 가 앞 Task 의 `git merge dev`(Task R6 — 또는 06d 가 먼저 머지된 뒤의 Task K9)로 06d 를 받아 06d 의 queueLine 다시 내보내기 지우기(`utils/researchEvents.ts` 의 `export { queueLine }`)가 들어왔으면 0줄). `chipLabel`·`chipTooltip`·`SHORT_TITLE_MAX` 가 든 줄은 없다. 마지막 줄 `└  ✨ Build complete!`(새 이름이 다른 utils 와 겹치지 않는다 — dev `da80f23` 에 이 파트의 프론트 변경을 얹은 통합 사본 실측: 경고는 `queueLine` 두 줄뿐, WARN 전체 줄 수가 Task H1 앞과 같은 수)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff --stat -- frontend/utils/citations.ts frontend/tests/unit/citations.test.ts frontend/components/work/TopicCard.vue frontend/components/research/CitationChip.vue frontend/utils/paperDetail.ts`
Expected: 빈 출력(범위 S — `citeLabel` 과 다른 네 곳·칩을 그리는 부품은 그대로)

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/utils/topicDeck.ts && git add frontend/tests/unit/topicDeck.test.ts && git status --short && git commit -m "[Feat] round06e 프론트 — 주제 카드의 근거 칩을 '제1저자 전체 이름 연도'(최성훈 2018)로 보인다. 지금 칩은 보고서 인용칩과 같은 citeLabel('성 연도')이라 한글 이름은 첫 글자만 남고(복성 남궁민 → 남) 같은 성이 많은 코퍼스에서 칩끼리 가를 수 없었다(06b 이월 §7-14 와 같은 문제 — 주제 카드 칩만). 제1저자는 splitAuthors 의 첫 사람에서 '외 n인'을 떼고, 한글 이름은 공백만 빼 붙이며(띄어 쓴 복성 포함) 영문 이름은 적힌 그대로 쓴다. 연도를 모르면 이름만, 저자가 없으면 제목 앞 18자(SHORT_TITLE_MAX — 넘으면 말줄임)와 연도, 서지가 없으면 cnts_id. 툴팁은 제목·저자·학술지·연도 가운데 있는 것을 잇는 서지 한 줄이다. 범위는 주제 카드 칩만이다(Q3 기본 S) — citeLabel 과 보고서 인용칩·목차·절·논문 상세는 그대로 둔다"
```

---

### Task H2: 기록 목록 kind 별 total

spec D26 의 N(§12-3 '사이드바 단계 표시 — 모두 보기 (N)'·§12-5 'N 의 kind 별 total 은 06e 가 fastapi 에 싣는다')·정함 26. `GET /api/history?kind=&limit=&before=` 응답(`app/api/history.py:79-91` — 지금 `{items, next_cursor}`)에 `total` 을 싣는다. `total` 은 **이 브라우저(x-session-id)·이 kind(주지 않으면 모든 kind)의 지우지 않은 기록 수**이고 `before`·`limit` 과 무관하다 — 사이드바가 첫 쪽만 읽어도 '모두 보기 (N)' 의 N 을 안다.

- **따로 센다(정함 26):** `HistoryRepository.list` 의 반환 모양(`(items, next_cursor)` 2-튜플)은 그대로 두고 `count(session_id, kind) -> int` 를 더해 API 가 둘 다 부른다 — 기존 저장소 테스트(`_list` 가 튜플을 푸는 59개 중 여럿)를 깨지 않는다. 두 쿼리가 같은 조건을 쓰도록 `list` 의 where(`:67-71` — 이 브라우저·`deleted_at IS NULL`·kind)를 모듈 함수 `_live(session_id, kind)` 로 빼서 함께 쓴다(동작 그대로 — `before` 조건은 `list` 에만 남는다).
- **쿼리 비용:** `SELECT count(*) FROM history_items WHERE session_id = … AND deleted_at IS NULL [AND kind = …]` 는 기존 부분 인덱스 `ix_history_items_session_kind_created`(`models/history.py:20-24` — `(session_id, kind, created_at DESC) WHERE deleted_at IS NULL`)를 탄다. 스키마 변경 없음.
- **응답 모양:** `HistoryListOut.total: int | None = None`(`app/schemas/history.py:75-77`). API 는 늘 정수를 싣는다(`None` 기본값은 모양 선언 — 06d 가 `res.total ?? null` 로 읽는다 — 06d 계획의 기록 total 받기, `createServerStore().list`).
- **백엔드 세 파일뿐이다.** `frontend/types/history.ts` 의 `HistoryListOut.total?`·`utils/historyStore.ts` 로 나르기·사이드바 그리기는 06d(06d 계획의 기록 total 받기·사이드바 '모두 보기 (N)')가 단다 — 06e 는 프론트 기록 파일을 건드리지 않는다(spec §12-5, 같은 줄을 두 줄이 따로 더하면 늦게 머지하는 쪽에서 충돌).

**알아 둘 것:**
- 이 Task 가 고치는 파일·테스트 둘은 06e 의 다른 Task·06c·06d 가 고치지 않는다 — 줄 번호·기대 수는 dev `da80f23` 값 그대로다(`test_history_repository.py` 59 passed·`test_history_api.py` 45 passed, 통합 사본 실측).
- 기존 테스트 하나가 응답 전체를 견준다 — `TestOwnership.test_other_browser_list_is_empty`(`test_history_api.py:138-139`, `== {"items": [], "next_cursor": None}`). 응답에 `total` 이 붙으므로 기대 dict 에 `"total": 0` 을 더한다(✎ — 남의 기록이 수에도 새지 않는다는 단언이 함께 된다). 다른 테스트는 키를 하나씩 읽어 그대로다(`grep -rn "/api/history\|HistoryRepository" app/tests` → 이 두 파일뿐).
- 테스트 DB 는 `history_sqlite` 의 SQLite(`AsyncSessionOverSync` — `execute`·`scalar` 를 동기 세션으로 넘긴다)라 `count` 의 SQL 이 실제로 돈다. async 는 `_call`(내부 `asyncio.run`)로 부른다.

**Files:**
- Modify: `app/repositories/history.py` (import `:5`, `InvalidCursor`(`:33-34`) 아래 새 `_live`, `list`(`:63-88`)의 where, `list` 아래 새 `count`)
- Modify: `app/schemas/history.py` (`HistoryListOut` `:75-77`)
- Modify: `app/api/history.py` (`list_history` `:87-91`)
- Test: `app/tests/test_history_repository.py` (도우미 `_count`, `TestList` 새 테스트 둘)
- Test: `app/tests/test_history_api.py` (`TestOwnership.test_other_browser_list_is_empty` ✎, `TestList` 새 테스트 하나)

기준선(Task H1 뒤 — 백엔드는 Task H1 이 바꾸지 않는다): 백엔드 전체 `5 failed, <Task H2 앞> passed, 1 skipped, 2 warnings, 1 error`(실패·오류는 기준선과 같은 세 파일).

- [ ] **Step 1: 저장소의 실패하는 테스트를 쓴다**

`app/tests/test_history_repository.py` — 교체 전(`:54-55`):

```python
def _list(engine, sid, kind=None, limit=30, before=None):
    return _call(engine, lambda r: r.list(sid, kind, limit, before))
```

교체 후:

```python
def _list(engine, sid, kind=None, limit=30, before=None):
    return _call(engine, lambda r: r.list(sid, kind, limit, before))


def _count(engine, sid, kind=None):
    return _call(engine, lambda r: r.count(sid, kind))
```

`TestList` 끝 — 교체 전(`:227-229`):

```python
    def test_malformed_cursor_raises(self, engine):
        with pytest.raises(InvalidCursor):
            _list(engine, SID_A, before="garbage")
```

교체 후:

```python
    def test_malformed_cursor_raises(self, engine):
        with pytest.raises(InvalidCursor):
            _list(engine, SID_A, before="garbage")

    def test_count_is_the_live_items_of_that_kind_whatever_the_page(self, engine):
        books = [uuid.uuid4() for _ in range(4)]
        _import(engine, SID_A, *[
            {"id": i, "kind": "book", "title": f"검색 {n}", "created_at": _at(n)}
            for n, i in enumerate(books)
        ], {"id": uuid.uuid4(), "kind": "paper", "title": "논문 검색", "created_at": _at(9)})
        # 한 쪽(limit)만 읽어도 수는 그 kind 전부다 — 사이드바 '모두 보기 (N)'
        items, cursor = _list(engine, SID_A, kind="book", limit=2)
        assert len(items) == 2 and cursor is not None
        assert _count(engine, SID_A, "book") == 4
        assert _count(engine, SID_A, "paper") == 1
        assert _count(engine, SID_A, "research") == 0

    def test_count_without_kind_counts_every_kind_and_skips_deleted_and_other_browsers(self, engine):
        book, paper, gone = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        _put(engine, SID_A, book, kind="book")
        _put(engine, SID_A, paper, kind="paper")
        _put(engine, SID_A, gone, kind="book")
        _put(engine, SID_B, uuid.uuid4(), kind="book")
        _call(engine, lambda r: r.soft_delete(SID_A, gone))
        assert _count(engine, SID_A) == 2
        assert _count(engine, SID_A, "book") == 1
        assert _count(engine, SID_B) == 1
```

- [ ] **Step 2: API 의 실패하는 테스트를 쓴다**

`app/tests/test_history_api.py` — 교체 전(`:138-139`):

```python
    def test_other_browser_list_is_empty(self, api, item_id):
        assert api.client.get("/api/history", headers=B).json() == {"items": [], "next_cursor": None}
```

교체 후:

```python
    def test_other_browser_list_is_empty(self, api, item_id):
        assert api.client.get("/api/history", headers=B).json() == {"items": [], "next_cursor": None, "total": 0}
```

`TestList` 끝 — 교체 전(`:221-223`):

```python
    def test_malformed_cursor_is_400(self, api):
        res = api.client.get("/api/history?before=garbage", headers=A)
        assert res.status_code == 400
```

교체 후:

```python
    def test_malformed_cursor_is_400(self, api):
        res = api.client.get("/api/history?before=garbage", headers=A)
        assert res.status_code == 400

    def test_total_is_in_the_response_and_ignores_the_cursor(self, api):
        items = [
            {"legacy_id": f"172700000000{n}", "kind": "book", "title": f"검색 {n}",
             "created_at": f"2026-09-0{n + 1}T09:00:00+00:00"}
            for n in range(3)
        ] + [{"legacy_id": "1727000000009", "kind": "paper", "title": "논문 검색",
              "created_at": "2026-09-05T09:00:00+00:00"}]
        api.client.post("/api/history/import", headers=A, json={"items": items})

        first = api.client.get("/api/history?kind=book&limit=2", headers=A).json()
        assert len(first["items"]) == 2 and first["total"] == 3
        second = api.client.get("/api/history", headers=A,
                                params={"kind": "book", "limit": 2, "before": first["next_cursor"]}).json()
        assert len(second["items"]) == 1 and second["total"] == 3
        # kind 를 주지 않으면 모든 kind, 남의 브라우저는 0
        assert api.client.get("/api/history", headers=A).json()["total"] == 4
        assert api.client.get("/api/history", headers=B).json()["total"] == 0
```

- [ ] **Step 3: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_history_repository.py tests/test_history_api.py -q -p no:cacheprovider`
Expected: `4 failed, 103 passed, 1 warning`(통합 사본 실측). 실패 넷:
- `test_history_repository.py::TestList::test_count_is_the_live_items_of_that_kind_whatever_the_page`·`::TestList::test_count_without_kind_counts_every_kind_and_skips_deleted_and_other_browsers` — `AttributeError: 'HistoryRepository' object has no attribute 'count'`
- `test_history_api.py::TestOwnership::test_other_browser_list_is_empty` — `AssertionError: assert {'items': [],...cursor': None} == {'items': [],...e, 'total': 0}`
- `test_history_api.py::TestList::test_total_is_in_the_response_and_ignores_the_cursor` — `KeyError: 'total'`

- [ ] **Step 4: 저장소에 수 세기를 더한다**

`app/repositories/history.py` — 교체 전(`:5`):

```python
from sqlalchemy import and_, exists, func, or_, select, update
```

교체 후(`ColumnElement` 는 `workers/job_runtime.py:31` 과 같은 import):

```python
from sqlalchemy import ColumnElement, and_, exists, func, or_, select, update
```

교체 전(`:33-34`):

```python
class InvalidCursor(ValueError):
    pass
```

교체 후:

```python
class InvalidCursor(ValueError):
    pass


def _live(session_id: uuid.UUID, kind: HistoryKind | None) -> list[ColumnElement[bool]]:
    """목록과 수가 함께 쓰는 조건 — 이 브라우저의 지우지 않은 기록(kind 를 주면 그 kind 만)."""
    clauses = [HistoryItem.session_id == session_id, HistoryItem.deleted_at.is_(None)]
    if kind is not None:
        clauses.append(HistoryItem.kind == kind)
    return clauses
```

`list` 의 where — 교체 전(`:66-72`):

```python
        """최신순 한 쪽과 다음 쪽 커서. 커서가 틀리면 InvalidCursor."""
        stmt = select(*_LIST_COLUMNS).where(
            HistoryItem.session_id == session_id, HistoryItem.deleted_at.is_(None),
        )
        if kind is not None:
            stmt = stmt.where(HistoryItem.kind == kind)
        if before is not None:
```

교체 후:

```python
        """최신순 한 쪽과 다음 쪽 커서. 커서가 틀리면 InvalidCursor."""
        stmt = select(*_LIST_COLUMNS).where(*_live(session_id, kind))
        if before is not None:
```

`list` 끝 — 교체 전(`:87-88`):

```python
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return items, next_cursor
```

교체 후(`list` 바로 아래, `get` 앞에 `count` 를 더한다):

```python
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return items, next_cursor

    async def count(self, session_id: uuid.UUID, kind: HistoryKind | None) -> int:
        """list 와 같은 조건의 전체 수 — 쪽(before·limit)과 무관하다(사이드바 '모두 보기 (N)')."""
        stmt = select(func.count()).select_from(HistoryItem).where(*_live(session_id, kind))
        return (await self.db.execute(stmt)).scalar_one()
```

- [ ] **Step 5: 응답 모양과 API 를 고친다**

`app/schemas/history.py` — 교체 전(`:75-77`):

```python
class HistoryListOut(BaseModel):
    items: list[HistoryItemOut]
    next_cursor: str | None = None
```

교체 후:

```python
class HistoryListOut(BaseModel):
    items: list[HistoryItemOut]
    next_cursor: str | None = None
    # 이 브라우저·이 kind(없으면 모든 kind)의 지우지 않은 기록 수 — before 와 무관하다(사이드바 '모두 보기 (N)')
    total: int | None = None
```

`app/api/history.py` `list_history` — 교체 전(`:87-91`):

```python
    try:
        items, next_cursor = await HistoryRepository(db).list(browser_id, kind, limit, before)
    except InvalidCursor:
        raise HTTPException(status_code=400, detail="before 형식이 올바르지 않다")
    return HistoryListOut(items=items, next_cursor=next_cursor)
```

교체 후:

```python
    repo = HistoryRepository(db)
    try:
        items, next_cursor = await repo.list(browser_id, kind, limit, before)
    except InvalidCursor:
        raise HTTPException(status_code=400, detail="before 형식이 올바르지 않다")
    # 사이드바 '모두 보기 (N)' — 이 브라우저·이 kind 의 지우지 않은 기록 전부(쪽과 무관)
    total = await repo.count(browser_id, kind)
    return HistoryListOut(items=items, next_cursor=next_cursor, total=total)
```

(커서가 틀린 요청은 400 으로 먼저 끝나 수를 세지 않는다. 읽기 둘은 같은 요청 세션 안의 짧은 SELECT 이고 사이에 외부 호출이 없다 — 함정 18 과 무관.)

- [ ] **Step 6: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_history_repository.py tests/test_history_api.py -q -p no:cacheprovider`
Expected: `107 passed, 1 warning`(저장소 59 + 2 = 61, API 45 + 1 = 46 — 통합 사본 실측)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors 2>&1 | tail -1`
Expected: `5 failed, <Task H2 앞 + 3> passed, 1 skipped, 2 warnings, 1 error`(dev `da80f23` 에 Task H2 만 얹은 통합 사본 실측 `5 failed, 2330 passed, 1 skipped, 2 warnings, 1 error` — 기준선 2327 + 3) — 실패 5·오류 1 은 기준선과 같은 세 파일(`test_build_manifest.py` 2·`test_loaders.py` 3·`test_book_chat.py` 수집 오류. Task S2 의 대역이 `test_book_chat.py` 수집 오류를 바꿨다면 그 Task 뒤의 값이 기준이다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff --stat -- frontend/types/history.ts frontend/utils/historyStore.ts frontend/utils/historyState.ts frontend/composables/useHistory.ts frontend/components/AppSidebar.vue`
Expected: 빈 출력(기록 프론트는 06d 몫)

- [ ] **Step 7: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add app/repositories/history.py && git add app/schemas/history.py && git add app/api/history.py && git add app/tests/test_history_repository.py && git add app/tests/test_history_api.py && git status --short && git commit -m "[Feat] round06e — 기록 목록 응답에 kind 별 total 을 싣는다. GET /api/history 가 이 브라우저·이 kind(주지 않으면 모든 kind)의 지우지 않은 기록 수를 쪽(before·limit)과 무관하게 함께 보내, 사이드바가 첫 쪽만 읽어도 '모두 보기 (N)'의 N 을 안다(spec D26·§12-3, 06d 가 그린다 — total 이 없으면 N 없이). 저장소 list 의 반환 모양은 그대로 두고 같은 조건(_live)을 쓰는 count 를 더해 API 가 둘 다 부른다. 수는 기존 부분 인덱스(session_id, kind, created_at WHERE deleted_at IS NULL)를 타고 스키마 변경은 없다. 남의 브라우저 목록이 비었는지 보는 테스트는 total 0 까지 견준다"
```

---

### Task H3 (조건부): 보고서 PDF 내보내기

> **조건:** 10/16 까지 앞 Task(A1~H2, R6 은 조건대로)가 모두 끝났을 때만 한다. 아니면 건너뛰고 완료노트 '이월'에 'PDF 내보내기(06e 마지막 Task) — 일정으로 자름(spec §12-6 자르는 순서 맨 앞)'을 적는다.

spec §12-1 처분표 'PDF 내보내기'(싸면 06e — `ReportPrint.vue` 인쇄 경로 재사용, 기본값 D21)·§12-4 'PDF(싸면)'·D21 'Word·PDF 기본 = 전부, 워터마크 없음'·정함 27. 보고서 화면(ProposalStep)의 내려받기 카드에 [PDF 로 내려받기]를 더한다. 문서는 Word 와 같은 `buildProposalDocument`(같은 입력 — Task X5 의 기본값 '모든 문단·워터마크 없음'과 '수락한 문단만' 체크)이고, 인쇄는 딥리서치 보고서가 쓰는 길 그대로다 — `useReportExport().printPdf(doc)` 가 `printDoc` 을 채우면 `<ReportPrint>` 가 body 에 붙고(Teleport), `research.css` 의 `@media print`(`body:has(> .rs-print) > :not(.rs-print)` 숨김·`@page rs-report` A4) 가 그 문서만 찍으며, 인쇄 창의 'PDF로 저장' 이 문서 제목(= `doc.fileName` 에서 `.docx` 를 뗀 것, `useReportExport.ts:30`)을 파일 이름으로 쓴다.

- **ProposalStep 이 스스로 인쇄한다(정함 27).** 자기 `useReportExport()` 에서 `printDoc`·`printPdf` 도 받고 템플릿 끝에 `<ReportPrint v-if="printDoc" :doc="printDoc" />` 를 둔다. `pages/research/[id].vue:196` 의 `<ReportPrint>` 는 딥리서치 보고서 몫(06d 영역)이라 건드리지 않는다 — 두 `useReportExport()` 는 `printDoc` 을 따로 쥐어 한 번에 하나만 body 에 붙는다. `ReportPrint.vue`·`useReportExport.ts`·`research.css` 는 고치지 않는다(import 만).
- **한 함수로 묶는다.** `downloadWord`(06b `:252-278`, Task X5 가 입력 이름·`console.warn` 글을 바꾼 것)를 `exportProposal(format: ReportExportFormat)`(`utils/reportDocument.ts:32` 의 `"docx" | "pdf"` — `[id].vue` 의 `runExport` 와 같은 형식 이름)로 갈음한다. 처음 내려받을 때의 `phase done` 처리(06b `:269-277`)는 `markDone()` 으로 떼어 두 형식이 함께 부른다. PDF 는 인쇄 창을 취소했는지 브라우저가 알려 주지 않는다 — 창이 닫히고 `printPdf` 가 오류 없이 돌아오면 내려받은 것으로 본다(단계는 앞으로만 가는 '도달' 표시라 되돌릴 일이 없다).
- **두 버튼은 한 `exporting` 으로 함께 잠근다**(`useReportExport` 의 `exportDocx`·`printPdf` 가 같은 깃발을 쓴다 — 이미 돌고 있으면 아무 일 없이 돌아오므로, `exportProposal` 이 먼저 `exporting` 을 보고 돌아가 `markDone` 이 헛돌지 않게 한다). 누른 형식은 `exportingAs` 로 기억해 '만드는 중…'·'인쇄 창을 여는 중…' 글을 누른 버튼에만 보인다.
- 실패 문구는 `[id].vue:539-543` 과 같다(Word — 배포 뒤 옛 화면의 docx 조각 파일이 사라진 경우 새로고침 안내, PDF — '인쇄 창을 열지 못했습니다. 다시 시도해 주세요.'). 성공 안내는 Word 만(`Word 문서를 내려받았습니다` — 06b 그대로) — PDF 는 인쇄 창 자체가 결과다(`[id].vue:535` 도 토스트가 없다). 그래서 내보내기를 시작할 때 앞 안내를 먼저 지운다(`act` 의 `say("")` 와 같다 — `ProposalStep.vue:171`). 06b 는 Word 한 형식이라 매번 안내를 덮어썼지만, PDF 는 성공 안내가 없어 지우지 않으면 앞선 실패 안내(`role="alert"`)가 성공 뒤에도 남는다.

**알아 둘 것:**
- **앞 Task 뒤 기준:** `ProposalStep.vue` 는 Task A5(큰 진행 막대·머리 목차·문서 자리)·Task X3(DocField)·Task X4(검토할 곳 줄)·Task X5(내보내기 카드 — 체크 `acceptedOnly`·설명 문구·`downloadWord` 입력 이름·`console.warn` 글)·Task R1(제목·문구)·Task S4(루트 `.wk-split`·패널·emits)가 먼저 고친다. 내보내기 카드(`<div class="rs-card wk-proposal__export">`)는 Task A5·Task S4 가 옮기지 않고 Task X5 가 안쪽 체크·설명만 바꾼다 — 이 Task 가 잡는 old 는 그 카드의 버튼 줄(06b `:89-93`, Task X5 가 고치지 않는 줄)과 script 의 import 두 줄(`:103` `AiFootprintMeter`·`:114` `researchErrors` — Task A5·Task S4 는 그 앞뒤에 줄을 더할 뿐 두 줄을 바꾸지 않는다. `ReportPrint` 를 `useReportExport` 위가 아니라 `AiFootprintMeter` 위에 넣는 까닭은 Task A5 가 `useReportExport` 바로 위에 `useAutoReport` 를 더해 그 자리가 composables 사이가 되기 때문이다)·`useReportExport()` 줄(`:126`)·내려받기 머리(`:244-245`, Task X5 뒤 `acceptedOnly`)·`downloadWord` 함수(Task X5 뒤 — Task S4 가 그 뒤 script 끝에 패널 묶음을 더해도 함수 블록은 그대로), 그리고 Task S4 가 둔 템플릿 루트 끝(`</DeepReadPanel>`·감싸개 `</div>`)이다. Edit 가 old 를 못 찾으면(들여쓰기가 Task A5·Task S4 로 바뀌었으면) 그 이름의 블록을 찾아 '교체 후'로 갈음하고 들여쓰기는 그 자리 그대로 둔다.
- **큰 진행 막대와 PDF(정함 28 — 10-11 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아"):** Task A5 가 보고서 화면 머리에 그리는 큰 진행 막대(`.wk-rbar`)·머리 목차·검토할 곳 줄(Task X4)·딥리드 패널(Task S4)은 PDF 에 찍히지 않는다 — `research.css` 의 `@media print` 가 `body:has(> .rs-print) > :not(.rs-print)` 로 앱 전체(`#__nuxt`)를 숨기고 body 에 붙은 `.rs-print` 만 찍는다. 그래서 이 Task 는 막대를 숨기는 인쇄 CSS 를 따로 두지 않는다. 막대가 도는 동안(자동 산출 중)에도 내려받기 버튼은 06b 의 Word 처럼 열려 있고 그때까지 쓴 절만 실린다(아직 쓰지 않은 절은 `buildProposalDocument` 의 빈 절 안내 — Task X5). 내려받기가 부르는 `markDone`(phase done)은 연쇄를 멈추지 않는다 — `autoChainOn`(Task A3)은 phase 를 보지 않는다.
- **`.vue` 는 단위 테스트하지 않는다** — 이 Task 는 판단을 새로 만들지 않는다(문서 모델은 Task X5 의 `buildProposalDocument` 가 테스트로 고정). `nuxi typecheck` 오류 0·`npm run build` 완료·vitest 수 그대로로 확인한다.
- **브라우저 확인은 배포 뒤 운영 확인(마무리 Task)에서 한다.** 로컬 미리보기를 운영 API 에 붙여(`frontend-prod-api`) [PDF 로 내려받기]를 누르면 `markDone` 이 운영 연구의 `phase` 를 `done` 으로 바꾼다 — 운영 쓰기 금지. 볼 것: 인쇄 창의 문서 제목 = 파일 이름에서 `.docx` 를 뗀 것(`보고서_<주제>_<날짜>` — Task X5 의 `proposalFileName`), 쪽마다 워터마크 없음, 본문 → AI 사용 공개 부록 → 참고문헌 순서가 Word 와 같다(`reportDocx.ts:114` 와 `ReportPrint.vue:8-25` 가 모두 blocks 다음 references), '수락한 문단만'을 켜면 검토 전 AI 작성 문단이 빠진다, 인쇄 창을 닫으면 버튼이 다시 살아난다, 자동 산출 중(큰 진행 막대가 보이는 동안)에 눌러도 인쇄 미리보기에 막대·머리 목차·버튼이 없고 그때까지 쓴 절만 있다.
- **완료노트에 남길 한계:** 마무리 Task 의 완료노트에 'PDF 는 인쇄 창을 취소해도 처음 누르면 phase done 이 된다 — `window.print()` 는 취소를 알려 주지 않는다(`useReportExport.printPdf` 는 `Promise<void>` 로 돌아온다. 06b Word 의 완료 처리를 뗀 같은 `markDone`)'를 적는다. 이 Task 를 건너뛰면(Step 1 조건) 적지 않는다 — 그때는 Step 1 의 이월 줄만 적는다.

**Files:**
- Modify: `frontend/components/work/ProposalStep.vue` (import 둘, `useReportExport()` 줄, 내려받기 머리·`exportingAs`, `downloadWord` → `exportProposal`·`markDone`, 내보내기 카드의 버튼 줄·안내 한 줄, 템플릿 루트의 마지막 자식 `<ReportPrint>`)

기준선(Task H2 뒤 — 이 계획의 앞 Task 가 모두 끝난 상태): typecheck 오류 0, 전체 vitest 실패 0(이 Task 는 수를 바꾸지 않는다), build 완료.

- [ ] **Step 1: 조건을 확인한다**

Run: `date +%F`
Expected: `2026-10-16` 이하. 그리고 이 계획의 Task A1~Task H2 체크박스가 모두 `[x]`(Task R6 은 그 Task 머리 조건대로 했거나 '건너뜀'으로 적힌 상태, Task K9 은 06c 머지를 받아 끝낸 상태)다.

둘 중 하나라도 아니면 여기서 멈추고 Step 2~5 를 하지 않는다 — 마무리 Task 의 완료노트 '이월'에 `PDF 내보내기(06e 마지막 Task) — 일정으로 자름(spec §12-6 자르는 순서 맨 앞)` 을 적고, 조건부 Task 판정 기록에 'Task H3 건너뜀(날짜·남은 Task)'을 남긴다.

- [ ] **Step 2: script — 인쇄 경로를 받고 내려받기를 한 함수로 묶는다**

`frontend/components/work/ProposalStep.vue` 의 `<script setup>` — import 둘을 더한다. 교체 전(06b `:103` — 첫 `~/components/work/` import. Task A5 가 `useReportExport` 위에 `useAutoReport` 를 더하고 Task S4 가 이 줄 아래에 부품 둘을 더해도 이 줄은 그대로 부품 import 의 맨 앞이다):

```ts
import AiFootprintMeter from "~/components/work/AiFootprintMeter.vue";
```

교체 후(import 는 경로 알파벳 순 — `components/research` 가 `components/work` 앞이다. `pages/research/[id].vue:209-226` 과 같은 순서. `components/research/*` 는 06e 가 고치지 않는다 — import 만):

```ts
import ReportPrint from "~/components/research/ReportPrint.vue";
import AiFootprintMeter from "~/components/work/AiFootprintMeter.vue";
```

교체 전(06b `:114`):

```ts
import { httpStatus, versionConflict, workErrorMessage } from "~/utils/researchErrors";
```

교체 후:

```ts
import type { ReportExportFormat } from "~/utils/reportDocument";
import { httpStatus, versionConflict, workErrorMessage } from "~/utils/researchErrors";
```

(앞 Task 가 `~/utils/researchErrors` import 줄의 이름을 바꿨으면 그 줄 바로 위에 `import type { ReportExportFormat } from "~/utils/reportDocument";` 한 줄만 넣는다.)

교체 전(06b `:126`):

```ts
const { exporting, exportDocx } = useReportExport();
```

교체 후:

```ts
// PDF 는 딥리서치 보고서와 같은 인쇄 경로다 — printDoc 이 차면 템플릿 끝의 ReportPrint 가 body 에 붙고 인쇄 창이 열린다
const { exporting, printDoc, exportDocx, printPdf } = useReportExport();
```

내려받기 머리 — 교체 전(Task X5 뒤 기준, 06b `:244-245` 에서 Task X5 가 `includeProposed` 를 `acceptedOnly` 로 바꾼 꼴):

```ts
// ── Word 내려받기 ─────────────────────────────────────────
const acceptedOnly = ref(false);
```

교체 후:

```ts
// ── 내려받기(Word·PDF) ────────────────────────────────────
const acceptedOnly = ref(false);
// 누른 형식 — 두 버튼은 한 exporting 으로 함께 잠그고, '만드는 중…' 글은 누른 버튼에만 보인다
const exportingAs = ref<ReportExportFormat | null>(null);
```

`downloadWord` — 교체 전(Task X5 뒤 기준, 06b `:252-278` 에서 Task X5 가 입력의 `includeProposed` 를 `acceptedOnly` 로, `console.warn` 글을 `"[research] 보고서 내보내기 실패"` 로 바꾼 꼴):

```ts
async function downloadWord(): Promise<void> {
  const p = proposal.value;
  const w = workView.value;
  if (!p || !w) return;
  const doc = buildProposalDocument(
    { question: props.question, url: proposalUrl(), proposal: p, work: w, acceptedOnly: acceptedOnly.value },
    new Date(),
  );
  try {
    await exportDocx(doc);
  } catch (e) {
    console.warn("[research] 보고서 내보내기 실패", e);
    // 배포 뒤 옛 화면에서 누르면 docx 조각 파일이 사라져 동적 import 가 실패한다 — 새로고침이 답이다
    say("Word 문서를 만들지 못했습니다. 새로고침한 뒤 다시 시도해 주세요.", true);
    return;
  }
  say("Word 문서를 내려받았습니다");
  // 처음 내려받으면 연구를 마친 것으로 둔다(phase done) — 단계는 앞으로만 가므로 이미 done 이면 보내지 않는다
  if (w.phase !== "proposal" || readOnly.value) return;
  try {
    props.work.setWork(await api.patchWork(props.jobId, { phase: "done" }));
    props.work.afterAction();
  } catch (e) {
    // 내려받기는 끝났다 — 단계 표시는 다음 내려받기나 새로고침에서 다시 맞춘다
    console.warn("[research] 완료 단계를 저장하지 못했습니다", e);
  }
}
```

교체 후(함수 둘 — `downloadWord` 라는 이름은 없어진다):

```ts
// Word·PDF 는 같은 문서 모델(buildProposalDocument — 같은 기본값과 '수락한 문단만' 체크)이다. PDF 는 인쇄 창의
// 'PDF로 저장' 이 문서 제목(파일 이름에서 .docx 를 뗀 것)을 파일 이름으로 쓴다(useReportExport.printPdf)
async function exportProposal(format: ReportExportFormat): Promise<void> {
  const p = proposal.value;
  const w = workView.value;
  // 이미 내보내는 중이면 exportDocx·printPdf 가 아무 일 없이 돌아온다 — 여기서 먼저 막아 markDone 이 헛돌지 않게 한다
  if (!p || !w || exporting.value) return;
  // 앞 안내를 지운다(act 와 같다) — PDF 는 성공 안내가 없어, 지우지 않으면 앞선 실패 안내가 성공 뒤에도 남는다
  say("");
  const doc = buildProposalDocument(
    { question: props.question, url: proposalUrl(), proposal: p, work: w, acceptedOnly: acceptedOnly.value },
    new Date(),
  );
  exportingAs.value = format;
  try {
    if (format === "docx") await exportDocx(doc);
    else await printPdf(doc);
  } catch (e) {
    console.warn("[research] 보고서 내보내기 실패", e);
    // 배포 뒤 옛 화면에서 누르면 docx 조각 파일이 사라져 동적 import 가 실패한다 — 새로고침이 답이다
    say(
      format === "docx"
        ? "Word 문서를 만들지 못했습니다. 새로고침한 뒤 다시 시도해 주세요."
        : "인쇄 창을 열지 못했습니다. 다시 시도해 주세요.",
      true,
    );
    return;
  } finally {
    exportingAs.value = null;
  }
  // PDF 는 인쇄 창 자체가 결과다 — 딥리서치 보고서의 PDF 도 안내를 띄우지 않는다
  if (format === "docx") say("Word 문서를 내려받았습니다");
  await markDone();
}

// 처음 내려받으면 연구를 마친 것으로 둔다(phase done) — 단계는 앞으로만 가므로 이미 done 이면 보내지 않는다.
// PDF 는 인쇄 창을 취소했는지 브라우저가 알려 주지 않아, 창이 닫히고 오류 없이 돌아오면 내려받은 것으로 본다
async function markDone(): Promise<void> {
  const w = workView.value;
  if (!w || w.phase !== "proposal" || readOnly.value) return;
  try {
    props.work.setWork(await api.patchWork(props.jobId, { phase: "done" }));
    props.work.afterAction();
  } catch (e) {
    // 내려받기는 끝났다 — 단계 표시는 다음 내려받기나 새로고침에서 다시 맞춘다
    console.warn("[research] 완료 단계를 저장하지 못했습니다", e);
  }
}
```

- [ ] **Step 3: 템플릿 — 버튼 줄과 인쇄 문서를 더한다**

내보내기 카드(`<div class="rs-card wk-proposal__export">`)의 버튼 줄 — 교체 전(06b `:89-93`, Task X5 는 이 줄을 고치지 않는다):

```vue
          <div class="rs-card__actions">
            <button type="button" class="rs-btn" :disabled="exporting" @click="downloadWord">
              {{ exporting ? "만드는 중…" : "Word 로 내려받기" }}
            </button>
          </div>
```

교체 후(들여쓰기는 그 자리 그대로):

```vue
          <div class="rs-card__actions">
            <button type="button" class="rs-btn" :disabled="exporting" @click="exportProposal('docx')">
              {{ exportingAs === "docx" ? "만드는 중…" : "Word 로 내려받기" }}
            </button>
            <button type="button" class="rs-btn rs-btn--ghost" :disabled="exporting" @click="exportProposal('pdf')">
              {{ exportingAs === "pdf" ? "인쇄 창을 여는 중…" : "PDF 로 내려받기" }}
            </button>
          </div>
          <p class="rs-muted">PDF 는 인쇄 창에서 대상을 ‘PDF로 저장’으로 고릅니다. Word 와 같은 문서·같은 기본값입니다.</p>
```

템플릿 루트(Task S4 뒤 `<div class="wk-split">`)의 **마지막 자식**으로 인쇄 문서를 더한다 — Task S4 가 루트 끝에 둔 `</DeepReadPanel>` 과 감싸개의 닫는 `</div>` 사이. 교체 전(Task S4 뒤 기준 — Task S4 는 감싸개·`<section>`·`<DeepReadPanel>` 을 모두 두 칸에 세운다):

```vue
  </DeepReadPanel>
  </div>
</template>
```

교체 후(루트의 다른 자식과 같은 두 칸):

```vue
  </DeepReadPanel>
  <!-- PDF 내려받기(인쇄) 동안에만 body 에 붙는 인쇄 전용 문서(Teleport) — 화면에는 그리지 않는다(research.css .rs-print) -->
  <ReportPrint v-if="printDoc" :doc="printDoc" />
  </div>
</template>
```

(주석에는 버튼 이름을 적지 않는다 — Task Z4 의 dev 머지 점검 ④ 가 `grep -c "PDF 로 내려받기"` 를 `1`(이 Task 를 했다)·`0`(건너뜀)으로만 판정한다. 아래 Step 끝에서 그 수를 잰다.)

(Task S4 가 루트 끝을 다르게 적었으면 루트의 닫는 태그 바로 위에 가운데 두 줄만 넣는다 — 들여쓰기는 루트의 다른 자식과 같게. `<ReportPrint>` 는 Teleport 로 body 에 붙으므로 루트 안 어느 자리에 두어도 화면 배치(`.wk-split` 2단)에 끼지 않는다.)

`downloadWord` 를 부르는 곳이 남지 않았는지 본다:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -n "downloadWord\|includeProposed" components/work/ProposalStep.vue`
Expected: 빈 출력

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -c "<ReportPrint" components/work/ProposalStep.vue`
Expected: `1`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && grep -c "PDF 로 내려받기" components/work/ProposalStep.vue`
Expected: `1`(버튼 글 한 줄 — Task Z4 의 dev 머지 점검 ④ 가 이 수로 이 Task 를 했는지 가른다. `2` 면 주석·안내 글에 버튼 이름이 들어간 것이니 그 줄에서 이름을 뺀다)

- [ ] **Step 4: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0`(`printDoc` 은 `ShallowRef<ReportDoc | null>` — `v-if` 가 좁혀 `:doc` 이 `ReportDoc` 이다. `[id].vue:196` 과 같은 꼴. 계획 작성 때 06b 의 `ProposalStep.vue` 에 Task X5 의 이름 바꾸기(`includeProposed` → `acceptedOnly`·`console.warn` 글)만 흉내 내고 이 Task 의 Step 2·3 을 그대로 얹은 통합 사본에서 `ProposalStep.vue` 의 오류 0·`npm run build` 완료를 확인했다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run`
Expected: 실패 0 — `Test Files` / `Tests` 가 Task H3 앞과 같은 수(이 Task 는 테스트를 더하지 않는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff --stat -- frontend/components/research/ReportPrint.vue frontend/composables/useReportExport.ts frontend/assets/css/research.css "frontend/pages/research/[id].vue" frontend/utils/reportDocument.ts frontend/utils/reportDocx.ts`
Expected: 빈 출력(인쇄 경로는 재사용만 — 이 Task 는 `ProposalStep.vue` 한 파일)

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add frontend/components/work/ProposalStep.vue && git status --short && git commit -m "[Feat] round06e 프론트 — 보고서를 PDF 로도 내려받는다. 내려받기 카드에 [PDF 로 내려받기]를 더하고, 문서는 Word 와 같은 buildProposalDocument(기본 모든 문단·워터마크 없음, '수락한 문단만' 체크 그대로)로 만들어 딥리서치 보고서와 같은 인쇄 경로(useReportExport.printPdf → body 에 붙는 ReportPrint)로 찍는다 — 인쇄 창의 'PDF로 저장'이 문서 제목(파일 이름에서 .docx 를 뗀 것)을 파일 이름으로 쓴다. 보고서 화면이 자기 인쇄 문서를 쥐어 연구 화면의 ReportPrint(딥리서치 몫)는 건드리지 않는다. Word·PDF 를 한 함수(exportProposal)로 묶고 처음 내려받을 때 연구를 완료로 두는 처리(markDone)를 두 형식이 함께 쓴다 — PDF 는 인쇄 창을 닫고 돌아오면 내려받은 것으로 본다. 두 버튼은 한 깃발로 함께 잠그고 진행 글은 누른 버튼에만 보인다(spec §12-4 PDF·D21)"
```

---

## 파트 메모 — 뼈대와 다른 점

1. **Task H1 — describe `evidenceChips` 의 둘째 it 는 고치지 않는다.** 뼈대는 describe 전체를 ✎ 로 적었지만, 둘째 it(`저자를 모르면 제목 앞부분(짧으면 그대로), 서지가 없으면 cnts_id 로 가른다`)의 기대(`지지망 분석`·`KCI_Z` — 라벨·툴팁 모두)는 새 규칙에서도 같아 그대로 통과한다. 첫 it 만 ✎ 하고 18자 경계(18자 그대로·19자 말줄임)와 `SHORT_TITLE_MAX` 값을 그 it 에 함께 고정했다. 새 it 둘의 이름은 뼈대 그대로(`복성·외 n인·영문 이름·연도 없음`·`툴팁은 서지 한 줄`).
2. **Task H1 — 툴팁의 저자 칸은 `splitAuthors(...).join(", ")` 이다.** 뼈대는 `[제목, 저자, 학술지, 연도]` 만 적었다. 원문 `personal_author` 를 그대로 쓰면 `김철수; 이영희`·`윤기찬 | 이순철` 처럼 원본 구분자가 보여 칩 라벨·참고문헌(06b 정함 8 — 같은 `splitAuthors` 구분)과 어긋나므로 나눠서 쉼표로 이었다. 짧은 제목은 자른 끝의 공백을 떼고 `…` 를 붙인다(18번째 글자가 공백인 제목이 '… 미치는 …' 가 되지 않게) — 뼈대의 '제목 앞 18자(넘으면 `…`)'를 그렇게 읽었다. 저자도 제목도 없으면 연도가 있어도 `cntsId` 다(연도만 있는 칩은 가를 수 없다).
3. **Task H2 — 기존 테스트 하나를 ✎ 한다(뼈대 목록에 없음).** `test_history_api.py` 의 `TestOwnership.test_other_browser_list_is_empty`(`:138-139`)가 응답 dict 전체를 견주어(`{"items": [], "next_cursor": None}`) `total` 이 붙으면 깨진다 — 기대에 `"total": 0` 을 더했다. 새 테스트 셋(저장소 둘·API 하나)의 이름은 뼈대 그대로다.
4. **Task H2 — `list` 의 where 를 모듈 함수 `_live(session_id, kind)` 로 뺐다.** 뼈대는 `count` 를 '같은 where' 로 새로 쓰라고 했다. 두 곳에 같은 조건을 따로 적으면 한쪽만 바뀔 수 있어 한 함수로 묶었다 — `list` 의 동작·반환 모양(2-튜플)은 그대로이고 기존 테스트 59개가 그대로 통과한다(통합 사본 실측).
5. **Task H3 — `downloadWord` 를 `exportProposal(format: ReportExportFormat)` 와 `markDone()` 으로 갈음하고 `exportingAs` ref 를 더했다.** 뼈대의 '처음 내려받기의 phase done 처리는 Word 와 같은 함수로 묶는다'를 이렇게 구현했다. 형식 타입은 새로 만들지 않고 `utils/reportDocument.ts:32` 의 `ReportExportFormat` 을 쓴다(한 이름 한 파일). PDF 는 인쇄 창 취소를 알 수 없어 창이 닫히면 완료로 둔다 — 완료노트에 적는다(Task H3 '알아 둘 것'의 '완료노트에 남길 한계'). 버튼 이름은 뼈대 그대로 `PDF 로 내려받기` 이고, 딥리서치 내려받기 메뉴(`ReportDownloadMenu.vue:47`)와 같은 뜻의 안내 한 줄(‘PDF로 저장’으로 고른다)을 더했다.

---

### Task Z1: K1 측정 결과 반영 — 논문 키워드 채움률(사용자 서버 실행)·상수 판정

**왜:** spec §12-4 '논문 키워드 채움률은 착수 전에 한 번 잰다(1회성)'·§12-11 '키워드 후보 원천'(정함 14). Task K2 는 기본값 `PAPER_KEYWORD_MIN_N = 1` 로 구현했다 — 운영 DB 의 실제 채움률로 1(논문에만 있는 후보도 1편부터)인지 2(보조 — 2편 이상 겹친 것만)인지 정하고, 목록 키워드 원문의 구분자가 `split_catalog_keywords` 의 가정(`[;,]` + 앞뒤 공백)과 맞는지 본다. 측정은 읽기 전용 SELECT 지만 운영 DB 는 서버에만 있고 `research/` 는 앱 이미지에 없어(함정 4) **사용자가** 돌린다. Task K1 을 커밋한 뒤 언제든 맡길 수 있다 — 결과 커밋은 Task Z2 의 회귀 전에 넣는다.

**Files:**
- Create: `research/round06e-keyword-candidates/out/fill_rate.md`(서버 출력 그대로)
- Modify: `research/round06e-keyword-candidates/README.md`('결과' 칸 — Task K1 이 만든 자리)
- Modify(판정이 2 일 때만): `app/services/research_work/keywords.py`(`PAPER_KEYWORD_MIN_N` 한 줄), `app/tests/test_research_work_keywords.py`
- Modify(구분자가 다를 때만): `app/services/research_work/keywords.py`(`split_catalog_keywords` 의 구분 정규식), `app/tests/test_research_work_keywords.py`

**알아 둘 것:**
- 실행 절차의 정본은 Task K1 이 쓴 `research/round06e-keyword-candidates/README.md` 의 '실행' 절이다. 아래 명령은 그 절차(`/app/data/` 바인드 마운트 + `-e PYTHONPATH=/app` — 함정 4)의 꼴이고, README 의 경로·인자가 다르면 README 를 따른다.
- **판정 규칙(정함 14):** ② '최근 이어간 연구 20건(예시·지운 연구 뺌)의 채택 논문(`research_reading.origin = 'evidence'`) 중 키워드가 하나라도 있는 비율' ≥ 50% → `PAPER_KEYWORD_MIN_N = 1`, < 50% → `2` — 스크립트가 ② 표 아래에 판정 줄(`판정: 비율 n% — 기준 50% 이상|미만 → PAPER_KEYWORD_MIN_N = 1|2`)을 찍는다. ① 전체 논문 채움률과 ④ 연구별 서로 다른 키워드 수(1편 이상·2편 이상)는 참고값이다(시연·실사용은 최근 이어간 연구가 대상이다 — '최근 20건'은 표본이 아니라 대상 정의라 `ORDER BY created_at DESC LIMIT 20` 그대로 둔다). ③ 653 원문 표본 20개(`ORDER BY random() LIMIT 20` — 함정 11)로 구분자를 본다. DB 주소는 컨테이너 env 로 만든 `DATABASE_URL_SYNC`(psycopg2 — `DATABASE_URL` 은 asyncpg URL 이라 동기 엔진에 못 쓴다), 트랜잭션은 `READ ONLY`·`statement_timeout` 120초다(Task K1).
- 출력은 운영 데이터의 집계와 키워드 원문 표본이다 — 저장소에 들이기 전에 그 밖의 것(논문 제목·저자·초록)이 섞이지 않았는지 본다.

- [ ] **Step 1: (개발 PC) dry-run 으로 SQL 을 다시 본다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && python -I research/round06e-keyword-candidates/measure.py --dry-run`

Expected: SQL 네 덩이(머리 줄 `-- ①` ~ `-- ④`)만 찍히고 DB 에 붙지 않는다(`--dry-run` 은 엔진을 만들기 전에 끝난다 — `core.config` 도 읽지 않는다). 눈으로 확인한다 — ①·② 의 '키워드 있음' 조건이 `(lc.keyword IS NOT NULL AND btrim(lc.keyword) <> '')` 와 `(CASE WHEN jsonb_typeof(lc.extra->'keywords') = 'array' THEN jsonb_array_length(lc.extra->'keywords') ELSE 0 END > 0)` 의 OR 이고 jsonb `?` 를 쓰지 않는다(함정 10), ② 가 `research_works` 의 `deleted_at IS NULL AND is_example = false` 를 `ORDER BY created_at DESC LIMIT 20` 으로 고른 뒤 `research_reading` 의 `origin = 'evidence'` 를 센다, ③ 이 `ORDER BY random() LIMIT 20` 이다(함정 11). 다르면 Task K1 으로 돌아가 고친 뒤 이 Step 부터 다시.

- [ ] **Step 2: (사용자, 서버) 측정 스크립트를 돌린다**

개발 PC 의 `research/round06e-keyword-candidates/measure.py` 를 평소 쓰는 방법(scp 등)으로 서버 일반 계정 홈의 `round06e/` 아래로 올린 뒤:

```bash
su - root                                                                              # /data/nl-lib/data 아래는 root 소유다
H=$(getent passwd "$(logname)" | cut -d: -f6)/round06e; ls -d "$H"                    # logname 이 실패하면 H=/home/계정이름/round06e 를 직접 넣는다
mkdir -p /data/nl-lib/data/round06e-keyword-candidates/out
cp $H/measure.py /data/nl-lib/data/round06e-keyword-candidates/
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06e-keyword-candidates/measure.py > /data/nl-lib/data/round06e-keyword-candidates/out/fill_rate.md
echo "exit=$?"; wc -l /data/nl-lib/data/round06e-keyword-candidates/out/fill_rate.md
cat /data/nl-lib/data/round06e-keyword-candidates/out/fill_rate.md
```

Expected: `exit=0`, 머리 `# round06e 논문 키워드 채움률` 과 markdown 표 넷 — ① `doc_type='paper'` 전체의 논문 수·653 키워드·추출 키워드·둘 중 하나·비율 ② 최근 이어간 연구 20건의 연구별 채택 논문·키워드 있음·비율과 합계 줄, 그 아래 판정 줄(`판정: 비율 … → PAPER_KEYWORD_MIN_N = 1` 또는 `2`, 채택 논문이 없으면 '기본값 … = 1 그대로') ③ `cnts_id`·`keyword` 원문 표본 20줄 ④ 연구별 서로 다른 키워드 수(1편 이상·2편 이상). Traceback 이 나오면(`ModuleNotFoundError: No module named 'core'` 는 `-e PYTHONPATH=/app` 를 빠뜨린 것 — 함정 4) 그 줄을 개발 PC 로 가져와 Task K1 으로 돌아간다. `fill_rate.md` 를 개발 PC 의 `C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/research/round06e-keyword-candidates/out/fill_rate.md` 로 가져온다(scp 또는 붙여 넣기 — 줄바꿈은 그대로).

- [ ] **Step 3: 판정하고 README '결과'에 적는다 (Edit 도구)**

`research/round06e-keyword-candidates/README.md` 의 '결과' 칸에 다음을 적는다(값은 `out/fill_rate.md` 그대로): 측정 날짜·실행한 사람(사용자), ① 비율, ② 합계 줄의 비율·채택 논문 수·판정 줄, ④ 의 1편 이상·2편 이상 키워드 수 범위 한 줄(참고), ③ 에서 본 구분자(예: `;` 만 · `;` 와 `,` · 그 밖에 `|`), **판정** — `PAPER_KEYWORD_MIN_N = <1|2>`(② 판정 줄 그대로 — 50% 이상/미만), 구분자 — '가정과 같다' 또는 '`<글자>` 를 더한다'.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -c "PAPER_KEYWORD_MIN_N = [12]" research/round06e-keyword-candidates/README.md`

Expected: `1` 이상(판정 줄이 있다).

- [ ] **Step 4: (판정이 2 일 때만) 상수를 바꾼다 — 실패 테스트 먼저**

`app/tests/test_research_work_keywords.py` 끝에 다음을 더한다:

```python
def test_the_default_min_n_follows_the_k1_measurement():
    # research/round06e-keyword-candidates/README.md '결과' — 최근 이어간 연구의 채택 논문 키워드 채움률이
    # 50% 미만이라 논문에만 있는 후보는 두 편 이상 겹친 것만 싣는다(정함 14)
    from services.research_work import keywords

    assert keywords.PAPER_KEYWORD_MIN_N == 2
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_keywords.py -q -p no:cacheprovider`

Expected: `1 failed` — `assert 1 == 2`(나머지는 통과).

`app/services/research_work/keywords.py` 의 `PAPER_KEYWORD_MIN_N = 1` 줄(Task K2 가 단 줄 끝 주석이 있으면 그 주석까지 한 줄 전체를 old 로)을 `PAPER_KEYWORD_MIN_N = 2` 로 Edit 하고, 줄 끝 주석이 있었으면 `# K1 측정 — 최근 연구 채택 논문 채움률 < 50%(README '결과')` 로 바꾼다. 다시 돌린다.

Expected: 새 테스트는 통과한다. 다른 테스트가 실패하면 그 테스트가 기본값 1(논문에만 있는 1편짜리 후보가 남는다)을 전제한 것이다 — 그 테스트의 인자에 `monkeypatch` 를 더하고 첫 줄에 `monkeypatch.setattr("services.research_work.keywords.PAPER_KEYWORD_MIN_N", 1)` 을 넣어 규칙만 보게 한다(Task K2 의 'MIN_N 아래 논문 후보는 버린다' 테스트가 2 를 끼우는 것과 같은 꼴). 그 뒤 `<Task K2 뒤 수 + 1> passed`.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_keywords.py tests/test_research_work_concepts.py tests/test_research_work_api.py -q -p no:cacheprovider`

Expected: 실패 0(`test_research_work_api.py` 의 이어가기 테스트는 논문 키워드를 `add_book(…, keyword=…)` 로 넣는다 — 기대가 1편짜리 논문 후보에 기대면 그 테스트도 위와 같이 고친다).

- [ ] **Step 5: (구분자가 다를 때만) `split_catalog_keywords` 에 구분자를 더한다 — 실패 테스트 먼저**

③ 에서 본 새 구분자를 `S` 라 하자(예: `|`). `app/tests/test_research_work_keywords.py` 끝에 다음을 더한다(`|` 자리에 실제 글자):

```python
def test_the_separator_seen_in_the_k1_sample_is_split_too():
    # research/round06e-keyword-candidates/out/fill_rate.md ③ — 운영 목록 키워드에 이 구분자가 있다
    from services.research_work.keywords import split_catalog_keywords

    assert split_catalog_keywords("노인 우울 | 사회적 지지") == ["노인 우울", "사회적 지지"]
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_keywords.py -q -p no:cacheprovider`

Expected: `1 failed` — 한 덩이로 남은 `['노인 우울 | 사회적 지지']`.

`keywords.py` 의 `split_catalog_keywords` 가 쓰는 구분 정규식(Task K2 의 `[;,]` 문자 집합)에 그 글자를 더한다(예: `[;,|]` — 정규식 특수 글자는 문자 집합 안이라 그대로 된다). 다시 돌린다.

Expected: 실패 0 — `<앞 수 + 1> passed`.

- [ ] **Step 6: 커밋한다**

판정 1·구분자 같음(코드 그대로):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add research/round06e-keyword-candidates/out/fill_rate.md && git add research/round06e-keyword-candidates/README.md && git status --short && git commit -m "[Docs] round06e — 논문 키워드 채움률 측정 결과(운영 서버, 읽기 전용): 최근 이어간 연구 20건의 채택 논문 중 키워드가 있는 비율이 50% 이상이라 PAPER_KEYWORD_MIN_N 은 1 그대로(정함 14), 목록 키워드 구분자는 가정(; ,)과 같다"
```

판정 2 또는 구분자를 더했으면 코드·테스트도 함께(메시지는 한 일만 남긴다):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add research/round06e-keyword-candidates/out/fill_rate.md && git add research/round06e-keyword-candidates/README.md && git add app/services/research_work/keywords.py && git add app/tests/test_research_work_keywords.py && git status --short && git commit -m "[Feat] round06e — 논문 키워드 채움률 측정(운영 서버, 읽기 전용)에 따라 키워드 후보 규칙을 정한다: 최근 이어간 연구의 채택 논문 키워드 채움률이 50% 미만이라 PAPER_KEYWORD_MIN_N 을 2 로 — 논문에만 있는 후보는 두 편 이상 겹친 것만 싣는다(정함 14). 기본값 1 을 전제한 테스트는 규칙만 보게 값을 끼운다"
```

(구분자만 더했으면 메시지를 `[Feat] round06e — 논문 키워드 채움률 측정(운영 서버, 읽기 전용) 결과를 넣고 목록 키워드 구분자에 '<글자>' 를 더한다 — 운영 표본에 그 구분자로 이은 키워드가 있다. PAPER_KEYWORD_MIN_N 은 <1|2>` 로 쓴다 — 꺾쇠는 실측값으로 바꾼다.)

Expected: 커밋 1개, `git status --short` 에 고른 파일만.

---

### Task Z2: 전체 회귀·경계 확인·영역별 정적 리뷰·반영

**왜:** 파트 A·X·R·S·K·H 와 Task Z1 을 마친 브랜치를 dev 에 넣기 전에 한 번에 회귀를 보고, 이 줄이 손대지 말아야 할 곳(06c·06d 파일·딥리서치 코드·`[id].vue` 의 06d 자리·근거 장부 블록·`citations.ts`·스키마)이 그대로인지 확인하고, 영역별 정적 리뷰(`.claude/agents/code-reviewer.md`)로 이 줄의 위험(JSONB 만·프롬프트 예시 금지·실패 타입·연쇄가 조건 밖에서 쓰지 않음·한 이름 한 파일·선택 필드·접근성·reduced-motion·토큰)을 본다(GIT_WORKFLOW — 리뷰 뒤 dev 머지). 리뷰 반영도 이 Task 안에서 끝내고 '리뷰를 마친 커밋'을 적는다 — 완료노트·dev 머지가 이 커밋을 가리킨다.

**Files:**
- Modify: 리뷰 발견을 고치는 파일(발견에 따라 — 판단을 고치면 그 순수 함수·백엔드 함수의 실패 테스트를 먼저 쓰고 고친다)
- 저장소 밖 작업 폴더: `C:/Users/LANDSOFT/round06e-eval/review/`(리뷰어에게 줄 diff — 저장소에 넣지 않는다)

**알아 둘 것:**
- Task K9·R6 이 06c·06d 를 기다리는 중이면 이 Task 를 그 전에 먼저 돌려도 된다 — 그때는 K9(·R6) 뒤 Step 1·2 를 다시 돌리고, 그 Task 의 diff 만 해당 영역 리뷰어에게 다시 보인다(Step 5 의 되풀이 규칙).
- code-reviewer 는 읽기 전용(Read·Grep·Glob)이라 git 을 돌리지 못한다 — 영역 diff 를 파일로 떠서 경로를 준다.
- `BASE=$(git merge-base HEAD dev)` 는 마지막으로 받은 dev 다 — K9·R6 이 dev 를 받았으면 그 커밋이고, `git diff $BASE HEAD` 는 06e 자신의 변경만 보인다.
- 리뷰 반영 커밋도 `[Fix] round06e — …` 처럼 Co-Authored-By 없이 쓴다. 발견을 거절할 때는 까닭을 완료노트 §3 에 적는다(Task Z3).

- [ ] **Step 1: 전체 회귀**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_work_outline.py tests/test_research_proposal_api.py tests/test_research_work_section_input.py tests/test_research_work_enqueue.py tests/test_research_work_markers.py tests/test_research_work_paragraph_edit.py tests/test_prompts.py tests/test_research_work_concepts.py tests/test_research_work_api.py tests/test_research_work_views.py tests/test_research_work_seeds.py tests/test_research_work_topic_card.py tests/test_research_topics_api.py tests/test_research_work_dispatch.py tests/test_research_work_generate.py tests/test_research_work_executor.py tests/test_research_work_tasks.py tests/test_history_repository.py tests/test_history_api.py tests/test_embed_index_guard.py tests/test_research_work_models.py tests/test_research_work_keywords.py tests/test_book_chat_prompt.py -q -p no:cacheprovider
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/app && python -m pytest tests/test_research_terms.py tests/test_research_eval.py -q -p no:cacheprovider
```

Expected:
- 백엔드 전체 — `5 failed, N passed, 1 skipped, 2 warnings, 1 error`. 실패 5·오류 1 은 Task 0 기준선과 같은 여섯 줄(test_build_manifest 2·test_loaders 3·test_book_chat 수집 — **Task S2 의 대역이 `test_book_chat.py` 수집 오류를 바꾸지 않았다**: 대역은 `test_book_chat_prompt.py` 의 fixture 안에서만 끼우고 되돌린다). N 은 계획 순서상 마지막으로 끝낸 백엔드 Task(K9, Task Z1 이 테스트를 더했으면 Z1)의 '통과 확인' 수와 같다(= Task 0 의 기준선 + 파트가 더한 수 +133('각 Task 의 기대 수' 합) + K9·R6 이 dev 에서 받은 06c·06d 백엔드 테스트 수). 다르면 Task 별 '통과 확인' 명령으로 어느 파일의 수가 다른지 센다. 그 밖의 실패가 있고 06e 파일이 아니면 받은 dev 의 것이다 — 멈추고 사용자와 그 줄의 세션에 알린다. 나온 N 을 적어 둔다(완료노트 §4)
- 06e 백엔드 묶음 스물세 파일 — 실패 0. 계획 값은 Task 0 의 `744` + 파트가 더한 +133 = `877 passed`(06c·06d 를 받아도 이 묶음은 그 줄이 고치지 않아 같다) — 다르면 Task 별 '통과 확인' 명령으로 어느 파일이 다른지 센다. `test_embed_index_guard.py` 의 6 개가 그대로 통과한다(대역이 새지 않았다). 나온 수를 적어 둔다
- 06c 의 두 파일 — 실패 0(06e 가 `terms.py`·`term_checks.json` 을 고치지 않았다). 06c 가 dev 에 없던 때 이 Task 를 먼저 돌리면 `file or directory not found` — K9 뒤 다시 돌린다

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx nuxi typecheck 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/proposalView.test.ts tests/unit/workPhase.test.ts tests/unit/outlineEdit.test.ts tests/unit/proposalDocument.test.ts tests/unit/readingList.test.ts tests/unit/topicDeck.test.ts tests/unit/workEvents.test.ts tests/unit/citations.test.ts tests/unit/reportDocx.test.ts tests/unit/reportDocument.test.ts tests/unit/useResearchWork.test.ts tests/unit/useReadingSaves.test.ts tests/unit/pdfViewer.test.ts tests/unit/useAutoReport.test.ts tests/unit/deepReadSse.test.ts tests/unit/useDeepReadChat.test.ts tests/unit/deepRead.test.ts tests/unit/citationEvidence.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npx vitest run tests/unit/citations.test.ts tests/unit/reportDocument.test.ts tests/unit/reportDocx.test.ts
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | grep -c "Duplicated imports"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && npm run build 2>&1 | tail -1
```

Expected:
- typecheck 오류 `0` · `Duplicated imports` — Task 0 Step 5 에서 적은 값과 같다(`2`, 또는 06d 를 받았으면 `0`). 늘었으면 새 이름 하나를 두 파일이 내보낸 것이다(한 이름 한 파일 — 공통 계약 1-6)
- vitest 전체 — 실패 0. `Test Files` 는 기준선 파일 수 + 5, `Tests` 는 계획 순서상 마지막으로 끝낸 프론트 Task(K9 의 프론트 it, R6·H3 은 +0)의 '통과 확인' 수와 같다(= Task 0 의 기준선 + 파트가 더한 수 +110('각 Task 의 기대 수' 합 — 06c·06d 를 받지 않았으면 `Tests  842 passed (842)`) + K9·R6 이 dev 에서 받은 06c·06d 프론트 테스트 수). 다르면 Task 별 '통과 확인' 명령으로 센다
- 06e 프론트 묶음 열여덟 파일 — 실패 0. 계획 값은 Task 0 의 열세 파일 `221` + 파트가 더한 +110 = `Test Files  18 passed (18)` / `Tests  331 passed (331)` — Task K9 의 9 는 06c `term_checks.json` 의 contains 사례 수를 따르므로 06c 가 사례를 더 두었으면 그만큼 크다. 나온 수를 적어 둔다(완료노트 §4)
- 그대로여야 하는 셋 — `Tests  49 passed (49)`(`citations` 18 + `reportDocument` 27 + `reportDocx` 4 — Task 0 과 같다: Q3 S, 딥리서치 보고서 내보내기 불변)
- build 의 `Duplicated imports` 는 typecheck 와 같은 값, 마지막 줄 `└  ✨ Build complete!`

- [ ] **Step 2: 경계 — 고친 파일·고치지 않을 파일·06d 자리·장부 블록·프롬프트·커밋 트레일러**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e
BASE=$(git merge-base HEAD dev); echo "$BASE"
git diff --name-only $BASE HEAD -- app frontend research scripts infra | LC_ALL=C sort
git diff --stat $BASE HEAD -- app/services/research app/workers app/alembic app/api/research.py app/api/research_reading.py app/models/research.py app/domains/nl_library/prompts/research_plan.yaml app/domains/nl_library/prompts/research_critique.yaml app/domains/nl_library/prompts/research_critique_question.yaml app/domains/nl_library/prompts/research_synthesize.yaml app/domains/nl_library/prompts/book_chat.yaml docker-compose.yml docker-compose.dev.yml infra frontend/package.json frontend/package-lock.json frontend/components/research frontend/assets/css/research.css frontend/assets/css/style_skovix.css frontend/components/work/EvidenceLedger.vue frontend/utils/evidenceLedger.ts frontend/utils/citations.ts frontend/utils/researchEvents.ts frontend/utils/researchErrors.ts frontend/types/research.ts frontend/types/history.ts frontend/utils/historyStore.ts frontend/composables/useReportExport.ts frontend/components/AppSidebar.vue frontend/pages/index.vue frontend/tests/fixtures/term_checks.json frontend/tests/fixtures/marker_checks.json frontend/tests/unit/citations.test.ts
git diff -U0 $BASE HEAD -- "frontend/pages/research/[id].vue" | grep -E '^[-+][^-+]' | grep -vE 'ReadingStep|ProposalStep|workPanelOpen|^\+\s*//|skx-app|AppSidebar|보고서 보기'
git diff -U0 $BASE HEAD -- frontend/pages/papers/index.vue "frontend/pages/papers/[id].vue" | grep -E '^[-+][^-+]' | grep -c 'doc-kind="paper"'
git diff -U0 $BASE HEAD -- frontend/pages/papers/index.vue "frontend/pages/papers/[id].vue" | grep -E '^[-+][^-+]' | grep -vc 'doc-kind="paper"'
diff <(git show $BASE:frontend/assets/css/work.css | sed -n '/근거 장부(EvidenceLedger)/,/진행 막대(WorkStepper)/p') <(sed -n '/근거 장부(EvidenceLedger)/,/진행 막대(WorkStepper)/p' frontend/assets/css/work.css) && echo "장부 블록 1 그대로"
diff <(git show $BASE:frontend/assets/css/work.css | sed -n '/진행 패널 아래 근거 장부/,/^}/p') <(sed -n '/진행 패널 아래 근거 장부/,/^}/p' frontend/assets/css/work.css) && echo "장부 블록 2 그대로"
git diff -U0 $BASE HEAD -- frontend/assets/css/work.css | grep -c '^-[^-]'
git diff $BASE HEAD -- frontend/assets/css/work.css | grep '^+' | grep -cE "#[0-9a-fA-F]{3,6}\b|rgba?\("
git diff $BASE HEAD -- app/domains/nl_library/prompts | grep '^+' | grep -cE '예시|예:|예를'
git log $BASE..HEAD --format=%B | grep -ciE "Co-Authored-By|Generated with Claude Code"
git status --short
```

Expected:
- `BASE` — Task 0 Step 2 의 dev 커밋, 또는 K9·R6 이 받은 dev 커밋
- 고친 파일 목록 — 정확히 다음 줄들(이 계획서를 브랜치에 커밋했으면 `docs/` 라 이 목록에 들지 않는다). 리뷰 반영으로 더한 파일이 있으면 그 파일과 까닭을 완료노트 §3 에 적는다

```text
app/api/history.py
app/api/research_proposal.py
app/api/research_topics.py
app/api/research_work.py
app/domains/nl_library/prompts/book_chat.paper.yaml
app/domains/nl_library/prompts/research_concepts.yaml
app/domains/nl_library/prompts/research_topic_card.yaml
app/models/research_work.py
app/repositories/history.py
app/schemas/book.py
app/schemas/history.py
app/scripts/verify_prompt_parity.py
app/services/chat/book_chat.py
app/services/research_work/apply.py
app/services/research_work/concepts.py
app/services/research_work/generate.py
app/services/research_work/keywords.py
app/services/research_work/markers.py
app/services/research_work/outline.py
app/services/research_work/progress.py
app/services/research_work/proposal_views.py
app/services/research_work/section_input.py
app/services/research_work/seeds.py
app/services/research_work/shapes.py
app/services/research_work/topic_card.py
app/services/research_work/views.py
app/tests/test_book_chat_prompt.py
app/tests/test_history_api.py
app/tests/test_history_repository.py
app/tests/test_prompts.py
app/tests/test_research_proposal_api.py
app/tests/test_research_topics_api.py
app/tests/test_research_work_api.py
app/tests/test_research_work_concepts.py
app/tests/test_research_work_dispatch.py
app/tests/test_research_work_enqueue.py
app/tests/test_research_work_executor.py
app/tests/test_research_work_generate.py
app/tests/test_research_work_keywords.py
app/tests/test_research_work_markers.py
app/tests/test_research_work_outline.py
app/tests/test_research_work_paragraph_edit.py
app/tests/test_research_work_section_input.py
app/tests/test_research_work_seeds.py
app/tests/test_research_work_tasks.py
app/tests/test_research_work_topic_card.py
app/tests/test_research_work_views.py
frontend/assets/css/work.css
frontend/components/BookChat.vue
frontend/components/work/CandidateDrawer.vue
frontend/components/work/CitationSource.vue
frontend/components/work/ConceptChips.vue
frontend/components/work/DeepReadPanel.vue
frontend/components/work/DocField.vue
frontend/components/work/FunnelCounter.vue
frontend/components/work/OnboardingModal.vue
frontend/components/work/OutlineEditor.vue
frontend/components/work/ProposalSection.vue
frontend/components/work/ProposalStep.vue
frontend/components/work/ReadingStep.vue
frontend/components/work/ReadingTable.vue
frontend/components/work/TopicCard.vue
frontend/components/work/TopicDeck.vue
frontend/components/work/TopicsStep.vue
frontend/components/work/WorkStepper.vue
frontend/composables/useAutoReport.ts
frontend/composables/useDeepReadChat.ts
frontend/composables/useReadingSaves.ts
frontend/composables/useResearchWork.ts
frontend/pages/papers/[id].vue
frontend/pages/papers/index.vue
frontend/pages/research/[id].vue
frontend/tests/fixtures/keyword_match.json
frontend/tests/unit/citationEvidence.test.ts
frontend/tests/unit/deepRead.test.ts
frontend/tests/unit/deepReadSse.test.ts
frontend/tests/unit/outlineEdit.test.ts
frontend/tests/unit/proposalDocument.test.ts
frontend/tests/unit/proposalView.test.ts
frontend/tests/unit/readingList.test.ts
frontend/tests/unit/topicDeck.test.ts
frontend/tests/unit/useAutoReport.test.ts
frontend/tests/unit/useDeepReadChat.test.ts
frontend/tests/unit/workEvents.test.ts
frontend/tests/unit/workPhase.test.ts
frontend/types/work.ts
frontend/utils/citationEvidence.ts
frontend/utils/deepRead.ts
frontend/utils/deepReadSse.ts
frontend/utils/outlineEdit.ts
frontend/utils/proposalDocument.ts
frontend/utils/proposalView.ts
frontend/utils/readingList.ts
frontend/utils/topicDeck.ts
frontend/utils/workEvents.ts
frontend/utils/workPhase.ts
research/round06e-keyword-candidates/README.md
research/round06e-keyword-candidates/measure.py
research/round06e-keyword-candidates/out/fill_rate.md
```

- 고치지 않을 파일 `diff --stat` — 빈 출력(딥리서치 코드·워커·스키마·`research_reading.py`·딥리서치 프롬프트·책 프롬프트·compose·인프라·패키지·06d 파일·`citations.ts`·기록 프론트·`term_checks.json`·`marker_checks.json`·`citations.test.ts`)
- `[id].vue` 의 예상 밖 줄 — 빈 출력. 06e 가 바꾼 줄은 Task R1 의 요약 띠 버튼 글 한 줄(`:60` — `[보고서 보기]` → `[딥리서치 보고서 보기]`, diff 의 `-`·`+` 두 줄), ReadingStep·ProposalStep 두 줄(`@open-pdf`·`@panel`)과 script 의 `workPanelOpen` 두 줄(주석 + `ref`), Task R6 을 했으면 루트 `skx-app` 줄·`AppSidebar` 자리뿐이다. 다른 줄이 나오면 06d 영역을 건드린 것이다 — 그 Task 로 돌아가 되돌린다
- `doc-kind="paper"` 줄 → `2`(두 파일에 한 줄씩), 그 밖의 줄 → `0`
- `장부 블록 1 그대로`·`장부 블록 2 그대로` 두 줄
- `work.css` 의 지운 줄 → `0`(06e 는 표시 줄 위에 더하기만 한다). 0 이 아니면 그 hunk 를 보고 어느 Task 가 기존 규칙을 고쳤는지 확인한 뒤(근거 장부 블록이 아니어야 한다) 까닭을 완료노트 §3 에 적는다
- 더한 줄의 색값 → `0`(`--skx-*` 토큰만)
- 프롬프트에 더한 줄의 예시 낱말 → `0`(함정 15)
- 트레일러 → `0`(종료 코드 1 은 맞는 줄이 없을 때의 정상 값. Git Bash 의 grep 은 `-i` 와 `-e` 여럿을 함께 주면 죽으므로 `-E` 한 패턴으로 쓴다)
- `git status --short` — 빈 출력

- [ ] **Step 3: (선택) 로컬 화면을 운영 API 에 붙여 GET 으로만 본다**

리뷰 전에 새 화면이 **06e 전 응답**(운영은 아직 06c fastapi — `section_gens`·`concept_candidates`·`total`·`doc_type` 이 없다)에서도 깨지지 않는지 한 번 본다. 배포 순서상 운영에서 새 nuxt 가 옛 fastapi 를 만날 일은 없지만, 06b 에 이어간 연구는 배포 뒤에도 새 키가 없는 저장값을 준다 — 같은 점검이다. **운영에 쓰지 않는다** — 아래 화면에서 누르면 쓰는 버튼([보고서 만들기]·[이 절 쓰기]·[담음]·[이 키워드로 다시 만들기]·칸 [저장]·Word·PDF·딥리드 질문 보내기·[다른 방향])은 누르지 않는다. 보고서 화면을 여는 것만으로 연쇄가 돌 수 있는지 먼저 본다 — 운영의 06e 전 반영은 `auto` 를 쓰지 않으므로 연쇄는 돌지 않는다(`autoChainOn` 이 `outline.auto === true` 를 요구한다):

```bash
curl -s http://192.168.12.57:92/api/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383/proposal | grep -c '"auto":true'
```

Expected: `0`. `1` 이면 이 Step 을 하지 않는다(운영에 이미 auto 목차가 있다 — 06e 가 나간 뒤다).

포트는 다른 세션의 미리보기(3000·3016)와 겹치지 않게 3017 을 쓴다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e/frontend && NUXT_DEV_API_TARGET=http://192.168.12.57:92/api npx nuxi dev --port 3017
```

(이 명령은 백그라운드로 띄우고, 다 보면 그 프로세스를 끈다.) 브라우저로 06b 운영 확인 잡(이어간 연구 `d8348de8-ee7f-48f9-8ceb-20924ed6a383`)을 본다:
- `http://localhost:3017/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383?s=topics` — 단계 이름 '제목 고르기', 키워드 칩은 후보가 없어 저장된 키워드만 눌린 칩으로, 카드 제목에 하이라이트 없음(카드에 `keywords` 가 없다), '키워드가 바뀌었습니다' 없음
- `?s=reading` — '참고문헌 선택하기', 논문 제목을 누르면 오른쪽 딥리드 패널이 열리고(대화는 보내지 않는다) [논문 상세 ↗]·닫기·Esc 로 닫히면 누른 제목으로 초점이 돌아온다
- `?s=proposal` — '보고서', 06b 목차(auto 없음)라 큰 진행 막대가 없고 연쇄가 돌지 않는다(개발자 도구 Network 에 `sections/…/generate` POST 가 없다), 머리 목차·문서 자리 1~6, '검토할 곳' 줄, 내보내기 카드의 '수락한 문단만' 체크. 인용 칩을 누르면 패널이 열리고 인용 근거 조회가 404(운영에 아직 없는 경로)라 오류 줄이 선다 — 이 미리보기에서만 맞는 모습이다
- 콘솔 오류 없음(인용 근거 404 의 네트워크 줄은 빼고)

Expected: 위 넷. 깨지는 화면이 있으면 그 Task 로 돌아가 고친 뒤 Step 1·2 를 다시 돈다.

- [ ] **Step 4: 영역별 정적 리뷰 — code-reviewer 여섯을 병렬로**

리뷰어에게 줄 diff 를 저장소 밖에 뜬다:

```bash
mkdir -p C:/Users/LANDSOFT/round06e-eval/review
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e
BASE=$(git merge-base HEAD dev)
git diff $BASE HEAD -- app/services/research_work/outline.py app/services/research_work/proposal_views.py app/api/research_proposal.py app/services/research_work/shapes.py app/services/research_work/progress.py app/services/research_work/section_input.py app/services/research_work/markers.py app/models/research_work.py > C:/Users/LANDSOFT/round06e-eval/review/a-report-backend.diff
git diff $BASE HEAD -- frontend/utils/proposalView.ts frontend/utils/proposalDocument.ts frontend/utils/outlineEdit.ts frontend/utils/workPhase.ts frontend/composables/useAutoReport.ts frontend/components/work/ProposalStep.vue frontend/components/work/ProposalSection.vue frontend/components/work/DocField.vue frontend/components/work/ReadingStep.vue frontend/types/work.ts frontend/assets/css/work.css > C:/Users/LANDSOFT/round06e-eval/review/b-report-frontend.diff
git diff $BASE HEAD -- frontend/utils/deepReadSse.ts frontend/composables/useDeepReadChat.ts frontend/utils/deepRead.ts frontend/components/BookChat.vue frontend/components/work/DeepReadPanel.vue frontend/components/work/CitationSource.vue frontend/utils/citationEvidence.ts frontend/components/work/ReadingStep.vue frontend/components/work/ReadingTable.vue frontend/components/work/ProposalStep.vue frontend/components/work/ProposalSection.vue frontend/utils/readingList.ts frontend/composables/useResearchWork.ts "frontend/pages/research/[id].vue" frontend/pages/papers/index.vue "frontend/pages/papers/[id].vue" frontend/assets/css/work.css app/services/chat/book_chat.py app/domains/nl_library/prompts/book_chat.paper.yaml app/schemas/book.py app/scripts/verify_prompt_parity.py app/api/research_proposal.py app/services/research_work/proposal_views.py > C:/Users/LANDSOFT/round06e-eval/review/c-deepread-cite.diff
git diff $BASE HEAD -- app/services/research_work/keywords.py app/services/research_work/concepts.py app/domains/nl_library/prompts/research_concepts.yaml app/api/research_work.py app/services/research_work/views.py app/services/research_work/seeds.py app/services/research_work/topic_card.py app/domains/nl_library/prompts/research_topic_card.yaml app/api/research_topics.py app/services/research_work/apply.py app/services/research_work/generate.py research/round06e-keyword-candidates > C:/Users/LANDSOFT/round06e-eval/review/d-keywords-backend.diff
git diff $BASE HEAD -- frontend/utils/topicDeck.ts frontend/utils/workEvents.ts frontend/composables/useResearchWork.ts frontend/components/work/ConceptChips.vue frontend/components/work/TopicCard.vue frontend/components/work/TopicDeck.vue frontend/components/work/TopicsStep.vue frontend/tests/fixtures/keyword_match.json frontend/utils/workPhase.ts frontend/components/work/OnboardingModal.vue frontend/components/work/OutlineEditor.vue frontend/components/work/FunnelCounter.vue frontend/components/work/WorkStepper.vue frontend/components/work/CandidateDrawer.vue frontend/composables/useReadingSaves.ts frontend/assets/css/work.css app/repositories/history.py app/api/history.py app/schemas/history.py > C:/Users/LANDSOFT/round06e-eval/review/e-keywords-names-history.diff
git diff $BASE HEAD -- app/tests frontend/tests > C:/Users/LANDSOFT/round06e-eval/review/f-tests.diff
wc -l C:/Users/LANDSOFT/round06e-eval/review/*.diff
```

Expected: 여섯 파일 모두 0 줄이 아니다.

`.claude/agents/code-reviewer.md` 서브에이전트(subagent_type `code-reviewer`) 여섯을 **한 번에 병렬로** 띄운다. 각 프롬프트는 아래 공통 머리 + 영역 줄이다.

공통 머리(그대로):

```text
round06e(연구 어시스턴트 — 워커·fastapi·nuxt) 브랜치의 한 영역을 정적 리뷰한다. 저장소 C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e 의 파일과 아래 diff 파일을 읽는다. 설계 정본은 docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md §12-4·§12-5·§12-6·§12-7·§12-11 과 D20·D21·D23·D24·D27, 이 줄의 결정은 docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md 의 '06e 에서 정한 것'(정함 1~31 — 정함 9·10·22·23·29 는 spec 을 실제 코드에 맞춰 좁혔고 정함 28 은 사용자가 10-11 확인했다, 문서는 나중에 맞춘다)과 '공통 계약'(1-1~1-9). 코딩 표준 docs/standards/coding-standard.md, 반복 함정 docs/ops/recurring-gotchas.md 와 대조한다. 공통으로 본다: ① 스키마 변경이 없다 — 새 모양은 JSONB·응답 안이고 옛 행(키가 없는 outline·card·생성 input/output)을 읽어도 깨지지 않는다(함정 14) ② 06c·06d 파일(services/research/*, workers/*, components/research/*, research.css, EvidenceLedger, evidenceLedger.ts, citations.ts, researchEvents.ts, types/research.ts, types/history.ts, historyStore.ts, AppSidebar.vue, pages/index.vue, term_checks.json)과 [id].vue 의 :57-75·workPanelOpen 밖, pages/papers 두 파일의 doc-kind 한 속성 밖을 고치지 않았다 ③ 프롬프트에 개수 예시·배열 견본·예시 제목·이전 제목이 없다(함정 15·26) ④ 실패 처리는 실제로 나는 타입만 잡고 except Exception 이 없다, FastAPI 쪽에 새 임베딩·Milvus·리랭커 호출이 없다(함정 17·19) ⑤ Nuxt 자동 import — 한 이름은 한 파일만 export 한다(공통 계약 1-6), utils·composable 은 쓰는 것을 모두 명시해 import 한다 ⑥ 06b 타입에 더한 필드는 선택(?)이다 ⑦ 화면을 그리는 경로·computed 가 쓰는 요청(POST·PUT·DELETE·PATCH)을 하지 않는다 — 쓰는 요청은 사용자 클릭 처리기와 useAutoReport 의 연쇄(autoChainOn 이 참일 때만 — 승인·auto·예시 아님·목차 생성 없음)에서만 ⑧ 순수 함수가 받은 객체를 고치지 않는다 ⑨ 접근성 — 버튼은 button, aria-pressed·aria-expanded·aria-controls·role=progressbar 의 aria-valuenow/valuetext·tablist/tab, 초점 복귀, aria-live 를 남발하지 않는다 ⑩ CSS 는 --skx-* 토큰만, 새 묶음은 work.css 표시 줄 위에만, 근거 장부 블록 그대로, 새 움직임은 prefers-reduced-motion 에서 멈춘다 ⑪ 409·422 의 detail 모양(문자열 / {"code","message"})과 화면의 오류 문구 읽기(detailMessage·workErrorMessage)가 맞다. 보고는 code-reviewer 형식(severity·location·issue·suggestion), 읽은 근거만.
```

영역 줄(공통 머리 뒤에 하나씩):

```text
[A 보고서 자동 산출·마무리 — 백엔드] diff: C:/Users/LANDSOFT/round06e-eval/review/a-report-backend.diff. 파일: app/services/research_work/outline.py, proposal_views.py, shapes.py, progress.py, section_input.py, markers.py, app/api/research_proposal.py, app/models/research_work.py. 특히: outline.apply 가 질문이 있을 때만 state approved·approved_at·auto true 로 저장하고 질문이 없으면 draft·auto false 로 두는지(정함 3), PUT /outline 이 auto 를 지우지 않는지, [보고서 다시 만들기](새 apply)가 auto 를 다시 붙이는지, outline.apply 가 옛 목차의 background 만 이어 받고(방법은 빈칸으로) 없으면 키를 두지 않는지, section_gens 가 kind section·target 있는 생성 중 키별 id 가 가장 큰 것(상태 무관)인지, 근거 없음 409 가 {"code": "no_section_papers", "message": …} 이고 다른 409 는 그대로인지, OutlinePut.background 가 None 이면 저장된 값을 지키고 길이 상한 422 인지, stale_flags 가 basis 에 question 키가 있는 절만 지금 연구 질문과 견주는지(06b 절은 stale 이 되지 않음 — 정함 9), sections_filled 가 outline.background 를 세는지, GAP_CLAIM_REWRITES 가 GAP_CLAIM_CONTEXT(코퍼스·소장 논문/자료/문헌/학술논문)를 품은 문장에만 걸리고 인용한 발견 문장('김(2015)[E1]은 … 확인되었다')은 그대로인지, 두 번 거쳐도 같은지, soften_claims 의 시그니처와 호출처(check_paragraph 둘·직접 둘)가 그대로인지, sources 조회가 gen 쿼리 → 저장된 절 gen_id → 그 키의 열린 생성 순으로 고르고 다른 연구·다른 키의 생성이면 404 인지, 예시 연구도 읽기는 되는지, 서지·Milvus·리랭커를 부르지 않는지.
[B 보고서 화면 — 프론트] diff: C:/Users/LANDSOFT/round06e-eval/review/b-report-frontend.diff. 파일: frontend/utils/proposalView.ts, proposalDocument.ts, outlineEdit.ts, workPhase.ts(FINAL_STEP_NAME·버튼 상수), composables/useAutoReport.ts, components/work/ProposalStep.vue, ProposalSection.vue, DocField.vue, ReadingStep.vue([보고서 만들기]), types/work.ts, assets/css/work.css(.wk-doc·.wk-rbar·.wk-docfield·.wk-review). 특히: autoChainOn·autoTargets·nextAutoSection 이 spec §12-4(대상 = 절도 생성 기록도 없는 키, failed·canceled 는 다시 넣지 않음, 문서 순서 prior.g1~g4 → gap)와 맞는지, useAutoReport 가 앞 POST 응답 뒤 다음 키를 넣고 생성 완료를 기다리지 않는지·409 no_section_papers 는 건너뛰고 그 밖의 오류는 멈추는지·scope 가 끝나면 넣지 않는지·reload 뒤 같은 키를 다시 넣지 않는지·running 중 watch 가 두 번째 루프를 띄우지 않는지, reportBar 가 조사 없는 꼴('보고서 작성 중 · n/m절 — 「…」')이고 추정 증가 없이 절이 끝날 때만 움직이며 쓸 것이 없으면 null 인지(정함 28 — 사용자 확인), 막대가 role=progressbar·aria-valuetext 이고 두께 토큰 --wk-bar-thick 1rem(768px 이하 0.75rem)·글줄 1rem 굵게·퍼센트 1.25rem 이며 is-running 움직임이 reduced-motion 에서 멈추는지, docToc 의 anchor 여섯이 문서 자리 id 와 같고 머리 목차가 그 자리로 스크롤·h3 초점을 옮기는지, OutlineEditor 가 승인 목차에선 접힌 채([목차 고치기]) 초안 목차에선 열린 채 시작하는지, putOnceMore 가 첫 409 version_conflict 만 응답 version 으로 한 번 더 보내는지, fieldPut 이 승인 상태를 지키는지(approve = state === approved), proposalDocument 의 기본이 모든 문단·워터마크 없음이고 acceptedOnly 면 수락·수정·직접 작성만·파일 이름 꼬리 _수락문단만, 2절에 연구 배경(없으면 흐린 안내 — '다음 단계에서 씁니다' 없음), 부록에 모델·시도 줄이 없고 상태별 개수·검토할 곳·날짜·결과·논의 미포함이 있는지, UNREVIEWED_WATERMARK 를 지웠어도 ReportDoc.watermark·reportDocx·ReportPrint 그리기는 그대로인지, FINAL_STEP_NAME 뒤에 조사를 붙여 만든 문구가 없는지(정함 1).
[C 딥리드·인용 근거] diff: C:/Users/LANDSOFT/round06e-eval/review/c-deepread-cite.diff. 파일: frontend/utils/deepReadSse.ts, composables/useDeepReadChat.ts, utils/deepRead.ts, components/BookChat.vue, components/work/DeepReadPanel.vue, CitationSource.vue, utils/citationEvidence.ts, components/work/ReadingStep.vue·ReadingTable.vue·ProposalStep.vue·ProposalSection.vue(패널·인용 칩), utils/readingList.ts(firstPathChunk), composables/useResearchWork.ts(getSectionSources), pages/research/[id].vue, pages/papers/index.vue·[id].vue, assets/css/work.css(.wk-split·.wk-panel·.wk-reading·.wk-cite), app/services/chat/book_chat.py, prompts/book_chat.paper.yaml, app/schemas/book.py, app/scripts/verify_prompt_parity.py, app/api/research_proposal.py·services/research_work/proposal_views.py(sources). 특히: parseSse 가 조각 경계를 잇고 깨진 JSON 을 버리는지, cntsId 가 바뀌면 스트림을 끊고 store 의 그 논문 대화로 바꾸는지(store 가 없으면 비움), stop 이 AbortController 로 끊고 받은 글 + '(답을 받다가 멈췄습니다)'(없으면 '(답을 받기 전에 멈췄습니다)')를 assistant 로 남겨 history 의 user/assistant 짝을 지키는지(정함 21), 출처 칩 글자가 저장값 그대로(p.X–Y — book_chat.py 의 LLM 문맥과 같은 날값)이고 [원문 보기]만 citedPdfTarget(+1)로 여는지(정함 22), 기존 네 화면(논문 상세·논문 검색 채팅 패널·도서 상세·TopResult)은 docKind 기본 book·pdfLinks 기본 false 로 동작이 그대로인지, 패널의 탭 role·aria·Esc·서랍/전체 폭에서 초점 가두기·배경 누르면 닫기·닫으면 누른 자리로 초점이 돌아오는지, ReadingStep·ProposalStep 이 panel emit 을 watch 와 onBeforeUnmount 로 내고 [id].vue 는 리스너·workPanelOpen 만 달았는지(R1 의 :60 요약 띠 버튼 글 '딥리서치 보고서 보기' 한 줄 밖 — 정함 30, watch(step) 없음, @panel 이 한 요소에 두 번 없음), 예시 연구는 [담음]이 꺼지고 대화는 열리는지, 인용 칩이 저장된 문단에서만 패널을 열고 흐르는 글의 칩은 span 그대로인지(정함 24), bestExcerptSentence 가 마커를 빼고 n-gram 겹침으로 고르는지, 대목이 없으면 초록만 보이는지, chat_prompt 가 doc_type 이 paper 면 논문 프롬프트·없거나 book 이면 base 를 쓰는지, book_chat.paper.yaml 이 base 와 같은 변수·params 이고 예시가 없는지, BookOut.doc_type 이 선택 필드인지, 딥리서치 보고서의 CitationChip 팝오버를 건드리지 않았는지. book_chat.py:117-118 의 참고문헌 의도 질문이 BookOut 에 없는 extra 를 읽던 기존 버그는 S2 가 _book_references 로 고쳤다(정함 31) — 속성 없음·None 을 빈 목록으로 읽고 참고문헌 의도 질문이 스트림을 끊지 않는지 본다.
[D 제목 고르기 — 백엔드] diff: C:/Users/LANDSOFT/round06e-eval/review/d-keywords-backend.diff. 파일: app/services/research_work/keywords.py, concepts.py, prompts/research_concepts.yaml, app/api/research_work.py, services/research_work/views.py, seeds.py, topic_card.py, prompts/research_topic_card.yaml, app/api/research_topics.py, services/research_work/apply.py, generate.py, research/round06e-keyword-candidates/(README·measure.py·out). 특히: 후보가 LLM 순서 먼저·논문에만 있는 것은 편수 내림차순·두 원천이면 both 와 편수·상한 10·일반어 없음·PAPER_KEYWORD_MIN_N(Task Z1 판정)을 따르는지, 미리 선택이 3개(모자라면 전부)인지, 옛 개념 output({"concepts"} 만)을 읽어도 concept_candidates 가 None 이고 깨지지 않는지, 이어가기가 주제 행만 만들고 topic_card 생성을 넣지 않는지, enqueue_seed_cards 가 씨앗 자리 행마다(상태 무관 기존 topic_card 생성이 있으면 건너뜀 — 정함 29) 넣고 커밋하지 않는지·[다른 방향] 카드가 씨앗 카드를 막지 않는지, done 반영(빈 결과 포함)과 취소 API 가 같은 함수를 부르고 취소면 키워드 없이 넣는지, 취소 API 가 커밋 뒤 dispatch·queued 이벤트를 보내는지, [다른 방향]이 개념 생성 중이면 409 KEYWORDS_BUSY 이고 잠금 전이라 롤백할 것이 없는지, regenerate 가 edited·picked·folded·user 카드를 건너뛰고 열린 생성은 skipped 로 세며 고른 키워드 2개 미만이면 409 인지·advisory lock 키가 카드 생성 target 과 겹치지 않는지, topic_input 의 keywords 가 늘 넘어가 StrictUndefined 에서 깨지지 않는지(옛 행 input.get("keywords") or []), keyword_misses 가 06c contains 를 쓰는지, soft_check 가 엄격한 통과를 이기지 않고 세 번 다 놓쳤을 때만 마지막 무른 통과 출력을 그 모델 이름으로 돌려주는지·soft_check 없는 실행기는 그대로인지, measure.py 가 읽기 전용 SELECT 만 하고 함정 10·11 을 피했는지, 워커 research_work_tasks.py 를 고치지 않고도 새 카드 생성이 디스패치되는지(_close 의 has_queued).
[E 제목 고르기 화면·단계 이름·기록 total] diff: C:/Users/LANDSOFT/round06e-eval/review/e-keywords-names-history.diff. 파일: frontend/utils/topicDeck.ts, workEvents.ts, composables/useResearchWork.ts(regenerateTopics), components/work/ConceptChips.vue, TopicCard.vue, TopicDeck.vue, TopicsStep.vue, tests/fixtures/keyword_match.json, utils/workPhase.ts(STEP_NAMES·문구), components/work/OnboardingModal.vue·OutlineEditor.vue·FunnelCounter.vue·WorkStepper.vue·CandidateDrawer.vue, composables/useReadingSaves.ts, assets/css/work.css(.wk-kw·.wk-kwchip·.wk-topic__kw), app/repositories/history.py, app/api/history.py, app/schemas/history.py. 특히: keywordSpans 가 NFKC·소문자·공백 무시로 찾되 원문 글자 그대로 감싸고 이어 붙이면 원문과 같은지, 06c term_checks.json 의 contains 칸과 참·거짓이 같은지(그 파일을 고치지 않음), cardStatus 가 생성 기록 없는 빈 씨앗 자리를 키워드 생성이 있으면 waiting(반영·취소 직후 포함)·실패면 blocked('키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다'), 씨앗 자리가 아니면 failed 로 가르는지, 다시 만드는 중인 카드는 canPick 이 거짓이고 cardRemakingNote 를 보이는지, RELOAD.concepts 에 topics 가 있는지, 칩이 aria-pressed·배지(AI 후보·논문 n편·직접)이고 후보 없는 옛·예시 연구는 저장된 키워드를 눌린 칩으로 보이는지, CONCEPTS_MAX 를 넘지 않고 2개 미만이면 [이 키워드로 다시 만들기]가 막히고 이유 줄이 보이는지, 고른 키워드가 저장과 다르면 PATCH 뒤 regenerate 를 부르고 409 면 다시 읽는지, '키워드가 바뀌었습니다'·'제목에 「…」 없음'이 고른·고친·사용자 카드엔 없는지, chipLabel 이 제1저자 전체 이름 연도(복성·외 n인·영문 이름)·저자 없으면 제목 앞 18자(SHORT_TITLE_MAX)이고 툴팁이 서지 한 줄인지, citeLabel·보고서 칩을 바꾸지 않았는지(Q3 S), STEP_NAMES 를 내보내고 단계 키·주소 ?s=·API 는 그대로인지, '계획서·읽기 목록·주제 고르기·핵심 개념' 이 보이는 글에 남지 않았는지, 06d 가 읽는 stepLine·stepForPhase·scopeLine 의 시그니처가 그대로인지, R1 의 서버 문구(IF_MATCH_FORMAT·VERSION_CONFLICT·CONCEPTS_BUSY·patch_work 422 — 코드는 a·d diff 에 있다)에 '계획서'·'핵심 개념'이 남지 않았는지, history count 가 list 와 같은 where(이 브라우저·deleted_at IS NULL·kind — _live 한 함수)이고 before 와 무관한지, list 의 반환 모양(2-튜플)이 그대로인지, total 이 선택 필드인지, 프론트 기록 파일을 건드리지 않았는지.
[F 테스트] diff: C:/Users/LANDSOFT/round06e-eval/review/f-tests.diff. 파일: app/tests/ 의 새 두 파일(test_research_work_keywords.py·test_book_chat_prompt.py)과 고친 열아홉 파일, frontend/tests/unit/ 의 새 다섯 파일(useAutoReport·deepReadSse·useDeepReadChat·deepRead·citationEvidence)과 고친 일곱 파일, tests/fixtures/keyword_match.json. 특히: 새 판단마다 실패 테스트가 먼저 있는지(TDD — 커밋 순서), spec §12-7 06e 목록(pytest: 목차 자동 승인·auto 를 PUT 이 지킴·절 키별 마지막 생성·'확인했다'·키워드 후보 정제·제목 일치·카드 한 번만(retry·취소)·다시 만들기(edited·열린 생성 건너뜀)·sources·질문 변경 stale·total / vitest: 남은 절 고르기·연구 공백 409·proposalDocument 기본·부록·'수락한 문단만'·칩 표기·키워드 하이라이트(공용 고정 예제)·SSE 파서·대화 중단·논문별 대화)이 모두 덮였는지, test_book_chat_prompt.py 의 대역이 모듈 머리가 아니라 fixture 안에서 끼우고 되돌리는지(test_search_chunk_answer_flag.py:24-53 의 _stubbed_pipeline 꼴 — 새로 import 한 모듈을 teardown 에서 직접 빼고, 그것을 보는 되돌림 테스트가 있는지), async 를 asyncio.run 으로 돌고 @pytest.mark.asyncio 가 없는지, 기존 테스트를 고친 곳이 계획의 ✎ 목록(예: TestApply·TestContinue·TestContinueSeeds·TestEndToEnd·test_research_work_tasks.py::TestDispatch·test_research_work_executor.py 의 두 it·test_research_work_api.py:510·TestTopicInput::test_shape·TestPrompt 의 견본 검사·proposalDocument 의 it 들·evidenceChips 첫 it·workEvents 의 reload it·TestOwnership.test_other_browser_list_is_empty)뿐인지, 픽스처 경로가 Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" 꼴인지, term_checks.json·marker_checks.json 을 고치지 않았는지, DOM·타이머·실제 네트워크에 기대는 vitest 가 없는지(node 환경 — fetch 는 대역 주입).
```

Expected: 리뷰어마다 요약 1~2문장 + 결함 목록(없으면 "없음"). 여섯 보고를 영역·severity 별로 한 표로 모은다(완료노트 §3 의 재료).

- [ ] **Step 5: 발견을 반영하고 리뷰를 마친 커밋을 적는다**

- severity high·medium 은 모두 고친다. low 는 고칠지 판단하고, 고치지 않으면 까닭을 적는다(완료노트 §3). 리뷰어끼리 엇갈리거나 계획의 결정(정함 1~31)과 다른 제안은 고치기 전에 그 결정의 근거와 견주고, 결정을 바꿔야 하면 사용자에게 묻는다(특히 정함 28 — 사용자가 확인한 결정이다).
- 판단을 바꾸는 수정은 그 함수의 실패 테스트를 먼저 쓰고(실행해 실패 확인) 고친 뒤 통과를 본다. `.vue`·`.css` 만의 수정은 typecheck `0`·build 완료로 확인한다. 커밋은 발견 묶음마다 `[Fix] round06e — <무엇을 왜>` 로, `git add` 는 파일을 하나씩 적는다.
- 다 고친 뒤 Step 1·Step 2 를 그대로 다시 돌린다. Expected: Step 1 의 수는 리뷰 반영으로 더한 테스트만큼 크고 나머지는 같다, Step 2 의 출력은 같다(고친 파일 목록에 새 파일이 들었으면 그 까닭이 적혀 있다).
- 그 뒤 고친 것만 해당 영역 리뷰어에게 다시 보인다(같은 공통 머리 + "앞 리뷰의 발견을 고친 diff 다 — 회귀가 없는지 본다", diff 는 `git diff <반영 전 커밋> HEAD`). 새 발견이 없을 때까지 되풀이한다(최대 3회 — 넘으면 남은 발견을 사용자에게 보인다).

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e rev-parse --short HEAD
```

Expected: 커밋 해시 한 줄 — '리뷰를 마친 커밋'으로 적어 둔다(완료노트 머리·§3, Task Z4 의 승인 요청).

---

### Task Z3: 문서 — 완료노트(배포 전)·00_status·spec 맞춤·반복 함정 판단

**왜:** D13(하위 라운드마다 완료노트), CLAUDE.md §3("문서와 코드가 어긋나면 코드가 실제이니 문서를 고친다"). 06e 는 spec 을 실제 코드에 맞춰 좁히거나 바로잡은 것(정함 9·10·22·23·29, §12-4 의 옛 줄 번호 넷, `BookOut` 에 없던 `doc_type`), 열린 질문을 기본값으로 만든 것(Q2·Q3 — 정함 1·2), §12-11 에서 정한 것(정함 7·11·12·14~19), spec 이 06d 에만 적은 큰 진행 막대를 보고서 화면에도 둔 것(정함 28 — 사용자 확인 2026-10-11)이 있다 — dev 머지 전에 spec 을 코드에 맞춘다. 배포·운영 확인 결과(§5)는 Task Z7 이 채운다.

**Files:**
- Create: `docs/roadmap/round06e-완료노트.md`
- Modify: `docs/roadmap/00_status.md`(3행 최종 갱신·round06 머리·round06 하위 줄 끝·다음 할 일의 06e 줄·라운드 이력의 round06 칸 — round06 줄만)
- Modify: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`(머리 상태 줄, D2·D20·D21·D23·D24·D27 행, §12-3 오프셋 행 한 구절, §12-4 의 옛 줄 번호 셋·카드 시점 한 문장, §12-10 Q2·Q3, §12-11 아홉 항목)
- `docs/ops/recurring-gotchas.md` — 이 Task 에서는 고치지 않는다(운영 전이라 라이브에서만 드러난 것이 아직 없다. Task Z7 이 다시 판단한다)

**알아 둘 것:**
- 기존 문서는 **Edit 도구로** 고친다(모두 CRLF). 아래 old 는 `c5d05b0`(spec 브랜치) 글자 그대로다. 06c·06d 의 문서 커밋이 K9·R6 의 dev 받기로 이 브랜치에 들어와 같은 줄을 먼저 고쳤으면 old 가 맞지 않을 수 있다 — 그때는 지금 줄을 바탕으로 같은 구절만 넣는다(아래 각 항목에 그 규칙을 적었다).
- `00_status.md` 는 round06 에 관한 줄만 고친다(3행은 모든 라운드가 함께 고치는 줄 — 06e 구절만 넣는다).
- 날짜는 이 Task 를 하는 날로 쓴다(아래 예는 계획 일정의 2026-10-16).
- 조건부 Task 에 따라 구절이 갈린다 — **R6**: 했다(06d 가 먼저 머지됨) / 건너뜀(06d 의 LNB 접기 연결 Task 가 단다). **H3**: 했다(PDF) / 건너뜀(일정으로 자름). **Z1**: `PAPER_KEYWORD_MIN_N` 1 / 2. 아래 꺾쇠 자리에 그 판정을 넣는다.

- [ ] **Step 1: 완료노트를 쓴다 (`docs/roadmap/round06e-완료노트.md`, 새 파일)**

꺾쇠 자리는 Task Z1·Z2 에서 실측·판단한 값과 이 Step 을 하는 날로 바꿔 쓰고 꺾쇠를 남기지 않는다 — 다 쓴 뒤 `grep -c '<[^>]*>' "docs/roadmap/round06e-완료노트.md"` 가 `0` 이다(이 노트에는 HTML 태그 꼴 글을 쓰지 않는다 — 부품 이름은 꺾쇠 없이 쓴다). §5 는 배포 뒤 Task Z7 에서 채운다.

```markdown
# round06e 완료노트

날짜: <이 Step 을 하는 날, 예: 2026-10-16> (계획 2026-10-08 · 구현·리뷰 <구현을 시작한 날>~<Task Z2 를 마친 날> · `dev` 머지·운영 배포·처음부터 끝까지 1회는 §5)
브랜치: `feat/round06e-assistant-auto-report` (worktree `.worktrees/round06e`, dev `<Task 0 Step 2 의 dev 커밋 7자리>` 에서 분기 · 커밋 <git rev-list --count 그 커밋..HEAD 의 수>개 · 리뷰를 마친 커밋 `<Task Z2 Step 5 의 커밋>`)
spec: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` (D20·D21·D23·D24·D27·D26 의 N, §12-4·§12-5·§12-6·§12-7·§12-11, Q1(보고서 화면에도 — 2026-10-11 사용자 확인)·Q2·Q3 기본값)
plan: `docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md` (Task 0 · A1~A5 · X1~X5 · R1~R6 · S1~S4 · K1~K9 · H1~H3 · Z1~Z7, 정함 1~31)
교본: 대회 뒤 round06 한 권(D13) — 06e 는 그 책의 한 장이 된다

> 한 줄 요약: 이어간 연구의 마지막 단계를 [보고서 만들기] 한 번으로 끝까지 가게 했다 — 목차가 자동으로 확정되고 선행연구 묶음·연구 공백 절이 문서 순서대로 차오르며, 화면 머리에 크게 보이는 진행 막대(사용자 Q1 답을 보고서 화면에도 — 2026-10-11 확인)·머리 목차·문서 자리 1~6·'검토할 곳'이 선다. Word 기본은 모든 문단·워터마크 없음과 공개 부록의 문단 상태별 개수다. 단계 이름을 '제목 고르기'·'참고문헌 선택하기'·'보고서'로 바꾸고, 논문 제목·보고서 인용 칩을 누르면 오른쪽에 딥리드·인용 근거(모델이 본 원문 대목 하이라이트)가 열린다. 제목 고르기는 후보 키워드 칩(LLM 후보 + 채택 논문 키워드)을 고르면 그 말이 박힌 카드 제목이 온다. 주제 카드 근거 칩은 제1저자 전체 이름 연도로, 기록 목록은 kind 별 total 을 싣는다<H3 을 했으면 ', 보고서를 PDF 로도 내려받는다'>. 워커·fastapi·nuxt — 스키마 변경은 없다.

---

## 1. 왜 했나

- **보고서 자동 산출(D20 — 회의 결정 ①, '최우선')** — 06b 의 마지막 단계는 목차 승인 → 절마다 [이 절 쓰기] → 문단 수락이라 시연에서 단계가 길었다. 회의 뒤 결정: 한 번 누르면 인용 달린 보고서가 끝까지 나오고, 수락·고치기는 선택 기능으로 남긴다. 수락 관문이 빠지므로 연구 공백 문단의 '확인했다' 단정(06b 이월 §7-13)을 함께 고쳤다.
- **큰 진행 막대(Q1)** — 사용자 "현재 절 작성 중에 보여지는 커다란 프로그레스바 필요, 예시 막대는 너무 작음"(10-08). spec 은 06d 딥리서치 진행 화면에만 적었지만 자동 보고서도 '절을 차례로 쓰는 중'인 화면이라 같은 크기 규칙의 막대를 두었다 — 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아"(2026-10-11).
- **내보내기 기본값(D21)** — 수락이 선택이 되면 06b 기본 Word(수락 문단만)는 모든 절이 빈 채로 나간다. 전부 싣고 부록으로 밝힌다.
- **참고문헌 선택하기·오른쪽 딥리드·인용 근거(D24 — 회의 결정 ⑤)** — 논문을 읽으러 상세 화면으로 떠나지 않고 그 자리에서 대화하고, 보고서 인용을 누르면 모델이 본 원문 대목을 바로 본다(저장된 대목을 보이는 것이 리랭커 점수보다 정직하고 싸다).
- **제목 고르기(D23 — 회의 결정 ③)** — 06b 핵심 개념에 일반어('측정 및 평가 · 연구 분야 · 발전 방향')가 섞였고 카드 제목이 그 개념을 쓰지 않았다. 고른 키워드가 제목에 박혀 오게 했다.
- **근거 칩 표기(D27 — 회의 결정 ④, 06b 이월 §7-14)** — '최 2018'(한글 이름 첫 글자·복성 잘림). Q3 답이 없어 주제 카드 칩만 고쳤다(S).
- **기록 total(D26 의 N)** — 06d 사이드바 '모두 보기 (N)' 의 재료.

---

## 2. 한 일

| 파트 | 한 것 |
|---|---|
| A 보고서 자동 산출 | 목차 반영이 질문이 있으면 승인 목차(`auto`)로 저장, ProposalView 의 절 키별 마지막 section 생성(`section_gens`), 근거 없음 409 에 code, 자동 산출 판정 순수 함수(`autoChainOn`·`autoTargets`·`nextAutoSection`·`docToc`·`reportBar`), 절 연쇄 `useAutoReport`(앞 응답 뒤 다음 키·근거 없음 건너뜀·오류면 멈추고 [이어서 쓰기]), 보고서 화면(큰 진행 막대·머리 목차·문서 자리 1~6·[목차 고치기] 뒤로 접기·[보고서 만들기]) |
| X 보고서 마무리·내보내기 | `outline.background`(상한 2000)·절 basis 의 연구 질문(바뀌면 '다시 맞춤 필요'), 연구 공백 단정 다듬기(`GAP_CLAIM_*` — 코퍼스 범위 문장만), 연구 배경·방법 칸(`DocField` — 승인 상태 그대로·버전 충돌 한 번 다시), '검토할 곳' 줄, 내보내기 기본값(모든 문단·워터마크 없음·'수락한 문단만'·2절 연구 배경·부록 상태별 개수·모델과 시도 기록 뺌)·문단 상태 이름 'AI 작성 · 검토 전' |
| R 단계 이름·딥리드 | 보이는 이름 '제목 고르기'·'참고문헌 선택하기'·'보고서'(`STEP_NAMES`·`FINAL_STEP_NAME` — 키·주소·API 그대로), 딥리드 스트림 분리(`deepReadSse`·`useDeepReadChat` — 논문별 대화·AbortController·멈춘 답 남기기), BookChat 문서 종류(책/논문 문구)·출처 칩 버튼·[원문 보기]·논문 화면 두 호출처 `doc-kind="paper"`, 오른쪽 패널 부품(`DeepReadPanel` — 2단·서랍·전체 폭·초점), 참고문헌 선택하기의 제목 → 딥리드·[담음]·들어온 경로 첫 대목, LNB 접기 연결(<R6 판정 — '06d 가 먼저 머지돼 06e 가 [id].vue 두 곳을 달았다' 또는 '건너뜀 — 06d 의 LNB 접기 연결 Task 가 단다'>) |
| S 인용 근거 | `GET …/sections/{key}/sources`(생성 행의 `input.papers` — 서지·Milvus·리랭커 없음), 딥리드 논문 프롬프트(`book_chat.paper.yaml`·`chat_prompt`·`BookOut.doc_type`), 대목 하이라이트 순수 함수(`citationEvidence` — 글자 n-gram 겹침), 인용 칩 → 오른쪽 인용 근거 탭(`CitationSource` — [원문 보기]·[이 논문과 대화하기]) |
| K 제목 고르기 | 논문 키워드 채움률 1회성 측정(`research/round06e-keyword-candidates/` — 판정 `PAPER_KEYWORD_MIN_N` = <Task Z1 판정>), 후보 키워드(`keywords.py` — LLM + 논문 편수·일반어·상한 10·위 3개), WorkView `concept_candidates`, 카드 입력·프롬프트의 키워드 규칙·[다른 방향]도 지금 키워드(개념 생성 중이면 409), 카드는 개념 반영 때 씨앗 자리마다 한 번(`enqueue_seed_cards` — done 과 취소가 같은 함수), [이 키워드로 다시 만들기](`POST …/topics/regenerate`), 키워드 칩·제목 하이라이트(`keywordSpans`·공용 고정 예제), 제목 키워드 검사(06c `terms.contains`)·세 번 놓친 카드(`soft_check`) |
| H 칩·total·PDF | 주제 카드 근거 칩 '제1저자 전체 이름 연도'·툴팁 서지 한 줄, 기록 목록 `total`(`HistoryRepository.count`), <H3 판정 — '보고서 PDF(보고서 화면이 스스로 인쇄 — Word 와 같은 문서·기본값)' 또는 'PDF 는 건너뜀(10/16 조건 — 일정으로 자름)'> |

스키마 변경 없음 — 바뀐 모양은 모두 JSONB·응답 안이다(`models/research_work.py` 머리 주석). 딥리서치 코드·워커·딥리서치 프롬프트·compose·인프라·06c/06d 파일·`citations.ts`·근거 장부 블록은 그대로다(Task Z2 Step 2).

---

## 3. 리뷰

작업마다 구현 → spec 준수 → 품질 검토를 돌렸고, 끝에 영역 여섯(A 보고서 백엔드·B 보고서 화면·C 딥리드·인용 근거·D 제목 고르기 백엔드·E 제목 고르기 화면·단계 이름·기록 total·F 테스트)을 code-reviewer 로 병렬 정적 리뷰했다. <발견 수와 반영 커밋 수·주요 수정 — 예: 'high 0 · medium 3 · low 7, 수정 3커밋: …'>. 고치지 않은 발견과 까닭: <없으면 '없음'>. 넘긴 것은 §7.

---

## 4. 검증

- 백엔드 pytest `5 failed, <Task Z2 Step 1 의 N> passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 Task 0 기준선과 같은 로컬 의존성 파일(test_build_manifest·test_loaders·test_book_chat 수집). 기준선 <Task 0 의 수>. 06e 백엔드 묶음 스물세 파일 <수> passed, 06c 의 `test_research_terms.py`·`test_research_eval.py` 그대로 통과.
- 프론트 vitest <F>파일 <T> · `nuxi typecheck` 오류 0 · `Duplicated imports` <Task 0 과 같은 값> · `npm run build` 완료 (<Task Z2 를 마친 날>, dev 머지 전). 그대로여야 하는 `citations`·`reportDocument`·`reportDocx` 49 그대로.
- 경계: 고친 파일 목록이 계획과 같고, 06c·06d 파일·딥리서치 코드·스키마·`citations.ts`·근거 장부 블록 diff 없음, `[id].vue` 는 요약 띠 버튼 글 한 줄(R1) + 두 줄 + `workPanelOpen` 두 줄<R6 이면 ' + 루트·AppSidebar'>, 논문 화면 두 곳은 `doc-kind="paper"` 한 줄씩, 프롬프트에 예시 낱말 0, 커밋 트레일러 0.

---

## 5. `dev` 머지·운영 배포·운영 확인

배포 전 — 계획 Task Z4~Z6 의 결과를 Task Z7 의 기록 브랜치에서 채운다.

---

## 6. 결정

| # | 결정 |
|---|---|
| 정함 1 | Q2 기본 '보고서' — 이름 낱말은 `FINAL_STEP_NAME` 하나이고 조사가 붙지 않는 꼴에만 쓴다(조사가 붙는 문장은 글자 그대로 — 이름을 바꾸면 상수 한 줄과 `grep -rn "보고서[를로가는의은이]"` 가 내는 문장·테스트). Q2 의 딥리서치 용어 — 단계 화면에서 딥리서치 보고서는 「딥리서치 보고서」(Task R1 의 다섯 곳과 온보딩 ②) |
| 정함 2 | Q3 기본 S — 주제 카드 칩만(`topicDeck.ts`), `citeLabel`·보고서 칩·상세 인용 배너 그대로 |
| 정함 3 | 자동 승인은 연구 질문이 있을 때만(첫 후보 → 카드 질문, 공백 정리 뒤 2자 미만은 없는 것) — 없으면 06b 처럼 초안·`auto` false |
| 정함 4 | [보고서 다시 만들기]는 이미 쓴 절을 다시 쓰지 않는다 — 주제·묶음·연구 질문이 바뀐 절은 '다시 맞춤 필요' + [이 절 다시 쓰기], 아직 쓰지 않은 절만 자동, 연구 배경은 이어 받는다 |
| 정함 5 | 근거 없음 409 는 `{"code": "no_section_papers", "message"}` — 연쇄는 code 로 가른다 |
| 정함 6 | 연쇄는 보고서 화면이 열려 있을 때 돈다 — 서버 값으로 매번 다시 계산해 탭을 닫았다 와도 남은 절부터 |
| 정함 7 | 연구 배경 = `outline.background` 자유 글(상한 2000, PUT 에서 생략·null 이면 지킴, 새 반영(apply)은 옛 목차에서 이어 받음 — Task X1) — Word·PDF 2절에도, '다음 단계에서 씁니다'는 지움 |
| 정함 8 | 방법·배경 칸은 문서 2·6절 자리에서 승인 상태 그대로 저장, `version_conflict` 는 응답 version 으로 한 번만 다시 |
| 정함 9 | 연구 질문 바뀜 = 절 basis 의 `question` — 06e 부터 쓴 절만 견준다(06b 절은 이 이유로 stale 이 되지 않음) |
| 정함 10 | 연구 공백 단정은 '소장 코퍼스 범위' 낱말(코퍼스·소장 논문/자료/문헌/학술논문)이 든 문장에서만 공백 후보 투로 — 인용한 발견은 그대로 |
| 정함 11 | '검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m' 줄과 부록의 같은 수는 넣고, '근거 없음' 보이는 배지는 넣지 않는다(화면낭독 글만) |
| 정함 12 | 문단 버튼 줄은 접지 않는다 |
| 정함 13 | 내보내기 기본 = 네 상태 전부·워터마크 없음, '수락한 문단만'(`acceptedOnly`)이면 수락·수정·직접 작성만과 파일 이름 꼬리 `_수락문단만`. 부록에서 모델 이름·시도 기록 줄을 뺐다 — 저장은 그대로(`research_generations.model`·`output.attempts` — 필요하면 DB 로 본다) |
| 정함 14 | 키워드 후보 = LLM 후보 + 채택 논문 키워드 문서 빈도 — `PAPER_KEYWORD_MIN_N` = <Task Z1 판정 — 1 또는 2>(최근 이어간 연구의 채택 논문 채움률 <측정값>%) |
| 정함 15 | 키워드 최소 선택 2(처음 미리 선택 3 은 하한을 보지 않음)·상한 5·직접 더하기 남김 |
| 정함 16 | 고른·고친·직접 쓴·접은 카드는 키워드를 바꿔도 다시 만들지 않는다 |
| 정함 17 | 세 번 다 놓친 카드는 `soft_check` 로 마지막 무른 통과 출력을 보관해 '제목에 「…」 없음' 경고와 함께 보인다 |
| 정함 18 | 딥리드 논문 프롬프트 채택 — `book_chat.paper.yaml` + `chat_prompt(book)`, `BookOut.doc_type` 을 더했다(spec 이 가정한 필드가 응답에 없었다) |
| 정함 19 | 연구 맥락을 반영한 딥리드 첫 화면은 하지 않는다 |
| 정함 20 | 딥리드 대화는 단계 화면이 쥔 논문별 대화 — 같은 단계 안에서만 이어지고 서버에 저장하지 않는다 |
| 정함 21 | 닫기·논문 바꾸기로 끊은 답은 받은 글 + '(답을 받다가 멈췄습니다)'로 남긴다(history 의 짝을 지킨다) |
| 정함 22 | 출처 칩 글자는 저장값 그대로(LLM 문맥과 같은 쪽), [원문 보기]만 뷰어 쪽(+1) |
| 정함 23 | 인용 근거 조회 = `{E#: {cnts_id, abstract, excerpt}}`, 생성은 `?gen=` → 저장된 절 → 열린 생성 순, 그 생성 행의 `input.papers` 만 읽는다 |
| 정함 24 | 인용 칩은 저장된 문단에서만 패널을 연다(쓰는 중인 글의 칩은 그대로) |
| 정함 25 | 개념 반영이 넣은 카드는 화면이 개념 done 에 다시 읽어 보고, 취소 API 가 넣은 카드는 커밋 뒤 queued 이벤트 |
| 정함 26 | 기록 total 은 `HistoryRepository.count` 로 따로 센다 — `list` 의 반환 모양 그대로, `before` 와 무관 |
| 정함 27 | PDF 는 보고서 화면이 스스로 인쇄한다(Word 와 같은 문서·기본값) — <H3 판정 — '했다' 또는 '일정으로 하지 않았다(§7)'> |
| 정함 28 | 자동 보고서 화면에도 큰 진행 막대(두께 1rem·768px 이하 0.75rem·큰 글줄·퍼센트 — `work.css` 토큰) — 이 계획의 판단, 사용자 확인 2026-10-11 |
| 정함 29 | 씨앗 카드 '한 번만'은 씨앗 자리마다 판정하고, [다른 방향]은 개념 생성이 열려 있으면 409 `KEYWORDS_BUSY` |
| 정함 30 | LNB 접기 — 06e 는 emit·리스너·`workPanelOpen`, `[id].vue:3-7` 두 곳은 늦게 머지하는 줄 — <R6 판정 — '06e 가 달았다(06d 먼저 머지)' 또는 '06d 의 LNB 접기 연결 Task 가 단다'> |
| 정함 31 | 딥리드 참고문헌 질문의 기존 버그(`book_chat.py:117-118` 이 `BookOut` 에 없는 `extra` 를 읽는다 — 코드는 0b51e68 부터) — Task S2 에서 고쳤다(`_book_references` 가 `BookOut.references` 를 읽는다, 테스트 1) |

---

## 디자인 참조

해당 없음 — 디자인 트랙 미도입(화면은 `--skx-*` 토큰만 읽는 `work.css` 에 두었다. 큰 진행 막대의 치수는 `--wk-bar-thick` 토큰이라 시각 디자인 담당이 고칠 수 있다).

---

## 7. 이월

1. **근거 칩 다섯 곳 통일(Q3 M)** — 보고서 `CitationChip`·상세 인용 배너·`OutlineEditor`·`ProposalSection`·`paperDetail` 의 '성 연도'(`citeLabel`)는 그대로다. 06b 이월 §7-14 가운데 보고서 절 인용 칩('박 2007' 꼴 — 운영 확인 표의 관찰)도 여기 남는다. 사용자가 M 을 고르면 `citeLabel` 한 곳을 `chipLabel` 규칙으로 바꾸고 `citations.test.ts` 를 고친다.
2. **딥리드 대화 서버 저장**(§12-9) — 지금은 단계 화면의 세션만(정함 20).
3. **연구 맥락을 반영한 딥리드 첫 화면**(§12-11 선택 — 정함 19).
4. **리랭커 뒷받침 점수·원문 뷰어 안 하이라이트**(§12-9 — 인용 근거 하이라이트가 대신한다).
5. **연쇄를 다른 단계 화면에서도 돌리기**(정함 6)·**쓰는 중인 글의 인용 칩**(정함 24).
6. **연구 공백 단정의 남는 한계** — 코퍼스 낱말이 앞 문장에만 있고 단정이 다음 문장에 있으면 잡지 못한다(Task X2 — '확인했다' 를 문장 단위로만 본다). 코퍼스 문장 안의 효과 없음 결과('소장 논문을 분석한 결과 성별 간 차이가 없음을 확인했다')는 결핍 단정('관련 연구가 없음을 확인했다')과 같은 꼴이라 공백 후보로 바뀐다 — 주어를 연구·논문으로 좁히면 '다룬 것이 없음을'·'아직까지 없음을' 같은 결핍 단정을 놓쳐 좁히지 않았다(결핍 말의 부정 '부족하지 않은'·'적지 않음을'·'다르지 않음을'과 '다름없는'·'변함없음' 같은 합성어는 그대로 둔다).
7. **LNB 접기 연결** — <R6 판정 — '06e 가 달았다 — 이월 없음' 또는 '06d 의 LNB 접기 연결 Task 가 단다(06d 는 06e 의 workPanelOpen 을 읽기만 한다 — 정함 30, spec §12-5)'>.
8. **PDF** — <H3 판정 — '했다. 인쇄 창 취소를 브라우저가 알려 주지 않아 창이 닫히면 내려받은 것으로 본다(단계 done 은 앞으로만 가는 도달 표시)' 또는 'PDF 내보내기(06e 마지막 Task) — 일정으로 자름(spec §12-6 자르는 순서 맨 앞)'>.
9. **리허설 전** — ETA 표본 섞임(06b 이월 §7-1), 3~5명 동시 사용 때 자동 보고서의 대기 길이(보고서 1건 = 생성 약 6건, 디스패처 전역 1건 — §12-8).
10. **해당 없음으로 닫은 06b 이월** — §7-3(개념 칩을 고쳐도 소속을 다시 세지 않음 — 06b 규칙 그대로, 목차 때 다시 센다), §7-6(`Section.model` 늘 null — D21 로 부록에 모델을 싣지 않는다).
11. **딥리드 참고문헌 질문(정함 31)** — 끊기던 것은 고쳤다(Task S2 의 `_book_references`). 참고문헌 목록이 없으면(책·참고문헌을 뽑지 못한 논문) 청크 검색으로 돌아가 본문 대목을 근거로 답한다(S2 quality 검토 반영). 남은 것은 의도 낱말이다 — `_REF_INTENT_KEYWORDS`(`book_chat.py:19-22`)를 부분 문자열로 보아, 목록이 있는 논문에서는 '이 인용 근거가 맞아?'·'출처가 어디야?'(spec §12-8 장면 3) 같은 본문 확인 질문도 청크 대신 참고문헌 목록을 받는다. 끊기지는 않지만 본문으로 확인한 답은 아니다. '인용'·'출처' 단독을 빼거나 '참고문헌'·'목록'과 함께 나올 때만 거는 좁히기는 사용자 결정 몫이다(기존 네 화면도 같은 길을 쓴다).
12. **방법 칸이 둘** — [목차 고치기] 안의 방법 칸과 문서 6절의 칸(`DocField`)이 같은 `outline.method` 를 고친다(시각 디자인 정리 때 하나로).

---

## 8. 다음 라운드 진입점

- **배포(10/17~18)** — 계획 Task Z4~Z7. 06d 가 dev 에 있으면 nuxt 이미지는 06e·06d 가 다 든 dev 로 한 번 만든다. 06c 기본값 커밋이 dev 에 있으면 이 배포로 운영에 켜진다.
- **10/19~21 운영 확인·수정 → 10/22 대회 배포 → 10/23 동결·리허설** — 시연용 자기 연구는 06e·06d 배포 뒤 새로 이어가기로 만든다(키워드 칩·자동 보고서 경로, §12-8). 예시 연구 3건은 그때 코퍼스로 다시 돌려 `mark_example.py` 로 지정한다.

---

## 상태
- [x] code-reviewer 정적 리뷰 통과(발견 사항 반영 완료) — 작업별 · 영역 여섯
- [x] 테스트 green — 백엔드 <N> · vitest <T> · typecheck 0 · build
- [ ] 수동 스모크 확인 — 운영 처음부터 끝까지 1회(§5)
- [ ] 문서 갱신 — `00_status` · spec (교본은 대회 뒤 round06 한 권 — D13)
- [ ] `dev` 머지 승인
- [ ] `dev→main` 머지 + push 완료
```

- [ ] **Step 2: `docs/roadmap/00_status.md` — round06 줄**

① 3행. 지금 줄의 머리를 본다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && sed -n '3p' docs/roadmap/00_status.md | grep -o '^최종 갱신: [0-9-]* ('
```

Expected: `최종 갱신: 2026-10-NN (` 한 줄(06c·06d 가 고쳤으면 그 날짜). 그 글자를 old 로 잡고 new 는 날짜를 이 Step 을 하는 날로 바꾼 뒤 괄호 바로 뒤에 06e 구절을 넣는다. 예: old `최종 갱신: 2026-10-14 (` → new

```markdown
최종 갱신: 2026-10-16 (round06e — 연구 어시스턴트 구현 완료(보고서 자동 산출·큰 진행 막대·내보내기 기본값·참고문헌 선택하기와 오른쪽 딥리드·인용 근거·제목 고르기·근거 칩·기록 total), `dev` 머지·배포 대기. 
```

(new 끝에 공백 하나가 있다 — 줄의 나머지는 그대로 이어진다.)

② round06 머리. old:

```markdown
** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색
```

new:

```markdown
 · 06e 구현 완료·`dev` 머지·배포 대기** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색
```

(new 는 공백으로 시작한다 — 앞의 06b·06c·06d 구절 뒤에 붙는다.)

③ round06 하위 줄 끝 — 06e 하위 줄을 round06 블록 맨 끝(다음 최상위 줄 `- **round07 종료**` 바로 앞)에 넣는다. old:

```markdown
- **round07 종료** — 적재 파이프라인 보강(
```

new(조건부 구절은 판정대로 — R6·H3·Z1):

```markdown
  - **06e 연구 어시스턴트 — 구현 완료** — 브랜치 `feat/round06e-assistant-auto-report`(worktree `.worktrees/round06e`, dev 에서 분기), 계획 `docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md`(Task 0 · A1~A5 · X1~X5 · R1~R6 · S1~S4 · K1~K9 · H1~H3 · Z1~Z7, 정함 1~31). 들어간 것: [보고서 만들기] 한 번에 목차 자동 확정(연구 질문 = 첫 후보 → 카드 질문, `auto`)과 보고서 화면의 절 연쇄(선행연구 묶음·연구 공백을 문서 순서대로 하나씩, 근거 없는 절은 건너뜀), 보고서 화면 머리의 큰 진행 막대(사용자 Q1 답을 보고서 화면에도 — 2026-10-11 확인)·머리 목차·문서 자리 1~6·연구 배경·방법 칸·'검토할 곳', 연구 공백 '확인했다' 단정 다듬기(06b 이월 §7-13), 내보내기 기본값(모든 문단·워터마크 없음·부록 상태별 개수·'수락한 문단만'), 단계 이름 '제목 고르기'·'참고문헌 선택하기'·'보고서'(Q2 기본), 오른쪽 딥리드 패널(논문별 대화·출처 칩 [원문 보기])·인용 근거 탭(`GET …/sections/{key}/sources` — 모델이 본 원문 대목 하이라이트)·딥리드 논문 프롬프트, 후보 키워드 칩(LLM + 채택 논문 키워드, `PAPER_KEYWORD_MIN_N` <1|2>)·카드 제목 키워드(06c `terms.contains`)·하이라이트·[이 키워드로 다시 만들기], 주제 카드 근거 칩 제1저자 전체 이름 연도(Q3 S·06b 이월 §7-14), 기록 목록 kind 별 `total`<H3 이면 '·보고서 PDF'><R6 이면 '·LNB 접기 연결(06d 먼저 머지)'>. 스키마 변경 없음(JSONB·응답 안 모양만). 배포 절차는 계획 Task Z4~Z6. 상세: `round06e-완료노트.md`.
- **round07 종료** — 적재 파이프라인 보강(
```

④ 다음 할 일의 06e 줄 머리. old:

```markdown
  - **06e 연구 어시스턴트(10/17~18 배포 — 워커·fastapi·nuxt)** — 브랜치 `feat/round06e-assistant-auto-report`.
```

new:

```markdown
  - **06e 연구 어시스턴트 — 구현 완료, `dev` 머지·배포 대기(10/17~18 — 워커·fastapi·nuxt)** — 계획 `docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md` 의 Task Z4(`dev` 머지, 사용자 승인 — 06c 운영 배포 뒤, 기본 06e 먼저) → Z5(워커 셋 → fastapi → nuxt → 게이트웨이 reload, 사용자 — 06d 가 dev 에 있으면 nuxt 를 한 번에 함께, dev 의 06c 기본값 커밋 포함) → Z6(운영 처음부터 끝까지 1회 — [보고서 만들기] 에서 Word 까지 소요·대기 순번) → Z7(기록) 순서. 브랜치 `feat/round06e-assistant-auto-report`.
```

(줄의 나머지 — 보고서 자동 산출·… 설명 — 는 그대로 이어진다.)

⑤ 라운드 이력의 round06 칸. 지금 칸의 '남음' 구절에서 06e 를 뺀다. old 가 `· 06c·06d·06e 남음(2026-10-08 재정의 — spec §12) |` 이면 new:

```markdown
· 06e 구현 완료·배포 대기(`feat/round06e-assistant-auto-report`) · [완료노트](round06e-완료노트.md) · 06c·06d 남음(2026-10-08 재정의 — spec §12) |
```

06c·06d 가 먼저 기록해 old 가 `· 06e 남음(2026-10-08 재정의 — spec §12) |` 이면 new 는 `· 06e 구현 완료·배포 대기(\`feat/round06e-assistant-auto-report\`) · [완료노트](round06e-완료노트.md) |` 다. old 가 `· 06d·06e 남음(…) |` 이면 `06d 남음` 을 남기고 06e 구절을 앞에 넣는다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && grep -c "round06e-완료노트.md" docs/roadmap/00_status.md && grep -c "06e 연구 어시스턴트(10/17~18 배포 — 워커·fastapi·nuxt)" docs/roadmap/00_status.md && sed -n '3p' docs/roadmap/00_status.md | grep -c "round06e — 연구 어시스턴트 구현 완료"`

Expected: `2`(하위 줄의 '상세'·라운드 이력), `0`(옛 다음 할 일 머리가 남지 않았다), `1`.

- [ ] **Step 3: spec 을 코드에 맞춘다 (`docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`)**

① 3행 머리 상태 줄. old:

```markdown
. **06c~06e 는 2026-10-08 시연 회의와 같은 날
```

new(H3 판정대로 '·PDF' 를 넣거나 뺀다):

```markdown
 · 06e 구현 완료(2026-10-16 — 보고서 자동 산출·큰 진행 막대·내보내기 기본값·참고문헌 선택하기와 오른쪽 딥리드·인용 근거·제목 고르기·근거 칩·기록 total·PDF, `dev` 머지·배포 대기). **06c~06e 는 2026-10-08 시연 회의와 같은 날
```

(06c·06d 가 같은 자리 앞에 구절을 넣었어도 이 old 는 그대로 맞는다 — 06e 구절이 그 뒤에 붙는다.)

② D2 행 — 산출물 이름. old:

```markdown
산출물 이름은 열린 질문(§12-10) |
```

new:

```markdown
산출물 이름은 '보고서'(§12-10 Q2 — 답이 없어 기본값으로 구현, 06e 계획 정함 1. 이름 낱말은 `utils/workPhase.ts` 의 `FINAL_STEP_NAME` 하나다) |
```

③ D20 행 — 구현 방식. old:

```markdown
결과·논의·가설 수치를 쓰지 않는 것(D2)은 그대로다 |
```

new:

```markdown
결과·논의·가설 수치를 쓰지 않는 것(D2)은 그대로다. **06e 구현:** 목차 반영(`outline.apply`)이 연구 질문이 있을 때만 승인 목차(`auto: true`)로 저장하고(없으면 06b 처럼 초안), 절 연쇄는 보고서 화면의 `useAutoReport` 가 `utils/proposalView.ts` 순수 함수(`autoChainOn`·`autoTargets`·`nextAutoSection`)로 서버 값(`outline.auto`·ProposalView `section_gens`)에서 매번 다시 계산해 하나씩 넣는다(근거 없음 409 는 `{"code": "no_section_papers"}` 로 건너뜀). 화면 머리에 큰 진행 막대(`reportBar` — 사용자 확인 2026-10-11)·머리 목차·문서 자리 1~6·'검토할 곳' 줄, 연구 배경은 `outline.background`, 연구 공백 단정은 '소장 코퍼스 범위' 문장에서만 다듬는다(06e 계획 정함 3~11·28) |
```

④ D21 행. old:

```markdown
문단 상태와 `research_generations.model`·`output.attempts` 저장은 그대로다 |
```

new:

```markdown
문단 상태와 `research_generations.model`·`output.attempts` 저장은 그대로다. **06e 구현:** `ProposalDocInput.acceptedOnly`(기본 false — 네 상태 전부·워터마크 없음, 켜면 수락·수정·직접 작성만과 파일 이름 꼬리 `_수락문단만`), 2절에 연구 배경, 부록은 상태별 개수·실은 문단·검토할 곳·날짜·결과·논의 미포함(모델·시도 줄 없음). 보고서 출력의 워터마크 그리기는 그대로다(06e 계획 정함 13) |
```

⑤ D23 행. old:

```markdown
[더 구체적으로]를 덮는다 |
```

new(Z1 판정대로):

```markdown
[더 구체적으로]를 덮는다. **06e 구현:** 후보 = LLM 후보 + 채택 논문 키워드 문서 빈도(`services/research_work/keywords.py` — 상한 10·일반어 거르기·위 3개 미리 선택, 논문에만 있는 후보는 <1|2>편부터 — 운영 채움률 측정, 06e 계획 정함 14), 카드는 개념 반영 때 씨앗 자리마다 한 번(정함 29), 제목 검사는 06c `terms.contains`, 세 번 다 놓친 카드는 무른 검사로 경고와 함께 보인다(정함 17). 최소 선택 2·직접 더하기 남김·고른 카드는 다시 만들지 않음(정함 15·16) |
```

⑥ D24 행. old:

```markdown
§5-5 '뒷받침 점수'를 덮는다 |
```

new:

```markdown
§5-5 '뒷받침 점수'를 덮는다. **06e 구현:** 공용 패널 `DeepReadPanel`(2단 sticky 22rem·1200px 미만 서랍·768px 이하 전체 폭)을 ReadingStep·ProposalStep 이 쥐고, BookChat 스트림을 `useDeepReadChat`·`deepReadSse` 로 뺐다(논문별 대화·AbortController). 출처 칩 글자는 저장값 그대로, [원문 보기]만 뷰어 쪽(06e 계획 정함 20~22). 인용 근거는 새 `GET /api/research/{id}/sections/{key}/sources`(생성 행의 `input.papers` — 정함 23)·대목 하이라이트는 글자 n-gram 겹침, 칩은 저장된 문단에서만 패널을 연다(정함 24) |
```

⑦ D27 행. old:

```markdown
열린 질문으로 둔다 |
```

new:

```markdown
열린 질문으로 둔다. **06e 구현:** Q3 답이 없어 S(주제 카드 칩만 — `topicDeck.ts` 의 `chipLabel`·`chipTooltip`, `SHORT_TITLE_MAX` 18)로 했다. `citeLabel` 은 그대로(06e 계획 정함 2) |
```

⑧ §12-3 오프셋 행 — 정함 28. old:

```markdown
인쇄에서 숨기고 단계 화면(`stepMode`)에서는 그리지 않는다 |
```

new:

```markdown
인쇄에서 숨기고 단계 화면(`stepMode`)에서는 그리지 않는다 — 06e 보고서 화면은 같은 크기 규칙의 자기 막대(`work.css` 의 `.wk-rbar`, 토큰 `--wk-bar-thick`)를 따로 그린다(06e 계획 정함 28 — 사용자 확인 2026-10-11) |
```

⑨ §12-4 의 옛 줄 번호와 카드 시점 — 네 군데를 Edit 한다(old 는 줄의 일부 — 그 글자가 spec 에 한 번만 있다).

old:

```markdown
사용자가 고친 글도 다시 검사한다(`paragraph_edit.py:192-209`)
```

new:

```markdown
사용자가 고친 글도 다시 검사한다(`paragraph_edit.py:48-65` `revalidate`)
```

old:

```markdown
카드 input 에 `keywords` 를 싣는다(`seeds.py:346-362` `topic_input`
```

new:

```markdown
카드 input 에 `keywords` 를 싣는다(`seeds.py:175-191` `topic_input`
```

old:

```markdown
열린 생성은 건너뛴다(`enqueue.py:251-255`)
```

new:

```markdown
열린 생성은 건너뛴다(`enqueue.py:34-38`)
```

old:

```markdown
한 번만: 그 연구에 `topic_card` 생성이 한 번도 없을 때만 4건을 넣는다
```

new:

```markdown
한 번만: 씨앗 자리(최대 4)마다 그 자리에 `topic_card` 생성이 한 번도 없을 때만 넣는다(06e 계획 정함 29 — '그 연구에'로 세면 개념 생성이 줄을 서는 사이 [다른 방향]을 누른 연구에 씨앗 카드가 영영 생기지 않는다. [다른 방향]은 개념 생성이 열려 있으면 409 `KEYWORDS_BUSY`)
```

⑩ §12-10 Q2·Q3. old(Q2 줄 끝):

```markdown
06e 구현 중(이름 바꾸기 Task 전) · '보고서']
```

new:

```markdown
06e 구현 중(이름 바꾸기 Task 전) · '보고서'] — **답이 없어 '보고서'로 구현했다**(06e 계획 정함 1 — 이름 낱말은 `FINAL_STEP_NAME` 하나이고 조사가 붙는 문장은 글자 그대로다. '연구 초안'으로 바꾸면 상수 한 줄과 `grep -rn "보고서[를로가는의은이]" frontend/components/work frontend/utils/workPhase.ts frontend/utils/readingList.ts` 가 내는 문장 중 마지막 단계를 가리키는 것·그 테스트를 고친다). '딥리서치'·'목차' 용어는 그대로
```

old(Q3 줄 끝):

```markdown
[06e · 구현 중 · 제안 표기에 S]
```

new:

```markdown
[06e · 구현 중 · 제안 표기에 S] — **답이 없어 S(주제 카드 칩만)로 구현했다**(06e 계획 정함 2). M(다섯 곳 통일)은 06e 완료노트 §7 이월
```

⑪ §12-11 아홉 항목 — 줄마다 통째로 갈음한다(old 는 c5d05b0 의 줄 전체, new 의 꺾쇠 `<1|2>` 는 Task Z1 판정 값으로 바꾼다. 06d 가 §12-11 의 다른 두 줄(PlanCard·소장자료)을 고쳤어도 아래 아홉 줄과 겹치지 않는다).

old:

```markdown
- **키워드 후보 원천** — 논문 키워드 채움률을 잰 뒤 LLM 후보와 합칠지(§12-4 제목 고르기).
```

new:

```markdown
- ~~**키워드 후보 원천**~~ — 정함(권고 — 06e 계획 정함 14): LLM 후보 + 채택 논문 키워드 문서 빈도를 합친다. 운영 채움률 측정(`research/round06e-keyword-candidates/`)으로 논문에만 있는 후보는 <1|2>편부터.
```

old:

```markdown
- **키워드 최소 선택 수** — 권고 2(묶음 수가 키워드 수 이하). 자유 입력('직접 더하기')을 남길지.
```

new:

```markdown
- ~~**키워드 최소 선택 수**~~ — 정함(권고 — 06e 계획 정함 15): 2. 직접 더하기는 남긴다(출처 배지 '직접').
```

old:

```markdown
- **고른(`picked`) 카드도 키워드를 바꾸면 다시 만들지** — 권고: 다시 만들지 않는다(목차 '다시 맞춤 필요'를 피한다).
```

new:

```markdown
- ~~**고른(`picked`) 카드도 키워드를 바꾸면 다시 만들지**~~ — 정함(권고 — 06e 계획 정함 16): 다시 만들지 않는다(고친·직접 쓴·접은 카드도).
```

old:

```markdown
- **키워드를 세 번 다 놓친 카드** — 지금 규칙이면 빈 결과('근거 부족' — 잘못된 안내)가 된다. 권고: 실행기(`generate.py`)에 무른 검사를 더해 마지막 통과 출력을 보관하고, '제목에 ○○ 없음' 경고를 단 채 보인다.
```

new:

```markdown
- ~~**키워드를 세 번 다 놓친 카드**~~ — 정함(권고 — 06e 계획 정함 17): `Executor.soft_check` 로 마지막 무른 통과 출력을 보관해 '제목에 「…」 없음' 경고와 함께 보인다.
```

old:

```markdown
- **연구 배경 저장** — 권고: `outline.background` 자유 글(`method` 처럼 — `OutlinePut` `research_proposal.py:74-78`, `types/work.ts:183`, `progress.py:196`, `proposalDocument.ts:120-121`). 대안: `sections.background` 의 사용자 작성 문단(지금 PUT 은 절이 없으면 404).
```

new:

```markdown
- ~~**연구 배경 저장**~~ — 정함(권고 — 06e 계획 정함 7): `outline.background` 자유 글(상한 2000 — `OutlinePut`, `types/work.ts`, `progress.py:43` `sections_filled`, `proposalDocument.ts` 2절). 대안 `sections.background` 는 쓰지 않았다.
```

old:

```markdown
- **문단 버튼 줄을 기본으로 접을지**(hover·포커스·절 단위 [편집]).
```

new:

```markdown
- ~~**문단 버튼 줄을 기본으로 접을지**~~ — 정함(06e 계획 정함 12 — 권고 없음, 계획이 정함): 접지 않는다.
```

old:

```markdown
- **'검토할 곳' 요약·'근거 없음' 배지·부록 수**(§12-4 보고서 자동 산출)를 넣을지.
```

new:

```markdown
- ~~**'검토할 곳' 요약·'근거 없음' 배지·부록 수**~~ — 정함(06e 계획 정함 11): 요약 줄과 부록 수는 넣고, 보이는 '근거 없음' 배지는 넣지 않는다(화면낭독 글만).
```

old:

```markdown
- **딥리드 프롬프트의 논문 변형** — `app/services/chat/book_chat.py:135` 가 `doc_type` 을 넘기지 않아 논문에도 책 문구가 나간다. 권고: 새 `app/domains/nl_library/prompts/book_chat.paper.yaml` + `get_prompt("book_chat", book.doc_type)`(06e fastapi 배포, 동등성 테스트 `test_prompts.py:124`·`app/scripts/verify_prompt_parity.py:84-86` 맞춤). 채택하면 두 파일은 06e 경계다(§12-5).
```

new:

```markdown
- ~~**딥리드 프롬프트의 논문 변형**~~ — 정함(권고 — 06e 계획 정함 18): 채택 — 새 `book_chat.paper.yaml` + `book_chat.chat_prompt(book)`. `BookOut` 에 `doc_type` 이 없어(spec 이 가정한 `book.doc_type`) 선택 필드로 더했다.
```

old:

```markdown
- **연구 맥락을 반영한 딥리드 첫 화면**(기존 `POST /api/papers/reason/stream`·추천 질문 칩) — 선택.
```

new:

```markdown
- ~~**연구 맥락을 반영한 딥리드 첫 화면**(기존 `POST /api/papers/reason/stream`·추천 질문 칩)~~ — 정함(06e 계획 정함 19): 하지 않는다(선택 항목).
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && S=docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && grep -c "06e 계획 정함" $S && grep -cE "paragraph_edit.py:192-209|seeds.py:346-362|enqueue.py:251-255|progress.py:196|그 연구에 .topic_card. 생성이 한 번도 없을 때만" $S && grep -c "06e 구현 완료(" $S && grep -c '<[12]|[12]>' $S`

Expected: 첫 수 `19`(D2·D20·D21·D23·D24·D27·§12-3 오프셋 행·§12-4 카드 시점·Q2·Q3·§12-11 아홉 줄 — 줄마다 한 번 센다), 둘째 `0`(옛 줄 번호·옛 문구가 남지 않았다), 셋째 `1`, 넷째 `0`(판정 자리가 남지 않았다).

- [ ] **Step 4: 반복 함정 — 이번에는 더하지 않는다는 판단을 적는다**

`docs/ops/recurring-gotchas.md` 는 라이브(docker·실데이터)에서만 드러난 패턴을 적는다. 06e 는 아직 운영 전이라 더할 것이 없다 — Task Z7 이 운영 확인의 관찰을 보고 다시 판단한다(예: 워커만 먼저 바뀐 사이 이어간 연구의 카드가 생기지 않으면, 연쇄가 디스패처 대기에 몰려 순번이 길면, 딥리드 SSE 가 게이트웨이 버퍼링으로 한꺼번에 오면, 인쇄 창 PDF 가 브라우저마다 다르면). 이 Step 은 파일을 고치지 않는다.

- [ ] **Step 5: 문서 리뷰 — code-reviewer 하나**

`.claude/agents/code-reviewer.md` 서브에이전트(subagent_type `code-reviewer`)에게 문서 일관성 리뷰를 맡긴다. 프롬프트:

```text
round06e 문서 리뷰(일관성). 저장소 C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e 에서 docs/roadmap/round06e-완료노트.md(새), docs/roadmap/00_status.md 의 round06 줄, docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md 의 머리 상태 줄·D2·D20·D21·D23·D24·D27·§12-3 오프셋 행·§12-4(카드 시점·고친 줄 번호)·§12-10 Q2·Q3·§12-11 을 읽고, 코드(app/services/research_work/outline.py·keywords.py·topic_card.py·markers.py·proposal_views.py, app/api/research_proposal.py·research_topics.py·history.py, frontend/utils/workPhase.ts·proposalView.ts·proposalDocument.ts·topicDeck.ts·deepRead.ts·citationEvidence.ts, composables/useAutoReport.ts·useDeepReadChat.ts, components/work/ProposalStep.vue·DeepReadPanel.vue, assets/css/work.css 의 .wk-rbar)와 계획 docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md 의 정함 1~31 에 맞는지 본다. 특히 상수·문구(FINAL_STEP_NAME '보고서'·OUTLINE_BACKGROUND_MAX 2000·MAX_KEYWORD_CANDIDATES 10·PRESELECT 3·MIN_PICKED_KEYWORDS 2·PAPER_KEYWORD_MIN_N(Task Z1 판정)·SHORT_TITLE_MAX 18·--wk-bar-thick 1rem/0.75rem·'_수락문단만'·'AI 작성 · 검토 전')가 문서마다 같은지, 완료노트 §2·§6·§7 의 조건부 구절(R6·H3·Z1 판정)이 실제로 한 Task 와 맞는지, spec 의 줄 번호 고침(paragraph_edit.py:48-65·seeds.py:175-191·enqueue.py:34-38·progress.py:43)이 실제 코드 줄과 맞는지, 정함 28 이 '사용자 확인 2026-10-11'로 적혔고 '확인 대기'·'질문' 서술이 남지 않았는지, stale 서술('계획서'·'읽기 목록'·'핵심 개념'을 단계 이름으로 쓰는 곳, '산출물 이름은 열린 질문')이 남았는지. 보고는 code-reviewer 형식.
```

Expected: 결함 목록(없으면 "없음"). 발견은 Edit 로 고친다(같은 커밋에 넣는다).

- [ ] **Step 6: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && ! grep -n '<[^>]*>' "docs/roadmap/round06e-완료노트.md" && git add "docs/roadmap/round06e-완료노트.md" && git add docs/roadmap/00_status.md && git add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git status --short && git commit -m "[Docs] round06e — 완료노트(왜·한 일·리뷰·검증·결정 정함 1~31·조건부 Task 판정·이월, 배포 전)와 현재 상태(round06 줄 — 06e 구현 완료·배포 대기, 다음 할 일은 계획 Task Z4~Z7 의 머지·배포·운영 확인 순서), spec 을 코드에 맞춘다: 머리 상태 줄, D2 산출물 이름 '보고서'(Q2 기본), D20·D21·D23·D24·D27 구현 방식, §12-3 — 06e 보고서 화면은 자기 큰 진행 막대를 그린다(정함 28, 사용자 확인 10-11), §12-4 의 옛 줄 번호 넷과 씨앗 카드 '한 번만'을 씨앗 자리마다로(정함 29), §12-10 Q2·Q3 기본값으로 구현, §12-11 아홉 항목을 정함으로 닫음"
```

Expected: `grep` 이 찍는 줄 없이 커밋 1개(`git status --short` 의 세 줄 `A `·`M `·`M ` 과 커밋 요약만 나온다). 완료노트에 꺾쇠 자리가 남았으면 그 줄을 행 번호와 함께 찍고 커밋하지 않은 채 멈춘다 — Step 1 의 규칙대로 채운 뒤 같은 명령을 다시 돌린다.

---

### Task Z4: (사용자 승인) dev 머지 — 머지 문 확인·조건부 Task 판정·임시 worktree

**왜:** GIT_WORKFLOW — dev 머지는 매번 사용자 승인. §12-6 머지 문 — 06e 는 06c 운영 배포(10/13~14)가 끝난 뒤에만 dev 에 들어간다. Task K9 는 06c 의 `contains` 를 쓰므로 06c 를 받은 뒤라야 하고, 06d 가 먼저 들어왔으면 LNB 접기(Task R6)를 단 뒤 머지한다. dev 머지가 배포보다 먼저다 — 06e 가 운영에 있고 dev 에 없는 동안 다른 세션이 dev 로 `:latest` 를 빌드·Recreate 하면 06e 가 말없이 되돌려진다(06a 사용자 결정 2026-10-03). **머지 뒤 배포(Task Z5)를 미루지 않는다** — 그 사이 다른 세션이 dev 로 만든 이미지로 `fastapi` 만 먼저 Recreate 하면 새 fastapi + 옛 `celery-research-plan` 이 되어, 그 사이 이어간 연구는 주제 행만 생기고 카드 생성이 영영 들어가지 않는다(카드는 새 워커의 개념 반영이 넣는다 — Task K5).

**Files:** 없음(머지 커밋만 — 문서 충돌이 났으면 그 해결)

- [ ] **Step 1: 머지 문·조건부 Task 를 확인한다(작업 트리를 건드리지 않는다)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e
git fetch origin dev:dev
git log --oneline --merges dev | grep -c "feat/round06c-query-broadening"
git show dev:docs/roadmap/round06c-완료노트.md | grep -c "5-2\. 서버 배포"
git log --oneline --merges HEAD | grep -c "feat/round06c-query-broadening"
grep -c "^from services.research.terms import contains" app/services/research_work/topic_card.py
git log --oneline --merges dev | grep -c "feat/round06d-research-progress-screen"
grep -c "is-lnb-collapsed" "frontend/pages/research/[id].vue"
M=$(git log --format=%H --merges -1 --grep="feat/round06d-research-progress-screen" dev); [ -z "$M" ] && echo "06d 머지 없음" || { git merge-base --is-ancestor "$M" HEAD && echo "06d 머지를 받았다" || echo "06d 머지를 받지 않았다"; }
grep -c "PDF 로 내려받기" frontend/components/work/ProposalStep.vue
git log --oneline --merges dev | grep -c "feat/round06e-"
```

Expected와 판단:
- ① 06c 머지 → `1` 이상, 06c 완료노트의 `5-2. 서버 배포`(배포 기록) → `1` 이상 — 06c 운영 배포가 끝났다. 둘 중 하나라도 `0` 이면 **머지하지 않고 멈춘다**(머지 문이 아직 닫혀 있다 — 06c 세션의 배포·기록을 기다린다. 사용자가 06c 배포가 끝났다고 따로 확인해 주면 그 문장과 날짜를 적고 진행한다).
- ② HEAD 의 06c 머지 → `1` 이상, `contains` import → `1` — Task K9 를 했다. `0` 이면 K9 부터 한다(그 뒤 Task Z2 Step 1·2 를 다시 돌리고 K9 의 diff 를 리뷰어 D·E·F 에 보인다 — Z2 Step 5 의 되풀이 규칙).
- ③ 06d 머지 → `0` 이면 06e 가 먼저 들어간다 — `is-lnb-collapsed` 는 `0` 이 맞고(R6 건너뜀) 다음 줄은 `06d 머지 없음`. `1` 이상이면 06d 가 먼저 들어왔다 — `is-lnb-collapsed` 가 `1` 이상이고 다음 줄이 `06d 머지를 받았다` 여야 한다. 06d 머지가 있는데 R6 을 하지 않았거나 그 머지를 받지 않았으면 **이 Task 를 멈추고 Task R6 을 한다**(R6 이 dev 를 받고 `[id].vue:3-7` 두 곳을 단다) → Task Z2 Step 1·2 를 다시 돌린다 → R6 의 diff 를 리뷰어 C 에 보인다 → 이 Step 부터 다시.
- ④ `PDF 로 내려받기` → `1`(Task H3 를 했다) 또는 `0`(건너뜀) — 완료노트 §2·§6·§7 의 H3 구절과 맞는지 본다.
- ⑤ 06e 머지 → `0`.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e
git log --oneline HEAD..dev
git merge-tree --write-tree --name-only dev HEAD; echo "exit=$?"
```

Expected:
- `HEAD..dev` — 빈 출력이거나 K9·R6 뒤 dev 에 들어온 커밋(06c 의 판정 기록·기본값 커밋, 06d 의 기록, 다른 라운드의 문서 등). 코드 커밋이 있으면 적어 둔다(Task Z5 Step 1 의 빌드 확인이 처리한다)
- `merge-tree` — 트리 OID 한 줄과 `exit=0`(충돌 없음). `exit=1` 이면 충돌 파일을 본다:
  - `docs/roadmap/00_status.md`·`docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` 만이면 아래 규칙으로 푼다.
  - `app/`·`frontend/` 의 파일이 나오면(06d 가 R6 뒤 다시 들어왔거나 다른 라운드가 같은 줄을 고쳤다) **머지를 멈추고** 06e worktree 에서 `git merge dev` 로 먼저 받아 푼 뒤(`[id].vue` 는 `:57-75`·`workPanelOpen`·R6 두 곳이 06e 쪽, 그 밖은 dev 쪽. `work.css` 는 근거 장부 블록이 dev 쪽, 표시 줄 위 묶음이 06e 쪽) Task Z2 Step 1·2 를 다시 돌리고 이 Step 부터 다시 한다. 푸는 방법이 분명하지 않으면 사용자와 정한다.
- 문서 충돌 규칙: 어느 한쪽을 통째로 고르지 않는다. `00_status.md` 3행은 dev 쪽 줄을 바탕으로 날짜를 머지하는 날로 바꾸고 괄호 맨 앞에 Task Z3 Step 2 ① 의 `round06e — … 배포 대기. ` 구절만 넣는다. round06 머리·하위 줄·다음 할 일·라운드 이력은 세 줄이 함께 쓰는 블록이다 — dev 쪽 줄(06c·06d 구절이 있으면 그대로)을 남기고 이 브랜치의 06e 구절(머리의 ` · 06e 구현 완료·…`·06e 하위 줄·06e 다음 할 일 줄·이력의 06e 칸)만 더한다. spec 3행·D 행·§12 의 줄도 같은 방법이다 — dev 쪽 글에 06e 구절만 더한다. 다 풀면 `grep -cE '^(<<<<<<<|=======|>>>>>>>)' docs/roadmap/00_status.md docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` 가 두 줄 모두 `:0`.

- [ ] **Step 2: 사용자에게 승인을 받는다**

리뷰를 마친 커밋(Task Z2 Step 5)·문서 커밋(Task Z3 Step 6)·Task Z1 의 판정(`PAPER_KEYWORD_MIN_N`·구분자)·조건부 Task 판정(R6·H3)·Step 1 의 출력(머지 문·충돌 없음)과 Task Z5 의 배포 경우(가 06d 와 함께 / 나 06e 만 / 다 06d 가 이미 운영 — Task Z5 Step 1 의 표)를 보이고 "06e 를 dev 에 머지하고 이어서 배포(Task Z5)를 한다" 는 승인을 받는다. 승인 문장과 날짜를 적어 둔다(완료노트 '상태').

- [ ] **Step 3: 임시 worktree 에서 머지하고 바로 지운다**

본 작업 폴더가 아니라 임시 worktree 에서 머지한다. 그 폴더 안으로 `cd` 하지 않는다 — 셸이 그 안에 있으면 Windows 가 폴더를 지우지 못해 빈 폴더가 남는다(06b 완료노트 §7-17).

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/dev-merge dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge merge --no-ff feat/round06e-assistant-auto-report -m "Merge feat/round06e-assistant-auto-report into dev — round06e 연구 어시스턴트(보고서 자동 산출·큰 진행 막대·내보내기 기본값·참고문헌 선택하기와 오른쪽 딥리드·인용 근거·제목 고르기·근거 칩·기록 total·PDF), 워커·fastapi·nuxt·스키마 변경 없음"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge push origin dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c dev-merge
```

H3 을 건너뛰었으면 머지 메시지 괄호 안의 `·PDF` 를 뺀다.

Expected: 머지 커밋 한 줄(완료노트 §5-1 에 적는다), push 성공, 마지막 줄 `0`. 충돌이 났으면 Step 1 의 문서 규칙으로 `.worktrees/dev-merge` 의 두 문서를 Edit 로 고친 뒤 `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge add docs/roadmap/00_status.md && git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge commit --no-edit` 로 머지를 끝내고 push 한다.

머지한 뒤 06d 세션(사용자)에게 알린다(06d 머지가 `0` 이었을 때): "06e 가 dev 에 들어갔다(머지 커밋 `…`) — 06d 는 dev 를 받아 LNB 접기 연결 Task 를 하고 머지한다. 배포는 06d 머지를 기다려 한 번에 할지(06e 계획 Task Z5 경우 가) 06e 만 먼저 낼지(경우 나) 사용자와 정한다."

---

### Task Z5: (사용자) 운영 배포 — 워커 셋 → fastapi → nuxt → 게이트웨이 reload (10/17~18)

**왜:** §12-6 — 06e 는 워커(`celery-research-plan` 의 생성 실행기 — 목차 자동 승인·새 개념 실행기·카드 시점·카드 키워드·무른 검사)·fastapi(06e API·history total·`BookOut.doc_type`·딥리드 논문 프롬프트)·nuxt 다. 스키마 단계는 없다(JSONB·응답 안 모양만 — 함정 14). 10/17~18 배포는 dev 에 있는 06d 화면과 06c 기본값 커밋도 함께 낸다 — 이 Task 가 그 배포의 정본이다(06d 계획의 배포 Task 는 함께 내는 경우 이 Task 를 따른다). Step 1 의 빌드는 개발 PC, 나머지는 **사용자가** 서버에서 한다.

**Files:** 없음

**알아 둘 것:**
- **경우 셋(Step 1 이 가른다).** **가** — 06d 가 dev 에 있고 아직 운영에 없다(기본 — 06e → 06d 머지 뒤 배포 한 번): 이 Task 하나로 06c 기본값·06e·06d 를 함께 내고, nuxt 이미지는 둘이 다 든 dev 로 한 번만 만든다. nuxt Recreate 뒤 06d 계획의 배포 Task 의 마지막 Step('06d 가 운영 nuxt 에 들었는지')을 이어서 한다. **나** — 06d 가 dev 에 없다(06d 가 늦다): 06e 만 낸다. 06d 는 뒤에 nuxt 만 낸다. 오늘 06d 머지가 예정돼 있으면 기다릴지 먼저 사용자에게 묻는다(기다리면 경우 가). **다** — 06d 가 이미 운영에 있다(06d 먼저 — Task R6 을 했다): 절차는 같다(nuxt 는 06d·06e 가 다 든 dev).
- **순서의 까닭:** ① **워커가 fastapi 보다 먼저다** — 새 fastapi 의 이어가기는 주제 행만 만들고 카드 생성은 워커가 개념(키워드) 생성을 반영할 때 넣는다(Task K5 — `apply.py` → `enqueue_seed_cards`). 옛 `celery-research-plan` 이 그 반영을 하면 카드가 영영 들어가지 않는다. 거꾸로 새 워커 + 옛 fastapi 는 안전하다 — 옛 이어가기가 카드 생성을 바로 넣고, 새 워커의 `enqueue_seed_cards` 는 생성이 이미 있는 씨앗 자리를 건너뛴다(정함 29). 새 실행기는 없는 입력 키를 빈 값으로 읽는다(`input.get("keywords") or []`·`input.get("paper_keywords") or []`). 워커와 nuxt 사이에 옛 화면에서 [목차 만들기]를 누르면 새 워커가 목차를 자동 승인한다 — 옛 화면에는 승인 목차와 빈 절이 보이고, nuxt 가 바뀐 뒤 그 보고서 화면을 열면 `auto` 가 참이라 연쇄가 남은 절을 넣는다(스스로 풀린다). ② `celery-research`(딥리서치 실행)는 06e 가 코드를 바꾸지 않지만 06c 기본값 커밋이 dev 에 있으면 그 값을 읽고, 워커 셋을 fastapi 와 같은 이미지로 맞추는 것이 롤백의 전제다(06b 선례). ③ `celery-control`(회수기·디스패치 틱)도 같은 이미지로 맞춘다 — 06e 의 카드 생성은 워커 `_close` 의 `has_queued → send_dispatch` 와 이 틱이 집는다. ④ 적재 워커(`celery-worker`·`celery-cpu`·`celery-llm`·`celery-embed`)와 `celery-beat` 는 Recreate 하지 않는다 — 스택 업데이트 금지(함정 16). ⑤ fastapi·nuxt 를 Recreate 했으니 마지막에 `nginx -s reload`(함정 20).
- **비었는지 확인에 생성을 넣는다** — 06e 부터 보고서 화면이 생성을 이어 넣는다. `research_generations` 의 queued·running 이 남은 채 `celery-research-plan` 을 Recreate 하면 도는 생성이 끊긴다(회수기가 1140초 뒤 failed 로 닫는다).
- **서버 명령은 처음부터 root 셸(`su - root`)에서 한다** — `sudo` 가 아니다. 셸을 바꾸면 `pg`·`pgq`·`API`·`SID`·`OLD`·`NEW`·`OLD_NUXT`·`NEW_NUXT` 를 다시 정의한다.
- 함정: 3(운영은 `:latest`)·12(Portainer 에 pull 을 맡기지 않는다 — CLI `docker pull` 을 끝까지 기다린 뒤 "Re-pull image" 끄고 Recreate)·14(`alembic_version` 그대로)·16(바뀐 컨테이너만)·18(fastapi Recreate 전 `idle in transaction` 0)·20(reload, 확인은 게이트웨이 92 경유)·24(browser_active 429 가 안 풀리면).

- [ ] **Step 1: (개발 PC·서버) 경우를 가르고, 빌드 확인 뒤 이미지를 만든다**

개발 PC:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e
git fetch origin dev:dev
git log --oneline --merges dev | grep -c "feat/round06d-research-progress-screen"
git show dev:app/services/research/state.py | grep -E '^ +"(broaden|query_context)": [01],'
```

Expected: 06d 머지 수(`0` 또는 `1`), dev 의 기본값 두 줄(예: `    "broaden": 1,`·`    "query_context": 1,` — 06c 판정 결과).

서버(root 셸):

```bash
su - root                                                                              # 이 셸에서 끝까지 이어 쓴다
pg()  { docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; }
pgq() { docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA'; }
API=http://localhost:92/api
SID=$(cat /proc/sys/kernel/random/uuid)
docker exec nl-lib-nuxt sh -c 'grep -l "rs-pbar" /app/.output/public/_nuxt/entry.*.css | wc -l'
docker exec -w /app nl-lib-fastapi python -c "from services.research.state import DEFAULT_PARAMS as P; print(P.get('broaden'), P.get('query_context'))"
curl -s "$API/history?kind=research&limit=1" -H "x-session-id: $SID"; echo
```

Expected: `rs-pbar` 든 entry CSS → `0`(06d 가 운영에 없다) 또는 `1`(있다), 운영 기본값 한 줄(예: `0 0`), history `{"items":[],"next_cursor":null}`(06e fastapi 가 운영에 없다 — 새 브라우저 ID 라 빈 목록).
- 운영 기본값이 `None None` 이면 06c 가 운영에 없다 — 머지 문이 어긋났다. **멈추고** 사용자와 06c 세션에 알린다.
- history 에 `"total":0` 이 붙어 나오면 06e fastapi 가 이미 운영에 있다 — 예상 밖이다. 멈추고 누가 언제 냈는지 사용자와 확인한다.

| 06d dev 머지 | 06d 운영(`rs-pbar`) | 경우 |
|---|---|---|
| 1 | 0 | **가** — 06e·06d·06c 기본값을 이 Task 로 한 번에. nuxt Recreate 뒤 06d 계획 배포 Task 의 마지막 Step 을 이어서 |
| 0 | 0 | **나** — 06e 만(06d 는 뒤에 nuxt 만). 오늘 06d 머지가 예정이면 사용자에게 기다릴지 묻는다 |
| 1 | 1 | **다** — 06d 가 먼저 나갔다. 절차는 같다 |
| 0 | 1 | 예상 밖 — 멈추고 사용자와 정한다 |

빌드 확인(개발 PC) — 빌드는 dev 와 같은 트리에서 한다(다르면 dev 에 있고 빌드에 없는 코드를 이 이미지가 말없이 되돌리거나, 그 반대를 다음 dev 빌드가 되돌린다):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e
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
- `dev 에 HEAD 에 없는 코드 커밋` — 06e 머지 뒤에 dev 에 코드가 더 들어왔다(경우 가면 06d 머지가 그것이다 — 맞다). 06e worktree 에서 `git merge --ff-only dev`(위 확인을 지났으니 빨리 감기로 dev 와 같아진다) → Task Z2 Step 1 의 회귀(백엔드 전체·06e 묶음·06c 두 파일·typecheck·`Duplicated imports`·vitest·06e 프론트 묶음·그대로여야 하는 셋·build)를 다시 돌려 실패 0 을 본 뒤 → 위 확인부터 다시 하고 빌드한다. 다시 돈 수를 완료노트 §5-1 에 적는다. 새로 들어온 것이 06d 머지면 경우 표를 다시 본다.

이미지(개발 PC, 위 확인이 '빌드해도 된다' 로 끝난 같은 폴더) — 워커 셋과 fastapi 가 같은 app 이미지다. nuxt 는 원문 뷰어(`frontend/public/pdfjs`, gitignore)를 본 작업 폴더에서 복사한 뒤 만든다(06b Task 37 Step 9 와 같다):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && cp -r C:/Users/LANDSOFT/mygit/NL_library_AI/frontend/public/pdfjs frontend/public/ && ls frontend/public/pdfjs/web/viewer.html && git status --short
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && NL_LIB_NUXT_IMAGE=landsoftdocker/nl-lib-nuxt:latest bash scripts/build_dev_images.sh nuxt
```

Expected: `frontend/public/pdfjs/web/viewer.html`, `git status --short` 빈 출력(pdfjs 는 `frontend/.gitignore` 에 있다), `── FastAPI: landsoftdocker/nl-lib-fastapi:latest ──…`·`── Nuxt: landsoftdocker/nl-lib-nuxt:latest ──…` 뒤 build·push 로그, 끝마다 `완료. Portainer에서 nl-lib-dev 스택 Pull & Redeploy 하면 반영됩니다.`(스크립트의 고정 안내 — 운영은 아래 Step 으로 한다).

- [ ] **Step 2: (사용자, 서버) 전제 확인**

```bash
echo "SELECT version_num FROM alembic_version" | pgq                                  # 0007_research_work — 06e 는 바꾸지 않는다
OLD=$(docker inspect --format '{{.Image}}' nl-lib-fastapi); echo "$OLD" | cut -c1-19
OLD_NUXT=$(docker inspect --format '{{.Image}}' nl-lib-nuxt); echo "$OLD_NUXT" | cut -c1-19
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$OLD" ] && echo "$c 같음" || echo "$c 다름"
done
```

Expected: `0007_research_work`, 이미지 ID 앞 19자 두 줄, 세 줄 모두 '같음'.
- `alembic_version` 이 다르면 멈춘다(함정 14).
- '다름' 이 있으면 배포를 멈추고 되돌릴 이미지를 사용자와 정한다(롤백은 넷이 같은 이미지라는 전제다).

- [ ] **Step 3: (사용자, 서버) 되돌리기 태그를 남기고 새 이미지를 받는다**

```bash
docker tag "$OLD" landsoftdocker/nl-lib-fastapi:pre-round06e
docker tag "$OLD_NUXT" landsoftdocker/nl-lib-nuxt:pre-round06e
docker pull landsoftdocker/nl-lib-fastapi:latest                                      # 7GB 남짓 — 끝까지 기다린다
docker pull landsoftdocker/nl-lib-nuxt:latest
NEW=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-fastapi:latest); echo "$NEW" | cut -c1-19
NEW_NUXT=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-nuxt:latest); echo "$NEW_NUXT" | cut -c1-19
[ "$NEW" != "$OLD" ] && echo "새 fastapi 이미지 받음"                                 # pull 이 끝나기 전에 잡으면 옛 ID 다(06a 교훈)
[ "$NEW_NUXT" != "$OLD_NUXT" ] && echo "새 nuxt 이미지 받음"
```

Expected: pull 마다 마지막 줄 `Status: Downloaded newer image for …:latest`, 새 ID 앞 19자 두 줄, `새 fastapi 이미지 받음`·`새 nuxt 이미지 받음`. pull 만으로는 아무 컨테이너도 다시 시작되지 않는다(함정 16).

- [ ] **Step 4: (사용자, 서버) 비었는지 확인**

`celery-research` 를 Recreate 하면 도는 딥리서치가 끊긴다(회수기가 45분 뒤 failed 로 거둔다). `celery-research-plan` 을 Recreate 하면 도는 계획·생성이 끊긴다(1140초 뒤 failed). 적재 워커는 건드리지 않지만 적재가 적은 시간에 한다.

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

- [ ] **Step 5: (사용자, 서버) 워커 셋 Recreate — celery-research → celery-research-plan → celery-control**

Portainer 에서 컨테이너마다 Recreate 를 누르고 **"Re-pull image" 는 끈다**(함정 12). 스택 업데이트는 하지 않는다(함정 16). ① `nl-lib-celery-research` → ② `nl-lib-celery-research-plan` → ③ `nl-lib-celery-control` 을 차례로 Recreate 한 뒤:

```bash
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$NEW" ] && echo "$c 새 이미지" || echo "$c 옛 이미지"
done
docker exec nl-lib-celery-research-plan sh -c 'celery -A workers.celery_app inspect registered -d "celery@$(hostname)" --timeout 5' | grep -c "tasks.dispatch_research_work"
docker exec -w /app nl-lib-celery-research-plan python -c "from services.research_work.generate import Executor; from services.research_work.topic_card import EXECUTOR as T, enqueue_seed_cards; from services.research_work.concepts import EXECUTOR as C; print('soft_check' in Executor.__dataclass_fields__, T.soft_check is not None, C.bind is not None)"
docker exec -w /app nl-lib-celery-research-plan grep -c "keywords" domains/nl_library/prompts/research_topic_card.yaml domains/nl_library/prompts/research_concepts.yaml
for c in nl-lib-celery-research nl-lib-celery-research-plan; do
  printf '%s ' $c; docker exec -w /app $c python -c "from services.research.state import DEFAULT_PARAMS as P; print(P['broaden'], P['query_context'])"
done
```

Expected: 세 줄 모두 '새 이미지'(하나라도 '옛 이미지' 면 그 컨테이너를 다시 Recreate — 06b 배포에서 `celery-research` 가 한 번 옛 이미지로 나왔다), `1`(생성 디스패치 태스크가 그 워커에 있다), `True True True`(무른 검사·카드의 무른 검사·개념의 bind — 06e 실행기다), 두 프롬프트 파일 줄마다 `…:1` 이상(카드 프롬프트의 `{% if keywords %}`·개념 프롬프트의 출력 키 — 06e 전 이미지는 둘 다 `:0`), 두 워커의 기본값이 Step 1 의 dev 기본값과 같다(예: `nl-lib-celery-research 1 1`). `inspect` 는 `-d` 가 없으면 적재 워커까지 모든 워커에 묻는다 — 한 워커를 볼 때는 `-d "celery@$(hostname)"` 로 좁힌다.

- [ ] **Step 6: (사용자, 서버) fastapi Recreate**

fastapi 를 Recreate 하기 전에 `library_catalog` 를 쥔 채 멈춘 트랜잭션이 없는지 본다(함정 18 — lifespan 의 `ALTER TABLE library_catalog …` 가 배타 잠금을 기다리며 기동이 멈추고 그 뒤 조회가 줄 선다).

```bash
pg <<'SQL'
SELECT pid, state, xact_start, left(query, 80) FROM pg_stat_activity WHERE state = 'idle in transaction';
SQL
# 0행(또는 xact_start 가 몇 초 전인 것뿐)이면 Portainer 에서 nl-lib-fastapi 를 Recreate 한다("Re-pull image" 끔)
docker logs -f --since 1m nl-lib-fastapi 2>&1 | grep -m1 "Application startup complete"   # 모델을 올려 1~2분
[ "$(docker inspect --format '{{.Image}}' nl-lib-fastapi)" = "$NEW" ] && echo "fastapi 새 이미지"
echo "SELECT version_num FROM alembic_version" | pgq
docker exec nl-lib-fastapi python -c "import json, urllib.request as u; p = json.load(u.urlopen('http://localhost:8000/openapi.json'))['paths']; print(sorted(k for k in p if k.endswith('/topics/regenerate') or k.endswith('/sources')))"
docker exec -w /app nl-lib-fastapi ls domains/nl_library/prompts/book_chat.paper.yaml
curl -s "$API/history?kind=research&limit=1" -H "x-session-id: $SID"; echo
C=$(echo "SELECT cnts_id FROM library_catalog WHERE doc_type = 'paper' LIMIT 1" | pgq); curl -s "$API/books/$C" | grep -o '"doc_type":"[a-z]*"'
docker exec -w /app nl-lib-fastapi python -c "from services.research.state import DEFAULT_PARAMS as P; print(P['broaden'], P['query_context'])"
```

Expected: `INFO:     Application startup complete.` 한 줄, `fastapi 새 이미지`, `0007_research_work`(그대로), `['/api/research/{job_id}/sections/{key}/sources', '/api/research/{job_id}/topics/regenerate']`, `domains/nl_library/prompts/book_chat.paper.yaml`, `{"items":[],"next_cursor":null,"total":0}`(06e 의 total — 새 브라우저 ID 라 0), `"doc_type":"paper"`, Step 1 의 dev 기본값.

- [ ] **Step 7: (사용자, 서버) nuxt Recreate → 게이트웨이 reload**

Portainer 에서 `nl-lib-nuxt` 를 Recreate 한다("Re-pull image" 끔). 그 뒤 게이트웨이를 reload 한다(함정 20 — Recreate 한 컨테이너의 새 IP 를 nginx 가 다시 읽는다).

```bash
[ "$(docker inspect --format '{{.Image}}' nl-lib-nuxt)" = "$NEW_NUXT" ] && echo "nuxt 새 이미지"
docker exec nl-lib-gateway nginx -s reload
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/
docker exec nl-lib-nuxt sh -c 'grep -l "wk-rbar" /app/.output/public/_nuxt/entry.*.css | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "이 키워드로 다시 만들기" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "참고문헌 선택하기" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "미검토 AI 초안" /app/.output/public/_nuxt/*.js | wc -l'
docker exec nl-lib-nuxt sh -c 'grep -l "rs-pbar" /app/.output/public/_nuxt/entry.*.css | wc -l'
```

Expected: `nuxt 새 이미지`, `200`·`200`, `wk-rbar`(보고서 화면 큰 진행 막대) 든 entry CSS → `1`, `이 키워드로 다시 만들기`·`참고문헌 선택하기` 든 JS 청크 → 각각 `1` 이상, 옛 워터마크 `미검토 AI 초안` → `0`, `rs-pbar`(06d) → 경우 가·다 `1`, 경우 나 `0`. 502 가 나오면 reload 를 빠뜨렸거나 nuxt 가 아직 뜨는 중이다 — `docker logs --since 1m nl-lib-nuxt` 에 `Listening on http://0.0.0.0:3000` 이 보인 뒤 reload 와 확인을 다시 한다.

경우 가면 이어서 06d 계획 배포 Task 의 마지막 Step('06d 가 운영 nuxt 에 들었는지')의 명령을 돈다(그 Step 의 Expected 를 그대로 본다).

- [ ] **Step 8: (사용자, 서버·브라우저) 배포 직후 확인 — 딥리서치 그대로(D15)·06b 연구·회수기**

게이트웨이(포트 92)를 거쳐 확인한다(컨테이너에 직접 붙는 확인은 함정 20 을 못 잡는다).

```bash
curl -s -w '\n%{http_code}\n' $API/research/0ec15239-beee-456e-a547-6be945a752c0/work
curl -s $API/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383/proposal | grep -o '"auto":[a-z]*' | head -1
curl -s $API/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383/proposal | grep -c '"section_gens":{'
curl -s $API/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383/work | grep -o '"concept_candidates":null'
```

Expected:
- 이어가지 않은 잡(06a 갈래 1 — 06b 배포 확인과 같은 잡) — `{"detail":"이어간 연구가 없습니다"}` 다음 줄 `404`
- 06b 에서 이어간 연구(`d8348de8` — 06b 운영 확인 잡)의 목차 — `"auto"` 줄이 **없다**(06b 목차엔 키가 없다 — 연쇄 대상이 아니다), `section_gens` → `1`(새 응답 키), `"concept_candidates":null`(06b 개념 output 에는 후보가 없다)

회수기는 fastapi 기동 뒤 다음 10분 틱 뒤에 본다:

```bash
docker logs --since 15m nl-lib-celery-control 2>&1 | grep "reap_stale_research" | grep succeeded | tail -1
```

Expected: `… {'jobs': 0, 'steps': 0, 'generations': 0, 'redispatched': False}`.

브라우저(`http://192.168.12.57:92`)로 본다 — 06a 갈래 1 잡 `/research/0ec15239-beee-456e-a547-6be945a752c0`: PlanCard·진행 패널·보고서·근거 장부·보고서 끝 [이 연구 이어가기]가 전과 같고(D15 — 06d 가 운영에 있으면 06d 의 화면 그대로), 머리에 4단계 진행 막대(WorkStepper)는 **없다**. 06b 연구 `/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383?s=proposal`: 단계 이름 '보고서', 큰 진행 막대 **없음**, 연쇄 없음(개발자 도구 Network 에 `sections/…/generate` POST 가 없다), 머리 목차·문서 자리 1~6. 이 연구에서 누르면 쓰는 버튼은 누르지 않는다(06b 기록). 콘솔 오류 없음.

배포가 끝났다. Step 1 에서 dev 기본값이 운영 기본값과 달랐으면 06c 세션(사용자)에게 "06c 기본값 커밋이 이 배포(워커 셋 → fastapi)로 운영에 나갔다 — 06c 계획의 '10/17~18 배포 뒤 06c 확인'을 하면 된다" 고 알린다. 경우 나면 06d 세션에 "06e 가 운영에 있다 — 06d 배포는 nuxt 를 dev(06e 포함)로 만들고 LNB 접기 연결은 06d 가 단다" 고 알린다. 그리고 Task Z6 이 끝날 때까지 다른 워커·fastapi·nuxt 배포를 하지 않는다.

---

### Task Z6: (사용자, 서버·브라우저) 운영 처음부터 끝까지 1회 — 이어가기에서 [보고서 만들기]·Word 까지

**왜:** §12-7 운영 확인(줄마다 배포 뒤 고정 질문 하나를 처음부터 끝까지)과 §8 — 06e 는 **[보고서 만들기] 한 번에서 Word 까지의 소요 시간과 생성 대기 순번**을 본다. 06e 의 화면 동작(키워드 칩·하이라이트·딥리드 패널·연쇄·큰 진행 막대·인용 근거 하이라이트)은 `.vue` 라 단위 테스트가 없고 운영에서만 실제 생성·이벤트로 본다. 질문은 랜딩 논문 예시 `노인의 우울과 사회적 지지에 관한 연구가 궁금해`(06c 판정 질문 `elderly` 와 같은 문장 — 코퍼스가 받쳐 딥리서치 정밀도가 높았다)로 한다 — §12-8 장면 2·3 을 그대로 지난다.

**Files:** 없음(결과는 Task Z7 이 완료노트 §5-3·§5-4 에 적는다)

**알아 둘 것:**
- 만든 딥리서치·이어간 연구·담은 논문·보고서는 실제 기록으로 남는다(사용자 자신의 브라우저 기록).
- 브라우저는 운영 주소(`http://192.168.12.57:92` 또는 `https://skovix.landsoft.co.kr`)로 연다. 넓은 화면은 1440px 창, 좁은 화면은 개발자 도구의 기기 모드로 768px·375px. '동작 줄이기'는 개발자 도구 Rendering 의 `prefers-reduced-motion: reduce` 흉내로 본다.
- 딥리서치는 브라우저당 1건이다(429 `browser_active`) — 06d 세션의 운영 확인이 같은 브라우저에서 돌고 있으면 끝난 뒤 하거나 다른 브라우저 프로필로 한다.
- 서버 명령은 Task Z5 의 root 셸(`pg`·`pgq`·`API` 정의)에서 한다.
- 본 것은 단계마다 짧게 적어 둔다(통과 / 다름 + 무엇이). 다른 것이 나오면 그 자리에서 고치지 않고 모아서 Step 9 에서 정한다.
- 파트 Task 들이 '브라우저 확인 — 마무리 운영 확인에 넘긴다'로 적은 항목(Task A5 Step 5 의 아홉 항목·X3·X4·X5·R3 의 기존 네 화면 회귀·R5·R6(했으면)·S4·K8)은 아래 Step 1~8 이 덮는다. 그 목록에 있는데 아래에 없는 항목은 Step 8 의 8번에서 그 Task 의 목록대로 본다.
- 딥리드에 참고문헌 의도 질문 하나("이 논문의 참고문헌은?" — 의도 낱말 `book_chat.py:19-22`)를 보내 목록이 답으로 오는지 본다(Step 4 의 2 — 정함 31 의 기존 버그를 Task S2 가 고쳤다).

- [ ] **Step 1: (브라우저, 1440px) 딥리서치를 끝까지 — 이어가기**

1. `/` — 논문 탭의 예시 칩 `노인의 우울과 사회적 지지에 관한 연구가 궁금해` 를 누르면 입력창에 채워진다 → + 메뉴에서 딥리서치를 골라 보낸다 → 계획을 승인한다. 주소의 잡 id 를 적는다(아래 `J`).
2. 끝날 때까지 기다린다(실측 202초 안팎 — 06c 기본값이 켜졌으면 계획에 몇 초 더). 보고서 끝 [이 연구 이어가기] 를 누른다 → 머리에 단계 막대(WorkStepper)가 서고 단계 이름이 `제목 고르기 · 참고문헌 선택하기 · 보고서` 다. 온보딩 창의 첫 줄이 `제목 고르기 → 참고문헌 선택하기 → 보고서 3단계를 거쳐 보고서 초안까지 갑니다.` 다.

Expected: 둘 다 위와 같다.

- [ ] **Step 2: (브라우저·서버) 제목 고르기 — 키워드 후보 칩·카드 4장·하이라이트**

1. 이어가기 직후 — 키워드 칩 줄에 후보가 서기 전에는 개념 생성 상태 줄, 빈 카드 넷은 대기 모양(스켈레톤)과 '차례를 기다리는 중입니다'(waiting — 키워드가 정해진 뒤 카드 생성이 들어간다)이고 '카드를 만들지 못했습니다'가 아니다. 키워드를 고르는 동안 [다른 방향]은 막혀 있다.
2. 후보가 서면 — 칩마다 출처 배지(`AI 후보`·`논문 n편`·`AI · 논문 n편`), 위 3개가 눌린 칩(`aria-pressed="true"`)이다. 일반어('연구 동향'·'선행연구' 같은 말)가 없다.
3. 카드 4장이 도착하면 — 제목 속 고른 키워드가 하이라이트(`<mark>`)되고, 키워드를 하나도 담지 못한 카드는 `제목에 「…」 없음` 경고를 단다. 근거 칩은 `김철수 2015` 꼴(제1저자 전체 이름 연도 — 복성·외 n인), 칩에 마우스를 올리면 서지 한 줄 툴팁.

```bash
J=<브라우저 주소의 잡 id>
pg <<SQL
SELECT kind, status, count(*) FROM research_generations WHERE work_id = '$J' GROUP BY kind, status ORDER BY kind, status;
SELECT jsonb_array_length(output->'candidates') AS candidates, output->'concepts' AS picked FROM research_generations WHERE work_id = '$J' AND kind = 'concepts' AND status = 'done' ORDER BY id DESC LIMIT 1;
SELECT concepts FROM research_works WHERE id = '$J';
SELECT slot, origin, state, left(card->>'title', 40) AS title, card->'keywords' AS keywords, card->'checks'->'missing_keywords' AS missing FROM research_topics WHERE work_id = '$J' ORDER BY id;
SQL
```

Expected: `concepts | done | 1`·`topic_card | done | 4`(카드 생성은 개념 반영 뒤 씨앗 자리마다 한 번 — failed 가 있으면 그 수와 `error` 를 적는다), 후보 수 1~10·`picked` 는 3개(후보가 3개 미만이면 전부), `research_works.concepts` 는 `picked` 와 같다, 주제 행 넷의 `keywords` 가 `picked` 와 같고 `missing` 은 제목에 없는 키워드만이다.

Expected(화면): 셋 모두 위와 같다.

- [ ] **Step 3: (브라우저) 키워드를 바꿔 다시 만들기 → 카드 고르기**

1. 눌린 칩 하나를 풀고 다른 후보 하나를 누른다(또는 직접 더하기로 한 낱말을 더한다 — 배지 `직접`). AI 카드마다 `키워드가 바뀌었습니다` 가 뜨고 [이 키워드로 다시 만들기] 가 보인다. 눌린 칩을 하나만 남기면 버튼이 막히고 `키워드를 2개 이상 고르면 다시 만들 수 있습니다` 줄이 선다 — 다시 2개 이상으로 둔다.
2. [이 키워드로 다시 만들기] → AI 카드들이 대기·작성 중을 거쳐 새 키워드가 하이라이트된 제목으로 바뀐다. 고친 카드·직접 쓴 카드가 있으면 그대로다.
3. 카드 하나를 고르고 `참고문헌 선택하기로` 를 누른다.

Expected: 셋 모두 위와 같다. `pg` 로 `SELECT count(*) FROM research_generations WHERE work_id = '$J' AND kind = 'topic_card'` 가 4 + 다시 만든 카드 수다.

- [ ] **Step 4: (브라우저, 1440px) 참고문헌 선택하기 — 오른쪽 딥리드**

1. 단계 제목 `참고문헌 선택하기`. 논문 제목을 누르면 오른쪽에 딥리드 패널이 열린다(제목 버튼 `aria-expanded="true"`, 그 행 강조, 패널 머리에 제목·`저자 · 연도 · 학술지`·[논문 상세 ↗]·닫기). 1440px 에서 LNB 가 접힌다 — Task R6 을 했거나(06d 먼저) 06d 의 LNB 접기 연결이 운영에 있을 때만이다. 둘 다 아니면 접히지 않는 것이 맞다(적어 둔다).
2. 질문 하나를 보낸다 → 답이 흐르며(`aria-live`) 끝나면 출처 칩(`p.X–Y`)이 붙는다. 칩을 누르면 대목 미리보기가 열리고 [원문 보기] 를 누르면 원문 뷰어가 `X+1` 쪽으로 열린다(칩의 쪽은 저장값 그대로, 뷰어 쪽은 +1 — 정함 22). 이어서 `이 논문의 참고문헌은?` 을 보낸다 → 끊기지 않고(오류 글 `오류가 발생했습니다. 다시 시도해주세요.` 없이) 그 논문의 참고문헌 목록을 들어 답한다(정함 31 — Task S2). 참고문헌이 비어 있는 논문이면 끊기지 않고 본문 대목으로 답한다 — 쪽을 말하면 출처 칩이 붙는다(목록이 없으면 청크 검색으로 돌아간다 — S2 quality 검토 반영).
3. 답이 흐르는 동안 다른 논문 제목을 누른다 → 스트림이 끊기고 그 논문의 대화가 열린다. 처음 논문으로 돌아오면 받다 만 답이 `(답을 받다가 멈췄습니다)` 와 함께 남아 있다. 다시 질문하면 이어서 답한다.
4. 패널의 [담음] 토글로 논문을 담거나 뺀다 — 행 상태가 같이 바뀐다. '들어온 경로' 첫 대목(접어 둠)을 펼치면 대목 글이 보인다.
5. Esc → 패널이 닫히고 초점이 누른 제목으로 돌아온다(LNB 가 접혔으면 다시 펼쳐진다). [논문 상세 ↗] → 상세로 갔다가 브라우저 뒤로 → 참고문헌 선택하기의 그 자리.
6. 담음이 5편 이상이 되게 둔다.

Expected: 여섯 모두 위와 같다.

- [ ] **Step 5: (브라우저·서버) [보고서 만들기] 한 번 — 소요 시간·대기 순번·큰 진행 막대**

먼저 서버의 다른 root 셸에서 대기 순번을 재는 스크립트를 띄운다(GET 만 한다 — 절 생성이 생긴 뒤 열린 생성이 10초 없으면 끝난다):

```bash
J=<잡 id>
docker exec -i -e J=$J nl-lib-fastapi python - <<'PY'
import json, os, time, urllib.request

url = f"http://localhost:8000/api/research/{os.environ['J']}/work"
peak, quiet, seen_section = {}, 0, False
for _ in range(300):                                   # 10분까지 2초마다
    gens = json.load(urllib.request.urlopen(url))["generations"]
    open_ = [g for g in gens if g["kind"] in ("outline", "section") and g["status"] in ("queued", "running")]
    seen_section = seen_section or any(g["kind"] == "section" for g in gens)
    for g in open_:
        if g["status"] == "queued" and g["position"] is not None:
            key = f'{g["kind"]} {g["target"] or ""}'.strip()
            peak[key] = max(peak.get(key, 0), g["position"])
    quiet = 0 if open_ else quiet + 1
    if seen_section and quiet >= 5:
        break
    time.sleep(2)
for key, pos in sorted(peak.items()):
    print(key, "— 가장 길었던 앞 순번", pos)
print("끝 — 대기 줄에 선 생성", len(peak), "건")
PY
```

그다음 브라우저에서:

1. [보고서 만들기] 를 **한 번** 누른다(누른 시각을 적는다) → 보고서 화면으로 간다. 목차가 서면 편집기는 접혀 있고([목차 고치기] 토글), 머리 목차 1~6 과 문서 자리가 선다. 5 연구 질문 자리에 자동으로 고른 질문이 보인다.
2. 큰 진행 막대 — 막대 위 큰 글줄 `보고서 작성 중 · 0/n절 — 「…」`(조사 없이), 오른쪽 끝 퍼센트, 절이 끝날 때마다 `1/n`·`2/n` 으로 차오르고 쓰는 동안 채움에 움직임이 있다. 개발자 도구에서 막대 트랙의 높이가 `16px`(1rem)이다. 절이 문서 순서(선행연구 묶음 → 연구 공백)로 제자리에 흘러 들어오고, 근거가 없는 절은 `근거가 없어 쓰지 않았습니다` 로 건너뛴다. 다 쓰면 막대가 사라진다.
3. **연쇄가 도는 동안** 2절 연구 배경 칸의 [고치기] 로 한 줄을 써서 [저장] 한다 → 오류 없이 저장되고(절 반영으로 버전이 올라도 한 번 다시 보낸다 — 정함 8) 글이 남는다. 6절 방법도 한 줄 저장한다. 목차는 승인 그대로다(절 쓰기가 멈추지 않는다).
4. 머리 목차의 `5 연구 질문` 을 누르면 그 자리로 스크롤되고 제목에 초점이 간다.
5. 스크립트가 `끝 — …` 을 찍으면 시간을 잰다:

```bash
pg <<SQL
SELECT outline->>'state' AS state, outline->>'auto' AS auto, left(outline->>'question', 60) AS question, left(outline->>'background', 30) AS background FROM research_proposals WHERE work_id = '$J';
SELECT id, kind, target, status, model,
       round(extract(epoch FROM started_at - created_at)) AS wait_s,
       round(extract(epoch FROM finished_at - started_at)) AS run_s
FROM research_generations
WHERE work_id = '$J' AND kind IN ('outline', 'section') ORDER BY id;
WITH o AS (SELECT max(id) AS oid FROM research_generations WHERE work_id = '$J' AND kind = 'outline')
SELECT round(extract(epoch FROM max(g.finished_at) - min(g.created_at)))::int AS total_s, count(*) AS gens
FROM research_generations g, o WHERE g.work_id = '$J' AND g.id >= o.oid AND g.kind IN ('outline', 'section');
SQL
```

Expected: `approved | true | <질문> | <쓴 배경 앞 30자>`, outline 1행·section 행들이 모두 `done`(근거 없음으로 건너뛴 절은 행이 없다), 다른 연구의 생성이 없으면 `wait_s` 가 몇 초 안, `total_s` 는 1분 안팎(06b 실측 목차 2초·절 평균 8초 — `round06b-완료노트.md:108`). 스크립트의 앞 순번과 `total_s`·`gens` 를 적어 둔다(완료노트 §5-3). 다른 연구의 생성이 겹쳐 순번이 길었으면 그 사실도 적는다(리허설의 동시 사용 시험 재료 — §12-8).

Expected(화면): 넷 모두 위와 같다.

- [ ] **Step 6: (브라우저) 검토할 곳·인용 근거·선택 기능**

1. 머리 목차 아래 `검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m`(0 인 칸은 빠지고, 둘 다 0 이면 줄이 없다) → 누르면 그 첫 문단으로 스크롤·초점.
2. 저장된 문단의 인용 칩을 누른다 → 오른쪽 패널이 `인용 근거` 탭으로 열린다: 논문 카드(제목·서지), 모델이 본 원문 대목에서 인용 문장을 가장 많이 덮는 문장이 하이라이트(`<mark>`)되고 쪽 표기가 있다(대목이 없으면 초록과 '원문 대목을 읽지 못해 초록을 보입니다'). 본문의 그 문장도 강조된다. 칩 몇 개를 눌러 내용이 무관한 문장이 강조되지 않는지(특히 '것으로 나타났다'·'을 대상으로' 같은 상투구만 같은 문장 — 목록에 없는 상투구로 강조되면 `BOILERPLATE` 에 더하거나 하한을 올린다), '인용한 문장과 겹치는 대목 문장을 찾지 못했습니다' 줄이 대부분의 칩에서 나오지 않는지 본다 — 잦으면 `EXCERPT_MATCH_MIN`(0.2)을 낮출지 판단한다(파트 S 메모 12). 여러 [E#] 가 붙은 문장의 칩은 따로 본다 — 마커가 문장 가운데 있는 꼴('… 낮추며 [E1], … 낮춘다 [E2].')과 끝에 몰린 꼴('… 낮추고, … 떨어뜨린다 [E1][E2].') 각각에서 칩을 하나씩 눌러, 칩마다 그 칩이 받치는 말에 맞는 대목 문장이 강조되는지('찾지 못했습니다' 줄로 떨어지지 않는지), '효과가 … 컸다'·'높을수록 … 낮았다' 같은 결과 문형만 같은 무관 문장이 강조되지 않는지 본다(파트 S 메모 12 의 3차 검토 반영 — 무관이 잦으면 하한을 올리거나 나누기를 끄고, '찾지 못했습니다' 가 잦으면 나누는 자리를 늘릴지 판단한다).
3. [원문 보기] → 원문 뷰어가 그 쪽으로 열린다. [이 논문과 대화하기] → 같은 패널이 `딥리드` 탭으로 바뀐다. Esc → 닫히고 초점이 누른 칩으로 돌아온다.
4. 선택 기능이 남았다 — 문단 하나에 [수락] → 상태 `수락`, 다른 문단의 상태 이름은 `AI 작성 · 검토 전`. [목차 고치기] 를 열면 편집기가 펼쳐진다(다시 승인하지 않고 닫는다).

Expected: 넷 모두 위와 같다.

- [ ] **Step 7: (브라우저·서버) 내보내기 — Word 기본·'수락한 문단만'·PDF**

1. [Word 로 내려받기](기본) → 파일 이름 `보고서_<주제 앞부분>_<날짜>.docx`. 열면 모든 절의 모든 문단(검토 전 AI 문단 포함)이 실리고 쪽마다 워터마크가 **없다**. 2절 연구 배경에 Step 5 에서 쓴 글, 6절 방법에 쓴 글. 끝의 부록 'AI 사용 공개' 에 절별 `문단 N개 — AI 작성·검토 전 p·수락 a·수정 e·직접 작성 u`, 실은 문단 줄, 검토할 곳 줄(있으면), `작성 일시 …`, 결과·논의 미포함 — 모델 이름·시도 기록 줄은 **없다**. 참고문헌은 부록 뒤.
2. `수락한 문단만 싣기` 를 켜고 다시 내려받는다 → 파일 이름 끝 `_수락문단만.docx`, Step 6 에서 수락한 문단만 실리고 부록에 `검토 전 AI 작성 문단 n개는 싣지 않음`.
3. (Task H3 를 했으면) [PDF 로 내려받기] → 인쇄 창의 문서 제목이 파일 이름에서 `.docx` 를 뗀 것, 워터마크 없음, 본문 → 부록 → 참고문헌 순서가 Word 와 같다. 인쇄 창을 닫으면 버튼이 다시 살아난다.

```bash
echo "SELECT phase FROM research_works WHERE id = '$J'" | pgq
```

Expected: 셋(H3 를 건너뛰었으면 둘) 모두 위와 같고, `done`(처음 내려받기가 단계를 끝냈다). [보고서 만들기] 를 누른 시각부터 Word 를 받은 시각까지를 적는다(완료노트 §5-3 — '한 번에서 Word 까지').

- [ ] **Step 8: (브라우저) 회귀·좁은 화면·움직임 줄이기**

1. **기존 BookChat 네 화면** — 논문 상세(`/papers/<cnts_id>`)의 채팅 패널: 첫 인사가 `… 논문에 대해 궁금한 것을 …`, 입력 안내가 논문 문구, 질문 → 답 → 출처 칩 미리보기(여기는 [원문 보기] 가 없다 — `pdfLinks` 기본 false). 논문 검색 결과의 채팅 패널도 논문 문구. 도서 상세와 `/search-classic`(보존 화면)의 `TopResult` — 맨 위 결과·'추천 도서 살펴보기'의 [DeepRead] — 는 책 문구 그대로(같은 책이면 대화가 남고 책이 바뀌면 비운다 — Task R2 의 의도된 변화). 보내기 버튼 이름 `질문 보내기`.
2. **딥리서치 보고서 `CitationChip` 팝오버** — 끝난 딥리서치 보고서의 인용 칩에 마우스를 올리면 전과 같은 팝오버(06e 패널이 아니다).
3. **06b 에서 이어간 연구**(`/research/d8348de8-ee7f-48f9-8ceb-20924ed6a383`) — `?s=topics` 는 저장된 키워드가 눌린 칩(후보 없음), 하이라이트 없음, `?s=proposal` 은 막대·연쇄 없음(누르면 쓰는 버튼은 누르지 않는다).
4. **예시 연구**(`curl -s "$API/research-works?example=1"` 이 항목을 내면) — 그 연구의 단계 화면에서 [보고서 만들기]·칸 저장·[담음]·[이 키워드로 다시 만들기] 가 막혀 있고 딥리드 대화는 열린다.
5. **768px·375px** — 보고서 화면의 막대가 얇아지고(0.75rem = `12px`) 큰 글줄은 한 줄 말줄임, 퍼센트와 겹치지 않는다. 참고문헌 선택하기의 딥리드 패널이 769~1199px 에서는 오버레이 서랍(배경을 누르면 닫힘·Tab 초점이 패널 안에 갇힘), 768px 이하는 전체 폭이다. 가로 스크롤이 생기지 않는다.
6. **움직임 줄이기**(Rendering 흉내) — 막대 채움의 움직임이 멈춘다. 패널 열림·닫힘도 움직임 없이 바뀐다.
7. **사이드바 '모두 보기 (N)'** — 06d 가 운영에 있으면 딥리서치 탭 끝에 N 이 붙는다(06e 의 `total`). 06d 가 아직 없으면 해당 없음(06e 쪽은 Task Z5 Step 6 의 `"total":0` 로 확인했다).
8. **Task 들이 넘긴 확인 목록의 남은 항목** — Task A5 Step 5·X3·X4·X5·R3·R5·R6·S4·K8 의 '브라우저 확인' 가운데 Step 1~8 에서 보지 않은 것을 그 목록대로 본다(예: 연쇄 중 손으로 누른 [이 절 쓰기]의 절을 연쇄가 다시 넣지 않는다 — Task A4, 한 문장에 칩이 둘이면 누른 칩만 펼침 — Task S4, 패널이 열린 사이 보고서를 다시 읽어도 닫으면 같은 자리 칩으로 초점이 돌아온다 — Task S4).

Expected: 여덟 모두 위와 같다(해당 없는 항목은 '해당 없음').

- [ ] **Step 9: 다른 것이 나왔을 때 — 모아서 정한다**

Step 1~8 에서 다른 것이 없으면 이 Step 은 끝이다. 있으면 목록(무엇이·어디서·재현 방법·잡 id)을 사용자에게 보이고 하나씩 정한다:
- **고칠 것** — dev 에서 분기한 브랜치 `fix/round06e-live-check` 에서 고친다(06e worktree 에서 `git status --short` 가 빈 것을 본 뒤 `git fetch origin dev:dev && git switch -c fix/round06e-live-check dev`). 판단을 고치면 실패 테스트부터(백엔드 함수·순수 함수), `.vue`·`.css` 만이면 typecheck·build. 커밋은 `[Fix] round06e — <무엇을 왜>`. 그 뒤 Task Z2 Step 1·2 의 회귀 → 사용자 승인 → 임시 worktree 머지(Task Z4 Step 3 의 명령, 머지 메시지 `Merge fix/round06e-live-check into dev — round06e 운영 확인 반영`) → 바뀐 컨테이너만 다시 낸다: 프론트만이면 Task Z5 의 빌드 확인·nuxt 빌드 → Step 3 의 nuxt 태그(`:pre-r06e-fix1`)·pull → Step 7. 백엔드가 바뀌었으면 fastapi 이미지 → Step 3(fastapi)·Step 4·Step 5·Step 6 → reload.
- **미룰 것** — 완료노트 §7 이월에 적는다(Task Z7).

---

### Task Z7: 배포 기록 — 기록 브랜치·dev 머지

**왜:** D13 — 완료노트에 dev 머지·배포·운영 확인을 남긴다. 06e 코드는 이미 dev 에 있으므로 기록 커밋은 dev 에서 분기한 브랜치에서 하고 dev 머지(사용자 승인)로 올린다.

**Files:**
- Modify: `docs/roadmap/round06e-완료노트.md`(머리 날짜·§5·§7·상태), `docs/roadmap/00_status.md`(Task Z3 가 넣은 06e 구절), spec(머리 상태 줄), 필요하면 `docs/ops/recurring-gotchas.md`

- [ ] **Step 1: 기록 브랜치**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e
git status --short
git fetch origin dev:dev && git switch -c docs/round06e-deploy-record dev
```

Expected: `git status --short` 빈 출력, `Switched to a new branch 'docs/round06e-deploy-record'`. Task Z6 Step 9 에서 `fix/round06e-live-check` 를 썼으면 그 브랜치가 dev 에 머지된 뒤 따는 것이다(fetch 가 그 머지를 가져온다). fetch 가 실패하면 Task Z5 Step 1 의 안내대로 푼 뒤 다시.

- [ ] **Step 2: 완료노트 §5 를 채운다 (Edit 도구)**

머리 날짜 줄의 `` `dev` 머지·운영 배포·처음부터 끝까지 1회는 §5`` 를 `` `dev` 머지 `<Task Z4 의 머지 커밋>` <날짜> · 운영 배포·처음부터 끝까지 1회 <날짜> — §5`` 로 바꾸고, §5 의 "배포 전 — …" 한 줄을 아래 하위 절로 바꾼다.

- **5-1. 머지와 이미지** — dev 머지 커밋(Task Z4), 머지 문의 값(06c 머지·배포 기록, K9 가 받은 06c 머지, 06d 머지 여부와 R6, H3), 배포 경우(가·나·다와 까닭 — Task Z5 Step 1 의 표 값), 빌드한 커밋(`빌드해도 된다:` 뒤 값), `--ff-only` 로 받았으면 그 사실과 다시 돈 테스트 수, 이미지 ID 앞 19자(`NEW`·`NEW_NUXT`), 서버 되돌리기 태그 `:pre-round06e`, 06c 기본값(dev 값·배포 전 운영 값 — 이 배포로 바뀌었는지).
- **5-2. 서버 배포** — Task Z5 Step 2~8 의 확인 결과(`0007_research_work`, 비었는지, 워커 셋 새 이미지·06e 실행기 `True True True`·프롬프트·기본값, fastapi 새 이미지·새 경로 둘·`book_chat.paper.yaml`·`total`·`doc_type`, nuxt 새 이미지·reload·`/health`·`/` 200·청크 확인 수, 06d 확인(경우 가), 이어가지 않은 잡 404·06b 연구 `auto` 없음, 회수기 0건). 머지 문을 연 시각·배포를 마친 시각.
- **5-3. 운영 처음부터 끝까지 1회** — 잡 id, Task Z6 Step 1~8 에서 본 것(통과 / 다름), 개념·카드 생성 수(Step 2 의 표), [보고서 만들기] 의 목차·절 생성 표(`wait_s`·`run_s`)·`total_s`·대기 순번(스크립트 출력)·[보고서 만들기] 에서 Word 까지 걸린 시간, Word·'수락한 문단만'·(PDF) 결과, 회귀 일곱 항목.
- **5-4. 운영 확인 반영** — Task Z6 Step 9 에서 고친 것(브랜치·커밋·dev 머지·다시 낸 컨테이너·태그) 또는 '고칠 것 없음'.

§7 이월에 운영 확인에서 미룬 것을 더한다. '상태' 의 수동 스모크·문서 갱신·`dev` 머지 승인을 `[x]` 로(승인 문장과 날짜를 함께).

- [ ] **Step 3: 00_status·spec·반복 함정 (Edit 도구)**

1. `docs/roadmap/00_status.md`:
   - 3행 — Task Z3 의 구절 `round06e — 연구 어시스턴트 구현 완료(보고서 자동 산출·큰 진행 막대·내보내기 기본값·참고문헌 선택하기와 오른쪽 딥리드·인용 근거·제목 고르기·근거 칩·기록 total), \`dev\` 머지·배포 대기. ` 를 `round06e — \`dev\` 머지·운영 배포(<경우 — 예: 06d 와 함께 워커 셋 → fastapi → nuxt / 06e 만 워커 셋 → fastapi → nuxt>, 06c 기본값 <함께 나감 / 이미 운영>)·처음부터 끝까지 1회(<한 줄 — 예: [보고서 만들기] 에서 Word 까지 n분, 대기 순번 최대 m, 고친 것 k건>). ` 로, 날짜를 이 Step 을 하는 날로.
   - round06 머리 — ` · 06e 구현 완료·\`dev\` 머지·배포 대기**` 를 ` · 06e 운영 배포(<배포 날>)**` 로.
   - 06e 하위 줄 끝(`상세: \`round06e-완료노트.md\`.`) 뒤에 한 문장: `운영 배포 <배포 날> — <경우와 한 줄 결과>(완료노트 §5).`
   - 다음 할 일의 06e 줄 머리 — Task Z3 의 `  - **06e 연구 어시스턴트 — 구현 완료, \`dev\` 머지·배포 대기(10/17~18 — 워커·fastapi·nuxt)** — 계획 … Z7(기록) 순서.` 를 `  - **06e 연구 어시스턴트 — 운영 배포·확인 끝(<배포 날>)** — 남은 것: 리허설(10/23~25)에서 시연용 자기 연구를 새로 이어가 키워드 칩·자동 보고서·인용 근거를 다시 보고, 3~5명 동시 사용 때 보고서 대기 길이를 잰다<, 이월이 있으면 '· 이월 n건(완료노트 §7)'>.` 로.
   - 라운드 이력의 round06 칸 — `· 06e 구현 완료·배포 대기(\`feat/round06e-assistant-auto-report\`)` 를 `· 06e 운영 배포(<배포 날>)` 로.
2. spec 3행 — Task Z3 의 ` · 06e 구현 완료(2026-10-16 — … \`dev\` 머지·배포 대기)` 를 ` · 06e 완료(<배포 날> 운영 배포·처음부터 끝까지 1회)` 로(Task Z3 를 한 날이 2026-10-16 이 아니면 그 날짜의 글을 old 로 잡는다).
3. `docs/ops/recurring-gotchas.md` — 운영 확인에서 라이브에서만 드러난 패턴이 있었으면 `## 28. …`(날짜·증상·원인·해결·재발 방지 — 06c·06d 가 먼저 28 을 썼으면 그다음 번호)로 더한다. 없으면 고치지 않고 완료노트 §5 끝에 "반복 함정 — 더할 것 없음" 한 줄을 남긴다.

꺾쇠 자리는 모두 실측값으로 바꾼다:

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git diff -U0 -- "docs/roadmap/round06e-완료노트.md" docs/roadmap/00_status.md docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md docs/ops/recurring-gotchas.md | grep '^+[^+]' | grep -c '<[^>]*>'
```

Expected: `0`(더한 줄에 꺾쇠 자리가 남지 않았다 — 원래 있던 줄의 꺾쇠는 세지 않는다).

- [ ] **Step 4: 커밋하고 dev 머지(사용자 승인)**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06e && git add "docs/roadmap/round06e-완료노트.md" && git add docs/roadmap/00_status.md && git add docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md && git status --short && git commit -m "[Docs] round06e 운영 배포 기록 — dev 머지·운영 배포(워커 셋 → fastapi → nuxt → 게이트웨이 reload, 배포 경우와 06c 기본값·06d 화면 동반 여부, 스키마 단계 없음), 랜딩 예시 질문으로 처음부터 끝까지 1회(키워드 후보 칩·카드 제목 하이라이트·다시 만들기, 참고문헌 선택하기의 오른쪽 딥리드, [보고서 만들기] 한 번에 목차 자동 승인·절 연쇄·큰 진행 막대 — 소요 시간·대기 순번, 검토할 곳·인용 근거 하이라이트, Word 기본·수락한 문단만, 회귀·좁은 화면)"
```

`docs/ops/recurring-gotchas.md` 를 고쳤으면 `git add docs/ops/recurring-gotchas.md` 를 `git status --short` 앞에 더한다.

Expected: `git status --short` 에 문서 셋(함정을 고쳤으면 넷)만 `M`, 커밋 1개.

기록 커밋을 사용자에게 보이고 승인을 받은 뒤:

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI fetch origin dev:dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/dev-merge dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge merge --no-ff docs/round06e-deploy-record -m "Merge docs/round06e-deploy-record into dev — round06e 운영 배포·확인 기록"
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge log --oneline -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/dev-merge push origin dev
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree remove .worktrees/dev-merge
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree list | grep -c dev-merge
```

Expected: 머지 커밋 한 줄, push 성공, 마지막 줄 `0`. 그 사이 06c·06d 의 기록이 같은 문서 줄을 고쳐 충돌하면 Task Z4 Step 1 의 문서 충돌 규칙으로 푼다. 그다음 `dev→main` 머지·push(`/round-finish`)를 06e 에서 할지, round06 세 줄을 모두 마친 뒤 한 번에 할지 사용자에게 묻는다.

---

#### 롤백 (사용자, 서버)

Task Z5·Z6 의 확인이 틀리거나 운영 오류(보고서 화면이 깨짐·연쇄가 멈추지 않음·주제 카드가 생기지 않음·연구 화면 500 등)가 나면 되돌린다. 스키마는 바뀌지 않았으므로 되돌릴 마이그레이션이 없다 — 06e 가 남긴 JSONB 키(`outline.auto`·`background`, 카드 `keywords`, 개념 output `candidates`)는 옛 코드가 읽지 않고 지나간다.

1. **먼저 비었는지 본다** — Task Z5 Step 4 의 명령(잡·생성 0행, 큐 0, 워커 셋 `- empty -`). 특히 개념(`kind = 'concepts'`) 생성이 열린 연구가 있으면 끝나기를 기다린다 — 새 fastapi 로 이어간 연구의 개념을 옛 워커가 반영하면 카드 생성이 들어가지 않는다(그런 연구는 [다른 방향]으로 카드를 받는다 — 06b 정함 15 와 같은 처리).
2. **되돌리는 순서는 배포의 거꾸로 — nuxt → fastapi → 워커 셋 → 게이트웨이.** 새 워커 + 옛 fastapi 는 안전하고(Task Z5 '순서의 까닭' ①) 옛 워커 + 새 fastapi 는 카드가 생기지 않으므로 워커를 맨 뒤에 되돌린다. 화면만 깨졌으면 nuxt 만 되돌려도 된다(옛 화면은 새 응답 키를 무시한다).
   - nuxt: `docker tag landsoftdocker/nl-lib-nuxt:pre-round06e landsoftdocker/nl-lib-nuxt:latest` → Portainer 에서 `nl-lib-nuxt` Recreate("Re-pull image" 끔).
   - fastapi: `idle in transaction` 0 확인(Task Z5 Step 6 의 질의) → `docker tag landsoftdocker/nl-lib-fastapi:pre-round06e landsoftdocker/nl-lib-fastapi:latest` → `nl-lib-fastapi` Recreate → `docker logs -f --since 1m nl-lib-fastapi 2>&1 | grep -m1 "Application startup complete"`.
   - 워커 셋: `nl-lib-celery-research-plan` → `nl-lib-celery-research` → `nl-lib-celery-control` Recreate(같은 `:latest` — 이미 되돌린 태그).
   - `docker exec nl-lib-gateway nginx -s reload`.
3. **확인**(Task Z5 의 root 셸 — 셸이 바뀌었으면 `OLD=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-fastapi:pre-round06e)`·`OLD_NUXT=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-nuxt:pre-round06e)`·`API`·`SID`·`pgq` 를 다시 정의한다): `for c in nl-lib-fastapi nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do [ "$(docker inspect --format '{{.Image}}' $c)" = "$OLD" ] && echo "$c 옛 이미지" || echo "$c 다름"; done`(넷 다 '옛 이미지'), `[ "$(docker inspect --format '{{.Image}}' nl-lib-nuxt)" = "$OLD_NUXT" ] && echo "nuxt 옛 이미지"`, `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/`(`200`), `curl -s "$API/history?kind=research&limit=1" -H "x-session-id: $SID"`(`total` 없음), `echo "SELECT version_num FROM alembic_version" | pgq`(`0007_research_work`).
4. **함께 되돌아가는 것:** 경우 가였으면 nuxt 이미지에 06d 도 들어 있다 — nuxt 를 되돌리면 06d 화면도 되돌아간다(06d 세션에 알린다). 이 배포가 06c 기본값 커밋을 처음 낸 것이었으면 fastapi·워커를 되돌릴 때 기본값도 이전 값으로 돌아간다 — 06c 세션에 알린다(그 사이 만든 잡의 params 는 저장된 그대로다).
5. 되돌린 사실·시각·까닭을 완료노트 §5 와 `00_status.md` 의 06e 줄에 적고(Task Z7 의 기록 브랜치), 고친 뒤 Task Z2 → Z4 → Z5 를 다시 한다.
