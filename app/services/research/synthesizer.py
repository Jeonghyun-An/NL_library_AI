"""synthesizer.py — 보고서 조립

인용을 두 갈래로 다룬다.
- 대표 논문 요약: 불릿 = 논문이므로 싣는 논문과 칩은 코드가 정한다. 다만 절의 논문을
  한 호출에 넣고 번호별로 받으므로, 어느 요약이 어느 번호에 붙는지는 모델이 정한다.
- 도입·향후 과제: 모델이 [E3] 마커를 달고 여기서 전수 검증한다.

종합은 하위질문 하나당 LLM 호출 하나다. 절 구성(소제목·어떤 논문을 싣는지)은
여기서 정하고 모델은 문장만 쓴다. 전체를 한 번에 맡겼을 때(2026-09-23 실측,
gemma-3-12b) 프롬프트 예시의 "섹션 1·논문 1·과제 1" 모양을 그대로 베껴
하위질문 3개 중 1개 절, 근거 10편 중 1편만 실렸다 — 절과 논문 선택을 모델에
맡기면 그게 구조가 아니라 추론이 된다.

제목·저자·연도는 모델 출력에서 가져오지 않는다. evidence 의 meta 를 쓴다 —
라벨을 모델이 쓰게 두면 언젠가 없는 논문을 만들어낸다.
"""
import difflib
import html
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, fields

import httpx

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.bibliography import has_prose
from services.research.citations import bind_markers, chunks_for, strip_markers, strip_numbered_refs
from services.research.hangul import josa
from services.research.llm_json import extract_json
from services.research.runner import subq_budget
from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, research_stats,
)

log = logging.getLogger(__name__)

UNMARKED_THRESHOLD = 3
# 절마다 싣는 대표 논문 상한. runner 가 evidence_ids 를 하위질문 안 순위로
# 정렬해 두므로 앞에서 자른다.
PAPERS_PER_SECTION = 5
# spec §6 "종합 LLM 실패 — 1회 재시도". 절 단위라 한 절을 다시 부를 때 이미
# 받은 절은 그대로 둔다.
_SECTION_ATTEMPTS = 2
# 프롬프트 JSON 예시의 자리표시자. gemma 는 예시를 견본으로 베끼므로
# (recurring-gotchas 15번) 이게 남은 문장은 서술이 아니라 지시문 원문이다.
_PLACEHOLDER = "[E#]"
_EID_KEY = re.compile(r"\s*\[?\s*[Ee]\s*(\d+)\s*\]?\s*")

# 절 생성에 논문마다 넘기는 대목 길이(앞에서 자른다)
EXCERPT_CHARS = 400
_BR = re.compile(r"<br\s*/?>", re.I)
# 표 대목 — '|' 가 둘 이상인 줄이 대목 창의 이만큼을 차지하면 표로 본다
_TABLE_SHARE = 0.6
# 완결 문장의 끝 — 마침표 뒤 공백·끝·각주 번호 '4)'·닫는 따옴표. 창 끝에서 잘린 조각('<Abstract> This s')은 문장이 아니다
_SENTENCE_STOP = re.compile(r"[.!?。](?=\s|$|\d{1,3}\)|[\"”’」』])")
# 영문 초록 문장에 흔한 서술 동사 — bibliography.has_prose 의 목록에 없는 것만
_ENGLISH_VERBS = re.compile(r"\b(?:analy[sz]ed|examined|investigated|revealed|indicated|compared|results?)\b", re.I)

# 앞 절과 같은 문장으로 보는 유사도(difflib ratio, 인용 표기·공백·문장부호를 뺀 글끼리). 운영 보고서 2건과 gemma 재생성
# 9회에서 0.85 이상은 모두 같은 대목을 옮긴 거의 같은 문장이었고, 0.70~0.82 는 바꿔 쓴 일반론('…다양한 변인에 대한
# 연구가 필요하다')이었다 — 그쪽은 남긴다
_REPEAT_RATIO = 0.85
# 비교 키(인용 표기·공백·문장부호를 뺀 글)가 이보다 짧으면 되풀이로 보지 않는다 — 마침표에서 잘린 번호 '1.'·'가정 vs.'
# 조각은 키가 '1'·'가정vs' 라 앞 절에 같은 조각이 있으면 유사도 1.0 으로 지워졌다. 되풀이로 지운 운영·재생성 문장은 모두
# 이보다 길다
_REPEAT_KEY_MIN = 8
# 절 자신을 가리키는 메타 문장('본 절에서는 … 분석하고자 한다') — 근거가 없는데 마커가 붙어 나온다
_META_SENTENCE = re.compile(r"^(?:본|이)\s?(?:절|장|보고서|섹션)(?:에서는|에서|은|는)\s")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?。])\s+")
_LEADING_BRACKETS = re.compile(r"^(?:[ \t]*[\[［【][^\[\]［］【】\n]*[\]］】])+")
# 마커 바로 뒤가 '연구는'·'논문에서'·조사('[E3]의')면 그 마커는 다음 문장의 주어다(운영 630e0d65 4절 '[E3] 연구는 …')
_MARKER_AS_SUBJECT = re.compile(r"^(?:[ \t]*(?:연구|논문)|[은는이가의에와과도])")
_NON_WORD = re.compile(r"[\W_]+")


# on_section(idx, total, status, info) — info 의 모양은 synthesize 독스트링에 있다. 인자 수를
# 타입에 못박지 않는 이유: 워커의 콜백은 info 를 선택 인자로 받는다(info 없는 호출과 호환).
SectionFn = Callable[..., Awaitable[None]]


class SynthesisCanceled(Exception):
    """취소가 확인돼 종합을 멈췄다 — 실패가 아니라 사용자의 결정이다."""


async def _no_progress(idx: int, total: int, status: str, info: dict | None = None) -> None:
    return None


