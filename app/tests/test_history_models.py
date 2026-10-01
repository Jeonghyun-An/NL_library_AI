import ast
import sys
import types
from pathlib import Path

import sqlalchemy as sa

from models.history import HISTORY_KINDS, HistoryItem

APP_DIR = Path(__file__).resolve().parents[1]
MIGRATION_PATH = APP_DIR / "alembic" / "versions" / "0006_history_items.py"
INDEX_NAME = "ix_history_items_session_kind_created"


def _column_signature(col, include_default=True):
    """(타입, nullable[, 기본값 유무]) — 컬럼 하나의 스키마 정합성 지문.

    PK 는 기본값을 비교하지 않는다. id 는 브라우저가 만들어 보내는 값이라 모델에도
    마이그레이션에도 기본값이 없어야 하고, 그건 아래 전용 테스트가 따로 본다.
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


def _index_parts(parts):
    """인덱스 구성요소를 이름 문자열로 — 컬럼은 이름, text("created_at DESC") 는 그 원문."""
    return [p.name if isinstance(p, sa.Column) else p if isinstance(p, str) else str(p) for p in parts]


def _model_indexes(table):
    sig = {}
    for ix in table.indexes:
        where = ix.dialect_options["postgresql"].get("where")
        sig[ix.name] = {
            "table_name": table.name,
            "parts": _index_parts(ix.expressions),
            "postgresql_where": str(where) if where is not None else None,
        }
    return sig


def _run_migration_upgrade(monkeypatch):
    """0006 의 upgrade() 를 alembic 없이 실행하고 create_table/create_index 호출을 캡처한다.

    로컬 venv 에 alembic 이 없어 op 를 스텁으로 갈아끼운다. create_table 인자로 진짜
    sa.Table 을 만들어 introspection 한다 — 인자를 직접 훑어 파싱하면 그 파싱이 또
    하나의 정합 리스크가 된다(test_research_models.py 와 같은 방식).
    """
    import importlib.util as u

    tables = {}
    indexes = {}

    def fake_create_table(name, *args, **kwargs):
        tables[name] = _table_signature(sa.Table(name, sa.MetaData(), *args))

    def fake_create_index(name, table_name, columns, **kwargs):
        where = kwargs.get("postgresql_where")
        indexes[name] = {
            "table_name": table_name,
            "parts": _index_parts(columns),
            "postgresql_where": str(where) if where is not None else None,
        }

    fake_op = types.ModuleType("alembic.op")
    fake_op.create_table = fake_create_table
    fake_op.create_index = fake_create_index
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = fake_op
    monkeypatch.setitem(sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(sys.modules, "alembic.op", fake_op)

    spec = u.spec_from_file_location("_migration_0006", MIGRATION_PATH)
    module = u.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    return module, tables, indexes


class TestHistoryModelShape:
    def test_columns(self):
        assert set(HistoryItem.__table__.columns.keys()) == {
            "id", "session_id", "user_id", "kind", "title", "params", "snapshot",
            "ai", "ref_id", "created_at", "updated_at", "deleted_at",
        }

    def test_id_has_no_default(self):
        # 기본값이 있으면 id 를 빠뜨린 저장이 조용히 새 행을 만든다 — 재전송이 중복을 쌓는다
        col = HistoryItem.__table__.c.id
        assert col.default is None and col.server_default is None

    def test_owner_is_required_and_user_is_placeholder(self):
        assert HistoryItem.__table__.c.session_id.nullable is False
        assert HistoryItem.__table__.c.user_id.nullable is True

    def test_kinds_fit_kind_column(self):
        assert HISTORY_KINDS == ("book", "paper", "research")
        max_len = HistoryItem.__table__.c.kind.type.length
        assert all(len(k) <= max_len for k in HISTORY_KINDS)

    def test_heavy_columns_store_none_as_sql_null(self):
        # JSON null 로 쓰면 has_snapshot(IS NOT NULL) 이 늘 참이 된다
        assert HistoryItem.__table__.c.snapshot.type.none_as_null is True
        assert HistoryItem.__table__.c.ai.type.none_as_null is True

    def test_list_index_is_partial_and_newest_first(self):
        ix = next(i for i in HistoryItem.__table__.indexes if i.name == INDEX_NAME)
        assert _index_parts(ix.expressions) == ["session_id", "kind", "created_at DESC"]
        assert str(ix.dialect_options["postgresql"]["where"]) == "deleted_at IS NULL"


class TestMigrationMatchesModel:
    def test_revision_chain(self, monkeypatch):
        module, _, _ = _run_migration_upgrade(monkeypatch)
        assert module.revision == "0006_history_items"
        assert module.down_revision == "0005_research_jobs"

    def test_upgrade_creates_columns_matching_orm(self, monkeypatch):
        _, tables, _ = _run_migration_upgrade(monkeypatch)
        assert tables == {"history_items": _table_signature(HistoryItem.__table__)}

    def test_upgrade_indexes_match_orm(self, monkeypatch):
        _, _, indexes = _run_migration_upgrade(monkeypatch)
        assert indexes == _model_indexes(HistoryItem.__table__)


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
        assert "models.history" in _imported_modules(APP_DIR / "alembic" / "env.py")

    def test_lifespan_create_all_sees_model(self):
        # create_all 은 import 된 모델만 만든다 — 라우터 import 의 부수효과에 기대지 않는다
        assert "models.history" in _imported_modules(APP_DIR / "main.py")
