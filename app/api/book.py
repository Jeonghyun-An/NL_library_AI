import io
import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4
from sqlalchemy import text
import json

from core.config import get_settings
from core.deps import get_db
from core.errors import broker_outage_as_503, search_outage_as_503, storage_outage_as_503
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
    CurationRequest,
    CurationItem,
    CurationResponse,
)
from repositories.book import BookRepository
from services.search.pipeline import best_chunk_score, is_safe_book_id, search, search_related_books
from services.search.title_scorer import apply_title_scores

log = logging.getLogger(__name__)
cfg = get_settings()
router = APIRouter(prefix="/api/books", tags=["books"])


def _history_session_id(raw: str | None) -> str | None:
    """옛 검색 기록(search_history)의 세션 id — uuid 로 읽히면 그 문자열, 아니면 None."""
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except ValueError:
        return None


def _resolve_original_key(client, cnts_id: str) -> str | None:
    """원본 PDF의 MinIO 키 해석 — 폴더형(originals/{id}/) 우선, 없으면 평탄형(originals/{id}.pdf).

    대량 적재는 `mc mirror`로 평탄 키로 올리므로 두 레이아웃을 모두 지원한다.
    객체가 없을 때(S3Error)만 None 이다 — MinIO 연결 장애는 그대로 올려 호출자가 503(storage_unavailable)으로 낸다.
    전에는 모든 예외를 '없음'으로 삼켜 저장소가 꺼져도 404 'PDF 없음'이 됐다.
    """
    from minio.error import S3Error

    objects = list(client.list_objects(
        cfg.MINIO_BUCKET, prefix=f"originals/{cnts_id}/", recursive=True
    ))
    if objects:
        return objects[0].object_name
    flat_key = f"originals/{cnts_id}.pdf"
    try:
        client.stat_object(cfg.MINIO_BUCKET, flat_key)
        return flat_key
    except S3Error:
        return None


def _minio_client():
    from minio import Minio

    return Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )


def _read_object(client, key: str) -> bytes | None:
    """MinIO 객체를 통째로 읽는다. 객체가 없으면(S3Error) None, 연결 장애는 그대로 올린다."""
    from minio.error import S3Error

    try:
        obj = client.get_object(cfg.MINIO_BUCKET, key)
    except S3Error:
        return None
    try:
        return obj.read()
    finally:
        obj.close()
        obj.release_conn()


