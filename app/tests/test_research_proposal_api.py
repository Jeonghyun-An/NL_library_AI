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
from models.research_work import PRIORITY_USER, ResearchGeneration, ResearchProposal, ResearchWork
from schemas.book import BookOut
from services.research_work import section_input
from services.research_work.enqueue import queued_event
from services.research_work.proposal_views import (
    cited_papers, disclosure_of, drafts_of, paper_ids, proposal_view, stale_flags,
)
from services.research_work.seeds import corpus_of
from services.research_work.shapes import MAX_PARAGRAPHS_PUT, OUTLINE_TARGET
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

    def test_the_proposal_row_is_locked_before_the_work_row(self, api):
        """잠금 순서 계획서 행 → 연구 행(워커의 절·목차 반영과 같다). 목차가 있을 때 [목차 다시 만들기]의 ON CONFLICT
        검사는 계획서 행을 고치는 중인 워커를 기다리고, 워커는 refresh_progress 에서 연구 행을 기다린다 — 연구 행을
        먼저 쥐면(concept_members UPDATE, 생성 행 INSERT 의 외래 키 FOR KEY SHARE) 교착이다."""
        jid = _work_job(api.engine, concepts=["노인의 우울", "사회적 지지"])
        add_proposal(api.engine, jid, version=7, outline=OUTLINE)
        api.affinity.result = AFFINITY
        api.seen.clear()

        assert api.client.post(f"/api/research/{jid}/outline").status_code == 200

        writes = [s.split("(")[0].split(" SET")[0].strip() for s, _ in api.seen[api.seen.index(("AFFINITY", None)):]
                  if s.startswith(("INSERT", "UPDATE"))]
        assert writes[:2] == ["INSERT INTO research_proposals", "INSERT INTO research_generations"]
        assert writes.count("UPDATE research_works") >= 2          # concept_members·phase(그 뒤 진행 요약)
        assert _proposal(api.engine, jid)["version"] == 7

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


# ── 절 쓰기·고치기 (Task 19) ─────────────────────────────────────────────

SEC_QUESTION = "노인의 우울과 사회적 지지에 관한 연구가 궁금해"
SEC_TOPIC = {"id": None, "title": "농촌 독거노인의 사회적 지지와 우울", "question": "어떤 지지가 우울을 낮추는가?"}
SEC_SNAPSHOT = {"evidence": {"E3": {"cnts_id": "KCI_A", "meta": {}, "chunks": [
    {"chunk_id": "KCI_A__0004", "text": "스냅숏 대목", "page_start": 4, "page_end": 4, "score": 0.8}]}}}
SEC_REPORT = {"question": SEC_QUESTION, "range": {"from": "1980", "to": "2017", "n_papers": 144748},
              "sections": [], "evidence": {}, "trail": []}
SEC_SEED = {"key": "future:1:0", "kind": "future", "section_idx": 1, "subq_idx": 1, "heading": "노인의 사회적 지지",
            "text": "농촌 노인 표본이 부족하다", "papers": ["KCI_A", "KCI_D"], "adopted": 9}
SEC_BOOKS = {
    cnts: BookOut(id=uuid.uuid4(), cnts_id=cnts, created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                  title=title, pub_date=year, abstract=f"{title} 초록")
    for cnts, title, year in (("KCI_A", "노인 우울과 가족 지지", "2013"), ("KCI_B", "사회적 지지 척도", "2015"),
                              ("KCI_C", "독거 노인", "2016"), ("KCI_D", "농촌 노인", "2011"))
}


class _SecBooks:
    """BookRepository 대역 — 서지는 라우터의 BookRepository 를 대역으로 고정한다(Task 12 의 add_book 도 있지만 BookOut 필드를
    그대로 두려고 — 계약 보강 6)."""

    def __init__(self, db):
        pass

    async def get_by_cnts_ids(self, cnts_ids):
        return {c: SEC_BOOKS[c] for c in cnts_ids if c in SEC_BOOKS}


