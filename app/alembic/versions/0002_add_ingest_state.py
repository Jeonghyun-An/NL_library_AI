"""library_catalog 에 인덱싱 상태 추적 컬럼 추가

- ingest_state      : pending | processing | embedded | failed | canceled
- ingest_task_id    : 마지막 Celery task id (cancel/retry 시 참조)
- ingest_source_key : 재시도용 MinIO key
- ingest_started_at / ingest_finished_at / ingest_error

Revision ID: 0002_add_ingest_state
Revises: 0001_baseline
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_ingest_state"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("library_catalog", sa.Column("ingest_state", sa.String(16), nullable=True))
    op.add_column("library_catalog", sa.Column("ingest_task_id", sa.String(64), nullable=True))
    op.add_column("library_catalog", sa.Column("ingest_source_key", sa.Text(), nullable=True))
    op.add_column("library_catalog", sa.Column("ingest_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("library_catalog", sa.Column("ingest_finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("library_catalog", sa.Column("ingest_error", sa.Text(), nullable=True))

    # 기존 is_embedded=True 인 도서는 embedded 상태로 백필
    op.execute(
        "UPDATE library_catalog SET ingest_state = 'embedded' "
        "WHERE is_embedded = true AND ingest_state IS NULL"
    )

    # 상태 인덱스 — 진행 중 / 실패 도서 조회 최적화
    op.create_index(
        "ix_library_catalog_ingest_state",
        "library_catalog",
        ["ingest_state"],
    )
    op.create_index(
        "ix_library_catalog_ingest_task_id",
        "library_catalog",
        ["ingest_task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_library_catalog_ingest_task_id", table_name="library_catalog")
    op.drop_index("ix_library_catalog_ingest_state", table_name="library_catalog")
    op.drop_column("library_catalog", "ingest_error")
    op.drop_column("library_catalog", "ingest_finished_at")
    op.drop_column("library_catalog", "ingest_started_at")
    op.drop_column("library_catalog", "ingest_source_key")
    op.drop_column("library_catalog", "ingest_task_id")
    op.drop_column("library_catalog", "ingest_state")
