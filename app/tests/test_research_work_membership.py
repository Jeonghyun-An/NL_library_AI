"""services/research_work/membership.py — 개념 소속·선행연구 묶음 배정.

순수 함수는 그대로 부른다. FastAPI 전용 concept_affinity 는 임베딩·Milvus 모듈을 대역으로 바꾼다 — 로컬 venv 에는
torch·FlagEmbedding·pymilvus 가 없다(test_search_research_path.py 와 같은 사정). pymilvus 가 없을 때만 MagicMock 과
예외 모듈을 꽂고, 임베딩·인덱서 모듈은 sys.modules 에 가짜를 꽂는다(함수 안 import 가 그것을 읽는다).
"""
import ast
import importlib
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from services.research_work.membership import (
    MEMBER_THRESHOLD, assign_groups, concept_affinity, cosine, group_count, members_from_affinity,
    ordered_papers, subq_affinity,
)
from services.research_work.shapes import MAX_GROUPS, PAPERS_PER_GROUP

MODULE = Path(__file__).resolve().parents[1] / "services" / "research_work" / "membership.py"


def _row(cnts_id, *, state="in", rank=None, position=None, origin="evidence", origin_ref=None):
    ref = origin_ref if origin_ref is not None else ({"rank": rank} if rank is not None else {})
    return SimpleNamespace(cnts_id=cnts_id, state=state, origin=origin, origin_ref=ref,
                           position=position)


class TestCosine:
    def test_values(self):
        assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
        assert cosine([1, 0], [0, 2]) == pytest.approx(0.0)
        assert cosine([1, 1], [-1, -1]) == pytest.approx(-1.0)
        assert cosine([3, 4], [6, 8]) == pytest.approx(1.0)

    def test_zero_vector_is_zero(self):
        assert cosine([0, 0], [1, 2]) == 0.0

    def test_numpy_float32_gives_a_python_float(self):
        out = cosine(np.array([1, 2], dtype=np.float32), [np.float32(2), np.float32(4)])
        assert type(out) is float and out == pytest.approx(1.0)


class TestGroupCount:
    def test_constants(self):
        assert (MEMBER_THRESHOLD, PAPERS_PER_GROUP, MAX_GROUPS) == (0.45, 4, 4)

    @pytest.mark.parametrize("n, k", [(0, 1), (1, 1), (5, 1), (7, 1), (8, 2), (12, 3), (16, 4), (40, 4)])
    def test_one_group_per_four_papers_between_one_and_four(self, n, k):
        assert group_count(n) == k


class TestOrderedPapers:
    def test_picked_rows_by_best_rank_then_position_then_id(self):
        rows = [
            _row("C5", rank={"0": 3}), _row("C4", rank={"0": 2, "1": 1}, position=9),
            _row("C3", rank={"1": 1}, position=1), _row("C2", state="candidate", rank={"0": 1}),
            _row("U1", origin="user"), _row("R1", origin="revived", origin_ref={"subq_idx": 0}),
            _row("C6", state="out", rank={"0": 1}),
        ]
        assert ordered_papers(rows) == ["C3", "C4", "C5", "R1", "U1"]


class TestSubqAffinity:
    def test_one_over_one_plus_rank_keyed_by_subquestion_text(self):
        rows = [_row("C1", rank={"0": 1, "1": 3}), _row("C2", rank={"1": 1}),
                _row("U1", origin="user"), _row("R1", origin="revived", origin_ref={"subq_idx": 0}),
                _row("C9", rank={"7": 1})]
        assert subq_affinity(rows, ["원인", "영향"]) == {
            "C1": {"원인": 0.5, "영향": 0.25}, "C2": {"영향": 0.5},
        }


class TestMembersFromAffinity:
    def test_threshold_is_inclusive_and_members_are_sorted(self):
        affinity = {"C1": {"우울": 0.45, "지지": 0.2}, "C2": {"우울": 0.8},
                    "C3": {"우울": 0.8, "지지": 0.6}, "C4": {"지지": 0.44}}
        assert members_from_affinity(affinity, ["우울", "지지", "노인"], 0.45) == {
            "우울": ["C2", "C3", "C1"], "지지": ["C3"], "노인": [],
        }


KEYS = ["A", "B", "C"]


