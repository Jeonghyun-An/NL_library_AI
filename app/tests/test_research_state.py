from dataclasses import fields

import pytest

from services.research.state import (
    _PARAM_BOUNDS, DEFAULT_PARAMS, VERDICTS, Chunk, Evidence, ResearchState, SubQuestion,
    merge_params, restore_state, snapshot_state,
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
        # 탐색·오케스트레이션이 params["per_subq_top_k"] 로 직접 인덱싱한다 — 이름이
        # 바뀌면 merge_params 가 옛 이름을 거부하는 쪽으로 실패해야 한다.
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
        }

    def test_bounds_cover_exactly_the_default_keys(self):
        # 키를 DEFAULT_PARAMS 에만 넣으면 _PARAM_BOUNDS[key] 가 KeyError 로 터지고,
        # API 는 ValueError 만 422 로 바꾸므로 500 이 된다
        assert set(_PARAM_BOUNDS) == set(DEFAULT_PARAMS)

    def test_defaults_are_within_bounds(self):
        assert merge_params(dict(DEFAULT_PARAMS)) == DEFAULT_PARAMS

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_citation_weight_is_rejected(self, value):
        # NaN 은 범위 비교가 전부 False 라 통과해버리고, JSONB 가 NaN 토큰을
        # 거부해 422 가 아니라 커밋 단계 500 이 된다
        with pytest.raises(ValueError, match="citation_weight"):
            merge_params({"citation_weight": value})

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


def _explored_state() -> ResearchState:
    st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
    st.corpus_range = {"from": "2002", "to": "2026", "n_papers": 72054}
    st.subquestions = [
        SubQuestion(idx=0, text="하위1", queries=["q1", "q2"], evidence_ids=["E0"],
                    verdict="sufficient", note="충분하다", capped=3,
                    evidence_chunks={"E0": ["c1"]}, chunk_scores={"c1": 0.91}),
        SubQuestion(idx=1, text="하위2", queries=["q3"], verdict="insufficient",
                    parse_failed=True, note="판정을 못 읽었다"),
        SubQuestion(idx=2, text="하위3", failed=True),
    ]
    st.evidence = {
        "E0": Evidence(id="E0", cnts_id="KCI_A", meta={"title": "논문 가", "pub_date": "2008-06"},
                       chunks=[Chunk(chunk_id="c1", text="본문", page_start=3,
                                     page_end=4, score=0.87)]),
    }
    return st


