from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
import uuid


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "library_catalog"

    # ── PK ──────────────────────────────────────────
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cnts_id          = Column(String(64), unique=True, nullable=False, index=True)  # CSV PK

    # ── MARC 기준 필드 ────────────────────────────────
    record_id        = Column(String(30))           # 001
    last_modified    = Column(String(20))           # 005
    title            = Column(Text, nullable=False) # 245 $a
    title_remainder  = Column(Text)                 # 245 $b
    part_number      = Column(Text)                 # MODS titleInfo/partNumber
    title_responsibility = Column(Text)             # 245 $d
    personal_author  = Column(Text)                 # 100 $a
    corporate_author = Column(Text)                 # 710 $a
    publisher        = Column(Text)                 # 260 $b
    pub_place        = Column(Text)                 # 260 $a
    pub_date         = Column(String(20))           # 260 $c
    extent           = Column(String(100))          # 300 $a
    kdc              = Column(String(20))           # 056 $a
    ddc              = Column(String(20))           # 082 $a
    isbn             = Column(String(20))           # 020 $a
    series_title     = Column(Text)                 # 440 $a
    subject          = Column(Text)                 # 650 $a
    keyword          = Column(Text)                 # 653 $a
    note             = Column(Text)                 # 500 $a
    bibliography_note= Column(Text)                 # 504 $a
    holdings         = Column(String(50))           # 049 $a
    price            = Column(String(50))           # 950 $a
    language         = Column(String(20))           # 008 [35-37]

    # ── MODS 보완 필드 ────────────────────────────────
    abstract         = Column(Text)                 # MODS abstract
    url              = Column(Text)                 # MODS location/url
    uci              = Column(String(50))           # MODS identifier(uci)
    media_type       = Column(String(50))           # MODS internetMediaType
    material_type    = Column(String(50))           # MODS typeOfResource
    genre            = Column(String(50))           # MODS genre
    access_condition = Column(String(20))           # MODS accessCondition
    target_audience  = Column(String(50))           # MODS targetAudience
    digital_origin   = Column(String(50))           # MODS digitalOrigin

    # ── 메타 ─────────────────────────────────────────
    source_format    = Column(String(10))           # 'MARC' | 'MODS'

    # ── RAG 관련 ──────────────────────────────────────
    raw_text         = Column(Text)                 # OCR 원본 (추후)
    summary          = Column(Text)                 # EXAONE 요약
    themes           = Column(Text)                 # LLM 추출 심층 테마 키워드 (쉼표 구분)
    introduction     = Column(Text)                 # 사서 소개글 (독자용 자연어 소개)
    cover_image_key  = Column(String(256))          # MinIO key — FLUX 자동생성 표지
    cover_prompt     = Column(Text)                 # 표지 생성에 사용된 영문 프롬프트
    is_embedded      = Column(Boolean, default=False, nullable=False)
    milvus_id        = Column(String(64))

    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())