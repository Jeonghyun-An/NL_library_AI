"""runner.py — 단계 오케스트레이션

각 단계는 ResearchState 를 받아 갱신한다. explore_fn·critique_fn 을 인자로
받는 이유는 Milvus·LLM 없이 루프 자체를 테스트하기 위해서다.

진행 중계도 같은 이유로 emit 인자로 주입받는다. `services.research.relay` 를
여기서 import 하면 relay 가 물고 있는 `redis` 가 이 모듈을 여는 모든 곳에
필요해지고, 미설치 환경에서는 테스트 수집 단계가 통째로 죽는다
(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).
"""
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from services.research.citations import build_evidence, chunks_for, evidence_id, link_chunks
from services.research.critic import Verdict
from services.research.critic import critique as _critique
from services.research.critic import should_recheck
from services.research.explorer import explore as _explore
from services.research.planner import query_key
from services.research.state import Evidence, HitRow, ResearchState, SubQuestion

log = logging.getLogger(__name__)

ExploreFn = Callable[..., Awaitable[tuple[list[HitRow], dict[str, dict]]]]
CritiqueFn = Callable[..., Awaitable[Verdict]]
EmitFn = Callable[[str, dict], Awaitable[None]]


async def _noop_emit(kind: str, payload: dict) -> None:
    return None


def _best_rank(hits: list[HitRow]) -> dict[str, float]:
    best: dict[str, float] = {}
    for h in hits:
        score = h.get("rank_score", h["score"])
        if score > best.get(h["book_id"], float("-inf")):
            best[h["book_id"]] = score
    return best


def _rank_order(ids: list[str], relevance: dict[str, float], leaders: list[str]) -> list[str]:
    """하위질문 안의 순위. 검색 라운드마다 새로 보탠 근거 중 1위는 앞자리를 보장하고,
    나머지는 rank_score 순이다.

    점수만으로 정렬하지 않는 이유: 라운드마다 검색어가 달라 점수를 그대로 비교할
    수 없고, 자기점검이 "시기 편중" 같은 이유로 부족하다고 해서 찾은 보완 근거는
    첫 검색의 상위 논문보다 점수가 낮기 쉽다. 그러면 절(앞 5편)에 끝내 실리지
    못해 재검색의 성과가 보고서 본문에서 사라진다.
    """
    seats = [e for e in leaders if e in ids]
    rest = sorted((e for e in ids if e not in seats),
                  key=lambda e: relevance.get(e, float("-inf")), reverse=True)
    return seats + rest


def _next_query(suggestions: list[str], tried: list[str]) -> str | None:
    """이미 시도한 검색어는 건너뛴다 — 같은 검색은 같은 결과를 내 라운드만 태운다."""
    seen = {query_key(q) for q in tried}
    for q in suggestions:
        if query_key(q) not in seen:
            return q
    return None


def _as_seen_by(ev: Evidence, subq: SubQuestion) -> Evidence:
    return Evidence(id=ev.id, cnts_id=ev.cnts_id, meta=ev.meta, chunks=chunks_for(ev, subq))