def _topic(text: str) -> str:
    """한계 문장의 주어 조각. 조사는 끝 문장부호('?' 등)를 뺀 마지막 글자의 받침에 맞춘다
    (한글로 끝나지 않으면 '(은)는')."""
    return f"'{text}' {josa(text, '은는')}"


def _first_sentence(text: str) -> str:
    """첫 문장 — 한글 바로 뒤 마침표에 공백이 이어지는 곳까지. 「제목」 안의 '. '·'58.4%' 같은 숫자 사이
    마침표에서는 자르지 않고, 끊을 곳이 없으면 통째로 돌려준다."""
    text = text.strip()
    depth = 0
    for i, ch in enumerate(text):
        if ch == "「":
            depth += 1
        elif ch == "」":
            depth = max(depth - 1, 0)
        elif (ch == "." and not depth and i and "가" <= text[i - 1] <= "힣"
              and i + 1 < len(text) and text[i + 1].isspace()):
            return text[:i + 1]
    return text


def _memo(note: str) -> str:
    """한계 줄 끝에 붙이는 critic note — 첫 문장만 '자기점검 메모'로 따옴표 안에 인용한다.

    note 를 그대로 이으면 '-다' 체 문장 뒤에 '…부족합니다. 특히 …어렵습니다.' 가 붙어 문체가 섞이고 줄이
    길어졌다(운영 630e0d65, 회차 note 42개 중 38개가 합니다체 — 프롬프트의 '-다 체'를 gemma 가 대부분 지키지
    않는다). 합니다→다 를 코드로 바꾸지 않는다: '않습니다'가 '않다'인지 '않는다'인지 코드가 가를 수 없다.
    직접 인용은 원문의 말투를 그대로 두는 표기라 섞여 보이지 않고, critic 의 판단이라는 출처도 드러난다.
    첫 문장만 싣는 것은 note 의 핵심('…은 부족하다')이 첫 문장 끝에 오기 때문이다 — 글자 수로 자르면 그게
    잘린다. 둘째 문장('특히 …')은 탐색 경로의 회차 note 에 그대로 남는다."""
    first = _first_sentence(note)
    return f" — 자기점검 메모: “{first}”" if first else ""


def _capped_clause(state: ResearchState, sq: SubQuestion, noun: str) -> str:
    """상한에 막힌 후보를 원인별로 적는다 — "…에 닿아 {noun} N편을" 을 쉼표로 잇는다.

    하위질문당 몫과 전체 상한을 한 수로 합치지 않는다. 풀리는 방법이 다르다 — 몫은 계획에서
    하위질문을 줄이면 커지고, 전체 상한은 max_evidence 를 올려야 풀린다.
    """
    parts = []
    if sq.budget_capped:
        parts.append(f"하위질문당 근거 상한({subq_budget(state)}편)에 닿아 "
                     f"{noun} {sq.budget_capped}편을")
    if sq.capped:
        parts.append(f"전체 근거 상한({state.params['max_evidence']}편)에 닿아 "
                     f"{noun} {sq.capped}편을")
    return ", ".join(parts)