def _sec_outline(topic_id: int, *, state: str = "approved") -> dict:
    return {"topic": {**SEC_TOPIC, "id": topic_id}, "basis": "concept",
            "groups": [{"key": "prior.g1", "name": "가족 지지와 우울", "hint": "노인의 우울",
                        "papers": ["KCI_A", "KCI_B", "KCI_C"]}],
            "questions": ["가족 지지는 우울을 낮추는가?"], "question": "가족 지지는 농촌 독거노인의 우울을 낮추는가?",
            "method": "", "state": state, "gen_id": 1, "approved_at": None}


def _sec_work(engine, *, state: str = "approved", seed: dict | None = None, sections: dict | None = None,
              version: int = 3, is_example: bool = False, proposal: bool = True) -> uuid.UUID:
    """목차까지 온 연구 — 완료 잡(질문·보고서·스냅숏) + 연구(phase proposal·고른 주제·코퍼스) + 주제 + 계획서."""
    jid = add_research_job(engine, status="completed", stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == jid).values(
            question=SEC_QUESTION, report=SEC_REPORT, state_snapshot=SEC_SNAPSHOT))
    add_work(engine, jid, phase="proposal", is_example=is_example)
    tid = add_topic(engine, jid, slot=1, seed=SEC_SEED if seed is None else seed,
                    card={"title": SEC_TOPIC["title"]}, state="picked")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchWork.__table__).where(ResearchWork.__table__.c.id == jid).values(
            topic_id=tid, corpus_snapshot={"n_papers": 144748, "from": "1980", "to": "2017", "at": None}))
    if proposal:
        add_proposal(engine, jid, version=version, outline=_sec_outline(tid, state=state), sections=sections)
    return jid


def _sec_gens(engine, jid) -> list:
    with engine.connect() as conn:
        return conn.execute(sa.select(ResearchGeneration.__table__)
                            .where(ResearchGeneration.__table__.c.work_id == jid)
                            .order_by(ResearchGeneration.__table__.c.id)).mappings().all()


def _sec_proposal(engine, jid):
    with engine.connect() as conn:
        return conn.execute(sa.select(ResearchProposal.__table__)
                            .where(ResearchProposal.__table__.c.work_id == jid)).mappings().one()


@pytest.fixture
def sec_books(api, monkeypatch):
    """서지 조회를 라우터 모듈에서 바꾼다(절 쓰기·계획서 조회가 읽는다) — 서지는 라우터의 BookRepository 를 대역으로 고정한다
    (Task 12 의 add_book 도 있지만 BookOut 필드를 그대로 두려고 — 계약 보강 6)."""
    monkeypatch.setattr(api.router, "BookRepository", _SecBooks, raising=False)


@pytest.fixture
def heavy(api, sec_books, monkeypatch):
    """대목 고르기의 무거운 함수(리랭커·Milvus)를 라우터 모듈에서 바꾼다 — 부른 순서를 남긴다."""
    calls = []

    def _milvus(cnts_id):
        calls.append(("milvus", cnts_id))
        return [{"chunk_id": f"{cnts_id}__0001", "text": f"{cnts_id} 대목", "page_start": 1, "page_end": 1,
                 "score": None}]

    def _pick(query, passages):
        calls.append(("pick", query, [p["chunk_id"] for p in passages]))
        best = passages[0]
        return {"chunk_id": best["chunk_id"], "page_start": best["page_start"], "page_end": best["page_end"],
                "text": best["text"]}

    monkeypatch.setattr(api.router, "milvus_passages", _milvus)
    monkeypatch.setattr(api.router, "pick_excerpt", _pick)
    return calls


