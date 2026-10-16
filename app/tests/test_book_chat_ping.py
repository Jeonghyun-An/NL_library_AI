"""test_book_chat_ping.py — DeepRead 대화 스트림(services/chat/book_chat.stream_book_chat)의 ': ping'.

화면(useDeepReadChat)은 응답 머리도 글 조각도 없이 60초가 지나면 스스로 끊는다. 서버는 첫 글 조각 전(질의 재구성 최대
20초 + 청크 검색 + LLM 첫 토큰 대기)과 조각 사이에 아무것도 보내지 않아 붐빌 때 결국 답했을 요청이 끊길 수 있었다 — 이제
보낼 이벤트 없이 CHAT_PING_INTERVAL(15초) 가 지나면 SSE 주석 줄 ': ping' 을 끼운다(딥리서치 SSE 와 같은 관례).

- 느린 질의 재구성·느린 청크 검색(동기 — 스레드에서 돌아 루프를 막지 않는다)·느린 LLM 조각 사이에 ping 이 나온다.
- ping 을 빼면 이벤트(글 조각·sources·{error, code}·[DONE])의 순서·모양은 그대로다. [DONE] 뒤에는 아무것도 없다.
- 화면이 끊으면(aclose·소비 task 취소) 기다리던 걸음(질의 재구성·LLM 스트림)을 취소하고 남은 task 가 없다.

시간은 CHAT_PING_INTERVAL 을 짧게 갈아 본다. book_chat 을 더미 embedder·indexer 위에서 올리는 픽스처는
test_book_chat_prompt.py 의 것을 그대로 쓴다.
"""
import asyncio

import pytest

from llm_stream_stub import DONE, delta, events, fake_llm
from test_book_chat_prompt import _fake_search, _paper, book_chat  # noqa: F401 — book_chat 은 픽스처

PING = ": ping\n\n"
INTERVAL = 0.02   # 테스트용 ping 간격(초) — 느린 걸음(SLOW)은 이것의 열 배라 ping 이 여럿 나온다
SLOW = 0.2
HISTORY = [{"role": "user", "content": "이 논문은 무엇을 다뤄?"}, {"role": "assistant", "content": "노인 우울을 다룹니다."}]
ANSWER_EVENTS = [
    {"text": "p.3–4 에 나옵니다."},
    {"sources": [{"page_start": 3, "page_end": 4, "text": "표본은 노인 300명이다."}]},
]


@pytest.fixture
def chat(book_chat, monkeypatch):
    """ping 간격을 INTERVAL 로 줄인 book_chat."""
    monkeypatch.setattr(book_chat, "CHAT_PING_INTERVAL", INTERVAL)
    return book_chat


@pytest.fixture
def hit(book_chat):
    return book_chat.SearchHit(chunk_id="c1", book_id="KCI_1", chunk_idx=0, section_idx=0,
                               text="표본은 노인 300명이다.", page_start=3, page_end=4, score=0.9)


def _stream(book_chat, message="이 논문의 대상은?", history=()) -> list[str]:
    async def collect():
        return [c async for c in book_chat.stream_book_chat("KCI_1", message, list(history), book=_paper())]
    return asyncio.run(collect())


def _without_pings(chunks: list[str]) -> list[str]:
    return [c for c in chunks if c != PING]


def _slow_rewrite(monkeypatch, book_chat, seconds=SLOW):
    async def rewrite_chat_query(message, history):
        await asyncio.sleep(seconds)
        return message
    monkeypatch.setattr(book_chat, "rewrite_chat_query", rewrite_chat_query)


def _others() -> list[asyncio.Task]:
    """지금 task 말고 아직 남은 task — 끊은 뒤 백그라운드 걸음이 새지 않았는지 본다."""
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]


def test_the_ping_is_an_sse_comment_every_15_seconds(book_chat):
    # 화면 파서는 ':' 로 시작하는 줄을 버린다 — data: 이벤트가 아니다
    assert book_chat.CHAT_PING == PING
    assert book_chat.CHAT_PING_INTERVAL == 15.0


def test_a_fast_stream_has_no_pings(book_chat, monkeypatch, hit):
    # 기본 간격(15초)에서 바로 끝나는 스트림에는 ping 이 끼지 않는다 — 기존 이벤트 그대로다
    _fake_search(monkeypatch, book_chat, [hit])
    fake_llm(monkeypatch, book_chat, [delta("p.3–4 에 나옵니다."), "data: [DONE]"])

    chunks = _stream(book_chat)

    assert PING not in chunks
    assert chunks[-1] == DONE and events(chunks) == ANSWER_EVENTS


def test_a_slow_query_rewrite_sends_pings_before_the_first_event(chat, monkeypatch, hit):
    _slow_rewrite(monkeypatch, chat)
    _fake_search(monkeypatch, chat, [hit])
    fake_llm(monkeypatch, chat, [delta("p.3–4 에 나옵니다."), "data: [DONE]"])

    chunks = _stream(chat, "그 표본은?", HISTORY)

    assert chunks[0] == PING
    first_event = next(i for i, c in enumerate(chunks) if c != PING)
    assert set(chunks[:first_event]) == {PING} and PING not in chunks[first_event:]
    rest = _without_pings(chunks)
    assert rest[-1] == DONE and rest.count(DONE) == 1 and events(rest) == ANSWER_EVENTS


