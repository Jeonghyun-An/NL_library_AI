"""services/research_work/section.py — 절 생성 실행기(kind=section, 스트리밍)·프롬프트 둘·결과 반영.

LLM 은 부르지 않는다. 실제 YAML 을 렌더해 변수 집합·규칙 줄을 고정하고(함정 15 — 예시 없음), 스트리밍 실행
(run_stream_generation)은 조각을 흘리는 가짜 stream_fn 으로 돌린다. 반영(apply)은 history_sqlite 의 SQLite 에서
실제 UPDATE 를 돌린다.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from jinja2 import Environment, meta

from history_sqlite import AsyncSessionOverSync, add_proposal, add_research_job, add_work, make_engine
from models.research_work import ResearchProposal, ResearchWork
from services.prompts import get_prompt
from services.research_work import routing, section
from services.research_work.apply import apply_result
from services.research_work.executors import EXECUTORS
from services.research_work.generate import run_stream_generation
from services.research_work.routing import GEMMA, WORK_MODEL_ROUTES
from services.research_work.section import EXECUTOR, PROMPTS, split_paragraphs
from services.research_work.shapes import GAP_NOTE, MAX_SECTION_PARAGRAPHS

PRIOR = {
    "key": "prior.g1", "kind": "prior", "question": "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
    "topic": {"id": 12, "title": "농촌 독거노인의 사회적 지지와 우울"},
    "research_question": "가족 지지는 농촌 독거노인의 우울을 낮추는가?",
    "group": {"name": "가족 지지와 우울"}, "seeds": [],
    "papers": [
        {"eid": "E1", "cnts_id": "KCI_A", "title": "노인 우울과 가족 지지", "year": 2013, "abstract": "초록 하나",
         "excerpt": {"chunk_id": "KCI_A__0001", "page_start": 2, "page_end": 2, "text": "대목 하나"}},
        {"eid": "E2", "cnts_id": "KCI_B", "title": "사회적 지지 척도", "year": 2015, "abstract": "초록 둘",
         "excerpt": None},
    ],
    "figures": [{"id": "F1", "label": "이 절에 준 논문 수", "value": "2"},
                {"id": "F2", "label": "발행 연도 범위", "value": "2013~2015"}],
    "basis": {"topic_id": 12, "papers": ["KCI_A", "KCI_B", "KCI_C"]},
}
GAP = {
    **PRIOR, "key": "gap", "kind": "gap", "group": None,
    "seeds": [{"heading": "노인의 사회적 지지", "text": "농촌 노인 표본이 부족하다"}],
    "basis": {"topic_id": 12, "papers": ["KCI_A", "KCI_B"]},
}
ANSWER = (
    "가족 지지는 노인의 우울을 낮춘다고 보고되었다 [E1]. 측정 도구도 정리되었다 [E2] [E7].\n\n"
    "두 연구는 [F1]편이고 발행 연도는 [F2]년이다 [E1]."
)


@pytest.fixture
def cfg(monkeypatch):
    settings = routing.get_settings()
    monkeypatch.setattr(settings, "VLM_BASE_URL", "http://qwen.test/v1")
    monkeypatch.setattr(settings, "VLM_MODEL", "qwen-test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://gemma.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    return settings


class TestSplitParagraphs:
    def test_blank_lines_split_and_inner_newlines_join(self):
        raw = "첫 문단 첫 줄\n첫 문단 둘째 줄 [E1].\n\n\n둘째 문단 [E2].\r\n  \r\n셋째 문단 [E1]."
        assert split_paragraphs(raw) == ["첫 문단 첫 줄 첫 문단 둘째 줄 [E1].", "둘째 문단 [E2].", "셋째 문단 [E1]."]

    def test_heading_lines_are_dropped(self):
        raw = "## 선행연구 검토\n\n가족 지지와 우울:\n\n본문이다 [E1].\n\n**정리**: 본문 둘이다 [E2]."
        assert split_paragraphs(raw) == ["본문이다 [E1].", "**정리**: 본문 둘이다 [E2]."]

    def test_capped_from_the_front(self):
        raw = "\n\n".join(f"문단 {i} [E1]." for i in range(MAX_SECTION_PARAGRAPHS + 2))
        assert split_paragraphs(raw) == [f"문단 {i} [E1]." for i in range(MAX_SECTION_PARAGRAPHS)]

    @pytest.mark.parametrize("raw", ["", "   \n\n  ", "# 제목만"])
    def test_nothing_left(self, raw):
        assert split_paragraphs(raw) == []


class TestPrompts:
    @pytest.mark.parametrize("kind, variables, max_tokens", [
        ("prior", {"question", "topic_title", "research_question", "group_name", "evidence_block", "figure_list"},
         1500),
        ("gap", {"question", "topic_title", "research_question", "seed_block", "evidence_block", "figure_list"},
         1200),
    ])
    def test_templates_read_exactly_their_inputs(self, kind, variables, max_tokens):
        tpl = get_prompt(PROMPTS[kind])
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == variables
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": max_tokens, "temperature": 0.3}

    @pytest.mark.parametrize("kind", ["prior", "gap"])
    def test_plain_paragraphs_with_markers_and_no_examples(self, kind):
        """출력은 화면에 그대로 흐르는 평문이다 — JSON 견본·예시가 없고(함정 15), 인용은 [E#]·수치는 [F#] 로만."""
        system = get_prompt(PROMPTS[kind]).system
        assert "예:" not in system and "예시" not in system
        assert "{" not in system and "}" not in system
        assert "[E#]" in system and "[F#]" in system
        assert "숫자를 직접 쓰지 마세요" in system and "제목·저자·연도" in system
        assert "빈 줄" in system and "'~다'" in system

    def test_gap_prompt_writes_only_unchecked_gap_candidates(self):
        assert GAP_NOTE in get_prompt(PROMPTS["gap"]).system


class TestBuild:
    def test_prior_renders_the_group_evidence_and_figures(self):
        messages, params = EXECUTOR.build(PRIOR)

        assert [m["role"] for m in messages] == ["system", "user"]
        user = messages[1]["content"]
        assert "원 질문: 노인의 우울과 사회적 지지에 관한 연구가 궁금해" in user
        assert "연구 주제: 농촌 독거노인의 사회적 지지와 우울" in user
        assert "연구 질문: 가족 지지는 농촌 독거노인의 우울을 낮추는가?" in user
        assert "이 묶음: 가족 지지와 우울" in user
        assert "[E1] 노인 우울과 가족 지지 (2013)\n초록: 초록 하나\n대목(쪽 3): 대목 하나" in user
        assert "[F1] 이 절에 준 논문 수: 2\n[F2] 발행 연도 범위: 2013~2015" in user
        assert params == {"max_tokens": 1500, "temperature": 0.3}

    def test_gap_renders_the_seeds(self):
        messages, params = EXECUTOR.build(GAP)

        user = messages[1]["content"]
        assert "공백 후보:\n- 농촌 노인 표본이 부족하다 (하위질문: 노인의 사회적 지지)" in user
        assert "이 묶음" not in user
        assert params["max_tokens"] == 1200


class TestExecutor:
    def test_kind_stream_and_route(self):
        assert EXECUTOR.kind == "section" and EXECUTOR.stream is True
        assert WORK_MODEL_ROUTES["section"] == GEMMA

    def test_parse_then_bind_checks_every_paragraph(self):
        output = EXECUTOR.bind(EXECUTOR.parse(ANSWER), PRIOR)

        first, second = output["paragraphs"]
        assert first["id"] == "p1" and first["state"] == "proposed" and first["gen_id"] is None
        assert first["text"] == "가족 지지는 노인의 우울을 낮춘다고 보고되었다 [E1]. 측정 도구도 정리되었다 [E2]."
        assert first["cites"] == ["KCI_A", "KCI_B"]
        assert first["checks"]["dropped"] == 1               # 입력에 없는 [E7]
        assert second["id"] == "p2" and second["cites"] == ["KCI_A"]
        assert "[F1]" in second["text"] and "[F2]" in second["text"]
        assert second["checks"]["numbers"] == []             # 숫자는 [F#] 안에만 있다
        assert output["dropped"] == 1

    def test_paragraph_left_empty_by_the_check_is_dropped(self):
        output = EXECUTOR.bind({"paragraphs": ["[E9]", "본문이다 [E1]."]}, PRIOR)
        assert [p["id"] for p in output["paragraphs"]] == ["p1"]
        assert output["paragraphs"][0]["text"] == "본문이다 [E1]."

    def test_unreadable_answer_parses_to_none(self):
        assert EXECUTOR.parse("## 선행연구 검토\n\n") is None

    def test_check_needs_a_paragraph_with_a_valid_citation(self):
        assert EXECUTOR.check(EXECUTOR.bind({"paragraphs": ["근거가 있다 [E2]."]}, PRIOR)) is True
        assert EXECUTOR.check(EXECUTOR.bind({"paragraphs": ["근거 표시가 없다.", "틀린 번호 [E9]다."]}, PRIOR)) is False
        assert EXECUTOR.check({"paragraphs": [], "dropped": 0}) is False

    def test_empty_result(self):
        assert EXECUTOR.empty(PRIOR) == {"paragraphs": [], "dropped": 0}
        assert EXECUTOR.is_empty({"paragraphs": [], "dropped": 0}) is True
        assert EXECUTOR.is_empty(EXECUTOR.bind(EXECUTOR.parse(ANSWER), PRIOR)) is False


class TestStreaming:
    def test_pieces_flow_out_and_the_whole_text_is_checked(self, cfg):
        """조각은 on_delta 로 그대로 흐르고, 끝난 뒤 전체 글이 parse·bind·check 를 거친다(계약 §2)."""
        pieces = ["가족 지지는 노인의 우울을 ", "낮춘다고 보고되었다 [E1].\n", "\n둘째 문단이다 [E2]."]
        calls, deltas = [], []

        async def _stream(messages, *, params=None, timeout=120.0, base_url=None, model=None):
            calls.append((base_url, model, params))
            for piece in pieces:
                yield piece

        async def _delta(text):
            deltas.append(text)

        async def _reset():
            raise AssertionError("다시 부르지 않는다")

        result = asyncio.run(run_stream_generation(EXECUTOR, PRIOR, stream_fn=_stream,
                                                   on_delta=_delta, on_reset=_reset))

        assert deltas == pieces
        assert calls == [("http://gemma.test/v1", "gemma-test", {"max_tokens": 1500, "temperature": 0.3})]
        assert result.model == "gemma-test"
        assert [p["text"] for p in result.output["paragraphs"]] == [
            "가족 지지는 노인의 우울을 낮춘다고 보고되었다 [E1].", "둘째 문단이다 [E2]."]


# ── 반영 ──────────────────────────────────────────────────────────────


OUTLINE = {"topic": {"id": 12, "title": "농촌 독거노인의 사회적 지지와 우울", "question": "q"}, "basis": "concept",
           "groups": [{"key": "prior.g1", "name": "가족 지지와 우울", "hint": "노인의 우울",
                       "papers": ["KCI_A", "KCI_B", "KCI_C"]}],
           "questions": ["q"], "question": "가족 지지는 농촌 독거노인의 우울을 낮추는가?", "method": "",
           "state": "approved", "gen_id": 3, "approved_at": "2026-10-12T01:00:00+00:00"}
OTHER = {"key": "gap", "gen_id": 5, "evidence": {"E1": "KCI_Z"}, "figures": [], "basis": {"topic_id": 12, "papers": []},
         "note": GAP_NOTE, "paragraphs": [{"id": "p1", "text": "다른 절 [E1].", "state": "accepted",
                                           "cites": ["KCI_Z"], "checks": {}, "gen_id": 5}],
         "model": None, "updated_at": "2026-10-12T01:00:00+00:00"}


@pytest.fixture
def engine():
    return make_engine()


def _work(engine, *, version: int = 3, sections: dict | None = None) -> uuid.UUID:
    jid = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, jid, phase="proposal")
    add_proposal(engine, jid, version=version, outline=OUTLINE, sections=sections or {})
    return jid


