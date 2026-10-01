"""llm_client.chat_full — 재시도·백오프·finish_reason 단위 테스트.

실제 LLM 은 부르지 않는다. llm_client 가 만드는 httpx.AsyncClient 에 MockTransport 를
끼워 응답(또는 예외)을 순서대로 돌려주고, asyncio.sleep 을 기록용 가짜로 바꿔 백오프
간격을 실제로 기다리지 않고 확인한다. 시간은 가짜 시계(llm_client._monotonic)로 고정해
기다린 시간(sleeps)과 요청이 쓴 시간(Took)만큼만 흐르게 한다 — 재시도가 호출자의
timeout 안에 들어가는지를 초 단위로 정확히 확인하려는 것이다.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace

import httpx
import pytest

from services import llm_client


def _ok(content: str = "응답", finish_reason: str | None = "stop") -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
    })


@dataclass
class Took:
    """server.queue 항목 — 가짜 시계를 seconds 만큼 흘린 뒤 outcome(응답 또는 예외)을 낸다."""
    seconds: float
    outcome: httpx.Response | Exception


@pytest.fixture
def clock(monkeypatch):
    """llm_client 의 시계(_monotonic)를 고정한다. 시간은 sleeps 의 대기와 Took 항목만 흘린다."""
    state = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(llm_client, "_monotonic", lambda: state.now)
    return state


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
def server(monkeypatch, clock):
    """queue 에 넣은 응답·예외를 요청마다 하나씩 꺼낸다.

    calls 에 (url, body), timeouts 에 시도마다 httpx 클라이언트에 준 timeout 을 쌓는다.
    """
    state = SimpleNamespace(queue=[], calls=[], timeouts=[])

    def handler(request: httpx.Request) -> httpx.Response:
        state.calls.append((str(request.url), json.loads(request.content)))
        item = state.queue.pop(0)
        if isinstance(item, Took):
            clock.now += item.seconds
            item = item.outcome
        if isinstance(item, Exception):
            raise item
        return item

    real_client = httpx.AsyncClient

    def client_with_mock_transport(*args, **kwargs):
        state.timeouts.append(kwargs.get("timeout"))
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", client_with_mock_transport)
    return state


@pytest.fixture
def sleeps(monkeypatch, clock):
    waited: list[float] = []

    async def fake_sleep(seconds):
        waited.append(seconds)
        clock.now += seconds                 # 기다린 만큼 시계도 흐른다

    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)
    return waited


@pytest.fixture
def fresh_schedule_cache():
    """백오프 설정 문자열은 한 번만 해석·경고한다(캐시) — 테스트 순서에 흔들리지 않게 비운다."""
    llm_client._parse_backoff_schedule.cache_clear()
    yield
    llm_client._parse_backoff_schedule.cache_clear()


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
    lambda: httpx.ReadError(""),                       # 서버 재기동·RST — 처리 중이던 요청은 빈 메시지로 끊긴다
    lambda: httpx.WriteError("쓰기 도중 끊김"),
    lambda: httpx.ReadTimeout("읽기 시간 초과"),
    lambda: httpx.RemoteProtocolError("서버가 연결을 끊음"),
    lambda: httpx.Response(429, text="too many"),
    lambda: httpx.Response(503, text="busy"),
], ids=["connect", "read_error", "write_error", "timeout", "protocol", "429", "503"])
def test_transient_failures_are_retried_with_backoff(cfg, server, sleeps, make_failure):
    server.queue.extend([make_failure(), make_failure(), _ok("세 번째에 성공")])

    result = asyncio.run(llm_client.chat_full(MESSAGES))

    assert result.content == "세 번째에 성공"
    assert len(server.calls) == 3
    assert sleeps == [2.0, 8.0]


@pytest.mark.parametrize("make_failure", [
    lambda: httpx.UnsupportedProtocol("주소에 http(s) 가 없다"),
    lambda: httpx.LocalProtocolError("요청을 만들지 못함"),
], ids=["unsupported_protocol", "local_protocol"])
def test_other_transport_errors_are_not_retried(cfg, server, sleeps, make_failure):
    """TransportError 전체가 아니라 네트워크 오류·타임아웃·연결 끊김만 재시도한다."""
    server.queue.append(make_failure())

    with pytest.raises(httpx.TransportError):
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert len(server.calls) == 1 and sleeps == []


def test_gives_up_after_attempts_and_raises_last_error(cfg, server, sleeps):
    server.queue.extend([httpx.ConnectError("1"), httpx.ConnectError("2"), httpx.ReadTimeout("3")])

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert len(server.calls) == 3
    assert sleeps == [2.0, 8.0]          # 마지막 실패 뒤에는 기다리지 않는다


def test_gives_up_on_5xx_after_attempts_and_raises_status_error(cfg, server, sleeps):
    server.queue.extend([httpx.Response(503, text="busy") for _ in range(3)])

    with pytest.raises(httpx.HTTPStatusError) as exc:
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert exc.value.response.status_code == 503
    assert len(server.calls) == 3
    assert sleeps == [2.0, 8.0]


@pytest.mark.parametrize("status", [400, 401, 404, 422])
def test_other_4xx_raise_immediately(cfg, server, sleeps, status):
    server.queue.append(httpx.Response(status, text="bad request"))

    with pytest.raises(httpx.HTTPStatusError) as exc:
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert exc.value.response.status_code == status
    assert len(server.calls) == 1
    assert sleeps == []


def test_retried_status_errors_warn_and_only_the_final_failure_is_error(cfg, server, sleeps, caplog):
    server.queue.extend([httpx.Response(503, text="busy") for _ in range(3)])

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(llm_client.chat_full(MESSAGES))

    records = [r for r in caplog.records if r.name == llm_client.log.name]
    assert [r.levelno for r in records] == [logging.WARNING, logging.WARNING, logging.ERROR]
    assert "1/3" in records[0].getMessage() and "3/3" in records[2].getMessage()


def test_status_error_that_recovers_logs_no_error(cfg, server, sleeps, caplog):
    server.queue.extend([httpx.Response(429, text="slow down"), _ok("회복")])

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        result = asyncio.run(llm_client.chat_full(MESSAGES))

    assert result.content == "회복"
    records = [r for r in caplog.records if r.name == llm_client.log.name]
    assert [r.levelno for r in records] == [logging.WARNING]


def test_non_retryable_status_is_logged_as_error(cfg, server, sleeps, caplog):
    server.queue.append(httpx.Response(400, text="bad request"))

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(llm_client.chat_full(MESSAGES))

    records = [r for r in caplog.records if r.name == llm_client.log.name]
    assert [r.levelno for r in records] == [logging.ERROR]


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


# ── 재시도 전체가 호출자의 timeout 안에 들어간다 ────────────────────────────────
# deadline = 시작 + timeout. 시도마다 httpx timeout 은 min(timeout, 남은 시간)이고, 실패 뒤
# 남은 시간 <= 다음 백오프 + 1초이면 재시도하지 않고 마지막 예외를 그대로 올린다.

def test_read_timeout_that_uses_the_whole_timeout_is_not_retried(cfg, server, sleeps):
    """응답 없이 붙잡는 장애는 예전처럼 timeout 한 번으로 끝난다 — 재시도로 지연이 3배가 되지 않는다."""
    server.queue.append(Took(120.0, httpx.ReadTimeout("응답 없음")))

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(llm_client.chat_full(MESSAGES, timeout=120.0))

    assert len(server.calls) == 1
    assert sleeps == []
    assert server.timeouts == [120.0]


def test_fast_failures_are_retried_inside_the_time_budget(cfg, server, sleeps):
    server.queue.extend([
        Took(0.5, httpx.Response(503, text="busy")),
        Took(0.5, httpx.ConnectError("연결 리셋")),
        _ok("회복"),
    ])

    result = asyncio.run(llm_client.chat_full(MESSAGES, timeout=30.0))

    assert result.content == "회복"
    assert len(server.calls) == 3
    assert sleeps == [2.0, 8.0]


def test_each_attempt_timeout_shrinks_to_the_remaining_time(cfg, server, sleeps):
    server.queue.extend([
        Took(5.0, httpx.Response(503, text="busy")),     # 5초 씀 → 2초 쉼 → 시작 후 7초
        Took(1.0, httpx.Response(503, text="busy")),     # 1초 씀 → 8초 쉼 → 시작 후 16초
        _ok("회복"),
    ])

    asyncio.run(llm_client.chat_full(MESSAGES, timeout=20.0))

    assert server.timeouts == [20.0, 13.0, 4.0]          # 20 - 0, 20 - 7, 20 - 16
    assert sleeps == [2.0, 8.0]


def test_stops_when_remaining_time_cannot_cover_the_next_backoff(cfg, server, sleeps):
    """timeout 이 짧으면 두 번째 백오프(8초)를 기다릴 시간이 없어 멈춘다 — 마지막 시도의 예외 그대로."""
    server.queue.extend([httpx.Response(503, text="첫째"), httpx.Response(503, text="둘째"), _ok()])

    with pytest.raises(httpx.HTTPStatusError) as exc:
        asyncio.run(llm_client.chat_full(MESSAGES, timeout=10.0))

    assert exc.value.response.text == "둘째"
    assert len(server.calls) == 2                        # 세 번째 시도는 없다
    assert sleeps == [2.0]
    assert server.timeouts == [10.0, 8.0]


def test_retries_when_remaining_is_more_than_backoff_plus_one_second(cfg, server, sleeps):
    server.queue.extend([Took(12.5, httpx.Response(503, text="busy")), _ok("회복")])   # 남은 3.5초 > 2 + 1

    result = asyncio.run(llm_client.chat_full(MESSAGES, timeout=16.0))

    assert result.content == "회복"
    assert sleeps == [2.0]
    assert server.timeouts == [16.0, 1.5]


def test_does_not_retry_when_remaining_equals_backoff_plus_one_second(cfg, server, sleeps):
    server.queue.extend([Took(13.0, httpx.Response(503, text="busy")), _ok("안 쓴다")])   # 남은 3.0초 == 2 + 1

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(llm_client.chat_full(MESSAGES, timeout=16.0))

    assert len(server.calls) == 1 and sleeps == []


@pytest.mark.parametrize("schedule, retry_no, expected", [
    ("2,8", 1, 2.0),
    ("2,8", 2, 8.0),
    ("2,8", 5, 8.0),
    (" 5 ", 3, 5.0),
    ("", 1, 0.0),
    ("x,3", 1, 3.0),
    ("nan,3", 1, 3.0),                  # nan 도 숫자가 아닌 칸처럼 건너뛴다
    ("2,8,", 3, 8.0),                   # 끝 쉼표(빈 칸)는 그냥 건너뛴다
    ("-3,8", 1, 0.0),                   # 음수는 0
    ("2,inf", 2, 60.0),                 # 무한대·과대값은 칸마다 60초로 줄인다
    ("2,9999", 2, 60.0),
    ("60,8", 1, 60.0),                  # 60초 자체는 그대로
])
def test_backoff_delay_parsing(schedule, retry_no, expected):
    assert llm_client._backoff_delay(schedule, retry_no) == expected


def test_backoff_warns_once_per_schedule_about_non_numeric_tokens(fresh_schedule_cache, caplog):
    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        delays = [llm_client._backoff_delay("2,x,8", n) for n in (1, 2, 3)]
        llm_client._backoff_delay("5,y", 1)

    assert delays == [2.0, 8.0, 8.0]
    warned = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warned) == 2                              # 같은 설정 문자열은 한 번, 다른 문자열은 따로
    assert "'2,x,8'" in warned[0] and "'x'" in warned[0]
    assert "'5,y'" in warned[1]


def test_backoff_reports_values_that_were_capped(fresh_schedule_cache, caplog):
    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        assert llm_client._backoff_delay("2,inf", 2) == 60.0
        assert llm_client._backoff_delay("2,inf", 1) == 2.0

    warned = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warned) == 1
    assert "'inf'" in warned[0] and "60" in warned[0]


@pytest.mark.parametrize("schedule", ["2,8", "", "2,8,", " 5 ", "0,60"])
def test_backoff_valid_schedules_log_nothing(fresh_schedule_cache, caplog, schedule):
    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        llm_client._backoff_delay(schedule, 1)

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
