import pytest

from services.research.state import (
    DEFAULT_PARAMS, VERDICTS, Chunk, Evidence, ResearchState, SubQuestion, merge_params,
)


class TestMergeParams:
    def test_empty_override_gives_defaults(self):
        assert merge_params({}) == DEFAULT_PARAMS

    def test_none_override_gives_defaults(self):
        assert merge_params(None) == DEFAULT_PARAMS

    def test_override_wins(self):
        assert merge_params({"max_recheck": 1})["max_recheck"] == 1

    def test_override_does_not_drop_other_keys(self):
        merged = merge_params({"max_recheck": 1})
        assert merged["max_subquestions"] == DEFAULT_PARAMS["max_subquestions"]

    def test_unknown_key_is_rejected(self):
        # 오타로 조용히 무시되는 파라미터가 생기면 시연 직전에 값을 바꿔도 안 먹는다
        with pytest.raises(ValueError, match="알 수 없는 파라미터"):
            merge_params({"max_rechecks": 1})

    def test_defaults_are_not_mutated(self):
        merge_params({"max_recheck": 9})
        assert DEFAULT_PARAMS["max_recheck"] == 3

    def test_default_params_key_set_is_fixed(self):
        # Task 7·9 가 params["per_subq_top_k"] 로 직접 인덱싱한다 — 이름이
        # 바뀌면 merge_params 가 옛 이름을 거부하는 쪽으로 실패해야 한다.
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
        }

    def test_negative_citation_weight_is_rejected(self):
        with pytest.raises(ValueError, match="citation_weight"):
            merge_params({"citation_weight": -0.2})

    def test_citation_weight_above_one_is_rejected(self):
        with pytest.raises(ValueError, match="citation_weight"):
            merge_params({"citation_weight": 1.5})

    def test_citation_weight_bounds_are_inclusive(self):
        assert merge_params({"citation_weight": 0.0})["citation_weight"] == 0.0
        assert merge_params({"citation_weight": 1.0})["citation_weight"] == 1.0

    def test_string_value_for_int_param_is_rejected(self):
        # JSON 본문에서 흔한 실수 — 그대로 두면 should_recheck 의 비교에서 TypeError 로 터진다
        with pytest.raises(ValueError, match="max_recheck"):
            merge_params({"max_recheck": "3"})

    def test_bool_value_for_int_param_is_rejected(self):
        # bool 은 int 의 서브클래스라 isinstance(True, int) 가 True 다
        with pytest.raises(ValueError, match="max_recheck"):
            merge_params({"max_recheck": True})

    def test_bool_value_for_float_param_is_rejected(self):
        with pytest.raises(ValueError, match="citation_weight"):
            merge_params({"citation_weight": True})

    def test_zero_chunks_per_evidence_is_rejected(self):
        # 0 이면 청크 없는 근거가 만들어져 인용칩 호버가 빈 상태가 된다
        with pytest.raises(ValueError, match="chunks_per_evidence"):
            merge_params({"chunks_per_evidence": 0})

    def test_negative_max_recheck_is_rejected(self):
        with pytest.raises(ValueError, match="max_recheck"):
            merge_params({"max_recheck": -1})

    def test_per_subq_top_k_upper_bound_is_rejected(self):
        # 상한 없이 그대로 두면 Milvus AnnSearchRequest(limit=...) 까지 흘러가
        # 요청 하나로 워커를 묶는 자해 경로가 된다
        with pytest.raises(ValueError, match="per_subq_top_k"):
            merge_params({"per_subq_top_k": 1_000_000})


class TestState:
    def test_new_state_has_no_subquestions(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.subquestions == []
        assert st.evidence == {}
        assert st.recheck_count == 0

    def test_subquestion_defaults_to_pending(self):
        sq = SubQuestion(idx=0, text="하위질문")
        assert sq.verdict == "pending"
        assert sq.verdict in VERDICTS
        assert sq.queries == []
        assert sq.evidence_ids == []

    def test_evidence_holds_chunks(self):
        ev = Evidence(
            id="E1", cnts_id="KCI_FI000000001", meta={"title": "제목"},
            chunks=[Chunk(chunk_id="c1", text="본문", page_start=3, page_end=3, score=0.9)],
        )
        assert ev.chunks[0].page_start == 3

    def test_corpus_range_defaults_to_none(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.corpus_range is None
