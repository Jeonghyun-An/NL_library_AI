"""topic_views.py — 주제 단계 응답(TopicsView)을 만드는 순수 함수 (계약 §6 TopicsView·TopicItem)

카드 근거·씨앗 후보 논문의 서지는 출발 잡 보고서의 근거(report.evidence[eid].meta)에서 꺼낸다 — 씨앗 후보는
모두 보고서가 인용한 논문이라 DB 를 다시 읽지 않는다. 보고서에 없는 논문은 제목 자리에 cnts_id 를 둔다.
"""
from services.research_work.seeds import corpus_of, pick_seeds, used_seed_keys


def paper_meta(meta: dict) -> dict:
    meta = meta or {}
    return {"title": str(meta.get("title") or ""), "personal_author": meta.get("personal_author"),
            "pub_date": meta.get("pub_date"), "series_title": meta.get("series_title")}


def topic_item(row, generation) -> dict:
    """주제 한 장. generation 은 그 주제(target = str(id))의 가장 최근 topic_card 생성 — 없으면 None."""
    return {
        "id": row.id,
        "slot": row.slot,
        "origin": row.origin,
        "state": row.state,
        "parent_id": row.parent_id,
        "seed": dict(row.seed) if row.seed else None,          # 사용자 카드의 seed 는 {}
        "card": dict(row.card) if row.card else None,          # 아직 없거나 근거 부족이면 {}
        "generation": {"id": generation.id, "status": generation.status} if generation is not None else None,
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
    }


def _order(row) -> tuple:
    # 처음 4장(slot 1~4)이 자리 순서로 먼저, 그 뒤는 만든 순서(id)
    return (row.slot is None, row.slot or 0, row.id)


def topics_view(work, job, rows, generations) -> dict:
    """GET /api/research/{id}/topics. generations 는 이 연구의 topic_card 생성(끝난 것 포함) — 주제마다 가장
    최근 것을 붙인다. seeds_left 는 [다른 방향] 으로 더 받을 수 있는 씨앗 수다."""
    report = job.report if isinstance(job.report, dict) else {}
    latest: dict[str, object] = {}
    for gen in generations:
        if gen.kind != "topic_card" or gen.target is None:
            continue
        if gen.target not in latest or gen.id > latest[gen.target].id:
            latest[gen.target] = gen
    ordered = sorted(rows, key=_order)
    metas: dict[str, dict] = {}
    for ev in (report.get("evidence") or {}).values():
        if isinstance(ev, dict) and ev.get("cnts_id"):
            metas.setdefault(ev["cnts_id"], ev.get("meta") or {})
    wanted: list[str] = []
    for row in ordered:
        for cnts_id in [*((row.seed or {}).get("papers") or []), *((row.card or {}).get("evidence") or [])]:
            if cnts_id not in wanted:
                wanted.append(cnts_id)
    papers = {c: paper_meta(metas[c]) if c in metas else {**paper_meta({}), "title": c} for c in wanted}
    used = used_seed_keys(row.seed for row in rows)
    return {
        "picked_id": work.topic_id,
        "seeds_left": len(pick_seeds(report, limit=None, exclude=used)),
        "corpus": work.corpus_snapshot or corpus_of(job),
        "papers": papers,
        "items": [topic_item(row, latest.get(str(row.id))) for row in ordered],
    }
