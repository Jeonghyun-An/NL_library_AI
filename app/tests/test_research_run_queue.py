"""test_research_run_queue.py — 딥리서치 대기 순번(Redis ZSET research:run_queue)

run_queue 는 redis 를 함수 안에서만 import 한다 — 로컬 venv 에 redis 가 없어도 이 파일이
수집된다. Redis 를 부르는 함수는 클라이언트 생성기(_async_client·_sync_client)를 대역으로
바꿔 보낸 명령을 기록하고, 순번·예상 시간 계산은 순수 함수라 직접 부른다.
"""
import asyncio
import sys
import types
import uuid

import pytest

from services.research import run_queue


class _FakeAsyncRedis:
    def __init__(self, *, fail: Exception | None = None, rank=None):
        self.calls: list[tuple] = []
        self.closed = 0
        self.fail = fail
        self.rank = rank

    async def zadd(self, key, mapping, nx=False):
        self.calls.append(("zadd", key, mapping, nx))
        if self.fail:
            raise self.fail

    async def zrem(self, key, *members):
        self.calls.append(("zrem", key, members))
        if self.fail:
            raise self.fail

    async def zrank(self, key, member):
        self.calls.append(("zrank", key, member))
        if self.fail:
            raise self.fail
        return self.rank

    async def aclose(self):
        self.closed += 1


class _FakeSyncRedis:
    def __init__(self, *, fail: Exception | None = None):
        self.calls: list[tuple] = []
        self.closed = 0
        self.fail = fail

    def zrem(self, key, *members):
        self.calls.append(("zrem", key, members))
        if self.fail:
            raise self.fail

    def close(self):
        self.closed += 1


def _use(monkeypatch, client) -> None:
    monkeypatch.setattr(run_queue, "_async_client", lambda: client)


class TestMarkWaiting:
    def test_adds_the_job_with_the_time_it_entered_the_line(self, monkeypatch):
        client = _FakeAsyncRedis()
        _use(monkeypatch, client)
        monkeypatch.setattr(run_queue, "_now", lambda: 1_790_000_000.5)
        jid = uuid.uuid4()

        asyncio.run(run_queue.mark_waiting(jid))

        # NX — 재전송된 승인이 자리를 뒤로 미루지 않는다
        assert client.calls == [("zadd", "research:run_queue", {str(jid): 1_790_000_000.5}, True)]
        assert client.closed == 1

    def test_redis_failure_is_swallowed_and_the_client_closed(self, monkeypatch, caplog):
        client = _FakeAsyncRedis(fail=ConnectionError("redis down"))
        _use(monkeypatch, client)

        asyncio.run(run_queue.mark_waiting(uuid.uuid4()))       # 예외가 나오지 않는다

        assert client.closed == 1
        assert any("redis down" in r.getMessage() for r in caplog.records)

    def test_client_creation_failure_is_swallowed(self, monkeypatch):
        def _broken():
            raise ConnectionError("no route")

        monkeypatch.setattr(run_queue, "_async_client", _broken)
        asyncio.run(run_queue.mark_waiting(uuid.uuid4()))


class TestUnmark:
    def test_removes_the_job(self, monkeypatch):
        client = _FakeAsyncRedis()
        _use(monkeypatch, client)
        jid = uuid.uuid4()

        asyncio.run(run_queue.unmark(jid))

        assert client.calls == [("zrem", "research:run_queue", (str(jid),))]
        assert client.closed == 1

    def test_redis_failure_is_swallowed(self, monkeypatch):
        client = _FakeAsyncRedis(fail=ConnectionError("redis down"))
        _use(monkeypatch, client)

        asyncio.run(run_queue.unmark(uuid.uuid4()))

        assert client.closed == 1


class TestRankOf:
    def test_returns_the_number_of_jobs_ahead_in_the_line(self, monkeypatch):
        client = _FakeAsyncRedis(rank=2)
        _use(monkeypatch, client)
        jid = uuid.uuid4()

        assert asyncio.run(run_queue.rank_of(jid)) == 2
        assert client.calls == [("zrank", "research:run_queue", str(jid))]
        assert client.closed == 1

    def test_job_not_in_the_line_is_none(self, monkeypatch):
        _use(monkeypatch, _FakeAsyncRedis(rank=None))
        assert asyncio.run(run_queue.rank_of(uuid.uuid4())) is None

    def test_redis_failure_is_none(self, monkeypatch):
        """Redis 가 죽어도 잡 조회는 돈다 — 순번만 created_at 순 근사로 물러난다."""
        _use(monkeypatch, _FakeAsyncRedis(fail=ConnectionError("redis down")))
        assert asyncio.run(run_queue.rank_of(uuid.uuid4())) is None


