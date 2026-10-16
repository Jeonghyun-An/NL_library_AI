"""test_search_outage_api.py — 검색 계열 엔드포인트의 오류 응답과 LLM 사유 실패 표시(ai_failed).

검색 기반(Milvus·임베딩) 연결/조회 장애 → 503 {"detail": "검색 서버가 잠시 응답하지 않습니다. 잠시 뒤 다시 시도하세요",
"code": "search_unavailable"} — 소장자료 검색·논문 검색·상황별 추천·소장자료 관련 자료·논문 관련 자료. 전에는 500
'Internal Server Error'(JSON 아님)가 화면에 갔다. 코드 버그(TypeError 등)와 장애가 아닌 Milvus 오류(컬렉션 없음 등)는
503 으로 가리지 않고 500 internal_error 다.

상황별 추천(/api/scenario/recommend)·큐레이션(/api/books/curate)은 LLM 사유 생성이 실패하면 빈 사유로 채우고
ai_failed=true 를 싣는다(성공이면 false).

pipeline 은 대역(pipeline_stub) 위에서 올리고, 검색 함수만 갈아 장애를 낸다. 서지는 history_sqlite 의 SQLite 다.
async 테스트 없음.
"""
import importlib
import sys
import types

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.errors import SEARCH_UNAVAILABLE_DETAIL, install_error_handlers
from history_sqlite import AsyncSessionOverSync, add_book, make_engine
from milvus_errors import rpc_error
from models.search_history import SearchHistory
from pipeline_stub import stubbed_pipeline

_FORGET = ("api.book", "api.paper", "api.scenario")
SEARCH_503 = {"detail": SEARCH_UNAVAILABLE_DETAIL, "code": "search_unavailable"}


def _milvus_down():
    exceptions = pytest.importorskip("pymilvus.exceptions")
    return exceptions.MilvusException(code=2, message="Fail connecting to server on milvus:19530")


class _Api:
    def __init__(self, client, mods, monkeypatch):
        self.client, self.mods, self._mp = client, mods, monkeypatch

    def fail_search(self, module: str, name: str, exc: BaseException) -> list:
        """mods[module].name 을 exc 를 던지는 함수로 간다. 불린 기록을 돌려준다."""
        calls: list = []

        async def _raise(*args, **kwargs):
            calls.append((args, kwargs))
            raise exc

        self._mp.setattr(self.mods[module], name, _raise)
        return calls

    def search_returns(self, module: str, book_ids: list[str]):
        schemas = importlib.import_module("schemas.book")

        async def _search(query, **kwargs):
            return schemas.BookSearchResponse(
                query=query, books=[schemas.BookChunkGroup(book_id=b, best_score=0.9, chunks=[]) for b in book_ids],
                elapsed_ms=1.0,
            )

        self._mp.setattr(self.mods[module], "search", _search)


@pytest.fixture
def api(monkeypatch):
    gen = stubbed_pipeline(monkeypatch)
    next(gen)
    # 라우터들은 pipeline 을 머리에서 import 한다 — 대역 위에서 새로 올리고 끝나면 import 전 그대로 되돌린다
    for name in _FORGET:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    mods = {name.rpartition(".")[2]: importlib.import_module(name) for name in _FORGET}
    from core.deps import get_db

    engine = make_engine()
    SearchHistory.__table__.to_metadata(sa.MetaData()).create(engine)
    add_book(engine, "CNTS-1", title="조선후기 세태소설 연구", doc_type="literature")
    add_book(engine, "CNTS-2", title="한국 근대 소설", doc_type="literature")
    add_book(engine, "KCI_FI1", title="노인 우울 연구", doc_type="paper")

    async def _db():
        db = AsyncSessionOverSync(engine)
        try:
            yield db
        finally:
            await db.rollback()
            await db.close()

    app = FastAPI()
    install_error_handlers(app)
    for mod in mods.values():
        app.include_router(mod.router)
    app.dependency_overrides[get_db] = _db
    yield _Api(TestClient(app, raise_server_exceptions=False), mods, monkeypatch)
    for name in _FORGET:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)
    next(gen, None)


