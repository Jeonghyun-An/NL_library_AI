"""test_stream_book_reason_end.py — 도서 추천 이유 스트림(services/search/pipeline.stream_book_reason)의 끝.

LLM 호출이 실패하면(httpx 연결·읽기 오류, 4xx·5xx 응답 등) [DONE] 앞에 {error} 이벤트를 먼저 보낸다. [DONE] 만 보내면 화면
(frontend/utils/bookAiPick.ts readReasonStream)이 '끝까지 받음'으로 읽어 받다 만 이유를 완성본으로 기록에 저장한다.
정상으로 끝난 스트림에는 {error} 가 없다. 추천 이유(text)가 글 조각 없이(공백뿐 포함) 끝난 빈 답도 같은 {error} 로 끝낸다.

pipeline 은 reranker(torch)·indexer(pymilvus) 를 물고 오므로 공용 대역(pipeline_stub.py)의 pipeline 픽스처로
import 한다 — 미설치 환경에서만 더미를 꽂고, 끝나면 import 전 그대로 되돌린다.
"""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from pipeline_stub import pipeline  # noqa: F401 — 픽스처(테스트 인자 이름으로 쓴다)

DONE = "data: [DONE]\n\n"


def _delta(text: str) -> str:
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]}, ensure_ascii=False)}"


def _fake_llm(monkeypatch, pipeline, lines, *, open_error=None, read_error=None, status=200):
    """LLM 스트리밍 대역 — pipeline.httpx.AsyncClient 를 갈아 lines 를 SSE 줄로 흘려 준다. open_error 면 stream() 을 여는
    자리에서, read_error 면 lines 를 다 흘린 뒤 읽는 자리에서 그 예외를 던진다. status 가 4xx·5xx 면 raise_for_status 가
    httpx 처럼 HTTPStatusError 를 던진다."""

    class _Response:
        def raise_for_status(self):
            request = httpx.Request("POST", "http://vllm.test/v1/chat/completions")
            httpx.Response(status, request=request).raise_for_status()

        async def aiter_lines(self):
            for line in lines:
                yield line
            if read_error is not None:
                raise read_error

    class _Stream:
        async def __aenter__(self):
            if open_error is not None:
                raise open_error
            return _Response()

        async def __aexit__(self, *exc):
            return False

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, **kwargs):
            return _Stream()

    monkeypatch.setattr(pipeline.httpx, "AsyncClient", _Client)


def _run(pipeline, **kwargs) -> list[str]:
    async def collect():
        return [chunk async for chunk in pipeline.stream_book_reason("노인 우울", "B1", ["구절"], **kwargs)]
    return asyncio.run(collect())


def _events(chunks: list[str]) -> list[dict]:
    return [json.loads(c[len("data: "):]) for c in chunks if c != DONE]


def test_a_failed_connection_sends_an_error_event_before_done(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [], open_error=httpx.ConnectError("vLLM 연결 실패"))

    chunks = _run(pipeline)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    events = _events(chunks)
    assert events == [{"error": pipeline.REASON_STREAM_ERROR}]
    assert isinstance(pipeline.REASON_STREAM_ERROR, str) and pipeline.REASON_STREAM_ERROR.strip()


def test_an_error_status_sends_an_error_event_before_done(pipeline, monkeypatch):
    # vLLM 이 503 을 돌려주면 본문은 SSE 가 아닌 오류 JSON 이다 — 상태를 보지 않으면 줄을 다 거르고 [DONE] 만 남는다
    _fake_llm(monkeypatch, pipeline, ['{"object": "error", "message": "Service Unavailable", "code": 503}'], status=503)

    chunks = _run(pipeline)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert _events(chunks) == [{"error": pipeline.REASON_STREAM_ERROR}]


def test_a_read_error_after_some_text_keeps_the_text_then_sends_the_error(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [_delta("#KW: 우울, 노년\n"), _delta("이 책은 노년의 우울을 다루며 " * 3)],
              read_error=httpx.ReadTimeout("읽기 시간 초과"))

    chunks = _run(pipeline)

    assert chunks[-1] == DONE
    events = _events(chunks)
    assert events[0] == {"keywords": ["우울", "노년"]}
    assert "".join(e.get("text", "") for e in events).startswith("이 책은 노년의 우울을")
    # 오류는 받은 글 뒤, [DONE] 바로 앞에 한 번
    assert events[-1] == {"error": pipeline.REASON_STREAM_ERROR}
    assert sum("error" in e for e in events) == 1


def test_marc_keywords_come_first_even_when_the_llm_fails(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [], open_error=httpx.ConnectError("vLLM 연결 실패"))
    book = SimpleNamespace(title="노년", personal_author=None, corporate_author=None, pub_date=None, publisher=None,
                           kdc=None, subject=None, keyword="우울; 노년", summary=None, plot=None)

    events = _events(_run(pipeline, book=book))

    assert events == [{"keywords": ["우울", "노년"]}, {"error": pipeline.REASON_STREAM_ERROR}]


