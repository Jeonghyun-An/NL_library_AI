import logging

from services.research.critic import Verdict, format_evidence_list, parse_verdict, should_recheck
from services.research.state import Chunk, Evidence, LLM_VERDICTS, SubQuestion, VERDICTS


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

    def test_parse_failure_is_logged(self, caplog):
        with caplog.at_level(logging.WARNING, logger="services.research.critic"):
            parse_verdict("죄송합니다 판단할 수 없습니다")
        assert any("판정 JSON 파싱 실패" in r.message for r in caplog.records)

    def test_unknown_verdict_value_is_logged(self, caplog):
        with caplog.at_level(logging.WARNING, logger="services.research.critic"):
            parse_verdict('{"verdict": "maybe", "note": "n", "new_queries": []}')
        assert any("알 수 없는 verdict" in r.message for r in caplog.records)


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


class TestFormatEvidenceList:
    def _evidence(self, title, year, chunk_text=None):
        chunks = []
        if chunk_text is not None:
            chunks.append(Chunk(chunk_id="c1", text=chunk_text, page_start=1, page_end=1, score=0.9))
        return Evidence(id="E1", cnts_id="cnts1", meta={"title": title, "pub_date": year}, chunks=chunks)

    def test_includes_excerpt_from_first_chunk(self):
        e = self._evidence("제목", "2020", "본문 발췌 내용")
        result = format_evidence_list([e])
        assert result == "- 제목 (2020) — 본문 발췌 내용"

    def test_excerpt_truncated(self):
        e = self._evidence("제목", "2020", "가" * 500)
        result = format_evidence_list([e])
        excerpt = result.split(" — ", 1)[1]
        assert len(excerpt) == 200

    def test_evidence_without_chunks_falls_back_to_title_year(self):
        e = self._evidence("제목", "2020")
        assert format_evidence_list([e]) == "- 제목 (2020)"

    def test_mixed_evidence_does_not_crash(self):
        with_chunk = self._evidence("A", "2020", "본문")
        without_chunk = self._evidence("B", "2021")
        result = format_evidence_list([with_chunk, without_chunk])
        lines = result.splitlines()
        assert lines == ["- A (2020) — 본문", "- B (2021)"]

    def test_empty_list_gives_placeholder(self):
        assert format_evidence_list([]) == "(없음)"
