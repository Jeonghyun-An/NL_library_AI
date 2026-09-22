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
    "approved", "queued", "running",
    "completed", "failed", "canceled",
)
# status 는 "지금 무슨 상태인가", stage 는 "어디까지 끝냈는가"다. 둘을 한 컬럼으로
# 합치면 실패했을 때 어디부터 다시 할지 알 수 없다 — failed 하나로는 계획에서
# 죽었는지 종합에서 죽었는지 구분되지 않아 5~7분짜리 탐색을 매번 다시 돌게 된다.
JOB_STAGES = ("created", "planned", "explored", "synthesized")

# run_deep_research 가 선점(_claim)할 수 있는 상태. API 의 approve·retry 가 여기
# 없는 값을 써 넣으면 워커가 그 잡을 영원히 건너뛰고, stage·state_snapshot 은
# 쓰기만 하고 아무도 안 읽는 컬럼이 된다. 양쪽이 같은 상수를 보게 묶어둔다.
STATUS_APPROVED = "approved"     # 사용자가 계획을 승인해 큐에 넣었다
STATUS_QUEUED = "queued"         # 실패한 잡을 재시도로 다시 큐에 넣었다
# 철자는 canceled(l 하나) 로 통일한다 — models/ingest_job.py 의 JOB_STATUSES·
# ITEM_STATUSES 가 이미 그 철자다. 두 잡 계열이 서로 다른 철자를 쓰면 상태
# 비교가 조용히 빗나간다.
STATUS_CANCELED = "canceled"
RUNNABLE_STATUSES = (STATUS_APPROVED, STATUS_QUEUED)

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
    stage       = Column(String(16), nullable=False, server_default=text("'created'"))
    # 탐색이 끝난 시점의 ResearchState 스냅샷. 종합만 재실행하기 위한 체크포인트다.
    # 이게 없으면 종합 LLM 이 실패할 때 5~7분짜리 탐색을 통째로 다시 돌려야 한다.
    # 읽는 쪽은 workers/research_tasks.py 의 stage == "explored" 분기이고, 그
    # 분기에 닿는 유일한 경로가 POST /api/research/{job_id}/retry 다.
    state_snapshot = Column(JSONB)
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
