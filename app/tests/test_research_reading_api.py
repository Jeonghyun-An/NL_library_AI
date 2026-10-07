"""test_research_reading_api.py — 읽기 목록(services/research_work/reading_views.py·api/research_reading.py).

앞 절은 응답 모양 순수 함수, 뒤 절은 TestClient 로 라우팅을 거치는 API 다. DB 는 history_sqlite 의 SQLite —
서지(library_catalog)·읽기 목록 행·진행 요약을 실제 SQL 로 읽고 쓴다. 요청이 끝나면 세션을 되돌리므로 핸들러가
직접 커밋한 쓰기만 남는다. redis 는 로컬 venv 에 없다 — 미설치일 때만 더미를 꽂고 publish_work 는 기록용 가짜다.
"""
import ast
import importlib
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from history_sqlite import (
    AsyncSessionOverSync, add_book, add_proposal, add_reading, add_research_job, add_topic, add_work,
    make_engine,
)
from models.research import ResearchJob
from models.research_work import ResearchReading, ResearchWork
from services.research_work.reading_views import (
    book_meta, excluded_candidates, funnel, reading_item, reading_order, reading_path, reading_view,
    subquestions_of,
)
from services.research_work.shapes import PATH_CHUNK_CHARS

PLAN = ["독서 격차의 원인", "독서 격차의 영향"]
LONG = "가" * (PATH_CHUNK_CHARS + 50)
X1 = {"cnts_id": "X1", "title": "무관 논문", "personal_author": "박민수", "pub_date": "2015"}
X2 = {"cnts_id": "X2", "title": "다른 뜻 논문", "personal_author": "최", "pub_date": "2012"}
ROUNDS_0 = [
    {"round": 1, "query": "독서 격차 원인", "verdict": "insufficient", "note": "가정 요인이 부족하다",
     "excluded": 1, "excluded_papers": [X1]},
    {"round": 2, "query": "가정 독서 환경", "verdict": "sufficient", "note": "충분하다",
     "excluded": 0, "excluded_papers": []},
]
ROUNDS_1 = [
    {"round": 1, "query": "독서 격차 영향", "verdict": "insufficient", "note": "영향 연구가 적다",
     "excluded": 2, "excluded_papers": [X2, X1]},
]
SNAPSHOT = {
    "question": "청소년 독서 격차",
    "subquestions": [
        {"idx": 0, "text": PLAN[0], "evidence_ids": ["E1", "E2"], "verdict": "sufficient",
         "evidence_chunks": {"E1": ["c1", "c2"], "E2": ["c3"]},
         "chunk_scores": {"c1": 0.91, "c2": 0.7, "c3": 0.65}, "rounds": ROUNDS_0},
        {"idx": 1, "text": PLAN[1], "evidence_ids": ["E1"], "verdict": "insufficient",
         "evidence_chunks": {"E1": ["c1"]}, "chunk_scores": {"c1": 0.5}, "rounds": ROUNDS_1},
    ],
    "evidence": {
        "E1": {"cnts_id": "C1", "meta": {"title": "독서 격차 연구"},
               "chunks": [{"chunk_id": "c1", "text": LONG, "page_start": 3, "page_end": 4, "score": 0.91},
                          {"chunk_id": "c2", "text": "둘째 대목", "page_start": 5, "page_end": 5,
                           "score": 0.7}]},
        "E2": {"cnts_id": "C2", "meta": {"title": "학교 도서관"},
               "chunks": [{"chunk_id": "c3", "text": "학교 대목", "page_start": 0, "page_end": 0,
                           "score": 0.65}]},
    },
}
REPORT = {
    "question": "청소년 독서 격차",
    "stats": {"papers_reviewed": 121, "evidence_adopted": 48, "rechecks": 1, "excluded": 2},
    "trail": [{"subquestion": PLAN[0], "excluded_papers": [X1]},
              {"subquestion": PLAN[1], "excluded_papers": [X2, X1]}],
}
# 이어가기(candidates_from_snapshot)가 C1·C2 에 남기는 들어온 경로 그대로
REF_C1 = {"subq_idx": [0, 1], "rank": {"0": 1, "1": 1}, "chunks": {"0": ["c1", "c2"], "1": ["c1"]},
          "chunk_scores": {"0": {"c1": 0.91, "c2": 0.7}, "1": {"c1": 0.5}},
          "verdict": {"0": "sufficient", "1": "insufficient"}, "first_round": {"0": 1}}
