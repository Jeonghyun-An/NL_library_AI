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

from bibliography_chunks import chunk as bibliography_chunk
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


class _RpcError(Exception):
    """grpc 미설치 환경용 대역 — 진짜 grpc.RpcError 도 Exception 을 잇는다."""


@pytest.fixture
def search(monkeypatch):
    """무거운 모듈을 대역으로 채우고 (indexer, reranker, MilvusException, RpcError) 를 준다. 끝나면 import 전 그대로
    되돌린다."""
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
    try:
        importlib.import_module("grpc")
    except ModuleNotFoundError:
        grpc = types.ModuleType("grpc")
        grpc.RpcError = _RpcError
        monkeypatch.setitem(sys.modules, "grpc", grpc)
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
        RpcError=sys.modules["grpc"].RpcError,
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

    def test_decimal_points_are_not_sentence_ends(self):
        # 소수점(3.14·p<.05·β=.32)에서 자르면 근거의 값이 바뀐다 — 바로 뒤가 공백인 마침표만 문장 끝이다
        text = "가" * 1120 + "다. 평균은 3.14점이었고 p<.05 로 유의하였" + "나" * 200
        assert clip(text) == "가" * 1120 + "다."
        # 창 안에 진짜 문장 끝이 없으면 소수점이 아니라 마지막 공백 앞에서 자른다('3.' 으로 끝나지 않는다)
        text = "가" * 1160 + " β=.32 평균은 3.14" + "나" * 200
        assert clip(text) == "가" * 1160 + " β=.32 평균은"

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

    def test_bibliography_chunks_are_not_passages(self):
        """옛 잡의 스냅숏에는 탐색이 거르기 전의 참고문헌 목록 조각이 있다 — 같은 점수여도 본문 대목만 후보로 남긴다
        (운영 d60a5dc1 E2: 참고문헌 __0071 과 본문 __0003 이 0.591 로 같았고 리랭커가 참고문헌을 골랐다)."""
        snapshot = {"evidence": {"E2": {"cnts_id": "KCI_FI002548462", "meta": {}, "chunks": [
            _snapshot_chunk("KCI_FI002548462__0071", 0.591), _snapshot_chunk("KCI_FI002548462__0003", 0.591)]}}}
        assert [p["chunk_id"] for p in snapshot_passages(snapshot, "KCI_FI002548462")] == ["KCI_FI002548462__0003"]

    def test_reference_tail_after_the_body_is_left_out(self):
        """본문 끝에 참고문헌 머리와 첫 항목이 붙은 청크는 본문이라 후보로 남되 머리 뒤를 뗀다 — 리랭커가 서지 속 제목으로
        점수를 매기지 않고, 대목이 남의 학위논문 제목으로 끝나지 않는다(운영 c816c7b2 이어가기 gap E3)."""
        snapshot = {"evidence": {"E4": {"cnts_id": "KCI_FI001407641", "meta": {}, "chunks": [
            _snapshot_chunk("KCI_FI001407641__0037", 0.8)]}}}
        (p,) = snapshot_passages(snapshot, "KCI_FI001407641")
        assert p["text"].endswith("실험연구를 수행할 필요를 느낀다.") and "고문희" not in p["text"]

    def test_a_paper_with_only_bibliography_chunks_gives_nothing(self):
        """빈 목록이라 _excerpts 의 `or milvus_passages(cnts)` 가 그 논문의 Milvus 청크에서 본문 대목을 고른다."""
        snapshot = {"evidence": {"E3": {"cnts_id": "KCI_FI001613573", "meta": {}, "chunks": [
            _snapshot_chunk("KCI_FI001613573__0041", 0.7)]}}}
        assert snapshot_passages(snapshot, "KCI_FI001613573") == []

    def test_falling_back_to_milvus_because_every_chunk_was_filtered_is_logged(self, caplog):
        """스냅숏 대목이 모두 걸려 Milvus 한 편 청크(최대 MAX_PASSAGES 개 리랭크)로 넘어가는 일은 요청 시간을 늘린다 —
        빈도를 운영 로그로 보게 info 한 줄을 남긴다. 스냅숏에 없던 논문(되살림·담기)은 원래 그 길이라 남기지 않는다."""
        snapshot = {"evidence": {"E3": {"cnts_id": "KCI_FI001613573", "meta": {}, "chunks": [
            _snapshot_chunk("KCI_FI001613573__0041", 0.7)]}}}
        with caplog.at_level("INFO", logger="services.research_work.passages"):
            snapshot_passages(snapshot, "KCI_FI001613573")
            snapshot_passages(snapshot, "KCI_Z")
        (record,) = caplog.records
        assert record.levelname == "INFO" and "KCI_FI001613573" in record.getMessage()


