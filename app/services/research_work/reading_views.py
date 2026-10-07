"""reading_views.py — 읽기 목록 API(GET·PUT /api/research/{id}/reading)의 응답 모양(순수 함수, DB·네트워크 없음).

- 들어온 경로(reading_path)는 저장된 값만 쓴다(spec §5-4): 행의 origin_ref(하위질문·그 안 순위·매칭 대목 id 와
  점수·critic 판정·처음 채택된 회차, 되살린 논문이면 뺀 하위질문·회차·note)와 잡의 state_snapshot 에 남은 대목 글.
  탐색 때만 있던 rank_score 는 저장되지 않으므로 쓰지 않는다. 대목 글은 팝오버용으로 PATH_CHUNK_CHARS 에서 자른다.
- critic 이 뺀 논문(excluded_candidates)은 06a pool_from_job 의 제외 목록에서 이미 행이 있는 논문을 뺀 것이다.
  회차·note 는 스냅숏의 subquestions[].rounds 로 붙인다 — 탐색 단계 result.rounds 와 같은 회차 기록이라(runner 가
  두 곳에 같은 목록을 쓴다) research_steps 를 다시 읽지 않는다.
- 서지(meta)는 호출부가 BookRepository.get_by_cnts_ids 한 번으로 읽어 넘긴다. 소장 목록에 없는 논문은 제목 자리에
  cnts_id 를 둔다.
- 다시 맞춤 필요(stale)는 저장하지 않고 조회 때 센다(spec §5-2): 목차를 만든 뒤 고른 주제가 바뀌었으면
  (outline.topic.id != work.topic_id) 참, 목차가 없으면 거짓. 목차는 호출부가 research_proposals 에서 읽어 넘긴다.
"""
from services.research_work.shapes import PATH_CHUNK_CHARS
from services.research_work.views import pool_from_job


def subquestions_of(job) -> list[str]:
    """잡의 하위질문(승인된 계획). 하위질문 번호(subq_idx)는 이 목록의 위치다."""
    return [s for s in (job.plan or []) if isinstance(s, str)]


def book_meta(cnts_id: str, book) -> dict:
    """PaperMeta — BookOut(없으면 None) → 화면이 쓰는 서지 넷."""
    if book is None:
        return {"title": cnts_id, "personal_author": None, "pub_date": None, "series_title": None}
    return {"title": book.title or cnts_id, "personal_author": book.personal_author,
            "pub_date": book.pub_date, "series_title": book.series_title}


def _subquestion(subquestions: list[str], idx) -> str:
    if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(subquestions):
        return subquestions[idx]
    return ""


def _chunk_index(snapshot: dict | None) -> dict[str, dict]:
    """chunk_id → 스냅숏의 대목(chunk_id 는 '{cnts_id}__{chunk_idx}' 라 논문을 가로질러 겹치지 않는다)."""
    out: dict[str, dict] = {}
    for ev in ((snapshot or {}).get("evidence") or {}).values():
        for chunk in (ev or {}).get("chunks") or []:
            cid = chunk.get("chunk_id")
            if cid and cid not in out:
                out[cid] = chunk
    return out


def reading_path(origin: str, origin_ref: dict, snapshot: dict | None, subquestions: list[str]) -> dict:
    """ReadingPath. evidence 는 하위질문마다 순위·판정·처음 채택된 회차·매칭 대목(스냅숏에 글이 남은 것만),
    revived 는 뺀 하위질문·회차·note, user 는 표시만."""
    ref = origin_ref if isinstance(origin_ref, dict) else {}
    path = {"subqs": [], "revived": None, "user": origin == "user"}
    if origin == "revived":
        idx = ref.get("subq_idx")
        path["revived"] = {"subq_idx": idx, "subquestion": _subquestion(subquestions, idx),
                           "round": ref.get("round"), "note": ref.get("note") or ""}
        return path
    if origin != "evidence":
        return path
    chunks = _chunk_index(snapshot)
    for idx in ref.get("subq_idx") or []:
        key = str(idx)
        scores = (ref.get("chunk_scores") or {}).get(key) or {}
        path["subqs"].append({
            "idx": idx,
            "subquestion": _subquestion(subquestions, idx),
            "rank": (ref.get("rank") or {}).get(key),
            "verdict": (ref.get("verdict") or {}).get(key),
            "first_round": (ref.get("first_round") or {}).get(key),
            "chunks": [
                {"chunk_id": cid, "page_start": chunks[cid].get("page_start"),
                 "page_end": chunks[cid].get("page_end"), "score": scores.get(cid),
                 "text": (chunks[cid].get("text") or "")[:PATH_CHUNK_CHARS]}
                for cid in (ref.get("chunks") or {}).get(key) or [] if cid in chunks
            ],
        })
    return path


