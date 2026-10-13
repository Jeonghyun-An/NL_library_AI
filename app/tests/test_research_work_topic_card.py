"""services/research_work/topic_card.py — 주제 카드 생성(kind=topic_card)의 프롬프트·해석·근거 되돌리기·수치 틀·
검사·반영.

프롬프트는 실제 YAML(research_topic_card.yaml)을 렌더한다. LLM 은 대본대로 답하는 가짜다. 반영(apply)은
history_sqlite 의 SQLite 에서 실제 SQL 로 돈다.
"""
import asyncio
import json
import re

import pytest
import sqlalchemy as sa
from jinja2 import Environment, meta

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_topic, add_work, make_engine,
)
from models.research import ResearchJob
from models.research_work import GEN_KINDS, ResearchGeneration, ResearchTopic, ResearchWork
from services.llm_client import LLMResult
from services.prompts import get_prompt
from services.research_work import routing, topic_card
from services.research_work.apply import apply_result
from services.research_work.executors import EXECUTORS
from services.research_work.generate import run_generation
from services.research_work.markers import numbers_outside, soften_claims
from services.research_work.seeds import topic_input
from services.research_work.shapes import MIN_TOPIC_EVIDENCE
from services.research_work.topic_card import (
    EXECUTOR, FIG_ADOPTED, FIG_CORPUS, FIG_LATEST, PROMPT, card_figures, evidence_ids, figure_sentence,
)

PAPERS = [
    {"eid": "E1", "cnts_id": "P2", "title": "독거노인의 사회적 관계망", "year": 2015},
    {"eid": "E2", "cnts_id": "P1", "title": "노인의 사회적 지지와 우울의 관계", "year": 2013},
    {"eid": "E3", "cnts_id": "P3", "title": "노인 우울의 종단 연구", "year": None},
]
INPUT = {
    "topic_id": 12,
    "question": "노인의 우울과 사회적 지지에 관한 연구가 궁금해",
    "seed": {"heading": "노인의 사회적 지지와 우울", "text": "독거노인의 지지망을 따로 볼 필요가 있다"},
    "papers": PAPERS,
    "adopted": 12,
    "corpus": {"n_papers": 144748, "from": "1980", "to": "2017"},
}
GOOD = {"title": "독거노인의 지지망 유형과 우울", "question": "독거노인의 지지망 유형에 따라 우울 수준이 다른가?",
        "evidence": ["E1", "E2"]}


def _reply(card: dict) -> str:
    return json.dumps(card, ensure_ascii=False)


def _bound(card: dict, input: dict = INPUT) -> dict:
    return EXECUTOR.bind(EXECUTOR.parse(_reply(card)), input)


class TestPrompt:
    def test_variables_are_fixed(self):
        tpl = get_prompt(PROMPT)
        env = Environment()
        names = meta.find_undeclared_variables(env.parse(tpl.system)) | meta.find_undeclared_variables(
            env.parse(tpl.user))
        assert names == {"question", "heading", "seed", "evidence_list", "keywords"}

    def test_the_keyword_rule_is_there_only_when_keywords_are_given(self):
        # 06e D23 — 고른 키워드가 있을 때만 규칙 한 줄. 없으면(옛 행·키워드 없이 넣은 카드) 06b 프롬프트와 글자까지 같다
        rule = "- title 에 다음 키워드 가운데 하나 이상을 글자 그대로 넣습니다: 노인 우울 · 사회적 지지"
        plain, _ = EXECUTOR.build(INPUT)
        with_kw, _ = EXECUTOR.build({**INPUT, "keywords": ["노인 우울", "사회적 지지"]})
        assert rule in with_kw[0]["content"] and "키워드" not in plain[0]["content"]
        assert with_kw[0]["content"].replace("\n" + rule, "") == plain[0]["content"]
        # 사용자 메시지(원 질문·씨앗·근거)는 그대로다 — 다시 만들 때도 이전 제목을 주지 않는다(함정 26)
        assert with_kw[1]["content"] == plain[1]["content"]

    def test_no_array_sample_no_example_and_no_figures(self):
        # 함정 15 — 원소가 든 배열 견본·JSON 견본·예시는 개수와 분야를 베끼게 한다. 수치는 모델에 주지 않는다(정함 3).
        # Jinja 문({% if %})과 변수({{ }})는 견본이 아니다 — 빼고 본다
        tpl = get_prompt(PROMPT)
        for text in (tpl.system, tpl.user):
            body = re.sub(r"\{%.*?%\}", "", text).replace("{{", "").replace("}}", "")
            assert "[" not in body and "{" not in body
            assert "예:" not in text and "예시" not in text
            assert "F#" not in text and "수치 목록" not in text

    def test_rules_ask_for_supporting_numbers_only(self):
        system = get_prompt(PROMPT).system
        assert "직접 받치는 논문을 둘 이상" in system
        assert "받치지 않는 논문으로 개수를 채우지 않습니다" in system
        assert "논문 제목을 쓰지 않습니다" in system

    def test_params(self):
        assert get_prompt(PROMPT).params == {"max_tokens": 400, "temperature": 0.3}


