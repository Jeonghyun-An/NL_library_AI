"""apply.py — 끝난 생성의 결과를 연구에 반영한다.

디스패처가 finish 와 같은 트랜잭션에서 부른다. 여기서는 커밋하지 않는다 — finish 가 생성 상태와 함께
커밋하고, 도는 사이 취소됐으면(finish 가 False) 이 반영도 함께 되돌린다.
"""
from sqlalchemy import update

from models.research_work import ResearchWork


async def apply_result(db, gen, output: dict) -> dict:
    """gen.kind 에 맞게 반영하고 generation 이벤트의 result 로 실을 값을 돌려준다.

    concepts: research_works.concepts 를 바꾸고 개념 소속(concept_members)을 비운다 — 소속은 FastAPI 가
    개념 임베딩으로 다시 계산한다(spec §5-3, 06c). 세 번 다 못 얻은 빈 결과면 연구를 건드리지 않는다 —
    빈 결과를 다시 부르기 전에 사용자가 넣은 칩과 소속을 아무 결과 없이 지우면 안 된다.
    그 밖의 kind 는 06a 에 실행기가 없어 하는 일이 없다.
    """
    if gen.kind == "concepts":
        concepts = list(output.get("concepts") or [])
        if concepts:
            await db.execute(
                update(ResearchWork)
                .where(ResearchWork.id == gen.work_id)
                .values(concepts=concepts, concept_members={})
            )
        return {"concepts": concepts}
    return {}
