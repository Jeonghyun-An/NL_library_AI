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
from services.research.run_queue import median_seconds

# 생성 디스패치 전역 잠금 키(부호 있는 bigint 범위 안). api/research.py 의 _RUN_SLOT_LOCK 과 다르다
GEN_LOCK = int.from_bytes(b"RSWKDISP", "big")

FINISH_STATUSES = ("done", "failed")

# 생성 예상 시간의 표본 — kind 마다 최근 done 몇 건의 소요 시간(finished_at - started_at) 중앙값을 쓰는가
ETA_SAMPLE = 20


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


async def _median_seconds(db, kind: str) -> float | None:
    """kind 의 최근 done ETA_SAMPLE 건 소요 시간 중앙값(초). 표본이 없으면 None.
    빈 결과로 끝난 done(model 없음)도 세 번 부른 실제 시간이라 표본에 넣는다."""
    g = ResearchGeneration
    rows = (await db.execute(
        select(g.started_at, g.finished_at)
        .where(g.kind == kind, g.status == "done", g.started_at.is_not(None), g.finished_at.is_not(None))
        .order_by(g.finished_at.desc(), g.id.desc())
        .limit(ETA_SAMPLE)
    )).all()
    return median_seconds([(finished - started).total_seconds() for started, finished in rows])


async def queue_info(db, gen: ResearchGeneration) -> dict:
    """대기 중(queued) 생성의 순번·예상 시간·다른 연구 작업 여부(spec §6-3 '대기 순번(생성)').

    position 은 queue_position 과 같은 값이다(내 앞 queued + running). eta_sec 는 내 앞 생성(running 포함)마다
    그 kind 의 최근 소요 시간 중앙값을 더한 것 — 한 kind 라도 표본이 없으면 None. others_ahead 는 앞 생성 가운데
    다른 연구의 것이 있는가(화면의 '다른 연구 작업 진행 중'). queued 가 아니면 기다리지 않는다."""
    if gen.status != "queued":
        return {"position": 0, "eta_sec": None, "others_ahead": False}
    g = ResearchGeneration
    # 정렬 키 priority DESC → created_at → id — pick_next·queue_position·ix_research_generations_queued 와 같다
    ahead = (await db.execute(
        select(g.kind, g.work_id).where(or_(
            g.status == "running",
            and_(g.status == "queued", or_(
                g.priority > gen.priority,
                and_(g.priority == gen.priority, or_(
                    g.created_at < gen.created_at,
                    and_(g.created_at == gen.created_at, g.id < gen.id),
                )),
            )),
        ))
    )).all()
    medians: dict[str, float | None] = {}
    for kind in sorted({row.kind for row in ahead}):
        medians[kind] = await _median_seconds(db, kind)
    eta: int | None = None
    if all(medians[row.kind] is not None for row in ahead):
        eta = int(round(sum(medians[row.kind] for row in ahead)))
    return {
        "position": len(ahead),
        "eta_sec": eta,
        "others_ahead": any(row.work_id != gen.work_id for row in ahead),
    }
