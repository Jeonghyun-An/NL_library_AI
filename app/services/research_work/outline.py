"""outline.py — 목차 만들기(kind=outline, gemma) — spec §5-5, 06b 정함 7

입력(outline_input)은 FastAPI 의 POST .../outline 이 만든다 — 묶음 수·배정은 서버 코드(membership)가 이미
정했고(개념 소속, 개념이 비면 하위질문 소속), LLM 은 묶음 이름과 연구 질문 후보만 쓴다. 06b 는 방법 선택지가
없다(특징이 06c 라 사용자 입력 칸 — 정함 16).
프롬프트는 JSON 키를 말로만 설명하고(실제 묶음 키는 group_keys 변수로 준다) 원소가 든 배열 견본·예시를 두지
않는다(함정 15). 질문 개수·모양(물음표·중복·글자 상한)과 묶음 이름은 코드가 정리하고 검사한다.
끝내 못 얻으면 묶음 이름은 배정 키(hint), 연구 질문은 고른 카드의 질문 하나로 done(fallback) — 화면은 그
목차를 그대로 고칠 수 있고, 다시 부르기(retry)도 열린다(is_empty).
반영(apply)은 research_proposals.outline 을 Outline 모양으로 바꾸고 version 을 올린다 — 화면이 들고 있던
옛 version 의 PUT 은 409 가 된다. 행은 POST .../outline 이 미리 만든다. 커밋은 디스패처(finish)가 한다.
"""
import re

from sqlalchemy import update

from models.research_work import ResearchProposal
from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research_work.generate import Executor
from services.research_work.progress import refresh_progress
from services.research_work.shapes import GROUP_LABEL_MAX, OUTLINE_QUESTION_MAX

PROMPT = "research_outline"
MIN_QUESTIONS, MAX_QUESTIONS = 2, 3
FALLBACK_GROUP_NAME = "선행연구"        # 배정 키도 없는 묶음(친밀도가 하나도 없을 때)의 빈 결과 이름
_YEAR = re.compile(r"(19|20)\d{2}")


def _year(pub_date) -> int | None:
    m = _YEAR.search(pub_date or "") if isinstance(pub_date, str) else None
    return int(m.group(0)) if m else None


def outline_input(question: str, topic: dict, concepts: list[str], basis: str, groups: list[dict],
                  metas: dict) -> dict:
    """생성 입력(§3 outline). groups 는 membership.assign_groups 결과, metas 는 {cnts_id: PaperMeta}.
    [E#] 번호는 묶음을 가로질러 차례로 붙인다."""
    n = 0
    out_groups = []
    for g in groups:
        papers = []
        for cnts_id in g["papers"]:
            n += 1
            meta = metas.get(cnts_id) or {}
            papers.append({"eid": f"E{n}", "cnts_id": cnts_id, "title": meta.get("title") or cnts_id,
                           "year": _year(meta.get("pub_date"))})
        out_groups.append({"key": g["key"], "hint": g.get("hint") or "", "papers": papers})
    return {
        "question": question,
        "topic": {"id": topic["id"], "title": topic["title"], "question": topic["question"]},
        "concepts": list(concepts),
        "basis": basis,
        "groups": out_groups,
    }


