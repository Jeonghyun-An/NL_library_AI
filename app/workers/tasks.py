import logging
import asyncio

from workers.celery_app import celery_app
from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.book import Book

log = logging.getLogger(__name__)
cfg = get_settings()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── 1. 엑셀 메타데이터 로드 (기존 유지) ─────────────────
@celery_app.task(name="tasks.load_catalog_xlsx", queue="ingestion")
def load_catalog_xlsx(xlsx_path: str):
    from services.ingestion.xlsx_loader import load_xlsx

    records = load_xlsx(xlsx_path)
    db = SyncSessionLocal()
    try:
        created = 0
        for rec in records:
            exists = db.query(Book).filter_by(cnts_id=rec["cnts_id"]).first()
            if exists:
                continue
            book = Book(**rec)
            db.add(book)
            created += 1
        db.commit()
        log.info(f"메타데이터 {created}건 저장 완료")
        return {"created": created, "total": len(records)}
    except Exception as e:
        db.rollback()
        log.error(f"메타데이터 저장 실패: {e}")
        raise
    finally:
        db.close()


# ── 2. 단일 도서 원본 파일 처리 ──────────────────────────
@celery_app.task(
    name="tasks.process_book_file",
    queue="ingestion",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def process_book_file(self, book_id: str, file_path: str):
    from services.ingestion.extractor import extract_text
    from services.ingestion.chunker import semantic_chunk
    from services.ingestion.embedder import embed_texts
    from services.ingestion.indexer import index_chunks
    from services.ingestion.summarizer import summarize

    log.info(f"[{book_id}] 처리 시작: {file_path}")

    # ① 텍스트 추출
    extraction = _run_async(extract_text(file_path, book_id))
    if not extraction.pages:
        log.error(f"[{book_id}] 텍스트 추출 실패: {extraction.errors}")
        return {"book_id": book_id, "status": "failed", "errors": extraction.errors}

    full_text = extraction.full_text
    log.info(f"[{book_id}] 추출 완료: {extraction.stats}")

    # ② 시맨틱 청킹
    def _embed_fn(texts: list[str]):
        return embed_texts(texts)

    chunks = semantic_chunk(full_text, _embed_fn)
    log.info(f"[{book_id}] 청킹 완료: {len(chunks)}개")

    # 페이지 정보 매핑
    page_acc = 0
    for chunk in chunks:
        ratio = page_acc / max(len(full_text), 1)
        chunk.page_start = int(ratio * extraction.total_pages)
        chunk.page_end = min(chunk.page_start + 1, extraction.total_pages - 1)
        page_acc += len(chunk.text)

    # ③ 청크별 임베딩
    chunk_texts = [c.text for c in chunks]
    embeddings = embed_texts(chunk_texts)
    log.info(f"[{book_id}] 임베딩 완료: {len(embeddings)}개")

    # ④ Milvus 저장
    idx_result = index_chunks(book_id, chunks, embeddings)
    log.info(f"[{book_id}] 인덱싱 완료: {idx_result.chunks_indexed}개")

    # ⑤ 요약 생성 → PostgreSQL 업데이트
    db = SyncSessionLocal()
    try:
        summary_input = full_text[:6000]
        summary = _run_async(summarize(summary_input))

        book = db.query(Book).filter_by(cnts_id=book_id).first()
        if book:
            book.summary = summary
            book.full_text_length = len(full_text)
            book.chunk_count = len(chunks)
            book.extraction_stats = str(extraction.stats)
            book.is_embedded = True
            db.commit()
            log.info(f"[{book_id}] DB 업데이트 완료")
    except Exception as e:
        db.rollback()
        log.warning(f"[{book_id}] 요약 저장 실패: {e}")
    finally:
        db.close()

    return {
        "book_id": book_id,
        "status": "completed",
        "extraction": extraction.stats,
        "chunks": len(chunks),
        "indexed": idx_result.chunks_indexed,
    }


# ── 3. 배치 처리 ────────────────────────────────────────
@celery_app.task(name="tasks.ingest_batch", queue="ingestion")
def ingest_batch(file_mappings: list[dict]):
    results = []
    for item in file_mappings:
        task = process_book_file.delay(item["book_id"], item["file_path"])
        results.append({"book_id": item["book_id"], "task_id": task.id})
    return {"dispatched": len(results), "tasks": results}


# ── 4. MinIO에서 파일 다운로드 후 처리 ───────────────────
@celery_app.task(name="tasks.process_from_minio", queue="ingestion")
def process_from_minio(book_id: str, minio_key: str):
    from minio import Minio
    import tempfile

    client = Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        client.fget_object(cfg.MINIO_BUCKET, minio_key, tmp.name)
        return process_book_file(book_id, tmp.name)