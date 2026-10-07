"""seeds.py — 보고서 씨앗 고르기·주제 카드 입력·코퍼스 스냅숏 (순수 함수, spec §5-2, 계약 §3·§4·§5)

씨앗 = 보고서가 남긴 '더 볼 것' 한 문장이다. 원천은 둘이다.
  - 절의 향후 과제(report.sections[i].future[j] — 근거 eid 가 달려 있다) → key 'future:i:j'
  - critic 이 insufficient 로 판정한 하위질문의 note(report.trail[t]) → key 'insufficient:t'
절 순번과 trail 순번은 어긋난다 — 근거 0편 하위질문은 절이 되지 않는다(synthesizer). 그래서 둘을
절 소제목(= 하위질문 문장) == trail.subquestion 으로 잇는다(research/round06-qwen-check/check.py 의
card_seeds 와 같은 방식).

고르는 규칙(pick_seeds): 절마다 후보 줄을 만들고(향후 과제 → 그 하위질문의 insufficient note 순), 절을
한 바퀴씩 돌며 하나씩 고른다 — 서로 다른 절이 먼저 나온다. 같은 글(공백 접고 casefold)은 하나만,
근거 후보가 MIN_TOPIC_EVIDENCE 편 미만인 씨앗은 버린다(카드가 근거 2개를 받칠 수 없다 — 정함 4).
근거 후보(seed_papers)는 씨앗에 묶인 근거(향후 과제의 evidence) → 그 절 논문 순으로 최대 TOPIC_PAPERS_MAX 편.

DB·LLM·네트워크를 쓰지 않는다 — FastAPI(이어가기·다른 방향·주제 조회)와 1회성 재비교 도구가 함께 쓴다.
"""
import re
from collections.abc import Collection, Iterable

from services.research.citations import strip_markers
from services.research_work.shapes import MIN_TOPIC_EVIDENCE, TOPIC_PAPERS_MAX

_YEAR = re.compile(r"(?:19|20)\d{2}")


def _norm(text: object) -> str:
    """소제목·하위질문 비교용 — 앞뒤 공백을 지우고 안쪽 공백을 하나로."""
    return " ".join(str(text or "").split())


def _same_text_key(text: str) -> str:
    return _norm(text).casefold()


def _year(pub_date: object) -> int | None:
    m = _YEAR.search(str(pub_date or ""))
    return int(m.group(0)) if m else None


def _evidence(report: dict) -> dict[str, dict]:
    ev = report.get("evidence")
    return ev if isinstance(ev, dict) else {}


def _metas(report: dict) -> dict[str, dict]:
    """cnts_id → 보고서 근거의 서지(meta). 보고서 evidence 는 절이 인용한 근거만 싣는다."""
    out: dict[str, dict] = {}
    for ev in _evidence(report).values():
        if isinstance(ev, dict) and ev.get("cnts_id"):
            out.setdefault(ev["cnts_id"], ev.get("meta") or {})
    return out


def _corpus(report: dict) -> dict | None:
    rng = report.get("range")
    if not isinstance(rng, dict) or rng.get("n_papers") is None:
        return None
    return {"n_papers": rng["n_papers"], "from": rng.get("from"), "to": rng.get("to")}


def corpus_of(job) -> dict | None:
    """출발 잡의 코퍼스 스냅숏 — 보고서를 만들 때 잰 적재분(report.range) + 잡이 끝난 시각.
    이어가기가 research_works·research_topics 의 corpus_snapshot 에 담는다(계약 §4)."""
    report = job.report if isinstance(job.report, dict) else {}
    corpus = _corpus(report)
    if corpus is None:
        return None
    finished = getattr(job, "finished_at", None)
    return {**corpus, "at": finished.isoformat() if finished is not None else None}


def seed_papers(report: dict, future_eids: list[str], section_idx: int | None) -> list[str]:
    """씨앗의 근거 후보 cnts_id — 씨앗에 묶인 근거(향후 과제의 evidence) → 그 절 논문 순, 중복 없이 최대
    TOPIC_PAPERS_MAX 편. 보고서 evidence 에 서지가 없는 논문은 넣지 않는다(카드 입력에 제목이 있어야 한다)."""
    evidence = _evidence(report)
    known = set(_metas(report))
    out: list[str] = []

    def add(cnts_id: object) -> None:
        if isinstance(cnts_id, str) and cnts_id in known and cnts_id not in out \
                and len(out) < TOPIC_PAPERS_MAX:
            out.append(cnts_id)

    for eid in future_eids or []:
        add((evidence.get(eid) or {}).get("cnts_id"))
    sections = report.get("sections") or []
    section = sections[section_idx] if section_idx is not None and 0 <= section_idx < len(sections) else None
    if isinstance(section, dict):
        for paper in section.get("papers") or []:
            if isinstance(paper, dict):
                add(paper.get("cnts_id"))
    return out


def _adopted(trail: list, t_idx: int | None) -> int | None:
    if t_idx is None:
        return None
    count = trail[t_idx].get("evidence_count")
    return count if isinstance(count, int) and not isinstance(count, bool) else None


