"""critic.py — 근거 충분성 자기점검

판정 결과는 내부 제어에만 쓰지 않는다. note 가 그대로 보고서의
"한계와 미확인 영역" 섹션이 된다 — 모른다고 말하는 것이 이 기능의 값이다.
"""
import json
import re
from dataclasses import dataclass, field

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.state import Evidence, LLM_VERDICTS, SubQuestion

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


@dataclass
class Verdict:
    verdict: str
    note: str = ""
    new_queries: list[str] = field(default_factory=list)


def parse_verdict(raw: str) -> Verdict:
    """판정 JSON 을 읽는다. 못 읽으면 sufficient 로 떨어뜨려 루프를 끝낸다.

    해석 실패를 insufficient 로 두면 파싱이 깨질 때마다 재검색이 상한까지
    돌아 시간을 태운다. 실패가 루프가 되면 안 된다.
    """
    body = raw or ""
    m = _FENCE.search(body)
    if m:
        body = m.group(1)
    try:
        data = json.loads(body[body.index("{"): body.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return Verdict("sufficient", note=f"판정 해석 실패 — {(raw or '')[:80]}")

    verdict = data.get("verdict")
    if verdict not in LLM_VERDICTS:
        return Verdict("sufficient", note=f"판정 해석 실패 — verdict={verdict!r}")

    queries = [q for q in (data.get("new_queries") or []) if isinstance(q, str) and q.strip()]
    return Verdict(verdict, note=str(data.get("note") or ""), new_queries=queries)


def should_recheck(subq: SubQuestion, *, recheck_count: int, max_recheck: int) -> bool:
    return subq.verdict == "insufficient" and recheck_count < max_recheck


async def critique(
    subq: SubQuestion, evidence: list[Evidence], *, params: dict,
) -> Verdict:
    lines = [
        f"- {e.meta.get('title', '(제목 없음)')} ({e.meta.get('pub_date', '연도미상')})"
        for e in evidence
    ]
    system, user, llm_params = get_prompt("research_critique").render(
        subquestion=subq.text,
        evidence_count=len(evidence),
        evidence_list="\n".join(lines) or "(없음)",
        min_evidence=params["min_evidence_per_subq"],
        tried_queries=", ".join(subq.queries),
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params,
    )
    return parse_verdict(raw)
