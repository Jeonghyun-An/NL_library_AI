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
