"""critic.py — 근거 충분성 자기점검

판정 결과는 내부 제어에만 쓰지 않는다. note 가 그대로 보고서의
"한계와 미확인 영역" 섹션이 된다 — 모른다고 말하는 것이 이 기능의 값이다.

판정을 못 읽었을 때는 parse_failed 로 표시한다. 그냥 sufficient 로만 두면
"모델이 충분하다고 판단한 것"과 구분되지 않아, 자기점검이 전부 꺼져도
보고서가 "한계 없음"으로 보인다. 판정 호출 자체가 일시 오류로 실패한 경우도
같다 — 판정을 받지 못한 것이지 탐색이 실패한 것이 아니다.
"""
import logging
import re
from dataclasses import dataclass, field

import httpx

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
# note 에서 목록 번호를 가리킨 표기. 목록에 번호가 붙고 off_topic 을 번호로 받으니 모델이 note 에도
# 쓰기 쉽다. 사용자는 이 목록을 보지 못하고 보고서는 인용을 [n] 으로 렌더해, 남기면 참고문헌 번호로 읽힌다.
_LIST_REF = re.compile(r"\[\s*(\d+)\s*\]")


@dataclass
class Verdict:
    verdict: str
    note: str = ""
    new_queries: list[str] = field(default_factory=list)
    parse_failed: bool = False
    # 발췌가 하위질문의 핵심 개념을 다루지 않는 근거의 목록 번호(1부터, format_evidence_list 의 [n]).
    # runner 가 그 하위질문에서 뺀다 — 같은 단어를 다른 뜻으로 쓴 논문을 걸러낼 수 있는 곳은
    # 발췌를 읽는 critic 뿐이다.
    off_topic: list[int] = field(default_factory=list)


def _unchecked() -> Verdict:
    return Verdict("sufficient", note=_PARSE_FAILED_NOTE, parse_failed=True)


def _failed(reason: str, raw: str) -> Verdict:
    """모델 원문은 로그에만 남긴다 — note 는 사용자 화면(탐색 경로)에 실린다."""
    log.warning("[critic] %s — raw=%r", reason, (raw or "")[:200])
    return _unchecked()


def parse_verdict(raw: str, *, listed: int = 0) -> Verdict:
    """판정 JSON 을 읽는다. 못 읽으면 sufficient 로 떨어뜨려 루프를 끝낸다.

    해석 실패를 insufficient 로 두면 파싱이 깨질 때마다 재검색이 상한까지
    돌아 시간을 태운다. 실패가 루프가 되면 안 된다.

    listed 는 번호를 붙여 보인 근거 수다(format_evidence_list). 판정을 못 읽으면
    off_topic 도 비어 있다 — 판정을 못 읽었는데 근거를 지우면 안 된다.
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
    return Verdict(verdict, note=str(data.get("note") or ""), new_queries=queries,
                   off_topic=_off_topic(data.get("off_topic"), listed))


def _off_topic(raw: object, listed: int) -> list[int]:
    """보인 목록 안의 번호만 순서대로·중복 없이 받는다. 배열이 아니거나 숫자로 읽히지 않는 값은
    버린다 — 잘못 읽은 번호로 관련 있는 근거를 지우느니 무관한 근거 하나를 남기는 편이 낫다."""
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for v in raw:
        if isinstance(v, str) and v.strip().isdecimal():
            v = int(v)
        # bool 은 int 의 서브클래스라 true 가 1번으로 읽힌다
        if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= listed and v not in out:
            out.append(v)
    return out


def should_recheck(
    subq: SubQuestion, *, recheck_count: int, max_recheck: int, emptied: bool = False,
) -> bool:
    """emptied — 이 회차에 무관 근거를 빼고 나니 0편이다. 그때는 판정이 충분이어도 다시 찾는다 —
    그 판정은 뺀 근거까지 보고 내린 것이고, 근거 없는 "충분"은 없다."""
    return (subq.verdict == "insufficient" or emptied) and recheck_count < max_recheck


def format_evidence_list(evidence: list[Evidence]) -> str:
    """근거를 critic 프롬프트용 목록 문자열로 만든다.

    제목·연도만으로는 "이 논문이 하위질문을 실제로 다루는가"를 모델이
    판단하기 어렵다 — 그 하위질문 검색에서 실제로 매칭된 본문(chunks[0])의
    앞부분을 붙여 직접적인 근거로 준다. runner 가 청크를 그 하위질문 몫으로
    추려서 넘긴다(citations.chunks_for). 청크가 없는 근거는 제목+연도만
    남긴다 — 인덱스 오류로 이 계층 전체가 죽으면 안 된다.

    evidence 는 하위질문 안 순위순이다 — 상한에서 잘리는 쪽이 순위 낮은 근거다.

    항목마다 [1]부터 번호를 붙인다. 모델은 이 번호로 무관한 근거를 가리키고(off_topic),
    runner 가 넘긴 순서로 근거 id 에 되돌린다. 잘린 나머지는 번호 없이 수만 적는다 —
    발췌를 보지 못한 근거를 무관하다고 가리키게 두지 않는다.

    발췌는 자르기 전에 공백을 접는다. 표 청크는 `[표]\\n…\\n{table_md}` 로
    저장되고 본문 청크도 단락 개행을 보존하므로, 그대로 쓰면 한 항목이
    여러 줄로 퍼져 어느 발췌가 어느 논문 것인지 흐려진다.
    """
    lines: list[str] = []
    for n, e in enumerate(evidence[:_MAX_LISTED], start=1):
        title = _title(e)
        year = e.meta.get("pub_date") or "연도미상"
        if not e.chunks:
            lines.append(f"[{n}] {title} ({year})")
            continue
        flat = " ".join(e.chunks[0].text.split())
        excerpt = flat[:_EXCERPT_LEN]
        if len(flat) > _EXCERPT_LEN:
            excerpt += "…"
        lines.append(f"[{n}] {title} ({year}) — {excerpt}")

    hidden = len(evidence) - _MAX_LISTED
    if hidden > 0:
        lines.append(f"…외 {hidden}편")
    return "\n".join(lines) or "(없음)"


def _title(e: Evidence) -> str:
    return e.meta.get("title") or "(제목 없음)"


def _titled_note(note: str, evidence: list[Evidence]) -> str:
    """note 의 목록 번호([2])를 그 논문 제목으로 바꾼다 — 지우면 '[2]는 …' 문장이 깨진다.
    보인 목록 밖의 번호는 가리킨 논문을 알 수 없으니 그대로 둔다."""
    listed = evidence[:_MAX_LISTED]

    def _sub(m: re.Match) -> str:
        n = int(m.group(1))
        return f"「{_title(listed[n - 1])}」" if 1 <= n <= len(listed) else m.group(0)

    return _LIST_REF.sub(_sub, note)


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
    try:
        raw = await chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            params=llm_params,
        )
    except httpx.HTTPError as e:
        # 올려 보내면 워커가 하위질문을 failed 로 두고, 이미 모은 근거가 절에서
        # 빠진 채 "탐색 중 오류"로 보고된다. 파싱 실패와 같은 '판정 불가'로 낮춘다.
        log.warning("[critic] 판정 호출 실패 subq=%s — %s: %s", subq.idx, type(e).__name__, e)
        return _unchecked()
    verdict = parse_verdict(raw, listed=min(len(evidence), _MAX_LISTED))
    verdict.note = _titled_note(verdict.note, evidence)
    return verdict
