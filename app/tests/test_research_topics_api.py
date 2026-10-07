"""test_research_topics_api.py — 주제 단계 API(api/research_topics.py)와 응답 모양(topic_views.py).

test_research_work_api.py 의 api 픽스처를 그대로 옮긴다 — 요청은 TestClient 로 실제 라우팅을 거치고, DB 는
history_sqlite 의 SQLite 다(요청이 끝나면 되돌리므로 핸들러가 직접 커밋한 쓰기만 남는다). redis 는 미설치일 때만
더미를 꽂고, 연구 채널(publish_work)은 기록용 가짜다. 디스패치를 보내는 워커 모듈은 sys.modules 에 가짜를
꽂는다. 이어가기부터 끝까지 한 번 돌리는 TestEndToEnd 를 위해 06a 라우터(research_work)도 함께 붙인다.
"""
import asyncio
import ast
import importlib
import json
import sys
import types
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_topic, add_work, make_engine,
)
from models.research import ResearchJob
from models.research_work import ResearchGeneration, ResearchTopic, ResearchWork
from services.research_work.enqueue import lock_key
from services.research_work.markers import numbers_outside, soften_claims
from services.research_work.seeds import pick_seeds, topic_input
from services.research_work.topic_views import paper_meta, topic_item, topics_view

A = {"x-session-id": "3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e"}
QUESTION = "노인의 우울과 사회적 지지에 관한 연구가 궁금해"


def _ev(cnts_id: str, title: str, pub_date: str) -> dict:
    return {"cnts_id": cnts_id, "chunks": [],
            "meta": {"title": title, "personal_author": "김철수", "pub_date": pub_date,
                     "series_title": "노인복지연구"}}


def _section(heading: str, pairs: tuple, futures: list[dict]) -> dict:
    return {"heading": heading, "intro": "", "future": futures,
            "papers": [{"cnts_id": c, "summary": "", "evidence": [e]} for c, e in pairs]}


# 씨앗 다섯 — 이어가기가 앞 4장(future:0:0·1:0·2:0·0:1)을 쓰고 insufficient:1 이 남는다
REPORT = {
    "question": QUESTION,
    "range": {"from": "1980", "to": "2017", "n_papers": 144748},
    "sections": [
        _section("노인의 사회적 지지와 우울", (("P1", "E1"), ("P2", "E2"), ("P3", "E3")),
                 [{"text": "독거노인의 지지망을 따로 볼 필요가 있다 [E2]", "evidence": ["E2"]},
                  {"text": "종단 자료로 인과를 확인해야 한다 [E1]", "evidence": ["E1"]}]),
        _section("농촌 노인의 우울 위험 요인", (("P4", "E4"), ("P5", "E5")),
                 [{"text": "농촌 노인의 우울 선별 도구를 검증할 필요가 있다 [E4]", "evidence": ["E4"]}]),
        _section("노인 우울 중재 프로그램", (("P6", "E6"), ("P1", "E1")),
                 [{"text": "중재 효과의 지속 기간을 확인해야 한다 [E6]", "evidence": ["E6"]}]),
    ],
    "evidence": {f"E{n}": _ev(f"P{n}", f"노인 우울 논문 {n}", f"20{10 + n}") for n in range(1, 7)},
    "trail": [
        {"subquestion": "노인의 사회적 지지와 우울", "evidence_count": 12, "verdict": "sufficient", "note": ""},
        {"subquestion": "농촌 노인의 우울 위험 요인", "evidence_count": 7, "verdict": "insufficient",
         "note": "농촌 표본 연구가 적다"},
        {"subquestion": "노인 우울 중재 프로그램", "evidence_count": 5, "verdict": "sufficient", "note": ""},
    ],
}
SEEDS = pick_seeds(REPORT, limit=None)            # future:0:0 · 1:0 · 2:0 · 0:1 · insufficient:1
CORPUS = {"n_papers": 144748, "from": "1980", "to": "2017", "at": "2026-10-06T09:30:00"}
CARD = {"title": "독거노인의 지지망 유형과 우울", "question": "지지망 유형에 따라 우울이 다른가?",
        "evidence": ["P2", "P1"], "figure_sentence": None, "figures": [], "latest_year": 2012, "edited": False,
        "checks": {"numbers": [], "softened": 0, "recovered": 0}, "gen_id": 1}


