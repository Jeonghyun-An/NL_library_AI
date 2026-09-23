"""test_research_explorer.py — 하위질문 탐색.

explore() 는 Milvus·GPU 없이도 대역으로 검증한다. 실제 pipeline 을 import 하면
reranker → torch 가 필요해 수집 단계에서 세션이 통째로 죽으므로, explore 안의
지연 import 를 sys.modules 로 가로챈다.
"""
import ast
import asyncio
import logging
import sys
import types
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from schemas.book import BookOut, ChunkHit, ChunkSearchResponse
from services.research.explorer import explore, is_source_passage, rank_hits
from services.research.state import merge_params

_DB = object()          # explore 가 그대로 흘려보내기만 하는 세션 자리


class TestRankHits:
    def _hit(self, book_id, score):
        return {"book_id": book_id, "chunk_id": f"{book_id}-c", "text": "t",
                "page_start": 1, "page_end": 1, "score": score}

    def _meta(self, pub_date, citations):
        return {"title": "t", "pub_date": pub_date, "kci_citations": citations}

    def test_empty_input(self):
        assert rank_hits([], {}, citation_weight=0.2, now_year=2026) == []

    def test_missing_metadata_scores_as_zero_impact(self):
        hits = [self._hit("A", 0.9)]
        ranked = rank_hits(hits, {}, citation_weight=0.2, now_year=2026)
        assert ranked[0]["rank_score"] == pytest.approx(0.9)

    def test_raw_score_is_kept_and_blend_goes_to_rank_score(self):
        """score 는 화면에 유사도로 나간다 — 혼합값을 덮어쓰면 141% 가 표시되고
        생 리랭킹 점수를 되찾을 길이 없어진다."""
        hits = [self._hit("A", 0.92)]
        ranked = rank_hits(hits, {"A": self._meta("2024-01", 40)},
                           citation_weight=0.2, now_year=2026)
        assert ranked[0]["score"] == pytest.approx(0.92)
        assert ranked[0]["rank_score"] > 1.0

    def test_impact_reorders_close_scores(self):
        hits = [self._hit("OLD", 0.81), self._hit("NEW", 0.80)]
        meta = {
            "OLD": self._meta("2002-01", 50),    # 50/25 = 2.0
            "NEW": self._meta("2024-01", 40),    # 40/3  = 13.3
        }
        ranked = rank_hits(hits, meta, citation_weight=0.2, now_year=2026)
        assert ranked[0]["book_id"] == "NEW"

    def test_zero_weight_preserves_rerank_order(self):
        hits = [self._hit("OLD", 0.81), self._hit("NEW", 0.80)]
        meta = {"OLD": self._meta("2002-01", 50), "NEW": self._meta("2024-01", 40)}
        ranked = rank_hits(hits, meta, citation_weight=0.0, now_year=2026)
        assert ranked[0]["book_id"] == "OLD"

    def test_null_citations_with_valid_year(self):
        """kci_citations 는 nullable 이다 — 한 편이 None 이라고 하위질문 전체가
        TypeError 로 죽으면 안 된다."""
        ranked = rank_hits([self._hit("A", 0.9)], {"A": self._meta("2008-06", None)},
                           citation_weight=0.2, now_year=2026)
        assert ranked[0]["rank_score"] == pytest.approx(0.9)

    def test_original_hits_are_not_mutated(self):
        hits = [self._hit("A", 0.9)]
        rank_hits(hits, {"A": self._meta("2008-01", 10)}, citation_weight=0.2, now_year=2026)
        assert hits[0]["score"] == pytest.approx(0.9)
        assert "rank_score" not in hits[0]


def _chunk(book_id, *, chunk_idx=4, text="본문", score=0.5, rerank_score=0.8, pages=(3, 4)):
    """실제 ChunkHit 을 쓴다 — explore 가 읽는 필드가 스키마에 실재하는지도 같이 본다."""
    return ChunkHit(
        chunk_id=f"{book_id}__{chunk_idx:04d}", book_id=book_id, chunk_idx=chunk_idx,
        text=text, page_start=pages[0], page_end=pages[1], score=score, rerank_score=rerank_score,
    )


def _book(cnts_id, *, title="논문 가", pub_date="2008-06", kci_citations=3):
    """실제 BookOut 을 쓴다 — explore 가 방어 없이 직접 속성 접근으로 읽는 7개
    필드(title·personal_author·series_title·vol_issue·pub_date·kci_citations·grade)가
    스키마에 실재하는지 여기서 고정된다."""
    return BookOut(
        id=uuid4(), cnts_id=cnts_id, title=title, created_at=datetime(2026, 1, 1),
        personal_author="저자", series_title="학술지", vol_issue="12(3)",
        pub_date=pub_date, kci_citations=kci_citations, grade="등재",
    )


