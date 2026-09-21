import logging

from services.research.critic import (
    _EXCERPT_LEN, _MAX_LISTED, Verdict, format_evidence_list, parse_verdict, should_recheck,
)
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
        assert v.parse_failed is True

    def test_unknown_verdict_value_falls_back(self):
        v = parse_verdict('{"verdict": "maybe", "note": "n", "new_queries": []}')
        assert v.verdict == "sufficient"
        assert v.parse_failed is True

    def test_successful_parse_is_not_marked_failed(self):
        v = parse_verdict('{"verdict": "sufficient", "note": "n", "new_queries": []}')
        assert v.parse_failed is False

    def test_note_does_not_leak_model_output(self):
        """note 는 탐색 경로·진행 패널에 그대로 실린다 — 모델 원문을 담지 않는다."""
        v = parse_verdict("죄송합니다 판단할 수 없습니다")
        assert "죄송합니다" not in v.note

    def test_string_new_queries_does_not_become_characters(self):
        """문자열을 순회하면 "진" 한 글자로 재검색하는 쓰레기 쿼리가 된다."""
        raw = '{"verdict": "insufficient", "note": "n", "new_queries": "진로상담 앱 효과"}'
        assert parse_verdict(raw).new_queries == []

    def test_prose_after_json_does_not_break_parsing(self):
        """탐욕적 슬라이스는 뒤따르는 산문의 } 까지 먹어 파싱이 깨진다."""
        raw = '{"verdict": "sufficient", "note": "n", "new_queries": []} 참고: {예시}'
        assert parse_verdict(raw).verdict == "sufficient"

    def test_parse_failure_logs_raw_for_diagnosis(self, caplog):
        """로그가 자기점검이 꺼졌음을 아는 유일한 신호다 — 원문 없이는 프롬프트를 못 고친다."""
        with caplog.at_level(logging.WARNING):
            parse_verdict("죄송합니다 판단할 수 없습니다")
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings
        assert any("죄송합니다" in r.getMessage() for r in warnings)

    def test_unknown_verdict_logs_raw_for_diagnosis(self, caplog):
        with caplog.at_level(logging.WARNING):
            parse_verdict('{"verdict": "maybe", "note": "n", "new_queries": []}')
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings
        assert any("maybe" in r.getMessage() for r in warnings)


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
    def test_llm_verdicts_exact(self):
        """부분집합 단언은 VERDICTS 순서가 바뀌어 sufficient 가 빠져도 통과한다."""
        assert LLM_VERDICTS == ("sufficient", "insufficient")

    def test_llm_verdicts_excludes_pending(self):
        assert "pending" not in LLM_VERDICTS
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
        excerpt = format_evidence_list([e]).split(" — ", 1)[1]
        assert excerpt == "가" * _EXCERPT_LEN + "…"

    def test_short_excerpt_has_no_ellipsis(self):
        e = self._evidence("제목", "2020", "짧다")
        assert format_evidence_list([e]).endswith("짧다")

    def test_newlines_in_chunk_are_flattened(self):
        """표 청크에는 개행이 실재한다 — 그대로 쓰면 한 항목이 여러 줄로 퍼진다."""
        chunk_text = "[표]\n설명\n\n| a | b |\n| 1 | 2 |"
        e = self._evidence("제목", "2020", chunk_text)
        result = format_evidence_list([e])
        assert "\n" not in result
        assert result == "- 제목 (2020) — [표] 설명 | a | b | | 1 | 2 |"

    def test_list_is_capped_with_remainder_note(self):
        """상한이 없으면 재검색 누적분이 컨텍스트를 넘겨 system 지시가 잘려 나간다."""
        many = [self._evidence(f"제목{i}", "2020", "본문") for i in range(_MAX_LISTED + 5)]
        lines = format_evidence_list(many).splitlines()
        assert len(lines) == _MAX_LISTED + 1
        assert lines[-1] == "- …외 5편"

    def test_empty_meta_values_fall_back(self):
        """이 코드베이스는 빈 메타를 "" 로 표현한다 — get 의 기본값이 안 먹는다."""
        e = Evidence(id="E1", cnts_id="c", meta={"title": "", "pub_date": ""}, chunks=[])
        assert format_evidence_list([e]) == "- (제목 없음) (연도미상)"

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
