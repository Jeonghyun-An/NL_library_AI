"""
workers/tasks.py — Celery 비동기 작업

파이프라인 본체는 services/ingestion/stages.py 의 4단계 함수로 분해되어 있다:
  extract → summarize → embed_index → finalize

이 모듈은 두 가지 실행 경로를 제공한다:
  ① 단건 흐름 (process_book_file)      : 4단계를 한 태스크에서 순차 실행 (기존 API 호환)
  ② 배치 잡 흐름 (workers/job_runtime) : 단계별 태스크 + 디스패처 (대량 인덱싱)
"""
import logging
import datetime as _dt

from workers.celery_app import celery_app
from core.config import get_settings
from core.lock import BookLock
from db.postgres import SyncSessionLocal
from models.book import Book
from services.ingestion.stages import (
    StageContext,
    run_extract,
    run_summarize,
    run_embed_index,
    run_finalize,
)

log = logging.getLogger(__name__)
cfg = get_settings()


def _normalize_book_id(raw_id: str) -> str:
    """MinIO 폴더명 등에서 추출한 book_id 정규화.
    끝에 붙은 _ 나 공백 제거 (예: CNTS-00052470502_ → CNTS-00052470502).
    """
    return raw_id.strip().rstrip("_").strip()


def _set_ingest_state(
    book_id: str,
    state: str,
    *,
    task_id: str | None = None,
    error: str | None = None,
    source_key: str | None = None,
) -> None:
    """library_catalog 의 인덱싱 상태 컬럼을 갱신. 도서 row 가 없으면 무시."""
    db = SyncSessionLocal()
    try:
        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if not book:
            return
        book.ingest_state = state
        if task_id is not None:
            book.ingest_task_id = task_id
        if source_key is not None:
            book.ingest_source_key = source_key
        if error is not None:
            book.ingest_error = error[:2000]
        now = _dt.datetime.now(_dt.timezone.utc)
        if state == "processing":
            book.ingest_started_at = now
            book.ingest_error = None
        elif state in ("embedded", "failed", "canceled"):
            book.ingest_finished_at = now
        db.commit()
    except Exception as e:
        db.rollback()
        log.warning(f"[{book_id}] ingest_state 갱신 실패 ({state}): {e}")
    finally:
        db.close()


# ── 1. 카탈로그 메타데이터 적재 (프로파일 로더 + bulk upsert) ──
@celery_app.task(name="tasks.load_catalog_file", queue="ingestion")
def load_catalog_file(file_path: str, loader_id: str | None = None):
    """범용 메타 적재 — 프로파일 로더 자동 판별 후 1,000행 배치 upsert."""
    from domains import get_active_profile
    from repositories.catalog_bulk import upsert_catalog_records

    profile = get_active_profile()
    loader = None
    if loader_id:
        loader = next((ld for ld in profile.loaders if ld.loader_id == loader_id), None)
        if loader is None:
            raise ValueError(f"loader_id '{loader_id}' 를 프로파일 '{profile.name}' 에서 찾을 수 없음")
    else:
        from domains.nl_library.loaders import read_headers
        headers = read_headers(file_path)
        loader = next(
            (ld for ld in profile.loaders if ld.detect(file_path, headers)), None,
        )
        if loader is None:
            raise ValueError(f"적합한 로더 없음 — 헤더: {headers}")

    log.info(f"카탈로그 적재 시작: {file_path} (loader={loader.loader_id})")
    db = SyncSessionLocal()
    try:
        return upsert_catalog_records(db, loader.load(file_path))
    finally:
        db.close()


# 레거시 태스크명 호환 래퍼 (api/book.py, api/paper.py 가 task name 으로 디스패치)
@celery_app.task(name="tasks.load_kci_catalog_xlsx", queue="ingestion")
def load_kci_catalog_xlsx(xlsx_path: str):
    return load_catalog_file(xlsx_path, loader_id="kci_xlsx")


@celery_app.task(name="tasks.load_catalog_xlsx", queue="ingestion")
def load_catalog_xlsx(xlsx_path: str):
    return load_catalog_file(xlsx_path, loader_id="nl_marc_mods_xlsx")


