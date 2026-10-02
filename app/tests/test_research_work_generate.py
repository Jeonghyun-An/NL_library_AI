"""services/research_work — 생성의 모델 라우팅(routing)과 재시도·넘김 공통 규칙(generate).

LLM 은 부르지 않는다. run_generation 에 넘기는 chat_fn 을 대본대로 답하는 가짜로 바꿔(모델 이름마다
응답이나 전송 실패를 차례로 꺼낸다) 호출 순서·모델·시도 기록을 확인한다(spec §6-3).
"""
import asyncio
import json

import httpx
import pytest

from models.research_work import GEN_KINDS
from services.llm_client import LLMResult
from services.research_work import routing
from services.research_work.generate import (
    CALL_TIMEOUT, MAX_CALLS, Executor, GenerationResult, run_generation,
)
from services.research_work.routing import GEMMA, QWEN, WORK_MODEL_ROUTES, endpoint, other

OK = '{"ok": true}'
NOT_JSON = "JSON 이 아닌 답"
THIN = '{"ok": false}'
MESSAGES = [{"role": "system", "content": "시스템"}, {"role": "user", "content": "사용자"}]
PARAMS = {"max_tokens": 50, "temperature": 0.2}


@pytest.fixture
def cfg(monkeypatch):
    settings = routing.get_settings()
    monkeypatch.setattr(settings, "VLM_BASE_URL", "http://qwen.test/v1")
    monkeypatch.setattr(settings, "VLM_MODEL", "qwen-test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://gemma.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    return settings


def _parse(raw: str) -> dict | None:
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _executor(kind: str = "concepts", built: list | None = None) -> Executor:
    def _build(inp: dict) -> tuple[list[dict], dict]:
        if built is not None:
            built.append(inp)
        return MESSAGES, dict(PARAMS)

    return Executor(
        kind=kind, build=_build, parse=_parse,
        check=lambda out: out.get("ok") is True,
        empty=lambda inp: {"empty": True, "q": inp["q"]},
    )


class _ScriptedChat:
    """모델 이름마다 응답 문자열이나 예외를 차례로 꺼낸다. calls 에 호출 인자를 쌓는다."""

    def __init__(self, script: dict[str, list]):
        self.script = {model: list(items) for model, items in script.items()}
        self.calls: list[dict] = []

    async def __call__(self, messages, *, params=None, timeout=120.0, base_url=None, model=None):
        self.calls.append({"messages": messages, "params": params, "timeout": timeout,
                           "base_url": base_url, "model": model})
        item = self.script[model].pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(content=item, finish_reason="stop")

    @property
    def models(self) -> list[str]:
        return [c["model"] for c in self.calls]


def _run(chat: _ScriptedChat, *, kind: str = "concepts", built: list | None = None) -> GenerationResult:
    return asyncio.run(run_generation(_executor(kind, built), {"q": "질문"}, chat_fn=chat))


def _outcomes(result: GenerationResult) -> list[str]:
    return [a["outcome"] for a in result.attempts]


def _unavailable() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://gemma.test/v1/chat/completions")
    return httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))


class TestRouting:
    def test_every_generation_kind_has_a_route(self):
        assert set(WORK_MODEL_ROUTES) == set(GEN_KINDS)

    def test_reading_side_goes_to_qwen_and_writing_side_to_gemma(self):
        assert {k for k, v in WORK_MODEL_ROUTES.items() if v == QWEN} == {
            "concepts", "topic_card", "refine", "facet",
        }
        assert {k for k, v in WORK_MODEL_ROUTES.items() if v == GEMMA} == {
            "outline", "section", "paragraph",
        }

    def test_endpoint_reads_settings_at_call_time(self, cfg):
        assert endpoint(QWEN) == ("http://qwen.test/v1", "qwen-test")
        assert endpoint(GEMMA) == ("http://gemma.test/v1", "gemma-test")

    def test_other_is_the_fallback_model(self):
        assert other(QWEN) == GEMMA and other(GEMMA) == QWEN

    @pytest.mark.parametrize("fn", [endpoint, other])
    def test_unknown_name_is_rejected(self, fn):
        with pytest.raises(ValueError):
            fn("llama")


