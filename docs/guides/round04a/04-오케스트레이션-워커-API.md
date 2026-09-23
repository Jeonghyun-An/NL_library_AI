# round04a 교본 (5) — 오케스트레이션·워커·API·배포

> 이 교본 하나로 round04a 전체를 클론코딩할 수 있어야 한다. 코드는 저장소 파일을 그대로 수록했다(`GIT_WORKFLOW.md` §개발 가이드 문서).

전체 개요·검증·Q&A 는 [00-개요.md](00-개요.md) 참조.

## 이 챕터의 자리

`app/services/research/` 의 단계 함수(`planner`·`critic`·`explorer`·`synthesizer`)는 입력을 받아 값을 돌려줄 뿐 DB 도, 큐도, 화면도 모른다. 이 챕터는 그것들을 **실제로 도는 잡**으로 묶는 층이다 — 하위질문 루프(`runner`), 진행 중계(`relay`), Celery 태스크(`research_tasks`), FastAPI 엔드포인트와 SSE(`api/research`), 그리고 큐 설정·라우팅·compose(배포).

잡 하나가 지나가는 길은 이렇다.

| 순서 | 누가 | 무엇을 | 잡 상태 |
|---|---|---|---|
| 1 | `POST /api/research` | 잡 행을 만들고 `tasks.plan_deep_research` 를 큐에 넣는다 | `created` |
| 2 | 워커 `plan_deep_research` | 선점 → 계획 LLM → `plan` 저장 | `planning` → `awaiting_approval` |
| 3 | `POST /{id}/approve` | 고친 계획 검증 → 조건부 전이 → `tasks.run_deep_research` | `approved` |
| 4 | 워커 `run_deep_research` | 선점 → 하위질문마다 `explore_subquestion` → 체크포인트 → `synthesize` | `running` → `completed` · `failed` |
| 5 | `GET /{id}/stream` | `research_steps` 스냅샷 + Redis 이벤트 중계 | — |
| — | `POST /{id}/cancel` · `/retry` | 취소는 진행 중인 거의 모든 상태에서, 재시도는 `failed` 에서 | `canceled` · `queued` |
| — | beat `reap_stale_research` | 10분마다, 시작(`started_at`, 없으면 생성 시각)한 지 45분이 지나도록 `planning`·`running` 인 잡을 `failed` 로 | — |

상태 전이 전체는 `app/api/research.py` 모듈 docstring 에 그려 두었다.

```text
    created ─plan─→ planning ─→ awaiting_approval ─approve─→ approved
    approved ─run─→ running ─→ completed | failed
    failed ─retry─→ queued ─run─→ running (stage=explored 면 종합부터)
    (거의 모든 상태) ─cancel─→ canceled
```

이 표에서 가장 중요한 성질은 **상태를 쓰는 프로세스가 여럿이라는 것**이다. 진행은 딥리서치 워커가, 취소·승인·재시도는 API 가, 회수는 `celery-cpu` 의 회수 태스크가 찍는다. 이 챕터의 설계 결정 대부분이 "여러 프로세스가 같은 행을 쓸 때 누가 이기는가"에 대한 답이다.

### 진행 기록은 2계층이다

| 계층 | 저장소 | 쓰는 곳 | 입자 | 수명 |
|---|---|---|---|---|
| 굵은 단계 | Postgres `research_steps` | 워커 `_step`·`_finish` | `plan` 1 + 하위질문마다 `search` 1 + `synthesize` 1 (기본 파라미터 하위질문 6개면 8행) | 영구 |
| 잔이벤트 | Redis pub/sub `research:{job_id}` | runner 의 `emit` → `relay.publish`, 종료는 `relay.publish_terminal` | `search`·`critique` 는 검색 라운드마다, 그리고 종료 이벤트 | 휘발 |

spec §2-3 의 결정이다. 한 테이블로 진행 패널과 보고서를 겸하면 입자가 충돌한다 — 잘게 쓰면 보고서가 지저분해지고 굵게 쓰면 화면이 멈춰 보인다. 카운터가 째깍거릴 때마다 Postgres 에 쓸 이유도 없다. 그래서 재접속하면 **뼈대는 DB 에서 복원하고, 그 이후는 Redis 에서 이어받는다.**

SSE 한 연결의 순서는 다음과 같다(§2.37).

1. 접속 순간 `research_steps` 를 읽어 `snapshot` 프레임 1개.
2. 잡이 이미 끝났으면 종료 프레임을 보내고 닫는다 — 구독하면 영원히 기다린다.
3. 아니면 구독한다. 이벤트는 그대로 흘리고, 15초 유휴마다 `: ping` 주석 프레임을 보내며 그때 DB 를 다시 본다. 끝났으면 종료 프레임을 보내고 닫는다.
4. 종료 프레임의 모양은 워커가 보내든 엔드포인트가 DB 를 보고 만들든 `relay.terminal_event` 하나로 만든다.

"놓친 잔이벤트는 볼 필요가 없다"는 원칙은 코드에서도 그대로다. 스냅샷을 읽은 뒤에 구독하므로 그 사이에 나간 `search`·`critique` 는 받지 못하고, Redis pub/sub 에는 재생이 없다. **종료 이벤트만은 놓치면 스트림이 닫히지 않으므로** 하트비트가 DB 로 다시 확인한다(최대 15초 늦게 닫힌다).

**spec 과 달라진 점**(spec §2-3·§3-3 구현 시 변경). step 은 하위질문당 1행이다 — 재검색 라운드는 같은 `search` 행의 `result.queries` 에 누적되고, `critique` 는 행으로 남지 않는다. Redis 로 흐르는 것은 `search`·`critique`·종료(`done`·`failed`·`canceled`) 셋뿐이고 **step 생성·종료와 계획 완료는 중계되지 않는다.** round04b 는 그것을 `GET /api/research/{id}` 폴링으로 얻는다. 중계를 보강할지 화면을 폴링에 맞출지는 round04b 착수 전에 정한다(완료노트 §8).

## 2. 구현 (클론코딩)

### 2.32 `config.py` — 딥리서치 큐 설정 두 개

**책임.** 계획·실행 태스크가 갈 큐 이름을 설정으로 뺀다. `RESEARCH_QUEUE` 는 실행 큐(기본 `q_llm`), `RESEARCH_PLAN_QUEUE` 는 계획 큐(비우면 `RESEARCH_QUEUE` 를 따른다).

**왜 설정인가.** 첫 구현(`f1ba3e1`)은 태스크 데코레이터와 라우팅 표에 `q_llm` 을 박아 두었다. 머지 전 리뷰가 여러 영역에서 같은 문제를 짚었다 — `q_llm` 은 적재의 요약·마무리 단계(`tasks.stage_summarize`·`tasks.stage_finalize`)가 도는 FIFO 라, 사용자의 계획 요청(0.6초짜리)이 요약 수십 건 뒤에 서고, 반대로 리서치 실행이 `celery-llm` 슬롯 4개 중 하나를 잡마다 오래 쥔다. 게다가 `celery-llm` 에는 GPU 도 모델 캐시도 없어 탐색의 BGE-M3·리랭커를 recreate 할 때마다 새로 받아 CPU 로 돌렸다(함정 17번). 답은 전용 큐·워커였다.

그런데 **바로 옮길 수 없었다.** 대량 인덱싱이 돌고 있고, 스택 업데이트 한 번이 같은 `:latest` 를 쓰는 적재 워커를 모두 재생성해 처리 중인 아이템을 끊는다(함정 16번). 그래서 큐 이름을 설정으로 빼고 **기본값을 옛 동작(`q_llm`)** 으로 두었다. 코드만 먼저 내보내면(기존 컨테이너를 설정 그대로 Recreate) 지금처럼 `celery-llm` 이 받고, compose 가 `q_research` 를 주는 순간 전용 워커로 넘어간다. 코드 배포와 큐 전환을 떼어 놓는 스위치다(배포 순서는 §2.39).

**계획 큐를 따로 둔 이유.** 전용 실행 워커는 `--concurrency=1` 이다(§2.39). 계획이 같은 큐에 있으면 다른 잡의 실행(최대 25분) 뒤에 서서 새 질문이 `created` 로 멈추고 "계획 수립 중"조차 뜨지 않는다. 이건 리뷰 반영을 검수하면서 나온 것이다 — 전용 워커를 concurrency 1 로 두자 계획까지 다른 잡의 실행 뒤에 섰다(완료노트 §4).

**빈 값 처리.** `RESEARCH_PLAN_QUEUE` 를 `model_validator(mode="after")` 로 채우는 이유는 "설정 안 함"과 "빈 문자열" 을 같게 다루기 위해서다. compose 가 빈 값을 넘겨도 계획이 이름이 `""` 인 큐로 가면 안 된다(`test_blank_plan_queue_follows_research_queue`). 두 값은 `get_settings()`(`lru_cache`)가 처음 불릴 때 한 번 읽어 캐시하고, `celery_app`·`research_tasks` 는 import 시점에 부른다 — 바꾸려면 컨테이너를 다시 띄워야 한다.

**파일**: `app/core/config.py` — `main` 대비 변경분(diff)

```diff
diff --git a/app/core/config.py b/app/core/config.py
index 889bd40..ea6a0b8 100644
--- a/app/core/config.py
+++ b/app/core/config.py
@@ -1,6 +1,6 @@
 from functools import lru_cache
 
-from pydantic import field_validator
+from pydantic import field_validator, model_validator
 from pydantic_settings import BaseSettings
 
 
@@ -112,6 +112,22 @@ class Settings(BaseSettings):
     # ── 도메인 프로파일 ──────────────────────────────
     DOMAIN_PROFILE: str = "nl_library"
 
+    # ── 딥리서치 ─────────────────────────────────────
+    # 계획·실행 태스크의 큐. 기본값이 q_llm 인 이유: 코드만 먼저 배포하면(기존
+    # 컨테이너 env 그대로) 지금처럼 celery-llm 이 받는다. 전용 워커(-Q q_research)를
+    # 띄울 때 보내는 쪽(fastapi)과 같이 q_research 로 바꾼다.
+    RESEARCH_QUEUE: str = "q_llm"
+    # 계획 태스크만 따로 보내는 큐. 비우면 RESEARCH_QUEUE 를 따른다(코드만 먼저 배포할
+    # 때 그대로 q_llm). 전용 워커는 concurrency 1 이라 계획(0.6초)이 같은 큐에 있으면
+    # 다른 잡의 실행(최대 25분) 뒤에 서서 새 질문이 created 로 멈춘다.
+    RESEARCH_PLAN_QUEUE: str = ""
+
+    @model_validator(mode="after")
+    def _plan_queue_follows_research_queue(self) -> "Settings":
+        if not self.RESEARCH_PLAN_QUEUE.strip():
+            self.RESEARCH_PLAN_QUEUE = self.RESEARCH_QUEUE
+        return self
+
     # ── 대량 인덱싱 잡 ───────────────────────────────
     INGEST_HIGH_WATER: int = 32          # 잡당 동시 in-flight 아이템 수
     INGEST_MAX_ATTEMPTS: int = 3         # 아이템당 자동 재시도 한도
```
따라 친 뒤 확인(`app/` 에서, `.env` 에 두 키가 없을 때):

```bash
$ python -c "from core.config import get_settings as g; s=g(); print(s.RESEARCH_QUEUE, s.RESEARCH_PLAN_QUEUE)"
q_llm q_llm
$ RESEARCH_QUEUE=q_research RESEARCH_PLAN_QUEUE= python -c "from core.config import get_settings as g; s=g(); print(s.RESEARCH_QUEUE, s.RESEARCH_PLAN_QUEUE)"
q_research q_research
$ RESEARCH_QUEUE=q_research RESEARCH_PLAN_QUEUE=q_research_plan python -c "from core.config import get_settings as g; s=g(); print(s.RESEARCH_QUEUE, s.RESEARCH_PLAN_QUEUE)"
q_research q_research_plan
```

### 2.33 `celery_app.py` — 태스크 등록·라우팅·회수 스케줄

**책임.** `workers.research_tasks` 를 `include` 에 넣어 워커가 태스크를 등록하게 하고, 세 태스크의 큐를 정하고, 회수 태스크를 beat 에 건다.

- `tasks.plan_deep_research` → `RESEARCH_PLAN_QUEUE`, `tasks.run_deep_research` → `RESEARCH_QUEUE`.
- `tasks.reap_stale_research` → `q_control`. 제어 큐의 소비자는 `celery-cpu`(`-Q q_cpu,q_control`)라, 회수는 딥리서치 워커가 아니라 그쪽에서 돈다 — 딥리서치 워커가 죽어 있어도 회수는 돈다.
- beat `reap-stale-research` 600초. 워커 프로세스가 죽으면 잡이 `running` 인 채 영원히 남는다(§2.36 ⑦).

**라우팅 표가 큐를 정한다.** API 는 태스크 모듈을 import 하지 않고 이름으로 보낸다(`celery_app.send_task`, §2.37 `_enqueue`). 데코레이터의 `queue=` 도 같은 설정값을 읽게 해 두 곳이 갈리지 않게 했다. 둘 다 **모듈 import 시점에** 평가되므로 큐를 결정하는 것은 보내는 프로세스(fastapi)가 뜰 때의 env 다. 받는 쪽은 워커의 `-Q` 가 정한다 — 둘이 어긋나면 태스크가 소비자 없는 큐에 쌓이기만 한다.

**기존 설정이 워커 설계에 미친 영향.** 이 파일의 기존 값 `task_acks_late=True`·`visibility_timeout: 7200` 은 적재용이지만 딥리서치 태스크에도 그대로 걸린다. ack 전에 워커가 죽으면 같은 메시지가 2시간 뒤 다시 배달된다(at-least-once). 워커의 선점이 조건부여야 하는 이유가 여기서 나온다(§2.36 ④).

**파일**: `app/workers/celery_app.py` — `main` 대비 변경분(diff)

```diff
diff --git a/app/workers/celery_app.py b/app/workers/celery_app.py
index 8ff96a2..1b0d5fd 100644
--- a/app/workers/celery_app.py
+++ b/app/workers/celery_app.py
@@ -7,7 +7,7 @@ celery_app = Celery(
     "nl-lib",
     broker=cfg.REDIS_URL,
     backend=cfg.REDIS_URL,
-    include=["workers.tasks"],
+    include=["workers.tasks", "workers.research_tasks"],
 )
 celery_app.conf.update(
     task_serializer="json",
@@ -30,6 +30,12 @@ celery_app.conf.update(
         "tasks.stage_finalize":    {"queue": "q_llm"},
         "tasks.dispatch_job_items":  {"queue": "q_control"},
         "tasks.cleanup_temp_files":  {"queue": "q_control"},
+        # 딥리서치 — 계획·실행은 설정 큐(core/config.py RESEARCH_QUEUE·RESEARCH_PLAN_QUEUE
+        # 주석), stale 회수는 제어 큐. 적재 요약과 같은 q_llm FIFO 에 있으면 사용자의 계획
+        # 요청이 요약 수십 건 뒤에 선다.
+        "tasks.plan_deep_research":  {"queue": cfg.RESEARCH_PLAN_QUEUE},
+        "tasks.run_deep_research":   {"queue": cfg.RESEARCH_QUEUE},
+        "tasks.reap_stale_research": {"queue": "q_control"},
     },
     beat_schedule={
         "dispatch-job-items": {
@@ -40,5 +46,11 @@ celery_app.conf.update(
             "task": "tasks.cleanup_temp_files",
             "schedule": 3600.0,
         },
+        # 워커가 죽으면 잡이 running 인 채 영원히 남는다 — 하드 리밋을 넘긴 것만 회수한다
+        # (research_tasks.STALE_MINUTES)
+        "reap-stale-research": {
+            "task": "tasks.reap_stale_research",
+            "schedule": 600.0,
+        },
     },
 )
```
확인은 §2.43 의 `TestQueue`(celery 가 로컬에 없어 더미로 import 한다).

### 2.34 `relay.py` — Redis 진행 중계

**책임.** 잔이벤트를 Redis pub/sub 채널 `research:{job_id}` 로 흘리고(`publish`), SSE 엔드포인트가 그것을 받는다(`subscribe`). 종료 이벤트의 모양을 한 곳에서 정한다(`terminal_event`·`TERMINAL_KIND`).

**설계 결정 넷.**

**① 중계 실패가 리서치를 죽이면 안 된다.** 중계는 화면용이고 보고서가 아니다. `publish` 는 예외를 삼키고 경고 로그만 남긴다. 다만 **응답 없는 Redis 는 예외가 아니라 무기한 대기**라 삼킬 기회조차 없다 — redis-py 의 소켓 타임아웃 기본값이 `None`(무제한)이라, Redis 가 연결만 받고 답하지 않으면 워커가 첫 emit 에서 멈춘 채 시간 상한까지 슬롯을 쥔다(리뷰 지적). 그래서 `_with_timeouts` 가 `REDIS_URL` 에 `socket_connect_timeout`·`socket_timeout` 2초를 얹는다. URL 에 운영자가 이미 준 값은 덮지 않는다. 타임아웃은 publish 에만 건다 — 구독은 15초 유휴 대기가 정상 동작이라 성격이 다르다.

**② 클라이언트를 호출마다 만든다.** 모듈 전역에 클라이언트를 하나 두면 첫 이벤트 루프에 묶인다. 워커는 잡마다 `asyncio.run` 으로 루프를 새로 열고 닫으므로(§2.36 ①) 두 번째 잡부터 `Event loop is closed` 로 죽는다. 한 잡에 수십 번 도는 정도라 연결 비용보다 이쪽이 싸다. 워커 DB 엔진을 잡 단위로 만드는 것과 같은 이유다.

**③ 구독은 유휴 때 `None` 을 낸다.** 처음(`f2290c8`)엔 `pubsub.listen()` 이었다. `listen()` 은 트래픽이 없는 동안 영원히 블록하므로 클라이언트가 조용히 끊겨도 알 방법이 없다 — 아무것도 쓰지 않으니 broken pipe 조차 나지 않는다. `get_message(timeout=idle_timeout)` 으로 바꿔 유휴 15초마다 `None` 을 내게 했고, 엔드포인트가 그때 `: ping` 을 쓰면서 끊긴 소켓을 드러내고 잡의 종료도 확인한다(`f1ba3e1`).

**④ 종료 이벤트의 모양은 하나다.** 리뷰 전에는 연결 시점에 따라 같은 종료가 다른 프레임으로 나갔다. 라이브로 붙어 있으면 워커가 보낸 `{kind:"done", status:"completed"}`·`{kind:"failed", error}`·`{kind:"canceled"}` 를, 끝난 잡에 붙거나 하트비트로 종료를 감지하면 상태와 무관하게 `{kind:"done", status:<…>}` 를 받았다. 프론트가 `kind === "done"` 이면 보고서를 로드하게 짜면, 실패한 잡을 다시 연 사용자는 보고서 로드로 분기해 빈 화면을 본다. `TERMINAL_KIND` 가 종료 상태 → kind 를 한 번만 정하고, 워커(`publish_terminal`)와 엔드포인트가 모두 `terminal_event` 를 거친다. `error` 는 200자로 자른다.

**`redis` 를 최상단에서 import 하는 모듈이다.** 그래서 runner 는 이 모듈을 import 하지 않고 `emit` 을 인자로 받는다(§2.35). 로컬 venv 에는 `redis` 가 없어, 최상단에서 물면 테스트 수집 단계가 통째로 죽는다(함정 13번의 torch 와 같은 함정).

**남겨 둔 것.** `publish` 의 `except Exception` 은 publish 도중 들어온 `SoftTimeLimitExceeded` 도 삼킨다 — 함정 19번의 재발 방지 규칙("폴백은 실제로 나는 실패 타입만")과 어긋나는 코드다. 실제 영향은 잡 데드라인이 흡수한다(데드라인 25분이 소프트 리밋 30분보다 먼저 온다, §2.36 ⑦). 좁히려면 로컬 더미 redis 에서도 쓸 수 있는 예외 타입 목록이 필요해 low 로 이월했다(완료노트 §8).

**파일**: `app/services/research/relay.py` — 전체 104줄

```python
"""relay.py — 진행 이벤트 중계 (Redis pub/sub)

잔이벤트는 여기로만 흐르고 Postgres 에 쓰지 않는다. 카운터가 째깍거리는
것 때문에 DB를 때릴 이유가 없고, 몇 초 뒤 아무도 안 본다.
재접속하면 research_steps 로 뼈대를 복원하고 그 이후를 여기서 받는다.

이 모듈은 `redis` 를 최상단에서 물고 온다. runner 나 테스트가 이걸 최상단에서
import 하면 `redis` 미설치 환경에서 수집 단계가 통째로 죽으므로, 주입은
호출자가 emit 인자로 넘기는 방식으로만 한다(runner.explore_subquestion 참고).
"""
import json
import logging
import uuid
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import redis.asyncio as aioredis

from core.config import get_settings
from models.research import STATUS_CANCELED

log = logging.getLogger(__name__)

# 종료 상태 → SSE 종료 이벤트 kind. 워커가 흘리는 종료 이벤트와 스트림
# 엔드포인트가 DB 를 보고 만드는 종료 프레임이 둘 다 terminal_event 를 거친다 —
# 연결 시점에 따라 모양이 갈리면(failed 를 done+status 로 받는 식) 프론트
# 분기가 조용히 빗나간다.
TERMINAL_KIND = {"completed": "done", "failed": "failed", STATUS_CANCELED: STATUS_CANCELED}

# 워커의 emit 경로에 있다. 응답 없는 Redis 는 예외가 아니라 무기한 대기라서
# publish 가 삼킬 기회조차 없이 잡이 소프트 리밋까지 멈춘다.
PUBLISH_TIMEOUT = 2.0


def channel(job_id: uuid.UUID | str) -> str:
    return f"research:{job_id}"


def terminal_event(status: str, error: str | None = None) -> dict:
    event = {"kind": TERMINAL_KIND[status], "status": status}
    if error:
        event["error"] = error[:200]
    return event


def _with_timeouts(url: str) -> str:
    """REDIS_URL 에 소켓 타임아웃을 얹는다. URL 에 이미 있는 값은 운영자 설정이라 그대로 둔다."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.setdefault("socket_connect_timeout", str(PUBLISH_TIMEOUT))
    query.setdefault("socket_timeout", str(PUBLISH_TIMEOUT))
    return urlunsplit(parts._replace(query=urlencode(query)))


async def publish(job_id: uuid.UUID | str, kind: str, payload: dict) -> None:
    """중계 실패가 리서치를 죽이면 안 된다 — 삼키고 로그만 남긴다.

    클라이언트를 호출마다 새로 만든다. 모듈 전역에 하나 두면 첫 이벤트루프에
    묶이는데, Celery 태스크는 잡마다 `asyncio.run(...)` 으로 루프를 새로 열고
    닫으므로 두 번째 잡부터 전부 `Event loop is closed` 로 죽는다.
    한 잡에 수십 번 도는 정도라 연결 비용보다 이쪽이 싸다.
    """
    cfg = get_settings()
    try:
        client = aioredis.from_url(_with_timeouts(cfg.REDIS_URL))
        try:
            await client.publish(
                channel(job_id), json.dumps({"kind": kind, **payload}, ensure_ascii=False)
            )
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:relay] publish 실패 job=%s kind=%s: %s", job_id, kind, e)


async def publish_terminal(job_id: uuid.UUID | str, status: str, error: str | None = None) -> None:
    event = terminal_event(status, error)
    await publish(job_id, event.pop("kind"), event)


async def subscribe(
    job_id: uuid.UUID | str, *, idle_timeout: float = 15.0,
) -> AsyncIterator[dict | None]:
    """이벤트 dict 를 yield 한다. 유휴 구간에서는 None 을 yield 한다.

    None 은 "아직 살아있다" 신호다. 엔드포인트가 이때 SSE 주석 프레임을 흘려
    끊긴 소켓을 감지하고, 잡이 이미 끝났는지도 확인한다. listen() 만 쓰면
    트래픽이 없는 동안 영원히 블록하므로 클라이언트가 조용히 끊겨도 알 방법이
    없다 — 아무것도 쓰지 않으니 broken pipe 조차 나지 않는다.
    """
    cfg = get_settings()
    client = aioredis.from_url(cfg.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel(job_id))
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=idle_timeout,
            )
            yield json.loads(message["data"]) if message else None
    finally:
        await pubsub.unsubscribe(channel(job_id))
        await pubsub.aclose()
        await client.aclose()
```
### 2.35 `runner.py` — 하위질문 하나의 탐색 루프

**책임.** 하위질문 하나를 "검색 → 근거 묶기 → 자기점검 → 부족하면 검색어를 바꿔 재검색"으로 상한까지 돈다. 근거 번호(`E1`, `E2` … — `citations.evidence_id`)는 `state.evidence` 를 소유한 이쪽이 붙인다. 진행은 `emit("search", …)`·`emit("critique", …)` 로 흘린다.

**왜 이렇게 짰나.**

- **`explore_fn`·`critique_fn`·`emit` 을 주입받는다.** Milvus·LLM·Redis 없이 루프 자체를 테스트하기 위해서다. 특히 `emit` 은 relay 를 import 하지 않으려는 목적도 있다(§2.34). 워커는 `emit=_emit`(→ `relay.publish`)을 넘기고, 테스트는 리스트에 쌓는 함수를 넘긴다.
- **같은 논문은 근거를 새로 만들지 않고 재사용한다.** 안 그러면 한 논문이 `E3` 와 `E17` 로 갈라져 인용칩이 같은 출처를 다른 번호로 가리킨다. `build_evidence` 는 묶기만 하고 id 를 비워 돌려준다.
- **상한(`max_evidence`)에 닿아도 `break` 가 아니라 `continue` 다.** 상한 뒤에 나오는 후보에도 "이미 있는 근거의 재사용"이 섞여 있고, 그건 총량을 늘리지 않는다.

**라이브·리뷰에서 바뀐 것.**

**① explore 직후 커밋 — 함정 18번.** 리뷰의 영역 경계 공백 점검에서 나온 잠복 결함이다. `explore()` 가 서지(`library_catalog`)를 조회하는 순간 SQLAlchemy 세션이 트랜잭션을 자동으로 열고, 커밋·롤백 전까지 닫지 않는다. 그 상태로 critic LLM 응답(수십 초, 혼잡하면 호출당 최대 120초)과 재검색 라운드를 기다리면 세션이 `idle in transaction` 으로 `library_catalog` 공유 잠금을 쥔다. 이때 FastAPI 를 재시작하면 lifespan 의 `ALTER TABLE library_catalog ADD COLUMN IF NOT EXISTS …` 가 — 컬럼이 이미 있어도 — 배타 잠금을 요청하며 기다리고, PostgreSQL 은 그 대기 뒤로 새 조회를 모두 줄 세운다. 검색·서지 조회·적재 쓰기가 한꺼번에 멈춘다. 그래서 `explore_fn` 이 돌아오자마자 `db.commit()` 으로 읽기 트랜잭션을 닫는다.

롤백이 아니라 커밋인 이유: 워커의 세션 팩토리는 `expire_on_commit=False` 라 커밋해도 이미 읽은 속성이 살아 있지만, 롤백은 설정과 무관하게 세션의 모든 인스턴스를 만료시킨다. async 세션에서 만료된 속성을 읽으면 지연 로드가 `MissingGreenlet` 으로 터진다. 기존 적재 단계(`stages.py`)가 이미 "읽고 닫고 → LLM → 다시 연다" 관례를 지키고 있었고, 새 워커가 그 관례를 깬 것이었다.

