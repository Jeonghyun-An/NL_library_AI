"""test_research_proposal_api.py — 계획서(services/research_work/proposal_views.py·api/research_proposal.py).

앞 절은 응답 모양 순수 함수, 뒤 절은 TestClient 로 라우팅을 거치는 API 다. DB 는 history_sqlite 의 SQLite.
개념 친밀도(membership.concept_affinity — 임베딩·Milvus)는 라우터 모듈 속성을 가짜로 바꾼다(FastAPI 에서만
돌고 로컬 venv 에는 모델이 없다). redis 는 미설치일 때만 더미를 꽂고, publish_work 는 기록용 가짜, 디스패치
태스크를 보내는 워커 모듈은 sys.modules 에 가짜를 꽂는다(test_research_work_api.py 와 같다).
"""
import ast
import importlib
import json
import sys
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from history_sqlite import (
    AsyncSessionOverSync, add_book, add_generation, add_proposal, add_reading, add_research_job,
    add_topic, add_work, make_engine,
)
from models.research import ResearchJob
from models.research_work import ResearchGeneration, ResearchProposal, ResearchWork
from services.research_work.proposal_views import (
    cited_papers, disclosure_of, drafts_of, paper_ids, proposal_view, stale_flags,
)
from services.research_work.seeds import corpus_of
from services.research_work.shapes import OUTLINE_TARGET
from services.search.paper_citation import build_citation

PLAN = ["노인 우울의 요인", "사회적 지지의 효과"]
CONCEPTS = ["노인의 우울", "사회적 지지"]
CARD = {"title": "노인의 사회적 지지와 우울의 관계", "question": "사회적 지지는 노인의 우울을 낮추는가?",
        "evidence": ["C1", "K9"], "figure_sentence": None, "figures": [], "latest_year": 2019,
        "edited": False, "checks": {"numbers": [], "softened": 0, "recovered": 0}, "gen_id": 3}


def _gen(id, kind, status, **kw) -> SimpleNamespace:
    return SimpleNamespace(id=id, kind=kind, status=status, target=kw.get("target"), model=kw.get("model"),
                           input=kw.get("input") or {}, output=kw.get("output"),
                           finished_at=kw.get("finished_at"))


def _section(key, *, topic_id=12, papers=(), cites=(), evidence=None) -> dict:
    return {"key": key, "gen_id": 40, "evidence": evidence or {}, "figures": [],
            "basis": {"topic_id": topic_id, "papers": list(papers)}, "note": None,
            "paragraphs": [{"id": "p1", "text": "문단 [E1].", "state": "proposed", "cites": list(cites),
                            "checks": {}, "gen_id": 40}],
            "model": "gemma-3-12b", "updated_at": "2026-10-12T01:00:00+00:00"}


OUTLINE = {
    "topic": {"id": 12, "title": CARD["title"], "question": CARD["question"]}, "basis": "concept",
    "concepts": CONCEPTS,
    "groups": [{"key": "prior.g1", "name": "노년기 우울", "hint": "노인의 우울", "papers": ["C1", "C2"]},
               {"key": "prior.g2", "name": "지지망", "hint": "사회적 지지", "papers": ["C3"]}],
    "questions": ["가는 나인가?", "다는 라인가?"], "question": None, "method": "", "state": "draft",
    "gen_id": 7, "approved_at": None,
}


# ── 응답 모양(순수 함수) ──────────────────────────────────────────────


