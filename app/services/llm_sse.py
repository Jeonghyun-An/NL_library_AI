"""llm_sse.py — OpenAI 호환(vLLM) 스트리밍 응답(SSE)에서 글 조각(choices[0].delta.content)만 꺼낸다.

검색·대화 스트림 다섯(search/paper_summary 의 세 스트림·chat/book_chat.stream_book_chat·search/pipeline.stream_book_reason)이
같이 쓴다. 이 스트림들은 LLM 실패를 화면에 {error} 이벤트로 알리고, 화면은 끝까지 받은 글만 캐시·검색 기록·대화에 저장한다.
그래서 '끝까지 받았다'를 여기서 엄격하게 본다:

- vLLM 은 생성 도중 실패하면(엔진 오류 등) HTTP 200 스트림 안에 data: {"error": {...}}(옛 판은 {"object": "error", ...}) 를
  보내고 이어 [DONE] 을 보낸다 — 이것을 LLMStreamError 로 올린다. 전에는 choices 가 없어 난 KeyError 를 삼키고 [DONE] 에서
  정상으로 끝나, 받다 만 글이나 빈 글이 완성본으로 저장됐다.
- [DONE] 을 보지 못하고 줄이 끝나도(위쪽이 깨끗이 닫음) LLMStreamError 다.
- 그 밖에 읽지 못하는 줄(JSON 아님·역할만 있는 첫 조각·content null·choices 가 빈 usage 조각)은 건너뛴다.

연구 어시스턴트의 llm_client.chat_stream 은 쓰지 않는다 — 그쪽은 잘린 글을 parse·check 로 잡는다(research_work/generate.py).
"""
import json
from typing import AsyncIterator


class LLMStreamError(RuntimeError):
    """LLM 스트림이 끝까지 오지 않았다(스트림 안 오류 줄·[DONE] 없이 끝남). 스트림들의 except Exception 분기로 간다."""


def _error_message(chunk: dict) -> str:
    err = chunk.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err)
    if err is not None:
        return str(err)
    return str(chunk.get("message") or chunk)


async def sse_deltas(resp) -> AsyncIterator[str]:
    """resp.aiter_lines() 의 'data: ' 줄에서 글 조각을 차례로 낸다. [DONE] 에서 끝나고, 스트림 안 오류 줄이나 [DONE] 없는
    끝에서는 LLMStreamError 를 던진다(이미 낸 조각은 그대로다)."""
    async for line in resp.aiter_lines():
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data.strip() == "[DONE]":
            return
        try:
            chunk = json.loads(data)
        except ValueError:
            continue
        if not isinstance(chunk, dict):
            continue
        if "error" in chunk or chunk.get("object") == "error":
            raise LLMStreamError(f"스트림 안 오류: {_error_message(chunk)}")
        try:
            delta = chunk["choices"][0]["delta"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError):
            continue
        if delta:
            yield delta
    raise LLMStreamError("[DONE] 없이 스트림이 끝났다")