**② 하위질문 안의 근거 순서(`_rank_order`).** 처음엔 `evidence_ids` 가 채택 순서였다. 자기점검이 "시기 편중" 같은 이유로 부족하다고 해서 찾은 보완 근거는 첫 검색의 상위 논문보다 점수가 낮기 쉽고, 절에는 앞 5편만 실리므로 재검색의 성과가 보고서 본문에서 사라졌다. 점수만으로 정렬하지도 않는다 — 라운드마다 검색어가 달라 점수를 그대로 비교할 수 없다. 그래서 **라운드마다 새로 보탠 근거 중 1위는 앞자리를 보장**하고(`leaders`) 나머지는 `rank_score` 순이다.

**③ 하위질문별 청크(`link_chunks`·`_as_seen_by`).** 처음엔 재사용 근거가 처음 채택한 하위질문의 청크만 들고 있어, 다른 하위질문의 critic 발췌·절 요약·인용칩 호버가 엉뚱한 대목을 썼다. 이제 재사용이어도 이번 검색에서 매칭된 대목을 그 하위질문에 연결하고, critic 에는 그 하위질문이 본 청크만 넘긴다(청크 매핑 자체는 `citations.py`).

**④ 상한과 재검색.** 상한에 막혀 싣지 못한 후보를 `capped` 로 따로 센다 — 처음엔 상한 때문에 굶은 하위질문이 "근거를 찾지 못했다"(코퍼스 빈틈)로 보고됐다. 상한에 닿으면 새 근거가 생길 수 없으므로 재검색을 멈추고, 이미 시도한 검색어는 `_next_query` 가 건너뛴다(같은 검색은 같은 결과를 내 라운드만 태운다). **굶김 자체는 그대로다** — `max_evidence` 는 여전히 잡 전역 선착순이다. 하위질문별 예산은 절당 5편 상한과 함께 정할 제품 결정이라 이월했다(완료노트 §8).

**⑤ 판정 실패 표시를 옮긴다.** `subq.parse_failed = verdict.parse_failed` 가 없으면 자기점검이 전부 실패해도 보고서의 한계 섹션이 "한계 없음"으로 보인다. `critique` 이벤트에도 `parse_failed`·`capped` 를 실었다 — "모델이 충분하다고 판단"과 "판정을 못 받음"을 note 문자열 없이 가를 수 있어야 한다. 마지막 라운드 값으로 덮어써도 되는 이유는 코드 주석에 있다(판정 불가는 `sufficient` 로 떨어지고 재검색은 `insufficient` 일 때만 돌므로, 판정 불가가 난 라운드가 항상 마지막 라운드다).

**파일**: `app/services/research/runner.py` — 전체 170줄

```python
"""runner.py — 단계 오케스트레이션

각 단계는 ResearchState 를 받아 갱신한다. explore_fn·critique_fn 을 인자로
받는 이유는 Milvus·LLM 없이 루프 자체를 테스트하기 위해서다.

진행 중계도 같은 이유로 emit 인자로 주입받는다. `services.research.relay` 를
여기서 import 하면 relay 가 물고 있는 `redis` 가 이 모듈을 여는 모든 곳에
필요해지고, 미설치 환경에서는 테스트 수집 단계가 통째로 죽는다
(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).
"""
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from services.research.citations import build_evidence, chunks_for, evidence_id, link_chunks
from services.research.critic import Verdict
from services.research.critic import critique as _critique
from services.research.critic import should_recheck
from services.research.explorer import explore as _explore
from services.research.planner import query_key
from services.research.state import Evidence, HitRow, ResearchState, SubQuestion

log = logging.getLogger(__name__)

ExploreFn = Callable[..., Awaitable[tuple[list[HitRow], dict[str, dict]]]]
CritiqueFn = Callable[..., Awaitable[Verdict]]
EmitFn = Callable[[str, dict], Awaitable[None]]


async def _noop_emit(kind: str, payload: dict) -> None:
    return None


def _best_rank(hits: list[HitRow]) -> dict[str, float]:
    best: dict[str, float] = {}
    for h in hits:
        score = h.get("rank_score", h["score"])
        if score > best.get(h["book_id"], float("-inf")):
            best[h["book_id"]] = score
    return best


def _rank_order(ids: list[str], relevance: dict[str, float], leaders: list[str]) -> list[str]:
    """하위질문 안의 순위. 검색 라운드마다 새로 보탠 근거 중 1위는 앞자리를 보장하고,
    나머지는 rank_score 순이다.

    점수만으로 정렬하지 않는 이유: 라운드마다 검색어가 달라 점수를 그대로 비교할
    수 없고, 자기점검이 "시기 편중" 같은 이유로 부족하다고 해서 찾은 보완 근거는
    첫 검색의 상위 논문보다 점수가 낮기 쉽다. 그러면 절(앞 5편)에 끝내 실리지
    못해 재검색의 성과가 보고서 본문에서 사라진다.
    """
    seats = [e for e in leaders if e in ids]
    rest = sorted((e for e in ids if e not in seats),
                  key=lambda e: relevance.get(e, float("-inf")), reverse=True)
    return seats + rest


def _next_query(suggestions: list[str], tried: list[str]) -> str | None:
    """이미 시도한 검색어는 건너뛴다 — 같은 검색은 같은 결과를 내 라운드만 태운다."""
    seen = {query_key(q) for q in tried}
    for q in suggestions:
        if query_key(q) not in seen:
            return q
    return None


def _as_seen_by(ev: Evidence, subq: SubQuestion) -> Evidence:
    return Evidence(id=ev.id, cnts_id=ev.cnts_id, meta=ev.meta, chunks=chunks_for(ev, subq))


async def explore_subquestion(
    state: ResearchState,
    subq: SubQuestion,
    *,
    db: AsyncSession | None,
    explore_fn: ExploreFn = _explore,
    critique_fn: CritiqueFn = _critique,
    emit: EmitFn | None = None,
) -> SubQuestion:
    """한 하위질문을 탐색하고, 부족하면 쿼리를 바꿔 상한까지 재탐색한다."""
    emit = emit or _noop_emit
    params = state.params
    query = subq.text
    recheck = 0
    relevance: dict[str, float] = {}
    leaders: list[str] = []
    capped: set[str] = set()

    while True:
        subq.queries.append(query)
        hits, meta = await explore_fn(query, params=params, db=db)
        # 읽기 트랜잭션을 여기서 끝낸다. 이어지는 critic 은 LLM 을 수십 초 기다리는데,
        # 그동안 세션이 library_catalog 공유 잠금을 쥐고 있으면 FastAPI 기동 시
        # lifespan 의 ALTER TABLE library_catalog 가 막히고 그 뒤 모든 조회가 줄 선다.
        if db is not None:
            await db.commit()
        await emit("search", {
            "subq_idx": subq.idx, "query": query, "found": len(hits),
        })

        # 같은 논문이 여러 하위질문에서 나오면 근거를 새로 만들지 않고 재사용한다.
        # 안 그러면 한 논문이 E3 와 E17 로 갈라져 인용칩이 같은 출처를 다른
        # 번호로 가리킨다. 번호는 state.evidence 를 소유한 이쪽이 붙인다 —
        # build_evidence 는 묶기만 하고 id 를 비워 돌려준다.
        known_by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
        best = _best_rank(hits)
        before = set(subq.evidence_ids)
        linked: list[str] = []
        for cand in build_evidence(
            hits, meta, chunks_per_evidence=params["chunks_per_evidence"],
        ):
            eid = known_by_cnts.get(cand.cnts_id)
            if eid is None:
                # break 가 아니라 continue 다. 상한에 닿은 뒤에 나오는 후보 중에도
                # "이미 있는 근거의 재사용"이 섞여 있는데, 그건 총량을 늘리지 않는다.
                # break 로 끊으면 그 하위질문이 정당한 근거 링크를 잃는다.
                if len(state.evidence) >= params["max_evidence"]:
                    capped.add(cand.cnts_id)
                    continue
                eid = evidence_id(len(state.evidence))
                state.evidence[eid] = Evidence(id=eid, cnts_id=cand.cnts_id, meta=cand.meta)
                known_by_cnts[cand.cnts_id] = eid
            # 재사용이어도 이번 검색에서 매칭된 대목은 버리지 않는다 — 그 하위질문의
            # critic 발췌·절 요약·호버는 이 대목을 써야 한다.
            link_chunks(state.evidence[eid], subq, cand.chunks,
                        limit=params["chunks_per_evidence"])
            relevance[eid] = max(relevance.get(eid, float("-inf")), best[cand.cnts_id])
            if eid not in linked:
                linked.append(eid)

        fresh = [e for e in linked if e not in before]
        if fresh:
            leaders.append(fresh[0])
        subq.evidence_ids = _rank_order(subq.evidence_ids + fresh, relevance, leaders)
        subq.capped = len(capped)

        verdict = await critique_fn(
            subq, [_as_seen_by(state.evidence[e], subq) for e in subq.evidence_ids],
            params=params,
        )
        subq.verdict = verdict.verdict
        subq.note = verdict.note
        # 판정을 못 받았다는 표시를 여기서 옮기지 않으면 보고서까지 닿지 않는다 —
        # synthesizer.build_limitations 는 subq.parse_failed 만 보고 "자동 점검을
        # 완료하지 못한 하위질문"을 센다. 자기점검이 전부 실패해도 보고서가
        # "한계 없음"으로 보이는 게 정확히 critic 의 parse_failed 가 막으려던 실패다.
        #
        # 마지막 라운드 값으로 덮어써도 된다(OR 누적이 필요 없다): 판정 불가는
        # verdict="sufficient" 로 떨어지고 should_recheck 는 "insufficient" 일 때만
        # True 이므로, 판정 불가가 난 라운드가 항상 마지막 라운드다.
        subq.parse_failed = verdict.parse_failed
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
        })

        if not should_recheck(subq, recheck_count=recheck, max_recheck=params["max_recheck"]):
            break
        # 상한에 닿으면 새 근거가 생길 수 없다 — 재검색은 검색·LLM 호출만 태운다.
        if len(state.evidence) >= params["max_evidence"]:
            break
        next_query = _next_query(verdict.new_queries, subq.queries)
        if next_query is None:
            break
        query = next_query
        recheck += 1

    return subq
```
### 2.36 `research_tasks.py` — Celery 태스크 세 개

**책임.** `plan_deep_research`(계획만 세우고 승인 대기로 멈춤) · `run_deep_research`(탐색·체크포인트·종합) · `reap_stale_research`(멈춘 잡 회수). 이 파일은 **`app/workers/` 에서 asyncio 를 직접 쓰는 첫 파일**이다 — 기존 사용은 0건이었다. 적재 단계도 `stages.run_async` 로 LLM 코루틴을 돌리지만 호출마다 새 루프를 열고 DB 는 동기 세션이다. 워커에서 async DB 세션을 쓰는 것은 이 파일이 처음이라 루프·세션·상태 쓰기 규칙을 여기서 못박는다. 리뷰 반영에서 이 챕터의 소스 파일 중 가장 크게 바뀐 파일이고, 머지 전 리뷰의 high 5건이 전부 여기서 나왔다.

**① 이벤트 루프 — 태스크마다 `asyncio.run` 한 번, 잡 단위 엔진, `dispose`.**

초안(plan Task 10 첫 판)은 동기 세션으로 잡을 쓰면서 단계마다 `asyncio.run` 을 불렀고, 탐색에는 세션을 넘기지 않았다(`db=None`). 탐색에 async 세션을 넘기려면 `db/postgres.py` 의 `AsyncSessionLocal` 을 집게 되는데, Task 10 재설계(`46a4cfc`)가 "단계마다 `asyncio.run` + 풀링 async 엔진" 조합을 두 번째 잡부터 깨지는 결함으로 짚었다. 그 엔진은 `pool_size=10` 이고 FastAPI 의 장수 루프 하나를 전제한다. 워커에서는 풀이 **닫힌 루프에 묶인 asyncpg 커넥션을 그대로 들고 있다가 다음 잡에 건넨다** → `attached to a different loop`. 첫 잡은 성공하므로 리허설을 통과하고 본 시연에서 터지는 종류다. 재설계는 다음 셋으로 바꿨다.

- `_run_job` — 잡 전체를 `asyncio.run` 한 번으로 돈다.
- `_job_engine` — 잡마다 엔진을 새로 만든다(`pool_size=5, max_overflow=0, pool_pre_ping=True`). NullPool 이 아닌 이유: 잡 안에서는 루프가 하나뿐이라 풀이 안전하고, 몇 분 동안 수십 번 질의하는데 매번 새로 접속할 이유가 없다.
- `finally: await engine.dispose()` — 루프가 죽기 전에 커넥션을 닫는다. 빠뜨리면 다음 잡이 남은 커넥션을 만난다.

라이브 검증 Step 8 이 이걸 본 자리다. **첫 잡만 돌려보고 넘어가면 이 결함은 안 보인다** — 같은 워커 프로세스(`ForkPoolWorker-2`)가 잡 2개의 계획·실행(루프 4회)을 처리했고 `attached to a different loop` 가 없었다(완료노트 §2). 리뷰 반영 이전 코드(`b6360b8`)로 본 것이지만, 태스크당 `asyncio.run` 1회·잡 단위 엔진·`dispose` 구조는 그때와 같다. 같은 이유로 API 의 하트비트는 반대로 풀링 엔진을 쓴다(§2.37) — 갈리는 기준은 이벤트 루프의 수명이다.

**② 상태 쓰기는 전부 조건부 UPDATE — 취소 덮어쓰기(high)의 원인과 수정.**

리뷰 전 워커는 ORM 객체에 대입하고 커밋했다(`job.status = "completed"`, 계획 단계의 `job.status = "awaiting_approval"`). 커밋이 내보내는 문장은 `UPDATE research_jobs SET status=… WHERE id=…` 이고 **이전 상태 조건이 없다.** 그 사이 API 가 찍은 `canceled` 는 그대로 덮인다. 취소 확인(`_is_cancelled`)은 `select(ResearchJob.status)` 로 컬럼만 읽었으므로 메모리의 `job` 객체는 취소를 모른 채 `running` 으로 남아 있었고, 그 확인도 하위질문 루프 머리 한 곳뿐이었다. 결과는 세 갈래였다.

- 마지막 하위질문·종합 중 취소 → 워커가 끝까지 돌고 `completed` 로 덮는다. 새로고침하면 취소한 잡이 보고서와 함께 나온다.
- 종합 실패였다면 `failed` 로 덮이고, 그러면 `POST /retry` 가 통과해 취소한 잡이 다시 산다.
- 계획 중 취소 → `awaiting_approval` 로 덮여 승인·실행까지 가능해진다.

리뷰는 8개 영역으로 나눠 돌았는데 **서로 다른 다섯 영역(API·모델, 워커, 테스트, 문서·스코프, 영역 간 계약)이 같은 원인을 독립적으로 high 로 짚었다.** 라이브 Step 9 의 취소 검증은 통과했었다 — 하위질문 0 을 탐색하는 중에 취소해서 루프 머리의 확인에 걸렸을 뿐, 덮어쓰는 구간을 지나지 않았다.

수정은 규칙 하나다 — **워커는 job ORM 객체에 대입하지 않는다. 모든 전이는 `_transition` 을 거친다**(모듈 docstring). 기대한 이전 상태를 `WHERE` 에 걸고, 0행이면 누가 먼저 바꾼 것이다.

```python
    res = await db.execute(
        update(ResearchJob)
        .where(ResearchJob.id == job_id, ResearchJob.status.in_(expect))
        .values(**values)
    )
```

- `_claim`(선점)·`_end_failed`·체크포인트·완료 전이·계획 완료 전이가 모두 이 위에 있다. 계획 단계는 `expect=("planning",)`, 실행 단계는 `expect=("running",)`.
- 선점이 0행이면 `skipped`(④), 나머지 전이가 0행이면 `_stopped` 로 간다. 현재 상태를 다시 읽어 종료 상태면 종료 이벤트를 내고, 결과를 버리고 멈춘다. 대개 취소지만 드물게 회수(⑦)다.
- 잡의 필드는 선점 직후 지역 변수로 꺼내 둔다(`stage, snapshot = job.stage, job.state_snapshot` 등). 그 뒤로는 job 객체를 다시 읽지 않으므로, 하위질문 예외에서 롤백이 인스턴스를 만료시켜도 문제가 없다(⑧).
- `_close_orphan_steps` 도 조건부다. 잡이 종료 상태일 때만 `running` step 을 닫는다 — 회수 뒤 재시도한 새 실행의 step 일 수 있기 때문이다.

**③ 취소를 보는 네 곳.**

| # | 지점 | 방식 | 그 구간을 고정하는 테스트(§2.43) |
|---|---|---|---|
| 1 | 하위질문 루프 머리 | `_is_cancelled` 로 읽고 `_stopped` | `test_cancel_before_first_subquestion_stops_everything` |
| 2 | 종합 직전 (새 탐색·스냅샷 재개 공통) | `_is_cancelled` | `test_resumed_job_canceled_before_synthesis` |
| 3 | 종합 안, 절마다 LLM 호출 직전 | `synthesize(state, should_stop=…)` → `SynthesisCanceled` | `test_cancel_between_sections_stops_synthesis` |
| 4 | 모든 상태 쓰기 | 조건부 전이가 0행 → `_stopped` | `test_cancel_during_last_subquestion_skips_synthesis`(체크포인트) · `test_cancel_after_synthesis_keeps_canceled`(완료) · `test_cancel_during_planning_is_not_revived`(계획) |

1~3 은 "다음 비싼 일을 시작하기 전에 멈춘다"이고, 4 는 1~3 을 모두 지나친 취소도 뒤집히지 않게 하는 마지막 그물이다. 마지막 하위질문 탐색 중에 들어온 취소는 1 을 이미 지났으므로 4 의 체크포인트 전이에서 걸린다 — 이때 `stage`·`state_snapshot` 도 쓰이지 않는다(취소된 잡에 체크포인트를 남기지 않는다). **진행 중인 LLM 호출은 끊지 않는다.** 취소 API 는 즉시 `canceled` 를 돌려주지만 워커는 진행 중인 하위질문이나 절 호출을 마저 끝낸 뒤 멈추므로, 취소 검증은 `status` 가 아니라 "잠시 뒤 step 이 닫혔는가, 이후 step 이 없는가"로 본다(완료노트 §6).

`_current_status` 는 읽고 곧바로 커밋한다. 이 조회는 LLM 호출 직전(하위질문 사이·절 사이)에 돌기 때문에, 트랜잭션을 연 채 LLM 으로 가면 §2.35 ① 과 같은 잠금 문제가 된다.

**④ 선점 — Celery 는 at-least-once 다.** `task_acks_late=True` 라 ack 전에 워커가 죽으면 같은 메시지가 다시 배달된다(§2.33). 무조건 `status="running"` 을 대입하면 같은 잡이 두 벌 돌아 step 이 중복되고 LLM 비용이 두 배가 된다. `_claim(allowed=RUNNABLE_STATUSES, to="running")` 은 `approved`·`queued` 만 잡는다 — 이미 `running` 이면 재배달이므로 `skipped` 로 돌아선다. 이 상수는 `models/research.py` 에 있고 API 가 같은 이름으로 쓴다. 초안에서 approve 가 상태를 바꾸지 않아 워커의 선점이 늘 0행을 잡은 결함(plan Task 10 (1))을 문자열 맞추기가 아니라 상수 공유로 막은 것이다. `_next_seq` 가 `max(seq)+1` 에서 이어 쓰는 이유도 같은 맥락이다 — 재시도·재개는 정상 경로인데 1 부터 다시 쓰면 `uq_research_steps_job_seq` 위반으로 복구 기능 자체가 죽는다.

**⑤ 전멸과 빈 계획.** 리뷰 전에는 하위질문이 전부 예외로 끝나도 무조건 체크포인트를 쓰고 종합으로 갔다. 종합은 실패한 하위질문을 빼므로 절 0개 보고서가 `completed` 로 저장됐고, `completed` 는 retry 가 409 라 복구할 길이 없었다. 수동으로 `failed` 로 돌려 재시도해도 전부 실패한 스냅샷에서 종합만 다시 했다. 지금은:

- `_wiped_out` — 모든 하위질문이 실패했고 **건진 근거도 없을 때만** 전멸이다. 근거를 모은 채 실패한 하위질문은 synthesizer 가 그 근거로 절을 쓰고 한계에 "오류로 중단"을 적는다 — 잡째 실패시키면 실재하는 근거를 버린다.
- 전멸이면 잡 `failed`, **체크포인트를 쓰지 않는다** → retry 가 탐색부터 다시 돈다.
- 가드 이전에 저장된 전멸 스냅샷(`stage=explored`)으로 재개하면 버리고 탐색부터 다시 한다.
- 계획이 빈 잡은 루프 전에 `EMPTY_PLAN_ERROR` 로 끝낸다. `all([])` 은 참이라, 여기서 끊지 않으면 "탐색이 오류로 실패"로 남아 운영자가 검색 장애로 오진한다.

**⑥ 체크포인트와 재개.** 탐색이 끝나면 조건부 전이로 `stage="explored"` 와 `state_snapshot` 을 쓴다. 여기까지가 비싼 구간이고 종합은 다시 돌려도 싸다. 종합이 실패하면 `_end_failed` 는 `stage`·`state_snapshot` 을 건드리지 않으므로, `POST /retry`(§2.37)가 `queued` 로 돌리면 워커가 `stage == "explored"` 분기로 탐색을 건너뛰고 종합부터 한다. `_stage()` 의 `assert` 는 `JOB_STAGES` 를 실제로 강제하는 유일한 지점이다 — stage 오타는 재개 분기를 예외 없이 조용히 빗나가게 만든다(`_step` 의 `STEP_KINDS` assert 도 같은 역할). **재개 경로는 라이브에서 한 번도 돌지 않았다** — 종합 실패가 자연발생하지 않았고 억지로 실패시키지 않았다. 체인의 세 구간(종합 실패가 체크포인트를 남김 → retry 가 그대로 두고 `queued` 로 → 워커가 탐색 없이 종합만)은 단위 테스트로만 덮었다(완료노트 §8).

**⑦ 시간 상한 — 네 겹.**

| 시각 | 무엇이 | 하는 일 |
|---|---|---|
| 25분 | 잡 자체 데드라인 `JOB_DEADLINE = SOFT_LIMIT - 300` | await 지점에서 끊고 조건부로 `failed`(`시간 상한 초과 — 워커를 회수했다`)·열린 step `failed`·SSE `failed` |
| 30분 | Celery 소프트 리밋 `SOFT_LIMIT` | 백스톱 — 데드라인이 못 끊는 동기 구간용. `asyncio.run` 밖으로 튄 것은 `_run_job` 이 새 루프·새 엔진으로 같은 정리 |
| 35분 | Celery 하드 리밋 `HARD_LIMIT` | 프로세스를 죽인다 — 아무 정리도 돌지 않는다 |
| 45분 | 회수 `STALE_MINUTES` (beat 10분 주기) | 아직 `planning`·`running` 인 잡은 워커가 죽은 것 → `failed`(`stale — 워커 응답 없음`) |

첫 구현은 소프트 리밋 하나에 기댔고 코루틴 안에 `except SoftTimeLimitExceeded` 를 두었다. 리뷰가 그 처리가 주 시나리오에서 돌지 않는다는 것을 재현했다(함정 19번).

- 소프트 리밋은 시그널 핸들러가 메인 스레드에서 예외를 던지는 방식이다. 잡은 대부분의 시간을 LLM 응답을 await 하며 보내는데, 그동안 메인 스레드는 이벤트 루프의 `select` 안에 있다. 예외는 코루틴이 아니라 `asyncio.run` 밖으로 튀고, 코루틴에는 `CancelledError` 만 들어가 `except SoftTimeLimitExceeded` 쪽 정리(잡·step 을 `failed` 로)가 돌지 않는다.
- 동기 구간에 떨어져도 `SoftTimeLimitExceeded` 는 `Exception` 의 하위라, 동기 리랭크 도중이면 `pipeline.py` 의 리랭크 폴백 `except Exception` 이 "리랭킹 실패, 벡터 점수 유지" 경고 한 줄로 삼켰다. 신호는 한 번뿐이라 잡은 계속 돌다 하드 리밋에 죽는다.

결과는 잡·step 이 `running` 에 남고 SSE 는 ping 만 보내다, 회수기가 와서야 `stale` 로 — 시간 초과를 워커 사망으로 오진한 기록으로 — 끝나는 것이었다. 수정은 **시간 상한을 Celery 에 맡기지 않고 코루틴 안에 두는 것**이다.

```python
async def _within_deadline(body: Callable[[str], Awaitable[dict]], job_id: str) -> dict:
    deadline = asyncio.timeout(JOB_DEADLINE)
    try:
        async with deadline:
            return await body(job_id)
    except TimeoutError:
        if not deadline.expired():
            raise
        return await _mark_timed_out(job_id)
```

`asyncio.timeout`(Python 3.11, 이미지가 3.11)은 await 지점에 `CancelledError` 를 넣는다. `CancelledError` 는 `BaseException` 이라 하위 계층의 `except Exception` 에 걸리지 않고 위로 올라온다. `deadline.expired()` 로 **우리 데드라인이 낸 `TimeoutError` 인지** 가린다 — 본문 안에서 올라온 다른 `TimeoutError` 를 시간 상한으로 오진하지 않는다. 여유는 리뷰가 "동기 구간 최대치인 임베딩+리랭크 200쌍+DB 쓰기보다 크게, 예: 180~300초"로 제안했고 코드는 300초다 — 동기 구간은 끊을 수 없어 취소가 그 구간이 끝난 다음 await 에서 걸리기 때문이다. 리랭크 폴백은 허용 목록(`RuntimeError`·`OSError`·`ValueError`·`ImportError`)으로 좁혔다(`pipeline.py`, §2.18). 코루틴 안의 `except SoftTimeLimitExceeded: raise` 는 그대로 남아 있다 — 동기 구간에서 코루틴 안으로 떨어진 경우 `except Exception` 보다 먼저 잡아 위로 보내야 하기 때문이다.

`_mark_timed_out` 은 `stage` 를 건드리지 않는다. 종합에서 시간을 넘긴 잡은 retry 가 스냅샷에서 이어받을 수 있어야 한다. 반대로 **탐색 중에 넘긴 잡은 하위질문 단위 체크포인트가 없어 retry 가 탐색을 처음부터 다시 돈다** — 같은 파라미터면 같은 초과를 반복할 수 있다. 기본 파라미터(하위질문 6·재탐색 3)가 25분 안에 드는지는 아직 재지 않았다(라이브는 축소 파라미터로 실행 34~89초였다, 완료노트 §2).

**회수기**(`reap_stale_research`).

- 임계는 처음 30분이었다. 소프트 리밋과 같고 하드 리밋(35분)보다 짧아서, 소프트 리밋이 삼켜진 채 아직 살아서 쓰는 워커의 잡을 회수할 수 있었다. 그 뒤 사용자가 retry 하면 옛 실행과 새 실행이 같은 잡에서 부딪힌다. 45분으로 올렸다(`test_stale_threshold_exceeds_hard_limit` 가 `STALE_MINUTES * 60 > HARD_LIMIT` 를 고정).
- 회수한 잡의 `running` step 을 **같은 문장(CTE)에서** 닫는다. 따로 두면 잡은 `failed` 인데 마지막 step 은 자기 `updated_at` 기준으로 한참 더 `running` 으로 보인다. step 자체의 `updated_at` 기준 회수도 두 번째 문장으로 남겼다.
- `coalesce(started_at, created_at)` — `started_at` 이 NULL 이면 비교가 NULL 이라 조건이 참이 되지 않아 영원히 회수되지 않는다.
- `approved`·`queued` 는 회수하지 않는다. 아직 워커가 집지 않은 정상 대기 상태다. 대신 브로커 메시지를 잃은 채 거기 묶인 잡은 사람이 찾아 취소해야 한다(런북 §8).
- 회수는 동기 세션(`SyncSessionLocal`)이다. 루프가 필요 없는 SQL 두 문장이다.

