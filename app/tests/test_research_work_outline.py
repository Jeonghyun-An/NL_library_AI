"""services/research_work/outline.py — 목차 만들기(kind=outline)의 입력·프롬프트·해석·검사·반영.

프롬프트는 실제 YAML(research_outline.yaml)을 렌더한다. LLM 은 가짜 chat_fn 으로만 부른다. 반영은
history_sqlite 의 SQLite 에서 실제 SQL 로 돈다(결과 적용은 커밋하지 않는다 — 디스패처의 finish 가 커밋한다).
"""
import asyncio
import json

import pytest
import sqlalchemy as sa
from jinja2 import Environment, meta

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_proposal, add_reading, add_research_job, add_work,
    make_engine,
)
from models.research_work import ResearchGeneration, ResearchProposal, ResearchWork
from services.llm_client import LLMResult
from services.prompts import get_prompt
from services.research_work import routing
from services.research_work.apply import apply_result
from services.research_work.executors import EXECUTORS
from services.research_work.generate import run_generation
from services.research_work.outline import (
    EXECUTOR, FALLBACK_GROUP_NAME, PROMPT, auto_question, clean_questions, outline_input, question_choices,
)
from services.research_work.shapes import GROUP_LABEL_MAX, OUTLINE_QUESTION_MAX, OUTLINE_TARGET

TOPIC = {"id": 12, "title": "노인의 사회적 지지와 우울의 관계", "question": "사회적 지지는 노인의 우울을 낮추는가?"}
GROUPS = [
    {"key": "prior.g1", "hint": "노인의 우울", "papers": ["C1", "C2"]},
    {"key": "prior.g2", "hint": "사회적 지지", "papers": ["C3"]},
]
METAS = {
    "C1": {"title": "노인 우울 연구", "personal_author": "김", "pub_date": "2013-05", "series_title": None},
    "C2": {"title": "C2", "personal_author": None, "pub_date": None, "series_title": None},
    "C3": {"title": "가족 지지와 노년", "personal_author": "이", "pub_date": "발행 2008년", "series_title": None},
}
INPUT = outline_input("노인의 우울과 사회적 지지에 관한 연구가 궁금해", TOPIC, ["노인의 우울", "사회적 지지"],
                      "concept", GROUPS, METAS)
GOOD = json.dumps({"group_names": {"prior.g1": "노년기 우울의 요인", "prior.g2": "가족·사회 지지망"},
                   "research_questions": ["사회적 지지의 유형에 따라 노인 우울은 어떻게 다른가?",
                                          "독거 여부는 지지와 우울의 관계를 조절하는가?",
                                          "지역사회 프로그램은 노인의 지지망을 넓히는가?"]},
                  ensure_ascii=False)


class TestOutlineInput:
    def test_shape_and_numbering_across_groups(self):
        assert INPUT == {
            "question": "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
            "topic": TOPIC,
            "concepts": ["노인의 우울", "사회적 지지"],
            "basis": "concept",
            "groups": [
                {"key": "prior.g1", "hint": "노인의 우울", "papers": [
                    {"eid": "E1", "cnts_id": "C1", "title": "노인 우울 연구", "year": 2013},
                    {"eid": "E2", "cnts_id": "C2", "title": "C2", "year": None}]},
                {"key": "prior.g2", "hint": "사회적 지지", "papers": [
                    {"eid": "E3", "cnts_id": "C3", "title": "가족 지지와 노년", "year": 2008}]},
            ],
        }
        assert json.loads(json.dumps(INPUT)) == INPUT

    def test_missing_meta_uses_the_id(self):
        out = outline_input("q", TOPIC, [], "subq", [{"key": "prior.g1", "hint": "", "papers": ["Z9"]}], {})
        assert out["groups"][0]["papers"] == [{"eid": "E1", "cnts_id": "Z9", "title": "Z9", "year": None}]