def _render_cover(pdf_bytes: bytes) -> bytes:
    """원본 PDF 첫 쪽을 JPEG 로 그린다(0.6× → A4 기준 약 357×505px)."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(0.6, 0.6))
        return pix.tobytes("jpeg")
    finally:
        doc.close()


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
    # 기록의 세션 id — search_history.session_id 는 UUID 칼럼이다. 없거나 uuid 가 아니면('null'·임의 글자) 새로 만든다
    session_id = _history_session_id(session_id) or str(uuid4())

    # Milvus·임베딩 연결/조회 장애는 503(search_unavailable) — 화면이 '잠시 뒤 다시'로 안내한다. 코드 버그는 500 그대로
    with search_outage_as_503("소장자료 검색"):
        result = await search(
            req.query,
            mode=req.mode,
            top_k=req.top_k,
            use_rewrite=req.use_rewrite,
            use_rerank=req.use_rerank,
            doc_scope="book",   # 논문 제외, 도서만 검색
            # 재작성이 제목만 넣은 질의를 주제어로 바꿔('구운몽' → '요몽, 이상향…') 그 책을 놓치던 것 — 원래 질의로도 찾는다
            include_original=True,
            db=db,
        )

        # 도서가 0권이면 날짜 조건(LLM 이 질의에서 뽑은 발행 연도)만 빼고 도서 안에서 다시 찾는다. 예전에는 doc_scope 를
        # 풀었다(doc_type 스칼라가 없던 옛 인덱스 대비) — 지금은 doc_type 이 컬렉션 필수 필드이고 빈 값도 도서 조건을
        # 통과해 그 대비는 할 일이 없는데, 날짜 조건이 도서를 다 걸러 낸 질의('올리버 트위스트' → 2026년)에서 그해 논문을
        # 소장자료 결과로 보였다(운영 2026-10-23, research/book-search-filter-recall)
        if isinstance(result, BookSearchResponse) and not result.books:
            log.warning("도서 필터 검색 0건 — 날짜 조건 없이 도서 안에서 재시도")
            result = await search(
                req.query,
                mode=req.mode,
                top_k=req.top_k,
                use_rewrite=req.use_rewrite,
                use_rerank=req.use_rerank,
                doc_scope="book",
                use_metadata_filter=False,
                include_original=True,
                db=db,
            )

    if isinstance(result, BookSearchResponse):
        # 서지는 한 번에 읽는다 — 원래 질의 갈래까지 합치면 후보가 40~50권이라 책마다 부르면 그만큼 순차 쿼리가 는다
        book_map = await BookRepository(db).get_by_cnts_ids([bg.book_id for bg in result.books])
        for bg in result.books:
            book = book_map.get(bg.book_id)
            if book:
                bg.book_info = BookOut.model_validate(book)
        # 제목 일치율 반영: 연관도 = max(제목, 내용), 재정렬 포함
        apply_title_scores(result.books, req.query, result.rewritten_query)

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
        # 실패한 트랜잭션을 그대로 두면 get_db 의 commit 이 다시 터지고 연결이 'idle in transaction' 으로 남을 수 있다
        await db.rollback()
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
    client = _minio_client()

    content = await file.read()
    minio_key = f"originals/{book_id}/{file.filename}"
    with storage_outage_as_503(f"업로드 {book_id}"):
        client.put_object(
            cfg.MINIO_BUCKET,
            minio_key,
            io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/pdf",
        )

    from workers.tasks import process_from_minio
    with broker_outage_as_503(f"업로드 적재 {book_id}"):
        task = process_from_minio.delay(book_id, minio_key)

    return {"task_id": task.id, "book_id": book_id, "minio_key": minio_key}


@router.post("/ingest/upload/batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
):
    """여러 PDF 일괄 업로드 → 파일명에서 cnts_id 추출 → 수집"""
    import os

    client = _minio_client()

    from workers.tasks import process_from_minio
    tasks = []

    for file in files:
        filename = file.filename or "unknown.pdf"
        book_id = os.path.splitext(filename)[0]

        content = await file.read()
        minio_key = f"originals/{book_id}/{filename}"
        # 중간에 끊기면 앞서 넣은 파일은 이미 올라가 적재 큐에 들어가 있다 — 가드가 로그에 남긴다
        with storage_outage_as_503(f"일괄 업로드 {book_id}(앞서 {len(tasks)}건 보냄)"):
            client.put_object(
                cfg.MINIO_BUCKET,
                minio_key,
                io.BytesIO(content),
                length=len(content),
                content_type=file.content_type or "application/pdf",
            )

        with broker_outage_as_503(f"일괄 업로드 적재 {book_id}(앞서 {len(tasks)}건 보냄)"):
            task = process_from_minio.delay(book_id, minio_key)
        tasks.append({"book_id": book_id, "task_id": task.id})

    return {"dispatched": len(tasks), "tasks": tasks}


@router.post("/ingest/batch")
async def ingest_batch(req: BatchIngestRequest):
    from workers.tasks import process_book_file, process_from_minio

    tasks = []
    for item in req.files:
        with broker_outage_as_503(f"일괄 적재 {item.book_id}(앞서 {len(tasks)}건 보냄)"):
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
    with broker_outage_as_503("서지 적재"):
        task = load_catalog_xlsx.delay(save_path)
    return {"task_id": task.id, "filename": file.filename}

@router.post("/ingest")
async def ingest_books(req: IngestionRequest):
    from workers.tasks import ingest_books_batch
    with broker_outage_as_503("도서 적재"):
        task = ingest_books_batch.delay(req.cnts_ids, req.force_re_summarize)
    return {"task_id": task.id, "total": len(req.cnts_ids)}


# ── 태스크 상태 ──────────────────────────────────────────
@router.get("/ingest/{task_id}", response_model=TaskStatusOut)
async def get_task_status(task_id: str):
    from workers.celery_app import celery_app
    # 결과 저장소도 브로커와 같은 Redis 다 — 닿지 못하면 같은 503
    with broker_outage_as_503(f"태스크 상태 {task_id}"):
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

    # 브로커에 닿지 못하면 취소 신호가 가지 않은 것이다 — 락·상태를 건드리지 않고 503 으로 돌려 다시 누르게 한다
    with broker_outage_as_503(f"적재 취소 {task_id}"):
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
        with storage_outage_as_503(f"적재 재시도 {cnts_id}"):
            source_key = _resolve_original_key(_minio_client(), cnts_id)
        if not source_key:
            raise HTTPException(404, f"원본 PDF 없음: {cnts_id}")

    from workers.tasks import process_from_minio
    with broker_outage_as_503(f"적재 재시도 {cnts_id}"):
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

    오류: 원문 저장소(MinIO) 연결 장애는 503(storage_unavailable), 원본이 없거나 깨져 표지를 그리지 못하면 404 — 화면의
    <img> 는 실패하면 대체 표지로 바꾼다. 전에는 깨진 원본(빈 파일·PDF 아님·쪽 없음)이 렌더 예외로 500 이 났다.
    """
    client = _minio_client()
    cache = {"Cache-Control": "public, max-age=86400"}

    # ① FLUX 자동 생성 표지 우선 — DB 조회 실패는 이 순서만 건너뛴다
    cover_key = None
    try:
        row = (await db.execute(
            text("SELECT cover_image_key FROM library_catalog WHERE cnts_id = :id"),
            {"id": cnts_id},
        )).first()
        cover_key = row[0] if row and row[0] else None
    except Exception as e:
        log.warning(f"[{cnts_id}] cover_image_key 조회 실패: {e}")

    thumbnail_key = f"thumbnails/{cnts_id}.jpg"

    with storage_outage_as_503(f"표지 {cnts_id}"):
        if cover_key:
            data = _read_object(client, cover_key)
            if data is not None:
                return Response(content=data, media_type="image/jpeg", headers=cache)
            log.warning(f"[{cnts_id}] cover_image_key 있으나 MinIO 객체 없음: {cover_key}")

        # ② 캐시 확인 (이미 생성된 PDF 썸네일)
        data = _read_object(client, thumbnail_key)
        if data is not None:
            return Response(content=data, media_type="image/jpeg", headers=cache)

        # ② PDF 파일 탐색 (폴더형 originals/{id}/ 우선, 평탄형 originals/{id}.pdf 폴백)
        obj_name = _resolve_original_key(client, cnts_id)
        pdf_bytes = _read_object(client, obj_name) if obj_name else None
        if pdf_bytes is None:
            raise HTTPException(404, f"PDF 없음: {cnts_id}")

    # ③ 첫 페이지 렌더링 — 깨진 원본은 PyMuPDF 가 여러 꼴로 실패한다(빈 파일 EmptyFileError, PDF 아님
    # FzErrorFormat, 쪽 없음 IndexError — 운영 이미지 PyMuPDF 1.24 에서 확인). 어느 것이든 표지를 그릴 수 없다는 뜻이다
    try:
        img_bytes = _render_cover(pdf_bytes)
    except Exception as e:
        log.warning("[%s] 표지 렌더 실패 — 원본 PDF 를 읽지 못했다(%s): %s: %s",
                    cnts_id, obj_name, type(e).__name__, e)
        raise HTTPException(404, f"표지를 그리지 못했습니다: {cnts_id}")

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

    return Response(content=img_bytes, media_type="image/jpeg", headers=cache)

