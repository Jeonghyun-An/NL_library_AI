"""research_topics.py — 연구 어시스턴트 주제 단계 API (round06b, spec §5-2·§6-2 '주제', 계약 §6)

조회(TopicsView)·[다른 방향](쓰지 않은 보고서 씨앗으로 카드 2장 더)·[직접 쓰기](사용자 카드, LLM 없음)·
[직접 고치기](제목·연구 질문만, card.edited)·[고르기](다음 단계로 갈 주제 하나 — phase 를 reading 으로 올린다).
카드 1장 = 생성 1건이다(D8 — 한 번에 여러 장을 시키면 구성이 무너진다). 생성은 06a 디스패처(전역 1건)가 돈다.

06a 라우터(api/research_work.py)의 도우미를 그대로 쓴다 — 잡 id 형식(422)·연구 없음(404)·예시 연구 쓰기(409)·
디스패치 보내기(실패해도 응답은 그대로, 회수기가 다시 보낸다)가 두 라우터에서 같아야 한다.
동기 엔드포인트라 LLM 을 부르지 않는다.
"""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints, model_validator
from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.research_work import _get_job, _get_work, _job_uuid, _send_dispatch, _writable
from core.deps import get_db
from models.research_work import GEN_OPEN_STATUSES, ResearchGeneration, ResearchTopic, ResearchWork
from services.research.relay import publish_work
from services.research_work.enqueue import enqueue_generation, lock_key, queued_event
from services.research_work.markers import numbers_outside, soften_claims
from services.research_work.progress import refresh_progress
from services.research_work.seeds import corpus_of, pick_seeds, topic_input, used_seed_keys
from services.research_work.shapes import (
    OTHER_DIRECTION_CARDS, TOPIC_QUESTION_MAX, TOPIC_TITLE_MAX,
)
from services.research_work.topic_views import topic_item, topics_view

router = APIRouter(tags=["research-work"])

NO_MORE_SEEDS = "더 쓸 씨앗이 없습니다"
TOPIC_NOT_FOUND = "주제가 없습니다"
CARD_BUSY = "카드를 만드는 중입니다 — 끝난 뒤 고쳐 주세요"
NO_CARD_YET = "카드가 아직 없습니다"
EMPTY_CARD_NEEDS_BOTH = "빈 카드는 제목과 연구 질문을 함께 보내 주세요"
# [다른 방향] 의 연구별 잠금 대상 — 주제 카드 생성의 target(주제 id 숫자 문자열)과 겹치지 않는 이름
OTHER_LOCK_TARGET = "other-direction"
# [고르기] 의 연구별 잠금 kind — 생성 kind 가 아니라 생성 넣기·[다른 방향]의 잠금과 겹치지 않는다
PICK_LOCK_KIND = "topic_pick"

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=TOPIC_TITLE_MAX)]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=TOPIC_QUESTION_MAX)]


class TopicsGenerate(BaseModel):
    mode: Literal["other"]            # 'cell'(이 칸으로 주제 만들기)은 06c — 그 전에는 422


class TopicCreate(BaseModel):
    title: Title
    question: Question


class TopicPatch(BaseModel):
    title: Title | None = None
    question: Question | None = None

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.title is None and self.question is None:
            raise ValueError("제목이나 연구 질문 중 하나는 보내 주세요")
        return self


def _soft(text: str) -> tuple[str, int]:
    return soften_claims(" ".join(text.split()))


def _user_card(title: str, question: str, *, edited: bool) -> dict:
    """사용자가 쓴 카드(계약 §4 Card) — 근거 칩·수치 없이 제목·질문만. 단정 표현은 카드와 같은 규칙으로 바꾼다."""
    title, soft_title = _soft(title)
    question, soft_question = _soft(question)
    return {"title": title[:TOPIC_TITLE_MAX], "question": question[:TOPIC_QUESTION_MAX], "evidence": [],
            "figure_sentence": None, "figures": [], "latest_year": None, "edited": edited,
            "checks": {"numbers": numbers_outside(f"{title}\n{question}"),
                       "softened": soft_title + soft_question, "recovered": 0},
            "gen_id": None}


async def _get_topic(db: AsyncSession, jid: uuid.UUID, tid: int) -> ResearchTopic:
    topic = await db.get(ResearchTopic, tid)
    if topic is None or topic.work_id != jid:
        raise HTTPException(status_code=404, detail=TOPIC_NOT_FOUND)
    return topic