**⑧ 예외 — 롤백한 뒤 기록하고, 가드 밖은 새 세션으로.**

- **하위질문 예외는 `db.rollback()` 부터.** `explore` 는 워커와 같은 세션으로 서지를 조회한다. 거기서 DB 오류(연결 리셋 등)가 나면 트랜잭션이 깨진 상태가 되고, 롤백 없이 `_finish` 로 기록하면 핸들러 안에서 `InFailedSQLTransaction`·`PendingRollbackError` 로 다시 터져 태스크째 죽었다. 잡은 `running` 에 묶이고 앞서 성공한 하위질문 탐색까지 잃었다. spec §6 의 "Milvus·DB 오류 → 해당 step만 `failed`"는 롤백을 넣은 뒤에야 성립했다.
- **`_step` 이 ORM 객체가 아니라 id 를 돌려주는 이유**가 이것이다. 롤백은 세션의 모든 인스턴스를 만료시키고, 만료된 속성을 async 세션에서 읽으면 `MissingGreenlet` 이 난다. step 행은 `insert … returning` 으로 id 만 받는다.
- **부분 실패는 전체 실패가 아니다.** 실패한 하위질문은 `subq.failed = True` 로 표시하고 나머지를 계속한다. 이 표시가 있어야 보고서가 그 하위질문을 "근거 없음"(연구 결과)이 아니라 "오류로 확인 못함"(시스템 장애)으로 쓴다.
- **가드 밖 예외.** 스냅샷 복원·수록 범위 조회·step 기록처럼 하위질문 `try` 밖에서 난 예외로 태스크만 죽으면, 잡은 `running` 에 묶여 SSE 는 ping 만 보내고 사용자는 retry 도 못 한 채 회수기(45분)를 기다린다. 바깥 `except Exception` 이 `_fail_open_job` 으로 **새 세션을 열어** 조건부로 `failed`·열린 step 정리·SSE `failed` 를 한다. 원래 세션은 깨졌을 수 있어서 새 세션이다. 바깥에서도 `except SoftTimeLimitExceeded: raise` 가 `except Exception` 보다 앞에 온다.

**⑨ 수록 범위는 매 실행 잰다.** `_corpus_range` 는 `library_catalog` 의 논문 발행연도 범위와 편수를 실행마다 조회해 보고서 서론에 싣는다. 인덱싱이 계속 도는 중이라 "2002~2009" 같은 고정 문구를 박으면 곧 거짓이 된다.

**파일**: `app/workers/research_tasks.py` — 전체 514줄

```python
"""research_tasks.py — 딥리서치 Celery 태스크

동기 워커에서 async 파이프라인을 돌린다. 이 파일이 이 코드베이스에서 워커가
async 코드를 부르는 첫 자리다(`app/workers/` 에 기존 asyncio 사용 0건). 그래서
루프와 세션을 다루는 규칙을 여기서 못박아 둔다 — 아래 _job_engine 주석.

상태 쓰기 규칙: 워커는 job ORM 객체에 대입하지 않는다. 모든 상태 전이는
_transition 의 조건부 UPDATE 로만 한다. 취소는 API 프로세스가 찍으므로, 조건 없이
쓰면 워커의 마지막 쓰기가 취소를 덮어 취소한 잡이 completed 로 되살아난다.
"""
import asyncio
import datetime as _dt
import logging
import uuid
from collections.abc import Awaitable, Callable

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import insert, select, text as sa_text, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.research import (
    JOB_STAGES, RUNNABLE_STATUSES, STATUS_CANCELED, STEP_KINDS, TERMINAL_STATUSES,
    ResearchJob, ResearchStep,
)
from services.research.relay import publish, publish_terminal
from services.research.runner import explore_subquestion
from services.research.state import (
    ResearchState, SubQuestion, merge_params, restore_state, snapshot_state,
)
from services.research.synthesizer import SynthesisCanceled, synthesize
from workers.celery_app import celery_app

log = logging.getLogger(__name__)

# 5~7분이 설계값이고 종합까지 10분을 안 넘긴다. 30분이면 멈춘 것이다.
# 상한이 없으면 응답 없는 LLM 호출 하나가 워커 슬롯을 영구 점유한다.
SOFT_LIMIT = 1800
HARD_LIMIT = 2100

# 잡 본문의 자체 상한. 소프트 리밋 신호는 LLM 응답을 await 하는 동안(메인 스레드가
# 이벤트 루프의 select 안) 오면 코루틴이 아니라 asyncio.run 밖으로 튀어나가, 코루틴
# 안의 정리 코드가 하나도 돌지 않는다. 데드라인은 await 지점에서 CancelledError 로
# 끊으므로 확실히 잡힌다 — 소프트 리밋은 데드라인이 못 끊은 경우의 백스톱이다.
JOB_DEADLINE = SOFT_LIMIT - 300

# 하드 리밋보다 길어야 한다. 짧으면 아직 살아서 쓰고 있는 워커의 잡을 회수하고,
# 그 뒤 retry 한 새 실행과 옛 실행이 같은 잡에서 부딪힌다.
STALE_MINUTES = 45

TIMEOUT_ERROR = "시간 상한 초과 — 워커를 회수했다"
EMPTY_PLAN_ERROR = "계획에 하위질문이 없어 탐색하지 않았다 — 새 잡을 만든다"
_IN_FLIGHT = ("planning", "running")


def _job_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """잡 하나짜리 async 엔진.

    db/postgres.py 의 AsyncSessionLocal 을 쓰면 안 된다. 그건 pool_size=10 인
    풀링 엔진이고 FastAPI 의 장수 루프 하나를 전제한다. Celery 는 잡마다
    asyncio.run 으로 루프를 새로 만들고 닫는데, 풀은 닫힌 루프에 묶인
    asyncpg 커넥션을 그대로 들고 있다가 다음 잡에 건네준다 →
    "attached to a different loop". 첫 잡은 성공하므로 리허설을 통과한다.

    NullPool 대신 잡 단위 엔진을 쓰는 이유: 잡 안에서는 루프가 하나뿐이라
    풀이 안전하고, 5~7분 동안 수십 번 질의하는데 매번 새로 접속할 이유가 없다.
    끝에 dispose() 로 루프가 죽기 전에 커넥션을 정리한다.
    """
    cfg = get_settings()
    engine = create_async_engine(
        cfg.DATABASE_URL, pool_size=5, max_overflow=0, pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _job_uuid(job_id: str) -> uuid.UUID:
    """Celery 는 job_id 를 문자열로만 실어 나른다 — PK 타입으로 되돌린다.

    research_jobs.id 는 UUID(as_uuid=True) 라 문자열을 그대로 넘기면 identity
    map 키가 str 과 UUID 로 갈려 같은 잡을 두 객체로 들고 있게 되고, 드라이버
    쪽 변환에 기대는 부분도 생긴다. 경계에서 한 번 변환하고 안쪽은 UUID 만 쓴다.
    """
    return uuid.UUID(str(job_id))


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _stage(stage: str) -> str:
    """JOB_STAGES 를 실제로 강제하는 유일한 지점.

    stage 오타는 재개 분기(stage == "explored")를 조용히 빗나가게 만든다 —
    예외도 안 나고 그냥 탐색을 처음부터 다시 돌 뿐이라 알아채기 어렵다.
    """
    assert stage in JOB_STAGES, f"알 수 없는 stage: {stage}"
    return stage


async def _next_seq(db: AsyncSession, job_id: uuid.UUID) -> int:
    """이어붙일 seq. 1 부터 다시 시작하면 uq_research_steps_job_seq 를 위반한다.

    재시도·재개는 정상 경로다(워커 사망 복구, 종합만 재실행). 그때마다
    IntegrityError 로 죽으면 복구 기능 자체가 동작하지 않는다.
    """
    row = await db.execute(sa_text(
        "SELECT coalesce(max(seq), -1) + 1 FROM research_steps WHERE job_id = :j"
    ), {"j": job_id})
    return int(row.scalar_one())


async def _step(
    db: AsyncSession, job_id: uuid.UUID, seq: int, kind: str, title: str, *,
    subq_idx: int | None = None, detail: str | None = None,
) -> int:
    """step 을 열고 id 를 돌려준다.

    ORM 객체가 아니라 id 를 들고 다니는 이유: 예외 핸들러는 rollback 부터 하는데,
    rollback 은 세션의 모든 인스턴스를 만료시켜 그 뒤 속성 접근이 async 세션에서
    MissingGreenlet 으로 터진다.
    """
    # STEP_KINDS 를 실제로 강제하는 유일한 지점. 상수만 정의하고 아무 데서도
    # 쓰지 않으면 장식이 되고, 오타난 kind 가 프론트 분기를 조용히 빗나간다.
    assert kind in STEP_KINDS, f"알 수 없는 kind: {kind}"
    step_id = (await db.execute(
        insert(ResearchStep).values(
            job_id=job_id, seq=seq, kind=kind, title=title,
            subq_idx=subq_idx, detail=detail, status="running",
        ).returning(ResearchStep.id)
    )).scalar_one()
    await db.commit()
    return step_id


async def _finish(db: AsyncSession, step_id: int, status: str, result: dict | None = None) -> None:
    await db.execute(
        update(ResearchStep).where(ResearchStep.id == step_id)
        .values(status=status, result=result or {}, finished_at=_now())
    )
    await db.commit()


async def _corpus_range(db: AsyncSession) -> dict:
    """실행 시점의 논문 수록 범위.

    인덱싱이 계속 도는 중이라 범위가 매주 달라진다. 보고서에 "2002~2009"
    같은 고정 문구를 박으면 곧 거짓말이 된다 — 매 실행마다 잰다.
    """
    row = (await db.execute(sa_text(
        "SELECT min(substring(pub_date, 1, 4)), max(substring(pub_date, 1, 4)), count(*) "
        "FROM library_catalog WHERE doc_type = 'paper' AND is_embedded"
    ))).first()
    return {"from": row[0], "to": row[1], "n_papers": row[2]}


async def _transition(
    db: AsyncSession, job_id: uuid.UUID, *, expect: tuple[str, ...], **values: object,
) -> bool:
    """조건부 상태 전이. 잡이 기대한 상태가 아니면(대개 취소) 아무것도 안 쓰고 False."""
    res = await db.execute(
        update(ResearchJob)
        .where(ResearchJob.id == job_id, ResearchJob.status.in_(expect))
        .values(**values)
    )
    await db.commit()
    return res.rowcount == 1


async def _claim(db: AsyncSession, job_id: uuid.UUID, *, allowed: tuple[str, ...], to: str) -> bool:
    """조건부 선점. 못 잡으면 False.

    Celery 는 at-least-once 다 — 워커가 ack 전에 죽으면 같은 잡이 다시 배달된다.
    무조건 status="running" 을 대입하면 그때 같은 잡이 두 벌 돌아 step 이 중복되고
    LLM 비용이 두 배가 되며, 두 실행이 같은 job 행을 서로 덮어쓴다.
    """
    return await _transition(db, job_id, expect=allowed, status=to, started_at=_now())


async def _current_status(db: AsyncSession, job_id: uuid.UUID) -> str | None:
    """DB 의 현재 상태. 읽고 바로 트랜잭션을 닫는다.

    이 조회는 LLM 호출 직전(절 사이·하위질문 사이)에 돈다. 트랜잭션을 열어 둔 채
    LLM 을 기다리면 그동안 잡은 잠금이 FastAPI 기동의 ALTER TABLE 을 막는다.
    """
    res = await db.execute(select(ResearchJob.status).where(ResearchJob.id == job_id))
    status = res.scalar_one_or_none()
    await db.commit()
    return status


async def _is_cancelled(db: AsyncSession, job_id: uuid.UUID) -> bool:
    return await _current_status(db, job_id) == STATUS_CANCELED


async def _stopped(db: AsyncSession, job_id: uuid.UUID) -> dict:
    """누가 먼저 상태를 바꿨다(대개 취소, 드물게 회수). 결과를 버리고 멈춘다."""
    status = await _current_status(db, job_id)
    log.info("[research] 잡 상태가 바뀌어 멈춘다 job=%s status=%s", job_id, status)
    if status in TERMINAL_STATUSES:
        await publish_terminal(job_id, status)
    return {"job_id": str(job_id), "status": status}


async def _end_failed(
    db: AsyncSession, job_id: uuid.UUID, error: str, *, expect: tuple[str, ...] = ("running",),
) -> dict:
    """stage·state_snapshot 은 건드리지 않는다 — retry 가 거기서 이어받는다."""
    if not await _transition(db, job_id, expect=expect, status="failed",
                             last_error=error[:1000], finished_at=_now()):
        return await _stopped(db, job_id)
    await publish_terminal(job_id, "failed", error)
    return {"job_id": str(job_id), "status": "failed"}


async def _close_orphan_steps(db: AsyncSession, job_id: uuid.UUID, error: str) -> None:
    """끝난 잡에 running 으로 남은 step 을 닫는다.

    잡이 아직 진행 중이면 건드리지 않는다 — 회수 뒤 retry 한 새 실행의 step 일 수 있다.
    """
    await db.execute(
        update(ResearchStep)
        .where(
            ResearchStep.job_id == job_id,
            ResearchStep.status == "running",
            select(ResearchJob.id).where(
                ResearchJob.id == job_id, ResearchJob.status.in_(TERMINAL_STATUSES),
            ).exists(),
        )
        .values(status="failed", result={"error": error[:500]}, finished_at=_now())
    )
    await db.commit()


async def _fail_open_job(
    Session: async_sessionmaker[AsyncSession], job_id: uuid.UUID, error: str,
) -> str | None:
    """새 세션으로 진행 중인 잡을 실패로 떨어뜨린다 — 원래 세션은 깨졌을 수 있다."""
    async with Session() as db:
        failed = await _transition(db, job_id, expect=_IN_FLIGHT, status="failed",
                                   last_error=error[:1000], finished_at=_now())
        await _close_orphan_steps(db, job_id, error)
        status = await _current_status(db, job_id)
    if failed:
        await publish_terminal(job_id, "failed", error)
    return status


async def _mark_timed_out(job_id: str) -> dict:
    """stage 는 건드리지 않는다 — 탐색까지 끝낸 뒤 종합에서 시간을 넘긴 잡은
    재시도가 스냅샷에서 이어받을 수 있어야 한다."""
    jid = _job_uuid(job_id)
    log.error("[research] 시간 상한 초과 job=%s", jid)
    engine, Session = _job_engine()
    try:
        status = await _fail_open_job(Session, jid, TIMEOUT_ERROR)
    finally:
        await engine.dispose()
    return {"job_id": str(jid), "status": status}


def _wiped_out(state: ResearchState) -> bool:
    """모든 하위질문이 오류로 끝났고 건진 근거도 없다 — 연구 결과가 아니라 장애다.

    근거를 하나라도 모은 채 실패한 하위질문은 전멸로 치지 않는다. synthesizer 가 그
    근거로 절을 쓰고 한계에 "오류로 중단"을 적는다 — 잡째 실패시키면 실재하는 근거를 버린다.
    """
    return all(sq.failed and not sq.evidence_ids for sq in state.subquestions)


async def _within_deadline(body: Callable[[str], Awaitable[dict]], job_id: str) -> dict:
    deadline = asyncio.timeout(JOB_DEADLINE)
    try:
        async with deadline:
            return await body(job_id)
    except TimeoutError:
        if not deadline.expired():
            raise
        return await _mark_timed_out(job_id)


def _run_job(body: Callable[[str], Awaitable[dict]], job_id: str) -> dict:
    """잡 전체를 이벤트 루프 하나로 돌린다. 단계마다 asyncio.run 을 부르지 않는
    이유는 _job_engine 주석에 있다."""
    try:
        return asyncio.run(_within_deadline(body, job_id))
    except SoftTimeLimitExceeded:
        # 루프가 이미 닫혔다 — 정리는 새 루프·새 엔진으로 한다
        return asyncio.run(_mark_timed_out(job_id))


@celery_app.task(name="tasks.plan_deep_research", queue=get_settings().RESEARCH_PLAN_QUEUE,
                 soft_time_limit=SOFT_LIMIT, time_limit=HARD_LIMIT)
def plan_deep_research(job_id: str) -> dict:
    """계획만 세우고 승인 대기 상태로 멈춘다."""
    return _run_job(_plan_deep_research, job_id)


async def _plan_deep_research(job_id: str) -> dict:
    from services.research.planner import make_plan

    jid = _job_uuid(job_id)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            if not await _claim(db, jid, allowed=("created",), to="planning"):
                log.warning("[research] 이미 계획 중이거나 계획된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}

            job = await db.get(ResearchJob, jid)
            question, params = job.question, merge_params(job.params or {})
            seq = await _next_seq(db, jid)
            await db.commit()      # 읽기 트랜잭션을 닫고 LLM 으로 간다

            step_id = await _step(db, jid, seq, "plan", "연구 계획 수립",
                                  detail="질문을 하위질문으로 분해하는 중입니다")
            try:
                plan = await make_plan(question, params=params)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                log.exception("[research] 계획 수립 실패 job=%s", jid)
                await _finish(db, step_id, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e), expect=("planning",))

            await _finish(db, step_id, "done", {"subquestions": plan})
            if not await _transition(db, jid, expect=("planning",), status="awaiting_approval",
                                     plan=plan, stage=_stage("planned")):
                return await _stopped(db, jid)
            return {"job_id": str(jid), "status": "awaiting_approval"}

    except SoftTimeLimitExceeded:
        raise
    except Exception as e:
        log.exception("[research] 계획 태스크 오류 job=%s", jid)
        return {"job_id": str(jid), "status": await _fail_open_job(Session, jid, str(e))}
    finally:
        await engine.dispose()


@celery_app.task(name="tasks.run_deep_research", queue=get_settings().RESEARCH_QUEUE,
                 soft_time_limit=SOFT_LIMIT, time_limit=HARD_LIMIT)
def run_deep_research(job_id: str) -> dict:
    return _run_job(_run_deep_research, job_id)


async def _run_deep_research(job_id: str) -> dict:
    jid = _job_uuid(job_id)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            # 재개 가능한 상태만 받는다. running 인 잡을 다시 받으면 재배달이다.
            if not await _claim(db, jid, allowed=RUNNABLE_STATUSES, to="running"):
                log.warning("[research] 이미 처리 중이거나 처리된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}

            job = await db.get(ResearchJob, jid)
            stage, snapshot = job.stage, job.state_snapshot
            question, params, plan = job.question, job.params, job.plan
            seq = await _next_seq(db, jid)
            await db.commit()

            async def _emit(kind: str, payload: dict) -> None:
                await publish(jid, kind, payload)

            # ── 탐색: stage 가 이미 explored 면 건너뛰고 스냅샷을 되살린다 ──
            state = restore_state(str(jid), snapshot) if stage == "explored" and snapshot else None
            if state is not None and _wiped_out(state):
                # 전멸 가드가 생기기 전에 남은 스냅샷이다. 거기서 종합만 다시 하면
                # 절 0개짜리 보고서가 completed 로 남아 retry 도 막힌다.
                log.warning("[research] 전멸 스냅샷 — 탐색부터 다시 한다 job=%s", job_id)
                state = None
            if state is not None:
                log.info("[research] 탐색 건너뜀 — 스냅샷에서 재개 job=%s", job_id)
            else:
                state = ResearchState(
                    job_id=str(jid), question=question, params=merge_params(params or {}),
                )
                state.subquestions = [SubQuestion(idx=i, text=t) for i, t in enumerate(plan or [])]
                if not state.subquestions:
                    # 아래 전멸 판정(all)은 빈 목록에도 참이다. 여기서 끊지 않으면 계획이
                    # 빈 잡이 "탐색이 오류로 실패"로 남아 검색 장애로 오진된다.
                    return await _end_failed(db, jid, EMPTY_PLAN_ERROR)
                state.corpus_range = await _corpus_range(db)

                for subq in state.subquestions:
                    if await _is_cancelled(db, jid):
                        return await _stopped(db, jid)

                    step_id = await _step(
                        db, jid, seq, "search", subq.text, subq_idx=subq.idx,
                        detail=f"'{subq.text}' 관련 논문을 찾기 위해 검색 중입니다",
                    )
                    seq += 1
                    try:
                        await explore_subquestion(state, subq, db=db, emit=_emit)
                    except SoftTimeLimitExceeded:
                        # except Exception 보다 먼저 와야 한다 — SoftTimeLimitExceeded 도
                        # Exception 이라 거기서 삼키면 남은 하위질문을 계속 돌다 하드 리밋에 죽는다.
                        raise
                    except Exception as e:
                        # 부분 실패는 전체 실패가 아니다 — 나머지 하위질문은 계속한다.
                        # 다만 failed 를 남겨야 보고서가 이걸 "근거 없음"(연구 결과)이
                        # 아니라 "오류로 확인 못함"(시스템 장애)으로 쓴다.
                        log.exception("[research] 하위질문 실패 job=%s idx=%s", jid, subq.idx)
                        await db.rollback()     # DB 오류면 트랜잭션이 깨져 있어 기록부터 터진다
                        subq.failed = True
                        await _finish(db, step_id, "failed", {"error": str(e)[:500]})
                    else:
                        await _finish(db, step_id, "done", {
                            "queries": subq.queries, "adopted": len(subq.evidence_ids),
                            "verdict": subq.verdict, "note": subq.note,
                            "parse_failed": subq.parse_failed, "capped": subq.capped,
                        })

                # 전멸은 연구 결과가 아니라 장애다. 체크포인트를 남기면 retry 가 전부
                # 실패한 스냅샷으로 종합만 다시 해 빈 보고서를 completed 로 저장한다.
                if _wiped_out(state):
                    return await _end_failed(db, jid, "모든 하위질문 탐색이 오류로 실패했다")

                # 체크포인트. 여기까지가 비싼 구간이고, 종합은 다시 돌려도 싸다.
                if not await _transition(db, jid, expect=("running",), stage=_stage("explored"),
                                         state_snapshot=snapshot_state(state)):
                    return await _stopped(db, jid)

            if await _is_cancelled(db, jid):
                return await _stopped(db, jid)

            # ── 종합 ──
            step_id = await _step(db, jid, seq, "synthesize", "보고서 종합")
            try:
                report = await synthesize(state, should_stop=lambda: _is_cancelled(db, jid))
            except SynthesisCanceled:
                await _finish(db, step_id, "failed", {"error": "취소됨"})
                return await _stopped(db, jid)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                # stage 는 explored 로 남는다 → POST /api/research/{job_id}/retry 가
                # 탐색을 건너뛰고 여기부터 다시 온다.
                log.exception("[research] 종합 실패 job=%s", jid)
                await db.rollback()
                await _finish(db, step_id, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e))

            await _finish(db, step_id, "done", {"sections": len(report["sections"])})
            if not await _transition(db, jid, expect=("running",), status="completed",
                                     report=report, stage=_stage("synthesized"),
                                     finished_at=_now()):
                return await _stopped(db, jid)
            await publish_terminal(jid, "completed")
            return {"job_id": str(jid), "status": "completed"}

    except SoftTimeLimitExceeded:
        raise
    except Exception as e:
        # 가드 밖 예외(스냅샷 복원·수록 범위·step 기록)로 태스크만 죽으면 잡이 running 에
        # 묶여 SSE 는 ping 만 보내고 사용자는 retry 도 못 한 채 회수기를 기다린다.
        log.exception("[research] 실행 태스크 오류 job=%s", jid)
        return {"job_id": str(jid), "status": await _fail_open_job(Session, jid, str(e))}
    finally:
        # 루프가 죽기 전에 커넥션을 닫는다. 빠뜨리면 다음 잡이 남은 커넥션을 만난다.
        await engine.dispose()


@celery_app.task(name="tasks.reap_stale_research", queue="q_control")
def reap_stale_research() -> dict:
    """멈춰버린 리서치를 실패로 떨어뜨린다.

    정상 잡은 JOB_DEADLINE 에서 스스로 실패를 남긴다. 그래도 planning·running 에
    남은 잡은 워커 프로세스가 죽은 것이다.

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
확인은 §2.43.

### 2.37 `api/research.py` — 엔드포인트 6개와 SSE

**책임.** 생성·승인·재시도·취소·조회·스트림. 실행은 Celery 가 맡고 진행은 SSE 로 중계한다 — 탭을 닫아도 워커는 계속 돌고, 다시 열면 `research_steps` 로 지금까지를 복원한 뒤 이어서 받는다.

| 엔드포인트 | 받는 상태 | 주요 응답 |
|---|---|---|
| `POST /api/research` | — | 200 `created` · params 422 · 브로커 실패 503(잡은 `failed`) |
| `POST /{id}/approve` | `awaiting_approval` | 200 `approved` · 본문 생략 가능 · 수정 계획 422 · 상태 409 · 과도기 429 · 브로커 실패 503(되돌림) |
| `POST /{id}/retry` | `failed` + `plan` 있음 | 200 `queued`(+`stage`) · 계획 없음 409 · 상태 409 · 과도기 429 · 브로커 실패 503(되돌림) |
| `POST /{id}/cancel` | `created`~`running` 6개 | 200 `canceled` · 끝난 잡 409 · 없는 잡 404 |
| `GET /{id}` | — | 잡 + steps(`result` 포함) |
| `GET /{id}/stream` | — | SSE |

**설계 결정과 리뷰 반영.**

**① 모든 전이가 조건부 UPDATE 다.** 리뷰 전 approve·retry 는 읽고(`db.get`) → 파이썬에서 상태를 검사하고 → ORM 에 대입해 커밋했다. approve 가 `awaiting_approval` 을 읽은 직후 cancel 이 커밋되면 approve 의 커밋이 `approved` 로 덮고 태스크를 보내, 취소한 잡이 5~7분 GPU 를 쓰고 `completed` 가 된다. 중복 approve·retry 가 첫 워커의 선점 뒤에 떨어지면 `running` 이 `approved` 로 되돌아가 같은 잡이 두 벌 돌 수도 있었다. cancel 만 조건부였던 비대칭이다. 지금은 워커와 같은 모양의 `_transition` 으로 모두 바꿨다. 사전 검사(`job.status != …` → 409)는 친절한 오류 메시지용이고, **정합성은 `WHERE` 가 지킨다** — 검사를 통과한 뒤 전이가 0행이면 "그 사이 잡 상태가 바뀌었다" 409 이고 태스크를 보내지 않는다(`test_cancel_racing_approve_wins`). 승인이 쓰는 값은 `STATUS_APPROVED` 다 — 워커 `_claim` 이 받는 `RUNNABLE_STATUSES` 와 같은 상수를 본다(§2.36 ④).

**② 브로커 실패는 되돌린다.** 세 쓰기 엔드포인트 모두 상태를 먼저 커밋하고 그다음 `send_task` 를 한다. 리뷰 전에는 Redis 가 재시작하는 몇 초 사이에 승인을 누르면 500 이 나고 잡이 `approved` 로 남았다 — 다시 누르면 409("승인할 수 없는 상태다: approved"), 회수기는 `approved` 를 건드리지 않으므로 영원히 거기 묶였다. 이제 `_enqueue` 가 kombu `OperationalError` 에 `False` 를 돌려주고, 호출자가 이전 상태로 되돌린 뒤 503 을 낸다. 생성은 `failed`(`작업 큐에 넣지 못했다`), 승인은 `awaiting_approval` + **원래 계획**, 재시도는 `failed` + 원래 `last_error`·`finished_at`. 되돌리기도 조건부(`expect=(STATUS_APPROVED,)` 등)라 그 사이 들어온 취소를 되살리지 않는다. `_enqueue` 는 kombu·`celery_app` 을 함수 안에서 import 하므로 `api.research` 를 여는 데 celery·kombu 가 필요 없다 — 둘 다 로컬 venv 에 없고, 테스트는 `workers.celery_app` 을 대역 모듈로 바꿔 끼운다(§2.44).

**③ 승인 계획 검증.** 워커는 `plan` 의 모든 항목을 하위질문으로 돈다. 리뷰 전 approve 는 "빈 리스트 아님"만 봤고, planner 가 계획을 만들 때 적용하는 정규화(strip·빈 항목 제거·중복 제거·`max_subquestions` 상한)를 거치지 않았다. `state.py` 가 파라미터 상한을 둔 이유 — 요청 하나로 워커를 묶는 자해 경로 차단 — 가 승인에서 그대로 열린 것이다. 리뷰가 든 시나리오는 하위질문 200개짜리 계획이다 — 잡 하나가 시간 상한까지 실행 슬롯과 공유 GPU 를 쥐다 실패한다. 게다가 `plan` 이 있으니 retry 가 허용돼 탐색부터 다시 탄다. 지금은 두 층이다.

- 형식 — `PlanItem`(pydantic `StringConstraints(strip_whitespace=True, min_length=2, max_length=300)`)과 `min_length=1` 리스트. 어기면 FastAPI 가 422.
- 내용 — `_validated_plan` 이 개수를 그 잡의 `max_subquestions` 이하로, 중복을 planner 와 **같은 규칙**(`query_key` — 공백·대소문자 무시)으로 막는다. 규칙이 두 경로에서 갈리지 않게 함수를 공유했다.

본문은 선택이다(`ResearchApprove | None = None`). 리뷰 전에는 기본값이 없어 본문 없는 POST 가 422 였다 — spec §10 의 "자동 승인" 폴백으로 프론트가 `fetch(url, {method: "POST"})` 만 보내면 승인이 안 됐다. 라이브 검증이 `-d '{}'` 를 붙여서 이걸 가렸다.

**④ `job_id` 정규화.** `uuid.UUID()` 는 대문자·하이픈 없는 표기도 받아 DB 조회에 성공한다. 그런데 리뷰 전 스트림은 경로 문자열을 그대로 구독했고, 워커는 `str(jid)`(소문자·하이픈 표준형) 채널에 publish 한다. 대문자 경로로 붙으면 스냅샷은 정상인데 이후 이벤트가 하나도 오지 않고 ping 만 흘렀다. `_job_uuid`(형식이 틀리면 500 이 아니라 422)는 리뷰 전에도 있었지만 조회에만 쓰였다. 이제 핸들러 첫 줄에서 한 번 바꾸고 이후에는 `str(jid)` 만 쓴다.

**⑤ 과도기 429 — `_to_run_queue`.** `RESEARCH_QUEUE` 가 적재 큐(`INGEST_QUEUES` — 기본값 `q_llm` 포함)인 동안에만 걸린다. 이 구성에서 딥리서치 실행은 적재 요약·마무리와 같은 `celery-llm` 슬롯 4개를 잡마다 최대 25분 쥔다. 여럿이 쥐면 슬롯을 기다리는 적재 아이템이 단계 타임아웃(요약 1200초·마무리 900초 — `updated_at` 부터 재고 큐 대기 중에는 갱신되지 않는다)을 넘겨 stale 복구되고, 새 체인과 큐에 남은 옛 체인이 겹쳐 **논문 본문 청크가 초록 청크로 덮일 수 있다**(함정 16번). 리뷰의 이산 사건 모델에서 잡을 몰아서 승인하거나 긴 잡이 겹칠 때 재현됐고, 한 번에 한 잡이면 25분짜리를 연달아 돌려도 stale 이 0 이었다. 그래서 approve·retry 가 실행 슬롯을 1개로 묶는다.

- **무엇을 세나.** `RUN_SLOT_STATUSES = (approved, queued, running)`. `approved`·`queued` 는 워커가 아직 안 집었을 뿐 이미 큐에 들어간 실행이다 — `running` 만 세면 몰아서 승인한 잡이 전부 통과한다.
- **왜 잠금인가.** 센 뒤 전이하는 사이에 다른 승인이 끼면 둘 다 빈 슬롯을 보고 통과한다. `pg_advisory_xact_lock`(키는 `"RESEARCH"` 의 ASCII)을 잡고 센 뒤 같은 트랜잭션에서 전이하며, 잠금은 `_transition` 의 커밋이 푼다. READ COMMITTED 라 잠금을 얻은 뒤의 조회는 먼저 들어온 쪽이 커밋한 상태를 본다.
- **429 는 아무것도 쓰지 않는다.** 롤백하고(잠금도 풀린다) 상태를 그대로 둔다 — 앞 잡이 끝나면 다시 승인하면 된다.
- **상태 오류가 먼저다.** 재시도할 수 없는 잡에 429 를 주면 "기다리면 된다"로 읽힌다. 그래서 409 검사가 슬롯 검사보다 앞에 있다.
- **전용 워커로 넘기면 상한이 없다.** `celery-research` 는 적재 슬롯을 먹지 않고 실행을 한 번에 한 잡씩 돌리므로, 뒤 잡은 `approved` 로 앞 잡이 끝나길 최대 25분 기다린다(그동안 SSE 는 ping 만). 상한·대기 신호를 둘지는 화면과 함께 정한다(완료노트 §8).

429 는 **몰아서 승인하는 사고를 막는 안전장치이지, 적재 중 실행을 허락한다는 뜻이 아니다.** "한 번에 한 잡이면 stale 0" 도 가정값 위의 모델 결과라, 과도기 구성에서 운영 딥리서치는 적재를 pause 하고 in-flight 0 을 본 뒤에만 돌린다(런북 §8). 브로커 메시지를 잃은 `approved`·`queued` 잡이 슬롯을 영원히 쥐면 429 가 풀리지 않는다 — 회수기는 그 둘을 건드리지 않으므로 찾아서 취소한다.

**⑥ 재시도가 체크포인트에 닿는 유일한 경로다.** 워커의 `_claim` 은 `approved`·`queued` 만 받으므로 `failed` 인 잡은 아무도 다시 집을 수 없다. 이 엔드포인트가 없으면 `stage`·`state_snapshot` 은 쓰기만 하고 아무도 안 읽는 컬럼이 된다(Task 10 구현 중에 연 경로다). **`stage`·`state_snapshot` 을 건드리지 않는 것이 이 엔드포인트의 전부다.** 큐에 들어간 잡이 종료 시각을 들고 있으면 안 되므로 `last_error`·`finished_at` 만 비운다. 계획 단계에서 실패한 잡(`plan` 없음)은 409 다 — 다시 돌려도 워커가 곧바로 `EMPTY_PLAN_ERROR` 로 끝낼 뿐이라, 재시도가 아니라 새 잡이 답이다.

**⑦ 취소.** `CANCELLABLE_STATUSES` 안에서 조건부로 `canceled` 를 찍는다. 0행이면 `_get_job` 이 404(없는 잡)를 먼저 가리고 나머지는 409(끝난 잡) — 리뷰 전에는 없는 잡도 409 였다. 커밋 뒤 `publish_terminal` 을 직접 부르는 이유: 승인 대기처럼 **워커가 없는 상태에서 취소하면 종료 이벤트를 낼 주체가 없어** 스트림이 다음 하트비트(최대 15초)까지 열려 있었다. 워커가 돌던 잡이면 워커의 `_stopped` 도 종료 이벤트를 내지만, 스트림은 첫 종료 이벤트에서 닫히므로 무해하다.

**⑧ 스트림.**

- 스냅샷과 잡 상태는 **핸들러 안에서 미리 꺼내 둔다.** FastAPI 는 핸들러가 반환하면 yield 의존성(`get_db` 세션)을 닫고, `StreamingResponse` 의 제너레이터는 그 뒤에 돈다. ORM 객체를 들고 가면 닫힌 세션을 쓰게 된다.
- 하트비트의 종료 확인(`_terminal_status`)은 **짧은 세션을 매번 새로 연다.** `Depends(get_db)` 세션을 계속 쓰면 유휴 SSE 하나가 커넥션을 몇 분씩 쥐고 수명도 요청을 벗어난다. 여기는 FastAPI 의 장수 루프 안이라 풀링 엔진(`AsyncSessionLocal`)이 맞다 — 워커와 반대 결론인 이유는 §2.36 ①.
- 하트비트에서 DB 를 보는 것은 종료 이벤트를 놓친 채 붙어 있는 경우를 위해서다. 회수기가 끝낸 잡은 아무도 종료 이벤트를 publish 하지 않는다.
- `X-Accel-Buffering: no` 는 nginx 가 SSE 를 버퍼링하지 않게 하는 헤더다. 다만 **게이트웨이 경유 스트림은 아직 확인하지 않았다** — 라이브 검증은 fastapi 컨테이너 안에서 앱에 직접 붙었다. round04b 에서 `curl -N http://<서버>:92/api/research/<id>/stream` 으로 처음 본다(완료노트 §8).

