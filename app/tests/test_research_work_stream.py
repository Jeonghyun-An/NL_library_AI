"""services/research_work/generate.run_stream_generation — 스트리밍 생성의 재시도·넘김 규칙(06b 계획 정함 11).

LLM 은 부르지 않는다. stream_fn 을 모델 이름마다 대본대로 조각을 내는 가짜 async generator 로 바꾼다 —
대본 한 줄은 조각 문자열·예외·("sleep", 초) 의 목록이다. 첫 조각 전 실패만 다른 모델로 곧바로 넘기고,
첫 조각 뒤 끊김·호출 상한 초과는 broken(내용 실패처럼 세고 on_reset 뒤 다시)인지 본다.
"""
import asyncio

import httpx
import pytest

from services.research_work import generate, routing
from services.research_work.generate import Executor, GenerationResult, run_stream_generation

MESSAGES = [{"role": "user", "content": "절을 써라"}]
PARAMS = {"max_tokens": 50}
GOOD = ["가족 지지는 ", "우울을 낮춘다 [E1]."]


@pytest.fixture
def cfg(monkeypatch):
    settings = routing.get_settings()
    monkeypatch.setattr(settings, "VLM_BASE_URL", "http://qwen.test/v1")
    monkeypatch.setattr(settings, "VLM_MODEL", "qwen-test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://gemma.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    return settings


class _Streamer:
    """모델 이름마다 대본 한 줄(조각·예외·("sleep", 초))을 차례로 꺼내 흘린다. 닫힌 스트림 수를 센다."""

    def __init__(self, script: dict[str, list[list]]):
        self.script = {model: list(lines) for model, lines in script.items()}
        self.calls: list[dict] = []
        self.closed = 0
        self.closed_before: list[int] = []      # 호출마다 그 앞에서 닫힌 스트림 수

    async def __call__(self, messages, *, params=None, timeout=120.0, base_url=None, model=None):
        self.calls.append({"messages": messages, "params": params, "timeout": timeout,
                           "base_url": base_url, "model": model})
        self.closed_before.append(self.closed)
        line = self.script[model].pop(0)
        try:
            for item in line:
                if isinstance(item, BaseException):
                    raise item
                if isinstance(item, tuple):
                    await asyncio.sleep(item[1])
                    continue
                yield item
        finally:
            self.closed += 1

    @property
    def models(self) -> list[str]:
        return [c["model"] for c in self.calls]


class _Screen:
    """on_delta·on_reset 이 받은 것 — 화면이 보는 글의 흐름. slow_first 면 첫 조각을 보내는 데 그만큼 걸린다."""

    def __init__(self, *, slow_first: float = 0.0):
        self.events: list = []
        self.slow_first = slow_first

    async def delta(self, piece: str) -> None:
        self.events.append(piece)
        if self.slow_first and len(self.events) == 1:
            await asyncio.sleep(self.slow_first)

    async def reset(self) -> None:
        self.events.append("<reset>")


def _executor(*, bind=None) -> Executor:
    """원문 그대로를 {"text"} 로 읽고, [E1] 이 있어야 통과한다. 빈 원문은 해석 실패."""
    return Executor(
        kind="section", build=lambda inp: (MESSAGES, dict(PARAMS)),
        parse=lambda raw: {"text": raw} if raw.strip() else None,
        check=lambda out: "[E1]" in out["text"],
        empty=lambda inp: {"text": "", "empty": True},
        stream=True, bind=bind,
    )


def _run(streamer: _Streamer, screen: _Screen, *, executor: Executor | None = None) -> GenerationResult:
    return asyncio.run(run_stream_generation(
        executor or _executor(), {"key": "prior.g1"}, stream_fn=streamer,
        on_delta=screen.delta, on_reset=screen.reset,
    ))


def _outcomes(result: GenerationResult) -> list[str]:
    return [a["outcome"] for a in result.attempts]


class TestStreamGeneration:
    def test_first_good_stream_is_the_result(self, cfg):
        streamer, screen = _Streamer({"gemma-test": [GOOD]}), _Screen()

        result = _run(streamer, screen)

        assert result == GenerationResult(
            output={"text": "가족 지지는 우울을 낮춘다 [E1]."}, model="gemma-test",
            attempts=[{"model": "gemma-test", "outcome": "ok"}])
        assert screen.events == GOOD
        (call,) = streamer.calls
        assert call == {"messages": MESSAGES, "params": PARAMS, "timeout": generate.CALL_TIMEOUT,
                        "base_url": "http://gemma.test/v1", "model": "gemma-test"}

    def test_bind_sees_the_whole_text_before_the_check(self, cfg):
        seen: list = []

        def _bind(output, inp):
            seen.append((output, inp))
            return {"text": output["text"].replace("[E9]", "[E1]")}

        streamer, screen = _Streamer({"gemma-test": [["지지가 크다 [E9]."]]}), _Screen()

        result = _run(streamer, screen, executor=_executor(bind=_bind))

        assert seen == [({"text": "지지가 크다 [E9]."}, {"key": "prior.g1"})]
        assert result.output == {"text": "지지가 크다 [E1]."} and _outcomes(result) == ["ok"]

    def test_a_content_failure_resets_the_screen_and_asks_again(self, cfg):
        streamer = _Streamer({"gemma-test": [["근거 없는 글."], GOOD]})
        screen = _Screen()

        result = _run(streamer, screen)

        assert streamer.models == ["gemma-test", "gemma-test"]
        assert _outcomes(result) == ["check", "ok"]
        assert screen.events == ["근거 없는 글.", "<reset>", *GOOD]

    def test_two_content_failures_hand_over_to_the_other_model(self, cfg):
        streamer = _Streamer({"gemma-test": [[], ["근거 없는 글."]], "qwen-test": [GOOD]})
        screen = _Screen()

        result = _run(streamer, screen)

        assert streamer.models == ["gemma-test", "gemma-test", "qwen-test"]
        assert _outcomes(result) == ["parse", "check", "ok"] and result.model == "qwen-test"
        # 빈 답은 화면에 흘린 글이 없어 지우지 않는다
        assert screen.events == ["근거 없는 글.", "<reset>", *GOOD]

    def test_failure_before_the_first_piece_hands_over_at_once(self, cfg):
        streamer = _Streamer({"gemma-test": [[httpx.ConnectError("연결 거부")]], "qwen-test": [GOOD]})
        screen = _Screen()

        result = _run(streamer, screen)

        assert streamer.models == ["gemma-test", "qwen-test"]
        assert result.attempts == [
            {"model": "gemma-test", "outcome": "transport", "error": "ConnectError: 연결 거부"},
            {"model": "qwen-test", "outcome": "ok"},
        ]
        assert "<reset>" not in screen.events

    def test_a_break_after_the_first_piece_is_a_content_failure(self, cfg):
        streamer = _Streamer({"gemma-test": [["앞부분", httpx.ReadError("끊김")], GOOD]})
        screen = _Screen()

        result = _run(streamer, screen)

        assert streamer.models == ["gemma-test", "gemma-test"]        # 다른 모델로 넘기지 않는다
        assert result.attempts == [
            {"model": "gemma-test", "outcome": "broken", "error": "ReadError: 끊김"},
            {"model": "gemma-test", "outcome": "ok"},
        ]
        assert screen.events == ["앞부분", "<reset>", *GOOD]

    def test_call_limit_before_the_first_piece_hands_over(self, cfg, monkeypatch):
        monkeypatch.setattr(generate, "CALL_TIMEOUT", 0.05)
        streamer = _Streamer({"gemma-test": [[("sleep", 5)]], "qwen-test": [GOOD]})

        result = _run(streamer, _Screen())

        assert streamer.models == ["gemma-test", "qwen-test"]
        assert result.attempts[0] == {"model": "gemma-test", "outcome": "transport",
                                      "error": "호출 상한 0초 초과"}
        assert result.model == "qwen-test"

    def test_call_limit_after_the_first_piece_is_broken_and_the_stream_is_closed(self, cfg, monkeypatch):
        # 화면에 보내는 동안(on_delta) 상한이 걸려도 스트림을 닫고 다시 부른다 — 열어 두면 vLLM 이 계속 만든다
        monkeypatch.setattr(generate, "CALL_TIMEOUT", 0.05)
        streamer = _Streamer({"gemma-test": [["앞부분", "뒷부분"], ["다시 [E1]."]]})
        screen = _Screen(slow_first=0.2)

        result = _run(streamer, screen)

        assert _outcomes(result) == ["broken", "ok"]
        assert result.attempts[0]["error"] == "호출 상한 0초 초과"
        assert screen.events == ["앞부분", "<reset>", "다시 [E1]."]
        assert streamer.closed_before == [0, 1]

    def test_three_failures_give_the_empty_result(self, cfg):
        streamer = _Streamer({"gemma-test": [["글."], ["글."]], "qwen-test": [["글."]]})

        result = _run(streamer, _Screen())

        assert len(streamer.calls) == generate.MAX_CALLS
        assert result.output == {"text": "", "empty": True} and result.model is None
        assert _outcomes(result) == ["check", "check", "check"]

    def test_a_failure_after_the_hand_over_ends_the_generation(self, cfg):
        streamer = _Streamer({"gemma-test": [[httpx.ConnectError("거부")]],
                              "qwen-test": [[_unavailable()]]})

        result = _run(streamer, _Screen())

        assert _outcomes(result) == ["transport", "transport"] and result.model is None
        assert result.attempts[1]["error"].startswith("HTTPStatusError: ")

    def test_errors_outside_the_transport_propagate(self, cfg):
        streamer = _Streamer({"gemma-test": [["앞부분", ValueError("코드 결함")]]})

        with pytest.raises(ValueError):
            _run(streamer, _Screen())

    def test_the_outer_deadline_is_not_swallowed(self, cfg):
        # 워커의 GEN_DEADLINE 이 끊으면 CancelledError 가 그대로 올라가 바깥에서 TimeoutError 가 된다
        streamer = _Streamer({"gemma-test": [["앞부분", ("sleep", 5)]]})
        screen = _Screen()

        async def _go():
            async with asyncio.timeout(0.05):
                await run_stream_generation(_executor(), {}, stream_fn=streamer,
                                            on_delta=screen.delta, on_reset=screen.reset)

        with pytest.raises(TimeoutError):
            asyncio.run(_go())
        assert screen.events == ["앞부분"] and len(streamer.calls) == 1


def _unavailable() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://qwen.test/v1/chat/completions")
    return httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))
