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
import re
import sys
from types import SimpleNamespace
from urllib.parse import quote

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
    """indexer.search_chunks 가 돌려주는 행 대역. score 는 Milvus 하이브리드(RRF) 점수, rerank 는 리랭커 대역이 text 로
    찾아 돌려주는 점수다."""

    def __init__(self, book_id: str, chunk_idx: int, score: float, *, rerank: float | None = None,
                 pub_date: str = "1990"):
        self.chunk_id = f"{book_id}__{chunk_idx:04d}"
        self.book_id, self.chunk_idx = book_id, chunk_idx
        self.text = f"{book_id} 본문 {chunk_idx}"
        self.page_start = self.page_end = 3
        self.score = score
        self.rerank = score if rerank is None else rerank
        self.pub_date = pub_date


# RRF(k=60) 점수는 많아야 2/61 ≈ 0.033 이다 — 긴 책의 청크는 이 눈금의 Milvus 점수를 받는다
_RRF = 0.02
# 대역 Milvus 가 조건식에서 읽는 자기 제외 — 실제 Milvus 처럼 창을 자르기 전에 뺀다
_EXCLUDE = re.compile(r'book_id != "([^"]*)"')


def _hits(book_scores: dict, pub_dates: dict[str, str] | None = None) -> list[_Hit]:
    """{책: 점수} → 청크 목록. 점수가 float 면 본문 청크 1개(Milvus·리랭크 모두 그 점수, 로그 부스트 없음 → 연관도 =
    그 점수), (리랭크, n) 이면 리랭크가 그 값인 청크 n개(Milvus 점수는 RRF 눈금) — 로그 부스트를 받는 긴 책이다."""
    out: list[_Hit] = []
    for bid, spec in book_scores.items():
        pub = (pub_dates or {}).get(bid, "1990")
        if isinstance(spec, tuple):
            rerank, n = spec
            out += [_Hit(bid, i, _RRF, rerank=rerank, pub_date=pub) for i in range(n)]
        else:
            out.append(_Hit(bid, 5, spec, pub_date=pub))
    return out


def _wire(monkeypatch, pipeline, book_scores: dict | None = None, *, hits: list[_Hit] | None = None,
          pub_dates: dict[str, str] | None = None, index_ignores_self_condition: bool = False) -> dict:
    """Milvus 대역은 indexer.search_by_book 처럼 조건식의 자기 제외를 먼저 적용하고, Milvus 점수 순 상위
    top_k_chunks 청크를 책으로 묶어 상위 top_k_books 권을 돌려준다.

    재작성·날짜 필터 LLM 은 부르면 seen["llm"] 에 남기고 그럴듯한 값을 돌려준다 — 예외를 던지면 search() 의
    gather(return_exceptions=True) 가 삼켜 테스트가 회귀를 못 본다. 재작성은 다른 질의를, 날짜 필터는 오래된 순
    정렬을 돌려주므로 관련 자료 경로가 사용자 검색으로 돌아가면 임베딩·순서 단언도 깨진다."""
    seen: dict = {"search_by_book": [], "embedded": [], "llm": []}
    pool = sorted(hits if hits is not None else _hits(book_scores or {}, pub_dates),
                  key=lambda h: h.score, reverse=True)
    by_text = {h.text: h.rerank for h in pool}

    def _search_by_book(dense, sparse, top_k_chunks=20, top_k_books=5, *, meta_expr=None):
        seen["search_by_book"].append(
            {"top_k_chunks": top_k_chunks, "top_k_books": top_k_books, "meta_expr": meta_expr})
        m = None if index_ignores_self_condition else _EXCLUDE.search(meta_expr or "")
        window = [h for h in pool if not (m and h.book_id == m.group(1))][:top_k_chunks]
        grouped: dict[str, list[_Hit]] = {}
        for h in window:
            grouped.setdefault(h.book_id, []).append(h)
        order = sorted(grouped, key=lambda b: max(h.score for h in grouped[b]), reverse=True)
        return {b: grouped[b] for b in order[:top_k_books]}

    def _embed(texts, is_query=False):
        seen["embedded"].append((list(texts), is_query))
        return [[0.1]], [{1: 0.2}]

    def _rerank(query, docs):
        return [SimpleNamespace(index=i, score=by_text[d]) for i, d in enumerate(docs)]

    async def _rewrite(query, **kwargs):
        seen["llm"].append(("rewrite", query))
        return f"{query} 연구 동향"

    async def _metadata_filter(query):
        seen["llm"].append(("filter", query))
        return pipeline.MetadataFilter(sort_by="oldest", has_filter=True)

    monkeypatch.setattr(pipeline, "search_by_book", _search_by_book)
    monkeypatch.setattr(pipeline, "embed_texts", _embed)
    monkeypatch.setattr(pipeline, "rerank_docs", _rerank)
    monkeypatch.setattr(pipeline, "rewrite_query", _rewrite)
    monkeypatch.setattr(pipeline, "extract_metadata_filter", _metadata_filter)
    return seen