class TestCleanQuestions:
    @pytest.mark.parametrize("raw", [None, "질문?", {"q": "질문?"}])
    def test_anything_but_a_list_gives_nothing(self, raw):
        assert clean_questions(raw) == []

    def test_keeps_questions_and_tidies_spaces(self):
        raw = ["  지지는   우울을 낮추는가? ", 3, None, "지지는 우울을 낮춘다.", "독거는 조절하는가？"]
        assert clean_questions(raw) == ["지지는 우울을 낮추는가?", "독거는 조절하는가?"]

    def test_duplicates_ignore_case_and_spaces_and_three_at_most(self):
        raw = ["가는 나인가?", "가는  나인가?", "다는 라인가?", "마는 바인가?", "사는 아인가?"]
        assert clean_questions(raw) == ["가는 나인가?", "다는 라인가?", "마는 바인가?"]

    def test_too_long_is_dropped(self):
        long = "가" * OUTLINE_QUESTION_MAX + "?"
        assert clean_questions([long, "짧은가?"]) == ["짧은가?"]

    def test_citation_markers_are_stripped_before_the_question_mark_check(self):
        # 모델은 시키지 않은 [E#] 를 단다(함정 15) — 끝에 붙어도 질문을 잃지 않고, 가운데 것도 남기지 않는다
        raw = ["독거는 조절하는가? [E2]", "사회적 지지[E1]는 우울을 낮추는가?", "노년은 외로운가？［E3］"]
        assert clean_questions(raw) == ["독거는 조절하는가?", "사회적 지지는 우울을 낮추는가?", "노년은 외로운가?"]


class TestPrompt:
    def test_template_reads_exactly_these_inputs(self):
        tpl = get_prompt(PROMPT)
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == {"question", "topic_title", "topic_question", "groups_block", "group_keys"}
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": 600, "temperature": 0.3}

    def test_format_is_described_in_words_without_samples(self):
        """원소가 든 배열 견본·예시를 두면 모델이 그 개수·분야를 베낀다(함정 15). 키는 말로만 적는다."""
        tpl = get_prompt(PROMPT)
        assert "[" not in tpl.system and "[" not in tpl.user
        assert "예:" not in tpl.system and "예시" not in tpl.system
        assert '"group_names"' in tpl.system and '"research_questions"' in tpl.system
        assert "세 개" in tpl.system

    def test_build_renders_the_real_template(self):
        messages, params = EXECUTOR.build(INPUT)

        assert [m["role"] for m in messages] == ["system", "user"]
        system, user = messages[0]["content"], messages[1]["content"]
        assert "묶음 키(prior.g1, prior.g2)" in system
        assert "고른 연구 주제: 노인의 사회적 지지와 우울의 관계" in user
        assert "주제의 연구 질문: 사회적 지지는 노인의 우울을 낮추는가?" in user
        assert ("묶음 prior.g1 — 배정 기준 핵심 개념: 노인의 우울\n[E1] 노인 우울 연구 (2013)\n"
                "[E2] C2 (연도 미상)") in user
        assert "묶음 prior.g2 — 배정 기준 핵심 개념: 사회적 지지\n[E3] 가족 지지와 노년 (2008)" in user
        assert params == {"max_tokens": 600, "temperature": 0.3}

    def test_subquestion_basis_is_labelled(self):
        _, user = (m["content"] for m in EXECUTOR.build({**INPUT, "basis": "subq"})[0])
        assert "배정 기준 하위질문: 노인의 우울" in user


