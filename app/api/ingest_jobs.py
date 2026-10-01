"""
api/ingest_jobs.py — 대량 인덱싱 배치 잡 관리 API

POST   /api/admin/ingest-jobs            잡 생성 (매니페스트 검증 → items 적재 → ready)
GET    /api/admin/ingest-jobs            잡 목록
GET    /api/admin/ingest-jobs/{id}       잡 상세 (stage/status 카운트, 처리율 1h·24h, ETA)
POST   /api/admin/ingest-jobs/{id}/start|pause|resume|cancel
GET    /api/admin/ingest-jobs/{id}/items 아이템 목록 (status/stage/error_group 필터)
GET    /api/admin/ingest-jobs/{id}/failures   error_group별 집계
POST   /api/admin/ingest-jobs/{id}/retry      실패 아이템 재시도
"""
import datetime as _dt
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import func, literal_column, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from models.ingest_job import IngestJob, IngestJobItem

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/ingest-jobs", tags=["ingest-jobs"])


# ── 요청 스키마 ───────────────────────────────────────────────
class CreateJobBody(BaseModel):
    name: str
    manifest_key: str
    params: dict = {}


class RetryBody(BaseModel):
    error_group: str | None = None
    item_ids: list[int] | None = None
    all_failed: bool = False
    force_all: bool = False
    reset_stage: str | None = None