def _stub_missing(monkeypatch, name: str, module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module)


_CACHED = ("api.research_topics", "api.research_work", "services.research.relay")


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다
    (test_research_work_api.py 와 같은 방식 — 더미 redis 에 묶인 relay 가 다른 테스트로 새지 않게)."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


class _Dispatch:
    """workers.research_work_tasks.send_dispatch 가짜 — 보낸 횟수를 센다."""
    def __init__(self):
        self.calls = 0

    def send_dispatch(self) -> bool:
        self.calls += 1
        return True


class _Api:
    def __init__(self, client, engine, router, events, dispatch):
        self.client = client
        self.engine = engine
        self.router = router
        self.events = events
        self.dispatch = dispatch


@pytest.fixture
def api(monkeypatch):
    for name in ("redis", "redis.asyncio"):
        _stub_missing(monkeypatch, name, MagicMock())
    _forget_on_teardown(monkeypatch, _CACHED)
    router = importlib.import_module("api.research_topics")
    work_router = importlib.import_module("api.research_work")
    from core.deps import get_db

    events: list[tuple] = []

    async def _publish_work(work_id, kind, payload):
        events.append((str(work_id), kind, payload))

    monkeypatch.setattr(router, "publish_work", _publish_work)
    monkeypatch.setattr(work_router, "publish_work", _publish_work)

    async def _queue_info(db, gen):
        return {"position": 1, "eta_sec": None, "others_ahead": False}

    monkeypatch.setattr(work_router, "queue_info", _queue_info)

    dispatch = _Dispatch()
    worker = types.ModuleType("workers.research_work_tasks")
    worker.send_dispatch = dispatch.send_dispatch
    monkeypatch.setitem(sys.modules, "workers.research_work_tasks", worker)

    engine = make_engine()

    async def _db():
        db = AsyncSessionOverSync(engine)
        try:
            yield db
        finally:
            # 성공해도 되돌린다 — 핸들러가 직접 커밋한 쓰기만 남아야 한다
            await db.rollback()
            await db.close()

    app = FastAPI()
    app.include_router(work_router.router)
    app.include_router(router.router)
    app.dependency_overrides[get_db] = _db
    return _Api(TestClient(app), engine, router, events, dispatch)


# ── 데이터 도우미 ─────────────────────────────────────────────────────


def _job(engine, *, report: dict | None = REPORT) -> uuid.UUID:
    jid = add_research_job(engine, status="completed", stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == jid).values(
            question=QUESTION, report=report, plan=[t["subquestion"] for t in REPORT["trail"]],
            finished_at=datetime(2026, 10, 6, 9, 30),
        ))
    return jid


def _work_job(engine, *, report: dict | None = REPORT, **work) -> uuid.UUID:
    jid = _job(engine, report=report)
    add_work(engine, jid, **work)
    return jid


def _rows(engine, model, **where) -> list:
    table = model.__table__
    stmt = sa.select(table)
    for col, value in where.items():
        stmt = stmt.where(table.c[col] == value)
    with engine.connect() as conn:
        return conn.execute(stmt.order_by(*table.primary_key.columns)).mappings().all()


def _set(engine, model, key, **values) -> None:
    table = model.__table__
    pk = list(table.primary_key.columns)[0]
    with engine.begin() as conn:
        conn.execute(sa.update(table).where(pk == key).values(**values))


def _topic(engine, tid: int):
    (row,) = _rows(engine, ResearchTopic, id=tid)
    return row


# ── 응답 모양(순수 함수) ──────────────────────────────────────────────


