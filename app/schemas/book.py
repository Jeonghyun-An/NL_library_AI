from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID as PyUUID
from datetime import datetime


# ── 도서 ─────────────────────────────────────────────────────
class BookBase(BaseModel):
    cnts_id:              str
    title:                str
    title_remainder:      Optional[str] = None
    title_responsibility: Optional[str] = None
    personal_author:      Optional[str] = None
    corporate_author:     Optional[str] = None
    publisher:            Optional[str] = None
    pub_place:            Optional[str] = None
    pub_date:             Optional[str] = None
    extent:               Optional[str] = None
    kdc:                  Optional[str] = None
    ddc:                  Optional[str] = None
    isbn:                 Optional[str] = None
    series_title:         Optional[str] = None
    subject:              Optional[str] = None
    keyword:              Optional[str] = None
    note:                 Optional[str] = None
    bibliography_note:    Optional[str] = None
    holdings:             Optional[str] = None
    price:                Optional[str] = None
    language:             Optional[str] = None
    abstract:             Optional[str] = None
    url:                  Optional[str] = None
    uci:                  Optional[str] = None
    media_type:           Optional[str] = None
    material_type:        Optional[str] = None
    genre:                Optional[str] = None
    access_condition:     Optional[str] = None
    target_audience:      Optional[str] = None
    digital_origin:       Optional[str] = None
    source_format:        Optional[str] = None


class BookCreate(BookBase):
    pass


class BookOut(BookBase):
    id:               PyUUID
    record_id:        Optional[str] = None
    summary:          Optional[str] = None
    is_embedded:      bool = False
    chunk_count:      Optional[int] = None
    full_text_length: Optional[int] = None
    created_at:       datetime

    class Config:
        from_attributes = True


# ── 검색 (기존 도서 단위) ────────────────────────────────────
class SearchRequest(BaseModel):
    query:       str  = Field(..., min_length=1, max_length=500, examples=["한강의 채식주의자와 비슷한 책"])
    mode:        str  = Field(default="book", pattern="^(chunk|book)$", description="chunk: 문단 직접 표시, book: 도서 추천")
    top_k:       int  = Field(default=5, ge=1, le=20)
    use_rewrite: bool = True
    use_rerank:  bool = True


class SearchResult(BaseModel):
    """도서 모드 결과 (기존 호환)"""
    book:   BookOut
    score:  float
    reason: str


class SearchResponse(BaseModel):
    """도서 모드 응답 (기존 호환)"""
    query:           str
    rewritten_query: str
    results:         list[SearchResult]
    elapsed_ms:      float


# ── 검색 (청크 모드 추가) ────────────────────────────────────
class ChunkHit(BaseModel):
    """청크 단위 검색 결과"""
    chunk_id:      str
    book_id:       str
    chunk_idx:     int
    text:          str
    page_start:    int
    page_end:      int
    score:         float
    rerank_score:  Optional[float] = None


class BookChunkGroup(BaseModel):
    """도서 모드에서 도서별 관련 청크 묶음"""
    book_id:    str
    book_info:  Optional[BookOut] = None
    best_score: float
    chunks:     list[ChunkHit] = []
    reason:     Optional[str] = None


class ChunkSearchResponse(BaseModel):
    """청크 모드 응답"""
    mode:            str = "chunk"
    query:           str
    rewritten_query: Optional[str] = None
    answer:          Optional[str] = None
    chunks:          list[ChunkHit] = []
    elapsed_ms:      float


class BookSearchResponse(BaseModel):
    """도서 모드 응답 (청크 기반 확장)"""
    mode:            str = "book"
    query:           str
    rewritten_query: Optional[str] = None
    books:           list[BookChunkGroup] = []
    elapsed_ms:      float


# ── 수집 (기존 유지 + 파일 업로드 추가) ──────────────────────
class XlsxLoadRequest(BaseModel):
    xlsx_path: str


class IngestionRequest(BaseModel):
    cnts_ids:           list[str] = Field(..., description="CNTS ID 목록")
    force_re_summarize: bool = False


class FileIngestRequest(BaseModel):
    """단일 파일 수집 요청"""
    book_id:   str
    file_path: Optional[str] = None    # 서버 로컬 경로
    minio_key: Optional[str] = None    # MinIO 키


class BatchIngestRequest(BaseModel):
    """배치 파일 수집 요청"""
    files: list[FileIngestRequest]


class IngestionStatus(BaseModel):
    task_id: str
    status:  str    # PENDING | STARTED | SUCCESS | FAILURE
    total:   int
    done:    int
    failed:  int


class TaskStatusOut(BaseModel):
    task_id: str
    status:  str
    result:  Optional[dict] = None