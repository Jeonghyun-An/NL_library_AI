"""services/research_work/passages.py·section_input.py — 절 생성 입력(원문 대목·수치·근거 블록).

passages 의 clip·snapshot_passages 와 section_input 은 순수 함수라 그대로 부른다. milvus_passages·pick_excerpt 는
FastAPI 에서만 도는 리랭커·Milvus 를 함수 안에서 import 한다(함정 13) — 로컬 venv 에 없는 torch·transformers·
FlagEmbedding·pymilvus 를 MagicMock 으로 채우고 검색 모듈을 새로 import 한 뒤(test_search_research_path.py 의
로더와 같은 방식) ensure_collection·compute_scores 만 대역으로 바꾼다.
"""
import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.research_work import passages, section_input
from services.research_work.passages import CLIP_WINDOW, clip, snapshot_passages
from services.research_work.section_input import (
    evidence_block, figure_block, gap_input, gap_seeds, prior_input, section_figures, section_papers,
)
from services.research_work.shapes import ABSTRACT_CHARS, EXCERPT_CHARS, SECTION_PAPERS_MAX

_HEAVY = ("torch", "transformers", "FlagEmbedding", "pymilvus")
_CACHED = ("services.search.pipeline", "services.search.reranker",
           "services.ingestion.embedder", "services.ingestion.indexer")


class _MilvusException(Exception):
    """pymilvus 미설치 환경용 대역 — 실제 MilvusException 처럼 message 키워드를 받는다."""

    def __init__(self, code: int = 1, message: str = ""):
        super().__init__(message)


@pytest.fixture
def search(monkeypatch):
    """무거운 모듈을 대역으로 채우고 (indexer, reranker, MilvusException) 을 준다. 끝나면 import 전 그대로 되돌린다."""
    for name in _HEAVY:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    try:
        importlib.import_module("pymilvus.exceptions")
    except ModuleNotFoundError:
        exc = types.ModuleType("pymilvus.exceptions")
        exc.MilvusException = _MilvusException
        monkeypatch.setitem(sys.modules, "pymilvus.exceptions", exc)
    for name in _CACHED:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    importlib.import_module("services.search.pipeline")
    yield SimpleNamespace(
        indexer=sys.modules["services.ingestion.indexer"],
        reranker=sys.modules["services.search.reranker"],
        MilvusException=sys.modules["pymilvus.exceptions"].MilvusException,
    )
    for name in _CACHED:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)


# ── 원문 대목 ─────────────────────────────────────────────────────────


class TestClip:
    def test_short_text_is_kept(self):
        assert clip("  노인의 우울을 다룬다.  ") == "노인의 우울을 다룬다."

    def test_cuts_after_the_last_sentence_end_near_the_limit_without_an_ellipsis(self):
        text = "가" * 1150 + "다. " + "나" * 200
        out = clip(text)
        assert out == "가" * 1150 + "다."
        assert not out.endswith("…") and len(out) <= EXCERPT_CHARS

    def test_falls_back_to_the_last_space(self):
        text = "가" * 1150 + " " + "나" * 30 + " " + "다" * 200
        assert clip(text) == "가" * 1150 + " " + "나" * 30

    def test_hard_cut_when_the_window_has_no_boundary(self):
        text = "가" * 1050 + ". " + "나" * 400       # 문장 끝이 끝 100자 구간보다 앞에 있다
        assert clip(text) == ("가" * 1050 + ". " + "나" * 400)[:EXCERPT_CHARS]
        assert CLIP_WINDOW == 100

    def test_custom_limit(self):
        assert clip("첫 문장이다. 둘째 문장이다.", 10) == "첫 문장이다."


