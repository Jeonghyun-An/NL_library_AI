"""citations.py — 근거 조립과 인용 마커 검증 (순수 함수)

인용은 두 종류다.

구조적 인용 — `대표 논문 요약`은 불릿 하나가 논문 하나라, 어느 논문이 실리고
칩이 어디를 가리키는지는 코드가 정한다. 다만 절의 논문 여러 편을 한 호출에 넣고
번호별로 요약을 받으므로, 요약 문장이 그 논문의 내용인지는 모델의 번호 배정에
달려 있다 — 인용은 구조지만 요약의 배정은 추론이다(spec §4-1 구현 시 변경).

마커 인용 — `도입 문단`·`향후 과제`는 여러 논문을 가로지르므로 구조로 못
정한다. 모델이 [E3] 로 달게 하고 여기서 전수 검증한다. 해석 안 되는 마커는
조용히 통과시키지 않고 제거한 뒤 개수를 보고한다.

근거 ID(E1·E2·...) 는 runner 가 state.evidence 에 넣는 시점에 붙인다 —
evidence 네임스페이스를 소유한 쪽이 번호도 소유해야 한다. build_evidence
는 순서만 보장하고(hits 등장 순서) 번호는 매기지 않는다.
"""
import re
from dataclasses import replace
from typing import NamedTuple

from services.research.state import Chunk, Evidence, HitRow, SubQuestion

# 반환 텍스트의 표준형. bind_markers 는 인식한 표기를 전부 이 모양으로 다시 쓴다 —
# 프론트와 계수 로직은 이 한 가지 문법만 알면 된다.
_MARKER = re.compile(r"[ \t]*\[(E\d+)\]")
# 모델은 지시("[E3] 형태만")를 어기고 묶음·범위·전각·소문자·0패딩을 낸다.
# 괄호 하나를 통째로 잡아 안을 해석한다 — 단일형만 보면 "[E2, E99]" 속 없는 번호가
# 검증도 제거도 안 된 채 본문에 실린다.
_BRACKET = re.compile(r"([ \t]*)[\[［【]([^\[\]［］【】\n]*)[\]］】]")
# 인용으로 보는 괄호: 영문자에 붙지 않은 E 뒤에 숫자. "[ICE 2019]"·"[표 1]" 은 제외.
# 숫자·소수점 뒤의 e 는 지수 표기다("[1.2e3, 4.5e3]"·"[n=2E5]") — 인용으로 보면
# 괄호째 지워 수치가 사라진다.
_CITATION_LIKE = re.compile(r"(?<![A-Za-z0-9.])[Ee]\s*\d")
_ID = r"[Ee]\s*(\d+)"
_RANGE_SEP = r"\s*[-~–—～]\s*"
_ITEM = re.compile(rf"{_ID}(?:{_RANGE_SEP}[Ee]?\s*(\d+))?")
_LIST_SEP = re.compile(r"\s*[,，;；]\s*")
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


def chunks_for(ev: Evidence, sq: SubQuestion) -> list[Chunk]:
    """그 하위질문 검색에서 매칭된 청크(점수순). 점수는 그 하위질문의 검색어로 받은 값이다.

    사본을 돌려준다 — Evidence.chunks 의 점수는 매칭한 하위질문 중 최고값이라 그대로
    넘기면 다른 하위질문의 점수가 발췌·호버에 나간다. 점수 기록이 없는 옛 스냅샷은
    Chunk.score 를, 매핑이 없는 옛 스냅샷은 청크 전부를 준다.
    """
    ids = sq.evidence_chunks.get(ev.id)
    if not ids:
        return list(ev.chunks)
    by_id = {c.chunk_id: c for c in ev.chunks}
    return [replace(by_id[i], score=sq.chunk_scores.get(i, by_id[i].score))
            for i in ids if i in by_id]


def link_chunks(ev: Evidence, sq: SubQuestion, found: list[Chunk], *, limit: int) -> None:
    """이번 검색에서 매칭된 청크를 그 하위질문의 몫으로 기록한다.

    같은 하위질문의 재검색이 더 잘 맞는 대목을 찾으면 점수순으로 갈아끼운다. 이미 매핑한
    청크는 이 하위질문이 받은 점수(sq.chunk_scores)로 비교한다 — Chunk.score 는 다른
    하위질문의 검색어로 받은 값일 수 있다.

    Evidence.chunks 는 매칭된 적 있는 청크의 저장소다. 새 청크는 이 하위질문이 가리킬 때만
    더하고, 점수는 매칭한 하위질문 중 최고값으로 둔다. 갈아끼워진 청크는 다른 하위질문이
    가리킬 수 있어 여기서 지우지 않는다 — 보고서에는 지금 가리키는 것만 싣는다
    (synthesizer._serialize_evidence).
    """
    by_id = {c.chunk_id: c for c in ev.chunks}
    scores = {i: sq.chunk_scores.get(i, by_id[i].score)
              for i in sq.evidence_chunks.get(ev.id, []) if i in by_id}
    found_by_id: dict[str, Chunk] = {}
    for c in found:
        if c.score > scores.get(c.chunk_id, float("-inf")):
            scores[c.chunk_id] = c.score
            found_by_id[c.chunk_id] = c
    ranked = sorted(scores, key=scores.__getitem__, reverse=True)[:limit]

    for i in ranked:
        chunk = by_id.get(i)
        if chunk is None:
            chunk = found_by_id[i]
            ev.chunks.append(chunk)
            by_id[i] = chunk
        chunk.score = max(chunk.score, scores[i])
    for i in sq.evidence_chunks.get(ev.id, []):
        if i not in ranked:
            sq.chunk_scores.pop(i, None)
    sq.evidence_chunks[ev.id] = ranked
    sq.chunk_scores.update({i: scores[i] for i in ranked})


