"""
job_runtime.py — 배치 잡 레이어 (단계 태스크 + 디스패처 + stale 복구)

구성:
  stage_extract / stage_summarize / stage_embed_index / stage_finalize
      : stages.run_* 의 thin wrapper — 아이템 상태 전이, 타이밍, error_group 기록
  dispatch_job_items (beat 30s)
      : running 잡마다 high_water 까지 pending 아이템을 단계 체인으로 디스패치
        + stale 아이템 복구 + 잡 완료 판정
  cleanup_temp_files (beat 1h)
      : 임시 다운로드/완료 잡 아티팩트 정리 + Milvus 주기 flush

핵심 규칙:
  - item.stage  = 마지막 완료된 체크포인트 → 재시도는 그 다음 단계부터 체인 구성
  - item.status = 실행 상태. 자동 재시도: failed && attempt < max_attempts 인 아이템을
    디스패처가 다시 픽업 (수동 재시도 API는 status='pending' + attempt 리셋)
"""
import datetime as _dt
import logging
import os
import time

from celery import chain

from core.config import get_settings
from core.lock import BookLock
from db.postgres import SyncSessionLocal
from models.ingest_job import IngestJob, IngestJobItem
from services.ingestion.stages import (
    CHECKPOINT_TO_REMAINING,
    STAGE_CHECKPOINT,
    STAGE_FUNCS,
    StageContext,
    StageError,
)
from workers.celery_app import celery_app

log = logging.getLogger(__name__)
cfg = get_settings()


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _stage_timeout(stage_name: str) -> int:
    return {
        "extract": cfg.INGEST_STAGE_TIMEOUT_EXTRACT,
        "summarize": cfg.INGEST_STAGE_TIMEOUT_SUMMARIZE,
        "embed_index": cfg.INGEST_STAGE_TIMEOUT_EMBED,
        "finalize": cfg.INGEST_STAGE_TIMEOUT_FINALIZE,
    }[stage_name]


# 디스패치 후 워커가 잡기까지의 허용 대기 (큐 적체 고려 — visibility_timeout 의 2배)
DISPATCH_STALE_SECONDS = cfg.DISPATCH_STALE_SECONDS


def classify_error(exc: BaseException) -> str:
    """예외 → error_group 분류 (대시보드의 실패 그룹/일괄 재시도 단위)."""
    if isinstance(exc, StageError):
        return exc.error_group
    try:
        import httpx
        if isinstance(exc, httpx.TimeoutException):
            return "llm_timeout"
        if isinstance(exc, httpx.HTTPStatusError):
            return "llm_error"
        if isinstance(exc, httpx.HTTPError):
            return "llm_error"
    except ImportError:
        pass
    name = type(exc).__name__
    msg = str(exc).lower()
    if "milvus" in msg or name.lower().startswith("milvus"):
        return "milvus_error"
    if name == "S3Error" or "minio" in msg:
        return "minio_error"
    if "vlm" in msg:
        return "vlm_error"
    return "unknown"


# ── 단계 태스크 공통 래퍼 ─────────────────────────────────────


def _run_stage(stage_name: str, item_id: int, celery_task_id: str | None) -> dict:
    from workers.tasks import _set_ingest_state

    db = SyncSessionLocal()
    try:
        item = db.query(IngestJobItem).filter_by(id=item_id).first()
        if not item:
            return {"item_id": item_id, "skipped": "not_found"}
        job = db.query(IngestJob).filter_by(id=item.job_id).first()
        if item.status == "canceled" or (job and job.status == "canceled"):
            return {"item_id": item_id, "skipped": "canceled"}
        book_id = item.book_id
        source_key = item.source_key
        params = dict(job.params or {}) if job else {}
    finally:
        db.close()

    timeout = _stage_timeout(stage_name)
    lock = BookLock(book_id, ttl=timeout)
    if not lock.acquire():
        # 다른 워커가 처리 중 — pending 으로 되돌려 디스패처가 재픽업
        _update_item(item_id, status="pending")
        log.warning(f"[{book_id}] item={item_id} 락 경합 → pending 복귀")
        return {"item_id": item_id, "skipped": "locked"}

    t0 = time.monotonic()
    _update_item(
        item_id,
        status="running",
        celery_task_id=celery_task_id,
        set_started=True,
    )
    if stage_name == "extract":
        _set_ingest_state(book_id, "processing", task_id=celery_task_id)

    try:
        ctx = StageContext(
            book_id=book_id,
            source_key=source_key,
            job_item_id=item_id,
            params=params,
        )
        result = STAGE_FUNCS[stage_name](ctx) or {}
        elapsed = round(time.monotonic() - t0, 1)

        is_final = stage_name == "finalize"
        _update_item(
            item_id,
            stage=STAGE_CHECKPOINT[stage_name],
            status="done" if is_final else "running",
            timing=(stage_name, elapsed),
            meta_update=result,
            set_finished=is_final,
        )
        if is_final:
            _set_ingest_state(book_id, "embedded", task_id=celery_task_id)
        return {"item_id": item_id, "stage": stage_name, "elapsed_s": elapsed}
    except Exception as e:
        group = classify_error(e)
        log.exception(f"[{book_id}] item={item_id} {stage_name} 실패 ({group}): {e}")
        _update_item(
            item_id,
            status="failed",
            error_group=group,
            last_error=str(e)[:2000],
            bump_attempt=True,
            timing=(stage_name, round(time.monotonic() - t0, 1)),
        )
        _set_ingest_state(book_id, "failed", task_id=celery_task_id, error=str(e))
        raise  # 체인 중단 (남은 단계 실행 안 함)
    finally:
        lock.release()


