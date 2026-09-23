import asyncio

import pytest

from services.research import planner
from services.research.planner import parse_plan, query_key
from services.research.state import merge_params


class TestParsePlan:
    def test_numbered_list(self):
        raw = "1. 첫째 주제\n2. 둘째 주제\n3. 셋째 주제"
        assert parse_plan(raw, limit=6) == ["첫째 주제", "둘째 주제", "셋째 주제"]

    def test_paren_numbering(self):
        assert parse_plan("1) 가\n2) 나", limit=6) == ["가", "나"]

    def test_bullet_list(self):
        assert parse_plan("- 가\n- 나", limit=6) == ["가", "나"]

    def test_preamble_is_dropped(self):
        raw = "다음과 같이 제안합니다.\n\n1. 가\n2. 나"
        assert parse_plan(raw, limit=6) == ["가", "나"]

    def test_limit_truncates(self):
        raw = "\n".join(f"{i}. 주제{i}" for i in range(1, 10))
        assert len(parse_plan(raw, limit=6)) == 6

    def test_blank_and_duplicate_removed(self):
        raw = "1. 가\n2.  \n3. 가\n4. 나"
        assert parse_plan(raw, limit=6) == ["가", "나"]

    def test_markdown_emphasis_stripped(self):
        assert parse_plan("1. **가** 주제", limit=6) == ["가 주제"]

    def test_fully_bolded_item_is_parsed(self):
        """모델이 항목 전체를 굵게 쓰면 앞의 * 가 불릿으로 먹혀 매칭이 깨진다.

        그러면 모든 줄이 탈락해 계획 수립이 통째로 실패하고 job 이 죽는다.
        강조를 항목 매칭보다 먼저 벗겨야 한다.
        """
        assert parse_plan("**1. 가**\n**2. 나**", limit=6) == ["가", "나"]

    def test_bolded_bullet_item_is_parsed(self):
        assert parse_plan("* **가**\n* **나**", limit=6) == ["가", "나"]

    def test_underscore_inside_word_is_preserved(self):
        """전역으로 [*_`] 를 지우면 TF_IDF → TFIDF 로 훼손된다."""
        assert parse_plan("1. TF_IDF 가중치 연구", limit=6) == ["TF_IDF 가중치 연구"]

    def test_duplicate_differing_only_in_whitespace_is_dropped(self):
        assert parse_plan("1. 가 주제\n2. 가  주제", limit=6) == ["가 주제"]

    def test_duplicate_differing_only_in_case_is_dropped(self):
        assert parse_plan("1. AI 윤리\n2. ai 윤리", limit=6) == ["AI 윤리"]

    def test_no_list_raises(self):
        with pytest.raises(ValueError, match="계획을 해석하지 못했다"):
            parse_plan("죄송하지만 답변할 수 없습니다.", limit=6)


class TestQueryKey:
    def test_whitespace_and_case_are_folded(self):
        assert query_key("  AI  윤리 ") == query_key("ai 윤리")


class TestMakePlan:
    def test_renders_real_template_and_parses_reply(self, monkeypatch):
        """chat 만 대역으로 바꾼다 — 호출부 kwargs 가 실제 템플릿을 통과하는지 고정한다."""
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return "1. 가\n2. 나\n3. 다"

        monkeypatch.setattr(planner, "chat", fake_chat)
        plan = asyncio.run(planner.make_plan(
            "청소년 진로상담", params=merge_params({"max_subquestions": 2}),
        ))
        assert plan == ["가", "나"]
        assert "최대 2개" in seen[0][0]["content"]
        assert "청소년 진로상담" in seen[0][1]["content"]
