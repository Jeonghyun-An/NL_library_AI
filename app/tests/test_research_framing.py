"""services/research/framing.py — 시작 질문 넓히기(06c, 잡 파라미터 broaden).

LLM 은 모듈의 chat 을 monkeypatch 로 바꾼다. async 는 asyncio.run 으로 돈다(pytest-asyncio 가 없다).
"""
import asyncio
import json
import logging

import httpx
import pytest
from jinja2 import Environment, meta

from services.prompts import get_prompt
from services.research import framing
from services.research.framing import (
    BROADEN_TIMEOUT, Framing, clean_terms, frame_question, parse_frame, unframed,
)

ELDERLY = "노인의 우울과 사회적 지지에 관한 연구가 궁금해"
COMPUTING = "컴퓨팅 자원에 대한 연구가 궁금해"
# API min_length=2 를 통과하지만 content_words 가 [] 다 — 낱말 검사가 아무것도 거르지 않는다
NO_CONTENT = "연구가 궁금해"
# 한 글자 명사 — content_words 의 2자 바닥에 걸려 내용어가 [] 다. 넓히기 검사는 한 글자 어절을 따로 본다
CANCER = "암 연구가 궁금해"
WORD_DROPPED = "[framing] 넓힌 질문이 원 질문 낱말"

# parse_frame 이 물러날 때 남기는 [framing] 줄 머리 — 어느 검사가 걸렀는지 가른다
BLANK_OR_LONG = f"[framing] 넓힌 질문이 비었거나 {framing.FRAMED_QUESTION_MAX}자를 넘어"
NOT_A_STRING = "[framing] 응답의 question 이 없거나 문자열이 아니어서"


def _reply(question, terms=()) -> str:
    return json.dumps({"question": question, "terms": list(terms)}, ensure_ascii=False)


def _framing_lines(caplog) -> list[str]:
    # 원 질문으로 물러날 때마다 [framing] 경고는 정확히 한 줄이다 — 판정 뒤 이 줄 수로 물러난 잡을 센다
    return [r.getMessage() for r in caplog.records if "[framing]" in r.getMessage()]


class TestPrompt:
    def test_prompt_takes_only_the_question_and_keeps_its_params(self):
        tpl = get_prompt("research_frame")
        env = Environment()
        used = set()
        for body in (tpl.system, tpl.user):
            used |= meta.find_undeclared_variables(env.parse(body))
        assert used == {"question"}
        assert tpl.parser == "plain"
        assert tpl.params == {"max_tokens": 600, "temperature": 0.2}
        assert tpl.user == "질문: {{ question }}"
        # vLLM 이 guided_* 를 조용히 버린다(함정 25 — test_prompts 가 모든 YAML 을 훑는다)
        assert not [k for k in tpl.params if k.startswith("guided_")]

    def test_prompt_rules_keep_words_and_carry_no_examples(self):
        system, user, _ = get_prompt("research_frame").render(question=ELDERLY)
        assert "원 질문에 쓰인 낱말을 빼거나 바꾸지 않고 모두 그대로 씁니다" in system
        assert "원 질문을 그대로 씁니다" in system
        assert "괄호로 예를 늘어놓지 마세요" in system
        assert "빼야 할 뜻을 범위 용어로 쓰지 마세요" in system
        assert '"question"' in system and '"terms"' in system
        # 예시는 모델이 베낀다(함정 15) — 개수는 코드가 자른다
        assert "예:" not in system + user and "예시" not in system + user
        assert user == f"질문: {ELDERLY}"


