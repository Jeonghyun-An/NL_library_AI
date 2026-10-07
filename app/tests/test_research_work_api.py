"""test_research_work_api.py — 연구 어시스턴트 API(api/research_work.py).

요청은 TestClient 로 실제 라우팅을 거친다(헤더 400·경로 422·본문 검증은 라우팅을 거쳐야 드러난다).
DB 는 history_sqlite 의 SQLite 다 — 이어가기의 멱등(ON CONFLICT DO NOTHING … RETURNING)·조건부 UPDATE·
이어간 연구 목록의 기록 조건을 실제 엔진이 판정한다. 요청이 끝나면 세션을 되돌리므로 핸들러가 직접
커밋한 쓰기만 남는다.

redis 는 로컬 venv 에 없다 — 미설치일 때만 더미를 꽂고, 연구 채널(publish_work·subscribe_work)은 기록용
가짜로 바꾼다. 디스패치 태스크를 보내는 워커 모듈은 sys.modules 에 가짜를 꽂는다(라우터는 보낼 때만
import 한다). 생성 대기 정보(queue_info)는 디스패처의 몫이라 가짜로 고정한다 — 끝까지 한 번 돌리는
TestEndToEnd 만 진짜 디스패처·실행기를 가짜 LLM 과 함께 쓴다.
"""
import ast
import asyncio
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
    SID_A, SID_B, AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.history import HistoryItem
from models.research import ResearchJob, ResearchStep
from models.research_work import (
    WORK_PHASES, ResearchGeneration, ResearchReading, ResearchTopic, ResearchWork,
)
from services.research_work.seeds import topic_input
from services.research_work.shapes import PHASE_ORDER

A = {"x-session-id": str(SID_A)}
B = {"x-session-id": str(SID_B)}
POSITION = 3                     # 가짜 queue_info 가 늘 돌려주는 대기 순번
ETA = 90                         # 가짜 queue_info 가 늘 돌려주는 예상 시간(초)
PROGRESS0 = {"topics": 0, "reading": 0, "sections": 0, "sections_total": 6}   # 카드·담음·절이 없는 연구

SNAPSHOT = {
    "question": "청소년 독서 격차", "params": {}, "corpus_range": None,
    "subquestions": [
        {"idx": 0, "text": "독서 격차의 원인", "evidence_ids": ["E1", "E2"], "verdict": "sufficient",
         "evidence_chunks": {"E1": ["c1"], "E2": ["c2"]}, "chunk_scores": {"c1": 0.9, "c2": 0.6},
         "rounds": []},
    ],
    "evidence": {
        "E1": {"cnts_id": "C1", "meta": {"title": "독서 격차 연구"}, "chunks": []},
        "E2": {"cnts_id": "C2", "meta": {"title": "학교 도서관"}, "chunks": []},
    },
}
X1 = {"cnts_id": "X1", "title": "무관 논문", "personal_author": "박민수", "pub_date": "2015"}
REPORT = {
    "question": "청소년 독서 격차", "sections": [{"heading": "독서 격차의 원인"}],
    "trail": [{"subquestion": "독서 격차의 원인", "excluded_papers": [X1]}],
}
ROUNDS = [
    {"round": 1, "query": "독서 격차 원인", "verdict": "insufficient", "note": "가정 요인이 부족하다",
     "excluded": 1, "excluded_papers": [X1],
     "adopted_papers": [{"cnts_id": "C1", "title": "독서 격차 연구", "personal_author": "김철수",
                         "pub_date": "2019", "rank": 1, "new": True}]},
]


def _ev(cnts_id: str, title: str, pub_date: str) -> dict:
    return {"cnts_id": cnts_id, "chunks": [],
            "meta": {"title": title, "personal_author": "김철수", "pub_date": pub_date}}


def _section(heading: str, pairs: tuple, futures: list[dict]) -> dict:
    return {"heading": heading, "intro": "", "future": futures,
            "papers": [{"cnts_id": c, "summary": "", "evidence": [e]} for c, e in pairs]}


# 씨앗이 다섯인 보고서 — 절을 한 바퀴 돌고(절 0·1·2) 절 0 의 두 번째 과제까지 4장, insufficient:1 은 남는다
SEED_REPORT = {
    "question": "노인의 우울과 사회적 지지",
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
SEED_KEYS = ["future:0:0", "future:1:0", "future:2:0", "future:0:1"]
FINISHED = datetime(2026, 10, 6, 9, 30)
CORPUS = {"n_papers": 144748, "from": "1980", "to": "2017", "at": "2026-10-06T09:30:00"}


def _stub_missing(monkeypatch, name: str, module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module)


_CACHED = ("api.research_work", "services.research.relay")


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다
    (test_research_api.py 와 같은 방식 — 더미 redis 에 묶인 relay 가 다른 테스트로 새지 않게)."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


class _Dispatch:
    """workers.research_work_tasks.send_dispatch 가짜 — 보낸 횟수를 센다."""
    def __init__(self):
        self.calls = 0
        self.result = True
        self.error: Exception | None = None

    def send_dispatch(self) -> bool:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class _Api:
    def __init__(self, client, engine, router, events, dispatch, asked):
        self.client = client
        self.engine = engine
        self.router = router
        self.events = events
        self.dispatch = dispatch
        self.asked = asked            # queue_info 를 물어본 생성 id


@pytest.fixture
def api(monkeypatch):
    for name in ("redis", "redis.asyncio"):
        _stub_missing(monkeypatch, name, MagicMock())
    _forget_on_teardown(monkeypatch, _CACHED)
    router = importlib.import_module("api.research_work")
    from core.deps import get_db

    events: list[tuple] = []

    async def _publish_work(work_id, kind, payload):
        events.append((str(work_id), kind, payload))

    monkeypatch.setattr(router, "publish_work", _publish_work)

    asked: list[int] = []

    async def _queue_info(db, gen):
        asked.append(gen.id)
        return {"position": POSITION, "eta_sec": ETA, "others_ahead": False}

    monkeypatch.setattr(router, "queue_info", _queue_info)

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
    app.include_router(router.router)
    app.dependency_overrides[get_db] = _db
    return _Api(TestClient(app), engine, router, events, dispatch, asked)


# ── 데이터 도우미 ─────────────────────────────────────────────────────


def _job(engine, *, status: str = "completed", snapshot: dict | None = None,
         report: dict | None = None, plan: list | None = None) -> uuid.UUID:
    jid = add_research_job(engine, status=status, stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == jid).values(
            question="청소년 독서 격차", state_snapshot=snapshot, report=report, plan=plan,
        ))
    return jid


