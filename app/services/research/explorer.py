"""explorer.py — 하위질문 1개를 탐색한다

기존 검색 파이프라인을 그대로 쓰고(논문 스코프), 그 위에 피인용 가중만
얹는다. 순위 계산은 rank_hits 로 빼서 Milvus 없이 테스트한다.
"""
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.book import BookRepository
from services.research.scoring import blend_score, impact_per_year, parse_pub_year
from services.research.state import HitRow

log = logging.getLogger(__name__)


def rank_hits(
    hits: list[HitRow], meta_by_id: dict[str, dict], *,
    citation_weight: float, now_year: int,
) -> list[HitRow]:
    """리랭킹 점수에 연간 피인용을 얹어 다시 정렬한다. 입력은 건드리지 않는다."""
    ranked = []
    for hit in hits:
        meta = meta_by_id.get(hit["book_id"]) or {}
        impact = impact_per_year(
            meta.get("kci_citations"), parse_pub_year(meta.get("pub_date")),
            now_year=now_year,
        )
        row = dict(hit)
        row["score"] = blend_score(hit["score"], impact=impact, weight=citation_weight)
        ranked.append(row)
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked


async def explore(query: str, *, params: dict, db: AsyncSession) -> tuple[list[HitRow], dict[str, dict]]:
    """검색 → 서지 조회 → 피인용 가중 재정렬.

    returns (정렬된 hit 목록, cnts_id → 서지 메타)
    """
    # pipeline 은 reranker(torch) 를 물고 와 모듈 최상단에서 임포트하면 이 파일을
    # 단순히 열기만 해도(rank_hits 만 쓰는 테스트에서도) torch 가 있어야 한다.
    # 기존 코드베이스도 같은 이유로 지연 임포트한다(api/book.py·main.py 참고).
    from services.search.pipeline import search

    resp = await search(
        query, mode="chunk", top_k=params["per_subq_top_k"],
        doc_scope="paper", db=db,
    )
    hits: list[HitRow] = [
        {
            "book_id": c.book_id, "chunk_id": c.chunk_id, "text": c.text,
            "page_start": c.page_start, "page_end": c.page_end,
            "score": c.rerank_score if c.rerank_score is not None else c.score,
        }
        for c in resp.chunks
    ]
    if not hits:
        return [], {}

    repo = BookRepository(db)
    books = await repo.get_by_cnts_ids(list({h["book_id"] for h in hits}))
    meta_by_id = {
        cnts_id: {
            "title": b.title, "personal_author": b.personal_author,
            "series_title": b.series_title, "vol_issue": b.vol_issue,
            "pub_date": b.pub_date, "kci_citations": b.kci_citations,
            "grade": b.grade,
        }
        for cnts_id, b in books.items()
    }
    ranked = rank_hits(
        hits, meta_by_id,
        citation_weight=params["citation_weight"], now_year=datetime.now().year,
    )
    return ranked, meta_by_id
