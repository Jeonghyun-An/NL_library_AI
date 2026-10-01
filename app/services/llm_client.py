"""
llm_client.py — LLM chat 어댑터 (OpenAI 호환 / Ollama 네이티브 겸용)

  LLM_API_STYLE=openai → {LLM_BASE_URL}/chat/completions     (vLLM 등, 기본)
  LLM_API_STYLE=ollama → {LLM_BASE_URL의 /v1 제거}/api/chat   (think 제어용 네이티브)

Ollama 의 OpenAI 호환(/v1) 엔드포인트는 think 파라미터를 무시하므로, thinking 을
끄려면 반드시 네이티브 /api/chat + think:false 를 써야 한다.
호출부는 chat() / chat_full() / chat_stream() 만 사용하고, 스타일 분기는 여기서 처리한다.

  chat_full() → LLMResult(content, finish_reason). 잘림(finish_reason == "length")을
  호출부가 처리해야 할 때 쓴다. chat() 은 그 content 만 돌려준다.
  비스트리밍 호출은 네트워크 오류(연결 거부, 서버 재기동·RST 로 읽기/쓰기 도중 끊김)·
  타임아웃·응답 도중 끊김·429·5xx 를 LLM_RETRY_ATTEMPTS(첫 시도 포함)까지
  LLM_RETRY_BACKOFF_SECONDS("2,8" — 모자라면 마지막 값 반복, 칸마다 60초 상한) 간격으로
  다시 보낸다. 그 밖의 4xx 는 요청 자체 문제라 바로 올린다. chat_stream() 은 재시도하지 않는다.
  재시도 전체는 호출자의 timeout 안에서만 한다 — 시도마다 httpx 의 읽기·쓰기·풀 timeout 은
  남은 시간으로 줄고 연결 timeout 은 그중 10초까지이며, 남은 시간이 다음 백오프 + 1초 이하이면
  마지막 예외를 그대로 올린다. 그래서 응답 없이 붙잡는 장애(ReadTimeout)는 예전처럼 timeout
  한 번으로 끝나고, 빠른 실패(연결 거부·리셋·429·5xx)와 10초에서 끊기는 연결 대기(ConnectTimeout —
  vLLM 재기동 중)는 남은 시간 안에서 재시도된다. 더 시도하지 않는 실패는 error 로, 시도 횟수를 다
  썼는지 남은 시간이 모자랐는지를 함께 남긴다.

  think 필드 처리:
    LLM_THINK is None  → think 필드 자체를 안 보냄 (gemma3 등 비-thinking 모델 안전)
    LLM_THINK True/False → 그 값 전송 (gemma4 요약은 false 로 추론 비용 제거)
"""
import asyncio
import functools
import json
import logging
import math
import time
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)

_monotonic = time.monotonic     # 테스트에서 시간을 고정할 수 있게 모듈 이름으로 둔다

# 다시 보내면 나을 수 있는 실패 — 네트워크 오류(연결 거부, 서버 재기동·RST 로 읽기/쓰기 도중
# 끊김: Connect·Read·Write·CloseError)·타임아웃(연결·읽기·쓰기·풀)·응답 도중 끊김.
# TransportError 전체로 넓히지는 않는다 — 주소·프록시·요청 조립 오류는 다시 보내도 같다.
_RETRYABLE_ERRORS = (httpx.NetworkError, httpx.TimeoutException, httpx.RemoteProtocolError)

_MAX_BACKOFF_SECONDS = 60.0     # 백오프 한 칸의 상한 — inf·잘못 쓴 큰 값이 와도 이 이상은 안 기다린다
_MIN_ATTEMPT_SECONDS = 1.0      # 재시도하려면 백오프 말고도 다음 시도에 이만큼은 남아 있어야 한다
# 시도마다 연결 timeout 의 상한. 남은 시간 전부를 주면 연결이 붙지 않는 장애(vLLM 재기동 중)에서 연결
# 시도 한 번이 호출자의 timeout 을 다 써 재시도할 시간이 남지 않는다. LLM 은 같은 docker 망(gemma:8000)에
# 있어 정상이면 연결은 곧바로 붙는다.
_CONNECT_TIMEOUT_SECONDS = 10.0


@dataclass
class LLMResult:
    content: str
    finish_reason: str | None   # openai: choices[0].finish_reason / ollama: done_reason (없으면 None)


def _is_retryable_status(code: int) -> bool:
    """429(과부하)·5xx(서버 쪽 일시 문제)만 재시도 — 그 밖의 4xx 는 다시 보내도 같다."""
    return code == 429 or 500 <= code < 600


@functools.lru_cache(maxsize=16)
def _parse_backoff_schedule(schedule: str) -> tuple[float, ...]:
    """"2,8" → (2.0, 8.0). 칸마다 0 ~ _MAX_BACKOFF_SECONDS 초로 맞춘다.

    숫자가 아닌 칸(nan 포함)은 건너뛰고 상한을 넘는 칸(inf 포함)은 상한으로 줄이는데, 둘 다
    설정이 잘못됐다는 뜻이라 경고를 남긴다. lru_cache 라 같은 설정 문자열은 한 번만 해석하고
    경고한다. 빈 칸(끝 쉼표·빈 설정)은 조용히 건너뛴다.
    """
    delays: list[float] = []
    skipped: list[str] = []
    capped: list[str] = []
    for tok in schedule.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            value = float(tok)
        except ValueError:
            skipped.append(tok)
            continue
        if math.isnan(value):
            skipped.append(tok)
            continue
        if value > _MAX_BACKOFF_SECONDS:
            capped.append(tok)
        delays.append(min(_MAX_BACKOFF_SECONDS, max(0.0, value)))
    problems: list[str] = []
    if skipped:
        problems.append(f"숫자가 아닌 칸 {skipped} 은 건너뜀")
    if capped:
        problems.append(
            f"{_MAX_BACKOFF_SECONDS:g}초를 넘는 칸 {capped} 은 {_MAX_BACKOFF_SECONDS:g}초로 줄임"
        )
    if problems:
        log.warning(f"[llm_client] LLM_RETRY_BACKOFF_SECONDS={schedule!r} — " + ", ".join(problems))
    return tuple(delays)


