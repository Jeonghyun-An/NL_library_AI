"""workers/research_work_tasks.py — 생성 디스패치 태스크(spec §6-3).

celery·kombu·redis 는 로컬 venv 에 없다(함정 13). 더미를 꽂고 모듈을 새로 import 하며, 끝나면
import 전 그대로 되돌린다(test_research_tasks.py 의 _load_tasks 와 같은 방식). 태스크 본문은
SQLite 대역(history_sqlite)에서 실제 SQL 로 돌리고, LLM(chat_full)·Redis(publish_work)·브로커
(send_dispatch)만 기록용 가짜로 바꾼다. 이벤트 모양 하나만은 진짜 publish_work(Redis 만 가짜)로 본다.
"""
import asyncio
import importlib
import json
import logging
import sys
import types
from unittest.mock import MagicMock

import httpx
import pytest
import sqlalchemy as sa

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.research_work import ResearchGeneration, ResearchWork
from services.llm_client import LLMResult
from services.research_work import routing

_CACHED = ("workers.research_work_tasks", "workers.celery_app", "services.research.relay")
GEN = ResearchGeneration.__table__
WORK = ResearchWork.__table__
CONCEPTS_INPUT = {"question": "청소년 독서 격차", "subquestions": ["독서 격차의 정의"], "headings": []}
GOOD = '{"concepts": ["독서 격차", "청소년"]}'


class _SoftTimeLimitExceeded(Exception):
    """celery 미설치 환경용 대역 — Celery 의 것도 Exception 의 하위 클래스다."""


class _OperationalError(Exception):
    pass


class _FakeConf:
    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class _FakeCelery:
    """task 데코레이터는 원함수를 돌려주고 옵션을 속성으로 붙인다. send_task 는 기록한다."""

    def __init__(self, *a, **kw):
        self.conf = _FakeConf()
        self.init_kw = kw
        self.sent: list[tuple] = []
        self.fail = False

    def task(self, *a, **kw):
        def _decorator(fn):
            for key, value in kw.items():
                setattr(fn, key, value)
            return fn
        return _decorator

    def send_task(self, name, args=None, **kw):
        if self.fail:
            raise _OperationalError("broker down")
        self.sent.append((name, args, kw))


def _stub_missing(monkeypatch, name: str) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, MagicMock())


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules·부모 패키지 속성에서 빼고 테스트가 끝나면 되돌린다(test_research_tasks.py 와 같다)."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


def _load(monkeypatch):
    celery_mod = types.ModuleType("celery")
    celery_mod.Celery = _FakeCelery
    celery_exc = types.ModuleType("celery.exceptions")
    celery_exc.SoftTimeLimitExceeded = _SoftTimeLimitExceeded
    kombu = types.ModuleType("kombu")
    kombu_exc = types.ModuleType("kombu.exceptions")
    kombu_exc.OperationalError = _OperationalError
    for name, module in (("celery", celery_mod), ("celery.exceptions", celery_exc),
                         ("kombu", kombu), ("kombu.exceptions", kombu_exc)):
        monkeypatch.setitem(sys.modules, name, module)
    _stub_missing(monkeypatch, "redis")
    _stub_missing(monkeypatch, "redis.asyncio")
    _forget_on_teardown(monkeypatch, _CACHED)
    return importlib.import_module("workers.research_work_tasks")


@pytest.fixture
def wt(monkeypatch):
    return _load(monkeypatch)