def _work_job(engine, **work) -> uuid.UUID:
    jid = _job(engine)
    add_work(engine, jid, **work)
    return jid


def _seed_job(engine) -> uuid.UUID:
    jid = _job(engine, report=SEED_REPORT, plan=[t["subquestion"] for t in SEED_REPORT["trail"]])
    _set(engine, ResearchJob, jid, finished_at=FINISHED)
    return jid


def _step(engine, jid: uuid.UUID, seq: int, subq_idx: int, result: dict) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(ResearchStep.__table__).values(
            job_id=jid, seq=seq, kind="search", subq_idx=subq_idx, title="탐색",
            status="done", result=result,
        ))


def _history(engine, session_id: uuid.UUID, ref_id: uuid.UUID, *, kind: str = "research",
             deleted: bool = False) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(HistoryItem.__table__).values(
            id=uuid.uuid4(), session_id=session_id, kind=kind, title="독서 격차 연구", params={},
            ref_id=str(ref_id), deleted_at=datetime.now(timezone.utc) if deleted else None,
        ))


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


def _frames(body: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in body.splitlines()
            if line.startswith("data: ")]


# ── 이어가기 ─────────────────────────────────────────────────────────


class TestContinue:
    def test_creates_the_work_its_candidates_and_one_concepts_generation(self, api, monkeypatch):
        monkeypatch.setattr(api.router, "concepts_input",
                            lambda job: {"question": job.question, "marker": 1})
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 200
        (gen,) = _rows(api.engine, ResearchGeneration)
        assert res.json() == {
            "id": str(jid), "phase": "topics", "concepts": [], "memo": None, "is_example": False,
            "progress": PROGRESS0, "topic_id": None, "corpus": None,
            "generations": [{"id": gen["id"], "kind": "concepts", "target": None,
                             "status": "queued", "model": None, "error": None,
                             "position": POSITION, "eta_sec": ETA, "others_ahead": False}],
        }
        (work,) = _rows(api.engine, ResearchWork)
        assert work["owner_sid"] == str(SID_A) and work["concept_members"] == {}
        assert [(r["cnts_id"], r["state"], r["origin"]) for r in _rows(api.engine, ResearchReading)] == [
            ("C1", "candidate", "evidence"), ("C2", "candidate", "evidence"),
        ]
        assert _rows(api.engine, ResearchReading, cnts_id="C1")[0]["origin_ref"]["rank"] == {"0": 1}
        assert (gen["work_id"], gen["kind"], gen["priority"], gen["status"]) == (
            jid, "concepts", 10, "queued")
        assert gen["input"] == {"question": "청소년 독서 격차", "marker": 1}
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "work", {"phase": "topics", "progress": PROGRESS0})]

    def test_concepts_input_reads_the_job(self, api):
        # 가짜 없이 — 핵심 개념 생성 입력이 잡 행(질문·계획·보고서)에서 만들어지는지
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        (gen,) = _rows(api.engine, ResearchGeneration)
        same_job = SimpleNamespace(id=jid, question="청소년 독서 격차", plan=["독서 격차의 원인"],
                                   report=REPORT, state_snapshot=SNAPSHOT, params={})
        assert gen["input"] == json.loads(json.dumps(api.router.concepts_input(same_job)))
        assert gen["input"]["question"] == "청소년 독서 격차"

    def test_second_continue_adds_nothing(self, api):
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        first = api.client.post(f"/api/research/{jid}/work/continue", headers=A)
        second = api.client.post(f"/api/research/{jid}/work/continue", headers=B)

        assert second.status_code == 200 and second.json() == first.json()
        assert len(_rows(api.engine, ResearchWork)) == 1
        assert _rows(api.engine, ResearchWork)[0]["owner_sid"] == str(SID_A)
        assert len(_rows(api.engine, ResearchReading)) == 2
        assert len(_rows(api.engine, ResearchGeneration)) == 1
        assert api.dispatch.calls == 1 and len(api.events) == 1

    def test_without_a_browser_id_the_owner_stays_empty(self, api):
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT)

        assert api.client.post(f"/api/research/{jid}/work/continue").status_code == 200

        assert _rows(api.engine, ResearchWork)[0]["owner_sid"] is None

    def test_job_without_a_snapshot_still_gets_concepts(self, api):
        jid = _job(api.engine, report=REPORT, plan=["독서 격차의 원인"])

        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        assert _rows(api.engine, ResearchReading) == []
        assert len(_rows(api.engine, ResearchGeneration)) == 1

    @pytest.mark.parametrize("status", ["awaiting_approval", "queued", "running", "failed", "canceled"])
    def test_only_a_completed_job_can_be_continued(self, api, status):
        jid = _job(api.engine, status=status, snapshot=SNAPSHOT)

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 409
        assert _rows(api.engine, ResearchWork) == []
        assert api.dispatch.calls == 0

    def test_unknown_job_is_404_and_malformed_id_is_422(self, api):
        assert api.client.post(f"/api/research/{uuid.uuid4()}/work/continue").status_code == 404
        assert api.client.post("/api/research/not-a-uuid/work/continue").status_code == 422

    def test_dispatch_failure_still_answers_200(self, api):
        # 행은 이미 커밋됐다 — 회수기가 queued 를 보고 디스패치를 다시 보낸다
        api.dispatch.result = False
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT)
        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        api.dispatch.error = RuntimeError("broker down")
        other = _job(api.engine, snapshot=SNAPSHOT, report=REPORT)
        assert api.client.post(f"/api/research/{other}/work/continue", headers=A).status_code == 200

        assert [g["status"] for g in _rows(api.engine, ResearchGeneration)] == ["queued", "queued"]

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 409 and res.json()["detail"] == "예시 연구는 읽기 전용입니다"
        assert _rows(api.engine, ResearchGeneration) == []


