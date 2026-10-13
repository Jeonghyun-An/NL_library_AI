"""test_book_related.py — 소장자료 상세 '관련 자료 추천'(GET /api/books/{cnts_id}/related).

예전에는 상세 화면이 자기 제목으로 사용자 검색(POST /api/books/search)을 그대로 불렀다. 그 검색은 하이브리드 상위
청크를 정해진 개수(top_k 6 → 180개)만 받아 책으로 묶는데, 긴 학위논문은 자기 본문 청크가 그 창을 거의 다 채워
(운영 확인: 180자리 중 178) 관련 자료가 1권만 남았다. 같은 경로라 제목에도 날짜·정렬 LLM 필터가 걸려('初期'→오래된
순, '1999'→1999년만) 관련 자료가 발행일순으로 잘리거나 0권이 됐고, 상세를 열 때마다 search_history 에 응답 전체가
쌓였다.

새 경로는 자기 자신을 Milvus 조건식에서 미리 빼고, 재작성·날짜 필터 LLM 을 부르지 않고, 연관도 하한 아래는 칸을
비우며, 기록을 남기지 않는다. 앞 절은 pipeline.search_related_books, 뒤 절은 TestClient 로 라우팅을 거치는 API 다.
Milvus·임베딩·리랭커만 대역이고 서지(library_catalog)·search_history 는 history_sqlite 의 SQLite 다.

async 테스트는 asyncio.run 으로 돈다(pytest-asyncio 없음).
"""
import asyncio
import importlib
import sys
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from history_sqlite import AsyncSessionOverSync, add_book, make_engine
from models.search_history import SearchHistory
from pipeline_stub import stubbed_pipeline

SELF = "CNTS-00052063539"
SELF_TITLE = "조선후기 세태소설 연구"


class _Hit:
    """indexer.search_chunks·search_by_book 이 돌려주는 행 대역. 리랭커 대역이 text 로 점수를 찾는다."""

    def __init__(self, book_id: str, chunk_idx: int, score: float):
        self.chunk_id = f"{book_id}__{chunk_idx:04d}"
        self.book_id, self.chunk_idx = book_id, chunk_idx
        self.text = f"{book_id} 본문 {chunk_idx}"
        self.page_start = self.page_end = 3
        self.score = score
        self.pub_date = "1990"


def _wire(monkeypatch, pipeline, book_scores: dict[str, float]) -> dict:
    """Milvus 는 책마다 본문 청크 1개(점수 = book_scores)로 고정한다. 청크가 1개라 로그 부스트가 없어 연관도 = 그 점수.

    재작성·날짜 필터 LLM 은 부르면 실패하게 둔다 — 관련 자료 경로는 둘 다 부르지 않아야 한다."""
    seen: dict = {"search_by_book": [], "embedded": []}
    hits = {bid: [_Hit(bid, 5, score)] for bid, score in book_scores.items()}
    by_text = {h.text: h.score for hs in hits.values() for h in hs}

    def _search_by_book(dense, sparse, top_k_chunks=20, top_k_books=5, *, meta_expr=None):
        seen["search_by_book"].append(
            {"top_k_chunks": top_k_chunks, "top_k_books": top_k_books, "meta_expr": meta_expr})
        return dict(hits)

    def _embed(texts, is_query=False):
        seen["embedded"].append((list(texts), is_query))
        return [[0.1]], [{1: 0.2}]

    def _rerank(query, docs):
        return [SimpleNamespace(index=i, score=by_text[d]) for i, d in enumerate(docs)]

    async def _no_llm(*args, **kwargs):
        raise AssertionError("관련 자료 경로가 LLM(재작성·날짜 필터)을 불렀다")

    monkeypatch.setattr(pipeline, "search_by_book", _search_by_book)
    monkeypatch.setattr(pipeline, "embed_texts", _embed)
    monkeypatch.setattr(pipeline, "rerank_docs", _rerank)
    monkeypatch.setattr(pipeline, "rewrite_query", _no_llm)
    monkeypatch.setattr(pipeline, "extract_metadata_filter", _no_llm)
    return seen


@pytest.fixture
def pipeline(monkeypatch):
    yield from stubbed_pipeline(monkeypatch)


