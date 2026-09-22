"""test_search_chunk_answer_flag.py — 청크 모드 답변 생성 스위치.

딥리서치 탐색은 resp.chunks 만 쓰고 answer 를 버린다. 하위질문마다 답변을
만들면 컨텍스트 예산 10만 토큰짜리 확장+생성이 한 잡에 6~24회 돌고 전부
폐기된다 — 그래서 generate_answer 를 받는다. 기본값은 True 라 기존
호출자(도서·논문 검색 API)의 동작은 그대로다.

pipeline 은 reranker(torch)·indexer(pymilvus) 를 물고 오므로, 미설치 환경에서만
더미를 꽂아 import 를 통과시킨다(test_embed_index_guard.py 와 같은 방식).
"""
import asyncio
import importlib
import sys
from unittest.mock import MagicMock

_HEAVY = ("torch", "transformers", "FlagEmbedding", "pymilvus")
# 더미를 꽂은 채 우리 쪽 모듈이 sys.modules 에 남으면 뒤에 도는 테스트가 Mock 을
# 물려받는다. monkeypatch.delitem 으로 지워 두면 테스트가 끝날 때 없는 상태로
# 복원되고 다음 사용자가 제대로 다시 import 한다.
_CACHED = ("services.search.pipeline", "services.search.reranker",
           "services.ingestion.embedder", "services.ingestion.indexer")


def _load_pipeline(monkeypatch):
    for name in _HEAVY:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    for name in _CACHED:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module("services.search.pipeline")


class _Hit:
    """indexer.search_chunks 가 돌려주는 행 대역."""

    chunk_id, book_id, chunk_idx = "A__0004", "A", 4
    text, page_start, page_end, score = "본문", 3, 4, 0.5


def _patch(monkeypatch, pipeline) -> list[str]:
    """Milvus 검색은 1건으로 고정하고, 확장·생성 3종은 호출 기록만 남긴다."""
    monkeypatch.setattr(pipeline, "search_chunks", lambda *a, **k: [_Hit()])
    called: list[str] = []

    async def _expand(chunks, db):
        called.append("expand")
        return []

    async def _with_context(query, contexts):
        called.append("with_context")
        return "확장 답변"

    async def _plain(query, chunks):
        called.append("plain")
        return "기본 답변"

    monkeypatch.setattr(pipeline, "expand_context", _expand)
    monkeypatch.setattr(pipeline, "_generate_answer_with_context", _with_context)
    monkeypatch.setattr(pipeline, "_generate_answer", _plain)
    return called


def _chunk_mode(pipeline, *, db, **kwargs):
    return asyncio.run(pipeline._search_chunk_mode(
        "질문", None, [0.1], {1: 0.2}, 3, False, 0.0, db, **kwargs,
    ))


def test_default_generates_with_expanded_context(monkeypatch):
    """기본값 True — 기존 호출자의 동작이 바뀌면 안 된다."""
    pipeline = _load_pipeline(monkeypatch)
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=MagicMock())
    assert resp.answer == "확장 답변"
    assert called == ["expand", "with_context"]


def test_false_skips_expansion_and_generation(monkeypatch):
    pipeline = _load_pipeline(monkeypatch)
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=MagicMock(), generate_answer=False)
    assert resp.answer is None
    assert called == []
    assert len(resp.chunks) == 1        # 검색 결과는 그대로 온다


def test_false_also_skips_the_no_db_path(monkeypatch):
    """db 가 없으면 예전 코드는 _generate_answer 로 답변을 만들었다 — 이쪽도 꺼진다."""
    pipeline = _load_pipeline(monkeypatch)
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=None, generate_answer=False)
    assert resp.answer is None
    assert called == []


def test_search_threads_the_flag_into_chunk_mode(monkeypatch):
    """search() 가 안 넘기면 explore 의 generate_answer=False 가 조용히 무시된다."""
    pipeline = _load_pipeline(monkeypatch)
    called = _patch(monkeypatch, pipeline)
    monkeypatch.setattr(pipeline, "embed_texts", lambda texts, is_query=False: ([[0.1]], [{1: 0.2}]))
    resp = asyncio.run(pipeline.search(
        "질문", mode="chunk", top_k=3, use_rewrite=False, use_rerank=False,
        doc_scope="paper", generate_answer=False, db=None,
    ))
    assert resp.answer is None
    assert called == []
