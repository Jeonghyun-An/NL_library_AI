"""citations.py — 근거 조립과 인용 마커 검증 (순수 함수)

인용은 두 종류다.

구조적 인용 — `대표 논문 요약`은 불릿 하나가 논문 하나라, 그 논문의 근거만
넣고 생성하면 인용이 추론이 아니라 구조로 정해진다. 모델이 고를 일이 없다.

마커 인용 — `도입 문단`·`향후 과제`는 여러 논문을 가로지르므로 구조로 못
정한다. 모델이 [E3] 로 달게 하고 여기서 전수 검증한다. 해석 안 되는 마커는
조용히 통과시키지 않고 제거한 뒤 개수를 보고한다.
"""
import re

from services.research.state import Chunk, Evidence

_MARKER = re.compile(r"\[(E\d+)\]")
_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+")


def evidence_id(index: int) -> str:
    return f"E{index + 1}"


def build_evidence(
    hits: list[dict],
    meta_by_id: dict[str, dict],
    *,
    start_index: int,
    chunks_per_evidence: int,
) -> dict[str, Evidence]:
    """검색 결과를 논문 단위 근거로 묶는다.

    같은 논문의 청크 여러 개는 근거 하나가 되고, 점수 높은 순으로
    chunks_per_evidence 개만 남긴다(호버 팝업의 1/2 페이지네이션).
    카탈로그에 메타가 없는 청크는 버린다 — 서지를 못 보여주면 근거가 아니다.
    """
    grouped: dict[str, list[dict]] = {}
    for hit in hits:
        cnts_id = hit["book_id"]
        if cnts_id not in meta_by_id:
            continue
        grouped.setdefault(cnts_id, []).append(hit)

    result: dict[str, Evidence] = {}
    for offset, (cnts_id, rows) in enumerate(grouped.items()):
        rows.sort(key=lambda r: r["score"], reverse=True)
        eid = evidence_id(start_index + offset)
        result[eid] = Evidence(
            id=eid,
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
        )
    return result


def bind_markers(text: str, valid_ids: set[str]) -> tuple[str, list[str], int]:
    """인용 마커를 검증한다.

    returns (정리된 본문, 제거된 마커 목록, 마커 없는 문장 수)
    """
    dropped: list[str] = []

    def _check(m: re.Match) -> str:
        if m.group(1) in valid_ids:
            return m.group(0)
        dropped.append(m.group(1))
        return ""

    cleaned = _MARKER.sub(_check, text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,!?])", r"\1", cleaned).strip()

    sentences = [s for s in _SENT_SPLIT.split(cleaned) if s.strip()]
    unmarked = sum(1 for s in sentences if not _MARKER.search(s))
    return cleaned, dropped, unmarked
