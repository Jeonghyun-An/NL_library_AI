"""baseline — 현재 운영 스키마 기준점

이 마이그레이션은 실행 시 아무 것도 변경하지 않는다.
운영 DB는 이미 이 시점의 스키마를 가지고 있으므로 `alembic stamp 0001` 로
"여기까지 적용됨" 표시만 하기 위한 베이스라인이다.

신규 환경(빈 DB)에서는 SQLAlchemy 모델로부터 `Base.metadata.create_all()` 으로
초기 스키마를 만든 뒤 `alembic stamp 0001` 을 실행해야 한다.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op — 운영 DB 는 이미 이 상태
    pass


def downgrade() -> None:
    # 베이스라인은 다운그레이드 대상이 아님
    pass
