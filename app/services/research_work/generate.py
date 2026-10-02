"""generate.py — 생성 1건의 재시도·넘김 공통 규칙 (spec §6-3)

생성 1건 = chat_full 최대 MAX_CALLS(3)회:
  주 모델(WORK_MODEL_ROUTES[kind]) 1회
  → 해석 실패(parse 가 None)나 내용 검사 미달(check 가 False)이면 주 모델 1회 더
  → 전송 실패(chat_fn 이 httpx.HTTPError 를 올림 — chat_full 이 자기 재시도까지 다 쓰고 포기)면 곧바로,
    해석·내용 미달이 두 번이면 다른 모델 1회
  → 그래도 안 되면 executor.empty(input) — 빈 결과로 done(개념 비움 등). 그때 model 은 None.
chat_full 안의 일시적 실패 재시도는 이 횟수에 세지 않는다. 시도마다 attempts 에 남긴다(공개 부록).
그 밖의 예외(코드 결함)는 그대로 올린다 — 디스패처가 생성을 failed 로 닫는다.
"""
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

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


@dataclass
class GenerationResult:
    output: dict
    model: str | None          # 결과를 낸 모델 이름(빈 결과면 None)
    attempts: list[dict]       # [{"model": str, "outcome": "ok"|"parse"|"check"|"transport", "error"?: str}]


ChatFn = Callable[..., Awaitable[LLMResult]]   # chat_full 과 같은 시그니처


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