class TestParseFrame:
    def test_broadened_question_that_keeps_every_word_is_used(self):
        raw = _reply("클라우드·엣지 환경에서 컴퓨팅 자원을 할당하고 관리하는 방법에 대한 연구 동향은 어떠한가",
                     ["컴퓨팅 자원 할당", "클라우드 컴퓨팅"])
        assert parse_frame(raw, COMPUTING) == Framing(
            "클라우드·엣지 환경에서 컴퓨팅 자원을 할당하고 관리하는 방법에 대한 연구 동향은 어떠한가",
            ["컴퓨팅 자원 할당", "클라우드 컴퓨팅"])

    def test_particle_change_still_keeps_the_word(self):
        # '노인의' → '노인이' — 어절째 대조하면 떨어지지만 내용어(노인)는 그대로 있다
        raw = _reply("노인이 겪는 우울과 사회적 지지의 관계를 다룬 국내 연구는 어디까지 왔는가", ["노인 우울"])
        framed = parse_frame(raw, ELDERLY)
        assert framed is not None and framed.question.startswith("노인이 겪는 우울")

    def test_question_that_drops_a_word_is_refused(self, caplog):
        raw = _reply("노인의 사회적 지지와 삶의 만족에 관한 연구 동향", ["사회적 지지"])
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert parse_frame(raw, ELDERLY) is None
        (line,) = _framing_lines(caplog)
        assert line.startswith("[framing] 넓힌 질문이 원 질문 낱말") and "우울" in line

    @pytest.mark.parametrize(("question", "framed", "dropped"), [
        # 내용어가 [] 인 질문에 지어낸 주제 — 한 글자 어절을 보지 않으면 그대로 받아들여 make_plan·question_used 가 된다
        (CANCER, "인공지능 기반 교육 플랫폼의 효과에 관한 국내 연구 동향", "암"),
        # '암'을 '종양'으로 바꿨다
        (CANCER, "종양의 발생 요인과 치료 효과에 관한 국내 연구 동향", "암"),
        # 내용어(환자·우울)는 모두 있고 '암'만 바뀌었다
        ("암 환자의 우울에 관한 연구", "종양 환자의 우울과 사회적 지지에 관한 국내 연구 동향", "암"),
        ("뇌 연구", "인지 기능과 학습에 관한 국내 연구 동향", "뇌"),
        # 문장부호는 content_words 처럼 공백이다 — '뇌·인지'를 한 어절로 보면 '뇌'가 빠져도 지나간다
        ("뇌·인지 연구", "인지 기능과 학습 전략에 관한 국내 연구 동향", "뇌"),
        # NFKC·casefold 도 content_words 와 같다 — 전각 'Ｃ' 는 'c' 다
        ("Ｃ 언어 교육 연구가 궁금해", "파이썬 언어 교육의 방법과 효과에 관한 국내 연구 동향", "c"),
    ], ids=["no-content-words-made-up-topic", "no-content-words-replaced", "replaced-beside-content-words",
            "brain", "punctuation", "nfkc"])
    def test_question_that_drops_a_one_char_word_is_refused(self, question, framed, dropped, caplog):
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert parse_frame(_reply(framed, ["교육 플랫폼"]), question) is None
        # 같은 낱말 검사 줄이다 — 판정 뒤 '[framing] 넓힌 질문이 원 질문 낱말' 줄 수에 함께 세진다
        (line,) = _framing_lines(caplog)
        assert line.startswith(WORD_DROPPED) and f"['{dropped}']" in line

    def test_broadened_question_that_keeps_a_one_char_word_is_used(self):
        raw = _reply("암의 발생 요인과 치료, 환자의 삶의 질에 관한 국내 연구 동향", ["암 치료", "암 환자 삶의 질"])
        assert parse_frame(raw, CANCER) == Framing(
            "암의 발생 요인과 치료, 환자의 삶의 질에 관한 국내 연구 동향", ["암 치료", "암 환자 삶의 질"])

    @pytest.mark.parametrize(("question", "framed"), [
        ("노인 및 장애인 복지 정책 연구가 궁금해", "노인과 장애인을 위한 복지 정책의 효과와 과제에 관한 국내 연구 동향"),
        ("더 효과적인 독서 교육 방법 연구가 궁금해", "효과적인 독서 교육 방법과 그 효과를 다룬 국내 연구 동향"),
    ], ids=["and", "more"])
    def test_one_char_function_words_may_be_rephrased(self, question, framed):
        # 및·더 는 주제가 아니라 잇는 말이다 — 넓힌 문장이 다른 말로 바꾸거나 빼도 받아들인다
        assert parse_frame(_reply(framed), question) == Framing(framed, [])

    @pytest.mark.parametrize(("raw", "question", "head"), [
        (_reply("   "), ELDERLY, BLANK_OR_LONG),
        # 내용어가 없는 질문은 낱말 검사가 아무것도 거르지 않는다 — 빈 문장은 이 검사만 막는다(빠지면 make_plan('')·
        # question_used '' 가 된다). 이름표만 옮겨 낸 답도 이름표를 떼면 빈 문장이다
        (_reply("   "), NO_CONTENT, BLANK_OR_LONG),
        (_reply("질문: "), NO_CONTENT, BLANK_OR_LONG),
        (json.dumps({"question": 3, "terms": ["노인"]}), ELDERLY, NOT_A_STRING),
        (json.dumps({"terms": ["노인 우울"]}, ensure_ascii=False), ELDERLY, NOT_A_STRING),
        (_reply("노인의 우울과 사회적 지지 " + "가" * 500), ELDERLY, BLANK_OR_LONG),
    ], ids=["blank", "blank-no-content-words", "label-only-no-content-words", "not-a-string", "missing", "too-long"])
    def test_empty_non_string_or_too_long_question_is_refused(self, raw, question, head, caplog):
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert parse_frame(raw, question) is None
        # 줄 머리까지 본다 — 어느 검사가 걸렀는지 고정한다(뒤의 낱말 검사가 대신 걸러도 통과하지 않게)
        (line,) = _framing_lines(caplog)
        assert line.startswith(head)

    def test_specific_question_returned_as_it_is_is_kept(self):
        # 함정 26 — 모델이 입력을 그대로 베껴도 정상이다(이미 구체적인 질문은 그대로 두라고 했다)
        question = "「공공도서관 서비스 고객만족도 평가체계에 관한 연구」에서 출발해, 선행 연구는 어떻게 전개되어 왔는가?"
        framed = parse_frame(_reply(question, ["공공도서관 고객만족도"]), question)
        assert framed == Framing(question, ["공공도서관 고객만족도"])

    def test_echoed_input_label_is_stripped(self):
        # 함정 26 — 입력 이름표('질문:')째 옮겨 낸 답은 낱말 검사를 통과한다. 떼지 않으면 계획 입력이
        # '질문: 질문: …' 이 되고 화면의 '이렇게 이해했어요' 줄에도 이름표가 실린다
        assert parse_frame(_reply("질문: " + ELDERLY, ["노인 우울"]), ELDERLY) == Framing(ELDERLY, ["노인 우울"])
        # 앞 공백·전각 콜론도 같은 이름표다
        assert parse_frame(_reply("  질문 ： " + ELDERLY), ELDERLY) == Framing(ELDERLY, [])

    @pytest.mark.parametrize("raw", [None, "", "질문을 넓혔습니다.", "[1, 2]", '{"question": "노인의'],
                             ids=["none", "empty", "prose", "list", "cut"])
    def test_unreadable_reply_is_refused(self, raw, caplog):
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert parse_frame(raw, ELDERLY) is None
        assert len(_framing_lines(caplog)) == 1


