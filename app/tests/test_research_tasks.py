"""test_research_tasks.py — 딥리서치 Celery 태스크

`workers.research_tasks` 는 celery(태스크 데코레이터)와 redis(relay) 를 물고
온다. 둘 다 로컬 venv 에 없어서 최상단에서 import 하면 pytest 가 **collection
단계에서** 죽고 세션 전체가 0건이 된다(`docs/ops/recurring-gotchas.md` 13번).
그래서 미설치일 때만 더미를 꽂고 함수 안에서 import 한다
(test_embed_index_guard.py·test_search_chunk_answer_flag.py 와 같은 방식).

DB 는 대역으로 세운다. 여기서 확인하려는 것은 SQL 이 아니라 **분기**다 —
stage="explored" 로 다시 들어온 잡이 탐색을 건너뛰고 종합부터 가는가.
"""
import asyncio
import importlib
import sys
import types
import uuid
from unittest.mock import MagicMock

from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, snapshot_state,
)

_CACHED = ("workers.research_tasks", "workers.celery_app", "services.research.relay")


class _SoftTimeLimitExceeded(Exception):
    """celery 미설치 환경용 대역. MagicMock 을 except 절에 쓰면 TypeError 가 난다."""


def _stub_missing(monkeypatch, name: str, module=None) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module or MagicMock())


def _load_tasks(monkeypatch):
    celery_exc = types.ModuleType("celery.exceptions")
    celery_exc.SoftTimeLimitExceeded = _SoftTimeLimitExceeded
    _stub_missing(monkeypatch, "celery")
    _stub_missing(monkeypatch, "celery.exceptions", celery_exc)
    _stub_missing(monkeypatch, "redis")
    _stub_missing(monkeypatch, "redis.asyncio")
    # 더미를 문 채 sys.modules 에 남으면 뒤에 도는 테스트가 Mock 을 물려받는다.
    for mod in _CACHED:
        monkeypatch.delitem(sys.modules, mod, raising=False)
    return importlib.import_module("workers.research_tasks")


# ── DB 대역 ────────────────────────────────────────────────────────────
class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _FakeSession:
    """execute 를 기록하고 정해진 값을 돌려주는 async 세션 대역."""

    def __init__(self, *, job=None, scalar=None):
        self.job = job
        self.scalar = scalar
        self.sql: list[str] = []
        self.params: list[dict] = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt, params=None):
        self.sql.append(str(stmt))
        self.params.append(params)
        return _Result(self.scalar)

    async def get(self, model, pk):
        return self.job

    async def refresh(self, obj):
        return None

    async def commit(self):
        self.commits += 1

    def add(self, obj):
        return None


class _FakeEngine:
    def __init__(self):
        self.disposed = 0

    async def dispose(self):
        self.disposed += 1


class _FakeJob:
    """ResearchJob 대역 — 태스크가 실제로 읽고 쓰는 필드만 가진다."""

    def __init__(self, *, stage, plan, state_snapshot=None):
        self.id = uuid.uuid4()
        self.question = "독서 격차 연구는 어디까지 왔나"
        self.params = {}
        self.plan = plan
        self.stage = stage
        self.state_snapshot = state_snapshot
        self.status = "running"
        self.report = None
        self.last_error = None
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


def _patch_pipeline(monkeypatch, rt, *, job, explored: list, synthesized: list):
    """DB·Redis·LLM 을 전부 대역으로 바꾸고 호출만 기록한다."""
    session = _FakeSession(job=job, scalar=0)
    engine = _FakeEngine()
    monkeypatch.setattr(rt, "_job_engine", lambda: (engine, lambda: session))

    async def _claim(db, job_id, *, allowed, to):
        return True

    async def _next_seq(db, job_id):
        return 3

    async def _step(db, job_id, seq, kind, title, *, subq_idx=None, detail=None):
        return MagicMock()

    async def _finish(db, row, status, result=None):
        return None

    async def _corpus_range(db):
        return {"from": "2002", "to": "2026", "n_papers": 7}

    async def _is_cancelled(db, job_id):
        return False

    async def _publish(job_id, kind, payload):
        return None

    async def _explore(state, subq, *, db, emit=None):
        explored.append(subq.text)
        return subq

    async def _synthesize(state):
        synthesized.append(state)
        return {"sections": []}

    for name, fn in (
        ("_claim", _claim), ("_next_seq", _next_seq), ("_step", _step),
        ("_finish", _finish), ("_corpus_range", _corpus_range),
        ("_is_cancelled", _is_cancelled), ("publish", _publish),
        ("explore_subquestion", _explore), ("synthesize", _synthesize),
    ):
        monkeypatch.setattr(rt, name, fn)
    return engine


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
                       state_snapshot=_explored_snapshot())
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        # plan 을 일부러 채워 뒀다 — 재개 분기를 지우면 여기서 2건이 탐색된다
        assert explored == []
        assert len(synthesized) == 1
        assert out["status"] == "completed"
        assert job.stage == "synthesized"

    def test_resumed_state_comes_from_the_snapshot(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=_explored_snapshot())
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
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1", "계획 하위2"]
        assert job.stage == "synthesized"

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
        engine = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert engine.disposed == 1


class TestClaim:
    """Celery 는 at-least-once 다 — 선점에 실패한 재배달은 즉시 돌아서야 한다."""

    def test_unclaimed_job_is_skipped(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        async def _no_claim(db, job_id, *, allowed, to):
            return False

        monkeypatch.setattr(rt, "_claim", _no_claim)
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


class TestStageGuard:
    def test_unknown_stage_is_rejected(self, monkeypatch):
        # stage 오타는 재개 분기를 조용히 빗나가게 만든다 — 예외도 안 난다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=[])
        try:
            rt._set_stage(job, "explored_")
        except AssertionError:
            return
        raise AssertionError("알 수 없는 stage 가 통과했다")
