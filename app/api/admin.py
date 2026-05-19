"""
api/admin.py — 관리자 API (데이터 현황 조회)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.config import get_settings
from core.deps import get_db
from models.book import Book
from models.section import BookSection

log = logging.getLogger(__name__)
cfg = get_settings()
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── 전체 현황 대시보드 ───────────────────────────────────
@router.get("/status")
async def get_status(db: AsyncSession = Depends(get_db)):
    """전체 시스템 현황"""
    # PostgreSQL 통계
    total_books = (await db.execute(select(func.count()).select_from(Book))).scalar() or 0
    embedded_books = (await db.execute(
        select(func.count()).select_from(Book).where(Book.is_embedded == True)
    )).scalar() or 0
    total_sections = (await db.execute(select(func.count()).select_from(BookSection))).scalar() or 0

    # Milvus 통계
    milvus_count = 0
    try:
        from pymilvus import connections, Collection, utility
        if not connections.has_connection("default"):
            connections.connect(host=cfg.MILVUS_HOST, port=cfg.MILVUS_PORT)
        if utility.has_collection(cfg.MILVUS_COLLECTION):
            col = Collection(cfg.MILVUS_COLLECTION)
            col.flush()
            milvus_count = col.num_entities
    except Exception as e:
        log.warning(f"Milvus 조회 실패: {e}")

    # MinIO 통계
    minio_count = 0
    try:
        from minio import Minio
        client = Minio(
            cfg.MINIO_ENDPOINT,
            access_key=cfg.MINIO_ACCESS_KEY,
            secret_key=cfg.MINIO_SECRET_KEY,
            secure=cfg.MINIO_SECURE,
        )
        objects = client.list_objects(cfg.MINIO_BUCKET, prefix="originals/", recursive=True)
        minio_count = sum(1 for _ in objects)
    except Exception as e:
        log.warning(f"MinIO 조회 실패: {e}")

    return {
        "books": {
            "total": total_books,
            "embedded": embedded_books,
            "not_embedded": total_books - embedded_books,
        },
        "sections": total_sections,
        "chunks_in_milvus": milvus_count,
        "files_in_minio": minio_count,
    }


# ── 도서 목록 ────────────────────────────────────────────
@router.get("/books")
async def list_books(
    page: int = 1,
    size: int = 20,
    embedded_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """도서 목록 (페이지네이션)"""
    stmt = select(Book).order_by(Book.created_at.desc())
    if embedded_only:
        stmt = stmt.where(Book.is_embedded == True)

    # 전체 건수
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 페이지네이션
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    books = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "cnts_id": b.cnts_id,
                "title": b.title,
                "personal_author": b.personal_author,
                "publisher": b.publisher,
                "is_embedded": b.is_embedded,
                "chunk_count": b.chunk_count,
                "full_text_length": b.full_text_length,
                "created_at": str(b.created_at) if b.created_at else None,
            }
            for b in books
        ],
    }


# ── 특정 도서의 섹션 목록 ────────────────────────────────
@router.get("/books/{cnts_id}/sections")
async def list_sections(cnts_id: str, db: AsyncSession = Depends(get_db)):
    """특정 도서의 섹션(원문) 목록"""
    stmt = (
        select(BookSection)
        .where(BookSection.book_id == cnts_id)
        .order_by(BookSection.section_idx)
    )
    result = await db.execute(stmt)
    sections = result.scalars().all()

    return {
        "book_id": cnts_id,
        "total_sections": len(sections),
        "sections": [
            {
                "section_idx": s.section_idx,
                "page_start": s.page_start,
                "page_end": s.page_end,
                "token_count": s.token_count,
                "text_preview": s.full_text[:200] + "..." if len(s.full_text) > 200 else s.full_text,
            }
            for s in sections
        ],
    }


# ── 특정 도서의 청크 목록 (Milvus) ───────────────────────
@router.get("/books/{cnts_id}/chunks")
async def list_chunks(cnts_id: str):
    """특정 도서의 Milvus 청크 목록"""
    try:
        from pymilvus import connections, Collection, utility
        if not connections.has_connection("default"):
            connections.connect(host=cfg.MILVUS_HOST, port=cfg.MILVUS_PORT)
        if not utility.has_collection(cfg.MILVUS_COLLECTION):
            return {"book_id": cnts_id, "total_chunks": 0, "chunks": []}

        col = Collection(cfg.MILVUS_COLLECTION)
        col.load()
        results = col.query(
            expr=f'book_id == "{cnts_id}"',
            output_fields=["chunk_id", "chunk_idx", "section_idx", "text", "page_start", "page_end"],
            limit=1000,
        )

        return {
            "book_id": cnts_id,
            "total_chunks": len(results),
            "chunks": [
                {
                    "chunk_id": r["chunk_id"],
                    "chunk_idx": r["chunk_idx"],
                    "section_idx": r.get("section_idx", 0),
                    "page_start": r["page_start"],
                    "page_end": r["page_end"],
                    "text_preview": r["text"][:150] + "..." if len(r["text"]) > 150 else r["text"],
                }
                for r in sorted(results, key=lambda x: x["chunk_idx"])
            ],
        }
    except Exception as e:
        log.error(f"청크 조회 실패: {e}")
        return {"book_id": cnts_id, "error": str(e)}


# ── MinIO 파일 목록 ──────────────────────────────────────
@router.get("/minio/files")
async def list_minio_files(prefix: str = "originals/"):
    """MinIO 파일 목록"""
    try:
        from minio import Minio
        client = Minio(
            cfg.MINIO_ENDPOINT,
            access_key=cfg.MINIO_ACCESS_KEY,
            secret_key=cfg.MINIO_SECRET_KEY,
            secure=cfg.MINIO_SECURE,
        )

        objects = client.list_objects(cfg.MINIO_BUCKET, prefix=prefix, recursive=True)
        files = []
        for obj in objects:
            files.append({
                "key": obj.object_name,
                "size_mb": round(obj.size / (1024 * 1024), 2) if obj.size else 0,
                "last_modified": str(obj.last_modified) if obj.last_modified else None,
            })

        return {"bucket": cfg.MINIO_BUCKET, "prefix": prefix, "total": len(files), "files": files}
    except Exception as e:
        log.error(f"MinIO 조회 실패: {e}")
        return {"error": str(e)}


# ── Milvus 인덱싱된 도서 목록 ────────────────────────────
@router.get("/milvus/books")
async def list_milvus_books(
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Milvus에 인덱싱된 도서 목록 및 청크 수 조회."""
    from services.ingestion.indexer import ensure_collection
    from repositories.book import BookRepository

    try:
        col = ensure_collection()
        if col.num_entities == 0:
            return {"total": 0, "total_chunks": 0, "page": page, "size": size, "books": []}

        # book_id별 청크 수 집계 (메타 청크 chunk_idx=-1 제외)
        book_chunk_count: dict[str, int] = {}
        batch = 16384
        offset = 0
        while True:
            rows = col.query(
                expr="chunk_idx >= 0",
                output_fields=["book_id"],
                limit=batch,
                offset=offset,
            )
            if not rows:
                break
            for r in rows:
                bid = r["book_id"]
                book_chunk_count[bid] = book_chunk_count.get(bid, 0) + 1
            if len(rows) < batch:
                break
            offset += batch
    except Exception as e:
        log.error(f"Milvus 조회 실패: {e}")
        return {"error": str(e)}

    book_ids = sorted(book_chunk_count)
    total = len(book_ids)

    # 페이지네이션
    start = (page - 1) * size
    page_ids = book_ids[start : start + size]

    # PostgreSQL에서 제목 조회
    repo = BookRepository(db)
    books = []
    for bid in page_ids:
        title = None
        try:
            book = await repo.get_by_cnts_id(bid)
            if book:
                title = book.title
        except Exception:
            pass
        books.append({"book_id": bid, "title": title, "chunk_count": book_chunk_count[bid]})

    return {
        "total": total,
        "total_chunks": col.num_entities,
        "page": page,
        "size": size,
        "books": books,
    }


