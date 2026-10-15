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
06e 부터 반영이 목차를 자동 확정한다(D20 — [보고서 만들기] 한 번): 연구 질문 = 고른 카드의 질문, 없으면 첫 후보
(auto_question), 방법 빈칸, state approved·approved_at 지금·auto true — 화면의 절 연쇄가 auto 를 읽는다. 질문이 하나도
없으면 06b 처럼 초안(auto false)으로 둔다 — 빈 질문으로 승인하면 [목차 고치기]의 PUT 이 422 가 된다.
카드 질문이 먼저인 까닭: 프롬프트가 후보끼리 '서로 다른 각도'로 묻게 해서 첫 후보가 카드와 다른 질문일 수 있다 — 운영
d60a5dc1 은 5절 연구 질문과 절 본문(basis.question)이 고른 카드가 아닌 첫 후보를 따라갔다. 저장하는 후보 목록(questions)도
카드 질문 → LLM 후보 순(question_choices)이라 [목차 고치기]에서 카드 질문 칸이 체크된 채 보이고 LLM 후보는 선택지로 남는다.
"""
import re
from datetime import datetime, timezone

from sqlalchemy import select, update

from models.research_work import ResearchProposal
from services.prompts import get_prompt
from services.research.citations import strip_markers
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


def _tidy(raw: str) -> str:
    """[E#] 마커를 걷고 공백을 정리한다. 이름·질문은 bind_markers 검증을 거치지 않는데, user 메시지가 논문을
    [E1] 제목 꼴로 줘서 모델이 시키지 않은 [E#] 를 단다(함정 15). 남기면 목차 화면에 나가고, 절 프롬프트는
    [E#] 를 절마다 새로 매겨 그 번호가 다른 논문을 가리킨다."""
    return " ".join(strip_markers(raw).split())


def _clean_name(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    text = _tidy(raw)
    return text if 1 <= len(text) <= GROUP_LABEL_MAX else None


def clean_questions(raw) -> list[str]:
    """연구 질문 후보 — 문자열만, [E#] 마커 제거·공백 정리, 물음표로 끝나는 것만(전각 ？ 는 ? 로), 2~300자,
    대소문자·공백 무시 중복 제거, 앞에서 3개. 물음표가 없는 평서문은 질문이 아니라 버린다."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        text = _tidy(item).replace("？", "?")
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


def _now() -> str:
    """자동 승인 시각(UTC ISO) — PUT .../outline 의 approved_at 과 같은 모양. 테스트가 바꿔 끼운다."""
    return datetime.now(timezone.utc).isoformat()


def _usable(raw) -> str | None:
    """공백을 정리한 질문, 2자 미만(공백만 포함)이면 None — PUT .../outline 의 승인 하한과 같아야 자동 승인한 목차를
    [목차 고치기]로 다시 승인할 수 있다."""
    text = " ".join(raw.split()) if isinstance(raw, str) else ""
    return text if len(text) >= 2 else None


def question_choices(output: dict, input: dict) -> list[str]:
    """목차에 저장하는 연구 질문 후보 — 고른 카드의 질문(input.topic.question) → LLM 후보(output.questions) 순, 공백을
    정리하고 _key(공백·대소문자 무시)로 중복 없이. 빈 결과(fallback)는 _empty 가 이미 카드 질문을 후보로 채웠다 — 한 번만 남는다."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in [(input.get("topic") or {}).get("question"), *(output.get("questions") or [])]:
        text = _usable(raw)
        if text is None or _key(text) in seen:
            continue
        seen.add(_key(text))
        out.append(text)
    return out


def auto_question(output: dict, input: dict) -> str | None:
    """자동 확정의 연구 질문 — 고른 카드의 질문(input.topic.question), 없으면 첫 후보(output.questions[0]), 둘 다 비면
    None. question_choices 의 첫째라 저장한 question 이 늘 questions[0] 이다(화면 [목차 고치기]가 그 칸을 체크한다).
    공백을 정리하고 2자 미만(공백만 포함)은 없는 것으로 본다(_usable)."""
    choices = question_choices(output, input)
    return choices[0] if choices else None


async def apply(db, gen, output: dict) -> dict:
    """research_proposals.outline ← Outline · version + 1 · 진행 요약. 커밋하지 않는다.
    연구 질문이 있으면 자동 승인한다(state approved·approved_at·auto true — 06e D20), 없으면 06b 처럼 초안(auto false).
    승인한 목차가 있어도 통째로 바꾼다([보고서 다시 만들기] — 새 반영이라 auto 가 다시 붙는다). 연구 배경(background —
    사용자가 쓰는 자유 글)만 옛 목차에서 이어 받는다.
    concepts 는 목차를 만들 때의 핵심 개념 — 뒤에 개념을 고치면 조회가 목차에 '다시 맞춤 필요' 를 붙인다.
    반환은 generation 이벤트의 result({fallback, auto})."""
    input = dict(gen.input or {})
    names = output.get("group_names") or {}
    question = auto_question(output, input)
    auto = question is not None
    outline = {
        "topic": input.get("topic"),
        "basis": input.get("basis"),
        "concepts": list(input.get("concepts") or []),
        "groups": [
            {"key": g["key"], "name": names.get(g["key"]) or _fallback_name(g.get("hint")),
             "hint": g.get("hint") or "", "papers": [p["cnts_id"] for p in g["papers"]]}
            for g in input.get("groups") or []
        ],
        "questions": question_choices(output, input),
        "question": question,
        "method": "",
        "state": "approved" if auto else "draft",
        "gen_id": gen.id,
        "approved_at": _now() if auto else None,
        "auto": auto,
    }
    # 연구 배경은 사용자가 쓰는 자유 글이다(06e) — 새 반영이 목차를 통째로 바꿔도 지우지 않는다. 적은 적이 없으면 키를
    # 두지 않는다(키가 없으면 "" 로 읽는다)
    old = await db.scalar(select(ResearchProposal.outline).where(ResearchProposal.work_id == gen.work_id))
    if (old or {}).get("background"):
        outline["background"] = old["background"]
    await db.execute(
        update(ResearchProposal)
        .where(ResearchProposal.work_id == gen.work_id)
        .values(outline=outline, version=ResearchProposal.version + 1)
    )
    await refresh_progress(db, gen.work_id)
    return {"fallback": bool(output.get("fallback")), "auto": auto}


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
