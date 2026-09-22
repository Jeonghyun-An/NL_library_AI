"""runner.py — 단계 오케스트레이션

각 단계는 ResearchState 를 받아 갱신한다. explore_fn·critique_fn 을 인자로
받는 이유는 Milvus·LLM 없이 루프 자체를 테스트하기 위해서다.

진행 중계도 같은 이유로 emit 인자로 주입받는다. `services.research.relay` 를
여기서 import 하면 relay 가 물고 있는 `redis` 가 이 모듈을 여는 모든 곳에
필요해지고, 미설치 환경에서는 테스트 수집 단계가 통째로 죽는다
(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).
"""
import logging

from services.research.citations import build_evidence, evidence_id
from services.research.critic import critique as _critique
from services.research.critic import should_recheck
from services.research.explorer import explore as _explore
from services.research.state import ResearchState, SubQuestion

log = logging.getLogger(__name__)


async def _noop_emit(kind: str, payload: dict) -> None:
    return None


async def explore_subquestion(
    state: ResearchState,
    subq: SubQuestion,
    *,
    db,
    explore_fn=_explore,
    critique_fn=_critique,
    emit=None,
) -> SubQuestion:
    """한 하위질문을 탐색하고, 부족하면 쿼리를 바꿔 상한까지 재탐색한다."""
    emit = emit or _noop_emit
    params = state.params
    query = subq.text
    recheck = 0

    while True:
        subq.queries.append(query)
        hits, meta = await explore_fn(query, params=params, db=db)
        await emit("search", {
            "subq_idx": subq.idx, "query": query, "found": len(hits),
        })

        # 같은 논문이 여러 하위질문에서 나오면 근거를 새로 만들지 않고 재사용한다.
        # 안 그러면 한 논문이 E3 와 E17 로 갈라져 인용칩이 같은 출처를 다른
        # 번호로 가리킨다. 번호는 state.evidence 를 소유한 이쪽이 붙인다 —
        # build_evidence 는 묶기만 하고 id 를 비워 돌려준다.
        known_by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
        for cand in build_evidence(
            hits, meta, chunks_per_evidence=params["chunks_per_evidence"],
        ):
            existing = known_by_cnts.get(cand.cnts_id)
            if existing is not None:
                if existing not in subq.evidence_ids:
                    subq.evidence_ids.append(existing)
                continue
            # break 가 아니라 continue 다. 상한에 닿은 뒤에 나오는 후보 중에도
            # "이미 있는 근거의 재사용"이 섞여 있는데, 그건 총량을 늘리지 않는다.
            # break 로 끊으면 그 하위질문이 정당한 근거 링크를 잃는다.
            if len(state.evidence) >= params["max_evidence"]:
                continue
            eid = evidence_id(len(state.evidence))
            cand.id = eid
            state.evidence[eid] = cand
            known_by_cnts[cand.cnts_id] = eid
            subq.evidence_ids.append(eid)

        verdict = await critique_fn(
            subq, [state.evidence[e] for e in subq.evidence_ids], params=params,
        )
        subq.verdict = verdict.verdict
        subq.note = verdict.note
        # 판정을 못 읽었다는 표시를 여기서 옮기지 않으면 보고서까지 닿지 않는다 —
        # synthesizer.build_limitations 는 subq.parse_failed 만 보고 "자동 점검을
        # 완료하지 못한 하위질문"을 센다. 자기점검이 전부 실패해도 보고서가
        # "한계 없음"으로 보이는 게 정확히 critic 의 parse_failed 가 막으려던 실패다.
        #
        # 마지막 라운드 값으로 덮어써도 된다(OR 누적이 필요 없다): 파싱 실패는
        # verdict="sufficient" 로 떨어지고 should_recheck 는 "insufficient" 일 때만
        # True 이므로, 파싱 실패가 난 라운드가 항상 마지막 라운드다.
        subq.parse_failed = verdict.parse_failed
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
        })

        if not should_recheck(subq, recheck_count=recheck, max_recheck=params["max_recheck"]):
            break
        if not verdict.new_queries:
            break
        query = verdict.new_queries[0]
        recheck += 1
        state.recheck_count += 1

    return subq
