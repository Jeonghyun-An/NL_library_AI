"""reading_views.py — 읽기 목록 API(GET·PUT /api/research/{id}/reading)의 응답 모양(순수 함수, DB·네트워크 없음).

- 들어온 경로(reading_path)는 저장된 값만 쓴다(spec §5-4): 행의 origin_ref(하위질문·그 안 순위·매칭 대목 id 와
  점수·critic 판정·처음 채택된 회차, 되살린 논문이면 뺀 하위질문·회차·note)와 잡의 state_snapshot 에 남은 대목 글.
  탐색 때만 있던 rank_score 는 저장되지 않으므로 쓰지 않는다. 대목 글은 팝오버용으로 <br> 를 줄바꿈으로 바꾼 뒤
  PATH_CHUNK_CHARS 에서 자른다(path_chunk_text).
- critic 이 뺀 논문(excluded_candidates)은 06a pool_from_job 의 제외 목록에서 이미 행이 있는 논문을 뺀 것이다.
  회차·note 는 스냅숏의 subquestions[].rounds 로 붙인다 — 탐색 단계 result.rounds 와 같은 회차 기록이라(runner 가
  두 곳에 같은 목록을 쓴다) research_steps 를 다시 읽지 않는다.
- 서지(meta)는 호출부가 BookRepository.get_by_cnts_ids 한 번으로 읽어 넘긴다. 소장 목록에 없는 논문은 제목 자리에
  cnts_id 를 둔다.
- 다시 맞춤 필요(stale)는 저장하지 않고 조회 때 센다(spec §5-2): 목차를 만든 뒤 고른 주제가 바뀌었으면
  (outline.topic.id != work.topic_id) 참, 목차가 없으면 거짓. 목차는 호출부가 research_proposals 에서 읽어 넘긴다.
- 이어가기의 읽기 목록 행(preselect)은 채택 근거를 이 목록과 같은 순서(reading_order)로 세워 앞 READING_PRESELECT 편을
  담음으로 넣는다(사용자 결정 2026-10-13). 미리 담은 행은 들어온 경로에 preselected 를 남기고, 응답의 preselected 가
  그 수를 센다(읽기 목록 머리 안내).
"""
import math
import re

from services.research_work.shapes import PATH_CHUNK_CHARS, READING_PRESELECT
from services.research_work.views import pool_from_job

# 대목 글의 <br> 태그 글자(적재 ODL 마크다운이 표 칸·문단 사이 줄바꿈으로 남긴다)와 빈 줄 연속 — 화면의
# frontend/utils/passageText.ts 와 같은 규칙이다(BR_TAG·BLANK_RUN)
_BR_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLANK_RUN = re.compile(r"\n(?:[ \t]*\n)+")


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


def path_chunk_text(text: str | None) -> str:
    """들어온 경로 팝오버의 대목 글 — <br> 를 줄바꿈으로 바꾸고 빈 줄 연속을 빈 줄 하나로 접은 뒤 PATH_CHUNK_CHARS 에서
    자른다. 원문 그대로 자르면 자른 자리가 '<br>' 안에 떨어져 '<'·'<br' 조각이 끝에 남고(화면은 온전한 <br> 만 바꾼다 —
    운영 2026-10-13), 태그 글자가 상한을 먹어 표가 많은 대목은 실제 글이 줄었다. '<' 하나는 통계 글('p <')일 수 있어
    지우지 않는다."""
    return _BLANK_RUN.sub("\n\n", _BR_TAG.sub("\n", text or ""))[:PATH_CHUNK_CHARS]


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
                 "text": path_chunk_text(chunks[cid].get("text"))}
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


def _best_score(origin_ref) -> float | None:
    """들어온 경로의 대목 점수(chunk_scores — 하위질문마다 {chunk_id: 점수}) 중 가장 높은 값. 숫자가 아닌 값은 건너뛴다."""
    by_subq = origin_ref.get("chunk_scores") if isinstance(origin_ref, dict) else None
    values = [v for scores in (by_subq.values() if isinstance(by_subq, dict) else ()) if isinstance(scores, dict)
              for v in scores.values()
              if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)]
    return max(values) if values else None


def _order_key(position, origin_ref, cnts_id: str) -> tuple:
    rank = _best_rank(origin_ref)
    score = _best_score(origin_ref)
    return (position is None, position or 0, rank is None, rank or 0, score is None, -(score or 0.0), cnts_id)


def reading_order(rows) -> list:
    """사용자가 정한 순서(position, 없으면 뒤) → 하위질문 안 가장 앞선 순위(없으면 뒤) → 대목 점수 중 가장 높은 값이 큰
    순(없으면 뒤 — 같은 순위에서 id 가 작은 옛 논문이 먼저 오지 않게, 사용자 결정 2026-10-14) → cnts_id. 화면의
    frontend/utils/readingList.ts sortedItems 가 같은 키다."""
    return sorted(rows, key=lambda row: _order_key(row.position, row.origin_ref, row.cnts_id))


def preselect(candidates: list[dict], limit: int = READING_PRESELECT) -> list[dict]:
    """이어가기의 읽기 목록 행 값 — candidates_from_snapshot 의 각 편에 state 를 붙인다. 읽기 목록 순서(reading_order —
    이어갈 때는 position 이 없어 하위질문 안 가장 앞선 순위 → 대목 점수 높은 순 → cnts_id)로 앞 limit 편은 담음(in)이고
    들어온 경로에 preselected: true 를 남긴다. 나머지는 후보(candidate). 순서는 candidates 그대로, 받은 dict 는 바꾸지 않는다."""
    ranked = sorted(candidates, key=lambda c: _order_key(None, c["origin_ref"], c["cnts_id"]))
    top = {c["cnts_id"] for c in ranked[:limit]}
    return [{**c, "state": "in", "origin_ref": {**c["origin_ref"], "preselected": True}} if c["cnts_id"] in top
            else {**c, "state": "candidate"} for c in candidates]


def _preselected(rows) -> int:
    """이어가기가 미리 담은 행 수 — 지금 상태와 관계없이(뺀 행도 미리 담았던 것이다)."""
    return sum(1 for r in rows if isinstance(r.origin_ref, dict) and r.origin_ref.get("preselected") is True)


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
        "preselected": _preselected(rows),
        "items": [reading_item(r, book_meta(r.cnts_id, books.get(r.cnts_id)), snapshot, subquestions)
                  for r in reading_order(rows)],
        "excluded": excluded_candidates(job, rows),
    }
