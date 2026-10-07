"""research_proposal.py — 계획서 API(round06b). spec §5-5(목차 만들기·목차 승인)·§6-2 계획서 줄.

목차 만들기(POST .../outline)는 묶음 수·배정을 서버 코드가 정하고 LLM 은 이름·연구 질문 후보만 쓴다(생성 1건,
gemma). 배정의 재료인 개념 소속은 여기(FastAPI)에서 계산한다 — 임베딩 모델은 FastAPI lifespan 에만 있고 생성
워커에는 GPU 가 없다(함정 17). 계산은 동기라 run_in_threadpool 로 부르고, 그 전에 읽기 트랜잭션을 커밋해 닫는다
— 세션을 쥔 채 임베딩·Milvus 를 기다리지 않는다(함정 18). 계산이 실패하거나 개념이 비면 하위질문 소속으로 한다.
목차 고치기·승인(PUT .../outline)은 If-Match 로 동시 수정을 막는다 — 값은 research_proposals.version(정수),
다르면 409 version_conflict(지금 version 을 실어), 없으면 428. 워커의 결과 반영도 version 을 올리므로 생성이
끝난 뒤의 옛 화면 PUT 은 409 가 된다. 성공 응답은 ProposalView 와 ETag: <새 version>.
LLM 을 부르는 엔드포인트는 없다(게이트웨이 proxy_read_timeout 120초) — 생성은 행을 넣고 디스패치를 보낸다.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.research_work import _get_job, _get_work, _job_uuid, _send_dispatch, _writable
from core.deps import get_db
from models.research_work import (
    GEN_OPEN_STATUSES, ResearchGeneration, ResearchProposal, ResearchReading, ResearchTopic,
    ResearchWork,
)
from repositories.book import BookRepository
from services.research.relay import publish_work
from services.research_work.enqueue import enqueue_generation, queued_event
from services.research_work.membership import (
    MEMBER_THRESHOLD, assign_groups, concept_affinity, group_count, members_from_affinity,
    ordered_papers, subq_affinity,
)
from services.research_work.outline import outline_input
from services.research_work.progress import refresh_progress
from services.research_work.proposal_views import paper_ids, proposal_view
from services.research_work.reading_views import book_meta, subquestions_of
from services.research_work.shapes import (
    GROUP_LABEL_MAX, MAX_GROUPS, MIN_READING_FOR_OUTLINE, OUTLINE_METHOD_MAX, OUTLINE_QUESTION_MAX,
    OUTLINE_TARGET, PHASE_ORDER,
)

router = APIRouter(tags=["research-work"])

PICK_TOPIC_FIRST = "주제를 먼저 고르세요"
NEED_READING = f"담은 논문이 {MIN_READING_FOR_OUTLINE}편 이상이어야 목차를 만듭니다"
OUTLINE_BUSY = "목차를 만드는 중입니다"
NO_OUTLINE = "목차가 없습니다"
IF_MATCH_REQUIRED = "If-Match 가 필요합니다"
IF_MATCH_FORMAT = "If-Match 는 계획서 버전 숫자입니다"
VERSION_CONFLICT = "다른 곳에서 계획서가 바뀌었습니다 — 다시 불러온 뒤 고쳐 주세요"
GROUP_KEYS_DIFFER = "묶음이 저장된 목차와 다릅니다"
GROUP_PAPERS_DIFFER = "묶음의 논문이 저장된 목차와 다릅니다"
PAPER_IN_TWO_GROUPS = "한 논문이 두 묶음에 들어 있습니다"
EMPTY_GROUP = "빈 묶음이 있습니다"
EMPTY_GROUP_NAME = "묶음 이름을 써 주세요"
APPROVE_NEEDS_QUESTION = "목차를 승인하려면 연구 질문을 2자 이상 써 주세요"
MAX_GROUP_PAPERS = 500        # 묶음 하나의 논문 수 상한(본문 크기 방어) — 읽기 목록 전체보다 넉넉하다


class OutlineGroupIn(BaseModel):
    key: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=GROUP_LABEL_MAX)
    papers: list[str] = Field(max_length=MAX_GROUP_PAPERS)


class OutlinePut(BaseModel):
    groups: list[OutlineGroupIn] = Field(min_length=1, max_length=MAX_GROUPS)
    question: str = Field(max_length=OUTLINE_QUESTION_MAX)
    method: str = Field(max_length=OUTLINE_METHOD_MAX)
    approve: bool


def _if_match(value: str | None) -> int:
    """If-Match 헤더 → 기대 version. 따옴표·약한 비교 표시(W/)는 벗겨 읽는다. 없으면 428, 숫자가 아니면 422."""
    raw = (value or "").strip()
    if not raw:
        raise HTTPException(status_code=428, detail=IF_MATCH_REQUIRED)
    if raw.startswith("W/"):
        raw = raw[2:]
    try:
        return int(raw.strip('"'))
    except ValueError:
        raise HTTPException(status_code=422, detail=IF_MATCH_FORMAT)


def _version_conflict(version: int) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": "version_conflict", "version": version,
                                                   "message": VERSION_CONFLICT})


async def _open(db: AsyncSession, jid, kind: str, target: str | None) -> bool:
    G = ResearchGeneration
    same = G.target.is_(None) if target is None else G.target == target
    return await db.scalar(
        select(G.id).where(G.work_id == jid, G.kind == kind, same, G.status.in_(GEN_OPEN_STATUSES)).limit(1)
    ) is not None


async def _picked_rows(db: AsyncSession, jid) -> list[ResearchReading]:
    return list((await db.execute(
        select(ResearchReading).where(ResearchReading.work_id == jid, ResearchReading.state == "in")
    )).scalars().all())


async def _picked_topic(db: AsyncSession, work) -> ResearchTopic | None:
    if work.topic_id is None:
        return None
    topic = await db.get(ResearchTopic, work.topic_id)
    if topic is None or topic.work_id != work.id or not (topic.card or {}).get("title"):
        return None
    return topic


async def _proposal_response(db: AsyncSession, work, response: Response) -> dict:
    """ProposalView 를 만들고 ETag 를 단다 — GET 과 PUT(목차·절)이 같은 모양을 돌려준다."""
    jid = work.id
    job = await _get_job(db, jid)
    proposal = (await db.execute(
        select(ResearchProposal).where(ResearchProposal.work_id == jid)
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    G = ResearchGeneration
    generations = list((await db.execute(select(G).where(G.work_id == jid).order_by(G.id))).scalars().all())
    picked = {r.cnts_id for r in await _picked_rows(db, jid)}
    topic = await _picked_topic(db, work)
    ids = paper_ids(proposal, generations)
    ids += [c for c in ((topic.card or {}).get("evidence") or [] if topic else []) if c not in ids]
    books = await BookRepository(db).get_by_cnts_ids(ids)
    # 고른 주제 행을 그대로 넘긴다 — 카드 제목(목차 뒤 [직접 고치기] 면 다시 맞춤 필요)·출처(topic_source — 공개 부록)
    view = proposal_view(work, job, proposal, books, generations, picked, topic)
    response.headers["ETag"] = str(view["version"])
    return view


@router.get("/api/research/{job_id}/proposal")
async def get_proposal(job_id: str, response: Response, db: AsyncSession = Depends(get_db)):
    work = await _get_work(db, _job_uuid(job_id))
    return await _proposal_response(db, work, response)


@router.post("/api/research/{job_id}/outline")
async def create_outline(job_id: str, db: AsyncSession = Depends(get_db)):
    """[목차 만들기] — 개념 소속을 계산해 concept_members 를 저장하고, 계획서 행이 없으면 만들고(version 1),
    목차 생성 1건을 넣는다. 단계를 proposal 로 올린다(앞으로만)."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    job = await _get_job(db, jid)
    topic = await _picked_topic(db, work)
    if topic is None:
        raise HTTPException(status_code=409, detail=PICK_TOPIC_FIRST)
    rows = await _picked_rows(db, jid)
    if len(rows) < MIN_READING_FOR_OUTLINE:
        raise HTTPException(status_code=409, detail=NEED_READING)
    if await _open(db, jid, "outline", OUTLINE_TARGET):
        raise HTTPException(status_code=409, detail=OUTLINE_BUSY)
    papers = ordered_papers(rows)
    books = await BookRepository(db).get_by_cnts_ids(papers)
    metas = {c: book_meta(c, books.get(c)) for c in papers}
    concepts = list(work.concepts or [])
    subquestions = subquestions_of(job)
    by_subq = subq_affinity(rows, subquestions)
    question = job.question
    card = topic.card or {}
    topic_view = {"id": topic.id, "title": card.get("title") or "", "question": card.get("question") or ""}
    await db.commit()             # 읽기 트랜잭션을 닫는다 — 임베딩·Milvus 를 기다리는 동안 세션을 쥐지 않는다

    affinity = await run_in_threadpool(concept_affinity, concepts, papers) if concepts else None
    if affinity and any(affinity.values()):
        basis, keys = "concept", concepts
    else:
        basis, keys, affinity = "subq", subquestions, by_subq
    groups = assign_groups(papers, affinity, group_count(len(papers)), keys=keys)
    gen_input = outline_input(question, topic_view, concepts, basis, groups, metas)

    gen_id = await enqueue_generation(db, jid, kind="outline", target=OUTLINE_TARGET, input=gen_input)
    if gen_id is None:
        await db.rollback()
        raise HTTPException(status_code=409, detail=OUTLINE_BUSY)
    if basis == "concept":
        await db.execute(
            update(ResearchWork).where(ResearchWork.id == jid)
            .values(concept_members=members_from_affinity(affinity, concepts, MEMBER_THRESHOLD))
        )
    await db.execute(
        insert(ResearchProposal).values(work_id=jid, version=1, outline={}, sections={})
        .on_conflict_do_nothing()
    )
    before = PHASE_ORDER[:PHASE_ORDER.index("proposal")]
    advanced = (await db.execute(
        update(ResearchWork).where(ResearchWork.id == jid, ResearchWork.phase.in_(before))
        .values(phase="proposal")
    )).rowcount == 1
    progress = await refresh_progress(db, jid)
    await db.commit()
    _send_dispatch()
    await publish_work(jid, "generation", queued_event(gen_id, "outline", OUTLINE_TARGET))
    if advanced:
        await publish_work(jid, "work", {"phase": "proposal", "progress": progress})
    return {"gen_id": gen_id}


