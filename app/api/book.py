import io
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from sqlalchemy import text
import json

from core.config import get_settings
from core.deps import get_db
from schemas.book import (
    BookOut,
    SearchRequest,
    ChunkSearchResponse,
    BookSearchResponse,
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
    session_id: str | None = Header(None, alias="x-session-id"),
    db: AsyncSession = Depends(get_db),
):
    # session_id 없으면 생성
    if not session_id or session_id == "null":
        session_id = str(uuid4())

    result = await search(
        req.query,
        mode=req.mode,
        top_k=req.top_k,
        use_rewrite=req.use_rewrite,
        use_rerank=req.use_rerank,
        db=db,
    )

    if isinstance(result, BookSearchResponse):
        repo = BookRepository(db)
        for bg in result.books:
            book = await repo.get_by_cnts_id(bg.book_id)
            if book:
                bg.book_info = BookOut.model_validate(book)

    # 히스토리 저장
    try:
        await db.execute(
            text("""
                INSERT INTO search_history (id, session_id, query, mode, result)
                VALUES (:id, :sid, :query, :mode, :result)
            """),
            {
                "id": str(uuid4()),
                "sid": session_id,
                "query": req.query,
                "mode": req.mode,
                "result": json.loads(json.dumps(result.model_dump(), default=str)),
            },
        )
        await db.commit()
    except Exception as e:
        log.warning(f"히스토리 저장 실패: {e}")

    return result


# ── 파일 업로드 + 수집 ──────────────────────────────────
@router.post("/ingest/upload")
async def upload_and_ingest(
    file: UploadFile = File(...),
):
    import os
    filename = file.filename or "unknown.pdf"
    book_id = os.path.splitext(filename)[0]
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


@router.post("/ingest/upload/batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
):
    """여러 PDF 일괄 업로드 → 파일명에서 cnts_id 추출 → 수집"""
    from minio import Minio
    import os

    client = Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )

    from workers.tasks import process_from_minio
    tasks = []

    for file in files:
        filename = file.filename or "unknown.pdf"
        book_id = os.path.splitext(filename)[0]

        content = await file.read()
        minio_key = f"originals/{book_id}/{filename}"
        client.put_object(
            cfg.MINIO_BUCKET,
            minio_key,
            io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/pdf",
        )

        task = process_from_minio.delay(book_id, minio_key)
        tasks.append({"book_id": book_id, "task_id": task.id})

    return {"dispatched": len(tasks), "tasks": tasks}


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
async def load_catalog(
    file: UploadFile = File(...),
):
    """엑셀 업로드 → 메타데이터 적재"""
    import os

    # 공유 볼륨에 저장 (FastAPI ↔ Celery 모두 접근 가능)
    os.makedirs("/app/data/uploads", exist_ok=True)
    save_path = f"/app/data/uploads/{file.filename}"

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    from workers.tasks import load_catalog_xlsx
    task = load_catalog_xlsx.delay(save_path)
    return {"task_id": task.id, "filename": file.filename}

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


# ── PDF 첫 페이지 썸네일 ─────────────────────────────────
@router.get("/{cnts_id}/thumbnail")
async def get_book_thumbnail(cnts_id: str):
    """PDF 1페이지를 JPEG로 렌더링해 반환. MinIO에 캐싱."""
    from minio import Minio
    from minio.error import S3Error
    import fitz  # PyMuPDF

    client = Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )
    thumbnail_key = f"thumbnails/{cnts_id}.jpg"

    # ① 캐시 확인 (이미 생성된 썸네일)
    try:
        obj = client.get_object(cfg.MINIO_BUCKET, thumbnail_key)
        data = obj.read()
        obj.close()
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except S3Error:
        pass

    # ② PDF 파일 탐색 (originals/{cnts_id}/ 하위 첫 번째 파일)
    try:
        objects = list(client.list_objects(
            cfg.MINIO_BUCKET, prefix=f"originals/{cnts_id}/", recursive=True
        ))
        if not objects:
            raise HTTPException(404, f"PDF 없음: {cnts_id}")
        pdf_obj = client.get_object(cfg.MINIO_BUCKET, objects[0].object_name)
        pdf_bytes = pdf_obj.read()
        pdf_obj.close()
    except S3Error:
        raise HTTPException(404, f"PDF 없음: {cnts_id}")

    # ③ 첫 페이지 렌더링 (0.6× → A4 기준 약 357×505px)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(0.6, 0.6))
    img_bytes = pix.tobytes("jpeg")
    doc.close()

    # ④ MinIO에 썸네일 캐싱
    try:
        client.put_object(
            cfg.MINIO_BUCKET,
            thumbnail_key,
            io.BytesIO(img_bytes),
            length=len(img_bytes),
            content_type="image/jpeg",
        )
    except Exception as e:
        log.warning(f"[{cnts_id}] 썸네일 캐싱 실패: {e}")

    return Response(
        content=img_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ── 도서 조회 ────────────────────────────────────────────
@router.get("/{cnts_id}", response_model=BookOut)
async def get_book(cnts_id: str, db: AsyncSession = Depends(get_db)):
    repo = BookRepository(db)
    book = await repo.get_by_cnts_id(cnts_id)
    if not book:
        raise HTTPException(404, f"도서 없음: {cnts_id}")
    return BookOut.model_validate(book)

@router.get("/history/{session_id}")
async def get_history(session_id: str, db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        text("""
            SELECT id, query, result, created_at
            FROM search_history
            WHERE session_id = :sid
            ORDER BY created_at DESC
            LIMIT 50
        """),
        {"sid": session_id},
    )

    items = rows.fetchall()

    return [
        {
            "id": r.id,
            "query": r.query,
            "result": r.result,
            "timestamp": r.created_at.isoformat(),
        }
        for r in items
    ]