**남겨 둔 것.** 라우터가 ORM·트랜잭션·상태 전이 규칙을 직접 다룬다 — `coding-standard.md` 가 백로그 반례로 둔 패턴을 새 코드가 늘렸고, 응답 스키마(`response_model`)도 없어 `GET` 과 `snapshot` 의 step 직렬화가 갈라져 있다(`result` 유무). `_transition` 이 워커와 API 에 중복돼 있는 것도 같은 뿌리다. 전이를 `services/research` 로, 응답을 Pydantic 스키마로 옮기는 것은 구조 변경이라 대회 이후로 이월했다(완료노트 §8). 잡 목록 API 도 없다 — 다시 열려면 `job_id` 를 보관해야 한다.

**파일**: `app/api/research.py` — 전체 362줄

```python
"""research.py — 딥리서치 API

실행은 Celery 가 맡고 진행은 SSE 로 중계한다. 탭을 닫아도 워커는 계속 돌고,
다시 열면 research_steps 로 지금까지를 복원한 뒤 이어서 받는다.

상태 전이:
    created ─plan─→ planning ─→ awaiting_approval ─approve─→ approved
    approved ─run─→ running ─→ completed | failed
    failed ─retry─→ queued ─run─→ running (stage=explored 면 종합부터)
    (거의 모든 상태) ─cancel─→ canceled

모든 전이는 기대한 이전 상태를 WHERE 에 건 조건부 UPDATE 다. 읽고-검사하고-대입하면
그 사이 커밋된 취소를 덮어, 사용자가 취소한 잡이 승인·실행된다.

실행을 적재 워커와 나눠 쓰는 동안(RESEARCH_QUEUE 가 적재 큐)은 approve·retry 가 실행
슬롯이 비었을 때만 전이하고 아니면 429 다 — _to_run_queue.
"""
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from db.postgres import AsyncSessionLocal
from models.research import (
    RUNNABLE_STATUSES, STATUS_APPROVED, STATUS_CANCELED, STATUS_QUEUED, TERMINAL_STATUSES,
    ResearchJob, ResearchStep,
)
from services.research.planner import query_key
from services.research.relay import TERMINAL_KIND, publish_terminal, subscribe, terminal_event
from services.research.state import merge_params

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])

# 중계를 끊어야 하는 이벤트. 종료 이벤트의 모양은 relay.terminal_event 하나로만 만든다.
TERMINAL_KINDS = tuple(TERMINAL_KIND.values())

# 취소를 받아주는 상태. completed·failed·canceled 는 이미 끝난 잡이라 409 다.
CANCELLABLE_STATUSES = (
    "created", "planning", "awaiting_approval",
    STATUS_APPROVED, STATUS_QUEUED, "running",
)

# 적재 단계 태스크가 도는 큐(workers/celery_app.py task_routes). 전용 워커로 넘기기 전
# (RESEARCH_QUEUE 기본값 q_llm) 딥리서치 실행은 적재 요약·마무리와 같은 celery-llm 슬롯
# 4개를 잡마다 최대 25분 쥔다. 여럿이 쥐면 슬롯을 기다리는 적재 아이템이 단계 타임아웃을
# 넘겨 stale 복구되고, 옛 체인과 새 체인이 겹쳐 논문 본문 청크가 초록으로 덮일 수 있다
# (recurring-gotchas 16번). 그래서 이 큐들에서는 실행을 한 번에 한 잡으로 묶는다.
INGEST_QUEUES = frozenset({"ingestion", "q_cpu", "q_llm", "q_embed", "q_control"})
SHARED_QUEUE_MAX_RUNS = 1
# 실행 슬롯을 쥐었거나 곧 쥘 상태. approved·queued 는 워커가 아직 안 집었을 뿐 이미
# 큐에 들어간 실행이다 — running 만 세면 몰아서 승인한 잡이 전부 통과한다.
RUN_SLOT_STATUSES = (*RUNNABLE_STATUSES, "running")
# 동시에 온 승인·재시도를 한 줄로 세우는 트랜잭션 잠금 키("RESEARCH" 의 ASCII)
_RUN_SLOT_LOCK = 0x5245534541524348

# 하위질문 한 줄. 빈 항목은 빈 쿼리 검색으로, 초장문은 LLM 컨텍스트 초과로 이어진다.
PlanItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=300)]


class ResearchCreate(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    params: dict = Field(default_factory=dict)


class ResearchApprove(BaseModel):
    # 사용자가 수정한 계획. 없으면 제안대로.
    plan: Annotated[list[PlanItem], Field(min_length=1)] | None = None


def _job_uuid(job_id: str) -> uuid.UUID:
    """경로 파라미터를 PK 타입으로 바꾼다. 형식이 틀리면 422 — 500 이 아니다.

    uuid.UUID 는 대문자·하이픈 없는 표기도 받는다. 이후로는 이 값의 str() 만 쓴다 —
    워커는 표준형 채널에 publish 하므로 경로 문자열을 그대로 구독하면 이벤트를 못 받는다.
    """
    try:
        return uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="job_id 형식이 올바르지 않습니다")


async def _get_job(db: AsyncSession, jid: uuid.UUID) -> ResearchJob:
    job = await db.get(ResearchJob, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


async def _transition(
    db: AsyncSession, jid: uuid.UUID, *, expect: tuple[str, ...], **values: object,
) -> bool:
    res = await db.execute(
        update(ResearchJob)
        .where(ResearchJob.id == jid, ResearchJob.status.in_(expect))
        .values(**values)
    )
    await db.commit()
    return res.rowcount == 1


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


def _enqueue(task_name: str, jid: uuid.UUID) -> bool:
    """브로커에 넣지 못하면 False. 호출자가 상태를 되돌린다 — 되돌리지 않으면
    created·approved·queued 에 묶인 잡을 다시 큐에 넣을 경로가 없다."""
    from kombu.exceptions import OperationalError

    from workers.celery_app import celery_app
    try:
        celery_app.send_task(task_name, args=[str(jid)])
    except OperationalError:
        log.exception("[research] 작업 큐 전달 실패 task=%s job=%s", task_name, jid)
        return False
    return True


def _broker_unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="작업 큐에 연결하지 못했습니다 — 잠시 후 다시 시도하세요")


def _validated_plan(plan: list[str], *, limit: int) -> list[str]:
    """사용자 수정 계획을 planner 가 만드는 계획과 같은 경계로 묶는다.

    워커는 plan 의 모든 항목을 하위질문으로 돈다. 여기서 막지 않으면
    max_subquestions 상한(요청 하나로 워커를 묶는 자해 경로 차단)이 승인에서 뚫린다.
    """
    if len(plan) > limit:
        raise HTTPException(status_code=422, detail=f"하위질문은 {limit}개까지다")
    seen: set[str] = set()
    for text in plan:
        key = query_key(text)        # planner 의 중복 제거와 같은 규칙
        if key in seen:
            raise HTTPException(status_code=422, detail=f"중복된 하위질문이다: {text}")
        seen.add(key)
    return plan


@router.post("")
async def create_research(req: ResearchCreate, db: AsyncSession = Depends(get_db)):
    try:
        params = merge_params(req.params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    job = ResearchJob(id=uuid.uuid4(), question=req.question, params=params)
    db.add(job)
    await db.commit()

    if not _enqueue("tasks.plan_deep_research", job.id):
        await _transition(db, job.id, expect=("created",), status="failed",
                          last_error="작업 큐에 넣지 못했다", finished_at=func.now())
        raise _broker_unavailable()
    return {"job_id": str(job.id), "status": "created"}


@router.post("/{job_id}/approve")
async def approve_plan(
    job_id: str, req: ResearchApprove | None = None, db: AsyncSession = Depends(get_db),
):
    """계획을 확정하고 실행 큐에 넣는다.

    status 를 STATUS_APPROVED 로 바꾸는 것이 핵심이다. 상태를 그대로 두고
    태스크만 던지면 워커의 _claim(allowed=RUNNABLE_STATUSES) 이 0행을 잡아
    잡이 영원히 skipped 로 떨어진다 — 그래서 양쪽이 같은 상수를 본다.
    """
    jid = _job_uuid(job_id)
    job = await _get_job(db, jid)
    if job.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail=f"승인할 수 없는 상태다: {job.status}")

    old_plan = job.plan
    plan = old_plan
    if req is not None and req.plan is not None:
        limit = merge_params(job.params or {})["max_subquestions"]
        plan = _validated_plan(req.plan, limit=limit)

    if not await _to_run_queue(db, jid, expect=("awaiting_approval",),
                               status=STATUS_APPROVED, plan=plan):
        raise HTTPException(status_code=409, detail="그 사이 잡 상태가 바뀌었다")

    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_APPROVED,),
                          status="awaiting_approval", plan=old_plan)
        raise _broker_unavailable()
    return {"job_id": str(jid), "status": STATUS_APPROVED, "plan": plan}


@router.post("/{job_id}/retry")
async def retry_research(job_id: str, db: AsyncSession = Depends(get_db)):
    """실패한 잡을 다시 큐에 넣는다. **체크포인트에 닿는 유일한 경로다.**

    종합이 실패하면 워커는 status="failed" 로 두고 stage="explored" 와
    state_snapshot 을 남긴다. 그런데 _claim 은 approved·queued 만 받으므로
    failed 인 잡은 아무도 다시 집을 수 없다 — 이 엔드포인트가 없으면
    stage·state_snapshot 은 쓰기만 하고 아무도 안 읽는 컬럼이 되고,
    5~7분짜리 탐색을 지켜둔 의미가 사라진다.

    stage 와 state_snapshot 을 건드리지 않는 것이 이 엔드포인트의 전부다.
    둘을 초기화하면 재시도가 탐색부터 다시 돌아 체크포인트가 무의미해진다.

    계획 단계에서 실패한 잡(plan 이 비어 있음)은 받지 않는다. 다시 돌려도 워커가
    탐색 없이 곧바로 failed(EMPTY_PLAN_ERROR)로 끝낼 뿐이라, 재시도가 아니라 새
    잡이 답이다 — 여기서 409 로 그렇게 알린다.
    """
    jid = _job_uuid(job_id)
    job = await _get_job(db, jid)
    if job.status != "failed":
        raise HTTPException(status_code=409, detail=f"재시도할 수 없는 상태다: {job.status}")
    if not job.plan:
        raise HTTPException(
            status_code=409, detail="계획이 없는 잡은 재시도할 수 없다 — 새 잡을 만든다",
        )

    old_error, old_finished = job.last_error, job.finished_at
    # 큐에 들어간 잡이 종료시각을 들고 있으면 안 된다
    if not await _to_run_queue(db, jid, expect=("failed",), status=STATUS_QUEUED,
                               last_error=None, finished_at=None):
        raise HTTPException(status_code=409, detail="그 사이 잡 상태가 바뀌었다")

    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_QUEUED,), status="failed",
                          last_error=old_error, finished_at=old_finished)
        raise _broker_unavailable()
    return {"job_id": str(jid), "status": STATUS_QUEUED, "stage": job.stage}


@router.post("/{job_id}/cancel")
async def cancel_research(job_id: str, db: AsyncSession = Depends(get_db)):
    """진행 중인 LLM 호출을 중간에 끊지는 않는다 — 탐색은 하위질문 경계에서, 종합은
    절 경계에서 멈춘다. 워커의 상태 쓰기가 조건부라 그 뒤 canceled 가 뒤집히지 않는다.

    5~7분짜리 GPU 작업을 멈출 방법이 없으면, 창을 닫은 사용자의 잡이 공유
    GPU 를 계속 먹는다. 시연 중에 이게 겹치면 다른 기능까지 느려진다.
    """
    jid = _job_uuid(job_id)
    if not await _transition(db, jid, expect=CANCELLABLE_STATUSES,
                             status=STATUS_CANCELED, finished_at=func.now()):
        await _get_job(db, jid)
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태입니다")
    # 워커가 없는 상태(승인 대기 등)에서 취소하면 종료 이벤트를 낼 주체가 없다 —
    # 여기서 내지 않으면 스트림이 다음 하트비트까지 열려 있다.
    await publish_terminal(jid, STATUS_CANCELED)
    return {"job_id": str(jid), "status": STATUS_CANCELED}


@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, _job_uuid(job_id))
    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    return {
        "job_id": str(job.id), "question": job.question, "status": job.status,
        "stage": job.stage, "plan": job.plan, "report": job.report,
        "last_error": job.last_error,
        "steps": [
            {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx, "title": s.title,
             "detail": s.detail, "status": s.status, "result": s.result}
            for s in rows
        ],
    }


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/{job_id}/stream")
async def stream_research(job_id: str, db: AsyncSession = Depends(get_db)):
    jid = _job_uuid(job_id)
    job = await _get_job(db, jid)

    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    snapshot = [
        {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx,
         "title": s.title, "detail": s.detail, "status": s.status}
        for s in rows
    ]
    # 제너레이터는 요청 세션이 닫힌 뒤에 돈다 — ORM 객체를 들고 가지 않고
    # 필요한 값만 미리 꺼내 둔다.
    job_status, job_error = job.status, job.last_error

    async def _gen() -> AsyncIterator[str]:
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield _sse({"kind": "snapshot", "steps": snapshot})
        if job_status in TERMINAL_STATUSES:
            # 끝난 잡에 붙었다면 중계할 것이 없다. 구독하면 영원히 기다린다.
            yield _sse(terminal_event(job_status, job_error))
            return
        async for event in subscribe(str(jid)):
            if event is None:
                # 하트비트. 끊긴 소켓은 여기서 드러난다. 그리고 종료 이벤트를
                # 놓친 채 붙어 있는 경우(회수기가 끝낸 잡 등)를 대비해 상태를 확인한다.
                yield ": ping\n\n"
                ended = await _terminal_status(jid)
                if ended is not None:
                    yield _sse(terminal_event(*ended))
                    return
                continue
            yield _sse(event)
            if event.get("kind") in TERMINAL_KINDS:
                return

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _terminal_status(jid: uuid.UUID) -> tuple[str, str | None] | None:
    """끝난 잡이면 (status, last_error). 하트비트마다 짧은 세션을 새로 연다 —
    Depends(get_db) 세션을 쓰지 않는다.

    FastAPI 는 핸들러가 반환하면 yield 의존성을 닫는다. StreamingResponse 의
    제너레이터는 그 뒤에 도는데, 닫힌 세션을 계속 쓰면 유휴 SSE 하나가
    커넥션을 몇 분씩 쥐고 있게 되고 수명도 요청 수명을 벗어난다. 여기는
    FastAPI 의 장수 루프 안이라 풀링 엔진(AsyncSessionLocal)이 맞다.
    """
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(ResearchJob.status, ResearchJob.last_error).where(ResearchJob.id == jid)
        )).first()
    if row is None or row[0] not in TERMINAL_STATUSES:
        return None
    return row[0], row[1]
```
### 2.38 `main.py` — 라우터 등록

**책임.** `research_router` 를 앱에 붙인다. 변경은 두 줄이다.

diff 는 두 줄이지만, diff 밖의 lifespan 이 딥리서치 배포에 두 번 얽힌다.

- **테이블은 여기서 생긴다.** lifespan 의 `Base.metadata.create_all` 이 새 이미지가 뜰 때 `research_jobs`·`research_steps` 를 모델에서 먼저 만든다. lifespan 은 `models.research` 를 직접 import 하지 않는다 — 추가한 `from api.research import …` 가 모델을 끌고 와 `Base.metadata` 에 올리므로, 이 두 줄이 곧 테이블 생성 스위치다. 그래서 운영에서는 `0005_research_jobs` 를 `upgrade` 하지 않고 테이블을 확인한 뒤 `alembic stamp` 만 했다 — `upgrade head` 면 `DuplicateTable` 이다(함정 14번, plan Task 11 Step 2). 현재 서버는 `0005_research_jobs` 다.
- **재시작은 잠금을 요구한다.** 같은 lifespan 의 `ALTER TABLE library_catalog ADD COLUMN IF NOT EXISTS …` 는 컬럼이 있어도 배타 잠금을 기다린다. 딥리서치 워커가 트랜잭션을 연 채 LLM 을 기다리면 이 재시작이 전체 조회를 멈춘다 — runner 의 커밋(§2.35 ①)이 막는 것이 이 경로다(함정 18번). 스키마를 만드는 경로가 셋(`create_all`·ad-hoc `ALTER`·Alembic)인 구조 자체의 정리는 대회 이후다.

**파일**: `app/main.py` — `main` 대비 변경분(diff)

```diff
diff --git a/app/main.py b/app/main.py
index 065531b..3253cb6 100644
--- a/app/main.py
+++ b/app/main.py
@@ -10,6 +10,7 @@ from api.admin import router as admin_router
 from api.paper import router as paper_router
 from api.ingest_jobs import router as ingest_jobs_router
 from api.scenario import router as scenario_router
+from api.research import router as research_router
 
 logging.basicConfig(level=logging.INFO)
 log = logging.getLogger(__name__)
@@ -82,4 +83,5 @@ app.include_router(book_router)
 app.include_router(admin_router)
 app.include_router(paper_router)
 app.include_router(ingest_jobs_router)
-app.include_router(scenario_router)
\ No newline at end of file
+app.include_router(scenario_router)
+app.include_router(research_router)
\ No newline at end of file
```
### 2.39 `docker-compose.yml` — 전용 워커 둘과 보내는 쪽 설정 (운영)

**책임.** 세 곳을 바꾼다.

- `fastapi` 서비스 env 에 `RESEARCH_QUEUE: q_research`·`RESEARCH_PLAN_QUEUE: q_research_plan` — 보내는 쪽.
- `celery-research` 신설 — 실행 전용(`-Q q_research`, `--concurrency=1`, GPU 예약, `/data/models/.hf-cache:/models`, `shm_size 4g`, Milvus 의존).
- `celery-research-plan` 신설 — 계획 전용(`-Q q_research_plan`, `--concurrency=2`, GPU·모델 캐시 없음, Milvus 의존 없음).

**왜 이렇게 짰나.**

