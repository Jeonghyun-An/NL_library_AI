"""planner.py — 질문을 하위질문으로 분해

파싱을 LLM 호출에서 분리한 이유: 모델이 번호 매김을 흐트러뜨리는 것은
흔한 일이고, 그 처리를 네트워크 없이 테스트할 수 있어야 한다.
"""
import re

from services.llm_client import chat
from services.prompts import get_prompt

_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.+?)\s*$")
_EMPH = re.compile(r"[*_`]+")


def parse_plan(raw: str, *, limit: int) -> list[str]:
    """번호/불릿 목록에서 하위질문을 뽑는다. 중복·공백 제거, limit 개까지."""
    items: list[str] = []
    for line in (raw or "").splitlines():
        m = _ITEM.match(line)
        if not m:
            continue
        text = _EMPH.sub("", m.group(1)).strip()
        if text and text not in items:
            items.append(text)
    if not items:
        raise ValueError(f"계획을 해석하지 못했다: {(raw or '')[:120]!r}")
    return items[:limit]


async def make_plan(question: str, *, params: dict) -> list[str]:
    limit = params["max_subquestions"]
    system, user, llm_params = get_prompt("research_plan").render(
        question=question, limit=limit,
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params,
    )
    return parse_plan(raw, limit=limit)