REF_C2 = {"subq_idx": [0], "rank": {"0": 2}, "chunks": {"0": ["c3", "c9"]},
          "chunk_scores": {"0": {"c3": 0.65}}, "verdict": {"0": "sufficient"}}


def _job_ns(**fields) -> SimpleNamespace:
    base = {"plan": PLAN, "state_snapshot": SNAPSHOT, "report": REPORT}
    return SimpleNamespace(**{**base, **fields})


def _row(cnts_id, **fields) -> SimpleNamespace:
    base = {"cnts_id": cnts_id, "state": "candidate", "origin": "evidence", "origin_ref": {},
            "note": None, "group_label": None, "position": None}
    return SimpleNamespace(**{**base, **fields})


# ── 응답 모양(순수 함수) ──────────────────────────────────────────────


class TestReadingPath:
    def test_evidence_path_lists_each_subquestion_with_its_stored_values(self):
        path = reading_path("evidence", REF_C1, SNAPSHOT, PLAN)
        assert path["revived"] is None and path["user"] is False
        assert [(s["idx"], s["subquestion"], s["rank"], s["verdict"], s["first_round"])
                for s in path["subqs"]] == [
            (0, PLAN[0], 1, "sufficient", 1), (1, PLAN[1], 1, "insufficient", None)]
        assert path["subqs"][0]["chunks"] == [
            {"chunk_id": "c1", "page_start": 3, "page_end": 4, "score": 0.91,
             "text": "가" * PATH_CHUNK_CHARS},
            {"chunk_id": "c2", "page_start": 5, "page_end": 5, "score": 0.7, "text": "둘째 대목"},
        ]
        # 같은 대목이라도 점수는 그 하위질문의 매칭 점수다
        assert path["subqs"][1]["chunks"][0]["score"] == 0.5

    def test_chunks_missing_from_the_snapshot_are_left_out(self):
        # c9 는 스냅숏에 글이 없다 — 저장된 값만 쓴다
        path = reading_path("evidence", REF_C2, SNAPSHOT, PLAN)
        assert [c["chunk_id"] for c in path["subqs"][0]["chunks"]] == ["c3"]

    def test_no_snapshot_keeps_the_subquestions_without_chunks(self):
        path = reading_path("evidence", REF_C1, None, PLAN)
        assert [s["chunks"] for s in path["subqs"]] == [[], []]

    def test_revived_path(self):
        path = reading_path("revived", {"subq_idx": 1, "round": 1, "note": "영향 연구가 적다"},
                            SNAPSHOT, PLAN)
        assert path == {"subqs": [], "user": False, "revived": {
            "subq_idx": 1, "subquestion": PLAN[1], "round": 1, "note": "영향 연구가 적다"}}

    def test_user_path(self):
        assert reading_path("user", {}, SNAPSHOT, PLAN) == {"subqs": [], "revived": None, "user": True}

    def test_subquestion_outside_the_plan_is_blank(self):
        path = reading_path("revived", {"subq_idx": 7, "round": None, "note": None}, None, PLAN)
        assert path["revived"] == {"subq_idx": 7, "subquestion": "", "round": None, "note": ""}


class TestReadingItemAndOrder:
    def test_item_shape(self):
        row = _row("C2", state="in", origin_ref=REF_C2, note="메모", group_label="가정", position=3)
        meta = book_meta("C2", None)
        assert reading_item(row, meta, SNAPSHOT, PLAN) == {
            "cnts_id": "C2", "state": "in", "origin": "evidence", "note": "메모",
            "group_label": "가정", "position": 3, "meta": meta,
            "path": reading_path("evidence", REF_C2, SNAPSHOT, PLAN),
        }

    def test_book_meta_falls_back_to_the_id(self):
        assert book_meta("Z9", None) == {"title": "Z9", "personal_author": None, "pub_date": None,
                                         "series_title": None}
        book = SimpleNamespace(title="독서 격차 연구", personal_author="김철수", pub_date="2019",
                               series_title="교육학연구")
        assert book_meta("C1", book) == {"title": "독서 격차 연구", "personal_author": "김철수",
                                         "pub_date": "2019", "series_title": "교육학연구"}

    def test_order_is_position_then_best_rank_then_id(self):
        rows = [_row("C5"), _row("C4", origin_ref={"rank": {"1": 2}}),
                _row("C3", origin_ref={"rank": {"0": 4, "1": 1}}), _row("C2", position=1),
                _row("C1", position=0), _row("R1", origin="revived", origin_ref={"subq_idx": 0})]
        assert [r.cnts_id for r in reading_order(rows)] == ["C1", "C2", "C3", "C4", "C5", "R1"]

    def test_subquestions_are_the_plan_strings(self):
        assert subquestions_of(_job_ns(plan=[PLAN[0], 3, None, PLAN[1]])) == PLAN
        assert subquestions_of(_job_ns(plan=None)) == []