class TestExecutor:
    def test_kind_and_route(self):
        assert EXECUTOR.kind == "outline" and EXECUTOR.stream is False
        assert routing.WORK_MODEL_ROUTES["outline"] == routing.GEMMA

    def test_parse_then_bind_keeps_only_the_input_keys(self):
        raw = ('```json\n{"group_names": {"prior.g1": "  노년기   우울 ", "prior.g9": "지어낸 묶음"}, '
               '"research_questions": ["지지는 우울을 낮추는가?", "평서문이다."]}\n```')
        parsed = EXECUTOR.parse(raw)
        assert parsed == {"group_names": {"prior.g1": "노년기 우울", "prior.g9": "지어낸 묶음"},
                          "questions": ["지지는 우울을 낮추는가?"], "fallback": False}
        assert EXECUTOR.bind(parsed, INPUT) == {
            "group_names": {"prior.g1": "노년기 우울", "prior.g2": None},
            "questions": ["지지는 우울을 낮추는가?"], "fallback": False}

    def test_citation_markers_are_stripped_from_group_names(self):
        # 이름은 인용 검증을 거치지 않는다 — 남기면 목차 화면과 절 입력에 다른 논문을 가리키는 번호가 실린다
        raw = json.dumps({"group_names": {"prior.g1": "노년기 우울 [E1, E2]", "prior.g2": "[E3]"},
                          "research_questions": []}, ensure_ascii=False)
        assert EXECUTOR.parse(raw)["group_names"] == {"prior.g1": "노년기 우울"}

    @pytest.mark.parametrize("raw", ["목차를 만들지 못했다", '{"group_names": [], "research_questions": []}',
                                     '{"group_names": {"prior.g1": "가"}}'])
    def test_unreadable_answers_parse_to_none(self, raw):
        assert EXECUTOR.parse(raw) is None

    def test_check_needs_every_name_distinct_names_and_two_questions(self):
        ok = {"group_names": {"prior.g1": "가", "prior.g2": "나"}, "questions": ["가?", "나?"], "fallback": False}
        assert EXECUTOR.check(ok) is True
        assert EXECUTOR.check({**ok, "group_names": {"prior.g1": "가", "prior.g2": None}}) is False
        assert EXECUTOR.check({**ok, "group_names": {"prior.g1": "가 나", "prior.g2": "가나"}}) is False
        assert EXECUTOR.check({**ok, "questions": ["가?"]}) is False
        assert EXECUTOR.check({**ok, "group_names": {}}) is False

    def test_empty_result_uses_the_hints_and_the_card_question(self):
        out = EXECUTOR.empty(INPUT)
        assert out == {"group_names": {"prior.g1": "노인의 우울", "prior.g2": "사회적 지지"},
                       "questions": [TOPIC["question"]], "fallback": True}
        assert EXECUTOR.is_empty(out) is True and EXECUTOR.is_empty({"fallback": False}) is False

    def test_empty_result_without_a_hint_gets_a_plain_name(self):
        bare = {**INPUT, "topic": {**TOPIC, "question": ""},
                "groups": [{"key": "prior.g1", "hint": "", "papers": []}]}
        assert EXECUTOR.empty(bare) == {"group_names": {"prior.g1": FALLBACK_GROUP_NAME},
                                        "questions": [], "fallback": True}

    def test_a_long_subquestion_hint_is_cut_to_the_name_limit(self):
        # 하위질문 소속이면 hint 가 하위질문 글이다 — 이름 상한을 넘으면 목차 저장(PUT)이 422 가 된다
        long = {**INPUT, "groups": [{"key": "prior.g1", "hint": "가" * (GROUP_LABEL_MAX + 20), "papers": []}]}
        assert EXECUTOR.empty(long)["group_names"] == {"prior.g1": "가" * GROUP_LABEL_MAX}

    def test_a_missing_group_name_is_asked_again_through_the_common_rule(self, monkeypatch):
        cfg = routing.get_settings()
        monkeypatch.setattr(cfg, "LLM_BASE_URL", "http://gemma.test/v1")
        monkeypatch.setattr(cfg, "LLM_MODEL", "gemma-test")
        missing = json.dumps({"group_names": {"prior.g1": "노년기 우울의 요인"},
                              "research_questions": ["가는 나인가?", "다는 라인가?"]}, ensure_ascii=False)
        answers = [missing, GOOD]
        seen = []

        async def fake_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            seen.append(model)
            return LLMResult(content=answers.pop(0), finish_reason="stop")

        result = asyncio.run(run_generation(EXECUTOR, INPUT, chat_fn=fake_chat))

        assert seen == ["gemma-test", "gemma-test"] and result.model == "gemma-test"
        assert result.output["group_names"] == {"prior.g1": "노년기 우울의 요인", "prior.g2": "가족·사회 지지망"}
        assert len(result.output["questions"]) == 3 and result.output["fallback"] is False


class TestRegistry:
    def test_outline_is_registered(self):
        assert EXECUTORS["outline"] is EXECUTOR


class TestAutoQuestion:
    def test_the_card_question_then_the_first_candidate_then_none(self):
        # 연구 질문은 고른 카드의 질문이다 — 목차 후보는 '서로 다른 각도'로 묻게 해서 첫 후보가 카드와 다른 질문일 수 있다
        # (운영 d60a5dc1: 카드 '…사회적 지지 유형이 노인의 우울에 미치는 영향은?', 첫 후보 '…지지 네트워크의 특징은?')
        card = {"topic": {**TOPIC, "question": "  카드의   질문인가? "}}
        assert auto_question({"questions": ["첫 후보인가?", "둘째 후보인가?"]}, card) == "카드의 질문인가?"
        assert auto_question({"questions": []}, card) == "카드의 질문인가?"
        assert auto_question({}, card) == "카드의 질문인가?"
        # 카드 질문이 비면(공백만이거나 2자 미만 — 승인 PUT 의 하한 APPROVE_NEEDS_QUESTION 과 같다) 첫 후보
        for blank in ("", "   ", "가", None):
            no_card = {"topic": {**TOPIC, "question": blank}}
            assert auto_question({"questions": ["첫 후보인가?", "둘째 후보인가?"]}, no_card) == "첫 후보인가?"
            assert auto_question({"questions": ["   "]}, no_card) is None
            assert auto_question({"questions": []}, no_card) is None
        assert auto_question({}, {}) is None