def _backoff_delay(schedule: str, retry_no: int) -> float:
    """retry_no 번째 재시도 전 대기(초). "2,8" → 1번째 2초, 2번째부터 8초(마지막 값 반복).

    쓸 값이 하나도 없으면 기다리지 않는다. 칸 해석·상한·경고는 _parse_backoff_schedule.
    """
    delays = _parse_backoff_schedule(str(schedule))
    if not delays:
        return 0.0
    return delays[min(retry_no, len(delays)) - 1]


def _retry_delay(attempt: int, attempts: int, schedule: str, deadline: float) -> float | None:
    """attempt 번째 시도가 일시적으로 실패한 뒤 기다릴 초. 더 시도하지 않으면 None.

    None — 시도 횟수를 다 썼거나, 호출자의 timeout(deadline) 안에 다음 시도가 들어가지 못할 때
    (남은 시간 <= 백오프 + _MIN_ATTEMPT_SECONDS). 까닭은 _give_up_reason. 그래서 응답 없이 붙잡는
    장애(ReadTimeout — 읽기 timeout 이 남은 시간 전부다)는 timeout 한 번으로 끝나고, 연결 거부·리셋·
    429·5xx 같은 빠른 실패와 _CONNECT_TIMEOUT_SECONDS 에서 끊기는 연결 대기만 재시도된다.
    """
    if attempt >= attempts:
        return None
    delay = _backoff_delay(schedule, attempt)
    if deadline - _monotonic() <= delay + _MIN_ATTEMPT_SECONDS:
        return None
    return delay


def _give_up_reason(attempt: int, attempts: int) -> str:
    """_retry_delay 가 None 을 낸 까닭 — 로그에 남긴다."""
    return "시도 횟수 소진" if attempt >= attempts else "남은 시간 부족"


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
    """한 번 보내고 응답을 LLMResult 로 바꾼다 (재시도는 chat_full 이 한다).

    timeout 은 이 시도에 남은 시간 — 읽기·쓰기·풀 timeout 으로 쓰고, 연결 timeout 은 그중
    _CONNECT_TIMEOUT_SECONDS 까지만 준다.
    """
    cfg = get_settings()
    client_timeout = httpx.Timeout(timeout, connect=min(_CONNECT_TIMEOUT_SECONDS, timeout))
    if cfg.LLM_API_STYLE == "ollama":
        url = f"{_ollama_root(cfg.LLM_BASE_URL)}/api/chat"
        body = _ollama_body(messages, params, stream=False)
        async with httpx.AsyncClient(timeout=client_timeout) as client:
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
    async with httpx.AsyncClient(timeout=client_timeout) as client:
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
    """비스트리밍 chat 완성 → LLMResult(content, finish_reason). 일시적 실패는 재시도한다.

    재시도 전체가 호출자의 timeout 안에 들어간다 — 시작 시각 + timeout 이 deadline 이고,
    시도마다 httpx 의 읽기·쓰기·풀 timeout 은 남은 시간, 연결 timeout 은 min(_CONNECT_TIMEOUT_SECONDS,
    남은 시간)이다 (더 시도할지는 _retry_delay). 다시 보낼 실패는 경고, 여기서 끝나는 실패(재시도 불가
    4xx, 다시 보낼 실패의 시도 횟수 소진·남은 시간 부족)만 error 로 남긴다.
    """
    cfg = get_settings()
    params = params or {}
    attempts = max(1, int(cfg.LLM_RETRY_ATTEMPTS))
    schedule = cfg.LLM_RETRY_BACKOFF_SECONDS
    deadline = _monotonic() + timeout
    attempt = 1
    while True:
        try:
            result = await _request_once(messages, params, min(timeout, deadline - _monotonic()))
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            retryable = _is_retryable_status(code)
            delay = _retry_delay(attempt, attempts, schedule, deadline) if retryable else None
            why = f", {_give_up_reason(attempt, attempts)}" if retryable and delay is None else ""
            log.log(
                logging.ERROR if delay is None else logging.WARNING,
                f"[llm_client:{cfg.LLM_API_STYLE}] {code} ({attempt}/{attempts}회차{why}) — "
                f"{e.response.text[:400]}",
            )
            if delay is None:
                raise
        except _RETRYABLE_ERRORS as e:
            delay = _retry_delay(attempt, attempts, schedule, deadline)
            why = f", {_give_up_reason(attempt, attempts)}" if delay is None else ""
            log.log(
                logging.ERROR if delay is None else logging.WARNING,
                f"[llm_client:{cfg.LLM_API_STYLE}] {type(e).__name__} ({attempt}/{attempts}회차{why}) — {e}",
            )
            if delay is None:
                raise
        else:
            if result.finish_reason == "length":
                log.warning(
                    f"[llm_client:{cfg.LLM_API_STYLE}] 응답이 max_tokens 에서 잘렸다 — "
                    f"model={cfg.LLM_MODEL} max_tokens={params.get('max_tokens')}"
                )
            return result
        await asyncio.sleep(delay)          # 여기까지 온 것은 다시 보낼 실패뿐 (delay 는 위 except 에서 정해졌다)
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
