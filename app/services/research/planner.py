"""planner.py — 질문을 하위질문으로 분해

파싱을 LLM 호출에서 분리한 이유: 모델이 번호 매김을 흐트러뜨리는 것은
흔한 일이고, 그 처리를 네트워크 없이 테스트할 수 있어야 한다.
"""
import logging
import re

from services.llm_client import chat
from services.prompts import get_prompt

log = logging.getLogger(__name__)

_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.+?)\s*$")
# 줄 전체를 감싼 강조. 여는 표식 뒤가 공백이 아닐 것을 요구해야 불릿과 구분된다 —
# "* **가**" 의 앞 "*" 는 불릿이지 강조가 아니다.
_WRAP = re.compile(r"^\s*(\*\*|__|\*|_)(?=\S)(.*?)\1\s*$", re.S)
# 쌍으로 감싼 강조만 벗긴다. 전역으로 [*_`] 를 지우면 TF_IDF → TFIDF 처럼
# 본문 중간 문자까지 훼손된다.
_PAIRED_EMPH = re.compile(r"(\*\*|__|\*|_|`)(?=\S)(.+?)\1")
_WS = re.compile(r"\s+")


def _unwrap_line(line: str) -> str:
    """`**1. 가**` 처럼 항목 전체를 감싼 강조를 벗긴다.

    이걸 항목 매칭보다 먼저 해야 한다. 안 그러면 앞의 `*` 가 불릿으로 먹혀
    매칭이 깨지고, 모든 줄이 탈락해 계획 수립이 통째로 실패한다.
    """
    m = _WRAP.match(line)
    return m.group(2) if m else line


def _strip_emphasis(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = _PAIRED_EMPH.sub(r"\2", text)
    return text


def parse_plan(raw: str, *, limit: int) -> list[str]:
    """번호/불릿 목록에서 하위질문을 뽑는다. 중복·공백 제거, limit 개까지.

    강조를 항목 매칭보다 먼저 벗기는 이유: 모델이 `**1. 주제**` 처럼 항목
    전체를 굵게 쓰면 앞의 `*` 가 불릿으로 먹혀 매칭이 깨진다. 그러면 모든
    줄이 탈락해 계획 수립이 통째로 실패하고 job 이 죽는다.
    """
    items: list[str] = []
    seen: set[str] = set()
    for line in (raw or "").splitlines():
        m = _ITEM.match(_unwrap_line(line))
        if not m:
            if line.strip():
                log.debug("[planner] 항목으로 해석되지 않은 줄 — %r", line.strip()[:80])
            continue
        text = _strip_emphasis(m.group(1)).strip()
        key = _WS.sub(" ", text).casefold()
        if text and key not in seen:
            seen.add(key)
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