def reading_item(row, meta: dict, snapshot: dict | None, subquestions: list[str]) -> dict:
    return {
        "cnts_id": row.cnts_id, "state": row.state, "origin": row.origin, "note": row.note,
        "group_label": row.group_label, "position": row.position, "meta": meta,
        "path": reading_path(row.origin, row.origin_ref, snapshot, subquestions),
    }


def _count(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def funnel(report: dict, rows) -> dict:
    """깔때기 '검토 → 채택 → 후보 → 담음'. 검토·채택은 보고서 stats(탐색 끝 값), 후보는 뺌이 아닌 행, 담음은 in."""
    stats = (report or {}).get("stats") or {}
    return {
        "reviewed": _count(stats.get("papers_reviewed")),
        "adopted": _count(stats.get("evidence_adopted")),
        "candidates": sum(1 for r in rows if r.state != "out"),
        "picked": sum(1 for r in rows if r.state == "in"),
    }


def excluded_candidates(job, rows) -> list[dict]:
    """critic 이 뺀 논문 중 아직 읽기 목록 행이 없는 것 — 후보 서랍의 [되살리기] 대상. 한 논문은 한 번
    (여러 하위질문에서 빠졌으면 하위질문 순 → 회차 순으로 처음 것)."""
    snapshot = job.state_snapshot if isinstance(job.state_snapshot, dict) else {}
    steps = [{"kind": "search", "subq_idx": sq.get("idx"), "result": {"rounds": sq.get("rounds") or []}}
             for sq in snapshot.get("subquestions") or [] if isinstance(sq, dict)]
    have = {r.cnts_id for r in rows}
    subquestions = subquestions_of(job)
    out: list[dict] = []
    seen: set[str] = set()
    for p in pool_from_job(job, steps)["excluded"]:
        cnts_id = p.get("cnts_id")
        if not cnts_id or cnts_id in have or cnts_id in seen:
            continue
        seen.add(cnts_id)
        out.append({
            "cnts_id": cnts_id, "title": p.get("title") or cnts_id,
            "personal_author": p.get("personal_author"), "pub_date": p.get("pub_date"),
            "subq_idx": p.get("subq_idx"), "subquestion": _subquestion(subquestions, p.get("subq_idx")),
            "round": p.get("round"), "note": p.get("note") or "",
        })
    return out


def _best_rank(origin_ref) -> int | None:
    ranks = (origin_ref or {}).get("rank") if isinstance(origin_ref, dict) else None
    values = [v for v in (ranks or {}).values() if isinstance(v, int) and not isinstance(v, bool)]
    return min(values) if values else None


def reading_order(rows) -> list:
    """사용자가 정한 순서(position, 없으면 뒤) → 하위질문 안 가장 앞선 순위(없으면 뒤) → cnts_id."""
    def key(row):
        rank = _best_rank(row.origin_ref)
        return (row.position is None, row.position or 0, rank is None, rank or 0, row.cnts_id)
    return sorted(rows, key=key)


def reading_view(work, job, rows, books: dict, outline: dict | None = None) -> dict:
    """ReadingView. books 는 {cnts_id: BookOut} — 행 전부의 서지를 한 번에 읽은 것. outline 은 계획서의 목차
    (없으면 None·{}) — 목차를 만든 뒤 고른 주제가 바뀌었는지(stale)만 본다."""
    subquestions = subquestions_of(job)
    snapshot = job.state_snapshot if isinstance(job.state_snapshot, dict) else None
    report = job.report if isinstance(job.report, dict) else {}
    return {
        "topic_id": work.topic_id,
        "stale": bool(outline) and (outline.get("topic") or {}).get("id") != work.topic_id,
        "subquestions": subquestions,
        "funnel": funnel(report, rows),
        "items": [reading_item(r, book_meta(r.cnts_id, books.get(r.cnts_id)), snapshot, subquestions)
                  for r in reading_order(rows)],
        "excluded": excluded_candidates(job, rows),
    }