def build_limitations(
    state: ResearchState, *, unmarked_total: int, dropped_total: int,
    failed_sections: int = 0, unsummarized_total: int = 0,
    unparsed_total: int = 0, introless_sections: int = 0,
) -> list[str]:
    """자기점검 결과를 사용자에게 보이는 문장으로 바꾼다.

    판정을 받지 못한 하위질문(parse_failed)을 반드시 별도로 센다. 판정 불가는
    verdict="sufficient" 로 떨어지므로 아래 insufficient 분기에 걸리지 않고,
    그대로 두면 자기점검이 전부 꺼져도 보고서가 "한계 없음"으로 보인다.

    절에 주지 않은 근거 번호(dropped)와 무근거 서술(unmarked)도 한 문장으로
    합치지 않는다. 종류가 다른 사건이다 — 마커 없는 문장은 "이 절에서는 …을
    다룬다" 같은 연결 문장일 때가 많아 몇 건은 넘긴다. 반면 주지 않은 번호를
    가리킨 표기는 모델이 근거를 지어낸 것이니 1건부터 보고한다. 합치면 흔한 쪽을
    과하게 알리면서 정작 심각한 쪽을 임계값에 묻는다.
    """
    out: list[str] = []
    # 보고서의 절 — synthesize 는 근거 있는 하위질문마다 순서대로 절을 하나씩 만든다. 화면·내려받은 문서는
    # 이 순서로 'N. 제목' 을 단다
    sectioned = [sq for sq in state.subquestions if sq.evidence_ids]
    for number, sq in enumerate(state.subquestions, 1):
        # note 를 여러 분기에 붙인다. 근거가 0편인 하위질문은 아래 insufficient
        # 분기에 닿지 못하는데, 정작 "왜 못 찾았는지"가 가장 필요한 경우다.
        # 판정을 못 받았을 때의 note 는 '왜'가 아니라 같은 실패의 반복이라 뺀다 —
        # 아래 집계 문장이 따로 센다.
        note = _memo(sq.note) if sq.note and not sq.parse_failed else ""
        n = len(sq.evidence_ids)
        topic = _topic(sq.text)
        blocked = sq.capped or sq.budget_capped
        # failed·상한을 "근거 없음"보다 먼저 본다. 시스템 장애나 우리 쪽 상한을
        # "근거를 찾지 못했다"로 쓰면 연구 결과(코퍼스 빈틈)로 둔갑한다.
        if sq.failed and n:
            out.append(
                f"{topic} 탐색이 오류로 중단돼 끝까지 확인하지 못했다"
                f"(중단 전까지 모은 근거 {n}편으로만 썼다){note}"
            )
        elif sq.failed:
            out.append(f"{topic} 탐색 중 오류로 확인하지 못했다{note}")
        elif not n and sq.excluded_cnts:
            # 자기점검이 실제 근거를 읽고 모두 뺐다 — 상한 분기로 보내면 이 원인과 note 가 가려지고,
            # '근거를 찾지 못했다'(코퍼스 빈틈)로 쓰면 찾아서 읽은 사실이 사라진다
            cap = f"({_capped_clause(state, sq, '후보')} 더 싣지 못했다)" if blocked else ""
            out.append(f"'{sq.text}' 에 대해서는 모은 논문 {len(sq.excluded_cnts)}편이 모두 "
                       f"하위질문과 무관해 근거에서 뺐다{cap}{note}")
        elif not n and blocked:
            # 상한 때문에 0편이면 critic 은 "(없음)"을 보고 판정한다 — 그 note 는 오보다
            out.append(f"{topic} {_capped_clause(state, sq, '검색된 논문')} 싣지 못했다")
        elif not n:
            out.append(f"'{sq.text}' 에 대해서는 근거를 찾지 못했다{note}")
        elif sq.verdict == "insufficient":
            # 판정을 적는다 — '근거 N편으로 결론이 약하다' 는 편수 탓으로 읽혀, critic 이 발췌가 핵심 개념을 다루지
            # 않는다고 본 13편 하위질문이 5편 '충분' 옆에서 모순으로 보였다(운영 d60a5dc1). 편수는 판정 신호의
            # 하나일 뿐이고(research_critique.yaml) 까닭은 note 가 말한다. '근거 부족' 은 탐색 경로 라벨과 같은 말이다
            # 주어는 절 번호다 — 하위질문 전문을 쓰면 계획이 낸 하위질문들이 같은 앞머리를 공유해 부족 줄 다섯이
            # 같은 45자로 시작하고 줄마다 280~310자가 됐다(운영 630e0d65). 근거가 있으니 늘 절이 있고, 절 제목이
            # 곧 하위질문이라 바로 위에서 찾는다. 앞에 근거 0편 하위질문이 있으면 절 번호가 당겨져 하위질문 번호와
            # 어긋난다 — 그때만 하위질문 번호를 함께 적는다. 보고서 옆 과정 패널과 내려받은 문서의 '부록: 탐색 경로'는
            # 하위질문을 0편까지 세어 번호 매겨, '2절' 만 쓰면 그쪽의 '2.'(다른 하위질문)를 가리키는 것으로 읽힌다
            k = next(i for i, s in enumerate(sectioned, 1) if s is sq)
            where = f"{k}절" if k == number else f"{k}절(하위질문 {number})"
            cap = f"({_capped_clause(state, sq, '후보')} 더 싣지 못했다)" if blocked else ""
            out.append(f"{where}은 근거 {n}편을 모았으나 자기점검에서 '근거 부족'으로 판정했다{cap}{note}")

    # 근거가 0편이면 충분성을 따질 대상이 없고, failed 는 위에서 이미 알렸다
    unchecked = sum(1 for sq in state.subquestions
                    if sq.parse_failed and sq.evidence_ids and not sq.failed)
    if unchecked:
        out.append(
            f"자동 점검을 완료하지 못한 하위질문이 {unchecked}건 있다 — "
            f"그 부분의 근거 충분성은 확인되지 않았다."
        )

    if failed_sections:
        out.append(
            f"서술을 생성하지 못한 절이 {failed_sections}개 있다 — "
            f"그 절은 근거 논문 목록만 싣는다."
        )

    if introless_sections:
        out.append(f"도입 문단을 생성하지 못한 절이 {introless_sections}개 있다.")

    if unsummarized_total:
        out.append(f"요약을 생성하지 못한 논문 {unsummarized_total}편이 있다.")

    if dropped_total:
        out.append(
            f"그 절의 근거에 없는 번호를 가리킨 인용 표기 "
            f"{dropped_total}건을 본문에서 제거했다."
        )

    if unparsed_total:
        out.append(f"해석할 수 없는 인용 표기 {unparsed_total}건을 본문에서 제거했다.")

    if unmarked_total >= UNMARKED_THRESHOLD:
        out.append(f"근거 표기가 없는 서술 {unmarked_total}건이 있다.")
    return out


def _evidence_entry(ev: Evidence, keep: list[Chunk]) -> dict:
    """report.evidence 한 항목의 모양. 청크는 점수순으로 싣는다.

    완성본(_serialize_evidence)과 작성 중 초안(section_evidence)이 이 함수 하나로 만든다 —
    따로 만들면 한쪽 모양만 바뀌어 초안과 완성본의 인용칩 팝오버가 조용히 갈린다.
    """
    return {
        "cnts_id": ev.cnts_id,
        "meta": ev.meta,
        "chunks": [asdict(c) for c in sorted(keep, key=lambda c: c.score, reverse=True)],
    }


def _cited(state: ResearchState, section: dict) -> list[str]:
    """다듬은 절(finalize_section) 하나가 인용한 근거 번호 — 대표 논문·도입·향후 과제의 칩 전부."""
    # 다듬은 도입에는 표준형 [E#] 만 남는다 — bind_markers 의 used 로 읽는다. 여기서 정규식을
    # 다시 쓰면 마커 문법이 두 곳으로 갈라진다.
    cited = list(bind_markers(section.get("intro", ""), set(state.evidence)).used)
    for item in (*section.get("papers", []), *section.get("future", [])):
        cited.extend(item.get("evidence", []))
    return cited


