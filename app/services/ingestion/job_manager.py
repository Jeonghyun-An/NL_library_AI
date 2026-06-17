"""
job_manager.py — 배치 잡 생성/검증/제어 (동기, API가 threadpool로 호출)

핵심:
  build_job_plan()       : 순수 로직 — 매니페스트 + 현재 상태 → (insert할 아이템, 검증 리포트)
  create_job()           : 매니페스트 로드 → dry-run 검증 → items bulk insert → ready
  retry_items()          : 실패 아이템 status='pending' 리셋 (stage 유지 → 실패 단계부터 재개)
"""
import gzip
import json
import logging
import uuid

log = logging.getLogger(__name__)


def _cfg():
    from core.config import get_settings

    return get_settings()


# ── 순수 계획 수립 (단위 테스트 대상) ─────────────────────────


def build_job_plan(
    manifest: list[dict],
    existing_keys: set[str],
    meta_ids: set[str],
    embedded_ids: set[str],
    *,
    reembed: bool = False,
) -> tuple[list[dict], dict]:
    """
    매니페스트 + 현재 상태 → (insert할 아이템 리스트, 검증 리포트).

    스킵 규칙:
      - 매니페스트 내 중복 book_id (첫 행만 채택)
      - MinIO에 object_key 없음
      - PG에 메타(cnts_id) 없음
      - 이미 embedded (reembed=True면 무시)
    """
    seen: set[str] = set()
    items: list[dict] = []
    duplicates: list[str] = []
    missing_object: list[str] = []
    missing_meta: list[str] = []
    already_embedded: list[str] = []

    for row in manifest:
        book_id = row.get("book_id")
        if not book_id:
            continue
        if book_id in seen:
            duplicates.append(book_id)
            continue
        seen.add(book_id)

        object_key = row.get("object_key") or f"originals/{book_id}/{book_id}.pdf"
        if object_key not in existing_keys:
            missing_object.append(book_id)
            continue
        if book_id not in meta_ids:
            missing_meta.append(book_id)
            continue
        if not reembed and book_id in embedded_ids:
            already_embedded.append(book_id)
            continue

        items.append({
            "book_id": book_id,
            "source_key": object_key,
            "stage": "pending",
            "status": "pending",
        })

    report = {
        "total_manifest": len(manifest),
        "to_ingest": len(items),
        "duplicates": sorted(set(duplicates)),
        "missing_object": sorted(missing_object),
        "missing_meta": sorted(missing_meta),
        "already_embedded": sorted(already_embedded),
    }
    return items, report


# ── MinIO / PG 상태 수집 ──────────────────────────────────────


def _load_manifest(manifest_key: str) -> list[dict]:
    from services.ingestion.stages import minio_client

    cfg = _cfg()
    client = minio_client()
    resp = client.get_object(cfg.MINIO_BUCKET, manifest_key)
    raw = resp.read()
    resp.close()
    resp.release_conn()
    if manifest_key.endswith(".gz"):
        raw = gzip.decompress(raw)
    rows = []
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _list_existing_keys(prefix: str = "originals/") -> set[str]:
    from services.ingestion.stages import minio_client

    cfg = _cfg()
    client = minio_client()
    return {
        obj.object_name
        for obj in client.list_objects(cfg.MINIO_BUCKET, prefix=prefix, recursive=True)
    }


def _fetch_id_sets(db, book_ids: list[str]) -> tuple[set[str], set[str]]:
    """(메타 존재 ID, embedded ID) — 큰 IN 절을 피해 청크로 조회."""
    from models.book import Book

    meta_ids: set[str] = set()
    embedded_ids: set[str] = set()
    CHUNK = _cfg().JOB_MANAGER_CHUNK_SIZE
    for i in range(0, len(book_ids), CHUNK):
        batch = book_ids[i:i + CHUNK]
        rows = (
            db.query(Book.cnts_id, Book.is_embedded)
            .filter(Book.cnts_id.in_(batch))
            .all()
        )
        for cnts_id, is_embedded in rows:
            meta_ids.add(cnts_id)
            if is_embedded:
                embedded_ids.add(cnts_id)
    return meta_ids, embedded_ids


# ── 잡 생성 ───────────────────────────────────────────────────


def create_job(name: str, manifest_key: str, params: dict, created_by: str | None = None) -> dict:
    """매니페스트 로드 → dry-run 검증 → items bulk insert → status='ready'."""
    from sqlalchemy import insert as sa_insert
    from db.postgres import SyncSessionLocal
    from models.ingest_job import IngestJob, IngestJobItem

    manifest = _load_manifest(manifest_key)
    book_ids = [r["book_id"] for r in manifest if r.get("book_id")]
    existing_keys = _list_existing_keys()

    db = SyncSessionLocal()
    try:
        meta_ids, embedded_ids = _fetch_id_sets(db, list(dict.fromkeys(book_ids)))
        items, report = build_job_plan(
            manifest, existing_keys, meta_ids, embedded_ids,
            reembed=bool(params.get("reembed")),
        )

        job_id = uuid.uuid4()
        db.add(IngestJob(
            id=job_id,
            name=name,
            kind=params.get("kind", "paper_bulk"),
            status="ready",
            manifest_key=manifest_key,
            params=params,
            total_items=len(items),
            validation_report=report,
            created_by=created_by,
        ))
        db.flush()

        # items bulk insert (배치)
        BATCH = _cfg().JOB_MANAGER_BATCH_SIZE
        for i in range(0, len(items), BATCH):
            batch = [{**it, "job_id": job_id} for it in items[i:i + BATCH]]
            if batch:
                db.execute(sa_insert(IngestJobItem), batch)
        db.commit()

        log.info(f"잡 '{name}' 생성: {len(items)}건 ({report})")
        return {"job_id": str(job_id), "total_items": len(items), "validation_report": report}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── 재시도 ────────────────────────────────────────────────────


def retry_items(
    job_id: str,
    *,
    error_group: str | None = None,
    item_ids: list[int] | None = None,
    all_failed: bool = False,
    reset_stage: str | None = None,
) -> int:
    """실패 아이템을 status='pending'으로 리셋 → 디스패처가 재픽업.

    attempt=0 으로 리셋 (max_attempts 초과분도 재시도 가능), stage는 유지.
    reset_stage 지정 시 처음부터(특정 체크포인트부터) 재실행.
    """
    from db.postgres import SyncSessionLocal
    from models.ingest_job import IngestJob, IngestJobItem

    db = SyncSessionLocal()
    try:
        q = db.query(IngestJobItem).filter(IngestJobItem.job_id == job_id)
        if item_ids:
            q = q.filter(IngestJobItem.id.in_(item_ids))
        elif error_group:
            q = q.filter(
                IngestJobItem.status == "failed",
                IngestJobItem.error_group == error_group,
            )
        elif all_failed:
            q = q.filter(IngestJobItem.status == "failed")
        else:
            return 0

        update_vals = {
            "status": "pending",
            "error_group": None,
            "last_error": None,
            "attempt": 0,
        }
        if reset_stage:
            update_vals["stage"] = reset_stage
        count = q.update(update_vals, synchronize_session=False)

        # 잡이 완료 상태였으면 다시 running 으로 (디스패처가 픽업하도록)
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if job and job.status in ("completed", "completed_with_errors"):
            job.status = "running"
            job.finished_at = None
        db.commit()
        log.info(f"잡 {job_id} 재시도: {count}건 pending 리셋")
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