class TestContinueSeeds:
    def test_report_seeds_become_four_topics_each_with_one_card_generation(self, api):
        jid = _seed_job(api.engine)

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 200
        topics = _rows(api.engine, ResearchTopic)
        assert [(t["slot"], t["origin"], t["state"], t["card"], t["seed"]["key"]) for t in topics] == [
            (n, "report_seed", "candidate", {}, key) for n, key in enumerate(SEED_KEYS, start=1)]
        assert all(t["corpus_snapshot"] == CORPUS and t["parent_id"] is None for t in topics)
        gens = _rows(api.engine, ResearchGeneration)
        assert [(g["kind"], g["target"], g["priority"], g["status"]) for g in gens] == [
            ("concepts", None, 10, "queued"),
            *[("topic_card", str(t["id"]), 10, "queued") for t in topics]]
        for topic, gen in zip(topics, gens[1:]):
            assert gen["input"] == topic_input("청소년 독서 격차", topic["seed"], SEED_REPORT, topic["id"])
        (work,) = _rows(api.engine, ResearchWork)
        assert (work["corpus_snapshot"], work["progress"], work["topic_id"]) == (CORPUS, PROGRESS0, None)
        body = res.json()
        assert (body["corpus"], body["topic_id"], body["progress"]) == (CORPUS, None, PROGRESS0)
        assert [(g["kind"], g["target"], g["position"], g["eta_sec"]) for g in body["generations"]] == [
            (g["kind"], g["target"], POSITION, ETA) for g in gens]
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "work", {"phase": "topics", "progress": PROGRESS0})]

    def test_second_continue_adds_no_topic_or_card(self, api):
        jid = _seed_job(api.engine)

        first = api.client.post(f"/api/research/{jid}/work/continue", headers=A)
        second = api.client.post(f"/api/research/{jid}/work/continue", headers=B)

        assert second.status_code == 200 and second.json() == first.json()
        assert len(_rows(api.engine, ResearchTopic)) == 4
        assert len(_rows(api.engine, ResearchGeneration)) == 5
        assert api.dispatch.calls == 1 and len(api.events) == 1

    def test_a_work_continued_before_06b_gets_no_seed_cards(self, api):
        # 정함 15 — 이미 있는 연구(06a 에서 이어간 확인용 연구)는 '이미 있음' 분기라 아무것도 넣지 않는다
        jid = _seed_job(api.engine)
        add_work(api.engine, jid)

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 200 and res.json()["corpus"] is None
        assert _rows(api.engine, ResearchTopic) == [] and _rows(api.engine, ResearchGeneration) == []
        assert api.dispatch.calls == 0 and api.events == []

    def test_a_report_without_seeds_adds_only_the_concepts(self, api):
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        assert api.client.post(f"/api/research/{jid}/work/continue", headers=A).status_code == 200

        assert _rows(api.engine, ResearchTopic) == []
        assert [g["kind"] for g in _rows(api.engine, ResearchGeneration)] == ["concepts"]
        assert _rows(api.engine, ResearchWork)[0]["corpus_snapshot"] is None

    def test_a_failure_while_adding_cards_leaves_nothing_behind(self, api, monkeypatch):
        # 씨앗 카드까지 한 커밋이다 — 중간에 실패하면 연구 행도 남지 않아 다음 이어가기가 처음부터 만든다
        def _broken(*args, **kwargs):
            raise RuntimeError("카드 입력을 만들지 못했다")

        monkeypatch.setattr(api.router, "topic_input", _broken)
        jid = _seed_job(api.engine)

        with pytest.raises(RuntimeError):
            api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert _rows(api.engine, ResearchWork) == []
        assert _rows(api.engine, ResearchTopic) == [] and _rows(api.engine, ResearchGeneration) == []
        assert api.dispatch.calls == 0 and api.events == []


# ── 조회·고치기 ───────────────────────────────────────────────────────