class TestFunnel:
    def test_counts(self):
        rows = [_row("C1", state="in"), _row("C2", state="candidate"), _row("C3", state="out")]
        assert funnel(REPORT, rows) == {"reviewed": 121, "adopted": 48, "candidates": 2, "picked": 1}

    def test_missing_stats_are_none(self):
        assert funnel({}, []) == {"reviewed": None, "adopted": None, "candidates": 0, "picked": 0}
        assert funnel({"stats": {"papers_reviewed": True}}, [])["reviewed"] is None


class TestExcludedCandidates:
    def test_round_and_note_come_from_the_snapshot_rounds(self):
        assert excluded_candidates(_job_ns(), []) == [
            {**X1, "subq_idx": 0, "subquestion": PLAN[0], "round": 1, "note": "가정 요인이 부족하다"},
            {**X2, "subq_idx": 1, "subquestion": PLAN[1], "round": 1, "note": "영향 연구가 적다"},
        ]

    def test_papers_that_already_have_a_row_are_left_out(self):
        assert [c["cnts_id"] for c in excluded_candidates(_job_ns(), [_row("X1", origin="revived")])] == [
            "X2"]

    def test_old_job_without_round_records(self):
        snap = {**SNAPSHOT, "subquestions": [{**sq, "rounds": []} for sq in SNAPSHOT["subquestions"]]}
        out = excluded_candidates(_job_ns(state_snapshot=snap), [])
        assert [(c["cnts_id"], c["round"], c["note"]) for c in out] == [("X1", None, ""), ("X2", None, "")]


class TestReadingView:
    def test_shape(self):
        work = SimpleNamespace(topic_id=12)
        rows = [_row("C2", origin_ref=REF_C2), _row("C1", state="in", origin_ref=REF_C1)]
        books = {"C1": SimpleNamespace(title="독서 격차 연구", personal_author="김철수", pub_date="2019",
                                       series_title=None)}
        view = reading_view(work, _job_ns(), rows, books)
        assert view["topic_id"] == 12 and view["stale"] is False and view["subquestions"] == PLAN
        assert view["funnel"] == {"reviewed": 121, "adopted": 48, "candidates": 2, "picked": 1}
        assert [(i["cnts_id"], i["meta"]["title"]) for i in view["items"]] == [
            ("C1", "독서 격차 연구"), ("C2", "C2")]
        assert [c["cnts_id"] for c in view["excluded"]] == ["X1", "X2"]
        assert json.loads(json.dumps(view)) == view

    def test_no_outline_or_the_same_topic_is_not_stale(self):
        work = SimpleNamespace(topic_id=2)
        # 목차가 없으면(계획서 행이 없거나 목차가 비었으면) 배지도 없다
        assert reading_view(work, _job_ns(), [], {})["stale"] is False
        assert reading_view(work, _job_ns(), [], {}, {})["stale"] is False
        # 목차를 만든 주제를 그대로 고른 채면 거짓 — 참이 되는 경우는 API 테스트가 본다
        assert reading_view(work, _job_ns(), [], {}, {"topic": {"id": 2}})["stale"] is False


# ── API ─────────────────────────────────────────────────────────────


def _stub_missing(monkeypatch, name: str, module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module)