class TestBuild:
    def test_renders_the_seed_and_the_numbered_papers(self):
        messages, params = EXECUTOR.build(INPUT)
        assert [m["role"] for m in messages] == ["system", "user"]
        user = messages[1]["content"]
        assert "원 질문: 노인의 우울과 사회적 지지에 관한 연구가 궁금해" in user
        assert "보고서 절(하위질문): 노인의 사회적 지지와 우울" in user
        assert "향후 과제(씨앗): 독거노인의 지지망을 따로 볼 필요가 있다" in user
        assert "[E1] 독거노인의 사회적 관계망 (2015)\n[E2] 노인의 사회적 지지와 우울의 관계 (2013)\n" \
               "[E3] 노인 우울의 종단 연구 (연도 미상)" in user
        assert "144748" not in user and "144,748" not in user
        assert params == {"max_tokens": 400, "temperature": 0.3}

    def test_old_rows_without_keywords_still_build(self):
        # 06e 전에 넣은 행엔 keywords 키가 없다 — 다시 부르기(retry)가 그 input 을 그대로 쓴다. 렌더러가 StrictUndefined
        # (services/prompts.py)라 _build 가 늘 넘겨야 한다. 빈 목록·None 도 키워드 규칙이 없는 프롬프트다
        assert "keywords" not in INPUT
        for inp in (INPUT, {**INPUT, "keywords": []}, {**INPUT, "keywords": None}):
            messages, _ = EXECUTOR.build(inp)
            assert "키워드" not in messages[0]["content"]


class TestParse:
    def test_reads_the_three_keys_verbatim(self):
        assert EXECUTOR.parse("```json\n" + _reply(GOOD) + "\n```") == GOOD

    def test_not_json_is_none(self):
        assert EXECUTOR.parse("카드를 만들 수 없습니다") is None

    def test_odd_shapes_become_empty_values(self):
        assert EXECUTOR.parse('{"title": 3, "evidence": "E1"}') == {
            "title": "", "question": "", "evidence": ["E1"]}
        assert EXECUTOR.parse('{"title": "t", "question": "q", "evidence": ["E1", {"id": "E2"}, 3]}') == {
            "title": "t", "question": "q", "evidence": ["E1"]}