async def explore_subquestion(
    state: ResearchState,
    subq: SubQuestion,
    *,
    db: AsyncSession | None,
    explore_fn: ExploreFn = _explore,
    critique_fn: CritiqueFn = _critique,
    emit: EmitFn | None = None,
) -> SubQuestion:
    """한 하위질문을 탐색하고, 부족하면 쿼리를 바꿔 상한까지 재탐색한다."""
    emit = emit or _noop_emit
    params = state.params
    query = subq.text
    recheck = 0
    relevance: dict[str, float] = {}
    leaders: list[str] = []
    capped: set[str] = set()

    while True:
        subq.queries.append(query)
        hits, meta = await explore_fn(query, params=params, db=db)
        # 읽기 트랜잭션을 여기서 끝낸다. 이어지는 critic 은 LLM 을 수십 초 기다리는데,
        # 그동안 세션이 library_catalog 공유 잠금을 쥐고 있으면 FastAPI 기동 시
        # lifespan 의 ALTER TABLE library_catalog 가 막히고 그 뒤 모든 조회가 줄 선다.
        if db is not None:
            await db.commit()
        await emit("search", {
            "subq_idx": subq.idx, "query": query, "found": len(hits),
        })

        # 같은 논문이 여러 하위질문에서 나오면 근거를 새로 만들지 않고 재사용한다.
        # 안 그러면 한 논문이 E3 와 E17 로 갈라져 인용칩이 같은 출처를 다른
        # 번호로 가리킨다. 번호는 state.evidence 를 소유한 이쪽이 붙인다 —
        # build_evidence 는 묶기만 하고 id 를 비워 돌려준다.
        known_by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
        best = _best_rank(hits)
        before = set(subq.evidence_ids)
        linked: list[str] = []
        for cand in build_evidence(
            hits, meta, chunks_per_evidence=params["chunks_per_evidence"],
        ):
            eid = known_by_cnts.get(cand.cnts_id)
            if eid is None:
                # break 가 아니라 continue 다. 상한에 닿은 뒤에 나오는 후보 중에도
                # "이미 있는 근거의 재사용"이 섞여 있는데, 그건 총량을 늘리지 않는다.
                # break 로 끊으면 그 하위질문이 정당한 근거 링크를 잃는다.
                if len(state.evidence) >= params["max_evidence"]:
                    capped.add(cand.cnts_id)
                    continue
                eid = evidence_id(len(state.evidence))
                state.evidence[eid] = Evidence(id=eid, cnts_id=cand.cnts_id, meta=cand.meta)
                known_by_cnts[cand.cnts_id] = eid
            # 재사용이어도 이번 검색에서 매칭된 대목은 버리지 않는다 — 그 하위질문의
            # critic 발췌·절 요약·호버는 이 대목을 써야 한다.
            link_chunks(state.evidence[eid], subq, cand.chunks,
                        limit=params["chunks_per_evidence"])
            relevance[eid] = max(relevance.get(eid, float("-inf")), best[cand.cnts_id])
            if eid not in linked:
                linked.append(eid)

        fresh = [e for e in linked if e not in before]
        if fresh:
            leaders.append(fresh[0])
        subq.evidence_ids = _rank_order(subq.evidence_ids + fresh, relevance, leaders)
        subq.capped = len(capped)

        verdict = await critique_fn(
            subq, [_as_seen_by(state.evidence[e], subq) for e in subq.evidence_ids],
            params=params,
        )
        subq.verdict = verdict.verdict
        subq.note = verdict.note
        # 판정을 못 받았다는 표시를 여기서 옮기지 않으면 보고서까지 닿지 않는다 —
        # synthesizer.build_limitations 는 subq.parse_failed 만 보고 "자동 점검을
        # 완료하지 못한 하위질문"을 센다. 자기점검이 전부 실패해도 보고서가
        # "한계 없음"으로 보이는 게 정확히 critic 의 parse_failed 가 막으려던 실패다.
        #
        # 마지막 라운드 값으로 덮어써도 된다(OR 누적이 필요 없다): 판정 불가는
        # verdict="sufficient" 로 떨어지고 should_recheck 는 "insufficient" 일 때만
        # True 이므로, 판정 불가가 난 라운드가 항상 마지막 라운드다.
        subq.parse_failed = verdict.parse_failed
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
        })

        if not should_recheck(subq, recheck_count=recheck, max_recheck=params["max_recheck"]):
            break
        # 상한에 닿으면 새 근거가 생길 수 없다 — 재검색은 검색·LLM 호출만 태운다.
        if len(state.evidence) >= params["max_evidence"]:
            break
        next_query = _next_query(verdict.new_queries, subq.queries)
        if next_query is None:
            break
        query = next_query
        recheck += 1

    return subq
