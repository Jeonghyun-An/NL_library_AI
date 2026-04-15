"""
models/section.py — 도서 원문 섹션 저장
구조:
  1권의 책 → N개의 section (챕터/페이지 그룹 단위)
  1개의 section → M개의 chunk (Milvus에 임베딩 저장)
  chunk.section_idx → section.section_idx 로 매핑
"""
import uuid

from sqlalchemy import Column, String, Text, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from models.book import Base


class BookSection(Base):
    __tablename__ = "book_sections"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id     = Column(String(64), nullable=False, index=True)   # = cnts_id
    section_idx = Column(Integer, nullable=False)                   # 섹션 순번 (0, 1, 2, ...)
    full_text   = Column(Text, nullable=False)                      # 원문 전체
    page_start  = Column(Integer)
    page_end    = Column(Integer)
    token_count = Column(Integer)                                   # 토큰 수 (예산 계산용)
    summary     = Column(Text, nullable=True)                       # LLM 생성 섹션 요약
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # 복합 인덱스: book_id + section_idx로 빠르게 조회
    __table_args__ = (
        {"extend_existing": True},
    )