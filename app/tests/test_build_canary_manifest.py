"""scripts/bulk_ingest/build_canary_manifest.py — 카나리 범주 판정·선정·매니페스트."""
import hashlib
import json
import random
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy import text

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "bulk_ingest"
sys.path.insert(0, str(SCRIPTS_DIR))

NO_SECTIONS = "섹션 없음 — extract 단계부터 재실행 필요"


class _FakeSession:
    """db.postgres.SyncSessionLocal() 이 돌려주는 세션 대역 - 실행한 문장을 순서대로 기록한다."""

    def __init__(self):
        self.executed = []          # [(SQL 문장, 바인드)]
        self.rolled_back = False
        self.closed = False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, params))
        return None if sql.startswith("SET ") else []

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


def _item(item_id, status="done", error_group=None, last_error=None, **meta):
    return {
        "id": item_id, "book_id": f"KCI_FI{item_id:09d}",
        "source_key": f"originals/KCI_FI{item_id:09d}/KCI_FI{item_id:09d}.pdf",
        "status": status, "error_group": error_group, "last_error": last_error, "meta": meta,
    }


def _pool():
    """범주마다 몫보다 넉넉한 후보 — 스캔 30·표 15·쪼개짐 8·섹션 8·보통 40."""
    rows, n = [], 0
    for _ in range(30):
        n += 1
        rows.append(_item(n, "failed", "not_found", NO_SECTIONS, pages=12))
    for _ in range(15):
        n += 1
        rows.append(_item(n, pages=12, chunks=20, n_tables=7, sections_total=6))
    for _ in range(8):
        n += 1
        rows.append(_item(n, pages=10, chunks=80, n_tables=0, sections_total=9))
    for _ in range(8):
        n += 1
        rows.append(_item(n, pages=40, chunks=90, n_tables=1, sections_total=55))
    for _ in range(40):
        n += 1
        rows.append(_item(n, pages=14, chunks=30, n_tables=1, sections_total=8))
    return rows


class TestClassify:
    def test_failed_without_sections_is_scan_candidate(self):
        from build_canary_manifest import classify

        assert classify(_item(1, "failed", "not_found", NO_SECTIONS)) == "scan_no_sections"

    def test_other_failures_are_not_picked(self):
        from build_canary_manifest import classify

        # '카탈로그 row 없음' 은 카탈로그 문제다 — 카나리로 볼 것이 없다
        assert classify(_item(1, "failed", "not_found", "카탈로그 row 없음")) is None
        assert classify(_item(2, "failed", "extract_empty", "텍스트 추출 실패: []")) is None
        assert classify(_item(3, "pending")) is None

    def test_done_categories(self):
        from build_canary_manifest import classify

        assert classify(_item(1, n_tables=5, pages=10, chunks=10)) == "many_tables"
        assert classify(_item(2, pages=10, chunks=61)) == "dense_chunks"      # 쪽당 6.1
        assert classify(_item(3, pages=10, chunks=60)) == "normal"            # 쪽당 6 은 초과가 아니다
        assert classify(_item(4, pages=10, chunks=20, sections_total=41)) == "many_sections"
        assert classify(_item(5)) == "normal"                                 # meta 가 비어도 보통

    def test_meta_numbers_must_be_json_numbers_like_the_sql(self):
        # SQL 의 _meta_num 은 jsonb 숫자만 숫자로 본다(숫자 문자열은 NULL) — 파이썬 판정도 같아야 후보와 범주가 맞는다
        from build_canary_manifest import _num, classify

        assert classify(_item(1, n_tables="7", pages=10, chunks=10)) == "normal"
        assert classify(_item(2, pages="10", chunks=90)) == "normal"        # 쪽수가 문자열이면 0 — 쪼개짐 판정 없음
        assert classify(_item(3, n_tables=7.0, pages=10, chunks=10)) == "many_tables"
        assert [_num({"x": v}, "x") for v in (True, False, None, "3", 3, 2.5)] == [0, 0, 0, 0, 3, 2.5]

    def test_earlier_category_wins(self):
        from build_canary_manifest import classify

        assert classify(_item(1, n_tables=6, pages=10, chunks=90, sections_total=50)) == "many_tables"
        assert classify(_item(2, pages=10, chunks=90, sections_total=50)) == "dense_chunks"