SNAPSHOT = {
    "evidence": {
        "E1": {"cnts_id": "KCI_A", "meta": {"title": "노인 우울"}, "chunks": [
            {"chunk_id": "KCI_A__0003", "text": "본문 셋", "page_start": 4, "page_end": 5, "score": 0.4},
            {"chunk_id": "KCI_A__0001", "text": "본문 하나", "page_start": 2, "page_end": 2, "score": 0.9},
            {"chunk_id": "KCI_A__0040", "text": "[초록] 초록 그대로", "page_start": 0, "page_end": 0, "score": 0.95},
            {"chunk_id": "KCI_A__-001", "text": "제목: 노인 우울 | 초록: …", "page_start": 0, "page_end": 0,
             "score": 0.99},
            {"chunk_id": "KCI_A__0001", "text": "본문 하나", "page_start": 2, "page_end": 2, "score": 0.9},
        ]},
        "E2": {"cnts_id": "KCI_B", "meta": {}, "chunks": [
            {"chunk_id": "KCI_B__0000", "text": "다른 논문", "page_start": 0, "page_end": 0, "score": 0.7},
        ]},
    },
}


class TestSnapshotPassages:
    def test_source_chunks_of_that_paper_best_score_first_once_each(self):
        assert snapshot_passages(SNAPSHOT, "KCI_A") == [
            {"chunk_id": "KCI_A__0001", "text": "본문 하나", "page_start": 2, "page_end": 2, "score": 0.9},
            {"chunk_id": "KCI_A__0003", "text": "본문 셋", "page_start": 4, "page_end": 5, "score": 0.4},
        ]

    def test_first_page_body_chunk_is_a_source_passage(self):
        # 쪽 0 이라도 보강 라벨이 없으면 본문이다(PyMuPDF 쪽 번호가 0 부터)
        assert [p["chunk_id"] for p in snapshot_passages(SNAPSHOT, "KCI_B")] == ["KCI_B__0000"]

    @pytest.mark.parametrize("snapshot", [None, {}, {"evidence": None}])
    def test_missing_snapshot_or_paper_gives_nothing(self, snapshot):
        assert snapshot_passages(snapshot, "KCI_A") == []
        assert snapshot_passages(SNAPSHOT, "KCI_Z") == []


class _Collection:
    def __init__(self, rows=None, error: Exception | None = None):
        self.rows, self.error, self.calls = rows or [], error, []

    def query(self, **kw):
        self.calls.append(kw)
        if self.error is not None:
            raise self.error
        return self.rows


class TestMilvusPassages:
    def test_reads_one_paper_body_chunks_in_order_without_enrichment(self, search, monkeypatch):
        col = _Collection(rows=[
            {"chunk_id": "KCI_A__0002", "chunk_idx": 2, "text": "둘째 쪽", "page_start": 3, "page_end": 3},
            {"chunk_id": "KCI_A__0030", "chunk_idx": 30, "text": "[표 설명] 모델이 쓴 설명", "page_start": 0,
             "page_end": 0},
            {"chunk_id": "KCI_A__0000", "chunk_idx": 0, "text": "첫 쪽", "page_start": 0, "page_end": 0},
        ])
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: col)

        out = passages.milvus_passages("KCI_A")

        assert [p["chunk_id"] for p in out] == ["KCI_A__0000", "KCI_A__0002"]
        assert out[1] == {"chunk_id": "KCI_A__0002", "text": "둘째 쪽", "page_start": 3, "page_end": 3,
                          "score": None}
        (call,) = col.calls
        assert call["expr"] == 'book_id == "KCI_A" && chunk_idx >= 0'
        assert set(call["output_fields"]) == {"chunk_id", "chunk_idx", "text", "page_start", "page_end"}

    @pytest.mark.parametrize("error", [RuntimeError("스키마 불일치"), OSError("연결 끊김")])
    def test_known_failures_give_no_passages(self, search, monkeypatch, error):
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: _Collection(error=error))
        assert passages.milvus_passages("KCI_A") == []

    def test_milvus_exception_gives_no_passages(self, search, monkeypatch):
        error = search.MilvusException(message="milvus down")
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: _Collection(error=error))
        assert passages.milvus_passages("KCI_A") == []

    def test_other_errors_are_not_swallowed(self, search, monkeypatch):
        # 함정 19 — 실제로 나는 실패 타입만 받는다. 코드 결함은 그대로 올라간다
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: _Collection(error=KeyError("x")))
        with pytest.raises(KeyError):
            passages.milvus_passages("KCI_A")

    def test_unsafe_id_is_not_put_into_the_expression(self, search, monkeypatch):
        col = _Collection()
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: col)
        assert passages.milvus_passages('KCI_A" || book_id != "') == []
        assert col.calls == []


