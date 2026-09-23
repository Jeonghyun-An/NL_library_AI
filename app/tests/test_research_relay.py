"""test_research_relay.py — 진행 중계의 종료 이벤트 모양과 publish 타임아웃

`redis` 는 로컬 venv 에 없다. 미설치일 때만 더미를 꽂고 relay 를 새로 import 한다
(test_research_runner.py 의 _load_relay 와 같은 방식).
"""
import asyncio
import importlib
import json
import sys
import types
import uuid
from urllib.parse import parse_qs, urlsplit
from unittest.mock import MagicMock

import pytest

_RELAY = "services.research.relay"


def _forget_on_teardown(monkeypatch, name: str) -> None:
    """name 을 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 있던 키만 되돌린다. 원래 없던 키는 기록이 남지 않아
    여기서 새로 import 한 모듈(더미 redis 에 묶인 채)이 teardown 뒤에도 남는다.
    setitem·setattr 은 원래 없던 키·속성이면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을
    남긴 뒤 뺀다. 부모 속성까지 되돌리는 이유: `from pkg import mod` 와 문자열 경로
    monkeypatch 는 sys.modules 보다 부모 속성을 먼저 본다.
    """
    parent, _, child = name.rpartition(".")
    monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
    monkeypatch.setitem(sys.modules, name, None)
    del sys.modules[name]


def _load_relay(monkeypatch):
    for name in ("redis", "redis.asyncio"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    _forget_on_teardown(monkeypatch, _RELAY)
    return importlib.import_module(_RELAY)


class _FakeRedis:
    def __init__(self):
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel, data):
        self.published.append((channel, data))

    async def aclose(self):
        return None


class TestTerminalEvent:
    """같은 종료 상태는 연결 시점과 상관없이 한 모양으로 나가야 한다."""

    def test_each_terminal_status_maps_to_one_kind(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        assert relay.terminal_event("completed") == {"kind": "done", "status": "completed"}
        assert relay.terminal_event("canceled") == {"kind": "canceled", "status": "canceled"}
        assert relay.terminal_event("failed", "boom") == {
            "kind": "failed", "status": "failed", "error": "boom",
        }

    def test_every_terminal_status_has_a_kind(self, monkeypatch):
        from models.research import TERMINAL_STATUSES
        relay = _load_relay(monkeypatch)
        assert set(relay.TERMINAL_KIND) == set(TERMINAL_STATUSES)

    def test_error_is_truncated(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        assert len(relay.terminal_event("failed", "x" * 5000)["error"]) == 200

    def test_publish_terminal_sends_the_same_shape(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        client = _FakeRedis()
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)
        jid = uuid.uuid4()

        asyncio.run(relay.publish_terminal(jid, "failed", "종합 실패"))

        channel, data = client.published[0]
        assert channel == f"research:{jid}"
        assert json.loads(data) == relay.terminal_event("failed", "종합 실패")


class TestPublishTimeout:
    """응답 없는 Redis 는 예외가 아니라 hang 이라 삼킬 기회조차 없다 — 소켓 타임아웃이 필요하다."""

    def test_publish_connects_with_socket_timeouts(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        seen = {}

        def _from_url(url):
            seen["url"] = url
            return _FakeRedis()

        monkeypatch.setattr(relay.aioredis, "from_url", _from_url)
        asyncio.run(relay.publish(uuid.uuid4(), "search", {}))

        query = parse_qs(urlsplit(seen["url"]).query)
        assert float(query["socket_timeout"][0]) > 0
        assert float(query["socket_connect_timeout"][0]) > 0

    def test_existing_query_is_kept(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        url = relay._with_timeouts("redis://:pw@redis:6379/0?socket_timeout=9&db=0")
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        assert parts.netloc == ":pw@redis:6379" and parts.path == "/0"
        assert query["socket_timeout"] == ["9"]       # 운영자가 URL 에 준 값은 덮지 않는다
        assert "socket_connect_timeout" in query


class TestChannel:
    def test_uuid_and_its_canonical_string_share_a_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        jid = uuid.uuid4()
        assert relay.channel(jid) == relay.channel(str(jid)) == f"research:{jid}"


class TestLoaderIsolation:
    """_load_relay 가 끝나면 sys.modules·부모 패키지 속성이 import 전 그대로여야 한다.

    더미 redis 에 묶인 relay 가 남으면 뒤에 도는 테스트가 더미 없이 import 해도 그
    Mock 결합 모듈을 물려받는다 — 로컬에서만, 실행 순서에 따라 결과가 달라진다.
    """

    def test_module_that_was_absent_is_gone_afterwards(self):
        parent = importlib.import_module("services.research")
        with pytest.MonkeyPatch.context() as outer:
            outer.delitem(sys.modules, _RELAY, raising=False)
            outer.delattr(parent, "relay", raising=False)
            with pytest.MonkeyPatch.context() as mp:
                _load_relay(mp)
            assert _RELAY not in sys.modules
            assert not hasattr(parent, "relay")

    def test_module_that_was_loaded_comes_back(self):
        parent = importlib.import_module("services.research")
        original = types.ModuleType(_RELAY)
        with pytest.MonkeyPatch.context() as outer:
            outer.setitem(sys.modules, _RELAY, original)
            outer.setattr(parent, "relay", original, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                assert _load_relay(mp) is not original   # 앞 테스트의 모듈을 물려받지 않는다
            assert sys.modules[_RELAY] is original
            assert parent.relay is original
