import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.errors import search_outage_as_503
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
    """독자 고민 → 맞춤 도서 추천 (reason + quote).

    오류: 검색 기반(Milvus·임베딩) 연결/조회 장애는 503(search_unavailable). LLM 사유 생성이 실패하면 책은 그대로 두고
    빈 사유·인용으로 채운 뒤 ai_failed=true 를 싣는다 — 화면이 빈 칸 대신 '사유를 만들지 못했다'를 보인다."""
    with search_outage_as_503("상황별 추천"):
        result = await search(
            req.concern,
            mode="book",
            top_k=req.top_k,
            use_rewrite=True,
            use_rerank=True,
            doc_scope="book",   # 논문 제외, 도서만 검색
            db=db,
        )

        # 도서가 0권이면 날짜 조건만 빼고 도서 안에서 다시 찾는다 — 범위를 풀면 논문을 도서로 추천한다(api/book.py 와 같다)
        if not result.books:
            log.warning("도서 필터 검색 0건 — 날짜 조건 없이 도서 안에서 재시도")
            result = await search(
                req.concern,
                mode="book",
                top_k=req.top_k,
                use_rewrite=True,
                use_rerank=True,
                doc_scope="book",
                use_metadata_filter=False,
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

    return ScenarioResponse(
        concern=req.concern,
        intro=rec.get("intro", ""),
        books=books,
        ai_failed=bool(rec.get("ai_failed")),
    )
