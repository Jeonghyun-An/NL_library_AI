import asyncio
import json
import logging

import httpx

from services.research import critic
from services.research.critic import (
    _EXCERPT_LEN, _MAX_LISTED, _PARSE_FAILED_NOTE, Verdict, format_evidence_list,
    parse_verdict, should_recheck,
)
from services.research.state import (
    Chunk, Evidence, LLM_VERDICTS, SubQuestion, VERDICTS, merge_params,
)


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


class TestOffTopic:
    """무관 근거 번호 — 잘못 읽은 번호로 관련 있는 근거를 지우면 안 된다."""

    def _parse(self, off_topic, *, listed=5, verdict="insufficient"):
        raw = json.dumps({"verdict": verdict, "note": "n", "new_queries": [],
                          "off_topic": off_topic}, ensure_ascii=False)
        return parse_verdict(raw, listed=listed)

    def test_integer_numbers_are_read(self):
        assert self._parse([2, 4]).off_topic == [2, 4]

    def test_numeric_strings_are_read(self):
        assert self._parse(["3", " 1 "]).off_topic == [3, 1]

    def test_numbers_outside_the_list_are_dropped(self):
        assert self._parse([0, 1, 5, 6, -2], listed=5).off_topic == [1, 5]

    def test_duplicates_are_dropped(self):
        assert self._parse([2, "2", 2]).off_topic == [2]

    def test_non_numbers_are_dropped(self):
        # true 는 int 의 서브클래스라 그냥 두면 1번으로 읽힌다
        assert self._parse([1.0, "둘", None, True, {"n": 3}, "3"]).off_topic == [3]

    def test_non_list_gives_empty(self):
        assert self._parse("2, 3").off_topic == []
        assert self._parse(2).off_topic == []

    def test_missing_key_gives_empty(self):
        v = parse_verdict('{"verdict": "sufficient", "note": "n", "new_queries": []}', listed=5)
        assert v.off_topic == []

    def test_sufficient_verdict_may_still_name_off_topic(self):
        assert self._parse([1], verdict="sufficient").off_topic == [1]

    def test_unreadable_verdict_excludes_nothing(self):
        """판정을 못 읽었는데 근거를 지우면 안 된다."""
        raw = '{"verdict": "maybe", "note": "n", "new_queries": [], "off_topic": [1, 2]}'
        v = parse_verdict(raw, listed=5)
        assert v.parse_failed is True
        assert v.off_topic == []


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
        assert result == "[1] 제목 (2020) — 본문 발췌 내용"

    def test_items_are_numbered_from_one_in_given_order(self):
        """critic 은 이 번호로 무관한 근거를 가리키고, runner 는 넘긴 순서로 id 에 되돌린다."""
        evs = [self._evidence(f"제목{i}", "2020") for i in range(3)]
        assert format_evidence_list(evs).splitlines() == [
            "[1] 제목0 (2020)", "[2] 제목1 (2020)", "[3] 제목2 (2020)"]

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
        assert result == "[1] 제목 (2020) — [표] 설명 | a | b | | 1 | 2 |"

    def test_list_is_capped_with_remainder_note(self):
        """상한이 없으면 재검색 누적분이 컨텍스트를 넘겨 system 지시가 잘려 나간다."""
        many = [self._evidence(f"제목{i}", "2020", "본문") for i in range(_MAX_LISTED + 5)]
        lines = format_evidence_list(many).splitlines()
        assert len(lines) == _MAX_LISTED + 1
        assert lines[_MAX_LISTED - 1].startswith(f"[{_MAX_LISTED}] ")
        # 잘린 나머지에는 번호가 없다 — 발췌를 보지 못한 근거를 무관하다고 가리키게 두지 않는다
        assert lines[-1] == "…외 5편"

    def test_empty_meta_values_fall_back(self):
        """이 코드베이스는 빈 메타를 "" 로 표현한다 — get 의 기본값이 안 먹는다."""
        e = Evidence(id="E1", cnts_id="c", meta={"title": "", "pub_date": ""}, chunks=[])
        assert format_evidence_list([e]) == "[1] (제목 없음) (연도미상)"

    def test_evidence_without_chunks_falls_back_to_title_year(self):
        e = self._evidence("제목", "2020")
        assert format_evidence_list([e]) == "[1] 제목 (2020)"

    def test_mixed_evidence_does_not_crash(self):
        with_chunk = self._evidence("A", "2020", "본문")
        without_chunk = self._evidence("B", "2021")
        result = format_evidence_list([with_chunk, without_chunk])
        lines = result.splitlines()
        assert lines == ["[1] A (2020) — 본문", "[2] B (2021)"]

    def test_empty_list_gives_placeholder(self):
        assert format_evidence_list([]) == "(없음)"


