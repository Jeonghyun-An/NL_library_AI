"""api/ingest_jobs.py — 잡 조회의 처리량·ETA·남은 수, 실패 그룹의 대표 메시지.

Postgres 가 로컬에 없다. 문장은 postgresql 방언으로 컴파일한 문자열로 확인하고, 엔드포인트는
문장을 SQL 로 구별해 정해 둔 값을 돌려주는 대역 세션으로 돌린다.
"""
import asyncio
import datetime as _dt
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from api import ingest_jobs
from models.ingest_job import JOB_STATUSES

JOB_ID = "1ca22f59-1e50-4dd1-81f5-2d3c79126825"

# ETA 를 내는 잡 상태(running)와 끝난 잡 상태, 그 밖(멈춤·취소·시작 전)
FINISHED = ("completed", "completed_with_errors")
NOT_RUNNING = ["created", "validating", "ready", "paused", "canceled"]


def _compiled(stmt):
    return stmt.compile(dialect=postgresql.dialect())


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def one(self):
        return self._rows[0]

    def all(self):
        return self._rows


def _hours_ago(moment: _dt.datetime) -> float:
    return (_dt.datetime.now(_dt.timezone.utc) - moment).total_seconds() / 3600


class _FakeDB:
    """get_job·list_failures 가 보내는 문장을 SQL 로 구별해 정해 둔 값을 돌려준다."""

    def __init__(self, job=None, *, status_counts=None, done_1h=0, done_24h=0,
                 permanently_failed=0, failure_rows=None):
        self.job = job
        self.status_counts = status_counts or {}
        self.done_1h = done_1h
        self.done_24h = done_24h
        self.permanently_failed = permanently_failed
        self.failure_rows = failure_rows or []
        self.sql: list[str] = []
        self.attempt_limits: list[int] = []
        self.done_windows: list[tuple[float, float]] = []   # (1시간 칸, 24시간 칸)이 쓴 창 길이(시간)

    async def execute(self, stmt):
        compiled = _compiled(stmt)
        sql = str(compiled)
        self.sql.append(sql)
        if "FROM ingest_jobs" in sql:
            return _Result(scalar=self.job)
        if "WITHIN GROUP" in sql:
            return _Result(rows=self.failure_rows)
        if "GROUP BY ingest_job_items.status" in sql:
            return _Result(rows=list(self.status_counts.items()))
        if "GROUP BY ingest_job_items.stage" in sql or "extract_method" in sql:
            return _Result(rows=[])
        if "ingest_job_items.attempt >=" in sql:
            self.attempt_limits.append(compiled.params["attempt_1"])
            return _Result(scalar=self.permanently_failed)
        if "FILTER (WHERE ingest_job_items.finished_at >=" in sql:
            self.done_windows.append(
                (_hours_ago(compiled.params["finished_at_1"]), _hours_ago(compiled.params["finished_at_2"]))
            )
            return _Result(rows=[(self.done_1h, self.done_24h)])
        raise AssertionError(f"대역이 모르는 문장: {sql}")


def _job(status="running", total_items=1000, params=None):
    return SimpleNamespace(
        id=uuid.UUID(JOB_ID), name="kci-full-236k", kind="paper_bulk", status=status,
        manifest_key="manifests/full/manifest.jsonl", params=params or {"reembed": True},
        total_items=total_items, validation_report=None,
        created_at=None, started_at=None, finished_at=None,
    )


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(
        ingest_jobs, "get_settings", lambda: SimpleNamespace(INGEST_MAX_ATTEMPTS=3), raising=False,
    )


