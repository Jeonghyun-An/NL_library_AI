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
import importlib
import sys
import types
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BindParameter, BooleanClauseList

from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, snapshot_state,
)

_CACHED = ("workers.research_tasks", "workers.celery_app", "services.research.relay")


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
    if op is operators.in_op:
        return left in right
    if op is operators.is_not:
        return left is not None
    raise AssertionError(f"대역이 모르는 연산자: {op}")


class _Result:
    def __init__(self, value=None, rowcount: int = 0):
        self._value = value
        self.rowcount = rowcount

    def scalar_one(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


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


def _patch_pipeline(monkeypatch, rt, *, job, explored: list, synthesized: list,
                    explore=None, synthesize=None) -> _Harness:
    """DB·Redis·LLM 을 대역으로 바꾸고 호출만 기록한다.

    explore·synthesize 로 하위 동작을 끼워 넣는다(취소를 찍거나 예외를 던지는 식).
    """
    session = _FakeSession(job=job, scalar=0)
    h = _Harness(session, _FakeEngine())
    monkeypatch.setattr(rt, "_job_engine", lambda: (h.engine, lambda: session))

    async def _next_seq(db, job_id):
        return 3

    async def _step(db, job_id, seq, kind, title, *, subq_idx=None, detail=None):
        h.steps.append((kind, title))
        return len(h.steps)

    async def _finish(db, step_id, status, result=None):
        # 롤백 없이 쓰면 깨진 트랜잭션 위에서 다시 터진다 — 몇 번 롤백한 뒤였는지 남긴다
        h.finished.append((step_id, status, result, session.rollbacks))

    async def _corpus_range(db):
        return {"from": "2002", "to": "2026", "n_papers": 7}

    async def _publish(job_id, kind, payload):
        h.events.append((kind, payload))

    async def _publish_terminal(job_id, status, error=None):
        h.events.append(("terminal", status, error))

    async def _explore(state, subq, *, db, emit=None):
        assert not session.in_txn, "탐색(LLM) 직전에 읽기 트랜잭션이 열려 있다"
        explored.append(subq.text)
        if explore is not None:
            await explore(state, subq)
        return subq

    async def _synthesize(state, *, should_stop=None):
        assert not session.in_txn, "종합(LLM) 직전에 읽기 트랜잭션이 열려 있다"
        synthesized.append(state)
        if synthesize is not None:
            return await synthesize(state, should_stop)
        return {"sections": []}

    for name, fn in (
        ("_next_seq", _next_seq), ("_step", _step), ("_finish", _finish),
        ("_corpus_range", _corpus_range), ("publish", _publish),
        ("publish_terminal", _publish_terminal),
        ("explore_subquestion", _explore), ("synthesize", _synthesize),
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


class TestReaper:
    class _SyncSession:
        def __init__(self):
            self.sql: list[str] = []

        def execute(self, stmt, params=None):
            self.sql.append(str(stmt))
            result = MagicMock()
            result.one.return_value = (1, 2)
            result.fetchall.return_value = [("s",)]
            return result

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

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
