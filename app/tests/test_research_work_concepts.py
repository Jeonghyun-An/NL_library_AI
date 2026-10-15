"""services/research_work/concepts.py — 핵심 개념 생성(kind=concepts)의 입력·프롬프트·해석·검사.

프롬프트는 실제 YAML(research_concepts.yaml)을 렌더한다. LLM 은 부르지 않는다.
"""
import asyncio
import re
from types import SimpleNamespace

import pytest
from jinja2 import Environment, meta

from models.research_work import GEN_KINDS
from services.llm_client import LLMResult
from services.prompts import get_prompt
from services.research_work import routing
from services.research_work.concepts import (
    EXECUTOR, MAX_CONCEPT_LEN, MAX_CONCEPTS, clean_concepts, concepts_input,
)
from services.research_work.executors import EXECUTORS
from services.research_work.generate import run_generation


def _job(**fields) -> SimpleNamespace:
    base = {
        "question": "청소년 독서 격차 연구는 어디까지 왔나",
        "plan": ["독서 격차의 정의", "독서 격차를 줄이는 프로그램"],
        "report": {"sections": [{"heading": "독서 격차의 개념"}, {"heading": "중재 프로그램의 효과"}]},
    }
    return SimpleNamespace(**{**base, **fields})


class TestCleanConcepts:
    def test_limits(self):
        # 사용자가 고른·고친 칩(PATCH .../work)의 개수·글자 상한 — 키워드 후보 수(keywords.MAX_KEYWORD_CANDIDATES)와 다르다
        assert (MAX_CONCEPTS, MAX_CONCEPT_LEN) == (5, 40)

    @pytest.mark.parametrize("raw", [None, "독서 격차, 청소년", {"concepts": ["가"]}, 3])
    def test_anything_but_a_list_gives_nothing(self, raw):
        assert clean_concepts(raw) == []

    def test_keeps_strings_and_tidies_spaces(self):
        assert clean_concepts(["  독서   격차 ", 3, None, ["청소년"], "청소년"]) == ["독서 격차", "청소년"]

    def test_drops_empty_and_too_long(self):
        assert clean_concepts(["", "   ", "가" * 41, "나" * 40]) == ["나" * 40]

    def test_duplicates_ignore_case_and_spaces(self):
        assert clean_concepts(["AI 윤리", "ai윤리", "AI  윤리", "교육"]) == ["AI 윤리", "교육"]

    def test_keeps_the_first_five(self):
        raw = ["가", "나", "다", "라", "마", "바", "사"]
        assert clean_concepts(raw) == ["가", "나", "다", "라", "마"]

    def test_full_width_and_compatibility_forms_are_normalized(self):
        # 전각 영숫자·전각 공백·전각 하이픈은 NFKC 로 보통 글자가 된다 — 같은 개념이 두 칩이 되지 않는다
        assert clean_concepts(["ＡＩ　윤리", "AI 윤리", "ｅ－러닝"]) == ["AI 윤리", "e-러닝"]

    def test_length_is_counted_after_normalization(self):
        # '㈜' 한 글자는 NFKC 로 '(주)' 세 글자다 — 14개는 42자라 40자 상한을 넘는다
        assert clean_concepts(["㈜" * 14, "㈜" * 13]) == ["(주)" * 13]


class TestConceptsInput:
    def test_question_and_plan_only(self):
        # 보고서 절 제목은 하위질문 글 그대로라 넣지 않는다 — _job 의 report 에 절이 있어도 읽지 않는다
        assert concepts_input(_job()) == {
            "question": "청소년 독서 격차 연구는 어디까지 왔나",
            "subquestions": ["독서 격차의 정의", "독서 격차를 줄이는 프로그램"],
            "paper_keywords": [],
        }

    def test_paper_keywords_ride_along(self):
        # 이어가기(FastAPI)가 채택 논문의 소장 키워드 문서 빈도를 세어 넘긴다 — 워커는 DB 를 읽지 않는다(§6-3)
        paper = [{"text": "독서 격차", "n": 3}, {"text": "학교 도서관", "n": 1}]
        out = concepts_input(_job(), paper_keywords=paper)
        assert out["paper_keywords"] == paper and out["paper_keywords"] is not paper

    def test_non_string_plan_items_are_skipped(self):
        assert concepts_input(_job(plan=["독서 격차의 정의", 3, None, "효과"]))["subquestions"] == [
            "독서 격차의 정의", "효과",
        ]

    def test_missing_plan_and_report(self):
        assert concepts_input(_job(plan=None, report=None)) == {
            "question": "청소년 독서 격차 연구는 어디까지 왔나", "subquestions": [], "paper_keywords": [],
        }


