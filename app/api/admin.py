"""
api/admin.py — 관리자 API (데이터 현황 조회)
"""
import logging
from fastapi import APIRouter, Depends
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