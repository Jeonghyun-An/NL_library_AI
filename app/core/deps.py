from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from db.postgres import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성: 비동기 DB 세션 제공"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        
