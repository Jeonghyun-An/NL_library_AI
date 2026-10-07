"""views.py — 연구 어시스턴트 API 의 응답 모양을 만드는 순수 함수(DB·네트워크 없음).

- work_view: GET /api/research/{id}/work·이어가기 응답·연구 SSE 의 snapshot 이 같은 모양을 쓴다 — 갈리면 새로고침한
  화면과 재접속한 화면이 같은 연구를 다르게 그린다.
- candidates_from_snapshot: 이어가기 때 채택 근거 전체(state_snapshot.evidence)를 읽기 목록 후보로 넣는
  값. 들어온 경로(origin_ref)는 저장된 값만 쓴다(spec §5-4) — 탐색 때만 있던 rank_score 는 저장되지
  않으므로 쓰지 않는다.
- pool_from_job: GET /api/research/{id}/pool — 채택 근거 전체(보고서에 인용되지 않은 것 포함)와 critic 이 뺀 논문.

하위질문 번호를 키로 쓰는 dict 는 문자열 키다("0", "1") — JSONB 에 저장되면 정수 키가 문자열이 되므로,
처음부터 문자열로 두어야 넣은 값과 읽은 값이 같다.
"""


_NOT_WAITING = {"position": None, "eta_sec": None, "others_ahead": False}


def work_view(work, generations, queue: dict[int, dict]) -> dict:
    """연구 한 건. generations 는 호출부가 고른 생성(열린 것 전부 + 최근 끝난 것)이고 id 순으로 싣는다.
    queue 는 대기 중(queued) 생성마다 dispatch.queue_info 의 결과(position·eta_sec·others_ahead) — 없는 생성은
    기다리지 않는다(position·eta_sec 는 None). corpus 는 이어가기 때 담은 코퍼스 스냅숏이다."""
    return {
        "id": str(work.id),
        "phase": work.phase,
        "concepts": list(work.concepts or []),
        "memo": work.memo,
        "is_example": bool(work.is_example),
        "progress": dict(work.progress or {}),
        "topic_id": work.topic_id,
        "corpus": dict(work.corpus_snapshot) if work.corpus_snapshot else None,
        "generations": [
            {"id": g.id, "kind": g.kind, "target": g.target, "status": g.status,
             "model": g.model, "error": g.error, **_waiting(queue.get(g.id))}
            for g in sorted(generations, key=lambda g: g.id)
        ],
    }


def _waiting(info: dict | None) -> dict:
    if info is None:
        return dict(_NOT_WAITING)
    return {"position": info.get("position"), "eta_sec": info.get("eta_sec"),
            "others_ahead": bool(info.get("others_ahead"))}


def _empty_path() -> dict:
    return {"subq_idx": [], "rank": {}, "chunks": {}, "chunk_scores": {}, "verdict": {}}


def _first_rounds(sq: dict) -> dict[str, int]:
    """cnts_id → 이 하위질문에서 처음 채택된 회차. 회차의 adopted_papers(06a 뒤 잡)에서만 안다."""
    first: dict[str, int] = {}
    for r in sq.get("rounds") or []:
        for p in r.get("adopted_papers") or []:
            first.setdefault(p.get("cnts_id"), r.get("round"))
    return first


def candidates_from_snapshot(snapshot: dict | None) -> list[dict]:
    """research_reading 삽입 값 — 채택 근거 한 편당 한 행. 순서는 하위질문 순 → 그 안의 순위 순."""
    if not snapshot:
        return []
    evidence = snapshot.get("evidence") or {}
    paths: dict[str, dict] = {}            # eid → origin_ref
    for sq in snapshot.get("subquestions") or []:
        key = str(sq.get("idx"))
        chunks_of = sq.get("evidence_chunks") or {}
        scores = sq.get("chunk_scores") or {}
        first = _first_rounds(sq)
        for rank, eid in enumerate(sq.get("evidence_ids") or [], start=1):
            ev = evidence.get(eid)
            if ev is None:
                continue
            path = paths.setdefault(eid, _empty_path())
            chunk_ids = list(chunks_of.get(eid) or [])
            path["subq_idx"].append(sq.get("idx"))
            path["rank"][key] = rank
            path["chunks"][key] = chunk_ids
            path["chunk_scores"][key] = {c: scores[c] for c in chunk_ids if c in scores}
            path["verdict"][key] = sq.get("verdict")
            if ev.get("cnts_id") in first:
                path.setdefault("first_round", {})[key] = first[ev["cnts_id"]]
    for eid in evidence:
        # 어느 하위질문에도 남지 않은 근거(무관 제외가 지우지 못한 옛 스냅샷) — 경로 없이 뒤에 둔다
        paths.setdefault(eid, _empty_path())

    out: list[dict] = []
    seen: set[str] = set()
    for eid, path in paths.items():
        cnts_id = (evidence.get(eid) or {}).get("cnts_id")
        if not cnts_id or cnts_id in seen:
            continue
        seen.add(cnts_id)
        out.append({"cnts_id": cnts_id, "origin": "evidence", "origin_ref": path})
    return out


def _brief(p: dict) -> dict:
    return {"cnts_id": p.get("cnts_id"), "title": p.get("title"),
            "personal_author": p.get("personal_author"), "pub_date": p.get("pub_date")}