async def _latest_card_generation(db: AsyncSession, jid: uuid.UUID, tid: int) -> ResearchGeneration | None:
    G = ResearchGeneration
    return await db.scalar(
        select(G).where(G.work_id == jid, G.kind == "topic_card", G.target == str(tid))
        .order_by(G.id.desc()).limit(1)
    )


async def _card_open(db: AsyncSession, jid: uuid.UUID, tid: int) -> bool:
    G = ResearchGeneration
    return await db.scalar(
        select(G.id).where(G.work_id == jid, G.kind == "topic_card", G.target == str(tid),
                           G.status.in_(GEN_OPEN_STATUSES)).limit(1)
    ) is not None


@router.get("/api/research/{job_id}/topics")
async def get_topics(job_id: str, db: AsyncSession = Depends(get_db)):
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    job = await _get_job(db, jid)
    rows = (await db.execute(select(ResearchTopic).where(ResearchTopic.work_id == jid))).scalars().all()
    G = ResearchGeneration
    gens = (await db.execute(
        select(G).where(G.work_id == jid, G.kind == "topic_card")
    )).scalars().all()
    return topics_view(work, job, rows, gens)


@router.post("/api/research/{job_id}/topics/generate")
async def generate_topics(job_id: str, req: TopicsGenerate, db: AsyncSession = Depends(get_db)):
    """[다른 방향] — 쓰지 않은 보고서 씨앗으로 카드 OTHER_DIRECTION_CARDS 장(origin other, 자리 없음). 연구별
    잠금이 '쓴 씨앗 읽기 → 주제·생성 넣기' 를 한 줄로 세운다 — 두 번 눌러도 같은 씨앗이 두 장 되지 않는다."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    job = await _get_job(db, jid)
    report = job.report if isinstance(job.report, dict) else {}
    await db.execute(select(func.pg_advisory_xact_lock(lock_key(jid, "topic_card", OTHER_LOCK_TARGET))))
    seeds_used = (await db.execute(
        select(ResearchTopic.seed).where(ResearchTopic.work_id == jid)
    )).scalars().all()
    seeds = pick_seeds(report, limit=OTHER_DIRECTION_CARDS, exclude=used_seed_keys(seeds_used))
    if not seeds:
        await db.rollback()
        raise HTTPException(status_code=409, detail=NO_MORE_SEEDS)
    corpus = work.corpus_snapshot or corpus_of(job)
    topic_ids: list[int] = []
    gen_ids: list[int] = []
    for seed in seeds:
        topic_id = await db.scalar(
            insert(ResearchTopic)
            .values(work_id=jid, slot=None, origin="other", seed=seed, card={}, state="candidate",
                    corpus_snapshot=corpus)
            .returning(ResearchTopic.id)
        )
        # 방금 만든 주제라 열린 생성이 없다 — enqueue_generation 은 늘 새 id 를 돌려준다
        gen_id = await enqueue_generation(db, jid, kind="topic_card", target=str(topic_id),
                                          input=topic_input(job.question, seed, report, topic_id))
        topic_ids.append(topic_id)
        gen_ids.append(gen_id)
    await db.commit()
    _send_dispatch()
    for topic_id, gen_id in zip(topic_ids, gen_ids):
        await publish_work(jid, "generation", queued_event(gen_id, "topic_card", str(topic_id)))
    return {"topic_ids": topic_ids, "gen_ids": gen_ids}


@router.post("/api/research/{job_id}/topics")
async def create_topic(job_id: str, req: TopicCreate, db: AsyncSession = Depends(get_db)):
    """[직접 쓰기] — 사용자 카드(origin user, 씨앗·근거 없음). LLM 을 부르지 않는다."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    topic_id = await db.scalar(
        insert(ResearchTopic)
        .values(work_id=jid, slot=None, origin="user", seed={}, state="candidate",
                card=_user_card(req.title, req.question, edited=False), corpus_snapshot=work.corpus_snapshot)
        .returning(ResearchTopic.id)
    )
    progress = await refresh_progress(db, jid)
    await db.commit()
    await publish_work(jid, "work", {"phase": work.phase, "progress": progress})
    return topic_item(await _get_topic(db, jid, topic_id), None)