class TestGetWork:
    def test_404_until_continued(self, api):
        jid = _job(api.engine)
        assert api.client.get(f"/api/research/{jid}/work").status_code == 404

    def test_lists_open_generations_and_the_ten_latest_finished(self, api):
        jid = _work_job(api.engine, concepts=["독서 격차"])
        done = [add_generation(api.engine, jid, status="done") for _ in range(11)]
        failed = add_generation(api.engine, jid, status="failed")
        running = add_generation(api.engine, jid, status="running")
        queued = add_generation(api.engine, jid, status="queued")

        res = api.client.get(f"/api/research/{jid}/work")

        assert res.status_code == 200
        gens = res.json()["generations"]
        assert [g["id"] for g in gens] == [*done[2:], failed, running, queued]
        assert {g["id"]: g["position"] for g in gens if g["status"] in ("running", "queued")} == {
            running: None, queued: POSITION}
        assert api.asked == [queued]
        assert res.json()["concepts"] == ["독서 격차"]

    def test_carries_the_picked_topic_the_corpus_and_the_wait(self, api):
        jid = _work_job(api.engine)
        _set(api.engine, ResearchWork, jid, topic_id=7, corpus_snapshot=CORPUS)
        queued = add_generation(api.engine, jid, kind="topic_card", target="7")
        done = add_generation(api.engine, jid, status="done")

        body = api.client.get(f"/api/research/{jid}/work").json()

        assert (body["topic_id"], body["corpus"]) == (7, CORPUS)
        assert {g["id"]: (g["position"], g["eta_sec"], g["others_ahead"]) for g in body["generations"]} == {
            queued: (POSITION, ETA, False), done: (None, None, False)}


class TestPatchWork:
    def test_cleans_concepts_and_clears_membership_when_they_change(self, api):
        jid = _work_job(api.engine, concepts=["옛 개념"])
        _set(api.engine, ResearchWork, jid, concept_members={"옛 개념": ["C1"]})
        add_generation(api.engine, jid, kind="concepts", status="done")       # 끝난 생성은 막지 않는다

        res = api.client.patch(f"/api/research/{jid}/work",
                               json={"concepts": ["  독서   격차 ", "청소년", "독서 격차"]})

        assert res.status_code == 200
        assert res.json()["concepts"] == ["독서 격차", "청소년"]
        (work,) = _rows(api.engine, ResearchWork)
        assert work["concepts"] == ["독서 격차", "청소년"] and work["concept_members"] == {}

    def test_concepts_only_patch_keeps_the_memo(self, api):
        jid = _work_job(api.engine, concepts=["옛 개념"])
        _set(api.engine, ResearchWork, jid, memo="가설 메모")

        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": ["독서 격차"]})

        assert res.status_code == 200 and res.json()["memo"] == "가설 메모"
        assert _rows(api.engine, ResearchWork)[0]["memo"] == "가설 메모"

    @pytest.mark.parametrize("status", ["queued", "running"])
    def test_concepts_cannot_change_while_concepts_are_being_made(self, api, status):
        # 워커의 결과 적용이 끝나며 칩을 덮어쓴다 — 고친 개념이 소리 없이 사라지지 않게 막는다
        jid = _work_job(api.engine, concepts=["독서 격차"])
        add_generation(api.engine, jid, kind="concepts", status=status)

        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": ["청소년"]})

        assert res.status_code == 409
        assert res.json()["detail"] == "핵심 개념을 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
        assert _rows(api.engine, ResearchWork)[0]["concepts"] == ["독서 격차"]

    def test_memo_and_same_concepts_pass_while_concepts_are_being_made(self, api):
        jid = _work_job(api.engine, concepts=["독서 격차"])
        add_generation(api.engine, jid, kind="concepts", status="running")

        res = api.client.patch(f"/api/research/{jid}/work",
                               json={"concepts": ["독서 격차"], "memo": "메모"})

        assert res.status_code == 200 and res.json()["memo"] == "메모"
        assert _rows(api.engine, ResearchWork)[0]["memo"] == "메모"

    def test_same_concepts_keep_membership(self, api):
        jid = _work_job(api.engine, concepts=["독서 격차", "청소년"])
        _set(api.engine, ResearchWork, jid, concept_members={"독서 격차": ["C1"]})

        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": ["독서 격차", "청소년"]})

        assert res.status_code == 200
        assert _rows(api.engine, ResearchWork)[0]["concept_members"] == {"독서 격차": ["C1"]}

    def test_a_single_concept_is_enough(self, api):
        jid = _work_job(api.engine)
        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": ["독서 격차"]})
        assert res.status_code == 200 and res.json()["concepts"] == ["독서 격차"]

    @pytest.mark.parametrize("concepts", [[], ["   "], ["가", "나", "다", "라", "마", "바"], [1, 2]])
    def test_rejects_concepts_that_leave_nothing_or_too_many(self, api, concepts):
        jid = _work_job(api.engine, concepts=["독서 격차"])

        res = api.client.patch(f"/api/research/{jid}/work", json={"concepts": concepts})

        assert res.status_code == 422
        assert _rows(api.engine, ResearchWork)[0]["concepts"] == ["독서 격차"]

    def test_memo_is_saved_cleared_and_capped(self, api):
        jid = _work_job(api.engine)

        assert api.client.patch(f"/api/research/{jid}/work", json={"memo": "가설 메모"}).json()["memo"] == "가설 메모"
        assert _rows(api.engine, ResearchWork)[0]["memo"] == "가설 메모"
        assert api.client.patch(f"/api/research/{jid}/work", json={"memo": ""}).json()["memo"] is None
        assert api.client.patch(f"/api/research/{jid}/work", json={"memo": "가" * 2001}).status_code == 422

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        res = api.client.patch(f"/api/research/{jid}/work", json={"memo": "메모"})
        assert res.status_code == 409 and res.json()["detail"] == "예시 연구는 읽기 전용입니다"

    def test_404_until_continued(self, api):
        jid = _job(api.engine)
        assert api.client.patch(f"/api/research/{jid}/work", json={"memo": "메모"}).status_code == 404