def _long_self_window() -> list[_Hit]:
    """운영 q1(조선후기 세태소설 연구) 모양 — 자기 청크 400개가 Milvus 상위를 다 차지하고 남의 책은 그 아래 3개씩.
    자기를 조건식에서 빼지 않으면 300자리 창이 자기로만 찬다."""
    own = [_Hit(SELF, i, 0.033 - i * 1e-6, rerank=0.95) for i in range(400)]
    others = [_Hit(bid, i, 0.01 - k * 1e-4 - i * 1e-6, rerank=r)
              for k, (bid, r) in enumerate((("B", 0.8), ("C", 0.7), ("D", 0.6), ("E", 0.5)))
              for i in range(3)]
    return own + others


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

    def test_long_self_does_not_crowd_the_window(self, monkeypatch, pipeline):
        """결함 그 자체 — 자기 청크 400개가 Milvus 상위를 차지해도 300자리 창은 남의 책으로 찬다."""
        seen = _wire(monkeypatch, pipeline, hits=_long_self_window())
        resp = self._run(pipeline)
        assert [b.book_id for b in resp.books] == ["B", "C", "D", "E"]
        assert seen["llm"] == []

    def test_window_is_three_books_and_thirty_chunks_per_fetch_unit(self, monkeypatch, pipeline):
        """사용자 검색과 같은 배수(×3권, 권당 ×10청크)를 쓴다 — fetch_top_k 10 이면 30권·300청크 창."""
        seen = _wire(monkeypatch, pipeline, {"B": 0.8})
        self._run(pipeline, fetch_top_k=10)
        assert seen["search_by_book"][0]["top_k_books"] == 30
        assert seen["search_by_book"][0]["top_k_chunks"] == 300
        assert seen["llm"] == []

    def test_no_llm_is_called_and_the_title_is_embedded_as_is(self, monkeypatch, pipeline):
        """'韓國初期近代詩論硏究'의 初期가 오래된 순 정렬로, '경제백서 1999'의 1999가 연도 필터로 읽히면 안 된다."""
        seen = _wire(monkeypatch, pipeline, {"B": 0.8})
        resp = self._run(pipeline, title="경제백서 1999", exclude_id="CNTS-00049655779")
        assert seen["llm"] == []
        assert seen["embedded"] == [(["경제백서 1999"], True)]
        assert resp.query == "경제백서 1999"
        assert resp.rewritten_query is None

    def test_books_come_back_in_score_order_not_date_order(self, monkeypatch, pipeline):
        """날짜 필터가 불렸다면 오래된 순(B 1980 → D 1990 → C 2000)이 된다 — 대역 날짜 필터는 늘 오래된 순을 돌려준다."""
        seen = _wire(monkeypatch, pipeline, {"B": 0.5, "C": 0.9, "D": 0.7},
                     pub_dates={"B": "1980", "C": "2000", "D": "1990"})
        resp = self._run(pipeline)
        assert [b.book_id for b in resp.books] == ["C", "D", "B"]
        assert seen["llm"] == []

    @pytest.mark.parametrize("bad", ['X" || book_id != "Y', "A\\B", "it's", "CNTS-1\n", "CNTS\t1", ""])
    def test_unsafe_id_is_refused_before_it_reaches_the_expression(self, monkeypatch, pipeline, bad):
        """id 는 조건식의 큰따옴표 문자열에 그대로 들어간다 — 그 문자열을 끝내거나 이스케이프로 읽히는 글자(따옴표·
        역슬래시·제어 문자)는 받지 않는다($ 는 끝 줄바꿈을 통과시킨다)."""
        seen = _wire(monkeypatch, pipeline, {"B": 0.8})
        with pytest.raises(ValueError):
            self._run(pipeline, exclude_id=bad)
        assert seen["search_by_book"] == []

    # 업로드 적재는 파일 이름(확장자 뺀 것)을 id 로 쓴다(api/book.py upload_and_ingest → stages Book(cnts_id=book_id))
    @pytest.mark.parametrize("ok", [SELF, "KCI_FI001234567", "NL.abc-01_x", "CNTS 1",
                                    "조선후기 세태소설 연구(최종본)", "보고서 [2024] #3 & 부록"])
    def test_catalog_and_upload_ids_are_safe(self, pipeline, ok):
        assert pipeline.is_safe_book_id(ok)

    def test_upload_id_goes_into_the_expression_verbatim(self, monkeypatch, pipeline):
        seen = _wire(monkeypatch, pipeline, {"B": 0.8})
        self._run(pipeline, exclude_id="조선후기 세태소설 연구(최종본)")
        assert 'book_id != "조선후기 세태소설 연구(최종본)"' in seen["search_by_book"][0]["meta_expr"]


