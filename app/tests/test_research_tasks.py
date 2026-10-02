"""test_research_tasks.py — 딥리서치 Celery 태스크

`workers.research_tasks` 는 celery(태스크 데코레이터)와 redis(relay) 를 물고
온다. 둘 다 로컬 venv 에 없어서 최상단에서 import 하면 pytest 가 **collection
단계에서** 죽고 세션 전체가 0건이 된다(`docs/ops/recurring-gotchas.md` 13번).
그래서 미설치일 때만 더미를 꽂고 함수 안에서 import 한다
(test_embed_index_guard.py·test_search_chunk_answer_flag.py 와 같은 방식).

DB 는 대역으로 세운다. 대역은 research_jobs 의 UPDATE·status 조회에 한해 WHERE 를
실제로 평가한다 — 취소가 워커의 최종 쓰기에 덮이는 회귀는 status 조건이 빠진
UPDATE 로 생기는데, 대역이 조건을 무시하면 그 회귀를 못 잡는다.
"""
import asyncio
import datetime as _dt
import importlib
import json
import logging
import sys
import types
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList, Grouping
from sqlalchemy.sql.selectable import Exists

from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, snapshot_state,
)

_CACHED = ("workers.research_tasks", "workers.celery_app", "services.research.relay",
           "workers.research_work_tasks")


class _SoftTimeLimitExceeded(Exception):
    """celery 미설치 환경용 대역. MagicMock 을 except 절에 쓰면 TypeError 가 난다."""


class _FakeConf:
    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class _FakeCelery:
    """task 데코레이터가 원함수를 돌려준다. 옵션은 Celery 처럼 속성으로 붙인다."""

    def __init__(self, *a, **kw):
        self.conf = _FakeConf()

    def task(self, *a, **kw):
        def _decorator(fn):
            for key, value in kw.items():
                setattr(fn, key, value)
            return fn
        return _decorator


def _stub_missing(monkeypatch, name: str, module=None) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module or MagicMock())


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 있던 키만 되돌린다. 원래 없던 키는 기록이 남지 않아
    여기서 새로 import 한 모듈(더미 celery·redis 에 묶인 채)이 teardown 뒤에도 남는다.
    setitem·setattr 은 원래 없던 키·속성이면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을
    남긴 뒤 뺀다. 부모 속성까지 되돌리는 이유: `from pkg import mod` 와 문자열 경로
    monkeypatch 는 sys.modules 보다 부모 속성을 먼저 본다.
    """
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


def _load_tasks(monkeypatch, *, fake_celery: bool = False):
    """research_tasks 를 새로 import 한다. 앞 테스트가 남긴 모듈을 물려받지 않고, 끝나면
    import 전 그대로 되돌린다(_forget_on_teardown).

    fake_celery=True 면 celery 가 설치됐거나 다른 테스트가 더미를 꽂아 뒀어도
    이 파일의 _FakeCelery 를 쓴다 — 태스크 옵션·라우팅을 단언할 때 필요하다."""
    celery_mod = types.ModuleType("celery")
    celery_mod.Celery = _FakeCelery
    celery_exc = types.ModuleType("celery.exceptions")
    celery_exc.SoftTimeLimitExceeded = _SoftTimeLimitExceeded
    if fake_celery:
        monkeypatch.setitem(sys.modules, "celery", celery_mod)
        monkeypatch.setitem(sys.modules, "celery.exceptions", celery_exc)
    _stub_missing(monkeypatch, "celery", celery_mod)
    _stub_missing(monkeypatch, "celery.exceptions", celery_exc)
    _stub_missing(monkeypatch, "redis")
    _stub_missing(monkeypatch, "redis.asyncio")
    _forget_on_teardown(monkeypatch, _CACHED)
    return importlib.import_module("workers.research_tasks")


# ── DB 대역 ────────────────────────────────────────────────────────────
def _matches(clause, obj) -> bool:
    if clause is None:
        return True
    if isinstance(clause, BooleanClauseList):
        return all(_matches(c, obj) for c in clause.clauses)
    left = getattr(obj, clause.left.key)
    right = getattr(clause.right, "value", None)
    op = clause.operator
    if op is operators.eq:
        return left == right
    if op is operators.lt:
        return left < right
    if op is operators.in_op:
        return left in right
    if op is operators.is_not:
        return left is not None
    raise AssertionError(f"대역이 모르는 연산자: {op}")


class _Result:
    def __init__(self, value=None, rowcount: int = 0, rows: list | None = None):
        self._value = value
        self.rowcount = rowcount
        self._rows = rows or []

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value

    def all(self):
        return self._rows


class _FakeSession:
    """execute 를 기록하고, research_jobs 의 조건부 UPDATE·status 조회를 흉내 낸다.

    in_txn 은 "읽기 트랜잭션이 열려 있는가"다. LLM 을 기다리는 동안 이게 참이면
    library_catalog 잠금을 쥔 채 FastAPI 기동 DDL 을 막는다.
    """

    def __init__(self, *, job=None, scalar=None):
        self.job = job
        self.scalar = scalar
        self.sql: list[str] = []
        self.params: list[dict] = []
        self.commits = 0
        self.rollbacks = 0
        self.in_txn = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt, params=None):
        self.sql.append(str(stmt))
        self.params.append(params)
        self.in_txn = True
        table = getattr(getattr(stmt, "table", None), "name", None)
        if getattr(stmt, "is_update", False) and table == "research_jobs":
            return _Result(rowcount=self._update_job(stmt))
        if str(stmt).startswith("SELECT research_jobs.status"):
            hit = self.job is not None and _matches(stmt.whereclause, self.job)
            return _Result(self.job.status if hit else None)
        return _Result(self.scalar)

    def _update_job(self, stmt) -> int:
        if self.job is None or not _matches(stmt.whereclause, self.job):
            return 0
        for key, value in stmt._values.items():
            setattr(self.job, getattr(key, "key", key),
                    value.value if isinstance(value, BindParameter) else value)
        return 1

    async def get(self, model, pk):
        self.in_txn = True
        return self.job

    async def commit(self):
        self.commits += 1
        self.in_txn = False

    async def rollback(self):
        self.rollbacks += 1
        self.in_txn = False

    def add(self, obj):
        return None


class _FakeEngine:
    def __init__(self):
        self.disposed = 0

    async def dispose(self):
        self.disposed += 1


class _FakeJob:
    """ResearchJob 대역 — 태스크가 실제로 읽고 쓰는 필드만 가진다."""

    def __init__(self, *, stage, plan, state_snapshot=None, status="approved"):
        self.id = uuid.uuid4()
        self.question = "독서 격차 연구는 어디까지 왔나"
        self.params = {}
        self.plan = plan
        self.stage = stage
        self.state_snapshot = state_snapshot
        self.status = status
        self.report = None
        self.last_error = None
        self.started_at = None
        self.finished_at = None


def _explored_snapshot() -> dict:
    st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
    st.subquestions = [
        SubQuestion(idx=0, text="스냅샷 하위1", queries=["q1"], evidence_ids=["E0"],
                    verdict="sufficient", note="충분"),
        SubQuestion(idx=1, text="스냅샷 하위2", failed=True),
    ]
    st.evidence = {
        "E0": Evidence(id="E0", cnts_id="A", meta={"title": "논문 가"},
                       chunks=[Chunk("c1", "본문", 3, 4, 0.8)]),
    }
    return snapshot_state(st)


class _Harness:
    def __init__(self, session, engine):
        self.session = session
        self.engine = engine
        self.events: list[tuple] = []
        self.steps: list[tuple] = []
        self.finished: list[tuple] = []
        self.on_section = None
        self.emit = None
        self.progress: list[tuple] = []
        # (단계, status, 알린 result) — _finish·_save_progress 가 step 이벤트로 흘리는 값
        self.announced: list[tuple] = []
        # (단계, 그때까지 나간 종료 이벤트) — 이전 시도의 초안 정리
        self.drops: list[tuple] = []
        # 대기 순번 ZSET 에서 뺀 잡
        self.unmarked: list = []


def _patch_pipeline(monkeypatch, rt, *, job, explored: list, synthesized: list,
                    explore=None, synthesize=None, session=None) -> _Harness:
    """DB·Redis·LLM 을 대역으로 바꾸고 호출만 기록한다.

    explore·synthesize 로 하위 동작을 끼워 넣는다(취소를 찍거나 예외를 던지는 식).
    session 을 주면 그 대역을 쓴다(research_steps 행까지 흉내 내야 할 때).
    """
    if session is None:
        session = _FakeSession(job=job, scalar=0)
    h = _Harness(session, _FakeEngine())
    monkeypatch.setattr(rt, "_job_engine", lambda: (h.engine, lambda: session))

    async def _next_seq(db, job_id):
        return 3

    async def _step(db, job_id, seq, kind, title, *, subq_idx=None, detail=None):
        h.steps.append((kind, title))
        return len(h.steps)

    async def _finish(db, step_id, status, result=None, event_result=None):
        # 롤백 없이 쓰면 깨진 트랜잭션 위에서 다시 터진다 — 몇 번 롤백한 뒤였는지 남긴다
        h.finished.append((step_id, status, result, session.rollbacks))
        h.announced.append((step_id, status, result if event_result is None else event_result))

    async def _corpus_range(db):
        return {"from": "2002", "to": "2026", "n_papers": 7}

    async def _publish(job_id, kind, payload):
        h.events.append((kind, payload))

    async def _publish_terminal(job_id, status, error=None):
        h.events.append(("terminal", status, error))

    async def _explore(state, subq, *, db, emit=None):
        assert not session.in_txn, "탐색(LLM) 직전에 읽기 트랜잭션이 열려 있다"
        explored.append(subq.text)
        h.emit = emit
        if explore is not None:
            await explore(state, subq)
        return subq

    async def _save_progress(db, step, result, event_result=None):
        h.progress.append((step, result))
        h.announced.append((step, "running", result if event_result is None else event_result))

    async def _drop_stale_previews(db, step):
        h.drops.append((step, _terminals(h)))

    async def _unmark(job_id):
        h.unmarked.append(job_id)

    async def _synthesize(state, *, should_stop=None, on_section=None):
        assert not session.in_txn, "종합(LLM) 직전에 읽기 트랜잭션이 열려 있다"
        synthesized.append(state)
        h.on_section = on_section
        if synthesize is not None:
            return await synthesize(state, should_stop)
        return {"sections": []}

    for name, fn in (
        ("_next_seq", _next_seq), ("_step", _step), ("_finish", _finish),
        ("_corpus_range", _corpus_range), ("publish", _publish),
        ("publish_terminal", _publish_terminal),
        ("explore_subquestion", _explore), ("synthesize", _synthesize),
        ("_save_progress", _save_progress), ("_drop_stale_previews", _drop_stale_previews),
        ("unmark", _unmark),
    ):
        monkeypatch.setattr(rt, name, fn)
    return h


def _terminals(h: _Harness) -> list[tuple]:
    return [e[1:] for e in h.events if e[0] == "terminal"]


class TestNextSeq:
    """seq 를 1 로 되돌리면 uq_research_steps_job_seq 를 위반해 재시도가 죽는다."""

    def test_returns_value_from_db_not_a_constant(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=7)
        assert asyncio.run(rt._next_seq(db, uuid.uuid4())) == 7

    def test_empty_table_starts_at_zero(self, monkeypatch):
        # coalesce(max(seq), -1) + 1 — step 이 없는 잡은 0 에서 시작한다
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=0)
        assert asyncio.run(rt._next_seq(db, uuid.uuid4())) == 0

    def test_query_continues_from_max_for_this_job(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=5)
        jid = uuid.uuid4()
        asyncio.run(rt._next_seq(db, jid))
        assert "max(seq)" in db.sql[0]
        assert "job_id = :j" in db.sql[0]
        # UUID 로 넘긴다 — 문자열을 넘기면 드라이버 쪽 변환에 기대게 된다
        assert db.params[0] == {"j": jid}


class TestResumeFromSnapshot:
    """stage="explored" 로 다시 들어온 잡은 탐색을 건너뛰고 종합부터 간다.

    이 분기가 없으면 stage·state_snapshot 은 쓰기만 하고 아무도 안 읽는
    컬럼이 되고, 종합 실패가 5~7분짜리 탐색을 매번 버린다.
    """

    def test_explored_job_skips_exploration(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=_explored_snapshot(), status="queued")
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        # plan 을 일부러 채워 뒀다 — 재개 분기를 지우면 여기서 2건이 탐색된다
        assert explored == []
        assert len(synthesized) == 1
        assert out["status"] == "completed"
        assert job.status == "completed"
        assert job.stage == "synthesized"

    def test_resumed_state_comes_from_the_snapshot(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=_explored_snapshot(), status="queued")
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        asyncio.run(rt._run_deep_research(str(job.id)))

        state = synthesized[0]
        # plan 이 아니라 스냅샷에서 살아난 하위질문이어야 한다
        assert [sq.text for sq in state.subquestions] == ["스냅샷 하위1", "스냅샷 하위2"]
        assert state.subquestions[1].failed is True
        assert state.evidence["E0"].chunks[0].page_start == 3

    def test_planned_job_runs_the_exploration_loop(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1", "계획 하위2"])
        explored, synthesized = [], []
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1", "계획 하위2"]
        assert job.stage == "synthesized"
        assert job.report == {"sections": []}
        assert job.finished_at is not None
        assert _terminals(h) == [("completed", None)]

    def test_exploration_writes_the_checkpoint(self, monkeypatch):
        """체크포인트를 안 쓰면 종합이 실패했을 때 되살릴 것이 없다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert job.state_snapshot is not None
        assert [sq["text"] for sq in job.state_snapshot["subquestions"]] == ["계획 하위1"]

    def test_stage_explored_without_snapshot_falls_back_to_exploration(self, monkeypatch):
        # 스냅샷이 비어 있으면 되살릴 것이 없다 — 빈 보고서를 completed 로 저장하느니
        # 탐색을 다시 도는 쪽이 맞다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1"], state_snapshot=None)
        explored = []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1"]

    def test_engine_is_disposed(self, monkeypatch):
        # dispose 를 빠뜨리면 다음 잡이 닫힌 루프에 묶인 커넥션을 만난다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1"],
                       state_snapshot=_explored_snapshot())
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert h.engine.disposed == 1


