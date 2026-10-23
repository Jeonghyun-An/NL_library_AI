"""test_book_search_original_query.py — 소장자료 검색이 재작성한 질의만으로 후보를 찾다 제목을 놓치던 것.

재작성(gemma)은 제목만 넣은 질의를 주제어로 바꾼다 — '구운몽' → '요몽, 이상향, 유토피아, 꿈…', '태평천하' → '번영하는 시대,
평화로운 사회…'. 후보는 그 문장으로만 찾고 제목 일치 점수는 찾은 후보의 순서만 바꾸므로, 운영 화면(top_k 10)에서 한국 문학
제목 41개 중 31개가 목록에도 없었다(research/book-search-title-recall). 소장자료 검색은 원래 질의로도 후보를 찾아 합친다 —
갈래마다 자기 질의로 재정렬하고 같은 책이면 내용 점수가 높은 쪽을 둔다. 상황별 추천처럼 고민 글을 넣는 다른 도서 검색은
켜지 않는다(include_original 기본 False).

같이 고친 것: 제목 정규화가 한자를 지워 '1930年代 世態小說 硏究' 가 '1930' 이 되고, '1930' 이 든 질의마다 제목 일치 1.0 이었다.
한자를 남기되, "'월인천강지곡(月印千江之曲)' 연구"처럼 한글 제목에 한자를 덧붙인 꼴은 한자를 뺀 꼴로도 견준다.

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
from services.search.metadata_filter import MetadataFilter
from services.search.title_scorer import title_match_score

ORIGINAL = "구운몽"
REWRITTEN = "요몽, 이상향, 유토피아"


# ── 제목 정규화 ──────────────────────────────────────────────

def test_hanja_title_is_not_cut_down_to_its_digits():
    # 정규화가 한자를 지우면 제목이 '1930' 만 남아 '1930년대…' 질의 안에 '들어 있는' 것으로 1.0 이 됐다
    assert title_match_score(["김유정의 동백꽃", "1930년대 농촌 사회, 해학"], "1930年代 世態小說 硏究") < 0.5


def test_short_hangul_leftover_of_a_hanja_title_does_not_match():
    # 한자를 지우면 '에나타난' 만 남아 '…에 나타난 …' 질의마다 1.0 이었다(관련 자료 칸을 무관한 학위논문이 채웠다)
    assert title_match_score(["한국 현대시에 나타난 도가사상 연구"], "韓國現代女流詩에 나타난 愛情意識硏究") < 0.5


def test_hanja_title_still_matches_itself():
    assert title_match_score(["辛夕汀 硏究"], "辛夕汀 硏究") == 1.0          # 한자만인 제목은 예전에 빈 문자열이었다


def test_hangul_title_with_hanja_gloss_matches_the_hangul_query():
    # 한자를 남기기만 하면 '월인천강지곡月印千江之曲연구' 가 되어 한글 질의와의 완전 일치가 0.6 으로 떨어진다
    assert title_match_score(["월인천강지곡 연구"], "'월인천강지곡(月印千江之曲)' 연구") == 1.0


def test_compatibility_hanja_is_folded():
    # 호환 한자 李(U+F9E1)와 통합 한자 李(U+674E)는 같은 글자다
    assert title_match_score(["李箱 硏究"], "李箱 硏究") == 1.0


# ── 원래 질의 갈래 ────────────────────────────────────────────

def _hit(book_id: str, idx: int, score: float, pub_date: str = ""):
    return SimpleNamespace(chunk_id=f"{book_id}__{idx}", book_id=book_id, chunk_idx=idx, text=f"{book_id} 본문 {idx}",
                           page_start=1, page_end=1, score=score, pub_date=pub_date)


# 갈래마다 찾는 책과 재정렬 점수. BOTH 는 원래 질의 갈래가, BOTH2 는 재작성 갈래가 높다
HITS = {
    REWRITTEN: {"R1": [_hit("R1", 1, 0.9, "2001")], "BOTH": [_hit("BOTH", 1, 0.8, "1990")],
                "BOTH2": [_hit("BOTH2", 1, 0.7, "1980")]},
    ORIGINAL: {"T1": [_hit("T1", 1, 0.7, "2020")], "BOTH": [_hit("BOTH", 2, 0.6, "1990")],
               "BOTH2": [_hit("BOTH2", 2, 0.5, "1980")]},
}
RERANK = {
    (REWRITTEN, "R1"): 0.5, (REWRITTEN, "BOTH"): 0.3, (REWRITTEN, "BOTH2"): 0.9,
    (ORIGINAL, "T1"): 0.5, (ORIGINAL, "BOTH"): 0.95, (ORIGINAL, "BOTH2"): 0.2,
}


def _patch(monkeypatch, pipeline, *, rewritten=REWRITTEN, hits=None):
    """재작성·임베딩·Milvus·재정렬 대역 — 벡터는 질의 글 자체로 두어 어느 갈래의 검색인지 가른다."""
    hits = HITS if hits is None else hits
    log = {"embedded": [], "searched": [], "reranked": []}

    async def _rewrite(query, db=None):
        if isinstance(rewritten, Exception):
            raise rewritten
        return rewritten

    def _embed(texts, is_query=False):
        log["embedded"].append(list(texts))
        return [[t] for t in texts], [{"q": t} for t in texts]

    def _search_by_book(dense, sparse, *, top_k_chunks, top_k_books, meta_expr=None):
        query = dense[0]
        log["searched"].append({"query": query, "top_k_books": top_k_books, "meta_expr": meta_expr})
        return hits.get(query, {})

    def _rerank(query_text, docs):
        log["reranked"].append((query_text, list(docs)))
        book = docs[0].split()[0]
        score = RERANK[(query_text.strip(), book)]
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
    assert {b.book_id for b in resp.books} == {"R1", "BOTH", "BOTH2", "T1"}
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
    assert by_book == {"R1": {REWRITTEN}, "T1": {ORIGINAL}, "BOTH": {REWRITTEN, ORIGINAL},
                       "BOTH2": {REWRITTEN, ORIGINAL}}


def test_same_book_keeps_whichever_branch_scores_higher(monkeypatch, pipeline):
    _patch(monkeypatch, pipeline)
    books = {b.book_id: b for b in _search(pipeline, include_original=True).books}
    # 원래 질의 갈래가 높은 책과 재작성 갈래가 높은 책 — 어느 한쪽이 늘 이기게 짜면 둘 중 하나가 깨진다
    assert (books["BOTH"].best_score, [c.chunk_id for c in books["BOTH"].chunks]) == (0.95, ["BOTH__2"])
    assert (books["BOTH2"].best_score, [c.chunk_id for c in books["BOTH2"].chunks]) == (0.9, ["BOTH2__1"])


def test_results_are_sorted_after_merging(monkeypatch, pipeline):
    _patch(monkeypatch, pipeline)
    scores = [b.best_score for b in _search(pipeline, include_original=True).books]
    assert scores == sorted(scores, reverse=True)


def test_empty_rewritten_branch_still_returns_the_original_branch(monkeypatch, pipeline):
    # 재작성 문장으로는 도서 필터 안에서 하나도 못 찾을 때 — 빈 응답이면 API 가 필터 없이(논문까지) 다시 찾는다
    _patch(monkeypatch, pipeline, hits={REWRITTEN: {}, ORIGINAL: HITS[ORIGINAL]})
    resp = _search(pipeline, include_original=True)
    assert {b.book_id for b in resp.books} == {"T1", "BOTH", "BOTH2"}


def test_date_sort_reads_pub_date_from_both_branches(monkeypatch, pipeline):
    # 원래 질의 갈래에만 있는 T1(2020)이 최신순 맨 앞이어야 한다 — 그 갈래의 pub_date 를 못 읽으면 '' 로 맨 뒤에 간다
    _patch(monkeypatch, pipeline)
    resp = asyncio.run(pipeline._search_book_mode(
        ORIGINAL, REWRITTEN, [REWRITTEN], {"q": REWRITTEN}, 10, True, 0.0, None,
        meta_expr=pipeline._BOOK_EXPR, metadata_filter=MetadataFilter(sort_by="recent", has_filter=True),
        original_vectors=([ORIGINAL], {"q": ORIGINAL}),
    ))
    assert [b.book_id for b in resp.books] == ["T1", "R1", "BOTH", "BOTH2"]


def test_default_searches_only_the_rewritten_query(monkeypatch, pipeline):
    """상황별 추천 등 다른 도서 검색 호출자는 그대로다."""
    log = _patch(monkeypatch, pipeline)
    resp = _search(pipeline)
    assert {b.book_id for b in resp.books} == {"R1", "BOTH", "BOTH2"}
    assert log["embedded"] == [[REWRITTEN]]
    assert len(log["searched"]) == 1


@pytest.mark.parametrize("query, rewritten", [
    (ORIGINAL, RuntimeError("gemma 끊김")),
    (ORIGINAL, ORIGINAL),
    (f" {ORIGINAL} ", ORIGINAL),        # 재작성은 앞뒤 공백을 떼어 돌려준다 — 공백만 다르면 같은 질의다
])
def test_no_second_branch_when_rewrite_failed_or_unchanged(monkeypatch, pipeline, query, rewritten):
    log = _patch(monkeypatch, pipeline, rewritten=rewritten, hits={**HITS, query: HITS[ORIGINAL]})
    resp = asyncio.run(pipeline.search(query, mode="book", top_k=10, use_rewrite=True, use_rerank=True,
                                       doc_scope="book", db=None, include_original=True))
    assert len(log["embedded"]) == 1 and len(log["embedded"][0]) == 1
    assert len(log["searched"]) == 1
    assert {b.book_id for b in resp.books} == {"T1", "BOTH", "BOTH2"}


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
    """api.book 을 대역 pipeline 위에서 새로 올리고 search·서지 조회가 받은 인자를 적는다 — 끝나면 import 전 그대로 되돌린다."""
    gen = stubbed_pipeline(monkeypatch)
    next(gen)
    for name in _FORGET:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    book = importlib.import_module("api.book")
    from core.deps import get_db
    from schemas.book import BookChunkGroup, BookSearchResponse

    seen = {"search": [], "lookups": []}
    found = {"books": []}

    async def _search(query, **kwargs):
        seen["search"].append(kwargs)
        books = [BookChunkGroup(book_id=b, best_score=0.5) for b in found["books"]]
        return BookSearchResponse(query=query, rewritten_query=None, books=books, elapsed_ms=1.0)

    class _Repo:
        """책마다 부르는 get_by_cnts_id 는 두지 않는다 — 부르면 AttributeError 로 500 이 난다."""

        def __init__(self, db):
            pass

        async def get_by_cnts_ids(self, ids):
            seen["lookups"].append(list(ids))
            return {}

    monkeypatch.setattr(book, "search", _search)
    monkeypatch.setattr(book, "BookRepository", _Repo)

    async def _db():
        yield _Db()

    app = FastAPI()
    app.include_router(book.router)
    app.dependency_overrides[get_db] = _db
    yield TestClient(app), seen, found
    for name in _FORGET:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)
    next(gen, None)


def test_book_search_route_turns_on_the_original_query_branch(book_client):
    client, seen, _ = book_client
    r = client.post("/api/books/search", json={"query": ORIGINAL, "mode": "book", "top_k": 10})
    assert r.status_code == 200
    # 빈 결과라 도서 필터 없이 다시 찾는 두 번째 호출도 켠다
    assert [c.get("include_original") for c in seen["search"]] == [True, True]
    assert seen["search"][0]["doc_scope"] == "book"


def test_book_search_route_reads_catalog_once(book_client):
    client, seen, found = book_client
    found["books"] = ["WS_014", "T1", "R1"]
    r = client.post("/api/books/search", json={"query": ORIGINAL, "mode": "book", "top_k": 10})
    assert r.status_code == 200
    assert seen["lookups"] == [["WS_014", "T1", "R1"]]