def test_a_finished_stream_has_no_error_event(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [_delta("#KW: 우울\n"), _delta("추천 이유입니다.\n###EFFECT###\n"),
                                      _delta("읽고 난 후입니다."), "data: [DONE]"])

    chunks = _run(pipeline)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    events = _events(chunks)
    assert not any("error" in e for e in events)
    assert {"effect": "읽고 난 후입니다."} in events


def test_an_error_inside_the_stream_sends_an_error_event(pipeline, monkeypatch):
    # vLLM 이 생성 도중 실패하면 HTTP 200 스트림 안에 {"error": {...}} 를 보내고 이어 [DONE] 을 보낸다 — 이것도 실패다
    engine_error = ('data: {"error": {"object": "error", "message": "EngineDeadError", '
                    '"type": "InternalServerError", "code": 500}}')
    _fake_llm(monkeypatch, pipeline, [_delta("#KW: 우울\n"), _delta("이 책은 노년의 우울을 다루며 " * 3), engine_error,
                                      "data: [DONE]"])

    chunks = _run(pipeline)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    events = _events(chunks)
    assert events[-1] == {"error": pipeline.REASON_STREAM_ERROR}
    assert sum("error" in e for e in events) == 1


def test_a_stream_closed_without_done_is_a_failure(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [_delta("#KW: 우울\n"), _delta("이 책은 노년의 우울을 다루며 " * 3)])

    chunks = _run(pipeline)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert _events(chunks)[-1] == {"error": pipeline.REASON_STREAM_ERROR}


def test_the_failure_log_names_the_exception_type_and_the_text_already_sent(pipeline, monkeypatch, caplog):
    # httpx.ReadTimeout 은 str(e) 가 빈 글일 때가 많다 — 예외 종류와 이미 받은 글 길이로 원인·시점을 남긴다
    _fake_llm(monkeypatch, pipeline, [_delta("노인 우울은 ")], read_error=httpx.ReadTimeout(""))

    with caplog.at_level("ERROR", logger=pipeline.log.name):
        _run(pipeline)

    messages = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
    assert len(messages) == 1
    assert "ReadTimeout" in messages[0]
    assert "받은 글 7자" in messages[0]


# LLM 이 글 조각 없이(공백뿐 포함) [DONE] 으로 끝난 빈 답 — 호출은 성공했지만 [DONE] 만 보내면 화면이 빈 이유를 끝까지 받은
# 답으로 읽는다. 같은 {error: REASON_STREAM_ERROR} 로 끝낸다(DeepRead 대화의 empty_answer 와 같은 판별). 화면이 보이는 것은
# 추천 이유(text)뿐이라, 키워드 줄만 오거나 효과(effect)만 와도 빈 답이다
def _book_with_marc_keywords():
    return SimpleNamespace(title="노년", personal_author=None, corporate_author=None, pub_date=None, publisher=None,
                           kdc=None, subject=None, keyword="우울; 노년", summary=None, plot=None)


@pytest.mark.parametrize("lines", [
    pytest.param(["data: [DONE]"], id="no-text"),
    pytest.param([_delta(" "), _delta("\n\n"), "data: [DONE]"], id="whitespace-only"),
])
def test_an_empty_answer_ends_with_the_error_event(pipeline, monkeypatch, caplog, lines):
    _fake_llm(monkeypatch, pipeline, lines)

    with caplog.at_level("WARNING", logger=pipeline.log.name):
        chunks = _run(pipeline)

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    events = _events(chunks)
    assert [e for e in events if "text" not in e] == [{"error": pipeline.REASON_STREAM_ERROR}]
    # 연결·응답 실패(ERROR)가 아니라 빈 답 경고로 남긴다
    records = [r for r in caplog.records if r.name == pipeline.log.name]
    assert [r.levelname for r in records] == ["WARNING"] and "빈 답" in records[0].getMessage()


def test_a_keyword_line_without_a_reason_is_an_empty_answer(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [_delta("#KW: 우울, 노년\n"), _delta("\n"), "data: [DONE]"])

    events = _events(_run(pipeline))

    assert [e for e in events if "text" not in e] == [{"keywords": ["우울", "노년"]},
                                                       {"error": pipeline.REASON_STREAM_ERROR}]


def test_marc_keywords_with_an_empty_answer_still_end_with_the_error(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, ["data: [DONE]"])

    events = _events(_run(pipeline, book=_book_with_marc_keywords()))

    assert events == [{"keywords": ["우울", "노년"]}, {"error": pipeline.REASON_STREAM_ERROR}]


def test_an_effect_without_a_reason_is_an_empty_answer(pipeline, monkeypatch):
    _fake_llm(monkeypatch, pipeline, [_delta("#KW: 우울\n"), _delta("###EFFECT###\n읽고 난 후입니다."), "data: [DONE]"])

    events = _events(_run(pipeline))

    assert {"effect": "읽고 난 후입니다."} in events
    assert not any(e.get("text", "").strip() for e in events)
    assert events[-1] == {"error": pipeline.REASON_STREAM_ERROR}
    assert sum("error" in e for e in events) == 1