def _serialize_evidence(state: ResearchState, cited: set[str]) -> dict:
    """보고서의 근거 목록. 절에 실린(cited) 근거만, 청크는 지금 어느 하위질문이든 가리키는 것만
    점수순으로 싣는다.

    채택한 근거를 전부 싣지 않는 이유: 절은 하위질문마다 앞 5편만 쓰므로 나머지는 어느 칩도
    가리키지 않는다. 그대로 두면 상한을 올릴수록 보고서 JSON 만 분다. 채택 수는 stats 가 센다.

    Evidence.chunks 는 매칭된 적 있는 청크의 저장소라 재검색이 갈아끼운 대목도 남아 있다.
    그대로 실으면 어느 절도 그 대목으로 쓰지 않았는데 삽입 순서대로 chunks[0] 에 나간다.
    매핑 없이 이 근거를 보는 하위질문이 있으면(옛 스냅샷) chunks_for 처럼 전부 싣는다.
    """
    mapped: dict[str, set[str]] = {}
    unmapped: set[str] = set()
    for sq in state.subquestions:
        for eid, ids in sq.evidence_chunks.items():
            mapped.setdefault(eid, set()).update(ids)
        unmapped.update(e for e in sq.evidence_ids if not sq.evidence_chunks.get(e))

    def _shown(eid: str, ev: Evidence) -> list[Chunk]:
        if eid in unmapped or eid not in mapped:
            return ev.chunks
        return [c for c in ev.chunks if c.chunk_id in mapped[eid]]

    return {eid: _evidence_entry(ev, _shown(eid, ev))
            for eid, ev in state.evidence.items() if eid in cited}


def section_evidence(state: ResearchState, section: dict) -> dict[str, dict]:
    """다듬은 절(finalize_section) 하나가 인용한 근거만 report.evidence 와 같은 모양으로 만든다.

    작성 중 초안의 인용칩 팝오버가 쓴다. 근거 전체를 절마다 실으면 절이 쌓일수록 같은 대목을
    거듭 나른다. 대목은 이 절이 매칭한 것(evidence_chunks)만 점수순으로 싣고, 매핑이 없으면
    _serialize_evidence 와 같이 전부 싣는다.
    """
    mapped = section.get("evidence_chunks", {})
    out: dict[str, dict] = {}
    for eid in _cited(state, section):
        if eid in out:
            continue
        # finalize_section 은 근거에 있는 번호만 남긴다 — 어기면 KeyError 로 바로 드러난다
        ev = state.evidence[eid]
        ids = set(mapped.get(eid) or [])
        out[eid] = _evidence_entry(ev, [c for c in ev.chunks if c.chunk_id in ids] if ids
                                   else ev.chunks)
    return out


@dataclass
class SectionTally:
    """절 하나를 다듬으며 센 검증 결과. 보고서의 한계 문장은 이것을 절마다 더한 값이다."""
    unmarked: int = 0
    dropped: int = 0
    unparsed: int = 0
    unsummarized: int = 0
    failed: int = 0
    introless: int = 0

    def add(self, other: "SectionTally") -> None:
        # 칸을 손으로 나열하지 않는다 — 칸을 더하고 여기서 빠뜨리면 한계 문장이 조용히 준다
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))


def finalize_section(state: ResearchState, sec: dict) -> tuple[dict, SectionTally]:
    """모델 출력으로 만든 절(build_section)을 보고서에 싣는 모양으로 다듬는다 (순수 함수).

    작성 중 초안(절마다 워커가 미리 보여 준다)과 최종 보고서가 이 함수 하나를 쓴다 — 따로
    다듬으면 초안에서 읽은 글과 완성본의 글이 갈린다.

    마커 검증 결과는 bind_markers 호출마다 누적한다. 절마다 도입·향후 과제로 여러 번
    부르므로 한 번의 반환값만 읽으면 나머지 호출에서 지운 표기가 조용히 사라진다. dropped 는
    번호 종류가 아니라 본문에 박힌 표기 수로 센다 — 사용자가 보는 단위가 그것이다.
    """
    by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
    tally = SectionTally()
    failed = bool(sec.get("failed"))
    # 모델은 절마다 그 절의 논문만 받는다 — 검증도 그 번호로 한정한다. 근거
    # 번호가 E1..En 으로 연속 발급되므로 전역 집합으로 검증하면 모델이 지어낸
    # 작은 번호는 거의 다 통과하고, 본 적 없는 논문을 가리키는 칩이 생긴다.
    valid = {by_cnts[p["cnts_id"]] for p in sec.get("papers", []) if p["cnts_id"] in by_cnts}
    intro = bind_markers(sec.get("intro", ""), valid)
    tally.unmarked += intro.unmarked
    tally.dropped += len(intro.dropped)
    tally.unparsed += len(intro.unparsed)
    # 칩만 남은 도입("[E1]")은 문장이 아니다 — 도입 없음으로 센다
    intro_text = intro.text if _prose(intro.text) else ""
    if failed:
        tally.failed += 1
    elif not intro_text:
        tally.introless += 1

    papers = []
    for p in sec.get("papers", []):
        eid = by_cnts.get(p["cnts_id"])
        if eid is None:
            continue                      # 근거에 없는 논문은 싣지 않는다
        summary = strip_markers(p.get("summary", ""))
        if not _prose(summary):
            summary = ""                  # "[E1]." 에서 번호만 걷으면 마침표 하나가 남는다
        # 서술이 통째로 실패한 절은 위의 failed 로 이미 센다 —
        # 그 절의 논문을 요약 누락으로 또 세면 실패가 두 건처럼 보인다.
        if not summary and not failed:
            tally.unsummarized += 1
        papers.append({
            "cnts_id": p["cnts_id"],
            "summary": summary,
            "evidence": [eid],            # 구조적 인용 — 모델이 고르지 않는다
        })

    future = []
    for f in sec.get("future", []):
        res = bind_markers(f.get("text", ""), valid)
        tally.unmarked += res.unmarked
        tally.dropped += len(res.dropped)
        tally.unparsed += len(res.unparsed)
        # 지운 번호는 위에서 이미 셌다. 마커만 있던 항목은 빈 불릿이나 칩 하나짜리
        # 불릿이 되므로 싣지 않는다.
        if not _prose(res.text):
            continue
        # used 를 bind_markers 가 돌려준다 — 여기서 정규식을 다시 쓰면
        # 마커 문법이 두 곳으로 갈라진다.
        future.append({"text": res.text, "evidence": res.used})

    return {
        "heading": sec.get("heading", ""),
        "intro": intro_text, "papers": papers, "future": future,
        # 근거 ID → 이 절에서 매칭된 청크 ID. 한 논문이 여러 절에 실리면
        # evidence.chunks 는 그 합집합이라, 호버는 이걸로 그 절의 대목을 고른다.
        "evidence_chunks": sec.get("evidence_chunks", {}),
        # 청크 ID → 이 절의 하위질문 검색어로 받은 점수. 두 절이 한 청크를 쓰면
        # evidence.chunks[].score(최고값) 하나로는 한쪽 절에 남의 점수가 뜬다.
        "chunk_scores": sec.get("chunk_scores", {}),
    }, tally


