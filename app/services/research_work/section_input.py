"""section_input.py — 절 생성(kind=section) 입력 만들기 (순수) — spec §5-5, 계약 §3·§8.

생성을 넣는 FastAPI(POST .../sections/{key}/generate)가 목차·서지·원문 대목을 모은 뒤 이 함수들로
research_generations.input 을 만든다. 워커는 이 input 만으로 프롬프트를 그린다(함정 17 — 워커는 DB 텍스트와
LLM 만 쓴다). 근거 번호 [E#] 는 이 절 입력의 로컬 번호(E1 부터)이고, 결과를 저장할 때 evidence 지도
(E# → cnts_id)로 묶인다(정함 9). 수치는 코드가 센 [F#] 로만 준다(정함 3) — 값은 단위 없는 글자다.
06b 는 특징 자리를 초록(ABSTRACT_CHARS 자)으로 대신한다.
"""
from services.research.scoring import parse_pub_year
from services.research_work.markers import figure
from services.research_work.passages import clip
from services.research_work.seeds import pick_seeds
from services.research_work.shapes import ABSTRACT_CHARS, GAP_KEY, SECTION_PAPERS_MAX

GAP_SEEDS_MAX = 4        # 연구 공백 절의 씨앗 상한(고른 카드의 씨앗 포함)
USER_CARD_SEEDS = 3      # 직접 쓴 카드(씨앗 없음)일 때 보고서에서 고르는 씨앗 수


def section_figures(years: list[int], corpus: dict | None, n: int) -> list[dict]:
    """이 절에 주는 수치. 있는 것만 F1 부터 차례로 번호를 붙인다.
    ① 이 절에 준 논문 수 ② 발행 연도 범위(연도를 아는 논문이 있을 때, 한 해면 그 해) ③ 소장 KCI 적재분(코퍼스
    스냅숏이 있을 때, 천 단위 쉼표)."""
    items = [("이 절에 준 논문 수", str(n))]
    known = sorted({y for y in years if isinstance(y, int)})
    if known:
        span = str(known[0]) if known[0] == known[-1] else f"{known[0]}~{known[-1]}"
        items.append(("발행 연도 범위", span))
    n_papers = (corpus or {}).get("n_papers")
    if isinstance(n_papers, int) and n_papers > 0:
        items.append(("소장 KCI 적재분 논문 수", f"{n_papers:,}"))
    return [figure(f"F{i}", label, value) for i, (label, value) in enumerate(items, start=1)]


def gap_seeds(topic_seed: dict, report: dict) -> list[dict]:
    """연구 공백 절의 씨앗(계약 §4 seed 모양, 최대 GAP_SEEDS_MAX). 06b 의 공백 재료는 보고서의 향후 과제와 critic
    이 insufficient 로 본 하위질문 note 로 한정한다(spec §5-5).
    고른 카드의 씨앗을 맨 앞에 두고, 같은 절이나 같은 하위질문에서 나온 다른 씨앗을 pick_seeds 순서로 잇는다.
    직접 쓴 카드(씨앗 {})면 보고서 전체에서 pick_seeds 로 USER_CARD_SEEDS 개를 고른다."""
    if not topic_seed or not topic_seed.get("key"):
        return pick_seeds(report, limit=USER_CARD_SEEDS)
    sec, subq = topic_seed.get("section_idx"), topic_seed.get("subq_idx")
    near = [
        s for s in pick_seeds(report, limit=None, exclude={topic_seed["key"]})
        if (sec is not None and s.get("section_idx") == sec)
        or (subq is not None and s.get("subq_idx") == subq)
    ]
    return [topic_seed, *near][:GAP_SEEDS_MAX]


def section_papers(cnts_ids: list[str], limit: int = SECTION_PAPERS_MAX) -> list[str]:
    """절에 넣을 논문 — 받은 순서 그대로(선행연구 묶음은 절 쓰기 API 가 하위질문 안 순위 → 담은 순서로 다시 세워
    넘긴다 — 목차 편집으로 옮긴 논문은 저장된 묶음 끝에 붙어 있다), 같은 논문은 한 번,
    앞에서 limit 편. 나머지는 참고문헌 후보로만 남는다(spec §5-5)."""
    return list(dict.fromkeys(c for c in cnts_ids if c))[:limit]