class TestGenerateSection:
    def test_prior_group_is_queued_with_the_built_input(self, api, heavy):
        jid = _sec_work(api.engine)

        res = api.client.post(f"/api/research/{jid}/sections/prior.g1/generate")

        assert res.status_code == 200
        (gen,) = _sec_gens(api.engine, jid)
        assert res.json() == {"gen_id": gen["id"]}
        assert (gen["kind"], gen["target"], gen["status"], gen["priority"]) == (
            "section", "prior.g1", "queued", PRIORITY_USER)
        inp = gen["input"]
        assert (inp["key"], inp["kind"], inp["question"]) == ("prior.g1", "prior", SEC_QUESTION)
        assert inp["research_question"] == "가족 지지는 농촌 독거노인의 우울을 낮추는가?"
        assert inp["group"] == {"name": "가족 지지와 우울"}
        assert [(p["eid"], p["cnts_id"], p["year"]) for p in inp["papers"]] == [
            ("E1", "KCI_A", 2013), ("E2", "KCI_B", 2015), ("E3", "KCI_C", 2016)]
        # 스냅숏에 있는 논문은 스냅숏 대목, 없는 논문만 Milvus 에서 읽는다
        assert inp["papers"][0]["excerpt"]["chunk_id"] == "KCI_A__0004"
        assert inp["papers"][1]["excerpt"]["chunk_id"] == "KCI_B__0001"
        assert [c[1] for c in heavy if c[0] == "milvus"] == ["KCI_B", "KCI_C"]
        assert {c[1] for c in heavy if c[0] == "pick"} == {"가족 지지와 우울 가족 지지는 농촌 독거노인의 우울을 낮추는가?"}
        assert [f["value"] for f in inp["figures"]] == ["3", "2013~2016", "144,748"]
        assert inp["basis"]["papers"] == ["KCI_A", "KCI_B", "KCI_C"]
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "generation", queued_event(gen["id"], "section", "prior.g1"))]

    def test_a_big_group_puts_its_six_best_ranked_papers_in_the_input(self, api, heavy):
        """spec §5-5 — 6편을 넘는 묶음은 하위질문 안 순위 → 담은 순서로 6편. 목차 편집으로 7편 묶음 끝에 옮겨 붙은 순위
        1위 논문도 입력에 들어가고, 담음에서 빠진 논문은 뒤로 간다(저장 순서의 앞 6편이 아니다)."""
        jid = _sec_work(api.engine)
        for rank, cnts in enumerate(("P1", "P2", "P3", "P4", "P5", "P6", "P7"), start=1):
            add_reading(api.engine, jid, cnts, state="in", origin_ref={"subq_idx": [0], "rank": {"0": rank}})
        outline = _sec_outline(_work_row(api.engine, jid)["topic_id"])
        outline["groups"][0]["papers"] = ["OUT", "P2", "P3", "P4", "P5", "P6", "P7", "P1"]   # OUT 은 담음에 없다
        with api.engine.begin() as conn:
            conn.execute(sa.update(ResearchProposal.__table__)
                         .where(ResearchProposal.__table__.c.work_id == jid).values(outline=outline))

        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/generate").status_code == 200

        inp = _sec_gens(api.engine, jid)[0]["input"]
        assert [p["cnts_id"] for p in inp["papers"]] == ["P1", "P2", "P3", "P4", "P5", "P6"]
        assert set(inp["basis"]["papers"]) == set(outline["groups"][0]["papers"])
        stored = _sec_proposal(api.engine, jid)["outline"]["groups"][0]["papers"]
        assert stored == outline["groups"][0]["papers"]                          # 저장된 목차는 그대로

    def test_gap_uses_the_picked_card_seed_and_its_papers(self, api, heavy, monkeypatch):
        monkeypatch.setattr(section_input, "pick_seeds", lambda report, *, limit, exclude=(): [])
        jid = _sec_work(api.engine)

        assert api.client.post(f"/api/research/{jid}/sections/gap/generate").status_code == 200

        inp = _sec_gens(api.engine, jid)[0]["input"]
        assert (inp["key"], inp["kind"], inp["group"]) == ("gap", "gap", None)
        assert inp["seeds"] == [{"heading": "노인의 사회적 지지", "text": "농촌 노인 표본이 부족하다"}]
        assert [p["cnts_id"] for p in inp["papers"]] == ["KCI_A", "KCI_D"]
        assert {c[1] for c in heavy if c[0] == "pick"} == {
            "가족 지지는 농촌 독거노인의 우울을 낮추는가? 농촌 노인 표본이 부족하다"}

    def test_gap_seeds_come_from_the_outline_topic_after_the_topic_changes(self, api, heavy, monkeypatch):
        """목차를 승인한 뒤 주제를 바꿔도 씨앗·주제 제목·연구 질문·basis 가 모두 목차의 주제 기준이다 — 새 주제의 씨앗과
        옛 주제의 제목·질문이 섞인 절을 쓰지 않는다(바뀐 것은 목차의 '다시 맞춤 필요'가 알린다)."""
        monkeypatch.setattr(section_input, "pick_seeds", lambda report, *, limit, exclude=(): [])
        jid = _sec_work(api.engine)
        outline_topic = _work_row(api.engine, jid)["topic_id"]
        other_seed = {**SEC_SEED, "key": "future:2:0", "heading": "다른 절", "text": "도시 노인을 따로 볼 필요가 있다",
                      "papers": ["KCI_B", "KCI_C"]}
        other = add_topic(api.engine, jid, slot=2, seed=other_seed, card={"title": "도시 노인의 지지"}, state="picked")
        _set_work(api.engine, jid, topic_id=other)

        assert api.client.post(f"/api/research/{jid}/sections/gap/generate").status_code == 200

        inp = _sec_gens(api.engine, jid)[0]["input"]
        assert inp["seeds"] == [{"heading": "노인의 사회적 지지", "text": "농촌 노인 표본이 부족하다"}]
        assert [p["cnts_id"] for p in inp["papers"]] == ["KCI_A", "KCI_D"]
        assert inp["topic"] == {"id": outline_topic, "title": SEC_TOPIC["title"]}
        assert inp["basis"]["topic_id"] == outline_topic

    def test_gap_of_a_user_card_takes_seeds_from_the_report(self, api, heavy, monkeypatch):
        asked = []

        def _pick(report, *, limit, exclude=()):
            asked.append((report["question"], limit))
            return [{**SEC_SEED, "key": "future:0:0", "papers": ["KCI_C"]}]

        monkeypatch.setattr(section_input, "pick_seeds", _pick)
        jid = _sec_work(api.engine, seed={})

        assert api.client.post(f"/api/research/{jid}/sections/gap/generate").status_code == 200

        assert asked == [(SEC_QUESTION, 3)]
        assert [p["cnts_id"] for p in _sec_gens(api.engine, jid)[0]["input"]["papers"]] == ["KCI_C"]

    def test_gap_without_any_seed_paper_is_409(self, api, heavy, monkeypatch):
        monkeypatch.setattr(section_input, "pick_seeds", lambda report, *, limit, exclude=(): [])
        jid = _sec_work(api.engine, seed={})

        res = api.client.post(f"/api/research/{jid}/sections/gap/generate")

        assert (res.status_code, res.json()["detail"]) == (409, "이 절에 넣을 논문이 없습니다")
        assert _sec_gens(api.engine, jid) == []

    @pytest.mark.parametrize("key", ["background", "prior.g5", "topic"])
    def test_sections_06b_does_not_write_are_422(self, api, heavy, key):
        jid = _sec_work(api.engine)
        res = api.client.post(f"/api/research/{jid}/sections/{key}/generate")
        assert (res.status_code, res.json()["detail"]) == (422, "이 절은 아직 쓸 수 없습니다")

    @pytest.mark.parametrize("state, proposal", [("draft", True), ("approved", False)])
    def test_outline_must_be_approved(self, api, heavy, state, proposal):
        jid = _sec_work(api.engine, state=state, proposal=proposal)
        res = api.client.post(f"/api/research/{jid}/sections/prior.g1/generate")
        assert (res.status_code, res.json()["detail"]) == (409, "목차를 먼저 승인하세요")

    def test_group_missing_from_the_outline_is_404(self, api, heavy):
        jid = _sec_work(api.engine)
        res = api.client.post(f"/api/research/{jid}/sections/prior.g2/generate")
        assert (res.status_code, res.json()["detail"]) == (404, "묶음이 없습니다")

    @pytest.mark.parametrize("kind, target, status", [
        ("section", "prior.g1", "queued"), ("section", "prior.g1", "running"),
        ("paragraph", "prior.g1#p2", "queued"), ("paragraph", "prior.g1#p1", "running"),
    ])
    def test_section_being_written_is_409(self, api, heavy, kind, target, status):
        jid = _sec_work(api.engine)
        add_generation(api.engine, jid, kind=kind, status=status, target=target)

        res = api.client.post(f"/api/research/{jid}/sections/prior.g1/generate")

        assert (res.status_code, res.json()["detail"]) == (409, "이 절을 쓰는 중입니다")
        assert len(_sec_gens(api.engine, jid)) == 1 and heavy == []

    def test_other_sections_being_written_do_not_block(self, api, heavy):
        jid = _sec_work(api.engine)
        add_generation(api.engine, jid, kind="section", status="running", target="prior.g2")
        add_generation(api.engine, jid, kind="paragraph", status="queued", target="gap#p1")
        add_generation(api.engine, jid, kind="section", status="done", target="prior.g1")

        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/generate").status_code == 200

    def test_reads_are_committed_before_the_reranker_runs(self, api, heavy, monkeypatch):
        """서지·스냅숏을 읽은 트랜잭션을 쥔 채 리랭커·Milvus(수 초)를 기다리지 않는다(함정 18) — 읽기 커밋 →
        대목 고르기 → 생성 넣기 → 커밋 순서."""
        jid = _sec_work(api.engine)
        order = []
        sa.event.listen(api.engine, "commit", lambda conn: order.append("COMMIT"))
        sa.event.listen(api.engine, "before_cursor_execute",
                        lambda conn, cur, stmt, params, ctx, many:
                        order.append("INSERT") if stmt.startswith("INSERT INTO research_generations") else None)
        pick = api.router.pick_excerpt

        def _pick(query, passages):
            order.append("PICK")
            return pick(query, passages)

        monkeypatch.setattr(api.router, "pick_excerpt", _pick)

        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/generate").status_code == 200

        first_pick = order.index("PICK")
        assert "COMMIT" in order[:first_pick]
        assert order[first_pick:].index("INSERT") < order[first_pick:].index("COMMIT")

    def test_example_work_is_read_only(self, api, heavy):
        jid = _sec_work(api.engine, is_example=True)
        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/generate").status_code == 409


