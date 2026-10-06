"""연구 어시스턴트 테이블 (round06)

research_works·research_generations·research_topics·research_gap_checks·research_reading·
paper_facets·research_proposals — 딥리서치를 이어간 연구와 그 산출물. 기존 테이블은 건드리지 않는다.
운영은 lifespan 의 create_all 이 만들고 이 리비전으로 stamp 한다(함정 14).

Revision ID: 0007_research_work
Revises: 0006_history_items
Create Date: 2026-10-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0007_research_work"
down_revision: Union[str, None] = "0006_history_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _work_fk(**kw) -> sa.Column:
    return sa.Column(
        "work_id", UUID(as_uuid=True),
        sa.ForeignKey("research_works.id", ondelete="CASCADE"), **kw,
    )


def upgrade() -> None:
    op.create_table(
        "research_works",
        sa.Column(
            "id", UUID(as_uuid=True),
            sa.ForeignKey("research_jobs.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("owner_sid", sa.String(64)),
        sa.Column("user_id", sa.String(64)),
        sa.Column("share_token", sa.String(64)),
        sa.Column("phase", sa.String(16), nullable=False, server_default=sa.text("'topics'")),
        sa.Column("concepts", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("concept_members", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("topic_id", sa.BigInteger()),
        sa.Column("progress", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("corpus_snapshot", JSONB()),
        sa.Column("memo", sa.Text()),
        sa.Column("is_example", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_research_works_owner_created", "research_works",
        ["owner_sid", sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "research_generations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _work_fk(nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target", sa.String(64)),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("model", sa.String(64)),
        sa.Column("input", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", JSONB()),
        sa.Column("error", sa.Text()),
        _created_at(),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        _updated_at(),
    )
    op.create_index("ix_research_generations_work_id", "research_generations", ["work_id"])
    # 연구마다 도는 생성은 1건 — 전역 1건 디스패처의 이중 안전장치
    op.create_index(
        "ux_research_generations_running", "research_generations", ["work_id"],
        unique=True, postgresql_where=sa.text("status = 'running'"),
    )
    # 정렬 키 priority DESC → created_at → id — 디스패처의 pick_next·queue_position 과 모델의 같은 인덱스가 함께 바뀐다
    op.create_index(
        "ix_research_generations_queued", "research_generations",
        [sa.text("priority DESC"), "created_at", "id"],
        postgresql_where=sa.text("status = 'queued'"),
    )

    op.create_table(
        "research_topics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _work_fk(nullable=False),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("research_topics.id", ondelete="CASCADE")),
        sa.Column("slot", sa.SmallInteger()),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("seed", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("card", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", sa.String(16), nullable=False, server_default=sa.text("'candidate'")),
        sa.Column("corpus_snapshot", JSONB()),
        _created_at(),
        _updated_at(),
    )
    op.create_index("ix_research_topics_work_id", "research_topics", ["work_id"])
    op.create_index("ix_research_topics_parent_id", "research_topics", ["parent_id"])
    # 처음 4장의 자리(1~4)는 연구마다 유일
    op.create_index(
        "ux_research_topics_slot", "research_topics", ["work_id", "slot"],
        unique=True, postgresql_where=sa.text("slot IS NOT NULL"),
    )

    op.create_table(
        "research_gap_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        _work_fk(nullable=False),
        sa.Column("cell_key", sa.String(128), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("results", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("m", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("corpus_snapshot", JSONB()),
        _created_at(),
    )
    op.create_index(
        "ix_research_gap_checks_work_cell", "research_gap_checks", ["work_id", "cell_key"],
    )

    op.create_table(
        "research_reading",
        _work_fk(primary_key=True),
        sa.Column("cnts_id", sa.String(64), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False, server_default=sa.text("'candidate'")),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("origin_ref", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("group_label", sa.Text()),
        sa.Column("position", sa.Integer()),
        sa.Column("note", sa.Text()),
        _created_at(),
        _updated_at(),
    )

    op.create_table(
        "paper_facets",
        sa.Column("cnts_id", sa.String(64), primary_key=True),
        sa.Column("schema_ver", sa.SmallInteger(), primary_key=True),
        sa.Column("facets", JSONB(), nullable=False),
        sa.Column("model", sa.String(64)),
        _created_at(),
    )

    op.create_table(
        "research_proposals",
        _work_fk(primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("outline", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sections", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _updated_at(),
    )


def downgrade() -> None:
    op.drop_table("research_proposals")
    op.drop_table("paper_facets")
    op.drop_table("research_reading")
    op.drop_table("research_gap_checks")
    op.drop_table("research_topics")
    op.drop_table("research_generations")
    op.drop_table("research_works")