class TestCritique:
    """critique() 는 외부 LLM(chat)만 대역으로 바꾸고 실제 템플릿을 거친다.

    critic 을 통째로 대역으로 바꾸면 호출부 kwargs 와 템플릿 변수명이 어긋나도
    (StrictUndefined → UndefinedError) 테스트가 전부 통과한다.
    """

    def _evidence(self):
        return [Evidence(id="E1", cnts_id="A", meta={"title": "논문 가", "pub_date": "2008"},
                         chunks=[Chunk("c1", "본문 발췌", 1, 1, 0.9)])]

    def _run(self, monkeypatch, chat, evidence=None):
        monkeypatch.setattr(critic, "chat", chat)
        sq = SubQuestion(idx=0, text="하위질문", queries=["첫 검색어", "둘째 검색어"])
        return asyncio.run(critic.critique(
            sq, evidence or self._evidence(), params=merge_params({"min_evidence_per_subq": 4}),
        ))

    def test_renders_real_template_and_parses_reply(self, monkeypatch):
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return '{"verdict": "insufficient", "note": "부족", "new_queries": ["새 검색어"]}'

        v = self._run(monkeypatch, fake_chat)
        assert v.verdict == "insufficient" and v.new_queries == ["새 검색어"]
        system, user = seen[0][0]["content"], seen[0][1]["content"]
        assert "4편 미만" in system
        assert "하위질문" in user and "첫 검색어, 둘째 검색어" in user
        assert "1편" in user and "본문 발췌" in user

    def test_prompt_asks_for_plain_written_style_note(self, monkeypatch):
        # note 는 보고서 한계 섹션에 그대로 실린다 — 서술은 '~다'인데 note 만 '~합니다'면 한 보고서에서 문체가 갈린다
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return '{"verdict": "sufficient", "note": "충분하다", "new_queries": []}'

        self._run(monkeypatch, fake_chat)
        system = seen[0][0]["content"]
        assert "'~다'로 끝나는 문어체 평서문" in system
        assert "'~합니다'·'~입니다' 금지" in system

    def test_transport_error_is_reported_as_unchecked_not_raised(self, monkeypatch):
        """판정 호출이 일시 오류로 죽으면 '판정 불가'다 — 탐색 실패로 올리면
        이미 모은 근거까지 절에서 빠진다."""
        async def fake_chat(messages, *, params=None, timeout=None):
            raise httpx.ReadTimeout("timeout")

        v = self._run(monkeypatch, fake_chat)
        assert v.verdict == "sufficient"
        assert v.parse_failed is True
        assert v.note == _PARSE_FAILED_NOTE

    def test_http_status_error_is_reported_as_unchecked(self, monkeypatch):
        async def fake_chat(messages, *, params=None, timeout=None):
            req = httpx.Request("POST", "http://llm/chat/completions")
            raise httpx.HTTPStatusError("503", request=req,
                                        response=httpx.Response(503, request=req))

        v = self._run(monkeypatch, fake_chat)
        assert v.parse_failed is True

    def test_prompt_numbers_the_evidence_and_asks_for_off_topic(self, monkeypatch):
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return ('{"verdict": "sufficient", "note": "n", "new_queries": [], '
                    '"off_topic": [1, 2]}')

        v = self._run(monkeypatch, fake_chat)
        system, user = seen[0][0]["content"], seen[0][1]["content"]
        assert '"off_topic": []' in system     # 예시는 빈 배열뿐 — gemma 는 예시의 개수를 베낀다
        # 모두 빼 0편이 되면 runner 가 다시 찾는데(should_recheck 의 emptied), 충분 판정에는 검색어를
        # 제안하지 않는 규칙만 있으면 찾을 검색어가 없다
        assert "남는 근거가 없으니 new_queries 에 다른 검색어를 제안하세요" in system
        assert "[1] 논문 가 (2008) — 본문 발췌" in user
        assert v.off_topic == [1]              # 근거 1편에 2번은 없다

    def test_off_topic_is_limited_to_listed_not_all_evidence(self, monkeypatch):
        """목록 상한 밖 근거는 발췌를 보이지 않았다 — '…외 5편' 줄을 다음 번호로 센 답으로
        runner 가 읽지도 않은 근거를 지우면 안 된다."""
        many = [Evidence(id=f"E{i}", cnts_id=f"c{i}", meta={"title": f"논문{i}", "pub_date": "2020"},
                         chunks=[Chunk(f"k{i}", "본문", 1, 1, 0.9)])
                for i in range(_MAX_LISTED + 5)]

        async def fake_chat(messages, *, params=None, timeout=None):
            return json.dumps({"verdict": "sufficient", "note": "n", "new_queries": [],
                               "off_topic": [_MAX_LISTED, _MAX_LISTED + 1]})

        v = self._run(monkeypatch, fake_chat, evidence=many)
        assert v.off_topic == [_MAX_LISTED]

    def _note_run(self, monkeypatch, note, evidence):
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return json.dumps({"verdict": "sufficient", "note": note, "new_queries": [],
                               "off_topic": []}, ensure_ascii=False)

        v = self._run(monkeypatch, fake_chat, evidence=evidence)
        return v, seen[0][0]["content"]

    def test_note_names_papers_by_title_not_list_number(self, monkeypatch):
        """note 는 한계 섹션·진행 패널에 그대로 실린다. 사용자는 critic 목록을 보지 못하고
        보고서(.docx)는 인용을 [n] 으로 렌더하므로, 목록 번호가 남으면 참고문헌 번호로 읽힌다."""
        evs = [Evidence(id=f"E{i}", cnts_id=f"c{i}", meta={"title": t, "pub_date": "2020"},
                        chunks=[Chunk(f"k{i}", "본문", 1, 1, 0.9)])
               for i, t in enumerate(["논문 가", "논문 나"], start=1)]
        v, system = self._note_run(monkeypatch, "[2]·[ 1 ]은 다른 뜻의 자원을 다룬다", evs)
        assert "note 에서 근거를 목록 번호로 가리키지 말고" in system
        # 지우면 '·은 다른 뜻의…' 로 문장이 깨진다 — 제목으로 바꾼다
        assert v.note == "「논문 나」·「논문 가」은 다른 뜻의 자원을 다룬다"

    def test_note_number_outside_the_list_is_left_as_is(self, monkeypatch):
        # 가리킨 논문을 알 수 없는 번호다 — 다른 논문의 제목을 대면 없는 판단을 지어낸다
        v, _ = self._note_run(monkeypatch, "[2]는 다른 뜻의 자원을 다룬다", self._evidence())
        assert v.note == "[2]는 다른 뜻의 자원을 다룬다"
