"""딥리서치 잡 테이블

research_jobs / research_steps — 질문 1건과 그 실행 단계.

Revision ID: 0005_research_jobs
Revises: 0004_doc_type_extra_ingest_jobs
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0005_research_jobs"
down_revision: Union[str, None] = "0004_doc_type_extra_ingest_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("plan", JSONB()),
        sa.Column("report", JSONB()),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_research_jobs_status", "research_jobs", ["status"])

    op.create_table(
        "research_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id", UUID(as_uuid=True),
            sa.ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("subq_idx", sa.Integer()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("result", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_research_steps_job_seq", "research_steps", ["job_id", "seq"])
    op.create_index(
        "ix_research_steps_inflight", "research_steps", ["updated_at"],
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_table("research_steps")
    op.drop_index("ix_research_jobs_status", table_name="research_jobs")
    op.drop_table("research_jobs")