class TestTaskOptions:
    def test_task_runs_on_the_fixed_plan_queue_with_limits(self, wt):
        task = wt.dispatch_research_work
        assert task.name == wt.DISPATCH_TASK == "tasks.dispatch_research_work"
        assert task.queue == wt.WORK_QUEUE == "q_research_plan"
        assert (task.soft_time_limit, task.time_limit) == (wt.GEN_SOFT_LIMIT, wt.GEN_HARD_LIMIT)

    def test_deadline_covers_three_calls_and_the_limits_sit_above_it(self, wt):
        from services.research_work.generate import CALL_TIMEOUT, MAX_CALLS
        assert wt.GEN_DEADLINE == 960
        assert wt.GEN_DEADLINE > MAX_CALLS * (CALL_TIMEOUT + 10)      # 호출마다 연결 10초까지
        assert (wt.GEN_SOFT_LIMIT, wt.GEN_HARD_LIMIT) == (1020, 1080)

    def test_registered_and_routed_even_when_the_plan_queue_setting_is_blank(self, monkeypatch):
        """celery-control·beat 에는 RESEARCH_PLAN_QUEUE 가 없다 — 설정을 따르면 q_llm 으로 떨어진다."""
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_llm")
        monkeypatch.setenv("RESEARCH_PLAN_QUEUE", "")
        get_settings.cache_clear()
        try:
            wt = _load(monkeypatch)
            app = sys.modules["workers.celery_app"].celery_app
            assert "workers.research_work_tasks" in app.init_kw["include"]
            assert app.conf.task_routes["tasks.dispatch_research_work"] == {"queue": "q_research_plan"}
            assert app.conf.task_routes["tasks.plan_deep_research"] == {"queue": "q_llm"}
            assert wt.dispatch_research_work.queue == "q_research_plan"
            assert wt.send_dispatch() is True
            assert app.sent == [("tasks.dispatch_research_work", None, {"queue": "q_research_plan"})]
        finally:
            get_settings.cache_clear()


class TestSendDispatch:
    def test_sends_the_dispatch_task_to_the_plan_queue(self, wt):
        assert wt.send_dispatch() is True
        assert wt.celery_app.sent == [("tasks.dispatch_research_work", None, {"queue": "q_research_plan"})]

    def test_broker_down_is_reported_not_raised(self, wt, caplog):
        wt.celery_app.fail = True
        with caplog.at_level(logging.ERROR):
            assert wt.send_dispatch() is False
        assert any("디스패치 태스크 전달 실패" in r.getMessage() for r in caplog.records)


