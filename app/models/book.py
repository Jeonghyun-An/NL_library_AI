from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
    kdc              = Column(String(32))           # 056 $a
    ddc              = Column(String(32))           # 082 $a
    isbn             = Column(String(64))           # 020 $a
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
    access_condition = Column(String(64))           # MODS accessCondition
    target_audience  = Column(String(50))           # MODS targetAudience
    digital_origin   = Column(String(50))           # MODS digitalOrigin

    # ── KCI 논문 전용 필드 ───────────────────────────
    grade            = Column(String(50))           # KCI 등재 등급
    vol_issue        = Column(String(30))           # 권호 (예: 20(2))
    kci_citations    = Column(Integer, default=0)   # KCI 피인용수
    wos_citations    = Column(Integer, default=0)   # WOS 피인용수

    # ── 메타 ─────────────────────────────────────────
    source_format    = Column(String(10))           # 'MARC' | 'MODS' | 'KCI'
    doc_type         = Column(String(16), index=True)  # 프로파일 doc_types (book/paper/literature/policy)
    # 도메인 확장 필드 (코어 컬럼에 없는 파싱 결과 — 전환기에는 dual-write)
    extra            = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # ── RAG 관련 ──────────────────────────────────────
    raw_text         = Column(Text)                 # OCR 원본 (추후)
    summary          = Column(Text)                 # EXAONE 요약
    themes           = Column(Text)                 # LLM 추출 심층 테마 키워드 (쉼표 구분)
    introduction     = Column(Text)                 # 사서 소개글 (독자용 자연어 소개)
    cover_image_key  = Column(String(256))          # MinIO key — FLUX 자동생성 표지
    cover_prompt     = Column(Text)                 # 표지 생성에 사용된 영문 프롬프트
    is_embedded      = Column(Boolean, default=False, nullable=False)
    milvus_id        = Column(String(64))

    # ── 인덱싱 상태 추적 ─────────────────────────────────────
    # pending  : 큐에 디스패치되었지만 워커가 아직 잡지 않음
    # processing: 워커가 실제 처리 중 (Redis 락 보유)
    # embedded : 정상 완료 (is_embedded=True 와 동기)
    # failed   : 예외로 종료 (ingest_error 에 사유)
    # canceled : 사용자가 취소 요청
    ingest_state      = Column(String(16))
    ingest_task_id    = Column(String(64))           # 마지막 Celery task id
    ingest_source_key = Column(Text)                 # MinIO key — 재시도 시 참조
    ingest_started_at = Column(DateTime(timezone=True))
    ingest_finished_at= Column(DateTime(timezone=True))
    ingest_error      = Column(Text)

    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def plot(self) -> str | None:
        return (self.extra or {}).get("plot")

    @property
    def read_effect(self) -> str | None:
        return (self.extra or {}).get("read_effect")