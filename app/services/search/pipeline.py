"""
pipeline.py — RAG 검색 파이프라인 (청크 모드 / 도서 모드)

흐름:
  ① 쿼리 재작성 (vLLM)
  ② 쿼리 임베딩 (BGE-M3)
  ③ Milvus 벡터 검색
  ④ 리랭킹 (Jina Reranker v2)
  ⑤ 답변 생성 (vLLM)
"""
import asyncio
import json
import math
import re
import time
import logging
from typing import AsyncGenerator

import httpx

from core.config import get_settings
from services.prompts import get_prompt
from services.search.sse_helpers import process_reason_deltas
from services.search.curator import curate_books, _parse_curation_result
from services.search.query_rewriter import rewrite_query
from services.search.metadata_filter import extract_metadata_filter, MetadataFilter
from services.search.reranker import rerank as rerank_docs
from services.search.context_expander import expand_context, ExpandedContext
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


_PAPER_EXPR = 'book_id like "KCI_FI%"'
_BOOK_EXPR  = 'book_id not like "KCI_FI%"'


def _build_milvus_expr(f: MetadataFilter, doc_scope: str = "all") -> str | None:
    """
    MetadataFilter + doc_scope → Milvus boolean expression.
    doc_scope: "paper" | "book" | "all"
    """
    parts: list[str] = []

    if doc_scope == "paper":
        parts.append(_PAPER_EXPR)
    elif doc_scope == "book":
        parts.append(_BOOK_EXPR)

    if f and f.has_filter:
        if f.pub_year_from:
            parts.append(f'pub_date >= "{f.pub_year_from}"')
        if f.pub_year_to:
            parts.append(f'pub_date < "{f.pub_year_to + 1}"')

    return " && ".join(parts) if parts else None


async def search(
    query: str,
    *,
    mode: str = "book",
    top_k: int = 10,
    use_rewrite: bool = True,
    use_rerank: bool = True,
    doc_scope: str = "all",   # "paper" | "book" | "all"
    db=None,
) -> ChunkSearchResponse | BookSearchResponse:
    t0 = time.perf_counter()

    # ① 쿼리 재작성 + 메타데이터 필터 추출 (병렬)
    rewritten: str | None = None
    search_query = query
    metadata_filter: MetadataFilter | None = None

    coros: list = []
    tags: list[str] = []
    if use_rewrite:
        coros.append(rewrite_query(query, db=db))
        tags.append("rewrite")
    if db:
        coros.append(extract_metadata_filter(query))
        tags.append("filter")

    if coros:
        results = await asyncio.gather(*coros, return_exceptions=True)
        for tag, result in zip(tags, results):
            if tag == "rewrite" and isinstance(result, str):
                rewritten = result
                search_query = rewritten
                log.info(f"쿼리 재작성: '{query}' → '{rewritten}'")
            elif tag == "rewrite" and isinstance(result, Exception):
                log.warning(f"쿼리 재작성 실패, 원본 사용: {result}")
            elif tag == "filter" and isinstance(result, MetadataFilter):
                metadata_filter = result
                if metadata_filter.has_filter:
                    log.info(f"메타데이터 필터 감지: {metadata_filter}")
            elif tag == "filter" and isinstance(result, Exception):
                log.warning(f"메타데이터 필터 추출 실패: {result}")

    # 메타데이터 필터 + doc_scope → Milvus expression
    milvus_expr = _build_milvus_expr(metadata_filter, doc_scope)
    if milvus_expr:
        log.info(f"Milvus expression: {milvus_expr}")

    # ② 쿼리 임베딩 (dense + sparse)
    dense_vecs, sparse_vecs = embed_texts([search_query], is_query=True)
    query_dense = dense_vecs[0]
    query_sparse = sparse_vecs[0]

    elapsed = (time.perf_counter() - t0) * 1000

    if mode == "chunk":
        return await _search_chunk_mode(
            query, rewritten, query_dense, query_sparse, top_k, use_rerank, elapsed, db,
            meta_expr=milvus_expr,
        )
    else:
        return await _search_book_mode(
            query, rewritten, query_dense, query_sparse, top_k, use_rerank, elapsed, db,
            meta_expr=milvus_expr,
            metadata_filter=metadata_filter,
        )


