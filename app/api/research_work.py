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
