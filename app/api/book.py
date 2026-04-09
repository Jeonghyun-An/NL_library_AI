import io
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.deps import get_db
from schemas.book import (
    BookOut,
    SearchRequest,
    ChunkSearchResponse,
    BookSearchResponse,
    XlsxLoadRequest,
    BatchIngestRequest,
    IngestionRequest,
    TaskStatusOut,
)
from repositories.book import BookRepository
from services.search.pipeline import search

log = logging.getLogger(__name__)
cfg = get_settings()
router = APIRouter(prefix="/api/books", tags=["books"])


# ── 검색 ─────────────────────────────────────────────────
@router.post(
    "/search",
    response_model=ChunkSearchResponse | BookSearchResponse,
)
async def search_books(
    req: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await search(
        req.query,
        mode=req.mode,
        top_k=req.top_k,
        use_rewrite=req.use_rewrite,
        use_rerank=req.use_rerank,
    )

    if isinstance(result, BookSearchResponse):
        repo = BookRepository(db)
        for bg in result.books:
            book = await repo.get_by_cnts_id(bg.book_id)
            if book:
                bg.book_info = BookOut.model_validate(book)

    return result


# ── 파일 업로드 + 수집 ──────────────────────────────────
@router.post("/ingest/upload")
async def upload_and_ingest(
    book_id: str,
    file: UploadFile = File(...),
):
    from minio import Minio

    client = Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )

    content = await file.read()
    minio_key = f"originals/{book_id}/{file.filename}"
    client.put_object(
        cfg.MINIO_BUCKET,
        minio_key,
        io.BytesIO(content),
        length=len(content),
        content_type=file.content_type or "application/pdf",
    )

    from workers.tasks import process_from_minio
    task = process_from_minio.delay(book_id, minio_key)

    return {"task_id": task.id, "book_id": book_id, "minio_key": minio_key}


@router.post("/ingest/batch")
async def ingest_batch(req: BatchIngestRequest):
    from workers.tasks import process_book_file, process_from_minio

    tasks = []
    for item in req.files:
        if item.minio_key:
            t = process_from_minio.delay(item.book_id, item.minio_key)
        elif item.file_path:
            t = process_book_file.delay(item.book_id, item.file_path)
        else:
            continue
        tasks.append({"book_id": item.book_id, "task_id": t.id})

    return {"dispatched": len(tasks), "tasks": tasks}


# ── 메타데이터 수집 (기존) ───────────────────────────────
@router.post("/catalog/load")
async def load_catalog(req: XlsxLoadRequest):
    from workers.tasks import load_catalog_xlsx
    task = load_catalog_xlsx.delay(req.xlsx_path)
    return {"task_id": task.id}


@router.post("/ingest")
async def ingest_books(req: IngestionRequest):
    from workers.tasks import ingest_books_batch
    task = ingest_books_batch.delay(req.cnts_ids, req.force_re_summarize)
    return {"task_id": task.id, "total": len(req.cnts_ids)}


# ── 태스크 상태 ──────────────────────────────────────────
@router.get("/ingest/{task_id}", response_model=TaskStatusOut)
async def get_task_status(task_id: str):
    from workers.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    return TaskStatusOut(
        task_id=task_id,
        status=result.status,
        result=result.result if result.ready() else None,
    )


# ── 도서 조회 ────────────────────────────────────────────
@router.get("/{cnts_id}", response_model=BookOut)
async def get_book(cnts_id: str, db: AsyncSession = Depends(get_db)):
    repo = BookRepository(db)
    book = await repo.get_by_cnts_id(cnts_id)
    if not book:
        raise HTTPException(404, f"도서 없음: {cnts_id}")
    return BookOut.model_validate(book)