class _FakeSearch:
    """pipeline.search 대역 — 호출 kwargs 를 그대로 붙잡아 둔다.

    chunk_filter 와 top_k 는 실물과 같은 순서(거른 뒤 자른다)로 적용한다. 실제
    파이프라인을 거치는 확인은 test_search_research_path.py 에 있다.
    """

    def __init__(self, chunks):
        self._chunks = chunks
        self.calls: list[dict] = []

    async def __call__(self, query, **kwargs):
        self.calls.append({"query": query, **kwargs})
        keep = kwargs.get("chunk_filter") or (lambda c: True)
        chunks = [c for c in self._chunks if keep(c)][: kwargs["top_k"]]
        return ChunkSearchResponse(query=query, chunks=chunks, elapsed_ms=1.0)


class _FakeRepo:
    """BookRepository 대역. 클래스 자리에 인스턴스를 꽂아 `BookRepository(db)` 를 받는다."""

    def __init__(self, books):
        self._books = books
        self.requested: list[str] = []

    def __call__(self, db):
        return self

    async def get_by_cnts_ids(self, cnts_ids):
        # 실물처럼 찾은 것만 돌려준다 — 없는 cnts_id 는 키가 아예 빠진다.
        self.requested = list(cnts_ids)
        return {k: v for k, v in self._books.items() if k in cnts_ids}


def _pipeline_search_params() -> set[str]:
    """pipeline.search 의 인자 이름을 소스에서 읽는다.

    import 하면 torch 가 필요해 로컬에서 수집 단계가 죽는다. explore 가 넘기는
    kwarg 가 파이프라인에 실재하는지는 확인해야 하고(어긋나면 워커에서
    TypeError 로만 드러난다) 시그니처만 보면 되므로 ast 로 읽는다.
    """
    src = (Path(__file__).resolve().parents[1] / "services" / "search" / "pipeline.py")
    fn = next(
        node for node in ast.parse(src.read_text(encoding="utf-8")).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "search"
    )
    return {a.arg for a in fn.args.args + fn.args.kwonlyargs}


class TestIsSourcePassage:
    """인용칩이 "원문 대목"으로 띄울 수 있는 청크인가. 판단 근거는 explorer 주석."""

    def test_body_chunk_is_kept(self):
        assert is_source_passage(_chunk("A"))

    def test_metadata_chunk_is_dropped(self):
        assert not is_source_passage(_chunk("A", chunk_idx=-1, text="제목: … | 초록: …"))

    @pytest.mark.parametrize("text", [
        "[초록] 이 연구는 공공도서관 …",
        "[키워드] 공공도서관, 서비스 품질",
        "[표 설명] 이 표는 연도별 예산이 증가했음을 보여준다",
        "[그림 설명] 막대그래프가 …",
    ])
    def test_generated_or_duplicate_enrichment_is_dropped(self, text):
        assert not is_source_passage(_chunk("A", chunk_idx=20, text=text, pages=(0, 0)))

    def test_verbatim_table_chunk_is_kept(self):
        text = "[표]\n예산 추이\n\n| 연도 | 예산 |\n|---|---|"
        assert is_source_passage(_chunk("A", chunk_idx=20, text=text, pages=(0, 0)))

    def test_page_zero_body_is_kept(self):
        """첫 쪽 본문, PDF 없이 초록을 본문으로 쓴 논문의 본문도 쪽수가 0 이다."""
        assert is_source_passage(_chunk("A", chunk_idx=0, text="서론 …", pages=(0, 0)))

    def test_label_lookalike_in_paged_body_is_kept(self):
        """보강 청크는 쪽수가 늘 0 이다 — 쪽수가 있으면 본문에 우연히 나온 글자다."""
        assert is_source_passage(_chunk("A", text="[표 설명] 아래 표는 …"))