CANDIDATES = [
    {"chunk_id": "c1", "text": "첫 대목이다.", "page_start": 2, "page_end": 2, "score": 0.5},
    {"chunk_id": "c2", "text": "가" * 1300, "page_start": 7, "page_end": 8, "score": 0.9},
    {"chunk_id": "c3", "text": "셋째 대목이다.", "page_start": 9, "page_end": 9, "score": None},
]


class TestPickExcerpt:
    def test_reranker_best_is_picked_and_clipped(self, search, monkeypatch):
        seen = {}

        def _scores(query, documents):
            seen["args"] = (query, documents)
            return [0.2, 0.3, 0.8]

        monkeypatch.setattr(search.reranker, "compute_scores", _scores)

        out = passages.pick_excerpt("노인 우울 사회적 지지", CANDIDATES)

        assert out == {"chunk_id": "c3", "page_start": 9, "page_end": 9, "text": "셋째 대목이다."}
        assert seen["args"] == ("노인 우울 사회적 지지", [c["text"] for c in CANDIDATES])

    def test_long_best_passage_is_clipped_to_the_limit(self, search, monkeypatch):
        monkeypatch.setattr(search.reranker, "compute_scores", lambda q, d: [0.1, 0.9, 0.1])
        out = passages.pick_excerpt("질의", CANDIDATES)
        assert out["chunk_id"] == "c2" and out["text"] == "가" * EXCERPT_CHARS

    @pytest.mark.parametrize("error", [RuntimeError("CUDA out of memory"), OSError("모델 없음"),
                                       ValueError("토크나이저"), ImportError("torch")])
    def test_reranker_failure_falls_back_to_the_stored_score(self, search, monkeypatch, error):
        def _broken(query, documents):
            raise error

        monkeypatch.setattr(search.reranker, "compute_scores", _broken)
        assert passages.pick_excerpt("질의", CANDIDATES, limit=20)["chunk_id"] == "c2"

    def test_other_reranker_errors_propagate(self, search, monkeypatch):
        def _broken(query, documents):
            raise KeyError("코드 결함")

        monkeypatch.setattr(search.reranker, "compute_scores", _broken)
        with pytest.raises(KeyError):
            passages.pick_excerpt("질의", CANDIDATES)

    def test_no_candidates_gives_none_without_loading_the_reranker(self):
        assert passages.pick_excerpt("질의", []) is None


# ── 절 입력 ───────────────────────────────────────────────────────────


class TestSectionFigures:
    def test_count_year_range_and_corpus(self):
        assert section_figures([2015, 2008, 2011], {"n_papers": 144748, "from": "1980", "to": "2017"}, 6) == [
            {"id": "F1", "label": "이 절에 준 논문 수", "value": "6"},
            {"id": "F2", "label": "발행 연도 범위", "value": "2008~2015"},
            {"id": "F3", "label": "소장 KCI 적재분 논문 수", "value": "144,748"},
        ]

    def test_one_year_is_that_year(self):
        assert section_figures([2013, 2013], None, 2)[1] == {"id": "F2", "label": "발행 연도 범위",
                                                            "value": "2013"}

    def test_missing_parts_are_left_out_and_numbers_stay_dense(self):
        assert section_figures([], {"n_papers": 1200}, 1) == [
            {"id": "F1", "label": "이 절에 준 논문 수", "value": "1"},
            {"id": "F2", "label": "소장 KCI 적재분 논문 수", "value": "1,200"},
        ]
        assert section_figures([], None, 3) == [{"id": "F1", "label": "이 절에 준 논문 수", "value": "3"}]


SEED = {"key": "future:1:0", "kind": "future", "section_idx": 1, "subq_idx": 1, "heading": "노인의 사회적 지지",
        "text": "농촌 노인 표본이 부족하다", "papers": ["KCI_A", "KCI_B"], "adopted": 9}


def _seed(key: str, section_idx: int | None, subq_idx: int | None, papers: list[str]) -> dict:
    return {**SEED, "key": key, "section_idx": section_idx, "subq_idx": subq_idx, "text": key, "papers": papers}


