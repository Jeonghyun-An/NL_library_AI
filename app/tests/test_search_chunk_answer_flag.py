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
import types
from unittest.mock import MagicMock

import pytest

_HEAVY = ("torch", "transformers", "FlagEmbedding", "pymilvus")
_CACHED = ("services.search.pipeline", "services.search.reranker",
           "services.ingestion.embedder", "services.ingestion.indexer")


def _stubbed_pipeline(monkeypatch):
    """더미 위에서 pipeline 을 새로 import 해 넘기고, 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 앞 테스트가 남긴 모듈을 물려받지 않게 해 줄 뿐이다.
    원래 없던 키는 되돌릴 목록에 오르지 않아서, 여기서 새로 import 한 모듈(더미
    torch·pymilvus 에 묶인 채)은 teardown 뒤에도 남고 뒤에 도는 테스트가 그것을
    물려받는다. 그래서 직접 빼고, 원래 있던 항목은 monkeypatch 가 되돌리게 둔다.

    부모 패키지 속성도 같은 규칙이다. 문자열 경로 monkeypatch 는 sys.modules 보다
    부모 속성을 먼저 따라가므로, 새 모듈을 가리키는 속성은 지우고 원래 있던 속성은
    import 전에 monkeypatch 에 맡겨 되돌리게 한다 — 새 import 가 그 속성을 덮어쓰고,
    되살아난 sys.modules 항목은 다시 import 해도 속성을 되달지 않는다.
    """
    for name in _HEAVY:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    for name in _CACHED:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield importlib.import_module("services.search.pipeline")
    for name in _CACHED:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)


@pytest.fixture
def pipeline(monkeypatch):
    yield from _stubbed_pipeline(monkeypatch)


def test_loader_leaves_sys_modules_as_it_found_them():
    snapshot = {name: sys.modules.get(name) for name in _CACHED}
    with pytest.MonkeyPatch.context() as mp:
        loader = _stubbed_pipeline(mp)
        next(loader)
        next(loader, None)
    assert {name: sys.modules.get(name) for name in _CACHED} == snapshot


def test_loader_restores_parent_attributes_of_modules_already_loaded():
    """앞 테스트가 올려 둔 모듈이면 끝난 뒤 부모 패키지 속성도 그 모듈이어야 한다.

    sys.modules 만 되돌리면 부모 속성이 지워진 채 남는다. 문자열 경로
    monkeypatch("services.ingestion.indexer.x")는 부모 속성을 따라가므로 뒤 테스트가
    AttributeError 로 죽는다 — sys.modules 에 있는 모듈은 다시 import 해도 속성을
    되달지 않는다.
    """
    originals = {name: types.ModuleType(name) for name in _CACHED}
    with pytest.MonkeyPatch.context() as outer:
        for name, module in originals.items():
            parent, _, child = name.rpartition(".")
            outer.setitem(sys.modules, name, module)
            outer.setattr(importlib.import_module(parent), child, module, raising=False)
        with pytest.MonkeyPatch.context() as mp:
            loader = _stubbed_pipeline(mp)
            next(loader)
            next(loader, None)
        for name, module in originals.items():
            parent, _, child = name.rpartition(".")
            assert sys.modules[name] is module
            assert getattr(sys.modules[parent], child, None) is module, name


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