def _proposal(engine, jid):
    with engine.connect() as conn:
        return conn.execute(sa.select(ResearchProposal.__table__)
                            .where(ResearchProposal.__table__.c.work_id == jid)).mappings().one()


def _apply(engine, gen, output, *, via_dispatcher: bool = False) -> dict:
    async def _go():
        db = AsyncSessionOverSync(engine)
        try:
            result = await (apply_result(db, gen, output) if via_dispatcher else section.apply(db, gen, output))
            await db.commit()
            return result
        finally:
            await db.close()
    return asyncio.run(_go())


def _gen(jid, inp, gid: int = 41):
    return SimpleNamespace(id=gid, work_id=jid, kind="section", target=inp["key"], input=inp)


class TestApply:
    def test_writes_the_section_with_its_evidence_map(self, engine):
        jid = _work(engine, sections={"gap": OTHER})
        output = EXECUTOR.bind(EXECUTOR.parse(ANSWER), PRIOR)

        result = _apply(engine, _gen(jid, PRIOR), output)

        assert result == {"key": "prior.g1", "paragraphs": 2, "dropped": 1}
        row = _proposal(engine, jid)
        assert row["version"] == 4
        written = row["sections"]["prior.g1"]
        assert written["key"] == "prior.g1" and written["gen_id"] == 41
        assert written["evidence"] == {"E1": "KCI_A", "E2": "KCI_B"}
        assert written["figures"] == PRIOR["figures"] and written["basis"] == PRIOR["basis"]
        assert written["note"] is None and written["model"] is None and written["updated_at"]
        assert [(p["id"], p["state"], p["gen_id"]) for p in written["paragraphs"]] == [
            ("p1", "proposed", 41), ("p2", "proposed", 41)]
        assert row["sections"]["gap"] == OTHER               # 다른 절은 그대로
        with engine.connect() as conn:
            progress = conn.execute(sa.select(ResearchWork.__table__.c.progress)
                                    .where(ResearchWork.__table__.c.id == jid)).scalar_one()
        # 주제·연구 질문(목차 값) 2절 + 묶음이 하나뿐인 선행연구가 다 써져 1절 + 이미 있던 연구 공백 1절(정함 16,
        # progress.sections_filled — 방법 제안은 빈 글이라 세지 않는다)
        assert progress["sections"] == 4 and progress["sections_total"] == 6

    def test_gap_section_carries_the_fixed_note(self, engine):
        jid = _work(engine)
        output = EXECUTOR.bind({"paragraphs": ["공백 후보다 [E1]."]}, GAP)

        _apply(engine, _gen(jid, GAP, gid=42), output)

        assert _proposal(engine, jid)["sections"]["gap"]["note"] == GAP_NOTE

    def test_writing_again_replaces_the_whole_section(self, engine):
        jid = _work(engine, sections={"prior.g1": {**OTHER, "key": "prior.g1"}})

        _apply(engine, _gen(jid, PRIOR, gid=50), EXECUTOR.bind({"paragraphs": ["새로 쓴 문단 [E2]."]}, PRIOR))

        written = _proposal(engine, jid)["sections"]["prior.g1"]
        assert written["gen_id"] == 50 and [p["text"] for p in written["paragraphs"]] == ["새로 쓴 문단 [E2]."]

    def test_empty_result_leaves_the_section_alone(self, engine):
        jid = _work(engine, sections={"prior.g1": {**OTHER, "key": "prior.g1"}})

        result = _apply(engine, _gen(jid, PRIOR), EXECUTOR.empty(PRIOR))

        assert result == {"key": "prior.g1", "paragraphs": 0, "dropped": 0}
        row = _proposal(engine, jid)
        assert row["version"] == 3 and row["sections"]["prior.g1"] == {**OTHER, "key": "prior.g1"}

    def test_dispatcher_hands_section_results_to_this_apply(self, engine):
        jid = _work(engine)
        output = EXECUTOR.bind({"paragraphs": ["본문이다 [E1]."]}, PRIOR)

        result = _apply(engine, _gen(jid, PRIOR), output, via_dispatcher=True)

        assert result == {"key": "prior.g1", "paragraphs": 1, "dropped": 0}
        assert _proposal(engine, jid)["version"] == 4


class TestRegistry:
    def test_section_is_registered_after_outline(self):
        assert EXECUTORS["section"] is EXECUTOR
        assert list(EXECUTORS)[:4] == ["concepts", "topic_card", "outline", "section"]