def _snapshot_chunk(chunk_id: str, score: float) -> dict:
    c = bibliography_chunk(chunk_id)
    return {"chunk_id": chunk_id, "text": c["text"], "page_start": c["page_start"], "page_end": c["page_end"],
            "score": score}


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
        # 상한은 정수 — pymilvus 는 timeout 이 int 일 때만 RPC 재시도 루프도 그 시간에서 끊는다(membership 과 같다)
        assert call["timeout"] == 10 and type(call["timeout"]) is int

    def test_bibliography_chunks_are_left_out(self, search, monkeypatch):
        """Milvus 로 넘어온 논문도 같은 규칙 — 참고문헌 목록 조각은 리랭커 후보에 넣지 않는다."""
        bib, body = bibliography_chunk("KCI_FI002548462__0071"), bibliography_chunk("KCI_FI002548462__0003")
        col = _Collection(rows=[
            {"chunk_id": "KCI_FI002548462__0071", "chunk_idx": 71, "text": bib["text"], "page_start": 33,
             "page_end": 33},
            {"chunk_id": "KCI_FI002548462__0003", "chunk_idx": 3, "text": body["text"], "page_start": 1,
             "page_end": 1},
        ])
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: col)
        assert [p["chunk_id"] for p in passages.milvus_passages("KCI_FI002548462")] == ["KCI_FI002548462__0003"]

    def test_reference_tail_after_the_body_is_left_out(self, search, monkeypatch):
        tail = bibliography_chunk("KCI_FI001061014__0022")
        col = _Collection(rows=[{"chunk_id": "KCI_FI001061014__0022", "chunk_idx": 22, "text": tail["text"],
                                 "page_start": 12, "page_end": 12}])
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: col)
        (p,) = passages.milvus_passages("KCI_FI001061014")
        assert p["text"].endswith("연구의 필요성을 시사한다.") and "강희숙" not in p["text"]

    @pytest.mark.parametrize("error", [RuntimeError("스키마 불일치"), OSError("연결 끊김")])
    def test_known_failures_give_no_passages(self, search, monkeypatch, error):
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: _Collection(error=error))
        assert passages.milvus_passages("KCI_A") == []

    def test_milvus_exception_gives_no_passages(self, search, monkeypatch):
        error = search.MilvusException(message="milvus down")
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: _Collection(error=error))
        assert passages.milvus_passages("KCI_A") == []

    def test_milvus_deadline_gives_no_passages(self, search, monkeypatch):
        # 기한을 넘기면(DEADLINE_EXCEEDED 등 IGNORE_RETRY_CODES) pymilvus 는 MilvusException 이 아니라 날
        # grpc.RpcError 를 다시 던진다 — 절 쓰기가 500 이 아니라 그 논문만 대목 없이 간다
        error = search.RpcError("Deadline Exceeded")
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: _Collection(error=error))
        assert passages.milvus_passages("KCI_A") == []

    def test_missing_grpc_module_gives_no_passages(self, search, monkeypatch):
        # membership.concept_affinity 와 같다 — grpc(또는 pymilvus)를 불러오지 못하면 500 이 아니라 그 논문만
        # 대목 없이 간다. sys.modules 의 None 은 import 를 ModuleNotFoundError(ImportError) 로 막는다
        col = _Collection()
        monkeypatch.setattr(search.indexer, "ensure_collection", lambda: col)
        monkeypatch.setitem(sys.modules, "grpc", None)
        assert passages.milvus_passages("KCI_A") == []
        assert col.calls == []

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

    def test_candidate_count_and_time_are_logged(self, search, monkeypatch, caplog):
        # [이 절 쓰기]는 게이트웨이 120초 안의 동기 요청이다 — 리랭크 후보 수·걸린 시간을 운영 로그로 잰다
        monkeypatch.setattr(search.reranker, "compute_scores", lambda query, documents: [0.2, 0.3, 0.8])
        with caplog.at_level("INFO", logger="services.research_work.passages"):
            passages.pick_excerpt("질의", CANDIDATES)
        (record,) = caplog.records
        assert record.levelname == "INFO" and "후보 3개" in record.getMessage()

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
    def test_count_and_year_range(self):
        assert section_figures([2015, 2008, 2011], 6) == [
            {"id": "F1", "label": "이 절에 준 논문 수", "value": "6"},
            {"id": "F2", "label": "발행 연도 범위", "value": "2008~2015"},
        ]

    def test_one_year_is_that_year(self):
        assert section_figures([2013, 2013], 2)[1] == {"id": "F2", "label": "발행 연도 범위", "value": "2013"}

    def test_missing_parts_are_left_out(self):
        assert section_figures([], 3) == [{"id": "F1", "label": "이 절에 준 논문 수", "value": "3"}]