# ── pipeline.search_related_books ────────────────────────
class TestSearchRelatedBooks:
    def _run(self, pipeline, title=SELF_TITLE, exclude_id=SELF, fetch_top_k=10):
        return asyncio.run(pipeline.search_related_books(title, exclude_id, fetch_top_k=fetch_top_k))

    def test_self_is_excluded_in_the_milvus_expression(self, monkeypatch, pipeline):
        """자기 청크가 후보 창을 먹기 전에 조건식에서 뺀다 — 묶은 뒤에 빼면 창은 이미 자기로 차 있다."""
        seen = _wire(monkeypatch, pipeline, {"B": 0.8})
        self._run(pipeline)
        expr = seen["search_by_book"][0]["meta_expr"]
        assert pipeline._BOOK_EXPR in expr
        assert f'book_id != "{SELF}"' in expr
        assert "pub_date" not in expr

    def test_window_is_three_books_and_thirty_chunks_per_fetch_unit(self, monkeypatch, pipeline):
        """사용자 검색과 같은 배수(×3권, 권당 ×10청크)를 쓴다 — fetch_top_k 10 이면 30권·300청크 창."""
        seen = _wire(monkeypatch, pipeline, {"B": 0.8})
        self._run(pipeline, fetch_top_k=10)
        assert seen["search_by_book"][0]["top_k_books"] == 30
        assert seen["search_by_book"][0]["top_k_chunks"] == 300

    def test_no_llm_is_called_and_the_title_is_embedded_as_is(self, monkeypatch, pipeline):
        """'韓國初期近代詩論硏究'의 初期가 오래된 순 정렬로, '경제백서 1999'의 1999가 연도 필터로 읽히면 안 된다."""
        seen = _wire(monkeypatch, pipeline, {"B": 0.8})
        resp = self._run(pipeline, title="경제백서 1999", exclude_id="CNTS-00049655779")
        assert seen["embedded"] == [(["경제백서 1999"], True)]
        assert resp.query == "경제백서 1999"
        assert resp.rewritten_query is None

    def test_books_come_back_in_score_order_not_date_order(self, monkeypatch, pipeline):
        _wire(monkeypatch, pipeline, {"B": 0.5, "C": 0.9, "D": 0.7})
        resp = self._run(pipeline)
        assert [b.book_id for b in resp.books] == ["C", "D", "B"]

    @pytest.mark.parametrize("bad", ['X" || book_id != "Y', "CNTS-1\n", "CNTS 1", ""])
    def test_unsafe_id_is_refused_before_it_reaches_the_expression(self, monkeypatch, pipeline, bad):
        """id 는 조건식 문자열에 그대로 들어간다 — 따옴표·공백·줄바꿈은 받지 않는다($ 는 끝 줄바꿈을 통과시킨다)."""
        seen = _wire(monkeypatch, pipeline, {"B": 0.8})
        with pytest.raises(ValueError):
            self._run(pipeline, exclude_id=bad)
        assert seen["search_by_book"] == []

    @pytest.mark.parametrize("ok", [SELF, "KCI_FI001234567", "NL.abc-01_x"])
    def test_catalog_ids_are_safe(self, pipeline, ok):
        assert pipeline.is_safe_book_id(ok)


# ── GET /api/books/{cnts_id}/related ─────────────────────
_FORGET = ("api.book",)


class _Api:
    def __init__(self, client, engine, pipeline, monkeypatch):
        self.client, self.engine, self.pipeline, self._mp = client, engine, pipeline, monkeypatch

    def wire(self, book_scores: dict[str, float]) -> dict:
        return _wire(self._mp, self.pipeline, book_scores)

    def history_rows(self) -> int:
        with self.engine.connect() as conn:
            return conn.execute(sa.select(sa.func.count()).select_from(SearchHistory.__table__)).scalar_one()


@pytest.fixture
def api(monkeypatch):
    gen = stubbed_pipeline(monkeypatch)
    pipeline = next(gen)
    # api.book 은 pipeline 을 머리에서 import 한다 — 대역 위에서 새로 올리고 끝나면 import 전 그대로 되돌린다
    for name in _FORGET:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    router = importlib.import_module("api.book")
    from core.deps import get_db

    engine = make_engine()
    SearchHistory.__table__.to_metadata(sa.MetaData()).create(engine)
    add_book(engine, SELF, title=SELF_TITLE, doc_type="literature")
    for bid, title in (("B", "갑 을"), ("C", "병 정"), ("D", "무 기"), ("E", "경 신"),
                       ("F", "임 계"), ("G", "자 축")):
        add_book(engine, bid, title=title, doc_type="literature")
    add_book(engine, "NOTITLE", title="", doc_type="literature")

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
    yield _Api(TestClient(app), engine, pipeline, monkeypatch)
    for name in _FORGET:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)
    next(gen, None)