# ── 전체 재인덱싱 ────────────────────────────────────────
@router.post("/reindex-all")
async def reindex_all():
    """MinIO originals/ 하위 PDF를 모두 스캔해 재인덱싱 태스크 일괄 디스패치."""
    from minio import Minio
    from minio.error import S3Error
    from workers.tasks import process_from_minio

    try:
        client = Minio(
            cfg.MINIO_ENDPOINT,
            access_key=cfg.MINIO_ACCESS_KEY,
            secret_key=cfg.MINIO_SECRET_KEY,
            secure=cfg.MINIO_SECURE,
        )
        objects = client.list_objects(cfg.MINIO_BUCKET, prefix="originals/", recursive=True)
    except S3Error as e:
        log.error(f"MinIO 조회 실패: {e}")
        return {"error": str(e)}

    dispatched = []
    skipped = []
    for obj in objects:
        key = obj.object_name  # originals/{book_id}/{filename}.pdf
        if not key.lower().endswith(".pdf"):
            skipped.append(key)
            continue

        parts = key.split("/")
        # 구조: originals / book_id / filename.pdf  (최소 3토큰)
        if len(parts) < 3:
            skipped.append(key)
            continue

        book_id = parts[1]
        task = process_from_minio.delay(book_id, key)
        dispatched.append({"book_id": book_id, "minio_key": key, "task_id": task.id})
        log.info(f"재인덱싱 디스패치: {book_id} ({key})")

    return {
        "dispatched": len(dispatched),
        "skipped": len(skipped),
        "tasks": dispatched,
    }


