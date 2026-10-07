"""progress.py — 연구의 진행 요약 research_works.progress (06b 계획 정함 14·16)

{"topics": 카드가 있는 후보 수, "reading": 담음 수, "sections": 채운 절 수, "sections_total": 6}.
06d 사이드바('후보 4'·'읽기 목록 12편'·'계획서 3/6절')의 재료다. 카드 반영·고르기·읽기 목록·목차·절을
쓸 때마다 refresh_progress 가 DB 에서 다시 세어 저장한다(더하고 빼며 고쳐 쓰지 않는다). 세기 전에 연구 행을
FOR UPDATE 로 잠근다 — 잠금을 마지막 UPDATE 에서야 잡으면, 같은 연구의 쓰기 둘이 겹칠 때 뒤에 커밋하는 쪽이
앞 커밋 전에 센 낡은 값을 쓴다(READ COMMITTED). 잠금을 얻은 뒤의 SELECT 는 새 스냅샷이라 앞서 커밋한 쓰기를
보므로 마지막에 커밋한 값이 사실이다. 부르는 쪽은 자기 행을 바꾼 뒤에 부르므로 잠금 순서는 늘 자기 행 →
연구 행이다(마지막 UPDATE 가 잡던 것과 같은 순서). 커밋은 부르는 쪽이 한다(워커의 결과 반영은 finish 가,
API 는 핸들러가).
세션에서는 execute·scalar 만 쓴다(tests/history_sqlite 대역이 흉내 내는 것).
"""
from sqlalchemy import func, select, update

from models.research_work import ResearchProposal, ResearchReading, ResearchTopic, ResearchWork
from services.research_work.shapes import PROPOSAL_SECTIONS

LIVE_TOPIC_STATES = ("candidate", "picked")     # 접은(folded)·근거 부족(insufficient) 카드는 세지 않는다


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _written(section) -> bool:
    """글이 있는 문단이 하나라도 있는 절."""
    paragraphs = section.get("paragraphs") if isinstance(section, dict) else None
    return any(isinstance(p, dict) and _text(p.get("text")) for p in paragraphs or [])


def sections_filled(outline: dict, sections: dict) -> int:
    """고정 6절 가운데 내용이 채워진 절 수(정함 16).

    주제 = 목차의 주제 제목, 연구 질문·방법 제안 = 목차에서 고른·적은 값, 연구 배경·연구 공백 = 글이 있는
    문단이 있는 절. 선행연구 검토는 목차의 묶음이 하나 이상이고 모든 묶음 절(prior.gN)이 써졌을 때 1절이다.
    """
    outline = outline if isinstance(outline, dict) else {}
    sections = sections if isinstance(sections, dict) else {}
    topic = outline.get("topic") if isinstance(outline.get("topic"), dict) else {}
    keys = [g.get("key") for g in outline.get("groups") or [] if isinstance(g, dict)]
    filled = {
        "topic": _text(topic.get("title")),
        "background": _written(sections.get("background")),
        "prior": bool(keys) and all(_written(sections.get(key)) for key in keys),
        "gap": _written(sections.get("gap")),
        "question": _text(outline.get("question")),
        "method": _text(outline.get("method")),
    }
    return sum(1 for key in PROPOSAL_SECTIONS if filled[key])


async def refresh_progress(db, work_id) -> dict:
    """이 연구의 진행 요약을 세어 research_works.progress 에 쓰고 그 dict 를 돌려준다. 커밋하지 않는다.
    연구 행을 먼저 잠그고 센다(머리 주석 — 겹친 쓰기에서 낡은 셈을 쓰지 않게). 잠금은 커밋·롤백까지 쥔다."""
    T, R, P = ResearchTopic, ResearchReading, ResearchProposal
    await db.execute(select(ResearchWork.id).where(ResearchWork.id == work_id).with_for_update())
    topics = (await db.execute(select(T.state, T.card).where(T.work_id == work_id))).all()
    reading = await db.scalar(
        select(func.count()).select_from(R).where(R.work_id == work_id, R.state == "in")
    )
    proposal = (await db.execute(
        select(P.outline, P.sections).where(P.work_id == work_id)
    )).first()
    progress = {
        "topics": sum(1 for state, card in topics if state in LIVE_TOPIC_STATES and card),
        "reading": int(reading or 0),
        "sections": sections_filled(proposal.outline, proposal.sections) if proposal is not None else 0,
        "sections_total": len(PROPOSAL_SECTIONS),
    }
    await db.execute(update(ResearchWork).where(ResearchWork.id == work_id).values(progress=progress))
    return progress