class TestStaleFlags:
    def test_nothing_changed(self):
        work = SimpleNamespace(topic_id=12, concepts=CONCEPTS)
        sections = {"prior.g1": _section("prior.g1", papers=["C2", "C1"]), "gap": _section("gap")}
        assert stale_flags(work, OUTLINE, sections, {"C1", "C2", "C3"}) == {
            "outline": False, "sections": {"prior.g1": False, "gap": False}}

    def test_reading_or_topic_or_group_changes_need_a_refit(self):
        sections = {"prior.g1": _section("prior.g1", papers=["C1"]),
                    "prior.g3": _section("prior.g3", papers=["C1"]), "gap": _section("gap")}
        flags = stale_flags(SimpleNamespace(topic_id=12, concepts=CONCEPTS), OUTLINE, sections,
                            {"C1", "C2", "C3", "C4"})
        # 담음이 늘었다 → 목차, 그 묶음 논문과 근거가 다르다 → prior.g1, 없는 묶음 → prior.g3
        assert flags == {"outline": True, "sections": {"prior.g1": True, "prior.g3": True, "gap": False}}
        other_topic = stale_flags(SimpleNamespace(topic_id=13, concepts=CONCEPTS), OUTLINE,
                                  {"gap": _section("gap")}, {"C1", "C2", "C3"})
        assert other_topic == {"outline": True, "sections": {"gap": True}}

    def test_changed_concepts_need_a_refit(self):
        # 묶음은 목차를 만들 때의 핵심 개념 소속으로 나눴다(정함 7) — 주제 화면에서 개념 칩을 고치면 목차를 다시 맞춘다
        work = SimpleNamespace(topic_id=12, concepts=["노인의 우울"])
        assert stale_flags(work, OUTLINE, {}, {"C1", "C2", "C3"}) == {"outline": True, "sections": {}}

    def test_same_topic_concepts_and_card_title_are_not_stale(self):
        work = SimpleNamespace(topic_id=12, concepts=list(CONCEPTS))
        # 카드 제목이 None(고른 카드를 읽지 못함)이면 제목은 견주지 않는다
        for title in (CARD["title"], None):
            assert stale_flags(work, OUTLINE, {}, {"C1", "C2", "C3"}, title) == {
                "outline": False, "sections": {}}

    def test_no_outline_is_not_stale(self):
        flags = stale_flags(SimpleNamespace(topic_id=None), {}, {}, set())
        assert flags == {"outline": False, "sections": {}}


class TestDisclosure:
    def test_done_steps_without_error_strings(self):
        at = datetime(2026, 10, 12, 1, 2, 3, tzinfo=timezone.utc)
        gens = [
            _gen(9, "outline", "done", target=OUTLINE_TARGET, model="gemma-3-12b", finished_at=at,
                 output={"attempts": [{"model": "gemma-3-12b", "outcome": "transport",
                                       "error": "ConnectError: http://10.0.0.5:18080"},
                                      {"model": "qwen3-vl-8b", "outcome": "ok"}]}),
            _gen(3, "concepts", "done", model="gemma-3-12b", finished_at=at,
                 output={"concepts": ["가"], "attempts": [{"model": "gemma-3-12b", "outcome": "ok"}]}),
            _gen(11, "section", "running", target="prior.g1"),
            _gen(5, "topic_card", "failed", target="4"),
        ]
        out = disclosure_of(gens)
        assert out == {"steps": [
            {"kind": "concepts", "target": None, "model": "gemma-3-12b", "finished_at": at.isoformat(),
             "attempts": [{"model": "gemma-3-12b", "outcome": "ok"}]},
            {"kind": "outline", "target": "outline", "model": "gemma-3-12b", "finished_at": at.isoformat(),
             "attempts": [{"model": "gemma-3-12b", "outcome": "transport"},
                          {"model": "qwen3-vl-8b", "outcome": "ok"}]},
        ]}
        assert "10.0.0.5" not in json.dumps(out)


class TestCitedAndDrafts:
    def test_cited_papers_follow_the_document_order(self):
        sections = {"gap": _section("gap", cites=["C9", "C1"]),
                    "prior.g2": _section("prior.g2", cites=["C3"]),
                    "prior.g1": _section("prior.g1", cites=["C1", "C2"])}
        assert cited_papers(sections) == ["C1", "C2", "C3", "C9"]

    def test_drafts_come_from_open_section_inputs(self):
        gen = _gen(52, "section", "running", target="prior.g2", input={
            "papers": [{"eid": "E1", "cnts_id": "C3"}, {"eid": "E2", "cnts_id": "C4"}],
            "figures": [{"id": "F1", "label": "이 절에 준 논문 수", "value": "2"}]})
        assert drafts_of([gen]) == {"prior.g2": {
            "gen_id": 52, "evidence": {"E1": "C3", "E2": "C4"},
            "figures": [{"id": "F1", "label": "이 절에 준 논문 수", "value": "2"}]}}

    def test_paper_ids_in_first_seen_order(self):
        proposal = SimpleNamespace(outline=OUTLINE, sections={"gap": _section("gap", evidence={"E1": "C7"})})
        gens = [_gen(52, "section", "queued", target="prior.g2",
                     input={"papers": [{"eid": "E1", "cnts_id": "C8"}]}),
                _gen(50, "section", "done", target="prior.g1",
                     input={"papers": [{"eid": "E1", "cnts_id": "C0"}]})]   # 끝난 절의 입력은 drafts 가 아니다
        assert paper_ids(proposal, gens) == ["C1", "C2", "C3", "C7", "C8"]
        assert paper_ids(None, []) == []


