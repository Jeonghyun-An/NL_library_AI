"""paragraph.py — 문단 하나 다시 쓰기(kind=paragraph, gemma, 비스트리밍) — spec §5-5 문단 [다시], 계약 §3.

같은 절 입력(그 절을 쓴 section 생성의 input — 같은 [E#] 번호·같은 수치)으로 그 문단만 다시 쓴다(정함 9).
앞뒤 문단을 함께 보여 이어지게 한다. 결과 검사는 절과 같다(section.make_paragraph → markers.check_paragraph).
반영은 그 문단이 아직 있고 AI 상태(proposed·accepted)일 때만 한다. 그 사이 사용자가 고쳤거나 지웠거나, 절을
다시 써서 번호 지도(evidence)가 바뀌었으면 그대로 두고 missing 으로 알린다 — 옛 번호로 쓴 글이 다른 논문을
가리키지 않게.
"""
from datetime import datetime, timezone

from sqlalchemy import select, update

from models.research_work import ResearchProposal
from services.prompts import get_prompt
from services.research_work.generate import Executor
from services.research_work.section import evidence_map, make_paragraph, split_paragraphs
from services.research_work.section_input import evidence_block, figure_block

PROMPT = "research_paragraph"
_REPLACEABLE = ("proposed", "accepted")


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
    # 한 문단만 쓰라고 했다 — 머리줄을 버린 뒤 첫 문단을 쓴다
    paragraphs = split_paragraphs(raw)
    return {"text": paragraphs[0]} if paragraphs else None


def _bind(output: dict, input: dict) -> dict:
    return {"paragraph": make_paragraph(output["text"], input, input["pid"])}


async def apply(db, gen, output: dict) -> dict:
    """그 문단이 아직 있고 AI 상태면 새 문단으로 바꾸고 version + 1. 아니면 그대로 두고 missing.
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
    if at is None or paragraphs[at].get("state") not in _REPLACEABLE:
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
