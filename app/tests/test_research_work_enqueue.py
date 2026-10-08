"""services/research_work/enqueue.py·progress.py 와 history_sqlite 의 06b 도우미.

SQLite 대역(history_sqlite)에서 실제 SQL 로 돈다. pg_advisory_xact_lock 은 SQLite 에서 빈 함수라, 세션이
보낸 문장을 Postgres 로 컴파일해 잠금 → 열린 생성 검사 → 넣기 순서와 잠금 키를 본다
(test_research_work_dispatch 와 같은 방식).
"""
import asyncio
import hashlib
import importlib
import sys
import uuid
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_proposal, add_reading, add_research_job, add_topic,
    add_work, make_engine,
)
from models.research import ResearchJob
from models.research_work import (
    PRIORITY_BACKGROUND, PRIORITY_USER, ResearchGeneration, ResearchProposal, ResearchReading,
    ResearchTopic, ResearchWork,
)
from services.research_work.enqueue import OPEN_SAME, enqueue_generation, lock_key, queued_event
from services.research_work.progress import refresh_progress, sections_filled

GEN = ResearchGeneration.__table__
WORK = ResearchWork.__table__
CARD = {"title": "노인의 우울과 가족 지지", "question": "가족 지지는 노인의 우울을 낮추는가?"}
PARA = {"id": "p1", "text": "가족 지지는 우울과 관련이 있다 [E1].", "state": "proposed"}


class _Recording(AsyncSessionOverSync):
    """보낸 문장을 Postgres 로 컴파일해 문장·인자를 순서대로 남기고 COMMIT·ROLLBACK 도 끼워 적는다."""

    def __init__(self, engine):
        super().__init__(engine, expire_on_commit=False)
        self.log: list[str] = []
        self.params: list[dict] = []

    def _note(self, stmt) -> None:
        compiled = stmt.compile(dialect=postgresql.dialect())
        self.log.append(str(compiled))
        self.params.append(dict(compiled.params))

    async def execute(self, stmt, params=None):
        self._note(stmt)
        return await super().execute(stmt, params)

    async def scalar(self, stmt, params=None):
        self._note(stmt)
        return await super().scalar(stmt, params)

    async def commit(self):
        self.log.append("COMMIT")
        self.params.append({})
        await super().commit()

    async def rollback(self):
        self.log.append("ROLLBACK")
        self.params.append({})
        await super().rollback()


@pytest.fixture
def engine():
    return make_engine()


def _work(engine, **fields) -> uuid.UUID:
    job_id = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, job_id, **fields)
    return job_id


def _call(engine, fn):
    """fn(db) 의 결과와 그 세션의 기록. fn 이 커밋하지 않은 쓰기는 세션을 닫을 때 사라진다."""
    async def _go():
        db = _Recording(engine)
        try:
            return await fn(db), db
        finally:
            await db.close()

    return asyncio.run(_go())


def _gens(engine, work_id) -> list:
    with engine.connect() as conn:
        return conn.execute(sa.select(GEN).where(GEN.c.work_id == work_id).order_by(GEN.c.id)).mappings().all()


def _stored_progress(engine, work_id) -> dict:
    with engine.connect() as conn:
        return conn.execute(sa.select(WORK.c.progress).where(WORK.c.id == work_id)).scalar_one()


def _enqueue_and_commit(work_id, **kw):
    async def _go(db):
        gid = await enqueue_generation(db, work_id, **kw)
        await db.commit()
        return gid
    return _go


# ── 잠금 키 ──────────────────────────────────────────────────────────


def _stub_missing(monkeypatch, name: str) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, MagicMock())


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules·부모 패키지 속성에서 빼고 테스트가 끝나면 되돌린다(test_research_work_api.py 와 같다)."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