class TestProposalView:
    def test_no_proposal_yet(self):
        work = SimpleNamespace(topic_id=None, corpus_snapshot=None)
        job = SimpleNamespace(report={"range": {"from": "1980", "to": "2017", "n_papers": 144748}},
                              finished_at=None)
        view = proposal_view(work, job, None, {}, [], set())
        assert view == {"version": 0, "outline": None, "sections": {}, "drafts": {}, "papers": {},
                        "references": {}, "corpus": corpus_of(job),
                        "stale": {"outline": False, "sections": {}}, "disclosure": {"steps": []},
                        "topic_source": None}

    def test_references_use_build_citation_and_papers_use_the_catalog(self):
        book = SimpleNamespace(cnts_id="C1", title="노인 우울 연구", title_remainder=None,
                               personal_author="김철수|이영희", corporate_author=None, pub_date="2019",
                               series_title="노인복지연구", vol_issue="74(2)", uci="G704-1.2019.74.2.001",
                               url=None)
        snapshot = {"n_papers": 10, "from": "2000", "to": "2020", "at": "2026-10-10T00:00:00+00:00"}
        work = SimpleNamespace(topic_id=12, concepts=CONCEPTS, corpus_snapshot=snapshot)
        proposal = SimpleNamespace(version=3, outline=OUTLINE,
                                   sections={"prior.g1": _section("prior.g1", papers=["C1", "C2"],
                                                                  cites=["C1", "C2"])})
        view = proposal_view(work, SimpleNamespace(report={}), proposal, {"C1": book, "K9": None}, [],
                             {"C1", "C2", "C3"})
        assert view["version"] == 3 and view["outline"] == OUTLINE and view["corpus"] == snapshot
        assert view["references"] == {"C1": build_citation(book)["korean"],
                                      "C2": "서지 정보 없음 (C2)."}
        assert list(view["papers"]) == ["C1", "C2", "C3", "K9"]
        assert view["papers"]["C1"]["title"] == "노인 우울 연구"
        assert view["papers"]["C3"] == {"title": "C3", "personal_author": None, "pub_date": None,
                                        "series_title": None}


# ── API ─────────────────────────────────────────────────────────────


def _stub_missing(monkeypatch, name: str, module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module)