SEED = {"key": "future:1:0", "kind": "future", "section_idx": 1, "subq_idx": 1, "heading": "노인의 사회적 지지",
        "text": "농촌 노인 표본이 부족하다", "papers": ["KCI_A", "KCI_B"], "adopted": 9}


def _seed(key: str, section_idx: int | None, subq_idx: int | None, papers: list[str]) -> dict:
    return {**SEED, "key": key, "section_idx": section_idx, "subq_idx": subq_idx, "text": key, "papers": papers}


# 운영 630e0d65(2026-10-14) 보고서의 꼴 — 고른 카드(59, '…변인들의 관계')의 씨앗 future:1:0 이 들어 있던 절의 하위질문은
# '시간적 변화 추이'다. 같은 절에 주제와 무관한 향후 과제(future:1:1 교육 프로그램)와 그 하위질문의 insufficient note
# ('제시된 근거들은 …')가 함께 있어, 연구 공백 절이 이 이웃을 끌어와 고른 주제가 아닌 '시간적 변화 추이' 공백을 썼다
_LIVE_GAP_HEADINGS = ["개념은 어떻게 제시되어 왔는가?", "연구의 시간적 변화 추이는 어떠한가?"]
LIVE_GAP_REPORT = {
    "sections": [
        {"heading": _LIVE_GAP_HEADINGS[0],
         "papers": [{"cnts_id": "K1", "evidence": ["E1"]}, {"cnts_id": "K2", "evidence": ["E2"]}],
         "future": [{"text": "언어 능력을 보여줄 객관적인 자료 조사가 필요하다 [E2].", "evidence": ["E2"]}]},
        {"heading": _LIVE_GAP_HEADINGS[1],
         "papers": [{"cnts_id": "K3", "evidence": ["E3"]}, {"cnts_id": "K4", "evidence": ["E4"]}],
         "future": [{"text": "언어 발달에 영향을 미치는 다양한 변인들에 대한 추가적인 연구가 필요하다 [E4].",
                     "evidence": ["E4"]},
                    {"text": "효과적인 교육 프로그램 개발에 대한 연구가 이루어져야 한다 [E3].", "evidence": ["E3"]}]},
    ],
    "evidence": {f"E{n}": {"cnts_id": f"K{n}", "meta": {"title": f"논문 {n}"}} for n in range(1, 5)},
    "trail": [
        {"subquestion": _LIVE_GAP_HEADINGS[0], "verdict": "sufficient", "note": "충분하다"},
        {"subquestion": _LIVE_GAP_HEADINGS[1], "verdict": "insufficient",
         "note": "제시된 근거들은 연구 현황을 다루고 있지만, 시간적 변화 추이를 종합적으로 보여주지는 못합니다."},
    ],
}


