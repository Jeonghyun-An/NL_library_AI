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
from services.research_work.seeds import pick_seeds, seed_evidence
from services.research_work.shapes import ABSTRACT_CHARS, GAP_KEY, SECTION_PAPERS_MAX

USER_CARD_SEEDS = 3      # 직접 쓴 카드(씨앗 없음)일 때 보고서에서 고르는 씨앗 수


def section_figures(years: list[int], n: int) -> list[dict]:
    """이 절에 주는 수치 — 근거 논문의 편수·연도뿐이다. 있는 것만 F1 부터 차례로 번호를 붙인다.
    ① 이 절에 준 논문 수 ② 발행 연도 범위(연도를 아는 논문이 있을 때, 한 해면 그 해).
    소장 KCI 적재분은 주지 않는다 — 절·문단 프롬프트가 [F#] 를 근거 논문의 편수·연도에만 쓰라고 하는데, 쓰지 말라는
    값을 목록에 두면 모델이 옮긴다(운영 2026-10-14 prior.g2 '…[F3]건에 달한다' → 값 칩 198,518). 적재분 기준은
    화면 머리띠(workPhase.scopeLine)와 주제 카드 수치 문장이 말한다."""
    items = [("이 절에 준 논문 수", str(n))]
    known = sorted({y for y in years if isinstance(y, int)})
    if known:
        span = str(known[0]) if known[0] == known[-1] else f"{known[0]}~{known[-1]}"
        items.append(("발행 연도 범위", span))
    return [figure(f"F{i}", label, value) for i, (label, value) in enumerate(items, start=1)]


def gap_seeds(topic_seed: dict, report: dict) -> list[dict]:
    """연구 공백 절의 씨앗(계약 §4 seed 모양 + evidence). 06b 의 공백 재료는 보고서의 향후 과제와 critic 이
    insufficient 로 본 하위질문 note 로 한정한다(spec §5-5).
    고른 카드면 그 카드의 씨앗 하나만 쓴다 — 카드의 주제는 씨앗의 글에서 나오는데, 종합은 절마다 그 절 하위질문과 상관없는
    향후 과제를 써서 씨앗이 들어 있던 절의 이웃(다른 과제·그 하위질문의 note)은 고른 주제와 어긋난다(운영 630e0d65·d60a5dc1
    2026-10-14: 연구 공백 절이 고른 주제가 아닌 그 절 하위질문의 공백을 썼다. 넘기는 논문은 씨앗의 papers 라 줄지 않는다).
    직접 쓴 카드(씨앗 {})면 보고서 전체에서 pick_seeds 로 USER_CARD_SEEDS 개를 고른다.
    씨앗마다 보고서가 그 향후 과제에 달았던 근거(cnts_id)를 evidence 로 붙인다(seeds.seed_evidence — gap_input 이 [E#] 로)."""
    if not topic_seed or not topic_seed.get("key"):
        seeds = pick_seeds(report, limit=USER_CARD_SEEDS)
    else:
        seeds = [topic_seed]
    return [{**s, "evidence": seed_evidence(report, s)} for s in seeds]


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


def _common(question: str, topic: dict, research_question: str, papers: list[dict]) -> dict:
    return {
        "question": question,
        "topic": {"id": topic.get("id"), "title": topic.get("title") or ""},
        "research_question": research_question,
        "papers": papers,
        "figures": section_figures([p["year"] for p in papers if p["year"]], len(papers)),
    }


def prior_input(*, question: str, topic: dict, research_question: str, group: dict,
                books: dict, excerpts: dict) -> dict:
    """선행연구 묶음 하나(group = 목차의 {key, name, hint, papers})의 절 입력(계약 §3). 논문은 section_papers 로
    6편까지. basis.papers 는 묶음의 논문 전부다 — 목차에서 묶음을 바꾸면 '다시 맞춤 필요'가 뜨게(계약 §4 stale).
    basis.question 은 이 절을 쓸 때의 연구 질문이다 — 질문을 바꿔도 '다시 맞춤 필요'가 뜨게(06e)."""
    papers = _papers(section_papers(group.get("papers") or []), books, excerpts)
    return {
        "key": group["key"], "kind": "prior",
        **_common(question, topic, research_question, papers),
        "group": {"name": group.get("name") or group.get("hint") or ""},
        "seeds": [],
        "basis": {"topic_id": topic.get("id"), "papers": list(group.get("papers") or []),
                  "question": research_question},
    }


_SENTENCE_END = (".", "?", "!")


def _gap_seed_text(seed: dict, eid_of: dict[str, str]) -> str:
    """프롬프트 '공백 후보' 한 줄의 글.
    - insufficient 씨앗: critic note 원문은 자기점검 말투('제시된 근거들은 …부족합니다')라 모델이 옮긴다(운영 630e0d65 gap
      p3). 그 하위질문에 답할 근거가 소장 코퍼스에서 충분히 확인되지 않았다는 한 줄로 쓴다.
    - 향후 과제 씨앗: 보고서가 그 과제에 달았던 근거(seed.evidence)가 이 절 논문(eid_of — cnts_id → 이 절의 E#)에 있으면
      그 [E#] 를 문장 끝 마침표 앞에 붙인다 — 모델이 씨앗 문장을 옮겨도 근거 표시가 남는다(630e0d65 gap p1)."""
    if seed.get("kind") == "insufficient":
        return f"'{seed.get('heading') or ''}'에 답할 근거가 소장 코퍼스에서 충분히 확인되지 않았다."
    text = (seed.get("text") or "").strip()
    marks = " ".join(f"[{eid_of[c]}]" for c in dict.fromkeys(seed.get("evidence") or []) if c in eid_of)
    if not marks:
        return text
    if text.endswith(_SENTENCE_END):
        return f"{text[:-1]} {marks}{text[-1]}"
    return f"{text} {marks}"


def gap_input(*, question: str, topic: dict, research_question: str, seeds: list[dict],
              books: dict, excerpts: dict) -> dict:
    """연구 공백 절의 입력(계약 §3). 논문은 씨앗에 묶인 근거 논문을 씨앗 순서로 모아 6편까지(spec §5-5).
    seeds 는 프롬프트에 그대로 쓸 줄(_gap_seed_text)과 그 씨앗의 하위질문(기록용)이다."""
    cnts = section_papers([c for s in seeds for c in s.get("papers") or []])
    papers = _papers(cnts, books, excerpts)
    eid_of = {p["cnts_id"]: p["eid"] for p in papers}
    return {
        "key": GAP_KEY, "kind": "gap",
        **_common(question, topic, research_question, papers),
        "group": None,
        "seeds": [{"heading": s.get("heading") or "", "text": _gap_seed_text(s, eid_of)} for s in seeds],
        "basis": {"topic_id": topic.get("id"), "papers": cnts, "question": research_question},
    }