def _rounds_by_subq(steps: list[dict]) -> dict[int, list[dict]]:
    """하위질문 번호 → 탐색 단계의 회차 기록. steps 는 seq 순 — 재시도로 같은 하위질문의 탐색 단계가
    다시 생기면 뒤의 것이 지금 상태다."""
    out: dict[int, list[dict]] = {}
    for s in steps:
        if s.get("kind") != "search" or s.get("subq_idx") is None:
            continue
        out[s["subq_idx"]] = list((s.get("result") or {}).get("rounds") or [])
    return out


def _adopted_from_snapshot(snapshot: dict) -> list[dict]:
    evidence = snapshot.get("evidence") or {}
    items: dict[str, dict] = {}            # eid → 항목
    for sq in snapshot.get("subquestions") or []:
        for rank, eid in enumerate(sq.get("evidence_ids") or [], start=1):
            ev = evidence.get(eid)
            if ev is None:
                continue
            item = items.get(eid)
            if item is None:
                meta = ev.get("meta") or {}
                item = items[eid] = {**_brief({**meta, "cnts_id": ev.get("cnts_id")}),
                                     "series_title": meta.get("series_title"),
                                     "subq_idx": [], "rank": rank}
            item["subq_idx"].append(sq.get("idx"))
            # 여러 하위질문에 채택된 논문은 그중 가장 앞선 순위
            item["rank"] = min(item["rank"], rank)
    for eid, ev in evidence.items():
        if eid not in items:
            meta = ev.get("meta") or {}
            items[eid] = {**_brief({**meta, "cnts_id": ev.get("cnts_id")}),
                          "series_title": meta.get("series_title"), "subq_idx": [], "rank": None}
    return list(items.values())


def _adopted_from_rounds(rounds: dict[int, list[dict]]) -> list[dict]:
    """도는 잡 — 하위질문마다 adopted_papers 가 있는 마지막 회차가 지금 채택 목록이다(순위순).
    서지는 그 논문이 새로 채택된 회차에만 실리므로 모든 회차에서 모은다. 학술지는 회차에 없다."""
    briefs: dict[str, dict] = {}
    for idx_rounds in rounds.values():
        for r in idx_rounds:
            for p in r.get("adopted_papers") or []:
                if p.get("new"):
                    briefs.setdefault(p["cnts_id"], p)
    items: dict[str, dict] = {}
    for idx in sorted(rounds):
        last = next((r for r in reversed(rounds[idx]) if "adopted_papers" in r), None)
        if last is None:
            continue                       # 06a 전 잡의 회차 — 채택 목록이 없다
        for p in last["adopted_papers"]:
            cnts_id = p["cnts_id"]
            item = items.get(cnts_id)
            if item is None:
                item = items[cnts_id] = {**_brief(briefs.get(cnts_id, {"cnts_id": cnts_id})),
                                         "series_title": None, "subq_idx": [], "rank": p["rank"]}
            item["subq_idx"].append(idx)
            item["rank"] = min(item["rank"], p["rank"])
    return list(items.values())


def _excluded_from_rounds(rounds: dict[int, list[dict]]) -> list[dict]:
    return [
        {**_brief(p), "subq_idx": idx, "round": r.get("round"), "note": r.get("note")}
        for idx in sorted(rounds)
        for r in rounds[idx]
        for p in r.get("excluded_papers") or []
    ]


def _excluded_from_trail(trail: list[dict], rounds: dict[int, list[dict]]) -> list[dict]:
    """끝난 잡 — 보고서 trail 의 제외 논문(보고서의 '관련성이 낮아 제외한 논문'과 같은 값)에, 어느 회차에서
    뺐는지와 그 회차의 critic note 를 회차 기록에서 찾아 붙인다. 논문별 제외 사유는 저장된 곳이 없다
    (spec §5-4). trail 은 하위질문 순이라 그 번호가 하위질문 번호다."""
    out: list[dict] = []
    for idx, t in enumerate(trail):
        where: dict[str, tuple] = {}
        for r in rounds.get(idx, []):
            for p in r.get("excluded_papers") or []:
                where.setdefault(p.get("cnts_id"), (r.get("round"), r.get("note")))
        for p in t.get("excluded_papers") or []:
            rnd, note = where.get(p.get("cnts_id"), (None, None))
            out.append({**_brief(p), "subq_idx": idx, "round": rnd, "note": note})
    return out


def pool_from_job(job, steps: list[dict]) -> dict:
    """채택 근거: 스냅샷(탐색이 끝나면 저장된다)이 있으면 그 근거 전부, 없으면(탐색 중) 회차의 adopted_papers.
    제외 논문: 보고서 trail 이 있으면 그것, 없으면 회차의 excluded_papers."""
    rounds = _rounds_by_subq(steps)
    snapshot = job.state_snapshot
    adopted = _adopted_from_snapshot(snapshot) if snapshot else _adopted_from_rounds(rounds)
    trail = (job.report or {}).get("trail")
    excluded = _excluded_from_trail(trail, rounds) if trail else _excluded_from_rounds(rounds)
    return {"adopted": adopted, "excluded": excluded}
