"""topic_card.py — 주제 카드 생성(kind=topic_card, 카드 1장 = 생성 1건) — spec §5-2, 계약 §3, 정함 3·4·5

입력은 보고서 씨앗 하나(seeds.topic_input — 원 질문·절 소제목·씨앗 문장·근거 후보 논문의 로컬 [E#]).
모델은 제목·연구 질문·근거 번호만 쓴다. 그 밖은 코드가 정한다.
  - 근거: 모델이 번호 대신 논문 제목을 써도 제목으로 번호를 찾아 되돌린다(정함 5 — Qwen 표본에서 gemma 실패
    11건 중 10건이 이 실수였다). 예시 한 줄을 넣지 않는다(함정 15 — 개수·분야를 베낀다). 찾지 못한 표기는 버리고,
    되돌린 수를 card.checks.recovered 에 남긴다.
  - 수치 문장: 모델에 수치를 주지 않고 figure_sentence 가 [F#] 를 넣은 고정 틀로 만든다(정함 3 — 표본의 Qwen 이
    근거 없는 해석·숫자 직접 쓰기·문장 깨짐을 냈다). 값은 card.figures 에 함께 저장한다.
  - 개수: 직접 받치는 논문 MIN_TOPIC_EVIDENCE(2)편 이상(정함 4). 미달이면 공통 규칙(generate.run_generation)의
    내용 검사 미달로 다시 부르고, 끝내 미달이면 card 가 None 인 빈 결과로 done — 화면은 '근거 부족' 슬롯이다.
  - 표현: 제목·질문의 단정 표현은 soften_claims 로 바꾸고, [F#] 밖 숫자는 numbers_outside 로 센다('확인 필요').
결과 반영(apply)은 research_topics 의 그 행만 바꾼다 — 사용자가 직접 고친 카드(card.edited)는 덮지 않는다.
"""
import re

from sqlalchemy import select, update

from models.research_work import ResearchTopic
from services.prompts import get_prompt
from services.research.citations import strip_markers
from services.research.llm_json import extract_json
from services.research_work.generate import Executor
from services.research_work.markers import figure, numbers_outside, soften_claims
from services.research_work.progress import refresh_progress
from services.research_work.shapes import MIN_TOPIC_EVIDENCE, TOPIC_QUESTION_MAX, TOPIC_TITLE_MAX

PROMPT = "research_topic_card"

# 카드 수치 — 라벨이 수치 문장 틀을 고른다. 값은 숫자 글자만(단위 없음 — 절 수치와 같은 규칙)이고 단위는
# 문장 틀이 [F#] 바로 뒤에 붙인다(화면 칩·Word 는 [F#] 자리에 값을 그대로 쓴다)
FIG_ADOPTED = "이 하위질문에서 채택한 논문 수"
FIG_LATEST = "고른 근거 가운데 가장 최근 발행 연도"
FIG_CORPUS = "소장 KCI 적재분 논문 수"
_SENTENCES = {
    FIG_ADOPTED: "이 하위질문에서 채택한 논문은 [{id}]편이다.",
    FIG_LATEST: "고른 근거 가운데 가장 최근 논문은 [{id}]년에 나왔다.",
    FIG_CORPUS: "수치는 소장 KCI 적재분 [{id}]편 기준이다.",
}

# 근거 표기 — [E3]·［E03］·【e3】·E3 (뒤에 글이 붙으면 공백으로 떨어져 있어야 한다 — 'E2E 암호화' 는 번호가 아니다)
_EID = re.compile(r"^\s*(?:[\[［【]\s*[Ee]\s*(\d+)\s*[\]］】]|[Ee]\s*(\d+)(?![0-9A-Za-z가-힣]))")
_YEAR_TAIL = re.compile(r"\s*[(（]\s*(?:19|20)\d{2}[^)）]*[)）]\s*$")
_NOT_WORD = re.compile(r"[\W_]+")
_CONTAIN_MIN = 8          # 제목 일부만 낸 출력 — 짧은 쪽이 이 글자 수 이상일 때만 품는 관계로 본다


def _evidence_list(papers: list[dict]) -> str:
    return "\n".join(
        f"[{p['eid']}] {p.get('title') or ''} ({p.get('year') or '연도 미상'})" for p in papers
    ) or "(없음)"