class TestPatchPhase:
    def test_moves_forward_and_tells_the_other_tabs(self, api):
        jid = _work_job(api.engine)

        res = api.client.patch(f"/api/research/{jid}/work", json={"phase": "reading"})

        assert res.status_code == 200 and res.json()["phase"] == "reading"
        assert _rows(api.engine, ResearchWork)[0]["phase"] == "reading"
        assert api.events == [(str(jid), "work", {"phase": "reading", "progress": {}})]

    def test_can_skip_ahead_to_done(self, api):
        jid = _work_job(api.engine, phase="proposal")

        res = api.client.patch(f"/api/research/{jid}/work", json={"phase": "done"})

        assert res.status_code == 200 and res.json()["phase"] == "done"

    @pytest.mark.parametrize("now, asked", [("reading", "topics"), ("done", "proposal")])
    def test_never_moves_back(self, api, now, asked):
        jid = _work_job(api.engine, phase=now)

        res = api.client.patch(f"/api/research/{jid}/work", json={"phase": asked, "memo": "메모"})

        assert res.status_code == 409 and res.json()["detail"] == "단계를 되돌릴 수 없습니다"
        (work,) = _rows(api.engine, ResearchWork)
        assert (work["phase"], work["memo"]) == (now, None)
        assert api.events == []

    def test_the_same_phase_changes_nothing_and_sends_nothing(self, api):
        jid = _work_job(api.engine, phase="reading")

        res = api.client.patch(f"/api/research/{jid}/work", json={"phase": "reading", "memo": "메모"})

        assert res.status_code == 200 and res.json()["memo"] == "메모"
        assert api.events == []

    def test_every_phase_of_the_order_is_accepted_and_nothing_else(self, api):
        # WorkPatch 의 값과 shapes.PHASE_ORDER(=models.WORK_PHASES)가 갈리면 PATCH 가 단계를 잃는다
        assert PHASE_ORDER == WORK_PHASES
        for phase in PHASE_ORDER:
            jid = _work_job(api.engine)
            assert api.client.patch(f"/api/research/{jid}/work", json={"phase": phase}).status_code == 200
        jid = _work_job(api.engine)
        assert api.client.patch(f"/api/research/{jid}/work", json={"phase": "finished"}).status_code == 422

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        res = api.client.patch(f"/api/research/{jid}/work", json={"phase": "reading"})
        assert res.status_code == 409 and _rows(api.engine, ResearchWork)[0]["phase"] == "topics"


# ── 근거 풀 ──────────────────────────────────────────────────────────


class TestPool:
    def test_completed_job_pool_includes_uncited_evidence_and_trail_exclusions(self, api):
        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT)
        _step(api.engine, jid, 2, 0, {"rounds": ROUNDS})

        res = api.client.get(f"/api/research/{jid}/pool")

        assert res.status_code == 200
        assert [(p["cnts_id"], p["subq_idx"], p["rank"]) for p in res.json()["adopted"]] == [
            ("C1", [0], 1), ("C2", [0], 2)]
        assert res.json()["excluded"] == [
            {**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"}]

    def test_running_job_pool_comes_from_the_search_rounds(self, api):
        # 이어가기 전(연구 행 없음)·탐색 중에도 읽는다 — 근거 장부가 쓴다
        jid = _job(api.engine, status="running")
        _step(api.engine, jid, 2, 0, {"rounds": ROUNDS})

        res = api.client.get(f"/api/research/{jid}/pool")

        assert res.json() == {
            "adopted": [{"cnts_id": "C1", "title": "독서 격차 연구", "personal_author": "김철수",
                         "pub_date": "2019", "series_title": None, "subq_idx": [0], "rank": 1}],
            "excluded": [{**X1, "subq_idx": 0, "round": 1, "note": "가정 요인이 부족하다"}],
        }

    def test_unknown_job_is_404(self, api):
        assert api.client.get(f"/api/research/{uuid.uuid4()}/pool").status_code == 404


# ── 이어간 연구 목록 ─────────────────────────────────────────────────


class TestListWorks:
    def test_needs_the_browser_id(self, api):
        assert api.client.get("/api/research-works").status_code == 400

    def test_only_this_browsers_works_still_in_its_history(self, api):
        kept = _work_job(api.engine, owner_sid=str(SID_A))
        _history(api.engine, SID_A, kept)
        deleted = _work_job(api.engine, owner_sid=str(SID_A))
        _history(api.engine, SID_A, deleted, deleted=True)
        _work_job(api.engine, owner_sid=str(SID_A))                      # 기록이 없다
        other_owner = _work_job(api.engine, owner_sid=str(SID_B))
        _history(api.engine, SID_A, other_owner)
        other_kind = _work_job(api.engine, owner_sid=str(SID_A))
        _history(api.engine, SID_A, other_kind, kind="paper")
        removed = _work_job(api.engine, owner_sid=str(SID_A))
        _history(api.engine, SID_A, removed)
        _set(api.engine, ResearchWork, removed, deleted_at=datetime.now(timezone.utc))
        elsewhere = _work_job(api.engine, owner_sid=str(SID_A))       # 기록이 다른 브라우저에만 있다
        _history(api.engine, SID_B, elsewhere)

        res = api.client.get("/api/research-works", headers=A)

        assert res.status_code == 200
        (item,) = res.json()["items"]
        assert set(item) == {"id", "question", "phase", "created_at"}
        assert (item["id"], item["question"], item["phase"]) == (str(kept), "청소년 독서 격차", "topics")

    def test_newest_first(self, api):
        old = _work_job(api.engine, owner_sid=str(SID_A))
        new = _work_job(api.engine, owner_sid=str(SID_A))
        for jid, day in ((old, 1), (new, 2)):
            _history(api.engine, SID_A, jid)
            _set(api.engine, ResearchWork, jid, created_at=datetime(2026, 10, day, tzinfo=timezone.utc))

        res = api.client.get("/api/research-works", headers=A)

        assert [i["id"] for i in res.json()["items"]] == [str(new), str(old)]

    def test_examples_are_listed_for_any_browser(self, api):
        example = _work_job(api.engine, owner_sid=str(SID_B), is_example=True)
        _work_job(api.engine, owner_sid=str(SID_A))

        res = api.client.get("/api/research-works?example=1", headers=A)

        assert [i["id"] for i in res.json()["items"]] == [str(example)]


# ── 생성 취소·다시 ───────────────────────────────────────────────────


class TestCancelGeneration:
    def test_queued_generation_is_canceled(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="queued")

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/cancel")

        assert res.status_code == 200 and res.json() == {"gen_id": gid, "status": "canceled"}
        (gen,) = _rows(api.engine, ResearchGeneration)
        assert gen["status"] == "canceled" and gen["finished_at"] is not None
        assert api.events == [(str(jid), "generation", {
            "gen_id": gid, "gen_kind": "concepts", "target": None, "status": "canceled",
            "model": None, "result": None})]
        assert api.dispatch.calls == 0

    def test_running_generation_waits_until_it_ends(self, api):
        # canceled 로 두면 디스패처의 전역 한 자리가 비어 다음 생성이 q_research_plan 의 남은 자리를 쓴다 —
        # 취소한 생성의 LLM 호출은 워커에서 계속 돌므로 두 자리를 생성이 다 쓴다(D15)
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="running")

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/cancel")

        assert res.status_code == 409
        assert res.json()["detail"] == "진행 중인 생성은 끝날 때까지 기다립니다"
        assert _rows(api.engine, ResearchGeneration)[0]["status"] == "running"
        assert api.events == [] and api.dispatch.calls == 0

    def test_generation_picked_after_it_was_read_is_409(self, api, monkeypatch):
        # 읽은 뒤 디스패처가 집었으면(queued → running) 조건부 UPDATE 가 바꾸지 않는다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="queued")
        read = api.router._get_generation

        async def _picked_meanwhile(db, work_id, gen_id):
            gen = await read(db, work_id, gen_id)
            _set(api.engine, ResearchGeneration, gen_id, status="running")
            return gen

        monkeypatch.setattr(api.router, "_get_generation", _picked_meanwhile)

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/cancel")

        assert res.status_code == 409
        assert _rows(api.engine, ResearchGeneration)[0]["status"] == "running"
        assert api.events == []

    @pytest.mark.parametrize("status", ["done", "failed", "canceled"])
    def test_finished_generation_is_409(self, api, status):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status=status)

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/cancel")

        assert res.status_code == 409
        assert _rows(api.engine, ResearchGeneration)[0]["status"] == status
        assert api.events == []

    def test_generation_of_another_work_is_404(self, api):
        jid = _work_job(api.engine)
        other = _work_job(api.engine)
        gid = add_generation(api.engine, other)

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/cancel").status_code == 404
        assert api.client.post(f"/api/research/{jid}/generations/999/cancel").status_code == 404
        assert _rows(api.engine, ResearchGeneration)[0]["status"] == "queued"

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        gid = add_generation(api.engine, jid)
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/cancel").status_code == 409


