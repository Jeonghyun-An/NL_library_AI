"""research.py — 딥리서치 잡 모델

research_jobs  : 리서치 1건 (질문 1개 = 잡 1개)
research_steps : 의미 있는 단계 (계획 · 하위질문별 탐색 · 점검 · 종합)

research_steps 는 진행 패널이자 보고서의 탐색 경로 섹션이다. 초당 갱신되는
잔이벤트(카운터 등)는 여기 쓰지 않고 Redis pub/sub 으로만 흘린다 — 입자가
다르고, 보고서에 남을 것과 몇 초 뒤 사라질 것을 한 테이블에 섞으면
보존 정책과 append/update 성격이 충돌한다.
"""
import uuid

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.book import Base

JOB_STATUSES = (
    "created", "planning", "awaiting_approval",
    "running", "completed", "failed", "canceled",
)
STEP_KINDS = ("plan", "search", "critique", "synthesize")
STEP_STATUSES = ("pending", "running", "done", "failed")


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question    = Column(Text, nullable=False)
    status      = Column(String(24), nullable=False, default="created", index=True)
    params      = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    plan        = Column(JSONB)      # 사용자 수정이 반영된 하위질문 목록
    report      = Column(JSONB)
    last_error  = Column(Text)
    created_by  = Column(String(64))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    started_at  = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


class ResearchStep(Base):
    __tablename__ = "research_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "seq", name="uq_research_steps_job_seq"),
        Index(
            "ix_research_steps_inflight", "updated_at",
            postgresql_where=text("status = 'running'"),
        ),
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id      = Column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq         = Column(Integer, nullable=False)
    kind        = Column(String(16), nullable=False)
    subq_idx    = Column(Integer)
    title       = Column(Text, nullable=False)
    detail      = Column(Text)
    status      = Column(String(16), nullable=False, default="pending")
    # kind 별 shape — API 가 가공 없이 프론트로 넘기고 프론트가 kind 로 분기한다.
    # plan:       {"subquestions": [...]}
    # search:     {"queries": [...], "adopted": n, "verdict": "...", "note": "..."}
    # synthesize: {"sections": n}
    # 실패 공통:   {"error": "..."}
    result      = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    updated_at  = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
