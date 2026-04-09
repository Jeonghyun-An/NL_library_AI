"""
pipeline.py — RAG 검색 파이프라인 (청크 모드 / 도서 모드)

흐름:
  ① 쿼리 재작성 (vLLM)
  ② 쿼리 임베딩 (BGE-M3)
  ③ Milvus 벡터 검색
  ④ 리랭킹 (Jina Reranker v2)
  ⑤ 답변 생성 (vLLM)
"""
import time
import logging

import httpx

from core.config import get_settings
from services.search.query_rewriter import rewrite_query
from services.search.reranker import rerank as rerank_docs
from services.ingestion.embedder import embed_texts
from services.ingestion.indexer import search_chunks, search_by_book
from schemas.book import (
    ChunkHit,
    BookChunkGroup,
    ChunkSearchResponse,
    BookSearchResponse,
)

log = logging.getLogger(__name__)
cfg = get_settings()


async def search(
    query: str,
    *,
    mode: str = "book",
    top_k: int = 5,
    use_rewrite: bool = True,
    use_rerank: bool = True,
) -> ChunkSearchResponse | BookSearchResponse:
    t0 = time.perf_counter()

    # ① 쿼리 재작성
    rewritten = None
    search_query = query
    if use_rewrite:
        try:
            rewritten = await rewrite_query(query)
            search_query = rewritten
            log.info(f"쿼리 재작성: '{query}' → '{rewritten}'")
        except Exception as e:
            log.warning(f"쿼리 재작성 실패, 원본 사용: {e}")

    # ② 쿼리 임베딩
    query_emb = embed_texts([search_query], is_query=True)[0]

    elapsed = (time.perf_counter() - t0) * 1000

    if mode == "chunk":
        return await _search_chunk_mode(query, rewritten, query_emb, top_k, use_rerank, elapsed)
    else:
        return await _search_book_mode(query, rewritten, query_emb, top_k, use_rerank, elapsed)


async def _search_chunk_mode(
    original: str,
    rewritten: str | None,
    query_emb: list[float],
    top_k: int,
    use_rerank: bool,
    elapsed_base: float,
) -> ChunkSearchResponse:
    t0 = time.perf_counter()

    candidates = search_chunks(query_emb, top_k=top_k * 4)

    chunks = [
        ChunkHit(
            chunk_id=h.chunk_id,
            book_id=h.book_id,
            chunk_idx=h.chunk_idx,
            text=h.text,
            page_start=h.page_start,
            page_end=h.page_end,
            score=h.score,
        )
        for h in candidates
    ]

    # ④ 리랭킹
    if use_rerank and chunks:
        query_text = rewritten or original
        try:
            ranked = rerank_docs(query_text, [c.text for c in chunks])
            reranked = []
            for r in ranked:
                c = chunks[r.index]
                c.rerank_score = r.score
                reranked.append(c)
            chunks = reranked
        except Exception as e:
            log.warning(f"리랭킹 실패, 벡터 점수 유지: {e}")

    chunks = chunks[:top_k]

    answer = await _generate_answer(original, chunks)

    elapsed = elapsed_base + (time.perf_counter() - t0) * 1000

    return ChunkSearchResponse(
        query=original,
        rewritten_query=rewritten,
        answer=answer,
        chunks=chunks,
        elapsed_ms=round(elapsed, 1),
    )


async def _search_book_mode(
    original: str,
    rewritten: str | None,
    query_emb: list[float],
    top_k: int,
    use_rerank: bool,
    elapsed_base: float,
) -> BookSearchResponse:
    t0 = time.perf_counter()

    book_hits = search_by_book(query_emb, top_k_chunks=top_k * 8, top_k_books=top_k)

    books = []
    for book_id, hits in book_hits.items():
        chunks = [
            ChunkHit(
                chunk_id=h.chunk_id,
                book_id=h.book_id,
                chunk_idx=h.chunk_idx,
                text=h.text,
                page_start=h.page_start,
                page_end=h.page_end,
                score=h.score,
            )
            for h in hits
        ]

        # ④ 도서 내 청크 리랭킹
        if use_rerank and chunks:
            query_text = rewritten or original
            try:
                ranked = rerank_docs(query_text, [c.text for c in chunks])
                reranked = []
                for r in ranked:
                    c = chunks[r.index]
                    c.rerank_score = r.score
                    reranked.append(c)
                chunks = reranked
            except Exception as e:
                log.warning(f"[{book_id}] 도서 내 리랭킹 실패: {e}")

        best = max(c.rerank_score or c.score for c in chunks)
        books.append(BookChunkGroup(
            book_id=book_id,
            best_score=best,
            chunks=chunks,
        ))

    books.sort(key=lambda b: b.best_score, reverse=True)

    elapsed = elapsed_base + (time.perf_counter() - t0) * 1000

    return BookSearchResponse(
        query=original,
        rewritten_query=rewritten,
        books=books,
        elapsed_ms=round(elapsed, 1),
    )


async def _generate_answer(query: str, chunks: list[ChunkHit]) -> str | None:
    if not chunks:
        return None

    context = "\n\n---\n\n".join(
        f"[출처: {c.book_id}, p.{c.page_start}-{c.page_end}]\n{c.text}"
        for c in chunks[:5]
    )

    prompt = (
        "아래 자료를 참고하여 질문에 답변해주세요.\n"
        "답변에 사용한 자료의 출처(도서, 페이지)를 함께 표기하세요.\n"
        "자료에 없는 내용은 추측하지 마세요.\n\n"
        f"[자료]\n{context}\n\n"
        f"[질문]\n{query}\n\n"
        "[답변]"
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{cfg.VLLM_BASE_URL}/chat/completions",
                json={
                    "model": cfg.VLLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2048,
                    "temperature": 0.3,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"답변 생성 실패: {e}")
        return None