def _excluded_papers(sq: SubQuestion) -> list[dict]:
    """하위질문이 무관하다고 뺀 논문의 서지 요약을 회차 순으로 잇는다. 한 번 뺀 논문은 같은 하위질문에
    다시 들지 않으니(runner) 중복이 없다. 보강 전 회차 기록에는 excluded_papers 가 없다."""
    return [p for r in sq.rounds for p in r.get("excluded_papers", [])]


def assemble_report(
    state: ResearchState, sections: list[dict], *, unmarked_total: int,
) -> dict:
    tally = SectionTally(unmarked=unmarked_total)
    out_sections = []
    cited: set[str] = set()
    for sec in sections:
        section, counted = finalize_section(state, sec)
        out_sections.append(section)
        tally.add(counted)
        cited.update(_cited(state, section))

    return {
        "question": state.question,
        "range": state.corpus_range,
        "sections": out_sections,
        "evidence": _serialize_evidence(state, cited),
        "trail": [
            {"subquestion": sq.text, "queries": sq.queries,
             "evidence_count": len(sq.evidence_ids),
             "verdict": sq.verdict, "note": sq.note,
             "parse_failed": sq.parse_failed, "failed": sq.failed, "capped": sq.capped,
             # 자기점검이 이 하위질문에서 무관하다고 뺀 논문 수 — 한 번 뺀 논문은 다시 들지 않는다
             "excluded": len(sq.excluded_cnts),
             # 보고서의 '관련성이 낮아 제외한 논문'과 문서 부록 — 풀에서 지운 논문도 서지가 남는다
             "excluded_papers": _excluded_papers(sq),
             # 무관 제외를 끈 잡이 무관하다고 본 논문 수(켠 잡은 0) — 켠 잡의 excluded 와 같은 쿼리로 나란히
             # 본다. 회차 기록의 flagged 는 처음 가리킨 논문만 센다(runner)
             "flagged": sum(r.get("flagged", 0) for r in sq.rounds)}
            for sq in state.subquestions
        ],
        "limitations": build_limitations(
            state, unmarked_total=tally.unmarked, dropped_total=tally.dropped,
            failed_sections=tally.failed, unsummarized_total=tally.unsummarized,
            unparsed_total=tally.unparsed, introless_sections=tally.introless,
        ),
        "stats": research_stats(state),
    }


def section_paper_ids(state: ResearchState, sq: SubQuestion) -> list[str]:
    return sq.evidence_ids[:PAPERS_PER_SECTION]


def _text(value: object) -> str:
    """모델 출력의 문장 필드 하나를 문자열로 만든다.

    문장 배열은 잇는다 — str() 로 바꾸면 "['문장1', '문장2']" 가 화면에 나간다.
    그 밖의 모양(null·숫자·dict)은 버린다. null 이 bind_markers 까지 가면 모든 절
    호출이 끝난 뒤 TypeError 로 보고서 전체를 잃는다.

    대목에서 옮겨 온 남의 번호 인용('[3, 4]')은 여기서 지운다(strip_numbered_refs) — 되풀이 지우기(drop_repeats)·
    작성 중 초안·완성본이 모두 이 글을 쓴다.
    """
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
        text = " ".join(v.strip() for v in value if v.strip())
    else:
        return ""
    return "" if _PLACEHOLDER in text else strip_numbered_refs(text)


def _eid_key(key: str) -> str:
    m = _EID_KEY.fullmatch(key)
    return f"E{int(m.group(1))}" if m else key


def build_section(state: ResearchState, sq: SubQuestion, data: dict | None,
                  excerpts: dict[str, Chunk] | None = None) -> dict:
    """하위질문 하나와 모델 출력으로 절을 만든다 (순수 함수).

    소제목은 하위질문 그대로, 논문 목록은 section_paper_ids 그대로다 — 모델
    출력에 무엇이 있든 없든 바뀌지 않는다. 모델이 요약을 빠뜨린 논문도 빈
    요약으로 싣고 assemble_report 가 개수를 한계에 올린다(_synthesize_section 이 그 전에
    한 번 다시 묻는다). data 가 None(서술을
    끝내 받지 못함)이면 논문 목록만 남기고 failed 로 표시한다.

    excerpts(pick_excerpts — 모델이 읽은 대목)가 있으면 그 대목을 evidence_chunks[eid] 맨 앞에 둔다. 인용칩
    팝오버는 이 순서로 대목을 띄우므로 첫 대목이 요약·도입이 읽은 대목과 같아진다. 다른 하위질문에서 빌려 온
    대목이면 이 절의 매칭 대목 앞에 더한다 — 이 하위질문의 검색어로 받은 점수가 없어 chunk_scores 에는 싣지 않는다.
    """
    raw = data or {}
    summaries = raw.get("summaries")
    summaries = ({_eid_key(str(k)): _text(v) for k, v in summaries.items()}
                 if isinstance(summaries, dict) else {})
    future = raw.get("future")
    future_texts = []
    for f in future if isinstance(future, list) else []:
        text = _text(f.get("text") if isinstance(f, dict) else f)
        if text:
            future_texts.append(text)
    eids = section_paper_ids(state, sq)
    chunks = {eid: chunks_for(state.evidence[eid], sq) for eid in eids}
    read = excerpts or {}

    def _shown_first(eid: str, cs: list[Chunk]) -> list[str]:
        ids = [c.chunk_id for c in cs]
        first = read.get(eid)
        return ids if first is None else [first.chunk_id, *(i for i in ids if i != first.chunk_id)]

    return {
        "heading": sq.text,
        "intro": _text(raw.get("intro")),
        "papers": [
            {"cnts_id": state.evidence[eid].cnts_id, "summary": summaries.get(eid, "")}
            for eid in eids
        ],
        "future": [{"text": t} for t in future_texts],
        "evidence_chunks": {eid: _shown_first(eid, cs) for eid, cs in chunks.items()},
        "chunk_scores": {c.chunk_id: c.score for cs in chunks.values() for c in cs},
        "failed": data is None,
    }


