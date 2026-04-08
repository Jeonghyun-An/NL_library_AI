from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from repositories.book import BookRepository
from schemas.book import (
    BookCreate, BookOut,
    SearchRequest, SearchResponse,
    CatalogLoadRequest,
    IngestionRequest, IngestionStatus,
)
from services.search.pipeline import run_search
from workers.tasks import load_catalog_csv, ingest_books_batch
from workers.celery_app import celery_app

router = APIRouter(prefix="/api/books", tags=["books"])


# ── CRUD ─────────────────────────────────────────────────────
@router.post("/", response_model=BookOut, status_code=status.HTTP_201_CREATED)
async def create_book(payload: BookCreate, db: AsyncSession = Depends(get_db)):
    return await BookRepository(db).create(payload)


@router.get("/{cnts_id}", response_model=BookOut)
async def get_book(cnts_id: str, db: AsyncSession = Depends(get_db)):
    book = await BookRepository(db).get_by_cnts_id(cnts_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


# ── 의미 기반 검색 ────────────────────────────────────────────
@router.post("/search", response_model=SearchResponse)
async def search_books(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    """자연어 쿼리로 의미 기반 도서 검색. 예: '한강의 채식주의자와 비슷한 책'"""
    return await run_search(req, BookRepository(db))


# ── CSV 카탈로그 로드 → DB 저장 ───────────────────────────────
@router.post("/catalog/load", status_code=status.HTTP_202_ACCEPTED)
async def load_catalog(payload: CatalogLoadRequest):
    """CSV 파싱 → DB 저장 (MODS 엑셀 병합 선택)"""
    result = load_catalog_csv.delay(payload.csv_path, payload.mods_excel_path)
    return {"task_id": result.id, "status": "PENDING"}


# ── 임베딩 파이프라인 트리거 ──────────────────────────────────
@router.post("/ingest", response_model=IngestionStatus, status_code=status.HTTP_202_ACCEPTED)
async def ingest_books(payload: IngestionRequest):
    """cnts_id 목록 → 요약 · 임베딩 · 인덱싱 비동기 처리"""
    result = ingest_books_batch.delay(payload.cnts_ids, payload.force_re_summarize)
    return IngestionStatus(
        task_id=result.id,
        status="PENDING",
        total=len(payload.cnts_ids),
        done=0,
        failed=0,
    )


@router.get("/ingest/{task_id}", response_model=IngestionStatus)
async def get_ingest_status(task_id: str):
    res = celery_app.AsyncResult(task_id)
    return IngestionStatus(task_id=task_id, status=res.status, total=0, done=0, failed=0)
