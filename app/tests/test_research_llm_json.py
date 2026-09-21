from services.research.llm_json import extract_json


class TestExtractJson:
    def test_plain_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_code_fence(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_bare_fence(self):
        assert extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_preamble_prose(self):
        assert extract_json('다음과 같습니다.\n{"a": 1}') == {"a": 1}

    def test_trailing_prose_with_braces(self):
        """탐욕적 슬라이스는 뒤따르는 } 까지 먹어 파싱이 깨진다."""
        assert extract_json('{"a": 1} 참고: {예시}') == {"a": 1}

    def test_nested_object_is_preserved(self):
        assert extract_json('{"a": {"b": 2}} 끝') == {"a": {"b": 2}}

    def test_no_json_gives_none(self):
        assert extract_json("죄송합니다 판단할 수 없습니다") is None

    def test_broken_json_gives_none(self):
        assert extract_json('{"a": ') is None

    def test_array_at_top_level_gives_none(self):
        """호출부는 dict 를 기대한다 — 리스트를 넘기면 .get 에서 터진다."""
        assert extract_json("[1, 2, 3]") is None

    def test_empty_input(self):
        assert extract_json("") is None

    def test_none_input(self):
        assert extract_json(None) is None