class TestGapSeeds:
    def test_a_picked_card_uses_only_its_own_seed_with_its_original_evidence(self, monkeypatch):
        """고른 카드의 주제는 씨앗의 글에서 나온다 — 씨앗이 들어 있던 절의 이웃(다른 향후 과제·하위질문 note)은 잇지 않는다.
        보고서가 그 향후 과제에 달았던 근거(cnts_id)를 evidence 로 붙인다. 넘기는 논문은 씨앗의 papers 그대로다."""
        calls = []

        def _pick(report, *, limit, exclude=()):
            calls.append(limit)
            return []

        monkeypatch.setattr(section_input, "pick_seeds", _pick)
        report = {"sections": [{"heading": "다른 절", "future": []},
                               {"heading": "노인의 사회적 지지",
                                "future": [{"text": "농촌 노인 표본이 부족하다 [E2]", "evidence": ["E2", "E9"]}]}],
                  "evidence": {"E2": {"cnts_id": "KCI_B", "meta": {"title": "사회적 지지 척도"}}}}

        out = gap_seeds(SEED, report)

        assert out == [{**SEED, "evidence": ["KCI_B"]}]
        assert calls == []                                  # 보고서에서 씨앗을 더 고르지 않는다
        assert "evidence" not in SEED                       # 저장된 카드 씨앗을 고치지 않는다

    def test_live_report_does_not_pull_in_the_neighbours_of_the_picked_seed(self):
        # 운영 630e0d65 카드 59 — 고치기 전에는 [future:1:0, future:1:1, insufficient:1] 이었다
        from services.research_work.seeds import pick_seeds as real_pick_seeds
        picked = next(s for s in real_pick_seeds(LIVE_GAP_REPORT, limit=None) if s["key"] == "future:1:0")

        out = gap_seeds(picked, LIVE_GAP_REPORT)

        assert [s["key"] for s in out] == ["future:1:0"]
        assert out[0]["evidence"] == ["K4"] and out[0]["papers"] == picked["papers"]

    def test_user_card_takes_three_seeds_from_the_whole_report(self, monkeypatch):
        calls = []

        def _pick(report, *, limit, exclude=()):
            calls.append(limit)
            return [_seed(f"future:{i}:0", i, i, ["X"]) for i in range(limit)]

        monkeypatch.setattr(section_input, "pick_seeds", _pick)

        out = gap_seeds({}, {"sections": []})
        assert [s["key"] for s in out] == ["future:0:0", "future:1:0", "future:2:0"]
        assert [s["evidence"] for s in out] == [[], [], []]
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
        figures = section_figures([2013], 2)
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
                          books=BOOKS, excerpts={"KCI_A": EXCERPT})

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
        # 수치는 근거 논문의 편수·연도뿐이다 — 소장 KCI 적재분은 절에 주지 않는다(프롬프트가 [F#] 를 근거 논문의 편수·
        # 연도에만 쓰라고 한다. 운영 2026-10-14 prior.g2 는 적재분 '198,518' 을 '…건에 달한다' 로 옮겼다)
        assert inp["figures"] == [
            {"id": "F1", "label": "이 절에 준 논문 수", "value": "6"},
            {"id": "F2", "label": "발행 연도 범위", "value": "2013~2016"},
        ]
        # 다시 맞춤 판정의 기준은 묶음의 논문 전부(넣지 못한 7번째 포함)와 이 절을 쓸 때의 연구 질문(06e)
        assert inp["basis"] == {"topic_id": 12, "papers": GROUP["papers"],
                                "question": "가족 지지는 농촌 독거노인의 우울을 낮추는가?"}

    def test_group_without_a_name_uses_its_hint(self):
        inp = prior_input(question="q", topic=TOPIC, research_question="rq", group={**GROUP, "name": ""},
                          books={}, excerpts={})
        assert inp["group"] == {"name": "노인의 우울"}


