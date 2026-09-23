"""test_search_research_path.py — 딥리서치 탐색이 타는 검색 경로.

explore 는 워커의 AsyncSession 을 db 로 넘긴다. 탐색기 테스트는 search 자체를
대역으로 바꾸므로, db 가 있을 때 pipeline.search 안에서 무엇이 도는지(도서
검색용 메타데이터 필터 LLM 등)는 거기서 보이지 않는다. 여기서는 실제
pipeline.search 를 부르고 Milvus·임베딩·리랭커·LLM 호출만 대역으로 바꾼다.

async 테스트는 asyncio.run 으로 돈다(pytest-asyncio 없음 — test_research_runner.py 참고).
"""
import asyncio
import importlib
import sys
import types
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from schemas.book import BookOut
from services.research.explorer import explore
from services.research.state import merge_params

_HEAVY = ("torch", "transformers", "FlagEmbedding", "pymilvus")
_CACHED = ("services.search.pipeline", "services.search.reranker",
           "services.ingestion.embedder", "services.ingestion.indexer")


class _SoftTimeLimitExceeded(Exception):
    """celery 미설치 환경용 대역 — billiard 의 것도 Exception 을 바로 잇는다."""


def _stubbed_pipeline(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
    """test_search_chunk_answer_flag.py 의 로더와 같다 — 정리 방식의 근거도 거기 있다."""
    for name in _HEAVY:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    for name in _CACHED:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield importlib.import_module("services.search.pipeline")
    for name in _CACHED:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)


@pytest.fixture
def pipeline(monkeypatch):
    yield from _stubbed_pipeline(monkeypatch)


def test_loader_restores_modules_and_parent_attributes():
    """이미 올라와 있던 모듈은 sys.modules 와 부모 패키지 속성 둘 다 그대로 돌아와야
    한다 — 속성이 지워지면 뒤 테스트의 문자열 경로 monkeypatch 가 AttributeError 로 죽는다."""
    originals = {name: types.ModuleType(name) for name in _CACHED}
    with pytest.MonkeyPatch.context() as outer:
        for name, module in originals.items():
            parent, _, child = name.rpartition(".")
            outer.setitem(sys.modules, name, module)
            outer.setattr(importlib.import_module(parent), child, module, raising=False)
        with pytest.MonkeyPatch.context() as mp:
            loader = _stubbed_pipeline(mp)
            next(loader)
            next(loader, None)
        for name, module in originals.items():
            parent, _, child = name.rpartition(".")
            assert sys.modules[name] is module
            assert getattr(sys.modules[parent], child, None) is module, name


class _Hit:
    """indexer.search_chunks 가 돌려주는 행 대역."""

    def __init__(self, chunk_idx: int, text: str, *, book_id: str = "A",
                 page: int = 3, score: float = 0.5):
        self.chunk_id = f"{book_id}__{chunk_idx:04d}"
        self.book_id, self.chunk_idx, self.text = book_id, chunk_idx, text
        self.page_start = self.page_end = page
        self.score = score


def _in_order(query, docs):
    """들어온 순서대로 점수를 매기는 리랭커 대역 — 앞에 둔 청크가 1위가 된다."""
    return [SimpleNamespace(index=i, score=1.0 - i * 0.01) for i in range(len(docs))]


def _wire(monkeypatch, pipeline, hits, *, rerank=_in_order) -> dict:
    """Milvus 는 hits 로 고정하고, LLM 을 부르는 전처리·생성은 호출 기록만 남긴다."""
    seen: dict = {"filter": 0, "rewrite": 0, "answer": 0, "reranked": [], "meta_expr": []}

    def _search_chunks(dense, sparse, *, top_k, meta_expr=None):
        seen["meta_expr"].append(meta_expr)
        return list(hits)

    async def _filter(query):
        seen["filter"] += 1
        return pipeline.MetadataFilter(pub_year_from=2006, pub_year_to=2006, has_filter=True)

    async def _rewrite(query, db=None):
        seen["rewrite"] += 1
        return query

    async def _answer(*args, **kwargs):
        seen["answer"] += 1
        return "답변"

    def _rerank(query, docs):
        seen["reranked"].append(list(docs))
        return rerank(query, docs)

    monkeypatch.setattr(pipeline, "search_chunks", _search_chunks)
    monkeypatch.setattr(pipeline, "embed_texts",
                        lambda texts, is_query=False: ([[0.1]], [{1: 0.2}]))
    monkeypatch.setattr(pipeline, "extract_metadata_filter", _filter)
    monkeypatch.setattr(pipeline, "rewrite_query", _rewrite)
    monkeypatch.setattr(pipeline, "rerank_docs", _rerank)
    monkeypatch.setattr(pipeline, "_generate_answer", _answer)
    monkeypatch.setattr(pipeline, "_generate_answer_with_context", _answer)
    return seen