class TestUnmarkManySync:
    def test_removes_all_given_jobs_in_one_command(self, monkeypatch):
        client = _FakeSyncRedis()
        monkeypatch.setattr(run_queue, "_sync_client", lambda: client)
        a, b = uuid.uuid4(), uuid.uuid4()

        run_queue.unmark_many_sync([a, str(b)])

        assert client.calls == [("zrem", "research:run_queue", (str(a), str(b)))]
        assert client.closed == 1

    def test_nothing_to_remove_does_not_connect(self, monkeypatch):
        def _never():
            raise AssertionError("빈 목록에 연결했다")

        monkeypatch.setattr(run_queue, "_sync_client", _never)
        run_queue.unmark_many_sync([])

    def test_redis_failure_is_swallowed(self, monkeypatch):
        client = _FakeSyncRedis(fail=ConnectionError("redis down"))
        monkeypatch.setattr(run_queue, "_sync_client", lambda: client)

        run_queue.unmark_many_sync([uuid.uuid4()])

        assert client.closed == 1


class TestClients:
    """응답 없는 Redis 는 예외가 아니라 무기한 대기다 — 잡 조회(GET)가 거기에 묶이면 안 된다."""

    def test_async_client_has_socket_timeouts(self, monkeypatch):
        seen = {}
        aioredis = types.ModuleType("redis.asyncio")
        aioredis.from_url = lambda url, **kw: seen.update(url=url, **kw) or "client"
        redis_mod = types.ModuleType("redis")
        redis_mod.asyncio = aioredis
        monkeypatch.setitem(sys.modules, "redis", redis_mod)
        monkeypatch.setitem(sys.modules, "redis.asyncio", aioredis)

        assert run_queue._async_client() == "client"
        assert seen["socket_timeout"] == seen["socket_connect_timeout"] == run_queue.REDIS_TIMEOUT
        assert seen["url"] == run_queue.get_settings().REDIS_URL

    def test_sync_client_has_socket_timeouts(self, monkeypatch):
        seen = {}

        class _Redis:
            @classmethod
            def from_url(cls, url, **kw):
                seen.update(url=url, **kw)
                return "client"

        redis_mod = types.ModuleType("redis")
        redis_mod.Redis = _Redis
        monkeypatch.setitem(sys.modules, "redis", redis_mod)

        assert run_queue._sync_client() == "client"
        assert seen["socket_timeout"] == seen["socket_connect_timeout"] == run_queue.REDIS_TIMEOUT


class TestWaitingAhead:
    def test_running_jobs_plus_rank(self):
        assert run_queue.waiting_ahead(1, 2, fallback_ahead=7) == 3

    def test_rank_zero_is_a_real_rank(self):
        assert run_queue.waiting_ahead(0, 0, fallback_ahead=5) == 0

    def test_missing_rank_uses_the_created_at_fallback(self):
        assert run_queue.waiting_ahead(1, None, fallback_ahead=4) == 5


class TestEta:
    """예상 시간은 시작까지 기다리는 시간이다 — 화면 문구 '앞에 N건 · 약 M분'."""

    @pytest.mark.parametrize("ahead, median, expected", [
        (0, 100.0, 0),          # 바로 다음 차례 — 기다릴 앞 잡이 없다
        (2, 100.0, 200),        # 내 잡의 실행 시간은 더하지 않는다
        (1, 90.6, 91),          # 버리지 않고 반올림
    ])
    def test_ahead_times_median(self, ahead, median, expected):
        assert run_queue.eta_seconds(ahead, median) == expected

    def test_no_median_means_no_eta(self):
        assert run_queue.eta_seconds(3, None) is None


class TestMedian:
    def test_odd_and_even(self):
        assert run_queue.median_seconds([300.0, 100.0, 200.0]) == 200.0
        assert run_queue.median_seconds([100.0, 200.0, 300.0, 400.0]) == 250.0

    def test_empty_is_none(self):
        assert run_queue.median_seconds([]) is None

    def test_negative_durations_are_ignored(self):
        """시계가 어긋난 행(finished < started)이 중앙값을 끌어내리지 않는다."""
        assert run_queue.median_seconds([-50.0, 120.0]) == 120.0
        assert run_queue.median_seconds([-1.0]) is None