class TestGapInput:
    def test_shape(self):
        seeds = [SEED, _seed("insufficient:1", None, 1, ["KCI_C", "KCI_A"])]

        inp = gap_input(question="q", topic=TOPIC, research_question="rq", seeds=seeds, books=BOOKS,
                        excerpts={})

        assert inp["key"] == "gap" and inp["kind"] == "gap" and inp["group"] is None
        assert inp["seeds"] == [{"heading": "노인의 사회적 지지", "text": "농촌 노인 표본이 부족하다"},
                                {"heading": "노인의 사회적 지지", "text": "insufficient:1"}]
        # 씨앗에 묶인 근거 논문을 씨앗 순서로, 같은 논문은 한 번
        assert [p["cnts_id"] for p in inp["papers"]] == ["KCI_A", "KCI_B", "KCI_C"]
        assert inp["basis"] == {"topic_id": 12, "papers": ["KCI_A", "KCI_B", "KCI_C"], "question": "rq"}
        assert [f["id"] for f in inp["figures"]] == ["F1", "F2"]

    def test_an_insufficient_seed_is_written_as_an_unanswered_subquestion_not_the_critic_note(self):
        """insufficient 씨앗의 글은 critic 의 자기점검 메모('제시된 근거들은 …부족합니다')다. 그대로 넘기면 모델이 그 말투를
        옮긴다(운영 630e0d65 gap p3 '제시된 근거들은 … 보여주지는 못한다'). 하위질문에 답할 근거가 확인되지 않았다는 한 줄로 쓴다."""
        note = "제시된 근거들은 연구 현황을 다루고 있지만, 시간적 변화 추이를 종합적으로 보여주지는 못합니다. 제공된 근거는 부족합니다."
        seed = {**SEED, "key": "insufficient:1", "kind": "insufficient", "heading": "연구의 시간적 변화 추이는 어떠한가?",
                "text": note, "evidence": []}

        inp = gap_input(question="q", topic=TOPIC, research_question="rq", seeds=[seed], books=BOOKS, excerpts={})

        (line,) = inp["seeds"]
        assert line == {"heading": "연구의 시간적 변화 추이는 어떠한가?",
                        "text": "'연구의 시간적 변화 추이는 어떠한가?'에 답할 근거가 소장 코퍼스에서 충분히 확인되지 않았다."}
        assert not any(w in line["text"] for w in ("제시된 근거", "제공된 근거", "합니다"))

    def test_a_future_seed_carries_the_number_of_its_original_evidence_in_this_section(self):
        """보고서가 그 향후 과제에 달았던 근거가 이 절의 논문에 있으면 씨앗 줄에 그 [E#] 를 붙인다 — 모델이 씨앗 문장을
        옮겨도 근거 표시가 남는다(운영 630e0d65 gap p1 은 씨앗 문장을 옮긴 근거 없는 문장이었다). 없으면 붙이지 않는다."""
        seed = {**SEED, "text": "농촌 노인 표본이 부족하다.", "evidence": ["KCI_B", "KCI_Z"]}

        inp = gap_input(question="q", topic=TOPIC, research_question="rq", seeds=[seed], books=BOOKS, excerpts={})

        assert [p["cnts_id"] for p in inp["papers"]] == ["KCI_A", "KCI_B"]
        assert inp["seeds"] == [{"heading": "노인의 사회적 지지", "text": "농촌 노인 표본이 부족하다 [E2]."}]

        outside = {**seed, "evidence": ["KCI_Z"]}
        inp = gap_input(question="q", topic=TOPIC, research_question="rq", seeds=[outside], books=BOOKS, excerpts={})
        assert inp["seeds"] == [{"heading": "노인의 사회적 지지", "text": "농촌 노인 표본이 부족하다."}]

    def test_a_seed_line_without_a_sentence_end_takes_the_marks_at_its_end(self):
        seed = {**SEED, "evidence": ["KCI_A", "KCI_B", "KCI_A"]}
        inp = gap_input(question="q", topic=TOPIC, research_question="rq", seeds=[seed], books=BOOKS, excerpts={})
        assert inp["seeds"][0]["text"] == "농촌 노인 표본이 부족하다 [E1] [E2]"
