"""membership.py — 개념 소속과 선행연구 묶음 배정 (spec §5-5 목차 만들기, 06b 정함 7)

- 개념 친밀도(concept_affinity): 담은 논문마다 각 핵심 개념과의 코사인 — BGE-M3 개념 임베딩 ↔ Milvus 메타청크
  (`chunk_idx == -1`, `book_id == cnts_id`) 의 `embedding`. FastAPI 에서만 부른다(임베딩 모델은 lifespan 에만
  있다 — 함정 17). 정해진 논문 집합의 유사도라 ANN 검색(nprobe 개 클러스터만 본다)이 아니라 col.query 로 벡터를
  꺼내 직접 잰다. 무거운 모듈(FlagEmbedding·pymilvus)은 함수 안에서 import 한다 — 이 파일의 순수 함수 테스트가
  torch 없이 돌아야 한다(함정 13). 실패는 실제로 나는 타입만 잡고 None 을 돌려준다(함정 19 — except Exception 금지).
- 하위질문 친밀도(subq_affinity): 개념이 비었거나 계산이 실패하면 쓴다 — 들어온 경로의 하위질문 안 순위로 1/(1+rank).
- 묶음 수(group_count)와 배정(assign_groups)은 서버 코드가 정한다(LLM 은 이름만 붙인다): 각 논문의 1순위 키로
  수를 세어 많은 순(같으면 논문 순서에서 먼저 나온 키) k 개를 묶음으로 삼고, 그 밖의 논문은 고른 키 가운데
  친밀도가 가장 높은 묶음으로, 친밀도가 없는 논문은 첫 묶음으로 보낸다 — 임계값 보정 전에도 결정적이고 모든
  논문이 꼭 한 묶음에 든다.
- 임계 MEMBER_THRESHOLD(제안값)는 배정에 쓰지 않는다. 임계 이상만 모은 {개념: [cnts_id]} 를
  research_works.concept_members 에 저장하는 데만 쓴다(06c 격자가 보정한다).
"""
import logging
import math
from collections import Counter

from services.research_work.shapes import MAX_GROUPS, PAPERS_PER_GROUP, PRIOR_KEYS

log = logging.getLogger(__name__)

MEMBER_THRESHOLD = 0.45
# 임베딩·Milvus 가 실제로 내는 실패(리랭커의 pipeline._RERANK_FAILURES 와 같은 묶음) — Milvus 는 함수 안에서
# import 한 MilvusException 을 더한다
_FAILURES = (RuntimeError, OSError, ValueError, ImportError)