class TestComputeEta:
    def test_uses_24h_throughput(self):
        # 24시간 480건 = 시간당 20건 → 남은 360건은 18시간
        assert ingest_jobs.compute_eta(360, 480, "running") == 18.0

    def test_paused_job_has_no_eta(self):
        assert ingest_jobs.compute_eta(360, 480, "paused") is None

    def test_no_throughput_has_no_eta(self):
        assert ingest_jobs.compute_eta(360, 0, "running") is None

    def test_nothing_left_is_zero(self):
        assert ingest_jobs.compute_eta(0, 0, "running") == 0.0

    @pytest.mark.parametrize("status", NOT_RUNNING)
    def test_a_job_that_is_not_running_has_no_eta(self, status):
        # 멈춤·취소·시작 전 잡은 처리되지 않는다 — 24시간 처리량이 남아 있어도 숫자를 내지 않는다
        assert ingest_jobs.compute_eta(360, 480, status) is None

    @pytest.mark.parametrize("status", FINISHED)
    def test_a_finished_job_has_zero_eta(self, status):
        assert ingest_jobs.compute_eta(0, 0, status) == 0.0
        assert ingest_jobs.compute_eta(5, 480, status) == 0.0   # 끝난 잡은 상태가 정한다

    def test_every_job_status_has_an_eta_rule(self):
        # 새 잡 상태가 생기면 이 목록(과 compute_eta)을 고쳐 ETA 를 낼지 정하게 한다
        assert set(NOT_RUNNING) | set(FINISHED) | {"running"} == set(JOB_STATUSES)


class TestJobDetail:
    def _get(self, db):
        return asyncio.run(ingest_jobs.get_job(JOB_ID, db=db))

    def test_rates_eta_and_remaining(self):
        db = _FakeDB(
            _job(total_items=1000),
            status_counts={"done": 600, "failed": 50, "pending": 350},
            done_1h=10, done_24h=480, permanently_failed=40,
        )
        out = self._get(db)
        assert out["rate_per_hour"] == 10          # 1시간 창은 그대로 둔다
        assert out["rate_per_hour_24h"] == 20.0
        assert out["permanently_failed"] == 40
        assert out["remaining"] == 1000 - 600 - 40  # 영구 실패는 더 처리되지 않는다
        assert out["eta_hours"] == 18.0             # 360 ÷ 20

    def test_paused_job_keeps_rates_but_no_eta(self):
        db = _FakeDB(_job(status="paused"), status_counts={"done": 600}, done_1h=10, done_24h=480)
        out = self._get(db)
        assert out["eta_hours"] is None
        assert out["rate_per_hour_24h"] == 20.0

    def test_canceled_job_has_no_eta_and_canceled_items_are_not_remaining(self):
        # cancel 은 pending·failed 를 canceled 로 바꾸고 진행 중이던 10건만 자연 종료까지 남는다
        db = _FakeDB(
            _job(status="canceled", total_items=1000),
            status_counts={"done": 600, "canceled": 390, "running": 10},
            done_1h=0, done_24h=480,
        )
        out = self._get(db)
        assert out["remaining"] == 1000 - 600 - 390
        assert out["eta_hours"] is None
        assert out["rate_per_hour_24h"] == 20.0     # 처리율 자체는 그대로 낸다

    def test_canceled_items_are_not_remaining_in_a_running_job(self):
        # 취소했다가 다시 start 한 잡 — 취소된 아이템은 다시 집히지 않는다
        db = _FakeDB(
            _job(total_items=1000),
            status_counts={"done": 600, "canceled": 100, "pending": 300},
            done_1h=20, done_24h=480,
        )
        out = self._get(db)
        assert out["remaining"] == 300
        assert out["eta_hours"] == 15.0             # 300 ÷ 20

    def test_finished_job_reports_zero_eta(self):
        db = _FakeDB(
            _job(status="completed_with_errors", total_items=1000),
            status_counts={"done": 960, "failed": 40}, permanently_failed=40,
        )
        out = self._get(db)
        assert out["remaining"] == 0
        assert out["eta_hours"] == 0.0

    def test_done_counts_are_one_statement_over_1h_and_24h_windows(self):
        db = _FakeDB(_job(), status_counts={"done": 600}, done_1h=10, done_24h=480)
        out = self._get(db)
        assert sum("FILTER" in s for s in db.sql) == 1      # done 행을 한 번만 훑는다
        [(hours_1, hours_24)] = db.done_windows
        assert hours_1 == pytest.approx(1, abs=0.01)         # 첫 칸이 1시간
        assert hours_24 == pytest.approx(24, abs=0.01)       # 둘째 칸이 24시간
        assert (out["rate_per_hour"], out["rate_per_hour_24h"]) == (10, 20.0)

    def test_permanent_failures_use_job_max_attempts(self):
        db = _FakeDB(_job(params={"reembed": True, "max_attempts": 5}), status_counts={"done": 1})
        self._get(db)
        assert db.attempt_limits == [5]

    def test_permanent_failures_default_to_setting(self):
        db = _FakeDB(_job(params={"reembed": True}), status_counts={"done": 1})
        self._get(db)
        assert db.attempt_limits == [3]


