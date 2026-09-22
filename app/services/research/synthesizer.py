"""synthesizer.py — 보고서 조립

인용을 두 갈래로 다룬다.
- 대표 논문 요약: 불릿 = 논문이므로 인용이 구조로 정해진다. 모델이 고르지 않는다.
- 도입·향후 과제: 모델이 [E3] 마커를 달고 여기서 전수 검증한다.

제목·저자·연도는 모델 출력에서 가져오지 않는다. evidence 의 meta 를 쓴다 —
라벨을 모델이 쓰게 두면 언젠가 없는 논문을 만들어낸다.
"""
import logging

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.citations import bind_markers
from services.research.llm_json import extract_json
from services.research.state import ResearchState

log = logging.getLogger(__name__)

UNMARKED_THRESHOLD = 3


def build_limitations(
    state: ResearchState, *, unmarked_total: int, dropped_total: int,
) -> list[str]:
    """자기점검 결과를 사용자에게 보이는 문장으로 바꾼다.

    판정 파싱이 실패한 하위질문(parse_failed)을 반드시 별도로 센다. 실패는
    verdict="sufficient" 로 떨어지므로 아래 insufficient 분기에 걸리지 않고,
    그대로 두면 자기점검이 전부 꺼져도 보고서가 "한계 없음"으로 보인다.

    없는 근거 번호(dropped)와 무근거 서술(unmarked)도 한 문장으로 합치지
    않는다. 종류가 다른 사건이다 — 마커 없는 문장은 "이 절에서는 …을 다룬다"
    같은 연결 문장일 때가 많아 몇 건은 넘긴다. 반면 없는 번호를 가리킨 표기는
    모델이 근거를 지어낸 것이니 1건부터 보고한다. 합치면 흔한 쪽을 과하게
    알리면서 정작 심각한 쪽을 임계값에 묻는다.
    """
    out: list[str] = []
    for sq in state.subquestions:
        # note 를 두 분기 모두에 붙인다. 근거가 0편인 하위질문은 아래
        # insufficient 분기에 닿지 못하는데, 정작 "왜 못 찾았는지"가 가장
        # 필요한 경우다 — 여기서 흘리면 critic 의 note 가 어디에도 안 실린다.
        note = f" — {sq.note}" if sq.note else ""
        if not sq.evidence_ids:
            out.append(f"'{sq.text}' 에 대해서는 근거를 찾지 못했다{note}")
        elif sq.verdict == "insufficient":
            out.append(
                f"'{sq.text}' 는 근거 {len(sq.evidence_ids)}편으로 결론이 약하다{note}"
            )

    unchecked = sum(1 for sq in state.subquestions if sq.parse_failed)
    if unchecked:
        out.append(
            f"자동 점검을 완료하지 못한 하위질문이 {unchecked}건 있다 — "
            f"그 부분의 근거 충분성은 확인되지 않았다."
        )

    if dropped_total:
        out.append(
            f"존재하지 않는 근거 번호를 가리킨 인용 표기 "
            f"{dropped_total}건을 본문에서 제거했다."
        )

    if unmarked_total >= UNMARKED_THRESHOLD:
        out.append(f"근거 표기가 없는 서술 {unmarked_total}건이 있다.")
    return out


def _serialize_evidence(state: ResearchState) -> dict:
    return {
        eid: {
            "cnts_id": ev.cnts_id,
            "meta": ev.meta,
            "chunks": [
                {"chunk_id": c.chunk_id, "text": c.text,
                 "page_start": c.page_start, "page_end": c.page_end}
                for c in ev.chunks
            ],
        }
        for eid, ev in state.evidence.items()
    }


def assemble_report(
    state: ResearchState, sections: list[dict], *, unmarked_total: int,
) -> dict:
    valid = set(state.evidence.keys())
    by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
    unmarked = unmarked_total
    # 마커 검증 결과는 bind_markers 호출마다 누적한다. 섹션마다 도입·향후
    # 과제로 여러 번 부르므로 한 번의 반환값만 읽으면 나머지 호출에서 지운
    # 표기가 조용히 사라진다. dropped 는 번호 종류가 아니라 본문에 박힌
    # 표기 수로 센다 — 사용자가 보는 단위가 그것이다.
    dropped = 0
    out_sections = []

    for sec in sections:
        intro = bind_markers(sec.get("intro", ""), valid)
        unmarked += intro.unmarked
        dropped += len(intro.dropped)

        papers = []
        for p in sec.get("papers", []):
            eid = by_cnts.get(p["cnts_id"])
            if eid is None:
                continue                      # 근거에 없는 논문은 싣지 않는다
            papers.append({
                "cnts_id": p["cnts_id"],
                "summary": p.get("summary", ""),
                "evidence": [eid],            # 구조적 인용 — 모델이 고르지 않는다
            })

        future = []
        for f in sec.get("future", []):
            res = bind_markers(f.get("text", ""), valid)
            unmarked += res.unmarked
            dropped += len(res.dropped)
            # used 를 bind_markers 가 돌려준다 — 여기서 정규식을 다시 쓰면
            # 마커 문법이 두 곳으로 갈라진다.
            future.append({"text": res.text, "evidence": res.used})

        out_sections.append({
            "heading": sec.get("heading", ""),
            "intro": intro.text, "papers": papers, "future": future,
        })

    return {
        "question": state.question,
        "range": state.corpus_range,
        "sections": out_sections,
        "evidence": _serialize_evidence(state),
        "trail": [
            {"subquestion": sq.text, "queries": sq.queries,
             "evidence_count": len(sq.evidence_ids),
             "verdict": sq.verdict, "note": sq.note}
            for sq in state.subquestions
        ],
        "limitations": build_limitations(
            state, unmarked_total=unmarked, dropped_total=dropped,
        ),
    }


async def synthesize(state: ResearchState) -> dict:
    blocks = []
    for sq in state.subquestions:
        lines = []
        for eid in sq.evidence_ids:
            ev = state.evidence[eid]
            excerpt = ev.chunks[0].text[:400] if ev.chunks else ""
            lines.append(
                f"[{eid}] {ev.meta.get('title')} "
                f"({ev.meta.get('pub_date')}, {ev.meta.get('series_title')}) "
                f"cnts_id={ev.cnts_id}\n{excerpt}"
            )
        blocks.append(f"## {sq.text}\n" + "\n\n".join(lines))

    system, user, llm_params = get_prompt("research_synthesize").render(
        question=state.question, evidence_blocks="\n\n".join(blocks),
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params, timeout=300.0,
    )
    # Task 6 에서 뺀 공용 추출기를 쓴다. 여기서 다시 구현하지 마라 —
    # body[index("{"):rindex("}")+1] 은 JSON 뒤에 } 를 포함한 산문이 붙으면
    # 그 끝까지 먹어 파싱이 깨진다.
    data = extract_json(raw)
    if data is None:
        log.error("[research] 종합 JSON 파싱 실패: %s", (raw or "")[:300])
        raise ValueError("보고서 종합 출력을 해석하지 못했다")
    sections = data.get("sections") or []

    return assemble_report(state, sections, unmarked_total=0)