# ── 2. 단일 도서 원본 파일 처리 (단건 흐름 — 4단계 순차 실행) ──
@celery_app.task(
    name="tasks.process_book_file",
    queue="ingestion",
    bind=True,
)
def process_book_file(self, book_id: str, file_path: str, force: bool = False):
    """인덱싱 진입점. Redis 락 + ingest_state 전이를 담당하고 실제 처리는 stages 에 위임."""
    task_id = self.request.id

    # 이미 완료된 경우 락 경합 없이 빠른 경로로 스킵
    if not force:
        db = SyncSessionLocal()
        try:
            book = db.query(Book).filter_by(cnts_id=book_id).first()
            if book and book.ingest_state == "embedded":
                log.info(f"[{book_id}] 이미 임베딩 완료 — 스킵 (force=False)")
                return {"book_id": book_id, "status": "skipped", "reason": "already_embedded"}
        finally:
            db.close()

    lock = BookLock(book_id)
    if not lock.acquire():
        log.warning(f"[{book_id}] 이미 처리 중인 태스크 존재 — 새 태스크 {task_id} 스킵")
        return {"book_id": book_id, "status": "skipped", "reason": "locked"}

    _set_ingest_state(book_id, "processing", task_id=task_id)
    try:
        ctx = StageContext(book_id=book_id, file_path=file_path)
        extract_result = run_extract(ctx)
        summarize_result = run_summarize(ctx)
        embed_result = run_embed_index(ctx)
        finalize_result = run_finalize(ctx)
        _set_ingest_state(book_id, "embedded", task_id=task_id)
        return {
            "book_id": book_id,
            "status": "completed",
            "extraction": extract_result,
            "sections": extract_result.get("sections"),
            "summaries": summarize_result,
            "chunks": embed_result.get("chunks"),
            "indexed": embed_result.get("indexed"),
            "finalize": finalize_result,
        }
    except Exception as e:
        log.exception(f"[{book_id}] 인덱싱 실패: {e}")
        _set_ingest_state(book_id, "failed", task_id=task_id, error=str(e))
        raise
    finally:
        lock.release()
        _cleanup_download(file_path)


def _cleanup_download(file_path: str) -> None:
    """MinIO에서 받은 임시 다운로드 파일 삭제 (원본은 MinIO에 있으므로 안전)."""
    import os

    download_dir = os.path.realpath("/app/data/downloads")
    try:
        real = os.path.realpath(file_path)
        if real.startswith(download_dir + os.sep) and os.path.isfile(real):
            os.remove(real)
            log.info(f"임시 파일 삭제: {real}")
    except Exception as e:
        log.warning(f"임시 파일 삭제 실패 ({file_path}): {e}")


# ── 3. 배치 처리 ────────────────────────────────────────
@celery_app.task(name="tasks.ingest_batch", queue="ingestion")
def ingest_batch(file_mappings: list[dict]):
    results = []
    for item in file_mappings:
        task = process_book_file.delay(item["book_id"], item["file_path"])
        _set_ingest_state(item["book_id"], "pending", task_id=task.id)
        results.append({"book_id": item["book_id"], "task_id": task.id})
    return {"dispatched": len(results), "tasks": results}


