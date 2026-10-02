"""llm_client.chat_full — 재시도·백오프·finish_reason 단위 테스트.

실제 LLM 은 부르지 않는다. llm_client 가 만드는 httpx.AsyncClient 에 MockTransport 를
끼워 응답(또는 예외)을 순서대로 돌려주고, asyncio.sleep 을 기록용 가짜로 바꿔 백오프
간격을 실제로 기다리지 않고 확인한다. 시간은 가짜 시계(llm_client._monotonic)로 고정해
기다린 시간(sleeps)과 요청이 쓴 시간(Took, Stall)만큼만 흐르게 한다 — 재시도가 호출자의
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


@dataclass
class Stall:
    """server.queue 항목 — 연결이 붙지 않거나('connect') 응답이 오지 않는('read') 장애. 그 요청의 httpx
    timeout 중 해당 칸만큼 가짜 시계를 흘린 뒤 그 칸의 타임아웃 예외를 낸다 — httpx 가 끊는 시점 그대로다."""
    phase: str


@pytest.fixture
def clock(monkeypatch):
    """llm_client 의 시계(_monotonic)를 고정한다. 시간은 sleeps 의 대기와 Took 항목만 흘린다."""
    state = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(llm_client, "_monotonic", lambda: state.now)
    return state


@pytest.fixture
def cfg(monkeypatch):
    """openai 호환 경로 + 재시도 3회(첫 시도 포함)·백오프 2초→8초."""
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

    calls 에 (url, body), timeouts 에 시도마다 httpx 클라이언트에 준 timeout(httpx.Timeout)을 쌓는다.
    """
    state = SimpleNamespace(queue=[], calls=[], timeouts=[])

    def handler(request: httpx.Request) -> httpx.Response:
        state.calls.append((str(request.url), json.loads(request.content)))
        item = state.queue.pop(0)
        if isinstance(item, Took):
            clock.now += item.seconds
            item = item.outcome
        if isinstance(item, Stall):
            clock.now += request.extensions["timeout"][item.phase]
            item = {"connect": httpx.ConnectTimeout, "read": httpx.ReadTimeout}[item.phase](f"{item.phase} 시간 초과")
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


_GIVE_UP_WORDS = ("시도 횟수 소진", "남은 시간 부족")


def _give_up_reasons(record) -> set[str]:
    """로그가 밝힌, 더 시도하지 않는 까닭."""
    return {w for w in _GIVE_UP_WORDS if w in record.getMessage()}


def test_retried_status_errors_warn_and_only_the_final_failure_is_error(cfg, server, sleeps, caplog):
    server.queue.extend([httpx.Response(503, text="busy") for _ in range(3)])

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(llm_client.chat_full(MESSAGES))

    records = [r for r in caplog.records if r.name == llm_client.log.name]
    assert [r.levelno for r in records] == [logging.WARNING, logging.WARNING, logging.ERROR]
    assert "1/3" in records[0].getMessage() and "3/3" in records[2].getMessage()


@pytest.mark.parametrize("queue, timeout, reason", [
    (lambda: [httpx.Response(503, text="busy") for _ in range(3)], 120.0, "시도 횟수 소진"),
    # 두 번째 백오프(8초) + 1초를 기다릴 시간이 없다 — 시도는 남았지만 멈춘다
    (lambda: [httpx.Response(503, text="첫째"), httpx.Response(503, text="둘째")], 10.0, "남은 시간 부족"),
], ids=["attempts", "deadline"])
def test_final_retryable_status_says_why_it_stopped(cfg, server, sleeps, caplog, queue, timeout, reason):
    server.queue.extend(queue())

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(llm_client.chat_full(MESSAGES, timeout=timeout))

    records = [r for r in caplog.records if r.name == llm_client.log.name]
    assert records[-1].levelno == logging.ERROR and _give_up_reasons(records[-1]) == {reason}
    assert all(r.levelno == logging.WARNING and not _give_up_reasons(r) for r in records[:-1])


