"""test_stream_book_reason_end.py — 도서 추천 이유 스트림(services/search/pipeline.stream_book_reason)의 끝.

LLM 호출이 실패하면(httpx 연결·읽기 오류 등) [DONE] 앞에 {error} 이벤트를 먼저 보낸다. [DONE] 만 보내면 화면
(frontend/utils/bookAiPick.ts readReasonStream)이 '끝까지 받음'으로 읽어 받다 만 이유를 완성본으로 기록에 저장한다.
정상으로 끝난 스트림에는 {error} 가 없다.

pipeline 은 reranker(torch)·indexer(pymilvus) 를 물고 오므로, 미설치 환경에서만 더미를 꽂아 새로 import 하고 끝나면
import 전 그대로 되돌린다(test_search_chunk_answer_flag.py 의 _stubbed_pipeline 과 같은 방식).
"""
import asyncio
import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

_HEAVY = ("torch", "transformers", "FlagEmbedding", "pymilvus")
_CACHED = ("services.search.pipeline", "services.search.reranker",
           "services.ingestion.embedder", "services.ingestion.indexer")
DONE = "data: [DONE]\n\n"


def _stubbed_pipeline(monkeypatch):
    """더미 위에서 pipeline 을 새로 import 해 넘기고, 끝나면 import 전 그대로 되돌린다 — 새로 올린 모듈은 직접 빼고,
    원래 있던 항목·부모 패키지 속성은 monkeypatch 가 되돌리게 둔다."""
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


def _delta(text: str) -> str:
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]}, ensure_ascii=False)}"


def _fake_llm(monkeypatch, pipeline, lines, *, open_error=None, read_error=None):
    """LLM 스트리밍 대역 — pipeline.httpx.AsyncClient 를 갈아 lines 를 SSE 줄로 흘려 준다. open_error 면 stream() 을 여는
    자리에서, read_error 면 lines 를 다 흘린 뒤 읽는 자리에서 그 예외를 던진다."""

    class _Response:
        async def aiter_lines(self):
            for line in lines:
                yield line
            if read_error is not None:
                raise read_error

    class _Stream:
        async def __aenter__(self):
            if open_error is not None:
                raise open_error
            return _Response()

        async def __aexit__(self, *exc):
            return False

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, **kwargs):
            return _Stream()

    monkeypatch.setattr(pipeline.httpx, "AsyncClient", _Client)


def _run(pipeline, **kwargs) -> list[str]:
    async def collect():
        return [chunk async for chunk in pipeline.stream_book_reason("노인 우울", "B1", ["구절"], **kwargs)]
    return asyncio.run(collect())


def _events(chunks: list[str]) -> list[dict]:
    return [json.loads(c[len("data: "):]) for c in chunks if c != DONE]


def test_a_failed_connection_sends_an_error_event_before_done(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [], open_error=httpx.ConnectError("vLLM 연결 실패"))

    chunks = _run(pipeline)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    events = _events(chunks)
    assert events == [{"error": pipeline.REASON_STREAM_ERROR}]
    assert isinstance(pipeline.REASON_STREAM_ERROR, str) and pipeline.REASON_STREAM_ERROR.strip()


def test_a_read_error_after_some_text_keeps_the_text_then_sends_the_error(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [_delta("#KW: 우울, 노년\n"), _delta("이 책은 노년의 우울을 다루며 " * 3)],
              read_error=httpx.ReadTimeout("읽기 시간 초과"))

    chunks = _run(pipeline)

    assert chunks[-1] == DONE
    events = _events(chunks)
    assert events[0] == {"keywords": ["우울", "노년"]}
    assert "".join(e.get("text", "") for e in events).startswith("이 책은 노년의 우울을")
    # 오류는 받은 글 뒤, [DONE] 바로 앞에 한 번
    assert events[-1] == {"error": pipeline.REASON_STREAM_ERROR}
    assert sum("error" in e for e in events) == 1


def test_marc_keywords_come_first_even_when_the_llm_fails(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [], open_error=httpx.ConnectError("vLLM 연결 실패"))
    book = SimpleNamespace(title="노년", personal_author=None, corporate_author=None, pub_date=None, publisher=None,
                           kdc=None, subject=None, keyword="우울; 노년", summary=None, plot=None)

    events = _events(_run(pipeline, book=book))

    assert events == [{"keywords": ["우울", "노년"]}, {"error": pipeline.REASON_STREAM_ERROR}]


def test_a_finished_stream_has_no_error_event(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [_delta("#KW: 우울\n"), _delta("추천 이유입니다.\n###EFFECT###\n"),
                                      _delta("읽고 난 후입니다."), "data: [DONE]"])

    chunks = _run(pipeline)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    events = _events(chunks)
    assert not any("error" in e for e in events)
    assert {"effect": "읽고 난 후입니다."} in events