- **env 를 `x-common-env` 에 두지 않는다.** 거기 넣으면 그것을 물고 있는 적재 워커 전부의 설정이 바뀌어, 스택 업데이트 때 돌고 있는 인덱싱 컨테이너까지 재생성된다(함정 16번). 바뀌는 서비스만 바뀌게 서비스 env 에 둔다.
- **`fastapi` 만 새 값을 받으면 안 된다.** 이것만 적용되면 잡이 소비자 없는 큐에 쌓인다. 셋(fastapi·`celery-research`·`celery-research-plan`)은 함께 올라가야 한다 — compose 주석에도 적어 두었다. 두 워커에도 같은 두 값이 있지만, 워커는 딥리서치 태스크를 보내지 않으므로 큐를 정하는 것은 fastapi 의 값이고 소비를 정하는 것은 `-Q` 다(§2.33).
- **`celery-research` 에 GPU·모델 캐시가 필요한 이유.** 탐색이 `pipeline.search()` 를 통해 BGE-M3(질의 임베딩)와 리랭커를 **워커 프로세스 안에서** 올린다. `celery-llm` 은 외부 vLLM 을 HTTP 로 부르는 적재 요약 전용이라 둘 다 없었고, 이미지가 `HF_HOME=/models` 라 마운트가 없으면 recreate 할 때마다 모델을 새로 받았다(함정 17번). GPU 를 `celery-embed` 와 나눠 쓰므로 띄우기 전에 `nvidia-smi` 로 여유 메모리(BGE-M3+리랭커 약 3~4GB)를 본다.
- **`--concurrency=1` 의 대가.** prefork 자식마다 모델을 따로 올리지 않으려는 것이다. 대신 실행은 한 번에 한 잡이라 두 번째 잡은 승인 뒤 `approved` 로 최대 25분 기다린다. 계획까지 이 슬롯에 두면 새 질문이 `created` 로 멈추므로 계획은 GPU 가 필요 없는 `celery-research-plan` 이 받는다(계획은 LLM HTTP 호출 하나, 라이브 실측 0.56~0.67초).
- 두 워커의 나머지 설정(`extra_hosts`·`working_dir`·`PYTHONPATH`)은 이 파일의 기존 `celery-llm` 과 같다.

**파일**: `docker-compose.yml` — `main` 대비 변경분(diff)

```diff
diff --git a/docker-compose.yml b/docker-compose.yml
index 79e38d6..0dec52e 100644
--- a/docker-compose.yml
+++ b/docker-compose.yml
@@ -524,6 +524,12 @@ services:
       <<: *common-env
       NVIDIA_VISIBLE_DEVICES: all
       NVIDIA_DRIVER_CAPABILITIES: compute,utility
+      # 딥리서치 태스크를 보내는 큐. 실행은 celery-research, 계획은 celery-research-plan
+      # 만 받으므로 셋을 같이 올린다 — 이것만 적용되면 잡이 소비자 없는 큐에 쌓인다.
+      # common-env 에 두지 않는 이유: 거기 넣으면 적재 워커 전부의 설정이 바뀌어
+      # 스택 업데이트 때 돌고 있는 인덱싱 컨테이너까지 재생성된다.
+      RESEARCH_QUEUE: q_research
+      RESEARCH_PLAN_QUEUE: q_research_plan
     deploy:
       resources:
         reservations:
@@ -638,6 +644,77 @@ services:
         condition: service_healthy
     restart: unless-stopped
 
+  # ── Celery Research Worker (딥리서치 실행: 탐색·재검색·종합 — 전용 큐 q_research, 계획은 celery-research-plan) ──
+  # 적재 요약(q_llm)과 큐를 나눈 이유: 같은 FIFO 면 사용자의 계획 요청이 요약 수십 건
+  # 뒤에 서고, 반대로 상한 25분(JOB_DEADLINE)의 리서치 실행이 적재 요약 슬롯을 쥔다 —
+  # 여럿이 쥐면 슬롯을 기다리는 적재 아이템이 stale 복구돼 중복 체인이 열린다(16번).
+  # 탐색이 BGE-M3·리랭커를 프로세스 안에서 올리므로 GPU 와 모델 캐시가 필요하다
+  # (celery-llm 에는 둘 다 없어 컨테이너마다 모델을 받고 CPU 로 리랭크했다).
+  # concurrency=1: 모델을 자식마다 따로 올리지 않는다. 대신 실행은 한 번에 한 잡이라
+  # 뒤 잡은 approved 로 앞 잡이 끝나길 기다린다(최대 JOB_DEADLINE 25분). 계획까지 이
+  # 슬롯에 두면 새 질문이 created 로 멈추므로 계획은 celery-research-plan 이 받는다.
+  # 배포: fastapi 의 RESEARCH_QUEUE·RESEARCH_PLAN_QUEUE, celery-research-plan 과 같이 올린다.
+  # 인덱싱이 도는 동안에는 배포하지 않는다 —
+  # 같은 :latest 이미지를 쓰는 적재 워커가 새 이미지 기준으로 재생성되면 진행 중인 적재
+  # 태스크가 끊긴다(docs/ops/recurring-gotchas.md 16번). GPU 를 celery-embed 와 나눠 쓰므로
+  # 띄우기 전에 nvidia-smi 로 여유 메모리(BGE-M3+리랭커 약 3~4GB)를 확인한다.
+  celery-research:
+    image: landsoftdocker/nl-lib-fastapi:latest
+    container_name: nl-lib-celery-research
+    <<: *nl-lib-net
+    shm_size: "4g"
+    working_dir: /app
+    extra_hosts:
+      - "host.docker.internal:host-gateway"
+    command: celery -A workers.celery_app worker --loglevel=info --concurrency=1 -Q q_research
+    environment:
+      <<: *common-env
+      RESEARCH_QUEUE: q_research
+      RESEARCH_PLAN_QUEUE: q_research_plan
+      NVIDIA_VISIBLE_DEVICES: all
+      NVIDIA_DRIVER_CAPABILITIES: compute,utility
+      PYTHONPATH: /app
+    deploy:
+      resources:
+        reservations:
+          devices:
+            - driver: nvidia
+              count: 1
+              capabilities: [gpu]
+    volumes:
+      - /data/models/.hf-cache:/models:rw
+    depends_on:
+      redis:
+        condition: service_healthy
+      postgres:
+        condition: service_healthy
+      milvus:
+        condition: service_healthy
+    restart: unless-stopped
+
+  # ── Celery Research Plan Worker (딥리서치 계획만 — 전용 큐 q_research_plan) ──
+  # 계획은 LLM HTTP 호출 하나(0.6초)라 GPU·모델 캐시가 필요 없다. celery-research 와 같은
+  # 슬롯에 두면 다른 잡의 실행 뒤에 선다(위 주석). 배포는 celery-research 와 함께.
+  celery-research-plan:
+    image: landsoftdocker/nl-lib-fastapi:latest
+    container_name: nl-lib-celery-research-plan
+    <<: *nl-lib-net
+    working_dir: /app
+    extra_hosts:
+      - "host.docker.internal:host-gateway"
+    command: celery -A workers.celery_app worker --loglevel=info --concurrency=2 -Q q_research_plan
+    environment:
+      <<: *common-env
+      RESEARCH_QUEUE: q_research
+      RESEARCH_PLAN_QUEUE: q_research_plan
+      PYTHONPATH: /app
+    depends_on:
+      redis:
+        condition: service_healthy
+      postgres:
+        condition: service_healthy
+    restart: unless-stopped
+
   # ── Celery Embed Worker (배치 잡: 청킹+BGE-M3 임베딩+Milvus — GPU) ──
   # 모델은 프로세스당 1회 로드 — concurrency=1 유지, 배치 크기로 처리량 확보
   celery-embed:
```
#### 배포 순서 — 두 단계로 나눈 이유

compose 에는 이미 `q_research` 가 적혀 있다. 그러니 **스택 업데이트 = 전용 워커 전환**이다. 문제는 그 스택 업데이트가 인덱싱을 끊는다는 것이다(함정 16번). fastapi 와 적재 워커 5개(그리고 새 딥리서치 워커 둘)가 전부 `landsoftdocker/nl-lib-fastapi:latest` 를 쓰고, 새 이미지를 받은 뒤 스택을 업데이트하면 이미지가 바뀐 서비스가 모두 재생성된다. 도커는 SIGTERM 10초 뒤 SIGKILL 하므로 수 분짜리 적재 태스크는 중간에 죽는다. 볼륨 데이터는 외부 볼륨이라 지워지지 않지만, **끊긴 아이템은 복구 경로가 둘 다 돈다** — 디스패처의 stale 복구가 약 20분 뒤 새 체인으로 끝내고(마무리 단계가 추출 아티팩트를 지운다), 약 2시간 뒤(`visibility_timeout` 7200초) 브로커가 옛 체인을 재전달해 같은 아이템의 `embed_index` 를 아티팩트 없이 다시 돈다. 논문은 PDF 본문 청크가 초록 청크로 덮인다. 근본 원인은 적재 코드에 있고, 인덱싱이 도는 동안 적재 코드는 건드리지 않으므로 이 라운드는 **재생성을 in-flight 0 에서만** 하는 절차로 막는다.

| 단계 | 언제 | 무엇을 | 결과 |
|---|---|---|---|
| 1단계(선택) | 인덱싱 중에도 코드를 먼저 내보내야 할 때 | 서버에서 새 `:latest` 를 `docker pull` → Portainer 에서 `nl-lib-fastapi`·`nl-lib-celery-llm` **컨테이너만** Recreate | 컨테이너 Recreate 는 기존 설정(env)을 그대로 쓴다 → `RESEARCH_QUEUE` 가 없어 딥리서치는 계속 `q_llm`·`celery-llm`(§2.32 기본값) |
| 2단계 | 인덱싱이 끝난 뒤, 또는 적재를 pause 해 in-flight 를 비운 뒤 | 스택 업데이트 한 번 | fastapi 가 계획은 `q_research_plan`, 실행은 `q_research` 로 보내고 두 워커가 생긴다 → 워밍업 잡 1회 → resume |

1단계의 함정 셋.

- **새 compose 로 `docker compose up -d fastapi celery-llm` 을 하면 안 된다.** fastapi 만 `q_research` 로 보내 잡이 소비자 없는 큐에 쌓인다. Portainer 스택 정의도 바꾸지 않는다 — 스택 정의를 고쳐 업데이트하는 것이 곧 2단계다. 스택이 git 저장소 자동 업데이트에 묶여 있다면 compose 변경을 push 하는 것만으로 2단계가 일어날 수 있으니 인덱싱 중에는 먼저 확인한다(그 설정은 저장소에 기록돼 있지 않다).
- **`celery-llm` Recreate 도 적재를 끊는다.** 그 워커가 적재의 요약·마무리 단계를 돌리고 있어 그 순간의 태스크(최대 4개)가 끊긴다. 끊지 않으려면 적재 잡을 pause 하고 in-flight(`dispatched`·`running`)가 0 이 된 뒤 Recreate 한다(런북 §8). pause 만으로는 모자라다 — `paused` 동안은 stale 판정이 멈출 뿐이고, `resume` 뒤 첫 틱이 그동안 타임아웃을 넘긴 아이템을 복구한다.
- **fastapi Recreate 는 lifespan 의 `ALTER TABLE library_catalog` 를 거친다**(§2.38, 함정 18번).

그리고 **1단계 구성(과도기)에서는 적재가 `running` 인 동안 운영 딥리서치를 돌리지 않는다.** 리허설·시연 후보 미리 돌리기·기본 파라미터 실측·워밍업 모두 적재 pause·in-flight 0 안에서 한다(§2.37 ⑤, 런북 §8). 이 경로가 가정만은 아니다 — 2026-09-23 서버 조회에서 stale 복구를 거친 적재 아이템 2건이 나왔고, 복구 시각으로 보아 끊긴 시점이 round04a 첫 배포 무렵이다. 옛 체인이 다시 돈 흔적은 조회 시점까지 없었고, 확인·재적재는 나중에 한꺼번에 처리하기로 했다(완료노트 §8).

**현재 상태.** 머지 전 리뷰 반영분(조건부 전이·데드라인·전용 워커 등)은 **아직 운영에 배포하지 않았다.** 라이브 검증(완료노트 §2)은 반영 이전 코드(`b6360b8`)로, 딥리서치가 `q_llm`·`celery-llm` 에서 돌던 구성으로 한 것이다. 스키마 변경이 없어 스탬프·마이그레이션은 필요 없다. 시연을 전용 워커로 치를지, 과도기 구성으로 시연 구간만 적재를 pause 할지는 시연 전에 정한다(완료노트 §5).

2단계 전후 서버에서 확인(plan Task 11 Step 3):

```bash
nvidia-smi                                           # 띄우기 전 — GPU 여유 3~4GB
# 보내는 쪽이 어느 큐로 보내는가 — 기대: q_research q_research_plan
docker exec nl-lib-fastapi python -c "from core.config import get_settings as g; print(g().RESEARCH_QUEUE, g().RESEARCH_PLAN_QUEUE)"
# 받는 쪽이 그 큐를 듣는가 — 0 이면 태스크가 쌓이기만 한다
docker exec nl-lib-celery-research python -c "import workers.research_tasks; print('OK')"
docker exec nl-lib-celery-research celery -A workers.celery_app inspect active_queues | grep -c q_research
docker exec nl-lib-celery-research-plan celery -A workers.celery_app inspect active_queues | grep -c q_research_plan
```

`celery inspect` 는 브로커에 붙은 워커 전부에 묻고, `grep -c q_research` 는 `q_research_plan` 줄도 센다. 0 이면 확실히 문제지만 1 이상이라고 실행 워커가 떠 있다는 뜻은 아니다 — 출력에서 어느 워커가 어느 큐를 듣는지 눈으로 본다. 워커 로그의 `리랭커 로드 완료 (cuda|cpu, …)` 로 장치를 확인하고, 축소 파라미터 워밍업 잡을 `completed` 까지 본다(런북 §8 에 명령이 있다).

### 2.40 `docker-compose.dev.yml` — 같은 구성 (dev)

**책임.** 운영과 같은 세 곳을 dev 스택에 넣는다 — `fastapi-dev` env, `celery-research-dev`(`nl-lib-dev-celery-research`), `celery-research-plan-dev`(`nl-lib-dev-celery-research-plan`).

운영과 다른 점은 이 파일의 기존 워커 관례에서 온 것뿐이다 — 이미지가 `:dev`, 네트워크 앵커가 `nl-lib-dev-net-and-prod`, 의존 서비스가 `*-dev`, `extra_hosts` 가 없다(dev 파일의 다른 워커에도 없다). 이유 설명은 운영 compose 주석을 가리키게 해 두 곳에 중복하지 않았다. dev 스택은 Windows 개발 PC 에서 직접 띄우지 못하고 서버에서 돈다(함정 2번). `build_dev_images.sh` 는 `:dev` 만 만든다(함정 3번).

**파일**: `docker-compose.dev.yml` — `main` 대비 변경분(diff)

```diff
diff --git a/docker-compose.dev.yml b/docker-compose.dev.yml
index 0734f69..64946d5 100644
--- a/docker-compose.dev.yml
+++ b/docker-compose.dev.yml
@@ -358,6 +358,10 @@ services:
       <<: *common-env-dev
       NVIDIA_VISIBLE_DEVICES: all
       NVIDIA_DRIVER_CAPABILITIES: compute,utility
+      # 실행은 celery-research-dev, 계획은 celery-research-plan-dev 만 받으므로 셋을 같이
+      # 올린다(운영 compose 주석 참고)
+      RESEARCH_QUEUE: q_research
+      RESEARCH_PLAN_QUEUE: q_research_plan
     deploy:
       resources:
         reservations:
@@ -461,6 +465,60 @@ services:
         condition: service_healthy
     restart: unless-stopped
 
+  # ── Celery Research Worker (딥리서치 전용 큐 q_research — GPU·모델 캐시) ──
+  # 적재 요약과 큐를 나눈 이유·배포 순서는 운영 compose 의 celery-research 주석 참고
+  celery-research-dev:
+    image: landsoftdocker/nl-lib-fastapi:dev
+    container_name: nl-lib-dev-celery-research
+    <<: *nl-lib-dev-net-and-prod
+    shm_size: "4g"
+    working_dir: /app
+    command: celery -A workers.celery_app worker --loglevel=info --concurrency=1 -Q q_research
+    environment:
+      <<: *common-env-dev
+      RESEARCH_QUEUE: q_research
+      RESEARCH_PLAN_QUEUE: q_research_plan
+      NVIDIA_VISIBLE_DEVICES: all
+      NVIDIA_DRIVER_CAPABILITIES: compute,utility
+      PYTHONPATH: /app
+    deploy:
+      resources:
+        reservations:
+          devices:
+            - driver: nvidia
+              count: 1
+              capabilities: [gpu]
+    volumes:
+      - /data/models/.hf-cache:/models:rw
+    depends_on:
+      redis-dev:
+        condition: service_healthy
+      postgres-dev:
+        condition: service_healthy
+      milvus-dev:
+        condition: service_healthy
+    restart: unless-stopped
+
+  # ── Celery Research Plan Worker (딥리서치 계획만 — q_research_plan, GPU 불필요) ──
+  # 실행 슬롯(concurrency 1)과 나눈 이유는 운영 compose 의 celery-research-plan 주석 참고
+  celery-research-plan-dev:
+    image: landsoftdocker/nl-lib-fastapi:dev
+    container_name: nl-lib-dev-celery-research-plan
+    <<: *nl-lib-dev-net-and-prod
+    working_dir: /app
+    command: celery -A workers.celery_app worker --loglevel=info --concurrency=2 -Q q_research_plan
+    environment:
+      <<: *common-env-dev
+      RESEARCH_QUEUE: q_research
+      RESEARCH_PLAN_QUEUE: q_research_plan
+      PYTHONPATH: /app
+    depends_on:
+      redis-dev:
+        condition: service_healthy
+      postgres-dev:
+        condition: service_healthy
+    restart: unless-stopped
+
   # ── Celery Embed Worker (배치 잡: 청킹+BGE-M3 임베딩+Milvus — GPU) ──
   celery-embed-dev:
     image: landsoftdocker/nl-lib-fastapi:dev
```
### 2.41 `test_research_runner.py` — 루프·재검색·근거 순서

**무엇을 고정하나.** 27건.

- `TestExploreSubquestion` — 항상 부족이면 `max_recheck` 에서 멈춘다, 검색 0건이면 근거 0, 두 하위질문의 같은 논문은 근거 하나를 재사용, 상한이 성장을 막아도 이미 채택한 논문의 링크는 남는다, `parse_failed` 전파, `emit` 페이로드(`found` 는 청크 수).
- `TestReadTransaction` — critic 이 불리는 순간 커밋이 1회 이미 일어났는지(`commits_at_critic == [1]`). §2.35 ① 의 회귀 테스트다. runner 의 커밋 두 줄을 지우면 이 테스트 1건이 실패한다(이 교본을 쓰며 저장소 사본에서 확인).
- `TestRequery` — 이미 시도한 제안은 건너뛰고 다음 제안을 쓴다, 제안이 전부 시도한 것이면 루프를 멈춘다.
- `TestEvidenceOrder` — 라운드별 1위의 앞자리, 나머지는 라운드를 가로질러 점수순, critic 이 보는 순서도 같다.
- `TestSubquestionChunks`·`TestSharedChunkScore` — 재사용 논문은 이 하위질문에서 매칭된 청크를 쓰고, 두 하위질문이 한 청크를 매칭해도 각자의 점수로 비교한다.
- `TestEvidenceCap` — 상한에 막힌 후보 수(`capped`), 굶은 하위질문은 "없음"이 아니라 `capped` 로, 상한에 닿으면 재검색 중단.
- `TestRelayPublish`·`TestRelayLoaderIsolation` — relay 의 publish 가 채널·페이로드를 맞게 쓰고(`ensure_ascii=False` — 로그·SSE 에서 한글이 읽혀야 한다), 연결·전송 오류를 삼키며 클라이언트를 닫는다. 로더가 끝나면 `sys.modules` 가 원래대로다. relay 가 Task 9 에서 runner 와 함께 들어와 테스트도 여기 있다.

**방식.** 비동기 테스트는 `asyncio.run(...)` 으로 돈다. `@pytest.mark.asyncio` 를 쓰면 안 된다 — `pytest-asyncio` 가 이 저장소에 없고, 플러그인 없이 async 테스트를 두면 **코루틴 본문이 실행되지 않는다.** 이 파일 docstring·완료노트는 "통과로 처리된다"고 적었지만, 로컬 pytest 9.1.1 에서 돌려 보면 통과가 아니라 실패(`async def functions are not natively supported`)로 나온다 — 버전에 따라 결과 표시는 달라도 검증이 안 된다는 점은 같다. relay 는 `_load_relay` 가 `redis` 미설치일 때만 더미를 꽂고 새로 import 하며, `_forget_on_teardown` 으로 끝나면 import 전 그대로 되돌린다(이유는 §2.43).

**파일**: `app/tests/test_research_runner.py` — 전체 588줄