@pytest.mark.parametrize("queue, timeout, levels, reason", [
    (lambda: [httpx.ConnectError("1"), httpx.ReadError(""), httpx.ConnectError("3")], 120.0,
     [logging.WARNING, logging.WARNING, logging.ERROR], "시도 횟수 소진"),
    # 응답 없이 timeout 을 다 썼다 — 시도는 남았지만 다음 시도가 deadline 안에 들지 못한다
    (lambda: [Stall("read")], 120.0, [logging.ERROR], "남은 시간 부족"),
], ids=["attempts", "deadline"])
def test_final_network_failure_is_error_with_the_reason(cfg, server, sleeps, caplog, queue, timeout, levels, reason):
    """다시 보낼 네트워크 실패는 경고, 여기서 끝나는 실패만 error — 왜 멈췄는지(횟수·시간)를 남긴다."""
    server.queue.extend(queue())

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        with pytest.raises(httpx.TransportError):
            asyncio.run(llm_client.chat_full(MESSAGES, timeout=timeout))

    records = [r for r in caplog.records if r.name == llm_client.log.name]
    assert [r.levelno for r in records] == levels
    assert _give_up_reasons(records[-1]) == {reason}
    assert not any(_give_up_reasons(r) for r in records[:-1])


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
    assert not _give_up_reasons(records[0])          # 재시도 대상이 아니다 — 횟수·시간 때문에 멈춘 것이 아니다


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
# deadline = 시작 + timeout. 시도마다 httpx 의 읽기·쓰기·풀 timeout 은 남은 시간, 연결 timeout 은
# min(10초, 남은 시간)이고, 실패 뒤 남은 시간 <= 다음 백오프 + 1초이면 재시도하지 않고 마지막 예외를
# 그대로 올린다.

def test_read_timeout_that_uses_the_whole_timeout_is_not_retried(cfg, server, sleeps, clock):
    """응답 없이 붙잡는 장애는 예전처럼 timeout 한 번으로 끝난다 — 재시도로 지연이 3배가 되지 않는다."""
    server.queue.append(Stall("read"))

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(llm_client.chat_full(MESSAGES, timeout=120.0))

    assert len(server.calls) == 1
    assert sleeps == []
    assert server.timeouts == [httpx.Timeout(120.0, connect=10.0)]
    assert clock.now == 1000.0 + 120.0                   # 읽기 timeout 은 남은 시간 전부였다


def test_connect_stall_fails_fast_and_is_retried_within_the_deadline(cfg, server, sleeps, clock):
    """연결이 붙지 않는 장애(vLLM 재기동 중)는 10초에서 끊고 남은 시간 안에서 다시 보낸다 — 연결 timeout 이
    남은 시간 전부면 연결 시도 한 번이 timeout 을 다 써 재시도할 시간이 남지 않는다."""
    server.queue.extend([Stall("connect"), _ok("회복")])

    result = asyncio.run(llm_client.chat_full(MESSAGES, timeout=120.0))

    assert result.content == "회복"
    assert len(server.calls) == 2 and sleeps == [2.0]
    # 10초 끊김 → 2초 쉼 → 시작 후 12초에 두 번째 시도
    assert server.timeouts == [httpx.Timeout(120.0, connect=10.0), httpx.Timeout(108.0, connect=10.0)]
    assert clock.now == 1000.0 + 12.0


def test_connect_stalls_are_retried_until_the_attempts_run_out(cfg, server, sleeps):
    server.queue.extend([Stall("connect"), Stall("connect"), Stall("connect")])

    with pytest.raises(httpx.ConnectTimeout):
        asyncio.run(llm_client.chat_full(MESSAGES, timeout=120.0))

    assert len(server.calls) == 3 and sleeps == [2.0, 8.0]


@pytest.mark.parametrize("style, response", [
    ("openai", lambda: _ok()),
    ("ollama", lambda: httpx.Response(200, json={"message": {"content": "응답"}, "done": True})),
])
def test_client_connect_timeout_is_ten_seconds_at_most(cfg, server, sleeps, monkeypatch, style, response):
    monkeypatch.setattr(cfg, "LLM_API_STYLE", style)
    server.queue.extend([response(), response()])

    asyncio.run(llm_client.chat_full(MESSAGES, timeout=120.0))
    asyncio.run(llm_client.chat_full(MESSAGES, timeout=5.0))

    # 남은 시간이 10초보다 짧으면 연결 timeout 도 남은 시간
    assert server.timeouts == [httpx.Timeout(120.0, connect=10.0), httpx.Timeout(5.0, connect=5.0)]


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

    assert server.timeouts == [                          # 20 - 0, 20 - 7, 20 - 16 (연결은 10초까지)
        httpx.Timeout(20.0, connect=10.0), httpx.Timeout(13.0, connect=10.0), httpx.Timeout(4.0, connect=4.0),
    ]
    assert sleeps == [2.0, 8.0]


