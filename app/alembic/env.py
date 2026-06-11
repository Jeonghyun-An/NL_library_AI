"""
Alembic 환경 설정.

DB URL은 core.config.Settings 에서 가져온다 (.env 파일 자동 로드).
모델 메타데이터는 Book 모델의 Base 로부터 import 한다.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# app 디렉터리를 sys.path 에 추가 — `from core.config` 등이 동작하도록
_APP_DIR = Path(__file__).resolve().parents[1]
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.config import get_settings  # noqa: E402
from models.book import Base          # noqa: E402

# 모든 모델을 import 해서 metadata 에 등록되도록 한다
from models import book as _book_mod          # noqa: F401, E402
from models import section as _section_mod    # noqa: F401, E402
from models import figure as _figure_mod      # noqa: F401, E402
from models import search_history as _hist_mod  # noqa: F401, E402
from models import ingest_job as _job_mod     # noqa: F401, E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DB URL 주입 (sync URL — alembic 은 동기 드라이버 필요)
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL_SYNC)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """SQL 파일 생성 모드 (실제 DB 연결 없이)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드 — 실제 DB 에 적용."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
