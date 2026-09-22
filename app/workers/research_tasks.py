"""research_tasks.py — 딥리서치 Celery 태스크

동기 워커에서 async 파이프라인을 돌린다. 이 파일이 이 코드베이스에서 워커가
async 코드를 부르는 첫 자리다(`app/workers/` 에 기존 asyncio 사용 0건). 그래서
루프와 세션을 다루는 규칙을 여기서 못박아 둔다 — 아래 _job_engine 주석.
"""
import asyncio
import datetime as _dt
import logging
import uuid

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, text as sa_text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.research import (
    JOB_STAGES, RUNNABLE_STATUSES, STATUS_CANCELED, STEP_KINDS,
    ResearchJob, ResearchStep,
)
from services.research.relay import publish
from services.research.runner import explore_subquestion
from services.research.state import (
    ResearchState, SubQuestion, merge_params, restore_state, snapshot_state,
)
from services.research.synthesizer import synthesize
from workers.celery_app import celery_app

log = logging.getLogger(__name__)

# 5~7분이 설계값이고 종합까지 10분을 안 넘긴다. 30분이면 멈춘 것이다.
# 상한이 없으면 응답 없는 LLM 호출 하나가 q_llm 워커를 영구 점유한다.
SOFT_LIMIT = 1800
HARD_LIMIT = 2100

STALE_MINUTES = 30


