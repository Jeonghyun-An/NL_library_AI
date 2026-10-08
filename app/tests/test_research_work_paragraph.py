"""services/research_work/paragraph.py — 문단 다시 쓰기 실행기(kind=paragraph)·프롬프트·결과 반영.

LLM 은 부르지 않는다. 실제 YAML 을 렌더해 변수 집합·규칙 줄을 고정하고(함정 15 — 예시 없음), 반영(apply)은
history_sqlite 의 SQLite 에서 실제 UPDATE 를 돌린다.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from jinja2 import Environment, meta

from history_sqlite import AsyncSessionOverSync, add_proposal, add_research_job, add_work, make_engine
from models.research_work import ResearchProposal
from services.prompts import get_prompt
from services.research_work import paragraph
from services.research_work.apply import apply_result
from services.research_work.executors import EXECUTORS
from services.research_work.paragraph import EXECUTOR, PROMPT, paragraph_input
from services.research_work.routing import GEMMA, WORK_MODEL_ROUTES
from services.research_work.shapes import GAP_NOTE

SECTION_INPUT = {
    "key": "prior.g1", "kind": "prior", "question": "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
    "topic": {"id": 12, "title": "농촌 독거노인의 사회적 지지와 우울"},
    "research_question": "가족 지지는 농촌 독거노인의 우울을 낮추는가?",
    "group": {"name": "가족 지지와 우울"}, "seeds": [],
    "papers": [
        {"eid": "E1", "cnts_id": "KCI_A", "title": "노인 우울과 가족 지지", "year": 2013, "abstract": "초록 하나",
         "excerpt": None},
        {"eid": "E2", "cnts_id": "KCI_B", "title": "사회적 지지 척도", "year": 2015, "abstract": "초록 둘",
         "excerpt": None},
    ],
    "figures": [{"id": "F1", "label": "이 절에 준 논문 수", "value": "2"}],
    "basis": {"topic_id": 12, "papers": ["KCI_A", "KCI_B"]},
}


def _p(pid: str, text: str, state: str = "proposed") -> dict:
    return {"id": pid, "text": text, "state": state, "cites": ["KCI_A"], "checks": {}, "gen_id": 41}


PARAGRAPHS = [_p("p1", "첫 문단 [E1]."), _p("p2", "둘째 문단 [E2].", "accepted"), _p("p3", "셋째 문단 [E1].")]
INPUT = paragraph_input(SECTION_INPUT, PARAGRAPHS, "p2")


class TestParagraphInput:
    def test_section_input_plus_the_paragraph_and_its_neighbours(self):
        assert INPUT == {**SECTION_INPUT, "pid": "p2", "before": "첫 문단 [E1].", "current": "둘째 문단 [E2].",
                         "after": "셋째 문단 [E1]."}

    def test_first_and_last_have_no_neighbour_on_one_side(self):
        assert paragraph_input(SECTION_INPUT, PARAGRAPHS, "p1")["before"] is None
        assert paragraph_input(SECTION_INPUT, PARAGRAPHS, "p3")["after"] is None

    def test_unknown_paragraph_is_rejected(self):
        with pytest.raises(ValueError):
            paragraph_input(SECTION_INPUT, PARAGRAPHS, "p9")


class TestPrompt:
    def test_template_reads_exactly_its_inputs(self):
        tpl = get_prompt(PROMPT)
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == {"question", "topic_title", "research_question", "section_label", "evidence_block",
                        "figure_list", "before", "current", "after"}
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": 600, "temperature": 0.5}

    def test_one_plain_paragraph_with_markers_and_no_examples(self):
        system = get_prompt(PROMPT).system
        assert "예:" not in system and "예시" not in system
        assert "{" not in system and "}" not in system
        assert "[E#]" in system and "[F#]" in system and "숫자를 직접 쓰지 마세요" in system
        assert "문단 하나만" in system and GAP_NOTE in system

    def test_asks_for_new_sentences_not_a_copy_of_the_inputs(self):
        # 운영(2026-10-08): gemma 가 '고칠 문단'을 그대로 내거나 '앞 문단:' 블록을 이름표째 옮겼다
        system = get_prompt(PROMPT).system
        assert "다른 문장으로" in system
        assert "그대로 옮기지 마세요" in system and "이름표를 붙이지 마세요" in system

    def test_build_renders_the_section_label_and_neighbours(self):
        messages, params = EXECUTOR.build(paragraph_input(SECTION_INPUT, PARAGRAPHS, "p1"))

        user = messages[1]["content"]
        assert "절: 선행연구 검토 — 가족 지지와 우울" in user
        assert "앞 문단(참고 — 옮겨 쓰지 않습니다):\n(없음)" in user
        assert "고칠 문단:\n첫 문단 [E1]." in user
        assert "뒤 문단(참고 — 옮겨 쓰지 않습니다):\n둘째 문단 [E2]." in user
        assert user.rstrip().endswith("위 '고칠 문단'을 다른 문장으로 다시 쓴 문단 하나만 쓰세요.")
        assert "[E2] 사회적 지지 척도 (2015)\n초록: 초록 둘" in user
        assert "[F1] 이 절에 준 논문 수: 2" in user
        assert params == {"max_tokens": 600, "temperature": 0.5}

    def test_gap_section_label(self):
        gap = {**SECTION_INPUT, "key": "gap", "kind": "gap", "group": None}
        user = EXECUTOR.build(paragraph_input(gap, PARAGRAPHS, "p2"))[0][1]["content"]
        assert "절: 연구 공백" in user


class TestExecutor:
    def test_kind_route_and_not_streamed(self):
        assert EXECUTOR.kind == "paragraph" and EXECUTOR.stream is False
        assert WORK_MODEL_ROUTES["paragraph"] == GEMMA

    def test_first_paragraph_is_checked_with_the_section_numbers(self):
        output = EXECUTOR.bind(EXECUTOR.parse("다시 쓴 문단:\n\n척도가 정리되었다 [E2] [E5].\n\n덧붙인 문단 [E1]."),
                               INPUT)

        new = output["paragraph"]
        assert (new["id"], new["state"], new["gen_id"]) == ("p2", "proposed", None)
        assert new["text"] == "척도가 정리되었다 [E2]." and new["cites"] == ["KCI_B"]
        assert new["checks"]["dropped"] == 1

    def test_unreadable_answer_parses_to_none(self):
        assert EXECUTOR.parse("# 다시 쓴 문단") is None

    def test_echoed_input_blocks_are_skipped_and_own_label_is_removed(self):
        # 운영(2026-10-08): 답이 '앞 문단: <앞 문단 글>' 로 시작해 그 글이 둘째 문단 자리에 들어갔다
        raw = ("앞 문단: 첫 문단 [E1].\n\n고칠 문단(원문): 둘째 문단 [E2].\n\n뒤 문단(참고 — 옮겨 쓰지 않습니다): 셋째 [E1]."
               "\n\n다시 쓴 문단: 척도를 새로 정리했다 [E2].")
        assert EXECUTOR.parse(raw) == {"text": "척도를 새로 정리했다 [E2]."}
        assert EXECUTOR.parse("앞 문단: 첫 문단 [E1].") is None

    def test_copy_of_the_paragraph_or_its_neighbours_fails_the_check(self):
        # 인용 표기·공백만 다른 글은 옮긴 글이다 — 검사에서 떨어져 다시 부른다(세 번 다 떨어지면 빈 결과 — 문단은 그대로)
        for text in ("둘째 문단 [E2].", "둘째  문단 [E1].", "첫 문단 [E1].", "셋째 문단 [E2] [E1]."):
            assert EXECUTOR.check(EXECUTOR.bind({"text": text}, INPUT)) is False, text
        assert EXECUTOR.check(EXECUTOR.bind({"text": "둘째 문단의 척도를 다른 말로 정리했다 [E2]."}, INPUT)) is True

    def test_first_or_last_paragraph_has_no_neighbour_to_compare(self):
        first = paragraph_input(SECTION_INPUT, PARAGRAPHS, "p1")
        assert EXECUTOR.check(EXECUTOR.bind({"text": "가족 지지를 새로 정리했다 [E1]."}, first)) is True

    def test_check_needs_a_valid_citation(self):
        assert EXECUTOR.check(EXECUTOR.bind({"text": "근거가 있다 [E1]."}, INPUT)) is True
        assert EXECUTOR.check(EXECUTOR.bind({"text": "근거 표시가 없다."}, INPUT)) is False
        assert EXECUTOR.check(EXECUTOR.bind({"text": "[E9]"}, INPUT)) is False

    def test_empty_result(self):
        assert EXECUTOR.empty(INPUT) == {"paragraph": None}
        assert EXECUTOR.is_empty({"paragraph": None}) is True
        assert EXECUTOR.is_empty(EXECUTOR.bind({"text": "근거가 있다 [E1]."}, INPUT)) is False


# ── 반영 ──────────────────────────────────────────────────────────────


EVIDENCE = {"E1": "KCI_A", "E2": "KCI_B"}


@pytest.fixture
def engine():
    return make_engine()


def _work(engine, paragraphs: list[dict], *, evidence: dict | None = None) -> uuid.UUID:
    jid = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, jid, phase="proposal")
    section = {"key": "prior.g1", "gen_id": 41, "evidence": evidence or EVIDENCE, "figures": SECTION_INPUT["figures"],
               "basis": SECTION_INPUT["basis"], "note": None, "paragraphs": paragraphs, "model": None,
               "updated_at": "2026-10-12T01:00:00+00:00"}
    add_proposal(engine, jid, version=7, outline={"state": "approved"}, sections={"prior.g1": section})
    return jid


def _section(engine, jid) -> tuple[dict, int]:
    with engine.connect() as conn:
        row = conn.execute(sa.select(ResearchProposal.__table__)
                           .where(ResearchProposal.__table__.c.work_id == jid)).mappings().one()
    return row["sections"]["prior.g1"], row["version"]


def _apply(engine, jid, output, *, via_dispatcher: bool = False, gid: int = 60) -> dict:
    gen = SimpleNamespace(id=gid, work_id=jid, kind="paragraph", target="prior.g1#p2", input=INPUT)

    async def _go():
        db = AsyncSessionOverSync(engine)
        try:
            result = await (apply_result(db, gen, output) if via_dispatcher else paragraph.apply(db, gen, output))
            await db.commit()
            return result
        finally:
            await db.close()
    return asyncio.run(_go())


NEW = EXECUTOR.bind({"text": "다시 쓴 둘째 문단이다 [E2]."}, INPUT)


class TestApply:
    @pytest.mark.parametrize("state", ["proposed", "accepted"])
    def test_ai_paragraph_is_replaced(self, engine, state):
        jid = _work(engine, [PARAGRAPHS[0], {**PARAGRAPHS[1], "state": state}, PARAGRAPHS[2]])

        assert _apply(engine, jid, NEW) == {"key": "prior.g1", "pid": "p2", "missing": False}

        section, version = _section(engine, jid)
        assert version == 8
        assert [p["text"] for p in section["paragraphs"]] == ["첫 문단 [E1].", "다시 쓴 둘째 문단이다 [E2].",
                                                              "셋째 문단 [E1]."]
        replaced = section["paragraphs"][1]
        assert (replaced["id"], replaced["state"], replaced["gen_id"], replaced["cites"]) == (
            "p2", "proposed", 60, ["KCI_B"])
        assert section["gen_id"] == 41 and section["updated_at"] != "2026-10-12T01:00:00+00:00"

    @pytest.mark.parametrize("paragraphs", [
        [PARAGRAPHS[0], {**PARAGRAPHS[1], "state": "edited"}],
        [PARAGRAPHS[0], {**PARAGRAPHS[1], "state": "authored"}],
        [PARAGRAPHS[0], PARAGRAPHS[2]],
    ], ids=["edited", "authored", "deleted"])
    def test_paragraph_the_user_changed_or_removed_is_left_alone(self, engine, paragraphs):
        jid = _work(engine, paragraphs)

        assert _apply(engine, jid, NEW) == {"key": "prior.g1", "pid": "p2", "missing": True}

        section, version = _section(engine, jid)
        assert version == 7 and section["paragraphs"] == paragraphs

    def test_section_written_again_with_other_numbers_is_left_alone(self, engine):
        # 절을 다시 써서 E2 가 다른 논문을 가리키면 옛 번호로 쓴 문단을 넣지 않는다
        jid = _work(engine, PARAGRAPHS, evidence={"E1": "KCI_A", "E2": "KCI_Z"})

        assert _apply(engine, jid, NEW)["missing"] is True
        assert _section(engine, jid)[1] == 7

    def test_section_written_again_with_the_same_numbers_is_left_alone(self, engine):
        # 같은 묶음으로 절을 다시 쓰면 번호 지도는 같아도 p2 가 다른 글이다 — 옛 앞뒤·고칠 문단을 보고 쓴 결과로 덮지 않는다
        paragraphs = [PARAGRAPHS[0], _p("p2", "새 둘째 문단 — 다른 내용 [E1].", "accepted"), PARAGRAPHS[2]]
        jid = _work(engine, paragraphs)

        assert _apply(engine, jid, NEW) == {"key": "prior.g1", "pid": "p2", "missing": True}

        section, version = _section(engine, jid)
        assert version == 7 and section["paragraphs"] == paragraphs

    def test_empty_result_changes_nothing(self, engine):
        jid = _work(engine, PARAGRAPHS)

        assert _apply(engine, jid, EXECUTOR.empty(INPUT)) == {"key": "prior.g1", "pid": "p2", "missing": False}
        section, version = _section(engine, jid)
        assert version == 7 and section["paragraphs"] == PARAGRAPHS

    def test_dispatcher_hands_paragraph_results_to_this_apply(self, engine):
        jid = _work(engine, PARAGRAPHS)
        assert _apply(engine, jid, NEW, via_dispatcher=True)["missing"] is False
        assert _section(engine, jid)[1] == 8


class TestRegistry:
    def test_paragraph_is_registered_last(self):
        assert EXECUTORS["paragraph"] is EXECUTOR
        assert list(EXECUTORS) == ["concepts", "topic_card", "outline", "section", "paragraph"]
