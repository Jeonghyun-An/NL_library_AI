import logging
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

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
