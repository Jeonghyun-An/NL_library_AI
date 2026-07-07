import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from repositories.book import BookRepository
from schemas.book import ScenarioRequest, ScenarioBook, ScenarioResponse
from services.search.pipeline import search
from services.search.scenario import recommend_books

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scenario", tags=["scenario"])


@router.post("/recommend", response_model=ScenarioResponse)
async def scenario_recommend(
    req: ScenarioRequest,
    db: AsyncSession = Depends(get_db),
):
    """독자 고민 → 맞춤 도서 추천 (reason + quote)"""
    result = await search(
        req.concern,
        mode="book",
        top_k=req.top_k,
        use_rewrite=True,
        use_rerank=True,
        db=db,
    )

    if not result.books:
        raise HTTPException(404, "추천 도서를 찾을 수 없습니다")

    repo = BookRepository(db)
    cnts_ids = [bg.book_id for bg in result.books]
    book_map = await repo.get_by_cnts_ids(cnts_ids)

    # 검색 파이프라인은 리랭킹용으로 top_k보다 많은 후보를 반환하므로
    # 요청한 top_k만큼만 LLM 추천에 사용한다
    ordered_books = [book_map[bid] for bid in cnts_ids if bid in book_map][
        : req.top_k
    ]
    rec = await recommend_books(req.concern, ordered_books)

    books = [
        ScenarioBook(
            book_id=item["book_id"],
            book_info=book_map.get(item["book_id"]),
            reason=item.get("reason", ""),
            quote=item.get("quote", ""),
        )
        for item in rec.get("items", [])
    ][: req.top_k]

    return ScenarioResponse(concern=req.concern, books=books)