class TestRetryGeneration:
    @pytest.mark.parametrize("status", ["failed", "canceled"])
    def test_adds_a_queued_copy_and_dispatches(self, api, status):
        jid = _work_job(api.engine)
        # 배경 우선순위(0)도 그대로 옮긴다 — 다시 부른다고 사용자 우선순위로 올리지 않는다
        gid = add_generation(api.engine, jid, status=status, priority=0,
                             input={"question": "청소년 독서 격차"})

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 200
        old, new = _rows(api.engine, ResearchGeneration)
        assert res.json() == {"gen_id": new["id"]}
        assert old["status"] == status
        assert (new["kind"], new["target"], new["priority"], new["status"], new["input"]) == (
            "concepts", None, 0, "queued", {"question": "청소년 독서 격차"})
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "generation", {
            "gen_id": new["id"], "gen_kind": "concepts", "target": None, "status": "queued",
            "model": None, "result": None})]

    def test_concepts_done_without_concepts_can_be_called_again(self, api):
        # spec §5-2 — 핵심 개념을 끝내 못 얻으면 비운 채 done 이고, 다시 부르기는 이 retry 다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="done", input={"question": "청소년 독서 격차"})
        _set(api.engine, ResearchGeneration, gid, output={"concepts": [], "attempts": []})

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 200
        old, new = _rows(api.engine, ResearchGeneration)
        assert res.json() == {"gen_id": new["id"]}
        assert (old["status"], new["kind"], new["priority"], new["status"], new["input"]) == (
            "done", "concepts", 10, "queued", {"question": "청소년 독서 격차"})
        assert api.dispatch.calls == 1
        assert api.events == [(str(jid), "generation", {
            "gen_id": new["id"], "gen_kind": "concepts", "target": None, "status": "queued",
            "model": None, "result": None})]

    def test_topic_card_done_without_a_card_can_be_called_again(self, api):
        # 근거 부족('카드 없음')으로 끝난 카드도 빈 결과다 — 그 kind 의 실행기가 판정한다(is_empty)
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, kind="topic_card", status="done", target="7",
                             input={"topic_id": 7}, output={"card": None, "attempts": []})

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 200
        old, new = _rows(api.engine, ResearchGeneration)
        assert (new["kind"], new["target"], new["status"], new["input"]) == (
            "topic_card", "7", "queued", {"topic_id": 7})
        assert api.events == [(str(jid), "generation", {
            "gen_id": new["id"], "gen_kind": "topic_card", "target": "7", "status": "queued",
            "model": None, "result": None})]

    def test_topic_card_done_with_a_card_is_409(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, kind="topic_card", status="done", target="7",
                             output={"card": {"title": "주제", "question": "질문?", "evidence": ["P1", "P2"]}})

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 409 and res.json()["detail"] == "다시 부를 수 없는 상태입니다: done"
        assert len(_rows(api.engine, ResearchGeneration)) == 1

    def test_done_of_a_kind_without_an_executor_is_409(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, kind="facet", status="done", output={})

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 409

    def test_concepts_done_with_concepts_is_409(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="done")
        _set(api.engine, ResearchGeneration, gid, output={"concepts": ["독서 격차", "청소년"]})

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 409 and res.json()["detail"] == "다시 부를 수 없는 상태입니다: done"
        assert len(_rows(api.engine, ResearchGeneration)) == 1
        assert api.dispatch.calls == 0

    @pytest.mark.parametrize("status", ["queued", "running"])
    def test_open_generation_cannot_be_retried(self, api, status):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status=status)

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 409
        assert len(_rows(api.engine, ResearchGeneration)) == 1
        assert api.dispatch.calls == 0

    def test_second_retry_while_the_copy_is_open_is_409(self, api):
        # 두 번 누르면 같은 생성이 두 줄 서지 않는다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="failed")

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 200
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 409
        assert len(_rows(api.engine, ResearchGeneration)) == 2

    def test_old_failure_after_a_newer_success_is_409_and_keeps_the_concepts(self, api):
        # gen1 failed → retry 로 gen2 done(개념 채움) → 사용자가 칩을 고침. 오래된 탭이 gen1 을 다시 부르면
        # gen3 의 결과가 고친 칩을 덮고 개념 소속을 비운다 — 같은 대상의 최신 행만 다시 부른다
        jid = _work_job(api.engine, concepts=["사용자 개념", "청소년"])
        old = add_generation(api.engine, jid, status="failed")
        newer = add_generation(api.engine, jid, status="done")
        _set(api.engine, ResearchGeneration, newer, output={"concepts": ["독서 격차", "청소년"]})

        res = api.client.post(f"/api/research/{jid}/generations/{old}/retry")

        assert res.status_code == 409 and res.json()["detail"] == api.router.NEWER_GENERATION
        assert len(_rows(api.engine, ResearchGeneration)) == 2
        assert _rows(api.engine, ResearchWork)[0]["concepts"] == ["사용자 개념", "청소년"]
        assert api.dispatch.calls == 0 and api.events == []

    def test_only_the_latest_failure_of_a_target_can_be_called_again(self, api):
        jid = _work_job(api.engine)
        first = add_generation(api.engine, jid, status="failed")
        latest = add_generation(api.engine, jid, status="failed")

        assert api.client.post(f"/api/research/{jid}/generations/{first}/retry").status_code == 409
        assert len(_rows(api.engine, ResearchGeneration)) == 2
        assert api.client.post(f"/api/research/{jid}/generations/{latest}/retry").status_code == 200
        assert len(_rows(api.engine, ResearchGeneration)) == 3

    def test_a_newer_generation_of_another_target_does_not_block(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="failed")
        _set(api.engine, ResearchGeneration, gid, target="t1")
        other = add_generation(api.engine, jid, status="failed")
        _set(api.engine, ResearchGeneration, other, target="t2")

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 200

    def test_an_open_generation_of_another_target_does_not_block(self, api):
        # 같은 kind 라도 대상(target)이 다르면 다른 일이다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="failed")
        _set(api.engine, ResearchGeneration, gid, target="t1")
        other = add_generation(api.engine, jid, status="queued")
        _set(api.engine, ResearchGeneration, other, target="t2")

        res = api.client.post(f"/api/research/{jid}/generations/{gid}/retry")

        assert res.status_code == 200
        (new,) = _rows(api.engine, ResearchGeneration, id=res.json()["gen_id"])
        assert (new["target"], new["status"]) == ("t1", "queued")

    def test_duplicate_check_and_insert_run_under_one_lock(self, api):
        # 동시에 두 번 눌러도 한 줄만 서게 — (연구·kind·target) 잠금 → 열린 생성 검사 → 넣기 → 커밋.
        # 잠금은 SQLite 에서 빈 함수다(history_sqlite) — 순서와 키를 문장 기록으로 본다
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, jid, status="failed")
        _set(api.engine, ResearchGeneration, gid, target="t1")
        seen: list[tuple] = []
        sa.event.listen(api.engine, "before_cursor_execute",
                        lambda conn, cur, stmt, params, ctx, many: seen.append((stmt, params)))
        sa.event.listen(api.engine, "commit", lambda conn: seen.append(("COMMIT", None)))

        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 200

        lock = next(i for i, (s, _) in enumerate(seen) if "pg_advisory_xact_lock" in s)
        check = next(i for i, (s, _) in enumerate(seen)
                     if s.startswith("SELECT") and "research_generations.status IN" in s)
        newer = next(i for i, (s, _) in enumerate(seen)
                     if s.startswith("SELECT") and "research_generations.id >" in s)
        insert = next(i for i, (s, _) in enumerate(seen)
                      if s.startswith("INSERT INTO research_generations"))
        commit = next(i for i, (s, _) in enumerate(seen) if s == "COMMIT" and i > lock)
        assert lock < check < newer < insert < commit
        assert seen[lock][1] == (api.router._retry_lock_key(jid, "concepts", "t1"),)
        assert api.router._retry_lock_key(jid, "concepts", "t1") != api.router._retry_lock_key(
            jid, "concepts", "t2")

    def test_example_work_is_read_only(self, api):
        jid = _work_job(api.engine, is_example=True)
        gid = add_generation(api.engine, jid, status="failed")
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 409

    def test_generation_of_another_work_is_404(self, api):
        jid = _work_job(api.engine)
        gid = add_generation(api.engine, _work_job(api.engine), status="failed")
        assert api.client.post(f"/api/research/{jid}/generations/{gid}/retry").status_code == 404


