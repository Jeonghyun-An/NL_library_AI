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
