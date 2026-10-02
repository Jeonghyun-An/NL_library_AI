"""services/research_work/dispatch.py·apply.py — 생성 디스패처(전체에서 한 번에 1건)와 결과 적용.

SQLite 대역(history_sqlite)에서 실제 SQL 로 돈다. 잠금(pg_advisory_xact_lock·FOR UPDATE SKIP LOCKED)은
SQLite 가 그리지 않으므로, 세션이 보낸 문장을 Postgres 로 컴파일해 순서와 모양을 본다(spec §6-3).
"""
import asyncio
import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.research_work import ResearchGeneration, ResearchWork
from services.research_work.apply import apply_result
from services.research_work.dispatch import (
    GEN_LOCK, finish, has_queued, pick_next, queue_position,
)

GEN = ResearchGeneration.__table__
WORK = ResearchWork.__table__
T0 = dt.datetime(2026, 10, 2, 9, 0, 0)


class _Recording(AsyncSessionOverSync):
    """보낸 문장을 Postgres 로 컴파일해 순서대로 남기고 COMMIT·ROLLBACK 도 끼워 적는다.
    워커의 세션처럼(expire_on_commit=False) 커밋 뒤에도 읽은 값을 들고 있다."""

    def __init__(self, engine):
        super().__init__(engine, expire_on_commit=False)
        self.log: list[str] = []

    async def execute(self, stmt, params=None):
        self.log.append(str(stmt.compile(dialect=postgresql.dialect())))
        return await super().execute(stmt, params)

    async def scalar(self, stmt, params=None):
        self.log.append(str(stmt.compile(dialect=postgresql.dialect())))
        return await super().scalar(stmt, params)

    async def commit(self):
        self.log.append("COMMIT")
        await super().commit()

    async def rollback(self):
        self.log.append("ROLLBACK")
        await super().rollback()


@pytest.fixture
def engine():
    return make_engine()


def _work(engine, **fields):
    job_id = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, job_id, **fields)
    return job_id


def _gen(engine, work_id, *, minute: int, **fields) -> int:
    """created_at 을 T0 + minute 분으로 박은 생성 — 같은 초에 넣은 행끼리의 순서를 정해 둔다."""
    gid = add_generation(engine, work_id, **fields)
    with engine.begin() as conn:
        conn.execute(sa.update(GEN).where(GEN.c.id == gid)
                     .values(created_at=T0 + dt.timedelta(minutes=minute)))
    return gid


def _row(engine, gid: int):
    with engine.connect() as conn:
        return conn.execute(sa.select(GEN).where(GEN.c.id == gid)).mappings().one()


def _work_row(engine, work_id):
    with engine.connect() as conn:
        return conn.execute(sa.select(WORK).where(WORK.c.id == work_id)).mappings().one()


def _call(engine, fn):
    async def _go():
        db = _Recording(engine)
        try:
            return await fn(db), db.log
        finally:
            await db.close()

    return asyncio.run(_go())


class TestLockKey:
    def test_lock_key_fits_a_signed_bigint(self):
        assert GEN_LOCK == int.from_bytes(b"RSWKDISP", "big")
        assert -(2 ** 63) <= GEN_LOCK < 2 ** 63

    def test_lock_key_differs_from_the_research_run_slot_lock(self):
        # api/research.py _RUN_SLOT_LOCK — 같으면 딥리서치 승인과 생성 디스패치가 서로를 기다린다
        assert GEN_LOCK != 0x5245534541524348