def _para(pid: str, text: str, state: str) -> dict:
    return {"id": pid, "text": text, "state": state, "cites": [], "checks": {}, "gen_id": 41}


SEC_STORED = {
    "key": "prior.g1", "gen_id": 41, "evidence": {"E1": "KCI_A", "E2": "KCI_B"},
    "figures": [{"id": "F1", "label": "이 절에 준 논문 수", "value": "2"}],
    "basis": {"topic_id": 1, "papers": ["KCI_A", "KCI_B"]}, "note": None,
    "paragraphs": [_para("p1", "가족 지지가 우울을 낮춘다 [E1].", "proposed"),
                   _para("p2", "척도가 정리되었다 [E2].", "accepted"),
                   _para("p3", "사용자가 고친 문단 [E1].", "edited")],
    "model": None, "updated_at": "2026-10-12T01:00:00+00:00",
}


def _put(api, jid, paragraphs, *, version: int | str | None = 3, key: str = "prior.g1"):
    headers = {} if version is None else {"If-Match": str(version)}
    return api.client.put(f"/api/research/{jid}/sections/{key}", json={"paragraphs": paragraphs},
                          headers=headers)


@pytest.mark.usefixtures("sec_books")
class TestPutSection:
    def test_states_are_decided_by_the_server_and_text_is_checked_again(self, api):
        jid = _sec_work(api.engine, sections={"prior.g1": SEC_STORED})

        res = _put(api, jid, [
            {"id": "p2", "text": "척도가 정리되었다 [E2].", "state": "proposed"},          # 수락 취소
            {"id": "p1", "text": "가족 지지가 우울을 낮춘다고 보고되었다 [E1].", "state": "accepted"},  # 글이 바뀜
            {"id": None, "text": "  사용자 문단이다 [E2] [E9]. 표본은 300명이다.  ", "state": "proposed"},
        ])

        assert res.status_code == 200
        assert res.headers["etag"] == "4" and res.json()["version"] == 4
        written = _sec_proposal(api.engine, jid)["sections"]["prior.g1"]
        assert [(p["id"], p["state"]) for p in written["paragraphs"]] == [
            ("p2", "proposed"), ("p1", "edited"), ("p4", "authored")]
        new = written["paragraphs"][2]
        assert new["text"] == "사용자 문단이다 [E2]. 표본은 300명이다."      # 입력에 없는 [E9] 는 지운다
        assert new["cites"] == ["KCI_B"] and new["checks"]["dropped"] == 1
        assert new["checks"]["numbers"] == ["300"] and new["gen_id"] is None
        assert written["paragraphs"][1]["cites"] == ["KCI_A"] and written["paragraphs"][1]["gen_id"] == 41
        assert written["evidence"] == SEC_STORED["evidence"] and written["updated_at"] != SEC_STORED["updated_at"]
        assert _sec_proposal(api.engine, jid)["version"] == 4
        (event,) = [e for e in api.events if e[1] == "work"]
        assert event[2]["phase"] == "proposal" and event[2]["progress"]["sections_total"] == 6

    def test_user_written_paragraph_stays_user_written(self, api):
        stored = {**SEC_STORED, "paragraphs": [_para("p1", "내가 쓴 문단 [E1].", "authored")]}
        jid = _sec_work(api.engine, sections={"prior.g1": stored})

        _put(api, jid, [{"id": "p1", "text": "내가 다시 쓴 문단 [E1].", "state": "accepted"}])

        (p,) = _sec_proposal(api.engine, jid)["sections"]["prior.g1"]["paragraphs"]
        assert (p["state"], p["text"]) == ("authored", "내가 다시 쓴 문단 [E1].")

    def test_state_only_put_keeps_the_stored_checks_of_other_paragraphs(self, api):
        """화면은 늘 절 전체를 PUT 한다 — p2 하나만 수락해도 손대지 않은 '검토 전' p1 은 다시 검사하지 않고 생성 때 센
        checks('인용 1개 버림·수치 표기 1개 버림·단정 표현 1곳 고침')를 그대로 지킨다. 이미 정리된 글을 다시 검사하면
        0 으로 덮여 사용자가 수락하기 전에 볼 근거가 사라진다."""
        generated = {"dropped": 1, "dropped_f": 1, "unmarked": 0, "numbers": [], "softened": 1}
        p1 = {**_para("p1", "관련 연구를 소장 코퍼스에서 확인하지 못했다 [E1].", "proposed"),
              "cites": ["KCI_A"], "checks": generated}
        p2 = {**_para("p2", "척도가 정리되었다 [E2].", "proposed"), "cites": ["KCI_B"],
              "checks": {**generated, "dropped_f": 0, "softened": 0}}
        jid = _sec_work(api.engine, sections={"prior.g1": {**SEC_STORED, "paragraphs": [p1, p2]}})

        res = _put(api, jid, [{"id": "p1", "text": p1["text"], "state": "proposed"},
                              {"id": "p2", "text": p2["text"], "state": "accepted"}])

        assert res.status_code == 200
        written = _sec_proposal(api.engine, jid)["sections"]["prior.g1"]["paragraphs"]
        assert written == [p1, {**p2, "state": "accepted"}]

    def test_if_match_is_required(self, api):
        jid = _sec_work(api.engine, sections={"prior.g1": SEC_STORED})
        res = _put(api, jid, [], version=None)
        assert res.status_code == 428
        assert _sec_proposal(api.engine, jid)["version"] == 3

    def test_old_version_is_409_with_the_current_version(self, api):
        jid = _sec_work(api.engine, sections={"prior.g1": SEC_STORED}, version=5)

        res = _put(api, jid, [{"id": "p1", "text": "고친다 [E1].", "state": "proposed"}], version=4)

        assert res.status_code == 409
        assert res.json()["detail"]["code"] == "version_conflict" and res.json()["detail"]["version"] == 5
        assert _sec_proposal(api.engine, jid)["sections"]["prior.g1"] == SEC_STORED

    @pytest.mark.parametrize("kind, target", [("section", "prior.g1"), ("paragraph", "prior.g1#p2")])
    def test_section_being_written_is_409(self, api, kind, target):
        jid = _sec_work(api.engine, sections={"prior.g1": SEC_STORED})
        add_generation(api.engine, jid, kind=kind, status="queued", target=target)

        res = _put(api, jid, [{"id": "p1", "text": "고친다 [E1].", "state": "proposed"}])

        assert (res.status_code, res.json()["detail"]) == (409, "이 절을 쓰는 중입니다")

    def test_section_not_written_yet_is_404(self, api):
        jid = _sec_work(api.engine, sections={"prior.g1": SEC_STORED})
        res = _put(api, jid, [], key="gap")
        assert (res.status_code, res.json()["detail"]) == (404, "절이 없습니다")

    def test_same_paragraph_twice_is_422(self, api):
        jid = _sec_work(api.engine, sections={"prior.g1": SEC_STORED})
        res = _put(api, jid, [{"id": "p1", "text": "가 [E1].", "state": "proposed"},
                              {"id": "p1", "text": "나 [E1].", "state": "proposed"}])
        assert (res.status_code, res.json()["detail"]) == (422, "같은 문단 id 가 두 번 있습니다")

    @pytest.mark.parametrize("paragraphs", [
        [{"id": "p1", "text": "   ", "state": "proposed"}],
        [{"id": "p1", "text": "가 [E1].", "state": "deleted"}],
        [{"id": None, "text": "가 [E1].", "state": "proposed"}] * (MAX_PARAGRAPHS_PUT + 1),
    ], ids=["blank-text", "unknown-state", "too-many"])
    def test_body_is_validated(self, api, paragraphs):
        jid = _sec_work(api.engine, sections={"prior.g1": SEC_STORED})
        assert _put(api, jid, paragraphs).status_code == 422

    def test_example_work_is_read_only(self, api):
        jid = _sec_work(api.engine, sections={"prior.g1": SEC_STORED}, is_example=True)
        assert _put(api, jid, []).status_code == 409