class TestQuestionChoices:
    def test_the_card_question_first_then_the_candidates_without_repeats(self):
        # [목차 고치기]의 연구 질문 선택지 — 카드 질문(공백 정리, 저장된 question 과 같은 글이라 그 칸이 체크된다) → LLM 후보.
        # 공백·대소문자만 다른 후보는 한 번만
        card = {"topic": {**TOPIC, "question": "  카드의   질문인가? "}}
        output = {"questions": ["첫 후보인가?", "카드의 질문인가?", "둘째 후보인가?"]}
        assert question_choices(output, card) == ["카드의 질문인가?", "첫 후보인가?", "둘째 후보인가?"]
        assert question_choices(output, card)[0] == auto_question(output, card)

    def test_no_card_question_leaves_the_candidates(self):
        output = {"questions": ["첫 후보인가?", "둘째 후보인가?"]}
        assert question_choices(output, {"topic": {**TOPIC, "question": " "}}) == ["첫 후보인가?", "둘째 후보인가?"]
        assert question_choices({}, {}) == []

    def test_the_fallback_outline_has_the_card_question_once(self):
        # 빈 결과(_empty)는 카드 질문 하나를 후보로 채운다 — 겹쳐 두 번 나오지 않는다(화면의 isFallbackOutline 은 후보 2개 미만)
        assert question_choices(EXECUTOR.empty(INPUT), INPUT) == [TOPIC["question"]]


# ── 반영 ────────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    return make_engine()


def _setup(engine, *, outline=None, version=1, input=INPUT):
    jid = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, jid, phase="proposal")
    for cnts_id in ("C1", "C2", "C3"):
        add_reading(engine, jid, cnts_id, state="in")
    add_proposal(engine, jid, version=version, outline=outline)
    gid = add_generation(engine, jid, kind="outline", status="running", target=OUTLINE_TARGET, input=input)
    return jid, gid


def _apply(engine, gid, output):
    commits: list[str] = []
    sa.event.listen(engine, "commit", lambda conn: commits.append("COMMIT"))

    async def _go():
        db = AsyncSessionOverSync(engine)
        try:
            gen = await db.get(ResearchGeneration, gid)
            payload = await apply_result(db, gen, output)
            pending = list(commits)
            await db.commit()
            return payload, pending
        finally:
            await db.close()

    return asyncio.run(_go())


def _proposal(engine, jid):
    table = ResearchProposal.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table).where(table.c.work_id == jid)).mappings().one()


NOW = "2026-10-17T01:02:03+00:00"
CARD_QUESTION = TOPIC["question"]      # 자동 확정의 연구 질문 = 고른 카드의 질문(GOOD 의 첫 후보가 아니다)