class TestClaim:
    """Celery 는 at-least-once 다 — 선점에 실패한 재배달은 즉시 돌아서야 한다."""

    def test_unclaimed_job_is_skipped(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"], status="running")
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "skipped"
        assert explored == [] and synthesized == []

    def test_run_claims_only_statuses_the_api_writes(self, monkeypatch):
        """approve·retry 가 쓰는 상태를 워커가 받지 못하면 잡이 영원히 skipped 다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])
        seen = {}

        async def _record(db, job_id, *, allowed, to):
            seen["allowed"], seen["to"] = allowed, to
            return True

        monkeypatch.setattr(rt, "_claim", _record)
        asyncio.run(rt._run_deep_research(str(job.id)))

        from models.research import STATUS_APPROVED, STATUS_QUEUED
        assert STATUS_APPROVED in seen["allowed"]
        assert STATUS_QUEUED in seen["allowed"]
        assert seen["to"] == "running"

    def test_claimed_job_leaves_the_wait_line_right_after_the_claim(self, monkeypatch):
        """집은 잡은 더 이상 기다리는 잡이 아니다 — 뒤 잡의 순번에서 빠져야 한다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        explored = []
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=[])
        order = []
        claim = rt._claim

        async def _claim(db, job_id, *, allowed, to):
            order.append(("claim", list(h.unmarked)))
            return await claim(db, job_id, allowed=allowed, to=to)

        monkeypatch.setattr(rt, "_claim", _claim)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert order == [("claim", [])]          # 집기 전에는 빼지 않는다
        assert h.unmarked == [job.id]
        assert explored == ["계획 하위1"]

    def test_unclaimed_job_also_leaves_the_wait_line(self, monkeypatch):
        """재배달·취소로 못 집은 잡도 줄에 남기지 않는다 — 남으면 뒤 잡의 순번이 하나씩 밀린다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"], status="canceled")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "skipped"
        assert h.unmarked == [job.id]


class TestConditionalTransition:
    """워커의 상태 쓰기는 기대한 이전 상태를 WHERE 에 건다."""

    def test_transition_sql_carries_status_condition(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["가"], status="running")
        db = _FakeSession(job=job)

        ok = asyncio.run(rt._transition(db, job.id, expect=("running",), status="completed"))

        assert ok is True and job.status == "completed"
        assert "research_jobs.status IN" in db.sql[0]
        assert db.commits == 1

    def test_transition_does_not_touch_a_canceled_job(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["가"], status="canceled")
        db = _FakeSession(job=job)

        ok = asyncio.run(rt._transition(db, job.id, expect=("running",), status="completed"))

        assert ok is False and job.status == "canceled"


class TestCancel:
    """취소는 API 가 조건부 UPDATE 로 찍는다. 워커는 그 뒤에 무엇도 덮어쓰면 안 된다."""

    def test_cancel_before_first_subquestion_stops_everything(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        explored, synthesized = [], []
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        async def _claim_then_cancel(db, job_id, *, allowed, to):
            job.status = "canceled"      # 선점 직후 사용자가 취소했다
            return True

        monkeypatch.setattr(rt, "_claim", _claim_then_cancel)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "canceled"
        assert explored == [] and synthesized == []
        assert job.status == "canceled"
        assert _terminals(h) == [("canceled", None)]

    def test_cancel_during_last_subquestion_skips_synthesis(self, monkeypatch):
        """루프 머리에서만 확인하면 마지막 하위질문 중의 취소가 종합까지 간다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        explored, synthesized = [], []

        async def _cancel_on_last(state, subq):
            if subq.idx == 1:
                job.status = "canceled"

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored,
                            synthesized=synthesized, explore=_cancel_on_last)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["하위1", "하위2"]
        assert synthesized == []
        assert out["status"] == "canceled"
        assert job.status == "canceled"
        # 취소된 잡에 체크포인트를 남기지 않는다
        assert job.stage == "planned" and job.state_snapshot is None
        assert ("canceled", None) in _terminals(h)

    def test_cancel_between_sections_stops_synthesis(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        calls = {"llm": 0}

        async def _synth(state, should_stop):
            # 절마다 LLM 직전에 should_stop 을 본다 — 첫 절 뒤에 취소가 들어왔다
            for i in range(3):
                if await should_stop():
                    raise rt.SynthesisCanceled()
                calls["llm"] += 1
                job.status = "canceled"
            return {"sections": []}

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_synth)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert calls["llm"] == 1
        assert out["status"] == "canceled"
        assert job.status == "canceled" and job.report is None
        # 종합 step 을 running 으로 남기면 회수기가 30분 뒤에야 닫는다
        assert h.finished[-1][1] == "failed"

    def test_cancel_after_synthesis_keeps_canceled(self, monkeypatch):
        """절 사이 확인을 모두 지나친 취소도 최종 전이의 status 조건에 걸린다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _synth(state, should_stop):
            job.status = "canceled"
            return {"sections": [{"title": "절"}]}

        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[], synthesize=_synth)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "canceled"
        assert job.status == "canceled"
        assert job.report is None and job.stage == "explored"

    def test_resumed_job_canceled_before_synthesis(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        synthesized = []
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=synthesized)

        async def _claim_then_cancel(db, job_id, *, allowed, to):
            job.status = "canceled"
            return True

        monkeypatch.setattr(rt, "_claim", _claim_then_cancel)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert synthesized == [] and out["status"] == "canceled"


class TestFailure:
    def test_synthesis_error_keeps_checkpoint_for_retry(self, monkeypatch):
        """retry 가 종합부터 이어받으려면 failed 여도 stage=explored·스냅샷이 남아야 한다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _boom(state, should_stop):
            raise ValueError("보고서 종합 출력을 해석하지 못했다")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_boom)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.status == "failed"
        assert job.stage == "explored" and job.state_snapshot is not None
        assert "해석하지 못했다" in job.last_error
        assert _terminals(h) == [("failed", "보고서 종합 출력을 해석하지 못했다")]

        # 이어서 retry 한 것처럼 다시 돌리면 탐색 없이 종합만 한다
        job.status = "queued"
        explored = []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=[])
        assert asyncio.run(rt._run_deep_research(str(job.id)))["status"] == "completed"
        assert explored == []

    def test_all_subquestions_failed_fails_the_job_without_checkpoint(self, monkeypatch):
        """전멸한 탐색을 completed 빈 보고서로 두면 retry 도 못 한다(completed 는 409)."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        synthesized = []

        async def _down(state, subq):
            raise ConnectionError("Milvus 연결 실패")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=synthesized,
                            explore=_down)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.status == "failed" and job.last_error
        # 체크포인트가 없어야 retry 가 탐색부터 다시 돈다
        assert job.stage == "planned" and job.state_snapshot is None
        assert synthesized == []
        assert [t[0] for t in _terminals(h)] == ["failed"]

    def test_all_failed_after_gathering_evidence_still_synthesizes(self, monkeypatch):
        """중단 전까지 모은 근거가 있으면 전멸이 아니다 — synthesizer 가 그 근거로 절을
        쓰고 한계에 "오류로 중단"을 적는다. 잡째 실패시키면 실재하는 근거를 버린다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])
        synthesized = []

        async def _fails_after_adopting(state, subq):
            eid = f"E{subq.idx}"
            state.evidence[eid] = Evidence(id=eid, cnts_id=f"C{subq.idx}", meta={})
            subq.evidence_ids = [eid]
            raise KeyError("재검색 라운드에서 터졌다")

        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=synthesized,
                        explore=_fails_after_adopting)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "completed"
        assert len(synthesized) == 1
        assert job.stage == "synthesized"
        assert [sq["failed"] for sq in job.state_snapshot["subquestions"]] == [True, True]

    def test_wiped_out_snapshot_is_explored_again(self, monkeypatch):
        """전멸 가드 이전에 저장된 '전부 실패' 스냅샷은 체크포인트가 아니다. 거기서
        종합만 다시 하면 절 0개짜리 보고서가 completed 로 남는다."""
        rt = _load_tasks(monkeypatch)
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        st.subquestions = [SubQuestion(idx=0, text="스냅샷 하위1", failed=True),
                           SubQuestion(idx=1, text="스냅샷 하위2", failed=True)]
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=snapshot_state(st), status="queued")
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1", "계획 하위2"]
        assert out["status"] == "completed"

    def test_empty_plan_fails_with_its_own_reason(self, monkeypatch):
        """전멸 판정(all)은 하위질문 0개에도 참이다 — 그대로 두면 계획이 빈 잡이
        '탐색이 오류로 실패'로 남아 운영자가 검색 장애로 오진한다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=[])
        explored, synthesized = [], []
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.last_error == rt.EMPTY_PLAN_ERROR
        assert "오류로 실패" not in job.last_error
        assert explored == [] and synthesized == [] and h.steps == []
        assert _terminals(h) == [("failed", rt.EMPTY_PLAN_ERROR)]

    def test_search_step_result_carries_capped(self, monkeypatch):
        """재접속한 화면은 step result 로 타임라인을 복원한다 — SSE 로만 보낸 값은 사라진다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _hit_cap(state, subq):
            subq.capped = 3

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_hit_cap)
        asyncio.run(rt._run_deep_research(str(job.id)))

        search_result = h.finished[0][2]
        assert search_result["capped"] == 3

    def test_partial_failure_still_completes(self, monkeypatch):
        """부분 실패는 전체 실패가 아니다 — 실패한 하위질문은 한계로 보고한다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])

        async def _second_fails(state, subq):
            if subq.idx == 1:
                raise ConnectionError("일시 장애")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_second_fails)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "completed"
        assert [sq["failed"] for sq in job.state_snapshot["subquestions"]] == [False, True]
        assert [f[1] for f in h.finished if f[0] in (1, 2)] == ["done", "failed"]

    def test_subquestion_error_rolls_back_before_recording(self, monkeypatch):
        """DB 오류로 깨진 트랜잭션 위에서 _finish 를 부르면 핸들러가 다시 터진다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])

        async def _first_fails(state, subq):
            if subq.idx == 0:
                raise RuntimeError("InFailedSQLTransaction")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_first_fails)
        asyncio.run(rt._run_deep_research(str(job.id)))

        step_id, status, _result, rollbacks = h.finished[0]
        assert status == "failed" and rollbacks >= 1

    def test_error_outside_step_handlers_fails_the_job(self, monkeypatch):
        """가드 밖 예외로 태스크가 죽으면 잡이 running 에 묶여 회수기만 기다린다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        async def _broken(db):
            raise RuntimeError("connection reset")

        monkeypatch.setattr(rt, "_corpus_range", _broken)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.status == "failed" and "connection reset" in job.last_error
        assert [t[0] for t in _terminals(h)] == ["failed"]
        assert any("UPDATE research_steps" in s for s in h.session.sql)  # 열린 step 을 닫는다
        assert h.engine.disposed >= 1


class TestTimeout:
    def test_soft_limit_outside_the_coroutine_marks_job_failed(self, monkeypatch):
        """LLM await 중에 온 소프트 리밋은 asyncio.run 밖으로 튄다 — 동기 래퍼가 잡는다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="running")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        async def _body(job_id):
            raise rt.SoftTimeLimitExceeded()

        out = rt._run_job(_body, str(job.id))

        assert out["status"] == "failed"
        assert job.status == "failed" and "시간 상한" in job.last_error
        assert any("UPDATE research_steps" in s for s in h.session.sql)
        assert [t[0] for t in _terminals(h)] == ["failed"]

    def test_deadline_cancels_the_await_and_marks_job_failed(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="running")
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])
        monkeypatch.setattr(rt, "JOB_DEADLINE", 0.05)

        async def _hang(job_id):
            await asyncio.sleep(5)       # 응답 없는 LLM

        out = rt._run_job(_hang, str(job.id))

        assert out["status"] == "failed"
        assert "시간 상한" in job.last_error

    def test_timeout_does_not_overwrite_cancel(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="canceled")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        async def _body(job_id):
            raise rt.SoftTimeLimitExceeded()

        out = rt._run_job(_body, str(job.id))

        assert job.status == "canceled" and out["status"] == "canceled"
        assert _terminals(h) == []

    def test_deadline_is_well_inside_the_soft_limit(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        assert rt.JOB_DEADLINE <= rt.SOFT_LIMIT - 60


class TestPlan:
    def _patch(self, monkeypatch, rt, job, make_plan):
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])
        planner = types.ModuleType("services.research.planner")

        async def _make_plan(question, *, params):
            assert not h.session.in_txn, "계획(LLM) 직전에 읽기 트랜잭션이 열려 있다"
            return await make_plan(question, params)

        planner.make_plan = _make_plan
        monkeypatch.setitem(sys.modules, "services.research.planner", planner)
        return h

    def test_plan_success_awaits_approval(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            return ["하위1", "하위2"]

        self._patch(monkeypatch, rt, job, _plan)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "awaiting_approval"
        assert job.status == "awaiting_approval"
        assert job.plan == ["하위1", "하위2"] and job.stage == "planned"

    def test_plan_failure_marks_failed(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            raise ValueError("계획을 해석하지 못했다")

        h = self._patch(monkeypatch, rt, job, _plan)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "failed"
        assert job.status == "failed" and "해석하지 못했다" in job.last_error
        assert h.finished[-1][1] == "failed"
        assert [t[0] for t in _terminals(h)] == ["failed"]

    def test_cancel_during_planning_is_not_revived(self, monkeypatch):
        """planning 중 취소가 awaiting_approval 로 덮이면 취소한 잡을 승인·실행할 수 있다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            job.status = "canceled"
            return ["하위1"]

        self._patch(monkeypatch, rt, job, _plan)
        out = asyncio.run(rt._plan_deep_research(str(job.id)))

        assert out["status"] == "canceled"
        assert job.status == "canceled" and job.plan is None


class _RecordingSession(_FakeSession):
    """실행한 문장 객체를 남긴다 — UPDATE 에 실제로 실은 값을 읽기 위해서다."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.stmts: list = []

    async def execute(self, stmt, params=None):
        self.stmts.append(stmt)
        return await super().execute(stmt, params)


def _update_values(stmt) -> dict:
    return {getattr(k, "key", k): (v.value if isinstance(v, BindParameter) else v)
            for k, v in stmt._values.items()}


class TestStepEvents:
    """단계가 열리고 닫힐 때 화면에 알린다. 닫을 때는 저장한 result 를 그대로 싣는다 —
    라이브로 본 장면과 끝난 뒤 다시 연 장면이 같아야 한다."""

    def _capture(self, monkeypatch, rt) -> list[tuple]:
        events: list[tuple] = []

        async def _publish(job_id, kind, payload):
            events.append((job_id, kind, payload))

        monkeypatch.setattr(rt, "publish", _publish)
        return events

    def test_opening_a_step_announces_it_running(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        jid = uuid.uuid4()

        step = asyncio.run(rt._step(_FakeSession(scalar=41), jid, 4, "search", "하위1",
                                    subq_idx=0, detail="검색 중"))

        assert step.id == 41
        assert events == [(jid, "step", {
            "seq": 4, "step_kind": "search", "subq_idx": 0, "title": "하위1",
            "detail": "검색 중", "status": "running",
        })]

    def test_step_is_announced_after_its_row_is_committed(self, monkeypatch):
        # 커밋 전에 알리면 그 틈에 재접속한 화면은 스냅샷에 없는 단계를 이벤트로만 받는다
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=41)
        commits_at_publish = []

        async def _publish(job_id, kind, payload):
            commits_at_publish.append(db.commits)

        monkeypatch.setattr(rt, "publish", _publish)
        asyncio.run(rt._step(db, uuid.uuid4(), 0, "plan", "연구 계획 수립"))

        assert commits_at_publish == [1]

    def test_closing_a_step_streams_the_result_it_saved(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        jid = uuid.uuid4()
        db = _RecordingSession(scalar=41)
        step = asyncio.run(rt._step(db, jid, 4, "search", "하위1", subq_idx=0))
        result = {"queries": ["q1"], "rounds": [{"round": 1, "query": "q1"}]}

        asyncio.run(rt._finish(db, step, "done", result))

        saved = _update_values(db.stmts[-1])
        assert saved["status"] == "done" and saved["result"] == result
        assert events[-1] == (jid, "step", {
            "seq": 4, "step_kind": "search", "subq_idx": 0, "title": "하위1",
            "detail": None, "status": "done", "result": result,
        })

    def test_closing_without_result_streams_an_empty_result(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        db = _FakeSession(scalar=7)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 0, "synthesize", "보고서 종합"))

        asyncio.run(rt._finish(db, step, "failed"))

        assert events[-1][2]["status"] == "failed" and events[-1][2]["result"] == {}

    def test_closing_can_announce_a_lighter_result(self, monkeypatch):
        # 종합 단계는 절 미리보기를 저장만 하고 알리지 않는다 — synth 이벤트가 이미 날랐다
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        db = _RecordingSession(scalar=7)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 0, "synthesize", "보고서 종합"))
        saved = {"error": "취소됨", "sections": [{"idx": 0, "section": {"heading": "h"}}],
                 "evidence": {"E1": {}}}
        light = {"error": "취소됨", "sections": [{"idx": 0}]}

        asyncio.run(rt._finish(db, step, "failed", saved, event_result=light))

        assert _update_values(db.stmts[-1])["result"] == saved
        assert events[-1][2]["result"] == light

    def test_unknown_step_kind_is_not_announced(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        with pytest.raises(AssertionError):
            asyncio.run(rt._step(_FakeSession(scalar=1), uuid.uuid4(), 0, "critique", "점검"))
        assert events == []


def _statuses(h: _Harness) -> list[dict]:
    return [e[1] for e in h.events if e[0] == "status"]


class TestStatusEvents:
    """상태·단계가 바뀔 때마다 알린다 — 스트림에 붙은 화면이 폴링 없이 따라온다.
    종료 상태는 기존 종료 프레임이 알리므로 status 로 따로 내지 않는다."""

    def test_run_announces_exploring_then_synthesizing(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert _statuses(h) == [
            {"status": "running", "stage": "planned"},
            {"status": "running", "stage": "explored"},
        ]
        assert h.events[-1] == ("terminal", "completed", None)

    def test_resumed_run_goes_straight_to_synthesis(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert _statuses(h) == [{"status": "running", "stage": "explored"}]

    def test_checkpoint_lost_to_cancel_is_not_announced(self, monkeypatch):
        # 취소에 진 전이를 알리면 화면이 취소된 잡을 "종합 중"으로 그린다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _cancel(state, subq):
            job.status = "canceled"

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_cancel)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert _statuses(h) == [{"status": "running", "stage": "planned"}]
        assert _terminals(h) == [("canceled", None)]

    def test_skipped_redelivery_announces_nothing(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="running")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert h.events == []

    def test_plan_announces_planning_then_awaiting_approval(self, monkeypatch):
        """계획 단계에 붙은 스트림은 이 이벤트가 없으면 계획이 끝난 것을 모른다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            return ["하위1", "하위2"]

        h = TestPlan()._patch(monkeypatch, rt, job, _plan)
        asyncio.run(rt._plan_deep_research(str(job.id)))

        assert _statuses(h) == [
            {"status": "planning", "stage": "created"},
            {"status": "awaiting_approval", "stage": "planned"},
        ]

    def test_failed_plan_announces_only_planning(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            raise ValueError("계획을 해석하지 못했다")

        h = TestPlan()._patch(monkeypatch, rt, job, _plan)
        asyncio.run(rt._plan_deep_research(str(job.id)))

        assert _statuses(h) == [{"status": "planning", "stage": "created"}]
        assert [t[0] for t in _terminals(h)] == ["failed"]


_ROUNDS = [
    {"round": 1, "query": "하위1", "found_chunks": 4, "new_papers": 3,
     "verdict": "insufficient", "note": "부족", "next_query": "보완 검색어"},
    {"round": 2, "query": "보완 검색어", "found_chunks": 2, "new_papers": 1,
     "verdict": "sufficient", "note": "충분", "next_query": None},
]


def _bare(idx: int, status: str) -> dict:
    """info 없이 부른 절의 기록 — 절 머리·시각을 모른다."""
    return {"idx": idx, "status": status, "subq_idx": None, "heading": None,
            "started_at": None, "duration_ms": None}


def _synth_info(idx: int, *, done: bool = False) -> dict:
    """synthesize 가 on_section 에 넘기는 info 대역. 끝난 절이면 다듬은 절과 그 근거를 더한다."""
    info = {"subq_idx": idx, "heading": f"하위{idx + 1}", "headings": ["하위1", "하위2"]}
    if done:
        eid, chunk = f"E{idx}", f"c{idx}"
        info["section"] = {
            "heading": f"하위{idx + 1}", "intro": f"도입 [{eid}].", "future": [],
            "papers": [{"cnts_id": f"C{idx}", "summary": "요약", "evidence": [eid]}],
            "evidence_chunks": {eid: [chunk]}, "chunk_scores": {chunk: 0.9},
        }
        info["evidence"] = {eid: {
            "cnts_id": f"C{idx}", "meta": {"title": f"논문 {idx}"},
            "chunks": [{"chunk_id": chunk, "text": "대목", "page_start": 1, "page_end": 1,
                        "score": 0.9}],
        }}
    return info


class TestStepResults:
    """이벤트로 흘린 것은 research_steps.result 에도 남는다 — 끝난 잡을 다시 열어도
    자기점검·종합 진행 장면을 재생할 수 있어야 한다."""

    def test_search_step_result_carries_round_history(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _two_rounds(state, subq):
            subq.rounds = [dict(r) for r in _ROUNDS]

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_two_rounds)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert h.finished[0][2]["rounds"] == _ROUNDS

    def test_failed_search_step_keeps_the_rounds_done_so_far(self, monkeypatch):
        # 실패 화면의 "멈춘 지점"이 여기서 온다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])

        async def _fails_in_round_two(state, subq):
            if subq.idx == 0:
                subq.rounds = [dict(_ROUNDS[0])]
                raise ConnectionError("재검색 중 끊김")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_fails_in_round_two)
        asyncio.run(rt._run_deep_research(str(job.id)))

        _, status, result, _ = h.finished[0]
        assert status == "failed"
        assert result["rounds"] == [_ROUNDS[0]] and "끊김" in result["error"]

    def test_synthesis_progress_is_streamed_and_saved(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = None

        async def _two_sections(state, should_stop):
            for idx, status in ((0, "running"), (0, "done"), (1, "running"), (1, "failed")):
                await h.on_section(idx, 2, status)
            return {"sections": [{}, {}]}

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_two_sections)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [e[1] for e in h.events if e[0] == "synth"] == [
            {"section_idx": 0, "total": 2, "status": "running"},
            {"section_idx": 0, "total": 2, "status": "done"},
            {"section_idx": 1, "total": 2, "status": "running"},
            {"section_idx": 1, "total": 2, "status": "failed"},
        ]
        _, status, result, _ = h.finished[-1]
        assert status == "done"
        # info 없이 불러도(옛 호출) 이벤트는 옛 모양 그대로고, 기록은 모르는 칸을 비워 둔다
        assert result == {"sections_total": 2, "headings": [],
                          "sections": [_bare(0, "done"), _bare(1, "failed")]}

    def test_failed_synthesis_keeps_the_sections_done_so_far(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = None

        async def _second_raises(state, should_stop):
            await h.on_section(0, 2, "running")
            await h.on_section(0, 2, "done")
            await h.on_section(1, 2, "running")
            raise ValueError("종합 호출 실패")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_second_raises)
        asyncio.run(rt._run_deep_research(str(job.id)))

        _, status, result, _ = h.finished[-1]
        assert status == "failed"
        assert result == {"error": "종합 호출 실패", "sections_total": 2, "headings": [],
                          "sections": [_bare(0, "done"), _bare(1, "running")]}

    def test_canceled_synthesis_keeps_the_sections_done_so_far(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = None

        async def _canceled_after_first(state, should_stop):
            await h.on_section(0, 3, "running")
            await h.on_section(0, 3, "done")
            job.status = "canceled"
            raise rt.SynthesisCanceled()

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_canceled_after_first)
        asyncio.run(rt._run_deep_research(str(job.id)))

        _, status, result, _ = h.finished[-1]
        assert status == "failed"
        assert result == {"error": "취소됨", "sections_total": 3, "headings": [],
                          "sections": [_bare(0, "done")]}

    def test_report_without_sections_saves_zero_total(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert h.finished[-1][2] == {"sections_total": 0, "headings": [], "sections": []}


class _FailingUpdateSession(_FakeSession):
    """UPDATE 만 실패한다 — 진행 기록이 깨져도 탐색이 계속되는지 본다."""

    async def execute(self, stmt, params=None):
        if getattr(stmt, "is_update", False):
            raise ConnectionError("DB 연결 끊김")
        return await super().execute(stmt, params)


class TestSaveProgress:
    """도는 중인 단계의 result 를 지금까지의 진행으로 덮어쓰고 알린다 — 탐색 중에 새로
    연 화면이 스냅샷만으로 앞 회차를 되살린다."""

    def test_running_step_result_is_overwritten_and_announced(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        jid = uuid.uuid4()
        db = _RecordingSession(scalar=41)
        step = asyncio.run(rt._step(db, jid, 4, "search", "하위1", subq_idx=0))
        result = {"rounds": [dict(_ROUNDS[0])],
                  "counters": {"papers_reviewed": 3, "evidence_adopted": 1, "rechecks": 0}}

        asyncio.run(rt._save_progress(db, step, result))

        # 단계를 닫지 않는다 — status·finished_at 은 _finish 몫이다
        assert _update_values(db.stmts[-1]) == {"result": result}
        assert db.commits == 2
        assert events[-1] == (jid, "step", {
            "seq": 4, "step_kind": "search", "subq_idx": 0, "title": "하위1",
            "detail": None, "status": "running", "result": result,
        })

    def test_db_failure_does_not_stop_exploration(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        db = _FailingUpdateSession(scalar=41)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 4, "search", "하위1", subq_idx=0))

        asyncio.run(rt._save_progress(db, step, {"rounds": []}))

        assert db.rollbacks == 1
        assert [e[2]["status"] for e in events] == ["running"]
        assert "result" not in events[-1][2]

    def test_time_limit_is_not_swallowed(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        TestStepEvents()._capture(monkeypatch, rt)
        db = _FakeSession(scalar=41)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 4, "search", "하위1", subq_idx=0))

        async def _limit(stmt, params=None):
            raise rt.SoftTimeLimitExceeded()

        db.execute = _limit
        with pytest.raises(rt.SoftTimeLimitExceeded):
            asyncio.run(rt._save_progress(db, step, {"rounds": []}))

    def test_event_result_is_announced_instead_of_the_saved_result(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        db = _RecordingSession(scalar=41)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 5, "synthesize", "보고서 종합"))
        saved = {"sections_total": 2, "sections": [{"idx": 0, "section": {"heading": "h"}}],
                 "evidence": {"E1": {}}}
        light = {"sections_total": 2, "sections": [{"idx": 0}]}

        asyncio.run(rt._save_progress(db, step, saved, event_result=light))

        assert _update_values(db.stmts[-1]) == {"result": saved}
        assert events[-1][2]["status"] == "running" and events[-1][2]["result"] == light


class TestLiveProgress:
    """회차·절이 끝날 때마다 진행을 단계 result 에 남긴다 — 카운터와 회차 이력이 끝날
    때만 저장되면 탐색 중에 새로 연 화면은 다음 이벤트까지 빈칸이다."""

    def test_each_critique_saves_rounds_and_counters(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = None

        async def _two_rounds(state, subq):
            for r in _ROUNDS:
                subq.rounds.append(dict(r))
                state.seen_cnts.add(f"P{r['round']}")
                await h.emit("search", {"subq_idx": 0, "query": r["query"], "found": 1})
                await h.emit("critique", {"subq_idx": 0, "verdict": r["verdict"]})

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_two_rounds)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [([r["round"] for r in res["rounds"]], res["counters"]["papers_reviewed"])
                for _, res in h.progress] == [([1], 1), ([1, 2], 2)]
        # 진행을 남겨도 이벤트는 그대로 흐른다
        assert [e[0] for e in h.events if e[0] in ("search", "critique")] == [
            "search", "critique", "search", "critique"]

    def test_finished_search_step_keeps_counters(self, monkeypatch):
        # 다음 하위질문의 첫 회차 전까지 재접속한 화면은 이 값을 카운터로 쓴다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])

        async def _saw_papers(state, subq):
            state.seen_cnts.add(f"P{subq.idx}")
            if subq.idx == 1:
                raise ConnectionError("끊김")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_saw_papers)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [f[2]["counters"]["papers_reviewed"] for f in h.finished[:2]] == [1, 2]

    def test_saved_counters_include_papers_excluded_in_the_round(self, monkeypatch):
        """counters 이벤트는 검색 직후라 이번 회차의 제외를 모른다 — 회차를 닫으며 저장·알리는 단계 result
        와 닫힌 단계가 제외 수를 싣는다(재접속한 화면의 카운터 '제외' 칸 원천)."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = None

        async def _excluding_round(state, subq):
            subq.rounds.append({**_ROUNDS[0], "excluded": 2})
            await h.emit("critique", {"subq_idx": 0, "verdict": "insufficient", "excluded": 2})

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_excluding_round)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [res["counters"]["excluded"] for _, res in h.progress] == [2]
        assert h.finished[0][2]["counters"]["excluded"] == 2

    def test_section_progress_is_saved_on_the_synthesis_step(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = None

        async def _one_section(state, should_stop):
            await h.on_section(0, 2, "running")
            await h.on_section(0, 2, "done")
            return {"sections": [{}]}

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_one_section)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [res for _, res in h.progress] == [
            {"sections_total": 2, "headings": [], "sections": [_bare(0, "running")]},
            {"sections_total": 2, "headings": [], "sections": [_bare(0, "done")]},
        ]


class TestSynthPreview:
    """다 쓴 절을 작성 중 초안으로 보여 준다. synth 이벤트가 절 내용을 절마다 한 번 나르고, 단계
    result 가 그것을 들고 있어 새로고침·재접속한 화면이 되살린다. step 이벤트는 가볍게 둔다."""

    _T0 = _dt.datetime(2026, 9, 28, 1, 2, 3, tzinfo=_dt.timezone.utc)

    def _progress(self, monkeypatch, rt, ticks=(10.0, 12.5)):
        monkeypatch.setattr(rt, "_now", lambda: self._T0)
        clock = iter(ticks)
        return rt._SynthProgress(uuid.uuid4(), clock=lambda: next(clock))

    def test_running_event_carries_heading_and_start_time(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        progress = self._progress(monkeypatch, rt)

        asyncio.run(progress(0, 2, "running", _synth_info(0)))

        assert events[-1][1:] == ("synth", {
            "section_idx": 0, "total": 2, "status": "running", "subq_idx": 0,
            "heading": "하위1", "headings": ["하위1", "하위2"],
            "started_at": "2026-09-28T01:02:03+00:00",
        })

    def test_done_event_carries_duration_section_and_evidence(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        progress = self._progress(monkeypatch, rt)
        done = _synth_info(0, done=True)

        asyncio.run(progress(0, 2, "running", _synth_info(0)))
        asyncio.run(progress(0, 2, "done", done))

        # 소요 시간은 워커가 잰 값이다 — 화면 시계와 무관하다
        assert events[-1][1:] == ("synth", {
            "section_idx": 0, "total": 2, "status": "done", "subq_idx": 0,
            "heading": "하위1", "headings": ["하위1", "하위2"], "duration_ms": 2500,
            "section": done["section"], "evidence": done["evidence"],
        })

    def test_call_without_info_keeps_the_old_event(self, monkeypatch):
        # info 를 모르는 호출과 호환 — 이벤트는 옛 모양 그대로다
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        progress = rt._SynthProgress(uuid.uuid4())

        asyncio.run(progress(0, 1, "running"))

        assert events[-1][2] == {"section_idx": 0, "total": 1, "status": "running"}
        assert progress.result() == {"sections_total": 1, "headings": [],
                                     "sections": [_bare(0, "running")]}

    def test_result_keeps_previews_and_merges_evidence(self, monkeypatch):
        # 한 논문이 두 절에 실리면 절마다 제 대목만 온다 — 합쳐야 앞 절 칩의 대목이 남는다
        rt = _load_tasks(monkeypatch)
        TestStepEvents()._capture(monkeypatch, rt)
        progress = self._progress(monkeypatch, rt, ticks=(0.0, 1.0, 2.0, 4.0))
        first, second = _synth_info(0, done=True), _synth_info(1, done=True)
        second["evidence"]["E0"] = {**first["evidence"]["E0"], "chunks": [
            {"chunk_id": "c0b", "text": "하위2 대목", "page_start": 4, "page_end": 4,
             "score": 0.95}]}

        for idx, info in ((0, first), (1, second)):
            asyncio.run(progress(idx, 2, "running", _synth_info(idx)))
            asyncio.run(progress(idx, 2, "done", info))

        full = progress.result()
        assert [s["section"] for s in full["sections"]] == [first["section"], second["section"]]
        assert [s["duration_ms"] for s in full["sections"]] == [1000, 2000]
        assert set(full["evidence"]) == {"E0", "E1"}
        assert [c["chunk_id"] for c in full["evidence"]["E0"]["chunks"]] == ["c0b", "c0"]

        light = progress.result(previews=False)
        assert "evidence" not in light
        assert all("section" not in s for s in light["sections"])
        assert light["headings"] == ["하위1", "하위2"]
        assert light["sections"][0]["started_at"] == "2026-09-28T01:02:03+00:00"

    def test_result_handed_out_earlier_does_not_change(self, monkeypatch):
        # 저장·알림에 넘긴 값을 뒤따르는 절이 고치면 앞서 저장한 기록이 바뀐다
        rt = _load_tasks(monkeypatch)
        TestStepEvents()._capture(monkeypatch, rt)
        progress = rt._SynthProgress(uuid.uuid4())
        first, second = _synth_info(0, done=True), _synth_info(1, done=True)
        second["evidence"] = {"E0": {**first["evidence"]["E0"], "chunks": [
            {"chunk_id": "c0b", "text": "하위2 대목", "page_start": 4, "page_end": 4,
             "score": 0.95}]}}

        asyncio.run(progress(0, 2, "done", first))
        before = progress.result()
        asyncio.run(progress(1, 2, "done", second))

        assert [c["chunk_id"] for c in before["evidence"]["E0"]["chunks"]] == ["c0"]

    def _run(self, monkeypatch, rt, *, stop_with: Exception | None = None,
             cancel_late: bool = False, patch=None):
        """절 0 을 끝내고 절 1 을 쓰기 시작한다. stop_with 가 없으면 절 1 도 끝내고 완료한다.
        cancel_late 면 절 1 의 LLM 을 기다리는 동안 취소가 들어온다 — synthesize 는 LLM 을
        부르기 직전에만 멈춤을 보므로 보고서를 돌려준 뒤 완료 전이에서야 걸린다.
        patch(h) 는 대역을 세운 뒤, 잡을 돌리기 전에 부른다 — 대역 위에 기록을 더 끼울 때 쓴다."""
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        ref = {}

        async def _synth(state, should_stop):
            h = ref["h"]
            await h.on_section(0, 2, "running", _synth_info(0))
            await h.on_section(0, 2, "done", _synth_info(0, done=True))
            await h.on_section(1, 2, "running", _synth_info(1))
            if stop_with is not None:
                if isinstance(stop_with, rt.SynthesisCanceled):
                    job.status = "canceled"
                raise stop_with
            if cancel_late:
                job.status = "canceled"
            await h.on_section(1, 2, "done", _synth_info(1, done=True))
            return {"sections": [{}, {}]}

        ref["h"] = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                                   synthesize=_synth)
        if patch is not None:
            patch(ref["h"])
        asyncio.run(rt._run_deep_research(str(job.id)))
        return ref["h"]

    def test_saved_progress_carries_previews_but_step_events_do_not(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt)

        # 새로고침한 화면은 저장된 result 에서 이미 쓴 절을 되살린다
        saved = h.progress[-1][1]
        assert [s["section"] for s in saved["sections"]] == [
            _synth_info(0, done=True)["section"], _synth_info(1, done=True)["section"]]
        assert set(saved["evidence"]) == {"E0", "E1"}
        # 절 내용은 synth 이벤트가 절마다 한 번만 나른다 — step 이벤트는 매번 가볍다
        assert ["section" in e[1] for e in h.events if e[0] == "synth"] == [
            False, True, False, True]
        assert len(h.announced) == 5          # 진행 저장 4번 + 닫기 1번
        for _, _, res in h.announced:
            assert "evidence" not in res
            assert all("section" not in s for s in res["sections"])

    def test_completed_step_drops_previews(self, monkeypatch):
        # 완료 뒤에는 최종 보고서가 같은 내용을 들고 있다 — 단계 result 에 두 벌 두지 않는다
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt)

        _, status, result, _ = h.finished[-1]
        assert status == "done"
        assert "evidence" not in result
        assert [(s["idx"], s["status"], s["heading"]) for s in result["sections"]] == [
            (0, "done", "하위1"), (1, "done", "하위2")]
        assert all("section" not in s for s in result["sections"])

    def test_failed_step_keeps_the_draft(self, monkeypatch):
        # 멈춘 초안을 보여 주고 내려받는 원천이다
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt, stop_with=ValueError("종합 호출 실패"))

        _, status, result, _ = h.finished[-1]
        assert status == "failed" and result["error"] == "종합 호출 실패"
        assert result["sections"][0]["section"] == _synth_info(0, done=True)["section"]
        assert "section" not in result["sections"][1]
        assert result["evidence"] == _synth_info(0, done=True)["evidence"]
        _, announced_status, announced = h.announced[-1]
        assert announced_status == "failed" and announced["error"] == "종합 호출 실패"
        assert "evidence" not in announced
        assert all("section" not in s for s in announced["sections"])

    def test_canceled_step_keeps_the_draft(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt, stop_with=rt.SynthesisCanceled())

        _, status, result, _ = h.finished[-1]
        assert status == "failed" and result["error"] == "취소됨"
        assert result["sections"][0]["section"] == _synth_info(0, done=True)["section"]
        assert result["evidence"] == _synth_info(0, done=True)["evidence"]
        _, _, announced = h.announced[-1]
        assert announced["error"] == "취소됨" and "evidence" not in announced

    def test_cancel_during_the_last_section_keeps_the_draft(self, monkeypatch):
        # 완료 전이가 취소에 지면 보고서는 버려진다 — 미리보기까지 지우면 초안도 보고서도 없다
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt, cancel_late=True)

        assert h.session.job.status == "canceled" and h.session.job.report is None
        assert _terminals(h) == [("canceled", None)]
        _, status, result, _ = h.finished[-1]
        assert status == "failed" and result["error"] == "취소됨"
        assert [s["section"] for s in result["sections"]] == [
            _synth_info(0, done=True)["section"], _synth_info(1, done=True)["section"]]
        assert set(result["evidence"]) == {"E0", "E1"}
        _, announced_status, announced = h.announced[-1]
        assert announced_status == "failed" and announced["error"] == "취소됨"
        assert "evidence" not in announced
        assert all("section" not in s for s in announced["sections"])

    def test_lost_completion_closes_the_step_once(self, monkeypatch):
        # done 으로 먼저 닫았다가 failed 로 다시 닫으면 화면에 done 이 한 번 스친다
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt, cancel_late=True)

        assert [f[1] for f in h.finished] == ["failed"]

    def test_step_is_closed_done_after_the_report_is_saved(self, monkeypatch):
        # 전이보다 먼저 미리보기를 지운 done 으로 닫으면, 그 틈에 데드라인에 걸린 잡은 보고서도 초안도 없다
        rt = _load_tasks(monkeypatch)
        seen = []

        def _patch(h):
            closing = rt._finish

            async def _finish(db, step, status, result=None, event_result=None):
                seen.append((status, h.session.job.status, h.session.job.report))
                await closing(db, step, status, result, event_result)

            monkeypatch.setattr(rt, "_finish", _finish)

        self._run(monkeypatch, rt, patch=_patch)

        assert seen == [("done", "completed", {"sections": [{}, {}]})]

    def test_completion_drops_drafts_of_earlier_attempts_after_announcing(self, monkeypatch):
        # 완료를 먼저 알린다 — 정리가 늘어지거나 실패해도 화면은 완료를 받는다
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt)

        assert h.drops == [(1, [("completed", None)])]

    @pytest.mark.parametrize("stop", ["failed", "canceled", "lost_completion"])
    def test_attempt_that_does_not_complete_leaves_earlier_drafts(self, monkeypatch, stop):
        rt = _load_tasks(monkeypatch)
        stop_with = {"failed": ValueError("종합 호출 실패"),
                     "canceled": rt.SynthesisCanceled()}.get(stop)
        h = self._run(monkeypatch, rt, stop_with=stop_with, cancel_late=stop == "lost_completion")

        assert h.drops == []

    def test_six_sections_of_thirty_papers_stay_at_report_scale(self, monkeypatch):
        """대목 원문이 대부분이라 미리보기는 최종 보고서와 같은 규모여야 하고, 절마다 알리는
        step 이벤트는 대목 길이와 무관하게 작아야 한다(spec §14-2 크기)."""
        from services.research import synthesizer
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        for i in range(6):
            eids = [f"E{i * 5 + k + 1}" for k in range(5)]
            st.subquestions.append(SubQuestion(idx=i, text=f"하위질문 {i + 1}", evidence_ids=eids))
            for eid in eids:
                # 청크 상한(MAX_CHUNK_TOKENS=1024)에 가까운 1,500자 대목 2개
                st.evidence[eid] = Evidence(
                    id=eid, cnts_id=f"C{eid}", meta={"title": f"논문 {eid}", "authors": "홍길동"},
                    chunks=[Chunk(f"{eid}-{j}", "가" * 1500, j, j, 0.9 - j / 10) for j in range(2)])
        reply = json.dumps({
            "intro": "이 절은 연구 흐름을 정리한다 [E1]. " * 3,
            "summaries": {f"E{n}": "무엇을 했고 무엇을 밝혔는지 요약한다. " * 3 for n in range(1, 31)},
            "future": [{"text": "남은 과제를 적는다."}],
        }, ensure_ascii=False)

        async def fake_chat(messages, *, params=None, timeout=None):
            return reply

        monkeypatch.setattr(synthesizer, "chat", fake_chat)
        progress = rt._SynthProgress(uuid.uuid4())
        report = asyncio.run(rt.synthesize(st, on_section=progress))

        def size(value) -> int:
            return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))

        # 대목 1,500자(4.5KB) × 2 × 30편 ≈ 270KB — 최종 보고서의 evidence 와 같은 규모
        assert size(progress.result()) < size(report) * 1.1
        assert size(progress.result()) < 400_000
        assert size(progress.result(previews=False)) < 3_000
        per_section = [size(e[2]) for e in events if e[1] == "synth" and e[2]["status"] == "done"]
        assert len(per_section) == 6 and max(per_section) < size(report) / 4


