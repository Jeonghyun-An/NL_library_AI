"""library_catalog 짧은 VARCHAR 컬럼 크기 확장

isbn: 20 → 64  (MARC 020$a 수식어 포함 시 초과)
kdc : 20 → 32  (세분류 기호 포함 시 초과)
ddc : 20 → 32
access_condition: 20 → 64

Revision ID: 0003_widen_varchar_fields
Revises: 0002_add_ingest_state
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_widen_varchar_fields"
down_revision: Union[str, None] = "0002_add_ingest_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("library_catalog", "isbn",
                    existing_type=sa.String(20), type_=sa.String(64), existing_nullable=True)
    op.alter_column("library_catalog", "kdc",
                    existing_type=sa.String(20), type_=sa.String(32), existing_nullable=True)
    op.alter_column("library_catalog", "ddc",
                    existing_type=sa.String(20), type_=sa.String(32), existing_nullable=True)
    op.alter_column("library_catalog", "access_condition",
                    existing_type=sa.String(20), type_=sa.String(64), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("library_catalog", "access_condition",
                    existing_type=sa.String(64), type_=sa.String(20), existing_nullable=True)
    op.alter_column("library_catalog", "ddc",
                    existing_type=sa.String(32), type_=sa.String(20), existing_nullable=True)
    op.alter_column("library_catalog", "kdc",
                    existing_type=sa.String(32), type_=sa.String(20), existing_nullable=True)
    op.alter_column("library_catalog", "isbn",
                    existing_type=sa.String(64), type_=sa.String(20), existing_nullable=True)
