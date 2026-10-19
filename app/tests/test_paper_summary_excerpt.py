"""test_paper_summary_excerpt.py — 논문 검색 AI 요약(services/search/paper_summary.stream_paper_summary)이 LLM 에 싣는 발췌.

화면(frontend/utils/summaryExcerpt.ts)이 논문마다 원문 초록(짧으면 색인 요약 본문을 덧붙임)을 best_chunk_text 로 보내고,
서버는 앞머리 표지를 걷어 _MAX_EXCERPT_CHARS 안의 마지막 문장 끝에서 자른다. 전에는 500자에서 공백 기준으로 잘라
'…노인의 특성에 따른…' 처럼 문장 한가운데서 끊겼고, 요약이 그 뒷부분을 지어 채웠다(원문 결론과 다른 제언).
"""
import asyncio

from llm_stream_stub import delta, fake_llm
from services.search import paper_summary
from services.search.paper_summary import _MAX_EXCERPT_CHARS, _truncate_at_sentence


def _collect(gen) -> list[str]:
    async def run():
        return [chunk async for chunk in gen]
    return asyncio.run(run())


def _user_prompt(monkeypatch, papers) -> str:
    payloads = fake_llm(monkeypatch, paper_summary, [delta("요약"), "data: [DONE]"])
    _collect(paper_summary.stream_paper_summary("노인 우울", papers))
    return payloads[0]["messages"][1]["content"]


SENTENCE = "본 연구는 노인의 사회적 지지와 우울의 관계를 분석하였다. "


def test_short_text_is_kept_whole():
    assert _truncate_at_sentence("짧은 초록이다.", 100) == "짧은 초록이다."


def test_long_text_is_cut_at_the_last_sentence_end_with_an_ellipsis():
    text = SENTENCE * 5 + "노인의 특성에 따른 간호 중재 프로그램을 개발하는 방향이 논의되었다."
    out = _truncate_at_sentence(text, 170)
    assert out == (SENTENCE * 5).rstrip() + " …"
    assert "노인의 특성에 따른" not in out


def test_decimal_points_are_not_sentence_ends():
    # 'β=.448' 의 점은 뒤가 숫자라 문장 끝이 아니다 — 앞 문장 끝에서 자른다
    first = "사회적 지지는 회복탄력성과 우울의 관계를 조절하였다."
    text = first + " 조절효과는 β=.448, p<.05 수준에서 유의하였고 매개된 조절효과는 유의하지 않았다."
    assert text.index("p<.05") + 5 < 56
    assert _truncate_at_sentence(text, 56) == first + " …"


def test_a_point_on_the_last_kept_character_needs_a_space_after_it():
    # 자르는 자리 바로 앞 글자가 점이어도 그 뒤가 숫자면(0.5) 문장 끝이 아니다 — 한 글자 더 보아 가린다
    text = "가" * 30 + ". " + "나" * 27 + "0.5 값이다."
    assert _truncate_at_sentence(text, 61) == "가" * 30 + ". …"
    # 뒤가 공백이면 문장 끝이다
    head = "가" * 59 + "."
    assert _truncate_at_sentence(head + " 다음 문장이다.", 60) == head + " …"


def test_a_very_long_sentence_falls_back_to_a_word_cut():
    text = "짧다. " + "아주 긴 한 문장이 " * 30 + "끝난다."
    out = _truncate_at_sentence(text, 100)
    assert out.endswith("…") and len(out) <= 101
    assert out != "짧다. …"


def test_english_sentences_end_with_a_period_and_space():
    text = "This study examined support. " * 3 + "It was designed to explain the mediating role of resilience."
    assert _truncate_at_sentence(text, 100) == ("This study examined support. " * 3).rstrip() + " …"


def test_the_prompt_carries_the_abstract_cut_at_a_sentence_end(monkeypatch):
    abstract = SENTENCE * 40   # 약 1240자
    user = _user_prompt(monkeypatch, [{"book_id": "K1", "title": "노인 우울", "authors": "김", "best_chunk_text": abstract}])
    excerpt = next(line for line in user.splitlines() if line.startswith("본 연구는"))
    assert excerpt.endswith("분석하였다. …")
    assert len(excerpt) <= _MAX_EXCERPT_CHARS + 2
    # 국문 초록이 대개 다 들어가는 길이 — 500자에서는 결과·결론 앞에서 끊겼다
    assert _MAX_EXCERPT_CHARS >= 1000


def test_a_paper_without_an_excerpt_is_marked_so_the_model_does_not_guess(monkeypatch):
    user = _user_prompt(monkeypatch, [{"book_id": "K1", "title": "노인 우울", "authors": "김", "best_chunk_text": ""}])
    assert "[1] 노인 우울 — 김\n(초록 없음)" in user


def test_the_system_prompt_keeps_the_grounding_rules(monkeypatch):
    payloads = fake_llm(monkeypatch, paper_summary, [delta("요약"), "data: [DONE]"])
    _collect(paper_summary.stream_paper_summary("q", [{"book_id": "K1", "title": "t", "best_chunk_text": "초록."}]))
    system = payloads[0]["messages"][0]["content"]
    # 그 내용을 직접 말한 논문만 출처로, 생략된 뒤를 짐작하지 않기, 없는 권고·메타 문장 금지, 없으면 섹션 빼기
    for rule in ("직접 말한 논문의 번호만", "짐작해 채우지 마세요", "('~해야 한다')", "확인할 수 없다는 문장은 쓰지 마세요",
                 "섹션을 통째로 빼세요", "마침표 바로 앞에", "굵은 글씨 소제목을 붙이지 마세요"):
        assert rule in system, rule
