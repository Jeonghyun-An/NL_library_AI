"""services/research_work/concepts.py — 핵심 개념 생성(kind=concepts)의 입력·프롬프트·해석·검사.

프롬프트는 실제 YAML(research_concepts.yaml)을 렌더한다. LLM 은 부르지 않는다.
"""
import asyncio
from types import SimpleNamespace

import pytest
from jinja2 import Environment, meta

from models.research_work import GEN_KINDS
from services.llm_client import LLMResult
from services.prompts import get_prompt
from services.research_work import routing
from services.research_work.concepts import (
    EXECUTOR, MAX_CONCEPT_LEN, MAX_CONCEPTS, MIN_CONCEPTS, clean_concepts, concepts_input,
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
        assert (MIN_CONCEPTS, MAX_CONCEPTS, MAX_CONCEPT_LEN) == (2, 5, 40)

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


class TestConceptsInput:
    def test_question_plan_and_section_headings(self):
        assert concepts_input(_job()) == {
            "question": "청소년 독서 격차 연구는 어디까지 왔나",
            "subquestions": ["독서 격차의 정의", "독서 격차를 줄이는 프로그램"],
            "headings": ["독서 격차의 개념", "중재 프로그램의 효과"],
        }

    def test_blank_headings_are_skipped(self):
        job = _job(report={"sections": [{"heading": "  "}, {"intro": "제목 없는 절"}, {"heading": "효과"}]})
        assert concepts_input(job)["headings"] == ["효과"]

    def test_missing_plan_and_report(self):
        out = concepts_input(_job(plan=None, report=None))
        assert out["subquestions"] == [] and out["headings"] == []


class TestPrompt:
    def test_template_reads_only_the_three_inputs(self):
        tpl = get_prompt("research_concepts")
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == {"question", "subquestions", "headings"}
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": 400, "temperature": 0.2}

    def test_build_renders_the_real_template(self):
        messages, params = EXECUTOR.build(concepts_input(_job()))

        assert [m["role"] for m in messages] == ["system", "user"]
        system, user = messages[0]["content"], messages[1]["content"]
        assert "2개 이상 5개 이하" in system and '"concepts"' in system
        assert "원 질문: 청소년 독서 격차 연구는 어디까지 왔나" in user
        assert "- 독서 격차의 정의\n- 독서 격차를 줄이는 프로그램" in user
        assert "- 독서 격차의 개념\n- 중재 프로그램의 효과" in user
        assert params == {"max_tokens": 400, "temperature": 0.2}

    def test_empty_lists_render_as_none(self):
        _, user = (m["content"] for m in EXECUTOR.build(concepts_input(_job(plan=[], report=None)))[0])
        assert user.count("(없음)") == 2

    def test_format_is_described_without_a_sample_list(self):
        """원소가 든 배열 견본({"concepts": ["<핵심 개념>"]})을 두면 모델이 그 개수를 따라 개념 1개만 내
        검사(2개 이상)에서 떨어진다(함정 15). 형식은 말로만 적는다 — 템플릿 어디에도 대괄호가 없다."""
        tpl = get_prompt("research_concepts")
        assert "[" not in tpl.system and "[" not in tpl.user
        assert "문자열" in tpl.system and "배열" in tpl.system


class TestExecutor:
    def test_kind(self):
        assert EXECUTOR.kind == "concepts"

    def test_parse_cleans_the_list(self):
        raw = '```json\n{"concepts": ["독서 격차", "청소년", "독서  격차"]}\n```'
        assert EXECUTOR.parse(raw) == {"concepts": ["독서 격차", "청소년"]}

    @pytest.mark.parametrize("raw", ["개념을 찾지 못했다", '{"concepts": "독서 격차"}', '{"keywords": ["가", "나"]}'])
    def test_unreadable_answers_parse_to_none(self, raw):
        assert EXECUTOR.parse(raw) is None

    def test_check_needs_two_concepts(self):
        assert EXECUTOR.check({"concepts": ["독서 격차", "청소년"]}) is True
        assert EXECUTOR.check({"concepts": ["독서 격차"]}) is False

    def test_empty_result_has_no_concepts(self):
        assert EXECUTOR.empty(concepts_input(_job())) == {"concepts": []}

    def test_one_concept_is_asked_again_through_the_common_rule(self, monkeypatch):
        cfg = routing.get_settings()
        monkeypatch.setattr(cfg, "VLM_BASE_URL", "http://qwen.test/v1")
        monkeypatch.setattr(cfg, "VLM_MODEL", "qwen-test")
        answers = ['{"concepts": ["독서 격차"]}', '{"concepts": ["독서 격차", "청소년", "독서 격차"]}']
        seen = []

        async def fake_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            seen.append(model)
            return LLMResult(content=answers.pop(0), finish_reason="stop")

        result = asyncio.run(run_generation(EXECUTOR, concepts_input(_job()), chat_fn=fake_chat))

        assert seen == ["qwen-test", "qwen-test"]
        assert result.output == {"concepts": ["독서 격차", "청소년"]} and result.model == "qwen-test"


class TestExecutors:
    def test_registry_holds_the_06a_executor(self):
        assert EXECUTORS == {"concepts": EXECUTOR}

    def test_keys_are_generation_kinds(self):
        assert all(kind in GEN_KINDS and ex.kind == kind for kind, ex in EXECUTORS.items())
