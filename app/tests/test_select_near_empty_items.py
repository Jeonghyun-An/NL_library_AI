"""scripts/bulk_ingest/select_near_empty_items.py — 빈 본문 완료 아이템 선정 규칙·출력."""
import csv
import datetime as _dt
import json
import re
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "bulk_ingest"
sys.path.insert(0, str(SCRIPTS_DIR))

UTC = _dt.timezone.utc
KST = _dt.timezone(_dt.timedelta(hours=9))


def _row(item_id, pages, body_chars, finished_at=None):
    return {
        "item_id": item_id, "book_id": f"KCI_FI{item_id:09d}", "pages": pages,
        "body_chars": body_chars,
        "finished_at": finished_at or _dt.datetime(2026, 9, 3, 4, 0, tzinfo=UTC),
    }


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

    picked = select_near_empty([_row(5, pages=12, body_chars=120)], min_pages=8, max_chars_per_page=150)
    csv_path, json_path = write_outputs(tmp_path / "out", picked)

    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == [{
        "item_id": "5", "book_id": "KCI_FI000000005", "pages": "12", "body_chars": "120",
        "chars_per_page": "10.0", "finished_at": "2026-09-03T04:00:00+00:00",
    }]
    assert json.loads(json_path.read_text(encoding="utf-8")) == retry_body(picked)


def test_candidate_sql_binds_and_avoids_param_cast():
    from select_near_empty_items import CANDIDATES_SQL

    assert set(text(CANDIDATES_SQL).compile().params) == {"job", "before", "min_pages", "max_cpp"}
    # `:param::type` 는 SQLAlchemy 가 바인딩하지 못한다(함정 7번) — CAST(:p AS type) 로 쓴다
    assert re.search(r":\w+::", CANDIDATES_SQL) is None
    # 완료 12만 건의 본문을 다 풀지 않게, 크기만 보는 octet_length 로 먼저 거른다
    assert "octet_length" in CANDIDATES_SQL


def test_finished_before_needs_a_timezone():
    from select_near_empty_items import parse_args

    args = parse_args(["--job", "j", "--out", "o", "--finished-before", "2026-10-02T03:00:00+00:00"])
    assert args.finished_before == "2026-10-02T03:00:00+00:00"
    with pytest.raises(SystemExit):
        parse_args(["--job", "j", "--out", "o", "--finished-before", "2026-10-02T03:00:00"])