def _row(**fields) -> SimpleNamespace:
    base = {"id": 1, "slot": None, "origin": "report_seed", "state": "candidate", "parent_id": None,
            "seed": {}, "card": {}, "created_at": datetime(2026, 10, 6, 10, 0)}
    return SimpleNamespace(**{**base, **fields})


def _gen(id: int, target: str, status: str = "done", kind: str = "topic_card") -> SimpleNamespace:
    return SimpleNamespace(id=id, kind=kind, target=target, status=status)


class TestTopicViews:
    def test_paper_meta(self):
        assert paper_meta(REPORT["evidence"]["E1"]["meta"]) == {
            "title": "노인 우울 논문 1", "personal_author": "김철수", "pub_date": "2011",
            "series_title": "노인복지연구"}
        assert paper_meta({}) == {"title": "", "personal_author": None, "pub_date": None, "series_title": None}

    def test_topic_item(self):
        row = _row(id=5, slot=2, seed=SEEDS[1], card=CARD)
        assert topic_item(row, _gen(9, "5", "running")) == {
            "id": 5, "slot": 2, "origin": "report_seed", "state": "candidate", "parent_id": None,
            "seed": SEEDS[1], "card": CARD, "generation": {"id": 9, "status": "running"},
            "created_at": "2026-10-06T10:00:00"}
        user = topic_item(_row(id=6, origin="user", seed={}, card={}), None)
        assert (user["seed"], user["card"], user["generation"]) == (None, None, None)

    def test_view_orders_slots_first_and_takes_each_topics_latest_generation(self):
        work = SimpleNamespace(topic_id=4, corpus_snapshot=CORPUS)
        job = SimpleNamespace(report=REPORT, finished_at=None)
        rows = [_row(id=7, origin="user", card={**CARD, "evidence": ["X9"]}),
                _row(id=4, slot=2, seed=SEEDS[1], state="picked", card=CARD),
                _row(id=3, slot=1, seed=SEEDS[0])]
        gens = [_gen(10, "3", "failed"), _gen(11, "3", "queued"), _gen(12, "4"), _gen(13, None, kind="concepts")]

        view = topics_view(work, job, rows, gens)

        assert [i["id"] for i in view["items"]] == [3, 4, 7]
        assert [i["generation"] for i in view["items"]] == [{"id": 11, "status": "queued"},
                                                           {"id": 12, "status": "done"}, None]
        assert (view["picked_id"], view["corpus"]) == (4, CORPUS)
        assert view["seeds_left"] == len(SEEDS) - 2
        assert list(view["papers"]) == ["P2", "P1", "P3", "P4", "P5", "X9"]
        assert view["papers"]["P4"]["title"] == "노인 우울 논문 4"
        assert view["papers"]["X9"] == {"title": "X9", "personal_author": None, "pub_date": None,
                                        "series_title": None}

    def test_corpus_falls_back_to_the_report_and_the_view_is_json(self):
        work = SimpleNamespace(topic_id=None, corpus_snapshot=None)
        job = SimpleNamespace(report=REPORT, finished_at=datetime(2026, 10, 6, 9, 30))
        view = topics_view(work, job, [], [])
        assert view["corpus"] == CORPUS and view["items"] == [] and view["seeds_left"] == len(SEEDS)
        assert json.loads(json.dumps(view, ensure_ascii=False)) == view


# ── 조회 ─────────────────────────────────────────────────────────────


