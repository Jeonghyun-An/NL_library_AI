"""history_sqlite.py — 기록 저장소·API 테스트가 함께 쓰는 DB.

로컬에 Postgres 도 aiosqlite 도 없다. 표준 라이브러리 sqlite3 위의 동기 Session 을
AsyncSession 모양으로 감싸, 저장소가 내는 SQL(upsert·커서·소프트 삭제 조건)을 실제
엔진이 실행하게 한다. 대역이 SQL 을 흉내 내면 그 조건을 대역이 대신 판정하게 되어
저장소의 버그를 못 잡는다.

SQLite 가 모르는 Postgres 표기 셋만 테스트 쪽에서 바꾼다 — JSONB 타입 이름(JSON 으로
그린다), '::jsonb' 가 붙은 서버 기본값(테스트 테이블에서만 뺀다. 저장소는 params 를
늘 채워 넣는다), BIGINT 기본키(INTEGER 로 — SQLite 는 INTEGER PRIMARY KEY 만 자동으로
번호를 매긴다). Postgres 함수 pg_advisory_xact_lock 은 아무 일도 하지 않는 SQLite 함수로
둔다(잠금 순서는 문장 기록으로 확인한다). 운영 모델·마이그레이션은 그대로다.
"""
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from models.history import HistoryItem
from models.research import ResearchJob
from models.research_work import ResearchGeneration, ResearchWork

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

    @sa.event.listens_for(engine, "connect")
    def _pg_functions(dbapi_conn, _record):
        # Postgres 트랜잭션 잠금은 SQLite 에서 아무 일도 하지 않는 함수로 둔다 — 잠금 순서는 문장 기록으로 확인한다
        dbapi_conn.create_function("pg_advisory_xact_lock", 1, lambda _key: None)

    metadata = sa.MetaData()
    for table in (HistoryItem.__table__, ResearchJob.__table__,
                  ResearchWork.__table__, ResearchGeneration.__table__):
        copy = table.to_metadata(metadata)
        for col in copy.columns:
            default = col.server_default
            if default is not None and "::" in str(getattr(default, "arg", "")):
                col.server_default = None
            # SQLite 는 INTEGER PRIMARY KEY 만 자동으로 번호를 매긴다 — BIGINT 기본키는 테스트 사본에서만 INTEGER 로
            if col.primary_key and isinstance(col.type, sa.BigInteger):
                col.type = sa.Integer()
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

    async def get(self, model, pk):
        return self._session.get(model, pk)

    def add(self, obj):
        self._session.add(obj)

    async def flush(self):
        self._session.flush()

    async def scalar(self, stmt, params=None):
        return self._session.scalar(stmt, params)


def add_research_job(engine: sa.Engine, *, status: str, stage: str) -> uuid.UUID:
    job_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(sa.insert(ResearchJob.__table__).values(
            id=job_id, question="독서 격차 연구", status=status, stage=stage, params={},
        ))
    return job_id


def add_work(engine: sa.Engine, job_id: uuid.UUID, *, owner_sid: str | None = None,
             phase: str = "topics", concepts: list | None = None, is_example: bool = False) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(ResearchWork.__table__).values(
            id=job_id, owner_sid=owner_sid, phase=phase, concepts=concepts or [],
            concept_members={}, progress={}, is_example=is_example,
        ))


def add_generation(engine: sa.Engine, work_id: uuid.UUID, *, kind: str = "concepts",
                   status: str = "queued", priority: int = 10, input: dict | None = None,
                   started_at=None) -> int:
    with engine.begin() as conn:
        res = conn.execute(sa.insert(ResearchGeneration.__table__).values(
            work_id=work_id, kind=kind, status=status, priority=priority,
            input=input or {}, started_at=started_at,
        ).returning(ResearchGeneration.__table__.c.id))
        return res.scalar_one()


def raw_row(engine: sa.Engine, item_id: uuid.UUID):
    """소프트 삭제가 행을 남기는지처럼 API 가 보여 주지 않는 것을 확인할 때 쓴다."""
    with engine.connect() as conn:
        return conn.execute(
            sa.select(HistoryItem.__table__).where(HistoryItem.__table__.c.id == item_id)
        ).first()
