"""research_reading.py — 읽기 목록 API(round06b). spec §5-4(06b 기본 — 담음·메모·묶음·순서·들어온 경로·되살리기)·§6-2.

GET 은 읽기 목록 행 전부(후보·담음·뺌)와 들어온 경로·깔때기, 아직 행이 없는 critic 제외 논문(후보 서랍의
'critic 이 뺀 논문')을 돌려준다. 서지는 BookRepository.get_by_cnts_ids 한 번으로 읽는다. 계획서의 목차를 함께 읽어
목차를 만든 뒤 고른 주제가 바뀌었으면 stale(다시 맞춤 필요)을 싣는다(spec §5-2).
PUT 은 본문에 보낸 필드만 바꾼다(빠진 필드는 그대로). 행이 없는 논문은 새로 만든다 — 그 잡의 critic 제외
논문이면 되살림(origin revived, origin_ref 에 뺀 하위질문·회차·note), 아니면 소장 목록(library_catalog)에 있는
논문이어야 담기(origin user — 06d 빠른검색 [담기] 가 쓴다). 보고서는 바꾸지 않는다.
LLM 을 부르지 않는 동기 엔드포인트다. 행을 쓰면 진행 요약(progress)을 다시 세고, 커밋 뒤 work 이벤트를 보낸다.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.research_work import _get_job, _get_work, _job_uuid, _writable
from core.deps import get_db
from models.book import Book
from models.research_work import ResearchProposal, ResearchReading
from repositories.book import BookRepository
from services.research.relay import publish_work
from services.research_work.progress import refresh_progress
from services.research_work.reading_views import (
    book_meta, excluded_candidates, reading_item, reading_view, subquestions_of,
)
from services.research_work.shapes import GROUP_LABEL_MAX, READING_NOTE_MAX

router = APIRouter(tags=["research-work"])

NO_PAPER = "논문이 없습니다"
STATE_REQUIRED = "state 는 비울 수 없습니다"
MAX_POSITION = 1_000_000       # 순서 값 상한 — integer 칼럼을 넘는 값이 500 으로 끝나지 않게


class ReadingPut(BaseModel):
    state: Literal["candidate", "in", "out"] | None = None
    note: str | None = Field(None, max_length=READING_NOTE_MAX)
    group_label: str | None = Field(None, max_length=GROUP_LABEL_MAX)
    position: int | None = Field(None, ge=0, le=MAX_POSITION)


def _text_or_none(value: str | None) -> str | None:
    """메모·묶음 이름 — 앞뒤 공백을 지우고, 비면 지운다(NULL)."""
    if value is None:
        return None
    return value.strip() or None


async def _rows(db: AsyncSession, jid) -> list[ResearchReading]:
    return list((await db.execute(
        select(ResearchReading).where(ResearchReading.work_id == jid)
    )).scalars().all())


async def _new_origin(db: AsyncSession, job, cnts_id: str) -> tuple[str, dict]:
    """행이 없는 논문의 출처. critic 제외 논문이면 되살림, 소장 목록에 있으면 담기, 둘 다 아니면 404."""
    for c in excluded_candidates(job, []):
        if c["cnts_id"] == cnts_id:
            return "revived", {"subq_idx": c["subq_idx"], "round": c["round"], "note": c["note"]}
    if await db.scalar(select(Book.cnts_id).where(Book.cnts_id == cnts_id)) is None:
        raise HTTPException(status_code=404, detail=NO_PAPER)
    return "user", {}


@router.get("/api/research/{job_id}/reading")
async def get_reading(job_id: str, db: AsyncSession = Depends(get_db)):
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    job = await _get_job(db, jid)
    rows = await _rows(db, jid)
    books = await BookRepository(db).get_by_cnts_ids([r.cnts_id for r in rows])
    outline = await db.scalar(select(ResearchProposal.outline).where(ResearchProposal.work_id == jid))
    return reading_view(work, job, rows, books, outline or {})


@router.put("/api/research/{job_id}/reading/{cnts_id}")
async def put_reading(job_id: str, cnts_id: str, req: ReadingPut, db: AsyncSession = Depends(get_db)):
    """보낸 필드만 바꾼다. 행이 없으면 만든다(되살림·담기 — 새 행의 상태는 보낸 값, 없으면 candidate).
    같은 논문을 동시에 두 번 보내도 INSERT … ON CONFLICT DO NOTHING 이 한 행만 남긴다."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    job = await _get_job(db, jid)
    sent = req.model_fields_set
    if "state" in sent and req.state is None:
        raise HTTPException(status_code=422, detail=STATE_REQUIRED)

    row = await db.get(ResearchReading, (jid, cnts_id))
    created = row is None
    if created:
        origin, origin_ref = await _new_origin(db, job, cnts_id)
        await db.execute(
            insert(ResearchReading)
            .values(work_id=jid, cnts_id=cnts_id, state="candidate", origin=origin, origin_ref=origin_ref)
            .on_conflict_do_nothing()
        )
        row = await db.get(ResearchReading, (jid, cnts_id))

    changes: dict = {}
    if "state" in sent:
        changes["state"] = req.state
    if "note" in sent:
        changes["note"] = _text_or_none(req.note)
    if "group_label" in sent:
        changes["group_label"] = _text_or_none(req.group_label)
    if "position" in sent:
        changes["position"] = req.position
    for name, value in changes.items():
        setattr(row, name, value)

    books = await BookRepository(db).get_by_cnts_ids([cnts_id])
    item = reading_item(row, book_meta(cnts_id, books.get(cnts_id)), job.state_snapshot,
                        subquestions_of(job))
    if not created and not changes:
        return item
    progress = await refresh_progress(db, jid)
    phase = work.phase
    await db.commit()
    await publish_work(jid, "work", {"phase": phase, "progress": progress})
    return item
