"""generate.py — 생성 1건의 재시도·넘김 공통 규칙 (spec §6-3)

생성 1건 = chat_full 최대 MAX_CALLS(3)회:
  주 모델(WORK_MODEL_ROUTES[kind]) 1회
  → 해석 실패(parse 가 None)나 내용 검사 미달(check 가 False)이면 주 모델 1회 더
  → 전송 실패(chat_fn 이 httpx.HTTPError 를 올림 — chat_full 이 자기 재시도까지 다 쓰고 포기)면 곧바로,
    해석·내용 미달이 두 번이면 다른 모델 1회
  → 그래도 안 되면 executor.empty(input) — 빈 결과로 done(개념 비움 등). 그때 model 은 None.
chat_full 안의 일시적 실패 재시도는 이 횟수에 세지 않는다. 시도마다 attempts 에 남긴다(공개 부록).
그 밖의 예외(코드 결함)는 그대로 올린다 — 디스패처가 생성을 failed 로 닫는다.

해석한 결과는 실행기의 bind(06b)가 있으면 검사 전에 입력으로 맞춘다 — 모델이 낸 근거 번호를 cnts_id 로
바꾸고 문단을 마커 검사하는 일처럼 입력이 있어야 하는 정리다. 끝내 못 얻은 빈 결과(empty)에는 하지 않는다.

스트리밍(run_stream_generation, 06b 절 쓰기 — 06b 계획 정함 11)도 같은 '최대 3회·넘김' 규칙이다. 다만
chat_stream 은 첫 조각 전에만 연결 실패·4xx·5xx 를 올리므로, 다른 모델로 곧바로 넘기는 전송 실패는 첫 조각
전의 실패뿐이다. 첫 조각 뒤에 끊기거나 호출 상한을 넘기면 그 시도는 broken — 해석·내용 미달처럼 센다(화면에
흘린 글을 on_reset 으로 지우고 다시 부른다). 호출마다 asyncio.timeout(CALL_TIMEOUT) 을 걸어(httpx timeout 은
조각 사이 간격이라 스트림 전체를 막지 못한다) 최악이 비스트리밍과 같은 MAX_CALLS × (CALL_TIMEOUT + 10)초다.
chat_stream 은 끝난 이유(finish_reason)를 주지 않는다 — 잘린 글은 parse·check 로만 잡는다.
"""
import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any

import httpx

from services.llm_client import LLMResult
from services.research_work.routing import WORK_MODEL_ROUTES, endpoint, other

log = logging.getLogger(__name__)

# 비스트리밍 호출 하나의 timeout(초). llm_client 기본 120초로는 Qwen 이 OCR 로 꽉 찬 구간에서 줄을
# 서다 끊긴다(spec §6-3 Qwen 자리). 호출 하나의 최악은 이 값 + 연결 10초다(llm_client).
CALL_TIMEOUT = 300.0
MAX_CALLS = 3


@dataclass(frozen=True)
class Executor:
    kind: str
    build: Callable[[dict], tuple[list[dict], dict]]   # input → (messages, llm params)
    parse: Callable[[str], dict | None]                # 원문 → output, 못 읽으면 None
    check: Callable[[dict], bool]                      # 내용 검사(예: 개념 2개 이상)
    empty: Callable[[dict], dict]                      # 끝내 못 얻었을 때의 빈 결과(input → output)
    # 06b 의 선택 필드 — 기본값이 06a 동작이다(핵심 개념 실행기는 is_empty 만 쓴다)
    bind: Callable[[dict, dict], dict] | None = None   # (output, input) → output: 해석 뒤·검사 전에 입력으로 맞춘다
    stream: bool = False                               # True 면 워커가 run_stream_generation 으로 돌린다
    apply: Callable[[Any, Any, dict], Awaitable[dict]] | None = None   # (db, gen, output) → 이벤트 result. 커밋 금지
    is_empty: Callable[[dict], bool] | None = None     # done 인데 빈 결과인가 — 다시 부르기(retry)를 허용한다


@dataclass
class GenerationResult:
    output: dict
    model: str | None          # 결과를 낸 모델 이름(빈 결과면 None)
    attempts: list[dict]       # [{"model": str, "outcome": "ok"|"parse"|"check"|"transport"|"broken", "error"?: str}]


ChatFn = Callable[..., Awaitable[LLMResult]]   # chat_full 과 같은 시그니처
StreamFn = Callable[..., AsyncIterator[str]]   # chat_stream 과 같은 시그니처