# ── 연구 SSE ─────────────────────────────────────────────────────────


class TestWorkStream:
    def test_snapshot_then_relayed_events_and_pings(self, api, monkeypatch):
        jid = _work_job(api.engine, concepts=["독서 격차"])
        gid = add_generation(api.engine, jid)
        seen = {}
        event = {"kind": "generation", "gen_id": gid, "gen_kind": "concepts", "target": None,
                 "status": "done", "model": "qwen3-vl-8b", "result": {"concepts": ["독서 격차"]}}

        async def _subscribe_work(work_id, *, idle_timeout=15.0):
            seen["work_id"] = work_id
            yield event
            yield None
            yield {"kind": "work", "phase": "topics", "progress": {}}

        monkeypatch.setattr(api.router, "subscribe_work", _subscribe_work)

        res = api.client.get(f"/api/research/{str(jid).upper()}/work/stream")

        assert res.headers["content-type"].startswith("text/event-stream")
        frames = _frames(res.text)
        assert frames[0]["kind"] == "snapshot"
        assert frames[0]["work"] == api.client.get(f"/api/research/{jid}/work").json()
        assert frames[1:] == [event, {"kind": "work", "phase": "topics", "progress": {}}]
        assert ": ping" in res.text
        # 워커는 표준형 id 채널에 쓴다 — 대문자 경로로 붙어도 같은 채널을 구독해야 한다
        assert seen["work_id"] == str(jid)

    def test_404_until_continued(self, api):
        jid = _job(api.engine)
        assert api.client.get(f"/api/research/{jid}/work/stream").status_code == 404


