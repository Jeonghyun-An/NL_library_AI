import pytest

from services.research.planner import parse_plan


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

    def test_no_list_raises(self):
        with pytest.raises(ValueError, match="계획을 해석하지 못했다"):
            parse_plan("죄송하지만 답변할 수 없습니다.", limit=6)