# ── GET /api/books/{cnts_id}/related ─────────────────────
_FORGET = ("api.book",)


class _Api:
    def __init__(self, client, engine, pipeline, monkeypatch):
        self.client, self.engine, self.pipeline, self._mp = client, engine, pipeline, monkeypatch

    def wire(self, book_scores: dict | None = None, **kw) -> dict:
        return _wire(self._mp, self.pipeline, book_scores, **kw)

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
                       ("F", "임 계"), ("G", "자 축"), ("L", "Pride and Prejudice"), ("T", "조선후기 세태소설")):
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

    @pytest.mark.parametrize("rerank, n", [(0.0, 20), (0.0, 30), (0.05, 16)])
    def test_long_unrelated_book_is_not_lifted_over_the_floor_by_its_chunk_count(self, api, rerank, n):
        """로그 부스트 1-(1-r)/(1+0.1·log2 n) 은 리랭크가 0 이어도 청크 20개면 0.30, 30개면 0.33 이다(r=0.05 면 16개로
        넘는다). 새 창은 자기 청크가 빠져 긴 남의 책이 청크를 더 받으므로 하한을 정한 관측보다 점수가 위로 밀린다 —
        하한은 부스트 전 원점수에도 건다."""
        api.wire({"B": 0.8, "L": (rerank, n)})
        lifted = asyncio.run(api.pipeline.search_related_books(SELF_TITLE, SELF, fetch_top_k=10))
        # 전제: 부스트만으로 종합 하한(0.3)을 넘는다 — 영어 제목이라 제목 일치는 0
        assert next(b for b in lifted.books if b.book_id == "L").best_score >= 0.3
        books = api.client.get(f"/api/books/{SELF}/related").json()["books"]
        assert [b["book_id"] for b in books] == ["B"]

    def test_long_related_book_is_kept_with_its_boosted_score(self, api):
        """원점수가 하한 이상인 긴 책은 그대로 둔다 — 화면의 연관도는 검색 결과 카드처럼 부스트 뒤 값이다."""
        api.wire({"L": (0.35, 30)})
        books = api.client.get(f"/api/books/{SELF}/related").json()["books"]
        assert [b["book_id"] for b in books] == ["L"]
        assert books[0]["content_score"] == pytest.approx(1 - 0.65 / 1.4907, abs=1e-3)

    def test_title_alone_over_the_floor_needs_no_passage_evidence(self, api):
        """제목만으로 하한을 넘는 책('조선후기 세태소설' ⊂ 원제목 → 제목 일치 1.0)은 부스트와 상관없이 넘으므로
        본문 원점수를 묻지 않는다."""
        api.wire({"T": (0.05, 3)})
        books = api.client.get(f"/api/books/{SELF}/related").json()["books"]
        assert [b["book_id"] for b in books] == ["T"]
        assert books[0]["title_score"] == 1.0

    def test_self_never_comes_back_even_if_the_index_returns_it(self, api):
        api.wire({SELF: 0.99, "B": 0.8}, index_ignores_self_condition=True)
        books = api.client.get(f"/api/books/{SELF}/related").json()["books"]
        assert [b["book_id"] for b in books] == ["B"]

    def test_long_self_does_not_leave_a_single_related_book(self, api):
        """운영 q1: 자기 청크가 창(180자리 중 178)을 채워 관련 자료가 1권만 남던 것 — 이제 4칸이 찬다."""
        seen = api.wire(hits=_long_self_window())
        books = api.client.get(f"/api/books/{SELF}/related").json()["books"]
        assert [b["book_id"] for b in books] == ["B", "C", "D", "E"]
        assert seen["llm"] == []

    def test_searches_by_the_catalog_title_without_self(self, api):
        seen = api.wire(SIX)
        api.client.get(f"/api/books/{SELF}/related")
        assert seen["llm"] == []
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

    def test_uploaded_book_with_a_hangul_file_name_id_has_related(self, api):
        """업로드 자료는 파일 이름이 id 다 — 한글·공백·괄호가 든 id 도 404 가 아니라 관련 자료를 받는다."""
        upload_id = "조선후기 세태소설 연구(최종본)"
        add_book(api.engine, upload_id, title=upload_id, doc_type="literature")
        seen = api.wire(SIX)
        resp = api.client.get(f"/api/books/{quote(upload_id)}/related")
        assert resp.status_code == 200
        assert [b["book_id"] for b in resp.json()["books"]] == ["B", "C", "D", "E"]
        assert f'book_id != "{upload_id}"' in seen["search_by_book"][0]["meta_expr"]

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