class TestPickNext:
    def test_user_generations_first_then_oldest_across_works(self, engine):
        w1, w2 = _work(engine), _work(engine)
        background = _gen(engine, w1, minute=0, priority=0)
        later = _gen(engine, w2, minute=2, priority=10)
        earlier = _gen(engine, w1, minute=1, priority=10)

        gen, _ = _call(engine, pick_next)

        assert gen.id == earlier
        assert (gen.status, gen.work_id) == ("running", w1) and gen.started_at is not None
        assert _row(engine, earlier)["status"] == "running"
        assert [_row(engine, g)["status"] for g in (background, later)] == ["queued", "queued"]

    def test_same_priority_and_time_go_by_id(self, engine):
        w1 = _work(engine)
        first = _gen(engine, w1, minute=0)
        _gen(engine, w1, minute=0)

        gen, _ = _call(engine, pick_next)

        assert gen.id == first

    def test_returns_the_row_with_its_input(self, engine):
        w1 = _work(engine)
        _gen(engine, w1, minute=0, kind="concepts", input={"question": "독서 격차"})

        gen, _ = _call(engine, pick_next)

        assert (gen.kind, gen.input, gen.target) == ("concepts", {"question": "독서 격차"}, None)

    def test_nothing_is_picked_while_any_generation_runs(self, engine):
        w1, w2 = _work(engine), _work(engine)
        _gen(engine, w1, minute=0, status="running", started_at=T0)
        waiting = _gen(engine, w2, minute=1)

        gen, log = _call(engine, pick_next)

        assert gen is None
        assert _row(engine, waiting)["status"] == "queued"
        assert log[-1] == "ROLLBACK" and not any(s.startswith("UPDATE") for s in log)

    def test_nothing_queued_gives_none(self, engine):
        w1 = _work(engine)
        _gen(engine, w1, minute=0, status="done")

        gen, log = _call(engine, pick_next)

        assert gen is None and log[-1] == "ROLLBACK"

    def test_lock_count_and_locked_pick_share_one_transaction(self, engine):
        w1 = _work(engine)
        _gen(engine, w1, minute=0)

        _, log = _call(engine, pick_next)

        lock = next(i for i, s in enumerate(log) if "pg_advisory_xact_lock" in s)
        count = next(i for i, s in enumerate(log) if s.startswith("SELECT count(*)"))
        pick = next(i for i, s in enumerate(log) if "FOR UPDATE SKIP LOCKED" in s)
        upd = next(i for i, s in enumerate(log) if s.startswith("UPDATE research_generations"))
        commit = log.index("COMMIT")
        assert lock < count < pick < upd < commit
        assert not {"COMMIT", "ROLLBACK"} & set(log[lock:upd])
        assert "ORDER BY research_generations.priority DESC, research_generations.created_at, " \
               "research_generations.id" in log[pick]
        assert "LIMIT" in log[pick]


class TestFinish:
    def test_closes_a_running_generation(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0, status="running", started_at=T0)
        output = {"concepts": ["독서 격차", "청소년"], "attempts": [{"model": "qwen-test", "outcome": "ok"}]}

        ok, log = _call(engine, lambda db: finish(db, gid, status="done", output=output,
                                                  model="qwen-test", error=None))

        row = _row(engine, gid)
        assert ok is True and log[-1] == "COMMIT"
        assert (row["status"], row["output"], row["model"], row["error"]) == (
            "done", output, "qwen-test", None)
        assert row["finished_at"] is not None

    def test_failed_keeps_the_error(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0, status="running", started_at=T0)

        ok, _ = _call(engine, lambda db: finish(db, gid, status="failed", output=None, model=None,
                                                error="ValueError: 코드 결함"))

        row = _row(engine, gid)
        assert ok is True
        assert (row["status"], row["output"], row["error"]) == ("failed", None, "ValueError: 코드 결함")

    def test_canceled_generation_is_left_alone(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0, status="canceled", started_at=T0)

        ok, log = _call(engine, lambda db: finish(db, gid, status="done", output={"concepts": []},
                                                  model="qwen-test", error=None))

        row = _row(engine, gid)
        assert ok is False and log[-1] == "ROLLBACK"
        assert (row["status"], row["output"], row["finished_at"]) == ("canceled", None, None)

    def test_a_dropped_finish_undoes_the_applied_result(self, engine):
        """도는 중에 취소된 생성의 결과는 연구에 남지 않는다 — 적용과 닫기가 한 트랜잭션이다."""
        w1 = _work(engine, concepts=["사용자 개념"])
        gid = _gen(engine, w1, minute=0, kind="concepts", status="canceled", started_at=T0)

        async def _apply_then_finish(db):
            gen = await db.get(ResearchGeneration, gid)
            await apply_result(db, gen, {"concepts": ["모델 개념", "다른 개념"]})
            return await finish(db, gid, status="done", output={"concepts": []}, model="m", error=None)

        ok, _ = _call(engine, _apply_then_finish)

        assert ok is False
        assert _work_row(engine, w1)["concepts"] == ["사용자 개념"]

    @pytest.mark.parametrize("status", ["queued", "running", "canceled"])
    def test_only_done_or_failed(self, engine, status):
        with pytest.raises(ValueError):
            _call(engine, lambda db: finish(db, 1, status=status, output=None, model=None, error=None))