class TestEvidenceIds:
    @pytest.mark.parametrize("raw, ids", [
        (["E1", "E2"], ["E1", "E2"]),
        (["[E2]", "［E03］", "【e1】"], ["E2", "E3", "E1"]),
        (["E1 독거노인의 사회적 관계망"], ["E1"]),
        (["E2", "E2", "[E2]"], ["E2"]),
        (["E9", "E0"], []),
        # 여러 번호를 문자열 하나로 묶어 내도 모두 읽는다 — 첫 번호만 남기면 2개 검사에서 떨어진다
        (["E1, E3"], ["E1", "E3"]),
        (["[E1, E3]"], ["E1", "E3"]),
        (["E1·E3"], ["E1", "E3"]),
        (["［E01］；【e3】"], ["E1", "E3"]),
        (["E2, E9"], ["E2"]),
        (["E1 및 E3"], ["E1", "E3"]),
        (["E3 and E1"], ["E3", "E1"]),
        (["(E2, E1)"], ["E2", "E1"]),
    ])
    def test_numbers(self, raw, ids):
        assert evidence_ids(raw, PAPERS) == (ids, 0)

    def test_a_number_inside_a_title_is_not_read_as_evidence(self):
        # 번호 표기로만 된 원소만 번호로 읽는다 — 제목 속 '비타민 E 2 mg' 을 E2 로 읽으면 다른 논문이 근거가 된다
        papers = [{"eid": "E1", "cnts_id": "A", "title": "비타민 E 2 mg 보충과 노인 우울", "year": 2019},
                  {"eid": "E2", "cnts_id": "B", "title": "노인 우울의 종단 연구", "year": 2018},
                  {"eid": "E3", "cnts_id": "C", "title": "사회적 지지와 우울", "year": 2017}]
        assert evidence_ids(["비타민 E 2 mg 보충과 노인 우울"], papers) == (["E1"], 1)
        assert evidence_ids(["비타민 E 3 보충 연구 E2"], papers) == ([], 0)

    def test_one_string_with_several_numbers_passes_the_two_chip_rule(self):
        # _parse 는 문자열 하나를 [문자열] 로 감싼다 — 그 안의 번호를 모두 되돌려야 근거 2개 검사를 넘는다
        bound = _bound({**GOOD, "evidence": "E1, E3"})
        assert bound["card"]["evidence"] == ["P2", "P3"] and bound["card"]["checks"]["recovered"] == 0
        assert EXECUTOR.check(bound) is True

    def test_titles_are_turned_back_into_numbers(self):
        # gemma 표본의 같은 실수 — 근거 칸에 번호 대신 논문 제목(연도 괄호가 붙기도 한다)
        raw = ["노인의 사회적 지지와 우울의 관계", "독거노인의 사회적 관계망 (2015)", "E1"]
        assert evidence_ids(raw, PAPERS) == (["E2", "E1"], 2)

    def test_part_of_a_long_title_is_enough(self):
        assert evidence_ids(["사회적 지지와 우울의 관계"], PAPERS) == (["E2"], 1)

    def test_short_or_ambiguous_parts_are_dropped(self):
        assert evidence_ids(["노인"], PAPERS) == ([], 0)
        papers = [*PAPERS, {"eid": "E4", "cnts_id": "P4", "title": "노인의 사회적 지지와 우울의 관계 재검토",
                            "year": 2016}]
        # '노인의 사회적 지지와 우울' 은 E2·E4 둘 다 품는다 — 어느 논문인지 모른다
        assert evidence_ids(["노인의 사회적 지지와 우울"], papers) == ([], 0)

    def test_a_number_inside_a_word_is_not_a_number(self):
        papers = [{"eid": "E1", "cnts_id": "A", "title": "E2E 암호화 기법 비교", "year": 2019},
                  {"eid": "E2", "cnts_id": "B", "title": "메신저 보안", "year": 2018}]
        assert evidence_ids(["E2E 암호화 기법 비교"], papers) == (["E1"], 1)


class TestFigures:
    def test_three_figures_and_their_sentence(self):
        figures = card_figures(12, 2015, {"n_papers": 144748})
        assert figures == [
            {"id": "F1", "label": FIG_ADOPTED, "value": "12"},
            {"id": "F2", "label": FIG_LATEST, "value": "2015"},
            {"id": "F3", "label": FIG_CORPUS, "value": "144,748"},
        ]
        assert figure_sentence(figures) == (
            "이 하위질문에서 채택한 논문은 [F1]편이다. 고른 근거 가운데 가장 최근 논문은 [F2]년에 나왔다. "
            "수치는 소장 KCI 적재분 [F3]편 기준이다.")

    def test_unknown_values_are_left_out_and_numbered_in_order(self):
        figures = card_figures(None, 2015, None)
        assert figures == [{"id": "F1", "label": FIG_LATEST, "value": "2015"}]
        assert figure_sentence(figures) == "고른 근거 가운데 가장 최근 논문은 [F1]년에 나왔다."

    def test_no_figures_no_sentence(self):
        assert card_figures(None, None, {"n_papers": None}) == []
        assert figure_sentence([]) is None

    def test_the_sentence_has_no_number_outside_the_markers(self):
        sentence = figure_sentence(card_figures(12, 2015, {"n_papers": 144748}))
        assert numbers_outside(sentence) == []


