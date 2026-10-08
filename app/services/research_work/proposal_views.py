"""proposal_views.py — 계획서 API(GET /api/research/{id}/proposal·목차 PUT 응답)의 응답 모양(순수 함수 + build_citation).

- 다시 맞춤 필요(stale)는 저장하지 않고 조회 때 센다(계약 §4): 목차는 고른 주제가 바뀌었거나 묶음 논문 합집합이
  지금 담음과 다르거나 핵심 개념이 목차를 만들 때(outline.concepts)와 다르거나 고른 카드의 제목이 목차의
  topic.title 과 다르면(호출부가 넘긴 경우만), 선행연구 절(prior.gN)은 주제가 바뀌었거나 그 절의 근거 논문이 그 묶음 논문과 다르면,
  그 밖의 절은 주제가 바뀌었으면. 앞 단계를 바꿔도 뒤 단계를 지우지 않고 배지만 붙인다(spec §4).
- AI 사용 공개(disclosure)는 끝난(done) 생성의 단계·모델·완료 시각·시도 목록이다. 시도에는 model·outcome 만
  싣는다 — attempts.error 에는 내부 호스트 주소가 든 예외 문자열이 있다(06a 넘김 7).
- 참고문헌(references)은 문단이 인용한 논문만, 논문 상세 인용과 같은 build_citation(book)["korean"] 으로 만든다
  (06b 정함 8 — UCI(없으면 URL) 포함, 인용 쪽 없음). 서지가 없는 논문은 '서지 정보 없음'.
- drafts 는 쓰는 중(queued·running)인 절 생성의 입력에서 [E#]·[F#] 지도를 꺼낸 것 — 스트리밍 조각을 화면이
  칩으로 그리는 재료다.
- topic_source 는 목차를 만든 주제(outline.topic.id) 행의 origin·card.edited — spec §5-2 'card.edited 는 데이터로만
  남기고(계보·공개 부록용)', 공개 부록의 '주제:' 줄 재료다. 행은 호출부가 이미 읽은 고른 주제를 넘기고, 그 id 가
  목차의 주제와 다르면 None.
"""
from models.research_work import GEN_OPEN_STATUSES, ResearchTopic
from services.research_work.reading_views import book_meta
from services.research_work.seeds import corpus_of
from services.research_work.shapes import GAP_KEY, PRIOR_KEYS
from services.search.paper_citation import build_citation

SECTION_ORDER = ("topic", "background", *PRIOR_KEYS, GAP_KEY, "question", "method")   # 문서 순서


def _section_keys(sections: dict) -> list[str]:
    def key(k: str):
        return (SECTION_ORDER.index(k) if k in SECTION_ORDER else len(SECTION_ORDER), k)
    return sorted(sections, key=key)


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def stale_flags(work, outline: dict, sections: dict, picked: set[str], topic_title: str | None = None) -> dict:
    """topic_title 은 고른 카드의 지금 제목(호출부가 고른 주제 행에서 읽는다) — None 이면 제목은 견주지 않는다."""
    topic_id = work.topic_id
    groups = {g.get("key"): set(g.get("papers") or []) for g in (outline or {}).get("groups") or []}
    outline_stale = bool(outline) and (
        (outline.get("topic") or {}).get("id") != topic_id
        or set().union(*groups.values()) != set(picked)
        or list(outline.get("concepts") or []) != list(work.concepts or [])
        or (topic_title is not None and (outline.get("topic") or {}).get("title") != topic_title)
    )
    flags: dict[str, bool] = {}
    for key in _section_keys(sections or {}):
        basis = (sections[key] or {}).get("basis") or {}
        stale = basis.get("topic_id") != topic_id
        if key.startswith("prior."):
            stale = stale or key not in groups or set(basis.get("papers") or []) != groups[key]
        flags[key] = stale
    return {"outline": outline_stale, "sections": flags}


def disclosure_of(generations) -> dict:
    steps = []
    for g in sorted(generations, key=lambda g: g.id):
        if g.status != "done":
            continue
        attempts = [{"model": a.get("model"), "outcome": a.get("outcome")}
                    for a in (g.output or {}).get("attempts") or [] if isinstance(a, dict)]
        steps.append({"kind": g.kind, "target": g.target, "model": g.model,
                      "finished_at": _iso(g.finished_at), "attempts": attempts})
    return {"steps": steps}


