"""critic.py — 근거 충분성 자기점검

판정 결과는 내부 제어에만 쓰지 않는다. note 가 그대로 보고서의
"한계와 미확인 영역" 섹션이 된다 — 모른다고 말하는 것이 이 기능의 값이다.
"""
import json
import logging
import re
from dataclasses import dataclass, field

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.state import Evidence, LLM_VERDICTS, SubQuestion

log = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
_EXCERPT_LEN = 200


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
        log.warning(f"[critic] 판정 JSON 파싱 실패 — raw={(raw or '')[:200]!r}")
        return Verdict("sufficient", note=f"판정 해석 실패 — {(raw or '')[:80]}")

    verdict = data.get("verdict")
    if verdict not in LLM_VERDICTS:
        log.warning(f"[critic] 알 수 없는 verdict 값 {verdict!r} — raw={(raw or '')[:200]!r}")
        return Verdict("sufficient", note=f"판정 해석 실패 — verdict={verdict!r}")

    queries = [q for q in (data.get("new_queries") or []) if isinstance(q, str) and q.strip()]
    return Verdict(verdict, note=str(data.get("note") or ""), new_queries=queries)


def should_recheck(subq: SubQuestion, *, recheck_count: int, max_recheck: int) -> bool:
    return subq.verdict == "insufficient" and recheck_count < max_recheck


def format_evidence_list(evidence: list[Evidence]) -> str:
    """근거를 critic 프롬프트용 목록 문자열로 만든다.

    제목·연도만으로는 "이 논문이 하위질문을 실제로 다루는가"를 모델이
    판단하기 어렵다 — 그 하위질문 검색에서 실제로 매칭된 본문(chunks[0])의
    앞부분을 붙여 직접적인 근거로 준다. 청크가 없는 근거는 제목+연도만
    남긴다 — 인덱스 오류로 이 계층 전체가 죽으면 안 된다.
    """
    lines = []
    for e in evidence:
        title = e.meta.get("title", "(제목 없음)")
        year = e.meta.get("pub_date", "연도미상")
        if not e.chunks:
            lines.append(f"- {title} ({year})")
            continue
        excerpt = e.chunks[0].text[:_EXCERPT_LEN]
        lines.append(f"- {title} ({year}) — {excerpt}")
    return "\n".join(lines) or "(없음)"


async def critique(
    subq: SubQuestion, evidence: list[Evidence], *, params: dict,
) -> Verdict:
    system, user, llm_params = get_prompt("research_critique").render(
        subquestion=subq.text,
        evidence_count=len(evidence),
        evidence_list=format_evidence_list(evidence),
        min_evidence=params["min_evidence_per_subq"],
        tried_queries=", ".join(subq.queries),
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params,
    )
    return parse_verdict(raw)
