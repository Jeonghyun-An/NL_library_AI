import sys
import types
from pathlib import Path

import sqlalchemy as sa

from models.research import (
    JOB_STAGES, JOB_STATUSES, RUNNABLE_STATUSES, STATUS_CANCELED, STEP_KINDS,
    STEP_STATUSES, ResearchJob, ResearchStep,
)

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0005_research_jobs.py"


def _column_signature(col, include_default=True):
    """(타입, nullable[, 기본값 유무]) — 컬럼 하나의 스키마 정합성 지문.

    PK 는 include_default=False 로 호출한다: 모델의 id 는 default=uuid.uuid4
    (ORM 레벨 생성)이고 마이그레이션에는 대응하는 server_default 가 없다 —
    UUID 를 만드는 주체가 DB 가 아니라 애플리케이션이라는 의도적 설계라
    기본값 유무를 비교 대상에서 뺀다. 타입·nullable 은 PK 도 계속 비교한다.
    """
    sig = [str(col.type), col.nullable]
    if include_default:
        sig.append(col.server_default is not None or col.default is not None)
    return tuple(sig)


def _table_signature(table):
    return {
        c.name: _column_signature(c, include_default=not c.primary_key)
        for c in table.columns
    }


def _model_index_signature(table):
    sig = {}
    for ix in table.indexes:
        where = ix.dialect_options["postgresql"].get("where")
        sig[ix.name] = {
            "name": ix.name,
            "table_name": table.name,
            "columns": [c.name for c in ix.columns],
            "postgresql_where": str(where) if where is not None else None,
        }
    return sig


def _run_migration_upgrade(monkeypatch, migration_path=MIGRATION_PATH):
    """0005 의 upgrade() 를 실제 alembic 없이 실행하고 create_table/create_index 호출을 캡처한다.

    로컬 venv 에 alembic 이 설치돼 있지 않아 (app/requirements.txt 에는 있으나 미설치)
    `from alembic import op` 를 만족시키는 최소 스텁만 넣는다 — upgrade() 는 op.create_table /
    op.create_index 만 호출하므로 그 둘만 흉내 내면 충분하다.

    create_table 은 넘어온 Column/UniqueConstraint 인자로 실제 sa.Table 을 만들어 바인딩한다
    (컬럼 이름만이 아니라 타입·nullable·기본값·제약까지 실제 SQLAlchemy introspection 으로
    읽기 위해서 — 인자를 훑어 직접 파싱하면 캡처 로직 자체가 또 하나의 정합 리스크가 된다).
    """
    import importlib.util as u

    tables = {}
    unique_constraints = {}
    indexes = []

    def fake_create_table(name, *args, **kwargs):
        table = sa.Table(name, sa.MetaData(), *args)
        tables[name] = _table_signature(table)
        unique_constraints[name] = {
            c.name: [col.name for col in c.columns]
            for c in table.constraints
            if isinstance(c, sa.UniqueConstraint)
        }

    def fake_create_index(name, table_name, columns, **kwargs):
        where = kwargs.get("postgresql_where")
        indexes.append({
            "name": name,
            "table_name": table_name,
            "columns": list(columns),
            "postgresql_where": str(where) if where is not None else None,
        })

    fake_op = types.ModuleType("alembic.op")
    fake_op.create_table = fake_create_table
    fake_op.create_index = fake_create_index

    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = fake_op

    monkeypatch.setitem(sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(sys.modules, "alembic.op", fake_op)

    spec = u.spec_from_file_location("_migration_0005", migration_path)
    module = u.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    return {"tables": tables, "unique_constraints": unique_constraints, "indexes": indexes}


class TestResearchModelShape:
    def test_job_table_columns(self):
        cols = set(ResearchJob.__table__.columns.keys())
        assert {"id", "question", "status", "params", "plan", "report"} <= cols

    def test_step_table_columns(self):
        cols = set(ResearchStep.__table__.columns.keys())
        assert {"job_id", "seq", "kind", "subq_idx", "title",
                "detail", "status", "result", "updated_at"} <= cols

    def test_step_has_job_seq_unique_constraint(self):
        uq = next(
            c for c in ResearchStep.__table__.constraints
            if getattr(c, "name", None) == "uq_research_steps_job_seq"
        )
        # 순서가 인덱스 활용 여부를 가른다 — job_id 선두가 아니면 job_id 단독 조회에
        # 이 유일 제약이 인덱스로 쓰이지 못한다.
        assert [c.name for c in uq.columns] == ["job_id", "seq"]

    def test_inflight_index_condition(self):
        idx = next(
            ix for ix in ResearchStep.__table__.indexes
            if ix.name == "ix_research_steps_inflight"
        )
        where_clause = idx.dialect_options["postgresql"]["where"]
        assert str(where_clause) == "status = 'running'"

    def test_step_job_fk_cascades_on_delete(self):
        fk = next(iter(ResearchStep.__table__.c.job_id.foreign_keys))
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

    def test_job_stage_default_is_valid_stage(self):
        default = ResearchJob.__table__.c.stage.server_default.arg.text.strip("'")
        assert default in JOB_STAGES

    def test_job_stages_fit_stage_column(self):
        max_len = ResearchJob.__table__.c.stage.type.length
        assert all(len(v) <= max_len for v in JOB_STAGES)

    def test_stage_is_not_nullable(self):
        # NULL stage 는 재개 분기(stage == "explored")에서 조용히 탐색부터 다시 돌게 한다
        assert ResearchJob.__table__.c.stage.nullable is False

    def test_runnable_statuses_are_declared_statuses(self):
        # API 의 approve·retry 가 쓰는 값이자 워커 _claim 이 받는 값이다.
        # JOB_STATUSES 에 없는 값을 쓰면 상태 목록이 거짓말이 된다.
        assert set(RUNNABLE_STATUSES) <= set(JOB_STATUSES)

    def test_canceled_spelling_is_single_l(self):
        # models/ingest_job.py 가 canceled(l 하나) 다 — 두 잡 계열이 철자를
        # 달리 쓰면 상태 비교가 조용히 빗나간다
        assert STATUS_CANCELED == "canceled"
        assert STATUS_CANCELED in JOB_STATUSES


class TestMigrationMatchesModel:
    def test_upgrade_creates_columns_matching_orm(self, monkeypatch):
        captured = _run_migration_upgrade(monkeypatch)

        assert captured["tables"]["research_jobs"] == _table_signature(ResearchJob.__table__)
        assert captured["tables"]["research_steps"] == _table_signature(ResearchStep.__table__)

    def test_upgrade_unique_constraint_matches_orm(self, monkeypatch):
        captured = _run_migration_upgrade(monkeypatch)

        model_uq = {
            c.name: [col.name for col in c.columns]
            for c in ResearchStep.__table__.constraints
            if isinstance(c, sa.UniqueConstraint)
        }
        assert captured["unique_constraints"]["research_steps"] == model_uq

    def test_upgrade_indexes_match_orm(self, monkeypatch):
        captured = _run_migration_upgrade(monkeypatch)
        migration_indexes = {ix["name"]: ix for ix in captured["indexes"]}

        model_indexes = {}
        for table in (ResearchJob.__table__, ResearchStep.__table__):
            model_indexes.update(_model_index_signature(table))

        assert migration_indexes == model_indexes