def _update_item(
    item_id: int,
    *,
    stage: str | None = None,
    status: str | None = None,
    error_group: str | None = None,
    last_error: str | None = None,
    celery_task_id: str | None = None,
    timing: tuple[str, float] | None = None,
    meta_update: dict | None = None,
    bump_attempt: bool = False,
    set_started: bool = False,
    set_finished: bool = False,
) -> None:
    db = SyncSessionLocal()
    try:
        item = db.query(IngestJobItem).filter_by(id=item_id).with_for_update().first()
        if not item:
            return
        if stage is not None:
            item.stage = stage
        if status is not None:
            item.status = status
            if status != "failed":
                item.error_group = None
        if error_group is not None:
            item.error_group = error_group
        if last_error is not None:
            item.last_error = last_error
        if celery_task_id is not None:
            item.celery_task_id = celery_task_id
        if timing is not None:
            item.stage_timings = {**(item.stage_timings or {}), f"{timing[0]}_s": timing[1]}
        if meta_update:
            # JSON 직렬화 가능한 값만 기록
            safe = {k: v for k, v in meta_update.items()
                    if isinstance(v, (str, int, float, bool, type(None)))}
            item.meta = {**(item.meta or {}), **safe}
        if bump_attempt:
            item.attempt = (item.attempt or 0) + 1
        now = _now()
        if set_started and item.started_at is None:
            item.started_at = now
        if set_finished:
            item.finished_at = now
        item.updated_at = now
        db.commit()
    except Exception as e:
        db.rollback()
        log.warning(f"item={item_id} 상태 갱신 실패: {e}")
    finally:
        db.close()


@celery_app.task(name="tasks.stage_extract", bind=True, acks_late=True)
def stage_extract(self, item_id: int):
    return _run_stage("extract", item_id, self.request.id)


@celery_app.task(name="tasks.stage_summarize", bind=True, acks_late=True)
def stage_summarize(self, item_id: int):
    return _run_stage("summarize", item_id, self.request.id)


@celery_app.task(name="tasks.stage_embed_index", bind=True, acks_late=True)
def stage_embed_index(self, item_id: int):
    return _run_stage("embed_index", item_id, self.request.id)


@celery_app.task(name="tasks.stage_finalize", bind=True, acks_late=True)
def stage_finalize(self, item_id: int):
    return _run_stage("finalize", item_id, self.request.id)


_STAGE_TASKS = {
    "extract": stage_extract,
    "summarize": stage_summarize,
    "embed_index": stage_embed_index,
    "finalize": stage_finalize,
}


def build_item_chain(item_stage: str, item_id: int):
    """체크포인트 기준 남은 단계 체인 구성. 남은 단계 없으면 None."""
    remaining = CHECKPOINT_TO_REMAINING.get(item_stage, list(STAGE_CHECKPOINT))
    if not remaining:
        return None
    return chain(*[_STAGE_TASKS[s].si(item_id) for s in remaining])


# ── 디스패처 (beat 30s) ───────────────────────────────────────


