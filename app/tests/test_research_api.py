"""test_research_api.py — 딥리서치 API 엔드포인트

요청은 TestClient 로 실제 FastAPI 라우팅을 거친다(본문 없는 POST·422 매핑은
라우팅을 거쳐야 드러난다). DB 는 대역이다 — research_jobs 의 UPDATE 는 WHERE 를
실제로 평가한다. approve·retry 가 status 조건 없이 덮어쓰는 회귀는 대역이 조건을
무시하면 안 잡힌다.

`redis`·`celery`·`kombu` 는 로컬 venv 에 없다. 미설치일 때만 더미를 꽂는다.
"""
import importlib
import json
import sys
import types
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BindParameter, BooleanClauseList


class _OperationalError(Exception):
    """kombu 미설치 환경용 대역 — 브로커 연결 실패."""


def _stub_missing(monkeypatch, name: str, module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module)


# ── DB 대역 ────────────────────────────────────────────────────────────
def _matches(clause, row: dict) -> bool:
    if clause is None:
        return True
    if isinstance(clause, BooleanClauseList):
        return all(_matches(c, row) for c in clause.clauses)
    left = row.get(clause.left.key)
    right = getattr(clause.right, "value", None)
    op = clause.operator
    if op is operators.eq:
        return left == right
    if op is operators.in_op:
        return left in right
    if op is operators.is_not:
        return left is not None
    raise AssertionError(f"대역이 모르는 연산자: {op}")


class _Result:
    def __init__(self, *, rowcount: int = 0, rows=None, scalar=None):
        self.rowcount = rowcount
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def scalar_one(self):
        return self._scalar


class _FakeDB:
    """research_jobs 를 dict 로 들고 get·조건부 UPDATE·개수 조회·step 조회를 흉내 낸다.

    sql 에는 실행한 문장과 COMMIT·ROLLBACK 을 순서대로 남긴다 — 잠금과 검사가 같은
    트랜잭션 안에 있는지는 순서로만 드러난다.
    """

    def __init__(self):
        self.jobs: dict[uuid.UUID, dict] = {}
        self.steps: list[SimpleNamespace] = []
        self.sql: list[str] = []
        self.after_get = None       # 읽은 직후에 끼어드는 경쟁 요청을 흉내 낸다

    def add_job(self, **fields) -> uuid.UUID:
        jid = fields.pop("id", None) or uuid.uuid4()
        row = {
            "id": jid, "question": "공공도서관 서비스 품질 평가", "status": "created",
            "params": {"max_subquestions": 3}, "plan": None, "report": None,
            "stage": "created", "state_snapshot": None, "last_error": None,
            "created_by": None, "created_at": None, "started_at": None, "finished_at": None,
        }
        row.update(fields)
        self.jobs[jid] = row
        return jid

    async def get(self, model, pk):
        row = self.jobs.get(pk)
        job = SimpleNamespace(**row) if row is not None else None
        if self.after_get is not None:
            self.after_get(pk)
        return job

    def add(self, obj):
        self.jobs[obj.id] = {
            "id": obj.id, "question": obj.question, "status": obj.status or "created",
            "params": obj.params, "plan": None, "report": None, "stage": "created",
            "state_snapshot": None, "last_error": None, "created_by": obj.created_by,
            "created_at": None, "started_at": None, "finished_at": None,
        }

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append(sql)
        table = getattr(getattr(stmt, "table", None), "name", None)
        if sql.startswith("SELECT pg_advisory_xact_lock"):
            return _Result()
        if sql.startswith("SELECT count(*)") and "FROM research_jobs" in sql:
            n = sum(1 for row in self.jobs.values() if _matches(stmt.whereclause, row))
            return _Result(scalar=n)
        if getattr(stmt, "is_update", False) and table == "research_jobs":
            n = 0
            for row in self.jobs.values():
                if _matches(stmt.whereclause, row):
                    for key, value in stmt._values.items():
                        row[getattr(key, "key", key)] = (
                            value.value if isinstance(value, BindParameter) else value
                        )
                    n += 1
            return _Result(rowcount=n)
        if sql.startswith("SELECT research_steps"):
            return _Result(rows=self.steps)
        raise AssertionError(f"대역이 모르는 문장: {stmt}")

    async def commit(self):
        self.sql.append("COMMIT")

    async def rollback(self):
        self.sql.append("ROLLBACK")