def _prose(text: str) -> str:
    """인용 표기를 걷어낸 문장. 마커만 있는 필드는 빈 문자열이다."""
    return strip_markers(text).strip(" \t\n.,;:")


def _has_narrative(section: dict) -> bool:
    """검증 전 출력으로 판정하므로 문장 기준으로 본다. 마커만 있는 도입·과제를
    서술로 세면 assemble_report 에서 지워진 뒤 서술 0줄이 되는데도, 재시도와
    '전부 실패' 가드를 건너뛰어 completed 로 남는다."""
    return bool(
        _prose(section["intro"])
        or any(_prose(f["text"]) for f in section["future"])
        or any(_prose(p["summary"]) for p in section["papers"])
    )


def _unsummarized(state: ResearchState, sq: SubQuestion, section: dict) -> list[str]:
    """요약이 없는 논문의 근거 번호(절의 논문 순서). finalize_section 이 '요약을 생성하지 못한 논문'으로 세는 것과
    같은 기준이다 — 키가 없거나, 값이 빈 글·마커뿐('[E2]')인 요약. build_section 은 논문을 section_paper_ids 순서로
    싣는다."""
    return [eid for eid, p in zip(section_paper_ids(state, sq), section["papers"]) if not _prose(p["summary"])]


def _sentences(text: str) -> list[str]:
    """문장 단위로 나눈다. 마침표 뒤에 붙은 마커 묶음('…다. [E1] 다음')은 앞 문장에 붙인다 — bind_markers 가 셀 때와
    같은 관례다. 다만 마커 바로 뒤가 '연구는'·조사면 다음 문장의 주어라 그 문장에 둔다(_MARKER_AS_SUBJECT)."""
    out: list[str] = []
    for piece in _SENTENCE_BREAK.split(text.strip()):
        lead = _LEADING_BRACKETS.match(piece)
        # strip_markers 가 다 걷어 내야 인용 표기 묶음이다 — '[표 1]' 같은 괄호는 문장의 글이다
        if (lead and out and not strip_markers(lead.group(0))
                and not _MARKER_AS_SUBJECT.match(piece[lead.end():])):
            out[-1] = f"{out[-1]} {lead.group(0).strip()}"
            piece = piece[lead.end():]
        if piece.strip():
            out.append(piece.strip())
    return out


def _sentence_key(sentence: str) -> str:
    return _NON_WORD.sub("", strip_markers(sentence))


def _repeats(key: str, seen: list[str]) -> bool:
    if len(key) < _REPEAT_KEY_MIN:
        return False
    for prev in seen:
        sm = difflib.SequenceMatcher(None, key, prev)
        if (sm.real_quick_ratio() >= _REPEAT_RATIO and sm.quick_ratio() >= _REPEAT_RATIO
                and sm.ratio() >= _REPEAT_RATIO):
            return True
    return False


def drop_repeats(section: dict, seen: list[str]) -> tuple[dict, list[str]]:
    """앞 절과 거의 같은 도입 문장·향후 과제, 그리고 도입의 메타 문장을 지운다 (순수 함수).

    절마다 따로 부르므로 모델은 앞 절에서 쓴 문장을 모른다. 같은 논문의 같은 대목이 여러 절에 들어가면 같은 문장이
    절마다 되풀이됐다(운영 630e0d65 — 1·2·4·5절 도입 첫 문장, 4개 절의 같은 향후 과제). pick_excerpts 가 대목을
    갈라도 같은 논문의 대목이 하나뿐이면 남는다.

    seen 은 앞 절들에 남은 문장의 비교 키다. (다듬기 전 절, 이 절에 남은 문장의 비교 키)를 돌려준다 — 부르는 쪽이
    seen 에 더한다. 대표 논문 요약은 건드리지 않는다(논문마다 하나라 되풀이가 아니다). 도입에서 남는 서술이 없으면
    도입은 원문 그대로 둔다 — 비우면 '도입 문단을 생성하지 못한 절' 한계 줄이 잘못 붙는다. 향후 과제는 비어도 된다.
    """
    intro = section.get("intro", "")
    sentences = _sentences(intro)
    kept = [s for s in sentences
            if not _META_SENTENCE.match(s) and not _repeats(_sentence_key(s), seen)]
    if len(kept) == len(sentences):
        trimmed = intro                    # 지운 것이 없으면 줄바꿈까지 원문 그대로
    elif _prose(" ".join(kept)):
        trimmed = " ".join(kept)
    else:
        trimmed, kept = intro, sentences
    future = [f for f in section.get("future", []) if not _repeats(_sentence_key(f["text"]), seen)]
    keys = [k for k in map(_sentence_key, [*kept, *(f["text"] for f in future)]) if k]
    return {**section, "intro": trimmed, "future": future}, keys


def excerpt_text(chunk: Chunk) -> str:
    """모델에 넘기는 대목 글 — HTML 이스케이프(&lt; &amp;)를 풀고 <br> 을 줄바꿈으로 바꾼 앞 EXCERPT_CHARS 자.
    적재된 표·초록 글에 이스케이프가 그대로 남아 있어 모델이 '&lt;기초학습기능검사&gt;' 를 읽었다."""
    return _BR.sub("\n", html.unescape(chunk.text))[:EXCERPT_CHARS]


