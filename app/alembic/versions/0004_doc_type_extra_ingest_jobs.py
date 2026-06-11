"""doc_type/extra 컬럼 + 대량 인덱싱 잡 테이블

- library_catalog.doc_type  : 프로파일 doc_types (book/paper/literature/policy)
- library_catalog.extra     : 도메인 확장 필드 JSONB (코어/도메인 스키마 분리 전환기 dual-write)
- ingest_jobs / ingest_job_items : 배치 잡 레이어 (stage 체크포인트 + status 실행 상태)

Revision ID: 0004_doc_type_extra_ingest_jobs
Revises: 0003_widen_varchar_fields
Create Date: 2026-06-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0004_doc_type_extra_ingest_jobs"
down_revision: Union[str, None] = "0003_widen_varchar_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── library_catalog: doc_type + extra (additive only) ───────
    op.add_column("library_catalog", sa.Column("doc_type", sa.String(16), nullable=True))
    op.add_column(
        "library_catalog",
        sa.Column("extra", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_library_catalog_doc_type", "library_catalog", ["doc_type"])

    # KCI 논문은 즉시 백필 — 나머지는 인덱싱 파이프라인이 처리하며 자동 백필
    op.execute(
        "UPDATE library_catalog SET doc_type = 'paper' "
        "WHERE source_format = 'KCI' AND doc_type IS NULL"
    )

    # ── ingest_jobs ──────────────────────────────────────────────
    op.create_table(
        "ingest_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="paper_bulk"),
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        sa.Column("manifest_key", sa.Text(), nullable=True),
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_report", JSONB(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingest_jobs_status", "ingest_jobs", ["status"])

    # ── ingest_job_items ─────────────────────────────────────────
    op.create_table(
        "ingest_job_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id", UUID(as_uuid=True),
            sa.ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("book_id", sa.String(64), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("error_group", sa.String(32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("stage_timings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("celery_task_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "book_id", name="uq_job_items_job_book"),
    )
    op.create_index("ix_job_items_job_status", "ingest_job_items", ["job_id", "status"])
    op.create_index("ix_job_items_job_stage", "ingest_job_items", ["job_id", "stage"])
    op.create_index(
        "ix_job_items_job_errgrp", "ingest_job_items", ["job_id", "error_group"],
        postgresql_where=sa.text("error_group IS NOT NULL"),
    )
    op.create_index(
        "ix_job_items_inflight", "ingest_job_items", ["updated_at"],
        postgresql_where=sa.text("status IN ('dispatched','running')"),
    )


def downgrade() -> None:
    op.drop_table("ingest_job_items")
    op.drop_table("ingest_jobs")
    op.drop_index("ix_library_catalog_doc_type", table_name="library_catalog")
    op.drop_column("library_catalog", "extra")
    op.drop_column("library_catalog", "doc_type")