# ── 태스크 본문 ───────────────────────────────────────────────────────
class _Session(AsyncSessionOverSync):
    """워커의 세션처럼(_job_engine: expire_on_commit=False) 커밋 뒤에도 읽은 값을 들고 있고, async with 로 연다."""

    def __init__(self, engine):
        super().__init__(engine, expire_on_commit=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
        return False


class _Env:
    """SQLite 대역 위에서 태스크를 돌린다. chat_full 은 replies 를 차례로 꺼내고(예외면 올린다)."""

    def __init__(self, monkeypatch, wt, replies=()):
        self.wt = wt
        self.engine = make_engine()
        self.replies = list(replies)
        self.calls: list[tuple] = []
        self.events: list[tuple] = []
        self.dispatched = 0
        self.disposed = 0
        self.on_call = None
        env = self

        class _Engine:
            async def dispose(self):
                env.disposed += 1

        cfg = routing.get_settings()
        for key, value in (("VLM_BASE_URL", "http://qwen.test/v1"), ("VLM_MODEL", "qwen-test"),
                           ("LLM_BASE_URL", "http://gemma.test/v1"), ("LLM_MODEL", "gemma-test")):
            monkeypatch.setattr(cfg, key, value)
        monkeypatch.setattr(wt, "_job_engine", lambda: (_Engine(), lambda: _Session(self.engine)))
        monkeypatch.setattr(wt, "chat_full", self._chat)
        monkeypatch.setattr(wt, "publish_work", self._publish)
        monkeypatch.setattr(wt, "send_dispatch", self._send)

    async def _chat(self, messages, *, params=None, timeout=120.0, base_url=None, model=None):
        self.calls.append((base_url, model, timeout))
        if self.on_call is not None:
            await self.on_call()
        item = self.replies.pop(0)
        if isinstance(item, BaseException):
            raise item
        return LLMResult(content=item, finish_reason="stop")

    async def _publish(self, work_id, kind, payload):
        self.events.append((work_id, kind, payload))

    def _send(self) -> bool:
        self.dispatched += 1
        return True

    def work(self, **fields):
        job_id = add_research_job(self.engine, status="completed", stage="synthesized")
        add_work(self.engine, job_id, **fields)
        return job_id

    def gen(self, work_id, **fields) -> int:
        fields.setdefault("input", CONCEPTS_INPUT)
        return add_generation(self.engine, work_id, **fields)

    def row(self, gid: int):
        with self.engine.connect() as conn:
            return conn.execute(sa.select(GEN).where(GEN.c.id == gid)).mappings().one()

    def work_row(self, work_id):
        with self.engine.connect() as conn:
            return conn.execute(sa.select(WORK).where(WORK.c.id == work_id)).mappings().one()

    def set_status(self, gid: int, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(sa.update(GEN).where(GEN.c.id == gid).values(status=status))


class TestDispatch:
    def test_idle_when_nothing_is_queued(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt)

        assert wt.dispatch_research_work() == {"status": "idle"}
        assert env.calls == [] and env.events == [] and env.dispatched == 0
        assert env.disposed == 1

    def test_idle_while_another_generation_runs(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        running = env.gen(env.work(), status="running")
        waiting = env.gen(env.work())

        assert wt.dispatch_research_work() == {"status": "idle"}
        assert env.calls == []
        assert (env.row(running)["status"], env.row(waiting)["status"]) == ("running", "queued")

    def test_concepts_generation_runs_to_done(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        work_id = env.work()
        gid = env.gen(work_id)

        out = wt.dispatch_research_work()

        row = env.row(gid)
        assert out == {"gen_id": gid, "status": "done"}
        # 핵심 개념의 주 모델은 gemma 다(06a Qwen 표본 결정)
        assert env.calls == [("http://gemma.test/v1", "gemma-test", 300.0)]
        assert (row["status"], row["model"], row["error"]) == ("done", "gemma-test", None)
        assert row["output"] == {"concepts": ["독서 격차", "청소년"],
                                 "attempts": [{"model": "gemma-test", "outcome": "ok"}]}
        assert row["started_at"] is not None and row["finished_at"] is not None
        work = env.work_row(work_id)
        assert (work["concepts"], work["concept_members"]) == (["독서 격차", "청소년"], {})
        assert env.events == [(work_id, "generation", {
            "gen_id": gid, "gen_kind": "concepts", "target": None, "status": "done",
            "model": "gemma-test", "result": {"concepts": ["독서 격차", "청소년"]},
        })]
        assert env.dispatched == 0 and env.disposed == 1

    def test_generation_event_keeps_its_kind_on_the_work_channel(self, monkeypatch, wt):
        """진짜 publish_work 로 보낸다(Redis 만 가짜). relay 는 {"kind": 이벤트 종류, **payload} 로 실어
        페이로드에 "kind" 가 있으면 "generation" 을 덮어쓴다 — 생성 종류는 gen_kind 에 실려야 한다."""
        env = _Env(monkeypatch, wt, replies=[GOOD])
        relay = sys.modules["services.research.relay"]
        published: list[tuple[str, str]] = []

        class _Redis:
            async def publish(self, channel, data):
                published.append((channel, data))

            async def aclose(self):
                return None

        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: _Redis())
        monkeypatch.setattr(wt, "publish_work", relay.publish_work)
        work_id = env.work()
        gid = env.gen(work_id)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "done"}

        ((channel, data),) = published
        event = json.loads(data)
        assert channel == f"research:work:{work_id}"
        assert (event["kind"], event["gen_kind"], event["gen_id"], event["status"]) == (
            "generation", "concepts", gid, "done")

    def test_no_answer_after_three_calls_is_done_with_no_concepts(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=["모르겠다", '{"concepts": ["하나"]}', "{}"])
        work_id = env.work()
        gid = env.gen(work_id)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "done"}

        row = env.row(gid)
        assert [c[1] for c in env.calls] == ["gemma-test", "gemma-test", "qwen-test"]
        assert (row["status"], row["model"]) == ("done", None)
        assert row["output"]["concepts"] == []
        assert [a["outcome"] for a in row["output"]["attempts"]] == ["parse", "check", "parse"]
        assert env.events[0][2]["result"] == {"concepts": []}

    def test_transport_failure_hands_over_to_qwen(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[httpx.ConnectError("거부"), GOOD])
        gid = env.gen(env.work())

        wt.dispatch_research_work()

        row = env.row(gid)
        assert [c[0] for c in env.calls] == ["http://gemma.test/v1", "http://qwen.test/v1"]
        assert (row["status"], row["model"]) == ("done", "qwen-test")

    def test_next_generation_is_sent_when_more_are_queued(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        first = env.gen(env.work())
        second = env.gen(env.work())

        wt.dispatch_research_work()

        assert (env.row(first)["status"], env.row(second)["status"]) == ("done", "queued")
        assert env.dispatched == 1

    def test_cancel_during_the_call_discards_the_result(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        work_id = env.work(concepts=["사용자 개념"])
        gid = env.gen(work_id)
        other = env.gen(env.work())

        async def _cancel():
            env.set_status(gid, "canceled")          # 사용자가 취소 — API 의 조건부 UPDATE

        env.on_call = _cancel
        out = wt.dispatch_research_work()

        row = env.row(gid)
        assert out == {"gen_id": gid, "status": "dropped"}
        assert (row["status"], row["output"], row["finished_at"]) == ("canceled", None, None)
        assert env.work_row(work_id)["concepts"] == ["사용자 개념"]
        assert env.events == []
        assert env.row(other)["status"] == "queued" and env.dispatched == 1

    def test_unexpected_error_fails_the_generation(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[ValueError("코드 결함")])
        work_id = env.work()
        gid = env.gen(work_id)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "failed"}

        row = env.row(gid)
        assert (row["status"], row["output"], row["model"]) == ("failed", None, None)
        assert row["error"] == "ValueError: 코드 결함"
        assert env.events == [(work_id, "generation", {
            "gen_id": gid, "gen_kind": "concepts", "target": None, "status": "failed",
            "model": None, "result": None,
        })]

    def test_apply_failure_rolls_back_and_fails_the_generation(self, monkeypatch, wt):
        """결과 반영(apply_result)이 터지면 반영을 되돌리고 생성을 failed 로 닫는다 — 연구의 칩은 그대로다."""
        env = _Env(monkeypatch, wt, replies=[GOOD])
        work_id = env.work(concepts=["사용자 개념"])
        gid = env.gen(work_id)
        other = env.gen(env.work())

        async def _broken_apply(db, gen, output):
            raise RuntimeError("반영 결함")

        monkeypatch.setattr(wt, "apply_result", _broken_apply)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "failed"}

        row = env.row(gid)
        assert (row["status"], row["output"], row["model"]) == ("failed", None, None)
        assert row["error"] == "RuntimeError: 반영 결함"
        assert env.work_row(work_id)["concepts"] == ["사용자 개념"]
        assert env.events == [(work_id, "generation", {
            "gen_id": gid, "gen_kind": "concepts", "target": None, "status": "failed",
            "model": None, "result": None,
        })]
        assert env.row(other)["status"] == "queued" and env.dispatched == 1

    def test_soft_time_limit_before_picking_is_a_timeout(self, monkeypatch, wt):
        """집기 전(pick_next 안)에 소프트 리밋이 걸리면 닫을 생성이 없다 — 상태만 알린다."""
        env = _Env(monkeypatch, wt)
        gid = env.gen(env.work())

        async def _slow_pick(db):
            raise _SoftTimeLimitExceeded()

        monkeypatch.setattr(wt, "pick_next", _slow_pick)

        assert wt.dispatch_research_work() == {"status": "timeout"}
        assert env.row(gid)["status"] == "queued" and env.calls == [] and env.events == []

    def test_kind_without_an_executor_fails_without_calling_the_llm(self, monkeypatch, wt):
        # facet 은 06c 까지 실행기가 없다 — outline 은 06b 에서 실행기가 생겼다
        env = _Env(monkeypatch, wt)
        gid = env.gen(env.work(), kind="facet", input={})

        wt.dispatch_research_work()

        row = env.row(gid)
        assert env.calls == []
        assert (row["status"], row["error"]) == ("failed", "실행기가 없는 생성 종류: facet")

    def test_deadline_fails_the_generation(self, monkeypatch, wt):
        env = _Env(monkeypatch, wt, replies=[GOOD])
        gid = env.gen(env.work())

        async def _hang():
            await asyncio.sleep(5)

        env.on_call = _hang
        monkeypatch.setattr(wt, "GEN_DEADLINE", 0.05)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "failed"}
        row = env.row(gid)
        assert (row["status"], row["error"]) == ("failed", wt.TIMEOUT_ERROR)
        assert env.events[0][2]["status"] == "failed"

    def test_soft_time_limit_closes_the_generation_on_a_new_loop(self, monkeypatch, wt):
        """소프트 리밋이 asyncio.run 밖으로 튀면 루프의 정리 코드가 돌지 않는다 — 새 루프로 닫는다(함정 19)."""
        env = _Env(monkeypatch, wt, replies=[_SoftTimeLimitExceeded()])
        work_id = env.work()
        gid = env.gen(work_id)
        other = env.gen(env.work())

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "failed"}

        row = env.row(gid)
        assert (row["status"], row["error"]) == ("failed", wt.TIMEOUT_ERROR)
        assert env.events[0][:2] == (work_id, "generation") and env.events[0][2]["status"] == "failed"
        assert env.row(other)["status"] == "queued" and env.dispatched == 1
        assert env.disposed == 2              # 잡 엔진 둘(본문·정리) 모두 닫는다