def _narrative(chunk: Chunk) -> bool:
    """모델이 읽을 창(excerpt_text)에 그 논문의 서술 문장이 있는가. 아닌 것은 둘이다.

    - 표: '|' 가 둘 이상인 줄이 창의 _TABLE_SHARE 이상. 선행연구 정리표의 한 행만 받은 모델은 표 속 남의 연구를 그
      논문의 성과로 썼다(운영 630e0d65 박혜성 2014 — '정금자, 이영숙 (2013)|만 5세 유아…').
    - 완결 문장이 없는 창: 창 끝에서 잘린 조각은 버리고 본다. 참고문헌 꼬리 + 영문 제목 + '<Abstract> This s' 로 400자가
      끝난 대목은 요약이 제목을 다시 쓴 한 문장이 됐다(같은 보고서 황상심 2009).
    """
    window = excerpt_text(chunk)
    rows = [line for line in window.splitlines() if line.count("|") >= 2]
    if window and sum(len(r) for r in rows) >= _TABLE_SHARE * len(window):
        return False
    stops = list(_SENTENCE_STOP.finditer(window))
    body = window[:stops[-1].end()] if stops else ""
    return has_prose(body) or bool(_ENGLISH_VERBS.search(body))


def _borrowed(state: ResearchState, ev: Evidence, own: list[Chunk]) -> list[Chunk]:
    """그 논문이 다른 하위질문에서 매칭한 서술 대목(점수순). 지금 어느 하위질문이든 가리키는 대목만 —
    _serialize_evidence 가 그 대목만 보고서 근거에 싣는다. 재검색이 갈아끼운 대목을 쓰면 칩이 빈 팝오버를 연다."""
    own_ids = {c.chunk_id for c in own}
    mapped = {i for s in state.subquestions for i in s.evidence_chunks.get(ev.id, [])}
    return sorted((c for c in ev.chunks
                   if c.chunk_id in mapped and c.chunk_id not in own_ids and _narrative(c)),
                  key=lambda c: c.score, reverse=True)


def pick_excerpts(state: ResearchState, sq: SubQuestion,
                  shown: set[tuple[str, str]]) -> dict[str, Chunk]:
    """절의 논문마다 모델에 넘길 대목 하나를 고른다 (순수 함수). 근거 번호 → 대목.

    그 하위질문이 매칭한 대목(chunks_for, 점수순) 가운데 서술 대목(_narrative)을 쓰고, 그중 앞 절에서 이 논문으로
    이미 보여 준 대목(shown — (근거 번호, 청크 ID))은 뒤로 미룬다. 한 논문이 여러 절에 실리면 각 하위질문의 1위
    대목이 같은 때가 많아(운영 630e0d65 장 2019 의 같은 대목이 1·2·4·5절 1위) 절마다 같은 문장이 되풀이됐고,
    2위였던 연구방법 대목은 방법 절에서도 모델에 가지 않았다.

    그 하위질문의 대목이 모두 서술이 아니면 다른 하위질문이 매칭한 그 논문의 서술 대목을 빌린다(_borrowed) —
    하위질문과 덜 맞더라도 그 논문 자신의 글이다. 그것도 없으면 지금처럼 1위 대목을 쓴다.
    """
    picked: dict[str, Chunk] = {}
    for eid in section_paper_ids(state, sq):
        ev = state.evidence[eid]
        # 그 하위질문 검색에서 매칭된 대목이 먼저다 — 재사용 근거의 첫 청크는 다른 하위질문의 검색어로 뽑힌 것일 수 있다
        own = chunks_for(ev, sq)
        pool = [c for c in own if _narrative(c)] or _borrowed(state, ev, own) or own
        fresh = [c for c in pool if (eid, c.chunk_id) not in shown]
        if pool:
            picked[eid] = (fresh or pool)[0]
    return picked


def _evidence_block(state: ResearchState, sq: SubQuestion, excerpts: dict[str, Chunk]) -> str:
    lines = []
    for eid in section_paper_ids(state, sq):
        ev = state.evidence[eid]
        chunk = excerpts.get(eid)
        lines.append(
            f"[{eid}] {ev.meta.get('title')} "
            f"({ev.meta.get('pub_date')}, {ev.meta.get('series_title')})\n"
            f"{excerpt_text(chunk) if chunk else ''}"
        )
    return "\n\n".join(lines)