class TestLockKey:
    def test_same_formula_as_the_06a_retry_key(self):
        jid = uuid.uuid4()
        raw = f"research_work_retry:{jid}:topic_card:12".encode()
        assert lock_key(jid, "topic_card", "12") == int.from_bytes(
            hashlib.sha256(raw).digest()[:8], "big", signed=True)
        assert -(2 ** 63) <= lock_key(jid, "topic_card", "12") < 2 ** 63
        assert lock_key(str(jid), "topic_card", "12") == lock_key(jid, "topic_card", "12")

    def test_key_differs_by_kind_and_target(self):
        jid = uuid.uuid4()
        keys = {lock_key(jid, "section", "prior.g1"), lock_key(jid, "section", "gap"),
                lock_key(jid, "paragraph", "prior.g1"), lock_key(uuid.uuid4(), "section", "prior.g1")}
        assert len(keys) == 4

    def test_api_retry_takes_this_key(self, monkeypatch):
        # '다시'(api/research_work)와 새 생성 넣기가 같은 키를 잡아야 같은 대상의 두 요청이 한 줄로 선다
        for name in ("redis", "redis.asyncio"):
            _stub_missing(monkeypatch, name)
        _forget_on_teardown(monkeypatch, ("api.research_work", "services.research.relay"))
        router = importlib.import_module("api.research_work")
        jid = uuid.uuid4()
        assert router._retry_lock_key(jid, "concepts", None) == lock_key(jid, "concepts", None)
        assert router._retry_lock_key(jid, "section", "gap") == lock_key(jid, "section", "gap")


# ── 생성 넣기 ────────────────────────────────────────────────────────


class TestEnqueue:
    def test_inserts_a_queued_row(self, engine):
        w = _work(engine)
        gid, _ = _call(engine, _enqueue_and_commit(w, kind="topic_card", target="12",
                                                   input={"topic_id": 12}))

        (row,) = _gens(engine, w)
        assert isinstance(gid, int) and row["id"] == gid
        assert (row["kind"], row["target"], row["priority"], row["status"], row["input"]) == (
            "topic_card", "12", PRIORITY_USER, "queued", {"topic_id": 12})

    def test_lock_then_check_then_insert_without_committing(self, engine):
        w = _work(engine)

        gid, db = _call(engine, lambda db: enqueue_generation(db, w, kind="section", target="gap",
                                                              input={}))

        lock = next(i for i, s in enumerate(db.log) if "pg_advisory_xact_lock" in s)
        check = next(i for i, s in enumerate(db.log)
                     if s.startswith("SELECT") and "research_generations.status IN" in s)
        insert = next(i for i, s in enumerate(db.log) if s.startswith("INSERT INTO research_generations"))
        assert lock < check < insert
        assert list(db.params[lock].values()) == [lock_key(w, "section", "gap")]
        assert "COMMIT" not in db.log                  # 커밋은 부르는 쪽 — 닫으면 사라진다
        assert isinstance(gid, int) and _gens(engine, w) == []

    @pytest.mark.parametrize("status", ["queued", "running"])
    def test_an_open_generation_of_the_same_target_gives_none(self, engine, status):
        w = _work(engine)
        add_generation(engine, w, kind="section", target="prior.g1", status=status)

        gid, db = _call(engine, _enqueue_and_commit(w, kind="section", target="prior.g1", input={}))

        assert gid is None
        assert not any(s.startswith("INSERT") for s in db.log)
        assert len(_gens(engine, w)) == 1

    def test_closed_generations_and_other_targets_do_not_block(self, engine):
        w = _work(engine)
        add_generation(engine, w, kind="section", target="prior.g1", status="done")
        add_generation(engine, w, kind="section", target="prior.g1", status="failed")
        add_generation(engine, w, kind="section", target="prior.g2", status="queued")
        add_generation(engine, w, kind="paragraph", target="prior.g1", status="queued")
        add_generation(engine, _work(engine), kind="section", target="prior.g1", status="queued")

        gid, _ = _call(engine, _enqueue_and_commit(w, kind="section", target="prior.g1", input={}))

        assert isinstance(gid, int)
        assert [r["status"] for r in _gens(engine, w)][-1] == "queued"

    def test_a_missing_target_matches_only_a_missing_target(self, engine):
        w = _work(engine)
        add_generation(engine, w, kind="concepts", status="queued")

        same, _ = _call(engine, _enqueue_and_commit(w, kind="concepts", target=None, input={}))
        other, _ = _call(engine, _enqueue_and_commit(w, kind="concepts", target="x", input={}))

        assert same is None and isinstance(other, int)

    def test_priority_is_kept(self, engine):
        w = _work(engine)
        _call(engine, _enqueue_and_commit(w, kind="facet", target="C1", input={},
                                          priority=PRIORITY_BACKGROUND))
        assert _gens(engine, w)[0]["priority"] == PRIORITY_BACKGROUND


