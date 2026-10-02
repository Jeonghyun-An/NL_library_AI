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
슬롯이 비었을 때만 전이하고 아니면 429 다 — _to_run_queue. 큐와 상관없이 한 브라우저
(잡의 created_by)는 실행 큐에 한 잡만 둔다 — 같은 브라우저의 다른 잡이 approved·queued·
running 이면 429. 두 429 는 detail.code(shared_queue·browser_active)로 가른다.
"""
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_browser_id_optional, get_db
from db.postgres import AsyncSessionLocal
from models.research import (
    RUNNABLE_STATUSES, STATUS_APPROVED, STATUS_CANCELED, STATUS_QUEUED, TERMINAL_STATUSES,
    ResearchJob, ResearchStep,
)
from services.research.planner import query_key
from services.research.relay import (
    TERMINAL_KIND, publish, publish_terminal, subscribe, terminal_event,
)
from services.research.run_queue import (
    eta_seconds, mark_waiting, median_seconds, rank_of, unmark, waiting_ahead,
)
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
_SHARED_QUEUE_MESSAGE = (
    "다른 딥리서치가 실행 중이거나 실행을 기다리고 있다 — 끝나거나 취소된 뒤 "
    "다시 요청한다(적재와 워커를 나눠 쓰는 동안은 한 번에 한 건만 실행한다)"
)
_BROWSER_ACTIVE_MESSAGE = "진행 중인 딥리서치가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요"
# 예상 대기 시간의 기준 — 최근 완료분 몇 건의 소요 시간 중앙값을 쓰는가
RECENT_RUNS = 20

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


async def _announce(jid: uuid.UUID, status: str, stage: str) -> None:
    """상태 전이를 스트림에 알린다. 전이가 성공한 뒤에만 부른다. 종료 상태는
    publish_terminal 이 알린다 — status 로 내면 스트림이 닫히지 않는다."""
    await publish(jid, "status", {"status": status, "stage": stage})


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
async def create_research(
    req: ResearchCreate, db: AsyncSession = Depends(get_db),
    browser_id: uuid.UUID | None = Depends(get_browser_id_optional),
):
    try:
        params = merge_params(req.params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 헤더가 없거나 틀려도 잡은 만든다 — 기록 API 와 달리 헤더 없는 curl 시연과
    # 옛 화면이 그대로 돌아야 한다.
    job = ResearchJob(id=uuid.uuid4(), question=req.question, params=params,
                      created_by=str(browser_id) if browser_id else None)
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
                               created_by=job.created_by, status=STATUS_APPROVED, plan=plan):
        raise HTTPException(status_code=409, detail="그 사이 잡 상태가 바뀌었다")

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
    if not await _to_run_queue(db, jid, expect=("failed",), created_by=job.created_by,
                               status=STATUS_QUEUED, last_error=None, finished_at=None):
        raise HTTPException(status_code=409, detail="그 사이 잡 상태가 바뀌었다")

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
    # approved·queued 에서 취소한 잡은 워커가 집지 않는다 — 여기서 빼지 않으면 줄에 남아
    # 뒤 잡의 순번을 하나씩 민다. 다른 상태면 줄에 없어 아무 일도 없다.
    await unmark(jid)
    # 워커가 없는 상태(승인 대기 등)에서 취소하면 종료 이벤트를 낼 주체가 없다 —
    # 여기서 내지 않으면 스트림이 다음 하트비트까지 열려 있다.
    await publish_terminal(jid, STATUS_CANCELED)
    return {"job_id": str(jid), "status": STATUS_CANCELED}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


async def _steps(db: AsyncSession, jid: uuid.UUID) -> list[dict]:
    """GET 과 스트림 스냅샷이 같은 모양을 쓴다 — 갈리면 새로고침한 화면과 재접속한
    화면이 같은 잡을 다르게 그린다."""
    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == jid).order_by(ResearchStep.seq)
    )).scalars().all()
    return [
        {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx, "title": s.title,
         "detail": s.detail, "status": s.status, "result": s.result}
        for s in rows
    ]


def _live_counters(steps: list[dict], report: dict | None) -> dict | None:
    """재접속한 화면의 카운터. 끝난 잡은 보고서의 stats, 도는 잡은 워커가 마지막으로
    단계 result 에 남긴 값이다 — counters 이벤트는 저장되지 않아, 이게 없으면 다음
    회차까지 카운터가 빈칸이다."""
    if report and report.get("stats"):
        return report["stats"]
    for step in reversed(steps):
        counters = (step["result"] or {}).get("counters")
        if counters:
            return counters
    return None


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


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _snapshot(db: AsyncSession, job: ResearchJob) -> dict:
    """재접속 복원용 뼈대. 연결 직후와 하트비트가 어긋남을 본 뒤가 이 한 곳에서 만든다 —
    모양이 갈리면 화면이 같은 잡을 두 경로에서 다르게 그린다."""
    steps = await _steps(db, job.id)
    job_state = {"status": job.status, "stage": job.stage, "plan": job.plan}
    counters = _live_counters(steps, job.report)
    if counters is not None:
        job_state["counters"] = counters
    queue = await _queue_info(db, job)
    if queue is not None:
        job_state["queue"] = queue
    return {"kind": "snapshot", "steps": steps, "job": job_state}


def _plan_known(snapshot: dict) -> bool:
    """이 스냅샷만으로 화면이 계획을 그릴 수 있는가. 화면은 job.plan 을, 없으면 plan
    단계 result 의 원안을 쓴다."""
    return bool(snapshot["job"]["plan"]) or any(
        s["kind"] == "plan" and (s["result"] or {}).get("subquestions")
        for s in snapshot["steps"]
    )


def _carries_plan(event: dict) -> bool:
    return (event.get("kind") == "step" and event.get("step_kind") == "plan"
            and bool((event.get("result") or {}).get("subquestions")))


@router.get("/{job_id}/stream")
async def stream_research(job_id: str, db: AsyncSession = Depends(get_db)):
    jid = _job_uuid(job_id)
    job = await _get_job(db, jid)

    # 제너레이터는 요청 세션이 닫힌 뒤에 돈다 — ORM 객체를 들고 가지 않고
    # 필요한 값만 미리 꺼내 둔다.
    snapshot = await _snapshot(db, job)
    job_status, job_stage, job_error = job.status, job.stage, job.last_error

    async def _gen() -> AsyncIterator[str]:
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield _sse(snapshot)
        if job_status in TERMINAL_STATUSES:
            # 끝난 잡에 붙었다면 중계할 것이 없다. 구독하면 영원히 기다린다.
            yield _sse(terminal_event(job_status, job_error))
            return
        # 화면이 지금 아는 상태와 계획 유무 — 하트비트가 DB 와 견줄 기준이다
        last, plan_sent = (job_status, job_stage), _plan_known(snapshot)
        # 화면이 지금 아는 대기 순번 — 하트비트가 다시 세어 바뀌었을 때만 queue 를 보낸다
        last_queue = snapshot["job"].get("queue")
        async for event in subscribe(str(jid)):
            if event is None:
                # 하트비트. 끊긴 소켓은 여기서 드러난다. 그리고 DB 와 맞춰 본다 —
                # 종료 이벤트를 놓친 채 붙어 있는 경우(회수기가 끝낸 잡 등)와, 스냅샷을
                # 읽은 뒤 구독이 붙기 전에 나간 이벤트를 놓친 경우다. 계획은 1초 안팎이라
                # plan 단계 done(계획 원안)과 awaiting_approval 이 함께, 또는 done 만
                # 그 틈에 빠지기 쉽다. 상태만 되살리면 화면은 승인 대기로 가도 승인할
                # 계획이 없어 막힌다 — 어긋나면 스냅샷을 통째로 다시 보낸다. 다시 읽는
                # 조회는 어긋났을 때만 한다.
                yield ": ping\n\n"
                current = await _job_status(jid)
                if current is None:
                    continue
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
                fresh = await _fresh_snapshot(jid)
                if fresh is None:
                    continue
                snap, error = fresh
                status, stage = snap["job"]["status"], snap["job"]["stage"]
                if status in TERMINAL_STATUSES:
                    # 두 조회 사이에 끝났다. 끝난 상태를 스냅샷으로 보내면 화면이
                    # 스트림을 닫지 않는다 — 종료 프레임으로만 알린다.
                    yield _sse(terminal_event(status, error))
                    return
                last, plan_sent = (status, stage), _plan_known(snap)
                last_queue = snap["job"].get("queue")
                yield _sse(snap)
                continue
            if event.get("kind") == "status":
                last = (event.get("status"), event.get("stage"))
            elif _carries_plan(event):
                plan_sent = True
            yield _sse(event)
            if event.get("kind") in TERMINAL_KINDS:
                return

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _job_status(jid: uuid.UUID) -> tuple[str, str, str | None, bool] | None:
    """(status, stage, last_error, 계획 유무). 하트비트마다 짧은 세션을 새로 연다 —
    Depends(get_db) 세션을 쓰지 않는다.

    FastAPI 는 핸들러가 반환하면 yield 의존성을 닫는다. StreamingResponse 의
    제너레이터는 그 뒤에 도는데, 닫힌 세션을 계속 쓰면 유휴 SSE 하나가
    커넥션을 몇 분씩 쥐고 있게 되고 수명도 요청 수명을 벗어난다. 여기는
    FastAPI 의 장수 루프 안이라 풀링 엔진(AsyncSessionLocal)이 맞다.
    """
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(ResearchJob.status, ResearchJob.stage, ResearchJob.last_error,
                   ResearchJob.plan)
            .where(ResearchJob.id == jid)
        )).first()
    return None if row is None else (row[0], row[1], row[2], bool(row[3]))


async def _fresh_snapshot(jid: uuid.UUID) -> tuple[dict, str | None] | None:
    """하트비트가 화면과 DB 의 어긋남을 봤을 때 다시 보낼 (스냅샷, last_error).
    짧은 세션을 새로 여는 이유는 _job_status 와 같다."""
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
