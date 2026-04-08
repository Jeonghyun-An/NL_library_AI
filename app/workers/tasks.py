import uuid
import asyncio
import logging
from celery import group
from workers.celery_app import celery_app
from services.ingestion.xlsx_loader import load_xlsx
from services.ingestion.summarizer import summarize_book
from services.ingestion.embedder import embed_texts
from services.ingestion.indexer import upsert_embeddings
from db.postgres import SyncSessionLocal
from models.book import Book

log = logging.getLogger(__name__)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── 1단계: CSV → DB 저장 ─────────────────────────────────────
@celery_app.task(name="tasks.load_catalog_xlsx")
def load_catalog_xlsx(xlsx_path: str):
    """
    엑셀 파싱 → DB 저장
    """
    records = load_xlsx(xlsx_path)

    saved_ids = []
    with SyncSessionLocal() as db:
        for rec in records:
            cnts_id = rec.get("cnts_id")
            if not cnts_id:
                continue

            existing = db.query(Book).filter(Book.cnts_id == cnts_id).first()
            if existing:
                log.info(f"[{cnts_id}] 이미 존재, skip")
                saved_ids.append(cnts_id)
                continue

            book = Book(**{k: v for k, v in rec.items() if hasattr(Book, k)})
            db.add(book)
            saved_ids.append(cnts_id)

        db.commit()

    log.info(f"DB 저장 완료: {len(saved_ids)}건")
    return saved_ids


# ── 2단계: 단일 도서 요약 → 임베딩 → Milvus ──────────────────
@celery_app.task(bind=True, max_retries=3, name="tasks.process_single_book")
def process_single_book(self, cnts_id: str, force: bool = False):
    with SyncSessionLocal() as db:
        book: Book = db.query(Book).filter(Book.cnts_id == cnts_id).first()

        if not book:
            log.warning(f"[{cnts_id}] DB에 없음")
            return {"cnts_id": cnts_id, "status": "not_found"}

        if book.is_embedded and not force:
            log.info(f"[{cnts_id}] 이미 임베딩됨, skip")
            return {"cnts_id": cnts_id, "status": "skipped"}

        # raw_text 없어도 메타데이터로 요약 생성 가능
        source_text = book.raw_text or _build_meta_text(book)

        try:
            # 1. 요약
            log.info(f"[{cnts_id}] 요약 중...")
            book.summary = _run(summarize_book(
                title=book.title,
                author=book.personal_author or book.corporate_author or "",
                raw_text=source_text,
            ))

            # 2. 임베딩 텍스트 구성 (제목 + 주제어 + KDC + 요약)
            embed_text = _build_embed_text(book)
            log.info(f"[{cnts_id}] 임베딩 중...")
            vecs = embed_texts([embed_text], is_query=False)

            # 3. Milvus 저장
            m_id = uuid.uuid4().hex[:20]
            upsert_embeddings([{
                "milvus_id": m_id,
                "book_id":   str(book.id),
                "cnts_id":   book.cnts_id,
                "title":     book.title,
                "subject":   book.subject or "",
                "embedding": vecs[0],
            }])

            # 4. PostgreSQL 업데이트
            book.milvus_id   = m_id
            book.is_embedded = True
            db.commit()

            log.info(f"[{cnts_id}] 완료")
            return {"cnts_id": cnts_id, "status": "success"}

        except Exception as exc:
            db.rollback()
            log.error(f"[{cnts_id}] 실패: {exc}")
            raise self.retry(exc=exc, countdown=30)


# ── 3단계: 배치 처리 ──────────────────────────────────────────
@celery_app.task(name="tasks.ingest_books_batch")
def ingest_books_batch(cnts_ids: list[str], force: bool = False):
    return group(process_single_book.s(cid, force) for cid in cnts_ids).apply_async()


# ── 헬퍼 ──────────────────────────────────────────────────────
def _build_meta_text(book: Book) -> str:
    """raw_text 없을 때 메타데이터로 텍스트 구성"""
    parts = [
        f"제목: {book.title}",
        f"저자: {book.personal_author or book.corporate_author or ''}",
        f"출판사: {book.publisher or ''}",
        f"주제어: {book.subject or ''}",
        f"KDC: {book.kdc or ''}",
        f"초록: {book.abstract or ''}",
        f"노트: {book.note or ''}",
    ]
    return "\n".join(p for p in parts if not p.endswith(": "))


def _build_embed_text(book: Book) -> str:
    """임베딩용 텍스트 구성 (제목 + 주제어 + KDC + 요약)"""
    parts = [
        book.title,
        book.subject or "",
        f"KDC {book.kdc}" if book.kdc else "",
        book.summary or "",
    ]
    return ". ".join(p for p in parts if p)