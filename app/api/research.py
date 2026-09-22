"""research.py — 딥리서치 API

실행은 Celery 가 맡고 진행은 SSE 로 중계한다. 탭을 닫아도 워커는 계속 돌고,
다시 열면 research_steps 로 지금까지를 복원한 뒤 이어서 받는다.

상태 전이:
    created ─plan─→ planning ─→ awaiting_approval ─approve─→ approved
    approved ─run─→ running ─→ completed | failed
    failed ─retry─→ queued ─run─→ running (stage=explored 면 종합부터)
    (거의 모든 상태) ─cancel─→ canceled
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from db.postgres import AsyncSessionLocal
from models.research import (
    STATUS_APPROVED, STATUS_CANCELED, STATUS_QUEUED, ResearchJob, ResearchStep,
)
from services.research.relay import subscribe
from services.research.state import merge_params

router = APIRouter(prefix="/api/research", tags=["research"])

# 중계를 끊어야 하는 이벤트 / 이미 끝난 잡의 상태.
# 이벤트 kind 도 상태와 같은 철자(canceled)를 쓴다 — 두 철자가 섞이면
# 프론트 분기가 조용히 빗나간다.
TERMINAL_KINDS = ("done", "failed", STATUS_CANCELED)
TERMINAL_STATUSES = ("completed", "failed", STATUS_CANCELED)

# 취소를 받아주는 상태. completed·failed·canceled 는 이미 끝난 잡이라 409 다.
CANCELLABLE_STATUSES = (
    "created", "planning", "awaiting_approval",
    STATUS_APPROVED, STATUS_QUEUED, "running",
)


class ResearchCreate(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    params: dict = Field(default_factory=dict)


class ResearchApprove(BaseModel):
    plan: list[str] | None = None      # 사용자가 수정한 계획. 없으면 제안대로.


def _job_uuid(job_id: str) -> uuid.UUID:
    """경로 파라미터를 PK 타입으로 바꾼다. 형식이 틀리면 422 — 500 이 아니다."""
    try:
        return uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="job_id 형식이 올바르지 않습니다")


async def _get_job(db: AsyncSession, job_id: str) -> ResearchJob:
    job = await db.get(ResearchJob, _job_uuid(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("")
async def create_research(req: ResearchCreate, db: AsyncSession = Depends(get_db)):
    try:
        params = merge_params(req.params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    job = ResearchJob(id=uuid.uuid4(), question=req.question, params=params)
    db.add(job)
    await db.commit()

    from workers.celery_app import celery_app
    celery_app.send_task("tasks.plan_deep_research", args=[str(job.id)])
    return {"job_id": str(job.id), "status": "created"}


@router.post("/{job_id}/approve")
async def approve_plan(
    job_id: str, req: ResearchApprove, db: AsyncSession = Depends(get_db),
):
    """계획을 확정하고 실행 큐에 넣는다.

    status 를 STATUS_APPROVED 로 바꾸는 것이 핵심이다. 상태를 그대로 두고
    태스크만 던지면 워커의 _claim(allowed=RUNNABLE_STATUSES) 이 0행을 잡아
    잡이 영원히 skipped 로 떨어진다 — 그래서 양쪽이 같은 상수를 본다.
    """
    job = await _get_job(db, job_id)
    if job.status != "awaiting_approval":
        raise HTTPException(
            status_code=409, detail=f"승인할 수 없는 상태다: {job.status}",
        )
    if req.plan is not None:
        if not req.plan:
            raise HTTPException(status_code=422, detail="계획이 비어 있다")
        job.plan = req.plan
    job.status = STATUS_APPROVED
    await db.commit()

    from workers.celery_app import celery_app
    celery_app.send_task("tasks.run_deep_research", args=[str(job.id)])
    return {"job_id": job_id, "status": job.status, "plan": job.plan}


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

    계획 단계에서 실패한 잡(plan 이 비어 있음)은 받지 않는다. 그대로
    run_deep_research 에 넘기면 하위질문 0개로 탐색이 끝나고 빈 보고서를
    completed 로 저장한다 — 실패보다 나쁜 조용한 성공이다.
    """
    job = await _get_job(db, job_id)
    if job.status != "failed":
        raise HTTPException(
            status_code=409, detail=f"재시도할 수 없는 상태다: {job.status}",
        )
    if not job.plan:
        raise HTTPException(
            status_code=409, detail="계획이 없는 잡은 재시도할 수 없다 — 새 잡을 만든다",
        )

    job.status = STATUS_QUEUED
    job.last_error = None
    job.finished_at = None      # 큐에 들어간 잡이 종료시각을 들고 있으면 안 된다
    await db.commit()

    from workers.celery_app import celery_app
    celery_app.send_task("tasks.run_deep_research", args=[str(job.id)])
    return {"job_id": job_id, "status": job.status, "stage": job.stage}