class TestCleanTerms:
    def test_terms_are_normalized_deduplicated_and_cut_at_four(self):
        raw = ["ＣＳＲ", "csr", "  재무   성과 ", "기업의 사회적 책임", "지배구조", "환경 경영"]
        assert clean_terms(raw) == ["CSR", "재무 성과", "기업의 사회적 책임", "지배구조"]

    def test_terms_that_are_not_strings_empty_or_too_long_are_dropped(self):
        raw = ["클라우드", 3, None, "", "   ", ["엣지"], "가" * 31, "나" * 30]
        assert clean_terms(raw) == ["클라우드", "나" * 30]
        assert clean_terms("클라우드") == [] and clean_terms(None) == []


def _status_error() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://gemma.test/v1/chat/completions")
    return httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))


class TestFrameQuestion:
    def test_gemma_is_called_once_with_the_broaden_timeout(self, monkeypatch):
        calls = []

        async def fake_chat(messages, **kw):
            calls.append((messages, kw))
            return _reply("노인이 겪는 우울과 사회적 지지의 관계에 관한 국내 연구 동향", ["노인 우울", "사회적 지지"])

        monkeypatch.setattr(framing, "chat", fake_chat)
        out = asyncio.run(frame_question(ELDERLY))

        assert out == Framing("노인이 겪는 우울과 사회적 지지의 관계에 관한 국내 연구 동향", ["노인 우울", "사회적 지지"])
        ((messages, kw),) = calls
        # 모델·엔드포인트를 넘기지 않는다 — LLM_BASE_URL·LLM_MODEL(gemma). 시간은 chat 기본 120초가 아니라 20초
        assert kw == {"params": {"max_tokens": 600, "temperature": 0.2}, "timeout": BROADEN_TIMEOUT}
        assert BROADEN_TIMEOUT == 20
        assert [m["role"] for m in messages] == ["system", "user"]
        assert messages[1]["content"] == f"질문: {ELDERLY}"

    @pytest.mark.parametrize("error", [
        httpx.ReadTimeout("응답 없음"), httpx.ConnectError("연결 거부"), _status_error(),
        ValueError("JSON 아님"), KeyError("choices"), IndexError("list index out of range"),
    ], ids=["read-timeout", "connect", "status", "json", "key", "index"])
    def test_llm_failure_keeps_the_original_question(self, monkeypatch, caplog, error):
        async def fake_chat(messages, *, params=None, timeout=None):
            raise error

        monkeypatch.setattr(framing, "chat", fake_chat)
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert asyncio.run(frame_question(ELDERLY)) == unframed(ELDERLY) == Framing(ELDERLY, [])
        (line,) = _framing_lines(caplog)
        assert line.startswith("[framing] 넓히기 호출 실패")

    def test_refused_reply_keeps_the_original_question(self, monkeypatch, caplog):
        async def fake_chat(messages, *, params=None, timeout=None):
            return _reply("사회적 지지에 관한 연구 동향", ["사회적 지지"])     # 노인·우울이 빠졌다

        monkeypatch.setattr(framing, "chat", fake_chat)
        with caplog.at_level(logging.WARNING, logger="services.research.framing"):
            assert asyncio.run(frame_question(ELDERLY)) == Framing(ELDERLY, [])
        # 까닭은 parse_frame 이 한 줄 남긴다 — frame_question 이 다시 찍으면 낱말 검사 실패가 두 번 세진다
        assert len(_framing_lines(caplog)) == 1

    def test_unexpected_errors_are_not_swallowed(self, monkeypatch):
        # 함정 19 — 코드 결함을 '원문'으로 숨기면 스위치를 켠 판정이 넓히기 없이 나온다. 계획 태스크가 계획 실패로 닫는다
        async def fake_chat(messages, *, params=None, timeout=None):
            raise RuntimeError("코드 결함")

        monkeypatch.setattr(framing, "chat", fake_chat)
        with pytest.raises(RuntimeError, match="코드 결함"):
            asyncio.run(frame_question(ELDERLY))
