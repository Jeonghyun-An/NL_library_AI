"""test_job_runtime.py — 배치 잡 레이어: 실행 토큰·체인 정지·재시도·stale 판정

`workers.job_runtime` 은 celery(태스크 데코레이터·chain)와 redis(core.lock)를 물고 온다.
둘 다 로컬 venv 에 없어 최상단에서 import 하면 pytest 가 collection 단계에서 세션 전체를
죽인다(`docs/ops/recurring-gotchas.md` 13번). 그래서 test_research_tasks.py 처럼 더미를
꽂고 함수 안에서 import 한다. celery 는 설치돼 있어도 늘 이 파일의 더미를 쓴다 — `.si()`
로 만든 서명과 `Ignore` 를 단언해야 해서다.

DB 는 SQLite 다(history_sqlite.py 와 같은 방식 — JSONB 를 JSON 으로 그리고 '::jsonb' 서버
기본값을 뺀다). 디스패처가 내는 조건(백오프 시각 비교·상태·attempt 한도)을 실제 엔진이
판정해야 조건이 빠진 회귀를 잡는다.

`Ignore` 가 체인을 멈추는 것은 Celery 의 동작이라 여기서는 "Ignore 를 던지고 아이템을
바꾸지 않는다"까지만 본다. 근거: celery 5.4 `celery/app/trace.py` 는 체인의 다음 태스크를
성공 분기(`else:`)에서만 보내고, `celery/worker/request.py` 는 Ignore 를 ack 한다.
"""
import datetime as _dt
import importlib
import sys
import types
import uuid
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import history_sqlite  # noqa: F401 — JSONB 를 SQLite 에서 JSON 으로 그리는 컴파일 규칙
from models.ingest_job import IngestJob, IngestJobItem
from services.ingestion.stages import StageError

_CACHED = ("workers.job_runtime", "workers.celery_app", "core.lock")
NOW = _dt.datetime(2026, 10, 1, 12, 0, 0, tzinfo=_dt.timezone.utc)
STAGES = ("extract", "summarize", "embed_index", "finalize")


def _ago(seconds: float) -> _dt.datetime:
    return NOW - _dt.timedelta(seconds=seconds)


# ── celery 대역 ────────────────────────────────────────────────────────
class _Ignore(Exception):
    """celery.exceptions.Ignore 대역 — 진짜처럼 Exception 의 하위다(그래서 except Exception 밖에서 던져야 한다)."""


class _Sig:
    def __init__(self, task_name: str, args: tuple):
        self.task_name = task_name
        self.args = args


class _Chain:
    """celery.chain 대역 — 받은 서명을 남기고 apply_async 는 태스크 id 만 돌려준다."""

    def __init__(self, *sigs):
        self.sigs = list(sigs)

    def apply_async(self):
        return types.SimpleNamespace(id=f"celery-{uuid.uuid4().hex[:8]}")


class _Task:
    def __init__(self, fn, name: str):
        self.fn = fn
        self.name = name

    def __call__(self, *a, **kw):
        return self.fn(*a, **kw)

    def si(self, *args):
        return _Sig(self.name, args)


class _Conf:
    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class _Celery:
    def __init__(self, *a, **kw):
        self.conf = _Conf()

    def task(self, *a, **kw):
        def _decorator(fn):
            return _Task(fn, kw.get("name"))
        return _decorator


def _stub_missing(monkeypatch, name: str) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, MagicMock())


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다
    (test_research_tasks.py 의 같은 이름 함수 주석 참고)."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