def test_the_chunk_search_stays_on_the_event_loop(chat, monkeypatch, hit):
    # 임베딩·Milvus 는 동기지만 스레드로 옮기지 않는다 — 메인 검색과 같은 모델·토크나이저를 다른 스레드에서 동시에 쓰지 않게.
    # 검색은 루프에서 끝까지 돌고, 그 뒤 이벤트 순서는 그대로다
    import threading
    loop_thread: list[str] = []

    def embed_texts(texts, is_query=False):
        loop_thread.append(threading.current_thread().name)
        return [[0.0]], [{}]

    _fake_search(monkeypatch, chat, [hit])
    monkeypatch.setattr(chat, "embed_texts", embed_texts)
    fake_llm(monkeypatch, chat, [delta("p.3–4 에 나옵니다."), "data: [DONE]"])

    chunks = _stream(chat)

    assert loop_thread == [threading.main_thread().name]
    rest = _without_pings(chunks)
    assert rest[-1] == DONE and rest.count(DONE) == 1 and events(rest) == ANSWER_EVENTS


def test_a_failing_search_keeps_its_error_event_last(chat, monkeypatch):
    # 실패 이벤트({error, code})도 그대로 [DONE] 바로 앞, 마지막 이벤트다
    def embed_texts(texts, is_query=False):
        raise ConnectionError("Milvus 연결 실패")

    monkeypatch.setattr(chat, "embed_texts", embed_texts)
    payloads = fake_llm(monkeypatch, chat, [delta("x"), "data: [DONE]"])

    chunks = _stream(chat)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1 and chunks[-2] != PING
    assert events(_without_pings(chunks)) ==[{"error": chat.CHAT_RETRIEVAL_ERROR, "code": "retrieval_failed"}]
    assert payloads == []   # LLM 은 부르지 않는다


def test_a_slow_llm_sends_pings_between_text_chunks(chat, monkeypatch, hit):
    async def sse_deltas(resp):
        yield "p.3–4 에 "
        await asyncio.sleep(SLOW)
        yield "나옵니다."

    _fake_search(monkeypatch, chat, [hit])
    fake_llm(monkeypatch, chat, [])
    monkeypatch.setattr(chat, "sse_deltas", sse_deltas)

    chunks = _stream(chat)

    first, second = chunks.index('data: {"text": "p.3–4 에 "}\n\n'), chunks.index('data: {"text": "나옵니다."}\n\n')
    assert PING in chunks[first + 1:second]
    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(_without_pings(chunks)) == [
        {"text": "p.3–4 에 "}, {"text": "나옵니다."},
        {"sources": [{"page_start": 3, "page_end": 4, "text": "표본은 노인 300명이다."}]},
    ]


def _hanging_rewrite(monkeypatch, book_chat) -> dict:
    """끝나지 않는 질의 재구성 — 취소되면 seen["cancelled"] 를 남긴다."""
    seen = {}

    async def rewrite_chat_query(message, history):
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            seen["cancelled"] = True
            raise
        return message

    monkeypatch.setattr(book_chat, "rewrite_chat_query", rewrite_chat_query)
    return seen


def test_closing_the_stream_cancels_the_waiting_step(chat, monkeypatch):
    # 화면이 끊어 StreamingResponse 가 제너레이터를 닫으면(aclose) — ping 을 내고 멈춰 있던 동안 돌던 질의 재구성을 취소한다
    seen = _hanging_rewrite(monkeypatch, chat)

    async def main():
        stream = chat.stream_book_chat("KCI_1", "그 표본은?", HISTORY, book=_paper())
        first = await stream.__anext__()
        await stream.aclose()
        return first, _others()

    first, others = asyncio.run(main())

    assert first == PING
    assert seen == {"cancelled": True} and others == []


def test_cancelling_the_consumer_cancels_the_waiting_step(chat, monkeypatch):
    # 스트림을 읽던 task 가 취소되면(기다리던 중 CancelledError) — 기다리던 걸음도 취소해 남기지 않는다
    seen = _hanging_rewrite(monkeypatch, chat)

    async def main():
        got = []

        async def consume():
            async for chunk in chat.stream_book_chat("KCI_1", "그 표본은?", HISTORY, book=_paper()):
                got.append(chunk)

        consumer = asyncio.create_task(consume())
        while not got:
            await asyncio.sleep(INTERVAL / 2)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        return got, _others()

    got, others = asyncio.run(main())

    assert got and set(got) == {PING}
    assert seen == {"cancelled": True} and others == []


def test_closing_the_stream_mid_answer_closes_the_llm_stream(chat, monkeypatch, hit):
    # 글 조각 사이에서 끊어도 LLM 스트림 읽기를 취소해 닫는다 — 백그라운드에서 끝까지 받지 않는다
    closed = {}

    async def sse_deltas(resp):
        try:
            yield "p.3–4 에 "
            await asyncio.sleep(3600)
            yield "나옵니다."
        finally:
            closed["deltas"] = True

    _fake_search(monkeypatch, chat, [hit])
    fake_llm(monkeypatch, chat, [])
    monkeypatch.setattr(chat, "sse_deltas", sse_deltas)

    async def main():
        stream = chat.stream_book_chat("KCI_1", "이 논문의 대상은?", [], book=_paper())
        got = [await stream.__anext__(), await stream.__anext__()]
        await stream.aclose()
        return got, _others()

    got, others = asyncio.run(main())

    assert got == ['data: {"text": "p.3–4 에 "}\n\n', PING]
    assert closed == {"deltas": True} and others == []