SIX = {"B": 0.8, "C": 0.7, "D": 0.5, "E": 0.35, "F": 0.2, "G": 0.05}


class TestRelatedApi:
    def test_fills_four_by_score_above_the_floor(self, api):
        api.wire(SIX)
        resp = api.client.get(f"/api/books/{SELF}/related")
        assert resp.status_code == 200
        books = resp.json()["books"]
        assert [b["book_id"] for b in books] == ["B", "C", "D", "E"]
        assert books[0]["book_info"]["title"] == "갑 을"
        assert [b["content_score"] for b in books] == [0.8, 0.7, 0.5, 0.35]

    def test_does_not_pad_with_books_below_the_floor(self, api):
        """관련 없는 책(운영: 영어 Gutenberg 소설 0.33 이하·무관 도서 0.01~0.1)으로 칸을 채우지 않는다."""
        api.wire({"B": 0.8, "C": 0.25})
        books = api.client.get(f"/api/books/{SELF}/related").json()["books"]
        assert [b["book_id"] for b in books] == ["B"]

    def test_self_never_comes_back_even_if_the_index_returns_it(self, api):
        api.wire({SELF: 0.99, "B": 0.8})
        books = api.client.get(f"/api/books/{SELF}/related").json()["books"]
        assert [b["book_id"] for b in books] == ["B"]

    def test_searches_by_the_catalog_title_without_self(self, api):
        seen = api.wire(SIX)
        api.client.get(f"/api/books/{SELF}/related")
        assert seen["embedded"] == [([SELF_TITLE], True)]
        assert f'book_id != "{SELF}"' in seen["search_by_book"][0]["meta_expr"]
        assert seen["search_by_book"][0]["top_k_books"] == 30

    def test_response_carries_no_chunk_text(self, api):
        """카드는 서지·점수만 쓴다 — 예전 응답은 청크 본문을 다 담아 320~500KB 였다."""
        api.wire(SIX)
        books = api.client.get(f"/api/books/{SELF}/related").json()["books"]
        assert books and all(b["chunks"] == [] for b in books)

    def test_writes_no_search_history(self, api):
        """상세를 여는 것은 사용자가 검색한 것이 아니다 — search-classic 기록에도 섞였다."""
        api.wire(SIX)
        before = api.history_rows()
        resp = api.client.get(f"/api/books/{SELF}/related", headers={"x-session-id": "s-1"})
        assert resp.status_code == 200 and resp.json()["books"]
        assert api.history_rows() == before == 0

    def test_top_k_limits_the_count(self, api):
        api.wire(SIX)
        books = api.client.get(f"/api/books/{SELF}/related", params={"top_k": 2}).json()["books"]
        assert [b["book_id"] for b in books] == ["B", "C"]

    @pytest.mark.parametrize("top_k", [0, 11])
    def test_top_k_out_of_range_is_400(self, api, top_k):
        seen = api.wire(SIX)
        resp = api.client.get(f"/api/books/{SELF}/related", params={"top_k": top_k})
        assert resp.status_code == 400
        assert seen["search_by_book"] == []

    def test_unknown_book_is_404(self, api):
        """라우트가 없어서 나는 404('Not Found')와 가른다 — 상세 GET 과 같은 '도서 없음'."""
        seen = api.wire(SIX)
        resp = api.client.get("/api/books/CNTS-NOPE/related")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "도서 없음: CNTS-NOPE"
        assert seen["search_by_book"] == []

    def test_unsafe_id_is_404_without_searching(self, api):
        """서지에 있어도 조건식에 못 넣는 id 면 찾지 않는다."""
        seen = api.wire(SIX)
        add_book(api.engine, 'A"B', title="따옴표 제목", doc_type="literature")
        resp = api.client.get('/api/books/A"B/related')
        assert resp.status_code == 404
        assert resp.json()["detail"] == '도서 없음: A"B'
        assert seen["search_by_book"] == []

    def test_book_without_title_has_no_related(self, api):
        seen = api.wire(SIX)
        resp = api.client.get("/api/books/NOTITLE/related")
        assert resp.status_code == 200
        assert resp.json()["books"] == []
        assert seen["search_by_book"] == []

    def test_book_detail_route_still_answers(self, api):
        """새 경로가 상세 GET /{cnts_id} 를 가리지 않는다."""
        resp = api.client.get(f"/api/books/{SELF}")
        assert resp.status_code == 200
        assert resp.json()["title"] == SELF_TITLE
