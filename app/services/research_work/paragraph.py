"""paragraph.py — 문단 하나 다시 쓰기(kind=paragraph, gemma, 비스트리밍) — spec §5-5 문단 [다시], 계약 §3.

같은 절 입력(그 절을 쓴 section 생성의 input — 같은 [E#] 번호·같은 수치)으로 그 문단만 다시 쓴다(정함 9).
앞뒤 문단을 함께 보여 이어지게 한다. 결과 검사는 절과 같다(section.make_paragraph → markers.check_paragraph).
반영은 그 문단이 아직 있고 AI 상태(proposed·accepted)이고 글이 입력 때(current)와 같을 때만 한다. 그 사이
사용자가 고쳤거나 지웠거나, 절을 다시 써서 번호 지도(evidence)나 그 문단의 글이 바뀌었으면 그대로 두고 missing
으로 알린다 — 옛 번호로 쓴 글이 다른 논문을 가리키거나, 옛 문단을 보고 쓴 글이 새 문단을 덮지 않게.
입력을 옮긴 답은 검사에서 떨어뜨려 다시 부른다 — 운영(2026-10-08)에서 gemma 가 고칠 문단을 그대로 내거나
'앞 문단: …' 블록을 이름표째 옮겨, [다시]가 글을 바꾸지 않거나 앞 문단을 그 자리에 복사했다.
"""
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy import select, update

from models.research_work import ResearchProposal
from services.prompts import get_prompt
from services.research_work.generate import Executor
from services.research_work.section import evidence_map, make_paragraph, split_paragraphs
from services.research_work.section_input import evidence_block, figure_block

PROMPT = "research_paragraph"
_REPLACEABLE = ("proposed", "accepted")
# 입력 블록의 이름표('앞 문단:'·'고칠 문단(참고 …):')로 시작하는 문단은 입력을 옮긴 것이다 — 건너뛴다
_ECHO_LABEL = re.compile(r"^(?:앞|뒤|고칠)\s*문단\s*(?:\([^)]*\))?\s*[:：]")
# 모델이 제 답에 붙인 이름표 — 떼고 쓴다
_OWN_LABEL = re.compile(r"^(?:다시\s*쓴|새)\s*문단\s*(?:\([^)]*\))?\s*[:：]\s*")
_MARKS_AND_SPACE = re.compile(r"\[[EF]\d+\]|\s+")
# 인용 표기·공백을 뺀 글이 이만큼 같으면 옮긴 글이다
COPY_RATIO = 0.9


def paragraph_input(section_input: dict, paragraphs: list[dict], pid: str) -> dict:
    """그 절 생성의 input + 다시 쓸 문단과 앞뒤 문단의 글(계약 §3 paragraph). 문단이 없으면 ValueError."""
    ids = [p.get("id") for p in paragraphs]
    if pid not in ids:
        raise ValueError(f"문단이 없습니다: {pid}")
    i = ids.index(pid)
    return {
        **section_input, "pid": pid,
        "before": paragraphs[i - 1]["text"] if i > 0 else None,
        "current": paragraphs[i]["text"],
        "after": paragraphs[i + 1]["text"] if i + 1 < len(paragraphs) else None,
    }


def _section_label(input: dict) -> str:
    if input.get("kind") == "prior":
        return f"선행연구 검토 — {(input.get('group') or {}).get('name') or ''}"
    return "연구 공백"