class TestAssignGroups:
    def test_most_common_first_keys_become_groups(self):
        affinity = {
            "P1": {"A": 0.9, "B": 0.1}, "P2": {"A": 0.8}, "P3": {"B": 0.7, "A": 0.2},
            "P4": {"B": 0.9}, "P5": {"A": 0.6, "C": 0.1}, "P6": {"C": 0.9, "B": 0.5, "A": 0.4},
        }
        groups = assign_groups(["P1", "P2", "P3", "P4", "P5", "P6"], affinity, 2, keys=KEYS)
        # A 3편·B 2편·C 1편 → A·B 가 묶음이고, 1순위가 C 인 P6 은 A·B 중 친밀도가 높은 B 로
        assert groups == [
            {"key": "prior.g1", "hint": "A", "papers": ["P1", "P2", "P5"]},
            {"key": "prior.g2", "hint": "B", "papers": ["P3", "P4", "P6"]},
        ]

    def test_equal_counts_follow_the_paper_order(self):
        affinity = {"P1": {"B": 0.9}, "P2": {"A": 0.9}, "P3": {"A": 0.8}, "P4": {"B": 0.8}}
        groups = assign_groups(["P1", "P2", "P3", "P4"], affinity, 2, keys=KEYS)
        assert [(g["hint"], g["papers"]) for g in groups] == [("B", ["P1", "P4"]), ("A", ["P2", "P3"])]

    def test_group_count_is_capped_by_the_distinct_first_keys(self):
        affinity = {p: {"A": 0.9} for p in ("P1", "P2", "P3")} | {"P4": {"B": 0.9}}
        groups = assign_groups(["P1", "P2", "P3", "P4"], affinity, 4, keys=KEYS)
        assert [g["key"] for g in groups] == ["prior.g1", "prior.g2"]

    def test_papers_without_affinity_go_to_the_first_group(self):
        affinity = {"P1": {"B": 0.9}, "P3": {"A": 0.9}, "P4": {"B": 0.5}}
        groups = assign_groups(["P1", "P2", "P3", "P4"], affinity, 2, keys=KEYS)
        assert groups == [
            {"key": "prior.g1", "hint": "B", "papers": ["P1", "P2", "P4"]},
            {"key": "prior.g2", "hint": "A", "papers": ["P3"]},
        ]

    def test_no_affinity_at_all_is_one_group(self):
        assert assign_groups(["P1", "P2"], {}, 3, keys=KEYS) == [
            {"key": "prior.g1", "hint": "", "papers": ["P1", "P2"]}]

    def test_a_tie_within_a_paper_follows_the_keys_order(self):
        groups = assign_groups(["P1"], {"P1": {"B": 0.5, "A": 0.5}}, 1, keys=KEYS)
        assert groups[0]["hint"] == "A"

    def test_keys_outside_the_given_keys_are_ignored(self):
        groups = assign_groups(["P1", "P2"], {"P1": {"옛 개념": 0.9, "B": 0.1}, "P2": {"A": 0.3}}, 2,
                               keys=KEYS)
        assert [(g["hint"], g["papers"]) for g in groups] == [("B", ["P1"]), ("A", ["P2"])]

    def test_never_more_than_four_groups(self):
        keys = ["A", "B", "C", "D", "E"]
        affinity = {f"P{i}": {keys[i % 5]: 0.9} for i in range(20)}
        groups = assign_groups([f"P{i}" for i in range(20)], affinity, 9, keys=keys)
        assert len(groups) == MAX_GROUPS

    def test_every_paper_lands_in_exactly_one_group(self):
        papers = [f"P{i}" for i in range(13)]
        affinity = {p: {KEYS[i % 3]: 0.1 * (i % 7)} for i, p in enumerate(papers) if i % 4}
        groups = assign_groups(papers, affinity, group_count(len(papers)), keys=KEYS)
        placed = [p for g in groups for p in g["papers"]]
        assert sorted(placed) == sorted(papers) and len(placed) == len(set(placed))
        assert all(g["papers"] for g in groups)


# ── concept_affinity(FastAPI 전용) ───────────────────────────────────


class _MilvusException(Exception):
    """pymilvus 미설치 환경용 대역 — 진짜 pymilvus.exceptions.MilvusException 도 Exception 을 잇는다."""


class _Collection:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.calls: list[dict] = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.rows