class TestCountStatements:
    """count 문장의 상태·시도 한도·시간 창 조건을 컴파일한 SQL 로 고정한다.

    대역 세션은 문장을 부분 문자열로만 구별해서, 조건 하나가 빠져도 엔드포인트 테스트는 통과한다.
    """

    def test_permanently_failed_counts_failed_items_at_the_attempt_limit(self):
        compiled = _compiled(ingest_jobs._permanently_failed(JOB_ID, 5))
        sql = str(compiled)
        assert "ingest_job_items.status = %(status_1)s" in sql
        assert "ingest_job_items.attempt >= %(attempt_1)s" in sql
        # 값까지 고정: 이 잡의 failed 만, 한도 5 이상만
        assert compiled.params == {"job_id_1": JOB_ID, "status_1": "failed", "attempt_1": 5}

    def test_done_counts_scan_the_jobs_done_items_once(self):
        t1h = _dt.datetime(2026, 10, 2, 11, 0, tzinfo=_dt.timezone.utc)
        t24h = _dt.datetime(2026, 10, 1, 12, 0, tzinfo=_dt.timezone.utc)
        compiled = _compiled(ingest_jobs._done_counts(JOB_ID, t1h, t24h))
        sql = str(compiled)
        assert sql.count("FROM ingest_job_items") == 1       # done 행을 한 번만 훑는다
        assert "ingest_job_items.status = %(status_1)s" in sql.split("FROM ingest_job_items", 1)[1]
        # 첫 칸은 1시간, 둘째 칸은 24시간
        assert (
            "count(*) FILTER (WHERE ingest_job_items.finished_at >= %(finished_at_1)s) AS done_1h, "
            "count(*) FILTER (WHERE ingest_job_items.finished_at >= %(finished_at_2)s) AS done_24h"
        ) in sql
        # 값까지 고정: 이 잡의 done 만, 창 시작 시각 둘
        assert compiled.params == {
            "job_id_1": JOB_ID, "status_1": "done", "finished_at_1": t1h, "finished_at_2": t24h,
        }


class TestFailureGroups:
    def test_counts_only_the_jobs_failed_items(self):
        compiled = _compiled(ingest_jobs._failure_groups(JOB_ID))
        assert "GROUP BY ingest_job_items.error_group" in str(compiled)
        assert compiled.params == {"job_id_1": JOB_ID, "status_1": "failed"}

    def test_sample_is_the_most_common_message(self):
        sql = str(_compiled(ingest_jobs._failure_groups(JOB_ID)))
        assert "mode() WITHIN GROUP (ORDER BY ingest_job_items.last_error)" in sql
        assert "max(" not in sql

    def test_endpoint_returns_groups(self):
        db = _FakeDB(failure_rows=[
            ("not_found", 560, "섹션 없음 — extract 단계부터 재실행 필요"),
            (None, 2, None),
        ])
        out = asyncio.run(ingest_jobs.list_failures(JOB_ID, db=db))
        assert out == {"groups": [
            {"error_group": "not_found", "count": 560, "sample_error": "섹션 없음 — extract 단계부터 재실행 필요"},
            {"error_group": "unknown", "count": 2, "sample_error": ""},
        ]}
        assert "mode() WITHIN GROUP" in db.sql[0]
