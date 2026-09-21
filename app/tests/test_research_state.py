import pytest

from services.research.state import (
    DEFAULT_PARAMS, Chunk, Evidence, ResearchState, SubQuestion, merge_params,
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
        merge_params({"max_recheck": 99})
        assert DEFAULT_PARAMS["max_recheck"] == 3


class TestState:
    def test_new_state_has_no_subquestions(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.subquestions == []
        assert st.evidence == {}
        assert st.recheck_count == 0

    def test_subquestion_defaults_to_pending(self):
        sq = SubQuestion(idx=0, text="하위질문")
        assert sq.verdict == "pending"
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