# ── 끝까지 한 번 ──────────────────────────────────────────────────────


class TestEndToEnd:
    def test_continue_then_the_dispatcher_fills_the_concepts(self, api):
        # spec §8 '새 라우터 API 를 가짜 LLM 으로 끝까지' — 이어가기가 넣은 생성을 Task 9 의 디스패처가 집고,
        # Task 8 의 실행기가 가짜 LLM 답을 읽고, 결과 적용·닫기 뒤 연구 조회에 개념이 보인다
        from services.llm_client import LLMResult
        from services.research_work import dispatch
        from services.research_work.apply import apply_result
        from services.research_work.executors import EXECUTORS
        from services.research_work.generate import run_generation

        jid = _job(api.engine, snapshot=SNAPSHOT, report=REPORT, plan=["독서 격차의 원인"])

        res = api.client.post(f"/api/research/{jid}/work/continue", headers=A)

        assert res.status_code == 200
        assert [(g["status"], g["position"]) for g in res.json()["generations"]] == [
            ("queued", POSITION)]
        models: list[str] = []

        async def _chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            models.append(model)
            return LLMResult(content='{"concepts": ["독서 격차", "청소년"]}', finish_reason="stop")

        async def _work_once():
            db = AsyncSessionOverSync(api.engine)
            try:
                gen = await dispatch.pick_next(db)
                gen_id = gen.id
                result = await run_generation(EXECUTORS[gen.kind], dict(gen.input), chat_fn=_chat)
                payload = await apply_result(db, gen, result.output)
                closed = await dispatch.finish(
                    db, gen_id, status="done", model=result.model, error=None,
                    output={**result.output, "attempts": result.attempts},
                )
                return gen_id, payload, closed
            finally:
                await db.close()

        gen_id, payload, closed = asyncio.run(_work_once())

        assert closed and payload == {"concepts": ["독서 격차", "청소년"]}
        assert len(models) == 1
        work = api.client.get(f"/api/research/{jid}/work").json()
        assert work["concepts"] == ["독서 격차", "청소년"]
        assert work["generations"] == [{"id": gen_id, "kind": "concepts", "target": None,
                                        "status": "done", "model": models[0], "error": None,
                                        "position": None, "eta_sec": None, "others_ahead": False}]


class TestEventShape:
    def test_worker_generation_event_uses_the_same_keys(self):
        # 워커(Task 9)가 끝난 생성을 알리는 generation 이벤트와 이 라우터의 것이 같은 키여야 한다 — relay 는
        # {"kind": 이벤트 종류, **payload} 로 실어 페이로드의 "kind" 가 이벤트 종류를 덮어쓴다.
        # 워커는 celery 를 끌어오므로 import 하지 않고 소스에서 publish_work(…, "generation", {…}) 를 찾는다
        source = (Path(__file__).resolve().parents[1] / "workers" / "research_work_tasks.py").read_text(
            encoding="utf-8")
        payloads = [
            {key.value for key in node.args[2].keys}
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "publish_work"
            and len(node.args) == 3 and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "generation" and isinstance(node.args[2], ast.Dict)
        ]
        assert payloads == [{"gen_id", "gen_kind", "target", "status", "model", "result"}]


class TestAppWiring:
    def test_main_includes_research_work_router(self):
        # 테스트는 라우터를 직접 붙인다 — main.py 등록을 빠뜨려도 위 테스트는 모두 통과한다
        tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
        imported = {
            (node.module, alias.name, alias.asname)
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        included = {
            node.args[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "include_router"
        }
        assert ("api.research_work", "router", "research_work_router") in imported
        assert "research_work_router" in included