def _checked_groups(req: OutlinePut, stored: list[dict]) -> list[dict]:
    """사용자가 옮긴 묶음 — 키는 저장된 키 그대로(순서까지), 논문 합집합도 그대로, 한 논문은 한 묶음에,
    빈 묶음 없음. hint 는 저장된 값을 지킨다. 이름 겹침은 보지 않는다(계약 보강 4 — LLM 결과만
    outline.check 가 본다)."""
    if [g.key for g in req.groups] != [g.get("key") for g in stored]:
        raise HTTPException(status_code=422, detail=GROUP_KEYS_DIFFER)
    seen: set[str] = set()
    out = []
    for g, old in zip(req.groups, stored):
        name = " ".join(g.name.split())
        if not name:
            raise HTTPException(status_code=422, detail=EMPTY_GROUP_NAME)
        if not g.papers:
            raise HTTPException(status_code=422, detail=EMPTY_GROUP)
        for cnts_id in g.papers:
            if cnts_id in seen:
                raise HTTPException(status_code=422, detail=PAPER_IN_TWO_GROUPS)
            seen.add(cnts_id)
        out.append({"key": g.key, "name": name, "hint": old.get("hint") or "", "papers": list(g.papers)})
    if seen != {c for g in stored for c in g.get("papers") or []}:
        raise HTTPException(status_code=422, detail=GROUP_PAPERS_DIFFER)
    return out