def _job_engine():
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
    쪽 변환에 기대는 부분도 생긴다. app/api 에도 UUID PK 선례가 없으므로
    여기서 규칙을 정한다 — 경계에서 한 번 변환하고 안쪽은 UUID 만 쓴다.
    """
    return uuid.UUID(str(job_id))


def _set_stage(job: ResearchJob, stage: str) -> None:
    """JOB_STAGES 를 실제로 강제하는 유일한 지점.

    stage 오타는 재개 분기(stage == "explored")를 조용히 빗나가게 만든다 —
    예외도 안 나고 그냥 탐색을 처음부터 다시 돌 뿐이라 알아채기 어렵다.
    """
    assert stage in JOB_STAGES, f"알 수 없는 stage: {stage}"
    job.stage = stage


async def _next_seq(db: AsyncSession, job_id: uuid.UUID) -> int:
    """이어붙일 seq. 1 부터 다시 시작하면 uq_research_steps_job_seq 를 위반한다.

    재시도·재개는 정상 경로다(워커 사망 복구, 종합만 재실행). 그때마다
    IntegrityError 로 죽으면 복구 기능 자체가 동작하지 않는다.
    """
    row = await db.execute(sa_text(
        "SELECT coalesce(max(seq), -1) + 1 FROM research_steps WHERE job_id = :j"
    ), {"j": job_id})
    return int(row.scalar_one())


async def _step(db: AsyncSession, job_id, seq, kind, title, *, subq_idx=None, detail=None):
    # STEP_KINDS 를 실제로 강제하는 유일한 지점. 상수만 정의하고 아무 데서도
    # 쓰지 않으면 장식이 되고, 오타난 kind 가 프론트 분기를 조용히 빗나간다.
    assert kind in STEP_KINDS, f"알 수 없는 kind: {kind}"
    row = ResearchStep(
        job_id=job_id, seq=seq, kind=kind, title=title,
        subq_idx=subq_idx, detail=detail, status="running",
    )
    db.add(row)
    await db.commit()
    return row


async def _finish(db: AsyncSession, row, status, result=None):
    row.status = status
    row.result = result or {}
    row.finished_at = _dt.datetime.now(_dt.timezone.utc)
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


async def _claim(db: AsyncSession, job_id, *, allowed: tuple[str, ...], to: str) -> bool:
    """조건부 선점. 못 잡으면 False.

    Celery 는 at-least-once 다 — 워커가 ack 전에 죽으면 같은 잡이 다시 배달된다.
    무조건 status="running" 을 대입하면 그때 같은 잡이 두 벌 돌아 step 이 중복되고
    LLM 비용이 두 배가 되며, 두 실행이 같은 job 행을 서로 덮어쓴다.
    """
    res = await db.execute(
        update(ResearchJob)
        .where(ResearchJob.id == job_id, ResearchJob.status.in_(allowed))
        .values(status=to, started_at=_dt.datetime.now(_dt.timezone.utc))
    )
    await db.commit()
    return res.rowcount == 1


async def _is_cancelled(db: AsyncSession, job_id) -> bool:
    """취소 여부를 DB 에서 다시 읽는다 — 취소는 API 프로세스에서 찍힌다."""
    await db.commit()          # 열린 트랜잭션의 스냅샷을 버려야 남의 커밋이 보인다
    res = await db.execute(select(ResearchJob.status).where(ResearchJob.id == job_id))
    return res.scalar_one_or_none() == STATUS_CANCELED


@celery_app.task(name="tasks.plan_deep_research", queue="q_llm",
                 soft_time_limit=SOFT_LIMIT, time_limit=HARD_LIMIT)
def plan_deep_research(job_id: str) -> dict:
    """계획만 세우고 승인 대기 상태로 멈춘다. 잡 전체를 이벤트 루프 하나로 돈다."""
    return asyncio.run(_plan_deep_research(job_id))


async def _plan_deep_research(job_id: str) -> dict:
    from services.research.planner import make_plan

    jid = _job_uuid(job_id)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            job = await db.get(ResearchJob, jid)
            if job is None:
                return {"error": "job not found", "job_id": job_id}

            if not await _claim(db, jid, allowed=("created",), to="planning"):
                log.warning("[research] 이미 계획 중이거나 계획된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}

            await db.refresh(job)
            seq = await _next_seq(db, jid)
            row = await _step(db, jid, seq, "plan", "연구 계획 수립",
                              detail="질문을 하위질문으로 분해하는 중입니다")
            try:
                params = merge_params(job.params or {})
                plan = await make_plan(job.question, params=params)
                job.plan = plan
                _set_stage(job, "planned")
                job.status = "awaiting_approval"
                await _finish(db, row, "done", {"subquestions": plan})
            except SoftTimeLimitExceeded:
                await _finish(db, row, "failed", {"error": "시간 상한 초과"})
                raise
            except Exception as e:
                log.exception("[research] 계획 수립 실패 job=%s", jid)
                job.status = "failed"
                job.last_error = str(e)[:1000]
                await _finish(db, row, "failed", {"error": str(e)[:500]})
            await db.commit()
            return {"job_id": str(jid), "status": job.status}

    except SoftTimeLimitExceeded:
        return await _mark_timed_out(Session, jid)
    finally:
        await engine.dispose()


@celery_app.task(name="tasks.run_deep_research", queue="q_llm",
                 soft_time_limit=SOFT_LIMIT, time_limit=HARD_LIMIT)
def run_deep_research(job_id: str) -> dict:
    """동기 Celery 진입점. 잡 전체를 이벤트 루프 하나로 돌린다.

    단계마다 asyncio.run 을 부르지 않는 이유는 _job_engine 주석에 있다.
    """
    return asyncio.run(_run_deep_research(job_id))


async def _run_deep_research(job_id: str) -> dict:
    jid = _job_uuid(job_id)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            job = await db.get(ResearchJob, jid)
            if job is None:
                return {"error": "job not found", "job_id": job_id}

            # 재개 가능한 상태만 받는다. running 인 잡을 다시 받으면 재배달이다.
            if not await _claim(db, jid, allowed=RUNNABLE_STATUSES, to="running"):
                log.warning("[research] 이미 처리 중이거나 처리된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}

            await db.refresh(job)
            seq = await _next_seq(db, jid)

            async def _emit(kind, payload):
                await publish(str(jid), kind, payload)

            # ── 탐색: stage 가 이미 explored 면 건너뛰고 스냅샷을 되살린다 ──
            if job.stage == "explored" and job.state_snapshot:
                state = restore_state(str(jid), job.state_snapshot)
                log.info("[research] 탐색 건너뜀 — 스냅샷에서 재개 job=%s", job_id)
            else:
                state = ResearchState(
                    job_id=str(jid), question=job.question,
                    params=merge_params(job.params or {}),
                )
                state.subquestions = [
                    SubQuestion(idx=i, text=t) for i, t in enumerate(job.plan or [])
                ]
                state.corpus_range = await _corpus_range(db)

                for subq in state.subquestions:
                    if await _is_cancelled(db, jid):
                        # 이벤트 kind 도 상태와 같은 철자를 쓴다 — api/research.py 의
                        # TERMINAL_KINDS 가 이 값으로 스트림을 끊는다.
                        await _emit(STATUS_CANCELED, {})
                        return {"job_id": job_id, "status": STATUS_CANCELED}

                    row = await _step(db, jid, seq, "search", subq.text,
                                      subq_idx=subq.idx,
                                      detail=f"'{subq.text}' 관련 논문을 찾기 위해 검색 중입니다")
                    seq += 1
                    try:
                        await explore_subquestion(state, subq, db=db, emit=_emit)
                        await _finish(db, row, "done", {
                            "queries": subq.queries, "adopted": len(subq.evidence_ids),
                            "verdict": subq.verdict, "note": subq.note,
                            "parse_failed": subq.parse_failed,
                        })
                    except SoftTimeLimitExceeded:
                        # 아래 except Exception 보다 먼저 와야 한다. SoftTimeLimitExceeded
                        # 도 Exception 이라 거기서 삼키면 남은 하위질문을 계속 돌다가
                        # 하드 리밋에 프로세스째 죽고, 잡은 running 에 묶여 흔적도 안 남는다.
                        await _finish(db, row, "failed", {"error": "시간 상한 초과"})
                        raise
                    except Exception as e:
                        # 부분 실패는 전체 실패가 아니다 — 나머지 하위질문은 계속한다.
                        # 다만 failed 를 남겨야 보고서가 이걸 "근거 없음"(연구 결과)이
                        # 아니라 "오류로 확인 못함"(시스템 장애)으로 쓴다.
                        log.exception("[research] 하위질문 실패 job=%s idx=%s", jid, subq.idx)
                        subq.failed = True
                        await _finish(db, row, "failed", {"error": str(e)[:500]})

                # 체크포인트. 여기까지가 비싼 구간이고, 종합은 다시 돌려도 싸다.
                _set_stage(job, "explored")
                job.state_snapshot = snapshot_state(state)
                await db.commit()

            # ── 종합 ──
            row = await _step(db, jid, seq, "synthesize", "보고서 종합")
            try:
                report = await synthesize(state)
                job.report = report
                _set_stage(job, "synthesized")
                job.status = "completed"
                await _finish(db, row, "done", {"sections": len(report["sections"])})
                await _emit("done", {"status": "completed"})
            except SoftTimeLimitExceeded:
                await _finish(db, row, "failed", {"error": "시간 상한 초과"})
                raise
            except Exception as e:
                # stage 는 explored 로 남는다 → 재시도가 탐색을 건너뛰고 여기부터 온다.
                # 그 재시도를 거는 곳이 POST /api/research/{job_id}/retry 다.
                log.exception("[research] 종합 실패 job=%s", jid)
                job.status = "failed"
                job.last_error = str(e)[:1000]
                await _finish(db, row, "failed", {"error": str(e)[:500]})
                await _emit("failed", {"error": str(e)[:200]})

            job.finished_at = _dt.datetime.now(_dt.timezone.utc)
            await db.commit()
            return {"job_id": str(jid), "status": job.status}

    except SoftTimeLimitExceeded:
        return await _mark_timed_out(Session, jid)
    finally:
        # 루프가 죽기 전에 커넥션을 닫는다. 빠뜨리면 다음 잡이 남은 커넥션을 만난다.
        await engine.dispose()


async def _mark_timed_out(Session, jid: uuid.UUID) -> dict:
    """하드 리밋에 죽으면 상태를 못 남긴다. 소프트에서 잡아 흔적을 남긴다.

    stage 는 건드리지 않는다 — 탐색까지 끝낸 뒤 종합에서 시간을 넘긴 잡은
    재시도가 스냅샷에서 이어받을 수 있어야 한다.
    """
    log.error("[research] 시간 상한 초과 job=%s", jid)
    async with Session() as db:
        await db.execute(
            update(ResearchJob).where(ResearchJob.id == jid).values(
                status="failed", last_error="시간 상한 초과 — 워커를 회수했다",
                finished_at=_dt.datetime.now(_dt.timezone.utc),
            )
        )
        await db.commit()
    return {"job_id": str(jid), "status": "failed"}


@celery_app.task(name="tasks.reap_stale_research", queue="q_control")
def reap_stale_research() -> dict:
    """멈춰버린 리서치를 실패로 떨어뜨린다.

    딥리서치는 한 번에 5~7분이고 종합이 길어도 10분을 안 넘는다.
    30분 넘게 running 이면 워커가 죽은 것이다.

    approved·queued 는 회수하지 않는다 — 아직 워커가 집지 않은 정상 대기 상태다.
    """
    db = SyncSessionLocal()
    try:
        steps = db.execute(sa_text(
            "UPDATE research_steps SET status = 'failed', "
            "       result = result || '{\"error\": \"stale — 워커 응답 없음\"}'::jsonb, "
            "       finished_at = now() "
            "WHERE status = 'running' "
            "  AND updated_at < now() - make_interval(mins => :m) "
            "RETURNING job_id"
        ), {"m": STALE_MINUTES}).fetchall()

        # coalesce 가 필요한 이유: started_at 은 선점 시점에 찍힌다. planning 단계에서
        # 워커가 죽으면 started_at 이 NULL 이고, NULL 비교는 NULL 이라 조건이 참이
        # 되지 않아 그 잡은 영원히 회수되지 않는다.
        jobs = db.execute(sa_text(
            "UPDATE research_jobs SET status = 'failed', "
            "       last_error = 'stale — 워커 응답 없음', finished_at = now() "
            "WHERE status IN ('planning', 'running') "
            "  AND coalesce(started_at, created_at) < now() - make_interval(mins => :m) "
            "RETURNING id"
        ), {"m": STALE_MINUTES}).fetchall()

        db.commit()
        return {"steps": len(steps), "jobs": len(jobs)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