async def _search_chunk_mode(
    original: str,
    rewritten: str | None,
    query_dense: list[float],
    query_sparse: dict,
    top_k: int,
    use_rerank: bool,
    elapsed_base: float,
    db=None,
    *,
    meta_expr: str | None = None,
) -> ChunkSearchResponse:
    t0 = time.perf_counter()

    candidates = search_chunks(query_dense, query_sparse, top_k=top_k * cfg.CHUNK_MODE_FETCH_MULTIPLIER, meta_expr=meta_expr)

    if not candidates:
        elapsed = elapsed_base + (time.perf_counter() - t0) * 1000
        return ChunkSearchResponse(
            query=original,
            rewritten_query=rewritten,
            answer="검색 결과가 없습니다. 도서 데이터를 먼저 수집해주세요.",
            chunks=[],
            elapsed_ms=round(elapsed, 1),
        )

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

    # 컨텍스트 확장: 청크 주변 원문 로드 (126K 활용)
    answer = None
    if db:
        try:
            expanded = await expand_context(chunks, db)
            answer = await _generate_answer_with_context(original, expanded)
        except Exception as e:
            log.warning(f"컨텍스트 확장 실패, 청크 텍스트로 fallback: {e}")
            answer = await _generate_answer(original, chunks)
    else:
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
    query_dense: list[float],
    query_sparse: dict,
    top_k: int,
    use_rerank: bool,
    elapsed_base: float,
    db=None,
    *,
    meta_expr: str | None = None,
    metadata_filter: MetadataFilter | None = None,
) -> BookSearchResponse:
    t0 = time.perf_counter()

    # 리랭킹 품질은 후보 풀 크기에 비례한다.
    # 날짜 정렬 시 4x, 일반 검색 시 3x 후보를 확보한 뒤 리랭킹으로 추려낸다.
    needs_date_sort = metadata_filter and metadata_filter.sort_by in ("recent", "oldest")
    fetch_books = top_k * cfg.BOOK_MODE_FETCH_MULTIPLIER_SORT if needs_date_sort else top_k * cfg.BOOK_MODE_FETCH_MULTIPLIER

    book_hits = search_by_book(
        query_dense,
        query_sparse,
        top_k_chunks=fetch_books * cfg.HYBRID_SEARCH_CHUNK_LIMIT_MULT,
        top_k_books=fetch_books,
        meta_expr=meta_expr,
    )

    if not book_hits:
        elapsed = elapsed_base + (time.perf_counter() - t0) * 1000
        return BookSearchResponse(
            query=original,
            rewritten_query=rewritten,
            books=[],
            elapsed_ms=round(elapsed, 1),
        )

    books = []
    for book_id, hits in book_hits.items():
        # 점수 집계: 메타 청크(chunk_idx=-1) 포함 → 메타 기반 쿼리도 책 발견 가능
        best_raw = max(h.score for h in hits)

        # 응답용 청크: 메타 청크 제외 (raw 메타 텍스트 노출 방지)
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
            if h.chunk_idx != -1
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

        # 리랭킹된 본문 청크 점수, 없으면 메타 청크 점수(best_raw)로 fallback
        best = max((c.rerank_score or c.score for c in chunks), default=best_raw)

        # 다수 청크가 매칭될수록 도서 적합도가 높음 → 로그 스케일 부스팅
        # 청크 1개=×1.0, 2개=×1.07, 3개=×1.11, 5개=×1.16
        n_chunks = len(chunks)
        if n_chunks > 1:
            best = min(best * (1 + 0.1 * math.log2(n_chunks)), 1.0)

        books.append(BookChunkGroup(
            book_id=book_id,
            best_score=best,
            chunks=chunks,
        ))

    books.sort(key=lambda b: b.best_score, reverse=True)

    # 날짜 정렬 요청이면 Milvus pub_date 스칼라 필드 기준 재정렬
    if metadata_filter and metadata_filter.sort_by in ("recent", "oldest"):
        reverse = metadata_filter.sort_by == "recent"

        def _pub_date(b: BookChunkGroup) -> str:
            hits = book_hits.get(b.book_id) or []
            return hits[0].pub_date if hits else ""

        books.sort(key=_pub_date, reverse=reverse)
        books = books[:top_k]  # 날짜 정렬 후 top_k로 축소

    # ⑤ 추천 이유는 별도 스트리밍 엔드포인트(/reason/stream)로 분리
    #    메인 검색 응답 속도를 위해 여기서는 생성하지 않음

    elapsed = elapsed_base + (time.perf_counter() - t0) * 1000

    return BookSearchResponse(
        query=original,
        rewritten_query=rewritten,
        books=books,
        elapsed_ms=round(elapsed, 1),
    )