# ── VLM 추출 결과 미리보기 ───────────────────────────────
@router.get("/books/{cnts_id}/extraction-preview")
async def extraction_preview(
    cnts_id: str,
    max_pages: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """MinIO에서 PDF를 받아 추출 파이프라인을 실행하고 페이지별 결과를 반환.

    method 필드로 어느 페이지가 VLM으로 처리됐는지 확인 가능.
    max_pages: 처음 N 페이지만 추출 (기본 30).
    """
    from minio import Minio
    from minio.error import S3Error
    from services.ingestion.extractor import extract_text

    # source_key 조회
    result = await db.execute(
        select(Book.ingest_source_key).where(Book.cnts_id == cnts_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, f"도서 없음: {cnts_id}")
    source_key = row[0]

    if not source_key:
        raise HTTPException(404, f"MinIO 키 없음 (인덱싱 전 도서): {cnts_id}")

    # MinIO 다운로드
    try:
        client = Minio(
            cfg.MINIO_ENDPOINT,
            access_key=cfg.MINIO_ACCESS_KEY,
            secret_key=cfg.MINIO_SECRET_KEY,
            secure=cfg.MINIO_SECURE,
        )
        response = client.get_object(cfg.MINIO_BUCKET, source_key)
        pdf_bytes = response.read()
        response.close()
    except S3Error as e:
        raise HTTPException(500, f"MinIO 다운로드 실패: {e}")

    # 추출 실행
    try:
        extraction = await extract_text(
            file_path=None,
            book_id=cnts_id,
            file_bytes=pdf_bytes,
        )
    except Exception as e:
        raise HTTPException(500, f"추출 실패: {e}")

    pages = extraction.pages[:max_pages]
    vlm_pages = [p for p in pages if p.method == "vlm"]

    return {
        "book_id": cnts_id,
        "total_pages": extraction.total_pages,
        "returned_pages": len(pages),
        "vlm_count": len(vlm_pages),
        "odl_count": len([p for p in pages if p.method == "opendataloader"]),
        "pages": [
            {
                "page_num": p.page_num,
                "method": p.method,
                "char_count": len(p.text),
                "text": p.text,
            }
            for p in pages
        ],
    }