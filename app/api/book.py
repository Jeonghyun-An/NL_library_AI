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
from fastapi.responses import StreamingResponse
from schemas.book import (
    BookOut,
    SearchRequest,
    ChunkSearchResponse,
    BookSearchResponse,
    BatchIngestRequest,
    IngestionRequest,
    TaskStatusOut,
    ReasonStreamRequest,
    BookChatRequest,
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
                "result": json.dumps(result.model_dump(), default=str),
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


# ── 인덱싱 취소 ──────────────────────────────────────────
@router.post("/ingest/{task_id}/cancel")
async def cancel_ingest(task_id: str, db: AsyncSession = Depends(get_db)):
    """진행 중인 인덱싱 태스크 취소.

    Celery revoke(terminate=True) 로 SIGTERM 전송 + Redis 락 강제 해제 +
    library_catalog.ingest_state 를 canceled 로 표시.
    """
    from workers.celery_app import celery_app
    from core.lock import force_release

    row = (await db.execute(
        text(
            "SELECT cnts_id FROM library_catalog "
            "WHERE ingest_task_id = :tid LIMIT 1"
        ),
        {"tid": task_id},
    )).first()
    cnts_id = row[0] if row else None

    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

    released = False
    if cnts_id:
        released = force_release(cnts_id)
        await db.execute(
            text(
                "UPDATE library_catalog SET "
                "  ingest_state = 'canceled', "
                "  ingest_finished_at = NOW(), "
                "  ingest_error = '사용자 취소' "
                "WHERE cnts_id = :cid"
            ),
            {"cid": cnts_id},
        )
        await db.commit()

    return {
        "task_id": task_id,
        "canceled": True,
        "book_id": cnts_id,
        "lock_released": released,
    }


# ── 인덱싱 재시도 ────────────────────────────────────────
@router.post("/{cnts_id}/retry")
async def retry_ingest(cnts_id: str, db: AsyncSession = Depends(get_db)):
    """실패/취소된 인덱싱을 재시도.

    library_catalog.ingest_source_key 가 저장돼 있으면 그 MinIO key 로 재디스패치.
    없으면 `originals/{cnts_id}/` 하위 첫 파일을 사용한다.
    이미 처리 중(processing) 상태면 거부한다.
    """
    row = (await db.execute(
        text(
            "SELECT ingest_state, ingest_source_key FROM library_catalog "
            "WHERE cnts_id = :cid"
        ),
        {"cid": cnts_id},
    )).first()
    if not row:
        raise HTTPException(404, f"도서 없음: {cnts_id}")

    state, source_key = row[0], row[1]
    if state == "processing":
        raise HTTPException(409, "이미 처리 중입니다. 먼저 취소(cancel)하세요.")

    # source_key 가 없으면 MinIO 에서 탐색
    if not source_key:
        from minio import Minio
        client = Minio(
            cfg.MINIO_ENDPOINT,
            access_key=cfg.MINIO_ACCESS_KEY,
            secret_key=cfg.MINIO_SECRET_KEY,
            secure=cfg.MINIO_SECURE,
        )
        objects = list(client.list_objects(
            cfg.MINIO_BUCKET, prefix=f"originals/{cnts_id}/", recursive=True
        ))
        if not objects:
            raise HTTPException(404, f"원본 PDF 없음: {cnts_id}")
        source_key = objects[0].object_name

    from workers.tasks import process_from_minio
    task = process_from_minio.delay(cnts_id, source_key)

    return {
        "book_id": cnts_id,
        "task_id": task.id,
        "source_key": source_key,
        "previous_state": state,
    }


# ── 인덱싱 상태 조회 ─────────────────────────────────────
@router.get("/{cnts_id}/ingest-status")
async def get_ingest_status(cnts_id: str, db: AsyncSession = Depends(get_db)):
    """UI 폴링용 — 현재 인덱싱 상태와 메타를 한 번에 반환."""
    row = (await db.execute(
        text(
            "SELECT ingest_state, ingest_task_id, ingest_source_key, "
            "       ingest_started_at, ingest_finished_at, ingest_error, "
            "       is_embedded "
            "FROM library_catalog WHERE cnts_id = :cid"
        ),
        {"cid": cnts_id},
    )).first()
    if not row:
        raise HTTPException(404, f"도서 없음: {cnts_id}")
    return {
        "book_id": cnts_id,
        "state": row[0],
        "task_id": row[1],
        "source_key": row[2],
        "started_at": row[3].isoformat() if row[3] else None,
        "finished_at": row[4].isoformat() if row[4] else None,
        "error": row[5],
        "is_embedded": row[6],
    }


# ── 표지 (FLUX 자동생성 → 없으면 PDF 1p 폴백) ──────────────
@router.get("/{cnts_id}/thumbnail")
async def get_book_thumbnail(cnts_id: str, db: AsyncSession = Depends(get_db)):
    """
    책 표지 반환 우선순위:
      ① FLUX 자동 생성 표지 (book.cover_image_key)
      ② 캐시된 PDF 1페이지 썸네일
      ③ 원본 PDF 1페이지 즉석 렌더 (+ MinIO 캐싱)
    """
    from minio import Minio
    from minio.error import S3Error
    import fitz  # PyMuPDF

    client = Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )

    # ① FLUX 자동 생성 표지 우선
    try:
        row = (await db.execute(
            text("SELECT cover_image_key FROM library_catalog WHERE cnts_id = :id"),
            {"id": cnts_id},
        )).first()
        if row and row[0]:
            try:
                obj = client.get_object(cfg.MINIO_BUCKET, row[0])
                data = obj.read()
                obj.close()
                return Response(
                    content=data,
                    media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"},
                )
            except S3Error:
                log.warning(f"[{cnts_id}] cover_image_key 있으나 MinIO 객체 없음: {row[0]}")
    except Exception as e:
        log.warning(f"[{cnts_id}] cover_image_key 조회 실패: {e}")

    thumbnail_key = f"thumbnails/{cnts_id}.jpg"

    # ② 캐시 확인 (이미 생성된 PDF 썸네일)
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

