"""
llm_client.py — LLM chat 어댑터 (OpenAI 호환 / Ollama 네이티브 겸용)

  LLM_API_STYLE=openai → {LLM_BASE_URL}/chat/completions     (vLLM 등, 기본)
  LLM_API_STYLE=ollama → {LLM_BASE_URL의 /v1 제거}/api/chat   (think 제어용 네이티브)

Ollama 의 OpenAI 호환(/v1) 엔드포인트는 think 파라미터를 무시하므로, thinking 을
끄려면 반드시 네이티브 /api/chat + think:false 를 써야 한다.
호출부는 chat() / chat_stream() 만 사용하고, 스타일 분기는 여기서 처리한다.

  think 필드 처리:
    LLM_THINK is None  → think 필드 자체를 안 보냄 (gemma3 등 비-thinking 모델 안전)
    LLM_THINK True/False → 그 값 전송 (gemma4 요약은 false 로 추론 비용 제거)
"""
import json
import logging
from typing import AsyncGenerator

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)


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


async def chat(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> str:
    """비스트리밍 chat 완성 → 최종 content 문자열."""
    cfg = get_settings()
    params = params or {}
    try:
        if cfg.LLM_API_STYLE == "ollama":
            url = f"{_ollama_root(cfg.LLM_BASE_URL)}/api/chat"
            body = _ollama_body(messages, params, stream=False)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                return (resp.json()["message"]["content"] or "").strip()

        # openai 호환 (vLLM 등)
        url = f"{cfg.LLM_BASE_URL}/chat/completions"
        body = {"model": cfg.LLM_MODEL, "messages": messages, **params}
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        log.error(
            f"[llm_client:{cfg.LLM_API_STYLE}] {e.response.status_code} — "
            f"{e.response.text[:400]}"
        )
        raise


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