```python
"""test_research_runner.py — 단계 오케스트레이션

async 테스트는 `asyncio.run` 으로 돈다. `@pytest.mark.asyncio` 를 쓰면 안
된다 — `pytest-asyncio` 가 이 저장소에 설치돼 있지 않고, 플러그인이 없으면
pytest 는 코루틴 본문을 **실행하지 않는다** — 로컬 pytest 9.1.1 은 `async def
functions are not natively supported` 로 실패 처리하고, 예전 판본은 경고만 남긴
채 통과시켰다. 어느 쪽이든 검증은 일어나지 않으므로 관례(`test_research_explorer.py`)
를 그대로 따른다.

relay 는 모듈 최상단에서 import 하지 않는다. `redis` 는 requirements 에만
있고 로컬 venv 에는 없어서, 최상단 import 는 수집 단계에서 세션을 통째로
죽인다(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).
"""
import asyncio
import importlib
import json
import sys
import types
from unittest.mock import MagicMock

import pytest

from services.research.critic import Verdict
from services.research.runner import explore_subquestion
from services.research.state import ResearchState, SubQuestion, merge_params


class _FakeCritic:
    """항상 부족을 반환하는 critic — 루프 상한을 검증한다. 제안은 매번 새 검색어다."""

    def __init__(self):
        self.calls = 0
        self.seen: list[list] = []

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        self.seen.append(evidence)
        return Verdict("insufficient", note="부족", new_queries=[f"다른 검색어 {self.calls}"])


class _SuggestingCritic:
    """정해진 제안 목록을 매번 그대로 내는 critic — 중복 제안 처리를 검증한다."""

    def __init__(self, suggestions):
        self.calls = 0
        self._suggestions = suggestions

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        return Verdict("insufficient", note="부족", new_queries=list(self._suggestions))


class _FakeDb:
    """runner 가 읽기 트랜잭션을 언제 닫는지만 기록한다."""

    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


class _ParseFailedCritic:
    """판정을 못 읽은 critic — `critic._failed()` 가 내는 형태 그대로다."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        return Verdict("sufficient", note="자동 점검을 완료하지 못했다", parse_failed=True)


def _hits(cnts_ids, *, query="q", scores=None):
    scores = scores or [0.9] * len(cnts_ids)
    hits = [
        {"book_id": cid, "chunk_id": f"{cid}-c-{query}", "text": f"{cid} 의 '{query}' 대목",
         "page_start": 1, "page_end": 1, "score": s, "rank_score": s}
        for cid, s in zip(cnts_ids, scores)
    ]
    meta = {
        cid: {"title": f"논문 {cid}", "pub_date": "2008-06", "kci_citations": 3}
        for cid in cnts_ids
    }
    return hits, meta


async def _fake_explore(query, *, params, db):
    return _hits(["A"], query=query)


async def _empty_explore(query, *, params, db):
    return [], {}


class TestExploreSubquestion:
    def test_always_insufficient_stops_at_max_recheck(self):
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="하위질문")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_fake_explore, critique_fn=critic, emit=None,
        ))
        assert critic.calls == 3            # 최초 1 + 재검색 2
        assert sq.queries == ["하위질문", "다른 검색어 1", "다른 검색어 2"]
        assert sq.verdict == "insufficient"
        assert sq.note == "부족"            # note 가 그대로 보고서의 한계 문장이 된다

    def test_no_hits_records_no_evidence(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq = SubQuestion(idx=0, text="하위질문")
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_empty_explore,
            critique_fn=_FakeCritic(), emit=None,
        ))
        assert sq.evidence_ids == []

    def test_same_paper_in_two_subquestions_reuses_one_evidence(self):
        """한 논문이 두 하위질문에서 나와도 근거는 하나다.

        중복 생성하면 같은 출처가 E1 과 E2 로 갈라져 인용칩이 어긋난다.
        """
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        assert len(st.evidence) == 1
        assert sq1.evidence_ids == sq2.evidence_ids == ["E1"]
        assert len({ev.cnts_id for ev in st.evidence.values()}) == 1

    def test_recheck_does_not_duplicate_same_paper(self):
        """재검색에서 같은 논문이 또 나와도 evidence_ids 에 두 번 들어가지 않는다."""
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="가")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_fake_explore,
                                        critique_fn=_FakeCritic(), emit=None))
        assert sq.evidence_ids == ["E1"]

    def test_max_evidence_caps_growth(self):
        async def _many(query, *, params, db):
            return _hits([f"B{i}" for i in range(10)], query=query)

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 4}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None,
            explore_fn=_many, critique_fn=_FakeCritic(), emit=None,
        ))
        assert len(st.evidence) == 4

    def test_cap_reached_still_links_already_adopted_paper(self):
        """상한에 닿은 뒤 나온 후보도 '이미 있는 근거'면 링크는 붙는다.

        상한 검사를 break 로 끊으면 그 뒤 후보를 아예 보지 못하고 지나가서,
        다른 하위질문에서 이미 채택된 논문인데도 이 하위질문만 링크를 잃는다.
        재사용은 총량을 늘리지 않으므로 상한과 무관한 손실이다.
        """
        by_query = {"가": ["A"], "나": ["B", "C", "A"]}

        async def _by_query(query, *, params, db):
            return _hits(by_query[query], query=query)

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 2}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=_by_query,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=_by_query,
                                        critique_fn=critic, emit=None))
        assert sq1.evidence_ids == ["E1"]
        assert sq2.evidence_ids == ["E2", "E1"]     # B 는 새로, C 는 상한에 막히고, A 는 재사용
        assert len(st.evidence) == 2

    def test_parse_failed_verdict_propagates_to_subquestion(self):
        """판정 파싱 실패 표시가 하위질문까지 올라와야 한다.

        `synthesizer.build_limitations` 는 `sq.parse_failed` 만 본다. 여기서
        옮기지 않으면 자기점검이 전부 실패해도 보고서가 "한계 없음"이 된다.
        """
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="가")
        critic = _ParseFailedCritic()
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        assert sq.parse_failed is True
        # 파싱 실패는 verdict="sufficient" 로 떨어지므로 루프가 한 바퀴에 끝난다 —
        # 그래서 마지막 라운드의 값만 옮겨도 표시가 유실되지 않는다.
        assert critic.calls == 1

    def test_emit_is_called_for_progress(self):
        events = []

        async def _emit(kind, payload):
            events.append((kind, payload))

        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None, explore_fn=_fake_explore,
            critique_fn=_FakeCritic(), emit=_emit,
        ))
        kinds = [k for k, _ in events]
        assert "search" in kinds and "critique" in kinds
        by_kind = dict(events)
        assert by_kind["search"] == {"subq_idx": 0, "query": "가", "found": 1}
        assert by_kind["critique"]["verdict"] == "insufficient"
        assert by_kind["critique"]["adopted"] == 1

    def test_critique_event_carries_unchecked_and_capped_flags(self):
        """'모델이 충분하다고 판단'과 '판정을 못 받음'을 note 문자열 없이 가를 수 있어야 한다."""
        events = []

        async def _emit(kind, payload):
            events.append((kind, payload))

        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None, explore_fn=_fake_explore,
            critique_fn=_ParseFailedCritic(), emit=_emit,
        ))
        critique = dict(events)["critique"]
        assert critique["parse_failed"] is True
        assert critique["capped"] == 0


class TestReadTransaction:
    def test_read_transaction_is_closed_before_critic_waits_on_llm(self):
        """워커 세션이 LLM 대기 내내 library_catalog 공유 잠금을 쥐면, FastAPI
        기동 시 ALTER TABLE library_catalog 가 막히고 그 뒤 모든 조회가 줄 선다."""
        db = _FakeDb()
        commits_at_critic = []

        async def _critic(subq, evidence, *, params):
            commits_at_critic.append(db.commits)
            return Verdict("sufficient", note="충분")

        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=db, explore_fn=_fake_explore,
            critique_fn=_critic, emit=None,
        ))
        assert commits_at_critic == [1]


class TestRequery:
    def test_already_tried_suggestion_is_skipped_for_the_next_one(self):
        """첫 제안이 이미 시도한 검색어면 같은 검색이 한 번 더 돌고 두 번째 제안은 버려진다."""
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 1}))
        sq = SubQuestion(idx=0, text="공공도서관 서비스 품질")
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_fake_explore,
            critique_fn=_SuggestingCritic(["공공도서관  서비스 품질", "LibQUAL+ 적용 사례"]),
            emit=None,
        ))
        assert sq.queries == ["공공도서관 서비스 품질", "LibQUAL+ 적용 사례"]

    def test_loop_stops_when_every_suggestion_was_tried(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 3}))
        sq = SubQuestion(idx=0, text="AI 윤리")
        critic = _SuggestingCritic(["ai 윤리", " AI  윤리 "])
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_fake_explore, critique_fn=critic, emit=None,
        ))
        assert sq.queries == ["AI 윤리"]
        assert critic.calls == 1


class TestEvidenceOrder:
    """evidence_ids 는 critic(20편)과 절(5편)이 앞에서 자른다 — 순서가 곧 선택이다."""

    def _run(self, rounds, *, max_recheck):
        async def _explore(query, *, params, db):
            ids, scores = rounds[query]
            return _hits(ids, query=query, scores=scores)

        class _Critic:
            def __init__(self):
                self.calls = 0

            async def __call__(self, subq, evidence, *, params):
                self.calls += 1
                return Verdict("insufficient", note="시기 편중",
                               new_queries=[f"r{self.calls + 1}"])

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": max_recheck}))
        sq = SubQuestion(idx=0, text="r1")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_explore,
                                        critique_fn=_Critic(), emit=None))
        return st, sq

    def _cnts(self, st, ids):
        return [st.evidence[e].cnts_id for e in ids]

    def test_best_new_paper_of_each_research_round_gets_a_front_seat(self):
        """점수만으로 자르면 자기점검이 부족하다고 해서 찾은 보완 논문이 절에서 빠진다.

        라운드마다 검색어가 달라 점수를 그대로 비교할 수도 없다.
        """
        rounds = {
            "r1": (["A", "B", "C", "D", "E", "F"], [0.95, 0.94, 0.93, 0.92, 0.91, 0.90]),
            "r2": (["G"], [0.40]),
        }
        st, sq = self._run(rounds, max_recheck=1)
        assert "G" in self._cnts(st, sq.evidence_ids[:5])
        assert self._cnts(st, sq.evidence_ids[:2]) == ["A", "G"]

    def test_rest_is_ordered_by_score_across_rounds(self):
        rounds = {
            "r1": (["A", "B", "C"], [0.50, 0.30, 0.20]),
            "r2": (["D", "E", "F"], [0.90, 0.80, 0.70]),
        }
        st, sq = self._run(rounds, max_recheck=1)
        assert self._cnts(st, sq.evidence_ids) == ["A", "D", "E", "F", "B", "C"]

    def test_round_leader_skips_papers_already_linked(self):
        # 2라운드 1위가 1라운드에서 이미 채택한 논문이면, 2라운드가 새로 보탠 것 중 1위가 자리를 받는다
        rounds = {
            "r1": (["A", "B", "C"], [0.9, 0.8, 0.7]),
            "r2": (["A", "D"], [0.95, 0.3]),
        }
        st, sq = self._run(rounds, max_recheck=1)
        assert self._cnts(st, sq.evidence_ids[:2]) == ["A", "D"]

    def test_critic_sees_ranked_order(self):
        rounds = {
            "r1": (["A", "B"], [0.5, 0.2]),
            "r2": (["C", "D"], [0.9, 0.8]),
        }

        async def _explore(query, *, params, db):
            ids, scores = rounds[query]
            return _hits(ids, query=query, scores=scores)

        critic = _FakeCritic()
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 1}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="r1"), db=None, explore_fn=_explore,
            critique_fn=_CriticWithQueries(critic, ["r2"]), emit=None,
        ))
        assert [e.cnts_id for e in critic.seen[-1]] == ["A", "C", "D", "B"]


class _CriticWithQueries:
    """_FakeCritic 의 기록은 그대로 두고 제안 검색어만 정해 준다."""

    def __init__(self, inner, queries):
        self._inner = inner
        self._queries = list(queries)

    async def __call__(self, subq, evidence, *, params):
        await self._inner(subq, evidence, params=params)
        q = self._queries.pop(0) if self._queries else "다른 검색어"
        return Verdict("insufficient", note="부족", new_queries=[q])


class TestSubquestionChunks:
    def test_reused_paper_uses_the_chunk_matched_in_this_subquestion(self):
        """재사용 근거의 발췌가 첫 하위질문 대목으로 고정되면, 다른 하위질문의
        critic 판정과 절 요약이 그 하위질문과 무관한 대목으로 만들어진다."""
        async def _explore(query, *, params, db):
            return _hits(["P"], query=query)

        critic = _FakeCritic()
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq1, sq2 = SubQuestion(idx=0, text="품질 측정"), SubQuestion(idx=1, text="만족도")
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=_explore,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=_explore,
                                        critique_fn=critic, emit=None))

        assert list(st.evidence) == ["E1"]
        assert sq1.evidence_chunks == {"E1": ["P-c-품질 측정"]}
        assert sq2.evidence_chunks == {"E1": ["P-c-만족도"]}
        assert {c.chunk_id for c in st.evidence["E1"].chunks} == {"P-c-품질 측정", "P-c-만족도"}
        assert critic.seen[1][0].chunks[0].text == "P 의 '만족도' 대목"

    def test_better_chunk_in_later_round_replaces_within_subquestion(self):
        by_query = {"가": 0.3, "다른 검색어 1": 0.9}

        async def _explore(query, *, params, db):
            return _hits(["P"], query=query, scores=[by_query[query]])

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 1, "chunks_per_evidence": 1}))
        sq = SubQuestion(idx=0, text="가")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_explore,
                                        critique_fn=_FakeCritic(), emit=None))
        assert sq.evidence_chunks == {"E1": ["P-c-다른 검색어 1"]}


class TestEvidenceCap:
    def _by_query(self, table):
        async def _explore(query, *, params, db):
            return _hits(table.get(query, []), query=query)
        return _explore

    def test_candidates_blocked_by_cap_are_counted(self):
        """상한에 막힌 것을 기록하지 않으면 보고서가 '근거를 찾지 못했다'(코퍼스 빈틈)로 쓴다."""
        explore = self._by_query({"가": ["A"], "나": ["B", "C", "A"]})
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 1}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=explore,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=explore,
                                        critique_fn=critic, emit=None))
        assert sq1.capped == 0
        assert sq2.capped == 2
        assert sq2.evidence_ids == ["E1"]

    def test_starved_subquestion_is_reported_as_capped_not_missing(self):
        from services.research.synthesizer import build_limitations

        explore = self._by_query({"가": ["A"], "나": ["B", "C"]})
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2, "max_evidence": 1}))
        st.subquestions = [SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")]
        critic = _FakeCritic()
        for sq in st.subquestions:
            asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=explore,
                                            critique_fn=critic, emit=None))
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "'나'" in x)
        assert "근거 상한(1편)" in line and "근거를 찾지 못했다" not in line
        assert critic.calls == 2                # 상한 뒤로는 어느 하위질문도 재검색하지 않는다

    def test_research_stops_once_cap_is_reached(self):
        """상한에 닿으면 새 근거가 생길 수 없다 — 재검색은 검색·LLM 호출만 태운다."""
        async def _many(query, *, params, db):
            return _hits([f"{query}-{i}" for i in range(3)], query=query)

        critic = _FakeCritic()
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 3, "max_evidence": 2}))
        sq = SubQuestion(idx=0, text="가")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_many,
                                        critique_fn=critic, emit=None))
        assert critic.calls == 1
        assert sq.queries == ["가"]
        assert sq.capped == 1


_RELAY = "services.research.relay"


def _forget_on_teardown(monkeypatch, name: str) -> None:
    """name 을 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 있던 키만 되돌린다. 원래 없던 키는 기록이 남지 않아
    여기서 새로 import 한 모듈(더미 redis 에 묶인 채)이 teardown 뒤에도 남는다.
    setitem·setattr 은 원래 없던 키·속성이면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을
    남긴 뒤 뺀다. 부모 속성까지 되돌리는 이유: `from pkg import mod` 와 문자열 경로
    monkeypatch 는 sys.modules 보다 부모 속성을 먼저 본다.
    """
    parent, _, child = name.rpartition(".")
    monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
    monkeypatch.setitem(sys.modules, name, None)
    del sys.modules[name]


def _load_relay(monkeypatch):
    """`redis` 미설치 환경에서만 더미를 꽂아 relay 를 새로 import 한다. 앞 테스트가 남긴
    relay 를 물려받지 않고, 끝나면 import 전 그대로 되돌린다(_forget_on_teardown)."""
    for name in ("redis", "redis.asyncio"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    _forget_on_teardown(monkeypatch, _RELAY)
    return importlib.import_module(_RELAY)


class _FakeRedis:
    def __init__(self, publish_error=None):
        self.published = []
        self.closed = False
        self._publish_error = publish_error

    async def publish(self, channel, data):
        if self._publish_error is not None:
            raise self._publish_error
        self.published.append((channel, data))

    async def aclose(self):
        self.closed = True


class TestRelayPublish:
    def test_publishes_kind_and_payload_to_job_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        client = _FakeRedis()
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)

        asyncio.run(relay.publish("job-1", "search", {"subq_idx": 0, "query": "한글"}))

        channel, data = client.published[0]
        assert channel == "research:job-1"
        assert json.loads(data) == {"kind": "search", "subq_idx": 0, "query": "한글"}
        assert "한글" in data              # ensure_ascii=False — 로그·SSE 에서 읽혀야 한다
        assert client.closed is True

    def test_publish_error_is_swallowed_and_client_closed(self, monkeypatch):
        """중계는 장식이고 보고서는 아니다 — publish 실패가 잡을 죽이면 안 된다."""
        relay = _load_relay(monkeypatch)
        client = _FakeRedis(publish_error=RuntimeError("연결 끊김"))
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)

        assert asyncio.run(relay.publish("job-1", "search", {})) is None
        assert client.closed is True

    def test_connect_error_is_swallowed(self, monkeypatch):
        relay = _load_relay(monkeypatch)

        def _boom(url):
            raise OSError("redis 없음")

        monkeypatch.setattr(relay.aioredis, "from_url", _boom)
        assert asyncio.run(relay.publish("job-1", "done", {})) is None


class TestRelayLoaderIsolation:
    """_load_relay 가 끝나면 sys.modules·부모 패키지 속성이 import 전 그대로여야 한다 —
    더미 redis 에 묶인 relay 가 남으면 뒤에 도는 테스트가 그것을 물려받는다."""

    def test_module_that_was_absent_is_gone_afterwards(self):
        parent = importlib.import_module("services.research")
        with pytest.MonkeyPatch.context() as outer:
            outer.delitem(sys.modules, _RELAY, raising=False)
            outer.delattr(parent, "relay", raising=False)
            with pytest.MonkeyPatch.context() as mp:
                _load_relay(mp)
            assert _RELAY not in sys.modules
            assert not hasattr(parent, "relay")

    def test_module_that_was_loaded_comes_back(self):
        parent = importlib.import_module("services.research")
        original = types.ModuleType(_RELAY)
        with pytest.MonkeyPatch.context() as outer:
            outer.setitem(sys.modules, _RELAY, original)
            outer.setattr(parent, "relay", original, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                assert _load_relay(mp) is not original
            assert sys.modules[_RELAY] is original
            assert parent.relay is original


class TestSharedChunkScore:
    """두 하위질문이 같은 청크를 매칭하면, 뒤 하위질문의 재검색은 그 청크를 자기 점수로 비교한다."""

    def test_research_does_not_swap_out_a_better_passage(self):
        table = {"A": [("P-c1", 0.2)], "B": [("P-c1", 0.95)], "B2": [("P-c2", 0.5)]}

        async def _explore(query, *, params, db):
            hits = [{"book_id": "P", "chunk_id": cid, "text": cid, "page_start": 1,
                     "page_end": 1, "score": s, "rank_score": s} for cid, s in table[query]]
            return hits, {"P": {"title": "P"}}

        class _Once:
            def __init__(self, new_queries):
                self.calls = 0
                self._new = new_queries

            async def __call__(self, subq, evidence, *, params):
                self.calls += 1
                if self.calls == 1 and self._new:
                    return Verdict("insufficient", note="부족", new_queries=self._new)
                return Verdict("sufficient")

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 1, "chunks_per_evidence": 1}))
        a, b = SubQuestion(idx=0, text="A"), SubQuestion(idx=1, text="B")
        st.subquestions = [a, b]
        asyncio.run(explore_subquestion(st, a, db=None, explore_fn=_explore,
                                        critique_fn=_Once([]), emit=None))
        asyncio.run(explore_subquestion(st, b, db=None, explore_fn=_explore,
                                        critique_fn=_Once(["B2"]), emit=None))

        assert b.evidence_chunks == {"E1": ["P-c1"]}
        assert b.chunk_scores == {"P-c1": 0.95}
        assert a.chunk_scores == {"P-c1": 0.2}
```
```bash
$ python -m pytest app/tests/test_research_runner.py -q
27 passed, 2 warnings in 0.63s
```

### 2.42 `test_research_relay.py` — 종료 프레임·타임아웃·채널

9건. 리뷰에서 새로 만든 파일이다. 리뷰가 짚은 중계 결함 셋(종료 프레임 두 모양, 소켓 타임아웃 없음, 비표준 UUID 구독)에 맞춰 relay 쪽 계약을 고정한다. 비표준 UUID 문제 자체는 API 가 고쳤고(§2.37 ④), 여기서는 UUID 와 그 표준형 문자열이 같은 채널이라는 전제만 본다.

- `TestTerminalEvent` — 상태별 kind 매핑, **`TERMINAL_KIND` 의 키가 `models.research.TERMINAL_STATUSES` 와 같은지**(종료 상태를 하나 더 만들면 매핑을 빠뜨릴 수 없다), `error` 200자 절단, `publish_terminal` 이 `terminal_event` 와 같은 모양을 내는지.
- `TestPublishTimeout` — publish 가 붙는 URL 에 두 타임아웃이 있는지, URL 에 운영자가 준 값·인증·DB 번호를 덮지 않는지.
- `TestChannel` — `uuid.UUID` 와 그 표준형 문자열이 같은 채널인지.
- `TestLoaderIsolation` — 로더가 끝난 뒤 `sys.modules`·부모 패키지 속성이 원래대로인지.

**파일**: `app/tests/test_research_relay.py` — 전체 150줄

```python
"""test_research_relay.py — 진행 중계의 종료 이벤트 모양과 publish 타임아웃

`redis` 는 로컬 venv 에 없다. 미설치일 때만 더미를 꽂고 relay 를 새로 import 한다
(test_research_runner.py 의 _load_relay 와 같은 방식).
"""
import asyncio
import importlib
import json
import sys
import types
import uuid
from urllib.parse import parse_qs, urlsplit
from unittest.mock import MagicMock

import pytest

_RELAY = "services.research.relay"


def _forget_on_teardown(monkeypatch, name: str) -> None:
    """name 을 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 있던 키만 되돌린다. 원래 없던 키는 기록이 남지 않아
    여기서 새로 import 한 모듈(더미 redis 에 묶인 채)이 teardown 뒤에도 남는다.
    setitem·setattr 은 원래 없던 키·속성이면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을
    남긴 뒤 뺀다. 부모 속성까지 되돌리는 이유: `from pkg import mod` 와 문자열 경로
    monkeypatch 는 sys.modules 보다 부모 속성을 먼저 본다.
    """
    parent, _, child = name.rpartition(".")
    monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
    monkeypatch.setitem(sys.modules, name, None)
    del sys.modules[name]


def _load_relay(monkeypatch):
    for name in ("redis", "redis.asyncio"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    _forget_on_teardown(monkeypatch, _RELAY)
    return importlib.import_module(_RELAY)


class _FakeRedis:
    def __init__(self):
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel, data):
        self.published.append((channel, data))

    async def aclose(self):
        return None


class TestTerminalEvent:
    """같은 종료 상태는 연결 시점과 상관없이 한 모양으로 나가야 한다."""

    def test_each_terminal_status_maps_to_one_kind(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        assert relay.terminal_event("completed") == {"kind": "done", "status": "completed"}
        assert relay.terminal_event("canceled") == {"kind": "canceled", "status": "canceled"}
        assert relay.terminal_event("failed", "boom") == {
            "kind": "failed", "status": "failed", "error": "boom",
        }

    def test_every_terminal_status_has_a_kind(self, monkeypatch):
        from models.research import TERMINAL_STATUSES
        relay = _load_relay(monkeypatch)
        assert set(relay.TERMINAL_KIND) == set(TERMINAL_STATUSES)

    def test_error_is_truncated(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        assert len(relay.terminal_event("failed", "x" * 5000)["error"]) == 200

    def test_publish_terminal_sends_the_same_shape(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        client = _FakeRedis()
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)
        jid = uuid.uuid4()

        asyncio.run(relay.publish_terminal(jid, "failed", "종합 실패"))

        channel, data = client.published[0]
        assert channel == f"research:{jid}"
        assert json.loads(data) == relay.terminal_event("failed", "종합 실패")


class TestPublishTimeout:
    """응답 없는 Redis 는 예외가 아니라 hang 이라 삼킬 기회조차 없다 — 소켓 타임아웃이 필요하다."""

    def test_publish_connects_with_socket_timeouts(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        seen = {}

        def _from_url(url):
            seen["url"] = url
            return _FakeRedis()

        monkeypatch.setattr(relay.aioredis, "from_url", _from_url)
        asyncio.run(relay.publish(uuid.uuid4(), "search", {}))

        query = parse_qs(urlsplit(seen["url"]).query)
        assert float(query["socket_timeout"][0]) > 0
        assert float(query["socket_connect_timeout"][0]) > 0

    def test_existing_query_is_kept(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        url = relay._with_timeouts("redis://:pw@redis:6379/0?socket_timeout=9&db=0")
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        assert parts.netloc == ":pw@redis:6379" and parts.path == "/0"
        assert query["socket_timeout"] == ["9"]       # 운영자가 URL 에 준 값은 덮지 않는다
        assert "socket_connect_timeout" in query


class TestChannel:
    def test_uuid_and_its_canonical_string_share_a_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        jid = uuid.uuid4()
        assert relay.channel(jid) == relay.channel(str(jid)) == f"research:{jid}"


class TestLoaderIsolation:
    """_load_relay 가 끝나면 sys.modules·부모 패키지 속성이 import 전 그대로여야 한다.

    더미 redis 에 묶인 relay 가 남으면 뒤에 도는 테스트가 더미 없이 import 해도 그
    Mock 결합 모듈을 물려받는다 — 로컬에서만, 실행 순서에 따라 결과가 달라진다.
    """

    def test_module_that_was_absent_is_gone_afterwards(self):
        parent = importlib.import_module("services.research")
        with pytest.MonkeyPatch.context() as outer:
            outer.delitem(sys.modules, _RELAY, raising=False)
            outer.delattr(parent, "relay", raising=False)
            with pytest.MonkeyPatch.context() as mp:
                _load_relay(mp)
            assert _RELAY not in sys.modules
            assert not hasattr(parent, "relay")

    def test_module_that_was_loaded_comes_back(self):
        parent = importlib.import_module("services.research")
        original = types.ModuleType(_RELAY)
        with pytest.MonkeyPatch.context() as outer:
            outer.setitem(sys.modules, _RELAY, original)
            outer.setattr(parent, "relay", original, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                assert _load_relay(mp) is not original   # 앞 테스트의 모듈을 물려받지 않는다
            assert sys.modules[_RELAY] is original
            assert parent.relay is original
```
```bash
$ python -m pytest app/tests/test_research_relay.py -q
9 passed, 1 warning in 0.48s
```

### 2.43 `test_research_tasks.py` — 워커 분기

**무엇을 고정하나.** 43건.

| 클래스 | 고정하는 계약 |
|---|---|
| `TestNextSeq` | seq 는 DB 의 `max(seq)+1` 이지 상수가 아니다 |
| `TestResumeFromSnapshot` | `stage=explored` 면 탐색을 건너뛰고 스냅샷의 하위질문으로 종합, 스냅샷이 없으면 탐색으로 되돌아감, 체크포인트를 쓴다, 엔진 `dispose` 1회 |
| `TestClaim` | 선점 실패는 `skipped`, 워커가 받는 상태가 API 가 쓰는 상수다 |
| `TestConditionalTransition` | 전이 SQL 에 `research_jobs.status IN` 이 있다, `canceled` 잡은 건드리지 않는다 |
| `TestCancel` | §2.36 ③ 의 네 곳(계획 중 취소만 `TestPlan`) |
| `TestFailure` | 종합 실패가 체크포인트를 남기고 이어서 돌리면 탐색 없이 종합만, 전멸은 `failed`·체크포인트 없음, 근거를 모은 실패는 전멸이 아님, 전멸 스냅샷은 재탐색, 빈 계획 사유, step result 의 `capped`, 부분 실패는 완료, 롤백 뒤 기록, 가드 밖 예외는 `failed` |
| `TestTimeout` | `asyncio.run` 밖의 소프트 리밋·데드라인 모두 `failed`, 시간 초과가 취소를 덮지 않는다, `JOB_DEADLINE ≤ SOFT_LIMIT - 60` |
| `TestPlan` | 계획 성공은 `awaiting_approval`, 실패는 `failed`, 계획 중 취소는 되살아나지 않는다 |
| `TestReaper` | `STALE_MINUTES * 60 > HARD_LIMIT`, 잡 회수 문장이 step 도 닫는다 |
| `TestQueue` | 기본 큐 `q_llm`, 설정을 따른다, 계획 큐 분리, 빈 계획 큐는 실행 큐를 따른다 — 적재 단계 라우팅은 그대로 |
| `TestStageGuard`·`TestLoaderIsolation` | 모르는 stage 거부, 로더 격리 |

리뷰 전 이 파일은 `_next_seq`·재개 분기·선점·`_set_stage` 만 봤다. 취소·실패·시간 초과·회수·계획 분기가 0건이었고, `_SoftTimeLimitExceeded` 대역은 정의만 있고 한 번도 발생시키지 않았다 — 취소 덮어쓰기(high)와 전멸 `completed` 가 테스트 없이 통과한 이유다.

**대역이 `WHERE` 를 평가한다 — 이 파일의 핵심.** 취소 덮어쓰기는 "status 조건이 빠진 UPDATE"로 생기는 회귀다. 대역 세션이 `execute` 를 기록만 하고 조건을 무시하면, 조건을 지워도 테스트가 그대로 통과한다. 그래서 `_FakeSession` 은 `research_jobs` 에 대한 UPDATE 와 status 조회에 한해 **SQLAlchemy 문장 객체의 `whereclause` 를 실제로 평가한다.**

- `_matches` 가 `BooleanClauseList`(AND)를 재귀로 내려가며 `eq`·`in_op`·`is_not` 을 대역 잡의 속성과 비교한다. 모르는 연산자면 참으로 넘기지 않고 `AssertionError` 를 낸다 — 코드가 새 조건을 쓰면 대역을 고치라고 알려야지, 조용히 통과시키면 안 된다.
- `_update_job` 은 조건이 맞을 때만 `stmt._values` 를 대역 잡에 적용하고 rowcount 를 1·0 으로 돌려준다. 그래서 워커의 `_transition` 이 0행을 보고 `_stopped` 로 가는 경로가 실제로 돈다.
- 테스트는 `_patch_pipeline` 의 `explore=`·`synthesize=` 훅(또는 `_claim` 대역) 안에서 `job.status = "canceled"` 를 찍어 "그 구간 도중에 API 가 취소를 커밋했다"를 흉내 낸다.

실제로 확인했다. 워커와 API 의 `_transition` 두 곳에서 `ResearchJob.status.in_(expect)` 를 지우면(저장소 사본에서) 이 파일 7건과 §2.44 의 2건, 합계 9건이 실패한다 — 선점 skip, 조건부 전이 둘, 마지막 하위질문 중 취소, 종합 뒤 취소, 시간 초과가 취소를 덮지 않음, 계획 중 취소, 승인과 경쟁한 취소, 끝난 잡 취소 409.

**트랜잭션도 추적한다.** `_FakeSession.in_txn` 은 `execute`·`get` 에서 참, `commit`·`rollback` 에서 거짓이 된다. `_patch_pipeline` 이 끼우는 `explore_subquestion`·`synthesize` 대역과 `TestPlan` 의 `make_plan` 대역은 들어오자마자 `assert not session.in_txn` 한다 — LLM 을 기다리기 전에 읽기 트랜잭션이 닫혔는가(함정 18번)를 워커 단위에서 본다. `_finish` 대역은 기록 시점의 롤백 횟수를 함께 남겨 "롤백 뒤 기록"을 단언한다.

**더미 import 와 격리.** `workers.research_tasks` 는 celery(데코레이터)와 redis(relay)를 물고 온다. 둘 다 로컬 venv 에 없어 최상단에서 import 하면 collection 단계에서 세션 전체가 0건이 된다(함정 13번). `_load_tasks` 는 미설치일 때만 더미를 꽂고 함수 안에서 import 한다. `_FakeCelery.task` 는 원함수를 돌려주면서 데코레이터 옵션을 속성으로 붙여, `run_deep_research.queue` 를 단언할 수 있게 한다(`fake_celery=True`). `_SoftTimeLimitExceeded` 가 `MagicMock` 이 아니라 진짜 예외 클래스인 이유는 `MagicMock` 을 `except` 절에 쓰면 `TypeError` 가 나기 때문이다.

`_forget_on_teardown` 은 리뷰의 테스트 격리 지적에서 나왔다. `monkeypatch.delitem` 은 **원래 있던 키만** 되돌린다 — 원래 없던 키는 기록이 남지 않아, 테스트가 새로 import 한 모듈(더미 celery·redis 에 묶인 채)이 세션 끝까지 남고 뒤 순서 파일이 그것을 물려받았다. 로컬에서만, 실행 순서에 따라 결과가 달라지는 종류다. `setitem`·`setattr` 은 원래 없던 키면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을 남긴 뒤 뺀다. 부모 패키지 속성까지 되돌리는 이유는 `from pkg import mod` 와 문자열 경로 monkeypatch 가 `sys.modules` 보다 부모 속성을 먼저 보기 때문이다. `TestLoaderIsolation` 이 두 방향(원래 없던 모듈은 사라지고, 원래 있던 모듈은 돌아온다)을 고정한다.