class TestBind:
    def test_card_shape(self):
        assert _bound(GOOD) == {"card": {
            "title": "독거노인의 지지망 유형과 우울",
            "question": "독거노인의 지지망 유형에 따라 우울 수준이 다른가?",
            "evidence": ["P2", "P1"],
            "figure_sentence": "이 하위질문에서 채택한 논문은 [F1]편이다. 고른 근거 가운데 가장 최근 논문은 [F2]년에 "
                               "나왔다. 수치는 소장 KCI 적재분 [F3]편 기준이다.",
            "figures": card_figures(12, 2015, INPUT["corpus"]),
            "latest_year": 2015,
            "edited": False,
            "checks": {"numbers": [], "softened": 0, "recovered": 0},
            "gen_id": None,
        }}

    def test_latest_year_comes_from_the_chosen_evidence(self):
        card = _bound({**GOOD, "evidence": ["E2", "E3"]})["card"]
        assert (card["evidence"], card["latest_year"]) == (["P1", "P3"], 2013)
        assert card_figures(12, None, None) == [{"id": "F1", "label": FIG_ADOPTED, "value": "12"}]
        no_year = _bound({**GOOD, "evidence": ["E3"]})["card"]
        assert no_year["latest_year"] is None and [f["label"] for f in no_year["figures"]] == [
            FIG_ADOPTED, FIG_CORPUS]

    def test_titles_given_as_evidence_are_counted(self):
        card = _bound({**GOOD, "evidence": ["독거노인의 사회적 관계망", "E2"]})["card"]
        assert card["evidence"] == ["P2", "P1"] and card["checks"]["recovered"] == 1

    def test_claims_are_softened_and_stray_numbers_counted(self):
        title = "최초의 독거노인 지지망 연구"
        question = "2015년 이후 지지망 연구가 없다면 무엇을 볼 것인가?"
        card = _bound({**GOOD, "title": title, "question": question})["card"]
        soft_title, n_title = soften_claims(title)
        soft_question, n_question = soften_claims(question)
        assert n_title >= 1                                   # '최초' 는 단정 표현이다(markers.CLAIM_REWRITES)
        assert (card["title"], card["question"]) == (soft_title, soft_question)
        assert card["checks"]["softened"] == n_title + n_question
        assert card["checks"]["numbers"] == numbers_outside(f"{soft_title}\n{soft_question}") != []

    def test_markers_and_extra_spaces_leave_the_text(self):
        card = _bound({**GOOD, "title": "  독거노인의 [E1]  지지망 ", "question": "다른가? [E2]"})["card"]
        assert (card["title"], card["question"]) == ("독거노인의 지지망", "다른가?")

    @pytest.mark.parametrize("field", ["title", "question"])
    def test_an_empty_title_or_question_is_no_card(self, field):
        assert _bound({**GOOD, field: "  "}) == {"card": None}
        assert _bound({**GOOD, field: "[E1]"}) == {"card": None}

    def test_bound_card_survives_a_jsonb_round_trip(self):
        card = _bound(GOOD)
        assert json.loads(json.dumps(card, ensure_ascii=False)) == card


class TestCheck:
    def test_needs_two_evidence_chips(self):
        assert MIN_TOPIC_EVIDENCE == 2
        assert EXECUTOR.check(_bound(GOOD)) is True
        assert EXECUTOR.check(_bound({**GOOD, "evidence": ["E1"]})) is False
        assert EXECUTOR.check(_bound({**GOOD, "evidence": ["E1", "E9", "없는 제목"]})) is False
        assert EXECUTOR.check({"card": None}) is False

    def test_empty_result(self):
        assert EXECUTOR.empty(INPUT) == {"card": None}
        assert EXECUTOR.is_empty({"card": None, "attempts": []}) is True
        assert EXECUTOR.is_empty({}) is True
        assert EXECUTOR.is_empty(_bound(GOOD)) is False