# ── PDF 원문 스트리밍 ──────────────────────────────────────
@router.get("/{cnts_id}/pdf")
async def get_book_pdf(cnts_id: str):
    """MinIO originals/{cnts_id}/ 하위 PDF를 스트리밍 반환.

    원본이 없으면 404 'PDF 없음', 원문 저장소(MinIO) 연결 장애는 503(storage_unavailable). 보내기 시작한 뒤 끊기는
    것은 응답 머리가 이미 나가 고칠 수 없다(뷰어가 읽기 실패로 본다)."""
    from minio.error import S3Error

    client = _minio_client()
    with storage_outage_as_503(f"원문 {cnts_id}"):
        obj_name = _resolve_original_key(client, cnts_id)
        if not obj_name:
            raise HTTPException(404, detail="PDF 없음")
        try:
            obj_stat = client.stat_object(cfg.MINIO_BUCKET, obj_name)
            obj = client.get_object(cfg.MINIO_BUCKET, obj_name)
        except S3Error as e:
            # S3 오류 글(영문)은 화면에 내지 않는다 — 로그에만
            log.warning(f"[{cnts_id}] 원문 객체를 읽지 못함({obj_name}): {e}")
            raise HTTPException(404, detail="PDF 없음")

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
@router.post("/curate", response_model=CurationResponse)
async def curate_books_api(
    req: CurationRequest,
    db: AsyncSession = Depends(get_db),
):
    """1~3권 도서 큐레이션 리포트 생성"""
    from services.search.curator import curate_books as _curate_books

    if len(req.book_ids) > cfg.CURATION_TOP_K:
        raise HTTPException(400, f"최대 {cfg.CURATION_TOP_K}권까지 가능합니다")

    repo = BookRepository(db)
    book_map = await repo.get_by_cnts_ids(req.book_ids)

    if not book_map:
        raise HTTPException(404, "도서를 찾을 수 없습니다")

    ordered_books = [book_map[bid] for bid in req.book_ids if bid in book_map]
    score_map = dict(zip(req.book_ids, req.scores)) if req.scores else {}
    intent = req.rewritten_query or req.query

    result = await _curate_books(intent, req.query, ordered_books)

    items = [
        CurationItem(
            book_id=item["book_id"],
            book_info=book_map.get(item["book_id"]),
            reason=item.get("reason", ""),
            score=score_map.get(item["book_id"]),
        )
        for item in result.get("items", [])
    ]

    # ai_failed: LLM 사유 생성이 실패해 빈 사유로 채운 응답 — 화면이 빈 칸 대신 '사유를 만들지 못했다'를 보인다
    return CurationResponse(intro=result.get("intro", ""), items=items,
                            ai_failed=bool(result.get("ai_failed")))


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
    # uuid 가 아니면 Postgres 가 칼럼 비교에서 터져 500 이 됐다 — DB 를 부르기 전에 400
    if _history_session_id(session_id) is None:
        raise HTTPException(400, "세션 id 는 uuid 여야 한다")
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


