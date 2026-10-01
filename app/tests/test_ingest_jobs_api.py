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

JOB_ID = "1ca22f59-1e50-4dd1-81f5-2d3c79126825"


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

    def all(self):
        return self._rows


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
        if "ingest_job_items.finished_at >=" in sql:
            since = compiled.params["finished_at_1"]
            hours = (_dt.datetime.now(_dt.timezone.utc) - since).total_seconds() / 3600
            return _Result(scalar=self.done_1h if hours < 2 else self.done_24h)
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

    def test_permanent_failures_use_job_max_attempts(self):
        db = _FakeDB(_job(params={"reembed": True, "max_attempts": 5}), status_counts={"done": 1})
        self._get(db)
        assert db.attempt_limits == [5]

    def test_permanent_failures_default_to_setting(self):
        db = _FakeDB(_job(params={"reembed": True}), status_counts={"done": 1})
        self._get(db)
        assert db.attempt_limits == [3]


class TestFailureGroups:
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
