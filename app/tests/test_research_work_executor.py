"""services/research_work — 06b 의 생성 틀 확장: 실행기 선택 필드(bind·stream·apply·is_empty)·결과 적용 위임·상수.

LLM 은 부르지 않는다. run_generation 에 넘기는 chat_fn 은 모델 이름마다 대본을 꺼내는 가짜다
(test_research_work_generate 와 같은 방식). 결과 적용은 SQLite 대역(history_sqlite)에서 실제 SQL 로 돈다.
"""
import ast
import asyncio
import dataclasses
from pathlib import Path

import pytest
import sqlalchemy as sa

from history_sqlite import (
    AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
)
from models.research_work import WORK_PHASES, ResearchGeneration, ResearchWork
from services.llm_client import LLMResult
from services.research_work import concepts, routing, shapes
from services.research_work.apply import apply_result
from services.research_work.executors import EXECUTORS
from services.research_work.generate import Executor, run_generation

MESSAGES = [{"role": "user", "content": "사용자"}]
NOT_READ = "읽지 못할 답"
INPUT = {"answer": "정답"}


@pytest.fixture
def cfg(monkeypatch):
    settings = routing.get_settings()
    monkeypatch.setattr(settings, "VLM_BASE_URL", "http://qwen.test/v1")
    monkeypatch.setattr(settings, "VLM_MODEL", "qwen-test")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://gemma.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    return settings


class _ScriptedChat:
    """모델 이름마다 응답 문자열을 차례로 꺼낸다."""

    def __init__(self, script: dict[str, list]):
        self.script = {model: list(items) for model, items in script.items()}
        self.models: list[str] = []

    async def __call__(self, messages, *, params=None, timeout=120.0, base_url=None, model=None):
        self.models.append(model)
        return LLMResult(content=self.script[model].pop(0), finish_reason="stop")


def _plain(kind: str = "outline", **fields) -> Executor:
    return Executor(kind, lambda inp: (MESSAGES, {}), lambda raw: {"raw": raw},
                    lambda out: True, lambda inp: {}, **fields)


def _bound(seen: list) -> Executor:
    """parse 는 {"raw": 원문}, bind 는 입력의 정답과 견줘 ok 를 붙인다 — check 는 bind 뒤의 값을 본다."""
    def _bind(output: dict, inp: dict) -> dict:
        seen.append((dict(output), inp))
        return {"raw": output["raw"], "ok": output["raw"] == inp["answer"]}

    return Executor(
        kind="outline", build=lambda inp: (MESSAGES, {}),
        parse=lambda raw: None if raw == NOT_READ else {"raw": raw},
        check=lambda out: out.get("ok") is True,
        empty=lambda inp: {"empty": True},
        bind=_bind,
    )


def _outcomes(result) -> list[str]:
    return [a["outcome"] for a in result.attempts]


class TestExecutorFields:
    def test_new_fields_follow_the_06a_five_with_defaults(self):
        # frozen dataclass — 06a 의 다섯 필드만 위치 인자로 준 실행기가 그대로 06a 처럼 돈다
        assert [f.name for f in dataclasses.fields(Executor)] == [
            "kind", "build", "parse", "check", "empty", "bind", "stream", "apply", "is_empty"]
        ex = _plain()
        assert (ex.bind, ex.stream, ex.apply, ex.is_empty) == (None, False, None, None)

    def test_concepts_marks_an_empty_done_as_retryable(self):
        # 06a api._retryable 의 concepts 특례(빈 개념 done 은 다시 부를 수 있다)를 실행기로 옮긴 것
        ex = concepts.EXECUTOR
        assert ex.is_empty({"concepts": []}) and ex.is_empty({}) and ex.is_empty(None)
        assert not ex.is_empty({"concepts": ["독서 격차", "청소년"]})
        assert (ex.bind, ex.stream, ex.apply) == (None, False, None)


class TestBind:
    def _go(self, chat, seen):
        return asyncio.run(run_generation(_bound(seen), INPUT, chat_fn=chat))

    def test_bind_runs_between_parse_and_check(self, cfg):
        seen: list = []
        chat = _ScriptedChat({"gemma-test": ["정답"]})

        result = self._go(chat, seen)

        assert seen == [({"raw": "정답"}, INPUT)]
        assert result.output == {"raw": "정답", "ok": True} and result.model == "gemma-test"

    def test_a_bound_output_that_fails_the_check_is_asked_again(self, cfg):
        seen: list = []
        chat = _ScriptedChat({"gemma-test": ["오답", "정답"]})

        result = self._go(chat, seen)

        assert chat.models == ["gemma-test", "gemma-test"]
        assert _outcomes(result) == ["check", "ok"]
        assert [s[0] for s in seen] == [{"raw": "오답"}, {"raw": "정답"}]

    def test_an_unreadable_answer_is_not_bound(self, cfg):
        seen: list = []
        chat = _ScriptedChat({"gemma-test": [NOT_READ, "정답"]})

        result = self._go(chat, seen)

        assert _outcomes(result) == ["parse", "ok"]
        assert seen == [({"raw": "정답"}, INPUT)]

    def test_the_empty_result_is_not_bound(self, cfg):
        seen: list = []
        chat = _ScriptedChat({"gemma-test": [NOT_READ, "오답"], "qwen-test": [NOT_READ]})

        result = self._go(chat, seen)

        assert chat.models == ["gemma-test", "gemma-test", "qwen-test"]
        assert result.output == {"empty": True} and result.model is None
        assert len(seen) == 1          # '오답' 한 번 — 빈 결과(empty)는 bind 를 거치지 않는다


