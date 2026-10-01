# app/core/deps.py
import uuid
from typing import AsyncGenerator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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


def _parse_browser_id(raw: str | None) -> uuid.UUID | None:
    """x-session-id 값 → 브라우저 ID. v4 만 받는다 — 브라우저는 v4 가 아니면 새로 만든다."""
    if not raw:
        return None
    try:
        value = uuid.UUID(raw)
    except ValueError:
        return None
    return value if value.version == 4 else None


def get_browser_id(
    x_session_id: str | None = Header(None, alias="x-session-id"),
) -> uuid.UUID:
    """기록의 소유 단위. 브라우저 ID 는 URL 에 싣지 않는다 — nginx access log 에 남는다."""
    browser_id = _parse_browser_id(x_session_id)
    if browser_id is None:
        raise HTTPException(status_code=400, detail="x-session-id 헤더가 필요하다")
    return browser_id


def get_browser_id_optional(
    x_session_id: str | None = Header(None, alias="x-session-id"),
) -> uuid.UUID | None:
    """헤더가 없어도 동작해야 하는 엔드포인트용(딥리서치 생성의 created_by)."""
    return _parse_browser_id(x_session_id)