def _load_runtime(monkeypatch, ingest_states: list):
    celery_mod = types.ModuleType("celery")
    celery_mod.Celery = _Celery
    celery_mod.chain = _Chain
    celery_exc = types.ModuleType("celery.exceptions")
    celery_exc.Ignore = _Ignore
    celery_exc.SoftTimeLimitExceeded = type("SoftTimeLimitExceeded", (Exception,), {})
    monkeypatch.setitem(sys.modules, "celery", celery_mod)
    monkeypatch.setitem(sys.modules, "celery.exceptions", celery_exc)
    _stub_missing(monkeypatch, "redis")
    # _run_stage 가 함수 안에서 import 하는 workers.tasks — 진짜는 적재 태스크 전부를 끌고 온다
    tasks_mod = types.ModuleType("workers.tasks")
    tasks_mod._set_ingest_state = lambda book_id, state, **kw: ingest_states.append((book_id, state))
    monkeypatch.setitem(sys.modules, "workers.tasks", tasks_mod)
    _forget_on_teardown(monkeypatch, _CACHED)
    return importlib.import_module("workers.job_runtime")


# ── DB ─────────────────────────────────────────────────────────────────
def _make_engine() -> sa.Engine:
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    metadata = sa.MetaData()
    for table in (IngestJob.__table__, IngestJobItem.__table__):
        copy = table.to_metadata(metadata)
        for col in copy.columns:
            default = col.server_default
            if default is not None and "::" in str(getattr(default, "arg", "")):
                col.server_default = None
    metadata.create_all(engine)
    return engine


def _snapshot(row) -> dict:
    return {
        "stage": row.stage, "status": row.status, "attempt": row.attempt,
        "meta": dict(row.meta or {}), "error_group": row.error_group,
        "last_error": row.last_error, "celery_task_id": row.celery_task_id,
        "updated_at": row.updated_at,
    }


class _Env:
    """잡 하나 + 아이템들 + 대역(락·단계 함수). 행은 매번 새 세션으로 읽는다 — 코드가 커밋한 값만 보인다."""

    def __init__(self, monkeypatch):
        self.ingest_states: list[tuple] = []
        self.rt = _load_runtime(monkeypatch, self.ingest_states)
        self.engine = _make_engine()
        self.Session = sessionmaker(bind=self.engine, autoflush=False)
        self.job_id = uuid.uuid4()
        with self.Session() as s:
            s.add(IngestJob(id=self.job_id, name="kci-test", status="running", params={},
                            total_items=0))
            s.commit()

        rt = self.rt
        monkeypatch.setattr(rt, "SyncSessionLocal", self.Session)
        monkeypatch.setattr(rt, "_now", lambda: NOW)
        monkeypatch.setattr(rt.cfg, "INGEST_MAX_ATTEMPTS", 3)
        monkeypatch.setattr(rt.cfg, "INGEST_HIGH_WATER", 32)
        monkeypatch.setattr(rt.cfg, "INGEST_RETRY_BACKOFF_SECONDS", "120,600")
        monkeypatch.setattr(rt.cfg, "INGEST_STAGE_TIMEOUT_EXTRACT", 3600)
        monkeypatch.setattr(rt.cfg, "INGEST_STAGE_TIMEOUT_SUMMARIZE", 1200)
        monkeypatch.setattr(rt.cfg, "INGEST_STAGE_TIMEOUT_EMBED", 1200)
        monkeypatch.setattr(rt.cfg, "INGEST_STAGE_TIMEOUT_FINALIZE", 900)
        monkeypatch.setattr(rt, "DISPATCH_STALE_SECONDS", 14400)

        # 락 대역 — lock_free=False 면 다른 워커가 쥐고 있는 것처럼 acquire 가 실패한다
        self.lock_free = True
        self.locks: list = []
        env = self

        class _Lock:
            def __init__(self, book_id, ttl=None):
                self.book_id, self.ttl, self.released = book_id, ttl, False
                env.locks.append(self)

            def acquire(self):
                return env.lock_free

            def release(self):
                self.released = True
                return True

        monkeypatch.setattr(rt, "BookLock", _Lock)

        # 단계 함수 대역 — 호출(ctx)과, 호출 순간 DB 에 적혀 있던 meta 를 남긴다
        self.calls: list[tuple[str, object]] = []
        self.meta_during: list[dict] = []
        self.results: dict[str, dict] = {}
        self.errors: dict[str, Exception] = {}

        def _make(name):
            def _fn(ctx):
                env.calls.append((name, ctx))
                env.meta_during.append(dict(env.item(ctx.job_item_id).meta or {}))
                if name in env.errors:
                    raise env.errors[name]
                return dict(env.results.get(name, {}))
            return _fn

        monkeypatch.setattr(rt, "STAGE_FUNCS", {s: _make(s) for s in STAGES})

        # 디스패처가 보낸 체인 — (체크포인트, item_id, 토큰, 서명들)
        self.sent: list[types.SimpleNamespace] = []
        real_build = rt.build_item_chain

        def _record(item_stage, item_id, run_token=None):
            sig = real_build(item_stage, item_id, run_token)
            if sig is not None:
                self.sent.append(types.SimpleNamespace(
                    stage=item_stage, item_id=item_id, token=run_token, sigs=sig.sigs))
            return sig

        monkeypatch.setattr(rt, "build_item_chain", _record)

    def add_item(self, item_id, *, stage="pending", status="pending", attempt=0, meta=None,
                 error_group=None, last_error=None, updated_at=None):
        with self.Session() as s:
            s.add(IngestJobItem(
                id=item_id, job_id=self.job_id, book_id=f"KCI_{item_id:04d}",
                source_key=f"originals/KCI_{item_id:04d}.pdf", stage=stage, status=status,
                attempt=attempt, meta=dict(meta or {}), stage_timings={},
                error_group=error_group, last_error=last_error,
                updated_at=updated_at or _ago(3600),
            ))
            s.commit()

    def item(self, item_id):
        with self.Session() as s:
            return s.get(IngestJobItem, item_id)

    def set_job(self, **values):
        with self.Session() as s:
            job = s.get(IngestJob, self.job_id)
            for key, value in values.items():
                setattr(job, key, value)
            s.commit()

    def dispatch(self) -> int:
        with self.Session() as s:
            return self.rt._dispatch_for_job(s, s.get(IngestJob, self.job_id))

    def recover_stale(self) -> int:
        with self.Session() as s:
            return self.rt._recover_stale(s, s.get(IngestJob, self.job_id))


