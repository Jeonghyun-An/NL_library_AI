"""enqueue.py — 생성 1건을 줄에 세운다 (spec §6-3 '생성을 넣는 API', 06b 계획 공통 계약 §2)

생성을 넣는 엔드포인트(이어가기·다른 방향·목차·절 쓰기·문단 다시 쓰기)가 함께 쓴다. 순서는
enqueue_generation → 커밋 → _send_dispatch() → publish_work(jid, "generation", queued_event(...)) 다.
같은 (연구·kind·target) 의 넣기는 트랜잭션 잠금으로 한 줄로 세운다 — 두 번 눌러도 같은 일이 두 줄 서지 않는다.
잠금 키는 06a 의 '다시'(api/research_work._retry_lock_key)와 같은 식이라 '다시' 와 새 생성도 서로를 기다린다.
커밋·롤백은 부르는 쪽이 한다 — 이어가기처럼 같은 트랜잭션에서 다른 행을 함께 넣는 호출이 있다.
세션에서는 execute·scalar 만 쓴다(tests/history_sqlite 대역이 흉내 내는 것).
"""
import hashlib
import uuid

from sqlalchemy import func, insert, select

from models.research_work import GEN_OPEN_STATUSES, PRIORITY_USER, ResearchGeneration

OPEN_SAME = "같은 생성이 이미 대기 중이거나 진행 중입니다"


def lock_key(work_id: uuid.UUID | str, kind: str, target: str | None) -> int:
    """(연구·kind·target) 별 pg_advisory_xact_lock 키 — sha256 앞 8바이트를 부호 있는 64비트 정수로.
    work_id 는 uuid 의 표준형 문자열로 넣는다(uuid.UUID 를 f-string 에 넣은 값과 같다)."""
    raw = f"research_work_retry:{work_id}:{kind}:{target or ''}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=True)


async def enqueue_generation(db, work_id: uuid.UUID, *, kind: str, target: str | None, input: dict,
                             priority: int = PRIORITY_USER) -> int | None:
    """queued 생성 한 행을 넣고 id 를 돌려준다. 같은 (연구·kind·target) 의 생성이 열려(queued·running)
    있으면 넣지 않고 None — 부르는 쪽이 롤백하고 409(OPEN_SAME)로 답한다. 잠금은 커밋·롤백까지 쥔다."""
    G = ResearchGeneration
    await db.execute(select(func.pg_advisory_xact_lock(lock_key(work_id, kind, target))))
    same_target = G.target.is_(None) if target is None else G.target == target
    if await db.scalar(
        select(G.id).where(G.work_id == work_id, G.kind == kind, same_target,
                           G.status.in_(GEN_OPEN_STATUSES)).limit(1)
    ) is not None:
        return None
    return await db.scalar(
        insert(G).values(work_id=work_id, kind=kind, target=target, priority=priority,
                         status="queued", input=input)
        .returning(G.id)
    )


def queued_event(gen_id: int, kind: str, target: str | None) -> dict:
    """generation 이벤트(queued)의 페이로드 — 워커·취소·다시와 같은 키다. 생성 종류는 gen_kind 에 싣는다
    (relay 가 이벤트 종류를 "kind" 에 싣는다)."""
    return {"gen_id": gen_id, "gen_kind": kind, "target": target, "status": "queued",
            "model": None, "result": None}