class _FakeCelery:
    def __init__(self):
        self.sent: list[tuple[str, list]] = []
        self.fail = False

    def send_task(self, name, args=None, **kw):
        if self.fail:
            raise sys.modules["kombu.exceptions"].OperationalError("broker down")
        self.sent.append((name, args))


class _Api:
    def __init__(self, client, db, celery, published, research, events):
        self.client = client
        self.db = db
        self.celery = celery
        self.published = published
        self.research = research
        self.events = events

    def announced(self) -> list[tuple[str, dict]]:
        return [(kind, payload) for _, kind, payload in self.events]


_CACHED = ("api.research", "services.research.relay")


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 있던 키만 되돌린다. 원래 없던 키는 기록이 남지 않아
    여기서 새로 import 한 모듈(더미 redis 에 묶인 채)이 teardown 뒤에도 남는다.
    setitem·setattr 은 원래 없던 키·속성이면 되돌릴 때 지우므로, 값을 한 번 꽂아 기록을
    남긴 뒤 뺀다. 부모 속성까지 되돌리는 이유: `from pkg import mod` 와 문자열 경로
    monkeypatch 는 sys.modules 보다 부모 속성을 먼저 본다.
    """
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


def _load_api(monkeypatch, celery: "_FakeCelery"):
    """더미 위에서 api.research 를 새로 import 한다. 끝나면 import 전 그대로 되돌린다."""
    for name in ("redis", "redis.asyncio"):
        _stub_missing(monkeypatch, name, MagicMock())
    kombu = types.ModuleType("kombu")
    kombu_exc = types.ModuleType("kombu.exceptions")
    kombu_exc.OperationalError = _OperationalError
    _stub_missing(monkeypatch, "kombu", kombu)
    _stub_missing(monkeypatch, "kombu.exceptions", kombu_exc)

    celery_mod = types.ModuleType("workers.celery_app")
    celery_mod.celery_app = celery
    monkeypatch.setitem(sys.modules, "workers.celery_app", celery_mod)

    _forget_on_teardown(monkeypatch, _CACHED)
    return importlib.import_module("api.research")


@pytest.fixture
def api(monkeypatch):
    celery = _FakeCelery()
    research = _load_api(monkeypatch, celery)
    from core.deps import get_db

    published: list[tuple] = []

    async def _publish_terminal(job_id, status, error=None):
        published.append((job_id, status, error))

    monkeypatch.setattr(research, "publish_terminal", _publish_terminal)

    events: list[tuple] = []

    async def _publish(job_id, kind, payload):
        events.append((job_id, kind, payload))

    monkeypatch.setattr(research, "publish", _publish)

    db = _FakeDB()
    app = FastAPI()
    app.include_router(research.router)
    app.dependency_overrides[get_db] = lambda: db
    return _Api(TestClient(app), db, celery, published, research, events)


def _frames(body: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in body.splitlines()
            if line.startswith("data: ")]


class TestJobId:
    def test_malformed_job_id_is_422(self, api):
        assert api.client.get("/api/research/not-a-uuid").status_code == 422

    def test_non_canonical_uuid_is_normalized(self, api):
        jid = api.db.add_job(status="completed")
        res = api.client.get(f"/api/research/{str(jid).upper()}")
        assert res.status_code == 200
        assert res.json()["job_id"] == str(jid)


class TestCreate:
    def test_create_queues_plan_task(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"})
        assert res.status_code == 200
        jid = res.json()["job_id"]
        assert api.celery.sent == [("tasks.plan_deep_research", [jid])]

    def test_broker_failure_does_not_strand_the_job(self, api):
        """커밋 뒤 send_task 가 실패하면 잡이 created 로 영원히 남는다."""
        api.celery.fail = True
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"})
        assert res.status_code == 503
        (row,) = api.db.jobs.values()
        assert row["status"] == "failed" and row["last_error"]

    def test_operator_can_turn_off_topic_exclusion_off_per_job(self, api):
        # 운영에서 결과가 나쁘면 재배포 없이 끈다(spec §11-3 의 curl) — 기본값에 합쳐 저장한다
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"exclude_off_topic": 0}})
        assert res.status_code == 200
        (row,) = api.db.jobs.values()
        assert row["params"]["exclude_off_topic"] == 0
        assert row["params"]["max_evidence"] == 90

    def test_off_topic_exclusion_other_than_zero_or_one_is_422(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"exclude_off_topic": 2}})
        assert res.status_code == 422

    def test_operator_can_pick_the_critic_criterion_per_job(self, api):
        # 평가 도구(scripts/research_eval)가 같은 질문을 critic_scope 0·1 두 갈래 잡으로 만든다
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"critic_scope": 1}})
        assert res.status_code == 200
        (row,) = api.db.jobs.values()
        assert row["params"]["critic_scope"] == 1
        assert row["params"]["exclude_off_topic"] == 1

    def test_critic_scope_other_than_zero_or_one_is_422(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"critic_scope": 2}})
        assert res.status_code == 422
        assert "허용 범위" in res.json()["detail"]      # 모르는 키가 아니라 값 검사에서 거부


class TestApprove:
    def test_approve_sets_status_the_worker_claims(self, api):
        """상태를 그대로 두고 태스크만 던지면 워커의 _claim 이 0행을 잡아 영원히 skipped 다."""
        from models.research import RUNNABLE_STATUSES
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A", "가설 B"])

        res = api.client.post(f"/api/research/{jid}/approve", json={})

        assert res.status_code == 200
        assert api.db.jobs[jid]["status"] in RUNNABLE_STATUSES
        assert api.celery.sent == [("tasks.run_deep_research", [str(jid)])]

    def test_approve_without_body_uses_proposed_plan(self, api):
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])
        res = api.client.post(f"/api/research/{jid}/approve")
        assert res.status_code == 200
        assert res.json()["plan"] == ["가설 A"]

    def test_edited_plan_is_stripped_and_saved(self, api):
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])
        res = api.client.post(f"/api/research/{jid}/approve",
                              json={"plan": ["  새 하위질문 1 ", "새 하위질문 2"]})
        assert res.status_code == 200
        assert api.db.jobs[jid]["plan"] == ["새 하위질문 1", "새 하위질문 2"]

    @pytest.mark.parametrize("plan", [
        [],                                      # 비어 있음
        ["하위1", "하위2", "하위3", "하위4"],     # max_subquestions(3) 초과
        ["하위1", "   "],                         # 공백 항목 → 빈 쿼리 검색
        ["하위1", "x" * 301],                     # 항목 길이 상한
        ["독서  격차", "독서 격차"],              # 공백만 다른 중복
        ["Reading Gap", "reading gap"],           # 대소문자만 다른 중복
    ])
    def test_invalid_plan_is_422(self, api, plan):
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])
        res = api.client.post(f"/api/research/{jid}/approve", json={"plan": plan})
        assert res.status_code == 422
        assert api.db.jobs[jid]["status"] == "awaiting_approval"
        assert api.celery.sent == []

    def test_wrong_status_is_409(self, api):
        jid = api.db.add_job(status="planning")
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 409

    def test_missing_job_is_404(self, api):
        assert api.client.post(f"/api/research/{uuid.uuid4()}/approve").status_code == 404

    def test_cancel_racing_approve_wins(self, api):
        """approve 가 읽은 직후 cancel 이 커밋되면, approve 는 덮어쓰지 말고 409 여야 한다."""
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        def _cancel(pk):
            api.db.jobs[pk]["status"] = "canceled"

        api.db.after_get = _cancel
        res = api.client.post(f"/api/research/{jid}/approve")

        assert res.status_code == 409
        assert api.db.jobs[jid]["status"] == "canceled"
        assert api.celery.sent == []

    def test_broker_failure_reverts_to_awaiting_approval(self, api):
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])
        api.celery.fail = True

        res = api.client.post(f"/api/research/{jid}/approve", json={"plan": ["바꾼 계획"]})

        assert res.status_code == 503
        # 다시 승인할 수 있어야 한다 — approved 에 남으면 approve 는 409, 워커는 안 온다
        assert api.db.jobs[jid]["status"] == "awaiting_approval"
        assert api.db.jobs[jid]["plan"] == ["가설 A"]


class TestRetry:
    def test_retry_keeps_checkpoint(self, api):
        snap = {"subquestions": []}
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             state_snapshot=snap, last_error="종합 실패")

        res = api.client.post(f"/api/research/{jid}/retry")

        assert res.status_code == 200
        row = api.db.jobs[jid]
        assert row["status"] == "queued" and row["last_error"] is None
        assert row["stage"] == "explored" and row["state_snapshot"] is snap
        assert api.celery.sent == [("tasks.run_deep_research", [str(jid)])]

    def test_retry_without_plan_is_409(self, api):
        jid = api.db.add_job(status="failed", plan=None)
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 409
        assert api.celery.sent == []

    def test_retry_non_failed_is_409(self, api):
        jid = api.db.add_job(status="completed", plan=["가"])
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 409

    def test_broker_failure_reverts_to_failed(self, api):
        jid = api.db.add_job(status="failed", plan=["가"], last_error="종합 실패")
        api.celery.fail = True

        assert api.client.post(f"/api/research/{jid}/retry").status_code == 503
        assert api.db.jobs[jid]["status"] == "failed"
        assert api.db.jobs[jid]["last_error"] == "종합 실패"


def _queue(api, monkeypatch, name: str) -> None:
    monkeypatch.setattr(api.research, "get_settings", lambda: SimpleNamespace(RESEARCH_QUEUE=name))


class TestSharedQueueRunSlot:
    """적재와 큐를 나눠 쓰는 동안(RESEARCH_QUEUE 기본값 q_llm) 실행은 한 번에 한 잡이다.

    딥리서치 실행은 적재 요약·마무리와 같은 celery-llm 슬롯(4개)을 잡마다 최대 25분
    쥔다. 여럿이 쥐면 슬롯을 기다리는 적재 아이템이 단계 타임아웃을 넘겨 stale 복구되고,
    옛 체인과 새 체인이 겹쳐 논문 본문 청크가 초록으로 덮일 수 있다(함정 16번).
    """

    @pytest.mark.parametrize("busy", ["running", "approved", "queued"])
    def test_approve_is_429_while_another_run_holds_the_slot(self, api, monkeypatch, busy):
        """approved·queued 도 센다 — 워커가 아직 안 집었을 뿐 이미 큐에 들어간 실행이다.
        running 만 세면 몰아서 승인한 잡이 전부 통과한다."""
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status=busy, plan=["가"])
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        res = api.client.post(f"/api/research/{jid}/approve")

        assert res.status_code == 429
        # 앞 잡이 끝나면 다시 승인할 수 있어야 한다
        assert api.db.jobs[jid]["status"] == "awaiting_approval"
        assert api.celery.sent == []

    def test_retry_is_429_while_another_run_holds_the_slot(self, api, monkeypatch):
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status="running", plan=["가"])
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             last_error="종합 실패")

        res = api.client.post(f"/api/research/{jid}/retry")

        assert res.status_code == 429
        row = api.db.jobs[jid]
        assert row["status"] == "failed" and row["last_error"] == "종합 실패"
        assert api.celery.sent == []

    @pytest.mark.parametrize("idle", [
        "created", "planning", "awaiting_approval", "completed", "failed", "canceled",
    ])
    def test_jobs_without_a_run_slot_do_not_block(self, api, monkeypatch, idle):
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status=idle, plan=["가"])
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200

    def test_state_errors_come_before_the_slot_check(self, api, monkeypatch):
        """재시도할 수 없는 잡에 429 를 주면 '기다리면 된다'로 읽힌다."""
        _queue(api, monkeypatch, "q_llm")
        api.db.add_job(status="running", plan=["가"])
        jid = api.db.add_job(status="completed", plan=["가"])

        assert api.client.post(f"/api/research/{jid}/retry").status_code == 409

    def test_slot_is_counted_under_a_lock_in_the_transition_transaction(self, api, monkeypatch):
        """동시에 온 두 승인이 서로 커밋 전 상태를 보고 둘 다 통과하면 상한이 뚫린다.
        잠금을 잡은 뒤 세고, 같은 트랜잭션에서 전이해 그 커밋이 잠금을 푼다."""
        _queue(api, monkeypatch, "q_llm")
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200

        sql = api.db.sql
        lock = next(i for i, s in enumerate(sql) if "pg_advisory_xact_lock" in s)
        count = next(i for i, s in enumerate(sql) if s.startswith("SELECT count(*)"))
        upd = next(i for i, s in enumerate(sql) if s.startswith("UPDATE research_jobs"))
        assert lock < count < upd
        assert not {"COMMIT", "ROLLBACK"} & set(sql[lock:upd])

    def test_dedicated_queue_lets_runs_wait_in_line(self, api, monkeypatch):
        """전용 워커(concurrency 1)는 뒤 잡을 approved 로 줄 세울 뿐 적재 슬롯을 먹지 않는다."""
        _queue(api, monkeypatch, "q_research")
        api.db.add_job(status="running", plan=["가"])
        jid = api.db.add_job(status="awaiting_approval", plan=["가설 A"])

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200
        assert not any("pg_advisory_xact_lock" in s for s in api.db.sql)


class TestCancel:
    def test_cancel_running_job_publishes_terminal(self, api):
        jid = api.db.add_job(status="running")

        res = api.client.post(f"/api/research/{jid}/cancel")

        assert res.status_code == 200
        assert api.db.jobs[jid]["status"] == "canceled"
        # 워커가 없는 상태에서 취소해도 스트림이 하트비트(15초)를 기다리지 않고 닫힌다
        assert api.published == [(jid, "canceled", None)]

    def test_cancel_missing_job_is_404(self, api):
        assert api.client.post(f"/api/research/{uuid.uuid4()}/cancel").status_code == 404

    def test_cancel_finished_job_is_409(self, api):
        jid = api.db.add_job(status="completed")
        assert api.client.post(f"/api/research/{jid}/cancel").status_code == 409
        assert api.published == []


class TestStream:
    def test_finished_job_sends_snapshot_then_terminal(self, api):
        jid = api.db.add_job(status="failed", last_error="모든 하위질문 탐색이 오류로 실패했다")

        frames = _frames(api.client.get(f"/api/research/{jid}/stream").text)

        from services.research.relay import terminal_event
        assert frames[0]["kind"] == "snapshot"
        # 워커가 흘리는 실패 이벤트와 같은 모양이어야 한다 — done+status 로 오면 안 된다
        assert frames[1] == terminal_event("failed", "모든 하위질문 탐색이 오류로 실패했다")
        assert len(frames) == 2

    @pytest.mark.parametrize("status,kind", [("completed", "done"), ("canceled", "canceled")])
    def test_terminal_kind_follows_status(self, api, status, kind):
        jid = api.db.add_job(status=status)
        frames = _frames(api.client.get(f"/api/research/{jid}/stream").text)
        assert frames[-1] == {"kind": kind, "status": status}

    def test_subscribes_on_the_canonical_channel(self, api, monkeypatch):
        """워커는 str(uuid) 채널에 쓴다. 대문자 경로로 붙어도 같은 채널을 구독해야 한다."""
        jid = api.db.add_job(status="running")
        seen = {}

        async def _subscribe(job_id):
            seen["job_id"] = job_id
            yield {"kind": "search", "subq_idx": 0}
            yield {"kind": "done", "status": "completed"}

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        frames = _frames(api.client.get(f"/api/research/{str(jid).upper()}/stream").text)

        assert str(seen["job_id"]) == str(jid)
        assert [f["kind"] for f in frames] == ["snapshot", "search", "done"]

    def test_heartbeat_detects_termination_with_same_shape(self, api, monkeypatch):
        jid = api.db.add_job(status="running")

        async def _subscribe(job_id):
            yield None

        async def _job_status(job_uuid):
            return "canceled", "planned", None, True

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        monkeypatch.setattr(api.research, "_job_status", _job_status)
        frames = _frames(api.client.get(f"/api/research/{jid}/stream").text)

        assert frames[-1] == {"kind": "canceled", "status": "canceled"}


_PLAN = ["초등 독서 효과", "중등 독서 효과"]
_CANCELED = {"kind": "canceled", "status": "canceled"}
_PLAN_DONE_EVENT = {"kind": "step", "seq": 1, "step_kind": "plan", "subq_idx": None,
                    "title": "연구 계획 수립", "detail": None, "status": "done",
                    "result": {"subquestions": _PLAN}}
_AWAITING_EVENT = {"kind": "status", "status": "awaiting_approval", "stage": "planned"}


class TestHeartbeatStatus:
    """스냅샷을 읽은 뒤 구독이 붙기 전에 나간 이벤트는 중계되지 않는다. 계획은 1초 안에
    끝나므로 plan 단계 done(계획 원안)과 awaiting_approval 이 함께 그 틈에 빠지기 쉽다.
    상태만 되살리면 화면은 승인 대기로 가도 승인할 계획이 없다 — 하트비트가 DB 와 맞춰
    보고, 어긋나면 스냅샷을 다시 보낸다."""

    def _stream(self, api, monkeypatch, *, live, job_status=None) -> list[dict]:
        """live 의 dict 는 중계된 이벤트, None 은 하트비트, 호출 가능한 값은 중계되지 않은
        채 DB 에만 남은 워커의 한 걸음(구독이 붙기 전에 publish 된 것)이다."""
        jid = api.db.add_job(status="planning", stage="created")
        api.db.steps = [SimpleNamespace(seq=1, kind="plan", subq_idx=None, title="연구 계획 수립",
                                        detail=None, status="running", result=None)]

        async def _subscribe(job_id):
            for item in live:
                if callable(item):
                    item(api.db.jobs[jid])
                    continue
                yield item

        async def _job_status(job_uuid):
            row = api.db.jobs[job_uuid]
            return row["status"], row["stage"], row["last_error"], bool(row["plan"])

        class _Session:
            async def __aenter__(self):
                return api.db

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        monkeypatch.setattr(api.research, "_job_status", job_status or _job_status)
        monkeypatch.setattr(api.research, "AsyncSessionLocal", _Session)
        return _frames(api.client.get(f"/api/research/{jid}/stream").text)

    def _plan_done(self, api):
        """워커의 계획 마무리 — plan 단계를 닫고(원안) 승인 대기로 전이한다."""
        def step(row):
            api.db.steps[0].status = "done"
            api.db.steps[0].result = {"subquestions": _PLAN}
            row.update(status="awaiting_approval", stage="planned", plan=_PLAN)
        return step

    def test_plan_finished_in_the_gap_is_recovered_with_the_plan(self, api, monkeypatch):
        frames = self._stream(api, monkeypatch,
                              live=[self._plan_done(api), None, None, _CANCELED])

        assert [f["kind"] for f in frames] == ["snapshot", "snapshot", "canceled"]
        first, recovered = frames[0], frames[1]
        assert first["job"]["plan"] is None and first["steps"][0]["result"] is None
        assert recovered["job"] == {"status": "awaiting_approval", "stage": "planned", "plan": _PLAN}
        assert recovered["steps"][0]["result"] == {"subquestions": _PLAN}
        # 연결 직후 스냅샷과 같은 모양이어야 화면이 같은 경로로 받는다
        assert recovered.keys() == first.keys() and recovered["job"].keys() == first["job"].keys()

    def test_status_relayed_but_plan_missed_is_recovered(self, api, monkeypatch):
        # plan 단계 done 은 틈에 빠지고 몇 ms 뒤의 awaiting_approval 만 중계된 경우 —
        # 상태는 맞지만 화면에 계획이 없다
        frames = self._stream(api, monkeypatch,
                              live=[self._plan_done(api), _AWAITING_EVENT, None, None, _CANCELED])

        assert [f["kind"] for f in frames] == ["snapshot", "status", "snapshot", "canceled"]
        assert frames[2]["job"]["plan"] == _PLAN

    def test_unchanged_status_stays_quiet(self, api, monkeypatch):
        frames = self._stream(api, monkeypatch, live=[None, _CANCELED])
        assert [f["kind"] for f in frames] == ["snapshot", "canceled"]

    def test_relayed_plan_and_status_are_not_repeated(self, api, monkeypatch):
        frames = self._stream(
            api, monkeypatch,
            live=[self._plan_done(api), _PLAN_DONE_EVENT, _AWAITING_EVENT, None, _CANCELED],
        )
        assert [f["kind"] for f in frames] == ["snapshot", "step", "status", "canceled"]

    def test_termination_between_the_two_reads_sends_the_terminal_frame(self, api, monkeypatch):
        # 하트비트 조회는 승인 대기였는데 스냅샷을 다시 읽을 때는 이미 취소됐다 —
        # 끝난 상태를 스냅샷으로 보내면 화면이 스트림을 닫지 않는다
        def canceled(row):
            row.update(status="canceled", stage="planned", plan=_PLAN)

        async def _stale(job_uuid):
            return "awaiting_approval", "planned", None, True

        frames = self._stream(api, monkeypatch, live=[canceled, None], job_status=_stale)

        assert [f["kind"] for f in frames] == ["snapshot", "canceled"]
        assert frames[1] == _CANCELED


class TestCreatedBy:
    """잡에 브라우저 ID 를 남긴다(research_jobs.created_by) — 누가 만든 잡인지의 유일한 근거다."""

    def _row(self, api, res) -> dict:
        return api.db.jobs[uuid.UUID(res.json()["job_id"])]

    def test_browser_id_header_fills_created_by(self, api):
        sid = str(uuid.uuid4())
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"},
                              headers={"x-session-id": sid})
        assert res.status_code == 200
        assert self._row(api, res)["created_by"] == sid

    def test_missing_header_still_creates_the_job(self, api):
        # 기록 API 와 달리 필수가 아니다 — 헤더 없는 curl 시연·옛 화면이 그대로 돌아야 한다
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"})
        assert res.status_code == 200
        assert self._row(api, res)["created_by"] is None

    def test_malformed_header_is_ignored(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"},
                              headers={"x-session-id": "not-a-uuid"})
        assert res.status_code == 200
        assert self._row(api, res)["created_by"] is None


class TestGetFields:
    _T0 = datetime(2026, 9, 26, 1, 2, 3, tzinfo=timezone.utc)

    def test_times_and_params_are_returned(self, api):
        jid = api.db.add_job(status="completed", params={"max_subquestions": 3},
                             created_at=self._T0, started_at=self._T0.replace(minute=3),
                             finished_at=self._T0.replace(minute=9))
        body = api.client.get(f"/api/research/{jid}").json()
        assert body["created_at"] == "2026-09-26T01:02:03+00:00"
        assert body["started_at"] == "2026-09-26T01:03:03+00:00"
        assert body["finished_at"] == "2026-09-26T01:09:03+00:00"
        assert body["params"] == {"max_subquestions": 3}

    def test_times_not_reached_yet_are_null(self, api):
        jid = api.db.add_job(status="created", created_at=self._T0)
        body = api.client.get(f"/api/research/{jid}").json()
        assert body["started_at"] is None and body["finished_at"] is None

    def test_creator_is_not_exposed(self, api):
        """조회에는 소유 확인이 없다 — 링크만 알면 누구나 여는 응답에 남의 브라우저 ID 가
        실리면 그걸 헤더에 넣어 그 사람의 기록을 읽을 수 있다."""
        jid = api.db.add_job(status="completed", created_by=str(uuid.uuid4()))
        assert "created_by" not in api.client.get(f"/api/research/{jid}").json()


_ROUNDS = [{"round": 1, "query": "가", "found_chunks": 4, "new_papers": 3,
            "verdict": "insufficient", "note": "부족", "next_query": "가 보완"}]


def _search_step():
    return SimpleNamespace(seq=1, kind="search", subq_idx=0, title="가", detail="검색 중",
                           status="done", result={"rounds": _ROUNDS})


class TestSnapshot:
    """재접속한 화면은 스냅샷만으로 지금까지의 장면을 복원한다."""

    def test_snapshot_carries_step_results_and_job_state(self, api):
        jid = api.db.add_job(status="completed", stage="synthesized", plan=["가"])
        api.db.steps = [_search_step()]

        snap = _frames(api.client.get(f"/api/research/{jid}/stream").text)[0]

        assert snap["job"] == {"status": "completed", "stage": "synthesized", "plan": ["가"]}
        assert snap["steps"][0]["result"] == {"rounds": _ROUNDS}

    def test_snapshot_steps_match_get(self, api):
        # 새로고침한 화면(GET)과 재접속한 화면(스냅샷)이 같은 모양을 받아야 한다
        jid = api.db.add_job(status="completed", stage="synthesized", plan=["가"])
        api.db.steps = [_search_step()]

        snap = _frames(api.client.get(f"/api/research/{jid}/stream").text)[0]

        assert snap["steps"] == api.client.get(f"/api/research/{jid}").json()["steps"]


class TestSnapshotCounters:
    """카운터 이벤트는 저장되지 않는다 — 재접속한 화면은 스냅샷의 job.counters 로 채운다."""

    _EARLY = {"papers_reviewed": 5, "evidence_adopted": 2, "rechecks": 0}
    _LATE = {"papers_reviewed": 9, "evidence_adopted": 4, "rechecks": 1}

    @staticmethod
    def _step(seq, result):
        return SimpleNamespace(seq=seq, kind="search", subq_idx=seq, title="가", detail=None,
                               status="done", result=result)

    @staticmethod
    def _snapshot(api, monkeypatch, jid) -> dict:
        async def _subscribe(job_id):
            yield {"kind": "canceled", "status": "canceled"}

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        return _frames(api.client.get(f"/api/research/{jid}/stream").text)[0]

    def test_running_job_takes_the_latest_saved_counters(self, api, monkeypatch):
        jid = api.db.add_job(status="running", stage="planned", plan=["가", "나", "다"])
        api.db.steps = [self._step(1, {"counters": self._EARLY}),
                        self._step(2, {"counters": self._LATE}), self._step(3, {})]

        assert self._snapshot(api, monkeypatch, jid)["job"]["counters"] == self._LATE

    def test_finished_job_takes_report_stats(self, api):
        jid = api.db.add_job(status="completed", stage="synthesized", plan=["가"],
                             report={"stats": self._EARLY})
        api.db.steps = [self._step(1, {"counters": self._LATE})]

        snap = _frames(api.client.get(f"/api/research/{jid}/stream").text)[0]

        assert snap["job"]["counters"] == self._EARLY

    def test_no_counters_yet_leaves_the_key_out(self, api, monkeypatch):
        jid = api.db.add_job(status="running", stage="planned", plan=["가"])
        api.db.steps = [self._step(1, {})]

        assert "counters" not in self._snapshot(api, monkeypatch, jid)["job"]


class TestStatusEvents:
    """승인·재시도는 처리 즉시 status 를 발행한다 — 스트림에 붙은 화면이 폴링 없이 따라온다."""

    def test_approve_announces_approved(self, api):
        jid = api.db.add_job(status="awaiting_approval", stage="planned", plan=["가설 A"])
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200
        assert api.announced() == [("status", {"status": "approved", "stage": "planned"})]

    def test_approve_is_announced_before_the_worker_can_claim(self, api):
        """큐에 넣은 뒤에 알리면 워커가 먼저 낸 running 뒤에 approved 가 도착해
        화면이 한 단계 뒤로 간다."""
        jid = api.db.add_job(status="awaiting_approval", stage="planned", plan=["가설 A"])
        at_send = []
        send = api.celery.send_task

        def _send(name, args=None, **kw):
            at_send.append(api.announced())
            return send(name, args, **kw)

        api.celery.send_task = _send
        api.client.post(f"/api/research/{jid}/approve")

        assert at_send == [[("status", {"status": "approved", "stage": "planned"})]]

    def test_broker_failure_announces_the_reverted_status(self, api):
        jid = api.db.add_job(status="awaiting_approval", stage="planned", plan=["가설 A"])
        api.celery.fail = True

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 503
        assert api.announced() == [
            ("status", {"status": "approved", "stage": "planned"}),
            ("status", {"status": "awaiting_approval", "stage": "planned"}),
        ]

    def test_rejected_approve_announces_nothing(self, api):
        jid = api.db.add_job(status="planning")
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 409
        assert api.events == []

    def test_retry_announces_queued_with_stage(self, api):
        # stage=explored 면 화면이 "종합부터 다시"로 그린다
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             last_error="종합 실패")
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 200
        assert api.announced() == [("status", {"status": "queued", "stage": "explored"})]

    def test_retry_broker_failure_ends_with_the_old_failure(self, api):
        """되돌린 상태는 종료 상태다 — status 가 아니라 종료 프레임으로 알려야 스트림이 닫힌다."""
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             last_error="종합 실패")
        api.celery.fail = True

        assert api.client.post(f"/api/research/{jid}/retry").status_code == 503
        assert api.announced() == [("status", {"status": "queued", "stage": "explored"})]
        assert api.published == [(jid, "failed", "종합 실패")]


class TestLoaderIsolation:
    """_load_api 가 끝나면 sys.modules·부모 패키지 속성이 import 전 그대로여야 한다.

    더미 redis 에 묶인 api.research·relay 가 남으면 뒤에 도는 테스트가 더미 없이
    import 해도 그 모듈을 물려받는다 — 로컬에서만, 실행 순서에 따라 결과가 달라진다.
    """

    @staticmethod
    def _parent(name: str):
        parent, _, child = name.rpartition(".")
        return importlib.import_module(parent), child

    def test_modules_that_were_absent_are_gone_afterwards(self):
        with pytest.MonkeyPatch.context() as outer:
            for name in _CACHED:
                parent, child = self._parent(name)
                outer.delitem(sys.modules, name, raising=False)
                outer.delattr(parent, child, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                _load_api(mp, _FakeCelery())
            for name in _CACHED:
                parent, child = self._parent(name)
                assert name not in sys.modules
                assert not hasattr(parent, child), name

    def test_modules_that_were_loaded_come_back(self):
        originals = {name: types.ModuleType(name) for name in _CACHED}
        with pytest.MonkeyPatch.context() as outer:
            for name, module in originals.items():
                parent, child = self._parent(name)
                outer.setitem(sys.modules, name, module)
                outer.setattr(parent, child, module, raising=False)
            with pytest.MonkeyPatch.context() as mp:
                assert _load_api(mp, _FakeCelery()) is not originals["api.research"]
            for name, module in originals.items():
                parent, child = self._parent(name)
                assert sys.modules[name] is module
                assert getattr(parent, child) is module, name
