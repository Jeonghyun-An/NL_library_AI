"""test_book_search_history_session.py — 옛 검색 기록(search_history)의 세션 id 다루기.

search_history.session_id 는 UUID 칼럼이다. 운영 점검(2026-10-14)에서 uuid 가 아닌 x-session-id 로 부르면
- POST /api/books/search 는 기록 INSERT 가 실패해 경고만 남기고, 실패한 트랜잭션을 되돌리지 않은 채 끝났고
- GET /api/books/history/{session_id} 는 Postgres 가 uuid 로 못 읽어 500 을 돌려줬다.
이제 검색은 uuid 가 아닌 값을 '세션 없음'처럼 새 uuid 로 바꿔 기록하고, 기록 저장이 실패하면 되돌린다.
기록 조회는 uuid 가 아니면 DB 를 부르지 않고 400 이다.

pipeline.search 는 대역, DB 는 실행한 SQL·값을 적는 가짜 세션이다. async 테스트 없음.
"""
import importlib
import sys
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline_stub import stubbed_pipeline

_FORGET = ("api.book",)


class _FakeDb:
    def __init__(self, fail_insert: bool = False):
        self.calls: list[tuple[str, dict]] = []
        self.rollbacks = 0
        self.fail_insert = fail_insert

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.calls.append((sql, dict(params or {})))
        if self.fail_insert and "INSERT INTO search_history" in sql:
            raise RuntimeError("invalid input syntax for type uuid")

        class _Rows:
            def fetchall(self_inner):
                return []

        return _Rows()

    async def commit(self):
        pass

    async def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def make_client(monkeypatch):
    gen = stubbed_pipeline(monkeypatch)
    next(gen)
    for name in _FORGET:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    book = importlib.import_module("api.book")
    from core.deps import get_db
    from schemas.book import BookSearchResponse

    async def _search(query, **kwargs):
        return BookSearchResponse(query=query, rewritten_query=None, books=[], elapsed_ms=1.0)

    monkeypatch.setattr(book, "search", _search)

    def _make(db: _FakeDb):
        async def _db():
            yield db

        app = FastAPI()
        app.include_router(book.router)
        app.dependency_overrides[get_db] = _db
        return TestClient(app)

    yield _make
    for name in _FORGET:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)
    next(gen, None)


def _inserted_sid(db: _FakeDb) -> str:
    sids = [p["sid"] for sql, p in db.calls if "INSERT INTO search_history" in sql]
    assert len(sids) == 1
    return sids[0]


BODY = {"query": "조선시대 고전소설을 연구한 자료 찾아줘", "mode": "book", "top_k": 10}


def test_search_keeps_a_uuid_session_id(make_client):
    db = _FakeDb()
    sid = str(uuid.uuid4())
    make_client(db).post("/api/books/search", json=BODY, headers={"x-session-id": sid})
    assert _inserted_sid(db) == sid


@pytest.mark.parametrize("raw", ["postdeploy-check-20261014", "null", ""])
def test_search_replaces_a_non_uuid_session_id(make_client, raw):
    db = _FakeDb()
    headers = {"x-session-id": raw} if raw else {}
    res = make_client(db).post("/api/books/search", json=BODY, headers=headers)
    assert res.status_code == 200
    sid = _inserted_sid(db)
    assert sid != raw
    uuid.UUID(sid)  # 칼럼에 들어갈 수 있는 값


def test_failed_history_insert_is_rolled_back_and_search_still_answers(make_client):
    db = _FakeDb(fail_insert=True)
    res = make_client(db).post("/api/books/search", json=BODY, headers={"x-session-id": str(uuid.uuid4())})
    assert res.status_code == 200
    assert db.rollbacks == 1


def test_history_rejects_a_non_uuid_session_id_without_querying(make_client):
    db = _FakeDb()
    res = make_client(db).get("/api/books/history/postdeploy-check-20261014")
    assert res.status_code == 400
    assert db.calls == []


def test_history_answers_for_a_uuid_session_id(make_client):
    db = _FakeDb()
    res = make_client(db).get(f"/api/books/history/{uuid.uuid4()}")
    assert res.status_code == 200
    assert res.json() == []
