"""history_sqlite.py — 기록 저장소·API 테스트가 함께 쓰는 DB.

로컬에 Postgres 도 aiosqlite 도 없다. 표준 라이브러리 sqlite3 위의 동기 Session 을
AsyncSession 모양으로 감싸, 저장소가 내는 SQL(upsert·커서·소프트 삭제 조건)을 실제
엔진이 실행하게 한다. 대역이 SQL 을 흉내 내면 그 조건을 대역이 대신 판정하게 되어
저장소의 버그를 못 잡는다.

SQLite 가 모르는 Postgres 표기 둘만 테스트 쪽에서 바꾼다 — JSONB 타입 이름(JSON 으로
그린다)과 '::jsonb' 가 붙은 서버 기본값(테스트 테이블에서만 뺀다. 저장소는 params 를
늘 채워 넣는다). 운영 모델·마이그레이션은 그대로다.
"""
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from models.history import HistoryItem
from models.research import ResearchJob

SID_A = uuid.UUID("3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e")
SID_B = uuid.UUID("7a6b5c4d-3e2f-4a1b-9c8d-7e6f5a4b3c2d")


@compiles(JSONB, "sqlite")
def _jsonb_as_json(type_, compiler, **kw):
    return "JSON"


def make_engine() -> sa.Engine:
    # 인메모리 DB 는 연결마다 따로 생긴다 — StaticPool 로 한 연결을 모두가 쓴다.
    # TestClient 는 앱을 다른 스레드에서 돌리므로 스레드 검사도 끈다.
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    metadata = sa.MetaData()
    for table in (HistoryItem.__table__, ResearchJob.__table__):
        copy = table.to_metadata(metadata)
        for col in copy.columns:
            default = col.server_default
            if default is not None and "::" in str(getattr(default, "arg", "")):
                col.server_default = None
    metadata.create_all(engine)
    return engine


class AsyncSessionOverSync:
    """저장소·라우터가 쓰는 AsyncSession 메서드만 동기 Session 으로 넘긴다."""

    def __init__(self, engine: sa.Engine):
        self._session = Session(engine)

    async def execute(self, stmt, params=None):
        return self._session.execute(stmt, params)

    async def commit(self):
        self._session.commit()

    async def rollback(self):
        self._session.rollback()

    async def close(self):
        self._session.close()


def add_research_job(engine: sa.Engine, *, status: str, stage: str) -> uuid.UUID:
    job_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(sa.insert(ResearchJob.__table__).values(
            id=job_id, question="독서 격차 연구", status=status, stage=stage, params={},
        ))
    return job_id


def raw_row(engine: sa.Engine, item_id: uuid.UUID):
    """소프트 삭제가 행을 남기는지처럼 API 가 보여 주지 않는 것을 확인할 때 쓴다."""
    with engine.connect() as conn:
        return conn.execute(
            sa.select(HistoryItem.__table__).where(HistoryItem.__table__.c.id == item_id)
        ).first()