class TestQueueState:
    def test_has_queued(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0, status="running", started_at=T0)
        assert _call(engine, has_queued)[0] is False
        _gen(engine, w1, minute=1)
        assert _call(engine, has_queued)[0] is True
        assert _row(engine, gid)["status"] == "running"

    def test_position_counts_queued_ahead_and_the_running_one(self, engine):
        w1, w2 = _work(engine), _work(engine)
        _gen(engine, w1, minute=0, status="running", started_at=T0)
        user_old = _gen(engine, w2, minute=1, priority=10)
        background = _gen(engine, w1, minute=0, priority=0)
        user_new = _gen(engine, w2, minute=2, priority=10)

        async def _positions(db):
            return [await queue_position(db, await db.get(ResearchGeneration, g))
                    for g in (user_old, user_new, background)]

        positions, _ = _call(engine, _positions)

        assert positions == [1, 2, 3]

    def test_position_without_a_running_generation(self, engine):
        w1 = _work(engine)
        gid = _gen(engine, w1, minute=0)

        async def _position(db):
            return await queue_position(db, await db.get(ResearchGeneration, gid))

        assert _call(engine, _position)[0] == 0

    def test_running_and_closed_generations_wait_for_nobody(self, engine):
        w1 = _work(engine)
        running = _gen(engine, w1, minute=0, status="running", started_at=T0)
        done = _gen(engine, w1, minute=1, status="done")
        _gen(engine, w1, minute=2)

        async def _positions(db):
            return [await queue_position(db, await db.get(ResearchGeneration, g)) for g in (running, done)]

        assert _call(engine, _positions)[0] == [0, 0]


class TestApplyResult:
    def test_concepts_replace_the_chips_and_reset_membership(self, engine):
        w1 = _work(engine, concepts=["옛 개념"])
        with engine.begin() as conn:
            conn.execute(sa.update(WORK).where(WORK.c.id == w1)
                         .values(concept_members={"옛 개념": ["C1"]}))
        gid = _gen(engine, w1, minute=0, kind="concepts", status="running", started_at=T0)

        async def _apply(db):
            gen = await db.get(ResearchGeneration, gid)
            payload = await apply_result(db, gen, {"concepts": ["독서 격차", "청소년"]})
            await db.commit()
            return payload

        payload, log = _call(engine, _apply)

        row = _work_row(engine, w1)
        assert payload == {"concepts": ["독서 격차", "청소년"]}
        assert (row["concepts"], row["concept_members"]) == (["독서 격차", "청소년"], {})
        assert log.count("COMMIT") == 1          # 적용은 커밋하지 않는다 — 위 커밋은 테스트가 했다

    def test_an_empty_result_keeps_the_chips(self, engine):
        """세 번 다 못 얻은 빈 결과는 사용자가 넣어 둔 칩·소속을 지우지 않는다(빈 결과를 다시 부른 경우)."""
        w1 = _work(engine, concepts=["사용자 개념"])
        with engine.begin() as conn:
            conn.execute(sa.update(WORK).where(WORK.c.id == w1)
                         .values(concept_members={"사용자 개념": ["C1"]}))
        gid = _gen(engine, w1, minute=0, kind="concepts", status="running", started_at=T0)

        async def _apply(db):
            return await apply_result(db, await db.get(ResearchGeneration, gid), {"concepts": []})

        payload, log = _call(engine, _apply)

        row = _work_row(engine, w1)
        assert payload == {"concepts": []} and log == []
        assert (row["concepts"], row["concept_members"]) == (["사용자 개념"], {"사용자 개념": ["C1"]})

    def test_kinds_without_an_06a_effect_change_nothing(self, engine):
        w1 = _work(engine, concepts=["독서 격차"])
        gid = _gen(engine, w1, minute=0, kind="outline", status="running", started_at=T0)

        async def _apply(db):
            return await apply_result(db, await db.get(ResearchGeneration, gid), {"outline": {}})

        payload, log = _call(engine, _apply)

        assert payload == {} and log == []
        assert _work_row(engine, w1)["concepts"] == ["독서 격차"]