def test_stops_when_remaining_time_cannot_cover_the_next_backoff(cfg, server, sleeps):
    """timeout 이 짧으면 두 번째 백오프(8초)를 기다릴 시간이 없어 멈춘다 — 마지막 시도의 예외 그대로."""
    server.queue.extend([httpx.Response(503, text="첫째"), httpx.Response(503, text="둘째"), _ok()])

    with pytest.raises(httpx.HTTPStatusError) as exc:
        asyncio.run(llm_client.chat_full(MESSAGES, timeout=10.0))

    assert exc.value.response.text == "둘째"
    assert len(server.calls) == 2                        # 세 번째 시도는 없다
    assert sleeps == [2.0]
    assert server.timeouts == [httpx.Timeout(10.0, connect=10.0), httpx.Timeout(8.0, connect=8.0)]


def test_retries_when_remaining_is_more_than_backoff_plus_one_second(cfg, server, sleeps):
    server.queue.extend([Took(12.5, httpx.Response(503, text="busy")), _ok("회복")])   # 남은 3.5초 > 2 + 1

    result = asyncio.run(llm_client.chat_full(MESSAGES, timeout=16.0))

    assert result.content == "회복"
    assert sleeps == [2.0]
    assert server.timeouts == [httpx.Timeout(16.0, connect=10.0), httpx.Timeout(1.5, connect=1.5)]


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


# ── 호출별 엔드포인트(round06a) — 연구 어시스턴트가 생성마다 Qwen·gemma 를 고른다 ─────────────────
# base_url·model 을 주지 않으면(None) 지금처럼 LLM_BASE_URL·LLM_MODEL 이다. 기존 호출부는 넘기지 않는다.

QWEN_URL, QWEN_MODEL = "http://qwen.test/v1", "qwen-test"


def _sse(*deltas: str) -> httpx.Response:
    """openai 호환 스트리밍 응답(SSE) — 델타마다 data 줄 하나, 끝에 [DONE]."""
    lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": d}}]}, ensure_ascii=False)
        for d in deltas
    ]
    return httpx.Response(200, content=("\n\n".join([*lines, "data: [DONE]"]) + "\n\n").encode())


def _ndjson(*deltas: str) -> httpx.Response:
    """ollama 스트리밍 응답(NDJSON) — 델타마다 한 줄, 끝에 done."""
    lines = [json.dumps({"message": {"content": d}, "done": False}, ensure_ascii=False) for d in deltas]
    lines.append(json.dumps({"message": {"content": ""}, "done": True}))
    return httpx.Response(200, content=("\n".join(lines) + "\n").encode())


def _collect(gen) -> list[str]:
    async def _go():
        return [d async for d in gen]
    return asyncio.run(_go())


def test_chat_full_uses_the_per_call_endpoint(cfg, server, sleeps):
    server.queue.append(_ok("큐웬 응답"))

    result = asyncio.run(llm_client.chat_full(
        MESSAGES, params={"max_tokens": 200}, base_url=QWEN_URL, model=QWEN_MODEL,
    ))

    assert result.content == "큐웬 응답"
    url, body = server.calls[0]
    assert url == "http://qwen.test/v1/chat/completions"
    assert body["model"] == QWEN_MODEL and body["max_tokens"] == 200


def test_explicit_none_keeps_the_configured_endpoint(cfg, server, sleeps):
    server.queue.append(_ok())

    asyncio.run(llm_client.chat_full(MESSAGES, base_url=None, model=None))

    url, body = server.calls[0]
    assert url == "http://llm.test/v1/chat/completions" and body["model"] == "gemma-test"


def test_base_url_and_model_are_independent(cfg, server, sleeps):
    server.queue.extend([_ok(), _ok()])

    asyncio.run(llm_client.chat_full(MESSAGES, base_url=QWEN_URL))
    asyncio.run(llm_client.chat_full(MESSAGES, model=QWEN_MODEL))

    assert [(url, body["model"]) for url, body in server.calls] == [
        ("http://qwen.test/v1/chat/completions", "gemma-test"),
        ("http://llm.test/v1/chat/completions", QWEN_MODEL),
    ]