@pytest.fixture
def env(monkeypatch):
    return _Env(monkeypatch)


# ── _run_stage: 실행하지 않고 체인을 멈추는 경우 ─────────────────────────
class TestStopsChain:
    """옛 체인·재전달 메시지·이미 끝난 단계는 Ignore 로 체인을 멈추고 아이템을 건드리지 않는다.

    dict 를 돌려주면 Celery 는 성공으로 보고 체인의 다음 단계를 보낸다 — 함정 16번에서
    재전달된 옛 체인의 embed_index 가 아티팩트 없이 돌아 논문 본문을 초록으로 덮은 경로다.
    """

    def _assert_stopped(self, env, item_id, before):
        assert env.calls == [], "단계 함수가 돌면 안 된다"
        assert _snapshot(env.item(item_id)) == before, "아이템 상태를 바꾸면 안 된다"
        assert env.ingest_states == []

    def test_token_mismatch(self, env):
        env.add_item(1, stage="summarized", status="running", meta={"run_token": "new"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("embed_index", 1, "celery-old", "old")

        self._assert_stopped(env, 1, before)

    def test_old_message_without_token_on_tokened_item(self, env):
        # 배포 전에 보낸 메시지는 토큰 인자가 없다 — 아이템에 토큰이 있으면 새 체인이 떴다는 뜻이다
        env.add_item(1, stage="summarized", status="running", meta={"run_token": "new"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("embed_index", 1, "celery-legacy", None)

        self._assert_stopped(env, 1, before)

    def test_stage_already_passed(self, env):
        # 체크포인트가 summarized — 같은 토큰이어도 요약을 다시 돌리지 않는다(재전달)
        env.add_item(1, stage="summarized", status="running", meta={"run_token": "t"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_finalized_item(self, env):
        env.add_item(1, stage="finalized", status="done", meta={"run_token": "t"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("embed_index", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_done_status_even_if_stage_remains(self, env):
        env.add_item(1, stage="indexed", status="done", meta={"run_token": "t"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("finalize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_canceled_item(self, env):
        env.add_item(1, stage="extracted", status="canceled", meta={"run_token": "t"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_canceled_job(self, env):
        env.add_item(1, stage="extracted", status="running", meta={"run_token": "t"})
        env.set_job(status="canceled")
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_lock_contention_keeps_status(self, env):
        # 예전에는 pending 으로 되돌리고 dict 를 돌려줘 체인이 다음 단계로 갔다. pending 으로
        # 되돌리면 디스패처가 새 토큰으로 또 보내, 락을 쥐고 일하는 체인을 끊고 경합을 되풀이한다
        env.add_item(1, stage="extracted", status="dispatched", meta={"run_token": "t"})
        env.lock_free = False
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)
        assert env.locks and not env.locks[0].released, "쥐지 못한 락은 풀지 않는다"

    def test_missing_item(self, env):
        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("extract", 999, "celery-1", "t")
        assert env.calls == []

    def test_item_is_read_with_row_lock(self, env):
        """디스패처는 메시지를 보낸 뒤 루프 끝에서 토큰을 커밋한다. 워커가 그 전에 아이템을 읽으면
        옛 토큰을 보고 새 체인을 멈춘다 — 그래서 첫 읽기는 FOR UPDATE 로 디스패처의 행 잠금
        (SELECT … FOR UPDATE SKIP LOCKED)이 풀릴 때까지 기다린다. SQLite 는 잠금을 그리지
        않으므로 같은 문장을 Postgres 로 컴파일해 본다."""
        env.add_item(1, stage="summarized", status="running", meta={"run_token": "new"})
        selects: list[str] = []

        @event.listens_for(env.Session, "do_orm_execute")
        def _record(state):
            if state.is_select:
                selects.append(str(state.statement.compile(dialect=postgresql.dialect())))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("embed_index", 1, "celery-old", "old")

        item_reads = [s for s in selects if "FROM ingest_job_items" in s]
        assert item_reads and "FOR UPDATE" in item_reads[0]


# ── _run_stage: 실행 ─────────────────────────────────────────────────────
class TestRunsStage:
    def test_matching_token_runs_and_marks_stage_running(self, env):
        env.add_item(1, stage="extracted", status="dispatched",
                     meta={"run_token": "t", "pages": 12})
        env.results["summarize"] = {"sections_total": 3}

        out = env.rt._run_stage("summarize", 1, "celery-1", "t")

        assert out["stage"] == "summarize"
        # 단계가 도는 동안에는 이름과 시작 시각이 적혀 있다 — stale 판정이 이것으로 실행 시간을 잰다
        during = env.meta_during[0]
        assert during["stage_running"] == "summarize"
        assert _dt.datetime.fromisoformat(during["stage_started_at"]) == NOW
        row = env.item(1)
        assert row.stage == "summarized" and row.status == "running"
        assert row.meta["stage_running"] is None, "끝나면 지운다 — 남아 있으면 대기를 실행으로 잰다"
        assert row.meta["stage_started_at"] == NOW.isoformat()
        assert row.meta["sections_total"] == 3 and row.meta["run_token"] == "t"
        assert env.locks[0].released

    def test_stage_context_carries_item_meta(self, env):
        env.add_item(1, stage="summarized", status="dispatched",
                     meta={"run_token": "t", "pages": 12})

        env.rt._run_stage("embed_index", 1, "celery-1", "t")

        _, ctx = env.calls[0]
        assert ctx.item_meta["pages"] == 12, "embed 가드가 PDF 가 있던 문서인지 meta.pages 로 판단한다"

    def test_old_message_runs_on_item_without_token(self, env):
        # 배포 전 아이템(토큰 없음)의 옛 메시지는 예전처럼 돈다
        env.add_item(1, stage="pending", status="dispatched", meta={})

        env.rt._run_stage("extract", 1, "celery-legacy", None)

        assert [c[0] for c in env.calls] == ["extract"]
        assert env.item(1).stage == "extracted"

    def test_finalize_marks_done_and_clears_stage_running(self, env):
        env.add_item(1, stage="indexed", status="running", meta={"run_token": "t"})

        env.rt._run_stage("finalize", 1, "celery-1", "t")

        row = env.item(1)
        assert row.status == "done" and row.stage == "finalized"
        assert row.meta["stage_running"] is None
        assert env.ingest_states == [("KCI_0001", "embedded")]

    def test_failure_clears_stage_running_and_bumps_attempt(self, env):
        env.add_item(1, stage="extracted", status="dispatched", attempt=0,
                     meta={"run_token": "t"})
        env.errors["summarize"] = StageError("llm_error", "섹션 요약 전체 실패 (3건)")

        with pytest.raises(StageError):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        row = env.item(1)
        assert row.status == "failed" and row.error_group == "llm_error"
        assert row.attempt == 1 and row.stage == "extracted"
        assert row.meta["stage_running"] is None
        assert env.locks[0].released


# ── 단계 태스크·체인 ───────────────────────────────────────────────────
class TestTasksAndChain:
    def test_build_item_chain(self, monkeypatch):
        rt = _load_runtime(monkeypatch, [])

        sig = rt.build_item_chain("summarized", 9, "tok")

        assert [s.task_name for s in sig.sigs] == ["tasks.stage_embed_index", "tasks.stage_finalize"]
        assert all(s.args == (9, "tok") for s in sig.sigs)
        assert rt.build_item_chain("finalized", 9, "tok") is None

    def test_stage_tasks_pass_token_and_accept_old_messages(self, monkeypatch):
        rt = _load_runtime(monkeypatch, [])
        seen = []
        monkeypatch.setattr(rt, "_run_stage", lambda *a: seen.append(a) or {})
        task_self = types.SimpleNamespace(request=types.SimpleNamespace(id="celery-9"))

        rt.stage_embed_index.fn(task_self, 9, "tok")
        rt.stage_finalize.fn(task_self, 9)   # 배포 전 메시지 — 토큰 인자가 없다

        assert seen == [("embed_index", 9, "celery-9", "tok"), ("finalize", 9, "celery-9", None)]


# ── 디스패처: 실행 토큰 ────────────────────────────────────────────────
class TestDispatchToken:
    def test_each_chain_gets_a_fresh_token(self, env):
        env.add_item(1, meta={"pages": 4})
        env.add_item(2)

        assert env.dispatch() == 2

        tokens = {s.item_id: s.token for s in env.sent}
        assert len(set(tokens.values())) == 2 and all(tokens.values())
        for s in env.sent:
            assert all(sig.args == (s.item_id, s.token) for sig in s.sigs)
            row = env.item(s.item_id)
            assert row.meta["run_token"] == s.token and row.status == "dispatched"
        assert env.item(1).meta["pages"] == 4, "다른 meta 키는 그대로 둔다"

    def test_redispatch_replaces_token(self, env):
        env.add_item(1, stage="extracted", status="failed", attempt=1,
                     error_group="stale", meta={"run_token": "old"}, updated_at=_ago(1000))

        env.dispatch()

        assert env.sent[0].token != "old"
        assert env.item(1).meta["run_token"] == env.sent[0].token


# ── 재시도: 결정적 실패 제외·추출부터 다시·백오프 ─────────────────────
class TestRetryPolicy:
    def test_no_text_exhausts_attempts(self, env):
        """같은 코드로 다시 해도 결과가 같은 실패 — 자동 재시도에서 뺀다."""
        env.add_item(1, stage="pending", status="dispatched", attempt=0, meta={"run_token": "t"})
        env.errors["extract"] = StageError("no_text", "강제 OCR 뒤에도 섹션 0개")

        with pytest.raises(StageError):
            env.rt._run_stage("extract", 1, "celery-1", "t")

        assert env.item(1).attempt == 3   # cfg.INGEST_MAX_ATTEMPTS

    def test_no_text_uses_job_max_attempts(self, env):
        env.set_job(params={"max_attempts": 5})
        env.add_item(1, stage="pending", status="dispatched", attempt=1, meta={"run_token": "t"})
        env.errors["extract"] = StageError("no_text", "강제 OCR 뒤에도 섹션 0개")

        with pytest.raises(StageError):
            env.rt._run_stage("extract", 1, "celery-1", "t")

        assert env.item(1).attempt == 5

    def test_no_text_item_is_not_picked_again(self, env, monkeypatch):
        env.add_item(1, stage="pending", status="dispatched", attempt=0, meta={"run_token": "t"})
        env.errors["extract"] = StageError("no_text", "강제 OCR 뒤에도 섹션 0개")
        with pytest.raises(StageError):
            env.rt._run_stage("extract", 1, "celery-1", "t")
        monkeypatch.setattr(env.rt, "_now", lambda: NOW + _dt.timedelta(days=1))   # 백오프는 한참 지났다

        assert env.dispatch() == 0
        assert env.item(1).status == "failed"

    def test_section_missing_failure_restarts_from_extract(self, env):
        # 옛 코드가 섹션 0개를 추출 성공으로 넘겨 요약에서 실패한 아이템 — 요약부터 다시 하면 같은 실패다
        env.add_item(1, stage="extracted", status="failed", attempt=1, error_group="not_found",
                     last_error="섹션 없음 — extract 단계부터 재실행 필요", updated_at=_ago(1000))

        env.dispatch()

        assert env.item(1).stage == "pending"
        assert env.sent[0].sigs[0].task_name == "tasks.stage_extract"

    def test_vlm_error_restarts_from_extract(self, env):
        env.add_item(1, stage="extracted", status="failed", attempt=1, error_group="vlm_error",
                     last_error="VLM 호출 실패", updated_at=_ago(1000))

        env.dispatch()

        assert env.item(1).stage == "pending"
        assert env.sent[0].sigs[0].task_name == "tasks.stage_extract"

    def test_other_failures_keep_checkpoint(self, env):
        env.add_item(1, stage="extracted", status="failed", attempt=1, error_group="not_found",
                     last_error="카탈로그 row 없음 — extract 단계부터 재실행 필요", updated_at=_ago(1000))
        env.add_item(2, stage="extracted", status="failed", attempt=1, error_group="llm_error",
                     last_error="섹션 요약 전체 실패 (3건)", updated_at=_ago(1000))

        env.dispatch()

        assert env.item(1).stage == "extracted" and env.item(2).stage == "extracted"
        assert {s.sigs[0].task_name for s in env.sent} == {"tasks.stage_summarize"}

    def test_backoff_by_attempt(self, env):
        env.set_job(params={"max_attempts": 5})
        env.add_item(1, status="failed", attempt=1, updated_at=_ago(100))   # 120초 전 — 대기
        env.add_item(2, status="failed", attempt=1, updated_at=_ago(120))   # 딱 120초 — 집는다
        env.add_item(3, status="failed", attempt=2, updated_at=_ago(500))   # 600초 전 — 대기
        env.add_item(4, status="failed", attempt=2, updated_at=_ago(700))
        env.add_item(5, status="failed", attempt=3, updated_at=_ago(500))   # 값이 모자라면 마지막(600) 반복
        env.add_item(6, status="failed", attempt=3, updated_at=_ago(700))
        env.add_item(7, status="pending", attempt=0, updated_at=NOW)        # pending 은 백오프 없음

        env.dispatch()

        assert sorted(s.item_id for s in env.sent) == [2, 4, 6, 7]
        assert env.item(1).status == "failed" and env.item(3).status == "failed"

    def test_items_in_backoff_do_not_block_pending(self, env):
        env.set_job(params={"high_water": 2})
        for item_id in range(1, 6):   # id 가 앞선 실패 5건이 모두 백오프 중
            env.add_item(item_id, status="failed", attempt=1, updated_at=_ago(10))
        env.add_item(6)
        env.add_item(7)
        env.add_item(8)

        assert env.dispatch() == 2

        assert [s.item_id for s in env.sent] == [6, 7], "id 순서는 지키고 백오프 중인 실패는 건너뛴다"

    def test_exhausted_attempts_not_picked(self, env):
        env.add_item(1, status="failed", attempt=3, updated_at=_ago(100000))

        assert env.dispatch() == 0

    def test_backoff_setting_parsing(self, env, monkeypatch):
        # 디스패처는 30초마다 이 값을 읽는다 — 잘못된 칸 하나로 디스패처가 죽으면 적재가 멈춘다
        for raw, want in {"120,600": [120, 600], " 30 , x ,90": [30, 90], "": []}.items():
            monkeypatch.setattr(env.rt.cfg, "INGEST_RETRY_BACKOFF_SECONDS", raw)
            assert env.rt._retry_backoff_steps() == want, raw

    def test_empty_backoff_setting_means_no_wait(self, env, monkeypatch):
        monkeypatch.setattr(env.rt.cfg, "INGEST_RETRY_BACKOFF_SECONDS", "")
        env.add_item(1, status="failed", attempt=1, updated_at=_ago(10))

        assert env.dispatch() == 1


# ── stale 판정: 실행 중 vs 다음 단계 대기 ────────────────────────────────
class TestRecoverStale:
    def test_running_stage_is_timed_from_its_start(self, env):
        env.add_item(1, stage="summarized", status="running", updated_at=_ago(5),
                     meta={"stage_running": "embed_index", "stage_started_at": _ago(1300).isoformat()})

        assert env.recover_stale() == 1

        row = env.item(1)
        assert row.status == "failed" and row.error_group == "stale" and row.attempt == 1
        assert "stale 복구" in row.last_error and "embed_index" in row.last_error

    def test_running_stage_within_timeout(self, env):
        env.add_item(1, stage="pending", status="running", updated_at=_ago(3500),
                     meta={"stage_running": "extract", "stage_started_at": _ago(3500).isoformat()})

        assert env.recover_stale() == 0
        assert env.item(1).status == "running"

    def test_waiting_for_next_stage_is_not_execution(self, env):
        # 임베딩을 끝내고 마무리(q_llm) 큐에서 2000초째 기다린다 — 예전에는 마무리 타임아웃
        # 900초로 재서 stale 로 오판하고 중복 체인을 열었다
        env.add_item(1, stage="indexed", status="running", updated_at=_ago(2000),
                     meta={"stage_running": None, "stage_started_at": _ago(2300).isoformat()})

        assert env.recover_stale() == 0
        assert env.item(1).status == "running"

    def test_waiting_beyond_dispatch_window(self, env):
        env.add_item(1, stage="indexed", status="running", updated_at=_ago(14500),
                     meta={"stage_running": None})

        assert env.recover_stale() == 1
        assert "다음 단계 대기" in env.item(1).last_error

    def test_item_without_stage_running_key_counts_as_waiting(self, env):
        # 배포 전에 마지막 단계를 끝낸 아이템은 meta 에 stage_running 키가 없다
        env.add_item(1, stage="indexed", status="running", updated_at=_ago(2000), meta={})

        assert env.recover_stale() == 0

    def test_dispatched_unchanged(self, env):
        env.add_item(1, stage="pending", status="dispatched", updated_at=_ago(2000))
        env.add_item(2, stage="pending", status="dispatched", updated_at=_ago(14500))

        assert env.recover_stale() == 1
        assert env.item(1).status == "dispatched" and env.item(2).status == "failed"

    def test_requeued_item_with_leftover_stage_running_is_not_execution(self, env):
        # 단계 도중 워커가 죽어 stale 복구된 아이템은 meta.stage_running 이 남은 채 다시 dispatched 가
        # 된다. 이때는 실행 중이 아니라 큐 대기다 — 옛 stage_started_at 으로 재면 큐에서 기다리는
        # 동안 다음 틱이 또 stale 로 오판해 중복 체인을 연다
        env.add_item(1, stage="pending", status="dispatched", updated_at=_ago(30),
                     meta={"stage_running": "extract", "stage_started_at": _ago(7200).isoformat()})

        assert env.recover_stale() == 0
        assert env.item(1).status == "dispatched"