_CACHED = ("api.research_proposal", "api.research_work", "services.research.relay")


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """test_research_work_api.py 와 같은 방식 — 더미 redis 에 묶인 relay 가 다른 테스트로 새지 않게."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


class _Dispatch:
    def __init__(self):
        self.calls = 0

    def send_dispatch(self) -> bool:
        self.calls += 1
        return True


class _Affinity:
    """membership.concept_affinity 가짜 — 받은 인자를 남기고 정해 둔 값을 돌려준다."""
    def __init__(self, seen: list):
        self.seen = seen
        self.calls: list[tuple] = []
        self.result: dict | None = None

    def __call__(self, concepts, cnts_ids):
        self.seen.append(("AFFINITY", None))
        self.calls.append((list(concepts), list(cnts_ids)))
        return self.result


class _Api:
    def __init__(self, client, engine, router, events, dispatch, affinity, seen):
        self.client = client
        self.engine = engine
        self.router = router
        self.events = events
        self.dispatch = dispatch
        self.affinity = affinity
        self.seen = seen            # 엔진이 실행한 문장·COMMIT·친밀도 호출 순서


@pytest.fixture
def api(monkeypatch):
    for name in ("redis", "redis.asyncio"):
        _stub_missing(monkeypatch, name, MagicMock())
    _forget_on_teardown(monkeypatch, _CACHED)
    router = importlib.import_module("api.research_proposal")
    from core.deps import get_db

    events: list[tuple] = []

    async def _publish_work(work_id, kind, payload):
        events.append((str(work_id), kind, payload))

    monkeypatch.setattr(router, "publish_work", _publish_work)
    seen: list[tuple] = []
    affinity = _Affinity(seen)
    monkeypatch.setattr(router, "concept_affinity", affinity)
    dispatch = _Dispatch()
    worker = types.ModuleType("workers.research_work_tasks")
    worker.send_dispatch = dispatch.send_dispatch
    monkeypatch.setitem(sys.modules, "workers.research_work_tasks", worker)

    engine = make_engine()
    sa.event.listen(engine, "before_cursor_execute",
                    lambda conn, cur, stmt, params, ctx, many: seen.append((stmt, params)))
    sa.event.listen(engine, "commit", lambda conn: seen.append(("COMMIT", None)))

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
    return _Api(TestClient(app), engine, router, events, dispatch, affinity, seen)


RANKS = {"C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}


def _work_job(engine, *, picked=("C1", "C2", "C3", "C4", "C5"), topic: bool = True, **work) -> uuid.UUID:
    jid = add_research_job(engine, status="completed", stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == jid).values(
            question="노인의 우울과 사회적 지지에 관한 연구가 궁금해", plan=PLAN,
            report={"range": {"from": "1980", "to": "2017", "n_papers": 144748}},
        ))
    add_work(engine, jid, phase="reading", **work)
    for cnts_id in picked:
        subq = "0" if RANKS.get(cnts_id, 9) <= 3 else "1"
        add_reading(engine, jid, cnts_id, state="in",
                    origin_ref={"subq_idx": [int(subq)], "rank": {subq: RANKS.get(cnts_id, 9)}})
    add_reading(engine, jid, "C6", state="candidate", origin_ref={"subq_idx": [0], "rank": {"0": 6}})
    if topic:
        tid = add_topic(engine, jid, slot=1, card=CARD, state="picked")
        _set_work(engine, jid, topic_id=tid)
    return jid


def _set_work(engine, jid, **values) -> None:
    table = ResearchWork.__table__
    with engine.begin() as conn:
        conn.execute(sa.update(table).where(table.c.id == jid).values(**values))


def _work_row(engine, jid):
    table = ResearchWork.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table).where(table.c.id == jid)).mappings().one()


def _proposal(engine, jid):
    table = ResearchProposal.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table).where(table.c.work_id == jid)).mappings().one_or_none()


def _generations(engine, jid) -> list:
    table = ResearchGeneration.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table).where(table.c.work_id == jid)
                            .order_by(table.c.id)).mappings().all()


def _topic_id(engine, jid) -> int:
    return _work_row(engine, jid)["topic_id"]


class TestGetProposal:
    def test_before_any_outline(self, api):
        jid = _work_job(api.engine)

        res = api.client.get(f"/api/research/{jid}/proposal")

        assert res.status_code == 200 and res.headers["etag"] == "0"
        body = res.json()
        assert (body["version"], body["outline"], body["sections"]) == (0, None, {})
        assert body["corpus"]["n_papers"] == 144748           # 연구에 스냅숏이 없으면 출발 잡의 보고서 범위
        # 고른 카드의 근거 서지는 소장 목록에 있는 것만 싣는다
        assert body["papers"] == {}

    def test_view_with_outline_sections_drafts_and_disclosure(self, api):
        jid = _work_job(api.engine, concepts=CONCEPTS)
        add_book(api.engine, "C1", title="노인 우울 연구", personal_author="김철수", pub_date="2019",
                 series_title="노인복지연구", vol_issue="74(2)", uci="G704-1")
        outline = {**OUTLINE, "topic": {**OUTLINE["topic"], "id": _topic_id(api.engine, jid)},
                   "groups": [{**OUTLINE["groups"][0], "papers": ["C1", "C2", "C4", "C5"]},
                              OUTLINE["groups"][1]]}
        add_proposal(api.engine, jid, version=4, outline=outline, sections={
            "prior.g1": _section("prior.g1", topic_id=_topic_id(api.engine, jid),
                                 papers=["C1", "C2", "C4", "C5"], cites=["C1"], evidence={"E1": "C1"})})
        add_generation(api.engine, jid, kind="outline", status="done", target=OUTLINE_TARGET,
                       output={"attempts": [{"model": "gemma-3-12b", "outcome": "ok"}]})
        writing = add_generation(api.engine, jid, kind="section", status="running", target="prior.g2",
                                 input={"papers": [{"eid": "E1", "cnts_id": "C3"}], "figures": []})

        res = api.client.get(f"/api/research/{jid}/proposal")

        body = res.json()
        assert res.headers["etag"] == "4" and body["version"] == 4
        assert body["outline"]["groups"][0]["name"] == "노년기 우울"
        assert body["stale"] == {"outline": False, "sections": {"prior.g1": False}}
        assert body["drafts"] == {"prior.g2": {"gen_id": writing, "evidence": {"E1": "C3"}, "figures": []}}
        assert body["references"] == {"C1": "김철수 (2019). 노인 우울 연구. 노인복지연구, 74(2). UCI G704-1"}
        assert body["papers"]["C1"]["title"] == "노인 우울 연구"
        assert [s["kind"] for s in body["disclosure"]["steps"]] == ["outline"]
        assert body["disclosure"]["steps"][0]["attempts"] == [{"model": "gemma-3-12b", "outcome": "ok"}]
        # 공개 부록의 '주제:' 줄 재료 — 목차 topic.id 의 주제 행(라우터가 읽은 고른 주제)의 origin·card.edited
        assert body["topic_source"] == {"origin": "report_seed", "edited": False}

    def test_editing_the_picked_card_title_after_the_outline_needs_a_refit(self, api):
        # 목차를 만든 뒤 고른 카드를 [직접 고치기] 로 고쳤다 — 목차의 topic.title 은 고치기 전 제목으로 남고
        # 목차·Word 가 그 제목을 쓰므로 배지를 붙인다. 카드 제목은 라우터가 고른 주제 행에서 읽어 넘긴다
        def stale_with(outline_title: str) -> dict:
            jid = _work_job(api.engine, picked=("C1", "C2", "C3"), concepts=CONCEPTS)
            topic = {**OUTLINE["topic"], "id": _topic_id(api.engine, jid), "title": outline_title}
            add_proposal(api.engine, jid, outline={**OUTLINE, "topic": topic})
            return api.client.get(f"/api/research/{jid}/proposal").json()["stale"]

        assert stale_with(CARD["title"]) == {"outline": False, "sections": {}}
        assert stale_with("고치기 전 주제 제목") == {"outline": True, "sections": {}}

    def test_404_until_continued(self, api):
        jid = add_research_job(api.engine, status="completed", stage="synthesized")
        assert api.client.get(f"/api/research/{jid}/proposal").status_code == 404


AFFINITY = {"C1": {"노인의 우울": 0.9, "사회적 지지": 0.2}, "C2": {"노인의 우울": 0.8},
            "C3": {"사회적 지지": 0.7}, "C4": {"노인의 우울": 0.5, "사회적 지지": 0.46},
            "C5": {"사회적 지지": 0.3}}


class TestCreateOutline:
    def test_concept_basis(self, api):
        jid = _work_job(api.engine, concepts=["노인의 우울", "사회적 지지"])
        add_book(api.engine, "C1", title="노인 우울 연구", pub_date="2013")
        api.affinity.result = AFFINITY

        res = api.client.post(f"/api/research/{jid}/outline")

        assert res.status_code == 200
        (gen,) = _generations(api.engine, jid)
        assert res.json() == {"gen_id": gen["id"]}
        assert (gen["kind"], gen["target"], gen["status"], gen["priority"]) == ("outline", OUTLINE_TARGET,
                                                                               "queued", 10)
        assert api.affinity.calls == [(["노인의 우울", "사회적 지지"], ["C1", "C2", "C3", "C4", "C5"])]
        inp = gen["input"]
        assert inp["basis"] == "concept" and inp["concepts"] == ["노인의 우울", "사회적 지지"]
        assert inp["topic"] == {"id": _topic_id(api.engine, jid), "title": CARD["title"],
                                "question": CARD["question"]}
        # 5편 → 묶음 1개(4편당 1개) — 1순위가 가장 많은 개념이 묶음 이름의 실마리가 된다
        assert [(g["key"], g["hint"], [p["cnts_id"] for p in g["papers"]]) for g in inp["groups"]] == [
            ("prior.g1", "노인의 우울", ["C1", "C2", "C3", "C4", "C5"])]
        assert inp["groups"][0]["papers"][0] == {"eid": "E1", "cnts_id": "C1", "title": "노인 우울 연구",
                                                 "year": 2013}
        work = _work_row(api.engine, jid)
        assert work["concept_members"] == {"노인의 우울": ["C1", "C2", "C4"], "사회적 지지": ["C3", "C4"]}
        assert work["phase"] == "proposal"
        prop = _proposal(api.engine, jid)
        assert (prop["version"], prop["outline"], prop["sections"]) == (1, {}, {})
        assert api.dispatch.calls == 1
        assert api.events[0] == (str(jid), "generation", {
            "gen_id": gen["id"], "gen_kind": "outline", "target": OUTLINE_TARGET, "status": "queued",
            "model": None, "result": None})
        assert api.events[1][1] == "work" and api.events[1][2]["phase"] == "proposal"

    def test_the_read_transaction_is_closed_before_the_affinity_runs(self, api):
        # 함정 18 — 임베딩·Milvus 를 기다리는 동안 세션(트랜잭션)을 쥐지 않는다
        jid = _work_job(api.engine, concepts=["노인의 우울", "사회적 지지"])
        api.affinity.result = AFFINITY
        api.seen.clear()

        assert api.client.post(f"/api/research/{jid}/outline").status_code == 200

        at = api.seen.index(("AFFINITY", None))
        assert api.seen[at - 1] == ("COMMIT", None)
        assert any(s.startswith("SELECT") for s, _ in api.seen[:at])
        assert any(s.startswith("INSERT INTO research_generations") for s, _ in api.seen[at:])

    def test_falls_back_to_subquestions_when_the_affinity_fails(self, api):
        jid = _work_job(api.engine, concepts=["노인의 우울", "사회적 지지"],
                        picked=("C1", "C2", "C3", "C4", "C5", "C7", "C8", "C9"))
        _set_work(api.engine, jid, concept_members={"옛": ["C1"]})
        api.affinity.result = None

        assert api.client.post(f"/api/research/{jid}/outline").status_code == 200

        (gen,) = _generations(api.engine, jid)
        inp = gen["input"]
        # 8편 → 묶음 2개. C1~C3 은 하위질문 0, 나머지는 하위질문 1 의 순위
        assert inp["basis"] == "subq"
        assert [(g["hint"], [p["cnts_id"] for p in g["papers"]]) for g in inp["groups"]] == [
            (PLAN[1], ["C4", "C5", "C7", "C8", "C9"]), (PLAN[0], ["C1", "C2", "C3"])]
        assert [p["eid"] for g in inp["groups"] for p in g["papers"]] == [f"E{i}" for i in range(1, 9)]
        assert _work_row(api.engine, jid)["concept_members"] == {"옛": ["C1"]}

    def test_no_concepts_skip_the_affinity(self, api):
        jid = _work_job(api.engine)
        assert api.client.post(f"/api/research/{jid}/outline").status_code == 200
        assert api.affinity.calls == []
        assert _generations(api.engine, jid)[0]["input"]["basis"] == "subq"

    def test_an_existing_proposal_keeps_its_version_and_phase_never_goes_back(self, api):
        jid = _work_job(api.engine)
        add_proposal(api.engine, jid, version=7, outline=OUTLINE)
        _set_work(api.engine, jid, phase="done")

        assert api.client.post(f"/api/research/{jid}/outline").status_code == 200

        assert _proposal(api.engine, jid)["version"] == 7
        assert _work_row(api.engine, jid)["phase"] == "done"
        assert [e[1] for e in api.events] == ["generation"]

    def test_topic_must_be_picked(self, api):
        jid = _work_job(api.engine, topic=False)
        res = api.client.post(f"/api/research/{jid}/outline")
        assert res.status_code == 409 and res.json()["detail"] == api.router.PICK_TOPIC_FIRST
        assert _generations(api.engine, jid) == []

    def test_five_picked_papers_are_needed(self, api):
        jid = _work_job(api.engine, picked=("C1", "C2", "C3", "C4"))
        res = api.client.post(f"/api/research/{jid}/outline")
        assert res.status_code == 409 and res.json()["detail"] == "담은 논문이 5편 이상이어야 목차를 만듭니다"
        assert api.affinity.calls == []

    def test_second_request_while_one_is_open_is_409(self, api):
        jid = _work_job(api.engine)
        assert api.client.post(f"/api/research/{jid}/outline").status_code == 200
        res = api.client.post(f"/api/research/{jid}/outline")
        assert res.status_code == 409 and res.json()["detail"] == api.router.OUTLINE_BUSY
        assert len(_generations(api.engine, jid)) == 1 and api.dispatch.calls == 1

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        assert api.client.post(f"/api/research/{jid}/outline").status_code == 409
        assert _generations(api.engine, jid) == []


def _put_body(**over) -> dict:
    body = {"groups": [{"key": "prior.g1", "name": "노년기 우울", "papers": ["C1", "C2"]},
                       {"key": "prior.g2", "name": "지지망", "papers": ["C3"]}],
            "question": "사회적 지지는 노인의 우울을 낮추는가?", "method": "설문 조사", "approve": False}
    return {**body, **over}


def _with_outline(api, *, version=2, picked=("C1", "C2", "C3", "C4", "C5")) -> uuid.UUID:
    jid = _work_job(api.engine, picked=picked)
    outline = {**OUTLINE, "topic": {**OUTLINE["topic"], "id": _topic_id(api.engine, jid)}}
    add_proposal(api.engine, jid, version=version, outline=outline)
    return jid


class TestPutOutline:
    def test_moving_a_paper_and_approving(self, api):
        jid = _with_outline(api)
        body = _put_body(groups=[{"key": "prior.g1", "name": " 노년기   우울 ", "papers": ["C1"]},
                                 {"key": "prior.g2", "name": "지지망", "papers": ["C3", "C2"]}],
                         approve=True)

        res = api.client.put(f"/api/research/{jid}/outline", json=body, headers={"If-Match": "2"})

        assert res.status_code == 200 and res.headers["etag"] == "3"
        out = res.json()["outline"]
        assert [(g["name"], g["hint"], g["papers"]) for g in out["groups"]] == [
            ("노년기 우울", "노인의 우울", ["C1"]), ("지지망", "사회적 지지", ["C3", "C2"])]
        assert (out["state"], out["question"], out["method"]) == (
            "approved", "사회적 지지는 노인의 우울을 낮추는가?", "설문 조사")
        assert out["approved_at"] is not None and out["questions"] == OUTLINE["questions"]
        assert _proposal(api.engine, jid)["version"] == 3
        assert api.events[-1][1] == "work"

    def test_saving_without_approval_is_a_draft(self, api):
        jid = _with_outline(api)
        api.client.put(f"/api/research/{jid}/outline", json=_put_body(approve=True),
                       headers={"If-Match": "2"})

        res = api.client.put(f"/api/research/{jid}/outline", json=_put_body(question=""),
                             headers={"If-Match": '"3"'})

        out = res.json()["outline"]
        assert (out["state"], out["question"], out["approved_at"]) == ("draft", None, None)
        assert res.headers["etag"] == "4"

    def test_weak_etag_is_read(self, api):
        jid = _with_outline(api)
        res = api.client.put(f"/api/research/{jid}/outline", json=_put_body(), headers={"If-Match": 'W/"2"'})
        assert res.status_code == 200

    def test_missing_if_match_is_428(self, api):
        jid = _with_outline(api)
        res = api.client.put(f"/api/research/{jid}/outline", json=_put_body())
        assert res.status_code == 428 and res.json()["detail"] == api.router.IF_MATCH_REQUIRED

    def test_non_numeric_if_match_is_422(self, api):
        jid = _with_outline(api)
        assert api.client.put(f"/api/research/{jid}/outline", json=_put_body(),
                              headers={"If-Match": "abc"}).status_code == 422

    def test_stale_version_is_409_with_the_current_version(self, api):
        jid = _with_outline(api, version=5)

        res = api.client.put(f"/api/research/{jid}/outline", json=_put_body(), headers={"If-Match": "4"})

        assert res.status_code == 409
        assert res.json()["detail"] == {"code": "version_conflict", "version": 5,
                                        "message": api.router.VERSION_CONFLICT}
        assert _proposal(api.engine, jid)["version"] == 5 and api.events == []

    def test_409_while_the_outline_is_being_made(self, api):
        jid = _with_outline(api)
        add_generation(api.engine, jid, kind="outline", status="running", target=OUTLINE_TARGET)
        res = api.client.put(f"/api/research/{jid}/outline", json=_put_body(), headers={"If-Match": "2"})
        assert res.status_code == 409 and res.json()["detail"] == api.router.OUTLINE_BUSY

    def test_no_outline_is_404(self, api):
        jid = _work_job(api.engine)
        res = api.client.put(f"/api/research/{jid}/outline", json=_put_body(), headers={"If-Match": "0"})
        assert res.status_code == 404 and res.json()["detail"] == api.router.NO_OUTLINE

    @pytest.mark.parametrize("groups, detail", [
        ([{"key": "prior.g2", "name": "가", "papers": ["C3"]},
          {"key": "prior.g1", "name": "나", "papers": ["C1", "C2"]}], "GROUP_KEYS_DIFFER"),
        ([{"key": "prior.g1", "name": "가", "papers": ["C1", "C2", "C3"]},
          {"key": "prior.g2", "name": "나", "papers": ["C3"]}], "PAPER_IN_TWO_GROUPS"),
        ([{"key": "prior.g1", "name": "가", "papers": ["C1", "C2", "C3"]},
          {"key": "prior.g2", "name": "나", "papers": []}], "EMPTY_GROUP"),
        ([{"key": "prior.g1", "name": "가", "papers": ["C1", "C9"]},
          {"key": "prior.g2", "name": "나", "papers": ["C3"]}], "GROUP_PAPERS_DIFFER"),
        ([{"key": "prior.g1", "name": "   ", "papers": ["C1", "C2"]},
          {"key": "prior.g2", "name": "나", "papers": ["C3"]}], "EMPTY_GROUP_NAME"),
    ])
    def test_group_rules_are_422(self, api, groups, detail):
        jid = _with_outline(api)
        res = api.client.put(f"/api/research/{jid}/outline", json=_put_body(groups=groups),
                             headers={"If-Match": "2"})
        assert res.status_code == 422 and res.json()["detail"] == getattr(api.router, detail)
        assert _proposal(api.engine, jid)["version"] == 2

    def test_approve_needs_a_question(self, api):
        jid = _with_outline(api)
        res = api.client.put(f"/api/research/{jid}/outline", json=_put_body(question=" 가 ", approve=True),
                             headers={"If-Match": "2"})
        assert res.status_code == 422 and res.json()["detail"] == api.router.APPROVE_NEEDS_QUESTION

    @pytest.mark.parametrize("over", [
        {"question": "가" * 301}, {"method": "가" * 1001}, {"approve": None},
        {"groups": [{"key": "prior.g1", "name": "가" * 61, "papers": ["C1"]}]},
    ])
    def test_body_limits_are_422(self, api, over):
        jid = _with_outline(api)
        assert api.client.put(f"/api/research/{jid}/outline", json=_put_body(**over),
                              headers={"If-Match": "2"}).status_code == 422

    def test_example_work_is_read_only(self, api):
        jid = _with_outline(api)
        _set_work(api.engine, jid, is_example=True)
        assert api.client.put(f"/api/research/{jid}/outline", json=_put_body(),
                              headers={"If-Match": "2"}).status_code == 409


class TestAppWiring:
    def test_main_includes_the_proposal_router_after_the_reading_router(self):
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
        assert ("api.research_proposal", "router", "research_proposal_router") in imported
        assert included.index("research_reading_router") < included.index("research_proposal_router")
