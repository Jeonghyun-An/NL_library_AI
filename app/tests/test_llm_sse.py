"""test_llm_sse.py — OpenAI 호환(vLLM) 스트리밍 응답에서 글 조각만 꺼내는 도우미(services/llm_sse.sse_deltas).

검색·대화 스트림 다섯(paper_summary 셋·book_chat·pipeline.stream_book_reason)이 같이 쓴다. vLLM 은 생성 도중 실패하면
(엔진 오류 등) HTTP 200 스트림 안에 data: {"error": {...}}(옛 판은 {"object": "error", ...}) 를 보내고 이어 [DONE] 을
보낸다 — 전에는 choices 가 없어 난 KeyError 를 삼키고 [DONE] 에서 정상으로 끝나, 받다 만 글이 완성본으로 저장됐다.
[DONE] 을 보지 못하고 줄이 끝나도 실패다. 그 밖에 읽지 못하는 줄은 건너뛴다.
"""
import asyncio
import json

import pytest

from services.llm_sse import LLMStreamError, sse_deltas


def _delta(text):
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]}, ensure_ascii=False)}"


class _Resp:
    def __init__(self, lines):
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


def _read(lines):
    """(받은 조각들, 던진 예외 또는 None)."""
    got: list[str] = []

    async def run():
        async for d in sse_deltas(_Resp(lines)):
            got.append(d)

    try:
        asyncio.run(run())
    except LLMStreamError as e:
        return got, e
    return got, None


def test_yields_content_deltas_until_done():
    got, err = _read([_delta("가"), "", ": keep-alive", _delta("나"), "data: [DONE]", _delta("뒤")])
    assert got == ["가", "나"] and err is None


def test_skips_lines_it_cannot_read():
    # 역할만 있는 첫 조각·content null·choices 가 빈 usage 조각·JSON 아닌 줄은 건너뛴다
    lines = [
        'data: {"choices": [{"delta": {"role": "assistant"}}]}',
        'data: {"choices": [{"delta": {"content": null}}]}',
        'data: {"choices": [], "usage": {"total_tokens": 9}}',
        "data: 이건 JSON 이 아니다",
        _delta("글"),
        "data: [DONE]",
    ]
    got, err = _read(lines)
    assert got == ["글"] and err is None


@pytest.mark.parametrize("line", [
    'data: {"error": {"object": "error", "message": "EngineDeadError", "type": "InternalServerError", "code": 500}}',
    'data: {"object": "error", "message": "EngineDeadError", "type": "InternalServerError", "code": 500}',
], ids=["wrapped", "bare"])
def test_an_error_inside_the_stream_raises_after_the_text_so_far(line):
    got, err = _read([_delta("부분 "), line, "data: [DONE]"])
    assert got == ["부분 "]
    assert isinstance(err, LLMStreamError)
    assert "EngineDeadError" in str(err)


def test_a_stream_that_ends_without_done_raises():
    got, err = _read([_delta("부분 ")])
    assert got == ["부분 "]
    assert isinstance(err, LLMStreamError)


def test_an_empty_stream_without_done_raises():
    got, err = _read([])
    assert got == [] and isinstance(err, LLMStreamError)


def test_the_error_is_a_runtime_error():
    # 스트림들의 except Exception 분기로 간다
    assert issubclass(LLMStreamError, RuntimeError)