@celery_app.task(name="tasks.dispatch_job_items")
def dispatch_job_items():
    db = SyncSessionLocal()
    summary = {"dispatched": 0, "stale_recovered": 0, "completed_jobs": 0}
    try:
        jobs = db.query(IngestJob).filter(IngestJob.status == "running").all()
        for job in jobs:
            summary["stale_recovered"] += _recover_stale(db, job)
            summary["dispatched"] += _dispatch_for_job(db, job)
            if _maybe_complete(db, job):
                summary["completed_jobs"] += 1
        return summary
    finally:
        db.close()


def _recover_stale(db, job) -> int:
    """워커 사망 등으로 멈춘 아이템 → failed(stale) 전이 (자동 재시도 대상이 됨)."""
    now = _now()
    recovered = 0
    inflight = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("dispatched", "running")),
        )
        .all()
    )
    for item in inflight:
        if item.status == "dispatched":
            timeout = DISPATCH_STALE_SECONDS
        else:
            remaining = CHECKPOINT_TO_REMAINING.get(item.stage) or ["extract"]
            timeout = _stage_timeout(remaining[0])
        ref = item.updated_at or item.dispatched_at or item.created_at
        if ref is None:
            continue
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=_dt.timezone.utc)
        if (now - ref).total_seconds() > timeout:
            item.status = "failed"
            item.error_group = "stale"
            item.last_error = f"{timeout}s 무응답 — 워커 중단 추정 (stale 복구)"
            item.attempt = (item.attempt or 0) + 1
            item.updated_at = now
            recovered += 1
            log.warning(f"[{item.book_id}] item={item.id} stale 복구 (stage={item.stage})")
    if recovered:
        db.commit()
    return recovered


def _dispatch_for_job(db, job) -> int:
    params = dict(job.params or {})
    high_water = int(params.get("high_water") or cfg.INGEST_HIGH_WATER)
    max_attempts = int(params.get("max_attempts") or cfg.INGEST_MAX_ATTEMPTS)

    in_flight = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("dispatched", "running")),
        )
        .count()
    )
    need = high_water - in_flight
    if need <= 0:
        return 0

    # pending(신규/수동 재시도) + failed(자동 재시도, attempt < max)
    items = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("pending", "failed")),
            IngestJobItem.attempt < max_attempts,
        )
        .order_by(IngestJobItem.id)
        .limit(need)
        .with_for_update(skip_locked=True)
        .all()
    )

    dispatched = 0
    now = _now()
    for item in items:
        sig = build_item_chain(item.stage, item.id)
        if sig is None:
            item.status = "done"
            item.finished_at = now
            item.updated_at = now
            continue
        res = sig.apply_async()
        item.status = "dispatched"
        item.dispatched_at = now
        item.updated_at = now
        item.celery_task_id = res.id
        dispatched += 1
    db.commit()
    return dispatched


def _maybe_complete(db, job) -> bool:
    """더 처리할 아이템이 없으면 잡 완료 처리."""
    params = dict(job.params or {})
    max_attempts = int(params.get("max_attempts") or cfg.INGEST_MAX_ATTEMPTS)

    in_flight = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("dispatched", "running")),
        )
        .count()
    )
    if in_flight:
        return False
    eligible = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("pending", "failed")),
            IngestJobItem.attempt < max_attempts,
        )
        .count()
    )
    if eligible:
        return False

    failed = (
        db.query(IngestJobItem)
        .filter(IngestJobItem.job_id == job.id, IngestJobItem.status == "failed")
        .count()
    )
    job.status = "completed_with_errors" if failed else "completed"
    job.finished_at = _now()
    db.commit()
    log.info(f"잡 '{job.name}' 완료 — status={job.status} (failed={failed})")
    return True


# ── 정리 태스크 (beat 1h) ─────────────────────────────────────


@celery_app.task(name="tasks.cleanup_temp_files")
def cleanup_temp_files(max_age_hours: int = 24):
    """임시 다운로드 파일 정리 + Milvus 주기 flush (num_entities 최신화)."""
    download_dir = "/app/data/downloads"
    removed = 0
    cutoff = time.time() - max_age_hours * 3600
    if os.path.isdir(download_dir):
        for name in os.listdir(download_dir):
            path = os.path.join(download_dir, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue

    # 건당 flush 제거에 대한 보상 — 주기 flush 1회 (검색 num_entities 가드 최신화)
    try:
        from services.ingestion.indexer import ensure_collection
        ensure_collection().flush()
    except Exception as e:
        log.warning(f"주기 Milvus flush 실패: {e}")

    log.info(f"cleanup_temp_files: 임시 파일 {removed}개 삭제")
    return {"removed": removed}