# ── 스트리밍 생성(06b) ────────────────────────────────────────────────


def _stream_executor():
    """원문을 {"text"} 로 읽고 [E1] 이 있어야 통과하는 스트리밍 실행기(절 실행기 자리)."""
    from services.research_work.generate import Executor

    return Executor(
        kind="section", build=lambda inp: ([{"role": "user", "content": "절을 써라"}], {}),
        parse=lambda raw: {"text": raw} if raw.strip() else None,
        check=lambda out: "[E1]" in out["text"],
        empty=lambda inp: {"text": ""},
        stream=True,
    )


class _StreamEnv(_Env):
    """_Env 에 chat_stream 대본을 더한다. 대본 한 줄 = 조각 문자열·예외·잠들 초(float)의 목록."""

    def __init__(self, monkeypatch, wt, streams=()):
        super().__init__(monkeypatch, wt)
        self.streams = list(streams)
        monkeypatch.setattr(wt, "chat_stream", self._stream)
        monkeypatch.setitem(wt.EXECUTORS, "section", _stream_executor())

    async def _stream(self, messages, *, params=None, timeout=120.0, base_url=None, model=None):
        self.calls.append((base_url, model, timeout))
        for item in self.streams.pop(0):
            if isinstance(item, BaseException):
                raise item
            if isinstance(item, float):
                await asyncio.sleep(item)
                continue
            yield item

    def section(self, work_id, target: str = "prior.g1") -> int:
        gid = self.gen(work_id, kind="section", input={"key": target})
        with self.engine.begin() as conn:
            conn.execute(sa.update(GEN).where(GEN.c.id == gid).values(target=target))
        return gid

    def deltas(self) -> list[dict]:
        return [payload for _, kind, payload in self.events if kind == "section_delta"]