class TestPrompt:
    def test_template_reads_only_the_question_and_subquestions(self):
        tpl = get_prompt("research_concepts")
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == {"question", "subquestions"}
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": 400, "temperature": 0.2}

    def test_build_renders_the_real_template(self):
        messages, params = EXECUTOR.build(concepts_input(_job()))

        assert [m["role"] for m in messages] == ["system", "user"]
        system, user = messages[0]["content"], messages[1]["content"]
        assert '"keywords"' in system and "키워드" in system and "개 이상" not in system
        assert "원 질문: 청소년 독서 격차 연구는 어디까지 왔나" in user
        assert "- 독서 격차의 정의\n- 독서 격차를 줄이는 프로그램" in user
        assert "독서 격차의 개념" not in user and "절 제목" not in system + user
        assert params == {"max_tokens": 400, "temperature": 0.2}

    def test_empty_lists_render_as_none(self):
        _, user = (m["content"] for m in EXECUTOR.build(concepts_input(_job(plan=[], report=None)))[0])
        assert user.count("(없음)") == 1

    def test_old_rows_with_headings_still_build(self):
        """06a 에 만든 생성 행의 input 에는 headings 키가 있다 — 다시 부르기(retry)로 그 input 을 그대로 써도
        절 제목은 프롬프트에 들어가지 않는다."""
        old = {"question": "청소년 독서 격차", "subquestions": ["독서 격차의 정의"], "headings": ["옛 절 제목"]}
        _, user = (m["content"] for m in EXECUTOR.build(old)[0])
        assert "- 독서 격차의 정의" in user and "옛 절 제목" not in user

    def test_format_is_described_without_a_sample_list(self):
        """원소가 든 배열 견본({"keywords": ["<키워드>"]})을 두면 모델이 그 개수를 따라 키워드 1개만 낸다(함정 15).
        형식은 말로만 적는다 — 템플릿 어디에도 대괄호가 없다. 키는 06e 부터 keywords 다."""
        tpl = get_prompt("research_concepts")
        assert "[" not in tpl.system and "[" not in tpl.user
        assert "문자열" in tpl.system and "배열" in tpl.system
        assert '"keywords"' in tpl.system and '"concepts"' not in tpl.system

    def test_no_count_is_written_in_the_prompt(self):
        # 후보 수는 코드가 자른다(MAX_KEYWORD_CANDIDATES) — 프롬프트에 개수를 적으면 모델이 그 수를 채우려 일반어를 끼운다
        tpl = get_prompt("research_concepts")
        for text in (tpl.system, tpl.user):
            assert re.search(r"\d+\s*개", text) is None
            assert "예:" not in text and "예시" not in text


