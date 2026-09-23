"""citations.py — 근거 조립과 인용 마커 검증 (순수 함수)

인용은 두 종류다.

구조적 인용 — `대표 논문 요약`은 불릿 하나가 논문 하나라, 그 논문의 근거만
넣고 생성하면 인용이 추론이 아니라 구조로 정해진다. 모델이 고를 일이 없다.

마커 인용 — `도입 문단`·`향후 과제`는 여러 논문을 가로지르므로 구조로 못
정한다. 모델이 [E3] 로 달게 하고 여기서 전수 검증한다. 해석 안 되는 마커는
조용히 통과시키지 않고 제거한 뒤 개수를 보고한다.

근거 ID(E1·E2·...) 는 runner 가 state.evidence 에 넣는 시점에 붙인다 —
evidence 네임스페이스를 소유한 쪽이 번호도 소유해야 한다. build_evidence
는 순서만 보장하고(hits 등장 순서) 번호는 매기지 않는다.
"""
import re
from typing import NamedTuple

from services.research.state import Chunk, Evidence, HitRow

_MARKER = re.compile(r"[ \t]*\[(E\d+)\]")
_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+")
# 마침표 뒤에 붙는 마커 묶음("문장이다. [E1] [E2]")을 셀 때만 통째로 문장
# 앞으로 당긴다 — LLM 이 마커를 문장 끝 마침표 뒤에 다는 게 흔해서, 그대로
# 세면 근거가 있는 문장이 무근거로 오분류된다. 마커 하나만 당기면 뒤에
# 남은 마커가 다음 문장 소속으로 잘못 잡혀 과소 계수된다. 계수용 사본에만
# 쓰므로 치환 뒤 공백이 지저분해도 무해하다. 반환 텍스트에는 적용하지 않는다.
_TRAILING_MARKER = re.compile(r"([.!?。])(\s+)((?:\[E\d+\][ \t]*)+)")


def evidence_id(index: int) -> str:
    return f"E{index + 1}"


def build_evidence(
    hits: list[HitRow],
    meta_by_id: dict[str, dict],
    *,
    chunks_per_evidence: int,
) -> list[Evidence]:
    """검색 결과를 논문 단위 근거로 묶는다.

    같은 논문의 청크 여러 개는 근거 하나가 되고, 점수 높은 순으로
    chunks_per_evidence 개만 남긴다(호버 팝업의 1/2 페이지네이션).
    카탈로그에 메타가 없는 청크는 버린다 — 서지를 못 보여주면 근거가 아니다.

    반환 순서는 hits 안에서 각 논문이 처음 등장한 순서다(hits 는 호출 전에
    점수 내림차순으로 정렬돼 들어온다는 전제). id 는 비워둔다 — runner 가
    state.evidence 에 넣으며 evidence_id() 로 채운다.
    """
    grouped: dict[str, list[HitRow]] = {}
    for hit in hits:
        cnts_id = hit["book_id"]
        if cnts_id not in meta_by_id:
            continue
        grouped.setdefault(cnts_id, []).append(hit)

    result: list[Evidence] = []
    for cnts_id, rows in grouped.items():
        rows.sort(key=lambda r: r["score"], reverse=True)
        result.append(Evidence(
            id="",
            cnts_id=cnts_id,
            meta=meta_by_id[cnts_id],
            chunks=[
                Chunk(
                    chunk_id=r["chunk_id"], text=r["text"],
                    page_start=r["page_start"], page_end=r["page_end"],
                    score=r["score"],
                )
                for r in rows[:chunks_per_evidence]
            ],
        ))
    return result


class MarkerResult(NamedTuple):
    text: str
    dropped: list[str]
    used: list[str]      # 등장 순서, 중복 제거 — 유효한 마커를 다시 정규식으로 훑지 않고 여기서 재사용한다
    unmarked: int


def bind_markers(text: str, valid_ids: set[str]) -> MarkerResult:
    """인용 마커를 검증한다.

    반환 본문은 유효하지 않은 마커(와 그 앞 공백)만 제거하고 나머지는
    바이트 단위로 보존한다 — "p < .05" 같은 논문 통계 표기를 건드리지 않는다.
    """
    dropped: list[str] = []
    used: list[str] = []

    def _check(m: re.Match) -> str:
        marker_id = m.group(1)
        if marker_id in valid_ids:
            if marker_id not in used:
                used.append(marker_id)
            return m.group(0)
        dropped.append(marker_id)
        return ""

    cleaned = _MARKER.sub(_check, text).strip()

    count_text = _TRAILING_MARKER.sub(r"\3\1\2", cleaned)
    sentences = [s for s in _SENT_SPLIT.split(count_text) if s.strip()]
    unmarked = sum(1 for s in sentences if not _MARKER.search(s))

    return MarkerResult(cleaned, dropped, used, unmarked)


def strip_markers(text: str) -> str:
    """구조적 인용 자리(대표 논문 요약)에서 마커를 전부 걷어낸다.

    그 자리의 인용은 불릿의 논문으로 이미 정해져 있어 마커가 필요 없다. 그런데
    모델은 시키지 않아도 요약 끝에 [E7] 을 단다(2026-09-23 실측). 요약은
    bind_markers 를 거치지 않으므로 남겨두면 지어낸 번호가 검증 없이 화면에
    나간다 — 유효한 번호도 칩과 중복이라 함께 지운다.
    """
    return _MARKER.sub("", text).strip()
