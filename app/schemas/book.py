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
    id:          PyUUID
    record_id:   Optional[str] = None
    summary:     Optional[str] = None
    is_embedded: bool
    created_at:  datetime

    class Config:
        from_attributes = True


# ── 검색 ─────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query:      str  = Field(..., min_length=1, max_length=500, examples=["한강의 채식주의자와 비슷한 책"])
    top_k:      int  = Field(default=5, ge=1, le=20)
    use_rerank: bool = True


class SearchResult(BaseModel):
    book:   BookOut
    score:  float
    reason: str


class SearchResponse(BaseModel):
    query:            str
    rewritten_query:  str
    results:          list[SearchResult]
    elapsed_ms:       float


# ── 수집 ─────────────────────────────────────────────────────
class XlsxLoadRequest(BaseModel):
    xlsx_path: str


class IngestionRequest(BaseModel):
    cnts_ids:           list[str] = Field(..., description="CNTS ID 목록")
    force_re_summarize: bool = False


class IngestionStatus(BaseModel):
    task_id: str
    status:  str   # PENDING | STARTED | SUCCESS | FAILURE
    total:   int
    done:    int
    failed:  int