# ── PDF 원문 스트리밍 ──────────────────────────────────────
@router.get("/{cnts_id}/pdf")
async def get_book_pdf(cnts_id: str):
    """MinIO originals/{cnts_id}/ 하위 PDF를 스트리밍 반환"""
    from minio import Minio
    from minio.error import S3Error

    client = Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )
    try:
        objects = list(client.list_objects(
            cfg.MINIO_BUCKET, prefix=f"originals/{cnts_id}/", recursive=True
        ))
        if not objects:
            raise HTTPException(404, detail="PDF 없음")
        obj_name = objects[0].object_name
        obj_stat = client.stat_object(cfg.MINIO_BUCKET, obj_name)
        obj = client.get_object(cfg.MINIO_BUCKET, obj_name)
    except S3Error as e:
        raise HTTPException(404, detail=f"PDF 없음: {e}")

    def _stream():
        try:
            while True:
                chunk = obj.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            obj.close()

    return StreamingResponse(
        _stream(),
        media_type="application/pdf",
        headers={
            "Content-Length": str(obj_stat.size),
            "Content-Disposition": f'inline; filename="{cnts_id}.pdf"',
            "Cache-Control": "private, max-age=3600",
        },
    )


# ── PDF 추출 비교 (fitz vs VLM vs OpenDataLoader) ────────
@router.post("/compare/extract")
async def compare_pdf_extraction(
    file: UploadFile = File(...),
    max_pages: int = 10,
):
    """PDF 업로드 → fitz / VLM(Gemma) / OpenDataLoader 세 가지로 추출 후 비교 반환.

    max_pages: 비교할 최대 페이지 수 (기본 10)
    """
    import asyncio
    import time
    import os
    from services.ingestion.extractor import (
        extract_text_fitz_all,
        extract_text_vlm_all,
        extract_text_opendataloader,
    )

    content = await file.read()
    book_id = f"cmp_{os.path.splitext(file.filename or 'temp')[0]}"

    # fitz는 동기 함수 — executor로 실행해 이벤트 루프 차단 방지
    loop = asyncio.get_event_loop()
    t_fitz = time.perf_counter()
    fitz_result = await loop.run_in_executor(
        None, lambda: extract_text_fitz_all(None, book_id, file_bytes=content, max_pages=max_pages)
    )
    fitz_elapsed = round(time.perf_counter() - t_fitz, 2)

    t_vlm = time.perf_counter()
    vlm_result = await extract_text_vlm_all(None, book_id, file_bytes=content, max_pages=max_pages)
    vlm_elapsed = round(time.perf_counter() - t_vlm, 2)

    t_odl = time.perf_counter()
    odl_result = await extract_text_opendataloader(None, book_id, file_bytes=content, max_pages=max_pages)
    odl_elapsed = round(time.perf_counter() - t_odl, 2)

    fitz_pages = {p.page_num: p for p in fitz_result.pages}
    vlm_pages  = {p.page_num: p for p in vlm_result.pages}
    odl_pages  = {p.page_num: p for p in odl_result.pages}
    all_page_nums = sorted(set(fitz_pages) | set(vlm_pages) | set(odl_pages))

    pages = []
    for pg in all_page_nums:
        fp = fitz_pages.get(pg)
        vp = vlm_pages.get(pg)
        op = odl_pages.get(pg)
        pages.append({
            "page": pg,
            "fitz":          {"chars": len(fp.text) if fp else 0, "confidence": fp.confidence if fp else None, "text": fp.text if fp else ""},
            "vlm":           {"chars": len(vp.text) if vp else 0, "confidence": vp.confidence if vp else None, "text": vp.text if vp else ""},
            "opendataloader":{"chars": len(op.text) if op else 0, "confidence": op.confidence if op else None, "text": op.text if op else ""},
        })

    def _summary(result, elapsed):
        return {
            "total_pages": result.total_pages,
            "processed_pages": len(result.pages),
            "total_chars": sum(len(p.text) for p in result.pages),
            "elapsed_sec": elapsed,
            "errors": result.errors,
        }

    return {
        "filename": file.filename,
        "max_pages": max_pages,
        "fitz":           _summary(fitz_result, fitz_elapsed),
        "vlm":            _summary(vlm_result,  vlm_elapsed),
        "opendataloader": _summary(odl_result,  odl_elapsed),
        "pages": pages,
    }