def _build(input: dict) -> tuple[list[dict], dict]:
    system, user, params = get_prompt(PROMPT).render(
        question=input["question"],
        topic_title=(input.get("topic") or {}).get("title") or "",
        research_question=input.get("research_question") or "",
        section_label=_section_label(input),
        evidence_block=evidence_block(input.get("papers") or []),
        figure_list=figure_block(input.get("figures") or []),
        before=input.get("before") or "(없음)",
        current=input["current"],
        after=input.get("after") or "(없음)",
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


def _parse(raw: str) -> dict | None:
    # 한 문단만 쓰라고 했다 — 머리줄과 입력을 이름표째 옮긴 문단을 버린 뒤 첫 문단을 쓴다. 옮긴 블록이 앞에
    # 여럿 와도 제 문단이 잘리지 않게 절의 문단 수 상한은 두지 않는다
    for text in split_paragraphs(raw, limit=None):
        if _ECHO_LABEL.match(text):
            continue
        text = _OWN_LABEL.sub("", text).strip()
        if text:
            return {"text": text}
    return None


def _plain(text: str | None) -> str:
    return _MARKS_AND_SPACE.sub("", text or "")


def copied(text: str, input: dict) -> bool:
    """고칠 문단이나 앞·뒤 문단을 거의 그대로 옮긴 글인가 — 인용 표기·공백을 빼고 견준다."""
    mine = _plain(text)
    return any(
        SequenceMatcher(None, mine, _plain(other)).ratio() >= COPY_RATIO
        for other in (input.get("current"), input.get("before"), input.get("after")) if other
    )


def _bind(output: dict, input: dict) -> dict:
    # 옮긴 글은 빈 문단으로 묶어 검사에서 떨어뜨린다 — 다시 부르고, 끝내 못 얻으면 문단을 그대로 둔다(빈 결과)
    if copied(output["text"], input):
        return {"paragraph": None}
    return {"paragraph": make_paragraph(output["text"], input, input["pid"])}


async def apply(db, gen, output: dict) -> dict:
    """그 문단이 아직 있고 AI 상태이고 글이 input 의 current 와 같고 절의 번호 지도가 input 과 같으면 새 문단으로
    바꾸고 version + 1. 아니면(고침·지움·절을 다시 써서 지도나 글이 바뀜) 그대로 두고 missing.
    빈 결과(세 번 다 못 얻음)는 문단을 건드리지 않는다. 행은 FOR UPDATE 로 읽는다(section.apply 와 같은 까닭)."""
    inp = gen.input
    key, pid = inp["key"], inp["pid"]
    result = {"key": key, "pid": pid, "missing": False}
    new = output.get("paragraph")
    if new is None:
        return result
    P = ResearchProposal
    row = (await db.execute(
        select(P.sections).where(P.work_id == gen.work_id).with_for_update()
    )).first()
    section = ((row.sections if row is not None else None) or {}).get(key)
    if section is None or section.get("evidence") != evidence_map(inp):
        return {**result, "missing": True}
    paragraphs = list(section.get("paragraphs") or [])
    at = next((i for i, p in enumerate(paragraphs) if p.get("id") == pid), None)
    # 글이 input 의 current 와 다르면 그 사이 절을 다시 쓴 것이다 — 같은 묶음이면 번호 지도는 같아도 같은 id 가
    # 다른 문단이다(옛 생성을 다시 시도했거나, 엔드포인트가 읽은 뒤 절 결과가 커밋됨). 생성이 열린 동안은
    # PUT·절 쓰기·같은 절 문단 다시 쓰기가 모두 409 라 정상 흐름에서는 글이 바뀌지 않는다
    if (at is None or paragraphs[at].get("state") not in _REPLACEABLE
            or paragraphs[at].get("text") != inp.get("current")):
        return {**result, "missing": True}
    paragraphs[at] = {**new, "id": pid, "gen_id": gen.id}
    updated = {**section, "paragraphs": paragraphs, "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.execute(
        update(P).where(P.work_id == gen.work_id)
        .values(sections={**row.sections, key: updated}, version=P.version + 1)
    )
    return result


EXECUTOR = Executor(
    kind="paragraph",
    build=_build,
    parse=_parse,
    check=lambda output: output["paragraph"] is not None and bool(output["paragraph"]["cites"]),
    empty=lambda input: {"paragraph": None},
    bind=_bind,
    apply=apply,
    is_empty=lambda output: (output or {}).get("paragraph") is None,
)
