from sqlalchemy import Column, Text, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from models.book import Base


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, server_default=func.now())


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), index=True)
    query = Column(Text, nullable=False)
    mode = Column(String(20))
    result = Column(Text)  # JSON string (간단하게 TEXT로)
    created_at = Column(DateTime, server_default=func.now())