def _search(pipeline, **kwargs):
    base = dict(mode="chunk", top_k=3, use_rewrite=False, doc_scope="paper",
                generate_answer=False, db=MagicMock())
    return asyncio.run(pipeline.search("질문", **{**base, **kwargs}))


class TestMetadataFilterSwitch:
    def test_default_still_runs_the_filter_when_db_is_given(self, monkeypatch, pipeline):
        """기본값은 그대로다 — 도서·논문 검색 API 는 db 를 넘기며 날짜 필터를 쓴다."""
        seen = _wire(monkeypatch, pipeline, [_Hit(4, "본문")])
        _search(pipeline)
        assert seen["filter"] == 1
        assert 'pub_date >= "2006"' in seen["meta_expr"][0]

    def test_off_skips_the_filter_even_with_db(self, monkeypatch, pipeline):
        """하위질문의 사건 연도("2006년 도서관법 개정")가 발행연도 필터가 되면
        그 뒤에 나온 연구가 전부 빠진다."""
        seen = _wire(monkeypatch, pipeline, [_Hit(4, "본문")])
        _search(pipeline, use_metadata_filter=False)
        assert seen["filter"] == 0
        assert "pub_date" not in seen["meta_expr"][0]


class TestChunkFilter:
    _HITS = [
        _Hit(-1, "제목: 논문 가 | 초록: …", page=0),
        _Hit(9, "[초록] 이 연구는 …", page=0),
        _Hit(1, "본문 1"), _Hit(2, "본문 2"), _Hit(3, "본문 3"), _Hit(4, "본문 4"),
    ]

    def test_filter_runs_before_rerank_and_truncation(self, monkeypatch, pipeline):
        """절단 뒤에 거르면 걸러진 수만큼 top_k 가 조용히 준다."""
        seen = _wire(monkeypatch, pipeline, self._HITS)
        resp = _search(pipeline, top_k=3,
                       chunk_filter=lambda c: not (c.chunk_idx == -1 or c.text.startswith("[초록]")))
        assert [c.text for c in resp.chunks] == ["본문 1", "본문 2", "본문 3"]
        assert seen["reranked"] == [["본문 1", "본문 2", "본문 3", "본문 4"]]

    def test_no_filter_keeps_the_live_behavior(self, monkeypatch, pipeline):
        """논문 검색 화면은 chunk_filter 를 안 넘긴다 — 결과가 바뀌면 안 된다."""
        _wire(monkeypatch, pipeline, self._HITS)
        resp = _search(pipeline, top_k=3)
        assert [c.chunk_idx for c in resp.chunks] == [-1, 9, 1]