# ── 3-b. cnts_id 목록 배치 인덱싱 ───────────────────────
@celery_app.task(name="tasks.ingest_books_batch", queue="ingestion")
def ingest_books_batch(cnts_ids: list[str], force: bool = False):
    """cnts_id 목록 → MinIO 원본 파일로 인덱싱 태스크 일괄 디스패치.

    force=False(기본): embedded·processing 상태 스킵
    force=True       : 모든 상태 강제 재인덱싱
    """
    db = SyncSessionLocal()
    dispatched: list[dict] = []
    skipped: list[dict] = []

    try:
        for cnts_id in cnts_ids:
            book = db.query(Book).filter_by(cnts_id=cnts_id).first()
            if not book:
                log.warning(f"[{cnts_id}] 도서 없음 — 스킵")
                skipped.append({"cnts_id": cnts_id, "reason": "not_found"})
                continue

            if not force:
                if book.ingest_state == "embedded":
                    log.info(f"[{cnts_id}] 이미 임베딩 완료 — 스킵")
                    skipped.append({"cnts_id": cnts_id, "reason": "already_embedded"})
                    continue
                if book.ingest_state == "processing":
                    log.info(f"[{cnts_id}] 처리 중 — 스킵")
                    skipped.append({"cnts_id": cnts_id, "reason": "processing"})
                    continue

            source_key = book.ingest_source_key
            if not source_key:
                from services.ingestion.stages import minio_client
                client = minio_client()
                # 구조 A: originals/{cnts_id}/ 폴더
                objects = list(client.list_objects(
                    cfg.MINIO_BUCKET, prefix=f"originals/{cnts_id}/", recursive=True
                ))
                # 구조 B: originals/{cnts_id}.pdf 플랫 파일
                if not objects:
                    flat_key = f"originals/{cnts_id}.pdf"
                    try:
                        client.stat_object(cfg.MINIO_BUCKET, flat_key)
                        objects = [type("obj", (), {"object_name": flat_key})()]
                    except Exception:
                        pass
                if not objects:
                    log.warning(f"[{cnts_id}] MinIO 파일 없음 — 스킵")
                    skipped.append({"cnts_id": cnts_id, "reason": "no_file"})
                    continue
                source_key = objects[0].object_name

            task = process_from_minio.delay(cnts_id, source_key)
            dispatched.append({"cnts_id": cnts_id, "task_id": task.id})
            log.info(f"[{cnts_id}] 인덱싱 디스패치: {task.id}")
    finally:
        db.close()

    log.info(f"ingest_books_batch 완료: 디스패치 {len(dispatched)}, 스킵 {len(skipped)}")
    return {"dispatched": len(dispatched), "skipped": len(skipped), "tasks": dispatched}


# ── 4. MinIO에서 파일 다운로드 후 처리 ───────────────────
@celery_app.task(name="tasks.process_from_minio", queue="ingestion", bind=True)
def process_from_minio(self, book_id: str, minio_key: str):
    from services.ingestion.stages import minio_client
    import os

    book_id = _normalize_book_id(book_id)

    # 디스패치 시점에 source_key 기록 → 재시도 시 참조
    _set_ingest_state(book_id, "pending", task_id=self.request.id, source_key=minio_key)

    client = minio_client()

    download_dir = "/app/data/downloads"
    os.makedirs(download_dir, exist_ok=True)
    local_path = os.path.join(download_dir, f"{book_id}.pdf")

    client.fget_object(cfg.MINIO_BUCKET, minio_key, local_path)
    log.info(f"[{book_id}] MinIO → {local_path} 다운로드 완료")

    task = process_book_file.delay(book_id, local_path)
    # 실제 처리 태스크 id로 갱신 (다운로드 태스크의 id 가 아닌)
    _set_ingest_state(book_id, "pending", task_id=task.id, source_key=minio_key)
    return {"book_id": book_id, "task_id": task.id}