@router.put("/api/research/{job_id}/outline")
async def put_outline(job_id: str, req: OutlinePut, response: Response,
                      if_match: str | None = Header(None), db: AsyncSession = Depends(get_db)):
    """목차 고치기·승인. approve 면 state approved(승인 시각), 아니면 draft — 승인한 목차를 고쳐 저장하면 다시
    승인해야 절을 쓴다. version 이 다르면 409(조건부 UPDATE 로 확인과 쓰기를 한 문장에)."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    expected = _if_match(if_match)
    proposal = await db.get(ResearchProposal, jid)
    if proposal is None or not proposal.outline:
        raise HTTPException(status_code=404, detail=NO_OUTLINE)
    if await _open(db, jid, "outline", OUTLINE_TARGET):
        raise HTTPException(status_code=409, detail=OUTLINE_BUSY)
    if proposal.version != expected:
        raise _version_conflict(proposal.version)
    outline = dict(proposal.outline)
    groups = _checked_groups(req, list(outline.get("groups") or []))
    question = " ".join(req.question.split())
    if req.approve and len(question) < 2:
        raise HTTPException(status_code=422, detail=APPROVE_NEEDS_QUESTION)
    outline.update({
        "groups": groups,
        "question": question or None,
        "method": req.method.strip(),
        "state": "approved" if req.approve else "draft",
        "approved_at": datetime.now(timezone.utc).isoformat() if req.approve else None,
    })
    res = await db.execute(
        update(ResearchProposal)
        .where(ResearchProposal.work_id == jid, ResearchProposal.version == expected)
        .values(outline=outline, version=expected + 1)
    )
    if res.rowcount != 1:
        await db.rollback()
        current = await db.scalar(select(ResearchProposal.version).where(ResearchProposal.work_id == jid))
        raise _version_conflict(current)
    progress = await refresh_progress(db, jid)
    phase = work.phase
    await db.commit()
    await publish_work(jid, "work", {"phase": phase, "progress": progress})
    return await _proposal_response(db, work, response)