# ── 관련 자료 추천 (소장자료 상세) ───────────────────────
# 맨 끝에 둔다 — 두 마디 경로라 위의 /ingest/{task_id}·/history/{session_id} 를 가리지 않게
@router.get("/{cnts_id}/related", response_model=BookSearchResponse)
async def get_related_books(
    cnts_id: str,
    top_k: int = 4,
    db: AsyncSession = Depends(get_db),
):
    """소장자료 상세 '관련 자료 추천' — 그 자료의 제목으로 찾은 다른 소장자료 최대 top_k 권(기본 4).

    자기 자신은 Milvus 조건식에서 미리 빼고 재작성·날짜 필터 LLM 은 부르지 않는다(search_related_books).
    연관도(제목·내용 종합, 검색 결과 카드와 같은 뜻)가 BOOK_RELATED_MIN_SCORE 아래인 책, 그리고 청크 수 로그 부스트로만
    하한을 넘은 긴 책으로 칸을 채우지 않는다(_clears_related_floor).
    카드는 서지·점수만 쓰므로 청크 본문은 빼고 보낸다. 사용자가 검색한 것이 아니므로 search_history 에 남기지 않는다.
    """
    if top_k < 1 or top_k > 10:
        raise HTTPException(400, "top_k는 1~10 사이여야 합니다.")
    if not is_safe_book_id(cnts_id):
        raise HTTPException(404, f"도서 없음: {cnts_id}")
    repo = BookRepository(db)
    source = await repo.get_by_cnts_id(cnts_id)
    if not source:
        raise HTTPException(404, f"도서 없음: {cnts_id}")
    title = (source.title or "").strip()
    if not title:
        return BookSearchResponse(query="", books=[], elapsed_ms=0.0)

    with search_outage_as_503(f"소장자료 관련 자료 {cnts_id}"):
        result = await search_related_books(title, cnts_id, fetch_top_k=cfg.BOOK_RELATED_FETCH_TOP_K)
    book_map = await repo.get_by_cnts_ids([bg.book_id for bg in result.books])
    for bg in result.books:
        bg.book_info = book_map.get(bg.book_id)
    apply_title_scores(result.books, title)

    picked = [bg for bg in result.books if bg.book_id != cnts_id and _clears_related_floor(bg)][:top_k]
    for bg in picked:
        bg.chunks = []
    result.books = picked
    return result


def _clears_related_floor(bg) -> bool:
    """관련 자료 하한 — 화면의 연관도(제목·내용 종합, 부스트 뒤)가 BOOK_RELATED_MIN_SCORE 이상이고, 그것이 청크 수
    로그 부스트만으로 올라선 것이 아니어야 한다. 부스트 1-(1-r)/(1+0.1·log2 n) 은 리랭크 0 인 책도 청크 20개면
    0.30 으로 올리고, 자기 청크가 빠진 창에서는 긴 남의 책이 청크를 더 받는다. 그래서 제목 일치만으로 하한을 넘거나
    (부스트와 상관없다), 가장 맞는 청크의 부스트 전 원점수가 BOOK_RELATED_MIN_RAW_SCORE 이상이어야 한다.
    청크 본문을 비우기 전에 부른다."""
    if bg.best_score < cfg.BOOK_RELATED_MIN_SCORE:
        return False
    if (bg.title_score or 0.0) >= cfg.BOOK_RELATED_MIN_SCORE:
        return True
    content = bg.content_score if bg.content_score is not None else bg.best_score
    return best_chunk_score(bg.chunks, default=content) >= cfg.BOOK_RELATED_MIN_RAW_SCORE