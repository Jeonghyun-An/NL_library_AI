from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import get_settings

cfg = get_settings()

# ── 비동기 (FastAPI) ─────────────────────────────────────────
engine = create_async_engine(
    cfg.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=cfg.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── 동기 (Celery Worker) ─────────────────────────────────────
sync_engine = create_engine(
    cfg.DATABASE_URL_SYNC,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
)