class TestQueuedEvent:
    def test_shape_matches_the_generation_event(self):
        assert queued_event(41, "topic_card", "12") == {
            "gen_id": 41, "gen_kind": "topic_card", "target": "12", "status": "queued",
            "model": None, "result": None}

    def test_open_same_is_the_06a_retry_text(self):
        assert OPEN_SAME == "같은 생성이 이미 대기 중이거나 진행 중입니다"


# ── 진행 요약 ────────────────────────────────────────────────────────


def _outline(**over) -> dict:
    outline = {
        "topic": {"id": 12, "title": "노인의 우울과 가족 지지", "question": "?"},
        "basis": "concept",
        "groups": [{"key": "prior.g1", "name": "가족 지지", "hint": "", "papers": ["C1"]},
                   {"key": "prior.g2", "name": "지역사회", "hint": "", "papers": ["C2"]}],
        "questions": [], "question": "가족 지지는 노인의 우울을 낮추는가?", "method": "설문 조사",
        "state": "approved", "gen_id": 3, "approved_at": None,
    }
    return {**outline, **over}


def _section(*texts: str) -> dict:
    return {"paragraphs": [{**PARA, "id": f"p{i}", "text": t} for i, t in enumerate(texts, 1)]}


class TestSectionsFilled:
    def test_nothing_before_the_outline(self):
        assert sections_filled({}, {}) == 0

    def test_outline_values_and_written_sections(self):
        sections = {"prior.g1": _section("가"), "prior.g2": _section("나"), "gap": _section("다")}
        # 주제·선행연구(묶음 둘 다)·연구 공백·연구 질문·방법 — 연구 배경(06c)만 비었다
        assert sections_filled(_outline(), sections) == 5

    def test_background_counts_when_written(self):
        sections = {"prior.g1": _section("가"), "prior.g2": _section("나"), "gap": _section("다"),
                    "background": _section("라")}
        assert sections_filled(_outline(), sections) == 6

    def test_prior_needs_every_group(self):
        assert sections_filled(_outline(question=None, method=""), {"prior.g1": _section("가")}) == 1
        assert sections_filled(_outline(question=None, method="", groups=[]),
                               {"prior.g1": _section("가")}) == 1

    def test_blank_text_does_not_count(self):
        sections = {"prior.g1": _section("  "), "prior.g2": _section("나"), "gap": {"paragraphs": []}}
        assert sections_filled(_outline(question="  ", method=None), sections) == 1


class TestRefreshProgress:
    def test_counts_and_stores_without_committing(self, engine):
        w = _work(engine)
        add_topic(engine, w, slot=1, card=CARD)
        add_topic(engine, w, slot=2)                                  # 카드 만드는 중
        add_topic(engine, w, slot=3, state="insufficient")
        add_topic(engine, w, origin="user", card=CARD, state="picked")
        add_topic(engine, w, origin="other", card=CARD, state="folded")
        for cnts, state in (("C1", "in"), ("C2", "in"), ("C3", "candidate"), ("C4", "out")):
            add_reading(engine, w, cnts, state=state)
        add_proposal(engine, w, outline=_outline(), sections={"prior.g1": _section("가"),
                                                              "prior.g2": _section("나")})
        other = _work(engine)
        add_topic(engine, other, slot=1, card=CARD)
        add_reading(engine, other, "C9", state="in")

        progress, db = _call(engine, lambda db: refresh_progress(db, w))

        assert progress == {"topics": 2, "reading": 2, "sections": 4, "sections_total": 6}
        assert any(s.startswith("UPDATE research_works") for s in db.log) and "COMMIT" not in db.log
        # 연구 행을 먼저 잠그고 센다 — 겹친 쓰기에서 뒤에 커밋하는 쪽이 앞 커밋 전에 센 값을 쓰지 않게
        lock = next(i for i, s in enumerate(db.log) if "FOR UPDATE" in s)
        counts = [i for i, s in enumerate(db.log) if s.startswith("SELECT") and i != lock]
        write = next(i for i, s in enumerate(db.log) if s.startswith("UPDATE research_works"))
        assert db.log[lock].startswith("SELECT research_works.id") and lock < min(counts) <= max(counts) < write
        assert _stored_progress(engine, w) == {}                      # 닫으면서 되돌렸다

        async def _commit(db):
            result = await refresh_progress(db, w)
            await db.commit()
            return result

        _call(engine, _commit)
        assert _stored_progress(engine, w) == progress
        assert _stored_progress(engine, other) == {}

    def test_no_proposal_yet(self, engine):
        w = _work(engine)

        progress, _ = _call(engine, lambda db: refresh_progress(db, w))

        assert progress == {"topics": 0, "reading": 0, "sections": 0, "sections_total": 6}