class TestGetTopics:
    def test_404_until_continued(self, api):
        jid = _job(api.engine)
        assert api.client.get(f"/api/research/{jid}/topics").status_code == 404
        assert api.client.get("/api/research/not-a-uuid/topics").status_code == 422

    def test_lists_the_topics_with_their_generations(self, api):
        jid = _work_job(api.engine)
        tid = add_topic(api.engine, jid, slot=1, seed=SEEDS[0])
        gid = add_generation(api.engine, jid, kind="topic_card", target=str(tid))
        mine = add_topic(api.engine, jid, origin="user", card=CARD)

        res = api.client.get(f"/api/research/{jid}/topics")

        assert res.status_code == 200
        body = res.json()
        assert [(i["id"], i["slot"], i["origin"], i["generation"]) for i in body["items"]] == [
            (tid, 1, "report_seed", {"id": gid, "status": "queued"}), (mine, None, "user", None)]
        assert body["items"][0]["seed"] == SEEDS[0] and body["items"][1]["card"] == CARD
        assert body["seeds_left"] == len(SEEDS) - 1
        # 연구에 스냅숏이 없으면(06a 에서 이어간 연구) 보고서 범위와 잡 완료 시각으로 채운다
        assert body["corpus"] == CORPUS and body["picked_id"] is None


# ── 다른 방향 ────────────────────────────────────────────────────────


class TestOtherDirection:
    def test_two_cards_from_unused_seeds(self, api):
        jid = _work_job(api.engine)
        _set(api.engine, ResearchWork, jid, corpus_snapshot=CORPUS)
        add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)

        res = api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"})

        assert res.status_code == 200
        made = [t for t in _rows(api.engine, ResearchTopic) if t["origin"] == "other"]
        assert [t["seed"]["key"] for t in made] == [SEEDS[1]["key"], SEEDS[2]["key"]]
        assert all((t["slot"], t["state"], t["card"], t["corpus_snapshot"]) == (None, "candidate", {}, CORPUS)
                   for t in made)
        gens = _rows(api.engine, ResearchGeneration)
        assert res.json() == {"topic_ids": [t["id"] for t in made], "gen_ids": [g["id"] for g in gens]}
        for topic, gen in zip(made, gens):
            assert (gen["kind"], gen["target"], gen["status"], gen["priority"]) == (
                "topic_card", str(topic["id"]), "queued", 10)
            assert gen["input"] == topic_input(QUESTION, topic["seed"], REPORT, topic["id"])
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "generation", {
            "gen_id": g["id"], "gen_kind": "topic_card", "target": g["target"], "status": "queued",
            "model": None, "result": None}) for g in gens]

    def test_the_last_seed_makes_one_card_then_409(self, api):
        jid = _work_job(api.engine)
        for n, seed in enumerate(SEEDS[:-1], start=1):
            add_topic(api.engine, jid, slot=n, seed=seed)

        first = api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"})
        again = api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"})

        assert first.status_code == 200 and len(first.json()["topic_ids"]) == 1
        assert _topic(api.engine, first.json()["topic_ids"][0])["seed"]["key"] == "insufficient:1"
        assert again.status_code == 409 and again.json()["detail"] == "더 쓸 씨앗이 없습니다"
        assert len(_rows(api.engine, ResearchTopic)) == len(SEEDS)
        assert api.dispatch.calls == 1

    def test_seeds_are_read_and_used_under_one_lock(self, api):
        jid = _work_job(api.engine)
        seen: list[tuple] = []
        sa.event.listen(api.engine, "before_cursor_execute",
                        lambda conn, cur, stmt, params, ctx, many: seen.append((stmt, params)))
        sa.event.listen(api.engine, "commit", lambda conn: seen.append(("COMMIT", None)))

        assert api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"}).status_code == 200

        lock = next(i for i, (s, p) in enumerate(seen) if "pg_advisory_xact_lock" in s
                    and p == (lock_key(jid, "topic_card", "other-direction"),))
        read = next(i for i, (s, _) in enumerate(seen) if s.startswith("SELECT research_topics.seed"))
        insert = next(i for i, (s, _) in enumerate(seen) if s.startswith("INSERT INTO research_topics"))
        commit = next(i for i, (s, _) in enumerate(seen) if s == "COMMIT" and i > lock)
        assert lock < read < insert < commit

    @pytest.mark.parametrize("body", [{"mode": "cell", "cell_key": "개념|실험"}, {}, {"mode": "more"}])
    def test_only_the_other_mode_in_06b(self, api, body):
        jid = _work_job(api.engine)
        assert api.client.post(f"/api/research/{jid}/topics/generate", json=body).status_code == 422
        assert _rows(api.engine, ResearchTopic) == []

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        res = api.client.post(f"/api/research/{jid}/topics/generate", json={"mode": "other"})
        assert res.status_code == 409 and res.json()["detail"] == "예시 연구는 읽기 전용입니다"
        assert _rows(api.engine, ResearchTopic) == []