# ── 문단 다시 쓰기 (Task 20) ─────────────────────────────────────────────

PARA_SOURCE_INPUT = {
    "key": "prior.g1", "kind": "prior", "question": SEC_QUESTION,
    "topic": {"id": 1, "title": SEC_TOPIC["title"]}, "research_question": "가족 지지는 우울을 낮추는가?",
    "group": {"name": "가족 지지와 우울"}, "seeds": [],
    "papers": [{"eid": "E1", "cnts_id": "KCI_A", "title": "노인 우울과 가족 지지", "year": 2013,
                "abstract": "초록", "excerpt": None},
               {"eid": "E2", "cnts_id": "KCI_B", "title": "사회적 지지 척도", "year": 2015,
                "abstract": "초록", "excerpt": None}],
    "figures": [{"id": "F1", "label": "이 절에 준 논문 수", "value": "2"}],
    "basis": {"topic_id": 1, "papers": ["KCI_A", "KCI_B"]},
}


def _para_work(engine, *, source_status: str = "done", source_kind: str = "section", is_example: bool = False,
               states: tuple[str, ...] = ("proposed", "accepted", "edited")) -> tuple[uuid.UUID, int]:
    """절 하나(prior.g1)가 써진 연구 — 그 절을 쓴 section 생성 행과 문단 셋."""
    jid = _sec_work(engine, is_example=is_example, proposal=False)
    source = add_generation(engine, jid, kind=source_kind, status=source_status, target="prior.g1",
                            input=PARA_SOURCE_INPUT, output={"paragraphs": []})
    stored = {**SEC_STORED, "gen_id": source,
              "paragraphs": [_para(f"p{i}", f"{i}번 문단 [E1].", s) for i, s in enumerate(states, start=1)]}
    with engine.connect() as conn:
        topic_id = conn.execute(sa.select(ResearchWork.__table__.c.topic_id)
                                .where(ResearchWork.__table__.c.id == jid)).scalar_one()
    add_proposal(engine, jid, version=3, outline=_sec_outline(topic_id), sections={"prior.g1": stored})
    return jid, source