**파일**: `app/tests/test_research_tasks.py` — 전체 994줄

```python
"""test_research_tasks.py — 딥리서치 Celery 태스크

`workers.research_tasks` 는 celery(태스크 데코레이터)와 redis(relay) 를 물고
온다. 둘 다 로컬 venv 에 없어서 최상단에서 import 하면 pytest 가 **collection
단계에서** 죽고 세션 전체가 0건이 된다(`docs/ops/recurring-gotchas.md` 13번).
그래서 미설치일 때만 더미를 꽂고 함수 안에서 import 한다
(test_embed_index_guard.py·test_search_chunk_answer_flag.py 와 같은 방식).

DB 는 대역으로 세운다. 대역은 research_jobs 의 UPDATE·status 조회에 한해 WHERE 를
실제로 평가한다 — 취소가 워커의 최종 쓰기에 덮이는 회귀는 status 조건이 빠진
UPDATE 로 생기는데, 대역이 조건을 무시하면 그 회귀를 못 잡는다.
"""
import asyncio
import importlib
import sys
import types
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BindParameter, BooleanClauseList

from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, snapshot_state,
)

_CACHED = ("workers.research_tasks", "workers.celery_app", "services.research.relay")


class _SoftTimeLimitExceeded(Exception):
    """celery 미설치 환경용 대역. MagicMock 을 except 절에 쓰면 TypeError 가 난다."""


class _FakeConf:
    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class _FakeCelery:
    """task 데코레이터가 원함수를 돌려준다. 옵션은 Celery 처럼 속성으로 붙인다."""

    def __init__(self, *a, **kw):
        self.conf = _FakeConf()

    def task(self, *a, **kw):
        def _decorator(fn):
            for key, value in kw.items():
                setattr(fn, key, value)
            return fn
        return _decorator


def _stub_missing(monkeypatch, name: str, module=None) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module or MagicMock())


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 있던 키만 되돌린다. 원래 없던 키는 기록이 남지 않아
    여기서 새로 import 한 모듈(더미 celery·redis 에 묶인 채)이 teardown 뒤에도 남는다.
    setitem·setattr 은 원래 없던 키·속성이면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을
    남긴 뒤 뺀다. 부모 속성까지 되돌리는 이유: `from pkg import mod` 와 문자열 경로
    monkeypatch 는 sys.modules 보다 부모 속성을 먼저 본다.
    """
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


def _load_tasks(monkeypatch, *, fake_celery: bool = False):
    """research_tasks 를 새로 import 한다. 앞 테스트가 남긴 모듈을 물려받지 않고, 끝나면
    import 전 그대로 되돌린다(_forget_on_teardown).

    fake_celery=True 면 celery 가 설치됐거나 다른 테스트가 더미를 꽂아 뒀어도
    이 파일의 _FakeCelery 를 쓴다 — 태스크 옵션·라우팅을 단언할 때 필요하다."""
    celery_mod = types.ModuleType("celery")
    celery_mod.Celery = _FakeCelery
    celery_exc = types.ModuleType("celery.exceptions")
    celery_exc.SoftTimeLimitExceeded = _SoftTimeLimitExceeded
    if fake_celery:
        monkeypatch.setitem(sys.modules, "celery", celery_mod)
        monkeypatch.setitem(sys.modules, "celery.exceptions", celery_exc)
    _stub_missing(monkeypatch, "celery", celery_mod)
    _stub_missing(monkeypatch, "celery.exceptions", celery_exc)
    _stub_missing(monkeypatch, "redis")
    _stub_missing(monkeypatch, "redis.asyncio")
    _forget_on_teardown(monkeypatch, _CACHED)
    return importlib.import_module("workers.research_tasks")


# ── DB 대역 ────────────────────────────────────────────────────────────
def _matches(clause, obj) -> bool:
    if clause is None:
        return True
    if isinstance(clause, BooleanClauseList):
        return all(_matches(c, obj) for c in clause.clauses)
    left = getattr(obj, clause.left.key)
    right = getattr(clause.right, "value", None)
    op = clause.operator
    if op is operators.eq:
        return left == right
    if op is operators.in_op:
        return left in right
    if op is operators.is_not:
        return left is not None
    raise AssertionError(f"대역이 모르는 연산자: {op}")


class _Result:
    def __init__(self, value=None, rowcount: int = 0):
        self._value = value
        self.rowcount = rowcount

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    """execute 를 기록하고, research_jobs 의 조건부 UPDATE·status 조회를 흉내 낸다.

    in_txn 은 "읽기 트랜잭션이 열려 있는가"다. LLM 을 기다리는 동안 이게 참이면
    library_catalog 잠금을 쥔 채 FastAPI 기동 DDL 을 막는다.
    """

    def __init__(self, *, job=None, scalar=None):
        self.job = job
        self.scalar = scalar
        self.sql: list[str] = []
        self.params: list[dict] = []
        self.commits = 0
        self.rollbacks = 0
        self.in_txn = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt, params=None):
        self.sql.append(str(stmt))
        self.params.append(params)
        self.in_txn = True
        table = getattr(getattr(stmt, "table", None), "name", None)
        if getattr(stmt, "is_update", False) and table == "research_jobs":
            return _Result(rowcount=self._update_job(stmt))
        if str(stmt).startswith("SELECT research_jobs.status"):
            hit = self.job is not None and _matches(stmt.whereclause, self.job)
            return _Result(self.job.status if hit else None)
        return _Result(self.scalar)

    def _update_job(self, stmt) -> int:
        if self.job is None or not _matches(stmt.whereclause, self.job):
            return 0
        for key, value in stmt._values.items():
            setattr(self.job, getattr(key, "key", key),
                    value.value if isinstance(value, BindParameter) else value)
        return 1

    async def get(self, model, pk):
        self.in_txn = True
        return self.job

    async def commit(self):
        self.commits += 1
        self.in_txn = False

    async def rollback(self):
        self.rollbacks += 1
        self.in_txn = False

    def add(self, obj):
        return None


class _FakeEngine:
    def __init__(self):
        self.disposed = 0

    async def dispose(self):
        self.disposed += 1


class _FakeJob:
    """ResearchJob 대역 — 태스크가 실제로 읽고 쓰는 필드만 가진다."""

    def __init__(self, *, stage, plan, state_snapshot=None, status="approved"):
        self.id = uuid.uuid4()
        self.question = "독서 격차 연구는 어디까지 왔나"
        self.params = {}
        self.plan = plan
        self.stage = stage
        self.state_snapshot = state_snapshot
        self.status = status
        self.report = None
        self.last_error = None
        self.started_at = None
        self.finished_at = None


def _explored_snapshot() -> dict:
    st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
    st.subquestions = [
        SubQuestion(idx=0, text="스냅샷 하위1", queries=["q1"], evidence_ids=["E0"],
                    verdict="sufficient", note="충분"),
        SubQuestion(idx=1, text="스냅샷 하위2", failed=True),
    ]
    st.evidence = {
        "E0": Evidence(id="E0", cnts_id="A", meta={"title": "논문 가"},
                       chunks=[Chunk("c1", "본문", 3, 4, 0.8)]),
    }
    return snapshot_state(st)


class _Harness:
    def __init__(self, session, engine):
        self.session = session
        self.engine = engine
        self.events: list[tuple] = []
        self.steps: list[tuple] = []
        self.finished: list[tuple] = []


def _patch_pipeline(monkeypatch, rt, *, job, explored: list, synthesized: list,
                    explore=None, synthesize=None) -> _Harness:
    """DB·Redis·LLM 을 대역으로 바꾸고 호출만 기록한다.

    explore·synthesize 로 하위 동작을 끼워 넣는다(취소를 찍거나 예외를 던지는 식).
    """
    session = _FakeSession(job=job, scalar=0)
    h = _Harness(session, _FakeEngine())
    monkeypatch.setattr(rt, "_job_engine", lambda: (h.engine, lambda: session))

    async def _next_seq(db, job_id):
        return 3

    async def _step(db, job_id, seq, kind, title, *, subq_idx=None, detail=None):
        h.steps.append((kind, title))
        return len(h.steps)

    async def _finish(db, step_id, status, result=None):
        # 롤백 없이 쓰면 깨진 트랜잭션 위에서 다시 터진다 — 몇 번 롤백한 뒤였는지 남긴다
        h.finished.append((step_id, status, result, session.rollbacks))

    async def _corpus_range(db):
        return {"from": "2002", "to": "2026", "n_papers": 7}

    async def _publish(job_id, kind, payload):
        h.events.append((kind, payload))

    async def _publish_terminal(job_id, status, error=None):
        h.events.append(("terminal", status, error))

    async def _explore(state, subq, *, db, emit=None):
        assert not session.in_txn, "탐색(LLM) 직전에 읽기 트랜잭션이 열려 있다"
        explored.append(subq.text)
        if explore is not None:
            await explore(state, subq)
        return subq

    async def _synthesize(state, *, should_stop=None):
        assert not session.in_txn, "종합(LLM) 직전에 읽기 트랜잭션이 열려 있다"
        synthesized.append(state)
        if synthesize is not None:
            return await synthesize(state, should_stop)
        return {"sections": []}

    for name, fn in (
        ("_next_seq", _next_seq), ("_step", _step), ("_finish", _finish),
        ("_corpus_range", _corpus_range), ("publish", _publish),
        ("publish_terminal", _publish_terminal),
        ("explore_subquestion", _explore), ("synthesize", _synthesize),
    ):
        monkeypatch.setattr(rt, name, fn)
    return h


def _terminals(h: _Harness) -> list[tuple]:
    return [e[1:] for e in h.events if e[0] == "terminal"]


class TestNextSeq:
    """seq 를 1 로 되돌리면 uq_research_steps_job_seq 를 위반해 재시도가 죽는다."""

    def test_returns_value_from_db_not_a_constant(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=7)
        assert asyncio.run(rt._next_seq(db, uuid.uuid4())) == 7

    def test_empty_table_starts_at_zero(self, monkeypatch):
        # coalesce(max(seq), -1) + 1 — step 이 없는 잡은 0 에서 시작한다
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=0)
        assert asyncio.run(rt._next_seq(db, uuid.uuid4())) == 0

    def test_query_continues_from_max_for_this_job(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=5)
        jid = uuid.uuid4()
        asyncio.run(rt._next_seq(db, jid))
        assert "max(seq)" in db.sql[0]
        assert "job_id = :j" in db.sql[0]
        # UUID 로 넘긴다 — 문자열을 넘기면 드라이버 쪽 변환에 기대게 된다
        assert db.params[0] == {"j": jid}


class TestResumeFromSnapshot:
    """stage="explored" 로 다시 들어온 잡은 탐색을 건너뛰고 종합부터 간다.

    이 분기가 없으면 stage·state_snapshot 은 쓰기만 하고 아무도 안 읽는
    컬럼이 되고, 종합 실패가 5~7분짜리 탐색을 매번 버린다.
    """

    def test_explored_job_skips_exploration(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=_explored_snapshot(), status="queued")
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        # plan 을 일부러 채워 뒀다 — 재개 분기를 지우면 여기서 2건이 탐색된다
        assert explored == []
        assert len(synthesized) == 1
        assert out["status"] == "completed"
        assert job.status == "completed"
        assert job.stage == "synthesized"

    def test_resumed_state_comes_from_the_snapshot(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=_explored_snapshot(), status="queued")
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        asyncio.run(rt._run_deep_research(str(job.id)))

        state = synthesized[0]
        # plan 이 아니라 스냅샷에서 살아난 하위질문이어야 한다
        assert [sq.text for sq in state.subquestions] == ["스냅샷 하위1", "스냅샷 하위2"]
        assert state.subquestions[1].failed is True
        assert state.evidence["E0"].chunks[0].page_start == 3

    def test_planned_job_runs_the_exploration_loop(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1", "계획 하위2"])
        explored, synthesized = [], []
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1", "계획 하위2"]
        assert job.stage == "synthesized"
        assert job.report == {"sections": []}
        assert job.finished_at is not None
        assert _terminals(h) == [("completed", None)]

    def test_exploration_writes_the_checkpoint(self, monkeypatch):
        """체크포인트를 안 쓰면 종합이 실패했을 때 되살릴 것이 없다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert job.state_snapshot is not None
        assert [sq["text"] for sq in job.state_snapshot["subquestions"]] == ["계획 하위1"]

    def test_stage_explored_without_snapshot_falls_back_to_exploration(self, monkeypatch):
        # 스냅샷이 비어 있으면 되살릴 것이 없다 — 빈 보고서를 completed 로 저장하느니
        # 탐색을 다시 도는 쪽이 맞다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1"], state_snapshot=None)
        explored = []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1"]

    def test_engine_is_disposed(self, monkeypatch):
        # dispose 를 빠뜨리면 다음 잡이 닫힌 루프에 묶인 커넥션을 만난다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1"],
                       state_snapshot=_explored_snapshot())
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert h.engine.disposed == 1


class TestClaim:
    """Celery 는 at-least-once 다 — 선점에 실패한 재배달은 즉시 돌아서야 한다."""

    def test_unclaimed_job_is_skipped(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"], status="running")
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "skipped"
        assert explored == [] and synthesized == []

    def test_run_claims_only_statuses_the_api_writes(self, monkeypatch):
        """approve·retry 가 쓰는 상태를 워커가 받지 못하면 잡이 영원히 skipped 다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])
        seen = {}

        async def _record(db, job_id, *, allowed, to):
            seen["allowed"], seen["to"] = allowed, to
            return True

        monkeypatch.setattr(rt, "_claim", _record)
        asyncio.run(rt._run_deep_research(str(job.id)))

        from models.research import STATUS_APPROVED, STATUS_QUEUED
        assert STATUS_APPROVED in seen["allowed"]
        assert STATUS_QUEUED in seen["allowed"]
        assert seen["to"] == "running"


class TestConditionalTransition:
    """워커의 상태 쓰기는 기대한 이전 상태를 WHERE 에 건다."""

    def test_transition_sql_carries_status_condition(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["가"], status="running")
        db = _FakeSession(job=job)

        ok = asyncio.run(rt._transition(db, job.id, expect=("running",), status="completed"))

        assert ok is True and job.status == "completed"
        assert "research_jobs.status IN" in db.sql[0]
        assert db.commits == 1

    def test_transition_does_not_touch_a_canceled_job(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["가"], status="canceled")
        db = _FakeSession(job=job)

        ok = asyncio.run(rt._transition(db, job.id, expect=("running",), status="completed"))

        assert ok is False and job.status == "canceled"


class TestCancel:
    """취소는 API 가 조건부 UPDATE 로 찍는다. 워커는 그 뒤에 무엇도 덮어쓰면 안 된다."""

    def test_cancel_before_first_subquestion_stops_everything(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        explored, synthesized = [], []
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        async def _claim_then_cancel(db, job_id, *, allowed, to):
            job.status = "canceled"      # 선점 직후 사용자가 취소했다
            return True

        monkeypatch.setattr(rt, "_claim", _claim_then_cancel)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "canceled"
        assert explored == [] and synthesized == []
        assert job.status == "canceled"
        assert _terminals(h) == [("canceled", None)]

    def test_cancel_during_last_subquestion_skips_synthesis(self, monkeypatch):
        """루프 머리에서만 확인하면 마지막 하위질문 중의 취소가 종합까지 간다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        explored, synthesized = [], []

        async def _cancel_on_last(state, subq):
            if subq.idx == 1:
                job.status = "canceled"

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored,
                            synthesized=synthesized, explore=_cancel_on_last)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["하위1", "하위2"]
        assert synthesized == []
        assert out["status"] == "canceled"
        assert job.status == "canceled"
        # 취소된 잡에 체크포인트를 남기지 않는다
        assert job.stage == "planned" and job.state_snapshot is None
        assert ("canceled", None) in _terminals(h)

    def test_cancel_between_sections_stops_synthesis(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        calls = {"llm": 0}

        async def _synth(state, should_stop):
            # 절마다 LLM 직전에 should_stop 을 본다 — 첫 절 뒤에 취소가 들어왔다
            for i in range(3):
                if await should_stop():
                    raise rt.SynthesisCanceled()
                calls["llm"] += 1
                job.status = "canceled"
            return {"sections": []}

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_synth)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert calls["llm"] == 1
        assert out["status"] == "canceled"
        assert job.status == "canceled" and job.report is None
        # 종합 step 을 running 으로 남기면 회수기가 30분 뒤에야 닫는다
        assert h.finished[-1][1] == "failed"

    def test_cancel_after_synthesis_keeps_canceled(self, monkeypatch):
        """절 사이 확인을 모두 지나친 취소도 최종 전이의 status 조건에 걸린다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _synth(state, should_stop):
            job.status = "canceled"
            return {"sections": [{"title": "절"}]}

        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[], synthesize=_synth)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "canceled"
        assert job.status == "canceled"
        assert job.report is None and job.stage == "explored"

    def test_resumed_job_canceled_before_synthesis(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        synthesized = []
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=synthesized)

        async def _claim_then_cancel(db, job_id, *, allowed, to):
            job.status = "canceled"
            return True

        monkeypatch.setattr(rt, "_claim", _claim_then_cancel)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert synthesized == [] and out["status"] == "canceled"


class TestFailure:
    def test_synthesis_error_keeps_checkpoint_for_retry(self, monkeypatch):
        """retry 가 종합부터 이어받으려면 failed 여도 stage=explored·스냅샷이 남아야 한다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _boom(state, should_stop):
            raise ValueError("보고서 종합 출력을 해석하지 못했다")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_boom)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.status == "failed"
        assert job.stage == "explored" and job.state_snapshot is not None
        assert "해석하지 못했다" in job.last_error
        assert _terminals(h) == [("failed", "보고서 종합 출력을 해석하지 못했다")]

        # 이어서 retry 한 것처럼 다시 돌리면 탐색 없이 종합만 한다
        job.status = "queued"
        explored = []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=[])
        assert asyncio.run(rt._run_deep_research(str(job.id)))["status"] == "completed"
        assert explored == []

    def test_all_subquestions_failed_fails_the_job_without_checkpoint(self, monkeypatch):
        """전멸한 탐색을 completed 빈 보고서로 두면 retry 도 못 한다(completed 는 409)."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        synthesized = []

        async def _down(state, subq):
            raise ConnectionError("Milvus 연결 실패")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=synthesized,
                            explore=_down)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.status == "failed" and job.last_error
        # 체크포인트가 없어야 retry 가 탐색부터 다시 돈다
        assert job.stage == "planned" and job.state_snapshot is None
        assert synthesized == []
        assert [t[0] for t in _terminals(h)] == ["failed"]

    def test_all_failed_after_gathering_evidence_still_synthesizes(self, monkeypatch):
        """중단 전까지 모은 근거가 있으면 전멸이 아니다 — synthesizer 가 그 근거로 절을
        쓰고 한계에 "오류로 중단"을 적는다. 잡째 실패시키면 실재하는 근거를 버린다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        synthesized = []

        async def _fails_after_adopting(state, subq):
            eid = f"E{subq.idx}"
            state.evidence[eid] = Evidence(id=eid, cnts_id=f"C{subq.idx}", meta={})
            subq.evidence_ids = [eid]
            raise KeyError("재검색 라운드에서 터졌다")

        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=synthesized,
                        explore=_fails_after_adopting)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "completed"
        assert len(synthesized) == 1
        assert job.stage == "synthesized"
        assert [sq["failed"] for sq in job.state_snapshot["subquestions"]] == [True, True]

    def test_wiped_out_snapshot_is_explored_again(self, monkeypatch):
        """전멸 가드 이전에 저장된 '전부 실패' 스냅샷은 체크포인트가 아니다. 거기서
        종합만 다시 하면 절 0개짜리 보고서가 completed 로 남는다."""
        rt = _load_tasks(monkeypatch)
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        st.subquestions = [SubQuestion(idx=0, text="스냅샷 하위1", failed=True),
                           SubQuestion(idx=1, text="스냅샷 하위2", failed=True)]
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=snapshot_state(st), status="queued")
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1", "계획 하위2"]
        assert out["status"] == "completed"

    def test_empty_plan_fails_with_its_own_reason(self, monkeypatch):
        """전멸 판정(all)은 하위질문 0개에도 참이다 — 그대로 두면 계획이 빈 잡이
        '탐색이 오류로 실패'로 남아 운영자가 검색 장애로 오진한다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=[])
        explored, synthesized = [], []
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.last_error == rt.EMPTY_PLAN_ERROR
        assert "오류로 실패" not in job.last_error
        assert explored == [] and synthesized == [] and h.steps == []
        assert _terminals(h) == [("failed", rt.EMPTY_PLAN_ERROR)]

    def test_search_step_result_carries_capped(self, monkeypatch):
        """재접속한 화면은 step result 로 타임라인을 복원한다 — SSE 로만 보낸 값은 사라진다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _hit_cap(state, subq):
            subq.capped = 3

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_hit_cap)
        asyncio.run(rt._run_deep_research(str(job.id)))

        search_result = h.finished[0][2]
        assert search_result["capped"] == 3

    def test_partial_failure_still_completes(self, monkeypatch):
        """부분 실패는 전체 실패가 아니다 — 실패한 하위질문은 한계로 보고한다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])

        async def _second_fails(state, subq):
            if subq.idx == 1:
                raise ConnectionError("일시 장애")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_second_fails)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "completed"
        assert [sq["failed"] for sq in job.state_snapshot["subquestions"]] == [False, True]
        assert [f[1] for f in h.finished if f[0] in (1, 2)] == ["done", "failed"]

    def test_subquestion_error_rolls_back_before_recording(self, monkeypatch):
        """DB 오류로 깨진 트랜잭션 위에서 _finish 를 부르면 핸들러가 다시 터진다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])

        async def _first_fails(state, subq):
            if subq.idx == 0:
                raise RuntimeError("InFailedSQLTransaction")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_first_fails)
        asyncio.run(rt._run_deep_research(str(job.id)))

        step_id, status, _result, rollbacks = h.finished[0]
        assert status == "failed" and rollbacks >= 1

    def test_error_outside_step_handlers_fails_the_job(self, monkeypatch):
        """가드 밖 예외로 태스크가 죽으면 잡이 running 에 묶여 회수기만 기다린다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        async def _broken(db):
            raise RuntimeError("connection reset")

        monkeypatch.setattr(rt, "_corpus_range", _broken)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.status == "failed" and "connection reset" in job.last_error
        assert [t[0] for t in _terminals(h)] == ["failed"]
        assert any("UPDATE research_steps" in s for s in h.session.sql)  # 열린 step 을 닫는다
        assert h.engine.disposed >= 1


class TestTimeout:
    def test_soft_limit_outside_the_coroutine_marks_job_failed(self, monkeypatch):
        """LLM await 중에 온 소프트 리밋은 asyncio.run 밖으로 튄다 — 동기 래퍼가 잡는다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="running")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        async def _body(job_id):
            raise rt.SoftTimeLimitExceeded()

        out = rt._run_job(_body, str(job.id))

        assert out["status"] == "failed"
        assert job.status == "failed" and "시간 상한" in job.last_error
        assert any("UPDATE research_steps" in s for s in h.session.sql)
        assert [t[0] for t in _terminals(h)] == ["failed"]

    def test_deadline_cancels_the_await_and_marks_job_failed(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="running")
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])
        monkeypatch.setattr(rt, "JOB_DEADLINE", 0.05)

        async def _hang(job_id):
            await asyncio.sleep(5)       # 응답 없는 LLM

        out = rt._run_job(_hang, str(job.id))

        assert out["status"] == "failed"
        assert "시간 상한" in job.last_error

    def test_timeout_does_not_overwrite_cancel(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="canceled")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        async def _body(job_id):
            raise rt.SoftTimeLimitExceeded()

        out = rt._run_job(_body, str(job.id))

        assert job.status == "canceled" and out["status"] == "canceled"
        assert _terminals(h) == []

    def test_deadline_is_well_inside_the_soft_limit(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        assert rt.JOB_DEADLINE <= rt.SOFT_LIMIT - 60


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

    def test_plan_success_awaits_approval(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            return ["하위1", "하위2"]

        self._patch(monkeypatch, rt, job, _plan)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "awaiting_approval"
        assert job.status == "awaiting_approval"
        assert job.plan == ["하위1", "하위2"] and job.stage == "planned"

    def test_plan_failure_marks_failed(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            raise ValueError("계획을 해석하지 못했다")

        h = self._patch(monkeypatch, rt, job, _plan)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.status == "failed" and "해석하지 못했다" in job.last_error
        assert h.finished[-1][1] == "failed"
        assert [t[0] for t in _terminals(h)] == ["failed"]

    def test_cancel_during_planning_is_not_revived(self, monkeypatch):
        """planning 중 취소가 awaiting_approval 로 덮이면 취소한 잡을 승인·실행할 수 있다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            job.status = "canceled"
            return ["하위1"]

        self._patch(monkeypatch, rt, job, _plan)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "canceled"
        assert job.status == "canceled" and job.plan is None


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

    def test_stale_threshold_exceeds_hard_limit(self, monkeypatch):
        """회수 임계가 하드 리밋보다 짧으면 아직 살아 있는 워커의 잡을 회수한다."""
        rt = _load_tasks(monkeypatch)
        assert rt.STALE_MINUTES * 60 > rt.HARD_LIMIT

    def test_reaping_a_job_closes_its_running_steps(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession()
        monkeypatch.setattr(rt, "SyncSessionLocal", lambda: db)

        out = rt.reap_stale_research()

        job_sql = next(s for s in db.sql if "UPDATE research_jobs" in s)
        # 회수한 잡의 running step 을 같은 문장에서 닫는다
        assert "UPDATE research_steps" in job_sql and "reaped" in job_sql
        assert out["jobs"] == 1


class TestQueue:
    """딥리서치 큐는 설정값이다 — 코드를 먼저 배포할 때는 q_llm, 전용 워커가 뜨면 q_research."""

    def test_default_queue_is_q_llm(self, monkeypatch):
        from core.config import get_settings
        monkeypatch.delenv("RESEARCH_QUEUE", raising=False)
        monkeypatch.delenv("RESEARCH_PLAN_QUEUE", raising=False)
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch, fake_celery=True)
            from workers.celery_app import celery_app
            assert rt.run_deep_research.queue == "q_llm"
            assert rt.plan_deep_research.queue == "q_llm"
            assert celery_app.conf.task_routes["tasks.run_deep_research"] == {"queue": "q_llm"}
        finally:
            get_settings.cache_clear()

    def test_queue_follows_setting(self, monkeypatch):
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_research")
        monkeypatch.delenv("RESEARCH_PLAN_QUEUE", raising=False)
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch, fake_celery=True)
            from workers.celery_app import celery_app
            assert rt.run_deep_research.queue == "q_research"
            assert rt.plan_deep_research.queue == "q_research"
            routes = celery_app.conf.task_routes
            assert routes["tasks.run_deep_research"] == {"queue": "q_research"}
            assert routes["tasks.plan_deep_research"] == {"queue": "q_research"}
            # 적재 LLM 단계는 그대로 q_llm 이다
            assert routes["tasks.stage_summarize"] == {"queue": "q_llm"}
        finally:
            get_settings.cache_clear()


    def test_plan_can_take_its_own_queue(self, monkeypatch):
        """전용 워커는 concurrency 1 이다. 계획(0.6초)이 실행(최대 25분)과 같은 큐면
        다른 잡이 도는 동안 새 질문이 created 로 멈춘다 — 계획만 따로 받는 큐를 둔다."""
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_research")
        monkeypatch.setenv("RESEARCH_PLAN_QUEUE", "q_research_plan")
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch, fake_celery=True)
            from workers.celery_app import celery_app
            assert rt.plan_deep_research.queue == "q_research_plan"
            assert rt.run_deep_research.queue == "q_research"
            routes = celery_app.conf.task_routes
            assert routes["tasks.plan_deep_research"] == {"queue": "q_research_plan"}
            assert routes["tasks.run_deep_research"] == {"queue": "q_research"}
        finally:
            get_settings.cache_clear()

    def test_blank_plan_queue_follows_research_queue(self, monkeypatch):
        """compose 가 `${RESEARCH_PLAN_QUEUE:-}` 처럼 빈 값을 넘겨도 계획이 빈 이름의
        큐로 가면 안 된다 — 실행과 같은 큐로 간다."""
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_research")
        monkeypatch.setenv("RESEARCH_PLAN_QUEUE", "")
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch, fake_celery=True)
            assert rt.plan_deep_research.queue == "q_research"
        finally:
            get_settings.cache_clear()


class TestStageGuard:
    def test_unknown_stage_is_rejected(self, monkeypatch):
        # stage 오타는 재개 분기를 조용히 빗나가게 만든다 — 예외도 안 난다
        rt = _load_tasks(monkeypatch)
        try:
            rt._stage("explored_")
        except AssertionError:
            return
        raise AssertionError("알 수 없는 stage 가 통과했다")


class TestLoaderIsolation:
    """_load_tasks 가 끝나면 sys.modules·부모 패키지 속성이 import 전 그대로여야 한다.

    더미 celery·redis 에 묶인 research_tasks·celery_app·relay 가 남으면 뒤에 도는 테스트가
    더미 없이 import 해도 그 모듈을 물려받는다 — 로컬에서만, 실행 순서에 따라 결과가 달라진다.
    """

    @staticmethod
    def _parent(name: str):
        parent, _, child = name.rpartition(".")
        return importlib.import_module(parent), child

    def test_modules_that_were_absent_are_gone_afterwards(self):
        with pytest.MonkeyPatch.context() as outer:
            for name in _CACHED:
                parent, child = self._parent(name)
                outer.delitem(sys.modules, name, raising=False)
                outer.delattr(parent, child, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                _load_tasks(mp)
            for name in _CACHED:
                parent, child = self._parent(name)
                assert name not in sys.modules
                assert not hasattr(parent, child), name

    def test_modules_that_were_loaded_come_back(self):
        originals = {name: types.ModuleType(name) for name in _CACHED}
        with pytest.MonkeyPatch.context() as outer:
            for name, module in originals.items():
                parent, child = self._parent(name)
                outer.setitem(sys.modules, name, module)
                outer.setattr(parent, child, module, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                assert _load_tasks(mp) is not originals["workers.research_tasks"]
            for name, module in originals.items():
                parent, child = self._parent(name)
                assert sys.modules[name] is module
                assert getattr(parent, child) is module, name
```
```bash
$ python -m pytest app/tests/test_research_tasks.py -q
43 passed, 2 warnings in 1.20s
$ python -m pytest app/tests/test_research_tasks.py -q -k "TestCancel or TestConditionalTransition or TestTimeout or TestPlan"
14 passed, 29 deselected, 2 warnings in 0.78s
```

