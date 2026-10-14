"""test_paper_search_no_rewrite.py — 논문 검색(POST /api/papers/search)은 쿼리 재작성을 하지 않는다.

재작성 프롬프트(query_rewrite.yaml)는 도서 추천용('X 같은 책', 감성 → 주제 키워드)이다. 논문 검색에 켜 두면 원 질문의
구체어를 버리고 질문에 없던 주제어를 덧붙였다. 켬 71% vs 끔 87%(파이프라인 측정, 독립 3세트 450문항 — 재작성 단계
−17.6%p), 배포본 실측 Recall@10 89%(2026-10-14, 합성 질문 기준) — research/brochure-search-eval/README.md(브랜치
feat/brochure-search-eval). 사용자 결정 2026-10-14 로 논문 검색은 화면이
무엇을 보내든 재작성을 끈다 — 소장자료 검색(/api/books/search)은 원래 목적대로 그대로 둔다.

pipeline.search 만 대역으로 바꿔 라우트가 넘기는 값을 본다. async 테스트 없음.
"""
import importlib
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline_stub import stubbed_pipeline

_FORGET = ("api.paper",)


@pytest.fixture
def client(monkeypatch):
    gen = stubbed_pipeline(monkeypatch)
    next(gen)
    # api.paper 는 pipeline.search 를 머리에서 import 한다 — 대역 위에서 새로 올리고 끝나면 import 전 그대로 되돌린다
    for name in _FORGET:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    paper = importlib.import_module("api.paper")
    from core.deps import get_db
    from schemas.book import BookSearchResponse

    seen: list[dict] = []

    async def _search(query, **kwargs):
        seen.append({"query": query, **kwargs})
        return BookSearchResponse(query=query, rewritten_query=None, books=[], elapsed_ms=1.0)

    monkeypatch.setattr(paper, "search", _search)

    async def _db():
        yield None

    app = FastAPI()
    app.include_router(paper.router)
    app.dependency_overrides[get_db] = _db
    yield TestClient(app), seen
    for name in _FORGET:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)
    next(gen, None)


@pytest.mark.parametrize("sent", [True, False, None])
def test_paper_search_never_rewrites(client, sent):
    http, seen = client
    body = {"query": "한우의 몸무게와 몸집 형질 간 유전 연관", "mode": "book", "top_k": 10}
    if sent is not None:
        body["use_rewrite"] = sent
    res = http.post("/api/papers/search", json=body)
    assert res.status_code == 200
    assert seen[-1]["use_rewrite"] is False
    assert seen[-1]["doc_scope"] == "paper"
    # 원 질문을 그대로 넘긴다 — 재작성이 없으니 응답의 rewritten_query 도 원 질문을 대신하지 않는다
    assert seen[-1]["query"] == body["query"]


def test_other_flags_still_follow_the_request(client):
    http, seen = client
    http.post("/api/papers/search", json={"query": "q", "mode": "chunk", "top_k": 7, "use_rerank": False})
    assert seen[-1]["mode"] == "chunk"
    assert seen[-1]["top_k"] == 7
    assert seen[-1]["use_rerank"] is False
