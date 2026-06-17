import logging
import os
from fastapi import APIRouter, Depends, File, Header, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from core.config import get_settings
from core.deps import get_db
from schemas.book import (
    SearchRequest,
    ChunkSearchResponse,
    BookSearchResponse,
    BookOut,
)
from repositories.book import BookRepository
from services.search.pipeline import search

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.post(
    "/search",
    response_model=ChunkSearchResponse | BookSearchResponse,
)
async def search_papers(
    req: SearchRequest,
    session_id: str | None = Header(None, alias="x-session-id"),
    db: AsyncSession = Depends(get_db),
):
    if not session_id or session_id == "null":
        session_id = str(uuid4())

    result = await search(
        req.query,
        mode=req.mode,
        top_k=req.top_k,
        use_rewrite=req.use_rewrite,
        use_rerank=req.use_rerank,
        doc_scope="paper",
        db=db,
    )

    if isinstance(result, BookSearchResponse):
        repo = BookRepository(db)
        for bg in result.books:
            book = await repo.get_by_cnts_id(bg.book_id)
            if book:
                bg.book_info = BookOut.model_validate(book)

    return result


@router.post("/catalog/load")
async def load_kci_catalog(file: UploadFile = File(...)):
    """KCI 논문 메타데이터 xlsx 업로드 → Celery 비동기 처리.

    업로드 파일은 fastapi/워커가 공유하는 /app/data 볼륨에 저장해야
    별도 컨테이너인 워커가 읽을 수 있다 (tempfile은 컨테이너 간 비공유).
    """
    content = await file.read()
    suffix = os.path.splitext(file.filename or "kci.xlsx")[1] or ".xlsx"
    upload_dir = "/app/data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, f"{uuid4().hex}{suffix}")
    with open(save_path, "wb") as f:
        f.write(content)

    from workers.tasks import load_kci_catalog_xlsx
    task = load_kci_catalog_xlsx.delay(save_path)
    return {"task_id": task.id, "filename": file.filename}