# ── 직접 쓰기·직접 고치기 ─────────────────────────────────────────────


class TestCreateTopic:
    def test_user_card_without_evidence(self, api):
        jid = _work_job(api.engine)

        res = api.client.post(f"/api/research/{jid}/topics",
                              json={"title": "  노인 우울과 디지털 소통 ", "question": "디지털 소통은 우울을 낮추는가?"})

        assert res.status_code == 200
        (row,) = _rows(api.engine, ResearchTopic)
        assert (row["origin"], row["slot"], row["state"], row["seed"]) == ("user", None, "candidate", {})
        assert row["card"] == {
            "title": "노인 우울과 디지털 소통", "question": "디지털 소통은 우울을 낮추는가?", "evidence": [],
            "figure_sentence": None, "figures": [], "latest_year": None, "edited": False,
            "checks": {"numbers": [], "softened": 0, "recovered": 0}, "gen_id": None}
        body = res.json()
        assert (body["id"], body["origin"], body["card"], body["seed"], body["generation"]) == (
            row["id"], "user", row["card"], None, None)
        assert _rows(api.engine, ResearchGeneration) == [] and api.dispatch.calls == 0
        (work,) = _rows(api.engine, ResearchWork)
        assert work["progress"]["topics"] == 1
        assert api.events == [(str(jid), "work", {"phase": "topics", "progress": work["progress"]})]

    def test_claims_are_softened_and_numbers_counted(self, api):
        jid = _work_job(api.engine)
        title, question = "최초의 노인 디지털 소통 연구", "2020년 이후 소통 방식은 바뀌었는가?"

        card = api.client.post(f"/api/research/{jid}/topics", json={"title": title, "question": question}).json()["card"]

        soft_title, n = soften_claims(title)
        assert n >= 1 and card["title"] == soft_title
        assert card["checks"]["softened"] == n + soften_claims(question)[1]
        assert card["checks"]["numbers"] == numbers_outside(f"{soft_title}\n{question}") == ["2020"]

    @pytest.mark.parametrize("body", [{"title": "가", "question": "질문은 이것인가?"},
                                      {"title": "주제", "question": "  "},
                                      {"title": "주" * 121, "question": "질문?"},
                                      {"title": "주제"}])
    def test_rejects_short_long_or_missing_text(self, api, body):
        jid = _work_job(api.engine)
        assert api.client.post(f"/api/research/{jid}/topics", json=body).status_code == 422
        assert _rows(api.engine, ResearchTopic) == []

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        res = api.client.post(f"/api/research/{jid}/topics", json={"title": "주제", "question": "질문?"})
        assert res.status_code == 409


