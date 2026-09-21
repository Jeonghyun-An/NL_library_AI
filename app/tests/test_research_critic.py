from services.research.critic import Verdict, parse_verdict, should_recheck
from services.research.state import LLM_VERDICTS, VERDICTS, SubQuestion


class TestParseVerdict:
    def test_sufficient(self):
        raw = '{"verdict": "sufficient", "note": "근거 충분", "new_queries": []}'
        v = parse_verdict(raw)
        assert v.verdict == "sufficient"
        assert v.new_queries == []

    def test_insufficient_with_queries(self):
        raw = ('{"verdict": "insufficient", "note": "3편뿐이다", '
               '"new_queries": ["진로상담 앱 효과", "온라인 진로지도 성과"]}')
        v = parse_verdict(raw)
        assert v.verdict == "insufficient"
        assert v.note == "3편뿐이다"
        assert len(v.new_queries) == 2

    def test_json_in_code_fence(self):
        raw = '```json\n{"verdict": "sufficient", "note": "n", "new_queries": []}\n```'
        assert parse_verdict(raw).verdict == "sufficient"

    def test_garbage_falls_back_to_sufficient(self):
        """판정을 못 읽으면 무한 재검색 대신 멈춘다 — 실패가 루프가 되면 안 된다."""
        v = parse_verdict("죄송합니다 판단할 수 없습니다")
        assert v.verdict == "sufficient"
        assert "판정 해석 실패" in v.note

    def test_unknown_verdict_value_falls_back(self):
        v = parse_verdict('{"verdict": "maybe", "note": "n", "new_queries": []}')
        assert v.verdict == "sufficient"


class TestShouldRecheck:
    def _sq(self, verdict):
        return SubQuestion(idx=0, text="q", verdict=verdict)

    def test_insufficient_under_limit(self):
        assert should_recheck(self._sq("insufficient"), recheck_count=0, max_recheck=3)

    def test_at_limit_stops(self):
        assert not should_recheck(self._sq("insufficient"), recheck_count=3, max_recheck=3)

    def test_sufficient_stops(self):
        assert not should_recheck(self._sq("sufficient"), recheck_count=0, max_recheck=3)

    def test_always_insufficient_critic_still_terminates(self):
        """항상 부족을 반환하는 critic 을 물려도 멈춘다."""
        sq = self._sq("insufficient")
        count = 0
        while should_recheck(sq, recheck_count=count, max_recheck=3):
            count += 1
            assert count <= 3
        assert count == 3


class TestLlmVerdicts:
    def test_llm_verdicts_is_subset_of_verdicts(self):
        assert set(LLM_VERDICTS) <= set(VERDICTS)