# ── 4-b. 줄거리(plot) 백필 ───────────────────────────────
@celery_app.task(name="tasks.backfill_plot", queue="ingestion")
def backfill_plot(limit: int = 500, force: bool = False):
    """plot 미생성 도서의 줄거리를 섹션 요약 재사용으로 백필 (재추출 없음).

    force=False(기본): extra->>'plot' IS NULL 인 임베딩 완료 도서만 대상
    force=True       : 임베딩 완료 도서 전체 재생성
    paper는 abstract 대체로 생략. 섹션 요약 없는 도서 스킵.
    """
    from sqlalchemy import text as sa_text
    from sqlalchemy.orm.attributes import flag_modified
    from models.section import BookSection
    from services.ingestion.stages import run_async
    from services.ingestion.summarizer import generate_book_plot

    _GENERATE_DOC_TYPES = {"book", "literature", "policy"}
    db = SyncSessionLocal()
    done = skipped = failed = 0
    try:
        q = db.query(Book).filter(
            Book.is_embedded == True,  # noqa: E712
            Book.doc_type.in_(list(_GENERATE_DOC_TYPES)),
        )
        if not force:
            q = q.filter(sa_text("extra->>'plot' IS NULL"))
        books = q.limit(limit).all()
        log.info(f"backfill_plot 시작: 대상 {len(books)}권 (force={force})")

        for book in books:
            rows = (
                db.query(BookSection.summary)
                .filter_by(book_id=book.cnts_id)
                .order_by(BookSection.section_idx)
                .all()
            )
            valid = [r[0] for r in rows if r[0]]
            if not valid:
                skipped += 1
                continue
            try:
                plot = run_async(generate_book_plot(
                    title=book.title or book.cnts_id,
                    author=book.personal_author or book.corporate_author or "",
                    section_summaries=valid,
                    doc_type=book.doc_type or "book",
                ))
                if plot:
                    extra = dict(book.extra or {})
                    extra["plot"] = plot
                    book.extra = extra
                    flag_modified(book, "extra")
                    db.commit()
                    done += 1
                else:
                    skipped += 1
            except Exception as e:
                db.rollback()
                log.warning(f"[{book.cnts_id}] plot 백필 실패: {e}")
                failed += 1
    finally:
        db.close()

    log.info(f"backfill_plot 완료: done={done}, skipped={skipped}, failed={failed}")
    return {"done": done, "skipped": skipped, "failed": failed}


# ── 4-c. 독후 효과(read_effect) 백필 ────────────────────
@celery_app.task(name="tasks.backfill_read_effect", queue="ingestion")
def backfill_read_effect(limit: int = 500, force: bool = False):
    """read_effect 미생성 도서의 독후 효과를 섹션 요약 재사용으로 백필.

    force=False(기본): extra->>'read_effect' IS NULL 인 임베딩 완료 도서만 대상
    force=True       : 임베딩 완료 도서 전체 재생성
    paper는 생략. 섹션 요약 없는 도서 스킵.
    """
    from sqlalchemy import text as sa_text
    from sqlalchemy.orm.attributes import flag_modified
    from models.section import BookSection
    from services.ingestion.stages import run_async
    from services.ingestion.summarizer import generate_read_effect

    _GENERATE_DOC_TYPES = {"book", "literature", "policy"}
    db = SyncSessionLocal()
    done = skipped = failed = 0
    try:
        q = db.query(Book).filter(
            Book.is_embedded == True,  # noqa: E712
            Book.doc_type.in_(list(_GENERATE_DOC_TYPES)),
        )
        if not force:
            q = q.filter(sa_text("extra->>'read_effect' IS NULL"))
        books = q.limit(limit).all()
        log.info(f"backfill_read_effect 시작: 대상 {len(books)}권 (force={force})")

        for book in books:
            rows = (
                db.query(BookSection.summary)
                .filter_by(book_id=book.cnts_id)
                .order_by(BookSection.section_idx)
                .all()
            )
            valid = [r[0] for r in rows if r[0]]
            if not valid:
                skipped += 1
                continue
            try:
                read_effect = run_async(generate_read_effect(
                    title=book.title or book.cnts_id,
                    author=book.personal_author or book.corporate_author or "",
                    section_summaries=valid,
                    doc_type=book.doc_type or "book",
                ))
                if read_effect:
                    extra = dict(book.extra or {})
                    extra["read_effect"] = read_effect
                    book.extra = extra
                    flag_modified(book, "extra")
                    db.commit()
                    done += 1
                else:
                    skipped += 1
            except Exception as e:
                db.rollback()
                log.warning(f"[{book.cnts_id}] read_effect 백필 실패: {e}")
                failed += 1
    finally:
        db.close()

    log.info(f"backfill_read_effect 완료: done={done}, skipped={skipped}, failed={failed}")
    return {"done": done, "skipped": skipped, "failed": failed}


# ── 5. 배치 잡 레이어 태스크 (workers/job_runtime.py) ─────
# 단계 태스크·디스패처는 job_runtime 모듈에 정의하고 여기서 로드한다
import workers.job_runtime  # noqa: E402, F401
