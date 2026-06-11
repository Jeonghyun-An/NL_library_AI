"""
ingest_job.py — 대량 인덱싱 배치 잡 모델

ingest_jobs       : 잡 단위 (매니페스트 1개 = 잡 1개)
ingest_job_items  : 아이템 단위 (도서/논문 1건)

핵심 설계 — stage vs status 분리:
  stage  : 마지막으로 "완료된" 체크포인트 (pending → extracted → summarized → indexed → finalized)
  status : 현재 실행 상태 (pending | dispatched | running | done | failed | skipped | canceled)
재시도는 status='pending' 으로 되돌리되 stage 는 유지 → 실패한 단계부터 재개.
"""
import uuid

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Index, Integer,
    SmallInteger, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.book import Base

# 단계 순서 — 디스패처가 남은 단계 체인을 구성할 때 사용
ITEM_STAGES = ["pending", "extracted", "summarized", "indexed", "finalized"]

JOB_STATUSES = (
    "created", "validating", "ready", "running", "paused",
    "completed", "completed_with_errors", "canceled",
)
ITEM_STATUSES = ("pending", "dispatched", "running", "done", "failed", "skipped", "canceled")


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name          = Column(String(128), nullable=False)
    kind          = Column(String(32), nullable=False, default="paper_bulk")
    status        = Column(String(24), nullable=False, default="created", index=True)
    manifest_key  = Column(Text)            # MinIO manifests/{name}/manifest.jsonl
    # {"skip_cover": true, "doc_type": "paper", "max_attempts": 3, "high_water": 32, ...}
    params        = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    total_items   = Column(Integer, nullable=False, default=0)
    validation_report = Column(JSONB)       # dry-run 결과 요약
    created_by    = Column(String(64))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    started_at    = Column(DateTime(timezone=True))
    finished_at   = Column(DateTime(timezone=True))


class IngestJobItem(Base):
    __tablename__ = "ingest_job_items"
    __table_args__ = (
        UniqueConstraint("job_id", "book_id", name="uq_job_items_job_book"),
        Index("ix_job_items_job_status", "job_id", "status"),
        Index("ix_job_items_job_stage", "job_id", "stage"),
        Index(
            "ix_job_items_job_errgrp", "job_id", "error_group",
            postgresql_where=text("error_group IS NOT NULL"),
        ),
        Index(
            "ix_job_items_inflight", "updated_at",
            postgresql_where=text("status IN ('dispatched','running')"),
        ),
    )

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id         = Column(
        UUID(as_uuid=True),
        ForeignKey("ingest_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    book_id        = Column(String(64), nullable=False)   # library_catalog.cnts_id
    source_key     = Column(Text, nullable=False)          # MinIO object key
    stage          = Column(String(16), nullable=False, default="pending")
    status         = Column(String(16), nullable=False, default="pending")
    attempt        = Column(SmallInteger, nullable=False, default=0)
    # extract_empty | vlm_error | llm_timeout | llm_error | milvus_error | minio_error | stale | unknown
    error_group    = Column(String(32))
    last_error     = Column(Text)
    stage_timings  = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # {"pages": 14, "sections": 5, "chunks": 42, "extract_method": "odl"}
    meta           = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    celery_task_id = Column(String(64))
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    dispatched_at  = Column(DateTime(timezone=True))
    started_at     = Column(DateTime(timezone=True))
    finished_at    = Column(DateTime(timezone=True))
    updated_at     = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