@router.patch("/api/research/{job_id}/topics/{tid}")
async def edit_topic(job_id: str, tid: int, req: TopicPatch, db: AsyncSession = Depends(get_db)):
    """[직접 고치기] — 제목·연구 질문만 바꾸고 card.edited 를 켠다(origin 은 그대로, 근거 칩은 그대로).
    카드가 비었으면(근거 부족) 이 요청이 사용자 카드를 만든다 — 그때는 제목과 질문을 함께 받는다.
    그 주제의 카드 생성이 열려 있으면 409 — 끝나는 결과가 고친 글과 겹친다."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    topic = await _get_topic(db, jid, tid)
    if await _card_open(db, jid, tid):
        raise HTTPException(status_code=409, detail=CARD_BUSY)
    card = dict(topic.card or {})
    if not card:
        if req.title is None or req.question is None:
            raise HTTPException(status_code=422, detail=EMPTY_CARD_NEEDS_BOTH)
        topic.card = _user_card(req.title, req.question, edited=True)
        topic.state = "candidate"
    else:
        softened = 0
        if req.title is not None:
            card["title"], n = _soft(req.title)
            card["title"] = card["title"][:TOPIC_TITLE_MAX]
            softened += n
        if req.question is not None:
            card["question"], n = _soft(req.question)
            card["question"] = card["question"][:TOPIC_QUESTION_MAX]
            softened += n
        checks = dict(card.get("checks") or {})
        checks.update(numbers=numbers_outside(f"{card['title']}\n{card['question']}"), softened=softened)
        card.update(edited=True, checks=checks)
        topic.card = card
    progress = await refresh_progress(db, jid)
    await db.commit()
    await publish_work(jid, "work", {"phase": work.phase, "progress": progress})
    return topic_item(await _get_topic(db, jid, tid), await _latest_card_generation(db, jid, tid))


@router.post("/api/research/{job_id}/topics/{tid}/pick")
async def pick_topic(job_id: str, tid: int, db: AsyncSession = Depends(get_db)):
    """[고르기] — 다음 단계는 고른 주제 하나로 간다. 이전에 고른 주제는 candidate 로 돌린다(지우지 않는다).
    phase 는 reading 까지 올리고(이미 더 앞이면 그대로 — 단계는 앞으로만), 주제를 바꾸면 뒤 단계에
    '다시 맞춤 필요' 가 붙는다(조회 때 계산)."""
    jid = _job_uuid(job_id)
    work = await _get_work(db, jid)
    _writable(work)
    # 같은 연구의 고르기를 한 줄로 세운다 — 두 탭이 다른 주제를 거의 같이 고르면 뒤 트랜잭션의 'picked → candidate'
    # 가 문장 스냅숏에서 앞이 막 고른 행을 candidate 로 보고 건너뛰어 picked 가 둘 남는다. 연구 행 FOR UPDATE 는 쓰지
    # 않는다 — 워커 topic_card.apply 의 '주제 행 → 연구 행' 잠금 순서와 뒤집힌다
    await db.execute(select(func.pg_advisory_xact_lock(lock_key(jid, PICK_LOCK_KIND, None))))
    topic = await _get_topic(db, jid, tid)
    if not topic.card:
        raise HTTPException(status_code=409, detail=NO_CARD_YET)
    await db.execute(
        update(ResearchTopic)
        .where(ResearchTopic.work_id == jid, ResearchTopic.state == "picked", ResearchTopic.id != tid)
        .values(state="candidate")
    )
    await db.execute(update(ResearchTopic).where(ResearchTopic.id == tid).values(state="picked"))
    # 단계는 앞으로만(정함 14) — 요청 처음에 읽은 work.phase 로 정해 덮으면, 그사이 다른 탭의 목차 만들기가 올린
    # proposal 을 reading 으로 되돌린다. 한 문장 안에서 지금 값을 보고 topics 일 때만 reading 으로 올린다
    phase = await db.scalar(
        update(ResearchWork).where(ResearchWork.id == jid)
        .values(topic_id=tid,
                phase=case((ResearchWork.phase == "topics", "reading"), else_=ResearchWork.phase))
        .returning(ResearchWork.phase)
    )
    progress = await refresh_progress(db, jid)
    await db.commit()
    await publish_work(jid, "work", {"phase": phase, "progress": progress})
    return {"topic_id": tid, "phase": phase}