class _StepTableSession(_FakeSession):
    """research_steps 행을 들고, 그 테이블의 INSERT·UPDATE·SELECT 를 실제로 적용한다.

    닫는 쓰기가 진행 중 저장한 result 를 합치는지(jsonb ||) 통째로 바꾸는지는 SQL
    문자열로는 확인이 약하다 — 값으로 확인한다. 모르는 식을 만나면 조용히 넘기지 않고
    터뜨려, 대역이 모르는 구현을 통과시키지 않게 한다.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self.steps: list[types.SimpleNamespace] = []

    async def execute(self, stmt, params=None):
        if getattr(stmt, "is_select", False) and [
                f.name for f in stmt.get_final_froms()] == ["research_steps"]:
            self.sql.append(str(stmt))
            self.params.append(params)
            self.in_txn = True
            hit = [row for row in self.steps if self._matches(stmt.whereclause, row)]
            return _Result(rows=[tuple(getattr(row, c.key) for c in stmt.selected_columns)
                                 for row in hit])
        if getattr(getattr(stmt, "table", None), "name", None) != "research_steps":
            return await super().execute(stmt, params)
        self.sql.append(str(stmt))
        self.params.append(params)
        self.in_txn = True
        if getattr(stmt, "is_insert", False):
            row = types.SimpleNamespace(id=len(self.steps) + 1, result={}, finished_at=None)
            for key, value in stmt._values.items():
                setattr(row, getattr(key, "key", key), self._eval(value, row))
            self.steps.append(row)
            return _Result(row.id)
        assert getattr(stmt, "is_update", False), f"대역이 모르는 문장: {stmt}"
        hit = [row for row in self.steps if self._matches(stmt.whereclause, row)]
        for row in hit:
            for key, value in stmt._values.items():
                setattr(row, getattr(key, "key", key), self._eval(value, row))
        return _Result(rowcount=len(hit))

    def _matches(self, clause, row) -> bool:
        if isinstance(clause, BooleanClauseList):
            return all(self._matches(c, row) for c in clause.clauses)
        if isinstance(clause, Grouping) and isinstance(clause.element, Exists):
            # EXISTS (SELECT research_jobs.id WHERE ...) — 잡 행에 대해 평가한다
            inner = clause.element.element.element
            return self.job is not None and _matches(inner.whereclause, self.job)
        return _matches(clause, row)

    @staticmethod
    def _eval(value, row):
        if isinstance(value, BindParameter):
            return value.value
        if (isinstance(value, BinaryExpression) and value.operator is operators.concat_op
                and getattr(value.left, "key", None) == "result"
                and isinstance(value.right, BindParameter)):
            # jsonb || jsonb — 같은 키는 오른쪽이 이긴다
            return {**row.result, **value.right.value}
        raise AssertionError(f"대역이 모르는 값 식: {value!r}")


class TestOrphanStepsKeepProgress:
    """시간 상한·가드 밖 예외로 잡을 닫을 때 running 단계에 진행 중 저장한 result
    (rounds·counters·sections)를 지우지 않고 error 만 더한다.

    회수기(reap_stale_research)는 `result || {"error": ...}` 로 합친다. 이 경로만
    통째로 바꾸면 어느 경로로 실패했는지에 따라 다시 연 화면이 달라진다 — 라이브로
    2회차까지 본 하위질문이 다시 열면 오류 문구만 남고, 카운터가 앞 하위질문 값으로 돌아간다.
    """

    _PROGRESS = {
        "rounds": [{"round": 1, "query": "q1"}, {"round": 2, "query": "q2"}],
        "counters": {"papers_reviewed": 31, "evidence_adopted": 9, "rechecks": 1},
    }

    def _row(self, db, job_id, *, status, result):
        row = types.SimpleNamespace(id=len(db.steps) + 1, job_id=job_id, status=status,
                                    result=dict(result), finished_at=None)
        db.steps.append(row)
        return row

    def test_closing_keeps_saved_keys_and_adds_error(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="failed")
        db = _StepTableSession(job=job)
        running = self._row(db, job.id, status="running", result=self._PROGRESS)
        done = self._row(db, job.id, status="done", result={"adopted": 3})

        asyncio.run(rt._close_orphan_steps(db, job.id, rt.TIMEOUT_ERROR))

        assert running.status == "failed" and running.finished_at is not None
        assert running.result == {**self._PROGRESS, "error": rt.TIMEOUT_ERROR}
        assert done.status == "done" and done.result == {"adopted": 3}

    def test_step_of_a_job_still_in_flight_is_left_alone(self, monkeypatch):
        # 회수 뒤 retry 한 새 실행의 step 일 수 있다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="running")
        db = _StepTableSession(job=job)
        running = self._row(db, job.id, status="running", result=self._PROGRESS)

        asyncio.run(rt._close_orphan_steps(db, job.id, rt.TIMEOUT_ERROR))

        assert running.status == "running" and running.result == self._PROGRESS

    def _run_until_deadline(self, monkeypatch, rt, job, harness: dict, **pipeline):
        """진짜 _step·_save_progress 로 진행을 쌓다가 JOB_DEADLINE 에 끊긴다.

        explore·synthesize 대역이 emit·on_section 을 쓰도록 harness["h"] 에 하네스를 둔다."""
        real = {name: getattr(rt, name) for name in ("_step", "_save_progress")}
        db = _StepTableSession(job=job, scalar=0)
        harness["h"] = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                                       session=db, **pipeline)
        for name, fn in real.items():
            monkeypatch.setattr(rt, name, fn)
        monkeypatch.setattr(rt, "JOB_DEADLINE", 0.3)
        return rt._run_job(rt._run_deep_research, str(job.id)), db

    def test_deadline_keeps_rounds_and_counters_of_the_running_search(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        harness = {}

        async def _two_rounds_then_hang(state, subq):
            for r in _ROUNDS:
                subq.rounds.append(dict(r))
                state.seen_cnts.add(f"P{r['round']}")
                await harness["h"].emit("critique", {"subq_idx": 0, "verdict": r["verdict"]})
            await asyncio.sleep(5)      # 3회차 자기점검 LLM 이 늘어진다

        out, db = self._run_until_deadline(monkeypatch, rt, job, harness,
                                           explore=_two_rounds_then_hang)

        assert out["status"] == "failed" and job.status == "failed"
        (step,) = db.steps
        assert step.kind == "search" and step.status == "failed"
        assert step.result["error"] == rt.TIMEOUT_ERROR
        assert [r["round"] for r in step.result["rounds"]] == [1, 2]
        assert step.result["counters"]["papers_reviewed"] == 2

    def test_deadline_keeps_sections_of_the_running_synthesis(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        harness = {}

        async def _one_section_then_hang(state, should_stop):
            await harness["h"].on_section(0, 2, "done", _synth_info(0, done=True))
            await harness["h"].on_section(1, 2, "running", _synth_info(1))
            await asyncio.sleep(5)      # 두 번째 절 LLM 이 늘어진다

        out, db = self._run_until_deadline(monkeypatch, rt, job, harness,
                                           synthesize=_one_section_then_hang)

        assert out["status"] == "failed" and job.status == "failed"
        (step,) = db.steps
        assert step.kind == "synthesize" and step.status == "failed"
        assert step.result["error"] == rt.TIMEOUT_ERROR
        assert [(s["idx"], s["status"]) for s in step.result["sections"]] == [
            (0, "done"), (1, "running")]
        # 시간 상한으로 닫혀도 멈춘 초안(다 쓴 절과 그 근거)이 남는다
        assert step.result["sections"][0]["section"] == _synth_info(0, done=True)["section"]
        assert step.result["evidence"] == _synth_info(0, done=True)["evidence"]
        assert step.result["sections"][1]["started_at"] is not None


class TestDropStalePreviews:
    """재시도가 완료되면 이전 시도의 종합 단계에 남은 멈춘 초안(절 미리보기·근거)을 걷는다.

    화면은 최신 시도의 단계만 읽는다. 남겨 두면 완성된 보고서를 열 때마다 GET·스냅샷이 아무도
    읽지 않는 수백 KB 를 더 나르고, 재시도를 거듭할수록 쌓인다.
    """

    _LIGHT = {"sections_total": 2, "headings": ["하위1", "하위2"],
              "sections": [_bare(0, "done"), _bare(1, "running")]}

    def _draft(self, error: str) -> dict:
        done = _synth_info(0, done=True)
        return {"error": error, **self._LIGHT,
                "sections": [{**_bare(0, "done"), "section": done["section"]}, _bare(1, "running")],
                "evidence": done["evidence"]}

    def _row(self, db, job_id, seq, kind, result):
        row = types.SimpleNamespace(id=len(db.steps) + 1, job_id=job_id, seq=seq, kind=kind,
                                    status="failed", result=result, finished_at=None)
        db.steps.append(row)
        return row

    def _step(self, rt, row):
        return rt._StepRef(row.id, row.job_id, row.seq, row.kind, "보고서 종합", None, None)

    def test_earlier_synthesis_steps_of_the_job_lose_their_drafts(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="synthesized", plan=["하위1"], status="completed")
        db = _StepTableSession(job=job)
        search = self._row(db, job.id, 1, "search", dict(TestOrphanStepsKeepProgress._PROGRESS))
        failed = self._row(db, job.id, 2, "synthesize", self._draft("종합 호출 실패"))
        timed_out = self._row(db, job.id, 3, "synthesize", self._draft(rt.TIMEOUT_ERROR))
        # 지금 시도의 단계 — 이미 가볍게 닫혔지만, 걸러 내는 조건이 seq 로 가르는지 보려고 초안을 둔다
        current = self._row(db, job.id, 4, "synthesize", self._draft("지금 시도"))
        other_job = self._row(db, uuid.uuid4(), 2, "synthesize", self._draft("다른 잡"))

        asyncio.run(rt._drop_stale_previews(db, self._step(rt, current)))

        # 절 목록·시각·오류는 남긴다 — 멈춘 지점 표시는 그대로다
        assert failed.result == {"error": "종합 호출 실패", **self._LIGHT}
        assert timed_out.result == {"error": rt.TIMEOUT_ERROR, **self._LIGHT}
        assert current.result == self._draft("지금 시도")
        assert other_job.result == self._draft("다른 잡")
        assert search.result == TestOrphanStepsKeepProgress._PROGRESS
        assert db.commits == 1

    def test_rows_of_older_shapes_are_left_as_they_are(self, monkeypatch):
        # 보강 전 잡은 sections 가 정수고, 첫 절 전에 끊긴 단계는 error 만 있다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="synthesized", plan=["하위1"], status="completed")
        db = _StepTableSession(job=job)
        old = self._row(db, job.id, 1, "synthesize", {"sections": 3, "error": "옛 실패"})
        bare = self._row(db, job.id, 2, "synthesize", {"error": rt.TIMEOUT_ERROR})
        current = self._row(db, job.id, 3, "synthesize", dict(self._LIGHT))

        asyncio.run(rt._drop_stale_previews(db, self._step(rt, current)))

        assert old.result == {"sections": 3, "error": "옛 실패"}
        assert bare.result == {"error": rt.TIMEOUT_ERROR}
        # 걷을 것이 없는 행은 다시 쓰지 않는다
        assert not any(sql.startswith("UPDATE") for sql in db.sql)

    def test_failure_is_logged_not_raised(self, monkeypatch, caplog):
        # 잡은 이미 완료로 끝났다 — 크기 정리가 실패했다고 완료를 되돌리거나 태스크를 터뜨리지 않는다
        rt = _load_tasks(monkeypatch)
        db = _FakeSession()

        async def _broken(stmt, params=None):
            raise ConnectionError("DB 연결 끊김")

        db.execute = _broken
        step = rt._StepRef(9, uuid.uuid4(), 4, "synthesize", "보고서 종합", None, None)

        with caplog.at_level(logging.WARNING, logger="workers.research_tasks"):
            asyncio.run(rt._drop_stale_previews(db, step))

        assert "초안 정리 실패" in caplog.text


class TestReaper:
    class _SyncSession:
        """문장마다 회수 결과를 돌려준다. events 에 문장·COMMIT·ROLLBACK 을 순서대로 남긴다(테스트가
        대기 줄 빼기·디스패치 보내기를 같은 목록에 적어 커밋과의 순서를 본다)."""

        def __init__(self, *, reaped=("j1",), gens=0, idle=False, fail_on=None):
            self.sql: list[str] = []
            self.params: list = []
            self.events: list = []
            self._reaped, self._gens, self._idle, self._fail_on = list(reaped), gens, idle, fail_on

        def execute(self, stmt, params=None):
            sql = str(stmt)
            if self._fail_on and self._fail_on in sql:
                raise RuntimeError("DB 오류")
            self.sql.append(sql)
            self.params.append(params)
            self.events.append(sql)
            result = MagicMock()
            if "UPDATE research_jobs" in sql:
                result.one.return_value = (len(self._reaped), 2, list(self._reaped))
            elif "UPDATE research_generations" in sql:
                result.rowcount = self._gens
            elif "EXISTS" in sql:
                result.scalar_one.return_value = self._idle
            else:
                result.fetchall.return_value = [("s",)]
            return result

        def commit(self):
            self.events.append("COMMIT")

        def rollback(self):
            self.events.append("ROLLBACK")

        def close(self):
            self.events.append("CLOSE")

    @staticmethod
    def _reap(monkeypatch, rt, db, *, sent: bool = True) -> dict:
        monkeypatch.setattr(rt, "SyncSessionLocal", lambda: db)
        monkeypatch.setattr(rt, "unmark_many_sync", lambda ids: db.events.append(("unmark", list(ids))))

        def _send() -> bool:
            db.events.append("DISPATCH")
            return sent

        monkeypatch.setattr(rt, "send_dispatch", _send)
        return rt.reap_stale_research()

    @staticmethod
    def _at(db, needle: str) -> int:
        return next(i for i, e in enumerate(db.events) if isinstance(e, str) and needle in e)

    def test_reaper_has_soft_and_hard_time_limits(self, monkeypatch):
        """회수기는 제어 워커(한 칸)에서 디스패치 틱과 같은 q_control 을 쓴다 — 오래 붙잡지 않게 끊는다."""
        rt = _load_tasks(monkeypatch, fake_celery=True)
        assert (rt.reap_stale_research.soft_time_limit, rt.reap_stale_research.time_limit) == (60, 90)
        assert rt.reap_stale_research.queue == "q_control"

    def test_stale_threshold_exceeds_hard_limit(self, monkeypatch):
        """회수 임계가 하드 리밋보다 짧으면 아직 살아 있는 워커의 잡을 회수한다."""
        rt = _load_tasks(monkeypatch)
        assert rt.STALE_MINUTES * 60 > rt.HARD_LIMIT

    def test_reaping_a_job_closes_its_running_steps(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession()
        monkeypatch.setattr(rt, "SyncSessionLocal", lambda: db)

        out = rt.reap_stale_research()

        job_sql = next(s for s in db.sql if "UPDATE research_jobs" in s)
        # 회수한 잡의 running step 을 같은 문장에서 닫는다
        assert "UPDATE research_steps" in job_sql and "reaped" in job_sql
        assert out["jobs"] == 1

    def test_stale_running_generations_fail_in_the_same_transaction(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(gens=2)

        out = self._reap(monkeypatch, rt, db)

        i = self._at(db, "UPDATE research_generations")
        gen_sql = db.events[i]
        assert "SET status = 'failed'" in gen_sql and "WHERE status = 'running'" in gen_sql
        assert "coalesce(started_at, created_at) < now() - make_interval(secs => :s)" in gen_sql
        assert db.params[db.sql.index(gen_sql)] == {"s": rt.GEN_STALE_SECONDS}
        assert self._at(db, "UPDATE research_jobs") < i < db.events.index("COMMIT")
        assert out["generations"] == 2

    def test_generation_threshold_is_past_the_dispatch_hard_limit(self, monkeypatch):
        """회수 임계가 디스패치 태스크의 하드 리밋보다 짧으면 아직 도는 생성을 회수한다."""
        rt = _load_tasks(monkeypatch)
        work_tasks = sys.modules["workers.research_work_tasks"]
        assert rt.GEN_STALE_SECONDS == work_tasks.GEN_HARD_LIMIT + 60 == 1140

    def test_queued_work_with_nothing_running_is_dispatched_after_commit(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(gens=1, idle=True)

        out = self._reap(monkeypatch, rt, db)

        check = self._at(db, "EXISTS")
        check_sql = db.events[check]
        assert "status = 'queued'" in check_sql and "NOT EXISTS" in check_sql
        assert "status = 'running'" in check_sql
        # 방금 회수한 running 이 빠진 뒤에 세고, 커밋한 뒤에 보낸다 — 커밋 전에 보내면 디스패처가 아직
        # running 인 회수 대상을 보고 그냥 끝난다
        assert self._at(db, "UPDATE research_generations") < check < db.events.index("COMMIT")
        assert db.events.index("COMMIT") < db.events.index("DISPATCH")
        assert out["redispatched"] is True

    def test_no_dispatch_while_one_runs_or_nothing_waits(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(idle=False)

        out = self._reap(monkeypatch, rt, db)

        assert "DISPATCH" not in db.events
        assert out["redispatched"] is False

    def test_broker_down_is_reported_in_the_result(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(idle=True)

        out = self._reap(monkeypatch, rt, db, sent=False)

        assert "DISPATCH" in db.events and out["redispatched"] is False

    def test_reaped_jobs_leave_the_wait_line_after_commit(self, monkeypatch):
        """회수로 failed 가 된 잡만 대기 줄에서 뺀다 — 상태로 거른 잡 전체를 빼지 않는다."""
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(reaped=("j1", "j2"))

        out = self._reap(monkeypatch, rt, db)

        job_sql = db.events[self._at(db, "UPDATE research_jobs")]
        assert "RETURNING id" in job_sql and "array_agg(id::text)" in job_sql
        assert "NOT IN" not in job_sql
        assert db.events.index("COMMIT") < db.events.index(("unmark", ["j1", "j2"]))
        assert (out["jobs"], out["steps"]) == (2, 3)

    def test_nothing_reaped_leaves_redis_alone(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(reaped=())

        out = self._reap(monkeypatch, rt, db)

        assert not any(isinstance(e, tuple) for e in db.events)
        assert out == {"jobs": 0, "steps": 3, "generations": 0, "redispatched": False}

    def test_db_error_rolls_back_and_sends_nothing(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = self._SyncSession(reaped=("j1",), idle=True, fail_on="UPDATE research_generations")

        with pytest.raises(RuntimeError):
            self._reap(monkeypatch, rt, db)

        assert "ROLLBACK" in db.events and "COMMIT" not in db.events
        assert "DISPATCH" not in db.events and not any(isinstance(e, tuple) for e in db.events)

    def test_redispatch_goes_to_q_research_plan_even_when_the_setting_is_blank(self, monkeypatch):
        """회수기가 도는 celery-control 에는 RESEARCH_PLAN_QUEUE 가 없다 — 그래도 q_research_plan 으로 간다."""
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_llm")
        monkeypatch.setenv("RESEARCH_PLAN_QUEUE", "")
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch)
            kombu_exc = types.ModuleType("kombu.exceptions")
            kombu_exc.OperationalError = type("OperationalError", (Exception,), {})
            _stub_missing(monkeypatch, "kombu", types.ModuleType("kombu"))
            _stub_missing(monkeypatch, "kombu.exceptions", kombu_exc)
            sent = []
            sender = types.SimpleNamespace(send_task=lambda name, args=None, **kw: sent.append((name, kw)))
            monkeypatch.setattr(sys.modules["workers.research_work_tasks"], "celery_app", sender)
            db = self._SyncSession(idle=True)
            monkeypatch.setattr(rt, "SyncSessionLocal", lambda: db)
            monkeypatch.setattr(rt, "unmark_many_sync", lambda ids: None)

            out = rt.reap_stale_research()

            assert sent == [("tasks.dispatch_research_work", {"queue": "q_research_plan"})]
            assert out["redispatched"] is True
        finally:
            get_settings.cache_clear()


class TestQueue:
    """딥리서치 큐는 설정값이다 — 코드를 먼저 배포할 때는 q_llm, 전용 워커가 뜨면 q_research."""

    def test_default_queue_is_q_llm(self, monkeypatch):
        from core.config import get_settings
        monkeypatch.delenv("RESEARCH_QUEUE", raising=False)
        monkeypatch.delenv("RESEARCH_PLAN_QUEUE", raising=False)
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch, fake_celery=True)
            from workers.celery_app import celery_app
            assert rt.run_deep_research.queue == "q_llm"
            assert rt.plan_deep_research.queue == "q_llm"
            assert celery_app.conf.task_routes["tasks.run_deep_research"] == {"queue": "q_llm"}
        finally:
            get_settings.cache_clear()

    def test_queue_follows_setting(self, monkeypatch):
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_research")
        monkeypatch.delenv("RESEARCH_PLAN_QUEUE", raising=False)
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch, fake_celery=True)
            from workers.celery_app import celery_app
            assert rt.run_deep_research.queue == "q_research"
            assert rt.plan_deep_research.queue == "q_research"
            routes = celery_app.conf.task_routes
            assert routes["tasks.run_deep_research"] == {"queue": "q_research"}
            assert routes["tasks.plan_deep_research"] == {"queue": "q_research"}
            # 적재 LLM 단계는 그대로 q_llm 이다
            assert routes["tasks.stage_summarize"] == {"queue": "q_llm"}
        finally:
            get_settings.cache_clear()


    def test_plan_can_take_its_own_queue(self, monkeypatch):
        """전용 워커는 concurrency 1 이다. 계획(0.6초)이 실행(최대 25분)과 같은 큐면
        다른 잡이 도는 동안 새 질문이 created 로 멈춘다 — 계획만 따로 받는 큐를 둔다."""
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_research")
        monkeypatch.setenv("RESEARCH_PLAN_QUEUE", "q_research_plan")
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch, fake_celery=True)
            from workers.celery_app import celery_app
            assert rt.plan_deep_research.queue == "q_research_plan"
            assert rt.run_deep_research.queue == "q_research"
            routes = celery_app.conf.task_routes
            assert routes["tasks.plan_deep_research"] == {"queue": "q_research_plan"}
            assert routes["tasks.run_deep_research"] == {"queue": "q_research"}
        finally:
            get_settings.cache_clear()

    def test_blank_plan_queue_follows_research_queue(self, monkeypatch):
        """compose 가 `${RESEARCH_PLAN_QUEUE:-}` 처럼 빈 값을 넘겨도 계획이 빈 이름의
        큐로 가면 안 된다 — 실행과 같은 큐로 간다."""
        from core.config import get_settings
        monkeypatch.setenv("RESEARCH_QUEUE", "q_research")
        monkeypatch.setenv("RESEARCH_PLAN_QUEUE", "")
        get_settings.cache_clear()
        try:
            rt = _load_tasks(monkeypatch, fake_celery=True)
            assert rt.plan_deep_research.queue == "q_research"
        finally:
            get_settings.cache_clear()


class TestStageGuard:
    def test_unknown_stage_is_rejected(self, monkeypatch):
        # stage 오타는 재개 분기를 조용히 빗나가게 만든다 — 예외도 안 난다
        rt = _load_tasks(monkeypatch)
        try:
            rt._stage("explored_")
        except AssertionError:
            return
        raise AssertionError("알 수 없는 stage 가 통과했다")


class TestLoaderIsolation:
    """_load_tasks 가 끝나면 sys.modules·부모 패키지 속성이 import 전 그대로여야 한다.

    더미 celery·redis 에 묶인 research_tasks·celery_app·relay 가 남으면 뒤에 도는 테스트가
    더미 없이 import 해도 그 모듈을 물려받는다 — 로컬에서만, 실행 순서에 따라 결과가 달라진다.
    """

    @staticmethod
    def _parent(name: str):
        parent, _, child = name.rpartition(".")
        return importlib.import_module(parent), child

    def test_modules_that_were_absent_are_gone_afterwards(self):
        with pytest.MonkeyPatch.context() as outer:
            for name in _CACHED:
                parent, child = self._parent(name)
                outer.delitem(sys.modules, name, raising=False)
                outer.delattr(parent, child, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                _load_tasks(mp)
            for name in _CACHED:
                parent, child = self._parent(name)
                assert name not in sys.modules
                assert not hasattr(parent, child), name

    def test_modules_that_were_loaded_come_back(self):
        originals = {name: types.ModuleType(name) for name in _CACHED}
        with pytest.MonkeyPatch.context() as outer:
            for name, module in originals.items():
                parent, child = self._parent(name)
                outer.setitem(sys.modules, name, module)
                outer.setattr(parent, child, module, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                assert _load_tasks(mp) is not originals["workers.research_tasks"]
            for name, module in originals.items():
                parent, child = self._parent(name)
                assert sys.modules[name] is module
                assert getattr(parent, child) is module, name