class TestEditTopic:
    def test_title_only_keeps_the_rest_and_marks_the_card_edited(self, api):
        jid = _work_job(api.engine)
        tid = add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)
        gid = add_generation(api.engine, jid, kind="topic_card", status="done", target=str(tid))

        res = api.client.patch(f"/api/research/{jid}/topics/{tid}", json={"title": "독거노인 지지망과 우울 변화"})

        assert res.status_code == 200
        card = _topic(api.engine, tid)["card"]
        assert card == {**CARD, "title": "독거노인 지지망과 우울 변화", "edited": True,
                        "checks": {"numbers": [], "softened": 0, "recovered": 0}}
        assert _topic(api.engine, tid)["origin"] == "report_seed"
        assert res.json()["card"] == card and res.json()["generation"] == {"id": gid, "status": "done"}
        assert api.events[-1][1] == "work"

    def test_an_insufficient_topic_becomes_a_user_written_card(self, api):
        jid = _work_job(api.engine)
        tid = add_topic(api.engine, jid, slot=2, seed=SEEDS[1], state="insufficient")

        res = api.client.patch(f"/api/research/{jid}/topics/{tid}",
                               json={"title": "농촌 노인 우울 선별", "question": "선별 도구는 타당한가?"})

        assert res.status_code == 200
        row = _topic(api.engine, tid)
        assert row["state"] == "candidate"
        assert (row["card"]["title"], row["card"]["evidence"], row["card"]["edited"]) == (
            "농촌 노인 우울 선별", [], True)
        assert _rows(api.engine, ResearchWork)[0]["progress"]["topics"] == 1

    def test_an_empty_card_needs_both_fields(self, api):
        jid = _work_job(api.engine)
        tid = add_topic(api.engine, jid, slot=2, seed=SEEDS[1], state="insufficient")

        res = api.client.patch(f"/api/research/{jid}/topics/{tid}", json={"title": "농촌 노인 우울 선별"})

        assert res.status_code == 422 and res.json()["detail"] == "빈 카드는 제목과 연구 질문을 함께 보내 주세요"
        assert _topic(api.engine, tid)["card"] == {}

    @pytest.mark.parametrize("status", ["queued", "running"])
    def test_waits_while_the_card_is_being_made(self, api, status):
        jid = _work_job(api.engine)
        tid = add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)
        add_generation(api.engine, jid, kind="topic_card", status=status, target=str(tid))

        res = api.client.patch(f"/api/research/{jid}/topics/{tid}", json={"title": "새 제목입니다"})

        assert res.status_code == 409 and res.json()["detail"] == "카드를 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
        assert _topic(api.engine, tid)["card"] == CARD

    def test_needs_a_field_and_a_known_topic(self, api):
        jid = _work_job(api.engine)
        tid = add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)
        other = add_topic(api.engine, _work_job(api.engine), slot=1, seed=SEEDS[0], card=CARD)

        assert api.client.patch(f"/api/research/{jid}/topics/{tid}", json={}).status_code == 422
        res = api.client.patch(f"/api/research/{jid}/topics/{other}", json={"title": "새 제목입니다"})
        assert res.status_code == 404 and res.json()["detail"] == "주제가 없습니다"
        assert api.client.patch(f"/api/research/{jid}/topics/999", json={"title": "새 제목입니다"}).status_code == 404

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        tid = add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)
        assert api.client.patch(f"/api/research/{jid}/topics/{tid}", json={"title": "새 제목"}).status_code == 409


# ── 고르기 ───────────────────────────────────────────────────────────


class TestPick:
    def test_picks_one_topic_and_moves_to_the_reading_list(self, api):
        jid = _work_job(api.engine)
        before = add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD, state="picked")
        tid = add_topic(api.engine, jid, slot=2, seed=SEEDS[1], card=CARD)
        _set(api.engine, ResearchWork, jid, topic_id=before)

        res = api.client.post(f"/api/research/{jid}/topics/{tid}/pick")

        assert res.status_code == 200 and res.json() == {"topic_id": tid, "phase": "reading"}
        assert [(t["id"], t["state"]) for t in _rows(api.engine, ResearchTopic)] == [
            (before, "candidate"), (tid, "picked")]
        (work,) = _rows(api.engine, ResearchWork)
        assert (work["topic_id"], work["phase"]) == (tid, "reading")
        assert api.events == [(str(jid), "work", {"phase": "reading", "progress": work["progress"]})]

    def test_a_later_phase_stays(self, api):
        jid = _work_job(api.engine, phase="proposal")
        tid = add_topic(api.engine, jid, slot=1, seed=SEEDS[0], card=CARD)

        assert api.client.post(f"/api/research/{jid}/topics/{tid}/pick").json() == {
            "topic_id": tid, "phase": "proposal"}
        assert _rows(api.engine, ResearchWork)[0]["phase"] == "proposal"

    @pytest.mark.parametrize("state", ["candidate", "insufficient"])
    def test_a_topic_without_a_card_cannot_be_picked(self, api, state):
        jid = _work_job(api.engine)
        tid = add_topic(api.engine, jid, slot=1, seed=SEEDS[0], state=state)

        res = api.client.post(f"/api/research/{jid}/topics/{tid}/pick")

        assert res.status_code == 409 and res.json()["detail"] == "카드가 아직 없습니다"
        assert _rows(api.engine, ResearchWork)[0]["topic_id"] is None and api.events == []

    def test_unknown_topic_and_example_work(self, api):
        jid = _work_job(api.engine)
        assert api.client.post(f"/api/research/{jid}/topics/999/pick").status_code == 404
        example = _work_job(api.engine, is_example=True)
        tid = add_topic(api.engine, example, slot=1, seed=SEEDS[0], card=CARD)
        assert api.client.post(f"/api/research/{example}/topics/{tid}/pick").status_code == 409


