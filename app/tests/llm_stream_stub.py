"""llm_stream_stub.py — LLM(vLLM) 스트리밍 호출을 흉내 내는 테스트 대역.

스트림 생성기(services/search/paper_summary 의 세 스트림·services/chat/book_chat.stream_book_chat)가 부르는
httpx.AsyncClient().stream(...) 을 갈아, 정해 둔 SSE 줄을 흘리거나 여는 자리·읽는 자리에서 오류를 던진다.
test_stream_book_reason_end.py 의 _fake_llm 과 같은 모양이다.

쓰는 곳: test_paper_summary_stream_end.py·test_book_chat_stream_end.py.
"""
import json

import httpx

DONE = "data: [DONE]\n\n"


def delta(text: str) -> str:
    """vLLM 이 흘리는 한 줄 — choices[0].delta.content 에 text."""
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]}, ensure_ascii=False)}"


def fake_llm(monkeypatch, module, lines, *, open_error=None, read_error=None, status=200):
    """module.httpx.AsyncClient 를 갈아 lines 를 SSE 줄로 흘려 준다. open_error 면 stream() 을 여는 자리에서,
    read_error 면 lines 를 다 흘린 뒤 읽는 자리에서 그 예외를 던진다. status 가 4xx·5xx 면 raise_for_status 가 httpx
    처럼 HTTPStatusError 를 던진다. stream() 이 받은 payload 목록을 돌려준다."""
    payloads = []

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
            payloads.append(kwargs.get("json"))
            return _Stream()

    monkeypatch.setattr(module.httpx, "AsyncClient", _Client)
    return payloads


def events(chunks: list[str]) -> list[dict]:
    """[DONE] 을 뺀 data: 이벤트들을 JSON 으로."""
    return [json.loads(c[len("data: "):]) for c in chunks if c != DONE]