class TestStreaming:
    def test_streaming_executor_relays_grouped_deltas_then_closes(self, monkeypatch, wt):
        monkeypatch.setattr(wt, "DELTA_FLUSH_SEC", 60.0)        # 글자 수로만 묶는다
        env = _StreamEnv(monkeypatch, wt, streams=[["가" * 50, "나" * 50, " 끝 [E1]."]])
        work_id = env.work()
        gid = env.section(work_id)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "done"}

        assert env.calls == [("http://gemma.test/v1", "gemma-test", 300.0)]   # chat_full 은 부르지 않는다
        assert env.deltas() == [
            {"gen_id": gid, "target": "prior.g1", "seq": 0, "offset": 0, "text": "가" * 50 + "나" * 50},
            {"gen_id": gid, "target": "prior.g1", "seq": 1, "offset": 100, "text": " 끝 [E1]."},
        ]
        assert env.events[-1] == (work_id, "generation", {
            "gen_id": gid, "gen_kind": "section", "target": "prior.g1", "status": "done",
            "model": "gemma-test", "result": {},
        })
        assert env.row(gid)["output"] == {"text": "가" * 50 + "나" * 50 + " 끝 [E1].",
                                          "attempts": [{"model": "gemma-test", "outcome": "ok"}]}

    def test_a_broken_stream_resets_the_screen_and_asks_again(self, monkeypatch, wt):
        monkeypatch.setattr(wt, "DELTA_FLUSH_CHARS", 1)         # 조각마다 보낸다
        env = _StreamEnv(monkeypatch, wt, streams=[["앞부분", httpx.ReadError("끊김")], ["다시 [E1]."]])
        gid = env.section(env.work(), target="gap")

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "done"}

        assert env.deltas() == [
            {"gen_id": gid, "target": "gap", "seq": 0, "offset": 0, "text": "앞부분"},
            {"gen_id": gid, "target": "gap", "seq": 1, "offset": 0, "text": "", "reset": True},
            {"gen_id": gid, "target": "gap", "seq": 2, "offset": 0, "text": "다시 [E1]."},
        ]
        assert env.row(gid)["output"]["attempts"] == [
            {"model": "gemma-test", "outcome": "broken", "error": "ReadError: 끊김"},
            {"model": "gemma-test", "outcome": "ok"},
        ]

    def test_failure_before_the_first_piece_hands_over_to_qwen(self, monkeypatch, wt):
        env = _StreamEnv(monkeypatch, wt, streams=[[httpx.ConnectError("거부")], ["본문 [E1]."]])
        gid = env.section(env.work())

        wt.dispatch_research_work()

        assert [c[0] for c in env.calls] == ["http://gemma.test/v1", "http://qwen.test/v1"]
        assert [d.get("reset") for d in env.deltas()] == [None]
        assert (env.row(gid)["status"], env.row(gid)["model"]) == ("done", "qwen-test")

    def test_the_deadline_fails_a_streaming_generation(self, monkeypatch, wt):
        env = _StreamEnv(monkeypatch, wt, streams=[["앞", 5.0]])
        gid = env.section(env.work())
        monkeypatch.setattr(wt, "GEN_DEADLINE", 0.05)

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "failed"}
        assert (env.row(gid)["status"], env.row(gid)["error"]) == ("failed", wt.TIMEOUT_ERROR)
        assert env.events[-1][2]["status"] == "failed"

    def test_relay_groups_by_size_and_time(self, monkeypatch, wt):
        events: list[tuple] = []

        async def _publish(work_id, kind, payload):
            events.append((work_id, kind, payload))

        monkeypatch.setattr(wt, "publish_work", _publish)
        now = [100.0]
        gen = wt._Picked(id=7, work_id="w-1", kind="section", target="gap", input={})
        relay = wt.DeltaRelay(gen, clock=lambda: now[0])

        async def _go():
            await relay.push("가" * 30)          # 30자·0초 — 묶어 둔다
            now[0] += 0.6
            await relay.push("나")               # 0.5초가 지났다 — 보낸다
            await relay.push("다" * 80)          # 80자 — 보낸다
            await relay.push("")
            await relay.reset()
            await relay.push("라")
            await relay.flush()                  # 끝 — 남은 조각
            await relay.flush()                  # 보낼 것이 없다

        asyncio.run(_go())

        assert [(w, k) for w, k, _ in events] == [("w-1", "section_delta")] * 4
        assert [p for _, _, p in events] == [
            {"gen_id": 7, "target": "gap", "seq": 0, "offset": 0, "text": "가" * 30 + "나"},
            {"gen_id": 7, "target": "gap", "seq": 1, "offset": 31, "text": "다" * 80},
            {"gen_id": 7, "target": "gap", "seq": 2, "offset": 0, "text": "", "reset": True},
            {"gen_id": 7, "target": "gap", "seq": 3, "offset": 0, "text": "라"},
        ]