# ── B2: 검색 기반 장애 → 503 search_unavailable ─────────────
class TestSearchUnavailable:
    def test_book_search(self, api):
        calls = api.fail_search("book", "search", _milvus_down())
        resp = api.client.post("/api/books/search", json={"query": "조선 소설", "mode": "book", "top_k": 5})
        assert resp.status_code == 503
        assert resp.json() == SEARCH_503
        assert len(calls) == 1

    def test_book_search_connection_refused_without_pymilvus(self, api):
        api.fail_search("book", "search", ConnectionRefusedError(111, "Connection refused"))
        resp = api.client.post("/api/books/search", json={"query": "조선 소설"})
        assert resp.status_code == 503 and resp.json() == SEARCH_503

    def test_book_search_code_bug_is_500_not_503(self, api):
        # 코드 버그를 '잠시 뒤 다시'로 가리면 영영 낫지 않는 오류를 사용자가 계속 다시 누른다
        api.fail_search("book", "search", TypeError("'NoneType' object is not subscriptable"))
        resp = api.client.post("/api/books/search", json={"query": "조선 소설"})
        assert resp.status_code == 500
        assert resp.json()["code"] == "internal_error"

    def test_paper_search(self, api):
        api.fail_search("paper", "search", _milvus_down())
        resp = api.client.post("/api/papers/search", json={"query": "노인 우울"})
        assert resp.status_code == 503 and resp.json() == SEARCH_503

    def test_paper_search_grpc_deadline(self, api):
        # pymilvus 는 기한 초과를 날 grpc.RpcError(DEADLINE_EXCEEDED)로 다시 던진다
        api.fail_search("paper", "search", rpc_error("DEADLINE_EXCEEDED"))
        resp = api.client.post("/api/papers/search", json={"query": "노인 우울"})
        assert resp.status_code == 503 and resp.json() == SEARCH_503

    def test_paper_search_with_a_dropped_collection_is_500_not_503(self, api):
        # 컬렉션이 없어진 것 같은 영구 오류는 '잠시 뒤 다시'로 낫지 않는다 — 503 으로 가리지 않는다
        exceptions = pytest.importorskip("pymilvus.exceptions")
        api.fail_search("paper", "search",
                        exceptions.MilvusException(code=100, message="collection not found[collection=nl_lib_chunks]"))
        resp = api.client.post("/api/papers/search", json={"query": "노인 우울"})
        assert resp.status_code == 500 and resp.json()["code"] == "internal_error"

    def test_scenario_recommend(self, api):
        api.fail_search("scenario", "search", _milvus_down())
        resp = api.client.post("/api/scenario/recommend", json={"concern": "요즘 너무 지쳐요"})
        assert resp.status_code == 503 and resp.json() == SEARCH_503

    def test_book_related(self, api):
        calls = api.fail_search("book", "search_related_books", TimeoutError("timed out"))
        resp = api.client.get("/api/books/CNTS-1/related")
        assert resp.status_code == 503 and resp.json() == SEARCH_503
        assert len(calls) == 1

    def test_book_related_unknown_book_is_still_404(self, api):
        api.fail_search("book", "search_related_books", _milvus_down())
        resp = api.client.get("/api/books/CNTS-NOPE/related")
        assert resp.status_code == 404 and resp.json() == {"detail": "도서 없음: CNTS-NOPE"}

    def test_paper_related(self, api, monkeypatch):
        # paper_related 는 라우트 안에서 import 한다 — 모듈째 대역으로 꽂는다(진짜는 FlagEmbedding·pymilvus 를 문다)
        down = _milvus_down()

        async def _find(cnts_id, db, top_k=4):
            raise down

        fake = types.ModuleType("services.search.paper_related")
        fake.find_related_papers = _find
        monkeypatch.setitem(sys.modules, "services.search.paper_related", fake)
        resp = api.client.get("/api/papers/KCI_FI1/related")
        assert resp.status_code == 503 and resp.json() == SEARCH_503

    def test_a_working_search_is_untouched(self, api):
        api.search_returns("paper", [])
        resp = api.client.post("/api/papers/search", json={"query": "노인 우울"})
        assert resp.status_code == 200 and resp.json()["books"] == []


# ── B4: LLM 사유 실패 → ai_failed ───────────────────────────
class TestAiFailed:
    def _recommend(self, api, rec: dict):
        api.search_returns("scenario", ["CNTS-1", "CNTS-2"])

        async def _rec(concern, books):
            return rec

        api._mp.setattr(api.mods["scenario"], "recommend_books", _rec)
        return api.client.post("/api/scenario/recommend", json={"concern": "요즘 너무 지쳐요", "top_k": 2})

    def test_scenario_fallback_is_flagged(self, api):
        resp = self._recommend(api, {
            "intro": "", "ai_failed": True,
            "items": [{"book_id": "CNTS-1", "reason": "", "quote": ""}, {"book_id": "CNTS-2", "reason": "", "quote": ""}],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_failed"] is True
        assert [b["book_id"] for b in body["books"]] == ["CNTS-1", "CNTS-2"]   # 책은 그대로 보인다

    def test_scenario_success_is_not_flagged(self, api):
        resp = self._recommend(api, {
            "intro": "지친 마음에", "items": [{"book_id": "CNTS-1", "reason": "쉼", "quote": "q"}],
        })
        assert resp.status_code == 200 and resp.json()["ai_failed"] is False

    def _curate(self, api, monkeypatch, result: dict):
        async def _curate_books(intent, query, books):
            return result

        monkeypatch.setattr("services.search.curator.curate_books", _curate_books)
        return api.client.post("/api/books/curate", json={"query": "조선 소설", "book_ids": ["CNTS-1", "CNTS-2"]})

    def test_curation_fallback_is_flagged(self, api, monkeypatch):
        resp = self._curate(api, monkeypatch, {
            "intro": "", "ai_failed": True,
            "items": [{"book_id": "CNTS-1", "reason": ""}, {"book_id": "CNTS-2", "reason": ""}],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_failed"] is True and len(body["items"]) == 2

    def test_curation_success_is_not_flagged(self, api, monkeypatch):
        resp = self._curate(api, monkeypatch, {"intro": "두 권", "items": [{"book_id": "CNTS-1", "reason": "r"}]})
        assert resp.status_code == 200 and resp.json()["ai_failed"] is False