class TestExplore:
    def _run(self, monkeypatch, *, chunks, books, params=None):
        fake_search = _FakeSearch(chunks)
        module = types.ModuleType("services.search.pipeline")
        module.search = fake_search
        monkeypatch.setitem(sys.modules, "services.search.pipeline", module)
        fake_repo = _FakeRepo(books)
        monkeypatch.setattr("services.research.explorer.BookRepository", fake_repo)
        ranked, meta = asyncio.run(
            explore("하위질문", params=merge_params(params or {}), db=_DB)
        )
        return fake_search, fake_repo, ranked, meta

    def test_search_receives_retrieval_only_kwargs(self, monkeypatch):
        """딥리서치는 검색만 필요하다 — 답변 생성·쿼리 재작성·메타데이터 필터를
        끄고, 원문 대목만 남기는 필터를 리랭크·절단 전에 건다."""
        fake_search, _, _, _ = self._run(
            monkeypatch, chunks=[_chunk("A")], books={"A": _book("A")},
            params={"per_subq_top_k": 7},
        )
        assert fake_search.calls == [{
            "query": "하위질문", "mode": "chunk", "top_k": 7, "doc_scope": "paper",
            "generate_answer": False, "use_rewrite": False, "use_metadata_filter": False,
            "chunk_filter": is_source_passage, "db": _DB,
        }]

    def test_every_kwarg_exists_on_the_real_pipeline(self, monkeypatch):
        """대역은 **kwargs 로 다 받는다 — 파이프라인에서 인자명이 바뀌어도 초록불이
        유지되고 워커가 TypeError 로 죽는다. 실제 시그니처와 맞춰 둔다."""
        fake_search, _, _, _ = self._run(
            monkeypatch, chunks=[_chunk("A")], books={"A": _book("A")},
        )
        assert set(fake_search.calls[0]) <= _pipeline_search_params()

    def test_rerank_zero_is_not_treated_as_missing(self, monkeypatch):
        """0.0 은 "리랭커가 이 청크를 버렸다"는 정보다. falsy 라고 벡터 점수로
        되돌리면 버려진 청크가 0.7 로 되살아난다."""
        _, _, ranked, _ = self._run(
            monkeypatch, chunks=[_chunk("A", score=0.7, rerank_score=0.0)],
            books={"A": _book("A")},
        )
        assert ranked[0]["score"] == pytest.approx(0.0)

    def test_rerank_none_falls_back_to_vector_score(self, monkeypatch):
        """리랭킹이 실패하면 rerank_score 가 없는 채로 내려온다."""
        _, _, ranked, _ = self._run(
            monkeypatch, chunks=[_chunk("A", score=0.42, rerank_score=None)],
            books={"A": _book("A")},
        )
        assert ranked[0]["score"] == pytest.approx(0.42)

    def test_metadata_chunk_is_excluded(self, monkeypatch):
        """chunk_idx=-1 은 카탈로그 서지 덩어리다 — 제목·초록을 품어 점수가 잘
        나오지만 발췌로 인용되면 "논문 발췌 (p.0-0)" 가 된다."""
        chunks = [
            _chunk("A", chunk_idx=-1, text="제목: 논문 가 | 기관: … | 초록: …", rerank_score=0.99),
            _chunk("A", chunk_idx=4, rerank_score=0.5),
        ]
        _, _, ranked, _ = self._run(monkeypatch, chunks=chunks, books={"A": _book("A")})
        assert [h["chunk_id"] for h in ranked] == ["A__0004"]

    def test_only_metadata_chunks_gives_no_hits(self, monkeypatch):
        _, fake_repo, ranked, meta = self._run(
            monkeypatch, chunks=[_chunk("A", chunk_idx=-1)], books={"A": _book("A")},
        )
        assert (ranked, meta) == ([], {})
        assert fake_repo.requested == []

    def test_hits_without_bibliography_are_dropped(self, monkeypatch):
        """서지를 못 찾으면 근거가 될 수 없다 — build_evidence 가 말없이 버리므로
        여기서 떨궈야 근거 수가 왜 모자란지 드러난다."""
        chunks = [_chunk("A"), _chunk("GONE")]
        _, _, ranked, meta = self._run(monkeypatch, chunks=chunks, books={"A": _book("A")})
        assert [h["book_id"] for h in ranked] == ["A"]
        assert set(meta) == {"A"}

    def test_dropped_hits_are_logged(self, monkeypatch, caplog):
        chunks = [_chunk("A"), _chunk("GONE")]
        with caplog.at_level(logging.WARNING, logger="services.research.explorer"):
            self._run(monkeypatch, chunks=chunks, books={"A": _book("A")})
        assert "GONE" in caplog.text

    def test_meta_carries_the_bibliography_fields(self, monkeypatch):
        _, _, _, meta = self._run(
            monkeypatch, chunks=[_chunk("A")], books={"A": _book("A")},
        )
        assert meta == {"A": {
            "title": "논문 가", "personal_author": "저자", "series_title": "학술지",
            "vol_issue": "12(3)", "pub_date": "2008-06", "kci_citations": 3,
            "grade": "등재",
        }}

    def test_no_chunks_returns_empty(self, monkeypatch):
        _, fake_repo, ranked, meta = self._run(monkeypatch, chunks=[], books={})
        assert (ranked, meta) == ([], {})
        assert fake_repo.requested == []