# ── 추천 이유 스트리밍 ───────────────────────────────────
@router.post("/reason/stream")
async def stream_reason(
    req: ReasonStreamRequest,
    db: AsyncSession = Depends(get_db),
):
    """도서 추천 이유를 SSE로 스트리밍"""
    from services.search.pipeline import stream_book_reason

    # DB 조회를 핸들러에서 미리 끝내고 book 객체만 넘긴다.
    # StreamingResponse 제너레이터에 db 세션을 직접 넘기면
    # 핸들러 리턴 후 세션이 닫혀 GC 경고가 발생한다.
    repo = BookRepository(db)
    book = await repo.get_by_cnts_id(req.book_id)

    return StreamingResponse(
        stream_book_reason(req.query, req.book_id, req.chunk_texts, req.rewritten_query, book=book),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── 도서 심층 대화 ───────────────────────────────────────
@router.post("/chat/{cnts_id}")
async def chat_with_book(
    cnts_id: str,
    req: BookChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """특정 도서와의 RAG 기반 대화 (SSE 스트리밍)"""
    from services.chat.book_chat import stream_book_chat

    repo = BookRepository(db)
    book = await repo.get_by_cnts_id(cnts_id)

    return StreamingResponse(
        stream_book_chat(cnts_id, req.message, [m.model_dump() for m in req.history], book=book),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
            "id": str(r.id),
            "query": r.query,
            "result": json.loads(r.result) if r.result else None,
            "timestamp": r.created_at.isoformat() + "Z",
        }
        for r in items
    ]