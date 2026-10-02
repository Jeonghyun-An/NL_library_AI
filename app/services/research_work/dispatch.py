"""dispatch.py — 생성 디스패처: 전체에서 한 번에 1건 (spec §6-3)

q_research_plan 은 두 자리다. 생성이 두 자리를 다 채우면 새 딥리서치의 '계획 세우는 중'이 생성 1건
길이(최대 약 16분)만큼 밀린다 — 그래서 모든 연구를 통틀어 running 생성은 1건이다.
  pick_next: 전역 advisory lock 안에서 running 수를 세고, 0 이면 queued 하나를
             (우선순위 높은 것 → 오래된 것 → id 순) FOR UPDATE SKIP LOCKED 로 집어 running 으로 바꾼다.
  부분 유니크 인덱스 ux_research_generations_running(연구마다 running 1건)은 이중 안전장치다.
상태 전이는 조건부 UPDATE 로만 한다 — 취소(API)와 회수(회수기)가 같은 행을 바꾼다.
세션에서 execute·commit·rollback·scalar 만 쓴다(tests/history_sqlite 대역이 흉내 내는 것).
"""
from sqlalchemy import and_, exists, func, or_, select, update

from models.research_work import ResearchGeneration

# 생성 디스패치 전역 잠금 키(부호 있는 bigint 범위 안). api/research.py 의 _RUN_SLOT_LOCK 과 다르다
GEN_LOCK = int.from_bytes(b"RSWKDISP", "big")

FINISH_STATUSES = ("done", "failed")


async def pick_next(db) -> ResearchGeneration | None:
    """다음 생성을 running 으로 바꿔 돌려준다. 이미 도는 생성이 있거나 줄이 비었으면 None.

    잠금·개수·집기·전이가 한 트랜잭션이다 — 사이에 커밋이 끼면 겹친 디스패치 둘이 같이 0건을 보고
    둘 다 집는다. 돌려준 행은 커밋 뒤의 값이다(started_at 은 RETURNING 으로 받는다).
    """
    await db.execute(select(func.pg_advisory_xact_lock(GEN_LOCK)))
    running = (await db.execute(
        select(func.count()).select_from(ResearchGeneration)
        .where(ResearchGeneration.status == "running")
    )).scalar_one()
    if running:
        await db.rollback()
        return None
    # 정렬 키 priority DESC → created_at → id — pick_next·queue_position·ix_research_generations_queued(모델·0007)가
    # 함께 바뀐다. 한쪽만 바꾸면 화면 순번과 실제로 집는 순서가 어긋난다
    gen_id = (await db.execute(
        select(ResearchGeneration.id)
        .where(ResearchGeneration.status == "queued")
        .order_by(ResearchGeneration.priority.desc(), ResearchGeneration.created_at,
                  ResearchGeneration.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )).scalar_one_or_none()
    if gen_id is None:
        await db.rollback()
        return None
    gen = (await db.execute(
        update(ResearchGeneration)
        .where(ResearchGeneration.id == gen_id)
        .values(status="running", started_at=func.now())
        .returning(ResearchGeneration)
    )).scalar_one()
    await db.commit()
    return gen


async def finish(db, gen_id: int, *, status: str, output: dict | None, model: str | None,
                 error: str | None) -> bool:
    """running 인 생성만 닫는다. 그 사이 취소·회수로 이미 닫혔으면 False 이고, 같은 트랜잭션의
    앞선 쓰기(결과 적용)까지 되돌린다 — 취소한 생성의 결과가 연구에 남으면 안 된다."""
    if status not in FINISH_STATUSES:
        raise ValueError(f"생성을 닫는 상태는 done·failed 뿐이다: {status!r}")
    res = await db.execute(
        update(ResearchGeneration)
        .where(ResearchGeneration.id == gen_id, ResearchGeneration.status == "running")
        .values(status=status, output=output, model=model, error=error, finished_at=func.now())
    )
    if res.rowcount != 1:
        await db.rollback()
        return False
    await db.commit()
    return True


async def has_queued(db) -> bool:
    return bool(await db.scalar(select(exists().where(ResearchGeneration.status == "queued"))))


async def queue_position(db, gen: ResearchGeneration) -> int:
    """내 앞의 queued(우선순위 높은 것 → 오래된 것 → id 순) + running 수. queued 가 아니면 0."""
    if gen.status != "queued":
        return 0
    g = ResearchGeneration
    # 정렬 키 priority DESC → created_at → id — pick_next·queue_position·ix_research_generations_queued(모델·0007)가
    # 함께 바뀐다
    ahead = await db.scalar(
        select(func.count()).select_from(g).where(
            g.status == "queued",
            or_(
                g.priority > gen.priority,
                and_(g.priority == gen.priority, or_(
                    g.created_at < gen.created_at,
                    and_(g.created_at == gen.created_at, g.id < gen.id),
                )),
            ),
        )
    )
    running = await db.scalar(
        select(func.count()).select_from(g).where(g.status == "running")
    )
    return int(ahead or 0) + int(running or 0)
