import sys
import types
from pathlib import Path

import sqlalchemy as sa

from models.research import JOB_STATUSES, STEP_KINDS, STEP_STATUSES, ResearchJob, ResearchStep

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0005_research_jobs.py"


def _run_migration_upgrade(monkeypatch, migration_path=MIGRATION_PATH):
    """0005 의 upgrade() 를 실제 alembic 없이 실행하고 create_table 호출을 캡처한다.

    로컬 venv 에 alembic 이 설치돼 있지 않아 (app/requirements.txt 에는 있으나 미설치)
    `from alembic import op` 를 만족시키는 최소 스텁만 넣는다 — upgrade() 는 op.create_table /
    op.create_index 만 호출하므로 그 둘만 흉내 내면 충분하다.
    """
    import importlib.util as u

    captured = {}

    def fake_create_table(name, *args, **kwargs):
        captured[name] = [a.name for a in args if isinstance(a, sa.Column)]

    fake_op = types.ModuleType("alembic.op")
    fake_op.create_table = fake_create_table
    fake_op.create_index = lambda *a, **k: None

    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = fake_op

    monkeypatch.setitem(sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(sys.modules, "alembic.op", fake_op)

    spec = u.spec_from_file_location("_migration_0005", migration_path)
    module = u.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    return captured


class TestResearchModelShape:
    def test_job_table_columns(self):
        cols = set(ResearchJob.__table__.columns.keys())
        assert {"id", "question", "status", "params", "plan", "report"} <= cols

    def test_step_table_columns(self):
        cols = set(ResearchStep.__table__.columns.keys())
        assert {"job_id", "seq", "kind", "subq_idx", "title",
                "detail", "status", "result", "updated_at"} <= cols

    def test_step_has_job_seq_unique_constraint(self):
        names = {c.name for c in ResearchStep.__table__.constraints}
        assert "uq_research_steps_job_seq" in names

    def test_inflight_index_condition(self):
        idx = next(
            ix for ix in ResearchStep.__table__.indexes
            if ix.name == "ix_research_steps_inflight"
        )
        where_clause = idx.dialect_options["postgresql"]["where"]
        assert str(where_clause) == "status = 'running'"

    def test_step_job_fk_cascades_on_delete(self):
        fk = next(iter(ResearchStep.__table__.foreign_keys))
        assert fk.ondelete == "CASCADE"

    def test_job_status_default_is_valid_status(self):
        assert ResearchJob.__table__.c.status.default.arg in JOB_STATUSES

    def test_step_status_default_is_valid_status(self):
        assert ResearchStep.__table__.c.status.default.arg in STEP_STATUSES

    def test_job_statuses_fit_status_column(self):
        max_len = ResearchJob.__table__.c.status.type.length
        assert all(len(v) <= max_len for v in JOB_STATUSES)

    def test_step_kinds_and_statuses_fit_their_columns(self):
        kind_len = ResearchStep.__table__.c.kind.type.length
        status_len = ResearchStep.__table__.c.status.type.length
        assert all(len(v) <= kind_len for v in STEP_KINDS)
        assert all(len(v) <= status_len for v in STEP_STATUSES)


class TestMigrationMatchesModel:
    def test_upgrade_creates_columns_matching_orm(self, monkeypatch):
        captured = _run_migration_upgrade(monkeypatch)

        assert set(captured["research_jobs"]) == set(ResearchJob.__table__.columns.keys())
        assert set(captured["research_steps"]) == set(ResearchStep.__table__.columns.keys())
