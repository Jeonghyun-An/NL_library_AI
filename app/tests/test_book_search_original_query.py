"""test_book_search_original_query.py — 소장자료 검색이 재작성한 질의만으로 후보를 찾다 제목을 놓치던 것.

재작성(gemma)은 제목만 넣은 질의를 주제어로 바꾼다 — '구운몽' → '요몽, 이상향, 유토피아, 꿈…', '태평천하' → '번영하는 시대,
평화로운 사회…'. 후보는 그 문장으로만 찾고 제목 일치 점수는 찾은 후보의 순서만 바꾸므로, 운영 화면(top_k 10)에서 한국 문학
제목 41개 중 31개가 목록에도 없었다(research/book-search-title-recall). 소장자료 검색은 원래 질의로도 후보를 찾아 합친다 —
갈래마다 자기 질의로 재정렬하고 같은 책이면 내용 점수가 높은 쪽을 둔다. 상황별 추천처럼 고민 글을 넣는 다른 도서 검색은
켜지 않는다(include_original 기본 False).

같이 고친 것: 제목 정규화가 한자를 지워 '1930年代 世態小說 硏究' 가 '1930' 이 되고, '1930' 이 든 질의마다 제목 일치 1.0 이었다.

pipeline 은 공용 대역(pipeline_stub.py) 위에서 import 하고 Milvus·임베딩·재정렬·재작성을 대역으로 바꾼다. async 테스트 없음.
"""
import asyncio
import importlib
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline_stub import pipeline, stubbed_pipeline  # noqa: F401 — pipeline 은 픽스처(테스트 인자 이름으로 쓴다)
from services.search.title_scorer import title_match_score

ORIGINAL = "구운몽"
REWRITTEN = "요몽, 이상향, 유토피아"


# ── 제목 정규화 ──────────────────────────────────────────────

def test_hanja_title_is_not_cut_down_to_its_digits():
    # 정규화가 한자를 지우면 제목이 '1930' 만 남아 '1930년대…' 질의 안에 '들어 있는' 것으로 1.0 이 됐다
    assert title_match_score(["김유정의 동백꽃", "1930년대 농촌 사회, 해학"], "1930年代 世態小說 硏究") < 0.5


def test_hanja_title_still_matches_itself():
    assert title_match_score(["韓國 四時歌의 硏究"], "韓國 四時歌의 硏究") == 1.0
    assert title_match_score(["辛夕汀 硏究"], "辛夕汀 硏究") == 1.0


def test_hangul_and_latin_titles_unchanged():
    assert title_match_score(["구운몽"], "구운몽") == 1.0
    assert title_match_score(["Little Women"], "Little Women") == 1.0
    assert title_match_score(["구운몽"], "韓國 四時歌의 硏究") == 0.0


# ── 원래 질의 갈래 ────────────────────────────────────────────

def _hit(book_id: str, idx: int, score: float):
    return SimpleNamespace(chunk_id=f"{book_id}__{idx}", book_id=book_id, chunk_idx=idx, text=f"{book_id} 본문 {idx}",
                           page_start=1, page_end=1, score=score, pub_date="")


def _patch(monkeypatch, pipeline, *, rewritten=REWRITTEN):
    """재작성·임베딩·Milvus·재정렬 대역 — 벡터는 질의 글 자체로 두어 어느 갈래의 검색인지 가른다."""
    log = {"embedded": [], "searched": [], "reranked": []}

    async def _rewrite(query, db=None):
        if isinstance(rewritten, Exception):
            raise rewritten
        return rewritten

    def _embed(texts, is_query=False):
        log["embedded"].append(list(texts))
        return [[t] for t in texts], [{"q": t} for t in texts]

    by_query = {
        REWRITTEN: {"R1": [_hit("R1", 1, 0.9)], "BOTH": [_hit("BOTH", 1, 0.8)]},
        ORIGINAL: {"T1": [_hit("T1", 1, 0.7)], "BOTH": [_hit("BOTH", 2, 0.6)]},
    }

    def _search_by_book(dense, sparse, *, top_k_chunks, top_k_books, meta_expr=None):
        query = dense[0]
        log["searched"].append({"query": query, "top_k_books": top_k_books, "meta_expr": meta_expr})
        return by_query.get(query, {})

    # 재정렬 점수: 원래 질의로 본 BOTH 는 0.95(재작성 갈래 0.3 보다 높다), 나머지는 0.5
    def _rerank(query_text, docs):
        log["reranked"].append((query_text, list(docs)))
        score = 0.95 if (query_text == ORIGINAL and docs and docs[0].startswith("BOTH")) else 0.5
        if query_text == REWRITTEN and docs and docs[0].startswith("BOTH"):
            score = 0.3
        return [SimpleNamespace(index=i, score=score) for i in range(len(docs))]

    monkeypatch.setattr(pipeline, "rewrite_query", _rewrite)
    monkeypatch.setattr(pipeline, "embed_texts", _embed)
    monkeypatch.setattr(pipeline, "search_by_book", _search_by_book)
    monkeypatch.setattr(pipeline, "rerank_docs", _rerank)
    return log


