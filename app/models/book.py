from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
import uuid


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "books"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nl_id       = Column(String(64), unique=True, nullable=False, index=True)

    title       = Column(String(512), nullable=False)
    author      = Column(String(256))
    publisher   = Column(String(256))
    pub_year    = Column(Integer)
    isbn        = Column(String(32))
    call_no     = Column(String(128))
    subject     = Column(String(512))

    raw_text    = Column(Text)
    summary     = Column(Text)
    summary_ver = Column(String(32))

    is_embedded = Column(Boolean, default=False, nullable=False)
    milvus_id   = Column(String(64))

    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())
