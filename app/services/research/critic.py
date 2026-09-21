"""critic.py — 근거 충분성 자기점검

판정 결과는 내부 제어에만 쓰지 않는다. note 가 그대로 보고서의
"한계와 미확인 영역" 섹션이 된다 — 모른다고 말하는 것이 이 기능의 값이다.

판정을 못 읽었을 때는 parse_failed 로 표시한다. 그냥 sufficient 로만 두면
"모델이 충분하다고 판단한 것"과 구분되지 않아, 자기점검이 전부 꺼져도
보고서가 "한계 없음"으로 보인다.
"""
import logging
from dataclasses import dataclass, field

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research.state import Evidence, LLM_VERDICTS, SubQuestion

log = logging.getLogger(__name__)

_EXCERPT_LEN = 200
# 근거 목록 길이 상한. 재검색 라운드마다 evidence_ids 가 누적되므로 상한이
# 없으면 프롬프트가 컨텍스트를 넘고, 앞쪽부터 잘려 system 의 JSON 출력
# 지시가 사라진다 — 그러면 산문 응답이 와서 판정이 또 실패한다.
_MAX_LISTED = 20
_PARSE_FAILED_NOTE = "자동 점검을 완료하지 못했다"


@dataclass
class Verdict:
    verdict: str
    note: str = ""
    new_queries: list[str] = field(default_factory=list)
    parse_failed: bool = False


def _failed(reason: str, raw: str) -> Verdict:
    """모델 원문은 로그에만 남긴다 — note 는 사용자 화면(탐색 경로)에 실린다."""
    log.warning("[critic] %s — raw=%r", reason, (raw or "")[:200])
    return Verdict("sufficient", note=_PARSE_FAILED_NOTE, parse_failed=True)


def parse_verdict(raw: str) -> Verdict:
    """판정 JSON 을 읽는다. 못 읽으면 sufficient 로 떨어뜨려 루프를 끝낸다.

    해석 실패를 insufficient 로 두면 파싱이 깨질 때마다 재검색이 상한까지
    돌아 시간을 태운다. 실패가 루프가 되면 안 된다.
    """
    data = extract_json(raw)
    if data is None:
        return _failed("판정 JSON 파싱 실패", raw)

    verdict = data.get("verdict")
    if verdict not in LLM_VERDICTS:
        return _failed(f"알 수 없는 verdict 값 {verdict!r}", raw)

    raw_queries = data.get("new_queries")
    if not isinstance(raw_queries, list):
        # 문자열이 오면 순회 시 글자 단위로 쪼개져 "진" 한 글자로 재검색한다
        raw_queries = []
    queries = [q for q in raw_queries if isinstance(q, str) and q.strip()]
    return Verdict(verdict, note=str(data.get("note") or ""), new_queries=queries)


def should_recheck(subq: SubQuestion, *, recheck_count: int, max_recheck: int) -> bool:
    return subq.verdict == "insufficient" and recheck_count < max_recheck


def format_evidence_list(evidence: list[Evidence]) -> str:
    """근거를 critic 프롬프트용 목록 문자열로 만든다.

    제목·연도만으로는 "이 논문이 하위질문을 실제로 다루는가"를 모델이
    판단하기 어렵다 — 그 하위질문 검색에서 실제로 매칭된 본문(chunks[0])의
    앞부분을 붙여 직접적인 근거로 준다. 청크가 없는 근거는 제목+연도만
    남긴다 — 인덱스 오류로 이 계층 전체가 죽으면 안 된다.

    발췌는 자르기 전에 공백을 접는다. 표 청크는 `[표]\\n…\\n{table_md}` 로
    저장되고 본문 청크도 단락 개행을 보존하므로, 그대로 쓰면 한 항목이
    여러 줄로 퍼져 어느 발췌가 어느 논문 것인지 흐려진다.
    """
    lines: list[str] = []
    for e in evidence[:_MAX_LISTED]:
        title = e.meta.get("title") or "(제목 없음)"
        year = e.meta.get("pub_date") or "연도미상"
        if not e.chunks:
            lines.append(f"- {title} ({year})")
            continue
        flat = " ".join(e.chunks[0].text.split())
        excerpt = flat[:_EXCERPT_LEN]
        if len(flat) > _EXCERPT_LEN:
            excerpt += "…"
        lines.append(f"- {title} ({year}) — {excerpt}")

    hidden = len(evidence) - _MAX_LISTED
    if hidden > 0:
        lines.append(f"- …외 {hidden}편")
    return "\n".join(lines) or "(없음)"


async def critique(
    subq: SubQuestion, evidence: list[Evidence], *, params: dict,
) -> Verdict:
    system, user, llm_params = get_prompt("research_critique").render(
        subquestion=subq.text,
        evidence_count=len(evidence),
        evidence_list=format_evidence_list(evidence),
        min_evidence=params["min_evidence_per_subq"],
        tried_queries=", ".join(subq.queries) or "(없음)",
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params,
    )
    return parse_verdict(raw)