_CACHED = ("api.research_reading", "api.research_work", "services.research.relay")


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """test_research_work_api.py 와 같은 방식 — 더미 redis 에 묶인 relay 가 다른 테스트로 새지 않게."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


class _Api:
    def __init__(self, client, engine, router, events):
        self.client = client
        self.engine = engine
        self.router = router
        self.events = events


@pytest.fixture
def api(monkeypatch):
    for name in ("redis", "redis.asyncio"):
        _stub_missing(monkeypatch, name, MagicMock())
    _forget_on_teardown(monkeypatch, _CACHED)
    router = importlib.import_module("api.research_reading")
    from core.deps import get_db

    events: list[tuple] = []

    async def _publish_work(work_id, kind, payload):
        events.append((str(work_id), kind, payload))

    monkeypatch.setattr(router, "publish_work", _publish_work)
    engine = make_engine()

    async def _db():
        db = AsyncSessionOverSync(engine)
        try:
            yield db
        finally:
            await db.rollback()
            await db.close()

    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[get_db] = _db
    return _Api(TestClient(app), engine, router, events)


def _work_job(engine, *, continued: bool = True, **work) -> uuid.UUID:
    jid = add_research_job(engine, status="completed", stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == jid).values(
            question="청소년 독서 격차", plan=PLAN, state_snapshot=SNAPSHOT, report=REPORT,
        ))
    if continued:
        add_work(engine, jid, phase="reading", **work)
        add_reading(engine, jid, "C1", origin_ref=REF_C1)
        add_reading(engine, jid, "C2", origin_ref=REF_C2)
    return jid


def _reading(engine, jid) -> dict:
    table = ResearchReading.__table__
    with engine.connect() as conn:
        rows = conn.execute(sa.select(table).where(table.c.work_id == jid)).mappings().all()
    return {r["cnts_id"]: dict(r) for r in rows}


def _progress(engine, jid) -> dict:
    table = ResearchWork.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table.c.progress).where(table.c.id == jid)).scalar_one()


class TestGetReading:
    def test_items_meta_funnel_and_excluded(self, api):
        jid = _work_job(api.engine)
        add_book(api.engine, "C1", title="독서 격차 연구", personal_author="김철수", pub_date="2019",
                 series_title="교육학연구")

        res = api.client.get(f"/api/research/{jid}/reading")

        assert res.status_code == 200
        body = res.json()
        assert body["topic_id"] is None and body["stale"] is False and body["subquestions"] == PLAN
        assert body["funnel"] == {"reviewed": 121, "adopted": 48, "candidates": 2, "picked": 0}
        assert [(i["cnts_id"], i["origin"], i["meta"]) for i in body["items"]] == [
            ("C1", "evidence", {"title": "독서 격차 연구", "personal_author": "김철수",
                                "pub_date": "2019", "series_title": "교육학연구"}),
            ("C2", "evidence", {"title": "C2", "personal_author": None, "pub_date": None,
                                "series_title": None}),
        ]
        assert body["items"][0]["path"]["subqs"][0]["chunks"][0]["text"] == "가" * PATH_CHUNK_CHARS
        assert [c["cnts_id"] for c in body["excluded"]] == ["X1", "X2"]

    def test_picking_another_topic_after_the_outline_marks_the_list_stale(self, api):
        # 목차를 만든 뒤 주제 화면에서 다른 카드를 골랐다 — 계획서뿐 아니라 읽기 목록에도 '다시 맞춤 필요'(spec §5-2)
        jid = _work_job(api.engine)
        card = {"title": "첫 주제", "question": "가는 나인가?"}
        first = add_topic(api.engine, jid, slot=1, card=card)
        second = add_topic(api.engine, jid, slot=2, card={"title": "둘째 주제", "question": "다는 라인가?"},
                           state="picked")
        add_proposal(api.engine, jid, outline={"topic": {"id": first, **card}, "groups": []})
        table = ResearchWork.__table__
        with api.engine.begin() as conn:
            conn.execute(sa.update(table).where(table.c.id == jid).values(topic_id=second))

        body = api.client.get(f"/api/research/{jid}/reading").json()

        assert body["topic_id"] == second and body["stale"] is True

    def test_404_until_continued(self, api):
        jid = _work_job(api.engine, continued=False)
        assert api.client.get(f"/api/research/{jid}/reading").status_code == 404

    def test_bad_id_is_422(self, api):
        assert api.client.get("/api/research/not-a-uuid/reading").status_code == 422


class TestPutReading:
    def test_picking_a_candidate(self, api):
        jid = _work_job(api.engine)

        res = api.client.put(f"/api/research/{jid}/reading/C1", json={"state": "in"})

        assert res.status_code == 200
        assert res.json()["state"] == "in" and res.json()["cnts_id"] == "C1"
        assert _reading(api.engine, jid)["C1"]["state"] == "in"
        assert _progress(api.engine, jid)["reading"] == 1
        (event,) = api.events
        assert event[:2] == (str(jid), "work")
        assert event[2]["phase"] == "reading" and event[2]["progress"]["reading"] == 1

    def test_only_the_sent_fields_change(self, api):
        jid = _work_job(api.engine)
        api.client.put(f"/api/research/{jid}/reading/C1",
                       json={"state": "in", "note": "핵심", "group_label": "가정", "position": 2})

        res = api.client.put(f"/api/research/{jid}/reading/C1", json={"note": "  다시 읽기  "})

        row = _reading(api.engine, jid)["C1"]
        assert (row["state"], row["note"], row["group_label"], row["position"]) == (
            "in", "다시 읽기", "가정", 2)
        assert res.json()["note"] == "다시 읽기"

    def test_null_or_blank_clears_note_and_group(self, api):
        jid = _work_job(api.engine)
        api.client.put(f"/api/research/{jid}/reading/C1", json={"note": "메모", "group_label": "가정"})

        api.client.put(f"/api/research/{jid}/reading/C1", json={"note": None, "group_label": "   "})

        row = _reading(api.engine, jid)["C1"]
        assert (row["note"], row["group_label"]) == (None, None)

    def test_reviving_a_paper_the_critic_dropped(self, api):
        jid = _work_job(api.engine)

        res = api.client.put(f"/api/research/{jid}/reading/X2", json={})

        assert res.status_code == 200
        row = _reading(api.engine, jid)["X2"]
        assert (row["state"], row["origin"]) == ("candidate", "revived")
        assert row["origin_ref"] == {"subq_idx": 1, "round": 1, "note": "영향 연구가 적다"}
        assert res.json()["path"]["revived"] == {"subq_idx": 1, "subquestion": PLAN[1], "round": 1,
                                                 "note": "영향 연구가 적다"}
        assert [c["cnts_id"] for c in api.client.get(f"/api/research/{jid}/reading").json()["excluded"]] == [
            "X1"]

    def test_new_row_takes_the_sent_state(self, api):
        jid = _work_job(api.engine)
        api.client.put(f"/api/research/{jid}/reading/X1", json={"state": "in"})
        assert _reading(api.engine, jid)["X1"]["state"] == "in"
        assert _progress(api.engine, jid)["reading"] == 1

    def test_adding_a_catalog_paper(self, api):
        # 06d 빠른검색 [담기] — 잡과 상관없는 논문도 소장 목록에 있으면 담는다
        jid = _work_job(api.engine)
        add_book(api.engine, "U1", title="빠른검색에서 담은 논문")

        res = api.client.put(f"/api/research/{jid}/reading/U1", json={"state": "in"})

        assert res.status_code == 200
        row = _reading(api.engine, jid)["U1"]
        assert (row["origin"], row["origin_ref"], row["state"]) == ("user", {}, "in")
        assert res.json()["meta"]["title"] == "빠른검색에서 담은 논문"
        assert res.json()["path"] == {"subqs": [], "revived": None, "user": True}

    def test_unknown_paper_is_404(self, api):
        jid = _work_job(api.engine)

        res = api.client.put(f"/api/research/{jid}/reading/NOPE", json={"state": "in"})

        assert res.status_code == 404 and res.json()["detail"] == api.router.NO_PAPER
        assert "NOPE" not in _reading(api.engine, jid) and api.events == []

    def test_nothing_sent_to_an_existing_row_writes_nothing(self, api):
        jid = _work_job(api.engine)
        res = api.client.put(f"/api/research/{jid}/reading/C1", json={})
        assert res.status_code == 200 and res.json()["state"] == "candidate"
        assert api.events == []

    @pytest.mark.parametrize("body", [
        {"state": "maybe"}, {"state": None}, {"note": "가" * 1001}, {"group_label": "가" * 61},
        {"position": -1},
    ])
    def test_invalid_body_is_422(self, api, body):
        jid = _work_job(api.engine)
        assert api.client.put(f"/api/research/{jid}/reading/C1", json=body).status_code == 422
        assert _reading(api.engine, jid)["C1"]["state"] == "candidate"

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        assert api.client.put(f"/api/research/{jid}/reading/C1", json={"state": "in"}).status_code == 409

    def test_404_until_continued(self, api):
        jid = _work_job(api.engine, continued=False)
        assert api.client.put(f"/api/research/{jid}/reading/C1", json={"state": "in"}).status_code == 404


class TestAppWiring:
    def test_main_includes_the_reading_router_after_the_topics_router(self):
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
        assert ("api.research_reading", "router", "research_reading_router") in imported
        assert included.index("research_topics_router") < included.index("research_reading_router")
