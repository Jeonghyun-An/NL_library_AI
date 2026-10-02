"""scripts/bulk_ingest/select_near_empty_items.py — 빈 본문 완료 아이템 선정 규칙·출력."""
import csv
import datetime as _dt
import json
import re
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy import text

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "bulk_ingest"
sys.path.insert(0, str(SCRIPTS_DIR))

UTC = _dt.timezone.utc
KST = _dt.timezone(_dt.timedelta(hours=9))
META_COLUMNS = ["extract_method", "sections", "chunks", "vlm_capped"]


def _row(item_id, pages, body_chars, finished_at=None, **meta):
    """SQL 이 돌려주는 한 줄. meta 에서 꺼낸 칼럼은 문자열(`meta ->> 'x'`)이고, 키가 없으면 None."""
    return {
        "item_id": item_id, "book_id": f"KCI_FI{item_id:09d}", "pages": pages,
        "body_chars": body_chars,
        "finished_at": finished_at or _dt.datetime(2026, 9, 3, 4, 0, tzinfo=UTC),
        **{name: None for name in META_COLUMNS},
        **meta,
    }


class _FakeSession:
    """db.postgres.SyncSessionLocal() 이 돌려주는 세션 대역 - 실행한 문장을 순서대로 기록한다."""

    def __init__(self):
        self.rows = []
        self.executed = []          # [(SQL 문장, 바인드)]
        self.rolled_back = False
        self.closed = False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, params))
        if sql.startswith("SET "):
            return None
        return [types.SimpleNamespace(_mapping=row) for row in self.rows]

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def fake_session(monkeypatch):
    """스크립트가 함수 안에서 import 하는 db.postgres 를 대역으로 바꾼다 - 진짜 DB 에 닿지 않는다."""
    session = _FakeSession()
    db_pkg = types.ModuleType("db")
    db_pg = types.ModuleType("db.postgres")
    db_pg.SyncSessionLocal = lambda: session
    db_pkg.postgres = db_pg
    monkeypatch.setitem(sys.modules, "db", db_pkg)
    monkeypatch.setitem(sys.modules, "db.postgres", db_pg)
    return session


def test_selects_long_documents_below_threshold():
    from select_near_empty_items import select_near_empty

    rows = [
        _row(1, pages=10, body_chars=1000),   # 100자/쪽 — 고른다
        _row(2, pages=10, body_chars=1500),   # 150자/쪽 — 기준과 같으면 고르지 않는다
        _row(3, pages=7, body_chars=0),       # 8쪽 미만은 대상이 아니다
        _row(4, pages=8, body_chars=0),       # 본문 0 — 고른다
    ]
    picked = select_near_empty(rows, min_pages=8, max_chars_per_page=150)
    assert [r["item_id"] for r in picked] == [4, 1]       # 쪽당 글자 수 오름차순
    assert [r["chars_per_page"] for r in picked] == [0.0, 100.0]


def test_chars_per_page_is_rounded():
    from select_near_empty_items import select_near_empty

    [picked] = select_near_empty([_row(1, pages=30, body_chars=1001)], min_pages=8, max_chars_per_page=150)
    assert picked["chars_per_page"] == 33.4


def test_finished_by_day_uses_utc_dates():
    from select_near_empty_items import finished_by_day

    rows = [
        _row(1, 10, 0, _dt.datetime(2026, 9, 3, 8, 30, tzinfo=KST)),   # UTC 09-02 23:30
        _row(2, 10, 0, _dt.datetime(2026, 9, 3, 2, 0, tzinfo=UTC)),
        _row(3, 10, 0, _dt.datetime(2026, 9, 3, 7, 59, tzinfo=UTC)),
    ]
    assert finished_by_day(rows) == [("2026-09-02", 1), ("2026-09-03", 2)]


def test_retry_body_is_what_the_retry_api_takes():
    from select_near_empty_items import retry_body

    assert retry_body([_row(7, 10, 0), _row(3, 10, 0)]) == {"item_ids": [7, 3], "reset_stage": "pending"}