class TestDeadline:
    def test_one_deadline_covers_every_executor(self, wt):
        from services.research_work.generate import CALL_TIMEOUT, MAX_CALLS
        # 스트리밍도 호출마다 CALL_TIMEOUT 이라(run_stream_generation) 생성 1건의 최악은 kind 와 상관없이
        # MAX_CALLS × (CALL_TIMEOUT + 연결 10초) — 데드라인·리밋을 kind 별로 나누지 않는다(06b 계획 정함 11)
        assert wt.GEN_DEADLINE >= MAX_CALLS * (CALL_TIMEOUT + 10)
        assert all(ex.kind == kind for kind, ex in wt.EXECUTORS.items())

    def test_streaming_calls_are_bounded_one_by_one(self, monkeypatch, wt):
        # 세 호출이 모두 첫 조각 뒤 멈춰도 호출마다 상한에서 끊겨 데드라인 전에 빈 결과로 done 이다
        from services.research_work import generate
        monkeypatch.setattr(generate, "CALL_TIMEOUT", 0.05)
        env = _StreamEnv(monkeypatch, wt, streams=[["앞", 5.0], ["앞", 5.0], ["앞", 5.0]])
        gid = env.section(env.work())

        assert wt.dispatch_research_work() == {"gen_id": gid, "status": "done"}

        row = env.row(gid)
        assert [c[1] for c in env.calls] == ["gemma-test", "gemma-test", "qwen-test"]
        assert row["model"] is None
        assert [a["outcome"] for a in row["output"]["attempts"]] == ["broken", "broken", "broken"]


class TestCloseFallback:
    def test_a_db_error_while_failing_leaves_the_generation_to_the_reaper(self, monkeypatch, wt, caplog):
        env = _Env(monkeypatch, wt)
        gid = env.gen(env.work(), kind="refine", input={})      # 실행기 없는 kind — failed 로 닫으려 한다
        other = env.gen(env.work())
        real_finish = wt.finish

        async def _finish(db, gen_id, *, status, **kw):
            if status == "failed":
                raise sa.exc.OperationalError("UPDATE research_generations", {}, Exception("연결 끊김"))
            return await real_finish(db, gen_id, status=status, **kw)

        monkeypatch.setattr(wt, "finish", _finish)

        with caplog.at_level(logging.ERROR):
            assert wt.dispatch_research_work() == {"gen_id": gid, "status": "dropped"}

        assert env.row(gid)["status"] == "running"              # 회수기(hard limit + 60초)가 거둔다
        assert env.events == []
        assert env.row(other)["status"] == "queued" and env.dispatched == 1
        assert any("회수기가 거둔다" in r.getMessage() for r in caplog.records)