class TestGapSeeds:
    def test_picked_seed_first_then_seeds_of_the_same_section_or_subquestion(self, monkeypatch):
        calls = []
        pool = [_seed("future:0:0", 0, 0, ["X"]), _seed("future:1:1", 1, 1, ["KCI_C"]),
                _seed("insufficient:1", None, 1, ["KCI_D"]), _seed("future:2:0", 2, 2, ["Y"]),
                _seed("future:1:2", 1, 1, ["KCI_E"]), _seed("future:1:3", 1, 1, ["KCI_F"])]

        def _pick(report, *, limit, exclude=()):
            calls.append((limit, set(exclude)))
            return [s for s in pool if s["key"] not in exclude]

        monkeypatch.setattr(section_input, "pick_seeds", _pick)

        out = gap_seeds(SEED, {"sections": []})

        assert [s["key"] for s in out] == ["future:1:0", "future:1:1", "insufficient:1", "future:1:2"]
        assert calls == [(None, {"future:1:0"})]

    def test_user_card_takes_three_seeds_from_the_whole_report(self, monkeypatch):
        calls = []

        def _pick(report, *, limit, exclude=()):
            calls.append(limit)
            return [_seed(f"future:{i}:0", i, i, ["X"]) for i in range(limit)]

        monkeypatch.setattr(section_input, "pick_seeds", _pick)

        assert [s["key"] for s in gap_seeds({}, {"sections": []})] == ["future:0:0", "future:1:0", "future:2:0"]
        assert calls == [3]


class TestSectionPapers:
    def test_keeps_order_drops_repeats_and_caps(self):
        ids = ["A", "B", "A", "C", "D", "E", "F", "G", ""]
        assert section_papers(ids) == ["A", "B", "C", "D", "E", "F"]
        assert SECTION_PAPERS_MAX == 6
        assert section_papers(ids, limit=2) == ["A", "B"]


PAPERS = [
    {"eid": "E1", "cnts_id": "KCI_A", "title": "노인 우울과 가족 지지", "year": 2013, "abstract": "초록 하나",
     "excerpt": {"chunk_id": "KCI_A__0001", "page_start": 2, "page_end": 3, "text": "대목 하나"}},
    {"eid": "E2", "cnts_id": "KCI_B", "title": "사회적 지지 척도", "year": None, "abstract": "",
     "excerpt": {"chunk_id": "KCI_B__0000", "page_start": 0, "page_end": 0, "text": "대목 둘"}},
    {"eid": "E3", "cnts_id": "KCI_C", "title": "독거 노인", "year": 2016, "abstract": "초록 셋", "excerpt": None},
]


class TestBlocks:
    def test_evidence_block_lines(self):
        assert evidence_block(PAPERS) == (
            "[E1] 노인 우울과 가족 지지 (2013)\n초록: 초록 하나\n대목(쪽 3~4): 대목 하나\n\n"
            "[E2] 사회적 지지 척도\n대목: 대목 둘\n\n"
            "[E3] 독거 노인 (2016)\n초록: 초록 셋"
        )

    def test_one_page_excerpt(self):
        paper = {**PAPERS[0], "excerpt": {**PAPERS[0]["excerpt"], "page_end": 2}}
        assert "대목(쪽 3): 대목 하나" in evidence_block([paper])

    def test_figure_block_lines(self):
        figures = section_figures([2013], None, 2)
        assert figure_block(figures) == "[F1] 이 절에 준 논문 수: 2\n[F2] 발행 연도 범위: 2013"

    def test_empty_blocks(self):
        assert evidence_block([]) == "(없음)" and figure_block([]) == "(없음)"


def _book(title: str, pub_date: str | None, abstract: str | None):
    return SimpleNamespace(title=title, pub_date=pub_date, abstract=abstract)


