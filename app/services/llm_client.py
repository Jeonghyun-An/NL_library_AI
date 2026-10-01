"""
llm_client.py — LLM chat 어댑터 (OpenAI 호환 / Ollama 네이티브 겸용)

  LLM_API_STYLE=openai → {LLM_BASE_URL}/chat/completions     (vLLM 등, 기본)
  LLM_API_STYLE=ollama → {LLM_BASE_URL의 /v1 제거}/api/chat   (think 제어용 네이티브)

Ollama 의 OpenAI 호환(/v1) 엔드포인트는 think 파라미터를 무시하므로, thinking 을
끄려면 반드시 네이티브 /api/chat + think:false 를 써야 한다.
호출부는 chat() / chat_full() / chat_stream() 만 사용하고, 스타일 분기는 여기서 처리한다.

  chat_full() → LLMResult(content, finish_reason). 잘림(finish_reason == "length")을
  호출부가 처리해야 할 때 쓴다. chat() 은 그 content 만 돌려준다.
  비스트리밍 호출은 연결 오류·타임아웃·연결 끊김·429·5xx 를 LLM_RETRY_ATTEMPTS(첫 시도
  포함)까지 LLM_RETRY_BACKOFF_SECONDS("2,8" — 모자라면 마지막 값 반복) 간격으로 다시
  보낸다. 그 밖의 4xx 는 요청 자체 문제라 바로 올린다. chat_stream() 은 재시도하지 않는다.

  think 필드 처리:
    LLM_THINK is None  → think 필드 자체를 안 보냄 (gemma3 등 비-thinking 모델 안전)
    LLM_THINK True/False → 그 값 전송 (gemma4 요약은 false 로 추론 비용 제거)
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)

# 다시 보내면 나을 수 있는 실패 — 연결 거부·타임아웃(연결·읽기·쓰기·풀)·응답 도중 끊김.
_RETRYABLE_ERRORS = (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError)


@dataclass
class LLMResult:
    content: str
    finish_reason: str | None   # openai: choices[0].finish_reason / ollama: done_reason (없으면 None)


def _is_retryable_status(code: int) -> bool:
    """429(과부하)·5xx(서버 쪽 일시 문제)만 재시도 — 그 밖의 4xx 는 다시 보내도 같다."""
    return code == 429 or 500 <= code < 600


def _backoff_delay(schedule: str, retry_no: int) -> float:
    """retry_no 번째 재시도 전 대기(초). "2,8" → 1번째 2초, 2번째부터 8초(마지막 값 반복).

    숫자가 아닌 칸은 건너뛰고, 쓸 값이 하나도 없으면 기다리지 않는다.
    """
    delays: list[float] = []
    for tok in str(schedule).split(","):
        try:
            delays.append(max(0.0, float(tok)))
        except ValueError:
            continue
    if not delays:
        return 0.0
    return delays[min(retry_no, len(delays)) - 1]


def _ollama_root(base_url: str) -> str:
    """OpenAI 호환 base( .../v1 )에서 Ollama 네이티브 루트를 도출."""
    b = base_url.rstrip("/")
    if b.endswith("/v1"):
        b = b[:-3].rstrip("/")   # http://ollama:11434/v1 → http://ollama:11434
    return b


def _ollama_body(messages: list[dict], params: dict, stream: bool) -> dict:
    cfg = get_settings()
    opts: dict = {"num_ctx": cfg.OLLAMA_NUM_CTX}
    if "temperature" in params:
        opts["temperature"] = params["temperature"]
    if "max_tokens" in params:
        opts["num_predict"] = params["max_tokens"]   # ollama 는 num_predict
    body: dict = {
        "model": cfg.LLM_MODEL,
        "messages": messages,
        "stream": stream,
        "options": opts,
    }
    if cfg.LLM_THINK is not None:                     # None 이면 think 필드 생략
        body["think"] = cfg.LLM_THINK
    return body


async def _request_once(messages: list[dict], params: dict, timeout: float) -> LLMResult:
    """한 번 보내고 응답을 LLMResult 로 바꾼다 (재시도는 chat_full 이 한다)."""
    cfg = get_settings()
    if cfg.LLM_API_STYLE == "ollama":
        url = f"{_ollama_root(cfg.LLM_BASE_URL)}/api/chat"
        body = _ollama_body(messages, params, stream=False)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
        return LLMResult(
            content=((data.get("message") or {}).get("content") or "").strip(),
            finish_reason=data.get("done_reason"),
        )

    # openai 호환 (vLLM 등)
    url = f"{cfg.LLM_BASE_URL}/chat/completions"
    body = {"model": cfg.LLM_MODEL, "messages": messages, **params}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
    choice = data["choices"][0]
    return LLMResult(
        content=(choice["message"]["content"] or "").strip(),
        finish_reason=choice.get("finish_reason"),
    )


async def chat_full(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> LLMResult:
    """비스트리밍 chat 완성 → LLMResult(content, finish_reason). 일시적 실패는 재시도한다."""
    cfg = get_settings()
    params = params or {}
    attempts = max(1, int(cfg.LLM_RETRY_ATTEMPTS))
    attempt = 1
    while True:
        try:
            result = await _request_once(messages, params, timeout)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            log.error(
                f"[llm_client:{cfg.LLM_API_STYLE}] {code} ({attempt}/{attempts}회차) — "
                f"{e.response.text[:400]}"
            )
            if not _is_retryable_status(code) or attempt >= attempts:
                raise
        except _RETRYABLE_ERRORS as e:
            log.warning(
                f"[llm_client:{cfg.LLM_API_STYLE}] {type(e).__name__} ({attempt}/{attempts}회차) — {e}"
            )
            if attempt >= attempts:
                raise
        else:
            if result.finish_reason == "length":
                log.warning(
                    f"[llm_client:{cfg.LLM_API_STYLE}] 응답이 max_tokens 에서 잘렸다 — "
                    f"model={cfg.LLM_MODEL} max_tokens={params.get('max_tokens')}"
                )
            return result
        await asyncio.sleep(_backoff_delay(cfg.LLM_RETRY_BACKOFF_SECONDS, attempt))
        attempt += 1


async def chat(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> str:
    """비스트리밍 chat 완성 → 최종 content 문자열 (= chat_full 의 content)."""
    return (await chat_full(messages, params=params, timeout=timeout)).content


async def chat_stream(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """스트리밍 chat → content 델타 순차 yield.

    검색/대화 SSE 기능용. 국회 1차(요약→DB) 스코프에는 불필요하지만
    스타일 겸용을 위해 함께 제공한다.
    """
    cfg = get_settings()
    params = params or {}

    if cfg.LLM_API_STYLE == "ollama":
        url = f"{_ollama_root(cfg.LLM_BASE_URL)}/api/chat"
        body = _ollama_body(messages, params, stream=True)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():   # ollama = NDJSON
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = (data.get("message") or {}).get("content", "")
                    if delta:
                        yield delta
                    if data.get("done"):
                        return
        return

    # openai 호환 (SSE)
    url = f"{cfg.LLM_BASE_URL}/chat/completions"
    body = {"model": cfg.LLM_MODEL, "messages": messages, "stream": True, **params}
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():        # openai = SSE
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    return
                try:
                    delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    continue