class TestSnapshotRoundTrip:
    """종합만 재실행하는 재개의 전제 — 스냅샷이 원래 상태와 같아야 한다.

    parse_failed·failed 가 왕복에서 떨어지면 재개한 잡의 한계 섹션이 조용히
    비고, 보고서가 "한계 없음"으로 보인다. 필드를 추가할 때마다 반복된 실수다.
    """

    def test_question_and_params_survive(self):
        st = _explored_state()
        back = restore_state("j1", snapshot_state(st))
        assert back.question == st.question
        assert back.params == st.params

    def test_corpus_range_survives(self):
        # 보고서의 "수록 범위" 문구가 여기서 온다 — 떨어지면 재개한 보고서만 비어 보인다
        back = restore_state("j1", snapshot_state(_explored_state()))
        assert back.corpus_range == {"from": "2002", "to": "2026", "n_papers": 72054}

    def test_subquestions_survive_in_order(self):
        st = _explored_state()
        back = restore_state("j1", snapshot_state(st))
        assert [s.idx for s in back.subquestions] == [0, 1, 2]
        assert [s.text for s in back.subquestions] == ["하위1", "하위2", "하위3"]
        assert [s.queries for s in back.subquestions] == [["q1", "q2"], ["q3"], []]
        assert [s.evidence_ids for s in back.subquestions] == [["E0"], [], []]
        assert [s.verdict for s in back.subquestions] == [
            "sufficient", "insufficient", "pending"]
        assert [s.note for s in back.subquestions] == [
            "충분하다", "판정을 못 읽었다", ""]

    def test_parse_failed_survives(self):
        back = restore_state("j1", snapshot_state(_explored_state()))
        assert [s.parse_failed for s in back.subquestions] == [False, True, False]

    def test_failed_survives(self):
        back = restore_state("j1", snapshot_state(_explored_state()))
        assert [s.failed for s in back.subquestions] == [False, False, True]

    def test_evidence_survives(self):
        back = restore_state("j1", snapshot_state(_explored_state()))
        ev = back.evidence["E0"]
        assert ev.id == "E0"
        assert ev.cnts_id == "KCI_A"
        assert ev.meta == {"title": "논문 가", "pub_date": "2008-06"}
        assert [(c.chunk_id, c.text, c.page_start, c.page_end, c.score) for c in ev.chunks] == [
            ("c1", "본문", 3, 4, 0.87)
        ]

    def test_snapshot_is_json_serializable(self):
        # JSONB 컬럼에 들어간다 — dataclass 가 섞여 있으면 커밋에서야 터진다
        import json

        json.dumps(snapshot_state(_explored_state()), ensure_ascii=False)

    def test_round_trip_is_stable(self):
        # 한 번 더 돌려도 같아야 한다 — 복원이 정보를 잃으면 여기서 갈린다
        snap = snapshot_state(_explored_state())
        assert snapshot_state(restore_state("j1", snap)) == snap

    def test_capped_and_evidence_chunks_survive(self):
        back = restore_state("j1", snapshot_state(_explored_state()))
        assert [s.capped for s in back.subquestions] == [3, 0, 0]
        assert back.subquestions[0].evidence_chunks == {"E0": ["c1"]}

    def test_chunk_scores_survive(self):
        # 떨어지면 재개한 잡의 절 호버가 다른 하위질문이 준 점수를 띄운다
        back = restore_state("j1", snapshot_state(_explored_state()))
        assert back.subquestions[0].chunk_scores == {"c1": 0.91}

    def test_snapshot_carries_every_dataclass_field(self):
        """필드를 추가하고 스냅샷에 빠뜨리면 재개한 잡에서만 조용히 기본값이 된다.

        양쪽을 같이 빠뜨리면 왕복 안정성 테스트는 통과하므로 키 집합을 직접 단언한다.
        """
        snap = snapshot_state(_explored_state())
        assert set(snap["subquestions"][0]) == {f.name for f in fields(SubQuestion)}
        assert set(snap["evidence"]["E0"]["chunks"][0]) == {f.name for f in fields(Chunk)}


class TestSnapshotEvolution:
    """배포 사이에 스키마가 바뀌어도 옛 스냅샷으로 종합만 재개할 수 있어야 한다."""

    def test_unknown_subquestion_key_is_ignored(self):
        snap = snapshot_state(_explored_state())
        snap["subquestions"][0]["removed_field"] = True
        back = restore_state("j1", snap)
        assert back.subquestions[0].text == "하위1"

    def test_missing_subquestion_key_gets_default(self):
        snap = snapshot_state(_explored_state())
        for sq in snap["subquestions"]:
            del sq["capped"]
            del sq["evidence_chunks"]
            del sq["chunk_scores"]
        back = restore_state("j1", snap)
        assert [s.capped for s in back.subquestions] == [0, 0, 0]
        assert back.subquestions[0].evidence_chunks == {}
        assert back.subquestions[0].chunk_scores == {}

    def test_unknown_chunk_key_is_ignored(self):
        snap = snapshot_state(_explored_state())
        snap["evidence"]["E0"]["chunks"][0]["old_field"] = 1
        assert restore_state("j1", snap).evidence["E0"].chunks[0].chunk_id == "c1"

    def test_params_are_refilled_with_defaults(self):
        """나중에 추가된 파라미터를 옛 스냅샷이 모르면 읽는 쪽이 KeyError 로 터진다."""
        snap = snapshot_state(_explored_state())
        del snap["params"]["min_evidence_per_subq"]
        snap["params"]["retired_param"] = 1
        back = restore_state("j1", snap)
        assert back.params == DEFAULT_PARAMS