@router.post("/{job_id}/cancel")
async def cancel_research(job_id: str, db: AsyncSession = Depends(get_db)):
    """탐색은 하위질문 경계에서 멈춘다 — 진행 중인 LLM 호출을 중간에 끊지는 않는다.

    5~7분짜리 GPU 작업을 멈출 방법이 없으면, 창을 닫은 사용자의 잡이 공유
    GPU 를 계속 먹는다. 시연 중에 이게 겹치면 다른 기능까지 느려진다.
    """
    res = await db.execute(
        update(ResearchJob)
        .where(ResearchJob.id == _job_uuid(job_id),
               ResearchJob.status.in_(CANCELLABLE_STATUSES))
        .values(status=STATUS_CANCELED, finished_at=func.now())
    )
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태입니다")
    return {"job_id": job_id, "status": STATUS_CANCELED}


@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, job_id)
    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    return {
        "job_id": job_id, "question": job.question, "status": job.status,
        "stage": job.stage, "plan": job.plan, "report": job.report,
        "last_error": job.last_error,
        "steps": [
            {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx, "title": s.title,
             "detail": s.detail, "status": s.status, "result": s.result}
            for s in rows
        ],
    }


@router.get("/{job_id}/stream")
async def stream_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, job_id)

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
    job_uuid = job.id
    job_status = job.status

    async def _gen():
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield f"data: {json.dumps({'kind': 'snapshot', 'steps': snapshot}, ensure_ascii=False)}\n\n"
        if job_status in TERMINAL_STATUSES:
            # 끝난 잡에 붙었다면 중계할 것이 없다. 구독하면 영원히 기다린다.
            yield f"data: {json.dumps({'kind': 'done', 'status': job_status}, ensure_ascii=False)}\n\n"
            return
        async for event in subscribe(job_id):
            if event is None:
                # 하트비트. 끊긴 소켓은 여기서 드러난다. 그리고 종료 이벤트를
                # 놓친 채 붙어 있는 경우를 대비해 상태를 한 번 더 확인한다.
                yield ": ping\n\n"
                st = await _terminal_status(job_uuid)
                if st is not None:
                    yield f"data: {json.dumps({'kind': 'done', 'status': st}, ensure_ascii=False)}\n\n"
                    return
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("kind") in TERMINAL_KINDS:
                return

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _terminal_status(job_uuid: uuid.UUID) -> str | None:
    """하트비트마다 짧은 세션을 새로 연다 — Depends(get_db) 세션을 쓰지 않는다.

    FastAPI 는 핸들러가 반환하면 yield 의존성을 닫는다. StreamingResponse 의
    제너레이터는 그 뒤에 도는데, 닫힌 세션을 계속 쓰면 유휴 SSE 하나가
    커넥션을 몇 분씩 쥐고 있게 되고 수명도 요청 수명을 벗어난다. 여기는
    FastAPI 의 장수 루프 안이라 풀링 엔진(AsyncSessionLocal)이 맞다.
    """
    async with AsyncSessionLocal() as db:
        st = (await db.execute(
            select(ResearchJob.status).where(ResearchJob.id == job_uuid)
        )).scalar_one_or_none()
    return st if st in TERMINAL_STATUSES else None
