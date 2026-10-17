"""test_milvus_search_timeout.py — 검색 경로 Milvus 호출의 시간 한도(cfg.MILVUS_SEARCH_TIMEOUT, 기본 20초).

Milvus 가 운영 중 죽으면 pymilvus 기본 재시도(75회, time.sleep 을 섞어 약 3.5분)가 이벤트 루프에서 돌아, 503 이 화면에
닿기 전에 화면이 먼저 끊고 그동안 fastapi 전체가 멈췄다. 이제 indexer.search_chunks 는 개수 읽기·hybrid_search 에 정수
timeout 을 넘긴다 — pymilvus 2.4.6 의 retry_on_rpc_failure 는 정수 timeout 일 때만 그것을 재시도 전체 시간 한도로 쓴다
(운영 이미지 소스로 확인). 한도를 넘기면 지금처럼 MilvusException(grpc UNAVAILABLE) 으로 끝나 503 search_unavailable·
DeepRead retrieval_failed 로 간다. 대량 적재(index_chunks)의 쓰기 호출에는 걸지 않는다.

pymilvus·grpc 가 없는 환경(로컬 venv)에서는 importorskip 으로 건너뛴다 — 운영 이미지(docker run …)에서 돈다.
"""
import asyncio
import importlib
import inspect
import json
import types

import pytest

from core.config import Settings
from core.errors import ApiError, SEARCH_UNAVAILABLE_DETAIL, is_search_outage, search_outage_as_503
from milvus_errors import milvus_retry_timeout_error


@pytest.fixture
def indexer():
    pytest.importorskip("pymilvus")
    return importlib.import_module("services.ingestion.indexer")


class _Conn:
    """Collection._get_connection() 대역 — get_collection_stats 가 받은 timeout 을 적는다."""

    def __init__(self, rows: int):
        self.rows = rows
        self.calls: list[dict] = []

    def get_collection_stats(self, collection_name, timeout=None, **kwargs):
        self.calls.append({"collection_name": collection_name, "timeout": timeout, **kwargs})
        return [types.SimpleNamespace(key="row_count", value=str(self.rows))]


class _Collection:
    """검색이 쓰는 만큼만 흉내 낸 컬렉션 — hybrid_search 가 받은 인자를 적는다."""

    name = "nl_lib_embeddings"

    def __init__(self, rows: int = 3):
        self.conn = _Conn(rows)
        self.searches: list[dict] = []

    def _get_connection(self):
        return self.conn

    def hybrid_search(self, **kwargs):
        self.searches.append(kwargs)
        return [[]]


def _search(indexer, monkeypatch, col: _Collection):
    monkeypatch.setattr(indexer, "ensure_collection", lambda: col)
    return indexer.search_chunks([0.0] * 4, {1: 0.5}, top_k=5, book_filter="KCI_1")


def test_the_setting_is_an_int_20_seconds_and_env_tunable(monkeypatch):
    monkeypatch.delenv("MILVUS_SEARCH_TIMEOUT", raising=False)
    assert Settings().MILVUS_SEARCH_TIMEOUT == 20
    monkeypatch.setenv("MILVUS_SEARCH_TIMEOUT", "7")
    tuned = Settings().MILVUS_SEARCH_TIMEOUT
    assert tuned == 7 and isinstance(tuned, int)


def test_search_chunks_passes_the_int_timeout_to_every_milvus_call(indexer, monkeypatch):
    col = _Collection(rows=3)

    assert _search(indexer, monkeypatch, col) == []

    assert col.conn.calls == [{"collection_name": "nl_lib_embeddings", "timeout": 20}]
    assert len(col.searches) == 1 and col.searches[0]["timeout"] == 20
    assert all(type(c["timeout"]) is int for c in [*col.conn.calls, *col.searches])


def test_an_empty_collection_stops_after_the_count_which_also_has_the_timeout(indexer, monkeypatch):
    col = _Collection(rows=0)

    assert _search(indexer, monkeypatch, col) == []

    assert col.conn.calls[0]["timeout"] == 20
    assert col.searches == []