# ── 테스트 DB 도우미(history_sqlite) ────────────────────────────────────


class TestHarness:
    def test_topic_and_proposal_tables_exist(self, engine):
        assert {"research_topics", "research_proposals", "research_reading"} <= set(
            sa.inspect(engine).get_table_names())

    def test_add_topic_fills_the_jsonb_columns(self, engine):
        w = _work(engine)
        tid = add_topic(engine, w)
        with engine.connect() as conn:
            row = conn.execute(sa.select(ResearchTopic.__table__)).mappings().one()
        assert isinstance(tid, int) and row["id"] == tid
        assert (row["slot"], row["origin"], row["seed"], row["card"], row["state"]) == (
            None, "report_seed", {}, {}, "candidate")

    def test_slot_is_unique_within_a_work(self, engine):
        w = _work(engine)
        add_topic(engine, w, slot=1)
        add_topic(engine, w)
        add_topic(engine, w)                                          # 자리 없는 카드는 몇 장이든
        add_topic(engine, _work(engine), slot=1)
        with pytest.raises(sa.exc.IntegrityError):
            add_topic(engine, w, slot=1)

    def test_add_proposal_and_reading(self, engine):
        w = _work(engine)
        add_proposal(engine, w, version=3, outline={"state": "draft"})
        add_reading(engine, w, "C1", state="in", origin="user", position=2, note="메모",
                    group_label="가족")
        with engine.connect() as conn:
            prop = conn.execute(sa.select(ResearchProposal.__table__)).mappings().one()
            reading = conn.execute(sa.select(ResearchReading.__table__)).mappings().one()
        assert (prop["version"], prop["outline"], prop["sections"]) == (3, {"state": "draft"}, {})
        assert (reading["cnts_id"], reading["state"], reading["origin"], reading["origin_ref"],
                reading["position"], reading["note"], reading["group_label"]) == (
            "C1", "in", "user", {}, 2, "메모", "가족")
        with pytest.raises(sa.exc.IntegrityError):
            add_proposal(engine, w)                                   # 연구마다 한 행

    def test_add_generation_takes_target_and_output(self, engine):
        w = _work(engine)
        gid = add_generation(engine, w, kind="section", status="done", target="prior.g1",
                             output={"paragraphs": [], "dropped": 0})
        (row,) = _gens(engine, w)
        assert (row["id"], row["target"], row["output"]) == (
            gid, "prior.g1", {"paragraphs": [], "dropped": 0})

    def test_deleting_the_job_removes_topics_reading_and_proposal(self, engine):
        w = _work(engine)
        add_topic(engine, w, slot=1)
        add_reading(engine, w, "C1")
        add_proposal(engine, w)
        with engine.begin() as conn:
            conn.execute(sa.delete(ResearchJob.__table__).where(ResearchJob.__table__.c.id == w))
        with engine.connect() as conn:
            left = [conn.execute(sa.select(sa.func.count()).select_from(t)).scalar_one()
                    for t in (ResearchTopic.__table__, ResearchReading.__table__,
                              ResearchProposal.__table__)]
        assert left == [0, 0, 0]