def _search(pipeline, **kwargs):
    return asyncio.run(pipeline.search(ORIGINAL, mode="book", top_k=10, use_rewrite=True, use_rerank=True,
                                       doc_scope="book", db=None, **kwargs))


def test_include_original_finds_books_only_the_original_query_reaches(monkeypatch, pipeline):
    log = _patch(monkeypatch, pipeline)
    resp = _search(pipeline, include_original=True)
    assert {b.book_id for b in resp.books} == {"R1", "BOTH", "T1"}
    assert resp.rewritten_query == REWRITTEN
    # 두 질의를 한 번에 임베딩하고 같은 조건(도서 필터·후보 수)으로 두 번 찾는다
    assert log["embedded"] == [[REWRITTEN, ORIGINAL]]
    assert [s["query"] for s in log["searched"]] == [REWRITTEN, ORIGINAL]
    assert log["searched"][0]["top_k_books"] == log["searched"][1]["top_k_books"]
    assert log["searched"][0]["meta_expr"] == log["searched"][1]["meta_expr"] == pipeline._BOOK_EXPR


def test_each_branch_is_reranked_with_its_own_query(monkeypatch, pipeline):
    log = _patch(monkeypatch, pipeline)
    _search(pipeline, include_original=True)
    by_book = {}
    for text, docs in log["reranked"]:
        by_book.setdefault(docs[0].split()[0], set()).add(text)
    assert by_book["R1"] == {REWRITTEN}
    assert by_book["T1"] == {ORIGINAL}
    assert by_book["BOTH"] == {REWRITTEN, ORIGINAL}


def test_same_book_keeps_the_higher_scoring_branch(monkeypatch, pipeline):
    _patch(monkeypatch, pipeline)
    resp = _search(pipeline, include_original=True)
    both = next(b for b in resp.books if b.book_id == "BOTH")
    assert both.best_score == 0.95                                # 원래 질의 갈래 0.95 > 재작성 갈래 0.3
    assert [c.chunk_id for c in both.chunks] == ["BOTH__2"]      # 그 갈래의 청크를 싣는다
    assert [b.best_score for b in resp.books] == sorted((b.best_score for b in resp.books), reverse=True)


def test_default_searches_only_the_rewritten_query(monkeypatch, pipeline):
    """상황별 추천 등 다른 도서 검색 호출자는 그대로다."""
    log = _patch(monkeypatch, pipeline)
    resp = _search(pipeline)
    assert {b.book_id for b in resp.books} == {"R1", "BOTH"}
    assert log["embedded"] == [[REWRITTEN]]
    assert len(log["searched"]) == 1


def test_no_second_branch_when_rewrite_failed_or_unchanged(monkeypatch, pipeline):
    for rewritten in (RuntimeError("gemma 끊김"), ORIGINAL):
        log = _patch(monkeypatch, pipeline, rewritten=rewritten)
        resp = _search(pipeline, include_original=True)
        assert log["embedded"] == [[ORIGINAL]]
        assert [s["query"] for s in log["searched"]] == [ORIGINAL]
        assert {b.book_id for b in resp.books} == {"T1", "BOTH"}


# ── 소장자료 검색 API ─────────────────────────────────────────

_FORGET = ("api.book",)


class _Db:
    async def execute(self, stmt, params=None):
        return None

    async def commit(self):
        pass

    async def rollback(self):
        pass


@pytest.fixture
def book_client(monkeypatch):
    """api.book 을 대역 pipeline 위에서 새로 올리고 search 가 받은 인자를 적는다 — 끝나면 import 전 그대로 되돌린다."""
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

    seen: list[dict] = []

    async def _search(query, **kwargs):
        seen.append(kwargs)
        return BookSearchResponse(query=query, rewritten_query=None, books=[], elapsed_ms=1.0)

    monkeypatch.setattr(book, "search", _search)

    async def _db():
        yield _Db()

    app = FastAPI()
    app.include_router(book.router)
    app.dependency_overrides[get_db] = _db
    yield TestClient(app), seen
    for name in _FORGET:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)
    next(gen, None)


def test_book_search_route_turns_on_the_original_query_branch(book_client):
    client, seen = book_client
    r = client.post("/api/books/search", json={"query": ORIGINAL, "mode": "book", "top_k": 10})
    assert r.status_code == 200
    # 빈 결과라 도서 필터 없이 다시 찾는 두 번째 호출도 켠다
    assert [c.get("include_original") for c in seen] == [True, True]
    assert seen[0]["doc_scope"] == "book"
