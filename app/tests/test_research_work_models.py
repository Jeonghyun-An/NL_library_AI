"""models/research_work.py — 연구 어시스턴트(round06) 테이블 7개.

모델 ↔ 마이그레이션 0007 ↔ 등록(main.py lifespan·alembic env) 정합과, 다른 테스트가 쓰는
SQLite 대역(history_sqlite.make_engine)이 새 테이블의 부분 유니크 인덱스를 지키는지 본다.
"""
import ast
import asyncio
import sys
import types
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.research_work import (
    FACET_SCHEMA_VER, GEN_KINDS, GEN_OPEN_STATUSES, GEN_STATUSES, PRIORITY_BACKGROUND,
    PRIORITY_USER, READING_ORIGINS, READING_STATES, TOPIC_ORIGINS, TOPIC_STATES, WORK_PHASES,
    PaperFacet, ResearchGapCheck, ResearchGeneration, ResearchProposal, ResearchReading,
    ResearchTopic, ResearchWork,
)

APP_DIR = Path(__file__).resolve().parents[1]
MIGRATION_PATH = APP_DIR / "alembic" / "versions" / "0007_research_work.py"
MODELS = (ResearchWork, ResearchGeneration, ResearchTopic, ResearchGapCheck,
          ResearchReading, PaperFacet, ResearchProposal)
TABLES = [m.__table__ for m in MODELS]


def _column_signature(col, include_default=True):
    """(타입, nullable[, 기본값 유무]) — test_history_models.py 와 같은 지문. PK 는 기본값을 비교하지 않는다."""
    sig = [str(col.type), col.nullable]
    if include_default:
        sig.append(col.server_default is not None or col.default is not None)
    return tuple(sig)


def _table_signature(table):
    return {c.name: _column_signature(c, include_default=not c.primary_key) for c in table.columns}


def _fk_signature(table):
    return {(fk.parent.name, fk.target_fullname, fk.ondelete) for fk in table.foreign_keys}


def _index_parts(parts):
    return [p.name if isinstance(p, sa.Column) else p if isinstance(p, str) else str(p) for p in parts]


def _model_indexes(tables):
    sig = {}
    for table in tables:
        for ix in table.indexes:
            where = ix.dialect_options["postgresql"].get("where")
            sig[ix.name] = {
                "table_name": table.name,
                "parts": _index_parts(ix.expressions),
                "unique": bool(ix.unique),
                "postgresql_where": str(where) if where is not None else None,
            }
    return sig