class TestRerankFallback:
    def _raise(self, exc):
        def _rerank(query, docs):
            raise exc
        return _rerank

    def test_soft_time_limit_is_not_swallowed(self, monkeypatch, pipeline):
        """소프트 리밋 신호는 한 번뿐이다. 폴백이 삼키면 워커의 시간 상한 처리가
        돌지 않고 하드 리밋에 프로세스째 죽는다."""
        _wire(monkeypatch, pipeline, [_Hit(4, "본문")],
              rerank=self._raise(_SoftTimeLimitExceeded()))
        with pytest.raises(_SoftTimeLimitExceeded):
            _search(pipeline, use_rerank=True)

    def test_model_failure_still_falls_back_to_vector_score(self, monkeypatch, pipeline):
        _wire(monkeypatch, pipeline, [_Hit(4, "본문", score=0.42)],
              rerank=self._raise(RuntimeError("CUDA out of memory")))
        resp = _search(pipeline, use_rerank=True)
        assert [(c.score, c.rerank_score) for c in resp.chunks] == [(0.42, None)]

    def test_book_mode_does_not_swallow_it_either(self, monkeypatch, pipeline):
        _wire(monkeypatch, pipeline, [], rerank=self._raise(_SoftTimeLimitExceeded()))
        monkeypatch.setattr(pipeline, "search_by_book",
                            lambda *a, **k: {"A": [_Hit(4, "본문")]})
        with pytest.raises(_SoftTimeLimitExceeded):
            _search(pipeline, mode="book", use_rerank=True)


class _FakeRepo:
    def __init__(self, db):
        pass

    async def get_by_cnts_ids(self, cnts_ids):
        return {
            cid: BookOut(id="00000000-0000-0000-0000-000000000001", cnts_id=cid,
                         title=f"논문 {cid}", created_at="2026-01-01T00:00:00",
                         pub_date="2010-01", kci_citations=0)
            for cid in cnts_ids
        }


class TestExploreThroughRealPipeline:
    """explore → 실제 pipeline.search. 운영 호출 형태(db 있음)에서 무엇이 도는지 본다."""

    # 리랭커 대역이 앞에서부터 점수를 주므로, 걸러지지 않으면 이것들이 상위를 차지한다.
    _HITS = [
        _Hit(-1, "제목: 논문 가 | 기관: … | 초록: …", book_id="A", page=0),
        _Hit(20, "[초록] 이 연구는 공공도서관 …", book_id="A", page=0),
        _Hit(21, "[키워드] 공공도서관, 서비스 품질", book_id="A", page=0),
        _Hit(22, "[표 설명] 이 표는 연도별 예산이 증가했음을 보여준다", book_id="B", page=0),
        _Hit(23, "[그림 설명] 막대그래프가 …", book_id="B", page=0),
        _Hit(0, "첫 쪽 본문", book_id="C", page=0),
        _Hit(5, "본문 가", book_id="A"),
        _Hit(24, "[표]\n예산 추이\n\n| 연도 | 예산 |\n|---|---|\n| 2010 | 3 |", book_id="B", page=0),
        _Hit(6, "본문 나", book_id="B"),
        _Hit(7, "본문 다", book_id="C"),
    ]

    def _explore(self, monkeypatch, pipeline, *, top_k):
        seen = _wire(monkeypatch, pipeline, self._HITS)
        monkeypatch.setattr("services.research.explorer.BookRepository", _FakeRepo)
        ranked, _ = asyncio.run(explore(
            "2006년 도서관법 전부개정이 공공도서관 운영에 미친 영향",
            params=merge_params({"per_subq_top_k": top_k, "citation_weight": 0.0}),
            db=MagicMock(),
        ))
        return seen, ranked

    def test_no_llm_preprocessing_or_generation_runs(self, monkeypatch, pipeline):
        seen, _ = self._explore(monkeypatch, pipeline, top_k=3)
        assert (seen["filter"], seen["rewrite"], seen["answer"]) == (0, 0, 0)
        assert "pub_date" not in seen["meta_expr"][0]

    def test_only_source_passages_reach_rerank_and_hits(self, monkeypatch, pipeline):
        seen, ranked = self._explore(monkeypatch, pipeline, top_k=10)
        expected = ["첫 쪽 본문", "본문 가", self._HITS[7].text, "본문 나", "본문 다"]
        assert seen["reranked"] == [expected]
        assert [h["text"] for h in ranked] == expected

    def test_hit_count_honors_per_subq_top_k(self, monkeypatch, pipeline):
        """메타·보강 청크가 상위 슬롯을 먹어도 본문이 top_k 만큼 남아야 한다."""
        _, ranked = self._explore(monkeypatch, pipeline, top_k=3)
        assert [h["text"] for h in ranked] == ["첫 쪽 본문", "본문 가", self._HITS[7].text]