class MarkerResult(NamedTuple):
    text: str
    dropped: list[str]
    used: list[str]      # 등장 순서, 중복 제거 — 유효한 마커를 다시 정규식으로 훑지 않고 여기서 재사용한다
    unmarked: int
    # 인용처럼 생겼지만 번호를 읽을 수 없는 괄호("[E1 참조]"). 없는 번호(dropped)와
    # 원인이 달라 따로 센다 — 이쪽은 프롬프트 형식 문제다.
    unparsed: list[str] = []


def _parse_ids(inner: str) -> list[tuple[int, int | None]] | None:
    """괄호 안을 (번호, 범위 끝) 목록으로 읽는다. 문법을 벗어나면 None."""
    items = []
    for part in _LIST_SEP.split(inner.strip()):
        m = _ITEM.fullmatch(part)
        if m is None:
            return None
        items.append((int(m.group(1)), int(m.group(2)) if m.group(2) else None))
    return items


def _resolve(items: list[tuple[int, int | None]], valid_ids: set[str]) -> tuple[list[str], list[str]]:
    """(유효 번호, 없는 번호). 0패딩은 정수로 읽어 E01 → E1 로 맞춘다.

    범위는 끝점만 모델이 쓴 번호다. 사이 번호는 주어진 것만 싣고 없는 것은
    세지 않는다 — "[E3-E7]" 을 E4·E5·E6 까지 지어낸 것으로 보고하면 과장이다.
    """
    valid_nums = sorted(int(v[1:]) for v in valid_ids if v[1:].isdigit())
    ok: list[str] = []
    bad: list[str] = []
    for start, end in items:
        if end is None or end == start:
            nums, ends = [start], {start}
        else:
            nums = [start, *(n for n in valid_nums if start < n < end), end]
            ends = {start, end}
        for n in nums:
            eid = f"E{n}"
            if eid in valid_ids:
                if eid not in ok:
                    ok.append(eid)
            elif n in ends:
                bad.append(eid)
    return ok, bad


def bind_markers(text: str, valid_ids: set[str]) -> MarkerResult:
    """인용 마커를 검증한다.

    인식한 표기는 유효한 번호만 표준형 `[E#]` 으로 다시 쓰고, 없는 번호와
    해석 못 한 표기는 (그 앞 공백과 함께) 지운다. 나머지는 바이트 단위로
    보존한다 — "p < .05" 같은 논문 통계 표기를 건드리지 않는다.
    """
    dropped: list[str] = []
    unparsed: list[str] = []
    used: list[str] = []

    def _check(m: re.Match) -> str:
        inner = m.group(2)
        if not _CITATION_LIKE.search(inner):
            return m.group(0)
        items = _parse_ids(inner)
        if items is None:
            unparsed.append(m.group(0).strip())
            return ""
        ok, bad = _resolve(items, valid_ids)
        dropped.extend(bad)
        for eid in ok:
            if eid not in used:
                used.append(eid)
        if not ok:
            return ""
        return m.group(1) + " ".join(f"[{eid}]" for eid in ok)

    cleaned = _BRACKET.sub(_check, text).strip()

    count_text = _TRAILING_MARKER.sub(r"\3\1\2", cleaned)
    sentences = [s for s in _SENT_SPLIT.split(count_text) if s.strip()]
    unmarked = sum(1 for s in sentences if not _MARKER.search(s))

    return MarkerResult(cleaned, dropped, used, unmarked, unparsed)


def strip_markers(text: str) -> str:
    """구조적 인용 자리(대표 논문 요약)에서 마커를 전부 걷어낸다.

    그 자리의 인용은 불릿의 논문으로 이미 정해져 있어 마커가 필요 없다. 그런데
    모델은 시키지 않아도 요약 끝에 [E7] 을 단다(2026-09-23 실측). 요약은
    bind_markers 를 거치지 않으므로 남겨두면 지어낸 번호가 검증 없이 화면에
    나간다 — 유효한 번호도 칩과 중복이라 함께 지운다. 묶음·전각 표기도
    bind_markers 와 같은 기준으로 인용으로 본다.
    """
    def _drop(m: re.Match) -> str:
        return "" if _CITATION_LIKE.search(m.group(2)) else m.group(0)

    return _BRACKET.sub(_drop, text).strip()
