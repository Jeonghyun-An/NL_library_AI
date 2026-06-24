"""
paper_related.py — AI 연관 논문 추천

현재 논문의 제목 + 초록을 임베딩해 Milvus에서 유사 논문을 검색한다.
embed_texts / search_by_book 을 pipeline.py 와 동일 패턴으로 직접 호출한다.
"""
import logging

from core.config import get_settings
from repositories.book import BookRepository
from schemas.book import BookOut
from services.ingestion.embedder import embed_texts
from services.ingestion.indexer import search_by_book

log = logging.getLogger(__name__)
cfg = get_settings()

_PAPER_EXPR = 'book_id like "KCI_FI%"'
_FETCH_MULT = 5   # top_k_chunks = top_k * _FETCH_MULT


async def find_related_papers(
    cnts_id: str,
    db,
    top_k: int = 4,
) -> list[dict]:
    """
    cnts_id 논문과 유사한 다른 KCI 논문 top_k 개 반환.

    반환값: [{"book_id": str, "score": float, "book_info": BookOut | None}]
    """
    repo = BookRepository(db)
    source: BookOut | None = await repo.get_by_cnts_id(cnts_id)
    if not source:
        return []

    # 대표 쿼리: 제목 + 초록(MARC 필드 또는 enricher 저장값 우선)
    abstract = (
        ((source.extra or {}).get("abstract") or "")
        or (source.abstract or "")
        or (source.summary or "")
        or (source.introduction or "")
    )
    title = source.title or ""
    query_text = f"{title}. {abstract[:800]}".strip(". ") if abstract else title
    if not query_text.strip():
        log.warning("[paper_related] %s: 대표 쿼리 텍스트 없음 — 연관 논문 추천 생략", cnts_id)
        return []

    # 임베딩 (sync, pipeline.py 와 동일 패턴)
    dense_vecs, sparse_vecs = embed_texts([query_text])
    dense, sparse = dense_vecs[0], sparse_vecs[0]

    # Milvus: KCI 논문 범위 + 자기 자신 제외
    expr = f'{_PAPER_EXPR} && book_id != "{cnts_id}"'
    book_hits = search_by_book(
        dense, sparse,
        top_k_chunks=top_k * _FETCH_MULT,
        top_k_books=top_k + 1,
        meta_expr=expr,
    )
    book_hits.pop(cnts_id, None)  # 혹시 포함됐을 경우 안전 제거

    result_ids = list(book_hits.keys())[:top_k]
    if not result_ids:
        return []

    books_map: dict[str, BookOut] = await repo.get_by_cnts_ids(result_ids)

    results = []
    for bid in result_ids:
        hits = book_hits[bid]
        best_score = round(max(h.score for h in hits), 4)
        results.append({
            "book_id": bid,
            "score": best_score,
            "book_info": books_map.get(bid),
        })

    return results