def _page_label(excerpt: dict) -> str:
    # 저장된 쪽은 0 부터 센다. 0 은 첫 쪽과 쪽 정보 없음이 겹쳐 쪽을 쓰지 않는다(frontend/utils/citations.ts pageLabel)
    start = excerpt.get("page_start") or 0
    if start <= 0:
        return "대목"
    end = max(excerpt.get("page_end") or start, start)
    return f"대목(쪽 {start + 1})" if end == start else f"대목(쪽 {start + 1}~{end + 1})"


def evidence_block(papers: list[dict]) -> str:
    """프롬프트의 근거 목록 — 논문마다 '[E1] 제목 (연도)' / '초록: …' / '대목(쪽 n~m): …', 논문 사이는 빈 줄.
    연도·초록·대목이 없으면 그 자리를 뺀다. 논문이 없으면 '(없음)'."""
    blocks = []
    for p in papers:
        lines = [f"[{p['eid']}] {p['title']}" + (f" ({p['year']})" if p.get("year") else "")]
        if p.get("abstract"):
            lines.append(f"초록: {p['abstract']}")
        excerpt = p.get("excerpt")
        if excerpt and excerpt.get("text"):
            lines.append(f"{_page_label(excerpt)}: {excerpt['text']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) or "(없음)"


def figure_block(figures: list[dict]) -> str:
    """프롬프트의 수치 목록 — 한 줄에 '[F1] 라벨: 값'. 없으면 '(없음)'."""
    return "\n".join(f"[{f['id']}] {f['label']}: {f['value']}" for f in figures) or "(없음)"


def _papers(cnts_ids: list[str], books: dict, excerpts: dict) -> list[dict]:
    # 서지가 없는 논문(library_catalog 에서 사라진 논문)은 제목 자리에 cnts_id 를 쓴다 — 번호는 그대로 남긴다
    out = []
    for i, cnts in enumerate(cnts_ids, start=1):
        book = books.get(cnts)
        out.append({
            "eid": f"E{i}", "cnts_id": cnts,
            "title": ((getattr(book, "title", None) or "").strip() or cnts),
            "year": parse_pub_year(getattr(book, "pub_date", None)),
            "abstract": clip(getattr(book, "abstract", None) or "", ABSTRACT_CHARS),
            "excerpt": excerpts.get(cnts),
        })
    return out


def _common(question: str, topic: dict, research_question: str, papers: list[dict],
            corpus: dict | None) -> dict:
    return {
        "question": question,
        "topic": {"id": topic.get("id"), "title": topic.get("title") or ""},
        "research_question": research_question,
        "papers": papers,
        "figures": section_figures([p["year"] for p in papers if p["year"]], corpus, len(papers)),
    }


def prior_input(*, question: str, topic: dict, research_question: str, group: dict,
                books: dict, excerpts: dict, corpus: dict | None) -> dict:
    """선행연구 묶음 하나(group = 목차의 {key, name, hint, papers})의 절 입력(계약 §3). 논문은 section_papers 로
    6편까지. basis.papers 는 묶음의 논문 전부다 — 목차에서 묶음을 바꾸면 '다시 맞춤 필요'가 뜨게(계약 §4 stale)."""
    papers = _papers(section_papers(group.get("papers") or []), books, excerpts)
    return {
        "key": group["key"], "kind": "prior",
        **_common(question, topic, research_question, papers, corpus),
        "group": {"name": group.get("name") or group.get("hint") or ""},
        "seeds": [],
        "basis": {"topic_id": topic.get("id"), "papers": list(group.get("papers") or [])},
    }


def gap_input(*, question: str, topic: dict, research_question: str, seeds: list[dict],
              books: dict, excerpts: dict, corpus: dict | None) -> dict:
    """연구 공백 절의 입력(계약 §3). 논문은 씨앗에 묶인 근거 논문을 씨앗 순서로 모아 6편까지(spec §5-5)."""
    cnts = section_papers([c for s in seeds for c in s.get("papers") or []])
    papers = _papers(cnts, books, excerpts)
    return {
        "key": GAP_KEY, "kind": "gap",
        **_common(question, topic, research_question, papers, corpus),
        "group": None,
        "seeds": [{"heading": s.get("heading") or "", "text": s.get("text") or ""} for s in seeds],
        "basis": {"topic_id": topic.get("id"), "papers": cnts},
    }
