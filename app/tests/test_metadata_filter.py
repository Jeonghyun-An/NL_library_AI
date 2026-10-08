"""metadata_filter.extract_metadata_filter — gemma(vLLM)에 보내는 요청 본문 모양 단위 테스트.

실제 LLM 은 부르지 않는다. metadata_filter 가 만드는 httpx.AsyncClient 에 MockTransport 를
끼워 요청 본문을 기록하고, 준비한 응답을 돌려준다.

출력 제약은 OpenAI 표준 response_format(json_schema)으로 보낸다. 예전 guided_json 은
vLLM v0.12.0 에서 빠졌고, 운영 이미지(v0.20.0)는 모르는 필드를 400 없이 받아 debug 로그만
남기고 버린다 — 제약이 걸리지 않아도 응답은 정상이라 겉으로는 드러나지 않는다.
"""
import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from services.search import metadata_filter
from services.search.metadata_filter import MetadataFilter

# 옛 guided_json 과 같은 스키마 — 바꾼 것은 싣는 자리뿐이다.
SCHEMA = {
    "type": "object",
    "properties": {
        "pub_year_from": {"type": ["integer", "null"]},
        "pub_year_to": {"type": ["integer", "null"]},
        "sort_by": {"type": ["string", "null"], "enum": ["recent", "oldest", None]},
        "has_filter": {"type": "boolean"},
    },
    "required": ["pub_year_from", "pub_year_to", "sort_by", "has_filter"],
    "additionalProperties": False,
}


def _ok(content: str) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
    })


@pytest.fixture
def cfg(monkeypatch):
    settings = metadata_filter.get_settings()
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    return settings


@pytest.fixture
def server(monkeypatch):
    """queue 의 응답을 요청마다 하나씩 꺼내고, calls 에 (url, body) 를 쌓는다."""
    state = SimpleNamespace(queue=[], calls=[])

    def handler(request: httpx.Request) -> httpx.Response:
        state.calls.append((str(request.url), json.loads(request.content)))
        return state.queue.pop(0)

    real_client = httpx.AsyncClient

    def client_with_mock_transport(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(metadata_filter.httpx, "AsyncClient", client_with_mock_transport)
    return state


def test_request_constrains_output_with_response_format_json_schema(cfg, server):
    server.queue.append(_ok(
        '{"pub_year_from": null, "pub_year_to": null, "sort_by": null, "has_filter": false}'))

    asyncio.run(metadata_filter.extract_metadata_filter("최근 책"))

    url, body = server.calls[0]
    assert url == "http://llm.test/v1/chat/completions"
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "metadata_filter", "schema": SCHEMA},
    }
    # vLLM 이 조용히 버리는 옛 필드도, 제약을 두 번 거는 vLLM 전용 필드도 싣지 않는다
    assert not [k for k in body if k.startswith("guided_")]
    assert "structured_outputs" not in body
    assert body["model"] == "gemma-test"
    assert body["max_tokens"] == 128 and body["temperature"] == 0.0
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_constrained_json_becomes_metadata_filter(cfg, server):
    server.queue.append(_ok(
        '{"pub_year_from": 2020, "pub_year_to": null, "sort_by": "recent", "has_filter": true}'))

    result = asyncio.run(metadata_filter.extract_metadata_filter("2020년 이후 최신 책"))

    assert result == MetadataFilter(
        pub_year_from=2020, pub_year_to=None, sort_by="recent", has_filter=True)


def test_server_rejecting_schema_falls_back_to_no_filter_with_warning(cfg, server, caplog):
    """스키마를 서버가 받지 못하면(400) 필터 없이 검색한다 — 대신 경고 로그로 드러난다."""
    server.queue.append(httpx.Response(400, json={"error": {"message": "bad schema"}}))

    with caplog.at_level(logging.WARNING, logger=metadata_filter.log.name):
        result = asyncio.run(metadata_filter.extract_metadata_filter("최근 책"))

    assert result == MetadataFilter()
    assert any("메타데이터 필터 추출 실패" in r.getMessage() for r in caplog.records)
