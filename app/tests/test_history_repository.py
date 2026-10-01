"""test_history_repository.py — 기록 저장소

history_sqlite 의 SQLite 위에서 저장소가 내는 SQL 을 실제로 실행한다. 한 번의 _call 이
요청 하나다 — 세션을 열고, 끝나면 커밋하고 닫는다.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from history_sqlite import SID_A, SID_B, AsyncSessionOverSync, add_research_job, make_engine, raw_row
from models.history import HistoryItem
from repositories.history import (
    HistoryRepository, InvalidCursor, decode_cursor, encode_cursor, legacy_history_id,
)
from schemas.history import HistoryImportItem, HistoryItemIn, HistoryItemPatch

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    return make_engine()


def _call(engine, fn):
    async def _go():
        db = AsyncSessionOverSync(engine)
        try:
            result = await fn(HistoryRepository(db))
            await db.commit()
            return result
        finally:
            await db.close()
    return asyncio.run(_go())


def _put(engine, sid, item_id, **fields):
    data = HistoryItemIn(**{"kind": "book", "title": "독서 격차", **fields})
    return _call(engine, lambda r: r.upsert(sid, item_id, data))


def _import(engine, sid, *items):
    return _call(engine, lambda r: r.import_items(sid, [HistoryImportItem(**i) for i in items]))


def _list(engine, sid, kind=None, limit=30, before=None):
    return _call(engine, lambda r: r.list(sid, kind, limit, before))


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


class TestLegacyId:
    def test_is_deterministic_uuid5(self):
        expected = uuid.uuid5(uuid.NAMESPACE_URL, "nl-lib-history-v1:1727000000000")
        assert legacy_history_id("1727000000000") == expected
        assert legacy_history_id("1727000000000") == legacy_history_id("1727000000000")

    def test_different_v1_ids_differ(self):
        assert legacy_history_id("1727000000000") != legacy_history_id("1727000000001")


class TestCursor:
    def test_round_trip(self):
        item_id = uuid.uuid4()
        at = datetime(2026, 9, 26, 10, 0, 0, 123456, tzinfo=timezone.utc)
        assert decode_cursor(encode_cursor(at, item_id)) == (at, item_id)

    def test_plus_decoded_as_space_is_tolerated(self):
        # 프론트가 인코딩을 빠뜨리면 "+00:00" 이 " 00:00" 으로 도착한다
        item_id = uuid.uuid4()
        at = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
        cursor = encode_cursor(at, item_id).replace("+", " ")
        assert decode_cursor(cursor) == (at, item_id)

    @pytest.mark.parametrize("cursor", ["", "garbage", "2026-09-26T10:00:00|not-uuid", f"nope|{uuid.uuid4()}"])
    def test_malformed_raises(self, cursor):
        with pytest.raises(InvalidCursor):
            decode_cursor(cursor)


class TestSchemas:
    def test_research_needs_ref_id(self):
        with pytest.raises(ValidationError):
            HistoryItemIn(kind="research", title="독서 격차 연구")

    @pytest.mark.parametrize("title", ["", "   ", "가" * 501])
    def test_title_bounds(self, title):
        with pytest.raises(ValidationError):
            HistoryItemIn(kind="book", title=title)

    def test_unknown_kind_is_rejected(self):
        with pytest.raises(ValidationError):
            HistoryItemIn(kind="chat", title="대화")

    @pytest.mark.parametrize("field", ["title", "params"])
    def test_patch_cannot_null_required_columns(self, field):
        with pytest.raises(ValidationError):
            HistoryItemPatch(**{field: None})

    def test_import_naive_time_is_utc(self):
        item = HistoryImportItem(kind="book", title="독서", created_at="2026-09-01T09:00:00")
        assert item.created_at == T0


class TestUpsert:
    def test_creates_item(self, engine):
        item_id = uuid.uuid4()
        out = _put(engine, SID_A, item_id, params={"grade": "KCI"}, snapshot={"books": [1]})
        assert out.id == item_id and out.title == "독서 격차"
        assert out.params == {"grade": "KCI"} and out.snapshot == {"books": [1]}
        assert out.has_snapshot and not out.has_ai and out.research is None
        assert raw_row(engine, item_id).user_id is None

    def test_repeating_same_id_keeps_one_row(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        _put(engine, SID_A, item_id, title="독서 격차 해소")
        items, _ = _list(engine, SID_A)
        assert [(i.id, i.title) for i in items] == [(item_id, "독서 격차 해소")]

    def test_other_browser_cannot_overwrite(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, title="원래 제목")
        assert _put(engine, SID_B, item_id, title="덮어쓰기") is None
        row = raw_row(engine, item_id)
        assert row.title == "원래 제목" and row.session_id == SID_A

    def test_omitted_heavy_fields_keep_previous_values(self, engine):
        # 중복 병합·재전송이 결과·AI 요약 없이 다시 보내도 이미 받은 것은 남는다
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, snapshot={"books": [1]}, ai={"intro": "요약", "items": []})
        out = _put(engine, SID_A, item_id)
        assert out.snapshot == {"books": [1]} and out.ai == {"intro": "요약", "items": []}

    def test_repeat_moves_item_to_top(self, engine):
        old, newer = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(timezone.utc)
        _import(engine, SID_A,
                {"id": old, "kind": "book", "title": "예전", "created_at": now - timedelta(hours=2)},
                {"id": newer, "kind": "book", "title": "최근", "created_at": now - timedelta(hours=1)})
        _put(engine, SID_A, old, title="예전")
        items, _ = _list(engine, SID_A)
        assert [i.id for i in items] == [old, newer]

    def test_revives_deleted_item(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        _call(engine, lambda r: r.soft_delete(SID_A, item_id))
        assert _put(engine, SID_A, item_id) is not None
        assert raw_row(engine, item_id).deleted_at is None


class TestGet:
    def test_own_item(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, ai={"intro": "요약", "items": []})
        out = _call(engine, lambda r: r.get(SID_A, item_id))
        assert out.ai == {"intro": "요약", "items": []} and out.has_ai

    def test_other_browser_sees_nothing(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        assert _call(engine, lambda r: r.get(SID_B, item_id)) is None

    def test_deleted_is_hidden(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        _call(engine, lambda r: r.soft_delete(SID_A, item_id))
        assert _call(engine, lambda r: r.get(SID_A, item_id)) is None


class TestList:
    def test_newest_first_own_live_items_only(self, engine):
        a, b, c, d = (uuid.uuid4() for _ in range(4))
        _import(engine, SID_A,
                {"id": a, "kind": "book", "title": "가", "created_at": _at(1)},
                {"id": b, "kind": "paper", "title": "나", "created_at": _at(2)},
                {"id": c, "kind": "book", "title": "다", "created_at": _at(3)})
        _import(engine, SID_B, {"id": d, "kind": "book", "title": "남의 것", "created_at": _at(4)})
        _call(engine, lambda r: r.soft_delete(SID_A, c))
        items, cursor = _list(engine, SID_A)
        assert [i.id for i in items] == [b, a] and cursor is None

    def test_kind_filter(self, engine):
        a, b = uuid.uuid4(), uuid.uuid4()
        _import(engine, SID_A,
                {"id": a, "kind": "book", "title": "가", "created_at": _at(1)},
                {"id": b, "kind": "paper", "title": "나", "created_at": _at(2)})
        items, _ = _list(engine, SID_A, kind="book")
        assert [i.id for i in items] == [a]

    def test_list_does_not_carry_heavy_fields(self, engine):
        _put(engine, SID_A, uuid.uuid4(), snapshot={"books": [1]})
        (item,), _ = _list(engine, SID_A)
        assert item.has_snapshot and not item.has_ai
        assert "snapshot" not in item.model_dump()

    def test_pages_do_not_skip_or_repeat(self, engine):
        ids = [uuid.uuid4() for _ in range(5)]
        # 같은 시각 두 행이 쪽 경계에 걸려도 빠지거나 겹치지 않아야 한다. limit=2 면 첫 쪽이
        # [t4, t3 중 id 가 큰 쪽] 으로 끝나 나머지 t3 이 다음 쪽으로 넘어간다
        times = [_at(1), _at(2), _at(3), _at(3), _at(4)]
        _import(engine, SID_A, *[
            {"id": i, "kind": "book", "title": f"검색 {n}", "created_at": t}
            for n, (i, t) in enumerate(zip(ids, times))
        ])
        seen, cursor = [], None
        for _ in range(3):
            items, cursor = _list(engine, SID_A, limit=2, before=cursor)
            seen += [i.id for i in items]
            if cursor is None:
                break
        expected = [i for _, i in sorted(zip(times, ids), reverse=True)]
        assert seen == expected
        assert cursor is None

    def test_malformed_cursor_raises(self, engine):
        with pytest.raises(InvalidCursor):
            _list(engine, SID_A, before="garbage")


class TestResearchStatus:
    def test_status_comes_from_research_jobs(self, engine):
        job_id = add_research_job(engine, status="running", stage="planned")
        _put(engine, SID_A, job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
        (item,), _ = _list(engine, SID_A)
        assert item.research.model_dump() == {"status": "running", "stage": "planned"}
        detail = _call(engine, lambda r: r.get(SID_A, job_id))
        assert detail.research.status == "running"

    def test_missing_job_gives_none(self, engine):
        job_id = uuid.uuid4()
        _put(engine, SID_A, job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
        (item,), _ = _list(engine, SID_A)
        assert item.research is None

    def test_malformed_ref_id_does_not_break_the_list(self, engine):
        _put(engine, SID_A, uuid.uuid4(), kind="research", title="독서 격차 연구", ref_id="not-a-uuid")
        (item,), _ = _list(engine, SID_A)
        assert item.research is None

    def test_other_kinds_have_no_research(self, engine):
        job_id = add_research_job(engine, status="completed", stage="synthesized")
        _put(engine, SID_A, uuid.uuid4(), kind="book", ref_id=str(job_id))
        (item,), _ = _list(engine, SID_A)
        assert item.research is None


class TestPatch:
    def test_updates_only_given_fields(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, params={"grade": "KCI"}, snapshot={"books": [1]})
        out = _call(engine, lambda r: r.patch(SID_A, item_id, HistoryItemPatch(ai={"text": "요약", "refs": []})))
        assert out.ai == {"text": "요약", "refs": []}
        assert out.params == {"grade": "KCI"} and out.snapshot == {"books": [1]}

    def test_explicit_null_clears_snapshot(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, snapshot={"books": [1]})
        out = _call(engine, lambda r: r.patch(SID_A, item_id, HistoryItemPatch(snapshot=None)))
        assert out.snapshot is None and not out.has_snapshot

    def test_other_browser_or_deleted_gives_none(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        patch = HistoryItemPatch(title="바꿈")
        assert _call(engine, lambda r: r.patch(SID_B, item_id, patch)) is None
        _call(engine, lambda r: r.soft_delete(SID_A, item_id))
        assert _call(engine, lambda r: r.patch(SID_A, item_id, patch)) is None
        assert raw_row(engine, item_id).title == "독서 격차"


class TestSoftDelete:
    def test_row_remains_but_is_hidden(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        assert _call(engine, lambda r: r.soft_delete(SID_A, item_id)) is True
        assert raw_row(engine, item_id).deleted_at is not None
        assert _list(engine, SID_A) == ([], None)

    def test_repeat_is_true_and_keeps_first_time(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        _call(engine, lambda r: r.soft_delete(SID_A, item_id))
        # SQLite 의 now() 는 초 단위라 두 삭제가 같은 초에 끝나면 시각을 덮어써도 같아 보인다.
        # 첫 삭제 시각을 과거로 옮겨 두고 두 번째 삭제가 그것을 지키는지 본다
        with engine.begin() as conn:
            conn.execute(sa.update(HistoryItem.__table__)
                         .where(HistoryItem.__table__.c.id == item_id)
                         .values(deleted_at=T0))
        assert _call(engine, lambda r: r.soft_delete(SID_A, item_id)) is True
        assert raw_row(engine, item_id).deleted_at.replace(tzinfo=timezone.utc) == T0

    def test_other_browser_cannot_delete(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        assert _call(engine, lambda r: r.soft_delete(SID_B, item_id)) is False
        assert raw_row(engine, item_id).deleted_at is None

    def test_delete_kind_touches_only_that_kind_of_this_browser(self, engine):
        book, paper, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        _put(engine, SID_A, book, kind="book")
        _put(engine, SID_A, paper, kind="paper")
        _put(engine, SID_B, other, kind="book")
        assert _call(engine, lambda r: r.soft_delete_kind(SID_A, "book")) == 1
        assert [i.id for i in _list(engine, SID_A)[0]] == [paper]
        assert raw_row(engine, other).deleted_at is None


class TestImport:
    def test_legacy_items_get_deterministic_ids(self, engine):
        out = _import(engine, SID_A,
                      {"legacy_id": "1727000000000", "kind": "book", "title": "가", "created_at": _at(1)},
                      {"legacy_id": "1727000000001", "kind": "paper", "title": "나", "created_at": _at(2)})
        assert (out.imported, out.skipped) == (2, 0)
        assert out.id_map == {
            "1727000000000": str(legacy_history_id("1727000000000")),
            "1727000000001": str(legacy_history_id("1727000000001")),
        }
        items, _ = _list(engine, SID_A)
        # 옛 기록의 시각을 지켜 순서가 그대로다
        assert [i.title for i in items] == ["나", "가"]
        assert items[1].created_at.replace(tzinfo=timezone.utc) == _at(1)

    def test_future_created_at_is_capped_to_now(self, engine):
        # 목록은 created_at 내림차순이다. 시계가 앞선 브라우저나 조작한 요청의 미래 시각을 믿으면
        # 그 항목이 이후에 새로 저장한 기록보다 계속 위에 고정된다
        item_id = uuid.uuid4()
        _import(engine, SID_A, {"id": item_id, "kind": "book", "title": "미래",
                                "created_at": datetime.now(timezone.utc) + timedelta(days=365)})
        after = datetime.now(timezone.utc)
        row = raw_row(engine, item_id)
        assert row.created_at.replace(tzinfo=timezone.utc) <= after
        assert row.updated_at == row.created_at

    def test_second_import_skips_and_returns_same_map(self, engine):
        item = {"legacy_id": "1727000000000", "kind": "book", "title": "가"}
        first = _import(engine, SID_A, item)
        second = _import(engine, SID_A, item)
        assert (second.imported, second.skipped) == (0, 1)
        assert second.id_map == first.id_map
        assert len(_list(engine, SID_A)[0]) == 1

    def test_does_not_revive_deleted_items(self, engine):
        item = {"legacy_id": "1727000000000", "kind": "book", "title": "가"}
        _import(engine, SID_A, item)
        _call(engine, lambda r: r.soft_delete(SID_A, legacy_history_id("1727000000000")))
        assert _import(engine, SID_A, item).imported == 0
        assert _list(engine, SID_A) == ([], None)

    def test_does_not_touch_other_browsers_rows(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_B, item_id, title="남의 것")
        out = _import(engine, SID_A, {"id": item_id, "kind": "book", "title": "내 것"})
        assert (out.imported, out.skipped) == (0, 1)
        assert raw_row(engine, item_id).title == "남의 것"

    def test_duplicates_in_one_batch_count_as_skipped(self, engine):
        item = {"legacy_id": "1727000000000", "kind": "book", "title": "가"}
        out = _import(engine, SID_A, item, item)
        assert (out.imported, out.skipped) == (1, 1)

    def test_explicit_id_wins(self, engine):
        item_id = uuid.uuid4()
        out = _import(engine, SID_A, {"id": item_id, "legacy_id": "1727000000000", "kind": "book", "title": "가"})
        assert out.id_map == {"1727000000000": str(item_id)}

    def test_empty_import(self, engine):
        out = _import(engine, SID_A)
        assert (out.imported, out.skipped, out.id_map) == (0, 0, {})