class TestRunGeneration:
    def test_limits(self):
        assert (CALL_TIMEOUT, MAX_CALLS) == (300.0, 3)

    def test_first_good_answer_is_the_result(self, cfg):
        chat = _ScriptedChat({"qwen-test": [OK]})

        result = _run(chat)

        assert result == GenerationResult(
            output={"ok": True}, model="qwen-test",
            attempts=[{"model": "qwen-test", "outcome": "ok"}],
        )
        (call,) = chat.calls
        assert call == {"messages": MESSAGES, "params": PARAMS, "timeout": CALL_TIMEOUT,
                        "base_url": "http://qwen.test/v1", "model": "qwen-test"}

    def test_unreadable_answer_asks_the_same_model_once_more(self, cfg):
        chat = _ScriptedChat({"qwen-test": [NOT_JSON, OK]})

        result = _run(chat)

        assert chat.models == ["qwen-test", "qwen-test"]
        assert _outcomes(result) == ["parse", "ok"] and result.model == "qwen-test"

    def test_two_content_failures_hand_over_to_the_other_model(self, cfg):
        built: list = []
        chat = _ScriptedChat({"qwen-test": [NOT_JSON, THIN], "gemma-test": [OK]})

        result = _run(chat, built=built)

        assert chat.models == ["qwen-test", "qwen-test", "gemma-test"]
        assert _outcomes(result) == ["parse", "check", "ok"]
        assert result.output == {"ok": True} and result.model == "gemma-test"
        assert chat.calls[2]["base_url"] == "http://gemma.test/v1"
        # 입력은 한 번만 만들고 세 호출이 같은 메시지를 보낸다
        assert len(built) == 1 and all(c["messages"] is MESSAGES for c in chat.calls)

    def test_transport_failure_hands_over_at_once(self, cfg):
        chat = _ScriptedChat({"qwen-test": [httpx.ConnectError("연결 거부")], "gemma-test": [OK]})

        result = _run(chat)

        assert chat.models == ["qwen-test", "gemma-test"]
        assert result.attempts == [
            {"model": "qwen-test", "outcome": "transport", "error": "ConnectError: 연결 거부"},
            {"model": "gemma-test", "outcome": "ok"},
        ]
        assert result.model == "gemma-test"

    def test_transport_failure_after_a_content_failure_hands_over(self, cfg):
        chat = _ScriptedChat({"qwen-test": [NOT_JSON, httpx.ReadTimeout("읽기 시간 초과")],
                              "gemma-test": [OK]})

        result = _run(chat)

        assert chat.models == ["qwen-test", "qwen-test", "gemma-test"]
        assert _outcomes(result) == ["parse", "transport", "ok"]

    def test_three_failures_give_the_empty_result(self, cfg):
        chat = _ScriptedChat({"qwen-test": [NOT_JSON, NOT_JSON], "gemma-test": [THIN]})

        result = _run(chat)

        assert len(chat.calls) == MAX_CALLS
        assert result.output == {"empty": True, "q": "질문"}
        assert result.model is None
        assert _outcomes(result) == ["parse", "parse", "check"]

    def test_the_other_model_gets_one_call_only(self, cfg):
        chat = _ScriptedChat({"qwen-test": [httpx.ConnectError("거부")], "gemma-test": [NOT_JSON, OK]})

        result = _run(chat)

        assert chat.models == ["qwen-test", "gemma-test"]
        assert result.output == {"empty": True, "q": "질문"} and result.model is None
        assert _outcomes(result) == ["transport", "parse"]

    def test_both_endpoints_down_give_the_empty_result(self, cfg):
        chat = _ScriptedChat({"qwen-test": [httpx.ConnectError("거부")], "gemma-test": [_unavailable()]})

        result = _run(chat)

        assert _outcomes(result) == ["transport", "transport"]
        assert result.attempts[1]["error"].startswith("HTTPStatusError: ")
        assert result.model is None

    def test_gemma_routed_kind_falls_back_to_qwen(self, cfg):
        chat = _ScriptedChat({"gemma-test": [httpx.ConnectError("거부")], "qwen-test": [OK]})

        result = _run(chat, kind="outline")

        assert chat.models == ["gemma-test", "qwen-test"] and result.model == "qwen-test"

    def test_errors_outside_the_transport_propagate(self, cfg):
        """해석·검사·전송 밖의 오류(코드 결함)는 빈 결과로 덮지 않는다 — 디스패처가 failed 로 닫는다."""
        chat = _ScriptedChat({"qwen-test": [ValueError("코드 결함")]})

        with pytest.raises(ValueError):
            _run(chat)