def cited_papers(sections: dict) -> list[str]:
    """문단 cites 의 cnts_id — 문서 순서(절 → 문단)로 처음 나온 순."""
    out: list[str] = []
    for key in _section_keys(sections or {}):
        for p in (sections[key] or {}).get("paragraphs") or []:
            for cnts_id in p.get("cites") or []:
                if cnts_id not in out:
                    out.append(cnts_id)
    return out


def _open_sections(generations) -> list:
    return [g for g in generations if g.kind == "section" and g.status in GEN_OPEN_STATUSES]


def drafts_of(open_section_gens) -> dict:
    out: dict[str, dict] = {}
    for g in sorted(open_section_gens, key=lambda g: g.id):
        inp = g.input or {}
        out[g.target] = {
            "gen_id": g.id,
            "evidence": {p["eid"]: p["cnts_id"] for p in inp.get("papers") or []
                         if p.get("eid") and p.get("cnts_id")},
            "figures": list(inp.get("figures") or []),
        }
    return out


def paper_ids(proposal, generations) -> list[str]:
    """서지가 필요한 논문 — 목차 묶음 논문 → 절 근거 → 쓰는 중인 절의 근거, 처음 나온 순. 호출부가 고른 카드의
    근거를 더해 BookRepository 로 한 번에 읽는다."""
    outline = (proposal.outline if proposal is not None else None) or {}
    sections = (proposal.sections if proposal is not None else None) or {}
    ids: list[str] = []

    def add(cnts_id) -> None:
        if isinstance(cnts_id, str) and cnts_id and cnts_id not in ids:
            ids.append(cnts_id)

    for g in outline.get("groups") or []:
        for cnts_id in g.get("papers") or []:
            add(cnts_id)
    for key in _section_keys(sections):
        for cnts_id in ((sections[key] or {}).get("evidence") or {}).values():
            add(cnts_id)
    for draft in drafts_of(_open_sections(generations)).values():
        for cnts_id in draft["evidence"].values():
            add(cnts_id)
    return ids


def _reference(cnts_id: str, book) -> str:
    return build_citation(book)["korean"] if book is not None else f"서지 정보 없음 ({cnts_id})."


def _topic_source(outline: dict, topic_row) -> dict | None:
    """목차 topic.id 의 주제 행이 넘어왔으면 {origin, edited} — 없거나 다른 주제(목차 뒤 주제를 바꿈)면 None."""
    if topic_row is None or not outline or (outline.get("topic") or {}).get("id") != topic_row.id:
        return None
    return {"origin": topic_row.origin, "edited": bool((topic_row.card or {}).get("edited"))}


def proposal_view(work, job, proposal, books: dict, generations, picked: set[str],
                  topic_row: ResearchTopic | None = None) -> dict:
    """ProposalView. proposal 이 None(목차를 아직 만들지 않음)이면 version 0·outline None·sections {}.
    books 는 {cnts_id: BookOut}, generations 는 이 연구의 생성 전부, picked 는 지금 담은 논문, topic_row 는
    호출부가 읽은 고른 주제 행 — 카드 제목은 stale 셈에, origin·card.edited 는 topic_source 에 쓴다(None 이면
    제목은 견주지 않고 topic_source 도 None)."""
    outline = dict((proposal.outline if proposal is not None else None) or {})
    sections = dict((proposal.sections if proposal is not None else None) or {})
    ids = paper_ids(proposal, generations)
    ids += [cnts_id for cnts_id in books if cnts_id not in ids]
    topic_title = (topic_row.card or {}).get("title") if topic_row is not None else None
    return {
        "version": proposal.version if proposal is not None else 0,
        "outline": outline or None,
        "sections": sections,
        "drafts": drafts_of(_open_sections(generations)),
        "papers": {cnts_id: book_meta(cnts_id, books.get(cnts_id)) for cnts_id in ids},
        "references": {cnts_id: _reference(cnts_id, books.get(cnts_id))
                       for cnts_id in cited_papers(sections)},
        "corpus": work.corpus_snapshot or corpus_of(job),
        "stale": stale_flags(work, outline, sections, picked, topic_title),
        "disclosure": disclosure_of(generations),
        "topic_source": _topic_source(outline, topic_row),
    }