@pytest.fixture
def cfg(monkeypatch):
    settings = routing.get_settings()
    monkeypatch.setattr(settings, "VLM_BASE_URL", "http://qwen.test/v1")
    monkeypatch.setattr(settings, "VLM_MODEL", "qwen-test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://gemma.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    return settings


def _models() -> tuple[str, str]:
    """주제 카드의 (주 모델, 넘길 모델) 이름 — 정함 6 재비교로 라우팅 한 칸이 바뀌어도 이 테스트는 그대로다."""
    name = routing.WORK_MODEL_ROUTES["topic_card"]
    return routing.endpoint(name)[1], routing.endpoint(routing.other(name))[1]


def _run(answers: dict[str, list[str]]):
    seen: list[str] = []

    async def fake_chat(messages, *, params=None, timeout=120.0, base_url=None, model=None):
        seen.append(model)
        return LLMResult(content=answers[model].pop(0), finish_reason="stop")

    return asyncio.run(run_generation(EXECUTOR, INPUT, chat_fn=fake_chat)), seen


class TestThroughTheCommonRule:
    def test_titles_as_evidence_pass_at_the_first_call(self, cfg):
        primary, _ = _models()
        result, seen = _run({primary: [_reply({**GOOD, "evidence": [p["title"] for p in PAPERS[:2]]})]})
        assert seen == [primary]
        assert result.output["card"]["evidence"] == ["P2", "P1"]
        assert result.output["card"]["checks"]["recovered"] == 2

    def test_one_chip_is_asked_again_and_ends_as_insufficient(self, cfg):
        one = _reply({**GOOD, "evidence": ["E1"]})
        primary, fallback = _models()
        result, seen = _run({primary: [one, one], fallback: [one]})
        assert seen == [primary, primary, fallback]
        assert result.output == {"card": None} and result.model is None
        assert [a["outcome"] for a in result.attempts] == ["check", "check", "check"]


class TestExecutors:
    def test_registered_under_its_kind(self):
        assert EXECUTORS["topic_card"] is EXECUTOR
        assert EXECUTOR.kind == "topic_card" and "topic_card" in GEN_KINDS
        assert EXECUTOR.apply is topic_card.apply and EXECUTOR.stream is False


# ── 반영(apply) ─────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    return make_engine()


def _topic_row(engine, tid: int):
    table = ResearchTopic.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table).where(table.c.id == tid)).mappings().one()


def _work_row(engine, wid):
    table = ResearchWork.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table).where(table.c.id == wid)).mappings().one()


def _setup(engine, *, card=None, state="candidate"):
    wid = add_research_job(engine, status="completed", stage="synthesized")
    add_work(engine, wid)
    tid = add_topic(engine, wid, slot=1, seed={"key": "future:0:0"}, card=card, state=state)
    gid = add_generation(engine, wid, kind="topic_card", status="running", target=str(tid),
                         input={**INPUT, "topic_id": tid})
    return wid, tid, gid


def _apply(engine, gid: int, output: dict) -> dict:
    async def _go():
        db = AsyncSessionOverSync(engine)
        try:
            payload = await apply_result(db, await db.get(ResearchGeneration, gid), output)
            await db.commit()
            return payload
        finally:
            await db.close()

    return asyncio.run(_go())