def cosine(a, b) -> float:
    """코사인 유사도. 영벡터가 끼면 0.0. 원소는 float() 로 읽는다(Milvus 는 numpy.float32 를 준다)."""
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        x, y = float(x), float(y)
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def group_count(n: int) -> int:
    """선행연구 묶음 수 — 담은 논문 PAPERS_PER_GROUP 편당 1개, 최소 1·최대 MAX_GROUPS(spec §5-5)."""
    return min(MAX_GROUPS, max(1, n // PAPERS_PER_GROUP))


def _ranks(origin_ref) -> dict[str, int]:
    """들어온 경로의 하위질문 안 순위 {"0": 1, …} — evidence 행에만 있다(되살림·담기 행은 빈 dict)."""
    ranks = origin_ref.get("rank") if isinstance(origin_ref, dict) else None
    if not isinstance(ranks, dict):
        return {}
    return {str(k): v for k, v in ranks.items() if isinstance(v, int) and not isinstance(v, bool)}


def ordered_papers(rows) -> list[str]:
    """담은(in) 논문 — 하위질문 안 가장 앞선 순위(없으면 뒤) → 사용자가 정한 순서(position, 없으면 뒤) → cnts_id."""
    def key(row):
        ranks = _ranks(row.origin_ref).values()
        best = min(ranks) if ranks else None
        return (best is None, best or 0, row.position is None, row.position or 0, row.cnts_id)
    return [r.cnts_id for r in sorted((r for r in rows if r.state == "in"), key=key)]


def subq_affinity(rows, subquestions: list[str]) -> dict[str, dict[str, float]]:
    """{cnts_id: {하위질문 글: 1/(1+순위)}}. 순위가 없는 논문(되살림·담기)은 싣지 않는다 — 첫 묶음으로 간다."""
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        scores: dict[str, float] = {}
        for idx, rank in _ranks(row.origin_ref).items():
            i = int(idx) if idx.isdigit() else -1
            if 0 <= i < len(subquestions):
                scores[subquestions[i]] = 1.0 / (1.0 + rank)
        if scores:
            out[row.cnts_id] = scores
    return out


def members_from_affinity(affinity: dict[str, dict[str, float]], concepts: list[str],
                          threshold: float) -> dict[str, list[str]]:
    """concept_members — 개념마다 친밀도가 임계 이상인 논문(높은 순, 같으면 cnts_id 순). 개념은 모두 키로 둔다
    (빈 목록 = 계산했지만 소속 논문이 없다. 06a 규칙의 {} 는 '개념이 바뀌어 비웠다')."""
    out: dict[str, list[str]] = {}
    for concept in concepts:
        hits = [(scores[concept], cnts_id) for cnts_id, scores in affinity.items()
                if concept in scores and scores[concept] >= threshold]
        out[concept] = [cnts_id for _, cnts_id in sorted(hits, key=lambda h: (-h[0], h[1]))]
    return out


def assign_groups(papers: list[str], affinity: dict[str, dict[str, float]], k: int, *,
                  keys: list[str]) -> list[dict]:
    """묶음 배정(정함 7). keys 는 친밀도 키(개념 또는 하위질문 글)의 정해진 순서 — 한 논문의 1순위가 비기면
    keys 에서 앞선 키를 고르고, keys 밖의 키는 보지 않는다. 묶음 키는 PRIOR_KEYS 를 차례로, hint 는 고른 키.
    결과 [{"key": "prior.g1", "hint": str, "papers": [cnts_id]}] — 묶음 안 논문은 papers 순서 그대로."""
    order = {key: i for i, key in enumerate(keys)}

    def scores_of(cnts_id: str) -> dict[str, float]:
        return {key: v for key, v in (affinity.get(cnts_id) or {}).items() if key in order}

    def best(scores: dict[str, float], among) -> str | None:
        candidates = [key for key in among if key in scores]
        if not candidates:
            return None
        return max(candidates, key=lambda key: (scores[key], -order[key]))

    tops = {p: best(scores_of(p), order) for p in papers}
    counts = Counter(t for t in tops.values() if t is not None)
    first_seen: dict[str, int] = {}
    for p in papers:
        if tops[p] is not None:
            first_seen.setdefault(tops[p], len(first_seen))
    ranked = sorted(counts, key=lambda key: (-counts[key], first_seen[key]))
    chosen = ranked[:max(1, min(k, MAX_GROUPS))]
    if not chosen:
        return [{"key": PRIOR_KEYS[0], "hint": "", "papers": list(papers)}]
    groups = [{"key": PRIOR_KEYS[i], "hint": key, "papers": []} for i, key in enumerate(chosen)]
    slot = {key: g for key, g in zip(chosen, groups)}
    for p in papers:
        target = tops[p] if tops[p] in slot else best(scores_of(p), chosen)
        (slot[target] if target is not None else groups[0])["papers"].append(p)
    return groups


def _ids_expr(cnts_ids: list[str]) -> str:
    return ", ".join(f'"{c}"' for c in cnts_ids)


def concept_affinity(concepts: list[str], cnts_ids: list[str]) -> dict[str, dict[str, float]] | None:
    """{cnts_id: {개념: 코사인}} — FastAPI 전용·동기(엔드포인트는 run_in_threadpool 로 부른다). Milvus 에
    메타청크가 없는 논문은 싣지 않는다. 개념이나 논문이 없으면 {}, 임베딩·Milvus 가 실패하면 경고 후 None."""
    ids = [c for c in dict.fromkeys(cnts_ids) if '"' not in c and "\\" not in c]   # 식 안 문자열을 깨는 id 는 뺀다
    if not concepts or not ids:
        return {}
    try:
        from pymilvus.exceptions import MilvusException
        from services.ingestion.embedder import embed_texts
        from services.ingestion.indexer import ensure_collection
    except ImportError as e:
        log.warning("[membership] 임베딩·Milvus 모듈을 불러오지 못했다 — 하위질문 소속으로 바꾼다: %s", e)
        return None
    try:
        dense, _ = embed_texts(list(concepts))
        rows = ensure_collection().query(
            expr=f"book_id in [{_ids_expr(ids)}] && chunk_idx == -1",
            output_fields=["book_id", "embedding"], limit=len(ids),
        )
    except (*_FAILURES, MilvusException) as e:
        log.warning("[membership] 개념 친밀도 계산 실패 — 하위질문 소속으로 바꾼다: %s: %s",
                    type(e).__name__, e)
        return None
    vectors = {r["book_id"]: [float(x) for x in r["embedding"]] for r in rows}
    return {
        cnts_id: {concept: cosine(vec, vectors[cnts_id]) for concept, vec in zip(concepts, dense)}
        for cnts_id in ids if cnts_id in vectors
    }