# ── 끝까지 한 번 ──────────────────────────────────────────────────────


class TestEndToEnd:
    def test_continue_makes_four_cards_then_one_is_picked(self, api):
        # 이어가기(씨앗 4장) → 디스패처가 생성을 하나씩 집어 실행기·결과 적용·닫기 → 주제 조회 → 고르기
        from services.llm_client import LLMResult
        from services.research_work import dispatch
        from services.research_work.apply import apply_result
        from services.research_work.executors import EXECUTORS
        from services.research_work.generate import run_generation

        jid = _job(api.engine)
        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        async def _chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            if "향후 과제(씨앗)" in messages[-1]["content"]:
                content = {"title": "독거노인 지지망 연구", "question": "지지망은 우울을 낮추는가?",
                           "evidence": ["E1", "E2"]}
            else:
                content = {"concepts": ["노인 우울", "사회적 지지"]}
            return LLMResult(content=json.dumps(content, ensure_ascii=False), finish_reason="stop")

        async def _drain() -> list[str]:
            kinds = []
            while True:
                db = AsyncSessionOverSync(api.engine)
                try:
                    gen = await dispatch.pick_next(db)
                    if gen is None:
                        return kinds
                    gen_id = gen.id
                    result = await run_generation(EXECUTORS[gen.kind], dict(gen.input), chat_fn=_chat)
                    await apply_result(db, gen, result.output)
                    assert await dispatch.finish(db, gen_id, status="done", model=result.model, error=None,
                                                 output={**result.output, "attempts": result.attempts})
                    kinds.append(gen.kind)
                finally:
                    await db.close()

        assert asyncio.run(_drain()) == ["concepts", "topic_card", "topic_card", "topic_card", "topic_card"]

        topics = api.client.get(f"/api/research/{jid}/topics").json()
        assert [(i["slot"], i["state"], i["generation"]["status"]) for i in topics["items"]] == [
            (n, "candidate", "done") for n in range(1, 5)]
        first = topics["items"][0]
        assert first["card"]["evidence"] == first["seed"]["papers"][:2]
        assert first["card"]["figure_sentence"].startswith("이 하위질문에서 채택한 논문은 [F1]")
        assert set(first["card"]["evidence"]) <= set(topics["papers"])
        assert topics["seeds_left"] == 1
        assert api.client.get(f"/api/research/{jid}/work").json()["progress"]["topics"] == 4

        res = api.client.post(f"/api/research/{jid}/topics/{first['id']}/pick")

        assert res.json() == {"topic_id": first["id"], "phase": "reading"}
        work = api.client.get(f"/api/research/{jid}/work").json()
        assert (work["topic_id"], work["phase"]) == (first["id"], "reading")


class TestAppWiring:
    def test_main_includes_the_topics_router_after_the_work_router(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
        imported = {
            (node.module, alias.name, alias.asname)
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        included = [
            node.args[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "include_router"
        ]
        assert ("api.research_topics", "router", "research_topics_router") in imported
        assert included.index("research_work_router") < included.index("research_topics_router")