def _queues(report: dict) -> list[list[dict]]:
    """절마다 씨앗 후보 줄(향후 과제 → 그 하위질문의 insufficient note). 거르기 전이다."""
    # 절·trail 번호는 보고서의 배열 위치 그대로다(seed key·seed_papers 가 같은 번호를 쓴다)
    sections = [s if isinstance(s, dict) else {} for s in report.get("sections") or []]
    trail = [t if isinstance(t, dict) else {} for t in report.get("trail") or []]
    trail_of: dict[str, int] = {}
    for t_idx, t in enumerate(trail):
        trail_of.setdefault(_norm(t.get("subquestion")), t_idx)
    section_of: dict[str, int] = {}
    queues: list[list[dict]] = []
    for s_idx, sec in enumerate(sections):
        heading = _norm(sec.get("heading"))
        section_of.setdefault(heading, s_idx)
        t_idx = trail_of.get(heading)
        queue = []
        for f_idx, fut in enumerate(sec.get("future") or []):
            if not isinstance(fut, dict):
                continue
            text = _norm(strip_markers(str(fut.get("text") or "")))
            if not text:
                continue
            queue.append({
                "key": f"future:{s_idx}:{f_idx}", "kind": "future", "section_idx": s_idx,
                "subq_idx": t_idx, "heading": heading, "text": text,
                "papers": seed_papers(report, [e for e in fut.get("evidence") or [] if isinstance(e, str)],
                                      s_idx),
                "adopted": _adopted(trail, t_idx),
            })
        queues.append(queue)
    for t_idx, t in enumerate(trail):
        if t.get("verdict") != "insufficient":
            continue
        note = _norm(strip_markers(str(t.get("note") or "")))
        heading = _norm(t.get("subquestion"))
        s_idx = section_of.get(heading)
        if not note or s_idx is None:
            continue                       # 절이 없는 하위질문 — 근거 후보가 없어 카드를 받칠 수 없다
        queues[s_idx].append({
            "key": f"insufficient:{t_idx}", "kind": "insufficient", "section_idx": s_idx,
            "subq_idx": t_idx, "heading": heading, "text": note,
            "papers": seed_papers(report, [], s_idx), "adopted": _adopted(trail, t_idx),
        })
    return queues


def pick_seeds(report: dict, *, limit: int | None, exclude: Collection[str] = ()) -> list[dict]:
    """쓸 씨앗을 고른다(계약 §4 seed 모양). 절을 한 바퀴씩 돌며 하나씩 — 서로 다른 절이 먼저다.
    exclude(이미 카드로 쓴 seed.key)는 돌아가는 순서에서 제 차례를 차지한 채 건너뛴다 — [다른 방향] 이 이미 쓴
    절 다음 절부터 고르게 된다. exclude 와 같은 글도 다시 고르지 않는다. limit 이 None 이면 남은 것 전부."""
    if not isinstance(report, dict) or (limit is not None and limit <= 0):
        return []
    skip = set(exclude)
    queues = [[s for s in q if len(s["papers"]) >= MIN_TOPIC_EVIDENCE] for q in _queues(report)]
    used_text = {_same_text_key(s["text"]) for q in queues for s in q if s["key"] in skip}
    seen: set[str] = set()
    out: list[dict] = []
    for depth in range(max((len(q) for q in queues), default=0)):
        for queue in queues:
            if depth >= len(queue):
                continue
            seed = queue[depth]
            text = _same_text_key(seed["text"])
            if text in seen:
                continue
            seen.add(text)
            if seed["key"] in skip or text in used_text:
                continue
            out.append(seed)
            if limit is not None and len(out) >= limit:
                return out
    return out


def topic_input(question: str, seed: dict, report: dict, topic_id: int) -> dict:
    """주제 카드 생성 1건의 입력(계약 §3 topic_card input). 근거 후보는 E1 부터 차례로 번호를 붙인다 —
    호출마다 붙이는 로컬 번호이고 카드에는 cnts_id 로 저장한다(spec §3 [E#])."""
    metas = _metas(report if isinstance(report, dict) else {})
    papers = []
    for n, cnts_id in enumerate(seed.get("papers") or [], start=1):
        meta = metas.get(cnts_id) or {}
        papers.append({"eid": f"E{n}", "cnts_id": cnts_id,
                       "title": str(meta.get("title") or "(제목 없음)"), "year": _year(meta.get("pub_date"))})
    return {
        "topic_id": topic_id,
        "question": question,
        "seed": {"heading": seed.get("heading") or "", "text": seed.get("text") or ""},
        "papers": papers,
        "adopted": seed.get("adopted"),
        "corpus": _corpus(report if isinstance(report, dict) else {}),
    }


def used_seed_keys(topics: Iterable[dict]) -> set[str]:
    """이미 카드로 쓴 씨앗 key. 원소는 research_topics 의 seed 값이거나 그것을 'seed' 키에 품은 dict 다
    (주제 응답의 TopicItem). 사용자 카드의 seed 는 {} 라 세지 않는다."""
    keys: set[str] = set()
    for topic in topics:
        seed = topic.get("seed") if isinstance(topic, dict) and isinstance(topic.get("seed"), dict) else topic
        if isinstance(seed, dict) and isinstance(seed.get("key"), str) and seed["key"]:
            keys.add(seed["key"])
    return keys