BOOKS = {
    "KCI_A": _book("노인 우울과 가족 지지", "2013-06", "가" * 700),
    "KCI_B": _book("사회적 지지 척도", None, None),
    "KCI_C": _book("독거 노인", "2016", "초록 셋"),
}
TOPIC = {"id": 12, "title": "농촌 독거노인의 사회적 지지와 우울", "question": "어떤 지지가 우울을 낮추는가?"}
GROUP = {"key": "prior.g1", "name": "가족 지지와 우울", "hint": "노인의 우울",
         "papers": ["KCI_A", "KCI_B", "KCI_C", "KCI_D", "KCI_E", "KCI_F", "KCI_G"]}
EXCERPT = {"chunk_id": "KCI_A__0001", "page_start": 2, "page_end": 2, "text": "대목"}


class TestPriorInput:
    def test_shape(self):
        inp = prior_input(question="노인의 우울과 사회적 지지에 관한 연구가 궁금해", topic=TOPIC,
                          research_question="가족 지지는 농촌 독거노인의 우울을 낮추는가?", group=GROUP,
                          books=BOOKS, excerpts={"KCI_A": EXCERPT}, corpus={"n_papers": 144748})

        assert inp["key"] == "prior.g1" and inp["kind"] == "prior"
        assert inp["question"] == "노인의 우울과 사회적 지지에 관한 연구가 궁금해"
        assert inp["topic"] == {"id": 12, "title": "농촌 독거노인의 사회적 지지와 우울"}
        assert inp["research_question"] == "가족 지지는 농촌 독거노인의 우울을 낮추는가?"
        assert inp["group"] == {"name": "가족 지지와 우울"} and inp["seeds"] == []
        # 묶음 7편 중 앞 6편, 번호는 E1 부터 차례로
        assert [(p["eid"], p["cnts_id"]) for p in inp["papers"]] == [
            ("E1", "KCI_A"), ("E2", "KCI_B"), ("E3", "KCI_C"), ("E4", "KCI_D"), ("E5", "KCI_E"), ("E6", "KCI_F")]
        first, second, fourth = inp["papers"][0], inp["papers"][1], inp["papers"][3]
        assert first["year"] == 2013 and first["excerpt"] == EXCERPT
        assert first["abstract"] == "가" * ABSTRACT_CHARS
        assert second == {"eid": "E2", "cnts_id": "KCI_B", "title": "사회적 지지 척도", "year": None,
                          "abstract": "", "excerpt": None}
        assert fourth["title"] == "KCI_D"                 # 서지가 없으면 cnts_id 를 제목 자리에
        assert inp["figures"] == [
            {"id": "F1", "label": "이 절에 준 논문 수", "value": "6"},
            {"id": "F2", "label": "발행 연도 범위", "value": "2013~2016"},
            {"id": "F3", "label": "소장 KCI 적재분 논문 수", "value": "144,748"},
        ]
        # 다시 맞춤 판정의 기준은 묶음의 논문 전부(넣지 못한 7번째 포함)
        assert inp["basis"] == {"topic_id": 12, "papers": GROUP["papers"]}

    def test_group_without_a_name_uses_its_hint(self):
        inp = prior_input(question="q", topic=TOPIC, research_question="rq", group={**GROUP, "name": ""},
                          books={}, excerpts={}, corpus=None)
        assert inp["group"] == {"name": "노인의 우울"}


class TestGapInput:
    def test_shape(self):
        seeds = [SEED, _seed("insufficient:1", None, 1, ["KCI_C", "KCI_A"])]

        inp = gap_input(question="q", topic=TOPIC, research_question="rq", seeds=seeds, books=BOOKS,
                        excerpts={}, corpus=None)

        assert inp["key"] == "gap" and inp["kind"] == "gap" and inp["group"] is None
        assert inp["seeds"] == [{"heading": "노인의 사회적 지지", "text": "농촌 노인 표본이 부족하다"},
                                {"heading": "노인의 사회적 지지", "text": "insufficient:1"}]
        # 씨앗에 묶인 근거 논문을 씨앗 순서로, 같은 논문은 한 번
        assert [p["cnts_id"] for p in inp["papers"]] == ["KCI_A", "KCI_B", "KCI_C"]
        assert inp["basis"] == {"topic_id": 12, "papers": ["KCI_A", "KCI_B", "KCI_C"]}
        assert [f["id"] for f in inp["figures"]] == ["F1", "F2"]
