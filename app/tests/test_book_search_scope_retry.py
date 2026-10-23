"""도서 필터 검색이 0권일 때의 재시도 — 소장자료 검색(POST /api/books/search)·상황별 추천(POST /api/scenario/recommend).

예전에는 doc_scope 를 풀어 다시 찾았다(doc_type 스칼라가 없던 옛 인덱스 대비). 운영 2026-10-23 에 날짜 필터(LLM)가
'올리버 트위스트'를 2026년으로 읽어 도서가 0권이 되자, 범위를 푼 재시도가 2026년 논문 30편을 소장자료 결과로 보였다
(research/book-search-filter-recall). 이제 도서 범위는 그대로 두고 날짜 조건(발행 연도·정렬 — use_metadata_filter)을 빼고
다시 찾는다.

pipeline.search 는 대역(받은 인자를 적고 준비한 응답을 차례로 돌려준다), DB 는 서지가 없는 가짜 세션이다. async 테스트 없음.
"""
import ast
import importlib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline_stub import stubbed_pipeline

_FORGET = ("api.book", "api.scenario")


class _NoRowsDb:
    """서지 조회(get_by_cnts_id·get_by_cnts_ids)도 기록 저장도 빈 결과로 받는다."""

    async def execute(self, stmt, params=None):
        class _Rows:
            def scalar_one_or_none(self_inner):
                return None

            def scalars(self_inner):
                return self_inner

            def all(self_inner):
                return []

            def fetchall(self_inner):
                return []

        return _Rows()

    async def commit(self):
        pass

    async def rollback(self):
        pass


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
    scenario = importlib.import_module("api.scenario")
    from core.deps import get_db
    from schemas.book import BookChunkGroup, BookSearchResponse

    def _make(*answers):
        """answers: 호출마다 돌려줄 book_id 목록. 받은 인자는 calls 에 쌓인다."""
        calls: list[dict] = []
        queue = list(answers)

        async def _search(query, **kwargs):
            calls.append(kwargs)
            books = [BookChunkGroup(book_id=b, best_score=0.5, chunks=[]) for b in queue.pop(0)]
            return BookSearchResponse(query=query, rewritten_query=None, books=books, elapsed_ms=1.0)

        monkeypatch.setattr(book, "search", _search)
        monkeypatch.setattr(scenario, "search", _search)

        async def _db():
            yield _NoRowsDb()

        app = FastAPI()
        app.include_router(book.router)
        app.include_router(scenario.router)
        app.dependency_overrides[get_db] = _db
        return TestClient(app), calls

    yield _make
    for name in _FORGET:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)
    next(gen, None)


def _pipeline_search_params() -> set[str]:
    """pipeline.search 의 인자 이름 — 대역은 **kwargs 로 다 받아서, 인자명이 어긋나면 운영에서만 TypeError 로 드러난다.
    시그니처만 보면 되므로 소스를 ast 로 읽는다(test_research_explorer.py 와 같은 방식)."""
    src = Path(__file__).resolve().parents[1] / "services" / "search" / "pipeline.py"
    fn = next(node for node in ast.parse(src.read_text(encoding="utf-8")).body
              if isinstance(node, ast.AsyncFunctionDef) and node.name == "search")
    return {a.arg for a in fn.args.args + fn.args.kwonlyargs}


def _assert_real_kwargs_and_same_db(calls: list[dict]) -> None:
    for kwargs in calls:
        assert set(kwargs) <= _pipeline_search_params()
    # 재시도도 같은 DB 세션을 넘긴다 — 빠지면 재작성의 DB 보강과 날짜 필터가 조용히 꺼진다
    assert calls[-1]["db"] is calls[0]["db"] is not None


BODY = {"query": "올리버 트위스트", "mode": "book", "top_k": 10, "use_rewrite": False}


def test_book_search_with_books_does_not_retry(make_client):
    http, calls = make_client(["LIT-GUTENBERG-730"])
    res = http.post("/api/books/search", json=BODY)
    assert res.status_code == 200
    assert [b["book_id"] for b in res.json()["books"]] == ["LIT-GUTENBERG-730"]
    assert len(calls) == 1
    assert calls[0]["doc_scope"] == "book"
    assert calls[0].get("use_metadata_filter", True) is True


def test_book_search_zero_books_retries_inside_books_without_date_filter(make_client):
    http, calls = make_client([], ["LIT-GUTENBERG-730"])
    res = http.post("/api/books/search", json=BODY)
    assert res.status_code == 200
    assert [b["book_id"] for b in res.json()["books"]] == ["LIT-GUTENBERG-730"]
    assert len(calls) == 2
    # 도서 범위는 풀지 않는다 — 날짜 조건만 뺀다
    assert calls[1]["doc_scope"] == "book"
    assert calls[1]["use_metadata_filter"] is False
    # 화면이 고른 나머지 인자는 그대로
    same = ("mode", "top_k", "use_rewrite", "use_rerank")
    assert {k: calls[1][k] for k in same} == {k: calls[0][k] for k in same}
    _assert_real_kwargs_and_same_db(calls)


def test_book_search_zero_books_twice_answers_empty_not_papers(make_client):
    http, calls = make_client([], [])
    res = http.post("/api/books/search", json=BODY)
    assert res.status_code == 200
    assert res.json()["books"] == []
    assert len(calls) == 2
    assert all(c["doc_scope"] == "book" for c in calls)


def test_scenario_zero_books_retries_inside_books_without_date_filter(make_client):
    http, calls = make_client([], [])
    res = http.post("/api/scenario/recommend", json={"concern": "올해 들어 마음이 불안해요", "top_k": 3})
    assert res.status_code == 404   # 두 번 다 0권이면 예전처럼 404
    assert len(calls) == 2
    assert calls[0]["doc_scope"] == "book"
    assert calls[1]["doc_scope"] == "book"
    assert calls[1]["use_metadata_filter"] is False
    _assert_real_kwargs_and_same_db(calls)