async def stream_book_reason(
    query: str,
    book_id: str,
    chunk_texts: list[str],
    rewritten_query: str = "",
    *,
    book=None,
) -> AsyncGenerator[str, None]:
    """
    도서 추천 이유 SSE 스트리밍 생성기.
    FastAPI StreamingResponse에 직접 전달한다.
    book 객체는 호출자(엔드포인트)에서 미리 조회해 넘긴다.
    """

    # ── 도서 서지 정보 블록 ──────────────────────────────
    meta_lines = []
    if book:
        if book.title:
            meta_lines.append(f"제목: {book.title}")
        author = book.personal_author or book.corporate_author
        if author:
            meta_lines.append(f"저자/기관: {author}")
        if book.pub_date:
            meta_lines.append(f"발행년도: {book.pub_date}")
        if book.publisher:
            meta_lines.append(f"출판사: {book.publisher}")
        if book.kdc:
            meta_lines.append(f"KDC 분류: {book.kdc}")
        if book.subject:
            meta_lines.append(f"주제: {book.subject}")
        if book.keyword:
            meta_lines.append(f"키워드: {book.keyword}")
    book_meta = "\n".join(meta_lines)

    # ── 컨텍스트 블록 (요약 + 줄거리 + 매칭 구절) ────────
    context_parts = []
    if book and book.summary:
        context_parts.append(f"[도서 요약]\n{book.summary}")
    if book and book.plot:
        context_parts.append(f"[도서 줄거리]\n{book.plot}")
    if chunk_texts:
        chunks_block = "\n\n".join(
            f"[관련 구절 {i+1}]\n{text}" for i, text in enumerate(chunk_texts[:cfg.REASON_CHUNKS_DISPLAY_LIMIT])
        )
        context_parts.append(f"[검색 매칭 구절]\n{chunks_block}")
    context_text = "\n\n".join(context_parts)

    # ── MARC 키워드 추출 (653 keyword / 650 subject) ──────
    marc_keywords: list[str] = []
    if book:
        raw = book.keyword or book.subject or ""
        if raw:
            marc_keywords = [k.strip() for k in re.split(r"[,;|/·]", raw) if k.strip()][:cfg.MARC_KEYWORDS_LIMIT]

    # MARC 키워드가 있으면 즉시 emit
    if marc_keywords:
        yield f"data: {json.dumps({'keywords': marc_keywords}, ensure_ascii=False)}\n\n"

    # ── 메시지 구성 ──────────────────────────────────────
    intent = rewritten_query or query

    kw_instruction = (
        ""
        if marc_keywords
        else (
            "반드시 답변 첫 줄에 다음 형식으로 이 도서의 핵심 테마 키워드 5개를 출력하세요.\n"
            "키워드는 아래 독서 의도와 도서 내용을 연결하는 개념으로 선택하세요:\n"
            "#KW: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5\n"
            "두 번째 줄부터 추천 이유 본문을 작성하세요.\n\n"
        )
    )

    tpl = get_prompt("recommendation")
    system_message, user_message, params = tpl.render(
        kw_instruction=kw_instruction,
        intent=intent,
        query=query,
        book_meta=book_meta,
        context_text=context_text,
    )

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json={
                    "model": cfg.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user",   "content": user_message},
                    ],
                    "max_tokens": cfg.RECOMMENDATION_MAX_TOKENS,
                    "temperature": params.get("temperature", cfg.REASON_TEMPERATURE),
                    "stream": True,
                },
                timeout=float(cfg.REASON_TIMEOUT),
            ) as resp:
                async def _delta_gen():
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            pass

                async for event in process_reason_deltas(_delta_gen(), marc_keywords):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    except Exception as e:
        log.error(f"[{book_id}] 추천 이유 스트리밍 실패: {e}")

    yield "data: [DONE]\n\n"


async def _generate_answer_with_context(
    query: str,
    contexts: list,
) -> str | None:
    """확장된 원문 컨텍스트 기반 LLM 답변 생성 (126K 활용)"""
    if not contexts:
        return None

    context_text = "\n\n" + "=" * 40 + "\n\n".join(
        f"[출처: {c.book_id}, p.{c.page_range[0]}-{c.page_range[1]}, "
        f"섹션 {c.section_range[0]}-{c.section_range[1]}]\n\n{c.expanded_text}"
        for c in contexts
    )

    total_tokens = sum(c.token_count for c in contexts)
    log.info(f"LLM 컨텍스트: {len(contexts)}개 소스, {total_tokens} 토큰")

    prompt = (
        "아래 도서 원문을 참고하여 질문에 상세히 답변해주세요.\n"
        "답변에 사용한 자료의 출처(도서, 페이지)를 함께 표기하세요.\n"
        "자료에 없는 내용은 추측하지 마세요.\n\n"
        f"[도서 원문]\n{context_text}\n\n"
        f"[질문]\n{query}\n\n"
        "[답변]"
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json={
                    "model": cfg.LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": cfg.ANSWER_EXTENDED_MAX_TOKENS,
                    "temperature": cfg.ANSWER_EXTENDED_TEMPERATURE,
                },
                timeout=float(cfg.ANSWER_EXTENDED_TIMEOUT),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"확장 컨텍스트 답변 생성 실패: {e}")
        return None


async def _generate_answer(query: str, chunks: list[ChunkHit]) -> str | None:
    if not chunks:
        return None

    context = "\n\n---\n\n".join(
        f"[출처: {c.book_id}, p.{c.page_start}-{c.page_end}]\n{c.text}"
        for c in chunks[:cfg.ANSWER_BASE_CHUNKS_LIMIT]
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
                f"{cfg.LLM_BASE_URL}/chat/completions",
                json={
                    "model": cfg.LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": cfg.ANSWER_BASE_MAX_TOKENS,
                    "temperature": cfg.ANSWER_BASE_TEMPERATURE,
                },
                timeout=float(cfg.ANSWER_BASE_TIMEOUT),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"답변 생성 실패: {e}")
        return None