### 2.44 `test_research_api.py` — 엔드포인트

리뷰 전 딥리서치 API 6개 엔드포인트의 테스트는 0건이었다. 리뷰에서 새로 만든 파일이다.

**무엇을 고정하나.** 44건.

- `TestJobId` — 형식이 틀리면 422, 대문자 표기는 표준형으로.
- `TestCreate` — 계획 태스크를 보낸다, 브로커 실패면 503 + 잡 `failed`(`created` 에 묶이지 않는다).
- `TestApprove` — 워커가 선점하는 상태로 바꾼다, 본문 없이 제안대로, 고친 계획의 strip·저장, 잘못된 계획 6종 422(빈 목록·상한 초과·공백 항목·301자·공백만 다른 중복·대소문자만 다른 중복), 상태 409·없는 잡 404, **승인과 경쟁한 취소가 이긴다**, 브로커 실패면 `awaiting_approval` + 원래 계획으로.
- `TestRetry` — 체크포인트(`stage`·`state_snapshot`)를 그대로 두고 `queued`, 계획 없으면 409, `failed` 아니면 409, 브로커 실패면 `failed` + 원래 `last_error`.
- `TestSharedQueueRunSlot` — `running`·`approved`·`queued` 가 슬롯을 쥐면 approve 429(상태 그대로, 태스크 안 보냄), retry 429, 슬롯을 안 쥐는 6개 상태는 막지 않는다, 상태 오류(409)가 슬롯 검사보다 먼저, **잠금 → 계수 → UPDATE 가 한 트랜잭션 안**, 전용 큐면 잠금도 상한도 없다.
- `TestCancel` — 취소가 종료 이벤트를 publish, 없는 잡 404, 끝난 잡 409.
- `TestStream` — 끝난 잡은 스냅샷과 종료 프레임, 두 프레임만 보내고 닫힌다(종료 프레임은 워커의 실패 이벤트와 같은 모양), 상태별 kind, 대문자 경로도 표준형 채널을 구독, 하트비트가 감지한 종료도 같은 모양.
- `TestLoaderIsolation` — 로더가 끝나면 `api.research`·relay 가 `sys.modules`·부모 패키지 속성에서 원래대로다.

**방식.** 요청은 `TestClient` 로 실제 FastAPI 라우팅을 거친다 — 본문 없는 POST 가 422 가 되는지, pydantic 검증이 422 로 매핑되는지는 라우팅을 거쳐야 드러난다. `get_db` 는 `dependency_overrides` 로 대역을 꽂는다.

`_FakeDB` 는 잡을 dict 행으로 들고 **UPDATE 와 `count(*)` 의 `whereclause` 를 평가한다**(§2.43 과 같은 규칙의 `_matches` 를 dict 행에 맞춰 둔 사본). 여기에 둘을 더했다.

- `after_get` — `db.get` 으로 읽은 **직후**에 끼어드는 경쟁 요청을 흉내 낸다. `test_cancel_racing_approve_wins` 가 읽은 직후 행을 `canceled` 로 바꾸고, approve 가 덮어쓰지 않고 409 를 내며 태스크도 보내지 않는지 본다. 읽고-검사하고-대입하던 리뷰 전 코드는 여기서 `approved` 로 덮는다.
- `sql` 목록에 실행한 문장과 함께 `COMMIT`·`ROLLBACK` 을 순서대로 남긴다. 잠금과 계수가 같은 트랜잭션 안에 있는지는 **순서로만** 드러나기 때문이다 — `test_slot_is_counted_under_a_lock_in_the_transition_transaction` 이 `pg_advisory_xact_lock` < `SELECT count(*)` < `UPDATE research_jobs` 이고 그 사이에 `COMMIT`·`ROLLBACK` 이 없음을 단언한다. 모르는 문장은 `AssertionError` 다.

`_FakeCelery` 는 `fail=True` 면 kombu `OperationalError` 를 던진다. `redis`·`kombu` 는 로컬 venv 에 없어 미설치일 때만 더미를 꽂고, `workers.celery_app` 은 항상 대역 모듈로 바꾸므로 celery 는 아예 import 되지 않는다. 과도기 여부는 `get_settings` 를 `RESEARCH_QUEUE` 만 가진 `SimpleNamespace` 로 바꿔 전환한다(`_queue`).

**파일**: `app/tests/test_research_api.py` — 전체 543줄

```python
"""test_research_api.py — 딥리서치 API 엔드포인트

요청은 TestClient 로 실제 FastAPI 라우팅을 거친다(본문 없는 POST·422 매핑은
라우팅을 거쳐야 드러난다). DB 는 대역이다 — research_jobs 의 UPDATE 는 WHERE 를
실제로 평가한다. approve·retry 가 status 조건 없이 덮어쓰는 회귀는 대역이 조건을
무시하면 안 잡힌다.

`redis`·`celery`·`kombu` 는 로컬 venv 에 없다. 미설치일 때만 더미를 꽂는다.
"""
import importlib
import json
import sys
import types
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BindParameter, BooleanClauseList


class _OperationalError(Exception):
    """kombu 미설치 환경용 대역 — 브로커 연결 실패."""


def _stub_missing(monkeypatch, name: str, module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module)


# ── DB 대역 ────────────────────────────────────────────────────────────
def _matches(clause, row: dict) -> bool:
    if clause is None:
        return True
    if isinstance(clause, BooleanClauseList):
        return all(_matches(c, row) for c in clause.clauses)
    left = row.get(clause.left.key)
    right = getattr(clause.right, "value", None)
    op = clause.operator
    if op is operators.eq:
        return left == right
    if op is operators.in_op:
        return left in right
    if op is operators.is_not:
        return left is not None
    raise AssertionError(f"대역이 모르는 연산자: {op}")


class _Result:
    def __init__(self, *, rowcount: int = 0, rows=None, scalar=None):
        self.rowcount = rowcount
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one(self):
        return self._scalar


class _FakeDB:
    """research_jobs 를 dict 로 들고 get·조건부 UPDATE·개수 조회·step 조회를 흉내 낸다.

    sql 에는 실행한 문장과 COMMIT·ROLLBACK 을 순서대로 남긴다 — 잠금과 검사가 같은
    트랜잭션 안에 있는지는 순서로만 드러난다.
    """

    def __init__(self):
        self.jobs: dict[uuid.UUID, dict] = {}
        self.steps: list[SimpleNamespace] = []
        self.sql: list[str] = []
        self.after_get = None       # 읽은 직후에 끼어드는 경쟁 요청을 흉내 낸다

    def add_job(self, **fields) -> uuid.UUID:
        jid = fields.pop("id", None) or uuid.uuid4()
        row = {
            "id": jid, "question": "공공도서관 서비스 품질 평가", "status": "created",
            "params": {"max_subquestions": 3}, "plan": None, "report": None,
            "stage": "created", "state_snapshot": None, "last_error": None,
            "finished_at": None,
        }
        row.update(fields)
        self.jobs[jid] = row
        return jid

    async def get(self, model, pk):
        row = self.jobs.get(pk)
        job = SimpleNamespace(**row) if row is not None else None
        if self.after_get is not None:
            self.after_get(pk)
        return job

    def add(self, obj):
        self.jobs[obj.id] = {
            "id": obj.id, "question": obj.question, "status": obj.status or "created",
            "params": obj.params, "plan": None, "report": None, "stage": "created",
            "state_snapshot": None, "last_error": None, "finished_at": None,
        }

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append(sql)
        table = getattr(getattr(stmt, "table", None), "name", None)
        if sql.startswith("SELECT pg_advisory_xact_lock"):
            return _Result()
        if sql.startswith("SELECT count(*)") and "FROM research_jobs" in sql:
            n = sum(1 for row in self.jobs.values() if _matches(stmt.whereclause, row))
            return _Result(scalar=n)
        if getattr(stmt, "is_update", False) and table == "research_jobs":
            n = 0
            for row in self.jobs.values():
                if _matches(stmt.whereclause, row):
                    for key, value in stmt._values.items():
                        row[getattr(key, "key", key)] = (
                            value.value if isinstance(value, BindParameter) else value
                        )
                    n += 1
            return _Result(rowcount=n)
        if sql.startswith("SELECT research_steps"):
            return _Result(rows=self.steps)
        raise AssertionError(f"대역이 모르는 문장: {stmt}")

    async def commit(self):
        self.sql.append("COMMIT")

    async def rollback(self):
        self.sql.append("ROLLBACK")


class _FakeCelery:
    def __init__(self):
        self.sent: list[tuple[str, list]] = []
        self.fail = False

    def send_task(self, name, args=None, **kw):
        if self.fail:
            raise sys.modules["kombu.exceptions"].OperationalError("broker down")
        self.sent.append((name, args))


class _Api:
    def __init__(self, client, db, celery, published, research):
        self.client = client
        self.db = db
        self.celery = celery
        self.published = published
        self.research = research


_CACHED = ("api.research", "services.research.relay")


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 있던 키만 되돌린다. 원래 없던 키는 기록이 남지 않아
    여기서 새로 import 한 모듈(더미 redis 에 묶인 채)이 teardown 뒤에도 남는다.
    setitem·setattr 은 원래 없던 키·속성이면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을
    남긴 뒤 뺀다. 부모 속성까지 되돌리는 이유: `from pkg import mod` 와 문자열 경로
    monkeypatch 는 sys.modules 보다 부모 속성을 먼저 본다.
    """
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


def _load_api(monkeypatch, celery: "_FakeCelery"):
    """더미 위에서 api.research 를 새로 import 한다. 끝나면 import 전 그대로 되돌린다."""
    for name in ("redis", "redis.asyncio"):
        _stub_missing(monkeypatch, name, MagicMock())
    kombu = types.ModuleType("kombu")
    kombu_exc = types.ModuleType("kombu.exceptions")
    kombu_exc.OperationalError = _OperationalError
    _stub_missing(monkeypatch, "kombu", kombu)
    _stub_missing(monkeypatch, "kombu.exceptions", kombu_exc)

    celery_mod = types.ModuleType("workers.celery_app")
    celery_mod.celery_app = celery
    monkeypatch.setitem(sys.modules, "workers.celery_app", celery_mod)

    _forget_on_teardown(monkeypatch, _CACHED)
    return importlib.import_module("api.research")


@pytest.fixture
def api(monkeypatch):
    celery = _FakeCelery()
    research = _load_api(monkeypatch, celery)
    from core.deps import get_db

    published: list[tuple] = []

    async def _publish_terminal(job_id, status, error=None):
        published.append((job_id, status, error))

    monkeypatch.setattr(research, "publish_terminal", _publish_terminal)

    db = _FakeDB()
    app = FastAPI()
    app.include_router(research.router)
    app.dependency_overrides[get_db] = lambda: db
    return _Api(TestClient(app), db, celery, published, research)


def _frames(body: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in body.splitlines()
            if line.startswith("data: ")]


class TestJobId:
    def test_malformed_job_id_is_422(self, api):
        assert api.client.get("/api/research/not-a-uuid").status_code == 422

    def test_non_canonical_uuid_is_normalized(self, api):
        jid = api.db.add_job(status="completed")
        res = api.client.get(f"/api/research/{str(jid).upper()}")
        assert res.status_code == 200
        assert res.json()["job_id"] == str(jid)


class TestCreate:
    def test_create_queues_plan_task(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"})
        assert res.status_code == 200
        jid = res.json()["job_id"]
        assert api.celery.sent == [("tasks.plan_deep_research", [jid])]

    def test_broker_failure_does_not_strand_the_job(self, api):
        """커밋 뒤 send_task 가 실패하면 잡이 created 로 영원히 남는다."""
        api.celery.fail = True
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"})
        assert res.status_code == 503
        (row,) = api.db.jobs.values()
        assert row["status"] == "failed" and row["last_error"]


class TestApprove:
    def test_approve_sets_status_the_worker_claims(self, api):
        """상태를 그대로 두고 태스크만 던지면 워커의 _claim 이 0행을 잡아 영원히 skipped 다."""
        from models.research import RUNNABLE_STATUSES
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A", "가설 B"])

        res = api.client.post(f"/api/research/{jid}/approve", json={})

        assert res.status_code == 200
        assert api.db.jobs[jid]["status"] in RUNNABLE_STATUSES
        assert api.celery.sent == [("tasks.run_deep_research", [str(jid)])]

    def test_approve_without_body_uses_proposed_plan(self, api):
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])
        res = api.client.post(f"/api/research/{jid}/approve")
        assert res.status_code == 200
        assert res.json()["plan"] == ["가설 A"]

    def test_edited_plan_is_stripped_and_saved(self, api):
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])
        res = api.client.post(f"/api/research/{jid}/approve",
                              json={"plan": ["  새 하위질문 1 ", "새 하위질문 2"]})
        assert res.status_code == 200
        assert api.db.jobs[jid]["plan"] == ["새 하위질문 1", "새 하위질문 2"]

    @pytest.mark.parametrize("plan", [
        [],                                      # 비어 있음
        ["하위1", "하위2", "하위3", "하위4"],     # max_subquestions(3) 초과
        ["하위1", "   "],                         # 공백 항목 → 빈 쿼리 검색
        ["하위1", "x" * 301],                     # 항목 길이 상한
        ["독서  격차", "독서 격차"],              # 공백만 다른 중복
        ["Reading Gap", "reading gap"],           # 대소문자만 다른 중복
    ])
    def test_invalid_plan_is_422(self, api, plan):
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])
        res = api.client.post(f"/api/research/{jid}/approve", json={"plan": plan})
        assert res.status_code == 422
        assert api.db.jobs[jid]["status"] == "awaiting_approval"
        assert api.celery.sent == []

    def test_wrong_status_is_409(self, api):
        jid = api.db.add_job(status="planning")
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 409

    def test_missing_job_is_404(self, api):
        assert api.client.post(f"/api/research/{uuid.uuid4()}/approve").status_code == 404

    def test_cancel_racing_approve_wins(self, api):
        """approve 가 읽은 직후 cancel 이 커밋되면, approve 는 덮어쓰지 말고 409 여야 한다."""
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        def _cancel(pk):
            api.db.jobs[pk]["status"] = "canceled"

        api.db.after_get = _cancel
        res = api.client.post(f"/api/research/{jid}/approve")

        assert res.status_code == 409
        assert api.db.jobs[jid]["status"] == "canceled"
        assert api.celery.sent == []

    def test_broker_failure_reverts_to_awaiting_approval(self, api):
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])
        api.celery.fail = True

        res = api.client.post(f"/api/research/{jid}/approve", json={"plan": ["바꾼 계획"]})

        assert res.status_code == 503
        # 다시 승인할 수 있어야 한다 — approved 에 남으면 approve 는 409, 워커는 안 온다
        assert api.db.jobs[jid]["status"] == "awaiting_approval"
        assert api.db.jobs[jid]["plan"] == ["가설 A"]


class TestRetry:
    def test_retry_keeps_checkpoint(self, api):
        snap = {"subquestions": []}
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             state_snapshot=snap, last_error="종합 실패")

        res = api.client.post(f"/api/research/{jid}/retry")

        assert res.status_code == 200
        row = api.db.jobs[jid]
        assert row["status"] == "queued" and row["last_error"] is None
        assert row["stage"] == "explored" and row["state_snapshot"] is snap
        assert api.celery.sent == [("tasks.run_deep_research", [str(jid)])]

    def test_retry_without_plan_is_409(self, api):
        jid = api.db.add_job(status="failed", plan=None)
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 409
        assert api.celery.sent == []

    def test_retry_non_failed_is_409(self, api):
        jid = api.db.add_job(status="completed", plan=["가"])
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 409

    def test_broker_failure_reverts_to_failed(self, api):
        jid = api.db.add_job(status="failed", plan=["가"], last_error="종합 실패")
        api.celery.fail = True

        assert api.client.post(f"/api/research/{jid}/retry").status_code == 503
        assert api.db.jobs[jid]["status"] == "failed"
        assert api.db.jobs[jid]["last_error"] == "종합 실패"


def _queue(api, monkeypatch, name: str) -> None:
    monkeypatch.setattr(api.research, "get_settings", lambda: SimpleNamespace(RESEARCH_QUEUE=name))


class TestSharedQueueRunSlot:
    """적재와 큐를 나눠 쓰는 동안(RESEARCH_QUEUE 기본값 q_llm) 실행은 한 번에 한 잡이다.

    딥리서치 실행은 적재 요약·마무리와 같은 celery-llm 슬롯(4개)을 잡마다 최대 25분
    쥔다. 여럿이 쥐면 슬롯을 기다리는 적재 아이템이 단계 타임아웃을 넘겨 stale 복구되고,
    옛 체인과 새 체인이 겹쳐 논문 본문 청크가 초록으로 덮일 수 있다(함정 16번).
    """

    @pytest.mark.parametrize("busy", ["running", "approved", "queued"])
    def test_approve_is_429_while_another_run_holds_the_slot(self, api, monkeypatch, busy):
        """approved·queued 도 센다 — 워커가 아직 안 집었을 뿐 이미 큐에 들어간 실행이다.
        running 만 세면 몰아서 승인한 잡이 전부 통과한다."""
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status=busy, plan=["가"])
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        res = api.client.post(f"/api/research/{jid}/approve")

        assert res.status_code == 429
        # 앞 잡이 끝나면 다시 승인할 수 있어야 한다
        assert api.db.jobs[jid]["status"] == "awaiting_approval"
        assert api.celery.sent == []

    def test_retry_is_429_while_another_run_holds_the_slot(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status="running", plan=["가"])
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             last_error="종합 실패")

        res = api.client.post(f"/api/research/{jid}/retry")

        assert res.status_code == 429
        row = api.db.jobs[jid]
        assert row["status"] == "failed" and row["last_error"] == "종합 실패"
        assert api.celery.sent == []

    @pytest.mark.parametrize("idle", [
        "created", "planning", "awaiting_approval", "completed", "failed", "canceled",
    ])
    def test_jobs_without_a_run_slot_do_not_block(self, api, monkeypatch, idle):
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status=idle, plan=["가"])
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200

    def test_state_errors_come_before_the_slot_check(self, api, monkeypatch):
        """재시도할 수 없는 잡에 429 를 주면 '기다리면 된다'로 읽힌다."""
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status="running", plan=["가"])
        jid = api.db.add_job(status="completed", plan=["가"])

        assert api.client.post(f"/api/research/{jid}/retry").status_code == 409

    def test_slot_is_counted_under_a_lock_in_the_transition_transaction(self, api, monkeypatch):
        """동시에 온 두 승인이 서로 커밋 전 상태를 보고 둘 다 통과하면 상한이 뚫린다.
        잠금을 잡은 뒤 세고, 같은 트랜잭션에서 전이해 그 커밋이 잠금을 푼다."""
        _queue(api, monkeypatch, "q_llm")
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200

        sql = api.db.sql
        lock = next(i for i, s in enumerate(sql) if "pg_advisory_xact_lock" in s)
        count = next(i for i, s in enumerate(sql) if s.startswith("SELECT count(*)"))
        upd = next(i for i, s in enumerate(sql) if s.startswith("UPDATE research_jobs"))
        assert lock < count < upd
        assert not {"COMMIT", "ROLLBACK"} & set(sql[lock:upd])

    def test_dedicated_queue_lets_runs_wait_in_line(self, api, monkeypatch):
        """전용 워커(concurrency 1)는 뒤 잡을 approved 로 줄 세울 뿐 적재 슬롯을 먹지 않는다."""
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"])
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200
        assert not any("pg_advisory_xact_lock" in s for s in api.db.sql)


class TestCancel:
    def test_cancel_running_job_publishes_terminal(self, api):
        jid = api.db.add_job(status="running")

        res = api.client.post(f"/api/research/{jid}/cancel")

        assert res.status_code == 200
        assert api.db.jobs[jid]["status"] == "canceled"
        # 워커가 없는 상태에서 취소해도 스트림이 하트비트(15초)를 기다리지 않고 닫힌다
        assert api.published == [(jid, "canceled", None)]

    def test_cancel_missing_job_is_404(self, api):
        assert api.client.post(f"/api/research/{uuid.uuid4()}/cancel").status_code == 404

    def test_cancel_finished_job_is_409(self, api):
        jid = api.db.add_job(status="completed")
        assert api.client.post(f"/api/research/{jid}/cancel").status_code == 409
        assert api.published == []


class TestStream:
    def test_finished_job_sends_snapshot_then_terminal(self, api):
        jid = api.db.add_job(status="failed", last_error="모든 하위질문 탐색이 오류로 실패했다")

        frames = _frames(api.client.get(f"/api/research/{jid}/stream").text)

        from services.research.relay import terminal_event
        assert frames[0]["kind"] == "snapshot"
        # 워커가 흘리는 실패 이벤트와 같은 모양이어야 한다 — done+status 로 오면 안 된다
        assert frames[1] == terminal_event("failed", "모든 하위질문 탐색이 오류로 실패했다")
        assert len(frames) == 2

    @pytest.mark.parametrize("status,kind", [("completed", "done"), ("canceled", "canceled")])
    def test_terminal_kind_follows_status(self, api, status, kind):
        jid = api.db.add_job(status=status)
        frames = _frames(api.client.get(f"/api/research/{jid}/stream").text)
        assert frames[-1] == {"kind": kind, "status": status}

    def test_subscribes_on_the_canonical_channel(self, api, monkeypatch):
        """워커는 str(uuid) 채널에 쓴다. 대문자 경로로 붙어도 같은 채널을 구독해야 한다."""
        jid = api.db.add_job(status="running")
        seen = {}

        async def _subscribe(job_id):
            seen["job_id"] = job_id
            yield {"kind": "search", "subq_idx": 0}
            yield {"kind": "done", "status": "completed"}

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        frames = _frames(api.client.get(f"/api/research/{str(jid).upper()}/stream").text)

        assert str(seen["job_id"]) == str(jid)
        assert [f["kind"] for f in frames] == ["snapshot", "search", "done"]

    def test_heartbeat_detects_termination_with_same_shape(self, api, monkeypatch):
        jid = api.db.add_job(status="running")

        async def _subscribe(job_id):
            yield None

        async def _terminal_status(job_uuid):
            return "canceled", None

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        monkeypatch.setattr(api.research, "_terminal_status", _terminal_status)
        frames = _frames(api.client.get(f"/api/research/{jid}/stream").text)

        assert frames[-1] == {"kind": "canceled", "status": "canceled"}


class TestLoaderIsolation:
    """_load_api 가 끝나면 sys.modules·부모 패키지 속성이 import 전 그대로여야 한다.

    더미 redis 에 묶인 api.research·relay 가 남으면 뒤에 도는 테스트가 더미 없이
    import 해도 그 모듈을 물려받는다 — 로컬에서만, 실행 순서에 따라 결과가 달라진다.
    """

    @staticmethod
    def _parent(name: str):
        parent, _, child = name.rpartition(".")
        return importlib.import_module(parent), child

    def test_modules_that_were_absent_are_gone_afterwards(self):
        with pytest.MonkeyPatch.context() as outer:
            for name in _CACHED:
                parent, child = self._parent(name)
                outer.delitem(sys.modules, name, raising=False)
                outer.delattr(parent, child, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                _load_api(mp, _FakeCelery())
            for name in _CACHED:
                parent, child = self._parent(name)
                assert name not in sys.modules
                assert not hasattr(parent, child), name

    def test_modules_that_were_loaded_come_back(self):
        originals = {name: types.ModuleType(name) for name in _CACHED}
        with pytest.MonkeyPatch.context() as outer:
            for name, module in originals.items():
                parent, child = self._parent(name)
                outer.setitem(sys.modules, name, module)
                outer.setattr(parent, child, module, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                assert _load_api(mp, _FakeCelery()) is not originals["api.research"]
            for name, module in originals.items():
                parent, child = self._parent(name)
                assert sys.modules[name] is module
                assert getattr(parent, child) is module, name
```
```bash
$ python -m pytest app/tests/test_research_api.py -q
44 passed, 1 warning in 1.54s
$ python -m pytest app/tests/test_research_runner.py app/tests/test_research_relay.py app/tests/test_research_tasks.py app/tests/test_research_api.py -q
123 passed, 2 warnings in 2.34s
```

(2026-09-23 로컬 측정. 이 네 파일이 이 챕터의 테스트 전부다 — 27 + 9 + 43 + 44 = 123건. 라운드 전체는 549 passed, 완료노트 §4.)