def _job_dict(job: IngestJob) -> dict:
    return {
        "id": str(job.id),
        "name": job.name,
        "kind": job.kind,
        "status": job.status,
        "manifest_key": job.manifest_key,
        "params": job.params,
        "total_items": job.total_items,
        "validation_report": job.validation_report,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


# ── 생성 ──────────────────────────────────────────────────────
@router.post("")
async def create_job(body: CreateJobBody):
    """매니페스트 dry-run 검증 후 잡 + 아이템 생성 (status='ready'). 무거운 작업은 threadpool."""
    from services.ingestion.job_manager import create_job as _create

    try:
        result = await run_in_threadpool(
            _create, body.name, body.manifest_key, body.params,
        )
    except Exception as e:
        log.exception(f"잡 생성 실패: {e}")
        raise HTTPException(400, f"잡 생성 실패: {e}")
    return result


# ── 목록 ──────────────────────────────────────────────────────
@router.get("")
async def list_jobs(db: AsyncSession = Depends(get_db), limit: int = 50):
    rows = (await db.execute(
        select(IngestJob).order_by(IngestJob.created_at.desc()).limit(limit)
    )).scalars().all()
    return {"jobs": [_job_dict(j) for j in rows]}


# ── 상세 (카운트 + 처리율 + ETA) ──────────────────────────────
def compute_eta(remaining: int, done_last_24h: int, status: str) -> float | None:
    """남은 건수 ÷ 최근 24시간의 시간당 처리량(시간). 멈춘 잡·처리량 0 이면 None.

    1시간 창은 스캔본(VLM)이 몰리면 처리량이 몇 분의 1로 떨어져 ETA 가 48시간 기준의
    0.73~5.7배로 출렁였다. 24시간 창은 두 구간(ODL·스캔본)이 섞여 덜 흔들린다.
    """
    if status == "paused":
        return None
    if remaining <= 0:
        return 0.0
    if done_last_24h <= 0:
        return None
    return round(remaining * 24 / done_last_24h, 1)


def _done_since(job_id: str, since: _dt.datetime):
    return select(func.count()).where(
        IngestJobItem.job_id == job_id,
        IngestJobItem.status == "done",
        IngestJobItem.finished_at >= since,
    )


def _permanently_failed(job_id: str, max_attempts: int):
    """자동 재시도 한도에 닿은 failed — 디스패처가 다시 집지 않는다(수동 retry 전까지)."""
    return select(func.count()).where(
        IngestJobItem.job_id == job_id,
        IngestJobItem.status == "failed",
        IngestJobItem.attempt >= max_attempts,
    )


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(IngestJob).where(IngestJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "잡 없음")

    # status별 / stage별 카운트 (각 1회 GROUP BY)
    status_rows = (await db.execute(
        select(IngestJobItem.status, func.count())
        .where(IngestJobItem.job_id == job_id)
        .group_by(IngestJobItem.status)
    )).all()
    stage_rows = (await db.execute(
        select(IngestJobItem.stage, func.count())
        .where(IngestJobItem.job_id == job_id)
        .group_by(IngestJobItem.stage)
    )).all()
    status_counts = {s: c for s, c in status_rows}
    stage_counts = {s: c for s, c in stage_rows}

    # 처리율: 최근 1시간·24시간 done 건수. ETA 는 24시간 기준(compute_eta)
    now = _dt.datetime.now(_dt.timezone.utc)
    done_last_hour = (await db.execute(
        _done_since(job_id, now - _dt.timedelta(hours=1))
    )).scalar() or 0
    done_last_24h = (await db.execute(
        _done_since(job_id, now - _dt.timedelta(hours=24))
    )).scalar() or 0

    # 영구 실패는 더 처리되지 않으므로 남은 수에서 뺀다
    params = dict(job.params or {})
    max_attempts = int(params.get("max_attempts") or get_settings().INGEST_MAX_ATTEMPTS)
    permanently_failed = (await db.execute(
        _permanently_failed(job_id, max_attempts)
    )).scalar() or 0

    done_total = status_counts.get("done", 0)
    remaining = job.total_items - done_total - permanently_failed
    rate_per_hour = done_last_hour
    rate_per_hour_24h = round(done_last_24h / 24, 1)
    eta_hours = compute_eta(remaining, done_last_24h, job.status)

    # 추출 방법 분포 (meta.extract_method)
    _extract_method = literal_column("ingest_job_items.meta ->> 'extract_method'")
    method_rows = (await db.execute(
        select(_extract_method, func.count())
        .select_from(IngestJobItem)
        .where(IngestJobItem.job_id == job_id)
        .group_by(_extract_method)
    )).all()
    extract_methods = {(m or "unknown"): c for m, c in method_rows}

    return {
        **_job_dict(job),
        "status_counts": status_counts,
        "stage_counts": stage_counts,
        "done_total": done_total,
        "permanently_failed": permanently_failed,
        "remaining": remaining,
        "rate_per_hour": rate_per_hour,
        "rate_per_hour_24h": rate_per_hour_24h,
        "eta_hours": eta_hours,
        "extract_methods": extract_methods,
    }


# ── 상태 제어 ─────────────────────────────────────────────────
async def _set_status(db: AsyncSession, job_id: str, new_status: str, **extra) -> dict:
    job = (await db.execute(select(IngestJob).where(IngestJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "잡 없음")
    job.status = new_status
    for k, v in extra.items():
        setattr(job, k, v)
    await db.commit()
    return {"id": job_id, "status": new_status}


@router.post("/{job_id}/start")
async def start_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """디스패처가 픽업하도록 running 전환. ready/paused/completed* 에서 호출 가능."""
    return await _set_status(
        db, job_id, "running",
        started_at=_dt.datetime.now(_dt.timezone.utc),
        finished_at=None,
    )


@router.post("/{job_id}/pause")
async def pause_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """신규 디스패치만 중단 (진행 중 아이템은 완료까지 진행)."""
    return await _set_status(db, job_id, "paused")


@router.post("/{job_id}/resume")
async def resume_job(job_id: str, db: AsyncSession = Depends(get_db)):
    return await _set_status(db, job_id, "running")


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """잡 취소 + pending/failed 아이템을 canceled 로 (진행 중 건은 자연 종료)."""
    job = (await db.execute(select(IngestJob).where(IngestJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "잡 없음")
    job.status = "canceled"
    job.finished_at = _dt.datetime.now(_dt.timezone.utc)
    await db.execute(
        update(IngestJobItem)
        .where(
            IngestJobItem.job_id == job_id,
            IngestJobItem.status.in_(("pending", "failed")),
        )
        .values(status="canceled")
    )
    await db.commit()
    return {"id": job_id, "status": "canceled"}


# ── 아이템 목록 ───────────────────────────────────────────────
@router.get("/{job_id}/items")
async def list_items(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    stage: str | None = None,
    error_group: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    conds = [IngestJobItem.job_id == job_id]
    if status:
        conds.append(IngestJobItem.status == status)
    if stage:
        conds.append(IngestJobItem.stage == stage)
    if error_group:
        conds.append(IngestJobItem.error_group == error_group)

    total = (await db.execute(
        select(func.count()).select_from(IngestJobItem).where(*conds)
    )).scalar() or 0
    rows = (await db.execute(
        select(IngestJobItem)
        .where(*conds)
        .order_by(IngestJobItem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": it.id,
                "book_id": it.book_id,
                "stage": it.stage,
                "status": it.status,
                "attempt": it.attempt,
                "error_group": it.error_group,
                "last_error": it.last_error,
                "stage_timings": it.stage_timings,
                "meta": it.meta,
                "updated_at": it.updated_at.isoformat() if it.updated_at else None,
            }
            for it in rows
        ],
    }


# ── 실패 그룹 집계 ────────────────────────────────────────────
def _failure_groups(job_id: str):
    # 대표 메시지는 그룹 안에서 가장 흔한 것(mode). max() 는 사전순 최댓값이라
    # not_found 545건('섹션 없음')이 15건뿐인 '카탈로그 row 없음'으로 보였다.
    return (
        select(
            IngestJobItem.error_group,
            func.count(),
            func.mode().within_group(IngestJobItem.last_error),
        )
        .where(IngestJobItem.job_id == job_id, IngestJobItem.status == "failed")
        .group_by(IngestJobItem.error_group)
        .order_by(func.count().desc())
    )


@router.get("/{job_id}/failures")
async def list_failures(job_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(_failure_groups(job_id))).all()
    return {
        "groups": [
            {"error_group": g or "unknown", "count": c, "sample_error": (err or "")[:300]}
            for g, c, err in rows
        ]
    }


# ── 재시도 ────────────────────────────────────────────────────
@router.post("/{job_id}/retry")
async def retry_job(job_id: str, body: RetryBody):
    from services.ingestion.job_manager import retry_items

    count = await run_in_threadpool(
        retry_items, job_id,
        error_group=body.error_group,
        item_ids=body.item_ids,
        all_failed=body.all_failed,
        force_all=body.force_all,
        reset_stage=body.reset_stage,
    )
    return {"id": job_id, "retried": count}