async def run_generation(executor: Executor, input: dict, *, chat_fn: ChatFn) -> GenerationResult:
    messages, params = executor.build(input)
    route = WORK_MODEL_ROUTES[executor.kind]
    switched = False
    content_failures = 0
    attempts: list[dict] = []
    for _ in range(MAX_CALLS):
        base_url, model = endpoint(route)
        try:
            reply = await chat_fn(messages, params=params, timeout=CALL_TIMEOUT,
                                  base_url=base_url, model=model)
        except httpx.HTTPError as e:
            error = f"{type(e).__name__}: {e}"[:300]
            log.warning("[research_work] %s 전송 실패 model=%s — %s", executor.kind, model, error)
            attempts.append({"model": model, "outcome": "transport", "error": error})
            if switched:
                break
            route, switched = other(route), True
            continue
        output = executor.parse(reply.content)
        if output is not None and executor.bind is not None:
            output = executor.bind(output, input)
        if output is not None and executor.check(output):
            attempts.append({"model": model, "outcome": "ok"})
            return GenerationResult(output=output, model=model, attempts=attempts)
        outcome = "parse" if output is None else "check"
        # 진단용 원문 앞부분과 끝난 이유(length 면 잘림)는 로그에만 남긴다 — attempts 는 공개 부록에 실린다
        log.warning("[research_work] %s %s 실패 model=%s finish=%s 원문=%r", executor.kind, outcome, model,
                    reply.finish_reason, (reply.content or "")[:200])
        attempts.append({"model": model, "outcome": outcome})
        if switched:
            break
        content_failures += 1
        if content_failures >= 2:
            route, switched = other(route), True
    return GenerationResult(output=executor.empty(input), model=None, attempts=attempts)


async def run_stream_generation(executor: Executor, input: dict, *, stream_fn: StreamFn,
                                on_delta: Callable[[str], Awaitable[None]],
                                on_reset: Callable[[], Awaitable[None]]) -> GenerationResult:
    """스트리밍 생성 1건. 조각마다 on_delta, 흘린 글을 버리고 다시 부르기 직전에 on_reset 을 부른다.

    attempts 의 outcome 은 "ok"|"parse"|"check"|"transport"|"broken". 바깥 데드라인(워커의 GEN_DEADLINE)이
    끊으면 CancelledError 가 그대로 올라간다 — 여기서 잡지 않는다.
    """
    messages, params = executor.build(input)
    route = WORK_MODEL_ROUTES[executor.kind]
    switched = False
    content_failures = 0
    streamed = False                 # 앞 시도가 화면에 글을 흘렸다 — 다시 부르기 전에 지운다
    attempts: list[dict] = []
    for _ in range(MAX_CALLS):
        if streamed:
            await on_reset()
            streamed = False
        base_url, model = endpoint(route)
        parts: list[str] = []
        error: str | None = None
        call_deadline = asyncio.timeout(CALL_TIMEOUT)
        try:
            # 끊긴 스트림은 다음 호출 전에 닫는다 — 열어 두면 vLLM 이 버린 답을 계속 만든다
            async with call_deadline, aclosing(stream_fn(
                    messages, params=params, timeout=CALL_TIMEOUT, base_url=base_url, model=model,
            )) as stream:
                async for piece in stream:
                    parts.append(piece)
                    streamed = True
                    await on_delta(piece)
        except httpx.HTTPError as e:
            error = f"{type(e).__name__}: {e}"[:300]
        except TimeoutError:
            if not call_deadline.expired():
                raise
            error = f"호출 상한 {CALL_TIMEOUT:.0f}초 초과"
        if error is not None and not parts:
            # 첫 조각 전 — 연결 실패·4xx·5xx·대기열에서 상한 초과. 비스트리밍처럼 곧바로 다른 모델로
            log.warning("[research_work] %s 전송 실패 model=%s — %s", executor.kind, model, error)
            attempts.append({"model": model, "outcome": "transport", "error": error})
            if switched:
                break
            route, switched = other(route), True
            continue
        raw = "".join(parts)
        if error is not None:
            log.warning("[research_work] %s 스트림 끊김 model=%s %d자 — %s", executor.kind, model,
                        len(raw), error)
            attempts.append({"model": model, "outcome": "broken", "error": error})
        else:
            output = executor.parse(raw)
            if output is not None and executor.bind is not None:
                output = executor.bind(output, input)
            if output is not None and executor.check(output):
                attempts.append({"model": model, "outcome": "ok"})
                return GenerationResult(output=output, model=model, attempts=attempts)
            outcome = "parse" if output is None else "check"
            log.warning("[research_work] %s %s 실패 model=%s 원문=%r", executor.kind, outcome, model,
                        raw[:200])
            attempts.append({"model": model, "outcome": outcome})
        if switched:
            break
        content_failures += 1
        if content_failures >= 2:
            route, switched = other(route), True
    return GenerationResult(output=executor.empty(input), model=None, attempts=attempts)
