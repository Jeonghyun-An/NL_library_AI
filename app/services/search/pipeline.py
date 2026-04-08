import time
from services.search.query_rewriter import rewrite_query
from services.search.reranker import rerank
from services.ingestion.embedder import embed_texts
from services.ingestion.indexer import search_similar
from schemas.book import SearchRequest, SearchResponse, SearchResult
from repositories.book import BookRepository


async def run_search(req: SearchRequest, repo: BookRepository) -> SearchResponse:
    t0 = time.perf_counter()

    # 1. 쿼리 재작성
    rewritten = await rewrite_query(req.query)

    # 2. 임베딩 → 벡터 검색
    vecs = embed_texts([rewritten], is_query=True)
    candidates = search_similar(vecs[0], top_k=20)

    # 3. LLM 재정렬 (선택)
    if req.use_rerank and candidates:
        ranked = await rerank(rewritten, candidates, top_k=req.top_k)
    else:
        ranked = candidates[:req.top_k]

    # 4. PostgreSQL 메타데이터 조회
    books_map = await repo.get_by_cnts_ids([r["cnts_id"] for r in ranked])

    results = [
        SearchResult(
            book=books_map[r["cnts_id"]],
            score=r.get("llm_score", r.get("score", 0.0)),
            reason=r.get("reason", ""),
        )
        for r in ranked
        if r["cnts_id"] in books_map
    ]

    return SearchResponse(
        query=req.query,
        rewritten_query=rewritten,
        results=results,
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
    )