def _run_migration(monkeypatch):
    """0007 의 upgrade()·downgrade() 를 alembic 없이 실행하고 op 호출을 캡처한다(로컬에 alembic 이 없다)."""
    import importlib.util as u

    captured = {"tables": {}, "fks": {}, "indexes": {}, "index_kwargs": set(),
                "created": [], "dropped": []}

    def fake_create_table(name, *args, **kwargs):
        table = sa.Table(name, sa.MetaData(), *args)
        captured["tables"][name] = _table_signature(table)
        captured["fks"][name] = _fk_signature(table)
        captured["created"].append(name)

    def fake_create_index(name, table_name, columns, **kwargs):
        where = kwargs.get("postgresql_where")
        captured["indexes"][name] = {
            "table_name": table_name,
            "parts": _index_parts(columns),
            "unique": bool(kwargs.get("unique", False)),
            "postgresql_where": str(where) if where is not None else None,
        }
        captured["index_kwargs"].update(kwargs)

    def fake_drop_table(name, *args, **kwargs):
        captured["dropped"].append(name)

    fake_op = types.ModuleType("alembic.op")
    fake_op.create_table = fake_create_table
    fake_op.create_index = fake_create_index
    fake_op.drop_table = fake_drop_table
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = fake_op
    monkeypatch.setitem(sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(sys.modules, "alembic.op", fake_op)

    spec = u.spec_from_file_location("_migration_0007", MIGRATION_PATH)
    module = u.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    module.downgrade()
    return module, captured


def _index(table, name):
    return next(ix for ix in table.indexes if ix.name == name)


class TestModelShape:
    def test_seven_tables_with_contract_names(self):
        assert [t.name for t in TABLES] == [
            "research_works", "research_generations", "research_topics", "research_gap_checks",
            "research_reading", "paper_facets", "research_proposals",
        ]

    def test_work_id_is_the_research_job_id(self):
        # 연구 id = 출발 딥리서치 잡 id — 잡을 지우면 연구도 지워지고, 기본값으로 새 id 를 만들지 않는다
        col = ResearchWork.__table__.c.id
        assert col.primary_key and col.default is None and col.server_default is None
        assert _fk_signature(ResearchWork.__table__) == {("id", "research_jobs.id", "CASCADE")}

    def test_children_cascade_from_research_works(self):
        for model in (ResearchGeneration, ResearchTopic, ResearchGapCheck, ResearchReading,
                      ResearchProposal):
            assert ("work_id", "research_works.id", "CASCADE") in _fk_signature(model.__table__)
        assert ("parent_id", "research_topics.id", "CASCADE") in _fk_signature(ResearchTopic.__table__)
        assert _fk_signature(PaperFacet.__table__) == set()   # 연구를 가로지르는 공용 캐시

    def test_composite_primary_keys(self):
        assert [c.name for c in ResearchReading.__table__.primary_key] == ["work_id", "cnts_id"]
        assert [c.name for c in PaperFacet.__table__.primary_key] == ["cnts_id", "schema_ver"]
        assert [c.name for c in ResearchProposal.__table__.primary_key] == ["work_id"]

    @pytest.mark.parametrize("values, column", [
        (WORK_PHASES, ResearchWork.__table__.c.phase),
        (GEN_KINDS, ResearchGeneration.__table__.c.kind),
        (GEN_STATUSES, ResearchGeneration.__table__.c.status),
        (TOPIC_ORIGINS, ResearchTopic.__table__.c.origin),
        (TOPIC_STATES, ResearchTopic.__table__.c.state),
        (READING_STATES, ResearchReading.__table__.c.state),
        (READING_ORIGINS, ResearchReading.__table__.c.origin),
    ], ids=["phase", "kind", "gen-status", "topic-origin", "topic-state", "reading-state",
            "reading-origin"])
    def test_enumerations_fit_their_columns(self, values, column):
        assert values and all(len(v) <= column.type.length for v in values)

    @pytest.mark.parametrize("column, allowed", [
        (ResearchWork.__table__.c.phase, WORK_PHASES),
        (ResearchGeneration.__table__.c.status, GEN_STATUSES),
        (ResearchTopic.__table__.c.state, TOPIC_STATES),
        (ResearchReading.__table__.c.state, READING_STATES),
    ], ids=["phase", "gen-status", "topic-state", "reading-state"])
    def test_server_defaults_are_declared_values(self, column, allowed):
        assert column.nullable is False
        assert column.server_default.arg.text.strip("'") in allowed

    def test_generation_constants(self):
        assert set(GEN_OPEN_STATUSES) <= set(GEN_STATUSES)
        assert GEN_OPEN_STATUSES == ("queued", "running")
        assert PRIORITY_USER > PRIORITY_BACKGROUND      # 사용자가 누른 생성이 배경 추출보다 먼저
        assert FACET_SCHEMA_VER == 1

    def test_optional_json_columns_store_none_as_sql_null(self):
        # JSON null 로 쓰면 IS NULL 검사가 늘 거짓이 된다(history.snapshot 과 같은 이유)
        for col in (ResearchWork.__table__.c.corpus_snapshot, ResearchGeneration.__table__.c.output,
                    ResearchTopic.__table__.c.corpus_snapshot,
                    ResearchGapCheck.__table__.c.corpus_snapshot):
            assert col.type.none_as_null is True, col

    def test_one_running_generation_per_work_on_both_dialects(self):
        # 전역 1건 디스패처의 이중 안전장치. sqlite_where 가 빠지면 SQLite 테스트에서 전체 유니크가 된다
        ix = _index(ResearchGeneration.__table__, "ux_research_generations_running")
        assert ix.unique and _index_parts(ix.expressions) == ["work_id"]
        pg = str(CreateIndex(ix).compile(dialect=postgresql.dialect()))
        lite = str(CreateIndex(ix).compile(dialect=sqlite.dialect()))
        assert pg.endswith("WHERE status = 'running'") and lite.endswith("WHERE status = 'running'")

    def test_first_four_topic_slots_are_unique_per_work(self):
        ix = _index(ResearchTopic.__table__, "ux_research_topics_slot")
        assert ix.unique and _index_parts(ix.expressions) == ["work_id", "slot"]
        lite = str(CreateIndex(ix).compile(dialect=sqlite.dialect()))
        assert str(ix.dialect_options["postgresql"]["where"]) == "slot IS NOT NULL"
        assert lite.endswith("WHERE slot IS NOT NULL")

    def test_dispatch_order_index_is_partial_on_queued(self):
        ix = _index(ResearchGeneration.__table__, "ix_research_generations_queued")
        assert _index_parts(ix.expressions) == ["priority DESC", "created_at", "id"]
        assert str(ix.dialect_options["postgresql"]["where"]) == "status = 'queued'"

    def test_owner_list_index_is_partial_and_newest_first(self):
        ix = _index(ResearchWork.__table__, "ix_research_works_owner_created")
        assert _index_parts(ix.expressions) == ["owner_sid", "created_at DESC"]
        assert str(ix.dialect_options["postgresql"]["where"]) == "deleted_at IS NULL"


class TestMigrationMatchesModel:
    def test_revision_chain(self, monkeypatch):
        module, _ = _run_migration(monkeypatch)
        assert module.revision == "0007_research_work"
        assert module.down_revision == "0006_history_items"

    def test_upgrade_creates_columns_matching_orm(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["tables"] == {t.name: _table_signature(t) for t in TABLES}

    def test_upgrade_foreign_keys_match_orm(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["fks"] == {t.name: _fk_signature(t) for t in TABLES}

    def test_upgrade_indexes_match_orm(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["indexes"] == _model_indexes(TABLES)

    def test_migration_has_no_sqlite_options(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["index_kwargs"] <= {"unique", "postgresql_where"}

    def test_downgrade_drops_in_reverse_order(self, monkeypatch):
        _, captured = _run_migration(monkeypatch)
        assert captured["dropped"] == list(reversed(captured["created"]))


def _imported_modules(path: Path) -> set[str]:
    """파일이 import 하는 모듈 이름 — `import a.b` 는 "a.b", `from a import b` 는 "a.b"."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


class TestModelRegistration:
    def test_alembic_env_registers_model(self):
        # 빠뜨리면 autogenerate 가 이 테이블을 모르는 것으로 보고 DROP TABLE 을 만든다
        assert "models.research_work" in _imported_modules(APP_DIR / "alembic" / "env.py")

    def test_lifespan_create_all_sees_models(self):
        # create_all 은 import 된 모델만 만든다 — research_works 의 FK 대상(research_jobs)도
        # 라우터 import 의 부수효과에 기대지 않고 명시한다
        imported = _imported_modules(APP_DIR / "main.py")
        assert {"models.research", "models.research_work"} <= imported


class TestSqliteHarness:
    """history_sqlite 가 새 테이블을 진짜 SQL 로 받는지 — 디스패처·API 테스트가 이 위에서 돈다."""

    @pytest.fixture
    def engine(self):
        return make_engine()

    def test_research_tables_exist(self, engine):
        names = set(sa.inspect(engine).get_table_names())
        assert {"research_jobs", "research_works", "research_generations"} <= names

    def test_generation_ids_are_assigned_by_the_database(self, engine):
        work = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work)
        first = add_generation(engine, work)
        second = add_generation(engine, work, kind="topic_card")
        assert isinstance(first, int) and second > first

    def test_second_running_generation_in_a_work_is_rejected(self, engine):
        work = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work)
        add_generation(engine, work, status="running")
        add_generation(engine, work, status="queued")        # 부분 인덱스 — queued 는 몇 건이든
        add_generation(engine, work, status="done")
        with pytest.raises(sa.exc.IntegrityError):
            add_generation(engine, work, status="running")

    def test_running_generations_in_different_works_coexist(self, engine):
        for _ in range(2):
            work = add_research_job(engine, status="completed", stage="synthesized")
            add_work(engine, work)
            add_generation(engine, work, status="running")
        with engine.connect() as conn:
            n = conn.execute(sa.text(
                "SELECT count(*) FROM research_generations WHERE status = 'running'")).scalar_one()
        assert n == 2

    def test_add_work_stores_contract_defaults(self, engine):
        work = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work, owner_sid="sid-a", concepts=["독서", "격차"])
        with engine.connect() as conn:
            row = conn.execute(sa.select(ResearchWork.__table__)).one()
        assert (row.id, row.owner_sid, row.phase, row.concepts, row.concept_members,
                row.progress, row.is_example) == (work, "sid-a", "topics", ["독서", "격차"], {}, {},
                                                  False)

    def test_advisory_lock_is_a_no_op_function(self, engine):
        async def _go():
            db = AsyncSessionOverSync(engine)
            try:
                return await db.scalar(sa.select(sa.func.pg_advisory_xact_lock(42)))
            finally:
                await db.close()
        assert asyncio.run(_go()) is None

    def test_async_session_get_add_flush_scalar(self, engine):
        work = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work)

        async def _go():
            db = AsyncSessionOverSync(engine)
            try:
                gen = ResearchGeneration(work_id=work, kind="concepts", priority=PRIORITY_USER,
                                         status="queued", input={"question": "독서 격차"})
                db.add(gen)
                await db.flush()
                gen_id = gen.id
                await db.commit()
                loaded = await db.get(ResearchGeneration, gen_id)
                n = await db.scalar(
                    sa.select(sa.func.count()).select_from(ResearchGeneration)
                    .where(ResearchGeneration.work_id == work)
                )
                return gen_id, loaded.kind, loaded.input, (await db.get(ResearchWork, work)).phase, n
            finally:
                await db.close()

        gen_id, kind, inp, phase, n = asyncio.run(_go())
        assert isinstance(gen_id, int)
        assert (kind, inp, phase, n) == ("concepts", {"question": "독서 격차"}, "topics", 1)

    def test_get_of_unknown_work_is_none(self, engine):
        # make_engine 은 부를 때마다 빈 DB 다 — 테스트끼리 행을 나누지 않는다
        async def _go():
            db = AsyncSessionOverSync(engine)
            try:
                return await db.get(ResearchWork, uuid.uuid4())
            finally:
                await db.close()
        assert asyncio.run(_go()) is None