class TestApply:
    def test_card_fills_the_topic_and_the_progress(self, engine):
        wid, tid, gid = _setup(engine)
        card = _bound(GOOD)["card"]

        assert _apply(engine, gid, {"card": card}) == {"topic_id": tid, "state": "candidate"}

        row = _topic_row(engine, tid)
        assert row["card"] == {**card, "edited": False, "gen_id": gid}
        assert row["state"] == "candidate"
        assert _work_row(engine, wid)["progress"]["topics"] == 1

    def test_no_card_marks_the_topic_insufficient(self, engine):
        wid, tid, gid = _setup(engine)

        assert _apply(engine, gid, {"card": None}) == {"topic_id": tid, "state": "insufficient"}

        row = _topic_row(engine, tid)
        assert (row["card"], row["state"]) == ({}, "insufficient")
        assert _work_row(engine, wid)["progress"]["topics"] == 0

    def test_a_card_the_user_wrote_meanwhile_is_kept(self, engine):
        mine = {"title": "내가 쓴 주제", "question": "내 질문?", "evidence": [], "edited": True}
        _, tid, gid = _setup(engine, card=mine, state="candidate")

        assert _apply(engine, gid, _bound(GOOD)) == {"topic_id": tid, "state": "candidate"}

        assert _topic_row(engine, tid)["card"] == mine

    @pytest.mark.parametrize("answer", ["card", "empty"])
    def test_a_picked_card_is_not_overwritten_by_a_regeneration(self, engine, answer):
        # 06e 정함 16 — [이 키워드로 다시 만들기] 가 도는 사이 고른 카드는 새 카드로도, 빈 결과(근거 부족)로도 덮지
        # 않는다 — 덮으면 목차에 '다시 맞춤 필요'가 붙는다. 06b 에서는 고른 카드에 열린 생성이 생길 수 없었다
        old = {"title": "옛 카드", "question": "옛 질문?"}
        _, tid, gid = _setup(engine, card=old, state="picked")
        output = _bound(GOOD) if answer == "card" else {"card": None}

        assert _apply(engine, gid, output) == {"topic_id": tid, "state": "picked"}

        row = _topic_row(engine, tid)
        assert (row["card"], row["state"]) == (old, "picked")

    def test_apply_does_not_commit(self, engine):
        _, tid, gid = _setup(engine)

        async def _go():
            db = AsyncSessionOverSync(engine)
            try:
                await apply_result(db, await db.get(ResearchGeneration, gid), _bound(GOOD))
                await db.rollback()
            finally:
                await db.close()

        asyncio.run(_go())
        assert (_topic_row(engine, tid)["card"], _topic_row(engine, tid)["state"]) == ({}, "candidate")


# ── 씨앗 카드 넣기(enqueue_seed_cards — 06e D23 '카드 시점') ──────────────────────

SEED_QUESTION = "노인의 우울과 사회적 지지에 관한 연구가 궁금해"
SEED_REPORT = {
    "range": {"from": "1980", "to": "2017", "n_papers": 144748},
    "evidence": {"E1": {"cnts_id": "P1", "meta": {"title": "노인의 사회적 지지와 우울의 관계", "pub_date": "2013"}},
                 "E2": {"cnts_id": "P2", "meta": {"title": "독거노인의 사회적 관계망", "pub_date": "2015"}}},
}
KEYWORDS = ["노인 우울", "사회적 지지"]


def _seed(n: int) -> dict:
    return {"key": f"future:{n}:0", "kind": "future", "section_idx": n, "subq_idx": n, "heading": f"절 {n}",
            "text": f"씨앗 {n}", "papers": ["P1", "P2"], "adopted": 5}


def _seed_work(engine, slots: int = 4) -> tuple:
    """이어가기가 남긴 모양 — 잡(질문·보고서)·연구·씨앗 자리 주제 행(slot 1~), 카드 생성은 아직 없다."""
    wid = add_research_job(engine, status="completed", stage="synthesized")
    with engine.begin() as conn:
        conn.execute(sa.update(ResearchJob.__table__).where(ResearchJob.__table__.c.id == wid)
                     .values(question=SEED_QUESTION, report=SEED_REPORT))
    add_work(engine, wid)
    return wid, [add_topic(engine, wid, slot=n, seed=_seed(n)) for n in range(1, slots + 1)]


def _enqueue(engine, wid, keywords, *, commit: bool = True):
    async def _go():
        db = AsyncSessionOverSync(engine)
        try:
            out = await topic_card.enqueue_seed_cards(db, wid, keywords)
            await (db.commit() if commit else db.rollback())
            return out
        finally:
            await db.close()

    return asyncio.run(_go())


def _card_gens(engine, wid):
    table = ResearchGeneration.__table__
    with engine.connect() as conn:
        return conn.execute(sa.select(table).where(table.c.work_id == wid, table.c.kind == "topic_card")
                            .order_by(table.c.id)).mappings().all()