def test_retries_stay_on_the_per_call_endpoint(cfg, server, sleeps, caplog):
    server.queue.extend([httpx.Response(503, text="busy"), httpx.ConnectError("연결 거부"), _ok("회복")])

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        result = asyncio.run(llm_client.chat_full(MESSAGES, base_url=QWEN_URL, model=QWEN_MODEL))

    assert result.content == "회복" and sleeps == [2.0, 8.0]
    assert {(url, body["model"]) for url, body in server.calls} == {
        ("http://qwen.test/v1/chat/completions", QWEN_MODEL),
    }
    # 재시도 경고(상태 코드·전송 실패)도 부른 모델을 남긴다 — Qwen·gemma 넘김을 워커 로그로 가른다
    warned = [r.getMessage() for r in caplog.records if r.name == llm_client.log.name]
    assert len(warned) == 2
    assert all(f"model={QWEN_MODEL}" in m and "gemma-test" not in m for m in warned)


def test_length_warning_names_the_model_that_was_called(cfg, server, sleeps, caplog):
    server.queue.append(_ok("잘린 응답", "length"))

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        asyncio.run(llm_client.chat_full(
            MESSAGES, params={"max_tokens": 200}, base_url=QWEN_URL, model=QWEN_MODEL,
        ))

    warned = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warned) == 1
    assert f"model={QWEN_MODEL}" in warned[0] and "gemma-test" not in warned[0]


def test_ollama_path_uses_the_per_call_endpoint(cfg, server, sleeps, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_API_STYLE", "ollama")
    server.queue.append(httpx.Response(200, json={"message": {"content": "응답"}, "done": True}))

    asyncio.run(llm_client.chat_full(MESSAGES, base_url="http://ollama2.test:11434/v1", model="qwen3:8b"))

    url, body = server.calls[0]
    assert url == "http://ollama2.test:11434/api/chat" and body["model"] == "qwen3:8b"


def test_chat_passes_the_endpoint_through(cfg, server, sleeps):
    server.queue.append(_ok("본문"))

    assert asyncio.run(llm_client.chat(MESSAGES, base_url=QWEN_URL, model=QWEN_MODEL)) == "본문"
    url, body = server.calls[0]
    assert url == "http://qwen.test/v1/chat/completions" and body["model"] == QWEN_MODEL


def test_chat_stream_defaults_to_the_configured_endpoint(cfg, server):
    server.queue.append(_sse("가", "나"))

    assert _collect(llm_client.chat_stream(MESSAGES, params={"max_tokens": 50})) == ["가", "나"]
    url, body = server.calls[0]
    assert url == "http://llm.test/v1/chat/completions"
    assert body["model"] == "gemma-test" and body["stream"] is True and body["max_tokens"] == 50


def test_chat_stream_uses_the_per_call_endpoint(cfg, server):
    server.queue.append(_sse("절의 ", "첫 문장"))

    deltas = _collect(llm_client.chat_stream(MESSAGES, base_url=QWEN_URL, model=QWEN_MODEL))

    assert deltas == ["절의 ", "첫 문장"]
    url, body = server.calls[0]
    assert url == "http://qwen.test/v1/chat/completions" and body["model"] == QWEN_MODEL


def test_chat_stream_ollama_uses_the_per_call_endpoint(cfg, server, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_API_STYLE", "ollama")
    server.queue.append(_ndjson("가", "나"))

    deltas = _collect(llm_client.chat_stream(
        MESSAGES, base_url="http://ollama2.test:11434/v1", model="qwen3:8b",
    ))

    assert deltas == ["가", "나"]
    url, body = server.calls[0]
    assert url == "http://ollama2.test:11434/api/chat"
    assert body["model"] == "qwen3:8b" and body["stream"] is True


def test_chat_stream_still_does_not_retry(cfg, server, sleeps):
    server.queue.append(httpx.Response(503, text="busy"))

    with pytest.raises(httpx.HTTPStatusError):
        _collect(llm_client.chat_stream(MESSAGES, base_url=QWEN_URL, model=QWEN_MODEL))

    assert len(server.calls) == 1 and sleeps == []
