# round06a 기반·품질 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ] **Step k: …**`) syntax for tracking.

**Goal:** round06(딥리서치 → 논문 에이전트 플랫폼)의 첫 하위 라운드. 딥리서치의 화면·흐름은 그대로 두고(D15) 내부 품질만 보강한다(critic 기준 스위치·근거 장부 데이터·인용 학술지 버그 — D16). 그 위에 연구 어시스턴트의 기반을 운영에 올린다 — 테이블 7개, 이어가기·연구 API·연구 SSE, 전역 1건 생성 디스패처와 핵심 개념 실행기(gemma/Qwen 라우팅·재시도 규칙·회수), 브라우저당 실행 제한·대기 순번, 일일 백업, critic 판정 도구 — spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` §9 의 06a 줄.

**Architecture:** 딥리서치 파이프라인(계획 → 탐색 → 종합)과 화면은 바꾸지 않는다. critic 은 잡 파라미터 `critic_scope`(기본 0 = 지금 기준 글자 그대로)로 새 기준을 고르게 해 꺼진 채 배포하고 운영에서 두 갈래를 비교해 켠다(D11). 연구 어시스턴트는 새 테이블(`research_works` 외 6개, 기존 테이블 무변경)과 새 라우터 `app/api/research_work.py` 로 붙고, LLM 생성은 `q_research_plan` 의 한 자리만 쓰는 전역 1건 디스패처(`tasks.dispatch_research_work`)가 돌린다 — 다른 한 자리는 늘 딥리서치 계획에 남긴다. 06a 의 실행기는 핵심 개념(kind=concepts) 하나다(주제 카드는 06b, 특징 추출은 06c).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2(Postgres — 테스트는 stdlib sqlite3), Celery·Redis(redis.asyncio), httpx, vLLM(gemma-3-12b · qwen3-vl-8b), Nuxt 4·Vue 3.5·vitest, POSIX sh, pytest.

---

## 실행 전 알아 둘 것

- **작업 위치:** `git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/round06a -b feat/round06a-foundation feat/round06-paper-agent` 로 만든 `C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a`(Task 0). 저장소 루트 폴더와 다른 worktree 는 건드리지 않는다(여러 세션이 함께 쓴다). 이 브랜치는 spec·이 계획 문서를 담은 `feat/round06-paper-agent` 에서 따므로, 06a 를 dev 에 머지하면 spec·계획도 함께 들어간다.
- **백엔드 테스트:** `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/<파일> -q -p no:cacheprovider`. 전체는 `python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors` — 기준선 **1369 passed, 1 skipped, 수집 오류 3**(test_book_chat·test_build_manifest·test_loaders — 로컬에 FlagEmbedding·openpyxl 없음, 원래 상태). pytest-asyncio 가 없어 async 는 `asyncio.run` 으로 돈다. 로컬에 redis·celery·kombu·aiosqlite 가 없어 테스트는 기존 `_stub_missing`·`_load_*` 패턴으로 대역을 쓴다. torch·FlagEmbedding 을 끌어오는 모듈은 함수 안에서 import 한다(함정 13).
- **프론트 테스트:** `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npm ci && npx nuxi typecheck` 를 먼저 한다(`.nuxt` 가 없으면 vitest 가 전부 실패한다). 기준선 vitest 28 files / 495 passed, typecheck 오류 0, `npm run build` 완료.
- **테스트 수 읽는 법:** 각 task 의 기대 수치는 실측값이다. 어떤 수치는 "앞 task 뒤 수 + N" 으로 적혀 있다 — 순서대로 실행하면 상대값(+N)을 따른다. pytest 출력 끝의 기존 경고(`core/config.py` 의 `PydanticDeprecatedSince20` 등 `, 1 warning`·`, 2 warnings`)는 기대값에 적혀 있지 않아도 같은 결과다. 계획 전체를 새 사본에 순서대로 글자 그대로 적용한 통합 검증(2026-10-02)의 백엔드 전체 수치: Task 1 뒤 1406 → 2: 1427 → 3: 1433 → 4: 1439 → 5: 1450 → 6: 1468 → 7: 1515 → 8: 1558 → 9: 1602 → 10: 1611 → 11: 1687 → 12: 1697 → 15·16: 1717(모두 `1 skipped`·수집 오류 3). 실행 브랜치(`feat/round06a-foundation`)는 Task 7 리뷰 반영(`b401939` — `test_research_api.py` 7·`test_research_run_queue.py` 4)이 테스트 11개를 더해 Task 7 뒤부터 이 수치보다 11 많다(15·16 뒤 1728 — Task 17 Step 3). 프론트 vitest: 495 → Task 4: 496 → Task 13: 510(28 files). 이 통합 검증에서 코드 수정은 하나도 필요하지 않았다.
- **셸:** 명령마다 `cd <절대 경로> &&` 로 시작한다(에이전트 셸은 호출 사이에 cwd 가 초기화된다). 저장소는 `core.autocrlf=true` 라 작업 트리 파일이 CRLF 다 — 교체할 원문을 찾을 때 줄바꿈을 맞춘다.
- **커밋:** `[Feat]`·`[Fix]`·`[Refactor]`·`[Test]`·`[Chore]`·`[Docs]` 접두어와 한국어 본문. **`Co-Authored-By`·"Generated with Claude Code" 는 넣지 않는다.** task 마다 커밋한다.
- **운영 금지:** Task 0~16 의 어떤 단계도 운영 서버·운영 DB·운영 Redis 에 쓰지 않는다. 배포와 운영 확인은 Task 17 의 절차대로 **사용자가** 한다(dev 머지도 사용자 승인 뒤).
- **지켜야 할 결정:** D15 — 딥리서치 화면·흐름(계획 카드·승인 요청 본문·진행 패널·상태 배지·보고서 작성 진행 막대·사이드바 줄의 진행 표시)은 그대로 둔다. 더하는 것은 근거 장부 데이터(화면은 06b)·이어가기 API·승인 때 실행 제한 안내와 대기 순번(기존 문구 뒤에 덧붙이기만)뿐이다. D16 — 계획 프롬프트·계획 출력 형식은 바꾸지 않는다.
- **함정:** `docs/ops/recurring-gotchas.md` 13(로컬에 없는 모듈)·14(create_all + stamp)·15(LLM 이 예시 개수를 베낀다 — 프롬프트에 개수 예시 금지)·16(적재 워커 Recreate)·17(워커의 GPU·볼륨)·19(asyncio 데드라인)·20(fastapi·nuxt Recreate 뒤 nginx reload).

## 공통 계약 (모든 task 가 이 이름을 쓴다)

| 무엇 | 이름·모양 | 만드는 task |
|---|---|---|
| 새 테이블 | `research_works`·`research_generations`·`research_topics`·`research_gap_checks`·`research_reading`·`paper_facets`·`research_proposals`(`app/models/research_work.py`, 상수 `WORK_PHASES`·`GEN_KINDS`·`GEN_STATUSES`·`GEN_OPEN_STATUSES`·`PRIORITY_USER=10`·`PRIORITY_BACKGROUND=0`…), 마이그레이션 `0007_research_work`(down `0006_history_items`) | 1 |
| 테스트 DB | `app/tests/history_sqlite.py` 의 `make_engine()`(새 두 테이블, BIGINT PK → INTEGER, `pg_advisory_xact_lock` no-op), `AsyncSessionOverSync.get/add/flush/scalar`, `add_work()`·`add_generation()` | 1 |
| critic 스위치 | 잡 파라미터 `critic_scope`(int 0~1, 기본 0), 새 프롬프트 `research_critique_question.yaml`, `critique(subq, evidence, *, params, question=None)`, runner 가 `question=state.question` 을 늘 넘긴다 | 2 |
| 근거 장부 데이터 | 회차 기록 `subq.rounds[]` 와 `critique` 이벤트의 `adopted_papers`: `[{cnts_id, rank}]`, 그 회차 새 채택은 `{cnts_id, title, personal_author, pub_date, rank, new: true}` | 3 |
| 인용 | `build_citation` 의 학술지 = `series_title`(publisher 로 물러나지 않음) | 4 |
| LLM 호출별 모델 | `chat_full`·`chat`·`chat_stream(…, base_url=None, model=None)` | 5 |
| 실행 제한 | `_to_run_queue(db, jid, *, expect, created_by, **values)`, 429 detail `{code: "browser_active"\|"shared_queue", message, job_id?}` | 6 |
| 대기 순번 | `app/services/research/run_queue.py`(`RUN_QUEUE_KEY="research:run_queue"`, `mark_waiting`(NX 아님 — 다시 줄에 선 잡은 넣은 시각을 새로 쓴다)·`unmark`·`members_ahead`(내 점수 미만의 앞 원소 — API 가 그중 DB 상태가 approved·queued 인 잡만 센다. Task 7 리뷰 반영 `b401939` 가 `rank_of` 를 바꿨다)·`unmark_many_sync`·`waiting_ahead`·`eta_seconds`(= ahead × 중앙값)·`median_seconds`), GET·승인·재시도 응답과 snapshot 의 `queue: {ahead, eta_sec} \| null`, SSE `{kind: "queue", ahead, eta_sec}` | 7 |
| 생성 서비스 | `app/services/research_work/`: `routing.WORK_MODEL_ROUTES`·`endpoint`·`other`, `generate.Executor`·`run_generation`(최대 3회·넘김 규칙)·`CALL_TIMEOUT=300`, `concepts.clean_concepts`·`concepts_input`·`EXECUTOR`, `executors.EXECUTORS`, 프롬프트 `research_concepts.yaml` | 8 |
| 디스패처 | `dispatch.pick_next`·`finish`·`has_queued`·`queue_position`(`GEN_LOCK`), `apply.apply_result`, 워커 `tasks.dispatch_research_work`(큐 문자열 `q_research_plan` 고정, `send_dispatch()`), relay `work_channel`·`publish_work`·`subscribe_work`, 이벤트 `generation`: `{gen_id, gen_kind, target, status, model, result}` | 9 |
| 회수 | `reap_stale_research` 가 오래 running 인 생성을 failed 로, 줄이 남았으면 디스패치 다시 보내기, 회수한 잡을 대기 줄에서 빼기 | 10 |
| 연구 API | `POST /api/research/{id}/work/continue`·`GET`/`PATCH …/work`·`GET …/pool`·`GET /api/research-works`(`?example=1`)·`POST …/generations/{gid}/cancel`(queued 만)·`…/retry`·`GET …/work/stream`, 순수 함수 `app/services/research_work/views.py` | 11 |
| history | `ResearchStatus` 에 `phase`·`progress`·`generating` | 12 |
| 화면 | 429 `browser_active` 안내·진행 중 연구 링크(`activeResearchId`·`activeJobId`), 대기 순번 덧붙임(`queueLine`), 회차 `adoptedPapers` | 13 |

## 작업 순서

| Task | 내용 | 기대는 것 |
|---|---|---|
| 0 | worktree·브랜치·기준선 | — |
| 1 | 테이블 7개·마이그레이션 0007·등록·테스트 DB | 0 |
| 2 | critic 기준 스위치 | 0 |
| 3 | 근거 장부 데이터 `adopted_papers` | 2 |
| 4 | 인용 학술지 자리 | 0 |
| 5 | llm_client 호출별 모델 | 0 |
| 6 | 브라우저당 실행 제한·429 code | 2(API 테스트 수 70 에서 시작) |
| 7 | 딥리서치 대기 순번 | 6 |
| 8 | 생성 서비스(라우팅·재시도 규칙·핵심 개념) | 1·5 |
| 9 | 생성 디스패처·연구 채널·결과 적용 | 8 |
| 10 | 회수기 확장 | 7·9 |
| 11 | 연구 API·SSE | 1·8·9 |
| 12 | history 에 단계·진행·생성 여부 | 1·11 |
| 13 | 화면(429 안내·대기 순번·adopted_papers) | 3·6·7 의 응답 모양 |
| 14 | 백업 스크립트 | — |
| 15 | critic 두 갈래 판정 도구 | 2 |
| 16 | Qwen 한국어 표본 확인(1회성) | 8 |
| 17 | 문서·배포·전체 검증 | 전부 |

## 작업

### Task 0: worktree·브랜치·기준선

**왜:** 06a 를 저장소 루트 폴더나 다른 라운드 worktree 와 섞이지 않는 별도 worktree 에서 한다(여러 세션이 같은 저장소를 쓴다 — 본 작업 폴더에서 checkout 하지 않는다). 시작 전 테스트 수를 재 두어야 각 작업이 더한 수와 깨뜨린 것을 가를 수 있다.

**Files:** 없음 (작업 환경과 기준선만 — 커밋 없음)

**알아 둘 것:**
- `feat/round06-paper-agent` 는 dev + round06 spec(과 이 계획서)이다. 06a 브랜치는 거기서 딴다.
- 백엔드는 PATH 의 `python`(3.11 venv)으로 돌린다. 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 `test_book_chat.py`·`test_build_manifest.py`·`test_loaders.py` 셋이 수집 단계에서 오류가 난다 — 원래 상태다. `--continue-on-collection-errors` 없이 돌리면 `Interrupted: 3 errors during collection` 으로 한 건도 돌지 않는다.
- 새 worktree 에는 `frontend/node_modules`·`.nuxt` 가 없다. `.nuxt` 가 생기기 전에는 vitest 가 전부 실패한다(`TSConfckParseError … .nuxt/tsconfig.app.json`). `npm ci`(postinstall 이 `nuxt prepare` 로 `.nuxt` 를 만든다) 뒤 typecheck 를 먼저 돌린다.

- [ ] **Step 1: worktree 와 브랜치를 만든다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI worktree add .worktrees/round06a -b feat/round06a-foundation feat/round06-paper-agent
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a status --short --branch
```

Expected: 첫 줄이 `## feat/round06a-foundation` 이고 그 아래 변경 줄이 없다.

- [ ] **Step 2: 백엔드 기준선**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 마지막 줄 `1369 passed, 1 skipped, 2 warnings, 3 errors` (사본에서 25초 남짓). `3 errors` 는 위 수집 오류 셋이다.

이 계획이 건드리는 파일의 기준선(각각 `python -m pytest tests/<파일> -q -p no:cacheprovider`, 사본에서 실측):

| 파일 | 기준선 |
|---|---|
| `test_history_models.py` | 11 passed |
| `test_research_models.py` | 18 passed |
| `test_history_repository.py` | 49 passed |
| `test_history_api.py` | 44 passed |
| `test_job_runtime.py` | 77 passed |
| `test_llm_client.py` | 57 passed |
| `test_research_critic.py` | 62 passed |
| `test_research_planner.py` | 16 passed |
| `test_research_synthesizer.py` | 111 passed |
| `test_summarizer.py` | 24 passed |
| `test_paper_enricher.py` | 65 passed |
| `test_research_runner.py` | 72 passed |
| `test_research_state.py` | 70 passed |
| `test_research_api.py` | 68 passed |
| `test_research_tasks.py` | 94 passed |
| `test_research_relay.py` | 9 passed |
| `test_celery_schedule.py` | 2 passed |
| `test_prompts.py` | 8 passed |

- [ ] **Step 3: 프론트 기준선**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npm ci
npx nuxi typecheck 2>&1 | grep -c "error TS"
npx vitest run
npm run build 2>&1 | tail -1
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a status --short
```

Expected (사본에서 실측):
- `npm ci` — 30초 남짓, 끝에 `npm audit` 안내(취약점 수)가 나오지만 실패가 아니다.
- typecheck — `0`
- vitest — `Test Files  28 passed (28)` / `Tests  495 passed (495)`
- build — `└  ✨ Build complete!`
- `git status --short` — 빈 출력(`node_modules`·`.nuxt`·`.output` 은 `.gitignore` 에 있다).

---


### Task 1: 연구 어시스턴트 테이블 7개 — 모델·마이그레이션 0007·등록·테스트 DB

**왜:** spec §6-1. 06a~06c 가 쓸 테이블 7개를 06a 에 한 번에 만든다 — 스키마 변경을 배포 한 번(`create_all` + `alembic stamp 0007_research_work`, 함정 14)으로 끝내기 위해서다. 기존 테이블은 바꾸지 않는다. 다른 작업(디스패처·연구 API·history join)이 진짜 SQL 로 테스트할 수 있게 테스트 DB(`tests/history_sqlite.py`)에 새 테이블 둘과 세션 메서드를 더한다.

**Files:**
- Create: `app/models/research_work.py`
- Create: `app/alembic/versions/0007_research_work.py`
- Modify: `app/main.py` (lifespan 의 모델 import, 30-33행)
- Modify: `app/alembic/env.py` (모델 등록 목록 끝, 30행)
- Modify: `app/tests/history_sqlite.py` (모듈 docstring 8-10행, import 20-21행, `make_engine` 32-46행, `AsyncSessionOverSync` 끝 64-65행, `add_research_job` 뒤 74-77행)
- Test: `app/tests/test_research_work_models.py` (새 파일)

**알아 둘 것:**
- 모델 코드는 공통 계약 §1 그대로다. 연구 id = 출발 딥리서치 잡 id(`research_works.id` 가 `research_jobs.id` 를 FK 로 물고 ON DELETE CASCADE).
- 부분 유니크 인덱스 두 개(`ux_research_generations_running`·`ux_research_topics_slot`)에는 `postgresql_where` 와 함께 `sqlite_where` 를 둔다 — `postgresql_where` 만 두면 SQLite 테스트 DB 에서 조건 없는 전체 유니크가 되어 연구마다 생성이 평생 1건만 들어간다. 마이그레이션에는 `sqlite_where` 를 넣지 않는다(테스트가 확인한다).
- `Column(..., index=True)` 인 `work_id` 둘(`research_generations`·`research_topics`)은 모델에 `ix_research_generations_work_id`·`ix_research_topics_work_id` 인덱스를 만든다. 마이그레이션도 같은 이름으로 만든다(인덱스 정합 테스트가 이름·구성·unique·조건을 모두 비교한다).
- **테스트 DB 의 BIGINT PK:** 계약 §1 의 `make_engine` 은 칼럼 복사 고리에서 BIGINT 기본키를 `Integer` 로 바꾼다(Step 6 ② 는 계약 코드 그대로다). SQLite 는 `INTEGER PRIMARY KEY` 만 rowid 별칭(자동 번호)이고 `BIGINT` PK 는 자동 번호가 아니기 때문이다(`test_job_runtime.py` 가 `ingest_job_items` 에 id 를 늘 직접 넣는 이유). 이 두 줄(`if` 와 `col.type = sa.Integer()`)을 빼면 `add_generation` 이 `sqlite3.IntegrityError: NOT NULL constraint failed: research_generations.id` 로 실패한다(사본에서 빼 보고 실측 — 새 테스트 4개 실패). 운영 모델·마이그레이션은 BIGINT(Postgres `BIGSERIAL`) 그대로다. 모듈 docstring 의 "SQLite 가 모르는 Postgres 표기" 설명도 이 바꿈과 `pg_advisory_xact_lock` 빈 함수에 맞춰 고친다(Step 6 ⑤).
- `make_engine` 은 계약대로 `research_works`·`research_generations` 둘만 더한다. `research_topics`·`research_reading` 등 나머지 다섯을 SQLite 에서 쓰려는 작업은 그 튜플에 더한다(같은 BIGINT 처리가 그대로 적용된다).
- 기존 파일(`main.py`·`env.py`·`history_sqlite.py`)은 CRLF 다 — Edit 도구로 고친다. 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다(`core.autocrlf=true`).
- `import main` 은 로컬에서 torch 가 없어 실패한다 — 등록 확인은 `ast` 로 import 문을 읽는 테스트로 한다(`test_history_models.py` 와 같은 방식).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_work_models.py` (새 파일, 전체):

```python
"""models/research_work.py — 연구 어시스턴트(round06) 테이블 7개.

모델 ↔ 마이그레이션 0007 ↔ 등록(main.py lifespan·alembic env) 정합과, 다른 테스트가 쓰는
SQLite 대역(history_sqlite.make_engine)이 새 테이블의 부분 유니크 인덱스를 지키는지 본다.
"""
import ast
import asyncio
import sys
import types
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.research_work import (
    FACET_SCHEMA_VER, GEN_KINDS, GEN_OPEN_STATUSES, GEN_STATUSES, PRIORITY_BACKGROUND,
    PRIORITY_USER, READING_ORIGINS, READING_STATES, TOPIC_ORIGINS, TOPIC_STATES, WORK_PHASES,
    PaperFacet, ResearchGapCheck, ResearchGeneration, ResearchProposal, ResearchReading,
    ResearchTopic, ResearchWork,
)

APP_DIR = Path(__file__).resolve().parents[1]
MIGRATION_PATH = APP_DIR / "alembic" / "versions" / "0007_research_work.py"
MODELS = (ResearchWork, ResearchGeneration, ResearchTopic, ResearchGapCheck,
          ResearchReading, PaperFacet, ResearchProposal)
TABLES = [m.__table__ for m in MODELS]


def _column_signature(col, include_default=True):
    """(타입, nullable[, 기본값 유무]) — test_history_models.py 와 같은 지문. PK 는 기본값을 비교하지 않는다."""
    sig = [str(col.type), col.nullable]
    if include_default:
        sig.append(col.server_default is not None or col.default is not None)
    return tuple(sig)


def _table_signature(table):
    return {c.name: _column_signature(c, include_default=not c.primary_key) for c in table.columns}


def _fk_signature(table):
    return {(fk.parent.name, fk.target_fullname, fk.ondelete) for fk in table.foreign_keys}


def _index_parts(parts):
    return [p.name if isinstance(p, sa.Column) else p if isinstance(p, str) else str(p) for p in parts]


def _model_indexes(tables):
    sig = {}
    for table in tables:
        for ix in table.indexes:
            where = ix.dialect_options["postgresql"].get("where")
            sig[ix.name] = {
                "table_name": table.name,
                "parts": _index_parts(ix.expressions),
                "unique": bool(ix.unique),
                "postgresql_where": str(where) if where is not None else None,
            }
    return sig


def _run_migration(monkeypatch):
    """0007 의 upgrade()·downgrade() 를 alembic 없이 실행하고 op 호출을 캡처한다(로컬에 alembic 이 없다)."""
    import importlib.util as u

    captured = {"tables": {}, "fks": {}, "indexes": {}, "index_kwargs": set(),
                "created": [], "dropped": []}

    def fake_create_table(name, *args, **kwargs):
        table = sa.Table(name, sa.MetaData(), *args)
        captured["tables"][name] = _table_signature(table)
        captured["fks"][name] = _fk_signature(table)
        captured["created"].append(name)

    def fake_create_index(name, table_name, columns, **kwargs):
        where = kwargs.get("postgresql_where")
        captured["indexes"][name] = {
            "table_name": table_name,
            "parts": _index_parts(columns),
            "unique": bool(kwargs.get("unique", False)),
            "postgresql_where": str(where) if where is not None else None,
        }
        captured["index_kwargs"].update(kwargs)

    def fake_drop_table(name, *args, **kwargs):
        captured["dropped"].append(name)

    fake_op = types.ModuleType("alembic.op")
    fake_op.create_table = fake_create_table
    fake_op.create_index = fake_create_index
    fake_op.drop_table = fake_drop_table
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = fake_op
    monkeypatch.setitem(sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(sys.modules, "alembic.op", fake_op)

    spec = u.spec_from_file_location("_migration_0007", MIGRATION_PATH)
    module = u.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    module.downgrade()
    return module, captured


def _index(table, name):
    return next(ix for ix in table.indexes if ix.name == name)


class TestModelShape:
    def test_seven_tables_with_contract_names(self):
        assert [t.name for t in TABLES] == [
            "research_works", "research_generations", "research_topics", "research_gap_checks",
            "research_reading", "paper_facets", "research_proposals",
        ]

    def test_work_id_is_the_research_job_id(self):
        # 연구 id = 출발 딥리서치 잡 id — 잡을 지우면 연구도 지워지고, 기본값으로 새 id 를 만들지 않는다
        col = ResearchWork.__table__.c.id
        assert col.primary_key and col.default is None and col.server_default is None
        assert _fk_signature(ResearchWork.__table__) == {("id", "research_jobs.id", "CASCADE")}

    def test_children_cascade_from_research_works(self):
        for model in (ResearchGeneration, ResearchTopic, ResearchGapCheck, ResearchReading,
                      ResearchProposal):
            assert ("work_id", "research_works.id", "CASCADE") in _fk_signature(model.__table__)
        assert ("parent_id", "research_topics.id", "CASCADE") in _fk_signature(ResearchTopic.__table__)
        assert _fk_signature(PaperFacet.__table__) == set()   # 연구를 가로지르는 공용 캐시

    def test_composite_primary_keys(self):
        assert [c.name for c in ResearchReading.__table__.primary_key] == ["work_id", "cnts_id"]
        assert [c.name for c in PaperFacet.__table__.primary_key] == ["cnts_id", "schema_ver"]
        assert [c.name for c in ResearchProposal.__table__.primary_key] == ["work_id"]

    @pytest.mark.parametrize("values, column", [
        (WORK_PHASES, ResearchWork.__table__.c.phase),
        (GEN_KINDS, ResearchGeneration.__table__.c.kind),
        (GEN_STATUSES, ResearchGeneration.__table__.c.status),
        (TOPIC_ORIGINS, ResearchTopic.__table__.c.origin),
        (TOPIC_STATES, ResearchTopic.__table__.c.state),
        (READING_STATES, ResearchReading.__table__.c.state),
        (READING_ORIGINS, ResearchReading.__table__.c.origin),
    ], ids=["phase", "kind", "gen-status", "topic-origin", "topic-state", "reading-state",
            "reading-origin"])
    def test_enumerations_fit_their_columns(self, values, column):
        assert values and all(len(v) <= column.type.length for v in values)

    @pytest.mark.parametrize("column, allowed", [
        (ResearchWork.__table__.c.phase, WORK_PHASES),
        (ResearchGeneration.__table__.c.status, GEN_STATUSES),
        (ResearchTopic.__table__.c.state, TOPIC_STATES),
        (ResearchReading.__table__.c.state, READING_STATES),
    ], ids=["phase", "gen-status", "topic-state", "reading-state"])
    def test_server_defaults_are_declared_values(self, column, allowed):
        assert column.nullable is False
        assert column.server_default.arg.text.strip("'") in allowed

    def test_generation_constants(self):
        assert set(GEN_OPEN_STATUSES) <= set(GEN_STATUSES)
        assert GEN_OPEN_STATUSES == ("queued", "running")
        assert PRIORITY_USER > PRIORITY_BACKGROUND      # 사용자가 누른 생성이 배경 추출보다 먼저
        assert FACET_SCHEMA_VER == 1

    def test_optional_json_columns_store_none_as_sql_null(self):
        # JSON null 로 쓰면 IS NULL 검사가 늘 거짓이 된다(history.snapshot 과 같은 이유)
        for col in (ResearchWork.__table__.c.corpus_snapshot, ResearchGeneration.__table__.c.output,
                    ResearchTopic.__table__.c.corpus_snapshot,
                    ResearchGapCheck.__table__.c.corpus_snapshot):
            assert col.type.none_as_null is True, col

    def test_one_running_generation_per_work_on_both_dialects(self):
        # 전역 1건 디스패처의 이중 안전장치. sqlite_where 가 빠지면 SQLite 테스트에서 전체 유니크가 된다
        ix = _index(ResearchGeneration.__table__, "ux_research_generations_running")
        assert ix.unique and _index_parts(ix.expressions) == ["work_id"]
        pg = str(CreateIndex(ix).compile(dialect=postgresql.dialect()))
        lite = str(CreateIndex(ix).compile(dialect=sqlite.dialect()))
        assert pg.endswith("WHERE status = 'running'") and lite.endswith("WHERE status = 'running'")

    def test_first_four_topic_slots_are_unique_per_work(self):
        ix = _index(ResearchTopic.__table__, "ux_research_topics_slot")
        assert ix.unique and _index_parts(ix.expressions) == ["work_id", "slot"]
        lite = str(CreateIndex(ix).compile(dialect=sqlite.dialect()))
        assert str(ix.dialect_options["postgresql"]["where"]) == "slot IS NOT NULL"
        assert lite.endswith("WHERE slot IS NOT NULL")

    def test_dispatch_order_index_is_partial_on_queued(self):
        ix = _index(ResearchGeneration.__table__, "ix_research_generations_queued")
        assert _index_parts(ix.expressions) == ["priority DESC", "created_at", "id"]
        assert str(ix.dialect_options["postgresql"]["where"]) == "status = 'queued'"

    def test_owner_list_index_is_partial_and_newest_first(self):
        ix = _index(ResearchWork.__table__, "ix_research_works_owner_created")
        assert _index_parts(ix.expressions) == ["owner_sid", "created_at DESC"]
        assert str(ix.dialect_options["postgresql"]["where"]) == "deleted_at IS NULL"


class TestMigrationMatchesModel:
    def test_revision_chain(self, monkeypatch):
        module, _ = _run_migration(monkeypatch)
        assert module.revision == "0007_research_work"
        assert module.down_revision == "0006_history_items"

    def test_upgrade_creates_columns_matching_orm(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["tables"] == {t.name: _table_signature(t) for t in TABLES}

    def test_upgrade_foreign_keys_match_orm(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["fks"] == {t.name: _fk_signature(t) for t in TABLES}

    def test_upgrade_indexes_match_orm(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["indexes"] == _model_indexes(TABLES)

    def test_migration_has_no_sqlite_options(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["index_kwargs"] <= {"unique", "postgresql_where"}

    def test_downgrade_drops_in_reverse_order(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["dropped"] == list(reversed(captured["created"]))


def _imported_modules(path: Path) -> set[str]:
    """파일이 import 하는 모듈 이름 — `import a.b` 는 "a.b", `from a import b` 는 "a.b"."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


class TestModelRegistration:
    def test_alembic_env_registers_model(self):
        # 빠뜨리면 autogenerate 가 이 테이블을 모르는 것으로 보고 DROP TABLE 을 만든다
        assert "models.research_work" in _imported_modules(APP_DIR / "alembic" / "env.py")

    def test_lifespan_create_all_sees_models(self):
        # create_all 은 import 된 모델만 만든다 — research_works 의 FK 대상(research_jobs)도
        # 라우터 import 의 부수효과에 기대지 않고 명시한다
        imported = _imported_modules(APP_DIR / "main.py")
        assert {"models.research", "models.research_work"} <= imported


class TestSqliteHarness:
    """history_sqlite 가 새 테이블을 진짜 SQL 로 받는지 — 디스패처·API 테스트가 이 위에서 돈다."""

    @pytest.fixture
    def engine(self):
        return make_engine()

    def test_research_tables_exist(self, engine):
        names = set(sa.inspect(engine).get_table_names())
        assert {"research_jobs", "research_works", "research_generations"} <= names

    def test_generation_ids_are_assigned_by_the_database(self, engine):
        work = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work)
        first = add_generation(engine, work)
        second = add_generation(engine, work, kind="topic_card")
        assert isinstance(first, int) and second > first

    def test_second_running_generation_in_a_work_is_rejected(self, engine):
        work = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work)
        add_generation(engine, work, status="running")
        add_generation(engine, work, status="queued")        # 부분 인덱스 — queued 는 몇 건이든
        add_generation(engine, work, status="done")
        with pytest.raises(sa.exc.IntegrityError):
            add_generation(engine, work, status="running")

    def test_running_generations_in_different_works_coexist(self, engine):
        for _ in range(2):
            work = add_research_job(engine, status="completed", stage="synthesized")
            add_work(engine, work)
            add_generation(engine, work, status="running")
        with engine.connect() as conn:
            n = conn.execute(sa.text(
                "SELECT count(*) FROM research_generations WHERE status = 'running'")).scalar_one()
        assert n == 2

    def test_add_work_stores_contract_defaults(self, engine):
        work = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work, owner_sid="sid-a", concepts=["독서", "격차"])
        with engine.connect() as conn:
            row = conn.execute(sa.select(ResearchWork.__table__)).one()
        assert (row.id, row.owner_sid, row.phase, row.concepts, row.concept_members,
                row.progress, row.is_example) == (work, "sid-a", "topics", ["독서", "격차"], {}, {},
                                                  False)

    def test_advisory_lock_is_a_no_op_function(self, engine):
        async def _go():
            db = AsyncSessionOverSync(engine)
            try:
                return await db.scalar(sa.select(sa.func.pg_advisory_xact_lock(42)))
            finally:
                await db.close()
        assert asyncio.run(_go()) is None

    def test_async_session_get_add_flush_scalar(self, engine):
        work = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work)

        async def _go():
            db = AsyncSessionOverSync(engine)
            try:
                gen = ResearchGeneration(work_id=work, kind="concepts", priority=PRIORITY_USER,
                                         status="queued", input={"question": "독서 격차"})
                db.add(gen)
                await db.flush()
                gen_id = gen.id
                await db.commit()
                loaded = await db.get(ResearchGeneration, gen_id)
                n = await db.scalar(
                    sa.select(sa.func.count()).select_from(ResearchGeneration)
                    .where(ResearchGeneration.work_id == work)
                )
                return gen_id, loaded.kind, loaded.input, (await db.get(ResearchWork, work)).phase, n
            finally:
                await db.close()

        gen_id, kind, inp, phase, n = asyncio.run(_go())
        assert isinstance(gen_id, int)
        assert (kind, inp, phase, n) == ("concepts", {"question": "독서 격차"}, "topics", 1)

    def test_get_of_unknown_work_is_none(self, engine):
        # make_engine 은 부를 때마다 빈 DB 다 — 테스트끼리 행을 나누지 않는다
        async def _go():
            db = AsyncSessionOverSync(engine)
            try:
                return await db.get(ResearchWork, uuid.uuid4())
            finally:
                await db.close()
        assert asyncio.run(_go()) is None
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_models.py -q -p no:cacheprovider`

Expected: `1 error` — 수집 단계 `ImportError: cannot import name 'add_generation' from 'history_sqlite'` (이어서 `models.research_work` 도 아직 없다).

- [ ] **Step 3: 모델을 만든다**

`app/models/research_work.py` (새 파일, 전체 — 공통 계약 §1 그대로):

```python
"""research_work.py — 연구 어시스턴트(round06) 테이블.

딥리서치를 [이 연구 이어가기] 로 이어간 연구 한 건과 그 산출물. 연구 id = 출발 딥리서치 잡 id.
기존 테이블은 건드리지 않는다. create_all 이 만들고 alembic 은 0007 로 stamp 한다(함정 14).
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, SmallInteger, String,
    Text, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.book import Base

WORK_PHASES = ("topics", "reading", "proposal", "done")
GEN_KINDS = ("concepts", "topic_card", "refine", "facet", "outline", "section", "paragraph")
GEN_STATUSES = ("queued", "running", "done", "failed", "canceled")
GEN_OPEN_STATUSES = ("queued", "running")
PRIORITY_USER = 10          # 사용자가 누른 생성
PRIORITY_BACKGROUND = 0     # 배경 특징 추출(06c)
TOPIC_ORIGINS = ("report_seed", "grid_seed", "other", "refine", "user")
TOPIC_STATES = ("candidate", "picked", "folded", "insufficient")
READING_STATES = ("candidate", "in", "out")
READING_ORIGINS = ("evidence", "revived", "broaden", "related", "user")
FACET_SCHEMA_VER = 1


class ResearchWork(Base):
    __tablename__ = "research_works"
    __table_args__ = (
        Index(
            "ix_research_works_owner_created", "owner_sid", text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
    id              = Column(UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="CASCADE"),
                             primary_key=True)
    owner_sid       = Column(String(64))
    user_id         = Column(String(64))
    share_token     = Column(String(64))
    phase           = Column(String(16), nullable=False, server_default=text("'topics'"))
    concepts        = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    concept_members = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    topic_id        = Column(BigInteger)
    progress        = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    corpus_snapshot = Column(JSONB(none_as_null=True))
    memo            = Column(Text)
    is_example      = Column(Boolean, nullable=False, server_default=text("false"))
    created_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                             onupdate=func.now())
    deleted_at      = Column(DateTime(timezone=True))


class ResearchGeneration(Base):
    __tablename__ = "research_generations"
    __table_args__ = (
        # 연구마다 도는 생성은 1건 — 전역 1건 디스패처(§6-3)의 이중 안전장치.
        # sqlite_where 를 함께 두지 않으면 SQLite 테스트에서 전체 유니크가 된다
        Index(
            "ux_research_generations_running", "work_id", unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
        Index(
            "ix_research_generations_queued", text("priority DESC"), "created_at", "id",
            postgresql_where=text("status = 'queued'"),
        ),
    )
    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    work_id     = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    kind        = Column(String(16), nullable=False)
    target      = Column(String(64))
    priority    = Column(SmallInteger, nullable=False, server_default=text("0"))
    status      = Column(String(16), nullable=False, server_default=text("'queued'"))
    model       = Column(String(64))
    input       = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    output      = Column(JSONB(none_as_null=True))
    error       = Column(Text)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at  = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    updated_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                         onupdate=func.now())


class ResearchTopic(Base):
    __tablename__ = "research_topics"
    __table_args__ = (
        # 처음 4장의 자리(1~4)는 연구마다 유일 — 4번째 격자 카드 자리가 이미 차 있으면 자동 생성하지 않는다(§5-2)
        Index(
            "ux_research_topics_slot", "work_id", "slot", unique=True,
            postgresql_where=text("slot IS NOT NULL"),
            sqlite_where=text("slot IS NOT NULL"),
        ),
    )
    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    work_id         = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    parent_id       = Column(BigInteger, ForeignKey("research_topics.id", ondelete="CASCADE"))
    slot            = Column(SmallInteger)
    origin          = Column(String(16), nullable=False)
    seed            = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    card            = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    state           = Column(String(16), nullable=False, server_default=text("'candidate'"))
    corpus_snapshot = Column(JSONB(none_as_null=True))
    created_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                             onupdate=func.now())


class ResearchGapCheck(Base):
    __tablename__ = "research_gap_checks"
    __table_args__ = (Index("ix_research_gap_checks_work_cell", "work_id", "cell_key"),)
    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    work_id         = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                             nullable=False)
    cell_key        = Column(String(128), nullable=False)
    query           = Column(Text, nullable=False)
    results         = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    m               = Column(Integer, nullable=False)
    verdict         = Column(String(16), nullable=False)
    corpus_snapshot = Column(JSONB(none_as_null=True))
    created_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResearchReading(Base):
    __tablename__ = "research_reading"
    work_id     = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                         primary_key=True)
    cnts_id     = Column(String(64), primary_key=True)
    state       = Column(String(16), nullable=False, server_default=text("'candidate'"))
    origin      = Column(String(16), nullable=False)
    origin_ref  = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    group_label = Column(Text)
    position    = Column(Integer)
    note        = Column(Text)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                         onupdate=func.now())


class PaperFacet(Base):
    __tablename__ = "paper_facets"
    cnts_id    = Column(String(64), primary_key=True)
    schema_ver = Column(SmallInteger, primary_key=True)
    facets     = Column(JSONB, nullable=False)
    model      = Column(String(64))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResearchProposal(Base):
    __tablename__ = "research_proposals"
    work_id    = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                        primary_key=True)
    version    = Column(Integer, nullable=False, server_default=text("1"))
    outline    = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sections   = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                        onupdate=func.now())
```

- [ ] **Step 4: 마이그레이션 0007 을 만든다**

`app/alembic/versions/0007_research_work.py` (새 파일, 전체):

```python
"""연구 어시스턴트 테이블 (round06)

research_works·research_generations·research_topics·research_gap_checks·research_reading·
paper_facets·research_proposals — 딥리서치를 이어간 연구와 그 산출물. 기존 테이블은 건드리지 않는다.
운영은 lifespan 의 create_all 이 만들고 이 리비전으로 stamp 한다(함정 14).

Revision ID: 0007_research_work
Revises: 0006_history_items
Create Date: 2026-10-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0007_research_work"
down_revision: Union[str, None] = "0006_history_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _work_fk(**kw) -> sa.Column:
    return sa.Column(
        "work_id", UUID(as_uuid=True),
        sa.ForeignKey("research_works.id", ondelete="CASCADE"), **kw,
    )


def upgrade() -> None:
    op.create_table(
        "research_works",
        sa.Column(
            "id", UUID(as_uuid=True),
            sa.ForeignKey("research_jobs.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("owner_sid", sa.String(64)),
        sa.Column("user_id", sa.String(64)),
        sa.Column("share_token", sa.String(64)),
        sa.Column("phase", sa.String(16), nullable=False, server_default=sa.text("'topics'")),
        sa.Column("concepts", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("concept_members", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("topic_id", sa.BigInteger()),
        sa.Column("progress", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("corpus_snapshot", JSONB()),
        sa.Column("memo", sa.Text()),
        sa.Column("is_example", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_research_works_owner_created", "research_works",
        ["owner_sid", sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "research_generations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _work_fk(nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target", sa.String(64)),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("model", sa.String(64)),
        sa.Column("input", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", JSONB()),
        sa.Column("error", sa.Text()),
        _created_at(),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        _updated_at(),
    )
    op.create_index("ix_research_generations_work_id", "research_generations", ["work_id"])
    # 연구마다 도는 생성은 1건 — 전역 1건 디스패처의 이중 안전장치
    op.create_index(
        "ux_research_generations_running", "research_generations", ["work_id"],
        unique=True, postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "ix_research_generations_queued", "research_generations",
        [sa.text("priority DESC"), "created_at", "id"],
        postgresql_where=sa.text("status = 'queued'"),
    )

    op.create_table(
        "research_topics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _work_fk(nullable=False),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("research_topics.id", ondelete="CASCADE")),
        sa.Column("slot", sa.SmallInteger()),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("seed", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("card", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", sa.String(16), nullable=False, server_default=sa.text("'candidate'")),
        sa.Column("corpus_snapshot", JSONB()),
        _created_at(),
        _updated_at(),
    )
    op.create_index("ix_research_topics_work_id", "research_topics", ["work_id"])
    # 처음 4장의 자리(1~4)는 연구마다 유일
    op.create_index(
        "ux_research_topics_slot", "research_topics", ["work_id", "slot"],
        unique=True, postgresql_where=sa.text("slot IS NOT NULL"),
    )

    op.create_table(
        "research_gap_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _work_fk(nullable=False),
        sa.Column("cell_key", sa.String(128), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("results", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("m", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("corpus_snapshot", JSONB()),
        _created_at(),
    )
    op.create_index(
        "ix_research_gap_checks_work_cell", "research_gap_checks", ["work_id", "cell_key"],
    )

    op.create_table(
        "research_reading",
        _work_fk(primary_key=True),
        sa.Column("cnts_id", sa.String(64), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False, server_default=sa.text("'candidate'")),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("origin_ref", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("group_label", sa.Text()),
        sa.Column("position", sa.Integer()),
        sa.Column("note", sa.Text()),
        _created_at(),
        _updated_at(),
    )

    op.create_table(
        "paper_facets",
        sa.Column("cnts_id", sa.String(64), primary_key=True),
        sa.Column("schema_ver", sa.SmallInteger(), primary_key=True),
        sa.Column("facets", JSONB(), nullable=False),
        sa.Column("model", sa.String(64)),
        _created_at(),
    )

    op.create_table(
        "research_proposals",
        _work_fk(primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("outline", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sections", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _updated_at(),
    )


def downgrade() -> None:
    op.drop_table("research_proposals")
    op.drop_table("paper_facets")
    op.drop_table("research_reading")
    op.drop_table("research_gap_checks")
    op.drop_table("research_topics")
    op.drop_table("research_generations")
    op.drop_table("research_works")
```

- [ ] **Step 5: lifespan 과 alembic env 에 등록한다**

`app/main.py` — 교체 전:

```python
    import models.history
    from sqlalchemy import text
```

교체 후:

```python
    import models.history
    import models.research          # research_works 의 FK 대상 — 라우터 import 부수효과에 기대지 않는다
    import models.research_work
    from sqlalchemy import text
```

`app/alembic/env.py` — 교체 전:

```python
from models import history as _history_mod    # noqa: F401, E402
```

교체 후:

```python
from models import history as _history_mod    # noqa: F401, E402
from models import research_work as _research_work_mod  # noqa: F401, E402
```

- [ ] **Step 6: 테스트 DB 를 넓힌다**

`app/tests/history_sqlite.py` 를 다섯 군데 고친다.

① import — 교체 전:

```python
from models.history import HistoryItem
from models.research import ResearchJob
```

교체 후:

```python
from models.history import HistoryItem
from models.research import ResearchJob
from models.research_work import ResearchGeneration, ResearchWork
```

② `make_engine` — 교체 전:

```python
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    metadata = sa.MetaData()
    for table in (HistoryItem.__table__, ResearchJob.__table__):
        copy = table.to_metadata(metadata)
        for col in copy.columns:
            default = col.server_default
            if default is not None and "::" in str(getattr(default, "arg", "")):
                col.server_default = None
    metadata.create_all(engine)
    return engine
```

교체 후:

```python
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )

    @sa.event.listens_for(engine, "connect")
    def _pg_functions(dbapi_conn, _record):
        # Postgres 트랜잭션 잠금은 SQLite 에서 아무 일도 하지 않는 함수로 둔다 — 잠금 순서는 문장 기록으로 확인한다
        dbapi_conn.create_function("pg_advisory_xact_lock", 1, lambda _key: None)

    metadata = sa.MetaData()
    for table in (HistoryItem.__table__, ResearchJob.__table__,
                  ResearchWork.__table__, ResearchGeneration.__table__):
        copy = table.to_metadata(metadata)
        for col in copy.columns:
            default = col.server_default
            if default is not None and "::" in str(getattr(default, "arg", "")):
                col.server_default = None
            # SQLite 는 INTEGER PRIMARY KEY 만 자동으로 번호를 매긴다 — BIGINT 기본키는 테스트 사본에서만 INTEGER 로
            if col.primary_key and isinstance(col.type, sa.BigInteger):
                col.type = sa.Integer()
    metadata.create_all(engine)
    return engine
```

③ `AsyncSessionOverSync` 끝 — 교체 전:

```python
    async def close(self):
        self._session.close()


def add_research_job(
```

교체 후:

```python
    async def close(self):
        self._session.close()

    async def get(self, model, pk):
        return self._session.get(model, pk)

    def add(self, obj):
        self._session.add(obj)

    async def flush(self):
        self._session.flush()

    async def scalar(self, stmt, params=None):
        return self._session.scalar(stmt, params)


def add_research_job(
```

④ `add_research_job` 뒤 — 교체 전:

```python
    return job_id


def raw_row(
```

교체 후:

```python
    return job_id


def add_work(engine: sa.Engine, job_id: uuid.UUID, *, owner_sid: str | None = None,
             phase: str = "topics", concepts: list | None = None, is_example: bool = False) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(ResearchWork.__table__).values(
            id=job_id, owner_sid=owner_sid, phase=phase, concepts=concepts or [],
            concept_members={}, progress={}, is_example=is_example,
        ))


def add_generation(engine: sa.Engine, work_id: uuid.UUID, *, kind: str = "concepts",
                   status: str = "queued", priority: int = 10, input: dict | None = None,
                   started_at=None) -> int:
    with engine.begin() as conn:
        res = conn.execute(sa.insert(ResearchGeneration.__table__).values(
            work_id=work_id, kind=kind, status=status, priority=priority,
            input=input or {}, started_at=started_at,
        ).returning(ResearchGeneration.__table__.c.id))
        return res.scalar_one()


def raw_row(
```

⑤ 모듈 docstring — 교체 전:

```python
SQLite 가 모르는 Postgres 표기 둘만 테스트 쪽에서 바꾼다 — JSONB 타입 이름(JSON 으로
그린다)과 '::jsonb' 가 붙은 서버 기본값(테스트 테이블에서만 뺀다. 저장소는 params 를
늘 채워 넣는다). 운영 모델·마이그레이션은 그대로다.
```

교체 후:

```python
SQLite 가 모르는 Postgres 표기 셋만 테스트 쪽에서 바꾼다 — JSONB 타입 이름(JSON 으로
그린다), '::jsonb' 가 붙은 서버 기본값(테스트 테이블에서만 뺀다. 저장소는 params 를
늘 채워 넣는다), BIGINT 기본키(INTEGER 로 — SQLite 는 INTEGER PRIMARY KEY 만 자동으로
번호를 매긴다). Postgres 함수 pg_advisory_xact_lock 은 아무 일도 하지 않는 SQLite 함수로
둔다(잠금 순서는 문장 기록으로 확인한다). 운영 모델·마이그레이션은 그대로다.
```

- [ ] **Step 7: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_models.py -q -p no:cacheprovider`

Expected: `37 passed`

테스트 DB 를 함께 쓰는 기존 테스트와 모델·마이그레이션 테스트:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_history_models.py tests/test_research_models.py tests/test_history_repository.py tests/test_history_api.py tests/test_job_runtime.py -q -p no:cacheprovider`

Expected: `199 passed, 1 warning` (11 + 18 + 49 + 44 + 77, 기준선 그대로. 경고는 기존 Pydantic class-based config 폐기 예고다)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: `1406 passed, 1 skipped, 2 warnings, 3 errors` (기준선 1369 + 37). `3 errors` 는 Task 0 의 수집 오류 셋이다.

- [ ] **Step 8: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/models/research_work.py app/alembic/versions/0007_research_work.py app/alembic/env.py app/main.py app/tests/history_sqlite.py app/tests/test_research_work_models.py && git status --short && git commit -m "[Feat] round06a — 연구 어시스턴트 테이블 7개(research_works·research_generations·research_topics·research_gap_checks·research_reading·paper_facets·research_proposals) 모델과 마이그레이션 0007 을 더한다. 운영은 lifespan create_all 로 만들고 0007 로 stamp 한다(함정 14) — lifespan 이 models.research·models.research_work 를 직접 import 하고 alembic env 에 등록한다. 생성은 연구마다 running 1건(부분 유니크 인덱스, SQLite 에도 같은 조건), 처음 4장 자리는 연구마다 유일. 테스트 DB(history_sqlite)는 새 테이블 둘·pg_advisory_xact_lock 빈 함수·세션 get/add/flush/scalar·add_work/add_generation 을 더하고 BIGINT PK 를 SQLite 자동 번호로 만든다"
```

---


### Task 2: critic 기준 스위치 (`critic_scope`)

**왜:** spec §5-1·D11·D16. 무관 제외(off_topic)가 하위질문 기준이라, 하위질문에서 조금 벗어났을 뿐 원 질문을 다루는 논문까지 빠진다(과잉 제외). 원 질문을 critic 에 넘기고 off_topic 만 "원 질문의 주제와 무관한 것"으로 좁히는 갈래(1)를 더하되, 운영에서 고정 질문을 두 갈래로 돌려 합격하기 전까지는 지금 기준(0)이 기본값이다. 0 갈래는 프롬프트·입력이 지금과 글자 그대로여야 두 갈래를 나란히 비교할 수 있다. 충분·부족 판정·출력 JSON 형식·파서·`exclude_off_topic` 동작은 두 갈래 모두 그대로다.

**Files:**
- Modify: `app/services/research/state.py` (`DEFAULT_PARAMS` 18–30행, `_PARAM_BOUNDS` 36–45행)
- Create: `app/domains/nl_library/prompts/research_critique_question.yaml`
- Modify: `app/services/research/critic.py` (`critique` 190–200행)
- Modify: `app/services/research/runner.py` (critic 호출 253–256행)
- Test: `app/tests/test_research_state.py` (34–41행 키 집합, 107–111행 `test_off_topic_exclusion_rejects_anything_else` 뒤에 3개 추가)
- Test: `app/tests/test_research_critic.py` (1–12행 import, 파일 끝 435–437행 뒤에 `TestCriticScope` 추가)
- Test: `app/tests/test_research_runner.py` (critic 대역 9곳 — 36·49·70·403·450·521·724·1024·1184행, 412행 `TestReadTransaction` 뒤에 `TestOriginalQuestion` 추가)
- Test: `app/tests/test_research_api.py` (`TestCreate` 269–272행 뒤에 2개 추가)

**알아 둘 것:**
- `app/domains/nl_library/prompts/research_critique.yaml` 은 **한 글자도 바꾸지 않는다.** 새 테스트가 이 파일의 sha256 (줄바꿈을 LF 로 맞춰 잰 값 `5b161222d7f47a330c05b9de942dd231200b478ec5af92bba44bdcf714cc9972` — git 에 저장된 blob 과 같다)을 박아 둔다. 이 worktree 는 `core.autocrlf=true` 라 작업 트리 파일은 CRLF 이고, CRLF 그대로 재면 `777cd3fb…` 가 나온다 — 테스트가 `\r\n` 을 `\n` 으로 바꿔 잰다.
- 새 프롬프트 `research_critique_question.yaml` 은 원본과 **두 군데만** 다르다(계약 §2): (1) system — 판단 기준 끝에 원 질문의 쓰임을 밝히는 한 줄(`- 원 질문은 무관한 근거(off_topic)를 가를 때만 씁니다. 충분·부족은 위 기준대로 하위질문을 두고 판단하세요.`)을 붙이고, off_topic 문장을 원 질문 기준 + "하위질문에서 벗어났더라도 원 질문의 주제를 다루는 논문은 넣지 않습니다." 로 바꾼다. (2) user 첫 줄 `원 질문: {{ question }}`. 판단 기준 한 줄을 붙이는 까닭: user 맨 앞에 원 질문이 오는데 system 이 그 쓰임을 말하지 않으면 모델이 충분·부족까지 원 질문을 두고 가를 수 있다 — spec §5-1 은 충분·부족을 두 갈래 모두 하위질문 기준으로 두므로, 그렇게 되면 D11 비교의 차이가 off_topic 기준 하나가 아니게 된다. 기존 판단 기준 네 줄·편수 문단·출력 JSON·문체 규칙은 그대로다. 예시는 넣지 않는다(함정 15). `test_scope_one_changes_only_the_off_topic_rule` 이 system 에서 판단 기준 끝에 붙은 그 한 줄을 빼면 달라진 줄이 off_topic 문장 정확히 1줄인지 본다.
- `critique` 는 `params.get("critic_scope", 0) == 1 and question` 일 때만 새 프롬프트를 쓴다. 그 밖(0, 또는 1 인데 원 질문이 없음)은 지금처럼 `research_critique` 를 지금 다섯 변수로 렌더하고 `question` 을 넘기지 않는다.
- 러너는 `critique_fn(..., params=params, question=state.question)` 으로 **늘** 넘긴다. 그래서 `test_research_runner.py` 의 critic 대역이 `question` 키워드를 받아야 한다 — 대역은 이 파일에만 9곳이다(`_FakeCritic` 36·`_SuggestingCritic` 49·`_ParseFailedCritic` 70·`_critic` 403·`_Critic` 450·`_CriticWithQueries` 521·`_ScriptedCritic` 724·`_FlagByPaper` 1024·`_Once` 1184행). `test_research_tasks.py` 는 `explore_subquestion` 을 통째로 대역으로 바꿔 critic 대역이 없다(계약의 "runner·tasks 8곳"과 다르다 — 실제 코드 기준).
- 워커(`workers/research_tasks.py`)는 고치지 않는다. `state.question` 은 새로 돌 때 `job.question`, 재개 때 `snap["question"]`(`restore_state`)에서 이미 채워진다. `critic_scope` 는 이미 넘기는 `params` 에 실린다.
- API(`create_research`)는 `merge_params(req.params)` 로 기본값까지 합쳐 저장한다. 06a 뒤 만든 잡은 `critic_scope=0` 이 `params` 에 명시적으로 남아, 나중에 기본값을 1 로 바꿔도 그 잡을 retry 하면 0 으로 돈다(만들 때의 기준 유지). 06a 전 잡은 키가 없어 워커의 `merge_params` 가 실행 시점 기본값을 채운다. 평가 도구(Task 15)는 잡을 만들 때 `params: {"critic_scope": 1}` 로 갈래 1 을 만든다 — `test_research_api.py` 에 그 경로를 잠근다.
- 이 저장소에는 pytest-asyncio 가 없다 — async 는 `asyncio.run` 으로 돌린다. 실패 메시지의 한글이 깨져 보이면(cp949 콘솔) Git Bash 에서 명령 앞에 `PYTHONIOENCODING=utf-8` 을 붙인다.
- 기존 파일은 **Edit 도구로** 고친다(CRLF 유지). 새 YAML 의 줄바꿈은 커밋 때 git 이 맞춘다.

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_research_state.py` — 교체 전(34–41행 안):

```python
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
            "exclude_off_topic",
        }
```

교체 후:

```python
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
            "exclude_off_topic", "critic_scope",
        }
```

`app/tests/test_research_state.py` — 교체 전(107–111행):

```python
    @pytest.mark.parametrize("value", [2, -1, True, "0", 0.0])
    def test_off_topic_exclusion_rejects_anything_else(self, value):
        # True 는 int 의 서브클래스라 막지 않으면 1 로 통과한다
        with pytest.raises(ValueError, match="exclude_off_topic"):
            merge_params({"exclude_off_topic": value})
```

교체 후:

```python
    @pytest.mark.parametrize("value", [2, -1, True, "0", 0.0])
    def test_off_topic_exclusion_rejects_anything_else(self, value):
        # True 는 int 의 서브클래스라 막지 않으면 1 로 통과한다
        with pytest.raises(ValueError, match="exclude_off_topic"):
            merge_params({"exclude_off_topic": value})

    def test_critic_scope_is_the_current_criterion_by_default(self):
        # 원 질문 기준(1)은 운영에서 두 갈래 판정에 합격한 뒤에 기본값을 바꿔 켠다(spec D11)
        assert DEFAULT_PARAMS["critic_scope"] == 0

    @pytest.mark.parametrize("value", [0, 1])
    def test_critic_scope_takes_zero_or_one(self, value):
        assert merge_params({"critic_scope": value})["critic_scope"] == value

    @pytest.mark.parametrize("value", [2, -1, True, "1", 1.0])
    def test_critic_scope_rejects_anything_else(self, value):
        # '알 수 없는 파라미터: critic_scope' 가 아니라 값 검사에서 거부돼야 한다 — 그래서 콜론 없는 문구로 맞춘다
        with pytest.raises(ValueError, match="파라미터 critic_scope"):
            merge_params({"critic_scope": value})
```

`app/tests/test_research_critic.py` — 교체 전(1–12행):

```python
import asyncio
import json
import logging

import httpx
import pytest

from services.research import critic
from services.research.critic import (
    _EXCERPT_LEN, _MAX_LISTED, _PARSE_FAILED_NOTE, Verdict, format_evidence_list,
    parse_verdict, should_recheck,
)
```

교체 후:

```python
import asyncio
import hashlib
import json
import logging
from pathlib import Path

import httpx
import pytest

from services.prompts import get_prompt
from services.research import critic
from services.research.critic import (
    _EXCERPT_LEN, _MAX_LISTED, _PARSE_FAILED_NOTE, Verdict, format_evidence_list,
    parse_verdict, should_recheck,
)
```

`app/tests/test_research_critic.py` — 교체 전(파일 끝, 435–437행):

```python
        evs = self._titled("자원 할당 기법에 관한 연구", "엣지 컴퓨팅 스케줄링", "MPEG-7")
        v, _ = self._note_run(monkeypatch, note, evs)
        assert v.note == expected
```

교체 후:

```python
        evs = self._titled("자원 할당 기법에 관한 연구", "엣지 컴퓨팅 스케줄링", "MPEG-7")
        v, _ = self._note_run(monkeypatch, note, evs)
        assert v.note == expected


# critic_scope=0 갈래의 프롬프트 파일 sha256(줄바꿈을 LF 로 맞춰 잰다 — Windows 체크아웃은 CRLF 다).
# 두 갈래를 나란히 비교하는 기준이라 한 글자도 바뀌면 안 된다. 기준을 바꾸려면 새 갈래 파일을 만든다
_CRITIQUE_SHA256 = "5b161222d7f47a330c05b9de942dd231200b478ec5af92bba44bdcf714cc9972"


class TestCriticScope:
    """잡 파라미터 critic_scope — 0 은 지금 기준(프롬프트·입력 글자 그대로), 1 은 원 질문 기준(무관 판정만
    원 질문의 주제로 좁히고, 충분·부족은 하위질문 기준 그대로). chat 만 대역으로 바꿔 실제 템플릿을 거친다."""

    QUESTION = "엣지 컴퓨팅의 자원 할당 연구는 어디까지 왔나"
    # 1 갈래가 판단 기준 끝에 붙이는 한 줄 — 원 질문은 off_topic 에만 쓰고 충분·부족은 하위질문 기준(spec §5-1)
    SCOPE_RULE = "- 원 질문은 무관한 근거(off_topic)를 가를 때만 씁니다. 충분·부족은 위 기준대로 하위질문을 두고 판단하세요."

    def _evidence(self):
        return [Evidence(id="E1", cnts_id="A", meta={"title": "논문 가", "pub_date": "2008"},
                         chunks=[Chunk("c1", "본문 발췌", 1, 1, 0.9)])]

    def _run(self, monkeypatch, *, question, reply=None, **job_params):
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append((messages, params))
            return reply or '{"verdict": "sufficient", "note": "충분하다", "new_queries": [], "off_topic": []}'

        monkeypatch.setattr(critic, "chat", fake_chat)
        v = asyncio.run(critic.critique(
            SubQuestion(idx=0, text="하위질문", queries=["첫 검색어"]), self._evidence(),
            params=merge_params(job_params), question=question,
        ))
        ((messages, llm_params),) = seen
        return v, messages[0]["content"], messages[1]["content"], llm_params

    def _current(self, **job_params):
        # 0 갈래가 보내야 하는 것 — 지금 템플릿을 지금 다섯 변수로 렌더한 결과
        return get_prompt("research_critique").render(
            subquestion="하위질문", evidence_count=1,
            evidence_list=format_evidence_list(self._evidence()),
            min_evidence=merge_params(job_params)["min_evidence_per_subq"], tried_queries="첫 검색어",
        )

    def test_current_prompt_file_is_unchanged(self):
        path = Path(__file__).resolve().parents[1] / "domains" / "nl_library" / "prompts" / "research_critique.yaml"
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(raw).hexdigest() == _CRITIQUE_SHA256

    @pytest.mark.parametrize("job_params", [{}, {"critic_scope": 0}])
    def test_scope_zero_sends_the_current_prompt_verbatim(self, monkeypatch, job_params):
        # 러너는 원 질문을 늘 넘긴다 — 0 갈래는 받아도 쓰지 않는다
        _, system, user, llm_params = self._run(monkeypatch, question=self.QUESTION, **job_params)
        assert (system, user, llm_params) == self._current(**job_params)
        assert self.QUESTION not in system + user

    def test_scope_one_puts_the_original_question_first(self, monkeypatch):
        _, _, user, _ = self._run(monkeypatch, question=self.QUESTION, critic_scope=1)
        _, current_user, _ = self._current()
        assert user == f"원 질문: {self.QUESTION}\n{current_user}"

    def test_scope_one_judges_off_topic_against_the_original_question(self, monkeypatch):
        _, system, _, _ = self._run(monkeypatch, question=self.QUESTION, critic_scope=1)
        assert ("off_topic 에는 발췌가 원 질문의 주제와 무관한 근거(같은 단어를 다른 뜻으로 쓴 논문 포함)의 "
                "번호를 정수로 씁니다. 하위질문에서 벗어났더라도 원 질문의 주제를 다루는 논문은 넣지 않습니다.") in system
        assert "off_topic 에는 발췌가 하위질문의 핵심 개념을 다루지 않는 근거" not in system

    def test_scope_one_changes_only_the_off_topic_rule(self, monkeypatch):
        """충분·부족 기준·출력 JSON 형식·문체 규칙·LLM 파라미터는 그대로다. 달라지는 것은 판단 기준 끝에 붙는
        원 질문의 쓰임 한 줄과 off_topic 문장 하나뿐이다. 다른 줄이 바뀌거나 예시가 붙으면 두 갈래의 차이가
        off_topic 기준 하나가 아니게 된다(예시는 개수를 베낀다 — 함정 15)."""
        _, system, _, llm_params = self._run(monkeypatch, question=self.QUESTION, critic_scope=1)
        current_system, _, current_params = self._current()
        old_lines, new_lines = current_system.splitlines(), system.splitlines()
        end = old_lines.index("판단 기준:") + 1
        while old_lines[end].startswith("- "):
            end += 1                                     # 판단 기준 마지막 줄 바로 뒤
        assert new_lines[end] == self.SCOPE_RULE
        rest = new_lines[:end] + new_lines[end + 1:]
        assert len(rest) == len(old_lines)
        ((old, new),) = [(a, b) for a, b in zip(old_lines, rest) if a != b]
        assert old.startswith("off_topic 에는 발췌가 하위질문의 핵심 개념을 다루지 않는 근거")
        assert new.startswith("off_topic 에는 발췌가 원 질문의 주제와 무관한 근거")
        assert old.partition(" 번호는 근거 목록")[2] == new.partition(" 번호는 근거 목록")[2]
        assert llm_params == current_params

    def test_scope_one_without_a_question_uses_the_current_prompt(self, monkeypatch):
        # 원 질문을 넘기지 않는 호출은 지금 기준으로 돈다 — 빈 '원 질문:' 줄을 보내지 않는다
        _, system, user, llm_params = self._run(monkeypatch, question=None, critic_scope=1)
        assert (system, user, llm_params) == self._current()

    def test_scope_one_reply_goes_through_the_same_parser(self, monkeypatch):
        # 출력 형식이 같으니 무관 제외 규칙도 같다 — 보인 근거를 모두 무관이라 하면 충분이어도 부족으로 읽는다
        v, *_ = self._run(
            monkeypatch, question=self.QUESTION, critic_scope=1,
            reply='{"verdict": "sufficient", "note": "충분하다", "new_queries": ["보완"], "off_topic": [1]}',
        )
        assert (v.verdict, v.off_topic, v.new_queries) == ("insufficient", [1], ["보완"])
```

`app/tests/test_research_runner.py` — critic 대역 8곳(36·49·70·450·521·724·1024·1184행)은 같은 줄이다. 들여쓰기만 다르고 `async def __call__(self, subq, evidence, *, params):` 부분이 같으니 **Edit 의 replace_all** 로 한 번에 바꾼다.

교체 전(8곳):

```python
    async def __call__(self, subq, evidence, *, params):
```

교체 후(8곳):

```python
    async def __call__(self, subq, evidence, *, params, question=None):
```

`app/tests/test_research_runner.py` — 교체 전(403행):

```python
        async def _critic(subq, evidence, *, params):
```

교체 후:

```python
        async def _critic(subq, evidence, *, params, question=None):
```

확인(아래 `TestOriginalQuestion` 을 넣기 **전**, `app/` 에서): `grep -c "question=None" tests/test_research_runner.py` → `9`. `TestOriginalQuestion` 을 넣은 뒤에는 그 클래스의 `_critic` 하나가 더해져 `10` 이다.

`app/tests/test_research_runner.py` — 교체 전(412–415행, `TestReadTransaction` 끝과 `TestRequery` 머리):

```python
        assert commits_at_critic == [1]


class TestRequery:
```

교체 후:

```python
        assert commits_at_critic == [1]


class TestOriginalQuestion:
    """러너는 critic 에 원 질문(state.question)을 늘 넘긴다 — 쓸지는 critic 이 잡 파라미터 critic_scope 로 정한다."""

    QUESTION = "독서 격차 연구는 어디까지 왔나"

    def test_critic_receives_the_original_question(self):
        seen = []

        async def _critic(subq, evidence, *, params, question=None):
            seen.append(question)
            return Verdict("sufficient", note="충분")

        st = ResearchState(job_id="j", question=self.QUESTION, params=merge_params({"max_recheck": 0}))
        asyncio.run(explore_subquestion(st, SubQuestion(idx=0, text="가"), db=None,
                                        explore_fn=_fake_explore, critique_fn=_critic, emit=None))
        assert seen == [self.QUESTION]

    @pytest.mark.parametrize(("scope", "first_line"), [
        (0, "하위질문: 가"), (1, f"원 질문: {QUESTION}"),
    ], ids=["scope0", "scope1"])
    def test_job_param_picks_the_prompt(self, monkeypatch, scope, first_line):
        # 실제 critique 를 거친다 — 러너가 넘긴 원 질문은 critic_scope=1 잡의 프롬프트에만 실린다
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages[1]["content"])
            return '{"verdict": "sufficient", "note": "충분하다", "new_queries": [], "off_topic": []}'

        monkeypatch.setattr(critic_module, "chat", fake_chat)
        st = ResearchState(job_id="j", question=self.QUESTION,
                           params=merge_params({"max_recheck": 0, "critic_scope": scope}))
        asyncio.run(explore_subquestion(st, SubQuestion(idx=0, text="가"), db=None,
                                        explore_fn=_fake_explore, emit=None))
        assert seen[0].splitlines()[0] == first_line


class TestRequery:
```

`app/tests/test_research_api.py` — 교체 전(269–272행, `TestCreate` 끝):

```python
    def test_off_topic_exclusion_other_than_zero_or_one_is_422(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"exclude_off_topic": 2}})
        assert res.status_code == 422
```

교체 후:

```python
    def test_off_topic_exclusion_other_than_zero_or_one_is_422(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"exclude_off_topic": 2}})
        assert res.status_code == 422

    def test_operator_can_pick_the_critic_criterion_per_job(self, api):
        # 평가 도구(scripts/research_eval)가 같은 질문을 critic_scope 0·1 두 갈래 잡으로 만든다
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"critic_scope": 1}})
        assert res.status_code == 200
        (row,) = api.db.jobs.values()
        assert row["params"]["critic_scope"] == 1
        assert row["params"]["exclude_off_topic"] == 1

    def test_critic_scope_other_than_zero_or_one_is_422(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"critic_scope": 2}})
        assert res.status_code == 422
        assert "허용 범위" in res.json()["detail"]      # 모르는 키가 아니라 값 검사에서 거부
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_api.py -q -p no:cacheprovider`

Expected: `21 failed, 272 passed, 2 warnings` (네 파일 기준선 70 + 62 + 72 + 68 = 272 에 새 테스트 21개, 그중 `test_current_prompt_file_is_unchanged` 는 파일을 아직 안 바꿨으니 이미 통과하는 가드다). 실패 이유:
- `test_research_state.py` 9개 — `test_default_params_key_set_is_fixed` 는 `AssertionError`(집합에 `critic_scope` 가 없다), `test_critic_scope_is_the_current_criterion_by_default` 는 `KeyError: 'critic_scope'`, `test_critic_scope_takes_zero_or_one[0·1]` 은 `ValueError: 알 수 없는 파라미터: critic_scope`, `test_critic_scope_rejects_anything_else[2·-1·True·1·1.0]` 은 `AssertionError: Regex pattern did not match.`(나온 오류가 값 검사가 아니라 '알 수 없는 파라미터: critic_scope' 라서)
- `test_research_critic.py::TestCriticScope` 7개 — `test_scope_zero_sends_the_current_prompt_verbatim[job_params0]` 은 `TypeError: critique() got an unexpected keyword argument 'question'`, 나머지 6개는 `ValueError: 알 수 없는 파라미터: critic_scope`
- `test_research_runner.py::TestOriginalQuestion` 3개 — `test_critic_receives_the_original_question` 은 `assert [None] == ['독서 격차 연구는 어디까지 왔나']`, `test_job_param_picks_the_prompt[scope0·scope1]` 은 `ValueError: 알 수 없는 파라미터: critic_scope`
- `test_research_api.py` 2개 — `test_operator_can_pick_the_critic_criterion_per_job` 은 `assert 422 == 200`, `test_critic_scope_other_than_zero_or_one_is_422` 는 `assert '허용 범위' in '알 수 없는 파라미터: critic_scope'`

- [ ] **Step 3: `app/services/research/state.py` — 파라미터와 범위**

`app/services/research/state.py` — 교체 전(27–30행):

```python
    # 자기점검이 무관하다고 본 근거를 뺄지(1) 세기만 할지(0). 운영에서 결과가 줄면 재배포 없이 잡 파라미터로
    # 끄고, 끈 잡의 회차 기록 flagged 로 켠 잡과 나란히 비교한다
    "exclude_off_topic": 1,
})
```

교체 후:

```python
    # 자기점검이 무관하다고 본 근거를 뺄지(1) 세기만 할지(0). 운영에서 결과가 줄면 재배포 없이 잡 파라미터로
    # 끄고, 끈 잡의 회차 기록 flagged 로 켠 잡과 나란히 비교한다
    "exclude_off_topic": 1,
    # 자기점검이 무관(off_topic)을 가르는 기준. 0 = 하위질문의 핵심 개념(지금 기준 — 프롬프트·입력 글자 그대로),
    # 1 = 원 질문의 주제(하위질문에서 벗어났을 뿐 원 질문을 다루는 논문은 빼지 않는다, research_critique_question).
    # 충분·부족은 두 갈래 모두 하위질문 기준이다. 운영에서 고정 질문을 두 갈래로 돌려 합격하면 기본값을 1 로 바꾼다
    "critic_scope": 0,
})
```

`app/services/research/state.py` — 교체 전(44–45행):

```python
    "exclude_off_topic": (int, 0, 1),
}
```

교체 후:

```python
    "exclude_off_topic": (int, 0, 1),
    "critic_scope": (int, 0, 1),
}
```

- [ ] **Step 4: `app/domains/nl_library/prompts/research_critique_question.yaml` — 원 질문 기준 프롬프트(새 파일, 전체)**

```yaml
parser: plain
params:
  max_tokens: 600
  temperature: 0.2
system: |-
  당신은 연구 사서입니다. 하위질문 하나에 대해 모인 근거가 충분한지 판단합니다.

  판단 기준:
  - 각 근거에 붙은 본문 발췌를 보고, 제목만으로 짐작하지 말고 하위질문의 핵심 개념을 실제로 다루는지 판단하세요.
  - 하위질문의 핵심 개념을 다루지 않는 논문만 있으면 부족합니다.
  - 특정 시기에만 쏠려 있으면 부족합니다.
  - 근거가 {{ min_evidence }}편 미만이면 부족할 가능성이 높습니다.
  - 원 질문은 무관한 근거(off_topic)를 가를 때만 씁니다. 충분·부족은 위 기준대로 하위질문을 두고 판단하세요.

  편수는 필요조건이 아니라 신호 중 하나입니다. 편수가 부족해도 핵심 개념을
  정면으로 다루는 근거가 있으면 충분으로 판정하세요. 반대로 편수가 많아도
  발췌가 하위질문과 겉돌면 부족으로 판정하세요.

  부족하다고 판단하면 이미 시도한 검색어와 다른 검색어를 최대 2개 제안하세요.
  같은 말을 바꿔 쓴 것이 아니라 다른 용어·다른 각도여야 합니다.

  반드시 아래 JSON 형식으로만 응답하세요. 설명이나 다른 텍스트는 출력하지 마세요.
  {
    "verdict": "<sufficient 또는 insufficient>",
    "note": "<판단 근거 한 문장>",
    "new_queries": ["<제안 검색어>", "<제안 검색어>"],
    "off_topic": []
  }

  verdict 에는 sufficient 또는 insufficient 만 씁니다.
  new_queries 는 항상 배열입니다. 제안할 것이 없으면 빈 배열로 둡니다.
  off_topic 에는 발췌가 원 질문의 주제와 무관한 근거(같은 단어를 다른 뜻으로 쓴 논문 포함)의 번호를 정수로 씁니다. 하위질문에서 벗어났더라도 원 질문의 주제를 다루는 논문은 넣지 않습니다. 번호는 근거 목록 맨 앞 [ ] 안의 숫자입니다. 여기에 넣은 근거는 이 하위질문의 근거에서 빠집니다. 없으면 빈 배열로 둡니다.
  모든 근거를 off_topic 에 넣었다면 남는 근거가 없으니 verdict 는 insufficient 로 하고 new_queries 에 다른 검색어를 제안하세요.
  note 는 사용자에게 그대로 보여집니다(보고서의 한계 섹션에 실립니다). 한국어로 구체적으로, '~다'로 끝나는 문어체 평서문으로 쓰세요('~합니다'·'~입니다' 금지).
  사용자는 근거 목록을 보지 못합니다. note 에서 근거를 목록 번호로 가리키지 말고, 가리켜야 하면 논문 제목으로 쓰세요.
user: |-
  원 질문: {{ question }}
  하위질문: {{ subquestion }}
  이미 시도한 검색어: {{ tried_queries }}
  모인 근거: {{ evidence_count }}편

  {{ evidence_list }}
```

파일은 마지막 줄 `  {{ evidence_list }}` 뒤에 **줄바꿈 하나로 끝난다**(원본과 같다). Write 도구로 붙여 넣으면 마지막 줄바꿈이 빠지기 쉬운데, 빠지면 아래 diff 에 `\ No newline at end of file` 이 붙은 덩어리(`40c42`)가 하나 더 나온다 — 그때는 파일 끝에 줄바꿈 하나를 더한다.

원본과 두 군데(system 의 판단 기준 끝·off_topic 문장, user 첫 줄)만 다른지 확인한다(Git Bash):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app/domains/nl_library/prompts && diff <(tr -d '\r' < research_critique.yaml) <(tr -d '\r' < research_critique_question.yaml)`

Expected(정확히 이 세 덩어리 — 앞의 둘이 system, 마지막이 user):

```
12a13
>   - 원 질문은 무관한 근거(off_topic)를 가를 때만 씁니다. 충분·부족은 위 기준대로 하위질문을 두고 판단하세요.
31c32
<   off_topic 에는 발췌가 하위질문의 핵심 개념을 다루지 않는 근거(같은 단어를 다른 뜻으로 쓴 논문 포함)의 번호를 정수로 씁니다. 번호는 근거 목록 맨 앞 [ ] 안의 숫자입니다. 여기에 넣은 근거는 이 하위질문의 근거에서 빠집니다. 없으면 빈 배열로 둡니다.
---
>   off_topic 에는 발췌가 원 질문의 주제와 무관한 근거(같은 단어를 다른 뜻으로 쓴 논문 포함)의 번호를 정수로 씁니다. 하위질문에서 벗어났더라도 원 질문의 주제를 다루는 논문은 넣지 않습니다. 번호는 근거 목록 맨 앞 [ ] 안의 숫자입니다. 여기에 넣은 근거는 이 하위질문의 근거에서 빠집니다. 없으면 빈 배열로 둡니다.
35a37
>   원 질문: {{ question }}
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git diff --quiet app/domains/nl_library/prompts/research_critique.yaml && echo unchanged`

Expected: `unchanged`

- [ ] **Step 5: `app/services/research/critic.py` — 두 갈래 렌더**

`app/services/research/critic.py` — 교체 전(190–200행):

```python
async def critique(
    subq: SubQuestion, evidence: list[Evidence], *, params: dict,
) -> Verdict:
    system, user, llm_params = get_prompt("research_critique").render(
        subquestion=subq.text,
        evidence_count=len(evidence),
        evidence_list=format_evidence_list(evidence),
        min_evidence=params["min_evidence_per_subq"],
        tried_queries=", ".join(subq.queries) or "(없음)",
    )
    try:
```

교체 후:

```python
async def critique(
    subq: SubQuestion, evidence: list[Evidence], *, params: dict, question: str | None = None,
) -> Verdict:
    """하위질문 하나의 근거를 판정한다. question 은 원 질문이다(러너가 늘 넘긴다).

    잡 파라미터 critic_scope 가 1 이고 원 질문이 있으면 원 질문 기준 프롬프트(research_critique_question)로
    무관 근거를 원 질문의 주제로만 가른다 — 하위질문에서 벗어났을 뿐 원 질문을 다루는 논문까지 빼면 과잉
    제외가 된다. 그 밖에는 지금 프롬프트를 지금 다섯 변수로 렌더한다(원 질문을 넘기지 않는다). 0 갈래의
    프롬프트·입력은 글자 하나 바뀌지 않는다 — 운영에서 두 갈래를 나란히 비교하는 기준이다.
    """
    variables = {
        "subquestion": subq.text,
        "evidence_count": len(evidence),
        "evidence_list": format_evidence_list(evidence),
        "min_evidence": params["min_evidence_per_subq"],
        "tried_queries": ", ".join(subq.queries) or "(없음)",
    }
    if params.get("critic_scope", 0) == 1 and question:
        system, user, llm_params = get_prompt("research_critique_question").render(
            question=question, **variables,
        )
    else:
        system, user, llm_params = get_prompt("research_critique").render(**variables)
    try:
```

(`try:` 아래 `chat` 호출·`parse_verdict`·`_titled_note` 는 그대로다.)

- [ ] **Step 6: `app/services/research/runner.py` — 원 질문 넘기기**

`app/services/research/runner.py` — 교체 전(253–256행):

```python
        verdict = await critique_fn(
            subq, [_as_seen_by(state.evidence[e], subq) for e in subq.evidence_ids],
            params=params,
        )
```

교체 후:

```python
        # 원 질문은 늘 넘긴다 — 쓸지는 critic 이 잡 파라미터 critic_scope 로 정한다
        verdict = await critique_fn(
            subq, [_as_seen_by(state.evidence[e], subq) for e in subq.evidence_ids],
            params=params, question=state.question,
        )
```

- [ ] **Step 7: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_api.py -q -p no:cacheprovider`

Expected: `293 passed, 2 warnings` (파일별로 `test_research_state.py` 78 · `test_research_critic.py` 70 · `test_research_runner.py` 75 · `test_research_api.py` 70)

- [ ] **Step 8: 관련 스위트·전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_prompts.py tests/test_research_tasks.py tests/test_research_synthesizer.py -q -p no:cacheprovider`

Expected: `213 passed, 2 warnings` (8 + 94 + 111, 이 task 전과 같다 — 워커·종합·프롬프트 로더는 바뀌지 않았다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 이 task 앞(Task 1 뒤) 전체 수치 + 21 passed, `1 skipped`, `3 errors`(로컬에 FlagEmbedding·openpyxl 이 없어 수집 단계에서 실패하는 기존 파일 셋 `test_book_chat.py`·`test_build_manifest.py`·`test_loaders.py`). 검증 사본(Task 1 없이 기준선 1369 에서)에서는 `1390 passed, 1 skipped, 2 warnings, 3 errors` 였다.

- [ ] **Step 9: 커밋**

작업 트리에 다른 작업 것이 있을 수 있다. `git add -A` 를 쓰지 말고 아래 파일만 올린다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/services/research/state.py app/domains/nl_library/prompts/research_critique_question.yaml app/services/research/critic.py app/services/research/runner.py app/tests/test_research_state.py app/tests/test_research_critic.py app/tests/test_research_runner.py app/tests/test_research_api.py && git status --short && git commit -m "[Feat] round06a — critic 기준 스위치: 잡 파라미터 critic_scope(int 0~1, 기본 0)를 더한다. 0 은 지금 프롬프트(research_critique.yaml — 한 글자도 바꾸지 않고 테스트가 sha256 으로 지킨다)를 지금 다섯 변수로 그대로 보내고, 1 은 원 질문을 함께 넘기는 research_critique_question.yaml 로 무관(off_topic) 판정만 원 질문의 주제로 좁힌다(하위질문에서 벗어났을 뿐 원 질문을 다루는 논문은 빼지 않는다 — 판단 기준 끝에 원 질문은 무관 판정에만 쓰고 충분·부족은 하위질문을 두고 가른다는 한 줄을 붙이고, 충분·부족 기준·출력 형식·파서는 그대로). 러너는 critic 에 원 질문(state.question)을 늘 넘긴다. 운영에서 고정 질문을 두 갈래로 돌려 합격하면 기본값을 1 로 바꾼다(spec D11·§5-1)"
```

---


### Task 3: 근거 장부 데이터 `adopted_papers`

**왜:** spec §5-1. `state_snapshot` 은 탐색이 끝날 때(stage=explored) 한 번만 저장되고, `search` 이벤트는 그 회차의 critic 보다 먼저 나가 채택·제외를 모른다. 제외 서지는 이미 회차 끝 `critique` 이벤트와 search 단계 `result.rounds[].excluded_papers` 에 실린다. 빠진 **채택** 목록을 같은 두 곳에 `adopted_papers` 로 더한다 — 그 회차 끝 하위질문의 `evidence_ids` 순서 `[{cnts_id, rank}]` 이고, 그 회차에 새로 채택된 논문은 `_paper_brief`(cnts_id·title·personal_author·pub_date)와 `new: True` 를 함께 싣는다. 그러면 탐색 중 재접속 때도 `steps[].result.rounds` 만으로 근거 장부(06b 화면)를 다시 그린다. 읽기 목록의 "처음 채택된 회차"(§5-4 들어온 경로)도 이 값에서 온다.

**Files:**
- Modify: `app/services/research/runner.py` (`_paper_brief` 85–89행 뒤에 `_adopted_papers` 추가, 회차 기록·`critique` 이벤트 283–297행 — Task 2 뒤 기준)
- Modify: `app/services/research/state.py` (`SubQuestion.rounds` 주석 151–157행 — Task 2 뒤 기준)
- Modify: `app/models/research.py` (`ResearchStep.result` search shape 주석 103–109행)
- Test: `app/tests/test_research_runner.py` (`TestRoundHistory` 356–393행, `TestOffTopicExclusionOff` 끝 1095–1097행 뒤에 `TestAdoptedPapers` 추가 — Task 2 뒤 기준)

**알아 둘 것:**
- 키 이름은 `adopted_papers` 다. `critique` 이벤트에 이미 있는 정수 `adopted`(채택 수 — 프론트 `utils/researchEvents.ts` 가 읽는다)와 다르다. `adopted` 는 그대로 둔다.
- `fresh` 는 러너 회차 안의 지역 변수(`fresh = [e for e in linked if e not in before]` — 이 회차에 이 하위질문에 새로 링크된 근거, 다른 하위질문 근거의 재사용 포함)다. 목록은 제외를 반영한 **뒤의** `subq.evidence_ids` 로 만드므로, 이 회차에 들어왔다가 같은 회차에 무관으로 빠진 논문은 나오지 않는다(그 논문은 `excluded_papers` 에 있다).
- 다른 하위질문이 먼저 채택해 재사용한 근거도 이 하위질문의 그 회차에는 `new: True` 와 서지를 싣는다 — 장부는 search 단계(하위질문)마다 그리므로 그 단계의 rounds 만으로 서지를 알아야 한다.
- 회차 기록과 이벤트는 **같은 리스트 객체**를 싣는다(`excluded_papers` 와 같은 방식) — 라이브로 본 장부와 재접속 때 rounds 로 다시 그린 장부가 같아야 한다(`test_history_matches_what_was_streamed`).
- 워커(`workers/research_tasks.py`)는 고치지 않는다. `_round_emitter` 가 `critique` 이벤트마다 `_search_progress(state, subq)` = `{"rounds": list(subq.rounds), "counters": …}` 를 search 단계 `result` 에 덮어쓰므로 새 키가 저절로 실린다. `snapshot_state` 도 `asdict` 라 저절로 실리고, `restore_state` 는 rounds 를 dict 그대로 되살린다.
- 06a 전 잡의 회차에는 키가 없다 — 소비처(06b 장부, Task 13 프론트)는 없으면 빈 목록으로 읽는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_research_runner.py` — 교체 전(356–375행, Task 2 뒤 기준):

```python
class TestRoundHistory:
    """이벤트로 흘린 장면은 subq.rounds 에도 남는다 — 워커가 그걸 search 단계 result 에 쓴다."""

    def _explore(self):
        return _explore_table({"가": ["A", "B"], "다른 검색어 1": ["B", "C", "D"]})

    def test_every_round_is_recorded_on_the_subquestion(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 1}))
        sq = SubQuestion(idx=0, text="가")
        st.subquestions = [sq]
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=self._explore(),
                                        critique_fn=_FakeCritic(), emit=None))
        assert sq.rounds == [
            {"round": 1, "query": "가", "found_chunks": 2, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1",
             "excluded": 0, "excluded_papers": [], "flagged": 0, "flagged_papers": []},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None, "excluded": 0,
             "excluded_papers": [], "flagged": 0, "flagged_papers": []},
        ]
```

교체 후:

```python
def _new_adopted(cnts_id, rank):
    """그 회차에 새로 채택된 논문의 adopted_papers 항목 — _hits 의 서지(저자 없음)에 순위·new 를 붙인다."""
    return {"cnts_id": cnts_id, "title": f"논문 {cnts_id}", "personal_author": None,
            "pub_date": "2008-06", "rank": rank, "new": True}


class TestRoundHistory:
    """이벤트로 흘린 장면은 subq.rounds 에도 남는다 — 워커가 그걸 search 단계 result 에 쓴다."""

    def _explore(self):
        return _explore_table({"가": ["A", "B"], "다른 검색어 1": ["B", "C", "D"]})

    def test_every_round_is_recorded_on_the_subquestion(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 1}))
        sq = SubQuestion(idx=0, text="가")
        st.subquestions = [sq]
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=self._explore(),
                                        critique_fn=_FakeCritic(), emit=None))
        assert sq.rounds == [
            {"round": 1, "query": "가", "found_chunks": 2, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1",
             "excluded": 0, "excluded_papers": [], "flagged": 0, "flagged_papers": [],
             "adopted_papers": [_new_adopted("A", 1), _new_adopted("B", 2)]},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None, "excluded": 0,
             "excluded_papers": [], "flagged": 0, "flagged_papers": [],
             # 2회차가 새로 보탠 C·D 중 1위 C 가 앞자리를 받는다(_rank_order). 앞 회차 것은 id·순위만
             "adopted_papers": [{"cnts_id": "A", "rank": 1}, _new_adopted("C", 2),
                                {"cnts_id": "B", "rank": 3}, _new_adopted("D", 4)]},
        ]
```

`app/tests/test_research_runner.py` — 교체 전(`test_history_matches_what_was_streamed` 안, 389–393행):

```python
             "excluded_papers": c["excluded_papers"], "flagged": c["flagged"],
             "flagged_papers": c["flagged_papers"]}
            for s, c in zip(_of(events, "search"), _of(events, "critique"))
        ]
        assert sq.rounds == streamed
```

교체 후:

```python
             "excluded_papers": c["excluded_papers"], "flagged": c["flagged"],
             "flagged_papers": c["flagged_papers"], "adopted_papers": c["adopted_papers"]}
            for s, c in zip(_of(events, "search"), _of(events, "critique"))
        ]
        assert sq.rounds == streamed
```

`app/tests/test_research_runner.py` — 교체 전(`TestOffTopicExclusionOff` 끝과 `_RELAY`, Task 2 뒤 1095–1100행):

```python
        assert sq.queries == ["엣지 컴퓨팅 자원"]
        assert (sq.verdict, sq.note) == ("sufficient", "충분하다")
        assert len(sq.evidence_ids) == 2 and sq.rounds[0]["flagged"] == 2


_RELAY = "services.research.relay"
```

교체 후:

```python
        assert sq.queries == ["엣지 컴퓨팅 자원"]
        assert (sq.verdict, sq.note) == ("sufficient", "충분하다")
        assert len(sq.evidence_ids) == 2 and sq.rounds[0]["flagged"] == 2


class TestAdoptedPapers:
    """회차 끝 채택 목록(adopted_papers) — 회차 기록과 critique 이벤트에 같은 값을 싣는다. state_snapshot 은
    탐색이 끝날 때 한 번만 저장되므로, 도는 잡의 근거 장부는 search 단계 result.rounds 만으로 다시 그린다."""

    def _state(self, *texts, **params):
        st = ResearchState(job_id="j", question="q", params=merge_params(params))
        st.subquestions = [SubQuestion(idx=i, text=t) for i, t in enumerate(texts)]
        return st

    def _run(self, st, sq, table, critic, emit=None):
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_explore_table(table),
                                        critique_fn=critic, emit=emit))

    def test_round_end_lists_the_subquestion_evidence_after_exclusion(self):
        # 무관하다고 뺀 B 는 들지 않는다 — 판정 전이 아니라 회차 끝(제외 반영 뒤)의 evidence_ids 순서다
        st = self._state("가", max_recheck=0)
        (sq,) = st.subquestions
        self._run(st, sq, {"가": ["A", "B", "C"]}, _ScriptedCritic(("sufficient", [2], [])))
        assert sq.rounds[0]["adopted_papers"] == [_new_adopted("A", 1), _new_adopted("C", 2)]

    def test_only_papers_new_in_the_round_carry_their_bibliography(self):
        # 앞 회차에 서지를 실은 논문은 id·순위만 싣는다 — 회차가 쌓여도 기록이 불어나지 않는다
        st = self._state("가", max_recheck=1)
        (sq,) = st.subquestions
        critic = _ScriptedCritic(("insufficient", [2], ["보완"]), ("sufficient", [], []))
        self._run(st, sq, {"가": ["A", "B", "C"], "보완": ["D"]}, critic)
        # 2회차 1위 D 는 앞자리를 받는다(_rank_order) — 순위는 회차 끝 순서 그대로다
        assert sq.rounds[1]["adopted_papers"] == [
            {"cnts_id": "A", "rank": 1}, _new_adopted("D", 2), {"cnts_id": "C", "rank": 3}]

    def test_critique_event_carries_the_same_list_as_the_round(self):
        events, emit = _recorder()
        st = self._state("가", max_recheck=1)
        (sq,) = st.subquestions
        critic = _ScriptedCritic(("insufficient", [2], ["보완"]), ("sufficient", [], []))
        self._run(st, sq, {"가": ["A", "B", "C"], "보완": ["D"]}, critic, emit=emit)
        assert [c["adopted_papers"] for c in _of(events, "critique")] == [
            r["adopted_papers"] for r in sq.rounds]
        # 정수 adopted(채택 수)는 그대로다 — 이름이 다른 키다
        assert [c["adopted"] for c in _of(events, "critique")] == [2, 3]

    def test_paper_another_subquestion_adopted_first_is_new_here(self):
        """근거 장부는 하위질문(search 단계)마다 그린다 — 다른 하위질문이 먼저 채택한 근거를 재사용해도 이
        하위질문의 회차 기록만으로 서지를 알 수 있어야 한다."""
        st = self._state("가", "나", max_recheck=0)
        sq1, sq2 = st.subquestions
        table = {"가": ["A"], "나": ["A", "B"]}
        self._run(st, sq1, table, _ScriptedCritic(("sufficient", [], [])))
        self._run(st, sq2, table, _ScriptedCritic(("sufficient", [], [])))
        assert sq2.rounds[0]["adopted_papers"] == [_new_adopted("A", 1), _new_adopted("B", 2)]

    def test_flagged_paper_stays_listed_when_exclusion_is_off(self):
        # 끈 잡은 빼지 않는다 — 장부에도 남는다(무관 표시는 flagged_papers 가 따로 싣는다)
        st = self._state("가", max_recheck=0, exclude_off_topic=0)
        (sq,) = st.subquestions
        self._run(st, sq, {"가": ["A", "B", "C"]}, _ScriptedCritic(("sufficient", [2], [])))
        assert [p["cnts_id"] for p in sq.rounds[0]["adopted_papers"]] == ["A", "B", "C"]
        assert [p["cnts_id"] for p in sq.rounds[0]["flagged_papers"]] == ["B"]

    def test_round_without_evidence_lists_nothing(self):
        # 키는 늘 있다 — 키가 없는 회차는 06a 전 워커가 남긴 것이다
        st = self._state("가", max_recheck=0)
        (sq,) = st.subquestions
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_empty_explore,
                                        critique_fn=_ScriptedCritic(("sufficient", [], [])), emit=None))
        assert sq.rounds[0]["adopted_papers"] == []


_RELAY = "services.research.relay"
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_runner.py -q -p no:cacheprovider`

Expected: `8 failed, 73 passed, 2 warnings` (Task 2 뒤 75 + 새 테스트 6). 실패 이유:
- `TestRoundHistory::test_every_round_is_recorded_on_the_subquestion` — `AssertionError`(회차 dict 에 `adopted_papers` 가 없다)
- `TestRoundHistory::test_history_matches_what_was_streamed` — `KeyError: 'adopted_papers'`(critique 이벤트에 없다)
- `TestAdoptedPapers` 6개 전부 — `KeyError: 'adopted_papers'`

- [ ] **Step 3: `app/services/research/runner.py` — `_adopted_papers` 와 두 곳에 싣기**

`app/services/research/runner.py` — 교체 전(85–89행):

```python
def _paper_brief(ev: Evidence) -> dict:
    """뺀 논문의 서지 요약 — 회차 기록(excluded_papers)에 남는다. 풀에서 지운 뒤에는 이것 말고 무엇을
    뺐는지 알 길이 없다."""
    return {"cnts_id": ev.cnts_id, "title": ev.meta.get("title"),
            "personal_author": ev.meta.get("personal_author"), "pub_date": ev.meta.get("pub_date")}
```

교체 후:

```python
def _paper_brief(ev: Evidence) -> dict:
    """뺀 논문의 서지 요약 — 회차 기록(excluded_papers)에 남는다. 풀에서 지운 뒤에는 이것 말고 무엇을
    뺐는지 알 길이 없다."""
    return {"cnts_id": ev.cnts_id, "title": ev.meta.get("title"),
            "personal_author": ev.meta.get("personal_author"), "pub_date": ev.meta.get("pub_date")}


def _adopted_papers(state: ResearchState, subq: SubQuestion, fresh: list[str]) -> list[dict]:
    """회차 끝 이 하위질문의 채택 근거(순위순). 이 회차에 새로 채택된 것은 서지를 함께 싣는다
    — 도는 잡의 장부를 rounds 만으로 다시 그리기 위해서다(state_snapshot 은 탐색 끝에 한 번만 저장된다)."""
    out = []
    for rank, eid in enumerate(subq.evidence_ids, start=1):
        ev = state.evidence[eid]
        item = {"cnts_id": ev.cnts_id, "rank": rank}
        if eid in fresh:
            item = {**_paper_brief(ev), "rank": rank, "new": True}
        out.append(item)
    return out
```

`app/services/research/runner.py` — 교체 전(Task 2 뒤 283–297행):

```python
        next_query = _recheck_query(state, subq, verdict, recheck=recheck, own=own)
        subq.rounds.append({
            "round": round_no, "query": query, "found_chunks": len(hits),
            "new_papers": new_papers, "verdict": verdict.verdict,
            "note": verdict.note, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers, "flagged": flagged, "flagged_papers": flagged_papers,
        })
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
            "round": round_no, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers, "flagged": flagged, "flagged_papers": flagged_papers,
            "will_recheck": next_query is not None,
        })
```

교체 후:

```python
        next_query = _recheck_query(state, subq, verdict, recheck=recheck, own=own)
        # 회차 기록과 이벤트에 같은 값을 싣는다 — 라이브로 본 장부와 재접속 때 rounds 로 다시 그린 장부가 같아야 한다
        adopted_papers = _adopted_papers(state, subq, fresh)
        subq.rounds.append({
            "round": round_no, "query": query, "found_chunks": len(hits),
            "new_papers": new_papers, "verdict": verdict.verdict,
            "note": verdict.note, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers, "flagged": flagged, "flagged_papers": flagged_papers,
            "adopted_papers": adopted_papers,
        })
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
            "round": round_no, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers, "flagged": flagged, "flagged_papers": flagged_papers,
            "adopted_papers": adopted_papers,
            "will_recheck": next_query is not None,
        })
```

- [ ] **Step 4: 주석 — `state.py` 의 `SubQuestion.rounds`, `models/research.py` 의 search result shape**

`app/services/research/state.py` — 교체 전(Task 2 뒤 151–157행):

```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query, excluded,
    # excluded_papers, flagged, flagged_papers}]. verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을
    # 다시 열었을 때 "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다. excluded(그 회차에 무관하다고 뺀 수)·
    # excluded_papers(뺀 논문의 서지 요약 — 풀에서 지운 뒤에도 무엇을 뺐는지 남는다)·flagged·flagged_papers(무관
    # 제외를 끈 잡에서 이 하위질문이 그 회차에 처음 무관하다고 본 수와 서지, 켠 잡은 0·빈 목록)는 보강 전 잡의
    # 회차에는 없다.
    rounds: list[dict] = field(default_factory=list)
```

교체 후:

```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query, excluded,
    # excluded_papers, flagged, flagged_papers, adopted_papers}]. verdict·note 는 마지막 회차 값만 남으므로, 이게
    # 없으면 끝난 잡을 다시 열었을 때 "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다. excluded(그 회차에 무관하다고 뺀 수)·
    # excluded_papers(뺀 논문의 서지 요약 — 풀에서 지운 뒤에도 무엇을 뺐는지 남는다)·flagged·flagged_papers(무관
    # 제외를 끈 잡에서 이 하위질문이 그 회차에 처음 무관하다고 본 수와 서지, 켠 잡은 0·빈 목록)는 보강 전 잡의
    # 회차에는 없다. adopted_papers(회차 끝 이 하위질문의 채택 근거 [{cnts_id, rank}] 순위순, 그 회차에 새로
    # 채택된 것은 서지 요약과 new: True 를 함께 — 도는 잡의 근거 장부를 rounds 만으로 다시 그린다)는 06a 전 잡의
    # 회차에는 없다.
    rounds: list[dict] = field(default_factory=list)
```

`app/models/research.py` — 교체 전(103–109행):

```python
    #              "rounds": [{"round", "query", "found_chunks", "new_papers",
    #                          "verdict", "note", "next_query", "excluded"?, "excluded_papers"?,
    #                          "flagged"?, "flagged_papers"?}],
    #             excluded 는 그 회차 자기점검이 무관하다고 뺀 근거 수, excluded_papers 는 뺀 논문의
    #             서지 요약 [{"cnts_id", "title", "personal_author", "pub_date"}], flagged·flagged_papers 는
    #             무관 제외를 끈 잡(params.exclude_off_topic=0)에서 그 하위질문이 처음 무관하다고 본 수와
    #             서지(켠 잡은 0·빈 목록). 보강 전 잡의 회차에는 없다.
```

교체 후:

```python
    #              "rounds": [{"round", "query", "found_chunks", "new_papers",
    #                          "verdict", "note", "next_query", "excluded"?, "excluded_papers"?,
    #                          "flagged"?, "flagged_papers"?, "adopted_papers"?}],
    #             excluded 는 그 회차 자기점검이 무관하다고 뺀 근거 수, excluded_papers 는 뺀 논문의
    #             서지 요약 [{"cnts_id", "title", "personal_author", "pub_date"}], flagged·flagged_papers 는
    #             무관 제외를 끈 잡(params.exclude_off_topic=0)에서 그 하위질문이 처음 무관하다고 본 수와
    #             서지(켠 잡은 0·빈 목록). 보강 전 잡의 회차에는 없다.
    #             adopted_papers 는 회차 끝 그 하위질문의 채택 근거 [{"cnts_id", "rank"}](순위순, 제외 반영 뒤)이고,
    #             그 회차에 새로 채택된 것은 서지 요약에 "new": true 를 더해 싣는다 — 도는 잡의 근거 장부를
    #             rounds 만으로 다시 그린다(critique 이벤트가 같은 값을 싣는다). 06a 전 잡의 회차에는 없다.
```

- [ ] **Step 5: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_runner.py -q -p no:cacheprovider`

Expected: `81 passed, 2 warnings`

- [ ] **Step 6: 관련 스위트·전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_tasks.py tests/test_research_synthesizer.py tests/test_research_api.py tests/test_prompts.py -q -p no:cacheprovider`

Expected: `431 passed, 2 warnings` (78 + 70 + 94 + 111 + 70 + 8 — Task 2 뒤와 같다. 워커는 rounds 를 그대로 저장하고, 종합은 `excluded_papers`·`flagged` 만 읽는다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: Task 2 뒤 전체 수치 + 6 passed, `1 skipped`, `3 errors`(위와 같은 기존 수집 오류 셋). 검증 사본(Task 1 없이)에서는 `1396 passed, 1 skipped, 2 warnings, 3 errors` 였다.

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/services/research/runner.py app/services/research/state.py app/models/research.py app/tests/test_research_runner.py && git status --short && git commit -m "[Feat] round06a — 근거 장부 데이터: 회차 끝 하위질문의 채택 근거를 adopted_papers([{cnts_id, rank}] 순위순, 그 회차에 새로 채택된 것은 서지 요약과 new 를 함께)로 subq.rounds[] 와 critique 이벤트에 같은 값으로 싣는다. state_snapshot 은 탐색 끝에 한 번만 저장되므로 도는 잡의 장부를 search 단계 result.rounds 만으로 다시 그리기 위해서다(spec §5-1). 정수 adopted(채택 수)는 그대로 두고, 워커는 rounds 를 그대로 저장하므로 고치지 않는다"
```


### Task 4: 논문 상세 인용의 학술지 자리 — `build_citation`

**왜:** spec §5-1 서지 버그. 논문 상세 CitationModal 의 인용(`GET /api/papers/{cnts_id}/citation`)이 학술지 자리에 `publisher` 를 쓴다. KCI 논문의 `publisher` 는 학회 이름(예: 한국교육학회)이고 학술지 이름은 `series_title`(예: 교육학연구)이다. 보고서 내보내기 참고문헌(`frontend/utils/reportDocument.ts` 의 `referenceText`)은 이미 `series_title` 을 쓰므로 두 화면의 인용이 어긋났다.

**Files:**
- Modify: `app/services/search/paper_citation.py` (`build_citation` 의 `journal` 한 줄, 57행)
- Create: `frontend/tests/fixtures/citation_reference.json` (두 쪽 테스트가 함께 읽는 서지와 기대 글자)
- Modify: `frontend/tests/unit/reportDocument.test.ts` (import 끝 23행, `describe("buildReportDocument — 참고문헌")` 끝 343-346행)
- Test: `app/tests/test_paper_citation.py` (새 파일 — 이 모듈의 첫 테스트)

**알아 둘 것:**
- 바꾸는 것은 학술지 자리 한 줄뿐이다. `series_title` 이 없으면(빈칸 포함) 학술지 자리를 비우고 `publisher` 로 물러나지 않는다. 저자 규칙(국문은 전원, 영문은 4인 이상 `et al.`)·연도 없음(`n.d.`)·말미 식별자(UCI, 없으면 URL)·영문 인용은 그대로다.
- 지금 코드는 학술지가 비면 권호도 함께 빠진다(`if journal:` 안에서 권호를 붙인다). 이 동작은 바꾸지 않는다 — 그래서 `series_title` 이 없는 논문은 백엔드 인용에 권호가 없고, 보고서 참고문헌(`referenceText`)은 권호만 남긴다(`… AI 윤리 교육. 57(3).`, 사본에서 vitest 로 확인). 계획서 참고문헌 함수는 06b 에서 정한다(spec §11).
- **두 쪽을 한 파일에 묶는다:** spec §5-1 의 대조(국문 인용의 "저자 (연도). 제목. 학술지, 권호." 부분 = `referenceText`)는 공유 파일 `frontend/tests/fixtures/citation_reference.json` 하나로 한다. 이 파일에 서지 둘(저자 3인 = 계약 고정 예제, 저자 2인)과 각 서지의 기대 글자(`reference`)를 두고, 백엔드 테스트는 `build_citation` 의 국문이 `reference + " UCI …"` 인지, 프론트 테스트는 `referenceText`(대목이 없어 `인용 쪽` 이 붙지 않는다)가 `reference` 와 같은지 본다. 한쪽 출력을 바꾸고 자기 테스트의 기대값만 고치는 일이 생기지 않는다 — 기대값을 고치려면 이 파일을 고쳐야 하고, 그러면 다른 쪽 테스트가 깨진다. 백엔드 테스트는 공유 파일의 서지가 고정 예제에서 저자만 다른지도 확인한다(공유 파일을 바꿔 대조를 약하게 만들지 못하게). 사본에서 저자 3인 `reference` 의 쉼표 하나를 지워 보면 백엔드 `[3-authors]` 1개와 프론트 새 테스트 1개가 함께 실패한다(실측).
- 백엔드 테스트가 `app/` 밖의 파일을 읽는 것은 이미 있는 방식이다(`test_celery_schedule.py` 의 `docker-compose.yml`, `test_build_canary_manifest.py` 의 `scripts/`). 프론트는 JSON 을 import 한다 — `nuxi typecheck` 가 `tests/` 도 보므로(`.nuxt/tsconfig.app.json` include `../**/*`, `resolveJsonModule: true`) Step 4 에서 typecheck 를 함께 돌린다.
- `reportDocument.test.ts` 는 CRLF 다 — Edit 도구로 고친다. 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다(`core.autocrlf=true`).
- 호출부는 `app/api/paper.py` 의 `get_paper_citation` 하나다(함수 안 import) — 고치지 않는다.
- 이 작업 뒤 프론트 vitest 는 28 파일·496 개다(기준선 495 + 1). `reportDocument.test.ts` 의 기존 줄은 이 작업이 더한 줄 수(import 1줄 + 테스트 11줄)만큼 아래로 밀린다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/fixtures/citation_reference.json` (새 파일, 전체):

```json
{
  "about": "같은 서지로 두 화면의 인용 글자를 맞춘다. 논문 상세 인용(app/services/search/paper_citation.py build_citation)의 국문 앞부분과 보고서 내보내기 참고문헌(frontend/utils/reportDocument.ts referenceText)이 reference 와 같아야 한다. app/tests/test_paper_citation.py 와 frontend/tests/unit/reportDocument.test.ts 가 함께 읽는다 — 한쪽 글자를 바꾸려면 이 파일을 고쳐야 하고, 그러면 다른 쪽 테스트가 깨진다.",
  "cases": [
    {
      "name": "3-authors",
      "meta": {
        "personal_author": "김철수; 이영희; 박민수",
        "pub_date": "2019-03",
        "title": "AI 윤리 교육",
        "series_title": "교육학연구",
        "vol_issue": "57(3)",
        "publisher": "한국교육학회",
        "uci": "G704-000001.2019.57.3.001"
      },
      "reference": "김철수, 이영희, 박민수 (2019). AI 윤리 교육. 교육학연구, 57(3)."
    },
    {
      "name": "2-authors",
      "meta": {
        "personal_author": "김철수; 이영희",
        "pub_date": "2019-03",
        "title": "AI 윤리 교육",
        "series_title": "교육학연구",
        "vol_issue": "57(3)",
        "publisher": "한국교육학회",
        "uci": "G704-000001.2019.57.3.001"
      },
      "reference": "김철수, 이영희 (2019). AI 윤리 교육. 교육학연구, 57(3)."
    }
  ]
}
```

`app/tests/test_paper_citation.py` (새 파일, 전체):

```python
"""services/search/paper_citation.py — 논문 상세 인용(CitationModal)의 학술지 자리.

학술지 이름은 series_title 이다(KCI 논문의 publisher 는 학회 이름). series_title 이 없으면 학술지
자리를 비우고 publisher 로 물러나지 않는다. 국문 인용의 "저자 (연도). 제목. 학술지, 권호." 부분은
보고서 내보내기 참고문헌(frontend/utils/reportDocument.ts 의 referenceText)과 같은 글자여야 한다 —
그 글자는 프론트 테스트(frontend/tests/unit/reportDocument.test.ts)와 함께 읽는 공유 파일
frontend/tests/fixtures/citation_reference.json 에 있다.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from schemas.book import BookOut
from services.search.paper_citation import build_citation

UCI = "G704-000001.2019.57.3.001"
# spec §5-1 의 고정 예제(저자 3인·series_title·vol_issue·UCI). publisher 는 학회 이름이다
EXAMPLE = dict(
    personal_author="김철수; 이영희; 박민수",
    pub_date="2019-03",
    title="AI 윤리 교육",
    series_title="교육학연구",
    vol_issue="57(3)",
    publisher="한국교육학회",
    uci=UCI,
)
SHARED_FIXTURE = (
    Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "citation_reference.json"
)
SHARED_CASES = {c["name"]: c for c in json.loads(SHARED_FIXTURE.read_text(encoding="utf-8"))["cases"]}


def _paper(**over) -> BookOut:
    fields = dict(
        id=uuid.UUID("0b5f3a3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b"),
        cnts_id="KCI_TEST_0001",
        created_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        **EXAMPLE,
    )
    fields.update(over)
    return BookOut(**fields)


def test_journal_is_series_title_not_publisher():
    citation = build_citation(_paper())

    assert citation["korean"] == f"김철수, 이영희, 박민수 (2019). AI 윤리 교육. 교육학연구, 57(3). UCI {UCI}"
    assert citation["english"] == f"김철수, 이영희, 박민수 (2019). AI 윤리 교육. 교육학연구, 57(3). UCI {UCI}"


@pytest.mark.parametrize("name, authors", [
    ("3-authors", "김철수; 이영희; 박민수"),     # 고정 예제 그대로
    ("2-authors", "김철수; 이영희"),
], ids=["3-authors", "2-authors"])
def test_korean_prefix_matches_report_reference(name, authors):
    # 프론트 테스트가 같은 파일의 같은 서지로 referenceText 의 글자를 고정한다. 공유 파일의 서지가
    # 고정 예제에서 저자만 다른지 먼저 본다 — 서지를 바꿔 이 대조를 약하게 만들지 못하게
    case = SHARED_CASES[name]
    assert case["meta"] == {**EXAMPLE, "personal_author": authors}

    korean = build_citation(_paper(**case["meta"]))["korean"]

    assert korean == f"{case['reference']} UCI {UCI}"


def test_missing_series_title_leaves_journal_empty():
    citation = build_citation(_paper(series_title=None))

    assert citation["korean"] == f"김철수, 이영희, 박민수 (2019). AI 윤리 교육. UCI {UCI}"
    assert "한국교육학회" not in citation["korean"]
    assert "한국교육학회" not in citation["english"]


def test_blank_series_title_is_treated_as_missing():
    citation = build_citation(_paper(series_title="  "))

    assert citation["korean"] == f"김철수, 이영희, 박민수 (2019). AI 윤리 교육. UCI {UCI}"


def test_other_parts_are_unchanged():
    # 저자 규칙(영문 4인 이상 et al.)·연도 없음(n.d.)·UCI 없을 때 URL 은 그대로다
    citation = build_citation(_paper(
        personal_author="Kim; Lee; Park; Choi", pub_date=None, uci=None,
        url="https://www.kci.go.kr/x",
    ))

    assert citation["korean"] == (
        "Kim, Lee, Park, Choi (n.d.). AI 윤리 교육. 교육학연구, 57(3). https://www.kci.go.kr/x"
    )
    assert citation["english"] == (
        "Kim et al. (n.d.). AI 윤리 교육. 교육학연구, 57(3). https://www.kci.go.kr/x"
    )
```

`frontend/tests/unit/reportDocument.test.ts` 를 두 군데 고친다.

① import 끝 — 교체 전:

```ts
import { reportIntro } from "~/utils/researchReport";
```

교체 후:

```ts
import { reportIntro } from "~/utils/researchReport";
import citationReference from "../fixtures/citation_reference.json";
```

② `describe("buildReportDocument — 참고문헌")` 끝 — 교체 전:

```ts
    // z(31쪽)는 어느 절도 인용하지 않았고, 0 은 첫 쪽과 쪽 정보 없음이 겹쳐 뺀다
    expect(doc.references.map((r) => r.text)).toEqual(["가. 인용 쪽: 12–13, 20", "나."]);
  });
});
```

교체 후:

```ts
    // z(31쪽)는 어느 절도 인용하지 않았고, 0 은 첫 쪽과 쪽 정보 없음이 겹쳐 뺀다
    expect(doc.references.map((r) => r.text)).toEqual(["가. 인용 쪽: 12–13, 20", "나."]);
  });

  it("논문 상세 인용(build_citation)과 같은 서지는 같은 글자로 쓴다 — 백엔드 test_paper_citation.py 가 같은 파일을 읽는다", () => {
    const evidence: Record<string, ReportEvidence> = {};
    citationReference.cases.forEach((c, i) => {
      evidence[`E${i + 1}`] = ev(`C${i + 1}`, c.meta);
    });
    const intro = citationReference.cases.map((_, i) => `[E${i + 1}]`).join("");
    const doc = buildReportDocument(input({ sections: [section({ intro })], evidence }), NOW);
    // 대목이 없어 인용 쪽이 붙지 않는다 — 백엔드 국문 인용의 "저자 (연도). 제목. 학술지, 권호." 와 같은 범위다
    expect(doc.references.map((r) => r.text)).toEqual(citationReference.cases.map((c) => c.reference));
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_paper_citation.py -q -p no:cacheprovider`

Expected: `6 failed, 1 warning`(경고는 기존 `schemas/book.py` 의 Pydantic class-based config 폐기 예고 — 이 작업과 무관하다) — 모두 인용의 학술지 자리에 `교육학연구`(series_title) 대신 `한국교육학회`(publisher)가 들어가서 문자열 `==` 비교의 `AssertionError` 다. 저자 3인·2인 접두 둘(`test_korean_prefix_matches_report_reference`)도 공유 파일의 서지 확인(첫 assert)은 지나고 마지막 `korean == …` 에서 실패한다.

프론트 쪽 새 테스트는 프론트를 고치지 않으므로 처음부터 통과한다(`referenceText` 가 이미 `series_title` 을 쓴다):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx vitest run tests/unit/reportDocument.test.ts`

Expected: `Tests  27 passed (27)` (기준선 26 + 1)

- [ ] **Step 3: 구현한다**

`app/services/search/paper_citation.py` — 교체 전:

```python
    journal     = (book.publisher or "").strip()
```

교체 후:

```python
    # 학술지 = series_title (KCI 논문의 publisher 는 학회 이름이다). 없으면 비운다 — publisher 로 물러나지 않는다
    journal     = (book.series_title or "").strip()
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_paper_citation.py -q -p no:cacheprovider`

Expected: `6 passed, 1 warning`

프론트(Task 0 의 `npm ci` 가 끝나 있어야 한다 — JSON import 가 타입검사를 지나는지도 본다):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx vitest run
```

Expected:
- typecheck — `0`
- vitest — `Test Files  28 passed (28)` / `Tests  496 passed (496)` (기준선 495 + 1)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 0, `3 errors`(수집 오류 셋) 그대로. 이 작업은 6개를 더한다(Task 1 만 적용한 사본에서 `1406 passed` → `1412 passed, 1 skipped, 2 warnings, 3 errors`. Task 2·3 이 먼저 들어갔으면 그 수만큼 더 많다).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/services/search/paper_citation.py app/tests/test_paper_citation.py frontend/tests/fixtures/citation_reference.json frontend/tests/unit/reportDocument.test.ts && git status --short && git commit -m "[Fix] round06a — 논문 상세 인용의 학술지 자리를 publisher(학회 이름)에서 series_title 로 바꾼다. series_title 이 없으면 학술지 자리를 비우고 publisher 로 물러나지 않는다. 국문 인용의 '저자 (연도). 제목. 학술지, 권호.' 부분이 보고서 참고문헌(referenceText)과 같은 글자인지는 두 쪽 테스트가 함께 읽는 공유 파일(frontend/tests/fixtures/citation_reference.json — 저자 3인 고정 예제·저자 2인)로 고정한다. 저자 규칙·UCI·영문 인용은 그대로"
```

---


### Task 5: llm_client 호출별 `base_url`·`model`

**왜:** spec §6-3 모델 라우팅. 연구 어시스턴트 생성은 kind 마다 Qwen(`VLM_BASE_URL`·`VLM_MODEL`)과 gemma(`LLM_BASE_URL`·`LLM_MODEL`)를 고르고(Task 8 의 `WORK_MODEL_ROUTES`), 해석·검사 실패나 전송 실패 때 다른 모델로 넘긴다. 지금 `llm_client` 는 설정의 한 엔드포인트만 부른다. `chat_full`·`chat`·`chat_stream` 에 호출별 `base_url`·`model` 을 더한다.

**Files:**
- Modify: `app/services/llm_client.py` (모듈 docstring 22-23행 뒤, `_ollama_body` 148-157행, `_request_once` 166-190행, `chat_full` 201-223행·231행·241행·249행, `chat` 256-263행, `chat_stream` 266-282행·300-302행)
- Test: `app/tests/test_llm_client.py` (파일 끝에 11개)

**알아 둘 것:**
- 공통 계약 §5 시그니처 그대로: `chat_full(messages, *, params=None, timeout=120.0, base_url: str | None = None, model: str | None = None) -> LLMResult`, `chat`·`chat_stream` 도 같은 두 키워드. `None` 이면 지금처럼 `LLM_BASE_URL`·`LLM_MODEL` 이다 — 빈 문자열은 `None` 으로 보지 않는다(설정이 비었으면 조용히 gemma 로 가지 않고 요청 오류로 드러난다).
- 기존 호출부(research `critic`·`planner`·`synthesizer`, 적재 `summarizer`·`paper_enricher`·`pdf_meta_extractor`·`cover_generator`)는 고치지 않는다. 그들의 테스트가 `chat` 이름을 `async def fake_chat(messages, *, params=None, timeout=None)` 로 바꿔 끼우는데, 이 작업은 그 호출부가 새 키워드를 넘기지 않으므로 대역도 그대로 맞는다.
- 엔드포인트는 호출 시작 때 한 번 정한다(`_endpoint`). `chat_full` 의 재시도는 같은 엔드포인트로만 한다 — 다른 모델로 넘기는 일은 호출부(Task 8 `run_generation`)가 한다. 재시도 규칙·시간 한도는 그대로다.
- **계약과 다른 점(비공개 함수만):** 계약 §5 는 "`_request_once`·`_ollama_body` 도 같은 두 인자를 받는다" 라고 했다. `_request_once` 는 `base_url`·`model` 을 받지만(`_endpoint` 로 채운 값, 키워드 전용·필수), `_ollama_body` 는 `base_url` 을 쓰지 않으므로 `model` 만 받는다. 둘 다 이 모듈 밖에서 부르는 곳이 없다(`grep -rn "_request_once\|_ollama_body" app` 로 확인).
- API 스타일(`LLM_API_STYLE`)·`think`·`num_ctx` 는 호출별로 바뀌지 않는다. Qwen 의 thinking 을 끄려면 호출부가 `params` 에 `chat_template_kwargs` 를 싣는다(openai 경로의 본문은 `{"model", "messages", **params}` 다).
- "length" 경고는 실제로 부른 모델 이름을 남긴다(지금은 늘 `cfg.LLM_MODEL`). `chat_full` 의 재시도·포기 로그 둘(상태 코드 실패·전송 실패)에도 `model=` 을 더한다 — 생성마다 Qwen·gemma 를 고르면 워커 로그의 503·ConnectError 가 어느 모델 것인지 가려야 한다(OCR 포화 때 Qwen→gemma 넘김 진단, spec §6-3). 기존 로그 테스트는 `1/3`·`시도 횟수 소진` 같은 부분 문자열만 보므로 그대로 지난다.
- `chat_stream` 테스트는 지금까지 없었다. 기본 엔드포인트 회귀 테스트 하나(`test_chat_stream_defaults_to_the_configured_endpoint`)는 구현 전에도 통과한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_llm_client.py` 파일 끝 — 교체 전(마지막 테스트):

```python
@pytest.mark.parametrize("schedule", ["2,8", "", "2,8,", " 5 ", "0,60"])
def test_backoff_valid_schedules_log_nothing(fresh_schedule_cache, caplog, schedule):
    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        llm_client._backoff_delay(schedule, 1)

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
```

교체 후(위 테스트는 그대로 두고 그 뒤에 덧붙인다):

```python
@pytest.mark.parametrize("schedule", ["2,8", "", "2,8,", " 5 ", "0,60"])
def test_backoff_valid_schedules_log_nothing(fresh_schedule_cache, caplog, schedule):
    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        llm_client._backoff_delay(schedule, 1)

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# ── 호출별 엔드포인트(round06a) — 연구 어시스턴트가 생성마다 Qwen·gemma 를 고른다 ─────────────────
# base_url·model 을 주지 않으면(None) 지금처럼 LLM_BASE_URL·LLM_MODEL 이다. 기존 호출부는 넘기지 않는다.

QWEN_URL, QWEN_MODEL = "http://qwen.test/v1", "qwen-test"


def _sse(*deltas: str) -> httpx.Response:
    """openai 호환 스트리밍 응답(SSE) — 델타마다 data 줄 하나, 끝에 [DONE]."""
    lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": d}}]}, ensure_ascii=False)
        for d in deltas
    ]
    return httpx.Response(200, content=("\n\n".join([*lines, "data: [DONE]"]) + "\n\n").encode())


def _ndjson(*deltas: str) -> httpx.Response:
    """ollama 스트리밍 응답(NDJSON) — 델타마다 한 줄, 끝에 done."""
    lines = [json.dumps({"message": {"content": d}, "done": False}, ensure_ascii=False) for d in deltas]
    lines.append(json.dumps({"message": {"content": ""}, "done": True}))
    return httpx.Response(200, content=("\n".join(lines) + "\n").encode())


def _collect(gen) -> list[str]:
    async def _go():
        return [d async for d in gen]
    return asyncio.run(_go())


def test_chat_full_uses_the_per_call_endpoint(cfg, server, sleeps):
    server.queue.append(_ok("큐웬 응답"))

    result = asyncio.run(llm_client.chat_full(
        MESSAGES, params={"max_tokens": 200}, base_url=QWEN_URL, model=QWEN_MODEL,
    ))

    assert result.content == "큐웬 응답"
    url, body = server.calls[0]
    assert url == "http://qwen.test/v1/chat/completions"
    assert body["model"] == QWEN_MODEL and body["max_tokens"] == 200


def test_explicit_none_keeps_the_configured_endpoint(cfg, server, sleeps):
    server.queue.append(_ok())

    asyncio.run(llm_client.chat_full(MESSAGES, base_url=None, model=None))

    url, body = server.calls[0]
    assert url == "http://llm.test/v1/chat/completions" and body["model"] == "gemma-test"


def test_base_url_and_model_are_independent(cfg, server, sleeps):
    server.queue.extend([_ok(), _ok()])

    asyncio.run(llm_client.chat_full(MESSAGES, base_url=QWEN_URL))
    asyncio.run(llm_client.chat_full(MESSAGES, model=QWEN_MODEL))

    assert [(url, body["model"]) for url, body in server.calls] == [
        ("http://qwen.test/v1/chat/completions", "gemma-test"),
        ("http://llm.test/v1/chat/completions", QWEN_MODEL),
    ]


def test_retries_stay_on_the_per_call_endpoint(cfg, server, sleeps, caplog):
    server.queue.extend([httpx.Response(503, text="busy"), httpx.ConnectError("연결 거부"), _ok("회복")])

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        result = asyncio.run(llm_client.chat_full(MESSAGES, base_url=QWEN_URL, model=QWEN_MODEL))

    assert result.content == "회복" and sleeps == [2.0, 8.0]
    assert {(url, body["model"]) for url, body in server.calls} == {
        ("http://qwen.test/v1/chat/completions", QWEN_MODEL),
    }
    # 재시도 경고(상태 코드·전송 실패)도 부른 모델을 남긴다 — Qwen·gemma 넘김을 워커 로그로 가른다
    warned = [r.getMessage() for r in caplog.records if r.name == llm_client.log.name]
    assert len(warned) == 2
    assert all(f"model={QWEN_MODEL}" in m and "gemma-test" not in m for m in warned)


def test_length_warning_names_the_model_that_was_called(cfg, server, sleeps, caplog):
    server.queue.append(_ok("잘린 응답", "length"))

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        asyncio.run(llm_client.chat_full(
            MESSAGES, params={"max_tokens": 200}, base_url=QWEN_URL, model=QWEN_MODEL,
        ))

    warned = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warned) == 1
    assert f"model={QWEN_MODEL}" in warned[0] and "gemma-test" not in warned[0]


def test_ollama_path_uses_the_per_call_endpoint(cfg, server, sleeps, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_API_STYLE", "ollama")
    server.queue.append(httpx.Response(200, json={"message": {"content": "응답"}, "done": True}))

    asyncio.run(llm_client.chat_full(MESSAGES, base_url="http://ollama2.test:11434/v1", model="qwen3:8b"))

    url, body = server.calls[0]
    assert url == "http://ollama2.test:11434/api/chat" and body["model"] == "qwen3:8b"


def test_chat_passes_the_endpoint_through(cfg, server, sleeps):
    server.queue.append(_ok("본문"))

    assert asyncio.run(llm_client.chat(MESSAGES, base_url=QWEN_URL, model=QWEN_MODEL)) == "본문"
    url, body = server.calls[0]
    assert url == "http://qwen.test/v1/chat/completions" and body["model"] == QWEN_MODEL


def test_chat_stream_defaults_to_the_configured_endpoint(cfg, server):
    server.queue.append(_sse("가", "나"))

    assert _collect(llm_client.chat_stream(MESSAGES, params={"max_tokens": 50})) == ["가", "나"]
    url, body = server.calls[0]
    assert url == "http://llm.test/v1/chat/completions"
    assert body["model"] == "gemma-test" and body["stream"] is True and body["max_tokens"] == 50


def test_chat_stream_uses_the_per_call_endpoint(cfg, server):
    server.queue.append(_sse("절의 ", "첫 문장"))

    deltas = _collect(llm_client.chat_stream(MESSAGES, base_url=QWEN_URL, model=QWEN_MODEL))

    assert deltas == ["절의 ", "첫 문장"]
    url, body = server.calls[0]
    assert url == "http://qwen.test/v1/chat/completions" and body["model"] == QWEN_MODEL


def test_chat_stream_ollama_uses_the_per_call_endpoint(cfg, server, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_API_STYLE", "ollama")
    server.queue.append(_ndjson("가", "나"))

    deltas = _collect(llm_client.chat_stream(
        MESSAGES, base_url="http://ollama2.test:11434/v1", model="qwen3:8b",
    ))

    assert deltas == ["가", "나"]
    url, body = server.calls[0]
    assert url == "http://ollama2.test:11434/api/chat"
    assert body["model"] == "qwen3:8b" and body["stream"] is True


def test_chat_stream_still_does_not_retry(cfg, server, sleeps):
    server.queue.append(httpx.Response(503, text="busy"))

    with pytest.raises(httpx.HTTPStatusError):
        _collect(llm_client.chat_stream(MESSAGES, base_url=QWEN_URL, model=QWEN_MODEL))

    assert len(server.calls) == 1 and sleeps == []
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_llm_client.py -q -p no:cacheprovider`

Expected: `10 failed, 58 passed, 1 warning`(경고는 기존 `core/config.py` 의 Pydantic class-based config 폐기 예고) — 10개 모두 `TypeError: chat_full() got an unexpected keyword argument 'base_url'`(6개)·`chat_stream() …`(3개)·`chat() …`(1개). 58 은 기존 57 + 기본 엔드포인트 스트리밍 회귀 테스트 1개.

- [ ] **Step 3: 구현한다**

`app/services/llm_client.py` 를 열 군데 고친다.

① 모듈 docstring — 교체 전:

```python
  연결(≤10초)까지 걸릴 수 있다 — 호출 전체의 최악은 timeout + 10초다. 더 시도하지 않는 실패는 error 로,
  시도 횟수를 다 썼는지 남은 시간이 모자랐는지를 함께 남긴다.
```

교체 후:

```python
  연결(≤10초)까지 걸릴 수 있다 — 호출 전체의 최악은 timeout + 10초다. 더 시도하지 않는 실패는 error 로,
  시도 횟수를 다 썼는지 남은 시간이 모자랐는지를 함께 남긴다.

  호출별 엔드포인트: chat_full()·chat()·chat_stream() 은 base_url·model 을 받는다. 주지 않으면(None)
  LLM_BASE_URL·LLM_MODEL 이다 — 연구 어시스턴트(round06)가 생성마다 Qwen(VLM_BASE_URL·VLM_MODEL)과
  gemma 를 고를 때 쓴다. 재시도는 같은 엔드포인트로만 한다(다른 모델로 넘기는 일은 호출부가 한다).
  API 스타일(LLM_API_STYLE)·think·num_ctx 는 호출별로 바꾸지 않는다.
```

② `_endpoint` 를 더하고 `_ollama_body` 가 모델을 받게 한다 — 교체 전:

```python
def _ollama_body(messages: list[dict], params: dict, stream: bool) -> dict:
    cfg = get_settings()
    opts: dict = {"num_ctx": cfg.OLLAMA_NUM_CTX}
    if "temperature" in params:
        opts["temperature"] = params["temperature"]
    if "max_tokens" in params:
        opts["num_predict"] = params["max_tokens"]   # ollama 는 num_predict
    body: dict = {
        "model": cfg.LLM_MODEL,
        "messages": messages,
```

교체 후:

```python
def _endpoint(base_url: str | None, model: str | None) -> tuple[str, str]:
    """호출별 (base_url, model) — None 인 쪽은 설정(LLM_BASE_URL·LLM_MODEL)으로 채운다."""
    cfg = get_settings()
    return (
        cfg.LLM_BASE_URL if base_url is None else base_url,
        cfg.LLM_MODEL if model is None else model,
    )


def _ollama_body(messages: list[dict], params: dict, stream: bool, *, model: str) -> dict:
    cfg = get_settings()
    opts: dict = {"num_ctx": cfg.OLLAMA_NUM_CTX}
    if "temperature" in params:
        opts["temperature"] = params["temperature"]
    if "max_tokens" in params:
        opts["num_predict"] = params["max_tokens"]   # ollama 는 num_predict
    body: dict = {
        "model": model,
        "messages": messages,
```

③ `_request_once` 머리와 ollama 경로 — 교체 전:

```python
async def _request_once(messages: list[dict], params: dict, timeout: float) -> LLMResult:
    """한 번 보내고 응답을 LLMResult 로 바꾼다 (재시도는 chat_full 이 한다).

    timeout 은 이 시도에 남은 시간 — 읽기·쓰기·풀 timeout 으로 쓰고, 연결 timeout 은 그중
    _CONNECT_TIMEOUT_SECONDS 까지만 준다. httpx 는 단계마다 따로 재고 읽기 timeout 은 연결 전에 정해지므로
    이 시도는 남은 시간 + 연결 시간(≤ _CONNECT_TIMEOUT_SECONDS)까지 걸릴 수 있다.
    """
    cfg = get_settings()
    client_timeout = httpx.Timeout(timeout, connect=min(_CONNECT_TIMEOUT_SECONDS, timeout))
    if cfg.LLM_API_STYLE == "ollama":
        url = f"{_ollama_root(cfg.LLM_BASE_URL)}/api/chat"
        body = _ollama_body(messages, params, stream=False)
```

교체 후:

```python
async def _request_once(
    messages: list[dict], params: dict, timeout: float, *, base_url: str, model: str,
) -> LLMResult:
    """한 번 보내고 응답을 LLMResult 로 바꾼다 (재시도는 chat_full 이 한다).

    timeout 은 이 시도에 남은 시간 — 읽기·쓰기·풀 timeout 으로 쓰고, 연결 timeout 은 그중
    _CONNECT_TIMEOUT_SECONDS 까지만 준다. httpx 는 단계마다 따로 재고 읽기 timeout 은 연결 전에 정해지므로
    이 시도는 남은 시간 + 연결 시간(≤ _CONNECT_TIMEOUT_SECONDS)까지 걸릴 수 있다.
    base_url·model 은 _endpoint 로 채운 값이다.
    """
    cfg = get_settings()
    client_timeout = httpx.Timeout(timeout, connect=min(_CONNECT_TIMEOUT_SECONDS, timeout))
    if cfg.LLM_API_STYLE == "ollama":
        url = f"{_ollama_root(base_url)}/api/chat"
        body = _ollama_body(messages, params, stream=False, model=model)
```

④ `_request_once` 의 openai 경로 — 교체 전:

```python
    # openai 호환 (vLLM 등)
    url = f"{cfg.LLM_BASE_URL}/chat/completions"
    body = {"model": cfg.LLM_MODEL, "messages": messages, **params}
    async with httpx.AsyncClient(timeout=client_timeout) as client:
```

교체 후:

```python
    # openai 호환 (vLLM 등)
    url = f"{base_url}/chat/completions"
    body = {"model": model, "messages": messages, **params}
    async with httpx.AsyncClient(timeout=client_timeout) as client:
```

⑤ `chat_full` 시그니처·엔드포인트 — 교체 전:

```python
async def chat_full(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> LLMResult:
    """비스트리밍 chat 완성 → LLMResult(content, finish_reason). 일시적 실패는 재시도한다.

    재시도는 호출자의 timeout 안에서만 한다 — 시작 시각 + timeout 이 deadline 이고, 시도마다 httpx 의
    읽기·쓰기·풀 timeout 은 남은 시간, 연결 timeout 은 min(_CONNECT_TIMEOUT_SECONDS, 남은 시간)이다
    (더 시도할지는 _retry_delay). 읽기 timeout 은 연결 전에 정해지므로 시도 하나는 남은 시간 + 연결
    (≤10초)까지 걸릴 수 있어, 이 호출의 최악은 timeout + 10초다. 다시 보낼 실패는 경고, 여기서 끝나는
    실패(재시도 불가 4xx, 다시 보낼 실패의 시도 횟수 소진·남은 시간 부족)만 error 로 남긴다.
    """
    cfg = get_settings()
    params = params or {}
    attempts = max(1, int(cfg.LLM_RETRY_ATTEMPTS))
    schedule = cfg.LLM_RETRY_BACKOFF_SECONDS
    deadline = _monotonic() + timeout
    attempt = 1
    while True:
        try:
            result = await _request_once(messages, params, min(timeout, deadline - _monotonic()))
```

교체 후:

```python
async def chat_full(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
    base_url: str | None = None,
    model: str | None = None,
) -> LLMResult:
    """비스트리밍 chat 완성 → LLMResult(content, finish_reason). 일시적 실패는 재시도한다.

    재시도는 호출자의 timeout 안에서만 한다 — 시작 시각 + timeout 이 deadline 이고, 시도마다 httpx 의
    읽기·쓰기·풀 timeout 은 남은 시간, 연결 timeout 은 min(_CONNECT_TIMEOUT_SECONDS, 남은 시간)이다
    (더 시도할지는 _retry_delay). 읽기 timeout 은 연결 전에 정해지므로 시도 하나는 남은 시간 + 연결
    (≤10초)까지 걸릴 수 있어, 이 호출의 최악은 timeout + 10초다. 다시 보낼 실패는 경고, 여기서 끝나는
    실패(재시도 불가 4xx, 다시 보낼 실패의 시도 횟수 소진·남은 시간 부족)만 error 로 남긴다.
    base_url·model 을 주면 그 엔드포인트로 보낸다(None 이면 LLM_BASE_URL·LLM_MODEL) — 재시도도 같은 곳이다.
    """
    cfg = get_settings()
    params = params or {}
    base_url, model = _endpoint(base_url, model)
    attempts = max(1, int(cfg.LLM_RETRY_ATTEMPTS))
    schedule = cfg.LLM_RETRY_BACKOFF_SECONDS
    deadline = _monotonic() + timeout
    attempt = 1
    while True:
        try:
            result = await _request_once(
                messages, params, min(timeout, deadline - _monotonic()), base_url=base_url, model=model,
            )
```

⑥ `chat_full` 의 상태 코드 실패 로그 — 교체 전:

```python
                f"[llm_client:{cfg.LLM_API_STYLE}] {code} ({attempt}/{attempts}회차{why}) — "
```

교체 후:

```python
                f"[llm_client:{cfg.LLM_API_STYLE}] {code} model={model} ({attempt}/{attempts}회차{why}) — "
```

⑦ `chat_full` 의 전송 실패 로그 — 교체 전:

```python
                f"[llm_client:{cfg.LLM_API_STYLE}] {type(e).__name__} ({attempt}/{attempts}회차{why}) — {e}",
```

교체 후:

```python
                f"[llm_client:{cfg.LLM_API_STYLE}] {type(e).__name__} model={model} "
                f"({attempt}/{attempts}회차{why}) — {e}",
```

⑧ `chat_full` 의 잘림 경고 — 교체 전:

```python
                    f"model={cfg.LLM_MODEL} max_tokens={params.get('max_tokens')}"
```

교체 후:

```python
                    f"model={model} max_tokens={params.get('max_tokens')}"
```

⑨ `chat` 과 `chat_stream` — 교체 전:

```python
async def chat(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> str:
    """비스트리밍 chat 완성 → 최종 content 문자열 (= chat_full 의 content)."""
    return (await chat_full(messages, params=params, timeout=timeout)).content


async def chat_stream(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """스트리밍 chat → content 델타 순차 yield.

    검색/대화 SSE 기능용. 국회 1차(요약→DB) 스코프에는 불필요하지만
    스타일 겸용을 위해 함께 제공한다.
    """
    cfg = get_settings()
    params = params or {}

    if cfg.LLM_API_STYLE == "ollama":
        url = f"{_ollama_root(cfg.LLM_BASE_URL)}/api/chat"
        body = _ollama_body(messages, params, stream=True)
```

교체 후:

```python
async def chat(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
    base_url: str | None = None,
    model: str | None = None,
) -> str:
    """비스트리밍 chat 완성 → 최종 content 문자열 (= chat_full 의 content)."""
    return (await chat_full(
        messages, params=params, timeout=timeout, base_url=base_url, model=model,
    )).content


async def chat_stream(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
    base_url: str | None = None,
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """스트리밍 chat → content 델타 순차 yield. 재시도하지 않는다.

    검색/대화 SSE 기능용. 국회 1차(요약→DB) 스코프에는 불필요하지만
    스타일 겸용을 위해 함께 제공한다. base_url·model 은 chat_full 과 같다(None 이면 설정).
    """
    cfg = get_settings()
    params = params or {}
    base_url, model = _endpoint(base_url, model)

    if cfg.LLM_API_STYLE == "ollama":
        url = f"{_ollama_root(base_url)}/api/chat"
        body = _ollama_body(messages, params, stream=True, model=model)
```

⑩ `chat_stream` 의 openai 경로 — 교체 전:

```python
    # openai 호환 (SSE)
    url = f"{cfg.LLM_BASE_URL}/chat/completions"
    body = {"model": cfg.LLM_MODEL, "messages": messages, "stream": True, **params}
```

교체 후:

```python
    # openai 호환 (SSE)
    url = f"{base_url}/chat/completions"
    body = {"model": model, "messages": messages, "stream": True, **params}
```

고친 뒤 `grep -n "cfg.LLM_BASE_URL\|cfg.LLM_MODEL" app/services/llm_client.py` 는 `_endpoint` 안의 두 줄만 나와야 한다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_llm_client.py -q -p no:cacheprovider`

Expected: `68 passed, 1 warning` (기준선 57 + 11. 재시도 로그의 `model=` 은 새 테스트를 더하지 않고 `test_retries_stay_on_the_per_call_endpoint` 가 함께 본다)

`chat`·`chat_full` 을 부르는 모듈의 기존 테스트(호출부는 바뀌지 않는다):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_critic.py tests/test_research_planner.py tests/test_research_synthesizer.py tests/test_summarizer.py tests/test_paper_enricher.py -q -p no:cacheprovider`

Expected: 실패 0 — Task 1·4·5 만 적용한 사본에서 `278 passed, 2 warnings`(62 + 16 + 111 + 24 + 65). Task 2 가 먼저 들어갔으면 `test_research_critic.py` 가 그 작업이 더한 수만큼 많다.

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 0, `3 errors`(수집 오류 셋) 그대로. 이 작업은 11개를 더한다(Task 1·4 만 적용한 사본에서 `1412 passed` → `1423 passed, 1 skipped, 2 warnings, 3 errors`).

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/services/llm_client.py app/tests/test_llm_client.py && git status --short && git commit -m "[Feat] round06a — llm_client 의 chat_full·chat·chat_stream 이 호출별 base_url·model 을 받는다. 주지 않으면(None) 지금처럼 LLM_BASE_URL·LLM_MODEL 이라 기존 호출부는 바뀌지 않는다. 연구 어시스턴트가 생성마다 Qwen·gemma 를 고를 때 쓴다. chat_full 의 재시도는 같은 엔드포인트로만 하고 chat_stream 은 여전히 재시도하지 않는다. max_tokens 잘림 경고와 재시도·포기 로그는 실제로 부른 모델 이름(model=)을 남긴다"
```


### Task 6: 브라우저당 실행 제한·429 code

spec §6-3 '동시 실행 제한(딥리서치)'·§6-2 '기존 수정' 줄, 계약 §6. 지금 `_to_run_queue` 는 적재 큐를 나눠 쓸 때(RESEARCH_QUEUE 가 적재 큐)만 실행 슬롯을 세고, 운영(`RESEARCH_QUEUE=q_research`)에서는 아무것도 막지 않는다 — 한 브라우저가 딥리서치를 여러 개 승인하면 전용 워커(동시 1)의 줄을 혼자 채운다. 잡의 `created_by`(잡을 만든 브라우저 ID)가 같은 다른 잡이 approved·queued·running 이면 approve·retry 를 429 로 막는다.

- **기준은 잡이다:** 요청 헤더가 아니라 `job.created_by` 를 쓰므로 approve·retry 에 헤더 의존성을 더하지 않는다. `created_by` 가 없는 잡(헤더 없는 curl, 평가 스크립트 `run_pair.py`)은 검사도 잠금도 하지 않는다. 승인하지 않고 둔 계획(created·planning·awaiting_approval)은 세지 않는다.
- **잠금:** 같은 브라우저의 동시 승인 두 건이 서로 커밋 전 상태를 보고 둘 다 통과하지 않게 `pg_advisory_xact_lock(_browser_lock_key(created_by))` 을 잡은 뒤 세고, 같은 트랜잭션에서 `_transition` 이 커밋하며 잠금을 푼다(걸리면 롤백이 푼다). 공유 큐 잠금과 함께 걸릴 때는 늘 공유 큐 → 브라우저 순서다. `func.pg_advisory_xact_lock(<int>)` 는 SQLAlchemy asyncpg 방언이 값 크기에 따라 `$1::INTEGER`/`$1::BIGINT` 로 그린다(검증 사본에서 컴파일 확인) — Postgres 는 둘 다 bigint 판으로 받는다. 이 잠금 문장은 지금까지 운영에서 한 번도 돈 적이 없다(공유 큐 분기는 운영 큐에서 꺼져 있다) — Task 17 운영 확인 ⑥ 의 429 browser_active 가 첫 실행이다.
- **429 detail:** 문자열에서 `{code, message, job_id?}` 로 바꾼다. 기존 공유 큐 429 는 `shared_queue`(문구 그대로), 새 제한은 `browser_active`(화면이 '진행 중인 연구 보기' 링크를 띄울 `job_id` 포함). 프론트는 지금 429 를 고정 문구로 보이므로(`frontend/utils/researchErrors.ts` 37행) 이 task 만으로 화면이 깨지지 않는다 — 문구 분기는 Task 13.
- **테스트 주의:** 로컬 설정의 `RESEARCH_QUEUE` 기본값은 `q_llm`(적재 큐)이라 `_queue` 로 바꾸지 않은 테스트는 공유 큐 검사가 먼저 돈다. 브라우저 제한 테스트는 운영과 같은 `q_research` 로 둔다. 대역 `_FakeDB` 는 브라우저 조회 문장(`SELECT research_jobs.id … LIMIT`)과 `!=` 를 평가하고, 잡은 잠금 키를 `locks` 에 순서대로 남기게 넓힌다.

**Files:**
- Modify: `app/api/research.py` (124c481 기준: 모듈 docstring 15-17행·import 18행, 상수 67-68행, `_to_run_queue` 115-138행, approve 의 `_to_run_queue` 호출 227-228행, retry 의 호출 270-271행)
- Modify: `app/tests/test_research_api.py` (Task 2 뒤 기준: `_matches` 46-49행, `_Result.scalar_one` 67-68행, `_FakeDB.__init__` 81-82행, `_FakeDB.execute` 115-117행, `TestSharedQueueRunSlot` 끝·`TestCancel` 474-478행 — Task 2 가 `TestCreate` 에 테스트 2개(15행)를 더하기 전의 124c481 에서는 459-463행)
- Test: `app/tests/test_research_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_api.py` 바꾸기 ①: `_matches` 가 `!=` 를 평가한다. old:

```python
    if op is operators.eq:
        return left == right
    if op is operators.in_op:
```

new:

```python
    if op is operators.eq:
        return left == right
    if op is operators.ne:
        return left != right
    if op is operators.in_op:
```

`app/tests/test_research_api.py` 바꾸기 ②: `_Result` 에 `scalar()` 를 더한다. old:

```python
    def scalar_one(self):
        return self._scalar


class _FakeDB:
```

new:

```python
    def scalar_one(self):
        return self._scalar

    def scalar(self):
        return self._scalar


class _FakeDB:
```

`app/tests/test_research_api.py` 바꾸기 ③: 잡은 잠금 키를 기록한다. old:

```python
        self.sql: list[str] = []
        self.after_get = None       # 읽은 직후에 끼어드는 경쟁 요청을 흉내 낸다
```

new:

```python
        self.sql: list[str] = []
        self.locks: list[int] = []  # pg_advisory_xact_lock 에 넘긴 키, 잡은 순서대로
        self.after_get = None       # 읽은 직후에 끼어드는 경쟁 요청을 흉내 낸다
```

`app/tests/test_research_api.py` 바꾸기 ④: 잠금 키를 남기고 브라우저 조회 문장을 평가한다. old:

```python
        if sql.startswith("SELECT pg_advisory_xact_lock"):
            return _Result()
        if sql.startswith("SELECT count(*)") and "FROM research_jobs" in sql:
```

new:

```python
        if sql.startswith("SELECT pg_advisory_xact_lock"):
            self.locks.extend(stmt.compile().params.values())
            return _Result()
        if sql.startswith("SELECT research_jobs.id \nFROM research_jobs") and "LIMIT" in sql:
            ids = [row["id"] for row in self.jobs.values() if _matches(stmt.whereclause, row)]
            return _Result(scalar=ids[0] if ids else None)
        if sql.startswith("SELECT count(*)") and "FROM research_jobs" in sql:
```

`app/tests/test_research_api.py` 바꾸기 ⑤: `TestSharedQueueRunSlot` 끝에 code 테스트를 더하고, 그 뒤 `TestCancel` 앞에 `TestBrowserRunLimit` 을 둔다. old:

```python
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200
        assert not any("pg_advisory_xact_lock" in s for s in api.db.sql)


class TestCancel:
```

new:

```python
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200
        assert not any("pg_advisory_xact_lock" in s for s in api.db.sql)

    def test_shared_queue_429_carries_its_code(self, api, monkeypatch):
        """화면이 429 두 가지(공유 큐·같은 브라우저)를 문구가 아니라 code 로 가른다."""
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status="running", plan=["가"])
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        res = api.client.post(f"/api/research/{jid}/approve")

        assert res.status_code == 429
        detail = res.json()["detail"]
        assert detail["code"] == "shared_queue"
        assert "한 번에 한 건만 실행한다" in detail["message"]
        assert "job_id" not in detail


_SID = "3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e"
_OTHER_SID = "7a6b5c4d-3e2f-4a1b-9c8d-7e6f5a4b3c2d"
_BROWSER_ACTIVE = "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요"


class TestBrowserRunLimit:
    """한 브라우저(잡의 created_by)는 딥리서치를 한 번에 하나만 실행 큐에 둔다.

    기준은 요청 헤더가 아니라 잡을 만든 브라우저다. 운영 큐(q_research)에서 확인한다 —
    적재 큐(q_llm)면 공유 큐 검사가 먼저 걸려 이 검사까지 오지 않는다.
    """

    @pytest.mark.parametrize("busy", ["running", "approved", "queued"])
    def test_approve_is_429_while_the_same_browser_has_a_run(self, api, monkeypatch, busy):
        _queue(api, monkeypatch, "q_research")
        other = api.db.add_job(status=busy, plan=["가"], created_by=_SID)
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_by=_SID)

        res = api.client.post(f"/api/research/{jid}/approve")

        assert res.status_code == 429
        assert res.json()["detail"] == {
            "code": "browser_active", "message": _BROWSER_ACTIVE, "job_id": str(other),
        }
        # 앞 잡이 끝나면 다시 승인할 수 있어야 한다
        assert api.db.jobs[jid]["status"] == "awaiting_approval"
        assert api.celery.sent == [] and api.events == []

    def test_retry_is_429_while_the_same_browser_has_a_run(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_research")
        other = api.db.add_job(status="running", plan=["가"], created_by=_SID)
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             last_error="종합 실패", created_by=_SID)

        res = api.client.post(f"/api/research/{jid}/retry")

        assert res.status_code == 429
        assert res.json()["detail"]["job_id"] == str(other)
        row = api.db.jobs[jid]
        assert row["status"] == "failed" and row["last_error"] == "종합 실패"
        assert api.celery.sent == [] and api.published == []

    def test_other_browsers_and_anonymous_runs_do_not_block(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"], created_by=_OTHER_SID)
        api.db.add_job(status="queued", plan=["가"], created_by=None)
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_by=_SID)

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200

    @pytest.mark.parametrize("idle", [
        "created", "planning", "awaiting_approval", "completed", "failed", "canceled",
    ])
    def test_jobs_not_in_the_run_queue_do_not_count(self, api, monkeypatch, idle):
        """승인하지 않고 둔 계획은 세지 않는다 — 계획을 여러 개 띄워 두고 하나씩 승인할 수 있다."""
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status=idle, plan=["가"], created_by=_SID)
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_by=_SID)

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200

    def test_job_without_a_browser_is_not_limited(self, api, monkeypatch):
        """created_by 가 없는 잡(헤더 없는 curl·평가 스크립트)은 검사도 잠금도 하지 않는다."""
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"], created_by=None)
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_by=None)

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200
        assert api.db.locks == []

    def test_state_errors_come_before_the_browser_check(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"], created_by=_SID)
        jid = api.db.add_job(status="completed", plan=["가"], created_by=_SID)

        assert api.client.post(f"/api/research/{jid}/retry").status_code == 409

    def test_browser_is_checked_under_its_lock_in_the_transition_transaction(
        self, api, monkeypatch,
    ):
        """같은 브라우저의 두 승인이 동시에 오면 둘 다 빈 줄을 보고 통과한다. 브라우저 잠금을
        잡은 뒤 세고, 같은 트랜잭션에서 전이해 그 커밋이 잠금을 푼다."""
        _queue(api, monkeypatch, "q_research")
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_by=_SID)

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200

        sql = api.db.sql
        lock = next(i for i, s in enumerate(sql) if "pg_advisory_xact_lock" in s)
        check = next(i for i, s in enumerate(sql) if s.startswith("SELECT research_jobs.id"))
        upd = next(i for i, s in enumerate(sql) if s.startswith("UPDATE research_jobs"))
        assert lock < check < upd
        assert not {"COMMIT", "ROLLBACK"} & set(sql[lock:upd])
        assert api.db.locks == [api.research._browser_lock_key(_SID)]

    def test_rejection_rolls_back_without_writing(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"], created_by=_SID)
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_by=_SID)

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 429

        sql = api.db.sql
        check = next(i for i, s in enumerate(sql) if s.startswith("SELECT research_jobs.id"))
        assert sql[check + 1:] == ["ROLLBACK"]

    def test_shared_queue_lock_comes_first(self, api, monkeypatch):
        """두 잠금을 늘 같은 순서로 잡는다 — 순서가 갈리면 두 요청이 서로를 기다린다."""
        _queue(api, monkeypatch, "q_llm")
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_by=_SID)

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200
        assert api.db.locks == [api.research._RUN_SLOT_LOCK,
                                api.research._browser_lock_key(_SID)]

    def test_lock_key_is_a_stable_signed_bigint_per_browser(self, api):
        key = api.research._browser_lock_key
        assert key(_SID) == key(_SID)
        assert key(_SID) != key(_OTHER_SID)
        for sid in (_SID, _OTHER_SID):
            assert -(2 ** 63) <= key(sid) < 2 ** 63
            assert key(sid) != api.research._RUN_SLOT_LOCK


class TestCancel:
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_api.py -q -p no:cacheprovider`
Expected: `9 failed, 79 passed` (기존 70 — 124c481 의 68 + Task 2 가 더한 2 — + 이미 통과하는 새 테스트 9: 다른 브라우저·세지 않는 상태 6·브라우저 없는 잡·상태 오류 우선)
- `test_approve_is_429_while_the_same_browser_has_a_run[running|approved|queued]`·`test_retry_is_429_while_the_same_browser_has_a_run`·`test_rejection_rolls_back_without_writing`: `assert 200 == 429` (브라우저 검사가 없다)
- `test_shared_queue_429_carries_its_code`: `TypeError: string indices must be integers, not 'str'` (detail 이 아직 문자열)
- `test_browser_is_checked_under_its_lock_in_the_transition_transaction`: `StopIteration` (브라우저 조회 문장이 없다)
- `test_shared_queue_lock_comes_first`·`test_lock_key_is_a_stable_signed_bigint_per_browser`: `AttributeError: module 'api.research' has no attribute '_browser_lock_key'`

- [ ] **Step 3: 구현한다**

`app/api/research.py` 바꾸기 ①: 모듈 docstring 에 새 제한을 적고 `hashlib` 를 import 한다. old:

```python
실행을 적재 워커와 나눠 쓰는 동안(RESEARCH_QUEUE 가 적재 큐)은 approve·retry 가 실행
슬롯이 비었을 때만 전이하고 아니면 429 다 — _to_run_queue.
"""
import json
import logging
```

new:

```python
실행을 적재 워커와 나눠 쓰는 동안(RESEARCH_QUEUE 가 적재 큐)은 approve·retry 가 실행
슬롯이 비었을 때만 전이하고 아니면 429 다 — _to_run_queue. 큐와 상관없이 한 브라우저
(잡의 created_by)는 실행 큐에 한 잡만 둔다 — 같은 브라우저의 다른 잡이 approved·queued·
running 이면 429. 두 429 는 detail.code(shared_queue·browser_active)로 가른다.
"""
import hashlib
import json
import logging
```

`app/api/research.py` 바꾸기 ②: 429 문구 상수. old:

```python
# 동시에 온 승인·재시도를 한 줄로 세우는 트랜잭션 잠금 키("RESEARCH" 의 ASCII)
_RUN_SLOT_LOCK = 0x5245534541524348
```

new:

```python
# 동시에 온 승인·재시도를 한 줄로 세우는 트랜잭션 잠금 키("RESEARCH" 의 ASCII)
_RUN_SLOT_LOCK = 0x5245534541524348
_SHARED_QUEUE_MESSAGE = (
    "다른 딥리서치가 실행 중이거나 실행을 기다리고 있다 — 끝나거나 취소된 뒤 "
    "다시 요청한다(적재와 워커를 나눠 쓰는 동안은 한 번에 한 건만 실행한다)"
)
_BROWSER_ACTIVE_MESSAGE = "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요"
```

`app/api/research.py` 바꾸기 ③: `_to_run_queue` 전체(115-138행)와 그 앞에 두 도우미. old:

```python
async def _to_run_queue(
    db: AsyncSession, jid: uuid.UUID, *, expect: tuple[str, ...], **values: object,
) -> bool:
    """실행 큐로 보내는 전이(approve·retry). 적재와 큐를 나눠 쓰는 동안은 실행 슬롯이
    비어 있을 때만 전이하고, 차 있으면 아무것도 쓰지 않고 429 다.

    센 뒤에 전이하는 사이에 다른 요청이 끼면 둘 다 빈 슬롯을 보고 통과한다. 그래서
    트랜잭션 잠금을 잡고 세며, 잠금은 _transition 의 커밋이 푼다 — READ COMMITTED 라
    잠금을 얻은 뒤의 조회는 먼저 들어온 쪽이 커밋한 상태를 본다.
    """
    if get_settings().RESEARCH_QUEUE in INGEST_QUEUES:
        await db.execute(select(func.pg_advisory_xact_lock(_RUN_SLOT_LOCK)))
        active = (await db.execute(
            select(func.count()).select_from(ResearchJob)
            .where(ResearchJob.status.in_(RUN_SLOT_STATUSES))
        )).scalar_one()
        if active >= SHARED_QUEUE_MAX_RUNS:
            await db.rollback()
            raise HTTPException(
                status_code=429,
                detail="다른 딥리서치가 실행 중이거나 실행을 기다리고 있다 — 끝나거나 취소된 뒤 "
                       "다시 요청한다(적재와 워커를 나눠 쓰는 동안은 한 번에 한 건만 실행한다)",
            )
    return await _transition(db, jid, expect=expect, **values)
```

new:

```python
def _browser_lock_key(created_by: str) -> int:
    """브라우저 ID 별 트랜잭션 잠금 키 — 같은 브라우저의 동시 승인·재시도를 한 줄로 세운다."""
    return int.from_bytes(hashlib.sha256(created_by.encode()).digest()[:8], "big", signed=True)


def _limit_detail(code: str, message: str, job_id: uuid.UUID | None = None) -> dict:
    detail = {"code": code, "message": message}
    if job_id is not None:
        detail["job_id"] = str(job_id)
    return detail


async def _to_run_queue(
    db: AsyncSession, jid: uuid.UUID, *, expect: tuple[str, ...], created_by: str | None,
    **values: object,
) -> bool:
    """실행 큐로 보내는 전이(approve·retry). 두 제한을 통과해야 전이하고, 걸리면 아무것도
    쓰지 않고 429 다.

    - 적재와 큐를 나눠 쓰는 동안(shared_queue): 실행 슬롯이 비어 있을 때만.
    - 같은 브라우저(browser_active): 잡을 만든 브라우저(created_by)의 다른 잡이 실행 큐
      (approved·queued·running)에 있으면 막는다. 기준은 요청 헤더가 아니라 잡이고,
      created_by 가 없으면(헤더 없는 curl·평가 스크립트) 검사하지 않는다.

    센 뒤에 전이하는 사이에 다른 요청이 끼면 둘 다 빈 슬롯을 보고 통과한다. 그래서
    트랜잭션 잠금을 잡고 세며, 잠금은 _transition 의 커밋(또는 거절 때의 롤백)이 푼다 —
    READ COMMITTED 라 잠금을 얻은 뒤의 조회는 먼저 들어온 쪽이 커밋한 상태를 본다.
    두 잠금은 늘 공유 큐 → 브라우저 순서로 잡는다(순서가 갈리면 서로를 기다린다).
    """
    if get_settings().RESEARCH_QUEUE in INGEST_QUEUES:
        await db.execute(select(func.pg_advisory_xact_lock(_RUN_SLOT_LOCK)))
        active = (await db.execute(
            select(func.count()).select_from(ResearchJob)
            .where(ResearchJob.status.in_(RUN_SLOT_STATUSES))
        )).scalar_one()
        if active >= SHARED_QUEUE_MAX_RUNS:
            await db.rollback()
            raise HTTPException(
                status_code=429, detail=_limit_detail("shared_queue", _SHARED_QUEUE_MESSAGE),
            )
    if created_by:
        await db.execute(select(func.pg_advisory_xact_lock(_browser_lock_key(created_by))))
        other = (await db.execute(
            select(ResearchJob.id)
            .where(ResearchJob.created_by == created_by,
                   ResearchJob.status.in_(RUN_SLOT_STATUSES),
                   ResearchJob.id != jid)
            .limit(1)
        )).scalar()
        if other is not None:
            await db.rollback()
            raise HTTPException(
                status_code=429,
                detail=_limit_detail("browser_active", _BROWSER_ACTIVE_MESSAGE, other),
            )
    return await _transition(db, jid, expect=expect, **values)
```

`app/api/research.py` 바꾸기 ④: approve 가 잡의 브라우저를 넘긴다. old:

```python
    if not await _to_run_queue(db, jid, expect=("awaiting_approval",),
                               status=STATUS_APPROVED, plan=plan):
```

new:

```python
    if not await _to_run_queue(db, jid, expect=("awaiting_approval",),
                               created_by=job.created_by, status=STATUS_APPROVED, plan=plan):
```

`app/api/research.py` 바꾸기 ⑤: retry 도 같다. old:

```python
    if not await _to_run_queue(db, jid, expect=("failed",), status=STATUS_QUEUED,
                               last_error=None, finished_at=None):
```

new:

```python
    if not await _to_run_queue(db, jid, expect=("failed",), created_by=job.created_by,
                               status=STATUS_QUEUED, last_error=None, finished_at=None):
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_api.py -q -p no:cacheprovider`
Expected: `88 passed` (기존 70 + 새 18)

관련 묶음:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_api.py tests/test_research_tasks.py tests/test_research_relay.py tests/test_research_models.py -q -p no:cacheprovider`
Expected: 실패 0 (검증 사본 — Task 1 의 모델·history_sqlite 와 Task 2 의 critic_scope 파라미터·API 테스트 2개를 먼저 넣은 상태 — 에서 `209 passed`. Task 3~5 가 이 파일들에 테스트를 더했으면 그만큼 많다)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`
Expected: 실패 0, `3 errors`(test_book_chat·test_build_manifest·test_loaders 수집 오류 — 기준선과 같음). Task 5 뒤 전체 수치 + 18 passed. 검증 사본(넣기 전 `1371 passed, 1 skipped` — 기준선 1369 + Task 2 의 API 테스트 2)에서 `1389 passed, 1 skipped`.

- [ ] **Step 5: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a add app/api/research.py app/tests/test_research_api.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a commit -m "[Feat] round06a — 딥리서치 승인·재시도에 브라우저당 실행 제한을 둔다: 잡을 만든 브라우저(created_by)의 다른 잡이 approved·queued·running 이면 429 browser_active(진행 중인 잡 id 포함)로 막고, 같은 브라우저의 동시 요청은 브라우저별 트랜잭션 잠금으로 한 줄로 세운다. created_by 가 없는 잡은 검사하지 않는다. 429 detail 을 {code, message, job_id} 로 구조화해 기존 공유 큐 429 는 shared_queue 로 가른다"
```

---


### Task 7: 딥리서치 대기 순번(run_queue·API·워커)

spec §6-3 '대기 순번(딥리서치)'·§6-4, 계약 §7. research_jobs 에는 승인 시각 칼럼이 없어, 실행 큐에 들어간 순서를 Redis ZSET `research:run_queue`(member = 잡 id, score = 넣은 시각)로 따로 든다. 순번 `ahead` = running 잡 수 + ZSET 에서 내 앞 원소 수(ZSET 에 없으면 — Redis 재기동 — 같은 대기 상태 중 먼저 만든 잡 수로 근사), 예상 시간 `eta_sec` = 시작까지 기다리는 시간 = ahead × 최근 완료 20건의 `finished_at - started_at` 중앙값(완료분이 없으면 null. 화면 문구 '앞에 N건 · 약 M분' 은 기다리는 시간이라 내 잡의 실행 시간은 더하지 않는다 — spec §6-3 '중앙값 × 순번').

- **넣고 빼는 곳:** approve·retry 는 전이에 성공하고 status 를 알린 뒤, **브로커에 넣기 전에** `mark_waiting`, 브로커에 못 넣어 되돌릴 때 `unmark`. 취소는 성공한 뒤 `unmark`(approved·queued 에서 취소한 잡은 워커가 집지 않는다). 워커는 `_run_deep_research` 에서 집기를 시도한 직후(집었든 못 집었든) `unmark`. 회수기가 failed 로 둔 잡을 빼는 `unmark_many_sync` 는 여기서 만들고 부르는 것은 Task 10 이다.
- **넣는 순서(계약 §7):** `mark_waiting` 은 전이·상태 알림 뒤, `_enqueue` **앞**이다. enqueue 뒤에 넣으면 바로 집은 워커의 `unmark` 가 먼저 돌고 그 뒤에 ZADD 가 들어가 그 잡이 줄에 영영 남는다(뒤 잡의 순번이 하나씩 밀린다). 브로커에 못 넣으면 되돌리기 때 `unmark` 로 뺀다. 테스트 `test_approve_marks_the_job_before_it_is_enqueued` 가 이 순서를 고정한다.
- **계약과 다른 점(`_queue_info` 의 상태 인자):** 계약 §7 의 `_queue_info(db, job)` 에 비공개 키워드 `status: str | None = None` 을 더한다(없으면 `job.status`). approve·retry 의 `job` 은 전이 **전에** 읽은 객체라 상태가 아직 awaiting_approval·failed 다. 그렇다고 `job.status = STATUS_APPROVED` 처럼 ORM 객체에 대입하면 그 객체가 dirty 가 되어, 다음 조회의 autoflush(AsyncSessionLocal 은 autoflush 기본값 True)가 `UPDATE research_jobs SET status=… WHERE id=…` 를 기대 상태 조건 없이 보낸다 — 전이 커밋 뒤 끼어든 취소가 쓴 canceled 를 덮을 수 있고, 커밋하지 않으니 요청이 끝날 때까지 행 잠금을 쥔다. 그래서 대입하지 않고 전이한 상태를 인자로 넘긴다. GET·스냅샷·하트비트는 지금 읽은 잡이라 인자 없이 부른다.
- **실패 처리:** 순번은 안내일 뿐이라 Redis 실패를 삼키고 로그만 남긴다(`rank_of` 는 None → created_at 근사). 응답 없는 Redis 에 잡 조회(GET)·승인이 묶이지 않게 소켓 타임아웃 2초(`REDIS_TIMEOUT`)를 `from_url` 키워드로 준다 — URL 에 이미 있는 값은 redis-py 가 키워드보다 앞세운다(relay `_with_timeouts` 와 같은 뜻). redis 는 함수 안에서 import 한다(함정 13 — 로컬 venv·테스트 수집에 redis 가 없다). 비동기 클라이언트는 호출마다 만들고 닫는다(relay 와 같은 까닭).
- **API:** approve·retry 응답에 `"queue"` — 승인 직후 화면이 첫 하트비트(15초)를 기다리지 않고 순번을 보인다(계약 §7, Task 13 이 `res.queue` 를 view 에 반영한다). `mark_waiting` 바로 뒤, `_enqueue` **앞에서** 센다 — 워커가 아직 잡을 집을 수 없어 줄이 정확하다(넣은 뒤에 세면 바로 집은 워커의 running 이 자기 앞으로 세어진다). 브로커에 못 넣으면 그 값은 버리고 503 이다. `GET /api/research/{id}` 응답에 `"queue"`(대기 중이 아니면 null). 스트림 스냅샷의 `job` 에 `"queue"`(대기 중일 때만 — 다른 상태의 스냅샷 모양은 그대로). 하트비트마다 DB 상태가 approved·queued 면 다시 세어, 화면이 마지막으로 받은 값과 다를 때만 `{"kind": "queue", "ahead": n, "eta_sec": s}` 를 보낸다(종료 검사 뒤, '바뀐 것 없음 → continue' 앞). 하트비트의 재계산은 `_job_status` 처럼 짧은 세션(`_queue_now`)을 연다.
- **테스트:** `test_research_api.py` 의 redis 는 MagicMock 이라 `api` 픽스처가 `mark_waiting`·`unmark`·`rank_of` 를 대역으로 바꾸고(`api.line.calls`·`api.line.ranks`), `test_research_tasks.py` 의 `_patch_pipeline` 이 `unmark` 를 기록용으로 바꾼다. run_queue 는 클라이언트 생성기(`_async_client`·`_sync_client`)를 대역으로 바꿔 보낸 명령을 확인하고, 순수 함수 셋은 직접 부른다. approve·retry 응답의 순번은 `TestQueueInResponse` 가 고정한다 — `send_task` 대역이 워커처럼 곧바로 running 으로 바꾸고 줄에서 빼, 브로커에 넣기 전에 세는지 본다(넣은 뒤에 세면 ahead 가 1 로 나온다).

**Files:**
- Create: `app/services/research/run_queue.py`
- Create: `app/tests/test_research_run_queue.py`
- Modify: `app/api/research.py` (Task 6 뒤 기준: relay import 42-45행, `_BROWSER_ACTIVE_MESSAGE` 76행, approve 의 알림·큐 넣기·응답 271-279행, retry 314-321행, cancel 335-337행, `get_research` 373-385행, `_snapshot` 395-400행, `stream_research` 434-436·449-454·465-467행, 파일 끝 `_fresh_snapshot` 500-507행)
- Modify: `app/workers/research_tasks.py` (124c481 기준: import 31-32행, `_run_deep_research` 575-578행)
- Modify: `app/tests/test_research_api.py` (Task 6 뒤 기준: import 15행, `_matches` 48-50행, `_FakeDB.execute` 의 브라우저 조회 분기, `_Api` 162-169행, `api` 픽스처 230-236행, `TestLoaderIsolation` 앞 971-976행 — Task 2 의 15행이 없으면 956-961행)
- Modify: `app/tests/test_research_tasks.py` (124c481 기준: `_Harness.drops` 248-249행, `_patch_pipeline` 의 `_drop_stale_previews` 297-298행·patch 목록 313-316행, `TestClaim` 끝 463-466행 — Task 2 가 이 파일의 critic 대역을 고친 뒤라 줄 번호가 밀렸으면 내용으로 찾는다)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_run_queue.py` 새 파일:

```python
"""test_research_run_queue.py — 딥리서치 대기 순번(Redis ZSET research:run_queue)

run_queue 는 redis 를 함수 안에서만 import 한다 — 로컬 venv 에 redis 가 없어도 이 파일이
수집된다. Redis 를 부르는 함수는 클라이언트 생성기(_async_client·_sync_client)를 대역으로
바꿔 보낸 명령을 기록하고, 순번·예상 시간 계산은 순수 함수라 직접 부른다.
"""
import asyncio
import sys
import types
import uuid

import pytest

from services.research import run_queue


class _FakeAsyncRedis:
    def __init__(self, *, fail: Exception | None = None, rank=None):
        self.calls: list[tuple] = []
        self.closed = 0
        self.fail = fail
        self.rank = rank

    async def zadd(self, key, mapping, nx=False):
        self.calls.append(("zadd", key, mapping, nx))
        if self.fail:
            raise self.fail

    async def zrem(self, key, *members):
        self.calls.append(("zrem", key, members))
        if self.fail:
            raise self.fail

    async def zrank(self, key, member):
        self.calls.append(("zrank", key, member))
        if self.fail:
            raise self.fail
        return self.rank

    async def aclose(self):
        self.closed += 1


class _FakeSyncRedis:
    def __init__(self, *, fail: Exception | None = None):
        self.calls: list[tuple] = []
        self.closed = 0
        self.fail = fail

    def zrem(self, key, *members):
        self.calls.append(("zrem", key, members))
        if self.fail:
            raise self.fail

    def close(self):
        self.closed += 1


def _use(monkeypatch, client) -> None:
    monkeypatch.setattr(run_queue, "_async_client", lambda: client)


class TestMarkWaiting:
    def test_adds_the_job_with_the_time_it_entered_the_line(self, monkeypatch):
        client = _FakeAsyncRedis()
        _use(monkeypatch, client)
        monkeypatch.setattr(run_queue, "_now", lambda: 1_790_000_000.5)
        jid = uuid.uuid4()

        asyncio.run(run_queue.mark_waiting(jid))

        # NX — 재전송된 승인이 자리를 뒤로 미루지 않는다
        assert client.calls == [("zadd", "research:run_queue", {str(jid): 1_790_000_000.5}, True)]
        assert client.closed == 1

    def test_redis_failure_is_swallowed_and_the_client_closed(self, monkeypatch, caplog):
        client = _FakeAsyncRedis(fail=ConnectionError("redis down"))
        _use(monkeypatch, client)

        asyncio.run(run_queue.mark_waiting(uuid.uuid4()))       # 예외가 나오지 않는다

        assert client.closed == 1
        assert any("redis down" in r.getMessage() for r in caplog.records)

    def test_client_creation_failure_is_swallowed(self, monkeypatch):
        def _broken():
            raise ConnectionError("no route")

        monkeypatch.setattr(run_queue, "_async_client", _broken)
        asyncio.run(run_queue.mark_waiting(uuid.uuid4()))


class TestUnmark:
    def test_removes_the_job(self, monkeypatch):
        client = _FakeAsyncRedis()
        _use(monkeypatch, client)
        jid = uuid.uuid4()

        asyncio.run(run_queue.unmark(jid))

        assert client.calls == [("zrem", "research:run_queue", (str(jid),))]
        assert client.closed == 1

    def test_redis_failure_is_swallowed(self, monkeypatch):
        client = _FakeAsyncRedis(fail=ConnectionError("redis down"))
        _use(monkeypatch, client)

        asyncio.run(run_queue.unmark(uuid.uuid4()))

        assert client.closed == 1


class TestRankOf:
    def test_returns_the_number_of_jobs_ahead_in_the_line(self, monkeypatch):
        client = _FakeAsyncRedis(rank=2)
        _use(monkeypatch, client)
        jid = uuid.uuid4()

        assert asyncio.run(run_queue.rank_of(jid)) == 2
        assert client.calls == [("zrank", "research:run_queue", str(jid))]
        assert client.closed == 1

    def test_job_not_in_the_line_is_none(self, monkeypatch):
        _use(monkeypatch, _FakeAsyncRedis(rank=None))
        assert asyncio.run(run_queue.rank_of(uuid.uuid4())) is None

    def test_redis_failure_is_none(self, monkeypatch):
        """Redis 가 죽어도 잡 조회는 돈다 — 순번만 created_at 순 근사로 물러난다."""
        _use(monkeypatch, _FakeAsyncRedis(fail=ConnectionError("redis down")))
        assert asyncio.run(run_queue.rank_of(uuid.uuid4())) is None


class TestUnmarkManySync:
    def test_removes_all_given_jobs_in_one_command(self, monkeypatch):
        client = _FakeSyncRedis()
        monkeypatch.setattr(run_queue, "_sync_client", lambda: client)
        a, b = uuid.uuid4(), uuid.uuid4()

        run_queue.unmark_many_sync([a, str(b)])

        assert client.calls == [("zrem", "research:run_queue", (str(a), str(b)))]
        assert client.closed == 1

    def test_nothing_to_remove_does_not_connect(self, monkeypatch):
        def _never():
            raise AssertionError("빈 목록에 연결했다")

        monkeypatch.setattr(run_queue, "_sync_client", _never)
        run_queue.unmark_many_sync([])

    def test_redis_failure_is_swallowed(self, monkeypatch):
        client = _FakeSyncRedis(fail=ConnectionError("redis down"))
        monkeypatch.setattr(run_queue, "_sync_client", lambda: client)

        run_queue.unmark_many_sync([uuid.uuid4()])

        assert client.closed == 1


class TestClients:
    """응답 없는 Redis 는 예외가 아니라 무기한 대기다 — 잡 조회(GET)가 거기에 묶이면 안 된다."""

    def test_async_client_has_socket_timeouts(self, monkeypatch):
        seen = {}
        aioredis = types.ModuleType("redis.asyncio")
        aioredis.from_url = lambda url, **kw: seen.update(url=url, **kw) or "client"
        redis_mod = types.ModuleType("redis")
        redis_mod.asyncio = aioredis
        monkeypatch.setitem(sys.modules, "redis", redis_mod)
        monkeypatch.setitem(sys.modules, "redis.asyncio", aioredis)

        assert run_queue._async_client() == "client"
        assert seen["socket_timeout"] == seen["socket_connect_timeout"] == run_queue.REDIS_TIMEOUT
        assert seen["url"] == run_queue.get_settings().REDIS_URL

    def test_sync_client_has_socket_timeouts(self, monkeypatch):
        seen = {}

        class _Redis:
            @classmethod
            def from_url(cls, url, **kw):
                seen.update(url=url, **kw)
                return "client"

        redis_mod = types.ModuleType("redis")
        redis_mod.Redis = _Redis
        monkeypatch.setitem(sys.modules, "redis", redis_mod)

        assert run_queue._sync_client() == "client"
        assert seen["socket_timeout"] == seen["socket_connect_timeout"] == run_queue.REDIS_TIMEOUT


class TestWaitingAhead:
    def test_running_jobs_plus_rank(self):
        assert run_queue.waiting_ahead(1, 2, fallback_ahead=7) == 3

    def test_rank_zero_is_a_real_rank(self):
        assert run_queue.waiting_ahead(0, 0, fallback_ahead=5) == 0

    def test_missing_rank_uses_the_created_at_fallback(self):
        assert run_queue.waiting_ahead(1, None, fallback_ahead=4) == 5


class TestEta:
    """예상 시간은 시작까지 기다리는 시간이다 — 화면 문구 '앞에 N건 · 약 M분'."""

    @pytest.mark.parametrize("ahead, median, expected", [
        (0, 100.0, 0),          # 바로 다음 차례 — 기다릴 앞 잡이 없다
        (2, 100.0, 200),        # 내 잡의 실행 시간은 더하지 않는다
        (1, 90.6, 91),          # 버리지 않고 반올림
    ])
    def test_ahead_times_median(self, ahead, median, expected):
        assert run_queue.eta_seconds(ahead, median) == expected

    def test_no_median_means_no_eta(self):
        assert run_queue.eta_seconds(3, None) is None


class TestMedian:
    def test_odd_and_even(self):
        assert run_queue.median_seconds([300.0, 100.0, 200.0]) == 200.0
        assert run_queue.median_seconds([100.0, 200.0, 300.0, 400.0]) == 250.0

    def test_empty_is_none(self):
        assert run_queue.median_seconds([]) is None

    def test_negative_durations_are_ignored(self):
        """시계가 어긋난 행(finished < started)이 중앙값을 끌어내리지 않는다."""
        assert run_queue.median_seconds([-50.0, 120.0]) == 120.0
        assert run_queue.median_seconds([-1.0]) is None
```

`app/tests/test_research_api.py` 바꾸기 ①: `timedelta` import. old:

```python
from datetime import datetime, timezone
from types import SimpleNamespace
```

new:

```python
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
```

`app/tests/test_research_api.py` 바꾸기 ②: `_matches` 가 `<` 를 평가한다(Task 6 이 더한 `ne` 바로 아래). old:

```python
    if op is operators.ne:
        return left != right
    if op is operators.in_op:
```

new:

```python
    if op is operators.ne:
        return left != right
    if op is operators.lt:
        return left is not None and left < right        # SQL 처럼 NULL 비교는 거짓
    if op is operators.in_op:
```

`app/tests/test_research_api.py` 바꾸기 ③: 최근 완료분 소요 시간 조회(Task 6 이 더한 브라우저 조회 분기 바로 아래). old:

```python
        if sql.startswith("SELECT research_jobs.id \nFROM research_jobs") and "LIMIT" in sql:
            ids = [row["id"] for row in self.jobs.values() if _matches(stmt.whereclause, row)]
            return _Result(scalar=ids[0] if ids else None)
```

new:

```python
        if sql.startswith("SELECT research_jobs.id \nFROM research_jobs") and "LIMIT" in sql:
            ids = [row["id"] for row in self.jobs.values() if _matches(stmt.whereclause, row)]
            return _Result(scalar=ids[0] if ids else None)
        if sql.startswith("SELECT research_jobs.started_at, research_jobs.finished_at"):
            # 최근 완료분 소요 시간 — 끝난 시각 내림차순으로 LIMIT 개
            done = sorted((row for row in self.jobs.values() if _matches(stmt.whereclause, row)),
                          key=lambda row: row["finished_at"], reverse=True)
            return _Result(rows=[(row["started_at"], row["finished_at"])
                                 for row in done[:stmt._limit]])
```

`app/tests/test_research_api.py` 바꾸기 ④: `_Api` 가 대기 줄 대역을 든다. old:

```python
class _Api:
    def __init__(self, client, db, celery, published, research, events):
        self.client = client
        self.db = db
        self.celery = celery
        self.published = published
        self.research = research
        self.events = events
```

new:

```python
class _Api:
    def __init__(self, client, db, celery, published, research, events, line):
        self.client = client
        self.db = db
        self.celery = celery
        self.published = published
        self.research = research
        self.events = events
        self.line = line            # 대기 순번 ZSET 대역 — calls 에 넣고 뺀 기록, ranks 에 순위
```

`app/tests/test_research_api.py` 바꾸기 ⑤: `api` 픽스처가 대기 줄 세 함수를 대역으로 바꾼다. old:

```python
    monkeypatch.setattr(research, "publish", _publish)

    db = _FakeDB()
    app = FastAPI()
    app.include_router(research.router)
    app.dependency_overrides[get_db] = lambda: db
    return _Api(TestClient(app), db, celery, published, research, events)
```

new:

```python
    monkeypatch.setattr(research, "publish", _publish)

    # 대기 순번 ZSET — 이 파일의 redis 는 MagicMock 이라 대역 없이 부르면 await 가 깨진다
    line = SimpleNamespace(calls=[], ranks={})

    async def _mark_waiting(job_id):
        line.calls.append(("mark", job_id))

    async def _unmark(job_id):
        line.calls.append(("unmark", job_id))

    async def _rank_of(job_id):
        return line.ranks.get(job_id)

    monkeypatch.setattr(research, "mark_waiting", _mark_waiting)
    monkeypatch.setattr(research, "unmark", _unmark)
    monkeypatch.setattr(research, "rank_of", _rank_of)

    db = _FakeDB()
    app = FastAPI()
    app.include_router(research.router)
    app.dependency_overrides[get_db] = lambda: db
    return _Api(TestClient(app), db, celery, published, research, events, line)
```

`app/tests/test_research_api.py` 바꾸기 ⑥: `TestLoaderIsolation` 앞에 세 클래스를 둔다(Task 6 의 `_SID` 를 쓴다). old:

```python
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 503
        assert api.announced() == [("status", {"status": "queued", "stage": "explored"})]
        assert api.published == [(jid, "failed", "종합 실패")]


class TestLoaderIsolation:
```

new:

```python
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 503
        assert api.announced() == [("status", {"status": "queued", "stage": "explored"})]
        assert api.published == [(jid, "failed", "종합 실패")]


class TestWaitLine:
    """실행 큐에 들어간 잡은 대기 순번 ZSET 에 들어가고, 나오면 빠진다."""

    def test_approve_marks_the_job_before_it_is_enqueued(self, api):
        """큐에 넣은 뒤에 넣으면, 바로 집은 워커가 먼저 뺀 뒤에 들어가 줄에 영영 남는다."""
        jid = api.db.add_job(status="awaiting_approval", stage="planned", plan=["가설 A"])
        at_send = []
        send = api.celery.send_task

        def _send(name, args=None, **kw):
            at_send.append(list(api.line.calls))
            return send(name, args, **kw)

        api.celery.send_task = _send
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200

        assert at_send == [[("mark", jid)]]
        assert api.line.calls == [("mark", jid)]

    def test_retry_marks_the_job(self, api):
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored", last_error="종합 실패")
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 200
        assert api.line.calls == [("mark", jid)]

    @pytest.mark.parametrize("action, status", [("approve", "awaiting_approval"), ("retry", "failed")])
    def test_broker_failure_takes_the_job_out_again(self, api, action, status):
        jid = api.db.add_job(status=status, plan=["가"], last_error="종합 실패")
        api.celery.fail = True

        res = api.client.post(f"/api/research/{jid}/{action}")

        assert res.status_code == 503
        assert "queue" not in res.json()            # 세어 둔 순번은 버린다
        assert api.line.calls == [("mark", jid), ("unmark", jid)]

    def test_rejected_requests_do_not_touch_the_line(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"], created_by=_SID)
        limited = api.db.add_job(status="awaiting_approval", plan=["가"], created_by=_SID)
        wrong = api.db.add_job(status="planning")

        assert api.client.post(f"/api/research/{limited}/approve").status_code == 429
        assert api.client.post(f"/api/research/{wrong}/approve").status_code == 409
        assert api.line.calls == []

    def test_cancel_takes_the_job_out(self, api):
        """approved·queued 에서 취소한 잡은 워커가 집지 않는다 — 여기서 빼지 않으면 줄에 남는다."""
        jid = api.db.add_job(status="queued", plan=["가"])
        assert api.client.post(f"/api/research/{jid}/cancel").status_code == 200
        assert api.line.calls == [("unmark", jid)]

    def test_rejected_cancel_does_not_touch_the_line(self, api):
        jid = api.db.add_job(status="completed")
        assert api.client.post(f"/api/research/{jid}/cancel").status_code == 409
        assert api.line.calls == []


_T0 = datetime(2026, 10, 2, 9, 0, 0, tzinfo=timezone.utc)


def _completed(api, minutes: float, *, finished_minute: int) -> None:
    """최근 완료분 — started_at 부터 minutes 분 걸려 finished_minute 분에 끝난 잡."""
    finished = _T0.replace(minute=finished_minute)
    api.db.add_job(status="completed", plan=["가"], finished_at=finished,
                   started_at=finished - timedelta(minutes=minutes))


class TestQueueInfo:
    """기다리는 잡(approved·queued)의 순번 = running 수 + 줄에서 내 앞, 예상 시간(시작까지
    기다리는 시간) = 순번 × 최근 완료분 소요 시간 중앙값."""

    def test_waiting_job_reports_ahead_and_eta(self, api):
        api.db.add_job(status="running", plan=["가"])
        for minutes, end in ((1, 10), (2, 20), (3, 30)):
            _completed(api, minutes, finished_minute=end)
        jid = api.db.add_job(status="approved", plan=["가"], created_at=_T0)
        api.line.ranks[jid] = 1

        body = api.client.get(f"/api/research/{jid}").json()

        # 앞에 running 1 + 줄 1 = 2, 시작까지 2 × 중앙값 120초
        assert body["queue"] == {"ahead": 2, "eta_sec": 240}

    def test_median_uses_only_the_latest_twenty_runs(self, api):
        for i in range(20):
            _completed(api, 1, finished_minute=30 + i)          # 최근 20건: 60초
        for i in range(25):
            _completed(api, 50, finished_minute=i + 1)          # 오래된 25건: 3000초 — 섞이면 중앙값이 3000
        jid = api.db.add_job(status="queued", plan=["가"], created_at=_T0)
        api.line.ranks[jid] = 1                                 # 앞에 1건 — 0 이면 중앙값과 상관없이 0초다

        assert api.client.get(f"/api/research/{jid}").json()["queue"] == {"ahead": 1, "eta_sec": 60}

    def test_without_the_line_it_falls_back_to_created_at_order(self, api):
        """Redis 가 재기동돼 줄이 비면 먼저 만든 대기 잡 수로 근사한다."""
        api.db.add_job(status="approved", plan=["가"], created_at=_T0.replace(minute=1))
        api.db.add_job(status="queued", plan=["가"], created_at=_T0.replace(minute=2))
        api.db.add_job(status="approved", plan=["가"], created_at=_T0.replace(minute=9))
        api.db.add_job(status="awaiting_approval", plan=["가"], created_at=_T0.replace(minute=3))
        jid = api.db.add_job(status="queued", plan=["가"], created_at=_T0.replace(minute=5))

        # 완료분이 없으면 예상 시간은 비운다
        assert api.client.get(f"/api/research/{jid}").json()["queue"] == {"ahead": 2, "eta_sec": None}

    @pytest.mark.parametrize("status", ["awaiting_approval", "running", "completed", "failed"])
    def test_jobs_not_waiting_have_no_queue(self, api, status):
        jid = api.db.add_job(status=status, plan=["가"], created_at=_T0)
        api.line.ranks[jid] = 0
        assert api.client.get(f"/api/research/{jid}").json()["queue"] is None


class TestQueueInResponse:
    """approve·retry 응답에도 순번을 싣는다 — 승인한 화면이 첫 하트비트(15초)를 기다리지 않는다."""

    def test_approve_response_carries_the_queue(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"])
        for minutes, end in ((1, 10), (2, 20), (3, 30)):
            _completed(api, minutes, finished_minute=end)
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_at=_T0)
        api.line.ranks[jid] = 1

        res = api.client.post(f"/api/research/{jid}/approve")

        assert res.status_code == 200
        # 앞에 running 1 + 줄 1 = 2, 시작까지 2 × 중앙값 120초
        assert res.json()["queue"] == {"ahead": 2, "eta_sec": 240}

    def test_retry_response_carries_the_queue(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"])
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             last_error="종합 실패", created_at=_T0)
        api.line.ranks[jid] = 0

        res = api.client.post(f"/api/research/{jid}/retry")

        assert res.status_code == 200
        assert res.json()["queue"] == {"ahead": 1, "eta_sec": None}

    def test_queue_is_counted_before_the_worker_can_claim(self, api):
        """브로커에 넣은 뒤에 세면, 바로 집은 워커가 쓴 running(자기 자신)이 앞 잡으로 세어진다."""
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"], created_at=_T0)
        api.line.ranks[jid] = 0
        send = api.celery.send_task

        def _send(name, args=None, **kw):
            send(name, args, **kw)
            api.db.jobs[jid]["status"] = "running"      # 워커가 곧바로 집고
            api.line.ranks.pop(jid)                     # 대기 줄에서 뺐다

        api.celery.send_task = _send
        res = api.client.post(f"/api/research/{jid}/approve")

        assert res.status_code == 200
        assert res.json()["queue"] == {"ahead": 0, "eta_sec": None}


class TestQueueEvents:
    """기다리는 잡의 스트림은 스냅샷에 순번을 싣고, 하트비트 때 다시 세어 바뀌었을 때만
    queue 이벤트를 보낸다."""

    def _stream(self, api, monkeypatch, *, status: str, live) -> list[dict]:
        jid = api.db.add_job(status=status, stage="planned", plan=["가"], created_at=_T0)

        async def _subscribe(job_id):
            for item in live:
                if callable(item):
                    item(jid)
                    continue
                yield item

        async def _job_status(job_uuid):
            row = api.db.jobs[job_uuid]
            return row["status"], row["stage"], row["last_error"], bool(row["plan"])

        class _Session:
            async def __aenter__(self):
                return api.db

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        monkeypatch.setattr(api.research, "_job_status", _job_status)
        monkeypatch.setattr(api.research, "AsyncSessionLocal", _Session)
        return _frames(api.client.get(f"/api/research/{jid}/stream").text)

    def _rank(self, api, rank: int):
        def step(jid):
            api.line.ranks[jid] = rank
        return step

    def test_snapshot_carries_the_queue_while_waiting(self, api, monkeypatch):
        api.db.add_job(status="approved", plan=["가"], created_at=_T0.replace(minute=0, second=1))
        api.db.add_job(status="approved", plan=["가"], created_at=_T0.replace(hour=8))

        frames = self._stream(api, monkeypatch, status="approved", live=[_CANCELED])

        # 줄에 없으면(순위 None) 먼저 만든 대기 잡 수로 근사한다 — 08시 잡 1건이 앞
        assert frames[0]["job"]["queue"] == {"ahead": 1, "eta_sec": None}

    def test_snapshot_leaves_the_queue_out_when_not_waiting(self, api, monkeypatch):
        frames = self._stream(api, monkeypatch, status="running", live=[_CANCELED])
        assert "queue" not in frames[0]["job"]

    def test_heartbeat_sends_queue_only_when_it_changes(self, api, monkeypatch):
        api.db.add_job(status="running", plan=["가"])
        frames = self._stream(
            api, monkeypatch, status="queued",
            live=[None, self._rank(api, 1), None, None, self._rank(api, 0), None, _CANCELED],
        )

        assert [f["kind"] for f in frames] == ["snapshot", "queue", "queue", "canceled"]
        assert frames[0]["job"]["queue"] == {"ahead": 1, "eta_sec": None}
        assert frames[1] == {"kind": "queue", "ahead": 2, "eta_sec": None}
        assert frames[2] == {"kind": "queue", "ahead": 1, "eta_sec": None}

    def test_terminal_state_wins_over_the_queue(self, api, monkeypatch):
        def canceled(jid):
            api.db.jobs[jid]["status"] = "canceled"
            api.line.ranks[jid] = 3

        frames = self._stream(api, monkeypatch, status="approved", live=[canceled, None])

        assert [f["kind"] for f in frames] == ["snapshot", "canceled"]

    def test_running_job_gets_no_queue_events(self, api, monkeypatch):
        def claimed(jid):
            api.db.jobs[jid]["status"] = "running"

        frames = self._stream(
            api, monkeypatch, status="approved",
            live=[claimed, {"kind": "status", "status": "running", "stage": "planned"},
                  None, _CANCELED],
        )

        assert [f["kind"] for f in frames] == ["snapshot", "status", "canceled"]


class TestLoaderIsolation:
```

`app/tests/test_research_tasks.py` 바꾸기 ①: `_Harness` 가 뺀 잡을 기록한다. old:

```python
        # (단계, 그때까지 나간 종료 이벤트) — 이전 시도의 초안 정리
        self.drops: list[tuple] = []
```

new:

```python
        # (단계, 그때까지 나간 종료 이벤트) — 이전 시도의 초안 정리
        self.drops: list[tuple] = []
        # 대기 순번 ZSET 에서 뺀 잡
        self.unmarked: list = []
```

`app/tests/test_research_tasks.py` 바꾸기 ②: `_patch_pipeline` 안 기록용 `unmark`. old:

```python
    async def _drop_stale_previews(db, step):
        h.drops.append((step, _terminals(h)))
```

new:

```python
    async def _drop_stale_previews(db, step):
        h.drops.append((step, _terminals(h)))

    async def _unmark(job_id):
        h.unmarked.append(job_id)
```

`app/tests/test_research_tasks.py` 바꾸기 ③: patch 목록에 더한다. old:

```python
        ("_save_progress", _save_progress), ("_drop_stale_previews", _drop_stale_previews),
    ):
        monkeypatch.setattr(rt, name, fn)
    return h
```

new:

```python
        ("_save_progress", _save_progress), ("_drop_stale_previews", _drop_stale_previews),
        ("unmark", _unmark),
    ):
        monkeypatch.setattr(rt, name, fn)
    return h
```

`app/tests/test_research_tasks.py` 바꾸기 ④: `TestClaim` 끝(`test_run_claims_only_statuses_the_api_writes` 뒤)에 둘을 더한다. old:

```python
        from models.research import STATUS_APPROVED, STATUS_QUEUED
        assert STATUS_APPROVED in seen["allowed"]
        assert STATUS_QUEUED in seen["allowed"]
        assert seen["to"] == "running"
```

new:

```python
        from models.research import STATUS_APPROVED, STATUS_QUEUED
        assert STATUS_APPROVED in seen["allowed"]
        assert STATUS_QUEUED in seen["allowed"]
        assert seen["to"] == "running"

    def test_claimed_job_leaves_the_wait_line_right_after_the_claim(self, monkeypatch):
        """집은 잡은 더 이상 기다리는 잡이 아니다 — 뒤 잡의 순번에서 빠져야 한다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        explored = []
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=[])
        order = []
        claim = rt._claim

        async def _claim(db, job_id, *, allowed, to):
            order.append(("claim", list(h.unmarked)))
            return await claim(db, job_id, allowed=allowed, to=to)

        monkeypatch.setattr(rt, "_claim", _claim)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert order == [("claim", [])]          # 집기 전에는 빼지 않는다
        assert h.unmarked == [job.id]
        assert explored == ["계획 하위1"]

    def test_unclaimed_job_also_leaves_the_wait_line(self, monkeypatch):
        """재배달·취소로 못 집은 잡도 줄에 남기지 않는다 — 남으면 뒤 잡의 순번이 하나씩 밀린다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"], status="canceled")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "skipped"
        assert h.unmarked == [job.id]
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_run_queue.py -q -p no:cacheprovider`
Expected: `1 error` — 수집 단계 `ImportError: cannot import name 'run_queue' from 'services.research'`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_api.py -q -p no:cacheprovider`
Expected: `108 errors, 2 passed` — 픽스처의 `AttributeError: <module 'api.research' ...> has no attribute 'mark_waiting'`(Task 6 뒤 88 + 새 22 중 픽스처를 쓰지 않는 `TestLoaderIsolation` 2건만 통과)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider`
Expected: `_patch_pipeline` 을 쓰는 테스트가 모두 `AttributeError: <module 'workers.research_tasks' ...> has no attribute 'unmark'` 로 실패 — 검증 사본에서 `59 failed, 37 passed`(기준선 94 + 새 2 — Task 2·3 은 이 파일의 테스트 수를 바꾸지 않는다)

- [ ] **Step 3: 구현한다**

`app/services/research/run_queue.py` 새 파일:

```python
"""run_queue.py — 딥리서치 대기 순번 (Redis ZSET research:run_queue)

research_jobs 에는 승인 시각 칼럼이 없다. 실행 큐에 들어간 순서를 ZSET(member = 잡 id,
score = 넣은 시각)으로 따로 들고, 순번 = running 잡 수 + ZSET 에서 내 앞 원소 수로 센다.

- 넣기: approve·retry 가 전이에 성공한 뒤, 브로커에 넣기 **전**(넣은 뒤면 바로 집은 워커가
  먼저 빼고 그 뒤에 들어가 줄에 영영 남는다). 브로커에 못 넣으면 뺀다.
- 빼기: 워커가 집기를 시도한 직후(집었든 못 집었든), 취소, 회수기가 failed 로 둔 잡.
- ZSET 이 비었으면(Redis 재기동) 호출부가 created_at 순으로 근사한다.

Redis 실패는 삼킨다 — 순번은 안내일 뿐이라 승인·조회·실행을 막으면 안 된다.
redis 는 함수 안에서 import 한다(로컬 venv·테스트 수집에 redis 가 없다 — 함정 13).
비동기 클라이언트는 호출마다 만들고 닫는다(relay.publish 와 같은 까닭 — Celery 태스크는
잡마다 asyncio.run 으로 이벤트 루프를 새로 연다).
"""
import logging
import statistics
import time

from core.config import get_settings

log = logging.getLogger(__name__)

RUN_QUEUE_KEY = "research:run_queue"

# 응답 없는 Redis 는 예외가 아니라 무기한 대기다. 잡 조회(GET)·승인이 거기 묶이지 않게
# 소켓 타임아웃을 건다. URL 에 이미 있는 값은 redis-py 가 키워드 인자보다 앞세운다.
REDIS_TIMEOUT = 2.0


def _now() -> float:
    return time.time()


def _async_client():
    import redis.asyncio as aioredis

    return aioredis.from_url(
        get_settings().REDIS_URL,
        socket_connect_timeout=REDIS_TIMEOUT, socket_timeout=REDIS_TIMEOUT,
    )


def _sync_client():
    import redis

    return redis.Redis.from_url(
        get_settings().REDIS_URL,
        socket_connect_timeout=REDIS_TIMEOUT, socket_timeout=REDIS_TIMEOUT,
    )


async def mark_waiting(job_id) -> None:
    """줄 끝에 넣는다. NX — 이미 있으면 처음 넣은 시각(자리)을 지킨다."""
    try:
        client = _async_client()
        try:
            await client.zadd(RUN_QUEUE_KEY, {str(job_id): _now()}, nx=True)
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:run_queue] 대기 줄에 넣지 못했다 job=%s: %s", job_id, e)


async def unmark(job_id) -> None:
    try:
        client = _async_client()
        try:
            await client.zrem(RUN_QUEUE_KEY, str(job_id))
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:run_queue] 대기 줄에서 빼지 못했다 job=%s: %s", job_id, e)


async def rank_of(job_id) -> int | None:
    """줄에서 내 앞 원소 수(0 부터). 줄에 없거나 Redis 가 실패하면 None."""
    try:
        client = _async_client()
        try:
            rank = await client.zrank(RUN_QUEUE_KEY, str(job_id))
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:run_queue] 순번을 읽지 못했다 job=%s: %s", job_id, e)
        return None
    return int(rank) if rank is not None else None


def unmark_many_sync(job_ids: list[str]) -> None:
    """회수기(동기 Celery 태스크)용 — 회수해 failed 로 둔 잡을 한 번에 뺀다."""
    if not job_ids:
        return
    try:
        client = _sync_client()
        try:
            client.zrem(RUN_QUEUE_KEY, *[str(j) for j in job_ids])
        finally:
            client.close()
    except Exception as e:
        log.warning("[research:run_queue] 회수한 잡을 대기 줄에서 빼지 못했다 n=%d: %s",
                    len(job_ids), e)


def waiting_ahead(running: int, rank: int | None, fallback_ahead: int) -> int:
    """앞에 있는 잡 수 = running + (ZSET 순위, 없으면 created_at 순 근사)."""
    return max(0, running) + max(0, rank if rank is not None else fallback_ahead)


def eta_seconds(ahead: int, median_run_seconds: float | None) -> int | None:
    """시작까지 기다리는 시간 = ahead × 중앙값(화면 문구 '앞에 N건 · 약 M분' 은 기다리는 시간이다).
    중앙값이 없으면 None. 반올림 int."""
    if median_run_seconds is None:
        return None
    return int(round(ahead * median_run_seconds))


def median_seconds(durations: list[float]) -> float | None:
    """소요 시간 중앙값. 음수(시계가 어긋난 행)는 버리고, 남은 것이 없으면 None."""
    values = [d for d in durations if d >= 0]
    if not values:
        return None
    return float(statistics.median(values))
```

`app/api/research.py` 바꾸기 ①: run_queue import. old:

```python
from services.research.relay import (
    TERMINAL_KIND, publish, publish_terminal, subscribe, terminal_event,
)
from services.research.state import merge_params
```

new:

```python
from services.research.relay import (
    TERMINAL_KIND, publish, publish_terminal, subscribe, terminal_event,
)
from services.research.run_queue import (
    eta_seconds, mark_waiting, median_seconds, rank_of, unmark, waiting_ahead,
)
from services.research.state import merge_params
```

`app/api/research.py` 바꾸기 ②: 예상 시간의 기준 건수(Task 6 이 더한 상수 바로 아래). old:

```python
_BROWSER_ACTIVE_MESSAGE = "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요"
```

new:

```python
_BROWSER_ACTIVE_MESSAGE = "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요"
# 예상 대기 시간의 기준 — 최근 완료분 몇 건의 소요 시간 중앙값을 쓰는가
RECENT_RUNS = 20
```

`app/api/research.py` 바꾸기 ③: approve — 브로커에 넣기 전에 줄에 넣고 순번을 세며, 못 넣으면 줄에서 빼고 순번은 버린다. 응답에 `queue`. old:

```python
    # 큐에 넣기 전에 알린다. 넣은 뒤에 알리면 워커가 먼저 집어 낸 running 뒤에
    # approved 가 도착해 화면이 한 단계 뒤로 간다.
    await _announce(jid, STATUS_APPROVED, job.stage)
    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_APPROVED,),
                          status="awaiting_approval", plan=old_plan)
        await _announce(jid, "awaiting_approval", job.stage)
        raise _broker_unavailable()
    return {"job_id": str(jid), "status": STATUS_APPROVED, "plan": plan}
```

new:

```python
    # 큐에 넣기 전에 알린다. 넣은 뒤에 알리면 워커가 먼저 집어 낸 running 뒤에
    # approved 가 도착해 화면이 한 단계 뒤로 간다. 대기 줄도 같은 까닭으로 먼저 넣는다 —
    # 넣은 뒤면 바로 집은 워커가 먼저 빼고 그 뒤에 들어가 줄에 영영 남는다.
    await _announce(jid, STATUS_APPROVED, job.stage)
    await mark_waiting(jid)
    # 응답에 실을 순번도 넣기 전에 센다 — 넣은 뒤면 바로 집은 워커의 running 이 자기 앞으로
    # 세어진다. job 은 전이 전에 읽은 객체라 상태를 인자로 넘긴다(대입하면 autoflush 가 쓴다).
    queue = await _queue_info(db, job, status=STATUS_APPROVED)
    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_APPROVED,),
                          status="awaiting_approval", plan=old_plan)
        await unmark(jid)
        await _announce(jid, "awaiting_approval", job.stage)
        raise _broker_unavailable()
    return {"job_id": str(jid), "status": STATUS_APPROVED, "plan": plan, "queue": queue}
```

`app/api/research.py` 바꾸기 ④: retry 도 같다. old:

```python
    # 큐에 넣기 전에 알리는 이유는 approve 와 같다
    await _announce(jid, STATUS_QUEUED, job.stage)
    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_QUEUED,), status="failed",
                          last_error=old_error, finished_at=old_finished)
        await publish_terminal(jid, "failed", old_error)
        raise _broker_unavailable()
    return {"job_id": str(jid), "status": STATUS_QUEUED, "stage": job.stage}
```

new:

```python
    # 큐에 넣기 전에 알리고 대기 줄에 넣고 순번을 세는 이유는 approve 와 같다
    await _announce(jid, STATUS_QUEUED, job.stage)
    await mark_waiting(jid)
    queue = await _queue_info(db, job, status=STATUS_QUEUED)
    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_QUEUED,), status="failed",
                          last_error=old_error, finished_at=old_finished)
        await unmark(jid)
        await publish_terminal(jid, "failed", old_error)
        raise _broker_unavailable()
    return {"job_id": str(jid), "status": STATUS_QUEUED, "stage": job.stage, "queue": queue}
```

`app/api/research.py` 바꾸기 ⑤: cancel 이 성공하면 줄에서 뺀다. old:

```python
        await _get_job(db, jid)
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태입니다")
    # 워커가 없는 상태(승인 대기 등)에서 취소하면 종료 이벤트를 낼 주체가 없다 —
```

new:

```python
        await _get_job(db, jid)
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태입니다")
    # approved·queued 에서 취소한 잡은 워커가 집지 않는다 — 여기서 빼지 않으면 줄에 남아
    # 뒤 잡의 순번을 하나씩 민다. 다른 상태면 줄에 없어 아무 일도 없다.
    await unmark(jid)
    # 워커가 없는 상태(승인 대기 등)에서 취소하면 종료 이벤트를 낼 주체가 없다 —
```

`app/api/research.py` 바꾸기 ⑥: `get_research` 앞에 순번 계산 둘, 응답에 `queue`. old:

```python
@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, _job_uuid(job_id))
    # created_by 는 싣지 않는다. 이 조회에는 소유 확인이 없어 링크만 알면 누구나 여는데,
    # 남의 브라우저 ID 가 나가면 그걸 헤더에 넣어 그 사람의 기록을 읽을 수 있다.
    return {
        "job_id": str(job.id), "question": job.question, "status": job.status,
        "stage": job.stage, "plan": job.plan, "report": job.report,
        "last_error": job.last_error, "params": job.params,
        "created_at": _iso(job.created_at), "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
        "steps": await _steps(db, job.id),
    }
```

new:

```python
async def _recent_run_seconds(db: AsyncSession) -> list[float]:
    """최근 완료분 RECENT_RUNS 건의 실행 소요 시간(finished_at - started_at, 초)."""
    rows = (await db.execute(
        select(ResearchJob.started_at, ResearchJob.finished_at)
        .where(ResearchJob.status == "completed",
               ResearchJob.started_at.is_not(None),
               ResearchJob.finished_at.is_not(None))
        .order_by(ResearchJob.finished_at.desc())
        .limit(RECENT_RUNS)
    )).all()
    return [(finished - started).total_seconds() for started, finished in rows]


async def _queue_info(db: AsyncSession, job, *, status: str | None = None) -> dict | None:
    """기다리는 잡(approved·queued)의 대기 순번과 예상 시간. 그 밖의 상태면 None.

    ahead = running 잡 수 + 대기 줄(ZSET)에서 내 앞 원소 수. 줄에 없으면(Redis 재기동)
    같은 대기 상태 중 먼저 만든 잡 수로 근사한다. eta_sec = 시작까지 기다리는 시간 =
    ahead × 최근 완료분 소요 시간 중앙값 — 완료분이 없으면 None.

    status 는 approve·retry 가 넘긴다 — 그 job 은 전이 전에 읽은 객체라 상태가 옛 값인데,
    ORM 객체에 대입하면 다음 조회의 autoflush 가 그 값을 조건 없이 써 버린다.
    """
    if (job.status if status is None else status) not in RUNNABLE_STATUSES:
        return None
    running = (await db.execute(
        select(func.count()).select_from(ResearchJob).where(ResearchJob.status == "running")
    )).scalar_one()
    rank = await rank_of(job.id)
    fallback = 0
    if rank is None and job.created_at is not None:
        fallback = (await db.execute(
            select(func.count()).select_from(ResearchJob)
            .where(ResearchJob.status.in_(RUNNABLE_STATUSES),
                   ResearchJob.created_at < job.created_at)
        )).scalar_one()
    ahead = waiting_ahead(running, rank, fallback)
    median = median_seconds(await _recent_run_seconds(db))
    return {"ahead": ahead, "eta_sec": eta_seconds(ahead, median)}


@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, _job_uuid(job_id))
    # created_by 는 싣지 않는다. 이 조회에는 소유 확인이 없어 링크만 알면 누구나 여는데,
    # 남의 브라우저 ID 가 나가면 그걸 헤더에 넣어 그 사람의 기록을 읽을 수 있다.
    return {
        "job_id": str(job.id), "question": job.question, "status": job.status,
        "stage": job.stage, "plan": job.plan, "report": job.report,
        "last_error": job.last_error, "params": job.params,
        "created_at": _iso(job.created_at), "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
        "steps": await _steps(db, job.id),
        "queue": await _queue_info(db, job),
    }
```

`app/api/research.py` 바꾸기 ⑦: 스냅샷의 `job` 에 순번(대기 중일 때만). old:

```python
    steps = await _steps(db, job.id)
    job_state = {"status": job.status, "stage": job.stage, "plan": job.plan}
    counters = _live_counters(steps, job.report)
    if counters is not None:
        job_state["counters"] = counters
    return {"kind": "snapshot", "steps": steps, "job": job_state}
```

new:

```python
    steps = await _steps(db, job.id)
    job_state = {"status": job.status, "stage": job.stage, "plan": job.plan}
    counters = _live_counters(steps, job.report)
    if counters is not None:
        job_state["counters"] = counters
    queue = await _queue_info(db, job)
    if queue is not None:
        job_state["queue"] = queue
    return {"kind": "snapshot", "steps": steps, "job": job_state}
```

`app/api/research.py` 바꾸기 ⑧: 스트림이 화면이 아는 순번을 기억한다. old:

```python
        # 화면이 지금 아는 상태와 계획 유무 — 하트비트가 DB 와 견줄 기준이다
        last, plan_sent = (job_status, job_stage), _plan_known(snapshot)
        async for event in subscribe(str(jid)):
```

new:

```python
        # 화면이 지금 아는 상태와 계획 유무 — 하트비트가 DB 와 견줄 기준이다
        last, plan_sent = (job_status, job_stage), _plan_known(snapshot)
        # 화면이 지금 아는 대기 순번 — 하트비트가 다시 세어 바뀌었을 때만 queue 를 보낸다
        last_queue = snapshot["job"].get("queue")
        async for event in subscribe(str(jid)):
```

`app/api/research.py` 바꾸기 ⑨: 하트비트 — 종료 검사 뒤, '바뀐 것 없음' 앞에서 순번을 다시 센다. old:

```python
                status, stage, error, has_plan = current
                if status in TERMINAL_STATUSES:
                    yield _sse(terminal_event(status, error))
                    return
                if (status, stage) == last and (plan_sent or not has_plan):
                    continue
```

new:

```python
                status, stage, error, has_plan = current
                if status in TERMINAL_STATUSES:
                    yield _sse(terminal_event(status, error))
                    return
                if status in RUNNABLE_STATUSES:
                    queue = await _queue_now(jid)
                    if queue is not None and queue != last_queue:
                        last_queue = queue
                        yield _sse({"kind": "queue", **queue})
                if (status, stage) == last and (plan_sent or not has_plan):
                    continue
```

`app/api/research.py` 바꾸기 ⑩: 스냅샷을 다시 보내면 그 순번이 기준이 된다. old:

```python
                last, plan_sent = (status, stage), _plan_known(snap)
                yield _sse(snap)
                continue
```

new:

```python
                last, plan_sent = (status, stage), _plan_known(snap)
                last_queue = snap["job"].get("queue")
                yield _sse(snap)
                continue
```

`app/api/research.py` 바꾸기 ⑪: 파일 끝 `_fresh_snapshot` 뒤에 하트비트용 짧은 세션. old:

```python
    async with AsyncSessionLocal() as db:
        job = await db.get(ResearchJob, jid)
        if job is None:
            return None
        return await _snapshot(db, job), job.last_error
```

new:

```python
    async with AsyncSessionLocal() as db:
        job = await db.get(ResearchJob, jid)
        if job is None:
            return None
        return await _snapshot(db, job), job.last_error


async def _queue_now(jid: uuid.UUID) -> dict | None:
    """하트비트 때 다시 센 대기 순번. 짧은 세션을 새로 여는 이유는 _job_status 와 같다."""
    async with AsyncSessionLocal() as db:
        job = await db.get(ResearchJob, jid)
        return None if job is None else await _queue_info(db, job)
```

`app/workers/research_tasks.py` 바꾸기 ①: import. old:

```python
from services.research.relay import publish, publish_terminal
from services.research.runner import explore_subquestion
```

new:

```python
from services.research.relay import publish, publish_terminal
from services.research.run_queue import unmark
from services.research.runner import explore_subquestion
```

`app/workers/research_tasks.py` 바꾸기 ②: 집기를 시도한 직후 줄에서 뺀다. old:

```python
            # 재개 가능한 상태만 받는다. running 인 잡을 다시 받으면 재배달이다.
            if not await _claim(db, jid, allowed=RUNNABLE_STATUSES, to="running"):
                log.warning("[research] 이미 처리 중이거나 처리된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}
```

new:

```python
            # 재개 가능한 상태만 받는다. running 인 잡을 다시 받으면 재배달이다.
            claimed = await _claim(db, jid, allowed=RUNNABLE_STATUSES, to="running")
            # 집었든 못 집었든 이제 기다리는 잡이 아니다 — 대기 줄에 남으면 뒤 잡의 순번이 밀린다
            await unmark(jid)
            if not claimed:
                log.warning("[research] 이미 처리 중이거나 처리된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}
```

(`_claim` 은 `_transition` 이 커밋하고 돌아오므로 `unmark` 의 Redis 호출 동안 열린 트랜잭션이 없다.)

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_run_queue.py -q -p no:cacheprovider`
Expected: `23 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_api.py -q -p no:cacheprovider`
Expected: `110 passed` (Task 6 뒤 88 + 새 22)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider`
Expected: 실패 0 — 검증 사본에서 `96 passed`(기준선 94 + 새 2)

관련 묶음:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_run_queue.py tests/test_research_api.py tests/test_research_tasks.py tests/test_research_relay.py tests/test_research_models.py tests/test_celery_schedule.py -q -p no:cacheprovider`
Expected: 실패 0 (검증 사본에서 `258 passed`)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`
Expected: 실패 0, 수집 오류 3(기준선과 같음). Task 6 뒤 전체 수치 + 47 passed(run_queue 23 + API 22 + 워커 2). 검증 사본에서 `1436 passed, 1 skipped`.

- [ ] **Step 5: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a add app/services/research/run_queue.py app/tests/test_research_run_queue.py app/api/research.py app/workers/research_tasks.py app/tests/test_research_api.py app/tests/test_research_tasks.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a commit -m "[Feat] round06a — 딥리서치 대기 순번: 실행 큐에 들어간 잡을 Redis ZSET research:run_queue 에 넣은 시각으로 줄 세운다(approve·retry 는 브로커에 넣기 전에 넣고 못 넣으면 빼며, 워커는 집기를 시도한 직후·취소는 성공 직후 뺀다). 순번 = running 수 + 줄에서 내 앞(줄에 없으면 먼저 만든 대기 잡 수), 예상 시간 = 시작까지 기다리는 시간 = 순번 × 최근 완료 20건 소요 시간 중앙값. approve·retry 응답의 queue(브로커에 넣기 전에 센다), GET /{id} 의 queue, 스냅샷 job.queue(대기 중일 때만), 하트비트마다 다시 세어 바뀌었을 때만 queue 이벤트를 보낸다. Redis 실패는 삼키고 소켓 타임아웃은 2초"
```

---


### Task 8: 연구 어시스턴트 생성 서비스 — 모델 라우팅·재시도 규칙·핵심 개념 실행기

**왜:** spec §5-2(핵심 개념)·§6-3(재시도·넘김 공통 규칙, 모델 라우팅). 생성 1건을 어느 모델에 몇 번 묻고 끝내 못 얻으면 무엇으로 닫는지를 kind 와 무관한 한 함수(`run_generation`)에 모은다. 06a 는 kind=concepts 실행기 하나로 디스패처(Task 9)·API(Task 11)까지 끝까지 검증하고, 06b·06c 는 `EXECUTORS` 에 실행기만 더한다. 이 작업은 DB·Celery·Redis 를 쓰지 않는 순수 서비스다.

**Files:**
- Create: `app/services/research_work/__init__.py`
- Create: `app/services/research_work/routing.py`
- Create: `app/services/research_work/generate.py`
- Create: `app/services/research_work/concepts.py`
- Create: `app/services/research_work/executors.py`
- Create: `app/domains/nl_library/prompts/research_concepts.yaml`
- Test: `app/tests/test_research_work_generate.py` (새 파일)
- Test: `app/tests/test_research_work_concepts.py` (새 파일)

**알아 둘 것:**
- Task 1(`models.research_work.GEN_KINDS`)과 Task 5(`chat_full` 의 `base_url`·`model` 키워드) 위에서 돈다. Task 1 이 없으면 새 테스트가 수집 단계에서 ImportError 로 멈춘다. Task 5 가 없어도 테스트는 가짜 `chat_fn` 이라 통과하지만 운영에서 `chat_full` 이 `base_url`·`model` 을 몰라 TypeError 가 난다 — Task 5 를 먼저 넣는다.
- **모델 라우팅(`WORK_MODEL_ROUTES`):** concepts·topic_card·refine·facet → Qwen(`VLM_BASE_URL`·`VLM_MODEL`), outline·section·paragraph → gemma(`LLM_BASE_URL`·`LLM_MODEL`). 두 설정은 compose `x-common-env` 에 이미 있어 모든 워커가 받는다. `endpoint()` 는 부를 때마다 설정을 읽는다. 딥리서치의 계획·critic·종합은 이 라우팅을 거치지 않는다.
- **재시도·넘김 규칙(`run_generation`, 생성 1건 = `chat_fn` 최대 3회):**

  | 경우 | 호출 순서 | 결과 |
  |---|---|---|
  | 첫 답이 해석·검사 통과 | 주 | 그 답 |
  | 해석 실패(`parse` 가 None) 또는 검사 미달(`check` 가 False) 한 번 | 주 → 주 | 두 번째 답 |
  | 해석·검사 실패 두 번 | 주 → 주 → 다른 | 다른 모델의 답, 그것도 실패면 `empty(input)` |
  | 전송 실패(`httpx.HTTPError`) | 주 → 다른 | 곧바로 넘긴다. 다른 모델도 실패하면 `empty(input)` — 다른 모델에는 한 번만 묻는다(호출 2회로 끝) |
  | 해석 실패 뒤 전송 실패 | 주 → 주 → 다른 | 다른 모델의 답, 그것도 실패면 `empty(input)` |

  전송 실패는 `chat_full` 이 자기 재시도(`LLM_RETRY_ATTEMPTS`)와 남은 시간을 다 쓰고 포기한 뒤 올린 예외다 — 그 재시도는 이 3회에 세지 않는다. 그 밖의 예외(코드 결함)는 빈 결과로 덮지 않고 그대로 올린다(Task 9 디스패처가 failed 로 닫는다). 빈 결과면 `model` 은 None, 시도마다 `attempts` 에 `{"model", "outcome", "error"?}` 를 남긴다(spec §6-3 공개 부록). 모든 호출은 `timeout=CALL_TIMEOUT`(300초)을 명시한다.
- **함정 15:** 개념의 개수·중복은 모델에 맡기지 않고 코드가 정한다(`clean_concepts` — 문자열만, 공백 정리, 1~40자, 대소문자·공백 무시 중복 제거, 앞에서 5개). 프롬프트에는 JSON 키와 개수 범위(2~5)만 적고 개수 예시·분야 예시는 넣지 않는다. 출력 형식도 말로만 적는다 — `{"concepts": ["<핵심 개념>"]}` 같은 견본은 원소가 1개인 배열이라 모델이 그 개수를 따라 개념 1개만 내고(함정 15의 '절 1개·논문 1편'과 같은 모양), 그러면 검사(2개 이상)에서 떨어져 세 번 다 쓰고 빈 결과로 끝난다. 가짜 LLM 단위 테스트로는 드러나지 않으므로 `TestPrompt` 가 프롬프트에 대괄호(배열 견본)가 없는지 본다. 40자를 넘는 항목은 자르지 않고 버린다. `clean_concepts` 는 Task 11 의 `PATCH .../work`(사용자 칩)도 쓴다.
- 프롬프트 변수는 `question`·`subquestions`·`headings` 셋이다. 두 목록은 `- ` 로 시작하는 줄 목록 문자열로 넘기고 비면 `(없음)` 이다. 테스트가 템플릿의 변수 집합을 고정한다(jinja2 `meta.find_undeclared_variables`).
- Qwen 경로에 `VLM_THINK`(`chat_template_kwargs`)를 싣지 않는다 — 지금 Qwen3-VL-8B-Instruct 는 비추론 모델이고, `llm_client` 의 openai 경로도 gemma 에 `LLM_THINK` 를 싣지 않는다.
- `services/` 는 `__init__.py` 없는 이름공간 패키지이고 `services/research/` 는 빈 `__init__.py` 를 둔다. 새 `services/research_work/` 도 `__init__.py` 를 둔다(설명 docstring 만).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_work_generate.py` (새 파일, 전체):

```python
"""services/research_work — 생성의 모델 라우팅(routing)과 재시도·넘김 공통 규칙(generate).

LLM 은 부르지 않는다. run_generation 에 넘기는 chat_fn 을 대본대로 답하는 가짜로 바꿔(모델 이름마다
응답이나 전송 실패를 차례로 꺼낸다) 호출 순서·모델·시도 기록을 확인한다(spec §6-3).
"""
import asyncio
import json

import httpx
import pytest

from models.research_work import GEN_KINDS
from services.llm_client import LLMResult
from services.research_work import routing
from services.research_work.generate import (
    CALL_TIMEOUT, MAX_CALLS, Executor, GenerationResult, run_generation,
)
from services.research_work.routing import GEMMA, QWEN, WORK_MODEL_ROUTES, endpoint, other

OK = '{"ok": true}'
NOT_JSON = "JSON 이 아닌 답"
THIN = '{"ok": false}'
MESSAGES = [{"role": "system", "content": "시스템"}, {"role": "user", "content": "사용자"}]
PARAMS = {"max_tokens": 50, "temperature": 0.2}


@pytest.fixture
def cfg(monkeypatch):
    settings = routing.get_settings()
    monkeypatch.setattr(settings, "VLM_BASE_URL", "http://qwen.test/v1")
    monkeypatch.setattr(settings, "VLM_MODEL", "qwen-test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://gemma.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    return settings


def _parse(raw: str) -> dict | None:
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _executor(kind: str = "concepts", built: list | None = None) -> Executor:
    def _build(inp: dict) -> tuple[list[dict], dict]:
        if built is not None:
            built.append(inp)
        return MESSAGES, dict(PARAMS)

    return Executor(
        kind=kind, build=_build, parse=_parse,
        check=lambda out: out.get("ok") is True,
        empty=lambda inp: {"empty": True, "q": inp["q"]},
    )


class _ScriptedChat:
    """모델 이름마다 응답 문자열이나 예외를 차례로 꺼낸다. calls 에 호출 인자를 쌓는다."""

    def __init__(self, script: dict[str, list]):
        self.script = {model: list(items) for model, items in script.items()}
        self.calls: list[dict] = []

    async def __call__(self, messages, *, params=None, timeout=120.0, base_url=None, model=None):
        self.calls.append({"messages": messages, "params": params, "timeout": timeout,
                           "base_url": base_url, "model": model})
        item = self.script[model].pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(content=item, finish_reason="stop")

    @property
    def models(self) -> list[str]:
        return [c["model"] for c in self.calls]


def _run(chat: _ScriptedChat, *, kind: str = "concepts", built: list | None = None) -> GenerationResult:
    return asyncio.run(run_generation(_executor(kind, built), {"q": "질문"}, chat_fn=chat))


def _outcomes(result: GenerationResult) -> list[str]:
    return [a["outcome"] for a in result.attempts]


def _unavailable() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://gemma.test/v1/chat/completions")
    return httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))


class TestRouting:
    def test_every_generation_kind_has_a_route(self):
        assert set(WORK_MODEL_ROUTES) == set(GEN_KINDS)

    def test_reading_side_goes_to_qwen_and_writing_side_to_gemma(self):
        assert {k for k, v in WORK_MODEL_ROUTES.items() if v == QWEN} == {
            "concepts", "topic_card", "refine", "facet",
        }
        assert {k for k, v in WORK_MODEL_ROUTES.items() if v == GEMMA} == {
            "outline", "section", "paragraph",
        }

    def test_endpoint_reads_settings_at_call_time(self, cfg):
        assert endpoint(QWEN) == ("http://qwen.test/v1", "qwen-test")
        assert endpoint(GEMMA) == ("http://gemma.test/v1", "gemma-test")

    def test_other_is_the_fallback_model(self):
        assert other(QWEN) == GEMMA and other(GEMMA) == QWEN

    @pytest.mark.parametrize("fn", [endpoint, other])
    def test_unknown_name_is_rejected(self, fn):
        with pytest.raises(ValueError):
            fn("llama")


class TestRunGeneration:
    def test_limits(self):
        assert (CALL_TIMEOUT, MAX_CALLS) == (300.0, 3)

    def test_first_good_answer_is_the_result(self, cfg):
        chat = _ScriptedChat({"qwen-test": [OK]})

        result = _run(chat)

        assert result == GenerationResult(
            output={"ok": True}, model="qwen-test",
            attempts=[{"model": "qwen-test", "outcome": "ok"}],
        )
        (call,) = chat.calls
        assert call == {"messages": MESSAGES, "params": PARAMS, "timeout": CALL_TIMEOUT,
                        "base_url": "http://qwen.test/v1", "model": "qwen-test"}

    def test_unreadable_answer_asks_the_same_model_once_more(self, cfg):
        chat = _ScriptedChat({"qwen-test": [NOT_JSON, OK]})

        result = _run(chat)

        assert chat.models == ["qwen-test", "qwen-test"]
        assert _outcomes(result) == ["parse", "ok"] and result.model == "qwen-test"

    def test_two_content_failures_hand_over_to_the_other_model(self, cfg):
        built: list = []
        chat = _ScriptedChat({"qwen-test": [NOT_JSON, THIN], "gemma-test": [OK]})

        result = _run(chat, built=built)

        assert chat.models == ["qwen-test", "qwen-test", "gemma-test"]
        assert _outcomes(result) == ["parse", "check", "ok"]
        assert result.output == {"ok": True} and result.model == "gemma-test"
        assert chat.calls[2]["base_url"] == "http://gemma.test/v1"
        # 입력은 한 번만 만들고 세 호출이 같은 메시지를 보낸다
        assert len(built) == 1 and all(c["messages"] is MESSAGES for c in chat.calls)

    def test_transport_failure_hands_over_at_once(self, cfg):
        chat = _ScriptedChat({"qwen-test": [httpx.ConnectError("연결 거부")], "gemma-test": [OK]})

        result = _run(chat)

        assert chat.models == ["qwen-test", "gemma-test"]
        assert result.attempts == [
            {"model": "qwen-test", "outcome": "transport", "error": "ConnectError: 연결 거부"},
            {"model": "gemma-test", "outcome": "ok"},
        ]
        assert result.model == "gemma-test"

    def test_transport_failure_after_a_content_failure_hands_over(self, cfg):
        chat = _ScriptedChat({"qwen-test": [NOT_JSON, httpx.ReadTimeout("읽기 시간 초과")],
                              "gemma-test": [OK]})

        result = _run(chat)

        assert chat.models == ["qwen-test", "qwen-test", "gemma-test"]
        assert _outcomes(result) == ["parse", "transport", "ok"]

    def test_three_failures_give_the_empty_result(self, cfg):
        chat = _ScriptedChat({"qwen-test": [NOT_JSON, NOT_JSON], "gemma-test": [THIN]})

        result = _run(chat)

        assert len(chat.calls) == MAX_CALLS
        assert result.output == {"empty": True, "q": "질문"}
        assert result.model is None
        assert _outcomes(result) == ["parse", "parse", "check"]

    def test_the_other_model_gets_one_call_only(self, cfg):
        chat = _ScriptedChat({"qwen-test": [httpx.ConnectError("거부")], "gemma-test": [NOT_JSON, OK]})

        result = _run(chat)

        assert chat.models == ["qwen-test", "gemma-test"]
        assert result.output == {"empty": True, "q": "질문"} and result.model is None
        assert _outcomes(result) == ["transport", "parse"]

    def test_both_endpoints_down_give_the_empty_result(self, cfg):
        chat = _ScriptedChat({"qwen-test": [httpx.ConnectError("거부")], "gemma-test": [_unavailable()]})

        result = _run(chat)

        assert _outcomes(result) == ["transport", "transport"]
        assert result.attempts[1]["error"].startswith("HTTPStatusError: ")
        assert result.model is None

    def test_gemma_routed_kind_falls_back_to_qwen(self, cfg):
        chat = _ScriptedChat({"gemma-test": [httpx.ConnectError("거부")], "qwen-test": [OK]})

        result = _run(chat, kind="outline")

        assert chat.models == ["gemma-test", "qwen-test"] and result.model == "qwen-test"

    def test_errors_outside_the_transport_propagate(self, cfg):
        """해석·검사·전송 밖의 오류(코드 결함)는 빈 결과로 덮지 않는다 — 디스패처가 failed 로 닫는다."""
        chat = _ScriptedChat({"qwen-test": [ValueError("코드 결함")]})

        with pytest.raises(ValueError):
            _run(chat)
```

`app/tests/test_research_work_concepts.py` (새 파일, 전체):

```python
"""services/research_work/concepts.py — 핵심 개념 생성(kind=concepts)의 입력·프롬프트·해석·검사.

프롬프트는 실제 YAML(research_concepts.yaml)을 렌더한다. LLM 은 부르지 않는다.
"""
import asyncio
from types import SimpleNamespace

import pytest
from jinja2 import Environment, meta

from models.research_work import GEN_KINDS
from services.llm_client import LLMResult
from services.prompts import get_prompt
from services.research_work import routing
from services.research_work.concepts import (
    EXECUTOR, MAX_CONCEPT_LEN, MAX_CONCEPTS, MIN_CONCEPTS, clean_concepts, concepts_input,
)
from services.research_work.executors import EXECUTORS
from services.research_work.generate import run_generation


def _job(**fields) -> SimpleNamespace:
    base = {
        "question": "청소년 독서 격차 연구는 어디까지 왔나",
        "plan": ["독서 격차의 정의", "독서 격차를 줄이는 프로그램"],
        "report": {"sections": [{"heading": "독서 격차의 개념"}, {"heading": "중재 프로그램의 효과"}]},
    }
    return SimpleNamespace(**{**base, **fields})


class TestCleanConcepts:
    def test_limits(self):
        assert (MIN_CONCEPTS, MAX_CONCEPTS, MAX_CONCEPT_LEN) == (2, 5, 40)

    @pytest.mark.parametrize("raw", [None, "독서 격차, 청소년", {"concepts": ["가"]}, 3])
    def test_anything_but_a_list_gives_nothing(self, raw):
        assert clean_concepts(raw) == []

    def test_keeps_strings_and_tidies_spaces(self):
        assert clean_concepts(["  독서   격차 ", 3, None, ["청소년"], "청소년"]) == ["독서 격차", "청소년"]

    def test_drops_empty_and_too_long(self):
        assert clean_concepts(["", "   ", "가" * 41, "나" * 40]) == ["나" * 40]

    def test_duplicates_ignore_case_and_spaces(self):
        assert clean_concepts(["AI 윤리", "ai윤리", "AI  윤리", "교육"]) == ["AI 윤리", "교육"]

    def test_keeps_the_first_five(self):
        raw = ["가", "나", "다", "라", "마", "바", "사"]
        assert clean_concepts(raw) == ["가", "나", "다", "라", "마"]


class TestConceptsInput:
    def test_question_plan_and_section_headings(self):
        assert concepts_input(_job()) == {
            "question": "청소년 독서 격차 연구는 어디까지 왔나",
            "subquestions": ["독서 격차의 정의", "독서 격차를 줄이는 프로그램"],
            "headings": ["독서 격차의 개념", "중재 프로그램의 효과"],
        }

    def test_blank_headings_are_skipped(self):
        job = _job(report={"sections": [{"heading": "  "}, {"intro": "제목 없는 절"}, {"heading": "효과"}]})
        assert concepts_input(job)["headings"] == ["효과"]

    def test_missing_plan_and_report(self):
        out = concepts_input(_job(plan=None, report=None))
        assert out["subquestions"] == [] and out["headings"] == []


class TestPrompt:
    def test_template_reads_only_the_three_inputs(self):
        tpl = get_prompt("research_concepts")
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == {"question", "subquestions", "headings"}
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": 200, "temperature": 0.2}

    def test_build_renders_the_real_template(self):
        messages, params = EXECUTOR.build(concepts_input(_job()))

        assert [m["role"] for m in messages] == ["system", "user"]
        system, user = messages[0]["content"], messages[1]["content"]
        assert "2개 이상 5개 이하" in system and '"concepts"' in system
        assert "원 질문: 청소년 독서 격차 연구는 어디까지 왔나" in user
        assert "- 독서 격차의 정의\n- 독서 격차를 줄이는 프로그램" in user
        assert "- 독서 격차의 개념\n- 중재 프로그램의 효과" in user
        assert params == {"max_tokens": 200, "temperature": 0.2}

    def test_empty_lists_render_as_none(self):
        _, user = (m["content"] for m in EXECUTOR.build(concepts_input(_job(plan=[], report=None)))[0])
        assert user.count("(없음)") == 2

    def test_format_is_described_without_a_sample_list(self):
        """원소가 든 배열 견본({"concepts": ["<핵심 개념>"]})을 두면 모델이 그 개수를 따라 개념 1개만 내
        검사(2개 이상)에서 떨어진다(함정 15). 형식은 말로만 적는다 — 템플릿 어디에도 대괄호가 없다."""
        tpl = get_prompt("research_concepts")
        assert "[" not in tpl.system and "[" not in tpl.user
        assert "문자열" in tpl.system and "배열" in tpl.system


class TestExecutor:
    def test_kind(self):
        assert EXECUTOR.kind == "concepts"

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
        cfg = routing.get_settings()
        monkeypatch.setattr(cfg, "VLM_BASE_URL", "http://qwen.test/v1")
        monkeypatch.setattr(cfg, "VLM_MODEL", "qwen-test")
        answers = ['{"concepts": ["독서 격차"]}', '{"concepts": ["독서 격차", "청소년", "독서 격차"]}']
        seen = []

        async def fake_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            seen.append(model)
            return LLMResult(content=answers.pop(0), finish_reason="stop")

        result = asyncio.run(run_generation(EXECUTOR, concepts_input(_job()), chat_fn=fake_chat))

        assert seen == ["qwen-test", "qwen-test"]
        assert result.output == {"concepts": ["독서 격차", "청소년"]} and result.model == "qwen-test"


class TestExecutors:
    def test_registry_holds_the_06a_executor(self):
        assert EXECUTORS == {"concepts": EXECUTOR}

    def test_keys_are_generation_kinds(self):
        assert all(kind in GEN_KINDS and ex.kind == kind for kind, ex in EXECUTORS.items())
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_generate.py tests/test_research_work_concepts.py -q -p no:cacheprovider`

Expected: `Interrupted: 2 errors during collection` — 두 파일 모두 `ModuleNotFoundError: No module named 'services.research_work'`

- [ ] **Step 3: 구현한다**

`app/services/research_work/__init__.py` (새 파일, 전체):

```python
"""research_work — 연구 어시스턴트(round06): 이어간 연구의 생성(핵심 개념·주제 카드·계획서 …).

생성 1건 = research_generations 1행 = Celery 메시지 1개. 워커는 DB 텍스트 조회와 LLM 호출만 한다
(임베딩이 필요한 입력은 생성을 넣는 FastAPI 가 만든다 — spec §6-3).
"""
```

`app/services/research_work/routing.py` (새 파일, 전체):

```python
"""routing.py — 생성 종류(kind)별 모델 (spec §6-3 모델 라우팅)

읽고 고르는 일(핵심 개념·주제 카드·자식 카드·특징 추출)은 Qwen, 계획서를 쓰는 일(목차·절·문단)은
gemma 다. 딥리서치의 계획·critic·종합은 여기를 거치지 않는다(지금처럼 gemma). Qwen 품질이 모자라면
그 kind 를 GEMMA 로 바꾸는 한 줄로 돌린다(Qwen 표본 확인 — spec §8).
엔드포인트는 호출할 때 설정에서 읽는다 — 테스트·운영 env 가 바꾼 값을 그대로 따른다.
"""
from core.config import get_settings

QWEN, GEMMA = "qwen", "gemma"

WORK_MODEL_ROUTES: dict[str, str] = {
    "concepts": QWEN, "topic_card": QWEN, "refine": QWEN, "facet": QWEN,
    "outline": GEMMA, "section": GEMMA, "paragraph": GEMMA,
}


def endpoint(name: str) -> tuple[str, str]:
    """모델 이름 → (base_url, model). Qwen 은 VLM_*, gemma 는 LLM_* 설정이다."""
    cfg = get_settings()
    if name == QWEN:
        return cfg.VLM_BASE_URL, cfg.VLM_MODEL
    if name == GEMMA:
        return cfg.LLM_BASE_URL, cfg.LLM_MODEL
    raise ValueError(f"알 수 없는 모델 이름: {name!r}")


def other(name: str) -> str:
    """넘길 모델 — 주 모델이 끝내 답하지 못하면 다른 쪽에 한 번 묻는다."""
    if name == QWEN:
        return GEMMA
    if name == GEMMA:
        return QWEN
    raise ValueError(f"알 수 없는 모델 이름: {name!r}")
```

`app/services/research_work/generate.py` (새 파일, 전체):

```python
"""generate.py — 생성 1건의 재시도·넘김 공통 규칙 (spec §6-3)

생성 1건 = chat_full 최대 MAX_CALLS(3)회:
  주 모델(WORK_MODEL_ROUTES[kind]) 1회
  → 해석 실패(parse 가 None)나 내용 검사 미달(check 가 False)이면 주 모델 1회 더
  → 전송 실패(chat_fn 이 httpx.HTTPError 를 올림 — chat_full 이 자기 재시도까지 다 쓰고 포기)면 곧바로,
    해석·내용 미달이 두 번이면 다른 모델 1회
  → 그래도 안 되면 executor.empty(input) — 빈 결과로 done(개념 비움 등). 그때 model 은 None.
chat_full 안의 일시적 실패 재시도는 이 횟수에 세지 않는다. 시도마다 attempts 에 남긴다(공개 부록).
그 밖의 예외(코드 결함)는 그대로 올린다 — 디스패처가 생성을 failed 로 닫는다.
"""
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from services.llm_client import LLMResult
from services.research_work.routing import WORK_MODEL_ROUTES, endpoint, other

log = logging.getLogger(__name__)

# 비스트리밍 호출 하나의 timeout(초). llm_client 기본 120초로는 Qwen 이 OCR 로 꽉 찬 구간에서 줄을
# 서다 끊긴다(spec §6-3 Qwen 자리). 호출 하나의 최악은 이 값 + 연결 10초다(llm_client).
CALL_TIMEOUT = 300.0
MAX_CALLS = 3


@dataclass(frozen=True)
class Executor:
    kind: str
    build: Callable[[dict], tuple[list[dict], dict]]   # input → (messages, llm params)
    parse: Callable[[str], dict | None]                # 원문 → output, 못 읽으면 None
    check: Callable[[dict], bool]                      # 내용 검사(예: 개념 2개 이상)
    empty: Callable[[dict], dict]                      # 끝내 못 얻었을 때의 빈 결과(input → output)


@dataclass
class GenerationResult:
    output: dict
    model: str | None          # 결과를 낸 모델 이름(빈 결과면 None)
    attempts: list[dict]       # [{"model": str, "outcome": "ok"|"parse"|"check"|"transport", "error"?: str}]


ChatFn = Callable[..., Awaitable[LLMResult]]   # chat_full 과 같은 시그니처


async def run_generation(executor: Executor, input: dict, *, chat_fn: ChatFn) -> GenerationResult:
    messages, params = executor.build(input)
    route = WORK_MODEL_ROUTES[executor.kind]
    switched = False
    content_failures = 0
    attempts: list[dict] = []
    for _ in range(MAX_CALLS):
        base_url, model = endpoint(route)
        try:
            reply = await chat_fn(messages, params=params, timeout=CALL_TIMEOUT,
                                  base_url=base_url, model=model)
        except httpx.HTTPError as e:
            error = f"{type(e).__name__}: {e}"[:300]
            log.warning("[research_work] %s 전송 실패 model=%s — %s", executor.kind, model, error)
            attempts.append({"model": model, "outcome": "transport", "error": error})
            if switched:
                break
            route, switched = other(route), True
            continue
        output = executor.parse(reply.content)
        if output is not None and executor.check(output):
            attempts.append({"model": model, "outcome": "ok"})
            return GenerationResult(output=output, model=model, attempts=attempts)
        outcome = "parse" if output is None else "check"
        log.warning("[research_work] %s %s 실패 model=%s", executor.kind, outcome, model)
        attempts.append({"model": model, "outcome": outcome})
        if switched:
            break
        content_failures += 1
        if content_failures >= 2:
            route, switched = other(route), True
    return GenerationResult(output=executor.empty(input), model=None, attempts=attempts)
```

`app/services/research_work/concepts.py` (새 파일, 전체):

```python
"""concepts.py — 핵심 개념 생성(kind=concepts, Qwen) — spec §5-2

입력은 원 질문 + 하위질문(승인된 계획) + 보고서 절 제목, 출력은 원 질문의 핵심 개념 2~5개.
개수·중복은 모델에 맡기지 않고 코드가 자르고 지운다(함정 15). 끝내 2개를 못 얻으면 비운 채
done 이고, 화면은 '핵심 개념 넣기' 입력을 보인다(사용자가 PATCH .../work 로 넣는다).
"""
from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research_work.generate import Executor

MIN_CONCEPTS, MAX_CONCEPTS, MAX_CONCEPT_LEN = 2, 5, 40


def clean_concepts(raw: object) -> list[str]:
    """문자열만, 공백 정리, 1~40자, 대소문자·공백 무시 중복 제거, 앞에서 5개.

    사용자가 고친 칩(PATCH .../work)도 같은 규칙으로 정리한다.
    """
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())
        if not 1 <= len(text) <= MAX_CONCEPT_LEN:
            continue
        key = "".join(text.split()).casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) == MAX_CONCEPTS:
            break
    return out


def concepts_input(job) -> dict:
    """완료된 딥리서치 잡(ResearchJob) → 생성 입력. research_generations.input 에 그대로 담긴다."""
    report = job.report if isinstance(job.report, dict) else {}
    headings = []
    for sec in report.get("sections") or []:
        heading = sec.get("heading") if isinstance(sec, dict) else None
        if isinstance(heading, str) and heading.strip():
            headings.append(heading.strip())
    return {
        "question": job.question,
        "subquestions": [s for s in (job.plan or []) if isinstance(s, str)],
        "headings": headings,
    }


def _lines(items: list[str]) -> str:
    return "\n".join(f"- {s}" for s in items) or "(없음)"


def _build(input: dict) -> tuple[list[dict], dict]:
    system, user, params = get_prompt("research_concepts").render(
        question=input["question"],
        subquestions=_lines(input.get("subquestions") or []),
        headings=_lines(input.get("headings") or []),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


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
)
```

`app/services/research_work/executors.py` (새 파일, 전체):

```python
"""executors.py — 생성 종류(kind) → 실행기. 디스패처가 여기서 고른다.

06a 는 핵심 개념만 있다. 06b·06c 가 주제 카드·자식 카드·특징 추출·목차·절·문단을 더한다.
실행기가 없는 kind 의 생성은 디스패처가 failed 로 닫는다.
"""
from services.research_work import concepts
from services.research_work.generate import Executor

EXECUTORS: dict[str, Executor] = {"concepts": concepts.EXECUTOR}
```

`app/domains/nl_library/prompts/research_concepts.yaml` (새 파일, 전체):

```yaml
parser: plain
params:
  max_tokens: 200
  temperature: 0.2
system: |-
  당신은 국내 학술논문 코퍼스를 다루는 연구 사서입니다.
  연구자의 원 질문에서 핵심 개념을 뽑습니다.

  핵심 개념은 원 질문이 무엇을 연구하려는지 가리키는 짧은 명사구입니다.
  하위질문과 보고서 절 제목은 원 질문을 이해하기 위한 참고 자료입니다. 거기에만 나오고 원 질문의 주제가 아닌 개념은 넣지 마세요.

  규칙:
  - 핵심 개념은 2개 이상 5개 이하입니다.
  - 개념 하나는 40자 이내의 명사구로 씁니다. 문장으로 쓰지 마세요.
  - 같은 개념을 다른 말로 되풀이하지 마세요.
  - 어느 질문에나 붙을 수 있는 일반적인 말만으로 된 개념은 넣지 마세요.
  - 원 질문에 쓰인 말을 살려 씁니다.

  반드시 JSON 객체 하나로만 응답하세요. 설명이나 다른 텍스트는 출력하지 마세요.
  객체의 키는 "concepts" 하나이고, 값은 핵심 개념 문자열들의 배열입니다. 배열에는 2개 이상 5개 이하의 개념을 담습니다.
user: |-
  원 질문: {{ question }}

  하위질문:
  {{ subquestions }}

  보고서 절 제목:
  {{ headings }}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_generate.py tests/test_research_work_concepts.py -q -p no:cacheprovider`

Expected: `43 passed` (generate 17 + concepts 26)

프롬프트 로더·llm_client·모델·critic(같은 프롬프트 디렉터리) 기존 테스트:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_prompts.py tests/test_llm_client.py tests/test_research_work_models.py tests/test_research_critic.py -q -p no:cacheprovider`

Expected: 실패 0 — Task 1~7 을 적용한 검증 사본에서 `183 passed`(8 + 68 + 37 + 70 — critic 70 은 Task 2 뒤 수)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 0, `3 errors`(Task 0 의 수집 오류 셋) 그대로. 이 작업은 43개를 더한다(Task 7 뒤 수 + 43) — Task 1~7 을 적용한 검증 사본(test_research_api.py 110개)에서 `1515 passed` → `1558 passed, 1 skipped, 2 warnings, 3 errors`.

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/services/research_work/__init__.py app/services/research_work/routing.py app/services/research_work/generate.py app/services/research_work/concepts.py app/services/research_work/executors.py app/domains/nl_library/prompts/research_concepts.yaml app/tests/test_research_work_generate.py app/tests/test_research_work_concepts.py && git status --short && git commit -m "[Feat] round06a — 연구 어시스턴트 생성 서비스(services/research_work): kind 별 모델 라우팅(핵심 개념·주제 카드·자식 카드·특징 추출은 Qwen, 목차·절·문단은 gemma), 생성 1건의 재시도·넘김 공통 규칙(chat_full 최대 3회 — 해석·검사 실패면 주 모델 한 번 더, 전송 실패나 두 번째 실패면 다른 모델 한 번, 그래도 안 되면 kind 별 빈 결과로 끝내고 시도 목록을 남긴다), 핵심 개념 실행기(원 질문·하위질문·절 제목 → 개념 2~5개, 개수·중복은 코드가 정리)와 프롬프트 research_concepts 를 더한다. 프롬프트의 출력 형식은 말로만 적고 원소가 든 배열 견본을 두지 않는다 — 모델이 견본의 개수를 베낀다(함정 15)"
```

---


### Task 9: 생성 디스패처·디스패치 태스크·연구 이벤트 채널·결과 적용

**왜:** spec §6-3 '생성 디스패처 — 전체에서 한 번에 1건'·'시간 한도', §6-4 연구 채널. `q_research_plan` 두 자리 중 하나는 늘 딥리서치 계획에 남겨야 한다(D15) — 생성이 두 자리를 채우면 새 딥리서치의 '계획 세우는 중'이 생성 1건 길이만큼 밀린다. 그래서 생성 1건 = Celery 메시지 1개이고, 디스패치 태스크가 전역 잠금 안에서 running 이 없을 때만 queued 하나를 집어 돌린다.

**Files:**
- Create: `app/services/research_work/dispatch.py`
- Create: `app/services/research_work/apply.py`
- Create: `app/workers/research_work_tasks.py`
- Modify: `app/services/research/relay.py` (파일 끝 `subscribe` 의 `finally` 101-104행 뒤에 더한다)
- Modify: `app/workers/celery_app.py` (`include` 15행, `task_routes` 끝 43-44행)
- Modify: `app/tests/test_research_relay.py` (`TestChannel` 117-121행 뒤에 더한다)
- Test: `app/tests/test_research_work_dispatch.py` (새 파일)
- Test: `app/tests/test_research_work_tasks.py` (새 파일)

**알아 둘 것:**
- **흐름(`dispatch_research_work`):** 태스크 단위 async 엔진 → `pick_next`(잠금 → running 수 → 0 이면 queued 하나를 `FOR UPDATE SKIP LOCKED` 로 집어 running·`started_at=now()` → 커밋) → 없으면 `{"status": "idle"}` → `EXECUTORS[kind]` 로 `run_generation(..., chat_fn=chat_full)` 을 `asyncio.timeout(GEN_DEADLINE)` 안에서(이 동안 DB 트랜잭션을 열어 두지 않는다 — `pick_next` 가 커밋하고 돌아왔다) → `apply_result` 와 `finish(done, output={**output, "attempts": [...]}, model)` 를 한 트랜잭션으로 → `publish_work(work_id, "generation", {gen_id, gen_kind, target, status, model, result})` → `has_queued` 면 `send_dispatch()`. 실행기가 없는 kind·예상 밖 예외·데드라인은 `finish(failed, error=…)` 뒤 같은 흐름이다.
- **생성 종류는 `gen_kind` 에 싣는다:** relay 는 이벤트를 `{"kind": kind, **payload}` 로 싣는다(`publish` 와 같은 방식 — `publish_work` 도 같다). 페이로드에 `"kind": "concepts"` 를 두면 이벤트 종류 `"generation"` 을 덮어써 Redis 에 `{"kind": "concepts", "gen_id": …}` 가 나가고, 연구 화면이 생성 이벤트를 알아보지 못한다(spec §6-4 'generation done 을 받으면 work·grid 를 다시 읽는다'가 돌지 않는다). Task 11 의 API 가 보내는 generation 이벤트도 같은 키(`gen_id`·`gen_kind`·`target`·`status`·`model`·`result`)이고, Task 11 의 `TestEventShape` 가 이 워커 소스의 `publish_work(…, "generation", {…})` 를 읽어 키를 맞춘다 — 그래서 generation 이벤트를 보내는 호출은 dict 를 그 자리에 쓴 한 곳뿐이다. `TestDispatch` 의 다른 테스트는 `publish_work` 를 (work_id, kind, payload) 를 따로 적는 가짜로 바꿔 이 덮어쓰기를 못 본다 — `test_generation_event_keeps_its_kind_on_the_work_channel` 만 진짜 `publish_work`(Redis 만 가짜)로 나간 JSON 을 본다.
- **06a 는 끝난 생성만 알린다:** 디스패처가 queued → running 으로 바꿀 때(`pick_next`)는 이벤트를 보내지 않는다(회수기가 failed 로 둘 때도 — Task 10). 06a 화면은 생성 진행을 그리지 않고(Task 11 '생성 대기 순번'), 연구 SSE 는 접속 때 snapshot 으로 DB 를 다시 읽는다(하트비트 때는 읽지 않는다 — 계약 §11). running 이벤트·순번 이벤트는 연구 화면을 만드는 06b 에서 정한다.
- **도는 사이 상태가 바뀐 생성:** 취소 API(Task 11)는 queued 만 canceled 로 바꾸고 running 은 409 로 막는다(running 을 풀면 LLM 호출이 q_research_plan 한 자리를 쥔 채 전역 1건 자리가 비어 두 번째 생성이 계획 자리를 차지한다 — D15). 그래도 회수기가 오래 돈 생성을 failed 로 둘 수 있다. `finish` 는 running 인 행만 바꾸는 조건부 UPDATE 이고, 바뀐 행이 없으면 **롤백**해 같은 트랜잭션의 결과 적용까지 되돌린 뒤 False 를 돌려준다 — 그러면 이벤트도 보내지 않는다(반환 status `"dropped"`). 줄이 남았으면 다음 디스패치는 보낸다.
- **ORM 객체를 들고 다니지 않는다:** `finish` 의 롤백은 세션의 인스턴스를 만료시켜 그 뒤 속성 접근이 async 세션에서 MissingGreenlet 으로 터진다(`research_tasks._StepRef` 와 같은 까닭). 집은 행은 곧바로 값 객체 `_Picked` 로 옮긴다. `pick_next` 는 `UPDATE … RETURNING` 으로 행을 돌려준다 — 커밋 뒤 `db.get` 으로 다시 읽으면 새 트랜잭션이 열린 채 LLM 호출(최대 16분)을 기다리게 된다.
- **큐 문자열 고정:** 태스크 옵션·`celery_app.task_routes`·`send_dispatch` 셋 다 `"q_research_plan"` 이다. 회수기(Task 10)가 도는 celery-control·celery-beat 에는 `RESEARCH_PLAN_QUEUE` env 가 없어 설정값을 따르면 q_llm(적재 워커)으로 떨어진다. 테스트가 `RESEARCH_PLAN_QUEUE=""` 에서 확인한다. beat 일정은 바꾸지 않는다(`test_celery_schedule.py` 그대로).
- **시간 한도(함정 19):** `GEN_DEADLINE = MAX_CALLS × (CALL_TIMEOUT + 10) + 30` = 960초(호출마다 연결 10초까지), soft 1020초·hard 1080초. 소프트 리밋이 `asyncio.run` 밖으로 튀면 새 루프·새 엔진으로 failed 로 닫는다(`research_tasks._run_job` 과 같은 방식). 본문의 `except Exception` 앞에 `except SoftTimeLimitExceeded: raise` 를 둔다(Celery 의 것도 Exception 하위 클래스).
- **연구 채널:** `research:work:{id}`. 연구 id = 출발 딥리서치 잡 id 라 잡 채널 `research:{id}` 와 이름을 갈라 둔다. 기존 `publish`·`subscribe` 는 고치지 않고 같은 방식(호출마다 클라이언트·소켓 타임아웃·실패 삼킴 / 유휴 None)으로 둘을 더한다.
- **결과 적용(`apply_result`):** concepts 이면 `research_works.concepts` 를 바꾸고 `concept_members` 를 비운다(소속은 06c 에서 FastAPI 가 다시 계산). 세 번 다 못 얻은 빈 결과(`{"concepts": []}`)면 연구를 건드리지 않고 `{"concepts": []}` 만 돌려준다 — 빈 결과로 끝난 개념 생성을 사용자가 칩을 넣은 뒤 다시 부르면(Task 11 retry), 또 빈 결과일 때 그 칩과 소속을 아무 결과 없이 지우게 된다. 처음 이어갈 때의 연구는 개념이 빈 채 만들어지므로(Task 11) 그 경우의 모양은 같다. 이벤트의 `result` 는 생성이 낸 값이지 연구의 지금 개념이 아니다(화면은 generation done 을 받으면 연구를 다시 읽는다). 커밋하지 않는다. 06a 에 실행기가 없는 kind 는 `{}` 를 돌려주고 아무것도 하지 않는다.
- **SQLite 대역의 한계:** `FOR UPDATE SKIP LOCKED` 는 SQLite 에서 조용히 빠진다 — 세션이 보낸 문장을 Postgres 로 컴파일해 잠금 → 개수 → 집기 → 전이 → 커밋 순서와 모양을 본다. `pg_advisory_xact_lock` 은 Task 1 이 `make_engine` 에 넣은 빈 함수다. 테스트 세션은 워커처럼 `expire_on_commit=False` 로 연다.
- **실패 시 회복:** `send_dispatch` 가 브로커에 못 넣으면 False 와 로그만 남긴다 — 회수기(Task 10, 10분 주기)가 'queued 가 있는데 running 이 없음'을 보고 다시 보낸다. 워커가 죽어 running 으로 남은 생성은 회수기가 failed 로 둔다.
- **계약과 다른 점:** ① `finish` 는 조건이 맞지 않으면 커밋하지 않고 롤백한다(계약: 조건부 UPDATE → commit) — 결과 적용을 함께 되돌리려고. 또 done·failed 밖의 상태는 ValueError 로 거부한다. ② `pick_next` 는 `db.get` 대신 `UPDATE … RETURNING` 으로 행을 받는다(위). ③ 비공개 이름 `_Picked`·`_dispatch`·`_generate`·`_close`·`_close_timed_out`·`_error_text`·`TIMEOUT_ERROR`·`FINISH_STATUSES`, 태스크 반환 `{"status": "idle"|"timeout"}`·`{"gen_id", "status": "done"|"failed"|"dropped"}`. ④ 태스크 엔진은 `pool_size=2`(한 번에 세션 하나). ⑤ generation 이벤트 페이로드의 생성 종류 키는 `gen_kind` 다(계약 §9: `"kind"` — relay 가 이벤트 종류를 `kind` 에 실어 덮어쓰므로, 위). ⑥ `apply_result` 는 빈 결과면 연구를 바꾸지 않는다(계약 §9: kind=concepts 이면 `concepts = output["concepts"]`·`concept_members = {}` 로 갱신 — 위).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_work_dispatch.py` (새 파일, 전체):

```python
"""services/research_work/dispatch.py·apply.py — 생성 디스패처(전체에서 한 번에 1건)와 결과 적용.

SQLite 대역(history_sqlite)에서 실제 SQL 로 돈다. 잠금(pg_advisory_xact_lock·FOR UPDATE SKIP LOCKED)은
SQLite 가 그리지 않으므로, 세션이 보낸 문장을 Postgres 로 컴파일해 순서와 모양을 본다(spec §6-3).
"""
import asyncio
import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.research_work import ResearchGeneration, ResearchWork
from services.research_work.apply import apply_result
from services.research_work.dispatch import (
    GEN_LOCK, finish, has_queued, pick_next, queue_position,
)

GEN = ResearchGeneration.__table__
WORK = ResearchWork.__table__
T0 = dt.datetime(2026, 10, 2, 9, 0, 0)


class _Recording(AsyncSessionOverSync):
    """보낸 문장을 Postgres 로 컴파일해 순서대로 남기고 COMMIT·ROLLBACK 도 끼워 적는다.
    워커의 세션처럼(expire_on_commit=False) 커밋 뒤에도 읽은 값을 들고 있다."""

    def __init__(self, engine):  # super().__init__ 은 기본 Session(expire_on_commit=True)을 만든다 — 그 자리만 바꾼다
        self._session = Session(engine, expire_on_commit=False)
        self.log: list[str] = []

    async def execute(self, stmt, params=None):
        self.log.append(str(stmt.compile(dialect=postgresql.dialect())))
        return await super().execute(stmt, params)

    async def scalar(self, stmt, params=None):
        self.log.append(str(stmt.compile(dialect=postgresql.dialect())))
        return await super().scalar(stmt, params)

    async def commit(self):
        self.log.append("COMMIT")
        await super().commit()

    async def rollback(self):
        self.log.append("ROLLBACK")
        await super().rollback()


@pytest.fixture
def engine():
    return make_engine()


def _work(engine, **fields):
    job_id = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, job_id, **fields)
    return job_id


def _gen(engine, work_id, *, minute: int, **fields) -> int:
    """created_at 을 T0 + minute 분으로 박은 생성 — 같은 초에 넣은 행끼리의 순서를 정해 둔다."""
    gid = add_generation(engine, work_id, **fields)
    with engine.begin() as conn:
        conn.execute(sa.update(GEN).where(GEN.c.id == gid)
                     .values(created_at=T0 + dt.timedelta(minutes=minute)))
    return gid


def _row(engine, gid: int):
    with engine.connect() as conn:
        return conn.execute(sa.select(GEN).where(GEN.c.id == gid)).mappings().one()


def _work_row(engine, work_id):
    with engine.connect() as conn:
        return conn.execute(sa.select(WORK).where(WORK.c.id == work_id)).mappings().one()


def _call(engine, fn):
    async def _go():
        db = _Recording(engine)
        try:
            return await fn(db), db.log
        finally:
            await db.close()

    return asyncio.run(_go())


class TestLockKey:
    def test_lock_key_fits_a_signed_bigint(self):
        assert GEN_LOCK == int.from_bytes(b"RSWKDISP", "big")
        assert -(2 ** 63) <= GEN_LOCK < 2 ** 63

    def test_lock_key_differs_from_the_research_run_slot_lock(self):
        # api/research.py _RUN_SLOT_LOCK — 같으면 딥리서치 승인과 생성 디스패치가 서로를 기다린다
        assert GEN_LOCK != 0x5245534541524348


class TestPickNext:
    def test_user_generations_first_then_oldest_across_works(self, engine):
        w1, w2 = _work(engine), _work(engine)
        background = _gen(engine, w1, minute=0, priority=0)
        later = _gen(engine, w2, minute=2, priority=10)
        earlier = _gen(engine, w1, minute=1, priority=10)

        gen, _ = _call(engine, pick_next)

        assert gen.id == earlier
        assert (gen.status, gen.work_id) == ("running", w1) and gen.started_at is not None
        assert _row(engine, earlier)["status"] == "running"
        assert [_row(engine, g)["status"] for g in (background, later)] == ["queued", "queued"]

    def test_same_priority_and_time_go_by_id(self, engine):
        w1 = _work(engine)
        first = _gen(engine, w1, minute=0)
        _gen(engine, w1, minute=0)

        gen, _ = _call(engine, pick_next)

        assert gen.id == first

    def test_returns_the_row_with_its_input(self, engine):
        w1 = _work(engine)
        _gen(engine, w1, minute=0, kind="concepts", input={"question": "독서 격차"})

        gen, _ = _call(engine, pick_next)

        assert (gen.kind, gen.input, gen.target) == ("concepts", {"question": "독서 격차"}, None)

    def test_nothing_is_picked_while_any_generation_runs(self, engine):
        w1, w2 = _work(engine), _work(engine)
        _gen(engine, w1, minute=0, status="running", started_at=T0)
        waiting = _gen(engine, w2, minute=1)

        gen, log = _call(engine, pick_next)

        assert gen is None
        assert _row(engine, waiting)["status"] == "queued"
        assert log[-1] == "ROLLBACK" and not any(s.startswith("UPDATE") for s in log)

    def test_nothing_queued_gives_none(self, engine):
        w1 = _work(engine)
        _gen(engine, w1, minute=0, status="done")

        gen, log = _call(engine, pick_next)

        assert gen is None and log[-1] == "ROLLBACK"

    def test_lock_count_and_locked_pick_share_one_transaction(self, engine):
        w1 = _work(engine)
        _gen(engine, w1, minute=0)

        _, log = _call(engine, pick_next)

        lock = next(i for i, s in enumerate(log) if "pg_advisory_xact_lock" in s)
        count = next(i for i, s in enumerate(log) if s.startswith("SELECT count(*)"))
        pick = next(i for i, s in enumerate(log) if "FOR UPDATE SKIP LOCKED" in s)
        upd = next(i for i, s in enumerate(log) if s.startswith("UPDATE research_generations"))
        commit = log.index("COMMIT")
        assert lock < count < pick < upd < commit
        assert not {"COMMIT", "ROLLBACK"} & set(log[lock:upd])
        assert "ORDER BY research_generations.priority DESC, research_generations.created_at, " \
               "research_generations.id" in log[pick]
        assert "LIMIT" in log[pick]


class TestFinish:
    def test_closes_a_running_generation(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0, status="running", started_at=T0)
        output = {"concepts": ["독서 격차", "청소년"], "attempts": [{"model": "qwen-test", "outcome": "ok"}]}

        ok, log = _call(engine, lambda db: finish(db, gid, status="done", output=output,
                                                  model="qwen-test", error=None))

        row = _row(engine, gid)
        assert ok is True and log[-1] == "COMMIT"
        assert (row["status"], row["output"], row["model"], row["error"]) == (
            "done", output, "qwen-test", None)
        assert row["finished_at"] is not None

    def test_failed_keeps_the_error(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0, status="running", started_at=T0)

        ok, _ = _call(engine, lambda db: finish(db, gid, status="failed", output=None, model=None,
                                                error="ValueError: 코드 결함"))

        row = _row(engine, gid)
        assert ok is True
        assert (row["status"], row["output"], row["error"]) == ("failed", None, "ValueError: 코드 결함")

    def test_canceled_generation_is_left_alone(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0, status="canceled", started_at=T0)

        ok, log = _call(engine, lambda db: finish(db, gid, status="done", output={"concepts": []},
                                                  model="qwen-test", error=None))

        row = _row(engine, gid)
        assert ok is False and log[-1] == "ROLLBACK"
        assert (row["status"], row["output"], row["finished_at"]) == ("canceled", None, None)

    def test_a_dropped_finish_undoes_the_applied_result(self, engine):
        """도는 중에 취소된 생성의 결과는 연구에 남지 않는다 — 적용과 닫기가 한 트랜잭션이다."""
        w1 = _work(engine, concepts=["사용자 개념"])
        gid = _gen(engine, w1, minute=0, kind="concepts", status="canceled", started_at=T0)

        async def _apply_then_finish(db):
            gen = await db.get(ResearchGeneration, gid)
            await apply_result(db, gen, {"concepts": ["모델 개념", "다른 개념"]})
            return await finish(db, gid, status="done", output={"concepts": []}, model="m", error=None)

        ok, _ = _call(engine, _apply_then_finish)

        assert ok is False
        assert _work_row(engine, w1)["concepts"] == ["사용자 개념"]

    @pytest.mark.parametrize("status", ["queued", "running", "canceled"])
    def test_only_done_or_failed(self, engine, status):
        with pytest.raises(ValueError):
            _call(engine, lambda db: finish(db, 1, status=status, output=None, model=None, error=None))


class TestQueueState:
    def test_has_queued(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0, status="running", started_at=T0)
        assert _call(engine, has_queued)[0] is False
        _gen(engine, w1, minute=1)
        assert _call(engine, has_queued)[0] is True
        assert _row(engine, gid)["status"] == "running"

    def test_position_counts_queued_ahead_and_the_running_one(self, engine):
        w1, w2 = _work(engine), _work(engine)
        _gen(engine, w1, minute=0, status="running", started_at=T0)
        user_old = _gen(engine, w2, minute=1, priority=10)
        background = _gen(engine, w1, minute=0, priority=0)
        user_new = _gen(engine, w2, minute=2, priority=10)

        async def _positions(db):
            return [await queue_position(db, await db.get(ResearchGeneration, g))
                    for g in (user_old, user_new, background)]

        positions, _ = _call(engine, _positions)

        assert positions == [1, 2, 3]

    def test_position_without_a_running_generation(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0)

        async def _position(db):
            return await queue_position(db, await db.get(ResearchGeneration, gid))

        assert _call(engine, _position)[0] == 0

    def test_running_and_closed_generations_wait_for_nobody(self, engine):
        w1 = _work(engine)
        running = _gen(engine, w1, minute=0, status="running", started_at=T0)
        done = _gen(engine, w1, minute=1, status="done")
        _gen(engine, w1, minute=2)

        async def _positions(db):
            return [await queue_position(db, await db.get(ResearchGeneration, g)) for g in (running, done)]

        assert _call(engine, _positions)[0] == [0, 0]


class TestApplyResult:
    def test_concepts_replace_the_chips_and_reset_membership(self, engine):
        w1 = _work(engine, concepts=["옛 개념"])
        with engine.begin() as conn:
            conn.execute(sa.update(WORK).where(WORK.c.id == w1)
                         .values(concept_members={"옛 개념": ["C1"]}))
        gid = _gen(engine, w1, minute=0, kind="concepts", status="running", started_at=T0)

        async def _apply(db):
            gen = await db.get(ResearchGeneration, gid)
            payload = await apply_result(db, gen, {"concepts": ["독서 격차", "청소년"]})
            await db.commit()
            return payload

        payload, log = _call(engine, _apply)

        row = _work_row(engine, w1)
        assert payload == {"concepts": ["독서 격차", "청소년"]}
        assert (row["concepts"], row["concept_members"]) == (["독서 격차", "청소년"], {})
        assert log.count("COMMIT") == 1          # 적용은 커밋하지 않는다 — 위 커밋은 테스트가 했다

    def test_an_empty_result_keeps_the_chips(self, engine):
        """세 번 다 못 얻은 빈 결과는 사용자가 넣어 둔 칩·소속을 지우지 않는다(빈 결과를 다시 부른 경우)."""
        w1 = _work(engine, concepts=["사용자 개념"])
        with engine.begin() as conn:
            conn.execute(sa.update(WORK).where(WORK.c.id == w1)
                         .values(concept_members={"사용자 개념": ["C1"]}))
        gid = _gen(engine, w1, minute=0, kind="concepts", status="running", started_at=T0)

        async def _apply(db):
            return await apply_result(db, await db.get(ResearchGeneration, gid), {"concepts": []})

        payload, log = _call(engine, _apply)

        row = _work_row(engine, w1)
        assert payload == {"concepts": []} and log == []
        assert (row["concepts"], row["concept_members"]) == (["사용자 개념"], {"사용자 개념": ["C1"]})

    def test_kinds_without_an_06a_effect_change_nothing(self, engine):
        w1 = _work(engine, concepts=["독서 격차"])
        gid = _gen(engine, w1, minute=0, kind="outline", status="running", started_at=T0)

        async def _apply(db):
            return await apply_result(db, await db.get(ResearchGeneration, gid), {"outline": {}})

        payload, log = _call(engine, _apply)

        assert payload == {} and log == []
        assert _work_row(engine, w1)["concepts"] == ["독서 격차"]
```

`app/tests/test_research_work_tasks.py` (새 파일, 전체):

```python
"""workers/research_work_tasks.py — 생성 디스패치 태스크(spec §6-3).

celery·kombu·redis 는 로컬 venv 에 없다(함정 13). 더미를 꽂고 모듈을 새로 import 하며, 끝나면
import 전 그대로 되돌린다(test_research_tasks.py 의 _load_tasks 와 같은 방식). 태스크 본문은
SQLite 대역(history_sqlite)에서 실제 SQL 로 돌리고, LLM(chat_full)·Redis(publish_work)·브로커
(send_dispatch)만 기록용 가짜로 바꾼다. 이벤트 모양 하나만은 진짜 publish_work(Redis 만 가짜)로 본다.
"""
import asyncio
import importlib
import json
import logging
import sys
import types
from unittest.mock import MagicMock

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.research_work import ResearchGeneration, ResearchWork
from services.llm_client import LLMResult
from services.research_work import routing

_CACHED = ("workers.research_work_tasks", "workers.celery_app", "services.research.relay")
GEN = ResearchGeneration.__table__
WORK = ResearchWork.__table__
CONCEPTS_INPUT = {"question": "청소년 독서 격차", "subquestions": ["독서 격차의 정의"], "headings": []}
GOOD = '{"concepts": ["독서 격차", "청소년"]}'


class _SoftTimeLimitExceeded(Exception):
    """celery 미설치 환경용 대역 — Celery 의 것도 Exception 의 하위 클래스다."""


class _OperationalError(Exception):
    pass


class _FakeConf:
    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class _FakeCelery:
    """task 데코레이터는 원함수를 돌려주고 옵션을 속성으로 붙인다. send_task 는 기록한다."""

    def __init__(self, *a, **kw):
        self.conf = _FakeConf()
        self.init_kw = kw
        self.sent: list[tuple] = []
        self.fail = False

    def task(self, *a, **kw):
        def _decorator(fn):
            for key, value in kw.items():
                setattr(fn, key, value)
            return fn
        return _decorator

    def send_task(self, name, args=None, **kw):
        if self.fail:
            raise _OperationalError("broker down")
        self.sent.append((name, args, kw))


def _stub_missing(monkeypatch, name: str) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, MagicMock())


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules·부모 패키지 속성에서 빼고 테스트가 끝나면 되돌린다(test_research_tasks.py 와 같다)."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


def _load(monkeypatch):
    celery_mod = types.ModuleType("celery")
    celery_mod.Celery = _FakeCelery
    celery_exc = types.ModuleType("celery.exceptions")
    celery_exc.SoftTimeLimitExceeded = _SoftTimeLimitExceeded
    kombu = types.ModuleType("kombu")
    kombu_exc = types.ModuleType("kombu.exceptions")
    kombu_exc.OperationalError = _OperationalError
    for name, module in (("celery", celery_mod), ("celery.exceptions", celery_exc),
                         ("kombu", kombu), ("kombu.exceptions", kombu_exc)):
        monkeypatch.setitem(sys.modules, name, module)
    _stub_missing(monkeypatch, "redis")
    _stub_missing(monkeypatch, "redis.asyncio")
    _forget_on_teardown(monkeypatch, _CACHED)
    return importlib.import_module("workers.research_work_tasks")


@pytest.fixture
def wt(monkeypatch):
    return _load(monkeypatch)


class TestTaskOptions:
    def test_task_runs_on_the_fixed_plan_queue_with_limits(self, wt):
        task = wt.dispatch_research_work
        assert task.name == wt.DISPATCH_TASK == "tasks.dispatch_research_work"
        assert task.queue == wt.WORK_QUEUE == "q_research_plan"
        assert (task.soft_time_limit, task.time_limit) == (wt.GEN_SOFT_LIMIT, wt.GEN_HARD_LIMIT)

    def test_deadline_covers_three_calls_and_the_limits_sit_above_it(self, wt):
        from services.research_work.generate import CALL_TIMEOUT, MAX_CALLS
        assert wt.GEN_DEADLINE == 960
        assert wt.GEN_DEADLINE > MAX_CALLS * (CALL_TIMEOUT + 10)      # 호출마다 연결 10초까지
        assert (wt.GEN_SOFT_LIMIT, wt.GEN_HARD_LIMIT) == (1020, 1080)

    def test_registered_and_routed_even_when_the_plan_queue_setting_is_blank(self, monkeypatch):
        """celery-control·beat 에는 RESEARCH_PLAN_QUEUE 가 없다 — 설정을 따르면 q_llm 으로 떨어진다."""
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_llm")
        monkeypatch.setenv("RESEARCH_PLAN_QUEUE", "")
        get_settings.cache_clear()
        try:
            wt = _load(monkeypatch)
            app = sys.modules["workers.celery_app"].celery_app
            assert "workers.research_work_tasks" in app.init_kw["include"]
            assert app.conf.task_routes["tasks.dispatch_research_work"] == {"queue": "q_research_plan"}
            assert app.conf.task_routes["tasks.plan_deep_research"] == {"queue": "q_llm"}
            assert wt.dispatch_research_work.queue == "q_research_plan"
            assert wt.send_dispatch() is True
            assert app.sent == [("tasks.dispatch_research_work", None, {"queue": "q_research_plan"})]
        finally:
            get_settings.cache_clear()


class TestSendDispatch:
    def test_sends_the_dispatch_task_to_the_plan_queue(self, wt):
        assert wt.send_dispatch() is True
        assert wt.celery_app.sent == [("tasks.dispatch_research_work", None, {"queue": "q_research_plan"})]

    def test_broker_down_is_reported_not_raised(self, wt, caplog):
        wt.celery_app.fail = True
        with caplog.at_level(logging.ERROR):
            assert wt.send_dispatch() is False
        assert any("디스패치 태스크 전달 실패" in r.getMessage() for r in caplog.records)


# ── 태스크 본문 ───────────────────────────────────────────────────────
class _Session(AsyncSessionOverSync):
    """워커의 세션처럼(_job_engine: expire_on_commit=False) 커밋 뒤에도 읽은 값을 들고 있고, async with 로 연다."""

    def __init__(self, engine):  # super().__init__ 은 기본 Session(expire_on_commit=True)을 만든다 — 그 자리만 바꾼다
        self._session = Session(engine, expire_on_commit=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
        return False


class _Env:
    """SQLite 대역 위에서 태스크를 돌린다. chat_full 은 replies 를 차례로 꺼내고(예외면 올린다)."""

    def __init__(self, monkeypatch, wt, replies=()):
        self.wt = wt
        self.engine = make_engine()
        self.replies = list(replies)
        self.calls: list[tuple] = []
        self.events: list[tuple] = []
        self.dispatched = 0
        self.disposed = 0
        self.on_call = None
        env = self

        class _Engine:
            async def dispose(self):
                env.disposed += 1

        cfg = routing.get_settings()
        for key, value in (("VLM_BASE_URL", "http://qwen.test/v1"), ("VLM_MODEL", "qwen-test"),
                           ("LLM_BASE_URL", "http://gemma.test/v1"), ("LLM_MODEL", "gemma-test")):
            monkeypatch.setattr(cfg, key, value)
        monkeypatch.setattr(wt, "_job_engine", lambda: (_Engine(), lambda: _Session(self.engine)))
        monkeypatch.setattr(wt, "chat_full", self._chat)
        monkeypatch.setattr(wt, "publish_work", self._publish)
        monkeypatch.setattr(wt, "send_dispatch", self._send)

    async def _chat(self, messages, *, params=None, timeout=120.0, base_url=None, model=None):
        self.calls.append((base_url, model, timeout))
        if self.on_call is not None:
            await self.on_call()
        item = self.replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        return LLMResult(content=item, finish_reason="stop")

    async def _publish(self, work_id, kind, payload):
        self.events.append((work_id, kind, payload))

    def _send(self) -> bool:
        self.dispatched += 1
        return True

    def work(self, **fields):
        job_id = add_research_job(self.engine, status="completed", stage="synthesized")
        add_work(self.engine, job_id, **fields)
        return job_id

    def gen(self, work_id, **fields) -> int:
        fields.setdefault("input", CONCEPTS_INPUT)
        return add_generation(self.engine, work_id, **fields)

    def row(self, gid: int):
        with self.engine.connect() as conn:
            return conn.execute(sa.select(GEN).where(GEN.c.id == gid)).mappings().one()

    def work_row(self, work_id):
        with self.engine.connect() as conn:
            return conn.execute(sa.select(WORK).where(WORK.c.id == work_id)).mappings().one()

    def set_status(self, gid: int, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(sa.update(GEN).where(GEN.c.id == gid).values(status=status))


class TestDispatch:
    def test_idle_when_nothing_is_queued(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt)

        assert wt.dispatch_research_work() == {"status": "idle"}
        assert env.calls == [] and env.events == [] and env.dispatched == 0
        assert env.disposed == 1

    def test_idle_while_another_generation_runs(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        running = env.gen(env.work(), status="running")
        waiting = env.gen(env.work())

        assert wt.dispatch_research_work() == {"status": "idle"}
        assert env.calls == []
        assert (env.row(running)["status"], env.row(waiting)["status"]) == ("running", "queued")

    def test_concepts_generation_runs_to_done(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        work_id = env.work()
        gid = env.gen(work_id)

        out = wt.dispatch_research_work()

        row = env.row(gid)
        assert out == {"gen_id": gid, "status": "done"}
        assert env.calls == [("http://qwen.test/v1", "qwen-test", 300.0)]
        assert (row["status"], row["model"], row["error"]) == ("done", "qwen-test", None)
        assert row["output"] == {"concepts": ["독서 격차", "청소년"],
                                 "attempts": [{"model": "qwen-test", "outcome": "ok"}]}
        assert row["started_at"] is not None and row["finished_at"] is not None
        work = env.work_row(work_id)
        assert (work["concepts"], work["concept_members"]) == (["독서 격차", "청소년"], {})
        assert env.events == [(work_id, "generation", {
            "gen_id": gid, "gen_kind": "concepts", "target": None, "status": "done",
            "model": "qwen-test", "result": {"concepts": ["독서 격차", "청소년"]},
        })]
        assert env.dispatched == 0 and env.disposed == 1

    def test_generation_event_keeps_its_kind_on_the_work_channel(self, monkeypatch, wt):
        """진짜 publish_work 로 보낸다(Redis 만 가짜). relay 는 {"kind": 이벤트 종류, **payload} 로 실어
        페이로드에 "kind" 가 있으면 "generation" 을 덮어쓴다 — 생성 종류는 gen_kind 에 실려야 한다."""
        env = _Env(monkeypatch, wt, replies=[GOOD])
        relay = sys.modules["services.research.relay"]
        published: list[tuple[str, str]] = []

        class _Redis:
            async def publish(self, channel, data):
                published.append((channel, data))

            async def aclose(self):
                return None

        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: _Redis())
        monkeypatch.setattr(wt, "publish_work", relay.publish_work)
        work_id = env.work()
        gid = env.gen(work_id)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "done"}

        ((channel, data),) = published
        event = json.loads(data)
        assert channel == f"research:work:{work_id}"
        assert (event["kind"], event["gen_kind"], event["gen_id"], event["status"]) == (
            "generation", "concepts", gid, "done")

    def test_no_answer_after_three_calls_is_done_with_no_concepts(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=["모르겠다", '{"concepts": ["하나"]}', "{}"])
        work_id = env.work()
        gid = env.gen(work_id)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "done"}

        row = env.row(gid)
        assert [c[1] for c in env.calls] == ["qwen-test", "qwen-test", "gemma-test"]
        assert (row["status"], row["model"]) == ("done", None)
        assert row["output"]["concepts"] == []
        assert [a["outcome"] for a in row["output"]["attempts"]] == ["parse", "check", "parse"]
        assert env.events[0][2]["result"] == {"concepts": []}

    def test_transport_failure_hands_over_to_gemma(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[httpx.ConnectError("거부"), GOOD])
        gid = env.gen(env.work())

        wt.dispatch_research_work()

        row = env.row(gid)
        assert [c[0] for c in env.calls] == ["http://qwen.test/v1", "http://gemma.test/v1"]
        assert (row["status"], row["model"]) == ("done", "gemma-test")

    def test_next_generation_is_sent_when_more_are_queued(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        first = env.gen(env.work())
        second = env.gen(env.work())

        wt.dispatch_research_work()

        assert (env.row(first)["status"], env.row(second)["status"]) == ("done", "queued")
        assert env.dispatched == 1

    def test_cancel_during_the_call_discards_the_result(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        work_id = env.work(concepts=["사용자 개념"])
        gid = env.gen(work_id)
        other = env.gen(env.work())

        async def _cancel():
            env.set_status(gid, "canceled")          # 사용자가 취소 — API 의 조건부 UPDATE

        env.on_call = _cancel
        out = wt.dispatch_research_work()

        row = env.row(gid)
        assert out == {"gen_id": gid, "status": "dropped"}
        assert (row["status"], row["output"], row["finished_at"]) == ("canceled", None, None)
        assert env.work_row(work_id)["concepts"] == ["사용자 개념"]
        assert env.events == []
        assert env.row(other)["status"] == "queued" and env.dispatched == 1

    def test_unexpected_error_fails_the_generation(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[ValueError("코드 결함")])
        work_id = env.work()
        gid = env.gen(work_id)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "failed"}

        row = env.row(gid)
        assert (row["status"], row["output"], row["model"]) == ("failed", None, None)
        assert row["error"] == "ValueError: 코드 결함"
        assert env.events == [(work_id, "generation", {
            "gen_id": gid, "gen_kind": "concepts", "target": None, "status": "failed",
            "model": None, "result": None,
        })]

    def test_kind_without_an_executor_fails_without_calling_the_llm(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt)
        gid = env.gen(env.work(), kind="outline", input={})

        wt.dispatch_research_work()

        row = env.row(gid)
        assert env.calls == []
        assert (row["status"], row["error"]) == ("failed", "실행기가 없는 생성 종류: outline")

    def test_deadline_fails_the_generation(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        gid = env.gen(env.work())

        async def _hang():
            await asyncio.sleep(5)

        env.on_call = _hang
        monkeypatch.setattr(wt, "GEN_DEADLINE", 0.05)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "failed"}
        row = env.row(gid)
        assert (row["status"], row["error"]) == ("failed", wt.TIMEOUT_ERROR)
        assert env.events[0][2]["status"] == "failed"

    def test_soft_time_limit_closes_the_generation_on_a_new_loop(self, monkeypatch, wt):
        """소프트 리밋이 asyncio.run 밖으로 튀면 루프의 정리 코드가 돌지 않는다 — 새 루프로 닫는다(함정 19)."""
        env = _Env(monkeypatch, wt, replies=[_SoftTimeLimitExceeded()])
        work_id = env.work()
        gid = env.gen(work_id)
        other = env.gen(env.work())

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "failed"}

        row = env.row(gid)
        assert (row["status"], row["error"]) == ("failed", wt.TIMEOUT_ERROR)
        assert env.events[0][:2] == (work_id, "generation") and env.events[0][2]["status"] == "failed"
        assert env.row(other)["status"] == "queued" and env.dispatched == 1
        assert env.disposed == 2              # 잡 엔진 둘(본문·정리) 모두 닫는다
```

`app/tests/test_research_relay.py` — 교체 전(117-121행, `TestChannel`):

```python
class TestChannel:
    def test_uuid_and_its_canonical_string_share_a_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        jid = uuid.uuid4()
        assert relay.channel(jid) == relay.channel(str(jid)) == f"research:{jid}"
```

교체 후:

```python
class TestChannel:
    def test_uuid_and_its_canonical_string_share_a_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        jid = uuid.uuid4()
        assert relay.channel(jid) == relay.channel(str(jid)) == f"research:{jid}"


class _FakePubSub:
    def __init__(self, messages):
        self.messages = list(messages)
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.timeouts: list[float] = []
        self.closed = False

    async def subscribe(self, name):
        self.subscribed.append(name)

    async def get_message(self, *, ignore_subscribe_messages, timeout):
        self.timeouts.append(timeout)
        return self.messages.pop(0) if self.messages else None

    async def unsubscribe(self, name):
        self.unsubscribed.append(name)

    async def aclose(self):
        self.closed = True


class _FakeSubscriber:
    def __init__(self, pubsub: _FakePubSub):
        self._pubsub = pubsub
        self.closed = False

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        self.closed = True


class TestWorkChannel:
    """이어간 연구(research_works)의 생성 이벤트 채널 — 딥리서치 잡 채널과 따로 둔다(spec §6-4)."""

    def test_work_channel_is_its_own_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        wid = uuid.uuid4()
        assert relay.work_channel(wid) == relay.work_channel(str(wid)) == f"research:work:{wid}"
        assert relay.work_channel(wid) != relay.channel(wid)

    def test_publish_work_sends_kind_and_payload_on_the_work_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        client = _FakeRedis()
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)
        wid = uuid.uuid4()

        asyncio.run(relay.publish_work(wid, "generation", {"gen_id": 3, "result": {"concepts": ["독서 격차"]}}))

        ((channel, data),) = client.published
        assert channel == f"research:work:{wid}"
        assert json.loads(data) == {"kind": "generation", "gen_id": 3, "result": {"concepts": ["독서 격차"]}}
        assert "독서 격차" in data                    # 한글을 \\u 로 풀지 않는다(publish 와 같다)

    def test_publish_work_connects_with_socket_timeouts(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        seen = {}

        def _from_url(url):
            seen["url"] = url
            return _FakeRedis()

        monkeypatch.setattr(relay.aioredis, "from_url", _from_url)
        asyncio.run(relay.publish_work(uuid.uuid4(), "work", {}))

        query = parse_qs(urlsplit(seen["url"]).query)
        assert float(query["socket_timeout"][0]) > 0
        assert float(query["socket_connect_timeout"][0]) > 0

    def test_publish_work_swallows_redis_errors(self, monkeypatch, caplog):
        relay = _load_relay(monkeypatch)

        def _down(url):
            raise ConnectionError("redis down")

        monkeypatch.setattr(relay.aioredis, "from_url", _down)
        asyncio.run(relay.publish_work(uuid.uuid4(), "generation", {"gen_id": 1}))

        assert any("publish_work 실패" in r.getMessage() for r in caplog.records)

    def test_subscribe_work_yields_events_and_idle_beats(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        pubsub = _FakePubSub([{"data": json.dumps({"kind": "generation", "gen_id": 7})}, None])
        client = _FakeSubscriber(pubsub)
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)
        wid = uuid.uuid4()

        async def _take_two():
            stream = relay.subscribe_work(wid)
            got = [await stream.__anext__(), await stream.__anext__()]
            await stream.aclose()
            return got

        got = asyncio.run(_take_two())

        assert got == [{"kind": "generation", "gen_id": 7}, None]
        assert pubsub.subscribed == pubsub.unsubscribed == [f"research:work:{wid}"]
        assert pubsub.timeouts == [15.0, 15.0]
        assert pubsub.closed and client.closed
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_dispatch.py -q -p no:cacheprovider`

Expected: `Interrupted: 1 error during collection` — `ModuleNotFoundError: No module named 'services.research_work.apply'`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_tasks.py -q -p no:cacheprovider`

Expected: `1 failed, 16 errors` — 모두 `ModuleNotFoundError: No module named 'workers.research_work_tasks'`(16개는 `wt` 픽스처에서, 1개는 테스트 안에서 직접 불러서)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_relay.py -q -p no:cacheprovider`

Expected: `5 failed, 9 passed` — `AttributeError: module 'services.research.relay' has no attribute 'publish_work'`(3)·`'work_channel'`(1)·`'subscribe_work'`(1)

- [ ] **Step 3: 구현한다**

`app/services/research_work/dispatch.py` (새 파일, 전체):

```python
"""dispatch.py — 생성 디스패처: 전체에서 한 번에 1건 (spec §6-3)

q_research_plan 은 두 자리다. 생성이 두 자리를 다 채우면 새 딥리서치의 '계획 세우는 중'이 생성 1건
길이(최대 약 16분)만큼 밀린다 — 그래서 모든 연구를 통틀어 running 생성은 1건이다.
  pick_next: 전역 advisory lock 안에서 running 수를 세고, 0 이면 queued 하나를
             (우선순위 높은 것 → 오래된 것 → id 순) FOR UPDATE SKIP LOCKED 로 집어 running 으로 바꾼다.
  부분 유니크 인덱스 ux_research_generations_running(연구마다 running 1건)은 이중 안전장치다.
상태 전이는 조건부 UPDATE 로만 한다 — 취소(API)와 회수(회수기)가 같은 행을 바꾼다.
세션에서 execute·commit·rollback·scalar 만 쓴다(tests/history_sqlite 대역이 흉내 내는 것).
"""
from sqlalchemy import and_, exists, func, or_, select, update

from models.research_work import ResearchGeneration

# 생성 디스패치 전역 잠금 키(부호 있는 bigint 범위 안). api/research.py 의 _RUN_SLOT_LOCK 과 다르다
GEN_LOCK = int.from_bytes(b"RSWKDISP", "big")

FINISH_STATUSES = ("done", "failed")


async def pick_next(db) -> ResearchGeneration | None:
    """다음 생성을 running 으로 바꿔 돌려준다. 이미 도는 생성이 있거나 줄이 비었으면 None.

    잠금·개수·집기·전이가 한 트랜잭션이다 — 사이에 커밋이 끼면 겹친 디스패치 둘이 같이 0건을 보고
    둘 다 집는다. 돌려준 행은 커밋 뒤의 값이다(started_at 은 RETURNING 으로 받는다).
    """
    await db.execute(select(func.pg_advisory_xact_lock(GEN_LOCK)))
    running = (await db.execute(
        select(func.count()).select_from(ResearchGeneration)
        .where(ResearchGeneration.status == "running")
    )).scalar_one()
    if running:
        await db.rollback()
        return None
    gen_id = (await db.execute(
        select(ResearchGeneration.id)
        .where(ResearchGeneration.status == "queued")
        .order_by(ResearchGeneration.priority.desc(), ResearchGeneration.created_at,
                  ResearchGeneration.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )).scalar_one_or_none()
    if gen_id is None:
        await db.rollback()
        return None
    gen = (await db.execute(
        update(ResearchGeneration)
        .where(ResearchGeneration.id == gen_id)
        .values(status="running", started_at=func.now())
        .returning(ResearchGeneration)
    )).scalar_one()
    await db.commit()
    return gen


async def finish(db, gen_id: int, *, status: str, output: dict | None, model: str | None,
                 error: str | None) -> bool:
    """running 인 생성만 닫는다. 그 사이 취소·회수로 이미 닫혔으면 False 이고, 같은 트랜잭션의
    앞선 쓰기(결과 적용)까지 되돌린다 — 취소한 생성의 결과가 연구에 남으면 안 된다."""
    if status not in FINISH_STATUSES:
        raise ValueError(f"생성을 닫는 상태는 done·failed 뿐이다: {status!r}")
    res = await db.execute(
        update(ResearchGeneration)
        .where(ResearchGeneration.id == gen_id, ResearchGeneration.status == "running")
        .values(status=status, output=output, model=model, error=error, finished_at=func.now())
    )
    if res.rowcount != 1:
        await db.rollback()
        return False
    await db.commit()
    return True


async def has_queued(db) -> bool:
    return bool(await db.scalar(select(exists().where(ResearchGeneration.status == "queued"))))


async def queue_position(db, gen: ResearchGeneration) -> int:
    """내 앞의 queued(우선순위 높은 것 → 오래된 것 → id 순) + running 수. queued 가 아니면 0."""
    if gen.status != "queued":
        return 0
    g = ResearchGeneration
    ahead = await db.scalar(
        select(func.count()).select_from(g).where(
            g.status == "queued",
            or_(
                g.priority > gen.priority,
                and_(g.priority == gen.priority, or_(
                    g.created_at < gen.created_at,
                    and_(g.created_at == gen.created_at, g.id < gen.id),
                )),
            ),
        )
    )
    running = await db.scalar(
        select(func.count()).select_from(g).where(g.status == "running")
    )
    return int(ahead or 0) + int(running or 0)
```

`app/services/research_work/apply.py` (새 파일, 전체):

```python
"""apply.py — 끝난 생성의 결과를 연구에 반영한다.

디스패처가 finish 와 같은 트랜잭션에서 부른다. 여기서는 커밋하지 않는다 — finish 가 생성 상태와 함께
커밋하고, 도는 사이 취소됐으면(finish 가 False) 이 반영도 함께 되돌린다.
"""
from sqlalchemy import update

from models.research_work import ResearchWork


async def apply_result(db, gen, output: dict) -> dict:
    """gen.kind 에 맞게 반영하고 generation 이벤트의 result 로 실을 값을 돌려준다.

    concepts: research_works.concepts 를 바꾸고 개념 소속(concept_members)을 비운다 — 소속은 FastAPI 가
    개념 임베딩으로 다시 계산한다(spec §5-3, 06c). 세 번 다 못 얻은 빈 결과면 연구를 건드리지 않는다 —
    빈 결과를 다시 부르기 전에 사용자가 넣은 칩과 소속을 아무 결과 없이 지우면 안 된다.
    그 밖의 kind 는 06a 에 실행기가 없어 하는 일이 없다.
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
    return {}
```

`app/services/research/relay.py` — 교체 전(101-104행, `subscribe` 의 `finally` — 파일 끝):

```python
    finally:
        await pubsub.unsubscribe(channel(job_id))
        await pubsub.aclose()
        await client.aclose()
```

교체 후:

```python
    finally:
        await pubsub.unsubscribe(channel(job_id))
        await pubsub.aclose()
        await client.aclose()


# ── 이어간 연구(research_works)의 채널 ─────────────────────────────────────
# 연구 id 는 출발 딥리서치 잡 id 와 같다. 잡 채널과 섞이면 딥리서치 화면이 생성 이벤트를 받으므로
# 이름을 따로 둔다. 보내는 방식(호출마다 클라이언트·소켓 타임아웃·실패 삼킴)과 받는 방식(유휴 None)은
# 위 publish·subscribe 와 같다.
def work_channel(work_id: uuid.UUID | str) -> str:
    return f"research:work:{work_id}"


async def publish_work(work_id: uuid.UUID | str, kind: str, payload: dict) -> None:
    cfg = get_settings()
    try:
        client = aioredis.from_url(_with_timeouts(cfg.REDIS_URL))
        try:
            await client.publish(
                work_channel(work_id), json.dumps({"kind": kind, **payload}, ensure_ascii=False)
            )
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:relay] publish_work 실패 work=%s kind=%s: %s", work_id, kind, e)


async def subscribe_work(
    work_id: uuid.UUID | str, *, idle_timeout: float = 15.0,
) -> AsyncIterator[dict | None]:
    """이벤트 dict 를 yield 하고, 유휴 구간에서는 None 을 yield 한다(subscribe 와 같다)."""
    cfg = get_settings()
    client = aioredis.from_url(cfg.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(work_channel(work_id))
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=idle_timeout,
            )
            yield json.loads(message["data"]) if message else None
    finally:
        await pubsub.unsubscribe(work_channel(work_id))
        await pubsub.aclose()
        await client.aclose()
```

`app/workers/research_work_tasks.py` (새 파일, 전체):

```python
"""research_work_tasks.py — 연구 어시스턴트 생성 디스패치 태스크 (spec §6-3)

생성 1건 = Celery 메시지 1개. 생성을 넣는 API·끝난 디스패치·회수기가 send_dispatch() 로 이 태스크를
보낸다. 태스크는 전역 잠금 안에서 running 생성이 없을 때만 queued 하나를 집어(dispatch.pick_next)
돌리고, 끝나면 queued 가 남았을 때 자기를 다시 보낸다. 그래서 q_research_plan 두 자리 중 하나는 늘
딥리서치 계획(tasks.plan_deep_research)에 남는다(D15). 겹친 디스패치는 아무것도 집지 않고 끝난다.

큐는 설정값이 아니라 문자열 "q_research_plan" 이다(task 옵션·celery_app.task_routes·send_dispatch 셋 다).
회수기가 도는 celery-control·celery-beat 에는 RESEARCH_PLAN_QUEUE env 가 없어, 설정값을 따르면
q_llm(적재 워커)으로 떨어진다.

시간 한도(함정 19): 본문을 GEN_DEADLINE = 호출 3회 × (timeout 300초 + 연결 10초) + 30초 안의 asyncio
데드라인으로 감싸고, Celery soft/hard limit 은 그보다 크게 둔다. 소프트 리밋이 asyncio.run 밖으로 튀면
새 루프·새 엔진으로 생성을 failed 로 닫는다(research_tasks._run_job 과 같은 방식).
생성 상태는 조건부 UPDATE(dispatch.finish)로만 닫는다 — 도는 사이 사용자가 취소했으면 결과를 버린다.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)

from core.config import get_settings
from services.llm_client import chat_full
from services.research.relay import publish_work
from services.research_work.apply import apply_result
from services.research_work.dispatch import finish, has_queued, pick_next
from services.research_work.executors import EXECUTORS
from services.research_work.generate import (
    CALL_TIMEOUT, MAX_CALLS, GenerationResult, run_generation,
)
from workers.celery_app import celery_app

log = logging.getLogger(__name__)

DISPATCH_TASK = "tasks.dispatch_research_work"
WORK_QUEUE = "q_research_plan"          # 설정값을 쓰지 않는다(celery-control 에는 RESEARCH_PLAN_QUEUE env 가 없다)
GEN_DEADLINE = MAX_CALLS * (CALL_TIMEOUT + 10) + 30      # 960초
GEN_SOFT_LIMIT = GEN_DEADLINE + 60
GEN_HARD_LIMIT = GEN_SOFT_LIMIT + 60

TIMEOUT_ERROR = "시간 상한 초과 — 생성을 끝내지 못했다"


@dataclass(frozen=True)
class _Picked:
    """집은 생성의 값. ORM 객체를 들고 다니지 않는다 — rollback(finish 가 취소를 만났을 때)이 세션의
    인스턴스를 만료시켜, 그 뒤 속성 접근이 async 세션에서 MissingGreenlet 으로 터진다(research_tasks._StepRef)."""
    id: int
    work_id: uuid.UUID
    kind: str
    target: str | None
    input: dict


def _job_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """태스크 하나짜리 async 엔진 — 까닭은 research_tasks._job_engine 과 같다(Celery 는 태스크마다
    asyncio.run 으로 루프를 새로 연다). 한 번에 세션 하나만 쓴다."""
    cfg = get_settings()
    engine = create_async_engine(
        cfg.DATABASE_URL, pool_size=2, max_overflow=0, pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def send_dispatch() -> bool:
    """디스패치 태스크를 보낸다. 브로커에 못 넣으면 False(회수기가 10분 안에 다시 보낸다)."""
    from kombu.exceptions import OperationalError

    try:
        celery_app.send_task(DISPATCH_TASK, queue=WORK_QUEUE)
    except OperationalError:
        log.exception("[research_work] 디스패치 태스크 전달 실패")
        return False
    return True


def _error_text(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}"[:500]


@celery_app.task(name=DISPATCH_TASK, queue=WORK_QUEUE,
                 soft_time_limit=GEN_SOFT_LIMIT, time_limit=GEN_HARD_LIMIT)
def dispatch_research_work() -> dict:
    picked: list[_Picked] = []
    try:
        return asyncio.run(_dispatch(picked))
    except SoftTimeLimitExceeded:
        if not picked:
            log.error("[research_work] 생성을 집기 전에 시간 상한 초과")
            return {"status": "timeout"}
        # 루프가 이미 닫혔다 — 정리는 새 루프·새 엔진으로 한다
        return asyncio.run(_close_timed_out(picked[0]))


async def _dispatch(picked: list[_Picked]) -> dict:
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            row = await pick_next(db)
            if row is None:
                return {"status": "idle"}
            gen = _Picked(id=row.id, work_id=row.work_id, kind=row.kind, target=row.target,
                          input=dict(row.input or {}))
            picked.append(gen)
            result, error = await _generate(gen)
            return await _close(db, gen, result, error)
    finally:
        # 루프가 죽기 전에 커넥션을 닫는다
        await engine.dispose()


async def _generate(gen: _Picked) -> tuple[GenerationResult | None, str | None]:
    """(결과, None) 또는 (None, 실패 문구). LLM 을 부르는 동안 DB 트랜잭션을 열어 두지 않는다
    (pick_next 가 커밋하고 돌아왔다)."""
    executor = EXECUTORS.get(gen.kind)
    if executor is None:
        return None, f"실행기가 없는 생성 종류: {gen.kind}"
    deadline = asyncio.timeout(GEN_DEADLINE)
    try:
        async with deadline:
            return await run_generation(executor, gen.input, chat_fn=chat_full), None
    except SoftTimeLimitExceeded:
        raise
    except Exception as e:
        if isinstance(e, TimeoutError) and deadline.expired():
            log.error("[research_work] 생성 데드라인 초과 gen=%s kind=%s", gen.id, gen.kind)
            return None, TIMEOUT_ERROR
        log.exception("[research_work] 생성 실패 gen=%s kind=%s", gen.id, gen.kind)
        return None, _error_text(e)


async def _close(db: AsyncSession, gen: _Picked, result: GenerationResult | None,
                 error: str | None) -> dict:
    """결과를 반영하고 생성을 닫은 뒤 알린다. 그 사이 취소·회수로 이미 닫혔으면(finish 가 False)
    반영을 되돌리고 알리지 않는다. 어느 쪽이든 queued 가 남았으면 다음 디스패치를 보낸다."""
    payload = None
    if result is not None:
        try:
            payload = await apply_result(db, gen, result.output)
            closed = await finish(
                db, gen.id, status="done", model=result.model, error=None,
                output={**result.output, "attempts": result.attempts},
            )
        except SoftTimeLimitExceeded:
            raise
        except Exception as e:
            await db.rollback()
            log.exception("[research_work] 결과 반영 실패 gen=%s kind=%s", gen.id, gen.kind)
            result, payload, error = None, None, _error_text(e)
    if result is None:
        closed = await finish(db, gen.id, status="failed", output=None, model=None, error=error)
    status = "done" if result is not None else "failed"
    if closed:
        # 생성 종류는 gen_kind — relay 가 이벤트 종류를 "kind" 에 싣는다(페이로드의 kind 는 그것을 덮어쓴다)
        await publish_work(gen.work_id, "generation", {
            "gen_id": gen.id, "gen_kind": gen.kind, "target": gen.target, "status": status,
            "model": result.model if result is not None else None, "result": payload,
        })
    else:
        log.info("[research_work] 도는 사이 취소·회수된 생성 — 결과를 버린다 gen=%s", gen.id)
    if await has_queued(db):
        send_dispatch()
    return {"gen_id": gen.id, "status": status if closed else "dropped"}


async def _close_timed_out(gen: _Picked) -> dict:
    log.error("[research_work] 시간 상한 초과 gen=%s kind=%s", gen.id, gen.kind)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            return await _close(db, gen, None, TIMEOUT_ERROR)
    finally:
        await engine.dispose()
```

`app/workers/celery_app.py` — 교체 전(15행):

```python
    include=["workers.tasks", "workers.research_tasks"],
```

교체 후:

```python
    include=["workers.tasks", "workers.research_tasks", "workers.research_work_tasks"],
```

`app/workers/celery_app.py` — 교체 전(43-44행, `task_routes` 끝):

```python
        "tasks.reap_stale_research": {"queue": "q_control"},
    },
```

교체 후:

```python
        "tasks.reap_stale_research": {"queue": "q_control"},
        # 연구 어시스턴트 생성 디스패치 — 설정값이 아니라 문자열로 고정한다. 회수기가 도는 celery-control·
        # celery-beat 에는 RESEARCH_PLAN_QUEUE env 가 없어 설정값이면 q_llm 으로 떨어진다(research_work_tasks)
        "tasks.dispatch_research_work": {"queue": "q_research_plan"},
    },
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_dispatch.py tests/test_research_work_tasks.py tests/test_research_relay.py -q -p no:cacheprovider`

Expected: `53 passed` (dispatch 22 + tasks 17 + relay 14 — relay 는 기존 9 + 새 5)

같은 모듈·celery_app 을 쓰는 기존 테스트와 Task 8:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_generate.py tests/test_research_work_concepts.py tests/test_celery_schedule.py tests/test_research_tasks.py tests/test_research_api.py tests/test_research_run_queue.py tests/test_research_work_models.py -q -p no:cacheprovider`

Expected: 실패 0 — Task 1~8 을 적용한 검증 사본에서 `311 passed`(17 + 26 + 2 + 96 + 110 + 23 + 37 — research_tasks 96·research_api 110 은 Task 7 뒤 수)

더미 celery·redis 에 묶인 모듈이 다음 파일로 새지 않는지(순서를 바꿔):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_tasks.py tests/test_research_relay.py tests/test_research_tasks.py tests/test_research_api.py tests/test_celery_schedule.py tests/test_research_work_dispatch.py -q -p no:cacheprovider`

Expected: `261 passed` (17 + 14 + 96 + 110 + 2 + 22)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 0, `3 errors` 그대로. 이 작업은 44개를 더한다(Task 8 뒤 수 + 44 — dispatch 22 + tasks 17 + relay 새 5) — 검증 사본에서 `1558 passed` → `1602 passed, 1 skipped, 2 warnings, 3 errors`.

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/services/research_work/dispatch.py app/services/research_work/apply.py app/workers/research_work_tasks.py app/services/research/relay.py app/workers/celery_app.py app/tests/test_research_relay.py app/tests/test_research_work_dispatch.py app/tests/test_research_work_tasks.py && git status --short && git commit -m "[Feat] round06a — 연구 어시스턴트 생성 디스패처: 생성 1건 = Celery 메시지 1개(tasks.dispatch_research_work, 큐는 설정이 아닌 q_research_plan 고정)로, 전역 advisory lock 안에서 running 생성이 없을 때만 queued 하나를 우선순위·오래된 순으로 FOR UPDATE SKIP LOCKED 로 집어 돌린다 — q_research_plan 두 자리 중 하나는 늘 딥리서치 계획에 남는다. 결과 적용과 조건부 닫기를 한 트랜잭션으로 해 도는 사이 취소된 생성의 결과는 버리고(빈 개념 결과는 연구의 칩을 덮지 않는다), 끝나면 generation 이벤트를 연구 채널(research:work:{id})로 보낸 뒤 줄이 남았으면 다음 디스패치를 보낸다. 생성 종류는 gen_kind 에 싣는다 — relay 가 이벤트 종류를 kind 에 싣는다. 데드라인 960초·soft 1020·hard 1080, 소프트 리밋은 새 루프로 failed 를 닫는다"
```

---


### Task 10: 회수기 확장 — 멈춘 생성 회수·디스패치 다시 보내기·회수한 잡을 대기 줄에서 빼기

**왜:** spec §6-3 '시간 한도'. 디스패치 워커가 죽으면 그 생성은 running 으로 영원히 남고, 전역 한 줄 디스패처는 running 이 있으면 아무것도 집지 않으므로 **모든 연구의 생성이 멈춘다**. 생성을 넣은 API 의 `send_dispatch` 가 브로커에 못 넣었을 때도 줄이 멈춘다. 기존 회수 태스크 `tasks.reap_stale_research`(q_control, beat 10분)를 넓혀 둘 다 풀고, 회수로 failed 가 된 딥리서치 잡은 대기 순번 ZSET(Task 7)에서도 뺀다.

**Files:**
- Modify: `app/workers/research_tasks.py` (Task 7 뒤 기준: import 32행·38행, `STALE_MINUTES` 55행, `reap_stale_research` 의 docstring 끝 722행 ~ 함수 끝 761행)
- Modify: `app/tests/test_research_tasks.py` (Task 7 뒤 기준: `_CACHED` 32행, `TestReaper` 머리와 `_SyncSession` 1920-1939행, `test_reaping_a_job_closes_its_running_steps` 끝 1959-1962행 뒤에 더한다)
- Test: `app/tests/test_research_tasks.py`

**알아 둘 것:**
- 같은 트랜잭션에서 차례로: ① 기존 잡·step 회수 — 마지막 SELECT 에 회수한 잡 id 배열(`array_agg(id::text)`, `RETURNING id` 로 받은 것)을 더한다 ② 기존 오래된 step 회수 ③ `research_generations` 의 running 중 `GEN_STALE_SECONDS`(= `GEN_HARD_LIMIT + 60` = 1140초) 넘은 것을 failed(`error='stale — 워커 응답 없음'`) ④ 'queued 가 있고 running 이 없는가'를 센다(③ 뒤라 방금 회수한 것은 running 이 아니다). 커밋한 **뒤에** 회수한 잡을 `unmark_many_sync` 로 빼고(없으면 Redis 를 부르지 않는다), ④ 가 참이면 `send_dispatch()`. 커밋 전에 보내면 디스패처가 아직 running 인 회수 대상을 보고 그냥 끝난다.
- 대기 줄 정리는 회수로 failed 가 된 잡만이다 — `status NOT IN ('approved','queued')` 같은 상태 필터로 줄 전체를 훑지 않는다(계약 §10). 회수 대상은 planning·running 잡이라 보통 이미 줄에 없다(워커가 집을 때 뺀다) — Redis 장애로 남은 것을 치우는 안전망이다.
- 반환에 `"generations": n_gen, "redispatched": bool` 을 더한다(`send_dispatch` 가 브로커에 못 넣으면 False). 시간 제한(60/90)·큐(q_control)·beat 일정은 그대로다.
- 회수한 생성은 연구 채널에 알리지 않는다(06a 범위 밖 — Task 9 '06a 는 끝난 생성만 알린다'). 열려 있는 화면은 다시 접속할 때 snapshot 으로 failed 를 본다. 06a 화면은 생성 진행을 그리지 않는다. 회수 알림(동기 Redis publish 로 `generation`(status=failed))은 연구 화면을 만드는 06b 에서 running 이벤트와 함께 정한다 — 그때 회수 문장에 `RETURNING id, work_id` 를 붙여 커밋 뒤에 보낸다.
- `research_tasks` 가 `workers.research_work_tasks` 를 최상단에서 import 한다(순환 없음 — research_work_tasks 는 research_tasks 를 부르지 않는다). 그래서 테스트의 `_CACHED` 에 `"workers.research_work_tasks"` 를 더해 더미 celery·redis 에 묶인 모듈이 테스트 밖으로 새지 않게 한다(`TestLoaderIsolation` 이 새 이름까지 확인한다).
- 테스트 대역 `_SyncSession` 은 문장마다 돌려줄 값을 고른다(잡 회수 `one()` 은 `(n, 2, ids)`, 생성 회수는 `rowcount`, EXISTS 는 `scalar_one()`). 기존 `test_reaping_a_job_closes_its_running_steps` 는 고치지 않고 새 대역으로 그대로 돈다. Postgres 전용 SQL(`make_interval`·`array_agg`·`::text[]`)은 로컬에서 실행되지 않아 문장 문자열로 확인한다 — 운영 배포 뒤 회수기 로그(10분 안)로 한 번 본다.
- **계약과 다른 점:** ① 생성 회수 조건을 `coalesce(started_at, created_at) < …` 로 둔다(계약: `started_at <`). 디스패처는 running 으로 바꿀 때 `started_at` 을 함께 쓰지만, 비어 있는 running 행이 하나라도 생기면 NULL 비교가 참이 되지 않아 영원히 남고 그동안 모든 연구의 생성이 멈춘다 — 잡 회수와 같은 물러남이다. ② 같은 문장에서 `updated_at = now()` 도 쓴다(raw SQL 이라 ORM `onupdate` 가 돌지 않는다). ③ 회수 임계를 상수 `GEN_STALE_SECONDS` 로 둔다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_research_tasks.py` — 교체 전(32행):

```python
_CACHED = ("workers.research_tasks", "workers.celery_app", "services.research.relay")
```

교체 후:

```python
_CACHED = ("workers.research_tasks", "workers.celery_app", "services.research.relay",
           "workers.research_work_tasks")
```

`app/tests/test_research_tasks.py` — 교체 전(1920-1939행, `TestReaper` 머리와 `_SyncSession`):

```python
class TestReaper:
    class _SyncSession:
        def __init__(self):
            self.sql: list[str] = []

        def execute(self, stmt, params=None):
            self.sql.append(str(stmt))
            result = MagicMock()
            result.one.return_value = (1, 2)
            result.fetchall.return_value = [("s",)]
            return result

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None
```

교체 후:

```python
class TestReaper:
    class _SyncSession:
        """문장마다 회수 결과를 돌려준다. events 에 문장·COMMIT·ROLLBACK 을 순서대로 남긴다(테스트가
        대기 줄 빼기·디스패치 보내기를 같은 목록에 적어 커밋과의 순서를 본다)."""

        def __init__(self, *, reaped=("j1",), gens=0, idle=False, fail_on=None):
            self.sql: list[str] = []
            self.params: list = []
            self.events: list = []
            self._reaped, self._gens, self._idle, self._fail_on = list(reaped), gens, idle, fail_on

        def execute(self, stmt, params=None):
            sql = str(stmt)
            if self._fail_on and self._fail_on in sql:
                raise RuntimeError("DB 오류")
            self.sql.append(sql)
            self.params.append(params)
            self.events.append(sql)
            result = MagicMock()
            if "UPDATE research_jobs" in sql:
                result.one.return_value = (len(self._reaped), 2, list(self._reaped))
            elif "UPDATE research_generations" in sql:
                result.rowcount = self._gens
            elif "EXISTS" in sql:
                result.scalar_one.return_value = self._idle
            else:
                result.fetchall.return_value = [("s",)]
            return result

        def commit(self):
            self.events.append("COMMIT")

        def rollback(self):
            self.events.append("ROLLBACK")

        def close(self):
            self.events.append("CLOSE")

    @staticmethod
    def _reap(monkeypatch, rt, db, *, sent: bool = True) -> dict:
        monkeypatch.setattr(rt, "SyncSessionLocal", lambda: db)
        monkeypatch.setattr(rt, "unmark_many_sync", lambda ids: db.events.append(("unmark", list(ids))))

        def _send() -> bool:
            db.events.append("DISPATCH")
            return sent

        monkeypatch.setattr(rt, "send_dispatch", _send)
        return rt.reap_stale_research()

    @staticmethod
    def _at(db, needle: str) -> int:
        return next(i for i, e in enumerate(db.events) if isinstance(e, str) and needle in e)
```

`app/tests/test_research_tasks.py` — 교체 전(1959-1962행, `test_reaping_a_job_closes_its_running_steps` 끝):

```python
        job_sql = next(s for s in db.sql if "UPDATE research_jobs" in s)
        # 회수한 잡의 running step 을 같은 문장에서 닫는다
        assert "UPDATE research_steps" in job_sql and "reaped" in job_sql
        assert out["jobs"] == 1
```

교체 후:

```python
        job_sql = next(s for s in db.sql if "UPDATE research_jobs" in s)
        # 회수한 잡의 running step 을 같은 문장에서 닫는다
        assert "UPDATE research_steps" in job_sql and "reaped" in job_sql
        assert out["jobs"] == 1

    def test_stale_running_generations_fail_in_the_same_transaction(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(gens=2)

        out = self._reap(monkeypatch, rt, db)

        i = self._at(db, "UPDATE research_generations")
        gen_sql = db.events[i]
        assert "SET status = 'failed'" in gen_sql and "WHERE status = 'running'" in gen_sql
        assert "coalesce(started_at, created_at) < now() - make_interval(secs => :s)" in gen_sql
        assert db.params[db.sql.index(gen_sql)] == {"s": rt.GEN_STALE_SECONDS}
        assert self._at(db, "UPDATE research_jobs") < i < db.events.index("COMMIT")
        assert out["generations"] == 2

    def test_generation_threshold_is_past_the_dispatch_hard_limit(self, monkeypatch):
        """회수 임계가 디스패치 태스크의 하드 리밋보다 짧으면 아직 도는 생성을 회수한다."""
        rt = _load_tasks(monkeypatch)
        work_tasks = sys.modules["workers.research_work_tasks"]
        assert rt.GEN_STALE_SECONDS == work_tasks.GEN_HARD_LIMIT + 60 == 1140

    def test_queued_work_with_nothing_running_is_dispatched_after_commit(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(gens=1, idle=True)

        out = self._reap(monkeypatch, rt, db)

        check = self._at(db, "EXISTS")
        check_sql = db.events[check]
        assert "status = 'queued'" in check_sql and "NOT EXISTS" in check_sql
        assert "status = 'running'" in check_sql
        # 방금 회수한 running 이 빠진 뒤에 세고, 커밋한 뒤에 보낸다 — 커밋 전에 보내면 디스패처가 아직
        # running 인 회수 대상을 보고 그냥 끝난다
        assert self._at(db, "UPDATE research_generations") < check < db.events.index("COMMIT")
        assert db.events.index("COMMIT") < db.events.index("DISPATCH")
        assert out["redispatched"] is True

    def test_no_dispatch_while_one_runs_or_nothing_waits(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(idle=False)

        out = self._reap(monkeypatch, rt, db)

        assert "DISPATCH" not in db.events
        assert out["redispatched"] is False

    def test_broker_down_is_reported_in_the_result(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(idle=True)

        out = self._reap(monkeypatch, rt, db, sent=False)

        assert "DISPATCH" in db.events and out["redispatched"] is False

    def test_reaped_jobs_leave_the_wait_line_after_commit(self, monkeypatch):
        """회수로 failed 가 된 잡만 대기 줄에서 뺀다 — 상태로 거른 잡 전체를 빼지 않는다."""
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(reaped=("j1", "j2"))

        out = self._reap(monkeypatch, rt, db)

        job_sql = db.events[self._at(db, "UPDATE research_jobs")]
        assert "RETURNING id" in job_sql and "array_agg(id::text)" in job_sql
        assert "NOT IN" not in job_sql
        assert db.events.index("COMMIT") < db.events.index(("unmark", ["j1", "j2"]))
        assert (out["jobs"], out["steps"]) == (2, 3)

    def test_nothing_reaped_leaves_redis_alone(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(reaped=())

        out = self._reap(monkeypatch, rt, db)

        assert not any(isinstance(e, tuple) for e in db.events)
        assert out == {"jobs": 0, "steps": 3, "generations": 0, "redispatched": False}

    def test_db_error_rolls_back_and_sends_nothing(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(reaped=("j1",), idle=True, fail_on="UPDATE research_generations")

        with pytest.raises(RuntimeError):
            self._reap(monkeypatch, rt, db)

        assert "ROLLBACK" in db.events and "COMMIT" not in db.events
        assert "DISPATCH" not in db.events and not any(isinstance(e, tuple) for e in db.events)

    def test_redispatch_goes_to_q_research_plan_even_when_the_setting_is_blank(self, monkeypatch):
        """회수기가 도는 celery-control 에는 RESEARCH_PLAN_QUEUE 가 없다 — 그래도 q_research_plan 으로 간다."""
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_llm")
        monkeypatch.setenv("RESEARCH_PLAN_QUEUE", "")
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch)
            kombu_exc = types.ModuleType("kombu.exceptions")
            kombu_exc.OperationalError = type("OperationalError", (Exception,), {})
            _stub_missing(monkeypatch, "kombu", types.ModuleType("kombu"))
            _stub_missing(monkeypatch, "kombu.exceptions", kombu_exc)
            sent = []
            sender = types.SimpleNamespace(send_task=lambda name, args=None, **kw: sent.append((name, kw)))
            monkeypatch.setattr(sys.modules["workers.research_work_tasks"], "celery_app", sender)
            db = self._SyncSession(idle=True)
            monkeypatch.setattr(rt, "SyncSessionLocal", lambda: db)
            monkeypatch.setattr(rt, "unmark_many_sync", lambda ids: None)

            out = rt.reap_stale_research()

            assert sent == [("tasks.dispatch_research_work", {"queue": "q_research_plan"})]
            assert out["redispatched"] is True
        finally:
            get_settings.cache_clear()
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `10 failed, 95 passed` — 새 테스트 9개와 기존 `test_reaping_a_job_closes_its_running_steps`(대역의 `one()` 이 셋을 돌려줘 `ValueError: too many values to unpack (expected 2)`). 새 테스트 중 7개는 `AttributeError: <module 'workers.research_tasks' ...> has no attribute 'unmark_many_sync'`, 2개는 `KeyError: 'workers.research_work_tasks'`.

- [ ] **Step 3: 구현한다**

`app/workers/research_tasks.py` — 교체 전(32행):

```python
from services.research.run_queue import unmark
```

교체 후:

```python
from services.research.run_queue import unmark, unmark_many_sync
```

`app/workers/research_tasks.py` — 교체 전(38행):

```python
from workers.celery_app import CONTROL_SOFT_TIME_LIMIT, CONTROL_TIME_LIMIT, celery_app
```

교체 후:

```python
from workers.celery_app import CONTROL_SOFT_TIME_LIMIT, CONTROL_TIME_LIMIT, celery_app
from workers.research_work_tasks import GEN_HARD_LIMIT, send_dispatch
```

`app/workers/research_tasks.py` — 교체 전(53-55행):

```python
# 하드 리밋보다 길어야 한다. 짧으면 아직 살아서 쓰고 있는 워커의 잡을 회수하고,
# 그 뒤 retry 한 새 실행과 옛 실행이 같은 잡에서 부딪힌다.
STALE_MINUTES = 45
```

교체 후:

```python
# 하드 리밋보다 길어야 한다. 짧으면 아직 살아서 쓰고 있는 워커의 잡을 회수하고,
# 그 뒤 retry 한 새 실행과 옛 실행이 같은 잡에서 부딪힌다.
STALE_MINUTES = 45

# 연구 어시스턴트 생성(research_generations)의 회수 임계(초) — 같은 까닭으로 디스패치 태스크의 하드 리밋보다 길다
GEN_STALE_SECONDS = GEN_HARD_LIMIT + 60
```

`app/workers/research_tasks.py` — 교체 전(722-761행, `reap_stale_research` 의 docstring 끝부터 함수 끝까지):

```python
    approved·queued 는 회수하지 않는다 — 아직 워커가 집지 않은 정상 대기 상태다.
    """
    db = SyncSessionLocal()
    try:
        # coalesce 가 필요한 이유: planning 단계에서 워커가 죽으면 started_at 이 NULL
        # 일 수 있고, NULL 비교는 NULL 이라 조건이 참이 되지 않아 영원히 회수되지 않는다.
        # 회수한 잡의 running step 도 같은 문장에서 닫는다 — 따로 두면 잡은 failed 인데
        # 마지막 step 은 자기 updated_at 기준으로 한참 더 running 으로 보인다.
        n_jobs, n_job_steps = db.execute(sa_text(
            "WITH reaped AS ("
            "  UPDATE research_jobs SET status = 'failed', "
            "         last_error = 'stale — 워커 응답 없음', finished_at = now() "
            "  WHERE status IN ('planning', 'running') "
            "    AND coalesce(started_at, created_at) < now() - make_interval(mins => :m) "
            "  RETURNING id"
            "), closed AS ("
            "  UPDATE research_steps SET status = 'failed', "
            "         result = result || '{\"error\": \"stale — 워커 응답 없음\"}'::jsonb, "
            "         finished_at = now() "
            "  WHERE status = 'running' AND job_id IN (SELECT id FROM reaped) "
            "  RETURNING id"
            ") SELECT (SELECT count(*) FROM reaped), (SELECT count(*) FROM closed)"
        ), {"m": STALE_MINUTES}).one()

        steps = db.execute(sa_text(
            "UPDATE research_steps SET status = 'failed', "
            "       result = result || '{\"error\": \"stale — 워커 응답 없음\"}'::jsonb, "
            "       finished_at = now() "
            "WHERE status = 'running' "
            "  AND updated_at < now() - make_interval(mins => :m) "
            "RETURNING job_id"
        ), {"m": STALE_MINUTES}).fetchall()

        db.commit()
        return {"jobs": n_jobs, "steps": n_job_steps + len(steps)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

교체 후:

```python
    approved·queued 는 회수하지 않는다 — 아직 워커가 집지 않은 정상 대기 상태다.

    연구 어시스턴트 생성(research_generations)도 같은 트랜잭션에서 회수한다 — running 이
    GEN_STALE_SECONDS 를 넘었으면 디스패치 워커가 죽은 것이다. 그 뒤 queued 가 남았는데 running 이
    없으면 커밋하고 디스패치 태스크를 다시 보낸다(API 의 send_dispatch 가 브로커에 못 넣었거나 디스패처가
    죽어 줄이 멈춘 경우 — 생성은 running 1건이 끝나야 다음이 돈다). beat 일정은 그대로다(10분).
    회수로 failed 가 된 잡은 대기 순번 ZSET 에서도 뺀다(Redis·브로커는 커밋 뒤).
    """
    db = SyncSessionLocal()
    try:
        # coalesce 가 필요한 이유: planning 단계에서 워커가 죽으면 started_at 이 NULL
        # 일 수 있고, NULL 비교는 NULL 이라 조건이 참이 되지 않아 영원히 회수되지 않는다.
        # 회수한 잡의 running step 도 같은 문장에서 닫는다 — 따로 두면 잡은 failed 인데
        # 마지막 step 은 자기 updated_at 기준으로 한참 더 running 으로 보인다.
        n_jobs, n_job_steps, reaped_ids = db.execute(sa_text(
            "WITH reaped AS ("
            "  UPDATE research_jobs SET status = 'failed', "
            "         last_error = 'stale — 워커 응답 없음', finished_at = now() "
            "  WHERE status IN ('planning', 'running') "
            "    AND coalesce(started_at, created_at) < now() - make_interval(mins => :m) "
            "  RETURNING id"
            "), closed AS ("
            "  UPDATE research_steps SET status = 'failed', "
            "         result = result || '{\"error\": \"stale — 워커 응답 없음\"}'::jsonb, "
            "         finished_at = now() "
            "  WHERE status = 'running' AND job_id IN (SELECT id FROM reaped) "
            "  RETURNING id"
            ") SELECT (SELECT count(*) FROM reaped), (SELECT count(*) FROM closed), "
            "         (SELECT coalesce(array_agg(id::text), '{}'::text[]) FROM reaped)"
        ), {"m": STALE_MINUTES}).one()

        steps = db.execute(sa_text(
            "UPDATE research_steps SET status = 'failed', "
            "       result = result || '{\"error\": \"stale — 워커 응답 없음\"}'::jsonb, "
            "       finished_at = now() "
            "WHERE status = 'running' "
            "  AND updated_at < now() - make_interval(mins => :m) "
            "RETURNING job_id"
        ), {"m": STALE_MINUTES}).fetchall()

        # started_at 은 디스패처가 running 으로 바꾸는 문장에서 함께 쓴다. 비어 있는 running 행이 생겨도
        # 영원히 남아 디스패치 줄 전체를 막지 않게 잡과 같이 created_at 으로 물러난다
        n_gen = db.execute(sa_text(
            "UPDATE research_generations SET status = 'failed', "
            "       error = 'stale — 워커 응답 없음', finished_at = now(), updated_at = now() "
            "WHERE status = 'running' "
            "  AND coalesce(started_at, created_at) < now() - make_interval(secs => :s)"
        ), {"s": GEN_STALE_SECONDS}).rowcount

        # 방금 회수한 running 이 빠진 뒤에 센다
        idle = db.execute(sa_text(
            "SELECT EXISTS (SELECT 1 FROM research_generations WHERE status = 'queued') "
            "   AND NOT EXISTS (SELECT 1 FROM research_generations WHERE status = 'running')"
        )).scalar_one()

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # 커밋 뒤에 보낸다 — 커밋 전에 보내면 디스패처가 아직 running 인 회수 대상을 보고 그냥 끝난다
    if reaped_ids:
        unmark_many_sync(list(reaped_ids))
    redispatched = bool(idle) and send_dispatch()
    return {"jobs": n_jobs, "steps": n_job_steps + len(steps),
            "generations": n_gen, "redispatched": redispatched}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `105 passed` (Task 7 뒤 96 + 새 9)

회수기가 부르는 모듈과 디스패처 쪽:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_tasks.py tests/test_research_work_tasks.py tests/test_research_run_queue.py tests/test_celery_schedule.py tests/test_research_relay.py tests/test_research_work_dispatch.py -q -p no:cacheprovider`

Expected: `183 passed` (105 + 17 + 23 + 2 + 14 + 22)

두 태스크 모듈을 한 세션에서 차례로 불러도 서로의 더미를 물려받지 않는지:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_tasks.py tests/test_research_tasks.py -q -p no:cacheprovider`

Expected: `122 passed` (17 + 105)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 0, `3 errors` 그대로. 이 작업은 9개를 더한다(Task 9 뒤 수 + 9) — 검증 사본에서 `1602 passed` → `1611 passed, 1 skipped, 2 warnings, 3 errors`.

- [ ] **Step 5: 커밋한다**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/workers/research_tasks.py app/tests/test_research_tasks.py && git status --short && git commit -m "[Feat] round06a — 딥리서치 회수기(tasks.reap_stale_research)를 넓힌다: 같은 트랜잭션에서 디스패치 하드 리밋 + 60초(1140초)를 넘긴 running 생성을 failed 로 두고, queued 생성이 남았는데 running 이 없으면 커밋 뒤 디스패치 태스크를 q_research_plan 으로 다시 보낸다(브로커 전달 실패·디스패처 사망으로 멈춘 줄을 푼다). 회수로 failed 가 된 딥리서치 잡은 대기 순번 ZSET 에서도 뺀다. 반환에 generations·redispatched 를 더하고 시간 제한·큐·beat 일정은 그대로 둔다"
```

---


### Task 11: 연구 API — 이어가기·조회·근거 풀·이어간 연구 목록·생성 취소/다시·연구 SSE

spec §5-2(이어가기 06a 줄)·§6-2(API 표의 연구·근거·생성 줄)·§6-4(실시간 이벤트)·§4 시연 정직성 규칙(예시 연구는 읽기 전용), 계약 §11. 보고서 끝 [이 연구 이어가기] 로 완료된 딥리서치 잡이 연구 한 건(`research_works`, id = 잡 id)이 되고, 06a 의 연구 화면·근거 장부·[담기] 메뉴가 읽을 API 를 새 라우터 `app/api/research_work.py` 에 둔다. 응답 모양은 순수 함수 모듈 `app/services/research_work/views.py` 가 만든다.

**알아 둘 것:**
- **앞 task 에 기댄다(여기서 다시 만들지 않는다):** Task 1 의 모델(`models/research_work.py`)·테스트 DB(`history_sqlite` 의 `add_work`·`add_generation`, 세션 `get`·`add`·`flush`·`scalar`, 빈 함수 `pg_advisory_xact_lock`), Task 8 의 `services/research_work/concepts.py`(`MAX_CONCEPTS`·`clean_concepts`·`concepts_input`)·`generate.py`(`run_generation`)·`executors.py`(`EXECUTORS`), Task 9 의 `services/research_work/dispatch.py`(`pick_next`·`finish`·`queue_position`)·`apply.py`(`apply_result`)·`services/research/relay.py`(`publish_work`·`subscribe_work`)·`workers/research_work_tasks.py`(`send_dispatch`, generation 이벤트). 이 task 는 그 모듈들을 고치지 않는다.
- **디스패치는 보낼 때만 import 한다:** 라우터는 `workers.research_work_tasks` 를 `_send_dispatch()` 안에서 import 한다(`api/research.py` 의 `_enqueue` 와 같은 방식 — celery 를 라우터 import 에 끌어오지 않는다). 테스트는 `sys.modules["workers.research_work_tasks"]` 에 가짜 모듈을 꽂는다. `send_dispatch` 가 False 를 돌려주거나 예외를 올려도 응답은 그대로다 — 행은 이미 커밋됐고 회수기(Task 10)가 queued 를 보고 다시 보낸다.
- **이어가기 멱등:** `INSERT … ON CONFLICT DO NOTHING RETURNING id` 로 연구 행을 만든 요청만 후보(`research_reading`)·핵심 개념 생성 1건을 넣고 디스패치·`work` 이벤트를 보낸다. 동시에 두 번 눌러도 Postgres 는 뒤 요청의 INSERT 를 앞 요청의 커밋까지 기다린 뒤 아무것도 넣지 않는다. 이미 있는 연구면 지금 모양을 200 으로 돌려주고, 그 연구가 예시면 409 다. SQLite 대역(3.35 이상)도 같은 문장을 그대로 돌린다.
- **JSONB NOT NULL 칼럼:** 테스트 DB 는 `'::jsonb'` 서버 기본값을 빼므로(계약 §1) 연구 행 삽입에 `concepts=[]`·`concept_members={}`·`progress={}` 를 함께 준다(계약 §11 의 `values(id=…, owner_sid=…)` 에 세 칼럼을 더한 것 — 운영에서도 같은 값이다).
- **생성 이벤트의 생성 종류는 `gen_kind`:** relay 는 `{"kind": kind, **payload}` 로 이벤트를 싣는다(`publish` 와 같은 방식 — `publish_work` 도 그렇다). 페이로드에 `"kind": "concepts"` 를 두면 이벤트 종류 `"generation"` 을 덮어써 화면이 생성 이벤트를 알아보지 못한다. 그래서 generation 페이로드는 `{"gen_id", "gen_kind", "target", "status", "model", "result"}` 이고, Task 9 의 워커(`_close`)가 끝난 생성을 알리는 이벤트도 같은 키다 — 둘이 갈리면 연구 화면의 리듀서가 두 모양을 받는다. `TestEventShape` 가 워커 소스에서 `publish_work(…, "generation", {…})` 의 키를 확인한다(워커는 celery 를 끌어오므로 import 하지 않고 소스만 읽는다).
- **이어가기 `work` 이벤트:** `{"phase", "progress"}` (spec §6-4 `work`(phase·progress)).
- **생성 다시(retry):** failed·canceled, 그리고 빈 결과로 끝난 핵심 개념(kind=concepts·status=done·`output.concepts` 가 빔)만 다시 부른다 — spec §5-2 '끝내 못 얻으면 비운 채 done … 다시 부르기는 `POST .../generations/{gid}/retry`', §6-2 '핵심 개념 다시 부르기 포함'(계약 §11 의 'failed·canceled' 보다 넓다). 개념이 채워진 done·열린 생성은 409. 같은 kind·target·input·priority 로 새 행. 같은 kind·target 의 열린 생성(queued·running)이 이미 있으면 409 — 두 번 눌러 같은 일이 두 줄 서지 않게(계약에 없는 작은 규칙). 동시에 두 번 눌러도 한 줄만 서도록 검사 앞에서 (연구·kind·target) 키(`_retry_lock_key`, `api/research.py` 의 `_browser_lock_key` 와 같은 sha256 앞 8바이트)로 `pg_advisory_xact_lock` 을 잡는다 — 커밋까지 쥐므로 뒤 요청은 앞 요청이 넣은 행을 보고 409 다. 새 행을 `generation`(queued) 이벤트로도 알린다(다른 탭의 SSE 가 새 줄을 안다).
- **생성 취소(cancel)는 queued 만:** queued → canceled 조건부 UPDATE(`status='queued'` 조건), `finished_at` 을 찍고 `generation`(canceled) 이벤트. running 은 409 `"진행 중인 생성은 끝날 때까지 기다립니다"`(계약 §11 의 'queued·running' 과 다른 점). 도는 생성을 canceled 로 바꾸면 디스패처의 전역 한 자리(`pick_next` 는 running 만 센다)가 곧바로 비지만, 워커의 LLM 호출은 최대 GEN_DEADLINE(960초)까지 `q_research_plan` 한 자리를 계속 쓴다 — 그 사이 다른 사람의 이어가기·다시나 회수기가 보낸 디스패치가 다음 생성을 남은 자리에서 돌리면 두 자리를 생성이 다 써서 새 딥리서치의 계획이 밀린다(D15). 읽은 뒤 디스패처가 집었으면(queued → running) 조건부 UPDATE 가 바꾸지 않아 409 다. 취소는 디스패치를 보내지 않는다(queued 한 줄이 빠질 뿐이다).
- **PATCH:** `concepts` 는 1~5개(pydantic — 비었거나 6개 이상·문자열 아님은 422), `clean_concepts` 로 정리한 결과가 비면 422, 정리한 값이 지금과 다를 때만 `concept_members = {}`(다시 계산은 06c). 개념을 바꾸는 요청은 그 연구의 concepts 생성이 열려 있으면(queued·running) 409 `"핵심 개념을 만드는 중입니다 — 끝난 뒤 고쳐 주세요"` — 워커의 결과 적용(`apply_result`)이 끝나며 칩을 덮어쓰고 개념 소속을 비워 사용자가 고친 개념이 소리 없이 사라진다. 같은 개념·메모만 고치는 요청은 막지 않는다. `memo` 는 본문에 있을 때만 바꾼다(개념만 고쳐도 메모는 그대로) — 2,000자 상한(초과 422), 빈 문자열은 지운다(NULL). 둘 다 없으면 바꾸지 않고 지금 모양을 돌려준다.
- **근거 풀(pool)은 연구 행 없이 읽는다:** 근거 장부(06b)가 이어가기 전·탐색 중에도 읽는다. 채택 근거는 스냅숏(탐색 끝에 저장)이 있으면 그 evidence 전부(보고서에 인용되지 않은 것 포함), 없으면 탐색 단계의 회차 중 adopted_papers 가 있는 마지막 회차(재시도로 같은 하위질문의 탐색 단계가 또 생기면 seq 가 큰 쪽). 여러 하위질문에 든 논문의 `rank` 는 가장 앞선 순위. 제외 논문은 보고서 trail 의 excluded_papers(없으면 회차의 excluded_papers)에 하위질문 번호·회차·그 회차 note 를 붙인다 — 논문별 제외 사유는 저장된 곳이 없다(spec §5-4).
- **이어간 연구 목록:** 이 브라우저(owner_sid)의 연구를 먼저 읽고, 그 id 들을 `history_items.ref_id IN (…)` 로 한 번 더 걸러 기록에 남은(kind='research', 지우지 않은) 것만 둔다. `research_works.id::text` 로 history_items 와 조인하지 않는다 — 문자열 ref_id 조인은 PK 인덱스를 못 쓰고 SQLite 대역의 UUID 문자열 표기도 다르다(`repositories/history.py` `_research_statuses` 의 주석과 같은 이유). 새 것부터 최대 50건(`MAX_WORK_LIST` — 계약에 없는 상한, [담기] 메뉴용). `?example=1` 은 예시 연구(브라우저 무관, 헤더는 여전히 필요).
- **생성 대기 순번:** 연구 응답의 queued 생성마다 `queue_position` 을 부른다. 06a 는 열린 생성이 연구마다 1~2건이다 — 06c 에서 특징 추출 생성이 수십 건 열리면 한 번의 질의로 세게 바꾼다. spec §6-3·§6-4 의 생성 예상 시간(kind 별 최근 완료분 소요 시간 중앙값의 합)·'다른 연구 작업 진행 중' 표시·generation 이벤트의 순번은 연구 화면을 만드는 06b 로 미룬다 — 06a 화면은 생성 대기를 그리지 않으므로 06a 응답은 `position` 만 싣는다.
- **끝까지 한 번(spec §8 '새 라우터 API 를 가짜 LLM 으로 끝까지'):** `TestEndToEnd` 가 이어가기 → Task 9 의 `pick_next` → Task 8 의 `run_generation(EXECUTORS[kind], …, chat_fn=가짜)` → `apply_result` → `finish(done)` 을 같은 SQLite 에서 돌리고, 연구 조회에 개념과 done 생성(순번 없음)이 보이는지 본다. 대기 순번은 여기서도 가짜다 — SQLite 대역은 `created_at` 을 문자열로 비교해(서버 기본값 `'… HH:MM:SS'` 와 바인딩한 `'… HH:MM:SS.ffffff'`) 진짜 `queue_position` 이 자기 자신을 앞으로 센다. 순번 계산은 Task 9 테스트의 몫이고, 워커 태스크 본문(celery·태스크 엔진)도 그렇다.
- **연구 SSE:** 접속 직후 `{"kind": "snapshot", "work": <연구 응답>}` 한 번, 그 뒤 `subscribe_work(str(jid))` 이벤트를 그대로, 조용하면 `": ping"`. 하트비트 때 DB 를 다시 읽지 않는다(06a). 대문자 경로로 붙어도 표준형 id 채널을 구독한다.
- **테스트 DB:** API 테스트가 `research_steps`(근거 풀)·`research_reading`(후보)을 SQLite 에서 쓰므로 `history_sqlite.make_engine` 의 테이블 튜플에 둘을 더한다(Task 1 의 메모대로). Task 2~10 은 이 튜플을 고치지 않는다. BIGINT PK(`research_steps.id`) 는 Task 1 의 칼럼 고리가 SQLite 자동 번호로 바꾼다.
- `main.py`·`history_sqlite.py` 는 CRLF 다 — Edit 도구로 고친다. 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다(`core.autocrlf=true`). 행 번호는 Task 1 뒤 기준이다.

**Files:**
- Create: `app/services/research_work/views.py`
- Create: `app/api/research_work.py`
- Modify: `app/main.py` (Task 1 뒤 기준 라우터 import 14행 `from api.history import …` 뒤, 92행 `app.include_router(history_router)` 뒤)
- Modify: `app/tests/history_sqlite.py` (Task 1 뒤 기준 import 23-24행, `make_engine` 테이블 튜플 48-49행)
- Test: `app/tests/test_research_work_views.py` (새 파일), `app/tests/test_research_work_api.py` (새 파일)

- [ ] **Step 1: 응답 모양 순수 함수의 실패하는 테스트를 쓴다**

워커가 실제로 저장하는 모양(state_snapshot·report.trail·research_steps.result.rounds)을 흉내 낸다. 하위질문 0 은 06a 뒤 잡의 회차(adopted_papers 있음), 하위질문 1 은 06a 전 잡의 회차(없음)다.

`app/tests/test_research_work_views.py` (새 파일, 전체):

```python
"""services/research_work/views.py — 연구 어시스턴트 API 응답을 만드는 순수 함수.

입력은 워커가 실제로 저장하는 모양(state_snapshot·report.trail·research_steps.result.rounds)을
그대로 흉내 낸다. 06a 뒤 잡의 회차에는 adopted_papers 가 있고(Task 3), 그 전 잡에는 없다.
"""
import json
import uuid
from types import SimpleNamespace

from services.research_work.views import candidates_from_snapshot, pool_from_job, work_view

X1 = {"cnts_id": "X1", "title": "무관 논문", "personal_author": "박민수", "pub_date": "2015"}
X2 = {"cnts_id": "X2", "title": "다른 뜻 논문", "personal_author": "최", "pub_date": "2012"}
C1_BRIEF = {"cnts_id": "C1", "title": "독서 격차 연구", "personal_author": "김철수",
            "pub_date": "2019-03"}
C2_BRIEF = {"cnts_id": "C2", "title": "학교 도서관", "personal_author": "이영희", "pub_date": "2017"}
C3_BRIEF = {"cnts_id": "C3", "title": "가정 독서 환경", "personal_author": "정", "pub_date": "2011"}

# 하위질문 0 — 06a 뒤 잡(회차마다 adopted_papers). 1회차에 C1 채택·X1 제외, 2회차에 C2 채택.
ROUNDS_0 = [
    {"round": 1, "query": "독서 격차 원인", "found_chunks": 9, "new_papers": 2,
     "verdict": "insufficient", "note": "가정 요인이 부족하다", "next_query": "가정 독서 환경",
     "excluded": 1, "excluded_papers": [X1], "flagged": 0, "flagged_papers": [],
     "adopted_papers": [{**C1_BRIEF, "rank": 1, "new": True}]},
    {"round": 2, "query": "가정 독서 환경", "found_chunks": 7, "new_papers": 1,
     "verdict": "sufficient", "note": "충분하다", "next_query": None,
     "excluded": 0, "excluded_papers": [], "flagged": 0, "flagged_papers": [],
     "adopted_papers": [{"cnts_id": "C1", "rank": 1}, {**C2_BRIEF, "rank": 2, "new": True}]},
]
# 하위질문 1 — 06a 전 잡과 같은 회차(adopted_papers 없음). 1회차에 X2 제외.
ROUNDS_1 = [
    {"round": 1, "query": "독서 격차 영향", "found_chunks": 5, "new_papers": 2,
     "verdict": "insufficient", "note": "영향 연구가 적다", "next_query": None,
     "excluded": 1, "excluded_papers": [X2], "flagged": 0, "flagged_papers": []},
]


def _snapshot() -> dict:
    return {
        "question": "청소년 독서 격차",
        "params": {},
        "corpus_range": {"from": "2002", "to": "2026", "n_papers": 72054},
        "subquestions": [
            {"idx": 0, "text": "독서 격차의 원인", "queries": ["독서 격차 원인", "가정 독서 환경"],
             "evidence_ids": ["E1", "E2"], "verdict": "sufficient", "parse_failed": False,
             "failed": False, "note": "충분하다", "capped": 0, "budget_capped": 0,
             "evidence_chunks": {"E1": ["c1", "c2"], "E2": ["c3"]},
             "chunk_scores": {"c1": 0.91, "c2": 0.7, "c3": 0.65},
             "rounds": ROUNDS_0, "excluded_cnts": ["X1"]},
            {"idx": 1, "text": "독서 격차의 영향", "queries": ["독서 격차 영향"],
             "evidence_ids": ["E3", "E1"], "verdict": "insufficient", "parse_failed": False,
             "failed": False, "note": "영향 연구가 적다", "capped": 0, "budget_capped": 0,
             "evidence_chunks": {"E3": ["c4"], "E1": ["c1"]},
             "chunk_scores": {"c4": 0.8, "c1": 0.5},
             "rounds": ROUNDS_1, "excluded_cnts": ["X2"]},
        ],
        "evidence": {
            "E1": {"cnts_id": "C1", "meta": {**C1_BRIEF, "series_title": "교육학연구"},
                   "chunks": [{"chunk_id": "c1", "text": "가", "page_start": 1, "page_end": 1,
                               "score": 0.91}]},
            "E2": {"cnts_id": "C2", "meta": {**C2_BRIEF, "series_title": None}, "chunks": []},
            "E3": {"cnts_id": "C3", "meta": {**C3_BRIEF, "series_title": "독서연구"}, "chunks": []},
        },
        "evidence_seq": 3,
        "seen_cnts": ["C1", "C2", "C3", "X1", "X2"],
    }


def _steps(rounds_0=ROUNDS_0, rounds_1=ROUNDS_1) -> list[dict]:
    return [
        {"seq": 1, "kind": "search", "subq_idx": 0, "status": "done", "result": {"rounds": rounds_0}},
        {"seq": 2, "kind": "search", "subq_idx": 1, "status": "done", "result": {"rounds": rounds_1}},
    ]


class TestCandidatesFromSnapshot:
    def test_no_snapshot_means_no_candidates(self):
        assert candidates_from_snapshot(None) == []
        assert candidates_from_snapshot({}) == []

    def test_every_adopted_paper_becomes_a_candidate_with_its_stored_path(self):
        assert candidates_from_snapshot(_snapshot()) == [
            {"cnts_id": "C1", "origin": "evidence", "origin_ref": {
                "subq_idx": [0, 1], "rank": {"0": 1, "1": 2},
                "chunks": {"0": ["c1", "c2"], "1": ["c1"]},
                "chunk_scores": {"0": {"c1": 0.91, "c2": 0.7}, "1": {"c1": 0.5}},
                "verdict": {"0": "sufficient", "1": "insufficient"},
                "first_round": {"0": 1}}},
            {"cnts_id": "C2", "origin": "evidence", "origin_ref": {
                "subq_idx": [0], "rank": {"0": 2}, "chunks": {"0": ["c3"]},
                "chunk_scores": {"0": {"c3": 0.65}}, "verdict": {"0": "sufficient"},
                "first_round": {"0": 2}}},
            # 하위질문 1 의 회차에는 adopted_papers 가 없다(06a 전 잡) — 처음 채택된 회차를 비운다
            {"cnts_id": "C3", "origin": "evidence", "origin_ref": {
                "subq_idx": [1], "rank": {"1": 1}, "chunks": {"1": ["c4"]},
                "chunk_scores": {"1": {"c4": 0.8}}, "verdict": {"1": "insufficient"}}},
        ]

    def test_path_survives_a_jsonb_round_trip(self):
        # 하위질문 번호 키를 문자열로 둔다 — 정수 키는 JSONB 에 저장되며 문자열이 되어 읽은 값이 달라진다
        out = candidates_from_snapshot(_snapshot())
        assert json.loads(json.dumps(out)) == out

    def test_evidence_outside_every_subquestion_is_kept_last_without_a_path(self):
        snap = _snapshot()
        snap["evidence"]["E9"] = {"cnts_id": "C9", "meta": {"title": "외톨이"}, "chunks": []}
        assert candidates_from_snapshot(snap)[-1] == {
            "cnts_id": "C9", "origin": "evidence",
            "origin_ref": {"subq_idx": [], "rank": {}, "chunks": {}, "chunk_scores": {},
                           "verdict": {}},
        }

    def test_one_row_per_paper(self):
        # research_reading 의 PK 는 (work_id, cnts_id) — 같은 논문이 두 번 나오면 한 INSERT 안에서 부딪친다
        snap = _snapshot()
        snap["evidence"]["E4"] = {"cnts_id": "C1", "meta": {}, "chunks": []}
        snap["subquestions"][1]["evidence_ids"].append("E4")
        ids = [c["cnts_id"] for c in candidates_from_snapshot(snap)]
        assert ids == ["C1", "C2", "C3"]


class TestPoolFromJob:
    def test_completed_job_lists_every_adopted_paper_from_the_snapshot(self):
        job = SimpleNamespace(state_snapshot=_snapshot(), report={"trail": []})
        pool = pool_from_job(job, _steps())
        assert pool["adopted"] == [
            {**C1_BRIEF, "series_title": "교육학연구", "subq_idx": [0, 1], "rank": 1},
            {**C2_BRIEF, "series_title": None, "subq_idx": [0], "rank": 2},
            {**C3_BRIEF, "series_title": "독서연구", "subq_idx": [1], "rank": 1},
        ]

    def test_paper_in_two_subquestions_takes_its_best_rank(self):
        snap = _snapshot()
        snap["subquestions"][1]["evidence_ids"] = ["E2", "E3", "E1"]
        job = SimpleNamespace(state_snapshot=snap, report=None)
        adopted = pool_from_job(job, [])["adopted"]
        assert [(p["cnts_id"], p["subq_idx"], p["rank"]) for p in adopted] == [
            ("C1", [0, 1], 1), ("C2", [0, 1], 1), ("C3", [1], 2),
        ]

    def test_completed_job_takes_excluded_papers_from_the_trail_with_round_and_note(self):
        trail = [{"subquestion": "독서 격차의 원인", "excluded_papers": [X1]},
                 {"subquestion": "독서 격차의 영향", "excluded_papers": [X2]}]
        job = SimpleNamespace(state_snapshot=_snapshot(), report={"trail": trail})
        assert pool_from_job(job, _steps())["excluded"] == [
            {**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"},
            {**X2, "subq_idx": 1, "round": 1, "note": "영향 연구가 적다"},
        ]

    def test_trail_paper_excluded_in_two_subquestions_takes_its_own_subquestions_round(self):
        # X1 은 하위질문 0 의 1회차와 하위질문 1 의 2회차에서 빠졌다 — 회차는 trail 항목의 하위질문에서 찾는다
        rounds_1 = [*ROUNDS_1, {"round": 2, "query": "독서 격차 결과", "found_chunks": 4,
                                "new_papers": 0, "verdict": "insufficient",
                                "note": "다른 뜻으로 쓴 논문이다", "next_query": None, "excluded": 1,
                                "excluded_papers": [X1], "flagged": 0, "flagged_papers": []}]
        trail = [{"excluded_papers": [X1]}, {"excluded_papers": [X2, X1]}]
        job = SimpleNamespace(state_snapshot=_snapshot(), report={"trail": trail})
        assert pool_from_job(job, _steps(rounds_1=rounds_1))["excluded"] == [
            {**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"},
            {**X2, "subq_idx": 1, "round": 1, "note": "영향 연구가 적다"},
            {**X1, "subq_idx": 1, "round": 2, "note": "다른 뜻으로 쓴 논문이다"},
        ]

    def test_trail_paper_without_a_round_record_keeps_round_and_note_empty(self):
        # 회차 기록이 없는 옛 잡 — trail 의 서지는 그대로 싣는다
        job = SimpleNamespace(state_snapshot=_snapshot(),
                              report={"trail": [{"excluded_papers": [X1]}]})
        assert pool_from_job(job, [])["excluded"] == [
            {**X1, "subq_idx": 0, "round": None, "note": None},
        ]

    def test_running_job_builds_the_pool_from_the_rounds(self):
        job = SimpleNamespace(state_snapshot=None, report=None)
        pool = pool_from_job(job, _steps())
        # 하위질문 0 은 마지막 회차의 adopted_papers 가 지금 채택 목록이다. 서지는 새로 채택된 회차의 값.
        # 하위질문 1 은 06a 전 회차라 채택 목록이 없다
        assert pool["adopted"] == [
            {**C1_BRIEF, "series_title": None, "subq_idx": [0], "rank": 1},
            {**C2_BRIEF, "series_title": None, "subq_idx": [0], "rank": 2},
        ]
        assert pool["excluded"] == [
            {**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"},
            {**X2, "subq_idx": 1, "round": 1, "note": "영향 연구가 적다"},
        ]

    def test_running_job_merges_a_paper_adopted_by_two_subquestions(self):
        # C2 는 하위질문 0 에서 2위, 1 에서 1위 — 가장 앞선 순위를 쓴다
        rounds_1 = [{**ROUNDS_1[0], "adopted_papers": [
            {**C2_BRIEF, "rank": 1, "new": True}, {**C3_BRIEF, "rank": 2, "new": True}]}]
        job = SimpleNamespace(state_snapshot=None, report=None)
        adopted = pool_from_job(job, _steps(rounds_1=rounds_1))["adopted"]
        assert [(p["cnts_id"], p["subq_idx"], p["rank"]) for p in adopted] == [
            ("C1", [0], 1), ("C2", [0, 1], 1), ("C3", [1], 2),
        ]

    def test_retried_search_step_replaces_the_earlier_one(self):
        # 재시도로 같은 하위질문의 탐색 단계가 새로 생기면 뒤(seq 가 큰) 단계가 지금 상태다
        later = [{**ROUNDS_0[0], "excluded_papers": [], "adopted_papers": [
            {**C2_BRIEF, "rank": 1, "new": True}]}]
        steps = [*_steps(), {"seq": 3, "kind": "search", "subq_idx": 0, "status": "running",
                             "result": {"rounds": later}}]
        pool = pool_from_job(SimpleNamespace(state_snapshot=None, report=None), steps)
        assert [p["cnts_id"] for p in pool["adopted"]] == ["C2"]
        assert [p["cnts_id"] for p in pool["excluded"]] == ["X2"]

    def test_nothing_recorded_yet(self):
        job = SimpleNamespace(state_snapshot=None, report=None)
        assert pool_from_job(job, []) == {"adopted": [], "excluded": []}
        steps = [{"seq": 1, "kind": "search", "subq_idx": 0, "status": "running", "result": {}}]
        assert pool_from_job(job, steps) == {"adopted": [], "excluded": []}


def _gen(id, status, **kw):
    return SimpleNamespace(id=id, kind=kw.get("kind", "concepts"), target=kw.get("target"),
                           status=status, model=kw.get("model"), error=kw.get("error"))


class TestWorkView:
    def test_shape(self):
        work = SimpleNamespace(
            id="0b9f6c3e-1d2a-4f5b-8c7d-6e5f4a3b2c1d", phase="topics",
            concepts=["독서 격차", "청소년"], memo="메모", is_example=False, progress={"topics": 0},
        )
        gens = [_gen(7, "queued"), _gen(3, "done", model="qwen3-vl-8b"),
                _gen(5, "failed", error="시간 초과")]
        assert work_view(work, gens, {7: 2}) == {
            "id": "0b9f6c3e-1d2a-4f5b-8c7d-6e5f4a3b2c1d", "phase": "topics",
            "concepts": ["독서 격차", "청소년"], "memo": "메모", "is_example": False,
            "progress": {"topics": 0},
            "generations": [
                {"id": 3, "kind": "concepts", "target": None, "status": "done",
                 "model": "qwen3-vl-8b", "error": None, "position": None},
                {"id": 5, "kind": "concepts", "target": None, "status": "failed",
                 "model": None, "error": "시간 초과", "position": None},
                {"id": 7, "kind": "concepts", "target": None, "status": "queued",
                 "model": None, "error": None, "position": 2},
            ],
        }

    def test_id_is_a_string(self):
        wid = uuid.uuid4()
        work = SimpleNamespace(id=wid, phase="topics", concepts=[], memo=None, is_example=True,
                               progress={})
        view = work_view(work, [], {})
        assert view["id"] == str(wid) and view["is_example"] is True and view["generations"] == []
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_views.py -q -p no:cacheprovider`

Expected: `1 error` — 수집 단계 `ModuleNotFoundError: No module named 'services.research_work.views'` (패키지 `services/research_work` 는 Task 8 이 만들었다).

- [ ] **Step 3: `views.py` 를 만든다**

`app/services/research_work/views.py` (새 파일, 전체):

```python
"""views.py — 연구 어시스턴트 API 의 응답 모양을 만드는 순수 함수(DB·네트워크 없음).

- work_view: GET /api/research/{id}/work·이어가기 응답·연구 SSE 의 snapshot 이 같은 모양을 쓴다 — 갈리면 새로고침한
  화면과 재접속한 화면이 같은 연구를 다르게 그린다.
- candidates_from_snapshot: 이어가기 때 채택 근거 전체(state_snapshot.evidence)를 읽기 목록 후보로 넣는
  값. 들어온 경로(origin_ref)는 저장된 값만 쓴다(spec §5-4) — 탐색 때만 있던 rank_score 는 저장되지
  않으므로 쓰지 않는다.
- pool_from_job: GET /api/research/{id}/pool — 채택 근거 전체(보고서에 인용되지 않은 것 포함)와 critic 이 뺀 논문.

하위질문 번호를 키로 쓰는 dict 는 문자열 키다("0", "1") — JSONB 에 저장되면 정수 키가 문자열이 되므로,
처음부터 문자열로 두어야 넣은 값과 읽은 값이 같다.
"""


def work_view(work, generations, positions: dict[int, int]) -> dict:
    """연구 한 건. generations 는 호출부가 고른 생성(열린 것 전부 + 최근 끝난 것)이고 id 순으로 싣는다.
    positions 는 대기 중(queued) 생성의 대기 순번 — 없는 생성은 None."""
    return {
        "id": str(work.id),
        "phase": work.phase,
        "concepts": list(work.concepts or []),
        "memo": work.memo,
        "is_example": bool(work.is_example),
        "progress": dict(work.progress or {}),
        "generations": [
            {"id": g.id, "kind": g.kind, "target": g.target, "status": g.status,
             "model": g.model, "error": g.error, "position": positions.get(g.id)}
            for g in sorted(generations, key=lambda g: g.id)
        ],
    }


def _empty_path() -> dict:
    return {"subq_idx": [], "rank": {}, "chunks": {}, "chunk_scores": {}, "verdict": {}}


def _first_rounds(sq: dict) -> dict[str, int]:
    """cnts_id → 이 하위질문에서 처음 채택된 회차. 회차의 adopted_papers(06a 뒤 잡)에서만 안다."""
    first: dict[str, int] = {}
    for r in sq.get("rounds") or []:
        for p in r.get("adopted_papers") or []:
            first.setdefault(p.get("cnts_id"), r.get("round"))
    return first


def candidates_from_snapshot(snapshot: dict | None) -> list[dict]:
    """research_reading 삽입 값 — 채택 근거 한 편당 한 행. 순서는 하위질문 순 → 그 안의 순위 순."""
    if not snapshot:
        return []
    evidence = snapshot.get("evidence") or {}
    paths: dict[str, dict] = {}            # eid → origin_ref
    for sq in snapshot.get("subquestions") or []:
        key = str(sq.get("idx"))
        chunks_of = sq.get("evidence_chunks") or {}
        scores = sq.get("chunk_scores") or {}
        first = _first_rounds(sq)
        for rank, eid in enumerate(sq.get("evidence_ids") or [], start=1):
            ev = evidence.get(eid)
            if ev is None:
                continue
            path = paths.setdefault(eid, _empty_path())
            chunk_ids = list(chunks_of.get(eid) or [])
            path["subq_idx"].append(sq.get("idx"))
            path["rank"][key] = rank
            path["chunks"][key] = chunk_ids
            path["chunk_scores"][key] = {c: scores[c] for c in chunk_ids if c in scores}
            path["verdict"][key] = sq.get("verdict")
            if ev.get("cnts_id") in first:
                path.setdefault("first_round", {})[key] = first[ev["cnts_id"]]
    for eid in evidence:
        # 어느 하위질문에도 남지 않은 근거(무관 제외가 지우지 못한 옛 스냅샷) — 경로 없이 뒤에 둔다
        paths.setdefault(eid, _empty_path())

    out: list[dict] = []
    seen: set[str] = set()
    for eid, path in paths.items():
        cnts_id = (evidence.get(eid) or {}).get("cnts_id")
        if not cnts_id or cnts_id in seen:
            continue
        seen.add(cnts_id)
        out.append({"cnts_id": cnts_id, "origin": "evidence", "origin_ref": path})
    return out


def _brief(p: dict) -> dict:
    return {"cnts_id": p.get("cnts_id"), "title": p.get("title"),
            "personal_author": p.get("personal_author"), "pub_date": p.get("pub_date")}


def _rounds_by_subq(steps: list[dict]) -> dict[int, list[dict]]:
    """하위질문 번호 → 탐색 단계의 회차 기록. steps 는 seq 순 — 재시도로 같은 하위질문의 탐색 단계가
    다시 생기면 뒤의 것이 지금 상태다."""
    out: dict[int, list[dict]] = {}
    for s in steps:
        if s.get("kind") != "search" or s.get("subq_idx") is None:
            continue
        out[s["subq_idx"]] = list((s.get("result") or {}).get("rounds") or [])
    return out


def _adopted_from_snapshot(snapshot: dict) -> list[dict]:
    evidence = snapshot.get("evidence") or {}
    items: dict[str, dict] = {}            # eid → 항목
    for sq in snapshot.get("subquestions") or []:
        for rank, eid in enumerate(sq.get("evidence_ids") or [], start=1):
            ev = evidence.get(eid)
            if ev is None:
                continue
            item = items.get(eid)
            if item is None:
                meta = ev.get("meta") or {}
                item = items[eid] = {**_brief({**meta, "cnts_id": ev.get("cnts_id")}),
                                     "series_title": meta.get("series_title"),
                                     "subq_idx": [], "rank": rank}
            item["subq_idx"].append(sq.get("idx"))
            # 여러 하위질문에 채택된 논문은 그중 가장 앞선 순위
            item["rank"] = min(item["rank"], rank)
    for eid, ev in evidence.items():
        if eid not in items:
            meta = ev.get("meta") or {}
            items[eid] = {**_brief({**meta, "cnts_id": ev.get("cnts_id")}),
                          "series_title": meta.get("series_title"), "subq_idx": [], "rank": None}
    return list(items.values())


def _adopted_from_rounds(rounds: dict[int, list[dict]]) -> list[dict]:
    """도는 잡 — 하위질문마다 adopted_papers 가 있는 마지막 회차가 지금 채택 목록이다(순위순).
    서지는 그 논문이 새로 채택된 회차에만 실리므로 모든 회차에서 모은다. 학술지는 회차에 없다."""
    briefs: dict[str, dict] = {}
    for idx_rounds in rounds.values():
        for r in idx_rounds:
            for p in r.get("adopted_papers") or []:
                if p.get("new"):
                    briefs.setdefault(p["cnts_id"], p)
    items: dict[str, dict] = {}
    for idx in sorted(rounds):
        last = next((r for r in reversed(rounds[idx]) if "adopted_papers" in r), None)
        if last is None:
            continue                       # 06a 전 잡의 회차 — 채택 목록이 없다
        for p in last["adopted_papers"]:
            cnts_id = p["cnts_id"]
            item = items.get(cnts_id)
            if item is None:
                item = items[cnts_id] = {**_brief(briefs.get(cnts_id, {"cnts_id": cnts_id})),
                                         "series_title": None, "subq_idx": [], "rank": p["rank"]}
            item["subq_idx"].append(idx)
            item["rank"] = min(item["rank"], p["rank"])
    return list(items.values())


def _excluded_from_rounds(rounds: dict[int, list[dict]]) -> list[dict]:
    return [
        {**_brief(p), "subq_idx": idx, "round": r.get("round"), "note": r.get("note")}
        for idx in sorted(rounds)
        for r in rounds[idx]
        for p in r.get("excluded_papers") or []
    ]


def _excluded_from_trail(trail: list[dict], rounds: dict[int, list[dict]]) -> list[dict]:
    """끝난 잡 — 보고서 trail 의 제외 논문(보고서의 '관련성이 낮아 제외한 논문'과 같은 값)에, 어느 회차에서
    뺐는지와 그 회차의 critic note 를 회차 기록에서 찾아 붙인다. 논문별 제외 사유는 저장된 곳이 없다
    (spec §5-4). trail 은 하위질문 순이라 그 번호가 하위질문 번호다."""
    out: list[dict] = []
    for idx, t in enumerate(trail):
        where: dict[str, tuple] = {}
        for r in rounds.get(idx, []):
            for p in r.get("excluded_papers") or []:
                where.setdefault(p.get("cnts_id"), (r.get("round"), r.get("note")))
        for p in t.get("excluded_papers") or []:
            rnd, note = where.get(p.get("cnts_id"), (None, None))
            out.append({**_brief(p), "subq_idx": idx, "round": rnd, "note": note})
    return out


def pool_from_job(job, steps: list[dict]) -> dict:
    """채택 근거: 스냅샷(탐색이 끝나면 저장된다)이 있으면 그 근거 전부, 없으면(탐색 중) 회차의 adopted_papers.
    제외 논문: 보고서 trail 이 있으면 그것, 없으면 회차의 excluded_papers."""
    rounds = _rounds_by_subq(steps)
    snapshot = job.state_snapshot
    adopted = _adopted_from_snapshot(snapshot) if snapshot else _adopted_from_rounds(rounds)
    trail = (job.report or {}).get("trail")
    excluded = _excluded_from_trail(trail, rounds) if trail else _excluded_from_rounds(rounds)
    return {"adopted": adopted, "excluded": excluded}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_views.py -q -p no:cacheprovider`

Expected: `16 passed`

- [ ] **Step 5: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a add app/services/research_work/views.py app/tests/test_research_work_views.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a commit -m "[Feat] round06a — 연구 어시스턴트 응답 모양 순수 함수(services/research_work/views.py)를 더한다. work_view 는 연구 한 건과 생성 목록(대기 순번 포함)을, candidates_from_snapshot 은 이어가기 때 채택 근거 전체를 읽기 목록 후보로 넣는 값(들어온 경로는 하위질문·순위·매칭 대목과 점수·critic 판정·처음 채택된 회차 등 저장된 값만, 하위질문 키는 JSONB 왕복에 맞춰 문자열)을, pool_from_job 은 채택 근거 전체(끝난 잡은 스냅숏, 도는 잡은 회차의 adopted_papers)와 critic 이 뺀 논문(trail 또는 회차, 하위질문·회차·note 를 붙여)을 만든다"
```

- [ ] **Step 6: API 의 실패하는 테스트를 쓴다**

테스트 DB 에 `research_steps`·`research_reading` 을 더한다. `app/tests/history_sqlite.py` 바꾸기 ①: import. old:

```python
from models.research import ResearchJob
from models.research_work import ResearchGeneration, ResearchWork
```

new:

```python
from models.research import ResearchJob, ResearchStep
from models.research_work import ResearchGeneration, ResearchReading, ResearchWork
```

`app/tests/history_sqlite.py` 바꾸기 ②: `make_engine` 의 테이블 튜플. old:

```python
    for table in (HistoryItem.__table__, ResearchJob.__table__,
                  ResearchWork.__table__, ResearchGeneration.__table__):
```

new:

```python
    for table in (HistoryItem.__table__, ResearchJob.__table__, ResearchStep.__table__,
                  ResearchWork.__table__, ResearchGeneration.__table__, ResearchReading.__table__):
```

`app/tests/test_research_work_api.py` (새 파일, 전체):

```python
"""test_research_work_api.py — 연구 어시스턴트 API(api/research_work.py).

요청은 TestClient 로 실제 라우팅을 거친다(헤더 400·경로 422·본문 검증은 라우팅을 거쳐야 드러난다).
DB 는 history_sqlite 의 SQLite 다 — 이어가기의 멱등(ON CONFLICT DO NOTHING … RETURNING)·조건부 UPDATE·
이어간 연구 목록의 기록 조건을 실제 엔진이 판정한다. 요청이 끝나면 세션을 되돌리므로 핸들러가 직접
커밋한 쓰기만 남는다.

redis 는 로컬 venv 에 없다 — 미설치일 때만 더미를 꽂고, 연구 채널(publish_work·subscribe_work)은 기록용
가짜로 바꾼다. 디스패치 태스크를 보내는 워커 모듈은 sys.modules 에 가짜를 꽂는다(라우터는 보낼 때만
import 한다). 생성 대기 순번(queue_position)은 디스패처의 몫이라 가짜로 고정한다 — 끝까지 한 번 돌리는
TestEndToEnd 만 진짜 디스패처·실행기를 가짜 LLM 과 함께 쓴다.
"""
import ast
import asyncio
import importlib
import json
import sys
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from history_sqlite import (
    SID_A, SID_B, AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.history import HistoryItem
from models.research import ResearchJob, ResearchStep
from models.research_work import ResearchGeneration, ResearchReading, ResearchWork

A = {"x-session-id": str(SID_A)}
B = {"x-session-id": str(SID_B)}
POSITION = 3                     # 가짜 queue_position 이 늘 돌려주는 대기 순번

SNAPSHOT = {
    "question": "청소년 독서 격차", "params": {}, "corpus_range": None,
    "subquestions": [
        {"idx": 0, "text": "독서 격차의 원인", "evidence_ids": ["E1", "E2"], "verdict": "sufficient",
         "evidence_chunks": {"E1": ["c1"], "E2": ["c2"]}, "chunk_scores": {"c1": 0.9, "c2": 0.6},
         "rounds": []},
    ],
    "evidence": {
        "E1": {"cnts_id": "C1", "meta": {"title": "독서 격차 연구"}, "chunks": []},
        "E2": {"cnts_id": "C2", "meta": {"title": "학교 도서관"}, "chunks": []},
    },
}
X1 = {"cnts_id": "X1", "title": "무관 논문", "personal_author": "박민수", "pub_date": "2015"}
REPORT = {
    "question": "청소년 독서 격차", "sections": [{"heading": "독서 격차의 원인"}],
    "trail": [{"subquestion": "독서 격차의 원인", "excluded_papers": [X1]}],
}
ROUNDS = [
    {"round": 1, "query": "독서 격차 원인", "verdict": "insufficient", "note": "가정 요인이 부족하다",
     "excluded": 1, "excluded_papers": [X1],
     "adopted_papers": [{"cnts_id": "C1", "title": "독서 격차 연구", "personal_author": "김철수",
                         "pub_date": "2019", "rank": 1, "new": True}]},
]


def _stub_missing(monkeypatch, name: str, module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module)


_CACHED = ("api.research_work", "services.research.relay")


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다
    (test_research_api.py 와 같은 방식 — 더미 redis 에 묶인 relay 가 다른 테스트로 새지 않게)."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


class _Dispatch:
    """workers.research_work_tasks.send_dispatch 가짜 — 보낸 횟수를 센다."""
    def __init__(self):
        self.calls = 0
        self.result = True
        self.error: Exception | None = None

    def send_dispatch(self) -> bool:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class _Api:
    def __init__(self, client, engine, router, events, dispatch, asked):
        self.client = client
        self.engine = engine
        self.router = router
        self.events = events
        self.dispatch = dispatch
        self.asked = asked            # queue_position 을 물어본 생성 id


@pytest.fixture
def api(monkeypatch):
    for name in ("redis", "redis.asyncio"):
        _stub_missing(monkeypatch, name, MagicMock())
    _forget_on_teardown(monkeypatch, _CACHED)
    router = importlib.import_module("api.research_work")
    from core.deps import get_db

    events: list[tuple] = []

    async def _publish_work(work_id, kind, payload):
        events.append((str(work_id), kind, payload))

    monkeypatch.setattr(router, "publish_work", _publish_work)

    asked: list[int] = []

    async def _queue_position(db, gen):
        asked.append(gen.id)
        return POSITION

    monkeypatch.setattr(router, "queue_position", _queue_position)

    dispatch = _Dispatch()
    worker = types.ModuleType("workers.research_work_tasks")
    worker.send_dispatch = dispatch.send_dispatch
    monkeypatch.setitem(sys.modules, "workers.research_work_tasks", worker)

    engine = make_engine()

    async def _db():
        db = AsyncSessionOverSync(engine)
        try:
            yield db
        finally:
            # 성공해도 되돌린다 — 핸들러가 직접 커밋한 쓰기만 남아야 한다
            await db.rollback()
            await db.close()

    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_db] = _db
    return _Api(TestClient(app), engine, router, events, dispatch, asked)


# ── 데이터 도우미 ─────────────────────────────────────────────────────


def _job(engine, *, status: str = "completed", snapshot: dict | None = None,
         report: dict | None = None, plan: list | None = None) -> uuid.UUID:
    jid = add_research_job(engine, status=status, stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == jid).values(
            question="청소년 독서 격차", state_snapshot=snapshot, report=report, plan=plan,
        ))
    return jid


def _work_job(engine, **work) -> uuid.UUID:
    jid = _job(engine)
    add_work(engine, jid, **work)
    return jid


def _step(engine, jid: uuid.UUID, seq: int, subq_idx: int, result: dict) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(ResearchStep.__table__).values(
            job_id=jid, seq=seq, kind="search", subq_idx=subq_idx, title="탐색",
            status="done", result=result,
        ))


def _history(engine, session_id: uuid.UUID, ref_id: uuid.UUID, *, kind: str = "research",
             deleted: bool = False) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(HistoryItem.__table__).values(
            id=uuid.uuid4(), session_id=session_id, kind=kind, title="독서 격차 연구", params={},
            ref_id=str(ref_id), deleted_at=datetime.now(timezone.utc) if deleted else None,
        ))


def _rows(engine, model, **where) -> list:
    table = model.__table__
    stmt = sa.select(table)
    for col, value in where.items():
        stmt = stmt.where(table.c[col] == value)
    with engine.connect() as conn:
        return conn.execute(stmt.order_by(*table.primary_key.columns)).mappings().all()


def _set(engine, model, key, **values) -> None:
    table = model.__table__
    pk = list(table.primary_key.columns)[0]
    with engine.begin() as conn:
        conn.execute(sa.update(table).where(pk == key).values(**values))


def _frames(body: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in body.splitlines()
            if line.startswith("data: ")]


# ── 이어가기 ─────────────────────────────────────────────────────────


class TestContinue:
    def test_creates_the_work_its_candidates_and_one_concepts_generation(self, api, monkeypatch):
        monkeypatch.setattr(api.router, "concepts_input",
                            lambda job: {"question": job.question, "marker": 1})
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 200
        (gen,) = _rows(api.engine, ResearchGeneration)
        assert res.json() == {
            "id": str(jid), "phase": "topics", "concepts": [], "memo": None, "is_example": False,
            "progress": {},
            "generations": [{"id": gen["id"], "kind": "concepts", "target": None,
                             "status": "queued", "model": None, "error": None,
                             "position": POSITION}],
        }
        (work,) = _rows(api.engine, ResearchWork)
        assert work["owner_sid"] == str(SID_A) and work["concept_members"] == {}
        assert [(r["cnts_id"], r["state"], r["origin"]) for r in _rows(api.engine, ResearchReading)] == [
            ("C1", "candidate", "evidence"), ("C2", "candidate", "evidence"),
        ]
        assert _rows(api.engine, ResearchReading, cnts_id="C1")[0]["origin_ref"]["rank"] == {"0": 1}
        assert (gen["work_id"], gen["kind"], gen["priority"], gen["status"]) == (
            jid, "concepts", 10, "queued")
        assert gen["input"] == {"question": "청소년 독서 격차", "marker": 1}
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "work", {"phase": "topics", "progress": {}})]

    def test_concepts_input_reads_the_job(self, api):
        # 가짜 없이 — 핵심 개념 생성 입력이 잡 행(질문·계획·보고서)에서 만들어지는지
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        (gen,) = _rows(api.engine, ResearchGeneration)
        same_job = SimpleNamespace(id=jid, question="청소년 독서 격차", plan=["독서 격차의 원인"],
                                   report=REPORT, state_snapshot=SNAPSHOT, params={})
        assert gen["input"] == json.loads(json.dumps(api.router.concepts_input(same_job)))
        assert gen["input"]["question"] == "청소년 독서 격차"

    def test_second_continue_adds_nothing(self, api):
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        first = api.client.post(f"/api/research/{jid}/work/continue", headers=A)
        second = api.client.post(f"/api/research/{jid}/work/continue", headers=B)

        assert second.status_code == 200 and second.json() == first.json()
        assert len(_rows(api.engine, ResearchWork)) == 1
        assert _rows(api.engine, ResearchWork)[0]["owner_sid"] == str(SID_A)
        assert len(_rows(api.engine, ResearchReading)) == 2
        assert len(_rows(api.engine, ResearchGeneration)) == 1
        assert api.dispatch.calls == 1 and len(api.events) == 1

    def test_without_a_browser_id_the_owner_stays_empty(self, api):
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT)

        assert api.client.post(f"/api/research/{jid}/work/continue").status_code == 200

        assert _rows(api.engine, ResearchWork)[0]["owner_sid"] is None

    def test_job_without_a_snapshot_still_gets_concepts(self, api):
        jid = _job(api.engine, report=REPORT, plan=["독서 격차의 원인"])

        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        assert _rows(api.engine, ResearchReading) == []
        assert len(_rows(api.engine, ResearchGeneration)) == 1

    @pytest.mark.parametrize("status", ["awaiting_approval", "queued", "running", "failed", "canceled"])
    def test_only_a_completed_job_can_be_continued(self, api, status):
        jid = _job(api.engine, status=status, snapshot=SNAPSHOT)

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 409
        assert _rows(api.engine, ResearchWork) == []
        assert api.dispatch.calls == 0

    def test_unknown_job_is_404_and_malformed_id_is_422(self, api):
        assert api.client.post(f"/api/research/{uuid.uuid4()}/work/continue").status_code == 404
        assert api.client.post("/api/research/not-a-uuid/work/continue").status_code == 422

    def test_dispatch_failure_still_answers_200(self, api):
        # 행은 이미 커밋됐다 — 회수기가 queued 를 보고 디스패치를 다시 보낸다
        api.dispatch.result = False
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT)
        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        api.dispatch.error = RuntimeError("broker down")
        other = _job(api.engine, snapshot=SNAPSHOT, report=REPORT)
        assert api.client.post(f"/api/research/{other}/work/continue", headers=A).status_code == 200

        assert [g["status"] for g in _rows(api.engine, ResearchGeneration)] == ["queued", "queued"]

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 409 and res.json()["detail"] == "예시 연구는 읽기 전용입니다"
        assert _rows(api.engine, ResearchGeneration) == []


# ── 조회·고치기 ───────────────────────────────────────────────────────


class TestGetWork:
    def test_404_until_continued(self, api):
        jid = _job(api.engine)
        assert api.client.get(f"/api/research/{jid}/work").status_code == 404

    def test_lists_open_generations_and_the_ten_latest_finished(self, api):
        jid = _work_job(api.engine, concepts=["독서 격차"])
        done = [add_generation(api.engine, jid, status="done") for _ in range(11)]
        failed = add_generation(api.engine, jid, status="failed")
        running = add_generation(api.engine, jid, status="running")
        queued = add_generation(api.engine, jid, status="queued")

        res = api.client.get(f"/api/research/{jid}/work")

        assert res.status_code == 200
        gens = res.json()["generations"]
        assert [g["id"] for g in gens] == [*done[2:], failed, running, queued]
        assert {g["id"]: g["position"] for g in gens if g["status"] in ("running", "queued")} == {
            running: None, queued: POSITION}
        assert api.asked == [queued]
        assert res.json()["concepts"] == ["독서 격차"]


class TestPatchWork:
    def test_cleans_concepts_and_clears_membership_when_they_change(self, api):
        jid = _work_job(api.engine, concepts=["옛 개념"])
        _set(api.engine, ResearchWork, jid, concept_members={"옛 개념": ["C1"]})
        add_generation(api.engine, jid, kind="concepts", status="done")       # 끝난 생성은 막지 않는다

        res = api.client.patch(f"/api/research/{jid}/work",
                               json={"concepts": ["  독서   격차 ", "청소년", "독서 격차"]})

        assert res.status_code == 200
        assert res.json()["concepts"] == ["독서 격차", "청소년"]
        (work,) = _rows(api.engine, ResearchWork)
        assert work["concepts"] == ["독서 격차", "청소년"] and work["concept_members"] == {}

    def test_concepts_only_patch_keeps_the_memo(self, api):
        jid = _work_job(api.engine, concepts=["옛 개념"])
        _set(api.engine, ResearchWork, jid, memo="가설 메모")

        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": ["독서 격차"]})

        assert res.status_code == 200 and res.json()["memo"] == "가설 메모"
        assert _rows(api.engine, ResearchWork)[0]["memo"] == "가설 메모"

    @pytest.mark.parametrize("status", ["queued", "running"])
    def test_concepts_cannot_change_while_concepts_are_being_made(self, api, status):
        # 워커의 결과 적용이 끝나며 칩을 덮어쓴다 — 고친 개념이 소리 없이 사라지지 않게 막는다
        jid = _work_job(api.engine, concepts=["독서 격차"])
        add_generation(api.engine, jid, kind="concepts", status=status)

        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": ["청소년"]})

        assert res.status_code == 409
        assert res.json()["detail"] == "핵심 개념을 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
        assert _rows(api.engine, ResearchWork)[0]["concepts"] == ["독서 격차"]

    def test_memo_and_same_concepts_pass_while_concepts_are_being_made(self, api):
        jid = _work_job(api.engine, concepts=["독서 격차"])
        add_generation(api.engine, jid, kind="concepts", status="running")

        res = api.client.patch(f"/api/research/{jid}/work",
                               json={"concepts": ["독서 격차"], "memo": "메모"})

        assert res.status_code == 200 and res.json()["memo"] == "메모"
        assert _rows(api.engine, ResearchWork)[0]["memo"] == "메모"

    def test_same_concepts_keep_membership(self, api):
        jid = _work_job(api.engine, concepts=["독서 격차", "청소년"])
        _set(api.engine, ResearchWork, jid, concept_members={"독서 격차": ["C1"]})

        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": ["독서 격차", "청소년"]})

        assert res.status_code == 200
        assert _rows(api.engine, ResearchWork)[0]["concept_members"] == {"독서 격차": ["C1"]}

    def test_a_single_concept_is_enough(self, api):
        jid = _work_job(api.engine)
        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": ["독서 격차"]})
        assert res.status_code == 200 and res.json()["concepts"] == ["독서 격차"]

    @pytest.mark.parametrize("concepts", [[], ["   "], ["가", "나", "다", "라", "마", "바"], [1, 2]])
    def test_rejects_concepts_that_leave_nothing_or_too_many(self, api, concepts):
        jid = _work_job(api.engine, concepts=["독서 격차"])

        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": concepts})

        assert res.status_code == 422
        assert _rows(api.engine, ResearchWork)[0]["concepts"] == ["독서 격차"]

    def test_memo_is_saved_cleared_and_capped(self, api):
        jid = _work_job(api.engine)

        assert api.client.patch(f"/api/research/{jid}/work", json={"memo": "가설 메모"}).json()["memo"] == "가설 메모"
        assert _rows(api.engine, ResearchWork)[0]["memo"] == "가설 메모"
        assert api.client.patch(f"/api/research/{jid}/work", json={"memo": ""}).json()["memo"] is None
        assert api.client.patch(f"/api/research/{jid}/work", json={"memo": "가" * 2001}).status_code == 422

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        res = api.client.patch(f"/api/research/{jid}/work", json={"memo": "메모"})
        assert res.status_code == 409 and res.json()["detail"] == "예시 연구는 읽기 전용입니다"

    def test_404_until_continued(self, api):
        jid = _job(api.engine)
        assert api.client.patch(f"/api/research/{jid}/work", json={"memo": "메모"}).status_code == 404


# ── 근거 풀 ──────────────────────────────────────────────────────────


class TestPool:
    def test_completed_job_pool_includes_uncited_evidence_and_trail_exclusions(self, api):
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT)
        _step(api.engine, jid, 2, 0, {"rounds": ROUNDS})

        res = api.client.get(f"/api/research/{jid}/pool")

        assert res.status_code == 200
        assert [(p["cnts_id"], p["subq_idx"], p["rank"]) for p in res.json()["adopted"]] == [
            ("C1", [0], 1), ("C2", [0], 2)]
        assert res.json()["excluded"] == [
            {**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"}]

    def test_running_job_pool_comes_from_the_search_rounds(self, api):
        # 이어가기 전(연구 행 없음)·탐색 중에도 읽는다 — 근거 장부가 쓴다
        jid = _job(api.engine, status="running")
        _step(api.engine, jid, 2, 0, {"rounds": ROUNDS})

        res = api.client.get(f"/api/research/{jid}/pool")

        assert res.json() == {
            "adopted": [{"cnts_id": "C1", "title": "독서 격차 연구", "personal_author": "김철수",
                         "pub_date": "2019", "series_title": None, "subq_idx": [0], "rank": 1}],
            "excluded": [{**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"}],
        }

    def test_unknown_job_is_404(self, api):
        assert api.client.get(f"/api/research/{uuid.uuid4()}/pool").status_code == 404


# ── 이어간 연구 목록 ─────────────────────────────────────────────────


class TestListWorks:
    def test_needs_the_browser_id(self, api):
        assert api.client.get("/api/research-works").status_code == 400

    def test_only_this_browsers_works_still_in_its_history(self, api):
        kept = _work_job(api.engine, owner_sid=str(SID_A))
        _history(api.engine, SID_A, kept)
        deleted = _work_job(api.engine, owner_sid=str(SID_A))
        _history(api.engine, SID_A, deleted, deleted=True)
        _work_job(api.engine, owner_sid=str(SID_A))                      # 기록이 없다
        other_owner = _work_job(api.engine, owner_sid=str(SID_B))
        _history(api.engine, SID_A, other_owner)
        other_kind = _work_job(api.engine, owner_sid=str(SID_A))
        _history(api.engine, SID_A, other_kind, kind="paper")
        removed = _work_job(api.engine, owner_sid=str(SID_A))
        _history(api.engine, SID_A, removed)
        _set(api.engine, ResearchWork, removed, deleted_at=datetime.now(timezone.utc))
        elsewhere = _work_job(api.engine, owner_sid=str(SID_A))       # 기록이 다른 브라우저에만 있다
        _history(api.engine, SID_B, elsewhere)

        res = api.client.get("/api/research-works", headers=A)

        assert res.status_code == 200
        (item,) = res.json()["items"]
        assert set(item) == {"id", "question", "phase", "created_at"}
        assert (item["id"], item["question"], item["phase"]) == (str(kept), "청소년 독서 격차", "topics")

    def test_newest_first(self, api):
        old = _work_job(api.engine, owner_sid=str(SID_A))
        new = _work_job(api.engine, owner_sid=str(SID_A))
        for jid, day in ((old, 1), (new, 2)):
            _history(api.engine, SID_A, jid)
            _set(api.engine, ResearchWork, jid, created_at=datetime(2026, 10, day, tzinfo=timezone.utc))

        res = api.client.get("/api/research-works", headers=A)

        assert [i["id"] for i in res.json()["items"]] == [str(new), str(old)]

    def test_examples_are_listed_for_any_browser(self, api):
        example = _work_job(api.engine, owner_sid=str(SID_B), is_example=True)
        _work_job(api.engine, owner_sid=str(SID_A))

        res = api.client.get("/api/research-works?example=1", headers=A)

        assert [i["id"] for i in res.json()["items"]] == [str(example)]


# ── 생성 취소·다시 ───────────────────────────────────────────────────


class TestCancelGeneration:
    def test_queued_generation_is_canceled(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="queued")

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/cancel")

        assert res.status_code == 200 and res.json() == {"gen_id": gid, "status": "canceled"}
        (gen,) = _rows(api.engine, ResearchGeneration)
        assert gen["status"] == "canceled" and gen["finished_at"] is not None
        assert api.events == [(str(jid), "generation", {
            "gen_id": gid, "gen_kind": "concepts", "target": None, "status": "canceled",
            "model": None, "result": None})]
        assert api.dispatch.calls == 0

    def test_running_generation_waits_until_it_ends(self, api):
        # canceled 로 두면 디스패처의 전역 한 자리가 비어 다음 생성이 q_research_plan 의 남은 자리를 쓴다 —
        # 취소한 생성의 LLM 호출은 워커에서 계속 돌므로 두 자리를 생성이 다 쓴다(D15)
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="running")

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/cancel")

        assert res.status_code == 409
        assert res.json()["detail"] == "진행 중인 생성은 끝날 때까지 기다립니다"
        assert _rows(api.engine, ResearchGeneration)[0]["status"] == "running"
        assert api.events == [] and api.dispatch.calls == 0

    def test_generation_picked_after_it_was_read_is_409(self, api, monkeypatch):
        # 읽은 뒤 디스패처가 집었으면(queued → running) 조건부 UPDATE 가 바꾸지 않는다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="queued")
        read = api.router._get_generation

        async def _picked_meanwhile(db, work_id, gen_id):
            gen = await read(db, work_id, gen_id)
            _set(api.engine, ResearchGeneration, gen_id, status="running")
            return gen

        monkeypatch.setattr(api.router, "_get_generation", _picked_meanwhile)

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/cancel")

        assert res.status_code == 409
        assert _rows(api.engine, ResearchGeneration)[0]["status"] == "running"
        assert api.events == []

    @pytest.mark.parametrize("status", ["done", "failed", "canceled"])
    def test_finished_generation_is_409(self, api, status):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status=status)

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/cancel")

        assert res.status_code == 409
        assert _rows(api.engine, ResearchGeneration)[0]["status"] == status
        assert api.events == []

    def test_generation_of_another_work_is_404(self, api):
        jid = _work_job(api.engine)
        other = _work_job(api.engine)
        gid = add_generation(api.engine, other)

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/cancel").status_code == 404
        assert api.client.post(f"/api/research/{jid}/generations/999/cancel").status_code == 404
        assert _rows(api.engine, ResearchGeneration)[0]["status"] == "queued"

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        gid = add_generation(api.engine, jid)
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/cancel").status_code == 409


class TestRetryGeneration:
    @pytest.mark.parametrize("status", ["failed", "canceled"])
    def test_adds_a_queued_copy_and_dispatches(self, api, status):
        jid = _work_job(api.engine)
        # 배경 우선순위(0)도 그대로 옮긴다 — 다시 부른다고 사용자 우선순위로 올리지 않는다
        gid = add_generation(api.engine, jid, status=status, priority=0,
                             input={"question": "청소년 독서 격차"})

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 200
        old, new = _rows(api.engine, ResearchGeneration)
        assert res.json() == {"gen_id": new["id"]}
        assert old["status"] == status
        assert (new["kind"], new["target"], new["priority"], new["status"], new["input"]) == (
            "concepts", None, 0, "queued", {"question": "청소년 독서 격차"})
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "generation", {
            "gen_id": new["id"], "gen_kind": "concepts", "target": None, "status": "queued",
            "model": None, "result": None})]

    def test_concepts_done_without_concepts_can_be_called_again(self, api):
        # spec §5-2 — 핵심 개념을 끝내 못 얻으면 비운 채 done 이고, 다시 부르기는 이 retry 다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="done", input={"question": "청소년 독서 격차"})
        _set(api.engine, ResearchGeneration, gid, output={"concepts": [], "attempts": []})

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 200
        old, new = _rows(api.engine, ResearchGeneration)
        assert res.json() == {"gen_id": new["id"]}
        assert (old["status"], new["kind"], new["priority"], new["status"], new["input"]) == (
            "done", "concepts", 10, "queued", {"question": "청소년 독서 격차"})
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "generation", {
            "gen_id": new["id"], "gen_kind": "concepts", "target": None, "status": "queued",
            "model": None, "result": None})]

    def test_concepts_done_with_concepts_is_409(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="done")
        _set(api.engine, ResearchGeneration, gid, output={"concepts": ["독서 격차", "청소년"]})

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 409 and res.json()["detail"] == "다시 부를 수 없는 상태입니다: done"
        assert len(_rows(api.engine, ResearchGeneration)) == 1
        assert api.dispatch.calls == 0

    @pytest.mark.parametrize("status", ["queued", "running"])
    def test_open_generation_cannot_be_retried(self, api, status):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status=status)

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 409
        assert len(_rows(api.engine, ResearchGeneration)) == 1
        assert api.dispatch.calls == 0

    def test_second_retry_while_the_copy_is_open_is_409(self, api):
        # 두 번 누르면 같은 생성이 두 줄 서지 않는다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="failed")

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 200
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 409
        assert len(_rows(api.engine, ResearchGeneration)) == 2

    def test_an_open_generation_of_another_target_does_not_block(self, api):
        # 같은 kind 라도 대상(target)이 다르면 다른 일이다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="failed")
        _set(api.engine, ResearchGeneration, gid, target="t1")
        other = add_generation(api.engine, jid, status="queued")
        _set(api.engine, ResearchGeneration, other, target="t2")

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 200
        (new,) = _rows(api.engine, ResearchGeneration, id=res.json()["gen_id"])
        assert (new["target"], new["status"]) == ("t1", "queued")

    def test_duplicate_check_and_insert_run_under_one_lock(self, api):
        # 동시에 두 번 눌러도 한 줄만 서게 — (연구·kind·target) 잠금 → 열린 생성 검사 → 넣기 → 커밋.
        # 잠금은 SQLite 에서 빈 함수다(history_sqlite) — 순서와 키를 문장 기록으로 본다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="failed")
        _set(api.engine, ResearchGeneration, gid, target="t1")
        seen: list[tuple] = []
        sa.event.listen(api.engine, "before_cursor_execute",
                        lambda conn, cur, stmt, params, ctx, many: seen.append((stmt, params)))
        sa.event.listen(api.engine, "commit", lambda conn: seen.append(("COMMIT", None)))

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 200

        lock = next(i for i, (s, _) in enumerate(seen) if "pg_advisory_xact_lock" in s)
        check = next(i for i, (s, _) in enumerate(seen)
                     if s.startswith("SELECT") and "research_generations.status IN" in s)
        insert = next(i for i, (s, _) in enumerate(seen)
                      if s.startswith("INSERT INTO research_generations"))
        commit = next(i for i, (s, _) in enumerate(seen) if s == "COMMIT" and i > lock)
        assert lock < check < insert < commit
        assert seen[lock][1] == (api.router._retry_lock_key(jid, "concepts", "t1"),)
        assert api.router._retry_lock_key(jid, "concepts", "t1") != api.router._retry_lock_key(
            jid, "concepts", "t2")

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        gid = add_generation(api.engine, jid, status="failed")
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 409

    def test_generation_of_another_work_is_404(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, _work_job(api.engine), status="failed")
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 404


# ── 연구 SSE ─────────────────────────────────────────────────────────


class TestWorkStream:
    def test_snapshot_then_relayed_events_and_pings(self, api, monkeypatch):
        jid = _work_job(api.engine, concepts=["독서 격차"])
        gid = add_generation(api.engine, jid)
        seen = {}
        event = {"kind": "generation", "gen_id": gid, "gen_kind": "concepts", "target": None,
                 "status": "done", "model": "qwen3-vl-8b", "result": {"concepts": ["독서 격차"]}}

        async def _subscribe_work(work_id, *, idle_timeout=15.0):
            seen["work_id"] = work_id
            yield event
            yield None
            yield {"kind": "work", "phase": "topics", "progress": {}}

        monkeypatch.setattr(api.router, "subscribe_work", _subscribe_work)

        res = api.client.get(f"/api/research/{str(jid).upper()}/work/stream")

        assert res.headers["content-type"].startswith("text/event-stream")
        frames = _frames(res.text)
        assert frames[0]["kind"] == "snapshot"
        assert frames[0]["work"] == api.client.get(f"/api/research/{jid}/work").json()
        assert frames[1:] == [event, {"kind": "work", "phase": "topics", "progress": {}}]
        assert ": ping" in res.text
        # 워커는 표준형 id 채널에 쓴다 — 대문자 경로로 붙어도 같은 채널을 구독해야 한다
        assert seen["work_id"] == str(jid)

    def test_404_until_continued(self, api):
        jid = _job(api.engine)
        assert api.client.get(f"/api/research/{jid}/work/stream").status_code == 404


# ── 끝까지 한 번 ──────────────────────────────────────────────────────


class TestEndToEnd:
    def test_continue_then_the_dispatcher_fills_the_concepts(self, api):
        # spec §8 '새 라우터 API 를 가짜 LLM 으로 끝까지' — 이어가기가 넣은 생성을 Task 9 의 디스패처가 집고,
        # Task 8 의 실행기가 가짜 LLM 답을 읽고, 결과 적용·닫기 뒤 연구 조회에 개념이 보인다
        from services.llm_client import LLMResult
        from services.research_work import dispatch
        from services.research_work.apply import apply_result
        from services.research_work.executors import EXECUTORS
        from services.research_work.generate import run_generation

        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 200
        assert [(g["status"], g["position"]) for g in res.json()["generations"]] == [
            ("queued", POSITION)]
        models: list[str] = []

        async def _chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            models.append(model)
            return LLMResult(content='{"concepts": ["독서 격차", "청소년"]}', finish_reason="stop")

        async def _work_once():
            db = AsyncSessionOverSync(api.engine)
            try:
                gen = await dispatch.pick_next(db)
                gen_id = gen.id
                result = await run_generation(EXECUTORS[gen.kind], dict(gen.input), chat_fn=_chat)
                payload = await apply_result(db, gen, result.output)
                closed = await dispatch.finish(
                    db, gen_id, status="done", model=result.model, error=None,
                    output={**result.output, "attempts": result.attempts},
                )
                return gen_id, payload, closed
            finally:
                await db.close()

        gen_id, payload, closed = asyncio.run(_work_once())

        assert closed and payload == {"concepts": ["독서 격차", "청소년"]}
        assert len(models) == 1
        work = api.client.get(f"/api/research/{jid}/work").json()
        assert work["concepts"] == ["독서 격차", "청소년"]
        assert work["generations"] == [{"id": gen_id, "kind": "concepts", "target": None,
                                        "status": "done", "model": models[0], "error": None,
                                        "position": None}]


class TestEventShape:
    def test_worker_generation_event_uses_the_same_keys(self):
        # 워커(Task 9)가 끝난 생성을 알리는 generation 이벤트와 이 라우터의 것이 같은 키여야 한다 — relay 는
        # {"kind": 이벤트 종류, **payload} 로 실어 페이로드의 "kind" 가 이벤트 종류를 덮어쓴다.
        # 워커는 celery 를 끌어오므로 import 하지 않고 소스에서 publish_work(…, "generation", {…}) 를 찾는다
        source = (Path(__file__).resolve().parents[1] / "workers" / "research_work_tasks.py").read_text(
            encoding="utf-8")
        payloads = [
            {key.value for key in node.args[2].keys}
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "publish_work"
            and len(node.args) == 3 and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "generation" and isinstance(node.args[2], ast.Dict)
        ]
        assert payloads == [{"gen_id", "gen_kind", "target", "status", "model", "result"}]


class TestAppWiring:
    def test_main_includes_research_work_router(self):
        # 테스트는 라우터를 직접 붙인다 — main.py 등록을 빠뜨려도 위 테스트는 모두 통과한다
        tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
        imported = {
            (node.module, alias.name, alias.asname)
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        included = {
            node.args[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "include_router"
        }
        assert ("api.research_work", "router", "research_work_router") in imported
        assert "research_work_router" in included
```

- [ ] **Step 7: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_api.py -q -p no:cacheprovider`

Expected: `1 failed, 1 passed, 58 errors` — 58개는 fixture 의 `ModuleNotFoundError: No module named 'api.research_work'`, 1개(`TestAppWiring::test_main_includes_research_work_router`)는 `AssertionError: assert ('api.research_work', 'router', 'research_work_router') in {…}`. 통과하는 1개는 `TestEventShape` — Task 9 의 워커가 이미 `gen_kind` 로 보낸다(라우터와 상관없는 가드라 지금 통과한다).

- [ ] **Step 8: 라우터를 만든다**

`app/api/research_work.py` (새 파일, 전체):

```python
"""research_work.py — 연구 어시스턴트(round06) API.

딥리서치 보고서 끝 [이 연구 이어가기] 를 누르면 그 잡이 연구 한 건(research_works, id = 잡 id)이 된다.
06a 는 이어가기·조회·핵심 개념/메모 고치기·근거 풀·이어간 연구 목록·생성 취소/다시·연구 SSE 를 둔다.

동기 엔드포인트에는 LLM 을 넣지 않는다(게이트웨이 proxy_read_timeout·llm_client 기본 timeout 이 120초).
LLM 작업은 research_generations 에 행을 넣고 디스패치 태스크를 보낸다 — 워커가 전체에서 한 번에 1건씩
돈다(spec §6-3). 보내기에 실패해도 행은 남고 회수기(tasks.reap_stale_research)가 다시 보낸다.

소유(owner_sid)는 기록만 하고 검사하지 않는다(spec D4). 예시 연구(is_example)를 바꾸는 요청은 409 다.
생성 이벤트의 생성 종류는 `gen_kind` 에 싣는다 — relay 가 이벤트 종류를 `kind` 에 넣으므로(publish 와
같은 방식) 페이로드에 `kind` 를 두면 이벤트 종류를 덮어쓴다. 워커(Task 9)의 generation 이벤트도 같은 키다.
도는(running) 생성은 취소하지 않는다 — 취소해도 워커의 LLM 호출은 계속 q_research_plan 한 자리를 쓰는데
디스패처의 전역 한 자리는 비어, 다음 생성이 남은 자리까지 쓰게 된다(D15).
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_browser_id, get_browser_id_optional, get_db
from models.history import HistoryItem
from models.research import ResearchJob, ResearchStep
from models.research_work import (
    GEN_OPEN_STATUSES, PRIORITY_USER, ResearchGeneration, ResearchReading, ResearchWork,
)
from services.research.relay import publish_work, subscribe_work
from services.research_work.concepts import MAX_CONCEPTS, clean_concepts, concepts_input
from services.research_work.dispatch import queue_position
from services.research_work.views import candidates_from_snapshot, pool_from_job, work_view

log = logging.getLogger(__name__)

router = APIRouter(tags=["research-work"])

EXAMPLE_READ_ONLY = "예시 연구는 읽기 전용입니다"
CONCEPTS_BUSY = "핵심 개념을 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
RUNNING_NOT_CANCELABLE = "진행 중인 생성은 끝날 때까지 기다립니다"
MAX_MEMO = 2000
RECENT_FINISHED = 10           # 연구 응답에 싣는 끝난 생성 수(열린 생성은 전부 싣는다)
MAX_WORK_LIST = 50             # 이어간 연구 목록 상한 — [담기] 메뉴가 고르는 목록이다
RETRYABLE_STATUSES = ("failed", "canceled")


class WorkPatch(BaseModel):
    # 사용자가 고친 핵심 개념은 1~5개(LLM 결과의 '2개 이상' 검사는 생성 쪽 규칙이다)
    concepts: list[str] | None = Field(None, min_length=1, max_length=MAX_CONCEPTS)
    memo: str | None = Field(None, max_length=MAX_MEMO)


def _job_uuid(job_id: str) -> uuid.UUID:
    """경로의 잡 id. 형식이 틀리면 422(api/research.py 와 같다). 이후로는 이 값의 str() 만 쓴다 —
    워커는 표준형 id 채널에 publish 하므로 경로 문자열을 그대로 구독하면 이벤트를 못 받는다."""
    try:
        return uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="job_id 형식이 올바르지 않습니다")


async def _get_job(db: AsyncSession, jid: uuid.UUID) -> ResearchJob:
    job = await db.get(ResearchJob, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


async def _get_work(db: AsyncSession, jid: uuid.UUID) -> ResearchWork:
    work = await db.get(ResearchWork, jid)
    if work is None:
        raise HTTPException(status_code=404, detail="이어간 연구가 없습니다")
    return work


def _writable(work: ResearchWork) -> None:
    if work.is_example:
        raise HTTPException(status_code=409, detail=EXAMPLE_READ_ONLY)


async def _get_generation(db: AsyncSession, jid: uuid.UUID, gen_id: int) -> ResearchGeneration:
    gen = await db.get(ResearchGeneration, gen_id)
    if gen is None or gen.work_id != jid:
        raise HTTPException(status_code=404, detail="생성이 없습니다")
    return gen


def _retryable(gen: ResearchGeneration) -> bool:
    """다시 부를 수 있는 생성 — failed·canceled, 그리고 빈 결과로 끝난 핵심 개념(spec §5-2: 끝내 못 얻으면
    비운 채 done 이고 다시 부르기는 retry 다). 개념이 채워진 done 은 다시 부르지 않는다."""
    if gen.status in RETRYABLE_STATUSES:
        return True
    return gen.kind == "concepts" and gen.status == "done" and not (gen.output or {}).get("concepts")


def _retry_lock_key(jid: uuid.UUID, kind: str, target: str | None) -> int:
    """(연구·kind·target) 별 트랜잭션 잠금 키 — 같은 생성의 동시 '다시' 를 한 줄로 세운다
    (api/research.py 의 _browser_lock_key 와 같은 방식)."""
    raw = f"research_work_retry:{jid}:{kind}:{target or ''}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=True)


async def _concepts_open(db: AsyncSession, jid: uuid.UUID) -> bool:
    """이 연구의 핵심 개념 생성이 대기 중이거나 도는 중인가."""
    G = ResearchGeneration
    return await db.scalar(
        select(G.id).where(G.work_id == jid, G.kind == "concepts",
                           G.status.in_(GEN_OPEN_STATUSES)).limit(1)
    ) is not None


async def _generations(db: AsyncSession, jid: uuid.UUID) -> list[ResearchGeneration]:
    """열린 생성(queued·running) 전부와 최근 끝난 생성 RECENT_FINISHED 건."""
    G = ResearchGeneration
    open_rows = (await db.execute(
        select(G).where(G.work_id == jid, G.status.in_(GEN_OPEN_STATUSES)).order_by(G.id)
    )).scalars().all()
    finished = (await db.execute(
        select(G).where(G.work_id == jid, G.status.not_in(GEN_OPEN_STATUSES))
        .order_by(G.id.desc()).limit(RECENT_FINISHED)
    )).scalars().all()
    return [*open_rows, *finished]


async def _view(db: AsyncSession, work: ResearchWork) -> dict:
    gens = await _generations(db, work.id)
    positions = {g.id: await queue_position(db, g) for g in gens if g.status == "queued"}
    return work_view(work, gens, positions)


def _send_dispatch() -> bool:
    """생성 디스패치 태스크를 보낸다. 실패해도 응답은 그대로다 — 행은 이미 커밋됐고 회수기가 queued 를 보고
    다시 보낸다. 워커 모듈(celery)은 보낼 때만 import 한다(api/research.py 의 _enqueue 와 같다)."""
    try:
        from workers.research_work_tasks import send_dispatch
        return send_dispatch()
    except Exception:
        log.exception("[research-work] 디스패치 태스크를 보내지 못했다 — 회수기가 다시 보낸다")
        return False


def _generation_event(gen_id: int, gen: ResearchGeneration, status: str) -> dict:
    return {"gen_id": gen_id, "gen_kind": gen.kind, "target": gen.target, "status": status,
            "model": None, "result": None}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@router.post("/api/research/{job_id}/work/continue")
async def continue_research(
    job_id: str, db: AsyncSession = Depends(get_db),
    browser_id: uuid.UUID | None = Depends(get_browser_id_optional),
):
    """[이 연구 이어가기]. 완료된 잡만, 멱등 — 연구 행을 새로 만든 요청만 후보·핵심 개념 생성을 넣는다.
    동시에 두 번 눌러도 ON CONFLICT DO NOTHING 이 한쪽만 행을 만들게 한다."""
    jid = _job_uuid(job_id)
    job = await _get_job(db, jid)
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="완료된 딥리서치만 이어갈 수 있습니다")
    created = await db.scalar(
        insert(ResearchWork)
        .values(id=jid, owner_sid=str(browser_id) if browser_id else None,
                concepts=[], concept_members={}, progress={})
        .on_conflict_do_nothing()
        .returning(ResearchWork.id)
    )
    if created is None:
        work = await _get_work(db, jid)
        _writable(work)
        return await _view(db, work)

    candidates = candidates_from_snapshot(job.state_snapshot)
    if candidates:
        await db.execute(
            insert(ResearchReading)
            .values([{"work_id": jid, "state": "candidate", **c} for c in candidates])
            .on_conflict_do_nothing()
        )
    await db.execute(insert(ResearchGeneration).values(
        work_id=jid, kind="concepts", priority=PRIORITY_USER, status="queued",
        input=concepts_input(job),
    ))
    await db.commit()
    _send_dispatch()
    work = await _get_work(db, jid)
    await publish_work(jid, "work", {"phase": work.phase, "progress": work.progress})
    return await _view(db, work)


@router.get("/api/research/{job_id}/work")
async def get_work(job_id: str, db: AsyncSession = Depends(get_db)):
    return await _view(db, await _get_work(db, _job_uuid(job_id)))


@router.patch("/api/research/{job_id}/work")
async def patch_work(job_id: str, req: WorkPatch, db: AsyncSession = Depends(get_db)):
    """핵심 개념 칩·메모. 개념이 바뀌면 개념 소속을 비운다(다시 계산은 06c 의 FastAPI 몫).
    핵심 개념 생성이 열려 있으면 개념은 바꾸지 않는다(409) — 워커의 결과 적용이 끝나며 칩을 덮어쓴다."""
    work = await _get_work(db, _job_uuid(job_id))
    _writable(work)
    if req.concepts is not None:
        concepts = clean_concepts(req.concepts)
        if not concepts:
            raise HTTPException(status_code=422, detail="핵심 개념을 1개 이상 넣어 주세요")
        if concepts != list(work.concepts or []):
            if await _concepts_open(db, work.id):
                raise HTTPException(status_code=409, detail=CONCEPTS_BUSY)
            work.concepts = concepts
            work.concept_members = {}
    if "memo" in req.model_fields_set:
        work.memo = req.memo or None
    await db.commit()
    return await _view(db, work)


async def _search_steps(db: AsyncSession, jid: uuid.UUID) -> list[dict]:
    rows = (await db.execute(
        select(ResearchStep)
        .where(ResearchStep.job_id == jid, ResearchStep.kind == "search")
        .order_by(ResearchStep.seq)
    )).scalars().all()
    return [{"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx, "status": s.status,
             "result": s.result} for s in rows]


@router.get("/api/research/{job_id}/pool")
async def get_pool(job_id: str, db: AsyncSession = Depends(get_db)):
    """채택 근거 전체(보고서에 인용되지 않은 것 포함)와 critic 이 뺀 논문. 이어가기 전·탐색 중에도
    읽는다 — 끝난 잡은 state_snapshot·보고서 trail, 도는 잡은 탐색 단계의 회차 기록에서 만든다."""
    jid = _job_uuid(job_id)
    job = await _get_job(db, jid)
    return pool_from_job(job, await _search_steps(db, jid))


async def _kept_in_history(db: AsyncSession, browser_id: uuid.UUID, refs: list[str]) -> set[str]:
    """이 브라우저의 기록에 남은(지우지 않은) 딥리서치 ref_id. history_items 와 research_works 를
    `id::text` 로 조인하지 않는다 — 문자열 ref_id 조인은 PK 인덱스를 못 쓴다(repositories/history.py)."""
    if not refs:
        return set()
    H = HistoryItem
    rows = (await db.execute(
        select(H.ref_id).where(H.session_id == browser_id, H.kind == "research",
                               H.deleted_at.is_(None), H.ref_id.in_(refs))
    )).scalars().all()
    return set(rows)


@router.get("/api/research-works")
async def list_works(
    example: bool = False, browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    """이어간 연구 목록 — 빠른검색 [담기] 가 고르는 대상. example=1 이면 예시 연구(브라우저 무관)."""
    W = ResearchWork
    stmt = (
        select(W.id, W.phase, W.created_at, ResearchJob.question)
        .join(ResearchJob, ResearchJob.id == W.id)
        .where(W.deleted_at.is_(None))
        .order_by(W.created_at.desc(), W.id)
    )
    if example:
        rows = (await db.execute(stmt.where(W.is_example.is_(True)).limit(MAX_WORK_LIST))).all()
    else:
        owned = (await db.execute(stmt.where(W.owner_sid == str(browser_id)))).all()
        kept = await _kept_in_history(db, browser_id, [str(r.id) for r in owned])
        rows = [r for r in owned if str(r.id) in kept][:MAX_WORK_LIST]
    return {"items": [
        {"id": str(r.id), "question": r.question, "phase": r.phase, "created_at": _iso(r.created_at)}
        for r in rows
    ]}


@router.post("/api/research/{job_id}/generations/{gen_id}/cancel")
async def cancel_generation(job_id: str, gen_id: int, db: AsyncSession = Depends(get_db)):
    """queued → canceled. 도는(running) 생성은 409 — 끝날 때까지 기다린다. canceled 로 두면 디스패처(running
    만 센다)의 전역 한 자리가 비어 다음 생성이 q_research_plan 의 남은 자리를 쓰는데, 취소한 생성의 LLM
    호출은 워커에서 계속 돌므로 두 자리를 생성이 다 쓴다(D15 — 새 딥리서치의 계획이 밀린다).
    읽은 뒤 디스패처가 집었으면 조건부 UPDATE 가 바꾸지 않아 409 다. 디스패치는 보내지 않는다."""
    jid = _job_uuid(job_id)
    _writable(await _get_work(db, jid))
    gen = await _get_generation(db, jid, gen_id)
    if gen.status == "running":
        raise HTTPException(status_code=409, detail=RUNNING_NOT_CANCELABLE)
    event = _generation_event(gen_id, gen, "canceled")
    G = ResearchGeneration
    res = await db.execute(
        update(G)
        .where(G.id == gen_id, G.work_id == jid, G.status == "queued")
        .values(status="canceled", finished_at=func.now())
    )
    if res.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태입니다")
    await db.commit()
    await publish_work(jid, "generation", event)
    return {"gen_id": gen_id, "status": "canceled"}


@router.post("/api/research/{job_id}/generations/{gen_id}/retry")
async def retry_generation(job_id: str, gen_id: int, db: AsyncSession = Depends(get_db)):
    """failed·canceled 생성과 빈 결과로 끝난 핵심 개념(_retryable)을 같은 kind·target·input·priority 로 다시
    줄 세운다(새 행). 같은 생성이 이미 열려 있으면(두 번 누름) 409 — 같은 일이 두 줄 서지 않게. 동시에 두 번
    눌러도 (연구·kind·target) 잠금이 검사와 넣기를 한 줄로 세운다(잠금은 커밋·롤백까지 쥔다)."""
    jid = _job_uuid(job_id)
    _writable(await _get_work(db, jid))
    gen = await _get_generation(db, jid, gen_id)
    if not _retryable(gen):
        raise HTTPException(status_code=409, detail=f"다시 부를 수 없는 상태입니다: {gen.status}")
    G = ResearchGeneration
    await db.execute(select(func.pg_advisory_xact_lock(_retry_lock_key(jid, gen.kind, gen.target))))
    same_target = G.target.is_(None) if gen.target is None else G.target == gen.target
    if await db.scalar(
        select(G.id).where(G.work_id == jid, G.kind == gen.kind, same_target,
                           G.status.in_(GEN_OPEN_STATUSES)).limit(1)
    ) is not None:
        await db.rollback()
        raise HTTPException(status_code=409, detail="같은 생성이 이미 대기 중이거나 진행 중입니다")
    new_id = await db.scalar(
        insert(G).values(work_id=jid, kind=gen.kind, target=gen.target, priority=gen.priority,
                         status="queued", input=gen.input)
        .returning(G.id)
    )
    event = _generation_event(new_id, gen, "queued")
    await db.commit()
    _send_dispatch()
    await publish_work(jid, "generation", event)
    return {"gen_id": new_id}


@router.get("/api/research/{job_id}/work/stream")
async def stream_work(job_id: str, db: AsyncSession = Depends(get_db)):
    """연구 SSE — 접속 직후 snapshot 한 번, 그 뒤 연구 채널 이벤트를 그대로, 조용하면 ': ping'.
    하트비트 때 DB 를 다시 읽지 않는다(06a). 이벤트를 받은 화면이 해당 GET 을 다시 읽는다(spec §6-4)."""
    jid = _job_uuid(job_id)
    snapshot = {"kind": "snapshot", "work": await _view(db, await _get_work(db, jid))}

    async def _gen() -> AsyncIterator[str]:
        yield _sse(snapshot)
        async for event in subscribe_work(str(jid)):
            if event is None:
                yield ": ping\n\n"
                continue
            yield _sse(event)

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 9: `main.py` 에 등록한다**

`app/main.py` 바꾸기 ①: 라우터 import. old:

```python
from api.history import router as history_router
```

new:

```python
from api.history import router as history_router
from api.research_work import router as research_work_router
```

`app/main.py` 바꾸기 ②: 등록(파일 끝 — 끝 줄에 줄바꿈이 없다). old:

```python
app.include_router(history_router)
```

new:

```python
app.include_router(history_router)
app.include_router(research_work_router)
```

- [ ] **Step 10: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_api.py tests/test_research_work_views.py -q -p no:cacheprovider`

Expected: `76 passed, 1 warning` (API 60 + 순수 함수 16. 경고는 api 픽스처가 라우터를 import 하며 `core/config.py` 를 읽을 때 나는 `PydanticDeprecatedSince20` — 기존 전체 실행의 경고와 같은 것)

- [ ] **Step 11: 관련 기존 테스트와 전체를 돌린다**

테스트 DB(`history_sqlite`)를 함께 쓰는 테스트와 Task 1 의 모델·대역 테스트:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_models.py tests/test_history_api.py tests/test_history_repository.py tests/test_history_models.py tests/test_job_runtime.py -q -p no:cacheprovider`

Expected: `218 passed` (37 + 44 + 49 + 11 + 77 — 이 task 전과 같은 수. Task 2~10 은 이 다섯 파일을 고치지 않는다 — history 두 파일은 이 task 뒤의 Task 12 가 넓힌다)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 실패 0, `3 errors`(test_book_chat·test_build_manifest·test_loaders 수집 오류 — 기준선과 같음). Task 10 뒤 전체 수 + 76 passed, `1 skipped`. 검증 사본(Task 1 과 Task 8·9 의 모듈만 넣은 상태 — 넣기 전 `1406 passed, 1 skipped, 2 warnings, 3 errors`)에서 `1482 passed, 1 skipped, 2 warnings, 3 errors`.

더미 redis·가짜 워커 모듈이 이웃 파일로 새지 않는지(순서를 바꿔 두 번):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_work_api.py tests/test_research_work_views.py tests/test_research_api.py tests/test_research_relay.py tests/test_research_tasks.py tests/test_history_api.py -q -p no:cacheprovider`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_api.py tests/test_research_relay.py tests/test_history_api.py tests/test_research_tasks.py tests/test_research_work_views.py tests/test_research_work_api.py -q -p no:cacheprovider`

Expected: 둘 다 실패 0 — 순서대로 실행하면 `349 passed`(76 + test_research_api 110 + test_research_relay 14 + test_research_tasks 105 + test_history_api 44 — Task 2·6·7·9·10 이 앞의 세 파일에 테스트를 더했다).

- [ ] **Step 12: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a add app/api/research_work.py app/main.py app/tests/history_sqlite.py app/tests/test_research_work_api.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a commit -m "[Feat] round06a — 연구 어시스턴트 API(api/research_work.py)를 더한다. [이 연구 이어가기](완료 잡만·멱등 — 연구 행을 새로 만든 요청만 채택 근거 후보와 핵심 개념 생성 1건을 넣고 디스패치, 보내기에 실패해도 200), 연구 조회·핵심 개념/메모 고치기(개념이 바뀌면 개념 소속을 비운다), 근거 풀(이어가기 전·탐색 중에도), 이어간 연구 목록(이 브라우저 기록에 남은 것·예시 연구), 생성 취소(대기 중인 것만 — 도는 생성을 취소로 두면 디스패처의 전역 한 자리가 비어 q_research_plan 두 자리를 생성이 다 쓰므로 409)·다시(failed·canceled 와 빈 결과로 끝난 핵심 개념, 같은 생성이 열려 있으면 409 — 검사와 넣기를 연구·kind·target 잠금 안에서), 핵심 개념 생성이 열려 있는 동안 개념 고치기는 409, 연구 SSE(snapshot → 연구 채널 이벤트 → ping). 예시 연구를 바꾸는 요청은 409. 생성 이벤트의 생성 종류는 워커와 같이 gen_kind 에 싣는다(relay 가 이벤트 종류를 kind 에 넣는다). 이어가기부터 디스패처·실행기·결과 적용까지 가짜 LLM 으로 한 번 끝까지 돌리는 테스트를 둔다. main.py 에 등록하고 테스트 DB 에 research_steps·research_reading 을 더한다"
```


### Task 12: history — 이어간 연구의 단계·진행·생성 여부

spec §6-2 '기존 수정'의 history 줄·§6-4 '사이드바 갱신', 계약 §12. 사이드바가 이어간 연구의 단계·진행 요약을 보이고(06d 에서 '진행 중 생성이 있는 이어간 연구'를 폴링 조건에 더하려면) 기록 응답의 `research` 에 그 값이 실려야 한다.

- `_research_statuses` 의 research_jobs PK 조회에 research_works 를 **id 로** outer join 한다(연구 id = 잡 id). 진행 중 생성(queued·running)은 상관 EXISTS 로 센다 — research_generations 를 조인하면 생성 수만큼 행이 불어난다. history_items 와는 조인하지 않는다(ref_id 는 문자열이라 `::text` 조인은 PK 인덱스를 못 쓰고, uuid 캐스팅은 형식이 틀린 ref_id 하나에 목록 전체가 실패한다 — 지금 주석 그대로).
- `ResearchStatus` 의 새 칸 셋은 기본값이 있어, 이어가지 않은 잡의 응답에는 `"phase": null, "progress": null, "generating": false` 가 더해질 뿐이다. 기존 exact 비교 테스트 둘(`test_history_repository.py` 233행, `test_history_api.py` 349·351행)은 새 키를 넣어 고친다.
- 기록 목록의 kind 별 total 은 06d 다(여기서 하지 않는다).
- 테스트는 Task 1 이 넓힌 `history_sqlite`(`add_work`·`add_generation`)를 쓴다. Task 1 의 `make_engine` 이 BIGINT 기본키를 테스트 사본에서 INTEGER 로 만들어 두어 `add_generation` 이 번호를 받는다 — 이 task 는 history_sqlite 를 고치지 않는다.

**Files:**
- Modify: `app/schemas/history.py` (124c481 기준 47-49행 `ResearchStatus`)
- Modify: `app/repositories/history.py` (124c481 기준 import 5-10행, `_research_statuses` 214-221행)
- Modify: `app/tests/test_history_repository.py` (124c481 기준 import 14-15행, `TestResearchStatus.test_status_comes_from_research_jobs` 229-235행, `TestResearchStatus` 끝 `test_other_kinds_have_no_research` 248-252행)
- Modify: `app/tests/test_history_api.py` (124c481 기준 import 19행, `TestResearchStatus` 345-352행)
- Test: `app/tests/test_history_repository.py`, `app/tests/test_history_api.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_history_repository.py` 바꾸기 ①: import. old:

```python
from history_sqlite import SID_A, SID_B, AsyncSessionOverSync, add_research_job, make_engine, raw_row
from models.history import HistoryItem
```

new:

```python
from history_sqlite import (
    SID_A, SID_B, AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
    raw_row,
)
from models.history import HistoryItem
from models.research_work import ResearchWork
```

`app/tests/test_history_repository.py` 바꾸기 ②: 기존 exact 비교에 새 키. old:

```python
        (item,), _ = _list(engine, SID_A)
        assert item.research.model_dump() == {"status": "running", "stage": "planned"}
        detail = _call(engine, lambda r: r.get(SID_A, job_id))
```

new:

```python
        (item,), _ = _list(engine, SID_A)
        # 이어가지 않은 딥리서치 — 연구 칸은 비어 있다
        assert item.research.model_dump() == {
            "status": "running", "stage": "planned",
            "phase": None, "progress": None, "generating": False,
        }
        detail = _call(engine, lambda r: r.get(SID_A, job_id))
```

`app/tests/test_history_repository.py` 바꾸기 ③: `TestResearchStatus` 뒤(`TestPatch` 앞)에 도우미와 새 클래스. old:

```python
    def test_other_kinds_have_no_research(self, engine):
        job_id = add_research_job(engine, status="completed", stage="synthesized")
        _put(engine, SID_A, uuid.uuid4(), kind="book", ref_id=str(job_id))
        (item,), _ = _list(engine, SID_A)
        assert item.research is None
```

new:

```python
    def test_other_kinds_have_no_research(self, engine):
        job_id = add_research_job(engine, status="completed", stage="synthesized")
        _put(engine, SID_A, uuid.uuid4(), kind="book", ref_id=str(job_id))
        (item,), _ = _list(engine, SID_A)
        assert item.research is None


def _continued(engine, *, phase: str = "topics", progress: dict | None = None) -> uuid.UUID:
    """[이 연구 이어가기] 를 누른 딥리서치 — 완료 잡 + 연구 행 + 기록 한 줄."""
    job_id = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, job_id, owner_sid=str(SID_A), phase=phase)
    if progress is not None:
        with engine.begin() as conn:
            conn.execute(sa.update(ResearchWork.__table__)
                         .where(ResearchWork.__table__.c.id == job_id).values(progress=progress))
    _put(engine, SID_A, job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
    return job_id


class TestContinuedResearch:
    """이어간 연구는 기록 줄에 단계·진행 요약·진행 중 생성 여부를 함께 싣는다(사이드바용)."""

    def test_phase_and_progress_come_from_research_works(self, engine):
        job_id = _continued(engine, phase="reading", progress={"topics": 4, "picked": 1})

        (item,), _ = _list(engine, SID_A)

        assert item.research.model_dump() == {
            "status": "completed", "stage": "synthesized",
            "phase": "reading", "progress": {"topics": 4, "picked": 1}, "generating": False,
        }
        detail = _call(engine, lambda r: r.get(SID_A, job_id))
        assert detail.research.phase == "reading"

    @pytest.mark.parametrize("status", ["queued", "running"])
    def test_open_generation_marks_generating(self, engine, status):
        job_id = _continued(engine)
        add_generation(engine, job_id, status=status)

        (item,), _ = _list(engine, SID_A)

        assert item.research.generating is True

    @pytest.mark.parametrize("status", ["done", "failed", "canceled"])
    def test_finished_generations_do_not_count(self, engine, status):
        job_id = _continued(engine)
        add_generation(engine, job_id, status=status)

        (item,), _ = _list(engine, SID_A)

        assert item.research.generating is False

    def test_many_generations_still_give_one_status_per_job(self, engine):
        job_id = _continued(engine)
        for status in ("queued", "queued", "done"):
            add_generation(engine, job_id, status=status)

        items, _ = _list(engine, SID_A)

        assert len(items) == 1 and items[0].research.generating is True

    def test_generations_of_another_research_do_not_leak(self, engine):
        quiet = _continued(engine)
        busy = _continued(engine)
        add_generation(engine, busy, status="running")

        items, _ = _list(engine, SID_A)

        generating = {uuid.UUID(i.ref_id): i.research.generating for i in items}
        assert generating == {quiet: False, busy: True}

    def test_status_query_joins_works_by_job_id_not_history(self, engine):
        """history_items.ref_id(문자열)로 조인하면 PK 인덱스를 못 쓰고, 캐스팅하면 형식이 틀린
        ref_id 하나에 목록 전체가 실패한다 — 연구 칸은 research_jobs PK 조회에 붙인다."""
        _continued(engine)
        statements: list[str] = []

        @sa.event.listens_for(engine, "before_cursor_execute")
        def _record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        _list(engine, SID_A)

        (status_sql,) = [s for s in statements if "research_works" in s]
        assert "LEFT OUTER JOIN research_works ON research_works.id = research_jobs.id" in status_sql
        assert "history_items" not in status_sql
```

`app/tests/test_history_api.py` 바꾸기 ①: import. old:

```python
from history_sqlite import SID_A, SID_B, AsyncSessionOverSync, add_research_job, make_engine, raw_row
```

new:

```python
from history_sqlite import (
    SID_A, SID_B, AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
    raw_row,
)
```

`app/tests/test_history_api.py` 바꾸기 ②: 기존 exact 비교에 새 키, 이어간 연구 한 건. old:

```python
class TestResearchStatus:
    def test_list_and_detail_carry_job_status(self, api):
        job_id = add_research_job(api.engine, status="awaiting_approval", stage="planned")
        res = api.put(job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
        assert res.json()["research"] == {"status": "awaiting_approval", "stage": "planned"}
        (item,) = api.client.get("/api/history?kind=research", headers=A).json()["items"]
        assert item["research"] == {"status": "awaiting_approval", "stage": "planned"}
        assert item["ref_id"] == str(job_id)
```

new:

```python
class TestResearchStatus:
    _NOT_CONTINUED = {"phase": None, "progress": None, "generating": False}

    def test_list_and_detail_carry_job_status(self, api):
        job_id = add_research_job(api.engine, status="awaiting_approval", stage="planned")
        res = api.put(job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
        assert res.json()["research"] == {
            "status": "awaiting_approval", "stage": "planned", **self._NOT_CONTINUED,
        }
        (item,) = api.client.get("/api/history?kind=research", headers=A).json()["items"]
        assert item["research"] == {
            "status": "awaiting_approval", "stage": "planned", **self._NOT_CONTINUED,
        }
        assert item["ref_id"] == str(job_id)

    def test_continued_research_carries_phase_and_open_generation(self, api):
        job_id = add_research_job(api.engine, status="completed", stage="synthesized")
        add_work(api.engine, job_id, owner_sid=str(SID_A))
        add_generation(api.engine, job_id, status="running")
        api.put(job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))

        (item,) = api.client.get("/api/history?kind=research", headers=A).json()["items"]

        assert item["research"] == {
            "status": "completed", "stage": "synthesized",
            "phase": "topics", "progress": {}, "generating": True,
        }
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_history_repository.py -q -p no:cacheprovider`
Expected: `10 failed, 48 passed` (기존 49 중 48 + 새 9 중 0)
- `test_open_generation_marks_generating[queued|running]`·`test_finished_generations_do_not_count[done|failed|canceled]`·`test_many_generations_still_give_one_status_per_job`·`test_generations_of_another_research_do_not_leak` (7건): `AttributeError: 'ResearchStatus' object has no attribute 'generating'`
- `test_status_comes_from_research_jobs`·`test_phase_and_progress_come_from_research_works`: dict 비교 실패(`Right contains 3 more items`)
- `test_status_query_joins_works_by_job_id_not_history`: `ValueError: not enough values to unpack (expected 1, got 0)` (research_works 를 읽는 문장이 없다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_history_api.py -q -p no:cacheprovider`
Expected: `2 failed, 43 passed` — 둘 다 dict 비교 실패(`Right contains 3 more items`)

- [ ] **Step 3: 구현한다**

`app/schemas/history.py` 바꾸기 ①: `ResearchStatus` 에 세 칸. old:

```python
class ResearchStatus(BaseModel):
    status: str
    stage: str
```

new:

```python
class ResearchStatus(BaseModel):
    status: str
    stage: str
    # 아래 셋은 [이 연구 이어가기] 로 연구 행(research_works)이 생긴 잡에만 값이 있다
    phase: str | None = None
    progress: dict | None = None
    # 진행 중 생성(queued·running)이 있는가 — 사이드바가 폴링을 이어갈지 정한다(06d)
    generating: bool = False
```

`app/repositories/history.py` 바꾸기 ①: import. old:

```python
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.history import HistoryItem
from models.research import ResearchJob
```

new:

```python
from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.history import HistoryItem
from models.research import ResearchJob
from models.research_work import GEN_OPEN_STATUSES, ResearchGeneration, ResearchWork
```

`app/repositories/history.py` 바꾸기 ②: `_research_statuses` 의 PK 조회에 연구 행·진행 중 생성. old:

```python
        job_ids = {jid for jid in map(_as_uuid, refs) if jid is not None}
        if not job_ids:
            return {}
        rows = (await self.db.execute(
            select(ResearchJob.id, ResearchJob.status, ResearchJob.stage)
            .where(ResearchJob.id.in_(job_ids))
        )).all()
        return {r.id: ResearchStatus(status=r.status, stage=r.stage) for r in rows}
```

new:

```python
        # 이어간 연구의 단계·진행 요약은 같은 PK 조회에 research_works 를 id 로 붙여 읽는다
        # (연구 id = 잡 id). 진행 중 생성은 행을 늘리지 않게 EXISTS 로 센다.
        job_ids = {jid for jid in map(_as_uuid, refs) if jid is not None}
        if not job_ids:
            return {}
        generating = exists().where(
            ResearchGeneration.work_id == ResearchJob.id,
            ResearchGeneration.status.in_(GEN_OPEN_STATUSES),
        )
        rows = (await self.db.execute(
            select(ResearchJob.id, ResearchJob.status, ResearchJob.stage,
                   ResearchWork.phase, ResearchWork.progress,
                   generating.label("generating"))
            .select_from(ResearchJob)
            .outerjoin(ResearchWork, ResearchWork.id == ResearchJob.id)
            .where(ResearchJob.id.in_(job_ids))
        )).all()
        return {
            r.id: ResearchStatus(status=r.status, stage=r.stage, phase=r.phase,
                                 progress=r.progress, generating=bool(r.generating))
            for r in rows
        }
```

Postgres 로 그린 문장(검증 사본에서 `postgresql.dialect()` 로 컴파일해 확인): `SELECT research_jobs.id, research_jobs.status, research_jobs.stage, research_works.phase, research_works.progress, EXISTS (SELECT * FROM research_generations WHERE research_generations.work_id = research_jobs.id AND research_generations.status IN (...)) AS generating FROM research_jobs LEFT OUTER JOIN research_works ON research_works.id = research_jobs.id WHERE research_jobs.id IN (...)` — EXISTS 는 바깥 research_jobs 에 상관되고, `research_generations.work_id` 인덱스(Task 1 `index=True`)를 쓴다.

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_history_repository.py tests/test_history_api.py -q -p no:cacheprovider`
Expected: `103 passed` (저장소 58 = 기존 49 + 새 9, API 45 = 기존 44 + 새 1)

관련 묶음(history_sqlite 를 쓰는 파일과 모델 테스트):

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_history_repository.py tests/test_history_api.py tests/test_history_models.py tests/test_job_runtime.py -q -p no:cacheprovider`
Expected: 실패 0 (검증 사본에서 `191 passed`. Task 1 이 test_history_models 에 테스트를 더했으면 그만큼 많다)

전체:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`
Expected: 실패 0, 수집 오류 3(기준선과 같음). Task 11 뒤 전체 수치 + 10 passed(순서대로 실행하면 1687 → 1697).

- [ ] **Step 5: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a add app/schemas/history.py app/repositories/history.py app/tests/test_history_repository.py app/tests/test_history_api.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a commit -m "[Feat] round06a — 기록 목록·상세의 research 에 이어간 연구의 단계(phase)·진행 요약(progress)·진행 중 생성 여부(generating)를 싣는다: research_jobs PK 조회에 research_works 를 id 로 outer join 하고 queued·running 생성은 EXISTS 로 센다(history_items 와는 조인하지 않는다). 이어가지 않은 잡은 null·null·false"
```


### Task 13: 프론트 — 대기 순번 덧붙임·429 browser_active 안내·회차 adopted_papers

spec §5-1(근거 장부 데이터)·§6-4·§6-6 의 06a 줄·§8 프론트, 계약 §13. 딥리서치 화면은 그대로 두고 세 가지만 받는다.

- **대기 순번:** GET `/api/research/{id}` 의 `queue`(대기 중이면 `{ahead, eta_sec}`, 아니면 `null`), snapshot 의 `job.queue`(대기 중일 때만 실림), 스트림의 새 `queue` 이벤트, 승인·재시도 응답의 `queue`(첫 하트비트 15초를 기다리지 않게 — 계약 §7). 화면은 지금 queued 문구 **뒤에** 순번 한 줄을 덧붙이기만 한다 — 기존 문구는 한 글자도 바꾸지 않는다.
- **429 browser_active:** 승인·재시도가 같은 브라우저의 다른 딥리서치에 막히면 detail 이 `{code: "browser_active", message, job_id}` 다(계약 §6). 그 문구를 보이고 rs-alert 아래에 [진행 중인 연구 보기] 링크를 단다. `shared_queue`·code 없는 문자열 429·503 은 지금 문구 그대로다.
- **adopted_papers:** `critique` 이벤트와 `steps[].result.rounds[]` 의 회차 끝 채택 근거(계약 §3)를 `RoundView.adoptedPapers` 로 받는다. 화면(근거 장부)은 06b 다 — 이 task 는 데이터만 받는다.

모든 새 필드는 선택이다. 06a 백엔드가 배포되기 전 서버(키 없음)에서는 `queue` 가 `null`, `adoptedPapers` 가 `[]` 라 화면이 지금과 같다 — 백엔드 Task 3·6·7 보다 먼저 머지돼도 된다. `.vue` 는 단위 테스트 대상이 아니므로(마운트 도구 없음) 문구는 순수 함수 `queueLine` 으로 빼서 테스트하고, `.vue` 는 `nuxi typecheck`·`npm run build` 로 확인한다.

- **계약과 다르게 한 곳(실측 근거):**
  - ProgressPanel 의 덧붙임은 계약의 `<span v-if="queueLine"> {{ queueLine }}</span>` 이 아니라 `<span v-if="queueLine">{{ " " + queueLine }}</span>` 다. Vue 컴파일러(whitespace: condense)가 `<span>` 첫머리의 공백 텍스트 노드를 지워 "시작합니다.앞에 2건" 으로 붙는다(`@vue/compiler-sfc` 로 컴파일해 `_toDisplayString(_ctx.queueLine)` — 공백 없음 — 을 확인했다).
  - `queue` 이벤트는 화면이 대기 중(approved·queued)일 때만 싣고, 종료 이벤트(done·failed·canceled)도 `queue` 를 비운다(계약은 status 이벤트만 말한다). 늦게 온 순번이 탐색 중·종료 화면에 남지 않게 하는 것이다.
  - 승인·재시도 응답의 순번은 계약 예시(`{...view, queue: toQueueView(res.queue)}`)대로 덮어쓰지 않고 새 순수 함수 `applyQueue(view, res.queue)` 로 싣는다. 응답보다 스트림이 먼저 running 을 알린 화면(`applyApproval` 이 status 를 되돌리지 않는 바로 그 경우)에 늦은 순번이 남지 않게 대기 중일 때만 싣고, 순번 키가 없는 옛 서버 응답(`undefined`)이면 화면 값을 그대로 둔다. composable 은 단위 테스트 대상이 아니라서 판단을 순수 함수로 빼 테스트한다. `toQueueView` 라는 이름은 만들지 않는다(같은 변환은 비공개 `queueFor` 가 한다).
  - `activeJobId` 는 새 시도·성공 때뿐 아니라 `setActionError` 와 `refresh()` 실패(actionError 를 다른 문구로 덮는 두 곳)에서도 비운다 — 링크가 엉뚱한 문구 아래 남지 않게.
  - `nuxi typecheck` 는 `tests/` 도 본다(`.nuxt/tsconfig.app.json` include `../**/*`). `RoundView`·`ResearchView` 에 필수 필드가 생기므로 타입을 붙여 만든 픽스처 둘(`reportDocument.test.ts`·`researchReport.test.ts`)에 `adoptedPapers: []`·`queue: null` 을 더한다.
  - 대기 카드 `.rs-card--wait` 는 `flex-direction: row` 라 순번 줄이 첫 줄 **옆**에 선다. CSS 는 06d(연구 화면 skx 토큰 재입히기) 몫이라 이 task 에서 바꾸지 않는다.

**Files:**
- Modify: `frontend/types/research.ts` (124c481 기준 `SearchRoundResult` 22-37행, `ExcludedPaper` 주석 39행, `ResearchJob` 177-191행, `ResearchApproveResponse`·`ResearchRetryResponse` 198-208행, `SnapshotEvent` 216-225행, `CritiqueEvent` 263-266행, `CanceledEvent`·`ResearchEvent` 303-318행, `RoundView` 323-335행, `ResearchView` 397-415행)
- Modify: `frontend/utils/researchEvents.ts` (import 2-33행, `TERMINAL_STATUSES` 55행, `isTerminalEvent` 86-88행, `initialResearchView` 232-233행, `applyResearchEvent` 271-298행, `applySnapshot` 303-306행, `applyCritique` 366-370행, `roundsFromQueries` 535-538행, `toExcludedPaperView`·`toRoundView`·`blankRound` 542-571행)
- Modify: `frontend/utils/researchErrors.ts` (`researchErrorMessage` 35-37행)
- Modify: `frontend/composables/useResearch.ts` (researchEvents import 13-22행, researchErrors import 23행, refs 79-80행, `setActionError` 103-106행, `refresh` catch 155-157행, `act` catch 285-287행, `approve`·`retry` 응답 처리 299-311행, 반환 346-349행)
- Modify: `frontend/components/research/ProgressPanel.vue` (template 10행, props 136-137행)
- Modify: `frontend/pages/research/[id].vue` (template 40·58-60·138행, script 172·188-189·192행)
- Test: `frontend/tests/unit/researchErrors.test.ts` (import 3행, 51행 뒤에 두 describe)
- Test: `frontend/tests/unit/researchEvents.test.ts` (import 18-19·25-26행, 정확 비교 170-171·875-876행, 파일 끝에 세 describe)
- Test(타입 픽스처): `frontend/tests/unit/reportDocument.test.ts` (Task 4 적용 뒤 430·468행 — 124c481 기준 418·456행), `frontend/tests/unit/researchReport.test.ts` (210행)

전제: Task 0 에서 `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npm ci && npx nuxi typecheck` 를 돌려 `.nuxt/` 가 있다(없으면 vitest 가 `TSConfckParseError … .nuxt/tsconfig.app.json` 으로 전부 실패한다). 프론트를 고치는 앞 task 는 Task 4 하나다 — `reportDocument.test.ts` 에 import 1줄과 테스트 1개(11줄)를 더하고 `tests/fixtures/citation_reference.json` 을 만든다. 이 task 의 `old` 블록은 Task 4 가 고친 곳과 겹치지 않는다. 기준선(Task 4 적용 뒤): `researchErrors.test.ts` 10 + `researchEvents.test.ts` 91 = 101 passed, 전체 28 files / 496 passed(124c481 의 495 + Task 4 의 1), typecheck 오류 0, build 완료.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

① `frontend/tests/unit/researchErrors.test.ts` — import 에 `activeResearchId` 를 더한다. old:

```ts
import { detailMessage, httpStatus, pdfCheckProblem, researchErrorMessage } from "~/utils/researchErrors";
```

new:

```ts
import { activeResearchId, detailMessage, httpStatus, pdfCheckProblem, researchErrorMessage } from "~/utils/researchErrors";
```

같은 파일, `describe("pdfCheckProblem", () => {` 바로 앞에 아래를 넣는다(`describe("researchErrorMessage", …)` 블록과 기존 "429·503 은 잠시 뒤 다시 안내한다" 단언은 그대로 둔다 — 문자열 429 회귀선이다). old:

```ts
describe("pdfCheckProblem", () => {
```

new:

```ts
// 브라우저당 실행 제한(api/research.py _to_run_queue) — 승인·재시도가 같은 브라우저의 다른 연구에 막히면
// detail 이 {code, message, job_id} 객체로 온다. 공유 큐 제한은 code 가 shared_queue 다
const ACTIVE_JOB = "22222222-2222-4222-8222-222222222222";
const BROWSER_ACTIVE = {
  code: "browser_active",
  message: "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요",
  job_id: ACTIVE_JOB,
};

describe("researchErrorMessage — 429 code", () => {
  it("browser_active 면 서버 문구를, 문구가 비었으면 같은 기본 문구를 쓴다", () => {
    expect(researchErrorMessage(fetchError(429, BROWSER_ACTIVE), "계획을 승인하지 못했습니다"))
      .toBe("진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요");
    expect(researchErrorMessage(fetchError(429, { ...BROWSER_ACTIVE, message: " 다른 탭의 연구가 돌고 있습니다 " }), "실패"))
      .toBe("다른 탭의 연구가 돌고 있습니다");
    expect(researchErrorMessage(fetchError(429, { code: "browser_active", message: "", job_id: ACTIVE_JOB }), "실패"))
      .toBe("진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요");
  });

  it("공유 큐(shared_queue)·code 가 없는 429 는 지금 문구 그대로다", () => {
    const crowded = "요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요";
    expect(researchErrorMessage(fetchError(429, { code: "shared_queue", message: "다른 딥리서치가 실행 중이다" }), "실패")).toBe(crowded);
    expect(researchErrorMessage(fetchError(429, "다른 딥리서치가 실행 중이다"), "실패")).toBe(crowded);
    expect(researchErrorMessage(fetchError(429), "실패")).toBe(crowded);
  });
});

describe("activeResearchId", () => {
  it("429 browser_active 면 진행 중인 연구 id 를 준다", () => {
    expect(activeResearchId(fetchError(429, BROWSER_ACTIVE))).toBe(ACTIVE_JOB);
  });

  it("다른 429·다른 상태·id 가 없는 detail·네트워크 오류는 null", () => {
    expect(activeResearchId(fetchError(429, { code: "shared_queue", message: "x" }))).toBeNull();
    expect(activeResearchId(fetchError(429, "x"))).toBeNull();
    expect(activeResearchId(fetchError(429, { code: "browser_active", message: "m" }))).toBeNull();
    expect(activeResearchId(fetchError(409, BROWSER_ACTIVE))).toBeNull();
    expect(activeResearchId(new Error("Failed to fetch"))).toBeNull();
    expect(activeResearchId(null)).toBeNull();
  });
});

describe("pdfCheckProblem", () => {
```

② `frontend/tests/unit/researchEvents.test.ts` — import 에 `applyQueue`·`queueLine` 을 더한다. old:

```ts
  applyApproval,
  applyResearchEvent,
```

new:

```ts
  applyApproval,
  applyQueue,
  applyResearchEvent,
```

old:

```ts
  mergeEvidence,
  refreshView,
  researchPhase,
```

new:

```ts
  mergeEvidence,
  queueLine,
  refreshView,
  researchPhase,
```

같은 파일, 회차를 통째로 비교하는 두 테스트("검색·점검 이벤트로 회차를 쌓고 재검색 장면을 강조한다", "단계 결과에 rounds 가 없으면 report.trail 로 회차를 대신 보여 준다")에 새 필드 `adoptedPapers: []` 를 넣는다 — 검색 이벤트·trail·queries 로 만든 회차는 채택 목록이 비어 있어야 한다. old(170-171행):

```ts
      { round: 1, query: "효과 측정", foundChunks: 12, newPapers: 5, verdict: "insufficient", note: "초등 대상 연구가 없다", nextQuery: "초등 AI 윤리 교육 효과", excluded: null, excludedPapers: [], flagged: null },
      { round: 2, query: "초등 AI 윤리 교육 효과", foundChunks: 9, newPapers: 4, verdict: null, note: "", nextQuery: null, excluded: null, excludedPapers: [], flagged: null },
```

new:

```ts
      { round: 1, query: "효과 측정", foundChunks: 12, newPapers: 5, verdict: "insufficient", note: "초등 대상 연구가 없다", nextQuery: "초등 AI 윤리 교육 효과", excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [] },
      { round: 2, query: "초등 AI 윤리 교육 효과", foundChunks: 9, newPapers: 4, verdict: null, note: "", nextQuery: null, excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [] },
```

old(875-876행):

```ts
      { round: 1, query: "효과 측정", foundChunks: null, newPapers: null, verdict: "insufficient", note: "", nextQuery: "초등 효과", excluded: null, excludedPapers: [], flagged: null },
      { round: 2, query: "초등 효과", foundChunks: null, newPapers: null, verdict: "sufficient", note: "충분하다", nextQuery: null, excluded: null, excludedPapers: [], flagged: null },
```

new:

```ts
      { round: 1, query: "효과 측정", foundChunks: null, newPapers: null, verdict: "insufficient", note: "", nextQuery: "초등 효과", excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [] },
      { round: 2, query: "초등 효과", foundChunks: null, newPapers: null, verdict: "sufficient", note: "충분하다", nextQuery: null, excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [] },
```

같은 파일 끝(마지막 `describe("stopPoint — 멈춘 지점", …)` 의 닫는 `});` 뒤)에 빈 줄 하나를 두고 아래를 붙인다. 파일 위쪽의 `job`·`step`·`run`·`SEARCH_STARTED`·`ROUND1`·`ROUND2`·`SAVED`·`LIVE`·`PLAN_ROW`·`SAVED_SEARCH_ROW` 를 그대로 쓴다.

```ts
describe("근거 장부 데이터 — adopted_papers", () => {
  // 회차 끝 이 하위질문의 채택 근거(순위순) — 그 회차에 새로 채택된 논문만 서지를 싣는다(runner._adopted_papers)
  const ADOPTED = [
    { cnts_id: "C1", rank: 1 },
    { cnts_id: "C2", title: " 초등 AI 윤리 수업의 효과 ", personal_author: "김철수; 이영희", pub_date: "2019-03", rank: 2, new: true },
  ];
  const ADOPTED_VIEW = [
    { cntsId: "C1", rank: 1, title: null, personalAuthor: null, pubDate: null, isNew: false },
    { cntsId: "C2", rank: 2, title: "초등 AI 윤리 수업의 효과", personalAuthor: "김철수; 이영희", pubDate: "2019-03", isNew: true },
  ];
  const SEARCHED: ResearchEvent[] = [
    SEARCH_STARTED,
    { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
  ];
  const CRITIQUE: CritiqueEvent = {
    kind: "critique", subq_idx: 0, verdict: "insufficient", note: "초등 대상 연구가 없다", adopted: 2,
    parse_failed: false, capped: 0, round: 1, next_query: "초등 AI 윤리 교육 효과", will_recheck: true,
  };

  it("점검 이벤트의 채택 목록을 그 회차에 싣고, 보내지 않는 옛 워커는 빈 목록으로 둔다", () => {
    const live = run([...SEARCHED, { ...CRITIQUE, adopted_papers: ADOPTED }]);
    expect(live.subqs[0]!.rounds[0]!.adoptedPapers).toEqual(ADOPTED_VIEW);
    // 검색 이벤트는 채택을 모른다 — 다음 회차는 그 회차의 점검이 올 때까지 빈 목록이다
    const next = applyResearchEvent(live, {
      kind: "search", subq_idx: 0, query: "초등 AI 윤리 교육 효과", found: 9, round: 2, new_papers: 4,
    });
    expect(next.subqs[0]!.rounds.map((r) => r.adoptedPapers.length)).toEqual([2, 0]);
    expect(run([...SEARCHED, CRITIQUE]).subqs[0]!.rounds[0]!.adoptedPapers).toEqual([]);
  });

  it("진행 저장본 회차로 다시 연 화면(GET)·재접속 snapshot 이 라이브와 같은 장부를 받고, 필드가 없는 옛 회차는 빈 목록이다", () => {
    const saved = step({
      ...SAVED_SEARCH_ROW,
      result: { rounds: [{ ...ROUND1, adopted_papers: ADOPTED }, ROUND2], counters: LIVE },
    });
    const opened = initialResearchView(job({ steps: [PLAN_ROW, saved] }));
    expect(opened.subqs[0]!.rounds.map((r) => r.adoptedPapers)).toEqual([ADOPTED_VIEW, []]);
    const resumed = applyResearchEvent(initialResearchView(job({ steps: [PLAN_ROW] })), {
      kind: "snapshot",
      steps: [PLAN_ROW, saved],
      job: { status: "running", stage: "planned", plan: ["효과 측정", "교사 인식"] },
    });
    expect(resumed.subqs[0]!.rounds.map((r) => r.adoptedPapers)).toEqual([ADOPTED_VIEW, []]);
    // 뒤따르는 진행 저장 step 이벤트가 같은 회차 기록을 실어도 라이브로 받은 장부 그대로다
    const live = run([...SEARCHED, { ...CRITIQUE, adopted_papers: ADOPTED }]);
    const stepped = applyResearchEvent(live, {
      ...SEARCH_STARTED,
      result: { rounds: [{ ...ROUND1, adopted_papers: ADOPTED }], counters: SAVED },
    });
    expect(stepped.subqs[0]!.rounds[0]!.adoptedPapers).toEqual(ADOPTED_VIEW);
  });
});

describe("대기 순번 — queue", () => {
  const WAITING = { ahead: 2, eta_sec: 1500 };

  it("GET 응답의 순번을 받고, 대기 중이 아니거나 순번을 싣지 않은 옛 서버면 null 이다", () => {
    expect(initialResearchView(job({ status: "queued", queue: WAITING })).queue).toEqual({ ahead: 2, etaSec: 1500 });
    expect(initialResearchView(job({ status: "approved", queue: { ahead: 0, eta_sec: null } })).queue)
      .toEqual({ ahead: 0, etaSec: null });
    expect(initialResearchView(job({ status: "running", queue: WAITING })).queue).toBeNull();
    expect(initialResearchView(job({ status: "queued" })).queue).toBeNull();
  });

  it("snapshot 의 job.queue 로 맞추고, 싣지 않았으면(대기를 벗어남·옛 서버) 비운다", () => {
    const start = initialResearchView(job({ status: "queued", queue: WAITING }));
    const moved = applyResearchEvent(start, {
      kind: "snapshot",
      steps: [],
      job: { status: "queued", stage: "planned", plan: ["효과 측정", "교사 인식"], queue: { ahead: 1, eta_sec: 600 } },
    });
    expect(moved.queue).toEqual({ ahead: 1, etaSec: 600 });
    const picked = applyResearchEvent(moved, {
      kind: "snapshot",
      steps: [],
      job: { status: "running", stage: "planned", plan: ["효과 측정", "교사 인식"] },
    });
    expect(picked.queue).toBeNull();
  });

  it("queue 이벤트가 순번을 바꾸고, 대기를 벗어난 화면에 늦게 온 이벤트는 싣지 않는다", () => {
    const start = initialResearchView(job({ status: "queued", queue: WAITING }));
    expect(applyResearchEvent(start, { kind: "queue", ahead: 0, eta_sec: 300 }).queue).toEqual({ ahead: 0, etaSec: 300 });
    const running = initialResearchView(job({ status: "running" }));
    expect(applyResearchEvent(running, { kind: "queue", ahead: 1, eta_sec: null })).toBe(running);
  });

  it("status 가 대기 안에서 바뀌면 순번을 남기고, 대기를 벗어나거나 잡이 끝나면 비운다", () => {
    const approved = initialResearchView(job({ status: "approved", queue: WAITING }));
    expect(applyResearchEvent(approved, { kind: "status", status: "queued", stage: "planned" }).queue)
      .toEqual({ ahead: 2, etaSec: 1500 });
    expect(applyResearchEvent(approved, { kind: "status", status: "running", stage: "planned" }).queue).toBeNull();
    expect(applyResearchEvent(approved, { kind: "canceled", status: "canceled" }).queue).toBeNull();
    expect(applyResearchEvent(approved, { kind: "failed", status: "failed", error: "x" }).queue).toBeNull();
  });

  it("GET 재동기화(refreshView)는 새로 읽은 순번을 쓴다", () => {
    const prev = initialResearchView(job({ status: "queued", queue: { ahead: 3, eta_sec: 2400 } }));
    expect(refreshView(prev, job({ status: "queued", queue: { ahead: 1, eta_sec: 900 } })).queue)
      .toEqual({ ahead: 1, etaSec: 900 });
    expect(refreshView(prev, job({ status: "running", queue: null })).queue).toBeNull();
  });

  it("승인·재시도 응답의 순번을 바로 싣고, 스트림이 먼저 대기를 벗어났거나 순번 키가 없는 옛 서버면 그대로 둔다", () => {
    // 승인 응답(applyApproval 로 approved) — 첫 하트비트(15초)를 기다리지 않고 순번이 보인다
    const approved = applyApproval(initialResearchView(job({ status: "awaiting_approval", started_at: null })), "approved", null);
    expect(applyQueue(approved, WAITING).queue).toEqual({ ahead: 2, etaSec: 1500 });
    // 재시도 응답(status 이벤트로 queued)
    const retried = applyResearchEvent(initialResearchView(job({ status: "failed" })), {
      kind: "status", status: "queued", stage: "planned",
    });
    expect(applyQueue(retried, { ahead: 0, eta_sec: null }).queue).toEqual({ ahead: 0, etaSec: null });
    // 응답보다 스트림이 먼저 running 을 알렸다 — applyApproval 이 status 를 되돌리지 않는 경우와 같다
    const running = initialResearchView(job({ status: "running" }));
    expect(applyQueue(running, WAITING)).toBe(running);
    const waiting = initialResearchView(job({ status: "queued", queue: { ahead: 3, eta_sec: 2400 } }));
    expect(applyQueue(waiting, undefined)).toBe(waiting);
    expect(applyQueue(waiting, null).queue).toBeNull();
  });
});

describe("queueLine — queued 문구 뒤에 덧붙이는 순번", () => {
  it("순번을 모르면 덧붙이지 않는다", () => {
    expect(queueLine(null)).toBeNull();
  });

  it("앞에 없으면 다음 차례라고, 있으면 건수와 분 단위 어림(올림·최소 1분)을 쓴다", () => {
    expect(queueLine({ ahead: 0, etaSec: 300 })).toBe("바로 다음 차례입니다");
    expect(queueLine({ ahead: 2, etaSec: null })).toBe("앞에 2건");
    expect(queueLine({ ahead: 2, etaSec: 1500 })).toBe("앞에 2건 · 약 25분");
    expect(queueLine({ ahead: 1, etaSec: 61 })).toBe("앞에 1건 · 약 2분");
    expect(queueLine({ ahead: 1, etaSec: 0 })).toBe("앞에 1건 · 약 1분");
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx vitest run tests/unit/researchErrors.test.ts tests/unit/researchEvents.test.ts`
Expected: `Test Files 2 failed (2)` / `Tests 15 failed | 100 passed (115)`.
- researchErrors 3건: "browser_active 면 서버 문구를…" 은 `AssertionError: expected '요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요' to be '진행 중인 딥리서치가 있습니다 — …'`, `activeResearchId` 두 건은 `TypeError: (0 , activeResearchId) is not a function`. "공유 큐(shared_queue)·code 가 없는 429 는 지금 문구 그대로다" 는 지금도 통과한다(회귀선).
- researchEvents 12건: 회차 정확 비교 2건(`adoptedPapers` 없음), adopted_papers 2건(`undefined` 를 `ADOPTED_VIEW` 와 비교), 대기 순번 5건(`queue` 가 `undefined`), 승인·재시도 응답 1건(`TypeError: (0 , applyQueue) is not a function`), `queueLine` 2건(`TypeError: (0 , queueLine) is not a function`).

- [ ] **Step 3: 타입을 더한다 (`frontend/types/research.ts`)**

① `SearchRoundResult` 끝에 `adopted_papers`, 그 아래 새 `AdoptedPaper`. old:

```ts
  // 무관 제외를 끈 잡(exclude_off_topic=0)이 빼지 않고 무관하다고만 본 수. 그 하위질문에서 처음 본 논문만
  // 센다(빼지 않은 논문은 다음 회차 목록에 남아 또 가리켜진다). 켠 잡은 0, 그 전 잡에는 없다
  flagged?: number | null;
}

// 자기점검이 무관하다고 보고 뺀 논문의 서지 요약(회차 기록·보고서 trail)
```

new:

```ts
  // 무관 제외를 끈 잡(exclude_off_topic=0)이 빼지 않고 무관하다고만 본 수. 그 하위질문에서 처음 본 논문만
  // 센다(빼지 않은 논문은 다음 회차 목록에 남아 또 가리켜진다). 켠 잡은 0, 그 전 잡에는 없다
  flagged?: number | null;
  // 회차 끝 이 하위질문의 채택 근거(순위순) — 근거 장부(06b)가 rounds 만으로 다시 그린다. 기록하기 전 잡에는 없다
  adopted_papers?: AdoptedPaper[] | null;
}

// 회차 끝 채택 근거 한 편(runner._adopted_papers). rank 는 1부터. 그 회차에 새로 채택된 논문(new)만
// 서지를 싣는다 — 나머지는 앞 회차의 같은 cnts_id 에 서지가 있다
export interface AdoptedPaper {
  cnts_id: string;
  rank: number;
  title?: string | null;
  personal_author?: string | null;
  pub_date?: string | null;
  new?: boolean;
}

// 자기점검이 무관하다고 보고 뺀 논문의 서지 요약(회차 기록·보고서 trail)
```

② `ResearchJob` 앞에 `QueueInfo`. old:

```ts
// ── API 응답 ───────────────────────────────────────────────
export interface ResearchJob {
```

new:

```ts
// ── API 응답 ───────────────────────────────────────────────
// 대기 순번(api/research.py _queue_info) — ahead 는 앞에 있는 잡 수(도는 잡 포함), eta_sec 는 최근 완료 잡의
// 걸린 시간 중앙값으로 어림한 초(완료 잡이 없으면 null). 대기 중(approved·queued)인 잡에만 온다
export interface QueueInfo {
  ahead: number;
  eta_sec: number | null;
}

export interface ResearchJob {
```

③ `ResearchJob` 끝에 `queue`. old:

```ts
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ResearchCreateResponse {
```

new:

```ts
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  // 대기 중이 아니면 null, 순번을 싣기 전 서버에는 키가 없다
  queue?: QueueInfo | null;
}

export interface ResearchCreateResponse {
```

④ 승인·재시도 응답에 `queue`(api/research.py approve·retry 가 `_queue_info` 를 싣는다). old:

```ts
export interface ResearchApproveResponse {
  job_id: string;
  status: "approved";
  plan: string[] | null;
}

export interface ResearchRetryResponse {
  job_id: string;
  status: "queued";
  stage: ResearchStage;
}
```

new:

```ts
export interface ResearchApproveResponse {
  job_id: string;
  status: "approved";
  plan: string[] | null;
  // 승인 직후의 대기 순번 — 첫 하트비트를 기다리지 않게 응답에 싣는다. 싣기 전 서버에는 키가 없다
  queue?: QueueInfo | null;
}

export interface ResearchRetryResponse {
  job_id: string;
  status: "queued";
  stage: ResearchStage;
  queue?: QueueInfo | null;
}
```

⑤ `SnapshotEvent.job` 에 `queue`. old:

```ts
    plan: string[] | null;
    counters?: CountersPayload;
  };
}
```

new:

```ts
    plan: string[] | null;
    counters?: CountersPayload;
    // 대기 중일 때만 싣는다
    queue?: QueueInfo | null;
  };
}
```

⑥ `CritiqueEvent` 에 `adopted_papers`. old:

```ts
  // 이번 회차에 뺀 논문의 서지와 무관 제외를 끈 잡이 무관하다고만 본 수 — 회차 기록(SearchRoundResult)과
  // 같은 값이다. 점검 직후 진행 저장이 실패해도 타임라인이 목록을 펼칠 수 있게 이벤트에도 싣는다
  excluded_papers?: ExcludedPaper[] | null;
  flagged?: number | null;
```

new:

```ts
  // 이번 회차에 뺀 논문의 서지와 무관 제외를 끈 잡이 무관하다고만 본 수 — 회차 기록(SearchRoundResult)과
  // 같은 값이다. 점검 직후 진행 저장이 실패해도 타임라인이 목록을 펼칠 수 있게 이벤트에도 싣는다
  excluded_papers?: ExcludedPaper[] | null;
  flagged?: number | null;
  // 회차 끝 채택 근거 — 회차 기록의 adopted_papers 와 같은 값이다. 보내지 않는 옛 워커는 빈 목록으로 받는다
  adopted_papers?: AdoptedPaper[] | null;
```

⑦ `QueueEvent` 를 정의한다. old:

```ts
export interface CanceledEvent {
  kind: "canceled";
  status: "canceled";
}

export type ResearchEvent =
```

new:

```ts
export interface CanceledEvent {
  kind: "canceled";
  status: "canceled";
}

// 스트림 하트비트가 대기 중인 잡의 순번을 다시 세어 바뀌었을 때만 보낸다
export interface QueueEvent {
  kind: "queue";
  ahead: number;
  eta_sec: number | null;
}

export type ResearchEvent =
```

⑧ 유니온에 넣는다. old:

```ts
  | FailedEvent
  | CanceledEvent;
```

new:

```ts
  | FailedEvent
  | CanceledEvent
  | QueueEvent;
```

⑨ `RoundView` 에 `adoptedPapers`, 그 아래 `AdoptedPaperView`. old:

```ts
  // 뺀 논문 목록이 있는 회차만 타임라인에서 펼칠 수 있다 — 목록을 기록하기 전 회차는 빈 목록
  excludedPapers: ExcludedPaperView[];
  flagged: number | null;
}
```

new:

```ts
  // 뺀 논문 목록이 있는 회차만 타임라인에서 펼칠 수 있다 — 목록을 기록하기 전 회차는 빈 목록
  excludedPapers: ExcludedPaperView[];
  flagged: number | null;
  // 회차 끝 채택 근거(순위순) — 점검 전 회차·기록하기 전 잡은 빈 목록
  adoptedPapers: AdoptedPaperView[];
}

export interface AdoptedPaperView {
  cntsId: string;
  rank: number;
  // 그 회차에 새로 채택된 논문(isNew)만 서지가 있고, 나머지는 null — 앞 회차의 같은 논문에서 찾는다
  title: string | null;
  personalAuthor: string | null;
  pubDate: string | null;
  isNew: boolean;
}
```

⑩ `ResearchView` 앞에 `QueueView`. old:

```ts
export interface ResearchView {
  jobId: string;
```

new:

```ts
export interface QueueView {
  ahead: number;
  etaSec: number | null;
}

export interface ResearchView {
  jobId: string;
```

⑪ `ResearchView` 끝에 `queue`. old:

```ts
  highlight: HighlightView | null;
  synth: SynthView;
  source: RoundSource;
}
```

new:

```ts
  highlight: HighlightView | null;
  synth: SynthView;
  source: RoundSource;
  // 대기 순번 — 대기 중(approved·queued)이고 서버가 순번을 실었을 때만 있다
  queue: QueueView | null;
}
```

- [ ] **Step 4: 리듀서를 고친다 (`frontend/utils/researchEvents.ts`)**

① import 두 곳. old:

```ts
import type {
  CountersPayload,
```

new:

```ts
import type {
  AdoptedPaper,
  AdoptedPaperView,
  CountersPayload,
```

old:

```ts
  HighlightView,
  ReportEvidence,
```

new:

```ts
  HighlightView,
  QueueInfo,
  QueueView,
  ReportEvidence,
```

② 대기 상태 상수. old:

```ts
export const TERMINAL_STATUSES: readonly ResearchStatus[] = ["completed", "failed", "canceled"];
```

new:

```ts
export const TERMINAL_STATUSES: readonly ResearchStatus[] = ["completed", "failed", "canceled"];
// 대기 순번을 보이는 상태 — 승인 직후(approved)와 재시도로 다시 큐에 든 상태(queued). 화면 단계로는 둘 다 '대기열'이다
const WAITING_STATUSES: readonly ResearchStatus[] = ["approved", "queued"];
```

③ `isTerminalEvent` 아래에 `isWaiting`·`queueFor`·`queueLine`·`applyQueue`. old:

```ts
export function isTerminalEvent(event: { kind: string }): boolean {
  return event.kind === "done" || event.kind === "failed" || event.kind === "canceled";
}
```

new:

```ts
export function isTerminalEvent(event: { kind: string }): boolean {
  return event.kind === "done" || event.kind === "failed" || event.kind === "canceled";
}

function isWaiting(status: ResearchStatus): boolean {
  return WAITING_STATUSES.includes(status);
}

// 서버는 대기 중인 잡에만 순번을 싣는다(GET 응답·snapshot.job). 대기 중이 아니거나 싣지 않은 옛 서버면 null
function queueFor(status: ResearchStatus, q: QueueInfo | null | undefined): QueueView | null {
  return q && isWaiting(status) ? { ahead: q.ahead, etaSec: q.eta_sec ?? null } : null;
}

// 대기 카드·진행 패널의 queued 문구 뒤에 덧붙이는 순번. 순번을 모르면(옛 서버·대기 아님) 덧붙이지 않는다
export function queueLine(q: QueueView | null): string | null {
  if (!q) return null;
  if (q.ahead === 0) return "바로 다음 차례입니다";
  const eta = q.etaSec !== null ? ` · 약 ${Math.max(1, Math.ceil(q.etaSec / 60))}분` : "";
  return `앞에 ${q.ahead}건${eta}`;
}

// 승인·재시도 응답이 실은 순번(api/research.py approve·retry) — 첫 하트비트(15초)를 기다리지 않고 바로 보인다.
// 응답보다 스트림이 먼저 대기를 벗어났으면(워커가 바로 집음 — applyApproval 이 status 를 되돌리지 않는 경우)
// 늦은 순번은 싣지 않고, 순번 키가 없는 옛 서버 응답(undefined)이면 화면 값을 그대로 둔다
export function applyQueue(view: ResearchView, q: QueueInfo | null | undefined): ResearchView {
  if (q === undefined || !isWaiting(view.status)) return view;
  return { ...view, queue: queueFor(view.status, q) };
}
```

④ `initialResearchView` 가 GET 의 순번을 받는다. old:

```ts
    synth: job.status === "queued" ? retiredSynth(steps) : { ...EMPTY_SYNTH },
    source: "none",
  });
```

new:

```ts
    synth: job.status === "queued" ? retiredSynth(steps) : { ...EMPTY_SYNTH },
    source: "none",
    queue: queueFor(job.status, job.queue),
  });
```

(`refreshView` 는 `rebuild({ ...fresh, … })` 라 새로 읽은 `queue` 를 그대로 받는다 — 고치지 않는다.)

⑤ `applyResearchEvent` 의 status 분기. old:

```ts
        stage: event.stage ?? view.stage,
        lastError: isTerminalStatus(event.status) ? view.lastError : null,
      };
```

new:

```ts
        stage: event.stage ?? view.stage,
        lastError: isTerminalStatus(event.status) ? view.lastError : null,
        // 대기를 벗어나면(워커가 집음·취소) 순번을 지운다 — 대기 안에서 바뀌면 다음 순번이 올 때까지 둔다
        queue: isWaiting(event.status) ? view.queue : null,
      };
```

⑥ 종료 이벤트와 새 `queue` 분기. old:

```ts
    case "done":
      return { ...view, status: "completed", highlight: null };
    case "failed":
      return { ...view, status: "failed", lastError: event.error ?? view.lastError, highlight: null };
    case "canceled":
      return { ...view, status: "canceled", highlight: null };
    default:
```

new:

```ts
    case "done":
      return { ...view, status: "completed", highlight: null, queue: null };
    case "failed":
      return { ...view, status: "failed", lastError: event.error ?? view.lastError, highlight: null, queue: null };
    case "canceled":
      return { ...view, status: "canceled", highlight: null, queue: null };
    case "queue":
      // 서버는 대기 중인 잡에만 보낸다 — 대기를 벗어난 화면에 늦게 온 순번은 싣지 않는다
      return isWaiting(view.status) ? { ...view, queue: { ahead: event.ahead, etaSec: event.eta_sec ?? null } } : view;
    default:
```

⑦ `applySnapshot` 이 `job.queue` 를 받는다. old:

```ts
    next.status = event.job.status;
    next.stage = event.job.stage;
    if (event.job.plan?.length) next.plan = event.job.plan;
```

new:

```ts
    next.status = event.job.status;
    next.stage = event.job.stage;
    // 서버는 대기 중일 때만 순번을 싣는다 — 빠졌으면 대기를 벗어났거나 옛 서버다
    next.queue = queueFor(event.job.status, event.job.queue);
    if (event.job.plan?.length) next.plan = event.job.plan;
```

⑧ `applyCritique` 가 채택 목록을 싣는다. old:

```ts
      // 뒤따르는 진행 저장 step 이벤트의 회차 기록도 같은 값을 싣지만, 저장이 실패하면 오지 않는다 —
      // 점검 이벤트의 값으로 바로 채운다. 목록을 보내지 않는 옛 워커는 빈 목록·null
      excludedPapers: (event.excluded_papers ?? []).map(toExcludedPaperView),
      flagged: event.flagged ?? null,
    };
```

new:

```ts
      // 뒤따르는 진행 저장 step 이벤트의 회차 기록도 같은 값을 싣지만, 저장이 실패하면 오지 않는다 —
      // 점검 이벤트의 값으로 바로 채운다. 목록을 보내지 않는 옛 워커는 빈 목록·null
      excludedPapers: (event.excluded_papers ?? []).map(toExcludedPaperView),
      flagged: event.flagged ?? null,
      adoptedPapers: (event.adopted_papers ?? []).map(toAdoptedPaperView),
    };
```

⑨ `roundsFromQueries`(trail·queries 로 만든 옛 회차). old:

```ts
    excluded: null,
    excludedPapers: [],
    flagged: null,
  }));
}
```

new:

```ts
    excluded: null,
    excludedPapers: [],
    flagged: null,
    adoptedPapers: [],
  }));
}
```

⑩ `toExcludedPaperView` 아래에 `toAdoptedPaperView`(06b 근거 장부가 다시 쓰므로 export). old:

```ts
    personalAuthor: p.personal_author ?? null,
    pubDate: p.pub_date ?? null,
  };
}

function toRoundView(r: SearchRoundResult): RoundView {
```

new:

```ts
    personalAuthor: p.personal_author ?? null,
    pubDate: p.pub_date ?? null,
  };
}

// 회차 끝 채택 근거 — 점검 이벤트와 진행 저장본의 회차 기록이 같은 모양으로 싣는다. 서지는 그 회차에
// 새로 채택된 논문에만 있다(앞 회차에서 채택된 논문은 cnts_id·rank 뿐)
export function toAdoptedPaperView(p: AdoptedPaper): AdoptedPaperView {
  return {
    cntsId: p.cnts_id,
    rank: p.rank,
    title: p.title?.trim() || null,
    personalAuthor: p.personal_author ?? null,
    pubDate: p.pub_date ?? null,
    isNew: p.new === true,
  };
}

function toRoundView(r: SearchRoundResult): RoundView {
```

⑪ `toRoundView`(진행 저장본 회차)·`blankRound`(검색 이벤트로 새로 연 회차). old:

```ts
    excludedPapers: (r.excluded_papers ?? []).map(toExcludedPaperView),
    flagged: r.flagged ?? null,
  };
}

function blankRound(round: number): RoundView {
  return {
    round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null,
  };
}
```

new:

```ts
    excludedPapers: (r.excluded_papers ?? []).map(toExcludedPaperView),
    flagged: r.flagged ?? null,
    adoptedPapers: (r.adopted_papers ?? []).map(toAdoptedPaperView),
  };
}

function blankRound(round: number): RoundView {
  return {
    round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [],
  };
}
```

- [ ] **Step 5: 429 code 를 가른다 (`frontend/utils/researchErrors.ts`)**

old:

```ts
export function researchErrorMessage(err: unknown, fallback: string): string {
  const status = httpStatus(err);
  if (status === 429 || status === 503) return "요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요";
```

new:

```ts
// 같은 브라우저의 다른 딥리서치가 진행 중이라 승인·재시도가 막혔다(api/research.py _to_run_queue 의 429
// detail {code: "browser_active", message, job_id}). 서버가 문구를 비워 보내도 같은 안내를 쓴다
const BROWSER_ACTIVE_MESSAGE = "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요";

interface LimitDetail {
  code?: unknown;
  message?: unknown;
  job_id?: unknown;
}

// 429 detail 이 객체({code, message, job_id?})면 돌려준다. 문자열 detail(06a 전 서버)·배열은 null
function limitDetail(err: unknown): LimitDetail | null {
  if (httpStatus(err) !== 429) return null;
  const data = (err as FetchLikeError | null)?.data;
  const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : null;
  return detail && typeof detail === "object" && !Array.isArray(detail) ? (detail as LimitDetail) : null;
}

// 막은 연구가 있으면 그 id — 화면이 [진행 중인 연구 보기] 링크를 단다
export function activeResearchId(err: unknown): string | null {
  const limit = limitDetail(err);
  return limit?.code === "browser_active" && typeof limit.job_id === "string" && limit.job_id ? limit.job_id : null;
}

export function researchErrorMessage(err: unknown, fallback: string): string {
  const status = httpStatus(err);
  const limit = limitDetail(err);
  if (limit?.code === "browser_active") {
    return (typeof limit.message === "string" && limit.message.trim()) || BROWSER_ACTIVE_MESSAGE;
  }
  // 공유 큐 제한(shared_queue)·code 가 없는 429 와 503 은 지금 문구 그대로
  if (status === 429 || status === 503) return "요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요";
```

(함수의 나머지 404·409·422·네트워크 분기는 그대로다.)

- [ ] **Step 6: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx vitest run tests/unit/researchErrors.test.ts tests/unit/researchEvents.test.ts`
Expected: `Test Files 2 passed (2)` / `Tests 115 passed (115)` (researchErrors 14 + researchEvents 101)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 오류 3줄 — 타입을 붙여 만든 테스트 픽스처가 새 필수 필드를 모른다(다음 단계에서 고친다):
```
tests/unit/reportDocument.test.ts(428,3): error TS2741: Property 'adoptedPapers' is missing in type '…' but required in type 'RoundView'.
tests/unit/reportDocument.test.ts(451,3): error TS2741: Property 'queue' is missing in type '…' but required in type 'ResearchView'.
tests/unit/researchReport.test.ts(208,3): error TS2741: Property 'adoptedPapers' is missing in type '…' but required in type 'RoundView'.
```
(Task 4 없이 이 task 만 넣은 사본에서는 `reportDocument.test.ts` 의 두 줄이 `(416,3)`·`(439,3)` 이다 — Task 4 가 그 위에 12줄을 더한다.)

- [ ] **Step 7: 타입 픽스처를 맞춘다**

`frontend/tests/unit/reportDocument.test.ts` 의 `round()`. old:

```ts
    round: n, query, foundChunks: 3, newPapers: 1, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null,
  };
```

new:

```ts
    round: n, query, foundChunks: 3, newPapers: 1, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null, adoptedPapers: [],
  };
```

같은 파일의 `view()`. old:

```ts
    synth: { seq: 9, status: "running", total: 3, sections: [], headings: [], evidence: {}, retiredSeq: null },
    source: "rounds",
  };
```

new:

```ts
    synth: { seq: 9, status: "running", total: 3, sections: [], headings: [], evidence: {}, retiredSeq: null },
    source: "rounds",
    queue: null,
  };
```

`frontend/tests/unit/researchReport.test.ts` 의 `round()`. old:

```ts
    excluded: papers.length, excludedPapers: papers, flagged: 0,
  };
```

new:

```ts
    excluded: papers.length, excludedPapers: papers, flagged: 0, adoptedPapers: [],
  };
```

- [ ] **Step 8: 화면에 잇는다 (composable·ProgressPanel·연구 페이지)**

① `frontend/composables/useResearch.ts` — import 두 곳. old:

```ts
  applyApproval,
  applyResearchEvent,
  initialResearchView,
```

new:

```ts
  applyApproval,
  applyQueue,
  applyResearchEvent,
  initialResearchView,
```

old:

```ts
import { httpStatus, researchErrorMessage } from "~/utils/researchErrors";
```

new:

```ts
import { activeResearchId, httpStatus, researchErrorMessage } from "~/utils/researchErrors";
```

ref. old:

```ts
  const actionError = ref("");
  const busy = ref(false);
```

new:

```ts
  const actionError = ref("");
  // 같은 브라우저의 다른 딥리서치에 막힌 승인·재시도(429 browser_active)면 그 연구 id — 화면이 링크를 단다.
  // actionError 와 함께 바뀐다(setActionError 가 비우고, 막힌 동작의 catch 만 채운다)
  const activeJobId = ref<string | null>(null);
  const busy = ref(false);
```

`setActionError`(load·act 시작·409 맞춤이 모두 이것을 부른다 — 새 시도·성공 때 비워진다). old:

```ts
  function setActionError(message: string): void {
    actionError.value = message;
    syncError = "";
  }
```

new:

```ts
  function setActionError(message: string): void {
    actionError.value = message;
    activeJobId.value = null;
    syncError = "";
  }
```

`refresh()` 실패(백그라운드 재동기화가 actionError 를 다른 문구로 덮는다). old:

```ts
      const message = researchErrorMessage(e, "최신 상태를 불러오지 못했습니다");
      actionError.value = message;
      syncError = message;
```

new:

```ts
      const message = researchErrorMessage(e, "최신 상태를 불러오지 못했습니다");
      actionError.value = message;
      activeJobId.value = null;
      syncError = message;
```

`act` 의 catch. old:

```ts
      } else {
        setActionError(researchErrorMessage(e, fallback));
      }
      return false;
```

new:

```ts
      } else {
        setActionError(researchErrorMessage(e, fallback));
        activeJobId.value = activeResearchId(e);
      }
      return false;
```

승인·재시도 응답의 순번(첫 하트비트를 기다리지 않게). old:

```ts
        // 스트림이 응답보다 먼저 running 을 알렸으면 status 는 그대로 둔다(applyApproval)
        view.value = applyApproval(view.value, res.status, res.plan);
        connect();
```

new:

```ts
        // 스트림이 응답보다 먼저 running 을 알렸으면 status 는 그대로 둔다(applyApproval) — 그때는 응답의
        // 순번도 싣지 않는다(applyQueue). 대기 중이면 첫 하트비트(15초)를 기다리지 않고 순번을 보인다
        view.value = applyQueue(applyApproval(view.value, res.status, res.plan), res.queue);
        connect();
```

old:

```ts
        view.value = applyResearchEvent(view.value, { kind: "status", status: res.status, stage: res.stage });
        connect();
```

new:

```ts
        view.value = applyQueue(
          applyResearchEvent(view.value, { kind: "status", status: res.status, stage: res.stage }),
          res.queue,
        );
        connect();
```

반환. old:

```ts
    view, loading, notFound, loadError, actionError, busy, connected, syncFailed, syncing,
    load, refresh, resync, connect, disconnect, approve, retry, cancel,
```

new:

```ts
    view, loading, notFound, loadError, actionError, activeJobId, busy, connected, syncFailed, syncing,
    load, refresh, resync, connect, disconnect, approve, retry, cancel,
```

② `frontend/components/research/ProgressPanel.vue` — queued 문구 뒤 덧붙임. 기존 문구는 그대로다. old:

```vue
    <p v-else-if="phase === 'queued'" class="rs-muted">대기열에 들어갔습니다. 앞선 연구가 끝나면 시작합니다.</p>
```

new:

```vue
    <p v-else-if="phase === 'queued'" class="rs-muted">대기열에 들어갔습니다. 앞선 연구가 끝나면 시작합니다.<span v-if="queueLine">{{ " " + queueLine }}</span></p>
```

props. old:

```ts
// revealExcluded: 새 창으로 연 제외 논문에서 돌아와 맞출 논문 — 그 논문을 뺀 회차를 펼쳐 둬야 자리가 생긴다
const props = defineProps<{ view: ResearchView; phase: ResearchPhase; revealExcluded?: string | null }>();
```

new:

```ts
// revealExcluded: 새 창으로 연 제외 논문에서 돌아와 맞출 논문 — 그 논문을 뺀 회차를 펼쳐 둬야 자리가 생긴다
// queueLine: 대기열 문구 뒤에 덧붙이는 순번(queueLine()) — 순번을 모르면 지금 문구만 둔다. 템플릿의 " " + 는
// 일부러다 — <span> 첫머리의 공백 글자는 Vue 컴파일러(whitespace: condense)가 지운다
const props = defineProps<{
  view: ResearchView;
  phase: ResearchPhase;
  revealExcluded?: string | null;
  queueLine?: string | null;
}>();
```

③ `frontend/pages/research/[id].vue` — rs-alert 아래 링크. old:

```vue
        <p v-if="actionError || pageError" class="rs-alert" role="alert">{{ actionError || pageError }}</p>
```

new:

```vue
        <p v-if="actionError || pageError" class="rs-alert" role="alert">{{ actionError || pageError }}</p>
        <p v-if="activeJobId" class="rs-muted">
          <NuxtLink :to="`/research/${activeJobId}`">진행 중인 연구 보기</NuxtLink>
        </p>
```

(링크로 옮겨 가면 주소의 id 가 바뀌어 `load()` → `setActionError("")` 가 `activeJobId` 를 비운다.)

대기 카드. old:

```vue
              <div v-else-if="phase === 'queued'" class="rs-card rs-card--wait">
                <p>앞선 연구가 끝나면 시작합니다</p>
              </div>
```

new:

```vue
              <div v-else-if="phase === 'queued'" class="rs-card rs-card--wait">
                <p>앞선 연구가 끝나면 시작합니다</p>
                <p v-if="queueText" class="rs-muted">{{ queueText }}</p>
              </div>
```

진행 패널. old:

```vue
            <ProgressPanel :view="view" :phase="phase" :reveal-excluded="revealExcluded" />
```

new:

```vue
            <ProgressPanel :view="view" :phase="phase" :reveal-excluded="revealExcluded" :queue-line="queueText" />
```

script import. old:

```ts
import { researchPhase } from "~/utils/researchEvents";
```

new:

```ts
import { queueLine, researchPhase } from "~/utils/researchEvents";
```

composable 받기. old:

```ts
const { view, notFound, loadError, actionError, busy, syncFailed, syncing, load, resync, approve, retry, cancel } =
  useResearchJob(() => String(route.params.id ?? ""));
```

new:

```ts
const {
  view, notFound, loadError, actionError, activeJobId, busy, syncFailed, syncing, load, resync, approve, retry, cancel,
} = useResearchJob(() => String(route.params.id ?? ""));
```

`queueText`. old:

```ts
const phase = computed(() => (view.value ? researchPhase(view.value) : null));
```

new:

```ts
const phase = computed(() => (view.value ? researchPhase(view.value) : null));
// 대기 카드·진행 패널의 대기열 문구 뒤에 덧붙이는 순번 — 대기 중이 아니거나 순번을 모르면 null
const queueText = computed(() => (view.value ? queueLine(view.value.queue) : null));
```

- [ ] **Step 9: 전체를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx nuxi typecheck 2>&1 | grep -c "error TS"`
Expected: `0` (`[Vue] Resolve plugin path failed: vue-router/volar/sfc-route-blocks …` 경고는 npx 가 받은 vue-tsc 의 것으로 기준선에도 나온다 — 오류가 아니다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx vitest run tests/unit/researchErrors.test.ts tests/unit/researchEvents.test.ts`
Expected: `Tests 115 passed (115)`

`RoundView`·`ResearchView` 를 함께 쓰는 기존 테스트:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx vitest run tests/unit/reportDocument.test.ts tests/unit/researchReport.test.ts tests/unit/researchDraft.test.ts`
Expected: `Test Files 3 passed (3)` / `Tests 79 passed (79)` (reportDocument 27 + researchReport 29 + researchDraft 23 — reportDocument 의 27 은 124c481 의 26 + Task 4 의 1. Task 4 없이 이 task 만 넣은 사본에서는 78)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx vitest run`
Expected: `Test Files 28 passed (28)` / `Tests 510 passed (510)` (Task 4 적용 뒤 기준선 496 + 새 테스트 14 — researchErrors 4 + researchEvents 10. Task 4 없이 이 task 만 넣은 사본에서는 509)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

덧붙임 공백 확인(1회성, 저장소에 남기지 않는다) — 컴파일된 템플릿이 공백을 실어 보내는지:

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && node -e "const fs=require('fs');const {parse,compileTemplate}=require('./node_modules/@vue/compiler-sfc');const d=parse(fs.readFileSync('components/research/ProgressPanel.vue','utf8')).descriptor;console.log(compileTemplate({source:d.template.content,filename:'p.vue',id:'x'}).code.split('\n').filter(l=>l.includes('queueLine')).join('\n'))"`
Expected: 출력에 `_toDisplayString(" " + _ctx.queueLine)` 가 있다.

- [ ] **Step 10: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a add frontend/types/research.ts frontend/utils/researchEvents.ts frontend/utils/researchErrors.ts frontend/composables/useResearch.ts frontend/components/research/ProgressPanel.vue "frontend/pages/research/[id].vue" frontend/tests/unit/researchErrors.test.ts frontend/tests/unit/researchEvents.test.ts frontend/tests/unit/reportDocument.test.ts frontend/tests/unit/researchReport.test.ts
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a commit -m "[Feat] round06a 프론트 — 딥리서치 대기 순번을 지금 queued 문구 뒤에 덧붙이고(GET·snapshot 의 queue, 스트림 queue 이벤트, 승인·재시도 응답의 queue — 대기를 벗어나거나 잡이 끝나면 비우고 응답보다 스트림이 먼저 대기를 벗어났으면 싣지 않는다, 문구는 queueLine: '바로 다음 차례입니다'·'앞에 N건 · 약 M분'), 승인·재시도가 같은 브라우저의 다른 연구에 막힌 429 browser_active 는 서버 문구와 [진행 중인 연구 보기] 링크로 안내한다(shared_queue·문자열 429·503 은 지금 문구 그대로). 회차 끝 채택 근거(critique 이벤트·rounds 의 adopted_papers)를 RoundView.adoptedPapers 로 받아 06b 근거 장부가 rounds 만으로 다시 그리게 한다. 새 필드는 모두 선택이라 옛 서버에서는 화면이 지금과 같다"
```

---


### Task 14: 백업 스크립트 — 연구 테이블 일일 덤프

spec D14·§6-5 백업 줄, 계약 §14. 지금 `infra/backup/pg_backup.sh` 는 매일 `library_catalog` 만, 일요일에 전체 DB 를 받는다. 연구 어시스턴트가 쌓는 사용자 연구(`research_*` 7개 새 테이블과 기존 `research_jobs`·`research_steps`)와 `history_items` 는 다시 만들 수 없으므로 매일 따로 받는다(`daily/research_<ts>.dump`). `paper_facets` 는 다시 만들 수 있는 캐시라 주간 전체 덤프에 맡긴다(`research_*` 패턴에 걸리지 않는다).

- **`dump` 인자:** 지금은 `dump "-t library_catalog" <파일>` 처럼 pg_dump 인자를 한 문자열로 받아 따옴표 없이 펼친다(`$1`). 여기에 `-t 'research_*'` 를 넣으면 셸이 현재 폴더에서 glob 을 풀 수 있다. 계약대로 첫 인자를 받을 파일로, 나머지를 `"$@"` 로 받게 바꾸고 패턴은 따옴표째 넘긴다 — spec §6-5 의 `set -f … set +f` 는 필요 없어진다(prune 의 glob 은 그대로 동작한다).
- **실패 모으기:** 지금은 `set -eu` 라 첫 덤프가 실패하면 그 자리에서 끝나 뒤 덤프·정리가 돌지 않는다. 덤프마다 `|| rc=1` 로 모으고 정리까지 돈 뒤 `exit "$rc"` 로 끝낸다.
- **정리:** `research_*.dump` 도 `KEEP_DAILY`(기본 14)개만 남긴다. research 덤프는 정리보다 앞에서 받는다.
- **복원 예시(머리 주석):** 연구 테이블은 외래 키로 묶여 있다(`research_steps`·`research_works` → `research_jobs`, 새 테이블 다섯 → `research_works`). 운영 DB 에 `pg_restore --clean -t research_works` 처럼 한 테이블만 되돌리면 그 테이블을 가리키는 다른 연구 테이블 때문에 `DROP TABLE` 이 막힌다. 그래서 예시는 연구 덤프를 통째로 되돌리는 줄과, 한 테이블(`-t research_works`)만 빈 DB 에 풀어 꺼내 보는 줄로 쓴다(spec 의 "`-t research_works` 한 줄"을 실제로 도는 형태로). 통째로 되돌리는 줄은 `research_*`·`history_items` 를 DROP 하고 다시 만들므로, 그 앞에 이 테이블들에 쓰는 컨테이너(`nl-lib-fastapi`·`nl-lib-celery-research`·`nl-lib-celery-research-plan`·`nl-lib-celery-control` — 회수기가 `research_jobs`·`research_steps`·`research_generations` 에 쓴다)를 먼저 멈추고 끝나면 다시 올리라고 적는다.
- **호스트 설치는 이 task 에서 하지 않는다** — Task 17 Step 10(root 셸에서 `install -m 755 … /usr/local/bin/nl-lib-pg-backup` 뒤 1회 실행 — 이 서버는 sudo 가 아니라 `su - root` 다)이다. 이 task 의 어떤 단계도 운영 DB 에 닿지 않는다(가짜 `docker` 로만 돈다).

**Files:**
- Modify: `infra/backup/pg_backup.sh` (124c481 기준 머리 주석 8-11·21-24행, `dump` 40-52행, 덤프 호출 54-59행, 정리 호출 74-75행)
- 1회성 확인 스크립트 `C:/Users/LANDSOFT/AppData/Local/Temp/round06a_check_pg_backup.sh` — worktree **밖**에 만들고(커밋하지 않는다) Step 4 끝에서 지운다

- [ ] **Step 1: 실패하는 확인 스크립트를 쓴다**

셸 스크립트 테스트 틀이 저장소에 없으므로 1회성 확인 스크립트로 TDD 를 대신한다. 가짜 `docker`(인자를 기록하고 더미 바이트를 냄)와 가짜 `date`(요일만 바꿈)를 PATH 앞에 두고 임시 폴더에 백업을 받아 파일 이름·pg_dump 인자·종료 코드·정리를 본다. 백업이 도는 폴더에 `research_glob_trap` 파일을 두어, `research_*` 가 따옴표 없이 넘어가면 셸 glob 으로 그 이름이 되는 것을 잡는다(따옴표를 지운 사본으로 돌리면 "2번째 인자" 한 줄이 FAIL 로 바뀌는 것을 확인했다).

아래 내용을 worktree 밖의 `C:/Users/LANDSOFT/AppData/Local/Temp/round06a_check_pg_backup.sh` 에 저장한다(Write 도구로 쓴다 — 저장소에 넣지 않는다):

```sh
#!/bin/sh
# round06a_check_pg_backup.sh — infra/backup/pg_backup.sh 1회성 확인(round06a Task 14). 저장소에 커밋하지 않는다.
# 가짜 docker·date 를 PATH 앞에 두고 임시 디렉터리에 백업을 받아 파일 이름·pg_dump 인자·종료 코드·정리를 본다.
# 쓰는 법: sh round06a_check_pg_backup.sh <확인할 pg_backup.sh 의 경로>
set -u
SCRIPT="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
REAL_DATE="$(command -v date)"
work="$(mktemp -d)"
mkdir -p "$work/bin" "$work/cwd"
fails=0

check() {  # check <설명> <조건 명령...>
  desc="$1"
  shift
  if "$@"; then
    echo "PASS $desc"
  else
    echo "FAIL $desc"
    fails=$((fails + 1))
  fi
}

count() {  # count <디렉터리> <이름 패턴> — 그 디렉터리 바로 아래 파일 수
  find "$1" -maxdepth 1 -type f -name "$2" 2>/dev/null | wc -l | tr -d ' '
}

call() {  # call <로그> <n> — n 번째 docker 호출의 인자를 공백 하나로 이어 한 줄로
  awk -v n="$2" 'BEGIN { c = 1 } $0 == "--" { c++; next } c == n { printf "%s ", $0 }' "$1" | sed 's/ $//'
}

cat > "$work/bin/docker" <<'FAKE'
#!/bin/sh
# 가짜 docker — 인자를 한 줄에 하나씩 FAKE_LOG 에 남기고(호출 사이는 '--') 더미 바이트를 낸다.
# FAKE_FAIL 과 같은 인자가 있으면 그 호출만 실패한다
for a in "$@"; do printf '%s\n' "$a"; done >> "$FAKE_LOG"
echo "--" >> "$FAKE_LOG"
for a in "$@"; do
  if [ "$a" = "${FAKE_FAIL:-}" ]; then exit 1; fi
done
printf 'PGDMP-dummy'
FAKE
cat > "$work/bin/date" <<FAKE
#!/bin/sh
# 가짜 date — 요일(+%u)만 FAKE_DOW 로 바꾸고 나머지는 진짜 date 에 넘긴다
if [ "\${1:-}" = "+%u" ] && [ -n "\${FAKE_DOW:-}" ]; then echo "\$FAKE_DOW"; exit 0; fi
exec "$REAL_DATE" "\$@"
FAKE
chmod +x "$work/bin/docker" "$work/bin/date"
# 셸 glob 함정 — 백업이 도는 폴더에 둔다. 'research_*' 가 따옴표 없이 풀리면 이 파일 이름으로 바뀐다
touch "$work/cwd/research_glob_trap"

run() {  # run <이름> [VAR=값...] — 백업 폴더 $work/<이름>, docker 인자 $work/<이름>.log, 종료 코드 $work/<이름>.rc
  name="$1"
  shift
  (cd "$work/cwd" && env PATH="$work/bin:$PATH" FAKE_LOG="$work/$name.log" NL_LIB_BACKUP_DIR="$work/$name" "$@" \
    sh "$SCRIPT") > "$work/$name.out" 2>&1
  echo "$?" > "$work/$name.rc"
  touch "$work/$name.log"
}

BASE="exec nl-lib-postgres pg_dump -U admin -d nl_lib --format=custom"

check "sh -n 문법" sh -n "$SCRIPT"

# 1) 평일 — 일일 덤프 둘, 전체 덤프 없음
run weekday FAKE_DOW=5
check "평일: 종료 코드 0" [ "$(cat "$work/weekday.rc")" = 0 ]
check "평일: docker 호출 2번" [ "$(grep -c '^--$' "$work/weekday.log")" = 2 ]
check "평일: 1번째 인자 = library_catalog" [ "$(call "$work/weekday.log" 1)" = "$BASE -t library_catalog" ]
check "평일: 2번째 인자 = 'research_*'·history_items (glob 안 풀림)" \
  [ "$(call "$work/weekday.log" 2)" = "$BASE -t research_* -t history_items" ]
check "평일: daily/library_catalog_<ts>.dump 1개" [ "$(count "$work/weekday/daily" 'library_catalog_*.dump')" = 1 ]
check "평일: daily/research_<ts>.dump 1개" [ "$(count "$work/weekday/daily" 'research_*.dump')" = 1 ]
check "평일: weekly 비어 있음" [ "$(count "$work/weekday/weekly" '*')" = 0 ]
check "평일: .part 가 남지 않음" [ -z "$(find "$work/weekday" -name '*.part')" ]

# 2) 일요일 — 전체 덤프가 세 번째로 더 돈다(테이블 인자 없음)
run sunday FAKE_DOW=7
check "일요일: 종료 코드 0" [ "$(cat "$work/sunday.rc")" = 0 ]
check "일요일: docker 호출 3번" [ "$(grep -c '^--$' "$work/sunday.log")" = 3 ]
check "일요일: 3번째 인자 = 테이블 지정 없음" [ "$(call "$work/sunday.log" 3)" = "$BASE" ]
check "일요일: weekly/nl_lib_full_<ts>.dump 1개" [ "$(count "$work/sunday/weekly" 'nl_lib_full_*.dump')" = 1 ]

# 3) 앞 덤프 실패 — 뒤 덤프·정리는 돌고 끝에서 1 로 끝난다
run failing FAKE_DOW=5 FAKE_FAIL=library_catalog
check "앞 덤프 실패: 종료 코드 1" [ "$(cat "$work/failing.rc")" = 1 ]
check "앞 덤프 실패: 그래도 research 덤프를 받는다" [ "$(count "$work/failing/daily" 'research_*.dump')" = 1 ]
check "앞 덤프 실패: 실패한 덤프는 파일·.part 없음" \
  [ "$(count "$work/failing/daily" 'library_catalog_*')" = 0 ]
check "앞 덤프 실패: FAIL 줄을 남긴다" grep -q "FAIL .*library_catalog_" "$work/failing.out"

# 4) 정리 — research_*.dump 도 KEEP_DAILY 개만 남긴다(오래된 것부터 지움)
mkdir -p "$work/prune/daily"
for d in 01 02 03; do
  touch -d "2026-01-$d 00:00:00" "$work/prune/daily/research_202601${d}T000000.dump"
  touch -d "2026-01-$d 00:00:00" "$work/prune/daily/library_catalog_202601${d}T000000.dump"
done
run prune FAKE_DOW=5 NL_LIB_KEEP_DAILY=2
check "정리: 종료 코드 0" [ "$(cat "$work/prune.rc")" = 0 ]
check "정리: research 덤프 2개만 남음" [ "$(count "$work/prune/daily" 'research_*.dump')" = 2 ]
check "정리: 가장 새 옛 research 덤프는 남음" [ -f "$work/prune/daily/research_20260103T000000.dump" ]
check "정리: library_catalog 덤프 2개만 남음" [ "$(count "$work/prune/daily" 'library_catalog_*.dump')" = 2 ]

echo "fails=$fails"
rm -rf "$work"
if [ "$fails" = 0 ]; then echo "ALL OK"; fi
exit "$fails"
```

- [ ] **Step 2: 실패를 확인한다**

Run(Git Bash): `sh C:/Users/LANDSOFT/AppData/Local/Temp/round06a_check_pg_backup.sh C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/infra/backup/pg_backup.sh; echo "exit=$?"`
Expected: PASS 14줄·FAIL 7줄, 끝에 `fails=7` 과 `exit=7`. FAIL 7줄:

```
FAIL 평일: docker 호출 2번
FAIL 평일: 2번째 인자 = 'research_*'·history_items (glob 안 풀림)
FAIL 평일: daily/research_<ts>.dump 1개
FAIL 일요일: docker 호출 3번
FAIL 일요일: 3번째 인자 = 테이블 지정 없음
FAIL 앞 덤프 실패: 그래도 research 덤프를 받는다
FAIL 정리: research 덤프 2개만 남음
```

("앞 덤프 실패: 종료 코드 1" 은 지금도 PASS 다 — `set -e` 가 첫 실패에서 바로 1 로 끝내기 때문이고, 그래서 research 덤프 줄이 FAIL 이다.)

- [ ] **Step 3: 구현한다 (`infra/backup/pg_backup.sh`)**

① 머리 주석의 단계 설명. old:

```sh
#   daily  — library_catalog 만. 작아서 매일 돌려도 부담이 없고, 실제로 날아간 것이 이 테이블이다.
#   weekly — 전체 DB. book_sections(원문 100만행 이상)까지 포함해 무겁지만,
#            원문은 재추출에 OCR 비용이 들어 반드시 지켜야 한다.
```

new:

```sh
#   daily  — library_catalog 만. 작아서 매일 돌려도 부담이 없고, 실제로 날아간 것이 이 테이블이다.
#            연구 테이블(research_*)과 history_items 도 따로 받는다(research_<ts>.dump) — 사용자가
#            쌓은 연구·기록이라 다시 만들 수 없다. paper_facets(다시 만들 수 있는 캐시)는 weekly 에 맡긴다.
#   weekly — 전체 DB. book_sections(원문 100만행 이상)까지 포함해 무겁지만,
#            원문은 재추출에 OCR 비용이 들어 반드시 지켜야 한다.
# 한 덤프가 실패해도 나머지 덤프·정리는 돌고, 끝에서 1 로 끝난다(cron 로그에 FAIL 줄이 남는다).
```

② 복원 예시. old:

```sh
#   docker exec -i nl-lib-postgres pg_restore -U admin -d nl_lib --clean --if-exists \
#     -t library_catalog < /data/nl-lib/backup/daily/library_catalog_<타임스탬프>.dump
set -eu
```

new:

```sh
#   docker exec -i nl-lib-postgres pg_restore -U admin -d nl_lib --clean --if-exists \
#     -t library_catalog < /data/nl-lib/backup/daily/library_catalog_<타임스탬프>.dump
# 연구 덤프는 테이블끼리 외래 키로 묶여 있어 통째로 되돌린다 — 한 테이블만 -t 로 --clean 하면 그 테이블을
# 가리키는 다른 연구 테이블 때문에 DROP 이 막힌다. 되돌리는 동안 이 테이블들에 쓰는 컨테이너를 먼저 멈추고
# 끝나면 다시 올린다(nl-lib-fastapi·nl-lib-celery-research·nl-lib-celery-research-plan·nl-lib-celery-control — 돌고 있으면 잠금에
# 걸리거나 도중에 쓴 행을 잃는다):
#   docker exec -i nl-lib-postgres pg_restore -U admin -d nl_lib --clean --if-exists \
#     < /data/nl-lib/backup/daily/research_<타임스탬프>.dump
# 한 테이블만 꺼내 볼 때는 운영 DB 를 건드리지 않고 빈 DB 에 푼다:
#   docker exec nl-lib-postgres createdb -U admin nl_lib_restore_check
#   docker exec -i nl-lib-postgres pg_restore -U admin -d nl_lib_restore_check \
#     -t research_works < /data/nl-lib/backup/daily/research_<타임스탬프>.dump
set -eu
```

③ `dump` 가 받을 파일을 첫 인자로, pg_dump 인자를 `"$@"` 로 받는다. old:

```sh
# 임시 파일에 받고 성공했을 때만 제자리로 옮긴다 — 중단된 덤프가 백업인 척하면 안 된다.
dump() {
  target="$2"
  tmp="$target.part"
  if docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB" --format=custom $1 > "$tmp"; then
```

new:

```sh
# 임시 파일에 받고 성공했을 때만 제자리로 옮긴다 — 중단된 덤프가 백업인 척하면 안 된다.
# 첫 인자는 받을 파일, 나머지는 pg_dump 에 그대로 넘긴다("$@" — 'research_*' 같은 패턴이 셸 glob 으로
# 풀리지 않고 pg_dump 의 -t 패턴으로 간다).
dump() {
  target="$1"
  shift
  tmp="$target.part"
  if docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB" --format=custom "$@" > "$tmp"; then
```

(`dump` 의 나머지 — mv·OK/FAIL 로그·`return 1` — 는 그대로다.)

④ 덤프 호출. old:

```sh
dump "-t library_catalog" "$BACKUP_DIR/daily/library_catalog_$ts.dump"

# 일요일에만 전체 덤프
if [ "$(date +%u)" = "7" ]; then
  dump "" "$BACKUP_DIR/weekly/nl_lib_full_$ts.dump"
fi
```

new:

```sh
# 앞 덤프가 실패해도 뒤 덤프·정리는 돈다 — 실패는 rc 에 모았다가 끝에서 알린다
rc=0
dump "$BACKUP_DIR/daily/library_catalog_$ts.dump" -t library_catalog || rc=1
# 패턴은 따옴표째 넘긴다 — pg_dump 가 research_jobs·research_steps·research_works 등과 그 시퀀스를 고른다
dump "$BACKUP_DIR/daily/research_$ts.dump" -t 'research_*' -t history_items || rc=1

# 일요일에만 전체 덤프
if [ "$(date +%u)" = "7" ]; then
  dump "$BACKUP_DIR/weekly/nl_lib_full_$ts.dump" || rc=1
fi
```

⑤ 정리와 종료 코드(파일 끝). old:

```sh
prune "$BACKUP_DIR/daily" "library_catalog_*.dump" "$KEEP_DAILY"
prune "$BACKUP_DIR/weekly" "nl_lib_full_*.dump" "$KEEP_WEEKLY"
```

new:

```sh
prune "$BACKUP_DIR/daily" "library_catalog_*.dump" "$KEEP_DAILY"
prune "$BACKUP_DIR/daily" "research_*.dump" "$KEEP_DAILY"
prune "$BACKUP_DIR/weekly" "nl_lib_full_*.dump" "$KEEP_WEEKLY"

exit "$rc"
```

(`prune` 함수와 그 위 주석 — "패턴을 따옴표 없이 둬야 셸이 glob 을 확장한다" — 는 그대로다. `set -f` 를 쓰지 않으므로 prune 의 glob 이 계속 동작한다.)

- [ ] **Step 4: 통과를 확인한다**

Run: `sh -n C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/infra/backup/pg_backup.sh && echo "sh -n ok"`
Expected: `sh -n ok`

Run(Git Bash): `sh C:/Users/LANDSOFT/AppData/Local/Temp/round06a_check_pg_backup.sh C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/infra/backup/pg_backup.sh; echo "exit=$?"`
Expected: PASS 21줄, FAIL 0줄, 끝에 `fails=0`·`ALL OK`·`exit=0`.

관련 기존 테스트: 이 스크립트를 부르는 pytest·vitest 는 없다(셸 스크립트는 호스트 cron 만 부른다). 확인 스크립트는 저장소에 넣지 않으므로 status 에는 `pg_backup.sh` 한 줄만 보여야 한다:

Run: `git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a status --short`
Expected: ` M infra/backup/pg_backup.sh` 한 줄

확인을 마쳤으면 1회성 확인 스크립트를 지운다:

Run(Git Bash): `rm -f C:/Users/LANDSOFT/AppData/Local/Temp/round06a_check_pg_backup.sh && test ! -e C:/Users/LANDSOFT/AppData/Local/Temp/round06a_check_pg_backup.sh && echo "check script removed"`
Expected: `check script removed`

- [ ] **Step 5: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a add infra/backup/pg_backup.sh
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a commit -m "[Chore] round06a 일일 백업에 연구 테이블을 더한다 — research_*·history_items 를 따로 받는다(daily/research_<ts>.dump, KEEP_DAILY 로 정리). dump 가 받을 파일을 첫 인자로, pg_dump 인자를 \"\$@\" 로 받아 'research_*' 패턴이 셸 glob 으로 풀리지 않게 하고, 한 덤프가 실패해도 나머지 덤프·정리를 마저 돈 뒤 1 로 끝낸다. 머리 주석에 연구 덤프 복원 예시(통째로·빈 DB 에 -t research_works)를 더한다. paper_facets 는 주간 전체 덤프에 맡긴다"
```


### Task 15: critic 두 갈래 판정 도구 (`scripts/research_eval/`)

**왜:** critic 새 기준(`critic_scope=1`)은 꺼진 채 배포하고, 배포 당일 운영에서 고정 질문 5개를 두 갈래(0·1)로 돌려 사람이 단 라벨로 합격선(절마다 무관 1편 이하·과잉 제외 10% 이하)을 넘으면 켠다(spec D11·§8). 그 판정을 그날 안에 세는 도구다. 리허설(10/23~25)에서도 다시 돌므로 `research/` 가 아니라 `scripts/` 에 둔다(CLAUDE.md §1). 예시 연구 지정(`research_works.is_example`)도 API 가 아니라 이 폴더의 운영 스크립트로만 한다(spec §6-1).

**Files:**
- Create: `scripts/research_eval/questions.json`
- Create: `scripts/research_eval/run_pair.py`
- Create: `scripts/research_eval/score.py`
- Create: `scripts/research_eval/make_labels.py`
- Create: `scripts/research_eval/mark_example.py`
- Create: `scripts/research_eval/README.md`
- Test: `app/tests/test_research_eval.py`

**알아 둘 것:**
- `run_pair.py`·`make_labels.py`·`score.py` 는 HTTP(httpx — 앱 이미지에 있다)만 쓰고 DB 를 읽지도 쓰지도 않는다. `mark_example.py` 만 DB 에 쓰고, `db.postgres.SyncSessionLocal` 을 함수 안에서 import 한다 — 테스트는 `test_build_canary_manifest.py` 처럼 `db.postgres` 를 대역으로 바꾼다. HTTP 는 `httpx.MockTransport` 로 바꾼다(실제 API·DB 에 닿지 않는다).
- 테스트는 `SCRIPTS_DIR = parents[2] / "scripts" / "research_eval"` 를 `sys.path` 에 넣는 기존 패턴(`test_build_canary_manifest.py`·`test_select_near_empty_items.py`)이다. `make_labels.py`·`score.py` 는 같은 폴더의 `run_pair.get_job` 을 import 한다 — 서버에서 `python /app/data/research_eval/score.py` 로 돌리면 스크립트 폴더가 `sys.path[0]` 이라 그대로 된다.
- 두 갈래 잡은 `x-session-id` 를 보내지 않는다 — `created_by` 가 NULL 이라 Task 6 의 브라우저당 실행 제한에 걸리지 않는다. 운영 `RESEARCH_QUEUE` 는 `q_research` 라 공유 큐 429 도 없다. 실행 워커(`celery-research`)가 동시 1 이라 잡 10개가 차례로 돈다.
- 갈래 1 은 승인 본문 `plan` 에 갈래 0 의 계획을 넘긴다(`ResearchApprove.plan` — 같은 기본 파라미터라 `_validated_plan` 의 `max_subquestions` 상한도 같다). 계획 프롬프트·승인 API 는 바꾸지 않는다(D16).
- 잡을 만들 때 `params` 에 `critic_scope` 를 싣는다 — Task 2 가 `DEFAULT_PARAMS` 에 키를 넣기 전이면 `merge_params` 가 422 로 거부한다. 기본값을 1 로 바꾼 뒤(Task 17)에도 갈래 0 은 명시한 0 으로 돈다.
- 콘솔 출력은 cp949 로 인코딩할 수 있는 글자만 쓴다(긴 줄표 `—` 금지 — Windows 콘솔·`--help` 가 `UnicodeEncodeError` 로 죽는다). 라벨 CSV 는 엑셀이 한글을 깨지 않게 BOM(`utf-8-sig`)으로 쓰고 읽는다.
- `*.csv` 는 `.gitignore` 4행 대상이다. 라벨 파일은 판정 뒤 Task 17 에서 `git add -f` 로 올린다.

- [ ] **Step 1: 고정 질문 4개 사용자 확인**

spec §8·§11 — 5개 중 첫 질문은 운영 잡 `2a56f8b6` 의 「컴퓨팅 자원에 대한 연구가 궁금해」로 고정이고, 나머지 4개는 06a 시작 때 정해 사용자 확인을 받는다. 지금 딥리서치 코퍼스는 2013년까지라(적재가 옛 논문부터 돈다) 2013년 이전 KCI 적재분에 근거가 많을 분야로 후보를 고른다. 사용자에게 아래 표를 보이고 확인을 받는다. 바꾸라고 하면 Step 4 의 `questions.json` 에 그 질문을 넣는다(`key` 는 영문 소문자·숫자·밑줄 — 라벨 파일 이름이 된다). 확인을 받기 전에는 Step 12(커밋)를 하지 않는다.

| key | 질문 후보 | 고른 까닭 |
|---|---|---|
| `library` | 공공도서관 서비스 품질 평가 연구가 궁금해 | 문헌정보학. 2000년대 KCI 에 서비스 품질 측정 논문이 많고, 운영 워밍업 질문(`bulk_ingest_runbook.md` §8)과 같은 주제라 결과를 견주기 쉽다 |
| `elderly` | 노인의 우울과 사회적 지지에 관한 연구가 궁금해 | 사회복지·간호. 2013년 이전에도 설문 기반 실증 연구가 두텁다 |
| `nursing` | 간호사의 직무 스트레스와 이직 의도에 관한 연구가 궁금해 | 간호·경영. 측면(원인·결과·중재)이 나뉘어 하위질문에서 벗어난 관련 논문이 생기기 쉽다 — 과잉 제외를 볼 수 있다 |
| `sensor` | 무선 센서 네트워크 라우팅 프로토콜 연구가 궁금해 | 공학. 2005~2012년 논문이 많고, '네트워크'가 사회 연결망과 같은 단어 다른 뜻이라 무관 판정(off_topic)을 시험한다 |

- [ ] **Step 2: 실패하는 테스트 작성**

`app/tests/test_research_eval.py` (새 파일, 전체):

```python
"""scripts/research_eval/ — critic 기준 스위치 두 갈래 판정 도구(질문 목록·두 갈래 실행·라벨 파일·채점·예시 지정).

스크립트는 HTTP(httpx)만 쓰거나(run_pair·make_labels·score) DB 세션을 함수 안에서 import 한다(mark_example).
HTTP 는 httpx.MockTransport 로, DB 는 db.postgres 대역으로 바꿔 운영에 닿지 않는다.
"""
import csv
import json
import re
import sys
import types
from pathlib import Path

import httpx
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "research_eval"
sys.path.insert(0, str(SCRIPTS_DIR))

API = "http://api.test/api"
WORK = "3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e"


def _report(sections, excluded_by_subq, evidence=None):
    """보고서(synthesizer.assemble_report) 가운데 도구가 읽는 키만."""
    return {
        "question": "컴퓨팅 자원에 대한 연구가 궁금해",
        "sections": [
            {"heading": f"하위질문 {i + 1}", "papers": [{"cnts_id": c} for c in ids]}
            for i, ids in enumerate(sections)
        ],
        "evidence": evidence or {},
        "trail": [
            {"subquestion": f"하위질문 {i + 1}", "excluded_papers": [
                {"cnts_id": c, "title": f"제외 {c}", "personal_author": "홍길동", "pub_date": "2010"}
                for c in ids
            ]}
            for i, ids in enumerate(excluded_by_subq)
        ],
    }


def _write_labels(path: Path, rows: list[tuple[str, str]]) -> None:
    body = "".join(f"{cnts},제목 {cnts},저자,{label}\n" for cnts, label in rows)
    path.write_text("cnts_id,title,authors,label\n" + body, encoding="utf-8-sig")


# ── questions.json ──────────────────────────────────────────────────────


def test_questions_file_lists_five_fixed_questions():
    items = json.loads((SCRIPTS_DIR / "questions.json").read_text(encoding="utf-8"))
    keys = [q["key"] for q in items]
    assert len(items) == 5 and len(set(keys)) == 5
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", k) for k in keys)    # 라벨 파일 이름이 된다
    assert all(set(q) == {"key", "question"} and 2 <= len(q["question"]) <= 500 for q in items)
    # 운영 잡 2a56f8b6 의 질문 — 옛 잡과 견주지 않고 같은 질문을 두 갈래로 다시 돌린다(spec §8)
    assert items[0] == {"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"}


# ── score.py ────────────────────────────────────────────────────────────


def test_section_irrelevant_counts_irrelevant_labels_per_section():
    from score import section_irrelevant

    report = _report([["A", "B", "C"], ["D", "E"], []], [])
    labels = {"A": "무관", "B": "관련", "C": "무관", "D": "관련"}     # E 는 라벨 없음 — 세지 않는다
    assert section_irrelevant(report, labels) == [2, 0, 0]


def test_over_exclusion_is_relevant_share_of_distinct_labeled_exclusions():
    from score import over_exclusion

    # X 는 두 하위질문이 함께 뺐다 — 서로 다른 논문으로 한 번만 센다. Z 는 라벨이 없어 분모에서 빠진다
    report = _report([], [["X", "Y"], ["X", "Z"], ["W"]])
    labels = {"X": "관련", "Y": "무관", "W": "무관"}
    assert over_exclusion(report, labels) == pytest.approx(1 / 3)


def test_over_exclusion_is_none_without_labeled_exclusions():
    from score import over_exclusion

    assert over_exclusion(_report([["A"]], []), {"A": "관련"}) is None    # 제외 0편
    assert over_exclusion(_report([], [["Z"]]), {}) is None                # 제외는 있으나 라벨 없음


@pytest.mark.parametrize("irrelevant, over, ok", [
    ([1, 1, 0], 0.10, True),     # 경계값은 합격 — '이하'
    ([0], None, True),           # 라벨 단 제외 논문이 없으면 ② 는 통과
    ([2, 0], 0.0, False),        # 한 절에 무관 2편
    ([0, 1], 0.11, False),       # 과잉 제외 11%
    ([], 0.0, True),
])
def test_passes_uses_the_d11_thresholds(irrelevant, over, ok):
    from score import passes

    assert passes({"section_irrelevant": irrelevant, "over_exclusion": over}) is ok


def test_load_labels_reads_excel_csv_and_rejects_unknown_labels(tmp_path):
    from score import load_labels

    path = tmp_path / "computing.csv"
    path.write_text("cnts_id,title,authors,label\nA,가,홍,관련\nB,나,김, 무관 \nC,다,이,\n",
                    encoding="utf-8-sig")
    assert load_labels(path) == {"A": "관련", "B": "무관"}     # 빈 칸은 라벨 없음

    path.write_text("cnts_id,title,authors,label\nA,가,홍,관련있음\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="2행"):
        load_labels(path)


def test_score_prints_both_arms_on_a_cp949_console(tmp_path, capsys):
    from score import main

    reports = {"job-1": _report([["A", "B"]], [["X"]]), "job-2": _report([["A"]], [])}

    def handler(request: httpx.Request) -> httpx.Response:
        jid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"job_id": jid, "status": "completed", "report": reports[jid]})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"}}), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    _write_labels(labels / "computing.csv", [("A", "관련"), ("B", "무관"), ("X", "관련")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--labels-dir", str(labels)], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    out.encode("cp949")
    # 갈래 0: 절 무관 1(B) 은 통과지만 뺀 X 가 '관련' — 과잉 제외 100% 로 불합격. 갈래 1: 무관 0·제외 없음
    assert "갈래 0  절별 무관 1  과잉 제외 100.0%" in out and "불합격" in out
    assert "합격 질문: 갈래 0 0/1 · 갈래 1 1/1" in out


def test_score_counts_every_question_and_holds_arms_with_blank_labels(tmp_path, capsys):
    """D11 은 다섯 질문 모두 합격이어야 한다 — 채점하지 못한 질문도 분모에 넣고, 라벨 칸이 빈 갈래는 합격으로 세지 않는다."""
    from score import main

    reports = {"job-1": _report([["A", "B"], ["C"]], []), "job-2": _report([["A", "D"]], [])}

    def handler(request: httpx.Request) -> httpx.Response:
        jid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"job_id": jid, "status": "completed", "report": reports[jid]})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"},
                                 "library": {"0": "job-3", "1": "job-4"}}), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    # library 는 라벨 파일이 없다. computing 의 D 는 라벨 칸이 비었다
    _write_labels(labels / "computing.csv", [("A", "무관"), ("B", "무관"), ("C", "관련"), ("D", "")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--labels-dir", str(labels)], client=client)

    assert rc == 0
    out = capsys.readouterr().out
    out.encode("cp949")
    # 갈래 0 은 한 절에 무관 2편 — 라벨을 더 달아도 줄지 않으니 불합격. 갈래 1 은 D 의 라벨이 비어 판정 보류
    assert "갈래 0  절별 무관 2,0" in out and "라벨 없음 0편  -> 불합격" in out
    assert "갈래 1  절별 무관 1" in out and "라벨 없음 1편  -> 판정 보류" in out
    assert "합격 질문: 갈래 0 0/2 · 갈래 1 0/2" in out
    assert "채점하지 못한 질문 1개: library" in out
    assert "라벨 칸이 빈 논문이 갈래 합계 1편" in out


# ── make_labels.py ──────────────────────────────────────────────────────


def test_label_rows_take_section_papers_then_exclusions_once_each():
    from make_labels import paper_rows

    evidence = {
        "E1": {"cnts_id": "A", "meta": {"title": "그리드 자원 관리", "personal_author": "김철수; 이영희"}},
        "E2": {"cnts_id": "B", "meta": {"title": "클라우드 스케줄링", "personal_author": None}},
    }
    report = _report([["A", "B"], ["A"]], [["X"], ["X", "B"]], evidence)
    assert paper_rows(report) == [
        {"cnts_id": "A", "title": "그리드 자원 관리", "authors": "김철수; 이영희", "label": ""},
        # B 는 절 서지에 저자가 비어 있고 다른 하위질문의 제외 기록에 있다 — 빈 칸만 채운다
        {"cnts_id": "B", "title": "클라우드 스케줄링", "authors": "홍길동", "label": ""},
        {"cnts_id": "X", "title": "제외 X", "authors": "홍길동", "label": ""},
    ]


def test_write_labels_keeps_existing_labels_and_appends_new_papers(tmp_path):
    from make_labels import write_labels
    from score import load_labels

    path = tmp_path / "computing.csv"
    _write_labels(path, [("A", "관련")])
    arm0 = _report([["A"]], [["X"]])
    arm1 = _report([["A", "C"]], [])

    assert write_labels(path, [arm0, arm1]) == (3, 2)        # (전체, 새로 붙인 줄)

    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["cnts_id"] for r in rows] == ["A", "X", "C"]
    assert rows[0]["title"] == "제목 A"                      # 이미 있는 줄은 손대지 않는다
    assert load_labels(path) == {"A": "관련"}
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")     # 엑셀이 한글을 깨지 않게 BOM


def test_make_labels_main_writes_one_file_per_question(tmp_path, capsys):
    from make_labels import main

    reports = {"job-1": _report([["A"]], [["X"]]), "job-2": _report([["B"]], [])}

    def handler(request: httpx.Request) -> httpx.Response:
        jid = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, json={"job_id": jid, "status": "completed", "report": reports[jid]})

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"}}), encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--pairs", str(pairs), "--out-dir", str(tmp_path / "labels")], client=client)

    assert rc == 0
    with (tmp_path / "labels" / "computing.csv").open(encoding="utf-8-sig", newline="") as f:
        assert [r["cnts_id"] for r in csv.DictReader(f)] == ["A", "X", "B"]
    capsys.readouterr().out.encode("cp949")


# ── run_pair.py ─────────────────────────────────────────────────────────


def _fake_research_api(fail: str | None = None):
    """POST /research·GET /research/{id}·POST approve 를 흉내 낸다.

    조회할 때마다 한 걸음씩 나아간다 — created → planning → awaiting_approval, approved → running → completed.
    fail 로 준 잡은 planning 다음에 failed 가 된다.
    """
    state = {"jobs": {}, "requests": []}
    steps = {"created": "planning", "planning": "awaiting_approval", "approved": "running", "running": "completed"}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        path = request.url.path
        if request.method == "POST" and path == "/api/research":
            body = json.loads(request.content)
            jid = f"job-{len(state['jobs']) + 1}"
            state["jobs"][jid] = {"job_id": jid, "question": body["question"], "params": body["params"],
                                  "status": "created", "plan": None, "last_error": None, "approved_with": "없음"}
            return httpx.Response(200, json={"job_id": jid, "status": "created"})
        m = re.fullmatch(r"/api/research/([^/]+)(/approve)?", path)
        job = state["jobs"][m.group(1)]
        if m.group(2):
            job["approved_with"] = json.loads(request.content) if request.content else None
            job["status"] = "approved"
            return httpx.Response(200, json={"job_id": job["job_id"], "status": "approved"})
        if job["status"] == "planning" and job["job_id"] == fail:
            job["status"], job["last_error"] = "failed", "계획 LLM 실패"
        elif job["status"] in steps:
            job["status"] = steps[job["status"]]
            if job["status"] == "awaiting_approval":
                job["plan"] = [f"{job['job_id']} 계획 1", f"{job['job_id']} 계획 2"]
        return httpx.Response(200, json={k: job[k] for k in ("job_id", "question", "params", "status",
                                                             "plan", "last_error")})

    return state, handler


def test_run_question_approves_arm1_with_arm0_plan_and_no_browser_id():
    from run_pair import run_question

    state, handler = _fake_research_api()
    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        pair = run_question(client, API, "컴퓨팅 자원에 대한 연구가 궁금해",
                            poll=5.0, timeout=60.0, sleep=sleeps.append)

    assert pair == {"0": "job-1", "1": "job-2"}
    jobs = state["jobs"]
    assert [j["params"] for j in jobs.values()] == [{"critic_scope": 0}, {"critic_scope": 1}]
    # 갈래 0 은 제 계획 그대로(본문 없음), 갈래 1 은 갈래 0 의 계획 — 같은 하위질문으로 critic 만 다르게 돈다
    assert jobs["job-1"]["approved_with"] is None
    assert jobs["job-2"]["approved_with"] == {"plan": ["job-1 계획 1", "job-1 계획 2"]}
    assert [j["status"] for j in jobs.values()] == ["completed", "completed"]
    # 브라우저 ID 를 보내지 않는다 — created_by 가 NULL 이라 브라우저당 실행 제한에 걸리지 않는다
    assert all("x-session-id" not in r.headers for r in state["requests"])
    assert sleeps and set(sleeps) == {5.0}


def test_run_pair_main_reports_a_failed_question_and_keeps_the_others(tmp_path, capsys):
    from run_pair import main

    questions = tmp_path / "questions.json"
    questions.write_text(json.dumps([{"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"},
                                     {"key": "library", "question": "공공도서관 서비스 품질 평가 연구가 궁금해"}],
                                    ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "pairs.json"
    out.write_text(json.dumps({"old": {"0": "a", "1": "b"}}), encoding="utf-8")
    state, handler = _fake_research_api(fail="job-1")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rc = main(["--api", API, "--out", str(out), "--questions", str(questions), "--poll", "0"],
                  client=client)

    assert rc == 1
    # computing 의 갈래 0(job-1)이 계획에서 실패 — 그 질문은 기록하지 않고 다음 질문을 돌린다. 먼저 있던 기록은 남긴다
    assert json.loads(out.read_text(encoding="utf-8")) == {"old": {"0": "a", "1": "b"},
                                                           "library": {"0": "job-2", "1": "job-3"}}
    text = capsys.readouterr().out
    text.encode("cp949")
    assert "--only computing" in text


# ── mark_example.py ─────────────────────────────────────────────────────


class _FakeSession:
    """db.postgres.SyncSessionLocal() 대역 — 실행한 문장을 기록하고 is_example 지금 값을 돌려준다."""

    def __init__(self, current):
        self.current = current          # None 이면 그 연구 행이 없다
        self.executed: list[tuple[str, dict]] = []
        self.committed = False
        self.closed = False

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        return types.SimpleNamespace(scalar_one_or_none=lambda: self.current)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True

    def updates(self) -> list[tuple[str, dict]]:
        return [(s, p) for s, p in self.executed if s.lstrip().upper().startswith("UPDATE")]


@pytest.fixture
def fake_db(monkeypatch):
    """스크립트가 함수 안에서 import 하는 db.postgres 를 대역으로 바꾼다 — 진짜 DB 에 닿지 않는다."""
    def _make(current):
        session = _FakeSession(current)
        db_pkg = types.ModuleType("db")
        db_pg = types.ModuleType("db.postgres")
        db_pg.SyncSessionLocal = lambda: session
        db_pkg.postgres = db_pg
        monkeypatch.setitem(sys.modules, "db", db_pkg)
        monkeypatch.setitem(sys.modules, "db.postgres", db_pg)
        return session
    return _make


def test_mark_example_without_yes_only_reads(fake_db, capsys):
    from mark_example import main

    session = fake_db(False)
    assert main(["--work", WORK, "--on"]) == 0
    assert session.updates() == [] and not session.committed and session.closed
    out = capsys.readouterr().out
    assert "--yes" in out and "False -> True" in out
    out.encode("cp949")


def test_mark_example_with_yes_updates_only_is_example(fake_db):
    from mark_example import main

    session = fake_db(False)
    assert main(["--work", WORK.upper(), "--on", "--yes"]) == 0
    (sql, params), = session.updates()
    assert "SET is_example = :flag" in sql and "WHERE id = CAST(:id AS uuid)" in sql
    assert params == {"id": WORK, "flag": True}             # 대문자로 줘도 표준형 id 로 찾는다
    assert session.committed and session.closed


def test_mark_example_leaves_unknown_or_unchanged_work_alone(fake_db):
    from mark_example import main

    missing = fake_db(None)
    assert main(["--work", WORK, "--off", "--yes"]) == 1
    assert missing.updates() == [] and not missing.committed

    already = fake_db(True)
    assert main(["--work", WORK, "--on", "--yes"]) == 0
    assert already.updates() == [] and not already.committed
```

- [ ] **Step 3: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`

Expected: `20 failed`. 이유:
- `test_questions_file_lists_five_fixed_questions` — `FileNotFoundError: … scripts\research_eval\questions.json`
- `score` 를 import 하는 11개(`section_irrelevant`·`over_exclusion` 둘·`passes` 매개변수 5개·`load_labels`·`score` CLI 둘) — `ModuleNotFoundError: No module named 'score'`
- `make_labels` 3개 — `ModuleNotFoundError: No module named 'make_labels'`
- `run_pair` 2개 — `ModuleNotFoundError: No module named 'run_pair'`
- `mark_example` 3개 — `ModuleNotFoundError: No module named 'mark_example'`

- [ ] **Step 4: `scripts/research_eval/questions.json`**

Step 1 에서 사용자가 바꾼 질문이 있으면 그 줄을 바꿔 쓴다(첫 줄 `computing` 은 그대로).

```json
[
  {"key": "computing", "question": "컴퓨팅 자원에 대한 연구가 궁금해"},
  {"key": "library", "question": "공공도서관 서비스 품질 평가 연구가 궁금해"},
  {"key": "elderly", "question": "노인의 우울과 사회적 지지에 관한 연구가 궁금해"},
  {"key": "nursing", "question": "간호사의 직무 스트레스와 이직 의도에 관한 연구가 궁금해"},
  {"key": "sensor", "question": "무선 센서 네트워크 라우팅 프로토콜 연구가 궁금해"}
]
```

- [ ] **Step 5: `scripts/research_eval/run_pair.py`**

```python
r"""run_pair.py — critic 기준 스위치 두 갈래 실행 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

고정 질문(questions.json)마다 딥리서치 잡 두 개를 만든다.
  갈래 0 — params {"critic_scope": 0}(지금 기준). 계획이 나오면 그 계획 그대로 승인한다.
  갈래 1 — params {"critic_scope": 1}(원 질문 기준). 같은 질문으로 만들고 승인 본문 plan 에 갈래 0 의
           계획을 넘긴다 — 같은 하위질문으로 돌려 두 갈래의 차이가 critic 하나뿐이게 한다.
두 잡 모두 x-session-id 를 보내지 않는다(created_by NULL — 브라우저당 실행 제한 밖). 실행 워커가 하나라
잡은 줄을 서서 차례로 돈다. 둘 다 completed 가 될 때까지 기다리고 {질문키: {"0": 잡 id, "1": 잡 id}} 를
--out JSON 에 질문마다 덧쓴다. 이미 있는 다른 질문의 기록은 남긴다 — 실패한 질문만 --only 로 다시 돌린다.

실행 (서버 — scripts/ 는 앱 이미지에 없어 데이터 바인드 마운트로 넣는다. 함정 4번):
  docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
    --api http://localhost:8000/api --out /app/data/research_eval/pairs.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions.json"
TERMINAL = ("completed", "failed", "canceled")


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def create_job(client: httpx.Client, api: str, question: str, critic_scope: int) -> str:
    res = client.post(f"{api}/research",
                      json={"question": question, "params": {"critic_scope": critic_scope}})
    res.raise_for_status()
    return res.json()["job_id"]


def get_job(client: httpx.Client, api: str, job_id: str) -> dict:
    res = client.get(f"{api}/research/{job_id}")
    res.raise_for_status()
    return res.json()


def approve(client: httpx.Client, api: str, job_id: str, plan: list[str] | None = None) -> None:
    """plan 이 None 이면 본문 없이 — 잡이 세운 계획 그대로 승인한다."""
    res = client.post(f"{api}/research/{job_id}/approve", json=None if plan is None else {"plan": plan})
    res.raise_for_status()


def wait_for(client: httpx.Client, api: str, job_id: str, status: str, *, poll: float, timeout: float,
             sleep=time.sleep, clock=time.monotonic) -> dict:
    """잡이 status 가 될 때까지 poll 초마다 조회한다. 다른 종료 상태로 끝나거나 timeout 을 넘기면 예외."""
    deadline = clock() + timeout
    while True:
        job = get_job(client, api, job_id)
        if job["status"] == status:
            return job
        if job["status"] in TERMINAL:
            raise RuntimeError(f"{job_id} 가 {job['status']} 로 끝났다: {job.get('last_error')}")
        if clock() >= deadline:
            raise TimeoutError(f"{job_id} 가 {timeout:.0f}초 안에 {status} 가 되지 않았다(지금 {job['status']})")
        sleep(poll)


def run_question(client: httpx.Client, api: str, question: str, *, poll: float, timeout: float,
                 sleep=time.sleep, clock=time.monotonic) -> dict[str, str]:
    """한 질문의 두 갈래를 만들어 승인하고 둘 다 completed 가 될 때까지 기다린다."""
    wait = {"poll": poll, "timeout": timeout, "sleep": sleep, "clock": clock}
    arm0 = create_job(client, api, question, 0)
    plan = wait_for(client, api, arm0, "awaiting_approval", **wait)["plan"]
    approve(client, api, arm0)
    arm1 = create_job(client, api, question, 1)
    wait_for(client, api, arm1, "awaiting_approval", **wait)
    approve(client, api, arm1, plan)
    for job_id in (arm0, arm1):
        wait_for(client, api, job_id, "completed", **wait)
    return {"0": arm0, "1": arm1}


def load_pairs(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_pairs(path: Path, pairs: dict) -> None:
    path.write_text(json.dumps(pairs, ensure_ascii=False, indent=1), encoding="utf-8")


def _reason(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code} {e.request.url} {e.response.text[:300]}"
    return str(e)


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="critic 기준 스위치 두 갈래 실행 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--out", required=True, type=Path, help="{질문키: {\"0\": 잡 id, \"1\": 잡 id}} 를 덧쓸 JSON")
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--only", default="", help="이 질문키만(쉼표로 이음). 실패한 질문을 다시 돌릴 때")
    ap.add_argument("--poll", type=float, default=5.0, help="상태 조회 간격(초)")
    ap.add_argument("--timeout", type=float, default=3600.0, help="잡 하나가 한 상태에 이르기까지 기다릴 초")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    questions = load_questions(args.questions)
    only = {k for k in args.only.split(",") if k}
    unknown = only - {q["key"] for q in questions}
    if unknown:
        print(f"모르는 질문키: {', '.join(sorted(unknown))}")
        return 2
    if only:
        questions = [q for q in questions if q["key"] in only]

    own = client is None
    client = client or httpx.Client(timeout=30.0)
    failed: list[str] = []
    try:
        for q in questions:
            print(f"[{q['key']}] {q['question']}", flush=True)
            try:
                pair = run_question(client, api, q["question"], poll=args.poll, timeout=args.timeout)
            except (httpx.HTTPError, RuntimeError, TimeoutError) as e:
                failed.append(q["key"])
                print(f"  실패: {_reason(e)}", flush=True)
                continue
            pairs = load_pairs(args.out)
            pairs[q["key"]] = pair
            save_pairs(args.out, pairs)
            print(f"  완료: 갈래 0 {pair['0']} · 갈래 1 {pair['1']}", flush=True)
    finally:
        if own:
            client.close()
    if failed:
        print(f"실패한 질문 {len(failed)}개 - --only {','.join(failed)} 로 다시 돌린다")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: `scripts/research_eval/score.py`**

```python
r"""score.py — critic 두 갈래 채점 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

spec §8 의 합격선(D11)을 질문·갈래마다 센다.
  ① 절마다 무관 1편 이하 — 보고서 절(sections[].papers)에 실린 논문 중 라벨이 '무관' 인 수
  ② 과잉 제외 10% 이하 — 제외된 서로 다른 논문(trail[].excluded_papers) 중 라벨이 '관련' 인 비율.
     라벨 칸이 빈 논문은 분모에서 뺀다. 라벨 단 제외 논문이 없으면(제외 0편 포함) 비율은 없고 ② 는 통과다.
라벨 칸이 빈 논문 수(절 논문·제외 논문)를 함께 찍는다 — 0 이 아니면 그 갈래는 '판정 보류'(합격으로 세지 않는다)이고
라벨을 마저 단 뒤 다시 센다. 단 ① 을 이미 넘긴 갈래는 라벨을 더 달아도 줄지 않으므로 '불합격' 이다.
'합격 질문' 의 분모는 pairs 의 질문 수 전체다 — 라벨 파일이나 보고서가 없어 채점하지 못한 질문도 분모에 들고
따로 이름을 찍는다(D11 은 다섯 질문 모두 합격이어야 한다).
라벨 파일은 make_labels.py 가 만든 labels/<질문키>.csv 이고 label 칸은 '관련'·'무관' 만 받는다.

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

import httpx

from run_pair import get_job

HERE = Path(__file__).resolve().parent
RELEVANT, IRRELEVANT = "관련", "무관"
LABELS = (RELEVANT, IRRELEVANT)
MAX_IRRELEVANT_PER_SECTION = 1
MAX_OVER_EXCLUSION = 0.10


def load_labels(path: Path) -> dict[str, str]:
    """{cnts_id: '관련'|'무관'}. 빈 칸은 라벨 없음으로 빼고, 다른 값이 있으면 줄 번호와 함께 ValueError."""
    labels: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("label") or "").strip()
            if not label:
                continue
            if label not in LABELS:
                raise ValueError(f"{path.name} {reader.line_num}행: 알 수 없는 라벨 {label!r} - 관련·무관 중 하나")
            labels[row["cnts_id"].strip()] = label
    return labels


def _section_ids(report: dict) -> list[list[str]]:
    return [[p["cnts_id"] for p in sec.get("papers") or []] for sec in report.get("sections") or []]


def _excluded_ids(report: dict) -> list[str]:
    """제외된 서로 다른 논문 — 두 하위질문이 같은 논문을 뺐으면 한 번만."""
    ids = (p["cnts_id"] for t in report.get("trail") or [] for p in t.get("excluded_papers") or [])
    return list(dict.fromkeys(ids))


def section_irrelevant(report: dict, labels: dict[str, str]) -> list[int]:
    """절마다 '무관' 라벨 논문 수(보고서 절 순서)."""
    return [sum(labels.get(c) == IRRELEVANT for c in dict.fromkeys(ids)) for ids in _section_ids(report)]


def over_exclusion(report: dict, labels: dict[str, str]) -> float | None:
    """제외된 서로 다른 논문 중 '관련' 비율. 라벨 없는 논문은 분모에서 빼고, 라벨 단 제외 논문이 없으면 None."""
    labeled = [c for c in _excluded_ids(report) if c in labels]
    if not labeled:
        return None
    return sum(labels[c] == RELEVANT for c in labeled) / len(labeled)


def score_arm(report: dict, labels: dict[str, str]) -> dict:
    excluded = _excluded_ids(report)
    labeled = [c for c in excluded if c in labels]
    papers = {c for ids in _section_ids(report) for c in ids} | set(excluded)
    return {
        "section_irrelevant": section_irrelevant(report, labels),
        "over_exclusion": over_exclusion(report, labels),
        "excluded": len(excluded),
        "excluded_labeled": len(labeled),
        "excluded_relevant": sum(labels[c] == RELEVANT for c in labeled),
        "unlabeled": len(papers - set(labels)),
    }


def _sections_ok(arm: dict) -> bool:
    return all(n <= MAX_IRRELEVANT_PER_SECTION for n in arm["section_irrelevant"])


def passes(arm: dict) -> bool:
    """합격선(D11): 절마다 무관 1편 이하이고 과잉 제외 10% 이하(비율이 없으면 통과)."""
    over = arm["over_exclusion"]
    return _sections_ok(arm) and (over is None or over <= MAX_OVER_EXCLUSION)


def verdict(arm: dict) -> str:
    """'합격'·'불합격'·'판정 보류'. 라벨 칸이 빈 논문이 있으면 보류한다 — 단 ① 을 이미 넘긴 갈래는
    라벨을 더 달아도 절의 무관 수가 줄지 않으므로 불합격이다."""
    if not _sections_ok(arm):
        return "불합격"
    if arm["unlabeled"]:
        return "판정 보류"
    return "합격" if passes(arm) else "불합격"


def format_arm(arm_key: str, arm: dict) -> str:
    per_section = ",".join(str(n) for n in arm["section_irrelevant"]) or "-"
    if arm["over_exclusion"] is None:
        over = f"과잉 제외 - (라벨 단 제외 0편, 제외 {arm['excluded']}편)"
    else:
        over = (f"과잉 제외 {arm['over_exclusion'] * 100:.1f}% (관련 {arm['excluded_relevant']}"
                f"/라벨 {arm['excluded_labeled']}, 제외 {arm['excluded']}편)")
    return f"  갈래 {arm_key}  절별 무관 {per_section}  {over}  라벨 없음 {arm['unlabeled']}편  -> {verdict(arm)}"


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="critic 두 갈래 채점 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="run_pair.py 출력 JSON")
    ap.add_argument("--labels-dir", type=Path, default=HERE / "labels")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    passed = {"0": 0, "1": 0}
    skipped: list[str] = []
    unlabeled = 0
    try:
        for key, arms in pairs.items():
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
            reports = {arm: get_job(client, api, arms[arm]).get("report") for arm in ("0", "1")}
            if not all(reports.values()):
                print(f"[{key}] 보고서가 없는 갈래가 있다 - 건너뛴다")
                skipped.append(key)
                continue
            print(f"[{key}] {reports['0'].get('question', '')}")
            for arm in ("0", "1"):
                result = score_arm(reports[arm], labels)
                passed[arm] += verdict(result) == "합격"
                unlabeled += result["unlabeled"]
                print(format_arm(arm, result))
    finally:
        if own:
            client.close()
    total = len(pairs)
    print(f"합격 질문: 갈래 0 {passed['0']}/{total} · 갈래 1 {passed['1']}/{total}")
    if skipped:
        print(f"채점하지 못한 질문 {len(skipped)}개: {', '.join(skipped)} - 합격으로 세지 않았다")
    if unlabeled:
        print(f"라벨 칸이 빈 논문이 갈래 합계 {unlabeled}편 있다 - 그 갈래는 판정 보류, 다 단 뒤 다시 센다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: `scripts/research_eval/make_labels.py`**

```python
r"""make_labels.py — 두 갈래 잡의 라벨 파일 만들기 (HTTP 만, DB 를 읽지도 쓰지도 않는다)

질문마다 labels/<질문키>.csv(cnts_id,title,authors,label) 를 쓴다. 두 갈래 보고서의 절 논문
(report.sections[].papers — 서지는 report.evidence)과 제외 논문(report.trail[].excluded_papers)을 합쳐
한 논문은 한 줄만 둔다 — 라벨은 잡이 아니라 질문 단위다(spec §8). 파일이 이미 있으면 그 줄과 라벨을
그대로 두고 새 논문만 뒤에 붙인다 — 리허설에서 다시 돌려도 단 라벨을 잃지 않는다.

label 칸은 사람이 '관련'·'무관' 으로 채운다. 원 질문의 주제를 다루면 '관련'(하위질문에서 벗어나도),
같은 단어를 다른 뜻으로 쓴 논문을 포함해 원 질문과 무관하면 '무관'. 엑셀이 한글을 깨지 않게 BOM 을 붙인다.

실행 (서버):
  docker exec nl-lib-fastapi python /app/data/research_eval/make_labels.py \
    --api http://localhost:8000/api --pairs /app/data/research_eval/pairs.json \
    --out-dir /app/data/research_eval/labels
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import httpx

from run_pair import get_job

HERE = Path(__file__).resolve().parent
FIELDS = ["cnts_id", "title", "authors", "label"]


def _add(rows: dict[str, dict], cnts_id: str, title: str | None, authors: str | None) -> None:
    row = rows.setdefault(cnts_id, {"cnts_id": cnts_id, "title": "", "authors": "", "label": ""})
    row["title"] = row["title"] or (title or "")
    row["authors"] = row["authors"] or (authors or "")


def paper_rows(report: dict) -> list[dict]:
    """보고서 하나의 절 논문 → 제외 논문 순으로, 한 논문 한 줄(label 은 빈 칸)."""
    meta = {e["cnts_id"]: e.get("meta") or {} for e in (report.get("evidence") or {}).values()}
    rows: dict[str, dict] = {}
    for sec in report.get("sections") or []:
        for p in sec.get("papers") or []:
            m = meta.get(p["cnts_id"], {})
            _add(rows, p["cnts_id"], m.get("title"), m.get("personal_author"))
    for t in report.get("trail") or []:
        for p in t.get("excluded_papers") or []:
            _add(rows, p["cnts_id"], p.get("title"), p.get("personal_author"))
    return list(rows.values())


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{k: (r.get(k) or "") for k in FIELDS} for r in csv.DictReader(f)]


def merge_rows(existing: list[dict], fresh: list[dict]) -> list[dict]:
    """있던 줄은 그대로(라벨 포함), 새 논문만 뒤에 붙인다."""
    seen = {r["cnts_id"] for r in existing}
    out = list(existing)
    for r in fresh:
        if r["cnts_id"] not in seen:
            seen.add(r["cnts_id"])
            out.append(r)
    return out


def write_labels(path: Path, reports: list[dict]) -> tuple[int, int]:
    """라벨 파일을 쓰고 (전체 줄 수, 새로 붙인 줄 수) 를 돌려준다."""
    existing = read_rows(path)
    rows = merge_rows(existing, [row for report in reports for row in paper_rows(report)])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows), len(rows) - len(existing)


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="두 갈래 잡의 라벨 파일 만들기 (HTTP 만)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="run_pair.py 출력 JSON")
    ap.add_argument("--out-dir", type=Path, default=HERE / "labels")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        for key, arms in pairs.items():
            jobs = [get_job(client, api, arms[arm]) for arm in ("0", "1")]
            missing = [j["job_id"] for j in jobs if not j.get("report")]
            if missing:
                print(f"[{key}] 보고서가 없는 잡 {', '.join(missing)} - 건너뛴다")
                continue
            path = args.out_dir / f"{key}.csv"
            total, new = write_labels(path, [j["report"] for j in jobs])
            print(f"[{key}] {total}편(새 {new}) -> {path}")
    finally:
        if own:
            client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: `scripts/research_eval/mark_example.py`**

```python
r"""mark_example.py — 연구를 방문자용 예시 연구로 지정하거나 푼다 (research_works.is_example 만 바꾼다)

예시 연구는 미리 돌린 실제 기록이고 읽기 전용이다(쓰기 API 는 409 — spec §4 시연 정직성 규칙). API 로는
켜지 않고 이 스크립트로만 지정한다(spec §6-1). --yes 가 없으면 지금 값과 할 일만 찍고 아무것도 쓰지 않는다.

실행 (서버 — DB 에 쓴다. 먼저 --yes 없이 본다):
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/research_eval/mark_example.py --work <연구 id> --on
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/research_eval/mark_example.py --work <연구 id> --on --yes
연구 id 는 [이 연구 이어가기] 를 누른 딥리서치 잡 id 다.
"""
import argparse
import sys
import uuid

SELECT_SQL = "SELECT is_example FROM research_works WHERE id = CAST(:id AS uuid)"
UPDATE_SQL = ("UPDATE research_works SET is_example = :flag, updated_at = now() "
              "WHERE id = CAST(:id AS uuid)")


def _work_id(raw: str) -> str:
    return str(uuid.UUID(raw))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="예시 연구 지정·해제 (research_works.is_example)")
    ap.add_argument("--work", required=True, type=_work_id, help="연구 id(= 출발 딥리서치 잡 id)")
    flag = ap.add_mutually_exclusive_group(required=True)
    flag.add_argument("--on", action="store_true", help="예시 연구로 지정")
    flag.add_argument("--off", action="store_true", help="예시 연구 지정을 푼다")
    ap.add_argument("--yes", action="store_true", help="실제로 쓴다(없으면 할 일만 찍는다)")
    args = ap.parse_args(argv)
    target = bool(args.on)

    from sqlalchemy import text as sa_text

    from db.postgres import SyncSessionLocal

    db = SyncSessionLocal()
    try:
        current = db.execute(sa_text(SELECT_SQL), {"id": args.work}).scalar_one_or_none()
        if current is None:
            print(f"연구 {args.work} 가 없다 - [이 연구 이어가기] 를 누른 딥리서치 잡 id 인지 본다")
            return 1
        if current == target:
            print(f"연구 {args.work} 는 이미 is_example={current} - 바꿀 것이 없다")
            return 0
        print(f"할 일: 연구 {args.work} is_example {current} -> {target}")
        if not args.yes:
            print("쓰지 않았다 - 실제로 바꾸려면 --yes 를 붙여 다시 돌린다")
            return 0
        db.execute(sa_text(UPDATE_SQL), {"id": args.work, "flag": target})
        db.commit()
        print("바꿨다")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 9: `scripts/research_eval/README.md`**

````markdown
# critic 두 갈래 판정 도구 (research_eval)

딥리서치 critic 의 기준 스위치(잡 파라미터 `critic_scope` — 0 = 지금 기준, 1 = 원 질문 기준)를 켤지 정하는 도구다. 고정 질문 5개를 운영에서 두 갈래로 돌리고, 사람이 단 라벨로 합격선을 센다(spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` D11·§8). 06a 배포 당일과 리허설(10/23~25)에 다시 돈다. LLM 심판은 쓰지 않는다.

**합격선(질문·갈래마다):** ① 보고서 절(`sections[].papers`)마다 '무관' 라벨 1편 이하 ② 과잉 제외 10% 이하 — 제외된 서로 다른 논문(`trail[].excluded_papers`) 중 '관련' 라벨 비율(라벨 칸이 빈 논문은 분모에서 뺀다). 라벨 칸이 빈 논문이 남은 갈래는 '판정 보류'로 합격에 세지 않고(① 을 이미 넘겼으면 '불합격'), '합격 질문' 의 분모는 채점하지 못한 질문까지 넣은 질문 수 전체다. 갈래 1 이 다섯 질문 모두 합격하면 `DEFAULT_PARAMS["critic_scope"]` 기본값을 1 로 바꾸는 작은 커밋을 하고, 하나라도 미달이면 0 으로 둔 채 계획 프롬프트 수정 여부를 사용자에게 묻는다.

| 파일 | 하는 일 | DB |
|---|---|---|
| `questions.json` | 고정 질문 5개 `[{key, question}]` — `key` 가 라벨 파일 이름이 된다 | — |
| `run_pair.py` | 질문마다 갈래 0·1 잡을 만들고(갈래 1 은 갈래 0 의 계획으로 승인) 완료까지 기다려 `{key: {"0": 잡 id, "1": 잡 id}}` 를 쓴다 | 안 씀(HTTP) |
| `make_labels.py` | 두 갈래 보고서의 절 논문·제외 논문을 합쳐 `labels/<key>.csv`(`cnts_id,title,authors,label`)를 쓴다. 이미 단 라벨은 남긴다 | 안 씀(HTTP) |
| `score.py` | 라벨과 보고서를 맞대어 갈래마다 절별 무관 수·과잉 제외 비율·판정(합격·불합격·판정 보류)을 찍는다 | 안 씀(HTTP) |
| `mark_example.py` | 연구를 예시 연구로 지정·해제(`research_works.is_example`) — `--yes` 없으면 할 일만 찍는다 | 씀(`--yes` 일 때만) |
| `labels/<key>.csv` | 사람이 단 라벨(질문 단위 — 두 갈래에 함께 나온 논문은 한 줄). `*.csv` 는 `.gitignore` 대상이라 `git add -f` 로 올린다 | — |

## 흐름

1. **질문 확인.** `questions.json` 의 5개를 쓴다. 첫 질문(`computing`)은 운영 잡 `2a56f8b6` 의 질문이다. 질문을 바꾸면 라벨 파일도 새로 만든다.
2. **서버로 옮기기.** `scripts/` 는 앱 이미지에 없다(함정 4번). 이 폴더를 서버의 `/data/nl-lib/data/research_eval/` 로 옮긴다(scp 등 평소 쓰는 방법). 컨테이너 안에서는 `/app/data/research_eval/` 이다.
3. **두 갈래 실행.** 실행 워커가 하나라 잡 10개가 차례로 돈다(잡 하나 약 2분 — 25분 안팎). 끊기지 않게 tmux 같은 세션에서 돌린다.
   ```bash
   RUN=pairs_$(date +%Y%m%d)
   docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
     --api http://localhost:8000/api --out /app/data/research_eval/$RUN.json
   ```
   마지막 줄이 `실패한 질문 …` 이면 그 줄의 `--only …` 를 붙여 다시 돌린다(완료된 질문의 기록은 남는다). 4·6 은 같은 `RUN` 을 쓴다 — 셸을 새로 열었으면 `ls /data/nl-lib/data/research_eval/` 로 이름을 보고 `RUN` 을 다시 넣는다.
4. **라벨 파일 만들기.**
   ```bash
   docker exec nl-lib-fastapi python /app/data/research_eval/make_labels.py \
     --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json \
     --out-dir /app/data/research_eval/labels
   ```
5. **라벨 달기(기획자).** 서버의 `/data/nl-lib/data/research_eval/labels/<key>.csv` 의 `label` 칸에 `관련`·`무관` 만 쓴다. 기준은 **원 질문**이다 — 하위질문에서 벗어났어도 원 질문의 주제를 다루면 `관련`, 같은 단어를 다른 뜻으로 쓴 논문을 포함해 원 질문과 무관하면 `무관`. 엑셀로 열어도 된다(BOM 이 붙어 있다 — 저장할 때 'CSV UTF-8' 로).
6. **채점.**
   ```bash
   docker exec nl-lib-fastapi python /app/data/research_eval/score.py \
     --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json \
     --labels-dir /app/data/research_eval/labels
   ```
   `합격 질문: 갈래 0 a/5 · 갈래 1 b/5` 줄과 질문별 줄을 기록한다. `판정 보류`·`라벨 칸이 빈 논문이 …` 가 나오면 5 로 돌아가 마저 단다. `채점하지 못한 질문 …` 이 나오면 그 질문의 라벨 파일(4)이나 잡(3, `--only`)부터 다시 한다.
7. **기록.** 라벨 파일을 저장소의 `scripts/research_eval/labels/` 로 옮겨 `git add -f` 로 커밋하고(리허설 때 다시 쓴다), 실행 JSON 의 잡 id 와 채점 결과는 라운드 완료노트에 적는다.
8. **예시 연구 지정(리허설).** 미리 돌려 이어간 연구를 예시로 보이려면 먼저 `--yes` 없이 보고 지정한다.
   ```bash
   docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/research_eval/mark_example.py --work <연구 id> --on
   docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/research_eval/mark_example.py --work <연구 id> --on --yes
   ```

## 테스트

`app/tests/test_research_eval.py` — `cd app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`. HTTP 는 `httpx.MockTransport`, DB 는 `db.postgres` 대역이라 운영에 닿지 않는다.
````

- [ ] **Step 10: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`

Expected: `20 passed`

- [ ] **Step 11: 관련 스위트·CLI 확인**

같은 `sys.path` 패턴을 쓰는 스크립트 테스트가 그대로인지 보고, 네 스크립트의 `--help` 가 cp949 콘솔에서 죽지 않는지 본다(`PYTHONIOENCODING` 을 주지 않는다).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_build_canary_manifest.py tests/test_select_near_empty_items.py tests/test_rewrite_milvus_doc_type.py -q -p no:cacheprovider`

Expected: `45 passed, 1 warning` (17 + 12 + 16, 기준선과 같다)

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && for s in run_pair make_labels score mark_example; do python scripts/research_eval/$s.py --help > /dev/null && echo "$s help ok"; done`

Expected: `run_pair help ok`·`make_labels help ok`·`score help ok`·`mark_example help ok` 네 줄(`UnicodeEncodeError` 없음)

- [ ] **Step 12: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add scripts/research_eval/questions.json scripts/research_eval/run_pair.py scripts/research_eval/score.py scripts/research_eval/make_labels.py scripts/research_eval/mark_example.py scripts/research_eval/README.md app/tests/test_research_eval.py && git status --short && git commit -m "[Feat] round06a — critic 두 갈래 판정 도구(scripts/research_eval/): 고정 질문 5개(사용자 확인)를 갈래 0·1(critic_scope 0·1, 갈래 1 은 갈래 0 의 계획으로 승인 — 같은 하위질문)로 HTTP 만으로 돌리는 run_pair(x-session-id 없음 — 브라우저당 제한 밖, 실패한 질문만 --only 로 다시), 두 갈래의 절 논문·제외 논문을 질문 단위 라벨 CSV 로 모으는 make_labels(단 라벨 보존·BOM), 절마다 무관 1편 이하·과잉 제외 10% 이하(라벨 없는 논문은 분모에서 뺀다)를 세는 score(라벨 칸이 빈 갈래는 판정 보류, 합격 질문의 분모는 채점하지 못한 질문까지 넣은 전체), 예시 연구를 --yes 일 때만 지정하는 mark_example. 리허설에서도 다시 돈다"
```

---


### Task 16: Qwen 한국어 품질 표본 확인 (`research/round06-qwen-check/`, 1회성)

**왜:** 연구 어시스턴트는 핵심 개념·주제 카드를 Qwen(`qwen3-vl-8b`)으로 만든다(D10, Task 8 의 `WORK_MODEL_ROUTES`). 대회 전에 Qwen 의 한국어 출력이 쓸 만한지 사람이 본다(spec §8). 06a 에서 핵심 개념 프롬프트(Task 8 의 `research_concepts.yaml`)와 주제 카드 **초안** 프롬프트를 고정 질문의 갈래 0 잡에 돌려 Qwen·gemma 출력을 나란히 남긴다. 미달이면 그 작업을 gemma 로 돌린다(라우팅 상수 한 줄 — 06a 화면에는 이어가기 입구가 없어 06b 첫 task 로 넘긴다, Task 17 Step 15). 1회성이라 `research/` 에 스크립트와 산출물을 함께 둔다(CLAUDE.md §1). 운영 실행은 Task 17 Step 12 에서 한다.

**Files:**
- Create: `research/round06-qwen-check/smoke_check.py`
- Create: `research/round06-qwen-check/topic_card_draft.yaml`
- Create: `research/round06-qwen-check/check.py`
- Create: `research/round06-qwen-check/README.md`
- Create(운영 실행 산출물, Task 17 Step 15 에서 커밋): `research/round06-qwen-check/out/<질문키>.md`

**알아 둘 것:**
- Task 8 뒤에 한다. 핵심 개념 요청은 연구 어시스턴트가 실제로 보내는 것 그대로 만든다 — `services.research_work.concepts` 의 `concepts_input(job)` → `EXECUTOR.build(input)`(→ `(messages, params)`), 응답은 `EXECUTOR.parse`·`EXECUTOR.check` 로 읽는다. 호출 상한은 `services.research_work.generate.CALL_TIMEOUT`(300초)이다. `concepts_input` 은 ResearchJob 을 받으므로 `GET /api/research/{id}` 응답에서 `question`·`plan`·`report` 를 같은 이름의 속성으로 옮긴다(`SimpleNamespace`).
- 주제 카드 초안 프롬프트는 이 폴더의 `topic_card_draft.yaml` 이고 `services.prompts.PromptLibrary(HERE)` 로 읽는다(06b 가 정식 프롬프트로 옮긴다). 개수·분야 예시는 넣지 않는다(함정 15번) — 근거 3개 이상은 예시가 아니라 규칙으로 적고, JSON 형식의 `evidence` 자리도 하나만 둔다(자리를 셋 두면 그 개수를 베껴 형식 검사가 두 모델을 가르지 못한다, spec §5-2 카드 내용 검사).
- 씨앗은 보고서 절의 첫 향후 과제(`sections[].future[0].text`)에서 `[E#]` 표기를 걷은 것(`services.research.citations.strip_markers`)이다. 근거 없는 하위질문은 절이 되지 않아(`synthesizer` 의 `targets`) 절 순번과 `trail` 순번이 어긋난다 — 채택 수 [F1] 은 소제목(= `trail[].subquestion`)으로 찾는다.
- vLLM 은 `httpx` 로 직접 부른다(`app/scripts/eval_answer_quality.py` 의 `_chat` 방식, 재시도 없음). 본문은 `llm_client.chat_full` 의 openai 본문과 같은 `{"model", "messages", **params}` 이고 `chat_template_kwargs` 는 보내지 않는다(운영 생성과 같게). DB 를 읽지도 쓰지도 않는다.
- pytest 대상이 아니다(1회성). `research/round04a-synth-dryrun/smoke_dryrun.py` 처럼 가짜 API·가짜 vLLM 으로 끝까지 돌려 보는 `smoke_check.py` 를 먼저 쓰고(실패 확인) `check.py` 를 쓴다.

- [ ] **Step 1: 실패하는 연기 확인 작성**

`research/round06-qwen-check/smoke_check.py` (새 파일, 전체):

```python
"""smoke_check.py — check.py 를 가짜 API·가짜 vLLM 으로 한 번 돌려 본다 (네트워크·DB 없음, 1회성)

운영에서 돌리기 전에 개발 PC 에서 요청 만들기(핵심 개념은 연구 어시스턴트의 실제 요청 그대로)·응답 읽기·
마크다운 쓰기가 끝까지 도는지만 본다. 품질은 운영 실행 결과(out/)를 사람이 본다.
사용법(저장소 루트에서): python research/round06-qwen-check/smoke_check.py  → 마지막 줄 'smoke OK'
"""
import json
import sys
import tempfile
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check  # noqa: E402

JOB = {
    "job_id": "job-1", "question": "컴퓨팅 자원에 대한 연구가 궁금해", "status": "completed",
    "plan": ["그리드 컴퓨팅의 자원 관리 기법", "분산 컴퓨팅 표준화 동향", "클라우드 자원 스케줄링",
             "고성능 컴퓨팅 활용 분야"],
    "report": {
        "question": "컴퓨팅 자원에 대한 연구가 궁금해",
        "range": {"from": "1998", "to": "2013", "n_papers": 125000},
        "sections": [
            {"heading": "그리드 컴퓨팅의 자원 관리 기법",
             "papers": [{"cnts_id": c} for c in ("A", "B", "C", "D")],
             "future": [{"text": "그리드 자원의 동적 배분을 실증할 필요가 있다 [E2]", "evidence": ["E2"]}]},
            {"heading": "클라우드 자원 스케줄링",
             "papers": [{"cnts_id": c} for c in ("E", "A", "D")],
             "future": [{"text": "가상화 환경의 스케줄링 비용을 비교해야 한다 [E5][E1]", "evidence": ["E5", "E1"]}]},
            # 향후 과제는 있지만 절 논문이 3편 미만 — 근거 3개 이상 규칙을 지킬 수 없어 카드를 만들지 않는다
            {"heading": "고성능 컴퓨팅 활용 분야", "papers": [{"cnts_id": "C"}],
             "future": [{"text": "고성능 계산 수요를 분야별로 조사해야 한다 [E3]", "evidence": ["E3"]}]},
        ],
        "evidence": {
            "E1": {"cnts_id": "A", "meta": {"title": "그리드 컴퓨팅 자원 관리", "pub_date": "2009-05"}},
            "E2": {"cnts_id": "B", "meta": {"title": "동적 자원 배분 기법", "pub_date": "2011"}},
            "E3": {"cnts_id": "C", "meta": {"title": "고성능 계산 환경 구축", "pub_date": "2004"}},
            "E4": {"cnts_id": "D", "meta": {"title": "분산 작업 스케줄러", "pub_date": None}},
            "E5": {"cnts_id": "E", "meta": {"title": "가상 머신 배치 최적화", "pub_date": "2013-02"}},
        },
        # 근거가 없어 절이 되지 않은 하위질문이 가운데 끼어 있다 — 채택 수는 소제목으로 찾아야 한다
        "trail": [{"subquestion": "그리드 컴퓨팅의 자원 관리 기법", "evidence_count": 15},
                  {"subquestion": "분산 컴퓨팅 표준화 동향", "evidence_count": 0},
                  {"subquestion": "클라우드 자원 스케줄링", "evidence_count": 9},
                  {"subquestion": "고성능 컴퓨팅 활용 분야", "evidence_count": 4}],
    },
}
GOOD_CARD = {"title": "그리드 자원의 동적 배분 실증 연구", "question": "동적 배분은 작업 대기 시간을 줄이는가?",
             "evidence": ["E1", "E2", "E3"],
             "figure_sentence": "채택 논문 [F1] 가운데 가장 최근 연구는 [F2] 에 나왔다."}
BAD_CARD = {"title": "자원 관리", "question": "자원 관리 연구", "evidence": ["E1", "E9", {"id": "E2"}],
            "figure_sentence": "2013년까지 관련 연구가 전무하다."}


def main() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.test":
            return httpx.Response(200, json=JOB)
        requests.append(request)
        body = json.loads(request.content)
        is_card = "향후 과제" in body["messages"][-1]["content"]
        qwen = request.url.host == "qwen.test"
        if is_card:
            content = json.dumps(GOOD_CARD if qwen else BAD_CARD, ensure_ascii=False)
        else:
            content = '{"concepts": ["그리드 컴퓨팅", "자원 관리", "그리드  컴퓨팅"]}' if qwen else "개념을 찾지 못했습니다"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    with tempfile.TemporaryDirectory() as tmp:
        pairs = Path(tmp) / "pairs.json"
        pairs.write_text(json.dumps({"computing": {"0": "job-1", "1": "job-2"}}), encoding="utf-8")
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            rc = check.main(["--api", "http://api.test/api", "--pairs", str(pairs), "--out-dir", tmp,
                             "--qwen-url", "http://qwen.test/v1", "--qwen-model", "qwen-test",
                             "--gemma-url", "http://gemma.test/v1", "--gemma-model", "gemma-test"],
                            client=client)
        md = (Path(tmp) / "computing.md").read_text(encoding="utf-8")

    def expect(ok: bool, what: str) -> None:
        if not ok:
            raise SystemExit(f"smoke FAIL: {what}\n---\n{md}")

    expect(rc == 0, "check.main 반환값 0")
    bodies = [json.loads(r.content) for r in requests]
    expect([r.url.host for r in requests].count("qwen.test") == 3, "Qwen 요청 3번(개념 1 + 카드 2)")
    expect([r.url.host for r in requests].count("gemma.test") == 3, "gemma 요청 3번")
    expect({b["model"] for b in bodies} == {"qwen-test", "gemma-test"}, "모델 이름")
    concept = next(b for b in bodies if "향후 과제" not in b["messages"][-1]["content"])
    user = concept["messages"][-1]["content"]
    expect(all(s in user for s in [JOB["question"], *JOB["plan"]]), "개념 요청에 원 질문·하위질문")
    expect(concept.get("max_tokens") is not None, "개념 요청에 research_concepts.yaml 의 LLM 파라미터")
    card = next(b for b in bodies if "향후 과제" in b["messages"][-1]["content"])["messages"][-1]["content"]
    expect("그리드 자원의 동적 배분을 실증할 필요가 있다" in card and "[E2]" not in card.split("\n")[0],
           "씨앗에서 [E#] 표기를 걷어 낸다")
    expect("[E1] 그리드 컴퓨팅 자원 관리 (2009)" in card and "[E4] 분산 작업 스케줄러 (연도 미상)" in card,
           "절 논문을 로컬 [E#] 로")
    expect("[F3] 소장 KCI 적재분: 125,000편(1998~2013년)" in card, "적재분 수치 [F#]")
    expect("[F1] 이 하위질문에서 채택한 논문 수: 9편" in md, "절 2 의 채택 수를 소제목으로 찾는다")
    expect("# computing - 컴퓨팅 자원에 대한 연구가 궁금해" in md, "머리")
    expect("| 개념 | 그리드 컴퓨팅 · 자원 관리 | 읽지 못함 |" in md, "개념 표(중복 제거·못 읽음)")
    expect("## 주제 카드 초안 1" in md and "## 주제 카드 초안 2" in md and "초안 3" not in md,
           "향후 과제가 있고 절 논문이 3편 이상인 절 둘만 카드")
    expect("| 형식 검사 | 통과 |" in md, "Qwen 카드 형식 통과")
    for problem in ("유효 근거 1개(3개 미만)", "없는 근거 번호 E9", "문자열이 아닌 근거 1개", "[F#] 없음",
                    "[F#] 밖의 숫자", "단정 표현"):
        expect(problem in md, f"gemma 카드 문제 '{problem}'")
    print("smoke OK")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && python research/round06-qwen-check/smoke_check.py`

Expected: 마지막 줄 `ModuleNotFoundError: No module named 'check'` (`check.py` 가 아직 없다)

- [ ] **Step 3: `research/round06-qwen-check/topic_card_draft.yaml`**

```yaml
parser: plain
params:
  max_tokens: 400
  temperature: 0.3
system: |-
  당신은 연구 주제를 함께 찾는 연구 사서입니다. 딥리서치 보고서가 남긴 향후 과제 하나를 씨앗으로 삼고, 그 과제를 받치는 소장 논문과 코드가 센 수치만 써서 연구 주제 카드 한 장을 만듭니다.

  규칙:
  - title 은 연구 주제 한 줄입니다. 씨앗을 그대로 베끼지 말고 연구할 대상과 관점이 드러나게 씁니다.
  - question 은 이 주제로 답할 연구 질문 한 문장이고 물음표로 끝냅니다.
  - evidence 에는 근거 논문 목록 맨 앞 대괄호 안의 표기를 대괄호 없이 문자열로 씁니다. 이 주제를 직접 받치는 논문만 고르고 3개 이상 씁니다. 목록에 없는 표기는 쓰지 않습니다.
  - figure_sentence 는 수치 목록의 [F#] 표기를 한 개 이상 넣은 한 문장입니다. 숫자는 직접 쓰지 말고 [F#] 표기로만 씁니다.
  - '연구가 없다'·'전무하다'·'최초' 처럼 단정하지 않습니다. 주어진 논문과 수치로 확인한 것만 씁니다.
  - title·figure_sentence 는 '~다' 로 끝나는 문어체로 씁니다('~합니다'·'~입니다' 금지).

  반드시 아래 JSON 형식으로만 응답하세요. 설명이나 다른 텍스트는 출력하지 마세요.
  {
    "title": "<연구 주제>",
    "question": "<연구 질문>",
    "evidence": ["<근거 표기>"],
    "figure_sentence": "<[F#] 표기를 넣은 문장>"
  }
user: |-
  향후 과제(씨앗): {{ seed }}

  근거 논문:
  {{ evidence_list }}

  수치(코드가 센 값):
  {{ figure_list }}
```

- [ ] **Step 4: `research/round06-qwen-check/check.py`**

```python
r"""check.py — Qwen 한국어 품질 표본 확인 (round06a, 1회성)

연구 어시스턴트는 핵심 개념·주제 카드를 Qwen(qwen3-vl-8b)으로 만든다(spec D10, WORK_MODEL_ROUTES). 대회 전에
Qwen 의 한국어 출력이 쓸 만한지 사람이 본다(spec §8 'Qwen 한국어 품질'). 고정 질문의 갈래 0 잡(run_pair.py
출력 JSON)을 HTTP 로 읽어 두 프롬프트를 Qwen 과 gemma 에 똑같이 보내고 out/<질문키>.md 에 나란히 쓴다.
  (a) 핵심 개념 — 연구 어시스턴트가 실제로 보내는 요청 그대로다(services.research_work.concepts 의
      concepts_input → EXECUTOR.build: research_concepts.yaml 렌더와 LLM 파라미터). 응답은 EXECUTOR.parse·check 로 읽는다.
  (b) 주제 카드 초안 — 이 폴더의 topic_card_draft.yaml(06b 가 정식 프롬프트로 옮긴다). 보고서 절의 첫 향후 과제
      (sections[].future)를 씨앗으로, 그 절의 논문을 로컬 [E#] 로, 코드가 센 수치를 [F#] 로 준다. 서로 다른 절에서
      앞에서부터 --cards 장(절 논문이 3편 미만인 절은 건너뛴다 — 근거 3개 이상 규칙을 지킬 수 없다).
vLLM 을 HTTP 로 직접 부른다(scripts/eval_answer_quality.py 의 _chat 방식, 재시도 없음 — 실패는 표에 남긴다).
DB 를 읽지도 쓰지도 않는다. 미달이면 그 작업을 gemma 로 돌린다(라우팅 상수 한 줄 — spec §8).

실행 (서버 — research/ 는 앱 이미지에 없다. 이 폴더를 /data/nl-lib/data/round06-qwen-check/ 로 옮긴다):
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06-qwen-check/check.py \
    --api http://localhost:8000/api --pairs /app/data/research_eval/pairs.json
  --qwen-url·--qwen-model·--gemma-url·--gemma-model 을 주지 않으면 앱 설정(VLM_BASE_URL·VLM_MODEL·LLM_BASE_URL·LLM_MODEL)을 쓴다.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))   # 개발 PC 에서 돌릴 때 — 컨테이너는 PYTHONPATH=/app

PAPERS_PER_CARD = 5
MIN_CARD_EVIDENCE = 3
_YEAR = re.compile(r"(?:19|20)\d{2}")
_FIGURE = re.compile(r"\[F(\d+)\]")
_ABSOLUTE = re.compile(r"전무|최초|연구가 없|연구되지 않")


def endpoints(args: argparse.Namespace) -> dict[str, tuple[str, str]]:
    """{"Qwen": (base_url, model), "gemma": (base_url, model)} — 인자가 없으면 앱 설정."""
    given = (args.qwen_url, args.qwen_model, args.gemma_url, args.gemma_model)
    if all(given):
        qwen_url, qwen_model, gemma_url, gemma_model = given
    else:
        from core.config import get_settings

        cfg = get_settings()
        qwen_url, qwen_model = args.qwen_url or cfg.VLM_BASE_URL, args.qwen_model or cfg.VLM_MODEL
        gemma_url, gemma_model = args.gemma_url or cfg.LLM_BASE_URL, args.gemma_model or cfg.LLM_MODEL
    return {"Qwen": (qwen_url.rstrip("/"), qwen_model), "gemma": (gemma_url.rstrip("/"), gemma_model)}


def call(client: httpx.Client, base_url: str, model: str, messages: list[dict], params: dict) -> dict:
    """llm_client.chat_full 의 openai 본문과 같은 모양으로 한 번 부른다(재시도 없음)."""
    from services.research_work.generate import CALL_TIMEOUT

    started = time.monotonic()
    try:
        res = client.post(f"{base_url}/chat/completions",
                          json={"model": model, "messages": messages, **params}, timeout=CALL_TIMEOUT)
        res.raise_for_status()
        choice = res.json()["choices"][0]
        content, finish, error = (choice["message"]["content"] or "").strip(), choice.get("finish_reason"), None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        content, finish, error = "", None, f"{type(e).__name__}: {e}"
    return {"content": content, "finish": finish, "seconds": time.monotonic() - started, "error": error}


def _job_view(job: dict) -> SimpleNamespace:
    """concepts_input 은 ResearchJob 을 받는다 — GET /api/research/{id} 응답에서 같은 이름의 속성만 옮긴다."""
    return SimpleNamespace(id=job["job_id"], question=job["question"], plan=job.get("plan") or [],
                           report=job.get("report") or {})


def concepts_request(job: dict) -> tuple[list[dict], dict]:
    from services.research_work.concepts import EXECUTOR, concepts_input

    return EXECUTOR.build(concepts_input(_job_view(job)))


def read_concepts(run: dict) -> dict:
    from services.research_work.concepts import EXECUTOR

    out = EXECUTOR.parse(run["content"]) if not run["error"] else None
    return {**run, "concepts": None if out is None else out["concepts"],
            "check": out is not None and EXECUTOR.check(out)}


def _year(pub_date: str | None) -> int | None:
    m = _YEAR.search(pub_date or "")
    return int(m.group(0)) if m else None


def card_seeds(report: dict, limit: int) -> list[dict]:
    """서로 다른 절의 첫 향후 과제를 앞 절부터 limit 개. 그 절의 논문(앞 5편)이 로컬 [E#], 수치가 [F#].

    절 논문이 MIN_CARD_EVIDENCE 편 미만인 절은 건너뛴다 — 근거 3개 이상 규칙을 어느 모델도 지킬 수 없어
    형식 검사가 두 모델을 가르지 못한다(목록에 없는 번호를 지어내게 부추기기도 한다).
    근거가 없는 하위질문은 절이 되지 않아 절 순번과 trail 순번이 어긋난다 — 채택 수는 소제목(= 하위질문)으로 찾는다.
    """
    from services.research.citations import strip_markers

    evidence = report.get("evidence") or {}
    meta = {e["cnts_id"]: e.get("meta") or {} for e in evidence.values()}
    adopted = {t.get("subquestion"): t.get("evidence_count") for t in report.get("trail") or []}
    corpus = report.get("range") or {}
    seeds = []
    for idx, sec in enumerate(report.get("sections") or []):
        futures = [f for f in sec.get("future") or [] if (f.get("text") or "").strip()]
        if not futures:
            continue
        cnts = [p["cnts_id"] for p in sec.get("papers") or [] if p["cnts_id"] in meta][:PAPERS_PER_CARD]
        if len(cnts) < MIN_CARD_EVIDENCE:
            continue
        papers = [{"id": f"E{n}", "title": meta[c].get("title") or "", "year": _year(meta[c].get("pub_date"))}
                  for n, c in enumerate(cnts, start=1)]
        facts = []
        if adopted.get(sec.get("heading")) is not None:
            facts.append(f"이 하위질문에서 채택한 논문 수: {adopted[sec['heading']]}편")
        years = [p["year"] for p in papers if p["year"]]
        if years:
            facts.append(f"근거 논문 중 가장 최근 연도: {max(years)}년")
        if corpus.get("n_papers"):
            facts.append(f"소장 KCI 적재분: {corpus['n_papers']:,}편({corpus.get('from')}~{corpus.get('to')}년)")
        seeds.append({
            "section": idx + 1, "heading": sec.get("heading", ""),
            "seed": strip_markers(futures[0]["text"]),
            "papers": papers,
            "figures": [{"id": f"F{n}", "text": t} for n, t in enumerate(facts, start=1)],
        })
        if len(seeds) >= limit:
            break
    return seeds


def card_request(seed: dict) -> tuple[list[dict], dict]:
    from services.prompts import PromptLibrary

    system, user, params = PromptLibrary(HERE).get("topic_card_draft").render(
        seed=seed["seed"],
        evidence_list="\n".join(f"[{p['id']}] {p['title']} ({p['year'] or '연도 미상'})" for p in seed["papers"]),
        figure_list="\n".join(f"[{f['id']}] {f['text']}" for f in seed["figures"]),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


def card_problems(card: dict | None, seed: dict) -> list[str]:
    """형식 검사 — 근거는 문자열·3개 이상·목록 안 번호, [F#] 사용·[F#] 밖 숫자·단정 표현."""
    if card is None:
        return ["JSON 아님"]
    problems = [f"{key} 없음" for key in ("title", "question", "figure_sentence")
                if not isinstance(card.get(key), str) or not card[key].strip()]
    local = {p["id"] for p in seed["papers"]}
    raw = card.get("evidence") if isinstance(card.get("evidence"), list) else []
    # 모델이 [{"id": "E1"}] 처럼 문자열이 아닌 항목을 내면 집합에 넣을 수 없다 — 빼고 문제로 남긴다
    cited = [e for e in raw if isinstance(e, str)]
    if len(cited) < len(raw):
        problems.append(f"문자열이 아닌 근거 {len(raw) - len(cited)}개")
    valid = {e for e in cited if e in local}
    if len(valid) < MIN_CARD_EVIDENCE:
        problems.append(f"유효 근거 {len(valid)}개({MIN_CARD_EVIDENCE}개 미만)")
    stray = [str(e) for e in cited if e not in local]
    if stray:
        problems.append(f"없는 근거 번호 {', '.join(stray)}")
    sentence = card.get("figure_sentence") if isinstance(card.get("figure_sentence"), str) else ""
    used = {f"F{n}" for n in _FIGURE.findall(sentence)}
    if not used:
        problems.append("[F#] 없음")
    unknown = used - {f["id"] for f in seed["figures"]}
    if unknown:
        problems.append(f"없는 수치 번호 {', '.join(sorted(unknown))}")
    if re.search(r"\d", _FIGURE.sub("", sentence)):
        problems.append("[F#] 밖의 숫자")
    texts = " ".join(str(card.get(k) or "") for k in ("title", "question", "figure_sentence"))
    if _ABSOLUTE.search(texts):
        problems.append("단정 표현")
    return problems


def read_card(run: dict, seed: dict) -> dict:
    from services.research.llm_json import extract_json

    card = extract_json(run["content"]) if not run["error"] else None
    return {**run, "card": card, "problems": card_problems(card, seed)}


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _timing(run: dict) -> str:
    if run["error"]:
        return f"오류 {run['error']}"
    return f"{run['seconds']:.1f}초 · {run['finish']}"


def _table(names: list[str], rows: list[tuple[str, list[str]]]) -> list[str]:
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    lines += [f"| {label} | " + " | ".join(_cell(v) for v in values) + " |" for label, values in rows]
    return lines


def _raw(runs: dict[str, dict]) -> list[str]:
    lines = ["", "<details><summary>원문</summary>", ""]
    for name, run in runs.items():
        lines += [f"**{name}**", "", "````text", run["content"] or "(빈 응답)", "````", ""]
    return lines + ["</details>", ""]


def render_markdown(key: str, job: dict, eps: dict[str, tuple[str, str]], concepts: dict[str, dict],
                    cards: list[tuple[dict, dict[str, dict]]]) -> str:
    names = list(eps)
    lines = [f"# {key} - {job['question']}", "",
             f"- 잡: `{job['job_id']}` (run_pair.py 의 갈래 0)"]
    lines += [f"- {name}: `{model}` @ {url}" for name, (url, model) in eps.items()]
    lines += ["- 사람이 볼 것: 한국어가 자연스러운가, 개념이 원 질문의 핵심인가, 카드의 제목·연구 질문을 고른 근거가 받치는가",
              "", "## 핵심 개념 (research_concepts.yaml)", ""]
    lines += _table(names, [
        ("개념", [" · ".join(r["concepts"]) if r["concepts"] else ("읽지 못함" if r["concepts"] is None else "(빈 목록)")
                for r in concepts.values()]),
        ("내용 검사(2개 이상)", ["통과" if r["check"] else "미달" for r in concepts.values()]),
        ("시간·끝난 이유", [_timing(r) for r in concepts.values()]),
    ])
    lines += _raw(concepts)
    for n, (seed, runs) in enumerate(cards, start=1):
        lines += [f"## 주제 카드 초안 {n} - 절 {seed['section']} 「{seed['heading']}」", "",
                  f"- 씨앗: {seed['seed']}", "- 근거 논문:"]
        lines += [f"  - [{p['id']}] {p['title']} ({p['year'] or '연도 미상'})" for p in seed["papers"]]
        lines += ["- 수치:"] + [f"  - [{f['id']}] {f['text']}" for f in seed["figures"]] + [""]

        def field(run: dict, key: str) -> str:
            card = run["card"] or {}
            value = card.get(key)
            return ", ".join(map(str, value)) if isinstance(value, list) else str(value or "")

        lines += _table(names, [
            ("제목", [field(r, "title") for r in runs.values()]),
            ("연구 질문", [field(r, "question") for r in runs.values()]),
            ("근거", [field(r, "evidence") for r in runs.values()]),
            ("수치 문장", [field(r, "figure_sentence") for r in runs.values()]),
            ("형식 검사", [" · ".join(r["problems"]) or "통과" for r in runs.values()]),
            ("시간·끝난 이유", [_timing(r) for r in runs.values()]),
        ])
        lines += _raw(runs)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    ap = argparse.ArgumentParser(description="Qwen 한국어 품질 표본 확인 (1회성, DB 를 쓰지 않는다)")
    ap.add_argument("--api", required=True, help="API 루트. fastapi 컨테이너 안이면 http://localhost:8000/api")
    ap.add_argument("--pairs", required=True, type=Path, help="scripts/research_eval/run_pair.py 출력(갈래 0 잡을 읽는다)")
    ap.add_argument("--out-dir", type=Path, default=HERE / "out")
    ap.add_argument("--cards", type=int, default=3, help="잡마다 주제 카드 초안 수(서로 다른 절)")
    ap.add_argument("--qwen-url")
    ap.add_argument("--qwen-model")
    ap.add_argument("--gemma-url")
    ap.add_argument("--gemma-model")
    args = ap.parse_args(argv)

    api = args.api.rstrip("/")
    eps = endpoints(args)
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        for key, arms in pairs.items():
            res = client.get(f"{api}/research/{arms['0']}")
            res.raise_for_status()
            job = res.json()
            if job.get("status") != "completed" or not job.get("report"):
                print(f"[{key}] 잡 {arms['0']} 이 완료되지 않았다({job.get('status')}) - 건너뛴다")
                continue
            messages, params = concepts_request(job)
            concepts = {name: read_concepts(call(client, url, model, messages, params))
                        for name, (url, model) in eps.items()}
            cards = []
            for seed in card_seeds(job["report"], args.cards):
                messages, params = card_request(seed)
                cards.append((seed, {name: read_card(call(client, url, model, messages, params), seed)
                                     for name, (url, model) in eps.items()}))
            path = args.out_dir / f"{key}.md"
            path.write_text(render_markdown(key, job, eps, concepts, cards), encoding="utf-8")
            print(f"[{key}] 개념 1 + 카드 {len(cards)} -> {path}")
    finally:
        if own:
            client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && python research/round06-qwen-check/smoke_check.py && python research/round06-qwen-check/check.py --help > /dev/null && echo "check help ok"`

Expected: 세 줄 — `[computing] 개념 1 + 카드 2 -> <임시 폴더>\computing.md`, `smoke OK`, `check help ok`. 첫 줄은 Git Bash(mintty)에서 한글이 깨져 보일 수 있다 — 출력이 cp949 로 나가서이고 실패가 아니다(앞에 `PYTHONIOENCODING=utf-8` 을 붙이면 바로 보인다). `smoke FAIL: …` 이면 그 뒤에 찍힌 마크다운에서 어긋난 칸을 본다(개념 요청이 Task 8 의 `EXECUTOR.build` 를 거치므로, `max_tokens` 나 원 질문·하위질문이 요청에 없다고 나오면 Task 8 의 `concepts_input`·`research_concepts.yaml` 을 먼저 본다).

- [ ] **Step 6: `research/round06-qwen-check/README.md`**

````markdown
# round06a — Qwen 한국어 품질 표본 확인 (1회성)

연구 어시스턴트는 짧고 정형적인 생성(핵심 개념·주제 카드·자식 카드·특징 추출)을 Qwen(`qwen3-vl-8b`, 같은 스택 `nl-lib-vllm`)으로 돌린다(spec `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` D10·§6-3 `WORK_MODEL_ROUTES`). 대회 전에 Qwen 의 한국어 출력이 쓸 만한지 사람이 본다(spec §8 'Qwen 한국어 품질'). 미달이면 그 작업을 gemma 로 돌린다 — `app/services/research_work/routing.py` 의 `WORK_MODEL_ROUTES` 한 줄. 특징 추출 표본은 06c 를 시작할 때 따로 본다.

## 방법

- 입력: 고정 질문 5개(`scripts/research_eval/questions.json`)의 **갈래 0** 잡 — 06a 배포 당일 `scripts/research_eval/run_pair.py` 가 만든 JSON 의 `"0"`. DB 를 읽지도 쓰지도 않는다(잡은 `GET /api/research/{id}` 로 읽는다).
- 프롬프트 두 개를 Qwen 과 gemma 에 똑같이 보낸다(재시도 없음, 호출마다 300초 상한 — 생성 호출과 같다).
  - **핵심 개념** — 연구 어시스턴트가 실제로 보내는 요청 그대로: `services.research_work.concepts` 의 `concepts_input` → `EXECUTOR.build`(`research_concepts.yaml` 렌더와 LLM 파라미터). 응답은 `EXECUTOR.parse`·`check`(2개 이상)로 읽는다.
  - **주제 카드 초안** — 이 폴더의 `topic_card_draft.yaml`(06b 가 정식 프롬프트로 옮긴다). 보고서 절의 첫 향후 과제(`sections[].future`)를 씨앗으로, 그 절의 논문 앞 5편을 로컬 [E#] 로, 코드가 센 수치(그 하위질문의 채택 수·근거 중 최신 연도·적재분 N)를 [F#] 로 준다. 서로 다른 절에서 앞에서부터 3장이고, 절 논문이 3편 미만인 절은 건너뛴다(근거 3개 이상 규칙을 어느 모델도 지킬 수 없어 비교가 되지 않는다). 형식 검사는 근거가 문자열인지·3개 이상·목록 안 번호·[F#] 사용·[F#] 밖 숫자·단정 표현(전무·최초 등)이다. 프롬프트의 JSON 형식에는 근거 자리를 하나만 둔다 — 자리를 셋 두면 모델이 그 개수를 베낀다(함정 15번). 3개 이상은 규칙 줄로만 적는다.
- 출력: `out/<질문키>.md` — 개념·카드마다 Qwen·gemma 를 한 표에 나란히, 원문은 접어 둔다.

| 파일 | 역할 |
|---|---|
| `check.py` | 위 확인을 돌려 `out/` 에 쓴다 |
| `topic_card_draft.yaml` | 주제 카드 프롬프트 초안 — 개수·분야 예시를 넣지 않는다(함정 15번) |
| `smoke_check.py` | 가짜 API·가짜 vLLM 으로 `check.py` 를 끝까지 돌려 본다(개발 PC, 네트워크 없음) — `python research/round06-qwen-check/smoke_check.py` → `smoke OK` |
| `out/<질문키>.md` | 운영 실행 결과 |

실행(서버 — `research/` 는 앱 이미지에 없다. 이 폴더를 `/data/nl-lib/data/round06-qwen-check/` 로 옮긴다):

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06-qwen-check/check.py \
  --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json
```

`RUN` 은 `scripts/research_eval/README.md` 흐름 3 에서 정한 이름이다. `--qwen-url`·`--qwen-model`·`--gemma-url`·`--gemma-model` 을 주지 않으면 앱 설정(`VLM_BASE_URL`·`VLM_MODEL`·`LLM_BASE_URL`·`LLM_MODEL`)을 쓴다 — 운영 생성이 부르는 곳과 같다. 끝나면 서버의 `out/` 을 이 폴더로 가져와 커밋하고 아래 표를 채운다.

## 결과

운영에서 돌린 뒤 사람이 `out/` 을 읽고 채운다. 판정은 '좋음·쓸 만함·미달' 셋 중 하나이고, 미달이면 메모에 까닭을 적는다.

| 질문키 | 핵심 개념 Qwen | 핵심 개념 gemma | 주제 카드 Qwen | 주제 카드 gemma | 메모 |
|---|---|---|---|---|---|
| computing | | | | | |
| library | | | | | |
| elderly | | | | | |
| multicultural | | | | | |
| csr | | | | | |

결정(사람): 핵심 개념 → Qwen 유지 / gemma 로 · 주제 카드 → Qwen 유지 / gemma 로.

'gemma 로' 가 하나라도 있으면 06b 계획의 첫 task 에서 `WORK_MODEL_ROUTES` 의 그 줄을 `GEMMA` 로 바꾸고 라우팅을 고정한 테스트를 함께 고친다. 06a 화면에는 [이 연구 이어가기] 입구가 없어(06b 의 이어가기 카드) 06a 운영에서 생성을 부르는 것은 배포 확인뿐이라 06a 를 다시 배포하지 않는다.
````

- [ ] **Step 7: 기존 테스트가 그대로인지**

`research/` 는 pytest 수집 대상이 아니다. Task 15 까지의 백엔드 결과가 그대로인지만 본다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_eval.py -q -p no:cacheprovider`

Expected: `20 passed`

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add research/round06-qwen-check/smoke_check.py research/round06-qwen-check/topic_card_draft.yaml research/round06-qwen-check/check.py research/round06-qwen-check/README.md && git status --short && git commit -m "[Chore] round06a — Qwen 한국어 품질 표본 확인(1회성, research/round06-qwen-check/): 고정 질문의 갈래 0 잡을 HTTP 로 읽어 핵심 개념(연구 어시스턴트의 실제 요청 — concepts_input → EXECUTOR.build, 응답은 parse·check)과 주제 카드 초안(topic_card_draft.yaml — 절의 첫 향후 과제 씨앗·로컬 [E#] 근거·코드가 센 [F#] 수치, 06b 가 정식 프롬프트로 옮긴다)을 Qwen·gemma 에 똑같이 보내 out/<질문키>.md 에 나란히 쓴다. 카드는 근거 3개 이상(절 논문 3편 미만 절은 건너뛴다)·문자열 근거·목록 안 번호·[F#] 사용·[F#] 밖 숫자·단정 표현을 검사하고, 프롬프트 JSON 형식의 근거 자리는 하나만 둔다(함정 15). DB 를 쓰지 않고, 가짜 API·vLLM 으로 끝까지 도는 smoke_check 를 함께 둔다"
```

---


### Task 17: 문서·배포·전체 검증

**왜:** 현재 상태 문서에 06a 진행을 적고(spec D13 — 하위 라운드마다 계획·dev 머지·완료노트), 전체 테스트로 머지·배포 조건(spec §9 — 자동 테스트 + 운영 기능 확인)을 확인한 뒤, 사용자가 운영에서 배포·기능 확인·critic 두 갈래 판정을 순서대로 할 수 있게 절차를 남긴다(spec §9 배포 순서, D11). 이 계획의 어떤 단계도 운영 서버·DB·Redis 에 쓰지 않는다 — Step 5 부터는 **사용자가** 운영 서버에서 한다.

**Files:**
- Modify: `docs/roadmap/00_status.md` (3행 최종 갱신, 22행 round06 상태 줄, 39행 다음 할 일 round06 줄, 64행 라운드 이력 round06 줄)
- Modify(배포 뒤, Step 15): `docs/ops/recurring-gotchas.md` (126행 — 14번 '현재 서버')
- Modify(판정 합격 때만, Step 14 — dev 에서 분기한 작은 브랜치 `fix/round06a-critic-scope-on`): `app/services/research/state.py` (`DEFAULT_PARAMS` 의 `critic_scope` 줄과 그 위 주석 한 줄 — Task 2 가 넣은 줄)
- Modify(판정 합격 때만, Step 14 — 같은 브랜치): `app/tests/test_research_state.py` (`TestMergeParams.test_critic_scope_is_the_current_criterion_by_default` — Task 2), `app/tests/test_research_critic.py` (`TestCriticScope.test_scope_zero_sends_the_current_prompt_verbatim` 의 매개변수 — Task 2)
- Create(배포 뒤, Step 15 — dev 에서 분기한 기록 브랜치): `scripts/research_eval/labels/<질문키>.csv` 5개, `research/round06-qwen-check/out/<질문키>.md` 5개
- Modify(배포 뒤, Step 15): `research/round06-qwen-check/README.md` (결과 표·결정 줄)
- Modify(Step 12 앞에서 고정 질문을 바꿨을 때만, Step 15): `scripts/research_eval/questions.json`

**알아 둘 것:**
- 기존 문서는 **Edit 도구로** 고친다. 이 worktree 의 문서는 CRLF 다(`core.autocrlf=true`) — Edit 도구는 원래 줄바꿈을 지킨다.
- **순서(사용자 결정 2026-10-03):** 최종 리뷰 → dev 머지(사용자 승인) → dev 코드로 빌드·배포 → 운영 확인 → critic 두 갈래 판정 → (합격 때만) `critic_scope` 기본값을 1 로 바꾸는 작은 브랜치(dev 에서 분기)·dev 머지(사용자 승인)·재배포. 처음 계획(06a 브랜치로 배포 → 판정 → dev 머지)을 바꾼 까닭은 Step 4.
- `00_status.md` 는 round06 에 관한 줄만 고친다. round07 등 다른 라운드 줄은 다른 세션이 고친다(dev 머지 때 충돌을 줄인다).
- 배포 순서의 까닭: ① 워커가 먼저다 — 새 fastapi 는 새 잡의 `params` 에 `critic_scope` 를 합쳐 저장하는데 옛 워커의 `merge_params` 는 모르는 키를 거부해 그 잡이 계획 단계에서 실패한다(round04c `exclude_off_topic` 때와 같다, 교본 round04c 3-4). 새 API 가 보내는 `tasks.dispatch_research_work` 도 새 `celery-research-plan` 만 안다. ② 회수기(`reap_stale_research`)가 바뀌었으므로 `celery-control` 도 Recreate 한다(spec §9 — 06a 필수). ③ 적재 워커(`celery-worker`·`celery-cpu`·`celery-llm`·`celery-embed`)와 `celery-beat` 는 Recreate 하지 않는다 — 스택 업데이트를 하지 않는다(함정 16번, beat 일정은 그대로). ④ fastapi·nuxt 를 Recreate 했으니 마지막에 게이트웨이 reload(함정 20번).
- 스키마는 lifespan 의 `create_all` 이 새 테이블 7개를 만들고 `alembic stamp 0007_research_work` 로 버전만 맞춘다(함정 14번 ③ — `upgrade` 하지 않는다). 기존 테이블에 ALTER 가 없다.

- [ ] **Step 1: `docs/roadmap/00_status.md` — round06 진행**

날짜는 이 단계를 하는 날로 쓴다(아래는 계획 일정의 10/09). 계획 파일 이름이 `docs/superpowers/plans/2026-10-02-round06a-foundation.md` 와 다르면 그 이름으로 쓴다.

`docs/roadmap/00_status.md` — 교체 전(3행):

```markdown
최종 갱신: 2026-10-02 (round05a `dev` 머지(`f293e0e`)·운영 배포(`nl-lib-nuxt`) — `main` 머지와 push 는 라운드 종료 승인 뒤 `/round-finish` 에서. round04b·round04c 종료, round07b `dev` 머지, round07 구현·리뷰 마무리·배포 대기, round06 기획 중단)
```

교체 후:

```markdown
최종 갱신: 2026-10-09 (round06a — 연구 어시스턴트 기반·딥리서치 품질 보강 구현 완료, 운영 배포·critic 두 갈래 판정 대기. round05a `dev` 머지(`f293e0e`)·운영 배포(`nl-lib-nuxt`) — `main` 머지와 push 는 라운드 종료 승인 뒤 `/round-finish` 에서. round04b·round04c 종료, round07b `dev` 머지, round07 구현·리뷰 마무리·배포 대기)
```

3행은 모든 라운드가 함께 고치는 줄이라 위 '교체 후' 의 round06a 밖 구절은 이 브랜치가 갈라질 때(`124c481`)의 글이다. dev 는 그 뒤 이 줄을 이미 고쳤다(예: `ce8a404` 의 'round05a 종료 — … `dev→main` 머지와 `origin` push …'). 그래서 dev 머지 때 3행이 충돌하면 어느 한쪽을 통째로 고르지 않는다 — **dev 쪽 줄을 바탕으로** 날짜를 머지하는 날로 바꾸고, 괄호 안 맨 앞에 `round06a — 연구 어시스턴트 기반·딥리서치 품질 보강 구현 완료, 운영 배포·critic 두 갈래 판정 대기. ` 를 넣고(dev 머지가 배포보다 먼저라 — 2026-10-03 결정, Step 4 — 이 구절 그대로다. 배포·판정 결과는 Step 15 의 기록 브랜치에서 고친다), 끝의 `, round06 기획 중단` 만 지운다. 이 브랜치를 dev 위로 다시 얹은 뒤 이 단계를 하면 교체 전 블록이 맞지 않는다 — 그때도 같은 방법으로 지금 3행에서 고친다. 22·39·64행도 dev 머지 때 충돌한다 — round06 줄은 이 브랜치만 고치지만 dev 가 바로 옆 줄을 고쳐(`ce8a404` round05a 종료, `4bee96e` round07 종료·운영 후속) git 이 한 덩어리로 묶는다(2026-10-03 에 `git merge-tree --write-tree HEAD dev` 로 작업 트리를 건드리지 않고 미리 본 결과 — 충돌은 `00_status.md` 하나에 덩어리 4개(3행 포함)이고, dev 쪽 다른 차이는 문서뿐이라 충돌하지 않는다). 이 셋도 어느 한쪽을 통째로 고르지 않는다 — 덩어리마다 **round06 줄만 이 브랜치 쪽, 나머지 줄은 모두 dev 쪽**을 남긴다(통째로 고르면 round05a·round07 종료 기록이나 06a 기록이 사라진다). ① '현재 상태'(22행 근처): 이 브랜치의 `round06 — 06a 구현 완료·운영 배포 대기` 줄 + dev 의 `round07 종료` 블록(하위 줄 `운영 배포 2026-10-02`·`본 잡 재개 2026-10-02` 포함) — 이 브랜치의 옛 `round07 — 구현·리뷰 마무리, 배포 대기` 줄과 dev 의 `round06 — 기획 중단` 줄은 버린다. ② '다음 할 일'(39행 근처): dev 의 `round07 운영 후속` 블록(①~⑤) + 이 브랜치의 `round06a 배포·판정` 줄(dev 의 `round06 재개` 자리) — 이 브랜치의 `round07 배포` 줄과 dev 의 `round06 재개` 줄은 버린다. ③ 라운드 이력(64행 근처): round05a·round07 행은 dev 쪽(완료 — `main` 머지·push), round06 행만 이 브랜치 쪽. 다 풀고 나면 `grep -cE '^(<<<<<<<|=======|>>>>>>>)|기획 중단|round06 재개|round07 배포' docs/roadmap/00_status.md` 가 `0` 이다(3행에서 `, round06 기획 중단` 을 지웠으면 — 06a 줄의 'round07 운영 배포' 는 걸리지 않는다).

`docs/roadmap/00_status.md` — 교체 전(22행):

```markdown
- **round06 — 기획 중단** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색 → 주제 후보·읽기 목록 → 연구계획서형 초안)으로 넓히는 브레인스토밍. 브랜치 `feat/round06-paper-agent`(dev `138a467` 에서 분기, worktree `.worktrees/round06`). 2026-10-01 기술 구조(설계 ③)와 검증 기준까지 승인된 상태에서 적재 수정(round07)을 먼저 하려고 멈췄다 — 일정(④)이 남았고, spec 은 아직 쓰지 않았다.
```

교체 후:

```markdown
- **round06 — 06a 구현 완료·운영 배포 대기** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색 → 주제 후보·읽기 목록 → 연구계획서형 초안)으로 넓힌다. 설계 `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md`(결정 D1~D17), 하위 라운드 06a 기반·품질 → 06b 수직 슬라이스 → 06c 공백·근거 깊이 ∥ 06d 입구·화면(spec §9 — 대회 10/26 역산, 10/23 기능 동결). 06a 는 브랜치 `feat/round06a-foundation`(worktree `.worktrees/round06a`, `feat/round06-paper-agent` 에서 분기), 계획 `docs/superpowers/plans/2026-10-02-round06a-foundation.md`. 들어간 것: critic 기준 스위치(잡 파라미터 `critic_scope`, 기본 0 — 판정 전), 근거 장부 데이터(`adopted_papers`), 인용의 학술지 자리(`series_title`), `llm_client` 호출별 모델, 브라우저당 딥리서치 실행 제한(429 `browser_active`)·대기 순번(`queue` 이벤트), 새 테이블 7개(마이그레이션 `0007_research_work` — 운영은 `create_all` + `stamp`), 생성 디스패처(전역 1건·`q_research_plan`)와 핵심 개념 생성(Qwen → gemma 넘김), 연구 API(이어가기·work·pool·목록·생성 취소·재시도·SSE), 기록의 단계·진행 표시, 화면의 대기 순번·429 안내, 일일 백업의 `research_*`·`history_items` 덤프, critic 판정 도구 `scripts/research_eval/`, Qwen 표본 확인 `research/round06-qwen-check/`. 배포·판정 절차는 계획 Task 17.
```

`docs/roadmap/00_status.md` — 교체 전(39행, '다음 할 일'):

```markdown
- **round06 재개** — round07 배포와 본 잡 재개 뒤 `.worktrees/round06` 에서 브레인스토밍 일정(④)부터 이어 spec 을 쓴다.
```

교체 후:

```markdown
- **round06a 배포·판정** — 사용자가 계획 Task 17 순서로 한다: 전제 확인(round07 운영 배포 — `nl-lib-celery-control` 이 있다) → 이미지 빌드(nuxt 는 `frontend/public/pdfjs` 를 복사해 넣고) → 딥리서치가 빈 때 워커(`celery-research`·`celery-research-plan`·`celery-control`) → `fastapi` → `nuxt` Recreate → 게이트웨이 reload → 테이블 7개 확인 뒤 `alembic stamp 0007_research_work` → 백업 스크립트 호스트 재설치·1회 실행 → 운영 기능 확인(429 `browser_active`·대기 순번·이어가기 → 핵심 개념 done) → critic 두 갈래 판정(`scripts/research_eval/`, 고정 질문 5개, 라벨은 기획자 — 고정 질문 하나의 단계별 소요 시간·대기 순번도 함께 기록) → 갈래 1 이 다섯 질문 모두 합격이면 `critic_scope` 기본값을 1 로 바꾸는 커밋·재배포, 미달이면 0 으로 둔 채 계획 프롬프트 수정 여부를 사용자에게 묻는다 → Qwen 표본 확인 결과 표(`research/round06-qwen-check/README.md`) → dev 머지(사용자 승인). 그다음 06b(10/10~16) — Qwen 표본 결정이 'gemma 로' 인 작업(핵심 개념·주제 카드)이 있으면 06b 첫 task 에서 `app/services/research_work/routing.py` 의 `WORK_MODEL_ROUTES` 그 줄을 `GEMMA` 로 바꾼다(06a 화면에는 이어가기 입구가 없어 06a 재배포는 하지 않는다).
```

`docs/roadmap/00_status.md` — 교체 전(64행, 라운드 이력 표):

```markdown
| round06 | 논문 에이전트 플랫폼(딥리서치 → 주제 후보·읽기 목록·계획서 초안) | 기획 중단 (`feat/round06-paper-agent`, 브레인스토밍 ③까지 승인) |
```

교체 후:

```markdown
| round06 | 논문 에이전트 플랫폼(딥리서치 → 주제 후보·읽기 목록·계획서 초안) — 하위 라운드 06a~06d | 06a 구현 완료·배포 대기 (`feat/round06a-foundation`) |
```

- [ ] **Step 2: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add docs/roadmap/00_status.md && git status --short && git commit -m "[Docs] round06a — 현재 상태: round06 을 '06a 구현 완료·배포 대기'로 적는다(설계 spec·하위 라운드 06a~06d·06a 브랜치와 계획·들어간 것). 다음 할 일은 06a 배포·판정 순서(워커 → fastapi → nuxt → 게이트웨이 reload → stamp 0007 → 백업 재설치 → 운영 기능 확인 → critic 두 갈래 판정과 고정 질문 운영 기록 → 합격이면 critic_scope 기본값 1) 뒤 dev 머지, 그다음 06b(Qwen 표본이 미달인 작업의 라우팅 전환은 06b 첫 task)"
```

- [ ] **Step 3: 전체 검증**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors`

Expected: 마지막 줄 `1755 passed, 1 skipped, 2 warnings, 3 errors` — 실패 0. Task 0 기준선 1369 에 task 마다 더한 백엔드 테스트 수(각 task 의 전체 검증 단계에 적힌 수와 리뷰 반영으로 더한 수)를 더한 값이다.

| Task | 더한 백엔드 테스트 | 내역 |
|---|---|---|
| 1 | 37 | `test_research_work_models.py` |
| 2 | 21 | state 8 · critic 8 · runner 3 · API 2 |
| 3 | 6 | `test_research_runner.py` |
| 4 | 6 | `test_paper_citation.py` |
| 5 | 11 | `test_llm_client.py` |
| 6 | 18 | `test_research_api.py` |
| 7 | 58 | run_queue 27 · API 29 · 워커 2 — 리뷰 반영 `b401939` 의 11개(run_queue 4 · API 7) 포함 |
| 8 | 43 | generate 17 · concepts 26 |
| 9 | 44 | dispatch 22 · tasks 17 · relay 5 |
| 10 | 9 | `test_research_tasks.py` |
| 11 | 76 | API 60 · 순수 함수 16 |
| 12 | 10 | history repository·API |
| 15 | 20 | `test_research_eval.py` |
| 최종 리뷰 반영 | 27 | 딥리서치 API 3 · 연구 API 3 · 모델·테스트 DB 3 · llm_client 1 · generate 3 · 디스패치 태스크 2 · 회수기 1 · `test_research_eval.py` 11 |
| 13·14·16·17 | 0 | 프론트·셸 스크립트·1회성 `research/`·문서 |

합계 1369 + 386 = 1755. 계획 전체(Task 0~17)를 새 사본에 순서대로 글자 그대로 적용한 통합 검증(2026-10-02)에서는 리뷰 반영분 없이 `1717 passed, 1 skipped, 2 warnings, 3 errors` 를 실측했고, 실행 브랜치에서는 Task 7 리뷰 반영 `b401939` 가 11개를 더해 `1728 passed, 1 skipped, 2 warnings, 3 errors` 를 실측했고(2026-10-03), 그 뒤 최종 리뷰 반영이 27개를 더해 `1755 passed, 1 skipped, 2 warnings, 3 errors` 를 실측했다(2026-10-03). Task 2 의 state·critic 은 새 테스트 수로 8·8 이다(Task 2 의 '실패 이유' 9·7 은 고친 기존 테스트 하나와 이미 통과하는 가드 하나를 넣어 센 실패 수다). 다르면 어느 task 의 테스트가 빠졌거나 늘었는지 task 별 '통과 확인' 명령으로 다시 센다 — 위 표는 계획을 합칠 때 각 task 의 전체 검증 단계 수(`이 작업은 N개를 더한다`·`전체 수치 + N passed`)로 다시 맞춘다. `3 errors` 는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 실패하는 기존 파일 셋(`test_book_chat.py`·`test_build_manifest.py`·`test_loaders.py`)이다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && python research/round06-qwen-check/smoke_check.py && sh -n infra/backup/pg_backup.sh && echo "pg_backup syntax ok"`

Expected: `smoke OK`, `pg_backup syntax ok`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/frontend && npx nuxi typecheck && npx vitest run && npm run build`

Expected: typecheck 오류 0. vitest 는 `Test Files  28 passed (28)` / `Tests  511 passed (511)` — 기준선 28 파일·495 에 Task 4 의 새 테스트 1(`reportDocument.test.ts`)과 Task 13 의 새 테스트 14(researchErrors 4·researchEvents 10), 최종 리뷰 반영의 researchEvents 1 을 더한 값이다(새 테스트 파일 없음 — Task 4 의 `tests/fixtures/citation_reference.json` 은 테스트 파일이 아니다). build 는 오류 없이 끝나고 `.output/server/index.mjs` 가 생긴다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git diff --stat feat/round06-paper-agent -- docker-compose.yml && git log feat/round06-paper-agent..HEAD --format=%B | grep -ciE "Co-Authored-By|Generated with Claude Code"`

Expected: `git diff --stat` 는 아무것도 찍지 않는다(compose 무변경 — spec §6-3, 스택 업데이트가 필요 없다). `grep -ciE` 는 `0`(종료 코드 1 은 맞는 줄이 없을 때의 정상 값이다). Git Bash 의 grep 은 `-i` 와 `-e` 여럿을 함께 주면 `Aborted` 로 죽으므로 `-E` 한 패턴으로 쓴다.

- [ ] **Step 4: 최종 리뷰·dev 머지·배포 요청**

정적 리뷰(`.claude/agents/code-reviewer.md`)와 자가 점검을 마친 뒤 리뷰를 마친 커밋을 적어 둔다(`git rev-parse --short HEAD`). 그다음 순서는 **최종 리뷰 → dev 머지(사용자 승인, 2026-10-03 결정 — 배포 창 동안 dev 로 빌드한 이미지가 06a 를 되돌리는 반쪽 롤백을 막는다) → dev 코드로 빌드·배포(Step 5~10) → 운영 확인(Step 11) → critic 두 갈래 판정(Step 12·13) → (합격 때만) `critic_scope` 기본값을 1 로 바꾸는 작은 브랜치(예: `fix/round06a-critic-scope-on`, dev 에서 분기)·dev 머지(사용자 승인)·재배포(Step 14)** 다. 처음 계획은 06a 브랜치로 배포 → 판정 → dev 머지였다. 그러면 06a 가 운영에 나가 있고 dev 에는 없는 동안 다른 세션이 dev 로 `:latest` 이미지(fastapi·nuxt·celery-research* 등)를 빌드·Recreate 하면 06a 가 말없이 되돌려진다 — 그래서 dev 에 먼저 넣는다.

dev 머지는 사용자 승인을 받아(GIT_WORKFLOW.md) 본 작업 폴더가 아니라 임시 worktree 에서 하고(`git worktree add .worktrees/dev-merge dev` → 머지 → dev push → `git worktree remove .worktrees/dev-merge`), 머지가 끝나면 그 worktree 를 바로 지운다 — dev 를 잡은 worktree 가 남아 있으면 Step 6 의 `git fetch origin dev:dev` 가 거부된다. 그때 `docs/roadmap/00_status.md` 충돌(덩어리 4개)은 Step 1 끝의 규칙대로 푼다 — 3행은 dev 쪽 줄에 06a 구절을 넣고, 나머지 셋은 round06 줄만 이 브랜치 쪽·나머지는 dev 쪽. 이 규칙은 2026-10-03 한 번의 `merge-tree` 결과에 기댄다 — 그 사이 dev 에 다른 라운드가 들어왔을 수 있으니 머지 직전에 `git merge-tree --write-tree HEAD dev` 로 충돌 파일이 `docs/roadmap/00_status.md` 하나뿐인지 다시 본다(다른 파일이 나오면 머지를 멈추고 그 충돌을 사용자와 정한다).

머지 뒤 06a 배포(Step 5~11)를 미루지 않고 이어 한다. dev 머지부터 06a 배포를 마칠 때까지 다른 세션이 dev 로 빌드한 이미지로 `fastapi`·`celery-research`·`celery-research-plan`·`celery-control` 가운데 일부만 Recreate 하면 06a 가 이 Task 의 순서(워커 먼저 → fastapi → stamp) 없이 반쯤 나간다 — 새 fastapi 와 옛 워커면 새 잡이 `critic_scope` 로 계획 단계에서 실패하고(위 '배포 순서의 까닭' ①), 새 `celery-control` 만이면 새 테이블이 생기기 전까지 회수기 틱이 통째로 실패한다(Step 8). 그 사이 다른 배포는 06a 배포 뒤로 미루거나 06a 배포와 함께 한다.

- [ ] **Step 5: (사용자, 서버) 전제 확인**

**서버 명령은 처음부터 root 셸(`su - root`)에서 한다** — 이 서버는 `sudo` 가 아니라 `su - root` 로 root 셸을 열고, 일반 계정 셸에서는 `/data/nl-lib/data` 아래에 쓰다가 Permission denied 가 났다(round07 배포 2026-10-02, dev 의 `bulk_ingest_runbook.md` §9 머리말). 그래서 아래 명령에는 `sudo` 가 없다. 셸을 바꾸면 `pg`·`pgq`·`OLD`·`NEW`·`NEW_NUXT`·`API`·`SID` 를 다시 정의한다.

06a 이미지는 dev(round07 포함) 위에서 빌드된다. round07 이 운영에 나가 있어야 `q_control` 을 받는 `celery-control` 이 따로 있고, 적재 워커를 건드리지 않고 회수기만 바꿀 수 있다. 서버의 같은 셸에서 이어 쓴다 — 아래에서 정한 셸 함수·변수(`pg`·`pgq`·`OLD`·`NEW`·`API`·`SID` 등)를 다음 단계가 쓴다.

```bash
docker ps --format '{{.Names}}' | grep -x nl-lib-celery-control                        # nl-lib-celery-control 한 줄 — 없으면 멈춘다(round07 배포가 먼저)
pg()  { docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; }
pgq() { docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA'; }
echo "SELECT version_num FROM alembic_version" | pgq                                  # 0006_history_items
OLD=$(docker inspect --format '{{.Image}}' nl-lib-fastapi)
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$OLD" ] && echo "$c 같음" || echo "$c 다름"
done                                                                                  # 셋 다 '같음'
```

- `nl-lib-celery-control` 이 없으면 배포하지 않는다 — round07(`bulk_ingest_runbook.md` §9)을 먼저 낸다.
- `다름` 이 있으면 배포를 멈추고 사용자와 되돌릴 이미지를 정한다(round07 배포가 모든 워커를 같은 이미지로 맞췄다 — 롤백은 이 넷이 같은 이미지라는 전제다).

- [ ] **Step 6: (사용자) 이미지 빌드·받기**

운영 스택은 `:latest` 를 쓴다(함정 3번 — `build_dev_images.sh` 의 기본 태그는 `:dev` 라 이미지 이름을 넘긴다). nuxt 이미지는 `frontend/public/pdfjs`(gitignore — 새 worktree 에 없다)가 있는 폴더에서 빌드해야 원문 뷰어가 들어간다(round05a 완료노트 §7 ②).

**빌드는 dev 코드로 한다 — 빌드하는 커밋의 코드가 dev 와 같아야 한다.** 06a 는 Step 4 에서 dev 에 들어갔다. `:latest` 로 `nl-lib-celery-control`(적재 디스패처 `dispatch_job_items`·`job_runtime` 도 돈다)·`fastapi`·`celery-research`·`nuxt` 를 Recreate 하므로, 빌드한 코드가 dev 와 다르면 어느 쪽이든 무언가 되돌려진다 — dev 에 있고 빌드에 없는 코드(병렬 세션 — round07 운영 후속·06d 등 — 이 dev 에 머지·배포한 수정)는 이 이미지가 말없이 되돌리고, 빌드에 있고 dev 에 없는 코드는 다음에 dev 로 빌드하는 세션이 되돌린다(반쪽 롤백). 그래서 둘을 본다: ① 빌드할 HEAD 가 dev 의 조상이거나 dev 와 같다(`git merge-base --is-ancestor HEAD dev`) ② `git log --oneline HEAD..dev -- app frontend infra docker-compose.yml scripts/build_dev_images.sh` 가 비어 있다. dev 머지 직후의 06a worktree(`feat/round06a-foundation`)는 dev 의 조상이고(머지 커밋은 dev 에만 있다), 그 뒤 dev 에 들어온 것이 문서뿐이면 ② 도 비어 있다 — 그 브랜치 그대로 빌드한다. 머지 전인 2026-10-03 에는 `HEAD..dev` 가 문서 커밋 셋(`ce8a404`·`4bee96e`·`acd372e`)뿐이었다.

`git fetch origin dev:dev` 는 로컬 dev 를 origin/dev 로 빨리 감고(origin/dev 도 함께 갱신한다), 실패하면 멈춘다 — 확인하지 못한 채 빌드하지 않는다. fetch 가 성공하면 로컬 dev 가 origin/dev 와 같아 `HEAD..dev` 하나로 둘 다 본다. 확인은 `( … )` 서브셸로 묶었다 — 붙여 넣은 셸에서 `exit 1` 이 셸 창을 닫지 않고 그 묶음만 끝낸다.

```bash
# 개발 PC — dev 머지(Step 4) 뒤, 06a worktree 에서
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a
(
  git fetch origin dev:dev || { echo "fetch 실패 — origin/dev 를 확인하지 못했다, 멈춘다"; exit 1; }
  git merge-base --is-ancestor HEAD dev || { echo "HEAD 에 dev 에 없는 커밋이 있다 — 멈춘다"; exit 1; }
  C=$(git log --oneline HEAD..dev -- app frontend infra docker-compose.yml scripts/build_dev_images.sh)
  [ -z "$C" ] || { printf 'dev 에 HEAD 에 없는 코드 커밋이 있다 — 멈춘다\n%s\n' "$C"; exit 1; }
  echo "빌드해도 된다: $(git rev-parse HEAD)"                                       # 빌드한 커밋 — 완료노트에 적는다
)
```

마지막 줄이 `빌드해도 된다: <커밋>` 일 때만 아래를 한다. 멈췄으면:
- `fetch 실패` — 위에 찍힌 git 메시지를 본다. `refusing to fetch into branch 'refs/heads/dev' checked out at …` 이면 Step 4 의 임시 worktree 가 남아 있다 — 지운 뒤 다시. `[rejected] … (non-fast-forward)` 면 로컬 dev 에 origin 에 없는 커밋이 있다 — 머지 뒤 dev push 를 빠뜨렸으면 push 한 뒤, 둘이 갈라졌으면 임시 worktree 에서 origin/dev 를 dev 에 머지·push 한 뒤 다시. 네트워크·인증 오류면 고친 뒤 다시.
- `HEAD 에 dev 에 없는 커밋` — 그 커밋을 먼저 dev 에 머지하거나(사용자 승인) dev 자체에서 빌드한다.
- `dev 에 HEAD 에 없는 코드 커밋` — 빌드 브랜치에 dev 를 받거나(`git merge --ff-only dev` — ① 을 지났으니 빨리 감기로 dev 와 같아진다) dev 자체에서 빌드한다(그때는 그 폴더에도 `frontend/public/pdfjs` 를 복사한다). 어느 쪽이든 새로 들어온 코드로 Step 3 의 전체 검증을 다시 돌린 뒤 위 확인부터 다시 하고 빌드한다.

```bash
# 개발 PC — 위 확인이 '빌드해도 된다' 로 끝난 같은 폴더에서
cp -r C:/Users/LANDSOFT/mygit/NL_library_AI/frontend/public/pdfjs frontend/public/
ls frontend/public/pdfjs/web/viewer.html                                              # 있어야 한다
NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi
NL_LIB_NUXT_IMAGE=landsoftdocker/nl-lib-nuxt:latest bash scripts/build_dev_images.sh nuxt
```

빌드한 커밋(위 확인의 `빌드해도 된다:` 뒤 값)은 완료노트에 적는다.

```bash
# 서버 — 지금 이미지를 되돌리기용 태그로 남기고 새 이미지를 받는다(Portainer 에 pull 을 맡기지 않는다 — 함정 12번)
docker tag "$OLD" landsoftdocker/nl-lib-fastapi:pre-round06a
docker tag "$(docker inspect --format '{{.Image}}' nl-lib-nuxt)" landsoftdocker/nl-lib-nuxt:pre-round06a
docker pull landsoftdocker/nl-lib-fastapi:latest
docker pull landsoftdocker/nl-lib-nuxt:latest
NEW=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-fastapi:latest)
NEW_NUXT=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-nuxt:latest)
mkdir -p /data/nl-lib/data/round06a /data/nl-lib/data/research_eval /data/nl-lib/data/round06-qwen-check
```

개발 PC 의 `infra/backup/pg_backup.sh` 를 서버 `/data/nl-lib/data/round06a/`, `scripts/research_eval/` 의 파일(`questions.json`·`run_pair.py`·`make_labels.py`·`score.py`·`mark_example.py`)을 `/data/nl-lib/data/research_eval/`, `research/round06-qwen-check/` 의 `check.py`·`topic_card_draft.yaml` 을 `/data/nl-lib/data/round06-qwen-check/` 로 옮긴다(scp 등 평소 쓰는 방법 — `scripts/`·`research/`·`infra/` 는 앱 이미지에 없다, 함정 4번). 위 `mkdir` 로 만든 폴더는 root 소유라 일반 계정 scp 는 Permission denied 다 — 일반 계정 홈으로 받은 뒤 root 셸에서 `cp` 로 옮긴다. 컨테이너 안에서는 `/app/data/…` 다.

- [ ] **Step 7: (사용자, 서버) 비었는지 확인**

`celery-research` 를 Recreate 하면 도는 딥리서치가 끊긴다(회수기가 45분 뒤 failed 로 거둔다). 적재 워커는 건드리지 않지만 적재가 적은 시간에 한다(spec §9).

```bash
pg <<'SQL'
SELECT id, status, stage, created_at FROM research_jobs
WHERE status IN ('created', 'planning', 'approved', 'queued', 'running');
SQL
# 0행이어야 한다 — 있으면 끝나기를 기다린다(사용자 잡을 취소하지 않는다)
for q in q_research q_research_plan; do echo "$q $(docker exec nl-lib-redis redis-cli LLEN $q)"; done   # 둘 다 0
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  echo "== $c"; docker exec $c sh -c 'celery -A workers.celery_app inspect active -d "celery@$(hostname)" --timeout 5'
done   # 셋 다 '- empty -' (celery-control 은 디스패치 틱이 도는 중이면 몇 초 뒤 다시)
JOB=1ca22f59-1e50-4dd1-81f5-2d3c79126825
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$JOB | grep -o '"status_counts":{[^}]*}'   # 적어 둔다(0 이 아니어도 된다 — 적재 워커는 Recreate 하지 않는다)
```

- [ ] **Step 8: (사용자, 서버) 컨테이너별 Recreate — 워커 → fastapi → nuxt → 게이트웨이**

Portainer 에서 컨테이너마다 Recreate 를 누르고 **"Re-pull image" 는 끈다**(서버에 받아 둔 `:latest` 를 쓴다 — 함정 12번). 스택 업데이트는 하지 않는다(함정 16번).

① `nl-lib-celery-research` → ② `nl-lib-celery-research-plan` → ③ `nl-lib-celery-control` 을 차례로 Recreate 한 뒤:

```bash
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$NEW" ] && echo "$c 새 이미지" || echo "$c 옛 이미지"
done                                                                                                     # 셋 다 '새 이미지'
docker exec nl-lib-celery-research-plan sh -c 'celery -A workers.celery_app inspect registered -d "celery@$(hostname)" --timeout 5' | grep -c "tasks.dispatch_research_work"   # 1
docker exec nl-lib-celery-research-plan sh -c 'celery -A workers.celery_app inspect active_queues -d "celery@$(hostname)" --timeout 5' | grep -o "\* {'name': 'q_[a-z_]*'"   # * {'name': 'q_research_plan' 한 줄
docker exec nl-lib-celery-control sh -c 'celery -A workers.celery_app inspect active_queues -d "celery@$(hostname)" --timeout 5' | grep -o "\* {'name': 'q_[a-z_]*'"         # * {'name': 'q_control' 한 줄
docker exec nl-lib-celery-control celery -A workers.celery_app inspect active_queues --timeout 5 | grep -c "'name': 'q_research_plan'"   # 1 — q_research_plan 을 받는 워커는 celery-research-plan 하나뿐
```

`active_queues` 는 큐마다 `* {'name': …, 'exchange': {'name': …}, …}` 한 줄을 찍는데, `-Q` 로 자동 생성된 큐는 exchange 이름이 큐 이름과 같다 — 그래서 줄 머리의 `* {'name':` 만 맞춘다(`'name': 'q_…'` 로 찾으면 같은 이름이 한 줄에서 두 번 나와 큐가 둘 붙은 것처럼 보인다). `inspect` 는 `-d` 가 없으면 브로커의 모든 워커(적재 워커 `celery-worker`·`celery-cpu`·`celery-llm`·`celery-embed` 포함)에 묻는다 — 그래서 한 워커를 볼 때는 `-d "celery@$(hostname)"`(compose 가 노드 이름을 주지 않아 컨테이너 호스트 이름이 곧 노드 이름이다)로 좁히고, 큐를 받는 워커 수를 볼 때만 전체에 묻고 센다(`bulk_ingest_runbook.md` §9 의 `q_control` 세기와 같은 방식). 셋은 같은 새 이미지라 전체에 물으면 `tasks.dispatch_research_work` 가 세 번 나온다.

워커를 Recreate 한 뒤 fastapi 가 뜰 때까지는 새 테이블이 아직 없다(`create_all` 은 fastapi lifespan 이 한다). 그 사이에 회수기 10분 틱(`reap_stale_research`)이 걸리면 `celery-control` 로그에 `relation "research_generations" does not exist` 실패가 한 번 남는다 — 정상이다(그 틱의 잡 회수도 같은 트랜잭션이라 함께 빠지고 다음 틱이 한다). 회수기 로그는 fastapi 기동 뒤의 틱만 본다(Step 11).

④ fastapi 를 Recreate 하기 전에 `library_catalog` 를 쥔 채 멈춘 트랜잭션이 없는지 본다 — lifespan 의 `ALTER TABLE library_catalog …` 가 배타 잠금을 기다리며 기동이 멈추고 그 뒤 조회가 줄 선다(함정 18번).

```bash
pg <<'SQL'
SELECT pid, state, xact_start, left(query, 80) FROM pg_stat_activity WHERE state = 'idle in transaction';
SQL
# 0행(또는 xact_start 가 몇 초 전인 것뿐)이면 nl-lib-fastapi 를 Recreate 한다
docker logs -f --since 1m nl-lib-fastapi 2>&1 | grep -m1 "Application startup complete"   # 모델을 올려 1~2분 걸린다
docker logs --since 10m nl-lib-fastapi 2>&1 | grep -c "DB 테이블 확인 완료"                # 1 — create_all 이 새 테이블을 만들었다
[ "$(docker inspect --format '{{.Image}}' nl-lib-fastapi)" = "$NEW" ] && echo "fastapi 새 이미지"
```

⑤ `nl-lib-nuxt` 를 Recreate 한 뒤 ⑥ 게이트웨이를 reload 한다(함정 20번).

```bash
[ "$(docker inspect --format '{{.Image}}' nl-lib-nuxt)" = "$NEW_NUXT" ] && echo "nuxt 새 이미지"
docker exec nl-lib-gateway nginx -s reload
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health      # 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/            # 200
```

- [ ] **Step 9: (사용자, 서버) 테이블 7개 확인 뒤 `alembic stamp 0007_research_work`**

버전 테이블은 현실을 반영하지 않으니 객체를 따로 본다(함정 14번). `0007` 에는 데이터 백필이 없다.

```bash
pg <<'SQL'
SELECT version_num FROM alembic_version;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ('research_works', 'research_generations', 'research_topics',
  'research_gap_checks', 'research_reading', 'paper_facets', 'research_proposals') ORDER BY 1;
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename IN ('research_works', 'research_generations', 'research_topics', 'research_gap_checks',
  'research_reading', 'paper_facets', 'research_proposals') AND indexname NOT LIKE '%_pkey' ORDER BY 1;
SQL
```

Expected: 버전 `0006_history_items`, 테이블 7행, 인덱스 8행 — `ix_research_gap_checks_work_cell`(work_id, cell_key) · `ix_research_generations_queued`(priority DESC, created_at, id) `WHERE ((status)::text = 'queued'::text)` · `ix_research_generations_work_id` · `ix_research_topics_parent_id` · `ix_research_topics_work_id` · `ix_research_works_owner_created`(owner_sid, created_at DESC) `WHERE (deleted_at IS NULL)` · `ux_research_generations_running` UNIQUE (work_id) `WHERE ((status)::text = 'running'::text)` · `ux_research_topics_slot` UNIQUE (work_id, slot) `WHERE (slot IS NOT NULL)`. 하나라도 다르면 stamp 하지 않고 멈춘다.

```bash
docker exec -e PYTHONPATH=/app -w /app nl-lib-fastapi alembic stamp 0007_research_work
echo "SELECT version_num FROM alembic_version" | pgq                                  # 0007_research_work
```

- [ ] **Step 10: (사용자, 서버 호스트) 백업 스크립트 재설치·1회 실행**

일요일에는 전체 덤프(수 GB)도 함께 돌므로 일요일이 아닌 날 한다.

```bash
diff /usr/local/bin/nl-lib-pg-backup /data/nl-lib/data/round06a/pg_backup.sh           # Task 14 의 변경만 보여야 한다
cp /usr/local/bin/nl-lib-pg-backup /usr/local/bin/nl-lib-pg-backup.pre-round06a        # 되돌리기용(root 셸 — Step 5)
install -m 755 /data/nl-lib/data/round06a/pg_backup.sh /usr/local/bin/nl-lib-pg-backup
/usr/local/bin/nl-lib-pg-backup; echo "exit=$?"                                        # OK …library_catalog_<시각>.dump · OK …research_<시각>.dump, exit=0
F=$(ls -1t /data/nl-lib/backup/daily/research_*.dump | head -1); echo "$F"
docker exec -i nl-lib-postgres pg_restore -l < "$F" | grep "TABLE DATA" | awk '{print $7}' | sort
```

Expected: 마지막 명령이 9줄 — `history_items`·`research_gap_checks`·`research_generations`·`research_jobs`·`research_proposals`·`research_reading`·`research_steps`·`research_topics`·`research_works`. `paper_facets`(다시 만들 수 있는 캐시)는 없다 — 주간 전체 덤프에 맡긴다(spec §6-5). cron 줄(`30 4 * * * /usr/local/bin/nl-lib-pg-backup …`)은 그대로다. 연구 덤프의 복원 절차(연구만 되돌릴 때 `history_items` 를 빼는 `-L` 목록·`--single-transaction`·복원 뒤 approved·queued 잡 정리·확인용 DB `dropdb`)는 스크립트 머리 주석에 있다.

- [ ] **Step 11: (사용자, 서버) 운영 기능 확인 — 429·대기 순번·이어가기 → 핵심 개념**

게이트웨이(포트 92)를 거쳐 확인한다(함정 20번). 축소 파라미터 잡 셋(A·B 는 같은 브라우저 ID, C 는 다른 ID)을 쓴다. 만든 잡과 연구는 실제 기록으로 남는다.

```bash
API=http://localhost:92/api
SID=$(cat /proc/sys/kernel/random/uuid); SID2=$(cat /proc/sys/kernel/random/uuid)
SMALL='{"question":"공공도서관 서비스 품질 평가 연구","params":{"max_subquestions":1,"max_recheck":0,"per_subq_top_k":4}}'
new_job() { curl -s -X POST $API/research -H 'Content-Type: application/json' -H "x-session-id: $1" -d "$SMALL" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4; }
A=$(new_job $SID); B=$(new_job $SID); C=$(new_job $SID2); echo "A=$A B=$B C=$C"
for j in $A $B $C; do until curl -s $API/research/$j | grep -q '"status":"awaiting_approval"'; do sleep 2; done; echo "$j 승인 대기"; done

curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/research/$A/approve          # 200
curl -s -w '\n%{http_code}\n' -X POST $API/research/$B/approve                       # {"detail":{"code":"browser_active","message":"진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요","job_id":"<A 의 id>"}} 다음 줄 429
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/research/$C/approve          # 200 — 다른 브라우저라 막히지 않는다
curl -s $API/research/$C | grep -o '"queue":{[^}]*}'                                # "queue":{"ahead":1,"eta_sec":…} — A 가 도는 동안 바로 본다
for j in $A $C; do until curl -s $API/research/$j | grep -q '"status":"completed"'; do sleep 5; done; echo "$j 완료"; done
curl -s $API/research/$C | grep -o '"queue":[a-z{]*'                                 # "queue":null — 끝난 잡에는 순번이 없다
curl -s -X POST $API/research/$B/cancel | grep -o '"status":"[a-z]*"'                # "status":"canceled" — 승인 못 한 B 를 치운다
```

브라우저로도 본다(선택): 같은 브라우저에서 딥리서치 둘을 차례로 승인하면 둘째가 "진행 중인 딥리서치가 있습니다" 와 [진행 중인 연구 보기] 링크를 보이고, 다른 연구가 도는 동안 승인한 잡의 대기 카드에 "앞에 1건 · 약 N분" 이 붙는다.

이어가기 → 핵심 개념 생성(Qwen, 실패하면 gemma 로 넘김):

```bash
curl -s -X POST $API/research/$A/work/continue -H "x-session-id: $SID" | grep -o '"phase":"[a-z]*"'   # "phase":"topics"
until echo "SELECT status FROM research_generations WHERE work_id = '$A' AND kind = 'concepts'" | pgq | grep -qx -e done -e failed -e canceled; do sleep 5; done
echo "SELECT status FROM research_generations WHERE work_id = '$A' AND kind = 'concepts'" | pgq            # done — failed 면 아래 error 칸을 본다
pg <<SQL
SELECT kind, status, model, jsonb_array_length(output->'attempts') AS calls, output->'concepts' AS concepts, error
FROM research_generations WHERE work_id = '$A';
SELECT phase, concepts, owner_sid FROM research_works WHERE id = '$A';
SELECT count(*) AS candidates FROM research_reading WHERE work_id = '$A';
SQL
curl -s -X POST $API/research/$A/work/continue -H "x-session-id: $SID" > /dev/null           # 두 번째 이어가기
echo "SELECT count(*) FROM research_generations WHERE work_id = '$A'" | pgq                    # 1 — 멱등(행·후보·생성이 한 벌)
curl -sN --max-time 5 $API/research/$A/work/stream | head -c 120; echo                         # data: {"kind": "snapshot", "work": {…
curl -s -o /dev/null -w '%{http_code}\n' $API/research/$A/pool                                 # 200
curl -s -o /dev/null -w '%{http_code}\n' "$API/research-works?example=1" -H "x-session-id: $SID"   # 200
docker logs --since 15m nl-lib-celery-research-plan 2>&1 | grep -c "tasks.dispatch_research_work"   # 1 이상 — 생성은 q_research_plan 에서 돈다
echo "SELECT count(*) FROM research_generations WHERE status IN ('queued', 'running')" | pgq           # 0
```

Expected: 생성 1행 `concepts | done | qwen3-vl-8b`(Qwen 이 실패했으면 `gemma-3-12b`, 둘 다 실패면 model 빈칸·concepts `[]`), `calls` 1~3, `research_works.concepts` 가 생성 출력과 같은 2~5개, `owner_sid` = `$SID`, `candidates` 는 A 의 채택 근거 수. 핵심 개념이 비었으면(둘 다 실패) 생성 출력의 `attempts` 와 `docker logs --since 15m nl-lib-celery-research-plan` 을 보고 사용자에게 알린다 — 배포를 되돌릴 일은 아니다(화면이 '핵심 개념 넣기'를 보인다, spec §5-2). 상태가 `failed` 면(데드라인·예외) `error` 칸과 같은 로그를 보고 사용자에게 알린다 — `G=$(echo "SELECT id FROM research_generations WHERE work_id = '$A' AND kind = 'concepts' ORDER BY id DESC LIMIT 1" | pgq); curl -s -X POST $API/research/$A/generations/$G/retry` 로 다시 넣을 수 있다(응답 `{"gen_id": …}`).

429 `browser_active` 가 계속되는데 응답의 `job_id` 잡이 approved·queued 로 멈춰 있으면 함정 24번의 순서로 본다(브로커 메시지를 잃은 잡은 회수기도 건드리지 않는다 — 화면에서 그 잡을 취소하면 풀린다).

회수기는 fastapi 기동 뒤의 다음 10분 틱 뒤에 본다(그보다 앞 틱의 `relation "research_generations" does not exist` 실패는 Step 8 의 설명대로 정상이다 — `succeeded` 줄만 본다).

```bash
docker logs --since 15m nl-lib-celery-control 2>&1 | grep "reap_stale_research" | grep succeeded | tail -1   # … {'jobs': 0, 'steps': 0, 'generations': 0, 'redispatched': False}
```

- [ ] **Step 12: (사용자, 서버) critic 두 갈래 실행·Qwen 표본 확인·고정 질문 운영 기록**

**고정 질문은 확정됐다(2026-10-04).** 사용자가 "문서 유형을 파악하고 알아서" 정하라고 맡겨, 운영 논문 검색으로 후보마다 적재분 근거를 재서 분야가 겹치지 않게 골랐다 — `computing`(고정)·`library`·`elderly`·`multicultural`·`csr`(처음 후보 `nursing`·`sensor` 는 분야가 `elderly`·`computing` 과 겹쳐 뺐다). 선정 표와 까닭은 `scripts/research_eval/README.md` '고정 질문 선정'. 서버에는 이 `questions.json` 을 옮긴다(Step 6). 완료노트에 이 결정을 적는다.

`scripts/research_eval/README.md` 흐름 3~6 이다. 잡 10개가 차례로 돌아 25분 안팎 걸린다 — 셸이 끊겨도 돌게 nohup 으로 띄운다. Step 11 의 셸(`pg`·`pgq`·`API`·`SID`)에서 이어 한다. 첫 질문의 갈래 1(`params` 의 `critic_scope` 가 1 인 도구 잡 — `created_by` 가 비어 있다)은 갈래 0 이 도는 동안 줄을 선다(실행 워커 1석) — 그때 대기 순번 표시를 본다(spec §8 운영 확인).

```bash
RUN=pairs_$(date +%Y%m%d)
nohup docker exec nl-lib-fastapi python /app/data/research_eval/run_pair.py \
  --api http://localhost:8000/api --out /app/data/research_eval/$RUN.json \
  > /data/nl-lib/data/research_eval/$RUN.out 2>&1 &
until Q=$(echo "SELECT id FROM research_jobs WHERE status IN ('approved', 'queued') AND created_by IS NULL AND params->>'critic_scope' = '1' ORDER BY created_at LIMIT 1" | pgq); [ -n "$Q" ]; do sleep 2; done
curl -s $API/research/$Q | grep -o '"queue":{[^}]*}'          # "queue":{"ahead":1,"eta_sec":…} — 첫 질문의 갈래 1. 적어 둔다
tail -f /data/nl-lib/data/research_eval/$RUN.out          # 질문마다 '완료: 갈래 0 … · 갈래 1 …' — 다섯 번 나오면 Ctrl+C
grep -c '"0":' /data/nl-lib/data/research_eval/$RUN.json   # 5
```

`실패한 질문 …` 줄이 있으면 그 줄의 `--only …` 를 붙여 같은 `--out` 으로 다시 돌린다. 그다음 Qwen 표본 확인(Task 16 — 갈래 0 잡만 읽는다)과 라벨 파일 만들기:

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round06-qwen-check/check.py \
  --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json      # [<질문키>] 개념 1 + 카드 n -> /app/data/round06-qwen-check/out/<질문키>.md 다섯 줄
docker exec nl-lib-fastapi python /app/data/research_eval/make_labels.py \
  --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json \
  --out-dir /app/data/research_eval/labels                                      # [<질문키>] N편(새 N) -> … 다섯 줄
```

Qwen 이 적재 OCR 로 바쁘면 호출마다 최대 300초를 기다린다 — 표의 '시간·끝난 이유' 칸에 그대로 남는다.

고정 질문 하나를 처음부터 끝까지 본 기록(spec §8 운영 확인 — 하위 라운드마다 배포 뒤 단계별 소요 시간과 대기 순번 표시): `computing` 의 갈래 0 잡으로 딥리서치 단계별 시간을 보고, 그 잡을 이어가 핵심 개념 생성까지 잰다. 위에서 적은 대기 순번과 함께 라운드 완료노트에 적는다.

```bash
W=$(docker exec nl-lib-fastapi python -c "import json; print(json.load(open('/app/data/research_eval/$RUN.json'))['computing']['0'])"); echo "$W"
pg <<SQL
SELECT round(extract(epoch FROM started_at - created_at)) AS before_run_sec,
       round(extract(epoch FROM finished_at - started_at)) AS run_sec
FROM research_jobs WHERE id = '$W';
SELECT kind, count(*) AS steps, round(extract(epoch FROM max(finished_at) - min(created_at))) AS sec
FROM research_steps WHERE job_id = '$W' GROUP BY kind ORDER BY min(created_at);
SQL
curl -s -X POST $API/research/$W/work/continue -H "x-session-id: $SID" | grep -o '"phase":"[a-z]*"'   # "phase":"topics"
until echo "SELECT status FROM research_generations WHERE work_id = '$W' AND kind = 'concepts'" | pgq | grep -qx -e done -e failed -e canceled; do sleep 5; done
pg <<SQL
SELECT status, model, round(extract(epoch FROM started_at - created_at)) AS wait_sec,
       round(extract(epoch FROM finished_at - started_at)) AS gen_sec, output->'concepts' AS concepts
FROM research_generations WHERE work_id = '$W' AND kind = 'concepts';
SQL
```

Expected: 첫 질의 1행 — `before_run_sec` 는 계획·승인·줄 서기, `run_sec` 는 탐색·종합. 둘째 질의 `plan`·`search`·`synthesize` 세 줄(단계별 걸린 초). 생성 1행 `done`(model `qwen3-vl-8b`, Qwen 이 실패했으면 `gemma-3-12b`) — `wait_sec` 는 생성 줄에서 기다린 초, `gen_sec` 는 LLM 호출 초다. `failed` 면 Step 11 Expected 의 재시도 방법을 쓴다.

- [ ] **Step 13: (사용자·기획자) 라벨·채점·판정**

기획자가 `/data/nl-lib/data/research_eval/labels/<질문키>.csv` 의 `label` 칸에 `관련`·`무관` 을 단다 — 기준은 원 질문이다(하위질문에서 벗어났어도 원 질문의 주제를 다루면 `관련`, 같은 단어를 다른 뜻으로 쓴 논문을 포함해 원 질문과 무관하면 `무관`). 컨테이너가 쓴 파일이라 root 소유다 — 가져와 엑셀로 달고('CSV UTF-8' 로 저장) 같은 자리에 다시 올린다. 올릴 때도 root 셸에서 옮기거나(일반 계정으로 받은 뒤 `su - root` 로 `cp`) root 로 복사한다 — 일반 계정 scp 는 Permission denied 다.

```bash
docker exec nl-lib-fastapi python /app/data/research_eval/score.py \
  --api http://localhost:8000/api --pairs /app/data/research_eval/$RUN.json \
  --labels-dir /app/data/research_eval/labels
```

Expected: 질문마다 `[<질문키>] <질문>` 과 `갈래 0`·`갈래 1` 두 줄(`절별 무관 …  과잉 제외 …  라벨 없음 N편  -> 합격|불합격|판정 보류`), 그 뒤 `합격 질문: 갈래 0 a/5 · 갈래 1 b/5`(분모는 늘 질문 수 5 — 채점하지 못한 질문도 든다). `판정 보류`·`라벨 칸이 빈 논문이 …` 가 있으면 라벨을 마저 달고 다시 센다. `채점하지 못한 질문 …` 이 있으면 그 질문의 라벨 파일(Step 12 의 make_labels)이나 잡(run_pair `--only`)부터 다시 한다. 판정은 이 둘이 모두 없는 출력으로만 한다. 출력 전체를 판정 기록으로 남긴다. 판정 기록(완료노트)에는 Step 12 앞에서 사용자가 정한 고정 질문 결정(새 질문 4개를 그대로 썼는지, 바꾼 질문)도 함께 적는다.

판정(D11): **갈래 1 이 다섯 질문 모두 합격**이면 Step 14 로 켠다. 하나라도 미달이면 `critic_scope` 기본값을 0 으로 둔 채 06b 를 그대로 진행하고, 계획 프롬프트(`research_plan.yaml`) 수정 여부를 사용자에게 묻는다(spec §7·§10) — Step 14 는 건너뛴다.

- [ ] **Step 14: (합격 때만) critic 기준 스위치를 켠다 — dev 에서 분기한 작은 브랜치·dev 머지·재배포**

06a 는 Step 4 에서 dev 에 들어갔으므로 이 변경은 dev 에서 분기한 작은 브랜치(예: `fix/round06a-critic-scope-on`)에서 하고, dev 머지(사용자 승인) 뒤 dev 코드로 재배포한다. 개발 PC, 06a worktree 에서 브랜치를 만든다(이 worktree 의 `feat/round06a-foundation` 은 이미 dev 에 들어가 있어 바꿔도 된다 — 본 작업 폴더에서는 브랜치를 바꾸지 않는다):

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a
git status --short                                                                    # 비어 있어야 한다
git fetch origin dev:dev && git switch -c fix/round06a-critic-scope-on dev            # fetch 가 실패하면 Step 6 의 안내대로 푼 뒤 다시
```

기본값을 바꾸면 Task 2 의 테스트 둘이 깨진다 — 기본값 0 을 고정한 state 테스트와, 기본 파라미터(`{}`)를 0 갈래로 보던 critic 테스트의 매개변수 하나다. 그 밖의 critic·러너·API 테스트는 갈래를 `{"critic_scope": 0}`·`{"critic_scope": 1}` 로 명시해 그대로다. 먼저 바꾸기 전 수를 센다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_tasks.py tests/test_research_api.py -q -p no:cacheprovider`

Expected: 실패 0. 나온 `N passed` 를 적어 둔다 — 아래를 고친 뒤에도 같은 N 이어야 한다(실행 브랜치에서 `455 passed, 2 warnings` — 2026-10-03 최종 리뷰 반영 뒤 실측. 계획만 글자 그대로 적용한 검증 사본은 444 였고, Task 7 리뷰 반영 `b401939` 가 `test_research_api.py` 에 7개, 최종 리뷰 반영이 `test_research_api.py` 3개·`test_research_tasks.py` 1개를 더했다).

`app/services/research/state.py` — 교체 전(`DEFAULT_PARAMS` 끝 — Task 2 가 넣은 주석의 마지막 줄과 값 줄):

```python
    # 충분·부족은 두 갈래 모두 하위질문 기준이다. 운영에서 고정 질문을 두 갈래로 돌려 합격하면 기본값을 1 로 바꾼다
    "critic_scope": 0,
```

교체 후:

```python
    # 충분·부족은 두 갈래 모두 하위질문 기준이다. 운영 고정 질문 5개 두 갈래 판정에 합격해 기본값을 1 로 켰다(D11)
    "critic_scope": 1,
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_tasks.py tests/test_research_api.py -q -p no:cacheprovider`

Expected: `2 failed` — 이 둘뿐이다.
- `tests/test_research_state.py::TestMergeParams::test_critic_scope_is_the_current_criterion_by_default` — `assert 1 == 0`
- `tests/test_research_critic.py::TestCriticScope::test_scope_zero_sends_the_current_prompt_verbatim[job_params0]` — 매개변수 `{}` 의 잡이 이제 원 질문 기준 프롬프트로 가서 지금 프롬프트와 같지 않다

`app/tests/test_research_state.py` — 교체 전:

```python
    def test_critic_scope_is_the_current_criterion_by_default(self):
        # 원 질문 기준(1)은 운영에서 두 갈래 판정에 합격한 뒤에 기본값을 바꿔 켠다(spec D11)
        assert DEFAULT_PARAMS["critic_scope"] == 0
```

교체 후:

```python
    def test_critic_scope_defaults_to_the_original_question_criterion(self):
        # 운영 고정 질문 5개 두 갈래 판정에 합격해 원 질문 기준(1)을 기본값으로 켰다(spec D11)
        assert DEFAULT_PARAMS["critic_scope"] == 1
```

`app/tests/test_research_critic.py` — 교체 전(`TestCriticScope` 안):

```python
    @pytest.mark.parametrize("job_params", [{}, {"critic_scope": 0}])
    def test_scope_zero_sends_the_current_prompt_verbatim(self, monkeypatch, job_params):
        # 러너는 원 질문을 늘 넘긴다 — 0 갈래는 받아도 쓰지 않는다
        _, system, user, llm_params = self._run(monkeypatch, question=self.QUESTION, **job_params)
        assert (system, user, llm_params) == self._current(**job_params)
        assert self.QUESTION not in system + user
```

교체 후(`{}` 매개변수를 빼고, 기본 파라미터가 원 질문 기준으로 가는 테스트를 그 자리에 둔다 — 수는 그대로다):

```python
    @pytest.mark.parametrize("job_params", [{"critic_scope": 0}])
    def test_scope_zero_sends_the_current_prompt_verbatim(self, monkeypatch, job_params):
        # 러너는 원 질문을 늘 넘긴다 — 0 갈래는 받아도 쓰지 않는다
        _, system, user, llm_params = self._run(monkeypatch, question=self.QUESTION, **job_params)
        assert (system, user, llm_params) == self._current(**job_params)
        assert self.QUESTION not in system + user

    def test_default_params_judge_against_the_original_question(self, monkeypatch):
        # 기본값을 1 로 켰다(D11) — 파라미터를 주지 않은 잡은 원 질문 기준 프롬프트로 간다
        _, _, user, _ = self._run(monkeypatch, question=self.QUESTION)
        _, current_user, _ = self._current()
        assert user == f"원 질문: {self.QUESTION}\n{current_user}"
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_tasks.py tests/test_research_api.py -q -p no:cacheprovider`

Expected: 실패 0, 바꾸기 전에 적어 둔 N 과 같은 `N passed`(실행 브랜치에서 `455 passed, 2 warnings`). 이어서 Step 3 의 백엔드 전체 명령도 실패 0 이고 수는 Step 3 과 같다(새 테스트 없음 — 06a 머지 뒤 dev 에 다른 라운드의 테스트가 들어왔으면 그만큼 다르다).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add app/services/research/state.py app/tests/test_research_state.py app/tests/test_research_critic.py && git status --short && git commit -m "[Feat] round06a — critic 기준 스위치를 켠다: DEFAULT_PARAMS critic_scope 0 → 1. 운영 고정 질문 5개를 두 갈래로 돌린 판정에서 갈래 1(원 질문 기준)이 다섯 질문 모두 합격선(절마다 무관 1편 이하·과잉 제외 10% 이하)을 넘었다(spec D11). 새 잡부터 원 질문 기준이고, 이미 만든 잡은 저장된 params 그대로다. 기본값을 고정한 state 테스트는 새 기본값으로 고치고, critic 의 0 갈래 테스트는 critic_scope 0 을 명시한 잡만 남긴 뒤 기본 파라미터가 원 질문 기준 프롬프트로 가는 테스트를 그 자리에 둔다"
```

dev 머지(사용자 승인) — Step 4 처럼 임시 worktree 에서 이 브랜치를 dev 에 머지하고 dev 를 push 한 뒤 그 worktree 를 바로 지운다. dev 에서 갈라진 브랜치라 충돌이 없다(그 사이 dev 가 `state.py`·두 테스트 파일을 고쳤으면 그 충돌은 사용자와 정한다).

재배포(사용자) — dev 머지 뒤 dev 코드로 빌드한다. 바뀐 것은 백엔드 기본값뿐이라 nuxt 는 그대로다. 새 기본값은 잡을 만드는 fastapi 가 `params` 에 싣지만, 워커와 같은 이미지로 맞추려고 넷 다 Recreate 한다.

```bash
# 개발 PC — dev 머지 뒤, 06a worktree(지금 fix/round06a-critic-scope-on)에서. Step 6 과 같은 확인이다
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a
(
  git fetch origin dev:dev || { echo "fetch 실패 — origin/dev 를 확인하지 못했다, 멈춘다"; exit 1; }
  git merge-base --is-ancestor HEAD dev || { echo "HEAD 에 dev 에 없는 커밋이 있다 — 멈춘다(이 브랜치를 dev 에 머지했는지 본다)"; exit 1; }
  C=$(git log --oneline HEAD..dev -- app frontend infra docker-compose.yml scripts/build_dev_images.sh)
  [ -z "$C" ] || { printf 'dev 에 HEAD 에 없는 코드 커밋이 있다 — 멈춘다\n%s\n' "$C"; exit 1; }
  echo "빌드해도 된다: $(git rev-parse HEAD)"                                       # 빌드한 커밋 — 완료노트에 적는다
)
```

마지막 줄이 `빌드해도 된다: <커밋>` 일 때만 빌드한다. 멈췄으면 Step 6 의 안내대로 푼다(dev 를 받았으면 Step 3 의 전체 검증을 다시 돌린 뒤 위 확인부터 다시).

```bash
# 개발 PC — 위 확인이 '빌드해도 된다' 로 끝난 같은 폴더에서
NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi
```

```bash
# 서버(root 셸 — Step 5)
docker pull landsoftdocker/nl-lib-fastapi:latest
NEW=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-fastapi:latest)
pg <<'SQL'
SELECT id, status FROM research_jobs WHERE status IN ('created', 'planning', 'approved', 'queued', 'running');
SELECT id, kind, status FROM research_generations WHERE status IN ('queued', 'running');
SQL
# 두 질의 모두 0행 — 도는 생성이 있는 채 celery-research-plan 을 Recreate 하면 그 생성이 끊긴다(회수기가 1140초 뒤 failed 로 닫는다). 끝나기를 기다린다
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control; do
  echo "== $c"; docker exec $c sh -c 'celery -A workers.celery_app inspect active -d "celery@$(hostname)" --timeout 5'
done   # 셋 다 '- empty -' (Step 7 과 같다)
# 0행·empty 일 때 Portainer 에서 nl-lib-celery-research → nl-lib-celery-research-plan → nl-lib-celery-control 차례로 Recreate("Re-pull image" 끔)
pg <<'SQL'
SELECT pid, state, xact_start, left(query, 80) FROM pg_stat_activity WHERE state = 'idle in transaction';
SQL
# 0행(또는 xact_start 가 몇 초 전인 것뿐)이면 nl-lib-fastapi 를 Recreate 한다(함정 18번 — Step 8 ④)
for c in nl-lib-celery-research nl-lib-celery-research-plan nl-lib-celery-control nl-lib-fastapi; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$NEW" ] && echo "$c 새 이미지" || echo "$c 옛 이미지"
done                                                                                      # 넷 다 '새 이미지'
docker exec nl-lib-gateway nginx -s reload
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health                       # 200
D=$(curl -s -X POST http://localhost:92/api/research -H 'Content-Type: application/json' \
  -d '{"question":"공공도서관 서비스 품질 평가 연구","params":{"max_subquestions":1}}' | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
curl -s http://localhost:92/api/research/$D | grep -o '"critic_scope":[0-9]'               # "critic_scope":1
curl -s -X POST http://localhost:92/api/research/$D/cancel | grep -o '"status":"[a-z]*"'  # "status":"canceled"
```

- [ ] **Step 15: 배포 기록 커밋**

06a 는 이미 dev 에 있으므로 이 기록 커밋도 dev 에서 분기한 브랜치에서 하고 dev 머지(사용자 승인)로 올린다 — 06a worktree 에서 `git fetch origin dev:dev && git switch -c docs/round06a-deploy-record dev`(Step 14 를 했으면 그 브랜치가 dev 에 머지된 뒤에). Step 12 앞에서 고정 질문을 바꿨으면 `scripts/research_eval/questions.json` 도 이 브랜치에서 고쳐 아래 커밋에 넣는다.

서버의 `/data/nl-lib/data/research_eval/labels/*.csv` 를 06a worktree 의 `scripts/research_eval/labels/` 로, `/data/nl-lib/data/round06-qwen-check/out/*.md` 를 `research/round06-qwen-check/out/` 으로 가져온다. 사람이 `out/` 을 읽고 `research/round06-qwen-check/README.md` 의 결과 표와 결정 줄을 채운다. 그리고 함정 14번의 '현재 서버' 를 고친다.

Qwen 결정 줄에 'gemma 로' 가 있으면(핵심 개념·주제 카드 중 하나라도) 이 라운드에서 라우팅을 바꾸지 않고 06b 로 넘긴다 — 06b 계획의 첫 task 가 `app/services/research_work/routing.py` 의 `WORK_MODEL_ROUTES` 에서 그 kind 의 값(`"concepts": QWEN` 이나 `"topic_card": QWEN`)만 `GEMMA` 로 바꾸고(한 줄에 `concepts`·`topic_card`·`refine`·`facet` 이 함께 있어 줄의 `QWEN` 을 모두 바꾸면 넷이 다 바뀐다), 라우팅을 고정한 Task 8·9 의 테스트(`test_research_work_generate.py` 의 `TestRouting`·기본 kind 가 `concepts` 인 `_run`, `test_research_work_concepts.py`, `test_research_work_tasks.py` 의 Qwen 엔드포인트 단언)를 함께 고친다. 까닭: 06a 화면에는 [이 연구 이어가기] 입구가 없어(06b 의 이어가기 카드 — spec §9) 06a 운영에서 생성을 부르는 것은 Step 11·12 의 확인뿐이고, 주제 카드 실행기는 06b 에 생긴다. 06a 를 다시 배포하면 딥리서치가 빈 때를 다시 기다려 워커 셋과 fastapi 를 Recreate 해야 하지만 사용자가 얻는 것은 없다. 넘김은 Step 1 이 적은 `00_status.md` 다음 할 일 줄과 README 결정 줄에 남는다.

`docs/ops/recurring-gotchas.md` — 교체 전(126행):

```markdown
- **현재 서버**: `alembic_version = 0006_history_items` — round04b 운영 배포(2026-09-28) 때 `stamp` 로 맞췄다(`history_items` 는 lifespan 이 `models.history` 를 import 해 `create_all` 이 만드는 새 테이블이다 — 위 ③ 의 `create_all` + `stamp` 경로). 그 전 `0005_research_jobs` 는 2026-09-23 확인.
```

교체 후:

```markdown
- **현재 서버**: `alembic_version = 0007_research_work` — round06a 운영 배포 때 테이블 7개(`research_works`·`research_generations`·`research_topics`·`research_gap_checks`·`research_reading`·`paper_facets`·`research_proposals`)와 인덱스를 확인한 뒤 `stamp` 로 맞췄다(lifespan 이 `models.research_work` 를 import 해 `create_all` 이 만드는 새 테이블이다 — 위 ③ 의 `create_all` + `stamp` 경로, `0007` 에는 데이터 백필이 없다). 그 전 `0006_history_items` 는 round04b 운영 배포(2026-09-28), `0005_research_jobs` 는 2026-09-23 확인.
```

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round06a && git add -f scripts/research_eval/labels/*.csv && git add research/round06-qwen-check/out/*.md research/round06-qwen-check/README.md docs/ops/recurring-gotchas.md && git status --short && git commit -m "[Docs] round06a 운영 배포 기록 — critic 두 갈래 판정 라벨(질문 단위 CSV 5개, 리허설에서 다시 쓴다)과 Qwen 표본 확인 결과(out/ 5개·결과 표), 함정 14번 현재 서버를 alembic_version 0007_research_work 로(테이블 7개·인덱스 확인 뒤 stamp)"
```

판정 출력·잡 id·배포 시각은 라운드 완료노트(`docs/roadmap/round06a-완료노트.md`)에 적는다 — 판정(Step 13)과 Step 14·15 를 마친 뒤 이 기록 브랜치에서 쓰고 함께 dev 머지(사용자 승인)로 올린다. 빌드한 커밋(Step 6·14), 배포 순서를 dev 머지 먼저로 바꾼 결정(2026-10-03 — Step 4)과 고정 질문 결정(Step 12 앞)도 적는다.

#### 롤백 (사용자, 서버)

배포 뒤 확인(Step 8~11)이 틀리거나 운영 오류가 나면 되돌린다. 새 테이블은 지우지 않는다 — 옛 코드는 쓰지 않고, 다시 배포하면 그대로 쓴다.

1. 딥리서치·생성이 빈 때 한다 — Step 7 의 `research_jobs` 질의가 0행이고 `echo "SELECT count(*) FROM research_generations WHERE status IN ('queued', 'running')" | pgq` 가 0(옛 회수기는 `research_generations` 를 몰라, 끊긴 생성이 running·queued 로 영영 남는다). Step 7 처럼 세 워커의 `inspect active` 도 비었는지 본다. 새 fastapi 가 만든 잡은 `params` 에 `critic_scope` 가 있어 옛 워커가 거부한다 — 그런 잡은 `awaiting_approval` 이든 `failed` 든 되돌린 뒤 승인·retry 하지 말고 새로 만든다. 찾기: `echo "SELECT id, status FROM research_jobs WHERE params ? 'critic_scope' AND status IN ('awaiting_approval', 'failed')" | pgq`.
2. 버전을 먼저 되돌린다(새 이미지의 fastapi 가 `0007` 을 안다): `docker exec -e PYTHONPATH=/app -w /app nl-lib-fastapi alembic stamp 0006_history_items` → `echo "SELECT version_num FROM alembic_version" | pgq` 가 `0006_history_items`.
3. 이미지 태그를 되돌린다: `docker tag landsoftdocker/nl-lib-fastapi:pre-round06a landsoftdocker/nl-lib-fastapi:latest` · `docker tag landsoftdocker/nl-lib-nuxt:pre-round06a landsoftdocker/nl-lib-nuxt:latest`.
4. fastapi 를 Recreate 하기 전에 Step 8 ④ 의 `idle in transaction` 질의가 0행인지 본다(함정 18번). Portainer 에서 `nl-lib-fastapi` → `nl-lib-nuxt` → `nl-lib-celery-research` → `nl-lib-celery-research-plan` → `nl-lib-celery-control` 차례로 Recreate("Re-pull image" 끔). fastapi 를 먼저 되돌리면 그 뒤 만든 잡에는 `critic_scope` 가 없어 새·옛 워커 모두 받는다.
5. 남은 것 치우기: `docker exec nl-lib-redis redis-cli DEL research:run_queue`(대기 순번 ZSET). `docker exec nl-lib-redis redis-cli LLEN q_research_plan` 이 0 이 아니면 남은 `tasks.dispatch_research_work` 메시지다 — 옛 `celery-research-plan` 이 '등록되지 않은 태스크' 오류 로그를 남기고 버린다.
6. `docker exec nl-lib-gateway nginx -s reload` → `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health` 가 200. `docker exec nl-lib-celery-research-plan celery -A workers.celery_app inspect registered --timeout 5 | grep -c "tasks.dispatch_research_work"` 가 0 — `-d` 없이 모든 워커에 묻는다. 적재 워커는 06a 에서 Recreate 하지 않아 round07 이미지이고 되돌린 셋도 옛 이미지라, 0 이면 그 태스크를 아는 워커가 하나도 없다.
7. 백업 스크립트는 새 것을 둬도 옛 스키마에서 돈다(`research_*` 는 `research_jobs`·`research_steps` 를 받는다). 되돌리려면 root 셸(Step 5)에서 `install -m 755 /usr/local/bin/nl-lib-pg-backup.pre-round06a /usr/local/bin/nl-lib-pg-backup`.
8. critic 기준만 되돌릴 때(Step 14 뒤): dev 에서 분기한 브랜치에서 Step 14 의 커밋을 `git revert <그 커밋>` 으로 되돌려(`state.py` 의 기본값·주석과 테스트 둘이 함께 돌아간다) dev 머지(사용자 승인) 뒤 Step 14 의 재배포 순서로 낸다. 급하면 새 잡을 만들 때 `params` 에 `{"critic_scope": 0}` 을 실어 그 잡만 지금 기준으로 돌린다.
9. 1~7 로 되돌린 뒤에도 dev 에는 06a 가 있다(dev 머지가 배포보다 먼저다 — Step 4). 그대로 두면 다음에 dev 로 이미지를 빌드·Recreate 하는 세션이 06a 를 이 Task 의 순서 없이 다시 낸다 — 고쳐서 다시 배포할지, dev 에서 06a 를 되돌릴지(revert, 사용자 승인) 정하기 전까지 dev 로 `fastapi`·`nuxt`·`celery-research`·`celery-research-plan`·`celery-control` 이미지를 빌드·Recreate 하지 않는다.