def test_write_outputs(tmp_path):
    from select_near_empty_items import retry_body, select_near_empty, write_outputs

    row = _row(5, pages=12, body_chars=120, extract_method="vlm", sections="3", chunks="9", vlm_capped="true")
    picked = select_near_empty([row], min_pages=8, max_chars_per_page=150)
    csv_path, json_path = write_outputs(tmp_path / "out", picked)

    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == [{
        "item_id": "5", "book_id": "KCI_FI000000005", "pages": "12", "body_chars": "120",
        "chars_per_page": "10.0", "finished_at": "2026-09-03T04:00:00+00:00",
        # 사람 검토용 - meta 에서 그대로 옮긴 값
        "extract_method": "vlm", "sections": "3", "chunks": "9", "vlm_capped": "true",
    }]
    # retry API 본문은 meta 칼럼과 상관없이 item_ids·reset_stage 뿐이다
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"item_ids": [5], "reset_stage": "pending"}
    assert json.loads(json_path.read_text(encoding="utf-8")) == retry_body(picked)


def test_csv_columns_and_blank_meta(tmp_path):
    from select_near_empty_items import select_near_empty, write_outputs

    # meta 에 그 키가 없는 아이템(SQL 이 NULL 을 돌려준다)은 칸을 비운다 - 'None' 글자가 들어가면 안 된다
    picked = select_near_empty([_row(6, pages=12, body_chars=0)], min_pages=8, max_chars_per_page=150)
    csv_path, _ = write_outputs(tmp_path / "out", picked)

    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        [row] = list(reader)
    assert reader.fieldnames == [
        "item_id", "book_id", "pages", "body_chars", "chars_per_page", "finished_at",
        "extract_method", "sections", "chunks", "vlm_capped",
    ]
    assert [row[name] for name in META_COLUMNS] == ["", "", "", ""]


def test_candidate_sql_binds_and_avoids_param_cast():
    from select_near_empty_items import CANDIDATES_SQL

    assert set(text(CANDIDATES_SQL).compile().params) == {"job", "before", "min_pages", "max_cpp"}
    # `:param::type` 는 SQLAlchemy 가 바인딩하지 못한다(함정 7번) — CAST(:p AS type) 로 쓴다
    assert re.search(r":\w+::", CANDIDATES_SQL) is None
    # 완료 12만 건의 본문을 다 풀지 않게, 크기만 보는 octet_length 로 먼저 거른다
    assert "octet_length" in CANDIDATES_SQL
    # 사람 검토용 meta 칼럼 - SQL 별칭이 CSV 칼럼 이름과 같다
    for name in META_COLUMNS:
        assert f"meta ->> '{name}' AS {name}" in CANDIDATES_SQL


def test_fetch_candidates_is_read_only_with_a_statement_timeout(fake_session):
    from select_near_empty_items import CANDIDATES_SQL, fetch_candidates

    fake_session.rows = [_row(1, pages=10, body_chars=0, extract_method="odl", vlm_capped="false")]
    rows = fetch_candidates("job-1", min_pages=8, max_chars_per_page=150.0, finished_before=None)

    # 본 질의보다 먼저: 쓰기는 DB 가 막고, 큰 집계가 길게 도는 동안 fastapi 가 재생성되면 lifespan 의
    # ALTER 가 배타 잠금을 기다리며 적재의 book_sections 접근을 줄 세운다(함정 18) - 15분에 끊는다
    assert [sql for sql, _ in fake_session.executed] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '15min'",
        CANDIDATES_SQL,
    ]
    assert fake_session.executed[2][1] == {"job": "job-1", "before": None, "min_pages": 8, "max_cpp": 150.0}
    assert rows == fake_session.rows
    assert fake_session.rolled_back and fake_session.closed


def test_help_prints_on_a_cp949_console(capsys):
    from select_near_empty_items import parse_args

    with pytest.raises(SystemExit) as exc:
        parse_args(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--finished-before" in out
    # Windows 한국어 콘솔(cp949)에서 --help 가 도는지 보는 로컬 확인 단계 - cp949 로 못 쓰는 글자(— 등)가
    # 있으면 UnicodeEncodeError 로 죽는다
    out.encode("cp949")


@pytest.mark.parametrize("value", ["2026-10-02T03:00:00", "내일"])
def test_argument_errors_print_on_a_cp949_console(value, capsys):
    from select_near_empty_items import parse_args

    with pytest.raises(SystemExit) as exc:
        parse_args(["--job", "j", "--out", "o", "--finished-before", value])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--finished-before" in err
    err.encode("cp949")


def test_finished_before_needs_a_timezone():
    from select_near_empty_items import parse_args

    args = parse_args(["--job", "j", "--out", "o", "--finished-before", "2026-10-02T03:00:00+00:00"])
    assert args.finished_before == "2026-10-02T03:00:00+00:00"
    with pytest.raises(SystemExit):
        parse_args(["--job", "j", "--out", "o", "--finished-before", "2026-10-02T03:00:00"])