class TestApplyDelegation:
    """apply_result 는 concepts 를 06a 분기 그대로 두고 그 밖의 kind 를 실행기의 apply 에 맡긴다."""

    @pytest.fixture
    def env(self):
        engine = make_engine()
        work_id = add_research_job(engine, status="completed", stage="synthesized")
        add_work(engine, work_id, concepts=["독서 격차"])
        return engine, work_id

    @staticmethod
    def _apply(engine, gid: int, output: dict, *, commit: bool = False):
        async def _go():
            db = AsyncSessionOverSync(engine)
            try:
                payload = await apply_result(db, await db.get(ResearchGeneration, gid), output)
                if commit:
                    await db.commit()
                else:
                    await db.rollback()        # 적용이 커밋하지 않았다면 되돌림으로 사라진다
                return payload
            finally:
                await db.close()

        return asyncio.run(_go())

    @staticmethod
    def _work(engine, work_id):
        with engine.connect() as conn:
            return conn.execute(sa.select(ResearchWork.__table__)
                                .where(ResearchWork.__table__.c.id == work_id)).mappings().one()

    def test_other_kinds_hand_over_to_the_executor_apply(self, env, monkeypatch):
        engine, work_id = env
        gid = add_generation(engine, work_id, kind="refine", status="running")
        calls: list = []

        async def _apply(db, gen, output):
            calls.append((gen.id, gen.kind, output))
            await db.execute(sa.update(ResearchWork).where(ResearchWork.id == gen.work_id)
                             .values(memo="반영"))
            return {"applied": True}

        monkeypatch.setitem(EXECUTORS, "refine", _plain("refine", apply=_apply))

        assert self._apply(engine, gid, {"x": 1}) == {"applied": True}
        assert calls == [(gid, "refine", {"x": 1})]
        assert self._work(engine, work_id)["memo"] is None       # 커밋은 finish 의 몫이다

        assert self._apply(engine, gid, {"x": 1}, commit=True) == {"applied": True}
        assert self._work(engine, work_id)["memo"] == "반영"

    def test_an_executor_without_apply_changes_nothing(self, env, monkeypatch):
        engine, work_id = env
        gid = add_generation(engine, work_id, kind="refine", status="running")
        monkeypatch.setitem(EXECUTORS, "refine", _plain("refine"))

        assert self._apply(engine, gid, {"x": 1}, commit=True) == {}
        assert self._work(engine, work_id)["concepts"] == ["독서 격차"]

    def test_concepts_keep_the_06a_branch(self, env, monkeypatch):
        engine, work_id = env
        gid = add_generation(engine, work_id, kind="concepts", status="running")

        async def _boom(db, gen, output):
            raise AssertionError("concepts 는 실행기 apply 로 가지 않는다")

        monkeypatch.setitem(EXECUTORS, "concepts", dataclasses.replace(concepts.EXECUTOR, apply=_boom))

        payload = self._apply(engine, gid, {"concepts": ["노인 우울", "사회적 지지"]}, commit=True)

        assert payload == {"concepts": ["노인 우울", "사회적 지지"]}
        assert self._work(engine, work_id)["concepts"] == ["노인 우울", "사회적 지지"]


class TestShapes:
    def test_constants_module_imports_nothing(self):
        # 실행기·API·조회 모양이 함께 가져다 쓴다 — LLM·DB·무거운 모듈을 끌어오면 안 된다
        tree = ast.parse(Path(shapes.__file__).read_text(encoding="utf-8"))
        assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]

    def test_phase_order_is_the_model_phase_order(self):
        assert shapes.PHASE_ORDER == WORK_PHASES

    def test_section_keys(self):
        assert shapes.WRITABLE_SECTION_KEYS == ("prior.g1", "prior.g2", "prior.g3", "prior.g4", "gap")
        assert len(shapes.PRIOR_KEYS) == shapes.MAX_GROUPS
        assert shapes.PROPOSAL_SECTIONS == ("topic", "background", "prior", "gap", "question", "method")
        assert set(shapes.EXPORTED_PARA_STATES) < set(shapes.PARA_STATES)
        # 절 키·목차 target 은 research_generations.target(String(64))에 들어간다
        assert all(len(k) <= 64 for k in (*shapes.WRITABLE_SECTION_KEYS, shapes.OUTLINE_TARGET))