def _groups_block(input: dict) -> str:
    label = "핵심 개념" if input.get("basis") == "concept" else "하위질문"
    blocks = []
    for g in input["groups"]:
        lines = [f"묶음 {g['key']} — 배정 기준 {label}: {g['hint'] or '(없음)'}"]
        for p in g["papers"]:
            lines.append(f"[{p['eid']}] {p['title']} ({p['year'] or '연도 미상'})")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _build(input: dict) -> tuple[list[dict], dict]:
    system, user, params = get_prompt(PROMPT).render(
        question=input["question"],
        topic_title=input["topic"]["title"],
        topic_question=input["topic"]["question"] or "(없음)",
        groups_block=_groups_block(input),
        group_keys=", ".join(g["key"] for g in input["groups"]),
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


def _key(text: str) -> str:
    return "".join(text.split()).casefold()


def _clean_name(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    text = " ".join(raw.split())
    return text if 1 <= len(text) <= GROUP_LABEL_MAX else None


def clean_questions(raw) -> list[str]:
    """연구 질문 후보 — 문자열만, 공백 정리, 물음표로 끝나는 것만(전각 ？ 는 ? 로), 2~300자, 대소문자·공백
    무시 중복 제거, 앞에서 3개. 물음표가 없는 평서문은 질문이 아니라 버린다."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split()).replace("？", "?")
        if not text.endswith("?") or not 2 <= len(text) <= OUTLINE_QUESTION_MAX:
            continue
        if _key(text) in seen:
            continue
        seen.add(_key(text))
        out.append(text)
        if len(out) == MAX_QUESTIONS:
            break
    return out


def _parse(raw: str) -> dict | None:
    data = extract_json(raw)
    if data is None:
        return None
    names, questions = data.get("group_names"), data.get("research_questions")
    if not isinstance(names, dict) or not isinstance(questions, list):
        return None
    cleaned = {str(k).strip(): _clean_name(v) for k, v in names.items()}
    return {"group_names": {k: v for k, v in cleaned.items() if v},
            "questions": clean_questions(questions), "fallback": False}


def _bind(output: dict, input: dict) -> dict:
    """입력의 묶음 키만 남긴다(모델이 지어낸 키는 버리고, 빠뜨린 키는 None — 검사에서 떨어진다)."""
    names = output.get("group_names") or {}
    return {"group_names": {g["key"]: names.get(g["key"]) for g in input["groups"]},
            "questions": list(output.get("questions") or []), "fallback": False}


def _check(output: dict) -> bool:
    names = list((output.get("group_names") or {}).values())
    if not names or not all(names):
        return False
    if len({_key(n) for n in names}) != len(names):
        return False                    # 묶음 이름이 겹치면 다시 묻는다
    return len(output.get("questions") or []) >= MIN_QUESTIONS


def _fallback_name(hint) -> str:
    """빈 결과의 묶음 이름 — 배정 키(개념·하위질문 글)를 이름 상한에서 자른 것, 키도 없으면 '선행연구'.
    하위질문 글은 이름 상한보다 길 수 있다 — 그대로 두면 사용자가 목차를 저장할 때 422 다."""
    text = " ".join((hint or "").split())[:GROUP_LABEL_MAX].strip()
    return text or FALLBACK_GROUP_NAME


def _empty(input: dict) -> dict:
    question = (input.get("topic") or {}).get("question") or ""
    return {"group_names": {g["key"]: _fallback_name(g.get("hint")) for g in input["groups"]},
            "questions": [question] if question else [], "fallback": True}


async def apply(db, gen, output: dict) -> dict:
    """research_proposals.outline ← Outline(state draft) · version + 1 · 진행 요약. 커밋하지 않는다.
    concepts 는 목차를 만들 때의 핵심 개념 — 뒤에 개념을 고치면 조회가 목차에 '다시 맞춤 필요' 를 붙인다."""
    input = dict(gen.input or {})
    names = output.get("group_names") or {}
    outline = {
        "topic": input.get("topic"),
        "basis": input.get("basis"),
        "concepts": list(input.get("concepts") or []),
        "groups": [
            {"key": g["key"], "name": names.get(g["key"]) or _fallback_name(g.get("hint")),
             "hint": g.get("hint") or "", "papers": [p["cnts_id"] for p in g["papers"]]}
            for g in input.get("groups") or []
        ],
        "questions": list(output.get("questions") or []),
        "question": None,
        "method": "",
        "state": "draft",
        "gen_id": gen.id,
        "approved_at": None,
    }
    await db.execute(
        update(ResearchProposal)
        .where(ResearchProposal.work_id == gen.work_id)
        .values(outline=outline, version=ResearchProposal.version + 1)
    )
    await refresh_progress(db, gen.work_id)
    return {"fallback": bool(output.get("fallback"))}


EXECUTOR = Executor(
    kind="outline",
    build=_build,
    parse=_parse,
    check=_check,
    empty=_empty,
    bind=_bind,
    apply=apply,
    is_empty=lambda output: (output or {}).get("fallback") is True,
)