class TestApply:
    def test_writes_an_approved_auto_outline_with_the_card_question(self, engine, monkeypatch):
        # 06e(D20) — [보고서 만들기] 한 번으로 목차를 자동 확정한다: 연구 질문 = 고른 카드의 질문, 방법 빈칸, 승인·auto 표시.
        # 선택지는 카드 질문 → LLM 후보
        monkeypatch.setattr("services.research_work.outline._now", lambda: NOW)
        jid, gid = _setup(engine)
        output = EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT)

        payload, pending = _apply(engine, gid, output)

        assert payload == {"fallback": False, "auto": True}
        assert pending == []                       # 반영은 커밋하지 않는다 — 위 커밋은 테스트가 했다
        row = _proposal(engine, jid)
        assert row["version"] == 2
        assert row["outline"] == {
            "topic": TOPIC, "basis": "concept", "concepts": ["노인의 우울", "사회적 지지"],
            "groups": [{"key": "prior.g1", "name": "노년기 우울의 요인", "hint": "노인의 우울",
                        "papers": ["C1", "C2"]},
                       {"key": "prior.g2", "name": "가족·사회 지지망", "hint": "사회적 지지", "papers": ["C3"]}],
            "questions": [CARD_QUESTION, *output["questions"]], "question": CARD_QUESTION, "method": "",
            "state": "approved",
            "gen_id": gid, "approved_at": NOW, "auto": True,
        }
        with engine.connect() as conn:
            progress = conn.execute(sa.select(ResearchWork.__table__.c.progress)
                                    .where(ResearchWork.__table__.c.id == jid)).scalar_one()
        assert progress["reading"] == 3 and progress["sections_total"] == 6

    def test_fallback_outline_is_flagged(self, engine, monkeypatch):
        # 모델이 끝내 실패해도 빈 결과가 카드 질문 하나를 후보로 채운다 — 그 질문으로 자동 승인한다
        monkeypatch.setattr("services.research_work.outline._now", lambda: NOW)
        jid, gid = _setup(engine)

        payload, _ = _apply(engine, gid, EXECUTOR.empty(INPUT))

        assert payload == {"fallback": True, "auto": True}
        outline = _proposal(engine, jid)["outline"]
        assert [g["name"] for g in outline["groups"]] == ["노인의 우울", "사회적 지지"]
        assert outline["questions"] == [TOPIC["question"]]
        assert (outline["question"], outline["state"], outline["approved_at"], outline["auto"]) == (
            TOPIC["question"], "approved", NOW, True)

    def test_a_new_outline_replaces_an_approved_one(self, engine, monkeypatch):
        # [보고서 다시 만들기]는 새 반영이다 — 옛 승인·질문·방법을 버리고 카드 질문으로 다시 자동 승인한다(auto 가 다시 붙는다)
        monkeypatch.setattr("services.research_work.outline._now", lambda: NOW)
        approved = {"state": "approved", "groups": [], "question": "옛 질문?", "method": "옛 방법",
                    "approved_at": "2026-10-10"}
        jid, gid = _setup(engine, outline=approved, version=5)

        _apply(engine, gid, EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT))

        row = _proposal(engine, jid)
        assert row["version"] == 6
        out = row["outline"]
        assert (out["state"], out["question"], out["method"], out["approved_at"], out["auto"]) == (
            "approved", CARD_QUESTION, "", NOW, True)

    def test_a_new_outline_keeps_the_research_background(self, engine, monkeypatch):
        # 06e(§12-11 권고) — 연구 배경은 사용자가 쓰는 자유 글이다. [보고서 다시 만들기]가 목차를 통째로 바꿔도 이어 받는다.
        # 적은 적이 없는(빈 글) 목차를 다시 만들면 키를 두지 않는다
        monkeypatch.setattr("services.research_work.outline._now", lambda: NOW)
        written = {"state": "approved", "groups": [], "question": "옛 질문?", "method": "옛 방법",
                   "approved_at": "2026-10-10", "background": "농촌 독거노인의 고립이 깊어지고 있다."}
        jid, gid = _setup(engine, outline=written, version=5)
        blank_jid, blank_gid = _setup(engine, outline={**written, "background": ""}, version=5)

        _apply(engine, gid, EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT))
        _apply(engine, blank_gid, EXECUTOR.bind(EXECUTOR.parse(GOOD), INPUT))

        out = _proposal(engine, jid)["outline"]
        assert (out["background"], out["question"], out["method"]) == ("농촌 독거노인의 고립이 깊어지고 있다.", CARD_QUESTION, "")
        assert "background" not in _proposal(engine, blank_jid)["outline"]

    def test_no_question_at_all_stays_a_draft_without_auto(self, engine):
        # 후보도 카드 질문도 없으면 06b 처럼 초안으로 둔다 — 빈 질문으로 승인하면 [목차 고치기]의 PUT 이 422 다(정함 3)
        bare = {**INPUT, "topic": {**TOPIC, "question": ""}}
        jid, gid = _setup(engine, input=bare)

        payload, _ = _apply(engine, gid, EXECUTOR.empty(bare))

        assert payload == {"fallback": True, "auto": False}
        out = _proposal(engine, jid)["outline"]
        assert (out["questions"], out["question"], out["state"], out["approved_at"], out["auto"]) == (
            [], None, "draft", None, False)
