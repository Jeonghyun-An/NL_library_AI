"""test_paper_summary_stream_end.py — 논문 스트림 셋(services/search/paper_summary)의 끝.

논문 검색 AI 요약(stream_paper_summary)·관련 논문 비교 사유(stream_related_reason)·논문 상세 AI 요약(stream_paper_reason)
은 LLM 호출이 실패하면(httpx 연결·읽기 오류, 4xx·5xx 응답 등) [DONE] 바로 앞에 {error: <문구>} 를 보낸다 — 소장자료
추천 이유 스트림(pipeline.stream_book_reason 의 REASON_STREAM_ERROR)과 같은 꼴. 전에는 '…오류가 발생했습니다.' 를 보통
{text} 로 흘려 화면이 정상 답처럼 이어 붙이고, 논문 상세 sessionStorage 캐시·논문 검색 기록(ai)에 그대로 저장했다.

글 일부가 이미 나간 뒤 실패해도 {error} 를 보낸다(받은 글은 그대로 둔다). 정상으로 끝난 스트림에는 {error} 가 없다.
요약 스트림은 실패하면 출처(sources) 이벤트를 보내지 않는다 — 오류가 [DONE] 바로 앞, 마지막 이벤트다.
"""
import asyncio
from types import SimpleNamespace

import httpx
import pytest

from llm_stream_stub import DONE, delta, events, fake_llm
from services.search import paper_summary

PAPERS = [{"book_id": "KCI_1", "title": "노인 우울 연구", "authors": "김철수", "best_chunk_text": "노인 300명을 조사했다."}]


def _paper():
    return SimpleNamespace(keyword="우울; 노년", themes=None, subject=None, summary=None, title="노인 우울 연구",
                           personal_author="김철수", corporate_author=None, pub_date="2019", publisher=None,
                           series_title=None, grade=None, abstract="노인 우울과 사회적 지지의 관계를 본다.",
                           introduction=None)


def _collect(gen) -> list[str]:
    async def run():
        return [chunk async for chunk in gen]
    return asyncio.run(run())


# (스트림 이름, 부르는 법, 실패 문구 상수, 실패 전에 늘 먼저 오는 이벤트)
STREAMS = [
    ("summary", lambda: paper_summary.stream_paper_summary("노인 우울", PAPERS), "SUMMARY_STREAM_ERROR", []),
    ("related", lambda: paper_summary.stream_related_reason("원 논문", "초록 가", "연관 논문", "초록 나"),
     "RELATED_REASON_STREAM_ERROR", []),
    ("reason", lambda: paper_summary.stream_paper_reason("노인 우울", _paper()), "PAPER_REASON_STREAM_ERROR",
     [{"keywords": ["우울", "노년"]}]),
]
IDS = [s[0] for s in STREAMS]


@pytest.mark.parametrize("name, run, const, lead", STREAMS, ids=IDS)
def test_the_error_phrase_is_a_short_non_empty_constant(name, run, const, lead):
    message = getattr(paper_summary, const)
    assert isinstance(message, str) and message.strip()
    assert "오류가 발생했습니다" not in message


@pytest.mark.parametrize("name, run, const, lead", STREAMS, ids=IDS)
def test_a_failed_connection_sends_an_error_event_before_done(monkeypatch, name, run, const, lead):
    fake_llm(monkeypatch, paper_summary, [], open_error=httpx.ConnectError("vLLM 연결 실패"))

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    # 오류 글을 {text} 로 흘리지 않고, 요약 스트림도 출처를 보내지 않는다
    assert events(chunks) == [*lead, {"error": getattr(paper_summary, const)}]


@pytest.mark.parametrize("name, run, const, lead", STREAMS, ids=IDS)
def test_an_error_status_sends_an_error_event_before_done(monkeypatch, name, run, const, lead):
    # vLLM 이 503 을 돌려주면 본문은 SSE 가 아닌 오류 JSON 이다
    fake_llm(monkeypatch, paper_summary, ['{"object": "error", "message": "Service Unavailable", "code": 503}'],
             status=503)

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [*lead, {"error": getattr(paper_summary, const)}]


@pytest.mark.parametrize("name, run, const, lead", STREAMS, ids=IDS)
def test_a_read_error_after_some_text_keeps_the_text_then_sends_the_error(monkeypatch, name, run, const, lead):
    fake_llm(monkeypatch, paper_summary, [delta("노인 우울은 "), delta("사회적 지지와")],
             read_error=httpx.ReadTimeout("읽기 시간 초과"))

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    got = events(chunks)
    assert got == [*lead, {"text": "노인 우울은 "}, {"text": "사회적 지지와"}, {"error": getattr(paper_summary, const)}]


@pytest.mark.parametrize("name, run, const, lead", STREAMS, ids=IDS)
def test_a_finished_stream_has_no_error_event(monkeypatch, name, run, const, lead):
    fake_llm(monkeypatch, paper_summary, [delta("두 논문은 "), delta("노인 우울을 다룬다."), "data: [DONE]"])

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    got = events(chunks)
    assert not any("error" in e for e in got)
    assert "".join(e.get("text", "") for e in got) == "두 논문은 노인 우울을 다룬다."


def test_a_finished_summary_still_ends_with_its_sources(monkeypatch):
    fake_llm(monkeypatch, paper_summary, [delta("요약 [1]"), "data: [DONE]"])

    got = events(_collect(paper_summary.stream_paper_summary("노인 우울", PAPERS)))

    assert got == [
        {"text": "요약 [1]"},
        {"sources": [{"num": 1, "book_id": "KCI_1", "title": "노인 우울 연구", "authors": "김철수"}]},
    ]