class TestRegenerateParagraph:
    def test_ai_paragraph_is_queued_with_the_section_input(self, api):
        jid, source = _para_work(api.engine)

        res = api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p2/regenerate")

        assert res.status_code == 200
        gen = _sec_gens(api.engine, jid)[-1]
        assert res.json() == {"gen_id": gen["id"]} and gen["id"] != source
        assert (gen["kind"], gen["target"], gen["status"], gen["priority"]) == (
            "paragraph", "prior.g1#p2", "queued", PRIORITY_USER)
        assert gen["input"] == {**PARA_SOURCE_INPUT, "pid": "p2", "before": "1번 문단 [E1].",
                                "current": "2번 문단 [E1].", "after": "3번 문단 [E1]."}
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "generation", queued_event(gen["id"], "paragraph", "prior.g1#p2"))]

    def test_proposed_paragraph_can_be_called_again_too(self, api):
        jid, _ = _para_work(api.engine)
        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p1/regenerate").status_code == 200

    @pytest.mark.parametrize("states", [("edited",), ("authored",)])
    def test_user_paragraph_is_409(self, api, states):
        jid, _ = _para_work(api.engine, states=states)

        res = api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p1/regenerate")

        assert (res.status_code, res.json()["detail"]) == (409, "다시 쓸 수 없는 문단입니다")

    @pytest.mark.parametrize("key, pid", [("prior.g1", "p9"), ("gap", "p1"), ("prior.g1", "x" * 80)])
    def test_unknown_paragraph_is_404(self, api, key, pid):
        jid, _ = _para_work(api.engine)
        res = api.client.post(f"/api/research/{jid}/sections/{key}/paragraphs/{pid}/regenerate")
        assert (res.status_code, res.json()["detail"]) == (404, "문단이 없습니다")

    @pytest.mark.parametrize("kind, target", [("section", "prior.g1"), ("paragraph", "prior.g1#p1"),
                                              ("paragraph", "prior.g1#p2")])
    def test_section_being_written_is_409(self, api, kind, target):
        jid, _ = _para_work(api.engine)
        add_generation(api.engine, jid, kind=kind, status="running", target=target)

        res = api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p2/regenerate")

        assert (res.status_code, res.json()["detail"]) == (409, "이 절을 쓰는 중입니다")

    def test_other_sections_being_written_do_not_block(self, api):
        jid, _ = _para_work(api.engine)
        add_generation(api.engine, jid, kind="paragraph", status="queued", target="prior.g2#p2")
        add_generation(api.engine, jid, kind="section", status="queued", target="gap")

        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p2/regenerate").status_code == 200

    @pytest.mark.parametrize("status, kind", [("failed", "section"), ("done", "outline")])
    def test_section_without_its_done_generation_is_409(self, api, status, kind):
        jid, _ = _para_work(api.engine, source_status=status, source_kind=kind)

        res = api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p2/regenerate")

        assert (res.status_code, res.json()["detail"]) == (409, "이 절을 쓴 생성 기록이 없어 문단을 다시 쓸 수 없습니다")

    def test_example_work_is_read_only(self, api):
        jid, _ = _para_work(api.engine, is_example=True)
        assert api.client.post(f"/api/research/{jid}/sections/prior.g1/paragraphs/p2/regenerate").status_code == 409
