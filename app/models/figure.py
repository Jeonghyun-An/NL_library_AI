import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from models.book import Base


class BookFigure(Base):
    __tablename__ = "book_figures"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id        = Column(String(64), nullable=False, index=True)
    page_num       = Column(Integer, nullable=False)
    img_idx        = Column(Integer, nullable=False)   # 페이지 내 순서 (0-based)
    minio_key      = Column(Text, nullable=False)      # figures/{book_id}/p{page}_i{idx}.jpg
    before_context = Column(Text)                      # 이미지 앞 300자
    after_context  = Column(Text)                      # 이미지 뒤 300자
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = ({"extend_existing": True},)