def _build(input: dict) -> tuple[list[dict], dict]:
    seed = input.get("seed") or {}
    system, user, params = get_prompt(PROMPT).render(
        question=input.get("question") or "",
        heading=seed.get("heading") or "",
        seed=seed.get("text") or "",
        evidence_list=_evidence_list(input.get("papers") or []),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


def _parse(raw: str) -> dict | None:
    """원문 → {"title", "question", "evidence": [str]}(원문 문자열 그대로). JSON 이 아니면 None."""
    data = extract_json(raw)
    if data is None:
        return None
    evidence = data.get("evidence")
    if isinstance(evidence, str):
        evidence = [evidence]
    elif not isinstance(evidence, list):
        evidence = []
    return {
        "title": data["title"] if isinstance(data.get("title"), str) else "",
        "question": data["question"] if isinstance(data.get("question"), str) else "",
        "evidence": [e for e in evidence if isinstance(e, str)],
    }


def _title_key(text: str) -> str:
    """제목 비교 키 — 끝의 '(2013)' 같은 연도 괄호를 떼고 공백·문장부호를 빼고 casefold."""
    return _NOT_WORD.sub("", _YEAR_TAIL.sub("", text)).casefold()


def _by_title(text: str, papers: list[dict]) -> str | None:
    key = _title_key(text)
    if not key:
        return None
    for p in papers:
        if _title_key(p.get("title") or "") == key:
            return p["eid"]
    near = []
    for p in papers:
        title = _title_key(p.get("title") or "")
        if title and min(len(title), len(key)) >= _CONTAIN_MIN and (key in title or title in key):
            near.append(p["eid"])
    return near[0] if len(near) == 1 else None          # 둘 이상이 걸리면 어느 논문인지 모른다 — 버린다


def evidence_ids(raw: list[str], papers: list[dict]) -> tuple[list[str], int]:
    """모델이 낸 근거 표기 → 입력의 근거 번호(등장 순, 중복 없이)와 제목에서 되돌린 수(정함 5).
    표기가 번호(E#)면 그 번호로, 아니면 제목 비교로 찾는다. 목록에 없는 번호·찾지 못한 제목은 버린다."""
    valid = {p["eid"] for p in papers}
    out: list[str] = []
    recovered = 0
    for item in raw:
        if not isinstance(item, str):
            continue
        m = _EID.match(item)
        if m:
            eid = f"E{int(m.group(1) or m.group(2))}"
            if eid in valid and eid not in out:
                out.append(eid)
            continue
        eid = _by_title(item, papers)
        if eid is not None and eid not in out:
            out.append(eid)
            recovered += 1
    return out, recovered


def card_figures(adopted, latest_year, corpus) -> list[dict]:
    """카드의 수치 — 그 하위질문의 채택 편수·고른 근거 중 최신 연도·적재분 N(spec §5-2). 모르는 값은 뺀다."""
    values: list[tuple[str, str]] = []
    if isinstance(adopted, int) and not isinstance(adopted, bool) and adopted >= 0:
        values.append((FIG_ADOPTED, str(adopted)))
    if isinstance(latest_year, int) and not isinstance(latest_year, bool):
        values.append((FIG_LATEST, str(latest_year)))
    n_papers = (corpus or {}).get("n_papers")
    if isinstance(n_papers, int) and not isinstance(n_papers, bool):
        values.append((FIG_CORPUS, f"{n_papers:,}"))
    return [figure(f"F{n}", label, value) for n, (label, value) in enumerate(values, start=1)]


def figure_sentence(figures: list[dict]) -> str | None:
    """수치 문장 고정 틀 — 수치마다 한 문장, [F#] 자리에 값이 들어간다. 수치가 없으면 None."""
    parts = [_SENTENCES[f["label"]].format(id=f["id"]) for f in figures if f.get("label") in _SENTENCES]
    return " ".join(parts) or None


def _clean(value: str) -> str:
    return " ".join(strip_markers(value or "").split())


def _bind(output: dict, input: dict) -> dict:
    """해석한 출력 → {"card": Card | None}(계약 §4 Card). 제목이나 질문이 비면 card 는 None."""
    title, question = _clean(output.get("title")), _clean(output.get("question"))
    if not title or not question:
        return {"card": None}
    papers = list(input.get("papers") or [])
    eids, recovered = evidence_ids(output.get("evidence") or [], papers)
    by_eid = {p["eid"]: p for p in papers}
    chosen = [by_eid[e] for e in eids]
    years = [p["year"] for p in chosen if isinstance(p.get("year"), int)]
    latest_year = max(years) if years else None
    title, soft_title = soften_claims(title)
    question, soft_question = soften_claims(question)
    title, question = title[:TOPIC_TITLE_MAX], question[:TOPIC_QUESTION_MAX]
    figures = card_figures(input.get("adopted"), latest_year, input.get("corpus"))
    return {"card": {
        "title": title,
        "question": question,
        "evidence": [p["cnts_id"] for p in chosen],
        "figure_sentence": figure_sentence(figures),
        "figures": figures,
        "latest_year": latest_year,
        "edited": False,
        "checks": {"numbers": numbers_outside(f"{title}\n{question}"),
                   "softened": soft_title + soft_question, "recovered": recovered},
        "gen_id": None,
    }}


def _check(output: dict) -> bool:
    card = output.get("card")
    return card is not None and len(card["evidence"]) >= MIN_TOPIC_EVIDENCE


async def apply(db, gen, output: dict) -> dict:
    """카드를 research_topics 의 그 행(input.topic_id)에 반영한다. 커밋하지 않는다(apply_result 와 같은 규칙).

    카드가 있으면 state 는 candidate(이미 고른 주제면 picked 그대로), 없으면 card 를 비우고 insufficient.
    그 사이 사용자가 직접 고친 카드(card.edited)는 덮지 않는다 — 다시 부르기(빈 카드의 retry)가 사용자의 글을
    지우면 안 된다."""
    topic_id = int(gen.input["topic_id"])
    row = (await db.execute(
        select(ResearchTopic.card, ResearchTopic.state)
        .where(ResearchTopic.id == topic_id, ResearchTopic.work_id == gen.work_id)
    )).first()
    if row is None:                    # 연구가 지워졌다(CASCADE) — finish 도 행을 찾지 못해 되돌린다
        return {"topic_id": topic_id, "state": None}
    if (row.card or {}).get("edited"):
        return {"topic_id": topic_id, "state": row.state}
    card = output.get("card")
    if card:
        values = {"card": {**card, "edited": False, "gen_id": gen.id},
                  "state": "picked" if row.state == "picked" else "candidate"}
    else:
        values = {"card": {}, "state": "insufficient"}
    await db.execute(update(ResearchTopic).where(ResearchTopic.id == topic_id).values(**values))
    await refresh_progress(db, gen.work_id)
    return {"topic_id": topic_id, "state": values["state"]}


EXECUTOR = Executor(
    kind="topic_card",
    build=_build,
    parse=_parse,
    check=_check,
    empty=lambda input: {"card": None},
    bind=_bind,
    apply=apply,
    is_empty=lambda out: (out or {}).get("card") is None,
)