class TestPick:
    def test_quotas_are_filled(self):
        from build_canary_manifest import QUOTAS, pick_canary

        picked = pick_canary(_pool())
        counts = {c: sum(1 for r in picked if r["category"] == c) for c in QUOTAS}
        assert counts == QUOTAS
        assert len({r["book_id"] for r in picked}) == sum(QUOTAS.values()) == 50

    def test_same_seed_same_pick_whatever_the_row_order(self):
        from build_canary_manifest import pick_canary

        rows = _pool()
        shuffled = rows[:]
        random.Random(1).shuffle(shuffled)
        assert pick_canary(rows, seed="s1") == pick_canary(shuffled, seed="s1")

    def test_pick_follows_the_seed_hash_not_the_id_order(self):
        from build_canary_manifest import order_key, pick_canary

        rows = _pool()
        scans = [r for r in rows if r["status"] == "failed"]
        expected = sorted(scans, key=lambda r: order_key(r["book_id"], "s1"))[:20]
        picked = [r for r in pick_canary(rows, seed="s1") if r["category"] == "scan_no_sections"]
        assert [r["id"] for r in picked] == [r["id"] for r in expected]
        assert {r["id"] for r in picked} != {r["id"] for r in scans[:20]}  # id 순 앞 20건이 아니다

    def test_order_key_matches_the_sql_md5(self):
        from build_canary_manifest import order_key

        # SQL 은 md5(book_id || :seed) 순으로 후보를 자른다 — 같은 순서여야 한다
        assert order_key("KCI_FI001", "round07") == hashlib.md5(b"KCI_FI001round07").hexdigest()

    def test_shortfalls(self):
        from build_canary_manifest import pick_canary, shortfalls

        rows = [r for r in _pool() if r["meta"].get("chunks") != 80]
        rows += [_item(900 + i, pages=10, chunks=80) for i in range(3)]
        assert shortfalls(pick_canary(rows)) == {"dense_chunks": 2}


class TestManifest:
    def test_rows_use_the_job_items_source_key(self):
        from build_canary_manifest import manifest_rows, pick_canary

        row = manifest_rows(pick_canary(_pool()))[0]
        assert set(row) == {"book_id", "object_key", "category", "item_id"}
        assert row["object_key"] == f"originals/{row['book_id']}/{row['book_id']}.pdf"

    def test_job_manager_accepts_the_manifest(self, tmp_path):
        from build_canary_manifest import manifest_rows, pick_canary, write_manifest
        from services.ingestion.job_manager import build_job_plan

        path = tmp_path / "manifest.jsonl"
        write_manifest(path, manifest_rows(pick_canary(_pool())))
        manifest = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        keys = {r["object_key"] for r in manifest}
        ids = {r["book_id"] for r in manifest}
        # 완료분도 다시 돌리므로 reembed=True — 이미 임베딩된 문서도 빼지 않는다
        items, report = build_job_plan(manifest, keys, ids, ids, reembed=True)
        assert report["to_ingest"] == 50 and not report["missing_object"] and not report["missing_meta"]
        assert {it["source_key"] for it in items} == keys

    def test_next_steps_print_upload_create_and_start(self):
        from build_canary_manifest import next_steps

        steps = "\n".join(next_steps("/app/data/round07/canary/manifest.jsonl", "round07-canary"))
        assert "'manifests/round07-canary/manifest.jsonl', '/app/data/round07/canary/manifest.jsonl'" in steps
        assert '"manifest_key":"manifests/round07-canary/manifest.jsonl"' in steps
        assert '"params":{"reembed":true,"skip_cover":true}' in steps
        assert "/start" in steps


def test_candidate_sql_binds():
    from build_canary_manifest import CATEGORY_FILTERS, QUOTAS, candidate_sql

    assert set(CATEGORY_FILTERS) == set(QUOTAS)
    for category in QUOTAS:
        sql = candidate_sql(category)
        assert "md5(book_id || :seed)" in sql
        assert set(text(sql).compile().params) <= {"job", "seed", "cap", "pat"}


def test_fetch_candidates_is_read_only_with_a_statement_timeout(fake_session):
    from build_canary_manifest import QUOTAS, candidate_sql, fetch_candidates

    assert fetch_candidates("job-1", "round07", 20) == []

    statements = [sql for sql, _ in fake_session.executed]
    # 후보 질의보다 먼저: 쓰기는 DB 가 막고, 큰 집계가 길게 도는 동안 fastapi 가 재생성되면 lifespan 의
    # ALTER 가 배타 잠금을 기다리며 적재의 book_sections 접근을 줄 세운다(함정 18) - 15분에 끊는다.
    # 같은 트랜잭션이라 범주 질의 다섯 개 모두에 걸린다
    assert statements[:2] == ["SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout = '15min'"]
    assert statements[2:] == [candidate_sql(category) for category in QUOTAS]
    # 범주마다 몫 × oversample 건까지만 읽고, 패턴 바인드는 스캔본 범주에만 쓴다
    params = [p for _, p in fake_session.executed[2:]]
    assert [p["cap"] for p in params] == [quota * 20 for quota in QUOTAS.values()]
    assert ["pat" in p for p in params] == [True, False, False, False, False]
    assert fake_session.rolled_back and fake_session.closed


def test_summary_prints_on_a_cp949_console(fake_session, tmp_path, capsys):
    # 후보가 없어 범주마다 '모자람' 줄까지 찍힌다 — 요약 출력도 Windows 한국어 콘솔(cp949)에서 죽지 않아야 한다
    from build_canary_manifest import main

    main(["--job", "job-1", "--out", str(tmp_path)])

    out = capsys.readouterr().out
    assert "모자람" in out
    out.encode("cp949")


def test_help_prints_on_a_cp949_console(capsys):
    from build_canary_manifest import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--oversample" in out
    # Windows 한국어 콘솔(cp949)에서 --help 가 도는지 보는 로컬 확인 단계 - cp949 로 못 쓰는 글자(— 등)가
    # 있으면 UnicodeEncodeError 로 죽는다
    out.encode("cp949")
