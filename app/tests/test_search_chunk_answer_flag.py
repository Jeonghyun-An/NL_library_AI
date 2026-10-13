"""test_search_chunk_answer_flag.py — 청크 모드 답변 생성 스위치.

딥리서치 탐색은 resp.chunks 만 쓰고 answer 를 버린다. 하위질문마다 답변을
만들면 컨텍스트 예산 10만 토큰짜리 확장+생성이 한 잡에 6~24회 돌고 전부
폐기된다 — 그래서 generate_answer 를 받는다. 기본값은 True 라 기존
호출자(도서·논문 검색 API)의 동작은 그대로다.

pipeline 은 reranker(torch)·indexer(pymilvus) 를 물고 오므로 공용 대역(pipeline_stub.py)의 pipeline 픽스처로
import 한다 — 미설치 환경에서만 더미를 꽂고, 끝나면 import 전 그대로 되돌린다.
"""
import asyncio
from unittest.mock import MagicMock

from pipeline_stub import pipeline  # noqa: F401 — 픽스처(테스트 인자 이름으로 쓴다)


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


def test_default_generates_with_expanded_context(monkeypatch, pipeline):
    """기본값 True — 기존 호출자의 동작이 바뀌면 안 된다."""
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=MagicMock())
    assert resp.answer == "확장 답변"
    assert called == ["expand", "with_context"]


def test_false_skips_expansion_and_generation(monkeypatch, pipeline):
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=MagicMock(), generate_answer=False)
    assert resp.answer is None
    assert called == []
    assert len(resp.chunks) == 1        # 검색 결과는 그대로 온다


def test_false_also_skips_the_no_db_path(monkeypatch, pipeline):
    """db 가 없으면 예전 코드는 _generate_answer 로 답변을 만들었다 — 이쪽도 꺼진다."""
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=None, generate_answer=False)
    assert resp.answer is None
    assert called == []


def test_search_threads_the_flag_into_chunk_mode(monkeypatch, pipeline):
    """search() 가 안 넘기면 explore 의 generate_answer=False 가 조용히 무시된다.

    explore 는 워커 세션을 db 로 넘긴다 — db=None 으로 부르면 확장 분기와 메타데이터
    필터 분기를 둘 다 건너뛰어 운영 호출 형태를 가린다.

    필터 호출은 예외가 아니라 기록으로 잡는다. search 는 필터를
    asyncio.gather(return_exceptions=True) 로 돌려 예외를 경고 로그로 삼키므로,
    대역이 던지는 AssertionError 로는 이 테스트가 실패하지 않는다.
    """
    called = _patch(monkeypatch, pipeline)
    monkeypatch.setattr(pipeline, "embed_texts", lambda texts, is_query=False: ([[0.1]], [{1: 0.2}]))
    filter_calls: list[str] = []

    async def _record_filter(query):
        filter_calls.append(query)
        return None

    monkeypatch.setattr(pipeline, "extract_metadata_filter", _record_filter)
    resp = asyncio.run(pipeline.search(
        "질문", mode="chunk", top_k=3, use_rewrite=False, use_rerank=False,
        doc_scope="paper", generate_answer=False, use_metadata_filter=False, db=MagicMock(),
    ))
    assert resp.answer is None
    assert called == []
    assert filter_calls == []
