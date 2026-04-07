import uuid
import asyncio
import logging
from celery import group
from workers.celery_app import celery_app
from services.ingestion.summarizer import summarize_book
from services.ingestion.embedder import embed_texts
from services.ingestion.indexer import upsert_embeddings
from db.postgres import SyncSessionLocal
from models.book import Book

log = logging.getLogger(__name__)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(bind=True, queue="ingestion", max_retries=3, name="tasks.process_single_book")
def process_single_book(self, nl_id: str, force: bool = False):
    with SyncSessionLocal() as db:
        book: Book = db.query(Book).filter(Book.nl_id == nl_id).first()

        if not book:
            log.warning(f"[{nl_id}] not found in DB")
            return {"nl_id": nl_id, "status": "not_found"}

        if book.is_embedded and not force:
            log.info(f"[{nl_id}] already embedded, skip")
            return {"nl_id": nl_id, "status": "skipped"}

        if not book.raw_text:
            log.warning(f"[{nl_id}] no raw_text")
            return {"nl_id": nl_id, "status": "no_text"}

        try:
            # 1. 요약
            log.info(f"[{nl_id}] summarizing...")
            book.summary = _run(summarize_book(
                title=book.title,
                author=book.author or "",
                raw_text=book.raw_text,
            ))

            # 2. 임베딩 (제목 + 주제어 + 요약 결합)
            embed_text = f"{book.title}. {book.subject or ''}. {book.summary}"
            log.info(f"[{nl_id}] embedding...")
            vecs = embed_texts([embed_text], is_query=False)

            # 3. Milvus 저장
            m_id = uuid.uuid4().hex[:20]
            upsert_embeddings([{
                "milvus_id": m_id,
                "book_id":   str(book.id),
                "nl_id":     book.nl_id,
                "title":     book.title,
                "subject":   book.subject or "",
                "embedding": vecs[0],
            }])

            # 4. PostgreSQL 상태 업데이트
            book.milvus_id   = m_id
            book.is_embedded = True
            db.commit()

            log.info(f"[{nl_id}] done")
            return {"nl_id": nl_id, "status": "success"}

        except Exception as exc:
            db.rollback()
            log.error(f"[{nl_id}] failed: {exc}")
            raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="tasks.ingest_books_batch")
def ingest_books_batch(nl_ids: list[str], force: bool = False):
    job = group(process_single_book.s(nl_id, force) for nl_id in nl_ids)
    return job.apply_async()