class TestEnqueueSeedCards:
    def test_one_card_generation_per_seed_slot_with_the_keywords(self, engine):
        wid, tids = _seed_work(engine)

        out = _enqueue(engine, wid, KEYWORDS)

        gens = _card_gens(engine, wid)
        assert out == [(tid, g["id"]) for tid, g in zip(tids, gens)]
        assert [(g["target"], g["status"], g["priority"]) for g in gens] == [(str(t), "queued", 10) for t in tids]
        for n, (tid, gen) in enumerate(zip(tids, gens), start=1):
            assert gen["input"] == topic_input(SEED_QUESTION, _seed(n), SEED_REPORT, tid, keywords=KEYWORDS)

    @pytest.mark.parametrize("status", ["done", "failed", "canceled"])
    def test_a_seed_slot_that_already_has_a_card_generation_gets_none(self, engine, status):
        # 상태와 상관없이 — 카드 생성을 한 번 넣은 자리는 다시 넣지 않는다(키워드를 다시 불러 반영돼도 또 들어가지 않는다)
        wid, tids = _seed_work(engine)
        add_generation(engine, wid, kind="topic_card", status=status, target=str(tids[0]))

        out = _enqueue(engine, wid, KEYWORDS)

        assert [tid for tid, _ in out] == tids[1:]
        assert len(_card_gens(engine, wid)) == 4
        assert _enqueue(engine, wid, KEYWORDS) == []            # 두 번째 반영은 아무것도 넣지 않는다

    def test_a_seed_slot_that_already_has_a_card_gets_none(self, engine):
        # 이어가기와 카드 생성 사이(키워드 생성이 줄을 서거나 failed 인 동안)는 빈 씨앗 자리에 카드 생성이 없어 [직접
        # 고치기]가 사용자 카드(edited)를 만든다. 생성 기록이 없다고 그 자리에 카드를 넣으면 LLM 을 헛되이 부르고 결과는
        # apply 의 edited 검사가 버리며, 그 사이 화면은 '다시 만드는 중'을 달고 [고르기]·[직접 고치기]를 막는다.
        # [이 키워드로 다시 만들기](K6)가 고친 카드를 건너뛰는 것과 같은 규칙(spec §12-4·정함 16)
        wid, tids = _seed_work(engine)
        mine = {"title": "내가 쓴 주제", "question": "내가 쓴 질문인가?", "evidence": [], "figure_sentence": None,
                "figures": [], "latest_year": None, "edited": True,
                "checks": {"numbers": [], "softened": 0, "recovered": 0}, "gen_id": None}
        table = ResearchTopic.__table__
        with engine.begin() as conn:
            conn.execute(sa.update(table).where(table.c.id == tids[0]).values(card=mine))

        out = _enqueue(engine, wid, KEYWORDS)

        assert [tid for tid, _ in out] == tids[1:]
        assert [g["target"] for g in _card_gens(engine, wid)] == [str(t) for t in tids[1:]]

    def test_other_direction_cards_do_not_block_the_seed_cards(self, engine):
        # 키워드 생성이 줄을 서는 사이 [다른 방향]이 먼저 카드를 만든 연구 — '그 연구에 카드 생성이 하나라도 있으면 안
        # 넣는다'로 하면 씨앗 카드 4장이 영영 생기지 않는다(06e 정함 29). 판정은 씨앗 자리 행마다다
        wid, tids = _seed_work(engine)
        other = add_topic(engine, wid, origin="other", seed=_seed(9))
        add_generation(engine, wid, kind="topic_card", status="done", target=str(other))

        out = _enqueue(engine, wid, KEYWORDS)

        assert [tid for tid, _ in out] == tids

    def test_user_and_other_direction_topics_get_none(self, engine):
        wid, tids = _seed_work(engine, slots=2)
        add_topic(engine, wid, origin="other", seed=_seed(8))
        add_topic(engine, wid, origin="user", card={"title": "내 주제", "question": "내 질문?", "evidence": []})

        out = _enqueue(engine, wid, [])

        assert [tid for tid, _ in out] == tids
        # 키워드 없이 넣으면(취소·빈 결과) 입력의 keywords 가 비고 프롬프트에 키워드 규칙이 붙지 않는다
        assert [g["input"]["keywords"] for g in _card_gens(engine, wid)] == [[], []]

    def test_does_not_commit(self, engine):
        wid, _ = _seed_work(engine)

        assert len(_enqueue(engine, wid, KEYWORDS, commit=False)) == 4
        assert _card_gens(engine, wid) == []