async def _synthesize_section(
    state: ResearchState, sq: SubQuestion, excerpts: dict[str, Chunk],
    *, should_stop: Callable[[], Awaitable[bool]] | None,
) -> dict:
    """절 하나를 만든다. excerpts 는 pick_excerpts 가 고른 대목이다.

    전송 오류·해석 실패·서술 없는 응답은 한 번 다시 부르고, 그래도 안 되면
    논문 목록만 남긴 절(failed)을 돌려준다 — 한 절의 실패가 이미 받은 다른
    절을 버리게 두지 않는다.

    서술은 있지만 summaries 에서 논문 요약을 빠뜨린 응답(_unsummarized)도 같은 횟수 안에서 다시 부른다 — 프롬프트가
    번호를 빠짐없이 키로 넣으라고 하는데도 빠뜨린 형식 위반이다(A/B focus2 85d2 3절 E11, 48호출 중 1건). 끝내 다
    채우지 못하면 빠진 논문이 가장 적은 응답을 싣는다. 빠진 논문은 지금처럼 빈 요약으로 나가고 finalize_section 이
    '요약을 생성하지 못한 논문' 한계로 센다 — 절을 failed 로 돌리면 이미 받은 도입·요약까지 잃는다.
    """
    system, user, llm_params = get_prompt("research_synthesize").render(
        question=state.question, subquestion=sq.text,
        evidence_block=_evidence_block(state, sq, excerpts),
        paper_ids=", ".join(section_paper_ids(state, sq)),
    )
    # 서술은 있으나 요약이 빠진 응답 가운데 빠진 논문이 가장 적은 것 — (절, 빠진 근거 번호)
    partial: tuple[dict, list[str]] | None = None
    for attempt in range(1, _SECTION_ATTEMPTS + 1):
        if should_stop is not None and await should_stop():
            raise SynthesisCanceled
        try:
            raw = await chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                params=llm_params, timeout=300.0,
            )
        except httpx.HTTPError as e:
            log.warning("[research] 절 종합 호출 실패 job=%s idx=%s 시도=%d — %s: %s",
                        state.job_id, sq.idx, attempt, type(e).__name__, e)
            continue
        # 공용 추출기를 쓴다. 여기서 다시 구현하지 마라 —
        # body[index("{"):rindex("}")+1] 은 JSON 뒤에 } 를 포함한 산문이 붙으면
        # 그 끝까지 먹어 파싱이 깨진다.
        data = extract_json(raw)
        if data is None:
            log.error("[research] 절 종합 JSON 파싱 실패 job=%s idx=%s 시도=%d: %s",
                      state.job_id, sq.idx, attempt, (raw or "")[:300])
            continue
        section = build_section(state, sq, data, excerpts)
        # 파싱만으로 성공을 판정하면 키가 다른 dict·빈 dict 가 성공으로 세어져,
        # 모든 절이 그렇게 와도 아래 '전부 실패' 가드를 빠져나간다.
        if not _has_narrative(section):
            log.error("[research] 절 종합 응답에 서술이 없다 job=%s idx=%s 시도=%d: %s",
                      state.job_id, sq.idx, attempt, (raw or "")[:300])
            continue
        missing = _unsummarized(state, sq, section)
        if not missing:
            return section
        log.warning("[research] 절 종합 응답에 요약이 빠졌다 job=%s idx=%s 시도=%d 빠진=%s",
                    state.job_id, sq.idx, attempt, missing)
        if partial is None or len(missing) < len(partial[1]):
            partial = (section, missing)
    if partial is not None:
        log.warning("[research] 절 종합 — 요약이 빠진 채 싣는다 job=%s idx=%s 빠진=%s",
                    state.job_id, sq.idx, partial[1])
        return partial[0]
    return build_section(state, sq, None)


async def synthesize(
    state: ResearchState, *, should_stop: Callable[[], Awaitable[bool]] | None = None,
    on_section: SectionFn | None = None,
) -> dict:
    """하위질문마다 절을 하나씩 만든다.

    근거가 없는 하위질문은 절을 만들지 않는다 — 한계 섹션이 그 사실을 적는다.
    탐색이 도중에 실패한 하위질문이라도 그 전에 모은 근거가 있으면 절을 만든다.
    빼면 실재하는 근거가 보고서에서 사라지고(report.evidence 는 절에 실린 근거만 담는다),
    한계에는 사실과 다른 "확인하지 못했다"만 실린다.

    일부 절의 실패는 한계로 보고하고 넘어가지만, 전부 실패하면 예외를 던진다.
    서술이 한 줄도 없는 보고서를 completed 로 두면 재시도(stage=explored 에서
    재개) 기회가 사라진다.

    should_stop 은 LLM 을 부르기 직전마다 확인하고, True 면 SynthesisCanceled 를
    던진다 — 취소 뒤에도 남은 절을 다 부르면 GPU 를 비운다는 취소의 약속이 거짓이 된다.

    on_section(idx, total, status, info) 는 절을 쓰기 시작할 때 "running", 끝낼 때 "done"
    또는 "failed" 로 부른다. idx 는 절 순번(0부터)이지 하위질문 번호가 아니다 — 근거
    없는 하위질문은 절이 되지 않아 둘이 어긋나고, 화면의 "2/3" 은 절 순번으로 센다.
    info 는 {subq_idx, heading, headings(쓸 절 전부의 소제목, 절 순서)} 이고, 끝낼 때는
    finalize_section 으로 다듬은 절(section)과 그 절이 인용한 근거(evidence)를 더한다 —
    화면이 다 쓴 절부터 초안으로 보여 준다. 서술을 받지 못한 절(failed)도 최종본처럼
    논문 목록만 있는 절로 싣는다.
    """
    on_section = on_section or _no_progress
    targets = [sq for sq in state.subquestions if sq.evidence_ids]
    # 첫 절을 쓰는 동안에도 화면이 남은 절을 "작성 대기"로 그릴 수 있게 소제목을 전부 싣는다
    headings = [sq.text for sq in targets]
    sections = []
    # 앞 절들이 모델에 보여 준 (근거 번호, 청크 ID) — pick_excerpts 가 같은 논문의 다른 대목을 먼저 고른다
    shown: set[tuple[str, str]] = set()
    # 앞 절들에 남은 도입 문장·향후 과제의 비교 키 — drop_repeats
    seen: list[str] = []
    for i, sq in enumerate(targets):
        info = {"subq_idx": sq.idx, "heading": sq.text, "headings": headings}
        await on_section(i, len(targets), "running", info)
        excerpts = pick_excerpts(state, sq, shown)
        section = await _synthesize_section(state, sq, excerpts, should_stop=should_stop)
        if not section["failed"]:
            # 서술을 받지 못한 절의 대목은 보고서 어디에도 쓰이지 않았다 — 다음 절이 피할 까닭이 없다
            shown.update((eid, c.chunk_id) for eid, c in excerpts.items())
            # 초안(on_section)을 다듬기 전에 지운다 — 초안과 완성본이 같은 절을 쓴다
            section, kept = drop_repeats(section, seen)
            seen.extend(kept)
        sections.append(section)
        log.info("[research] 절 종합 job=%s idx=%s 논문=%d ok=%s",
                 state.job_id, sq.idx, len(section["papers"]), not section["failed"])
        preview, _ = finalize_section(state, section)
        await on_section(i, len(targets), "failed" if section["failed"] else "done",
                         {**info, "section": preview,
                          "evidence": section_evidence(state, preview)})

    if targets and all(s["failed"] for s in sections):
        raise ValueError("보고서의 어느 절도 서술을 받지 못했다")

    return assemble_report(state, sections, unmarked_total=0)