class _Heavy:
    def __init__(self):
        self.texts: list[list[str]] = []
        self.dense: list[list[float]] = []
        self.embed_error: Exception | None = None
        self.collection = _Collection()
        self.milvus_exception = _MilvusException

    def embed_texts(self, texts, is_query=False):
        self.texts.append(list(texts))
        if self.embed_error is not None:
            raise self.embed_error
        return self.dense, [{} for _ in texts]


@pytest.fixture
def heavy(monkeypatch):
    fake = _Heavy()
    try:
        importlib.import_module("pymilvus.exceptions")
        fake.milvus_exception = importlib.import_module("pymilvus.exceptions").MilvusException
    except ModuleNotFoundError:
        exceptions = types.ModuleType("pymilvus.exceptions")
        exceptions.MilvusException = _MilvusException
        monkeypatch.setitem(sys.modules, "pymilvus", MagicMock())
        monkeypatch.setitem(sys.modules, "pymilvus.exceptions", exceptions)
    embedder = types.ModuleType("services.ingestion.embedder")
    embedder.embed_texts = fake.embed_texts
    indexer = types.ModuleType("services.ingestion.indexer")
    indexer.ensure_collection = lambda: fake.collection
    monkeypatch.setitem(sys.modules, "services.ingestion.embedder", embedder)
    monkeypatch.setitem(sys.modules, "services.ingestion.indexer", indexer)
    return fake


def _meta_row(cnts_id, vec):
    # Milvus 는 embedding 원소를 numpy.float32 로 준다 — JSON 직렬화가 안 되는 값이다
    return {"book_id": cnts_id, "embedding": [np.float32(x) for x in vec]}


class TestConceptAffinity:
    def test_cosine_between_concepts_and_meta_chunks(self, heavy):
        heavy.dense = [[1.0, 0.0], [0.0, 1.0]]
        heavy.collection.rows = [_meta_row("C2", [0.0, 3.0]), _meta_row("C1", [1.0, 1.0])]

        out = concept_affinity(["우울", "지지"], ["C1", "C2", "C3"])

        assert out == {"C1": {"우울": pytest.approx(0.7071, abs=1e-4), "지지": pytest.approx(0.7071, abs=1e-4)},
                       "C2": {"우울": pytest.approx(0.0), "지지": pytest.approx(1.0)}}
        assert json.loads(json.dumps(out)) == out          # numpy 값이 남지 않는다
        assert heavy.texts == [["우울", "지지"]]
        # ANN 검색이 아니라 메타청크 행을 그대로 꺼낸다
        assert heavy.collection.calls == [{
            "expr": 'book_id in ["C1", "C2", "C3"] && chunk_idx == -1',
            "output_fields": ["book_id", "embedding"], "limit": 3,
        }]

    def test_nothing_to_compare_is_empty_without_calling_the_models(self, heavy):
        assert concept_affinity([], ["C1"]) == {}
        assert concept_affinity(["우울"], []) == {}
        assert heavy.texts == [] and heavy.collection.calls == []

    def test_embedding_failure_is_none(self, heavy):
        heavy.embed_error = RuntimeError("CUDA out of memory")
        assert concept_affinity(["우울"], ["C1"]) is None

    def test_milvus_failure_is_none(self, heavy):
        heavy.dense = [[1.0, 0.0]]
        heavy.collection.error = heavy.milvus_exception("collection not loaded")
        assert concept_affinity(["우울"], ["C1"]) is None

    def test_a_code_defect_is_not_swallowed(self, heavy):
        heavy.dense = [[1.0, 0.0]]
        heavy.collection.rows = [{"book_id": "C1"}]          # embedding 이 빠진 행 — 코드 결함은 올린다
        with pytest.raises(KeyError):
            concept_affinity(["우울"], ["C1"])


class TestNoHeavyImportAtModuleLevel:
    def test_heavy_modules_are_imported_inside_the_function(self):
        # 최상단에서 끌면 이 파일의 순수 함수 테스트까지 torch 없이 돌지 못한다(함정 13)
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        top = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        names = [alias.name for node in top if isinstance(node, ast.Import) for alias in node.names]
        names += [node.module for node in top if isinstance(node, ast.ImportFrom)]
        heavy_prefixes = ("services.ingestion", "services.search", "pymilvus", "torch", "FlagEmbedding")
        assert not [n for n in names if n.startswith(heavy_prefixes)]
