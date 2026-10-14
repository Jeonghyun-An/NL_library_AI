"""test_book_chat_stream_end.py — DeepRead 대화 스트림(services/chat/book_chat.stream_book_chat)의 끝.

LLM 호출이 실패하면(httpx 연결·읽기 오류, 4xx·5xx 응답 등) [DONE] 바로 앞에 {error: CHAT_STREAM_ERROR} 를 보낸다 —
소장자료 추천 이유 스트림(pipeline.stream_book_reason)과 같은 꼴. 전에는 '응답 생성 중 오류가 발생했습니다.' 를 보통
{text} 로 흘려 화면이 정상 답처럼 이어 붙이고 대화에 남겨, 다음 질문의 history 로 모델에게까지 보냈다.

글 일부가 이미 나간 뒤 실패해도 {error} 를 보낸다. 실패한 답은 인용 출처(sources)를 보내지 않는다 — 오류가 [DONE]
바로 앞, 마지막 이벤트다. 정상으로 끝난 스트림에는 {error} 가 없다.

book_chat 을 더미 embedder·indexer 위에서 올리는 픽스처는 test_book_chat_prompt.py 의 것을 그대로 쓴다.
"""
import asyncio

import httpx
import pytest

from llm_stream_stub import DONE, delta, events, fake_llm
from test_book_chat_prompt import _fake_search, _paper, book_chat  # noqa: F401 — book_chat 은 픽스처


def _stream(book_chat, message="이 논문의 대상은?") -> list[str]:
    async def collect():
        return [chunk async for chunk in book_chat.stream_book_chat("KCI_1", message, [], book=_paper())]
    return asyncio.run(collect())


@pytest.fixture
def hit(book_chat):
    return book_chat.SearchHit(chunk_id="c1", book_id="KCI_1", chunk_idx=0, section_idx=0,
                               text="표본은 노인 300명이다.", page_start=3, page_end=4, score=0.9)


def test_the_error_phrase_is_a_short_non_empty_constant(book_chat):
    assert isinstance(book_chat.CHAT_STREAM_ERROR, str) and book_chat.CHAT_STREAM_ERROR.strip()
    assert "오류가 발생했습니다" not in book_chat.CHAT_STREAM_ERROR


def test_a_failed_connection_sends_an_error_event_before_done(book_chat, monkeypatch, hit):
    _fake_search(monkeypatch, book_chat, [hit])
    fake_llm(monkeypatch, book_chat, [], open_error=httpx.ConnectError("vLLM 연결 실패"))

    chunks = _stream(book_chat)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [{"error": book_chat.CHAT_STREAM_ERROR}]


def test_an_error_status_sends_an_error_event_before_done(book_chat, monkeypatch, hit):
    _fake_search(monkeypatch, book_chat, [hit])
    fake_llm(monkeypatch, book_chat, ['{"object": "error", "message": "Service Unavailable", "code": 503}'],
             status=503)

    chunks = _stream(book_chat)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [{"error": book_chat.CHAT_STREAM_ERROR}]


def test_a_read_error_after_some_text_sends_the_error_and_no_sources(book_chat, monkeypatch, hit):
    # 받은 글이 쪽(p.3–4)을 인용했어도 실패한 답에는 출처 칩을 붙이지 않는다 — 화면은 이 답을 남기지 않는다
    _fake_search(monkeypatch, book_chat, [hit])
    fake_llm(monkeypatch, book_chat, [delta("p.3–4 에 따르면 ")], read_error=httpx.ReadTimeout("읽기 시간 초과"))

    chunks = _stream(book_chat)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [{"text": "p.3–4 에 따르면 "}, {"error": book_chat.CHAT_STREAM_ERROR}]


def test_a_finished_stream_has_no_error_event_and_keeps_its_sources(book_chat, monkeypatch, hit):
    _fake_search(monkeypatch, book_chat, [hit])
    fake_llm(monkeypatch, book_chat, [delta("p.3–4 에 나옵니다."), "data: [DONE]"])

    chunks = _stream(book_chat)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [
        {"text": "p.3–4 에 나옵니다."},
        {"sources": [{"page_start": 3, "page_end": 4, "text": "표본은 노인 300명이다."}]},
    ]


@pytest.mark.parametrize("engine_error", [
    'data: {"error": {"object": "error", "message": "EngineDeadError", "type": "InternalServerError", "code": 500}}',
    'data: {"object": "error", "message": "EngineDeadError", "type": "InternalServerError", "code": 500}',
], ids=["wrapped", "bare"])
def test_an_error_inside_the_stream_sends_the_error_and_no_sources(book_chat, monkeypatch, hit, engine_error):
    # vLLM 이 생성 도중 실패하면 HTTP 200 스트림 안에 오류 줄을 보내고 이어 [DONE] 을 보낸다 — 이것도 실패다
    _fake_search(monkeypatch, book_chat, [hit])
    fake_llm(monkeypatch, book_chat, [delta("p.3–4 에 따르면 "), engine_error, "data: [DONE]"])

    chunks = _stream(book_chat)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [{"text": "p.3–4 에 따르면 "}, {"error": book_chat.CHAT_STREAM_ERROR}]


def test_a_stream_closed_without_done_is_a_failure(book_chat, monkeypatch, hit):
    _fake_search(monkeypatch, book_chat, [hit])
    fake_llm(monkeypatch, book_chat, [delta("p.3–4 에 따르면 ")])

    chunks = _stream(book_chat)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [{"text": "p.3–4 에 따르면 "}, {"error": book_chat.CHAT_STREAM_ERROR}]


def test_the_failure_log_names_the_exception_type_and_the_text_already_sent(book_chat, monkeypatch, hit, caplog):
    # httpx.ReadTimeout 은 str(e) 가 빈 글일 때가 많다 — 예외 종류와 이미 보낸 글 길이로 원인·시점을 남긴다
    _fake_search(monkeypatch, book_chat, [hit])
    fake_llm(monkeypatch, book_chat, [delta("노인 우울은 ")], read_error=httpx.ReadTimeout(""))

    with caplog.at_level("ERROR", logger=book_chat.log.name):
        _stream(book_chat)

    messages = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
    assert len(messages) == 1
    assert "ReadTimeout" in messages[0]
    assert "보낸 글 7자" in messages[0]