class TestExecutor:
    def test_kind(self):
        assert EXECUTOR.kind == "concepts"

    def test_parse_cleans_the_list(self):
        # 정리·일반어 거르기·같은 말 지우기(띄어쓰기·대소문자 무시)만 하고 순서는 모델이 낸 그대로다
        raw = '```json\n{"keywords": ["독서 격차", "청소년", "독서  격차", "연구 동향", "학교도서관"]}\n```'
        assert EXECUTOR.parse(raw) == {"llm": ["독서 격차", "청소년", "학교도서관"]}
        # 06e 전 프롬프트의 키(concepts)도 읽는다 — 배포 사이에 옛 워커가 넣은 행을 새 워커가 다시 부를 수 있다
        assert EXECUTOR.parse('{"concepts": ["독서 격차"]}') == {"llm": ["독서 격차"]}

    @pytest.mark.parametrize("raw", ["키워드를 찾지 못했다", '{"keywords": "독서 격차"}', '{"terms": ["가", "나"]}'])
    def test_unreadable_answers_parse_to_none(self, raw):
        assert EXECUTOR.parse(raw) is None

    def test_bind_merges_paper_keywords_and_preselects_three(self):
        paper = [{"text": "독서격차", "n": 3}, {"text": "학교 도서관", "n": 2}, {"text": "연구 동향", "n": 5}]
        out = EXECUTOR.bind(EXECUTOR.parse('{"keywords": ["독서 격차", "청소년", "가정 환경"]}'),
                            concepts_input(_job(), paper_keywords=paper))
        assert out == {
            "concepts": ["독서 격차", "청소년", "가정 환경"],
            "candidates": [{"text": "독서 격차", "source": "both", "n": 3},
                           {"text": "청소년", "source": "llm", "n": 0},
                           {"text": "가정 환경", "source": "llm", "n": 0},
                           {"text": "학교 도서관", "source": "paper", "n": 2}],
        }

    def test_check_needs_one_candidate_from_the_model(self):
        bound = EXECUTOR.bind({"llm": ["독서 격차"]}, concepts_input(_job()))
        assert EXECUTOR.check(bound) is True
        # 논문 키워드만 남았다 — 모델이 실패한 것이라 다시 부른다
        paper_only = EXECUTOR.bind({"llm": []}, concepts_input(_job(), paper_keywords=[{"text": "독서 격차", "n": 2}]))
        assert paper_only["candidates"] == [{"text": "독서 격차", "source": "paper", "n": 2}]
        assert EXECUTOR.check(paper_only) is False

    def test_empty_result_has_no_concepts(self):
        # 끝내 못 얻으면 미리 고르지 않고 논문 키워드만 후보로 둔다 — 사용자가 고르거나 [다시]
        assert EXECUTOR.empty(concepts_input(_job())) == {"concepts": [], "candidates": []}
        out = EXECUTOR.empty(concepts_input(_job(), paper_keywords=[{"text": "학교 도서관", "n": 2}]))
        assert out == {"concepts": [], "candidates": [{"text": "학교 도서관", "source": "paper", "n": 2}]}
        assert EXECUTOR.is_empty(out) is True

    def test_only_generic_words_are_asked_again_through_the_common_rule(self, monkeypatch):
        # 키워드 생성의 주 모델은 gemma(LLM_*)다 — 06a Qwen 표본 결정
        cfg = routing.get_settings()
        monkeypatch.setattr(cfg, "LLM_BASE_URL", "http://gemma.test/v1")
        monkeypatch.setattr(cfg, "LLM_MODEL", "gemma-test")
        answers = ['{"keywords": ["연구 동향", "선행연구"]}', '{"keywords": ["독서 격차", "청소년", "독서 격차"]}']
        seen = []

        async def fake_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            seen.append(model)
            return LLMResult(content=answers.pop(0), finish_reason="stop")

        result = asyncio.run(run_generation(EXECUTOR, concepts_input(_job()), chat_fn=fake_chat))

        assert seen == ["gemma-test", "gemma-test"]
        assert [a["outcome"] for a in result.attempts] == ["check", "ok"]
        assert result.output == {
            "concepts": ["독서 격차", "청소년"],
            "candidates": [{"text": "독서 격차", "source": "llm", "n": 0}, {"text": "청소년", "source": "llm", "n": 0}],
        }
        assert result.model == "gemma-test"


class TestExecutors:
    def test_concepts_executor_is_registered(self):
        assert EXECUTORS["concepts"] is EXECUTOR

    def test_keys_are_generation_kinds(self):
        # 06b·06c 가 실행기를 더해도 지키는 규칙 — 키는 생성 종류이고 실행기의 kind 가 키와 같다
        assert set(EXECUTORS) <= set(GEN_KINDS)
        assert all(ex.kind == kind for kind, ex in EXECUTORS.items())
