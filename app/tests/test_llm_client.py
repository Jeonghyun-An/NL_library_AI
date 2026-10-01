"""llm_client.chat_full — 재시도·백오프·finish_reason 단위 테스트.

실제 LLM 은 부르지 않는다. llm_client 가 만드는 httpx.AsyncClient 에 MockTransport 를
끼워 응답(또는 예외)을 순서대로 돌려주고, asyncio.sleep 을 기록용 가짜로 바꿔 백오프
간격을 실제로 기다리지 않고 확인한다.
"""
import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from services import llm_client


def _ok(content: str = "응답", finish_reason: str | None = "stop") -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
    })


@pytest.fixture
def cfg(monkeypatch):
    """openai 호환 경로 + 재시도 3회(첫 시도 포함)·백오프 2초→8초 (Task 0 이 더한 키)."""
    settings = llm_client.get_settings()
    monkeypatch.setattr(settings, "LLM_API_STYLE", "openai")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    monkeypatch.setattr(settings, "LLM_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LLM_RETRY_BACKOFF_SECONDS", "2,8")
    return settings


@pytest.fixture
def server(monkeypatch):
    """queue 에 넣은 응답·예외를 요청마다 하나씩 꺼낸다. calls 에 (url, body) 를 쌓는다."""
    state = SimpleNamespace(queue=[], calls=[])

    def handler(request: httpx.Request) -> httpx.Response:
        state.calls.append((str(request.url), json.loads(request.content)))
        item = state.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    real_client = httpx.AsyncClient

    def client_with_mock_transport(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", client_with_mock_transport)
    return state


@pytest.fixture
def sleeps(monkeypatch):
    waited: list[float] = []

    async def fake_sleep(seconds):
        waited.append(seconds)

    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)
    return waited


MESSAGES = [{"role": "user", "content": "안녕"}]


def test_chat_full_returns_content_and_finish_reason(cfg, server, sleeps):
    server.queue.append(_ok("  요약 결과  ", "stop"))

    result = asyncio.run(llm_client.chat_full(MESSAGES, params={"max_tokens": 50}))

    assert result == llm_client.LLMResult(content="요약 결과", finish_reason="stop")
    url, body = server.calls[0]
    assert url == "http://llm.test/v1/chat/completions"
    assert body["model"] == "gemma-test" and body["max_tokens"] == 50
    assert sleeps == []


def test_chat_keeps_signature_and_returns_content_only(cfg, server, sleeps):
    server.queue.append(_ok("본문", "length"))

    assert asyncio.run(llm_client.chat(MESSAGES, params={"max_tokens": 10})) == "본문"


def test_length_finish_reason_logs_model_and_max_tokens(cfg, server, sleeps, caplog):
    server.queue.append(_ok("잘린 응답", "length"))

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        result = asyncio.run(llm_client.chat_full(MESSAGES, params={"max_tokens": 600}))

    assert result.finish_reason == "length"
    warned = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("gemma-test" in m and "600" in m for m in warned)


def test_ollama_path_reads_done_reason(cfg, server, sleeps, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_API_STYLE", "ollama")
    server.queue.append(httpx.Response(200, json={
        "message": {"content": "올라마 응답"}, "done": True, "done_reason": "length",
    }))
    server.queue.append(httpx.Response(200, json={"message": {"content": "옛 응답"}, "done": True}))

    first = asyncio.run(llm_client.chat_full(MESSAGES))
    second = asyncio.run(llm_client.chat_full(MESSAGES))

    assert first == llm_client.LLMResult(content="올라마 응답", finish_reason="length")
    assert second == llm_client.LLMResult(content="옛 응답", finish_reason=None)
    assert server.calls[0][0] == "http://llm.test/api/chat"


@pytest.mark.parametrize("make_failure", [
    lambda: httpx.ConnectError("연결 거부"),
    lambda: httpx.ReadTimeout("읽기 시간 초과"),
    lambda: httpx.RemoteProtocolError("서버가 연결을 끊음"),
    lambda: httpx.Response(429, text="too many"),
    lambda: httpx.Response(503, text="busy"),
], ids=["connect", "timeout", "protocol", "429", "503"])
def test_transient_failures_are_retried_with_backoff(cfg, server, sleeps, make_failure):
    server.queue.extend([make_failure(), make_failure(), _ok("세 번째에 성공")])

    result = asyncio.run(llm_client.chat_full(MESSAGES))

    assert result.content == "세 번째에 성공"
    assert len(server.calls) == 3
    assert sleeps == [2.0, 8.0]


def test_gives_up_after_attempts_and_raises_last_error(cfg, server, sleeps):
    server.queue.extend([httpx.ConnectError("1"), httpx.ConnectError("2"), httpx.ReadTimeout("3")])

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert len(server.calls) == 3
    assert sleeps == [2.0, 8.0]          # 마지막 실패 뒤에는 기다리지 않는다


@pytest.mark.parametrize("status", [400, 401, 404, 422])
def test_other_4xx_raise_immediately(cfg, server, sleeps, status):
    server.queue.append(httpx.Response(status, text="bad request"))

    with pytest.raises(httpx.HTTPStatusError) as exc:
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert exc.value.response.status_code == status
    assert len(server.calls) == 1
    assert sleeps == []


def test_backoff_repeats_last_value_when_schedule_is_short(cfg, server, sleeps, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_RETRY_ATTEMPTS", 4)
    server.queue.extend([httpx.Response(502), httpx.Response(502), httpx.Response(502), _ok()])

    asyncio.run(llm_client.chat_full(MESSAGES))

    assert sleeps == [2.0, 8.0, 8.0]


def test_single_attempt_means_no_retry(cfg, server, sleeps, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_RETRY_ATTEMPTS", 1)
    server.queue.append(httpx.ConnectError("연결 거부"))

    with pytest.raises(httpx.ConnectError):
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert len(server.calls) == 1 and sleeps == []


@pytest.mark.parametrize("schedule, retry_no, expected", [
    ("2,8", 1, 2.0),
    ("2,8", 2, 8.0),
    ("2,8", 5, 8.0),
    (" 5 ", 3, 5.0),
    ("", 1, 0.0),
    ("x,3", 1, 3.0),
])
def test_backoff_delay_parsing(schedule, retry_no, expected):
    assert llm_client._backoff_delay(schedule, retry_no) == expected
