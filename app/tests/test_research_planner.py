import asyncio

import pytest
from jinja2 import Environment, meta

from services.prompts import get_prompt
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

    def test_prompt_keeps_subquestions_inside_the_core_concept(self, monkeypatch):
        """운영에서 '컴퓨팅 자원' 질문이 HPC·클라우드·엣지처럼 이웃한 기술 목록으로 나뉘었다.

        예시는 넣지 않는다 — gemma 는 예시의 개수·분야를 베낀다(recurring-gotchas 15번).
        """
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return "1. 가"

        monkeypatch.setattr(planner, "chat", fake_chat)
        asyncio.run(planner.make_plan("컴퓨팅 자원에 대한 연구", params=merge_params({})))
        system = seen[0][0]["content"]
        assert "원 질문의 핵심 개념 안에 머뭅니다" in system
        assert "이웃한 기술·분야를 나열하는 식으로 나누지 마세요" in system
        assert "개념·정의, 방법·기법, 적용 분야, 성과·평가, 한계·과제 중 질문에 맞는 것만" in system
        assert "원 질문의 핵심어를 그대로 넣습니다" in system
        assert "최대 6개" in system and "더 적어도 됩니다" in system
        assert "예:" not in system and "예시" not in system

    def test_prompt_keeps_the_target_and_context_of_the_question_in_every_subquestion(self, monkeypatch):
        """D18 — 06a critic 판정에서 무관이 몰린 절은 핵심어 하나는 넣고 원 질문의 대상·관계 축을 떨어뜨린
        하위질문이었다(「사회적 지지 개념 및 측정 도구」는 노인을, 「CSR 측정 방법」은 재무성과를 잃었고,
        「… 적용 분야」는 괄호에 대상을 늘어놓았다). 규칙 줄만 더하고 예시는 넣지 않는다(함정 15)."""
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return "1. 가"

        monkeypatch.setattr(planner, "chat", fake_chat)
        asyncio.run(planner.make_plan("노인의 우울과 사회적 지지에 관한 연구가 궁금해", params=merge_params({})))
        system = seen[0][0]["content"]
        assert ("원 질문이 정한 대상·맥락(연구 대상 집단·기관·장소, 함께 묻는 다른 개념)을 "
                "모든 하위질문에 그대로 씁니다") in system
        assert "측면으로 나눌 때도 그 대상·맥락을 떼어 낸 일반론(정의·측정만 묻는 하위질문)으로 만들지 마세요" in system
        assert "원 질문이 두 개념의 관계를 물으면 모든 하위질문이 두 개념을 함께 다룹니다" in system
        assert "하위질문 안에 괄호로 예를 늘어놓지 마세요" in system
        assert "예:" not in system and "예시" not in system

    def test_plan_prompt_inputs_params_and_output_format_stay(self, monkeypatch):
        """D18 은 규칙 줄만 바꾼다 — 변수(question·limit)·LLM 파라미터·번호 목록 출력이 그대로여야
        parse_plan·job.plan(list[str])·PlanCard·승인 요청 본문이 그대로다."""
        tpl = get_prompt("research_plan")
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == {"question", "limit"}
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": 800, "temperature": 0.3}
        assert "번호 목록으로만 출력합니다" in tpl.system
        assert tpl.user == "질문: {{ question }}"