def test_without_the_private_connection_method_the_count_falls_back_to_num_entities(indexer, monkeypatch):
    # _get_connection 은 pymilvus 비공개 메서드 — 판이 바뀌어 없어져도 검색은 예전처럼(한도 없는 num_entities) 돈다
    class _NewerCollection:
        name = "nl_lib_embeddings"
        num_entities = 0

    assert indexer._entity_count(_NewerCollection(), 20) == 0
    _NewerCollection.num_entities = 4
    assert indexer._entity_count(_NewerCollection(), 20) == 4


def test_the_timeout_follows_the_setting_and_stays_an_int(indexer, monkeypatch):
    # 실수가 들어와도 정수로 넘긴다 — pymilvus 는 실수 timeout 이면 재시도 시간 한도로 쓰지 않는다
    monkeypatch.setattr(indexer.cfg, "MILVUS_SEARCH_TIMEOUT", 5)
    col = _Collection()
    _search(indexer, monkeypatch, col)
    assert col.searches[0]["timeout"] == 5

    monkeypatch.setattr(indexer.cfg, "MILVUS_SEARCH_TIMEOUT", 2.7)
    assert indexer.search_timeout() == 2 and type(indexer.search_timeout()) is int
    monkeypatch.setattr(indexer.cfg, "MILVUS_SEARCH_TIMEOUT", 0)
    assert indexer.search_timeout() == 1


def test_the_bulk_ingest_write_path_has_no_timeout(indexer):
    # 대량 적재 쓰기(delete·insert)는 느려도 끝나야 한다 — 검색 한도를 걸지 않는다
    source = inspect.getsource(indexer.index_chunks)
    assert "timeout" not in source and "search_timeout" not in source


def test_an_int_timeout_bounds_pymilvus_retries_and_ends_as_a_search_outage():
    # Milvus 가 죽은 것처럼 계속 UNAVAILABLE 로 끝나는 호출 — 기본 재시도(75회)라면 약 3.5분이지만 정수 timeout 이면 그 안에 끝난다
    exc, elapsed = milvus_retry_timeout_error("UNAVAILABLE", 1)

    exceptions = pytest.importorskip("pymilvus.exceptions")
    assert isinstance(exc, exceptions.MilvusException)
    assert "Retry timeout: 1s" in str(exc)
    # 마지막 백오프(최대 3초) 한 번까지 넉넉히 — 75회 재시도(분 단위)와는 자릿수가 다르다
    assert elapsed < 6
    assert is_search_outage(exc)

    # 라우트의 검색 가드는 이것을 503 search_unavailable 로 바꾼다(소장자료·논문 검색·관련 자료·상황별 추천)
    with pytest.raises(ApiError) as caught:
        with search_outage_as_503("test"):
            raise exc
    assert caught.value.status_code == 503
    assert caught.value.code == "search_unavailable" and caught.value.detail == SEARCH_UNAVAILABLE_DETAIL


def test_deepread_turns_the_timed_out_search_into_retrieval_failed(monkeypatch):
    # DeepRead(book_chat)는 응답 머리가 이미 나가 503 으로 바꿀 수 없다 — 같은 실패를 retrieval_failed 이벤트로 끝낸다
    exc, _ = milvus_retry_timeout_error("UNAVAILABLE", 1)
    from test_book_chat_prompt import _paper, _stubbed_book_chat

    gen = _stubbed_book_chat(monkeypatch)
    book_chat = next(gen)
    try:
        def embed_texts(texts, is_query=False):
            return [[0.0]], [{}]

        def search_chunks(*args, **kwargs):
            raise exc

        monkeypatch.setattr(book_chat, "embed_texts", embed_texts)
        monkeypatch.setattr(book_chat, "search_chunks", search_chunks)

        async def collect():
            return [c async for c in book_chat.stream_book_chat("KCI_1", "대상은?", [], book=_paper())]

        chunks = [c for c in asyncio.run(collect()) if not c.startswith(":")]
        events = [json.loads(c[len("data: "):]) for c in chunks if c != "data: [DONE]\n\n"]
        assert events == [{"error": book_chat.CHAT_RETRIEVAL_ERROR, "code": "retrieval_failed"}]
        assert chunks[-1] == "data: [DONE]\n\n"
    finally:
        next(gen, None)
