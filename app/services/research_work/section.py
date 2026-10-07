"""section.py — 절 생성(kind=section, gemma, 스트리밍) — spec §5-5, 계약 §3.

선행연구 검토의 묶음 하나(prior.g1~g4)나 연구 공백(gap)을 쓴다. 출력은 조각마다 화면에 그대로 흐르므로
(section_delta) JSON 이 아니라 빈 줄로 나눈 평문 문단이다. 문단 수 상한·인용 번호·수치 표기는 코드가 정하고
검사한다(함정 15 — 프롬프트에 예시가 없다): 문단마다 markers.check_paragraph 가 틀린 [E#]·[F#] 를 지우고
[F#] 밖 숫자와 단정 표현을 센다(정함 3). 인용은 절 범위 [E#] 를 그대로 두고 evidence 지도(E# → cnts_id)를
함께 저장한다(정함 9). 사용자가 고친 글(PUT)과 문단 다시 쓰기(paragraph.py)도 같은 검사를 쓴다.
"""
import re
from datetime import datetime, timezone

from sqlalchemy import select, update

from models.research_work import ResearchProposal
from services.prompts import get_prompt
from services.research_work.generate import Executor
from services.research_work.markers import check_paragraph
from services.research_work.progress import refresh_progress
from services.research_work.section_input import evidence_block, figure_block
from services.research_work.shapes import GAP_NOTE, MAX_SECTION_PARAGRAPHS

PROMPTS = {"prior": "research_section_prior", "gap": "research_section_gap"}
_BLANK_LINE = re.compile(r"\n[ \t]*\n")


def split_paragraphs(raw: str) -> list[str]:
    """빈 줄로 나눈 문단, 앞에서 MAX_SECTION_PARAGRAPHS 개. 문단 안 줄바꿈은 공백 하나로 잇는다.
    한 줄짜리 머리줄('#' 로 시작하거나 ':' 로 끝나는 줄 — 모델이 붙인 제목·안내)은 버린다."""
    out: list[str] = []
    for block in _BLANK_LINE.split((raw or "").replace("\r\n", "\n")):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if len(lines) == 1 and (lines[0].startswith("#") or lines[0].endswith((":", "："))):
            continue
        out.append(" ".join(lines))
    return out[:MAX_SECTION_PARAGRAPHS]


def evidence_map(input: dict) -> dict[str, str]:
    """절 입력의 근거 번호 → cnts_id(정함 9). 저장하는 Section.evidence 와 검사의 유효 번호가 이것이다."""
    return {p["eid"]: p["cnts_id"] for p in input.get("papers") or []}


def make_paragraph(text: str, input: dict, pid: str) -> dict | None:
    """모델이 쓴 문단 하나를 그 절 입력의 번호·수치로 검사한 Paragraph(state proposed). 검사 뒤 글이 비면 None."""
    evidence = evidence_map(input)
    fixed, cites, checks = check_paragraph(
        text, valid_e=set(evidence), valid_f={f["id"] for f in input.get("figures") or []}, evidence=evidence,
    )
    if not fixed.strip():
        return None
    return {"id": pid, "text": fixed, "state": "proposed", "cites": cites, "checks": checks, "gen_id": None}


def _seed_block(seeds: list[dict]) -> str:
    return "\n".join(f"- {s['text']} (하위질문: {s['heading']})" for s in seeds) or "(없음)"


def _build(input: dict) -> tuple[list[dict], dict]:
    common = {
        "question": input["question"],
        "topic_title": (input.get("topic") or {}).get("title") or "",
        "research_question": input.get("research_question") or "",
        "evidence_block": evidence_block(input.get("papers") or []),
        "figure_list": figure_block(input.get("figures") or []),
    }
    if input["kind"] == "prior":
        extra = {"group_name": (input.get("group") or {}).get("name") or ""}
    else:
        extra = {"seed_block": _seed_block(input.get("seeds") or [])}
    system, user, params = get_prompt(PROMPTS[input["kind"]]).render(**common, **extra)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], params


def _parse(raw: str) -> dict | None:
    paragraphs = split_paragraphs(raw)
    return {"paragraphs": paragraphs} if paragraphs else None


def _bind(output: dict, input: dict) -> dict:
    paragraphs: list[dict] = []
    dropped = 0
    for text in output["paragraphs"]:
        paragraph = make_paragraph(text, input, f"p{len(paragraphs) + 1}")
        if paragraph is None:
            continue
        dropped += paragraph["checks"]["dropped"]
        paragraphs.append(paragraph)
    return {"paragraphs": paragraphs, "dropped": dropped}


def _check(output: dict) -> bool:
    # 문단이 하나 이상이고 유효한 인용이 하나 이상 — 근거 없이 쓴 절은 다시 부른다
    return bool(output["paragraphs"]) and any(p["cites"] for p in output["paragraphs"])


async def apply(db, gen, output: dict) -> dict:
    """research_proposals.sections[절 키] 를 Section 모양으로 통째로 쓰고 version + 1·진행 요약을 다시 센다.

    빈 결과(세 번 다 못 얻음)면 절을 건드리지 않는다 — 앞서 쓴·수락한 문단을 아무 결과 없이 지우지 않게.
    행을 FOR UPDATE 로 읽는다 — 같은 계획서의 다른 절 PUT 과 겹쳐도 한쪽 쓰기를 덮지 않게(PUT 은 If-Match 로
    version 을 맞춰 보므로 이 쓰기 뒤에는 409 다). 커밋하지 않는다(디스패처의 finish 가 커밋한다).
    """
    key = gen.target
    paragraphs = [{**p, "gen_id": gen.id} for p in output.get("paragraphs") or []]
    result = {"key": key, "paragraphs": len(paragraphs), "dropped": int(output.get("dropped") or 0)}
    if not paragraphs:
        return result
    P = ResearchProposal
    row = (await db.execute(
        select(P.sections).where(P.work_id == gen.work_id).with_for_update()
    )).first()
    if row is None:
        return result
    inp = gen.input
    section = {
        "key": key, "gen_id": gen.id,
        "evidence": evidence_map(inp),
        "figures": list(inp.get("figures") or []),
        "basis": dict(inp.get("basis") or {"topic_id": None, "papers": []}),
        "note": GAP_NOTE if inp.get("kind") == "gap" else None,
        "paragraphs": paragraphs,
        "model": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.execute(
        update(P).where(P.work_id == gen.work_id)
        .values(sections={**(row.sections or {}), key: section}, version=P.version + 1)
    )
    await refresh_progress(db, gen.work_id)
    return result


EXECUTOR = Executor(
    kind="section",
    build=_build,
    parse=_parse,
    check=_check,
    empty=lambda input: {"paragraphs": [], "dropped": 0},
    bind=_bind,
    stream=True,
    apply=apply,
    is_empty=lambda output: not (output or {}).get("paragraphs"),
)
